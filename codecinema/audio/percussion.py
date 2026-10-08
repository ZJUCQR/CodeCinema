"""
codecinema.audio.percussion -- synthesized percussion: a drum kit, orchestral percussion and the Chinese
luogu (gong-and-drum) ensemble.

Every function takes a velocity 0..1 and a numpy Generator and returns float64 audio at dsp.SR whose first
sample is the stroke (anchor 0), except cymbal_swell (the crescendo peaks at the end of the clip).  Peak ~ vel.

    kit         kick, snare, side_stick, clap, hihat (closed / pedal / open), tom, ride, crash, tambourine,
                shaker, cowbell, woodblock, triangle, castanets
    orchestral  timpani (pitched; rolls), bass_drum, cymbals (clash / choke), cymbal_swell, sleigh_bells, taiko
    Chinese     daluo (big gong, pitch falls), xiaoluo (small opera gong, pitch rises), bo (cymbals; muted 'qi'),
                tanggu (hall drum: center / edge / rim), bangzi (hardwood clapper), muyu (wooden fish)
    hand        bodhran (open / muted / rim), conga (open / muted / slap), bongo (high / low), claves
    8-bit       chip_noise: the console's shift-register noise as snare, kick or hat
Taiko is adapted from the Silver Grass pack.
"""
import numpy as np

from codecinema.audio import dsp
from codecinema.audio.dsp import SR, TWO_PI, n_of, t_axis


def _nrm(x):
    return x / (dsp.peak(x) + 1e-12)


def _r(r, *keys):
    return r if r is not None else dsp.rng("perc", *keys)


def _burst(r, n, lo, hi, tau, order=2):
    t = t_axis(n)
    return dsp.bandpass(r.standard_normal(n), lo, min(hi, dsp.NYQ * 0.95), order) * np.exp(-t / tau)


def _metal_cloud(r, n, lo, hi, count, t60_lo, t60_hi, tilt=0.5, bloom=0.0, fdrift=None):
    """many inharmonic modes (log-spaced at random) with frequency-dependent decay; optional bloom of the highs"""
    fr = np.exp(r.uniform(np.log(lo), np.log(min(hi, dsp.NYQ * 0.9)), count))
    u = (np.log(fr) - np.log(lo)) / max(np.log(hi / lo), 1e-9)
    amps = r.uniform(0.4, 1.0, count) / (fr / lo) ** tilt
    t60 = t60_lo * (t60_hi / t60_lo) ** u * r.uniform(0.8, 1.2, count)
    y = dsp.modal(fr, amps, t60, n, r=r, attack=0.0005, fdrift=fdrift)
    if bloom > 0:
        hi_part = dsp.modal(fr[u > 0.5], amps[u > 0.5] * 1.5, t60[u > 0.5] * 1.3, n, r=r, fdrift=fdrift)
        t = t_axis(n)
        y = y + bloom * hi_part * dsp.smoothstep(t / 0.12)
    return y


def _stereo(r, fn, width=0.5):
    """two decorrelated renders of a mono generator, mixed for a natural width"""
    a, b = fn(dsp.rng(r.integers(1 << 30))), fn(dsp.rng(r.integers(1 << 30)))
    m = 0.5 * (a + b)
    s = 0.5 * (a - b) * width
    return np.vstack([m + s, m - s])


# ======================================================================================  drum kit
def kick(vel=0.8, r=None, tone=0.5, dur=0.6):
    r = _r(r, "kick", vel)
    n = n_of(dur)
    t = t_axis(n)
    f = 48.0 + (95.0 + 60.0 * tone) * np.exp(-t / 0.035)
    body = np.sin(TWO_PI * dsp.phase_cycles(f, n)) * np.exp(-t / (0.22 + 0.1 * (1 - tone)))
    k = n_of(0.02)
    click = dsp.highpass(r.standard_normal(k), 1500, 2) * np.exp(-t[:k] / 0.0025)
    y = body
    y[:k] += (0.15 + 0.25 * tone) * vel * _nrm(click)
    y[: n_of(0.001)] *= np.linspace(0, 1, n_of(0.001))
    return _nrm(dsp.fade(y, 0.0, 0.05)) * vel


def snare(vel=0.8, r=None, tone=0.5, dur=0.45, brush=False):
    r = _r(r, "snare", vel, brush)
    n = n_of(dur)
    t = t_axis(n)
    if brush:
        y = dsp.bandpass(r.standard_normal(n), 2000, 9000, 2) * np.exp(-t / 0.08) * np.clip(t / 0.01, 0, 1)
        return _nrm(y) * vel * 0.8
    head = dsp.modal([180.0, 330.0, 462.0], [1.0, 0.6, 0.3], [0.12, 0.09, 0.06], n, r=r,
                     fdrift=1.0 + 0.05 * np.exp(-t / 0.01))
    wires = dsp.bandpass(r.standard_normal(n), 1800, 9500, 2) * np.exp(-t / (0.09 + 0.06 * vel))
    k = n_of(0.01)
    crack = dsp.highpass(r.standard_normal(k), 3000, 2) * np.exp(-t[:k] / 0.0015)
    y = (0.9 - 0.3 * tone) * _nrm(head) + (0.7 + 0.3 * vel) * _nrm(wires)
    y[:k] += 0.4 * vel * _nrm(crack)
    return _nrm(dsp.fade(y, 0.0, 0.05)) * vel


