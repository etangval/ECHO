import itertools
import json
import numpy as np
import pandas as pd
import pytest
from digitalcreativity import adapters, engine, pipeline, temporal


def test_higher_order_transposition_and_extended_chords():
    # Test all 4096 pitch-class sets at all 12 transpositions.
    for shift in range(12):
        masks = np.arange(4096)
        rotated = ((masks << shift) | (masks >> (12-shift))) & 4095
        np.testing.assert_allclose(engine.H[masks], engine.H[rotated], atol=1e-14)
    c7 = sum(1 << p for p in [0, 4, 7, 10])
    dm6 = sum(1 << p for p in [2, 5, 9, 11])
    assert engine.H[c7] <= .02+1e-14
    assert engine.H[dm6] <= .02+1e-14
    assert engine.H[0] == engine.H[1] == 0
    assert np.isfinite(engine.H).all() and (engine.H >= 0).all()


def test_exact_aggregation_and_incremental_annealing():
    rng = np.random.default_rng(11)
    onset = np.sort(rng.uniform(1, 40, 180))
    group = rng.integers(0, 8, len(onset))
    full = engine.Objective(onset, group, 8, 52, aggregate=False)
    compact = engine.Objective(onset, group, 8, 52, aggregate=True)
    for _ in range(3):
        pitch = rng.choice(engine.KEYS, 8, replace=False)
        for key in ["objective", "chord_set_cost", "roughness_proxy", "melody_leap_cost", "register_cost"]:
            assert abs(full.full(pitch)[0][key]-compact.full(pitch)[0][key]) < 1e-11
    chosen, report = compact.optimize(12, 300)
    again, _ = compact.optimize(12, 300)
    assert len(set(chosen)) == 8
    assert report["optimized"]["objective"] <= report["initial"]["objective"]+1e-12
    np.testing.assert_array_equal(chosen, again)
    assert compact.full(chosen)[0]["objective"] == report["optimized"]["objective"]


def test_ordered_dp_against_exhaustive_partition():
    values = np.repeat(np.arange(6), [2, 7, 1, 9, 3, 1])
    labels, info = adapters.ordered_groups(values, 3)
    candidates = []
    for cuts in itertools.combinations(range(1, 6), 2):
        alternate = np.searchsorted(cuts, values, side="right")
        candidates.append(float(np.sum((np.bincount(alternate)-len(values)/3)**2)))
    assert info["counts_sse"] == min(candidates)
    for value in np.unique(values):
        assert len(set(labels[values == value])) == 1
    assert np.all(np.diff(labels) >= 0)


def test_geographic_wrap_and_antipodal_degeneracy():
    frame = pd.DataFrame(dict(latitude_deg=[0, 0, 0, 0], longitude_deg=[179, -179, 10, 12]))
    labels, info = adapters.geographic_groups(frame, 2)
    assert labels[0] == labels[1] and labels[2] == labels[3] and labels[0] != labels[2]
    opposite = pd.DataFrame(dict(latitude_deg=[0, 0], longitude_deg=[0, 180]))
    one, _ = adapters.geographic_groups(opposite, 1)
    assert list(one) == [0, 0]
    with pytest.raises(ValueError):
        adapters.geographic_groups(frame, 5)


def test_long_duration_resonance_without_overflow():
    p = pipeline.protocol(3600)
    onset = np.arange(.1, p["active_seconds"], .6)
    metrics = temporal.load_metrics(onset, p)
    assert np.isfinite(metrics["resonance_load_q95"])
    assert metrics["resonance_load_max"] < 4


def make_csv(tmp_path, times, categories):
    path = tmp_path/"input.csv"
    pd.DataFrame(dict(time_seconds=times, category=categories)).to_csv(path, index=False, float_format="%.17g")
    return path


