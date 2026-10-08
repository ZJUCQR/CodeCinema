"""Spoken dialogue from recordings, a local neural voice, or the operating system's voice.

Supplied recordings always win. The neural voice (Qwen3-TTS through mlx-audio)
is optional and loaded only when requested; install ``.[speech]`` on an Apple
Silicon Mac. System voices work everywhere: macOS `say`, Windows SAPI through
PowerShell, and `espeak-ng` (or `espeak`) on Linux.
"""
from __future__ import annotations

import gc
import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import wave

import numpy as np
from scipy.signal import resample_poly

from codecinema.workspace import settings

TTS_MODEL = "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-6bit"
DESIGN_MODEL = "mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-6bit"
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


# Narration languages, their locales and the standard voice preferred for each one on macOS.
SYSTEM_LOCALES = {"Chinese": "zh_CN", "English": "en_US", "Japanese": "ja_JP", "Korean": "ko_KR",
                  "French": "fr_FR", "German": "de_DE", "Spanish": "es_ES", "Italian": "it_IT",
                  "Portuguese": "pt_BR", "Russian": "ru_RU"}
PREFERRED_SYSTEM_VOICES = {"zh_CN": "Tingting", "en_US": "Samantha", "ja_JP": "Kyoko", "ko_KR": "Yuna",
                           "fr_FR": "Thomas", "de_DE": "Anna", "es_ES": "Mónica", "it_IT": "Alice",
                           "pt_BR": "Luciana", "ru_RU": "Milena"}
NOVELTY_VOICES = {"Albert", "Bad News", "Bahh", "Bells", "Boing", "Bubbles", "Cellos", "Good News", "Jester",
                  "Organ", "Superstar", "Trinoids", "Whisper", "Wobble", "Zarvox"}
ESPEAK_VOICES = {"zh_CN": "cmn", "en_US": "en-us", "ja_JP": "ja", "ko_KR": "ko", "fr_FR": "fr", "de_DE": "de",
                 "es_ES": "es", "it_IT": "it", "pt_BR": "pt-br", "ru_RU": "ru"}


def system_backend():
    """'say' (macOS), 'sapi' (Windows), 'espeak' (Linux and others) or None."""
    if shutil.which("say"):
        return "say"
    if platform.system() == "Windows" and (shutil.which("powershell") or shutil.which("pwsh")):
        return "sapi"
    if shutil.which("espeak-ng") or shutil.which("espeak"):
        return "espeak"
    return None


def _installed_system_voices():
    """{locale: [voice, ...]} from `say -v ?`, or {} where macOS speech is unavailable."""
    say = shutil.which("say")
    if not say:
        return {}
    listing = subprocess.run([say, "-v", "?"], capture_output=True, text=True, encoding="utf-8",
                             errors="replace").stdout
    voices = {}
    for line in listing.splitlines():
        match = re.match(r"^(.*?)\s+([a-z]{2,3}_[A-Z]{2,3})\s+#", line)
        if match:
            voices.setdefault(match[2], []).append(match[1].strip())
    return voices


def system_voice(language="Chinese"):
    """The system voice for `language` on this platform: a macOS voice name, a Windows culture or an espeak voice."""
    locale = SYSTEM_LOCALES.get(language, "en_US")
    backend = system_backend()
    if backend == "sapi":
        return locale.replace("_", "-")
    if backend == "espeak":
        return ESPEAK_VOICES.get(locale, "en-us")
    preferred = PREFERRED_SYSTEM_VOICES[locale]
    installed = _installed_system_voices().get(locale, [])
    if preferred in installed or not installed:
        return preferred
    return next((voice for voice in installed if voice not in NOVELTY_VOICES), installed[0])


_SAPI = r"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$pick = $s.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -eq $args[0] } |
        Select-Object -First 1
if (-not $pick) { $pick = $s.GetInstalledVoices() | Where-Object {
        $_.Enabled -and $_.VoiceInfo.Culture.Name.StartsWith($args[0].Substring(0, 2)) } | Select-Object -First 1 }
