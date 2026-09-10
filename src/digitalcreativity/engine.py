"""Shared harmony, expression and MIDI engine; no dataset is a reference."""
import hashlib
import json
import math
import struct
from pathlib import Path
import numpy as np

NAMES = ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B']
KEYS = np.arange(21, 109)
BITS = (1 << np.arange(12)).astype(np.int32)
POPCOUNT = np.array([i.bit_count() for i in range(4096)])
SEED = 20260909
PARAMS = {
    'frame_hop_seconds': .08, 'short_support_seconds': .320,
    'pedal_effective_support_seconds': 1.5, 'anneal_steps_each': 14000,
    'gate_seconds': .320, 'repeat_memory_seconds': .70, 'repeat_suppression': 1.5,
    'population_suppression': .15, 'isolated_velocity_scale': .87,
    'velocity_min': 18, 'velocity_max': 78,
}



def chord_tables():
    # Nonnegative, hand-designed priors, NOT estimates of human preferences.
    qualities = {
        '': ([0, 4, 7], .00), 'm': ([0, 3, 7], .00),
        'sus2': ([0, 2, 7], .05), 'sus4': ([0, 5, 7], .05),
        'dim': ([0, 3, 6], .10), 'aug': ([0, 4, 8], .13),
        '7': ([0, 4, 7, 10], .02), 'maj7': ([0, 4, 7, 11], .03),
        'm7': ([0, 3, 7, 10], .02), '6': ([0, 4, 7, 9], .02),
        'm6': ([0, 3, 7, 9], .02), 'm7b5': ([0, 3, 6, 10], .07),
        'dim7': ([0, 3, 6, 9], .09), 'add9': ([0, 2, 4, 7], .05),
        'madd9': ([0, 2, 3, 7], .05),
        '9': ([0, 2, 4, 7, 10], .10), 'maj9': ([0, 2, 4, 7, 11], .11),
        'm9': ([0, 2, 3, 7, 10], .10), '6/9': ([0, 2, 4, 7, 9], .10),
    }
    templates, names, priors = [], [], []
    seen = set()
    for quality, (intervals, prior) in qualities.items():
        for root in range(12):
            pcs = tuple(sorted((root + np.array(intervals)) % 12))
            if pcs in seen:
                continue
            seen.add(pcs)
            templates.append(np.isin(np.arange(12), pcs))
            names.append(NAMES[root] + quality)
            priors.append(prior)
    t = np.array(templates, dtype=np.float64)
    masks = np.arange(4096)
    sets = ((masks[:, None] & BITS) != 0).astype(float)
    cardinality = sets.sum(1)
    overlap = sets @ t.T
    # Outside fraction strongly penalized; missing tones tolerated at lower cost.
    costs = (3.0 * (cardinality[:, None] - overlap) / np.maximum(1, cardinality[:, None])
             + .45 * (t.sum(1)[None, :] - overlap) / t.sum(1)[None, :]
             + np.array(priors)[None, :])
    label = costs.argmin(1)
    energy = costs.min(1)
    energy[cardinality <= 1] = 0.0
    pcs = np.arange(12)
    d = np.abs(pcs[:, None] - pcs[None, :])
    d = np.minimum(d, 12 - d) / 6
    # Symmetric nearest-tone distance; an efficient voice-leading surrogate.
    transitions = np.zeros((len(t), len(t)))
    for i in range(len(t)):
        for j in range(len(t)):
            sub = d[np.ix_(t[i] > 0, t[j] > 0)]
            transitions[i, j] = .5 * (sub.min(0).mean() + sub.min(1).mean())
    return energy, label, transitions, names, t, costs


def roughness_table():
    # A transparent six-partial interference proxy, not calibrated piano physics.
    f = 440 * 2 ** ((KEYS - 69) / 12)
    r = np.zeros((89, 89), dtype=float)
    for h in range(1, 7):
        for k in range(1, 7):
            a, b = f[:, None] * h, f[None, :] * k
            x = .24 * np.abs(a - b) / (.021 * np.minimum(a, b) + 19)
            r[:88, :88] += (np.exp(-3.5*x) - np.exp(-5.75*x)) / (h*k)**1.4
    r[:88, :88] /= r[:88, :88].max()
    np.fill_diagonal(r, 0)
    return r


