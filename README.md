# ECHO: Event-Conserving Harmonic Optimisation

Turn a multivariate point process into MIDI and stereo piano audio using a fixed, injective identity-to-pitch map and sequence-wide, higher-order harmonic optimisation.

This is the public implementation accompanying **“Designing for Sonic Beauty: Event-Preserving Sonification through Harmonic Optimisation”** (manuscript in preparation). The repository contains the sonification engine, artificial examples, and a [manuscript analysis supplement](paper_analysis/sonic_beauty/) with keyboard note excerpts, aggregate listening counts, statistics and figures. Participant-level study responses, private event mappings and recorded study stimuli are not included.

The optimisation seeks a more coherent harmonic texture. Its objective is a declared compositional proxy; it does not establish that listeners find the output more beautiful, pleasant or calming. “Global” refers to the scope of the objective, not a guarantee of a global optimum.

## Quick start

Python 3.10 or newer; Windows, macOS or Linux. No API key or scientific dataset is needed for this example. This package is installed from this repository; it has not been published to PyPI.

```sh
git clone https://github.com/etangval/ECHO.git
cd ECHO
python -m venv .venv
```

Activate the environment with `source .venv/bin/activate` on macOS/Linux or `.venv\Scripts\Activate.ps1` in Windows PowerShell. Then:

```sh
python -m pip install ".[audio]"
digitalcreativity sonify examples/synthetic.csv runs/demo --intervals examples/synthetic.coverage.csv --duration 120 --voices 12 --random-baseline
digitalcreativity render runs/demo
digitalcreativity render runs/demo --condition random
digitalcreativity verify runs/demo
digitalcreativity decode runs/demo runs/recovered.csv
```

The first piano render downloads the required [Salamander Grand Piano samples](docs/THIRD_PARTY.md) to a user cache. The download is pinned to an upstream commit and recorded with SHA-256 hashes. Include the generated `PIANO_CREDITS.txt` attribution when distributing piano audio. The renderer uses full recorded decays with a held pedal, stereo balance, no added artificial reverb, a ten-second interval with no new notes and a final two-second gain taper.

For an offline audio test without downloading piano samples, use `--instrument sine --wav-only`. This test instrument is different from the piano used in the demonstrations. MIDI creation and verification work without the audio extra. A system FFmpeg or the `audio` extra is needed for piano sample decoding and MP3 encoding.

Optimisation defaults to three seeded searches of 14,000 proposals each. Runtime depends on the number of identities and distinct active sets. For a quick installation check, add `--steps 100`; this is a smoke test, not the full optimisation setting.

## Your own events

A long-format CSV uses **seconds** and a categorical identity:

```csv
event_id,time_seconds,category
1,0.012,unit_A
2,0.086,unit_B
3,0.120,unit_A
```

`event_id` is optional (otherwise the original row number is assigned); each supplied ID must be unique. Category labels, including `001` and `NA`, are strings. Times must be finite; unsorted input is stably sorted. Coincident events are retained. See [input formats and domain adapters](docs/INPUTS.md) for USGS CSV, NICER FITS and other long-format CSV files.

There are two explicit temporal modes:

| Mode | What is included | Playback clock |
|---|---|---|
| `auto` (default) | A viewport within an objectively selected representative context, for retained identities | Fastest one- or two-significant-digit factor satisfying declared density/load targets; requested output duration |
| `all` | Every event of the retained identities in the supplied CSV | Explicit `--speed`, for example `1/40`; output duration is computed from the event span |

Auto mode **requires observation coverage** in a separate CSV with `start_seconds,stop_seconds`. Intervals are half-open, nonoverlapping and in the same clock as the events. It never treats a gap without events as proof that acquisition was running. Every supplied event must be inside coverage; perform any necessary filtering explicitly before using the tool.

```sh
# One-hour output from a sufficiently long record: no event looping.
digitalcreativity sonify my_events.csv runs/hour --intervals coverage.csv --duration 3600
digitalcreativity render runs/hour

# Preserve all prepared events with an explicit forty-fold slowdown.
digitalcreativity sonify my_events.csv runs/all --mode all --speed 1/40

# Make a new artificial example, without a real dataset.
digitalcreativity synthetic examples/my_artificial.csv --seconds 300 --rate 2 --categories 12 --seed 12345
```

The default budget is at most 70 unique pitches, adjustable with `--voices 1..70`. If categorical input exceeds the budget, identities are sampled uniformly with a fixed seed before temporal selection; this is explicitly recorded. The process does not preserve discarded identities. To include every input identity, supply no more identities than the chosen budget. Geographic and ordered marks are quantized into the requested number of categories; continuous marks cannot be recovered from those categories alone.

Output durations are limited to one hour per run. In `all` mode, `--duration` does not stretch the data: duration follows the explicit speed. If there is no feasible auto viewport, the command reports an error instead of silently thinning events or relaxing the profile.

## Outputs and reconstruction

| File | Contents |
|---|---|
| `optimized.mid` | Piano program, one voice track per category, fixed pan, note-on per event, held-pedal schedule |
| `events.npz` | Prepared symbolic event attributes, timing, pitch, deterministic expression and stereo placement |
| `prepared_events.csv` | Included input rows, category, group index and playback onset |
| `manifest.json` | Pitch maps, affine clock, settings, random seeds, source hash, optimisation metrics and artifact hashes |
| `verification.json` | Hash, event count, identity, round-trip timing, pedal and ending checks |
| `context_candidates.csv`, `speed_trials.csv` | Auto-mode selection audit |
| `optimized_piano.wav`, `.mp3`, `_audio.json` | Audio and renderer provenance after `render` |
| `random.mid`, `random_events.npz` | Optional matched random-permutation control |

