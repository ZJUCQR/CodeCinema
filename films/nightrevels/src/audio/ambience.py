"""
ambience.py -- the quiet night-hall bed under the whole film.

    room tone     warm low noise floor of a big timber hall (decorrelated stereo, slow breathing)
    candles       very soft, sparse wick crackles + a faint flame flutter
    crickets      distant, outside the paper windows: the intermission (scene 'rest') and, fewer, the epilogue
    dawn birds    one or two soft distant calls near the end (frame ~2900+)

    render(doc, n_total) -> (2, n_total) stereo at nominal level (the mix sets the bus gain)
"""
import numpy as np

import dsp
from dsp import SR, n_of, t_axis, TWO_PI


def _sec(doc, sid):
    for s in doc.get("sections", []):
        if s["id"] == sid:
            return s
    return None


def _f2t(frame, fps=24.0):
    return (float(frame) - 1.0) / fps


def _window(n_total, t0, t1, fin=2.0, fout=2.0):
    t = np.arange(n_total) / SR
    return dsp.smoothstep((t - t0) / max(fin, 1e-3)) * (1.0 - dsp.smoothstep((t - (t1 - fout)) / max(fout, 1e-3)))


def room_tone(n, r):
    out = np.zeros((2, n))
    for ch in range(2):
        b = dsp.lowpass(dsp.brown(n, r), 180, 2)
        p = dsp.lowpass(dsp.pink(n, r), 1400, 2)
        out[ch] = 0.8 * b + 0.12 * p
    breath = 1.0 + 0.12 * dsp.ctrl_noise(n, r, 0.08, rate=50.0)
    out *= breath
    return dsp.highpass(out, 30, 2)


def candles(n, r):
    out = np.zeros((2, n))
    for ch in range(2):
        c = dsp.crackle(n, r, 0.55, amp_sigma=0.8, dur_range=(0.0004, 0.0025), hp=1800.0)
        c = dsp.lowpass(c, 7000, 2)
        # flame flutter: gentle low 'fff' of the wick in a draught
        fl = dsp.bandpass(r.standard_normal(n), 120, 900, 2) * np.clip(0.4 + 0.6 * dsp.ctrl_noise(n, r, 0.6, rate=100.0), 0, None)
        out[ch] = 0.9 * c / (dsp.peak(c) + 1e-9) + 0.05 * fl / (dsp.rms(fl) + 1e-9) * 0.05
    return out


def _cricket(dur, r, f=4500.0, rate=1.6, pulses=4):
    """one field cricket: chirps of `pulses` syllables (~15 ms, 32 ms apart) repeated `rate` times per second"""
    n = n_of(dur)
    y = np.zeros(n)
    tt = r.uniform(0, 0.6)
    syl = n_of(0.016)
    ts = t_axis(syl)
    win = np.sin(np.pi * ts / (syl / SR)) ** 2
    while tt < dur - 0.3:
        k = pulses + int(r.integers(-1, 2))
        g = r.uniform(0.7, 1.0)
        for j in range(max(2, k)):
            s = n_of(tt + j * 0.032 * r.uniform(0.95, 1.05))
            fj = f * r.uniform(0.995, 1.005) * (1.0 - 0.012 * ts / ts[-1])
            ph = TWO_PI * np.cumsum(fj) / SR
            syl_sig = (np.sin(ph) + 0.08 * np.sin(2 * ph)) * win * g
            e = min(n, s + syl)
            y[s:e] += syl_sig[: e - s]
        tt += (1.0 / rate) * r.uniform(0.8, 1.25)
        if r.uniform() < 0.08:
            tt += r.uniform(0.8, 2.5)             # pauses now and then
    return y


def crickets(dur, r, count=3, spread=0.8):
    n = n_of(dur)
    out = np.zeros((2, n))
    for i in range(count):
        f = r.uniform(3900, 5200)
        y = _cricket(dur, r, f=f, rate=r.uniform(1.2, 2.2), pulses=int(r.integers(3, 6)))
        y = dsp.lowpass(y, 5800 + 1500 * r.uniform(), 2) * r.uniform(0.45, 1.0)   # distance
        out += dsp.pan_mono(y, r.uniform(-spread, spread))
    wet = dsp.convolve_reverb(out, "field", seed=3)
    return out * 0.7 + 0.5 * wet


