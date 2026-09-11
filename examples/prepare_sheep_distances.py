"""Prepare local Dryad sheep step lengths; no data are downloaded or bundled."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from digitalcreativity.movement import distance_threshold_events


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('distances', type=Path, help='Original MovementDistance.csv (no header)')
    parser.add_argument('timestamps', type=Path, help='Original ts.csv (time in second column)')
    parser.add_argument('output', type=Path, help='New output directory')
    parser.add_argument('--threshold', type=float, default=50.)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output directory already exists')
    rows = []
    with args.distances.open(newline='') as handle:
        for row in csv.reader(handle):
            rows.append(np.array([np.nan if value == 'Indeterminate' else float(value) for value in row]))
    distances = np.vstack(rows)
    timestamps = pd.read_csv(args.timestamps).iloc[:, 1].to_numpy(float)
    frame, metadata = distance_threshold_events(distances, timestamps,
        [f'sheep_{i+1:02d}' for i in range(len(distances))], args.threshold, 6.)
    metadata.update(source='Dryad doi:10.5061/dryad.59zw3r2d6', license='CC0-1.0',
        timestamp_row_numbering='One-based data rows, excluding the CSV header',
        input_sha256={str(p.name):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [args.distances, args.timestamps]})
    args.output.mkdir(parents=True)
    frame.to_csv(args.output/'events.csv', index=False, float_format='%.17g')
    (args.output/'preparation.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    print(json.dumps(dict(events=len(frame), output=str(args.output))))


if __name__ == '__main__':
    main()
