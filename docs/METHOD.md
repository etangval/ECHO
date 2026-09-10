# Mathematical method and implementation scope

This document describes the **implemented** public method. Parameters are explicit compositional choices, not estimated universal auditory thresholds. No completed listening-study results are asserted. See `engine.py`, `temporal.py`, `adapters.py`, `pipeline.py` and `audio.py` for the corresponding algorithms.

## 1. Prepared event object and feasible pitch maps

Let the prepared categorical record be

$$\mathcal E=\{(t_e,c_e)\}_{e=1}^{N},\qquad c_e\in\{1,\ldots,K\}.$$

This is a **multiset**: two observations can have the same time and category. Preparation may involve declared filtering, a category budget, quantization and temporal selection. All preservation statements below refer to this prepared object, not discarded raw observations.

For the piano palette $\mathcal P=\{21,\ldots,108\}$, the feasible set is

$$\Phi_K=\{\phi:\{1,\ldots,K\}\to\mathcal P\mid\phi\text{ is injective}\},\qquad 1\le K\le70.$$

The adjustable category budget is a design constraint for control and audibility. It is not a claim that human listeners discriminate 70 independent simultaneous streams. Categories are fixed throughout a run; their pitches do not change with local chords.

The playback transformation is affine:

$$u_e=b+\frac{t_e-a}{s},\qquad p_e=\phi(c_e),\qquad s>0.$$

Here $s$ is source seconds per playback second; $s=1/40$ means forty-fold slowdown. The active viewport is half-open. The default entrance is $b=1$ s, with no new note onsets in the final 10 s. The pedal remains held to the endpoint.

## 2. Optional context and speed selection

Auto mode requires explicit nonoverlapping observation intervals. Let their total exposure be $L$ and the retained-category event rate be $r=N/L$. For active output length $T$, context width is

$$W=\min\left(\frac{Q(T)}r,\;\max_j |I_j|\right),\qquad
Q(T)=\max\left(20,\operatorname{round}\left(1024\frac{T}{116}\right)\right).$$

Candidates of width $W$ advance by $W/2$ within a single valid interval; candidates with fewer than 20 observations are excluded. Five descriptors are computed: log relative rate, log-one-plus interevent coefficient of variation, log-one-plus 16-bin Fano factor, normalized mark entropy (zero for one category), and Jensen–Shannon divergence to the full retained-category distribution. Coordinatewise midranks normalize their scales. The chosen context is the observed medoid under Euclidean distance between these rank vectors; the earliest candidate breaks a tie. This centrality is specific to the declared descriptors, not a guarantee of scientific representativeness.

The lower-median event of the context anchors the viewport. Candidate speed factors are positive multipliers with one or two significant digits, or their reciprocals. For each factor, a centered source viewport of width $Ts$ must fit inside the context. Using the viewport's playback onsets, define

$$R(u)=\sum_{e:u_e\le u}e^{-(u-u_e)/\tau},\qquad
A_\delta(u)=\#\{e:u-\delta<u_e\le u\}.$$

On a 20-ms grid, choose the fastest candidate satisfying

$$\frac NT\le3,\qquad Q_{.95}[R]\le8,\qquad Q_{.95}[A_{.25}]\le3,\qquad\tau=1.5\text{ s}.$$

The stable recurrence $R_e=R_{e-1}\exp[-(u_e-u_{e-1})/\tau]+1$ avoids overflow in long renders. Limits constrain the specified quantiles, not every instantaneous peak. No feasible candidate means an explicit error. Selection never uses harmonic scores or measured liking. `--mode all` bypasses this selection and profile enforcement, includes all retained-category events, and uses an explicitly supplied rounded speed; its output duration follows the source span.

## 3. Higher-order harmonic term

For support $\ell\in\{0.32,1.5\}$ s and grid spacing 0.08 s, let $B_{q,c}^{(\ell)}$ indicate whether category $c$ has an onset in $(u_q-\ell,u_q]$. Its pitch-class set is

$$S_q^{(\ell)}(\phi)=\{\phi(c)\bmod12:B_{q,c}^{(\ell)}=1\}.$$

Binary support records an active category once even if it struck repeatedly. Distinct categories at octave-related pitches contribute once to the pitch-class set but separately to register-sensitive roughness.

The template dictionary contains all roots of major, minor, suspended, diminished and augmented triads and common seventh, sixth, added-ninth and ninth structures. Deduplication yields 175 distinct pitch-class sets. Hand-assigned nonnegative priors range from 0 to 0.13. Dominant sevenths and minor sixths are allowed vocabulary elements, not automatically classified as errors.

