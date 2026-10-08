"""
codecinema.audio.dsp -- core DSP toolkit shared by the CodeCinema films.

Conventions
    * sample rate SR = the active film's audio.sample_rate setting (48 kHz by default), float64 numpy arrays
    * mono  = shape (n,)      stereo = shape (2, n)
    * times in seconds unless a name ends in _n (samples)
    * every random process takes a numpy Generator (see rng()) -> fully deterministic renders

Contents
    oscillators (sine, PolyBLEP saw/square, additive triangle, FM), noise (white/pink/brown),
    envelopes, filters (Butterworth, RBJ biquads, block-wise time-varying biquad, SVF, filter-bank sweep),
    one-pole smoothers, resonator/modal synthesis, Karplus-Strong (vectorised per period),
    cubic-interpolated resampling / varispeed / pitch shift, synthetic stereo convolution reverb,
    equal-power pan, compressor, true-peak lookahead limiter, soft clip, Timeline placement helper.
"""
import hashlib

import numpy as np
from scipy import signal

from codecinema.workspace import settings as _settings

SR = int(_settings.get("audio", "sample_rate", 48000))   # the active film's sample rate
NYQ = SR / 2.0
LN1000 = 6.907755278982137          # ln(1000): exp(-LN1000*t/T60) is -60 dB at T60
TWO_PI = 2.0 * np.pi


# =====================================================================================  basics
def n_of(sec):
    """seconds -> samples (non-negative int)"""
    return max(0, int(round(float(sec) * SR)))


def t_axis(n):
    return np.arange(n, dtype=np.float64) / SR


def db2lin(db):
    return 10.0 ** (np.asarray(db, dtype=np.float64) / 20.0)


def lin2db(x, floor=1e-12):
    return 20.0 * np.log10(np.maximum(np.abs(x), floor))


