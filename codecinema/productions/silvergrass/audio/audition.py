"""
audition.py -- render every instrument, every SFX type and every score section in isolation, with sanity
measurements (we cannot listen, so we measure) and spectrogram contact sheets.

out/audio/audition/
    instruments/<name>.wav     a short phrase per instrument / articulation (with the score's reverb send)
    sfx/<type>.wav             3 variations per SFX type (different seed / strength / parameters), 2-3 s apart;
                               whooshes per weapon kind (whoosh_katana, whoosh_spear, ...), thunder per distance
    ambience/<bed>.wav         8-10 s excerpts of each ambience bed (wind calm / gusting, grass, fire, rain, ...)
    score/<nn>_<section>.wav   every score section cut from the full score render (with its reverb tail)
    stats.json                 per-note / per-variation measurements: spectral centroid, T60, f0 error (cents),
                               attack time, crest factor, max momentary loudness, NaN / clip checks
    sheets/<group>.png         log-frequency spectrogram contact sheets (view with any image viewer)

usage:
    .venv/bin/python codecinema/productions/silvergrass/audio/audition.py                      # everything (draft events for the score cut)
    .venv/bin/python codecinema/productions/silvergrass/audio/audition.py --only instruments,sfx
    .venv/bin/python codecinema/productions/silvergrass/audio/audition.py --events out/events.json
"""

import argparse
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(HERE, "..", "common"), HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import config  # noqa: E402
import dsp  # noqa: E402
import analysis as an  # noqa: E402
import instruments as I  # noqa: E402
import timeline as tl  # noqa: E402
import score  # noqa: E402
import sfx  # noqa: E402
from dsp import SR, n_of  # noqa: E402

OUT = os.path.join(config.AUDIO_DIR, "audition")
TARGET_LUFS = -18.0          # audition files are loudness-matched (peaks kept <= config.AUDIO_TRUE_PEAK_DB)


# ============================================================================================ io / helpers
def _write(path, x, target_lufs=TARGET_LUFS, ceiling_db=config.AUDIO_TRUE_PEAK_DB):
    """loudness-match to target, never exceed the true-peak ceiling (plain gain, no limiter), 24-bit"""
    import mix
    x = dsp.as_stereo(x)
    L = an.loudness_integrated(x)
    g = 0.0 if not np.isfinite(L) else target_lufs - L
    tp = an.true_peak_dbtp(x) + g
    if tp > ceiling_db:
        g -= tp - ceiling_db
    y = x * dsp.db2lin(g)
    y = dsp.fade(y, 0.0, 0.01)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mix.write_wav24(path, y)
    return float(g)


def _concat(clips, gap=0.5, lead=0.25):
    """stereo clips -> one stereo buffer, each clip starting `gap` s after the previous one ended"""
    parts, starts = [], []
    t = lead
    for c in clips:
        c = dsp.as_stereo(c)
        starts.append(t)
        parts.append((n_of(t), c))
        t += c.shape[-1] / SR + gap
    n = n_of(t) + n_of(0.2)
    out = np.zeros((2, n))
    for s, c in parts:
        dsp.place(out, c, s)
    return out, starts


def _r1(v):
    return None if v is None else round(v, 1)


