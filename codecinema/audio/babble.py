"""
codecinema.audio.babble -- cartoon voices without text-to-speech.

    plan(text, profile="girl", mood="neutral", seed=0) -> {"duration": s, "syllables": [{"t0", "t1", "vowel", "level",
                                                         "text", "f0", "stress"}]}
    render(text, profile="girl", mood="neutral", seed=0) -> mono float64 at dsp.SR, following plan() exactly
    vocalize(kind, profile="girl", seed=0, mood=None) -> mono float64 at dsp.SR
    PROFILES, MOODS, VOCALIZATIONS

The planner is pure arithmetic on the text (no audio, no optional packages), so lip-sync can be built from it before
any sound exists: Latin text is split into syllables at vowel groups, every CJK character is one syllable (its
vowel chosen deterministically), punctuation becomes pauses and intonation (a question rises, an exclamation
peaks).  Vowels are 'a' 'e' 'i' 'o' 'u'.  Human profiles speak through a glottal source with pitch contour, jitter
and shimmer, three formant resonators per vowel scaled by vocal-tract size, consonant noise bursts and breath;
creature profiles turn the same syllables into their calls (gull squawks, cat mews, fox yips, bird chirps, robot
beeps, the gentle rumbling hums of a big friendly beast).
"""
import re

import numpy as np

from codecinema.audio import dsp
from codecinema.audio.dsp import TWO_PI, n_of, t_axis

VOWELS = ("a", "e", "i", "o", "u")
# F1, F2, F3 (Hz) of an adult male voice, and relative formant gains
FORMANTS = {"a": (730, 1090, 2440), "e": (530, 1840, 2480), "i": (300, 2250, 3000), "o": (500, 850, 2400),
            "u": (320, 800, 2240), "m": (280, 1100, 2300)}
F_BW = (90.0, 110.0, 160.0)
F_GAIN = (1.0, 0.55, 0.32)

PROFILES = {
    # f0 (Hz), pitch range (semitones), vocal-tract scale (formants x), syllables per second, breath, jitter,
    # tremor (cents), nasal emphasis, kind
    "girl": dict(f0=275, range=7.0, tract=1.22, rate=4.6, breath=0.06, jitter=0.008, tremor=0, nasal=0.0, kind="voice"),
    "boy": dict(f0=245, range=6.5, tract=1.18, rate=4.8, breath=0.05, jitter=0.009, tremor=0, nasal=0.0, kind="voice"),
    "woman": dict(f0=205, range=6.0, tract=1.12, rate=4.2, breath=0.06, jitter=0.008, tremor=0, nasal=0.0, kind="voice"),
    "man": dict(f0=112, range=5.0, tract=1.0, rate=4.0, breath=0.05, jitter=0.01, tremor=0, nasal=0.0, kind="voice"),
    "grandma": dict(f0=190, range=5.0, tract=1.08, rate=3.4, breath=0.12, jitter=0.022, tremor=28, nasal=0.1,
                    kind="voice"),
    "grandpa": dict(f0=102, range=4.5, tract=0.97, rate=3.2, breath=0.14, jitter=0.025, tremor=22, nasal=0.05,
                    kind="voice"),
    "penguin_kid": dict(f0=390, range=9.0, tract=1.38, rate=5.6, breath=0.04, jitter=0.012, tremor=0, nasal=0.35,
                        kind="voice"),
    "creature_big": dict(f0=72, range=6.0, tract=0.62, rate=2.3, breath=0.1, jitter=0.012, tremor=10, nasal=0.2,
                         kind="beast"),
    "seagull": dict(f0=900, range=5.0, tract=1.6, rate=3.5, breath=0.05, jitter=0.03, tremor=0, nasal=0.0, kind="gull"),
    "fox": dict(f0=520, range=8.0, tract=1.45, rate=3.8, breath=0.06, jitter=0.02, tremor=0, nasal=0.2, kind="fox"),
    "cat": dict(f0=470, range=7.0, tract=1.5, rate=2.6, breath=0.05, jitter=0.015, tremor=0, nasal=0.15, kind="cat"),
    "small_bird": dict(f0=3200, range=7.0, tract=1.0, rate=7.0, breath=0.0, jitter=0.0, tremor=0, nasal=0.0, kind="bird"),
    "robot": dict(f0=1300, range=12.0, tract=1.0, rate=5.0, breath=0.0, jitter=0.0, tremor=0, nasal=0.0, kind="robot"),
}
MOODS = {
    # pitch offset (semitones), range factor, speed factor, loudness, breathiness, final contour, extra tremor (cents)
    "neutral": dict(shift=0.0, span=1.0, speed=1.0, loud=0.8, breath=1.0, end=-2.5, tremor=0),
    "happy": dict(shift=2.5, span=1.35, speed=1.08, loud=0.9, breath=1.0, end=1.0, tremor=0),
    "excited": dict(shift=4.5, span=1.7, speed=1.22, loud=1.0, breath=0.9, end=2.0, tremor=0),
    "sad": dict(shift=-2.0, span=0.6, speed=0.78, loud=0.6, breath=1.6, end=-4.0, tremor=12),
    "scared": dict(shift=4.0, span=1.2, speed=1.18, loud=0.75, breath=1.8, end=1.5, tremor=45),
    "angry": dict(shift=1.0, span=1.3, speed=1.08, loud=1.0, breath=0.7, end=-3.0, tremor=0),
    "curious": dict(shift=1.5, span=1.2, speed=0.98, loud=0.8, breath=1.0, end=5.0, tremor=0),
    "tender": dict(shift=-1.0, span=0.8, speed=0.88, loud=0.62, breath=1.8, end=-2.0, tremor=0),
    "sleepy": dict(shift=-3.0, span=0.5, speed=0.68, loud=0.5, breath=2.2, end=-3.0, tremor=0),
}
VOCALIZATIONS = ("laugh", "giggle", "gasp", "sigh", "cry", "sob", "yay", "hmm", "huh", "wow", "oh", "ouch", "yawn",
                 "sniff", "growl_soft", "whimper", "rumble_happy", "squawk", "chirp", "yip", "beep_happy", "beep_sad",
                 "beep_question")

