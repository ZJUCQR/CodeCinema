"""
sfx.py -- procedural foley for The Night Revels of Han Xizai, Cat Edition.

EVENTS = {type: fn(ev, r) -> (clip, anchor)}: clip mono (n,) or stereo (2, n) float64 at dsp.SR, peak-normalised
to 1.0 (mix.py sets per-type gains); `anchor` is the sample that lands on the event time (the impact of impact
sounds, 0 for sounds that start at the event; pre-roll such as a pounce's scrabble sits before the anchor).
Everything is driven by the passed Generator -> deterministic.
"""

import numpy as np

import dsp
import cats
from dsp import SR, n_of, t_axis, TWO_PI


def _dec(n, tau, att=0.0005):
    t = t_axis(n)
    e = np.exp(-t / tau)
    if att > 0:
        e *= np.clip(t / att, 0.0, 1.0)
    return e


def _nrm(x):
    return x / (dsp.peak(x) + 1e-12)


def _impulses(rate, n, r, amp_sigma=0.4):
    """Poisson impulse train (rate: scalar or array events/s) with log-normal amplitudes"""
    rate = np.broadcast_to(np.asarray(rate, dtype=np.float64), (n,))
    hits = np.nonzero(r.random(n) < rate / SR)[0]
    x = np.zeros(n)
    x[hits] = np.exp(r.normal(0.0, amp_sigma, len(hits))) * r.choice([-1.0, 1.0], len(hits))
    return x


def _stick_slip(rate_curve, n, r, jitter=0.25):
    """quasi-periodic stick-slip impulse train following a rate curve (Hz), jittered amplitude"""
    rt = np.maximum(rate_curve, 1.0) * (1.0 + jitter * dsp.ctrl_noise(n, r, 25.0, rate=2000.0))
    ph = dsp.phase_cycles(np.maximum(rt, 1.0), n, r.uniform())
    k = np.floor(ph)
    hit = np.nonzero(np.diff(k, prepend=k[0]) > 0)[0]
    x = np.zeros(n)
    x[hit] = np.exp(r.normal(0.0, 0.35, len(hit)))
    return x


def _pad_thud(r, weight=1.0, dur=0.16):
    """soft padded paw on wood: low modal thump, soft pad noise, a faint fur tick"""
    n = n_of(dur)
    t = t_axis(n)
    f = r.uniform(85.0, 130.0) / weight ** 0.3
    y = dsp.modal([f, f * 1.93, f * 3.1, f * 4.6], [1.0, 0.5, 0.25, 0.1], [0.09, 0.06, 0.04, 0.03], n, r=r,
                  attack=0.004)
    pad = dsp.lowpass(r.standard_normal(n), 380.0, 2) * _dec(n, 0.012, 0.003)
    y = _nrm(y) + 0.7 * _nrm(pad)
    k = n_of(0.012)
    d = n_of(r.uniform(0.002, 0.006))
    tick = dsp.highpass(r.standard_normal(k), 3000.0, 2) * np.exp(-t[:k] / 0.003)
    y[d:d + k] += 0.07 * _nrm(tick)[: len(y[d:d + k])]
    if r.uniform() < 0.3:     # a floorboard answers
        cr = dsp.modal([r.uniform(450, 900)], [1.0], [0.05], n, r=r, attack=0.003)
        y += 0.12 * _nrm(cr)
    return _nrm(y)


# ======================================================================================  prologue / scene 1
def tiptoe(ev, r):
    steps = int(ev.get("n") or 8)
    dur = float(ev.get("dur") or 3.0)
    y = np.zeros(n_of(dur + 0.35))
    dt = dur / max(steps, 1)
    for i in range(steps):
        ts = i * dt + (r.uniform(-0.12, 0.12) * dt if i > 0 else 0.0)
        lv = r.uniform(0.6, 1.0) * (0.85 if i % 2 else 1.0)
        dsp.place(y, _pad_thud(r, weight=0.55), n_of(ts), lv)
    return _nrm(y), 0


