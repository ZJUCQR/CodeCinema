<h1 align="center">CodeCinema</h1>

<p align="center">
  <strong>English</strong> · <a href="README.zh-CN.md">简体中文</a>
</p>

<p align="center">
  <a href="https://zjucqr.github.io/CodeCinema/#films">
    <img src="assets/images/banner.jpg" width="100%" alt="CodeCinema filmmaking framework: make your story move, from picture and sound to a finished film">
  </a>
</p>

<p align="center">
  <a href="https://github.com/ZJUCQR/CodeCinema/actions/workflows/ci.yml"><img src="https://github.com/ZJUCQR/CodeCinema/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-2ea44f.svg" alt="License: MIT"></a>
  <a href="#quick-start"><img src="https://img.shields.io/badge/python-3.12%2B-3776ab?logo=python&amp;logoColor=white" alt="Python 3.12+"></a>
  <a href="#quick-start"><img src="https://img.shields.io/badge/ffmpeg-required-007808?logo=ffmpeg&amp;logoColor=white" alt="FFmpeg required"></a>
  <a href="#blender"><img src="https://img.shields.io/badge/Blender-optional-ea7600?logo=blender&amp;logoColor=white" alt="Blender optional"></a>
</p>

<p align="center">
  <a href="https://zjucqr.github.io/CodeCinema/"><strong>Project page</strong></a> ·
  <a href="#quick-start"><strong>Quick start</strong></a> ·
  <a href="#framework">Framework guide</a>
</p>

---

CodeCinema is an extensible, open-source filmmaking framework that brings stories to life with code, combining picture, music and sound into a finished film. Start with a configurable template in the local visual editor, or build your own renderer and production pipeline. Each film is a folder with a `film.toml`; the framework provides:

- **Settings:** one layered configuration per film, with local overrides and environment variables, plus discovery of tools and fonts.
- **Sound:** a shared audio toolkit for synthesis, physical models, reverb, true-peak limiting and loudness.
- **Assembly:** ffmpeg helpers that probe, encode, concatenate and mux.
- **Command line:** one CLI that lists films, runs their steps and starts new ones.

Studio provides a simple path from a template to a finished MP4. The example films demonstrate how to connect custom renderers, sound and post-production.

## ✨ Highlights