H, LABEL, TRANSITION, CHORD_NAMES, TEMPLATES, ALL_COSTS = chord_tables()
ROUGHNESS = roughness_table()


def build_state(active, mapping):
    pc = np.zeros((len(active), 12), dtype=np.int16)
    for i in np.flatnonzero(mapping < 88):
        pc[:, KEYS[mapping[i]] % 12] += active[:, i].astype(np.int16)
    selected = np.flatnonzero(mapping < 88)
    idx = mapping[selected]
    aa = active[:, selected]
    r = ROUGHNESS[np.ix_(idx, idx)]
    rough = np.sum((aa @ r) * aa, axis=1) * .5
    top = np.max(active * np.where(mapping < 88, np.minimum(mapping, 87)+21, 0), axis=1)
    return pc, rough, top


class Objective:
    def __init__(self, onset, group, k, duration=120.0, aggregate=True):
        self.k = k
        self.group = group
        self.freq = np.bincount(group, minlength=k)/len(group)
        grid = np.arange(0, duration, PARAMS["frame_hop_seconds"])
        matrices = []
        for support in [PARAMS["short_support_seconds"], PARAMS["pedal_effective_support_seconds"]]:
            active = np.zeros((len(grid), k), dtype=float)
            left = np.searchsorted(onset, grid-support, side="right")
            right = np.searchsorted(onset, grid, side="right")
            for row, (a, b) in enumerate(zip(left, right)):
                active[row, group[a:b]] = 1
            matrices.append(active)
        self.active = np.vstack(matrices)
        self.weights = np.r_[np.full(len(grid), .30/len(grid)), np.full(len(grid), .70/len(grid))]
        self.group_frames = [np.flatnonzero(self.active[:, c]) for c in range(k)]
        self.n = self.active.sum(axis=1)
        self.denom = np.maximum(1, self.n*(self.n-1)/2)
        self.transitions = np.zeros((k, k))
        gaps = np.diff(onset)
        usable = (gaps >= .04) & (gaps <= 1.2)
        np.add.at(self.transitions, (group[:-1][usable], group[1:][usable]), 1)
        self.transitions /= max(1, self.transitions.sum())

        self.original_frames = len(self.active)
        if aggregate:
            packed = np.packbits(self.active.astype(np.uint8), axis=1)
            _, first, inverse = np.unique(packed, axis=0, return_index=True, return_inverse=True)
            self.active = self.active[first]
            self.weights = np.bincount(inverse, weights=self.weights, minlength=len(first))
            self.group_frames = [np.flatnonzero(self.active[:, c]) for c in range(k)]
            self.n = self.active.sum(axis=1)
            self.denom = np.maximum(1, self.n*(self.n-1)/2)

    def nonlocal_cost(self, pitch):
        d = np.abs(pitch[:, None]-pitch[None, :])
        leap = d/12 + .5*(np.maximum(0, d-7)/12)**2
        melody = float(np.sum(self.transitions*leap))
        register = float(np.sum(self.freq*((np.maximum(0, 48-pitch)/12)**2+(np.maximum(0, pitch-80)/12)**2+.15*((pitch-64)/24)**2)))
        return .12*melody + .08*register, melody, register

    def full(self, pitch):
        pc, rough, _ = build_state(self.active, pitch-21)
        masks = (pc > 0).astype(np.int32) @ BITS
        local = H[masks] + .30*rough/self.denom
        tail, melody, register = self.nonlocal_cost(pitch)
        metrics = {"objective": float(local @ self.weights + tail),
            "chord_set_cost": float(H[masks] @ self.weights),
            "roughness_proxy": float((rough/self.denom) @ self.weights),
            "melody_leap_cost": melody, "register_cost": register,
            "evaluation": "Same target excerpt, .08-second grid with .32-second and 1.5-second support. Design proxies, not measured liking or held-out performance."}
        return metrics, pc, rough, local

    def optimize(self, seed, steps=14000):
        rng = np.random.default_rng(seed)
        pitch = rng.choice(KEYS, self.k, replace=False)
        initial = pitch.copy()
        metrics, pc, rough, local = self.full(pitch)
        current = metrics["objective"]
        nonlocal_current = self.nonlocal_cost(pitch)[0]
        best, best_value = pitch.copy(), current
        accepted = 0
        for step in range(steps):
            proposal = pitch.copy()
            i = int(rng.integers(self.k))
            if self.k > 1 and (self.k == len(KEYS) or rng.random() < .68):
                j = int(rng.integers(self.k-1))
                j += j >= i
                proposal[i], proposal[j] = proposal[j], proposal[i]
                changed = [i, j]
                rows = np.union1d(self.group_frames[i], self.group_frames[j])
            else:
                proposal[i] = rng.choice(np.setdiff1d(KEYS, pitch))
                changed = [i]
                rows = self.group_frames[i]
            aa = self.active[rows]
            cp = pc[rows].copy()
            rr = rough[rows].copy()
            working = pitch.copy()
            for c in changed:
                old, new = int(working[c]), int(proposal[c])
                dv = ROUGHNESS[new-21, working-21] - ROUGHNESS[old-21, working-21]
                dv[c] = 0
                rr += aa[:, c] * (aa @ dv)
                cp[:, old % 12] -= aa[:, c].astype(np.int16)
                cp[:, new % 12] += aa[:, c].astype(np.int16)
                working[c] = new
            masks = (cp > 0).astype(np.int32) @ BITS
            ll = H[masks] + .30*rr/self.denom[rows]
            nonlocal_new = self.nonlocal_cost(proposal)[0]
            delta = float((ll-local[rows]) @ self.weights[rows] + nonlocal_new-nonlocal_current)
            temperature = .010*(.000030/.010)**(step/max(1, steps-1))
            if delta <= 0 or rng.random() < math.exp(-delta/temperature):
                pitch = proposal
                pc[rows], rough[rows], local[rows] = cp, rr, ll
                nonlocal_current = nonlocal_new
                current += delta
                accepted += 1
                if current < best_value:
                    best, best_value = pitch.copy(), current
        full = self.full(best)[0]
        assert abs(full["objective"]-best_value) < 1e-9
        assert len(np.unique(best)) == self.k
        return best, {"seed": seed, "accepted": accepted, "initial": self.full(initial)[0], "optimized": full}


