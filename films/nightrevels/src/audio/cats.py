"""
cats.py -- synthesized cat voices for The Night Revels of Han Xizai, Cat Edition.

Building blocks (all return mono float64 at dsp.SR, onset at sample 0, peak-normalised to 1.0):
    meow(f0, dur, who, size, contour, r)   formant voice: nasal 'm' -> open 'e/a' -> rounded 'ow' glide,
                                            contours normal | offended ('mrrp!') | sheepish | mip
    purr(dur, who, r)                       ~23-31 Hz pulse train, exhale/inhale breath cycles, warm band
    trill(f0, dur, who, size, rise, r)      tongue-trilled rising 'brrrp' chirrup
    chirp_chatter(dur, who, r)              hunting chatter: a 'mrrt' chirrup + rapid 'ek-ek-ek' at ~12 Hz
    yawn(who, r), sigh(who, r), giggle(dur, r) (stereo), lick(r)

EVENTS = {type: fn(ev, r) -> (clip, anchor)} for the story events handled here.
Voices of individual cats (who) set pitch, formant scale (vocal-tract size) and purr rate.
"""
import re

import numpy as np

import dsp
from dsp import n_of, t_axis, TWO_PI

# pitch multiplier, formant scale, purr rate (Hz), purr brightness
WHO = {
    None:     dict(pitch=1.00, fs=1.00, purr=26.0, bright=1.0),
    "han":    dict(pitch=0.70, fs=0.84, purr=23.0, bright=0.80),   # Maine Coon: big, low, deep purr
    "lady":   dict(pitch=1.05, fs=1.00, purr=25.0, bright=0.90),   # white Persian
    "wang":   dict(pitch=1.12, fs=1.03, purr=27.0, bright=1.05),   # Siamese dancer
    "monk":   dict(pitch=0.88, fs=0.95, purr=25.0, bright=0.95),   # Sphynx
    "lang":   dict(pitch=0.95, fs=0.97, purr=25.5, bright=1.0),    # ginger tabby
    "bcat":   dict(pitch=0.92, fs=0.96, purr=25.0, bright=0.95),   # basket cat
    "kitten": dict(pitch=1.45, fs=1.20, purr=30.5, bright=1.30),   # the painter kitten
    "fold":   dict(pitch=1.15, fs=1.05, purr=27.0, bright=1.05),
}


def _who(who, size=1.0):
    key = None
    if who:
        k = re.sub(r"\d+$", "", str(who)).lower()
        key = k if k in WHO else None
    w = dict(WHO[key])
    s = float(size) if size else 1.0
    w["pitch"] *= s ** -0.6
    w["fs"] *= s ** -0.35
    return w


def _curve(points, n, dur, scale=1.0, curve="cos"):
    """breakpoints in normalised time u in [0, 1] -> per-sample curve over dur seconds"""
    return dsp.env_points([(u * dur, v * scale) for u, v in points], n, curve)


_FB = (120.0, 170.0, 250.0, 330.0)        # formant bandwidths (Hz)
_FG = (1.0, 0.6, 0.3, 0.12)                # formant gains


def _voice(f0, F, amp, r, breath=0.15, tilt=1800.0, jitter=0.008, shimmer=0.06, bw=1.0, rough=0.0):
    """glottal-ish source (saw + narrow pulse, tilt, jitter, shimmer, aspiration) through a parallel bank of
    time-varying formant bandpasses F = [F1(t), F2(t), ...]; amp(t) applied at the end."""
    n = len(f0)
    f = f0 * (1.0 + jitter * dsp.ctrl_noise(n, r, 30.0, rate=2000.0))
    src = 0.75 * dsp.osc_saw(f, n, r.uniform()) + 0.45 * dsp.osc_square(f, n, r.uniform(), pw=0.28)
    if rough > 0:          # period-doubling roughness (raspy, indignant)
        src *= 1.0 + rough * np.sin(np.pi * dsp.phase_cycles(f, n))
    src = dsp.onepole(src, tilt)
    src /= dsp.rms(src) + 1e-12
    src *= np.maximum(0.0, 1.0 + shimmer * dsp.ctrl_noise(n, r, 50.0, rate=2000.0))
    asp = dsp.highpass(r.standard_normal(n), 500.0, 2)
    ex = src + 3.0 * breath * asp
    y = np.zeros(n)
    for k, Fk in enumerate(F):
        q = np.clip(Fk / (_FB[k] * bw), 0.8, 30.0)
        y += _FG[k] * dsp.tv_biquad(ex, "bp", Fk, q, block=64)
    return y * amp