def _stats(x, f0=None, tail_from=None):
    """measurements on a single note / clip"""
    xs = dsp.as_stereo(x)
    xm = xs.mean(axis=0)
    a = np.abs(xm)
    pk = float(a.max()) if a.size else 0.0
    d = dict(finite=bool(np.all(np.isfinite(xs))),
             dur_s=round(xs.shape[-1] / SR, 3),
             peak_dbfs=round(float(dsp.lin2db(np.abs(xs).max())), 2),
             crest_db=round(float(dsp.lin2db(pk) - dsp.lin2db(np.sqrt(np.mean(xm * xm)) + 1e-12)), 1),
             centroid_hz=round(an.spectral_centroid(xs), 0),
             centroid_mag_hz=round(an.spectral_centroid(xs, weight="mag"), 0),
             sub40_db=_r1(an.band_share(xs, 0, 40)), hf4k_db=_r1(an.band_share(xs, 4000, 24000)),
             dc=round(float(np.mean(xm)), 6))
    if pk > 0:
        ip = int(np.argmax(a > 0.5 * pk))
        d["attack_ms"] = round(ip / SR * 1000, 1)
    t60 = an.decay_t60(xs)
    d["t60_s"] = round(t60, 2) if t60 else None
    if f0:
        est = an.f0_estimate(xs, fmin=max(20.0, f0 * 0.6), fmax=f0 * 1.6, t0=min(0.12, xs.shape[-1] / SR * 0.2),
                             dur=min(0.6, xs.shape[-1] / SR * 0.6))
        if est:
            d["f0_target"] = round(float(f0), 2)
            d["f0_est"] = round(est, 2)
            d["f0_err_cents"] = round(1200 * np.log2(est / f0), 1)
    xp = dsp.pad_to(xs, max(xs.shape[-1], n_of(0.6)))
    _, mo = an.loudness_curve(xp, 0.4, 0.02)
    if mo.size:
        d["max_momentary_lufs"] = round(float(np.max(mo)), 1)
    # stereo correlation (width sanity): +1 mono .. 0 wide .. <0 phasey
    if xs.shape[0] == 2 and np.std(xs[0]) > 0 and np.std(xs[1]) > 0:
        d["lr_corr"] = round(float(np.corrcoef(xs[0], xs[1])[0, 1]), 2)
    return d


def _verb(x, preset, send):
    x = dsp.as_stereo(x)
    n = x.shape[-1] + dsp.reverb_tail_len(preset)
    dry = dsp.pad_to(x, n)
    return dry + send * dsp.convolve_reverb(dry, preset, seed=3)


# ============================================================================================ instruments
def _hz(m):
    return float(dsp.midi2hz(m))


