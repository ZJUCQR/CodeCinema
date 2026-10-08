"""
codecinema.audio.sfx -- procedural sound effects: Foley and footsteps, household and UI, animals, water and
weather, vehicles, action, crowds, magic and sci-fi, festival and cartoon sounds.

    render(name, seed=0, **params) -> float64 audio at dsp.SR (mono (n,) or stereo (2, n)), starting at sample 0
    catalog() -> [{"name", "description", "params": {name: default}, "stereo": bool}]
    names()

Every sound is synthesized from physical models -- modal resonators (struck bars, plates, bells, glass), Karplus-
Strong strings, bubbles (Minnaert resonances), stick-slip friction, source-filter voices for animal calls, moving
sources with propagation delay (Doppler) and ground reflection -- and shaped noise.  Renders are deterministic for a
seed and loudness-matched (the loudest 100 ms sits at -14 LUFS, K-weighted; peaks at most -1 dBFS) so a mix sets
levels with plain gains.  Impacts start on their first sample; gestures such as whooshes peak part-way through
(`peak` param).  Every clip starts and ends at zero.
"""
import numpy as np
from scipy import signal

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


C_AIR = 343.0                   # speed of sound (m/s)


def _pass_by(src, dur, speed, closest, distance, direction=1.0, ground=0.0, height=1.5, absorb=True, width=0.85):
    """a source moving on a straight line past the listener: propagation delay (the Doppler shift falls out of it),
    1/r spreading (unity at the closest point), air absorption and an azimuth pan.  ground > 0 adds the ground
    reflection, whose sweeping comb is the 'phasing' of a fly-over.  src(m) -> mono source of m samples (emission
    time); speed in m/s, closest = time (s) of the closest approach, distance = closest distance (m)."""
    n = n_of(dur)
    t = t_axis(n)
    x = direction * speed * (t - closest)
    paths = [(np.sqrt(x * x + distance ** 2), 1.0)]
    if ground:
        paths.append((np.sqrt(x * x + (distance + 2.0 * height) ** 2), ground))
    emit = [t - (R - distance) / C_AIR for R, _ in paths]
    e0 = min(float(e.min()) for e in emit)
    s = src(int(np.ceil((max(float(e.max()) for e in emit) - e0) * SR)) + 8)
    y = np.zeros(n)
    for (R, g), e in zip(paths, emit):
        y += g * dsp.interp_cubic(s, (e - e0) * SR) * (distance / R)
    R = paths[0][0]
    if absorb:
        y = dsp.lp_varying(y, np.clip(20000.0 / (1.0 + R / 40.0), 700.0, 18000.0), 0.7, spacing=0.5)
    return dsp.pan_mono(y, width * np.clip(x / R, -1.0, 1.0))


def _voiced(r, f, n, tilt=1800.0, jitter=0.008, shimmer=0.06, breath=0.12, rough=0.0):
    """voiced source of an animal call: band-limited glottal pulses following f (Hz, scalar or array) with cycle
    jitter and shimmer, aspiration noise and optional roughness (period doubling: the rasp of crows and cows)"""
    f = np.broadcast_to(np.asarray(f, dtype=np.float64), (n,)) * (1.0 + jitter * dsp.ctrl_noise(n, r, 40.0))
    src = dsp.onepole(dsp.osc_saw(f, n, r.uniform()), tilt)
    src = src / (dsp.rms(src) + 1e-12)
    if rough:
        src = src * (1.0 + 0.5 * rough * np.tanh(3.0 * np.sin(TWO_PI * dsp.phase_cycles(f * 0.5, n, r.uniform()))))
    src = src * (1.0 + shimmer * dsp.ctrl_noise(n, r, 30.0))
    return src + breath * 2.5 * dsp.bandpass(r.standard_normal(n), 400, 7000, 2)


def _formants(src, bands):
    """parallel band-pass resonators [(fc Hz (scalar or array), q, gain)] -- a vocal tract, a horn, a body"""
    y = np.zeros_like(src)
    for fc, q, g in bands:
        if np.ndim(fc):
            y += g * dsp.tv_biquad(src, "bp", np.clip(fc, 60.0, dsp.NYQ * 0.9), q, block=64)
        else:
            y += g * dsp.biquad(src, "bp", fc, q)
    return y


def _call(r, f, d, bands, env=None, **voice):
    """one animal call: voiced source through formants under a smooth envelope (default: quick rise, rounded end)"""
    n = n_of(d)
    y = _formants(_voiced(r, f, n, **voice), bands)
    if env is None:
        env = _env([(0, 0), (min(0.025, d * 0.15), 1.0), (d * 0.7, 0.85), (d, 0.0)], n)
    return y * env


# bell partials: (ratio, amplitude, relative T60); the doublets beat like a real, slightly asymmetric bell
_BELL = ((1.0, 1.0, 1.0), (1.0042, 0.65, 0.95), (2.09, 0.42, 0.55), (2.95, 0.3, 0.42), (4.13, 0.18, 0.3),
         (5.43, 0.1, 0.2))


def _bell(r, f, n, t60=1.2, bright=1.0, partials=_BELL):
    fr = np.array([p[0] for p in partials]) * f * r.uniform(0.997, 1.003, len(partials))
    amps = np.array([p[1] for p in partials]) * bright ** np.log2(np.array([p[0] for p in partials]) + 1.0)
    return dsp.modal(fr, amps, np.array([p[2] for p in partials]) * t60, n, r=r, attack=0.0003)


def _strikes(n, times, amps):
    """impulse train for resonator banks: one (amplitude) impulse per strike time"""
    x = np.zeros(n)
    for t, a in zip(times, amps):
        i = n_of(t)
        if i < n:
            x[i] += a
    return x


def _ticks(r, rate, n, sigma=0.3):
    """impulse train at a (time-varying) rate with random amplitudes: it drives resonators (teeth, tymbals, ratchets)"""
    k = np.floor(dsp.phase_cycles(rate, n, r.uniform()))
    hits = np.nonzero(np.diff(k, prepend=k[0]) > 0)[0]
    x = np.zeros(n)
    x[hits] = np.exp(r.normal(0.0, sigma, len(hits)))
    return x


def _bubble_field(r, n, rate, f_lo=400.0, f_hi=3000.0, sigma=0.6, bands=18):
    """a population of bubbles (Minnaert resonances rising as they surface) -- streams, rivers, pouring.
    Vectorised: each of `bands` log-spaced bubble sizes is an impulse train convolved with its own bubble."""
    rate = np.broadcast_to(np.asarray(rate, dtype=np.float64), (n,))
    y = np.zeros(n)
    for f0 in np.geomspace(f_lo, f_hi, bands):
        hits = np.nonzero(r.random(n) < rate / (bands * SR))[0]
        if not len(hits):
            continue
        x = np.zeros(n)
        x[hits] = np.exp(r.normal(0.0, sigma, len(hits))) * (f_lo / f0) ** 0.35
        b = _bubble(r, f0 * r.uniform(0.94, 1.06))
        y += signal.oaconvolve(x, b)[:n]
    return y


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


@sound("water_drip", "a single water drop", True, pitch=1.0)
def water_drip(r, pitch):
    n = n_of(0.25)
    y = 0.8 * _bubble(r, 1100 * pitch, 0.06, rise=1.2)
    y = np.pad(y, (0, n - len(y)))
    y += 0.15 * _burst(r, n, 3000, 9000, 0.002)
    return _space(y, "field", 0.15)


# ================================================================================================ footsteps
_SURFACES = ("grass", "sand", "snow", "wood", "stone", "wet_rock", "carpet", "metal", "tile", "gravel", "leaves", "mud")


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
        elif surface == "carpet":
            fibre = dsp.bandpass(r.standard_normal(m), 700, 3500, 2) * _env([(0, 0), (0.01, 1), (0.08, 0),
                                                                             (m / SR + 0.1, 0)], m)
            hit = _thump(r, 75, m / SR, 0.035, 0.2, 0.9) + 0.25 * _nrm(fibre)
            hit = dsp.lowpass(hit, 1700, 4)
        elif surface == "metal":
            hit = _modal_hit(r, np.array([290, 710, 1240, 1980, 2950]) * r.uniform(0.92, 1.08),
                             [1.0, 0.75, 0.5, 0.3, 0.18],
                             [0.32, 0.24, 0.17, 0.12, 0.08], m / SR, noise=(1800, 8000, 0.7, 0.0015))
            hit += 0.35 * _thump(r, 110, m / SR, 0.025, 0.4, 0.3)
        elif surface == "tile":
            click = _burst(r, m, 2200, 10000, 0.0022, 0.0002)
            ring = dsp.modal(r.uniform(2400, 3600) * np.array([1.0, 1.9]), [1.0, 0.4], [0.05, 0.03], m, r=r)
            hit = _nrm(click) + 0.25 * _nrm(ring) + 0.35 * _nrm(_thump(r, 130, m / SR, 0.018, 0.5, 0.3))
        elif surface == "gravel":
            crunch = _grains(r, m, 2600, 900, 7500, 0.0006, 0.004, 0.9) * \
                _env([(0, 0), (0.008, 1), (0.07, 0.7), (0.17, 0), (m / SR + 0.1, 0)], m)
            hit = 0.45 * _thump(r, 85, m / SR, 0.03, 0.3, 0.6) + _nrm(crunch)
        elif surface == "leaves":
            crisp = _grains(r, m, 3200, 1600, 10000, 0.0003, 0.0018, 1.0) * _env([(0, 0), (0.006, 1), (0.06, 0.6),
                                                                              (0.2, 0), (m / SR + 0.1, 0)], m)
            swish = dsp.bandpass(r.standard_normal(m), 1500, 6000, 2) * _env([(0, 0), (0.02, 1), (0.15, 0),
                                                                              (m / SR + 0.1, 0)], m)
            hit = 0.3 * _thump(r, 90, m / SR, 0.025, 0.3, 0.5) + _nrm(crisp) + 0.3 * _nrm(swish)
        elif surface == "mud":
            tt = t_axis(m)
            env = _env([(0, 0), (0.015, 1), (0.12, 0.3), (0.2, 0), (m / SR + 0.1, 0)], m)
            suck = dsp.tv_biquad(r.standard_normal(m) * env, "bp", 260 + 700 * np.exp(-tt / 0.05), 5.0, block=64)
            hit = 0.8 * _thump(r, 70, m / SR, 0.04, 0.3, 0.5) + 0.7 * _nrm(suck)
            for _ in range(int(r.integers(2, 5))):
                hit += 0.25 * np.pad(_bubble(r, r.uniform(250, 700), amp=1.0), (0, m))[:m]
            hit = dsp.lowpass(hit, 3000, 2)
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


def _walk(r, surface, steps, interval, weight, toe, swish=0.0):
    """a run of footsteps, feet alternating a little left and right, with optional clothing swish per stride"""
    if surface not in _SURFACES:
        raise ValueError(f"Unknown surface {surface!r}; use one of {', '.join(_SURFACES)}")
    n = n_of(interval * steps + 0.5)
    out = np.zeros((2, n))
    t = r.uniform(0.0, 0.03)
    k_sw = n_of(0.16)
    for k in range(int(steps)):
        w = float(np.clip(weight * r.uniform(0.85, 1.05) * (1.0 if k % 2 == 0 else 0.9), 0.05, 1.0))
        y = _step(r, surface, w, toe * r.uniform(0.8, 1.25))
        _place(out, dsp.pan_mono(y, (-0.12 if k % 2 == 0 else 0.12) + r.normal(0.0, 0.03)), t, w)
        if swish:
            cl = dsp.bandpass(r.standard_normal(k_sw), 400, 3000, 2) * np.sin(np.pi * np.linspace(0, 1, k_sw)) ** 2
            _place(out, dsp.pan_mono(_nrm(cl), 0.0), t - 0.1, swish * 0.12)
        t += interval * r.uniform(0.95, 1.06)
    return out


@sound("footsteps", "a walk: several footsteps on one surface, feet alternating (pace 1 = normal)", True,
       surface="stone", steps=6, pace=1.0, weight=0.6)
def footsteps(r, surface, steps, pace, weight):
    return _walk(r, surface, steps, 0.56 / max(pace, 0.2), weight, r.uniform(0.04, 0.065))


@sound("footsteps_run", "running: quick heavy strides on one surface with a swish of clothing", True,
       surface="stone", steps=8, pace=1.0, weight=0.85)
def footsteps_run(r, surface, steps, pace, weight):
    return _walk(r, surface, steps, 0.3 / max(pace, 0.2), weight, r.uniform(0.012, 0.025), swish=1.0)


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


def _texture_env(n, fade=0.4):
    d = n / SR
    fade = min(fade, d * 0.3)
    return _env([(0, 0), (fade, 1.0), (d - fade, 1.0), (d, 0.0)], n)


def _flow(r, n, intensity=1.0, lo=350.0, hi=2800.0):
    """running water (stereo): a population of bubbles, turbulent gurgle and a little spray, channels decorrelated"""
    out = np.zeros((2, n))
    for ch in range(2):
        rate = 160.0 * intensity * np.clip(1.0 + 0.5 * dsp.ctrl_noise(n, r, 0.7), 0.2, None)
        gurgle = dsp.bandpass(dsp.pink(n, r), 150, 1200, 2) * (0.7 + 0.3 * dsp.ctrl_noise(n, r, 3.0))
        spray = dsp.bandpass(r.standard_normal(n), 2500, 9000, 2)
        out[ch] = _nrm(_bubble_field(r, n, rate, lo, hi)) + 0.35 * _nrm(gurgle) + 0.12 * intensity * _nrm(spray)
    return out


@sound("stream", "a babbling brook: bubbles, gurgles and a little spray", True, dur=4.0, intensity=1.0)
def stream(r, dur, intensity):
    n = n_of(dur)
    return _flow(r, n, intensity) * _texture_env(n)


def _falls(r, n, size=1.0):
    out = np.zeros((2, n))
    for ch in range(2):
        roar = dsp.lowpass(dsp.pink(n, r), 900 / size ** 0.3, 2) + 0.6 * dsp.lowpass(dsp.brown(n, r), 200, 2)
        roar *= 1.0 + 0.12 * dsp.ctrl_noise(n, r, 0.4)
        spray = dsp.bandpass(dsp.pink(n, r), 1500, 10000, 2)
        churn = _bubble_field(r, n, 300.0, 250, 1500)
        out[ch] = _nrm(roar) + 0.45 * _nrm(spray) + 0.2 * _nrm(_grains(r, n, 2500, 1500, 9000)) + 0.3 * _nrm(churn)
    return out


@sound("waterfall", "a waterfall: a deep roar of falling water, dense spray and churning foam", True, dur=4.0, size=1.0)
def waterfall(r, dur, size):
    n = n_of(dur)
    return _falls(r, n, size) * _texture_env(n)


def _howl(r, n, strength=1.0, f_base=None):
    """wind moaning through a gap: narrow resonances on noise whose pitch rises with each gust, over a broad body"""
    gust = np.clip(0.55 + 0.45 * dsp.ctrl_noise(n, r, 0.35), 0.05, None)
    f_base = f_base or r.uniform(380, 620)
    out = np.zeros((2, n))
    for ch in range(2):
        body = dsp.lp_varying(dsp.pink(n, r), 200 + 900 * gust * strength, 0.7, spacing=0.5) * gust
        howl = np.zeros(n)
        for ratio, q, g in ((1.0, 40.0, 1.0), (1.52, 45.0, 0.45), (2.03, 50.0, 0.2)):
            fc = f_base * ratio * (0.75 + 0.5 * gust) * (1.0 + 0.01 * dsp.ctrl_noise(n, r, 2.0)) * (1.0 + 0.01 * ch)
            howl += g * dsp.tv_biquad(r.standard_normal(n), "bp", fc, q, block=128)
        out[ch] = 0.6 * _nrm(body) + strength * _nrm(howl * gust ** 2)
    return out