_PLOSIVE, _FRIC, _NASAL, _LIQUID = set("pbtdkgqc"), set("sfvzhjx"), set("mn"), set("lrwy")
_PUNCT = {",": 0.2, ";": 0.25, ":": 0.25, ".": 0.38, "!": 0.32, "?": 0.34, "…": 0.55, "-": 0.12, "—": 0.3,
          "，": 0.22, "。": 0.4, "！": 0.34, "？": 0.36, "、": 0.15, "；": 0.25, "：": 0.25}


def _is_cjk(c):
    o = ord(c)
    return 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF or 0x3040 <= o <= 0x30FF or 0xAC00 <= o <= 0xD7AF


def _latin_syllables(word):
    """'little' -> [('l', 'i', 'li'), ('tt', 'e', 'ttle')]: (onset consonants, vowel, text)"""
    w = word.lower()
    groups = list(re.finditer(r"[aeiouyàáâäèéêëìíîïòóôöùúûü]+", w))
    if not groups:
        return [(w, "e", word)]
    if len(groups) > 1 and w.endswith("e") and groups[-1].group() == "e" and not w.endswith("le"):
        groups = groups[:-1]
    splits = [0]
    for k in range(1, len(groups)):
        cluster = groups[k].start() - groups[k - 1].end()
        splits.append(groups[k].start() - (1 if cluster >= 1 else 0))
    splits.append(len(w))
    out = []
    for k, g in enumerate(groups):
        v = g.group()
        vowel = ("i" if v in ("ee", "ea", "ie", "y", "ey") else "u" if v in ("oo", "ou", "ew", "ue") else
                 "o" if v[0] in "oòóôö" else "a" if v[0] in "aàáâä" else "e" if v[0] in "eèéêë" else
                 "i" if v[0] in "iyìíîï" else "u")
        out.append((w[splits[k]:g.start()], vowel, word[splits[k]:splits[k + 1]]))
    return out


def _tokens(text):
    """[(kind, payload)]: ('syl', (onset, vowel, text, word_index, stressed)) | ('pause', (seconds, mark))"""
    out = []
    word_i = 0
    for m in re.finditer(r"[A-Za-zÀ-ÿ']+|[぀-ヿ㐀-䶿一-鿿가-힯]|[,.;:!?…\-—，。！？、；：]|\s+", text):
        tok = m.group()
        if tok.isspace():
            out.append(("gap", 0.05))
            continue
        if tok in _PUNCT:
            out.append(("pause", (_PUNCT[tok], tok)))
            continue
        if len(tok) == 1 and _is_cjk(tok):
            v = VOWELS[(ord(tok) * 2654435761 >> 7) % 5]
            onset = "ptkmsnlhfj"[(ord(tok) * 40503 >> 3) % 10]
            out.append(("syl", (onset, v, tok, word_i, (ord(tok) % 3) == 0)))
            word_i += 1
            continue
        syls = _latin_syllables(tok)
        for k, (onset, v, s) in enumerate(syls):
            stressed = (k == 0 and len(syls) <= 2) or (k == len(syls) - 2 and len(syls) > 2)
            out.append(("syl", (onset, v, s, word_i, stressed)))
        word_i += 1
    return out


