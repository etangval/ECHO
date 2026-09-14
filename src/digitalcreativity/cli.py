"""Command-line interface. All scientific observations remain local."""
import os
# Small repeated linear algebra benefits from avoiding BLAS thread overhead.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
import argparse
from pathlib import Path
import json
import sys
import numpy as np
import pandas as pd
from . import __version__, adapters, pipeline


def parse_factor(value):
    try:
        if "/" in value:
            a, b = value.split("/")
            return float(a)/float(b)
        return float(value)
    except (ValueError, ZeroDivisionError):
        raise argparse.ArgumentTypeError("Use a positive factor such as 20 or 1/40")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Event-preserving point-process sonification")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    synth = commands.add_parser("synthetic", help="Generate artificial marked events and explicit coverage")
    synth.add_argument("output", type=Path)
    synth.add_argument("--seconds", type=float, default=300)
    synth.add_argument("--rate", type=float, default=2)
    synth.add_argument("--categories", type=int, default=12)
    synth.add_argument("--seed", type=int, default=12345)
    run = commands.add_parser("sonify", help="Prepare marks and optimise a MIDI mapping")
    run.add_argument("input", type=Path)
    run.add_argument("output", type=Path)
    run.add_argument("--adapter", choices=["categorical", "geographic", "ordered"], default="categorical")
    run.add_argument("--mode", choices=["auto", "all"], default="auto")
    run.add_argument("--intervals", type=Path)
    run.add_argument("--duration", type=float, default=120)
    run.add_argument("--voices", type=int, default=70)
    run.add_argument("--min-category-events", type=int, default=1, help="Optional declared identity eligibility threshold, before uniform sampling")
    run.add_argument("--digits", type=int, choices=[1, 2], default=1)
    run.add_argument("--steps", type=int, default=14000)
    run.add_argument("--seed", type=int, default=20260909)
    run.add_argument("--speed", type=parse_factor, default=1., help="Only in all mode; source seconds/playback second")
    run.add_argument("--random-baseline", action="store_true")
    render = commands.add_parser("render", help="Render a prepared run to stereo WAV and MP3")
    render.add_argument("folder", type=Path)
    render.add_argument("--condition", choices=["optimized", "random"], default="optimized")
    render.add_argument("--instrument", choices=["piano", "sine"], default="piano")
    render.add_argument("--wav-only", action="store_true")
    render.add_argument("--sample-cache", type=Path)
    inverse = commands.add_parser("decode", help="Recover categorical events from MIDI plus mapping/clock metadata")
    inverse.add_argument("folder", type=Path)
    inverse.add_argument("output", type=Path)
    inverse.add_argument("--condition", choices=["optimized", "random"], default="optimized")
    check = commands.add_parser("verify", help="Check hashes, event preservation, timing, pedal and ending")
    check.add_argument("folder", type=Path)
    imp = commands.add_parser("import", help="Normalize a local long CSV, USGS CSV or NICER FITS file")
    imp.add_argument("input", type=Path)
    imp.add_argument("output", type=Path)
    imp.add_argument("--format", choices=["csv", "usgs", "nicer"], required=True)
    imp.add_argument("--time-column", default="time")
    imp.add_argument("--category-column", default="category")
    imp.add_argument("--time-unit", choices=["seconds", "milliseconds"], default="seconds")
    imp.add_argument("--pi-min", type=float, default=20)
    imp.add_argument("--pi-max", type=float, default=1500)
    prep = commands.add_parser("prepare", help="Prepare a supported public source locally; originals stay unchanged")
    prep.add_argument("source", choices=["retail", "taxi", "hippocampus"])
    prep.add_argument("input", type=Path)
    prep.add_argument("output", type=Path)
    prep.add_argument("--relaxed-taxi", action="store_true")
    analysis = commands.add_parser("analyze", help="Coverage-aware point-process diagnostics (research extra)")
    analysis.add_argument("folder", type=Path)
    analysis.add_argument("output", type=Path)
    analysis.add_argument("--asynchronous", action="store_true", help="Omit simultaneous-population analysis (required for independent animal deployments)")
    analysis.add_argument("--surrogates", action="store_true", help="Also compute episode-interval and local-count shuffles")
    listening = commands.add_parser("listening", help="Aggregate a local paired-rating JSON; no records copied")
    listening.add_argument("input", type=Path)
    listening.add_argument("output", type=Path)
    listening.add_argument("--replicates", type=int, default=20000)
    study = commands.add_parser("render-study", help="Archived additive instrument used in the listening comparison")
    study.add_argument("events", type=Path, help="Private event NPZ, optimized or random")
    study.add_argument("output", type=Path, help="Destination WAV")
    study.add_argument("--duration", type=float, default=120)
    study.add_argument("--mp3", action="store_true", help="Also make a constant-gain -23 LUFS, -2 dBTP capped MP3")
    args = parser.parse_args(argv)
    try:
        if args.command == "synthetic":
            if args.output.exists() or args.output.with_suffix(".coverage.csv").exists():
                raise ValueError("Synthetic destination already exists")
            if not (np.isfinite(args.seconds) and args.seconds > 0 and np.isfinite(args.rate) and args.rate > 0 and 1 <= args.categories <= 10000 and args.seed >= 0):
                raise ValueError("Require positive finite seconds/rate, positive category count and nonnegative seed")
            rng = np.random.default_rng(args.seed)
            n = int(rng.poisson(args.seconds*args.rate))
            if n == 0:
                raise ValueError("No synthetic events sampled; increase rate or duration")
            times = np.sort(rng.uniform(0, args.seconds, n))
            # Mark transitions are correlated in time; no scientific data used.
            phase = np.floor(times/8).astype(int) % args.categories
            categories = (phase+rng.integers(0, min(3, args.categories), n)) % args.categories
            frame = pd.DataFrame(dict(event_id=np.arange(1, n+1), time_seconds=times,
                category=[f"synthetic_{c+1:02d}" for c in categories]))
            args.output.parent.mkdir(parents=True, exist_ok=True)
            frame.to_csv(args.output, index=False, float_format="%.17g")
            pd.DataFrame(dict(start_seconds=[0.], stop_seconds=[args.seconds])).to_csv(args.output.with_suffix(".coverage.csv"), index=False)
            result = dict(events=n, categories=args.categories, seed=args.seed, data="Artificial example only")
        elif args.command == "sonify":
            if args.mode == "auto" and args.speed != 1.:
                raise ValueError("--speed only applies in --mode all")
            if args.output.exists() and any(args.output.iterdir()):
                raise ValueError("Output directory is not empty")
            p = pipeline.protocol(args.duration, args.voices, args.digits, args.steps, args.seed)
            if args.min_category_events < 1:
                raise ValueError("min-category-events must be positive")
            p["minimum_category_events"] = args.min_category_events
            result = pipeline.sonify(args.input, args.output, p, args.adapter, args.mode, args.intervals, args.speed, args.random_baseline)
            result = {key:result[key] for key in ["prepared_event_count", "timing", "objective_scores"]}
        elif args.command == "render":
            from .audio import render as render_audio
            result = render_audio(args.folder, args.condition, args.instrument, not args.wav_only, args.sample_cache)
            result = {key:result[key] for key in ["duration_seconds", "events", "peak", "final_100ms_rms_dbfs"]}
        elif args.command == "decode":
            if args.output.exists():
                raise ValueError("Decode destination already exists")
            manifest = json.loads((args.folder/"manifest.json").read_text(encoding="utf-8"))
            frame = pipeline.decode_midi(args.folder/f"{args.condition}.mid", manifest, args.condition)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            frame.to_csv(args.output, index=False, float_format="%.17g")
            result = dict(recovered_events=len(frame), precision="Source-clock-scaled MIDI tick precision")
        elif args.command == "verify":
            result = pipeline.verify(args.folder)
        elif args.command == "prepare":
            from . import preprocessing
            pipeline.new_directory(args.output)
            if args.source == "taxi":
                result = preprocessing.prepare_taxi(args.input, args.output, strict=not args.relaxed_taxi)
            else:
                result = getattr(preprocessing, "prepare_"+args.source)(args.input, args.output)
        elif args.command == "analyze":
            from .processes import analyze_source
            pipeline.new_directory(args.output)
            asynchronous = args.asynchronous
            result = analyze_source(args.folder, args.output, population=not asynchronous)
            if args.surrogates:
                from .surrogates import analyze_surrogates
                analyze_surrogates(args.folder, args.output/'surrogates', population=not asynchronous)
        elif args.command == "listening":
            from .listening import summarize, adjusted_means
            if args.output.exists():
                raise ValueError("Aggregate destination already exists")
            if args.replicates < 100:
                raise ValueError("Use at least 100 bootstrap replicates")
            rows = json.loads(args.input.read_text(encoding="utf-8"))
            if isinstance(rows, dict):
                rows = rows["responses"]
            result = summarize(rows, replicates=args.replicates)
            if all("randomVariant" in row for row in rows):
                result["adjusted"] = adjusted_means(rows)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            pipeline.save_json(args.output, result)
        elif args.command == "render-study":
            from .study_synthesis import render_study_wav, loudness_mp3
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with np.load(args.events, allow_pickle=False) as data:
                result = render_study_wav(dict(data), args.output, args.duration)
            if args.mp3:
                result["mp3"] = loudness_mp3(args.output, args.output.with_suffix(".mp3"))
            pipeline.save_json(args.output.with_suffix(".render.json"), result)
        else:
            folder = pipeline.new_directory(args.output)
            if args.format == "nicer":
                if args.pi_min > args.pi_max:
                    raise ValueError("pi-min must not exceed pi-max")
                frame, coverage, result = adapters.import_nicer(args.input, args.pi_min, args.pi_max)
                coverage.to_csv(folder/"coverage.csv", index=False, float_format="%.17g")
            else:
                frame, result = adapters.import_csv(args.input, args.format, args.time_column,
                    args.category_column, 1000 if args.time_unit == "milliseconds" else 1)
            frame.to_csv(folder/"events.csv", index=False, float_format="%.17g")
            result["source_sha256"] = pipeline.digest(args.input)
            pipeline.save_json(folder/"import.json", result)
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    except (ValueError, KeyError, OSError, RuntimeError) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