@sound("wind_howl", "wind howling through a gap: a moaning whistle that rises with every gust", True, dur=4.0,
       strength=1.0)
def wind_howl(r, dur, strength):
    n = n_of(dur)
    return _howl(r, n, strength) * _texture_env(n, 0.6)


def _roof_rain(r, n, roof="tin", intensity=1.0):
    out = np.zeros((2, n))
    rate = 500.0 * intensity
    for ch in range(2):
        if roof == "tin":
            y = np.zeros(n)
            for _ in range(6):              # roof panels, each ringing its own modes
                x = np.where(r.random(n) < rate / 6.0 / SR, np.exp(r.normal(0.0, 0.6, n)), 0.0)
                y += dsp.resonator_bank(x, np.exp(r.uniform(np.log(700), np.log(6000), 5)), r.uniform(0.02, 0.06, 5),
                                        r.uniform(0.3, 1.0, 5))
            out[ch] = _nrm(y) + 0.25 * _nrm(dsp.lowpass(dsp.brown(n, r), 220, 2)) + \
                0.15 * _nrm(dsp.bandpass(dsp.pink(n, r), 1000, 8000, 2))
        else:
            out[ch] = _nrm(_grains(r, n, rate * 2.0, 300, 2500, 0.001, 0.004, 0.6)) + \
                0.4 * _nrm(dsp.lowpass(dsp.pink(n, r), 1200, 2))
    trickle = _bubble_field(r, n, 45.0 * intensity, 900, 2600, bands=10)
    return out + 0.25 * dsp.pan_mono(_nrm(dsp.lowpass(trickle, 4000, 2)), r.choice([-0.7, 0.7]))


@sound("rain_on_roof", "rain heard under a roof (roof tin | shingle): drops drumming overhead, a gutter trickling",
       True, dur=4.0, roof="tin", intensity=1.0)
def rain_on_roof(r, dur, roof, intensity):
    n = n_of(dur)
    return _roof_rain(r, n, roof, intensity) * _texture_env(n)


def _rolls(r, n, count, spread, lp, rise=(0.3, 0.8), decay=(1.0, 2.5)):
    """rolling thunder: overlapping swells of low-passed brown noise"""
    t = t_axis(n)
    y = np.zeros(n)
    for _ in range(count):
        at = r.uniform(0.0, spread)
        env = np.clip((t - at) / r.uniform(*rise), 0.0, 1.0) ** 2 * np.exp(-np.maximum(t - at, 0.0) / r.uniform(*decay))
        y += r.uniform(0.4, 1.0) * dsp.lowpass(dsp.brown(n, r), lp, 2) * env
    return y


@sound("thunder_clap", "a lightning strike close by: a tearing crack, a huge boom and the roll that follows", True)
def thunder_clap(r):
    n = n_of(6.0)
    t = t_axis(n)
    out = np.zeros((2, n))
    m = n_of(0.02)
    for ch in range(2):
        crack = np.zeros(n)
        times = np.sort(r.exponential(0.06, 40))
        for at, a in zip(times, np.exp(-times / 0.12) * r.uniform(0.3, 1.0, 40)):
            _place(crack, a * dsp.highpass(r.standard_normal(m), 400, 2) * np.exp(-t_axis(m) / 0.003), at)
        boom = dsp.lowpass(dsp.brown(n, r), 120, 2) * (1.0 - np.exp(-t / 0.03)) * np.exp(-t / 1.1)
        roll = _rolls(r, n, 4, 2.5, 250, (0.2, 0.6), (0.8, 1.6))
        out[ch] = 0.9 * _nrm(crack) + _nrm(boom) + 0.7 * _nrm(roll)
    return _space(dsp.fade(out, 0.0, 1.0), "field", 0.3)


@sound("thunder_rumble", "distant thunder: a long low roll that swells and fades away", True, dur=7.0)
def thunder_rumble(r, dur):
    n = n_of(dur)
    out = np.zeros((2, n))
    for ch in range(2):
        out[ch] = _nrm(_rolls(r, n, 6, dur * 0.45, r.uniform(120, 180)) + 0.5 * _rolls(r, n, 2, dur * 0.3, 60))
    return dsp.fade(out, 0.0, dur * 0.25)


@sound("ice_crack", "lake ice cracking in the cold: sharp snaps and the eerie 'pew' of waves racing through the ice",
       True, cracks=4)
def ice_crack(r, cracks):
    out = np.zeros((2, n_of(cracks * 0.6 + 1.0)))
    at = 0.05
    for _ in range(int(cracks)):
        pan = r.uniform(-0.7, 0.7)
        y = np.zeros(n_of(0.6))
        for path in range(2):
            # flexural waves are dispersive (group velocity ~ sqrt(f)): the highs arrive first, f(t) ~ (t1 / t)^2
            f_hi, f_lo, t1 = r.uniform(4000, 7000), r.uniform(250, 450), r.uniform(0.02, 0.05) * (1.0 + 0.4 * path)
            m = n_of(t1 * np.sqrt(f_hi / f_lo) - t1 + 0.04)
            tt = t1 + t_axis(m)
            f = np.clip(f_hi * (t1 / tt) ** 2, f_lo, None)
            env = _env([(0, 0), (0.003, 1), (m / SR * 0.7, 0.6), (m / SR, 0)], m)
            pew = np.sin(TWO_PI * dsp.phase_cycles(f, m)) * (t1 / tt) ** 0.5 * env
            _place(y, (1.0, 0.5)[path] * pew, 0.004 + 0.01 * path)
        snap = dsp.highpass(r.standard_normal(n_of(0.004)), 1500, 2) * np.exp(-t_axis(n_of(0.004)) / 0.0008)
        _place(y, 0.8 * _nrm(snap), 0.0)
        _place(out, dsp.pan_mono(_nrm(y), pan), at, r.uniform(0.6, 1.0))
        at += r.uniform(0.25, 0.7)
    return _space(out, "hall", 0.35)


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


def _latch(r, g=1.0, pitch=1.0):
    """a latch, bolt or catch: a sharp metal click, a short ring of the bolt and plate, a knock of the body"""
    m = n_of(0.14)
    y = _nrm(dsp.modal(r.uniform(1900, 2700) * pitch * np.array([1.0, 2.31, 3.86]), [1.0, 0.5, 0.25],
                       [0.05, 0.032, 0.02], m, r=r))
    k = n_of(0.003)
    y[:k] += 0.9 * _nrm(dsp.bandpass(r.standard_normal(k), 3000, 10000, 2))
    return g * (y + 0.35 * _nrm(_thump(r, 240 * pitch, 0.14, 0.012, 0.3, 0.3)))


@sound("door_open", "a door opening: handle, latch, the swing of air and a short hinge creak (creak 0 .. 1)", True,
       creak=0.4, weight=1.0)
def door_open(r, creak, weight):
    dur = 1.4
    n = n_of(dur)
    y = np.zeros(n)
    _place(y, _latch(r, 0.7, 0.9), 0.0)
    _place(y, _latch(r, 1.0, 1.1), 0.17 + r.uniform(-0.02, 0.03))
    swing = dsp.lowpass(dsp.pink(n, r), 300 + 150 * weight, 2) * _env([(0, 0), (0.22, 0), (0.5, 1.0), (1.1, 0.3),
                                                                        (dur, 0)], n)
    y += 0.4 * weight * _nrm(swing)
    if creak > 0:
        c = _creak(r, 0.75, 35, 110, (600 * r.uniform(0.85, 1.15), 1400 * r.uniform(0.85, 1.15)))
        _place(y, 0.7 * creak * _nrm(dsp.highpass(c, 150, 2)), 0.26)
    return _space(_stereo(y, 0.0, 0.25, r), "room", 0.18)


@sound("door_close", "a door swinging shut: a push of air, the thump into the frame and the latch catching", True,
       force=0.6)
def door_close(r, force):
    n = n_of(0.9)
    y = np.zeros(n)
    y += 0.3 * _nrm(dsp.lowpass(dsp.pink(n, r), 250, 2) * _env([(0, 0), (0.12, 1.0), (0.2, 0.0), (0.9, 0)], n))
    body = _modal_hit(r, np.array([82, 165, 250, 390, 610]) * r.uniform(0.92, 1.08), [1.0, 0.7, 0.45, 0.3, 0.15],
                      [0.22, 0.16, 0.12, 0.08, 0.05], 0.6, noise=(400, 3500, 0.5, 0.006))
    _place(y, (0.5 + 0.5 * force) * body, 0.2)
    _place(y, _latch(r, 0.55 + 0.3 * force, 1.05), 0.2 + r.uniform(0.008, 0.02))
    return _space(_stereo(y, 0.0, 0.2, r), "room", 0.2)


@sound("door_slam", "a door slammed: a heavy boom, the latch, the frame and pictures rattling", True, force=1.0)
def door_slam(r, force):
    n = n_of(1.4)
    y = 0.25 * _nrm(dsp.lowpass(dsp.pink(n, r), 300, 2) * _env([(0, 0), (0.09, 1.0), (0.13, 0.0), (1.4, 0)], n))
    at = 0.13
    boom = _modal_hit(r, np.array([58, 117, 176, 260, 420, 700]) * r.uniform(0.94, 1.06),
                      [1.0, 0.8, 0.55, 0.4, 0.25, 0.12], [0.4, 0.3, 0.22, 0.15, 0.1, 0.06], 1.0,
                      noise=(300, 5000, 0.8, 0.01))
    _place(y, boom, at)
    _place(y, 0.9 * _thump(r, 50, 1.0, 0.12, 0.6, 0.6), at)
    _place(y, _latch(r, 0.8, 0.95), at + 0.006)
    m = n_of(0.8)
    rattle = dsp.modal(r.uniform(900, 5200, 8), r.uniform(0.3, 1.0, 8), r.uniform(0.08, 0.3, 8), m, r=r)
    rattle *= 1.0 + 0.8 * np.sin(TWO_PI * r.uniform(18, 26) * t_axis(m))
    _place(y, 0.2 * force * _nrm(rattle), at + 0.01)
    return _space(_stereo(y * (0.6 + 0.4 * force), 0.0, 0.3, r), "room", 0.35)


@sound("drawer", "a wooden drawer sliding open (action open | close): runners, rattling contents, the stop", True,
       action="open", contents=0.5)
def drawer(r, action, contents):
    slide = 0.45 if action == "open" else 0.35
    n = n_of(slide + 0.5)
    env = _env([(0, 0), (0.04, 1.0), (slide * 0.8, 0.8), (slide, 0.0), (n / SR, 0)], n)
    y = 0.6 * _nrm(dsp.bandpass(r.standard_normal(n), 300, 3000, 2) * env * (0.6 + 0.4 * dsp.ctrl_noise(n, r, 25.0)))
    rub = _creak(r, slide, 90, 220, (420, 1250))
    y[:len(rub)] += 0.35 * _nrm(rub)
    if contents > 0:
        x = np.where(r.random(n) < contents * 90.0 / SR * env, r.uniform(0.3, 1.0, n), 0.0)
        rattle = dsp.resonator_bank(x, r.uniform(1500, 6000, 5), r.uniform(0.02, 0.08, 5), r.uniform(0.3, 1.0, 5))
        if np.any(rattle):
            y += 0.3 * _nrm(rattle)
    stop = _modal_hit(r, np.array([140, 330, 560, 900]) * r.uniform(0.9, 1.1), [1.0, 0.7, 0.4, 0.2],
                      [0.12, 0.09, 0.06, 0.04], 0.4, noise=(800, 5000, 0.5, 0.002))
    _place(y, (0.6 if action == "open" else 1.0) * stop, slide - 0.01)
    return _space(_stereo(y, 0.0, 0.25, r), "room", 0.15)


@sound("light_switch", "a wall light switch flicked (state on | off): the spring snap and the plastic plate",
       state="on")
def light_switch(r, state):
    n = n_of(0.12)
    p = 1.0 if state == "on" else 0.9
    y = _nrm(dsp.modal(np.array([2600, 4100, 6200]) * p * r.uniform(0.95, 1.05), [1.0, 0.6, 0.3],
                       [0.03, 0.02, 0.012], n, r=r))
    k = n_of(0.0015)
    y[:k] += 0.5 * _nrm(dsp.highpass(r.standard_normal(k), 2500, 2))
    y += 0.7 * _nrm(dsp.modal([r.uniform(450, 650), r.uniform(1100, 1500)], [1.0, 0.5], [0.05, 0.03], n, r=r))
    return y


@sound("clock_tick", "a ticking clock: the escapement's tick-tock in its case (kind wall | watch; rate in ticks/s)",
       ticks=6, rate=None, kind="wall")
def clock_tick(r, ticks, rate, kind):
    watch = kind == "watch"
    period = 1.0 / (rate or (5.0 if watch else 1.0))
    n = n_of(period * ticks + 0.3)
    y = np.zeros(n)
    modes = np.array([3300, 5200, 7600]) if watch else np.array([520, 1150, 1900, 2950])
    t60 = [0.012, 0.009, 0.006] if watch else [0.09, 0.06, 0.045, 0.03]
    m = n_of(0.2)
    for k in range(int(ticks)):
        tock = k % 2 == 1
        tick = np.zeros(m)
        for j, (dt, a) in enumerate(((0.0, 1.0), (r.uniform(0.004, 0.008), 0.55))):
            exc = np.zeros(m)
            exc[n_of(dt)] = a
            tick += dsp.resonator_bank(exc, modes * (0.88 if tock else 1.0) * r.uniform(0.99, 1.01, len(modes)), t60,
                                       [1.0, 0.6, 0.4, 0.25][:len(modes)])
        tick = _nrm(tick)
        tick[:n_of(0.002)] += 0.5 * _nrm(dsp.bandpass(r.standard_normal(n_of(0.002)), 4000, 11000, 2))
        _place(y, tick, k * period + r.normal(0.0, 0.001), 0.8 if tock else 1.0)
    return y


@sound("alarm_clock", "an alarm clock going off: twin bells under a buzzing hammer (kind bell) or beeps (kind digital)",
       dur=2.5, kind="bell")
def alarm_clock(r, dur, kind):
    n = n_of(dur + 1.0)
    if kind == "digital":
        y = np.zeros(n)
        f = r.uniform(2700, 3100)
        for g in np.arange(0.0, dur, 1.0):
            for j in range(4):
                b = _beep(r, f, f, 0.06, "square")
                _place(y, b, g + 0.11 * j)
        return y
    rate = r.uniform(17.0, 21.0)
    times = np.arange(0.0, dur, 1.0 / rate) + np.abs(r.normal(0.0, 0.0012, int(np.ceil(dur * rate))))
    amps = r.uniform(0.75, 1.0, len(times))
    f1 = r.uniform(2300, 2700)
    y = np.zeros(n)
    for b, f in enumerate((f1, f1 * r.uniform(1.05, 1.12))):
        exc = _strikes(n, times[b::2], amps[b::2])
        y += dsp.resonator_bank(exc, [f * p[0] for p in _BELL], [1.1 * p[2] for p in _BELL], [p[1] for p in _BELL])
    hammer = _strikes(n, times, amps)
    buzz = dsp.resonator_bank(hammer, r.uniform(700, 1600, 3), [0.01, 0.008, 0.006], [1.0, 0.6, 0.4])
    return _nrm(y) + 0.25 * _nrm(buzz)


@sound("phone_ring", "a telephone ringing: the twin-gong bell of a classic phone (kind classic) or a marimba ringtone "
       "(kind mobile)", True, rings=2, kind="classic")
