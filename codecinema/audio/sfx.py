"""
codecinema.audio.sfx -- procedural cartoon and Foley sounds.

    render(name, seed=0, **params) -> float64 audio at dsp.SR (mono (n,) or stereo (2, n)), starting at sample 0
    catalog() -> [{"name", "description", "params": {name: default}, "stereo": bool}]
    names()

Every sound is synthesized from noise, modal resonators, chirps and Karplus-Strong strings, deterministic for a
seed, and loudness-matched (the loudest 100 ms sits at -14 LUFS, K-weighted; peaks at most -1 dBFS) so a mix sets
levels with plain gains.  Impacts start on their first sample; gestures such as whooshes peak part-way through (`peak` param).
"""
import numpy as np

from codecinema.audio import dsp
from codecinema.audio.dsp import SR, TWO_PI, n_of, t_axis

REF_LU = -14.0                  # loudest 100 ms of every sound (K-weighted LUFS scale)
_REGISTRY = {}


def sound(name, description, stereo=False, **defaults):
    """register a generator f(r, **params) under `name`"""
    def wrap(fn):
        _REGISTRY[name] = (fn, description, defaults, stereo)
        return fn
    return wrap


def names():
    return sorted(_REGISTRY)


def catalog():
    return [{"name": k, "description": v[1], "params": dict(v[2]), "stereo": v[3]} for k, v in sorted(_REGISTRY.items())]


def render(name, seed=0, **params):
    if name not in _REGISTRY:
        raise KeyError(f"Unknown sound effect {name!r}. Known: {', '.join(names())}")
    fn, _, defaults, _ = _REGISTRY[name]
    kw = {**defaults, **params}
    r = dsp.rng("sfx", name, seed, tuple(sorted((k, str(v)) for k, v in kw.items())))
    return _finish(fn(r, **kw))


def _finish(y):
    """loudness-match a sound: its loudest 100 ms sits at REF_LU (K-weighted), sample peaks at most -1 dBFS (a
    fast limiter takes up to 8 dB off the clicks of crackles rather than turning the whole sound down)"""
    y = np.asarray(y, dtype=np.float64)
    y = dsp.dc_block(y, 15.0)
    y = dsp.fade(y, 0.0005, min(0.02, y.shape[-1] / SR * 0.1))
    y = y * dsp.db2lin(REF_LU - dsp.loudness_peak(y))
    ceiling = dsp.db2lin(-1.0)
    pk = dsp.peak(y)
    if pk > ceiling * dsp.db2lin(8.0):
        y = y * (ceiling * dsp.db2lin(8.0) / pk)
    if dsp.peak(y) > ceiling:
        lim = dsp.limiter(dsp.as_stereo(y), -1.0, lookahead_ms=1.5, release_ms=40.0, true_peak=False)[0]
        y = lim if y.ndim == 2 else lim[0]
    return y


# ------------------------------------------------------------------------------------------------ helpers
def _nrm(x):
    return x / (dsp.peak(x) + 1e-12)


def _dec(n, tau, att=0.0005):
    t = t_axis(n)
    e = np.exp(-t / max(tau, 1e-5))
    return e * np.clip(t / att, 0.0, 1.0) if att > 0 else e


def _burst(r, n, lo, hi, tau, att=0.0005, order=2):
    return dsp.bandpass(r.standard_normal(n), lo, min(hi, dsp.NYQ * 0.95), order) * _dec(n, tau, att)


def _chirp(f0, f1, n, curve=1.0):
    u = np.linspace(0.0, 1.0, n) ** curve
    return np.sin(TWO_PI * dsp.phase_cycles(f0 * (f1 / f0) ** u, n))


def _place(buf, clip, t, gain=1.0):
    dsp.place(buf, clip, n_of(t), gain)


def _stereo(x, pan=0.0, width=0.0, r=None):
    if x.ndim == 2:
        return dsp.pan_stereo(x, pan, 1.0 + width)
    y = dsp.pan_mono(x, pan)
    if width > 0 and r is not None:
        d = n_of(0.011)
        side = np.concatenate([np.zeros(d), x[:-d]]) * width * 0.4
        y = y + np.vstack([side, -side])
    return y


def _space(x, preset="field", wet=0.25, seed=3):
    x = dsp.as_stereo(x)
    tail = dsp.reverb_tail_len(preset)
    y = np.pad(x, ((0, 0), (0, tail)))
    return y + wet * dsp.convolve_reverb(y, preset, seed=seed)


def _env(points, n, curve="cos"):
    return dsp.env_points(points, n, curve)


def _bubble(r, f0, dur=None, rise=None, amp=1.0):
    """one bubble: a damped sine whose pitch rises as it nears the surface (Minnaert resonance)"""
    dur = dur or float(np.clip(18.0 / f0, 0.012, 0.08))
    n = n_of(dur)
    t = t_axis(n)
    rise = rise if rise is not None else r.uniform(0.6, 1.6)
    f = f0 * (1.0 + rise * t / dur)
    return amp * np.sin(TWO_PI * dsp.phase_cycles(f, n)) * np.exp(-t / (dur * 0.3)) * np.clip(t / 0.0015, 0, 1)


def _modal_hit(r, freqs, amps, t60s, dur, noise=(1500, 6000, 0.3, 0.003), drift=None):
    n = n_of(dur)
    y = dsp.modal(np.asarray(freqs, float), amps, t60s, n, r=r, fdrift=drift)
    y = _nrm(y)
    lo, hi, lvl, tau = noise
    k = n_of(min(dur, 0.04))
    y[:k] += lvl * _nrm(_burst(r, k, lo, hi, tau))
    return y


def _grains(r, n, rate, lo, hi, dmin=0.0004, dmax=0.003, sigma=0.6):
    """Poisson clicks (crunch, crackle, rustle) band-limited to [lo, hi]"""
    g = dsp.crackle(n, r, rate, amp_sigma=sigma, dur_range=(dmin, dmax), hp=0)
    return dsp.bandpass(g, lo, hi, 2)


def _thump(r, f0=90.0, dur=0.25, tau=0.06, drop=0.5, noise=0.3):
    n = n_of(dur)
    t = t_axis(n)
    f = f0 * (1.0 + drop * np.exp(-t / 0.02))
    y = np.sin(TWO_PI * dsp.phase_cycles(f, n)) * _dec(n, tau, 0.002)
    y += noise * _nrm(dsp.lowpass(r.standard_normal(n), 300, 2)) * _dec(n, tau * 0.5, 0.001)
    return y


def _whoosh_core(r, dur, peak, f_lo, f_hi, q=1.6, whistle=0.0, rise=2.0, stereo_move=0.6):
    """air rushing past: noise through a band-pass sweeping up toward the closest point and down after, swelling
    amplitude, a faint pitched whistle, the source moving across the stereo field"""
    n = n_of(dur)
    t = t_axis(n)
    u = t / max(dur, 1e-3)
    pk = peak / max(dur, 1e-3)
    shape = np.where(u < pk, (u / pk) ** rise, np.exp(-(u - pk) / max(1e-3, (1 - pk) * 0.35)))
    fc = f_lo * (f_hi / f_lo) ** np.clip(shape, 0, 1)
    noise = r.standard_normal(n)
    y = dsp.tv_biquad(noise, "bp", fc, q, block=256)
    y += 0.5 * dsp.tv_biquad(dsp.pink(n, r), "lp", fc * 1.6, 0.7, block=256)
    if whistle:
        y += whistle * _nrm(dsp.tv_biquad(noise, "bp", fc * 1.9, 12.0, block=256))
    y = y * shape
    pan = stereo_move * np.clip((u - pk) * 2.0, -1, 1)
    return dsp.pan_mono(_nrm(y), pan)


