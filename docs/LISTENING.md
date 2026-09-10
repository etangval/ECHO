# Listening synthesis and aggregate analysis

## Distinct instruments

`render` uses recorded piano decays. `render-study` instead exposes the archived three-harmonic sustained-tone instrument used in the fixed A/B listening comparison: partial weights 1, 0.105 and 0.023; pitch-dependent exponential decay; a history-dependent mixture of 60 ms and 190 ms attacks; fixed equal-power stereo lanes; ten cross-channel delay taps. Phase is continuous per pitch. The final ten seconds contain no new attacks, with a short terminal guard fade. These choices are explicit and are not a model of every real piano or every listener.

```sh
digitalcreativity render-study runs/demo/events.npz outputs/study.wav --duration 120 --mp3
digitalcreativity render-study runs/demo/random_events.npz outputs/control.wav --duration 120 --mp3
```

The optional MP3 path measures integrated loudness and true peak with FFmpeg, then applies one constant gain per file toward -23 LUFS, subject to a -2 dBTP source peak ceiling. No dynamic limiter or within-file gain normalisation is applied. Decoded MP3 measurements are recorded because encoding changes exact loudness/peak. Require matched delivery loudness and verify the output in an actual study. Outputs are never silently overwritten.

The archived study used three prespecified random seeds per domain, permuting only the active pitch inventory. Every event-level onset, velocity, envelope mixture and spatial lane was frozen across each pair. This estimates the contribution of pitch assignment conditional on shared rendering decisions; it is not an ablation identifying the separate contribution of every objective term. Fixed excerpts cannot support inference over an unlimited population of new pieces.

## Local response schema

The aggregate command accepts a JSON array or an object with a `responses` array. Artificial example record:

```json
{"domain":"artificial", "firstCondition":"optimized", "randomVariant":1,
 "scaleOrientation":"1=A,4=equal,7=B",
 "comparisons":{"beauty":2,"pleasantness":3,"preference":4}}
```

```sh
digitalcreativity listening private/input.json outputs/aggregate.json
```

All three outcomes require integer 1..7. Positive oriented scores favour the optimized mapping; equal is zero. The output contains aggregate counts, distributions, bootstrap intervals (20,000 seeded draws), exact sign tests excluding ties, Holm corrections across the three pooled outcomes and across all domain-outcome contrasts, and equal-domain-weighted coded means. The implementation's `sign_p_holm_9` field retains the study naming convention; the actual correction uses however many domain-outcome tests are present. Means of ordinal codes are descriptive, not physical distances of beauty. If variant labels exist, exploratory HC3 adjustment includes domain-specific A/B effects and nested random-variant offsets.

No participant IDs, email, ages, free text or row-level responses are written into the aggregate output. Keep the input private; aggregate combinations may still require disclosure review for small groups. The software performs no network transmission. Consent, permitted publication scope, withdrawal handling and data retention remain responsibilities of the study organiser. Reconcile withdrawals before publication; never manufacture an ethics approval or infer that an online volunteer study needs none.

The public repository deliberately includes no survey observations or evaluated recordings. Claims about human aesthetic benefit require an actual evaluation of a stated stimulus and listener population; the objective value alone is not validation.