def phone_ring(r, rings, kind):
    if kind == "mobile":
        from codecinema.audio import instruments
        motif = [(0.0, 76), (0.14, 83), (0.28, 88), (0.42, 86), (0.7, 83), (0.84, 88)]
        out = np.zeros((2, n_of(1.6 * rings + 1.2)))
        for k in range(int(rings)):
            for j, (at, p) in enumerate(motif):
                dsp.place(out, instruments.play("marimba", p, 0.4, 0.75, seed=j), n_of(1.6 * k + at))
        return out
    on, gap = 1.0, 1.1
    n = n_of(rings * (on + gap) + 0.6)
    f1 = r.uniform(950, 1150)
    rate = r.uniform(19.0, 21.0)
    y = np.zeros(n)
    for b, f in enumerate((f1, f1 * r.uniform(1.18, 1.27))):
        times = [k * (on + gap) + j / rate for k in range(int(rings)) for j in range(b, int(on * rate), 2)]
        exc = _strikes(n, times, r.uniform(0.8, 1.0, len(times)))
        y += dsp.resonator_bank(exc, [f * p[0] for p in _BELL], [0.8 * p[2] for p in _BELL], [p[1] for p in _BELL])
    return _space(_nrm(y), "room", 0.15)


@sound("phone_vibrate", "a phone vibrating (surface table | pocket): the motor buzz rattling the case", pulses=3,
       surface="table")
def phone_vibrate(r, pulses, surface):
    on, off = 0.42, 0.28
    n = n_of(pulses * (on + off) + 0.15)
    gate = np.zeros(n)
    for k in range(int(pulses)):
        gate += _env([(0, 0), (k * (on + off), 0), (k * (on + off) + 0.03, 1.0), (k * (on + off) + on, 1.0),
                      (k * (on + off) + on + 0.06, 0.0), (n / SR, 0)], n)
    f = r.uniform(150, 185) * (0.75 + 0.25 * gate)
    ph = dsp.phase_cycles(f, n)
    hum = np.sin(TWO_PI * ph) + 0.3 * np.sin(TWO_PI * 2 * ph)
    x = _ticks(r, f, n, 0.25) * gate
    if surface == "table":
        rattle = dsp.resonator_bank(x, [r.uniform(260, 340), r.uniform(850, 1100), r.uniform(2000, 2600),
                                        r.uniform(3600, 4400)], [0.03, 0.02, 0.012, 0.008], [1.0, 0.8, 0.5, 0.3])
        y = 0.45 * _nrm(hum) + _nrm(rattle)
    else:
        thud = dsp.resonator_bank(x, [300, 700], [0.02, 0.01], [1.0, 0.5])
        y = dsp.lowpass(0.8 * _nrm(hum) + 0.3 * _nrm(thud), 900, 2)
    return y * gate


def _key_stroke(r, kind, space=False):
    """one key: keyboard (press clack, lighter release) or typewriter (type bar on the platen, escapement tick)"""
    m = n_of(0.22)
    y = np.zeros(m)
    if kind == "typewriter":
        if not space:
            strike = _modal_hit(r, [r.uniform(170, 230), r.uniform(1800, 2600), r.uniform(3600, 4800)], [0.6, 1.0, 0.5],
                                [0.05, 0.04, 0.025], 0.2, noise=(1500, 9000, 1.2, 0.002))
            _place(y, strike, 0.0)
        tick = dsp.modal([r.uniform(2800, 3300), r.uniform(5000, 6000)], [1.0, 0.5], [0.02, 0.012], n_of(0.06), r=r)
        _place(y, 0.35 * _nrm(tick), 0.03 if not space else 0.0)
        return y
    f = r.uniform(0.85, 1.15)
    body = [200, 520, 900] if space else [380, 1700 * f, 3900 * f]
    press = _modal_hit(r, body, [1.0, 0.8, 0.45] if space else [0.6, 1.0, 0.5], [0.04, 0.025, 0.015], 0.12,
                       noise=(1500, 8000, 0.5, 0.0015))
    _place(y, press, 0.0)
    rel = _modal_hit(r, [b * 1.15 for b in body], [0.5, 1.0, 0.6], [0.02, 0.015, 0.01], 0.08,
                     noise=(2000, 8000, 0.4, 0.001))
    _place(y, 0.35 * rel, r.uniform(0.055, 0.095))
    if space:
        _place(y, 0.3 * _latch(r, 0.4, 1.4), 0.006)
    return y


@sound("typing", "typing (kind keyboard | typewriter): bursts of keystrokes, the space bar, pauses between words", True,
       dur=2.5, speed=1.0, kind="keyboard")
def typing(r, dur, speed, kind):
    n = n_of(dur + 1.2)
    out = np.zeros((2, n))
    t = r.uniform(0.02, 0.08)
    while t < dur:
        for _ in range(int(r.integers(2, 8))):
            if t >= dur:
                break
            _place(out, dsp.pan_mono(_key_stroke(r, kind), r.uniform(-0.35, 0.35)), t, r.uniform(0.6, 1.0))
            t += r.gamma(4.0, 0.035) / speed
        if t < dur:
            _place(out, dsp.pan_mono(_key_stroke(r, kind, space=True), 0.0), t, 0.9)
        t += r.uniform(0.15, 0.55) / speed
    if kind == "typewriter" and dur >= 2.0:
        bell = _bell(r, r.uniform(2500, 2800), n_of(1.0), 0.9)
        _place(out, dsp.pan_mono(0.6 * _nrm(bell), 0.3), dur + 0.05)
        k = n_of(0.45)
        clicks = _strikes(k, np.cumsum(np.linspace(0.04, 0.012, 22)), np.ones(22))
        ret = dsp.resonator_bank(clicks, [2200, 3700, 5400], [0.02, 0.015, 0.01], [1.0, 0.6, 0.3])
        _place(out, dsp.pan_mono(0.7 * _nrm(ret), 0.4), dur + 0.25)
    return _space(out, "room", 0.12)


def _micro_click(r, g, pitch):
    m = n_of(0.05)
    y = _nrm(dsp.modal(np.array([3800, 5600, 8200]) * pitch * r.uniform(0.97, 1.03), [1.0, 0.6, 0.3],
                       [0.02, 0.012, 0.008], m, r=r))
    y += 0.6 * _nrm(dsp.modal([r.uniform(900, 1300)], [1.0], [0.03], m, r=r))
    y[:n_of(0.001)] += 0.4 * _nrm(dsp.bandpass(r.standard_normal(n_of(0.001)), 3000, 11000, 2))
    return g * y


@sound("mouse_click", "a computer mouse button pressed and released (clicks 2 = a double click)", clicks=1)
def mouse_click(r, clicks):
    y = np.zeros(n_of(0.2 + 0.14 * clicks))
    for k in range(int(clicks)):
        _place(y, _micro_click(r, 1.0, 1.0), 0.13 * k)
        _place(y, _micro_click(r, 0.45, 1.15), 0.13 * k + r.uniform(0.06, 0.085))
    return y


@sound("camera_shutter", "a mechanical camera: mirror slap and shutter curtains (winder: the film-advance motor)", True,
       winder=False)
def camera_shutter(r, winder):
    n = n_of(0.5 + (0.45 if winder else 0.0))
    y = np.zeros(n)
    mirror = _modal_hit(r, [r.uniform(160, 220), r.uniform(700, 900), r.uniform(1400, 1800)], [1.0, 0.8, 0.5],
                        [0.04, 0.03, 0.02], 0.15, noise=(1000, 6000, 0.6, 0.002))
    _place(y, mirror, 0.0)
    for at in (0.032, 0.032 + r.uniform(0.012, 0.02)):                # the two curtains
        curtain = _modal_hit(r, [r.uniform(2600, 3200), r.uniform(5200, 6400)], [1.0, 0.5], [0.015, 0.01], 0.06,
                             noise=(3000, 10000, 1.0, 0.0008))
        _place(y, 0.7 * curtain, at)
    _place(y, 0.6 * mirror, 0.085)
    if winder:
        k = n_of(0.38)
        tt = t_axis(k)
        f = 1400 * (1.0 + 0.35 * dsp.smoothstep(tt / 0.08)) * (1.0 - 0.3 * dsp.smoothstep((tt - 0.28) / 0.1))
        whir = dsp.bandpass(dsp.osc_saw(f, k), 800, 5000, 2) + 0.5 * _grains(r, k, 500, 2000, 8000)
        _place(y, 0.4 * _nrm(whir * _env([(0, 0), (0.02, 1), (0.34, 1), (0.38, 0)], k)), 0.2)
    return _stereo(y, 0.0, 0.2, r)


def _handling(r, n, bursts, rate=4.0):
    """a positive envelope of a few hand gestures (rustling, shaking)"""
    return np.clip(dsp.ctrl_noise(n, r, rate) + 0.4, 0.0, None) ** 1.3 * _env([(0, 0), (0.05, 1), (n / SR - 0.08, 1),
                                                                               (n / SR, 0)], n) * bursts


@sound("paper_rustle", "a sheet of paper handled and crumpled (stiffness 0 soft .. 1 crisp)", True, dur=1.2,
       stiffness=0.5)
def paper_rustle(r, dur, stiffness):
    n = n_of(dur)
    out = np.zeros((2, n))
    env = _handling(r, n, 1.0)
    for ch in range(2):
        crackle = _grains(r, n, (300 + 1500 * stiffness) * env, 1200, 9000, 0.0003, 0.003, 0.6 + 0.4 * stiffness)
        swish = dsp.bandpass(r.standard_normal(n), 800, 6000, 2) * env
        out[ch] = _nrm(crackle) + 0.25 * _nrm(swish)
    return out


@sound("page_turn", "a book page turned: the lift, the flutter of the flip and the soft landing", True)
def page_turn(r):
    n = n_of(0.8)
    t = t_axis(n)
    y = 0.4 * _nrm(_grains(r, n, 800, 1500, 8000, 0.0003, 0.002) * _env([(0, 0), (0.03, 1), (0.15, 0), (0.8, 0)], n))
    fc = 700 + 2200 * np.sin(np.pi * np.clip((t - 0.12) / 0.38, 0, 1)) ** 2
    flip = dsp.tv_biquad(r.standard_normal(n), "bp", fc, 1.5, block=128) * \
        _env([(0, 0), (0.12, 0), (0.3, 1), (0.48, 0.4), (0.52, 0), (0.8, 0)], n)
    flip *= 1.0 + 0.5 * np.sin(TWO_PI * 26.0 * t) * np.exp(-np.maximum(t - 0.12, 0) / 0.2)
    y += _nrm(flip)
    land = _burst(r, n_of(0.2), 300, 3000, 0.012, 0.001)
    _place(y, 0.6 * _nrm(land), 0.5)
    return _stereo(y, 0.0, 0.5, r)


@sound("book_close", "a book clapped shut: pages riffle, then the covers meet in a papery thump and a puff of air",
       weight=1.0)
def book_close(r, weight):
    n = n_of(0.6)
    t = t_axis(n)
    riffle = _grains(r, n, 1500 * (0.3 + t / 0.15), 1500, 8000, 0.0004, 0.002) * _env([(0, 0), (0.05, 1), (0.15, 1),
                                                                                       (0.16, 0), (0.6, 0)], n)
    y = 0.4 * _nrm(riffle)
    k = n_of(0.45)
    thump = _thump(r, 140 / weight ** 0.3, 0.45, 0.03, 0.4, 0.8)
    thump += 0.6 * _modal_hit(r, [r.uniform(200, 260), r.uniform(450, 560), r.uniform(850, 1000)], [1.0, 0.6, 0.3],
                              [0.06, 0.04, 0.03], 0.45, noise=(300, 4000, 0.6, 0.004))
    thump[:n_of(0.05)] += 0.4 * _nrm(dsp.lowpass(r.standard_normal(n_of(0.05)), 700, 2))
    _place(y, _nrm(thump[:k]), 0.15)
    return y


@sound("zipper", "a zipper pulled (direction up | down): the slider ticking over the teeth, quickest mid-pull",
       dur=0.7, direction="up")
def zipper(r, dur, direction):
    n = n_of(dur + 0.05)
    t = t_axis(n)
    u = np.clip(t / dur, 0.0, 1.0)
    speed = (0.25 + 0.75 * dsp.smoothstep(u / 0.7)) * (1.0 - dsp.smoothstep((u - 0.88) / 0.12))
    x = _ticks(r, speed * r.uniform(260, 380), n)
    p = 1.0 if direction == "up" else 0.92
    teeth = dsp.resonator_bank(x * speed, np.array([2100, 3700, 5900]) * p, [0.012, 0.009, 0.006], [1.0, 0.7, 0.4])
    rub = dsp.bandpass(r.standard_normal(n), 1500, 7000, 2) * speed ** 2
    return _nrm(teeth) + 0.2 * _nrm(rub)


@sound("keys_jingle", "a bunch of keys jingling on their ring", True, dur=1.0, intensity=1.0)
def keys_jingle(r, dur, intensity):
    n = n_of(dur + 0.5)
    out = np.zeros((2, n))
    env = _handling(r, n_of(dur), 1.0, 5.0)
    t = 0.0
    while t < dur:
        e = float(env[min(len(env) - 1, n_of(t))])
        if e > 0.05:
            f = r.uniform(2400, 7500)
            m = n_of(0.4)
            ping = dsp.modal([f, f * r.uniform(2.3, 2.9)], [1.0, 0.4], [r.uniform(0.08, 0.35), 0.06], m, r=r)
            if r.uniform() < 0.15:
                ping += dsp.modal([r.uniform(1200, 1800)], [0.7], [0.5], m, r=r)
            _place(out, dsp.pan_mono(ping, r.uniform(-0.5, 0.5)), t, e * r.uniform(0.3, 1.0))
        t += r.exponential(1.0 / (70.0 * intensity))
    return out


@sound("glass_clink", "two glasses touched in a toast (material glass) or two mugs knocked together (material mug)",
       True, material="glass")
def glass_clink(r, material):
    if material == "mug":
        n = n_of(0.6)
        y = _modal_hit(r, r.uniform(1300, 1900) * np.array([1.0, 2.2, 3.6, 5.1]), [1.0, 0.5, 0.3, 0.15],
                       [0.25, 0.15, 0.1, 0.07], 0.6, noise=(800, 6000, 0.5, 0.002))
        y += 0.4 * _nrm(_thump(r, 420, 0.6, 0.02, 0.2, 0.3))
        return _stereo(y, 0.0)
    n = n_of(3.0)
    out = np.zeros((2, n))
    f = r.uniform(800, 1150)
    for k, (fk, pan) in enumerate(((f, -0.2), (f * r.uniform(1.12, 1.35), 0.2))):
        ratios = np.array([1.0, 2.32, 4.25, 6.63])
        fr = np.concatenate([fk * ratios, fk * ratios + r.uniform(0.4, 1.6, 4)])
        g = np.tile([1.0, 0.45, 0.22, 0.1], 2) * np.repeat([1.0, 0.7], 4)
        y = dsp.modal(fr, g, np.tile([2.6, 1.2, 0.6, 0.35], 2), n, r=r, attack=0.0003)
        y[:n_of(0.002)] += 0.3 * dsp.peak(y) * _nrm(dsp.highpass(r.standard_normal(n_of(0.002)), 5000, 2))
        out += dsp.pan_mono(_nrm(y) * (1.0 if k == 0 else 0.8), pan)
    return out


@sound("pour_water", "water poured into a glass: the stream, bubbles, and the air column ringing higher as it fills",
       True, dur=2.5)