def plan(text, profile="girl", mood="neutral", seed=0):
    """deterministic timing of the syllables of `text` (seconds from the start of the line)"""
    p = PROFILES[profile] if isinstance(profile, str) else profile
    md = MOODS.get(mood or "neutral", MOODS["neutral"])
    r = dsp.rng("babble-plan", text, profile if isinstance(profile, str) else "custom", mood, seed)
    toks = _tokens(str(text))
    syl_rate = p["rate"] * md["speed"]
    t = 0.04
    rows = []
    phrase_syls = []
    for kind, payload in toks + [("pause", (0.0, "."))]:
        if kind == "gap":
            if rows and rows[-1]["t1"] >= t - 1e-9:
                t += payload * (1.25 if mood == "sleepy" else 1.0) * r.uniform(0.7, 1.3)
            continue
        if kind == "pause":
            secs, mark = payload
            if phrase_syls:
                # intonation of the finished phrase: declination, mood, question / exclamation endings
                k = len(phrase_syls)
                end = md["end"] + (5.0 if mark in ("?", "？") else (2.0 if mark in ("!", "！") else 0.0))
                for j, row in enumerate(phrase_syls):
                    u = j / max(1, k - 1)
                    row["semis"] += -2.5 * u
                    if j == k - 1:
                        row["semis"] += end
                        row["t1"] = row["t0"] + (row["t1"] - row["t0"]) * 1.35
                        row["level"] *= 0.85
                t = phrase_syls[-1]["t1"]
                phrase_syls = []
            t += secs / max(0.6, md["speed"]) * (1.4 if mood == "sleepy" else 1.0)
            continue
        onset, vowel, s, word_i, stressed = payload
        d = (1.0 / syl_rate) * r.uniform(0.82, 1.2) * (1.12 if stressed else 0.95)
        cons = len(onset) > 0
        row = {"t0": round(t, 4), "t1": round(t + d, 4), "vowel": vowel, "text": s, "onset": onset[-2:],
               "stress": bool(stressed), "word": word_i,
               "level": float(np.clip(md["loud"] * (1.0 if stressed else 0.82) * r.uniform(0.9, 1.05), 0.1, 1.0)),
               "semis": md["shift"] + (p["range"] * 0.35 * md["span"] if stressed else 0.0)
               + r.normal(0.0, 0.9) * md["span"], "consonant": cons}
        rows.append(row)
        phrase_syls.append(row)
        t = row["t1"]
    for row in rows:
        row["t1"] = round(row["t1"], 4)
        row["f0"] = round(float(p["f0"] * 2.0 ** (row["semis"] / 12.0)), 2)
        row["semis"] = round(float(row["semis"]), 3)
        row["level"] = round(row["level"], 3)
    duration = (rows[-1]["t1"] if rows else 0.0) + 0.25
    return {"duration": round(duration, 4), "syllables": rows, "profile": profile if isinstance(profile, str) else "custom",
            "mood": mood or "neutral", "text": str(text)}


# ------------------------------------------------------------------------------------------------ synthesis
def _vowel_bank(src, vowel, tract, nasal=0.0):
    """parallel formant resonators (3 formants) for one vowel, tract-scaled"""
    fr = FORMANTS[vowel]
    y = np.zeros_like(src)
    for f, bw, g in zip(fr, F_BW, F_GAIN):
        fc = min(f * tract, dsp.NYQ * 0.8)
        y += g * dsp.biquad(src, "bp", fc, q=fc / (bw * max(tract, 0.6)))
    if nasal:
        y += nasal * dsp.biquad(src, "bp", 1000.0 * tract, q=2.5) - 0.3 * nasal * dsp.biquad(src, "bp", 700 * tract, q=4.0)
    return y


def _glottal(f, n, r, tilt_hz=900.0, soft=0.0):
    """band-limited pulse source with a spectral tilt; soft > 0 mixes toward a sine (warm, breathy fundamental)"""
    saw = dsp.osc_saw(f, n, r.uniform())
    src = dsp.onepole(saw, tilt_hz)
    src = src / (dsp.rms(src) + 1e-9)
    if soft:
        sine = np.sin(TWO_PI * dsp.phase_cycles(f, n, r.uniform()))
        src = (1.0 - soft) * src + soft * sine * 1.4
    return src


