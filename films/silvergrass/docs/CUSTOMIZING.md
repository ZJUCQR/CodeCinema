# Customizing the film

Every part of the film is generated from code and data. This guide is organised as *what to change → where → how to regenerate*. Commands are run inside `films/silvergrass/` (from the repo root, `codecinema run silvergrass <step>` does the same). After a change you usually only need:

```bash
python src/run.py preview <lane>     # low-resolution preview of one act, a few minutes
python src/run.py all                # rebuild and render incrementally: only shots whose content changed
```

> Conventions: frames start at 1 at 24 fps; units are metres with Z up; the arena centre is the origin. Saku (`SHINOBI_*`) stands on the −Y side facing +Y; Tenkosai (`SAINT_*`) stands on the +Y side facing −Y; the camera stays on the +X side by default (the 180° rule, see [STAGING.md](STAGING.md)).

---

## 1. On-screen text and fonts
- **Text and timing:** `TITLES` in `src/common/config.py`. Each card has `text` (main text), `sub` (small text), `start` / `end` (frames) and `style` (`epigraph` / `main` / `name` / `act` / `end`).
- **Position and layout:** the `LAYOUT` dict in `src/post/titles.py` sets the centre and glyph size per card id.
- **Fonts:** found automatically in the OS font folders and in `assets/fonts/`. To pin a font, create `film.local.toml` in the repo root (git-ignored):
  ```toml
  [fonts]
  calligraphy = "~/fonts/ZhiMangXing-Regular.ttf"   # main title, name cards, act cards
  kaiti = "~/fonts/LXGWWenKai-Regular.ttf"          # epigraph
  ```
  You can also set a font for one run with `SILVERGRASS_FONTS_CALLIGRAPHY` and the like. After switching fonts, run `python src/post/titles.py --check-fonts` to confirm that every character has a glyph.
- **Regenerate:** `python src/run.py titles && python src/run.py assemble`. Titles are overlaid in post, so no re-render is needed.

## 2. Timeline, shots and rhythm
All in `src/common/config.py`:

| Data | Purpose |
|---|---|
| `SHOTS` | Frame range, owning choreography lane and description of each of the 30 shots |
| `ACTS` | The five sections and their default lighting states |
| `HANDOFF` | Position, facing, weapon and costume state of each character where two lanes meet |
| `TEMPO_MAP` / `beat_frame()` | BPM and beat grid per act; the fight lands on the beat |
| `MUSIC_CUES` | Music cue points: main title, first clash, silence, final pass, … |
| `TIME_WARP` | Slow-motion windows; the effects clock `fx_time` slows sparks, rain and grass with them |
| `FULL_WHITE` / `PHOTOSENSITIVITY` | Flash budget (photosensitivity safety) |
| `FADE_TO_BLACK` / `RENDER_SKIP` | Black frames generated in post instead of rendered |
| `STORY_BEATS` | Story beats the build QA checks for in the event list |

When you change a shot's length, move the keyframes in the matching lane as well, and keep the total length consistent with `FRAME_END` (or change `FRAME_END` too).

## 3. Characters
- **Colours:** `PALETTE`, e.g. `shinobi_red` (headband and sash) and `saint_haori` (the haori).
- **Height and proportions:** `SHINOBI_HEIGHT` / `SAINT_HEIGHT`. The skeleton and dimensions are in `src/blender/characters.py`, where `DIMS` holds the sizes of the sword, spear and straw hat.
- **Meshes and materials:** `src/blender/character_meshes.py` builds the costumes, faces, weapons and the "moon over silver grass" crest on the haori.
- **Bone conventions and posing:** see the module docstring of `src/blender/characters.py`. Swords are driven by world-space controllers, so `characters.key_sword(rig, frame, grip, direction)` places a blade at any position and orientation.
- **Inspect:** `src/blender/tools/pose_atlas.py` renders every pose on one sheet; `python src/run.py preview <lane>` shows the characters in their shots.