def pour_water(r, dur):
    n = n_of(dur + 0.5)
    t = t_axis(n)
    flow = _env([(0, 0), (0.06, 1.0), (dur - 0.12, 1.0), (dur, 0.0), (n / SR, 0)], n)
    fill = np.clip(t / dur, 0.0, 1.0)
    fc = C_AIR / (4.0 * (0.13 * (1.0 - 0.85 * fill) + 0.012))
    stream = dsp.bandpass(r.standard_normal(n), 500, 6000, 2) * (1.0 + 0.5 * dsp.ctrl_noise(n, r, 10.0))
    cavity = dsp.tv_biquad(stream, "bp", fc, 14.0, block=64)
    bubbles = _bubble_field(r, n, 140.0 * flow, 600, 3200)
    y = (_nrm(cavity) + 0.18 * _nrm(stream) + 0.35 * _nrm(bubbles)) * flow
    for _ in range(3):
        _place(y, 0.25 * _bubble(r, r.uniform(1400, 2600)), dur + r.uniform(0.05, 0.3))
    return _stereo(y, 0.0, 0.3, r)


@sound("doorbell", "a doorbell chime: 'ding-dong' on two tone bars", True, pitch=1.0)
def doorbell(r, pitch):
    n = n_of(4.2)
    y = np.zeros(n)
    for at, f in ((0.0, 659.3 * pitch), (0.55, 523.3 * pitch)):
        m = n - n_of(at)
        bar = dsp.modal([f, f * 1.0018, f * 2.756, f * 5.404], [1.0, 0.6, 0.25, 0.06], [2.4, 2.3, 0.9, 0.4], m, r=r)
        bar[:n_of(0.03)] += 0.15 * dsp.peak(bar) * _nrm(_thump(r, 180, 0.03, 0.006, 0.2, 0.5))
        _place(y, _nrm(bar), at)
    return _space(_stereo(y, 0.0, 0.2, r), "room", 0.2)


# ================================================================================================ animals
def _calls(r, count, make, gap, tail=0.4):
    """several calls in a row: make(r, k) -> mono clip, gap(r, k) -> silence before the next one (s)"""
    clips, t = [], 0.0
    for k in range(int(count)):
        c = make(r, k)
        clips.append((t, c))
        t += len(c) / SR + gap(r, k)
    y = np.zeros(max(n_of(at) + len(c) for at, c in clips) + n_of(tail))
    for at, c in clips:
        _place(y, c, at)
    return y


def _bark(r, size):
    d = r.uniform(0.11, 0.16) * size ** 0.35
    n = n_of(d + 0.04)
    t = t_axis(n)
    u = np.clip(t / d, 0.0, 1.0)
    f = r.uniform(420, 560) / size ** 0.85 * (0.85 + 0.35 * np.sin(np.pi * np.clip(u * 1.6, 0, 1)) - 0.25 * u)
    k = 1.0 / size ** 0.45
    o = np.sin(np.pi * np.clip(t / (d * 1.05), 0, 1)) ** 0.6
    bands = [(k * (350 + 450 * o), 3.0, 1.0), (k * (1050 + 350 * o), 4.0, 0.6), (k * 2500, 5.0, 0.3),
             (k * 3500, 6.0, 0.15)]
    env = _env([(0, 0), (0.006, 1.0), (d * 0.45, 0.8), (d, 0.0), (n / SR, 0)], n)
    return _call(r, f, n / SR, bands, env, tilt=2500, jitter=0.03, shimmer=0.15, breath=0.3, rough=0.45)


@sound("dog_bark", "a dog barking (size 0.5 small .. 1.5 big)", True, barks=2, size=1.0)
def dog_bark(r, barks, size):
    y = _calls(r, barks, lambda rr, k: _bark(rr, size * rr.uniform(0.95, 1.05)) * rr.uniform(0.8, 1.0),
               lambda rr, k: rr.uniform(0.12, 0.25) * size ** 0.3)
    return _space(_stereo(y, 0.0), "field", 0.15)


@sound("dog_whine", "a dog whining: high nasal whimpers rising and falling", True, whines=2, size=1.0)
def dog_whine(r, whines, size):
    def whine(rr, k):
        d = rr.uniform(0.5, 0.9)
        n = n_of(d)
        t = t_axis(n)
        u = t / d
        f0 = rr.uniform(700, 1000) / size ** 0.5
        wobble = 1.0 + 0.012 * np.sin(TWO_PI * rr.uniform(5, 7) * t)
        f = f0 * (1.0 + 0.25 * np.sin(np.pi * u) ** 1.5 - 0.15 * u) * wobble
        src = _voiced(rr, f, n, tilt=900.0, jitter=0.01, shimmer=0.08, breath=0.25)
        y = dsp.lowpass(src, 2.0 * f0, 2) + 0.25 * _formants(src, [(1200 / size ** 0.4, 3.0, 1.0)])
        return y * _env([(0, 0), (0.06, 1.0), (d * 0.7, 0.8), (d, 0.0)], n)
    return _space(_stereo(_calls(r, whines, whine, lambda rr, k: rr.uniform(0.15, 0.35)), 0.0), "room", 0.15)


@sound("cat_meow", "a cat meowing 'mi-a-ow' (size 0.6 kitten .. 1.2 big cat)", True, meows=1, size=1.0)
def cat_meow(r, meows, size):
    def meow(rr, k):
        d = rr.uniform(0.55, 0.85) * size ** 0.5
        n = n_of(d)
        u = t_axis(n) / d
        rise = np.sin(np.pi * np.clip(u * 1.25, 0, 1)) ** 0.8
        f = rr.uniform(480, 620) / size ** 0.7 * (0.85 + 0.45 * rise - 0.1 * u)
        k_ = 1.5 / size ** 0.5
        f1 = k_ * np.interp(u, [0, 0.15, 0.4, 0.75, 1], [300, 350, 750, 500, 380])
        f2 = k_ * np.interp(u, [0, 0.15, 0.4, 0.75, 1], [1500, 2100, 1250, 900, 800])
        env = _env([(0, 0), (0.04, 0.6), (d * 0.3, 1.0), (d * 0.75, 0.8), (d, 0.0)], n)
        return _call(rr, f, d, [(f1, 4.0, 1.0), (f2, 5.0, 0.6), (k_ * 2500, 6.0, 0.3)], env, tilt=1500.0, jitter=0.015,
                     shimmer=0.08, breath=0.12, rough=0.1)
    return _space(_stereo(_calls(r, meows, meow, lambda rr, k: rr.uniform(0.3, 0.6)), 0.0), "room", 0.12)


@sound("cat_purr", "a cat purring: a soft rhythmic rumble on the out- and in-breath", True, dur=3.0)
def cat_purr(r, dur):
    n = n_of(dur)
    t = t_axis(n)
    cyc = (t / r.uniform(1.9, 2.3) + r.uniform()) % 1.0
    out_breath = cyc < 0.55
    sw = np.clip(np.sin(np.pi * np.where(out_breath, cyc / 0.55, (cyc - 0.55) / 0.45)), 0.0, 1.0) ** 0.6
    breath = np.where(out_breath, sw, 0.6 * sw)
    rate = dsp.onepole(np.where(out_breath, 24.0, 27.0), 4.0) * (1.0 + 0.03 * dsp.ctrl_noise(n, r, 2.0))
    pulses = (0.5 + 0.5 * np.cos(TWO_PI * dsp.phase_cycles(rate, n, r.uniform()))) ** 10
    exc = pulses * (0.6 + r.standard_normal(n))
    y = _formants(exc, [(220, 2.0, 1.0), (600, 2.5, 0.5), (1200, 3.0, 0.2)]) + 0.4 * dsp.lowpass(pulses, 150, 2)
    y = dsp.lowpass(y, 1600, 2) * dsp.onepole(breath, 20.0)
    return _stereo(dsp.fade(y, 0.15, 0.3), 0.0, 0.2, r)


def _tweet(f, d, harm=0.18):
    """a bird note: syrinx tone following f (array), a whisper of a second harmonic, smooth ends"""
    n = len(f)
    ph = dsp.phase_cycles(f, n)
    u = t_axis(n) / max(d, 1e-3)
    return (np.sin(TWO_PI * ph) + harm * np.sin(TWO_PI * 2 * ph)) * np.sin(np.pi * np.clip(u, 0, 1)) ** 0.8


@sound("sparrow_chirp", "a sparrow's chirps: quick bright 'cheep' notes", True, chirps=4)
def sparrow_chirp(r, chirps):
    def cheep(rr, k):
        d = rr.uniform(0.045, 0.09)
        n = n_of(d)
        u = t_axis(n) / d
        f = rr.uniform(4200, 5600) * (1.0 - 0.4 * u) * (1.0 + 0.15 * np.sin(np.pi * u))
        return _tweet(f, d, 0.25) + 0.05 * dsp.bandpass(rr.standard_normal(n), 3000, 9000, 2) * np.sin(np.pi * u)
    y = _calls(r, chirps, cheep, lambda rr, k: rr.uniform(0.06, 0.22), 0.2)
    return _space(_stereo(y, r.uniform(-0.3, 0.3)), "field", 0.12)


@sound("songbird", "a songbird's phrase: clear whistles, a trill and a final flourish", True)
def songbird(r):
    parts, t = [], 0.0
    base = r.uniform(2800, 4200)
    for _ in range(int(r.integers(2, 4))):                          # opening whistles
        d = r.uniform(0.12, 0.28)
        u = np.linspace(0.0, 1.0, n_of(d))
        parts.append((t, _tweet(base * r.uniform(0.9, 1.2) * (1.0 + r.uniform(-0.12, 0.12) * u), d)))
        t += d + r.uniform(0.04, 0.12)
    rate, reps = r.uniform(12, 20), int(r.integers(6, 12))         # the trill
    f_tr = base * r.uniform(1.0, 1.4)
    for j in range(reps):
        d = 0.55 / rate
        u = np.linspace(0.0, 1.0, n_of(d))
        parts.append((t, 0.8 * _tweet(f_tr * (1.15 - 0.3 * u), d, 0.1)))
        t += 1.0 / rate
    d = r.uniform(0.2, 0.35)                                        # the flourish
    u = np.linspace(0.0, 1.0, n_of(d))
    up = r.uniform() < 0.5
    parts.append((t + 0.05,
                  _tweet(base * (0.8 + 0.7 * (u if up else 1.0 - u)) * (1.0 + 0.04 * np.sin(TWO_PI * 30 * u * d)), d)))
    y = np.zeros(n_of(t + d + 0.5))
    for at, c in parts:
        _place(y, c, at)
    return _space(_stereo(y, r.uniform(-0.3, 0.3)), "field", 0.2)


@sound("crow_caw", "a crow cawing: harsh, nasal 'caw' calls", True, caws=3)
def crow_caw(r, caws):
    def caw(rr, k):
        d = rr.uniform(0.3, 0.45)
        n = n_of(d)
        u = t_axis(n) / d
        f = rr.uniform(480, 620) * (1.0 + 0.08 * np.sin(np.pi * u) - 0.12 * u)
        o = np.sin(np.pi * np.clip(u * 1.1, 0, 1)) ** 0.5
        env = _env([(0, 0), (0.015, 1.0), (d * 0.6, 0.85), (d, 0.0)], n)
        return _call(rr, f, d, [(800 + 450 * o, 3.0, 1.0), (1900, 4.0, 0.7), (3000, 5.0, 0.35)], env, tilt=3000.0,
                     jitter=0.04, shimmer=0.2, breath=0.35, rough=0.9)
    y = _calls(r, caws, caw, lambda rr, k: rr.uniform(0.25, 0.45))
    return _space(_stereo(y, r.uniform(-0.3, 0.3)), "field", 0.25)


@sound("owl_hoot", "a tawny owl calling: a long 'hooo', then 'hu-hu-hooo' with a tremble", True)
def owl_hoot(r):
    f0 = r.uniform(360, 440)
    y = np.zeros(n_of(3.0))
    for at, d, g, trem in ((0.0, 0.5, 1.0, 0.0), (1.1, 0.12, 0.7, 0.0), (1.3, 0.12, 0.75, 0.0), (1.5, 0.85, 0.9, 1.0)):
        n = n_of(d)
        t = t_axis(n)
        u = t / d
        f = f0 * (1.0 + 0.05 * np.sin(np.pi * u) - 0.04 * u) * \
            (1.0 + trem * 0.02 * np.sin(TWO_PI * 9.0 * t) * dsp.smoothstep((u - 0.3) / 0.3))
        ph = dsp.phase_cycles(f, n)
        tone = np.sin(TWO_PI * ph) + 0.08 * np.sin(TWO_PI * 2 * ph) + 0.02 * np.sin(TWO_PI * 3 * ph)
        tone += 0.06 * dsp.bandpass(r.standard_normal(n), 300, 1500, 2)
        _place(y, g * tone * np.sin(np.pi * u) ** (0.9 if d > 0.3 else 2.0), at)
    return _space(_stereo(y, r.uniform(-0.3, 0.3)), "field", 0.35)


@sound("rooster_crow", "a rooster crowing 'cock-a-doodle-doo'", True)
def rooster_crow(r):
    f0 = r.uniform(520, 640)
    vowels = {"a": (1100, 1800), "e": (900, 2300), "u": (650, 1300), "o": (850, 1500)}
    y = np.zeros(n_of(1.9))
    syllables = ((0.0, 0.11, 1.05, "a"), (0.14, 0.08, 1.0, "e"), (0.25, 0.16, 1.25, "u"), (0.44, 0.12, 1.15, "e"),
                 (0.6, 0.8, 1.35, "o"))           # cock - a - doo - dle - doooo
    for at, d, p, v in syllables:
        n = n_of(d)
        t = t_axis(n)
        u = t / d
        f = f0 * p * (1.0 + 0.05 * np.sin(np.pi * u) - (0.18 * u ** 2 if d > 0.5 else 0.06 * u))
        if d > 0.5:
            f = f * (1.0 + 0.015 * np.sin(TWO_PI * 22.0 * t))
        f1, f2 = vowels[v]
        env = _env([(0, 0), (0.012, 1.0), (d * 0.75, 0.9), (d, 0.0)], n)
        _place(y, _call(r, f, d, [(f1, 3.0, 1.0), (f2, 4.0, 0.7), (3500, 5.0, 0.3)], env, tilt=3500.0, jitter=0.03,
                        shimmer=0.15, breath=0.2, rough=0.6), at)
    return _space(_stereo(y, r.uniform(-0.2, 0.2)), "field", 0.3)


@sound("cow_moo", "a cow mooing: a nasal 'mmm' opening into a long 'ooo'", True)
def cow_moo(r):
    d = r.uniform(1.3, 1.9)
    n = n_of(d)
    u = t_axis(n) / d
    f = r.uniform(115, 145) * (1.0 + 0.25 * np.sin(np.pi * np.clip(u * 1.2, 0, 1)) ** 1.2 - 0.12 * u)
    o = dsp.smoothstep((u - 0.1) / 0.25) * (1.0 - 0.6 * dsp.smoothstep((u - 0.7) / 0.3))
    bands = [(250 + 300 * o, 3.0, 1.0), (800 + 250 * o, 4.0, 0.5), (2100, 5.0, 0.15), (260, 6.0, 0.6 * (1.0 - o))]
    env = _env([(0, 0), (0.15, 0.8), (d * 0.4, 1.0), (d * 0.8, 0.8), (d, 0.0)], n)
    y = _call(r, f, d, bands, env, tilt=1200.0, jitter=0.02, shimmer=0.1, breath=0.06, rough=0.25)
    return _space(_stereo(y, r.uniform(-0.2, 0.2)), "field", 0.25)