def _voice(p, md, rows, duration, r, seed):
    n = n_of(duration)
    t = t_axis(n)
    tract = p["tract"]
    # pitch curve: per-syllable targets, smoothed glides, jitter, tremor / vibrato
    semis = np.zeros(n)
    amp = np.zeros(n)
    w = {v: np.zeros(n) for v in VOWELS}
    fric_env = np.zeros(n)
    plosive = []
    for row in rows:
        a, b = n_of(row["t0"]), min(n, n_of(row["t1"]))
        if b <= a:
            continue
        glide = row.get("glide")
        if glide and len(glide) > 1:
            gt = [g[0] for g in glide] + [row["t1"]]
            gs = [g[1] for g in glide] + [glide[-1][1]]
            semis[a:b] = np.interp(t[a:b], gt, gs)
        else:
            semis[a:b] = row["semis"]
        L = b - a
        on = n_of(0.05 if not row["consonant"] else 0.035)
        off = n_of(0.045)
        env = np.ones(L)
        env[:min(on, L)] = np.linspace(0.0, 1.0, min(on, L)) ** 1.5
        env[max(0, L - off):] *= np.linspace(1.0, 0.0, L - max(0, L - off))
        amp[a:b] = np.maximum(amp[a:b], env * row["level"])
        w[row["vowel"]][a:b] = 1.0
        o = row.get("onset", "")
        c = o[-1] if o else ""
        if c in _PLOSIVE:
            plosive.append((a, c))
            k = min(L, n_of(0.03))
            amp[a:a + k] *= np.linspace(0.15, 1.0, k)
        elif c in _FRIC:
            k = min(L, n_of(0.07))
            fric_env[a:a + k] = np.maximum(fric_env[a:a + k], np.sin(np.pi * np.linspace(0, 1, k)) * row["level"])
            amp[a:a + k] *= np.linspace(0.2, 1.0, k)
        elif c in _NASAL:
            k = min(L, n_of(0.05))
            w["u"][a:a + k] = np.maximum(w["u"][a:a + k], 0.8)
    semis = dsp.onepole(semis, 9.0)
    cents = 100.0 * semis + 100.0 * p["jitter"] * 12.0 * dsp.ctrl_noise(n, r, 25.0)
    trem = p["tremor"] + md["tremor"]
    if trem:
        cents += trem * np.sin(TWO_PI * dsp.phase_cycles(5.5 + 3.0 * (md["tremor"] > 30), n, r.uniform()))
    f = p["f0"] * dsp.cents2ratio(cents)
    amp = dsp.onepole(amp, 40.0)
    amp *= 1.0 + 0.06 * dsp.ctrl_noise(n, r, 18.0)
    beast = p["kind"] == "beast"
    src = _glottal(f, n, r, tilt_hz=500.0 if beast else (650.0 if md["breath"] > 1.5 else 900.0),
                   soft=0.55 if beast else (0.25 if md["breath"] > 1.5 else 0.0))
    if beast:
        sub = np.sin(TWO_PI * dsp.phase_cycles(f * 0.5, n, r.uniform()))
        src = src + 0.35 * sub * (0.6 + 0.4 * np.sin(TWO_PI * 24.0 * t))
    breath = r.standard_normal(n) * p["breath"] * md["breath"] * 3.0
    exc = src + breath
    total_w = sum(dsp.onepole(w[v], 25.0) for v in VOWELS) + 1e-9
    y = np.zeros(n)
    for v in VOWELS:
        if np.any(w[v]):
            wv = dsp.onepole(w[v], 25.0) / total_w
            y += _vowel_bank(exc, v, tract, p["nasal"]) * wv
    y *= amp
    # consonants: fricative hiss and plosive bursts
    if np.any(fric_env):
        hiss = dsp.bandpass(r.standard_normal(n), 2500 * min(tract, 1.4), min(9000.0, 7000 * tract), 2)
        y += 0.35 * fric_env * hiss / (dsp.rms(hiss) + 1e-9) * (dsp.rms(y) + 1e-6) * 2.0
    lvl = dsp.rms(y) + 1e-6
    for a, c in plosive:
        k = min(n - a, n_of(0.012))
        if k <= 0:
            continue
        lo, hi = (500, 4000) if c in "pb" else ((2500, 8000) if c in "tdc" else (1200, 5000))
        burst = dsp.bandpass(r.standard_normal(k), lo, hi, 2) * np.exp(-t_axis(k) / 0.004)
        y[a:a + k] += 2.5 * lvl * burst / (dsp.rms(burst) + 1e-9) * (0.7 if c in "bdg" else 1.0)
    y = dsp.highpass(y, 70 if not beast else 30, 2)
    return y


