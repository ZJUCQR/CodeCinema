"""
codecinema.audio.ambience -- continuous stereo environment beds of any length.

    bed(name, seconds, seed=0, intensity=1.0) -> (2, n) float64 at dsp.SR
    catalog() -> [{"name", "description"}]

A bed is generated for exactly the requested length: continuous layers (surf, wind, room tone, rain) are shaped
noise with slow random motion, and sparse events (gulls, birds, dogs, distant firecrackers, creaks) are scattered
over the whole length, so nothing loops audibly.  Beds play at full level from start to end (only a 2 ms ramp at
each edge; the mix fades them) and are normalised to -20 dBFS RMS at intensity 1 with peaks under -3 dBFS; intensity
scales density and loudness of the events.
"""
import numpy as np

from codecinema.audio import dsp
from codecinema.audio.dsp import SR, TWO_PI, n_of, t_axis

REF_DB = -20.0
CTRL = 100.0                    # control-curve rate (Hz)
_BEDS = {}


def _bed(name, description):
    def wrap(fn):
        _BEDS[name] = (fn, description)
        return fn
    return wrap


def catalog():
    return [{"name": k, "description": v[1]} for k, v in sorted(_BEDS.items())]


def names():
    return sorted(_BEDS)


def bed(name, seconds, seed=0, intensity=1.0):
    if name not in _BEDS:
        raise KeyError(f"Unknown ambience bed {name!r}. Known: {', '.join(names())}")
    n = max(1, n_of(seconds))
    r = dsp.rng("ambience", name, seed)
    y = _BEDS[name][0](n, r, float(intensity))
    y = dsp.as_stereo(dsp.pad_to(np.asarray(y, dtype=np.float64), n))
    y = dsp.dc_block(y, 12.0)
    for _ in range(2):
        lvl = dsp.rms(y)
        if lvl > 0:
            y *= dsp.db2lin(REF_DB) / lvl * (0.6 + 0.4 * min(1.0, intensity))
        if dsp.peak(y) > dsp.db2lin(-3.0):
            # crackles and drops have a huge crest factor: tame the clicks, not the whole bed
            y = dsp.limiter(y, -3.0, lookahead_ms=1.5, release_ms=25.0, true_peak=False)[0]
    return dsp.fade(y, 0.002, 0.002)


# ------------------------------------------------------------------------------------------------ building blocks
def _nrm(x):
    return x / (dsp.peak(x) + 1e-12)


def _unit(x):
    return x / (dsp.rms(x) + 1e-12)


def _slow(n, r, fc, depth=1.0, base=1.0):
    """slowly wandering positive gain curve"""
    return np.maximum(0.0, base + depth * dsp.ctrl_noise(n, r, fc, rate=CTRL))


def _lull(n, r, fc, depth=0.5, floor=0.35):
    """a wandering gain like _slow that never falls below floor: leaves and sand calm down, they do not switch off"""
    return floor + (1.0 - floor) * _slow(n, r, fc, depth)


def _stereo_noise(n, r, kind="pink"):
    gen = dsp.pink if kind == "pink" else (dsp.brown if kind == "brown" else (lambda m, rr: rr.standard_normal(m)))
    return np.vstack([gen(n, r), gen(n, r)])


def _events(n, r, rate, make, pan_spread=0.8, gain=(0.5, 1.0), at_least=0):
    """scatter clips made by make(r) over n samples as a Poisson process (rate per second)"""
    out = np.zeros((2, n))
    t = r.exponential(1.0 / max(rate, 1e-6)) * 0.5
    count = 0
    dur = n / SR
    while t < dur or count < at_least:
        if t >= dur:
            t = r.uniform(0, max(dur - 0.5, 0.0))
        clip = make(r)
        clip = clip if clip.ndim == 2 else dsp.pan_mono(clip, r.uniform(-pan_spread, pan_spread))
        dsp.place(out, clip, n_of(t), r.uniform(*gain))
        count += 1
        t += r.exponential(1.0 / max(rate, 1e-6))
    return out


def _far(x, lp=2500.0, wet=0.5, preset="field"):
    """push a sound into the distance: high-frequency loss and more room"""
    x = dsp.lowpass(dsp.as_stereo(x), lp, 2)
    return x + wet * dsp.convolve_reverb(x, preset, seed=17)


def _wind(n, r, strength=1.0, gust_rate=0.08, whistle=0.0, lo=120.0, hi=1600.0):
    g = _slow(n, r, gust_rate, 0.45, 1.0) ** 1.5
    fc = lo + (hi - lo) * np.clip(0.35 * g * strength, 0.0, 1.0)
    out = np.zeros((2, n))
    for ch in range(2):
        base = dsp.pink(n, r)
        y = dsp.lp_varying(base, fc, 0.7, spacing=0.5) * g
        if whistle:
            w = dsp.lp_varying(r.standard_normal(n), fc * 3.0, 0.7, spacing=0.5)
            w = dsp.bandpass(w, 500, 2500, 2) * g ** 2
            y = y + whistle * _unit(w) * 0.08
        out[ch] = y
    return out


def _surf(n, r, period=(7.0, 11.0), closeness=1.0):
    """sea surf: each wave swells, breaks and washes back; overlapping waves, decorrelated channels"""
    out = np.zeros((2, n))
    t0 = -r.uniform(0, period[1])
    dur = n / SR
    while t0 < dur:
        L = r.uniform(*period) * 1.2
        m = n_of(L)
        tt = t_axis(m)
        tc = r.uniform(0.3, 0.45) * L
        env_roar = np.where(tt < tc, (tt / tc) ** 2.0, np.exp(-(tt - tc) / (0.18 * L)))
        env_wash = np.where(tt < tc, 0.0, np.minimum(1.0, (tt - tc) / 0.4) * np.exp(-(tt - tc) / (0.32 * L)))
        wave = np.zeros((2, m))
        for ch in range(2):
            roar = dsp.lp_varying(dsp.pink(m, r), 250 + 1400 * env_roar * closeness, 0.7, spacing=0.5) * env_roar
            foam = dsp.bandpass(r.standard_normal(m), 1500, 9000, 2) * env_wash
            fizz = dsp.crackle(m, r, 600.0 * closeness, 0.5, (0.0005, 0.003), hp=2000.0) * env_wash
            wave[ch] = _unit(roar) + 0.45 * closeness * _unit(foam) + 0.25 * closeness * _unit(fizz)
        dsp.place(out, wave * r.uniform(0.6, 1.0), int(round(t0 * SR)))
        t0 += r.uniform(*period)
    bed_ = _stereo_noise(n, r, "pink")
    bed_ = dsp.lowpass(bed_, 700, 2) * 0.35
    return out + bed_


def _gull(r):
    """a distant gull: a raspy, falling 'kee-ow', sometimes in a laughing series"""
    calls = 1 if r.uniform() < 0.6 else int(r.integers(3, 6))
    pieces, t = [], 0.0
    for k in range(calls):
        d = r.uniform(0.25, 0.45) if calls == 1 else r.uniform(0.12, 0.2)
        m = n_of(d)
        tt = t_axis(m)
        f0 = r.uniform(900, 1300) * (1.0 + 0.25 * np.sin(np.pi * tt / d) - 0.3 * (tt / d))
        rasp = 1.0 + 0.4 * np.sign(np.sin(TWO_PI * 70 * tt))
        ph = dsp.phase_cycles(f0, m)
        src = sum(np.sin(TWO_PI * h * ph) / h ** 0.8 for h in range(1, 7)) * rasp
        y = dsp.bandpass(src, 1500, 4500, 2) * np.sin(np.pi * np.clip(tt / d, 0, 1)) ** 0.7
        pieces.append((t, y))
        t += d + r.uniform(0.04, 0.12)
    out = np.zeros(n_of(t + 0.1))
    for at, y in pieces:
        dsp.place(out, y, n_of(at))
    return out


