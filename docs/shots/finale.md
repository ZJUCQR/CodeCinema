# Lane finale — S24–S29 (frames 3073–3840) — shot breakdown

Owner of the code: `src/blender/acts/finale.py` (act-implementation agent). This file is the shot breakdown it codes from. Binding sources: `docs/FILM_PLAN.md`, `docs/STAGING.md`, `src/common/config.py` (import it — numbers quoted here are copies for readability; if config changes, config wins). Geometry checks: `out/dev/breakdown/finale/*.py`. Progress log: `out/dev/breakdown/PROGRESS_finale.md`.

Status: COMPLETE — all sections filled; numbers verified by `out/dev/breakdown/finale/geom.py` (report `geom_report.txt`).

## Sub-cut list (hard cuts only) — summary (binding details: §3 "Final cut table")

| cut id | frames | len | lens | camera | purpose |
|---|---|---|---|---|---|
| S24a | 3073–3120 | 48 | 135 mm | locked telephoto profile = `S05_AXIS` (x 52, z 2.10, pitch 1.45°), y = midpoint | silence; the shinobi rises from his knee in the rain (3085–3115) |
| S24b | 3121–3156 | 36 | 100 mm | locked ECU of the shinobi's scabbard mouth (mirror of S06) | he sheathes; click 3150 over rain alone |
| S24c | 3157–3196 | 40 | 28 mm | low-angle (0.5 m) of the elder from +X | he lifts into jodan; rain bounces off the steel |
| S24d | 3197–3232 | 36 | 85 mm | profile medium of the shinobi, slow push-in | he sinks into the elder's own quick-draw stance; tails hang, no wind |
| S24e | 3233–3264 | 32 | 100 mm | locked ECU of the drop at the tail tip | drop falls 3250 (leaves frame ≈3252), drip 3256 (heard), both launch 3257–3264 (his seen, hers heard) |
| S25a | 3265–3270 | 6 | 135 mm | `S05_AXIS` again (locked) | white 3265–3268; black silhouettes on white meet 3269 and pass 3270 |
| S25b | 3271–3360 | 90 | 135 mm | the SAME camera (marker only: secondary springs reset after the tableau jump) | back to back from 3271; storm image back by 3300; slow rain; thunder tremor 3300 |
| S26a | 3361–3428 | 68 | 40 mm | fixed deep 3/4, the shinobi foreground, rack focus to the elder | slow sheathe; click 3412 = the elder's blade snaps; cord + red mist 3414 |
| S26b | 3429–3456 | 28 | 50 mm | fixed low insert (0.3 m) | the spinning tip plants in the earth 3440 |
| S27 | 3457–3600 | 144 | 30 mm | composed deep two-shot from +X/−Y (imperceptible creep), moon in frame | kneel 3470, blade planted 3476; rain thins; moon; turn 3552–3568; bow 3570–3600 |
| S28 | 3601–3744 | 144 | 50→24 mm | crane up + pull back from the master's bowed head | the shinobi walks away screen-right into depth toward the moon; the elder the still point; wind returns |
| S29 | 3745–3840 | 96 | 35 mm | locked low still life (0.4 m) | the broken tip in moonlit grass; bell + "End" 3758; post fades 3770→3811 (3811–3840 black in post) |

## 1. Lane summary (span, entering / leaving state, deviations)