- 🪄 **Choose, personalize, render.** The local Studio offers eight animated looks, editable scene cards, titles, captions, colors, three frame shapes and one-click MP4 production. No API key is needed.
- 🧩 **A small contract, any renderer.** A film declares its steps in `film.toml`, and `codecinema run <film> <step>` runs them with that film's settings. Blender, 2D vector drawing, shaders or anything else that writes frames will fit.
- 🎼 **A shared sound toolkit.** The DSP library behind the films is part of the framework: oscillators, plucked-string and modal models, convolution reverb, a true-peak limiter and loudness helpers.
- 🎙️ **Optional expressive voices.** Add spoken lines and acting directions in Studio, or use your own recordings. The [speech guide](#speech) covers the local speech pack and reusable mouth-timing API.
- ♻️ **Reproducible and configurable.** Deterministic renders, resumable parallel jobs, layered settings that never require editing tracked files, and helpers that work on macOS, Linux and Windows.


<a id="quick-start"></a>

## 🚀 Quick start

You need **Python 3.12+**, Git and **FFmpeg** (which includes `ffprobe`). Clone the repository, then expand the commands for your operating system:

```bash
git clone https://github.com/ZJUCQR/CodeCinema.git
cd CodeCinema
```

<details>
<summary>macOS</summary>

install the tools with [Homebrew](https://brew.sh/), then create the environment:

```bash
brew install python@3.12 ffmpeg
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m codecinema studio
```

</details>

<details>
<summary>Linux · Ubuntu 24.04</summary>

install Python 3.12+ and FFmpeg with your distribution's package manager. On Ubuntu 24.04:

```bash
sudo apt-get install python3-venv ffmpeg fonts-dejavu-core libgl1 libegl1 libfontconfig1
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m codecinema studio
```

</details>

<details>
<summary>Windows · PowerShell</summary>

install [Python 3.12+](https://www.python.org/downloads/) and FFmpeg, then run:

```powershell
winget install Gyan.FFmpeg
# Reopen PowerShell after installation, then return to CodeCinema.
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m codecinema studio
```

</details>

These commands use the virtual environment directly. On Windows, replace `-3.12` if you installed a newer Python. Studio opens **http://127.0.0.1:8787/**; keep the terminal running and press `Ctrl+C` to stop.

1. **Choose a look:** click a thumbnail.
2. **Personalize:** enter a film ID, title and caption; choose duration and frame. Defaults are three scenes, 12 seconds and 720p.
3. **Render my film:** watch or download the finished MP4.

Output: **`films/<id>/assets/film/<id>.mp4`**. Quick preview saves a separate 360p video, preserving the master. Reopen it under **My films** to edit; previous settings are backed up in the film’s `out/edits/`.

![Eight starter looks](assets/images/starters.jpg)

For the CLI examples below, activate the environment with `source .venv/bin/activate` (macOS/Linux) or `.\.venv\Scripts\Activate.ps1` (Windows PowerShell). Alternatively, use the environment’s Python path above with `-m codecinema`.

## 🎞 Example films

<table width="100%">
  <tr>
    <td width="50%" valign="top">
      <a href="films/silvergrass/README.md"><img src="assets/images/examples/silvergrass.jpg" width="100%" alt="Duel in the Silver Grass"></a>
      <h3><a href="films/silvergrass/README.md">Duel in the Silver Grass</a></h3>
      <p>A masterless shinobi faces an old sword master in a sea of silver grass, through Blade, Fire and Thunder.</p>
      <p><strong>Blender 3D · 160 s · 30 shots</strong></p>
      <p><a href="https://zjucqr.github.io/CodeCinema/#silvergrass">Watch</a> · <a href="https://github.com/ZJUCQR/CodeCinema/releases/tag/film">Download</a> · <a href="films/silvergrass/README.md">Film guide</a></p>
    </td>
    <td width="50%" valign="top">
      <a href="films/nightrevels/README.md"><img src="assets/images/examples/nightrevels.jpg" width="100%" alt="The Night Revels of Han Xizai, Cat Edition"></a>
      <h3><a href="films/nightrevels/README.md">The Night Revels of Han Xizai, Cat Edition</a></h3>
      <p>A night banquet painted on silk, where every guest is a cat and a kitten painter spies on them.</p>
      <p><strong>Skia 2D · 128 s · 13 cat breeds</strong></p>
      <p><a href="https://zjucqr.github.io/CodeCinema/#nightrevels">Watch</a> · <a href="https://github.com/ZJUCQR/CodeCinema/releases/tag/nightrevels">Download</a> · <a href="films/nightrevels/README.md">Film guide</a></p>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <a href="films/xishen/README.md"><img src="assets/images/examples/xishen.jpg" width="100%" alt="I Am Not the God of Drama: The Opening Trilogy"></a>
      <h3><a href="films/xishen/README.md">I Am Not the God of Drama: The Opening Trilogy</a></h3>
      <p>Chen Ling&#x27;s rain-soaked return, a watching audience and his first directing experiment, following the novel&#x27;s opening chapters.</p>
      <p><strong>Skia 2D · 11 min · 3 episodes · Mandarin speech</strong></p>
      <p><a href="https://zjucqr.github.io/CodeCinema/xishen/watch.html">Watch</a> · <a href="https://github.com/ZJUCQR/CodeCinema/releases/tag/xishen">Download</a> · <a href="films/xishen/README.md">Film guide</a></p>
    </td>
    <td width="50%" valign="top">
      <a href="films/beacon/README.md"><img src="assets/images/examples/beacon.jpg" width="100%" alt="The Last Beacon"></a>
      <h3><a href="films/beacon/README.md">The Last Beacon</a></h3>
      <p>A porcelain keeper rekindles a celestial observatory above the clouds; a distant light answers.</p>
      <p><strong>Blender 3D · 48 s · 6 shots · Original score</strong></p>
      <p><a href="https://zjucqr.github.io/CodeCinema/#beacon">Watch</a> · <a href="https://github.com/ZJUCQR/CodeCinema/releases/tag/beacon">Download</a> · <a href="films/beacon/README.md">Film guide</a></p>
    </td>
  </tr>
</table>

Watch the examples on the [homepage](https://zjucqr.github.io/CodeCinema/#films), download their MP4s from the linked releases, or use `codecinema list` to explore their production steps. SilverGrass and The Last Beacon need Blender 5.2+; 3D rendering takes longer than the 2D examples. The opening trilogy uses the same Skia 2D cast throughout, with a scene-led score and expressive Mandarin voices. Its published speech uses the optional local pack on Apple Silicon; other platforms can supply recordings. Use `--narration off` for a captions-and-music edition. Each film's guide covers setup and customization.


<a id="customization"></a>

## 🎨 Make your own film

```bash
codecinema new myfilm --preset aurora --title "My Film" --render --open
codecinema customize myfilm --preset neon --format portrait --render
codecinema run myfilm all --quality preview
```

Use **Personalize every scene** in Studio to add, remove or reorder scenes and change text, duration, colors and camera moves. Or edit `films/myfilm/scenes.json` directly. Eight looks—`moonrise`, `sunset`, `aurora`, `neon`, `ocean`, `ink`, `cosmos`, `ember`—support landscape, portrait and square frames.

These presets make animated scenic title films. New characters, choreography and story performances need a [custom renderer](#framework).

<details>
<summary>Edit scene JSON</summary>

```json
{
  "version": 1,
  "title": "From Night to Morning",
  "seed": 7,
  "scenes": [
    {"preset": "moonrise", "duration_s": 6, "camera": "wide", "title": "A Quiet Night", "subtitle": "One last look at the stars."},
    {"preset": "sunset", "duration_s": 6, "camera": "drift", "title": "Another Horizon", "subtitle": "There is more to come.", "accent": "#ffdfb5"}
  ]
}
```

Cameras: `wide`, `drift`, `close`. Each scene must last at least 0.5 seconds; total runtime is 1.5–600 seconds. Save, then run `codecinema run myfilm all`. Text wraps to the frame; picture and sound share frame boundaries. Full renders decode and validate the MP4 before reporting success.

</details>


<a id="framework"></a>

## 🧩 Framework development

<details>
<summary>Film contract, settings and shared modules</summary>

```
films/<id>/
├── film.toml          # the manifest: [film] metadata and steps, [settings.*] the film's settings
├── film.local.toml    # optional, git-ignored: personal overrides of [settings]
├── src/
│   └── run.py         # the entry script: `python src/run.py <step> [args]`
├── assets/            # README images; assets/film/ receives the finished video (git-ignored)
└── out/               # generated files (git-ignored)
```

The `[film]` table declares the film’s identity, entry script, steps and requirements. Everything inside `src/` (the story data, the renderer, the score) belongs to the film, so a film can use Blender, 2D vector drawing, shaders, or any other way to produce frames.

### The command line

| Command | What it does |
|---|---|
| `codecinema list` | Lists the films in `films/`, with their titles, steps and requirements |
| `codecinema studio` | Opens the local visual editor for starter projects; `--port` and `--no-open` are optional |
| `codecinema presets` | Lists eight starter looks, formats and quality levels |
| `codecinema run <film> <step> [args…]` | Runs `python <entry> <step> [args…]` inside the film folder, with `CODECINEMA_FILM_DIR` set |
| `codecinema new <id> --render` | Creates and produces a complete starter; accepts title, subtitle, preset, duration, format, quality and accent |
| `codecinema customize <id> --render` | Updates an existing starter, saves previous settings, and renders it again |
| `codecinema check` | Checks the Python packages, ffmpeg and (optionally) Blender |

`python -m codecinema …` is the same as the installed `codecinema` command. A film can also run its steps directly with `python src/run.py <step>` inside its folder.

### Settings

`codecinema.settings` loads the active film's settings in layers, where later layers win:

1. framework defaults (`paths`, `tools`, `fonts`, `video`, `audio`);
2. `[settings.<section>]` tables in `film.toml`;
3. `film.local.toml` (same tables without the `settings.` prefix);
4. environment variables `<ENV_PREFIX>_<SECTION>_<KEY>` or `CODECINEMA_<SECTION>_<KEY>`, plus the aliases `BLENDER_BIN`, `FFMPEG` and `FFPROBE`.

The active film is `$CODECINEMA_FILM_DIR` (the CLI sets it) or the nearest folder above the working directory that contains a `film.toml`.

```python
from codecinema import settings

settings.get("video", "fps")              # a value, coerced to the type of its default
settings.path("paths", "out_dir")         # a path resolved against the film folder
settings.tool("ffmpeg")                   # setting / env -> PATH -> standard install folders -> bare name
settings.font("calligraphy")              # setting / env -> known file names in the OS font folders
settings.ROOT                             # the film folder
```

The module is pure standard library, so it also works inside Blender's Python.

### Shared modules

| Module | Provides |
|---|---|
| `codecinema.audio.speech` / `performance` | Optional local emotional voices, recordings, syllable alignment and waveform-gated mouth shapes; see the [speech guide](#speech) |
| `codecinema.audio.dsp` | Oscillators, noise, envelopes, filters, Karplus-Strong and modal synthesis, resampling, convolution reverb, panning, a compressor, a true-peak lookahead limiter, and loudness helpers. `dsp.SR` is the film's `audio.sample_rate` |
| `codecinema.media` | `probe()`, `encoder()` (raw RGBA frames on stdin, H.264 out), `concat()` and `mux()` |
| `codecinema.procutil` | Cross-platform file locks, process liveness, command lines, free memory, process-group termination and link-or-copy |
| `codecinema.blender` | Headless launching with film settings, assigned action-slot access and temporary modifier suspension; see the [Blender guide](#blender) |
| `codecinema.films` | `discover()` and `Film.run(step, args)`, the logic behind the CLI |

### Renderer extension

- `draw_frame(canvas, frame)` draws one frame with skia.
- `score()` returns the stereo sound track, built with `codecinema.audio.dsp`.
- `plan` and `stills` write a timeline and contact sheet; `render`, `audio` and `assemble` produce the MP4; `qc` verifies metadata and fully decodes it. `all` runs those stages in order.

`--quality preview` uses its own `out/preview/` stages and `<id>_preview.mp4`, preserving the master. Other quality overrides write the master. Use identical quality, format, FPS and duration options across individual stages; signatures prevent assembling stale inputs. Scene boundaries are quantized once to frames, and sound uses the resulting clock. Unsupported font glyphs fail before rendering with a font-selection hint. CLI and Studio customizations save the previous JSON and TOML in `out/edits/`.

`customize` and Studio accept films marked `[film] template = "starter-v1"`. The standalone example films keep their own contracts and guides. A starter can still run directly using `python src/run.py all` inside its folder. New scene types require editing its renderer and palette table; `codecinema/starters.py` holds the shared starter JSON validation and choices.

To grow it into a real film:

1. **Write the story as data first.** Timeline, shots, cue frames, tempo and the score as notes, all in one config module. Keep picture and sound on this shared clock.
2. **Keep the renderer deterministic.** Seed every random choice, so a frame renders the same way every time and a partial re-render matches.
3. **Make motion and sound share a clock.** Actions emit timed events and the audio engine places sounds from them, or the reverse: the score drives the animation of the musicians.
4. **Render in resumable chunks.** Encode frames straight into segments (see `media.encoder`), skip finished ones, and join them at the end with `media.concat`.
5. **Add steps as you need them.** Previews, stills, QC: list them in `steps` and handle them in `run.py`.

</details>


<a id="blender"></a>

## 🎬 Blender

<details>
<summary>Build a Blender production</summary>

CodeCinema includes two Blender productions: [Duel in the Silver Grass](films/silvergrass/README.md) and [The Last Beacon](films/beacon/README.md). Blender is one of the framework's supported renderers. The starter and the opening trilogy use Skia. Each film declares its own renderer and production steps.

Install [Blender 5.2 or later](https://www.blender.org/download/) and follow the [framework installation guide](#quick-start). Standard installation locations and `PATH` are detected. Set `BLENDER_BIN` if Blender is elsewhere.

### Follow the existing production

From the repository root:

```bash
codecinema run silvergrass check
codecinema run silvergrass build
```

The first command checks the toolchain. The second builds the rigged, animated scene without rendering the whole film. See the film's [guide](films/silvergrass/README.md) for rendering and assembly.

| Existing source | Responsibility |
| --- | --- |
| [characters.py](films/silvergrass/src/blender/characters.py) | Two-duelist rigs, IK/FK and anatomical dimensions |
| [character_meshes.py](films/silvergrass/src/blender/character_meshes.py) | Procedural character meshes and materials |
| [poses.py](films/silvergrass/src/blender/poses.py) / [moves.py](films/silvergrass/src/blender/moves.py) | Pose macros, world-space foot planting, gait and fight choreography |
| [secondary.py](films/silvergrass/src/blender/secondary.py) | Cloth, hair and beard response to motion, wind and rain |
| [cameras.py](films/silvergrass/src/blender/cameras.py) | Shot markers, lenses, focus and camera movement |
| [render_setup.py](films/silvergrass/src/blender/render_setup.py) / [render_frames.py](films/silvergrass/src/blender/render_frames.py) | EEVEE settings, color management, motion blur and resumable frame rendering |
| [audio/score.py](films/silvergrass/src/audio/score.py) | Music arranged against the film's action events |

These modules share SilverGrass's two-character configuration, bone conventions, time warps and choreography lanes. Importing its walking or secondary-motion modules directly into an unrelated cast does not create a compatible rig. Its scene design remains inside that film.

### A compact production to learn from

[The Last Beacon](films/beacon/README.md) is a 48-second original short with six shots, an articulated automaton, procedural materials, volumetric clouds, a synthesized score and synchronized Foley. It uses the shared Blender launcher with four readable Python files:

- `story.py`: shot boundaries and shared action/sound cues.
- `scene.py`: scene construction, continuous-time acting, cameras and atomic frame writes.
- `sound.py`: deterministic music, ambience and effects stems.
- `run.py`: source-aware render caching, assembly, full decoding and encoded-audio QC.

```bash
codecinema run beacon still       # inspect six quick frames
codecinema run beacon all         # render, score, assemble and verify
```

This is also a working example of Blender 5.2's compositor node-group and menu-socket API. Its [film guide](films/beacon/README.md#personalize) demonstrates `film.local.toml` overrides for render samples, exposure and character colors.

### Reuse the shared Blender tools

The renderer-neutral launcher and selected Blender utilities extracted from SilverGrass live in [`codecinema.blender`](codecinema/blender.py). Importing this module in ordinary Python does not import `bpy`.

```python
# In films/<id>/src/run.py, with CODECINEMA_FILM_DIR set by the CLI:
from codecinema import blender

blender.run("src/build_scene.py", "--quality", "preview")
```

`run()` uses the active film directory, tool overrides and Blender's background mode. Script arguments follow Blender's `--` separator. Blender script failures return a nonzero exit code. `command()` returns the same argument list for supervisors that manage their own processes; it also accepts `blend=`, `root=` and `executable=`.

Inside a Blender script:

```python
from codecinema.blender import fcurves_of, muted_modifiers

with muted_modifiers(types=("SUBSURF", "ARMATURE", "SOLIDIFY")):
    bake_motion()

for curve in fcurves_of(camera, "location"):
    for key in curve.keyframe_points:
        key.interpolation = "LINEAR"
```

`muted_modifiers()` restores viewport flags even when baking raises an exception; render visibility is unchanged. `channelbag_of()` and `fcurves_of()` use Blender 5.x's assigned action slots, rather than the removed legacy action API. SilverGrass calls these same shared helpers.

[`codecinema.audio.performance`](codecinema/audio/performance.py) is also usable inside Blender. Its `Performance.mouth(time, character)` returns speech activity and syllable shapes from the final recorded take. Use the shot's own time in seconds and the same audio start offset when muxing. Narration and thoughts must not drive a visible character's mouth. See the [speech guide](#speech).

</details>


<a id="speech"></a>

## 🎙️ Voices and mouth timing

<details>
<summary>Expressive speech, recordings and character timing</summary>

The eight starter looks support optional spoken text per scene. Keep the voice text empty for the usual music-only film.

### Use Studio

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

### Edit scene data

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

When you add spoken text, an unchanged previous starter renderer is upgraded automatically; its source is saved alongside the previous scene data in `out/edits/`. A custom renderer is preserved. If it lacks narration support, Studio shows an actionable error instead of silently ignoring the voice text. You can create a new starter and copy the scene data, or merge the narration support into your renderer.

### Reuse voices and mouth timing in a custom renderer

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

See [the opening trilogy](films/xishen/README.md) for a complete production with character voices, alignment, subtitles and media QC.

</details>


<a id="troubleshooting"></a>

## 🔧 Troubleshooting

<details>
<summary>Find a fix</summary>

| Symptom | Fix |
| --- | --- |
| `codecinema` is not found | Use `.venv/bin/python -m codecinema` on macOS/Linux, or `.\.venv\Scripts\python.exe -m codecinema` on Windows |
| A Python package is missing | Run the install command above with the same environment you use to launch Studio |
| FFmpeg or `ffprobe` is missing | Install FFmpeg, reopen the terminal on Windows, then run `python -m codecinema check` |
| Skia cannot load a Linux graphics library | Install `libgl1`, `libegl1` and `libfontconfig1` with your package manager; Studio reports the original loader error |
| Chinese characters are unsupported | Install Noto Sans CJK (`fonts-noto-cjk` on Ubuntu), or set `[fonts] ui = "/path/to/font.ttf"` in the film's `film.local.toml` |
| The ID already exists | Choose a new ID, or select the saved film in Studio; use `customize` from the CLI |
| The port is in use | Run `python -m codecinema studio --port 8788` |
| Assembly says settings differ | Run `all`, or repeat every stage with identical quality, format, duration and FPS options |
| An edit needs undoing | Copy `scenes.json` and `film.toml` from a saved `out/edits/<timestamp>/` back into the film folder, then render again |

</details>


<a id="publishing"></a>

## 📦 Publishing

<details>
<summary>GitHub Releases and the project page</summary>

The homepage plays the finished MP4s attached to parallel film releases:

| Film | Release tag | Finished assets |
| --- | --- | --- |
| Duel in the Silver Grass | `film` | `SilverGrass.mp4` |
| The Night Revels of Han Xizai, Cat Edition | `nightrevels` | `NightRevels.mp4` |
| The Last Beacon | `beacon` | `TheLastBeacon.mp4` |
| I Am Not the God of Drama: The Opening Trilogy | `xishen` | `ep01.mp4`, `ep02.mp4`, `ep03.mp4`, `xishen_complete.mp4` |

Finish rendering and run the film's quality checks before replacing its release
assets. Keep the filenames stable so existing download links continue to work.
Attach finished films only; intermediate clips, frames,
diagnostics and checksum files belong in the local ignored output directory.
Unchanged films already match their release and do not need uploading again.
The film-name tags identify the current published source edition; keep them
aligned with the source commit used for the finished masters.

For the opening trilogy, run from the repository root:

```bash
codecinema run xishen all --narration required --speech-engine local
git push origin main
gh release upload xishen films/xishen/assets/film/ep01.mp4 films/xishen/assets/film/ep02.mp4 films/xishen/assets/film/ep03.mp4 films/xishen/assets/film/xishen_complete.mp4 --clobber
gh release edit film --notes-file films/silvergrass/RELEASE.md
gh release edit nightrevels --notes-file films/nightrevels/RELEASE.md
gh release edit beacon --notes-file films/beacon/RELEASE.md
gh release edit xishen --notes-file films/xishen/RELEASE.md
gh workflow run pages.yml --ref main
```

The trilogy uses Skia throughout. `all` regenerates changed inputs and reuses
completed render chunks only when their source and settings signatures match.

Commit and push any source, poster and webpage updates to `main` first. Upload
all changed finished assets, then run the Pages workflow on `main`. Replacing
an asset does not trigger a release publication event, so dispatch the workflow
explicitly even if the release already exists. Release notes should use the
same specification, downloads and reproduction sections for every example film,
and describe the actual published renderer and edition. Each film's tracked
`RELEASE.md` is the canonical release description; publish it with `--notes-file`
so the repository and GitHub show the same instructions.

The site builder downloads only the expected finished MP4s listed in `site/build.py`, verifies their
sizes and GitHub-provided digests, and versions video URLs using the asset IDs.
Each build starts in a fresh staging directory, so removed files do not survive
from an earlier edition. A completed build replaces the old staging directory.
Incomplete releases fail the build before deployment, keeping the previous
site online. The homepage and screening room receive the same media edition,
including after an episode switch.

To inspect the assembled site locally:

```bash
python3 site/build.py
python3 -m http.server 8080 --directory out/site
```

Custom output directories must be empty or contain a previous CodeCinema site
build marker. Repository source folders are rejected as output paths.

</details>

## 🗂 Project layout

Shared tools live in `codecinema/`; each folder in `films/` owns its story, renderer and production assets.

```text
CodeCinema/
├── codecinema/             # shared filmmaking framework
│   ├── cli.py              # commands and toolchain checks
│   ├── studio.py           # local editor and render jobs
│   ├── studio_assets/      # editor interface and preset thumbnails
│   ├── projects.py         # project creation, edits and backups
│   ├── starters.py         # preset choices and scene validation
│   ├── template/           # source copied into new starter films
│   ├── films.py            # film discovery and step execution
│   ├── settings.py         # configuration, tools and fonts
│   ├── blender.py          # Blender launcher and shared helpers
│   ├── media.py            # FFmpeg encoding and assembly
│   ├── audio/              # synthesis, speech and mouth timing
│   ├── procutil.py         # processes, locks and memory helpers
│   └── diagnostics.py      # dependency checks and setup hints
├── films/                  # independent film projects
│   ├── silvergrass/        # Duel in the Silver Grass
│   ├── nightrevels/        # The Night Revels of Han Xizai, Cat Edition
│   ├── xishen/             # I Am Not the God of Drama: The Opening Trilogy
│   └── beacon/             # The Last Beacon — expanded below
├── assets/images/          # shared branding and README illustrations
├── site/                   # bilingual project page and site builder
├── .github/workflows/      # CI and GitHub Pages deployment
├── README.md               # English setup and framework reference
├── README.zh-CN.md         # Chinese setup and framework reference
├── CONTRIBUTING.md         # contribution guide
└── pyproject.toml          # package metadata and dependencies
```

Inside a film, using [The Last Beacon](films/beacon/README.md) as an example:

```text
films/beacon/
├── film.toml               # film identity, steps, tools and art settings
├── src/                    # this film's production code
│   ├── story.py            # shot timeline and shared picture/sound cues
│   ├── scene.py            # Blender character, scene, animation and cameras
│   ├── sound.py            # music, ambience, Foley and mixing
│   └── run.py              # render, audio, assembly and quality checks
├── assets/
│   ├── images/             # poster and storyboard
│   └── film/               # finished TheLastBeacon.mp4 (generated)
├── out/                    # frames, audio intermediates and reports (generated)
├── docs/FILM_PLAN.md        # creative plan and review criteria
├── README.md               # reproduction and customization guide
├── README.zh-CN.md         # Chinese film guide
└── RELEASE.md              # published edition's release notes
```

`film.toml` tells the framework which script and steps to run; in Beacon it also sets render samples, exposure and character colors. The `src/` layout varies by film: the other examples use their own rendering and audio modules. Starter projects additionally have `scenes.json` for Studio edits. Generated `assets/film/` and `out/` directories are ignored by Git; finished MP4s are available in Releases. Optional personal overrides go in `film.local.toml`.

## 🧭 How it works

![How a CodeCinema film is produced: specification, scene synthesis, rendering, sound and post-production](assets/images/pipeline.svg)

**Figure 1.** How a CodeCinema film is produced. **(a)** The film is written as data: `film.toml` declares its steps and settings, and one config holds the story (timeline, beats, cast, the score as notes). **(b)** The film turns that data into a scene: characters, choreography, cameras, environment and VFX, all keyed on one film clock, and every move emits a timed sound event. **(c)** A renderer draws the frames in parallel, resumable chunks: Blender 3D or Skia 2D painting, depending on the film. **(d)** The score, SFX and ambience are synthesized from the notes and events, then mixed and mastered. **(e)** Titles, picture and sound are assembled sample-accurately and checked. The framework runs every step with the film's settings and supplies the shared settings, sound toolkit and ffmpeg helpers.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, checks and how to add templates or a renderer. The [framework guide](#framework) documents the film contract and shared tools.

## 📜 License

Released under the [MIT License](LICENSE) © 2026 ZJUCQR.
