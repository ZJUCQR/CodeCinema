"""
codecinema.audio.mixer -- render and master a film's whole soundtrack from a timeline description.

    report = mix(audio, out_dir)

    audio = {"duration": 165.0, "seed": 7,
             "music": {"themes": {...}, "cues": [...]},                                   (codecinema.audio.composer)
             "dialogue": [{"t", "file", "who", "pan", "gain_db", "space"}],               mono WAV takes, any rate
                                                                       (or "samples" + "rate" instead of "file")
             "vocals": [{"t", "profile", "kind", "pan", "gain_db", "seed", "mood"}],      babble.vocalize
             "babble": [{"t", "profile", "text", "mood", "pan", "gain_db", "seed"}],      babble.render
             "sfx": [{"t", "name", "gain_db", "pan", "distance", "params"}],               sfx.render
             "foley": [{"t", "kind", "surface", "weight", "pan", "distance", "gain_db"}],
             "ambience": [{"start", "end", "bed", "gain_db", "fade", "intensity", "seed"}],  ambience.bed
             "spaces": [{"start", "end", "space": outdoor | forest | room | cave | underwater | memory}],
             "master": {"target_lufs": -16, "true_peak_db": -1, "bits": 24, "stems": true, "music_stems": false}}

Buses: dialogue (babble and vocals included), music, sfx, foley, ambience -- each with its own EQ.  Music and
ambience duck smoothly under the dialogue (sidechain).  Spaces vary over time: reverb sends (outdoor, forest, room,
cave) feed on the dialogue, effects and Foley; underwater muffles everything except the music; memory gives the
non-music buses a warm lo-fi band.  Every line of dialogue peaks at one loudness anchor; effects sit 3 dB and Foley
10 dB under it at gain 0 (distance in metres from the camera: no change within 2 m, then -10 log10(d/2) down to
-14 dB, plus air absorption); panning is equal-power.  The master gets gentle glue compression, loudness normalisation to the target
(pyloudnorm, ITU-R BS.1770) and a true-peak limiter.  Writes mix.wav (dsp.SR, stereo, 24- or 16-bit PCM),
stems/<bus>.wav and report.json; returns the report.
"""
import json
import time
import wave
from fractions import Fraction
from pathlib import Path

import numpy as np
from scipy import signal

from codecinema.audio import dsp
from codecinema.audio.dsp import SR, n_of

BUSES = ("dialogue", "music", "sfx", "foley", "ambience")
# level anchors on the loudest-100-ms (K-weighted) scale: every line of dialogue peaks at DIALOGUE_LU; effects and
# Foley are rendered at the same anchor and sit SFX_DB / FOLEY_DB under it at gain_db 0 and distance <= 2 m
# (with the perspective law an effect 4 m away reads ~6 dB, 10 m away ~10 dB under the dialogue peaks)
DIALOGUE_LU = -14.0
SFX_DB = -3.0
FOLEY_DB = -10.0
BUS_EQ = {
    "dialogue": [("hp", 85, 0, 0.7), ("peak", 300, -2.0, 1.0), ("peak", 3500, 2.0, 0.9), ("highshelf", 10000, 1.0, 0.7)],
    "music": [("hp", 28, 0, 0.7)],
    "sfx": [("hp", 30, 0, 0.7)],
    "foley": [("hp", 55, 0, 0.7), ("highshelf", 6000, 1.0, 0.7)],
    "ambience": [("hp", 40, 0, 0.7), ("peak", 2500, -1.5, 0.8), ("lp", 15000, 0, 0.7)],
}
# reverb sends per space: (preset, dialogue, sfx, foley, ambience wet)
SPACES = {
    "none": None,
    "outdoor": ("field", 0.10, 0.14, 0.08, 0.0),
    "forest": ("field", 0.18, 0.24, 0.14, 0.05),
    "room": ("room", 0.16, 0.2, 0.16, 0.0),
    "cave": ("temple", 0.35, 0.45, 0.32, 0.15),
    "underwater": ("hall", 0.25, 0.3, 0.2, 0.1),
    "memory": ("hall", 0.22, 0.22, 0.18, 0.1),
}
FOLEY = {
    # kind -> (sfx name, extra params from the event)
    "step": ("step", ("weight",)), "waddle": ("waddle", ("surface", "weight")),
    "creature_step": ("creature_step", ("weight", "surface")), "land": ("land", ("weight",)),
    "jump": ("jump", ("weight",)), "cloth": ("cloth_rustle", ("intensity",)), "rustle": ("cloth_rustle", ("intensity",)),
    "grab": ("grab", ("weight",)), "pat": ("pat", ("weight",)), "slide": ("slide_friction", ("dur", "surface")),
    "flap": ("wing_flap_small", ("dur",)), "sit": ("sit", ("weight",)),
}
_SURF = {"grass": "grass", "sand": "sand", "snow": "snow", "wood": "wood", "stone": "stone", "rock": "stone",
         "wet_rock": "wet_rock", "ground": "grass", "dirt": "grass", "floor": "wood", "ice": "stone"}


