# Changelog

## 0.2.0 — 2026-09-10

- Source adapters for Online Retail II invoices, NYC January 2026 taxi pickups, Movebank cat displacement and the selected DANDI 000552 CA1 NWB session. Originals remain unchanged; provenance and exclusion decisions are recorded locally.
- Coverage-aware IEI, CV, CV2, LV, burstiness, event rates, multiscale Fano, ACF, power spectra, DFA, censored renewal fits, chronological held-out Poisson and binned self-exciting diagnostics. Local count and within-episode IEI surrogates; asynchronous animal deployments are not a simultaneous population.
- Explicit datetime-unit normalization supports pandas 2 and 3 without a thousand-fold clock error.
- Optional declared minimum recurring-identity count before uniform pitch-budget selection.
- **Baseline fix:** permute only pitches that are active in the selected interval. Inactive category assignments stay fixed, preserving the sounding pitch inventory. All other event attributes remain fixed. Recompute random controls made with v0.1.0 if their selected interval had inactive categories; optimized outputs are unaffected.
- Archived three-harmonic listening renderer, constant-gain loudness matching and final-response aggregate statistics. This instrument differs from the sampled piano and the offline sine smoke test.
- Research/listening CLI commands, synthetic regression tests and expanded CI dependencies.

No scientific observations, participant records, evaluated audio or private event maps are included. The archived renderer was checked locally against an evaluated WAV and reproduced its bytes; this does not make the confidential source data publicly available.

## 0.1.0 — 2026-09-10

First public, data-free toolkit release, refactored from the study's local sonification scripts.

- Shared higher-order pitch-class-set objective, register/roughness/leap terms and seeded annealing.
- Exact active-set aggregation; categorical, spherical-geographic and ordered-band adapters.
- Explicit observation coverage, representative contexts and rounded audibility-constrained speeds.
- Deterministic expression, repeat attenuation, fixed stereo positions, held pedal and ten-second ending.
- MIDI, sampled piano WAV/MP3, controlled random-permutation baseline, reconstruction and artifact audit.
- Synthetic input, documentation, unit/integration tests and three-platform CI.

Public-interface changes are explicit: string category ordering, support for one category and coincident events, overflow-resistant long-duration load calculation, short-duration convolution handling, no MIDI reverb request, and a ten-second no-new-note ending for every duration. Scientific input paths and private records are removed. The sampled piano backend replaces the earlier exploratory oscillator renderer. The sine backend is for offline smoke tests only.

This release exposes the implemented method; it does not redistribute or claim exact reproduction of the private study observations, listening-stimulus assignments or survey dataset. New user inputs and the declared parameters determine new outputs. The matched random control is a permutation of the optimized pitch inventory; it must be identified as such when reporting experiments.
