"""
instruments.py -- synthesized Tang-court instruments for the score of The Night Revels of Han Xizai, Cat Edition.

Every function returns float64 audio at dsp.SR whose first sample is the note onset (anchor 0).  Mono
instruments return shape (n,); the bell and the sheng pad return stereo (2, n).  Levels: peak ~ vel (0..1) so
the score balances with plain gains.  All randomness comes from the Generator `r` -> deterministic renders.

    pipa        bright plucked lute (Tang plectrum style): Karplus-Strong string with a shaped plectrum
                excitation, nail/plectrum click, body resonances, yin vibrato on long notes, bends.
                tech: None/pluck | tremolo (lunzhi, ~13 Hz re-plucks) | harmonic | sour (the comic wrong note:
                buzzing slap, clashing neighbour string, pitch droop)
    pipa_strum  chord: all strings swept by the plectrum within a few tens of ms
    jiegu       small bright double-headed drum: 'center' (crisp high tock), 'rim' (wooden click),
                'final' (both sticks, both heads, big hall-filling stroke)
    paiban      wooden clapper slats
    dizi        bamboo flute with the membrane buzz (dimo), breath, chiff, vibrato, grace notes;
                tech 'long' (strains, sags and trembles toward its end), 'squeak' (cracks into a high squeak)
    bili        nasal double reed (scoops, wide vibrato, reed buzz)
    sheng       soft free-reed mouth-organ pad (stereo)
    guqin       low silk-string zither: soft flesh pluck, long decay, slides (zou yin) with silk friction,
                harmonics (fan yin)
    bell        temple bell / bowl (stereo): beating doublet partials tuned to D, wooden striker thud
"""
import numpy as np

import dsp
from dsp import SR, n_of, t_axis, LN1000, TWO_PI

NYQ_SAFE = 0.45 * SR


def _r(r, *keys):
    return r if r is not None else dsp.rng("inst", *keys)


def _unit(x):
    return x / (dsp.peak(x) + 1e-12)


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
    exc = _unit(exc) + scrape * (scr - scr.mean())
    if lp:
        exc = dsp.lowpass(np.concatenate([exc, exc]), lp, 2)[N:]
    return exc


# ======================================================================================  pipa
_PIPA_BODY = [("peak", 250, 3.0, 1.4), ("peak", 520, 1.5, 1.6), ("peak", 800, -2.0, 1.0),
              ("peak", 1300, 2.0, 1.3), ("peak", 3300, 3.0, 1.0), ("highshelf", 9000, -3.0, 0.7), ("hp", 75, 0.0, 0.7)]


def _pipa_string(freq, hold, vel, r, bright=0.75, tail=0.45, cents=None, t60=None, click=1.0, damp_t60=0.22,
                 nonlin=None, eq=True):
    """one plectrum pluck; the string rings freely for `hold` s, then the hand damps it (t60 damp_t60)."""
    L = hold + tail
    n = n_of(L)
    t = t_axis(n)
    t60 = t60 or float(np.clip(2.0 * (220.0 / freq) ** 0.45, 0.8, 2.8))
    c = (5.0 + 12.0 * vel) * np.exp(-t / 0.035)                 # tension settle after the pluck
    if cents is not None:
        c = c + cents[:n] if len(cents) >= n else c + np.pad(cents, (0, n - len(cents)), mode="edge")
    exc = _shaped_exc(freq, r, bright=bright * (0.75 + 0.35 * vel), pos=0.1 + 0.04 * r.uniform(), lp=2500 + 9000 * vel)
    y = dsp.karplus_strong(freq, L, r, t60=t60, brightness=0.55 + 0.32 * bright, pick_pos=0.0, exc=exc, cents=c,
                           nonlin=nonlin, damp_after=(hold, damp_t60) if hold < L - 0.01 else None)
    y = _unit(y)
    # plectrum / nail: a sharp click + a short bright snap
    k = n_of(0.02)
    tk = t[:k]
    cl = dsp.highpass(r.standard_normal(k), 2800, 2) * np.exp(-tk / 0.0009)
    sn = dsp.bandpass(r.standard_normal(k), 1500, 6500, 2) * np.exp(-tk / 0.0035)
    y[:k] += click * vel * (0.32 * _unit(cl) + 0.22 * _unit(sn))
    if eq:
        y = dsp.eq_chain(y, _PIPA_BODY)
    return dsp.fade(y, 0.0, min(0.04, L * 0.2))


def _yin(n, r, depth=14.0, rate=5.4, delay=0.2):
    t = t_axis(n)
    return depth * dsp.smoothstep((t - delay) / 0.3) * np.sin(TWO_PI * dsp.phase_cycles(rate * (1 + 0.04 * r.uniform(-1, 1)), n, r.uniform()))


