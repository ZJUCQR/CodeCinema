"""
sfx.py -- per-event sound effects for Duel in the Silver Grass (all procedural, seeded, varied per event).

render_event(e, ctx) -> Clip | None      one event (normalised by timeline.py) -> audio + placement info
render_all(doc)       -> dict            places every event on the film timeline (sfx stem + reverb send)
render_ambience(doc)  -> see ambience.py (re-exported here for convenience)

Clip.anchor is the sample that must land exactly on the event time (impacts: the transient;
whooshes: the swing start, with a short pre-roll before it; swells: their peak).

Design notes
    * metal: inharmonic modal CLUSTERS (groups of close modes sharing a decay -> the tail beats as a group, never a
      single long pure 'ting'; clash T60 <= 0.8 s, clash_heavy <= 1.0 s, x1.5 in a slow-motion bloom) + crack +
      body thump + grind.  The perfect deflect has no tuned partials: a harder crack, a short dense cluster
      (T60 <= 0.45 s), a low air 'whump', a brief spark shimmer; the bloom is the reverb + the score's drum drop-out
    * every event has its own RNG (type, frame, index) -> reproducible yet never identical
    * distance: the APPARENT distance dist * 35 / lens (the cut's focal length from events.json cuts[]: sound
      perspective follows the shot size), gain (2.5/d)^0.5 floored at -10 dB, air lowpass beyond 10 m, wetter send;
      the click motif (tsuba_click), fire ignite, thunder, bells, stingers, slow-motion swell ignore distance
    * slow-motion windows (timeline.slowmo_windows: config.SLOWMO united with the slowmo events): events inside a
      short window are rendered at 0.72x speed; picture-locked durations are pre-shortened so the slowed clip still
      covers exactly [t, t + D]
    * the Raikiri breath: rolling thunder is faded out before it; the inhale / the swing go to the `exempt` buffer
    * wet ground after the rain starts: steps / lands / rolls / skids get splash layers
"""

import numpy as np

import dsp
import instruments as inst
import timeline as tl
from dsp import SR, n_of, t_axis, TWO_PI

SLOWMO_RATE = 0.72
# Level hierarchy trims (dB), measured with `audition.py --calib` (max momentary loudness of the middle
# variation, dry, centred, 6 m).  Targets: raikiri -10.5 > thunder near / fire ignite -12.5 > clash_heavy -13.5 >
# lightning -13 > perfect deflect -14.5 > sword break / stinger / shockwave -15 > grass shear / rain split -16 >
# clash (0.7) / hat cut / fire burst -18 > kunai deflect / draw -21 > whooshes -23..-29 > foley -24..-27 >
# far thunder -25 > tsuba click -26 > steps -31..-32.  (The master adds ~+6 dB on the way to -14 LUFS.)
TRIM_DB = {
    "raikiri": -1.9, "fire_ignite": -2.4, "thunder_near": -2.0, "thunder_mid": -0.9, "thunder_far": -5.9,
    "perfect_deflect": -0.5, "stinger": 1.7, "shockwave": 2.4, "rain_split": 2.6, "slowmo": -0.9,
    "grass_shear": 3.2, "kunai_deflect": -1.7, "sheathe": -4.6, "heartbeat": -1.8, "steam_hiss": -0.9,
    "fire_burst": 4.2, "blade_lock": -1.0, "draw": 2.1, "spear_draw": -1.0, "tree_split": 6.4, "haori_shed": 1.7,
    "whoosh_spear": 1.7, "kick": 4.1, "body_fall": 2.1, "whoosh_katana": 2.0, "drip": -0.5, "dash": 1.3,
    "electric_crackle": 2.6, "spear_spin": 0.3, "skid": 2.1, "land": 3.4, "roll": 2.4, "spear_pull": 2.2,
    "jump": 1.9, "kunai_throw": 2.2, "kneel": 3.6, "tsuba_click": 4.7, "whoosh_body": 2.8, "hit": 5.9,
    "whoosh_kunai": 4.4, "step": 5.4, "lightning_strike": -2.5,
}


# story-beat emphasis by tag (the first thunder announces the storm; it must read over the act II music)
TAG_TRIM_DB = {"thunder_first": 4.0}


def trim_key(e):
    """TRIM_DB key of an event: type, or type_subkind for whooshes (weapon) and thunder (distance)"""
    t = e["type"]
    if t == "whoosh":
        w = e.get("weapon", "katana")
        w = "spear" if w in ("spear", "yari", "shaft", "polearm") else ("kunai" if w in ("kunai", "shuriken", "knife", "dart")
                                                                       else ("body" if w in ("body", "kick", "cloth", "fist", "hand", "arm") else "katana"))
        return f"whoosh_{w}"
    if t == "thunder":
        return f"thunder_{e.get('distance', 'far')}"
    return t


class Clip:
    __slots__ = ("audio", "anchor", "send", "reverb", "duck", "spatial", "width", "name", "ignore_dist", "gain",
                 "breath_exempt", "t_place")

    def __init__(self, audio, anchor=0, send=0.12, reverb="field", duck=None, spatial=False, width=1.0,
                 name="", ignore_dist=False, gain=1.0, breath_exempt=False):
        self.audio = audio
        self.anchor = int(anchor)
        self.send = send
        self.reverb = reverb
        self.duck = duck              # (depth_db, hold_s, release_s)
        self.spatial = spatial        # audio already stereo-positioned (apply balance pan only)
        self.width = width
        self.name = name
        self.ignore_dist = ignore_dist
        self.gain = gain
        self.breath_exempt = breath_exempt   # plays through the 'breath' dip before a story hit (the inhale itself)
        self.t_place = None           # optional override of the placement time (s), e.g. a sheathe re-timed to its click


# =====================================================================================  building blocks
def _nz(r, n):
    return r.standard_normal(n)


def _norm(x, lvl=1.0):
    return dsp.normalize(x, lvl)


def _decay_burst(r, n, lo, hi, tau, attack=0.0005, order=2):
    t = t_axis(n)
    e = np.exp(-t / tau) * np.clip(t / max(attack, 1e-5), 0, 1)
    if lo is None:
        y = dsp.lowpass(_nz(r, n), hi, order)
    elif hi is None:
        y = dsp.highpass(_nz(r, n), lo, order)
    else:
        y = dsp.bandpass(_nz(r, n), lo, hi, order)
    return y * e


def _thump(r, f0=110.0, dur=0.25, drop=0.6, tau=0.05, noise=0.35):
    n = n_of(dur)
    t = t_axis(n)
    f = f0 * (1.0 + drop * np.exp(-t / 0.018))
    body = np.sin(TWO_PI * dsp.phase_cycles(f, n)) * np.exp(-t / tau) * np.clip(t / 0.0015, 0, 1)
    nz = dsp.lowpass(_nz(r, n), f0 * 2.5, 2) * np.exp(-t / (tau * 0.6))
    return dsp.fade(body + noise * nz / (dsp.peak(nz) + 1e-9), 0.0, dur * 0.3)    # no truncation click


def _strat_log(r, lo, hi, n):
    """n frequencies in [lo, hi], one per log-spaced bin (jittered): varied per event, but a CONSISTENT spectral
    envelope -- purely random draws sometimes piled several long modes into one octave (+-2 dB swings in a scene)"""
    edges = np.log(lo) + (np.arange(n) + r.uniform(0.15, 0.85, n)) * (np.log(hi) - np.log(lo)) / n
    return np.exp(edges)


def _modal_cloud(r, n, lo, hi, count, t60_hi, t60_lo, tilt=0.6, doublet=0.6, fixed=None):
    freqs = _strat_log(r, lo, hi, count)
    if fixed is not None:
        freqs = np.concatenate([np.asarray(fixed, float), freqs])
    amps = r.uniform(0.35, 1.0, len(freqs)) * (freqs / lo) ** (-tilt)
    t60 = np.clip(t60_hi * (freqs / lo) ** (-0.7), t60_lo, t60_hi) * r.uniform(0.7, 1.3, len(freqs))
    y = dsp.modal(freqs, amps, t60, n, r=r)
    if doublet:
        y += dsp.modal(freqs * (1 + r.uniform(0.0006, 0.0035, len(freqs))), amps * doublet, t60 * 0.85, n, r=r)
    return y


def _stereo_pair(fn):
    """call a mono generator twice (independent randomness) -> decorrelated stereo"""
    a = fn()
    b = fn()
    m = min(len(a), len(b))
    return np.vstack([a[:m], b[:m]])


def _crackle(r, n, rate, hp=1500.0, sigma=0.9, dmin=0.0002, dmax=0.0025):
    return dsp.crackle(n, r, rate, amp_sigma=sigma, dur_range=(dmin, dmax), hp=hp)


def _env_rate(n, points):
    return dsp.env_points(points, n, "lin")


def _whoosh_core(r, dur, pre, t_peak, f0, fp, f1, q=1.8, whistle=0.3, wq=9.0, body=0.0, flutter=0.0, rise=2.2):
    """band-passed noise with Doppler-like centre sweep; returns mono with peak at t_peak (s)"""
    n = n_of(dur)
    t = t_axis(n)
    tp = max(t_peak, 0.01)
    jit = r.uniform(0.9, 1.1)
    f0, fp, f1 = f0 * jit, fp * jit, f1 * jit
    fc = np.where(t < tp, f0 * (fp / f0) ** np.clip(t / tp, 0, 1),
                  fp * (f1 / fp) ** np.clip((t - tp) / max(dur - tp, 1e-3), 0, 1))
    e = np.where(t < tp, np.clip(t / tp, 0, 1) ** rise, np.exp(-(t - tp) / max((dur - tp) / 3.8, 1e-3)))
    main = dsp.tv_biquad(_nz(r, n), "bp", fc, q, block=64)
    y = main / (dsp.peak(main) + 1e-9)
    if whistle > 0:
        w = dsp.tv_biquad(_nz(r, n), "bp", np.minimum(fc * 1.75, 16000), wq, block=64)
        y += whistle * w / (dsp.peak(w) + 1e-9)
    if body > 0:
        b = dsp.tv_biquad(_nz(r, n), "lp", np.maximum(fc * 0.3, 60), 0.9, block=64)
        y += body * b / (dsp.peak(b) + 1e-9)
    if flutter > 0:
        fl = 0.5 + 0.5 * np.sin(TWO_PI * dsp.phase_cycles(flutter * (1 + 0.15 * dsp.lp_noise(n, r, 3.0)), n))
        y *= 0.55 + 0.45 * fl
    return y * e


def _grass_crunch(r, dur=0.12, density=1500.0, hp=1800.0, level=1.0):
    n = n_of(dur)
    t = t_axis(n)
    rate = density * np.exp(-t / (dur * 0.35))
    c = _crackle(r, n, rate, hp=hp, sigma=0.8)
    sw = _decay_burst(r, n, 900, 5500, dur * 0.4, attack=0.008)
    y = c / (dsp.peak(c) + 1e-9) + 0.5 * sw / (dsp.peak(sw) + 1e-9)
    return y * level


def _splash(r, dur=0.25, level=1.0):
    n = n_of(dur)
    t = t_axis(n)
    sq = dsp.bandpass(_nz(r, n), 250, 1600, 2) * np.exp(-t / 0.05) * (0.6 + 0.4 * np.abs(dsp.lp_noise(n, r, 60)))
    y = sq / (dsp.peak(sq) + 1e-9)
    for _ in range(int(r.integers(3, 8))):
        s = n_of(r.uniform(0.0, dur * 0.6))
        m = n_of(r.uniform(0.012, 0.035))
        if s + m >= n:
            continue
        f0 = r.uniform(1400, 4200)
        tt = t_axis(m)
        ch = np.sin(TWO_PI * dsp.phase_cycles(f0 * (1 + 1.2 * tt / tt[-1]), m)) * np.exp(-tt / (m / SR / 3))
        y[s:s + m] += r.uniform(0.2, 0.6) * ch
    spray = dsp.highpass(_nz(r, n), 2500, 2) * np.exp(-t / 0.07)
    y += 0.3 * spray / (dsp.peak(spray) + 1e-9)
    return y * level


def _cloth(r, dur=0.3, fc=900.0, flutter=35.0, level=1.0):
    n = n_of(dur)
    e = dsp.env_points([(0, 0), (dur * 0.2, 1.0), (dur, 0.0)], n, "cos")
    y = dsp.bandpass(_nz(r, n), 150, fc * 2, 2)
    am = 0.5 + 0.5 * np.sin(TWO_PI * dsp.phase_cycles(flutter * (1 + 0.3 * dsp.lp_noise(n, r, 4.0)), n))
    return y * e * (0.5 + 0.5 * am) / (dsp.peak(y) + 1e-9) * level