# ======================================================================================  meow
_CONTOURS = {
    # pitch (x f0), F1, F2, F3 (Hz, before formant scaling), amplitude, nasal murmur, breath
    "normal": dict(
        pitch=[(0, 0.86), (0.3, 1.12), (0.6, 1.05), (1, 0.78)],
        F1=[(0, 330), (0.14, 420), (0.34, 1000), (0.6, 950), (0.85, 700), (1, 430)],
        F2=[(0, 1800), (0.14, 1850), (0.34, 1900), (0.6, 1600), (0.85, 1050), (1, 900)],
        F3=[(0, 2900), (0.35, 3300), (1, 2800)],
        amp=[(0, 0), (0.04, 0.35), (0.15, 0.45), (0.32, 1.0), (0.75, 0.85), (0.93, 0.3), (1, 0)],
        nasal=[(0, 0), (0.03, 0.55), (0.17, 0.4), (0.3, 0.0), (1, 0.0)],
        breath=0.15, dur=0.55),
    "offended": dict(      # 'mrrp!': rolled rr, quick upward jump, abrupt stop
        pitch=[(0, 0.9), (0.38, 0.93), (0.5, 1.25), (0.85, 1.32), (1, 1.22)],
        F1=[(0, 380), (0.4, 520), (0.55, 980), (0.9, 900), (1, 700)],
        F2=[(0, 1500), (0.4, 1400), (0.55, 1850), (1, 1700)],
        F3=[(0, 2800), (0.5, 3200), (1, 3100)],
        amp=[(0, 0), (0.05, 0.55), (0.4, 0.7), (0.52, 1.0), (0.94, 0.95), (1, 0)],
        nasal=[(0, 0), (0.04, 0.5), (0.3, 0.3), (0.45, 0.0), (1, 0.0)],
        breath=0.12, dur=0.32),
    "sheepish": dict(      # small, soft, falling, breathy
        pitch=[(0, 1.08), (0.25, 1.02), (1, 0.72)],
        F1=[(0, 350), (0.2, 520), (0.4, 800), (0.75, 600), (1, 400)],
        F2=[(0, 1800), (0.4, 1750), (0.8, 1150), (1, 950)],
        F3=[(0, 2900), (1, 2800)],
        amp=[(0, 0), (0.1, 0.6), (0.38, 1.0), (0.8, 0.55), (1, 0)],
        nasal=[(0, 0), (0.05, 0.45), (0.2, 0.2), (0.35, 0.0), (1, 0.0)],
        breath=0.45, dur=0.5),
    "mip": dict(           # tiny nose-touch 'mip'
        pitch=[(0, 1.45), (0.4, 1.75), (1, 1.62)],
        F1=[(0, 350), (0.5, 620), (1, 400)],
        F2=[(0, 2000), (0.5, 2450), (1, 2250)],
        F3=[(0, 3200), (1, 3500)],
        amp=[(0, 0), (0.15, 0.6), (0.4, 1.0), (0.8, 0.7), (1, 0)],
        nasal=[(0, 0), (0.1, 0.5), (0.35, 0.0), (1, 0.0)],
        breath=0.1, dur=0.11),
}


