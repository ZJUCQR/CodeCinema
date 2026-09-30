# Director's notes — staging rules every choreography / camera lane must follow

Source of truth for frames: `src/common/config.py` (SHOTS desc strings carry the per-shot key frames). This file carries the rules and the reasons. The originality guard-rails are in [FILM_PLAN.md](FILM_PLAN.md) §4.

## 1. Screen direction (180-degree rule) — HARD
- From S05 (433) until the S25 pass (3271) the camera stays on the **+X side** of the Y-axis action line. Shinobi (at −Y) is **screen-left facing right**, elder (at +Y) **screen-right facing left**. Hero pushes left→right.
- Over-the-shoulder shots only over the **elder's left** shoulder or the **shinobi's right** shoulder.
- Line crossings only as visible camera moves that end back on +X (S08 orbit, S10 circling ≤ 90° with the dolly following).
- Knockbacks carry the shinobi screen-left (S18 kick, S23 shockwave). Rolls go perpendicular to the line, never past the opponent.
- S25 swaps the sides by action. Afterwards keep the same physical camera side (shinobi now screen-right).
- A headless check (cameras.check_screen_direction) projects both heads at the first/last frame of every sub-shot and asserts shinobi_x < elder_x before 3271 and the reverse after (single-character shots: sign of projected facing).

## 2. Cutting rhythm
- Each SHOT is a beat; lanes split it into **sub-cuts** (`S12a`, `S12b`, … — cameras.shot accepts sub ids).
- Fights: **12–48 f per cut** (target ≈ 55–65 cuts in the film, average 2.5–3 s). Stillness beats stay long takes: S02, S05, S24a, S27, S28 — the contrast is the rhythm.
- Cut **2–3 f after a contact**, never mid-swing. Hide every body contact on a cut (S12 shove, S18 kick).
- Cheat cuts are allowed: characters may be repositioned (≤ 0.5 m) across a cut to make blades meet in the new angle.
- Hard cuts + motion blur: `motion_blur_position='START'` and CONSTANT interpolation on the last key of a shot for any object that "teleports" across a cut.

## 3. Lens / shot vocabulary per act
- Prologue: extreme wide (18–24 mm) → knee-height tracking (28 mm) → medium close-up (85 mm, shallow DOF).
- Act I (classical): profile wides and mediums, slow lateral dollies, camera locked on impacts, telephoto profile (135–150 mm from ~50 m) for S05 — **reuse this exact axis + lens for S24a and S25**.
- Act II (fire): handheld mediums (35–50 mm), low angles against the fire, a top-down for the ring ignition.
- Act III (storm): extremes — extreme wides that show the scale of the lightning cut against extreme close-ups of blades and water; as few mediums as possible. Break up low angles (S20 is a HIGH wide).
- Finale: telephoto profile (S24a/S25), ECU inserts (24b scabbard mouth, 24e drop), composed deep two-shot (S27), crane (S28), still life (S29).

## 4. Time: slow motion + tempo
- Slow motion ONLY in `config.SLOWMO`: S07 595–630, S13 1367–1408, a short S19 ramp 2280–2304, and S25–S26 3269–3456 (the longest, the only one in rain: rain at ~1/8 speed, grass frozen with wind 0). Frame slow motion on effects and silhouettes (sparks, rain, mist, tails), never on full-body mechanics.
- Put hits on the beat grid (`config.beat_frame(section, beat)`): Act I 92 BPM anchored at 631, Act II 120 BPM (12 f per beat) from 1633, Act III 140 BPM from 2497. The music hard-stops at 3073.

## 5. Light, flashes, photosensitivity — HARD
- Only 3265–3268 may be (near) full-frame white.
- Other flashes ≤ 70 % and ≤ 2 per second (≥ 12 f apart); S13 perfect-deflect exposure lift ≤ 40 % for 2 f; S21 bolt ≤ 2 f at ≤ 70 %, blue-tinted; S15 fire eruption ramps up over ≥ 6 f (red-flash rule); no flash in S24.
- A QC script (src/tools/flash_qc.py) measures frame luminance on previews and fails > 3 opposing flashes per 24 f.

