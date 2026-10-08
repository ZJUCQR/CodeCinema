"""
codecinema.audio.ambience -- continuous stereo environment beds of any length.

    bed(name, seconds, seed=0, intensity=1.0) -> (2, n) float64 at dsp.SR
    catalog() -> [{"name", "description"}]

A bed is generated for exactly the requested length: continuous layers (surf, wind, room tone, rain) are shaped
noise with slow random motion, and sparse events (gulls, birds, dogs, distant firecrackers, creaks) are scattered
over the whole length, so nothing loops audibly.  Beds start and end at full level (the mix fades them) and are
normalised to -20 dBFS RMS at intensity 1; intensity scales density and loudness of the events.
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
    return y


# ------------------------------------------------------------------------------------------------ building blocks
def _nrm(x):
    return x / (dsp.peak(x) + 1e-12)


def _unit(x):
    return x / (dsp.rms(x) + 1e-12)


def _slow(n, r, fc, depth=1.0, base=1.0):
    """slowly wandering positive gain curve"""
    return np.maximum(0.0, base + depth * dsp.ctrl_noise(n, r, fc, rate=CTRL))


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


def _murmur(n, r, voices=24, level=1.0):
    """distant crowd talk: vowel-like formant noise shaped by syllable rhythms, many voices"""
    out = np.zeros((2, n))
    formants = [(700, 1200), (400, 2000), (300, 2300), (500, 900), (600, 1700)]
    for v in range(voices):
        rate = r.uniform(3.0, 6.0)
        syl = np.clip(dsp.ctrl_noise(n, r, rate, rate=CTRL) + 0.3, 0.0, None) ** 1.5
        talk = np.clip(dsp.ctrl_noise(n, r, 0.25, rate=CTRL) + 0.4, 0.0, 1.0)
        f1, f2 = formants[int(r.integers(len(formants)))]
        src = r.standard_normal(n)
        y = dsp.biquad(src, "bp", f1 * r.uniform(0.85, 1.15), 4.0) + 0.6 * dsp.biquad(src, "bp", f2 * r.uniform(0.85, 1.15), 5.0)
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
