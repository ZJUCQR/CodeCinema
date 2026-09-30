# Lane breakdown — PROLOGUE (S01–S04, frames 1–432)

Owner of the code: `src/blender/acts/prologue.py` (act-implementation agent). This file is the shot breakdown it codes from. Binding sources: `docs/FILM_PLAN.md`, `docs/STAGING.md`, `src/common/config.py` (import it — numbers quoted here are copies for readability; if config changes, config wins). Geometry checks: `out/dev/breakdown/prologue/*.py`.

Status: complete (all sections filled; progress log `out/dev/breakdown/PROGRESS_prologue.md`). Geometry re-checked against the real rig (`characters.rig_template`, `DIMS`, `SPEAR_SLUNG`, `SAYA_PLACE`) and the real `cameras` / `environment` APIs.

## Sub-cut list (hard cuts only)

| cut id | frames | len | lens | camera | purpose |
|---|---|---|---|---|---|
| S01 | 1–96 | 96 | (placeholder = S02 start cam) | none rendered (post makes black) | sound only: wind rises, distant blade ring 40, far thunder 70; epigraph 13–90 |
| S02 | 97–240 | 144 | 20 mm | slow crane push-in, high behind the shinobi, +X offset | the world, the elder waiting, the shinobi walking in from frame bottom; main title 140–236 |
| S03 | 241–336 | 96 | 28 mm | knee-height tracking behind him, tilt up, settled 286 | the man: grass parting, his back, he stops; name card "Saku" 288–334 |
| S04 | 337–432 | 96 | 85 mm | slow push, MCU from slightly +X | the master: head lift under the hat brim (done 378), eye glint 392; name card "Tenkosai" 380–430 |

## 1. Lane summary (span, entering / leaving state, deviations)

- **Span** `config.lane_span("prologue") == (1, 432)`; shots S01 1–96, S02 97–240, S03 241–336, S04 337–432; 4 cuts, all hard. Act `prologue`, env state `dusk_gold` for the whole span. No fight, **0 clashes, 0 flashes, 0 blade trails, no slow motion** (none of `config.SLOWMO` / `TIME_WARP` falls in 1–432, so `fx_time` runs at speed 1.0 throughout).
- **Entering state** (film start, no previous HANDOFF) — key everything at frame 1:
  | who | root (x, y) | facing | pose | states |
  |---|---|---|---|---|
  | shinobi `SHINOBI_rig` | (0.0, −21.30) until 73, walking from 73 | 180 (faces +Y) | `shinobi_walk_saya` cycle (§5) | `characters.set_weapon_state(shinobi, 1, "sheathed")`, `set_arm_mode(shinobi, 1, "fk")` (sword arm pure FK while sheathed), `set_two_hand(shinobi, 1, False)`, `set_kunai_in_hand(1, False)` (kunai 1–3 hidden) |
  | elder `SAINT_rig` | (0.0, 4.0) = `config.SAINT_START` | 0 (faces −Y) | `elder_wait_bowed` (§5) | `set_weapon_state(saint, 1, "sheathed")`, `set_weapon_state(saint, 1, "slung")`, `set_costume(1, haori=True)` (tasuki hidden, thrown haori hidden), `set_hat(1, "on")` (halves hidden), `set_beard_cord(1, False)`, `set_arm_mode(saint, 1, "fk")`, `set_two_hand(saint, 1, False)` |
- **Leaving state = `config.HANDOFF[432]` exactly (no cheat needed at the lane boundary):** shinobi (0.0, −4.5) facing 180, katana sheathed, pose `shinobi_stop_ready` (held since ≈300); elder (0.0, 4.0) facing 0, katana sheathed, hat on, haori on, spear slung, pose `elder_wait_level` (held since 378: neck 0°, **head −13° = chin raised** — needed so the eye clears the real hat brim in S04, see S04; act1a may keep it or ease the head back to neutral in S05, where he is 50 m away). Both hold still-with-breathing to 432 (+2 f handle to 434, same values) so act1a starts from a clean state.
- **Deviations (both intra-lane, none at the boundary):**
  1. **Walk ellipsis at the S02→S03 cut.** SHINOBI_WALK_FROM (0,−20) → SHINOBI_START (0,−4.5) is 15.5 m; walking it continuously between 97 and the stop at ≈290 needs 1.9 m/s (a hurried power-walk, wrong for the character). He walks a measured **1.30 m/s** in both shots and the cut skips ≈4 s of walking: S02 ends at (0,−12.25) @240, S03 starts at (0,−6.96) @241 (+5.29 m along his own path). Invisible: the cut goes from a 20 mm wide where he is a 9 % figure to a 28 mm knee-height view with no positional reference (the elder is hidden in S03, see S03 proof). Implementation: root key @240 CONSTANT (`bl_util.set_key_interp_at`, pipeline rule 2).
  2. **Walk pre-roll inside black S01.** The shinobi walks from frame 73 at (0,−21.30) so he is in full stride and passes `SHINOBI_WALK_FROM` (0,−20.0) exactly at 97 (the first rendered frame). S01 is not rendered.
  3. S01 gets a camera + marker even though it renders black (post) — needed for QA "marker at every shot start" and for `events.finalize` pan/dist of the S01 sound events.