# ================================================================================================ movement / impacts
@sound("whoosh", "air rushing past -- a quick movement (size 0.3 small .. 2 big)", True, size=1.0, dur=None, peak=None,
       brightness=0.5)
def whoosh(r, size, dur, peak, brightness):
    dur = dur or 0.3 + 0.35 * size
    peak = peak if peak is not None else dur * 0.45
    lo = 250.0 / size ** 0.5
    hi = (1500.0 + 4000.0 * brightness) / size ** 0.3
    return _whoosh_core(r, dur, peak, lo, hi, q=1.3 + 0.6 * brightness, whistle=0.08 * brightness, rise=2.2)


@sound("swish", "a thin, fast swish (stick, tail, flipper)", True, dur=0.22, brightness=0.7)
def swish(r, dur, brightness):
    return _whoosh_core(r, dur, dur * 0.55, 1200.0, 3500.0 + 4000.0 * brightness, q=2.2, whistle=0.15, rise=3.0,
                        stereo_move=0.4)


@sound("pop", "a cork / bubble pop", pitch=1.0)
def pop(r, pitch):
    n = n_of(0.12)
    t = t_axis(n)
    y = _chirp(420 * pitch, 1500 * pitch, n, 0.5) * _dec(n, 0.018, 0.0005)
    y += 0.6 * _burst(r, n, 1500, 7000, 0.002)
    y += 0.3 * np.sin(TWO_PI * 180 * pitch * t) * _dec(n, 0.01)
    return y


@sound("boing", "cartoon spring 'boing' (pitch 0.5 .. 2)", pitch=1.0, dur=0.9)
def boing(r, pitch, dur):
    n = n_of(dur)
    t = t_axis(n)
    f0 = 170.0 * pitch
    wob = 1.0 + 0.55 * np.exp(-t / 0.07) + 0.09 * np.exp(-t / 0.35) * np.sin(TWO_PI * dsp.phase_cycles(9.0, n))
    ph = dsp.phase_cycles(f0 * wob, n)
    y = np.sin(TWO_PI * ph + 1.2 * np.exp(-t / 0.2) * np.sin(TWO_PI * 2.0 * ph))
    y = y * _dec(n, dur * 0.28, 0.002)
    y += 0.25 * _thump(r, 70 * pitch, dur, 0.05, 0.3, 0.1)[:n]
    return dsp.fade(y, 0.0, dur * 0.2)


def _slide(r, f0, f1, dur, vib_end=True):
    n = n_of(dur)
    t = t_axis(n)
    u = t / dur
    f = f0 * (f1 / f0) ** dsp.smoothstep(u * 1.1)
    if vib_end:
        f = f * (1.0 + 0.012 * dsp.smoothstep((u - 0.75) / 0.2) * np.sin(TWO_PI * 6.5 * t))
    ph = dsp.phase_cycles(f, n)
    y = np.sin(TWO_PI * ph) + 0.06 * np.sin(TWO_PI * 2 * ph) + 0.03 * np.sin(TWO_PI * 3 * ph)
    breath = dsp.bandpass(r.standard_normal(n), 1500, 6000, 2) * 0.05
    env = _env([(0, 0), (0.03, 1.0), (dur * 0.85, 0.9), (dur, 0.0)], n)
    return (y + breath) * env


@sound("slide_whistle_up", "slide whistle gliding up", dur=0.7, pitch=1.0)
def slide_whistle_up(r, dur, pitch):
    return _slide(r, 520 * pitch, 1900 * pitch, dur)


@sound("slide_whistle_down", "slide whistle gliding down", dur=0.7, pitch=1.0)
def slide_whistle_down(r, dur, pitch):
    return _slide(r, 1900 * pitch, 480 * pitch, dur)


@sound("bonk", "hollow cartoon head bonk", pitch=1.0)
def bonk(r, pitch):
    n = n_of(0.45)
    t = t_axis(n)
    drift = 1.0 + 0.18 * np.exp(-t / 0.03)
    y = _modal_hit(r, np.array([520, 1230, 2050]) * pitch, [1.0, 0.45, 0.2], [0.28, 0.15, 0.08], 0.45,
                   noise=(800, 5000, 0.5, 0.003), drift=drift)
    y += 0.5 * _thump(r, 110 * pitch, 0.45, 0.05, 0.4, 0.2)
    return y


@sound("thud", "body or heavy object falling on the ground", weight=1.0, surface="ground")
def thud(r, weight, surface):
    dur = 0.35 + 0.25 * weight
    n = n_of(dur)
    y = _thump(r, 75.0 / weight ** 0.3, dur, 0.06 + 0.04 * weight, 0.6, 0.5)
    y += 0.25 * _burst(r, n, 300, 2500, 0.012)
    if surface == "wood":
        y += 0.4 * _modal_hit(r, [180, 320, 470], [1.0, 0.6, 0.3], [0.2, 0.15, 0.1], dur)
    return y


@sound("splat", "wet splat (pie, mud, snowball)", size=1.0)
def splat(r, size):
    dur = 0.4 + 0.2 * size
    n = n_of(dur)
    t = t_axis(n)
    body = r.standard_normal(n) * _dec(n, 0.05 * size, 0.001)
    fc = 1800.0 * np.exp(-t / 0.08) + 350.0
    y = dsp.tv_biquad(body, "bp", fc, 3.0, block=128)
    y = _nrm(y) + 0.4 * _burst(r, n, 2000, 8000, 0.01)
    drops = _grains(r, n, 60.0 * size, 1500, 6000, 0.002, 0.006) * _dec(n, 0.12)
    y += 0.3 * _nrm(drops)
    y += 0.4 * _thump(r, 120, dur, 0.04, 0.3, 0.2)[:n]
    return y


@sound("belly_flop_sand", "flat landing on sand: thump and a spray of grains", weight=1.0)
def belly_flop_sand(r, weight):
    dur = 0.7
    n = n_of(dur)
    y = _thump(r, 80.0 / weight ** 0.3, dur, 0.07, 0.4, 0.6)
    spray = _grains(r, n, 900.0, 2500, 9000, 0.0003, 0.002) * _env([(0, 0), (0.01, 1.0), (0.12, 0.6), (dur, 0)], n)
    hiss = dsp.bandpass(r.standard_normal(n), 2000, 8000, 2) * _dec(n, 0.12, 0.005)
    return _nrm(y) + 0.35 * _nrm(spray) + 0.2 * _nrm(hiss)


def _splash(r, size, dur):
    n = n_of(dur)
    out = np.zeros((2, n))
    slap = _burst(r, n, 300, 6000, 0.03 * size, 0.002) + 0.6 * _burst(r, n, 2000, 10000, 0.08 * size, 0.003)
    out += _stereo(_nrm(slap), 0.0)
    count = int(25 * size + 10)
    for _ in range(count):
        f0 = r.uniform(500, 3500) / size ** 0.3
        b = _bubble(r, f0, amp=r.uniform(0.2, 0.7))
        _place(out, dsp.pan_mono(b, r.uniform(-0.5, 0.5)), r.uniform(0.0, 0.25 * size))
    back = _grains(r, n, 300.0 * size, 1500, 9000, 0.001, 0.006)
    back = back * _env([(0, 0), (0.08 * size, 0.0), (0.2 * size, 1.0), (dur, 0.0)], n)
    out += np.vstack([back, np.roll(back, n_of(0.007))]) * 0.3 / (dsp.peak(back) + 1e-9)
    body = dsp.lowpass(r.standard_normal(n), 900, 2) * _env([(0, 0), (0.01, 1), (0.3 * size, 0.3), (dur, 0)], n)
    out += _stereo(0.3 * _nrm(body), 0.0)
    return out


