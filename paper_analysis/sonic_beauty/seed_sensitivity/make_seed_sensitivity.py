"""Reproduce the exploratory seed-sensitivity analysis and Figure S3."""
from pathlib import Path
import itertools
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parent
RUNS = pd.read_csv(ROOT / "seed_sensitivity_runs.csv")
LONG = pd.read_csv(ROOT / "declared_seeds_56000.csv")
MAPS = pd.read_csv(ROOT / "pitch_maps.csv", index_col="seed")
DECLARED = {1701, 1723, 1741}


def transposition_agreement(a, b):
    return max(np.mean(a % 12 == (b + shift) % 12) for shift in range(12))


values = RUNS.objective.to_numpy()
pairwise = np.eye(len(MAPS))
pair_records = []
for i, j in itertools.combinations(range(len(MAPS)), 2):
    a, b = MAPS.iloc[i].to_numpy(), MAPS.iloc[j].to_numpy()
    exact = float(np.mean(a == b))
    pitch_class = float(np.mean(a % 12 == b % 12))
    shifted = float(transposition_agreement(a, b))
    rho = float(spearmanr(a, b).statistic)
    pairwise[i, j] = pairwise[j, i] = shifted
    pair_records.append((exact, pitch_class, shifted, rho))

pairs = np.asarray(pair_records)
summary = {
    "data": {"events": 579, "categories": 12, "seeded_runs": 24},
    "search": {"proposals_per_run": 14000, "extended_proposals": 56000},
    "objective": {
        "minimum": float(values.min()), "median": float(np.median(values)),
        "maximum": float(values.max()), "sd": float(values.std(ddof=1)),
        "cv_percent": float(100 * values.std(ddof=1) / values.mean()),
        "median_excess_over_minimum_percent": float(100 * (np.median(values) / values.min() - 1)),
        "maximum_excess_over_minimum_percent": float(100 * (values.max() / values.min() - 1)),
    },
    "pairwise_mapping": {
        "median_exact_pitch_fraction": float(np.median(pairs[:, 0])),
        "median_pitch_class_fraction": float(np.median(pairs[:, 1])),
        "median_best_transposition_pitch_class_fraction": float(np.median(pairs[:, 2])),
        "median_pitch_rank_spearman": float(np.median(pairs[:, 3])),
    },
    "declared_seeds": {
        "best_14000": float(RUNS[RUNS.seed.isin(DECLARED)].objective.min()),
        "best_56000": float(LONG.objective.min()),
    },
}
(ROOT / "seed_sensitivity_summary.json").write_text(json.dumps(summary, indent=2) + "\n")

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.titlesize": 10})
fig = plt.figure(figsize=(10.4, 7.0), constrained_layout=True)
gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.05])

ax = fig.add_subplot(gs[0, 0])
x = np.arange(1, len(RUNS) + 1)
colors = ["#d96b32" if int(s) in DECLARED else "#16738a" for s in RUNS.seed]
ax.scatter(x, values, c=colors, s=34, zorder=3)
ax.axhline(np.median(values), color="#606a70", lw=1, ls="--", label="Median")
ax.set(xlabel="Seeded search", ylabel="Optimized objective  J", title="A  Objective values across 24 seeds")
ax.set_xticks([1, 6, 12, 18, 24]); ax.grid(axis="y", color="#dfe4e6", lw=.7)
ax.legend(frameon=False, loc="upper right")

ax = fig.add_subplot(gs[0, 1])
im = ax.imshow(pairwise, vmin=0, vmax=1, cmap="Blues", interpolation="nearest")
ax.set(title="B  Pitch-class agreement after best transposition", xlabel="Seeded search", ylabel="Seeded search")
ticks = [0, 5, 11, 17, 23]; labels = [1, 6, 12, 18, 24]
ax.set_xticks(ticks, labels); ax.set_yticks(ticks, labels)
cb = fig.colorbar(im, ax=ax, fraction=.046, pad=.04); cb.set_label("Fraction of categories")

ax = fig.add_subplot(gs[1, :])
base = RUNS[RUNS.seed.isin(DECLARED)].set_index("seed")
extended = LONG.set_index("seed")
for seed, color in zip(sorted(DECLARED), ["#16738a", "#5a8f3d", "#d96b32"]):
    ys = [base.loc[seed, "objective"], extended.loc[seed, "objective"]]
    ax.plot([14000, 56000], ys, marker="o", lw=1.8, color=color, label=f"Seed {seed}")
ax.set(xlabel="Proposals per search", ylabel="Optimized objective  J", title="C  Longer searches for the three prespecified seeds")
ax.set_xticks([14000, 56000], ["14,000", "56,000"]); ax.grid(axis="y", color="#dfe4e6", lw=.7)
ax.legend(frameon=False, ncol=3, loc="upper right")

fig.suptitle("Seed sensitivity of ECHO pitch optimization", fontsize=13, fontweight="bold")
for ext in ("png", "pdf", "svg"):
    fig.savefig(ROOT / f"Figure_S3_seed_sensitivity.{ext}", dpi=300, bbox_inches="tight")