def side_stick(vel=0.7, r=None):
    r = _r(r, "stick", vel)
    n = n_of(0.15)
    y = dsp.modal([1650.0, 2700.0, 4100.0], [1.0, 0.5, 0.3], [0.04, 0.03, 0.02], n, r=r)
    y = _nrm(y)
    y[: n_of(0.005)] += 0.8 * _nrm(dsp.highpass(r.standard_normal(n_of(0.005)), 3000, 2))
    return _nrm(dsp.highpass(y, 400, 2)) * vel


def clap(vel=0.8, r=None, people=1):
    r = _r(r, "clap", vel, people)
    n = n_of(0.35)
    t = t_axis(n)
    y = np.zeros(n)
    for p in range(people):
        off = r.uniform(0, 0.012) if p else 0.0
        for j, d in enumerate((0.0, 0.009, 0.017)):
            s = n_of(off + d * r.uniform(0.8, 1.2))
            m = n - s
            y[s:] += r.uniform(0.6, 1.0) * dsp.bandpass(r.standard_normal(m), 900, 3500, 2) * np.exp(-t[:m] / 0.006)
        s = n_of(off + 0.024)
        m = n - s
        y[s:] += 0.9 * dsp.bandpass(r.standard_normal(m), 800, 4000, 2) * np.exp(-t[:m] / 0.06)
    return _nrm(dsp.fade(y, 0.0, 0.03)) * vel


_HAT_FREQS = np.array([205.3, 304.4, 369.6, 522.7, 540.0, 800.0]) * 1.65


def hihat(vel=0.6, r=None, kind="closed"):
    """kind: closed | pedal | open"""
    r = _r(r, "hat", vel, kind)
    dur = {"closed": 0.12, "pedal": 0.16, "open": 0.9}[kind]
    tau = {"closed": 0.025, "pedal": 0.04, "open": 0.3}[kind]
    n = n_of(dur)
    t = t_axis(n)
    metal = sum(dsp.osc_square(f * r.uniform(0.99, 1.01), n, r.uniform()) for f in _HAT_FREQS)
    metal = dsp.bandpass(metal, 6500, 14000, 2)
    noise = dsp.highpass(r.standard_normal(n), 7000, 2)
    y = (0.6 * _nrm(metal) + 0.5 * _nrm(noise)) * np.exp(-t / tau)
    if kind == "pedal":
        y += 0.2 * _burst(r, n, 300, 1200, 0.01)
    y[: n_of(0.0005)] *= np.linspace(0, 1, n_of(0.0005))
    y = dsp.lowpass(y, 15000, 2)
    return _nrm(dsp.fade(y, 0.0, 0.03)) * vel * (0.7 + 0.3 * vel)


def tom(vel=0.8, r=None, pitch=0.5):
    """pitch 0 (floor) .. 1 (high rack)"""
    r = _r(r, "tom", vel, pitch)
    f0 = 70.0 * 2.0 ** (pitch * 2.0)
    n = n_of(0.9 - 0.4 * pitch)
    t = t_axis(n)
    y = dsp.modal(f0 * np.array([1.0, 1.59, 2.14, 2.3]), [1.0, 0.45, 0.25, 0.15], [0.6, 0.3, 0.2, 0.15], n, r=r,
                  fdrift=1.0 + 0.18 * vel * np.exp(-t / 0.05))
    k = n_of(0.02)
    y = _nrm(y)
    y[:k] += 0.35 * vel * _nrm(_burst(r, k, 800, 5000, 0.004))
    return _nrm(dsp.fade(y, 0.0, 0.08)) * vel


def ride(vel=0.6, r=None, bell=False):
    r = _r(r, "ride", vel, bell)
    n = n_of(3.0)
    t = t_axis(n)
    y = _metal_cloud(r, n, 350, 12000, 60, 3.0, 0.8, tilt=0.35)
    if bell:
        y = 0.5 * _nrm(y) + _nrm(dsp.modal([720.0, 1310.0, 2050.0, 3010.0], [1.0, 0.7, 0.4, 0.25], [2.0, 1.5, 1.0, 0.7], n, r=r))
    k = n_of(0.01)
    y = _nrm(dsp.highpass(y, 300, 2))
    y[:k] += 0.3 * _nrm(dsp.highpass(r.standard_normal(k), 4000, 2)) * np.exp(-t[:k] / 0.001)
    return _nrm(dsp.fade(y, 0.0, 0.5)) * vel


