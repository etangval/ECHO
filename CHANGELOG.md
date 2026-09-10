# Changelog

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
