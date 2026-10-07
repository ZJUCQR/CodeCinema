"""Original deterministic piano, string and glass score with synchronized Foley."""


from pathlib import Path

import numpy as np
import pyloudnorm as pyln
from scipy import signal
from scipy.io import wavfile
from story import CUES, SECONDS

SR = 48000
N = SR * SECONDS


def frequency(note):
    return 440 * 2 ** ((note - 69) / 12)


def tone(note, duration, kind="piano"):
    t = np.arange(int(duration * SR)) / SR
    f = frequency(note)
    if kind == "piano":
        out = sum(
            np.sin(2 * np.pi * f * k * (1 + 0.00016 * k * k) * t) * np.exp(-t * (0.65 + k * 0.31)) / k**1.7
            for k in range(1, 9)
        )
        out *= 1 - np.exp(-t * 180)
    elif kind == "glass":
        out = sum(
            np.sin(2 * np.pi * f * k * t) * np.exp(-t * (0.55 + j * 0.28)) / (j + 1) ** 2
            for j, k in enumerate((1, 2.002, 2.997, 4.17))
        )
        out *= 1 - np.exp(-t * 100)
    else:
        vibrato = 0.006 * np.sin(2 * np.pi * 4.5 * t)
        phase = 2 * np.pi * f * np.cumsum(1 + vibrato) / SR
        out = sum((np.sin(k * phase) + 0.4 * np.sin(k * phase * 1.0017 + 0.4)) / k**2 for k in range(1, 8))
        out *= np.minimum(t / 1.6, 1) * np.minimum((duration - t) / 2, 1)
    out *= np.minimum((duration - t) / 0.04, 1)
    return out


def add(track, mono, at, gain=1, pan=0):
    start = round(at * SR)
    length = min(len(mono), N - start)
    if length <= 0:
        return
    angle = (pan + 1) * np.pi / 4
    track[start : start + length, 0] += mono[:length] * gain * np.cos(angle)
    track[start : start + length, 1] += mono[:length] * gain * np.sin(angle)


def room(track):
    result = track.copy()
    for delay, gain in ((0.113, 0.20), (0.227, 0.16), (0.419, 0.12), (0.673, 0.09), (0.941, 0.06), (1.31, 0.035)):
        shift = int(delay * SR)
        result[shift:] += track[:-shift, ::-1] * gain
    return result


def generate(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(1207)
    music = np.zeros((N, 2))
    effects = np.zeros_like(music)
    # Six harmonic phrases follow the six shots; the last phrase resolves to D major.
    chords = (
        (50, 57, 60, 65),
        (46, 53, 57, 62),
        (48, 55, 60, 64),
        (50, 57, 62, 65),
        (43, 50, 57, 62),
        (50, 57, 61, 66),
    )
    melody = (
        (74, 77, 81, 77),
        (74, 72, 69, 65),
        (72, 76, 79, 76),
        (74, 77, 81, 86),
        (81, 79, 77, 74),
        (78, 81, 86, 85),
    )
    for section, (chord, notes) in enumerate(zip(chords, melody)):
        for j, note in enumerate(chord):
            add(music, tone(note, 10, "strings"), section * 8, 0.027 + section * 0.002, (j - 1.5) * 0.35)
            add(music, tone(note - 12, 7), section * 8 + 0.02 * j, 0.065, (j - 1.5) * 0.3)
        for j, note in enumerate(notes):
            at = section * 8 + j * 1.75 + 0.4
            add(music, tone(note, 5), at, 0.115 if section < 3 else 0.14, (-1) ** j * 0.28)
            if section >= 3:
                add(music, tone(note - 12, 4), at + 0.65, 0.045, (-1) ** (j + 1) * 0.5)
    # Broad stereo wind, slow dynamics and a quiet air-pressure bed.
    t = np.arange(N) / SR
    ambience = np.column_stack(
        [signal.sosfilt(signal.butter(2, 700, fs=SR, output="sos"), rng.normal(0, 1, N)) for _ in range(2)]
    )
    ambience *= 0.055 * (0.65 + 0.25 * np.sin(t * 0.31) + 0.10 * np.sin(t * 1.1))[:, None]
    # Reach motor ramps into contact; a tiny metal click occurs on the exact touch frame.
    q = np.arange(SR * 4) / SR
    servo = np.sin(2 * np.pi * (85 * q + 12 * q * q)) * 0.018 * np.sin(np.pi * q / 4) ** 2
    add(effects, servo, 16, 1, -0.35)
    q = np.arange(int(0.22 * SR)) / SR
    click = (rng.normal(0, 0.2, len(q)) + np.sin(2 * np.pi * 1600 * q)) * np.exp(-q * 45)
    add(effects, click, CUES["touch"], 0.075, -0.2)
    for event, notes in (("ignition", (50, 62, 69, 74)), ("signal", (86, 81, 89, 93)), ("answer", (78, 81, 86))):
        for j, note in enumerate(notes):
            add(effects, tone(note, 6, "glass"), CUES[event] + j * 0.22, 0.12, (-0.65 + j * 0.4))
    q = np.arange(8 * SR) / SR
    swell = signal.sosfilt(signal.butter(2, 1200, fs=SR, output="sos"), rng.normal(0, 1, len(q)))
    swell *= np.sin(np.pi * q / 8) ** 2 * 0.055
    add(effects, swell, 24, 1, 0.2)
    music = room(music)
    effects = room(effects)
    fade = np.minimum(t / 1.4, 1) * np.minimum((SECONDS - t) / 2.8, 1)
    mix = (music + ambience + effects) * fade[:, None]
    loudness = pyln.Meter(SR).integrated_loudness(mix)
    gain = 10 ** ((-16 - loudness) / 20)
    mix *= gain
    # Leave AAC headroom; no hard clipping of synthesized transients.
    peak = np.max(np.abs(mix))
    if peak > 0.79:
        mix *= 0.79 / peak
    for name, track in (("music", music), ("ambience", ambience), ("effects", effects), ("mix", mix)):
        wavfile.write(folder / f"{name}.wav", SR, track.astype(np.float32))
    return {
        "sample_rate": SR,
        "samples": N,
        "integrated_lufs": float(pyln.Meter(SR).integrated_loudness(mix)),
        "sample_peak_dbfs": float(20 * np.log10(np.max(np.abs(mix)))),
        "cues": CUES,
    }
