"""Reproduce the paper analysis from the bundled inputs, without network access.

Run: python run_all.py          (includes all 99 shuffles per excerpt)
     python run_all.py --quick  (skips recomputation of shuffle controls)
"""
from pathlib import Path
import argparse
import importlib.metadata
import json
import platform
import subprocess
import sys
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent


def run_step(name, script, *args):
    print(f"Running {name}...", flush=True)
    start = time.monotonic()
    result = subprocess.run(
        [sys.executable, str(script), *args], cwd=ROOT,
        capture_output=True, text=True, check=False,
    )
    (ROOT / "validation" / f"{name}.log").write_text(
        result.stdout + result.stderr, encoding="utf-8"
    )
    if result.returncode:
        raise RuntimeError(f"{name} failed; see validation/{name}.log")
    print(f"  passed ({time.monotonic() - start:.1f} s)", flush=True)
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()
    (ROOT / "validation").mkdir(exist_ok=True)

    # The plot input is a copy of the keyboard comparison, with labels added.
    # Fail if a figure was paired with different descriptor results.
    source = pd.read_csv(ROOT / "keyboard/comparison_25.csv")
    plotted = pd.read_csv(ROOT / "figures/keyboard_figure_data.csv")
    if source.id.tolist() != plotted.id.tolist():
        raise ValueError("Keyboard selection order differs between analysis and figures")
    numeric = source.select_dtypes(include="number").columns
    if not np.allclose(source[numeric], plotted[numeric], rtol=0, atol=1e-10,
                       equal_nan=True):
        raise ValueError("Keyboard figure inputs differ from analysis reference values")

    math_report = json.loads(run_step(
        "mathematics", ROOT / "keyboard/code/verify_mathematics.py"
    ))
    controls = [] if args.quick else ["--controls"]
    keyboard_report = json.loads(run_step(
        "keyboard", ROOT / "keyboard/code/reproduce.py", *controls
    ))
    # Preserve the supplied reference counts before the figure script rewrites its outputs.
    counts = pd.read_csv(ROOT / "figures/listening_aggregate_counts.csv")
    run_step("figures_and_statistics", ROOT / "figures/make_figures.py")

    # Compare the supplied counts to the values actually used by the calculation.
    stats = pd.read_csv(ROOT / "figures/listening_aggregate_statistics.csv")
    pd.testing.assert_frame_equal(
        counts.reset_index(drop=True), stats[counts.columns].reset_index(drop=True)
    )
    report = {
        "status": "passed",
        "mode": "quick" if args.quick else "full",
        "python": platform.python_version(),
        "packages": {name: importlib.metadata.version(name) for name in
                     ["numpy", "pandas", "scipy", "matplotlib"]},
        "mathematics": math_report,
        "keyboard": keyboard_report,
        "shuffle_controls_recomputed": not args.quick,
        "figure_input_matches_keyboard_reference": True,
        "figures": [1, 2, 3, 4, 5, "S1"],
        "listening_tests": len(stats),
        "listening_source": "Manuscript aggregate counts, not participant-level records",
        "scope": "Reproduction of calculations; not validation of perceived beauty or OMR",
    }
    (ROOT / "validation/reproduction_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