def _bird_call(r, kind=0):
    """a soft dawn call: kind 0 = two sweet descending whistles, kind 1 = a short sparrow-like chirrup series"""
    if kind == 0:
        dur = 0.9
        n = n_of(dur)
        y = np.zeros(n)
        for (t0, f0, f1, d) in [(0.0, 3600, 2900, 0.22), (0.34, 3500, 2750, 0.26)]:
            m = n_of(d)
            tt = t_axis(m)
            f = f0 + (f1 - f0) * (tt / d) ** 0.7 + 60 * np.sin(TWO_PI * 28 * tt)
            ph = TWO_PI * np.cumsum(f) / SR
            env = np.sin(np.pi * tt / d) ** 1.5
            s = n_of(t0)
            y[s:s + m] += env * (np.sin(ph) + 0.1 * np.sin(2 * ph))
        return y
    dur = 1.1
    n = n_of(dur)
    y = np.zeros(n)
    t0 = 0.0
    for j in range(int(r.integers(4, 7))):
        d = r.uniform(0.045, 0.07)
        m = n_of(d)
        tt = t_axis(m)
        f = np.linspace(r.uniform(4800, 5600), r.uniform(3000, 3600), m)
        ph = TWO_PI * np.cumsum(f) / SR
        env = np.sin(np.pi * tt / d) ** 2
        s = n_of(t0)
        e = min(n, s + m)
        y[s:e] += (env * (np.sin(ph) + 0.2 * np.sin(2 * ph)))[: e - s] * r.uniform(0.6, 1.0)
        t0 += d + r.uniform(0.07, 0.13)
        if t0 > dur - 0.1:
            break
    return y


def render(doc, n_total):
    fps = float(doc.get("fps", 24))
    r = dsp.rng("ambience")
    total_s = n_total / SR
    out = np.zeros((2, n_total))
    # room tone + candles for the whole film (fade in from the black opening)
    rt = room_tone(n_total, r)
    rt = rt / (dsp.rms(rt) + 1e-12) * dsp.db2lin(-50.0)
    cd = candles(n_total, r) * dsp.db2lin(-40.0)
    bed = rt + cd
    bed *= _window(n_total, 0.0, total_s + 10.0, fin=3.0, fout=1.0)
    out += bed

    # crickets: the intermission (full), the epilogue (a few, fading toward dawn)
    rest = _sec(doc, "rest") or dict(f0=1465, f1=1848)
    t0, t1 = _f2t(rest["f0"], fps), _f2t(rest["f1"] + 1, fps)
    cr = crickets(t1 - t0 + 1.0, r, count=4)
    cr = cr / (dsp.rms(cr) + 1e-12) * dsp.db2lin(-40.0)
    buf = np.zeros((2, n_total))
    dsp.place(buf, cr, n_of(t0 - 0.5))
    out += buf * _window(n_total, t0 - 0.5, t1 + 0.5, fin=2.5, fout=2.5)

    epi = _sec(doc, "epilogue") or dict(f0=2713, f1=3072)
    e0 = _f2t(epi["f0"], fps) + 1.0
    cr2 = crickets(total_s - e0 + 0.5, r, count=2, spread=0.6)
    cr2 = cr2 / (dsp.rms(cr2) + 1e-12) * dsp.db2lin(-46.0)
    buf = np.zeros((2, n_total))
    dsp.place(buf, cr2, n_of(e0))
    t_dawn = _f2t(2900, fps)
    out += buf * _window(n_total, e0, t_dawn + 3.0, fin=3.0, fout=4.0)

    # dawn birds
    for (fr, kind, pan) in [(2912, 0, -0.45), (2968, 1, 0.5), (3034, 0, -0.3)]:
        t = _f2t(fr, fps)
        if t >= total_s - 0.3:
            continue
        b = _bird_call(dsp.rng("bird", fr), kind)
        b = dsp.lowpass(b, 6500, 2)
        st = dsp.pan_mono(b, pan)
        st = st + 0.6 * dsp.convolve_reverb(st, "field", seed=5, n_out=st.shape[-1] + n_of(1.0))[:, : st.shape[-1]]
        st = st / (dsp.peak(st) + 1e-12) * dsp.db2lin(-34.0)
        dsp.place(out, st, n_of(t))
    return out
