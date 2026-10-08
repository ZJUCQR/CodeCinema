"""
codecinema.audio.synth -- synthesized melodic instruments (the fallback for every sampled instrument, and the
only source of the Chinese plucked, blown and bowed instruments).

Every engine takes a MIDI pitch (float), a gate `dur` in seconds (the note-on time), a velocity 0..1, a numpy
Generator and optional `cents` (pitch deviation in cents: scalar or array at dsp.SR), and returns float64 audio at
dsp.SR whose first sample is the note onset.  Single sources return mono (n,), ensembles return stereo (2, n).
The clip includes the natural release / ring after the gate.  Peak level ~ velocity (the catalog matches loudness).

    families  modal (mallets, bells, yangqin, kalimba, steel drums), piano, plucked (Karplus-Strong guitars, harp,
              basses, ukulele, banjo, pizzicato, pipa, guzheng, guqin), bowed (solo strings, sections, tremolo,
              erhu), winds (flutes, whistles, ocarina, reeds, suona, dizi, sheng, accordion, harmonica), brass, voices
              (choir aahs, voice oohs), pads
Pipa, guqin, dizi, sheng and the string/choir ensembles are adapted from the Night Revels and Silver Grass packs.
"""
import numpy as np
from scipy import signal

from codecinema.audio import dsp
from codecinema.audio.dsp import LN1000, SR, TWO_PI, n_of, t_axis

NYQ_SAFE = 0.45 * SR


def hz(midi):
    return float(dsp.midi2hz(midi))


def _nrm(x):
    return x / (dsp.peak(x) + 1e-12)


def _cents(cents, n):
    """scalar / array / None -> array(n) of cents (arrays are held at their last value)"""
    if cents is None:
        return np.zeros(n)
    if np.ndim(cents) == 0:
        return np.full(n, float(cents))
    c = np.asarray(cents, dtype=np.float64)
    if len(c) >= n:
        return c[:n].copy()
    return np.concatenate([c, np.full(n - len(c), c[-1] if len(c) else 0.0)])


def _vib(n, r, depth, rate, delay=0.25, ramp=0.4):
    """delayed vibrato in cents with slight rate wander"""
    t = t_axis(n)
    vr = rate * (1.0 + 0.05 * dsp.ctrl_noise(n, r, 0.7))
    return depth * dsp.smoothstep((t - delay) / ramp) * np.sin(TWO_PI * dsp.phase_cycles(vr, n, r.uniform()))


CR = 1000.0            # control rate (Hz) of slow modulation curves (vibrato, drift, bow pressure, envelopes)


def _ctrl_axis(n):
    m = int(np.ceil(n * CR / SR)) + 2
    return m, np.arange(m) / CR


def _cnoise(m, r, fc, order=2):
    """smooth unit-RMS random curve at the control rate"""
    pre = int(CR // 4)
    w = r.standard_normal(m + pre)
    y = signal.sosfilt(signal.butter(order, min(float(fc), CR * 0.45), "low", fs=CR, output="sos"), w)[pre:]
    sd = np.std(y)
    return y / sd if sd > 0 else y


def _up(x, n):
    """control-rate curve -> n audio samples (linear interpolation)"""
    return np.interp(np.arange(n) * (CR / SR), np.arange(len(x)), x)


def _env_ctrl(points, tc):
    """cosine-interpolated breakpoint envelope sampled at the control times tc"""
    ts = np.array([p[0] for p in points], dtype=np.float64)
    vs = np.array([p[1] for p in points], dtype=np.float64)
    idx = np.clip(np.searchsorted(ts, tc, side="right") - 1, 0, len(ts) - 2)
    u = np.clip((tc - ts[idx]) / np.maximum(ts[idx + 1] - ts[idx], 1e-9), 0.0, 1.0)
    return vs[idx] + (vs[idx + 1] - vs[idx]) * (0.5 - 0.5 * np.cos(np.pi * u))


def _sustain_points(attack, dur, release, peak=1.0, sustain=0.9, decay=0.15, end=1e9):
    pts = [(0.0, 0.0), (attack, peak)]
    if dur > attack + decay:
        pts += [(attack + decay, sustain), (dur, sustain)]
    else:
        pts += [(max(dur, attack + 1e-3), peak)]
    return pts + [(pts[-1][0] + release, 0.0), (max(end, pts[-1][0] + release + 1.0), 0.0)]


def _sustain_env(n, attack, dur, release, peak=1.0, sustain=0.9, decay=0.15):
    """attack to `peak`, settle to `sustain`, hold to the gate, cosine release"""
    pts = [(0.0, 0.0), (attack, peak)]
    if dur > attack + decay:
        pts += [(attack + decay, sustain), (dur, sustain)]
    else:
        pts += [(max(dur, attack + 1e-3), peak)]
    pts += [(pts[-1][0] + release, 0.0), (n / SR + 1.0, 0.0)]
    return dsp.env_points(pts, n, "cos")


def _damp(y, gate, t60):
    """the player damps the sound at `gate` (exponential decay with the given T60)"""
    n = y.shape[-1]
    k = n_of(gate)
    if k >= n:
        return y
    t = np.arange(n - k) / SR
    y = np.array(y, copy=True)
    y[..., k:] *= np.exp(-LN1000 * t / max(t60, 1e-3))
    return y


def _end_fade(y, sec=0.01):
    return dsp.fade(y, 0.0, min(sec, y.shape[-1] / SR * 0.3))


# ======================================================================================  modal (struck bars / bells)
MALLETS = {
    # ratios of the bar/plate modes, relative amplitudes, T60 of the fundamental at C4 and its pitch scaling,
    # partial T60 tilt, strike noise (band, level), mallet hardness (brightness at full velocity), tremolo
    "celesta": dict(ratios=[1.0, 2.0, 3.01, 4.04, 5.4], amps=[1.0, 0.32, 0.1, 0.05, 0.02], t60=2.4, scale=0.55,
                    tilt=1.1, noise=(1500, 6000, 0.05), hard=0.35, resonator=0.35),
    "glockenspiel": dict(ratios=[1.0, 2.756, 5.404, 8.933], amps=[1.0, 0.42, 0.2, 0.08], t60=7.0, scale=0.25,
                         tilt=0.8, noise=(3000, 12000, 0.12), hard=0.85),
    "music_box": dict(ratios=[1.0, 6.27, 17.55, 3.0], amps=[1.0, 0.12, 0.02, 0.03], t60=4.0, scale=0.45, tilt=0.6,
                      noise=(2500, 9000, 0.1), hard=0.7, tick=0.25),
    "vibraphone": dict(ratios=[1.0, 3.984, 9.0, 2.0], amps=[1.0, 0.28, 0.06, 0.03], t60=6.5, scale=0.35, tilt=1.0,
                       noise=(800, 4000, 0.04), hard=0.3, tremolo=(5.6, 0.3), resonator=0.3),
    "marimba": dict(ratios=[1.0, 3.98, 9.15, 2.0], amps=[1.0, 0.18, 0.05, 0.02], t60=1.5, scale=0.65, tilt=1.7,
                    noise=(300, 2500, 0.08), hard=0.35, resonator=0.6),
    "xylophone": dict(ratios=[1.0, 3.0, 6.06, 9.25], amps=[1.0, 0.3, 0.1, 0.04], t60=0.6, scale=0.55, tilt=1.6,
                      noise=(2000, 9000, 0.18), hard=0.85),
    "tubular_bells": dict(ratios=[0.5, 1.0, 1.5, 2.0, 2.76, 3.0, 4.22, 5.4], amps=[0.12, 1.0, 0.18, 0.5, 0.28, 0.2, 0.12, 0.06],
                          t60=9.0, scale=0.2, tilt=0.55, noise=(1200, 7000, 0.06), hard=0.6),
    "kalimba": dict(ratios=[1.0, 6.27, 17.55], amps=[1.0, 0.2, 0.04], t60=2.2, scale=0.5, tilt=0.9,
                    noise=(1500, 6000, 0.08), hard=0.5, body=[("peak", 380, 4.0, 1.5), ("peak", 950, 2.0, 1.8)]),
    "steel_drums": dict(ratios=[1.0, 2.0, 3.0, 4.0, 5.02], amps=[1.0, 0.55, 0.25, 0.12, 0.05], t60=2.0, scale=0.45,
                        tilt=0.7, noise=(1000, 5000, 0.06), hard=0.55, bloom=1),
    "yangqin": dict(ratios=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0], amps=[1.0, 0.55, 0.35, 0.22, 0.12, 0.08, 0.05],
                    t60=4.5, scale=0.35, tilt=0.8, noise=(1500, 7000, 0.12), hard=0.75, strings=2,
                    body=[("peak", 300, 3.0, 1.2), ("peak", 1200, 2.0, 1.4), ("peak", 3200, 2.0, 1.0)]),
}