def meow(f0=600.0, dur=None, who=None, size=1.0, contour="normal", r=None):
    """formant meow; f0 = base pitch of a medium cat (who/size scale it); contour normal|offended|sheepish|mip"""
    c = _CONTOURS[contour]
    w = _who(who, size)
    dur = float(dur) if dur else c["dur"]
    r = r if r is not None else dsp.rng("meow", f0, dur, who, contour)
    n = n_of(dur)
    fs = w["fs"] * r.uniform(0.97, 1.03)
    f0c = _curve(c["pitch"], n, dur, f0 * w["pitch"] * r.uniform(0.96, 1.04))
    F = [_curve(c[k], n, dur, fs) for k in ("F1", "F2", "F3")]
    F.append(np.full(n, 4300.0 * fs))
    amp = _curve(c["amp"], n, dur)
    rough = 0.35 if contour == "offended" else 0.0
    y = _voice(f0c, F, amp, r, breath=c["breath"], rough=rough,
               tilt=1400.0 if contour == "sheepish" else 1900.0)
    y /= dsp.peak(y) + 1e-12
    # nasal murmur ('m' hum through the nose)
    nas = _curve(c["nasal"], n, dur)
    hum = dsp.osc_sine(f0c, n) + 0.3 * dsp.osc_sine(2.0 * f0c, n)
    y += 0.45 * nas * hum
    if contour == "offended":
        # rolled 'rr' in the first ~45 %: tongue-trill flutter ~27 Hz
        t = t_axis(n)
        dep = 0.8 * (1.0 - dsp.smoothstep((t / dur - 0.3) / 0.18))
        y *= 1.0 - dep * (0.5 + 0.5 * np.cos(TWO_PI * dsp.phase_cycles(27.0 * r.uniform(0.95, 1.05), n)))
    y = dsp.highpass(y, 180.0, 2)
    y = dsp.fade(y, 0.002, 0.004 if contour == "offended" else 0.012)
    return dsp.normalize(y, 1.0)


# ======================================================================================  trill / chirp
def trill(f0=700.0, dur=0.3, who=None, size=1.0, rise=1.3, rate=25.0, r=None):
    """tongue-trilled chirrup 'brrrp' (rising)"""
    w = _who(who, size)
    r = r if r is not None else dsp.rng("trill", f0, dur, who)
    n = n_of(dur)
    t = t_axis(n)
    fs = w["fs"] * r.uniform(0.96, 1.04)
    f0c = _curve([(0, 0.9), (0.6, rise), (1, rise * 0.96)], n, dur, f0 * w["pitch"])
    F = [_curve([(0, 420), (0.5, 620), (1, 520)], n, dur, fs),
         _curve([(0, 1500), (0.5, 1850), (1, 1750)], n, dur, fs),
         np.full(n, 2950.0 * fs)]
    amp = _curve([(0, 0), (0.08, 0.8), (0.7, 1.0), (1, 0)], n, dur)
    y = _voice(f0c, F, amp, r, breath=0.12)
    dep = 0.85 - 0.5 * dsp.smoothstep(t / dur)
    y *= 1.0 - dep * (0.5 + 0.5 * np.cos(TWO_PI * dsp.phase_cycles(rate * r.uniform(0.9, 1.1), n)))
    y = dsp.highpass(y, 200.0, 2)
    return dsp.normalize(dsp.fade(y, 0.002, 0.01), 1.0)


def _ek(r, f0, dur=0.036):
    """one chatter 'ek': sharp teeth click + short down-chirped tweet"""
    n = n_of(dur)
    t = t_axis(n)
    f = f0 * (1.0 + 0.35 * np.exp(-t / 0.008)) * (1.0 - 0.15 * t / dur)
    ph = dsp.phase_cycles(f, n)
    tone = np.sin(TWO_PI * ph) + 0.35 * np.sin(2 * TWO_PI * ph + 0.3) + 0.12 * np.sin(3 * TWO_PI * ph)
    env = np.clip(t / 0.003, 0, 1) * np.exp(-t / 0.011)
    y = tone * env
    k = n_of(0.003)
    click = dsp.highpass(r.standard_normal(k), 2500.0, 2) * np.exp(-t[:k] / 0.0006)
    y[:k] += 0.5 * click / (dsp.peak(click) + 1e-9)
    y += 0.12 * dsp.bandpass(r.standard_normal(n), 1500, 6000, 2) * env
    return y