def _creature(p, md, rows, duration, r):
    """non-speaking profiles: every syllable becomes the creature's call"""
    n = n_of(duration)
    y = np.zeros(n)
    kind = p["kind"]
    for k, row in enumerate(rows):
        d = max(0.06, row["t1"] - row["t0"])
        f0 = p["f0"] * 2.0 ** (row["semis"] / 12.0)
        rr = dsp.rng("creature", kind, k, round(f0, 1))
        if kind == "gull":
            call = _gull_call(rr, f0, d * 1.1)
        elif kind == "cat":
            call = _meow(rr, f0, d * 1.3, row["vowel"])
        elif kind == "fox":
            call = _yip(rr, f0, min(d, 0.22))
        elif kind == "bird":
            call = _chirp(rr, f0, min(d, 0.12))
        else:
            call = _beep_seq(rr, f0, d, row["semis"])
        dsp.place(y, call * row["level"], n_of(row["t0"]))
    return y


def _gull_call(r, f0, d):
    n = n_of(d)
    tt = t_axis(n)
    f = f0 * (1.0 + 0.3 * np.sin(np.pi * np.clip(tt / d, 0, 1)) - 0.25 * tt / d)
    rasp = 1.0 + 0.5 * np.sign(np.sin(TWO_PI * 75.0 * tt))
    ph = dsp.phase_cycles(f, n)
    src = sum(np.sin(TWO_PI * h * ph) / h ** 0.7 for h in range(1, 8)) * rasp
    y = dsp.bandpass(src, 1200, 5000, 2) + 0.3 * dsp.biquad(src, "bp", 2400, 3.0)
    return y * np.sin(np.pi * np.clip(tt / d, 0, 1)) ** 0.6


def _meow(r, f0, d, vowel):
    n = n_of(d)
    tt = t_axis(n)
    u = tt / d
    f = f0 * (1.0 + 0.25 * np.sin(np.pi * u) - 0.15 * u)
    src = _glottal(f, n, r, 1200.0)
    yi = _vowel_bank(src, "i", 1.6)
    ya = _vowel_bank(src, "a", 1.6)
    yu = _vowel_bank(src, "u", 1.6)
    wa = np.sin(np.pi * np.clip(u * 1.2, 0, 1))
    y = yi * np.clip(1 - u * 3, 0, 1) + ya * wa + yu * np.clip(u * 2 - 1, 0, 1)
    return y * np.sin(np.pi * np.clip(u, 0, 1)) ** 0.8


def _yip(r, f0, d):
    n = n_of(d)
    tt = t_axis(n)
    f = f0 * (1.0 + 0.5 * np.exp(-tt / 0.03))
    src = _glottal(f, n, r, 1500.0) + 0.3 * r.standard_normal(n)
    y = _vowel_bank(src, "i", 1.45) * np.clip(1 - tt / d, 0, 1) + _vowel_bank(src, "a", 1.45) * np.clip(tt / d, 0, 1)
    return y * np.exp(-tt / (d * 0.5)) * np.clip(tt / 0.004, 0, 1)


def _chirp(r, f0, d):
    n = n_of(d)
    tt = t_axis(n)
    f = f0 * (1.3 - 0.5 * tt / d) * (1.0 + 0.05 * np.sin(TWO_PI * 40 * tt))
    y = np.sin(TWO_PI * dsp.phase_cycles(f, n)) + 0.1 * np.sin(TWO_PI * 2 * dsp.phase_cycles(f, n))
    return y * np.sin(np.pi * np.clip(tt / d, 0, 1)) ** 1.2


def _beep_seq(r, f0, d, semis):
    n = n_of(d * 0.9)
    tt = t_axis(n)
    f1 = f0 * 2.0 ** (r.uniform(-5, 7) / 12.0)
    f = f0 + (f1 - f0) * dsp.smoothstep(tt / max(d * 0.9, 1e-3))
    y = np.sin(TWO_PI * dsp.phase_cycles(f, n))
    if r.uniform() < 0.35:
        y = dsp.lowpass(np.sign(y) * 0.6, 4500, 2)
    return y * dsp.env_points([(0, 0), (0.008, 1), (max(0.01, d * 0.9 - 0.012), 1), (d * 0.9, 0)], n)


