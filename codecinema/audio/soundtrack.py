"""Scene-timed score, ambience, narration and the master for story projects.

Every scene preset has a musical character (a composer style in the key of its palette) and a quiet ambience bed.
Consecutive scenes with the same preset share one continuous cue; a change of preset crossfades into the next
cue, and a story with several looks carries one theme through all of them.  Narration takes come from the
speech engine and duck the music.  Everything is rendered and mastered by codecinema.audio.mixer; with the
sound bank switched off or unavailable the score uses synthesized instruments, so it works offline.
"""

import json
import os

import numpy as np

from codecinema.audio import dsp
from codecinema.renderers.palettes import PALETTES
from codecinema.workspace import settings

# style, mode, ambience bed and its level for every built-in look (the key comes from the palette root)
PRESET_MUSIC = {
    "moonrise": dict(style="night", mode="dorian", bed="night_crickets", bed_db=-31.0),
    "sunset": dict(style="tender", mode="major", bed="beach_day", bed_db=-30.0),
    "aurora": dict(style="wonder", mode="lydian", bed="snow_forest_night", bed_db=-28.0),
    "neon": dict(style="mystery", mode="dorian", bed=None, lead=["vibraphone", "clarinet"]),
    "ocean": dict(style="lullaby", mode="major", bed="beach_day", bed_db=-26.0),
    "ink": dict(style="tender_chinese", mode="gong", bed="meadow_day", bed_db=-30.0),
    "cosmos": dict(style="underwater", mode="lydian", bed=None),
    "ember": dict(style="playful", mode="major", bed="night_crickets", bed_db=-33.0, variation="light",
                  intensity=0.35),
}
CROSSFADE_S = 1.2


def _key_name(hz):
    """the palette's root frequency -> a key name"""
    midi = int(round(69 + 12 * np.log2(hz / 440.0)))
    return ("C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")[midi % 12]


def _groups(context):
    """[(preset, start_s, end_s)] of consecutive scenes sharing a preset"""
    out = []
    for spec, start, end in context.scenes:
        a, b = start / context.fps, end / context.fps
        if out and out[-1][0] == spec["preset"]:
            out[-1][2] = b
        else:
            out.append([spec["preset"], a, b])
    return [tuple(g) for g in out]


def timeline(context):
    """the audio timeline (codecinema.audio.mixer format) for the story, without narration"""
    from codecinema.audio import composer, theory
    seed = int(context.story.get("seed", 7))
    duration = float(context.duration)
    groups = _groups(context)
    cues, beds = [], []
    themes = {}
    if len(groups) > 1:
        first = PRESET_MUSIC.get(groups[0][0], PRESET_MUSIC["sunset"])
        style = composer.STYLES[first["style"]]
        key = theory.Key(theory.pitch_class(_key_name(PALETTES[groups[0][0]]["root"])), first["mode"])
        beats, compound = theory.meter_beats(style.get("meter", 4))
        themes["film"] = composer.generate_theme(key, beats, compound, 8, style, dsp.rng("film-theme", seed))
    for i, (preset, a, b) in enumerate(groups):
        m = PRESET_MUSIC.get(preset, PRESET_MUSIC["sunset"])
        last = i == len(groups) - 1
        start = 0.0 if i == 0 else max(0.0, a - CROSSFADE_S / 2)
        end = duration if last else min(duration, b + CROSSFADE_S / 2)
        if last and duration >= 8.0:
            end = max(start + 1.0, duration - 0.9)
        cue = {"start": start, "end": end, "style": m["style"], "key": _key_name(PALETTES[preset]["root"]),
               "mode": m["mode"], "intensity": m.get("intensity", 0.55), "seed": seed + i}
        if m.get("variation"):
            cue["variation"] = m["variation"]
        if m.get("lead"):
            cue["lead"] = m["lead"]
        if themes:
            cue["theme"] = "film"
        if i > 0:
            cue["fade_in"] = CROSSFADE_S
        if not last:
            cue["end_with"], cue["fade_out"] = "fade", CROSSFADE_S
        else:
            cue["end_with"] = "ring" if duration >= 8.0 else "fade"
            if duration < 8.0:
                cue["fade_out"] = min(1.0, 0.3 * (end - start))
        cues.append(cue)
        if m.get("bed"):
            beds.append({"start": max(0.0, a - 0.5), "end": min(duration, b + 0.5), "bed": m["bed"],
                         "gain_db": m.get("bed_db", -28.0), "fade": min(1.5, 0.25 * (b - a)), "seed": seed + i})
    return {"duration": duration, "seed": seed, "music": {"themes": themes, "cues": cues}, "ambience": beds,
            "master": {"target_lufs": float(settings.get("audio", "target_lufs", -16.0)),
                       "true_peak_db": float(settings.get("audio", "true_peak_db", -1.0)), "bits": 16,
                       "stems": False}}


