"""Local-only preparation, optimisation, symbolic export and audit."""
from importlib.resources import files
from pathlib import Path
import hashlib
import json
import platform
import numpy as np
import pandas as pd
import mido
from . import __version__
from . import adapters, engine, temporal


def save_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+"\n", encoding="utf-8")


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def new_directory(path):
    path = Path(path)
    if path.exists() and any(path.iterdir()):
        raise ValueError(f"Output directory is not empty: {path}")
    path.mkdir(parents=True, exist_ok=True)
    return path


def protocol(duration=120., voices=70, digits=1, steps=14000, seed=20260909):
    if not np.isfinite(duration) or not 12 <= duration <= 3600:
        raise ValueError("Duration must be 12 to 3600 seconds")
    if not 1 <= voices <= 70 or digits not in [1, 2] or steps < 1 or seed < 0:
        raise ValueError("Require 1..70 voices, 1..2 significant digits, positive steps and nonnegative seed")
    p = json.loads(files("digitalcreativity").joinpath("defaults.json").read_text())
    active = duration-p["intro_seconds"]-p["tail_seconds"]
    p.update(output_seconds=float(duration), active_seconds=active, voice_budget=voices,
             speed_significant_digits=digits, mapping_proposals_each=steps, seed=seed,
             context_expected_events=max(20, round(1024*active/116)))
    return p


def read_events(path):
    frame = pd.read_csv(path, dtype={"category": str, "event_id": str}, float_precision="round_trip", keep_default_na=False)
    if "time_seconds" not in frame or frame.empty:
        raise ValueError("A nonempty CSV with time_seconds is required")
    frame["time_seconds"] = pd.to_numeric(frame.time_seconds, errors="raise")
    if not np.isfinite(frame.time_seconds).all():
        raise ValueError("Event times must be finite")
    if "event_id" not in frame:
        frame.insert(0, "event_id", [str(i+1) for i in range(len(frame))])
    if frame.event_id.isna().any() or (frame.event_id == "").any() or frame.event_id.duplicated().any():
        raise ValueError("event_id must be present and unique for every row")
    # Restrict copied columns explicitly: do not carry arbitrary personal fields.
    known = [c for c in ["event_id", "time_seconds", "category", "latitude_deg", "longitude_deg", "ordered_mark"] if c in frame]
    return frame[known].sort_values("time_seconds", kind="stable").reset_index(drop=True)


def prepare_marks(frame, kind, k, seed, minimum_category_events=1):
    if kind == "categorical":
        if "category" not in frame or frame.category.isna().any() or (frame.category == "").any():
            raise ValueError("Every event requires a nonempty category")
        all_categories = np.sort(frame.category.unique())
        counts = frame.category.value_counts()
        categories = np.sort(counts[counts >= minimum_category_events].index.to_numpy())
        if not len(categories):
            raise ValueError("No category meets the explicitly declared minimum event count")
        rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed, k])))
        selected = np.sort(rng.choice(categories, min(k, len(categories)), replace=False))
        keep = frame.category.isin(selected)
        frame = frame.loc[keep].copy()
        labels = np.searchsorted(selected, frame.category.to_numpy())
        info = dict(method="fixed_seed_uniform_identity_selection", input_categories=len(all_categories),
                    eligible_categories=len(categories), minimum_category_events=minimum_category_events,
                    ineligible_categories=len(all_categories)-len(categories),
                    categories=selected.tolist(), retained_events=len(frame), seed=seed,
                    inclusion_probability=min(k, len(categories))/len(categories))
    elif kind == "geographic":
        labels, info = adapters.geographic_groups(frame, k, seed)
        frame = frame.copy()
        selected = [f"region_{i+1:02d}" for i in range(k)]
        frame["category"] = np.asarray(selected)[labels]
        info["categories"] = selected
    elif kind == "ordered":
        labels, info = adapters.ordered_groups(frame.ordered_mark.to_numpy(), k)
        frame = frame.copy()
        selected = [f"band_{i+1:02d}" for i in range(k)]
        frame["category"] = np.asarray(selected)[labels]
        info["categories"] = selected
    else:
        raise ValueError("Unknown mark adapter")
    frame["group_index"] = labels
    return frame.reset_index(drop=True), info


