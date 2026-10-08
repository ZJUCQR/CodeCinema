# __FILM_TITLE__

Open `.venv/bin/python -m codecinema studio` from the repository root. Select this
project under **My films** to edit scenes, choose Skia or Blender, add captions or
voices and render an MP4.

On Windows, use `.\.venv\Scripts\python.exe` in place of `.venv/bin/python`.
Run these commands from the repository root:

```bash
.venv/bin/python -m codecinema run __FILM_ID__ all
.venv/bin/python -m codecinema customize __FILM_ID__ --renderer blender --render
```

`scenes.json` holds the story, shot durations, looks, camera moves and narration.
The root `pyproject.toml` registers the renderer and output settings. Optional
recordings, models and Blender scenes belong in `assets/`. Finished videos go to
`assets/film/`. The generated working files go to `out/`.

This folder needs no Python scripts. CodeCinema owns the production pipeline.
See the [repository README](../../README.md#quick-start) for installation and
[CONTRIBUTING.md](../../CONTRIBUTING.md#renderer-plugins) for renderer plugins.