def _scrape(r, v, n):
    """porcelain on lacquer driven by a push-velocity curve v (0..1): stick-slip grains ringing short
    lacquer/porcelain resonances, friction hiss, a faint porcelain whine on the strongest pushes"""
    grains = _impulses(20.0 + 140.0 * v, n, r, 0.5) * v
    ring = dsp.resonator_bank(grains, [1350 * r.uniform(0.95, 1.05), 2210, 2350, 3050, 3120, 3900, 4480],
                              [0.03, 0.03, 0.12, 0.025, 0.1, 0.02, 0.07], [0.6, 0.8, 0.5, 0.7, 0.35, 0.5, 0.25])
    fric = dsp.bandpass(r.standard_normal(n), 900.0, 4200.0, 2) * v ** 1.5 * (1.0 + 0.4 * dsp.ctrl_noise(n, r, 30.0))
    table = dsp.lowpass(np.abs(grains), 500.0, 2)
    whine_env = v ** 3 * np.clip(0.5 + dsp.ctrl_noise(n, r, 1.5, rate=500.0), 0.0, None)
    whine = np.sin(TWO_PI * dsp.phase_cycles(2900.0 * (1.0 + 0.02 * dsp.ctrl_noise(n, r, 6.0, rate=500.0)), n))
    y = 1.0 * _nrm(ring) + 0.35 * _nrm(fric) + 0.25 * _nrm(table) + 0.07 * whine * whine_env / (whine_env.max() + 1e-9)
    return dsp.highpass(y, 150.0, 2)


def cup_slide(ev, r):
    """porcelain cup pushed slowly across lacquer in a few nudges over ev['dur']"""
    dur = float(ev.get("dur") or 2.5)
    n = n_of(dur + 0.2)
    t = t_axis(n)
    v = np.zeros(n)
    starts = np.sort(r.uniform(0.0, 1.0, 4)) * (dur - 0.5)
    starts[0] = 0.0
    for s in starts:
        L = r.uniform(0.35, 0.6)
        u = (t - s) / L
        v += np.where((u > 0) & (u < 1), np.sin(np.pi * np.clip(u, 0, 1)) ** 1.5, 0.0) * r.uniform(0.6, 1.0)
    y = _scrape(r, np.clip(v, 0.0, 1.0), n)
    return _nrm(dsp.fade(y, 0.02, 0.1)), 0


def cup_nudge(ev, r):
    """one paw nudge of the cup toward the table edge: soft paw touch on porcelain + a short (~0.2 s) scrape.
    The nudge just before the fall (within 1 s of cue cup_fall) is longer and wobbly: the foot rocks on the edge."""
    import config
    edge = float(ev.get("frame", 0)) >= config.CUE.get("cup_fall", 1e9) - 24
    L = (0.32 if edge else 0.2) * r.uniform(0.85, 1.15)
    n = n_of(L + 0.15)
    t = t_axis(n)
    u = (t - 0.008) / L
    v = np.where((u > 0) & (u < 1), np.sin(np.pi * np.clip(u, 0, 1)) ** 1.2, 0.0) * r.uniform(0.75, 1.0)
    if edge:     # rocking on the rim: ~8 Hz stutter growing toward the end
        v *= 1.0 - 0.6 * np.clip(u, 0, 1) * (0.5 + 0.5 * np.sin(TWO_PI * dsp.phase_cycles(8.0, n, r.uniform())))
    y = _nrm(_scrape(r, v, n))
    k = n_of(0.05)
    touch = dsp.modal(_CUP[:3] * r.uniform(0.98, 1.02), [1.0, 0.5, 0.3], [0.08, 0.05, 0.04], k, r=r, attack=0.002)
    touch += 0.8 * _nrm(dsp.lowpass(r.standard_normal(k), 600.0, 2)) * _dec(k, 0.006, 0.002)
    y[:k] += 0.35 * _nrm(touch)
    if edge:     # the foot tips on the edge: a small porcelain 'tok' at the end
        m = n_of(0.12)
        tok = dsp.modal(_CUP[:4] * r.uniform(0.98, 1.02), [0.8, 1.0, 0.5, 0.3], [0.12, 0.09, 0.06, 0.04], m, r=r,
                        attack=0.0005)
        dsp.place(y, _nrm(tok), n_of(0.008 + L * 0.92), 0.4)
    return _nrm(dsp.fade(y, 0.0, 0.06)), 0


_CUP = np.array([2350.0, 3120.0, 4480.0, 5750.0, 6900.0])
_CUP_T60 = np.array([0.95, 0.65, 0.45, 0.3, 0.22])