def _bird(r, kind=None):
    """a small songbird phrase: chirps, whistles, trills or warbles"""
    kind = kind or ("chirp", "whistle", "trill", "warble")[int(r.integers(4))]
    f_base = r.uniform(2500, 5500)
    pieces, t = [], 0.0
    reps = int(r.integers(2, 7))
    for k in range(reps):
        if kind == "chirp":
            d = r.uniform(0.03, 0.07)
            f = np.linspace(f_base * 1.4, f_base * 0.8, n_of(d))
        elif kind == "whistle":
            d = r.uniform(0.12, 0.3)
            f = f_base * (1.0 + 0.05 * np.sin(np.linspace(0, np.pi * r.uniform(1, 3), n_of(d))))
        elif kind == "trill":
            d = r.uniform(0.25, 0.6)
            tt = t_axis(n_of(d))
            f = f_base * (1.0 + 0.18 * np.sign(np.sin(TWO_PI * r.uniform(14, 24) * tt)))
        else:
            d = r.uniform(0.15, 0.35)
            tt = t_axis(n_of(d))
            f = f_base * (1.0 + 0.12 * np.sin(TWO_PI * r.uniform(25, 45) * tt)) * np.linspace(1.1, 0.9, len(tt))
        m = len(f)
        tt = t_axis(m)
        ph = dsp.phase_cycles(f, m)
        env = np.sin(np.pi * np.clip(tt / d, 0, 1)) ** 1.2
        y = (np.sin(TWO_PI * ph) + 0.12 * np.sin(TWO_PI * 2 * ph)) * env
        pieces.append((t, y))
        t += d + r.uniform(0.03, 0.15)
        f_base *= r.uniform(0.92, 1.08)
    out = np.zeros(n_of(t + 0.05))
    for at, y in pieces:
        dsp.place(out, y, n_of(at))
    return out


def _cricket_chorus(n, r, count=6, density=1.0):
    out = np.zeros((2, n))
    for i in range(count):
        f = r.uniform(3800, 5400)
        rate = r.uniform(1.2, 2.4)
        pulses = int(r.integers(2, 5))
        y = np.zeros(n)
        tt = r.uniform(0, 0.6)
        syl = n_of(0.015)
        win = np.sin(np.pi * np.arange(syl) / syl) ** 2
        tone = np.sin(TWO_PI * f * np.arange(syl) / SR) * win
        while tt < n / SR - 0.2:
            for j in range(pulses):
                dsp.place(y, tone * r.uniform(0.7, 1.0), n_of(tt + j * 0.03))
            tt += 1.0 / (rate * density) * r.uniform(0.8, 1.25)
            if r.uniform() < 0.05:
                tt += r.uniform(1.0, 3.0)
        y = dsp.lowpass(y, 6500, 2) * r.uniform(0.3, 1.0)
        out += dsp.pan_mono(y, r.uniform(-0.9, 0.9))
    return out


def _murmur(n, r, voices=24, level=1.0, tract=1.0):
    """distant crowd talk: vowel-like formant noise shaped by syllable rhythms, many voices (tract > 1: children)"""
    out = np.zeros((2, n))
    formants = [(700, 1200), (400, 2000), (300, 2300), (500, 900), (600, 1700)]
    for v in range(voices):
        rate = r.uniform(3.0, 6.0)
        syl = np.clip(dsp.ctrl_noise(n, r, rate, rate=CTRL) + 0.3, 0.0, None) ** 1.5
        talk = np.clip(dsp.ctrl_noise(n, r, 0.25, rate=CTRL) + 0.4, 0.0, 1.0)
        f1, f2 = formants[int(r.integers(len(formants)))]
        src = r.standard_normal(n)
        y = dsp.biquad(src, "bp", f1 * tract * r.uniform(0.85, 1.15), 4.0) + \
            0.6 * dsp.biquad(src, "bp", f2 * tract * r.uniform(0.85, 1.15), 5.0)
        out += dsp.pan_mono(y * syl * talk, r.uniform(-0.9, 0.9)) * r.uniform(0.4, 1.0)
    return out * level


def _dog_bark(r):
    barks = int(r.integers(1, 4))
    out = np.zeros(n_of(0.35 * barks + 0.3))
    for k in range(barks):
        m = n_of(r.uniform(0.12, 0.2))
        tt = t_axis(m)
        f0 = r.uniform(350, 600) * (1.0 + 0.3 * np.exp(-tt / 0.03))
        src = dsp.osc_saw(f0, m) * 0.6 + r.standard_normal(m) * 0.5
        y = dsp.biquad(src, "bp", 700, 2.5) + dsp.biquad(src, "bp", 1500, 3.0) * 0.6
        y *= np.sin(np.pi * np.clip(tt / tt[-1], 0, 1)) ** 0.5 * np.exp(-tt / 0.08)
        dsp.place(out, y, n_of(k * r.uniform(0.28, 0.4)))
    return out


def _owl(r):
    out = np.zeros(n_of(1.6))
    for k, (at, d) in enumerate(((0.0, 0.35), (0.55, 0.25), (0.85, 0.5))):
        if k and r.uniform() < 0.3:
            continue
        m = n_of(d)
        tt = t_axis(m)
        f = 410 * r.uniform(0.95, 1.05) * (1.0 - 0.06 * tt / d)
        y = np.sin(TWO_PI * dsp.phase_cycles(f, m)) * np.sin(np.pi * np.clip(tt / d, 0, 1)) ** 1.5
        y += 0.05 * dsp.lowpass(r.standard_normal(m), 1200, 2) * np.sin(np.pi * np.clip(tt / d, 0, 1))
        dsp.place(out, y, n_of(at))
    return out


def _creak(r):
    d = r.uniform(0.4, 1.2)
    n = n_of(d)
    rate = r.uniform(25, 60) * (1.0 + 0.5 * dsp.ctrl_noise(n, r, 2.0, rate=CTRL))
    ph = dsp.phase_cycles(np.maximum(rate, 5.0), n, r.uniform())
    k = np.floor(ph)
    x = np.zeros(n)
    hits = np.nonzero(np.diff(k, prepend=k[0]) > 0)[0]
    x[hits] = np.exp(r.normal(0, 0.3, len(hits)))
    f = r.uniform(500, 1100)
    y = dsp.resonator_bank(x, [f, f * 2.2, f * 3.1], [0.05, 0.04, 0.03], [1.0, 0.6, 0.3])
    return y * np.sin(np.pi * np.clip(t_axis(n) / d, 0, 1))


def _distant_firecrackers(r):
    from codecinema.audio import sfx
    y = sfx.render("firecracker_string", seed=int(r.integers(1 << 30)), dur=float(r.uniform(1.5, 4.0)),
                   density=float(r.uniform(0.6, 1.2)), spread=0.4)
    return _far(y, 1800.0, 0.8)


def _whale(r):
    d = r.uniform(2.0, 4.5)
    n = n_of(d)
    tt = t_axis(n)
    f0 = r.uniform(140, 380)
    f = f0 * (1.0 + r.uniform(-0.35, 0.45) * dsp.smoothstep(tt / d)) * (1.0 + 0.01 * np.sin(TWO_PI * 5 * tt))
    ph = dsp.phase_cycles(f, n)
    y = np.sin(TWO_PI * ph) + 0.3 * np.sin(TWO_PI * 2 * ph) + 0.1 * np.sin(TWO_PI * 3 * ph)
    return y * np.sin(np.pi * np.clip(tt / d, 0, 1)) ** 1.5


