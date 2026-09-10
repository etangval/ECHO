# Reproduction checks

The 25-selection repository edition passed a full run of `python run_all.py`
with Python 3.12.14 and the pinned dependencies. This recomputed all 25 selection
coordinates from 36 excerpts and 4,379 noteheads, all 99 pitch-shuffle controls
per selection, the six figures, and the 12 aggregate listener tests.

- Maximum coordinate discrepancy: 2.842170943040401e-14.
- Maximum control discrepancy: 4.263256414560601e-14.
- All 4,096 pitch-class sets tested at 12 rotations; rotation error zero.
- Maximum Mobius reconstruction error: 4.440892098500626e-15.
- Transport versus linear programming: 12 cases; maximum discrepancy
  1.7763568394002505e-15.

`validation/reproduction_report.json` and the logs record this full run.
The earlier 23-selection package was also checked after relocation and invocation
from a different working directory. The same relative-path workflow is retained.

The two new coordinates use a corrected Berg opening input and a pinned public
Webern encoding. Their boundaries, acquisition hashes and structural checks are
recorded in `keyboard/extensions/`. No numerical result uses the faulty full-score
OMR candidates. Berg's complete-score correction remains unfinished. Numerical
reproduction does not establish the perceptual validity of these descriptors.