def soften(e):
    r={k:v.copy() for k,v in e.items()}
    t=e['onset_seconds'];cell=e['cell']
    memory=np.zeros(len(t));interval=np.full(len(t),np.inf)
    for c in np.unique(cell):
        rows=np.flatnonzero(cell==c)
        state=0.;previous=None
        for k in rows:
            delta=np.inf if previous is None else float(t[k]-previous)
            state*=math.exp(-delta/PARAMS['repeat_memory_seconds'])
            memory[k]=state;interval[k]=delta
            state+=1;previous=float(t[k])
    n=np.searchsorted(t,t+.20,side='right')-np.searchsorted(t,t-.20,side='left')
    attenuation=1/(1+PARAMS['repeat_suppression']*memory)
    population=(1+PARAMS['population_suppression']*np.maximum(0,n-3))**-.5
    v=PARAMS['isolated_velocity_scale']*e['velocity']*(attenuation*population)**(1/1.8)
    r['velocity']=np.clip(np.rint(v),PARAMS['velocity_min'],PARAMS['velocity_max']).astype(int)
    r['repeat_memory']=memory
    r['same_cell_interval_seconds']=interval
    r['repeat_amplitude_attenuation']=attenuation
    r['crowding_attenuation']=population
    r['soft_attack_fraction']=memory/(1+memory)
    return r