def _bubble_stream(r):
    from codecinema.audio import sfx
    y = sfx.render("bubbles", seed=int(r.integers(1 << 30)), dur=float(r.uniform(0.5, 2.0)), density=float(r.uniform(0.5, 1.5)))
    return dsp.lowpass(y, 2200, 2)


def _drip(r):
    from codecinema.audio import sfx
    return sfx.render("water_drip", seed=int(r.integers(1 << 30)), pitch=float(r.uniform(0.7, 1.4)))


def _snow_fall(r):
    d = r.uniform(0.4, 1.2)
    n = n_of(d)
    tt = t_axis(n)
    thump = np.sin(TWO_PI * 70 * tt) * np.exp(-tt / 0.05) * np.clip(tt / 0.005, 0, 1)
    powder = dsp.bandpass(r.standard_normal(n), 1500, 7000, 2) * np.exp(-tt / (d * 0.4)) * np.clip(tt / 0.03, 0, 1)
    return 0.6 * _nrm(thump) + 0.5 * _nrm(powder)


# ------------------------------------------------------------------------------------------------ beds
@_bed("beach_day", "sunny beach: rolling surf, distant gulls, a light breeze")
def beach_day(n, r, k):
    surf = _surf(n, r, (7.0, 11.0), 0.9)
    breeze = _wind(n, r, 0.6, 0.06, 0.0, 200, 1400)
    gulls = _events(n, r, 0.12 * k, lambda rr: _far(_gull(rr), 3500, 0.5), 0.9, (0.3, 0.8))
    out = _unit(surf) + 0.35 * _unit(breeze)
    return out + 0.13 * _unit(gulls) if np.any(gulls) else out


@_bed("seaside_cliff_wind", "high on a sea cliff: strong gusty wind with whistles, surf far below")
def seaside_cliff_wind(n, r, k):
    wind = _wind(n, r, 1.4 * k, 0.12, 1.0, 150, 2600)
    surf = dsp.lowpass(_surf(n, r, (8.0, 13.0), 0.4), 900, 2)
    gulls = _events(n, r, 0.05 * k, lambda rr: _far(_gull(rr), 3000, 0.6), 0.9, (0.2, 0.5))
    out = _unit(wind) + 0.45 * _unit(surf)
    return out + 0.15 * _unit(gulls) if np.any(gulls) else out


@_bed("underwater", "under the sea: muffled rumble, bubbles, distant whale-like calls")
def underwater(n, r, k):
    rumble = dsp.lowpass(_stereo_noise(n, r, "brown"), 180, 2) * _slow(n, r, 0.05, 0.3)
    hum = dsp.bandpass(_stereo_noise(n, r, "pink"), 60, 400, 2) * 0.3
    bubbles = _events(n, r, 0.25 * k, _bubble_stream, 0.8, (0.3, 0.9))
    whales = _events(n, r, 0.04 * k, lambda rr: _far(_whale(rr), 900, 1.2, "hall"), 0.7, (0.4, 0.9), at_least=1 if n > SR * 20 else 0)
    out = _unit(rumble) + 0.5 * _unit(hum)
    if np.any(bubbles):
        out = out + 0.4 * _unit(bubbles)
    if np.any(whales):
        out = out + 0.35 * _unit(whales)
    return dsp.lowpass(out, 3000, 2)


@_bed("meadow_day", "sunny meadow: songbirds, insects, a light wind through grass")
def meadow_day(n, r, k):
    wind = _wind(n, r, 0.5, 0.07, 0.0, 300, 2500)
    grass = dsp.highpass(_stereo_noise(n, r, "pink"), 2500, 2) * _slow(n, r, 0.1, 0.4) * 0.3
    birds = _events(n, r, 0.6 * k, lambda rr: _far(_bird(rr), 7000, 0.3), 0.9, (0.2, 0.8))
    bees = _events(n, r, 0.03 * k, lambda rr: _bee(rr), 0.8, (0.1, 0.3))
    out = _unit(wind) + 0.4 * _unit(grass)
    out = out + 0.6 * _unit(birds) if np.any(birds) else out
    return out + 0.2 * _unit(bees) if np.any(bees) else out


def _bee(r):
    d = r.uniform(1.0, 3.0)
    n = n_of(d)
    tt = t_axis(n)
    f = r.uniform(180, 240) * (1.0 + 0.05 * dsp.ctrl_noise(n, r, 3.0))
    y = dsp.bandpass(dsp.osc_saw(f, n), 200, 2500, 2) * np.sin(np.pi * np.clip(tt / d, 0, 1))
    return dsp.pan_mono(y, np.linspace(r.uniform(-1, 0), r.uniform(0, 1), n))


@_bed("forest_day", "daytime forest: birds near and far, canopy rustle, the odd creak and woodpecker")
def forest_day(n, r, k):
    canopy = _wind(n, r, 0.7, 0.05, 0.0, 400, 3500)
    leaves = dsp.bandpass(_stereo_noise(n, r, "white"), 2000, 8000, 2) * _slow(n, r, 0.08, 0.5) * 0.15
    birds = _events(n, r, 0.45 * k, lambda rr: _far(_bird(rr), 6000, 0.6, "hall"), 0.95, (0.15, 0.8))
    creaks = _events(n, r, 0.03 * k, lambda rr: _far(_creak(rr), 3000, 0.5), 0.8, (0.1, 0.3))
    pecks = _events(n, r, 0.02 * k, _woodpecker, 0.8, (0.2, 0.4))
    out = _unit(canopy) + 0.3 * _unit(leaves)
    for layer, g in ((birds, 0.6), (creaks, 0.15), (pecks, 0.15)):
        if np.any(layer):
            out = out + g * _unit(layer)
    return out


def _woodpecker(r):
    hits = int(r.integers(8, 20))
    rate = r.uniform(14, 20)
    out = np.zeros(n_of(hits / rate + 0.2))
    f = r.uniform(900, 1500)
    for j in range(hits):
        m = n_of(0.05)
        y = dsp.modal([f, f * 2.3], [1.0, 0.4], [0.04, 0.02], m, r=r) * (1.0 - 0.4 * j / hits)
        dsp.place(out, y, n_of(j / rate))
    return _far(out, 4000, 0.6, "hall")


@_bed("night_crickets", "summer night: a chorus of crickets, a soft breeze, an owl far away")
def night_crickets(n, r, k):
    crickets = _cricket_chorus(n, r, int(4 + 5 * k), 1.0)
    crickets = crickets + 0.4 * dsp.convolve_reverb(crickets, "field", seed=5)
    breeze = _wind(n, r, 0.35, 0.05, 0.0, 150, 900)
    owls = _events(n, r, 0.02 * k, lambda rr: _far(_owl(rr), 1500, 0.9, "hall"), 0.8, (0.3, 0.6))
    out = _unit(crickets) + 0.4 * _unit(breeze)
    return out + 0.3 * _unit(owls) if np.any(owls) else out