@sound("splash_small", "small splash (a hop into a puddle, a fish)", True, size=0.6)
def splash_small(r, size):
    return _splash(r, size, 0.6 + 0.4 * size)


@sound("splash_big", "big splash (a fall into the sea)", True, size=1.6)
def splash_big(r, size):
    return _splash(r, size, 1.2 + 0.5 * size)


@sound("dive", "a clean dive: plunge, then the bubble trail", True, size=1.0)
def dive(r, size):
    dur = 1.6
    n = n_of(dur)
    out = np.zeros((2, n))
    k = n_of(0.25)
    plunk = _chirp(380, 950, k, 0.6) * _dec(k, 0.06, 0.002)
    out[:, :k] += 0.7 * dsp.pan_mono(plunk, 0.0)
    out[:, :k] += 0.4 * _stereo(_nrm(_burst(r, k, 800, 7000, 0.02)), 0.0)
    for _ in range(int(40 * size)):
        b = _bubble(r, r.uniform(700, 2500), amp=r.uniform(0.15, 0.5))
        _place(out, dsp.pan_mono(dsp.lowpass(b, 2500, 2), r.uniform(-0.4, 0.4)), 0.08 + r.exponential(0.25))
    rumble = dsp.lowpass(r.standard_normal(n), 250, 2) * _env([(0, 0), (0.05, 1), (dur, 0)], n)
    out += 0.25 * _stereo(_nrm(rumble), 0.0)
    return out


@sound("bubbles", "a stream of bubbles", True, dur=1.5, density=1.0, size=1.0)
def bubbles(r, dur, density, size):
    n = n_of(dur + 0.1)
    out = np.zeros((2, n))
    t = 0.0
    while t < dur:
        b = _bubble(r, r.uniform(600, 2400) / size, amp=r.uniform(0.3, 1.0))
        _place(out, dsp.pan_mono(b, r.uniform(-0.6, 0.6)), t)
        t += r.exponential(1.0 / (18.0 * density))
    return dsp.lowpass(out, 6000, 2)


@sound("water_drip", "a single water drop", pitch=1.0)
def water_drip(r, pitch):
    n = n_of(0.25)
    y = 0.8 * _bubble(r, 1100 * pitch, 0.06, rise=1.2)
    y = np.pad(y, (0, n - len(y)))
    y += 0.15 * _burst(r, n, 3000, 9000, 0.002)
    return _space(y, "field", 0.15)


# ================================================================================================ footsteps
_SURFACES = ("grass", "sand", "snow", "wood", "stone", "wet_rock")


def _step(r, surface, weight=0.6, toe_delay=None):
    dur = 0.32
    n = n_of(dur)
    y = np.zeros(n)
    toe_delay = toe_delay if toe_delay is not None else r.uniform(0.035, 0.07)
    for k, (at, g) in enumerate(((0.0, 1.0), (toe_delay, 0.6))):
        m = n - n_of(at)
        if surface == "grass":
            hit = 0.5 * _thump(r, 90, m / SR, 0.03, 0.3, 0.6) + _grains(r, m, 1600, 1800, 7000) * _dec(m, 0.05)
        elif surface == "sand":
            hit = 0.6 * _thump(r, 80, m / SR, 0.035, 0.3, 0.8) + 1.2 * _grains(r, m, 2500, 2500, 9000, 0.0003, 0.0015) \
                * _dec(m, 0.07, 0.004)
        elif surface == "snow":
            crunch = _grains(r, m, 900, 700, 5000, 0.002, 0.008, 0.9) * _env([(0, 0), (0.01, 1), (0.09, 0.8), (0.16, 0),
                                                                              (m / SR + 0.1, 0)], m)
            squeak = dsp.bandpass(_grains(r, m, 300, 1200, 3500, 0.003, 0.01), 1500, 3000, 2) * _dec(m, 0.06)
            hit = 0.4 * _thump(r, 70, m / SR, 0.04, 0.2, 0.6) + crunch + 0.4 * squeak
        elif surface == "wood":
            hit = _modal_hit(r, np.array([140, 310, 520, 860]) * r.uniform(0.9, 1.1), [1.0, 0.7, 0.4, 0.2],
                             [0.12, 0.08, 0.06, 0.04], m / SR, noise=(1500, 6000, 0.4, 0.002))
            hit += 0.5 * _thump(r, 95, m / SR, 0.03, 0.4, 0.3)
        elif surface in ("stone", "wet_rock"):
            hit = 0.6 * _burst(r, m, 1500, 9000, 0.004) + 0.4 * _thump(r, 110, m / SR, 0.02, 0.5, 0.4)
            hit += 0.2 * _grains(r, m, 400, 3000, 9000) * _dec(m, 0.03)
            if surface == "wet_rock":
                sq = dsp.tv_biquad(r.standard_normal(m) * _dec(m, 0.05, 0.003), "bp",
                                   1600 * np.exp(-t_axis(m) / 0.06) + 500, 4.0, block=128)
                hit += 0.6 * _nrm(sq)
                for _ in range(3):
                    hit += 0.2 * np.pad(_bubble(r, r.uniform(900, 2200), amp=0.6), (0, m))[:m]
        else:
            raise ValueError(f"Unknown surface {surface!r}; use one of {', '.join(_SURFACES)}")
        y[n_of(at):] += g * hit[:m] / (dsp.peak(hit) + 1e-9)
    y *= 0.4 + 0.6 * weight
    return dsp.lowpass(y, 6000 + 6000 * weight, 2) if weight < 0.4 else y


for _s in _SURFACES:
    def _make(surface):
        def f(r, weight):
            return _step(r, surface, weight)
        return f
    sound(f"step_{_s}", f"footstep on {_s.replace('_', ' ')} (heel and toe)", weight=0.6)(_make(_s))


@sound("waddle", "penguin waddle: a soft flat pat of a webbed foot", surface="rock", weight=0.5)
def waddle(r, surface, weight):
    n = n_of(0.2)
    y = 0.7 * _thump(r, 140, 0.2, 0.025, 0.3, 0.7)
    slap = _burst(r, n, 600, 4000, 0.008, 0.001)
    y = _nrm(y) + 0.6 * _nrm(slap)
    if surface in ("sand", "snow"):
        y += 0.5 * _nrm(_grains(r, n, 1500, 2000, 8000, 0.0003, 0.0015) * _dec(n, 0.04))
    if surface in ("wet_rock", "water"):
        y += 0.4 * np.pad(_bubble(r, r.uniform(1000, 2000), amp=0.7), (0, n))[:n]
    return y * (0.5 + 0.5 * weight)


@sound("creature_step", "light padded creature step", weight=0.4, surface="ground")
def creature_step(r, weight, surface):
    n = n_of(0.18)
    y = _thump(r, 70 + 60 * (1 - weight), 0.18, 0.03, 0.2, 0.9)
    y = _nrm(y) + 0.15 * _nrm(_grains(r, n, 600, 1500, 6000) * _dec(n, 0.03))
    if surface == "snow":
        y += 0.4 * _nrm(_grains(r, n, 700, 700, 4000, 0.002, 0.006) * _dec(n, 0.06))
    return y


