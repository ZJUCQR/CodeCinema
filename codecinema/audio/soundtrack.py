"""Scene-timed score, speech placement and dialogue ducking for story projects."""

import json
import numpy as np
from scipy.io import wavfile
from codecinema import settings
from codecinema.audio import dsp
from codecinema.renderers.palettes import PALETTES


def score(context):
    """A stereo pad and scene-timed bells, synthesized locally with the shared DSP toolkit."""
    n = dsp.n_of(context.duration)
    t = dsp.t_axis(n)
    root = PALETTES[context.scenes[0][0]["preset"]]["root"]
    drone = sum(dsp.osc_sine(root * ratio, n) * amplitude for ratio, amplitude in ((1, 0.5), (1.5, 0.3), (2, 0.2)))
    drone *= dsp.env_points(
        [
            (0, 0),
            (min(0.5, context.duration * 0.2), 0.35),
            (context.duration - min(0.8, context.duration * 0.25), 0.35),
            (context.duration, 0),
        ],
        n,
    )
    drone *= 1 + 0.12 * np.sin(2 * np.pi * 0.25 * t)
    mix = dsp.pan_mono(drone * 0.6, -0.15)
    for i, (spec, start, end) in enumerate(context.scenes):
        at = dsp.n_of(start / context.fps + min(0.7, (end - start) / context.fps * 0.2))
        m = min(dsp.n_of(3.5), n - at)
        note = PALETTES[spec["preset"]]["root"] * (4, 6, 5)[i % 3]
        bell = dsp.additive(note, m, [(1, 1.0, 3.0), (2.76, 0.35, 1.6), (5.4, 0.12, 0.8)])
        bell *= dsp.env_decay(m, 3.0)
        mix[:, at : at + m] += dsp.pan_mono(dsp.fade(bell, 0.006, 0.2) * 0.4, (-0.25, 0.2, 0)[i % 3])
    mix += 0.3 * dsp.convolve_reverb(mix, "hall")
    mix = dsp.fade(dsp.normalize(mix, 0.78), 0.03, min(0.8, context.duration * 0.25))
    limited = dsp.limiter(mix, float(settings.get("audio", "true_peak_db", -1.0)))
    return limited[0] if isinstance(limited, tuple) else limited


def generate(context):
    context.out.mkdir(parents=True, exist_ok=True)
    temporary = context.sound.with_name("sound.partial.wav")
    mix = score(context)
    cues = [(spec, start, end) for spec, start, end in context.scenes if spec.get("narration", {}).get("text")]
    if cues:
        from codecinema.audio.speech import SpeechEngine, read_wave
        from scipy.signal import resample_poly
        from scipy.ndimage import uniform_filter1d

        speech = SpeechEngine(context.film / "out/voices", context.options.speech_engine)
        dialogue = np.zeros(mix.shape[1], dtype=np.float32)
        try:
            for spec, start, end in cues:
                cue = spec["narration"]
                recording = context.film / "assets/voices" / cue["recording"] if cue.get("recording") else None
                if recording and not recording.is_file():
                    raise ValueError(f"The narration recording is missing: {recording}")
                path, _ = speech.take(
                    cue["text"],
                    voice=cue.get("voice", "Serena"),
                    direction=cue.get("direction", "Speak naturally, with warmth and varied emphasis."),
                    language=cue.get("language", "Chinese"),
                    recording=recording,
                    system_voice="Samantha" if cue.get("language") == "English" else "Tingting",
                )
                samples, rate = read_wave(path)
                samples = resample_poly(samples, dsp.SR, rate).astype(np.float32)
                indices = np.flatnonzero(np.abs(samples) > 0.0025)
                if len(indices):
                    samples = samples[
                        max(0, indices[0] - round(dsp.SR * 0.04)) : min(len(samples), indices[-1] + round(dsp.SR * 0.1))
                    ]
                slot = (end - start) / context.fps - 0.55
                if len(samples) / dsp.SR > slot:
                    raise ValueError(
                        f"{spec.get('name', 'Scene')}: narration needs {len(samples) / dsp.SR + 0.55:.1f}s. "
                        "Increase this scene's length or shorten the voice text."
                    )
                at = round(start / context.fps * dsp.SR + 0.3 * dsp.SR)
                peak = max(float(np.max(np.abs(samples))), 0.001)
                dialogue[at : at + len(samples)] += samples * (0.55 / peak)
        finally:
            speech.close()
        activity = uniform_filter1d(np.abs(dialogue), size=max(1, round(0.1 * dsp.SR)))
        mix *= 1 - 0.72 * np.clip(activity / 0.018, 0, 1)[None, :]
        mix += dsp.pan_mono(dialogue)
        limited = dsp.limiter(mix, float(settings.get("audio", "true_peak_db", -1)))
        mix = limited[0] if isinstance(limited, tuple) else limited
    wavfile.write(temporary, dsp.SR, (np.clip(mix.T, -1, 1) * 32767).astype(np.int16))
    temporary.replace(context.sound)
    (context.out / "sound.json").write_text(json.dumps({"signature": context.signature}), encoding="utf-8")
    print(f"Sound: {context.sound}", flush=True)