**These run outputs contain your observations and must be handled as data.** The software does not upload observations or outputs. The repository's ignore rules exclude normal output folders and audio, but they do not replace checking what you publish yourself.

With MIDI **plus its mapping and clock metadata**, the decoder recovers the prepared `(time, category)` event multiset to MIDI tick precision. At 30,000 ticks per beat and 120 BPM, one tick is 1/60,000 playback seconds. Source-time error is bounded by half a tick multiplied by the speed factor, plus floating-point arithmetic error. Exact original event IDs and continuous marks require their sidecars. No claim of reversible WAV/MP3 decoding is made. External synthesisers may merge coincident same-pitch strikes even when the MIDI contains every note-on; the provided sample renderer mixes each event separately.

The random control permutes the **active** optimised pitch inventory while keeping event times, velocities, envelope parameters and category-specific stereo positions fixed. Assignments for categories that are silent in the selected interval stay unchanged. This is a particular controlled baseline, not the only definition of random sonification; report the baseline and seeds used in any study.

## Public-source preparation and research diagnostics

Install `.[audio,research]` for the optional research tools. Four source adapters prepare invoice-level purchases, zone-level taxi pickups, GPS-derived displacement events and the selected open CA1 NWB session. They read originals and write separate local event/coverage tables. See [sources and exact commands](docs/RESEARCH.md), including licences, frozen DANDI version, GPS threshold sensitivity and limitations of the process models.

```sh
digitalcreativity prepare retail online_retail_II.xlsx data/retail
digitalcreativity analyze data/retail outputs/retail-analysis --surrogates
digitalcreativity sonify data/retail/sonification_events.csv runs/retail --intervals data/retail/sonification_coverage.csv --duration 3600 --min-category-events 20
```

The optional recurring-identity threshold is declared before uniform identity selection; it does not remove individual events from a retained voice. Default `1` preserves the original general-purpose eligibility rule. Scientific diagnostics retain all prepared identities independently of the voice budget.

The archived listening comparison used a **three-harmonic sustained-tone instrument**, distinct from the sampled piano in the hour-long demonstrations. `render-study` exposes that renderer and its original attack mixture, delays and constant-gain loudness matching. This permits new controlled stimuli without distributing the confidential study excerpts. `listening` aggregates local seven-point A/B records with explicit orientation, bootstrap intervals and multiplicity corrections. See [listening tools](docs/LISTENING.md).

## Manuscript analysis supplement

The [ECHO analysis supplement](paper_analysis/sonic_beauty/) reproduces the keyboard descriptors, aggregate-only listening tests and six manuscript figures. It includes its own pinned dependencies, input data, source-specific rights notices and validation instructions. Its historical reference commit is recorded separately from the current sonification engine. The existing Python package and CLI remain `digitalcreativity`.

## Method, reproducibility and reuse

- [Mathematical method and preservation claims](docs/METHOD.md)
- [Input formats and domain adapters](docs/INPUTS.md)
- [Public sources and process diagnostics](docs/RESEARCH.md)
- [Simultaneously tracked sheep: movement-distance events](docs/SHEEP.md)
- [Listening synthesis and aggregate analysis](docs/LISTENING.md)
- [Dependency/sample licences](docs/THIRD_PARTY.md)
- [Version history and scope](CHANGELOG.md)
- [Citation metadata](CITATION.cff)

```sh
python -m pip install ".[audio,fits,research,test]"
python -m pytest -q
```

Tests cover exact active-set aggregation, the annealing update, transposition of all 4096 pitch-class sets, extended chords, exhaustive small ordered partitions, geographic wraparound, GTI conversion, seeded reproducibility, coincident-event MIDI reconstruction, overflow-resistant hour-long load evaluation, controlled baselines and an offline stereo audio ending. CI runs on Windows, Linux and macOS. An original study record is neither required nor included.

The complete toolkit and manuscript analysis supplement are maintained together in [ECHO v0.3.0](https://github.com/etangval/ECHO/releases/tag/v0.3.0). Historical engine releases [v0.1.0](https://github.com/etangval/ECHO/releases/tag/v0.1.0) and [v0.2.0](https://github.com/etangval/ECHO/releases/tag/v0.2.0) retain their original commit identities here; the `legacy-sonification` branch preserves the earlier engine history. The Python import name and command remain `digitalcreativity` for compatibility. Record the release/commit, installed dependency versions and generated manifest in your own work. A seed alone does not promise identical floating-point results across every numerical-library version or platform.

The code is [MIT licensed](LICENSE). Piano samples are separately licensed CC BY 3.0. Scientific source data and other dependencies retain their own terms. The associated manuscript is in preparation; no publication DOI or completed perceptual-validation result is claimed here.

## 日本語

多変量の点過程を、固定した「カテゴリ→音程」の対応でMIDI・ピアノ音声にする公開ツールです。音程の高次和音最適化、音符密度からの再生速度設定、再現可能な強弱、ステレオ配置、踏み続けたペダルによる減衰、MIDIからのイベント復元・検証を含みます。

上の Quick start を実行すると、人工データから約2分の音源を作れます。`--duration 3600` で60分版を指定できます。最後の10秒間には新しい音を加えません。自分のCSVには `time_seconds` と `category` を用意してください。自動選択には別途、実際の観測区間を指定した `start_seconds,stop_seconds` のCSVが必要です。

参加者の個票・非公開のイベント対応表・実験音源は公開していません。論文解析の補足フォルダには、楽曲の冒頭抜粋の音符、アンケート集計値、検定結果と図を収録しています。再構成できるのは、保持したカテゴリの準備済みイベントと時刻です。除外した観測や連続値の属性、MP3から元データが復元できるという意味ではありません。音の美しさや好感度の向上は、このコードだけで実証されるものではありません。

Author: Yuji Ikegaya. This repository does not imply institutional endorsement.