def pipa(freq, dur, vel=0.7, r=None, tech=None, bright=0.75, grace=None, choke_at=None):
    """one pipa note. grace: optional (cents, dur_s) slide into the note from `cents` away (tui / la)."""
    r = _r(r, "pipa", freq, dur, tech)
    if tech == "tremolo":
        y = pipa_tremolo(freq, dur, vel, r, bright)
    elif tech == "harmonic":
        y = pipa_harmonic(freq, dur, vel, r)
    elif tech == "sour":
        y = pipa_sour(freq, dur, vel, r)
    else:
        hold = max(dur, 0.12) * 1.15 + 0.05
        n = n_of(hold + 0.45)
        cents = np.zeros(n)
        if dur >= 0.5:
            cents += _yin(n, r, depth=12.0 + 6.0 * r.uniform(), delay=0.18)
        if grace:
            gc, gd = grace
            cents += gc * (1.0 - dsp.smoothstep(t_axis(n) / max(gd, 1e-3)))
        y = _pipa_string(freq, hold, vel, r, bright=bright, cents=cents)
        y = _unit(y) * vel
    if choke_at is not None:
        y = _choke(y, choke_at)
    return y


def _choke(y, t_sec, fade_s=0.03):
    k = n_of(t_sec)
    if k >= y.shape[-1]:
        return y
    y = np.array(y, copy=True)
    m = min(y.shape[-1] - k, n_of(fade_s))
    y[..., k:k + m] *= np.linspace(1.0, 0.0, m)
    y[..., k + m:] = 0.0
    return y


def pipa_tremolo(freq, dur, vel=0.7, r=None, bright=0.75, rate=None):
    """lunzhi: the five fingers (ring, middle, index, thumb...) re-pluck the string ~12-14 times per second.
    The string is one linear system, so the note is a sum of shifted plucks; each pluck is damped when the next
    finger touches the string."""
    r = _r(r, "pipa_trem", freq, dur)
    rate = rate or r.uniform(12.3, 13.8)
    total = dur + 0.5
    n = n_of(total)
    # variants: one per finger (different nail angle -> different excitation / brightness)
    variants = []
    for v in range(5):
        vb = bright * (0.85 + 0.08 * v)
        variants.append(_unit(_pipa_string(freq, total - 0.05, 1.0, r, bright=vb, tail=0.05, click=0.8)))
    # stroke times: slight acceleration into the tremolo, human jitter
    times = [0.0]
    tt = 0.0
    while True:
        rr = rate * (0.92 + 0.08 * min(1.0, tt / 0.25))
        tt += 1.0 / rr + r.normal(0.0, 0.0022)
        if tt > dur - 0.03:
            break
        times.append(tt)
    finger_g = [1.0, 0.8, 0.9, 0.78, 0.86]
    y = np.zeros(n)
    t = t_axis(n)
    for i, ts in enumerate(times):
        s = n_of(ts)
        nxt = times[i + 1] if i + 1 < len(times) else None
        clip = variants[i % 5][: n - s].copy()
        tc = t[: len(clip)]
        if nxt is not None:
            d = nxt - ts + 0.004
            clip *= np.where(tc < d, 1.0, np.exp(-(tc - d) / 0.012))
        else:
            # last stroke rings, then the hand releases
            d = max(0.25, dur - ts + 0.12)
            clip *= np.where(tc < d, 1.0, np.exp(-(tc - d) / 0.09))
        # dynamic shape of the tremolo: accent on the first stroke, gentle swell in the middle
        u = ts / max(dur, 1e-3)
        g = finger_g[i % 5] * (1.15 if i == 0 else (0.78 + 0.22 * np.sin(np.pi * min(u, 1.0)))) * r.uniform(0.92, 1.06)
        y[s:s + len(clip)] += g * clip
    y = dsp.fade(y, 0.0, 0.04)
    return _unit(y) * vel


def pipa_harmonic(freq, dur, vel=0.6, r=None):
    """fan yin: finger lightly touching a node -> glassy, almost pure partials with a soft pluck tick"""
    r = _r(r, "pipa_harm", freq)
    L = max(dur, 0.6) + 1.2
    n = n_of(L)
    t = t_axis(n)
    y = dsp.modal([freq, 2.0 * freq * 1.001, 3.0 * freq * 1.003], [1.0, 0.16, 0.05], [2.2, 1.0, 0.5], n, r=r, attack=0.002)
    k = n_of(0.02)
    tick = dsp.bandpass(r.standard_normal(k), 1500, 6000, 2) * np.exp(-t[:k] / 0.002)
    y[:k] += 0.18 * _unit(tick)
    y = dsp.fade(y, 0.0, 0.3)
    return _unit(y) * vel * 0.8