- **Span** `config.lane_span("finale") == (3073, 3840)` = 768 f (32.0 s): S24 3073–3264 (5 cuts), S25 3265–3360 (2 markers on one framing: S25a 3265–3270, S25b 3271–3360), S26 3361–3456 (2 cuts), S27 3457–3600, S28 3601–3744, S29 3745–3840 (1 cut each) — **12 sub-cuts (11 visible camera changes), all hard cuts**. Acts: `act3` to 3456 (env `storm_night`), `epilogue` 3457–3840 (`moon_clear`, default blend 3470→3550, moon key on the 3457 cut — `environment.default_timeline()` already carries both; the lane re-keys them inside its span). Slow motion: `config.TIME_WARP` (3269, 3456, 0.125) — the film clock runs at 1/8 through S25–S26 (rain, grass freeze, mist, trails, secondary motion); character keys are authored on film frames (see §3 S25/S26 for their pacing). Music: hard stop at 3073 (`silence`), free time afterwards — no metered grid in the span (§2).
- **Pass geometry (the one fight action of the lane).** Both launch from the stand-off (3257 / 3258), charge along the Y axis in two lanes 0.7 m apart (shinobi x −0.35, elder x +0.35 — the shinobi passes on the elder's RIGHT side), blades meet between 3269 and 3270 at ≈ (0.0, −1.30, 1.30); from 3271 they stand back to back 4.6 m apart: shinobi (−0.25, +1.10) facing 180, elder (+0.30, −3.50) facing 0. The camera never leaves the +X side of the action line (`cameras.line_side` sin −0.44 … −1.00 in every cut before 3271, +0.18 … +0.99 after), so the action itself swaps the sides at 3271 (`config.SCREEN_DIRECTION.swap_frame`).
- **Entering state = `config.HANDOFF[3072]`** (key everything at 3073, CONSTANT, and 2 f of handle before):

  | who | root (x, y) | facing | pose | states at 3073 |
  |---|---|---|---|---|
  | shinobi `SHINOBI_rig` | (0.0, −6.0) | 180 | `kneel_sword_planted` (pose atlas / tests: right knee down, blade planted in the mud in front, head bowed; `auto_elbow` R+L) | katana `drawn`, two-handed (`set_two_hand(sh, 3073, True)`), `set_arm_mode(sh, 3073, 'ik')`, kunai hidden (`set_kunai_in_hand(3073, False)`) |
  | elder `SAINT_rig` | (0.0, 2.5) | 0 | `gedan` (library pose: lower guard, blade low toward the opponent's knees, two hands) — act3 holds him still 3040–3072; if its last pose differs, the 3072/3073 cut (a 52 m telephoto) hides it | katana `drawn`, two-handed, `set_arm_mode(el, 3073, 'ik')`, hat `off` (`set_hat(3073, 'off')`), `set_costume(3073, haori=False, thrown=False)` (tasuki visible, thrown haori already burnt/hidden), spear `gone`, beard cord intact (`set_beard_cord(3073, False)`) |
  | env | — | — | — | `storm_night`, rain intensity 1.0 (act2's `vfx.rain(2376, 3500, …)` object — the finale does NOT create rain), wetness 1.0, the ring's glowing steam band alive until 3456 (act2's `fire_ring`), wind as act3 leaves it (re-keyed to 0 at 3073, §3 S24a) |
- **Leaving state (end of film — no HANDOFF follows; everything holds to 3840 +2 f):** shinobi walking away, at (2.00, 7.50) at 3744 facing 160.6 (toward the moon), katana `sheathed` since 3412, left hand on the saya; elder kneeling at (0.30, −3.50) facing 0 in `elder_kneel_broken` (§5) since 3476, katana `broken` since 3412 (stub planted, both hands on the hilt), beard cord `cut` since 3414 (`SAINT_beard_cord_cut` lying in the grass), `SAINT_katana_tip_broken` planted point-down at (0.98, −4.90) since 3440; env `moon_clear`, rain gone (3500), wind 0.6 (heading 170°).
- **Weapon / costume / prop switches in the span (all CONSTANT keys through the `characters` helpers):**

  | frame | call | why |
  |---|---|---|
  | 3073 | states of the table above | enter HANDOFF[3072] |
  | 3086 | `set_two_hand(sh, 3086, False)` | right hand alone pulls the blade from the mud (3086–3094) |
  | 3112 | `set_left_hand(sh, 3112, 'saya', blend=4)` | left hand takes the scabbard mouth for the noto |
  | 3150 | `set_weapon_state(sh, 3150, 'sheathed')` + `key_saya(sh, 3150, 0, 0)` | the tsuba seats — click #2 |
  | 3158 | `set_arm_mode(sh, 3158, 'fk', blend=6)` | right hand leaves the hilt off-screen (hangs; `relaxed_saya` by 3168) |
  | 3162 | elder two-handed already (keep) | jodan lift 3162–3186 |
  | 3200–3214 | `key_saya(sh, f, 0, 60)` (roll 0 → 60 over 3200–3212), `set_arm_mode(sh, 3208, 'ik', blend=6)` with the controller on `sheathed_ctrl_matrix` | iai grab (koiguchi o kiru) |
  | 3268 | `set_weapon_state(sh, 3268, 'drawn')` (inside the white) | the draw happens inside the white-out |
  | 3271 | shinobi one-handed zanshin, left hand back on the saya (`set_left_hand(sh, 3271, 'saya')`), elder two-handed | tableau |
  | 3361 | (left hand stays on the saya since 3271) | slow noto begins |
  | 3412 | `set_weapon_state(sh, 3412, 'sheathed')` **and** `set_weapon_state(el, 3412, 'broken')` + `snap_free('SAINT_katana_tip_broken', 3412)` | click #3 = the snap (same frame) |
  | 3413 | `set_arm_mode(sh, 3413, 'fk', blend=8)` | right hand off the hilt |
  | 3414 | `set_beard_cord(3414, True)` + `snap_free('SAINT_beard_cord_cut', 3414)` | the cord flutters away |
  | 3440 | tip planted: last toss key, CONSTANT (§3 S26b) | still life prop for S29 |
- **Deviations from config / HANDOFF / SPEC (and why)** — none at the entering boundary (HANDOFF[3072] exactly):
  - **D1 S05 axis = direction, height, pitch, lens; y follows the pair.** `S05_AXIS` (act1a: x 52.0, z 2.10, pitch 1.45°, 135 mm, *camera y = the fighters' midpoint*): S24a y −1.75 (8.5 m apart, as S05), S25 y −1.20. Same image grammar as S05, not the same world line (the fighters stand 1–1.5 m further −Y than in S05).
  - **D2 The pass is a two-frame "time jump".** 3269 = contact (silhouettes touching), 3270 = overlap (heads at the same screen x, the draw-cut through), 3271 = the tableau 2–3 m further on (a physical skid would need ~0.6 s). Hidden by the white-out: 3265–3268 pure white, 3269–3276 black silhouettes on white (the eye cannot track the jump). Root keys 3270 → 3271 are CONSTANT (a hard jump, no motion-blur streak on the tableau frame).
  - **D3 S24e shows the drop, its fall and the shinobi's launch; the puddle hit and the elder's launch are heard.** The tail tip hangs at the small of his back, so no ECU of it can also hold the puddle (0.9 m below) or the elder (8.7 m ahead, masked by his own body). The drop leaves the frame at ≈3252; `drip` at 3256 and the elder's `dash` at 3258 are sound-only; his tail and body whip out of the frame 3257–3259. (config: "falls at 3250, hits a puddle at 3256; both launch 3257–3264" — frames kept exactly.)
  - **D4 The elder's zanshin blade is held HIGH** (fists 1.22 m, blade 10° below horizontal, z 1.07–1.22 m) instead of a low follow-through, so it stays above the waist-high grass in S25 and S26 and the snap reads.
  - **D5 The broken tip flies on the fx clock** (1/8 speed, Δfx 0.146 s from 3412 to 3440): to plant at ~3440 it needs a downward spring-back flick (v0 ≈ (2.3, −1.4, −6.2) m/s fx), i.e. it sinks and tumbles at ≈3 cm per film frame.
  - **D6 Cross-lane channels (keyed only inside the finale span):** visibility of act2's rain pools (hidden 3265–3276) and of act2's steam-band / smoke / ember objects and fire-ring lights (hidden 3265–3276; the env fog is handled by `fog_den` 0 in the white-out snapshot, not by visibility). act2 owns and creates these objects (act2.md R1); the finale only keys `hide_render`/`hide_viewport` from 3073 (visible) on. If act2 prefers, it can add `intensity` keys (3264: 1.0, 3265: 0.0, 3276: 0.0, 3277: 1.0) to its rain call instead — then drop the rain part of D6.
  - **D7 White-out look (3265–3300) = an environment snapshot keyed with the public `environment.set_param`** (camera-ray sky white, lighting-ray ambient 0, lamps 0, fog 0, aerial haze distance 2 m) + `render_setup.key_white_flash` for the 4 pure-white frames. No new module API is needed (§3 S25 has the exact values + fallbacks).
  - **D8 Moon cheats per cut** (key light = moon from the 3457 cut): S27 az 347° el 9° disk 4.2°, S28 az 350° el 3.5° disk 4.8°, S29 az 240° el 24° (key only, disk out of frame). The storm key also moves per cut in S24–S26 (backlight 150–170° from each lens, DIRECTION §6).
  - **D9 Camera grass clearance overrides** (`environment.set_camera_clearance`) per cut — S24b/S24e/S26b default (the lens is < 1.5 m from the subject), S24c 1.5/4.0, S24d 3.0/6.0, S27 3.7/5.5, S28 1.5/4.0, S29 2.6/4.6; reset to the default 1.5/4.0 at 3073 and never left unkeyed across a cut.
  - **D10 Tail override 3226–3264** (`lane_tools.secondary_override(SHINOBI_rig, 3226, 3264, tail bones)`): the soaked tails hang 11° back so the tips clear the hakama (the sim collides with head/chest spheres only) and the S24e ECU finds the tip where the camera is aimed; the lane keys the 3257–3262 whip. Outside that range the secondary sim runs normally (wind 0 + wet → hanging).

## 2. Beat grid for the span

The finale is **free time**: `config.TEMPO_MAP` ends with act3 (2497–3072, 140 BPM); `beat_frame("act3", 56)` = **3073** is the downbeat of bar 15 on which ALL music stops (`MUSIC_CUES["silence"]`). Nothing after 3073 is locked to a grid. Picture locks are to `config.MUSIC_CUES` (emit each as a `music_cue` event on the frame below) and to the score's free-time placements made from them (`src/audio/score.py::arr_final_pass / arr_epilogue`, read, not edited):

| frame | source | picture on that frame |
|---|---|---|
| **3073** | `silence` (act3 beat 56) | hard cut to S24a: rain only, the shinobi still hidden kneeling in the grass |
| 3150 | story beat `sheathe` + `tsuba_click` (REQUIRED ±3) | S24b: the tsuba seats — click #2 over rain alone |
| 3256 | `drip` (audio extension type, S24e) | the drop hits the puddle off-screen (it left the frame at ≈3252) |
| 3257 / 3258 | `dash` ×2 | he explodes out of the S24e frame / the elder's charge is heard (pan right) |
| **3265** | `white_silence` (every stem to digital zero until 3277) | the cut to S25 IS the white: 3265–3268 pure white |
| 3269–3270 | — (silent) | the crossing, black on white |
| **3277** | `blade_ring` (mix places the thin ring itself: no clash/draw/sword_break event within ±3 f!) | the rain reappears, hanging (1/8 speed); the white starts to fade |
| **3300** | `final_pass` (the unified hit: odaiko, sub, noise, strings sfz, huge tail) + `thunder` near | the storm image fully back; a 0.12-strength tremor on the telephoto |
| 3377 | score: low strings swell (final_pass + 3.2 s) | — |
| **3412** | story beats `sheathe`, `tsuba_click`, `sword_break` (REQUIRED ±8, same frame) | S26a: guard home = the blade snaps |
| 3414 | `cord_cut` (REQUIRED ±4) | the cord flutters away, red mist |
| 3420 / 3432 / 3462 | score: solo shakuhachi answers the break (tenko fragment D4 → Eb4 meri → D4, the "sigh" resolves ≈3462) | the tip lands 3440; the elder's knees give way **from 3462** (the sigh) → knee down 3470 |
| 3470 | `rain_stop` (audio: rain fades over 1.6 s) | S27: knee lands; the rain thins 3470→3500 (act2's intensity curve) |
| **3505** | `epilogue` (strings swell, then shakuhachi Tenko motif in yo from ≈3534, koto Saku motif ≈3587 / ≈3656) | the moonlight edge starts its sweep (3505–3550) |
| 3587 | score: koto Saku motif (home figure) | the shinobi's bow is at its lowest 3582–3592 |
| 3734 | score: last koto dyad (end_card − 1 s) | S28 crane settling |
| **3758** | `end_card` (+ `bell` event, REQUIRED ±3) | S29: the "End" glyph starts writing (post overlay) |

For reference only: continuing the act3 grid past the silence would give 3083, 3094, 3104 … (10.29 f per beat) — not used.

## 3. Sub-cuts

Conventions in every block: NDC x −1 (left) … +1 (right), y −1 (bottom) … +1 (top) of the 1920×816 picture; "fig %H" = full standing/kneeling figure height as % of frame height at its depth, "above grass" = the part above the nominal 1.05 m arena grass; pinhole with `sensor_fit='HORIZONTAL'`, 36 mm (as `bl_util.new_camera`), vertical half-extent 7.65 mm. Numbers come from `out/dev/breakdown/finale/geom.py` → `geom_report.txt` (re-run it after any change). Camera keys are `(frame, location, look_at, lens)` for `cameras.shot` (look-at = an aim point on the lens axis). Module aliases used below: `C` = cameras, `CH` = characters, `PZ` = poses, `M` = moves, `ENV` = environment, `VFX` = vfx, `EV` = events, `RS` = render_setup, `LT` = lane_tools, `U` = bl_util. Seeds: `zlib.crc32(b"S25:0")` etc. Every key on a character / prop / env channel in this lane is CONSTANT at a cut (pipeline rule 2); poses between keys are BEZIER unless noted. Facing θ: forward = (sin θ, −cos θ); compass azimuth: 0 = +Y, 90 = +X.

### Final cut table

| cut | frames | len | camera | lens | key/moon (az, el) | story point |
|---|---|---|---|---|---|---|
| S24a | 3073–3120 | 48 | locked telephoto profile, `S05_AXIS` at y −1.75 | 135 | 272 / 28 (behind the pair) | silence; he rises out of the grass |
| S24b | 3121–3156 | 36 | locked ECU (1 cm creep) below-front-right of the koiguchi, looking up 44° | 100 | 236 / 40 | the noto's last 30 cm; click 3150 |
| S24c | 3157–3196 | 40 | locked low angle (0.5 m) from +X, 4 m | 28 | 268 / 22 (glow behind his head) | jodan lift, rain bouncing off the steel |
| S24d | 3197–3232 | 36 | slow push-in 0.30 m, profile from +X, 6 m | 85 | 262 / 26 | he takes the elder's iai stance; tails hang |
| S24e | 3233–3264 | 32 | locked ECU of the tail tip from +X, 0.5 m | 100 | 268 / 22 | the drop gathers, falls 3250; drip 3256; launch 3257 |
| S25a | 3265–3270 | 6 | locked telephoto profile, `S05_AXIS` at y −1.20 | 135 | 270 / 26 (white-out) | white 3265–3268; silhouettes meet 3269, pass 3270 |
| S25b | 3271–3360 | 90 | the same camera (marker only) + tremor 3300 | 135 | 270 / 26 | back to back 3271; image back by 3300; slow rain |
| S26a | 3361–3428 | 68 | locked deep 3/4 from +X/+Y, rack focus 3398→3410 | 40 | 212 / 28 | slow noto in front; click 3412 = the snap; cord 3414 |
| S26b | 3429–3456 | 28 | locked low insert (0.30 m), 1.2 m from the landing point | 50 | 290 / 30 | the tip plants 3440 |
| S27 | 3457–3600 | 144 | locked (3.6 cm creep) low deep two-shot from +X/−Y | 30 | moon 347 / 9, disk 4.2° in frame | kneel 3470, stub 3476; rain stops; moon; turn 3552–3568; bow 3570–3600 |
| S28 | 3601–3744 | 144 | crane up + pull back + zoom 50→24 mm around the kneeling elder | 50→24 | moon 350 / 3.5, disk 4.8° | he walks away toward the moon; the wind returns |
| S29 | 3745–3840 | 96 | locked low still life (0.40 m) | 35 | key 240 / 24 (disk out of frame) | the broken tip; bell + "End" 3758; post fade 3770→3811 |

Cut lengths: every visible cut is ≥ 28 f (S25a's 6 f is a marker on the SAME framing as S25b, not a visible cut — see S25); stillness beats S24a (48), S25a+b (96), S27 (144), S28 (144), S29 (96).

### Shared blocking (both characters, root = rig object on the ground)

| frame | shinobi root (x, y) / facing / pose | elder root (x, y) / facing / pose |
|---|---|---|
| 3073 | (0.00, −6.00) / 180 / `kneel_sword_planted` | (0.00, 2.50) / 0 / `gedan` (two hands) |
| 3085–3115 | rises: `rise_kneel` 3094 → `relaxed_saya`-like stand 3115 (blade lowered right, `low_1h`) | still |
| 3116–3150 | noto at (0, −6.00): `sheathe_quick_1` 3116 → controller slide (S24b) → `sheathe_done` 3150 | still |
| 3162–3186 | `relaxed_saya` (hands: left on the saya, right hanging) | `gedan` → `chudan` 3172 → `jodan` 3186 |
| 3200–3226 | → `iai_crouch` settled 3226, root (0.00, −5.90) (right foot forward) | `jodan` |
| 3257 | launch (`dash` body, iai hands): 3258 (−0.04, −5.84), 3260 (−0.11, −5.48), 3262 (−0.20, −4.83), 3264 (−0.29, −4.05), 3266 (−0.34, −3.23), 3268 (−0.35, −2.41) | 3258 launch: 3260 (0.09, 2.29), 3262 (0.19, 1.85), 3264 (0.28, 1.24), 3266 (0.33, 0.56), 3268 (0.35, −0.12) (charge in `jodan`) |
| 3269 | (−0.35, −2.00) `pass_contact_sh` (§5) | (0.35, −0.46) `pass_contact_el` (§5) |
| 3270 | (−0.35, −1.55) `pass_overlap_sh` — **CONSTANT** | (0.35, −0.80) `pass_overlap_el` — **CONSTANT** |
| 3271–3360 | (−0.25, 1.10) / 180 / `sh_zanshin_pass` (§5) | (0.30, −3.50) / 0 / `elder_zanshin_high` (§5) |
| 3361–3412 | slow noto `sheathe_slow_chiburi` 3361 → `sheathe_slow_1` 3384 → `sheathe_slow_2` 3398 → `sheathe_done` 3412 | frozen; 3412 blade breaks, 3414 cord cut |
| 3413–3551 | `relaxed_saya`, head bowed 8° | 3456 still standing; knees give 3462; `elder_kneel_broken` (§5) knee 3470, stub planted 3476 |
| 3552–3568 | turns in place 180 → 90 → 0 (via +X, toward the camera side) | kneeling, still |
| 3570–3600 | `bow` 3582, held to 3592, up by 3600 | still |
| 3601–3614 | turns 0 → 90 → 160.6 | still |
| 3614–3744 | `M.walk` (−0.20, 1.18) → (2.00, 7.50), 1.26 m/s | still (the still point) |

### Lane-local helpers used by several blocks (full specs in §5)
`_local_toss_fx(obj, f0, f1, p0, v0, spin_axis, spin_deg, rot0=None)` — ballistic keys EVERY frame on the FILM CLOCK (`t = fxclock.fx_time_at(f) − fxclock.fx_time_at(f0)`, `p = p0 + v0·t + ½·g·t²`, g = −9.81), so props slow down with `config.TIME_WARP` exactly like rain / mist (use `props.toss` instead only if it integrates fx time); `_local_droplets(frame, pos, direction, count, speed, spread, life, size, seed)` — a tiny fixed-count water-drop pool (same recipe as vfx pools: GN points, fx-time ballistics, scale 0 when unborn/dead, the vfx `VFX_water_drop` material if it exists, else a local copy: Translucent + Glossy 0.65 + emission 0.06, DITHERED, no shadow); `_local_drop()` — the single S24e drop; `_local_whiteout(f)` — the white-out environment snapshot (S25); `_local_hide(objs, f_hide, f_show)` — `U.key_visible` pairs with an explicit visible key at the span start 3073.

### S24a — 3073–3120 (48 f) — silence; he rises out of the grass (stillness beat)
**Purpose.** The music is gone; only rain. The long lens flattens the field: the elder waits in the downpour, blade low, unhurried; the shinobi is not there — he is down in the waist-high grass where S23 left him. Then his head and shoulders rise out of the grass sea, the blade comes out of the mud, he stands. The audience must read: he is not finished, and the master is waiting for him (respect, not mercy).

**Camera — locked telephoto profile on the S05 axis (D1).**
```python
S05_AXIS = dict(x=52.0, z=2.10, pitch_deg=1.45, lens=135.0)        # act1a's constant (same numbers)
y_mid = (-6.0 + 2.5) / 2                                           # -1.75 (HANDOFF[3072] pair, 8.5 m apart as in S05)
look_z = S05_AXIS["z"] + S05_AXIS["x"] * math.tan(math.radians(S05_AXIS["pitch_deg"]))   # 3.416
C.shot("S24a", 3073, 3120, keys=[(3073, (52.0, y_mid, 2.10), (0.0, y_mid, look_z), 135.0)],
       dof=dict(focus=52.0, fstop=5.6), subjects=["shinobi", "saint"], framing="wide")
```
No shake, no drift. Pitch +1.45°, yaw 270° (looking −X); horizon at y −0.45; the grass line at the figures (1.05 m) at y −0.80 (1.15 m: −0.77); frame 13.9 × 5.9 m at the subjects.

| frame | shinobi head (x, y) | above grass | elder head (x, y) | fig / above grass | rule |
|---|---|---|---|---|---|
| 3073 | (−0.57, −0.81) kneeling | 1.3 %H → hidden (head at the grass tops) | (+0.60, −0.58) | 30.8 / 13.0 %H | side sin −0.997, order OK |
| 3092 | (−0.58, −0.77) | 3.5 %H — head + headband break the grass line | (+0.60, −0.58) | | OK |
| 3100 | (−0.59, −0.70) | 6.9 %H | | | OK |
| 3108 | (−0.60, −0.64) | 9.8 %H | | | OK |
| 3120 | (−0.61, −0.62) standing | 11.1 %H (fig 28.9 %H) | (+0.60, −0.58) | 30.8 / 13.0 %H | OK |

**Action.**
| frames | shinobi (0.00, −6.00), facing 180 | elder (0.00, 2.50), facing 0 |
|---|---|---|
| 3073–3084 | `kneel_sword_planted` held (key 3073 + 3084), two hands on the hilt; one heavy breath (chest X +1.5° at 3079, back at 3085) | `gedan` (two hands, tip low toward the shinobi's knees) held; breathing chest X ±0.8° period 60 f |
| 3085 | right fist tightens (hand.R X +4°) | — |
| 3086–3094 | `CH.set_two_hand(sh, 3086, False)`; left hand pushes on the left knee (FK: upper_arm.L flex 30, forearm.L 60); right hand draws the blade out of the mud along its own axis: `CH.key_sword(sh, 3086, grip=(0.03, −5.55, 0.66), direction=(0, 0.15, −1))` → `CH.key_sword(sh, 3094, grip=(0.05, −5.60, 0.95), direction=(0.10, 0.35, −0.93))` (tip clears the ground at ≈3090) | — |
| 3090–3112 | rises: `PZ.key_pose(sh, 3094, "rise_kneel")` → hips −0.15 / back knee lifting at 3104 → standing at 3112 with the blade lowered on his right, `PZ.key_pose(sh, 3112, "low_1h")` (one-handed, tip down-forward-right, edge down); head comes up to level on the elder by 3108 | — |
| 3112 | `CH.set_left_hand(sh, 3112, "saya", blend=4)` | — |
| 3113–3120 | the blade swings up and across to the left hip: `PZ.key_pose(sh, 3118, "sheathe_quick_1")` (kissaki at the koiguchi on the saya axis = slide s 0.70, see S24b), right foot drawn back 0.2 m (`legs` lead "L" — needed by the S24b camera) | still |
Root keys: shinobi (0.0, −6.0) / 180 at 3073 and 3120; elder (0.0, 2.5) / 0 at 3073 and 3120.

**Clashes.** none.

**Environment** (also the lane-start snapshot; the default env timeline already has storm_night here):
```python
ENV.set_state(3073, "storm_night")                                   # full snapshot, blend 0
ENV.set_sun(3073, 272.0, 28.0)                                       # moon behind clouds, behind the pair: 27° off the lens axis (153° backlight)
ENV.set_wind(3073, 0.0, direction_deg=205.0, interp='CONSTANT')      # the storm holds its breath on the cut (held until S28)
ENV.set_wetness(3073, 1.0, interp='CONSTANT')
ENV.set_camera_clearance(3073, 1.5, 4.0, 0.0, 0.0)
ENV.set_cloud_shadow(3073, edge='off')
# (the D6 visibility keys - visible from 3073 - are made by the single _local_hide call listed in S25)
```
No `flash` anywhere in S24 (DIRECTION §5); no lightning bolts.

**VFX.** None new: act2's rain curtain (intensity 1.0; the telephoto box, RAIN_LENS_* 135 mm) and the glowing steam band behind the pair (far side of act2's ring at x ≈ −11) carry the image.

**Events.**
```python
EV.emit(3073, "music_cue", cue="silence")                            # every music stem stops on this frame
EV.emit(3090, "step", who="shinobi", strength=0.25)                  # left foot takes the weight, blade leaves the mud
EV.emit(3104, "step", who="shinobi", strength=0.30)                  # back foot comes up
EV.emit(3116, "whoosh", who="shinobi", weapon="katana", strength=0.15)
```
**Notes.** His rise must read as coming OUT of the grass (his head crosses the grass line ≈3088). The elder must not move at all. The act3 → finale cut at 3072/3073 is a change of lens (act3's S23 camera → 135 mm from 52 m): any small pose mismatch of the kneeling shinobi is invisible (he is hidden in the grass).

### S24b — 3121–3156 (36 f) — the noto; click #2 at 3150 (mirror of S06)
**Purpose.** In front of an armed master he puts his sword AWAY — the commitment to answer iai with iai. An ECU of the scabbard mouth, the same scale as S06 (≈20 × 9 cm): the last centimetres of wet steel slide into the black lacquer, the tsuba seats — click — over the rain alone. S06 showed the elder's tsuba going OUT with the hilt pointing screen-left; here the shinobi's goes IN with the hilt pointing screen-right (his facing).

**Camera — locked ECU from below-front-right of the koiguchi (the only clean +X view of his LEFT hip), 1 cm creep.**
```python
saya = bpy.data.objects["SHINOBI_saya"]                              # origin = koiguchi, local +Y = to the kojiri
K = U.world_pos_of(saya, 3140)                                       # nominal (-0.118, -5.882, 0.985)
A = (U.world_matrix_of(saya, 3140).to_3x3() @ Vector((0, 1, 0))).normalized()   # nominal (-0.219, -0.844, -0.489)
u0 = Vector((0.69, 0.22, -0.69)); u = (u0 - u0.dot(A) * A).normalized()          # nominal (0.69, 0.22, -0.69)
# create AFTER the shinobi's 3116-3150 keys exist (the saya follows the hips)
C.shot("S24b", 3121, 3156, keys=[(3121, K + 0.60 * u, K - 0.015 * A, 100.0),
                                 (3156, K + 0.59 * u, K - 0.015 * A, 100.0)],
       dof=dict(focus="SHINOBI_saya", fstop=4.0), subjects=["shinobi"], framing="ecu", clip=(0.02, 500.0))
```
Nominal lens position (0.30, −5.75, 0.57): pitch +44.5°, yaw 253.8°, 0.60 m from the koiguchi; view ⟂ the saya axis (90.0°) so the whole slide stays inside the ≈4 mm focus slab (f/4, 100 mm, 0.6 m).

| point | NDC (x, y) at 3121 / 3156 |
|---|---|
| koiguchi (= seated tsuba face) | (−0.10, −0.22) / (−0.11, −0.22) |
| tsuba 3 cm out | (+0.10, +0.22) |
| tsuba 6 cm out | (+0.31, +0.65) |
| tsuba 9 cm out | (+0.52, +1.08) — outside: the tsuba enters the frame at ≈8.5 cm (≈3139) |
| saya 8 cm toward the kojiri | (−0.66, −1.38) — the scabbard runs out of the lower-left corner |
The saya/blade axis crosses the frame on a 42° diagonal, hilt up-right (= his facing, screen-right). Heads are far off-screen (shinobi (−0.74, +6.6)); `line_side` −0.80 (+X side; QA side check = SKIP, no head in view). Occlusion (geom): the view ray passes 0.19 m in front of his right thigh — **the right foot must be the rear foot** (noto stance `stance(lead="L")`) — and in front of the belly (the koiguchi sits on the obi's front-left surface).

**Action — the slide on the sword controller ().** s(f) = distance of the tsuba face from the koiguchi, measured along −A (hilt side):

| frame | 3118 (S24a) | 3121 | 3128 | 3134 | 3140 | 3145 | 3148 | **3150** | 3151–3156 |
|---|---|---|---|---|---|---|---|---|---|
| s (m) | 0.70 (kissaki at the mouth) | 0.52 | 0.30 | 0.16 | 0.075 | 0.030 | 0.008 | **0.000** click | 0 |
```python
ctrl = bpy.data.objects["SHINOBI_sword_ctrl"]
for f, s in S_KEYS:                                   # the table above; BEZIER, LINEAR on 3145 -> 3150 (no overshoot)
    CH.key_ctrl_matrix(ctrl, f, Matrix.Translation(-A_at(f) * s) @ CH.sheathed_ctrl_matrix(sh, f))
CH.set_weapon_state(sh, 3150, "sheathed")             # in-hand -> sheathed copy on the same frame (0.003-0.006 mm apart)
CH.key_saya(sh, 3121, 0.0, 0.0); CH.key_saya(sh, 3150, 0.0, 0.0)      # edge up, no saya-biki
```
Body `sheathe_quick_1` (3118) → `sheathe_done` (3150), left hand on the saya mouth ('saya' since 3112), right fist on the hilt (IK); after the click the fist stays on the hilt to 3156 (it drops off-screen 3158–3168: `CH.set_arm_mode(sh, 3158, "fk", blend=6)` → `relaxed_saya`). One-handed on the hilt throughout (DIRECTION §7: the two-handed grip is for cutting). Elder off-screen: `gedan` held.

**Clashes.** none.

**Environment.** `ENV.set_sun(3121, 236.0, 40.0)` — the key 14° off the lens axis, behind and above the obi: rim on the lacquer, a line of light along the steel's edge, rain streaks lit. Clearance default (1.5 / 4.0: the lens sits 0.6 m from the koiguchi, well inside the bare zone). Wind 0.

**VFX.** The near rain pool of act2's rain call fills the focus slab (DOF on + focus object = `SHINOBI_saya`, vfx notes "S24 inserts"). At the click the jolt shakes the beads off the guard: `_local_droplets(3150, K - 0.005 * A, direction=(0.2, 0.3, 1.0), count=8, speed=0.6, spread=40, life=10, size=0.0015, seed=zlib.crc32(b"S24b:0"))`.

**Events.**
```python
EV.emit(3150, "sheathe", who="shinobi", tags=["sheathe"])
EV.emit(3150, "tsuba_click", target="SHINOBI_saya", who="shinobi", tags=["tsuba_click", "click_motif_2"])
```
**Notes.** The click lands on 3150 exactly (REQUIRED beat ±3; motif 566 / 3150 / 3412). No camera move and no light change at the click. The hands stay dark masses at the frame edges; only lacquer and steel catch the key.

### S24c — 3157–3196 (40 f) — the master lifts into jodan; rain bouncing off the steel
**Purpose.** His answer: from the low guard the old master raises the long blade into jodan, both hands, against the storm — the stance that split the rain in S23. The rain splashes off the rising steel. A low angle makes him a tower; the moon's glow through the clouds sits right behind his head.

**Camera — locked low angle from +X (0.5 m, 4 m), 6 cm push.**
```python
C.shot("S24c", 3157, 3196, keys=[(3157, (3.80, 1.90, 0.50), (0.00, 2.02, 1.60), 28.0),
                                 (3196, (3.74, 1.92, 0.50), (0.00, 2.02, 1.62), 28.0)],
       dof=dict(focus=(saint_rig, "head"), fstop=2.8), subjects=["saint"], framing="medium")
ENV.set_camera_clearance(3157, 1.5, 4.0)
```
Pitch +16.1°, yaw 273.8°; the horizon is below the frame (y −1.06): storm sky behind him.

| frame | elder head | fig / above grass | blade | rule |
|---|---|---|---|---|
| 3157 | (+0.16, +0.08) | 83.0 / 35.0 %H | gedan tip (−0.17, −1.00) — low in the foreground grass | side sin −0.435 ✓; shinobi off-screen left (x −3.3), the elder faces screen-left toward him ✓ |
| 3186–3196 | (+0.18, +0.12) | 84.6 / 36.7 %H | jodan fists (+0.23, +0.34), tip (+0.37, +0.88) — inside the frame | ✓ |
Foreground: the lens is below the grass tops; the clearance ramp (1.5 → 4 m) leaves 40–80 %-height grass tips across the bottom of the frame, out of focus (framed waist-up through foreground grass, like act1b S14).

**Action — elder (0.00, 2.50), facing 0, two-handed throughout.**
| frames | pose / move |
|---|---|
| 3157–3161 | `gedan` held |
| 3162–3184 | the lift: `PZ.key_pose(el, 3162, "gedan")` → `PZ.key_pose(el, 3172, "chudan")` → `PZ.key_pose(el, 3184, "jodan")` (or `M.stance(el, 3184, "jodan")`); the tip travels in the sagittal plane from forward-low (0.10, 1.75, 0.55) over forward-horizontal (3172) to overhead-back (0.0, 3.04, 2.68); unhurried (25 f) |
| 3186–3190 | settle: 2 cm sink (hips_offset y −0.02) on an exhale |
| 3190–3196 | absolute stillness |
Shinobi off-screen: `relaxed_saya` (right arm dropped by 3168), head level on the elder.

**Clashes.** none.

**Environment.** `ENV.set_sun(3157, 268.0, 22.0)` → the moon's position projects at (−0.15, +0.38), 8° off the lens axis: the storm's moon glow (`glow_str` 0.22) sits as a pale halo just behind his head and the rising blade — his silhouette reads against it (DIRECTION §6). Wind 0.

**VFX — rain bouncing off the steel** (+ the near rain pool around the focus distance 4 m):
```python
for i, f in enumerate(range(3168, 3197, 2)):                         # 15 small bursts along the blade's upper edge
    p = _blade_point("SAINT_katana_base", "SAINT_katana_tip", f, u=0.25 + 0.75 * ((i * 0.618) % 1.0))  # sampled at f
    _local_droplets(f, p, direction=(0.0, 0.0, 1.0), count=6, speed=1.0, spread=50, life=9, size=0.002,
                    seed=zlib.crc32(f"S24c:{i}".encode()))
```
(`_blade_point` evaluates the two blade sockets at `f` inside `U.muted_modifiers`; direction = up, the spread tilts some drops off the flat.) Backlit, the drops sparkle; they must stay small (1.2–2.5 mm) — never a spray cloud.

**Events.** `EV.emit(3176, "whoosh", who="saint", weapon="katana", strength=0.25)` (the blade through the rain).

**Notes.** The low camera is 0.5 m high — below the grass: keep the clearance keyed (default 1.5/4.0) so no blade of grass touches the lens. The hat is gone since S13 (bare scarred head in silhouette against the glow).

### S24d — 3197–3232 (36 f) — he takes the master's own stance; tails hang, no wind
**Purpose.** The student answers with the teacher's technique: he sinks into exactly the iai crouch the elder showed in S05 (right hand to the hilt, left thumb on the tsuba, weight forward). The soaked hachimaki tails hang straight down — no wind, nothing moves but the rain.

**Camera — profile medium from +X, 85 mm, slow push-in 0.30 m.**
```python
C.shot("S24d", 3197, 3232, keys=[(3197, (6.30, -5.75, 1.62), (0.00, -5.82, 1.22), 85.0),
                                 (3232, (6.00, -5.75, 1.60), (0.00, -5.82, 1.22), 85.0)],
       dof=dict(focus=(shinobi_rig, "chest"), fstop=2.8), subjects=["shinobi"], framing="medium")
ENV.set_camera_clearance(3197, 3.0, 6.0)          # lowers the grass between lens and subject: the fist on the hilt reads
```
Pitch −3.6°, yaw 269.3°; horizon y +0.70 (far field + steam band glow behind him); grass line at the subject ≈ y −0.32.

| frame | shinobi head | fig / above grass | right fist (hilt) | koiguchi | tail tip | rule |
|---|---|---|---|---|---|---|
| 3197 | (−0.11, +0.66) standing | 150 / 57.3 %H | (+0.15, −0.44) | (+0.04, −0.61) | (−0.19, −0.53) | side sin −0.999 ✓; elder off-screen right (x +6.3), he faces screen-right ✓ |
| 3214 | (0.00, +0.45) sinking | 142 / 47.4 %H | (+0.15, −0.45) | | (−0.19, −0.54) | ✓ |
| 3232 | (+0.03, +0.39) crouched | 142 / 44.9 %H | (+0.16, −0.46) | (+0.05, −0.64) | (−0.20, −0.56) | ✓ |
The fists sit at the grass tops (partly veiled by the bent tips of his own parting — accepted: the arm reaching across to the hilt carries the gesture). Tails hang behind his back, screen-left of the head.

**Action — shinobi, root (0.00, −6.00) → (0.00, −5.90), facing 180.**
| frames | move |
|---|---|
| 3197–3199 | `relaxed_saya` held (left hand on the saya mouth, right arm hanging) |
| 3200–3212 | koiguchi o kiru: `CH.key_saya(sh, 3200, 0.0, 0.0)` → `CH.key_saya(sh, 3212, 0.0, 60.0)` (edge turns out) — the thumb rests on the tsuba, **no push, no click** (the motif's clicks are 566 / 3150 / 3412 only) |
| 3202–3226 | sinks into `iai_crouch` (`PZ.key_pose(sh, 3226, "iai_crouch")` = the S05 `elder_iai_crouch` numbers on his rig: hips −0.13, right foot 0.33 forward, spine 14 / chest 8, head level on the elder); the right foot slides forward (suriashi) 3204–3214: root (0, −6.00) → (0, −5.90) |
| 3206–3214 | right hand to the hilt: controller on `CH.sheathed_ctrl_matrix(sh, f)` keyed at 3208 and 3214, `CH.set_arm_mode(sh, 3208, "ik", blend=6)`, `CH.auto_elbow(sh, 3214, "R")`, `CH.auto_elbow(sh, 3214, "L")` ( iai-grab wrists R 51/−84, L 58/−19) |
| 3226–3232 | absolute stillness (breath held); the tails hang (secondary override from 3226, D10) |
Elder off-screen: `jodan`, still.

**Clashes.** none.

**Environment.** `ENV.set_sun(3197, 262.0, 26.0)` (key 30° off the lens axis, behind him: rim on the shoulder line, hood of the head, hanging tails; backlit rain). Wind 0 (held since 3073). Tail override registration (D10):
```python
LT.secondary_override("SHINOBI_rig", 3226, 3264, bones=[f"tail{t}.{i}" for t in (1, 2) for i in (1, 2, 3, 4)])
_local_hang_tails(sh, 3226, 3256)     # §5: key the 8 tail bones so both tails hang 11° back (tips clear the hakama)
```
**VFX.** none new (near rain pool: focus at 6.2 m < 12 m).

**Events.** `EV.emit(3205, "step", who="shinobi", strength=0.2)` (suriashi, the right foot slides forward).

**Notes.** Same side and same stance as the elder's S05 — the audience should recognise the silhouette. Keep the head level and still from 3214 on (no eye acting exists; stillness is the acting).

### S24e — 3233–3264 (32 f) — the drop (the clock of the duel)
**Purpose.** A water drop gathers at the tip of his soaked headband tail. Everything waits for it. It falls (3250), the frame is empty for a breath, the drip sounds from the puddle (3256) — and he is gone: body and tail tear out of the frame (3257), the elder's charge is heard (3258). (D3: the puddle hit and the elder's launch are sound-only.)

**Camera — locked ECU of the tail tip from +X, 0.5 m, 100 mm.**
```python
T = Vector((0.03, -6.07, 0.92))        # tip of tail2 (his right tail) in the S24d/e override hang (see §5 _local_hang_tails)
C.shot("S24e", 3233, 3264, keys=[(3233, (0.53, -6.07, 0.935), T + Vector((0.0, 0.0225, -0.012)), 100.0)],
       dof=dict(focus=0.50, fstop=2.8), subjects=["shinobi"], framing="ecu", clip=(0.02, 500.0))
```
Pitch −3.1°, yaw 272.6° (looking −X); frame at the tip 0.18 × 0.077 m. Screen: tail tip (−0.25, +0.31), the drop under it (−0.25, +0.16); his hakama (the seat of it, y ≥ −6.04 — screen-right is +Y looking −X) fills the right third; the left two-thirds = the far field, fully out of focus (f/2.8 at 0.5 m), rain streaks in the focus slab. Heads off-screen (shinobi (+2.9, +13), elder far off) → QA side check SKIP; `line_side` −0.88 (+X side ✓).

**Action.**
| frames | what |
|---|---|
| 3233–3249 | the drop swells at the tip: `_local_drop` (§5) parented to bone `tail2.4` at its tail, scale 0.35 → 1.0 (radius 3.5 mm) with an ease-in, sagging 3244–3249 (z-scale 1.0 → 1.4, a neck forms); the tail hangs perfectly still (override keys) |
| **3250** | detach: the drop switches to world-space keys (`CH.snap_free`-style: copy its world matrix at 3250, CONSTANT) and falls in REAL time (not in the slow-motion window): z(f) = z0 − ½·9.81·((f − 3250)/24)², one key per frame; it leaves the frame bottom at ≈3252.7 (y −0.73 at 3252); hidden (`U.key_visible(drop, 3254, False)`). The unloaded tail tip bounces up 4 mm 3250–3253 (damped) |
| 3254–3256 | nothing moves but the rain (the held breath) |
| 3256 | the drip — off-screen (sound) |
| **3257** | LAUNCH: his hakama (right third) jerks out to screen-right: root (−0.02, −5.90) at 3257 → (−0.04, −5.84) 3258 → (−0.07, −5.70) 3259 — out of frame by 3259; body `dash` with iai hands (`sh_dash_iai`, §5); the tail lags one frame, then whips up and to screen-right (override keys 3258–3262: tail bones rotate +55° up/forward with a 2-frame chain lag), out of frame by 3260, flinging water: `_local_droplets(3258, T, direction=(0.0, 0.6, 0.8), count=24, speed=2.2, spread=35, life=10, size=0.002, seed=zlib.crc32(b"S24e:0"))` |
| 3260–3264 | the empty frame: rain and the out-of-focus field; the flung drops leave the frame |
Elder (off-screen): launches at 3258 in `jodan` (`el_charge_jodan`, §5), roots per the shared blocking table.

**Clashes.** none.

**Environment.** `ENV.set_sun(3233, 268.0, 22.0)` (key 25° off the lens axis from behind the tip: the drop is backlit — a bright refracted point with a dark rim). Clearance default (the lens is 0.5 m from the tip). Wind 0.

**VFX.** `_local_drop` (§5), the tail flick droplets above; the near rain pool (focus 0.5 m).

**Events.**
```python
EV.emit(3256, "drip", pos=(0.03, -6.10, 0.0), tags=["drip"])          # audio extension type (events.KNOWN_TYPES)
EV.emit(3257, "dash", who="shinobi", strength=1.0)
EV.emit(3258, "dash", who="saint", strength=1.0)
EV.emit(3259, "step", who="shinobi", strength=0.8); EV.emit(3261, "step", who="saint", strength=0.8)
```
Nothing may be emitted in 3265–3276 (the white silence; see S25).

**Notes.** The tail tip must be exactly where the camera aims: keep the override (D10) — the secondary sim alone lets the wet tails hang through the hakama (it collides with head/chest spheres only). If the override is dropped, aim the camera at the evaluated `tail2.4` tail at 3233 after the secondary pass instead (and re-check the framing).

### S25a — 3265–3270 (6 f) and S25b — 3271–3360 (90 f) — the pass (one image, two camera markers)
**Purpose.** The lightning: 3265–3268 the only pure-white frames of the film (and total digital silence). Out of the white, two black silhouettes on white meet (3269) and pass through each other (3270) — the shinobi's iai draw-cut — and from 3271 they stand back to back, frozen, while the storm image slowly returns (by 3300), the rain hanging at 1/8 speed, the grass frozen. The thin blade ring (3277) and the late thunderclap (3300) are the only sounds of the cut. Nobody knows who won — that is the point of the hold.

**Why two markers on one framing.** S25a and S25b are the SAME camera (same keys, same lens) — no visible cut. The marker at 3271 exists because both roots jump 2–3 m between 3270 and 3271 (D2): the secondary-motion springs reset at every marker with a settled 24-f pre-roll (); without that reset the jump would read to the springs as a ~380 m/s velocity inside the 1/8 slow motion and the tails/beard/cord would explode. Characters' root keys at 3270 are CONSTANT (pipeline rule 2).

**Camera — the S05 axis at y −1.20 (D1), locked; a thunder tremor at 3300.**
```python
look_z = 2.10 + 52.0 * math.tan(math.radians(1.45))                    # 3.416
for cut, f0, f1 in (("S25a", 3265, 3270), ("S25b", 3271, 3360)):
    C.shot(cut, f0, f1, keys=[(f0, (52.0, -1.20, 2.10), (0.0, -1.20, look_z), 135.0)],
           dof=dict(focus=52.0, fstop=5.6), subjects=["shinobi", "saint"], framing="wide")
C.impact_shake(3300, strength=0.12, duration=14)                      # on S25b: a 0.14° tremor with the thunderclap
```
| frame | shinobi head | fig / above grass | elder head | fig / above grass | rule |
|---|---|---|---|---|---|
| 3265 (white) | (−0.31, −0.71) | 24.2 / 6.5 %H (dashing, low) | (+0.28, −0.61) | 29.4 / 11.5 %H | before swap: side sin −0.981 ✓, order ✓ |
| 3269 contact | (−0.07, −0.72) | 23.7 / 6.0 | (+0.07, −0.62) | 29.0 / 11.0 | ✓ (silhouettes touching) |
| 3270 overlap | (−0.01, −0.72) | 23.4 / 5.7 | (+0.01, −0.67) | 26.7 / 8.8 | ✓ (S25a last frame: shinobi still ≤ elder) |
| 3271 tableau | (+0.34, −0.65) | 27.1 / 9.4 | (−0.35, −0.60) | 30.0 / 12.0 | after swap: side sin +0.987 ✓, order ✓ |
| 3300, 3360 | same | | same | | ✓ |
The blades meet at ≈ (0.0, −1.30, 1.30) → NDC (−0.01, −0.72): dead centre, just above the grass line (y −0.80). Horizon y −0.45. Back to back from 3271: a 0.69-wide gap of empty field between the two heads.

**Action.**
| frames | shinobi | elder |
|---|---|---|
| 3265–3268 (white) | dash continues (roots in the shared table); the draw begins inside the white: `PZ.key_pose(sh, 3266, "iai_draw_1")`, `CH.set_weapon_state(sh, 3268, "drawn")` with the controller on `sheathed_ctrl_matrix(sh, 3268)`, `PZ.key_pose(sh, 3268, "iai_draw_2")`, `CH.key_saya(sh, 3268, 0.10, 60.0)` (saya-biki) | the charge closes, blade still high: `el_charge_jodan` (§5) |
| **3269** | `pass_contact_sh` = `iai_cut` (one-handed horizontal from the left hip, arm driving forward-right, deep lunge; head 1.30 m) at root (−0.35, −2.00) | `pass_contact_el` = `overhead_strike` (shomen at head height, arms extended) at root (0.35, −0.46) |
| **3270** | `pass_overlap_sh` = `iai_follow` (blade swept out to his right, chest open) at (−0.35, −1.55) — **CONSTANT** | `pass_overlap_el` = `overhead_follow` (blade driven down, trunk folded) at (0.35, −0.80) — **CONSTANT** |
| **3271–3360** | tableau `sh_zanshin_pass` (§5) at (−0.25, 1.10), facing 180: knees bent, trunk upright, right arm extended back-right at shoulder height, blade horizontal pointing back-right (world dir ≈ (0.45, −0.89, 0.0)), **one-handed**; left hand at the saya mouth (`set_left_hand(sh, 3271, "saya")`); saya-biki released (`key_saya(sh, 3271, 0, 60)`) | tableau `elder_zanshin_high` (§5) at (0.30, −3.50), facing 0: fists 1.22 m in front of the belly (world grip (0.40, −4.00, 1.22)), blade 10° below horizontal pointing forward-left (dir (0.38, −0.91, −0.17)), **two-handed**, knees bent, head level |
| 3271–3360 | absolutely still — held breath. Only fx-time secondary motion (tails, sleeves) and the rain move | same (beard, cord, sleeves hang; wet) |
Keys at 3271 and 3360 identical (the NLA holds the tableau into S26a).

**Clashes.** One: **the pass** at ≈3269.5, contact ≈ (0.0, −1.30, 1.30), sword/sword, a decisive **cut-through**: the shinobi's draw-cut notches through the elder's blade 0.33 m below its tip (it will fall away at 3412) and severs the beard cord (it will fall at 3414). No sparks, no `moves.clash`, no clash event (inside the white silence; the mix places the thin blade ring at the `blade_ring` cue and would replace it with a clash sound if a clash/draw/sword_break event sat within ±3 f of 3277).

**Environment — the white-out (D7): compositor white 3265–3268, then an env snapshot that makes every camera-ray surface white and every lit surface black, fading back to the storm 3277 → 3300.**
```python
RS.key_white_flash(3265, 1.0, duration=4)          # compositor Flash factor 1.0 on 3265-3268, 0 on 3264 / 3269 (FULL_WHITE)

W_SKY = 1.0                                         # (tune, see acceptance) scene-linear white of sky + aerial haze
def _local_whiteout(f):                             # all CONSTANT keys through the public API, keyed under the white
    for n in ("sky_zen", "sky_mid", "sky_hor"):
        ENV.set_param(f, n, (W_SKY, W_SKY, W_SKY))
    for n, v in (("sky_str", 1.0), ("glow_str", 0.0), ("disk_vis", 0.0), ("star_str", 0.0), ("cloud_alpha", 0.0),
                 ("amb_str", 0.0),                  # lighting rays see no world light (world = camera-ray sky / lighting-ray ambient)
                 ("haze_dist", 2.0), ("haze_max", 1.0),   # aerial perspective -> every env surface >= ~10 m away IS the white sky
                 ("fog_den", 0.0), ("mtn_glow", 0.0), ("gobo_cover", 0.0),
                 ("key_pow", 0.0), ("fill_pow", 0.0), ("bounce_pow", 0.0)):
        ENV.set_param(f, n, v)
    ENV.set_param(f, "fog_emit", (0.0, 0.0, 0.0))
_local_whiteout(3265)
ENV.set_sun(3265, 270.0, 26.0)                      # the storm key for the image that returns (behind the pair, 25° off the axis)
ENV.set_state(3277, "storm_night", blend_frames=23) # keys the white-out values at 3277 (SINE) -> storm_night at 3300
ENV.set_wind(3269, 0.0, interp='CONSTANT')
ENV.grass_effect("freeze", {}, 3269, 3456)          # the wind clock stops: grass frozen through S25-S26
# D6 - VFX objects of other lanes that would glow / veil on the white: hidden 3265-3276, visible from 3277
RAIN_AND_STEAM = [ob for ob in bpy.data.objects
                  if any(c.name in ("VFX_rain", "VFX_steam", "VFX_smoke", "VFX_fire", "VFX_embers") for c in ob.users_collection)
                  and _window_overlaps(ob.get("vfx_window"), 3265, 3276)]   # no window prop -> include
_local_hide(RAIN_AND_STEAM, 3265, 3277)             # key_visible True at 3073, False at 3265, True at 3277 (lights included)
```
What each frame shows:
- **3265–3268**: pure white (compositor 1.0 → linear 16 → display white). The only FULL_WHITE frames.
- **3269–3276**: a pale, even white field (sky, clouds, mountains, far field and the grass in front of the figures are all "sky" through the 2 m haze distance) and two pure black silhouettes cut off at the white grass tops — nothing is lit (no lamps, no ambient), the characters' own materials take no aerial haze. No rain, no steam (hidden), no fog.
- **3277–3300**: the white drains out of the world (SINE) — sky and haze darken to the storm, the moon key and ambient come back, the silhouettes regain rim light; the rain reappears on 3277, hanging (1/8 speed) as short dark strokes that turn silver as the key returns; the steam band glows again behind them.
- **3300–3360**: the storm image, frozen tableau, slow rain; the thunder tremor 3300–3313. Acceptance (preview render of 3265–3310, `src/tools/flash_qc.py --start 3255 --end 3320`): frames 3269–3276 mean linear luminance **0.60–0.70** (tune `W_SKY`; start 1.0, AgX + LOOK + vignette decide the exact value), never > 0.92 (hard FAIL outside FULL_WHITE); the silhouettes' interior ≤ 0.05; 3277–3300 monotonic decrease (no frame-to-frame rise).

**VFX.** None added. (No blade trail in the pass: an additive trail is invisible on white and would only draw a glowing seam through the black silhouettes.) The rain is act2's curtain: from 3269 the film clock runs at 1/8 (TIME_WARP), so when it reappears at 3277 it hangs — elongated drops, never snow (vfx notes, sheet `rain_s25`).

**Events.**
```python
EV.emit(3265, "music_cue", cue="white_silence")      # every stem, rain included, to digital zero until blade_ring
EV.emit(3269, "slowmo", duration=188)                # 3269-3456 (frames)
EV.emit(3277, "music_cue", cue="blade_ring")         # the mix synthesises the thin ring here (no other sound event 3274-3280)
EV.emit(3300, "music_cue", cue="final_pass")         # the unified hit + huge tail; rain returns low-passed
EV.emit(3300, "thunder", distance="near", pos=(-400.0, -1.2, 300.0), tags=["final_pass"])   # ahead of the lens: pan ~0
```
No event may be emitted in 3265–3276 (reverb tails would leak past the silence).

**Notes.**
- 180° rule: the camera never moves; the swap is by action (config swap_frame 3271 = S25b's first frame).
- The crossing must read in two frames: 3269 two shapes touching blade to blade, 3270 one merged shape with both blades out of it (heads at the same x), 3271 two shapes apart, back to back. Motion blur: 3269's shutter (3269 → 3269.5) smears the charge; 3270 and 3271 are sharp (CONSTANT roots at 3270; S25 mb_steps 3 in `config.SHOT_RENDER`).
- Silhouette purity depends on unlit character materials: if a material glows (the shinobi's slightly emissive headband red, DIRECTION §6) or fast GI lifts the torsos above 0.05, apply fallback F2 (§7: holdout mix).

### S26a — 3361–3428 (68 f) — the slow noto in front; click #3 = the snap (3412); the cord (3414)
**Purpose.** Still in slow motion. In the foreground the shinobi, his back to the master, sheathes — slowly, head bowed. Behind him the master stands frozen with his blade held out. The guard clicks home — and on that exact frame the master's blade breaks: the tip falls away, spinning. Two frames later the vermilion cord drops from his beard with a thin wisp of red. The audience learns who won from the steel, not from blood.

**Camera — locked deep 3/4 from +X/+Y (in front-right of the shinobi, behind-left of the elder), 40 mm; rack focus.**
```python
C.shot("S26a", 3361, 3428, keys=[(3361, (2.00, 4.50, 1.40), (-0.20, -1.30, 1.15), 40.0)],
       dof=dict(focus=3.85, fstop=2.8, distance_keys=[(3361, 3.85), (3398, 3.85), (3410, 8.8), (3428, 8.8)]),
       subjects=["shinobi", "saint"], framing="medium")
```
Pitch −2.3°, yaw 200.8° (world +X runs screen-LEFT in this view); horizon y +0.21.

| frame | shinobi head | fig / above grass | elder head | fig / above grass | rule |
|---|---|---|---|---|---|
| 3361 | (+0.52, +0.35) | 107 / 37 %H (waist-up, foreground) | (−0.35, +0.36) | 56 / 23 %H (background) | after swap: side sin +0.650 ✓, order ✓ (shinobi screen-right) |
| 3412 | (+0.52, +0.42) | 111 / 41 %H | (−0.35, +0.36) | | ✓ |
| 3428 | (+0.51, +0.43) | | (−0.35, +0.36) | | ✓ |
Points: the shinobi's koiguchi (+0.48, −0.36) (the sheathing reads low right, in focus); the elder's blade break (−0.47, +0.05) and tip end (−0.51, +0.02) — the blade sticks out of his silhouette to screen-left; the tip piece at 3428 (−0.54, −0.28); the cord (−0.36, +0.20) — behind his chest until it drifts out to screen-left. Rack focus 3398 → 3410 (3.85 m → 8.8 m): the click happens soft, the snap happens sharp.

**Action.**
| frames | shinobi (−0.25, 1.10), facing 180 — one-handed, left hand on the saya | elder (0.30, −3.50), facing 0 — two-handed |
|---|---|---|
| 3361–3370 | from the tableau the blade comes down and out to his right: `PZ.key_pose(sh, 3370, "sheathe_slow_chiburi")` (a slow chiburi — the rain has washed the steel) | frozen `elder_zanshin_high` |
| 3370–3384 | `PZ.key_pose(sh, 3384, "sheathe_slow_1")`: back of the blade laid across the left fist, kissaki at the koiguchi, head bowed (look_pitch 14) | frozen |
| 3384–3412 | the slide on the controller along the saya axis (S24b recipe): s = 0.70 (3384) → 0.35 (3398, `sheathe_slow_2`) → 0.06 (3406) → 0.01 (3410) → **0 at 3412** (LINEAR on the last 4 f); `CH.set_weapon_state(sh, 3412, "sheathed")`, `PZ.key_pose(sh, 3412, "sheathe_done")` | frozen |
| **3412** | the click | **`CH.set_weapon_state(el, 3412, "broken")`**, `CH.snap_free("SAINT_katana_tip_broken", 3412)`, then `_local_toss_fx("SAINT_katana_tip_broken", 3412, 3440, p0=<snap>, v0=(2.27, −1.42, −6.21), spin_axis=<horizontal ⟂ blade>, spin_deg=440)` — the tip sinks and tumbles down to screen-left (plants 3440 in S26b) |
| 3413–3428 | `CH.set_arm_mode(sh, 3413, "fk", blend=8)`; the right hand leaves the hilt and hangs; head stays bowed; `relaxed_saya` by 3428 | 3414: `CH.set_beard_cord(3414, True)`, `CH.snap_free("SAINT_beard_cord_cut", 3414)`, `_local_toss_fx("SAINT_beard_cord_cut", 3414, 3470, p0=<snap>, v0=(3.0, −0.4, 0.6), g_scale=0.35, spin_deg=220)` (a cord drifts, it does not drop like steel); 3414–3456: the arms sink 8 cm (the weight of the lost tip), nothing else |
Tip flight on the film clock (D5): p0 = tip CoM (0.67, −4.64, 1.10) at 3412 → (0.86, −4.76, 0.55) at 3428 → CoM (1.00, −4.85, 0.09) at 3440 (Δfx 0.146 s; v0 fx (2.27, −1.42, −6.21) m/s, |v0| 6.8 — the snap's spring-back flick; on screen ≈ 3 cm per film frame).

**Clashes.** none (the break is the pass's delayed consequence).

**Environment.** `ENV.set_sun(3361, 212.0, 28.0)` (32° off the lens axis, behind the elder: rim on both silhouettes, the steam band glowing behind the elder). Clearance default 1.5/4.0. Freeze + wind 0 continue (the grass does not move), rain hangs at 1/8.

**VFX.**
```python
VFX.red_mist(3414, (0.30, -3.72, 1.38), direction=(1.0, -0.15, 0.12), seed=zlib.crc32(b"S26a:0"))
# the thin vermilion wisp from the cut cord (cord colour, not blood): drifts ~0.5-1 m toward +X = screen-left by 3456
```
Optional (look-dev): a single cold glint on the break face at 3412 (`_local_glint` as act1a §5, peak 0.8, 3 real frames, size 0.01) — no sparks (spark pools cool to red and would hang for seconds in the slow motion).

**Events.**
```python
EV.emit(3412, "sheathe", who="shinobi", tags=["sheathe"])
EV.emit(3412, "tsuba_click", target="SHINOBI_saya", who="shinobi", tags=["tsuba_click", "click_motif_3"])
EV.emit(3412, "sword_break", pos=(0.61, -4.49, 1.13), tags=["sword_break"])     # the break point
EV.emit(3414, "cord_cut", pos=(0.30, -3.72, 1.38), tags=["cord_cut"])
```
**Notes.** 3412 is sacred: the click (sheathe + tsuba_click), the weapon state 'broken' and the tip's first free frame all on 3412 (REQUIRED beats ±8, the score answers at 3412 + 0.35 s). The cord + mist leave the elder's silhouette on his LEFT (+X) side — the side of the cut's sweep — so they read against the glowing steam band, not against his dark back.

### S26b — 3429–3456 (28 f) — the tip plants in the earth (3440)
**Purpose.** An insert at grass-root level: the spinning tip falls into the frame and stabs point-down into the mud, quivering in slow motion among frozen grass stems and hanging rain. It sets up the last image of the film (S29).

**Camera — locked low insert, 0.30 m high, 1.2 m from the landing point, 50 mm.**
```python
C.shot("S26b", 3429, 3456, keys=[(3429, (2.15, -5.20, 0.30), (1.00, -4.87, 0.12), 50.0)],
       dof=dict(focus="SAINT_katana_tip_broken", fstop=2.8), subjects=[], framing="insert", clip=(0.02, 500.0))
```
Pitch −8.6°, yaw 286.0°; the horizon sits at the top edge (y +0.98): ground, stems and hanging drops only. Tip on screen: 3430 (+0.12, +1.87) and 3434 (+0.09, +1.11) above the frame → enters at the top ≈3435 → 3438 (+0.06, +0.28) → planted 3440: CoM (+0.04, −0.15), top (+0.20, +0.70), base in the mud (−0.08, −0.62). The standing elder's legs (+1.27, +1.27) and both heads are out of frame at 3429 and 3456 (elder head (+1.43, +5.42), shinobi head (+3.95, +3.18)); `line_side` +0.244 (+X side ✓; QA side check: SKIP, no head in view).

**Action.** The tip only: the fx-time toss ends at 3440 (last key CONSTANT: planted point-down, 7 cm deep, leaning 20° toward the lens-right, top at (1.06, −4.80, 0.25)); 3440–3456 a slow quiver about its base (rotation keys 3440 0°, 3443 +4°, 3448 −2.5°, 3453 +1°, 3456 0° — a 20 Hz ring at 1/8). The elder (off-screen) stands frozen; the shinobi (off-screen) stands with his head bowed, the right hand at his side.

**Clashes.** none.

**Environment.** `ENV.set_sun(3429, 290.0, 30.0)` (the key from behind the tip: a cold line of light along the steel's edge and the wet mud). Clearance default (the tip is 1.2 m from the lens: it stands in a bare patch; the frozen grass wall starts 0.3 m behind it). Freeze continues to 3456.

**VFX.** `_local_droplets(3440, (0.98, -4.90, 0.01), direction=(0, 0, 1), count=14, speed=0.9, spread=55, life=12, size=0.0025, seed=zlib.crc32(b"S26b:0"), tint=(0.25, 0.22, 0.18))` — a few muddy beads hanging in the slow motion.

**Events.** `EV.emit(3440, "land", pos=(0.98, -4.90, 0.0), strength=0.25, tags=["blade_tip"])`.

**Notes.** The planted tip is a prop that must persist, untouched, to 3840 (S29 frames it again under the moon). No later camera shows it by accident: S27 projects it at (−0.67, −1.55) (below the frame), S28 at (−0.28, −1.07) at 3744 (below the frame, and under the grass).

### S27 — 3457–3600 (144 f) — the kneel, the rain stops, the moon, the bow (stillness beat)
**Purpose.** Real time again. One composed deep two-shot: in the foreground the master's knees give way and he kneels on his broken sword — the exact pose of the shinobi's low point (S23/HANDOFF[3072]). Behind him, his back to him, the shinobi stands. The rain thins and stops; the clouds open; a huge full moon rises over the field and its light sweeps from the far field toward us, reaching the shinobi first, then the master. The shinobi turns and bows to the master's back.

**Camera — locked low deep two-shot from +X/−Y (1.35 m high, 3.9 m from the elder), 30 mm; 3.6 cm creep.**
```python
C.shot("S27", 3457, 3600, keys=[(3457, (3.30, -6.30, 1.35), (-1.10, 0.25, 1.05), 30.0),
                                (3600, (3.28, -6.27, 1.35), (-1.10, 0.25, 1.05), 30.0)],
       dof=dict(focus=3.8, fstop=5.6), subjects=["shinobi", "saint"], framing="medium")
ENV.set_camera_clearance(3457, 3.7, 5.5)     # no grass between the lens and the kneeling master (his hands + hilt at 0.5 m read)
```
Pitch −2.2°, yaw 326.1°; deep focus (30 mm f/5.6 at 3.8 m: sharp from 2.2 m to 13 m); horizon y +0.15.

| frame | elder head | fig / above grass | shinobi head | fig / above grass | rule |
|---|---|---|---|---|---|
| 3457 | (−0.42, +0.43) standing | 88 / 35 %H | (+0.25, +0.26) | 41 / 15 %H | after swap: side sin +0.324 ✓, order ✓ |
| 3470 knee down | (−0.46, −0.03) | 67 %H | (+0.25, +0.26) | | ✓ |
| 3476 stub planted | (−0.47, −0.11) | 63 %H | | | ✓ |
| 3586 bow lowest | (−0.48, −0.12) | | (+0.21, +0.15) | 37 %H | ✓ |
| 3600 | (−0.48, −0.12) | 63 %H | (+0.24, +0.26) | 41 %H | ✓ |
Kneeling elder: hands on the hilt (−0.53, −0.76), front knee (−0.57, −0.73) — the stub runs down out of the frame bottom (into the ground below the frame). The moon (az 347°, el 9°, disk 4.2°) at **(+0.64, +0.82)**: upper right, diagonally above the shinobi — the line elder → shinobi → moon. The grass at the elder is ≤ 22 % height (clearance ring 3.7–5.5 m), so he kneels in a trampled patch (the fighting ground); the shinobi stands waist-deep at 8 m. The framing QA may WARN "saint clipped > 30 %" (his lower body is out of frame on purpose).

**Action.**
| frames | elder (0.30, −3.50), facing 0 | shinobi (−0.25, 1.10) |
|---|---|---|
| 3457–3461 | stands in the tableau (arms already 8 cm lower since S26a), the stub in both hands | stands, facing 180 (back to the elder), `relaxed_saya`, head bowed 8° |
| 3462–3470 | the knees give with the score's "sigh" (≈3462): 3462 knees bend (hips −0.10), 3466 hips −0.30, **3470 right knee on the ground** (`elder_kneel_broken`, §5; `M.kneel(el, 3462)` if its timing matches) | — |
| 3470–3476 | the stub is brought down point-first; **3476 planted** 5 cm into the ground in front of the left foot at (0.30, −3.98); both fists on the hilt at 0.50 m; `CH.auto_elbow(el, 3476, "R")`, `CH.auto_elbow(el, 3476, "L")` | — |
| 3476–3600 | head bows further (neck 25, head 20 by 3490); still; slow breath (chest X ±0.6°, period 72 f) | 3505–3525 lifts his head toward the opening sky (head pitch −8° → +4°), level again by 3545 |
| 3552–3568 | — | turns in place 180 → 90 → 0 (to his right, i.e. toward the camera side); feet: 3556 right pivots, 3566 left closes (`legs` keyed; root stays at (−0.25, 1.10)) |
| 3570–3600 | — | the bow: `CH.set_left_hand(sh, 3570, "free", blend=6)`, `PZ.key_pose(sh, 3582, "bow")` (trunk 30°, hands along the thighs), held to 3592, upright by 3600 (`relaxed_saya` again: `CH.set_left_hand(sh, 3598, "saya", blend=4)`) |
The bow is to the master's BACK — he does not see it (he faces −Y, head bowed). Nobody speaks, nothing is explained.

**Clashes.** none.

**Environment — storm → moon (the default timeline, re-keyed in the lane strip) + the moonlight sweep.**
```python
ENV.set_state(3457, "storm_night")                           # snapshot on the cut
ENV.set_sun(3457, 347.0, 9.0, disk_deg=4.2)                  # the moon: key + disk (invisible until the blend), on the cut
ENV.set_state(3470, "moon_clear", blend_frames=80)           # clouds part 3470 -> 3550 (disk, stars, silver grass)
ENV.set_wind(3457, 0.0, interp='CONSTANT')                   # still no wind (it returns in S28)
ENV.set_wetness(3457, 1.0); ENV.set_wetness(3560, 1.0)       # LINEAR from 3560 to 3640 (S28): 1.0 -> 0.55
# moonlight edge: lit where g . dir > edge, dir = the lens heading 326° (foreground -> background)
ENV.set_cloud_shadow(3457, edge=45.0, edge_dir_deg=326.0, edge_width=5.0, interp='CONSTANT')  # on the cut: the near
                                                             # field starts in cloud shadow (no pop when the sweep begins)
ENV.set_cloud_shadow(3505, edge=45.0, interp='LINEAR')       # far field lit first, the edge starts moving toward the lens
ENV.set_cloud_shadow(3528, edge=8.0)
ENV.set_cloud_shadow(3538, edge=0.5)                         # the shinobi (g.dir +1.06) is lit at ~3537
ENV.set_cloud_shadow(3547, edge=-3.6)                        # the master (g.dir -3.10) is lit at ~3546
ENV.set_cloud_shadow(3552, edge=-14.0)                       # past the lens (camera at g.dir -7.08)
ENV.set_cloud_shadow(3553, edge='off')
```
The rain thins 3470 → 3500 by itself (act2's `intensity` curve); wetness stays (moonlit wet grass glistens). No flash. Frame luminance rises slowly (storm ≈ 0.03 → moonlit ≈ 0.10 over 45 f): a ramp, not a flash (§4).

**VFX.** None required. (tune/optional, look-dev) a thin ground mist catching the moon from 3490: `VFX.steam(3490, 3840, (0.3, 0.0, 0.0), 16.0, height=1.0, density=0.10, rise=0.12, seed=zlib.crc32(b"S27:0"))` — only if it does not veil the kneeling master (preview 3560).

**Events.**
```python
EV.emit(3470, "kneel", who="saint", tags=["kneel"])
EV.emit(3470, "rain_stop")                                     # the audio rain fades over 1.6 s, drips follow
EV.emit(3476, "hit", pos=(0.30, -3.98, 0.05), strength=0.3, tags=["plant_blade"])
EV.emit(3505, "music_cue", cue="epilogue")                     # with the moonlight
EV.emit(3556, "step", who="shinobi", strength=0.3); EV.emit(3566, "step", who="shinobi", strength=0.3)
```
**Notes.** The two knee-down poses rhyme on purpose (DIRECTION §7): same knee, same stub/blade in front, same bowed head. The moon disk must not touch the frame edge (its centre at (+0.64, +0.82), radius ≈ 0.10 in x at 30 mm).

### S28 — 3601–3744 (144 f) — the crane: he walks away toward the moon; the master is the still point
**Purpose.** From the master's bowed head the camera rises and pulls back: the shinobi walks away into depth, screen-right, toward the low full moon; the grass parts around him and closes behind him (the bookend of S03). The master stays kneeling — the still point of a moving sea: the wind returns and silver waves roll through the grass.

**Camera — crane up + pull back + zoom out (50 → 24 mm), eased, the elder kept in frame throughout.**
```python
C.shot("S28", 3601, 3744, keys=[(3601, (1.55, -4.85, 1.05), (saint_rig, "head"), 50.0),     # MCU of the bowed head
                                (3672, (2.70, -7.90, 2.30), (0.55, 0.20, 1.05), 32.0),
                                (3744, (4.30, -12.30, 4.50), (0.95, 5.20, 1.60), 24.0)],
       dof=dict(focus=1.66, fstop=2.8, fstop_keys=[(3601, 2.8), (3650, 8.0)],
                distance_keys=[(3601, 1.66), (3640, 6.0), (3744, 12.0)]),
       subjects=["saint"], framing="wide")        # the shinobi is off-screen right until ~3622 (not a listed subject)
```
BEZIER keys (slow in, slow out); 8.2 m of travel, 3.45 m of rise in 6 s.

| frame | camera (x, y, z) / lens | elder head | shinobi head | moon (350°, 3.5°) | horizon y | rule |
|---|---|---|---|---|---|---|
| 3601 | (1.55, −4.85, 1.05) / 50 | (0.00, 0.00) MCU (fig 238 %H) | off-screen (+1.74) | off (+2.25) | −0.17 | side sin +0.181 ✓ |
| 3614 | (1.65, −5.12, 1.16) / 48 | (−0.33, −0.02) | off (+1.08) | off (+1.43) | +0.21 | ✓ |
| 3630 | (1.97, −5.96, 1.51) / 43 | (−0.59, −0.26) | (+0.43, +0.68) 61 %H — walking away | top edge (+0.58, +0.98) | +0.61 | ✓ order ✓ |
| 3650 | (2.44, −7.20, 2.01) / 36 | (−0.53, −0.44) | (+0.19, +0.47) 39 %H | (+0.24, +0.96) | +0.66 | ✓ |
| 3672 | (2.70, −7.90, 2.30) / 32 | (−0.47, −0.46) 53 %H | (+0.18, +0.38) 30 %H | (+0.15, +0.89) | +0.62 | ✓ |
| 3710 | (3.57, −10.28, 3.49) / 28 | (−0.39, −0.62) | (+0.12, +0.15) 19 %H | (+0.05, +0.80) | +0.57 | ✓ |
| 3744 | (4.30, −12.30, 4.50) / 24 | (−0.32, −0.62) 20 %H | (+0.10, +0.05) 13 %H | **(+0.02, +0.71)** | +0.51 | ✓ |
The final image: the master small, lower-left, kneeling; the shinobi walking up the frame straight into the moon, which sits on the horizon above him; the silver grass sea between them.

**Action.**
| frames | shinobi | elder |
|---|---|---|
| 3601–3614 | turns 0 → 90 → 160.6 (to his left, toward the camera side) in place, steps 3605 / 3611 | kneeling, still (the still point), beard stirring in the returning wind |
| 3614–3744 | `M.walk(sh, 3614, 3744, (-0.20, 1.18), (2.00, 7.50), upper="relaxed_saya", stop=False)` (still walking on the cut; not seen after it) — 6.8 m at 1.26 m/s (the prologue's measured pace), facing 160.6 (toward the moon); left hand on the saya, right arm swinging ±12°, head level — he never looks back | still |
The grass parts around him and closes behind him: request the parting wake for this span (`environment.bake_wake`, run by build_scene after `assemble_nla` — the lane cannot bake it; see §7 open item). His tails lift again in the wind (DIRECTION §7): wetness 1.0 → 0.55 over 3560–3640 lightens the springs.

**Clashes.** none.

**Environment.**
```python
ENV.set_sun(3601, 350.0, 3.5, disk_deg=4.8)                  # the low huge moon on the horizon (key clamped to 2.5° min)
ENV.set_wind(3601, 0.0, direction_deg=170.0)                 # LINEAR ramps (heading 170: toward -Y, back toward the lens)
ENV.set_wind(3625, 0.7); ENV.set_wind(3650, 1.1); ENV.set_wind(3668, 1.4); ENV.set_wind(3690, 1.0)
ENV.set_wind(3715, 1.3); ENV.set_wind(3744, 1.0)
ENV.set_wetness(3640, 0.55)                                  # (from 1.0 at 3560, LINEAR)
ENV.set_camera_clearance(3601, 1.5, 4.0)
```
The gust bands roll toward the lens, backlit by the moon ahead (silver waves). moon_clear holds (from 3550).

**VFX.** none (the optional ground mist from S27 continues).

**Events.**
```python
EV.emit(3605, "step", who="shinobi", strength=0.3); EV.emit(3611, "step", who="shinobi", strength=0.3)
# + the steps emitted by M.walk (who="shinobi", strength ~0.35: grass)
EV.emit(3610, "wind_gust", strength=0.5); EV.emit(3680, "wind_gust", strength=0.35)
```
**Notes.** S27 → S28 is not a jump cut: 30 mm two-shot → 50 mm MCU of the master from 30° further round. Keep the elder's head fixed on the lower-left third after 3630 (the still point); the crane must feel inevitable, not showy.

### S29 — 3745–3840 (96 f) — still life: the broken tip in moonlit grass; bell + "End" (3758)
**Purpose.** The last image: the tip of the master's sword standing where it fell, wet steel catching the moonlight, grass and plumes stirring around it. The bell; the "End" glyph writes itself in the centre; the picture fades to black.

**Camera — locked low still life, 0.40 m high, 2.2 m from the tip, 35 mm.**
```python
C.shot("S29", 3745, 3840, keys=[(3745, (2.95, -3.55, 0.40), (0.89, -5.73, 0.40), 35.0)],
       dof=dict(focus="SAINT_katana_tip_broken", fstop=4.0), subjects=[], framing="insert")
ENV.set_camera_clearance(3745, 2.6, 4.6)      # the tip stands in a bare patch, the grass wall rises behind it
```
Pitch 0.0°, yaw 223.4°; horizon y 0.00. Tip top **(+0.45, −0.31)**, base in the mud (+0.42, −0.78) — lower right, outside the end card's backdrop ellipse (centre (0, +0.083), radii 0.261 × 0.463: (0.45/0.261)² + (0.393/0.463)² = 3.7 > 1). The kneeling master is out of frame (head x +1.75), the shinobi is behind the camera, the moon's disk is out of frame (key at (+0.58, +2.13)). Above the tip: grass stems rising (2.6 → 4.6 m), plume heads from y ≈ +0.4 up, a band of starry sky at the top.

**Action.** None — the tip does not move. Only the grass and plumes sway (wind 0.6) and the light is still. Optional (look-dev): `_local_glint(obj="SAINT_katana_tip_broken", f0=3752, f1=3786, peak_frame=3760, peak=0.9, size=0.012)` — one slow cold glint travelling up the edge with the bell.

**Clashes.** none.

**Environment.**
```python
ENV.set_sun(3745, 240.0, 24.0)                                   # key 29° off the lens axis from behind the tip (disk out of frame)
ENV.set_wind(3745, 0.6, direction_deg=170.0)                     # LINEAR down from S28's 1.0
```
**VFX.** none.

**Post (not rendered by the lane).** Render 3745–3810 at full brightness — **no render-side fade** (`assemble.py` owns the picture fade 3770 → 3811, `FADE_START` 3770, `--fade auto`); 3811–3840 are black (`config.RENDER_SKIP`). The "End" title (3758–3840) is overlaid by post over the fading picture, then over black.

**Events.**
```python
EV.emit(3746, "wind_gust", strength=0.2)
EV.emit(3758, "music_cue", cue="end_card")
EV.emit(3758, "bell", pos=(0.0, 60.0, 5.0), tags=["end_card"])  # REQUIRED beat ±3 (the score's bell is merged with it)
```
**Notes.** The frame must stay calm and dark enough for the ivory title (mean luminance ≈ 0.05–0.10); nothing bright inside the backdrop ellipse (no moon, no specular hot spot) — if the tip's glint lands inside it, move the key azimuth, not the title.

## 4. Flash schedule + budget proof

The lane has **one light event** — the lightning of the pass — and no `environment.flash`, `vfx.lightning_bolt`, `vfx.strobe` or `vfx.env_flash` call anywhere (DIRECTION §5: no flash in S24; the thunder at 3300 is sound only). Strength = mean frame luminance as full-frame-white equivalent (linear, as `src/tools/flash_qc.py` measures it).

| frames | what makes the light | strength | duration | rule status |
|---|---|---|---|---|
| 3073–3264 | storm ambience only (no lightning) | ≈ 0.02–0.04 | — | S24: no flash ✓ |
| **3265–3268** | `RS.key_white_flash(3265, 1.0, duration=4)` (compositor → linear 16 → display white) | **1.00** | 4 f (CONSTANT) | `config.FULL_WHITE` (3265, 3268) — the only full white ✓ |
| 3269–3276 | the white-out field (env snapshot: camera-ray sky + aerial haze = `W_SKY`), black silhouettes | **0.60–0.70** (acceptance window; hard cap 0.92) | 8 f | not a new onset: luminance only falls after 3268 (1.00 → ≈0.65) |
| 3277–3300 | `ENV.set_state(3277, "storm_night", blend_frames=23)` (SINE) | 0.65 → ≈0.03, monotonic | 24 f | a single falling transition |
| 3301–3504 | storm / clearing, no lightning | ≈ 0.02–0.04 | — | ✓ |
| 3505–3553 | moonlight edge sweep + storm → moon blend | ≈ 0.03 → ≈ 0.10, a ramp over ≥ 45 f | — | a ramp, Δ < 0.10 → not a flash ✓ |
| 3554–3810 | moonlight | ≈ 0.08–0.12 (S29 ≈ 0.05–0.10 under the title) | — | ✓; post fades 3770 → 3811 |

Budget proof:
- **Onsets ≥ 12 f apart / ≤ 2 per second:** one onset in 768 f (3265). Nearest other lane flash: act3's S22 strobe ends by 2784 (S23 is "real time, no glow") → gap ≥ 480 f. Cross-lane requirement: **act3 must not flash after 3252** (12 f before 3265) — `environment.flash` refuses it anyway (FLASH_MIN_GAP), but the refusal would silently drop act3's.
- **≤ 70 % except FULL_WHITE:** 3269–3276 are held to 0.60–0.70 by the `W_SKY` calibration (§3 S25 acceptance); every other frame of the span is ≤ 0.12.
- **flash_qc counting** (≥ 10 % transitions whose darker side < 0.80; FULL_WHITE ± 1 f ignored): 3264 → 3265 (rise) and 3268 → 3269 (fall 1.00 → 0.65) are inside the ignored band 3264–3269; 3276 → 3300 is one counted falling transition; the moon ramp stays below 10 % per transition. Max counted transitions in any 24-f window: **1** (FAIL needs ≥ 7 = > 3 flashes) → PASS; the four quadrants behave the same (the white-out is uniform) → PASS; no frame outside FULL_WHITE above 0.92 → PASS; no saturated-red rise (the red mist is a few pixels) → PASS.
- **Photosensitive character of the event:** one bright plateau (12 f) with a slow 24-f decay — no flicker, no pattern.

## 5. Local poses / moves not in the SPEC macro list

**Timing rule for this lane.** `moves` macros time themselves in STORY frames (moves.py header): inside 3269–3456 (TIME_WARP 0.125) every story frame lasts 8 film frames. So: **no macro may straddle 3269** (`M.dash` for the charges ends at 3268; the pass 3269/3270/3271 is keyed explicitly), and the S26 noto is keyed explicitly (`M.sheathe(..., speed="slow")` anchored at 3412 would put its chiburi 40 story frames earlier = film ≈3247). Outside the window macros are fine (`M.stance`, `M.walk`, `M.turn`, `M.dash`, `M.kneel` / `M.bow` when they exist).

Library poses used as they are (`poses.POSES`): `kneel_sword_planted` / `kneel_planted`, `rise_kneel`, `low_1h`, `relaxed_saya`, `sheathe_quick_1`, `sheathe_done`, `sheathe_slow_chiburi`, `sheathe_slow_1`, `sheathe_slow_2`, `gedan`, `chudan`, `jodan`, `iai_crouch`, `iai_draw_1`, `iai_draw_2`, `iai_cut`, `iai_follow`, `overhead_strike`, `overhead_follow`, `dash`, `bow`, the walk cycle (via `M.walk`).

| name | used | definition |
|---|---|---|
| `sh_dash_iai` | S24e/S25a 3257–3268 | `M.dash(sh, 3257, 3268, (-0.02, -5.90), (-0.35, -2.41), start=True, stop=False, upper="iai_crouch")` — the dash legs/trunk with the iai hands riding on top (right fist on the sheathed hilt, left fist on the saya rolled 60°); root path = the shared blocking table (key it with `M.root` if the macro's trapezoid differs by > 0.1 m) |
| `el_charge_jodan` | 3258–3268 | `M.dash(el, 3258, 3268, (0.02, 2.48), (0.35, -0.12), start=True, stop=False, upper="jodan")` — two-handed, blade high; trunk pitched less than the `dash` default (lean 14, the blade must stay up) |
| `pass_contact_sh` / `pass_overlap_sh` | 3269 / 3270 | `iai_cut` at root (−0.35, −2.00) / `iai_follow` at (−0.35, −1.55), facing 180, one-handed, `key_saya(sh, f, 0.10, 60)`; roots LINEAR 3268 → 3269 → 3270, CONSTANT on 3270 |
| `pass_contact_el` / `pass_overlap_el` | 3269 / 3270 | `overhead_strike` at (0.35, −0.46) / `overhead_follow` at (0.35, −0.80), facing 0, two-handed; CONSTANT on 3270 |
| `sh_zanshin_pass` | 3271–3360 | trunk `torso(lean=4, twist=-40)`, hips (0, −0.14, 0.04), `legs=stance(front=0.36, back=0.34, width=0.30, lead="R")`, `ctrl=blade(grip=(-0.50, 0.05, 1.30), direction=(-0.45, 0.89, 0.0))` (rig space, SHINOBI m: right arm straight out to his right and a little back at shoulder height, blade horizontal pointing back-right = world (0.45, −0.89, 0) at facing 180), edge = default, `left="saya"`, `saya=(0.0, 60.0)`, `elbow={"R": "auto"}`, head level (look_pitch 0) facing +Y |
| `elder_zanshin_high` | 3271–3412 (then arms −8 cm to 3456) | trunk `torso(lean=6, twist=8)`, hips (0, −0.10, 0.03), `legs=stance(front=0.40, back=0.36, width=0.30, lead="R")`, `ctrl={"SAINT": {"grip": (0.10, -0.50, 1.22), "dir": (0.38, -0.91, -0.17)}}, "scale": False` (rig space = world offsets at facing 0: fists 1.22 m high in front of the belly, blade 10° down pointing forward-left, its break point at world (0.61, −4.49, 1.13)), `left="grip"`, `elbow={"R": "auto", "L": "auto"}` |
| `elder_kneel_broken` | 3470–3840 | `kneel_planted` with a lower grip for the 0.49 m stub: body spine 18, chest 12, neck 25, head 20 (bowed deeper); hips/legs as `kneel_planted` (SAINT-scaled); `ctrl={"SAINT": {"grip": (0.0, -0.46, 0.50), "dir": (0.0, -0.10, -1.0), "edge": (0.0, -1.0, 0.0)}}, "scale": False` (stub point 5 cm into the ground at world (0.30, −3.98)); two hands; `auto_elbow` R + L ( kneel row) |
| elder knee-down in-betweens | 3462 / 3466 | hips −0.10 (knees bend, weight down) / hips −0.30 with the right knee 0.15 m above the ground, stub still held forward (the `elder_zanshin_high` ctrl lowered to z 0.85) |
| `sh_rise_from_kneel` | 3085–3112 | keys: 3084 `kneel_sword_planted` (hold) → blade out of the mud 3086–3094 (`CH.key_sword` table in S24a; `set_two_hand(False)` 3086, left hand to the left knee) → 3094 `rise_kneel` → 3104 half-risen (hips −0.15, back foot planting) → 3112 `low_1h` |
| `sh_turn_in_place` | S27 3552–3568, S28 3601–3614 | `M.turn(sh, 3552, 3568, 0.0)` (180 → 0 through 90: to his right) / `M.turn(sh, 3601, 3614, 160.6)` (0 → 160.6 through 90: to his left) — both turn toward the +X camera side |
| `_local_noto_slide(rig, keys)` | S24b 3118–3150, S26a 3384–3412 | per key `(f, s)`: `CH.key_ctrl_matrix(ctrl, f, Matrix.Translation(-A(f) * s) @ CH.sheathed_ctrl_matrix(rig, f))`, A(f) = the saya's +Y axis in world at f; LINEAR on the last segment; `set_weapon_state(rig, f_click, "sheathed")` on the s = 0 frame |
| `_local_hang_tails(rig, f0, f1)` + whip | S24d/e 3226–3264 (under `LT.secondary_override`) | keys all 8 tail bones so each tail is a straight line from its knot to a tip 11° behind the vertical (toward −facing): per frame, target world direction d = normalize(−sin 11°·fwd − cos 11°·Z); local rotation = parent_world⁻¹ · align(bone +Y → d); keys at 3226, 3232, 3240, 3249; tail2.4 tip +4 mm bounce 3250–3253 (release of the drop); whip 3258–3262 (chain lag 1 f per segment, up to +55° up/back, then free — the sim resumes at 3265 on the S25a marker) |
| `_local_drop()` | S24e 3233–3253 | UV sphere r 3.5 mm (12 × 8), bottom half stretched 1.15 (teardrop); material `VFX_water_drop` if present else a local copy (Glossy 0.8 r 0.05 + Translucent + emission 0.08, DITHERED, no shadow); child of `SHINOBI_rig` bone `tail2.4` at its tail − 3.5 mm z; scale 0.35 (3233) → 1.0 (3249) ease-in, z-scale 1.0 (3244) → 1.4 (3249); at 3250 world keys from its evaluated matrix, then free fall in real time (z0 − ½·9.81·t², t = (f − 3250)/24), hidden from 3254 |
| `_local_droplets(frame, pos, direction, count, speed, spread, life, size, seed, tint=None)` | S24b, S24c, S24e, S26b | a fixed pool of `count` points (GN, `fxclock.drive_gn_input(ob, "Time")`): birth = frame + U[0, 1.5) f, v0 = cone(direction, spread) × speed × U[0.6, 1.3], life × U[0.7, 1.3] frames (fx time), p = p0 + v0·t + ½·g·t²; instance an icosphere of radius size × U[0.6, 1.2]; scale 0 when unborn / dead (pipeline rule 3); `VFX_water_drop` material (tint multiplies its colour for mud); `visible_shadow=False`. (If the vfx lane adds a `droplets` spawner, use that.) |
| `_local_toss_fx(obj, f0, f1, p0, v0, spin_axis, spin_deg, g_scale=1.0, rot0=None)` | S26 tip, cord | keys location + rotation EVERY frame f0..f1 (LINEAR) with t = `fxclock.fx_time_at(f) − fxclock.fx_time_at(f0)`: p = p0 + v0·t + ½·(0, 0, −9.81·g_scale)·t², rotation = rot0 · R(spin_axis, spin_deg·t/t_total); z clamped at the ground (0.02 m; the cord settles flat, the tip's last key is the planted pose); last key CONSTANT; `g_scale` < 1 = drag for the cord (a cloth strand drifts); `M.toss` may replace it if it integrates fx time |
| `_local_whiteout(f)` | S25 3265 | the env snapshot of §3 S25 (`set_param` keys, CONSTANT) |
| `_local_hide(objs, f_hide, f_show)` | S25 3265–3276 | `U.key_visible(ob, 3073, True)`, `U.key_visible(ob, f_hide, False)`, `U.key_visible(ob, f_show, True)` for each (lights included) |
| `_blade_point(base, tip, f, u)` | S24c | world point at fraction u from the base socket to the tip socket, evaluated at f inside `U.muted_modifiers()` |
| `_window_overlaps(win, a, b)` | S25 | True if the object's `vfx_window` (f0, f1) overlaps [a, b] or the object has no window property |
| `_local_glint(...)` (optional) | S26a 3412, S29 3752–3786 | as act1a §5 (camera-facing emissive card sliding along the metal, opaque DITHERED, no shadow) |

## 6. Title overlays in the span

Only one `config.TITLES` entry falls in 3073–3840: **`end`** — "End" 3758–3840, style `end`, sub = the credit line ("an original animated short, generated procedurally with Blender, original score"). (The act3 card 2521–2588 is outside the span.) Measured with `src/post/titles.py` (`out/dev/breakdown/finale/end_title_box.py`, delivery 1920×1080, picture rows 132–948, NDC of the 2.35:1 picture):

| element | position (picture NDC) | timing (film frames) |
|---|---|---|
| "End" glyph ink (Xingkai, 230 px) | x −0.101 … +0.101, y −0.161 … +0.327 (centred, cy 506 px) | written in over 3758–3784 (26 local frames) |
| soft dark backdrop ellipse | centre (0.000, +0.083), radii x 0.261, y 0.463 | fades in with the ink |
| seal ("Saku") | centre (+0.147, −0.026), 0.069 wide | impact **3788** (+ `end_seal` cue if the audio places one) |
| credit line | lower letterbox bar (y 998–1030 px), outside the picture | 3780–3792 fade-in |
| fade-out of the whole card | — | 3824 → 3840 |

How S29 leaves room: the tip stands at (+0.45, −0.31) … (+0.42, −0.78), lower right, outside the backdrop ellipse ((0.45/0.261)² + (0.393/0.463)² = 3.7 > 1) and 0.27 to the right of the seal; the moon disk and every specular hot spot stay out of the ellipse (key light from behind the tip at (+0.58, +2.13), above the frame); behind the title there are only dark grass stems, plume heads and night sky (mean ≈ 0.05–0.10), so the ivory ink reads without extra darkening. The picture itself fades to black under the card 3770 → 3811 (post, `assemble.py` FADE_START); the card finishes over black 3811–3840. The lane renders no text and no fade.

## 7. Risks + fallbacks

| # | risk | how to see it | fallback (in order) |
|---|---|---|---|
| R1 | **White-out silhouettes not black** (the headband's night emission, a glowing prop, fast-GI screen bounce from the white haze onto the torsos) | preview 3272: silhouette interior mean > 0.05 | F1 key that material's emission to 0 over 3265–3276 (if characters exposes it); **F2 holdout mix**: `_local_sil_holdout(3265, 3277)` — insert in every SHINOBI_* / SAINT_* material (bodies, costume, props, blades) a Mix Shader (fac = Attribute VIEW_LAYER `env_sil`, keyed 1 on 3265–3276, 0 elsewhere, CONSTANT) between the original surface and a Holdout shader → exact black RGB 0 with correct AA and motion blur; F3 (render_setup owner) Cryptomatte-object mask of the characters → mix to black in `SEKIRO_post` for 3269–3276 |
| R2 | White field too bright / too grey (AgX + "Punchy" + vignette + bloom) | flash_qc on 3255–3320: mean 3269–3276 outside 0.60–0.70 | tune `W_SKY` (one constant); if bloom halos eat the blades (≈6 px wide at 52 m), ask the config owner for `SHOT_RENDER["S25"]["bloom"] = 0.15` |
| R3 | The pass unreadable (one black blob for 3 frames) | preview 3268–3272 at full res | widen the lanes to x ±0.45; give 3269 a visible gap between the bodies (only the blades touch); keep 3270 as the merged frame; never add frames (config 3269–3270) |
| R4 | Secondary springs pop at 3271 despite the S25b marker | preview tails 3271–3290 | `LT.secondary_override` on tails/beard/cord 3271–3290 with hanging keys (the tableau is still anyway) |
| R5 | S24b koiguchi hidden (right thigh, hakama, left fist) | preview 3140–3156 | u = (0.69, 0.35, −0.62) (80° to the axis; still inside the focus slab at f/5.6) and/or d 0.55 m; a fist over the mouth is acceptable — the tsuba meeting it still reads |
| R6 | S24e tail tip not where the camera aims | preview 3233 | keep D10 (override); else aim with `target=` (TRACK_TO) on the `_local_drop` object so the camera follows the simulated tip, with the lens placed 0.5 m to +X of the unsimulated estimate |
| R7 | S24e's empty frame 3260–3264 reads as a mistake | cut review | whip-pan: yaw 272.6° → 330° over 3258–3264 (motion-blurred smear into the rain) — still ends on the white cut at 3265 |
| R8 | The tip's fx-time descent looks mechanical (constant slide) | preview 3412–3440 | land later: 3446 (v0z −4.8) or 3450 (v0z −4.1) — move the `land` event with it (not a REQUIRED beat); add 90° more tumble |
| R9 | The cord / red mist invisible behind the elder in S26a | preview 3414–3428 | raise the cord's v0 to (3.8, −0.2, 0.9) (it clears his silhouette earlier); `red_mist(..., speed=4.5)` |
| R10 | S24d / S27 grass clearance reads as a crater | preview 3226 / 3560 | S24d: accept the veiled fists (the arm reads) and return to 1.5/4.0; S27: cone mode toward the master (`set_camera_clearance(3457, cone_deg=14, cone_len=4.3)`) |
| R11 | The moon disk too small / too hot under AgX in S27–S28 | preview 3550, 3744 | `set_param(f, "disk_str", …)` per cut (moon_clear 2.5), `disk_deg` 4.2 → 5.0; the disk must never touch the frame edge |
| R12 | act3's last pose/position differs from HANDOFF[3072] | build QA "handoffs within 0.5 m" | the 52 m telephoto hides ≤ 0.5 m; if act3 leaves the elder in jodan, shorten S24c's lift (start it from act3's pose) |
| R13 | `moves` macros stretched ×8 by the slow-motion clock | pose keys after 3269 in the dope sheet | never straddle 3269 with a macro (§5 rule); explicit keys in S25–S26 |
| R14 | Render cost: S25 mb_steps 3 + white-out, optional S27 ground mist | render_supervisor timings | drop the optional mist first |

**Cross-lane requests / assumptions (please confirm):**
- X1 act2 owns the film rain (`vfx.rain(2376, 3500, …)`, thinning 3470–3500) and the ring's steam band (to 3456); the finale keys only their visibility 3265–3277 (D6). Alternative: act2 adds `intensity` keys (3264 1.0, 3265 0.0, 3276 0.0, 3277 1.0).
- X2 act3: no `environment.flash` / bolt after **3252**; end at HANDOFF[3072] exactly (shinobi `kneel_sword_planted` at (0, −6.0); elder standing at (0, 2.5), blade low — `gedan` preferred).
- X3 build_scene: run `environment.bake_wake(3601, 3744)` (the grass closing behind the walker in S28) after `assemble_nla`; apply `lane_tools.secondary_override` masks (S24d/e tails).
- X4 audio: nothing emitted by this lane in 3265–3276; the ring at 3277 comes from the `blade_ring` cue (mix.py places it only if no clash/draw/sword_break event lies within ±3 f).
- X5 render_setup: the compositor `Flash` node is keyed only through `key_white_flash(3265, 1.0, 4)`; nothing else in the span touches the compositor (unless fallback F3).
- X6 post: `assemble.py` fades 3770 → 3811 (`--fade auto` must detect "renders do not fade").

**Implementation order for `acts/finale.py::build(ctx)` (suggested).**
1. Entering states at 3073 (§1 table) + env lane snapshot (S24a env block) + `_local_hide` visible keys at 3073.
2. Shinobi: kneel hold → rise (3085–3112) → noto keys (3116–3150, `_local_noto_slide`) → `relaxed_saya` → iai crouch (3200–3226) → `M.dash` 3257–3268 → pass keys 3269/3270 (CONSTANT) → tableau 3271–3360 → slow noto 3361–3412 → `relaxed_saya` → turn / bow (3552–3600) → turn + `M.walk` (3601–3744).
3. Elder: `gedan` → jodan lift (3162–3186) → `M.dash` 3258–3268 → pass keys → tableau → break at 3412 (weapon state, `snap_free`, `_local_toss_fx` tip) → cord 3414 → knee-down 3462–3476 → `elder_kneel_broken` to 3840.
4. Props/effects: `_local_drop`, `_local_droplets` calls, `red_mist`, tail override keys + `LT.secondary_override`.
5. Environment per cut (set_sun / wind / clearance / white-out / freeze / state blends / cloud-shadow sweep) and `RS.key_white_flash(3265, 1.0, 4)`.
6. Cameras S24a … S29 (S24b after the shinobi's keys exist; S28 first key aims at `(saint_rig, "head")`), shakes.
7. Events (§3 lists, all music cues explicit: silence, white_silence, blade_ring, final_pass, epilogue, end_card).
8. CONSTANT on every teleport key (3270 roots, 3250 drop, 3412 tip, 3414 cord), `U.freeze_handles` on everything keyed.
9. Checks: `cameras.check_screen_direction` (12 cuts; S24b/S24e/S26b/S29 SKIP — no head in view), `framing_qa` (expected WARN only: S27 elder clipped), `events.finalize` missing-beats list empty for 3073–3840, flash_qc on the 3255–3320 preview, re-run `out/dev/breakdown/finale/geom.py` if any number changes.

**Open questions.**
- Q1 Is keying `hide_render` on act2's VFX objects inside the finale span acceptable to the pipeline owner (D6)?
- Q2 Does `characters` expose the headband's night emission (for F1), or should the lane go straight to F2 if needed?
- Q3 Should `vfx` provide a small `droplets(...)` spawner (used 4× here, plus S23's likely needs) instead of `_local_droplets`?

## Implementation notes (act implementer, `src/blender/acts/finale.py`)

Deviations from the breakdown above (same story beats, same frames) and why. Everything else is implemented as written.

| where | breakdown | implemented | why |
|---|---|---|---|
| S24a rise 3094 / 3104 | `rise_kneel` → hips −0.15 | local `sh_rise_push` (left hand pushing on the left knee, weight over the planted foot) → `sh_rise_mid`; blade keyed with `CH.key_sword` 3086/3090/3094/3104 | `rise_kneel` has no hand on the knee; the push sells the exhaustion of S23 |
| S24b noto | body `sheathe_quick_1` → `sheathe_done` | `_L` variants (right foot back, `stance(lead="L")`); the saya turns onto the blade (roll/turn 50/40 → 64/18 → fixed 75/10) while the first 40 cm go in; the sword controller is keyed EVERY frame 3119–3156 on the evaluated saya axis (`_local_noto_ctrl`) | with sparse pose keys the controller and the saya interpolate separately and the blade left the scabbard axis by up to 4 cm in the 100 mm ECU |
| S24b / S24e light | storm key | `key_pow` ×2 (S24b) / ×2.5 (S24e) per-cut cheats | inserts: lacquer, steel and the drop must catch the key |
| S24d / S24e tails (D10) | straight hang 11° back | 4-segment drape 40/30/15/4° behind the vertical (`HANG_DEG`), tails spread ±4 cm; whip 3257–3264 per frame | the straight hang went through the crouched hips; the drape clears them by 6 cm and the last segment is plumb so the drop falls straight |
| S24e camera | level lens 0.5 m at the tip height | lens 6 cm BELOW the tip looking up 6° (same distance, lens, tip on screen at (−0.25, +0.2)) | at the tip height the whole ECU background is the black grass wall (frame mean 0.001: the drop was invisible); looking up puts the drop against the steam band / storm sky above the grass line |
| S25 pass geometry | contact at (0, −1.30, 1.30) | blades cross at (0.02, −1.28, 1.55) with explicit `CH.key_sword` keys at 3269/3270: shinobi's rising one-handed draw-cut under the elder's still-high two-handed downswing | an X in the S05-axis silhouette (the camera sees only y/z): with both blades near horizontal they read as one line |
| S25 `elder_zanshin_high` | grip z 1.22, dir z −0.17, lead R | grip z 1.28, dir (0.38, −0.91, −0.10), LEFT foot forward | blade clears the grass tops in S25/S26 (D4); left lead lets him drop straight onto the RIGHT knee in S27 (same knee as S23) |
| S25 white-out (D7) | `W_SKY` 1.0 | `W_SKY` 1.8, plus `cloud_billow` 0 and `cloud_cover` 0 in the snapshot | the storm billows stayed dark on the white field (top third 0.13) and the field measured 0.32 < 0.60 |
| S25 white silence | "nothing emitted 3265–3276" | `_local_silence_events`: bakes the span's feet itself (end_lane's bake then finds them evented) and drops this lane's sound events in 3265–3276 (the dash / foot bake / tableau-jump steps); `music_cue` + `slowmo` stay | moves.dash and the foot bake emitted 10 steps inside the silence |
| D6 veil | `key_visible` on other lanes' VFX | same, and for objects whose `hide_render` is DRIVEN by a vfx time window (the fire-ring lights) the hidden step is added to the driver's fx-time curve (`_local_driver_hide`) | keyed visibility cannot override a driver; the ring lights would light the silhouettes in the white |
| S26 cord | `_local_toss_fx` | `props.toss` (fx-time aware) with drag 3.0 + wind (0.8, −0.1, −0.3), g −1.6 to 3456; lies at (1.05, −3.92) from the S27 cut | drifts like cloth, clears the elder's silhouette to screen-left |
| S26b / S29 tip | leans 20° toward lens-right | planted with its flat = the mirror normal between the S29 lens and the S29 key (lean ≈ 21°, top away from the lens) | edge-on / backlit the 3 cm tip read as a grey post; mirrored it carries the moonlight sheen |
| S27 bow | library `bow` (32°) | local `sh_bow_deep` (48° from the hips), 3577 (70 %) → 3582–3592 lowest → up 3600 | at 15 %H in the 30 mm two-shot the 32° bow read as a nod |
| S27–S29 fill | moon_clear fill 0.07 | `fill_pow` 0.40 keyed on the moon blend's end key (3550) | the backlit kneeling master was a black hole in the foreground grass |
| S29 | lens 2.2 m, 0.40 m high, key 240/24, clearance 2.6/4.6 | lens (2.36, −3.94, 0.32), 1.6 m from the tip, tip at NDC x ≈ +0.42 (outside the title ellipse); key cheat 146/24 (disk behind the lens); clearance 2.2/4.2; wetness 0.30 | the tip read too thin at 2.2 m; a backlit vertical flat cannot mirror the key; the wet bare patch read as a pale mirror floor |
| framing labels | `medium` / `wide` | S24c, S24d, S26a, S28 labelled `mcu` for framing_qa | waist-up / partially clipped by design; framing_qa accepts clipping only for close labels |
| partial builds | — | `dev_standins`: only when no rain object covers 3073 (this lane built alone) the lane creates act2's exact `vfx.rain` + `vfx.fire_ring` calls; a full build skips them | every finale image leans on act2's rain + steam band |
