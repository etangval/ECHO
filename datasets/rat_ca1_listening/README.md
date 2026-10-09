# Rat CA1 recording used in the listening comparison

This is the sorted spike-time recording used to create the neuronal stimulus pair in **Designing for Sonic Beauty: Event-Conserving Sonification through Harmonic Optimization**. Yuji Ikegaya authorized public release of this laboratory dataset on October 9, 2026.

The source is one approximately 61-minute recording from dorsal hippocampal CA1 in one male Long-Evans rat freely exploring its home cage, acquired in the Ikegaya laboratory at the University of Tokyo. It contains 1,501,913 spike events from 168 putative pyramidal units. It was repurposed from a separate laboratory study; no rats were sacrificed specifically for the sonification study. Animal procedures were approved by the Animal Experiment Ethics Committee of the University of Tokyo (P4-15 and A2025P009) and followed the University of Tokyo guidelines for the care and use of laboratory animals.

This recording supplied the **human listening comparison**. The public hippocampal YouTube demonstration instead uses the openly available **DANDI 000552 mouse CA1 dataset**. The six-animal cohort of the separate laboratory study is not an additional analysis in ECHO.

## Files and interpretation

- `spiketrain.csv`: the complete, byte-for-byte unchanged author-supplied table. `cellNumber` is the integer unit identifier; `firing_ms` is spike time in milliseconds on the source recording clock. The file has 22,576,546 bytes and no missing values. These are spike-sorted events, not raw extracellular voltage traces.
- `listening_excerpt.csv`: the 264 source events actually used for the 120-second neuronal listening stimulus. `event_id` is the one-based row of the source table, excluding its header; `time_seconds` is `firing_ms / 1000`; `group_index` is the prepared category index; `onset_seconds` is the playback onset. Every event is traceable to the source table.
- `optimized_0_mapping.csv` and `random_1_mapping.csv` through `random_3_mapping.csv`: the fixed pitch maps used for the optimized stimulus and its three random controls. The mapping schema is preserved from stimulus preparation.
- `metadata.json`: recording provenance, animal approval numbers, acquisition and sorting methods, file integrity information, and the excerpt clock.

Source SHA-256: `1c552556365674368f0f7302df9c62ffbedf8f39f8cbf4738e6df74395abad64`.

## Recording and unit preparation

The rat was 10 weeks old and approximately 350 g at surgery (Japan SLC, Shizuoka, Japan). Two Cambridge Neurotech ASSY-116 E-1 silicon probes were advanced into dorsal CA1. Activity was acquired with an Intan system at 30 kHz. Broadband data were band-pass filtered at 300–6000 Hz and common-average referenced before Kilosort 2 sorting and manual curation in Phy. Curation assessed waveforms, refractory-period contamination below 0.5% within a 2-ms interval, amplitude stability, and cluster separation. Units with trough-to-peak latency shorter than 0.5 ms were excluded as putative interneurons; the 168 retained units were classified as putative pyramidal cells. Waveform criteria do not establish cell identity.

The author supplied the recording provenance. This release does not include broadband recordings or spike waveforms, so it does not independently reproduce the spike-sorting or cell-classification steps. It provides the complete event table used as input to sonification.

## Reuse

This dataset is distributed under the repository's [MIT license](../../LICENSE). Please acknowledge Yuji Ikegaya and cite the associated study and this dataset location when reusing it. Individual human questionnaire responses remain private under the participant consent terms and are not included in this release. See the [analysis supplement](../../paper_analysis/sonic_beauty/) for aggregate listening results and the [listening tools](../../docs/LISTENING.md) for synthesis and analysis.