def crash(vel=0.8, r=None, size=1.0, choke=None):
    """crash cymbal (stereo); choke = seconds after which a hand stops it"""
    r = _r(r, "crash", vel, size)
    dur = 2.5 + 1.5 * size
    n = n_of(dur)
    t = t_axis(n)

    def one(rr):
        cloud = _metal_cloud(rr, n, 300 / size, 13000, 34, 3.2 * size, 0.9, tilt=0.3, bloom=0.4)
        hiss = dsp.highpass(rr.standard_normal(n), 3000, 2) * np.exp(-t / (0.5 + 0.6 * size))
        return 0.8 * _nrm(cloud) + 0.45 * _nrm(hiss) * (0.6 + 0.4 * vel)
    y = _stereo(r, one, 0.6)
    y = dsp.highpass(y, 250, 2)
    y = dsp.lowpass(y, 9000 + 6000 * vel, 2)
    if choke:
        k = n_of(choke)
        y[:, k:] *= np.exp(-(t[k:] - choke) / 0.025)[None, :]
    return _nrm(dsp.fade(y, 0.0, 0.4)) * vel


def tambourine(vel=0.7, r=None, shake=False):
    r = _r(r, "tamb", vel, shake)
    n = n_of(0.5 if not shake else 0.7)
    y = np.zeros(n)
    hits = [0.0] if not shake else list(np.cumsum(r.uniform(0.02, 0.05, 8)) - 0.02)
    for i, h in enumerate(hits):
        s = n_of(h)
        m = n - s
        jingles = _metal_cloud(r, m, 3500, 12000, 14, 0.25, 0.08, tilt=0.2)
        y[s:] += (1.0 if i == 0 else r.uniform(0.3, 0.7)) * _nrm(jingles)
    y += 0.25 * _burst(r, n, 150, 900, 0.03)
    return _nrm(dsp.highpass(dsp.fade(y, 0.0, 0.05), 400, 2)) * vel


def shaker(vel=0.6, r=None, dur=0.09):
    r = _r(r, "shaker", vel)
    n = n_of(dur + 0.05)
    t = t_axis(n)
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 2
    grains = dsp.crackle(n, r, 2500.0, amp_sigma=0.5, dur_range=(0.0002, 0.0012), hp=3000.0)
    y = dsp.bandpass(grains + 0.3 * r.standard_normal(n), 3500, 11000, 2) * env
    return _nrm(y) * vel


def cowbell(vel=0.7, r=None):
    r = _r(r, "cowbell", vel)
    n = n_of(0.5)
    y = dsp.modal([565.0, 845.0, 1305.0, 1670.0, 2510.0], [1.0, 0.75, 0.3, 0.25, 0.1], [0.35, 0.3, 0.2, 0.15, 0.1], n, r=r)
    y = _nrm(y)
    y[: n_of(0.004)] += 0.4 * _nrm(dsp.highpass(r.standard_normal(n_of(0.004)), 2500, 2))
    return _nrm(dsp.bandpass(y, 400, 6000, 2)) * vel


def woodblock(vel=0.7, r=None, high=True):
    r = _r(r, "woodblock", vel, high)
    f = 1050.0 if high else 760.0
    n = n_of(0.25)
    t = t_axis(n)
    y = dsp.modal([f, f * 2.6, f * 4.3], [1.0, 0.35, 0.12], [0.09, 0.05, 0.03], n, r=r)
    y = _nrm(y)
    y[: n_of(0.006)] += 0.5 * _nrm(dsp.highpass(r.standard_normal(n_of(0.006)), 3000, 2)) * np.exp(-t[:n_of(0.006)] / 0.001)
    return _nrm(dsp.highpass(y, 300, 2)) * vel


def triangle(vel=0.6, r=None, muted=False):
    r = _r(r, "triangle", vel, muted)
    n = n_of(0.25 if muted else 3.5)
    f = 1260.0
    ratios = np.array([1.0, 2.72, 3.9, 5.41, 6.6, 7.96, 9.33])
    t60 = np.array([3.5, 3.0, 2.6, 2.2, 1.8, 1.5, 1.2]) * (0.06 if muted else 1.0)
    y = dsp.modal(f * ratios, [0.5, 1.0, 0.7, 0.6, 0.4, 0.3, 0.2], t60, n, r=r)
    y = _nrm(y)
    y[: n_of(0.002)] += 0.2 * _nrm(dsp.highpass(r.standard_normal(n_of(0.002)), 5000, 2))
    return _nrm(dsp.fade(y, 0.0, 0.2 if not muted else 0.05)) * vel


def castanets(vel=0.7, r=None):
    r = _r(r, "castanets", vel)
    n = n_of(0.12)
    y = np.zeros(n)
    for d in (0.0, r.uniform(0.012, 0.02)):
        s = n_of(d)
        y[s:] += dsp.modal([2100.0, 3400.0, 5200.0], [1.0, 0.5, 0.3], [0.03, 0.02, 0.015], n - s, r=r)
    return _nrm(dsp.highpass(y, 800, 2)) * vel