def _rumble(r, dur, lp=250.0, bursts=5, atk=(0.2, 0.7), dec=(0.8, 2.2), first=0.0, spread=0.7, recede=None):
    """thunder roll: lowpassed brown noise under a sum of swelling bursts.  spread = fraction of the duration in
    which bursts may start; recede (s) = later bursts weaker by exp(-t0/recede) (a close strike rolling away)"""
    n = n_of(dur)
    t = t_axis(n)
    base = dsp.highpass(dsp.lowpass(dsp.brown(n, r), lp, 3), 28.0, 2)     # no infrasonic (inaudible, eats headroom)
    env = np.zeros(n)
    for i in range(bursts):
        t0 = first if i == 0 else r.uniform(0.1, dur * spread)
        a, d = r.uniform(*atk), r.uniform(*dec)
        amp = r.uniform(0.4, 1.0) * (1.0 if i == 0 else 0.8)
        if recede and i > 0:
            amp *= np.exp(-t0 / recede)
        env += amp * np.clip((t - t0) / a, 0, 1) ** 1.5 * np.exp(-np.maximum(t - t0 - a, 0) / d) * (t >= t0)
    env *= 1.0 + 0.3 * dsp.lp_noise(n, r, 6.0)
    return base * np.maximum(env, 0)


def _crack(r, dur=0.12, hp=700.0, drive=2.5, tau=0.02):
    n = n_of(dur)
    t = t_axis(n)
    y = dsp.highpass(_nz(r, n), hp, 2) * np.exp(-t / tau) * np.clip(t / 0.0006, 0, 1)
    tear = _crackle(r, n, 9000 * np.exp(-t / (dur * 0.4)), hp=1500, sigma=1.1)
    y = y / (dsp.peak(y) + 1e-9) + 0.6 * tear / (dsp.peak(tear) + 1e-9)
    return dsp.fade(np.tanh(drive * y) / np.tanh(drive), 0.0, dur * 0.35)


def _tear(r, dur=0.42, lo=180.0, hi=6000.0, drive=2.2):
    """the rip of a close lightning channel (sound from the whole bolt arriving over a few hundred ms):
    band noise chopped into irregular bursts + dense crackle grains, saturated, ~0.3-0.5 s"""
    n = n_of(dur)
    t = t_axis(n)
    env = np.clip(t / 0.002, 0, 1) * np.exp(-np.maximum(t - 0.035, 0) / (dur * 0.28))
    rips = 0.3 + 0.7 * np.clip(dsp.lp_noise(n, r, 45.0), 0, None) ** 1.5
    body = dsp.bandpass(_nz(r, n), lo, hi, 2) * rips
    grains = _crackle(r, n, 7000 * np.exp(-t / (dur * 0.35)) + 300, hp=None, sigma=1.0, dmin=0.0003, dmax=0.004)
    grains = dsp.bandpass(grains, lo * 1.5, min(hi * 1.3, 16000), 2)
    y = (0.6 * body / (np.std(body) + 1e-9) + 0.4 * grains / (np.std(grains) + 1e-9)) * env
    y = np.tanh(drive * y / (dsp.peak(y) + 1e-9)) / np.tanh(drive)
    return dsp.fade(y, 0.0, dur * 0.3)


def _sizzle(r, dur=0.4, level=1.0):
    """gated HF hiss + dense crackle (air ionising / water flashing to steam).  No tonal 'mains hum' layer: a
    sawtooth buzz reads as sci-fi electricity (and near a blade as an electrified sword -- deny-listed)."""
    n = n_of(dur)
    t = t_axis(n)
    gate = (dsp.lp_noise(n, r, 25.0) > r.uniform(-0.3, 0.3)).astype(float)
    gate = dsp.onepole(gate, 300.0)
    hs = dsp.highpass(_nz(r, n), 3000, 2)
    y = hs / (dsp.peak(hs) + 1e-9) * 0.7 * (0.35 + 0.65 * gate)
    y += 0.8 * _crackle(r, n, 700, hp=2500) / 3.0
    return dsp.fade(y * np.exp(-t / (dur * 0.5)) * level, 0.0, dur * 0.3)


def _ring(r, n, lo, hi, count, t60_hi, t60_lo, tilt=0.5):
    return _modal_cloud(r, n, lo, hi, count, t60_hi, t60_lo, tilt=tilt, doublet=0.5)


# =====================================================================================  weapons / impacts
def sfx_whoosh(e, r, ctx):
    w = e.get("weapon", "katana")
    s = float(np.clip(e["strength"], 0.1, 1.3))
    if w in ("spear", "yari", "shaft", "polearm"):
        pre = 0.07
        y = _whoosh_core(r, 0.55 + 0.2 * s, pre, pre + 0.14, 240, 800 + 500 * s, 300, q=1.3, whistle=0.12, body=0.7 * s)
        lvl = 0.55
    elif w in ("kunai", "shuriken", "knife", "dart"):
        pre = 0.02
        y = _whoosh_core(r, 0.2, pre, 0.06, 1800, 5200, 2600, q=3.0, whistle=0.7, wq=14)
        lvl = 0.3
    elif w in ("body", "kick", "cloth", "fist", "hand", "arm"):
        pre = 0.05
        y = _whoosh_core(r, 0.32, pre, 0.13, 220, 850, 280, q=0.9, whistle=0.0, body=0.35, flutter=38.0)
        lvl = 0.38
    else:
        pre = 0.04
        y = _whoosh_core(r, 0.3 + 0.12 * s, pre, pre + 0.075 + 0.02 * s, 600, 1600 + 700 * s, 750,
                         q=1.9, whistle=0.18, body=0.35 * s)
        lvl = 0.5
    n = len(y)
    d = r.choice([-1.0, 1.0])
    pan_curve = d * np.linspace(-0.3, 0.3, n)
    st = dsp.pan_mono(_norm(y, lvl * (0.45 + 0.55 * s)), pan_curve)
    return Clip(st, n_of(pre), send=0.08, spatial=True, width=1.0, name=f"whoosh_{w}")


def _mode_groups(rr, lo, hi, groups, per_group, spread=0.028):
    """inharmonic mode set as CLUSTERS: `groups` centres log-uniform in [lo, hi], each carrying `per_group` modes
    within +-spread -> every decaying component is a dense beating cluster, never one long sine.
    Returns (freqs, group centre of each mode)"""
    cen = _strat_log(rr, lo, hi, groups)
    f = (cen[:, None] * (1.0 + rr.uniform(-spread, spread, (groups, per_group)))).ravel()
    c = np.repeat(cen, per_group)
    o = np.argsort(f)
    return f[o], c[o]


def _clash_core(r, s, heavy=False, deflect=False, long=False):
    """steel on steel.  Layers: (1) inharmonic modal ring of both blades as clusters of close modes (same mode set
    L/R, different phases / amplitudes -> beating, no single-pitch 'ting'), (2) the blades' low bending modes -- the
    'clang' weight, (3) a band-limited impact burst (not a digital click), (4) the stick-slip 'zing' of the edges
    sliding off each other with a falling resonance, (5) a soft body thump, (6) spark crackle.
    Ring T60 caps: clash 0.8 s, clash_heavy 1.0 s (x1.5 when `long`, the slow-motion bloom).
    deflect=True: the perfect deflect's own identity -- a sharper, harder crack, a SHORT dense inharmonic cluster
    (T60 <= 0.45 s, nothing tuned), a low air 'whump' and a brief spark shimmer; the bloom comes from the reverb and
    the score's drum drop-out."""
    dur = 2.0 if heavy else (1.4 if deflect else 1.4)
    n = n_of(dur)
    t = t_axis(n)
    out = np.zeros((2, n))
    lng = 1.5 if long else 1.0
    if deflect:
        lo, hi, groups, per, t60h, t60l, spread = 2600.0, 11000.0, 9, 4, 0.45, 0.12, 0.035
    elif heavy:
        lo, hi, groups, per, t60h, t60l, spread = 1150.0, 7000.0, 7, 4, 1.0 * lng, 0.25, 0.03
    else:
        lo, hi, groups, per, t60h, t60l, spread = 1000.0 * (1.1 - 0.15 * s), 9000.0, 7, 3, 0.8 * lng, 0.18, 0.025
    ring_seed = r.integers(1 << 30)
    for ch in range(2):
        rr = np.random.default_rng(ring_seed + ch * 7919)
        rr_modes = np.random.default_rng(ring_seed)          # same mode set L/R, different phases/amps
        freqs, cen = _mode_groups(rr_modes, lo, hi, groups, per, spread)
        # members of a cluster share its decay (+-5 %) and have similar weights: the tail beats as a GROUP; the
        # decay falls only gently with frequency so several clusters are still sounding in the tail
        amps = rr_modes.uniform(0.6, 1.0, len(freqs)) * (cen / lo) ** (-0.55) * rr.uniform(0.85, 1.15, len(freqs))
        slope = -0.35 if heavy else -0.65
        t60 = np.clip(t60h * (cen / lo) ** slope, t60l, t60h) * rr_modes.uniform(0.95, 1.05, len(freqs))
        ring = dsp.modal(freqs, amps, t60, n, r=rr, attack=0.0008)
        out[ch] = ring / (dsp.peak(ring) + 1e-9)
    out *= 0.8 if deflect else (0.85 if heavy else 0.62)      # ring vs body: less 2-4 kHz bite, more 'clang'
    # blade bending modes: the weight of the 'clang' (heavier + lower for the elder's two-handed blows)
    bf = np.array([r.uniform(380, 520), r.uniform(690, 900), r.uniform(1000, 1350)]) * (0.8 if heavy else 1.0)
    for ch in range(2):
        bd = dsp.modal(bf * (1 + 0.004 * ch), [1.0, 0.7, 0.5], np.array([0.32, 0.24, 0.17]) * (1.3 if heavy else 1.0),
                       n_of(0.8), r=r, attack=0.0015)
        out[ch, : len(bd)] += (0.55 + 0.1 * heavy) * bd / (dsp.peak(bd) + 1e-9)
    # impact burst: band-limited, a few ms, gently saturated (the deflect: shorter, harder, driven -- a crack)
    k = n_of(0.03)
    if deflect:
        burst = dsp.bandpass(_nz(r, k), 900, 12000, 2) * np.exp(-t[:k] / 0.0013) * np.clip(t[:k] / 0.0002, 0, 1)
        burst = np.tanh(3.2 * burst / (dsp.peak(burst) + 1e-9)) / np.tanh(3.2)
        out[:, :k] += 1.0 * burst
    else:
        burst = dsp.bandpass(_nz(r, k), 700, 7500, 2) * np.exp(-t[:k] / (0.0025 + 0.0015 * heavy)) * np.clip(t[:k] / 0.0003, 0, 1)
        burst = np.tanh(1.8 * burst / (dsp.peak(burst) + 1e-9)) / np.tanh(1.8)
        out[:, :k] += (0.5 + 0.2 * heavy) * burst
    # body thump
    th = _thump(r, 75.0 if heavy else 125.0, 0.35 if heavy else 0.2, 0.7, 0.09 if heavy else 0.05)
    th = th / (dsp.peak(th) + 1e-9) * (0.9 if heavy else 0.45) * (0.6 + 0.4 * s)
    out[:, :len(th)] += th
    if heavy:
        sub = _thump(r, 44.0, 0.6, 0.4, 0.16, noise=0.1)
        out[:, :len(sub)] += 0.4 * sub / (dsp.peak(sub) + 1e-9)
    # the zing: stick-slip grind as the edges slide off each other, resonance falling
    gd = n_of(0.24 if heavy else 0.17)
    g0 = n_of(r.uniform(0.004, 0.012))
    tt = t_axis(gd)
    fz = np.geomspace(r.uniform(6500, 8000), r.uniform(2600, 3400), gd)
    grind = dsp.tv_biquad(_nz(r, gd), "bp", fz, 3.5, block=64) * np.exp(-tt / (gd / SR / 3.2))
    grind *= (dsp.lp_noise(gd, r, 90.0) > 0.25).astype(float) * 0.65 + 0.35
    grind = grind / (dsp.peak(grind) + 1e-9)
    out[0, g0:g0 + gd] += 0.3 * grind
    out[1, g0:g0 + gd] += 0.3 * np.roll(grind, 29)
    # spark crackle (decorrelated L/R)
    m = n_of(0.45)
    for ch in range(2):
        spk = _crackle(r, m, 110 * np.exp(-t[:m] / 0.13), hp=4500, sigma=0.9)
        out[ch, :m] += 0.13 * spk / (dsp.peak(spk) + 1e-9)
    if deflect:
        # low air 'whump' (the pressure of the parry) + a brief spark shimmer (~0.5 s, not a ringing tail)
        m = n_of(0.35)
        wh = dsp.tv_biquad(_nz(r, m), "lp", np.geomspace(420.0, 90.0, m), 0.9, block=64)
        wh *= np.clip(t[:m] / 0.012, 0, 1) * np.exp(-t[:m] / 0.07)
        out[:, :m] += 0.55 * wh / (dsp.peak(wh) + 1e-9)
        sh = dsp.bandpass(r.standard_normal((2, n)), 6000, 14000, 2)
        env = np.clip(t / 0.02, 0, 1) * np.exp(-t / 0.12)
        tw = 0.6 + 0.4 * np.abs(np.sin(TWO_PI * 11.0 * t + r.uniform(0, 6)))
        out += 0.16 * sh * env * tw / (dsp.peak(sh) + 1e-9)
        fl = _whoosh_core(r, 0.25, 0.0, 0.02, 3000, 7000, 2000, q=0.8, whistle=0.0)
        out[:, :len(fl)] += 0.2 * fl / (dsp.peak(fl) + 1e-9)
    return out


