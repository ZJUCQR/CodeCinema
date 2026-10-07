# __FILM_TITLE__

A complete starter film with three editable scenes, moving artwork and synthesized stereo music. No API keys or downloaded media are needed.

```bash
codecinema studio                      # visual editor: open this film under My films
codecinema run __FILM_ID__ all          # render, assemble and verify
codecinema run __FILM_ID__ all --quality preview   # separate fast preview
```

Run commands from your project root. The finished MP4 is `assets/film/__FILM_ID__.mp4` in this folder; previews use `__FILM_ID___preview.mp4` and do not replace the master.

## Make it yours

In Studio, choose the film, edit the title, captions, runtime, frame and colors, then click **Render my film**. Expand **Personalize every scene** to add or reorder scenes, mix looks, and change individual captions and camera moves. **Add a voice** accepts optional spoken text, a voice and acting direction; leave it blank for music only. See the [speech guide](../../README.md#speech) for the optional local speech pack and supplied recordings.

The command line works too:

```bash
codecinema customize __FILM_ID__ --preset sunset --title "My Next Film" --duration 20 --render
codecinema customize __FILM_ID__ --format portrait --quality high --render --open
```

- `scenes.json` is your story: each scene has `preset`, `duration_s`, `title`, `subtitle` and `camera` (`wide`, `drift`, `close`). Optional `accent` accepts a color such as `#c5e8db`. Scene durations determine the runtime.
- Eight looks are available: `moonrise`, `sunset`, `aurora`, `neon`, `ocean`, `ink`, `cosmos`, `ember`. Run `codecinema presets` to see them.
- `film.toml` stores picture and audio settings. Local overrides belong in `film.local.toml`, using `[video]`, `[audio]` and `[fonts]` sections.
- `src/run.py` draws each frame (`draw_frame`) and composes the sound (`score`). Edit these only when you want to develop new animation or music.

Every visual or CLI customization saves the previous JSON and TOML in `out/edits/`. Render all after changes, or keep identical options for `render`, `audio`, `assemble` and `qc`; assembly rejects stale or mismatched stages. A storyboard and verification report are saved in `out/master/` (or `out/preview/`).

The [simple tutorial](../../README.md#quick-start) covers installation and your first film. The [framework guide](../../README.md#framework) explains writing a custom renderer.