def cup_clink(ev, r):
    """porcelain cup lands on the wooden floor: first impact with floor knock, two bounces, a rocking rattle
    on the rim settling faster and faster, then the ring -- no breakage.  anchor = first impact."""
    dur = 1.5
    n = n_of(dur)
    # contact list (t, level)
    contacts = [(0.0, 1.0), (0.14, 0.5), (0.235, 0.3), (0.30, 0.2)]
    tc, gap, lv = 0.34, 0.05, 0.14
    while gap > 0.009 and tc < 0.8:
        contacts.append((tc, lv))
        tc += gap
        gap *= 0.8
        lv *= 0.86
    exA, exB = np.zeros(n), np.zeros(n)
    k = n_of(0.0012)
    for i, (tt, a) in enumerate(contacts):
        s = n_of(tt)
        burst = r.standard_normal(k) * np.hanning(k + 2)[1:-1] * a
        (exA if (i % 2 == 0 or r.uniform() < 0.3) else exB)[s:s + k] += burst[: len(exA[s:s + k])]
    f = _CUP * r.uniform(0.98, 1.02)
    ringA = dsp.resonator_bank(exA, f, _CUP_T60, [1.0, 0.7, 0.55, 0.35, 0.25]) \
        + dsp.resonator_bank(exA, f * 1.0021, _CUP_T60 * 0.9, [0.6, 0.4, 0.3, 0.2, 0.15])     # doublets beat
    ringB = dsp.resonator_bank(exB, f, _CUP_T60, [0.5, 1.0, 0.4, 0.6, 0.35]) \
        + dsp.resonator_bank(exB, f * 1.0017, _CUP_T60 * 0.9, [0.3, 0.6, 0.25, 0.3, 0.2])
    ring = ringA + ringB
    # wooden floor knocks for the first three contacts
    floor = np.zeros(n)
    for (tt, a) in contacts[:3]:
        m = n_of(0.12)
        kn = dsp.modal([150, 265, 410, 655, 980], [1.0, 0.7, 0.5, 0.3, 0.2], [0.07, 0.05, 0.04, 0.03, 0.02], m, r=r,
                       attack=0.0003)
        th = dsp.lowpass(r.standard_normal(m), 900.0, 2) * _dec(m, 0.008)
        dsp.place(floor, _nrm(kn) + 0.6 * _nrm(th), n_of(tt), a)
    kk = n_of(0.004)
    tick = dsp.highpass(r.standard_normal(kk), 4000.0, 2) * _dec(kk, 0.0007)
    y = _nrm(ring) + 0.45 * floor
    y[:kk] += 0.5 * _nrm(tick)
    y = dsp.highpass(y, 60.0, 2)
    return _nrm(dsp.fade(y, 0.0, 0.3)), 0


# ======================================================================================  scene 2
def moth_flutter(ev, r):
    """tiny soft intermittent wing-flutter bursts (wingbeat ~28-38 Hz)"""
    dur = float(ev.get("dur") or 4.0)
    n = n_of(dur)
    t = t_axis(n)
    env = np.zeros(n)
    tc = r.uniform(0.0, 0.2)
    while tc < dur - 0.2:
        L = r.uniform(0.25, 0.7)
        u = (t - tc) / L
        env += np.where((u > 0) & (u < 1), np.sin(np.pi * np.clip(u, 0, 1)) ** 2, 0.0) * r.uniform(0.5, 1.0)
        tc += L + r.uniform(0.2, 0.9)
    beat = 33.0 * (1.0 + 0.08 * dsp.ctrl_noise(n, r, 2.0, rate=500.0))
    ph = dsp.phase_cycles(beat, n, r.uniform())
    pulse = np.sin(np.pi * (ph % 1.0)) ** 6
    air = dsp.bandpass(r.standard_normal(n), 1500.0, 7000.0, 2)
    flap = dsp.bandpass(r.standard_normal(n), 180.0, 700.0, 2)
    y = env * pulse * (_nrm(air) + 0.35 * _nrm(flap))
    return _nrm(dsp.fade(y, 0.05, 0.1)), 0


def _whoosh(r, dur, f_lo=700.0, f_hi=3500.0, f_end=1200.0, q=1.2, silk=0.3, flutter=0.25):
    n = n_of(dur)
    fc = dsp.env_points([(0, f_lo), (dur * 0.45, f_hi), (dur, f_end)], n, "cos")
    x = r.standard_normal(n)
    y = dsp.tv_biquad(x, "bp", fc, q, block=128)
    env = dsp.env_points([(0, 0), (dur * 0.4, 1.0), (dur, 0)], n, "cos") ** 1.5
    fl = 1.0 - flutter * (0.5 + 0.5 * np.sin(TWO_PI * dsp.phase_cycles(r.uniform(12.0, 18.0), n)))
    hs = dsp.highpass(r.standard_normal(n), 5000.0, 2)
    return env * fl * (_nrm(y) + silk * _nrm(hs))