def expression(onset, group, pitch_mapping, duration=120.0, seed=SEED):
    pitch = pitch_mapping[group]
    k = len(pitch_mapping)
    dt = .02
    grid = np.arange(0, duration+dt, dt)
    hist = np.bincount(np.rint(onset/dt).astype(int), minlength=len(grid)).astype(float)
    kt = np.arange(-300, 301)*dt
    kernel = np.exp(-.5*(kt/1.5)**2)
    kernel /= kernel.sum()*dt
    density = np.log1p(np.interp(onset, grid, np.convolve(hist, kernel, mode="full")[len(kernel)//2:len(kernel)//2+len(hist)]))
    median = np.median(density)
    mad = max(.1, 1.4826*np.median(np.abs(density-median)))
    z = np.clip((density-median)/mad, -2, 2)
    phrase = .65*np.sin(2*np.pi*onset/11.3)+.35*np.sin(2*np.pi*onset/19.7+.8)
    burst = np.log2(np.maximum(1, np.searchsorted(onset, onset, side="right")-np.searchsorted(onset, onset-.12, side="left")))
    touch = np.zeros(len(onset)); bias = touch.copy(); recovery = touch.copy()
    for c in range(k):
        idx = np.flatnonzero(group == c)
        if not len(idx):
            continue
        rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed, c+1])))
        bias[idx] = rng.uniform(-1, 1)
        q = 0.0
        for row, epsilon in zip(idx, rng.standard_normal(len(idx))):
            q = .85*q + math.sqrt(1-.85**2)*epsilon
            touch[row] = np.clip(q, -2, 2)
        recovery[idx] = 1-np.exp(-np.r_[np.inf, np.diff(onset[idx])]/.55)-.6
    register = np.maximum(0, (48-pitch)/24)+np.maximum(0, (pitch-84)/24)
    unrounded = 71+7*z+4*phrase+2.2*touch+2*bias+7*recovery-2.4*burst-3*register
    # One representative in a 45 ms bin receives a small foreground emphasis.
    leader = np.zeros(len(onset), dtype=bool)
    bins = np.floor(onset/.045).astype(int)
    for b in np.unique(bins):
        idx = np.flatnonzero(bins == b)
        leader[idx[np.argmax(unrounded[idx]+3*register[idx])]] = True
    unrounded += np.where(leader, 4, -2)
    velocity = np.clip(np.rint(unrounded), 38, 104).astype(int)
    lane = np.rint((pitch-21)/87*14).astype(int)
    channels = np.array([c for c in range(16) if c != 9])
    events = dict(cell=group+1, onset_seconds=onset, pitch=pitch, velocity=velocity,
        channel=channels[lane], pan_cc10=np.rint(18+91*lane/14).astype(int),
        density_z=z, phrase=phrase, touch_ar1=touch, cell_bias=bias, recovery=recovery,
        burst_log2=burst, register_penalty=register, unrounded_velocity=unrounded,
        melody_attack=leader)
    events = soften(events)
    # Ease in without deleting any events, unlike cutting an existing recording.
    x = np.clip(onset/3, 0, 1)
    entrance = .65+.35*x*x*(3-2*x)
    events["velocity"] = np.clip(np.rint(events["velocity"]*entrance), 18, 78).astype(int)
    events["entrance_multiplier"] = entrance
    return events