def mallet(kind, midi, dur, vel=0.7, r=None, cents=None, damp=None):
    """struck bar / plate / tine. dur is how long the note may ring before a damper (None = let ring)."""
    r = r if r is not None else dsp.rng("mallet", kind, midi)
    p = MALLETS[kind]
    f0 = hz(midi)
    t60_1 = p["t60"] * (261.6 / f0) ** p["scale"]
    ring = float(np.clip(t60_1 * 1.05, 0.3, 12.0))
    L = ring if damp is None else min(dur + 0.35, ring)
    n = n_of(L)
    t = t_axis(n)
    drift = dsp.cents2ratio(_cents(cents, n)) if cents is not None else None
    vel = float(np.clip(vel, 0.02, 1.2))
    bright = 0.35 + 0.65 * vel * (0.5 + 0.5 * p["hard"])
    freqs, amps, t60s = [], [], []
    for i, (ratio, a) in enumerate(zip(p["ratios"], p["amps"])):
        f = f0 * ratio
        if f >= NYQ_SAFE * 0.9:
            continue
        k = np.log2(max(ratio, 0.5) + 1.0)
        freqs.append(f)
        amps.append(a * bright ** (k * 1.6) * r.uniform(0.9, 1.1))
        t60s.append(max(0.04, t60_1 / max(ratio, 1.0) ** p["tilt"]))
    strings = p.get("strings", 1)
    y = np.zeros(n)
    for s in range(strings):
        det = 1.0 + (0.0 if s == 0 else r.uniform(0.0008, 0.0016))
        y += dsp.modal(np.array(freqs) * det, amps, t60s, n, r=r, attack=0.0008, fdrift=drift)
    if p.get("bloom"):
        # steelpan: the octave partial swells a moment after the strike (energy transfer in the note area)
        y += 0.25 * dsp.modal([2.0 * f0], [1.0], [t60_1 * 0.5], n, r=r, fdrift=drift) * dsp.smoothstep(t / 0.06)
    if p.get("resonator"):
        y += p["resonator"] * dsp.modal([f0], [1.0], [t60_1 * 1.3], n, r=r, attack=0.01, fdrift=drift)
    if p.get("tremolo"):
        rate, depth = p["tremolo"]
        y *= 1.0 - depth * (0.5 + 0.5 * np.sin(TWO_PI * rate * t))
    lo, hi, lvl = p["noise"]
    k = n_of(0.03)
    burst = dsp.bandpass(r.standard_normal(k), lo, min(hi, NYQ_SAFE), 2) * np.exp(-t[:k] / (0.002 + 0.004 * (1 - p["hard"])))
    y = _nrm(y)
    y[:k] += lvl * (0.5 + vel) * _nrm(burst)
    if p.get("tick"):
        kt = n_of(0.006)
        y[:kt] += p["tick"] * vel * _nrm(dsp.highpass(r.standard_normal(kt), 4000, 2)) * np.exp(-t[:kt] / 0.001)
    if p.get("body"):
        y = dsp.eq_chain(y, [(b[0], b[1], b[2], b[3]) for b in p["body"]])
    if damp is not None:
        y = _damp(y, dur, damp)
    y = dsp.highpass(y, 40, 2)
    return _end_fade(_nrm(y), 0.05) * vel


def bells(midi, dur, vel=0.7, r=None, bright=0.55, cents=None):
    """church-type bell (stereo): beating doublet partials (hum, prime, tierce, quint, nominal...)"""
    r = r if r is not None else dsp.rng("bells", midi)
    f0 = hz(midi)
    L = min(max(dur + 1.0, 7.0), 9.0)
    n = n_of(L)
    t = t_axis(n)
    table = [(0.5, 0.6, 9.0, 0.4), (1.0, 1.0, 5.5, 0.7), (1.19, 0.45, 3.5, 1.0), (1.5, 0.25, 3.0, 1.2),
             (2.0, 0.5, 2.6, 1.5), (2.52, 0.18, 1.8, 2.0), (3.01, 0.14, 1.4, 2.4), (4.1, 0.08, 0.9, 3.0)]
    out = np.zeros((2, n))
    for ratio, a, t60, split in table:
        f = f0 * ratio * r.uniform(0.999, 1.001)
        if f > NYQ_SAFE * 0.85:
            continue
        a = a * (0.6 + 0.8 * bright) ** np.log2(ratio + 1.0)
        e = np.exp(-LN1000 * t / t60)
        s1 = a * e * np.sin(TWO_PI * (f * t + r.uniform()))
        s2 = a * 0.7 * e * np.sin(TWO_PI * ((f + split) * t + r.uniform()))
        out[0] += 0.75 * s1 + 0.35 * s2
        out[1] += 0.35 * s1 + 0.75 * s2
    k = n_of(0.02)
    clang = dsp.highpass(r.standard_normal(k), 2500, 2) * np.exp(-t[:k] / 0.003)
    out[:, :k] += 0.08 * _nrm(clang)
    out = dsp.fade(out, 0.001, 0.5)
    return _nrm(out) * vel


# ======================================================================================  piano
def piano(midi, dur, vel=0.7, r=None, cents=None, soft=0.0):
    """modal piano: inharmonic partials shaped by the hammer (strike point, felt), double decay, unison-string
    beating, hammer knock, soundboard EQ, damper at the gate; stereo by partial phase spread"""
    r = r if r is not None else dsp.rng("piano", midi)
    f0 = hz(midi)
    vel = float(np.clip(vel, 0.02, 1.2))
    key = float(midi)
    B = 0.00012 * (2.0 ** ((key - 48.0) / 12.0 * 0.95) if key > 48 else 2.0 ** ((48.0 - key) / 12.0 * 0.4))
    t60_1 = float(np.clip(18.0 * (55.0 / f0) ** 0.62, 0.8, 22.0))
    L = min(dur + 0.6, t60_1 + 0.3, 6.5)
    n = n_of(L)
    t = t_axis(n)
    K = int(min(32, max(4, 9500.0 / f0)))
    k = np.arange(1, K + 1)
    fk = f0 * k * np.sqrt(1.0 + B * k * k)
    keep = fk < NYQ_SAFE * 0.9
    k, fk = k[keep], fk[keep]
    hardness = 0.25 + 0.75 * vel * (1.0 - 0.5 * soft)
    slope = 1.55 - 0.65 * hardness
    felt = np.exp(-fk / (900.0 + 5200.0 * hardness ** 1.5))
    strike = np.abs(np.sin(np.pi * k / 8.3)) + 0.12
    amp = strike * felt / k ** slope * r.uniform(0.85, 1.15, len(k))
    t_fast = t60_1 * 0.22 / (1.0 + 0.0011 * (fk - f0))
    t_slow = t60_1 / (1.0 + 0.0006 * (fk - f0))
    nstr = 1 if key < 34 else (2 if key < 46 else 3)
    out = np.zeros((2, n))
    ph_base = dsp.phase_cycles(dsp.cents2ratio(_cents(cents, n)), n) if cents is not None else t
    for i in range(len(k)):
        life = min(n, n_of(t_slow[i] * 1.25) + 1)            # stop once the partial is ~75 dB down
        tt = t[:life]
        env = 0.62 * np.exp(-LN1000 * tt / t_fast[i]) + 0.38 * np.exp(-LN1000 * tt / t_slow[i])
        if nstr > 1:
            beat = r.uniform(0.15, 1.2) * (1.0 + 0.3 * i / len(k))
            env = env * (1.0 + 0.22 * np.cos(TWO_PI * beat * tt + r.uniform(0, TWO_PI)))
        part = amp[i] * env * np.sin(TWO_PI * fk[i] * ph_base[:life] + r.uniform(0, TWO_PI))
        th = (0.25 + 0.5 * i / max(1, len(k) - 1) + r.uniform(-0.12, 0.12)) * np.pi / 2  # partials spread across
        out[0, :life] += part * np.cos(th)
        out[1, :life] += part * np.sin(th)
    out = out / (dsp.peak(out) + 1e-12)
    # hammer knock + soundboard thump
    kk = n_of(0.06)
    knock = dsp.bandpass(r.standard_normal(kk), 120, 1800 + 2000 * hardness, 2) * np.exp(-t[:kk] / 0.008)
    thump = dsp.lowpass(r.standard_normal(kk), 180, 2) * np.exp(-t[:kk] / 0.02)
    out[:, :kk] += (0.05 + 0.08 * hardness) * _nrm(knock) + 0.06 * _nrm(thump)
    att = n_of(0.0015 + 0.003 * (1.0 - hardness))
    out[:, :att] *= np.linspace(0.0, 1.0, att)
    if dur < L:
        out = _damp(out, dur, piano_damp(midi))
    out = dsp.eq_chain(out, [("peak", 110, 2.5, 0.9), ("peak", 420, -1.5, 1.0), ("peak", 2600, 1.5 * hardness, 1.0),
                             ("highshelf", 9000, -4.0, 0.7), ("hp", 30, 0, 0.7)])
    pan = float(np.clip((key - 64.0) / 64.0, -1, 1)) * 0.35
    out = dsp.pan_stereo(out, pan, 1.0)
    return _end_fade(_nrm(out), 0.08 if dur < L else 0.8) * vel