if ($pick) { $s.SelectVoice($pick.VoiceInfo.Name) }
$s.Rate = [int]$args[3]
$s.SetOutputToWaveFile($args[2])
$s.Speak([IO.File]::ReadAllText($args[1], [Text.Encoding]::UTF8))
$s.Dispose()
"""


def speak_system(text, voice, rate, target_raw, script):
    """Render `text` with the platform voice into an audio file; returns the file written."""
    backend = system_backend()
    if backend is None:
        raise RuntimeError("No system voice found. Install espeak-ng (Linux), or supply WAV recordings in "
                           "assets/<film-id>/voices/.")
    script.write_text(text, encoding="utf-8")
    if backend == "say":
        subprocess.run([shutil.which("say"), "-v", voice, "-r", str(rate), "-f", str(script), "-o", str(target_raw)],
                       check=True)
        return target_raw
    if backend == "sapi":
        out = target_raw.with_suffix(".wav")
        ps = script.with_suffix(".ps1")
        ps.write_text(_SAPI, encoding="utf-8")
        shell = shutil.which("powershell") or shutil.which("pwsh")
        try:
            subprocess.run([shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps), voice, str(script),
                            str(out), str(max(-10, min(10, round((rate - 175) / 12))))], check=True)
        finally:
            ps.unlink(missing_ok=True)
        return out
    out = target_raw.with_suffix(".wav")
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    subprocess.run([exe, "-v", voice, "-s", str(int(rate * 0.9)), "-w", str(out), "-f", str(script)], check=True)
    return out


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
            engine = "local" if local_available() else "system" if system_backend() else "recording"
        if engine == "local" and not local_available():
            raise RuntimeError("Local emotional speech needs an Apple Silicon Mac and: python -m pip install '.[speech]'. "
                               "Elsewhere, supply WAV takes or use --speech-engine system.")
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
             system_voice="Tingting", rate=185, language="Chinese", design=None):
        """A cached take. `design` describes a new voice in words (the voice-design model) instead of a speaker."""
        recording = Path(recording) if recording else None
        if recording and not recording.is_file():
            recording = None
        payload = {"text": text, "voice": voice, "direction": direction, "engine": self.engine,
                   "model": self.model_id, "seed": seed, "system_voice": system_voice, "rate": rate,
                   "recording": hashlib.sha256(recording.read_bytes()).hexdigest() if recording else None}
        if language != "Chinese":
            payload["language"] = language
        if design:
            payload["design"] = design
            payload["model"] = DESIGN_MODEL
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
            wanted = DESIGN_MODEL if design else self.model_id
            if self.model is None or getattr(self, "_loaded", None) != wanted:
                self.model = None
                gc.collect()
                mx.set_memory_limit(7 * 1024**3)
                mx.set_cache_limit(128 * 1024**2)
                print(f"Loading acting voice model: {wanted}", flush=True)
                self.model = load_model(wanted)
                self._loaded = wanted
            mx.random.seed(seed)
            if design:
                instruct = design if not direction else f"{design} {direction}"
                results = list(self.model.generate(text=text, instruct=instruct, language=language,
                                                   max_tokens=600, verbose=False))
            else:
                results = list(self.model.generate_custom_voice(
                    text=text, speaker=voice, language=language, instruct=direction,
                    max_tokens=400, verbose=False))
            if not results:
                raise RuntimeError("The speech model returned no audio")
            samples = np.concatenate([np.asarray(r.audio, dtype=np.float32).reshape(-1) for r in results])
            write_wave(target, samples, results[0].sample_rate)
        elif self.engine == "system":
            script, raw = self.cache / f"{key}.txt", self.cache / f"{key}.aiff"
            written = None
            try:
                written = speak_system(text, system_voice, rate, raw, script)
                self._convert(written, target)
            finally:
                for path in (raw, script, written):
                    if path is not None and Path(path) != target:
                        Path(path).unlink(missing_ok=True)
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

    def align(self, samples, rate, text, language="Chinese"):
        import mlx.core as mx
        from mlx_audio.stt import load
        if self.model is None:
            mx.set_memory_limit(6 * 1024**3)
            mx.set_cache_limit(128 * 1024**2)
            print(f"Loading dialogue aligner: {self.model_id}", flush=True)
            self.model = load(self.model_id)
        audio = resample_poly(samples, 16000, rate).astype(np.float32)
        result = self.model.generate(audio=audio, text=text, language=language)
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
