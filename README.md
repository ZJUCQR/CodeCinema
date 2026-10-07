<h1 align="center">CodeCinema</h1>

<p align="center">
  <strong>Make your story move.</strong><br>
  An open-source filmmaking framework for picture, music, sound and the final cut.
</p>

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
  <a href="docs/GETTING_STARTED.md"><img src="https://img.shields.io/badge/python-3.12%2B-3776ab?logo=python&amp;logoColor=white" alt="Python 3.12+"></a>
  <a href="docs/GETTING_STARTED.md"><img src="https://img.shields.io/badge/ffmpeg-required-007808?logo=ffmpeg&amp;logoColor=white" alt="FFmpeg required"></a>
  <a href="docs/BLENDER.md"><img src="https://img.shields.io/badge/Blender-optional-ea7600?logo=blender&amp;logoColor=white" alt="Blender optional"></a>
</p>

<p align="center">
  <a href="https://zjucqr.github.io/CodeCinema/#films"><strong>Watch the films</strong></a> ·
  <a href="docs/GETTING_STARTED.md"><strong>Quick start</strong></a> ·
  <a href="docs/FRAMEWORK.md">Framework guide</a>
</p>

---

CodeCinema is an extensible framework for making complete films with code. Start with a configurable template in the local visual editor, or build your own renderer and production pipeline. Each film is a folder with a `film.toml`; the framework provides:

- **Settings:** one layered configuration per film, with local overrides and environment variables, plus discovery of tools and fonts.
- **Sound:** a shared audio toolkit for synthesis, physical models, reverb, true-peak limiting and loudness.
- **Assembly:** ffmpeg helpers that probe, encode, concatenate and mux.
- **Command line:** one CLI that lists films, runs their steps and starts new ones.

Studio provides a simple path from a template to a finished MP4. The example films demonstrate how to connect custom renderers, sound and post-production.

## ✨ Highlights

- 🪄 **Choose, personalize, render.** The local Studio offers eight animated looks, editable scene cards, titles, captions, colors, three frame shapes and one-click MP4 production. No API key is needed.
- 🧩 **A small contract, any renderer.** A film declares its steps in `film.toml`, and `codecinema run <film> <step>` runs them with that film's settings. Blender, 2D vector drawing, shaders or anything else that writes frames will fit.
- 🎼 **A shared sound toolkit.** The DSP library behind the films is part of the framework: oscillators, plucked-string and modal models, convolution reverb, a true-peak limiter and loudness helpers.
- 🎙️ **Optional expressive voices.** Add spoken lines and acting directions in Studio, or use your own recordings. The [speech guide](docs/SPEECH.md) covers the local speech pack and reusable mouth-timing API.
- ♻️ **Reproducible and configurable.** Deterministic renders, resumable parallel jobs, layered settings that never require editing tracked files, and helpers that work on macOS, Linux and Windows.

## 🚀 Quick start

```bash
git clone https://github.com/ZJUCQR/CodeCinema.git && cd CodeCinema
python3 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
python -m pip install -e .                             # installs the `codecinema` command

codecinema studio                    # opens the local visual editor in your browser
```

Install **FFmpeg** before rendering. The **[three-step tutorial](docs/GETTING_STARTED.md)** has exact macOS, Linux and Windows setup commands. In Studio, choose a look, enter your words and press **Render my film**. Each film writes its finished video to its own `assets/film/` folder. `python -m codecinema …` works too.

![Eight actual starter looks: moonrise, sunset, aurora, neon, ocean, ink, cosmos and ember](assets/images/starters.jpg)

Prefer a command? Create and produce your first film at once:

```bash
codecinema new myfilm --preset aurora --title "My Film" --render --open
```

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

## 🎨 Make your own film

```bash
codecinema new myfilm --preset sunset --title "My Film" --duration 15 --render
codecinema customize myfilm --preset neon --title "City Lights" --format portrait --render
codecinema run myfilm all --quality preview   # separate preview; preserves the master
```

The starter defaults to **three scenes, 12 seconds and 720p**. Use Studio or edit `scenes.json` to change each scene's look, timing, text and camera motion. Eight looks support landscape, portrait and square frames, with original synthesized music. Earlier settings are saved automatically when you customize.

For a new animation technique, replace `draw_frame()` and `score()` in the generated `src/run.py`, add production steps as needed, and keep technical settings in `film.toml`. The [simple tutorial](docs/GETTING_STARTED.md) covers personalization; the [framework guide](docs/FRAMEWORK.md) covers renderer development.

```toml
# films/myfilm/film.toml
[film]
id = "myfilm"
title = "My Film"
entry = "src/run.py"                    # the script that runs the film's steps
steps = ["render", "audio", "assemble", "all"]

[settings.video]
width = 1920
height = 1080
fps = 24
```

In the film's code, `from codecinema import settings, media` and `from codecinema.audio import dsp` provide the settings, ffmpeg helpers and the sound toolkit. The full guide is **[docs/FRAMEWORK.md](docs/FRAMEWORK.md)**. The [Blender guide](docs/BLENDER.md) and [speech guide](docs/SPEECH.md) show how to reuse the shared renderer and voice tools.

## 🗂 Project layout

```
CodeCinema/
├── codecinema/             # the framework
│   ├── cli.py              # studio | presets | new | customize | list | run | check
│   ├── studio.py           # local visual editor and render jobs
│   ├── studio_assets/      # editor UI and actual preset thumbnails
│   ├── settings.py         # layered per-film settings, tool and font discovery
│   ├── films.py            # film discovery and step running
│   ├── media.py            # ffmpeg: probe, encode, concat, mux
│   ├── blender.py          # headless launching and shared Blender utilities
│   ├── procutil.py         # cross-platform locks, processes, memory
│   ├── audio/
│   │   ├── dsp.py          # synthesis, effects, mixing and mastering
│   │   ├── speech.py       # optional voices, recordings and alignment
│   │   └── performance.py  # reusable dialogue and mouth timing
│   └── template/           # the starter film used by `codecinema new`
├── films/
│   ├── silvergrass/        # example: Duel in the Silver Grass (Blender 3D)
│   ├── nightrevels/        # example: The Night Revels of Han Xizai, Cat Edition (2D)
│   ├── xishen/             # opening trilogy (motion comic, 11 minutes)
│   └── beacon/             # example: The Last Beacon (Blender 3D)
├── docs/                   # the framework guide
├── site/                   # the homepage
└── pyproject.toml          # the package and its dependencies
```

## 🧭 How it works

![How a CodeCinema film is produced: specification, scene synthesis, rendering, sound and post-production](assets/images/pipeline.svg)

**Figure 1.** How a CodeCinema film is produced. **(a)** The film is written as data: `film.toml` declares its steps and settings, and one config holds the story (timeline, beats, cast, the score as notes). **(b)** The film turns that data into a scene: characters, choreography, cameras, environment and VFX, all keyed on one film clock, and every move emits a timed sound event. **(c)** A renderer draws the frames in parallel, resumable chunks: Blender 3D or Skia 2D painting, depending on the film. **(d)** The score, SFX and ambience are synthesized from the notes and events, then mixed and mastered. **(e)** Titles, picture and sound are assembled sample-accurately and checked. The framework runs every step with the film's settings and supplies the shared settings, sound toolkit and ffmpeg helpers.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, checks and how to add templates or a renderer. The [framework guide](docs/FRAMEWORK.md) documents the film contract and shared tools.

## 📜 License

Released under the [MIT License](LICENSE) © 2026 ZJUCQR.