def _buzz_loop(amount):
    """energy-neutral in-loop rectifying buzz (string slapping the frets)"""
    def f(fb, k):
        rect = np.abs(fb)
        rect -= rect.mean()
        out = fb + amount * rect
        e0 = float(np.dot(fb, fb))
        e1 = float(np.dot(out, out))
        return out * np.sqrt(e0 / (e1 + 1e-30)) if e1 > 0 else out
    return f


def pipa_sour(freq, dur, vel=0.85, r=None):
    """the comic wrong note: the plectrum slips, the string slaps and buzzes on the frets, a neighbour string a
    semitone up rings along, and the whole thing droops flat like a sigh ('bwoiinng')."""
    r = _r(r, "pipa_sour", freq)
    hold = dur
    L = dur + 0.35
    n = n_of(L)
    t = t_axis(n)
    droop = (30.0 * np.exp(-t / 0.03)
             - 170.0 * dsp.smoothstep((t - 0.10) / 0.55)
             - 90.0 * dsp.smoothstep((t - 0.50) / 0.40)
             + 22.0 * dsp.smoothstep((t - 0.18) / 0.25) * np.sin(TWO_PI * 6.2 * t))
    main = _pipa_string(freq, hold, 1.0, r, bright=0.95, cents=droop, t60=2.6, click=1.2, damp_t60=0.12)
    clash = _pipa_string(freq * 2 ** (1.0 / 12.0), hold, 1.0, r, bright=0.8, cents=droop * 0.8 + 18.0, t60=2.2,
                         click=0.4, damp_t60=0.12)
    y = _unit(main) + 0.45 * _unit(clash)
    # fret buzz: the string slaps the frets while it swings wide -> a rasp that follows the amplitude
    env = dsp.onepole(np.abs(y), 25.0)
    env = env / (env.max() + 1e-12)
    buzz = np.sign(y) * np.abs(y / (env + 0.03)) ** 0.3
    buzz = dsp.bandpass(buzz, 1200, 6500, 2) * env ** 1.2
    y = y + 0.45 * _unit(buzz) * dsp.peak(y)
    # fret rattle: a decaying train of tiny clicks at ~45 Hz (the 'zzzt')
    k = min(n, n_of(0.45))
    rt = np.zeros(k)
    per = SR / 46.0
    for j in range(int(0.45 * 46)):
        idx = int(j * per * (1 + 0.03 * r.uniform(-1, 1)))
        if idx < k:
            rt[idx] = np.exp(-j / 7.0) * r.uniform(0.6, 1.0)
    rt = dsp.bandpass(np.convolve(rt, np.exp(-np.arange(90) / 12.0))[:k], 1200, 6000, 2)
    y[:k] += 0.3 * _unit(rt)
    # slap of the plectrum on the body
    ks = n_of(0.05)
    slap = dsp.bandpass(r.standard_normal(ks), 250, 2500, 2) * np.exp(-t[:ks] / 0.008)
    y[:ks] += 0.4 * _unit(slap)
    y = dsp.eq_chain(y, [("peak", 1800, 3.0, 1.0), ("hp", 90, 0.0, 0.7)])
    y = dsp.fade(y, 0.0, 0.05)
    return _unit(y) * vel


def pipa_strum(freqs, dur, vel=0.8, r=None, spread=0.012, direction="up"):
    """sao: the plectrum sweeps across the strings; returns mono, onset of the first string at 0"""
    r = _r(r, "pipa_strum", tuple(np.round(freqs, 2)), dur)
    fs = sorted(freqs) if direction == "up" else sorted(freqs, reverse=True)
    L = dur + 0.8
    y = np.zeros(n_of(L) + n_of(spread * len(fs)) + 10)
    for i, f in enumerate(fs):
        s = n_of(i * spread * r.uniform(0.8, 1.2))
        hold = dur
        c = _pipa_string(f, hold, vel, r, bright=0.85, tail=0.8, t60=float(np.clip(3.0 * (220 / f) ** 0.4, 1.5, 3.5)),
                         damp_t60=0.6)
        y[s:s + len(c)] += _unit(c) * (0.9 + 0.1 * i / max(1, len(fs) - 1))
    # plectrum rasp over the strings
    k = n_of(spread * len(fs) + 0.03)
    rasp = dsp.bandpass(r.standard_normal(k), 1800, 7000, 2) * dsp.env_points([(0, 0), (0.004, 1), (k / SR, 0.2)], k)
    y[:k] += 0.25 * vel * _unit(rasp)
    y = dsp.fade(y, 0.0, 0.1)
    return _unit(y) * vel


