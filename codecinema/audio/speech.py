"""Optional local acting voices and recorded dialogue, independent of a renderer.

Neural dependencies are loaded only when requested. Install ``.[speech]`` on an
Apple Silicon Mac; the ordinary framework remains usable on all platforms.
"""
from __future__ import annotations

import gc
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import wave

import numpy as np
from scipy.signal import resample_poly

from codecinema.workspace import settings

TTS_MODEL = "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-6bit"
ALIGN_MODEL = "mlx-community/Qwen3-ForcedAligner-0.6B-8bit"


def write_wave(path, samples, rate):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".partial.wav")
    with wave.open(str(temporary), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(rate)
        fh.writeframes((np.clip(samples, -.999, .999) * 32767).astype(np.int16).tobytes())
    temporary.replace(path)


def read_wave(path):
    with wave.open(str(path), "rb") as fh:
        if fh.getnchannels() != 1 or fh.getsampwidth() != 2:
            raise ValueError(f"Expected a mono PCM16 WAV: {path}")
        samples = np.frombuffer(fh.readframes(fh.getnframes()), np.int16).astype(np.float32) / 32768
        return samples, fh.getframerate()


def local_available():
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        return False
    from importlib.util import find_spec
    return find_spec("mlx_audio") is not None and find_spec("pypinyin") is not None


class SpeechEngine:
    """Cache spoken takes by text, voice, direction, model and random seed.

    Supplied recordings always take precedence. ``auto`` selects the local
    model when installed, then macOS's lightweight system voice. ``local``
    never silently falls back to a system voice.
    """

    def __init__(self, cache, engine="auto", model=TTS_MODEL):
        if engine not in ("auto", "local", "system", "recording"):
            raise ValueError(f"Unknown speech engine: {engine}")
        if engine == "auto":
            engine = "local" if local_available() else "system"
        if engine == "local" and not local_available():
            raise RuntimeError("Local emotional speech needs an Apple Silicon Mac and: python -m pip install '.[speech]'. "
                               "Other platforms can supply WAV takes or use --speech-engine system on macOS.")
        self.engine, self.model_id = engine, model
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.model = None

    def close(self):
        self.model = None
        gc.collect()
        if self.engine == "local":
            import mlx.core as mx
            mx.clear_cache()

    def take(self, text, *, voice="Dylan", direction="", recording=None, seed=43,
             system_voice="Tingting", rate=185, language="Chinese"):
        recording = Path(recording) if recording else None
        if recording and not recording.is_file():
            recording = None
        payload = {"text": text, "voice": voice, "direction": direction, "engine": self.engine,
                   "model": self.model_id, "seed": seed, "system_voice": system_voice, "rate": rate,
                   "recording": hashlib.sha256(recording.read_bytes()).hexdigest() if recording else None}
        if language != "Chinese":
            payload["language"] = language
        key = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24]
        target = self.cache / f"{key}.wav"
        if target.is_file():
            read_wave(target)  # Reject an interrupted or invalid cache entry.
            return target, key
        if recording:
            self._convert(recording, target)
        elif self.engine == "local":
            import mlx.core as mx
            from mlx_audio.tts.utils import load_model
            if self.model is None:
                mx.set_memory_limit(7 * 1024**3)
                mx.set_cache_limit(128 * 1024**2)
                print(f"Loading acting voice model: {self.model_id}", flush=True)
                self.model = load_model(self.model_id)
            mx.random.seed(seed)
            results = list(self.model.generate_custom_voice(
                text=text, speaker=voice, language=language, instruct=direction,
                max_tokens=400, verbose=False))
            if not results:
                raise RuntimeError("The speech model returned no audio")
            samples = np.concatenate([np.asarray(r.audio, dtype=np.float32).reshape(-1) for r in results])
            write_wave(target, samples, results[0].sample_rate)
        elif self.engine == "system":
            say = shutil.which("say")
            if not say:
                raise RuntimeError("No system Mandarin voice. Supply assets/<film-id>/voices/<shot_id>.wav recordings.")
            script, raw = self.cache / f"{key}.txt", self.cache / f"{key}.aiff"
            try:
                script.write_text(text, encoding="utf-8")
                subprocess.run([say, "-v", system_voice, "-r", str(rate), "-f", str(script), "-o", str(raw)], check=True)
                self._convert(raw, target)
            finally:
                raw.unlink(missing_ok=True)
                script.unlink(missing_ok=True)
        else:
            raise RuntimeError("A recording is required for this spoken cue")
        samples, _ = read_wave(target)
        if not len(samples) or not np.all(np.isfinite(samples)) or np.max(np.abs(samples)) < .001:
            target.unlink(missing_ok=True)
            raise ValueError("The speech take was empty or invalid")
        return target, key

    @staticmethod
    def _convert(source, target):
        temporary = target.with_suffix(".partial.wav")
        subprocess.run([settings.tool("ffmpeg"), "-v", "error", "-y", "-i", str(source),
                        "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(temporary)], check=True)
        temporary.replace(target)


class ForcedAligner:
    """Align the *final* waveform, including any editing, to its spoken text."""

    def __init__(self, model=ALIGN_MODEL):
        self.model_id, self.model = model, None

    def align(self, samples, rate, text):
        import mlx.core as mx
        from mlx_audio.stt import load
        if self.model is None:
            mx.set_memory_limit(6 * 1024**3)
            mx.set_cache_limit(128 * 1024**2)
            print(f"Loading dialogue aligner: {self.model_id}", flush=True)
            self.model = load(self.model_id)
        audio = resample_poly(samples, 16000, rate).astype(np.float32)
        result = self.model.generate(audio=audio, text=text, language="Chinese")
        duration = len(samples) / rate
        rows = [{"text": item.text, "start": max(0., float(item.start_time)),
                 "end": min(duration, float(item.end_time))} for item in result]
        if not rows or any(r["end"] < r["start"] for r in rows):
            raise ValueError("Forced alignment returned invalid dialogue timestamps")
        return rows

    def close(self):
        self.model = None
        gc.collect()
        import mlx.core as mx
        mx.clear_cache()