def render(text, profile="girl", mood="neutral", seed=0):
    """mono audio of `text` spoken as babble, timed exactly as plan(text, profile, mood, seed)"""
    p = PROFILES[profile]
    md = MOODS.get(mood or "neutral", MOODS["neutral"])
    pl = plan(text, profile, mood, seed)
    rows = pl["syllables"]
    r = dsp.rng("babble", text, profile, mood, seed)
    if not rows:
        return np.zeros(n_of(pl["duration"]))
    if p["kind"] in ("voice", "beast"):
        y = _voice(p, md, rows, pl["duration"], r, seed)
    else:
        y = _creature(p, md, rows, pl["duration"], r)
    return _level(y)


def _level(y, ref_lu=-14.0):
    """the loudest 100 ms of the line at ref_lu (K-weighted), sample peaks at most -1 dBFS"""
    y = dsp.fade(y, 0.003, 0.03)
    if not np.any(y):
        return y
    y = y * dsp.db2lin(ref_lu - dsp.loudness_peak(y))
    if dsp.peak(y) > dsp.db2lin(-1.0):
        y = dsp.limiter(y, -1.0, lookahead_ms=2.0, release_ms=60.0, true_peak=False)[0][0]
    return y


# ------------------------------------------------------------------------------------------------ vocalizations
def _syl(t0, d, vowel, semis, level=0.9, onset=""):
    return {"t0": t0, "t1": t0 + d, "vowel": vowel, "semis": semis, "level": level, "onset": onset,
            "consonant": bool(onset), "text": vowel}


def _breath_noise(r, d, tract, vowel="a", inhale=False, level=1.0):
    n = n_of(d)
    tt = t_axis(n)
    src = r.standard_normal(n)
    y = _vowel_bank(src, vowel, tract) * 0.6 + dsp.bandpass(src, 1500, 6000, 2) * 0.3
    env = np.sin(np.pi * np.clip(tt / d, 0, 1)) ** (0.5 if inhale else 1.2)
    if inhale:
        env *= np.clip(tt / (d * 0.15), 0, 1)
    return y * env * level


