"""
mix.py -- render the complete soundtrack of Duel in the Silver Grass from an events.json and master it.

usage:
    .venv/bin/python codecinema/productions/silvergrass/audio/mix.py                                   # out/events.json -> out/audio/final_mix.wav
    .venv/bin/python codecinema/productions/silvergrass/audio/mix.py --events out/audio/draft_events.json --out out/audio/demo_mix.wav
    .venv/bin/python codecinema/productions/silvergrass/audio/mix.py --strict                          # exit 2 if a QC check in the report fails

Outputs (paths derive from --out, so a demo run never touches the final's files)
    <out>                       48 kHz / 24-bit PCM / stereo, exactly (FRAME_END-FRAME_START+1)/FPS seconds
    report                      out/audio/mix_report.json for final_mix.wav (the file codecinema/productions/silvergrass/post/assemble.py checks),
                                <out_dir>/<name>_report.json for any other output (e.g. demo_mix_report.json)
    <out_dir>/stems/<name>/music.wav, sfx.wav, ambience.wav
                                32-bit float stems, taken AFTER the bus dynamics, ducking, breaths and silences and
                                scaled by the master's static gain -- but before the master's loudness-map automation,
                                glue compression and limiter (they do not sum exactly to the master; inspection only)
    <out_dir>/spectrograms/<name>_*.png   spectrograms (whole film + zoom windows), stems + loudness-map plots
    The report holds loudness / peaks per act, clip count, events by type, unknown types, onset check, independent
    meters (pyloudnorm, ffmpeg ebur128), the loudness map (targets vs measured), story-hit contrasts, spectral
    balance, music-vs-event sync marks and `checks` (pass/fail per QC gate; `events_real` fails for draft events).

Signal flow
    score.render ─┐  breaths (Raikiri: every stem -20 dB but the inhale)   ducking (music: not under unified hits
    sfx.render_all┼─ + reverb sends ── SFX bus: 2-4 kHz cut, comp ───────┤  or score accents; ambience)
    ambience ─────┘  slow-motion muffle (ambience)                          hard silences / end fade
      -> master: HPF, gentle EQ, low-band + glue compression -> LOUDNESS MAP (section rides to the targets, +3 dB
         impact automation at the unified story hits, routine-peak leveller) -> loudness normalisation -> clip +
         true-peak limiter (iterated)
"""

import argparse
import json
import os
import shutil
import sys
import time
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(HERE, "..", "common"), HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import config  # noqa: E402
import dsp  # noqa: E402
import analysis as an  # noqa: E402
import timeline as tl  # noqa: E402
import score  # noqa: E402
import sfx  # noqa: E402
import ambience  # noqa: E402
from dsp import SR, n_of  # noqa: E402

STEM_GAIN = dict(music=0.55, sfx=1.1, ambience=0.75)
SFX_BUS = dict(thr_over=10.0, ratio=3.0, ceiling_over=15.0)      # dB relative to the SFX stem's own loudness
SFX_BUS_EQ = [("peak", 2300.0, -3.0, 0.7), ("peak", 4200.0, -1.0, 1.2)]   # the clash / grass 'bite' band tamed
MUSIC_BUS = dict(thr_over=7.0, ratio=2.5, ceiling_over=13.0)
AMB_DUCK_FRACTION = 0.6
LOW_BAND = dict(fc=110.0, thr_over=5.0, ratio=3.0)            # master sub-bass compressor (threshold re parked LUFS)
# True-peak safety: the limiter detects inter-sample peaks at 8x and aims TP_MARGIN_DB below the delivery ceiling.
# Meters differ by a few tenths of a dB (ffmpeg's ebur128 reads ~0.35 dB above a 16x reference on this material),
# and the AAC encode in post adds overshoot -- so -1 dBTP must hold on any meter, not just ours.
TP_OVERSAMPLE = 8
TP_MARGIN_DB = 0.5
BLADE_RING_LEVEL = 0.075      # S25 3277: the first sound after the white silence -- thin (~ -24 LUFS momentary in the mix)
# story hits where the music hit and the SFX are designed as ONE event: SFX within +-0.3 s of these cues do not
# duck the music (the music downbeat is part of the impact); they also get the impact automation
UNIFIED_CUES = ("first_clash", "hat_cut", "act2_start", "raikiri", "low_point", "final_pass")
ACCENT_EXEMPT_S = 0.06        # an SFX within 60 ms of a score accent does not duck the music (they are one hit)
# the breath before a story hit: (cue, seconds, {stem: dB}); the Raikiri's is total -- only the inhale is left
BREATH_CUES = (("raikiri", 0.42, dict(music=-20.0, sfx=-20.0, ambience=-20.0)),
               ("act2_start", 0.30, dict(sfx=-6.0, ambience=-8.0)),
               ("low_point", 0.30, dict(ambience=-8.0)))
# ---------------------------------------------------------------- the loudness map (final-master domain, LUFS)
MAP_TARGETS = dict(act1_groove=-16.0, act1_flurry=-14.0, act2=-13.5, act3=-12.5)   # median short-term (3 s)
# the quiet sections are capped (kind 'max': the span's loudness may not exceed the value) so the fight's rides and
# the master's normalisation cannot lift them: the prologue, the stand-off before the first clash, the elder
# listening (S10), the drone after the hat cut, the grave bars after the low point, the rain-alone stand-off (S24),
# the final pass's tail, the epilogue
MAP_CAPS = dict(prologue=-18.5, act1_pre=-17.0, act1_hide=-18.0, tension=-17.5, post_low=-14.5, standoff=-21.0,
                pass_tail=-15.5, epilogue=-20.0)
MAP_TOL_LU = 1.5
SUSPENSION_MAX = -20.0        # 1367 deflect -> 1420 hat cut: held breath, drums out
IMPACT_S = 0.8                # impact automation length at each unified cue (its gain is solved per hit, below)
# story-hit levels (max momentary, final domain): the final pass on top, the Raikiri next, the others a notch below;
# each hit's impact gain is solved (-4..+6 dB) to land on its target
HIT_TARGETS = dict(first_clash=-8.6, hat_cut=-8.6, act2_start=-8.4, raikiri=-8.0, low_point=-8.2, final_pass=-7.2)
PRE_HIT_S = 3.0               # the context before each hit is held HIT_CONTRAST_LU + 0.5 below its target
ROUTINE_MAX = -10.0           # momentary ceiling for everything that is not a unified story hit
HIT_WINDOW = (-0.2, 1.2)      # a story hit's loudness: max momentary with block centre in [t-0.2, t+1.2]
HIT_CONTEXT_S = 3.0           # ... compared with the loudness of the 3 s before it (EBU short-term window)
HIT_CONTRAST_LU = 6.0
# spectral balance of the fight (octave bands re 1 kHz): presence without harshness
BAL_2K_MAX, BAL_4K_MAX = 0.0, -2.0


# ============================================================================================ io helpers
def write_wav24(path, x):
    x = np.clip(np.asarray(x, dtype=np.float64), -1.0, 1.0 - 2.0 ** -23)
    ints = np.round(x.T * 8388607.0).astype("<i4")
    raw = ints.reshape(-1).view(np.uint8).reshape(-1, 4)[:, :3].tobytes()
    with wave.open(path, "wb") as w:
        w.setnchannels(x.shape[0])
        w.setsampwidth(3)
        w.setframerate(SR)
        w.writeframes(raw)


def write_wav_float(path, x):
    from scipy.io import wavfile
    wavfile.write(path, SR, np.asarray(x, dtype=np.float32).T)


