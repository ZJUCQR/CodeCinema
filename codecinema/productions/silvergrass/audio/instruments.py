"""
instruments.py -- synthesized, Japanese-flavoured instruments for the original score of Duel in the Silver Grass.

Every function returns float64 audio at dsp.SR whose first sample is the note onset (anchor 0)
unless stated otherwise.  Mono instruments return shape (n,), ensemble instruments (strings,
choir, bell, metal_swell) return stereo (2, n).  Levels: peak ~ velocity (0..1) so the score
can balance with plain gains.  All randomness comes from the Generator `r` -> deterministic.

    odaiko      big barrel drum: pitch-dropping air-loaded membrane modes, second head, shell,
                bachi slap/click, air thump
    shime       high-tension rope drum (bright crack, short ring); rim=True -> wooden 'ka'
    hyoshigi    two hardwood clappers (free-bar modes, beating pair, contact click)
    shakuhachi  harmonic partials with per-partial breath jitter, pitched + broadband breath noise,
                delayed vibrato / yuri, meri/kari bends, atari grace, chiff, muraiki blast, fall
    koto        Karplus-Strong, bright tsume pluck, tension pitch settle, oshide press-bends, body EQ
    shamisen    Karplus-Strong with in-loop rectifying 'sawari' buzz, bachi skin slap, nasal body
    strings     low string ensemble: detuned PolyBLEP saws, per-voice vibrato, lowpass + body EQ,
                bow noise; modes sustain / swell / sfz / tremolo / spiccato
    choir       'ah'/'oh' formant-filtered glottal sources, chorus of voices, breath
    temple_bell modal inharmonic partials as beating doublets, very long decay, wooden striker thud
    heartbeat   lub-dub
    metal_swell reversed gong cloud + rising noise -> crescendo that ENDS at the returned anchor
"""

import numpy as np

import dsp
from dsp import SR, n_of, t_axis, LN1000, TWO_PI

NYQ_SAFE = 0.45 * SR


def _r(r, *keys):
    return r if r is not None else dsp.rng("inst", *keys)


# ======================================================================================  drums
def odaiko(vel=0.8, r=None, size=1.0, f0=None, dur=None, tone=0.5):
    """big barrel drum. size 1.0 ~ large o-daiko (f0 ~ 56 Hz), 0.65 ~ nagado-daiko (f0 ~ 80 Hz).
    tone 0..1 = darker..brighter (stick hardness)."""
    r = _r(r, "odaiko", vel, size)
    vel = float(np.clip(vel, 0.02, 1.2))
    f0 = f0 or (56.0 / size ** 0.85) * r.uniform(0.985, 1.015)
    dur = dur or (1.6 + 1.6 * size) * (0.65 + 0.35 * min(vel, 1.0))
    n = n_of(dur)
    t = t_axis(n)
    drop = (0.16 + 0.34 * min(vel, 1.1)) * r.uniform(0.9, 1.1)
    fmul = 1.0 + drop * np.exp(-t / 0.042) + 0.035 * vel * np.exp(-t / 0.35)
    ratios = np.array([1.0, 1.505, 1.985, 2.44, 2.905, 3.37, 3.83, 4.29, 4.74, 5.2])
    amps = np.array([1.0, 0.58, 0.42, 0.27, 0.19, 0.13, 0.09, 0.06, 0.04, 0.03])
    t60s = np.array([2.7, 1.55, 1.05, 0.78, 0.58, 0.44, 0.34, 0.27, 0.22, 0.18]) * (0.7 + 0.3 * size)
    b = 0.3 + 0.55 * min(vel, 1.0) + 0.3 * (tone - 0.5)
    amps = amps * b ** (np.arange(len(amps)) * 0.45)
    amps *= r.uniform(0.85, 1.15, len(amps))
    head1 = dsp.modal(f0 * ratios, amps, t60s, n, r=r, fdrift=fmul)
    # second (resonant) head: slightly detuned, delayed by the shell transit, weaker -> beating depth
    d2 = n_of(0.0016 * size)
    head2 = dsp.modal(f0 * ratios * 1.013, amps * 0.32, t60s * 1.1, n, r=r, fdrift=1.0 + 0.5 * (fmul - 1.0))
    head2 = np.concatenate([np.zeros(d2), head2[: n - d2]])
    # shell (wooden barrel) modes
    shell = dsp.modal(np.array([168, 243, 331, 462, 610, 820]) * r.uniform(0.97, 1.03), [0.2, 0.17, 0.13, 0.09, 0.06, 0.04],
                      [0.2, 0.16, 0.13, 0.1, 0.08, 0.06], n, r=r)
    # bachi impact: click + slap + air push
    k = min(n, n_of(0.12))
    tk = t[:k]
    click = dsp.highpass(r.standard_normal(k), 1800, 2) * np.exp(-tk / 0.0022)
    slap = dsp.bandpass(r.standard_normal(k), 280, 1900 + 1600 * tone, 2) * np.exp(-tk / (0.012 + 0.01 * size))
    air = dsp.lowpass(r.standard_normal(k), 140, 2) * np.exp(-tk / 0.05)
    y = head1 + 0.8 * head2 + shell * (1.0 + 0.8 * vel)
    y[:k] += (0.45 * vel ** 1.5) * click / (dsp.peak(click) + 1e-9) \
        + (0.85 * vel) * slap / (dsp.peak(slap) + 1e-9) \
        + (0.45 * vel) * air / (dsp.peak(air) + 1e-9)
    y = dsp.highpass(y, 28.0, 2)
    y = dsp.normalize(y, 1.0)
    if vel > 0.75:
        y = dsp.saturate(y * (1.0 + (vel - 0.75) * 1.6), 0.35)
        y = dsp.normalize(y, 1.0)
    y = dsp.fade(y, 0.0, min(0.3, dur * 0.2))
    return y * min(vel, 1.1) ** 1.15