def varlen(v):
    assert v >= 0
    out = [int(v) & 127]
    while v >> 7:
        v >>= 7
        out.insert(0, (int(v) & 127) | 128)
    return bytes(out)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def midi_bytes(events, duration):
    end_tick = round(duration * 60000)
    tracks = [b'\x00\xff\x51\x03\x07\xa1\x20'
              + varlen(end_tick) + b'\xff\x2f\x00']
    # One controller track per stereo lane. All cells in a lane share one fixed
    # pan; percussion channel 10 is never used. No channel-wide pan automation.
    for ch in sorted(set(events['channel'])):
        pan = int(events['pan_cc10'][np.flatnonzero(events['channel'] == ch)[0]])
        name = f'Piano lane {ch+1} pan {pan}'.encode('ascii')
        t = bytearray(b'\x00\xff\x03' + varlen(len(name)) + name)
        t += bytes([0, 0xC0+ch, 0])
        for cc, value in [(7,100), (10,pan), (11,127), (91,0), (64,127)]:
            t += bytes([0, 0xB0+ch, cc, value])
        # Keep the pedal down throughout the performance; release only at end.
        t += varlen(end_tick) + bytes([0xB0+ch, 64, 0])
        t += b'\x00\xff\x2f\x00'
        tracks.append(bytes(t))
    for c in sorted(set(events['cell'])):
        idx = np.flatnonzero((events['cell'] == c) & (events['onset_seconds'] < duration))
        all_idx = np.flatnonzero(events['cell'] == c)
        ch = int(events['channel'][all_idx[0]])
        pitch = int(events['pitch'][all_idx[0]])
        name = f'Voice {c} pitch {pitch}'.encode('ascii')
        t = bytearray(b'\x00\xff\x03' + varlen(len(name)) + name)
        onsets = np.rint(events['onset_seconds'][idx]*60000).astype(np.int64)
        queue = []
        for j, (row, start) in enumerate(zip(idx, onsets)):
            end = min(int(start + PARAMS['gate_seconds']*60000), end_tick)
            if j+1 < len(idx):
                end = min(end, int(onsets[j+1]))
            # Keep every note-on, including events sharing one quantized tick.
            # External MIDI synths may merge coincident voices; the symbolic
            # event multiplicity and the sample renderer retain them.
            end = max(int(start)+1, end)
            if end > end_tick:
                raise ValueError("Note onset leaves no MIDI tick before the endpoint")
            queue += [(int(start), 1, bytes([0x90+ch,pitch,int(events['velocity'][row])])),
                      (end, 0, bytes([0x80+ch,pitch,0]))]
        queue.sort(key=lambda x:(x[0],x[1]))
        previous = 0
        for tick, _, msg in queue:
            t += varlen(tick-previous) + msg
            previous = tick
        t += varlen(end_tick-previous) + b'\xff\x2f\x00'
        tracks.append(bytes(t))
    result = b'MThd' + struct.pack('>IHHH',6,1,len(tracks),30000)
    for t in tracks:
        result += b'MTrk' + struct.pack('>I',len(t)) + t
    return result


def parse_midi(path):
    b = path.read_bytes()
    assert b[:4] == b'MThd'
    ntracks, division = struct.unpack('>HH',b[10:14])
    pos, ons, offs, controllers, max_tick = 14, [], [], [], 0
    for tr in range(ntracks):
        assert b[pos:pos+4] == b'MTrk'
        size = struct.unpack('>I',b[pos+4:pos+8])[0]
        t = b[pos+8:pos+8+size]
        p, tick = 0, 0
        while p < len(t):
            delta=0
            while True:
                z=t[p];p+=1;delta=(delta<<7)|(z&127)
                if z<128:break
            tick+=delta
            status=t[p];p+=1
            if status==255:
                p+=1
                n=0
                while True:
                    z=t[p];p+=1;n=(n<<7)|(z&127)
                    if z<128:break
                p+=n
            elif status & 240 == 192:
                p+=1
            else:
                a,v=t[p:p+2];p+=2
                ch=status&15
                kind=status&240
                if kind==144 and v:
                    ons.append((tick,ch,a,v))
                elif kind==128 or (kind==144 and not v):
                    offs.append((tick,ch,a,v))
                elif kind==176:
                    controllers.append((tick,ch,a,v))
                else:
                    raise AssertionError(f'Unexpected message {status}')
        max_tick=max(max_tick,tick)
        pos+=8+size
    assert pos==len(b)
    return dict(ons=sorted(ons),offs=sorted(offs),cc=sorted(controllers),
                duration=max_tick/(2*division),tracks=ntracks)