def read_wav24(path):
    with wave.open(path, "rb") as w:
        n, ch, sw, sr = w.getnframes(), w.getnchannels(), w.getsampwidth(), w.getframerate()
        raw = w.readframes(n)
    b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
    ints = (b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) | (b[:, 2].astype(np.int32) << 16))
    ints = np.where(ints >= 1 << 23, ints - (1 << 24), ints)
    return (ints.reshape(-1, ch).T / 8388608.0), sr, sw


def is_final_output(out_path):
    """True when out_path is the delivery mix config.FINAL_MIX_WAV (the file post/assemble.py muxes)"""
    return os.path.realpath(out_path) == os.path.realpath(config.FINAL_MIX_WAV)


def default_paths(out_path):
    """report / stems / spectrogram locations derived from the output file: config.FINAL_MIX_WAV keeps the canonical
    config.MIX_REPORT_JSON (what post/assemble.py verifies); any other output gets its own <name>_report.json"""
    out_dir = os.path.dirname(os.path.abspath(out_path))
    name = os.path.splitext(os.path.basename(out_path))[0]
    rep = config.MIX_REPORT_JSON if is_final_output(out_path) else os.path.join(out_dir, f"{name}_report.json")
    return dict(report=rep, stems=os.path.join(out_dir, "stems", name), spec=os.path.join(out_dir, "spectrograms"))


# ============================================================================================ gain curves
def duck_curve(ducks, N, fraction=1.0):
    """event ducking: -depth dB from 12 ms before the hit, held, exponential release; min() across events"""
    rate = 1000
    n = int(np.ceil(N / SR * rate)) + 2
    g = np.zeros(n)
    tt = np.arange(n) / rate
    for (t, depth, hold, rel) in ducks:
        d = depth * fraction
        a = t - 0.012
        m = tt >= a
        env = np.where(tt[m] <= t + hold, -d, -d * np.exp(-(tt[m] - t - hold) / max(rel / 3.0, 1e-3)))
        ramp = np.clip((tt[m] - a) / 0.012, 0, 1)
        g[m] = np.minimum(g[m], env * ramp)
    return dsp.db2lin(np.interp(np.arange(N) / SR, tt, g))


def breath_window(doc):
    """(t0, t1) of the Raikiri breath (the SFX renderer fades rolling thunder by t0 and exempts the inhale)"""
    for cue, d, _ in BREATH_CUES:
        if cue == "raikiri" and doc.cue(cue) is not None:
            t = doc.cue(cue)
            return (t - d - 0.08, t)
    return None


def breath_curves(doc, N):
    """{stem: gain curve}: a quick dip before each BREATH_CUES hit (80 ms fade in, 25 ms release AT the hit)"""
    rate = 1000
    n = int(np.ceil(N / SR * rate)) + 2
    tt = np.arange(n) / rate
    g = {k: np.zeros(n) for k in ("music", "sfx", "ambience")}
    info = []
    for cue, d, dbs in BREATH_CUES:
        t = doc.cue(cue)
        if t is None:
            continue
        a, b = t - d - 0.08, t - 0.004
        u = np.clip((tt - a) / 0.08, 0, 1) * (tt < b) + np.clip(1.0 - (tt - b) / 0.025, 0, 1) * (tt >= b)
        for k, db in dbs.items():
            g[k] = np.minimum(g[k], db * dsp.smoothstep(u))
        info.append(dict(cue=cue, t=round(t, 3), from_s=round(a, 3), dip_db=dbs))
    ta = np.arange(N) / SR
    return {k: dsp.db2lin(np.interp(ta, tt, v)) for k, v in g.items()}, info


def split_ducks(ducks, doc, accents, window=0.3):
    """-> (ducks for the music, ducks for the ambience): SFX that belong to a unified story hit, or land within
    60 ms of a score accent (the drum IS the hit), leave the music alone"""
    ts = [doc.cue(c) for c in UNIFIED_CUES if doc.cue(c) is not None]
    acc = np.asarray(sorted(accents)) if len(accents) else np.array([-1e9])
    music = []
    for d in ducks:
        if any(abs(d[0] - t) <= window for t in ts):
            continue
        if np.min(np.abs(acc - d[0])) <= ACCENT_EXEMPT_S:
            continue
        music.append(d)
    return music, ducks


def apply_muffle(x, windows, fc_low=650.0, gain_db=-4.0, t_in=0.15, t_out=0.35):
    """slow-motion 'time dilation': low-pass sweep + small dip inside each window (segment-wise, cheap)"""
    y = x.copy()
    N = x.shape[-1]
    for (a, b, _) in windows:
        s0 = max(0, n_of(a - 0.3))
        s1 = min(N, n_of(b + t_out + 0.3))
        if s1 <= s0:
            continue
        t = np.arange(s0, s1) / SR
        u = np.clip((t - a) / t_in, 0, 1) * np.clip((b + t_out - t) / t_out, 0, 1)
        u = dsp.smoothstep(u)
        fc = np.exp(np.log(20000.0) + (np.log(fc_low) - np.log(20000.0)) * u)
        seg = dsp.lp_sweep(x[:, s0:s1], fc, n_bank=12, fmin=fc_low * 0.9)
        y[:, s0:s1] = seg * dsp.db2lin(gain_db * u)
    return y


def gate(x, t0, t1, fade_in=0.004, fade_out=0.004):
    """exact digital silence in [t0, t1) with short fades outside the window (no clicks)"""
    N = x.shape[-1]
    a, b = int(round(t0 * SR)), int(round(t1 * SR))
    fo, fi = n_of(fade_out), n_of(fade_in)
    if a > 0:
        m = min(fo, a)
        x[:, a - m:a] *= np.linspace(1.0, 0.0, m)
    x[:, max(0, a):min(N, b)] = 0.0
    if b < N and fi > 0:
        m = min(fi, N - b)
        x[:, b:b + m] *= np.linspace(0.0, 1.0, m)
    return x


def end_fade(x, t_fade0, t_zero):
    a, b = n_of(t_fade0), n_of(t_zero)
    if b > a:
        u = np.linspace(0, 1, b - a)
        x[:, a:b] *= 0.5 + 0.5 * np.cos(np.pi * u)
    x[:, b:] = 0.0
    return x


def bus_dynamics(sfx_stem, music):
    """SFX bus: presence cut (2-4 kHz), fast peak compressor (3:1, 0.8 ms) + soft limiter so impacts keep their punch
    but stop dominating the master limiter; music bus: gentle glue (2.5:1, 6 ms).  Thresholds are relative to each
    stem's own integrated loudness, so they adapt to whatever the events file contains."""
    info = {}
    sfx_stem = dsp.eq_chain(sfx_stem, SFX_BUS_EQ)
    Ls = an.loudness_integrated(sfx_stem)
    thr = Ls + SFX_BUS["thr_over"]
    y, gr = dsp.compressor(sfx_stem, threshold_db=thr, ratio=SFX_BUS["ratio"], attack_ms=0.8, release_ms=140.0,
                           knee_db=6.0, block=16, mode="peak")
    ceil = dsp.db2lin(Ls + SFX_BUS["ceiling_over"])
    y = dsp.soft_limit(y, ceil, knee=0.7)
    info["sfx"] = dict(lufs_in=round(Ls, 2), thr_db=round(thr, 2), max_gr_db=round(float(-np.min(gr)), 2),
                       eq=SFX_BUS_EQ)
    Lm = an.loudness_integrated(music)
    mthr = Lm + MUSIC_BUS["thr_over"]
    m, gm = dsp.compressor(music, threshold_db=mthr, ratio=MUSIC_BUS["ratio"], attack_ms=6.0, release_ms=220.0,
                           knee_db=6.0, block=32, mode="peak")
    m = dsp.soft_limit(m, dsp.db2lin(Lm + MUSIC_BUS["ceiling_over"]), knee=0.8)
    info["music"] = dict(lufs_in=round(Lm, 2), thr_db=round(mthr, 2), max_gr_db=round(float(-np.min(gm)), 2))
    return y, m, info