def instrument_phrases():
    """-> list of (name, stereo audio, [per-note stats], meta)"""
    out = []

    def seq(fn_list, track, name, meta=""):
        """fn_list: [(t, callable(r)->(audio, f0 or None))] -> rendered phrase + per-note stats"""
        notes, st = [], []
        for i, (t, fn) in enumerate(fn_list):
            r = dsp.rng("aud", name, i)
            a, f0 = fn(r)
            st.append(_stats(a, f0))
            notes.append((t, a))
        n = max(n_of(t) + a.shape[-1] for t, a in notes) + n_of(0.3)
        buf = np.zeros((2, n))
        tr = score.TRACKS.get(track, dict(pan=0.0, width=1.0, send={}, gain=1.0))
        for t, a in notes:
            s = dsp.pan_mono(a, tr["pan"]) if a.ndim == 1 else dsp.pan_stereo(a, tr["pan"], tr["width"])
            dsp.place(buf, s, n_of(t))
        for k, lv in tr["send"].items():
            buf = _verb(buf, k, lv)
        out.append((name, buf, st, meta))

    # ---- drums (120 BPM patterns, velocity layers)
    b = 0.5
    pat = [(0, 1.0), (0.75, 0.55), (1.5, 0.72), (2, 0.95), (2.75, 0.5), (3.25, 0.62), (3.5, 0.8), (4, 1.1),
           (5.5, 0.35), (5.75, 0.45), (6, 0.9)]
    seq([(tb * b, (lambda v: (lambda r: (I.odaiko(v, r, size=0.9, tone=0.55, f0=score.D2), score.D2)))(v)) for tb, v in pat],
        "odaiko", "odaiko", "tuned D2 (73.4 Hz), size 0.9 tone 0.55, velocities 0.35-1.1")
    seq([(tb * b * 2, (lambda v: (lambda r: (I.odaiko(v, r, size=1.2, tone=0.35, f0=score.G1), score.G1)))(v)) for tb, v in
         [(0, 1.0), (1, 0.6), (2, 0.85), (3, 1.15)]], "odaiko_lo", "odaiko_lo", "tuned G1 (49 Hz), size 1.2 tone 0.35")
    seq([(0.0, lambda r: (I.odaiko(1.08, r, size=1.55, tone=0.45, f0=score.D1), score.D1)),
         (4.0, lambda r: (I.odaiko(1.13, r, size=1.5, tone=0.42, f0=score.G1), score.G1))], "odaiko_lo", "odaiko_story",
        "story hits: D1 (36.7 Hz, first clash / hat cut / low point / final pass), G1 (Raikiri)")
    seq([(i * 1.8, (lambda f: (lambda r: (score._sub(0.9, r, 1.6, f), f)))(f)) for i, f in
         enumerate((score.D1, score.G1, score.A1, score.BB1))], "sub", "sub", "pitched subs gliding ONTO D1 / G1 / A1 / Bb1")
    shp = [(i * 0.125, 0.3 + 0.7 * ((i % 4) == 0) + 0.2 * ((i % 2) == 0)) for i in range(24)]
    seq([(t, (lambda v, i: (lambda r: (I.shime(min(v, 1.0), r, rim=(i % 8 == 6)), None)))(v, i)) for i, (t, v) in
         enumerate(shp)], "shime", "shime", "16ths with accents + rim 'ka' on every 8th step 6")
    seq([(t, (lambda v: (lambda r: (I.hyoshigi(v, r), None)))(v)) for t, v in
         [(0, 0.8), (1.2, 0.85), (2.1, 0.9), (2.7, 0.9), (3.1, 0.95), (3.35, 1.0)]], "hyoshigi", "hyoshigi",
        "accelerating claps")
    # ---- shakuhachi: the tenko motif with the prologue articulations (rubato)
    arts = [dict(attack="meri", bend=-120, bend_time=0.2, vib_delay=0.6, swell=0.4), dict(attack="plain", vib_depth=10),
            dict(attack="meri", bend=-60, yuri=0.6), dict(attack="plain", atari=200, vib_depth=6),
            dict(attack="kari", vib_depth=22, swell=0.3), dict(attack="plain", fall=160, vib_depth=18, swell=0.6, release=0.35)]
    fl, t = [], 0.1
    for (b0, nb, m), art in zip(score.motif("tenko"), arts):
        d = nb * 0.8
        fl.append((t, (lambda m, d, art: (lambda r: (I.shakuhachi(_hz(m), d, 0.34, r, **art), _hz(m))))(m, d, art)))
        t += d + 0.12
    seq(fl, "shakuhachi", "shakuhachi_tenko", "tenko motif, meri/kari/atari/yuri/fall articulations")
    fl = []
    for i, (m, art) in enumerate([(74, dict(muraiki=1.0, attack="meri", bend=-200, fall=250)),
                                  (75, dict(flutter=0.6, attack="kari")), (69, dict(muraiki=0.5, glide_to=(0.3, _hz(70))))]):
        fl.append((i * 1.4, (lambda m, art: (lambda r: (I.shakuhachi(_hz(m), 1.0, 0.7, r, **art), _hz(m))))(m, art)))
    seq(fl, "shakuhachi", "shakuhachi_fx", "muraiki blast, flutter, glide")
    # ---- koto: saku motif (8ths @ 92) + a press-bend + low arpeggio
    fl, bt = [], 60 / 92
    for i, (b0, nb, m) in enumerate(score.motif("saku") + [(t0 + 4.0, nb, m) for (t0, nb, m) in score.motif("saku", inv=True)]):
        fl.append((b0 * bt, (lambda m, v: (lambda r: (I.koto(_hz(m), 1.4, v, r), _hz(m))))(m, 0.42 if i % 7 else 0.55)))
    fl.append((6.0, lambda r: (I.koto(_hz(69), 3.0, 0.6, r, press=[(0.45, 100, 0.12), (1.2, 0, 0.25)]), _hz(69))))
    for j, m in enumerate((50, 57, 62, 63, 69)):
        fl.append((8.5 + 0.18 * j, (lambda m: (lambda r: (I.koto(_hz(m), 3.0, 0.45, r), _hz(m))))(m)))
    seq(fl, "koto", "koto", "saku motif + inversion, oshide press-bend, arpeggio")
    # ---- shamisen: tsugaru-style riff on the diminished tenko
    fl, bt = [], 0.5
    mot = score.motif("tenko", octave=-1, aug=0.5)
    for (b0, nb, m) in mot:
        if nb >= 1.0:
            for j in range(int(nb * 4)):
                fl.append(((b0 + j / 4) * bt, (lambda m, v: (lambda r: (I.shamisen(_hz(m), 0.3, v, r), _hz(m))))(m, 0.62 if j == 0 else 0.4)))
        else:
            fl.append((b0 * bt, (lambda m: (lambda r: (I.shamisen(_hz(m), 0.35, 0.56, r), _hz(m))))(m)))
    fl.append((3.2, lambda r: (I.shamisen(_hz(50), 1.6, 0.8, r, slide=(0.4, 200, 0.15)), _hz(50))))
    fl.append((5.0, lambda r: (I.shamisen(_hz(57), 1.2, 0.5, r, hajiki=True), _hz(57))))
    seq(fl, "shamisen", "shamisen", "riff (repeated 16ths), suri slide, hajiki")
    # ---- strings: five modes
    fl = [(0.0, lambda r: (I.strings([_hz(38), _hz(45)], 3.0, 0.5, r, mode="sustain"), None)),
          (4.2, lambda r: (I.strings([_hz(38), _hz(45), _hz(50)], 3.0, 0.5, r, mode="swell", release=1.0), None)),
          (8.6, lambda r: (I.strings([_hz(38), _hz(45), _hz(50)], 2.2, 0.7, r, mode="sfz", swell_to=0.6), None)),
          (12.0, lambda r: (I.strings([_hz(50), _hz(51)], 2.4, 0.55, r, mode="tremolo"), None)),
          (18.0, lambda r: (I.strings([_hz(75), _hz(81)], 2.4, 0.45, r, mode="tremolo", tone="ponticello"), None))]
    for j in range(8):
        fl.append((15.2 + 0.25 * j, (lambda j: (lambda r: (I.strings([_hz(50), _hz(57)], 0.11, 0.42 * (1.0 if j % 3 == 0 else 0.6), r, mode="spiccato"), None)))(j)))
    seq(fl, "strings", "strings", "sustain / swell / sfz / tremolo (D-Eb) / spiccato / sul ponticello tremolo (Eb5-A5)")
    fl = [(0.0, lambda r: (I.strings([_hz(62)], 2.5, 0.5, r, mode="sustain"), _hz(62))),
          (3.2, lambda r: (I.strings([_hz(50)], 2.5, 0.5, r, mode="sustain"), _hz(50))),
          (6.4, lambda r: (I.strings([_hz(38)], 2.5, 0.5, r, mode="sustain"), _hz(38)))]
    seq(fl, "strings", "strings_pitch", "single notes D4 / D3 / D2 (pitch check)")
    # ---- choir
    fl = [(0.0, lambda r: (I.choir([_hz(50), _hz(57), _hz(62)], 3.0, 0.5, r, vowel="a"), None)),
          (4.5, lambda r: (I.choir([_hz(50), _hz(57), _hz(62), _hz(63)], 3.0, 0.55, r, vowel="a", attack=0.1), None)),
          (9.0, lambda r: (I.choir([_hz(50), _hz(57)], 3.0, 0.45, r, vowel="o", swell=1.0), None)),
          (13.5, lambda r: (I.choir([_hz(51), _hz(55), _hz(58), _hz(63)], 4.0, 0.55, r, vowel="a", vowel_to="o", attack=0.1), None))]
    seq(fl, "choir", "choir", "'a' triad, 'a' cluster with Eb, 'o' swell, Raikiri chord Eb/Bb with the a->o morph")
    # ---- bell / heartbeat / swell
    seq([(0.0, lambda r: (I.temple_bell(_hz(50), 0.8, r, dur=12.0), None))], "bell", "temple_bell", "D3 strike tone")
    seq([(i * 60 / 62, (lambda i: (lambda r: (I.heartbeat(0.75 + 0.03 * i, r), None)))(i)) for i in range(6)], "heart",
        "heartbeat", "62 BPM")
    seq([(0.0, lambda r: (I.metal_swell(2.5, 0.6, r)[0], None)),
         (2.5, lambda r: (I.odaiko(1.0, r, size=1.25, tone=0.35), None))], "swell", "metal_swell", "swell into a hit")
    return out


