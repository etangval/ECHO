# ECHO: manuscript analysis supplement

This directory contains the code and numerical inputs used for the keyboard
comparisons, aggregate listening tests, and final figures in **Designing for Sonic
Beauty: Event-Preserving Sonification through Harmonic Optimisation**.

It is an addition to `etangval/digitalcreativity`, prepared against reference
commit `27f4f10b9e0d485afcc6e8bb09c6afc0999e0219`. It does not replace the
existing sonification engine. ECHO stands for **Event-Conserving Harmonic Optimisation**.

## Location

This supplement is located at `paper_analysis/sonic_beauty/` in the repository.
All paths in the supported reproduction workflow are relative to the code files;
the original workspace is not required. No network connection is needed to run
the analysis once the dependencies have been installed.

## Reproduce

Python 3.12 was used. In this directory, run:

```bash
python -m pip install -r requirements.txt
python run_all.py
```

The full run checks the mathematics, recomputes all 25 selection coordinates
and their 99 seeded pitch-shuffle controls, checks the plot inputs against the
analysis, recomputes the listening tests, and generates Figures 1–5 and S1.
The shuffle calculation can take several minutes. For a faster check that reuses
the saved shuffle results, run `python run_all.py --quick`.

Figures are written to `figures/` as 300-dpi PNG, vector PDF and SVG. Statistics
are written to CSV and JSON alongside them. Logs and the validation report are
written to `validation/`. Re-running overwrites these generated outputs; it does
not contact or edit Google Docs or GitHub.

## Contents

| Location | Purpose |
| --- | --- |
| `keyboard/code/core_metrics.py` | Chord-set cost, six-partial roughness, exact time integration and optimal pitch-distribution transport |
| `keyboard/code/analyze.py` | Release sensitivity and multiscale continuity calculations; imported by `reproduce.py` |
| `keyboard/code/reproduce.py` | Recompute the reported coordinates and optional shuffle controls from the supplied note events |
| `keyboard/code/verify_mathematics.py` | Check Möbius reconstruction, transposition invariance and transport against linear programming |
| `keyboard/analysis_notes_25.csv` | Actual numerical input: 4,379 note events in 36 opening excerpts |
| `keyboard/excerpt_manifest_25.csv` | Excerpt boundaries and correspondence to the 25 selections |
| `keyboard/analysis_parameters.json` | Parameters used in the reported calculations; documentary, not a runtime configuration file |
| `keyboard/comparison_25.csv` | Reference coordinates, sensitivity ranges and control summaries |
| `keyboard/permutation_controls_25.csv` | Reference values for the 99 seeded controls per selection |
| `keyboard/selection_register_25.csv` | Selection register, covering all 25 works |
| `keyboard/source_manifest.json` | Sources, available source hashes and recorded rights notices |
| `figures/make_figures.py` | Aggregate listening tests and the six final figures |
| `figures/listening_aggregate_counts.csv` | Optimized/equal/random counts used by the script |
| `figures/listening_aggregate_statistics.csv` | Conditional effect estimates, exact intervals and corrected p values |
| `figures/figure_captions.txt` | Final manuscript captions |
| `workflow_archive/` | Original workspace-dependent extraction and unverified OMR scripts; not called by `run_all.py` |

`analyze.py` is used as a calculation module here. Its historical standalone
command expects earlier workspace files; use `reproduce.py` or `run_all.py`
for this package. The figure script retains the manuscript counts explicitly
in its `counts` dictionary and exports them to CSV on each run. To analyse new
counts, update that dictionary; editing the exported CSV alone does not change
the tests. Other model constants remain explicit in the Python source.

## Statistical and musical scope

The listener analysis uses the manuscript's aggregate counts from 453 completed
responses: 153 neural-spike, 153 earthquake and 147 X-ray responses. Each response
provided three outcomes. Two-sided exact sign tests condition on non-neutral
responses. Holm correction is applied separately to three pooled tests and nine
source–outcome tests. Confidence intervals are pointwise 95% Clopper–Pearson
intervals, not simultaneous intervals. Ties remain visible in the figures.
The full seven-category participant records, ordinal-score analyses, covariate
adjustments and participant-level bootstrap are not reconstructed here.

The keyboard comparison uses opening excerpts. Each includes any pickup and at least eight complete bars. Webern movement I uses 14 bars (10.5 quarter notes), the minimum complete-bar extension needed to support all four temporal scales at both phases. Casella, Szymanowski and Webern use equal means of two, nine and three constituents. The comparison contains 25 selections, 36 excerpts and 4,379 noteheads.

Berg's corrected opening input is in `keyboard/extensions/berg_opening.json`.
Webern uses a pinned public Humdrum encoding of all three movements; its source
hashes and complete-movement descriptors are in `keyboard/extensions/`.
`keyboard/code/extend_repertoire.py` rebuilds the 25-selection references from
the original 23 and the two additions. `keyboard/code/extract_webern.py` optionally
fetches and re-extracts Webern's source files (requires `music21==10.5.0`). Complete
source encodings are not redistributed here. The archived Berg full-score OMR
candidate remains outside the comparison; it has not been corrected throughout.
The original 23-selection reference files are retained for version comparison.

X describes chord-template affinity with a roughness penalty. Y describes
multiscale pitch-distribution continuity and does not track individual voices.
Neither is a calibrated rating of perceived beauty or artistic value. The
shuffle contrasts and parameter ranges are computational controls, not listener
confidence intervals or tests establishing a hierarchy of musical periods.

## Attribution and rights

The retained upstream MIT notice is in `LICENSE-digitalcreativity.txt`, also
beside `core_metrics.py`. Third-party score material and derived note records
retain their source-specific rights; they are not relicensed under the software
license. Preserve `keyboard/source_manifest.json` with the data. It records
public-domain declarations, CC BY, CC BY-SA and CC BY-NC-SA sources, and source
provenance where a blanket redistribution license was not established. No raw
score PDFs, piano samples, participant-level records or executable OMR software
are included. The source manifest is a record of the material used, not a legal
clearance for every jurisdiction or subsequent use.

`checksums_sha256.json` identifies the packaged files at delivery. Generated files
can change when rerun, including rendering metadata. Numerical reproduction is
checked against the supplied reference tables rather than file byte identity.