def chirp_chatter(dur=0.8, who=None, r=None):
    """hunting chatter at a moth: small 'mrrt' chirrup, then a rapid run of 'ek-ek-ek' (~12 Hz)"""
    w = _who(who)
    r = r if r is not None else dsp.rng("chatter", dur, who)
    dur = float(np.clip(dur, 0.5, 1.2))
    n = n_of(dur + 0.08)
    y = np.zeros(n)
    tr = trill(640.0, 0.14, who=who, rise=1.25, rate=30.0, r=r)
    dsp.place(y, tr, 0, 0.7)
    tk = 0.17
    rate = 12.0 * r.uniform(0.92, 1.08)
    k = 0
    while tk < dur - 0.04:
        prog = (tk - 0.17) / max(dur - 0.21, 1e-3)
        lvl = (0.75 + 0.25 * np.sin(np.pi * min(prog * 1.2, 1.0))) * r.uniform(0.75, 1.0)
        f = 1650.0 * w["pitch"] ** 0.5 * r.uniform(0.9, 1.12) * (1.08 if k % 2 == 0 else 0.97)
        dsp.place(y, _ek(r, f), n_of(tk), lvl)
        tk += (1.0 / rate) * r.uniform(0.85, 1.15)
        k += 1
    y = dsp.highpass(y, 300.0, 2)
    return dsp.normalize(y, 1.0)


# ======================================================================================  purr
def purr(dur=3.0, who=None, r=None):
    """real-cat purr: laryngeal pulses at ~25 Hz, voiced on the exhale and (quieter, slightly slower) the inhale,
    ~2 s breath cycles, each pulse a short noisy burst filtered into a warm 60-1500 Hz band"""
    w = _who(who)
    r = r if r is not None else dsp.rng("purr", dur, who)
    dur = max(float(dur), 0.6)
    n = n_of(dur)
    rate0 = w["purr"] * r.uniform(0.97, 1.03)
    # breath cycle breakpoints: exhale (loud, rate0), short gap, inhale (softer, ~0.9 rate0), short gap
    lv_pts, rt_pts = [(0.0, 0.0)], [(0.0, rate0)]
    tc = 0.0
    phase_in = r.uniform(0.0, 1.0) < 0.5
    while tc < dur + 2.5:
        cyc = r.uniform(1.7, 2.3)
        ex = cyc * r.uniform(0.52, 0.6)
        segs = [(ex, 1.0 * r.uniform(0.9, 1.05), rate0), (cyc - ex, 0.62 * r.uniform(0.85, 1.1), rate0 * 0.9)]
        if phase_in:
            segs = segs[::-1]
        for (L, lv, rt) in segs:
            lv_pts += [(tc + 0.06, lv), (tc + L - 0.07, lv * 0.92), (tc + L, 0.12)]
            rt_pts += [(tc + 0.05, rt), (tc + L - 0.05, rt)]
            tc += L
    lv = dsp.env_points(lv_pts, n, "cos")
    rt = dsp.env_points(rt_pts, n, "lin") * (1.0 + 0.025 * dsp.ctrl_noise(n, r, 1.5, rate=500.0))
    ph = dsp.phase_cycles(rt, n)
    frac = ph % 1.0
    idx = np.floor(ph).astype(np.int64)
    pa = np.exp(r.normal(0.0, 0.18, idx.max() + 2))[idx]            # per-pulse amplitude variation
    pw = r.uniform(0.9, 1.1, idx.max() + 2)[idx]
    pulse = np.clip(frac / 0.05, 0, 1) * np.exp(-frac / (0.22 * pw))
    low = dsp.highpass(pulse * pa, 18.0, 2)
    lo_hi = 1100.0 * w["bright"]
    nz = dsp.bandpass(r.standard_normal(n), 70.0, lo_hi, 2)
    buzz = pulse ** 1.5 * pa * nz
    y = 0.8 * low / (dsp.rms(low) + 1e-12) + 1.0 * buzz / (dsp.rms(buzz) + 1e-12)
    y = dsp.eq_chain(y, [("peak", 160.0 * w["bright"], 4.0, 0.9), ("peak", 420.0 * w["bright"], 2.0, 1.0),
                         ("lp", 1500.0 * w["bright"], 0.0, 0.7), ("hp", 22.0, 0.0, 0.7)])
    y *= lv
    y = dsp.fade(y, min(0.35, dur * 0.2), min(0.5, dur * 0.25))
    return dsp.normalize(y, 1.0)