@sound("cloth_rustle", "clothing or fur moving with a gesture", intensity=0.6, dur=0.35)
def cloth_rustle(r, intensity, dur):
    n = n_of(dur)
    env = _env([(0, 0), (dur * 0.25, 1.0), (dur, 0)], n) * (1.0 + 0.3 * dsp.ctrl_noise(n, r, 12.0))
    y = dsp.bandpass(r.standard_normal(n), 300, 3500, 2) + 0.4 * _grains(r, n, 300 * intensity, 1500, 6000)
    return y * np.maximum(env, 0) * (0.5 + 0.5 * intensity)


@sound("pat", "a soft pat (hand on a back, flipper on a belly)", weight=0.5)
def pat(r, weight):
    n = n_of(0.15)
    y = _burst(r, n, 400, 3500, 0.012, 0.001) + 0.6 * _thump(r, 150, 0.15, 0.02, 0.2, 0.5)
    return y * (0.5 + 0.5 * weight)


@sound("slide_friction", "sliding on a smooth surface (ice, snow, wet rock)", dur=1.0, surface="ice")
def slide_friction(r, dur, surface):
    n = n_of(dur)
    env = _env([(0, 0), (0.06, 1.0), (dur * 0.7, 0.8), (dur, 0)], n) * (1.0 + 0.2 * dsp.ctrl_noise(n, r, 4.0))
    lo, hi = {"ice": (1500, 8000), "snow": (600, 5000), "sand": (1500, 9000)}.get(surface, (800, 6000))
    y = dsp.bandpass(r.standard_normal(n), lo, hi, 2) + 0.3 * _grains(r, n, 500, lo, hi)
    if surface == "ice":
        y += 0.2 * _creak(r, dur, 60, 160, (1800, 3600))[:n]
    return y * np.maximum(env, 0)


# ================================================================================================ weather / nature
@sound("wind_gust", "a gust of wind with a faint whistle", True, dur=2.5, strength=1.0)
def wind_gust(r, dur, strength):
    n = n_of(dur)
    t = t_axis(n)
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.5 * (1.0 + 0.25 * dsp.ctrl_noise(n, r, 1.5))
    out = np.zeros((2, n))
    for ch in range(2):
        base = dsp.pink(n, r)
        fc = 300.0 + 1500.0 * strength * env
        y = dsp.tv_biquad(base, "lp", fc, 0.8, block=256)
        whistle = dsp.tv_biquad(r.standard_normal(n), "bp", 700 + 900 * env + 120 * ch, 18.0, block=256)
        out[ch] = (_nrm(y) + 0.15 * strength * _nrm(whistle)) * env
    return out


@sound("rustle_leaves", "leaves rustling", True, dur=1.0, intensity=1.0)
def rustle_leaves(r, dur, intensity):
    n = n_of(dur)
    env = _env([(0, 0), (dur * 0.2, 1), (dur * 0.7, 0.8), (dur, 0)], n) * (1 + 0.4 * dsp.ctrl_noise(n, r, 6.0))
    out = np.zeros((2, n))
    for ch in range(2):
        g = _grains(r, n, 1800 * intensity, 1500, 9000, 0.0005, 0.004, 0.8)
        out[ch] = _nrm(g + 0.2 * dsp.bandpass(r.standard_normal(n), 2000, 7000, 2)) * np.maximum(env, 0)
    return out


@sound("rustle_bush", "a bush shaken: twigs and leaves", True, dur=1.2, intensity=1.0)
def rustle_bush(r, dur, intensity):
    n = n_of(dur)
    leaves = rustle_leaves(r, dur, intensity)
    twigs = _grains(r, n, 120 * intensity, 600, 4000, 0.002, 0.008, 0.9) * _env([(0, 0), (0.1, 1), (dur, 0)], n)
    swish = dsp.bandpass(dsp.pink(n, r), 300, 1500, 2) * _env([(0, 0), (dur * 0.3, 1), (dur, 0)], n)
    return leaves + _stereo(0.5 * _nrm(twigs) + 0.3 * _nrm(swish), 0.0, 0.5, r)


def _flaps(r, dur, rate, lo, hi, tau, snap=0.0):
    n = n_of(dur)
    y = np.zeros(n)
    t = 0.0
    while t < dur - 0.02:
        m = n_of(min(0.25, 1.0 / rate * 1.2))
        f = dsp.bandpass(r.standard_normal(m), lo, hi, 2) * _env([(0, 0), (0.25 / rate, 1.0), (m / SR, 0)], m) * \
            r.uniform(0.7, 1.0)
        if snap:
            k = n_of(0.004)
            f[:k] += snap * _nrm(dsp.highpass(r.standard_normal(k), 2000, 2))
        _place(y, f, t)
        t += 1.0 / rate * r.uniform(0.85, 1.15)
    return y


@sound("cloth_flutter", "cloth fluttering in the wind", True, dur=1.0, rate=12.0)
def cloth_flutter(r, dur, rate):
    y = _flaps(r, dur, rate, 400, 3000, 0.02)
    return _stereo(y, 0.0, 0.6, r)


@sound("kite_flap", "kite fabric flapping and snapping taut", True, dur=1.2, rate=4.0)
def kite_flap(r, dur, rate):
    y = _flaps(r, dur, rate, 250, 2200, 0.05, snap=0.5)
    return _stereo(y, 0.0, 0.5, r)


@sound("wing_flap_small", "small bird taking off: quick wing flutter", True, dur=0.6, rate=14.0)
def wing_flap_small(r, dur, rate):
    y = _flaps(r, dur, rate, 900, 5000, 0.015)
    return _stereo(y * _env([(0, 0.6), (dur * 0.3, 1.0), (dur, 0.3)], len(y)), 0.0, 0.3, r)


@sound("wing_flap_big", "big gull wing beats", True, dur=1.4, rate=3.2)
def wing_flap_big(r, dur, rate):
    y = _flaps(r, dur, rate, 180, 1800, 0.08)
    return _stereo(y, 0.0, 0.5, r)


@sound("wave_crash", "an ocean wave: rising roar, crash and foamy wash", True, size=1.0)
def wave_crash(r, size):
    dur = 3.5 + 1.5 * size
    n = n_of(dur)
    t = t_axis(n)
    t_c = 1.0 + 0.4 * size
    out = np.zeros((2, n))
    for ch in range(2):
        roar_env = np.where(t < t_c, (t / t_c) ** 2.5, np.exp(-(t - t_c) / (0.5 * size)))
        roar = dsp.tv_biquad(dsp.pink(n, r), "lp", 300 + 2500 * roar_env, 0.7, block=256) * roar_env
        crash = dsp.bandpass(r.standard_normal(n), 400, 9000, 2) * np.where(t < t_c, 0, np.exp(-(t - t_c) / 0.35))
        foam_env = np.where(t < t_c, 0.0, np.minimum(1.0, (t - t_c) / 0.2) * np.exp(-(t - t_c) / (1.4 * size)))
        foam = (_grains(r, n, 2500, 2500, 10000, 0.0005, 0.003) + 0.5 * dsp.highpass(r.standard_normal(n), 3000, 2))
        out[ch] = 0.9 * _nrm(roar) + 0.6 * _nrm(crash) + 0.35 * _nrm(foam * foam_env)
    return out