@sound("horse_neigh", "a horse neighing: a high whinny trembling downward, ending in a snort", True)
def horse_neigh(r):
    d = r.uniform(1.1, 1.5)
    n = n_of(d)
    t = t_axis(n)
    u = t / d
    trill = 1.0 + 0.1 * (1.0 - 0.6 * u) * np.sin(TWO_PI * dsp.phase_cycles(12.0 - 3.0 * u, n))
    f = r.uniform(900, 1100) * (1.0 - 0.55 * u ** 0.8) * trill
    bands = [(700 - 200 * u, 3.0, 1.0), (1800 - 500 * u, 4.0, 0.7), (2600, 5.0, 0.3)]
    env = _env([(0, 0), (0.03, 1.0), (d * 0.6, 0.75), (d, 0.0)], n)
    y = np.zeros(n_of(d + 0.5))
    _place(y, _call(r, f, d, bands, env, tilt=2500.0, jitter=0.03, shimmer=0.2, breath=0.25, rough=0.4), 0.0)
    k = n_of(0.3)
    tk = t_axis(k)
    snort = dsp.bandpass(r.standard_normal(k), 150, 1500, 2) * (1.0 + 0.6 * np.sin(TWO_PI * 30.0 * tk))
    _place(y, 0.5 * _nrm(snort * _env([(0, 0), (0.03, 1.0), (0.3, 0.0)], k)), d + 0.05)
    return _space(_stereo(y, r.uniform(-0.2, 0.2)), "field", 0.25)


def _hoof(r, surface):
    m = n_of(0.22)
    if surface == "cobble":
        y = _modal_hit(r, [r.uniform(500, 700), r.uniform(1100, 1400), r.uniform(2200, 2700)], [1.0, 0.7, 0.4],
                       [0.06, 0.045, 0.03], 0.22, noise=(2000, 7000, 0.6, 0.0015))
        return y + 0.5 * _nrm(_thump(r, 110, 0.22, 0.02, 0.4, 0.4))
    crumble = _grains(r, m, 600, 300, 3000, 0.001, 0.006) * _dec(m, 0.05)
    return _nrm(_thump(r, r.uniform(85, 105), 0.22, 0.03, 0.4, 0.8)) + 0.3 * _nrm(crumble)


@sound("horse_gallop", "a horse's hooves (gait walk | trot | gallop) on dirt or cobble", True, gait="gallop", dur=3.0,
       surface="dirt")
def horse_gallop(r, gait, dur, surface):
    rate, offs = {"walk": (0.9, (0.0, 0.25, 0.5, 0.75)), "trot": (1.5, (0.0, 0.5)),
                  "gallop": (2.1, (0.0, 0.07, 0.17, 0.25))}[gait]
    out = np.zeros((2, n_of(dur + 0.5)))
    t = 0.0
    while t < dur:
        for j, o in enumerate(offs):
            at = t + o / rate + r.normal(0.0, 0.004)
            pan = (-0.2, 0.2, -0.1, 0.1)[j % 4]
            g = r.uniform(0.7, 1.0) * (1.0 if gait != "gallop" or j != 3 else 1.15)
            _place(out, dsp.pan_mono(_hoof(r, surface), pan), at, g)
            if gait == "trot":
                _place(out, dsp.pan_mono(_hoof(r, surface), -pan), at + r.uniform(0.008, 0.02), 0.7 * g)
        if gait == "gallop":
            k = n_of(0.25)
            puff = dsp.bandpass(r.standard_normal(k), 200, 1800, 2) * np.sin(np.pi * np.linspace(0, 1, k)) ** 2
            _place(out, dsp.pan_mono(0.2 * _nrm(puff), 0.0), t + 0.2 / rate)
        t += 1.0 / rate * r.uniform(0.97, 1.03)
    return _space(out, "field", 0.15)


@sound("sheep_bleat", "a sheep bleating 'baa' with its wavering tremble (size 0.6 lamb .. 1.2 sheep)", True, size=1.0)
def sheep_bleat(r, size):
    d = r.uniform(0.6, 0.9) * size ** 0.3
    n = n_of(d)
    t = t_axis(n)
    u = t / d
    wob = np.sin(TWO_PI * dsp.phase_cycles(r.uniform(6.0, 9.0), n, r.uniform()))
    f = r.uniform(260, 330) / size ** 0.8 * (1.0 + 0.06 * wob) * (1.0 + 0.1 * np.sin(np.pi * u) - 0.08 * u)
    k = 1.25 / size ** 0.4
    env = _env([(0, 0), (0.03, 1.0), (d * 0.75, 0.85), (d, 0.0)], n) * (0.6 + 0.4 * wob)
    y = _call(r, f, d, [(k * 700, 3.0, 1.0), (k * 1500, 4.0, 0.6), (k * 2500, 5.0, 0.25)], env, tilt=2000.0,
              jitter=0.03, shimmer=0.15, breath=0.2, rough=0.3)
    return _space(_stereo(y, r.uniform(-0.2, 0.2)), "field", 0.2)


@sound("duck_quack", "a duck quacking: nasal, buzzy 'quack' calls tumbling down", True, quacks=3)
def duck_quack(r, quacks):
    def quack(rr, k):
        d = rr.uniform(0.13, 0.19)
        n = n_of(d)
        u = t_axis(n) / d
        f = rr.uniform(280, 350) * (1.0 - 0.05 * k) * (1.05 - 0.2 * u)
        o = np.clip(u * 3.0, 0.0, 1.0)
        bands = [(400 + 450 * o, 4.0, 1.0), (1300 + 300 * o, 5.0, 0.7), (1000, 6.0, 0.6), (2600, 6.0, 0.3)]
        env = _env([(0, 0), (0.005, 1.0), (d * 0.6, 0.8), (d, 0.0)], n)
        return _call(rr, f, d, bands, env, tilt=4000.0, jitter=0.02, shimmer=0.1, breath=0.15, rough=0.3)
    y = _calls(r, quacks, quack, lambda rr, k: rr.uniform(0.07, 0.15))
    return _space(_stereo(y, r.uniform(-0.2, 0.2)), "field", 0.15)


@sound("frog_croak", "a frog calling: a pulsed 'rib-bit' (size 0.5 .. 1) or a deep bullfrog (size 2)", True,
       size=1.0, calls=2)
def frog_croak(r, size, calls):
    bull = size >= 1.5

    def croak(rr, k):
        syl = ((rr.uniform(0.45, 0.7), rr.uniform(80, 110), rr.uniform(160, 230), 1.0),) if bull else \
            ((rr.uniform(0.09, 0.13), rr.uniform(70, 100), rr.uniform(1300, 1800) / size, 1.0),
             (rr.uniform(0.08, 0.11), rr.uniform(80, 110), rr.uniform(1600, 2100) / size, 0.85))
        y = np.zeros(n_of(sum(s[0] for s in syl) + 0.15))
        at = 0.0
        for d, pr, fc, g in syl:
            n = n_of(d)
            x = _ticks(rr, pr, n, 0.15) * _env([(0, 0), (d * 0.15, 1.0), (d * 0.7, 0.9), (d, 0.0)], n)
            v = dsp.resonator_bank(x, [fc, fc * 2.02, fc * 3.1], [0.03 if bull else 0.012, 0.01, 0.006],
                                   [1.0, 0.4, 0.15])
            _place(y, g * _nrm(v), at)
            at += d + 0.03
        return y
    y = _calls(r, calls, croak, lambda rr, k: rr.uniform(0.25, 0.6))
    return _space(_stereo(y, r.uniform(-0.3, 0.3)), "field", 0.2)


@sound("insect_buzz", "a flying insect circling close by (kind fly | bee | mosquito): wingbeat drone, swooping", True,
       kind="fly", dur=3.0)
def insect_buzz(r, kind, dur):
    n = n_of(dur)
    fw = {"fly": 190.0, "bee": 230.0, "mosquito": 560.0}.get(kind, 190.0) * r.uniform(0.92, 1.08)
    x = 1.2 * dsp.ctrl_noise(n, r, 0.5)
    yy = 0.8 * dsp.ctrl_noise(n, r, 0.5)
    dist = np.sqrt(x * x + yy * yy + 0.15)
    vr = np.gradient(dist) * SR
    f = fw * (1.0 + 0.03 * dsp.ctrl_noise(n, r, 1.5)) * (1.0 - vr / C_AIR) * (1.0 + 0.01 * np.abs(vr))
    src = dsp.onepole(dsp.osc_saw(f, n, r.uniform()), 1500.0 if kind == "bee" else 3000.0)
    src = src * (1.0 + 0.2 * np.sin(TWO_PI * dsp.phase_cycles(f, n)))
    y = dsp.lp_varying(src, np.clip(2500.0 + 5000.0 / dist, 2500.0, 12000.0), 0.7, spacing=0.5) / dist
    y = dsp.fade(y, 0.3, 0.4)
    return dsp.pan_mono(y, np.clip(x / dist, -1.0, 1.0) * 0.9)


@sound("cicada", "a cicada singing: a shrill pulsing buzz that swells and fades", True, dur=4.0)
def cicada(r, dur):
    n = n_of(dur)
    t = t_axis(n)
    fc = r.uniform(4200, 6200)
    env = _env([(0, 0), (0.6, 1.0), (dur - 0.7, 1.0), (dur, 0.0)], n) * \
        (0.7 + 0.3 * np.sin(TWO_PI * r.uniform(0.5, 2.0) * t + r.uniform(0, 6)))
    x = _ticks(r, r.uniform(140, 260) * (1.0 + 0.02 * dsp.ctrl_noise(n, r, 3.0)), n, 0.2) * env
    y = dsp.resonator_bank(x, [fc, fc * 1.08, fc * 2.0], [0.006, 0.005, 0.003], [1.0, 0.5, 0.15])
    y = _nrm(y) + 0.08 * dsp.bandpass(r.standard_normal(n), 3000, 10000, 2) * env
    return _space(_stereo(y, r.uniform(-0.3, 0.3)), "field", 0.15)


# ================================================================================================ vehicles
def _engine(r, n, f_fire, rough=0.3, pipe=(90.0, 180.0, 420.0)):
    """combustion engine: firing pulses (cycle-to-cycle jitter, cylinder imbalance) through exhaust-pipe resonances"""
    ph = dsp.phase_cycles(f_fire * (1.0 + 0.004 * dsp.ctrl_noise(n, r, 3.0)), n, r.uniform())
    cyc = np.floor(ph).astype(np.int64)
    amp = 1.0 + rough * r.standard_normal(int(cyc[-1]) + 2)
    pulses = (0.5 + 0.5 * np.cos(TWO_PI * ph)) ** 6 * amp[cyc]
    y = _formants(pulses, [(pipe[0], 2.0, 1.0), (pipe[1], 2.5, 0.7), (pipe[2], 3.0, 0.35)]) + 0.3 * pulses
    return dsp.lowpass(y - y.mean(), 1800, 2)


@sound("car_pass", "a car driving past (speed km/h, distance m): engine and tyres, the Doppler drop as it goes by",
       True,
       speed=60.0, distance=5.0, direction=1)
def car_pass(r, speed, distance, direction):
    v = max(float(speed), 5.0) / 3.6
    dur = float(np.clip(90.0 / v, 3.0, 9.0))
    f_fire = r.uniform(70, 110)

    def src(m):
        tyre = dsp.bandpass(dsp.pink(m, r), 250, 3500, 2)
        wind = dsp.bandpass(r.standard_normal(m), 1500, 8000, 2)
        return _nrm(_engine(r, m, f_fire)) + (0.2 + 0.5 * speed / 100.0) * _nrm(tyre) + \
            0.15 * (speed / 100.0) ** 2 * _nrm(wind)
    return _pass_by(src, dur, v, dur / 2, max(float(distance), 1.0), 1.0 if direction >= 0 else -1.0)


@sound("car_horn", "a car horn: the two-tone 'honk' of a pair of electric horns", True, honks=2, length=0.3)
def car_horn(r, honks, length):
    f1 = r.uniform(400, 440)
    n = n_of(length)
    t = t_axis(n)
    y = np.zeros(n_of(honks * (length + 0.12) + 0.3))
    for k in range(int(honks)):
        honk = np.zeros(n)
        for f in (f1, f1 * r.uniform(1.24, 1.27)):
            ff = f * (1.0 + 0.01 * np.exp(-t / 0.02)) * (1.0 + 0.002 * dsp.ctrl_noise(n, r, 20.0))
            src = dsp.osc_square(ff, n, r.uniform(), 0.35) + 0.3 * dsp.osc_saw(ff, n, r.uniform())
            horn = _formants(src, [(1000, 2.0, 1.0), (2200, 3.0, 0.6), (3500, 4.0, 0.3)])
            honk += horn + 0.3 * dsp.lowpass(src, 1500, 2)
        env = _env([(0, 0), (0.012, 1.0), (length - 0.03, 1.0), (length, 0.0)], n)
        _place(y, honk * env, k * (length + 0.12))
    return _space(_stereo(y, 0.0, 0.2, r), "field", 0.2)


@sound("engine_idle", "an engine idling (rpm; size 1 car .. 2 truck): lumpy firing pulses, valve tick, intake hiss",
       True, dur=4.0, rpm=800.0, size=1.0)
def engine_idle(r, dur, rpm, size):
    n = n_of(dur)
    cyl = 4 if size < 1.5 else 6
    f_fire = rpm / 60.0 * cyl / 2.0
    pipe = tuple(p / size ** 0.5 for p in (90.0, 180.0, 420.0))
    y = _nrm(_engine(r, n, f_fire, 0.35, pipe))
    tick = dsp.resonator_bank(_ticks(r, f_fire * 2.0, n, 0.4), [3000, 4500, 6200], [0.008, 0.006, 0.004],
                              [1.0, 0.6, 0.3])
    y = y + 0.06 * _nrm(tick) + 0.04 * _nrm(dsp.bandpass(r.standard_normal(n), 1000, 4000, 2))
    return _stereo(y * _texture_env(n, 0.3), 0.0, 0.3, r)


@sound("bicycle_bell", "a bicycle bell: the 'ring-ring' of a thumb-flicked dome bell", True, rings=2)
def bicycle_bell(r, rings):
    f = r.uniform(1900, 2600)
    n = n_of(rings * 0.32 + 1.6)
    times, amps = [], []
    for k in range(int(rings)):
        for j, (dt, a) in enumerate(((0.0, 1.0), (0.028, 0.6), (0.052, 0.35))):
            times.append(k * 0.32 + dt + r.uniform(0, 0.004))
            amps.append(a * r.uniform(0.85, 1.0))
    y = dsp.resonator_bank(_strikes(n, times, amps), [f * p[0] for p in _BELL], [1.4 * p[2] for p in _BELL],
                           [p[1] for p in _BELL])
    return _space(_stereo(_nrm(y), 0.0, 0.2, r), "field", 0.12)


@sound("train_horn", "a train's air horn: a long chord of chimes (chimes 3 or 5), carrying across the land", True,
       dur=1.5, chimes=5)
def train_horn(r, dur, chimes):
    notes = (311.1, 370.0, 415.3, 493.9, 622.3) if chimes >= 5 else (277.2, 349.2, 415.3)
    n = n_of(dur + 0.3)
    t = t_axis(n)
    y = np.zeros(n)
    for f in notes:
        ff = f * r.uniform(0.995, 1.005) * dsp.cents2ratio(-60.0 * (1.0 - dsp.smoothstep(t / 0.12))
                                                          + 3.0 * dsp.ctrl_noise(n, r, 4.0))
        src = dsp.osc_saw(ff, n, r.uniform())
        y += _formants(src, [(f * 2.0, 3.0, 0.6), (1400, 2.0, 0.5)]) + 0.5 * dsp.lowpass(src, 2500, 2)
    y = y * _env([(0, 0), (0.08, 1.0), (dur, 1.0), (dur + 0.25, 0.0), (dur + 0.3, 0.0)], n)
    return _space(_stereo(dsp.lowpass(y, 6000, 2), 0.0, 0.3, r), "field", 0.5)


@sound("train_clatter", "a train rolling on jointed rails: the 'clickety-clack' of the bogies, rumble and rattle", True,
       dur=5.0, speed=1.0)
