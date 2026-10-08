<h1 align="center">CodeCinema</h1>

<p align="center">
  <a href="https://zjucqr.github.io/CodeCinema/"><strong>Project page</strong></a> ·
  <a href="#quick-start"><strong>Quick start</strong></a> ·
  <a href="#framework">Framework</a> ·
  <a href="README.zh-CN.md">简体中文</a>
</p>

<p align="center">
  <a href="https://github.com/ZJUCQR/CodeCinema/actions/workflows/ci.yml"><img src="https://github.com/ZJUCQR/CodeCinema/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-2ea44f.svg" alt="License: MIT"></a>
  <a href="#quick-start"><img src="https://img.shields.io/badge/python-3.12%2B-3776ab?logo=python&amp;logoColor=white" alt="Python 3.12+"></a>
  <a href="#quick-start"><img src="https://img.shields.io/badge/ffmpeg-required-007808?logo=ffmpeg&amp;logoColor=white" alt="FFmpeg required"></a>
  <a href="#blender"><img src="https://img.shields.io/badge/Blender-optional-ea7600?logo=blender&amp;logoColor=white" alt="Blender optional"></a>
</p>

<p align="center">
  <a href="https://zjucqr.github.io/CodeCinema/#films">
    <img src="assets/_shared/images/banner.jpg" width="100%" alt="CodeCinema filmmaking framework: make your story move, from picture and sound to a finished film">
  </a>
</p>

---

CodeCinema is an extensible, open-source filmmaking framework for picture, music, sound and the final cut. Write your story in the local Studio, choose Skia or Blender, and turn your scenes into an MP4 with music and optional voices.

Film folders hold story data. Media lives in the root `assets/<film-id>/` directory. The framework owns the renderers, sound and assembly, so you can make a film without copying or writing production scripts. Developers can add rendering backends through plugins.

## ✨ Highlights

- 🪄 **From a look to a finished film.** Eight animated styles with editable text, colors, timing and camera moves.
- 🎨 **Choose your frame.** Create landscape, portrait or square videos.
- 🎼 **Picture and sound together.** Generate music and effects, with optional voices and recordings.
- 🧩 **Choose your renderer.** Switch between Skia 2D and Blender 3D, use your own Blender scenes, or install a renderer plugin.
- 💻 **Runs locally.** Available on macOS, Linux and Windows. No API key is needed for the core workflow.
- ♻️ **Made for iteration.** Reopen saved projects in Studio or run individual production steps from the command line.

<a id="quick-start"></a>

## 🚀 Quick start

You need **Python 3.12+**, Git and **FFmpeg**. Clone the repository, then expand the commands for your operating system:

```bash
git clone https://github.com/ZJUCQR/CodeCinema.git
cd CodeCinema
```

<details>
<summary>macOS</summary>