@sound("rope_snap", "a taut rope snapping", True)
def rope_snap(r):
    n = n_of(0.8)
    crack = _burst(r, n, 1500, 12000, 0.004, 0.0002)
    whip = dsp.tv_biquad(r.standard_normal(n), "bp", 5000 * np.exp(-t_axis(n) / 0.05) + 800, 2.0, block=64) * _dec(n, 0.06)
    thump = _thump(r, 120, 0.8, 0.04, 0.5, 0.3)
    flutter = _flaps(r, 0.6, 22.0, 300, 2000, 0.01)
    y = _nrm(crack) + 0.5 * _nrm(whip) + 0.4 * _nrm(thump)
    y[n_of(0.05):n_of(0.05) + len(flutter)] += 0.2 * _nrm(flutter)[: n - n_of(0.05)]
    return _stereo(y, 0.0, 0.3, r)


@sound("net_tangle", "a rope net tangling and rustling", True, dur=1.2)
def net_tangle(r, dur):
    n = n_of(dur)
    rub = _grains(r, n, 220, 800, 5000, 0.003, 0.012, 0.8) * (0.6 + 0.4 * dsp.ctrl_noise(n, r, 5.0))
    creak = _creak(r, dur * 0.6, 60, 140, (900, 1900))
    y = _nrm(rub)
    y[:len(creak)] += 0.35 * _nrm(creak)[:n]
    y += 0.25 * _nrm(_flaps(r, dur, 7.0, 400, 2500, 0.02))
    return _stereo(y, 0.0, 0.5, r)


@sound("snow_crunch", "a slow press into deep snow", dur=0.5)
def snow_crunch(r, dur):
    n = n_of(dur)
    env = _env([(0, 0), (0.03, 1.0), (dur * 0.6, 0.7), (dur, 0)], n)
    y = _grains(r, n, 1100, 600, 5000, 0.002, 0.01, 0.9) * env
    y += 0.3 * _thump(r, 60, dur, 0.06, 0.2, 0.5)
    return y


def _creak(r, dur, f_lo, f_hi, bands=(800, 1600)):
    """stick-slip friction: a pulse train whose rate wanders, ringing a few wooden resonances"""
    n = n_of(dur)
    rate = f_lo + (f_hi - f_lo) * np.clip(0.5 + 0.5 * dsp.ctrl_noise(n, r, 1.2), 0, 1)
    ph = dsp.phase_cycles(rate, n, r.uniform())
    k = np.floor(ph)
    hits = np.nonzero(np.diff(k, prepend=k[0]) > 0)[0]
    x = np.zeros(n)
    x[hits] = np.exp(r.normal(0, 0.35, len(hits)))
    y = dsp.resonator_bank(x, [bands[0], bands[1], bands[1] * 1.7], [0.05, 0.04, 0.03], [1.0, 0.7, 0.4])
    return y * _env([(0, 0), (0.08, 1), (dur * 0.8, 0.8), (dur, 0)], n)


@sound("ice_creak", "ice creaking under weight", dur=1.5)
def ice_creak(r, dur):
    y = _creak(r, dur, 25, 90, (1300, 2700))
    n = len(y)
    ping = dsp.modal([r.uniform(1800, 3200)], [1.0], [0.6], n, r=r) * 0.2
    return dsp.highpass(_nrm(y) + ping, 300, 2)


@sound("thunder", "thunder: crack and rolling rumble (distance 0.5 near .. 3 far)", True, distance=1.0)
def thunder(r, distance):
    dur = 5.0 + 2.0 * distance
    n = n_of(dur)
    out = np.zeros((2, n))
    t = t_axis(n)
    for ch in range(2):
        rumble = np.zeros(n)
        for _ in range(5):
            at = r.uniform(0.0, 1.5) * distance
            env = np.where(t < at, 0, (1 - np.exp(-(t - at) / 0.15)) * np.exp(-(t - at) / r.uniform(0.8, 2.0)))
            rumble += r.uniform(0.4, 1.0) * dsp.lowpass(dsp.brown(n, r), 120 + 300 / distance, 2) * env
        out[ch] = _nrm(rumble)
        if distance < 1.5:
            crack = _grains(r, n, 4000, 1000, 8000, 0.0005, 0.004, 1.0) * np.exp(-t / 0.25) * np.clip(t / 0.01, 0, 1)
            out[ch] += (1.5 - distance) * 0.6 * _nrm(crack)
    return dsp.lowpass(out, 6000 / distance, 2)


@sound("rain", "a passing shower of rain", True, dur=3.0, intensity=1.0)
def rain(r, dur, intensity):
    n = n_of(dur)
    out = np.zeros((2, n))
    env = _env([(0, 0), (min(0.5, dur * 0.2), 1.0), (dur * 0.8, 1.0), (dur, 0)], n)
    for ch in range(2):
        drops = _grains(r, n, 900 * intensity, 1200, 9000, 0.0008, 0.004, 0.7)
        hiss = dsp.bandpass(dsp.pink(n, r), 800, 9000, 2)
        out[ch] = (0.7 * _nrm(drops) + 0.5 * _nrm(hiss)) * env
    return out


# ================================================================================================ magic / signals
@sound("sparkle", "magical sparkle: a spray of tiny bright pings", True, dur=1.0, density=1.0)
def sparkle(r, dur, density):
    n = n_of(dur + 0.6)
    out = np.zeros((2, n))
    t = 0.0
    while t < dur:
        f = r.uniform(2800, 9000)
        m = n_of(0.35)
        ping = dsp.modal([f, f * 2.01], [1.0, 0.2], [r.uniform(0.15, 0.4), 0.1], m, r=r) * r.uniform(0.3, 1.0)
        _place(out, dsp.pan_mono(ping, r.uniform(-0.8, 0.8)), t)
        t += r.exponential(1.0 / (35.0 * density))
    shimmer = dsp.highpass(r.standard_normal((2, n)), 6000, 2) * _env([(0, 0), (0.1, 1), (dur, 0.5), (n / SR, 0)], n)
    return out + 0.04 * shimmer


@sound("twinkle", "a few rising bell-like twinkles", True, notes=5, pitch=1.0)
def twinkle(r, notes, pitch):
    scale = [0, 2, 4, 7, 9, 12, 14, 16, 19]
    n = n_of(0.12 * notes + 1.5)
    out = np.zeros((2, n))
    base = 1568.0 * pitch
    for k in range(int(notes)):
        f = base * 2 ** (scale[k % len(scale)] / 12)
        m = n_of(1.4)
        ping = dsp.modal([f, f * 2.76, f * 5.4], [1.0, 0.25, 0.08], [1.2, 0.5, 0.2], m, r=r)
        _place(out, dsp.pan_mono(ping, -0.5 + k / max(1, notes - 1)), 0.11 * k)
    return _space(out, "hall", 0.3)


@sound("magic_shimmer", "a sustained magical shimmer that swells and fades", True, dur=2.0, pitch=1.0)
def magic_shimmer(r, dur, pitch):
    n = n_of(dur)
    t = t_axis(n)
    out = np.zeros((2, n))
    for k in range(10):
        f = 880.0 * pitch * 2 ** (r.choice([0, 4, 7, 11, 12, 16, 19, 24]) / 12) * r.uniform(0.997, 1.003)
        trem = 0.5 + 0.5 * np.sin(TWO_PI * r.uniform(4, 9) * t + r.uniform(0, 6))
        out += dsp.pan_mono(np.sin(TWO_PI * f * t + r.uniform(0, 6)) * trem * r.uniform(0.3, 1.0), r.uniform(-0.8, 0.8))
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.2
    air = dsp.highpass(r.standard_normal((2, n)), 5000, 2) * 0.15
    return (out / 10.0 + air) * env