$$H(S)=\min_{C\in\mathcal C}\left[
3\frac{|S\setminus C|}{\max(1,|S|)}+
0.45\frac{|C\setminus S|}{|C|}+\pi_C\right],\qquad H(S)=0\text{ if }|S|\le1.$$

All 4096 subsets are tabulated. This is a joint set evaluation through a minimum over templates, not an assumption that chord quality is a sum of pairwise interval scores. A dictionary encompassing all transpositions gives

$$H(S+r)=H(S),\qquad r\in\mathbb Z_{12}.$$

The full objective below is **not** transposition invariant because register, palette boundaries and the frequency-dependent interference term are retained. This cultural vocabulary is one compositional choice; other tuning systems and harmonic traditions require a different palette and set functional.

## 4. Frequency, transition and register terms

With $f_p=440\,2^{(p-69)/12}$ Hz, a six-partial interference proxy is

$$\widetilde\rho(p,q)=\sum_{h=1}^{6}\sum_{k=1}^{6}
\frac{e^{-3.5x_{hk}}-e^{-5.75x_{hk}}}{(hk)^{1.4}},\qquad
x_{hk}=\frac{0.24|hf_p-kf_q|}{0.021\min(hf_p,kf_q)+19}.$$

Normalize by the maximum over the full 88-key table and set its diagonal to zero. $R_q^{(\ell)}$ is the average of this table over distinct active category pairs (zero if fewer than two). It is a transparent proxy, not calibrated piano acoustics or a fitted model of individual preference.

