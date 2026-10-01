"""
ambience.py -- continuous environment beds over the whole film (data-driven from the events Doc).

    wind      strength per act (+ wind_gust events, + slow drift); held-breath hushes from the staging notes
    grass     rustle / blade-tick texture following the wind, thinned by fire and masked by rain
    fire      roar + licking flutter + crackle + pops from fire_ignite until the rain has drowned it,
              then a steam-hiss tail
    rain      downpour that hits on rain_start (0.12 s onset), thins at rain_stop, then drips
    thunder   distant rolls every ~6-11 s through the storm (avoiding explicit thunder/lightning events)
    insects   bell-cricket chirps (suzumushi-like) + faint chorus in the moonlit epilogue

render(doc) -> dict(total=(2,N), beds={name: (2,N)}, info={...})
All beds are stereo-decorrelated.  Levels are pre-balanced for the mix (dBFS-ish, before mastering).
"""
import numpy as np

import dsp
import sfx
import timeline as tl
from dsp import SR, n_of, TWO_PI

WIND_BY_ACT = {"prologue": 0.72, "act1": 0.55, "act2": 0.5, "act3": 0.8, "epilogue": 0.3}
GRASS_BY_ACT = {"prologue": 1.0, "act1": 1.0, "act2": 0.55, "act3": 0.25, "epilogue": 0.9}
# staging hushes (shot id, first frame offset, last frame offset, wind factor) -- from config.SHOTS desc / DIRECTION:
#   S06 576-588 "wind drops out (held breath)"; S24d/e 3197-3264 "tails hang, no wind"; S25 "grass frozen (wind 0)";
#   S26 hanging tails in the rain.  Offsets are relative to the shot start, so re-timed shots stay correct.
HUSHES = [("S06", 35, 48, 0.04), ("S24", 124, 191, 0.12), ("S25", 0, 95, 0.05), ("S26", 0, 95, 0.25)]
CTRL_RATE = 100          # control-signal rate (Hz) for slow envelopes


def _rn(x, q=99.7, ceiling=1.6):
    """robust normalisation for sparse textures (crackle, pops, drops): scale by a high percentile of |x|,
    then soft-limit the rare outliers (tanh) so no single grain can spike the bed"""
    ref = np.percentile(np.abs(x), q)
    if ref <= 0:
        return x
    y = x / ref
    return ceiling * np.tanh(y / ceiling)


def _ctrl_axis(doc):
    n = int(np.ceil(doc.duration * CTRL_RATE)) + 1
    return np.arange(n) / CTRL_RATE


def _to_audio(ctrl, N):
    """upsample a CTRL_RATE control curve to audio rate (linear)"""
    tc = np.arange(len(ctrl)) / CTRL_RATE
    return np.interp(np.arange(N) / SR, tc, ctrl)


def _smooth(ctrl, sec):
    if sec <= 0:
        return ctrl
    a = np.exp(-1.0 / (sec * CTRL_RATE))
    from scipy.signal import filtfilt
    return filtfilt([1 - a], [1, -a], ctrl, padlen=min(len(ctrl) - 1, int(3 * sec * CTRL_RATE)))


def _shot_frames(doc, sid):
    for s in doc.shots:
        if s["id"] == sid:
            return s
    return None


def wind_curve(doc):
    tc = _ctrl_axis(doc)
    w = np.zeros_like(tc)
    for a in doc.acts:
        m = (tc >= a["t0"]) & (tc < a["t1"])
        w[m] = WIND_BY_ACT.get(a["id"], 0.5)
    w = _smooth(w, 1.2)
    # S28: "the wind returns" (epilogue lift)
    s28 = _shot_frames(doc, "S28")
    if s28:
        w += 0.22 * np.clip((tc - s28["t0"]) / 3.0, 0, 1) * (tc < s28["t1"] + 2.0)
    r = dsp.rng("wind_drift")
    drift = _smooth(r.standard_normal(len(tc)), 4.0)
    drift /= (np.std(drift) + 1e-9)
    w *= 1.0 + 0.14 * drift
    for e in doc.events:
        if e["type"] == "wind_gust":
            s = float(np.clip(e["strength"], 0.0, 1.3))
            att, rel = 0.8, 2.6
            g = np.clip((tc - e["t"]) / att, 0, 1) * np.exp(-np.maximum(tc - e["t"] - att, 0) / rel) * (tc >= e["t"])
            w += 0.45 * s * g
    # opening: wind rises out of silence over the black of S01
    w *= np.clip(tc / 3.2, 0, 1) ** 1.6
    # hushes
    hush = np.ones_like(tc)
    for sid, a0, a1, fac in HUSHES:
        s = _shot_frames(doc, sid)
        if not s:
            continue
        t0 = s["t0"] + a0 / doc.fps
        t1 = s["t0"] + (a1 + 1) / doc.fps
        m = (tc >= t0) & (tc < t1)
        hush[m] = np.minimum(hush[m], fac)
    hush = _smooth(hush, 0.08)
    return tc, np.clip(w, 0, 1.6) * hush, hush