@sound("chime", "a wind chime tube", True, pitch=1.0)
def chime(r, pitch):
    n = n_of(3.5)
    f = 1046.5 * pitch
    y = dsp.modal([f, f * 2.76, f * 5.4, f * 8.93], [1.0, 0.5, 0.25, 0.1], [3.0, 1.6, 0.8, 0.4], n, r=r)
    y[:n_of(0.004)] += 0.3 * _nrm(dsp.highpass(r.standard_normal(n_of(0.004)), 4000, 2))
    return _space(y, "field", 0.2)


@sound("bell_ding", "a small service bell 'ding'", pitch=1.0)
def bell_ding(r, pitch):
    n = n_of(2.2)
    f = 2093.0 * pitch
    y = dsp.modal([f, f * 1.003, f * 2.32, f * 4.2], [1.0, 0.8, 0.3, 0.15], [1.8, 1.7, 0.8, 0.4], n, r=r)
    y[:n_of(0.003)] += 0.4 * _nrm(dsp.highpass(r.standard_normal(n_of(0.003)), 5000, 2))
    return y


@sound("zap", "an electric zap", pitch=1.0, dur=0.4)
def zap(r, pitch, dur):
    n = n_of(dur)
    t = t_axis(n)
    f = 1800 * pitch * np.exp(-t / (dur * 0.35)) + 120
    ph = dsp.phase_cycles(f, n)
    y = np.sign(np.sin(TWO_PI * ph)) * 0.5 + np.sin(TWO_PI * ph * 1.5)
    y = dsp.lowpass(y, 7000, 2) * _dec(n, dur * 0.4, 0.001)
    buzz = dsp.bandpass(r.standard_normal(n), 2000, 9000, 2) * (0.5 + 0.5 * np.sign(np.sin(TWO_PI * 60 * t))) * _dec(n, dur * 0.3)
    return _nrm(y) + 0.4 * _nrm(buzz)


def _beep(r, f0, f1, dur, wave="sine"):
    n = n_of(dur)
    t = t_axis(n)
    f = f0 + (f1 - f0) * dsp.smoothstep(t / dur)
    ph = dsp.phase_cycles(f, n)
    y = np.sin(TWO_PI * ph) if wave == "sine" else dsp.lowpass(dsp.osc_square(f, n, 0.0, 0.5), 5000, 2) * 0.6
    return y * _env([(0, 0), (0.006, 1), (dur - 0.01, 1), (dur, 0)], n)


@sound("robot_beeps", "R2-style chirps and beeps with portamento", count=5, mood="happy")
def robot_beeps(r, count, mood):
    seq = []
    t = 0.0
    for k in range(int(count)):
        f0 = r.uniform(900, 2400)
        f1 = f0 * (r.uniform(1.1, 1.6) if mood == "happy" else r.uniform(0.5, 0.8) if mood == "sad" else r.uniform(0.8, 1.3))
        d = r.uniform(0.05, 0.16)
        seq.append((t, _beep(r, f0, f1, d, "sine" if k % 3 else "square")))
        t += d + r.uniform(0.01, 0.06)
    y = np.zeros(n_of(t + 0.1))
    for at, b in seq:
        _place(y, b, at)
    return y


@sound("servo", "a small servo motor whirring", dur=0.8, pitch=1.0)
def servo(r, dur, pitch):
    n = n_of(dur)
    t = t_axis(n)
    f = 180 * pitch * (1.0 + 0.6 * dsp.smoothstep(t / 0.12)) * (1.0 - 0.25 * dsp.smoothstep((t - dur + 0.15) / 0.12))
    whine = dsp.bandpass(dsp.osc_saw(f, n), 600, 4000, 2)
    gears = _grains(r, n, 400, 1500, 7000, 0.0005, 0.002) * 0.3
    env = _env([(0, 0), (0.03, 1), (dur - 0.05, 1), (dur, 0)], n)
    return (_nrm(whine) + gears) * env


# ================================================================================================ festival
def _pop_crack(r, size=1.0, bright=1.0):
    """one firecracker: a sharp broadband crack with a body thump and a short high ring"""
    m = n_of(0.09)
    t = t_axis(m)
    crack = r.standard_normal(m) * np.exp(-t / (0.0025 + 0.002 * size)) * np.clip(t / 0.0002, 0, 1)
    crack = dsp.highpass(crack, 500, 2)
    body = np.sin(TWO_PI * dsp.phase_cycles(160 * (1 + 2 * np.exp(-t / 0.004)), m)) * np.exp(-t / 0.012)
    ring = dsp.bandpass(r.standard_normal(m), 3000 * bright, 9000, 2) * np.exp(-t / 0.01)
    return _nrm(crack) + 0.35 * size * _nrm(body) + 0.15 * _nrm(ring)


@sound("firecracker_string", "a string of firecrackers: dense realistic crackle with spread and echo", True,
       dur=3.0, density=1.0, pitch=1.0, spread=1.0, decay=1.0)
def firecracker_string(r, dur, density, pitch, spread, decay):
    n = n_of(dur + 0.6)
    out = np.zeros((2, n))
    t = r.uniform(0.0, 0.02)
    k = 0
    while t < dur:
        u = t / dur
        rate = 60.0 * density * (0.4 + 0.6 * dsp.smoothstep(u / 0.15)) * (1.0 - 0.6 * decay * dsp.smoothstep((u - 0.7) / 0.3))
        size = float(np.exp(r.normal(0.0, 0.35)))
        pop_ = _pop_crack(r, size, pitch * r.uniform(0.85, 1.2))
        g = size * (1.0 - 0.5 * decay * u) * r.uniform(0.5, 1.0)
        pan = float(np.clip(r.normal(0.0, 0.45 * spread) + 0.3 * spread * np.sin(TWO_PI * 0.3 * t), -1, 1))
        _place(out, dsp.pan_mono(pop_, pan), t, g)
        t += r.exponential(1.0 / max(rate, 1.0))
        k += 1
    debris = dsp.bandpass(r.standard_normal((2, n)), 2000, 8000, 2) * _env([(0, 0), (0.2, 1), (dur, 0.6), (n / SR, 0)], n)
    out += 0.03 * debris
    return _space(out, "field", 0.35, seed=11)


@sound("firecracker", "a single firecracker bang", True, size=1.0)
def firecracker(r, size):
    y = np.pad(_pop_crack(r, size * 1.4, 1.0), (0, n_of(0.3)))
    return _space(_stereo(y, 0.0), "field", 0.4)


@sound("firework_launch", "a firework rocket launching with a rising whistle", True, dur=1.6)
def firework_launch(r, dur):
    n = n_of(dur)
    t = t_axis(n)
    f = 600 + 2200 * (t / dur) ** 0.7
    whistle = np.sin(TWO_PI * dsp.phase_cycles(f * (1 + 0.004 * np.sin(TWO_PI * 30 * t)), n))
    hiss = dsp.bandpass(r.standard_normal(n), 1500, 7000, 2)
    thump = np.pad(_thump(r, 80, 0.3, 0.04, 0.5, 0.6), (0, max(0, n - n_of(0.3))))[:n]
    env = _env([(0, 0), (0.05, 1), (dur * 0.8, 0.8), (dur, 0)], n)
    y = (0.5 * whistle + 0.5 * _nrm(hiss)) * env * np.exp(-t / (dur * 1.5)) + 0.6 * _nrm(thump)
    return _stereo(y, 0.0)