def shime(vel=0.7, r=None, f0=None, rim=False, dur=0.5):
    """shime-daiko: tight, high, bright 'ten'. rim=True gives the wooden rim/shell 'ka'."""
    r = _r(r, "shime", vel)
    vel = float(np.clip(vel, 0.02, 1.2))
    n = n_of(dur)
    t = t_axis(n)
    k = min(n, n_of(0.06))
    tk = t[:k]
    if rim:
        y = dsp.modal(np.array([1720, 2890, 4630, 6210]) * r.uniform(0.97, 1.03),
                      [1.0, 0.6, 0.35, 0.2], [0.07, 0.05, 0.035, 0.025], n, r=r)
        cl = dsp.highpass(r.standard_normal(k), 3000, 2) * np.exp(-tk / 0.0012)
        y[:k] += 0.8 * cl / (dsp.peak(cl) + 1e-9)
        return dsp.normalize(y, 1.0) * vel * 0.8
    f0 = f0 or 440.0 * r.uniform(0.994, 1.006)          # A4: in the key (in-scale on D), one drum = one pitch
    ratios = np.array([1.0, 1.594, 2.136, 2.296, 2.653, 2.918, 3.156, 3.501, 3.600, 4.060])
    amps = np.array([1.0, 0.7, 0.55, 0.45, 0.35, 0.3, 0.22, 0.18, 0.15, 0.1]) * r.uniform(0.8, 1.2, 10)
    b = 0.45 + 0.55 * min(vel, 1.0)
    amps = amps * b ** (np.arange(10) * 0.25)
    t60s = np.array([0.32, 0.2, 0.15, 0.14, 0.11, 0.1, 0.085, 0.07, 0.065, 0.05])
    fmul = 1.0 + 0.07 * vel * np.exp(-t / 0.012)
    y = dsp.modal(f0 * ratios, amps, t60s, n, r=r, fdrift=fmul)
    crack = dsp.highpass(r.standard_normal(k), 2500, 2) * np.exp(-tk / 0.0016)
    slap = dsp.bandpass(r.standard_normal(k), 900, 5500, 2) * np.exp(-tk / 0.006)
    y[:k] += (0.9 * vel) * crack / (dsp.peak(crack) + 1e-9) + 0.7 * slap / (dsp.peak(slap) + 1e-9)
    y = dsp.highpass(y, 120, 2)
    return dsp.normalize(y, 1.0) * min(vel, 1.1) ** 1.1


def hyoshigi(vel=0.8, r=None, flam=None):
    """two hardwood clappers struck together: piercing woody 'KAN'"""
    r = _r(r, "hyoshigi", vel)
    n = n_of(0.45)
    t = t_axis(n)
    f1 = 1180.0 * r.uniform(0.97, 1.03)
    bar = np.array([1.0, 2.756, 5.404, 8.933])
    a = dsp.modal(f1 * bar, [1.0, 0.5, 0.22, 0.09], [0.15, 0.065, 0.035, 0.02], n, r=r)
    b = dsp.modal(f1 * 1.064 * bar, [0.85, 0.45, 0.2, 0.08], [0.14, 0.06, 0.03, 0.02], n, r=r)
    fl = n_of(r.uniform(0.0, 0.0012) if flam is None else flam)
    b = np.concatenate([np.zeros(fl), b[: n - fl]])
    k = n_of(0.02)
    click = dsp.highpass(r.standard_normal(k), 3500, 2) * np.exp(-t[:k] / 0.0007)
    knock = dsp.bandpass(r.standard_normal(k), 900, 6000, 2) * np.exp(-t[:k] / 0.004)
    y = a + b
    y[:k] += 1.2 * click / (dsp.peak(click) + 1e-9) + 0.9 * knock / (dsp.peak(knock) + 1e-9)
    y = dsp.peq(y, 600, -6, 0.7)
    return dsp.normalize(y, 1.0) * vel


