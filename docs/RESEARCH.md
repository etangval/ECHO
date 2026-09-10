# Public sources and common diagnostics

The source domains are parallel applications of the same event-processing tools. Their entities and events have different meanings; common metrics do not make those meanings interchangeable. Install with `python -m pip install ".[audio,research]"`.

## Acquisition and licences

Download only the indicated files from the original providers, into a local folder outside Git tracking. Keep originals unchanged and record SHA-256 hashes. URLs and licences were verified on 10 September 2026. Provider terms apply separately from the MIT software licence.

| Source | Official retrieval | Files | Terms |
|---|---|---|---|
| Online Retail II | [UCI / DOI](https://doi.org/10.24432/C5CG6D) | `online_retail_II.xlsx` (45,622,278 bytes) | CC BY 4.0; cite Chen (2012) |
| Yellow Taxi, January 2026 | [TLC records](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page), [Parquet](https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2026-01.parquet), [zone lookup](https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv) | Parquet (64,165,080 bytes), lookup (12,331 bytes) | [NYC Open Data terms](https://data.cityofnewyork.us/stories/s/Terms-of-Use/k9k7-3cje/); no CC licence assumed |
| Pet Cats Australia | [Movebank DOI](https://doi.org/10.5441/001/1.289p5s77), [record move.876](https://datarepository.movebank.org/handle/10255/move.876) | event CSV (139,910,027 bytes), reference CSV (123,468 bytes), README | CC0; data by Philip Roetman and Hayley Tindle (2020); related paper Kays et al. (2020), doi:10.1111/acv.12563 |
| Mouse CA1 | [DANDI 000552 frozen version](https://doi.org/10.48324/dandi.000552/0.230630.2304) | Only `sub-e14-2m3/sub-e14-2m3_ses-e14-2m3-201121_behavior+ecephys.nwb` (41,281,925 bytes) | CC BY 4.0; Huszár, Zhang, Blockus and Buzsáki (2023), associated Nature Neuroscience 2022 paper doi:10.1038/s41593-022-01138-x |

Do not download the whole DANDI collection. The selected asset ID is `f36a3ffe-1aa2-4019-a8fc-07b03bb2b38e`; [official single-asset download](https://api.dandiarchive.org/api/assets/f36a3ffe-1aa2-4019-a8fc-07b03bb2b38e/download/) redirects to its blob. Its SHA-256 is `f4f08fe3960a8e6c41433f7e828b5d9f424d58d575321586610bf1d3a4bf05be`. The source NWB has 56 sorted units and position data. Unit cell-type labels are absent; do not call all units pyramidal neurons. DANDI 000410 is not used.

## Preparation

```sh
digitalcreativity prepare retail online_retail_II.xlsx data/retail
digitalcreativity prepare taxi yellow_tripdata_2026-01.parquet data/taxi
digitalcreativity prepare cats "Pet Cats Australia.csv" data/cats --reference "Pet Cats Australia-reference-data.csv"
digitalcreativity prepare hippocampus sub-e14-2m3_ses-e14-2m3-201121_behavior+ecephys.nwb data/hippocampus
```

Each destination must be new or empty. Outputs include long-format `events.parquet` (`source, entity_id, event_time, event_type, mark_1, mark_2` where applicable), `observation_intervals.parquet`, a provenance/exclusion report and minimal `sonification_events.csv`/`sonification_coverage.csv` inputs. Times are seconds in the declared clock; source precision is retained. Naive merchant and local taxi times are represented as nominal calendar seconds, not relabelled as known UTC acquisition times.

- Purchases: unify invoice IDs across both worksheets; aggregate product rows; identify cancellations and ambiguous customer/time records separately. Retain positively priced qualifying purchases. Missing-customer activity cannot be assigned an invented identity.
- Taxi: one valid pickup per event, zone as identity. Enforce January 2026 and plausible trip intervals; strict cleaning excludes negative distance, fare and total. Missing passenger count alone is allowed. The report and `relaxed_events.parquet` support cleaning sensitivity; `--relaxed-taxi` selects the relaxed branch explicitly.
- Cats: author-visible valid GPS fixes; each event is the first confirming fix beyond an anchor-centred 50 m disk. Reset anchors at gaps over 900 seconds. Also extract 25/100 m versions and linked-path/speed summaries. Crossing times are interval-censored, not exact movement onsets. Statistical support comprises linked-fix episodes. The sound retains deployment calendar time and silences, never aligning cats into a fabricated simultaneous population.
- CA1: this adapter deliberately targets the selected NWB schema. Use the complete supplied position interval as the primary behaviour-supported input, independent of spike count or musical score; extract all unit events, position, smoothed speed and available annotations. Other NWB layouts require a declared adapter extension. It does not download LFP/electrode waveforms or infer unavailable cell labels.

## Shared analysis

```sh
digitalcreativity analyze data/retail outputs/retail --surrogates
digitalcreativity analyze data/taxi outputs/taxi --surrogates
digitalcreativity analyze data/cats outputs/cats --asynchronous --surrogates
digitalcreativity analyze data/hippocampus outputs/hippocampus --surrogates
```

All prepared entities enter descriptive interval metrics; up to 24 uniformly sampled entities with at least 30 complete intervals enter renewal/surrogate diagnostics. Intervals are never connected across acquisition gaps. Gamma/Weibull/exponential renewal likelihoods include right censoring after the final event in each episode; tied or coarse clocks bypass continuous-time fitting.

Population counts use explicit support, multiple bin widths for Fano and avalanches, masked autocorrelation, Welch spectra and descriptive DFA. Trend and daily/weekly harmonics, with available CA1 speed/position, enter a Poisson baseline. A nonnegative exponential count-history kernel provides a **binned self-exciting Poisson approximation**, not a fully observed continuous-time Hawkes fit. Fit the first 70% of complete time bins; evaluate chronological one-step predictions on the last 30%. Report held-out likelihood, randomized count-PIT discrepancy, Pearson dispersion and residual correlation. A 199-replicate homogeneous-Poisson bootstrap calibrates one dispersion diagnostic. These tools do not establish Poisson equivalence or identify causal excitation.

Surrogates shuffle IEIs within observed episodes and independently permute each entity's counts inside local 64-bin blocks. The former preserves interval distributions while removing order; the latter preserves local count distributions while disrupting coactivation. Rate nonstationarity can affect both comparisons. Synchrony is descriptive pairwise coactivation across three bin scales. Shared continuous observation support is required. Independent cat deployments receive no population synchrony, avalanche or causal branching claim.

Avalanche size/duration refer to runs of occupied bins bracketed by observed silence. The adjacent-bin count ratio is not a causal branching ratio; changing bins can change the result drastically. Power spectra, DFA and broad interval tails alone do not prove long-range correlations or criticality. Insufficient support yields an explicit status, not fabricated estimates.

For defensible extensions, retain additional date/state covariates, test further scales on independent records, and compare models on held-out intervals. Sonification itself requires none of these source mechanisms to be Poisson.