For consecutive onsets separated by 0.04–1.2 s, form empirical category-transition weights $W_{cd}$, normalized by the number of eligible transitions. If none are eligible, the term is zero. For $d=|\phi(c)-\phi(d')|$ semitones,

$$J_M=\sum_{c,d'}W_{cd'}\left[\frac{d}{12}+\frac12\left(\frac{[d-7]_+}{12}\right)^2\right].$$

This discourages large adjacent-onset leaps; it does not infer a unique monophonic melody. Let $w_c$ be the fraction of events in category $c$. Then

$$J_G=\sum_c w_c\left[
\left(\frac{[48-\phi(c)]_+}{12}\right)^2+
\left(\frac{[\phi(c)-80]_+}{12}\right)^2+
0.15\left(\frac{\phi(c)-64}{24}\right)^2\right].$$

## 5. Complete objective and search

For each support, average over all frames of the requested output, including silent frames:

$$J_\ell(\phi)=\frac1F\sum_q\left[H(S_q^{(\ell)}(\phi))+0.30R_q^{(\ell)}(\phi)\right],$$

$$J(\phi)=0.30J_{0.32}(\phi)+0.70J_{1.5}(\phi)+0.12J_M(\phi)+0.08J_G(\phi).$$

Identical active-category sets are aggregated exactly by summing their frame weights. The objective is unchanged by this compression. The search uses three initial injective maps with seeds 1701, 1723 and 1741, each with 14,000 simulated-annealing proposals. A proposal swaps two category pitches with probability 0.68 or replaces one with an unused key. For one category only replacements are used. Temperature decreases geometrically from 0.010 to 0.000030; uphill proposals are accepted with probability $\exp(-\Delta J/T)$. The best encountered map across all restarts is retained, and incremental calculations are checked against full recomputation.

There are $88!/(88-K)!$ feasible assignments. The implementation is a heuristic for this combinatorial search, not a global-optimality certificate. Memory for frame construction scales as $O(FK)$; precomputation is reduced to $U$ distinct active sets. A dense worst-case full evaluation is $O(UK^2+K^2)$; each proposal updates affected frames and the category transition/register terms. The rank-medoid context step is quadratic in candidate count; it is evaluated in bounded-memory blocks. The ordered-band adapter is $O(KM^2)$ for $M$ distinct values. No proof of NP-hardness of this particular restricted objective is asserted here.

Weights specify one scalarization of several competing goals. Exploring Pareto-efficient solutions is a possible extension; this release does not calculate or claim a Pareto frontier.

## 6. Reproducible expression and attenuation

Expression changes velocity, not note onset. Let $z_e\in[-2,2]$ be robustly standardized log local onset density, using a 1.5-s Gaussian on a 20-ms grid and median/MAD scaling. Let

$$P(u)=0.65\sin(2\pi u/11.3)+0.35\sin(2\pi u/19.7+0.8).$$

Each category receives a seeded bias $b_c\sim U[-1,1]$ and an AR(1) touch state $q_e=0.85q_{e^-}+\sqrt{1-0.85^2}\epsilon_e$ with standard-normal innovations. Observed touch is clipped to $[-2,2]$, while the latent state is not clipped. Independent PCG64 streams use `SeedSequence([seed,c+1])`.

With previous same-category gap $\Delta_e$ (infinite on the first event), define recovery $r_e=1-e^{-\Delta_e/0.55}-0.6$, burst $b_e=\log_2\max(1,\#\{j:u_e-0.12\le u_j\le u_e\})$, and register penalty $g_e=[48-p_e]_+/24+[p_e-84]_+/24$. Initial velocity is obtained by rounding and clipping to 38–104:

$$\widetilde V_e=71+7z_e+4P(u_e)+2.2\operatorname{clip}(q_e,-2,2)+2b_{c_e}+7r_e-2.4b_e-3g_e+L_e.$$

In each 45-ms bin, the event with greatest pre-emphasis score after removing its register penalty is a deterministic foreground leader: $L_e=4$ for that event and $-2$ for the others. Ties retain event order.

Repetition memory immediately before event $e$ is

$$\mu_e=\sum_{j<e:c_j=c_e}e^{-(u_e-u_j)/0.70}.$$

With $n_e=\#\{j:|u_j-u_e|\le0.20\}$, attenuation is

$$a_e=\frac{1}{1+1.5\mu_e}\left(1+0.15[n_e-3]_+\right)^{-1/2},\qquad
V_e=\operatorname{clip}_{18}^{78}\operatorname{round}\left(0.87V_e^{(0)}a_e^{1/1.8}\right).$$

A three-second smoothstep entrance multiplier $0.65+0.35x^2(3-2x)$ with $x=\operatorname{clip}(u_e/3,0,1)$ is then applied, followed by rounding and clipping to 18–78. Attenuation is history dependent and has a velocity floor; it does not remove events. It is not claimed as a calibrated human-hearing compression law. `soft_attack_fraction` is retained as diagnostic metadata but is unused by the sampled-piano backend.

## 7. Rendering and controlled comparison

Optimized pitches determine 15 fixed stereo lanes, using

$$\ell_e=\operatorname{round}\left(14\frac{p_e-21}{87}\right),\qquad
\operatorname{pan}_e=\operatorname{round}(18+91\ell_e/14).$$

The MIDI percussion channel is excluded. Each lane has a constant pan controller and sustain CC64=127 from time zero until the endpoint; MIDI note gate is at most 0.32 s, shortened at repeated strikes where possible. Coincident quantized same-pitch onsets retain separate note-ons with a one-tick minimum gate. MIDI requests no added reverb. Instrument interpretation of controller messages is implementation dependent.

The audio backend resamples the nearest supplied piano sample, trims its leading silence, applies gain $(V_e/90)^{1.8}$ and fixed stereo balance $\sqrt2(\cos\theta_e,\sin\theta_e)$ where $\theta_e=\pi\operatorname{pan}_e/(2\cdot127)$. Each event starts independently. Full recorded decay approximates a held pedal without separate sympathetic-resonance simulation. There is no synthetic room reverb. Audio is mixed in 30-s blocks; gain is the smaller of that required for RMS 0.05 and peak 0.75. The last two seconds have a half-cosine recording-gain taper. WAV uses stereo 44.1-kHz PCM16; MP3 uses 192-kbit/s encoding.

The optional random control uniformly permutes the optimized pitch inventory. Event times, velocities and category-specific pan/channel values remain identical; only the identity-to-pitch map changes. Condition-specific audio normalization is recorded. The control is explicitly defined and does not stand for every possible random baseline. Pitch-dependent velocity terms are not recomputed for the control, because doing so would change an additional experimental factor.

## 8. Preservation and limits of invertibility

For an injective map and known $a,b,s$, symbolic inversion is

$$c_e=\phi^{-1}(p_e),\qquad t_e=a+s(u_e-b).$$

The affine clock preserves event order, simultaneous events, interevent-interval ratios and category identity. It rescales absolute intervals by $1/s$. There is no onset jitter, rhythmic quantization, event thinning or looping inside the prepared viewport.

Exported MIDI uses one tick $\delta=1/60000$ playback seconds. Nearest-tick rounding gives

$$|\widehat t_e-t_e|\le s\delta/2+\varepsilon_{\mathrm{float}}.$$

Very closely spaced events can collapse to one tick while their note-on multiplicity remains. Their strict order below that precision is not recoverable. Local sidecars retain higher-precision prepared timing and event-row metadata. Pitch maps may include categories with no events in a selected viewport; those remain part of the run's fixed mapping.

The decoder verifies the categorical event multiset, not recovery of raw coordinates, photon energies, excluded intervals, discarded identities or original event IDs from sound. Audio rendering, velocity rounding, continuous-mark quantization and omitted observations are not injective transformations of the full source dataset. MIDI and sidecars can disclose scientific observations and should remain private where appropriate. This repository releases algorithms and artificial examples only.