def seed_of(*keys):
    h = hashlib.blake2b(repr(keys).encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(h, "little")


def rng(*keys):
    """Deterministic Generator from arbitrary hashable keys (e.g. rng('clash', 630, 3))."""
    return np.random.default_rng(seed_of(*keys))


def midi2hz(m):
    return 440.0 * 2.0 ** ((np.asarray(m, dtype=np.float64) - 69.0) / 12.0)


def cents2ratio(c):
    return 2.0 ** (np.asarray(c, dtype=np.float64) / 1200.0)


def as_stereo(x):
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 1:
        return np.vstack([x, x])
    return x


def mono(x):
    x = np.asarray(x, dtype=np.float64)
    return x if x.ndim == 1 else x.mean(axis=0)


def pad_to(x, n):
    """zero-pad / truncate the last axis to n samples"""
    m = x.shape[-1]
    if m == n:
        return x
    if m > n:
        return x[..., :n]
    pad = [(0, 0)] * (x.ndim - 1) + [(0, n - m)]
    return np.pad(x, pad)


def peak(x):
    return float(np.max(np.abs(x))) if x.size else 0.0


def rms(x):
    return float(np.sqrt(np.mean(np.square(x)))) if x.size else 0.0


def normalize(x, target_peak=1.0):
    p = peak(x)
    return x * (target_peak / p) if p > 0 else x


# =====================================================================================  pan
def pan_gains(pan):
    """equal-power pan law, pan in [-1, 1] -> (gL, gR); centre = -3 dB each"""
    p = np.clip(pan, -1.0, 1.0)
    th = (p + 1.0) * np.pi / 4.0
    return np.cos(th), np.sin(th)


def pan_mono(x, pan=0.0):
    """mono -> stereo with (optionally time-varying) equal-power pan"""
    gl, gr = pan_gains(pan)
    return np.vstack([x * gl, x * gr])


def pan_stereo(x, pan=0.0, width=1.0):
    """re-position a stereo clip: M/S width then equal-power balance (centre keeps unity)"""
    x = as_stereo(x)
    m = 0.5 * (x[0] + x[1])
    s = 0.5 * (x[0] - x[1]) * width
    l, r = m + s, m - s
    gl, gr = pan_gains(pan)
    k = np.sqrt(2.0)
    return np.vstack([l * gl * k, r * gr * k])


def spread_voices(voices, pans):
    """list of mono voices + pans -> stereo sum"""
    n = max(len(v) for v in voices)
    out = np.zeros((2, n))
    for v, p in zip(voices, pans):
        gl, gr = pan_gains(p)
        out[0, :len(v)] += v * gl
        out[1, :len(v)] += v * gr
    return out


# =====================================================================================  oscillators
def phase_cycles(freq, n, phase0=0.0):
    """instantaneous phase in cycles; phase[0] == phase0; freq scalar or array(n)"""
    f = np.broadcast_to(np.asarray(freq, dtype=np.float64), (n,))
    ph = np.cumsum(f) / SR
    ph -= f / SR
    ph += phase0
    return ph


def osc_sine(freq, n, phase0=0.0):
    return np.sin(TWO_PI * phase_cycles(freq, n, phase0))


def _polyblep(t, dt):
    out = np.zeros_like(t)
    m = t < dt
    if np.any(m):
        x = t[m] / dt[m]
        out[m] = x + x - x * x - 1.0
    m = t > 1.0 - dt
    if np.any(m):
        x = (t[m] - 1.0) / dt[m]
        out[m] = x * x + x + x + 1.0
    return out


def osc_saw(freq, n, phase0=0.0):
    """band-limited (PolyBLEP) sawtooth, rising ramp in [-1, 1]"""
    f = np.broadcast_to(np.asarray(freq, dtype=np.float64), (n,))
    dt = np.clip(f / SR, 1e-9, 0.5)
    t = phase_cycles(f, n, phase0) % 1.0
    return 2.0 * t - 1.0 - _polyblep(t, dt)


def osc_square(freq, n, phase0=0.0, pw=0.5):
    """band-limited (PolyBLEP) pulse wave with pulse width pw (scalar or array)"""
    f = np.broadcast_to(np.asarray(freq, dtype=np.float64), (n,))
    dt = np.clip(f / SR, 1e-9, 0.5)
    t = phase_cycles(f, n, phase0) % 1.0
    pw = np.broadcast_to(np.asarray(pw, dtype=np.float64), (n,))
    y = np.where(t < pw, 1.0, -1.0)
    y = y + _polyblep(t, dt)
    y = y - _polyblep((t - pw) % 1.0, dt)
    return y


def osc_tri(freq, n, phase0=0.0, max_harm=40):
    """additive band-limited triangle (odd harmonics 1/k^2), harmonics faded near Nyquist"""
    f = np.broadcast_to(np.asarray(freq, dtype=np.float64), (n,))
    ph = TWO_PI * phase_cycles(f, n, phase0)
    y = np.zeros(n)
    sgn = 1.0
    for k in range(1, 2 * max_harm, 2):
        fk = f * k
        if np.min(fk) > NYQ * 0.9:
            break
        w = np.clip((NYQ * 0.9 - fk) / (NYQ * 0.1), 0.0, 1.0)
        y += sgn * w * np.sin(k * ph) / (k * k)
        sgn = -sgn
    return y * (8.0 / np.pi ** 2)


def additive(f0, n, partials, phase_rng=None, amp_env=None):
    """sum of harmonic/inharmonic partials following f0 (scalar or array).
    partials: iterable of (ratio, amp) or (ratio, amp, t60). Partials above 0.92*Nyquist are skipped
    (faded when a pitch trajectory crosses the limit)."""
    f0 = np.broadcast_to(np.asarray(f0, dtype=np.float64), (n,))
    ph = phase_cycles(f0, n)
    t = t_axis(n)
    y = np.zeros(n)
    lim = NYQ * 0.92
    for p in partials:
        ratio, amp = p[0], p[1]
        fk = f0 * ratio
        if np.min(fk) >= lim:
            continue
        phi = phase_rng.uniform(0, 1) if phase_rng is not None else 0.0
        comp = amp * np.sin(TWO_PI * (ratio * ph + phi))
        if np.max(fk) > lim * 0.9:
            comp *= np.clip((lim - fk) / (lim * 0.1), 0.0, 1.0)
        if len(p) > 2 and p[2]:
            comp *= np.exp(-LN1000 * t / p[2])
        y += comp
    if amp_env is not None:
        y *= amp_env
    return y


def fm(fc, n, ratio=1.0, index=1.0, fb_phase=0.0):
    """two-operator FM: carrier fc (scalar/array), modulator at fc*ratio, index scalar/array"""
    fc = np.broadcast_to(np.asarray(fc, dtype=np.float64), (n,))
    mod = np.sin(TWO_PI * phase_cycles(fc * ratio, n))
    idx = np.broadcast_to(np.asarray(index, dtype=np.float64), (n,))
    return np.sin(TWO_PI * phase_cycles(fc, n, fb_phase) + idx * mod)


# =====================================================================================  noise
_PINK_B = np.array([0.049922035, -0.095993537, 0.050612699, -0.004408786])
_PINK_A = np.array([1.0, -2.494956002, 2.017265875, -0.522189400])


def white(n, r):
    return r.standard_normal(n)


def pink(n, r):
    """pink (1/f) noise, unit RMS approx (Kellet 3-pole filter)"""
    w = r.standard_normal(n + 2000)
    y = signal.lfilter(_PINK_B, _PINK_A, w)[2000:]
    return y / 0.0936


def brown(n, r, leak=0.998):
    """brown (1/f^2, leaky-integrated) noise, unit-RMS approx, DC-blocked"""
    w = r.standard_normal(n + 4000)
    y = signal.lfilter([1.0], [1.0, -leak], w)[4000:]
    y = dc_block(y, 8.0)
    return y / (np.sqrt(1.0 / (1.0 - leak * leak)) * 0.93)


def noise_band(n, r, lo, hi, order=2):
    return bandpass(white(n, r), lo, hi, order)


def lp_noise(n, r, fc, order=2):
    """smooth random control signal ~unit RMS (lowpassed white noise, renormalised)"""
    y = lowpass(r.standard_normal(n + SR // 4), fc, order)[SR // 4:]
    s = np.std(y)
    return y / s if s > 0 else y


def ctrl_noise(n, r, fc, rate=1000.0, order=2):
    """smooth random control signal (~unit RMS) generated at a control rate and linearly upsampled to n
    audio samples -- ~50x cheaper than lp_noise for slow modulations (jitter, drift, flutter < ~rate/4 Hz)"""
    m = int(np.ceil(n * rate / SR)) + 2
    pre = int(rate // 4)
    w = r.standard_normal(m + pre)
    fcl = min(float(fc), rate * 0.45)
    y = signal.sosfilt(signal.butter(order, fcl, "low", fs=rate, output="sos"), w)[pre:]
    s = np.std(y)
    y = y / s if s > 0 else y
    return np.interp(np.arange(n) * (rate / SR), np.arange(m), y)


def crackle(n, r, rate, amp_sigma=1.0, dur_range=(0.0003, 0.003), hp=1500.0, decay=True):
    """Poisson process of short noise clicks (fire crackle, grass, sparks).
    rate: events/s (scalar or array(n)).  Returns mono."""
    rate = np.broadcast_to(np.asarray(rate, dtype=np.float64), (n,))
    p = rate / SR
    hits = np.nonzero(r.random(n) < p)[0]
    y = np.zeros(n)
    if len(hits) == 0:
        return y
    maxlen = max(4, int(dur_range[1] * SR))
    amps = np.exp(r.normal(0, amp_sigma, len(hits)))
    lens = r.integers(max(2, int(dur_range[0] * SR)), maxlen + 1, len(hits))
    grain_bank = r.standard_normal((16, maxlen))
    k = np.arange(maxlen)
    for i, (h, a, L) in enumerate(zip(hits, amps, lens)):
        g = grain_bank[i % 16, :L] * (np.exp(-5.0 * k[:L] / L) if decay else 1.0)
        e = min(n, h + L)
        y[h:e] += a * g[: e - h]
    if hp:
        y = highpass(y, hp, 2)
    return y


# =====================================================================================  envelopes
def env_points(points, n, curve="lin"):
    """breakpoint envelope. points = [(t_sec, value), ...]; curve 'lin' | 'db' (interp in dB) | 'cos'"""
    t = t_axis(n)
    ts = np.array([p[0] for p in points], dtype=np.float64)
    vs = np.array([p[1] for p in points], dtype=np.float64)
    if curve == "db":
        vdb = lin2db(np.maximum(vs, 1e-6))
        e = db2lin(np.interp(t, ts, vdb))
        e[t >= ts[-1]] = vs[-1]
        e[t <= ts[0]] = vs[0]
        return e
    if curve == "cos":
        idx = np.clip(np.searchsorted(ts, t, side="right") - 1, 0, len(ts) - 2)
        t0, t1 = ts[idx], ts[idx + 1]
        v0, v1 = vs[idx], vs[idx + 1]
        u = np.clip((t - t0) / np.maximum(t1 - t0, 1e-9), 0.0, 1.0)
        u = 0.5 - 0.5 * np.cos(np.pi * u)
        return v0 + (v1 - v0) * u
    return np.interp(t, ts, vs)


def env_decay(n, t60, attack=0.0015, hold=0.0):
    """linear attack (s), optional hold, exponential decay reaching -60 dB after t60 s"""
    t = t_axis(n)
    e = np.exp(-LN1000 * np.maximum(t - attack - hold, 0.0) / max(t60, 1e-4))
    if attack > 0:
        e *= np.clip(t / attack, 0.0, 1.0)
    return e


def env_adsr(n, a, d, s, r, gate=None, curve=3.0):
    """ADSR; gate = note-on length in seconds (default: n - release). Exponential-ish segments."""
    t = t_axis(n)
    gate = (n / SR - r) if gate is None else gate
    e = np.zeros(n)
    a = max(a, 1e-4)
    ma = t < a
    e[ma] = (t[ma] / a) ** (1.0 / max(curve * 0.5, 1.0))
    md = (t >= a) & (t < gate)
    e[md] = s + (1.0 - s) * np.exp(-curve * (t[md] - a) / max(d, 1e-4))
    # release from whatever level at gate
    lvl_gate = s + (1.0 - s) * np.exp(-curve * max(gate - a, 0) / max(d, 1e-4)) if gate > a else min(gate / a, 1.0)
    mr = t >= gate
    e[mr] = lvl_gate * np.exp(-LN1000 * (t[mr] - gate) / max(r, 1e-4))
    return e


def fade(x, fin=0.0, fout=0.0, shape="cos"):
    """in-place-safe fade in/out on the last axis"""
    x = np.array(x, dtype=np.float64, copy=True)
    n = x.shape[-1]
    ni, no = min(n, n_of(fin)), min(n, n_of(fout))
    if ni > 0:
        u = np.linspace(0, 1, ni)
        w = 0.5 - 0.5 * np.cos(np.pi * u) if shape == "cos" else u
        x[..., :ni] *= w
    if no > 0:
        u = np.linspace(1, 0, no)
        w = 0.5 - 0.5 * np.cos(np.pi * u) if shape == "cos" else u
        x[..., n - no:] *= w
    return x


def smoothstep(u):
    u = np.clip(u, 0.0, 1.0)
    return u * u * (3.0 - 2.0 * u)


# =====================================================================================  filters
def _butter(kind, fc, order):
    if kind == "band":
        lo, hi = fc
        lo = max(lo, 5.0)
        hi = min(hi, NYQ * 0.98)
        if hi <= lo * 1.01:
            hi = lo * 1.01
        return signal.butter(order, [lo, hi], "bandpass", fs=SR, output="sos")
    fc = float(np.clip(fc, 5.0, NYQ * 0.98))
    return signal.butter(order, fc, kind, fs=SR, output="sos")


def lowpass(x, fc, order=2):
    if fc >= NYQ * 0.98:
        return np.array(x, dtype=np.float64, copy=True)
    return signal.sosfilt(_butter("low", fc, order), x, axis=-1)


def highpass(x, fc, order=2):
    if fc <= 5.0:
        return np.array(x, dtype=np.float64, copy=True)
    return signal.sosfilt(_butter("high", fc, order), x, axis=-1)


def bandpass(x, lo, hi, order=2):
    return signal.sosfilt(_butter("band", (lo, hi), order), x, axis=-1)


def lr4_split(x, fc):
    """Linkwitz-Riley 24 dB/oct crossover -> (low, high); low + high is an allpass (flat magnitude)"""
    lo = signal.butter(2, fc, "low", fs=SR, output="sos")
    hi = signal.butter(2, fc, "high", fs=SR, output="sos")
    return (signal.sosfilt(np.vstack([lo, lo]), x, axis=-1), signal.sosfilt(np.vstack([hi, hi]), x, axis=-1))


def dc_block(x, fc=10.0):
    """first-order DC blocker (highpass)"""
    rr = np.exp(-TWO_PI * fc / SR)
    return signal.lfilter([1.0, -1.0], [1.0, -rr], x, axis=-1)


def biquad_sos(kind, fc, q=0.7071, gain_db=0.0):
    """RBJ audio-EQ-cookbook biquad as a (1,6) sos array.
    kind: lp hp bp (constant 0 dB peak) notch peak lowshelf highshelf allpass"""
    fc = float(np.clip(fc, 5.0, NYQ * 0.98))
    A = 10.0 ** (gain_db / 40.0)
    w0 = TWO_PI * fc / SR
    cw, sw = np.cos(w0), np.sin(w0)
    alpha = sw / (2.0 * q)
    if kind == "lp":
        b = [(1 - cw) / 2, 1 - cw, (1 - cw) / 2]; a = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == "hp":
        b = [(1 + cw) / 2, -(1 + cw), (1 + cw) / 2]; a = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == "bp":
        b = [alpha, 0.0, -alpha]; a = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == "notch":
        b = [1.0, -2 * cw, 1.0]; a = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == "peak":
        b = [1 + alpha * A, -2 * cw, 1 - alpha * A]; a = [1 + alpha / A, -2 * cw, 1 - alpha / A]
    elif kind == "lowshelf":
        sa = 2 * np.sqrt(A) * alpha
        b = [A * ((A + 1) - (A - 1) * cw + sa), 2 * A * ((A - 1) - (A + 1) * cw), A * ((A + 1) - (A - 1) * cw - sa)]
        a = [(A + 1) + (A - 1) * cw + sa, -2 * ((A - 1) + (A + 1) * cw), (A + 1) + (A - 1) * cw - sa]
    elif kind == "highshelf":
        sa = 2 * np.sqrt(A) * alpha
        b = [A * ((A + 1) + (A - 1) * cw + sa), -2 * A * ((A - 1) + (A + 1) * cw), A * ((A + 1) + (A - 1) * cw - sa)]
        a = [(A + 1) - (A - 1) * cw + sa, 2 * ((A - 1) - (A + 1) * cw), (A + 1) - (A - 1) * cw - sa]
    elif kind == "allpass":
        b = [1 - alpha, -2 * cw, 1 + alpha]; a = [1 + alpha, -2 * cw, 1 - alpha]
    else:
        raise ValueError(kind)
    b = np.array(b) / a[0]
    a = np.array(a) / a[0]
    return np.concatenate([b, a])[None, :]


def biquad(x, kind, fc, q=0.7071, gain_db=0.0):
    return signal.sosfilt(biquad_sos(kind, fc, q, gain_db), x, axis=-1)


def peq(x, fc, gain_db, q=1.0):
    return biquad(x, "peak", fc, q, gain_db)


def shelf(x, fc, gain_db, kind="low", q=0.7071):
    return biquad(x, "lowshelf" if kind == "low" else "highshelf", fc, q, gain_db)


def eq_chain(x, bands):
    """bands: list of (kind, fc, gain_db, q)"""
    if not bands:
        return x
    sos = np.vstack([biquad_sos(k, fc, q, g) for (k, fc, g, q) in bands])
    return signal.sosfilt(sos, x, axis=-1)


def tv_biquad(x, kind, fc, q=0.7071, gain_db=0.0, block=128):
    """time-varying RBJ biquad, coefficients updated every `block` samples (state carried).
    fc / q / gain_db may be scalars or arrays of len(x). Mono or stereo input."""
    x = np.asarray(x, dtype=np.float64)
    n = x.shape[-1]
    fc = np.broadcast_to(np.asarray(fc, dtype=np.float64), (n,))
    q = np.broadcast_to(np.asarray(q, dtype=np.float64), (n,))
    g = np.broadcast_to(np.asarray(gain_db, dtype=np.float64), (n,))
    stereo = x.ndim == 2
    y = np.empty_like(x)
    zi = np.zeros((1, 2, 2)) if stereo else np.zeros((1, 2))
    for s in range(0, n, block):
        e = min(n, s + block)
        c = (s + e) // 2
        sos = biquad_sos(kind, fc[c], q[c], g[c])
        if stereo:
            y[:, s:e], zi = signal.sosfilt(sos, x[:, s:e], axis=-1, zi=zi)
        else:
            y[s:e], zi = signal.sosfilt(sos, x[s:e], zi=zi)
    return y


def svf(x, fc, q=0.7071, mode="lp"):
    """per-sample TPT state-variable filter (Zavalishin) with audio-rate fc; pure python loop,
    use only on short clips (< ~1 s). mode: lp | bp | hp | notch"""
    x = np.asarray(x, dtype=np.float64)
    n = len(x)
    fc = np.broadcast_to(np.asarray(fc, dtype=np.float64), (n,))
    gs = np.tan(np.pi * np.clip(fc, 5.0, NYQ * 0.95) / SR)
    k = 1.0 / q
    y = np.empty(n)
    ic1 = ic2 = 0.0
    xl = x.tolist()
    gl = gs.tolist()
    for i in range(n):
        gg = gl[i]
        a1 = 1.0 / (1.0 + gg * (gg + k))
        v3 = xl[i] - ic2
        v1 = a1 * ic1 + gg * a1 * v3
        v2 = ic2 + gg * v1
        ic1 = 2 * v1 - ic1
        ic2 = 2 * v2 - ic2
        if mode == "lp":
            y[i] = v2
        elif mode == "bp":
            y[i] = v1
        elif mode == "hp":
            y[i] = xl[i] - k * v1 - v2
        else:
            y[i] = xl[i] - k * v1
    return y


def lp_sweep(x, fc, n_bank=14, fmin=150.0, fmax=20000.0, order=2):
    """smooth time-varying lowpass via crossfading a bank of fixed Butterworth filters
    (fully vectorised, zipper-free).  fc: array(len) or scalar."""
    x = np.asarray(x, dtype=np.float64)
    n = x.shape[-1]
    fc = np.clip(np.broadcast_to(np.asarray(fc, dtype=np.float64), (n,)), fmin, fmax)
    cut = np.geomspace(fmin, fmax, n_bank)
    pos = np.interp(np.log(fc), np.log(cut), np.arange(n_bank))
    lo = np.floor(pos).astype(int)
    fr = pos - lo
    out = np.zeros_like(x)
    used = np.unique(np.concatenate([lo, np.minimum(lo + 1, n_bank - 1)]))
    for i in used:
        w = np.where(lo == i, 1.0 - fr, 0.0) + np.where(lo + 1 == i, fr, 0.0)
        if not np.any(w > 0):
            continue
        yi = x if cut[i] >= NYQ * 0.97 else lowpass(x, cut[i], order)
        out += yi * w
    return out


def onepole(x, fc):
    """one-pole lowpass smoother (fc in Hz), works on control signals too"""
    a = np.exp(-TWO_PI * fc / SR)
    return signal.lfilter([1.0 - a], [1.0, -a], x, axis=-1)


def onepole_coef(tau_s, rate=SR):
    return np.exp(-1.0 / max(tau_s * rate, 1e-9))


def comb_ff(x, delay_s, g):
    d = max(1, n_of(delay_s))
    y = np.array(x, dtype=np.float64, copy=True)
    y[..., d:] += g * x[..., :-d]
    return y


# =====================================================================================  modal / resonators
def resonator_bank(exc, freqs, t60s, gains):
    """drive a bank of 2-pole resonators (impulse response g*r^n*sin(w(n+1))) with excitation"""
    exc = np.asarray(exc, dtype=np.float64)
    y = np.zeros_like(exc)
    for f, t60, g in zip(freqs, t60s, gains):
        if f <= 0 or f >= NYQ * 0.95 or g == 0:
            continue
        r = np.exp(-LN1000 / (max(t60, 1e-3) * SR))
        w = TWO_PI * f / SR
        y += signal.lfilter([g * np.sin(w)], [1.0, -2.0 * r * np.cos(w), r * r], exc, axis=-1)
    return y


def modal(freqs, amps, t60s, n, r=None, phases=None, attack=0.0005, fdrift=None):
    """direct modal synthesis: sum of exponentially damped sinusoids (mono).
    fdrift: optional array(n) of pitch multipliers applied to all modes (pitch glides)."""
    t = t_axis(n)
    y = np.zeros(n)
    base_ph = None
    if fdrift is not None:
        base_ph = phase_cycles(np.asarray(fdrift, dtype=np.float64), n)   # integral of multiplier/SR
    for i, (f, a, t60) in enumerate(zip(freqs, amps, t60s)):
        if f <= 0 or f >= NYQ * 0.95 or a == 0:
            continue
        ph0 = phases[i] if phases is not None else (r.uniform(0, 1) if r is not None else 0.0)
        if base_ph is None:
            arg = TWO_PI * (f * t + ph0)
        else:
            arg = TWO_PI * (f * base_ph + ph0)
        y += a * np.exp(-LN1000 * t / max(t60, 1e-4)) * np.sin(arg)
    if attack > 0:
        y *= np.clip(t / attack, 0.0, 1.0)
    return y


# =====================================================================================  resampling
def interp_cubic(x, pos):
    """Catmull-Rom cubic interpolation of 1-D x at fractional positions pos"""
    x = np.asarray(x, dtype=np.float64)
    n = len(x)
    pos = np.clip(pos, 0.0, n - 1.000001)
    i = np.floor(pos).astype(np.int64)
    f = pos - i
    xm1 = x[np.clip(i - 1, 0, n - 1)]
    x0 = x[i]
    x1 = x[np.clip(i + 1, 0, n - 1)]
    x2 = x[np.clip(i + 2, 0, n - 1)]
    c1 = 0.5 * (x1 - xm1)
    c2 = xm1 - 2.5 * x0 + 2.0 * x1 - 0.5 * x2
    c3 = 0.5 * (x2 - xm1) + 1.5 * (x0 - x1)
    return ((c3 * f + c2) * f + c1) * f + x0


def varispeed(x, rate, n_out=None):
    """read x at time-varying speed rate (scalar or array(n_out)); rate>1 = higher pitch & faster.
    Works on mono or stereo."""
    x = np.asarray(x, dtype=np.float64)
    n_in = x.shape[-1]
    if np.isscalar(rate) or np.ndim(rate) == 0:
        rate = float(rate)
        if n_out is None:
            n_out = int((n_in - 1) / rate)
        pos = np.arange(n_out) * rate
    else:
        rate = np.asarray(rate, dtype=np.float64)
        if n_out is None:
            n_out = len(rate)
        rate = np.broadcast_to(rate, (n_out,)) if rate.size == 1 else rate[:n_out]
        pos = np.cumsum(rate) - rate[0]
    valid = pos <= n_in - 1
    if x.ndim == 2:
        y = np.vstack([interp_cubic(x[0], pos), interp_cubic(x[1], pos)])
        y[:, ~valid] = 0.0
    else:
        y = interp_cubic(x, pos)
        y[~valid] = 0.0
    return y


def resample_ratio(x, ratio):
    """change duration/pitch by fixed ratio (ratio<1 -> slower & lower); anti-aliased when speeding up"""
    if abs(ratio - 1.0) < 1e-6:
        return np.array(x, dtype=np.float64, copy=True)
    if ratio > 1.0:
        x = lowpass(x, NYQ * 0.9 / ratio, 4)
    return varispeed(x, ratio)


def pitch_shift(x, semitones):
    """tape-style pitch shift (duration changes accordingly)"""
    return resample_ratio(x, 2.0 ** (semitones / 12.0))


# =====================================================================================  Karplus-Strong
def karplus_strong(freq, dur, r, t60=2.0, brightness=0.5, pick_pos=0.14, exc=None, exc_lp=None,
                   nonlin=None, cents=None, exc_len=None, damp_after=None):
    """Vectorised Karplus-Strong plucked string (one block == one period).
    freq       : target f0 (Hz)
    t60        : decay time of the fundamental (s)
    brightness : 0..1 -> loop lowpass H(z)=a+(1-a)z^-1, a in [0.5, 0.99]
    pick_pos   : pluck position (fraction of string) -> comb notch on excitation
    exc        : optional custom excitation (else noise burst of one period)
    exc_lp     : optional lowpass (Hz) on excitation (soft pluck)
    nonlin     : optional f(fb, period_index)->fb applied to feedback block (e.g. sawari buzz)
    cents      : optional array(n) of pitch deviations in cents (bends); applied by varispeed
    damp_after : optional (t_sec, new_t60) -> string damped (muted) after t_sec
    The integer-delay loop is re-tuned exactly by resampling the output."""
    n = n_of(dur)
    a = 0.5 + 0.49 * float(np.clip(brightness, 0.0, 1.0))
    P = SR / freq
    g_per = 10.0 ** (-3.0 / (freq * t60))
    # high notes: the loop lowpass alone would over-damp -> raise brightness until t60 is reachable
    while a < 0.985:
        w_ = TWO_PI * freq / SR
        hm_ = np.sqrt(a * a + (1 - a) ** 2 + 2 * a * (1 - a) * np.cos(w_))
        if g_per / hm_ <= 0.9995:
            break
        a += 0.01
    N = max(2, int(np.floor(P - (1.0 - a))))
    f_int = SR / (N + (1.0 - a))
    base_rate = freq / f_int
    rate = base_rate * (cents2ratio(cents) if cents is not None else np.ones(n))
    n_ks = int(np.ceil(np.sum(rate))) + 8 if cents is not None else int(np.ceil(n * base_rate)) + 8
    # loop gain: per-period amplitude factor for desired t60 at f0, compensating filter loss at f0
    w = TWO_PI * f_int / SR
    hmag = np.sqrt(a * a + (1 - a) ** 2 + 2 * a * (1 - a) * np.cos(w))
    g_per = 10.0 ** (-3.0 / (f_int * t60))
    g = min(g_per / hmag, 0.99995)
    g2 = None
    if damp_after is not None:
        g2 = min(10.0 ** (-3.0 / (f_int * damp_after[1])) / hmag, 0.99999)
        k_damp = int(damp_after[0] * f_int)
    y = np.zeros(n_ks + N + 2)
    L = exc_len if exc_len else N
    if exc is None:
        e = r.uniform(-1, 1, L)
        e -= e.mean()
    else:
        e = np.asarray(exc, dtype=np.float64)
    if exc_lp:
        e = lowpass(e, exc_lp, 2)
    if pick_pos and pick_pos > 0:
        d = max(1, int(round(pick_pos * N)))
        e2 = e.copy()
        e2[d:] -= e[:-d]
        e = e2
    y[: len(e)] += e
    ga, gb = a, (1.0 - a)
    k = 0
    for s in range(N, n_ks, N):
        k += 1
        e_ = min(s + N, n_ks)
        m = e_ - s
        prev = y[s - N: s - N + m]
        if s - N - 1 >= 0:
            prev1 = y[s - N - 1: s - N - 1 + m]
        else:
            prev1 = np.concatenate([[0.0], y[0: m - 1]])
        gg = g if (g2 is None or k < k_damp) else g2
        fb = gg * (ga * prev + gb * prev1)
        if nonlin is not None:
            fb = nonlin(fb, k)
        y[s: e_] += fb
    y = y[:n_ks]
    out = varispeed(y, rate if cents is not None else base_rate, n_out=n)
    return out


# =====================================================================================  reverb
REVERB_PRESETS = {
    # outdoor field: ground bounce + sparse distant echoes (treeline / hills) + faint short diffuse tail
    "field":  dict(rt60=0.7, length=1.6, predelay=0.004, n_er=6, er_span=0.03, er_gain=0.5,
                   echoes=[(0.23, 0.10), (0.37, 0.07), (0.61, 0.045), (0.93, 0.03)],
                   bands=(1.0, 0.9, 0.55, 0.3), tail_gain=0.55, build=0.01),
    "hall":   dict(rt60=2.3, length=3.8, predelay=0.022, n_er=18, er_span=0.085, er_gain=0.55,
                   echoes=[], bands=(1.2, 1.0, 0.75, 0.45), tail_gain=1.0, build=0.03),
    "temple": dict(rt60=3.3, length=5.2, predelay=0.034, n_er=14, er_span=0.13, er_gain=0.6,
                   echoes=[], bands=(1.25, 1.0, 0.62, 0.33), tail_gain=1.0, build=0.05),
    "huge":   dict(rt60=8.0, length=11.0, predelay=0.065, n_er=24, er_span=0.28, er_gain=0.45,
                   echoes=[(0.41, 0.12), (0.79, 0.08)], bands=(1.3, 1.0, 0.6, 0.3), tail_gain=1.0, build=0.35),
}
_IR_CACHE = {}
_BAND_EDGES = (250.0, 1500.0, 5000.0)


def make_ir(preset="hall", seed=7):
    """synthetic true-stereo IR -> array (2, 2, n): ir[in_ch, out_ch].
    early reflections (random taps, lowpassed) + exponentially decaying band-split noise tail
    with frequency-dependent RT60; ipsi/contra channels decorrelated. Unit energy per out channel."""
    key = (preset, seed)
    if key in _IR_CACHE:
        return _IR_CACHE[key]
    p = REVERB_PRESETS[preset]
    n = n_of(p["length"])
    t = t_axis(n)
    r = rng("ir", preset, seed)
    ir = np.zeros((2, 2, n))
    rt = p["rt60"]
    for i in range(2):
        for o in range(2):
            contra = (i != o)
            wn = r.standard_normal(n)
            tail = np.zeros(n)
            edges = (0.0,) + _BAND_EDGES + (NYQ,)
            for b, mul in enumerate(p["bands"]):
                lo, hi = edges[b], edges[b + 1]
                if lo <= 0:
                    band = lowpass(wn, hi, 3)
                elif hi >= NYQ:
                    band = highpass(wn, lo, 3)
                else:
                    band = bandpass(wn, lo, hi, 3)
                tail += band * np.exp(-LN1000 * t / (rt * mul))
            pd = p["predelay"] + (0.0035 if contra else 0.0) + r.uniform(0, 0.002)
            onset = np.clip((t - pd) / max(p["build"], 1e-3), 0.0, 1.0)
            tail *= onset ** 1.5 * p["tail_gain"]
            # early reflections
            er = np.zeros(n)
            n_er = p["n_er"]
            for k in range(n_er):
                d = pd * 0.4 + r.uniform(0.0, p["er_span"]) * (k + 1) / n_er
                idx = n_of(d)
                if idx < n - 8:
                    amp = p["er_gain"] * (1.0 - 0.7 * k / n_er) * r.choice([-1.0, 1.0]) * r.uniform(0.5, 1.0)
                    er[idx] += amp
            for (d, gdb) in p["echoes"]:
                idx = n_of(d * r.uniform(0.95, 1.05) + (0.007 if contra else 0.0))
                if idx < n - 8:
                    er[idx] += gdb * r.choice([-1.0, 1.0])
            er = lowpass(er, 6000.0 if preset != "field" else 4000.0, 2)
            h = er + tail
            h = dc_block(h, 20.0)
            e = np.sqrt(np.sum(h * h))
            h /= max(e, 1e-12)
            ir[i, o] = h * (0.62 if contra else 1.0)
    _IR_CACHE[key] = ir
    return ir


def convolve_reverb(x, preset="hall", seed=7, n_out=None):
    """true-stereo convolution reverb (wet only). x mono or stereo; returns (2, n_out)
    (default n_out = len(x), tail truncated)."""
    x = as_stereo(x)
    n = x.shape[-1]
    n_out = n if n_out is None else n_out
    ir = make_ir(preset, seed)
    out = np.zeros((2, n_out))
    for i in range(2):
        if not np.any(x[i]):
            continue
        for o in range(2):
            y = signal.oaconvolve(x[i], ir[i, o])
            m = min(n_out, len(y))
            out[o, :m] += y[:m]
    return out


def reverb_tail_len(preset):
    return n_of(REVERB_PRESETS[preset]["length"])


# =====================================================================================  dynamics
def _block_level(x, block, mode="peak"):
    xs = as_stereo(x)
    n = xs.shape[-1]
    nb = int(np.ceil(n / block))
    pad = nb * block - n
    a = np.abs(np.pad(xs, ((0, 0), (0, pad))))
    a = a.reshape(2, nb, block)
    if mode == "rms":
        lv = np.sqrt(np.mean(a * a, axis=2)).max(axis=0)
    else:
        lv = a.max(axis=2).max(axis=0)
    return lv


def _smooth_ar(target, att_coef, rel_coef, init=None):
    """attack/release smoothing of a gain-reduction curve in dB (loop over blocks).
    target: desired gain dB (<=0). Attack = moving towards more reduction."""
    out = np.empty_like(target)
    g = target[0] if init is None else init
    tl = target.tolist()
    for i, tg in enumerate(tl):
        if tg < g:
            g = att_coef * g + (1.0 - att_coef) * tg
        else:
            g = rel_coef * g + (1.0 - rel_coef) * tg
        out[i] = g
    return out


def compressor(x, threshold_db=-18.0, ratio=2.0, attack_ms=15.0, release_ms=180.0, knee_db=6.0,
               makeup_db=0.0, key=None, block=64, mode="rms"):
    """feed-forward stereo-linked compressor (block-rate detector, sample-rate interpolated gain)"""
    xs = as_stereo(x)
    k = xs if key is None else as_stereo(key)
    lv = _block_level(k, block, mode)
    ldb = lin2db(lv, 1e-9)
    over = ldb - threshold_db
    gr = np.zeros_like(ldb)
    hk = knee_db / 2.0
    m1 = over > hk
    gr[m1] = -(over[m1]) * (1.0 - 1.0 / ratio)
    m2 = (over > -hk) & ~m1
    gr[m2] = -((over[m2] + hk) ** 2) / (2.0 * max(knee_db, 1e-6)) * (1.0 - 1.0 / ratio)
    brate = SR / block
    g = _smooth_ar(gr, onepole_coef(attack_ms / 1000.0, brate), onepole_coef(release_ms / 1000.0, brate), init=0.0)
    n = xs.shape[-1]
    gs = np.interp(np.arange(n), (np.arange(len(g)) + 0.5) * block, g)
    out = xs * db2lin(gs + makeup_db)
    return out, gs


def true_peak_envelope(x, oversample=4, chunk=SR * 8):
    """per-sample true-peak estimate (max |x| of the 4x-oversampled signal around each sample),
    max over channels.  Chunked to bound memory."""
    xs = as_stereo(x)
    n = xs.shape[-1]
    out = np.zeros(n)
    halo = 64
    for s in range(0, n, chunk):
        e = min(n, s + chunk)
        a, b = max(0, s - halo), min(n, e + halo)
        seg = xs[:, a:b]
        up = signal.resample_poly(seg, oversample, 1, axis=-1, window=("kaiser", 8.0))
        up = np.abs(up).max(axis=0)
        # max over the oversampled points belonging to [i-0.5, i+0.5]
        m = up[: (b - a) * oversample].reshape(b - a, oversample).max(axis=1)
        m = np.maximum(m, np.abs(seg).max(axis=0))
        # include the neighbouring half-sample region
        m2 = np.maximum(m, np.concatenate([m[1:], m[-1:]]))
        out[s:e] = m2[s - a: s - a + (e - s)]
    return out


def true_peak_dbtp(x, oversample=4):
    return float(lin2db(np.max(true_peak_envelope(x, oversample))))


def limiter(x, ceiling_db=-1.0, lookahead_ms=5.0, release_ms=120.0, oversample=4, true_peak=True):
    """lookahead brick-wall limiter with true-peak detection.
    gain = min over lookahead window of required gain, smoothed by a moving average of the same
    length (guaranteed <= requirement at the peak), then a release smoother."""
    xs = as_stereo(x)
    n = xs.shape[-1]
    ceil = db2lin(ceiling_db)
    tp = true_peak_envelope(xs, oversample) if true_peak else np.abs(xs).max(axis=0)
    req = np.minimum(1.0, ceil / np.maximum(tp, 1e-12))
    if np.all(req >= 1.0):
        return xs.copy(), np.ones(n)
    L = max(2, n_of(lookahead_ms / 1000.0))
    from scipy.ndimage import minimum_filter1d, uniform_filter1d
    # centred min-hold over +-L, then centred moving average over L: for every sample p all
    # averaged values come from windows that contain p  ->  gavg[p] <= req[p]  (no overshoot),
    # while the gain ramps smoothly over ~L samples before each peak (offline lookahead).
    gmin = minimum_filter1d(req, size=2 * L + 1, mode="nearest")
    gavg = uniform_filter1d(gmin, size=L, mode="nearest")
    # release: instant attack (already anticipated), exponential release (block loop)
    block = 32
    nb = int(np.ceil(n / block))
    gb = np.pad(gavg, (0, nb * block - n), mode="edge").reshape(nb, block).min(axis=1)
    gdb = lin2db(gb, 1e-9)
    rel = onepole_coef(release_ms / 1000.0, SR / block)
    sm = _smooth_ar(gdb, 0.0, rel, init=0.0)
    gs = db2lin(np.interp(np.arange(n), (np.arange(nb) + 0.5) * block, sm))
    g = np.minimum(gs, gavg)
    return xs * g, g


def softclip(x, drive=1.0):
    """tanh soft clipper normalised so small signals keep unity gain"""
    if drive <= 0:
        return x
    return np.tanh(drive * x) / drive


def soft_limit(x, ceiling=1.0, knee=0.7):
    """transparent below knee*ceiling, smooth tanh approach to the ceiling above it (per sample)"""
    k = knee * ceiling
    a = np.abs(x)
    over = a > k
    if not np.any(over):
        return x
    y = x.copy()
    room = ceiling - k
    y[over] = np.sign(x[over]) * (k + room * np.tanh((a[over] - k) / room))
    return y


def saturate(x, amount=0.3):
    """gentle asymmetric tape-like saturation (adds even+odd harmonics), amount 0..1"""
    k = 1.0 + 4.0 * amount
    y = np.tanh(k * x + 0.15 * amount) - np.tanh(0.15 * amount)
    return y / k


# =====================================================================================  timeline
class Timeline:
    """stereo accumulation buffer; add clips at absolute sample offsets (negative/overflow-safe)"""

    def __init__(self, n, channels=2):
        self.n = int(n)
        self.buf = np.zeros((channels, self.n))

    def add(self, clip, start, gain=1.0):
        """clip: mono (added equally, no pan law) or stereo; start: sample index (int)"""
        clip = np.asarray(clip, dtype=np.float64)
        if clip.ndim == 1:
            clip = np.vstack([clip, clip])
        m = clip.shape[-1]
        s = int(start)
        a = max(0, -s)
        b = min(m, self.n - s)
        if b <= a:
            return
        self.buf[:, s + a: s + b] += gain * clip[:, a:b]

    def add_at(self, clip, t_sec, anchor=0, gain=1.0):
        """place so that clip sample `anchor` lands exactly at t_sec"""
        self.add(clip, int(round(t_sec * SR)) - int(anchor), gain)


def place(buf, clip, start, gain=1.0):
    """functional variant of Timeline.add for raw (2,n) or (n,) buffers"""
    clip = np.asarray(clip, dtype=np.float64)
    if buf.ndim == 2 and clip.ndim == 1:
        clip = np.vstack([clip, clip])
    m = clip.shape[-1]
    n = buf.shape[-1]
    s = int(start)
    a = max(0, -s)
    b = min(m, n - s)
    if b <= a:
        return
    buf[..., s + a: s + b] += gain * clip[..., a:b]