def _long(ctx):
    return bool(ctx.get("bloom") or ctx.get("slow", 1.0) != 1.0)


def sfx_clash(e, r, ctx):
    s = float(np.clip(e["strength"], 0.1, 1.3))
    y = dsp.saturate(_norm(_clash_core(r, s, long=_long(ctx)), 1.0), 0.3)
    return Clip(_norm(y, 0.74 * s ** 0.6), 0, send=0.16, spatial=True, width=0.35, name="clash",
                duck=(2.0, 0.05, 0.25) if s > 0.8 else None)


def sfx_clash_heavy(e, r, ctx):
    s = float(np.clip(e["strength"], 0.3, 1.3))
    y = dsp.saturate(_norm(_clash_core(r, s, heavy=True, long=_long(ctx)), 1.0), 0.75)
    return Clip(_norm(y, 1.0 * min(1.0, s) ** 0.5), 0, send=0.22, spatial=True, width=0.45, name="clash_heavy",
                duck=(4.0, 0.08, 0.45))


def sfx_perfect_deflect(e, r, ctx):
    y = dsp.saturate(_norm(_clash_core(r, 1.0, deflect=True), 1.0), 0.25)
    return Clip(_norm(y, 0.73), 0, send=0.24, reverb="hall", spatial=True, width=0.6, name="perfect_deflect",
                duck=(5.0, 0.15, 0.6))


def sfx_blade_lock(e, r, ctx):
    D = e["duration_s"] or 1.5
    D = float(np.clip(D, 0.3, 6.0))
    tail = 0.6
    n = n_of(D + tail)
    t = t_axis(n)
    tension = np.clip(0.35 + 0.65 * t / D, 0, 1) * (t < D) * (1 + 0.25 * dsp.lp_noise(n, r, 3.0))
    fr = dsp.bandpass(_nz(r, n), 900, 6500, 2) * tension * 0.25
    imp = np.zeros(n)
    tc = 0.0
    while tc < D:
        rate = 22 + 30 * tc / D
        tc += r.exponential(1.0 / rate)
        i = n_of(tc)
        if i < n:
            imp[i] += r.uniform(0.4, 1.0) * (1 if r.random() < 0.5 else -1)
    exc = fr + imp
    freqs = _strat_log(r, 750, 5200, 12)
    y = dsp.resonator_bank(exc, freqs, 0.18 * (freqs / 750.0) ** -0.3 * r.uniform(0.85, 1.15, 12),
                           r.uniform(0.6, 1.0, 12) * (freqs / 750.0) ** -0.4)
    y = y / (dsp.peak(y) + 1e-9)
    # squeal: a narrow, wandering band of friction noise (not a pure tone), only in the pressure peaks
    sq_f = r.uniform(1900, 2900) * (1 + 0.012 * dsp.lp_noise(n, r, 5.0))
    sq_g = np.clip(dsp.lp_noise(n, r, 1.5) - 0.5, 0, None) * (t < D)
    sq = dsp.tv_biquad(_nz(r, n), "bp", sq_f, 18.0, block=64)
    y += 0.035 * sq / (np.std(sq) + 1e-9) * dsp.onepole(sq_g, 20.0)
    # strain rumble
    y += 0.25 * dsp.lowpass(dsp.brown(n, r), 180, 2) * tension
    # release shing at the end
    m = n_of(0.35)
    rel = dsp.tv_biquad(_nz(r, m), "bp", np.geomspace(6500, 1800, m), 3.0) * np.exp(-t[:m] / 0.08)
    rel = rel / (dsp.peak(rel) + 1e-9) + 0.5 * _ring(r, m, 2000, 8000, 8, 0.5, 0.1) / 2.0
    s0 = n_of(D - 0.03)
    y[s0:s0 + m] += 0.8 * rel[: n - s0]
    y = dsp.fade(y, 0.02, 0.1)
    return Clip(_norm(y, 0.6), 0, send=0.14, name="blade_lock")


def sfx_hit(e, r, ctx):
    s = float(np.clip(e["strength"], 0.1, 1.2))
    n = n_of(0.35)
    t = t_axis(n)
    sw = dsp.tv_biquad(_nz(r, n), "bp", np.geomspace(2200, 6500, n), 1.4) * np.exp(-t / 0.035) * np.clip(t / 0.003, 0, 1)
    fab = _crackle(r, n, 700 * np.exp(-t / 0.03), hp=3000)
    th = _thump(r, 120.0, 0.35, 0.5, 0.045)
    y = sw / (dsp.peak(sw) + 1e-9) * 0.8 + 0.4 * fab / (dsp.peak(fab) + 1e-9) + 0.6 * th[:n] / (dsp.peak(th) + 1e-9)
    if "plant_blade" in e["tags"]:
        y += 0.5 * _ring(r, n, 1500, 5000, 6, 0.25, 0.05)
    return Clip(_norm(y, 0.42 * (0.5 + 0.5 * s)), 0, send=0.1, name="hit")


def sfx_kick(e, r, ctx):
    pre = 0.09
    wh = _whoosh_core(r, 0.2, 0.0, 0.08, 250, 900, 400, q=0.9, whistle=0.0, body=0.3)
    th = _thump(r, 95.0, 0.4, 0.8, 0.08)
    cl = _decay_burst(r, n_of(0.08), 600, 3000, 0.012)
    n = n_of(pre) + len(th)
    y = np.zeros(n)
    y[: len(wh)] += 0.35 * wh / (dsp.peak(wh) + 1e-9)
    k = n_of(pre)
    y[k: k + len(th)] += th / (dsp.peak(th) + 1e-9)
    y[k: k + len(cl)] += 0.45 * cl / (dsp.peak(cl) + 1e-9)
    return Clip(_norm(y, 0.6), k, send=0.1, name="kick", duck=(2.0, 0.05, 0.3))


# =====================================================================================  body / foley
def _step_one(r, who, s, wet, surface=None):
    heavy = who == "saint"
    if surface == "grass_crawl":
        n = n_of(0.6)
        y = _cloth(r, 0.6, 700, 12.0) * 0.6 + _grass_crunch(r, 0.6, 250, 2200, 0.6)[:n]
        return y * 0.5 * s
    th = _thump(r, 78.0 if heavy else 105.0, 0.16, 0.4, 0.03 if heavy else 0.022, noise=0.6)
    gc = _grass_crunch(r, 0.16, 1800 if heavy else 1300, 1100, 1.0)
    gc = dsp.lowpass(gc, 4200.0, 2)                  # dry stalks, not glassy crackle: keep the 2-8 kHz presence down
    n = max(len(th), len(gc))
    y = np.zeros(n)
    y[: len(th)] += (0.9 if heavy else 0.6) * th / (dsp.peak(th) + 1e-9)
    y[: len(gc)] += 0.55 * gc / (dsp.peak(gc) + 1e-9)
    if wet > 0:
        sp = _splash(r, 0.22, 0.7 * wet)
        y = np.pad(y, (0, max(0, len(sp) - n)))
        y[: len(sp)] += sp
    return y * s


def sfx_step(e, r, ctx):
    s = float(np.clip(e["strength"], 0.1, 1.2))
    y = _step_one(r, e.get("who", "shinobi"), s, ctx["wet"], e.get("surface"))
    lvl = (0.26 if e.get("who") == "saint" else 0.2) * (0.5 + 0.5 * s)
    return Clip(_norm(y, lvl), 0, send=0.06, name="step")


def sfx_dash(e, r, ctx):
    s = float(np.clip(e["strength"], 0.2, 1.2))
    n = n_of(0.6)
    y = np.zeros(n)
    for i, tt in enumerate([0.0, 0.085, 0.17, 0.25]):
        st = _step_one(r, e.get("who", "shinobi"), 1.0 - 0.1 * i, ctx["wet"])
        k = n_of(tt)
        m = min(len(st), n - k)
        y[k:k + m] += st[:m] / (dsp.peak(st) + 1e-9) * (1.0 - 0.12 * i)
    wh = _whoosh_core(r, 0.45, 0.0, 0.12, 250, 1100, 350, q=0.8, whistle=0.0, body=0.4, flutter=30.0)
    y[: len(wh)] += 0.7 * wh / (dsp.peak(wh) + 1e-9)
    gs = _grass_crunch(r, 0.5, 900, 1500, 0.5)
    y[: len(gs)] += 0.5 * gs / (dsp.peak(gs) + 1e-9)
    return Clip(_norm(y, 0.4 * s), 0, send=0.08, name="dash")


def sfx_jump(e, r, ctx):
    n = n_of(0.55)
    y = np.zeros(n)
    st = _step_one(r, e.get("who", "shinobi"), 1.0, ctx["wet"])
    y[: len(st)] += st / (dsp.peak(st) + 1e-9)
    wh = _whoosh_core(r, 0.45, 0.0, 0.14, 300, 1400, 900, q=0.8, whistle=0.0, body=0.3, flutter=28.0)
    y[n_of(0.03): n_of(0.03) + len(wh)] += 0.8 * wh[: n - n_of(0.03)] / (dsp.peak(wh) + 1e-9)
    return Clip(_norm(y, 0.38), 0, send=0.08, name="jump")


def sfx_land(e, r, ctx):
    s = float(np.clip(e["strength"], 0.1, 1.3))
    if "blade_tip" in e["tags"]:
        n = n_of(0.5)
        y = 0.6 * _ring(r, n, 2500, 7000, 8, 0.3, 0.06)
        th = _thump(r, 160.0, 0.2, 0.3, 0.02, noise=0.8)
        y[: len(th)] += 0.8 * th / (dsp.peak(th) + 1e-9)
        return Clip(_norm(y, 0.3), 0, send=0.15, name="land_tip")
    th = _thump(r, 62.0 + 25 * (1 - s), 0.45, 0.9, 0.06 + 0.06 * s)
    gc = _grass_crunch(r, 0.3, 2500, 1200, 1.0)
    n = n_of(0.8)
    y = np.zeros(n)
    y[: len(th)] += th / (dsp.peak(th) + 1e-9)
    y[: len(gc)] += 0.6 * gc / (dsp.peak(gc) + 1e-9)
    cl = _cloth(r, 0.35, 800, 25.0)
    k = n_of(0.12)
    y[k:k + len(cl)] += 0.3 * cl[: n - k]
    if ctx["wet"] > 0:
        sp = _splash(r, 0.4, 1.2 * ctx["wet"])
        y[: len(sp)] += sp
    return Clip(_norm(y, 0.55 * s ** 0.7), 0, send=0.1, name="land", duck=(2.0, 0.05, 0.3) if s > 0.85 else None)


def sfx_roll(e, r, ctx):
    n = n_of(0.8)
    y = np.zeros(n)
    for i, tt in enumerate([0.0, 0.17, 0.34]):
        th = _thump(r, 90.0 + 10 * i, 0.2, 0.4, 0.04, noise=0.7)
        k = n_of(tt)
        y[k:k + len(th)] += (1.0 - 0.25 * i) * th / (dsp.peak(th) + 1e-9)
    cl = _cloth(r, 0.7, 900, 22.0)
    y[: len(cl)] += 0.6 * cl
    gc = _grass_crunch(r, 0.7, 1200, 1500, 0.8)
    y[: len(gc)] += 0.5 * gc / (dsp.peak(gc) + 1e-9)
    if ctx["wet"] > 0:
        for tt in (0.0, 0.2, 0.36):
            sp = _splash(r, 0.25, 0.6 * ctx["wet"])
            k = n_of(tt)
            y[k:k + len(sp)] += sp[: n - k]
    return Clip(_norm(y, 0.42), 0, send=0.08, name="roll")


