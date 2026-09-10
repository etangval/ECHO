"""Bounded-memory sampled-piano renderer, with held-pedal decay and no added room."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import math
import os
import shutil
import subprocess
import tempfile
import urllib.request
import wave
import numpy as np
from .pipeline import digest, save_json

SR = 44100
SAMPLE_COMMIT = "869b6f8d9cddb47d966238c012041480b1ce517a"
SOURCE = f"https://raw.githubusercontent.com/Tonejs/audio/{SAMPLE_COMMIT}/salamander/"
CREDIT = ("Piano samples: Salamander Grand Piano by Alexander Holm, via Tone.js audio; "
          "CC BY 3.0 https://creativecommons.org/licenses/by/3.0/ ; "
          f"https://github.com/Tonejs/audio/tree/{SAMPLE_COMMIT}/salamander . "
          "Adapted by pitch resampling, amplitude dynamics and stereo balance.")


def ffmpeg(args):
    binary = shutil.which("ffmpeg")
    if binary is None:
        try:
            import imageio_ffmpeg
            binary = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError as exc:
            raise ValueError("Install FFmpeg or the audio extra: pip install '.[audio]'") from exc
    run = subprocess.run([binary, "-v", "error", *args], capture_output=True,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if run.returncode:
        raise RuntimeError(run.stderr.decode(errors="replace"))
    return run.stdout


def sample_name(pitch):
    return {0:"C", 3:"Ds", 6:"Fs", 9:"A"}[pitch % 12]+str(pitch//12-1)+".mp3"


def piano_buffers(pitches, cache=None):
    cache = Path(cache) if cache else Path(os.environ.get("XDG_CACHE_HOME", Path.home()/".cache"))/"digitalcreativity"/SAMPLE_COMMIT
    cache.mkdir(parents=True, exist_ok=True)
    anchors = np.arange(21, 109, 3)
    nearest = {p:int(anchors[np.argmin(abs(anchors-p))]) for p in pitches}
    names = sorted({sample_name(p) for p in nearest.values()})
    def fetch(name):
        path = cache/name
        if not path.exists():
            request = urllib.request.Request(SOURCE+name, headers={"User-Agent":"digitalcreativity/0.1.0"})
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read()
            if len(data) < 2000:
                raise ValueError("Piano sample download was unexpectedly short")
            # Atomic replacement prevents partially downloaded cache entries.
            with tempfile.NamedTemporaryFile(dir=cache, delete=False) as temporary:
                temporary.write(data)
                tmp = Path(temporary.name)
            tmp.replace(path)
        return dict(name=name, url=SOURCE+name, sha256=digest(path))
    with ThreadPoolExecutor(max_workers=4) as pool:
        assets = list(pool.map(fetch, names))
    buffers, details = {}, {}
    for pitch in pitches:
        anchor = nearest[pitch]
        rate = SR*2**((pitch-anchor)/12)
        data = ffmpeg(["-i", str(cache/sample_name(anchor)), "-af", f"asetrate={rate:.10f},aresample={SR}",
                       "-f", "f32le", "-acodec", "pcm_f32le", "-ac", "2", "pipe:1"])
        pcm = np.frombuffer(data, dtype="<f4").reshape(-1, 2).copy()
        magnitude = np.max(abs(pcm), axis=1)
        audible = np.flatnonzero(magnitude > max(float(magnitude.max())*.0005, 1e-6))
        start = max(0, int(audible[0])-22) if len(audible) else 0
        if start >= round(.10*SR):
            raise ValueError(f"Unexpected piano sample attack latency: pitch {pitch}")
        pcm = pcm[start:]
        guard = min(round(.035*SR), len(pcm))
        pcm[-guard:] *= np.linspace(1, 0, guard)[:, None]
        pcm[:44] *= np.linspace(0, 1, 44)[:, None]
        buffers[pitch] = pcm
        details[str(pitch)] = dict(anchor_midi_pitch=anchor, leading_samples_trimmed=start,
                                  recorded_decay_seconds=len(pcm)/SR)
    return buffers, dict(credit=CREDIT, pinned_sample_commit=SAMPLE_COMMIT, assets=assets, pitches=details)


def sine_buffers(pitches):
    # An offline smoke-test instrument, not the piano used in the demonstrations.
    t = np.arange(10*SR)/SR
    envelope = (1-np.exp(-t/.01))*np.exp(-t/1.5)
    envelope[-round(.035*SR):] *= np.linspace(1, 0, round(.035*SR))
    return {p:np.repeat((np.sin(2*np.pi*440*2**((p-69)/12)*t)*envelope)[:, None], 2, axis=1).astype(np.float32)
            for p in pitches}, dict(instrument="synthetic sine; offline verification only")


def render(folder, condition="optimized", instrument="piano", mp3=True, cache=None):
    folder = Path(folder)
    manifest = json.loads((folder/"manifest.json").read_text(encoding="utf-8"))
    events_file = folder/("events.npz" if condition == "optimized" else "random_events.npz")
    if condition not in manifest["pitch_maps"]:
        raise ValueError("The requested condition is absent from this run")
    if digest(events_file) != manifest["hashes"][events_file.name]:
        raise ValueError("Event sidecar hash does not match the run")
    with np.load(events_file, allow_pickle=False) as loaded:
        events = dict(loaded)
    duration = manifest["protocol"]["output_seconds"]
    onset = events["onset_seconds"]
    if not np.all(onset < duration-manifest["protocol"]["tail_seconds"]):
        raise ValueError("Quiet-tail constraint violated")
    stem = f"{condition}_{instrument}"
    wav, encoded = folder/f"{stem}.wav", folder/f"{stem}.mp3"
    if wav.exists() or encoded.exists():
        raise ValueError("Audio output already exists; move it before rerendering")
    pitches = sorted(map(int, np.unique(events["pitch"])))
    buffers, provenance = piano_buffers(pitches, cache) if instrument == "piano" else sine_buffers(pitches)
    for pitch in pitches:
        pans = np.unique(events["pan_cc10"][events["pitch"] == pitch])
        if len(pans) != 1:
            raise ValueError("One fixed stereo position per identity is required")
        angle = float(pans[0])/127*math.pi/2
        buffers[pitch] *= np.array([math.cos(angle), math.sin(angle)], np.float32)*math.sqrt(2)
    starts = np.rint(onset*SR).astype(np.int64)
    amplitude = (events["velocity"].astype(np.float32)/90)**1.8
    total, chunk = round(duration*SR), 30*SR
    maximum = max(map(len, buffers.values()))
    peak, energy = 0., 0.
    # Temporary PCM lives beside the output, is never committed or uploaded.
    with tempfile.TemporaryFile(dir=folder) as raw:
        for begin in range(0, total, chunk):
            end = min(total, begin+chunk)
            mix = np.zeros((end-begin, 2), np.float32)
            left = np.searchsorted(starts, begin-maximum, side="right")
            right = np.searchsorted(starts, end, side="left")
            for i in range(left, right):
                buf = buffers[int(events["pitch"][i])]
                start = int(starts[i])
                first, last = max(begin, start), min(end, start+len(buf))
                if first < last:
                    mix[first-begin:last-begin] += buf[first-start:last-start]*amplitude[i]
            first = max(begin, total-2*SR)
            if first < end:
                fade = .5*(1+np.cos(np.pi*np.arange(first-total+2*SR, end-total+2*SR)/(2*SR-1)))
                mix[first-begin:] *= fade[:, None]
            peak = max(peak, float(abs(mix).max()))
            energy += float(np.sum(mix.astype(float)**2))
            raw.write(mix.astype("<f4", copy=False).tobytes())
        rms = math.sqrt(energy/(2*total))
        gain = min(.05/max(rms, 1e-15), .75/max(peak, 1e-15))
        raw.seek(0)
        terminal = None
        with wave.open(str(wav), "wb") as output:
            output.setnchannels(2)
            output.setsampwidth(2)
            output.setframerate(SR)
            while data := raw.read(chunk*8):
                block = np.frombuffer(data, "<f4").reshape(-1, 2)*gain
                output.writeframes(np.rint(np.clip(block, -1, 1)*32767).astype("<i2").tobytes())
                terminal = block[-SR//10:]
    if mp3:
        ffmpeg(["-n", "-i", str(wav), "-c:a", "libmp3lame", "-b:a", "192k",
                "-metadata", "comment="+(CREDIT if instrument == "piano" else "Synthetic sine test instrument"), str(encoded)])
    report = dict(duration_seconds=total/SR, sample_rate=SR, stereo=True,
        events=len(onset), instrument=instrument, artificial_reverb=False,
        pedal="Held; entire recorded decay, no note-off damping or separate sympathetic resonance model",
        terminal_gain_taper_seconds=2, no_new_notes_last_seconds=manifest["protocol"]["tail_seconds"],
        gain=gain, rms=rms*gain, peak=peak*gain,
        final_100ms_rms_dbfs=20*math.log10(max(float(np.sqrt(np.mean(terminal.astype(float)**2))), 1e-15)),
        onset_rounding_max_seconds=float(np.max(abs(starts/SR-onset))),
        provenance=provenance, wav_sha256=digest(wav), mp3_sha256=digest(encoded) if mp3 else None)
    save_json(folder/f"{stem}_audio.json", report)
    if instrument == "piano":
        (folder/"PIANO_CREDITS.txt").write_text(CREDIT+"\n", encoding="utf-8")
    return report