def pounce(ev, r):
    """claw scrabble on wood (~0.3 s pre-roll), then the push-off thump + leap whoosh.  anchor = push-off"""
    pre = 0.3
    n = n_of(pre + 0.6)
    y = np.zeros(n)
    t = t_axis(n)
    npre = n_of(pre)
    rate = np.zeros(n)
    rate[:npre] = 25.0 + 70.0 * (t[:npre] / pre)
    clicks = _impulses(rate, n, r, 0.45)
    y += 0.7 * dsp.resonator_bank(clicks, [1650, 2400, 3300, 5200], [0.012, 0.01, 0.008, 0.005], [1, 0.8, 0.6, 0.4])
    y += 0.25 * dsp.highpass(clicks, 4000.0, 2)
    for ts in (0.04, 0.15, 0.24):
        dsp.place(y, _pad_thud(r, 1.2) * 0.35, n_of(ts))
    y = _nrm(y) * 0.55
    m = n_of(0.2)
    tm = t_axis(m)
    thump = np.sin(TWO_PI * dsp.phase_cycles(90.0 * (1 + 0.5 * np.exp(-tm / 0.015)), m)) * _dec(m, 0.05, 0.002)
    thump += 0.6 * _nrm(dsp.lowpass(r.standard_normal(m), 400.0, 2)) * _dec(m, 0.02, 0.001)
    dsp.place(y, _nrm(thump), npre, 1.0)
    dsp.place(y, _whoosh(r, 0.45, 600.0, 2600.0, 900.0, q=1.0), npre + n_of(0.01), 0.75)
    return _nrm(y), npre


def sleeve_whoosh(ev, r):
    """long silk sleeves swishing: overlapping swooshes with moving bandpass, silky high sheen"""
    y = np.zeros(n_of(1.4))
    for (ts, d, lv) in ((0.0, 0.6, 1.0), (0.22, 0.7, 0.8), (0.5, 0.8, 0.6)):
        dsp.place(y, _whoosh(r, d, r.uniform(600, 900), r.uniform(2800, 4200), r.uniform(1000, 1500), q=1.1,
                             silk=0.45), n_of(ts), lv)
    return _nrm(dsp.fade(y, 0.01, 0.1)), 0


def land_soft(ev, r):
    """soft landing: body thump + pads, then cloth rustle and sleeves settling.  anchor = thump"""
    pre = 0.05
    n = n_of(pre + 0.8)
    y = np.zeros(n)
    dsp.place(y, _whoosh(r, pre + 0.03, 1500, 3500, 2500, q=0.9) * 0.2, 0)
    a = n_of(pre)
    m = n_of(0.25)
    tm = t_axis(m)
    body = np.sin(TWO_PI * dsp.phase_cycles(72.0 * (1 + 0.35 * np.exp(-tm / 0.02)), m)) * _dec(m, 0.07, 0.003)
    body += 0.7 * _nrm(dsp.lowpass(r.standard_normal(m), 260.0, 2)) * _dec(m, 0.045, 0.002)
    dsp.place(y, _nrm(body), a, 1.0)
    dsp.place(y, _pad_thud(r, 1.3), a + n_of(0.018), 0.45)
    k = n_of(0.45)
    rus = dsp.bandpass(r.standard_normal(k), 1200.0, 6000.0, 2) * (1.0 + 1.5 * np.abs(dsp.crackle(k, r, 150.0, hp=0)))
    rus *= dsp.env_points([(0, 0), (0.02, 1.0), (0.12, 0.5), (0.45, 0.0)], k, "cos")
    dsp.place(y, _nrm(rus) * 0.35, a + n_of(0.01))
    dsp.place(y, _whoosh(r, 0.3, 900, 2200, 1200, q=1.0, silk=0.2) * 0.25, a + n_of(0.12))
    return _nrm(dsp.fade(y, 0.0, 0.1)), a