# ============================================================================================ loudness map
def map_spans(doc, M):
    """the loudness-map sections (data-driven: cue / event-derived score marks, shot starts).  kind 'ride' sets the
    median short-term loudness, 'max' caps the span's loudness (the suspension, the context before each story hit)."""
    C = {k: v["t"] for k, v in doc.cues.items()}
    m1 = M["marks"]["act1"]
    secs = {s["name"]: s for s in M["sections"]}

    def shot(sid, default):
        for s in doc.shots:
            if s["id"] == sid:
                return s["t0"]
        return default
    t_gs, t_ov, t_sh = m1["grass_shear"], m1["overhead"], m1["shove"]
    t_low = M["marks"]["act3"]["low_point"]
    sp = [dict(name="act1_groove", t0=secs["act1"]["t0"] + 1.2, t1=min(shot("S10", t_gs - 6.0), t_gs - 0.3),
               target=MAP_TARGETS["act1_groove"], kind="ride"),
          dict(name="act1_flurry", t0=t_ov + 1.2, t1=t_sh - 0.1, target=MAP_TARGETS["act1_flurry"], kind="ride"),
          dict(name="suspension", t0=m1["perfect_deflect"] + 0.6, t1=m1["hat_cut"] - 0.05, target=SUSPENSION_MAX,
               kind="max"),
          dict(name="act2", t0=C["act2_start"] + 1.5, t1=C.get("thunder_first", secs["act2"]["t1"] - 6.0) - 0.1,
               target=MAP_TARGETS["act2"], kind="ride"),
          dict(name="act3", t0=C["raikiri"] + 1.5, t1=min(shot("S23", t_low - 3.0), t_low - 1.5),
               target=MAP_TARGETS["act3"], kind="ride")]
    caps = [("prologue", 0.0, C["act1_start"]), ("act1_pre", C["act1_start"], C["first_clash"] - PRE_HIT_S),
            ("act1_hide", shot("S10", t_gs - 6.0), t_gs - 0.3), ("tension", m1["hat_cut"] + 1.5, m1["spear_draw"] - 0.2),
            ("post_low", t_low + 1.6, C["silence"] - 0.05),
            ("standoff", C["silence"] + 0.5, C.get("white_silence", C["final_pass"]) - 0.1),
            ("pass_tail", C["final_pass"] + 2.0, C["epilogue"]), ("epilogue", C["epilogue"], C.get("end_card", doc.duration))]
    for name, a, b in caps:
        sp.append(dict(name=name, t0=a, t1=b, target=MAP_CAPS[name], kind="max"))
    for c in UNIFIED_CUES:
        if c in C:
            sp.append(dict(name=f"pre_{c}", t0=C[c] - PRE_HIT_S, t1=C[c] - 0.02,
                           target=HIT_TARGETS[c] - HIT_CONTRAST_LU - 0.8, kind="max", pre_hit=True))
    return [s for s in sp if s["t1"] - s["t0"] > 0.5]


def _integrated_from_blocks(z):
    L = an._to_lufs(z)
    zg = z[L > -70.0]
    if zg.size == 0:
        return -np.inf
    rel = an._to_lufs(np.mean(zg)) - 10.0
    zg2 = z[(L > -70.0) & (L > rel)]
    return float(an._to_lufs(np.mean(zg2))) if zg2.size else -np.inf