@_bed("snow_night_village", "snowy village on a festival night: soft wind, far bustle, dogs, distant firecrackers")
def snow_night_village(n, r, k):
    wind = _wind(n, r, 0.45, 0.05, 0.3, 120, 900)
    bustle = _far(_murmur(n, r, 20, 1.0), 1200, 0.7)
    dogs = _events(n, r, 0.035 * k, lambda rr: _far(_dog_bark(rr), 1500, 0.8), 0.9, (0.3, 0.7))
    crackers = _events(n, r, 0.03 * k, _distant_firecrackers, 0.9, (0.2, 0.5), at_least=1 if n > SR * 25 else 0)
    out = _unit(wind) + 0.45 * _unit(bustle)
    for layer, g in ((dogs, 0.18), (crackers, 0.3)):
        if np.any(layer):
            out = out + g * _unit(layer)
    return out


@_bed("snow_forest_night", "snowy pine forest at night: hush, wind through pines, creaks, snow slipping off boughs")
def snow_forest_night(n, r, k):
    pines = _wind(n, r, 0.55, 0.04, 0.0, 600, 4500)
    hush = dsp.lowpass(_stereo_noise(n, r, "brown"), 200, 2) * 0.4
    creaks = _events(n, r, 0.05 * k, lambda rr: _far(_creak(rr), 2500, 0.7, "hall"), 0.9, (0.15, 0.4))
    falls = _events(n, r, 0.04 * k, lambda rr: _far(_snow_fall(rr), 4000, 0.6, "hall"), 0.9, (0.15, 0.4))
    out = _unit(pines) + 0.35 * _unit(hush)
    for layer, g in ((creaks, 0.15), (falls, 0.15)):
        if np.any(layer):
            out = out + g * _unit(layer)
    return out


@_bed("interior_warm", "a warm room: low room tone, a crackling fire, a kettle simmering now and then")
def interior_warm(n, r, k):
    room = dsp.lowpass(_stereo_noise(n, r, "brown"), 220, 2) * _slow(n, r, 0.03, 0.1)
    air = dsp.bandpass(_stereo_noise(n, r, "pink"), 300, 3000, 2) * 0.08
    fire = np.zeros((2, n))
    for ch in range(2):
        fire[ch] = dsp.crackle(n, r, 6.0 * k, 1.0, (0.0005, 0.004), hp=1200) + \
            0.5 * dsp.crackle(n, r, 0.8 * k, 0.6, (0.003, 0.012), hp=300)
    fire = dsp.lowpass(fire, 9000, 2)
    simmer = _events(n, r, 0.015 * k, lambda rr: _simmer(rr), 0.3, (0.3, 0.6))
    out = _unit(room) + 0.4 * _unit(air) + 0.5 * _unit(fire)
    return out + 0.2 * _unit(simmer) if np.any(simmer) else out


def _simmer(r):
    d = r.uniform(4.0, 9.0)
    n = n_of(d)
    tt = t_axis(n)
    env = np.sin(np.pi * np.clip(tt / d, 0, 1))
    return dsp.crackle(n, r, 80.0, 0.5, (0.002, 0.01), hp=300) * env


@_bed("festival_crowd", "a festival crowd: lively chatter, laughter, children, distant drums and firecrackers")
def festival_crowd(n, r, k):
    talk = _murmur(n, r, int(30 * max(k, 0.3)), 1.0)
    talk = talk + 0.4 * dsp.convolve_reverb(talk, "field", seed=7)
    laughs = _events(n, r, 0.25 * k, _laugh_burst, 0.9, (0.2, 0.6))
    drums = _events(n, r, 0.03 * k, _far_drums, 0.6, (0.2, 0.4))
    crackers = _events(n, r, 0.04 * k, _distant_firecrackers, 0.9, (0.3, 0.6))
    out = _unit(talk)
    for layer, g in ((laughs, 0.25), (drums, 0.2), (crackers, 0.25)):
        if np.any(layer):
            out = out + g * _unit(layer)
    return out


def _laugh_burst(r):
    d = r.uniform(0.6, 1.4)
    n = n_of(d)
    tt = t_axis(n)
    rate = r.uniform(4.5, 7.0)
    pulses = np.clip(np.sin(TWO_PI * rate * tt), 0, 1) ** 2 * np.exp(-tt / (d * 0.6))
    f0 = r.uniform(180, 380) * (1.0 - 0.15 * tt / d)
    src = dsp.osc_saw(f0, n) * 0.5 + 0.3 * r.standard_normal(n)
    y = dsp.biquad(src, "bp", r.uniform(600, 900), 3.0) + 0.6 * dsp.biquad(src, "bp", r.uniform(1100, 1800), 4.0)
    return _far(y * pulses, 3000, 0.4)


def _far_drums(r):
    from codecinema.audio import instruments
    out = np.zeros((2, n_of(3.0)))
    for j in range(int(r.integers(4, 10))):
        dsp.place(out, instruments.play("tanggu", 60, 0.2, r.uniform(0.5, 0.9), seed=j), n_of(j * 0.23))
    return _far(out, 1200, 0.8)


@_bed("rain", "steady rain: drops on many surfaces, hiss, nearby drips")
def rain(n, r, k):
    out = np.zeros((2, n))
    for ch in range(2):
        drops = dsp.crackle(n, r, 1500 * k, 0.7, (0.0008, 0.004), hp=1000)
        hiss = dsp.bandpass(dsp.pink(n, r), 600, 9000, 2)
        out[ch] = _unit(drops) + 0.8 * _unit(hiss)
    out = out * _slow(n, r, 0.05, 0.15)
    drips = _events(n, r, 0.6 * k, _drip, 0.8, (0.1, 0.4))
    return out + 0.15 * _unit(drips) if np.any(drips) else out


@_bed("storm", "a storm: heavy rain, howling gusts, thunder rolling near and far")
def storm(n, r, k):
    rain_ = rain(n, r, 1.6 * k)
    wind = _wind(n, r, 1.8 * k, 0.15, 1.0, 150, 3000)
    from codecinema.audio import sfx
    thunder = _events(n, r, 0.06 * k, lambda rr: sfx.render("thunder", seed=int(rr.integers(1 << 30)),
                                                           distance=float(rr.uniform(0.6, 2.5))), 0.6, (0.4, 1.0),
                      at_least=1 if n > SR * 15 else 0)
    out = _unit(rain_) + 0.7 * _unit(wind)
    return out + 0.8 * _unit(thunder) if np.any(thunder) else out


# ------------------------------------------------------------------------------------------------ more building blocks
def _sfx(r, name, **params):
    from codecinema.audio import sfx
    return sfx.render(name, seed=int(r.integers(1 << 30)), **params)


def _texture(r, name, n, **params):
    """a long sound-effect texture (a stream, rain on a roof ...) cut free of its own fade-in and fade-out"""
    pad = n_of(0.75)
    y = _sfx(r, name, dur=(n + 2 * pad) / SR, **params)
    return dsp.as_stereo(y)[:, pad:pad + n]


_REF = []


def _hits(n, r, rate, make, level_db, pan_spread=0.8, at_least=0, spread=6.0):
    """sparse events at a level relative to the bed: each event's loudest 100 ms (K-weighted) sits level_db
    (+- spread / 2) from the loudness of unit-RMS pink noise, the level of the bed's continuous layers"""
    if not _REF:
        _REF.append(dsp.loudness_peak(_unit(_stereo_noise(n_of(1.0), dsp.rng("ambience-ref"), "pink"))))

    def make_level(rr):
        c = make(rr)
        return c * dsp.db2lin(_REF[0] + level_db + rr.uniform(-spread / 2, spread / 2) - dsp.loudness_peak(c))
    return _events(n, r, rate, make_level, pan_spread, (1.0, 1.0), at_least)


def _layers(*pairs):
    """sum of (gain, layer); continuous layers come in unit-RMS, sound-effect events at their own catalog level"""
    out = None
    for g, x in pairs:
        if np.any(x):
            out = g * x if out is None else out + g * x
    return out