# ======================================================================================  guqin
_QIN_BODY = [("peak", 110, 3.0, 1.0), ("peak", 330, 2.0, 1.3), ("peak", 1900, -2.0, 0.8),
             ("highshelf", 4500, -5.0, 0.7), ("hp", 45, 0.0, 0.7)]


def guqin(freq, dur, vel=0.5, r=None, tech=None):
    """7-string silk zither. tech: None | slide (glide up into the note) | harmonic (fan yin)."""
    r = _r(r, "guqin", freq, dur, tech)
    if tech == "harmonic":
        return guqin_harmonic(freq, dur, vel, r)
    L = dur + 2.2
    n = n_of(L)
    t = t_axis(n)
    t60 = float(np.clip(7.0 * (110.0 / freq) ** 0.3, 4.0, 9.0))
    c = 4.0 * np.exp(-t / 0.05)
    slide_env = None
    if tech == "slide":
        # shang: pluck two scale steps below, then the left thumb glides up the silk into the note
        c += -300.0 * (1.0 - dsp.smoothstep((t - 0.10) / 0.55))
        slide_env = np.gradient(dsp.smoothstep((t - 0.10) / 0.55)) * SR
    if dur >= 3.0:
        # yin: a slow, decaying left-hand vibrato after the note has bloomed
        c += 9.0 * dsp.smoothstep((t - 0.9) / 0.5) * np.exp(-np.maximum(t - 1.4, 0) / 2.0) * \
            np.sin(TWO_PI * dsp.phase_cycles(3.6, n, r.uniform()))
    exc = _shaped_exc(freq, r, bright=0.25, pos=0.09, p_dark=1.7, scrape=0.05, lp=900 + 1800 * vel)
    y = dsp.karplus_strong(freq, L, r, t60=t60, brightness=0.38, pick_pos=0.0, exc=exc, cents=c)
    y = _unit(y)
    # fingertip thump + faint nail tick
    k = n_of(0.06)
    th = dsp.lowpass(r.standard_normal(k), 300, 2) * np.exp(-t[:k] / 0.012)
    y[:k] += 0.18 * _unit(th)
    if slide_env is not None:
        # silk friction under the sliding finger (the qin's characteristic whisper)
        fr = dsp.bandpass(r.standard_normal(n), 700, 3200, 2) * np.clip(slide_env / (slide_env.max() + 1e-9), 0, 1)
        fr = dsp.onepole(fr, 5000)
        y += 0.06 * _unit(fr)
    y = dsp.eq_chain(y, _QIN_BODY)
    y = dsp.fade(y, 0.0, 1.0)
    return _unit(y) * vel


def guqin_harmonic(freq, dur, vel=0.5, r=None):
    """fan yin: pure, bell-like floating tone"""
    r = _r(r, "qin_harm", freq)
    L = dur + 1.8
    n = n_of(L)
    t = t_axis(n)
    y = dsp.modal([freq, 2.0 * freq * 1.0015, 3.0 * freq * 1.004, 4.0 * freq * 1.007], [1.0, 0.22, 0.07, 0.03],
                  [4.5, 2.0, 1.0, 0.6], n, r=r, attack=0.003)
    k = n_of(0.03)
    tick = dsp.bandpass(r.standard_normal(k), 900, 4000, 2) * np.exp(-t[:k] / 0.003)
    y[:k] += 0.08 * _unit(tick)
    y = dsp.fade(y, 0.0, 0.8)
    return _unit(y) * vel * 0.75