# ============================================================================================ sfx
def _mk(raw, doc):
    e = tl._norm_event(dict(raw), raw.get("idx", 0), doc)
    return e


SFX_VARIANTS = {
    # type or audition-name: list of 3 raw event dicts (frame / seed differ -> different randomness)
    "whoosh_katana": [dict(type="whoosh", weapon="katana", strength=s) for s in (0.55, 0.8, 1.0)],
    "whoosh_spear": [dict(type="whoosh", weapon="spear", strength=s) for s in (0.6, 0.85, 1.0)],
    "whoosh_kunai": [dict(type="whoosh", weapon="kunai", strength=s) for s in (0.6, 0.8, 1.0)],
    "whoosh_body": [dict(type="whoosh", weapon="body", strength=s) for s in (0.35, 0.6, 0.8)],
    "clash": [dict(type="clash", strength=s) for s in (0.5, 0.7, 0.9)],
    "clash_heavy": [dict(type="clash_heavy", strength=s) for s in (0.8, 1.0, 1.2)],
    "perfect_deflect": [dict(type="perfect_deflect", strength=1.0) for _ in range(3)],
    "blade_lock": [dict(type="blade_lock", duration=d) for d in (24, 44, 60)],
    "hit": [dict(type="hit", strength=0.3), dict(type="hit", strength=0.7), dict(type="hit", strength=0.4, tags=["plant_blade"])],
    "kick": [dict(type="kick", strength=s) for s in (0.6, 0.8, 1.0)],
    "step": [dict(type="step", who="shinobi", strength=0.5), dict(type="step", who="saint", strength=0.8),
             dict(type="step", who="shinobi", strength=0.3, surface="grass_crawl")],
    "step_wet": [dict(type="step", who="shinobi", strength=0.6, _wet=1.0), dict(type="step", who="saint", strength=0.9, _wet=1.0),
                 dict(type="step", who="shinobi", strength=0.4, _wet=1.0)],
    "dash": [dict(type="dash", who=w, strength=s) for w, s in (("shinobi", 0.7), ("saint", 1.0), ("shinobi", 1.0))],
    "jump": [dict(type="jump", who=w) for w in ("shinobi", "saint", "shinobi")],
    "land": [dict(type="land", strength=0.3), dict(type="land", strength=0.7), dict(type="land", strength=1.0)],
    "roll": [dict(type="roll"), dict(type="roll"), dict(type="roll", _wet=1.0)],
    "skid": [dict(type="skid", duration=12), dict(type="skid", duration=24), dict(type="skid", duration=32, tags=["blade"])],
    "kneel": [dict(type="kneel"), dict(type="kneel"), dict(type="kneel", _wet=1.0)],
    "body_fall": [dict(type="body_fall") for _ in range(2)] + [dict(type="body_fall", _wet=1.0)],
    "draw": [dict(type="draw", who="shinobi"), dict(type="draw", who="saint"), dict(type="draw", who="shinobi")],
    "sheathe": [dict(type="sheathe", who="shinobi"), dict(type="sheathe", who="saint"), dict(type="sheathe", who="shinobi", _slow=True)],
    "tsuba_click": [dict(type="tsuba_click") for _ in range(3)],
    "spear_pull": [dict(type="spear_pull") for _ in range(3)],
    "spear_spin": [dict(type="spear_spin", duration=d) for d in (20, 28, 40)],
    "spear_draw": [dict(type="spear_draw") for _ in range(3)],
    "sheath_drop": [dict(type="sheath_drop") for _ in range(3)],
    "haori_shed": [dict(type="haori_shed") for _ in range(3)],
    "kunai_throw": [dict(type="kunai_throw") for _ in range(3)],
    "kunai_deflect": [dict(type="kunai_deflect", strength=s) for s in (0.6, 0.7, 0.9)],
    "hat_cut": [dict(type="hat_cut") for _ in range(3)],
    "sword_break": [dict(type="sword_break") for _ in range(3)],
    "cord_cut": [dict(type="cord_cut") for _ in range(3)],
    "grass_shear": [dict(type="grass_shear") for _ in range(3)],
    "fire_ignite": [dict(type="fire_ignite") for _ in range(3)],
    "fire_burst": [dict(type="fire_burst", strength=s) for s in (0.5, 0.8, 1.0)],
    "thunder_far": [dict(type="thunder", distance="far") for _ in range(3)],
    "thunder_mid": [dict(type="thunder", distance="mid") for _ in range(3)],
    "thunder_near": [dict(type="thunder", distance="near") for _ in range(3)],
    "lightning_strike": [dict(type="lightning_strike") for _ in range(3)],
    "raikiri": [dict(type="raikiri") for _ in range(3)],
    "tree_split": [dict(type="tree_split") for _ in range(3)],
    "electric_crackle": [dict(type="electric_crackle", duration=d) for d in (12, 20, 36)],
    "rain_split": [dict(type="rain_split") for _ in range(3)],
    "steam_hiss": [dict(type="steam_hiss", strength=s) for s in (0.3, 0.6, 1.0)],
    "shockwave": [dict(type="shockwave", strength=0.5), dict(type="shockwave", strength=0.9),
                  dict(type="shockwave", strength=0.8, tags=["water"])],
    "bell": [dict(type="bell") for _ in range(3)],
    "heartbeat": [dict(type="heartbeat", bpm=b, duration=d) for b, d in ((58, 72), (62, 86), (80, 72))],
    "stinger": [dict(type="stinger", strength=s) for s in (0.4, 0.8, 1.0)],
    "slowmo": [dict(type="slowmo", duration=d) for d in (24, 35, 41)],
    "drip": [dict(type="drip") for _ in range(3)],
}
# every SFX type must be auditioned
_COVER = {v[0]["type"] for v in SFX_VARIANTS.values()}
assert set(sfx.SFX) <= _COVER, set(sfx.SFX) - _COVER


