# __FILM_TITLE__

Open `codecinema studio` and select this project under **My films** to edit scenes,
choose Skia or Blender, add captions or voices and render an MP4.

```bash
codecinema run __FILM_ID__ all
codecinema customize __FILM_ID__ --renderer blender --render
```

`scenes.json` holds the story, shot durations, looks, camera moves and narration.
The root `pyproject.toml` registers the renderer and output settings. Optional
recordings, models and Blender scenes belong in `assets/`. Finished videos go to
`assets/film/`. The generated working files go to `out/`.

This folder needs no Python scripts. CodeCinema owns the production pipeline.
See the repository README for installation and CONTRIBUTING.md for renderer plugins.