def sfx_skid(e, r, ctx):
    D = float(np.clip(e["duration_s"] or 0.5, 0.15, 3.0))
    n = n_of(D + 0.25)
    t = t_axis(n)
    env = np.clip(t / 0.02, 0, 1) * np.clip(1.0 - t / (D + 0.2), 0, 1) ** 1.3
    sc = dsp.bandpass(dsp.pink(n, r), 250, 2800, 2) * (1 + 0.5 * dsp.lp_noise(n, r, 30))
    gr = _crackle(r, n, 500 * env + 20, hp=900)
    y = sc / (dsp.peak(sc) + 1e-9) + 0.6 * gr / (dsp.peak(gr) + 1e-9)
    if "blade" in e["tags"]:
        exc = dsp.bandpass(_nz(r, n), 1500, 7000, 2) + 0.5 * (r.random(n) < 40 / SR)
        fr = np.sort(np.exp(r.uniform(np.log(1600), np.log(6500), 10)))
        bl = dsp.resonator_bank(exc, fr, r.uniform(0.05, 0.15, 10), r.uniform(0.4, 1.0, 10))
        y += 0.7 * bl / (dsp.peak(bl) + 1e-9)
    if ctx["wet"] > 0:
        spr = dsp.highpass(_nz(r, n), 2000, 2)
        y += 0.5 * ctx["wet"] * spr / (dsp.peak(spr) + 1e-9)
    y *= env
    return Clip(_norm(y, 0.34), 0, send=0.08, name="skid")


def sfx_kneel(e, r, ctx):
    th = _thump(r, 95.0, 0.3, 0.4, 0.04, noise=0.8)
    cl = _cloth(r, 0.4, 700, 18.0)
    n = n_of(0.5)
    y = np.zeros(n)
    y[: len(th)] += th / (dsp.peak(th) + 1e-9)
    y[: len(cl)] += 0.45 * cl
    if ctx["wet"] > 0:
        sp = _splash(r, 0.3, 0.8 * ctx["wet"])
        y[: len(sp)] += sp
    return Clip(_norm(y, 0.35), 0, send=0.08, name="kneel")


def sfx_body_fall(e, r, ctx):
    n = n_of(0.9)
    y = np.zeros(n)
    for tt, a in ((0.0, 1.0), (0.14, 0.45)):
        th = _thump(r, 62.0, 0.4, 0.8, 0.09)
        k = n_of(tt)
        y[k:k + len(th)] += a * th[: n - k] / (dsp.peak(th) + 1e-9)
    y[: n_of(0.35)] += 0.4 * _grass_crunch(r, 0.35, 2000, 1200)[: n_of(0.35)]
    cl = _cloth(r, 0.5, 700, 20.0)
    y[n_of(0.05): n_of(0.05) + len(cl)] += 0.4 * cl
    if ctx["wet"] > 0:
        sp = _splash(r, 0.45, 1.2 * ctx["wet"])
        y[: len(sp)] += sp
    return Clip(_norm(y, 0.5), 0, send=0.1, name="body_fall", duck=(2.0, 0.05, 0.3))


# =====================================================================================  blades & props
def _koiguchi_click(r, level=1.0):
    """the film's 'click' motif (S06 566 / S24b 3150 / S26 3412): one fixed metal + horn/wood modal signature
    (seeded once) so the three clicks are recognisably the same sound; only micro variation per event.
    Contact = a 1-2 ms band-limited burst (no digital spike), then the habaki / tsuba ring briefly."""
    n = n_of(0.14)
    t = t_axis(n)
    sig = np.random.default_rng(1566)
    mf = np.array([3310, 4720, 6080, 7930]) * sig.uniform(0.99, 1.01, 4)
    wf = np.array([1260, 1910]) * sig.uniform(0.99, 1.01, 2)
    v = r.uniform(0.985, 1.015)
    m = dsp.modal(mf * v, [1.0, 0.72, 0.5, 0.3], [0.11, 0.085, 0.06, 0.045], n, phases=[0.0, 0.25, 0.5, 0.1], attack=0.0004)
    w = dsp.modal(wf * v, [0.8, 0.5], [0.04, 0.03], n, phases=[0.0, 0.3], attack=0.0004)
    k = n_of(0.006)
    b = dsp.bandpass(_nz(np.random.default_rng(1567), k), 1500, 9000, 2) * np.exp(-t[:k] / 0.0011)
    y = m / (dsp.peak(m) + 1e-9) + 0.75 * w / (dsp.peak(w) + 1e-9)
    y[:k] += 0.55 * b / (dsp.peak(b) + 1e-9)
    return dsp.saturate(y / (dsp.peak(y) + 1e-9), 0.2) * level


def _blade_slide(r, dur, f_from, f_to, level=1.0):
    n = n_of(dur)
    fc = np.geomspace(f_from, f_to, n)
    exc = dsp.tv_biquad(_nz(r, n), "bp", fc, 2.2)
    fr = np.sort(np.exp(r.uniform(np.log(2200), np.log(8500), 10)))
    res = dsp.resonator_bank(exc, fr, r.uniform(0.04, 0.12, 10), r.uniform(0.4, 1.0, 10))
    y = exc / (dsp.peak(exc) + 1e-9) * 0.5 + res / (dsp.peak(res) + 1e-9)
    return y * level


def sfx_draw(e, r, ctx):
    heavy = e.get("who") == "saint"
    D = 0.62 if heavy else 0.42
    n = n_of(D + 0.8)
    y = np.zeros(n)
    ck = _koiguchi_click(r, 0.7)
    y[: len(ck)] += ck
    sl = _blade_slide(r, D, 2600, 6800)
    k = n_of(0.03)
    env = dsp.env_points([(0, 0.2), (D * 0.8, 1.0), (D, 0.6)], len(sl), "cos")
    y[k:k + len(sl)] += 0.7 * sl * env
    rg = _ring(r, n_of(0.8), 2800, 9000, 10, 0.7, 0.15)
    k2 = n_of(D)
    y[k2:k2 + len(rg)] += 0.9 * rg[: n - k2] / (dsp.peak(rg) + 1e-9)
    return Clip(_norm(y, 0.5), 0, send=0.14, name="draw")


def sheathe_slide_s(e, ctx):
    """duration of the sheathe's blade slide (pre-roll before the guard seats)"""
    D = 0.55 if e.get("who") == "saint" else 0.42
    return D * 2.2 if ctx.get("in_slowmo") else D     # S26: the slow, deliberate sheathe


def sfx_sheathe(e, r, ctx):
    """event frame = the guard seating home (the click); the blade slide is pre-roll before it.
    If a tsuba_click event falls inside the slide window, the click is left to it (no double click) and the
    slide is re-timed to end on that click (render_all)."""
    D = sheathe_slide_s(e, ctx)
    n = n_of(D + 0.3)
    y = np.zeros(n)
    sl = _blade_slide(r, D, 6000, 2400)
    env = dsp.env_points([(0, 0.0), (min(0.08, D * 0.2), 0.8), (D * 0.5, 1.0), (D, 0.5)], len(sl), "cos")
    y[: len(sl)] += 0.65 * sl * env
    k = n_of(D)
    if not ctx.get("no_click"):
        ck = _koiguchi_click(r, 1.0)
        y[k:k + len(ck)] += ck[: n - k]
    return Clip(_norm(y, 0.45 if not ctx.get("no_click") else 0.3), k, send=0.12, name="sheathe")


def sfx_tsuba_click(e, r, ctx):
    pre = 0.2
    y = np.zeros(n_of(pre + 0.25))
    sl = _blade_slide(r, pre, 3000, 5200, 0.12)
    y[: len(sl)] += sl * dsp.env_points([(0, 0), (pre * 0.5, 1.0), (pre, 0.6)], len(sl), "cos")
    ck = _koiguchi_click(r, 1.0)
    k = n_of(pre)
    y[k:k + len(ck)] += ck
    # the click MOTIF (566 / 3150 / 3412) must read at one level whatever the camera: sound perspective of an
    # ECU, independent of the physical camera distance (ignore_dist)
    return Clip(_norm(y, 0.36), k, send=0.1, name="tsuba_click", ignore_dist=True)


def sfx_drip(e, r, ctx):
    """a single drop falling into a puddle (S24e): impact tick + Minnaert bubble 'plip' + ripple"""
    n = n_of(0.5)
    t = t_axis(n)
    y = np.zeros(n)
    kt = n_of(0.004)                                   # contact tick: band-limited, ~0.5 ms decay (no raw spike)
    tick = dsp.bandpass(_nz(r, kt), 1500, 9000, 2) * np.exp(-t[:kt] / 0.0005) * np.clip(t[:kt] / 0.0001, 0, 1)
    y[:kt] += 0.6 * tick / (dsp.peak(tick) + 1e-9)
    m = n_of(0.07)
    tt = t_axis(m)
    f0 = r.uniform(1100, 1500)
    bub = np.sin(TWO_PI * dsp.phase_cycles(f0 * (1 + 1.6 * tt / tt[-1]) ** 1.2, m)) * np.exp(-tt / 0.018)
    k = n_of(0.004)
    y[k:k + m] += bub
    rip = dsp.bandpass(_nz(r, n), 600, 3000, 2) * np.exp(-t / 0.08) * 0.08
    y += rip
    y2 = np.zeros(n)
    k2 = n_of(r.uniform(0.09, 0.14))
    m2 = n_of(0.04)
    y2[k2:k2 + m2] = 0.25 * np.sin(TWO_PI * dsp.phase_cycles(r.uniform(1800, 2400) * (1 + t_axis(m2) * 20), m2)) * np.exp(-t_axis(m2) / 0.01)
    y += y2
    return Clip(_norm(y, 0.42), 0, send=0.22, reverb="hall", name="drip", ignore_dist=True)


def blade_ring(r, level=0.35):
    """'a thin blade ring' (S25 3277, after the white silence): sparse high partials, soft bloom, ~1.6 s"""
    n = n_of(2.2)
    t = t_axis(n)
    fr = np.array([2349.3 * 2, 3140.0, 4410.0, 5950.0, 7320.0]) * r.uniform(0.995, 1.005, 5)
    am = np.array([0.5, 1.0, 0.6, 0.35, 0.2])
    out = np.zeros((2, n))
    for ch in range(2):
        y = dsp.modal(fr * (1 + 0.0015 * ch), am, [1.6, 1.4, 1.0, 0.7, 0.5], n, r=r)
        y *= np.clip(t / 0.012, 0, 1)
        out[ch] = y
    out += 0.05 * np.vstack([dsp.highpass(_nz(r, n), 6000, 2), dsp.highpass(_nz(r, n), 6000, 2)]) * np.exp(-t / 0.05)
    return dsp.normalize(out, level)


def sfx_spear_pull(e, r, ctx):
    n = n_of(0.9)
    t = t_axis(n)
    y = np.zeros(n)
    dirt = _crackle(r, n_of(0.4), 1500 * np.exp(-t[:n_of(0.4)] / 0.12), hp=250, sigma=1.0)
    y[: len(dirt)] += dirt / (dsp.peak(dirt) + 1e-9)
    creak_n = n_of(0.3)
    cr = dsp.resonator_bank((r.random(creak_n) < 60 / SR).astype(float), [340, 520, 810], [0.05, 0.04, 0.03], [1, 0.6, 0.4])
    y[: creak_n] += 0.6 * cr / (dsp.peak(cr) + 1e-9)
    rg = _ring(r, n_of(0.5), 3000, 8000, 8, 0.4, 0.1)
    k = n_of(0.28)
    y[k:k + len(rg)] += 0.6 * rg[: n - k] / (dsp.peak(rg) + 1e-9)
    return Clip(_norm(y, 0.5), 0, send=0.1, name="spear_pull")


def sfx_spear_spin(e, r, ctx):
    D = float(np.clip(e["duration_s"] or 1.0, 0.25, 4.0))
    n = n_of(D + 0.25)
    rot = r.uniform(4.2, 5.6) * (1 + 0.08 * dsp.lp_noise(n, r, 1.0))
    ph = dsp.phase_cycles(2 * rot, n)
    am = np.abs(np.sin(np.pi * ph)) ** 3
    fc = 500 + 700 * am
    y = dsp.tv_biquad(_nz(r, n), "bp", fc, 1.2, block=64) * am
    body = dsp.lowpass(_nz(r, n), 350, 2) * am
    y = y / (dsp.peak(y) + 1e-9) + 0.5 * body / (dsp.peak(body) + 1e-9)
    y *= dsp.env_points([(0, 0), (0.08, 1.0), (D, 1.0), (D + 0.25, 0.0)], n, "cos")
    return Clip(_norm(y, 0.45), 0, send=0.1, name="spear_spin")


def sfx_kunai_throw(e, r, ctx):
    n = n_of(0.35)
    t = t_axis(n)
    fl = _decay_burst(r, n_of(0.04), 700, 3500, 0.008)
    wh = dsp.tv_biquad(_nz(r, n), "bp", np.geomspace(4800, 2600, n), 12.0) * np.exp(-t / 0.1) * np.clip(t / 0.01, 0, 1)
    y = 0.8 * wh / (dsp.peak(wh) + 1e-9)
    y[: len(fl)] += 0.6 * fl / (dsp.peak(fl) + 1e-9)
    return Clip(_norm(y, 0.26), 0, send=0.08, name="kunai_throw")