def sfx_variations(doc):
    out = []
    for name, raws in SFX_VARIANTS.items():
        clips, st = [], []
        for i, raw in enumerate(raws):
            raw = dict(raw)
            wet = raw.pop("_wet", 0.0)
            slow = raw.pop("_slow", False)
            raw.setdefault("frame", 1000 + 97 * i + 13 * len(name))
            raw["idx"] = i
            raw.setdefault("pan", [-0.35, 0.0, 0.35][i])
            raw.setdefault("dist", [4.0, 6.0, 12.0][i] if name not in ("bell",) else 40.0)
            e = _mk(raw, doc)
            ctx = dict(doc=doc, wet=wet, fire=0.0, slow=1.0, in_slowmo=slow, bloom=False)
            clip = sfx.render_event(e, ctx)
            stx, send = sfx.spatialize(clip, e)
            a = clip.anchor
            wet_sig = send * dsp.convolve_reverb(dsp.pad_to(stx, stx.shape[-1] + n_of(1.2)), clip.reverb, seed=5)
            full = dsp.pad_to(stx, wet_sig.shape[-1]) + wet_sig
            s = _stats(stx)
            s.update(anchor_ms=round(a / SR * 1000, 1), reverb=clip.reverb, send=round(send, 3),
                     duck=clip.duck, strength=e["strength"], params={k: v for k, v in raw.items() if k not in ("frame", "idx")})
            # onset sharpness at the anchor (impulsive types): rise of HF energy within +-5 ms of the anchor
            if e["type"] in sfx.IMPULSIVE:
                t_on, rise = an.guided_onset(dsp.pad_to(np.pad(stx, ((0, 0), (n_of(0.2), 0))), stx.shape[-1] + n_of(0.4)),
                                             0.2 + a / SR, search=0.03)
                s["onset_err_ms"] = None if t_on is None else round((t_on - (0.2 + a / SR)) * 1000, 2)
            st.append(s)
            clips.append(full)
        buf, starts = _concat(clips, gap=0.6)
        out.append((name, buf, st, f"{raws[0]['type']} x{len(raws)}"))
    return out


