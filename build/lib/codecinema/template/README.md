# __FILM_TITLE__

A CodeCinema film, started from the template. The template renders a 6-second sample: a moon rises over layered hills while the title fades in, with a synthesized drone and bell.

```bash
codecinema run __FILM_ID__ all          # or: python src/run.py all  (inside this folder)
```

- `film.toml` names the film, declares its steps and holds its settings.
- `src/run.py` draws the frames (`draw_frame`) and composes the sound (`score`). Replace both with your own film.
- The finished film is written to `assets/film/`.
