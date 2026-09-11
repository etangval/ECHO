# Movement-derived events from a simultaneously tracked flock

Della Libera et al. (2023), *Fission-fusion dynamics in sheep: the influence of resource distribution and temporal activity patterns*, provides a useful alternative to independent animal deployments. The study tracked a flock of 50 sheep every six seconds over 16 days. Obtain the two original files from [Dryad](https://doi.org/10.5061/dryad.59zw3r2d6), under CC0: `MovementDistance.csv` and `ts.csv`. Keep originals separate from prepared output. The [article](https://doi.org/10.1098/rsos.230402) describes the source authors' GPS cleaning and interpolation.

The public matrix contains **per-step movement distances**, not individual latitude/longitude trajectories. Its 51 rows follow the source ID numbering 1–51; not all IDs occur in every recording block. Do not infer that all 51 were tracked simultaneously, merge different IDs, or replace missing observations with stationary steps. The 210,350 columns correspond to the intervals between 210,351 timestamps. Column `j` (zero-based) ends at timestamp `j+1`. `Indeterminate` denotes missing values. The three long timestamp gaps require resets.

After installing this repository, prepare local events:

```sh
python examples/prepare_sheep_distances.py raw/MovementDistance.csv raw/ts.csv prepared/sheep50 --threshold 50
```

For each identity, accumulate valid consecutive step lengths. At the first observed endpoint where the sum reaches 50 m, emit one event and reset the sum to zero. Discard the overshoot. A missing, nonfinite or negative distance, or an interval other than six seconds, resets the sum without an event. A large single step creates at most one event. This is cumulative path length; it differs from displacement from an anchor location. It is also distinct from movement onset or a raw GPS fix.

The output preserves the observed endpoint time and records the last interval's start as a lower bound for the threshold crossing. At uniform playback factor `s`, the six-second sampling lattice becomes `6/s` playback seconds. No sub-sample jitter is added. MIDI decoding can recover the prepared movement-event times and identities, not the full trajectory or the unknown exact physical crossing times.

Repeat with thresholds 25 and 100 m to examine sensitivity. Report event counts, active identities, and temporal density variation before making robustness claims. The default 50 m is an explicit creative event definition, not a species-independent behavioural threshold or a GPS-error calibration. Supply actual observation coverage for any subsequent temporal selection or process inference. The event table alone does not establish coverage, stationarity or simultaneous availability of all identities.

For the 30-minute sheep realization, the creative selection retains 50 identities from one recording block, at least 95% valid steps per identity, at least 45 active identities in each five-minute playback bin, and 100–150 attacks/minute overall. Rounded playback factors and contiguous window starts are searched before pitch optimisation. Among feasible candidates, the selection cost is five-minute rate CV plus half the relative deviation of the mean from 125 attacks/minute. This listening-texture selection is separate from inferential sampling or the harmonic objective. The other source adapters retain their own event definitions.

The reusable array-level operator is `digitalcreativity.movement.distance_threshold_events`. The example script reads local files, records their SHA-256 hashes, and writes a new event table; it does not download or upload observations.

## Optional model-based timing within a sample interval

Endpoint detection can concentrate notes on the sampling lattice: at five-fold playback compression, all endpoints fall 1.2 seconds apart. An explicit interpolation option estimates each already detected crossing's position within its six-second step:

```sh
python examples/prepare_sheep_distances.py raw/MovementDistance.csv raw/ts.csv prepared/sheep-interpolated --threshold 50 --interpolate
```

Let the crossing step span times $t_j$ to $t_{j+1}$, have length $d_j>0$, and complete an accumulated length $A_j$ for threshold $D$. Under constant speed within that step, the crossing fraction is $f_j=1-(A_j-D)/d_j$, and the estimated time is $\hat t=t_j+f_j(t_{j+1}-t_j)$. The operator retains the same detections and the same reset-at-endpoint rule, including discarded overshoot; it does not replace this detector with a continuous path-length counter. Only the time attached to each detection is estimated. The reusable function is `interpolate_distance_crossings`.

Observed endpoints, interval lower bounds and crossing fractions remain in the output table. No missing interval is bridged and no random timing jitter is added. These times are model estimates, not extra observations or improved GPS resolution. Any timing-preservation or reconstruction claim must specify whether it concerns observed endpoints or the derived estimated event process. Interpolation can disperse artificial coincidences, but does not prove that the original animals moved at the inferred sub-sample times.