def sfx_kunai_deflect(e, r, ctx):
    """a thrown kunai batted away by the spinning spear: small-steel 'tink' + the knock of the lacquered shaft /
    spear head + the kunai tumbling off: a whirr of band-passed air noise chopped at its spin rate, its band falling
    with the Doppler shift (no pure-tone ricochet whine)"""
    n = n_of(0.7)
    t = t_axis(n)
    tink = _ring(r, n, 2900, 8500, 8, 0.35, 0.07)
    y = tink / (dsp.peak(tink) + 1e-9)
    k = n_of(0.008)
    y[:k] += 0.6 * dsp.bandpass(_nz(r, k), 1200, 9000, 2) * np.exp(-t[:k] / 0.0015) / 0.5
    knock = dsp.modal(np.array([r.uniform(620, 760), r.uniform(1150, 1400), r.uniform(1900, 2300)]),
                      [1.0, 0.6, 0.35], [0.06, 0.045, 0.03], n_of(0.2), r=r, attack=0.0005)
    y[: len(knock)] += 0.45 * knock / (dsp.peak(knock) + 1e-9)
    fc = np.geomspace(r.uniform(3400, 4300), r.uniform(1200, 1700), n)
    spin = r.uniform(26.0, 38.0) * np.geomspace(1.0, 0.8, n)
    chop = (0.5 + 0.5 * np.cos(TWO_PI * dsp.phase_cycles(spin, n))) ** 3
    whirr = dsp.tv_biquad(_nz(r, n), "bp", fc, 5.0, block=64) * chop
    whirr *= np.exp(-t / 0.2) * np.clip((t - 0.012) / 0.03, 0, 1)
    y += 0.3 * whirr / (dsp.peak(whirr) + 1e-9)
    y = dsp.saturate(y / (dsp.peak(y) + 1e-9), 0.25)
    st = dsp.pan_mono(dsp.fade(y, 0.0, 0.1), r.choice([-1, 1]) * np.linspace(0, 0.5, n))
    s_ = float(np.clip(e["strength"], 0.2, 1.2))
    return Clip(_norm(st, 0.62 * s_ ** 0.4), 0, send=0.14, spatial=True, width=1.0, name="kunai_deflect")


def sfx_hat_cut(e, r, ctx):
    """the rising cut slices the straw hat in two: a close blade 'shff', the lacquered bamboo rim cracking,
    straw fibres tearing (0.25 s), then both halves spinning away (flutter + small whooshes L / R)"""
    pre = 0.03
    n = n_of(1.2)
    out = np.zeros((2, n))
    wh = _whoosh_core(r, 0.22, 0.0, pre + 0.02, 1500, 4800, 2000, q=2.0, whistle=0.25)
    out[:, : len(wh)] += 0.45 * wh / (dsp.peak(wh) + 1e-9)
    k = n_of(pre)
    m = n_of(0.26)
    tt = t_axis(m)
    straw = _crackle(r, m, 6000 * np.exp(-tt / 0.06), hp=1200, sigma=1.0)
    crunch = _crackle(r, m, 1800 * np.exp(-tt / 0.07), hp=None, sigma=0.8, dmax=0.004)
    crunch = dsp.bandpass(crunch, 350, 2600, 2)
    rim = dsp.modal(np.array([r.uniform(820, 980), r.uniform(1500, 1800), r.uniform(2500, 2900)]),
                    [1.0, 0.7, 0.4], [0.07, 0.05, 0.035], m, r=r, attack=0.0005)
    snap = dsp.bandpass(_nz(r, m), 600, 6000, 2) * np.exp(-tt / 0.004)
    sc = 0.9 * straw / (dsp.peak(straw) + 1e-9) + 0.8 * crunch / (dsp.peak(crunch) + 1e-9) \
        + 0.55 * rim / (dsp.peak(rim) + 1e-9) + 0.6 * snap / (dsp.peak(snap) + 1e-9)
    sc = dsp.fade(sc, 0.0, 0.08)
    out[0, k:k + m] += sc
    out[1, k:k + m] += np.roll(sc, 17)
    for ch in range(2):
        fl = _cloth(r, 0.85, 520, r.uniform(7.0, 11.0))
        s0 = n_of(0.12)
        out[ch, s0:s0 + len(fl)] += 0.5 * fl[: n - s0]
        w2 = _whoosh_core(r, 0.45, 0.0, 0.2, 300, 1100, 400, q=0.9, whistle=0.0, body=0.3)
        s1 = n_of(0.16 + 0.05 * ch)
        out[ch, s1:s1 + len(w2)] += 0.3 * w2[: n - s1] / (dsp.peak(w2) + 1e-9)
    out = dsp.saturate(out / (dsp.peak(out) + 1e-9), 0.3)
    return Clip(_norm(out, 0.72), k, send=0.14, spatial=True, width=0.8, name="hat_cut", duck=(3.0, 0.1, 0.4))


def sfx_sword_break(e, r, ctx):
    """the elder's blade snaps: a hard steel crack with body (bandpassed, 6 ms, driven), the broken edge's
    high inharmonic ping, the blade's low bending modes released, a small thud, and the tip whistling away"""
    n = n_of(1.5)
    t = t_axis(n)
    y = np.zeros(n)
    k = n_of(0.03)
    snap = dsp.bandpass(_nz(r, k), 600, 9000, 2) * np.exp(-t[:k] / 0.006) * np.clip(t[:k] / 0.0004, 0, 1)
    y[:k] += 1.0 * np.tanh(2.5 * snap / (dsp.peak(snap) + 1e-9)) / np.tanh(2.5)
    ping = _ring(r, n, 2600, 9500, 12, 0.7, 0.12, tilt=0.4)
    y += 0.8 * ping / (dsp.peak(ping) + 1e-9)
    bend = dsp.modal(np.array([r.uniform(420, 560), r.uniform(900, 1150), r.uniform(1500, 1800)]),
                     [1.0, 0.65, 0.4], [0.3, 0.2, 0.14], n_of(0.7), r=r, attack=0.001)
    y[: len(bend)] += 0.4 * bend / (dsp.peak(bend) + 1e-9)
    th = _thump(r, 85.0, 0.25, 0.4, 0.04)
    y[: len(th)] += 0.35 * th / (dsp.peak(th) + 1e-9)
    # tip spinning away: whistle AM at ~13 Hz
    m = n_of(0.9)
    tt = t_axis(m)
    spin = dsp.tv_biquad(_nz(r, m), "bp", 2600 + 900 * np.sin(TWO_PI * 13 * tt), 9.0) * \
        np.abs(np.sin(TWO_PI * 6.5 * tt)) * np.exp(-tt / 0.35)
    s0 = n_of(0.05)
    y[s0:s0 + m] += 0.35 * dsp.fade(spin, 0.0, 0.2)[: n - s0] / (dsp.peak(spin) + 1e-9)
    y = dsp.saturate(y / (dsp.peak(y) + 1e-9), 0.3)
    st = dsp.pan_mono(y, np.linspace(0, r.choice([-0.4, 0.4]), n))
    return Clip(_norm(st, 0.9), 0, send=0.25, reverb="hall", spatial=True, width=1.0, name="sword_break",
                duck=(5.0, 0.12, 0.6))


def sfx_cord_cut(e, r, ctx):
    """the vermilion beard cord severed (slow motion): a tight double 'snip' of fibres, a tiny twang of the
    released tension and the cord fluttering off"""
    n = n_of(0.7)
    t = t_axis(n)
    y = np.zeros(n)
    for j, d in enumerate((0.0, r.uniform(0.006, 0.011))):
        k = n_of(d)
        m = n_of(0.012)
        b = dsp.bandpass(_nz(r, m), 1800, 11000, 2) * np.exp(-t[:m] / 0.0018)
        b = np.tanh(2.2 * b / (dsp.peak(b) + 1e-9)) / np.tanh(2.2)          # a crisp snip, not a soft tick
        y[k:k + m] += (1.0 - 0.35 * j) * b
    fib = _crackle(r, n_of(0.05), 3000, hp=2500, sigma=0.8)
    y[: len(fib)] += 0.4 * fib / (dsp.peak(fib) + 1e-9)
    tw = dsp.modal([r.uniform(700, 900), r.uniform(1500, 1800)], [1.0, 0.4], [0.12, 0.08], n_of(0.3), r=r, attack=0.002)
    y[: len(tw)] += 0.25 * tw / (dsp.peak(tw) + 1e-9)
    fl = _cloth(r, 0.55, 1400, 16.0)
    s0 = n_of(0.02)
    y[s0:s0 + len(fl)] += 0.35 * fl[: n - s0]
    y = dsp.saturate(y / (dsp.peak(y) + 1e-9), 0.3)
    return Clip(_norm(y, 0.46), 0, send=0.2, reverb="hall", name="cord_cut")


def sfx_haori_shed(e, r, ctx):
    n = n_of(1.3)
    y = np.zeros(n)
    snap = _decay_burst(r, n_of(0.05), 500, 3000, 0.01)
    y[: len(snap)] += 0.7 * snap / (dsp.peak(snap) + 1e-9)
    wh = _whoosh_core(r, 0.75, 0.0, 0.2, 180, 900, 250, q=0.7, whistle=0.0, body=0.4, flutter=32.0)
    y[: len(wh)] += wh / (dsp.peak(wh) + 1e-9)
    land = _grass_crunch(r, 0.3, 500, 1500, 0.5) + 0.3 * _cloth(r, 0.3, 500, 15.0)
    k = n_of(0.9)
    y[k:k + len(land)] += 0.35 * land[: n - k] / (dsp.peak(land) + 1e-9)
    st = dsp.pan_mono(y, np.linspace(0, r.choice([-0.5, 0.5]), n))
    return Clip(_norm(st, 0.42), 0, send=0.1, spatial=True, width=1.0, name="haori_shed")


def sfx_spear_draw(e, r, ctx):
    n = n_of(1.1)
    y = np.zeros(n)
    m = n_of(0.38)
    fr = dsp.bandpass(_nz(r, m), 700, 3600, 2)
    fr = dsp.eq_chain(fr, [("peak", 1100, 6, 4.0), ("peak", 2400, 5, 4.0)]) * dsp.env_points([(0, 0.2), (0.3, 1.0), (0.38, 0.3)], m, "cos")
    y[:m] += 0.7 * fr / (dsp.peak(fr) + 1e-9)
    wh = _whoosh_core(r, 0.6, 0.0, 0.18, 260, 1100, 300, q=1.2, whistle=0.15, body=0.6)
    k = n_of(0.3)
    y[k:k + len(wh)] += wh[: n - k] / (dsp.peak(wh) + 1e-9)
    rg = _ring(r, n_of(0.5), 3500, 8500, 8, 0.35, 0.08)
    k2 = n_of(0.36)
    y[k2:k2 + len(rg)] += 0.5 * rg[: n - k2] / (dsp.peak(rg) + 1e-9)
    return Clip(_norm(y, 0.52), 0, send=0.12, name="spear_draw")


def sfx_sheath_drop(e, r, ctx):
    n = n_of(1.0)
    y = np.zeros(n)
    m = n_of(0.62)
    tt = t_axis(m)
    am = np.abs(np.sin(TWO_PI * 3.5 * tt)) ** 2
    wh = dsp.bandpass(_nz(r, m), 400, 1800, 2) * am * np.exp(-tt / 0.35)
    y[:m] += wh / (dsp.peak(wh) + 1e-9)
    thud = dsp.modal(np.array([520, 880, 1420]) * r.uniform(0.95, 1.05), [1, 0.6, 0.35], [0.05, 0.04, 0.03], n_of(0.2), r=r)
    thud += 0.6 * _grass_crunch(r, 0.2, 900, 1500)[: n_of(0.2)]
    k = n_of(0.66)
    y[k:k + len(thud)] += 0.7 * thud[: n - k] / (dsp.peak(thud) + 1e-9)
    st = dsp.pan_mono(y, np.linspace(0, r.choice([-0.6, 0.6]), n))
    return Clip(_norm(st, 0.34), 0, send=0.1, spatial=True, width=1.0, name="sheath_drop")


