# Add a voice to your film

The eight starter looks support optional spoken text per scene. Keep the voice text empty for the usual music-only film.

## Use Studio

1. Open `codecinema studio`, then **Personalize every scene**.
2. Expand **Add a voice**, write a short line, choose a voice and language, and describe its mood: “warm and curious”, “quiet, a little afraid”, or “calm and thoughtful”.
3. Allow enough scene time, then press **Render my film**. Preview uses a separate MP4.

On an Apple Silicon Mac, install the expressive speech pack once from the repository root:

```bash
python -m pip install -e ".[speech]"
codecinema studio
```

The first spoken render downloads Qwen3-TTS CustomVoice. Later renders reuse cached takes. No API key is needed. The basic framework and music-only starters do not load or download speech models. Plain macOS installations can use a basic system voice; it does not support the acting directions. Expressive local voices currently require Apple Silicon.

Choose a voice appropriate to the language. Serena, Vivian, Dylan, Uncle Fu and Eric are Chinese presets; Ryan and Aiden are English presets; Ono Anna and Sohee are Japanese and Korean presets. The model also supports multilingual speech. Listen to a preview before a long render.

## Edit scene data

Add `narration` to any scene in `scenes.json`:

```json
{
  "name": "Arrival",
  "preset": "aurora",
  "duration_s": 8,
  "camera": "drift",
  "title": "",
  "subtitle": "A little light in the quiet.",
  "narration": {
    "text": "A little light in the quiet.",
    "voice": "Ryan",
    "language": "English",
    "direction": "Warm and curious. Speak naturally, with a gentle pause."
  }
}
```

This object is one scene; put it inside the existing `scenes` array. Then run:

```bash
codecinema run myfilm all --speech-engine local
```

A line that exceeds its scene produces a clear error. Increase the scene length or shorten the line; the starter never silently truncates dialogue. Music automatically becomes quieter while the voice speaks. Text, language, voice and acting directions all affect the take's cache key.

For your own recordings on any platform, put a mono WAV in `films/myfilm/assets/voices/arrival.wav`, set `narration.recording` to `arrival.wav`, and run with `--speech-engine recording`. Supply a recording for every scene with spoken text. Use `--speech-engine system` for macOS's basic voice, or `auto` to choose an installed local engine first.

Existing starter projects retain their entry script so customization does not overwrite a custom renderer. To use new renderer features in an older unmodified starter, create a new starter and copy its `scenes.json` across, or deliberately update its `src/run.py` from `codecinema/template/src/run.py` after saving your changes.

## Reuse voices and mouth timing in a custom renderer

```python
from codecinema.audio.speech import SpeechEngine, ForcedAligner, read_wave
from codecinema.audio.performance import describe, Performance

speech = SpeechEngine("out/voices", engine="local")
try:
    path, _ = speech.take("Where am I?", voice="Ryan", language="English",
                          direction="Quiet and uncertain; a natural question.")
    samples, rate = read_wave(path)
finally:
    speech.close()  # Release the voice model before starting render workers.
```

`ForcedAligner.align(samples, rate, text)` provides Chinese syllable timestamps. Align the final waveform after trimming or time fitting. Release the aligner with `close()` before rendering. The trilogy demonstrates this ordering in `films/xishen/src/sound.py`.

`describe(samples, rate, text=..., speaker="hero", alignment=rows)` creates a small serializable performance record. Save it as JSON and load it with `Performance.load(path)`. At any frame, `performance.mouth(time_in_shot, "hero")` returns a shape (`a`, `o`, `i`, `e`, `f`, `closed`) and opening amount. The default dialogue onset is 0.65 seconds; supply `start` to change it. Give narration or thoughts `speaker=None`, so visible characters stay silent.

The envelope closes the mouth during actual pauses; aligned consonants and vowels distinguish lip shapes. Recordings without syllable timestamps can use the envelope alone, with less phonetic accuracy. Other languages can supply externally aligned timestamp rows using the same `{text, start, end}` schema.

See [the opening trilogy](../films/xishen/README.md) for a complete production with character voices, alignment, subtitles and media QC.