@sound("firework_boom", "a firework burst: deep boom with a long echo", True, size=1.0)
def firework_boom(r, size):
    dur = 3.0
    n = n_of(dur)
    boom = _thump(r, 55 / size ** 0.3, dur, 0.25 * size, 0.8, 0.6)
    crack = _burst(r, n, 300, 6000, 0.03, 0.001)
    y = _nrm(boom) + 0.5 * _nrm(crack)
    return _space(_stereo(y, 0.0), "field", 0.6, seed=13)


@sound("firework_crackle", "the glittering crackling tail of a firework", True, dur=2.0, density=1.0)
def firework_crackle(r, dur, density):
    n = n_of(dur + 0.3)
    out = np.zeros((2, n))
    t = 0.0
    while t < dur:
        u = t / dur
        m = n_of(0.03)
        c = dsp.highpass(r.standard_normal(m), 2500, 2) * np.exp(-t_axis(m) / 0.003) * r.uniform(0.3, 1.0)
        _place(out, dsp.pan_mono(c, r.uniform(-0.9, 0.9)), t, 1.0 - 0.7 * u)
        t += r.exponential(1.0 / (120.0 * density * (1.0 - 0.6 * u)))
    return _space(out, "field", 0.3)


@sound("firework", "a whole firework: launch whistle, boom, crackling tail", True, size=1.0)
def firework(r, size):
    a = firework_launch(r, 1.4)
    b = firework_boom(r, size)
    c = firework_crackle(r, 2.2, 1.0)
    n = n_of(1.4 + 3.0 + 1.0)
    out = np.zeros((2, n + c.shape[-1]))
    dsp.place(out, a, 0, 0.6)
    dsp.place(out, b, n_of(1.35), 1.0)
    dsp.place(out, c, n_of(1.5), 0.6)
    return out


@sound("lantern_whoosh", "a sky lantern lifting away: soft whoosh and paper rustle", True, dur=1.8)
def lantern_whoosh(r, dur):
    w = _whoosh_core(r, dur, dur * 0.4, 200, 1200, q=1.0, rise=1.5, stereo_move=0.3)
    n = w.shape[-1]
    paper = _grains(r, n, 250, 1500, 7000, 0.001, 0.005) * _env([(0, 0), (0.2, 1), (dur, 0)], n)
    return w + 0.25 * _stereo(_nrm(paper), 0.0, 0.4, r)


@sound("flame_ignite", "a flame catching: strike, whoomph, crackle", True)
def flame_ignite(r):
    dur = 1.6
    n = n_of(dur)
    t = t_axis(n)
    strike = _grains(r, n_of(0.12), 2500, 2000, 9000, 0.0005, 0.002) * _dec(n_of(0.12), 0.05)
    whoomph = dsp.tv_biquad(dsp.pink(n, r), "lp", 300 + 1200 * np.exp(-t / 0.4), 0.8, block=256) * \
        _env([(0, 0), (0.08, 0.2), (0.25, 1.0), (dur, 0.2)], n)
    crackle = dsp.crackle(n, r, 25.0, 0.8, (0.0005, 0.003), hp=1500) * _env([(0, 0), (0.3, 1), (dur, 0.6)], n)
    y = np.zeros(n)
    y[:len(strike)] += 0.5 * _nrm(strike)
    y += _nrm(whoomph) + 0.4 * _nrm(crackle)
    return _stereo(y, 0.0, 0.4, r)


# ================================================================================================ household
@sound("door_creak", "an old door creaking open", dur=1.6, pitch=1.0)
def door_creak(r, dur, pitch):
    y = _creak(r, dur, 30 * pitch, 140 * pitch, (650 * pitch, 1500 * pitch))
    return dsp.highpass(y, 150, 2)


@sound("door_knock", "knuckles knocking on a wooden door", knocks=3, force=0.7)
def door_knock(r, knocks, force):
    gap = 0.17
    n = n_of(gap * knocks + 0.4)
    y = np.zeros(n)
    for k in range(int(knocks)):
        hit = _modal_hit(r, np.array([180, 410, 690, 1150]) * r.uniform(0.97, 1.03), [1.0, 0.7, 0.4, 0.2],
                         [0.14, 0.1, 0.07, 0.05], 0.35, noise=(800, 5000, 0.5, 0.002))
        _place(y, hit, k * gap * r.uniform(0.92, 1.08), force * r.uniform(0.85, 1.0))
    return y


@sound("table_thump", "a fist or bowl set down on a wooden table, cups rattling", force=0.7)
def table_thump(r, force):
    n = n_of(0.6)
    y = _modal_hit(r, np.array([95, 210, 380, 640]), [1.0, 0.6, 0.35, 0.2], [0.18, 0.12, 0.09, 0.06], 0.6,
                   noise=(500, 4000, 0.4, 0.004))
    rattle = dsp.modal(r.uniform(1800, 5200, 6), r.uniform(0.2, 1.0, 6), r.uniform(0.05, 0.2, 6), n, r=r)
    y[n_of(0.01):] += 0.2 * force * _nrm(rattle)[: n - n_of(0.01)]
    return y * force


@sound("bowl_clink", "porcelain bowls clinking", pitch=1.0)
def bowl_clink(r, pitch):
    n = n_of(1.0)
    f = 2350.0 * pitch * r.uniform(0.97, 1.03)
    y = dsp.modal([f, f * 1.72, f * 2.6, f * 3.9], [1.0, 0.6, 0.3, 0.15], [0.9, 0.5, 0.3, 0.2], n, r=r)
    y[:n_of(0.002)] += 0.5 * _nrm(dsp.highpass(r.standard_normal(n_of(0.002)), 5000, 2))
    return y


@sound("chopsticks", "two chopsticks tapping a bowl rim", taps=2)
def chopsticks(r, taps):
    n = n_of(0.12 * taps + 0.2)
    y = np.zeros(n)
    for k in range(int(taps)):
        click = dsp.modal([r.uniform(2600, 3400), r.uniform(4200, 5200)], [1.0, 0.5], [0.04, 0.03], n_of(0.1), r=r)
        click[:n_of(0.002)] += 0.6 * _nrm(dsp.highpass(r.standard_normal(n_of(0.002)), 4000, 2))
        _place(y, click, 0.11 * k * r.uniform(0.9, 1.1))
    return y


@sound("dumpling_plop", "a dumpling dropped into boiling water", True)
def dumpling_plop(r):
    n = n_of(0.8)
    y = np.zeros(n)
    plop = _chirp(220, 520, n_of(0.12), 0.7) * _dec(n_of(0.12), 0.035, 0.002)
    y[:len(plop)] += plop
    y += 0.3 * _nrm(_burst(r, n, 600, 5000, 0.02))
    for _ in range(8):
        _place(y, _bubble(r, r.uniform(500, 1500), amp=0.3), r.uniform(0.02, 0.4))
    return _space(_stereo(y, 0.0), "field", 0.1)