# ======================================================================================  winds
def shakuhachi(freq, dur, vel=0.6, r=None, attack="meri", bend=-90.0, bend_time=0.14,
               vib_depth=16.0, vib_rate=5.2, vib_delay=0.45, yuri=0.0, breath=1.0, muraiki=0.0,
               atari=None, release=0.14, fall=0.0, swell=0.25, flutter=0.0, glide_to=None, bright=0.0):
    """end-blown bamboo flute.
    attack : 'meri' (scoop up from below by `bend` cents) | 'kari' (settle from above) | 'plain'
    atari  : optional grace-note offset in cents (short tap above the note at the onset)
    yuri   : 0..1 slow deep head-shake vibrato;  flutter: 0..1 tonguing flutter (tamane-like)
    muraiki: 0..1 explosive breath at the attack;  fall: cents of 'otoshi' at the end
    glide_to: optional (t_start_rel, target_freq) portamento inside the note
    bright : 0..1 flatter harmonic slope (more upper partials at the same level) -- presence without volume"""
    r = _r(r, "shaku", freq, dur)
    tail = release + 0.08
    n = n_of(dur + tail)
    t = t_axis(n)
    # ---------------- pitch (cents)
    c = np.zeros(n)
    if attack == "meri":
        c += bend * np.exp(-t / bend_time)
    elif attack == "kari":
        c += abs(bend) * 0.6 * np.exp(-t / (bend_time * 0.7))
    if atari:
        ga = n_of(r.uniform(0.035, 0.06))
        c[:ga] += atari
        c[ga: ga + n_of(0.02)] += atari * np.linspace(1, 0, len(c[ga: ga + n_of(0.02)]))
    vib_env = dsp.smoothstep((t - vib_delay) / 0.5) * (t < dur + 0.05)
    vr = vib_rate * (1.0 + 0.07 * dsp.lp_noise(n, r, 0.7))
    c += vib_depth * vib_env * np.sin(TWO_PI * dsp.phase_cycles(vr, n))
    if yuri > 0:
        c += 45.0 * yuri * dsp.smoothstep((t - 0.25) / 0.6) * np.sin(TWO_PI * dsp.phase_cycles(3.1, n, r.uniform()))
    c += 5.0 * dsp.lp_noise(n, r, 0.9)
    if fall:
        c -= fall * dsp.smoothstep((t - (dur - 0.18)) / 0.28)
    if glide_to is not None:
        tg, fg = glide_to
        c += 1200 * np.log2(fg / freq) * dsp.smoothstep((t - tg) / 0.12)
    f = freq * dsp.cents2ratio(c)
    # ---------------- amplitude
    att = 0.045 + 0.09 * (1.0 - vel) + (0.05 if attack == "meri" else 0.0)
    env = dsp.env_points([(0, 0), (att, 0.75), (att + 0.12, 0.7), (max(dur * 0.5, att + 0.13), 0.7 + 0.3 * swell),
                          (max(dur, att + 0.14), 0.75 + 0.1 * swell), (dur + release, 0.0), (n / SR, 0.0)], n, "cos")
    env *= 1.0 + 0.07 * dsp.lp_noise(n, r, 3.5)          # komibuki breath pulses
    if flutter > 0:
        env *= 1.0 - 0.45 * flutter * (0.5 + 0.5 * np.sin(TWO_PI * dsp.phase_cycles(17.0 + 3 * r.uniform(), n)))
    # ---------------- harmonic body
    ph = dsp.phase_cycles(f, n)
    b = 0.25 + 0.6 * vel + 0.3 * muraiki
    slope = max(0.9, 2.9 - 1.7 * b - 0.9 * bright)
    K = int(min(14, 9000.0 / freq))
    tone = np.zeros(n)
    for k in range(1, K + 1):
        ak = k ** (-slope) * (0.75 if k % 2 == 0 else 1.0) * r.uniform(0.85, 1.15)
        if k == 2:
            ak *= 1.05   # octave partial fairly strong in the otsu register
        jit = 1.0 + (0.18 + 0.25 * (1 - vel)) * dsp.lp_noise(n, r, 35.0 + 5 * k) * min(1.0, 0.4 + 0.15 * k)
        tone += ak * jit * np.sin(TWO_PI * (k * ph + r.uniform()))
    # ---------------- breath: pitched (comb-like via period-synchronous gating) + broadband air
    wn = r.standard_normal(n)
    gate = (0.5 + 0.5 * np.cos(TWO_PI * ph)) ** 3
    pitched = dsp.bandpass(wn * gate, 300, 4500, 2)
    air = dsp.lowpass(dsp.bandpass(r.standard_normal(n), 1200, 6000, 2), 7000, 2)
    nl = breath * (0.07 + 0.15 * (1.0 - vel))
    nl = nl * (1.0 + 2.5 * muraiki * np.exp(-t / 0.35))
    y = env * (tone / (K ** 0.25) + nl * (1.1 * pitched + 0.35 * air))
    # chiff at onset
    k_ = n_of(0.05)
    ch = dsp.bandpass(r.standard_normal(k_), 1200, 4200, 2) * np.exp(-t[:k_] / 0.012)
    y[:k_] += (0.08 + 0.12 * vel) * ch / (dsp.peak(ch) + 1e-9)
    if muraiki > 0:
        km = n_of(0.35)
        blast = r.standard_normal(km) * np.exp(-t[:km] / 0.09) * np.clip(t[:km] / 0.01, 0, 1)
        blast = dsp.tv_biquad(blast, "lp", np.geomspace(9000, 1500, km), 0.8)
        y[:km] += 0.6 * muraiki * blast / (dsp.peak(blast) + 1e-9)
    y = dsp.highpass(y, 180, 2)
    y = dsp.peq(y, 750, 2.0, 0.8)
    y = dsp.fade(y, 0.002, 0.02)
    return dsp.normalize(y, 1.0) * vel