## 4. Choreography and cameras of an act
Each act is a module `src/blender/acts/<lane>.py` with the entry point `build(ctx)`. The lanes are `prologue`, `act1a`, `act1b`, `act2`, `act3` and `finale`.

- **Shot breakdowns:** `docs/shots/<lane>.md` lists every sub-cut with its frames, camera, lens, action, VFX and events.
- **Motion API:** see the module docstrings of `src/blender/moves.py` and `poses.py`.
  - Poses: `poses.key_pose(rig, frame, name)`.
  - Move macros: `moves.slash / deflect / dodge / jump / roll / spear_thrust ...`.
  - Blade contact: `moves.clash(attacker, defender, frame, point)` makes the two blades meet at a world point, spawns sparks and emits a clash sound event.
- **Cameras:** `cameras.shot(cut_id, f0, f1, keys, lens=..., dof=..., shake=...)`, one camera per sub-cut.
- **Iterate:** `python src/run.py preview act2` builds only that act and renders a low-resolution preview, a contact sheet and an mp4 into `out/lanes/act2/` and `out/previews/`.
- **Rules:** a lane keys only inside its own frame span; entry and exit states must match `HANDOFF`; flashes and slow motion must stay within budget. The build QA checks all of this and writes its results to `out/build_report.json`.

### Adding or replacing a whole act
1. Assign the shots to a new `lane` name in `SHOTS` and add it to `LANES`.
2. Create `src/blender/acts/<new_lane>.py` implementing `build(ctx)`; `acts/_demo.py` is a minimal example.
3. Iterate with `python src/run.py preview <new_lane>`, then run `python src/run.py all`.

## 5. Sky, light, wind and grass
Call these functions of `src/blender/environment.py` from a lane:
- `set_state(frame, state, blend_frames)`: `dusk_gold` (golden sunset), `crimson_fire` (crimson dusk), `storm_night` (thunderstorm) or `moon_clear` (moonlit night). The parameters of each state are in the `STATES` dict.
- `set_sun(frame, azimuth_deg, elevation_deg)`: adjusts the sun or moon per shot.
- `set_wind(frame, strength, direction_deg)`: wind strength and direction.
- `flash(frame, strength)`: lightning illumination; it respects the flash budget automatically.
- `grass_effect('shear' | 'burn' | 'wet' | 'freeze', params, f0, f1)`: cut, scorch, soak or freeze the grass.
- `set_camera_clearance(...)`: the grass-free radius around the camera.

Grass density is a setting: `grass_density_final`, `grass_density_preview` and `grass_density_layout` under `[render]`.

## 6. Visual effects
All effects live in `src/blender/vfx.py`. Each is a fixed-size particle pool driven by the effects clock, so nothing needs baking. The docstrings describe the parameters. The most used ones are:
- `sparks`, `blade_trail`, `flash_ring` (the perfect-deflect ring)
- `fire_ring`, `embers`, `steam` / `smoke`
- `lightning_bolt` (with optional `fork_ends`), `tree_strike` (lightning splits the lone pine)
- `rain` (`time_scale` for slow-motion rain), `rain_split` (the parting rain curtain), `spray_ring` (splash shockwave), `red_mist`

## 7. Music and sound
Sound is driven entirely by `out/events.json`, which the build writes: every move macro emits events, the mixer places sound effects on their frames, and the score's accents are aligned to them.

