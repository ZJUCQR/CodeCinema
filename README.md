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
  <a href="#framework">Framework</a>
</p>

---

CodeCinema is an extensible, open-source filmmaking framework for picture, music, sound and the final cut. Choose a look in the local Studio, personalize your scenes and render an MP4, or create your own production with Blender or another renderer.

## ✨ Highlights

- 🪄 **From a look to a finished film.** Eight animated styles with editable text, colors, timing and camera moves.
- 🎨 **Choose your frame.** Create landscape, portrait or square videos.
- 🎼 **Picture and sound together.** Generate music and effects, with optional voices and recordings.
- 🧩 **Room to create.** Connect Blender, 2D drawing or your own renderer.
- 💻 **Runs locally.** Available on macOS, Linux and Windows. No API key is needed for the core workflow.

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

1. **Choose a look:** click a thumbnail.
2. **Personalize:** enter a film ID, title and caption. Choose duration and frame.
3. **Render my film:** watch or download the finished MP4.

![Eight starter looks](assets/images/starters.jpg)

## 🎞 Example films

<table width="100%">
  <tr>
    <td width="50%" valign="top">
      <a href="films/silvergrass/README.md"><img src="assets/images/examples/silvergrass.jpg" width="100%" alt="Duel in the Silver Grass"></a>
      <h3><a href="films/silvergrass/README.md">Duel in the Silver Grass</a></h3>
      <p>A masterless shinobi faces an old sword master in a sea of silver grass, through Blade, Fire and Thunder.</p>
      <p><a href="https://zjucqr.github.io/CodeCinema/#silvergrass">Watch</a> · <a href="https://github.com/ZJUCQR/CodeCinema/releases/tag/film">Download</a> · <a href="films/silvergrass/README.md">Film guide</a></p>
    </td>
    <td width="50%" valign="top">
      <a href="films/nightrevels/README.md"><img src="assets/images/examples/nightrevels.jpg" width="100%" alt="The Night Revels of Han Xizai, Cat Edition"></a>
      <h3><a href="films/nightrevels/README.md">The Night Revels of Han Xizai, Cat Edition</a></h3>
      <p>A night banquet painted on silk, where every guest is a cat and a kitten painter spies on them.</p>
      <p><a href="https://zjucqr.github.io/CodeCinema/#nightrevels">Watch</a> · <a href="https://github.com/ZJUCQR/CodeCinema/releases/tag/nightrevels">Download</a> · <a href="films/nightrevels/README.md">Film guide</a></p>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <a href="films/xishen/README.md"><img src="assets/images/examples/xishen.jpg" width="100%" alt="I Am Not the God of Drama"></a>
      <h3><a href="films/xishen/README.md">I Am Not the God of Drama</a></h3>
      <p>Chen Ling&#x27;s rain-soaked return, a watching audience and his first directing experiment.</p>
      <p><a href="https://zjucqr.github.io/CodeCinema/#xishen">Watch</a> · <a href="https://github.com/ZJUCQR/CodeCinema/releases/tag/xishen">Download</a> · <a href="films/xishen/README.md">Film guide</a></p>
    </td>
    <td width="50%" valign="top">
      <a href="films/beacon/README.md"><img src="assets/images/examples/beacon.jpg" width="100%" alt="The Last Beacon"></a>
      <h3><a href="films/beacon/README.md">The Last Beacon</a></h3>
      <p>A porcelain keeper rekindles a celestial observatory above the clouds. A distant light answers.</p>
      <p><a href="https://zjucqr.github.io/CodeCinema/#beacon">Watch</a> · <a href="https://github.com/ZJUCQR/CodeCinema/releases/tag/beacon">Download</a> · <a href="films/beacon/README.md">Film guide</a></p>
    </td>
  </tr>
</table>


<a id="customization"></a>

## 🎨 Make your own film

Use Personalize every scene in Studio to add, remove or reorder scenes and adjust text, timing, colors and camera moves. Reopen a saved film whenever you want to edit and render it again.

Starters create animated scenic shorts. Custom characters, choreography and acting can be developed with your own renderer.

<a id="framework"></a>

## 🧩 Framework

Each film owns its story, renderer and assets. The framework supplies shared tools for sound and final assembly. Build on the [example source](films/) to create your own production, with film configuration in the root [pyproject.toml](pyproject.toml).

<a id="blender"></a>

## 🎬 Blender

Install [Blender 5.2 or later](https://www.blender.org/download/) for 3D filmmaking. The [Last Beacon guide](films/beacon/README.md) covers rendering and personalizing a complete production. Studio starters do not require Blender.

<a id="speech"></a>

## 🎙️ Voices and mouth timing

In Studio, expand Add a voice on a scene card to write dialogue, choose a voice and describe its mood. Leave the text empty for music only.

On an Apple Silicon Mac, install the local expressive speech pack from the repository root, then restart Studio:

```bash
.venv/bin/python -m pip install -e ".[speech]"
```

The first spoken render downloads the voice model. No API key is needed. Other platforms can use recordings. The [I Am Not the God of Drama guide](films/xishen/README.md) shows a complete production with voices and character mouth timing.

## 🗂 Project layout

```text
CodeCinema/
├── codecinema/       # framework and Studio
├── films/            # examples and your own films
├── assets/images/    # shared presentation images
├── site/             # project page
└── pyproject.toml    # dependencies and film configuration
```

## 🧭 How it works

![The CodeCinema filmmaking workflow](assets/images/pipeline.svg)

Start with a story and its shots, render the picture, create the music and sound, then bring them together as a synchronized film.

## Contributing

Contributions to looks, Studio and renderers are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

## 📜 License

Released under the [MIT License](LICENSE) © 2026 ZJUCQR.