# ======================================================================================  percussion
def jiegu(vel=0.7, r=None, stroke="center", head=0):
    """jiegu: small waisted drum on a stand, both heads struck with thin sticks -> crisp, bright, dry 'tock'.
    head 0/1 = left/right head (tuned a step apart)."""
    r = _r(r, "jiegu", vel, stroke, head)
    vel = float(np.clip(vel, 0.05, 1.2))
    if stroke == "final":
        return _jiegu_final(vel, r)
    dur = 0.4
    n = n_of(dur)
    t = t_axis(n)
    k = n_of(0.05)
    tk = t[:k]
    if stroke == "rim":
        y = dsp.modal(np.array([1780, 2950, 4480, 6300]) * r.uniform(0.97, 1.03),
                      [1.0, 0.55, 0.32, 0.18], [0.055, 0.04, 0.028, 0.02], n, r=r)
        cl = dsp.highpass(r.standard_normal(k), 3000, 2) * np.exp(-tk / 0.001)
        y[:k] += 0.9 * _unit(cl)
        # a touch of the head ringing along
        y += 0.12 * dsp.modal([660.0 * (1.0 if head == 0 else 1.122)], [1.0], [0.1], n, r=r)
        y = dsp.highpass(y, 400, 2)
        return _unit(y) * vel * 0.75
    f0 = 440.0 * (1.0 if head == 0 else 1.1225) * r.uniform(0.995, 1.005)
    ratios = np.array([1.0, 1.594, 2.136, 2.296, 2.653, 2.918, 3.156, 3.501])
    amps = np.array([1.0, 0.75, 0.55, 0.5, 0.35, 0.3, 0.22, 0.15]) * r.uniform(0.8, 1.2, 8)
    amps *= (0.5 + 0.5 * min(vel, 1.0)) ** (np.arange(8) * 0.3)
    t60s = np.array([0.22, 0.13, 0.1, 0.09, 0.07, 0.06, 0.05, 0.045])
    fmul = 1.0 + 0.06 * vel * np.exp(-t / 0.01)
    y = dsp.modal(f0 * ratios, amps, t60s, n, r=r, fdrift=fmul)
    crack = dsp.highpass(r.standard_normal(k), 2500, 2) * np.exp(-tk / 0.0012)
    slap = dsp.bandpass(r.standard_normal(k), 900, 6000, 2) * np.exp(-tk / 0.005)
    y[:k] += (0.8 * vel) * _unit(crack) + 0.6 * _unit(slap)
    y = dsp.highpass(y, 160, 2)
    y = dsp.peq(y, 2800, 2.5, 1.0)
    return _unit(y) * min(vel, 1.1) ** 1.1


def _jiegu_final(vel, r):
    """the big climactic stroke: both sticks on both heads at once (a tiny flam), the drum rings out,
    the stand and floorboards boom in the hall."""
    dur = 2.0
    n = n_of(dur)
    t = t_axis(n)
    y = np.zeros(n)
    for j, (h, dl) in enumerate([(0, 0.0), (1, 0.006)]):
        f0 = 440.0 * (1.0 if h == 0 else 1.1225)
        ratios = np.array([1.0, 1.594, 2.136, 2.296, 2.653, 2.918, 3.156, 3.501])
        amps = np.array([1.0, 0.8, 0.6, 0.55, 0.4, 0.35, 0.25, 0.2]) * r.uniform(0.85, 1.15, 8)
        t60s = np.array([0.7, 0.4, 0.3, 0.26, 0.2, 0.17, 0.14, 0.12])
        fmul = 1.0 + 0.1 * np.exp(-t / 0.015)
        m = dsp.modal(f0 * ratios, amps, t60s, n, r=r, fdrift=fmul)
        s = n_of(dl)
        y[s:] += m[: n - s] * (1.0 if j == 0 else 0.85)
    k = n_of(0.08)
    tk = t[:k]
    crack = dsp.highpass(r.standard_normal(k), 2200, 2) * np.exp(-tk / 0.0018)
    slap = dsp.bandpass(r.standard_normal(k), 500, 5000, 2) * np.exp(-tk / 0.009)
    y = _unit(y)
    y[:k] += 0.9 * _unit(crack) + 0.7 * _unit(slap)
    # the body + stand + floor boom (makes the small drum sound climactic)
    boom_f = 118.0 * (1.0 + 0.25 * np.exp(-t / 0.03))
    boom = np.sin(TWO_PI * dsp.phase_cycles(boom_f, n)) * np.exp(-t / 0.22) * np.clip(t / 0.002, 0, 1)
    y += 0.65 * boom
    y += 0.25 * dsp.modal([236, 355, 520], [1.0, 0.6, 0.4], [0.4, 0.3, 0.2], n, r=r)
    y = dsp.highpass(y, 45, 2)
    y = dsp.saturate(_unit(y) * 1.3, 0.3)
    y = dsp.fade(y, 0.0, 0.4)
    return _unit(y) * min(vel, 1.1)


def paiban(vel=0.8, r=None):
    """paiban: hardwood slats bound at one end, swung together -> a dry woody 'ka' with a tiny slat rattle"""
    r = _r(r, "paiban", vel)
    n = n_of(0.35)
    t = t_axis(n)
    bar = np.array([1.0, 2.756, 5.404, 8.933])
    y = np.zeros(n)
    f1 = 1020.0 * r.uniform(0.97, 1.03)
    for j, (dl, fm, g) in enumerate([(0.0, 1.0, 1.0), (0.0018, 1.07, 0.75), (0.0041, 0.93, 0.45)]):
        dl = dl * r.uniform(0.7, 1.3)
        m = dsp.modal(f1 * fm * bar, [1.0, 0.45, 0.2, 0.08], [0.07, 0.035, 0.02, 0.012], n, r=r)
        s = n_of(dl)
        y[s:] += g * m[: n - s]
    k = n_of(0.02)
    click = dsp.highpass(r.standard_normal(k), 3500, 2) * np.exp(-t[:k] / 0.0008)
    knock = dsp.bandpass(r.standard_normal(k), 700, 5000, 2) * np.exp(-t[:k] / 0.004)
    y = _unit(y)
    y[:k] += 1.0 * _unit(click) + 0.9 * _unit(knock)
    y = dsp.peq(y, 600, -5, 0.7)
    y = dsp.highpass(y, 250, 2)
    return _unit(y) * vel