def _room(n, r, hum=0.0):
    """room tone: a low air rumble, a whisper of ventilation, an optional mains hum"""
    rumble = dsp.lowpass(_stereo_noise(n, r, "brown"), 180, 2)
    tone = _unit(rumble) + 0.5 * _unit(dsp.bandpass(_stereo_noise(n, r), 200, 2500, 2))
    if hum:
        t = t_axis(n)
        tone = tone + hum * dsp.pan_mono(np.sin(TWO_PI * 100.0 * t) + 0.3 * np.sin(TWO_PI * 200.0 * t), 0.2)
    return tone * _slow(n, r, 0.05, 0.1)


def _clink(r):
    """cutlery or a cup touching china: a few small bright pings"""
    y = np.zeros(n_of(0.6))
    for j in range(int(r.integers(1, 4))):
        f = r.uniform(2500, 6000)
        dsp.place(y, dsp.modal([f, f * r.uniform(2.3, 2.8)], [1.0, 0.3], [r.uniform(0.1, 0.35), 0.06], n_of(0.5), r=r),
                  n_of(j * r.uniform(0.05, 0.12)), r.uniform(0.5, 1.0))
    return y


def _steam(r):
    """an espresso machine's steam wand: a turbulent hiss swelling and stopping"""
    d = r.uniform(1.5, 4.0)
    n = n_of(d)
    y = dsp.bandpass(r.standard_normal(n), 1800, 8000, 2) * (1.0 + 0.4 * dsp.ctrl_noise(n, r, 6.0))
    return y * dsp.env_points([(0, 0), (0.1, 1.0), (d - 0.2, 0.8), (d, 0.0)], n, "cos")


def _scribble(r):
    """a pencil writing: short scratchy strokes"""
    d = r.uniform(0.6, 2.0)
    n = n_of(d)
    rate = r.uniform(3.0, 6.0) * (1.0 + 0.3 * dsp.ctrl_noise(n, r, 2.0))
    strokes = np.clip(np.sin(TWO_PI * dsp.phase_cycles(rate, n)), 0.0, None) ** 0.5
    return dsp.bandpass(r.standard_normal(n), 2000, 7000, 2) * strokes * np.sin(np.pi * np.clip(t_axis(n) / d, 0, 1))


def _chair(r):
    """a chair scraping on the floor: a short stick-slip groan"""
    d = r.uniform(0.25, 0.6)
    n = n_of(d)
    rate = r.uniform(70, 160) * (1.0 + 0.3 * dsp.ctrl_noise(n, r, 4.0, rate=CTRL))
    k = np.floor(dsp.phase_cycles(np.maximum(rate, 20.0), n, r.uniform()))
    x = np.zeros(n)
    x[np.nonzero(np.diff(k, prepend=k[0]) > 0)[0]] = 1.0
    f = r.uniform(300, 600)
    y = dsp.resonator_bank(x, [f, f * 2.1, f * 3.3], [0.04, 0.03, 0.02], [1.0, 0.6, 0.3])
    return y * np.sin(np.pi * np.clip(t_axis(n) / d, 0, 1)) ** 0.5


def _hawk(r):
    """a raptor's far cry: a harsh descending 'kee-eeer'"""
    d = r.uniform(0.8, 1.4)
    n = n_of(d)
    u = t_axis(n) / d
    f = r.uniform(2600, 3200) * (1.0 - 0.4 * u ** 1.5)
    ph = dsp.phase_cycles(f * (1.0 + 0.02 * np.sin(TWO_PI * 30.0 * t_axis(n))), n)
    y = np.sin(TWO_PI * ph) + 0.35 * np.sin(TWO_PI * 2 * ph) + 0.15 * r.standard_normal(n)
    return dsp.bandpass(y, 1500, 7000, 2) * np.sin(np.pi * u) ** 0.6


def _slosh(r):
    """water lapping against a hull or a pier: a low slap and a gurgling wash back"""
    d = r.uniform(0.3, 0.8)
    n = n_of(d)
    t = t_axis(n)
    slap = dsp.lowpass(r.standard_normal(n), 900, 2) * np.exp(-t / 0.05) * np.clip(t / 0.01, 0, 1)
    wash = dsp.bandpass(r.standard_normal(n), 300, 2500, 2) * np.sin(np.pi * np.clip(t / d, 0, 1)) ** 2 * 0.5
    y = slap + wash
    for _ in range(int(r.integers(1, 4))):
        dsp.place(y, _bubble_clip(r, r.uniform(300, 900)), n_of(r.uniform(0.02, d * 0.7)), r.uniform(0.2, 0.5))
    return y


def _bubble_clip(r, f0):
    from codecinema.audio import sfx
    return sfx._bubble(r, f0)


def _halyard(r):
    """a halyard slapping an aluminium mast: two or three ringing 'tinks'"""
    y = np.zeros(n_of(1.2))
    f = r.uniform(1400, 2600)
    for j in range(int(r.integers(1, 4))):
        dsp.place(y, dsp.modal([f, f * 2.7, f * 5.1], [1.0, 0.5, 0.2], [0.6, 0.3, 0.15], n_of(0.8), r=r),
                  n_of(j * r.uniform(0.12, 0.3)), r.uniform(0.5, 1.0))
    return y


def _blip(r):
    """a ship's console: a soft telemetry blip or a short run of them"""
    y = np.zeros(n_of(0.8))
    f = r.choice([880.0, 1174.7, 1318.5, 1760.0, 2349.3])
    for j in range(int(r.integers(1, 4))):
        d = r.uniform(0.04, 0.09)
        n = n_of(d)
        dsp.place(y, np.sin(TWO_PI * f * (1.0 + 0.5 * (j % 2)) * t_axis(n)) * np.sin(np.pi * t_axis(n) / d) ** 2,
                  n_of(j * 0.12))
    return y


def _hiss_door(r):
    """a pneumatic door: a sharp 'pssht' of air"""
    d = r.uniform(0.4, 0.8)
    n = n_of(d)
    t = t_axis(n)
    return dsp.bandpass(r.standard_normal(n), 1500, 9000, 2) * np.exp(-t / (d * 0.3)) * np.clip(t / 0.01, 0, 1)


def _glass_tap(n, r, rate):
    """rain drops ticking on a window pane: sharp ticks ringing the glass"""
    out = np.zeros((2, n))
    for ch in range(2):
        x = np.where(r.random(n) < rate / SR, np.exp(r.normal(0.0, 0.7, n)), 0.0)
        out[ch] = dsp.resonator_bank(x, r.uniform(2200, 6500, 5), r.uniform(0.01, 0.025, 5), r.uniform(0.4, 1.0, 5))
    return out


def _chop(r):
    """a cleaver on a chopping board: a quick run of woody thuds"""
    y = np.zeros(n_of(2.0))
    rate = r.uniform(3.0, 6.0)
    f = r.uniform(250, 400)
    for j in range(int(r.integers(3, 9))):
        hit = dsp.modal([f, f * 2.3, f * 4.1], [1.0, 0.5, 0.2], [0.06, 0.04, 0.02], n_of(0.15), r=r)
        hit[:n_of(0.003)] += 0.5 * dsp.peak(hit) * _nrm(dsp.highpass(r.standard_normal(n_of(0.003)), 2000, 2))
        dsp.place(y, hit, n_of(j / rate + r.normal(0.0, 0.01)), r.uniform(0.6, 1.0))
    return y