## 6. Readability
- Act III: put a brighter layer behind the silhouettes (the steam band from the drowned fire ring glowing orange from embers beneath; cloud undersides lit by in-cloud lightning). Backlight the rain (rim light 150–170° from the lens).
- Colour-code effects by owner: the elder's trails/sparks follow the act (gold → fire-orange → cold steel-blue); the shinobi's stay cool white with a red core. His headband red is slightly emissive at night.
- Blades are 1.3–1.5× thicker than realistic so they read in wide shots; rely on trails and glints.
- Nothing important below the grass line; feet stay hidden in wides.

## 7. Character arc through body language (the rig has no face/finger acting)
- The elder fights **one-handed** S07–S12 (a master testing a student); his **first two-handed** blow is the S13 heavy overhead (≈1350) — exactly the blow that gets perfectly deflected. Then the spear (Act II), then two-handed jodan in Act III.
- The shinobi's LOW POINT is S23 (knocked down to one knee, sword planted, head bowed ≈3000); S24 opens with him rising in silence. In S27 the elder kneels on his broken sword in the SAME pose — a visual echo.
- The "click" motif: S06 elder's koiguchi (566) → S24b shinobi sheathes (3150) → S26 shinobi's guard clicks home (≈3412) on the exact frame the elder's blade snaps.
- Headband tails as a mood gauge via secondary-motion wind: streaming in Act I, whipping in the fire, soaked and hanging S23–S26, lifting again in S28.
- Faces: eyes stay in the hat-brim shadow in S04 (one tiny eye glint at ≈392). The hat split (S13) is a backlit profile. Walks are framed so the grass carries the motion (S03), or waist-up through foreground grass.

## 8. Events every lane must emit (audio + music sync)
Emit through `events.emit` at the exact frames: every whoosh/clash/step/land etc. from the moves library, plus the tagged story beats: `first_clash` (595), `perfect_deflect` (≈1367), `hat_cut` (1420), `haori_shed`, `spear_draw` (≈1584), `sheath_drop`, `fire_ignite` (1633), `kunai_deflect` ×3, `kick`, `thunder` (first ≈2353, tag `thunder_first`), `rain_start` (2401), `raikiri` (2497), `tree_split`, `lightning_strike` / `thunder` (S22 flashes), `low_point` (≈2950), `sheathe` (3150, 3412), `tsuba_click` (566, 3150, ≈3412), `sword_break` (≈3412), `cord_cut` (3414), `final_pass` (3300 thunderclap), `rain_stop`, `bell` (3758), plus `music_cue` events for every `config.MUSIC_CUES` key at the frame where the action actually happens.

## 9. Per-lane quick reference
| lane | shots | frames | enters from | leaves at |
|---|---|---|---|---|
| prologue | S01–S04 | 1–432 | — | HANDOFF[432] |
| act1a | S05–S09 | 433–936 | HANDOFF[432] | HANDOFF[936] |
| act1b | S10–S14 | 937–1632 | HANDOFF[936] | HANDOFF[1632] |
| act2 | S15–S20 | 1633–2496 | HANDOFF[1632] | HANDOFF[2496] |
| act3 | S21–S23 (incl. S22b) | 2497–3072 | HANDOFF[2496] | HANDOFF[3072] |
| finale | S24–S29 | 3073–3840 | HANDOFF[3072] | end |

## 10. VFX staging constraints (from the finished vfx lane)
- **S23 rain split** is a gap in depth: it only reads when the camera looks along the cut plane (within ~10°, ≤ ~2 m from the plane). Give it its own sub-cut with such a camera, then return to the +X side for the spray ring.
- **S21 Raikiri fork:** `vfx.lightning_bolt(..., fork_ends=[<pine top>, <a point behind the elder>])` — one branch arches to the pine, a short steep strike lands behind the elder; never toward the shinobi. `bolt_guard` warns if a bolt lands < 5 m from a fighter.
- Spark bursts get 2 motion-blur steps on their first frames automatically (render_setup + `vfx.mb_steps_at`).