# ======================================================================================  orchestral
def timpani(midi=45, vel=0.8, r=None, dur=3.0, roll=0.0, damp=None):
    """kettle drum: the preferred (1,1)-family membrane modes tuned near 1 : 1.5 : 2 : 2.44 : 2.94, a damped
    (0,1) thud, a felt-mallet thump.  roll > 0 = seconds of single-stroke roll (crescendo to vel)."""
    r = _r(r, "timp", midi, vel, roll)
    if roll > 0:
        rate = r.uniform(13.0, 16.0)
        times = np.arange(0.0, roll, 1.0 / rate)
        times = times + r.normal(0, 0.004, len(times))
        n = n_of(roll + dur)
        out = np.zeros(n)
        for i, ts in enumerate(np.maximum(times, 0.0)):
            u = ts / max(roll, 1e-3)
            v = vel * (0.35 + 0.65 * u ** 1.3) * r.uniform(0.85, 1.05)
            hit = timpani(midi, v, dsp.rng("timp_roll", midi, i), dur=1.6 if i < len(times) - 1 else dur)
            s = n_of(ts)
            out[s:s + len(hit)] += hit[: n - s]
        return _nrm(dsp.fade(out, 0.0, 0.3)) * vel
    f0 = float(dsp.midi2hz(midi))
    n = n_of(dur)
    t = t_axis(n)
    ratios = np.array([1.0, 1.504, 1.742, 2.0, 2.245, 2.44, 2.82, 2.94, 3.17])
    amps = np.array([1.0, 0.55, 0.15, 0.4, 0.12, 0.25, 0.1, 0.15, 0.06]) * r.uniform(0.85, 1.15, 9)
    amps *= (0.5 + 0.5 * vel) ** (np.arange(9) * 0.35)
    t60s = np.array([2.6, 1.9, 0.7, 1.5, 0.6, 1.1, 0.5, 0.8, 0.4]) * (1.0 + 0.3 * (110.0 / max(f0, 60)))
    fmul = 1.0 + 0.012 * vel * np.exp(-t / 0.08)
    y = dsp.modal(f0 * ratios, amps, t60s, n, r=r, fdrift=fmul, attack=0.002)
    thud = dsp.modal([f0 * 0.62], [1.0], [0.12], n, r=r, attack=0.002)
    k = n_of(0.05)
    felt = dsp.lowpass(r.standard_normal(k), 900 + 1500 * vel, 2) * np.exp(-t[:k] / 0.006)
    y = _nrm(y) + 0.5 * _nrm(thud)
    y[:k] += 0.25 * vel * _nrm(felt)
    if damp:
        y[n_of(damp):] *= np.exp(-(t[n_of(damp):] - damp) / 0.06)
    y = dsp.highpass(y, 30, 2)
    return _nrm(dsp.fade(y, 0.0, 0.3)) * vel


def bass_drum(vel=0.8, r=None, dur=3.0):
    """concert bass drum: very low, long, soft beater"""
    r = _r(r, "bassdrum", vel)
    n = n_of(dur)
    t = t_axis(n)
    y = dsp.modal(np.array([44.0, 71.0, 97.0, 122.0, 150.0]), [1.0, 0.6, 0.4, 0.25, 0.15], [2.6, 1.6, 1.1, 0.8, 0.6], n,
                  r=r, fdrift=1.0 + 0.1 * vel * np.exp(-t / 0.06), attack=0.004)
    k = n_of(0.08)
    y = _nrm(y)
    y[:k] += 0.3 * vel * _nrm(dsp.lowpass(r.standard_normal(k), 400, 2) * np.exp(-t[:k] / 0.015))
    return _nrm(dsp.fade(dsp.highpass(y, 25, 2), 0.0, 0.4)) * vel


def cymbals(vel=0.85, r=None, choke=None):
    """orchestral clash cymbals (stereo)"""
    r = _r(r, "cymbals", vel)
    y = crash(vel, r, size=1.25, choke=choke)
    k = n_of(0.02)
    y[:, :k] += 0.3 * vel * _nrm(dsp.bandpass(r.standard_normal((2, k)), 800, 5000, 2))
    return _nrm(y) * vel