def _sizzle(r):
    """a wok sizzling: a burst of frying crackle"""
    d = r.uniform(1.5, 3.5)
    n = n_of(d)
    y = dsp.crackle(n, r, 900.0, 0.6, (0.0003, 0.002), hp=2500)
    y = y + 0.3 * dsp.bandpass(r.standard_normal(n), 3000, 9000, 2)
    return y * dsp.env_points([(0, 0), (0.05, 1.0), (d * 0.6, 0.7), (d, 0.0)], n, "cos")


def _vendor(r):
    """a market vendor calling out in the distance"""
    from codecinema.audio import babble
    line = ("新鲜的包子！", "热乎乎的烤红薯！", "来看看，便宜啦！", "糖葫芦——", "豆腐脑，豆浆！")[int(r.integers(5))]
    return babble.render(line, "man" if r.uniform() < 0.6 else "woman", "excited", int(r.integers(1 << 20)))


def _temple_bell(r):
    """a great bronze temple bell struck far away: a deep, beating hum that takes many seconds to fade"""
    d = 9.0
    n = n_of(d)
    f = r.uniform(70, 95)
    ratios = (0.5, 1.0, 1.003, 2.0, 2.004, 2.76, 3.35, 4.1, 5.4)
    y = dsp.modal([f * x for x in ratios], [0.5, 1.0, 0.8, 0.6, 0.5, 0.35, 0.25, 0.15, 0.08],
                  [8.0, 7.0, 7.0, 5.0, 5.0, 3.5, 2.5, 1.8, 1.2], n, r=r, attack=0.004)
    y[:n_of(0.05)] += 0.2 * dsp.peak(y) * _nrm(dsp.lowpass(r.standard_normal(n_of(0.05)), 600, 2))
    return dsp.fade(y, 0.0, 1.5)


def _chimes(r):
    """wind chimes stirred by a breeze: a few pentatonic tubes"""
    scale = (0, 2, 4, 7, 9, 12, 14)
    base = 784.0 * r.uniform(0.98, 1.02)
    y = np.zeros((2, n_of(4.5)))
    t = 0.0
    for _ in range(int(r.integers(2, 6))):
        f = base * 2.0 ** (scale[int(r.integers(len(scale)))] / 12.0)
        tube = dsp.modal([f, f * 2.76, f * 5.4], [1.0, 0.4, 0.15], [2.5, 1.2, 0.5], n_of(3.2), r=r)
        dsp.place(y, dsp.pan_mono(tube, r.uniform(-0.5, 0.5)), n_of(t), r.uniform(0.4, 1.0))
        t += r.exponential(0.25)
    return y


def _muyu_chant(r):
    """distant temple practice: a steady wooden-fish pulse"""
    from codecinema.audio import instruments
    y = np.zeros((2, n_of(9.0)))
    period = r.uniform(0.45, 0.6)
    for j in range(int(r.integers(8, 15))):
        dsp.place(y, instruments.play("muyu", 60, 0.2, 0.6 * r.uniform(0.85, 1.0), seed=j % 2), n_of(j * period))
    return y


def _log_shift(r):
    """a log settling in the fire: a soft knock and a flurry of sparks"""
    n = n_of(1.2)
    t = t_axis(n)
    knock = np.sin(TWO_PI * r.uniform(90, 140) * t) * np.exp(-t / 0.05) * np.clip(t / 0.003, 0, 1)
    sparks = dsp.crackle(n, r, 60.0, 0.8, (0.0005, 0.003), hp=1500) * np.exp(-t / 0.4)
    return 0.6 * _nrm(knock) + _nrm(sparks)


# ------------------------------------------------------------------------------------------------ more beds
@_bed("city_street", "a city street by day: traffic rolling past, a horn now and then, footsteps and passers-by")
def city_street(n, r, k):
    wash = dsp.lowpass(_stereo_noise(n, r, "pink"), 900, 2) + 0.6 * dsp.lowpass(_stereo_noise(n, r, "brown"), 200, 2)
    wash = _unit(wash * _slow(n, r, 0.08, 0.2))
    talk = _unit(_far(_murmur(n, r, 8, 1.0), 2500, 0.3))
    cars = _hits(n, r, 0.16 * k, lambda rr: _sfx(rr, "car_pass", speed=float(rr.uniform(30, 55)),
                                                  distance=float(rr.uniform(4, 15)),
                                                  direction=int(rr.choice([-1, 1]))), 4.0, 0.0)
    horns = _hits(n, r, 0.02 * k, lambda rr: _far(_sfx(rr, "car_horn", honks=int(rr.integers(1, 3)),
                                                       length=float(rr.uniform(0.15, 0.4))), 3000, 0.6), -4.0)
    steps = _hits(n, r, 0.2 * k, lambda rr: _far(_sfx(rr, "footsteps", surface="stone", steps=int(rr.integers(3, 8)),
                                                      weight=0.5), 6000, 0.3), -10.0)
    return _layers((0.8, wash), (0.35, talk), (1.0, cars), (1.0, horns), (1.0, steps))


@_bed("cafe", "a busy cafe: chatter, cups and spoons, the espresso machine hissing, a laugh now and then")
def cafe(n, r, k):
    talk = _murmur(n, r, int(14 + 8 * k), 1.0)
    talk = _unit(talk + 0.5 * dsp.convolve_reverb(talk, "room", seed=9))
    clinks = _hits(n, r, 0.9 * k, lambda rr: _far(_clink(rr), 9000, 0.25, "room"), -8.0)
    cups = _hits(n, r, 0.12 * k, lambda rr: _far(_sfx(rr, "glass_clink", material="mug"), 6000, 0.3, "room"), -8.0)
    steam = _hits(n, r, 0.025 * k, _steam, -12.0, 0.6)
    laughs = _hits(n, r, 0.06 * k, _laugh_burst, -8.0, 0.9)
    return _layers((1.0, talk), (0.4, _unit(_room(n, r))), (1.0, clinks), (1.0, cups), (1.0, steam), (1.0, laughs))


@_bed("classroom", "a classroom at work: children murmuring, pencils scratching, pages, chairs scraping")
def classroom(n, r, k):
    kids = _murmur(n, r, int(10 + 8 * k), 1.0, tract=1.25)
    kids = _unit(kids + 0.4 * dsp.convolve_reverb(kids, "room", seed=4))
    pencils = _hits(n, r, 0.4 * k, lambda rr: _far(_scribble(rr), 8000, 0.2, "room"), -16.0)
    pages = _hits(n, r, 0.06 * k, lambda rr: _far(_sfx(rr, "page_turn"), 7000, 0.2, "room"), -12.0)
    chairs = _hits(n, r, 0.05 * k, lambda rr: _far(_chair(rr), 5000, 0.3, "room"), -12.0)
    return _layers((1.0, kids), (0.4, _unit(_room(n, r))), (1.0, pencils), (1.0, pages), (1.0, chairs))


@_bed("office", "an open-plan office: ventilation hum, keyboards, mouse clicks, a phone ringing somewhere")
def office(n, r, k):
    air = _unit(_room(n, r, hum=0.05) + 0.6 * dsp.lowpass(_stereo_noise(n, r, "pink"), 600, 2))
    talk = _unit(_far(_murmur(n, r, 5, 1.0), 2000, 0.6, "room"))
    typing = _hits(n, r, 0.1 * k, lambda rr: _far(_sfx(rr, "typing", dur=float(rr.uniform(1.5, 5.0))), 6000, 0.2,
                                                  "room"), -8.0)
    clicks = _hits(n, r, 0.15 * k, lambda rr: _far(_sfx(rr, "mouse_click", clicks=int(rr.integers(1, 3))), 7000, 0.2,
                                                   "room"), -14.0)
    phones = _hits(n, r, 0.012 * k, lambda rr: _far(_sfx(rr, "phone_ring", rings=1, kind="mobile"), 2500, 0.8, "room"),
                   -10.0)
    return _layers((1.0, air), (0.3, talk), (1.0, typing), (1.0, clicks), (1.0, phones))


