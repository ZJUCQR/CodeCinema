# Your first CodeCinema film

[Chinese guide](GETTING_STARTED.zh-CN.md) · [Framework reference](FRAMEWORK.md)

**Install once, open Studio, click Render.** The starter generates the picture, titles, captions, stereo music and a verified MP4 on your computer. No account, API key, Blender or external media is needed for the starter.

![Eight actual starter looks: moonrise, sunset, aurora, neon, ocean, ink, cosmos and ember](../assets/images/starters.jpg)

## 1. Install once

You need **Python 3.12+**, Git and **FFmpeg** (which includes `ffprobe`). Clone the repository:

```bash
git clone https://github.com/ZJUCQR/CodeCinema.git
cd CodeCinema
```

**macOS:** install the tools with [Homebrew](https://brew.sh/), then create the environment:

```bash
brew install python@3.12 ffmpeg
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m codecinema studio
```

**Linux:** install Python 3.12+ and FFmpeg with your distribution's package manager. On Ubuntu 24.04:

```bash
sudo apt-get install python3-venv ffmpeg fonts-dejavu-core
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m codecinema studio
```

**Windows (PowerShell):** install [Python 3.12+](https://www.python.org/downloads/) and FFmpeg, then run:

```powershell
winget install Gyan.FFmpeg
# Reopen PowerShell after installation, then return to CodeCinema.
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m codecinema studio
```

These commands use the environment directly; activation is optional. If you use a newer Python on Windows, replace `-3.12` with its installed version. Studio opens **http://127.0.0.1:8787/**. Keep the terminal running while you use it; `Ctrl+C` stops the server.

## 2. Click your way to a film

1. **Choose a world:** click a thumbnail.
2. **Make it personal:** enter a film ID and title, change the caption, length and frame. Start with 12 seconds and 720p.
3. **Render my film:** wait for the progress indicator, then watch or download the MP4.

The default starter usually takes seconds, depending on your computer. Larger frames and longer timelines take longer. **Quick preview** writes a separate 360p MP4, preserving your existing master. Projects and media stay on your computer.

Your video is saved at **`films/<film-id>/assets/film/<film-id>.mp4`**. To change it later, open Studio again, select it under **My films**, edit and render. Earlier settings are saved in `out/edits/` inside the film folder.

## Make it yours

| Look | Scene | Good for |
| --- | --- | --- |
| `moonrise` | Stars, moon and mountain silhouettes | Quiet openings and personal titles |
| `sunset` | Warm light, islands and reflections | Travel memories and warm endings |
| `aurora` | Northern lights over a forest lake | Dreamlike or mysterious scenes |
| `neon` | Violet skyline with glowing windows | City stories and music intros |
| `ocean` | Turquoise waves and sunlit clouds | Summer messages and relaxed clips |
| `ink` | Misty mountains, birds and a red sun | Poetry and minimalist title films |
| `cosmos` | Ringed planet, orbiting moon and stars | Science-fiction openings |
| `ember` | Fireflies in a twilight forest | Gentle, warm nighttime scenes |

Studio's **Personalize every scene** panel lets you change every caption, scene duration and camera move. You can add scenes, move them up or down, remove them, or combine different looks in one film. The total duration follows the scene cards. **Frame** selects landscape, portrait or square; **accent color** changes the highlight color.

The starter creates animated scenic title films. A new character, choreography or narrative scene needs a custom renderer; see the [framework guide](FRAMEWORK.md) and the [opening trilogy](../films/xishen/README.md) for a longer story with shared characters.

## Prefer one command?

After activating your environment, the installed `codecinema` command supports creation and editing:

```bash
codecinema new myfilm --preset aurora --title "My Film" --render --open
codecinema customize myfilm --preset ocean --title "Summer Days" --duration 20 --render
codecinema customize myfilm --format portrait --quality high --render
codecinema run myfilm all --quality preview
```

`--open` uses your default video player. A new film defaults to 12 seconds, three scenes and 720p. Creation refuses to overwrite an existing film; `customize` updates a starter and saves the previous settings. `python -m codecinema` works with the same arguments.

For hand-edited scenes, change `films/myfilm/scenes.json`, then run `codecinema run myfilm all`:

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

Supported cameras: `wide`, `drift`, `close`. Each scene lasts at least 0.5 seconds; total runtime is 1.5–600 seconds. Text wraps to the frame; missing glyphs produce an actionable font error. Picture and sound share frame-accurate scene boundaries. Full renders validate and decode the MP4 before reporting success.

## If something does not work

| Symptom | Fix |
| --- | --- |
| `codecinema` is not found | Use `.venv/bin/python -m codecinema` on macOS/Linux, or `.\.venv\Scripts\python.exe -m codecinema` on Windows |
| A Python package is missing | Run the install command above with the same environment you use to launch Studio |
| FFmpeg or `ffprobe` is missing | Install FFmpeg, reopen the terminal on Windows, then run `python -m codecinema check` |
| Chinese characters are unsupported | Install Noto Sans CJK (`fonts-noto-cjk` on Ubuntu), or set `[fonts] ui = "/path/to/font.ttf"` in the film's `film.local.toml` |
| The ID already exists | Choose a new ID, or select the saved film in Studio; use `customize` from the CLI |
| The port is in use | Run `python -m codecinema studio --port 8788` |
| Assembly says settings differ | Run `all`, or repeat every stage with identical quality, format, duration and FPS options |
| An edit needs undoing | Copy `scenes.json` and `film.toml` from a saved `out/edits/<timestamp>/` back into the film folder, then render again |

Generated videos, audio and intermediates are ignored by Git. Source code, scene data and documentation can be shared; finished videos can be attached to a GitHub Release.