# =====================================================================================  elemental
def sfx_grass_shear(e, r, ctx):
    D = 1.1
    n = n_of(D)
    t = t_axis(n)
    out = np.zeros((2, n))
    cut = _whoosh_core(r, 0.26, 0.0, 0.05, 1200, 5200, 1500, q=2.2, whistle=0.45, body=0.2)
    out[:, : len(cut)] += 0.7 * cut / (dsp.peak(cut) + 1e-9)
    rate = 7000 * np.clip(t / 0.04, 0, 1) * np.exp(-np.maximum(t - 0.04, 0) / 0.28)
    for ch in range(2):
        c = _crackle(r, n, rate, hp=1400, sigma=0.9)
        c = dsp.lp_sweep(c, np.geomspace(14000, 3500, n))
        out[ch] += 0.8 * c / (dsp.peak(c) + 1e-9)
    width = np.clip(t / 0.5, 0, 1)
    m = 0.5 * (out[0] + out[1])
    sdf = 0.5 * (out[0] - out[1]) * (0.3 + 0.7 * width)
    out = np.vstack([m + sdf, m - sdf])
    for _ in range(int(r.integers(5, 9))):
        s0 = n_of(r.uniform(0.08, 0.75))
        mm = n_of(r.uniform(0.08, 0.22))
        if s0 + mm >= n:
            continue
        tt = t_axis(mm)
        pf = dsp.bandpass(_nz(r, mm), 500, 2600, 2) * np.clip(tt / 0.025, 0, 1) * np.exp(-tt / (mm / SR / 3))
        gl, gr = dsp.pan_gains(r.uniform(-0.9, 0.9))
        a = r.uniform(0.2, 0.45) / (dsp.peak(pf) + 1e-9)
        out[0, s0:s0 + mm] += a * gl * pf
        out[1, s0:s0 + mm] += a * gr * pf
    air = _decay_burst(r, n_of(0.4), None, 160, 0.09, attack=0.01)
    out[:, : len(air)] += 0.5 * air / (dsp.peak(air) + 1e-9)
    return Clip(_norm(out, 0.8), 0, send=0.14, spatial=True, width=1.0, name="grass_shear", duck=(3.0, 0.1, 0.5))


def sfx_fire_ignite(e, r, ctx):
    D = 3.0
    n = n_of(D)
    t = t_axis(n)
    out = np.zeros((2, n))
    for ch in range(2):
        wh = dsp.tv_biquad(_nz(r, n), "lp", np.clip(150 + 1100 * (t / 0.25) ** 0.7, 150, 1250) * np.exp(-np.maximum(t - 0.25, 0) / 1.5) + 120, 0.9, block=128)
        wh *= np.clip(t / 0.015, 0, 1) * np.exp(-t / 0.7)
        roar = dsp.bandpass(_nz(r, n), 250, 2800, 2) * np.clip((t - 0.1) / 0.4, 0, 1) * np.exp(-t / 1.4)
        roar *= 1 + 0.4 * dsp.lp_noise(n, r, 9.0)
        cr = _crackle(r, n, 60 * np.clip(t / 0.3, 0, 1), hp=1500, sigma=1.2)
        out[ch] = wh / (dsp.peak(wh) + 1e-9) + 0.5 * roar / (dsp.peak(roar) + 1e-9) + 0.35 * cr / (dsp.peak(cr) + 1e-9)
    th = _thump(r, 55.0, 0.5, 0.5, 0.12)
    out[:, : len(th)] += 0.7 * th / (dsp.peak(th) + 1e-9)
    return Clip(_norm(out, 0.9), 0, send=0.12, spatial=True, width=1.0, name="fire_ignite", duck=(3.0, 0.2, 0.8), ignore_dist=True)


def sfx_fire_burst(e, r, ctx):
    s = float(np.clip(e["strength"], 0.2, 1.3))
    D = 1.3
    n = n_of(D)
    t = t_axis(n)
    out = np.zeros((2, n))
    for ch in range(2):
        wh = dsp.tv_biquad(_nz(r, n), "lp", 200 + 2200 * np.exp(-t / 0.18), 0.8, block=128) * np.clip(t / 0.008, 0, 1) * np.exp(-t / 0.35)
        cr = _crackle(r, n, 120 * np.exp(-t / 0.4), hp=1200, sigma=1.2)
        out[ch] = wh / (dsp.peak(wh) + 1e-9) + 0.35 * cr / (dsp.peak(cr) + 1e-9)
    th = _thump(r, 62.0, 0.4, 0.5, 0.08)
    out[:, : len(th)] += 0.6 * s * th / (dsp.peak(th) + 1e-9)
    return Clip(_norm(out, 0.72 * s ** 0.6), 0, send=0.12, spatial=True, width=0.8, name="fire_burst",
                duck=(2.5, 0.1, 0.4) if s > 0.8 else None)


def _thunder(r, kind, final=False):
    """kind: far (long roll) | mid (soft crack + roll) | near (whip crack, rip, boom, receding roll).
    final=True (the S25 pass): the thunder IS the unified hit -- crack, rip and boom, then only a short roll so
    the long tail belongs to the reverb, not to a sustained rumble"""
    if kind == "far":
        D = r.uniform(6.0, 8.0)
        L = np.vstack([_rumble(r, D, 220, 6, (0.3, 0.9), (1.0, 2.4), 0.0) for _ in range(2)])
        return _norm(L, 0.45), D
    if kind == "mid":
        D = 6.5
        n = n_of(D)
        out = np.vstack([_rumble(r, D, 480, 6, (0.05, 0.4), (0.8, 2.0), 0.0) for _ in range(2)])
        out = out / (dsp.peak(out) + 1e-9)
        cr = _crack(r, 0.25, 400, 1.5, 0.06)
        cr = dsp.lowpass(cr, 3000, 2)
        out[:, : len(cr)] += 0.6 * cr / (dsp.peak(cr) + 1e-9)
        return _norm(out, 0.65), D
    D = 6.5
    n = n_of(D)
    if final:
        out = np.vstack([_rumble(r, D, 380, 3, (0.02, 0.1), (0.5, 1.2), 0.05, spread=0.15, recede=0.6) for _ in range(2)])
        out = out / (dsp.peak(out) + 1e-9) * 0.6
    else:
        out = np.vstack([_rumble(r, D, 380, 5, (0.02, 0.2), (0.8, 2.2), 0.08, spread=0.4, recede=1.6) for _ in range(2)])
        out = out / (dsp.peak(out) + 1e-9) * 0.75
    for ch in range(2):                      # whip crack, then the rip of the channel (decorrelated L/R)
        cr = _crack(r, 0.08, 900, 3.0, 0.01)
        out[ch, : len(cr)] += (0.28 if final else 0.5) * cr
        tr = _tear(r, r.uniform(0.65, 0.8) if final else r.uniform(0.38, 0.5))
        s0 = n_of(r.uniform(0.003, 0.012))
        out[ch, s0:s0 + len(tr)] += (0.9 if final else 0.8) * tr
    boom = _thump(r, 48.0, 1.2, 0.6, 0.35, noise=0.5)
    b0 = n_of(0.025)                         # the pressure wave lands a hair after the crack
    out[:, b0:b0 + len(boom)] += 0.6 * boom[: n - b0] / (dsp.peak(boom) + 1e-9)
    out = dsp.saturate(_norm(out, 1.0), 0.22)          # overload: denser, not peakier
    return _norm(out, 0.72), D


def sfx_thunder(e, r, ctx):
    kind = e.get("distance", "far")
    final = bool(ctx.get("final_pass")) and kind != "far"
    y, D = _thunder(r, kind, final=final)
    return Clip(y, 0, send=0.22 if final else (0.16 if kind != "far" else 0.25), reverb="huge" if kind != "far" else "hall",
                spatial=True, width=1.0,
                name=f"thunder_{kind}" + ("_final" if final else ""), ignore_dist=True,
                duck=(4.0, 0.3, 1.2) if kind == "near" else None)


def sfx_lightning_strike(e, r, ctx):
    """environmental strike (S22 flashes): a whip crack and a short rip, then a MID-distance roll -- deliberately a
    size below the Raikiri, which owns the only full near-thunder body in Act III"""
    y, D = _thunder(r, "mid")
    k = n_of(0.5)
    sz = np.vstack([_sizzle(r, 0.5), _sizzle(r, 0.5)])
    y[:, :k] += 0.3 * sz[:, :k] / (dsp.peak(sz) + 1e-9)
    cr = _crack(r, 0.12, 1500, 4.0, 0.012)
    y[:, : len(cr)] += 0.45 * cr
    for ch in range(2):
        tr = _tear(r, r.uniform(0.2, 0.3), lo=300.0)
        s0 = n_of(r.uniform(0.002, 0.008))
        y[ch, s0:s0 + len(tr)] += 0.35 * tr
    d = float(e.get("dist", 6.0))
    if d > 25.0:                                    # far strikes: darker and a little softer, never tiny
        y = dsp.lowpass(y, float(np.clip(20000.0 * (25.0 / d) ** 0.8, 2500.0, 20000.0)), 2) * dsp.db2lin(-2.5 * min(1.0, (d - 25.0) / 50.0))
    return Clip(dsp.soft_limit(y, 0.98, 0.75), 0, send=0.14, reverb="huge", spatial=True, width=1.0,
                name="lightning_strike", duck=(5.0, 0.2, 1.2), ignore_dist=True)


def _raikiri_inhale(r, dur=0.46):
    """the storm breathes in before the cut: a reversed, rising air swell that ENDS on the cut (stereo)"""
    n = n_of(dur)
    t = t_axis(n)
    out = np.zeros((2, n))
    for ch in range(2):
        x = _nz(r, n)
        fc = np.geomspace(500.0, 6500.0, n)
        y = dsp.tv_biquad(x, "bp", fc, 1.4, block=64)
        y += 0.5 * dsp.tv_biquad(_nz(r, n), "lp", np.geomspace(180.0, 900.0, n), 0.8, block=64)
        env = (t / dur) ** 2.6
        out[ch] = y / (dsp.peak(y) + 1e-9) * env
    return dsp.fade(out, 0.03, 0.004)


def sfx_raikiri(e, r, ctx):
    """Raikiri (the lightning cut) -- the one sound of its kind in the film: the storm's reversed inhale INTO the cut (pre-roll), a crack, a
    blade 'shing' pitched to D/A (short clustered doublets -- not a pure ting), the near-thunder rip + boom, and the
    split: two branches tearing apart, the stronger one sweeping towards the pine (the tree_split event's pan)."""
    pre = 0.46
    k0 = n_of(pre)
    y0, D = _thunder(r, "near")
    n = k0 + y0.shape[-1]
    y = np.zeros((2, n))
    y[:, k0:] += 0.85 * y0
    y[:, :k0] += 0.55 * _raikiri_inhale(r, pre)
    # the blade meets the bolt: a D/A steel 'shing' (clustered doublets, T60 <= 0.9 s) + a hard crack
    fr = np.array([1174.7, 1760.0, 2349.3, 3520.0, 4698.6])
    fr = np.concatenate([fr, fr * 1.0035, fr * 0.9972]) * r.uniform(0.998, 1.002)
    am = np.tile([0.55, 1.0, 0.8, 0.5, 0.3], 3) * np.repeat([1.0, 0.7, 0.6], 5)
    t60 = np.tile([0.9, 0.8, 0.65, 0.5, 0.4], 3)
    shing = np.vstack([dsp.modal(fr, am, t60, n_of(1.2), r=r, attack=0.0015) for _ in range(2)])
    shing = shing / (dsp.peak(shing) + 1e-9)
    y[:, k0:k0 + shing.shape[1]] += 0.32 * shing
    crk = _crack(r, 0.1, 2000, 5.0, 0.01)
    y[:, k0:k0 + len(crk)] += 0.55 * crk
    # the split: two tearing branches; the stronger falls away towards the pine
    doc = ctx.get("doc")
    pine = None
    if doc is not None:
        ts = [x for x in doc.events if x["type"] == "tree_split" and 0.0 <= x["t"] - e["t"] < 3.0]
        if ts:
            pine = ts[0]["pan"]
    side_main = float(np.clip(pine if pine is not None else 0.8, -1.0, 1.0))
    if abs(side_main) < 0.25:
        side_main = 0.25 if side_main >= 0 else -0.25
    for side, amp in ((side_main, 0.5), (-np.sign(side_main) * 0.7, 0.3)):
        m = n_of(0.9)
        tt = t_axis(m)
        br = dsp.tv_biquad(_nz(r, m), "bp", np.geomspace(7000, 600, m), 4.0) * np.exp(-tt / 0.3)
        br = dsp.fade(br / (dsp.peak(br) + 1e-9), 0.0, 0.25) + 0.5 * _sizzle(r, 0.9)[:m]
        s0 = k0 + n_of(0.012)
        gl, gr = dsp.pan_gains(np.linspace(0.0, side, m))
        y[0, s0:s0 + m] += amp * br * gl
        y[1, s0:s0 + m] += amp * br * gr
    return Clip(dsp.soft_limit(y, 0.98, 0.7), k0, send=0.18, reverb="huge", spatial=True, width=1.0, name="raikiri",
                duck=(8.0, 0.3, 1.6), ignore_dist=True, breath_exempt=True)