def piano_damp(midi):
    """T60 of a damped piano string (felt damper; low strings ring a little longer)"""
    return 0.18 + 0.25 * (55.0 / hz(midi)) ** 0.3


# ======================================================================================  plucked strings
def _shaped_exc(freq, r, bright=0.8, pos=0.12, p_dark=1.35, scrape=0.12, lp=None):
    """one period of a plucked-string excitation built additively: harmonic k ~ |sin(k pi pos)| / k^p
    (pos = pluck point, p from the pick hardness) + a little scrape noise; periodic low-pass."""
    N = max(2, int(SR / freq))
    kk = np.arange(N) / N
    nh = int(max(1, min(70, 0.45 * SR / freq)))
    hn = np.arange(1, nh + 1)
    p = p_dark - 0.75 * float(np.clip(bright, 0.0, 1.0))
    amp = (np.abs(np.sin(hn * np.pi * pos)) + 0.06) / hn ** p * r.uniform(0.8, 1.2, nh)
    ph = r.uniform(-0.25, 0.25, nh)
    exc = (amp[:, None] * np.sin(TWO_PI * (hn[:, None] * kk[None, :] + ph[:, None]))).sum(axis=0)
    scr = r.uniform(-1, 1, N)
    exc = _nrm(exc) + scrape * (scr - scr.mean())
    if lp:
        exc = dsp.lowpass(np.concatenate([exc, exc]), lp, 2)[N:]
    return exc


PLUCKED = {
    # t60 at A3 and its register scaling, loop brightness, excitation brightness, pluck position, finger/pick
    # click, damping T60 at the gate, settle cents, body EQ
    "harp": dict(t60=5.5, scale=0.5, loop=0.55, exc=0.45, pos=0.3, click=0.05, damp=0.6, settle=4,
                 body=[("peak", 180, 2.0, 1.0), ("peak", 520, 2.5, 1.3), ("peak", 2400, -2.0, 1.0),
                       ("highshelf", 6500, -5.0, 0.7)]),
    "nylon_guitar": dict(t60=3.2, scale=0.45, loop=0.45, exc=0.5, pos=0.16, click=0.12, damp=0.2, settle=6,
                         body=[("peak", 100, 4.0, 1.4), ("peak", 210, 3.0, 1.6), ("peak", 420, -2.0, 1.2),
                               ("peak", 2600, 1.5, 1.0), ("highshelf", 6000, -4.0, 0.7)]),
    "steel_guitar": dict(t60=4.0, scale=0.4, loop=0.72, exc=0.8, pos=0.12, click=0.25, damp=0.18, settle=8,
                         body=[("peak", 105, 3.0, 1.4), ("peak", 220, 2.5, 1.5), ("peak", 3200, 2.5, 1.0),
                               ("highshelf", 9000, -3.0, 0.7)]),
    "ukulele": dict(t60=1.3, scale=0.3, loop=0.6, exc=0.62, pos=0.2, click=0.18, damp=0.12, settle=8,
                    body=[("peak", 330, 4.0, 1.6), ("peak", 640, 2.0, 1.6), ("peak", 1500, 2.0, 1.2),
                          ("hp", 180, 0, 0.7), ("highshelf", 7000, -4.0, 0.7)]),
    "banjo": dict(t60=1.1, scale=0.3, loop=0.8, exc=0.95, pos=0.1, click=0.4, damp=0.1, settle=12,
                  body=[("peak", 720, 7.0, 1.6), ("peak", 2200, 5.0, 1.4), ("peak", 4500, 2.0, 1.2),
                        ("hp", 200, 0, 0.7)]),
    "acoustic_bass": dict(t60=2.4, scale=0.3, loop=0.3, exc=0.25, pos=0.22, click=0.06, damp=0.15, settle=6,
                          body=[("peak", 70, 3.0, 1.2), ("peak", 140, 3.0, 1.3), ("peak", 600, -2.0, 1.0),
                                ("highshelf", 2500, -8.0, 0.7)]),
    "fingered_bass": dict(t60=4.0, scale=0.25, loop=0.45, exc=0.35, pos=0.2, click=0.08, damp=0.12, settle=4,
                          body=[("peak", 80, 2.0, 1.0), ("peak", 800, 2.0, 1.2), ("highshelf", 3500, -8.0, 0.7)]),
    "pizzicato": dict(t60=0.9, scale=0.3, loop=0.5, exc=0.4, pos=0.25, click=0.1, damp=0.18, settle=6,
                      body=[("peak", 280, 3.0, 2.0), ("peak", 460, 2.0, 2.0), ("peak", 2700, 2.0, 1.2),
                            ("highshelf", 6000, -4.0, 0.7)]),
    "guzheng": dict(t60=4.5, scale=0.4, loop=0.7, exc=0.75, pos=0.12, click=0.3, damp=0.35, settle=10,
                    body=[("peak", 160, 3.0, 1.2), ("peak", 380, 2.0, 1.5), ("peak", 900, 1.5, 1.4),
                          ("peak", 3500, 2.0, 1.0), ("hp", 60, 0, 0.7)]),
}


def plucked(kind, midi, dur, vel=0.7, r=None, cents=None, press=None, let_ring=False):
    """Karplus-Strong plucked string with a shaped pick excitation and body EQ.
    press: list of (t_rel, cents, glide_s) press-bends (guzheng / koto style); let_ring: no damper at the gate."""
    r = r if r is not None else dsp.rng("pluck", kind, midi)
    p = PLUCKED[kind]
    f0 = hz(midi)
    vel = float(np.clip(vel, 0.02, 1.2))
    t60 = float(np.clip(p["t60"] * (220.0 / f0) ** p["scale"], 0.25, 9.0))
    ring = min(t60 * 1.1, 10.0)
    L = ring if let_ring else min(max(dur, 0.05) + max(p["damp"] * 2.2, 0.12), ring + 0.1)
    L = max(L, 0.12)
    n = n_of(L)
    t = t_axis(n)
    c = p["settle"] * (0.5 + vel) * np.exp(-t / 0.06) + _cents(cents, n)
    if press:
        for tp, pc, gl in press:
            c = c + pc * dsp.smoothstep((t - tp) / max(gl, 1e-3))
    exc = _shaped_exc(f0, r, bright=p["exc"] * (0.7 + 0.4 * vel), pos=p["pos"] * r.uniform(0.9, 1.1),
                      lp=1500 + 9000 * vel * p["exc"])
    y = dsp.karplus_strong(f0, L, r, t60=t60, brightness=p["loop"] + 0.08 * vel, pick_pos=0.0, exc=exc, cents=c)
    y = _nrm(y)
    if not let_ring and dur < L:
        y = _damp(y, dur, p["damp"])
    k = n_of(0.012)
    click = dsp.highpass(r.standard_normal(k), 2500, 2) * np.exp(-t[:k] / 0.0012)
    y[:k] += p["click"] * vel * _nrm(click)
    y = dsp.eq_chain(y, p["body"])
    y = dsp.dc_block(y, 25.0)
    return _end_fade(_nrm(y), 0.03) * vel


def pizz_section(midi, dur, vel=0.7, r=None, cents=None, players=3):
    """pizzicato string section (stereo): a few slightly detuned, slightly late players"""
    r = r if r is not None else dsp.rng("pizz", midi)
    parts = []
    for i in range(players):
        rr = dsp.rng("pizz", midi, i, r.integers(1 << 30))
        y = plucked("pizzicato", midi + r.normal(0, 0.05), dur, vel * r.uniform(0.85, 1.0), rr, cents=cents)
        s = n_of(r.uniform(0, 0.012) if i else 0.0)
        parts.append((np.concatenate([np.zeros(s), y]), r.uniform(-0.6, 0.6)))
    n = max(len(y) for y, _ in parts)
    out = np.zeros((2, n))
    for y, p in parts:
        out[:, :len(y)] += dsp.pan_mono(y, p)
    return _nrm(out) * vel


# --------------------------------------------------------------------------- pipa / guqin (Night Revels)
_PIPA_BODY = [("peak", 250, 3.0, 1.4), ("peak", 520, 1.5, 1.6), ("peak", 800, -2.0, 1.0),
              ("peak", 1300, 2.0, 1.3), ("peak", 3300, 3.0, 1.0), ("highshelf", 9000, -3.0, 0.7), ("hp", 75, 0.0, 0.7)]