def read_coverage(path, times):
    if path is None:
        raise ValueError("Auto mode requires --intervals CSV (start_seconds,stop_seconds); do not infer observation coverage from events")
    frame = pd.read_csv(path).sort_values("start_seconds")
    pair = frame[["start_seconds", "stop_seconds"]].to_numpy(float)
    if not len(pair) or not np.isfinite(pair).all() or np.any(pair[:, 1] <= pair[:, 0]):
        raise ValueError("Coverage intervals must be finite and have positive duration")
    if len(pair) > 1 and np.any(pair[1:, 0] < pair[:-1, 1]):
        raise ValueError("Coverage intervals must not overlap")
    covered = np.zeros(len(times), bool)
    for a, b in pair:
        covered |= (times >= a) & (times < b)
    if not covered.all():
        raise ValueError("Events lie outside the supplied half-open coverage intervals; filter explicitly before sonification")
    return [(i+1, float(a), float(b)) for i, (a, b) in enumerate(pair)]


def sonify(source, output, p, adapter="categorical", mode="auto", intervals=None, speed=1., random_baseline=False):
    frame = read_events(source)
    total = len(frame)
    # Validate coverage against all input events before selecting identities.
    coverage = read_coverage(intervals, frame.time_seconds.to_numpy()) if mode == "auto" else None
    frame, mark_info = prepare_marks(frame, adapter, p["voice_budget"], p["seed"], p.get("minimum_category_events", 1))
    t = frame.time_seconds.to_numpy(float)
    group = frame.group_index.to_numpy(int)
    categories = mark_info["categories"]
    k = len(categories)
    context = None
    if mode == "auto":
        context, candidates = temporal.representative_context(t, group, k, coverage, p)
        timing, onset, trials = temporal.choose_speed(t, context, p)
        frame = frame.iloc[timing["row_start"]:timing["row_stop_exclusive"]].copy()
        group = frame.group_index.to_numpy(int)
    elif mode == "all":
        if not np.isfinite(speed) or speed <= 0:
            raise ValueError("Speed must be positive source seconds per playback second")
        preferred = temporal.preferred_factors(p)
        match = next((x for x in preferred if np.isclose(x["speed"], speed, rtol=1e-12, atol=0)), None)
        if match is None:
            raise ValueError("Use a factor (or reciprocal) with the declared one or two significant digits")
        origin = float(t[0])
        onset = (t-origin)/speed+p["intro_seconds"]
        duration = max(12., float(onset[-1]+p["tail_seconds"]+.01))
        if duration > 3600:
            raise ValueError("Output exceeds one hour; use a faster speed or a smaller explicit input")
        p = dict(p, output_seconds=duration, active_seconds=duration-p["intro_seconds"]-p["tail_seconds"])
        timing = dict(match, source_start_seconds=origin,
                      source_stop_seconds=float(np.nextafter(t[-1], np.inf)),
                      auditory_profile_enforced=False, scope="All events of the retained categories")
    else:
        raise ValueError("mode must be auto or all")
    if not len(onset) or not np.all(onset < p["output_seconds"]-p["tail_seconds"]):
        raise ValueError("No valid events or an onset intrudes into the quiet tail")
    objective = engine.Objective(onset, group, k, duration=p["output_seconds"])
    runs = []
    best = None
    for seed in p["mapping_seeds"]:
        mapping, report = objective.optimize(seed, p["mapping_proposals_each"])
        runs.append(report)
        if best is None or report["optimized"]["objective"] < best[0]:
            best = report["optimized"]["objective"], mapping
    mapping = best[1]
    events = engine.expression(onset, group, mapping, p["output_seconds"], p["seed"])
    folder = new_directory(output)
    frame["onset_seconds"] = onset
    frame.to_csv(folder/"prepared_events.csv", index=False, float_format="%.17g")
    np.savez_compressed(folder/"events.npz", **events)
    (folder/"optimized.mid").write_bytes(engine.midi_bytes(events, p["output_seconds"]))
    maps = {"optimized": dict(zip(categories, map(int, mapping)))}
    scores = {"optimized": objective.full(mapping)[0]}
    if random_baseline:
        # Same pitch inventory, times, velocities and category-specific pan.
        # Only the identity-to-pitch bijection is permuted.
        active = np.unique(group)
        random_mapping = mapping.copy()
        random_mapping[active] = np.random.default_rng(p["seed"]+9001).permutation(mapping[active])
        control = {key: value.copy() for key, value in events.items()}
        control["pitch"] = random_mapping[group]
        np.savez_compressed(folder/"random_events.npz", **control)
        (folder/"random.mid").write_bytes(engine.midi_bytes(control, p["output_seconds"]))
        maps["random"] = dict(zip(categories, map(int, random_mapping)))
        scores["random"] = objective.full(random_mapping)[0]
    if context is not None:
        candidates.to_csv(folder/"context_candidates.csv", index=False)
        trials.to_csv(folder/"speed_trials.csv", index=False)
    manifest = dict(format="digitalcreativity-run-1", software_version=__version__,
        python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__,
        source_sha256=digest(source), source_event_count=total,
        prepared_event_count=len(frame), prepared_category_count=k,
        adapter=mark_info, protocol=p, mode=mode, context=context, timing=timing,
        pitch_maps=maps, optimization_runs=runs, objective_scores=scores,
        original_objective_frames=objective.original_frames, distinct_active_sets=len(objective.active),
        baseline="Uniform permutation of the active optimized pitch inventory; inactive assignments, per-event timing, velocity and pan fixed" if random_baseline else None,
        reversibility="Prepared categorical event multiset plus affine clock; not raw discarded events, continuous marks or audio",
        hashes={f.name:digest(f) for f in folder.iterdir() if f.is_file()})
    save_json(folder/"manifest.json", manifest)
    save_json(folder/"verification.json", verify(folder))
    return manifest


