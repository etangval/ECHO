# Input formats and adapters

All commands operate on files you supply locally. The repository does not contain, fetch or redistribute the original research records.

## Categorical events

Canonical columns: `time_seconds,category`, optionally `event_id`. Extra columns are not automatically copied to outputs. Negative relative times are allowed. Use a documented source clock and finite values. Empty category labels, duplicated event IDs and nonfinite times fail validation.

For a spike-style CSV with `cellNumber,firing_ms`:

```sh
digitalcreativity import local_spikes.csv data/neural --format csv --time-column firing_ms --category-column cellNumber --time-unit milliseconds
digitalcreativity sonify data/neural/events.csv runs/neural --intervals neural_coverage.csv
```

The adapter divides milliseconds by 1000; it does not invent an acquisition interval. Supply coverage from acquisition metadata. Category sampling is uniform over distinct string labels, using the declared seed. It is not selection by firing rate. Label ordering is lexicographic in this generic release; earlier study scripts ordered numeric identities numerically. Consequently, this refactor is not a claim of bit-identical reconstruction of earlier private mappings from a seed alone.

## Earthquake events

Download a CSV using the [USGS FDSN Event Web Service](https://earthquake.usgs.gov/fdsnws/event/1/). Declare and retain the query, time limits and catalogue filters with your own data. The importer accepts standard USGS `time`, `latitude`, `longitude` columns:

```sh
digitalcreativity import earthquakes.csv data/earthquake --format usgs --time-column time
digitalcreativity sonify data/earthquake/events.csv runs/earthquake --adapter geographic --voices 30 --intervals earthquake_coverage.csv
```

Times are seconds relative to the earliest imported UTC timestamp; `import.json` records that origin. Express the query coverage relative to this same origin, including any known observation gaps. The importer does not interpret the first/last event as the full query coverage.

Spherical k-means partitions unit vectors derived from latitude/longitude, using 12 seeded initializations. Each event is assigned to the centroid with greatest dot product. Longitude wraparound is handled on the sphere. The selected centroids and counts are local run metadata. These are data-fitted regions, not named tectonic plates. Use fewer groups if there are fewer distinct positions. The method discards continuous positional information in the categorical sonification; preserve the prepared CSV separately if coordinates matter.

You can also supply a canonical CSV directly with `time_seconds,latitude_deg,longitude_deg`.

## X-ray photon events

Obtain an appropriately calibrated and filtered event file from [NASA HEASARC](https://heasarc.gsfc.nasa.gov/). The included adapter supports local NICER `EVENTS`/`GTI` FITS files with `TIME`, `PI`, `START`, `STOP`, second-based `TIMEUNIT`, and extension-specific `TIMEZERO`. It is not a general mission-independent FITS calibration pipeline.

```sh
python -m pip install ".[fits]"
digitalcreativity import observation.evt.gz data/xray --format nicer --pi-min 20 --pi-max 1500
digitalcreativity sonify data/xray/events.csv runs/xray --adapter ordered --voices 30 --intervals data/xray/coverage.csv
```

The adapter keeps events inside half-open GTIs and the inclusive PI range. It subtracts the first GTI start after adding each extension's `TIMEZERO`, so events and intervals share a clock. Mission clock origin and available MJD reference metadata are recorded locally. This conversion is not a UTC/barycentric correction; perform appropriate calibration before import. Confirm the PI convention for your instrument rather than treating PI as a universal energy unit.

The ordered-mark adapter partitions distinct values into contiguous bands minimizing squared count imbalance about `N/K`. Equal PI values are never split. Inclusive lower boundaries of the new bands are saved in `manifest.json`. For another ordered point process, supply `time_seconds,ordered_mark` directly. Complexity is O(K M²) time and O(K M) memory for M distinct ordered values; this exact dynamic program is suited to discrete instrument channels. Millions of unique continuous values require a separately declared quantizer before this step.

## Coverage and selection

```csv
start_seconds,stop_seconds
0,100
120,300
```

Intervals must be positive, nonoverlapping and share the event clock. An event exactly at a stop is outside that interval. Auto mode never concatenates across gaps. Context features and partition fitting use the supplied record; this is an exploratory fit, not an independently held-out estimate. Selection is based on event descriptors and audibility targets, not harmonic scores or listeners' ratings. Save the reported selection rules and inclusion counts when reporting results.

Geographic and ordered partitions fitted on one record should be frozen before a held-out comparison. You can apply saved centroids/boundaries yourself to produce a categorical CSV and run `--adapter categorical`; do not refit them silently on test observations.

## Prepared versus raw events

Timing and identity preservation apply after explicit filtering, category selection/quantization and viewport selection. One retained event becomes one note-on. No rhythmic grid, jitter, merging, thinning or looping is applied inside the retained viewport. Coincident observations remain separate note-ons. Symbolic multiplicity can be recovered even though an external MIDI instrument may not sound coincident same-pitch strikes separately.