# ======================================================================================  yawn / sigh / giggle / lick
def yawn(who=None, r=None, dur=1.75):
    """big yawn: breathy wide 'aaaah' opening with falling pitch, ending in a tiny high squeak 'iik'"""
    w = _who(who)
    r = r if r is not None else dsp.rng("yawn", who)
    body = dur - 0.2
    n = n_of(dur + 0.05)
    nb = n_of(body)
    f0c = _curve([(0, 1.0), (0.3, 0.9), (1, 0.55)], nb, body, 520.0 * w["pitch"])
    fs = w["fs"]
    F = [_curve([(0, 400), (0.3, 1100), (0.7, 1050), (1, 600)], nb, body, fs),
         _curve([(0, 1500), (0.3, 1700), (0.7, 1550), (1, 1200)], nb, body, fs),
         _curve([(0, 2800), (0.4, 3100), (1, 2700)], nb, body, fs)]
    amp = _curve([(0, 0), (0.18, 0.8), (0.45, 1.0), (0.8, 0.6), (1, 0)], nb, body)
    voiced = _voice(f0c, F, amp, r, breath=0.0, tilt=1200.0)
    breathy = _voice(f0c, F, amp, r, breath=2.5, tilt=1200.0, shimmer=0.0)     # mostly breath, a little voice
    y = np.zeros(n)
    yb = 0.9 * breathy / (dsp.peak(breathy) + 1e-9) + 0.25 * voiced / (dsp.peak(voiced) + 1e-9)
    y[:nb] += yb
    # the squeak 'iik'
    ns = n_of(0.12)
    fsq = _curve([(0, 1250), (0.45, 1750), (1, 1500)], ns, 0.12, w["pitch"] ** 0.4)
    Fs = [np.full(ns, 520.0 * fs), np.full(ns, 2650.0 * fs), np.full(ns, 3500.0 * fs)]
    sq = _voice(fsq, Fs, _curve([(0, 0), (0.2, 1.0), (0.7, 0.8), (1, 0)], ns, 0.12), r, breath=0.08)
    dsp.place(y, sq / (dsp.peak(sq) + 1e-9), n_of(body - 0.05), 0.75)
    y = dsp.highpass(y, 150.0, 2)
    return dsp.normalize(dsp.fade(y, 0.02, 0.02), 1.0)


def sigh(who="han", r=None):
    """weary huff through the nose (han: with a tiny voiced 'hmm'); monk: longer relieved 'pfff'"""
    w = _who(who)
    r = r if r is not None else dsp.rng("sigh", who)
    if who == "monk":
        dur = 1.45
        n = n_of(dur)
        t = t_axis(n)
        env = dsp.env_points([(0, 0), (0.05, 1.0), (0.35, 0.75), (1.0, 0.3), (dur, 0.0)], n, "cos")
        fff = dsp.bandpass(r.standard_normal(n), 900.0, 5500.0, 2)
        haah = dsp.eq_chain(r.standard_normal(n), [("bp", 750.0, 0.0, 3.0)]) * 2.0 \
            + dsp.eq_chain(r.standard_normal(n), [("bp", 1250.0, 0.0, 4.0)]) * 1.2
        y = env * (0.7 * fff / dsp.rms(fff) + 0.6 * haah / dsp.rms(haah))
        k = n_of(0.02)
        pl = dsp.bandpass(r.standard_normal(k), 300.0, 3000.0, 2) * np.exp(-t[:k] / 0.004)
        y[:k] += 3.0 * pl / (dsp.peak(pl) + 1e-9)
        y *= 1.0 + 0.1 * dsp.ctrl_noise(n, r, 8.0, rate=500.0)
    else:
        dur = 1.05
        n = n_of(dur)
        t = t_axis(n)
        env = np.clip(t / 0.06, 0, 1) * np.exp(-t / 0.33)
        nz = dsp.eq_chain(r.standard_normal(n), [("bp", 950.0 * w["fs"], 0.0, 1.2), ("notch", 1800.0, 0.0, 3.0),
                                                 ("peak", 420.0, 4.0, 1.5)])
        y = env * nz / dsp.rms(nz)
        # the tiny 'hmm' (nasal murmur, falling)
        nh = n_of(0.55)
        f = _curve([(0, 1.0), (1, 0.75)], nh, 0.55, 300.0 * w["pitch"] * 1.1)
        hm = dsp.osc_saw(f, nh, r.uniform())
        hm = dsp.lowpass(dsp.onepole(hm, 500.0), 900.0, 2)
        hm *= dsp.env_points([(0, 0), (0.04, 1.0), (0.3, 0.6), (0.55, 0.0)], nh, "cos")
        dsp.place(y, hm / (dsp.peak(hm) + 1e-9) * 1.1, n_of(0.03))
    y = dsp.highpass(y, 120.0, 2)
    return dsp.normalize(dsp.fade(y, 0.004, 0.05), 1.0)


