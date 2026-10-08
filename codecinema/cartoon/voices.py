"""Dialogue for cartoon films: one take per line, its timing and its mouth envelope.

Each character's `voice` in the cast library says how it speaks:

    "voice": {"profile": "girl", "speaker": "Vivian", "design": "A bright seven-year-old girl...", "pitch": 3.0}

Takes come from, in order: a recording in assets/<film>/voices/<line>.flac (or
.wav) whose text still matches; the local neural voice (voice design when a
description is given, otherwise a named speaker); the operating system's voice;
and finally cartoon babble, which needs nothing installed. Creatures without
words (`speaker` and `design` both empty) always use babble and vocalizations.
`--keep-voices` stores the takes as FLAC recordings, so the film sounds the
same on every platform without a speech model.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly

from codecinema.audio import dsp
from codecinema.audio import speech as speaking
from codecinema.workspace import settings

MOODS = {
    "neutral": "Natural and warm, conversational.",
    "happy": "Cheerful and bright, smiling while speaking.",
    "excited": "Very excited and energetic, almost bouncing.",
    "joy": "Bursting with joy.",
    "sad": "Sad and quiet, a little shaky.",
    "teary": "Holding back tears, voice trembling.",
    "moved": "Deeply moved, soft and trembling with emotion.",
    "scared": "Frightened and breathless.",
    "worried": "Worried and uncertain.",
    "curious": "Curious and wondering.",
    "tender": "Soft, warm and tender.",
    "dreamy": "Dreamy and hopeful, gazing far away.",
    "determined": "Determined and brave.",
    "angry": "Annoyed and firm.",
    "shout": "Shouting loudly across a distance.",
    "whisper": "Whispering softly.",
    "laughing": "Laughing while speaking.",
    "wise": "Calm and wise, with a gentle smile, at a natural pace.",
    "surprised": "Surprised, with a quick rising voice.",
    "proud": "Proud and beaming.",
    "pleading": "Pleading, urgent and emotional.",
}


def _key(line, voice, language):
    """What a take depends on: a recording made for an older version of the line is not reused."""
    blob = json.dumps({"text": line.get("text"), "vocal": line.get("vocal"), "voice": voice, "mood": line.get("mood"),
                       "delivery": MOODS.get(line.get("mood", "neutral"), ""), "direction": line.get("direction"),
                       "language": language}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def trim(samples, rate, floor_db=-42.0, pad=0.04):
    """Cut the silence a speech model leaves before and after a line (keeps a short natural margin)."""
    if not len(samples):
        return samples
    hop = max(1, int(rate * 0.01))
    frames = len(samples) // hop
    if frames < 3:
        return samples
    rms = np.sqrt(np.mean(samples[:frames * hop].reshape(frames, hop) ** 2, axis=1))
    peak = float(rms.max())
    loud = np.where(rms > peak * 10 ** (floor_db / 20))[0]
    if not len(loud):
        return samples
    a = max(0, loud[0] * hop - int(pad * rate))
    b = min(len(samples), (loud[-1] + 1) * hop + int(pad * 2 * rate))
    out = samples[a:b].copy()
    fade = min(len(out) // 4, int(0.015 * rate))
    if fade > 1:
        out[:fade] *= np.linspace(0, 1, fade)
        out[-fade:] *= np.linspace(1, 0, fade)
    return out


def envelope(samples, rate, hz=100.0):
    hop = max(1, round(rate / hz))
    padded = np.pad(samples, (0, (-len(samples)) % hop))
    rms = np.sqrt(np.mean(padded.reshape(-1, hop) ** 2, axis=1))
    ref = max(float(np.percentile(rms, 90)), 0.005)
    return np.clip((rms - max(0.0015, ref * 0.06)) / (ref * 0.85), 0, 1)


def _load_any(path):
    """Decode a recording (any format ffmpeg reads) to mono float at the film's sample rate."""
    path = Path(path)
    if path.suffix.lower() == ".wav":
        try:
            samples, rate = speaking.read_wave(path)
            return _to_rate(samples, rate)
        except (ValueError, OSError):
            pass
    out = subprocess.run([settings.tool("ffmpeg"), "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(dsp.SR),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(out, dtype=np.float32).astype(np.float64)


def _to_rate(samples, rate):
    if rate == dsp.SR:
        return np.asarray(samples, dtype=np.float64)
    from math import gcd
    g = gcd(int(rate), int(dsp.SR))
    return resample_poly(np.asarray(samples, dtype=np.float64), dsp.SR // g, rate // g)


class Casting:
    def __init__(self, plan, out_dir, assets_dir, engine="auto"):
        self.plan = plan
        self.out = Path(out_dir)
        self.out.mkdir(parents=True, exist_ok=True)
        self.assets = Path(assets_dir) / "voices"
        self.language = plan.get("language", "English")
        self.requested = engine
        self.engine = None
        self.manifest_path = self.assets / "lines.json"
        try:
            self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.manifest = {}

    def _speech(self):
        if self.engine is None:
            choice = self.requested
            if choice == "babble":
                self.engine = False
            else:
                try:
                    self.engine = speaking.SpeechEngine(self.out / "cache", "auto" if choice == "auto" else choice)
                except RuntimeError:
                    if choice not in ("auto",):
                        raise
                    self.engine = False
        return self.engine

    def take(self, line):
        cast = self.plan["cast"][line["who"]]["spec"]
        voice = dict(cast.get("voice", {}))
        voice.update(line.get("voice", {}))
        key = _key(line, voice, self.language)
        for ext in (".flac", ".wav", ".ogg", ".m4a"):
            rec = self.assets / f"{line['id']}{ext}"
            if rec.is_file() and self.manifest.get(line["id"]) == key:
                return _load_any(rec), "recording", None
        mood = line.get("mood", "neutral")
        profile = voice.get("profile", "girl")
        wordless = not voice.get("speaker") and not voice.get("design")
        if line.get("vocal") or wordless or not line.get("text"):
            return self._babble(line, profile, mood)
        engine = self._speech()
        if not engine:
            return self._babble(line, profile, mood)
        direction = " ".join(filter(None, (voice.get("direction", ""), MOODS.get(mood, ""), line.get("direction", ""))))
        design = voice.get("design") if engine.engine == "local" else None
        system = speaking.system_voice(self.language)
        path, _ = engine.take(line["text"], voice=voice.get("speaker") or "Serena", direction=direction,
                              language=self.language, design=design, system_voice=system,
                              seed=int(voice.get("seed", 7)), rate=int(voice.get("rate", 175)))
        samples, rate = speaking.read_wave(path)
        samples = _to_rate(samples, rate)
        shift = float(voice.get("pitch", 0.0)) if engine.engine != "local" or not design else \
            float(voice.get("design_pitch", 0.0))
        if abs(shift) > 0.05:
            samples = dsp.pitch_shift(samples, shift)
        return samples, engine.engine, None

    def _babble(self, line, profile, mood):
        from codecinema.audio import babble
        seed = int(hashlib.sha256(line["id"].encode()).hexdigest()[:6], 16) % 10000
        if line.get("vocal"):
            samples = babble.vocalize(line["vocal"], profile, seed, mood=mood)
            return np.asarray(samples, dtype=np.float64), "babble", []
        timing = babble.plan(line.get("text") or "...", profile, mood, seed)
        samples = babble.render(line.get("text") or "...", profile, mood, seed)
        return np.asarray(samples, dtype=np.float64), "babble", timing.get("syllables", [])

    def run(self, keep=False):
        lines = self.plan.get("lines", [])
        result = {}
        for i, line in enumerate(lines):
            samples, engine, syllables = self.take(line)
            if samples.ndim > 1:
                samples = samples.mean(axis=0)
            if engine != "babble":
                samples = trim(samples, dsp.SR)
            peak = float(np.max(np.abs(samples))) if len(samples) else 0.0
            if peak > 0:
                samples = samples * (0.9 / peak)
            target = self.out / f"{line['id']}.wav"
            speaking.write_wave(target, samples.astype(np.float32), dsp.SR)
            env = envelope(samples, dsp.SR)
            result[line["id"]] = {"file": str(target), "duration": round(len(samples) / dsp.SR, 3),
                                  "energy": [round(float(v), 3) for v in env], "envelope_hz": 100.0,
                                  "syllables": syllables or [], "engine": engine, "who": line["who"],
                                  "text": line.get("text", "")}
            print(f"Voice {i + 1}/{len(lines)} {line['id']} {line['who']} [{engine}] "
                  f"{len(samples) / dsp.SR:.2f}s {line.get('text') or line.get('vocal')}", flush=True)
            if keep and engine not in ("recording",):
                self.keep(line, target)
        partial = self.out / "voices.partial.json"
        partial.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
        partial.replace(self.out / "voices.json")
        if keep:
            self.assets.mkdir(parents=True, exist_ok=True)
            self.manifest_path.write_text(json.dumps(self.manifest, indent=1, sort_keys=True), encoding="utf-8")
        return result

    def keep(self, line, wav):
        """Save a take as a FLAC recording so any platform reproduces the film without a speech model."""
        self.assets.mkdir(parents=True, exist_ok=True)
        cast = self.plan["cast"][line["who"]]["spec"]
        voice = dict(cast.get("voice", {}))
        voice.update(line.get("voice", {}))
        target = self.assets / f"{line['id']}.flac"
        subprocess.run([settings.tool("ffmpeg"), "-v", "error", "-y", "-i", str(wav), "-ar", "24000", "-ac", "1",
                        "-sample_fmt", "s16", "-compression_level", "8", str(target)], check=True)
        self.manifest[line["id"]] = _key(line, voice, self.language)