def _pat(r):
    """one muffled paw-pad pat"""
    n = n_of(0.07)
    y = dsp.bandpass(r.standard_normal(n), 150.0, 1100.0 * r.uniform(0.8, 1.2), 2) * _dec(n, r.uniform(0.01, 0.018), 0.0015)
    y += 0.5 * _nrm(dsp.modal([r.uniform(200, 340)], [1.0], [0.04], n, r=r, attack=0.002))
    return _nrm(y)


def applause(ev, r):
    """soft paw-pad patting of several cats (stereo)"""
    dur = float(ev.get("dur") or 2.0)
    n = n_of(dur + 0.2)
    out = np.zeros((2, n))
    bank = [_pat(r) for _ in range(12)]
    cats_ = 5
    pans = np.linspace(-0.7, 0.7, cats_) + r.uniform(-0.1, 0.1, cats_)
    for c in range(cats_):
        rate = r.uniform(4.2, 6.2)
        tc = r.uniform(0.0, 0.25)
        gl, gr = dsp.pan_gains(pans[c])
        cv = r.uniform(0.6, 1.0)
        while tc < dur:
            u = tc / dur
            env = min(1.0, 0.35 + 2.5 * u) * (1.0 - 0.75 * max(0.0, (u - 0.55) / 0.45))
            p = bank[r.integers(len(bank))]
            lv = env * cv * r.uniform(0.7, 1.0)
            dsp.place(out, np.vstack([p * gl, p * gr]), n_of(tc), lv)
            tc += (1.0 / rate) * r.uniform(0.85, 1.15)
    return _nrm(dsp.fade(out, 0.0, 0.1)), 0


# ======================================================================================  scene 3
def _plip(r, f0=1100.0, dur=0.08, rise=0.9, tau=0.022):
    n = n_of(dur)
    t = t_axis(n)
    f = f0 * (1.0 + rise * (1.0 - np.exp(-t / 0.012)))
    return np.sin(TWO_PI * dsp.phase_cycles(f, n)) * _dec(n, tau, 0.0008)


def water_dip(ev, r):
    """a toe touching water: small plip, a couple of ripple drips, soft lapping.  anchor = plip"""
    n = n_of(0.9)
    y = np.zeros(n)
    y[: n_of(0.09)] += _plip(r, r.uniform(1000, 1200), 0.09)
    k = n_of(0.015)
    sp = dsp.highpass(r.standard_normal(k), 2500.0, 2) * _dec(k, 0.003)
    y[:k] += 0.25 * _nrm(sp)
    for (ts, lv) in ((0.09, 0.35), (0.2, 0.25), (0.34, 0.16), (0.47, 0.1)):
        dsp.place(y, _plip(r, r.uniform(1500, 2500), 0.05, rise=r.uniform(0.5, 1.0), tau=0.012), n_of(ts), lv)
    m = n_of(0.7)
    lap = dsp.bandpass(r.standard_normal(m), 250.0, 1200.0, 2) * (0.5 + 0.5 * dsp.ctrl_noise(m, r, 6.0, rate=500.0))
    lap *= dsp.env_points([(0, 0), (0.05, 1.0), (0.7, 0.0)], m, "cos")
    dsp.place(y, _nrm(lap) * 0.08, n_of(0.03))
    return _nrm(dsp.fade(y, 0.0, 0.1)), 0


def paw_shake(ev, r):
    """rapid paw flicks (~9 Hz) throwing water droplets"""
    flicks = 5
    n = n_of(1.0)
    y = np.zeros(n)
    tc = 0.0
    for i in range(flicks):
        m = n_of(0.06)
        fl = dsp.bandpass(r.standard_normal(m), 700.0, 4500.0, 2) * dsp.env_points(
            [(0, 0), (0.006, 1.0), (0.06, 0.0)], m, "cos")
        fl += 0.4 * _nrm(dsp.lowpass(r.standard_normal(m), 300.0, 2)) * _dec(m, 0.015, 0.003)
        dsp.place(y, _nrm(fl), n_of(tc), (1.0 - 0.1 * i) * r.uniform(0.8, 1.0))
        for _ in range(r.integers(2, 4)):
            td = tc + r.uniform(0.03, 0.35)
            dsp.place(y, _plip(r, r.uniform(2200, 4000), 0.03, rise=0.5, tau=0.006), n_of(td), r.uniform(0.12, 0.3))
        tc += (1.0 / 9.0) * r.uniform(0.9, 1.1)
    return _nrm(dsp.fade(dsp.highpass(y, 100.0, 2), 0.0, 0.05)), 0