- **Melodies and modes:** `LEITMOTIFS` (the two leitmotifs "Tenko" and "Saku", written as scale degree, octave offset and beats), `SCALE_IN` / `SCALE_YO`, and the tonic `TONIC_MIDI`.
- **Tempo:** `TEMPO_MAP`.
- **Arrangement:** `src/audio/score.py`, one function per section, e.g. `arr_act1`, `arr_act3`, `arr_epilogue`.
- **Instruments:** `src/audio/instruments.py`: taiko, shime-daiko, hyoshigi, shakuhachi, koto, shamisen, strings, choir, temple bell and heartbeat.
- **Sound effects:** `src/audio/sfx.py` has one generator per event type. Ambience (wind, fire, rain, thunder, insects) is in `src/audio/ambience.py`.
- **Mixing and mastering:** `src/audio/mix.py`. The loudness target and true-peak ceiling come from the `[audio]` settings and can be overridden with `--target-lufs` and `--ceiling`.
- **Audition:** `python src/audio/audition.py` writes audition files for each instrument, sound effect and section to `out/audio/audition/`.
- **Regenerate:** `python src/run.py audio && python src/run.py assemble`. No re-render is needed.

## 8. Render quality and speed
- **Quality:** `samples_final` (default 16), `samples_preview` and `motion_blur` under `[render]`. Use 32 or more for a cleaner image; render time grows roughly linearly with samples. `shadow_pool_mb`, `volumetric_tile` and `volumetric_samples` trade GPU memory and time for quality.
- **Per-shot overrides:** `SHOT_RENDER` in config, e.g. `{"S25": dict(mb_steps=3)}`.
- **Resolution:** `width` and `height` under `[render]` (the render size, 1920×816 by default); the delivery size is `delivery_width` and `delivery_height` under `[video]`. Encoding quality is under `[video]` (`crf`, `preset`, `audio_bitrate`), and the loudness target under `[audio]`.
- **Parallelism:** `slots` under `[render]`, or `python src/run.py render --slots N` for one run. On machines with little memory keep it at 1–2; a slot only starts when `min_free_mem_gb` is available.
- **Partial re-renders:** `python src/run.py render --shots S21-S23`. The supervisor renders incrementally by per-shot content fingerprint, so editing one act re-renders only that act. Changing the render configuration itself (`render_setup.py`, `render_frames.py` or the render settings) re-renders every shot.

## 9. Output
- **Film path:** `final_video` under `[paths]`.
- **Assembly options:** `src/post/assemble.py`, e.g. `--crf`, `--grain` (film grain), `--no-titles`, `--range START END`.
- **Film QC:** `out/final_qc.json` reports photosensitivity flashes, black frames and loudness.

## 10. Settings and environment variables
All machine and taste settings live in `film.toml` under `film.toml [settings]`. They apply in this order, later ones winning:

built-in defaults → `film.toml` → `film.local.toml` (optional, git-ignored; same keys without the `tool.silvergrass.` prefix) → environment variables → `src/run.py` flags

| Section | Keys |
|---|---|
| `[paths]` | `out_dir`, `final_video`, `lock_dir` |
| `[tools]` | `blender`, `ffmpeg`, `ffprobe`, `python` (empty = auto-detect) |
| `[fonts]` | `calligraphy`, `weibei`, `kaiti`, `song`, `ui`, `mono` (empty = auto-detect) |
| `[render]` | size, samples, motion blur, grass density, slots, memory gate, watchdog, … |
| `[video]` | delivery size, codec, quality, preview and review encodes |
| `[audio]` | sample rate, loudness target, true-peak ceiling, QC tolerance |
| `[post]` | title-card workers, title lock timeout |

| Environment variable | Purpose |
|---|---|
| `SILVERGRASS_<SECTION>_<KEY>` | Override any setting, e.g. `SILVERGRASS_RENDER_SLOTS=3`, `SILVERGRASS_VIDEO_CRF=18` |
| `BLENDER_BIN` / `FFMPEG` / `FFPROBE` | Tool paths (common aliases for `SILVERGRASS_TOOLS_*`) |
| `SILVERGRASS_ROOT` | Repository root (detected automatically; rarely needed) |

## Publishing your version
The code is released under the [MIT License](../LICENSE), so you are free to modify and redistribute it. Keep the copyright notice when you publish a derivative, and for commercial use make sure the title fonts you use are licensed for it.