def sfx_tree_split(e, r, ctx):
    n = n_of(3.0)
    t = t_axis(n)
    y = np.zeros(n)
    k = n_of(0.05)
    crack = dsp.lowpass(_nz(r, k), 5000, 2) * np.exp(-t[:k] / 0.006)
    y[:k] += 1.2 * np.tanh(2 * crack / (dsp.peak(crack) + 1e-9))
    m = n_of(0.7)
    tt = t_axis(m)
    fib = _crackle(r, m, 2600 * np.exp(-tt / 0.2), hp=None, sigma=1.0, dmax=0.006)
    fib = dsp.bandpass(fib, 280, 3200, 2)
    y[:m] += 0.8 * fib / (dsp.peak(fib) + 1e-9)
    gm = n_of(1.2)
    groan = dsp.resonator_bank((r.random(gm) < 35 / SR).astype(float) + 0.02 * _nz(r, gm), [92, 131, 187], [0.3, 0.25, 0.2], [1, 0.7, 0.5])
    groan *= np.exp(-t_axis(gm) / 0.5)
    y[n_of(0.05): n_of(0.05) + gm] += 0.5 * groan / (dsp.peak(groan) + 1e-9)
    fw = dsp.lowpass(_nz(r, n_of(1.0)), 900, 2) * np.clip(t[:n_of(1.0)] / 0.03, 0, 1) * np.exp(-t[:n_of(1.0)] / 0.3)
    k2 = n_of(0.25)
    y[k2:k2 + len(fw)] += 0.45 * fw / (dsp.peak(fw) + 1e-9)
    return Clip(_norm(y, 0.75), 0, send=0.3, reverb="hall", name="tree_split", duck=(3.0, 0.2, 0.8))


def sfx_electric_crackle(e, r, ctx):
    """environmental arcing after a strike (grass / wet ground): a steady HF sizzle, dense crackle, a steam-like
    band of hiss and a few louder snaps -- no tonal buzz (that reads as sci-fi electricity)"""
    D = float(np.clip(e["duration_s"] or 0.8, 0.15, 6.0))
    n = n_of(D + 0.15)
    t = t_axis(n)
    y = _sizzle(r, D + 0.15)
    dense = _crackle(r, n, 1400, hp=1800, sigma=0.8, dmin=0.0002, dmax=0.0015)
    y = y / (np.std(y) + 1e-9) * 0.5 + 0.5 * dense / (np.std(dense) + 1e-9)
    hiss = dsp.bandpass(_nz(r, n), 1800, 7000, 2)
    y += 0.25 * hiss / (np.std(hiss) + 1e-9) * (0.5 + 0.5 * np.abs(dsp.lp_noise(n, r, 12.0)))
    for _ in range(int(r.integers(2, 5))):
        k = n_of(r.uniform(0.0, D))
        m = n_of(0.02)
        if k + m < n:
            y[k:k + m] += 2.5 * dsp.bandpass(_nz(r, m), 1500, 9000, 2) * np.exp(-t[:m] / 0.004)
    y *= dsp.env_points([(0, 0), (0.02, 1.0), (D, 0.8), (D + 0.15, 0)], n, "cos")
    y = dsp.saturate(y / (dsp.peak(y) + 1e-9), 0.3)
    return Clip(_norm(y, 0.45), 0, send=0.15, name="electric_crackle")


def sfx_rain_split(e, r, ctx):
    D = 1.4
    n = n_of(D)
    t = t_axis(n)
    out = np.zeros((2, n))
    air = _whoosh_core(r, 0.6, 0.0, 0.14, 180, 900, 220, q=0.8, whistle=0.0, body=0.8)
    out[:, : len(air)] += air / (dsp.peak(air) + 1e-9)
    for ch in range(2):
        rain = dsp.bandpass(_nz(r, n), 900, 9000, 2) + 0.7 * _crackle(r, n, 2500, hp=2500) / 3.0
        notch_f = np.geomspace(8000, 900, n)
        rain = dsp.tv_biquad(rain, "notch", notch_f, 0.7, block=128)
        dip = 1.0 - 0.8 * np.exp(-((t - 0.2) / 0.12) ** 2)
        rain *= np.clip(t / 0.05, 0, 1) * np.exp(-t / 0.6) * dip
        out[ch] += 0.7 * rain / (dsp.peak(rain) + 1e-9)
    sp_n = n_of(1.0)
    spray = np.vstack([dsp.highpass(_nz(r, sp_n), 2000, 2), dsp.highpass(_nz(r, sp_n), 2000, 2)]) * np.exp(-t[:sp_n] / 0.3)
    k = n_of(0.25)
    out[:, k:k + sp_n] += 0.4 * spray[:, : n - k] / (dsp.peak(spray) + 1e-9)
    w = np.clip(t / 0.4, 0, 1)
    m = 0.5 * (out[0] + out[1])
    sd = 0.5 * (out[0] - out[1]) * (0.4 + 0.6 * w)
    out = np.vstack([m + sd, m - sd])
    return Clip(_norm(out, 0.72), 0, send=0.14, spatial=True, width=1.0, name="rain_split", duck=(3.0, 0.1, 0.5))


def sfx_steam_hiss(e, r, ctx):
    s = float(np.clip(e["strength"], 0.2, 1.3))
    D = 2.6
    n = n_of(D)
    t = t_axis(n)
    env = np.clip(t / 0.05, 0, 1) * np.exp(-t / 0.9)
    out = np.zeros((2, n))
    for ch in range(2):
        h = dsp.bandpass(_nz(r, n), 2500, 11000, 2)
        body = dsp.bandpass(_nz(r, n), 500, 2000, 2)
        sz = _crackle(r, n, 300 * env + 10, hp=3000)
        out[ch] = (h / (dsp.peak(h) + 1e-9) + 0.3 * body / (dsp.peak(body) + 1e-9) + 0.4 * sz / (dsp.peak(sz) + 1e-9)) * env
    return Clip(_norm(out, 0.42 * s ** 0.7), 0, send=0.1, spatial=True, width=0.9, name="steam_hiss")


def sfx_shockwave(e, r, ctx):
    s = float(np.clip(e["strength"], 0.3, 1.3))
    n = n_of(2.2)
    t = t_axis(n)
    out = np.zeros((2, n))
    boom = _thump(r, 40.0, 1.4, 0.8, 0.35, noise=0.6)
    out[:, : len(boom)] += boom / (dsp.peak(boom) + 1e-9)
    air = _whoosh_core(r, 0.55, 0.0, 0.05, 250, 3200, 350, q=0.7, whistle=0.0, body=0.4)
    out[0, : len(air)] += 0.6 * air / (dsp.peak(air) + 1e-9)
    air2 = _whoosh_core(r, 0.55, 0.0, 0.06, 250, 3000, 350, q=0.7, whistle=0.0, body=0.4)
    out[1, : len(air2)] += 0.6 * air2 / (dsp.peak(air2) + 1e-9)
    deb = np.vstack([_crackle(r, n_of(0.9), 800 * np.exp(-t[:n_of(0.9)] / 0.3), hp=700) for _ in range(2)])
    out[:, n_of(0.05): n_of(0.05) + deb.shape[1]] += 0.25 * deb / (dsp.peak(deb) + 1e-9)
    if "water" in e["tags"] or ctx["wet"] > 0.5:
        sp = np.vstack([dsp.highpass(_nz(r, n_of(1.2)), 1500, 2) for _ in range(2)]) * np.exp(-t[:n_of(1.2)] / 0.35)
        sp *= np.clip(t[:n_of(1.2)] / 0.03, 0, 1)
        out[:, : sp.shape[1]] += 0.45 * sp / (dsp.peak(sp) + 1e-9)
        for ch in range(2):
            pat = _crackle(r, n_of(1.2), 900 * np.exp(-t[:n_of(1.2)] / 0.4), hp=1800)
            out[ch, : len(pat)] += 0.25 * pat / (dsp.peak(pat) + 1e-9)
    return Clip(_norm(out, 0.9 * s ** 0.5), 0, send=0.2, reverb="huge", spatial=True, width=1.0, name="shockwave",
                duck=(6.0, 0.15, 0.9))


def sfx_bell(e, r, ctx):
    y = inst.temple_bell(dsp.midi2hz(50), 0.8, r, dur=10.0)
    return Clip(_norm(y, 0.6), 0, send=0.3, reverb="temple", spatial=True, width=1.0, name="bell")


def sfx_heartbeat(e, r, ctx):
    bpm = float(np.clip(tl._num(e.get("bpm"), 64.0), 30, 200))
    D = float(np.clip(e["duration_s"] or 3.0, 0.5, 20.0))
    n = n_of(D + 0.8)
    y = np.zeros(n)
    tt = 0.0
    i = 0
    while tt < D:
        hb = inst.heartbeat(0.75 + 0.2 * min(1.0, tt / D), r)
        k = n_of(tt)
        m = min(len(hb), n - k)
        y[k:k + m] += hb[:m]
        tt += 60.0 / bpm * r.uniform(0.97, 1.03)
        i += 1
    y = dsp.eq_chain(y, [("peak", 140, 4.0, 1.0)])
    return Clip(_norm(y, 0.55), 0, send=0.03, name="heartbeat", ignore_dist=True)


def sfx_stinger(e, r, ctx):
    s = float(np.clip(e["strength"], 0.2, 1.3))
    pre = 0.45 if s >= 0.5 else 0.0
    n = n_of(pre + 2.5)
    out = np.zeros((2, n))
    k = n_of(pre)
    if pre > 0:
        sw, anc = inst.metal_swell(pre, 0.6, r, bright=0.7)
        out[:, :anc] += sw[:, :anc]
    sub = _thump(r, 42.0, 1.6, 0.9, 0.45, noise=0.3)
    out[:, k:k + len(sub)] += sub / (dsp.peak(sub) + 1e-9)
    cl = _modal_cloud(r, n_of(2.0), 280, 3200, 20, 1.2, 0.3, tilt=0.3)
    out[0, k:k + len(cl)] += 0.5 * cl / (dsp.peak(cl) + 1e-9)
    cl2 = _modal_cloud(r, n_of(2.0), 280, 3200, 20, 1.2, 0.3, tilt=0.3)
    out[1, k:k + len(cl2)] += 0.5 * cl2 / (dsp.peak(cl2) + 1e-9)
    bn = _decay_burst(r, n_of(0.2), 200, 6000, 0.03)
    out[:, k:k + len(bn)] += 0.6 * bn / (dsp.peak(bn) + 1e-9)
    return Clip(_norm(out, 0.8 * s ** 0.6), k, send=0.2, reverb="hall", spatial=True, width=1.0, name="stinger",
                ignore_dist=True, duck=(3.0, 0.1, 0.5))


def sfx_slowmo(e, r, ctx):
    """time dilation: a whoosh stretched down like tape slowing + a low 'bwoom' swell (falling pitch, a few
    harmonics + a filtered-noise body, gently saturated -- not a bare sine) that settles within ~2.5 s, so a
    long slow-motion window stays free for the scene's own focus sounds"""
    D = float(np.clip(e["duration_s"] or 1.5, 0.3, 6.0))
    Dd = min(D, 1.3)                  # short: the slow-motion window belongs to the scene's own focus sounds
    pre = 0.15
    n = n_of(pre + Dd + 0.45)
    t = t_axis(n)
    wh = _whoosh_core(r, 0.8, 0.0, 0.22, 600, 1600, 180, q=1.0, whistle=0.1, body=0.6)
    wh = dsp.resample_ratio(wh, 0.6)
    out = np.zeros(n)
    m = min(len(wh), n)
    out[:m] += wh[:m] / (dsp.peak(wh) + 1e-9) * np.exp(-np.maximum(t[:m] - pre - 0.3, 0) / 0.35)
    f = 73.4 * (1 - 0.25 * np.clip((t - pre) / (Dd + 0.3), 0, 1))
    ph = dsp.phase_cycles(f, n)
    tone = np.sin(TWO_PI * ph) + 0.35 * np.sin(2 * TWO_PI * ph + 0.7) + 0.15 * np.sin(3 * TWO_PI * ph + 1.9)
    body = dsp.lowpass(_nz(r, n), 200.0, 2)
    body = body / (np.std(body) + 1e-9) * (0.7 + 0.3 * dsp.lp_noise(n, r, 3.0))
    env = dsp.env_points([(0, 0), (pre + 0.15, 1.0), (pre + Dd * 0.5, 0.4), (n / SR, 0)], n, "cos")
    drone = dsp.saturate((0.7 * tone + 0.35 * body) * env / 1.6, 0.3)
    out += 0.9 * drone / (dsp.peak(drone) + 1e-9) * 0.45
    return Clip(_norm(dsp.fade(out, 0.0, 0.25), 0.45), n_of(pre), send=0.12, reverb="hall", name="slowmo", ignore_dist=True)