def train_clatter(r, dur, speed):
    n = n_of(dur)
    v = 22.0 * max(speed, 0.2)
    clack = np.zeros(n)
    for j in range(int(dur * v / 18.0) + 2):
        t0 = j * 18.0 / v - r.uniform(0.0, 0.3)
        for pos, g in ((0.0, 1.0), (2.5, 0.9), (15.5, 0.4), (18.0, 0.35)):
            modes = [r.uniform(250, 350), r.uniform(750, 900), r.uniform(1500, 1800), r.uniform(2900, 3400)]
            hit = _modal_hit(r, modes, [1.0, 0.7, 0.4, 0.2], [0.08, 0.05, 0.035, 0.02], 0.25,
                             noise=(800, 6000, 0.6, 0.003))
            _place(clack, g * (hit + 0.6 * _nrm(_thump(r, 60, 0.25, 0.04, 0.3, 0.5))), t0 + pos / v)
    rumble = dsp.lowpass(dsp.brown(n, r), 200, 2) * (1.0 + 0.15 * np.sin(TWO_PI * 0.8 * t_axis(n)))
    hiss = dsp.bandpass(dsp.pink(n, r), 800, 4000, 2) * speed
    rattle = _grains(r, n, 30.0, 1500, 6000, 0.001, 0.004)
    y = _nrm(clack) + 0.5 * _nrm(rumble) + 0.15 * _nrm(hiss) + 0.1 * _nrm(rattle)
    return _stereo(y * _texture_env(n, 0.3), 0.0, 0.4, r)


@sound("airplane_flyover",
       "an aircraft flying over (kind jet | prop): approach, roar overhead, the receding rumble and "
       "the phasing of the ground reflection", True, kind="jet", dur=9.0, altitude=150.0)
def airplane_flyover(r, kind, dur, altitude):
    v = 80.0 if kind == "jet" else 55.0
    closest = dur * 0.45
    x = v * (t_axis(n_of(dur)) - closest)
    cos_a = x / np.sqrt(x * x + altitude ** 2)
    if kind == "jet":
        f_b = r.uniform(1800, 2600)

        def whine(m):
            tt = t_axis(m)
            f = f_b * (1.0 + 0.003 * dsp.ctrl_noise(m, r, 2.0))
            tone = np.sin(TWO_PI * dsp.phase_cycles(f, m)) + 0.4 * np.sin(TWO_PI * dsp.phase_cycles(2.0 * f, m))
            hiss = dsp.bandpass(r.standard_normal(m), 1500, 5000, 2)
            return tone * (1.0 + 0.2 * np.sin(TWO_PI * 37.0 * tt)) + 0.3 * hiss

        def roar(m):
            return dsp.lowpass(dsp.pink(m, r), 1200, 2) + 0.4 * dsp.bandpass(dsp.pink(m, r), 1200, 4000, 2)
        fwd = np.clip((1.0 - cos_a) / 2.0, 0.0, 1.0) ** 1.5
        aft = np.clip((1.0 + cos_a) / 2.0, 0.0, 1.0) ** 1.5
        y = 0.35 * _pass_by(whine, dur, v, closest, altitude, ground=0.8, height=1.6) * fwd + \
            _pass_by(roar, dur, v, closest, altitude, ground=0.8, height=1.6) * (0.3 + aft)
    else:
        f_b = r.uniform(85, 110)

        def prop(m):
            ph = dsp.phase_cycles(f_b * (1.0 + 0.004 * dsp.ctrl_noise(m, r, 1.0)), m)
            blade = dsp.lowpass((0.5 + 0.5 * np.cos(TWO_PI * ph)) ** 8, 2500, 2)
            return _nrm(blade - blade.mean()) + 0.5 * _nrm(_engine(r, m, f_b * 0.75)) + \
                0.3 * _nrm(dsp.lowpass(dsp.pink(m, r), 2000, 2))
        y = _pass_by(prop, dur, v, closest, altitude, ground=0.8, height=1.6)
    return y * _texture_env(n_of(dur), 0.5)


@sound("ship_horn", "a ship's horn: a deep, long blast echoing across the water", True, blasts=1, length=2.2)
def ship_horn(r, blasts, length):
    f0 = r.uniform(70, 110)
    n = n_of(length + 0.5)
    t = t_axis(n)
    y = np.zeros(n_of(blasts * (length + 0.7) + 0.5))
    for k in range(int(blasts)):
        f = f0 * dsp.cents2ratio(-100.0 * (1.0 - dsp.smoothstep(t / 0.25)) + 4.0 * dsp.ctrl_noise(n, r, 3.0))
        src = dsp.osc_saw(f, n, r.uniform()) + 0.3 * dsp.osc_square(f, n, r.uniform())
        horn = _formants(src, [(f0 * 3.0, 2.0, 0.8), (450, 2.0, 1.0), (900, 3.0, 0.4)])
        blast = horn + 0.6 * dsp.lowpass(src, 1200, 2)
        _place(y, blast * _env([(0, 0), (0.2, 1.0), (length, 1.0), (length + 0.4, 0.0), (length + 0.5, 0.0)], n),
               k * (length + 0.7))
    return _space(_stereo(dsp.lowpass(y, 3500, 2), 0.0, 0.3, r), "field", 0.6)


@sound("siren", "an emergency siren (kind wail | yelp | two_tone); moving drives it past with the Doppler drop", True,
       kind="wail", dur=5.0, moving=False)
def siren(r, kind, dur, moving):
    period = r.uniform(2.6, 3.4)

    def src(m):
        tt = t_axis(m)
        if kind == "yelp":
            f = 650.0 + 850.0 * (2.0 * np.abs((tt * 3.5) % 1.0 - 0.5))
        elif kind == "two_tone":
            f = dsp.onepole(np.where(np.floor(tt / 0.55) % 2 == 0, 440.0, 587.3), 60.0)
        else:
            f = 650.0 + 850.0 * (0.5 - 0.5 * np.cos(TWO_PI * tt / period))
        tone = 0.5 * dsp.osc_square(f, m, 0.0, 0.5) + 0.3 * dsp.osc_saw(f, m)
        return _formants(tone, [(1500, 1.5, 1.0), (3000, 2.0, 0.4)]) + 0.2 * dsp.bandpass(tone, 400, 4000, 2)
    if moving:
        return _pass_by(src, dur, 18.0, dur * 0.5, 12.0) * _texture_env(n_of(dur), 0.3)
    n = n_of(dur)
    return _space(_stereo(src(n) * _texture_env(n, 0.15), 0.0, 0.2, r), "field", 0.3)


@sound("tire_screech", "tyres screeching under hard braking: a wavering rubber squeal over road noise", True, dur=1.5)
def tire_screech(r, dur):
    n = n_of(dur)
    t = t_axis(n)
    u = t / dur
    f = r.uniform(900, 1400) * (1.0 + 0.06 * dsp.ctrl_noise(n, r, 4.0)) * (1.0 - 0.15 * u)
    wob = 1.0 + 0.35 * np.abs(dsp.ctrl_noise(n, r, 15.0))
    squeal = _formants(dsp.osc_saw(f, n, r.uniform()), [(f.mean(), 3.0, 1.0), (2.0 * f.mean(), 4.0, 0.5),
                                                         (3.0 * f.mean(), 5.0, 0.25)]) * wob
    road = dsp.bandpass(dsp.pink(n, r), 300, 3000, 2) * (1.0 - 0.7 * u)
    env = _env([(0, 0), (0.05, 1.0), (dur * 0.8, 0.9), (dur, 0.0)], n)
    return _stereo((_nrm(squeal) + 0.35 * _nrm(road)) * env, 0.0, 0.4, r)


# ================================================================================================ action
def _smack(r, weight=1.0):
    """an impact on a body: the slap of skin and cloth, a meaty low thud, a little crunch"""
    n = n_of(0.35)
    t = t_axis(n)
    slap = dsp.bandpass(r.standard_normal(n), 900, 6000, 2) * np.exp(-t / 0.006) * np.clip(t / 0.0004, 0, 1)
    thud = _thump(r, 75 / weight ** 0.3, 0.35, 0.05 + 0.03 * weight, 0.7, 0.4)
    crunch = _grains(r, n, 900, 600, 4000, 0.0005, 0.003) * np.exp(-t / 0.02)
    return 0.8 * _nrm(slap) + _nrm(thud) + 0.25 * _nrm(crunch)


@sound("punch", "a movie punch: the swish of the fist, then a meaty smack (weight 0.5 .. 1.5)", True, weight=1.0,
       swish=True)
def punch(r, weight, swish):
    out = np.zeros((2, n_of(0.55)))
    at = 0.12 if swish else 0.0
    if swish:
        _place(out, _whoosh_core(r, 0.16, 0.13, 600, 3500, q=1.5, whistle=0.05, rise=2.5, stereo_move=0.5), 0.0, 0.35)
    _place(out, dsp.pan_mono(_smack(r, weight), r.uniform(-0.1, 0.1)), at)
    _place(out, dsp.pan_mono(0.2 * _nrm(_burst(r, n_of(0.08), 400, 4000, 0.015)), 0.0), at)
    return _space(out, "room", 0.1)


@sound("kick", "a kick landing on a body: a heavy swish and a deep thud", True, weight=1.0)
def kick(r, weight):
    out = np.zeros((2, n_of(0.7)))
    _place(out, _whoosh_core(r, 0.24, 0.2, 350, 2500, q=1.2, whistle=0.03, rise=2.2, stereo_move=0.5), 0.0, 0.45)
    hit = _smack(r, weight * 1.4)
    hit += 0.6 * _nrm(_thump(r, 58 / weight ** 0.3, 0.35, 0.09, 0.6, 0.3))
    _place(out, dsp.pan_mono(hit, r.uniform(-0.1, 0.1)), 0.2)
    return _space(out, "room", 0.1)


@sound("sword_swing", "a sword cutting the air: a thin whistling swish (weight 0.5 rapier .. 1.5 broadsword)", True,
       weight=1.0)
def sword_swing(r, weight):
    dur = 0.3 + 0.12 * weight
    y = _whoosh_core(r, dur, dur * 0.5, 900 / weight ** 0.4, 5000 / weight ** 0.3, q=3.5, whistle=0.45, rise=2.5,
                     stereo_move=0.7)
    m = n_of(0.5)
    f = r.uniform(2500, 3500) / weight ** 0.3
    ring = dsp.modal([f, f * 2.756], [1.0, 0.4], [0.4, 0.2], m, r=r) * np.clip(t_axis(m) / 0.05, 0, 1)
    _place(y, dsp.pan_mono(0.05 * _nrm(ring), 0.0), dur * 0.4)
    return y


def _blade(r, f1, t60=1.2):
    """a steel blade ringing: free-free bar modes (1 : 2.76 : 5.40 : 8.93 : 13.3), each a slightly split doublet"""
    ratios = np.array([1.0, 2.756, 5.404, 8.933, 13.34])
    fr = np.concatenate([f1 * ratios, f1 * ratios * 1.0015])
    amps = np.tile([0.5, 1.0, 0.8, 0.5, 0.3], 2) * np.repeat([1.0, 0.6], 5)
    return dsp.modal(fr, amps, np.tile(t60 / ratios ** 0.35, 2), n_of(t60 * 1.2 + 0.1), r=r, attack=0.0002)


@sound("sword_clash", "two swords clashing: a bright metallic 'shing', a scrape and a long ring", True, ring=1.0)
def sword_clash(r, ring):
    out = np.zeros((2, n_of(2.6 + ring)))
    for pan in (-0.25, 0.25):
        _place(out, dsp.pan_mono(_nrm(_blade(r, r.uniform(380, 650), 1.0 + 0.6 * ring)), pan), 0.0, r.uniform(0.7, 1.0))
    k = n_of(0.15)
    impact = dsp.bandpass(r.standard_normal(k), 2000, 10000, 2) * np.exp(-t_axis(k) / 0.003)
    _place(out, dsp.pan_mono(0.8 * _nrm(impact), 0.0), 0.0)
    scrape = (dsp.bandpass(r.standard_normal(k), 3000, 9000, 2) + _grains(r, k, 2000, 3000, 9000)) * \
        _env([(0, 0), (0.02, 1.0), (0.15, 0.0)], k)
    _place(out, dsp.pan_mono(0.35 * _nrm(scrape), 0.1), 0.01)
    return _space(out, "field", 0.2)


@sound("sword_unsheathe", "a sword drawn from its scabbard: a rising metallic scrape, then the blade rings free", True,
       dur=0.8)
def sword_unsheathe(r, dur):
    n = n_of(dur + 1.6)
    t = t_axis(n)
    u = t / dur
    speed = dsp.smoothstep(u / 0.85) * (u < 1.0)
    noise = r.standard_normal(n)
    scrape = dsp.bandpass(noise, 2000, 9000, 2) * speed + 0.5 * _grains(r, n, 1500.0 * speed, 2500, 9000)
    sing = dsp.tv_biquad(noise, "bp", 2500 + 3000 * np.clip(u, 0, 1), 8.0, block=64) * speed
    y = 0.6 * _nrm(dsp.onepole(scrape, 12000)) + 0.5 * _nrm(sing)
    _place(y, 0.45 * _nrm(_blade(r, r.uniform(450, 600), 1.4)), dur)
    return _space(_stereo(y, 0.0, 0.3, r), "field", 0.15)


@sound("arrow_whoosh", "an arrow flying past: a thin fluttering whoosh with a Doppler drop", True, distance=1.5)
def arrow_whoosh(r, distance):
    rate = r.uniform(60, 90)
    f_w = r.uniform(3500, 4500)

    def src(m):
        tt = t_axis(m)
        air = dsp.bandpass(r.standard_normal(m), 1500, 7000, 2) * (1.0 + 0.5 * np.sin(TWO_PI * rate * tt))
        return air + 0.6 * dsp.biquad(r.standard_normal(m), "bp", f_w, 12.0)
    return _pass_by(src, 0.9, 55.0, 0.45, max(float(distance), 0.5), r.choice([-1.0, 1.0]))


@sound("arrow_hit", "an arrow striking a target (target wood | straw): a sharp thunk and the shaft quivering", True,
       target="wood")
def arrow_hit(r, target):
    n = n_of(0.8)
    t = t_axis(n)
    if target == "straw":
        hit = _nrm(_thump(r, 120, 0.8, 0.03, 0.4, 0.8)) + 0.5 * _nrm(_grains(r, n, 1500, 1500,
                                                                             7000) * np.exp(-t / 0.05))
    else:
        hit = _modal_hit(r, [r.uniform(400, 600), r.uniform(1100, 1500), r.uniform(2300, 2900)], [1.0, 0.7, 0.4],
                         [0.07, 0.05, 0.03], 0.8, noise=(1500, 8000, 0.8, 0.002))
    f_q = r.uniform(25, 40)
    quiver = np.sin(TWO_PI * r.uniform(110, 160) * t) * (0.5 + 0.5 * np.sin(TWO_PI * f_q * t)) * \
        np.exp(-t / 0.18) * np.clip(t / 0.01, 0, 1)
    rattle = dsp.bandpass(r.standard_normal(n), 1500, 5000, 2) * np.abs(np.sin(TWO_PI * f_q * t)) * np.exp(-t / 0.1)
    return _stereo(_nrm(hit) + 0.4 * _nrm(quiver) + 0.08 * _nrm(rattle), 0.0, 0.2, r)


@sound("explosion", "an explosion: blast crack, deep boom, fireball roar and falling debris (size; distance in m)",
       True, size=1.0, distance=30.0)