@_bed("train_interior", "inside a moving train: rumble and sway, the rhythmic clatter of the rail joints, air hiss")
def train_interior(n, r, k):
    t = t_axis(n)
    sway = 1.0 + 0.15 * np.sin(TWO_PI * r.uniform(0.6, 0.9) * t)
    rumble = _unit(dsp.lowpass(_stereo_noise(n, r, "brown"), 160, 2) * sway)
    clatter = _unit(dsp.lowpass(_texture(r, "train_clatter", n, speed=0.9 + 0.2 * k), 3500, 2))
    air = _unit(dsp.bandpass(_stereo_noise(n, r), 500, 4000, 2))
    return _layers((1.0, rumble), (0.9, clatter), (0.15, air))


@_bed("night_city", "a city at night: a distant wash of traffic, a far siren, a dog, an air conditioner humming")
def night_city(n, r, k):
    t = t_axis(n)
    wash = _unit(dsp.lowpass(_stereo_noise(n, r, "pink"), 500, 2) * _slow(n, r, 0.05, 0.25))
    ac = _unit(dsp.pan_mono(np.sin(TWO_PI * 98.0 * t) + 0.4 * np.sin(TWO_PI * 196.3 * t) +
                            0.3 * dsp.bandpass(r.standard_normal(n), 300, 1500, 2), r.uniform(-0.7, 0.7)))
    crickets = _unit(_cricket_chorus(n, r, 2, 0.8))
    sirens = _hits(n, r, 0.012 * k, lambda rr: _far(_sfx(rr, "siren", moving=True, dur=float(rr.uniform(5, 9)),
                                                         kind=str(rr.choice(["wail", "yelp"]))), 1500, 1.0), -6.0, 0.5,
                   at_least=1 if n > SR * 40 else 0)
    dogs = _hits(n, r, 0.02 * k, lambda rr: _far(_dog_bark(rr), 1500, 0.8), -10.0, 0.9)
    cars = _hits(n, r, 0.04 * k, lambda rr: _far(_sfx(rr, "car_pass", speed=float(rr.uniform(30, 60)),
                                                      distance=float(rr.uniform(20, 60))), 3000, 0.4), -4.0, 0.0)
    return _layers((1.0, wash), (0.15, ac), (0.1, crickets), (1.0, sirens), (1.0, dogs), (1.0, cars))


@_bed("desert_wind", "open desert: a dry wind with sand hissing over the dunes, a hawk's far cry")
def desert_wind(n, r, k):
    wind = _unit(_wind(n, r, 1.1 * k, 0.1, 0.4, 250, 2600))
    far = _unit(dsp.bandpass(_stereo_noise(n, r, "pink"), 150, 1500, 2) * _slow(n, r, 0.05, 0.15))
    gust = _lull(n, r, 0.15, 0.5)
    sand = _unit(np.vstack([dsp.bandpass(dsp.crackle(n, r, 3000.0 * gust, 0.5, (0.0002, 0.001), hp=0), 3000, 9000, 2)
                            for _ in range(2)]) * gust)
    hawks = _hits(n, r, 0.01 * k, lambda rr: _far(_hawk(rr), 4000, 0.8), -10.0)
    return _layers((1.0, wind), (0.35, far), (0.45, sand), (1.0, hawks))


@_bed("cave", "inside a cave: a deep hush, water dripping into pools, a breath of air moaning in the dark")
def cave(n, r, k):
    hush = _unit(dsp.lowpass(_stereo_noise(n, r, "brown"), 90, 2) * _slow(n, r, 0.03, 0.2))
    air = _unit(dsp.bandpass(_stereo_noise(n, r, "pink"), 150, 2500, 2) * _slow(n, r, 0.05, 0.2))
    moan = _unit(dsp.lowpass(_texture(r, "wind_howl", n, strength=0.4), 800, 2))
    drips = _hits(n, r, 0.5 * k, lambda rr: _far(_drip(rr), 6000, 1.6, "huge"), 2.0, 0.9)
    pebbles = _hits(n, r, 0.02 * k, lambda rr: _far(_sfx(rr, "step_gravel", weight=0.3), 3000, 1.2, "huge"), -8.0, 0.9)
    return _layers((1.0, hush), (0.2, air), (0.15, moan), (1.0, drips), (1.0, pebbles))


@_bed("river", "a broad river: the steady rush of water, eddies bubbling, spray along the bank")
def river(n, r, k):
    flow = _unit(_texture(r, "stream", n, intensity=1.2 + 0.6 * k))
    roar = _unit(dsp.lowpass(_stereo_noise(n, r, "brown"), 300, 2) * _slow(n, r, 0.1, 0.15))
    return _layers((1.0, flow), (0.6, roar))


@_bed("waterfall", "beside a waterfall: a thundering curtain of water, spray and churning foam")
def waterfall(n, r, k):
    return _unit(_texture(r, "waterfall", n, size=1.0 + 0.3 * k))


@_bed("harbor", "a harbor: water lapping at hulls, rigging creaking, halyards ringing on masts, gulls")
def harbor(n, r, k):
    water = _unit(dsp.lowpass(_stereo_noise(n, r, "pink"), 700, 2) * _slow(n, r, 0.12, 0.3))
    laps = _hits(n, r, 1.5 * k, _slosh, -4.0, 0.9)
    creaks = _hits(n, r, 0.06 * k, lambda rr: _far(_creak(rr), 3000, 0.4), -10.0)
    halyards = _hits(n, r, 0.1 * k, lambda rr: _far(_halyard(rr), 6000, 0.6), -8.0, 0.9)
    gulls = _hits(n, r, 0.06 * k, lambda rr: _far(_gull(rr), 3500, 0.5), -6.0, 0.9)
    horn = _hits(n, r, 0.008 * k, lambda rr: _far(_sfx(rr, "ship_horn", length=float(rr.uniform(1.5, 3.0))), 1500, 1.0),
                 -4.0, 0.6, at_least=1 if n > SR * 60 else 0)
    return _layers((1.0, water), (1.0, laps), (1.0, creaks), (1.0, halyards), (1.0, gulls), (1.0, horn))


@_bed("spaceship_interior", "aboard a spaceship: the engines' deep hum, air recyclers, console blips, a door hissing")
def spaceship_interior(n, r, k):
    t = t_axis(n)
    f = r.uniform(48, 60)
    hum = sum(a * np.sin(TWO_PI * f * h * (1.0 + 0.0008 * h) * t + r.uniform(0, 6)) for h, a in ((1, 1.0), (2, 0.5),
                                                                                                (3, 0.3), (4, 0.15)))
    hum = _unit(dsp.as_stereo(hum * (1.0 + 0.08 * np.sin(TWO_PI * 0.13 * t))))
    air = _unit(dsp.bandpass(_stereo_noise(n, r), 200, 2000, 2) * _slow(n, r, 0.06, 0.15))
    blips = _hits(n, r, 0.15 * k, lambda rr: _far(_blip(rr), 8000, 0.4, "room"), -12.0, 0.9)
    servos = _hits(n, r, 0.02 * k, lambda rr: _far(_sfx(rr, "servo", dur=float(rr.uniform(0.4, 1.2))), 5000, 0.3,
                                                   "room"), -12.0, 0.9)
    doors = _hits(n, r, 0.01 * k, lambda rr: _far(_hiss_door(rr), 7000, 0.5, "room"), -8.0, 0.9)
    return _layers((1.0, hum), (0.6, air), (1.0, blips), (1.0, servos), (1.0, doors))


