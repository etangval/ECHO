"""Descriptive serial-order and synchrony controls, without pooling deployments.

Null intervals describe the stated randomisation, not a causal interaction test.
Inhomogeneous rates, source clock precision and observation support remain
essential to interpretation. No p-value or criticality inference is returned.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy import stats
from .preprocessing import merge_intervals
from .processes import finite, interval_sample
from .pipeline import save_json, new_directory


def serial_statistic(segments):
    pairs = [(d[:-1], d[1:]) for d in segments if len(d) >= 2]
    if not pairs:
        return None
    a = np.concatenate([x[0] for x in pairs]); b = np.concatenate([x[1] for x in pairs])
    if np.ptp(a) == 0 or np.ptp(b) == 0:
        return None
    return float(stats.spearmanr(a, b).statistic)


def interval_shuffle(times, coverage, rng, replicates=199):
    t = np.sort(np.asarray(times, float))
    segments = []
    for lo, hi in merge_intervals(coverage):
        a, b = np.searchsorted(t, [lo, hi]); segments.append(np.diff(t[a:b]))
    observed = serial_statistic(segments)
    if observed is None or sum(len(d) for d in segments) < 30:
        return dict(status='insufficient_intervals_or_variation')
    null = [serial_statistic([rng.permutation(d) for d in segments]) for _ in range(replicates)]
    null = [v for v in null if v is not None]
    return dict(status='within_episode_IEI_permutation', serial_spearman=observed,
                shuffled_median=float(np.median(null)), shuffled_95_interval=np.quantile(null,[.025,.975]).tolist(),
                note='Preserves each episode interval multiset and duration; removes interval order. Rate drift can produce serial order, so this does not isolate intrinsic memory.')


def pair_coactivation(matrix):
    """Fraction of entity pairs jointly active, averaged over bins."""
    a = (np.asarray(matrix) > 0).sum(axis=1)
    k = matrix.shape[1]
    return float(np.mean(a*(a-1)/(k*(k-1)))) if k >= 2 else None


def local_shuffle(matrix, rng, block_bins=64):
    shuffled = matrix.copy()
    for a in range(0, len(matrix), block_bins):
        b = min(a+block_bins, len(matrix))
        for c in range(matrix.shape[1]):
            shuffled[a:b,c] = rng.permutation(matrix[a:b,c])
    return shuffled


def analyze_surrogates(prepared, output, population=True, seed=20260910, replicates=199):
    folder = Path(prepared); output = new_directory(output)
    events = pd.read_parquet(folder/'events.parquet')
    coverage = pd.read_parquet(folder/'observation_intervals.parquet')
    prep = json.loads((folder/'preparation.json').read_text(encoding='utf-8'))
    by_times = {str(k): g.event_time.to_numpy(float) for k,g in events.groupby('entity_id')}
    by_cov = {str(k): merge_intervals(g[['start_seconds','stop_seconds']].to_numpy(float)) for k,g in coverage.groupby('entity_id')}
    eligible = [k for k,t in by_times.items() if k in by_cov and len(interval_sample(t,by_cov[k])[0]) >= 30]
    rng = np.random.default_rng(seed)
    chosen = sorted(rng.choice(eligible, min(24,len(eligible)), replace=False))
    serial = {k: interval_shuffle(by_times[k],by_cov[k],rng,replicates) for k in chosen}
    synch = dict(status='not_applicable_to_asynchronous_deployments')
    if population:
        entities = sorted(rng.choice(eligible,min(70,len(eligible)),replace=False))
        # Require identical continuous support, never infer simultaneous coverage
        # from the absence of events or silently combine unlike deployments.
        supports = [by_cov[k] for k in entities]
        if len(entities) < 2 or any(s != supports[0] for s in supports) or len(supports[0]) != 1:
            synch = dict(status='not_evaluated_without_common_continuous_support')
        else:
            lo, hi = supports[0][0]; scales = []
            for bins in [2048,4096,8192]:
                width = (hi-lo)/bins
                if width < prep['time_precision_seconds']: continue
                edges = np.linspace(lo,hi,bins+1)
                matrix = np.stack([np.histogram(by_times[k],edges)[0] for k in entities],axis=1)
                observed = pair_coactivation(matrix)
                null = [pair_coactivation(local_shuffle(matrix,rng)) for _ in range(replicates)]
                scales.append(dict(bin_seconds=width,block_seconds=64*width,
                    pair_coactivation=observed,shuffled_median=float(np.median(null)),
                    shuffled_95_interval=np.quantile(null,[.025,.975]).tolist()))
            synch = dict(status='descriptive_local_count_shuffle',entities=len(entities),scales=scales,
                note='Independent permutations of entity counts within 64-bin blocks preserve each local count distribution. A scale-dependent comparison, not a causal synchrony test; faster common rate changes remain a confound.')
    report = finite(dict(source=prep['source'],seed=seed,replicates=replicates,
                         selection='Uniform seeded eligible-entity subsets; no selection by outcome',
                         interval_order=serial,synchrony=synch))
    save_json(output/'surrogates.json',report)
    return report