@sound("fire_crackle", "a wood fire crackling", True, dur=3.0, intensity=1.0)
def fire_crackle(r, dur, intensity):
    n = n_of(dur)
    out = np.zeros((2, n))
    for ch in range(2):
        c = dsp.crackle(n, r, 9.0 * intensity, 1.0, (0.0005, 0.004), hp=1200)
        pops = dsp.crackle(n, r, 1.2 * intensity, 0.6, (0.003, 0.012), hp=300)
        roar = dsp.lowpass(dsp.brown(n, r), 400, 2) * (0.8 + 0.2 * dsp.ctrl_noise(n, r, 1.0))
        out[ch] = _nrm(c) + 0.6 * _nrm(pops) + 0.2 * _nrm(roar)
    return out


@sound("kettle", "a kettle coming to the boil, whistle optional", True, dur=4.0, whistle=True)
def kettle(r, dur, whistle):
    n = n_of(dur)
    t = t_axis(n)
    u = t / dur
    boil = dsp.crackle(n, r, 40.0 + 300.0 * u, 0.5, (0.002, 0.01), hp=300) * (0.3 + 0.7 * u)
    rumble = dsp.lowpass(dsp.brown(n, r), 300, 2) * u
    y = 0.6 * _nrm(boil) + 0.3 * _nrm(rumble)
    if whistle:
        w_env = dsp.smoothstep((u - 0.55) / 0.25)
        f = 1850 * (1 + 0.02 * dsp.smoothstep((u - 0.55) / 0.3))
        wh = (np.sin(TWO_PI * f * t) + 0.6 * np.sin(TWO_PI * (f * 1.012) * t)) * w_env
        breath = dsp.bandpass(r.standard_normal(n), 1500, 3000, 2) * w_env * 0.2
        y = y + 0.5 * (wh / 1.6) + breath
    return _stereo(y, 0.1, 0.3, r)


# ================================================================================================ musical gestures
def _instrument_run(name, pitches, step, vel, art="normal", dur=0.6):
    from codecinema.audio import instruments
    clips = [(n_of(k * step), instruments.play(name, p, dur, vel * (0.7 + 0.3 * k / max(1, len(pitches) - 1)), art, seed=k))
             for k, p in enumerate(pitches)]
    n = max(s + c.shape[-1] for s, c in clips)
    out = np.zeros((2, n))
    for s, c in clips:
        out[:, s:s + c.shape[-1]] += c
    return out


@sound("gliss_up", "harp glissando up (C major / pentatonic)", True, pentatonic=False, sweep=0.6)
def gliss_up(r, pentatonic, sweep):
    scale = (0, 2, 4, 7, 9) if pentatonic else (0, 2, 4, 5, 7, 9, 11)
    ps = [48 + 12 * o + s for o in range(4) for s in scale][:22]
    return _instrument_run("harp", ps, sweep / len(ps), 0.6, dur=1.2)


@sound("gliss_down", "harp glissando down", True, pentatonic=False, sweep=0.6)
def gliss_down(r, pentatonic, sweep):
    scale = (0, 2, 4, 7, 9) if pentatonic else (0, 2, 4, 5, 7, 9, 11)
    ps = [48 + 12 * o + s for o in range(4) for s in scale][:22][::-1]
    return _instrument_run("harp", ps, sweep / len(ps), 0.6, dur=1.2)


@sound("cartoon_rise", "anticipation rise: tremolo strings and a slide whistle climbing", True, dur=1.5)
def cartoon_rise(r, dur):
    n = n_of(dur + 0.3)
    out = np.zeros((2, n))
    w = _slide(r, 400, 1600, dur, vib_end=False)
    out[:, :len(w)] += dsp.pan_mono(0.5 * w, 0.2)
    k = 8
    for j in range(k):
        from codecinema.audio import instruments
        c = instruments.play("tremolo_strings", 55 + j * 2, dur / k * 1.3, 0.4 + 0.5 * j / k, seed=j)
        dsp.place(out, c, n_of(j * dur / k), 0.5)
    return out


@sound("cartoon_fall", "falling-away whistle (something dropping from a height)", dur=1.6)
def cartoon_fall(r, dur):
    return _slide(r, 2400, 700, dur, vib_end=False)


@sound("comedic_sting", "comic sting: sad trombone 'wah-wah-wah-waah' or 'ta-da'", True, kind="sad_trombone")
def comedic_sting(r, kind):
    from codecinema.audio import instruments
    if kind == "tada":
        out = np.zeros((2, n_of(2.5)))
        dsp.place(out, instruments.chord("brass_section", [60, 64, 67], 0.12, 0.8, "staccato"), 0)
        dsp.place(out, instruments.chord("brass_section", [65, 69, 72, 77], 1.0, 0.9, "accent"), n_of(0.16))
        dsp.place(out, instruments.play("cymbals", 60, 1.0, 0.7), n_of(0.16), 0.6)
        return out
    notes = [(55, 0.38), (54, 0.38), (53, 0.38), (52, 1.3)]
    out = np.zeros((2, n_of(3.2)))
    at = 0.0
    for k, (m, d) in enumerate(notes):
        c = instruments.play("trombone", m, d * 0.92, 0.7, "vibrato" if k == 3 else "normal", seed=k)
        n = c.shape[-1]
        wah = 0.55 + 0.45 * np.sin(np.pi * np.clip(np.arange(n) / SR / max(d, 0.1), 0, 1)) ** 0.7
        c = dsp.lp_varying(c, 500 + 2200 * wah, 1.6, spacing=0.5) * wah
        dsp.place(out, c, n_of(at))
        at += d
    return out


@sound("heartbeat", "heartbeats: lub-dub", beats=2, bpm=72.0)
def heartbeat(r, beats, bpm):
    period = 60.0 / bpm
    n = n_of(period * beats + 0.5)
    y = np.zeros(n)
    for k in range(int(beats)):
        for at, f0, a, d in ((0.0, 52.0, 1.0, 0.085), (0.17, 60.0, 0.62, 0.07)):
            m = n_of(0.4)
            tt = t_axis(m)
            body = np.sin(TWO_PI * dsp.phase_cycles(f0 * (1.0 + 0.45 * np.exp(-tt / 0.02)), m)) * np.exp(-tt / d)
            body *= np.clip(tt / 0.004, 0, 1)
            thump = dsp.lowpass(r.standard_normal(m), 160, 2) * np.exp(-tt / 0.03)
            _place(y, a * (body + 0.25 * _nrm(thump)), k * period + at)
    return dsp.lowpass(y, 400, 2)


@sound("gasp_hit", "surprise: a sharp inhale into an orchestral hit", True)
def gasp_hit(r):
    from codecinema.audio import instruments
    n = n_of(2.2)
    out = np.zeros((2, n))
    k = n_of(0.35)
    t = t_axis(k)
    gasp = dsp.tv_biquad(r.standard_normal(k), "bp", 900 + 1800 * (t / t[-1]), 3.0, block=128) * \
        _env([(0, 0), (0.25, 1.0), (0.35, 0)], k)
    out[:, :k] += 0.4 * _stereo(_nrm(gasp), 0.0)
    dsp.place(out, instruments.chord("brass_section", [50, 57, 62, 65], 0.35, 0.95, "marcato"), n_of(0.33))
    dsp.place(out, instruments.chord("strings", [62, 69, 74], 0.3, 0.9, "marcato"), n_of(0.33))
    dsp.place(out, instruments.play("timpani", 38, 1.0, 0.9), n_of(0.33), 0.8)
    return out