def explosion(r, size, distance):
    n = n_of(5.0 + size)
    t = t_axis(n)
    out = np.zeros((2, n))
    for ch in range(2):
        blast = dsp.highpass(r.standard_normal(n), 150, 2) * np.exp(-t / (0.012 * size)) * np.clip(t / 0.0005, 0, 1)
        boom = np.sin(TWO_PI * dsp.phase_cycles(28.0 + 42.0 * np.exp(-t / 0.15), n)) * np.exp(-t / (0.6 * size))
        boom += 0.8 * dsp.lowpass(dsp.brown(n, r), 150, 2) * np.clip(t / 0.005, 0, 1) * np.exp(-t / (1.2 * size))
        roar = dsp.lp_varying(dsp.pink(n, r), 300 + 1500 * np.exp(-t / 0.6), 0.7, spacing=0.5) * \
            np.clip(t / 0.05, 0, 1) * np.exp(-t / (1.5 * size))
        debris = _grains(r, n, 400.0 * np.exp(-t / 0.8) * (t > 0.2), 1000, 6000, 0.001, 0.005)
        out[ch] = 0.8 * _nrm(blast) + _nrm(boom) + 0.6 * _nrm(roar) + 0.15 * _nrm(debris)
    out = dsp.lowpass(out, 18000.0 / (1.0 + max(distance, 1.0) / 60.0), 2)
    return _space(out, "field", 0.4)


@sound("glass_break", "glass shattering: the crack, a burst of shards and the tinkle of falling pieces", True, size=1.0)
def glass_break(r, size):
    out = np.zeros((2, n_of(2.0 + 0.5 * size)))
    k = n_of(0.05)
    crack = dsp.bandpass(r.standard_normal(k), 2000, 14000, 2) * np.exp(-t_axis(k) / 0.004)
    _place(out, dsp.pan_mono(_nrm(crack), 0.0), 0.0)
    _place(out, dsp.pan_mono(0.4 * _nrm(_thump(r, 180, 0.2, 0.02, 0.3, 0.4)), 0.0), 0.0)
    for count, t0, spread, g, (lo, hi), life in ((int(60 * size), 0.0, 0.06, 1.0, (2500, 11000), (0.05, 0.4)),
                                                 (int(30 * size), 0.2, 0.35, 0.4, (3000, 9000), (0.05, 0.2))):
        for _ in range(count):
            f = np.exp(r.uniform(np.log(lo), np.log(hi)))
            m = n_of(life[1] * 1.3)
            ping = dsp.modal([f, f * r.uniform(2.2, 2.8)], [1.0, 0.4], [r.uniform(*life), 0.05], m, r=r, attack=0.0002)
            _place(out, dsp.pan_mono(ping, r.uniform(-0.7, 0.7)), t0 + r.exponential(spread), g * r.uniform(0.2, 1.0))
    m = n_of(0.6)
    slide = _grains(r, m, 600, 2000, 8000, 0.0005, 0.003) * _env([(0, 0), (0.1, 1.0), (0.6, 0.0)], m)
    _place(out, _stereo(0.3 * _nrm(slide), 0.0, 0.5, r), 0.1)
    return out


@sound("metal_clang", "a heavy metal object struck (size 0.5 pipe .. 2 drum): inharmonic modes ringing and beating",
       True, size=1.0)
def metal_clang(r, size):
    f1 = 300.0 / size ** 0.7 * r.uniform(0.9, 1.1)
    ratios = np.array([1.0, 1.47, 2.09, 2.56, 2.92, 3.71, 4.42, 5.28, 6.6]) * r.uniform(0.97, 1.03, 9)
    fr = np.concatenate([f1 * ratios, f1 * ratios + r.uniform(0.5, 3.0, 9)])
    t60 = np.tile(2.5 * size ** 0.3 / ratios ** 0.5, 2)
    amps = np.tile(r.uniform(0.4, 1.0, 9) / ratios ** 0.3, 2) * np.repeat([1.0, 0.7], 9)
    y = _nrm(dsp.modal(fr, amps, t60, n_of(float(t60.max()) * 1.1), r=r, attack=0.0003))
    k = n_of(0.03)
    y[:k] += 0.5 * _nrm(dsp.bandpass(r.standard_normal(k), 1000, 8000, 2) * np.exp(-t_axis(k) / 0.004))
    y[:n_of(0.2)] += 0.3 * _nrm(_thump(r, f1 * 0.5, 0.2, 0.03, 0.3, 0.3))
    return _stereo(y, 0.0, 0.5, r)


@sound("wood_crack", "wood cracking and snapping (size 0.5 twig .. 2 tree): fibres giving way, then the snap", True,
       size=1.0)
def wood_crack(r, size):
    pre = 0.05 if size < 0.8 else 0.25 + 0.3 * size
    n = n_of(pre + 1.2)
    f1 = 420.0 / size ** 0.6
    modes = np.array([1.0, 2.3, 3.9, 5.6]) * f1
    t60 = [0.12 * size ** 0.5, 0.08, 0.05, 0.03]
    times = pre * (1.0 - np.sort(r.uniform(0.0, 1.0, int(8 + 20 * size))) ** 2.5)
    x = _strikes(n, times, r.uniform(0.1, 0.5, len(times)) * (1.0 - times / (pre + 1e-9)) ** 0.5 + 0.05)
    x[n_of(pre)] += 3.0
    y = dsp.resonator_bank(x, modes, t60, [1.0, 0.6, 0.35, 0.2])
    k = n_of(0.04)
    _place(y, 1.5 * dsp.peak(y) * _nrm(dsp.bandpass(r.standard_normal(k), 800, 11000, 2) * np.exp(-t_axis(k) / 0.004)),
           pre)
    _place(y, dsp.peak(y) * _nrm(_thump(r, 80 / size ** 0.3, 0.4, 0.05, 0.4, 0.5)) * min(1.0, size), pre)
    return _space(_stereo(y, 0.0, 0.3, r), "field", 0.15)


@sound("body_fall", "a body falling to the ground (surface ground | wood): clothing, a heavy thud, limbs settling",
       True,
       weight=1.0, surface="ground")
def body_fall(r, weight, surface):
    out = np.zeros((2, n_of(1.2)))
    k = n_of(0.18)
    cloth = dsp.bandpass(r.standard_normal(k), 400, 3500, 2) * np.sin(np.pi * np.linspace(0, 1, k)) ** 2
    _place(out, _stereo(0.3 * _nrm(cloth), 0.0, 0.4, r), 0.0)
    at = 0.15
    main = _nrm(_thump(r, 70 / weight ** 0.3, 0.6, 0.08, 0.5, 0.6))
    main[:n_of(0.35)] += 0.4 * _nrm(_smack(r, weight))
    if surface == "wood":
        main += 0.5 * _modal_hit(r, [95, 210, 380, 640], [1.0, 0.6, 0.35, 0.2], [0.18, 0.12, 0.09, 0.06], 0.6)
    _place(out, dsp.pan_mono(main, 0.0), at)
    for j in range(int(r.integers(2, 4))):
        _place(out, dsp.pan_mono(_nrm(_thump(r, r.uniform(90, 140), 0.25, 0.03, 0.4, 0.6)), r.uniform(-0.3, 0.3)),
               at + r.uniform(0.06, 0.25), r.uniform(0.25, 0.5))
    m = n_of(0.4)
    settle = dsp.bandpass(r.standard_normal(m), 500, 3000, 2) * _env([(0, 0), (0.05, 1.0), (0.4, 0.0)], m)
    _place(out, _stereo(0.15 * _nrm(settle), 0.0, 0.4, r), at + 0.3)
    return _space(out, "field", 0.1)


# ================================================================================================ crowds
_VOWEL = {"a": (730, 1090, 2440), "e": (530, 1840, 2480), "i": (300, 2250, 3000), "o": (500, 850, 2400),
          "u": (320, 800, 2240)}


def _vowels(src, v1, v2=None, morph=0.0, tract=1.0):
    """a voice through static vowel formant banks, cross-faded from v1 to v2 by morph (0..1, scalar or array)"""
    def bank(v):
        return _formants(src, [(f * tract, q, g) for f, q, g in zip(_VOWEL[v], (5.0, 7.0, 9.0), (1.0, 0.5, 0.25))])
    y = bank(v1)
    return y if v2 is None else y * (1.0 - morph) + bank(v2) * morph


def _person(r):
    """f0 and vocal-tract scale of a random adult"""
    return (r.uniform(105, 165), r.uniform(0.95, 1.05)) if r.uniform() < 0.5 else (r.uniform(190, 310),
                                                                                    r.uniform(1.1, 1.2))


@sound("applause", "applause: a crowd clapping, swelling in and thinning out", True, dur=4.0, people=30)
def applause(r, dur, people):
    n = n_of(dur + 0.6)
    out = np.zeros((2, n))
    k = n_of(0.012)
    for _ in range(int(people)):
        start = r.exponential(0.15)
        stop = max(start + 0.3, dur - r.exponential(0.5))
        rate = r.uniform(3.5, 6.0)
        times = np.arange(start, stop, 1.0 / rate)
        times = times + r.normal(0.0, 0.04 / rate, len(times))
        x = _strikes(n, times, r.uniform(0.6, 1.0, len(times)))
        y = signal.oaconvolve(x, r.standard_normal(k) * np.exp(-t_axis(k) / 0.003))[:n]
        y = dsp.biquad(y, "bp", r.uniform(900, 2500), r.uniform(1.2, 2.5)) + 0.3 * dsp.bandpass(y, 2000, 9000, 2)
        out += dsp.pan_mono(y * r.uniform(0.4, 1.0), r.uniform(-0.9, 0.9))
    return _space(dsp.lowpass(out, 12000, 2), "hall", 0.25)


@sound("cheer", "a crowd cheering: whoops and 'yeah!'s over clapping, a whistle or two", True, dur=3.0, people=25)
def cheer(r, dur, people):
    n = n_of(dur + 0.6)
    out = np.zeros((2, n))
    for _ in range(int(people)):
        f0, tract = _person(r)
        for _ in range(int(r.integers(1, 3))):
            d = r.uniform(0.4, min(1.4, dur))
            m = n_of(d)
            u = t_axis(m) / d
            f = f0 * 2.0 ** ((r.uniform(4, 9) * np.sin(np.pi * np.clip(u * 1.3, 0, 1)) ** 0.7 - 2.0 * u) / 12.0)
            v1, v2 = ("e", "a") if r.uniform() < 0.6 else ("u", "o")
            y = _vowels(_voiced(r, f, m, tilt=2200.0, jitter=0.02, shimmer=0.1, breath=0.25, rough=0.15), v1, v2,
                        dsp.smoothstep(u / 0.4), tract)
            y *= _env([(0, 0), (0.04, 1.0), (d * 0.6, 0.8), (d, 0.0)], m)
            _place(out, dsp.pan_mono(_nrm(y) * r.uniform(0.3, 1.0), r.uniform(-0.9, 0.9)), r.uniform(0.0, dur - d))
    for _ in range(int(r.integers(1, 4))):
        d = r.uniform(0.5, 0.9)
        m = n_of(d)
        u = t_axis(m) / d
        f = r.uniform(2000, 2600) * (1.0 + 0.25 * np.sin(np.pi * u))
        w = (np.sin(TWO_PI * dsp.phase_cycles(f, m)) + 0.05 * dsp.bandpass(r.standard_normal(m), 1500, 6000, 2))
        _place(out, dsp.pan_mono(0.35 * w * np.sin(np.pi * u) ** 0.5, r.uniform(-0.8, 0.8)), r.uniform(0.1, dur - d))
    out = _nrm(out) + 0.45 * _nrm(applause(r, dur, max(6, int(people * 0.6)))[:, :n])
    return _space(out, "hall", 0.25)


@sound("crowd_gasp", "a crowd gasping in surprise: a sharp collective intake of breath", True, people=25)
def crowd_gasp(r, people):
    n = n_of(1.2)
    out = np.zeros((2, n))
    for _ in range(int(people)):
        f0, tract = _person(r)
        d = r.uniform(0.25, 0.45)
        m = n_of(d)
        env = _env([(0, 0), (0.04, 1.0), (d * 0.5, 0.7), (d, 0.0)], m)
        y = _vowels(r.standard_normal(m), "a" if r.uniform() < 0.5 else "o", tract=tract) * env
        if r.uniform() < 0.3:
            u = t_axis(m) / d
            y += 0.4 * _nrm(_vowels(_voiced(r, f0 * (1.3 + 0.3 * u), m, breath=0.3), "o",
                                    tract=tract)) * env * dsp.peak(y)
        _place(out, dsp.pan_mono(_nrm(y) * r.uniform(0.3, 1.0), r.uniform(-0.9, 0.9)), abs(r.normal(0.0, 0.05)))
    return _space(out, "hall", 0.25)


@sound("crowd_laugh", "a crowd laughing together: many 'ha-ha's at their own pace, swelling and dying away", True,
       dur=3.0, people=20)
def crowd_laugh(r, dur, people):
    n = n_of(dur + 0.6)
    t = t_axis(n)
    out = np.zeros((2, n))
    for _ in range(int(people)):
        f0, tract = _person(r)
        start = r.exponential(0.2)
        length = r.uniform(1.0, max(1.1, min(dur - start, 2.8)))
        tt = t - start
        on = (tt >= 0) & (tt <= length)
        gate = np.where(on, (0.5 - 0.5 * np.cos(TWO_PI * r.uniform(4.0, 6.5) * np.maximum(tt, 0))) ** 1.5, 0.0)
        env = np.where(on, np.exp(-np.maximum(tt, 0) / length) * np.clip(tt / 0.05, 0, 1) *
                       np.clip((length - tt) / 0.1, 0, 1), 0.0)
        f = f0 * (1.0 + 0.15 * gate) * (1.0 + 0.12 * np.exp(-np.maximum(tt, 0) / 0.5))
        y = _vowels(_voiced(r, f, n, tilt=2000.0, jitter=0.02, shimmer=0.1, breath=0.5, rough=0.2), "a",
                    tract=tract) * gate * env
        out += dsp.pan_mono(_nrm(y) * r.uniform(0.3, 1.0), r.uniform(-0.9, 0.9))
    return _space(out, "hall", 0.25)


# ================================================================================================ magic and sci-fi
def _flange(x, delay):
    """x plus a copy delayed by `delay` seconds (array): a moving comb -- phasers, jet whooshes, teleporters"""
    n = len(x)
    return x + dsp.interp_cubic(x, np.clip(np.arange(n) - np.asarray(delay) * SR, 0.0, n - 1.0))


@sound("teleport", "teleporting away: a rising shimmering sweep that flares and vanishes", True, dur=1.4)
def teleport(r, dur):
    n = n_of(dur + 0.4)
    t = t_axis(n)
    u = np.clip(t / dur, 0.0, 1.0)
    gone = 1.0 - dsp.smoothstep((t - dur) / 0.06)
    trem = 0.6 + 0.4 * np.sin(TWO_PI * dsp.phase_cycles(8.0 + 32.0 * u, n))
    out = np.zeros((2, n))
    for k, det in enumerate((0.99, 1.0, 1.012)):
        f = 220.0 * 2.0 ** (4.0 * u ** 1.5) * det
        ph = dsp.phase_cycles(f, n, r.uniform())
        tone = np.sin(TWO_PI * ph + 0.8 * np.sin(TWO_PI * 2.0 * ph))
        out += dsp.pan_mono(tone * trem, np.sin(TWO_PI * 1.3 * t + k * 2.1) * 0.7)
    shimmer = _flange(dsp.highpass(r.standard_normal(n), 2000, 2), 0.005 * (1.0 - u) + 0.0003)
    out += 0.35 * _stereo(_nrm(dsp.lowpass(shimmer, 12000, 2)) * u, 0.0, 0.6, r)
    out = out * (0.2 + 0.8 * u ** 1.5) * gone
    sp = sparkle(r, 0.4, 1.5)
    _place(out, 0.4 * sp / (dsp.peak(sp) + 1e-9), dur - 0.05)
    return out


