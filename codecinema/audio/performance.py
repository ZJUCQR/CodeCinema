"""Renderer-neutral, waveform-gated mouth shapes on the actual speech clock."""
from __future__ import annotations

from bisect import bisect_right
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np

_CURRENT = ContextVar("codecinema_spoken_performance", default=None)


@dataclass(frozen=True)
class Mouth:
    shape: str = "closed"
    opening: float = 0.


def phoneme(text):
    try:
        from pypinyin import lazy_pinyin
        sound = lazy_pinyin(text)[0].lower()
    except (ImportError, IndexError):
        sound = text.lower()
    consonant = next((s for s in ("zh", "ch", "sh", "b", "p", "m", "f") if sound.startswith(s)), "")
    if "a" in sound:
        vowel = "a"
    elif "o" in sound or "u" in sound or "ü" in sound:
        vowel = "o"
    elif "i" in sound:
        vowel = "i"
    else:
        vowel = "e"
    return consonant, vowel


def describe(samples, rate, *, text, speaker, start=.65, alignment=(), method="envelope"):
    """Store a small 100 Hz RMS envelope and aligned syllables, not a waveform."""
    samples = np.asarray(samples, dtype=np.float32)
    hop = max(1, round(rate / 100))
    padded = np.pad(samples, (0, (-len(samples)) % hop))
    rms = np.sqrt(np.mean(padded.reshape(-1, hop)**2, axis=1))
    reference = max(float(np.percentile(rms, 88)), .005)
    # The fixed floor closes the mouth in noise and the relative floor handles quiet takes.
    energy = np.clip((rms - max(.0015, reference * .055)) / (reference * .85), 0, 1)
    rows = []
    for item in alignment:
        onset, vowel = phoneme(item["text"])
        rows.append({**item, "onset": onset, "vowel": vowel})
    return {"version": 1, "speaker": speaker, "text": text, "start": start,
            "duration": len(samples) / rate, "envelope_hz": rate / hop,
            "energy": np.round(energy, 4).tolist(), "alignment": rows, "method": method}


class Performance:
    def __init__(self, data=None):
        self.data = data or {}
        self.rows = self.data.get("alignment", [])
        self.starts = [row["start"] for row in self.rows]

    @classmethod
    def load(cls, path):
        path = Path(path)
        return cls(json.loads(path.read_text(encoding="utf-8"))) if path.is_file() else cls()

    def mouth(self, time, character):
        if not character or character != self.data.get("speaker"):
            return Mouth()
        local = time - self.data.get("start", .65)
        if not 0 <= local < self.data.get("duration", 0):
            return Mouth()
        energy = self.data.get("energy", [])
        at = local * self.data.get("envelope_hz", 100)
        index = int(at)
        if index >= len(energy):
            return Mouth()
        amplitude = energy[index] * (1 - at + index) + energy[min(index+1, len(energy)-1)] * (at-index)
        if amplitude < .035:
            return Mouth()
        i = bisect_right(self.starts, local) - 1
        if self.rows:
            if i < 0 or local >= self.rows[i]["end"]:
                return Mouth()
            row = self.rows[i]
            phase = (local-row["start"]) / max(row["end"]-row["start"], .001)
            if row["onset"] in ("b", "p", "m") and phase < .22:
                return Mouth()
            if row["onset"] == "f" and phase < .25:
                return Mouth("f", float(amplitude) * .3)
            return Mouth(row["vowel"], float(amplitude))
        return Mouth("e", float(amplitude))


@contextmanager
def activate(performance, time):
    """Scope a performance to one frame; safe for threads and render workers."""
    token = _CURRENT.set((performance, time))
    try:
        yield
    finally:
        _CURRENT.reset(token)


def current_mouth(character):
    current = _CURRENT.get()
    return current[0].mouth(current[1], character) if current else Mouth()