def render_wind(doc, N, w_audio):
    r = dsp.rng("amb_wind")
    out = np.zeros((2, N))
    for ch in range(2):
        pn = dsp.pink(N, r)
        fc = 220.0 + 2300.0 * np.clip(w_audio, 0, 1.4) ** 1.5
        rush = dsp.tv_biquad(pn, "lp", fc, 0.6, block=512)
        buf = dsp.highpass(dsp.lowpass(dsp.brown(N, r), 140.0, 2), 32.0, 2)   # buffeting, no infrasonic rumble
        howl = np.zeros(N)
        for k in range(2):
            cen = 330.0 + 90.0 * k + 160.0 * dsp.lp_noise(N // 64 + 1, r, 0.08 * 64)[np.arange(N) // 64]
            howl += dsp.tv_biquad(r.standard_normal(N), "bp", np.clip(cen, 180, 900), 9.0, block=512)
        wa = np.clip(w_audio, 0, 1.6)
        out[ch] = 0.9 * rush * wa ** 1.3 + 0.55 * buf * wa ** 1.2 + 0.5 * howl * np.clip(wa - 0.45, 0, None) ** 1.5
    return out


def render_grass(doc, N, w_audio):
    r = dsp.rng("amb_grass")
    tc = _ctrl_axis(doc)
    pres = np.zeros_like(tc)
    for a in doc.acts:
        m = (tc >= a["t0"]) & (tc < a["t1"])
        pres[m] = GRASS_BY_ACT.get(a["id"], 0.8)
    pres = _to_audio(_smooth(pres, 1.5), N)
    wa = np.clip(w_audio, 0, 1.4)
    out = np.zeros((2, N))
    step = 64
    for ch in range(2):
        hs = dsp.bandpass(r.standard_normal(N), 1600, 9000, 2)
        grain = 0.55 + 0.45 * np.abs(dsp.lp_noise(N // step + 1, r, 7.0 * step)[np.arange(N) // step])
        ticks = dsp.crackle(N, r, 40 + 260 * wa, amp_sigma=0.7, dur_range=(0.0002, 0.0012), hp=2500)
        ticks = _rn(ticks) * 0.5
        out[ch] = (hs * grain + 0.35 * ticks) * wa ** 1.5 * pres
    return out


def render_fire(doc, N):
    t_on, t_out = tl.fire_window(doc)
    info = dict(on=t_on, out=t_out)
    out = np.zeros((2, N))
    if t_on is None:
        return out, info
    r_on, _ = tl.rain_window(doc)
    a = max(0, n_of(t_on) - SR // 10)
    b = min(N, n_of(t_out + 8.0) if t_out else N)
    n = b - a
    t = np.arange(n) / SR + a / SR
    env = np.clip((t - t_on) / 0.35, 0, 1)
    if r_on is not None:
        env *= np.where(t < r_on, 1.0, np.exp(-(t - r_on) / 2.2))
    r = dsp.rng("amb_fire")
    for ch in range(2):
        roar = dsp.lowpass(dsp.brown(n, r), 320.0, 2) * (1.0 + 0.35 * dsp.lp_noise(n, r, 0.6))
        flut = dsp.bandpass(r.standard_normal(n), 300, 2600, 2) * (0.6 + 0.4 * np.abs(dsp.lp_noise(n, r, 14.0)))
        cr = dsp.crackle(n, r, 32.0, amp_sigma=1.3, dur_range=(0.0003, 0.004), hp=1500)
        pops = dsp.crackle(n, r, 1.6, amp_sigma=0.8, dur_range=(0.004, 0.015), hp=700)
        mix = 0.9 * roar / (np.std(roar) + 1e-9) + 0.45 * flut / (np.std(flut) + 1e-9) \
            + 0.9 * _rn(cr) + 0.8 * _rn(pops, 99.99)
        steam = np.zeros(n)
        if r_on is not None:
            se = np.clip((t - r_on) / 1.2, 0, 1) * np.exp(-np.maximum(t - r_on - 1.2, 0) / 2.5) * (t >= r_on)
            steam = dsp.bandpass(r.standard_normal(n), 2500, 10000, 2) * se
            steam = 0.7 * steam / (np.std(steam[se > 0.2]) + 1e-9) if np.any(se > 0.2) else steam
        out[ch, a:b] = mix * env + steam
    return out, info


def render_rain(doc, N):
    t_on, t_off = tl.rain_window(doc)
    info = dict(on=t_on, off=t_off)
    out = np.zeros((2, N))
    if t_on is None:
        return out, info
    r = dsp.rng("amb_rain")
    a = max(0, n_of(t_on - 1.6))
    b = N if t_off is None else min(N, n_of(t_off + 12.0))
    n = b - a
    t = np.arange(n) / SR + a / SR
    on = np.clip((t - t_on) / 0.12, 0, 1)                      # the downpour hits on the cut
    off = 1.0 if t_off is None else np.clip(1.0 - (t - t_off) / 1.6, 0, 1) ** 1.5
    # intensity: act III full, S20 slightly less; late S27 thinning handled by `off`
    a3 = next((x for x in doc.acts if x["id"] == "act3"), None)
    inten = np.where(t < (a3["t0"] if a3 else t_on), 0.85, 1.0)
    env = on * off * inten
    pre = (t >= t_on - 1.6) & (t < t_on)                        # first drops before the downpour
    drip_env = np.zeros(n) if t_off is None else np.clip((t - t_off) / 0.8, 0, 1) * np.exp(-np.maximum(t - t_off - 0.8, 0) / 4.0) * (t >= t_off)
    for ch in range(2):
        wash = dsp.bandpass(dsp.pink(n, r), 300, 14000, 2)
        wash = dsp.eq_chain(wash, [("lowshelf", 500, -7.0, 0.7), ("peak", 5200, 2.5, 0.8)])
        fine = dsp.crackle(n, r, 2600 * env + 1, amp_sigma=0.8, dur_range=(0.0002, 0.0011), hp=2500)
        patter = dsp.crackle(n, r, 380 * env + 1, amp_sigma=0.9, dur_range=(0.0008, 0.004), hp=None)
        patter = dsp.bandpass(patter, 700, 4500, 2)
        big = _drops(n, r, 22.0 * env + 3.0 * pre + 5.0 * drip_env)
        y = 0.8 * wash / (np.std(wash) + 1e-9) * env + 0.9 * _rn(fine) * np.maximum(env, 0.02) \
            + 0.7 * _rn(patter) + 0.9 * np.tanh(big)
        out[ch, a:b] = y
    return out, info


def _drops(n, r, rate):
    """resonant water-drop 'plinks' (short rising chirps)"""
    rate = np.broadcast_to(np.asarray(rate, float), (n,))
    hits = np.nonzero(r.random(n) < rate / SR)[0]
    y = np.zeros(n)
    m = n_of(0.03)
    tt = np.arange(m) / SR
    for h in hits:
        f0 = r.uniform(900, 3600)
        ch = np.sin(TWO_PI * np.cumsum(f0 * (1 + 1.4 * tt / tt[-1])) / SR) * np.exp(-tt / r.uniform(0.004, 0.012))
        e = min(n, h + m)
        y[h:e] += r.uniform(0.3, 1.0) * ch[: e - h]
    return y * 0.6


def render_thunder_rolls(doc, N):
    """distant rolls through the storm: one slot every ~5-9 s from shortly after the rain starts; each slot
    slides (<= 2.5 s) to the nearest time >= 3 s away from any explicit thunder / lightning event.  A roll may not
    SOUND (onset + its length) anywhere from 1 s before the music's hard stop to 1.5 s after the white silence: the
    S24 stand-off is rain alone (the 3150 click plays over nothing else).  The last one (after the pass) recedes."""
    t_on, t_off = tl.rain_window(doc)
    out = np.zeros((2, N))
    times = []
    if t_on is None:
        return out, times
    t_end = (t_off - 1.0) if t_off else doc.duration - 10
    avoid = [e["t"] for e in doc.events if e["type"] in ("thunder", "lightning_strike", "raikiri", "tree_split")]
    sil, ws = doc.cue("silence"), doc.cue("white_silence")
    sw = tl.silence_windows(doc).get("all")
    quiet = None
    if sil is not None:
        quiet = (sil - 1.0, (sw[1] if sw else (ws if ws is not None else sil + 9.0)) + 1.5)
    rk = doc.cue("raikiri")
    fp = doc.cue("final_pass")
    r = dsp.rng("amb_thunder")

    def ok(t, D):
        if quiet and t < quiet[1] and t + D > quiet[0]:
            return False
        if rk is not None and t < rk + 0.5 and t + D > rk - 1.0 and t < rk:
            return False                      # nothing rolls into the Raikiri breath
        return all(abs(t - ta) >= 3.0 for ta in avoid) and all(abs(t - tb) >= 4.0 for tb in times)

    t = t_on + r.uniform(2.5, 4.0)
    while t < t_end:
        y, D = sfx._thunder(r, "far")
        cand = sorted(np.arange(-2.5, 2.51, 0.25), key=abs)
        pick = next((t + d for d in cand if ok(t + d, D) and t + d < t_end), None)
        if pick is not None:
            after = fp is not None and pick > fp
            y = dsp.lowpass(y, 600 if after else 900, 2)
            gain = r.uniform(0.4, 0.62) * (0.6 if after else 1.0)
            dsp.place(out, y * gain, n_of(pick))
            times.append(round(float(pick), 2))
        t += r.uniform(5.0, 9.0)
    if quiet:                                  # belt and braces: nothing of a roll survives into the stand-off
        a, b = n_of(quiet[0]), min(N, n_of(quiet[1]))
        f = n_of(0.6)
        out[:, max(0, a - f):a] *= np.linspace(1.0, 0.0, min(f, a))
        out[:, a:b] = 0.0
    return out, times


def _cricket(r, n, fc, level, t0, t_end):
    """one bell-cricket (suzumushi-like) voice: 'riiin' syllables at the stridulation rate, each a slightly
    falling, waveshaped carrier with tooth-rate flutter and a breathy edge (not a bare sine), repeated in phrases"""
    y = np.zeros(n)
    tc = t0
    while tc < t_end - 0.6:
        L = r.uniform(0.25, 0.55)                       # one phrase
        m = n_of(L)
        s = n_of(tc)
        if s + m >= n:
            break
        tt = np.arange(m) / SR
        rate = r.uniform(26, 34)
        syl = (0.5 + 0.5 * np.sin(TWO_PI * rate * tt)) ** 2.2
        f = fc * (1.0 - 0.018 * (tt * rate % 1.0)) * (1.0 + 0.003 * np.sin(TWO_PI * 5 * tt))
        ph = TWO_PI * np.cumsum(f) / SR + r.uniform(0, 6.3)
        car = np.tanh(1.6 * np.sin(ph) + 0.25) - np.tanh(0.25)          # odd + even partials, softly
        z = dsp.lowpass(r.standard_normal(m), 450.0, 2)
        flut = 1.0 + 0.15 * z / (np.std(z) + 1e-9)
        edge = dsp.bandpass(r.standard_normal(m), fc * 0.8, min(fc * 1.3, 15000), 2)
        env = np.clip(tt / 0.03, 0, 1) * np.clip((L - tt) / 0.06, 0, 1)
        v = (car * np.clip(flut, 0.3, 1.8) + 0.06 * edge / (np.std(edge) + 1e-9)) * syl * env
        y[s:s + m] += level * v
        tc += L + r.uniform(0.5, 1.4)
    return y


def render_insects(doc, N):
    _, t_off = tl.rain_window(doc)
    ep = doc.cue("epilogue") or (doc.acts[-1]["t0"] if doc.acts else doc.duration - 14)
    t0 = max((t_off + 2.5) if t_off else ep, ep - 1.0)
    out = np.zeros((2, N))
    if t0 >= doc.duration - 2:
        return out, t0
    a = n_of(t0)
    n = N - a
    t = np.arange(n) / SR
    fade_in = np.clip(t / 5.0, 0, 1) ** 1.5
    r = dsp.rng("amb_insects")
    for k in range(4):
        fc = r.uniform(4150, 4850)
        pan = r.uniform(-0.8, 0.8)
        lvl = r.uniform(0.35, 1.0)
        near = lvl > 0.7
        y = _cricket(r, n, fc, 1.0, r.uniform(0.2, 1.5), n / SR)
        if not near:                                  # the farther ones: duller, a little smeared
            y = dsp.lowpass(y, 6000.0, 2)
        gl, gr = dsp.pan_gains(pan)
        d = int(r.integers(0, 24))                    # tiny inter-channel delay: a position, not a point
        out[0, a:] += lvl * gl * y
        out[1, a + d:] += lvl * gr * y[: n - d]
    for ch in range(2):
        chorus = dsp.bandpass(r.standard_normal(n), 3600, 5600, 2) * (0.5 + 0.5 * np.sin(TWO_PI * 24 * t + ch)) ** 2
        out[ch, a:] += 0.35 * chorus / (np.std(chorus) + 1e-9) * 0.25
    out[:, a:] *= fade_in
    return out, t0


LEVELS = dict(wind=0.055, grass=0.012, fire=0.03, rain=0.034, thunder=0.5, insects=0.012)
PRE_RAIKIRI_DB = -7.0    # the storm holds its breath in the last seconds before the cut (then the mix breath: -20 dB)
RAIN_HUSH_DB = -3.5      # the stand-off after the music stops: the rain steps back so the click / the drop read


def rain_hush(doc):
    """control curve (CTRL_RATE) for the rain level: the downpour settles 2.5 dB after its first second, holds
    its breath before the Raikiri (PRE_RAIKIRI_DB over the last 2.5 s), and steps back -3.5 dB from shortly after
    'silence' until 'white_silence'"""
    tc = _ctrl_axis(doc)
    gdb = np.zeros_like(tc)
    r_on, _ = tl.rain_window(doc)
    rk = doc.cue("raikiri")
    if r_on is not None:
        settle = dsp.smoothstep((tc - (r_on + 1.0)) / 1.5)
        if rk is not None and rk > r_on:
            settle = settle * (tc < rk + 0.1) + (tc >= rk + 0.1) * (1.0 - dsp.smoothstep((tc - (rk + 0.1)) / 1.0))
        gdb += -2.5 * settle
    if rk is not None:
        u = dsp.smoothstep((tc - (rk - 2.5)) / 2.0) * (tc < rk)
        gdb += PRE_RAIKIRI_DB * u
    s, ws = doc.cue("silence"), doc.cue("white_silence")
    if s is not None and ws is not None and ws > s + 2.0:
        u = np.clip((tc - (s + 0.6)) / 1.8, 0, 1) * (tc < ws)
        gdb += RAIN_HUSH_DB * dsp.smoothstep(u)
    return dsp.db2lin(gdb)


def render(doc, keep_beds=True):
    """keep_beds=False: only the total is returned (the mix does not need the separate beds -- saves memory)"""
    N = doc.n_samples
    tc, wc, hush = wind_curve(doc)
    wa = _to_audio(wc, N)
    beds = {}
    beds["wind"] = render_wind(doc, N, wa) * LEVELS["wind"]
    beds["grass"] = render_grass(doc, N, wa) * LEVELS["grass"]
    fire, finfo = render_fire(doc, N)
    beds["fire"] = fire * LEVELS["fire"] * _to_audio(rain_hush(doc), N)
    rain, rinfo = render_rain(doc, N)
    beds["rain"] = rain * LEVELS["rain"] * _to_audio(rain_hush(doc), N)
    th, ttimes = render_thunder_rolls(doc, N)
    beds["thunder"] = th * LEVELS["thunder"]
    ins, it0 = render_insects(doc, N)
    beds["insects"] = ins * LEVELS["insects"]
    total = np.zeros((2, N))
    for k in list(beds):
        total += beds[k]
        if not keep_beds:
            del beds[k]
    total = dsp.dc_block(total, 15.0)
    info = dict(fire=finfo, rain=rinfo, thunder_rolls=ttimes, insects_from=round(it0, 2),
                wind_mean=float(np.mean(wc)), hushes=[h[0] for h in HUSHES])
    return dict(total=total, beds=beds, info=info)