def cymbal_swell(dur=2.5, vel=0.7, r=None):
    """suspended cymbal roll with soft mallets: crescendo that peaks at the END of the clip (stereo)"""
    r = _r(r, "cswell", dur, vel)
    n = n_of(dur + 0.6)
    t = t_axis(n)
    peak_at = dur

    def one(rr):
        cloud = _metal_cloud(rr, n, 250, 11000, 80, 2.5, 0.6, tilt=0.35)
        roll = dsp.crackle(n, rr, 30.0, amp_sigma=0.2, dur_range=(0.003, 0.008), hp=200.0)
        hiss = dsp.highpass(rr.standard_normal(n), 2500, 2)
        return 0.6 * _nrm(cloud) * (0.4 + 0.6 * np.abs(dsp.lowpass(roll, 60, 2)) / (dsp.peak(dsp.lowpass(roll, 60, 2)) + 1e-9)) + 0.6 * _nrm(hiss)
    y = _stereo(r, one, 0.8)
    env = np.where(t < peak_at, (t / peak_at) ** 2.2, np.exp(-(t - peak_at) / 0.25))
    fc = 1500.0 + 9000.0 * np.clip(t / peak_at, 0, 1) ** 1.5
    y = dsp.lp_varying(y * env, fc, 0.8, spacing=0.5)
    return _nrm(dsp.fade(y, 0.05, 0.1)) * vel


def sleigh_bells(vel=0.7, r=None, dur=0.35, shake=True):
    """a strap of small jingle bells, shaken (dur = length of the shake)"""
    r = _r(r, "sleigh", vel, dur)
    n = n_of(dur + 0.5)
    t = t_axis(n)
    y = np.zeros(n)
    count = int(10 + 30 * dur) if shake else 3
    for i in range(count):
        s = n_of(r.uniform(0, dur) if shake else r.uniform(0, 0.01))
        m = min(n - s, n_of(0.35))
        f = r.uniform(3200, 6500)
        bell = dsp.modal([f, f * 1.48, f * 2.12], [1.0, 0.4, 0.2], [0.25, 0.15, 0.1], m, r=r)
        y[s:s + m] += r.uniform(0.3, 1.0) * bell
    y = dsp.highpass(y, 1500, 2) * (1.0 - 0.3 * np.clip(t / (dur + 0.4), 0, 1))
    return _nrm(dsp.fade(y, 0.002, 0.1)) * vel


def taiko(vel=0.8, r=None, size=1.0, tone=0.5, rim=False):
    """big barrel drum (from the Silver Grass odaiko): pitch-dropping air-loaded membrane modes, second head, shell,
    stick slap and air thump. size 1.0 = o-daiko (~56 Hz), 0.6 = chu-daiko. rim = wooden 'ka' on the shell."""
    r = _r(r, "taiko", vel, size, rim)
    vel = float(np.clip(vel, 0.02, 1.2))
    if rim:
        n = n_of(0.3)
        y = dsp.modal(np.array([1720, 2890, 4630]) * r.uniform(0.95, 1.05), [1.0, 0.55, 0.3], [0.07, 0.05, 0.035], n, r=r)
        y = _nrm(y)
        y[: n_of(0.01)] += 0.7 * _nrm(dsp.highpass(r.standard_normal(n_of(0.01)), 3000, 2))
        return _nrm(y) * vel * 0.8
    f0 = (56.0 / size ** 0.85) * r.uniform(0.985, 1.015)
    dur = (1.6 + 1.6 * size) * (0.65 + 0.35 * min(vel, 1.0))
    n = n_of(dur)
    t = t_axis(n)
    drop = (0.16 + 0.34 * min(vel, 1.1)) * r.uniform(0.9, 1.1)
    fmul = 1.0 + drop * np.exp(-t / 0.042) + 0.035 * vel * np.exp(-t / 0.35)
    ratios = np.array([1.0, 1.505, 1.985, 2.44, 2.905, 3.37, 3.83, 4.29])
    amps = np.array([1.0, 0.58, 0.42, 0.27, 0.19, 0.13, 0.09, 0.06])
    t60s = np.array([2.7, 1.55, 1.05, 0.78, 0.58, 0.44, 0.34, 0.27]) * (0.7 + 0.3 * size)
    b = 0.3 + 0.55 * min(vel, 1.0) + 0.3 * (tone - 0.5)
    amps = amps * b ** (np.arange(len(amps)) * 0.45) * r.uniform(0.85, 1.15, len(amps))
    head1 = dsp.modal(f0 * ratios, amps, t60s, n, r=r, fdrift=fmul)
    d2 = n_of(0.0016 * size)
    head2 = dsp.modal(f0 * ratios * 1.013, amps * 0.32, t60s * 1.1, n, r=r, fdrift=1.0 + 0.5 * (fmul - 1.0))
    head2 = np.concatenate([np.zeros(d2), head2[: n - d2]])
    shell = dsp.modal(np.array([168, 243, 331, 462, 610]) * r.uniform(0.97, 1.03), [0.2, 0.17, 0.13, 0.09, 0.06],
                      [0.2, 0.16, 0.13, 0.1, 0.08], n, r=r)
    k = min(n, n_of(0.12))
    tk = t[:k]
    click = dsp.highpass(r.standard_normal(k), 1800, 2) * np.exp(-tk / 0.0022)
    slap = dsp.bandpass(r.standard_normal(k), 280, 1900 + 1600 * tone, 2) * np.exp(-tk / (0.012 + 0.01 * size))
    air = dsp.lowpass(r.standard_normal(k), 140, 2) * np.exp(-tk / 0.05)
    y = head1 + 0.8 * head2 + shell * (1.0 + 0.8 * vel)
    y[:k] += 0.45 * vel ** 1.5 * _nrm(click) + 0.85 * vel * _nrm(slap) + 0.45 * vel * _nrm(air)
    y = dsp.highpass(y, 28.0, 2)
    y = _nrm(y)
    if vel > 0.75:
        y = _nrm(dsp.saturate(y * (1.0 + (vel - 0.75) * 1.6), 0.35))
    return dsp.fade(y, 0.0, min(0.3, dur * 0.2)) * min(vel, 1.1) ** 1.15