def _pipa_string(freq, hold, vel, r, bright=0.75, tail=0.45, cents=None, t60=None, click=1.0, damp_t60=0.22):
    t60 = t60 or float(np.clip(2.0 * (220.0 / freq) ** 0.45, 0.8, 2.8))
    L = min(hold + tail, t60 * 1.1 + 0.05)
    n = n_of(L)
    t = t_axis(n)
    c = (5.0 + 12.0 * vel) * np.exp(-t / 0.035) + _cents(cents, n)
    exc = _shaped_exc(freq, r, bright=bright * (0.75 + 0.35 * vel), pos=0.1 + 0.04 * r.uniform(), lp=2500 + 9000 * vel)
    y = dsp.karplus_strong(freq, L, r, t60=t60, brightness=0.55 + 0.32 * bright, pick_pos=0.0, exc=exc, cents=c)
    y = _nrm(y)
    if hold < L - 0.01:
        y = _damp(y, hold, damp_t60)
    k = n_of(0.02)
    tk = t[:k]
    cl = dsp.highpass(r.standard_normal(k), 2800, 2) * np.exp(-tk / 0.0009)
    sn = dsp.bandpass(r.standard_normal(k), 1500, 6500, 2) * np.exp(-tk / 0.0035)
    y[:k] += click * vel * (0.32 * _nrm(cl) + 0.22 * _nrm(sn))
    y = dsp.eq_chain(y, _PIPA_BODY)
    return dsp.fade(y, 0.0, min(0.04, L * 0.2))


def pipa(midi, dur, vel=0.7, r=None, cents=None, tremolo=False):
    """pipa: bright plectrum-plucked lute; yin vibrato on long notes; tremolo = lunzhi (~13 re-plucks per second)"""
    r = r if r is not None else dsp.rng("pipa", midi)
    f0 = hz(midi)
    if tremolo:
        return pipa_tremolo(midi, dur, vel, r, cents=cents)
    hold = min(max(dur, 0.12) * 1.1 + 0.05, 30.0)
    n = n_of(min(hold + 0.45, 4.0))
    c = _cents(cents, n)
    if dur >= 0.5:
        c += _vib(n, r, 12.0 + 6.0 * r.uniform(), 5.4, delay=0.18, ramp=0.3)
    y = _pipa_string(f0, hold, vel, r, cents=c)
    return _nrm(y) * vel


def pipa_tremolo(midi, dur, vel=0.7, r=None, cents=None):
    """lunzhi: the fingers re-pluck the string ~13 times a second; each pluck is damped when the next lands"""
    r = r if r is not None else dsp.rng("pipa_trem", midi)
    f0 = hz(midi)
    rate = r.uniform(12.3, 13.8)
    total = dur + 0.5
    n = n_of(total)
    variants = [_nrm(_pipa_string(f0, total - 0.05, 0.7, r, bright=0.75 * (0.85 + 0.08 * v), tail=0.05, click=0.35,
                                  cents=cents)) for v in range(3)]
    times, tt = [0.0], 0.0
    while True:
        tt += 1.0 / (rate * (0.92 + 0.08 * min(1.0, tt / 0.25))) + r.normal(0.0, 0.0022)
        if tt > dur - 0.03:
            break
        times.append(tt)
    y = np.zeros(n)
    t = t_axis(n)
    for i, ts in enumerate(times):
        s = n_of(ts)
        clip = variants[i % 3][: n - s].copy()
        tc = t[: len(clip)]
        if i + 1 < len(times):
            d = times[i + 1] - ts + 0.004
            clip *= np.where(tc < d, 1.0, np.exp(-(tc - d) / 0.012))
        else:
            d = max(0.25, dur - ts + 0.12)
            clip *= np.where(tc < d, 1.0, np.exp(-(tc - d) / 0.09))
        u = ts / max(dur, 1e-3)
        g = (1.15 if i == 0 else (0.78 + 0.22 * np.sin(np.pi * min(u, 1.0)))) * r.uniform(0.9, 1.06)
        y[s:s + len(clip)] += g * clip
    return _nrm(dsp.fade(y, 0.0, 0.04)) * vel


_QIN_BODY = [("peak", 110, 3.0, 1.0), ("peak", 330, 2.0, 1.3), ("peak", 1900, -2.0, 0.8),
             ("highshelf", 4500, -5.0, 0.7), ("hp", 45, 0.0, 0.7)]


def guqin(midi, dur, vel=0.5, r=None, cents=None, slide=False, harmonic=False):
    """seven-string silk zither: soft flesh pluck, long decay, slides with silk friction, harmonics (fan yin)"""
    r = r if r is not None else dsp.rng("guqin", midi)
    f0 = hz(midi)
    if harmonic:
        L = min(dur + 1.8, 5.0)
        n = n_of(L)
        y = dsp.modal([f0, 2.0 * f0 * 1.0015, 3.0 * f0 * 1.004], [1.0, 0.22, 0.07], [4.5, 2.0, 1.0], n, r=r, attack=0.003)
        return _nrm(dsp.fade(y, 0.0, 0.8)) * vel * 0.75
    t60 = float(np.clip(7.0 * (110.0 / f0) ** 0.3, 4.0, 9.0))
    L = min(dur + 2.2, t60 + 0.5)
    n = n_of(L)
    t = t_axis(n)
    c = 4.0 * np.exp(-t / 0.05) + _cents(cents, n)
    slide_env = None
    if slide:
        c += -300.0 * (1.0 - dsp.smoothstep((t - 0.10) / 0.55))
        slide_env = np.gradient(dsp.smoothstep((t - 0.10) / 0.55)) * SR
    if dur >= 2.0:
        c += 9.0 * dsp.smoothstep((t - 0.9) / 0.5) * np.exp(-np.maximum(t - 1.4, 0) / 2.0) * \
            np.sin(TWO_PI * dsp.phase_cycles(3.6, n, r.uniform()))
    exc = _shaped_exc(f0, r, bright=0.25, pos=0.09, p_dark=1.7, scrape=0.05, lp=900 + 1800 * vel)
    y = _nrm(dsp.karplus_strong(f0, L, r, t60=t60, brightness=0.38, pick_pos=0.0, exc=exc, cents=c))
    k = n_of(0.06)
    y[:k] += 0.18 * _nrm(dsp.lowpass(r.standard_normal(k), 300, 2) * np.exp(-t[:k] / 0.012))
    if slide_env is not None:
        fr = dsp.bandpass(r.standard_normal(n), 700, 3200, 2) * np.clip(slide_env / (slide_env.max() + 1e-9), 0, 1)
        y += 0.06 * _nrm(dsp.onepole(fr, 5000))
    y = dsp.eq_chain(y, _QIN_BODY)
    return _nrm(dsp.fade(y, 0.0, 1.0)) * vel


def guzheng(midi, dur, vel=0.7, r=None, cents=None, press=None, vibrato=True):
    """21-string zither: bright fingerpick, long ring, left-hand press-bends (an) and a singing vibrato (rou)"""
    r = r if r is not None else dsp.rng("guzheng", midi)
    n_guess = n_of(min(dur, 12.0) + 4.0)
    c = _cents(cents, n_guess)
    if vibrato and dur > 0.45:
        c = c + _vib(n_guess, r, 14.0, 5.0, delay=0.25, ramp=0.4)
    return plucked("guzheng", midi, dur, vel, r, cents=c, press=press, let_ring=True)


def gliss(engine, midi, dur, vel, r, scale_offsets=(0, 2, 4, 7, 9), span=12, up=True, sweep=0.35, **kw):
    """harp / guzheng style glissando into (up=True) or away from the note: string after string over `sweep` s.
    Returns mono/stereo audio whose target note starts at sample n_of(sweep) (up) or 0 (down)."""
    notes = []
    for octave in range(-2, 2):
        for s in scale_offsets:
            m = midi + 12 * octave + s
            if (midi - span <= m < midi) if up else (midi - span < m <= midi):
                notes.append(m)
    notes = sorted(set(notes)) if up else sorted(set(notes), reverse=True)
    if not up:
        notes = notes[1:] if notes and notes[0] == midi else notes
    seq = notes + [midi] if up else [midi] + notes
    step = sweep / max(1, len(seq) - 1)
    clips = []
    for i, m in enumerate(seq):
        last = (i == len(seq) - 1) if up else (i == 0)
        v = vel * (0.45 + 0.55 * (i + 1) / len(seq)) if up else vel * (1.0 - 0.6 * i / len(seq))
        d = dur if last else max(0.25, sweep * 1.5)
        clips.append((n_of(i * step), engine(m, d, v if not last else vel, dsp.rng("gliss", m, i, r.integers(1 << 30)), **kw)))
    n = max(s + c.shape[-1] for s, c in clips)
    stereo = any(c.ndim == 2 for _, c in clips)
    out = np.zeros((2, n)) if stereo else np.zeros(n)
    for s, c in clips:
        if stereo:
            out[:, s:s + c.shape[-1]] += dsp.as_stereo(c)
        else:
            out[s:s + len(c)] += c
    return out