# ======================================================================================  plucked
def koto(freq, dur, vel=0.7, r=None, bright=0.6, press=None, t60=None, settle=None, damp_at=None):
    """13-string zither. press: list of (t_rel, cents, glide_s) oshide press-bends (additive).
    damp_at: time (s) at which the string is muted by the hand."""
    r = _r(r, "koto", freq, dur)
    n = n_of(dur)
    t = t_axis(n)
    t60 = t60 or float(np.clip(4.2 * (220.0 / freq) ** 0.45, 1.0, 6.0))
    c = (settle if settle is not None else (6.0 + 16.0 * vel)) * np.exp(-t / 0.075)
    if press:
        for (tp, cents, gl) in press:
            c = c + cents * dsp.smoothstep((t - tp) / max(gl, 1e-3))
    N = max(2, int(SR / freq))
    # the tsume pluck, built additively over one period: harmonic n ~ |sin(n pi b)| / n^p (b = pluck point,
    # p = 1.42 - 0.8 bright: a sharp ivory pick is brighter than a finger's 1/n^2) with small random weights and
    # phases, + a little scrape noise.  (A pure noise burst gave every note random harmonic weights: some notes had
    # a 2nd / 3rd harmonic 10 dB over the fundamental.)
    kk = np.arange(N) / N
    b = float(np.clip(0.18 + r.uniform(-0.02, 0.02), 0.1, 0.4))
    p = 1.42 - 0.8 * float(np.clip(bright, 0.0, 1.0))
    nh = int(max(1, min(60, 0.45 * SR / freq)))
    hn = np.arange(1, nh + 1)
    amp = (np.abs(np.sin(hn * np.pi * b)) + 0.08) / hn ** p * r.uniform(0.8, 1.2, nh)
    ph = r.uniform(-0.25, 0.25, nh)
    exc = (amp[:, None] * np.sin(2 * np.pi * (hn[:, None] * kk[None, :] + ph[:, None]))).sum(axis=0)
    scr = r.uniform(-1, 1, N)
    exc = exc / (dsp.peak(exc) + 1e-9) + 0.1 * (scr - scr.mean())
    exc = dsp.lowpass(np.concatenate([exc, exc]), 2200 + 7000 * vel * bright, 2)[N:]      # periodic filtering
    y = dsp.karplus_strong(freq, dur, r, t60=t60, brightness=0.42 + 0.34 * bright + 0.06 * vel,
                           pick_pos=0.0, exc=exc, cents=c,
                           damp_after=(damp_at, 0.08) if damp_at else None)
    k = n_of(0.006)
    click = dsp.highpass(r.standard_normal(k), 2500, 2) * np.exp(-t[:k] / 0.0009)
    y[:k] += 0.25 * vel * click / (dsp.peak(click) + 1e-9) * dsp.peak(y[: n_of(0.02)] + 1e-9)
    y = dsp.eq_chain(y, [("peak", 190, 3.0, 1.2), ("peak", 430, 2.0, 1.4), ("peak", 1150, -1.5, 1.0),
                         ("peak", 2200, -1.5, 0.8), ("hp", 60, 0.0, 0.7)])
    y = dsp.fade(y, 0.0, min(0.08, dur * 0.2))
    return dsp.normalize(y, 1.0) * vel * 0.74          # -2.6 dB: the shaped pluck is denser than the old noise pluck


def _sawari(amount):
    """scale-invariant, energy-neutral in-loop buzz: each period the string's feedback block gets a
    rectified (even-harmonic rich) component added, then is renormalised to the same energy, so the
    decay stays governed by the loop gain while energy keeps being pushed into upper partials."""
    def f(fb, k):
        rect = np.abs(fb)
        rect -= rect.mean()
        out = fb + amount * rect
        e0 = float(np.dot(fb, fb))
        e1 = float(np.dot(out, out))
        return out * np.sqrt(e0 / (e1 + 1e-30)) if e1 > 0 else out
    return f