def decode_midi(midi_path, manifest, condition="optimized"):
    """Decode note-ons with mido, including tempo and running status handling."""
    inverse = {int(pitch): category for category, pitch in manifest["pitch_maps"][condition].items()}
    if len(inverse) != len(manifest["pitch_maps"][condition]):
        raise ValueError("Pitch map is not injective")
    elapsed = 0.
    rows = []
    speed = manifest["timing"]["speed"]
    origin = manifest["timing"]["source_start_seconds"]
    intro = manifest["protocol"]["intro_seconds"]
    for msg in mido.MidiFile(midi_path):
        elapsed += msg.time
        if msg.type == "note_on" and msg.velocity > 0:
            if msg.note not in inverse:
                raise ValueError("A MIDI pitch is absent from the supplied mapping")
            rows.append(dict(time_seconds=origin+speed*(elapsed-intro), category=inverse[msg.note],
                             onset_seconds=elapsed, pitch=msg.note, velocity=msg.velocity))
    return pd.DataFrame(rows)


def verify(folder):
    folder = Path(folder)
    manifest = json.loads((folder/"manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["hashes"].items():
        if Path(name).name != name or digest(folder/name) != expected:
            raise ValueError(f"Artifact hash mismatch: {name}")
    original = pd.read_csv(folder/"prepared_events.csv", dtype={"category":str}, float_precision="round_trip", keep_default_na=False)
    reports = {}
    for condition in manifest["pitch_maps"]:
        recovered = decode_midi(folder/f"{condition}.mid", manifest, condition)
        original_sort = original.sort_values(["category", "time_seconds"], kind="stable").reset_index(drop=True)
        recovered = recovered.sort_values(["category", "time_seconds"], kind="stable").reset_index(drop=True)
        if len(recovered) != len(original_sort) or not recovered.category.equals(original_sort.category):
            raise ValueError("MIDI changed event multiplicity or categorical identity")
        error = float(np.max(np.abs(original_sort.time_seconds-recovered.time_seconds)))
        theoretical = manifest["timing"]["speed"]/120000
        floating_tolerance = max(1e-9, np.max(abs(original_sort.time_seconds))*1e-12)
        if error > theoretical+floating_tolerance:
            raise ValueError("Source-time round-trip error exceeds half a MIDI tick plus floating tolerance")
        midi = mido.MidiFile(folder/f"{condition}.mid")
        elapsed, pedals = 0., []
        for msg in midi:
            elapsed += msg.time
            if msg.type == "control_change" and msg.control == 64:
                pedals.append((elapsed, msg.channel, msg.value))
        duration = manifest["protocol"]["output_seconds"]
        if any(value != 127 for time, _, value in pedals if time < duration-1e-4):
            raise ValueError("Pedal was released before the ending")
        if not pedals or abs(elapsed-duration) > 1/60000+1e-8:
            raise ValueError("MIDI duration/pedal audit failed")
        if recovered.onset_seconds.max() >= duration-manifest["protocol"]["tail_seconds"]+1/60000:
            raise ValueError("MIDI notes intrude into the ending")
        reports[condition] = dict(events=len(recovered), max_source_time_error_seconds=error,
            theoretical_half_tick_seconds=theoretical, floating_tolerance_seconds=float(floating_tolerance),
            identity_and_multiplicity_preserved=True, pedal_held_to_endpoint=True,
            no_new_notes_in_tail=True, midi_duration_seconds=elapsed)
    return dict(hashes_match=True, conditions=reports)