# ======================================================================================  bowed strings
_BODY_CACHE = {}


def _string_body(kind, variant):
    """fixed pseudo-random body-resonance filter of one string desk: known low modes, the bridge hill and narrow
    random peaks / dips -- vibrato sweeps the harmonics across them, the shimmer of real strings."""
    key = (kind, variant)
    if key in _BODY_CACHE:
        return _BODY_CACHE[key]
    r = dsp.rng("string_body", kind, variant)
    if kind == "low":
        fixed = [(98.0, 4.0, 2.5), (196.0, 3.0, 3.0), (410.0, 2.5, 3.0), (1900.0, 3.0, 1.1)]
        lo, hi = 140.0, 4200.0
    elif kind == "erhu":
        fixed = [(420.0, 5.0, 2.0), (980.0, 6.0, 1.6), (2300.0, 5.0, 1.4), (3600.0, 3.0, 1.5)]
        lo, hi = 500.0, 6000.0
    else:
        fixed = [(280.0, 4.0, 3.0), (460.0, 3.0, 4.0), (560.0, 2.0, 4.0), (2700.0, 4.0, 1.2)]
        lo, hi = 300.0, 6000.0
    bands = [("peak", fc * r.uniform(0.95, 1.05), g, q) for fc, g, q in fixed]
    for f in np.exp(r.uniform(np.log(lo), np.log(hi), 9)):
        bands.append(("peak", float(f), float(r.uniform(-8.0, 6.0)), float(r.uniform(5.0, 14.0))))
    sos = np.vstack([dsp.biquad_sos(k, fc, q, g) for (k, fc, g, q) in bands])
    _BODY_CACHE[key] = sos
    return sos


def bowed(midi, dur, vel=0.6, r=None, cents=None, voices=1, detune=7.0, vib_depth=14.0, vib_rate=5.6,
          attack=None, release=0.35, mode="sustain", body="high", width=0.7, trem_rate=12.5, portamento=None):
    """bowed string(s), stereo. voices=1 solo, 4-8 section. mode: sustain | swell | tremolo | spiccato | sfz.
    portamento: optional (from_midi, glide_s) slide into the note."""
    r = r if r is not None else dsp.rng("bowed", midi, voices)
    f0 = hz(midi)
    vel = float(np.clip(vel, 0.02, 1.2))
    if mode == "spiccato":
        attack, release = 0.006, 0.08
    attack = attack if attack is not None else (0.09 if voices == 1 else 0.2) * (1.3 - 0.6 * vel)
    n = n_of(dur + release + 0.05)
    t = t_axis(n)
    base = _cents(cents, n)
    if portamento:
        src, gl = portamento
        base = base + 100.0 * (src - midi) * (1.0 - dsp.smoothstep(t / max(gl, 1e-3)))
    desks = [np.zeros((2, n)), np.zeros((2, n))]
    m, tc = _ctrl_axis(n)
    env_sum = np.zeros(m)
    K = int(min(48, NYQ_SAFE * 0.9 / f0))
    end = n / SR + 1.0
    for v in range(voices):
        det = r.normal(0.0, detune * 0.5) if voices > 1 else 0.0
        vd = vib_depth * (r.uniform(0.7, 1.25) if voices > 1 else 1.0)
        vrate = vib_rate * r.uniform(0.92, 1.08) * (1.0 + 0.05 * _cnoise(m, r, 0.7))
        vib = vd * dsp.smoothstep((tc - r.uniform(0.12, 0.35)) / 0.35) * np.sin(TWO_PI * (np.cumsum(vrate) / CR + r.uniform()))
        cc = det + vib + 3.0 * _cnoise(m, r, 0.6) + 1.2 * _cnoise(m, r, 9.0)
        f = f0 * dsp.cents2ratio(_up(cc, n) + base)
        osc = dsp.osc_saw(f, n, r.uniform()) if K > 6 else dsp.additive(f, n, [(k, 1.0 / k) for k in range(1, K + 1)])
        a_j = attack * r.uniform(0.8, 1.3) + (r.uniform(0, 0.025) if voices > 1 else 0.0)
        if mode == "spiccato":
            e = _env_ctrl([(0, 0), (a_j, 1.0), (a_j + 0.05, 0.5), (max(dur, a_j + 0.06), 0.3),
                           (max(dur, a_j + 0.06) + release, 0), (end, 0)], tc)
        elif mode == "sfz":
            e = _env_ctrl([(0, 0), (0.012, 1.0), (0.2, 0.32), (max(dur * 0.6, 0.21), 0.45), (max(dur, 0.22), 0.6),
                           (max(dur, 0.22) + release, 0), (end, 0)], tc)
        elif mode == "swell":
            e = _env_ctrl([(0, 0.0), (max(dur * 0.8, 0.05), 1.0), (max(dur, 0.06), 1.0),
                           (max(dur, 0.06) + release, 0), (end, 0)], tc) ** 1.5
        else:
            e = _env_ctrl(_sustain_points(a_j, dur, release, 1.0, 0.92, 0.25, end), tc)
        if mode == "tremolo":
            phs = np.cumsum(trem_rate * r.uniform(0.9, 1.1) * (1 + 0.05 * _cnoise(m, r, 1.0))) / CR + r.uniform()
            e = e * (0.45 + 0.55 * np.abs(np.sin(np.pi * phs)) ** 0.7)
        e = e * np.maximum(0.0, 1.0 + 0.045 * _cnoise(m, r, 2.0) + 0.03 * _cnoise(m, r, 16.0))
        desk = v % 2
        p = (r.uniform(0.1, width) * (-1.0 if desk == 0 else 1.0)) if voices > 1 else 0.0
        gl, gr = dsp.pan_gains(p)
        sig = osc * _up(e, n)
        desks[desk][0] += sig * gl
        desks[desk][1] += sig * gr
        env_sum += e
    env_sum = _up(env_sum, n)
    kind = body if body != "high" else ("low" if f0 < 170.0 else "high")
    out = np.zeros((2, n))
    for d in range(2 if voices > 1 else 1):
        out += signal.sosfilt(_string_body(kind, d), desks[d], axis=-1)
    fc = float(np.clip(1300 + 3000 * vel + 2.0 * f0, 900, 8000)) * (1.25 if body == "erhu" else 1.0)
    en = env_sum / (env_sum.max() + 1e-12)
    out = dsp.lp_sweep(out, fc * (0.4 + 0.6 * en ** 0.8), n_bank=10, fmin=300.0, fmax=16000.0)
    out = dsp.eq_chain(out, [("peak", 1300, -1.5, 1.0), ("peak", 2900, 0.6 * vel, 1.2), ("highshelf", 7000, -6.0, 0.7),
                             ("hp", 35 if f0 < 100 else 60, 0, 0.7)])
    bn = dsp.bandpass(r.standard_normal((2, n)), 1500, 7000, 2)
    benv = dsp.env_points([(0, 0), (attack * 0.5 + 0.01, 1.0), (max(dur, 0.02), 0.5), (max(dur, 0.02) + release * 0.5, 0),
                           (n / SR + 1, 0)], n, "cos")
    if mode == "tremolo":
        benv = benv * (0.3 + 0.7 * np.abs(np.sin(np.pi * dsp.phase_cycles(trem_rate, n, r.uniform()))) ** 4)
    bl = (0.015 + (0.05 if mode in ("tremolo", "spiccato", "sfz") else 0.0) + (0.02 if voices == 1 else 0.0)) * vel
    out = _nrm(out)
    out += bl * 4.0 * bn * benv / (dsp.peak(bn) + 1e-9)
    if voices == 1:
        out = dsp.pan_stereo(out, 0.0, 0.0)
    return _end_fade(_nrm(out), 0.03) * vel


