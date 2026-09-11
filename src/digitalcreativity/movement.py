"""Convert regularly sampled step lengths into explicit movement events."""
import numpy as np
import pandas as pd


def distance_threshold_events(distances, timestamps, entity_ids, threshold=50., step_seconds=6.):
    """One event at the observed endpoint of each cumulative-distance crossing.

    distances[i, j] spans timestamps[j] to timestamps[j+1]. Missing,
    nonfinite or negative distances, and sampling gaps, reset accumulated
    distance without an event. Each event also resets to zero, discarding
    overshoot. At most one event is emitted per observed interval, even if
    that interval spans several threshold lengths. Inputs are never modified.

    This operator is not an inverse of the GPS trajectory: it defines a new
    event process from sampled movement. Distances and thresholds must share
    a unit; timestamps and step_seconds use seconds.
    """
    d = np.asarray(distances, dtype=float)
    t = np.asarray(timestamps, dtype=float)
    ids = [str(x) for x in entity_ids]
    if t.ndim != 1 or len(t) < 2 or not np.isfinite(t).all() or np.any(np.diff(t) <= 0):
        raise ValueError("Timestamps must be a finite, strictly increasing vector")
    if d.ndim != 2 or d.shape != (len(ids), len(t)-1) or len(ids) == 0:
        raise ValueError("Require one distance row per identity and one column per timestamp interval")
    if any(not x.strip() for x in ids) or len(set(ids)) != len(ids):
        raise ValueError("Identity labels must be nonempty and distinct")
    if not np.isfinite(threshold) or threshold <= 0 or not np.isfinite(step_seconds) or step_seconds <= 0:
        raise ValueError("Threshold and expected sampling interval must be positive and finite")
    valid = np.isfinite(d) & (d >= 0) & (np.diff(t) == step_seconds)[None, :]
    records = []
    for i, label in enumerate(ids):
        accumulated = 0.
        start = -1
        for j in range(d.shape[1]):
            if not valid[i, j]:
                accumulated, start = 0., -1
                continue
            if start < 0:
                start = j
            accumulated += d[i, j]
            if accumulated >= threshold:
                records.append((t[j+1], label, j+2, t[j], accumulated, j-start+1))
                accumulated, start = 0., -1
    frame = pd.DataFrame(records, columns=["time_seconds", "category", "timestamp_row_1based",
        "time_lower_seconds", "distance_since_event_or_reset", "valid_steps_since_event_or_reset"])
    frame = frame.sort_values(["time_seconds", "category"], kind="stable").reset_index(drop=True)
    frame.insert(0, "event_id", np.arange(1, len(frame)+1))
    metadata = dict(method="cumulative_distance_threshold", threshold=float(threshold),
        expected_step_seconds=float(step_seconds), interval_test="Exact equality of timestamp differences",
        input_identities=ids, valid_steps_per_identity=valid.sum(axis=1).tolist(),
        events=len(frame), missing_or_gap_policy="Reset without an event; never stitch gaps",
        event_policy="First observed endpoint reaching the threshold; reset to zero; discard overshoot",
        timing="Sample endpoint, with the last step's start retained as a lower bound",
        reconstruction="Selected movement events can be encoded reversibly; the original trajectory cannot")
    return frame, metadata


def interpolate_distance_crossings(events, distances, timestamps, entity_ids, threshold=50., step_seconds=6.):
    """Estimate the within-step times of already defined distance events.

    Event membership and the endpoint-reset detector are unchanged. For a
    crossing step of length d with total accumulated distance A, the crossing
    fraction is 1-(A-threshold)/d. This assumes constant speed within the step.
    Observed endpoints are retained; interpolated times are model estimates,
    not additional GPS observations. No random jitter or gap interpolation.
    """
    d = np.asarray(distances, dtype=float)
    t = np.asarray(timestamps, dtype=float)
    ids = [str(x) for x in entity_ids]
    if t.ndim != 1 or len(t) < 2 or not np.isfinite(t).all() or np.any(np.diff(t) <= 0):
        raise ValueError("Require finite increasing timestamps")
    if d.ndim != 2 or d.shape != (len(ids), len(t)-1) or len(set(ids)) != len(ids):
        raise ValueError("Distance matrix and unique identities must match timestamps")
    if not np.isfinite(threshold) or threshold <= 0 or not np.isfinite(step_seconds) or step_seconds <= 0:
        raise ValueError("Require positive finite threshold and step")
    required = {'category', 'timestamp_row_1based', 'time_seconds', 'distance_since_event_or_reset'}
    if not required.issubset(events.columns):
        raise ValueError("Require the unmodified endpoint-event table")
    rows = pd.Categorical(events.category, categories=ids).codes
    index = events.timestamp_row_1based.to_numpy(float)
    if np.any(rows < 0) or not np.isfinite(index).all() or np.any(index != np.floor(index)):
        raise ValueError("Unknown identity or noninteger timestamp row")
    cols = index.astype(int)-2
    if np.any(cols < 0) or np.any(cols >= d.shape[1]):
        raise ValueError("Timestamp interval outside input matrix")
    if np.any(np.diff(t)[cols] != step_seconds) or np.any(events.time_seconds.to_numpy() != t[cols+1]):
        raise ValueError("Event endpoint disagrees with an observed valid interval")
    length = d[rows, cols]
    if not np.isfinite(length).all() or np.any(length <= 0):
        raise ValueError("Crossing requires a finite positive step length")
    fraction = 1-(events.distance_since_event_or_reset.to_numpy(float)-threshold)/length
    if not np.isfinite(fraction).all() or np.any(fraction <= 0) or np.any(fraction > 1+1e-12):
        raise ValueError("Distance threshold does not cross in the stated step")
    fraction = np.minimum(fraction, 1.)
    result = events.copy()
    result['observed_endpoint_seconds'] = events.time_seconds
    result['time_lower_seconds'] = t[cols]
    result['crossing_fraction'] = fraction
    result['time_seconds'] = t[cols]+step_seconds*fraction
    return result.sort_values(['time_seconds', 'category'], kind='stable').reset_index(drop=True)