# ======================================================================================  Chinese luogu
def daluo(vel=0.85, r=None, size=1.0, dur=None):
    """big gong (da luo): the strike flares, then the pitch slides DOWN a couple of semitones ('kuang'); a dense
    metallic hum whose upper modes bloom a moment after the strike. Stereo."""
    r = _r(r, "daluo", vel, size)
    dur = dur or 3.5 + 1.5 * size
    n = n_of(dur)
    t = t_axis(n)
    fc = 240.0 / size ** 0.8 * r.uniform(0.97, 1.03)
    drift = 1.0 + (0.1 + 0.05 * vel) * np.exp(-t / 0.28)

    def one(rr):
        base = dsp.modal(fc * np.array([1.0, 1.52, 2.03, 2.47]), [1.0, 0.6, 0.45, 0.3],
                         [dur * 0.9, dur * 0.7, dur * 0.5, dur * 0.4], n, r=rr, fdrift=drift, attack=0.003)
        cloud = _metal_cloud(rr, n, fc * 2.5, 7000, 36, dur * 0.45, 0.5, tilt=0.55, bloom=0.8 * vel, fdrift=drift)
        return 0.9 * _nrm(base) + 0.65 * _nrm(cloud)
    y = _stereo(r, one, 0.5)
    k = n_of(0.08)
    strike = dsp.bandpass(r.standard_normal((2, k)), 400, 5000, 2) * np.exp(-t[:k] / 0.015)
    y[:, :k] += 0.35 * vel * _nrm(strike)
    y = dsp.lowpass(y, 6000 + 5000 * vel, 2)
    return _nrm(dsp.fade(dsp.highpass(y, 60, 2), 0.0, min(1.0, dur * 0.3))) * vel


def xiaoluo(vel=0.8, r=None, dur=1.6):
    """small opera gong (xiao luo): a bright 'jing' whose pitch rises a few semitones right after the strike"""
    r = _r(r, "xiaoluo", vel)
    n = n_of(dur)
    t = t_axis(n)
    fc = 760.0 * r.uniform(0.97, 1.03)
    drift = 1.0 - (0.15 + 0.04 * vel) * np.exp(-t / 0.1)
    base = dsp.modal(fc * np.array([1.0, 1.47, 2.09, 2.71, 3.4]), [1.0, 0.5, 0.35, 0.2, 0.12],
                     [dur * 0.85, dur * 0.6, dur * 0.45, dur * 0.35, dur * 0.25], n, r=r, fdrift=drift, attack=0.001)
    cloud = _metal_cloud(r, n, fc * 3.5, 11000, 24, dur * 0.3, 0.15, tilt=0.4, fdrift=drift)
    y = _nrm(base) + 0.35 * _nrm(cloud)
    k = n_of(0.01)
    y[:k] += 0.35 * vel * _nrm(dsp.highpass(r.standard_normal(k), 2500, 2)) * np.exp(-t[:k] / 0.0015)
    return _nrm(dsp.fade(dsp.highpass(y, 300, 2), 0.0, 0.3)) * vel


def bo(vel=0.8, r=None, muted=False, dur=1.6):
    """Chinese cymbals (bo / nao), clashed: a mid-heavy, trashy 'cha'; muted=True is the choked 'qi'. Stereo."""
    r = _r(r, "bo", vel, muted)
    dur = 0.18 if muted else dur
    n = n_of(dur + 0.05)
    t = t_axis(n)

    def one(rr):
        dome = dsp.modal(np.array([520.0, 830.0, 1240.0]) * rr.uniform(0.95, 1.05), [1.0, 0.7, 0.5],
                         [dur * 0.5, dur * 0.4, dur * 0.3], n, r=rr)
        cloud = _metal_cloud(rr, n, 450, 12000, 70, dur * 0.8, dur * 0.25, tilt=0.25, bloom=0.5)
        hiss = dsp.bandpass(rr.standard_normal(n), 1500, 11000, 2) * np.exp(-t / (0.08 if muted else dur * 0.3))
        return 0.35 * _nrm(dome) + 0.8 * _nrm(cloud) + 0.5 * _nrm(hiss)
    y = _stereo(r, one, 0.6)
    k = n_of(0.006)
    y[:, :k] += 0.4 * vel * _nrm(dsp.bandpass(r.standard_normal((2, k)), 1000, 6000, 2))
    if muted:
        y *= np.exp(-t / 0.05)[None, :]
    y = dsp.highpass(y, 300, 2)
    return _nrm(dsp.fade(y, 0.0, 0.03 if muted else 0.3)) * vel