# ------------------------------------------------------------------------------------------------ files
def read_wav(path):
    """any PCM / float WAV -> mono float64 at dsp.SR"""
    from scipy.io import wavfile
    rate, data = wavfile.read(str(path))
    x = np.asarray(data)
    if x.dtype == np.uint8:
        x = (x.astype(np.float64) - 128.0) / 128.0
    elif np.issubdtype(x.dtype, np.integer):
        x = x.astype(np.float64) / float(np.iinfo(x.dtype).max + 1)
    else:
        x = x.astype(np.float64)
    if x.ndim == 2:
        x = x.mean(axis=1)
    if rate != SR:
        fr = Fraction(SR, int(rate)).limit_denominator(1000)
        x = signal.resample_poly(x, fr.numerator, fr.denominator)
    return x


def write_wav(path, x, bits=24):
    """stereo float -> PCM WAV (16 or 24 bit) at dsp.SR, written atomically"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    x = np.ascontiguousarray(np.clip(dsp.as_stereo(x).T, -1.0, 1.0))
    tmp = path.with_suffix(".partial.wav")
    with wave.open(str(tmp), "wb") as fh:
        fh.setnchannels(2)
        fh.setframerate(SR)
        if bits == 16:
            fh.setsampwidth(2)
            fh.writeframes((x * 32767.0).round().astype("<i2").tobytes())
        else:
            fh.setsampwidth(3)
            q = np.ascontiguousarray((x * 8388607.0).round().astype("<i4"))
            b = q.view(np.uint8).reshape(-1, 4)[:, :3]
            fh.writeframes(b.tobytes())
    tmp.replace(path)
    return path


# ------------------------------------------------------------------------------------------------ helpers
def distance_db(d):
    """film perspective rather than physics: no change within 2 m, then -10 log10(d / 2), at most -14 dB"""
    d = float(d)
    return 0.0 if d <= 2.0 else max(-14.0, -10.0 * np.log10(d / 2.0))


def _place_event(bus, clip, t, pan=0.0, gain_db=0.0, distance=None):
    clip = np.asarray(clip, dtype=np.float64)
    if distance is not None and float(distance) > 2.0:
        d = float(distance)
        clip = dsp.lowpass(clip, 20000.0 / (1.0 + d / 15.0), 2)       # air absorption
        gain_db += distance_db(d)
    if clip.ndim == 1:
        clip = dsp.pan_mono(clip, float(pan))
    elif pan:
        clip = dsp.pan_stereo(clip, float(pan), 1.0)
    dsp.place(bus, clip, n_of(t), dsp.db2lin(gain_db))


def _mask(n, segments, fade=0.25):
    """0..1 curve that is 1 inside the segments, with raised-cosine ramps of `fade` seconds centred on the edges"""
    t = np.arange(n) / SR
    m = np.zeros(n)
    h = max(fade, 1e-3) / 2.0
    for a, b in segments:
        rise = 0.5 - 0.5 * np.cos(np.pi * np.clip((t - (a - h)) / (2 * h), 0.0, 1.0))
        fall = 0.5 - 0.5 * np.cos(np.pi * np.clip(((b + h) - t) / (2 * h), 0.0, 1.0))
        m = np.maximum(m, np.minimum(rise, fall))
    return m


def _underwater(x):
    t = np.arange(x.shape[-1]) / SR
    fc = 650.0 * (1.0 + 0.25 * np.sin(2 * np.pi * 0.11 * t))
    y = dsp.lp_varying(x, fc, 1.1, spacing=0.5)
    y = dsp.peq(y, 250, 3.0, 0.8)
    return dsp.varispeed(y, 1.0 + 0.0015 * np.sin(2 * np.pi * 0.3 * t), n_out=x.shape[-1]) * 1.3


def _memory(x):
    y = dsp.highpass(x, 220, 2)
    y = dsp.lowpass(y, 3800, 2)
    y = dsp.peq(y, 1200, 2.0, 0.7)
    return dsp.saturate(y * 1.5, 0.3) / 1.5


def _lufs(x):
    import pyloudnorm as pyln
    x = dsp.as_stereo(x)
    if x.shape[-1] < n_of(0.5) or not np.any(x):
        return -70.0
    v = pyln.Meter(SR).integrated_loudness(x.T)
    return float(v) if np.isfinite(v) else -70.0


def _bus_report(x):
    return {"rms_db": round(float(dsp.lin2db(dsp.rms(x) + 1e-12)), 2),
            "peak_db": round(float(dsp.lin2db(dsp.peak(x) + 1e-12)), 2), "lufs": round(_lufs(x), 2)}


# ------------------------------------------------------------------------------------------------ the mix
def mix(audio, out_dir):
    """render, mix and master `audio` into out_dir; returns the report dict"""
    from codecinema.audio import ambience, babble, composer, sfx
    began = time.monotonic()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    duration = float(audio["duration"])
    seed = int(audio.get("seed", 0))
    n = n_of(duration)
    buses = {b: np.zeros((2, n)) for b in BUSES}
    warnings = []
    timing = {}

    # music
    t0 = time.monotonic()
    music = audio.get("music") or {}
    music_stems = {}
    if music.get("cues"):
        music_stems = composer.render_score(music, duration, seed)
        buses["music"] = sum(music_stems.values()) * dsp.db2lin(float(music.get("gain_db", -3.0)))
    timing["music_s"] = round(time.monotonic() - t0, 2)

    # dialogue: recorded takes, babble lines and creature vocals
    t0 = time.monotonic()
    line_spaces = []
    for ev in audio.get("dialogue") or []:
        if ev.get("samples") is not None:
            x = np.asarray(ev["samples"], dtype=np.float64)
            x = dsp.mono(x) if x.ndim == 2 else x
            rate = int(ev.get("rate", SR))
            if rate != SR:
                fr = Fraction(SR, rate).limit_denominator(1000)
                x = signal.resample_poly(x, fr.numerator, fr.denominator)
        else:
            path = Path(ev["file"])
            if not path.is_file():
                warnings.append(f"dialogue take missing: {path}")
                continue
            x = read_wav(path)
        x = x / (dsp.peak(x) + 1e-9) * dsp.db2lin(-3.0)
        x = dsp.eq_chain(x, BUS_EQ["dialogue"])
        x = dsp.compressor(x, -24.0, 2.5, 6.0, 140.0, 6.0, 4.0)[0][0]
        x = x * dsp.db2lin(DIALOGUE_LU - dsp.loudness_peak(x))
        _place_event(buses["dialogue"], x, float(ev["t"]), ev.get("pan", 0.0), float(ev.get("gain_db", 0.0)))
        if ev.get("space"):
            line_spaces.append((float(ev["t"]), float(ev["t"]) + len(x) / SR, ev["space"]))
    for ev in audio.get("babble") or []:
        x = babble.render(ev["text"], ev.get("profile", "girl"), ev.get("mood", "neutral"), int(ev.get("seed", 0)))
        _place_event(buses["dialogue"], x, float(ev["t"]), ev.get("pan", 0.0), float(ev.get("gain_db", 0.0)))
    for ev in audio.get("vocals") or []:
        x = babble.vocalize(ev["kind"], ev.get("profile", "girl"), int(ev.get("seed", 0)), ev.get("mood"))
        _place_event(buses["dialogue"], x, float(ev["t"]), ev.get("pan", 0.0), float(ev.get("gain_db", 0.0)))
    timing["dialogue_s"] = round(time.monotonic() - t0, 2)

    # effects and Foley
    t0 = time.monotonic()
    for k, ev in enumerate(audio.get("sfx") or []):
        x = sfx.render(ev["name"], seed=int(ev.get("seed", seed * 1000 + k)), **(ev.get("params") or {}))
        _place_event(buses["sfx"], x, float(ev["t"]), ev.get("pan", 0.0), float(ev.get("gain_db", 0.0)) + SFX_DB,
                     ev.get("distance"))
    for k, ev in enumerate(audio.get("foley") or []):
        x = _foley(sfx, ev, seed * 7919 + k)
        _place_event(buses["foley"], x, float(ev["t"]), ev.get("pan", 0.0), float(ev.get("gain_db", 0.0)) + FOLEY_DB,
                     ev.get("distance"))
    timing["effects_s"] = round(time.monotonic() - t0, 2)

    # ambience beds
    t0 = time.monotonic()
    for k, ev in enumerate(audio.get("ambience") or []):
        a, b = max(0.0, float(ev.get("start", 0.0))), min(duration, float(ev.get("end", duration)))
        if b <= a:
            continue
        y = ambience.bed(ev["bed"], b - a, seed=int(ev.get("seed", seed + k)), intensity=float(ev.get("intensity", 1.0)))
        fd = float(ev.get("fade", 1.0))
        y = dsp.fade(y, min(fd, (b - a) / 2), min(fd, (b - a) / 2))
        dsp.place(buses["ambience"], y, n_of(a), dsp.db2lin(float(ev.get("gain_db", -18.0)) + 2.0))
    timing["ambience_s"] = round(time.monotonic() - t0, 2)

    # bus EQ
    for b in BUSES:
        if b != "dialogue" and np.any(buses[b]):
            buses[b] = dsp.eq_chain(buses[b], BUS_EQ[b])

    # spaces
    t0 = time.monotonic()
    _apply_spaces(buses, audio.get("spaces") or [], line_spaces, n)
    timing["spaces_s"] = round(time.monotonic() - t0, 2)

    # ducking under the dialogue
    master_cfg = audio.get("master") or {}
    duck = _duck_curve(buses["dialogue"])
    if duck is not None:
        buses["music"] *= dsp.db2lin(-float(master_cfg.get("duck_music_db", 10.0)) * duck)[None, :]
        buses["ambience"] *= dsp.db2lin(-float(master_cfg.get("duck_ambience_db", 6.0)) * duck)[None, :]

    # master
    t0 = time.monotonic()
    master = audio.get("master") or {}
    from codecinema.workspace import settings
    target = float(master.get("target_lufs", settings.get("audio", "target_lufs", -16.0)))
    ceiling = float(master.get("true_peak_db", settings.get("audio", "true_peak_db", -1.0)))
    total = sum(buses.values())
    pre = _lufs(total)
    g = dsp.db2lin(target - pre) if pre > -70 else 1.0
    total = total * g
    total = dsp.compressor(total, target + 4.0, 1.6, 25.0, 250.0, 8.0)[0]
    for _ in range(3):
        lv = _lufs(total)
        if lv > -70:
            total = total * dsp.db2lin(target - lv)
        total, _gain = dsp.limiter(total, ceiling, lookahead_ms=5.0, release_ms=120.0)
        if abs(_lufs(total) - target) < 0.3:
            break
    k = min(n, n_of(0.01))
    if k > 1:
        total[:, :k] *= np.linspace(0, 1, k)
        total[:, -k:] *= np.linspace(1, 0, k)
    timing["master_s"] = round(time.monotonic() - t0, 2)
    final_lufs = _lufs(total)
    tp = dsp.true_peak_dbtp(total)
    bits = int(master.get("bits", 24))
    files = {"mix": str(write_wav(out_dir / "mix.wav", total, bits))}
    peaks = [dsp.peak(buses[b]) for b in BUSES] + [dsp.peak(x) for x in music_stems.values()]
    stem_gain = min(g, dsp.db2lin(-1.0) / max(max(peaks), 1e-9))
    for b in BUSES if master.get("stems", True) else ():
        files[b] = str(write_wav(out_dir / "stems" / f"{b}.wav", buses[b] * stem_gain, bits))
    if master.get("music_stems") and music_stems:
        for s, x in music_stems.items():
            files[f"music_{s}"] = str(write_wav(out_dir / "stems" / f"music_{s}.wav", x * stem_gain, bits))
    report = {
        "duration": duration, "sample_rate": SR, "bits": bits,
        "lufs": round(final_lufs, 2), "true_peak_dbtp": round(tp, 2), "target_lufs": target, "true_peak_limit": ceiling,
        "peak_dbfs": round(float(dsp.lin2db(dsp.peak(total) + 1e-12)), 2),
        "buses": {b: _bus_report(buses[b] * stem_gain) for b in BUSES}, "stem_gain_db": round(float(dsp.lin2db(stem_gain)), 2),
        "music": composer.summary(composer.plan(music, duration, seed)) if music.get("cues") else [],
        "counts": {k: len(audio.get(k) or []) for k in ("dialogue", "babble", "vocals", "sfx", "foley", "ambience")},
        "files": files, "warnings": warnings, "timing": {**timing, "total_s": round(time.monotonic() - began, 2)},
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def _foley(sfx, ev, seed):
    kind = ev.get("kind", "step")
    weight = float(ev.get("weight", 0.5))
    surface = _SURF.get(str(ev.get("surface", "stone")), "stone")
    if kind == "step":
        return sfx.render(f"step_{surface}", seed=seed, weight=weight)
    if kind == "land":
        a = sfx.render(f"step_{surface}", seed=seed, weight=min(1.0, weight + 0.3))
        b = sfx.render("thud", seed=seed, weight=weight)
        return _sum(a, 0.8, b, 0.6)
    if kind == "jump":
        return _sum(sfx.render("cloth_rustle", seed=seed, intensity=weight), 0.7,
                    sfx.render("swish", seed=seed, dur=0.18), 0.4)
    if kind == "grab":
        return _sum(sfx.render("cloth_rustle", seed=seed, intensity=weight, dur=0.25), 0.7,
                    sfx.render("pat", seed=seed, weight=weight), 0.6)
    if kind == "sit":
        return _sum(sfx.render("thud", seed=seed, weight=weight * 0.6), 0.6,
                    sfx.render("cloth_rustle", seed=seed, intensity=weight), 0.6)
    name, keys = FOLEY.get(kind, (kind, ()))
    params = {k: ev[k] for k in keys if k in ev}
    if "surface" in params and name in ("waddle", "creature_step"):
        params["surface"] = str(ev["surface"])
    return sfx.render(name, seed=seed, **params)


def _sum(a, ga, b, gb):
    a, b = dsp.as_stereo(a), dsp.as_stereo(b)
    n = max(a.shape[-1], b.shape[-1])
    return dsp.pad_to(a, n) * ga + dsp.pad_to(b, n) * gb


def _segments_union(segs, n, pad_before, pad_after):
    """merged sample windows [a, b) covering the segments plus margins"""
    win = sorted((max(0, n_of(a - pad_before)), min(n, n_of(b + pad_after))) for a, b in segs)
    out = []
    for a, b in win:
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        elif b > a:
            out.append((a, b))
    return out


def _active(x, a, b, gap_s=1.0):
    """sub-ranges of [a, b) where a bus actually carries sound (sparse buses convolve much faster this way)"""
    if b <= a:
        return []
    block = n_of(0.05)
    seg = np.abs(x[:, a:b]).max(axis=0)
    k = int(np.ceil(len(seg) / block))
    lv = np.pad(seg, (0, k * block - len(seg))).reshape(k, block).max(axis=1) > 1e-6
    if not np.any(lv):
        return []
    idx = np.nonzero(lv)[0]
    out = []
    gap = max(1, int(gap_s / 0.05))
    start = prev = idx[0]
    for i in idx[1:]:
        if i - prev > gap:
            out.append((a + start * block, min(b, a + (prev + 1) * block)))
            start = i
        prev = i
    out.append((a + start * block, min(b, a + (prev + 1) * block)))
    return out


def _apply_spaces(buses, spaces, line_spaces, n):
    """time-varying acoustic spaces: reverb sends plus the underwater / memory filters, processed only where a space
    is active (plus fade and reverb-tail margins)"""
    segs = {}
    for sp in spaces:
        name = sp.get("space", "none")
        if name not in SPACES:
            raise ValueError(f"Unknown space {name!r}; use one of {', '.join(SPACES)}")
        segs.setdefault(name, []).append((float(sp["start"]), float(sp["end"])))
    line_segs = {}
    for a, b, name in line_spaces:
        if name in SPACES:
            line_segs.setdefault(name, []).append((a, b))
    wet_buses = ("dialogue", "sfx", "foley", "ambience")
    out = {b: buses[b].copy() for b in wet_buses}
    for name, seg in segs.items():
        if name not in ("underwater", "memory"):
            continue
        m = _mask(n, seg, 0.3)
        fn = _underwater if name == "underwater" else _memory
        for a, b in _segments_union(seg, n, 0.5, 0.5):
            for bus in wet_buses:
                if np.any(buses[bus][:, a:b]):
                    proc = fn(buses[bus][:, a:b])
                    out[bus][:, a:b] = out[bus][:, a:b] * (1.0 - m[a:b]) + proc * m[a:b]
    for name, seg in list(segs.items()) + [(k, v) for k, v in line_segs.items() if k not in segs]:
        cfg = SPACES[name]
        if cfg is None:
            continue
        preset = cfg[0]
        lines_only = name not in segs
        m = _mask(n, seg, 0.1 if lines_only else 0.25)
        tail = dsp.reverb_tail_len(preset)
        for a0, b0 in _segments_union(seg, n, 0.5, 0.0):
            for k, bus in enumerate(wet_buses):
                if lines_only and bus != "dialogue":
                    continue
                send = cfg[1 + k]
                if send <= 0:
                    continue
                for a, b in _active(buses[bus], a0, b0):
                    e = min(n, b + tail)
                    x = buses[bus][:, a:b] * m[a:b]
                    if name == "underwater":
                        x = _underwater(x)
                    out[bus][:, a:e] += send * dsp.convolve_reverb(x, preset, seed=21, n_out=e - a)
    for b in wet_buses:
        buses[b] = out[b]


def _duck_curve(dialogue):
    """0..1 amount of ducking: follows the dialogue level (fast attack, slow release)"""
    if not np.any(dialogue):
        return None
    x = dsp.mono(dialogue)
    block = n_of(0.01)
    k = len(x) // block
    if k < 2:
        return None
    e = np.sqrt(np.mean(x[:k * block].reshape(k, block) ** 2, axis=1))
    db = dsp.lin2db(e + 1e-9)
    ref = np.percentile(db[db > -80], 90) if np.any(db > -80) else -20.0
    amt = np.clip((db - (ref - 22.0)) / 10.0, 0.0, 1.0)
    out = np.empty_like(amt)
    g = 0.0
    att, rel = np.exp(-1.0 / (0.04 * 100)), np.exp(-1.0 / (0.45 * 100))
    for i, v in enumerate(amt.tolist()):
        g = att * g + (1 - att) * v if v > g else rel * g + (1 - rel) * v
        out[i] = g
    curve = np.interp(np.arange(len(x)), (np.arange(k) + 0.5) * block, out)
    return dsp.onepole(curve, 8.0)