def erhu(midi, dur, vel=0.65, r=None, cents=None, portamento=None, vib_depth=26.0):
    """erhu: two-string fiddle with a python-skin resonator -- nasal, singing; wide expressive vibrato that grows
    through the note, a slide into the note (portamento) and a small scoop on attacks"""
    r = r if r is not None else dsp.rng("erhu", midi)
    n = n_of(dur + 0.4)
    t = t_axis(n)
    c = _cents(cents, n) - 35.0 * np.exp(-t / 0.05)
    c = c + _vib(n, r, vib_depth * (0.6 + 0.6 * dsp.smoothstep(t / max(dur, 0.3))), 6.0, delay=0.15, ramp=0.5)
    y = bowed(midi, dur, vel, r, cents=c, voices=1, vib_depth=0.0, body="erhu", attack=0.06, release=0.25,
              portamento=portamento)
    y = dsp.eq_chain(y, [("hp", 260, 0, 0.7), ("peak", 1050, 4.0, 1.2), ("peak", 2400, 3.0, 1.4),
                         ("peak", 600, -3.0, 1.0), ("highshelf", 7500, -6.0, 0.7)])
    return _nrm(y) * vel


# ======================================================================================  winds
WINDS = {
    # harmonic spectrum: slope (dark..bright with velocity), odd/even balance, formants (fc, gain dB, q);
    # breath noise, chiff, vibrato (depth cents, rate, delay), attack / release (s), scoop (cents)
    "flute": dict(slope=(2.6, 1.6), even=0.75, formants=[], breath=0.07, chiff=0.12, vib=(14, 5.2, 0.3), attack=0.05,
                  release=0.09, hp=200),
    "piccolo": dict(slope=(2.4, 1.6), even=0.8, formants=[], breath=0.09, chiff=0.12, vib=(12, 5.6, 0.25), attack=0.035,
                    release=0.07, hp=400),
    "recorder": dict(slope=(2.9, 2.2), even=0.5, formants=[], breath=0.05, chiff=0.25, vib=(3, 5.0, 0.4), attack=0.025,
                     release=0.06, hp=250),
    "whistle": dict(slope=(4.5, 3.5), even=1.0, formants=[], breath=0.05, chiff=0.03, vib=(22, 5.8, 0.15), attack=0.04,
                    release=0.07, hp=400, scoop=-40),
    "ocarina": dict(slope=(4.0, 3.0), even=0.8, formants=[], breath=0.04, chiff=0.06, vib=(8, 4.8, 0.35), attack=0.05,
                    release=0.08, hp=200),
    "clarinet": dict(slope=(2.0, 1.25), even=0.12, formants=[(1500, 3.0, 1.2), (3200, -4.0, 1.0)], breath=0.03,
                     chiff=0.05, vib=(2, 5.0, 0.5), attack=0.035, release=0.08, hp=120),
    "oboe": dict(slope=(1.2, 0.8), even=0.9, formants=[(1100, 9.0, 1.6), (2900, 6.0, 1.8), (500, -4.0, 1.0)],
                 breath=0.02, chiff=0.04, vib=(14, 5.6, 0.3), attack=0.03, release=0.08, hp=220),
    "bassoon": dict(slope=(1.4, 0.9), even=0.85, formants=[(480, 8.0, 1.4), (1150, 5.0, 1.6), (2900, -3.0, 1.0)],
                    breath=0.02, chiff=0.04, vib=(9, 5.2, 0.35), attack=0.04, release=0.09, hp=45),
    "suona": dict(slope=(0.95, 0.55), even=0.95, formants=[(1300, 8.0, 1.4), (2700, 7.0, 1.6), (4200, 4.0, 1.6)],
                  breath=0.03, chiff=0.08, vib=(30, 6.2, 0.18), attack=0.025, release=0.07, hp=300, scoop=-110,
                  buzz=0.18),
    "harmonica": dict(slope=(1.3, 0.85), even=0.9, formants=[(1100, 5.0, 1.3), (2600, 4.0, 1.5)], breath=0.08,
                      chiff=0.05, vib=(6, 6.0, 0.3), attack=0.03, release=0.06, hp=200, scoop=-30, tremolo=(5.5, 0.18)),
    "shakuhachi": dict(slope=(3.2, 2.2), even=0.55, formants=[(900, 3.0, 1.2)], breath=0.18, chiff=0.2,
                       vib=(16, 4.6, 0.4), attack=0.08, release=0.12, hp=180, scoop=-50),
}


def wind(kind, midi, dur, vel=0.6, r=None, cents=None, vibrato=None):
    """blown pipe / reed: additive harmonics with jitter, formant EQ, pitched + broadband breath, chiff, vibrato"""
    r = r if r is not None else dsp.rng("wind", kind, midi)
    p = WINDS[kind]
    f0 = hz(midi)
    vel = float(np.clip(vel, 0.02, 1.2))
    rel = p["release"]
    n = n_of(dur + rel + 0.05)
    t = t_axis(n)
    c = _cents(cents, n) + 2.5 * dsp.ctrl_noise(n, r, 1.0)
    if p.get("scoop"):
        c += p["scoop"] * np.exp(-t / 0.045)
    vd, vr, vdl = vibrato if vibrato is not None else p["vib"]
    if dur > 0.25:
        c += _vib(n, r, vd, vr, delay=vdl, ramp=0.35)
    f = f0 * dsp.cents2ratio(c)
    att = p["attack"] * (1.3 - 0.5 * vel)
    env = _sustain_env(n, att, dur, rel, peak=1.0, sustain=0.88, decay=0.12)
    env *= 1.0 + 0.04 * dsp.ctrl_noise(n, r, 3.0)
    if p.get("tremolo"):
        tr, td = p["tremolo"]
        env *= 1.0 - td * (0.5 + 0.5 * np.sin(TWO_PI * dsp.phase_cycles(tr, n, r.uniform())))
    ph = dsp.phase_cycles(f, n)
    s0, s1 = p["slope"]
    slope = s0 + (s1 - s0) * vel
    K = int(max(2, min(24, NYQ_SAFE * 0.85 / f0)))
    tone = np.zeros(n)
    for k in range(1, K + 1):
        ak = k ** (-slope) * (p["even"] if k % 2 == 0 and k > 1 else 1.0) * r.uniform(0.9, 1.1)
        if f0 * k > 9000:
            ak *= np.exp(-(f0 * k - 9000) / 3000)
        jit = 1.0 + 0.06 * dsp.ctrl_noise(n, r, 20.0 + 3 * k, rate=400.0)
        tone += ak * jit * np.sin(TWO_PI * (k * ph + r.uniform()))
    if p["formants"]:
        tone = dsp.eq_chain(tone, [("peak", fc, g, q) for fc, g, q in p["formants"]])
    tone = _nrm(tone)
    if p.get("buzz"):
        bz = dsp.bandpass(np.tanh(3.0 * tone) - 0.7 * tone, 1800, 7000, 2)
        tone = tone + p["buzz"] * _nrm(bz)
    gate = (0.5 + 0.5 * np.cos(TWO_PI * ph)) ** 3
    pitched = dsp.bandpass(r.standard_normal(n) * gate, max(300, f0), min(6000, f0 * 8), 2)
    air = dsp.bandpass(r.standard_normal(n), 1500, 8000, 2)
    nl = p["breath"] * (1.2 - 0.5 * vel)
    y = env * (tone + nl * (0.8 * _nrm(pitched) + 0.5 * _nrm(air)))
    kc = n_of(0.04)
    ch = dsp.bandpass(r.standard_normal(kc), 1000, 6000, 2) * np.exp(-t[:kc] / 0.009)
    y[:kc] += p["chiff"] * (0.5 + vel) * _nrm(ch)
    y = dsp.highpass(y, p["hp"], 2)
    return _end_fade(_nrm(dsp.fade(y, 0.002, 0.0)), 0.015) * vel