@_bed("rain_on_window", "rain against a window: drops ticking on the glass, rivulets, the muffled rain outside")
def rain_on_window(n, r, k):
    outside = _unit(dsp.lowpass(_stereo_noise(n, r, "pink"), 1500, 2) * _slow(n, r, 0.05, 0.15))
    taps = _unit(_glass_tap(n, r, 50.0 * k * _slow(n, r, 0.1, 0.4)))
    trickle = _unit(np.vstack([dsp.lowpass(_bubble_run(r, n, 25.0 * k), 4000, 2) for _ in range(2)]))
    return _layers((1.0, outside), (0.25, taps), (0.2, trickle), (0.3, _unit(_room(n, r))))


def _bubble_run(r, n, rate):
    y = np.zeros(n)
    t = r.exponential(1.0 / max(rate, 1e-3))
    while t < n / SR:
        dsp.place(y, _bubble_clip(r, r.uniform(1200, 3000)), n_of(t), r.uniform(0.2, 1.0))
        t += r.exponential(1.0 / max(rate, 1e-3))
    return y


@_bed("campfire_night", "a campfire at night: crackling wood, crickets in the dark, an owl, a breeze")
def campfire_night(n, r, k):
    fire = np.zeros((2, n))
    for ch in range(2):
        fire[ch] = dsp.crackle(n, r, 8.0 * k, 1.0, (0.0005, 0.004), hp=1200) + \
            0.6 * dsp.crackle(n, r, 1.0 * k, 0.6, (0.003, 0.012), hp=300) + 0.15 * dsp.lowpass(dsp.brown(n, r), 300, 2)
    crickets = _cricket_chorus(n, r, int(4 + 4 * k), 1.0)
    crickets = _unit(crickets + 0.4 * dsp.convolve_reverb(crickets, "field", seed=5))
    owls = _hits(n, r, 0.015 * k, lambda rr: _far(_owl(rr), 1500, 0.9, "hall"), -8.0)
    logs = _hits(n, r, 0.03 * k, _log_shift, -4.0, 0.3)
    return _layers((1.0, _unit(dsp.lowpass(fire, 9000, 2))), (0.5, crickets), (0.3, _unit(_wind(n, r, 0.3, 0.05))),
                   (1.0, owls), (1.0, logs))


@_bed("chinese_market",
      "a Chinese street market: a bustling crowd, vendors calling, cleavers, a sizzling wok, bike bells")
def chinese_market(n, r, k):
    crowd = _murmur(n, r, int(20 + 12 * k), 1.0)
    crowd = _unit(crowd + 0.4 * dsp.convolve_reverb(crowd, "field", seed=6))
    vendors = _hits(n, r, 0.08 * k, lambda rr: _far(_vendor(rr), 3500, 0.5), -6.0, 0.9)
    chops = _hits(n, r, 0.08 * k, lambda rr: _far(_chop(rr), 5000, 0.3), -8.0)
    woks = _hits(n, r, 0.04 * k, lambda rr: _far(_sizzle(rr), 7000, 0.3), -10.0)
    bells = _hits(n, r, 0.05 * k, lambda rr: _far(_sfx(rr, "bicycle_bell", rings=int(rr.integers(1, 3))), 5000, 0.4),
                  -8.0, 0.9)
    bowls = _hits(n, r, 0.15 * k, lambda rr: _far(_sfx(rr, "bowl_clink", pitch=float(rr.uniform(0.85, 1.2))), 7000,
                                                  0.2), -12.0, 0.9)
    return _layers((1.0, crowd), (1.0, vendors), (1.0, chops), (1.0, woks), (1.0, bells), (1.0, bowls))


@_bed("temple_courtyard", "a temple courtyard: a soft breeze, wind chimes, a great bell far away, birds, a wooden fish")
def temple_courtyard(n, r, k):
    breeze = _unit(_wind(n, r, 0.4, 0.06, 0.0, 250, 1800))
    leaves = _unit(dsp.bandpass(_stereo_noise(n, r), 2000, 7000, 2) * _lull(n, r, 0.08, 0.5))
    chimes = _hits(n, r, 0.1 * k, lambda rr: _far(_chimes(rr), 9000, 0.4, "hall"), -2.0, 0.0)
    bell = _hits(n, r, 0.012 * k, lambda rr: _far(_temple_bell(rr), 2500, 0.6, "temple"), 0.0, 0.4,
                 at_least=1 if n > SR * 30 else 0)
    birds = _hits(n, r, 0.15 * k, lambda rr: _far(_bird(rr), 6000, 0.5, "hall"), -8.0, 0.9)
    muyu = _hits(n, r, 0.01 * k, lambda rr: _far(_muyu_chant(rr), 3000, 0.8, "temple"), -8.0, 0.0)
    return _layers((1.0, breeze), (0.2, leaves), (1.0, chimes), (1.0, bell), (1.0, birds), (1.0, muyu))


@_bed("summer_countryside", "a summer afternoon in the country: cicadas shrilling, birds, a breeze in the grass, a far "
      "farm")
def summer_countryside(n, r, k):
    breeze = _unit(_wind(n, r, 0.5, 0.07, 0.0, 300, 2500))
    grass = _unit(dsp.highpass(_stereo_noise(n, r), 2500, 2) * _lull(n, r, 0.1, 0.4))
    cicadas = _hits(n, r, 0.25 * k, lambda rr: _far(_sfx(rr, "cicada", dur=float(rr.uniform(3.0, 8.0))), 9000, 0.3),
                    0.0, 0.0, at_least=2)
    birds = _hits(n, r, 0.3 * k, lambda rr: _far(_bird(rr), 7000, 0.3), -6.0, 0.9)
    bees = _hits(n, r, 0.02 * k, lambda rr: _far(_sfx(rr, "insect_buzz", kind="bee", dur=float(rr.uniform(2, 4))),
                                                 8000, 0.1), -6.0, 0.0)
    farm = _hits(n, r, 0.01 * k, lambda rr: _far(_sfx(rr, str(rr.choice(["cow_moo", "rooster_crow", "sheep_bleat"]))),
                                                 2000, 0.8), -12.0, 0.7)
    return _layers((1.0, breeze), (0.3, grass), (1.0, cicadas), (1.0, birds), (1.0, bees), (1.0, farm))


@_bed("winter_wind", "a winter gale: cold wind howling through gaps, blowing snow hissing, trees creaking")
def winter_wind(n, r, k):
    howl = _unit(_texture(r, "wind_howl", n, strength=0.8 + 0.4 * k))
    gale = _unit(_wind(n, r, 1.2 * k, 0.1, 0.6, 150, 2200))
    far = _unit(dsp.bandpass(_stereo_noise(n, r, "pink"), 150, 1800, 2) * _slow(n, r, 0.05, 0.15))
    gust = _lull(n, r, 0.12, 0.5)
    snow = _unit(np.vstack([dsp.bandpass(dsp.crackle(n, r, 2500.0 * gust, 0.4, (0.0002, 0.001), hp=0), 2500, 8000, 2)
                            for _ in range(2)]) * gust)
    creaks = _hits(n, r, 0.04 * k, lambda rr: _far(_creak(rr), 2500, 0.6), -10.0, 0.9)
    return _layers((0.8, howl), (1.0, gale), (0.35, far), (0.3, snow), (1.0, creaks))