# ======================================================================================  winds
def dizi(freq, dur, vel=0.6, r=None, tech=None, grace=None, vib_depth=22.0, membrane=1.0):
    """di with the dimo membrane. grace: list of (cents, dur_s) ornaments played before settling on the note
    (quick upper-neighbour da yin / die yin).  tech: None | long (strains toward the end) | squeak."""
    r = _r(r, "dizi", freq, dur, tech)
    if tech == "squeak":
        return dizi_squeak(freq, dur, vel, r)
    long_ = tech == "long"
    rel = 0.03 if long_ else 0.1
    n = n_of(dur + rel + 0.04)
    t = t_axis(n)
    # ---------------- pitch (cents)
    c = -18.0 * np.exp(-t / 0.025)
    if grace:
        pos = 0.0
        for gc, gd in grace:
            a, b = n_of(pos), n_of(pos + gd)
            c[a:b] += gc
            pos += gd
        # lift of the finger: 6 ms glide from the last grace onto the note
        b = n_of(pos)
        m = n_of(0.006)
        c[b:b + m] += grace[-1][0] * np.linspace(1, 0, len(c[b:b + m]))
    vr = 5.6 * (1.0 + 0.04 * dsp.ctrl_noise(n, r, 0.8))
    vd = vib_depth * r.uniform(0.8, 1.2)
    strain = np.zeros(n)
    if long_:
        strain = dsp.smoothstep((t - 0.9) / max(dur - 0.9, 0.1)) * (t < dur + 0.01)
        vr = vr * (1.0 + 0.35 * strain)
        vd = vd * (1.0 + 1.3 * strain)
    if dur > 0.3 or long_:
        c += vd * dsp.smoothstep((t - 0.18) / 0.3) * np.sin(TWO_PI * dsp.phase_cycles(vr, n, r.uniform()))
    c += 3.0 * dsp.ctrl_noise(n, r, 1.0)
    if long_:
        c += -55.0 * strain ** 1.6 + 14.0 * strain * dsp.ctrl_noise(n, r, 9.0)
    f = freq * dsp.cents2ratio(c)
    # ---------------- amplitude
    att = 0.02 + 0.02 * (1.0 - vel)
    env = dsp.env_points([(0, 0), (att, 1.0), (att + 0.06, 0.86), (max(dur, att + 0.07), 0.9),
                          (dur + rel, 0.0), (n / SR, 0.0)], n, "cos")
    env *= 1.0 + 0.05 * dsp.ctrl_noise(n, r, 3.0)
    if long_:
        # puffed cheeks: a swell, then the breath runs out -> trembling, fading, gasping
        env *= (1.0 + 0.25 * np.sin(np.pi * np.clip(strain * 1.3, 0, 1))) * (1.0 - 0.45 * strain ** 2.5)
        env *= 1.0 - 0.4 * strain ** 1.5 * (0.5 + 0.5 * np.sin(TWO_PI * dsp.phase_cycles(8.5 + 3.0 * strain, n)))
    # ---------------- harmonic body
    ph = dsp.phase_cycles(f, n)
    K = int(max(3, min(10, 9500.0 / freq)))
    slope = 1.9 - 0.5 * vel
    tone = np.zeros(n)
    for k in range(1, K + 1):
        ak = k ** (-slope) * (0.6 if k % 2 == 0 else 1.0) * r.uniform(0.85, 1.15)
        jit = 1.0 + 0.08 * dsp.ctrl_noise(n, r, 25.0 + 4 * k)
        tone += ak * jit * np.sin(TWO_PI * (k * ph + r.uniform()))
    tone = _unit(tone)
    # ---------------- the dimo membrane: bright rasp locked to the waveform
    buzz = np.tanh(3.5 * tone) - 0.8 * tone
    buzz = dsp.bandpass(buzz, 2300, 8500, 2) * (1.0 + 0.3 * dsp.ctrl_noise(n, r, 60.0))
    gate = (0.5 + 0.5 * np.cos(TWO_PI * ph)) ** 4
    sync = dsp.bandpass(r.standard_normal(n) * gate, 2800, 9000, 2)
    # ---------------- breath
    air = dsp.bandpass(r.standard_normal(n), 1200, 7500, 2)
    nl = 0.05 + 0.06 * (1.0 - vel) + (0.25 * strain if long_ else 0.0)
    y = env * (tone + membrane * (0.30 * _unit(buzz) + 0.10 * _unit(sync)) + nl * _unit(air) * 1.6)
    # tongued chiff
    kc = n_of(0.035)
    ch = dsp.bandpass(r.standard_normal(kc), 1000, 5000, 2) * np.exp(-t[:kc] / 0.008)
    y[:kc] += (0.10 + 0.1 * vel) * _unit(ch)
    y = dsp.highpass(y, 250, 2)
    y = dsp.peq(y, 3200, 2.5, 1.2)
    y = dsp.fade(y, 0.002, 0.015)
    return _unit(y) * vel