def loudness_map(x, spans, hits, target_lufs, duration, loss_db=None, log=print):
    """section rides + per-hit impact automation + routine-peak leveller, solved in the K-weighted energy domain
    (400 ms blocks, 50 ms hop; a slowly varying gain scales block energies) -> (audio-rate gain, info).
    hits: [(name, t, target max-momentary LUFS)].  Levels are compared in the FINAL domain: measured +
    (target_lufs - estimated integrated loudness after the map).  loss_db (per block, >= 0): the loudness the final
    limiter took off each block in the previous pass -- the solver sees the LIMITED levels (story hits lose 1-3 LU)."""
    from scipy.ndimage import minimum_filter1d, uniform_filter1d
    hop = 0.05
    tb, z = an.k_block_energy(x, 0.4, hop)
    if loss_db is not None:
        z = z * 10 ** (-np.clip(loss_db[:len(z)], 0.0, 20.0) / 10.0)
    tcb = tb + 0.2
    rate = 100
    n_c = int(np.ceil(duration * rate)) + 2
    tc = np.arange(n_c) / rate
    ride = np.zeros(n_c)
    lev = np.zeros(n_c)
    shapes = []
    for name, t, tgt in hits:
        u = np.clip((tc - (t - 0.015)) / 0.015, 0, 1) * np.clip(1.0 - (tc - (t + IMPACT_S)) / 0.25, 0, 1)
        shapes.append(dsp.smoothstep(u))
    hit_db = np.zeros(len(hits))
    excl = [(t + HIT_WINDOW[0] - 0.3, t + HIT_WINDOW[1] + 0.4) for _, t, _ in hits]
    in_excl = np.zeros(len(tcb), bool)
    for a, b in excl:
        in_excl |= (tcb >= a) & (tcb <= b)

    def span_w(sp, ramp=0.5):
        a, b = sp["t0"], sp["t1"]
        if sp.get("pre_hit"):             # ramp in inside the span, release in 30 ms right at the hit
            return dsp.smoothstep((tc - a) / ramp) * dsp.smoothstep((b - tc) / 0.03)
        return dsp.smoothstep((tc - (a - ramp)) / ramp) * dsp.smoothstep(((b + ramp) - tc) / ramp)
    info = dict(spans=[], hits=[], iterations=[])
    for it in range(8):
        imp = np.zeros(n_c)
        for k in range(len(hits)):
            imp = np.where(shapes[k] > 0, shapes[k] * hit_db[k] + (1 - shapes[k]) * imp, imp)
        g = ride + lev + imp
        zb = z * 10 ** (np.interp(tcb, tc, g) / 10.0)
        L_int = _integrated_from_blocks(zb)
        off = target_lufs - L_int
        k3 = int(round((3.0 - 0.4) / hop)) + 1
        st = uniform_filter1d(zb, size=k3, origin=-(k3 // 2), mode="nearest")
        changed = 0.0
        for sp in spans:
            m = (tb >= sp["t0"]) & (tb + 3.0 <= sp["t1"])
            if sp["kind"] == "ride" and np.any(m):
                Lm = float(np.median(an._to_lufs(st[m])))
            else:
                m = (tb >= sp["t0"] - 0.2) & (tb + 0.4 <= sp["t1"] + 0.2)
                if not np.any(m):
                    continue
                Lm = float(an._to_lufs(np.mean(zb[m])))
            Lf = Lm + off
            if sp["kind"] == "ride":
                d = float(np.clip(sp["target"] - Lf, -6.0, 6.0))
            else:
                d = min(0.0, sp["target"] - 0.3 - Lf)
            if abs(d) > 0.05:
                ride = np.clip(ride + d * span_w(sp), -12.0, 8.0)
                changed = max(changed, abs(d))
        Lb = an._to_lufs(zb) + off
        for k, (name, t, tgt) in enumerate(hits):
            m = (tcb >= t + HIT_WINDOW[0]) & (tcb <= t + HIT_WINDOW[1])
            if np.any(m):
                d = tgt - float(np.max(Lb[m]))
                new = float(np.clip(hit_db[k] + d, -4.0, 6.0))
                changed = max(changed, abs(new - hit_db[k]))
                hit_db[k] = new
        # leveller: routine momentary peaks above ROUTINE_MAX (final domain), outside the story-hit windows
        over = np.where(in_excl, 0.0, np.maximum(0.0, Lb - (ROUTINE_MAX - 0.3)))
        if np.any(over > 0.05):
            req = np.zeros(n_c)
            for i in np.nonzero(over > 0.05)[0]:
                a, b = int(tb[i] * rate), int((tb[i] + 0.4) * rate) + 1
                req[a:b] = np.minimum(req[a:b], -over[i])
            req = minimum_filter1d(req, size=int(0.1 * rate) * 2 + 1)
            req = uniform_filter1d(req, size=int(0.12 * rate))
            lev = np.maximum(np.minimum(lev, lev + req), -9.0)
            changed = max(changed, float(np.max(over)))
        info["iterations"].append(dict(L_int_est=round(L_int + off, 2), offset_db=round(off, 2),
                                       max_change_db=round(changed, 2)))
        if changed < 0.1:
            break
    imp = np.zeros(n_c)
    for k in range(len(hits)):
        imp = np.where(shapes[k] > 0, shapes[k] * hit_db[k] + (1 - shapes[k]) * imp, imp)
    g = ride + lev + imp
    for sp in spans:
        m = (tc >= sp["t0"]) & (tc <= sp["t1"])
        info["spans"].append(dict(name=sp["name"], ride_db=round(float(np.median(ride[m])), 2) if np.any(m) else 0.0,
                                  leveller_min_db=round(float(np.min(lev[m])), 2) if np.any(m) else 0.0))
    info["hits"] = [dict(cue=n, target=tg, impact_db=round(float(h), 2)) for (n, _, tg), h in zip(hits, hit_db)]
    info["offset_db"] = float(off)
    info["leveller_time_below_1db_s"] = round(float(np.sum(lev < -1.0) / rate), 2)
    ga = dsp.db2lin(np.interp(np.arange(x.shape[-1]) / SR, tc, g))
    return ga, info


def _normalise_limit(x, target_lufs, ceiling_dbtp, g0=None, log=print):
    """loudness normalisation + clip-then-limit (true peak), iterated -> (y, gain dB, limiter gain curve)"""
    g = (target_lufs - an.loudness_integrated(x)) if g0 is None else g0
    tp_goal = ceiling_dbtp - TP_MARGIN_DB                        # what our 8x meter must read
    ceil = tp_goal - 0.1
    y, lim_gain = None, None
    clip_ceil = dsp.db2lin(ceiling_dbtp + 1.5)
    for it in range(6):
        # clip-then-limit: a soft clipper shaves the top ~2 dB of millisecond transients (clash cracks),
        # the look-ahead true-peak limiter does the rest with a short release (little pumping)
        xc = dsp.soft_limit(x * dsp.db2lin(g), clip_ceil, knee=0.72)
        y, lim_gain = dsp.limiter(xc, ceiling_db=ceil, lookahead_ms=5.0, release_ms=70.0, oversample=TP_OVERSAMPLE)
        del xc
        L = an.loudness_integrated(y)
        tp = an.true_peak_dbtp(y)
        log(f"   master iter {it}: gain {g:+.2f} dB -> {L:.2f} LUFS, TP {tp:.2f} dBTP, max limiting {-dsp.lin2db(np.min(lim_gain)):.1f} dB")
        if abs(L - target_lufs) <= 0.05 and tp <= tp_goal:
            break
        g += (target_lufs - L)
        if tp > tp_goal:
            ceil -= (tp - tp_goal) + 0.05
    tp = an.true_peak_dbtp(y)
    if tp > tp_goal:
        y *= dsp.db2lin(tp_goal - tp - 0.02)
    return y, g, lim_gain


def master(mix, target_lufs=config.AUDIO_TARGET_LUFS, ceiling_dbtp=config.AUDIO_TRUE_PEAK_DB, spans=(), hits=(),
           log=print):
    """HPF + gentle EQ + low-band / glue compression, the loudness map, then loudness normalisation with a
    true-peak limiter.  The story-hit levels are closed THROUGH the limiter: the hits are measured on the limited
    master and their impact gains corrected (outer loop), because the limiter takes 1.5-2.5 LU off a hit whose
    first 100 ms carry most of its 400 ms energy.  Returns (y, static gain of the stems, info)."""
    x = dsp.highpass(mix, 28.0, 4)
    x = dsp.eq_chain(x, [("lowshelf", 55.0, -1.0, 0.7), ("highshelf", 7000.0, 1.5, 0.7)])
    L0 = an.loudness_integrated(x)
    pre = dsp.db2lin((target_lufs - 2.0) - L0)                  # park the programme near the target first
    x = x * pre
    # sub-bass control: LR4 low band (< fc) peak compressor.  Stacked booms (o-daiko + sub + thunder) are ~90 % of
    # the energy of the big hits; left alone they drive the full-band limiter and duck everything above them.
    lo, hi = dsp.lr4_split(x, LOW_BAND["fc"])
    lo, grl = dsp.compressor(lo, threshold_db=(target_lufs - 2.0) + LOW_BAND["thr_over"], ratio=LOW_BAND["ratio"],
                             attack_ms=4.0, release_ms=160.0, knee_db=4.0, block=32, mode="peak")
    x = lo + hi
    del lo, hi
    low_gr_max = float(-np.min(grl))
    x, gr = dsp.compressor(x, threshold_db=-16.0, ratio=1.6, attack_ms=25.0, release_ms=260.0, knee_db=8.0)
    comp_gr_max = float(-np.min(gr))
    loss, g, outer = None, None, []
    for k in range(5):
        gmap, lm_info = loudness_map(x, spans, hits, target_lufs, x.shape[-1] / SR, loss_db=loss, log=log)
        xm = x * gmap
        del gmap
        y, g, lim_gain = _normalise_limit(xm, target_lufs, ceiling_dbtp, g0=g, log=log)
        _, zx = an.k_block_energy(xm, 0.4, 0.05)
        _, zy = an.k_block_energy(y, 0.4, 0.05)
        del xm
        loss = np.maximum(0.0, 10 * np.log10((zx * 10 ** (g / 10.0) + 1e-20) / (zy + 1e-20)))
        tm, mo = an.momentary_curve(y, 0.05)
        err = {}
        for n, t, tg in hits:
            m = (tm >= t + HIT_WINDOW[0]) & (tm <= t + HIT_WINDOW[1])
            if np.any(m):
                err[n] = tg - float(np.max(mo[m]))
        d_off = g - lm_info["offset_db"]
        outer.append(dict(hits={n: round(v, 2) for n, v in err.items()}, offset_err_db=round(d_off, 2),
                          max_block_loss_db=round(float(np.max(loss)), 2)))
        log(f"   story hits vs targets (LU): {outer[-1]['hits']}  map offset error {d_off:+.2f} dB")
        settled = abs(d_off) <= 0.3 or (len(outer) > 1 and abs(d_off - outer[-2]["offset_err_db"]) < 0.1)
        if (not err or max(abs(v) for v in err.values()) <= 0.4) and settled:
            break
        if k < 4:
            del y
    total_gain = pre * dsp.db2lin(g)
    info = dict(pre_gain_db=float(dsp.lin2db(pre)), post_gain_db=float(g), comp_max_gr_db=comp_gr_max,
                low_band_max_gr_db=low_gr_max, low_band_gr_time_over_3db_s=float(np.sum(grl < -3.0) / SR),
                limiter_max_gr_db=float(-dsp.lin2db(np.min(lim_gain))),
                limiter_gr_time_over_1db_s=float(np.sum(lim_gain < dsp.db2lin(-1.0)) / SR),
                limiter_gr_time_over_3db_s=float(np.sum(lim_gain < dsp.db2lin(-3.0)) / SR),
                loudness_map=lm_info)
    return y, total_gain, info


# ============================================================================================ measurements
HERO_ONSET_TYPES = {"clash", "clash_heavy", "perfect_deflect", "kunai_deflect", "sword_break", "hat_cut", "raikiri",
                    "tree_split", "lightning_strike", "tsuba_click", "kick", "draw", "cord_cut"}


def onset_check(sfx_stem, placed, doc, pre_stem=None, silent=()):
    """onset detection on the rendered SFX stem for every impulsive event (nearest detected energy rise).
    Events whose own clip is >10 dB below the stem during their first 20 ms (masked by a simultaneous
    louder sound) are reported separately and not counted; so are events inside windows that are silent by
    design (`silent`: [(t0, t1)], e.g. the end fade) and events in the first 20 ms (no pre-window).
    Gate: every 'hero' impact within 10 ms and >= 95 % of all checked events."""
    res = []
    masked = []
    ref = pre_stem if pre_stem is not None else sfx_stem
    for p in placed:
        if p["type"] not in sfx.IMPULSIVE:
            continue
        if p["t"] < 0.02 or any(a <= p["t"] < b for (a, b) in silent):
            continue
        i0 = n_of(p["t"])
        e_stem = float(np.sum(ref[:, i0:i0 + n_of(0.02)] ** 2))
        rel = 10 * np.log10((p.get("e_on", e_stem) + 1e-20) / (e_stem + 1e-20))
        if rel < -10.0:
            masked.append(dict(t=round(p["t"], 3), type=p["type"], rel_db=round(rel, 1)))
            continue
        t_on, rise = an.guided_onset(sfx_stem, p["t"], search=0.05)
        if t_on is None:
            continue
        res.append(dict(t=round(p["t"], 4), frame=p["frame"], type=p["type"], err_ms=round((t_on - p["t"]) * 1000, 2),
                        rise_db=round(rise, 1)))
    errs = np.array([abs(r["err_ms"]) for r in res]) if res else np.zeros(0)
    det = an.onset_times(sfx_stem)
    match = []
    for r in res:
        if len(det):
            j = int(np.argmin(np.abs(det - r["t"])))
            match.append(abs(det[j] - r["t"]) * 1000)
    match = np.array(match) if match else np.array([np.inf])
    hero = [r for r in res if r["type"] in HERO_ONSET_TYPES]
    hero_ok = sum(1 for r in hero if abs(r["err_ms"]) <= 10.0)
    within = int(np.sum(errs <= 10.0))
    return dict(checked=len(res), within_10ms=within,
                max_abs_ms=float(np.max(errs)) if errs.size else 0.0,
                mean_abs_ms=float(np.mean(errs)) if errs.size else 0.0,
                median_abs_ms=float(np.median(errs)) if errs.size else 0.0,
                hero_checked=len(hero), hero_within_10ms=hero_ok,
                gate_pass=bool(hero_ok == len(hero) and within >= 0.95 * len(res)),
                unguided_detected=int(len(det)), unguided_within_10ms=int(np.sum(match <= 10.0)) if res else 0,
                masked_excluded=masked, outliers=[r for r in res if abs(r["err_ms"]) > 10.0][:20])


def music_sync(M, fps):
    """every event-driven music accent must sit within 1 frame of its event"""
    tol = 1.0 / fps
    rows = [m for m in M["event_marks"] if m.get("t_event") is not None]
    bad = [m for m in rows if abs(m["t"] - m["t_event"]) > tol + 1e-6]
    return dict(checked=len(rows), hit_points=len(M["hits"]), tolerance_ms=round(tol * 1000, 1),
                max_abs_ms=round(max([abs(m["t"] - m["t_event"]) * 1000 for m in rows], default=0.0), 2),
                failures=bad, grid_warnings=M["warnings"], pass_=not bad)


def story_hits(y, doc, t_hits):
    """loudness of each unified story hit vs its context, and the film's loudest moment"""
    tm, mo = an.momentary_curve(y, 0.05)
    k = int(np.argmax(mo))
    film_max = dict(t=round(float(tm[k]), 2), lufs=round(float(mo[k]), 2))
    rows = []
    for name, t in t_hits:
        m = (tm >= t + HIT_WINDOW[0]) & (tm <= t + HIT_WINDOW[1])
        hit = float(np.max(mo[m])) if np.any(m) else -np.inf
        c3 = an.loudness_window(y, t - HIT_CONTEXT_S, t)
        c6 = an.loudness_window(y, t - 6.0, t)
        rows.append(dict(cue=name, t=round(t, 3), hit_max_momentary=round(hit, 2), context_3s=round(c3, 2),
                         context_6s=round(c6, 2), contrast_3s=round(hit - c3, 2), contrast_6s=round(hit - c6, 2)))
    # routine peaks: loudest momentary outside every story-hit window
    ex = np.zeros(len(tm), bool)
    for _, t in t_hits:
        ex |= (tm >= t + HIT_WINDOW[0] - 0.3) & (tm <= t + HIT_WINDOW[1] + 0.4)
    rk = np.argsort(np.where(ex, -np.inf, mo))[::-1][:5]
    routine = [dict(t=round(float(tm[i]), 2), lufs=round(float(mo[i]), 2)) for i in rk if np.isfinite(mo[i])]
    return dict(hits=rows, film_max=film_max, loudest_routine=routine)


def loudness_map_report(y, spans):
    out = []
    for sp in spans:
        st = an.short_term_stats(y, sp["t0"], sp["t1"])
        L = an.loudness_window(y, sp["t0"], sp["t1"])
        if sp["kind"] == "ride":
            ok = abs(st["median"] - sp["target"]) <= MAP_TOL_LU
        else:
            ok = L <= sp["target"] + 0.5
        out.append(dict(name=sp["name"], t0=round(sp["t0"], 2), t1=round(sp["t1"], 2), target=sp["target"],
                        kind=sp["kind"], short_term_median=round(st["median"], 2), short_term_p10=round(st["p10"], 2),
                        short_term_p90=round(st["p90"], 2), loudness=round(L, 2), ok=bool(ok)))
    return out


def spectral_balance(y, spans, extra):
    rows = []
    for name, a, b, fight in [(s["name"], s["t0"], s["t1"], s["kind"] == "ride") for s in spans
                              if s["kind"] == "ride" or s["name"] == "suspension"] + extra:
        ob = an.octave_bands(y, a, b)
        if ob is None:
            continue
        lf = an.power_fraction_below(y, a, b, 120.0)
        ok = (not fight) or (ob["2000"] <= BAL_2K_MAX + 0.05 and ob["4000"] <= BAL_4K_MAX + 0.05)
        rows.append(dict(name=name, t0=round(a, 2), t1=round(b, 2), fight=fight, octaves_re_1k=ob,
                         power_below_120hz=round(lf, 3) if lf is not None else None, ok=bool(ok)))
    return rows


def section_stats(y, sections, stems):
    """loudness per music section (mix + each stem) and the loudest momentary (400 ms) value in it"""
    out = []
    for s in sections:
        a, b = n_of(s["t0"]), n_of(s["t1"])
        if b - a < n_of(0.5):
            continue
        seg = y[:, a:b]
        _, mo = an.loudness_curve(seg, 0.4, 0.05)
        row = dict(name=s["name"], t0=s["t0"], t1=s["t1"], lufs=round(an.loudness_integrated(seg), 2),
                   max_momentary=round(float(np.max(mo)), 2) if mo.size else None)
        for k, v in stems.items():
            L = an.loudness_integrated(v[:, a:b])
            row[f"{k}_lufs"] = round(L, 2) if np.isfinite(L) else None
        out.append(row)
    return out


def mono_compat(y):
    """L/R correlation (energy-weighted, 1 s blocks) and the loudness change of a mono fold-down"""
    L, R = y[0], y[1]
    blk = SR
    nb = len(L) // blk
    cs, ws = [], []
    for i in range(nb):
        l, r = L[i * blk:(i + 1) * blk], R[i * blk:(i + 1) * blk]
        e = float(np.dot(l, l) + np.dot(r, r))
        if e > 1e-9:
            cs.append(float(np.dot(l, r) / np.sqrt(np.dot(l, l) * np.dot(r, r) + 1e-30)))
            ws.append(e)
    cs, ws = np.array(cs), np.array(ws)
    m = 0.5 * (L + R)
    d = an.loudness_integrated(np.vstack([m, m])) - an.loudness_integrated(y)
    return dict(corr_weighted=round(float(np.sum(cs * ws) / max(np.sum(ws), 1e-20)), 3) if len(cs) else None,
                corr_min_1s=round(float(np.min(cs)), 3) if len(cs) else None,
                mono_fold_lufs_delta=round(float(d), 2))


FFMPEG = config.FFMPEG           # settings tools.ffmpeg (auto-detected; may be a bare command name)
FFMPEG_TIMEOUT_S = 120           # the ebur128 meter pass over the whole film


def ffmpeg_ebur128(path):
    """independent meter: ffmpeg's EBU R128 filter on the written file -> dict(I LUFS, LRA LU, TP dBTP) or None"""
    import re
    import subprocess
    if not (shutil.which(FFMPEG) or os.path.isfile(FFMPEG)):
        return None
    try:
        out = subprocess.run([FFMPEG, "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=peak=true",
                              "-f", "null", "-"], capture_output=True, text=True, timeout=FFMPEG_TIMEOUT_S).stderr
    except (OSError, subprocess.SubprocessError):
        return None
    tail = out[out.rfind("Summary:"):] if "Summary:" in out else out

    def grab(key):
        m = re.search(key + r":\s+(-?[0-9.]+|-inf)", tail)
        return float(m.group(1)) if m else None
    return dict(integrated_lufs=grab("I"), lra_lu=grab("LRA"), true_peak_dbtp=grab("Peak"))


def crosscheck_loudness(y, path=None):
    """independent BS.1770 implementations: pyloudnorm (if installed) and ffmpeg ebur128 on the written file"""
    out = {}
    try:
        import pyloudnorm as pyln
        out["pyloudnorm_lufs"] = round(float(pyln.Meter(SR).integrated_loudness(y.T)), 2)
    except Exception as ex:          # noqa: BLE001 -- optional dependency
        out["pyloudnorm_lufs"] = None
        out["note"] = str(ex)[:120]
    if path:
        out["ffmpeg_ebur128"] = ffmpeg_ebur128(path)
    return out


def per_act_stats(x, doc):
    out = []
    for a in doc.acts:
        seg = x[:, n_of(a["t0"]):n_of(a["t1"])]
        out.append(dict(id=a["id"], t0=round(a["t0"], 3), t1=round(a["t1"], 3),
                        lufs=round(an.loudness_integrated(seg), 2),
                        peak_dbfs=round(float(dsp.lin2db(np.max(np.abs(seg)))), 2),
                        true_peak_dbtp=round(an.true_peak_dbtp(seg), 2)))
    return out


# ============================================================================================ main
def render(events_path=None, out_path=None, report_path=None, stems_dir=None, spec_dir=None,
           target_lufs=config.AUDIO_TARGET_LUFS, ceiling=config.AUDIO_TRUE_PEAK_DB, spectrograms=True, log=print):
    T0 = time.time()
    timings = {}
    doc = tl.load(events_path)
    N = doc.n_samples
    C = {k: v["t"] for k, v in doc.cues.items()}
    out_path = out_path or config.FINAL_MIX_WAV
    dp = default_paths(out_path)
    report_path, stems_dir, spec_dir = report_path or dp["report"], stems_dir or dp["stems"], spec_dir or dp["spec"]
    log(f"events: {doc.path}  ({len(doc.events)} events, draft={doc.draft}) -> {N} samples = {N / SR:.3f} s")
    for w in doc.warnings:
        log("   warning:", w)

    # ---------------------------------------------------------------- music
    t = time.time()
    M = score.render(doc)
    music = M["stem"]
    timings["music_s"] = round(time.time() - t, 1)
    log(f"music: {M['notes']} notes in {timings['music_s']} s")
    for w in M["warnings"]:
        log("   music warning:", w)

    # ---------------------------------------------------------------- sfx
    t = time.time()
    score_bells = [C[k] for k in ("title", "end_card") if k in C]
    bw = breath_window(doc)
    X = sfx.render_all(doc, merged_bells=score_bells, merged_stingers=[M["marks"]["act1"]["hat_cut"]], breath=bw)
    sfx_dry = X["dry"]
    br = C.get("blade_ring")
    blade_ring_placed = False
    if br is not None:
        near = [p for p in X["placed"] if abs(p["t"] - br) < 3.0 / doc.fps and p["type"] in
                ("clash", "clash_heavy", "perfect_deflect", "draw", "sword_break")]
        if not near:
            ring = sfx.blade_ring(dsp.rng("blade_ring", br), level=BLADE_RING_LEVEL)
            dsp.place(sfx_dry, ring, n_of(br))
            X["sends"].setdefault("hall", np.zeros((2, N), dtype=np.float32))
            dsp.place(X["sends"]["hall"], ring, n_of(br), 0.35)
            blade_ring_placed = True
    for preset in list(X["sends"]):
        buf = X["sends"].pop(preset)
        sfx_dry += dsp.convolve_reverb(buf, preset, seed=5)
        del buf
    timings["sfx_s"] = round(time.time() - t, 1)
    log(f"sfx: {len(X['placed'])} clips placed, {len(X['skipped'])} skipped, {len(X['ducks'])} duck points in {timings['sfx_s']} s")
    for w in X["notes"]:
        log("   sfx note:", w)

    # ---------------------------------------------------------------- ambience
    t = time.time()
    A = ambience.render(doc, keep_beds=False)
    amb = A["total"]
    del A["total"]
    sw = tl.slowmo_windows(doc)
    amb = apply_muffle(amb, sw)
    timings["ambience_s"] = round(time.time() - t, 1)
    log(f"ambience in {timings['ambience_s']} s: {A['info']}")

    # ---------------------------------------------------------------- breaths (before the bus dynamics)
    bc, breath_info = breath_curves(doc, N)
    music *= bc["music"]
    sfx_stem = sfx_dry * bc["sfx"] + X["exempt"]
    del sfx_dry, X["dry"], X["exempt"]
    amb *= bc["ambience"]
    del bc

    # ---------------------------------------------------------------- bus dynamics (tame transients at the source)
    sfx_pre = sfx_stem.astype(np.float32)
    sfx_stem, music, bus_info = bus_dynamics(sfx_stem, music)
    log(f"bus dynamics: {bus_info}")

    # ---------------------------------------------------------------- ducking + stem gains
    ducks_m, ducks_a = split_ducks(X["ducks"], doc, M["accents"])
    music = music * duck_curve(ducks_m, N, 1.0) * STEM_GAIN["music"]
    amb = amb * duck_curve(ducks_a, N, AMB_DUCK_FRACTION) * STEM_GAIN["ambience"]
    sfx_stem = sfx_stem * STEM_GAIN["sfx"]
    log(f"ducking: {len(ducks_m)}/{len(X['ducks'])} duck points act on the music (unified hits / score accents exempt); "
        f"breaths {[b['cue'] for b in breath_info]}")

    # ---------------------------------------------------------------- hard silences + end fade
    wins = tl.silence_windows(doc)
    if "all" in wins:
        for x in (music, sfx_stem, amb):
            gate(x, *wins["all"], fade_in=0.0)
    if "ambience" in wins:
        a, b = wins["ambience"]
        gate(amb, a, b, fade_in=0.35)
    t_zero = doc.duration - 0.25
    t_f0 = max((C.get("end_card", doc.duration - 3.5)) + 0.6, doc.duration - 3.0)
    for x in (music, sfx_stem, amb):
        end_fade(x, t_f0, t_zero)

    # ---------------------------------------------------------------- master (with the loudness map)
    t = time.time()
    spans = map_spans(doc, M)
    t_hits = [(c, C[c]) for c in UNIFIED_CUES if c in C]
    y, g_master, minfo = master(music + sfx_stem + amb, target_lufs, ceiling, spans=spans,
                                hits=[(c, t, HIT_TARGETS[c]) for c, t in t_hits], log=log)
    # the limiter / filters can leave tiny residues: re-assert exact digital silence
    if "all" in wins:
        y = gate(y, *wins["all"], fade_in=0.0, fade_out=0.0)
    y[:, n_of(t_zero):] = 0.0
    timings["master_s"] = round(time.time() - t, 1)

    # ---------------------------------------------------------------- write
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    assert y.shape == (2, N), y.shape
    write_wav24(out_path, y)
    del y
    os.makedirs(stems_dir, exist_ok=True)
    stems = dict(music=(music * g_master).astype(np.float32), sfx=(sfx_stem * g_master).astype(np.float32),
                 ambience=(amb * g_master).astype(np.float32))
    del music, sfx_stem, amb
    for k, v in stems.items():
        write_wav_float(os.path.join(stems_dir, f"{k}.wav"), v)
    log(f"wrote {out_path} and stems in {stems_dir}")

    # ---------------------------------------------------------------- verify (read back what was written)
    t = time.time()
    yr, sr_r, sw_r = read_wav24(out_path)
    st = an.basic_stats(yr)
    real_events = os.path.realpath(doc.path or "") == os.path.realpath(config.EVENTS_JSON)
    is_final = is_final_output(out_path)
    rep = dict(
        output=os.path.abspath(out_path), events_source=os.path.abspath(doc.path) if doc.path else None,
        events_draft=doc.draft, report=os.path.abspath(report_path), stems_dir=os.path.abspath(stems_dir),
        sample_rate=sr_r, bit_depth=8 * sw_r, channels=int(yr.shape[0]),
        length_samples=int(yr.shape[1]), length_s=yr.shape[1] / sr_r,
        expected_length_s=(doc.frame_end - doc.frame_start + 1) / doc.fps,
        integrated_lufs=round(an.loudness_integrated(yr), 2), true_peak_dbtp=round(an.true_peak_dbtp(yr), 2),
        lra_lu=round(an.lra(yr), 2), **{k: (round(v, 3) if isinstance(v, float) else v) for k, v in st.items()},
        first_sample_zero=bool(np.all(yr[:, 0] == 0)), last_frame_digital_silence=bool(np.all(yr[:, -n_of(1.0 / doc.fps):] == 0)),
        acts=per_act_stats(yr, doc),
        stems={k: dict(lufs=round(an.loudness_integrated(v), 2), peak_dbfs=round(float(dsp.lin2db(np.max(np.abs(v)))), 2))
               for k, v in stems.items()},
        master=minfo, stem_gains=STEM_GAIN,
        cues={k: dict(frame=v["frame"], t=round(v["t"], 4), source=v["source"]) for k, v in doc.cues.items()},
        tempo_sections=tl.tempo_sections(doc), music_sections=M["sections"], music_note_counts=M["counts"],
        music_hit_points=M["hits"], music_marks=M["marks"], music_event_marks=M["event_marks"],
        events_total=len(doc.events), events_by_type=doc.summary(), unknown_types=doc.unknown, aliased_types=doc.aliased,
        sfx_placed=len(X["placed"]), sfx_skipped=X["skipped"], sfx_notes=X["notes"], blade_ring_from_cue=blade_ring_placed,
        duck_points=len(X["ducks"]), duck_points_on_music=len(ducks_m),
        slowmo_windows=[(round(a, 3), round(b, 3), "event" if e is not None else "config") for a, b, e in sw],
        silence_windows={k: (round(a, 3), round(b, 3)) for k, (a, b) in wins.items()},
        ambience=A["info"], warnings=doc.warnings,
    )
    sil = {}
    for k, (a, b) in wins.items():
        seg = yr[:, n_of(a):n_of(b)] if k != "ambience" else stems["ambience"][:, n_of(a):n_of(b)]
        sil[k] = dict(max_abs=float(np.max(np.abs(seg))) if seg.size else 0.0)
    m_sil = stems["music"][:, n_of(wins["music"][0]):n_of(wins["music"][1])] if "music" in wins else np.zeros((2, 1))
    sil["music_stem_in_music_window"] = float(np.max(np.abs(m_sil)))
    rep["silence_check"] = sil
    silent = [(t_f0 + 0.5 * (t_zero - t_f0), doc.duration + 1.0)] + ([wins["all"]] if "all" in wins else []) + \
        ([bw] if bw else [])
    rep["onset_check"] = onset_check(stems["sfx"], X["placed"], doc, pre_stem=sfx_pre, silent=silent)
    del sfx_pre
    rep["music_sync"] = music_sync(M, doc.fps)
    rep["story_hits"] = story_hits(yr, doc, t_hits)
    rep["loudness_map"] = loudness_map_report(yr, spans)
    extra = [("prologue", 0.0, C["act1_start"], False), ("epilogue", C["epilogue"], C.get("end_card", doc.duration - 3.0), False)]
    rep["spectral_balance"] = spectral_balance(yr, spans, extra)
    rep["sections"] = section_stats(yr, M["sections"], stems)
    rep["breaths"] = breath_info
    rep["mono_compat"] = mono_compat(yr)
    rep["loudness_crosscheck"] = crosscheck_loudness(yr, out_path)
    ff = rep["loudness_crosscheck"].get("ffmpeg_ebur128") or {}
    sh = rep["story_hits"]
    fp_hit = next((h for h in sh["hits"] if h["cue"] == "final_pass"), None)
    checks = dict(
        length_exact=rep["length_samples"] == N, finite=bool(st.get("finite", True)), no_clipping=rep["clip_count"] == 0,
        lufs_within_1=abs(rep["integrated_lufs"] - target_lufs) <= config.AUDIO_LOUDNESS_TOL_LU,
        true_peak_ok=rep["true_peak_dbtp"] <= ceiling and (ff.get("true_peak_dbtp") is None or ff["true_peak_dbtp"] <= ceiling),
        dc_ok=bool(np.all(np.abs(np.asarray(st.get("dc_offset", [0.0]))) < 1e-3)),
        music_silent_in_silence=rep["silence_check"]["music_stem_in_music_window"] == 0.0,
        white_silence_digital_zero=rep["silence_check"].get("all", {}).get("max_abs", 0.0) == 0.0,
        onsets_within_10ms=rep["onset_check"]["gate_pass"],
        last_frame_silent=rep["last_frame_digital_silence"],
        music_sync_1_frame=rep["music_sync"]["pass_"],
        story_hit_contrast=all(h["contrast_3s"] >= HIT_CONTRAST_LU for h in sh["hits"]),
        final_pass_loudest=bool(fp_hit is not None and fp_hit["hit_max_momentary"] >= sh["film_max"]["lufs"] - 0.05),
        loudness_map=all(r["ok"] for r in rep["loudness_map"]),
        spectral_balance=all(r["ok"] for r in rep["spectral_balance"]),
    )
    checks["qc_pass"] = all(checks.values())
    checks["events_real"] = bool(not doc.draft and (real_events or not is_final))
    checks["all_pass"] = checks["qc_pass"] and checks["events_real"]
    rep["checks"] = checks
    timings["verify_s"] = round(time.time() - t, 1)

    # ---------------------------------------------------------------- spectrograms
    if spectrograms:
        t = time.time()
        os.makedirs(spec_dir, exist_ok=True)
        name = os.path.splitext(os.path.basename(out_path))[0]
        spans_act = [(a["t0"], a["t1"], a["id"]) for a in doc.acts]
        marks = [(v["t"], k) for k, v in doc.cues.items()]
        files = [an.plot_spectrogram(yr, os.path.join(spec_dir, f"{name}_full.png"), title=f"{name}: full film",
                                     spans=spans_act, markers=marks)]
        zooms = [("first_clash", C.get("act1_start", 18) - 1, C.get("act1_bar1", 26.25) + 4),
                 ("perfect_deflect_hat_cut", C.get("perfect_deflect", 57) - 5, C.get("hat_cut", 59) + 4),
                 ("thunder_rain_raikiri", C.get("thunder_first", 98) - 2, C.get("raikiri", 104) + 5),
                 ("silence_final_pass", C.get("low_point", 123) - 2, C.get("final_pass", 137.5) + 6),
                 ("epilogue_end", C.get("epilogue", 146) - 1, doc.duration)]
        for zn, a, b in zooms:
            files.append(an.plot_spectrogram(yr, os.path.join(spec_dir, f"{name}_{zn}.png"), t0=max(0, a),
                                             t1=min(doc.duration, b), title=f"{name}: {zn}", spans=spans_act, markers=marks))
        stem_file = os.path.join(spec_dir, f"{name}_stems.png")
        _plot_stems(stems, stem_file, doc)
        files.append(stem_file)
        lm_file = os.path.join(spec_dir, f"{name}_loudness_map.png")
        _plot_loudness_map(yr, lm_file, doc, spans, t_hits)
        files.append(lm_file)
        rep["spectrograms"] = [os.path.abspath(f) for f in files]
        timings["spectrograms_s"] = round(time.time() - t, 1)
    timings["total_s"] = round(time.time() - T0, 1)
    rep["timings"] = timings
    os.makedirs(os.path.dirname(os.path.abspath(report_path)), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1, default=float)
    log(f"report -> {report_path}")
    log(f"LUFS {rep['integrated_lufs']}  TP {rep['true_peak_dbtp']} dBTP (ffmpeg {ff.get('true_peak_dbtp')})  "
        f"length {rep['length_s']:.4f} s  clips {rep['clip_count']}  onsets {rep['onset_check']['within_10ms']}/"
        f"{rep['onset_check']['checked']} within 10 ms  total {timings['total_s']} s")
    bad = [k for k, v in checks.items() if not v and k not in ("qc_pass", "all_pass")]
    log("checks: ALL PASS" if not bad else f"checks FAILED: {bad}")
    return rep


def _plot_stems(stems, path, doc):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 1, figsize=(18, 4))
    for (k, v), c in zip(stems.items(), ("tab:purple", "tab:red", "tab:green")):
        t, l = an.loudness_curve(v, 3.0, 0.1)
        ax.plot(t, l, label=k, color=c, lw=1.1)
    for a in doc.acts:
        ax.axvline(a["t0"], color="k", lw=0.6, alpha=0.5)
        ax.text(a["t0"] + 0.3, -8, a["id"], fontsize=8)
    ax.set_ylim(-60, 0)
    ax.set_xlim(0, doc.duration)
    ax.set_ylabel("short-term LUFS")
    ax.grid(alpha=0.3)
    ax.legend(loc="lower left")
    fig.tight_layout()
    fig.savefig(path, dpi=80)
    plt.close(fig)


def _plot_loudness_map(y, path, doc, spans, t_hits):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 1, figsize=(18, 4.5))
    tm, mo = an.momentary_curve(y, 0.05)
    ts, st = an.loudness_curve(y, 3.0, 0.1)
    ax.plot(tm, mo, color="tab:blue", lw=0.5, alpha=0.7, label="momentary (0.4 s)")
    ax.plot(ts, st, color="tab:orange", lw=1.4, label="short-term (3 s)")
    for sp in spans:
        ax.hlines(sp["target"], sp["t0"], sp["t1"], color="tab:green" if sp["kind"] == "ride" else "tab:red", lw=2.5)
        ax.text(sp["t0"], sp["target"] + 0.8, sp["name"], fontsize=7, color="tab:green")
    for name, t in t_hits:
        ax.axvline(t, color="k", lw=0.6, ls="--", alpha=0.5)
        ax.text(t + 0.2, -3.5, name, fontsize=7, rotation=90, va="top")
    ax.axhline(ROUTINE_MAX, color="gray", ls=":", lw=1)
    ax.set_ylim(-45, -2)
    ax.set_xlim(0, doc.duration)
    ax.set_ylabel("LUFS")
    ax.set_xlabel("time (s)")
    ax.grid(alpha=0.3)
    ax.legend(loc="lower left", fontsize=8)
    ax.set_title("loudness map: targets (green: section median short-term; red: suspension max), story hits (dashed)")
    fig.tight_layout()
    fig.savefig(path, dpi=80)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description="render + master the 芒原决战 soundtrack")
    ap.add_argument("--events", default=None, help="events.json (default out/events.json, fallback out/audio/draft_events.json)")
    ap.add_argument("--out", default=config.FINAL_MIX_WAV)
    ap.add_argument("--report", default=None, help=f"default: {config.MIX_REPORT_JSON} for {config.FINAL_MIX_WAV}, "
                                                    "else <out>_report.json")
    ap.add_argument("--stems-dir", default=None, help="default <out dir>/stems/<out name>")
    ap.add_argument("--spec-dir", default=None, help="default <out dir>/spectrograms")
    ap.add_argument("--target-lufs", type=float, default=config.AUDIO_TARGET_LUFS)
    ap.add_argument("--ceiling", type=float, default=config.AUDIO_TRUE_PEAK_DB, help="true-peak ceiling dBTP")
    ap.add_argument("--no-spectrograms", action="store_true")
    ap.add_argument("--strict", action="store_true", help="exit code 2 if any report check fails (outputs are still "
                                                          "written); draft events always fail checks.events_real")
    a = ap.parse_args()
    ev = a.events
    if ev is None:
        ev = config.EVENTS_JSON if os.path.exists(config.EVENTS_JSON) else config.DRAFT_EVENTS_JSON
    rep = render(ev, a.out, a.report, a.stems_dir, a.spec_dir, a.target_lufs, a.ceiling, not a.no_spectrograms)
    if a.strict and not rep["checks"]["all_pass"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