# ======================================================================================  scene 4
def fan(ev, r):
    """silk round fan swishing rhythmically (~0.9 s period, alternating strokes)"""
    dur = float(ev.get("dur") or 8.0)
    n = n_of(dur + 0.6)
    y = np.zeros(n)
    bank = []
    for i in range(6):
        d = r.uniform(0.42, 0.52)
        bank.append(_whoosh(r, d, r.uniform(400, 550), r.uniform(1100, 1600), r.uniform(600, 800), q=0.8,
                            silk=0.12, flutter=0.1))
    tc, k = 0.0, 0
    period = r.uniform(0.85, 0.95)
    while tc < dur:
        lv = (1.0 if k % 2 == 0 else 0.7) * r.uniform(0.85, 1.0)
        dsp.place(y, bank[r.integers(len(bank))], n_of(tc), lv)
        tc += (period / 2.0) * r.uniform(0.92, 1.08)
        k += 1
    y = dsp.eq_chain(y, [("hp", 200.0, 0.0, 0.7), ("highshelf", 5000.0, -4.0, 0.7)])
    return _nrm(dsp.fade(y, 0.5, 0.6)), 0


def _chime(r, f, dur=0.6, lv=1.0):
    n = n_of(dur)
    y = dsp.modal([f, f * 2.76, f * 5.4], [1.0, 0.25, 0.08], [dur * 0.9, dur * 0.4, dur * 0.2], n, r=r, attack=0.001)
    return y * lv


def boop(ev, r):
    """tiny nose touch: a 'mip' and a very small chime sparkle (D7 F#7 A7)"""
    mip = cats.meow(600.0, 0.11, who=ev.get("who") or "kitten", size=0.9, contour="mip", r=r)
    y = np.zeros(n_of(0.8))
    dsp.place(y, mip, 0, 1.0)
    for i, f in enumerate((2349.3, 2960.0, 3520.0)):
        dsp.place(y, _chime(r, f, 0.55, 1.0), n_of(0.05 + 0.035 * i), 0.14 - 0.03 * i)
    return _nrm(dsp.fade(y, 0.0, 0.1)), 0


def paw_tap(ev, r):
    """a quick soft tap on a paw"""
    n = n_of(0.15)
    y = _pad_thud(r, 0.8, 0.15)
    k = n_of(0.01)
    cl = dsp.bandpass(r.standard_normal(k), 1200.0, 4000.0, 2) * _dec(k, 0.002)
    y[:k] += 0.3 * _nrm(cl)
    return _nrm(y[:n]), 0


# ======================================================================================  scene 5 / epilogue
def basket_creak(ev, r):
    """wicker creaking as a cat squeezes in: stick-slip creaks through woven-reed resonances + fibre crackle"""
    dur = 1.3
    n = n_of(dur)
    t = t_axis(n)
    rate = np.zeros(n)
    amp = np.zeros(n)
    for (ts, d) in ((0.0, 0.2), (0.3, 0.26), (0.62, 0.16), (0.88, 0.25)):
        u = (t - ts) / d
        m = (u > 0) & (u < 1)
        f0, f1 = r.uniform(70, 140), r.uniform(150, 320)
        rate[m] += f0 + (f1 - f0) * u[m]
        amp[m] += np.sin(np.pi * u[m]) ** 0.7 * r.uniform(0.6, 1.0)
    ex = _stick_slip(np.maximum(rate, 40.0), n, r) * amp
    body = dsp.resonator_bank(ex, [420 * r.uniform(0.9, 1.1), 780, 1350, 2100, 3300], [0.04, 0.035, 0.03, 0.02, 0.015],
                              [1.0, 0.8, 0.7, 0.45, 0.3])
    fib = dsp.crackle(n, r, 60.0 * (amp > 0.1) + 5.0, amp_sigma=0.8, hp=2000.0) * (0.3 + amp)
    y = _nrm(body) + 0.25 * _nrm(fib)
    return _nrm(dsp.fade(dsp.highpass(y, 150.0, 2), 0.005, 0.1)), 0


def blow(ev, r):
    """a soft short breath puff"""
    n = n_of(0.38)
    y = dsp.eq_chain(r.standard_normal(n), [("bp", 1100.0, 0.0, 0.8), ("peak", 2500.0, 3.0, 1.0)])
    y *= dsp.env_points([(0, 0), (0.025, 1.0), (0.1, 0.7), (0.38, 0.0)], n, "cos")
    k = n_of(0.01)
    p = dsp.lowpass(r.standard_normal(k), 1500.0, 2) * _dec(k, 0.002)
    y[:k] += 0.4 * _nrm(p) * dsp.peak(y)
    return _nrm(dsp.highpass(y, 150.0, 2)), 0


