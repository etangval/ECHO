"""Archived additive renderer used in the fixed listening comparison.

This explicit three-harmonic sustained-tone instrument is not the later
sampled-piano renderer. It includes its original attack mixture and delay taps.
No scientific observations or recorded stimuli are distributed here.
"""
from pathlib import Path
import math
import numpy as np
from .pipeline import digest

def render_study_wav(events, path, duration=120., target_rms=.05, peak_ceiling=.75):
    import wave
    events = {k: np.asarray(v) for k,v in events.items()}
    required = ('onset_seconds', 'pitch', 'velocity', 'pan_cc10')
    n = len(events['onset_seconds'])
    if any(len(events[k]) != n or not np.isfinite(events[k]).all() for k in required):
        raise ValueError('Event arrays must have equal lengths and finite values')
    order = np.argsort(events['onset_seconds'], kind='stable')
    events = {k: v[order] for k, v in events.items() if v.ndim == 1 and len(v) == n}
    if np.any((events['pitch'] < 21) | (events['pitch'] > 108)) or np.any(events['pitch'] != np.rint(events['pitch'])):
        raise ValueError('Require integer piano pitches 21..108')
    if np.any((events['velocity'] < 1) | (events['velocity'] > 127)) or np.any((events['pan_cc10'] < 0) | (events['pan_cc10'] > 127)):
        raise ValueError('Invalid MIDI velocity or pan')
    if "soft_attack_fraction" not in events:
        memory = events["repeat_memory"]
        events["soft_attack_fraction"] = memory/(1+memory)
    if Path(path).exists(): raise ValueError("Output already exists")
    if not np.isfinite(target_rms) or target_rms <= 0 or not 0 < peak_ceiling < 1:
        raise ValueError('Require positive RMS target and peak ceiling below one')
    if not np.isfinite(events['soft_attack_fraction']).all() or np.any((events['soft_attack_fraction'] < 0) | (events['soft_attack_fraction'] > 1)):
        raise ValueError('Soft attack fractions must lie in [0,1]')
    for pitch in np.unique(events['pitch']):
        if len(np.unique(events['pan_cc10'][events['pitch'] == pitch])) != 1:
            raise ValueError('The archived instrument requires a fixed pan per pitch')
    if not 12 <= duration <= 3600: raise ValueError("Duration must be 12..3600 seconds")
    if not len(events["onset_seconds"]) or np.any(events["onset_seconds"] < 0) or np.any(events["onset_seconds"] >= duration-10):
        raise ValueError("Events must precede the ten-second ending")
    sr = 44100
    length = int(duration*sr)
    dry = np.zeros((length, 2), dtype=np.float32)
    for pitch in np.unique(events["pitch"]):
        rows = np.flatnonzero(events["pitch"] == pitch)
        tau = float(np.clip(1.7*2**((60-pitch)/52), .65, 3.))
        tt = np.arange(round(min(15., 7*tau)*sr))/sr
        kernels = []
        for attack in [.06, .19]:
            kernel = np.exp(-tt/tau)-np.exp(-tt/attack)
            kernel /= kernel.max()
            kernel[-round(.12*sr):] *= np.linspace(1, 0, round(.12*sr))
            kernels.append(kernel.astype(np.float32))
        envelope = np.zeros(length, dtype=np.float32)
        spans = []
        for row in rows:
            start = round(events["onset_seconds"][row]*sr)
            stop = min(length, start+len(tt))
            beta = events["soft_attack_fraction"][row]
            envelope[start:stop] += (events["velocity"][row]/90)**1.8*((1-beta)*kernels[0][:stop-start]+beta*kernels[1][:stop-start])
            if spans and start <= spans[-1][1]:
                spans[-1][1] = max(spans[-1][1], stop)
            else:
                spans.append([start, stop])
        x = events["pan_cc10"][rows[0]]/127
        position = np.array([math.cos(x*np.pi/2), math.sin(x*np.pi/2)], dtype=np.float32)
        f = 440*2**((pitch-69)/12)
        for a, b in spans:
            time = np.arange(a, b)/sr
            wavelet = np.sin(2*np.pi*f*time)+.105*np.sin(4*np.pi*f*time)+.023*np.sin(6*np.pi*f*time)
            dry[a:b] += (envelope[a:b]*wavelet)[:, None]*position
    room = dry.copy()
    taps = [(.037,.090),(.061,.075),(.103,.057),(.167,.045),(.263,.035),(.397,.027),(.577,.021),(.811,.016),(1.109,.012),(1.487,.008)]
    for j, (delay, level) in enumerate(taps):
        dl = round(delay*sr); dr = round((delay+.009+.003*(j%3))*sr)
        room[dl:, 0] += level*dry[:-dl, 1]
        room[dr:, 1] += level*dry[:-dr, 0]
    room[-round(.12*sr):] *= np.linspace(1, 0, round(.12*sr))[:, None]
    raw_rms = float(np.sqrt(np.mean(room**2)))
    gain = min(target_rms/max(raw_rms, 1e-12), peak_ceiling/max(float(np.max(np.abs(room))), 1e-12))
    room *= gain
    pcm = np.rint(room*32767).astype("<i2")
    with wave.open(str(path), "wb") as f:
        f.setnchannels(2); f.setsampwidth(2); f.setframerate(sr); f.writeframes(pcm.tobytes())
    assert np.isfinite(room).all() and np.abs(room).max() <= peak_ceiling+1e-6
    return {"duration_seconds": duration, "rms": float(np.sqrt(np.mean(room**2))), "peak": float(np.max(np.abs(room))), "gain": gain, "path": str(path), "sha256": digest(path)}


