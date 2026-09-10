# Sonic Beauty: figure and aggregate-statistics package

Prepared 10 September 2026 for the Google manuscript whose body title is
“Designing for Sonic Beauty: Event-Preserving Sonification through Harmonic Optimisation”.
The original Google manuscript is the edited primary document; this package contains
figure assets, captions, and reproducible aggregate analyses, not a replacement manuscript.

## Figure plan

- Figure 1: event-preserving design and the higher-order harmonic objective.
  The event display is explicitly synthetic, not an experimental stimulus.
- Figure 2: pooled listener choices, effect estimates, exact intervals, and tests.
- Figure 3: source-specific listener choices and tests, retaining the inconclusive result.
- Figure 4: two descriptive coordinates for 25 keyboard selections.
- Figure 5: original-minus-shuffled-pitch contrasts for the same selections.
- Figure S1: sensitivity to release extension and temporal scale.

The native manuscript places these figures, captions, the original production metadata
(Table 1), and the 25-selection register (Table 2) at its end. Survey counts are shown
as figures rather than a duplicate table. All figure text is English. PNG files are
300 dpi; PDF and SVG files retain vector elements. Captions are supplied separately.

## Statistical provenance and interpretation

`listening_aggregate_counts.csv` transcribes the optimized / equal / random counts
reported in the current manuscript, Section 3.3. There are 453 completed responses:
153 neural-spike, 153 earthquake, and 147 X-ray responses. The three outcomes are
from the same respondents and must not be treated as independent samples.

`make_figures.py` computes a two-sided exact sign test (binomial null probability
0.5) conditional on non-neutral responses. Neutral responses remain visible in
Figure 2 and the source-specific counts, but are excluded from the conditional test.
Holm correction is applied separately to the three pooled tests and the nine
source–outcome tests. Displayed 95% intervals are pointwise Clopper–Pearson exact
binomial intervals; they are not simultaneous intervals. The exact p values and
intervals are checked against independent binomial-CDF and beta-quantile formulae.

Pooled optimized/equal/random counts:
beauty 288/77/88; pleasantness 318/49/86; personal preference 264/88/101.
All three pooled conditional tests favour the optimized condition after correction.
X-ray personal preference has Holm-adjusted p = 0.05943073; it is inconclusive
at the conventional 0.05 threshold. Differences between separately reported p values
do not test differences between outcomes or sources.

These are aggregate-only recomputations. Participant-level records and seven-category
ratings were not supplied to this analysis. The existing manuscript's ordinal,
bootstrap, covariate-adjusted and attention/placement sensitivity analyses were
preserved as source-reported, not independently recomputed. Distinct individuals
across devices are not verified. Inference is restricted to responses to three fixed
source excerpts, not a sampled population of independent musical works.

## Keyboard data and scope

`keyboard_figure_data.csv` contains the precomputed coordinates and shuffle-control
summaries used in this repository edition. The plotting script reuses these values; it does
not perform score transcription or recompute descriptors from scores. The eligible
material consists of 36 opening excerpts and 4,379 noteheads, summarized as 25 selections. Excerpts include any pickup and at least eight complete bars. Webern I extends to bar 14 so that the same four-scale continuity descriptor is defined. Casella, Szymanowski and Webern are equal means of two, nine and three constituents. The underlying note events, exact boundaries and source records are in `../keyboard/`.


X is a chord-template affinity descriptor with a roughness penalty. Y is a multiscale
pitch-distribution continuity descriptor; it does not identify individual voices.
Neither axis is calibrated to human beauty ratings, nor does it rank artistic value.
The shuffle contrasts and parameter ranges are descriptive controls, not listener
confidence intervals or tests of a historical hierarchy of musical beauty. Each
excerpt has 99 seeded pitch permutations. These hold onsets and durations fixed
and preserve the notehead pitch histogram, but not pitch-duration associations.

## Reproduction

With Python and the packages in `requirements.txt` installed, run:

    python make_figures.py

Run from any working directory. The script uses the included keyboard CSV and
writes figures/statistics alongside itself. It reproduces the aggregate tests and
plots; rebuilding the keyboard descriptors requires the separate score-analysis
materials. `figure_captions.txt` contains the updated captions for this repository edition.

The repository edition adds Berg and Webern to the comparison. It does not automatically update the native manuscript.