def dizi_squeak(freq, dur, vel=0.7, r=None):
    """the flute cracks: a split tone, then a thin squealing overblown whistle that overshoots, wobbles and
    deflates."""
    r = _r(r, "dizi_squeak", freq)
    L = dur + 0.12
    n = n_of(L)
    t = t_axis(n)
    c = (140.0 * dsp.smoothstep(t / 0.03) - 60.0 * dsp.smoothstep((t - 0.05) / 0.08)
         + 45.0 * dsp.smoothstep((t - 0.06) / 0.05) * np.sin(TWO_PI * 11.5 * t)
         - 420.0 * dsp.smoothstep((t - dur * 0.7) / (dur * 0.45)))
    f = freq * dsp.cents2ratio(c)
    ph = dsp.phase_cycles(f, n)
    tone = np.sin(TWO_PI * ph) + 0.12 * np.sin(TWO_PI * 2 * ph) + 0.05 * np.sin(TWO_PI * 3 * ph)
    env = dsp.env_points([(0, 0), (0.006, 1.0), (dur * 0.6, 0.9), (dur, 0.55), (L, 0.0)], n, "cos")
    # the crack: a split between the low note and the squeak for a few ms + a burst of hissing air
    kc = n_of(0.04)
    low = np.sin(TWO_PI * dsp.phase_cycles(freq * 2 ** (-6 / 12.0), kc)) * np.exp(-t[:kc] / 0.012)
    hiss = dsp.bandpass(r.standard_normal(n), 3000, 10000, 2) * env * (0.35 + 0.65 * np.exp(-t / 0.03))
    rasp = dsp.bandpass(np.sign(tone) * np.abs(tone) ** 0.3, 3000, 9000, 2)
    y = env * (tone + 0.15 * _unit(rasp)) + 0.22 * _unit(hiss)
    y[:kc] += 0.5 * low
    y = dsp.highpass(y, 300, 2)
    y = dsp.fade(y, 0.001, 0.02)
    return _unit(y) * vel


def bili(freq, dur, vel=0.45, r=None):
    """bili (guan): cylindrical-bore double reed -> nasal, reedy; scoops into notes, wide vibrato"""
    r = _r(r, "bili", freq, dur)
    rel = 0.14
    n = n_of(dur + rel + 0.04)
    t = t_axis(n)
    c = -70.0 * (1.0 - dsp.smoothstep(t / 0.12))
    c += 18.0 * dsp.smoothstep((t - 0.3) / 0.4) * np.sin(TWO_PI * dsp.phase_cycles(5.0, n, r.uniform()))
    c += 5.0 * dsp.ctrl_noise(n, r, 1.2)
    f = freq * dsp.cents2ratio(c)
    src = 0.6 * dsp.osc_saw(f, n, r.uniform()) + 0.5 * dsp.osc_square(f, n, r.uniform(), pw=0.22)
    src = dsp.lowpass(src, 4200, 2)
    y = (0.35 * dsp.biquad(src, "bp", 480, q=2.0) + 1.0 * dsp.biquad(src, "bp", 1150, q=4.0)
         + 0.55 * dsp.biquad(src, "bp", 2600, q=5.0) + 0.12 * src)
    ph = dsp.phase_cycles(f, n)
    gate = (0.5 + 0.5 * np.cos(TWO_PI * ph)) ** 3
    reed = dsp.bandpass(r.standard_normal(n) * gate, 900, 4000, 2)
    env = dsp.env_points([(0, 0), (0.05, 0.9), (0.25, 0.85), (max(dur * 0.7, 0.26), 1.0), (dur, 0.9), (dur + rel, 0),
                          (n / SR, 0)], n, "cos")
    env *= 1.0 + 0.05 * dsp.ctrl_noise(n, r, 4.0)
    y = env * (_unit(y) + 0.12 * _unit(reed))
    y = dsp.highpass(y, 90, 2)
    y = dsp.fade(y, 0.003, 0.02)
    return _unit(y) * vel