def loudness_mp3(wav, output, target_lufs=-23., ceiling_dbtp=-2.):
    """Measure BS.1770 loudness, then apply one constant gain (no limiter).

    MP3 encoding can slightly change integrated loudness and peak. Both the
    source measurement and decoded delivery measurement are saved for audit.
    """
    import json
    import re
    from .audio import ffmpeg
    if Path(output).exists():
        raise ValueError('Output already exists')
    # FFmpeg's measurement filter reports on stderr; keep all subprocess output
    # captured and use the same binary resolver as the public audio renderer.
    import shutil
    import subprocess
    binary = shutil.which('ffmpeg')
    if binary is None:
        import imageio_ffmpeg
        binary = imageio_ffmpeg.get_ffmpeg_exe()
    def measure(path):
        command = [binary, '-hide_banner', '-i', str(path), '-af',
                   f'loudnorm=I={target_lufs}:TP={ceiling_dbtp}:LRA=11:print_format=json', '-f', 'null', '-']
        run = subprocess.run(command, capture_output=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if run.returncode:
            raise RuntimeError(run.stderr.decode(errors='replace'))
        found = re.findall(r'\{\s*"input_i".*?\}', run.stderr.decode(errors='replace'), re.S)
        if not found:
            raise RuntimeError('FFmpeg did not return a loudness measurement')
        return json.loads(found[-1])
    before = measure(wav)
    integrated, peak = float(before['input_i']), float(before['input_tp'])
    if not np.isfinite([integrated, peak]).all():
        raise ValueError('Loudness is undefined for this input')
    gain_db = min(target_lufs-integrated, ceiling_dbtp-peak)
    ffmpeg(['-n', '-i', str(wav), '-af', f'volume={gain_db:.8f}dB', '-ar', '44100',
            '-ac', '2', '-codec:a', 'libmp3lame', '-b:a', '160k', str(output)])
    return dict(target_lufs=target_lufs, ceiling_dbtp=ceiling_dbtp,
                constant_gain_db=gain_db, source_measurement=before,
                decoded_measurement=measure(output), sha256=digest(output))

