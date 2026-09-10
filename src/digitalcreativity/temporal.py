"""Domain-neutral representative contexts and audibility-constrained speed."""
import math
import numpy as np
import pandas as pd

def entropy(probability):
    positive = probability[probability > 0]
    return float(-np.sum(positive*np.log(positive)))


def representative_context(t, group, k, intervals, P):
    exposure = sum(b-a for _, a, b in intervals)
    rate = len(t)/exposure
    width = min(P["context_expected_events"]/rate, max(b-a for _,a,b in intervals))
    global_p = np.bincount(group, minlength=k)/len(group)
    rows = []
    feature_names = P["representative_features"]
    for interval_id, lo, hi in intervals:
        if hi-lo < width:
            continue
        starts = np.arange(lo, hi-width+1e-10*width, width*P["context_stride_fraction"])
        for a in starts:
            b = min(a+width, hi)
            first, stop = np.searchsorted(t, [a, b], side="left")
            n = int(stop-first)
            if n < P["context_minimum_events"]:
                continue
            tt = t[first:stop]
            gap = np.diff(tt)
            cv = float(np.std(gap)/max(np.mean(gap), np.finfo(float).eps))
            counts = np.histogram(tt, bins=np.linspace(a, b, 17))[0]
            fano = float(np.var(counts)/np.mean(counts))
            marks = np.bincount(group[first:stop], minlength=k)/n
            mixture = .5*(marks+global_p)
            js = entropy(mixture)-.5*(entropy(marks)+entropy(global_p))
            f = [math.log((n/(b-a))/rate), math.log1p(cv), math.log1p(fano), (entropy(marks)/math.log(k) if k > 1 else 0.), js]
            rows.append({"candidate_id": len(rows)+1, "interval_id": interval_id,
                "start_seconds": float(a), "stop_seconds": float(b), "events": n,
                "row_start": int(first), "row_stop_exclusive": int(stop),
                **dict(zip(feature_names, f))})
    if not rows:
        raise ValueError("No complete context of the specified information scale fits in valid coverage; change the declared context parameter, not the chosen example silently.")
    table = pd.DataFrame(rows)
    features = table[feature_names]
    rank = (features.rank(method="average").to_numpy()-.5)/len(table)
    # A medoid is an observed candidate; the distance includes rate, burst and marks.
    cost = np.empty(len(rank))
    for first in range(0, len(rank), 128):
        distance = np.sqrt(np.sum((rank[first:first+128, None, :]-rank[None, :, :])**2, axis=2))
        cost[first:first+128] = distance.mean(axis=1)
    chosen = int(np.argmin(cost))
    table["medoid_cost"] = cost
    table["rate_midrank_fraction"] = rank[:, 0]
    table["selected"] = np.arange(len(table)) == chosen
    row = table.iloc[chosen]
    first, stop = int(row.row_start), int(row.row_stop_exclusive)
    anchor_index = first+(stop-first-1)//2
    context = {key: (value.item() if isinstance(value, np.generic) else value) for key, value in row.to_dict().items()}
    context.update({"anchor_row": anchor_index, "anchor_seconds": float(t[anchor_index]),
        "global_retained_rate_per_second": rate, "coverage_seconds": exposure,
        "native_context_seconds": width, "candidate_count": len(table),
        "all_features": feature_names,
        "representativeness_scope": "Centrality within the chosen five descriptors of this available record; not a guarantee of scientific or aesthetic representativeness."})
    return context, table


def preferred_factors(P):
    # The displayed compression or slowdown multiplier itself has <=2 sig figs.
    values = {}
    digits = P["speed_significant_digits"]
    assert digits in [1, 2]
    for exponent in range(1-digits, 10):
        for mantissa in range(10**(digits-1), 10**digits):
            multiplier = mantissa*10.**exponent
            if multiplier < 1:
                continue
            if multiplier == 1:
                values[1.] = {"speed": 1., "kind": "unchanged", "factor": 1., "display": "1"}
            else:
                values[multiplier] = {"speed": multiplier, "kind": "compression", "factor": multiplier, "display": f"{multiplier:g}"}
                values[1/multiplier] = {"speed": 1/multiplier, "kind": "slowdown", "factor": multiplier, "display": f"1/{multiplier:g}"}
    return sorted(values.values(), key=lambda x: -x["speed"])


