# The CodeCinema framework

CodeCinema keeps the parts every code-made film needs (settings, sound tools, assembly, a command line) and leaves the creative pipeline to each film. Start with the [simple tutorial](GETTING_STARTED.md) for the visual editor and one-command starters. This reference covers the film contract, settings and shared modules for custom renderers.

## 1. A film is a folder

```
films/<id>/
├── film.toml          # the manifest: [film] metadata and steps, [settings.*] the film's settings
├── film.local.toml    # optional, git-ignored: personal overrides of [settings]
├── src/
│   └── run.py         # the entry script: `python src/run.py <step> [args]`
├── assets/            # README images; assets/film/ receives the finished video (git-ignored)
└── out/               # generated files (git-ignored)
```

The `[film]` table tells the framework how to run the film:

```toml
[film]
id = "myfilm"                       # folder name and CLI name
title = "My Film"
title_zh = ""                       # optional second-language title
description = "One line about the film."
entry = "src/run.py"                # the script that runs the film's steps
env_prefix = "MYFILM"               # MYFILM_<SECTION>_<KEY> environment overrides
steps = ["render", "audio", "assemble", "all"]
requires = ["ffmpeg"]               # informational, shown by `codecinema list`
```

That is the whole contract. Everything inside `src/` (the story data, the renderer, the score) belongs to the film, so a film can use Blender, 2D vector drawing, shaders, or any other way to produce frames.

## 2. The command line

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

## 3. Settings

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

## 4. Shared modules

| Module | Provides |
|---|---|
| `codecinema.audio.speech` / `performance` | Optional local emotional voices, recordings, syllable alignment and waveform-gated mouth shapes; see the [speech guide](SPEECH.md) |
| `codecinema.audio.dsp` | Oscillators, noise, envelopes, filters, Karplus-Strong and modal synthesis, resampling, convolution reverb, panning, a compressor, a true-peak lookahead limiter, and loudness helpers. `dsp.SR` is the film's `audio.sample_rate` |
| `codecinema.media` | `probe()`, `encoder()` (raw RGBA frames on stdin, H.264 out), `concat()` and `mux()` |
| `codecinema.procutil` | Cross-platform file locks, process liveness, command lines, free memory, process-group termination and link-or-copy |
| `codecinema.blender` | Headless launching with film settings, assigned action-slot access and temporary modifier suspension; see the [Blender guide](BLENDER.md) |
| `codecinema.films` | `discover()` and `Film.run(step, args)`, the logic behind the CLI |

A film whose modules import each other by bare name (`import settings`, `import dsp`) can keep doing so with a tiny alias module that points the name at the framework, which is what both examples do:

```python
# films/<id>/src/audio/dsp.py
import os, sys
_HERE = os.path.dirname(os.path.abspath(__file__))
os.environ["CODECINEMA_FILM_DIR"] = os.path.abspath(os.path.join(_HERE, "..", ".."))
...                                   # add the repository root to sys.path
from codecinema.audio import dsp as _m
sys.modules[__name__] = _m
```

## 5. Starting a film

```bash
codecinema new myfilm --preset aurora --title "My Film" --render
codecinema customize myfilm --preset ocean --duration 20 --render
codecinema run myfilm all --quality preview
```

The template defaults to a 12-second, three-scene film with synthesized stereo music. `scenes.json` holds scene order, durations, titles, captions, preset looks, camera modes and optional accent colors. Studio edits the same file; no Python changes are needed for those choices. Presets are `moonrise`, `sunset`, `aurora`, `neon`, `ocean`, `ink`, `cosmos` and `ember`.
- `draw_frame(canvas, frame)` draws one frame with skia.
- `score()` returns the stereo sound track, built with `codecinema.audio.dsp`.
- `plan` and `stills` write a timeline and contact sheet; `render`, `audio` and `assemble` produce the MP4; `qc` verifies metadata and fully decodes it. `all` runs those stages in order.

`--quality preview` uses its own `out/preview/` stages and `<id>_preview.mp4`, preserving the master. Other quality overrides write the master. Use identical quality, format, FPS and duration options across individual stages; signatures prevent assembling stale inputs. Scene boundaries are quantized once to frames, and sound uses the resulting clock. Unsupported font glyphs fail before rendering with a font-selection hint. CLI and Studio customizations save the previous JSON and TOML in `out/edits/`.

`customize` and Studio accept films marked `[film] template = "starter-v1"`. The standalone example films keep their own contracts and guides. A starter can still run directly using `python src/run.py all` inside its folder. New scene types require editing its renderer and palette table; `codecinema/starters.py` holds the shared starter JSON validation and choices.

To grow it into a real film:
1. **Write the story as data first.** Timeline, shots, cue frames, tempo and the score as notes, all in one config module. Both examples derive every frame number from it.
2. **Keep the renderer deterministic.** Seed every random choice, so a frame renders the same way every time and a partial re-render matches.
3. **Make motion and sound share a clock.** Actions emit timed events and the audio engine places sounds from them, or the reverse: the score drives the animation of the musicians.
4. **Render in resumable chunks.** Encode frames straight into segments (see `media.encoder`), skip finished ones, and join them at the end with `media.concat`.
5. **Add steps as you need them.** Previews, stills, QC: list them in `steps` and handle them in `run.py`.

## 6. The example pipelines

| | Duel in the Silver Grass | The Night Revels of Han Xizai, Cat Edition |
|---|---|---|
| Folder | `films/silvergrass/` | `films/nightrevels/` |
| Picture | Blender 5.2 (Python inside Blender, EEVEE), a supervisor rendering per-shot chunks | 2D vector puppets with skia on a procedural silk scroll |
| Sound | Score, SFX and ambience driven by the events emitted by every move | The score as note data drives the playing paws; story events place cat voices and foley |
| Length | 160 s, 3840 frames | 128 s, 3072 frames |
| Full render | Hours (Blender) | About two minutes |
| Guide | [README](../films/silvergrass/README.md), [docs](../films/silvergrass/docs/) | [README](../films/nightrevels/README.md), [plan](../films/nightrevels/docs/FILM_PLAN.md) |

The [opening trilogy](../films/xishen/README.md) adds a longer 2D motion-comic pipeline: 67 shots across three episodes, a sourced character ledger, local emotional speech and aligned dialogue, subtitles, chapters and media/continuity QC. It shares the framework's settings, DSP and FFmpeg helpers while keeping its story-specific renderer separate from the generic starter.

The [Blender guide](BLENDER.md) covers SilverGrass’s production architecture and the reusable renderer tools.