def vocalize(kind, profile="girl", seed=0, mood=None):
    """non-verbal sounds: laugh giggle gasp sigh cry sob yay hmm huh wow oh ouch yawn sniff growl_soft whimper
    rumble_happy squawk chirp yip beep_happy beep_sad beep_question"""
    if kind not in VOCALIZATIONS:
        raise KeyError(f"Unknown vocalization {kind!r}. Known: {', '.join(VOCALIZATIONS)}")
    p = dict(PROFILES[profile])
    md = MOODS.get(mood or "neutral", MOODS["neutral"])
    r = dsp.rng("vocalize", kind, profile, mood, seed)
    rows, extra = [], []
    if kind in ("beep_happy", "beep_sad", "beep_question"):
        return _level(_robot(kind, r, p))
    if kind in ("squawk", "chirp", "yip"):
        n_calls = {"squawk": int(r.integers(1, 3)), "chirp": int(r.integers(2, 5)), "yip": int(r.integers(1, 3))}[kind]
        y = np.zeros(n_of(0.35 * n_calls + 0.4))
        f0 = {"squawk": 950.0, "chirp": 3400.0, "yip": 650.0}[kind] * (p["f0"] / PROFILES[profile]["f0"])
        if kind == "chirp" and p["kind"] != "bird":
            f0 = 2800.0
        if kind == "yip" and p["kind"] not in ("fox",):
            f0 = max(400.0, p["f0"] * 1.8)
        for k in range(n_calls):
            rr = dsp.rng("call", kind, seed, k)
            call = (_gull_call(rr, f0 * r.uniform(0.9, 1.1), r.uniform(0.25, 0.4)) if kind == "squawk" else
                    _chirp(rr, f0 * r.uniform(0.9, 1.15), r.uniform(0.05, 0.1)) if kind == "chirp" else
                    _yip(rr, f0 * r.uniform(0.95, 1.1), r.uniform(0.12, 0.18)))
            dsp.place(y, call * r.uniform(0.7, 1.0), n_of(k * r.uniform(0.18, 0.32)))
        return _level(y)
    beast = p["kind"] == "beast"
    if p["kind"] not in ("voice", "beast"):
        p = dict(PROFILES["girl"], f0=p["f0"] * 0.5 if p["f0"] > 600 else p["f0"], tract=min(p["tract"], 1.4))
    if kind == "laugh":
        k = int(r.integers(4, 7))
        for j in range(k):
            rows.append(_syl(0.05 + j * 0.17, 0.12, "a", 4.0 - 0.8 * j + r.normal(0, 0.5), 0.9 - 0.06 * j, "h"))
    elif kind == "giggle":
        k = int(r.integers(5, 8))
        for j in range(k):
            rows.append(_syl(0.04 + j * 0.11, 0.08, "i", 7.0 - 0.5 * j + r.normal(0, 0.6), 0.8 - 0.05 * j, "h"))
    elif kind == "yay":
        rows += [_syl(0.05, 0.12, "e", 3.0, 0.8, "y"), _syl(0.17, 0.42, "i", 7.0, 1.0)]
    elif kind == "hmm":
        rows.append(_syl(0.05, 0.6, "u", 0.0, 0.6, "m"))
        extra.append(("contour", [(0.0, -1.0), (0.3, 1.5), (0.65, -0.5)]))
    elif kind == "huh":
        rows.append(_syl(0.05, 0.22, "a", 0.0, 0.8, "h"))
        extra.append(("contour", [(0.0, -1.0), (0.27, 5.0)]))
    elif kind == "wow":
        rows += [_syl(0.05, 0.1, "u", 0.0, 0.7, "w"), _syl(0.15, 0.32, "a", 3.0, 1.0), _syl(0.47, 0.15, "u", 0.0, 0.7)]
    elif kind == "oh":
        rows.append(_syl(0.05, 0.38, "o", 3.0, 0.9))
        extra.append(("contour", [(0.0, 4.0), (0.43, -2.0)]))
    elif kind == "ouch":
        rows += [_syl(0.03, 0.18, "a", 7.0, 1.0), _syl(0.21, 0.12, "u", 2.0, 0.8, "")]
        extra.append(("fric_end", 0.36))
    elif kind == "sigh":
        rows.append(_syl(0.25, 0.75, "a", 1.0, 0.45, "h"))
        extra.append(("contour", [(0.25, 2.0), (1.0, -4.0)]))
        extra.append(("breath_pre", 0.25))
    elif kind == "yawn":
        rows += [_syl(0.05, 1.1, "a", 2.0, 0.6), _syl(1.15, 0.35, "u", -3.0, 0.4, "m")]
        extra.append(("contour", [(0.05, 3.0), (0.6, 4.0), (1.5, -4.0)]))
    elif kind in ("cry", "whimper"):
        hi = 9.0 if kind == "cry" else 6.0
        k = 1 if kind == "whimper" else int(r.integers(2, 4))
        t0 = 0.05
        for j in range(k):
            d = r.uniform(0.6, 1.0) if kind == "cry" else r.uniform(0.5, 0.8)
            rows.append(_syl(t0, d, "a" if kind == "cry" else "i", hi, 0.75, "w" if kind == "cry" else "m"))
            extra.append(("contour", [(t0, hi), (t0 + d * 0.3, hi + 1.5), (t0 + d, hi - 6.0)]))
            t0 += d + r.uniform(0.15, 0.3)
        p["tremor"] = max(p["tremor"], 45 if kind == "cry" else 35)
    elif kind == "sob":
        t0 = 0.05
        for j in range(int(r.integers(3, 6))):
            extra.append(("inhale", (t0, 0.12)))
            t0 += 0.14
            rows.append(_syl(t0, 0.14, "u", 3.0 - j, 0.6, "h"))
            t0 += 0.2 + r.uniform(0.05, 0.2)
        p["tremor"] = max(p["tremor"], 40)
    elif kind == "gasp":
        extra.append(("inhale", (0.0, 0.38)))
    elif kind == "sniff":
        extra.append(("sniff", 0.0))
        extra.append(("sniff", 0.22))
    elif kind == "growl_soft":
        rows.append(_syl(0.05, 0.9, "o", -2.0, 0.55, ""))
        p["tremor"] = 0
        extra.append(("growl", 22.0))
    elif kind == "rumble_happy":
        rows += [_syl(0.05, 0.4, "u", 0.0, 0.6, "m"), _syl(0.5, 0.55, "o", 3.0, 0.7)]
        extra.append(("contour", [(0.05, 0.0), (0.45, 2.0), (0.6, 3.5), (1.05, 0.5)]))
        extra.append(("growl", 30.0))
    if beast:
        for row in rows:
            row["vowel"] = {"i": "u", "e": "o", "a": "o"}.get(row["vowel"], row["vowel"])
    dur = max([row["t1"] for row in rows] + [0.5]) + 0.3
    for kind_e, v in extra:
        if kind_e == "inhale":
            dur = max(dur, v[0] + v[1] + 0.2)
    n = n_of(dur)
    y = np.zeros(n)
    if rows:
        for row in rows:
            row["semis"] += md["shift"]
        y = _voice(p, md, rows, dur, r, seed)
        if any(k == "contour" for k, _ in extra):
            pts = [pt for k, v in extra if k == "contour" for pt in v]
            y = _recontour(p, md, rows, dur, r, seed, sorted(pts))
        if any(k == "growl" for k, _ in extra):
            rate = [v for k, v in extra if k == "growl"][0]
            y *= 0.65 + 0.35 * np.abs(np.sin(np.pi * rate * t_axis(n)))
    for kind_e, v in extra:
        if kind_e == "inhale":
            at, d = v
            dsp.place(y, _breath_noise(r, d, p["tract"], "a", True, 1.0) * (dsp.rms(y) * 3.0 + 0.05), n_of(at))
        elif kind_e == "breath_pre":
            dsp.place(y, _breath_noise(r, v, p["tract"], "o", True, 0.6) * (dsp.rms(y) * 2.0 + 0.03), 0)
        elif kind_e == "sniff":
            k = n_of(0.12)
            s = dsp.bandpass(r.standard_normal(k), 2500, 7500, 2) * np.sin(np.pi * np.linspace(0, 1, k)) ** 2
            dsp.place(y, s * 0.3, n_of(v))
        elif kind_e == "fric_end":
            k = n_of(0.12)
            s = dsp.bandpass(r.standard_normal(k), 2500, 6000, 2) * np.sin(np.pi * np.linspace(0, 1, k))
            dsp.place(y, s * (dsp.rms(y) * 2.0 + 0.02), n_of(v))
    return _level(y)