Install the tools with [Homebrew](https://brew.sh/), then create the environment:

```bash
brew install python@3.12 ffmpeg
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m codecinema studio
```

</details>

<details>
<summary>Linux</summary>

Install Python 3.12+ and FFmpeg with your distribution's package manager. On Ubuntu 24.04:

```bash
sudo apt-get install python3-venv ffmpeg fonts-dejavu-core libgl1 libegl1 libfontconfig1
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m codecinema studio
```

</details>

<details>
<summary>Windows</summary>

Install [Python 3.12+](https://www.python.org/downloads/) and FFmpeg, then run:

```powershell
winget install Gyan.FFmpeg
# Reopen PowerShell after installation, then return to CodeCinema.
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m codecinema studio
```

</details>

These commands use the virtual environment directly. On Windows, replace `-3.12` if you installed a newer Python. Studio opens **http://127.0.0.1:8787/**. Keep the terminal running and press `Ctrl+C` to stop.

1. **Choose a look:** click a thumbnail to set the film’s starting style.
2. **Personalize:** enter a film ID, title and caption. Choose Skia or Blender, then set duration, frame and picture quality.
3. **Render my film:** watch or download the finished MP4.

![Eight starter looks](assets/_shared/images/starters.jpg)

## 🎞 Example films

<table width="100%">
  <tr>
    <td width="50%" valign="top">
      <a href="films/silvergrass/README.md"><img src="assets/_shared/images/examples/silvergrass.jpg" width="100%" alt="Duel in the Silver Grass"></a>
      <h3><a href="films/silvergrass/README.md">Duel in the Silver Grass</a></h3>
      <p>A masterless shinobi faces an old sword master in a sea of silver grass, through Blade, Fire and Thunder.</p>
      <p><a href="https://zjucqr.github.io/CodeCinema/#silvergrass">Watch</a> · <a href="https://github.com/ZJUCQR/CodeCinema/releases/tag/film">Download</a> · <a href="films/silvergrass/README.md">Film guide</a></p>
    </td>
    <td width="50%" valign="top">
      <a href="films/nightrevels/README.md"><img src="assets/_shared/images/examples/nightrevels.jpg" width="100%" alt="The Night Revels of Han Xizai, Cat Edition"></a>
      <h3><a href="films/nightrevels/README.md">The Night Revels of Han Xizai, Cat Edition</a></h3>
      <p>A night banquet painted on silk, where every guest is a cat and a kitten painter spies on them.</p>
      <p><a href="https://zjucqr.github.io/CodeCinema/#nightrevels">Watch</a> · <a href="https://github.com/ZJUCQR/CodeCinema/releases/tag/nightrevels">Download</a> · <a href="films/nightrevels/README.md">Film guide</a></p>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <a href="films/xishen/README.md"><img src="assets/_shared/images/examples/xishen.jpg" width="100%" alt="I Am Not the God of Drama"></a>
      <h3><a href="films/xishen/README.md">I Am Not the God of Drama</a></h3>
      <p>Chen Ling&#x27;s rain-soaked return, a watching audience and his first directing experiment.</p>
      <p><a href="https://zjucqr.github.io/CodeCinema/#xishen">Watch</a> · <a href="https://github.com/ZJUCQR/CodeCinema/releases/tag/xishen">Download</a> · <a href="films/xishen/README.md">Film guide</a></p>
    </td>
  </tr>
</table>

<a id="customization"></a>

## 🎨 Make your own film

Use Personalize every scene in Studio to shape each shot. Mix different looks within one film, then connect them through captions, pacing and camera movement.

| What to personalize | Available controls |
| --- | --- |
| Renderer | Skia for fast 2D films, Blender for 3D scenes, or an installed plugin |
| Words | Film title, opening caption and individual scene captions |
| Visual style | Moonrise, Sunset, Aurora, Neon, Ocean, Ink, Cosmos and Ember, with your own accent color |
| Scenes and pacing | Add, remove or reorder shots, adjust their length, and choose wide, drift or close camera moves |
| Video format | Landscape, portrait or square frames, with a choice of picture quality |

Reopen a project under My films to keep editing and rendering. The scene cards control captions, timing, looks and camera movement. They create scenic shorts, not automatic character acting from a prose prompt. For custom characters and animation, supply a Blender scene or extend a renderer.

Prefer the terminal? Run these commands from the repository root to create a film and change its visual backend. On Windows, use `.\.venv\Scripts\python.exe` in place of `.venv/bin/python`:

```bash
.venv/bin/python -m codecinema new myfilm --renderer skia --preset aurora --render
.venv/bin/python -m codecinema customize myfilm --renderer blender --render
```

Use `--story path/to/scenes.json` with `new` or `customize` to import a storyline. Explicit title, caption, duration and style options override the imported values. Scene data stays in `films/<id>/`, and media stays in `assets/<id>/`. Backend choices and production settings stay in the root `pyproject.toml`.

<a id="framework"></a>

## 🧩 Framework

The framework separates film content from production code:

- **Content:** scene order, captions, narration, timing and assets belong to each film.
- **Production:** a shared scene clock connects planning, rendered frames, music, speech, assembly and quality checks.
- **Renderers:** Skia and Blender turn scenes into frames through the same interface. Installed plugins appear in `codecinema renderers` and Studio.
- **Production packs:** the three examples retain their authored character designs, choreography and sound in [codecinema/productions](codecinema/productions). Their film folders contain story data, with media in `assets/<id>/`.

The examples use specialized production packs and keep their existing commands. Their choreography cannot be switched automatically between backends. New Studio projects use the shared pipeline and can change renderer without moving their content. Existing projects with custom entry scripts remain runnable.

See [CONTRIBUTING.md](CONTRIBUTING.md#renderer-plugins) for the small renderer interface and plugin registration.

<a id="blender"></a>

## 🎬 Blender

Install [Blender 5.2 or later](https://www.blender.org/download/), then choose **Blender · 3D** in Studio or pass `--renderer blender`. The built-in worlds provide lit scenery and moving cameras. The same scene timeline places captions, music and optional narration.

To use your own characters or animation, save a `.blend` file under `assets/<film-id>/`, for example `assets/<film-id>/scenes/world.blend`. On its scene card, expand Blender scene and enter `scenes/world.blend` and an optional camera name. Paths are relative to that film’s asset directory. Pack external resources in Blender so the project can move between computers. Your scene animation is sampled using its own frame rate.

Start with Quick preview or a few still frames. Blender rendering takes longer than Skia and depends on scene complexity, resolution and hardware. The [Duel in the Silver Grass guide](films/silvergrass/README.md) demonstrates a more elaborate authored production.

<a id="speech"></a>

## 🎙️ Voices

In Studio, expand Add a voice on a scene card to write dialogue, choose a voice and describe its mood, such as “warm and curious” or “nervous but composed.” Allow enough time for each line and listen to a sample before producing a longer film. Leave the text empty for music only.

On an Apple Silicon Mac, install the local expressive speech pack from the repository root, then restart Studio:

```bash
.venv/bin/python -m pip install -e ".[speech]"
```

The first spoken render downloads the voice model. Later renders can reuse existing takes, and no API key is needed. For recorded speech, put a WAV file in `assets/<film-id>/voices/` and set the scene’s `narration.recording` filename and `narration.text` in `scenes.json`. Recordings work on all platforms.

## 🗂 Project layout

The framework and film content have separate homes. Use this map to find the part you want to change:

```text
CodeCinema/
├── codecinema/               # shared framework and local Studio
│   ├── __init__.py             # package version and public convenience imports
│   ├── __main__.py             # python -m codecinema entry point
│   ├── cli/                    # command-line interface
│   │   └── app.py              # commands, arguments and dispatch
│   ├── workspace/              # film content and project management
│   │   ├── paths.py            # workspace and package locations
│   │   ├── registry.py         # film registration and atomic configuration edits
│   │   ├── settings.py         # layered settings, tools and fonts
│   │   ├── films.py            # film discovery and worker launch
│   │   ├── projects.py         # creation, customization and backups
│   │   └── story.py            # scene validation, looks and formats
│   ├── engine/                 # shared production pipeline
│   │   ├── context.py          # validated timeline and render context
│   │   ├── pipeline.py         # planning, picture, sound, assembly and QC
│   │   └── worker.py           # isolated execution for each film
│   ├── runtime/                # external tools and process support
│   │   ├── blender.py          # Blender launch and shared scene helpers
│   │   ├── media.py            # FFmpeg encoding, probing and muxing
│   │   ├── process.py          # processes, locks and memory helpers
│   │   └── diagnostics.py      # dependency checks and setup hints
│   ├── studio/                 # local visual editor
│   │   ├── server.py           # HTTP API and media delivery
│   │   └── jobs.py             # project state and background render jobs
│   ├── renderers/              # Skia, Blender and renderer plugin interface
│   ├── audio/                  # music, effects, speech and performance timing
│   └── productions/            # authored example production packs
│       ├── silvergrass/        # choreography, Blender scenes and post-production
│       ├── nightrevels/        # painted characters, scroll animation and music
│       └── xishen/             # cast, acting, speech timing and episode assembly
├── films/                    # story data and generated working files
│   ├── silvergrass/          # Duel in the Silver Grass
│   ├── nightrevels/          # The Night Revels of Han Xizai, Cat Edition
│   └── xishen/               # I Am Not the God of Drama
├── assets/                   # all media, grouped by film
│   ├── silvergrass/          # Duel in the Silver Grass media
│   ├── nightrevels/          # The Night Revels media
│   ├── xishen/               # episode artwork, recordings and finished MP4s
│   └── _shared/              # resources shared by the framework and website
│       ├── images/           # branding and README illustrations
│       ├── studio/           # editor interface and look thumbnails
│       ├── scaffold/         # starting files for new films
│       └── site/             # website styles, scripts and preview media
├── pyproject.toml            # dependencies and all film configurations
├── CONTRIBUTING.md           # development and contribution guidance
└── LICENSE                   # MIT license
```

Each film uses `assets/<id>/images/` for illustrations and `assets/<id>/film/` for finished videos. Add `voices/`, `scenes/`, `models/`, `textures/` or `fonts/` there when needed. Generated working files remain in `films/<id>/out/`. In configuration, paths beginning with `assets/` are relative to the workspace root. Other relative paths start at the film folder.

## 🧭 How it works

![The CodeCinema filmmaking workflow](assets/_shared/images/pipeline.svg)

1. **Shape the story:** arrange shots, content and pacing.
2. **Make the picture:** the chosen renderer builds scenes, animation and camera movement.
3. **Create the sound:** place music, ambience, effects and optional voices against the shots.
4. **Finish the film:** align picture and sound, then encode a playable MP4.

## Contributing

Improvements to looks, Studio, renderers and documentation are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and checks. Use [GitHub Issues](https://github.com/ZJUCQR/CodeCinema/issues) for bugs and feature ideas, and include a screenshot or short clip when discussing a visual change.

## 📜 License

Released under the [MIT License](LICENSE) © 2026 ZJUCQR.