def dizi(midi, dur, vel=0.6, r=None, cents=None, grace=None, membrane=1.0, vib_depth=22.0):
    """di bamboo flute with the dimo membrane buzz, breath, chiff, vibrato and grace notes [(cents, dur_s), ...]"""
    r = r if r is not None else dsp.rng("dizi", midi)
    freq = hz(midi)
    rel = 0.1
    n = n_of(dur + rel + 0.04)
    t = t_axis(n)
    c = -18.0 * np.exp(-t / 0.025) + _cents(cents, n)
    if grace:
        pos = 0.0
        for gc, gd in grace:
            a, b = n_of(pos), n_of(pos + gd)
            c[a:b] += gc
            pos += gd
        b = n_of(pos)
        m = n_of(0.006)
        c[b:b + m] += grace[-1][0] * np.linspace(1, 0, len(c[b:b + m]))
    vr = 5.6 * (1.0 + 0.04 * dsp.ctrl_noise(n, r, 0.8))
    if dur > 0.3:
        c += vib_depth * r.uniform(0.8, 1.2) * dsp.smoothstep((t - 0.18) / 0.3) * \
            np.sin(TWO_PI * dsp.phase_cycles(vr, n, r.uniform()))
    c += 3.0 * dsp.ctrl_noise(n, r, 1.0)
    f = freq * dsp.cents2ratio(c)
    att = 0.02 + 0.02 * (1.0 - vel)
    env = dsp.env_points([(0, 0), (att, 1.0), (att + 0.06, 0.86), (max(dur, att + 0.07), 0.9),
                          (max(dur, att + 0.07) + rel, 0.0), (n / SR + 1, 0.0)], n, "cos")
    env *= 1.0 + 0.05 * dsp.ctrl_noise(n, r, 3.0)
    ph = dsp.phase_cycles(f, n)
    K = int(max(3, min(10, 9500.0 / freq)))
    slope = 1.9 - 0.5 * vel
    tone = np.zeros(n)
    for k in range(1, K + 1):
        ak = k ** (-slope) * (0.6 if k % 2 == 0 else 1.0) * r.uniform(0.85, 1.15)
        jit = 1.0 + 0.08 * dsp.ctrl_noise(n, r, 25.0 + 4 * k)
        tone += ak * jit * np.sin(TWO_PI * (k * ph + r.uniform()))
    tone = _nrm(tone)
    buzz = np.tanh(3.5 * tone) - 0.8 * tone
    buzz = dsp.bandpass(buzz, 2300, 8500, 2) * (1.0 + 0.3 * dsp.ctrl_noise(n, r, 60.0))
    gate = (0.5 + 0.5 * np.cos(TWO_PI * ph)) ** 4
    sync = dsp.bandpass(r.standard_normal(n) * gate, 2800, 9000, 2)
    air = dsp.bandpass(r.standard_normal(n), 1200, 7500, 2)
    nl = 0.05 + 0.06 * (1.0 - vel)
    y = env * (tone + membrane * (0.22 * _nrm(buzz) + 0.07 * _nrm(sync)) + nl * _nrm(air) * 1.3)
    kc = n_of(0.035)
    y[:kc] += (0.10 + 0.1 * vel) * _nrm(dsp.bandpass(r.standard_normal(kc), 1000, 5000, 2) * np.exp(-t[:kc] / 0.008))
    y = dsp.highpass(y, 250, 2)
    y = dsp.peq(y, 3200, 2.5, 1.2)
    return _nrm(dsp.fade(y, 0.002, 0.015)) * vel


def sheng(midi, dur, vel=0.4, r=None, cents=None, chord=(0,), attack=0.3, release=0.45, width=0.6):
    """sheng: pairs of slightly beating free-reed pipes; soft swell; stereo. chord = semitone offsets above midi."""
    r = r if r is not None else dsp.rng("sheng", midi, tuple(chord))
    n = n_of(dur + release + 0.05)
    out = np.zeros((2, n))
    base = _cents(cents, n)
    for i, off in enumerate(chord):
        f0 = hz(midi + off)
        for p in range(2):
            c = base + (-4.0 if p == 0 else 4.0) + r.normal(0, 1.5) + 3.0 * dsp.ctrl_noise(n, r, 0.7)
            ph = dsp.phase_cycles(f0 * dsp.cents2ratio(c), n, r.uniform())
            K = int(max(2, min(12, 6500.0 / f0)))
            v = np.zeros(n)
            for k in range(1, K + 1):
                v += (k ** -1.2) * (1.0 if k % 2 else 0.7) * np.sin(TWO_PI * k * ph)
            e = dsp.env_points([(0, 0), (attack * r.uniform(0.85, 1.2), 1.0), (max(dur, attack + 0.01), 0.95),
                                (max(dur, attack + 0.01) + release, 0), (n / SR + 1, 0)], n, "cos")
            e *= 1.0 + 0.04 * dsp.ctrl_noise(n, r, 2.5)
            gl, gr = dsp.pan_gains((-1 if (i + p) % 2 else 1) * width * r.uniform(0.3, 1.0))
            out[0] += v * e * gl
            out[1] += v * e * gr
    out = dsp.lowpass(out, 3800, 2)
    out = dsp.eq_chain(out, [("peak", 1150, 2.5, 1.0), ("peak", 2400, 1.5, 1.2), ("hp", 120, 0.0, 0.7)])
    return _nrm(out) * vel


def accordion(midi, dur, vel=0.6, r=None, cents=None, musette=10.0):
    """accordion: two reed banks tuned apart (musette beating), reedy pulse wave, bellows swell, box resonance"""
    r = r if r is not None else dsp.rng("accordion", midi)
    f0 = hz(midi)
    n = n_of(dur + 0.12)
    base = _cents(cents, n)
    out = np.zeros((2, n))
    for i, det in enumerate((-musette * 0.5, musette * 0.5, -1200.0 + 2.0)):
        c = base + det + 1.5 * dsp.ctrl_noise(n, r, 0.8)
        f = f0 * dsp.cents2ratio(c)
        src = 0.6 * dsp.osc_square(f, n, r.uniform(), pw=0.3) + 0.5 * dsp.osc_saw(f, n, r.uniform())
        g = 0.55 if i == 2 else 1.0
        out += dsp.pan_mono(src * g, (-0.35, 0.35, 0.0)[i])
    out = dsp.lowpass(out, min(6500, 1800 + 4000 * vel), 2)
    out = dsp.eq_chain(out, [("peak", 900, 4.0, 1.2), ("peak", 2200, 2.5, 1.5), ("hp", 100, 0, 0.7)])
    env = _sustain_env(n, 0.04, dur, 0.08, peak=1.0, sustain=0.92, decay=0.2)
    env *= 1.0 + 0.05 * dsp.ctrl_noise(n, r, 2.0)
    return _end_fade(_nrm(out * env), 0.015) * vel


# ======================================================================================  brass
BRASS = {
    # brightness: cutoff at pp / ff (Hz) and its tracking of the note, formants, attack, scoop, vibrato depth
    "trumpet": dict(cut=(1400, 7000), track=1.2, formants=[(1200, 4.0, 1.1), (2600, 3.0, 1.4)], attack=0.03,
                    scoop=-35, vib=(9, 5.4, 0.35), release=0.09, hp=150),
    "trombone": dict(cut=(700, 3800), track=1.4, formants=[(580, 4.0, 1.1), (1250, 3.0, 1.4)], attack=0.04,
                     scoop=-40, vib=(6, 5.0, 0.4), release=0.12, hp=60),
    "french_horn": dict(cut=(450, 2400), track=1.5, formants=[(420, 4.0, 1.0), (850, 2.0, 1.4)], attack=0.07,
                        scoop=-25, vib=(4, 5.0, 0.45), release=0.18, hp=50),
    "tuba": dict(cut=(280, 1300), track=1.7, formants=[(230, 3.0, 1.0), (500, 2.0, 1.4)], attack=0.06, scoop=-30,
                 vib=(3, 4.6, 0.5), release=0.14, hp=28),
    "muted_trumpet": dict(cut=(1800, 5000), track=1.1, formants=[(1700, 9.0, 2.5), (3600, 5.0, 2.0)], attack=0.025,
                          scoop=-20, vib=(6, 5.6, 0.3), release=0.07, hp=500),
}


def brass(kind, midi, dur, vel=0.7, r=None, cents=None, voices=1, mode="sustain"):
    """lip-reed brass: band-limited saw through a low-pass whose cutoff follows the amplitude (the brass 'blat'),
    a short lip scoop into the note, formant EQ, delayed vibrato. voices > 1 = section (stereo spread)."""
    r = r if r is not None else dsp.rng("brass", kind, midi, voices)
    p = BRASS[kind]
    f0 = hz(midi)
    vel = float(np.clip(vel, 0.02, 1.2))
    rel = p["release"]
    n = n_of(dur + rel + 0.05)
    t = t_axis(n)
    att = p["attack"] * (1.4 - 0.6 * vel)
    if mode == "swell":
        env = dsp.env_points([(0, 0.05), (max(dur * 0.85, 0.06), 1.0), (max(dur, 0.07), 1.0),
                              (max(dur, 0.07) + rel, 0.0), (n / SR + 1, 0)], n, "cos") ** 1.4
    elif mode == "sfz":
        env = dsp.env_points([(0, 0), (att * 0.6, 1.0), (att + 0.15, 0.35), (max(dur, att + 0.16), 0.55),
                              (max(dur, att + 0.16) + rel, 0.0), (n / SR + 1, 0)], n, "cos")
    else:
        env = _sustain_env(n, att, dur, rel, peak=1.0, sustain=0.82, decay=0.18)
    out = np.zeros((2, n))
    base = _cents(cents, n)
    for v in range(voices):
        c = base + p["scoop"] * (1.0 - vel * 0.4) * np.exp(-t / 0.035) + 2.0 * dsp.ctrl_noise(n, r, 1.2)
        if voices > 1:
            c = c + r.normal(0, 5.0)
        if dur > 0.35:
            vd, vr, vdl = p["vib"]
            c = c + _vib(n, r, vd, vr, delay=vdl, ramp=0.4)
        f = f0 * dsp.cents2ratio(c)
        src = dsp.osc_saw(f, n, r.uniform())
        e_v = env if voices == 1 else np.concatenate([np.zeros(n_of(r.uniform(0, 0.018))), env])[:n]
        out += dsp.pan_mono(src * e_v, 0.0 if voices == 1 else r.uniform(-0.55, 0.55))
    lo, hi = p["cut"]
    cut = (lo + (hi - lo) * vel ** 1.3) * (f0 / 300.0) ** (0.35 * (p["track"] - 1.0))
    fc = np.clip(f0 * 1.5 + cut * np.maximum(env, 0.0) ** 1.6, 120.0, NYQ_SAFE * 0.9)
    out = dsp.lp_varying(out, fc, 0.9)
    out = dsp.eq_chain(out, [("peak", a, g, q) for a, g, q in p["formants"]] + [("hp", p["hp"], 0, 0.7)])
    k = n_of(0.05)
    buzz = dsp.bandpass(r.standard_normal(k), 400, 3000, 2) * np.exp(-t[:k] / 0.012)
    out[:, :k] += 0.06 * vel * _nrm(buzz)
    return _end_fade(_nrm(out), 0.02) * vel