def load_metrics(onset, P):
    """Same exponential load as v1.0, without overflow on hour-long arrays."""
    tau = P["resonance_decay_seconds"]
    grid = np.arange(0, P["active_seconds"], P["load_grid_seconds"])
    right = np.searchsorted(onset, grid, side="right")
    left = np.searchsorted(onset, grid-P["attack_window_seconds"], side="right")
    state = np.zeros(len(onset)+1)
    previous = 0.
    for i, t in enumerate(onset):
        state[i+1] = state[i] * math.exp(-(t-previous)/tau) + 1
        previous = t
    last = np.r_[0., onset][right]
    resonance = state[right] * np.exp(-(grid-last)/tau)
    sample = np.linspace(0, len(grid)-1, 19).astype(int)
    direct = np.array([np.exp(-(grid[j]-onset[onset <= grid[j]])/tau).sum() for j in sample])
    assert np.allclose(resonance[sample], direct, rtol=1e-11, atol=1e-11)
    assert np.isfinite(resonance).all()
    counts = right-left
    q = P["load_quantile"]
    return dict(events=len(onset), mean_attacks_per_second=len(onset)/P["active_seconds"],
                resonance_load_q95=float(np.quantile(resonance, q)),
                attack_window_count_q95=float(np.quantile(counts, q)),
                resonance_load_max=float(resonance.max()),
                attack_window_count_max=int(counts.max()),
                maximum_is_not_the_constrained_quantity=True)


def choose_speed(t, context, P):
    duration = P["active_seconds"]
    anchor = context["anchor_seconds"]
    margin = min(anchor-context["start_seconds"], context["stop_seconds"]-anchor)
    max_speed_coverage = 2*margin/duration
    trials = []
    for factor in preferred_factors(P):
        speed = factor["speed"]
        if speed > max_speed_coverage*(1+1e-12):
            continue
        left = anchor-duration*speed/2
        right = anchor+duration*speed/2
        a, b = np.searchsorted(t, [left, right], side="left")
        n = int(b-a)
        mean = n/duration
        trial = {**factor, "events": n, "mean_attacks_per_second": mean}
        if mean > P["maximum_mean_attacks_per_second"]:
            trial.update({"feasible": False, "reason": "mean_density"})
            trials.append(trial)
            continue
        relative = (t[a:b]-left)/speed
        metrics = load_metrics(relative, P)
        feasible = n > 0 and metrics["resonance_load_q95"] <= P["maximum_resonance_load_quantile"] and metrics["attack_window_count_q95"] <= P["maximum_attack_window_count_quantile"]
        trial.update(metrics)
        trial.update({"feasible": bool(feasible), "reason": "satisfies_profile" if feasible else "temporal_load"})
        trials.append(trial)
        if feasible and n > 0:
            assert all(not x["feasible"] for x in trials[:-1])
            assert context["start_seconds"] <= left < right <= context["stop_seconds"]
            result = {**factor, **metrics, "source_start_seconds": float(left), "source_stop_seconds": float(right),
                "source_span_seconds": float(duration*speed), "row_start": int(a), "row_stop_exclusive": int(b),
                "source_anchor_seconds": anchor, "maximum_speed_from_context_coverage": max_speed_coverage,
                "preferred_factors_evaluated": len(trials), "fastest_feasible_preferred_factor_verified": True}
            return result, relative+P["intro_seconds"], pd.DataFrame(trials)
    raise ValueError("No preferred factor satisfies the declared auditory profile.")