@sound("laser", "a sci-fi laser blast 'pew' (shots; pitch)", True, shots=1, pitch=1.0)
def laser(r, shots, pitch):
    out = np.zeros((2, n_of(0.25 * shots + 0.4)))
    for k in range(int(shots)):
        d = r.uniform(0.16, 0.24)
        n = n_of(d + 0.05)
        t = t_axis(n)
        f = (180.0 + 2600.0 * np.exp(-t / (d * 0.25))) * pitch * r.uniform(0.9, 1.1)
        ph = dsp.phase_cycles(f, n)
        y = np.sin(TWO_PI * ph + 1.5 * np.exp(-t / 0.05) * np.sin(TWO_PI * 2.0 * ph)) + 0.3 * np.sin(TWO_PI * 1.5 * ph)
        y *= np.clip(t / 0.002, 0, 1) * np.exp(-t / (d * 0.45))
        y[:n_of(0.004)] += 0.3 * _nrm(dsp.highpass(r.standard_normal(n_of(0.004)), 3000, 2))
        _place(out, dsp.pan_mono(y, r.uniform(-0.3, 0.3)), k * 0.22)
    return _space(out, "room", 0.1)


@sound("power_up", "powering up: a rising whine with a quickening pulse, then a bright chime", True, dur=1.5)
def power_up(r, dur):
    n = n_of(dur + 1.5)
    t = t_axis(n)
    u = np.clip(t / dur, 0.0, 1.0)
    f = 110.0 * 2.0 ** (4.5 * u ** 1.3)
    y = dsp.lp_varying(dsp.osc_saw(f, n, r.uniform()), np.clip(2.5 * f, 300.0, 12000.0), 2.0, spacing=0.5)
    y *= (0.6 + 0.4 * np.sin(TWO_PI * dsp.phase_cycles(5.0 + 25.0 * u, n))) * (0.15 + 0.85 * u) * \
        (1.0 - dsp.smoothstep((t - dur) / 0.03))
    m = n - n_of(dur)
    ding = _bell(r, 1568.0, m, 1.2) + 0.6 * _bell(r, 2349.3, m, 1.0)
    _place(y, 0.6 * _nrm(ding), dur)
    return _space(_stereo(y, 0.0, 0.4, r), "room", 0.12)


@sound("power_down", "powering down: a whine falling and slowing to a stop, then a last relay click", True, dur=1.6)
def power_down(r, dur):
    n = n_of(dur + 0.4)
    t = t_axis(n)
    u = np.clip(t / dur, 0.0, 1.0)
    f = 1800.0 * 2.0 ** (-5.0 * u ** 0.8)
    y = dsp.lp_varying(dsp.osc_saw(f, n, r.uniform()), np.clip(3.0 * f, 200.0, 12000.0), 1.5, spacing=0.5)
    y *= (0.6 + 0.4 * np.sin(TWO_PI * dsp.phase_cycles(25.0 - 23.0 * u, n))) * (1.0 - u) ** 0.7
    _place(y, 0.5 * _latch(r, 1.0, 1.2), dur + 0.05)
    return _space(_stereo(y, 0.0, 0.3, r), "room", 0.12)


@sound("force_field", "a force field humming: a deep electric drone, a shimmering halo and crackling sparks", True,
       dur=3.0)
def force_field(r, dur):
    n = n_of(dur)
    t = t_axis(n)
    rise = 0.7 + 0.3 * dsp.smoothstep(t / 0.35)
    hum = dsp.osc_saw(55.0 * rise, n, r.uniform()) + 0.7 * dsp.osc_saw(110.4 * rise, n, r.uniform())
    hum = dsp.lowpass(hum, 900, 2) * (0.85 + 0.15 * np.sin(TWO_PI * 3.0 * t))
    halo = sum(np.sin(TWO_PI * f * t + r.uniform(0, 6)) * (0.6 + 0.4 * dsp.ctrl_noise(n, r, 0.8))
               for f in r.uniform(1200, 4000, 5))
    halo = dsp.comb_ff(halo, 0.0017, 0.6)
    sparks = dsp.crackle(n, r, 6.0 * np.clip(dsp.ctrl_noise(n, r, 1.0), 0, None), 0.8, (0.0005, 0.003), hp=2000)
    y = _nrm(hum) + 0.25 * _nrm(halo) + 0.3 * _nrm(sparks)
    return _stereo(y * _texture_env(n, 0.3), 0.0, 0.5, r)


@sound("portal", "a magic portal swirling open: a rotating vortex of rumble, wind and shimmer", True, dur=3.0)
def portal(r, dur):
    n = n_of(dur)
    t = t_axis(n)
    u = t / dur
    opening = dsp.smoothstep(u / 0.3)
    rumble = dsp.lowpass(dsp.brown(n, r), 120, 2) + 0.5 * np.sin(TWO_PI * dsp.phase_cycles(40.0 + 15.0 * u, n))
    fc = (400.0 + 1600.0 * (0.5 + 0.5 * np.sin(TWO_PI * 0.7 * t))) * (1.0 + u)
    swirl = dsp.tv_biquad(dsp.pink(n, r), "bp", fc, 4.0, block=128)
    shimmer = sum(np.sin(TWO_PI * dsp.phase_cycles(f * (1.0 + 0.3 * u), n, r.uniform()))
                  for f in (1760.0, 2217.5, 2637.0))
    out = dsp.pan_mono(_nrm(swirl), 0.8 * np.sin(TWO_PI * 0.5 * t)) + _stereo(0.7 * _nrm(rumble) * opening, 0.0)
    out += dsp.pan_mono(0.15 * _nrm(shimmer) * opening, -0.6 * np.sin(TWO_PI * 0.5 * t))
    whoomph = dsp.lowpass(dsp.pink(n, r), 500, 2) * _env([(0, 0), (0.25, 1.0), (0.6, 0.0), (dur, 0.0)], n)
    out += _stereo(0.6 * _nrm(whoomph), 0.0)
    return out * _texture_env(n, 0.5)


@sound("spaceship_pass", "a spaceship roaring past: a harmonic engine drone and rushing air with a steep Doppler sweep",
       True, distance=8.0)
def spaceship_pass(r, distance):
    f0 = r.uniform(70, 110)

    def src(m):
        tt = t_axis(m)
        f = f0 * (1.0 + 0.01 * np.sin(TWO_PI * 6.0 * tt))
        drone = dsp.lowpass(dsp.osc_saw(f, m, r.uniform()) + 0.6 * dsp.osc_saw(f * 1.5, m, r.uniform()), 2500, 2)
        rush = dsp.bandpass(dsp.pink(m, r), 200, 5000, 2)
        return _nrm(drone) * (1.0 + 0.3 * np.sin(TWO_PI * 31.0 * tt)) + 0.8 * _nrm(rush)
    return _pass_by(src, 2.5, 120.0, 1.25, max(float(distance), 1.0), r.choice([-1.0, 1.0]), ground=0.7, height=1.6) * \
        _texture_env(n_of(2.5), 0.3)


@sound("helicopter", "a helicopter passing low: the thudding main rotor, the buzzing tail rotor, the turbine whine",
       True, dur=6.0, distance=40.0)
def helicopter(r, dur, distance):
    f_main, f_tail, f_turb = r.uniform(16, 22), r.uniform(90, 110), r.uniform(4500, 6000)

    def src(m):
        ph = dsp.phase_cycles(f_main * (1.0 + 0.005 * dsp.ctrl_noise(m, r, 0.5)), m, r.uniform())
        slap = (0.5 + 0.5 * np.cos(TWO_PI * ph)) ** 24
        slap = slap - slap.mean()
        whop = dsp.lowpass(slap * (0.3 + r.standard_normal(m)), 1200, 2) + 0.8 * dsp.lowpass(slap, 150, 2)
        tail = dsp.bandpass((0.5 + 0.5 * np.cos(TWO_PI * dsp.phase_cycles(f_tail, m))) ** 6, 300, 2000, 2)
        whine = np.sin(TWO_PI * dsp.phase_cycles(f_turb, m)) * 0.3 + dsp.bandpass(r.standard_normal(m), 3000, 7000, 2)
        return _nrm(whop) + 0.35 * _nrm(tail) + 0.06 * _nrm(whine)
    return _pass_by(src, dur, 25.0, dur * 0.5, max(float(distance), 5.0), ground=0.6,
                    height=1.6) * _texture_env(n_of(dur))


# ================================================================================================ cartoon
@sound("rubber_squeak", "a squeezed rubber toy: a reedy 'squee-eek' (squeaks 2 = squeeze and release)", True, squeaks=2,
       pitch=1.0)
def rubber_squeak(r, squeaks, pitch):
    y = np.zeros(n_of(0.3 * squeaks + 0.3))
    for k in range(int(squeaks)):
        release = k % 2 == 1
        d = r.uniform(0.12, 0.2) if release else r.uniform(0.18, 0.3)
        n = n_of(d)
        t = t_axis(n)
        u = t / d
        f0 = r.uniform(1300, 1900) * pitch * (0.85 if release else 1.0)
        f = f0 * (1.05 - 0.2 * u) if release else f0 * (0.8 + 0.25 * dsp.smoothstep(u / 0.3)) * \
            (1.0 + 0.02 * np.sin(TWO_PI * 25.0 * t))
        src = dsp.osc_square(f, n, r.uniform(), 0.2) + 0.3 * dsp.osc_saw(f, n, r.uniform())
        tone = _formants(src, [(2400, 3.0, 1.0), (4000, 4.0, 0.4)]) + 0.2 * dsp.lowpass(src, 3000, 2)
        env = _env([(0, 0), (0.01, 1.0), (d * 0.7, 0.8), (d, 0.0)], n)
        squish = dsp.bandpass(r.standard_normal(n), 150, 700, 2)
        _place(y, (_nrm(tone) + 0.15 * _nrm(squish) + 0.04 * dsp.bandpass(r.standard_normal(n), 2000, 8000, 2)) * env,
               0.3 * k)
    return _stereo(y, 0.0, 0.2, r)


@sound("run_away_zip", "a cartoon zip-off: a quick rising whistle and a whoosh vanishing into the distance", True,
       direction=1)
def run_away_zip(r, direction):
    n = n_of(0.9)
    t = t_axis(n)
    side = 1.0 if direction >= 0 else -1.0
    f = 500.0 * (2600.0 / 500.0) ** dsp.smoothstep(t / 0.25) * (1.0 - 0.08 * dsp.smoothstep((t - 0.3) / 0.5))
    whistle = np.sin(TWO_PI * dsp.phase_cycles(f, n)) * _env([(0, 0), (0.02, 1.0), (0.3, 0.8), (0.75, 0.0), (0.9, 0)],
                                                             n)
    away = np.exp(-np.maximum(t - 0.15, 0.0) / 0.25)
    y = dsp.pan_mono(0.5 * whistle * (0.4 + 0.6 * away), side * dsp.smoothstep(t / 0.5))
    w = _whoosh_core(r, 0.6, 0.12, 400, 5000, q=1.5, whistle=0.1, rise=1.5, stereo_move=0.9 * side)
    _place(y, w, 0.0)
    k = n_of(0.3)
    puff = dsp.lowpass(r.standard_normal(k), 900, 2) * _env([(0, 0), (0.01, 1.0), (0.3, 0.0)], k)
    _place(y, dsp.pan_mono(0.4 * _nrm(puff), -0.3 * side), 0.0)
    return dsp.lp_varying(y, np.clip(12000.0 * away + 1500.0, 1500.0, 14000.0), 0.7, spacing=0.5)


@sound("tiptoe", "cartoon tiptoeing: soft pizzicato plinks sneaking along, step by step", True, steps=6, pitch=1.0)
def tiptoe(r, steps, pitch):
    from codecinema.audio import instruments
    base = 52 + 12 * np.log2(max(pitch, 0.25))
    seq = [0, 3, 0, 3, 2, 5, 2, 5, 0, 3, -2, 0]
    out = np.zeros((2, n_of(0.34 * steps + 1.0)))
    for k in range(int(steps)):
        at = 0.34 * k + (0.03 if k % 2 else 0.0)
        dsp.place(out, instruments.play("pizzicato_strings", base + seq[k % len(seq)], 0.2, 0.5, seed=k), n_of(at))
        _place(out, dsp.pan_mono(0.04 * _nrm(_burst(r, n_of(0.08), 400, 2500, 0.01)), -0.2 if k % 2 else 0.2), at)
    return out


@sound("xylophone_fall", "a xylophone run tumbling down the bars (a fall, a dizzy spell)", True, notes=12, sweep=0.9)
def xylophone_fall(r, notes, sweep):
    from codecinema.audio import instruments
    scale = [96, 93, 91, 89, 88, 86, 84, 81, 79, 77, 76, 74, 72, 69, 67]
    ps = scale[:max(2, min(int(notes), len(scale)))]
    out = np.zeros((2, n_of(sweep + 1.5)))
    for k, p in enumerate(ps):
        u = k / (len(ps) - 1)
        c = instruments.play("xylophone", p, 0.3, 0.85 - 0.3 * u, seed=k)
        dsp.place(out, dsp.pan_stereo(c, 0.4 - 0.8 * u, 1.0), n_of(sweep * u ** 0.85))
    return out


@sound("cartoon_whistle", "a cartoon whistle (kind wolf: 'fweet-fweeoo' | pea: a referee's trilling blast)", True,
       kind="wolf")
def cartoon_whistle(r, kind):
    def blow(f, d):
        n = len(f)
        tone = np.sin(TWO_PI * dsp.phase_cycles(f, n)) + 0.08 * np.sin(TWO_PI * dsp.phase_cycles(2.0 * f, n))
        air = dsp.bandpass(r.standard_normal(n), 2000, 8000, 2)
        return (tone + 0.06 * air) * _env([(0, 0), (0.02, 1.0), (d - 0.05, 0.9), (d, 0.0)], n)
    if kind == "pea":
        d = 0.7
        n = n_of(d)
        t = t_axis(n)
        rate = r.uniform(25, 40)
        f = r.uniform(2700, 3300) * (1.0 + 0.03 * np.sin(TWO_PI * rate * t))
        y = blow(f, d) * (0.65 + 0.35 * np.sin(TWO_PI * rate * t + 1.0))
        return _space(_stereo(y, 0.0), "field", 0.15)
    y = np.zeros(n_of(1.2))
    n1 = n_of(0.22)
    _place(y, blow(900.0 * (2600.0 / 900.0) ** dsp.smoothstep(t_axis(n1) / 0.22), 0.22), 0.0)
    n2 = n_of(0.6)
    u = t_axis(n2) / 0.6
    f2 = np.where(u < 0.25, 1300.0 + 1600.0 * dsp.smoothstep(u / 0.25),
                  2900.0 - 2000.0 * dsp.smoothstep((u - 0.25) / 0.75))
    _place(y, blow(f2, 0.6), 0.3)
    return _space(_stereo(y, 0.0), "field", 0.15)


@sound("bulb_horn", "a clown's bulb horn: a squeezed rubber bulb blowing a brassy 'honk'", True, honks=2)
def bulb_horn(r, honks):
    y = np.zeros(n_of(0.32 * honks + 0.3))
    f0 = r.uniform(330, 400)
    for k in range(int(honks)):
        d = 0.22
        n = n_of(d)
        t = t_axis(n)
        bend = -200.0 * np.exp(-t / 0.015) - 60.0 * dsp.smoothstep((t - 0.15) / 0.07)
        f = f0 * (0.9 if k % 2 else 1.0) * dsp.cents2ratio(bend)
        src = dsp.osc_square(f, n, r.uniform(), 0.3) + 0.5 * dsp.osc_saw(f, n, r.uniform())
        honk = _formants(src, [(900, 3.0, 1.0), (1700, 4.0, 0.6), (2800, 5.0, 0.3)]) + 0.2 * dsp.lowpass(src, 2000, 2)
        _place(y, honk * _env([(0, 0), (0.015, 1.0), (d * 0.7, 0.8), (d, 0.0)], n), 0.32 * k)
    return _space(_stereo(y, 0.0, 0.2, r), "room", 0.12)


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