SFX = {
    "whoosh": sfx_whoosh, "clash": sfx_clash, "clash_heavy": sfx_clash_heavy, "perfect_deflect": sfx_perfect_deflect,
    "blade_lock": sfx_blade_lock, "hit": sfx_hit, "kick": sfx_kick, "step": sfx_step, "dash": sfx_dash,
    "jump": sfx_jump, "land": sfx_land, "roll": sfx_roll, "skid": sfx_skid, "kneel": sfx_kneel,
    "body_fall": sfx_body_fall, "draw": sfx_draw, "sheathe": sfx_sheathe, "tsuba_click": sfx_tsuba_click,
    "spear_pull": sfx_spear_pull, "spear_spin": sfx_spear_spin, "kunai_throw": sfx_kunai_throw,
    "kunai_deflect": sfx_kunai_deflect, "hat_cut": sfx_hat_cut, "sword_break": sfx_sword_break,
    "cord_cut": sfx_cord_cut, "haori_shed": sfx_haori_shed, "spear_draw": sfx_spear_draw,
    "sheath_drop": sfx_sheath_drop, "grass_shear": sfx_grass_shear, "fire_ignite": sfx_fire_ignite,
    "fire_burst": sfx_fire_burst, "thunder": sfx_thunder, "lightning_strike": sfx_lightning_strike,
    "raikiri": sfx_raikiri, "tree_split": sfx_tree_split, "electric_crackle": sfx_electric_crackle,
    "rain_split": sfx_rain_split, "steam_hiss": sfx_steam_hiss, "shockwave": sfx_shockwave, "bell": sfx_bell,
    "heartbeat": sfx_heartbeat, "stinger": sfx_stinger, "slowmo": sfx_slowmo, "drip": sfx_drip,
}
# types whose sound is an impact with a sharp onset exactly at the event time (used by the onset check)
IMPULSIVE = {"clash", "clash_heavy", "perfect_deflect", "hit", "kick", "step", "land", "tsuba_click",
             "kunai_deflect", "sword_break", "lightning_strike", "raikiri", "tree_split", "draw", "hat_cut",
             "cord_cut", "kneel", "drip"}
NO_SLOWMO = {"thunder", "lightning_strike", "raikiri", "rain_split", "steam_hiss", "slowmo", "bell", "heartbeat",
             "stinger", "fire_ignite", "electric_crackle", "tree_split", "drip", "tsuba_click", "sheathe",
             "sword_break", "cord_cut"}


# =====================================================================================  rendering
# a story hit may have one 'breath' before it: everything but the inhale is pulled down (mix.BREATH_CUES).  SFX
# clips of these types that START inside the breath window keep playing (the swing that IS the inhale).
BREATH_EXEMPT_TYPES = {"whoosh", "raikiri", "dash"}
RAIKIRI_HIERARCHY_S = 15.0          # near thunder within this time after the Raikiri is rendered one size smaller
APPARENT_DIST_REF_MM = 35.0         # sound perspective follows the shot size: apparent distance = dist * 35 / lens


def event_ctx(doc, e, slow_windows):
    """per-event context: wet ground, fire, slow-motion.
    Slow-motion pitch-down only for events strictly inside a SHORT window (<= 3 s): the contact that
    triggers a ramp (event at the window start) keeps its real pitch but blooms (more reverb); the long
    S25-S26 hold keeps every sound natural (only the ambience is muffled)."""
    t = e["t"]
    slow, in_w, bloom = 1.0, False, False
    for (a, b, _) in slow_windows:
        if a - 0.09 <= t <= b:
            in_w = True
            if e["type"] not in NO_SLOWMO and (b - a) <= 3.0:
                if t <= a + 0.09:
                    bloom = True
                else:
                    slow = SLOWMO_RATE
            break
    fp = doc.cue("final_pass")
    final = ("final_pass" in e["tags"]) or (fp is not None and abs(t - fp) <= 0.15)
    return dict(doc=doc, wet=tl.wetness_at(doc, t), fire=tl.fire_at(doc, t), slow=slow, in_slowmo=in_w, bloom=bloom,
                final_pass=final)


def render_event(e, ctx):
    fn = SFX.get(e["type"])
    if fn is None:
        return None
    r = dsp.rng("sfx", e["type"], round(e["frame"], 3), e.get("idx", 0))
    rate = ctx.get("slow", 1.0)
    if rate != 1.0 and e["type"] in tl.DURATION_TYPES and e.get("duration_s"):
        # a picture-locked duration inside a slowed window: render the clip for D*rate so that, once slowed down,
        # it covers exactly [t, t + D] (a blade_lock's release 'shing' lands on its end frame, not 40 % later)
        e = dict(e, duration_s=e["duration_s"] * rate)
    clip = fn(e, r, ctx)
    if clip is None:
        return None
    a = clip.audio
    if not np.all(np.isfinite(a)):
        raise FloatingPointError(f"non-finite audio in sfx {e['type']} @ {e['frame']}")
    trim = TRIM_DB.get(trim_key(e), 0.0) + sum(v for k, v in TAG_TRIM_DB.items() if k in e["tags"])
    a = dsp.fade(a, 0.0, 0.006) * dsp.db2lin(trim)          # no truncation clicks; hierarchy trim
    clip.audio = a
    if rate != 1.0:
        clip.audio = dsp.resample_ratio(a, rate)
        clip.anchor = int(round(clip.anchor / rate))
        clip.send = min(0.6, clip.send * 1.8)
        if clip.reverb == "field":
            clip.reverb = "hall"
    elif ctx.get("bloom"):
        clip.send = min(0.6, clip.send * 2.2)
        clip.reverb = "huge" if e["type"] == "clash_heavy" else "hall"
    return clip


def apparent_dist(e):
    """camera distance scaled by the lens: a 135 mm telephoto from 50 m is a medium shot (~13 m), an 18 mm wide
    shot pushes the same distance back.  Without a lens (draft data) the physical distance is used."""
    d = float(e["dist"])
    lens = e.get("lens")
    if lens:
        d *= float(np.clip(APPARENT_DIST_REF_MM / float(lens), 0.15, 1.6))
    return max(d, 0.2)


def spatialize(clip, e):
    """distance attenuation / air absorption / pan -> stereo, plus reverb send gain.
    Cinematic perspective: -0.5 exponent, floor -10 dB, air lowpass only beyond 10 m (>= 5 kHz); the distance is
    the APPARENT distance (shot size, see apparent_dist)."""
    a = clip.audio
    d = apparent_dist(e)
    d0 = 2.5
    g = 1.0 if clip.ignore_dist else float(max(dsp.db2lin(-10.0), min(1.0, (d0 / max(d, d0)) ** 0.5)))
    if not clip.ignore_dist and d > 10.0:
        fc = float(np.clip(20000.0 * (10.0 / d) ** 0.5, 5000.0, 20000.0))
        if fc < 18500:
            a = dsp.lowpass(a, fc, 2)
    if a.ndim == 1:
        st = dsp.pan_mono(a, e["pan"])
    else:
        st = dsp.pan_stereo(a, e["pan"] * (0.85 if clip.spatial else 1.0), clip.width)
    # farther = wetter (direct-to-reverb ratio); sounds that ignore the distance law keep their designed send
    send = clip.send * (1.0 if clip.ignore_dist else float(np.clip(1.0 + 0.4 * np.log2(max(d, 1.0) / d0), 0.6, 2.2)))
    return st * g * clip.gain, min(send, 0.8)


def _sheathe_clicks(doc, slow_w):
    """{event idx of a sheathe: t of the tsuba_click that owns its click}: a tsuba_click anywhere inside the
    sheathe's slide window (t - slide - 0.1 .. t + 0.3) takes the click; the slide is re-timed to end on it"""
    clicks = [x for x in doc.events if x["type"] == "tsuba_click"]
    out, notes = {}, []
    for e in doc.events:
        if e["type"] != "sheathe" or not clicks:
            continue
        D = sheathe_slide_s(e, event_ctx(doc, e, slow_w))
        cand = [c for c in clicks if e["t"] - D - 0.1 <= c["t"] <= e["t"] + 0.3]
        if not cand:
            continue
        c = min(cand, key=lambda c: abs(c["t"] - e["t"]))
        out[e["idx"]] = c["t"]
        off = (c["t"] - e["t"]) * doc.fps
        if abs(off) > 2.0:
            notes.append(f"sheathe at frame {e['frame']} and tsuba_click at {c['frame']} are {off:+.1f} f apart: "
                         f"the click belongs to the tsuba_click, the slide is re-timed to end on it")
    return out, notes


def render_all(doc, merged_bells=(), merged_stingers=(), breath=None, skip_heartbeats=False, verbose=False):
    """Render every event onto the timeline.
    breath: optional (t0, t1) window before the Raikiri: thunder already rolling is faded out by t0; clips of
    BREATH_EXEMPT_TYPES starting inside it (and clips flagged breath_exempt) go to the separate `exempt` buffer
    so the mix can pull everything else down.
    Returns dict(dry=(2,N), exempt=(2,N), sends={preset:(2,N)}, placed=[...], ducks=[(t, depth, hold, rel)],
    skipped=[...], notes=[...])"""
    N = doc.n_samples
    dry = np.zeros((2, N))
    exempt = np.zeros((2, N))
    sends = {}
    placed = []
    ducks = []
    skipped = []
    slow_w = tl.slowmo_windows(doc)
    click_owner, notes = _sheathe_clicks(doc, slow_w)
    hard = tl.silence_windows(doc).get("all")
    t_rk = doc.cue("raikiri")
    for e in doc.events:
        typ = e["type"]
        if typ in tl.CONTROL_TYPES:
            continue
        if hard and hard[0] - 0.02 <= e["t"] < hard[1]:
            skipped.append(dict(frame=e["frame"], type=typ, reason="starts inside the white silence (every stem at digital zero)"))
            continue
        if typ == "bell" and any(abs(e["t"] - tb) < 1.0 for tb in merged_bells):
            skipped.append(dict(frame=e["frame"], type=typ, reason="merged into the score bell"))
            continue
        if typ == "stinger" and any(abs(e["t"] - ts) < 0.3 for ts in merged_stingers):
            skipped.append(dict(frame=e["frame"], type=typ, reason="merged into the score's own stinger"))
            continue
        if typ not in SFX:
            skipped.append(dict(frame=e["frame"], type=typ, reason="no renderer"))
            continue
        ctx = event_ctx(doc, e, slow_w)
        if typ == "sheathe" and e["idx"] in click_owner:
            ctx["no_click"] = True
        ev = e
        if typ == "thunder" and e.get("distance") == "near" and t_rk is not None and not ctx["final_pass"] \
                and 0.3 < e["t"] - t_rk < RAIKIRI_HIERARCHY_S:
            ev = dict(e, distance="mid")                   # the Raikiri stays the biggest thunder of Act III
            notes.append(f"thunder near at frame {e['frame']} rendered as 'mid' (within {RAIKIRI_HIERARCHY_S:.0f} s "
                         f"after the Raikiri)")
        clip = render_event(ev, ctx)
        if clip is None:
            continue
        if typ == "sheathe" and e["idx"] in click_owner:
            clip.t_place = click_owner[e["idx"]]
        t_evt = clip.t_place if clip.t_place is not None else e["t"]
        st, send = spatialize(clip, e)
        start = int(round(t_evt * SR)) - clip.anchor
        if breath is not None and typ in ("thunder",) and start < n_of(breath[0]) < start + st.shape[-1]:
            k = n_of(breath[0]) - start                    # a roll already sounding: faded out by the breath
            f = n_of(0.35)
            st = st.copy()
            st[:, max(0, k - f):k] *= np.linspace(1.0, 0.0, min(f, k))
            st[:, k:] = 0.0
            notes.append(f"thunder at frame {e['frame']} faded out before the Raikiri breath")
        to_exempt = clip.breath_exempt or (breath is not None and typ in BREATH_EXEMPT_TYPES
                                          and breath[0] - 0.05 <= t_evt - clip.anchor / SR < breath[1])
        dsp.place(exempt if to_exempt else dry, st, start)
        if send > 0:
            if clip.reverb not in sends:
                sends[clip.reverb] = np.zeros((2, N), dtype=np.float32)
            dsp.place(sends[clip.reverb], st, start, send)
        if clip.duck:
            ducks.append((t_evt, *clip.duck))
        k0 = clip.anchor
        e_on = float(np.sum(st[:, k0:k0 + n_of(0.02)] ** 2))
        placed.append(dict(frame=e["frame"], t=t_evt, type=typ, start=start, anchor=clip.anchor,
                           len=st.shape[-1], slow=ctx["slow"], name=clip.name, e_on=e_on, exempt=bool(to_exempt)))
    return dict(dry=dry, exempt=exempt, sends=sends, placed=placed, ducks=ducks, skipped=skipped, notes=notes)


def render_ambience(doc):
    import ambience
    return ambience.render(doc)