def tanggu(vel=0.8, r=None, stroke="center"):
    """hall drum (tang gu): stroke center (warm boom), edge (higher, ringing), rim (wooden click)"""
    r = _r(r, "tanggu", vel, stroke)
    if stroke == "rim":
        return taiko(vel * 0.8, r, rim=True)
    edge = stroke == "edge"
    f0 = (98.0 if not edge else 150.0) * r.uniform(0.98, 1.02)
    n = n_of(1.4 if not edge else 0.9)
    t = t_axis(n)
    ratios = np.array([1.0, 1.59, 2.14, 2.3, 2.65, 2.92])
    amps = np.array([1.0, 0.5, 0.35, 0.3, 0.2, 0.15]) * ((0.6 if not edge else 1.3) ** np.arange(6) * 0.5 + 0.5)
    t60s = np.array([1.1, 0.6, 0.45, 0.4, 0.3, 0.25]) * (1.0 if not edge else 0.8)
    y = dsp.modal(f0 * ratios, amps, t60s, n, r=r, fdrift=1.0 + 0.12 * vel * np.exp(-t / 0.05))
    k = n_of(0.04)
    y = _nrm(y)
    y[:k] += (0.35 + 0.3 * edge) * vel * _nrm(_burst(r, k, 500, 5000, 0.005))
    y[:k] += 0.3 * vel * _nrm(dsp.lowpass(r.standard_normal(k), 200, 2) * np.exp(-t[:k] / 0.015))
    return _nrm(dsp.fade(dsp.highpass(y, 35, 2), 0.0, 0.2)) * vel


def bangzi(vel=0.8, r=None):
    """hardwood clapper (bang zi): a piercing dry 'ta'"""
    r = _r(r, "bangzi", vel)
    n = n_of(0.2)
    t = t_axis(n)
    f = 2050.0 * r.uniform(0.97, 1.03)
    y = dsp.modal([f, f * 1.9, f * 2.9], [1.0, 0.3, 0.1], [0.08, 0.04, 0.025], n, r=r)
    y = _nrm(y)
    k = n_of(0.004)
    y[:k] += 0.7 * _nrm(dsp.highpass(r.standard_normal(k), 3500, 2)) * np.exp(-t[:k] / 0.0007)
    return _nrm(dsp.highpass(y, 800, 2)) * vel


def muyu(vel=0.7, r=None, size=1.0):
    """wooden fish (mu yu): hollow, pitched 'tok' (size 0.5 small/high .. 1.5 large/low)"""
    r = _r(r, "muyu", vel, size)
    f = 640.0 / size * r.uniform(0.98, 1.02)
    n = n_of(0.3)
    t = t_axis(n)
    y = dsp.modal([f, f * 2.3, f * 3.6], [1.0, 0.2, 0.08], [0.16, 0.06, 0.03], n, r=r,
                  fdrift=1.0 + 0.02 * np.exp(-t / 0.01))
    y = _nrm(y)
    k = n_of(0.005)
    y[:k] += 0.35 * vel * _nrm(dsp.bandpass(r.standard_normal(k), 1500, 6000, 2))
    return _nrm(dsp.highpass(y, 200, 2)) * vel


# ======================================================================================  hand drums and 8-bit noise
def bodhran(vel=0.8, r=None, stroke="open"):
    """bodhran frame drum struck with a tipper: a deep, loose goatskin boom (stroke open | muted | rim)"""
    r = _r(r, "bodhran", vel, stroke)
    if stroke == "rim":
        n = n_of(0.15)
        modes = np.array([1100, 2600, 4100]) * r.uniform(0.95, 1.05)
        y = dsp.modal(modes, [1.0, 0.5, 0.2], [0.04, 0.025, 0.015], n, r=r)
        return _nrm(dsp.highpass(y, 400, 2)) * vel
    muted = stroke == "muted"
    f0 = r.uniform(85, 105) * (1.25 if muted else 1.0)
    n = n_of(0.35 if muted else 0.9)
    t = t_axis(n)
    t60 = np.array([0.45, 0.3, 0.2, 0.18, 0.12, 0.1]) * (0.3 if muted else 1.0)
    y = dsp.modal(f0 * np.array([1.0, 1.59, 2.14, 2.3, 2.65, 2.92]), [1.0, 0.5, 0.35, 0.3, 0.2, 0.12], t60, n, r=r,
                  fdrift=1.0 + 0.12 * vel * np.exp(-t / 0.04), attack=0.001)
    k = n_of(0.03)
    y = _nrm(y)
    y[:k] += 0.35 * vel * _nrm(_burst(r, k, 300, 3000, 0.005))
    return _nrm(dsp.fade(dsp.highpass(y, 40, 2), 0.0, 0.05)) * vel