def sheng(freqs, dur, vel=0.3, r=None, attack=0.35, release=0.5, width=0.6):
    """sheng pad: pairs of slightly beating free-reed pipes; soft swell; stereo"""
    r = _r(r, "sheng", tuple(np.round(freqs, 2)), dur)
    n = n_of(dur + release + 0.05)
    t = t_axis(n)
    out = np.zeros((2, n))
    for i, f0 in enumerate(freqs):
        for p in range(2):
            det = (-4.0 if p == 0 else 4.0) + r.normal(0, 1.5)
            c = det + 3.0 * dsp.ctrl_noise(n, r, 0.7)
            f = f0 * dsp.cents2ratio(c)
            ph = dsp.phase_cycles(f, n, r.uniform())
            K = int(max(2, min(10, 6000.0 / f0)))
            v = np.zeros(n)
            for k in range(1, K + 1):
                v += (k ** -1.25) * (1.0 if k % 2 else 0.7) * np.sin(TWO_PI * k * ph)
            e = dsp.env_points([(0, 0), (attack * r.uniform(0.85, 1.2), 1.0), (dur, 0.95), (dur + release, 0),
                                (n / SR, 0)], n, "cos")
            e *= 1.0 + 0.04 * dsp.ctrl_noise(n, r, 2.5)
            gl, gr = dsp.pan_gains((-1 if (i + p) % 2 else 1) * width * r.uniform(0.3, 1.0))
            out[0] += v * e * gl
            out[1] += v * e * gr
    out = dsp.lowpass(out, 3200, 2)
    out = dsp.eq_chain(out, [("peak", 1150, 2.0, 1.0), ("hp", 120, 0.0, 0.7)])
    return _unit(out) * vel


# ======================================================================================  bell
_BELL = [  # ratio (to the strike tone), amp, t60, doublet split (Hz); upper partials kept in D (A, D, E, A)
    (0.5, 1.0, 30.0, 0.3), (1.0, 0.85, 20.0, 0.6), (1.5, 0.22, 9.0, 1.0), (2.0, 0.34, 8.0, 1.3),
    (2.245, 0.10, 4.5, 1.5), (3.0, 0.11, 4.0, 1.9), (4.22, 0.07, 2.2, 2.6), (5.39, 0.045, 1.4, 3.2),
    (6.93, 0.03, 0.9, 4.0), (8.71, 0.018, 0.55, 5.0),
]


def bell(hum_freq, dur=8.0, vel=0.8, r=None, bright=0.55):
    """temple bell / bowl, stereo. hum_freq = the long hum (the strike tone is an octave above)."""
    r = _r(r, "bell", hum_freq, vel)
    f0 = 2.0 * hum_freq
    n = n_of(dur)
    t = t_axis(n)
    L = np.zeros(n)
    R = np.zeros(n)
    for (ratio, amp, t60, split) in _BELL:
        f = f0 * ratio * r.uniform(0.998, 1.002)
        if f > 16000:
            continue
        a = amp * (0.6 + 0.8 * bright) ** (np.log2(ratio + 1.0)) * r.uniform(0.85, 1.15)
        e = np.exp(-LN1000 * t / (t60 * (0.85 + 0.3 * r.uniform())))
        ph1, ph2 = r.uniform(0, 1, 2)
        s1 = a * e * np.sin(TWO_PI * (f * t + ph1))
        s2 = a * r.uniform(0.6, 0.95) * e * np.sin(TWO_PI * ((f + split) * t + ph2))
        L += 0.75 * s1 + 0.35 * s2
        R += 0.35 * s1 + 0.75 * s2
    k = n_of(0.6)
    fr = r.uniform(900, 7000, 20)
    cl_l = dsp.modal(fr, r.uniform(0.02, 0.05, 20), r.uniform(0.08, 0.3, 20), k, r=r)
    cl_r = dsp.modal(fr * r.uniform(0.995, 1.005, 20), r.uniform(0.02, 0.05, 20), r.uniform(0.08, 0.3, 20), k, r=r)
    th = dsp.lowpass(r.standard_normal(k), 450, 2) * np.exp(-t[:k] / 0.022)
    th = 0.3 * vel * _unit(th)
    L[:k] += cl_l * bright + th
    R[:k] += cl_r * bright + th
    out = np.vstack([L, R])
    out = dsp.fade(out, 0.0015, min(1.5, dur * 0.15))
    return _unit(out) * vel