def giggle(dur=1.4, r=None, cats=4):
    """several cats chirruping / trilling happily (stereo)"""
    r = r if r is not None else dsp.rng("giggle", dur)
    dur = max(float(dur), 0.6)
    n = n_of(dur + 0.4)
    out = np.zeros((2, n))
    pans = np.linspace(-0.65, 0.65, cats) + r.uniform(-0.1, 0.1, cats)
    whos = ["fold", "lang", "wang", "kitten", None][:cats]
    for c in range(cats):
        tc = r.uniform(0.0, 0.18)
        while tc < dur - 0.15:
            d = r.uniform(0.14, 0.28)
            f0 = r.uniform(620.0, 900.0)
            if r.uniform() < 0.7:
                y = trill(f0, d, who=whos[c], rise=r.uniform(1.2, 1.5), rate=r.uniform(22.0, 30.0), r=r)
            else:
                y = meow(f0, d * 0.8, who=whos[c], size=0.8, contour="mip", r=r)
            gl, gr = dsp.pan_gains(pans[c])
            lv = r.uniform(0.55, 1.0) * (1.0 - 0.35 * tc / dur)
            dsp.place(out, np.vstack([y * gl, y * gr]), n_of(tc), lv)
            tc += d + r.uniform(0.05, 0.22)
    return dsp.normalize(dsp.fade(out, 0.0, 0.05), 1.0)


def lick(r=None):
    """single small wet lick 'tlk': tongue pop + tiny slurpy swish"""
    r = r if r is not None else dsp.rng("lick")
    n = n_of(0.13)
    y = np.zeros(n)
    k = n_of(0.025)
    pop = dsp.modal([420.0 * r.uniform(0.9, 1.1), 1150.0 * r.uniform(0.9, 1.1), 2300.0], [1.0, 0.6, 0.3],
                    [0.02, 0.012, 0.008], k, r=r)
    y[:k] += pop / (dsp.peak(pop) + 1e-9)
    ks = n_of(0.09)
    sw = r.standard_normal(ks) * (1.0 + 1.2 * np.abs(dsp.crackle(ks, r, 400.0, hp=0)))
    sw = dsp.tv_biquad(sw, "bp", np.geomspace(5200.0, 2300.0, ks), 1.6, block=64)
    sw *= dsp.env_points([(0, 0), (0.012, 1.0), (0.05, 0.5), (0.09, 0.0)], ks, "cos")
    dsp.place(y, sw / (dsp.peak(sw) + 1e-9) * 0.7, n_of(0.008))
    y = dsp.highpass(y, 200.0, 2)
    return dsp.normalize(dsp.fade(y, 0.0005, 0.01), 1.0)


# ======================================================================================  event wrappers
def _ev_chirp(ev, r):
    return chirp_chatter(ev.get("dur") or 0.8, ev.get("who"), r=r), 0


def _ev_sigh(ev, r):
    return sigh(ev.get("who") or "han", r=r), 0


def _ev_meow_offended(ev, r):
    return meow(600.0, ev.get("dur") or 0.32, who=ev.get("who") or "han", size=ev.get("size") or 1.0,
                contour="offended", r=r), 0


def _ev_meow_sheepish(ev, r):
    return meow(600.0, ev.get("dur") or 0.5, who=ev.get("who"), size=ev.get("size") or 1.0,
                contour="sheepish", r=r), 0


def _ev_purr(ev, r):
    return purr(ev.get("dur") or 3.0, ev.get("who"), r=r), 0


def _ev_yawn(ev, r):
    return yawn(ev.get("who"), r=r), 0


def _ev_giggle(ev, r):
    return giggle(ev.get("dur") or 1.4, r=r), 0


def _ev_lick(ev, r):
    return lick(r=r), 0


EVENTS = {
    "chirp": _ev_chirp,
    "sigh": _ev_sigh,
    "meow_offended": _ev_meow_offended,
    "meow_sheepish": _ev_meow_sheepish,
    "purr": _ev_purr,
    "yawn": _ev_yawn,
    "giggle": _ev_giggle,
    "lick": _ev_lick,
}