def sfx_calibration(doc, dist=6.0):
    """level hierarchy check: the middle variation of every SFX entry, dry, centred, at `dist` m ->
    max momentary loudness (400 ms), sample peak, crest factor, energy centroid"""
    rows = {}
    for name, raws in SFX_VARIANTS.items():
        raw = dict(raws[len(raws) // 2])
        wet = raw.pop("_wet", 0.0)
        slow = raw.pop("_slow", False)
        raw.update(frame=2000, idx=0, pan=0.0, dist=dist)
        e = _mk(raw, doc)
        clip = sfx.render_event(e, dict(doc=doc, wet=wet, fire=0.0, slow=1.0, in_slowmo=slow, bloom=False))
        stx, _ = sfx.spatialize(clip, e)
        xp = dsp.pad_to(stx, max(stx.shape[-1], n_of(0.6)))
        _, mo = an.loudness_curve(xp, 0.4, 0.01)
        pk = float(np.max(np.abs(stx)))
        rows[name] = dict(max_momentary_lufs=round(float(np.max(mo)), 1), peak_dbfs=round(float(dsp.lin2db(pk)), 1),
                          plr_db=round(float(dsp.lin2db(pk)) - float(np.max(mo)), 1),
                          centroid_hz=round(an.spectral_centroid(stx), 0))
    return rows


# ============================================================================================ ambience beds
def ambience_excerpts(doc):
    import ambience
    A = ambience.render(doc, keep_beds=True)
    beds = A["beds"]
    C = {k: v["t"] for k, v in doc.cues.items()}
    fire_on, _ = tl.fire_window(doc)
    rain_on, rain_off = tl.rain_window(doc)
    ex = [("wind_prologue", "wind", 3.0, 12.0), ("wind_act3_storm", "wind", 110.0, 10.0),
          ("grass_prologue", "grass", 4.0, 10.0),
          ("fire_ring", "fire", (fire_on or 68.0) + 0.0, 10.0), ("fire_drowned_steam", "fire", (rain_on or 100) - 1.0, 10.0),
          ("rain_onset", "rain", (rain_on or 100) - 2.0, 10.0), ("rain_act3", "rain", 128.5, 8.5),
          ("insects_epilogue", "insects", C.get("epilogue", 146) + 3.0, 10.0),
          ("rain_standoff_s24", "rain", C.get("silence", 128.0) + 1.0, 7.0)]
    th = [t for t in A["info"].get("thunder_rolls", [])]
    if th:
        ex.append(("thunder_roll", "thunder", th[0] - 0.5, 9.0))
    out = []
    for name, bed, t0, d in ex:
        x = beds[bed][:, n_of(t0):n_of(t0 + d)]
        x = dsp.fade(x, 0.3, 0.5)
        out.append((name, x, [_stats(x)], f"{bed} bed {t0:.1f}-{t0 + d:.1f} s"))
    total = A["total"]
    return out, total


# ============================================================================================ score sections
def score_sections(doc):
    M = score.render(doc)
    stem = M["stem"]
    out = []
    for i, s in enumerate(M["sections"]):
        if s["name"] == "silence":
            continue
        a, b = s["t0"], min(doc.duration, s["t1"] + (2.5 if s["name"] != "epilogue" else 0.0))
        x = stem[:, n_of(a):n_of(b)]
        x = dsp.fade(x, 0.01, 0.6)
        meta = f"{s['t0']:.2f}-{s['t1']:.2f} s" + (f", {s['bpm']} BPM x {s['bars']} bars" if s["bpm"] else "")
        out.append((f"{i:02d}_{s['name']}", x, [_stats(x)], meta))
    return out, M


# ============================================================================================ sheets
def contact_sheet(items, path, title, cols=2, max_s=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from scipy import signal
    n = len(items)
    rows = int(np.ceil(n / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(9 * cols, 2.3 * rows), squeeze=False)
    for k, (name, x, st, meta) in enumerate(items):
        ax = axes[k // cols][k % cols]
        xm = dsp.as_stereo(x).mean(axis=0)
        if max_s:
            xm = xm[: n_of(max_s)]
        nfft = 2048
        f, t, Z = signal.stft(xm, SR, nperseg=nfft, noverlap=nfft - 256, boundary=None, padded=False)
        P = 10 * np.log10(np.abs(Z) ** 2 + 1e-14)
        vmax = np.percentile(P, 99.8)
        edges = np.geomspace(30, 20000, 161)
        idx = np.searchsorted(f, edges)
        L = np.array([P[idx[i]:max(idx[i + 1], idx[i] + 1)].mean(axis=0) for i in range(160)])
        ax.pcolormesh(t, np.sqrt(edges[:-1] * edges[1:]), L, shading="nearest", cmap="magma", vmin=vmax - 80, vmax=vmax)
        ax.set_yscale("log")
        ax.set_ylim(30, 20000)
        ax.set_title(f"{name}  —  {meta}", fontsize=8)
        ax.tick_params(labelsize=7)
    for k in range(n, rows * cols):
        axes[k // cols][k % cols].axis("off")
    fig.suptitle(title, fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=70)
    plt.close(fig)
    return path


# ============================================================================================ main
def main():
    ap = argparse.ArgumentParser(description="render auditions + sanity stats")
    ap.add_argument("--events", default=None, help="events file for the score / ambience cuts (default: draft)")
    ap.add_argument("--only", default="instruments,sfx,ambience,score")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--calib", action="store_true", help="only print the SFX level hierarchy table")
    a = ap.parse_args()
    only = set(a.only.split(","))
    ev = a.events or config.EVENTS_JSON
    doc = tl.load(ev)
    if a.calib:
        rows = sfx_calibration(doc)
        print(f"{'sfx':18s} {'maxMom':>7s} {'peak':>6s} {'PLR':>5s} {'centroid':>8s}")
        for k, v in sorted(rows.items(), key=lambda kv: -kv[1]["max_momentary_lufs"]):
            print(f"{k:18s} {v['max_momentary_lufs']:7.1f} {v['peak_dbfs']:6.1f} {v['plr_db']:5.1f} {v['centroid_hz']:8.0f}")
        return
    os.makedirs(os.path.join(a.out, "sheets"), exist_ok=True)
    stats_path = os.path.join(a.out, "stats.json")
    stats = {}
    if os.path.exists(stats_path):
        try:
            with open(stats_path, "r", encoding="utf-8") as f:
                stats = json.load(f)
        except (OSError, ValueError):
            stats = {}
    T0 = time.time()
    groups = []
    if "instruments" in only:
        groups.append(("instruments", instrument_phrases()))
    if "sfx" in only:
        groups.append(("sfx", sfx_variations(doc)))
        stats["sfx_calibration_6m"] = sfx_calibration(doc)
    if "ambience" in only:
        items, _ = ambience_excerpts(doc)
        groups.append(("ambience", items))
    if "score" in only:
        items, M = score_sections(doc)
        groups.append(("score", items))
    for gname, items in groups:
        stats[gname] = {}
        for name, x, st, meta in items:
            g = _write(os.path.join(a.out, gname, f"{name}.wav"), x)
            stats[gname][name] = dict(meta=meta, file=os.path.join(gname, f"{name}.wav"), gain_db=round(g, 2),
                                      items=st)
        per = 12 if gname == "sfx" else 16
        for k in range(0, len(items), per):
            contact_sheet(items[k:k + per], os.path.join(a.out, "sheets", f"{gname}_{k // per + 1}.png"),
                          f"audition: {gname} ({k + 1}-{min(len(items), k + per)} of {len(items)})")
        print(f"{gname}: {len(items)} files")
    stats["_meta"] = dict(events=os.path.abspath(ev), target_lufs=TARGET_LUFS, render_s=round(time.time() - T0, 1))
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=1, default=float)
    print(f"stats -> {stats_path}  ({time.time() - T0:.1f} s)")


if __name__ == "__main__":
    main()