def score(context):
    """The mastered stereo score (music and ambience, no narration) as a float array (2, n)."""
    import tempfile
    from codecinema.audio import mixer
    from scipy.io import wavfile
    with tempfile.TemporaryDirectory() as tmp:
        mixer.mix(timeline(context), tmp)
        _, data = wavfile.read(os.path.join(tmp, "mix.wav"))
    return (data.astype(np.float64) / 32768.0).T


def _narration(context, audio):
    """speech-engine takes for scenes with narration, trimmed and placed 0.3 s into their scene"""
    cues = [(spec, start, end) for spec, start, end in context.scenes if spec.get("narration", {}).get("text")]
    if not cues:
        return
    from codecinema.audio.speech import SpeechEngine, read_wave, system_voice
    from scipy.signal import resample_poly

    speech = SpeechEngine(context.film / "out/voices", context.options.speech_engine)
    try:
        for spec, start, end in cues:
            cue = spec["narration"]
            recording = context.assets / "voices" / cue["recording"] if cue.get("recording") else None
            if recording and not recording.is_file():
                raise ValueError(f"The narration recording is missing: {recording}")
            path, _ = speech.take(
                cue["text"],
                voice=cue.get("voice", "Serena"),
                direction=cue.get("direction", "Speak naturally, with warmth and varied emphasis."),
                language=cue.get("language", "Chinese"),
                recording=recording,
                system_voice=system_voice(cue.get("language", "Chinese")),
            )
            samples, rate = read_wave(path)
            samples = resample_poly(samples, dsp.SR, rate).astype(np.float64)
            indices = np.flatnonzero(np.abs(samples) > 0.0025)
            if len(indices):
                samples = samples[max(0, indices[0] - round(dsp.SR * 0.04)): min(len(samples), indices[-1] + round(dsp.SR * 0.1))]
            slot = (end - start) / context.fps - 0.55
            if len(samples) / dsp.SR > slot:
                raise ValueError(
                    f"{spec.get('name', 'Scene')}: narration needs {len(samples) / dsp.SR + 0.55:.1f}s. "
                    "Increase this scene's length or shorten the voice text."
                )
            audio.setdefault("dialogue", []).append({"t": start / context.fps + 0.3, "samples": samples,
                                                     "rate": dsp.SR, "who": "narrator", "pan": 0.0})
    finally:
        speech.close()


def generate(context):
    from codecinema.audio import mixer
    context.out.mkdir(parents=True, exist_ok=True)
    audio = timeline(context)
    _narration(context, audio)
    work = context.out / "soundtrack"
    report = mixer.mix(audio, work)
    os.replace(work / "mix.wav", context.sound)
    (context.out / "sound.json").write_text(json.dumps({"signature": context.signature}), encoding="utf-8")
    print(f"Sound: {context.sound} ({report['lufs']:.1f} LUFS, {report['true_peak_dbtp']:.1f} dBTP)", flush=True)