def tea_set(ev, r):
    """ceramic tea bowl set down on wood: soft clunk, the foot settling, a short ceramic ring.  anchor = clunk"""
    n = n_of(0.7)
    y = np.zeros(n)
    for (ts, lv) in ((0.0, 1.0), (0.011, 0.4), (0.07, 0.12)):
        m = n_of(0.5)
        wood = dsp.modal([180, 330, 520, 800], [1.0, 0.7, 0.4, 0.2], [0.07, 0.05, 0.04, 0.03], m, r=r, attack=0.0008)
        th = dsp.lowpass(r.standard_normal(m), 700.0, 2) * _dec(m, 0.01, 0.0008)
        cer = dsp.modal(np.array([1180, 2890, 5100]) * r.uniform(0.99, 1.01), [1.0, 0.5, 0.25], [0.35, 0.2, 0.12], m,
                        r=r, attack=0.0005)
        c = _nrm(wood) + 0.5 * _nrm(th) + 0.3 * _nrm(cer)
        dsp.place(y, c, n_of(ts), lv)
    return _nrm(dsp.fade(dsp.highpass(y, 60.0, 2), 0.0, 0.15)), 0


def seal_thump(ev, r):
    """a seal stamped on silk + paper: faint paper whisper, then a firm low-mid thump with the seal's wooden knock
    and a papery press/crinkle, then the tacky lift.  anchor = thump"""
    pre = 0.12
    n = n_of(pre + 0.95)
    y = np.zeros(n)
    k0 = n_of(pre)
    wh = dsp.bandpass(r.standard_normal(k0), 1500.0, 6000.0, 2) * dsp.env_points([(0, 0), (pre, 1.0)], k0, "lin")
    y[:k0] += 0.035 * _nrm(wh)
    m = n_of(0.35)
    tm = t_axis(m)
    thump = dsp.modal([85, 150, 232, 340], [1.0, 0.7, 0.45, 0.25], [0.14, 0.09, 0.07, 0.05], m, r=r,
                      attack=0.0015, fdrift=1.0 + 0.12 * np.exp(-tm / 0.01))
    punch = dsp.lowpass(r.standard_normal(m), 320.0, 2) * _dec(m, 0.025, 0.001)
    knock = dsp.modal([620, 1150, 1830], [1.0, 0.5, 0.25], [0.05, 0.035, 0.02], m, r=r, attack=0.0005)
    hit = _nrm(thump) + 0.7 * _nrm(punch) + 0.35 * _nrm(knock)
    dsp.place(y, hit, k0, 1.0)
    kc = n_of(0.28)
    cr = dsp.crackle(kc, r, np.linspace(900.0, 100.0, kc), amp_sigma=0.8, hp=1500.0)
    cr = dsp.lowpass(cr, 7000.0, 2) * dsp.env_points([(0, 1.0), (0.28, 0.0)], kc, "lin")
    dsp.place(y, _nrm(cr) * 0.2, k0 + n_of(0.004))
    kl = n_of(0.09)
    lift = dsp.tv_biquad(r.standard_normal(kl), "bp", np.geomspace(1200.0, 4500.0, kl), 1.5, block=64)
    lift *= dsp.env_points([(0, 0), (0.01, 1.0), (0.09, 0.0)], kl, "cos")
    dsp.place(y, _nrm(lift) * 0.12, k0 + n_of(0.5))
    return _nrm(dsp.fade(dsp.highpass(y, 40.0, 2), 0.0, 0.1)), k0


EVENTS = {
    "tiptoe": tiptoe,
    "cup_slide": cup_slide,
    "cup_nudge": cup_nudge,
    "cup_clink": cup_clink,
    "moth_flutter": moth_flutter,
    "pounce": pounce,
    "sleeve_whoosh": sleeve_whoosh,
    "land_soft": land_soft,
    "applause": applause,
    "water_dip": water_dip,
    "paw_shake": paw_shake,
    "fan": fan,
    "boop": boop,
    "paw_tap": paw_tap,
    "basket_creak": basket_creak,
    "blow": blow,
    "tea_set": tea_set,
    "seal_thump": seal_thump,
}