def _recontour(p, md, rows, dur, r, seed, pts):
    """re-render a vocalization with an explicit pitch contour [(t, semis)] instead of flat syllable targets"""
    ts = np.array([q[0] for q in pts])
    ss = np.array([q[1] for q in pts]) + md["shift"]
    out_rows = []
    for row in rows:
        mid = 0.5 * (row["t0"] + row["t1"])
        out_rows.append(dict(row, semis=float(np.interp(mid, ts, ss))))
    # render each syllable split into short pieces so the glide follows the contour
    pieces = []
    for row in out_rows:
        k = max(1, int((row["t1"] - row["t0"]) / 0.05))
        edges = np.linspace(row["t0"], row["t1"], k + 1)
        for j in range(k):
            sm = float(np.interp(0.5 * (edges[j] + edges[j + 1]), ts, ss))
            pieces.append(dict(row, t0=float(edges[j]), t1=float(edges[j + 1]), semis=sm,
                               onset=row["onset"] if j == 0 else "", consonant=row["consonant"] and j == 0))
    return _voice_continuous(p, md, pieces, dur, r)


def _voice_continuous(p, md, pieces, dur, r):
    """like _voice, but adjoining pieces of a syllable are joined without amplitude dips"""
    merged = []
    for pc in pieces:
        if merged and abs(merged[-1]["t1"] - pc["t0"]) < 1e-6 and not pc["consonant"] and merged[-1]["vowel"] == pc["vowel"]:
            merged[-1]["glide"].append((pc["t0"], pc["semis"]))
            merged[-1]["t1"] = pc["t1"]
        else:
            merged.append(dict(pc, glide=[(pc["t0"], pc["semis"])]))
    return _voice(p, md, merged, dur, r, 0)


def _robot(kind, r, p):
    if kind == "beep_happy":
        seq = [(0.0, 1200, 1700, 0.08), (0.11, 1500, 2100, 0.07), (0.21, 1800, 2600, 0.12)]
    elif kind == "beep_sad":
        seq = [(0.0, 1400, 1100, 0.25), (0.3, 1100, 700, 0.45)]
    else:
        seq = [(0.0, 1300, 1250, 0.09), (0.13, 1100, 1900, 0.22)]
    scale = p["f0"] / 1300.0 if p["kind"] == "robot" else 1.0
    y = np.zeros(n_of(1.0))
    for at, f0, f1, d in seq:
        n = n_of(d)
        tt = t_axis(n)
        f = (f0 + (f1 - f0) * dsp.smoothstep(tt / d)) * scale
        b = np.sin(TWO_PI * dsp.phase_cycles(f, n)) * dsp.env_points([(0, 0), (0.006, 1), (d - 0.01, 1), (d, 0)], n)
        dsp.place(y, b, n_of(at))
    return y