# ======================================================================================  voices / pads
_FORMANTS = {
    ("bass", "a"): ([600, 1040, 2250, 2450, 2750], [0, -7, -9, -9, -20], [60, 70, 110, 120, 130]),
    ("tenor", "a"): ([650, 1080, 2650, 2900, 3250], [0, -6, -7, -8, -22], [80, 90, 120, 130, 140]),
    ("alto", "a"): ([800, 1150, 2800, 3500, 4950], [0, -4, -20, -36, -60], [80, 90, 120, 130, 140]),
    ("soprano", "a"): ([800, 1150, 2900, 3900, 4950], [0, -6, -32, -20, -50], [80, 90, 120, 130, 140]),
    ("bass", "o"): ([400, 750, 2400, 2600, 2900], [0, -11, -21, -20, -40], [40, 80, 100, 120, 120]),
    ("tenor", "o"): ([400, 800, 2600, 2800, 3000], [0, -10, -12, -12, -26], [40, 80, 100, 120, 120]),
    ("alto", "o"): ([450, 800, 2830, 3500, 4950], [0, -9, -16, -28, -55], [70, 80, 100, 130, 135]),
    ("soprano", "o"): ([450, 800, 2830, 3800, 4950], [0, -11, -22, -22, -50], [70, 80, 100, 130, 135]),
    ("bass", "u"): ([350, 600, 2400, 2675, 2950], [0, -20, -32, -28, -36], [40, 60, 100, 120, 120]),
    ("tenor", "u"): ([350, 600, 2700, 2900, 3300], [0, -20, -17, -14, -26], [40, 60, 100, 120, 120]),
    ("alto", "u"): ([325, 700, 2530, 3500, 4950], [0, -12, -30, -40, -64], [50, 60, 170, 180, 200]),
    ("soprano", "u"): ([325, 700, 2700, 3800, 4950], [0, -16, -35, -40, -60], [50, 60, 170, 180, 200]),
}


def _voice_type(f):
    return "bass" if f < 160 else ("tenor" if f < 300 else ("alto" if f < 480 else "soprano"))


def _formant_filter(x, vtype, vowel, fscale=1.0, count=4):
    fr, gdb, bw = _FORMANTS[(vtype, vowel)]
    y = np.zeros_like(x)
    for f, g, b in list(zip(fr, gdb, bw))[:count]:
        f = f * fscale
        y += dsp.db2lin(g) * dsp.biquad(x, "bp", f, q=f / (b * fscale))
    return y


def choir(midi, dur, vel=0.6, r=None, cents=None, vowel="a", voices=4, attack=0.35, release=0.7, breath=0.1,
          width=0.9):
    """choir section on one pitch (stereo): sub-groups of singers with different vocal-tract lengths, each with
    detune, delayed vibrato, drift and shimmer; saw + narrow pulse source with a glottal tilt; formant banks"""
    r = r if r is not None else dsp.rng("choir", midi, vowel)
    pf = hz(midi)
    n = n_of(dur + release + 0.05)
    G = 3
    fsc = np.array([0.96, 1.0, 1.04]) * r.uniform(0.99, 1.01, G)
    gpan = np.array([-0.7, 0.0, 0.7]) * width
    vt = _voice_type(pf)
    subs = [np.zeros(n) for _ in range(G)]
    base = _cents(cents, n)
    m, tc = _ctrl_axis(n)
    for v in range(voices):
        vrate = r.uniform(4.8, 6.0) * (1.0 + 0.05 * _cnoise(m, r, 0.7))
        vib = r.uniform(12, 24) * dsp.smoothstep((tc - r.uniform(0.2, 0.5)) / 0.5) * \
            np.sin(TWO_PI * (np.cumsum(vrate) / CR + r.uniform()))
        cc = r.normal(0, 6.0) + vib + 5.0 * _cnoise(m, r, 0.8) + 2.0 * _cnoise(m, r, 11.0)
        f = pf * dsp.cents2ratio(_up(cc, n) + base)
        src = 0.8 * dsp.osc_saw(f, n, r.uniform()) + 0.35 * dsp.osc_square(f, n, r.uniform(), pw=0.28)
        a_j = attack * r.uniform(0.8, 1.35)
        e = _env_ctrl([(0, 0), (a_j, 1.0), (max(dur, a_j + 0.01), 0.95), (max(dur, a_j + 0.01) + release, 0),
                       (n / SR + 1, 0)], tc)
        e *= np.maximum(0.0, 1.0 + 0.07 * _cnoise(m, r, 1.5) + 0.03 * _cnoise(m, r, 17.0))
        subs[v % G] += src * _up(e, n)
    out = np.zeros((2, n))
    for g in range(G):
        x = dsp.onepole(subs[g], 1100.0)
        x = dsp.lowpass(x, 5200, 2)
        y = _formant_filter(x, vt, vowel, fsc[g])
        gl, gr = dsp.pan_gains(gpan[g] * r.uniform(0.8, 1.0))
        out[0] += y * gl
        out[1] += y * gr
    asp = _formant_filter(dsp.highpass(r.standard_normal((2, n)), 800, 2), vt, vowel, count=2)
    aenv = dsp.env_points([(0, 0), (attack, 1.0), (max(dur, attack + 0.01), 1.0),
                           (max(dur, attack + 0.01) + release, 0), (n / SR + 1, 0)], n, "cos")
    out = _nrm(out) + breath * aenv * asp / (dsp.peak(asp) + 1e-9)
    out = dsp.eq_chain(out, [("hp", 90, 0, 0.7), ("peak", 2800, -1.0, 1.0)])
    return _end_fade(_nrm(out), 0.05) * vel


def pad(midi, dur, vel=0.5, r=None, cents=None, attack=0.7, release=1.4, cutoff=1600.0, voices=4, detune=14.0):
    """warm analogue-style pad (stereo): detuned band-limited saws, slowly breathing low-pass, wide chorus"""
    r = r if r is not None else dsp.rng("pad", midi)
    f0 = hz(midi)
    n = n_of(dur + release + 0.05)
    out = np.zeros((2, n))
    base = _cents(cents, n)
    for v in range(voices):
        det = detune * (v / max(1, voices - 1) - 0.5) * 2.0 if voices > 1 else 0.0
        c = base + det + 4.0 * dsp.ctrl_noise(n, r, 0.3)
        osc = 0.7 * dsp.osc_saw(f0 * dsp.cents2ratio(c), n, r.uniform()) + \
            0.35 * np.sin(TWO_PI * dsp.phase_cycles(0.5 * f0 * dsp.cents2ratio(c), n, r.uniform()))
        out += dsp.pan_mono(osc, (v / max(1, voices - 1) - 0.5) * 1.6 if voices > 1 else 0.0)
    env = dsp.env_points([(0, 0), (attack, 1.0), (max(dur, attack + 0.01), 0.9), (max(dur, attack + 0.01) + release, 0),
                          (n / SR + 1, 0)], n, "cos")
    breathe = 1.0 + 0.25 * np.sin(TWO_PI * dsp.phase_cycles(0.13, n, r.uniform()))
    fc = np.clip(cutoff * (0.6 + 0.4 * vel) * breathe * (0.5 + 0.5 * env), 200.0, 9000.0)
    out = dsp.lp_varying(out, fc, 0.8, spacing=0.5) * env
    out = dsp.eq_chain(out, [("hp", 70, 0, 0.7), ("peak", 300, 1.5, 0.8)])
    return _end_fade(_nrm(out), 0.05) * vel