def shamisen(freq, dur, vel=0.8, r=None, sawari=0.55, t60=None, hajiki=False, slide=None):
    """three-string lute with skin body: sawari buzz, bachi strikes skin. hajiki = soft left-hand pluck.
    slide: optional (t_rel, cents, glide) suri slide."""
    r = _r(r, "shamisen", freq, dur)
    n = n_of(dur)
    t = t_axis(n)
    t60 = t60 or float(np.clip(1.9 * (200.0 / freq) ** 0.35, 0.7, 3.0))
    c = (4.0 + 10.0 * vel) * np.exp(-t / 0.05)
    if slide:
        tp, cents, gl = slide
        c = c + cents * dsp.smoothstep((t - tp) / max(gl, 1e-3))
    N = max(2, int(SR / freq))
    exc = r.uniform(-1, 1, N)
    if hajiki:
        exc = dsp.lowpass(exc, 1500, 2)
        vel *= 0.6
    else:
        exc[: max(2, N // 10)] += 2.0 * r.choice([-1, 1])   # sharp bachi edge
    y = dsp.karplus_strong(freq, dur, r, t60=t60, brightness=0.45 + 0.25 * vel, pick_pos=0.09,
                           exc=exc, cents=c, nonlin=_sawari(sawari))
    y = dsp.dc_block(y, 30.0)
    y = dsp.normalize(y, 1.0)
    if not hajiki:
        k = n_of(0.12)
        skin = dsp.modal([205, 330, 468, 610], [1.0, 0.6, 0.4, 0.25], [0.09, 0.07, 0.05, 0.04], k, r=r)
        snap = dsp.bandpass(r.standard_normal(k), 1200, 4500, 2) * np.exp(-t[:k] / 0.005)
        y[:k] += 0.55 * vel * skin / (dsp.peak(skin) + 1e-9) + 0.6 * vel * snap / (dsp.peak(snap) + 1e-9)
    y = dsp.eq_chain(y, [("peak", 1250, 2.0, 1.2), ("peak", 3100, -1.0, 1.2), ("peak", 350, -2.0, 1.0),
                         ("hp", 90, 0.0, 0.7)])
    y = dsp.fade(y, 0.0, min(0.06, dur * 0.2))
    return dsp.normalize(y, 1.0) * vel


# ======================================================================================  strings / choir
_BODY_CACHE = {}


def _string_body(kind, variant):
    """fixed pseudo-random body-resonance filter of one string desk: the known low modes (air A0, main wood
    modes), the 'bridge hill' and a dozen narrow random peaks / dips.  As vibrato sweeps every harmonic across
    these resonances its amplitude flickers -- the shimmer that separates real strings from a static synth pad."""
    key = (kind, variant)
    if key in _BODY_CACHE:
        return _BODY_CACHE[key]
    r = dsp.rng("string_body", kind, variant)
    if kind == "low":        # cellos + basses
        fixed = [(98.0, 4.0, 2.5), (196.0, 3.0, 3.0), (410.0, 2.5, 3.0), (1900.0, 3.0, 1.1)]
        lo, hi = 140.0, 4200.0
    else:                    # violas / violins
        fixed = [(280.0, 4.0, 3.0), (460.0, 3.0, 4.0), (560.0, 2.0, 4.0), (2700.0, 4.0, 1.2)]
        lo, hi = 300.0, 6000.0
    bands = [("peak", fc * r.uniform(0.95, 1.05), g, q) for fc, g, q in fixed]
    for f in np.exp(r.uniform(np.log(lo), np.log(hi), 14)):
        bands.append(("peak", float(f), float(r.uniform(-8.0, 6.0)), float(r.uniform(5.0, 14.0))))
    sos = np.vstack([dsp.biquad_sos(k, fc, q, g) for (k, fc, g, q) in bands])
    _BODY_CACHE[key] = sos
    return sos


def strings(pitches, dur, vel=0.6, r=None, mode="sustain", attack=None, release=None, voices=6,
            detune=9.0, vib_depth=11.0, cutoff=None, trem_rate=12.5, swell_to=None, width=0.9, sfz_drop=0.28,
            tone="normal"):
    """string ensemble (stereo). pitches: Hz or list of Hz.
    mode: sustain | swell (pp->vel) | sfz (hard accent then drop and re-swell) | tremolo | spiccato
    tone: 'normal' | 'ponticello' (sul ponticello: bow at the bridge -- weak fundamental, glassy upper partials,
          airy 5-9 kHz sheen instead of body; used for the Act III storm tremolo)
    Players alternate between two desks (stage-left / stage-right), each desk through its own body-resonance
    filter; every player has his own detune, vibrato (rate wander, depth, delayed onset), slow drift + fast bow
    jitter (pitch and level), attack spread and seat.  Brightness follows the dynamic envelope."""
    from scipy import signal as _sig
    r = _r(r, "strings", dur)
    pitches = np.atleast_1d(np.asarray(pitches, dtype=np.float64))
    if mode == "spiccato":
        attack = attack or 0.006
        release = release or 0.09
    attack = attack if attack is not None else (0.35 if mode != "sfz" else 0.012)
    release = release if release is not None else 0.6
    n = n_of(dur + release + 0.05)
    t = t_axis(n)
    gate = dur
    desks = [np.zeros((2, n)), np.zeros((2, n))]
    env_sum = np.zeros(n)
    for pf in pitches:
        for v in range(voices):
            det = r.normal(0.0, detune * 0.5)
            vr = r.uniform(4.6, 6.1) * (1.0 + 0.05 * dsp.ctrl_noise(n, r, 0.8))
            vd = vib_depth * r.uniform(0.6, 1.3)
            vdel = r.uniform(0.15, 0.5)
            cents = det + vd * dsp.smoothstep((t - vdel) / 0.4) * np.sin(TWO_PI * dsp.phase_cycles(vr, n, r.uniform())) \
                + 4.0 * dsp.ctrl_noise(n, r, 0.6) + 1.6 * dsp.ctrl_noise(n, r, 9.0)
            f = pf * dsp.cents2ratio(cents)
            osc = dsp.osc_saw(f, n, r.uniform())
            a_j = attack * r.uniform(0.8, 1.3) + r.uniform(0, 0.02)
            if mode == "spiccato":
                e = dsp.env_points([(0, 0), (a_j, 1.0), (a_j + 0.05, 0.55), (gate, 0.35), (gate + release, 0), (n / SR, 0)], n, "cos")
            elif mode == "sfz":
                e = dsp.env_points([(0, 0), (a_j, 1.0), (a_j + 0.18, sfz_drop), (max(gate * 0.6, a_j + 0.2), max(0.45, sfz_drop)),
                                    (gate, 0.6 if swell_to is None else swell_to), (gate + release, 0), (n / SR, 0)], n, "cos")
            elif mode == "swell":
                e = dsp.env_points([(0, 0.0), (gate * 0.85, 1.0), (gate, 1.0), (gate + release, 0), (n / SR, 0)], n, "cos") ** 1.6
            else:
                e = dsp.env_points([(0, 0), (a_j, 1.0), (gate, 1.0), (gate + release, 0), (n / SR, 0)], n, "cos")
            if mode == "tremolo":
                tr = trem_rate * r.uniform(0.9, 1.1) * (1 + 0.05 * dsp.ctrl_noise(n, r, 1.0))
                phs = dsp.phase_cycles(tr, n, r.uniform())
                e = e * (0.45 + 0.55 * np.abs(np.sin(np.pi * phs)) ** 0.7)
            # slow bow-pressure swell + fast stick-slip jitter
            e = e * np.maximum(0.0, 1.0 + 0.045 * dsp.ctrl_noise(n, r, 2.0) + 0.03 * dsp.ctrl_noise(n, r, 16.0))
            desk = v % 2
            p = r.uniform(0.12, width) * (-1.0 if desk == 0 else 1.0)
            gl, gr = dsp.pan_gains(p)
            sig = osc * e
            desks[desk][0] += sig * gl
            desks[desk][1] += sig * gr
            env_sum += e
    kind = "low" if np.mean(pitches) < 170.0 else "high"
    out = np.zeros((2, n))
    for d in range(2):
        out += _sig.sosfilt(_string_body(kind, d), desks[d], axis=-1)
    # brightness follows the dynamics (crescendo opens the tone, the tail darkens)
    pont = tone == "ponticello"
    fc = cutoff or float(np.clip(1100 + 2600 * vel + 2.0 * np.mean(pitches), 800, 7000))
    fc_hi = fc * (2.2 if pont else 1.3)
    en = env_sum / (env_sum.max() + 1e-12)
    out = dsp.lp_sweep(out, fc_hi * (0.38 + 0.62 * en ** 0.8), n_bank=10, fmin=250.0, fmax=16000.0)
    out = dsp.lowpass(out, min(fc_hi * 1.6, NYQ_SAFE), 2)
    if pont:
        f_lo = float(np.min(pitches))
        out = dsp.highpass(out, f_lo * 2.6, 2)             # the fundamental and 2nd harmonic thinned
        out = dsp.eq_chain(out, [("peak", 1300, -2.0, 1.0), ("peak", 2800, -2.0, 1.0), ("peak", 6500, 3.5, 0.8),
                                 ("highshelf", 11000, -4.0, 0.7), ("hp", 35, 0, 0.7)])
    else:
        out = dsp.eq_chain(out, [("peak", 1300, -1.5, 1.0), ("peak", 2900, 0.5 * vel, 1.2),
                                 ("highshelf", 6500, -6.0, 0.7), ("hp", 35, 0, 0.7)])
    # bow noise (rosin hiss; bursts on every stroke in tremolo)
    bn = dsp.bandpass(r.standard_normal((2, n)), 1500, 7000, 2)
    benv = dsp.env_points([(0, 0), (attack * 0.5 + 0.01, 1.0), (gate, 0.6), (gate + release * 0.5, 0), (n / SR, 0)], n, "cos")
    if mode == "tremolo":
        benv = benv * (0.3 + 0.7 * np.abs(np.sin(np.pi * dsp.phase_cycles(trem_rate, n, r.uniform()))) ** 4)
    bl = (0.012 + (0.05 if mode in ("tremolo", "spiccato", "sfz") else 0.0) + (0.04 if pont else 0.0)) * vel
    out = dsp.normalize(out, 1.0)
    out += bl * bn * benv / (dsp.peak(bn) + 1e-9) * 4.0
    out = dsp.fade(out, 0.0, 0.03)
    return dsp.normalize(out, 1.0) * vel


_FORMANTS = {
    # (freqs, dB, bandwidths) -- classic vocal formant tables
    ("bass", "a"): ([600, 1040, 2250, 2450, 2750], [0, -7, -9, -9, -20], [60, 70, 110, 120, 130]),
    ("tenor", "a"): ([650, 1080, 2650, 2900, 3250], [0, -6, -7, -8, -22], [80, 90, 120, 130, 140]),
    ("alto", "a"): ([800, 1150, 2800, 3500, 4950], [0, -4, -20, -36, -60], [80, 90, 120, 130, 140]),
    ("soprano", "a"): ([800, 1150, 2900, 3900, 4950], [0, -6, -32, -20, -50], [80, 90, 120, 130, 140]),
    ("bass", "o"): ([400, 750, 2400, 2600, 2900], [0, -11, -21, -20, -40], [40, 80, 100, 120, 120]),
    ("tenor", "o"): ([400, 800, 2600, 2800, 3000], [0, -10, -12, -12, -26], [40, 80, 100, 120, 120]),
    ("alto", "o"): ([450, 800, 2830, 3500, 4950], [0, -9, -16, -28, -55], [70, 80, 100, 130, 135]),
    ("soprano", "o"): ([450, 800, 2830, 3800, 4950], [0, -11, -22, -22, -50], [70, 80, 100, 130, 135]),
}


def _voice_type(f):
    return "bass" if f < 160 else ("tenor" if f < 300 else ("alto" if f < 480 else "soprano"))


def _formant_filter(x, vtype, vowel, fscale=1.0):
    """parallel formant bank; fscale shifts all formants (vocal-tract length of a sub-group of singers)"""
    fr, gdb, bw = _FORMANTS[(vtype, vowel)]
    y = np.zeros_like(x)
    for f, g, b in zip(fr, gdb, bw):
        f = f * fscale
        y += dsp.db2lin(g) * dsp.biquad(x, "bp", f, q=f / (b * fscale))
    return y


def choir(pitches, dur, vel=0.6, r=None, vowel="a", voices=6, attack=0.6, release=1.2, breath=0.12,
          width=0.95, swell=0.0, vowel_to=None, morph=(0.25, 0.85)):
    """mixed choir pad. pitches Hz or list; stereo out.
    Every part is sung by four sub-groups of singers with different vocal-tract lengths (formant scale ~0.95..1.05,
    jittered per note) spread across the stage; every singer has his own detune, delayed vibrato, slow drift and
    fast jitter / shimmer.  The source is a saw + narrow pulse with a glottal -12 dB/oct tilt.
    vowel_to: optional second vowel -- the sound opens / closes slowly from `vowel` to `vowel_to` between the
    fractions `morph` of the note (each sub-group a little early or late, so the change blooms rather than switches)."""
    r = _r(r, "choir", dur)
    pitches = np.atleast_1d(np.asarray(pitches, dtype=np.float64))
    n = n_of(dur + release + 0.05)
    t = t_axis(n)
    out = np.zeros((2, n))
    G = 4
    fsc = np.array([0.955, 0.99, 1.02, 1.05]) * r.uniform(0.99, 1.01, G)
    gpan = np.array([-0.75, 0.3, -0.3, 0.75]) * width
    for pf in pitches:
        vt = _voice_type(pf)
        subs = [np.zeros(n) for _ in range(G)]
        for v in range(voices):
            det = r.normal(0, 7.0)
            vr = r.uniform(4.8, 6.2) * (1.0 + 0.05 * dsp.ctrl_noise(n, r, 0.7))
            vd = r.uniform(12, 28)
            cents = det + vd * dsp.smoothstep((t - r.uniform(0.2, 0.6)) / 0.5) * \
                np.sin(TWO_PI * dsp.phase_cycles(vr, n, r.uniform())) + 6.0 * dsp.ctrl_noise(n, r, 0.8) \
                + 2.5 * dsp.ctrl_noise(n, r, 11.0)
            f = pf * dsp.cents2ratio(cents)
            src = 0.8 * dsp.osc_saw(f, n, r.uniform()) + 0.35 * dsp.osc_square(f, n, r.uniform(), pw=0.28)
            a_j = attack * r.uniform(0.8, 1.35)
            if swell > 0:
                e = dsp.env_points([(0, 0), (a_j, 0.5), (dur, 0.5 + 0.5 * swell), (dur + release, 0), (n / SR, 0)], n, "cos")
            else:
                e = dsp.env_points([(0, 0), (a_j, 1.0), (dur, 0.95), (dur + release, 0), (n / SR, 0)], n, "cos")
            e *= np.maximum(0.0, 1.0 + 0.08 * dsp.ctrl_noise(n, r, 1.5) + 0.035 * dsp.ctrl_noise(n, r, 17.0))
            subs[v % G] += src * e
        grp = np.zeros((2, n))
        for g in range(G):
            x = dsp.onepole(subs[g], 1100.0)                  # glottal tilt (-12 dB/oct overall above ~1 kHz)
            x = dsp.lowpass(x, 5200, 2)
            ya = _formant_filter(x, vt, vowel, fsc[g])
            if vowel_to and vowel_to != vowel:
                yb = _formant_filter(x, vt, vowel_to, fsc[g])
                j = r.uniform(-0.08, 0.08)
                u = dsp.smoothstep((t / max(dur, 1e-3) - (morph[0] + j)) / max(morph[1] - morph[0], 1e-3))
                ya = ya * np.sqrt(1.0 - u) + yb * np.sqrt(u)
            gl, gr = dsp.pan_gains(gpan[g] * r.uniform(0.8, 1.0))
            grp[0] += ya * gl
            grp[1] += ya * gr
        asp = _formant_filter(dsp.highpass(r.standard_normal((2, n)), 800, 2), vt, vowel)
        aenv = dsp.env_points([(0, 0), (attack, 1.0), (dur, 1.0), (dur + release, 0), (n / SR, 0)], n, "cos")
        grp = dsp.normalize(grp, 1.0) + breath * aenv * asp / (dsp.peak(asp) + 1e-9)
        out += grp
    out = dsp.eq_chain(out, [("hp", 90, 0, 0.7), ("peak", 2800, -1.0, 1.0)])
    out = dsp.fade(out, 0.0, 0.05)
    return dsp.normalize(out, 1.0) * vel


# ======================================================================================  bell etc.
_BELL = [  # ratio, amp, t60 (s), doublet split (Hz) -- sparse, bonsho-like: the long hum and the beating strike tone
    # carry the sound; the upper partials are in the key (D: A, D, G, A) or short inharmonic shimmer.  No minor-third
    # 'tierce' (1.183 = F) and no 2.514 (F#) partial -- those made a Western church bell that clashed with the scale.
    (0.5, 1.0, 34.0, 0.3), (1.0, 0.85, 22.0, 0.62), (1.5, 0.2, 9.0, 1.0), (2.0, 0.34, 8.5, 1.3),
    (2.67, 0.12, 5.0, 1.6), (3.0, 0.11, 4.2, 1.9), (4.22, 0.07, 2.3, 2.6), (5.39, 0.045, 1.5, 3.2),
    (6.93, 0.03, 0.9, 4.0), (8.71, 0.018, 0.55, 5.0),
]


def temple_bell(f0=146.83, vel=0.8, r=None, dur=14.0, bright=0.5):
    """bonsho-style temple bell (stereo). f0 = strike tone (the hum sounds an octave below). Doublet partials beat
    slowly and are spread across the stereo field so the 'wavering' (unari) rotates."""
    r = _r(r, "bell", f0, vel)
    n = n_of(dur)
    t = t_axis(n)
    L = np.zeros(n)
    R = np.zeros(n)
    for (ratio, amp, t60, split) in _BELL:
        f = f0 * ratio * r.uniform(0.997, 1.003)
        if f > 16000:
            continue
        a = amp * (0.6 + 0.8 * bright) ** (np.log2(ratio + 1.0)) * r.uniform(0.85, 1.15)
        tt = t60 * (0.85 + 0.3 * r.uniform())
        e = np.exp(-LN1000 * t / tt)
        ph1, ph2 = r.uniform(0, 1, 2)
        s1 = a * e * np.sin(TWO_PI * (f * t + ph1))
        s2 = a * r.uniform(0.6, 0.95) * e * np.sin(TWO_PI * ((f + split) * t + ph2))
        L += 0.75 * s1 + 0.35 * s2
        R += 0.35 * s1 + 0.75 * s2
    # clang: brief dense inharmonic cloud from the strike
    k = n_of(0.6)
    fr = r.uniform(900, 7000, 24)
    clang_l = dsp.modal(fr, r.uniform(0.02, 0.06, 24), r.uniform(0.08, 0.35, 24), k, r=r)
    clang_r = dsp.modal(fr * r.uniform(0.995, 1.005, 24), r.uniform(0.02, 0.06, 24), r.uniform(0.08, 0.35, 24), k, r=r)
    # wooden striker (shumoku) thud
    th = dsp.lowpass(r.standard_normal(k), 400, 2) * np.exp(-t[:k] / 0.025)
    th = 0.35 * vel * th / (dsp.peak(th) + 1e-9)
    L[:k] += clang_l * bright + th
    R[:k] += clang_r * bright + th
    out = np.vstack([L, R])
    out = dsp.fade(out, 0.0015, min(1.5, dur * 0.1))
    return dsp.normalize(out, 1.0) * vel


def heartbeat(vel=0.8, r=None, gap=0.17):
    """lub-dub (mono). onset = start of 'lub'."""
    r = _r(r, "heart", vel)
    n = n_of(0.75)
    t = t_axis(n)
    y = np.zeros(n)
    for i, (t0, f0, a, dd) in enumerate([(0.0, 52.0, 1.0, 0.085), (gap, 60.0, 0.62, 0.07)]):
        s = n_of(t0)
        m = n - s
        tt = t[:m]
        fm = f0 * (1.0 + 0.45 * np.exp(-tt / 0.02))
        body = np.sin(TWO_PI * dsp.phase_cycles(fm, m)) * np.exp(-tt / dd) * np.clip(tt / 0.004, 0, 1)
        thump = dsp.lowpass(r.standard_normal(m), 160, 2) * np.exp(-tt / 0.03)
        y[s:] += a * (body + 0.25 * thump / (dsp.peak(thump) + 1e-9))
    y = dsp.lowpass(y, 400, 2)
    return dsp.normalize(y, 1.0) * vel


def metal_swell(dur=2.5, vel=0.7, r=None, bright=0.6):
    """reversed gong/cymbal cloud + rising filtered noise. Returns (stereo, anchor) where anchor is
    the sample at which the crescendo peaks (place anchor on the target hit point)."""
    r = _r(r, "mswell", dur)
    n = n_of(dur)
    t = t_axis(n)
    out = np.zeros((2, n))
    for ch in range(2):
        m = 70
        fr = np.exp(r.uniform(np.log(180), np.log(9000), m))
        am = r.uniform(0.2, 1.0, m) / np.sqrt(fr / 300.0)
        t60 = r.uniform(1.0, 5.0, m)
        cloud = dsp.modal(fr, am, t60, n, r=r)
        cloud = cloud[::-1]
        nz = r.standard_normal(n)
        fc = np.geomspace(400, 9000 * (0.5 + bright), n)
        nz = dsp.tv_biquad(nz, "lp", fc, 0.9, block=256)
        ne = (t / dur) ** 3
        out[ch] = dsp.normalize(cloud, 1.0) * 0.8 + 0.5 * nz * ne / (dsp.peak(nz * ne) + 1e-9)
    out *= dsp.smoothstep(t / dur) ** 1.5
    out = dsp.fade(out, 0.2, 0.004)
    return dsp.normalize(out, 1.0) * vel, n