def claves(vel=0.8, r=None):
    """two hardwood sticks: one bright, woody 'tock'"""
    r = _r(r, "claves", vel)
    n = n_of(0.25)
    f = r.uniform(2300, 2600)
    y = _nrm(dsp.modal([f, f * 2.71, f * 4.6], [1.0, 0.12, 0.04], [0.14, 0.04, 0.02], n, r=r, attack=0.0003))
    y[:n_of(0.002)] += 0.4 * _nrm(dsp.highpass(r.standard_normal(n_of(0.002)), 3000, 2))
    return _nrm(dsp.highpass(y, 600, 2)) * vel


def conga(vel=0.8, r=None, stroke="open"):
    """conga, high drum: an open ringing tone, a muted tone or a sharp slap (stroke open | muted | slap)"""
    r = _r(r, "conga", vel, stroke)
    f0 = r.uniform(195, 215)
    n = n_of(0.6)
    t = t_axis(n)
    life = {"open": 1.0, "muted": 0.25, "slap": 0.3}.get(stroke, 1.0)
    y = _nrm(dsp.modal(f0 * np.array([1.0, 1.59, 2.14, 2.65]), [1.0, 0.45, 0.3, 0.15],
                       np.array([0.35, 0.2, 0.15, 0.1]) * life, n, r=r, fdrift=1.0 + 0.04 * vel * np.exp(-t / 0.03)))
    k = n_of(0.02)
    slap = 1.2 if stroke == "slap" else 0.3
    y[:k] += slap * vel * _nrm(_burst(r, k, 1000 if stroke == "slap" else 400, 6000, 0.003))
    return _nrm(dsp.fade(dsp.highpass(y, 80, 2), 0.0, 0.05)) * vel


def bongo(vel=0.8, r=None, high=True):
    """bongos: a small tight membrane, high (macho) or low (hembra)"""
    r = _r(r, "bongo", vel, high)
    f0 = r.uniform(400, 440) if high else r.uniform(290, 320)
    n = n_of(0.35)
    t = t_axis(n)
    y = _nrm(dsp.modal(f0 * np.array([1.0, 1.59, 2.14, 2.3]), [1.0, 0.4, 0.25, 0.15], [0.18, 0.1, 0.07, 0.05], n, r=r,
                       fdrift=1.0 + 0.05 * vel * np.exp(-t / 0.02)))
    k = n_of(0.015)
    y[:k] += 0.35 * vel * _nrm(_burst(r, k, 800, 7000, 0.002))
    return _nrm(dsp.fade(dsp.highpass(y, 120, 2), 0.0, 0.03)) * vel


_LFSR = {}


def _lfsr():
    """the 15-bit noise shift register of 8-bit consoles (one full 32767-step period, +-1)"""
    if not _LFSR:
        reg, out = 1, np.empty(32767)
        for i in range(32767):
            bit = (reg ^ (reg >> 1)) & 1
            reg = (reg >> 1) | (bit << 14)
            out[i] = 1.0 if reg & 1 else -1.0
        _LFSR[0] = out
    return _LFSR[0]


def chip_noise(vel=0.8, r=None, kind="snare"):
    """8-bit noise drum: the shift-register noise clocked at a chosen rate under a stepped decay (kind snare | kick |
    hat); the kick adds the console's falling triangle thump"""
    r = _r(r, "chip_noise", vel, kind)
    presets = {"kick": (3500.0, 0.08, 2500.0), "hat": (120000.0, 0.03, 14000.0), "snare": (17000.0, 0.11, 9000.0)}
    clock, decay, lp = presets.get(kind, presets["snare"])
    n = n_of(decay * 4.0 + 0.03)
    t = t_axis(n)
    seq = _lfsr()
    pos = np.cumsum(np.full(n, clock / SR) * (1.0 + (2.0 * np.exp(-t / 0.01) if kind == "kick" else 0.0)))
    y = dsp.lowpass(seq[(pos + r.integers(len(seq))).astype(np.int64) % len(seq)], lp, 2)
    frames = (np.floor(t * 60.0) / 60.0)
    y = y * np.round(np.exp(-frames / decay) * 15.0) / 15.0
    if kind == "kick":
        y = 0.6 * y + np.sin(TWO_PI * dsp.phase_cycles(50.0 + 250.0 * np.exp(-t / 0.02), n)) * np.exp(-t / 0.07)
    if kind == "hat":
        y = dsp.highpass(y, 5000, 2)
    return _nrm(dsp.fade(y, 0.0005, 0.01)) * vel