- **Screen direction.** The hard rule starts at 433 (`cameras.check_screen_direction` skips cuts ending before it), but the prologue already obeys it: every camera sits on the +X side of the Y axis (x = +0.10 … +5.5 m); in S02 (both visible) the shinobi is always left of the elder (x −0.69…−0.28 vs +0.03); in S03 only the shinobi is visible and his projected facing points screen-right (+0.17…+0.19); in S04 only the elder, facing screen-left (−0.33).
- **Sun cheats** (`environment.set_sun` compass azimuth, 0 = +Y, 90 = +X; env default for dusk 270°/4°): the sun stays on the −X half of the sky in every cut — backlight from the side opposite the +X cameras: S01/S02 321.9°/4°, S03 290°/5°, S04 315°/5° (act1a's S05 then has it at −X between the fighters). Wind heading 250° throughout.
- **Build order for `acts/prologue.py::build(ctx)`:** (1) states at frame 1 (table above); (2) env calls per cut (`set_state`, `set_sun`, `set_wind`, `set_camera_clearance`); (3) shinobi: walk 73→240, walk 241→290 + stop, `shinobi_stop_ready`, breathing; (4) elder: `elder_wait_bowed` 1→347, head-lift keys, `elder_wait_level`, breathing; (5) cameras S01–S04 (+ the S03 float); (6) `S04_eye_glint` placement (needs the head keys) and the optional fill; (7) events; (8) CONSTANT at the 240 teleport, `bl_util.freeze_handles` on everything keyed.

## 2. Beat grid for the span

The prologue is **free time** — no `config.TEMPO_MAP` section covers 1–432 (act1 starts at 631), so nothing is locked to a beat grid. Locks are to `config.MUSIC_CUES` and to the free-time placements `src/audio/score.py::arr_prologue` makes from those cues (read, not edited):

| frame | source | what the picture does there |
|---|---|---|
| 1 | `MUSIC_CUES["prologue_start"]` | black; wind rises out of silence (ambience ramps over 3.2 s automatically) |
| 13–90 | `TITLES["epigraph"]` | black + epigraph (post) |
| 40 | this lane | distant blade ring (sound only) |
| 70 | this lane | far thunder (sound only) |
| 97 | cut S01→S02 | hard cut from black to the sunset sea (no fade — the jump is the opening accent) |
| **179** | `MUSIC_CUES["title"]` = main_title.start + 39 (seal stamp; score: temple bell + soft low odaiko) | the title seal lands; the shinobi is mid-frame lower-left, 10 f before he crosses the arena edge (r = 15 m) at 189 — no picture event is forced onto 179 |
| 211, 258, 276, 306, 314, 347 (–404) | score: shakuhachi Tenko motif, rubato, starts title + 1.35 s | soft sync only: the S03 stop step (≈288) sits between notes 276 and 306; the long last note 347–404 carries the whole S04 head lift 347–378 |
| **337** | cut S03→S04; score: odaiko at S04.start + 0.1 s (≈339) | the cut to the elder lands on the drum |
| **392** | score: koto note at S04.start + 55 f ("the eye glint") | eye glint peak **must stay on S04.start + 55 = 392** |

For reference only (act1a may count in from it): the act-I 92-BPM grid extrapolated backwards from its anchor 631 (`beat_frame("act1", b)`, b < 0) gives 318, 334, 349, 365, 381, 396, 412, 428 for b = −20 … −13 — nothing in the prologue is placed on these.

## 3. Sub-cuts

Conventions in every block: NDC x −1 (left) … +1 (right), y −1 (bottom) … +1 (top) of the 1920×816 picture; "size" = % of frame height; pinhole with `sensor_fit='HORIZONTAL'`, 36 mm (as `bl_util.new_camera`), so the vertical half-extent is 7.65 mm. Heights from `characters.rig_template`: shinobi head centre 1.61 m, head top 1.72 m; elder head centre ≈1.74 m, hat top ≈1.86 m (bowed) / 1.875 m (rest), slung spear's upper end 2.37 m. Camera keys are `(frame, location, look_at, lens)` for `cameras.shot` (look-at points are just aim points on the lens axis). Heights of the grass: field (r > 15 m) 1.1–1.5 m, arena (r < 15 m) 0.95–1.15 m.

### S01 — 1–96 (black, sound only)

- **Purpose:** before any image the audience hears the field: wind rising out of silence, one distant blade ring (someone out there waits with a blade), far thunder (Act III planted). The epigraph (13–90) is read over black.
- **Camera:** `cameras.shot("S01", 1, 96, keys=[(1, (5.500, -26.000, 3.600), (1.397, -6.589, 6.127), 20)], lens=20, framing="wide", subjects=[])` — a static clone of S02's first key. **Never rendered** (`config.RENDER_SKIP` (1, 96); post writes black + epigraph). It exists for the QA "marker at every shot start" and so `events.finalize` computes pan/dist of the S01 sounds from the same place S02 opens. No DOF, no shake. Screen check (QA only): f1 shinobi head (−0.90, −1.30) = below frame, elder head (+0.03, −0.50) 8.1 % full figure; f96 shinobi (−0.69, −1.12) below frame, elder unchanged → shinobi_x < elder_x ✓, camera x = +5.5 ✓.
- **Action:** shinobi root (0.0, −21.30) facing 180 keyed at 1 and held; his walk starts at 73 (one `moves.walk` call 73→240, see S02). Elder `elder_wait_bowed` at (0.0, 4.0) facing 0 from frame 1, breathing only.
- **Clashes:** none (the blade ring is sound only).
- **Environment:** `set_state(1, "dusk_gold", blend_frames=0)`; `set_sun(1, 321.9, 4.0)` (= the S02 values, below); `set_wind(1, 1.2, direction_deg=250.0)` so the field is already moving at 97 (the audio's wind ramp is independent). Scale of `environment.set_wind`: 1.0 = default breeze, 2 = gale; heading = compass bearing the wind blows TOWARD (0 = +Y, 90 = +X). Heading 250° (toward −X, slightly −Y) is used for the whole prologue: it streams the shinobi's tails and the elder's beard toward screen-left in S02–S04 (into the empty side of each frame) and rolls the S02 waves right→left. No `flash` (black, and the storm is far away).
- **VFX:** none.
- **Events** (emit with `events.emit`; the camera for pan is the S01 marker camera):

  | frame | type | attrs | note |
  |---|---|---|---|
  | 1 | `music_cue` | `cue="prologue_start"` | |
  | 28 | `wind_gust` | `strength=0.45` | first gust out of silence |
  | 40 | `clash` | `strength=0.6, pos=(0.0, 70.0, 1.5), tags=["distant", "omen"]` | the distant blade ring; dist ≈ 96 m, pan ≈ +0.15. Emit directly — NOT `moves.clash` (no blades, no sparks) |
  | 70 | `thunder` | `distance="far", pos=(-900.0, 2600.0, 500.0), tags=["distant", "omen"]` | far roll; dist ≈ 2.8 km, pan ≈ −0.12 |
  | ≈73, ≈86 | `step` | from `moves.walk` (`who="shinobi"`, surface grass) | faint footsteps under the black |
  | 84 | `wind_gust` | `strength=0.55` | swells into the cut at 97 (ambience gust peaks ≈0.8 s after the event) |
- **Notes:** never type/tag the 40 ring as `blade_ring` (that cue is S25's 3277). The 70 thunder is the film's first `thunder` event — see Risk R6 (audio cue derivation).

### S02 — 97–240 (extreme wide, crane push-in, main title)

- **Purpose (144 f, one long take — a stillness beat):** the world and the stakes in one image. An endless silver-grass sea at golden sunset rolling in wind waves, sky dominant; a tiny figure waiting at the centre (straw hat, spear slung diagonally — the elder); the lone pine on its rise (paid off in S21); a second figure rises into frame from the bottom-left and walks toward him (the shinobi). The title writes itself into the sky (140–236).
- **Camera:** crane push-in, 20 mm, LINEAR location (already moving at the cut, still moving at 240 — no ease at either end), fixed pitch **+7.26°** (eye-level horizon locked at NDC y −0.333 = 2/3 down), roll 0, no DOF (deep focus), no shake.
  ```python
  cameras.shot("S02", 97, 240, lens=20, framing="wide", subjects=["saint"], interp="LINEAR", keys=[
      (97,  (5.500, -26.000, 3.600), (1.397, -6.589, 6.127), 20),
      (168, (5.093, -24.014, 3.302), (1.021, -4.597, 5.830), 20),
      (240, (4.680, -22.000, 3.000), (0.639, -2.576, 5.527), 20)])   # last key CONSTANT (automatic)
  ```
  (`subjects=["saint"]` because the shinobi is legitimately below frame at 97 — `framing_qa` checks first/last frames.) = a 4.10 m push along the lens axis (yaw 11.9° left of +Y, 0.69 m/s) + 0.60 m crane-down. The elder grows 30.0 → 26.0 m (+15 %) — slow.
- **Framing proof** (`out/dev/breakdown/prologue/s02_final.py`):

  | frame | shinobi head (x, y) | shinobi above grass | elder head (x, y) / hat top y / spear top (x, y) | elder above grass: to hat top / to spear top | pine base / 9 m top y | sun | horizon y |
  |---|---|---|---|---|---|---|---|
  | 97 | (−0.69, −1.12) below frame | — | (+0.030, −0.497) / −0.486 / (+0.019, −0.439) | 3.3 % (27 px) / 5.6 % (45 px) | (+0.25, −0.39) / +0.04 | (−0.55, −0.13) | −0.333 |
  | 115 | head top crosses the bottom edge at (0, −19.03): **walks in from the bottom of frame** | | | | | | |
  | 179 | (−0.41, −0.83) | 6.3 % | (+0.030, −0.478) / −0.466 / (+0.018, −0.416) | 3.6 % / 6.0 % | | | −0.333 |
  | 240 | (−0.28, −0.69) | 8.6 % (arena, waist-high grass) | (+0.030, −0.461) / −0.449 / (+0.018, −0.395) | 3.8 % (31 px) / 6.4 % (52 px) | (+0.26, −0.36) / +0.10 | (−0.55, −0.13) | −0.333 |

  (Elder heights from the real rig: bowed hat top ≈1.86 m, slung spear's upper end (−0.366, 4.325, 2.373) from `characters.SPEAR_SLUNG`; grass line 1.10 m.) 180°: shinobi x (−0.69 … −0.28) < elder x (+0.03) at every frame; camera x +4.68 … +5.50 ✓. He walks a diagonal from the lower-left toward the centre. At final resolution the elder is a 27–31 px figure above the grass with the spear's sheathed end standing 18–21 px higher, off his right shoulder (screen-left), hat ≈22–25 px wide — hat + diagonal spear read as a shape; the shinobi is head, shoulders and streaming red hachimaki tails above the grass (0.4–0.7 m visible), his wake of parted grass behind him. Grass clearance: the nearest grass visible along the bottom edge (bottom ray −13.67°) is 8.6 m (97) → 6.2 m (240) from the lens, both characters ≥ 6.7 m away → nothing inside the 1.5–4 m clearance zone is visible; keep the default radial clearance. Title room: main_title ink x −0.43…+0.43, y −0.10…+0.48, seal (+0.50, +0.055); the elder's hat top (≤ −0.45) and spear top (≤ −0.40) are ≥ 0.30 below the ink, the shinobi lower still; the sun lies outside the title backdrop ellipse ((−0.55/0.533)² + (−0.32/0.436)² = 1.60 > 1). The pine (if taller than ≈6.5 m above its base) reaches behind the two lower-right title glyphs during 140–236 — accepted: the white calligraphy on its dark backdrop reads over a dark pine, and the pine is seen clean 97–139.
- **Action:**
  - shinobi: `moves.walk(SHINOBI_rig, 73, 240, (0.0, -21.30), (0.0, -12.25))` → 9.05 m / 167 f = **1.30 m/s**, step 0.70 m, ≈12.9 f per step; facing 180; root LINEAR (if `walk()` eases in/out, re-key the root with `key_root(..., interp="LINEAR")` at 73 and 240). Upper body: overlay `shinobi_walk_saya` (§5: left hand resting on the saya at the guard, right arm swings ±12°, head level on the elder). Passes (0, −20.0) at 97, crosses the arena edge y = −15 at ≈189. Root key @240 **CONSTANT** (the S03 ellipsis). Katana sheathed, one-handed nothing (no weapon use).
  - elder: static `elder_wait_bowed` at (0.0, 4.0) facing 0, breathing only (`_local_breath`, chest X ±0.6°, period 80 f); beard, beard cord, haori hem and sleeves move by `characters.apply_secondary_motion` (wind).
- **Clashes:** none.
- **Environment:**
  - `set_sun(97, 321.9, 4.0)` — compass azimuth (0 = +Y, 90 = +X, as `environment.set_sun` defines), elevation 4°; direction toward the sun (−0.616, 0.785, 0.070), i.e. 38.1° left of +Y (the env default for dusk is 270°/4°). Keep the dusk disk size (2.2°, ≈43 px). Acceptance: the disk renders at NDC ≈ (−0.55, −0.13), just above the horizon, left of the title and outside its backdrop.
  - `set_wind(f, strength, direction_deg=250.0)`: 97 → 1.2, 116 → 1.6 (gust), 140 → 1.2, 169 → 1.5 (gust), 200 → 1.2, 240 → 1.2 (visual gusts peak ≈19 f after the audio `wind_gust` events so picture and sound swell together). The waves must read from 97; heading 250° rolls them right→left across the frame.
  - no `flash`, no `grass_effect` (default parting around both rigs; default camera clearance near 1.5 / far 4.0).
- **VFX:** none required. (Optional polish, only if vfx grows a slow-drift mode: 20–40 plume seeds drifting through the backlight in the upper-left sky 97–240, speed ≤ 0.8 m/s — never in front of the title glyphs.)
- **Events:**

  | frame | type | attrs |
  |---|---|---|
  | 97 | `wind_gust` | `strength=0.7` (the cut lands on a rising gust) |
  | ≈99 … ≈239 | `step` | from `moves.walk` (`who="shinobi"`, grass; they are 7–10 m from the lens → quiet) |
  | 150 | `wind_gust` | `strength=0.6` |
  | 179 | `music_cue` | `cue="title"` (seal stamp: bell + low odaiko in the score) |
- **Notes:** no slow motion; no DOF; the elder must not move. The cut in from black at 97 is hard (no fade). Nothing important below the grass line (his hands and scabbard are under it in the field).

### S03 — 241–336 (knee-height tracking, tilt up to his back, name card "Saku")

- **Purpose (96 f, one take):** the man, felt before he is seen: knee-height behind him, his grey hakama legs and red sash push through waist-high grass that parts around him (the grass carries the shot), the black scabbard swaying at his left hip; the camera tilts up his back to the head and the streaming red hachimaki tails against the sky as he takes a last step and stops (settled 286–290). Name card "Saku / the masterless shinobi" lower-left 288–334 while he stands, facing where the elder waits (the elder is deliberately hidden — S04 is his reveal).
- **Camera:** tracking (steadicam float) at knee height 0.48 → 0.61 m, 28 mm, f/2.8. Location follows his root with a smooth distance 1.90 → 2.02 m, almost on his line (x +0.18 → +0.10, so his body masks the elder, see proof); tilt / rise / yaw ease over 256→286 (`u = smoothstep((f-256)/30)`: pitch 6.0° + 14.3°·u, yaw 11.0° − 1.2°·u left of +Y, x 0.18 − 0.08·u, z 0.48 + 0.12·u); forward travel stops with him at 290; 290→336 a 0.08 m creep-in (breath). Key it densely (these keys with Bezier auto-clamped handles, or every frame from `out/dev/breakdown/prologue/s03_keys.py`):
  ```python
  cam = cameras.shot("S03", 241, 336, lens=28, framing="close", subjects=["shinobi"], keys=[
      (241, (0.180, -8.860, 0.480), (-0.294, -6.419, 0.741), 28),   # pitch  6.0 yaw 11.0 | him y -6.960, d 1.90
      (256, (0.180, -8.047, 0.480), (-0.294, -5.607, 0.741), 28),   # pitch  6.0          | him y -6.147 (tracks 1.30 m/s)
      (262, (0.172, -7.735, 0.492), (-0.296, -5.301, 0.818), 28),   # pitch  7.5
      (268, (0.152, -7.440, 0.522), (-0.299, -5.028, 1.001), 28),   # pitch 11.0
      (274, (0.128, -7.150, 0.558), (-0.300, -4.777, 1.216), 28),   # pitch 15.3
      (280, (0.108, -6.855, 0.588), (-0.300, -4.524, 1.394), 28),   # pitch 18.8 | he decelerates from here
      (286, (0.100, -6.590, 0.600), (-0.299, -4.280, 1.467), 28),   # pitch 20.3 | tilt settled
      (290, (0.100, -6.520, 0.600), (-0.299, -4.209, 1.467), 28),   # travel stops with him (d 2.02)
      (336, (0.100, -6.440, 0.610), (-0.299, -4.129, 1.477), 28)],  # 0.08 m breath-in; last key CONSTANT (auto)
      dof=dict(focus=(shinobi_rig, "chest"), fstop=2.8))
  bl_util.add_shake(cam, 241, 292, amp_deg=0.35, scale=6.0, blend=8, seed=zlib.crc32(b"S03:float"))  # walk float, gone by 292
  ```
  (`cameras.shot`'s own `handheld=` runs over the whole cut without a blend-out, hence the direct `add_shake`.) DOF at 2 m, 28 mm f/2.8: sharp 1.65–2.55 m (him); near blades and the sky soft.
- **Framing proof** (`s03_keys.py`; body points on his root line x = 0):

  | frame | head (x, y) | head top y | shoulders L/R (x, y) | sash y / hips y | shin (0.25 m) y / foot y | size head-top→hips | facing·right |
  |---|---|---|---|---|---|---|---|
  | 241 | (+0.14, +1.69) above frame | +1.88 | (−0.02, +1.32)/(+0.31, +1.39) above | +0.54 / +0.44…+0.47 | −0.84 / **−1.24 (below frame)** | 73 % | +0.19 |
  | 262 | (+0.15, +1.54) above | +1.72 | above | +0.42 / +0.31…+0.34 | −0.96 / −1.37 | 72 % | +0.19 |
  | 274 | (+0.16, +0.84) entering | +1.00 | (+0.01, +0.51)/(+0.32, +0.57) | −0.22 / −0.30…−0.32 | out | 67 % | +0.18 |
  | 286 | (+0.17, +0.41) | +0.57 | (+0.03, +0.10)/(+0.33, +0.15) | −0.64 / −0.72…−0.74 | out | 66 % | +0.17 |
  | 336 | (+0.17, +0.46) | +0.62 | (+0.02, +0.13)/(+0.33, +0.18) | −0.63 / −0.71…−0.73 | out | 68 % | +0.17 |

  Opening frame = mid-shins to lower back (sash in the upper third, feet below the bottom edge); end frame = hips to head with ≈0.2 of sky above, body x +0.02…+0.35 (centre-right), leaving the left 60 % for the card, grass and sky. 180°: single character; his projected facing points screen-right (+0.17…+0.19) = consistent with "shinobi faces right"; camera x +0.18 → +0.10 (+X side). (`cameras.check_screen_direction` skips cuts ending before 433 anyway.) **The elder stays hidden the whole shot** (S04 is his reveal, and the S02→S03 ellipsis gets no reference). With the real rig numbers (hat top ≈ (0, 3.87, 1.86) bowed; slung spear's upper end (−0.366, 4.325, 2.373) from `characters.SPEAR_SLUNG`) the rays lens→hat top and lens→spear top cross the shinobi's plane at 0.69–0.93 m height and lateral +0.15 → +0.01 m, i.e. inside his hips/hakama silhouette (half-width ≥ 0.19 m) at every frame, and additionally run through 0.25–3.0 m of uncleared arena grass. Projected if nothing occluded: hat (+0.28, +0.02) → (+0.26, −0.87), spear top (+0.23, +0.14) → (+0.20, −0.71) — behind him on screen too.
- **Grass (the shot's texture — env call):** the default radial camera clearance (1.5–4 m) would mow everything around him, so switch to the front-cone mode for this cut (`environment.set_camera_clearance`, CONSTANT keys):
  ```python
  environment.set_camera_clearance(241, near=0.25, far=0.35, cone_deg=24, cone_len=1.25)   # walk: blades at the edges
  environment.set_camera_clearance(276, cone_deg=24, cone_len=1.25, interp='LINEAR')
  environment.set_camera_clearance(288, cone_deg=31, cone_len=1.25)                        # card: clean left side
  environment.set_camera_clearance(337, near=1.5, far=4.0, cone_deg=0)                     # S04: back to default
  ```
  Meaning: only blades inside a cone of half-angle `cone_deg` around the view axis and within 1.25 m of the lens are scaled to 0 (plus the tiny 0.25–0.35 m radial sphere, if the cone mode keeps it, so nothing crosses the lens); everything else stays full height. From 1.1 m on, his own parting (radius ≈0.8 m around `SHINOBI_rig`) takes over, so the lens sees a channel he opens; the near blades outside the cone make soft vertical strokes at the frame edges during the walk (|x| > 0.69), pushed out to |x| ≳ 0.94 by the wider cone before the card appears. Turn the parting **wake** on if env has it (the channel stays open ≈1.5 m behind him). The uncleared bent stems at his shins keep the feet unseen even at the bottom edge. If the API differs, the intent is: *no clearance bowl around him, a clean line of sight lens→him, blades at the edges*.
- **Action (shinobi, facing 180 throughout):**
  - root: jump-cut from (0.0, −12.25) @240 to **(0.0, −6.96) @241**; LINEAR to (0.0, −4.846) @280 (1.30 m/s), then the stopping step decelerates (cubic Hermite, start slope 0.0542 m/f, end slope 0) to **(0.0, −4.50) @290** and holds.
  - legs: `moves.walk(SHINOBI_rig, 241, 290, (0.0, -6.96), (0.0, -4.50))` with the cycle **mid-stride at 241** (no standing start — he has been walking); contacts ≈241, 254, 267, 280; the last step is shorter (0.25 m) and plants at **288**, the trailing foot closes to ≈0.28 m stance width by 290. If `walk()` cannot start mid-stride / ease the last step, key its root as above with `key_root` and use the local `_local_walk_stop` (§5) for 280–290.
  - upper body: `shinobi_walk_saya` overlay (left hand on the saya at the guard, thumb on the tsuba — seen screen-left of his hips; right arm swing ±12°) until 288; 288–296 the right arm settles to hang; then `shinobi_stop_ready` (§5) 290–300: hips sink 1.5 cm, shoulders square and drop 1 cm, head lifts 3° to look at the elder (300); breathing (chest X ±0.8°, period 72 f) from 300 to 432 (he is off-screen in S04 but keep him alive).
  - katana sheathed, no two-handed grip (no weapon use); hachimaki tails stream (secondary motion, wind).
- **Clashes:** none.
- **Environment:**
  - `set_sun(241, 290.0, 5.0)` (compass): toward the sun (−0.936, 0.341, 0.087) = 70° left of +Y — ≈60° off the lens axis, i.e. out of frame (half-FOV 32.7°): a warm raking back-light from his left, rim down the screen-left edge of his back/head/tails, plumes glowing on the left, sky brighter toward screen-left. (The S02 sun at 321.9° would sit on this frame's left edge and slide under the name card as the camera tilts up — hence the cheat.)
  - `set_wind(f, strength, direction_deg=250.0)`: 241 → 1.1, 300 → 1.1, 319 → 1.5 (gust, after the audio gust at 300), 336 → 1.2 — heading 250° is ≈100° left of this lens axis (compass ≈350°), so the tails stream screen-left, above the card.
  - camera-clearance keys above; no flash.
- **VFX:** none required. Optional polish: `vfx.grass_burst(f, pos=(0.0, y_shin(f)+0.05, 0.65), direction=(0.0, -0.7, 0.5), count=4, speed=0.8, fluff=1.0, seed=zlib.crc32(f"S03:{i}".encode()))` on the four step contacts (254, 267, 280, 288) — a few loosened plume hairs drifting back past the lens; keep counts tiny so S11's plume burst stays special.
- **Events:**

  | frame | type | attrs |
  |---|---|---|
  | ≈241 … 280 | `step` | from `moves.walk` (`who="shinobi"`, grass, ~2 m from the lens → present, intimate) |
  | 288 | `step` | `who="shinobi", strength=0.5` — the stopping step (make sure the walk's last step lands here ±2 f, no duplicate) |
  | 300 | `wind_gust` | `strength=0.5` |
- **Notes:** hidden by the cut in: the 5.29 m walk ellipsis (no reference in frame). The name card starts at 288 on the stop step. No slow motion. Keep the tilt a single smooth move (no hold between 256 and 286); the camera must feel like it "arrives" on his back a beat before he stops.

### S04 — 337–432 (elder MCU, head lift, eye glint, name card "Tenkosai")

- **Purpose (96 f, one take):** the master. The cut lands on the drum with his face hidden under the straw hat; he lifts his head slowly (347–378) — jaw and the long grey beard with its vermilion cord come into the light, and the eyes surface only as a thin dark slot under the brim; one tiny eye glint at 392 (he has seen his opponent). The vermilion spear shaft rises diagonally behind his right shoulder; beard, cord and ochre haori move in the wind. Name card "Tenkosai / founder of the Tenko school" (380–430) lower-left, in the space he looks into.
- **Geometry that drives this cut (real rig numbers, `characters.rig_template("SAINT")`, `DIMS["SAINT"]`):** head bone (0, 3.901, 1.623) → (0, 3.885, 1.850) with the rig at (0, 4); sugegasa Ø 0.62 m, rim plane 0.105 m below the crown top, hat axis = head-bone axis (tilted 4° forward at rest). So the brim edge sits at eye level: with the head level, the eyes are *behind* the brim from any camera between 1.45 and 1.64 m (margin −3 … −4 cm). Solution used here: the lift ends in a proud **13° chin-up** (head extension) and the lens sits **0.28 m below his eye line** (1.45 → 1.47 m): the ray to his left eye then clears the brim's underside from ≈372 and by **+1.8 cm** from 378 on — the eyes read as a dark slot under the brim, never lit (check script `out/dev/breakdown/prologue/s04_brim.py`, per-frame margins below).
- **Camera:** slow push-in, 85 mm, f/2.0, no shake, `framing="mcu"`, `subjects=["saint"]`. Distance to the end-pose head point A = (0.000, 3.921, 1.744) eased in-out 4.60 → 4.05 m (starts from rest after the cut, creeps, settles), azimuth 15° toward +X off his facing axis, height 1.45 → 1.47 m. The aim keeps A at NDC (+0.34, +0.42) for the whole shot: the bowed head sits lower in frame and rises into its place.
  ```python
  cameras.shot("S04", 337, 432, lens=85, framing="mcu", subjects=["saint"], keys=[
      (337, (1.191, -0.523, 1.450), (-0.119, 3.255, 1.555), 85),   # focus 4.61 m  pitch 1.50  yaw 19.12
      (347, (1.186, -0.506, 1.451), (-0.124, 3.272, 1.556), 85),   # focus 4.59
      (362, (1.166, -0.432, 1.453), (-0.144, 3.346, 1.560), 85),   # focus 4.52
      (378, (1.134, -0.311, 1.458), (-0.176, 3.467, 1.568), 85),   # focus 4.39
      (392, (1.103, -0.195, 1.462), (-0.207, 3.583, 1.576), 85),   # focus 4.27
      (410, (1.068, -0.064, 1.467), (-0.242, 3.714, 1.584), 85),   # focus 4.13
      (432, (1.048,  0.009, 1.470), (-0.262, 3.786, 1.589), 85)],  # focus 4.06 (last key CONSTANT, automatic)
      dof=dict(focus=(saint_rig, "head"), fstop=2.0))
  ```
  If the built rig's end-pose head point differs from A, translate every S04 location AND look-at by the difference (the whole camera move rides on his head). Sharp zone ≈0.3 m (brim edge → beard); the spear shaft (0.1–0.3 m behind the head plane) stays nearly sharp; the grass sea and the sky melt (≈45 px CoC at 1920 for the far background).
- **Framing proof** (`s04_real.py`, `s04_final2.py`):

  | frame | neck / head flexion | head A (x, y) | left eye (x, y) | brim front y | hat top y | chin y / beard end y | R / L shoulder (x, y) | brim tips x | eye clears brim by | facing·right |
  |---|---|---|---|---|---|---|---|---|---|---|
  | 337 | +8° / +18° (bowed) | (+0.31, +0.38) | (+0.33, +0.29) hidden | −0.01 | +0.67 | −0.09 / −0.83 | (+0.14, −0.11) / (+0.57, −0.11) | +0.01 … +0.64 | −13.2 cm (hat hides the face) | −0.33 |
  | 362 | +3.6° / +5.8° (lifting) | (+0.33, +0.42) | (+0.33, +0.39) hidden | +0.24 | +0.74 | −0.03 / −0.84 | (+0.14, −0.12) / (+0.57, −0.12) | +0.01 … +0.65 | −6.5 cm | −0.33 |
  | 378 | 0° / −13° (chin up) | (+0.34, +0.42) | (+0.35, +0.49) slot | +0.57 | +0.74 | +0.07 / −0.72 | (+0.13, −0.14) / (+0.58, −0.13) | +0.02 … +0.67 | +1.8 cm | −0.33 |
  | 392 | 0° / −13° | (+0.34, +0.42) | (+0.35, +0.49) ← **glint** | +0.58 | +0.75 | +0.06 / −0.75 | (+0.13, −0.16) / (+0.59, −0.15) | +0.01 … +0.68 | +1.8 cm | −0.33 |
  | 432 | 0° / −13° | (+0.34, +0.42) | (+0.35, +0.50) | +0.59 | +0.77 | +0.05 / −0.82 | (+0.12, −0.18) / (+0.60, −0.18) | −0.00 … +0.70 | +1.9 cm | −0.33 |

  Size hat top → beard end 72–78 % of frame height (MCU, hat and beard both inside the frame). The eye clears the brim at ≈372 (margin −0.8 cm @370, +0.3 @372, +1.1 @374, +1.6 @376) — the eyes appear just as the lift completes. The shaft runs from behind his right shoulder, past his right cheek, along the left slope of the hat and out of the top edge at x ≈ +0.19 (≈18° lean; the black sheath on its upper end stays above frame). Eye-level horizon y −0.29…−0.33 (behind the upper beard; soft at this blur). 180°: one character, projected facing −0.33 (faces screen-left, toward the off-frame shinobi); camera x +1.05 … +1.19 (+X side). Grass: lens 1.45 m high; the frame bottom passes ≈1.19 m above the ground at his distance and meets the 1.1 m grass tops ≈5.6 m out (behind him, full height, defocused); the shrunk clearance zone (1.5–4 m) is never in frame; rig-to-lens distance 4.13 m at 432 (> 4.0, no `framing_qa` warning). Name-card room (name_saint backdrop ellipse centre (−0.57, −0.60), radii (0.52, 0.45); > 1 = outside): right shoulder (+0.12, −0.18) 2.54, hanging right elbow (+0.06, −0.94) 2.06, outer sleeve edge (−0.03, −0.99) 1.83, brim tip (−0.02, +0.37) 5.67; the ink (x ≤ −0.44) is ≥ 0.41 clear of him.
- **Action (elder at (0.0, 4.0), facing 0; katana sheathed, hat + haori on, spear slung — the HANDOFF state):**
  - 337–347 hold `elder_wait_bowed` (neck +8°, head +18°, chest +3° flexion), breathing.
  - **head lift 347–378:** neck +8° → 0° over 347–375, head +18° → **−13°** over 350–378 (ease in-out, the neck leads by 3 f); chest +3° → 0° over 347–372 with an inhale (chest X −1.5° at 366, back to 0° by 378); shoulders square (shoulder.L/R Z −2°). Controlled, unhurried, no overshoot. **Done by 378.**
  - 378–432 hold `elder_wait_level` (neck 0°, head −13°: chin raised, looking down his nose at the challenger); breathing only (chest X ±0.6°, period 80 f). After 392 nothing moves but the wind (beard, cord, haori).
  - arms (out of frame, keep for continuity with S02/S05): left hand on the saya at the guard, right arm hanging.
- **Eye glint (local prop, §5):** `S04_eye_glint` — emissive UV sphere r = 1.5 mm, warm white (1.0, 0.93, 0.82), on his camera-side (LEFT, +X) eye. Place at build time *after* the head keys exist: `frame_set(392)`; eye estimate = (+0.034, 3.830, 1.765) (end pose; = rest estimate (+0.034, 3.800, 1.745) rotated with the head); `hit = scene.ray_cast(depsgraph, cam_loc_392, normalize(eye - cam_loc_392))`; if the first hit is `SAINT_hat` the eye is occluded → raise the chin 2° more (max −17°) or drop the lens 0.05 m (min 1.35 m) and retry; else put the glint 3 mm in front of the hit along the ray, then `bl_util.parent_to_bone(glint, SAINT_rig, "head", keep_world=True)`. Emission strength 386: 0 → 390: 6 → **392: 20** → 394: 6 → 399: 0 (BEZIER); `key_visible` on at 386, off at 400. On screen at ≈ NDC (+0.35, +0.49), ≈3 px (1.07 px/mm at 1920×816) + bloom. Tune in preview until it reads as a glint, never a lamp. Peak **392 = S04.start + 55** (the score computes its koto note from S04's start).
- **Clashes:** none.
- **Environment:**
  - `set_sun(337, azimuth_deg=315.0, elevation_deg=5.0)` (compass, as `environment.set_sun` defines: 0 = +Y, 90 = +X; direction toward the sun (−0.704, 0.704, 0.087)): behind him to his right, ≈26° beyond the left frame edge (half-FOV 12°) → rim on the brim's screen-left edge, his right shoulder, the left edge of beard and cord; face front unlit; sky brighter at frame-left.
  - `set_wind` (1.0 = default breeze; heading = compass direction the wind blows TOWARD): 337 → 1.1 @250°, 350 → 1.1, 369 → 1.6 (gust peaks mid-lift: beard, cord, haori sleeves lift as he rises), 395 → 1.2, 432 → 1.2. Heading 250° streams beard and sleeves toward screen-left, into the space he faces.
  - `environment.set_camera_clearance(337, near=1.5, far=4.0, cone_deg=0)` — restores the default after S03's cone (clearance keys are CONSTANT and would otherwise hold). No flash.
  - optional local fill `S04_beard_fill` (§5).
- **VFX:** none required. Optional polish: 20–30 airborne plume seeds crossing the far background (8–20 m behind him, defocused into bokeh) 337–432.
- **Events:**

  | frame | type | attrs |
  |---|---|---|
  | 350 | `wind_gust` | `strength=0.6` (lifts the beard during the head lift) |
  | 392 | — | none: `score.py` already places the koto note at S04.start + 55 = 392 for the glint — do NOT add a `stinger` (it is a heavy thump) |
  | 433 | — | `music_cue "act1_start"` belongs to act1a |
- **Notes:** ends exactly at 432 = HANDOFF[432] (+2 f handle, same values; his head stays at −13° — act1a's S05 telephoto profile shows him from 50 m, where a raised chin reads as posture). Nothing fast, no slow motion. The glint is the only highlight in the shot: keep the lacquered spear sheath and the straw matte enough not to sparkle in the rim.

## 4. Flash schedule + budget proof

| frame | strength (full-frame white equiv.) | duration | cause |
|---|---|---|---|
| — | — | — | **no flashes in 1–432** (no `environment.flash`, no `bl_util.comp_key_flash`, no lightning, no `flash_ring`) |

Luminance changes that are *not* flashes (listed so QC does not trip on them):

| frame | what | size | why it passes |
|---|---|---|---|
| 97 | hard cut black (post) → sunset wide | one upward step, ≈0 → ≈0.45 mean luma | a single transition, no return to dark; `flash_qc` counts *opposing* flips |
| 241 | cut S02 → S03 (sky-dominant wide → backlit back view) | small step | one flip, next cut 96 f later |
| 337 | cut S03 → S04 (→ MCU, face in shadow, bright sky top-left) | small step | one flip |
| 386–400 | eye glint | ≈3 px sphere + bloom, < 0.05 % of the frame | 0.00 full-frame equivalent |
| 70 | far thunder | sound only | S01 is black (generated in post) |

Budget proof: 0 flashes → the ≥ 12 f spacing (`config.FLASH_MIN_GAP`), the ≤ 70 % cap and the ≤ 2 per second limit hold trivially; `config.FULL_WHITE` (3265–3268) is outside the span; the only ≥ 10 % luminance changes are the three cuts, ≥ 96 f apart, so no 24 f window contains more than one flip (`src/post/flash_qc.py` limit: > 3 opposing flips per 24 f).

## 5. Local poses / moves not in the SPEC macro list

Define these inside `acts/prologue.py` (prefix `_local_` for helpers, pose names as below, objects prefixed with the shot id — pipeline rule 13). Angles are bone-local Euler degrees in the rig conventions (+X = flexion for spine, chest, neck, head, thigh, shin, forearm; Z = abduction; rest = A-pose, arms 46° below horizontal). They are *intent + first values*: check them with `tools/pose_atlas.py` / a Workbench still before previews. **Use FK keys only** — no lane-local constraints (a prologue strip holds forward past 432 and would drag a constraint into Act I).

| name | who | definition | used |
|---|---|---|---|
| `elder_wait_bowed` | SAINT | Waiting, head bowed under the hat. hips 0; spine X +2; chest X +3; **neck X +8; head X +18**; right arm hangs: upper_arm.R adducted to ≈6° off the body (≈ −40° Z from rest), X +8 (a touch forward), forearm.R X +12; left hand resting on the saya just below the guard (koiguchi at rig (0.135, −0.140, 1.050)): upper_arm.L adducted (≈ −35° Z), X +20, forearm.L X +70, hand.L wrist neutral, palm on the saya; legs as rest (stance ≈0.23 m), thigh X +3, shin X +6, `hips_offset` z −0.010. | 1–347 |
| `elder_wait_level` | SAINT | Same body, **neck X 0, head X −13** (chin raised: looking down his nose at the challenger; required for the eye to clear the brim, S04), chest X 0, shoulder.L/R Z −2 (squared). | 378–434 |
| head-lift keys | SAINT | Not a pose, keys: neck +8 → 0 over 347–375, head +18 → −13 over 350–378 (ease in-out, neck leads 3 f); chest +3 → 0 over 347–372 with an inhale (chest X −1.5 at 366, 0 at 378); shoulder.L/R Z 0 → −2. | 347–378 |
| `shinobi_walk_saya` | SHINOBI | Upper-body overlay keyed on top of the walk cycle (key it *after* `moves.walk`, on the same frames, so it replaces the walk's left-arm keys): left hand on the saya at the koiguchi (rig (0.118, −0.118, 0.985)), thumb on the tsuba — upper_arm.L adducted (≈ −35° Z), X +15, forearm.L X +75; right arm swings with the gait, upper_arm.R X ±12 in antiphase with the right leg, forearm.R X +15 … +25; chest Y ±3 counter-rotation; head level (gaze on the elder). | 73–288 |
| `shinobi_stop_ready` | SHINOBI | Stopped, ready but unhurried: feet ≈0.28 m apart, thigh X +4, shin X +8, `hips_offset` z −0.015; spine X 0, chest X −1 (open), neck X 0, head X −2 (eyes on the elder, 1° up); shoulder.L/R Z −1 (dropped, relaxed); left hand stays on the saya (as walk_saya); right arm hangs (upper_arm.R ≈ −40° Z, forearm.R X +10). | 290–434 |
| `_local_walk_stop(rig, 280, 290, (0, -4.846), (0, -4.50))` | SHINOBI | Only if `moves.walk` cannot end on a decelerating short step: root cubic Hermite (start slope 0.0542 m/f, end slope 0); the swing foot plants a 0.25 m step at 288 (heel 285, flat 288); the trailing foot closes to 0.28 m width 288→290 (lift ≤ 3 cm); right-arm swing decays to 0 by 296. | 280–296 |
| `_local_walk_phase` | SHINOBI | Only if `moves.walk` always starts from a standing contact: shift the cycle so 241 is mid-stride (passing pose of the left leg) — simplest: call `walk` over 228–290 on a *scratch* rig/action and copy keys ≥ 241 onto the rig, or key the four-pose cycle (contact / down / passing / up, 12.9 f per step) directly. The S02 walk (73–240) may start standing — it is below frame until 115. | 241–280 |
| `_local_breath(rig, f0, f1, amp, period, phase)` | both | chest X ±amp at quarter periods (BEZIER), shoulder.L/R Z ∓0.3·amp (shoulders rise on the inhale). Shinobi amp 0.8°, period 72 f; elder amp 0.6°, period 80 f (older, slower); different phases. Holds only: S02 elder, 300–434 shinobi, 378–434 elder. | holds |
| `S04_eye_glint` | prop | Emissive UV sphere r = 1.5 mm, colour (1.0, 0.93, 0.82), emission 0 → 20 → 0 over 386–399 (peak 392), `key_visible` 386–400, placed by ray cast and parented to `SAINT_rig`/`head` (details in S04). `visible_shadow=False`. | 386–400 |
| `S04_beard_fill` (optional) | light | Area light 0.8 × 0.8 m, warm (1.0, 0.78, 0.55), at (1.30, 2.30, 1.10) aimed at the beard (0.0, 3.86, 1.50), 6–12 W, **shadows off** (keeps the ≤ 3 shadow-light budget), `key_visible` 337–432 only. Acceptance at 392: beard + jaw read; the eye slot stays ≥ 2 stops darker than the beard. | 337–432 |

Requests to the macro library (nice-to-have; the local fallbacks above cover them): `moves.walk(..., phase=0.5)` to start mid-stride, `ease_out_frames=` for a decelerating final step, and root interpolation `LINEAR` for constant-speed walks.

## 6. Title overlays in the span and framing room

All four are composited in post (`src/post/titles.py` → `assemble.py`); Blender renders nothing for them. Boxes below are the rendered ink extents converted to picture NDC (probe: `out/dev/breakdown/title_boxes.py`; the 2.35:1 picture is y 132…948 of the 1080 delivery frame). Backdrop = the soft dark ellipse each card lays under its text.

| id | frames | cut | text ink (NDC) | backdrop ellipse | how the framing leaves room |
|---|---|---|---|---|---|
| `epigraph` ("For a swordsman, a whole life goes to meet a single instant.") | 13–90 | S01 | glyphs x −0.35…+0.42, y −0.03…+0.14; dateline x ±0.17, y −0.20…−0.12 | centre (+0.03, −0.03) | frame is black (post) — nothing to avoid |
| `main_title` ("Duel in the Silver Grass") | 140–236 (seal 179) | S02 | glyphs x −0.43…+0.43, y −0.10…+0.48; seal centre (+0.50, +0.055), 92 px | centre (0, +0.19), radii (0.53, 0.44) | sky-dominant frame, horizon locked at y −0.333; elder hat top ≤ −0.45 and spear top ≤ −0.40 (≥ 0.30 below the ink), shinobi ≤ −0.66, sun disk (−0.55, −0.13) outside the backdrop (metric 1.60). Only the pine crown (if > 6.5 m) can reach behind the last two title glyphs (accepted, R7). Title fully gone at 236, the cut at 240. |
| `name_shinobi` ("Saku / the masterless shinobi") | 288–334 | S03 | name x −0.82…−0.69, y −0.62…−0.30; epithet x −0.81…−0.62, y −0.80…−0.73 | centre (−0.69, −0.57), radii (0.33, 0.48) → x −1.02…−0.36 | he stands centre-right, body x +0.02…+0.35 (≥ 0.38 clear of the backdrop); under the card: soft grass tops (y < −0.5) and backlit sky; the wider front cone from 288 keeps near blades out of the left edge; hachimaki tails stream screen-left above it. Card ends 334, cut 336. |
| `name_saint` ("Tenkosai / founder of the Tenko school") | 380–430 | S04 | name x −0.82…−0.44, y −0.62…−0.33; epithet x −0.81…−0.56, y −0.81…−0.73 | centre (−0.57, −0.60), radii (0.52, 0.45) → x −1.09…−0.05 | he is right of centre (head x +0.34), facing screen-left into the card; nearest points all outside the backdrop (right shoulder 2.54, hanging elbow 2.06, outer sleeve 1.83, brim tip 5.67); the spear shaft and the sun glow sit above/left-top, clear of the text. Card starts 2 f after the lift ends (378) and before the glint (392); ends 430, cut 432. |

## 7. Risks + fallbacks

| # | risk | detect | fallback (in order) |
|---|---|---|---|
| R1 | `moves.walk` starts every call from a standing contact / eases the root / ends without a short stopping step | S03 frames 241–250 show a start-up; root speed not constant | `_local_walk_phase` + `_local_walk_stop` (§5); re-key the root with `key_root(..., interp="LINEAR")`; S02's walk may start standing (he is below frame until 115) |
| R2 | front-cone clearance behaves differently (keeps a radial bowl around the lens, or clears too little so blades cover the lens) | S03 preview at 241/262/290 | bowl → cone_len 1.25 → 1.0 and near/far 0.25/0.35; blades on the lens → cone_deg 28 for the whole cut; last resort: lens up to 0.62 m at 241 (pitch ≥ 9°) so the nearest blades pass under the frame |
| R3 | preview grass density ×0.25 makes S03's channel look sparse and hides less | previews only | nothing: the elder is masked by the shinobi's body in every frame (proof in S03), not only by grass; judge the grass texture on a final-density still (≈287) |
| R4 | the slung spear changes (meshes lane) and crosses his face in S04 | S04 still at 392 | shaft must stay ≥ 0.03 NDC left of his right cheek: reduce the camera azimuth 15° → 12° (moves the shaft further left of the face) and re-aim at (+0.34, +0.42) |
| R5 | final face/hat meshes put the eye behind the brim despite the 13° chin-up | S04 ray cast hits `SAINT_hat` | chin up to −17°, lens down to 1.35 m (margin grows ≈0.7 cm per 2° of chin, ≈0.5 cm per 0.1 m of lens drop); if still hidden, place the glint on the lower rim of the eye socket just below the brim (reads as the eye catch); ask characters to seat the hat 1–2 cm higher (`hat_seat` 0.105 → 0.09) |
| R6 | the S01 omen `thunder` (70) is the film's first `thunder` event: `src/audio/timeline._derive_cues` takes it as `thunder_first` | audio warning "cue 'thunder_first' … breaks cue order" | its order check already reverts to config 2353; act2 must emit the explicit `music_cue "thunder_first"` (DIRECTION §8, highest priority). Ask the audio lane to skip events tagged `omen` in type-derived cues |
| R7 | the pine (height set by env) reaches behind the title glyphs | S02 still at 200 | accepted (white ink on its dark backdrop over a dark pine reads); if the pine top passes y +0.30, ask env for a shorter crown — PINE_POS is shared with S21, don't move it |
| R8 | the shinobi reads poorly in S02 (0.4–0.7 m above the grass, 7–10 m away, preview density hides less than final) | S02 final-density still at 179 / 236 | lower the whole S02 path 0.3 m (he enters ≈8 f earlier, the elder moves up ≈0.03 — re-run `s02_final.py`); make sure the grass parting follows `SHINOBI_rig` so his wake shows |
| R9 | lane keys hold forward into Act I (NLA HOLD_FORWARD): camera clearance, sun, wind, the glint, the fill light, the chin-up | act1a first frames | clearance reset keyed at 337 (S04); glint hidden from 400, fill hidden at 433; act1a must key its own `set_sun`/`set_wind` at 433 (the prologue leaves 315°/5° and 1.2 @250°); the chin-up is a documented handoff pose (§1) |
| R10 | the 13° chin-up looks wrong in act1a's 50 m profile | act1a review | act1a eases the head to neutral over 433–460 — nobody sees it at 50 m |
| R11 | `environment.set_sun` moves only the key light, not the sky disk, per cut | S02 still | only S02 shows the disk — that is the value that must be right; S03/S04 need only the light direction (rim from screen-left) |
| R12 | motion-blur smear on the S02→S03 teleport | final frame 241 | root key @240 CONSTANT (`bl_util.set_key_interp_at`); cameras are separate objects per cut |
| R13 | the S03 steadicam float makes the settled back view wobble | preview 286–336 | the `add_shake` range ends at 292 with blend 8 → static from 292; if still visible lower amp 0.35 → 0.2 |
| R14 | the walk looks stiff in S03's close view (hakama legs are the subject for 30 frames) | preview 241–270 | tighten the frame to the upper hakama/sash (pitch at 241: 6° → 9°) and let the grass carry more of the frame; the tilt still lands on the same end frame |

Simplest acceptable version if time runs out: S02 as specified (static elder, straight walk); S03 without the decelerating step (he stops on a normal step at 288) and without the float; S04 with the lift and the glint but without the optional fill light — the three cuts, the ellipsis, the titles and HANDOFF[432] are unchanged.

### Open questions (for the lane owners, not blocking)
1. env: does the front-cone mode keep a small radial clearance? Is a parting wake available (S03)?
2. env: pine height (title overlap in S02).
3. characters/meshes: final eye position of the elder and the hat seat (S04 glint, R5).
4. moves: can `walk` start mid-stride and end on a decelerating short step (R1)?
5. audio: skip `omen`-tagged events when deriving `thunder_first` (R6).

## Implementation notes

Implemented in `src/blender/acts/prologue.py` (act-implementation agent, 2026-09-30). Build: `Blender -b --factory-startup --python src/blender/build_scene.py -- --lanes prologue --quality preview`. Progress log + review sheets: `out/dev/acts/prologue/`. Sub-cuts, frames, lenses, camera keys and the HANDOFF[432] state are as specified above; the deviations (same story beats, same timing) and their reasons:

1. **Walks through `moves.walk`** (no local walk): S02 `walk(73 → 240, start=True, stop=False, upper='relaxed_saya')` (1.36 m/s after the start ramp), S03 `walk(241 → 290, phase=0.5, stop=True)` (1.41 m/s, trapezoid stop). The closing step lands at **286** (last full step 277); the step event there is raised to strength 0.5 and tagged `stop` (the breakdown's 288 ± 2). Right-arm swing (upper_arm.R ±12°, antiphase with the right leg) is keyed locally on the walk's footfalls (`_arm_swing`) because an `upper` pose freezes the arms.
2. **Foot plants across the ellipsis cut** (R1 / R12): `moves.bake_feet` is not cut-aware — without extra keys both feet floated 0.6 m up at 236–240 (the S02 gait stops mid-swing) and the S03 left foot was dragged 5 m from its S02 position until 249 (plus two bogus strength-1.0 `step` events at 240/241). The lane registers WORLD plants at 240 (heel strike, trailing foot planted) and 241 (left = stance foot under the hips) and marks the cross-cut footfalls as evented (`_local_plant`, `moves._EVENTED_STEPS`).
3. **`shinobi_stop_ready` keeps the walk's legs** (legs/feet not re-keyed, hips offset = relaxed_saya's): re-solving the pose legs slid the feet 12 cm and sank them 1.4 cm below the ground.
4. **S03 grass clearance**: after he stops, his parting **wake** closes between the lens and him (~1 s later) and the near plume fans rose over him from ≈300 until he was hidden by 320. The front cone now grows LINEAR 276 → 292 from 24° / 1.25 m to **33° / 1.75 m** (the 31° / 1.25 m key at 288 is replaced); the near blades still frame the edges.
5. **S03 rim light** `S03_rim` (new, lane-local): unshadowed warm 1.2 m area light 60 W riding 1.3 m left / 1.9 m ahead of his root at 0.75 m (toward the sun side), 15 W after 296. The knee-height walk was ~60 % black at final quality (the low sun cannot reach into the grass); the rim lights the grass behind him so his legs, sash and saya read as a silhouette against it and catches the saya edge.
6. **S04 fill = shadowed spot from above** instead of the low unshadowed area light: the low fill lit the eyes under the brim (the whole face read, eyes wide open). `S04_beard_fill` is a SPOT (38°, 60 W, soft shadow 0.25 m) at (0.95, 2.45, 2.75) aimed at the beard: the brim throws its shadow across the eyes while moustache, beard and cord read. Shadow casters in S04: ENV_key + this (ENV_flash unused) ≤ 3.
7. **Head end pose −13° → −6°** (`elder_wait_level`, also the HANDOFF[432] pose): with the real hat mesh the −13° chin-up lifted the brim above the brows. At −6° the eyes sit in the brim shadow as a dark slot.
8. **Eye glint** uses the meshes lane's glint discs (`character_meshes.key_eye_glint`: 0 @387 → 0.35 @390 → **1 @392** → 0.35 @394 → 0 @398) instead of a local emissive sphere — no ray-cast placement needed, both eyes catch it.
9. Lane lights hide at `last frame + 0.5` (a key at 433 lies outside the lane strip, which HOLDS its value forward — QA `lane_objects` failed with the light visible through Act I).
10. **S03 plume wisps (optional polish) tried and dropped:** `vfx.grass_burst` tufts (6 per footfall 246–286, `fluff=1.0`, grass-top height) read in preview as dull olive blobs against the backlit sky, and the ones the tracking camera overtakes became large defocused dark smudges crossing the frame (275–285) — debris, not plume hairs. The grass parting + the walk carry the shot; S11's plume burst stays the film's first.