def test_symbolic_roundtrip_coincidences_and_random_control(tmp_path):
    # Unsorted, negative source origin, coincident repeated identity, literal NA.
    source = make_csv(tmp_path, [-1., -5., -5., -4.123456789, -2., -1.], ["001", "NA", "NA", "001", "z", "z"])
    p = pipeline.protocol(20, steps=60)
    folder = tmp_path/"run"
    manifest = pipeline.sonify(source, folder, p, mode="all", speed=.5, random_baseline=True)
    result = pipeline.verify(folder)
    assert manifest["prepared_event_count"] == 6
    assert result["conditions"]["optimized"]["identity_and_multiplicity_preserved"]
    assert set(manifest["pitch_maps"]["optimized"]) == {"001", "NA", "z"}
    with np.load(folder/"events.npz") as a, np.load(folder/"random_events.npz") as b:
        for field in ["onset_seconds", "velocity", "pan_cc10", "channel"]:
            np.testing.assert_array_equal(a[field], b[field])
    decoded = pipeline.decode_midi(folder/"optimized.mid", manifest)
    assert len(decoded) == 6
    with pytest.raises(ValueError, match="not empty"):
        pipeline.new_directory(folder)
    # Tampering must be detected without trusting the stored verification file.
    (folder/"optimized.mid").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="hash mismatch"):
        pipeline.verify(folder)


def test_single_category_short_expression_and_midi(tmp_path):
    source = make_csv(tmp_path, [0., .1, .2], ["a"]*3)
    folder = tmp_path/"single"
    manifest = pipeline.sonify(source, folder, pipeline.protocol(12, voices=1, steps=30), mode="all")
    assert manifest["prepared_category_count"] == 1
    assert pipeline.verify(folder)["conditions"]["optimized"]["events"] == 3


def test_auto_speed_is_fastest_feasible_and_coverage_is_required(tmp_path):
    rng = np.random.default_rng(4)
    t = np.sort(rng.uniform(0, 300, 700))
    source = make_csv(tmp_path, t, [str(i % 5) for i in range(len(t))])
    p = pipeline.protocol(120, voices=5, steps=30)
    with pytest.raises(ValueError, match="requires --intervals"):
        pipeline.sonify(source, tmp_path/"missing", p)
    intervals = tmp_path/"coverage.csv"
    pd.DataFrame(dict(start_seconds=[0.], stop_seconds=[300.])).to_csv(intervals, index=False)
    manifest = pipeline.sonify(source, tmp_path/"auto", p, intervals=intervals)
    assert manifest["timing"]["fastest_feasible_preferred_factor_verified"]
    assert manifest["timing"]["mean_attacks_per_second"] <= 3
    trials = pd.read_csv(tmp_path/"auto/speed_trials.csv")
    assert not trials.feasible.iloc[:-1].any()
    assert trials.feasible.iloc[-1]
    assert manifest["protocol"]["tail_seconds"] == 10


@pytest.mark.parametrize("times,categories", [([float("nan")], ["a"]), ([0], [""])])
def test_invalid_events_fail_before_output(tmp_path, times, categories):
    source = make_csv(tmp_path, times, categories)
    with pytest.raises(ValueError):
        pipeline.sonify(source, tmp_path/"bad", pipeline.protocol(20), mode="all")
    assert not (tmp_path/"bad").exists()


def test_nicer_import_uses_gti_clock_and_filter(tmp_path):
    fits = pytest.importorskip("astropy.io.fits")
    event = fits.BinTableHDU.from_columns([
        fits.Column(name="TIME", format="D", array=[0., 1., 2., 3., 4.]),
        fits.Column(name="PI", format="I", array=[100, 100, 100, 2000, 100])], name="EVENTS")
    event.header["TIMEZERO"] = 100.
    gti = fits.BinTableHDU.from_columns([
        fits.Column(name="START", format="D", array=[101.]),
        fits.Column(name="STOP", format="D", array=[104.])], name="GTI")
    path = tmp_path/"artificial.evt"
    fits.HDUList([fits.PrimaryHDU(), event, gti]).writeto(path)
    frame, intervals, info = adapters.import_nicer(path)
    assert frame.event_id.tolist() == [2, 3]
    assert frame.time_seconds.tolist() == [0., 1.]
    assert intervals.stop_seconds.tolist() == [3.]
    assert info["original_events"] == 5
