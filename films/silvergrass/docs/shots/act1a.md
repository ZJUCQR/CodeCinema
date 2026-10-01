# Lane act1a — S05–S09 (frames 433–936) — shot breakdown

Status: COMPLETE (all sections filled; history in out/dev/breakdown/PROGRESS_act1a.md). Owner file for the implementer: `src/blender/acts/act1a.py`. Numbers here are binding unless marked "(tune)". `config.py` wins if it disagrees with a number copied here (import it; never re-type TEMPO_MAP / HANDOFF / TITLES). Geometry proofs: `out/dev/breakdown/act1a/geom.py` → `geom_report.txt` (pinhole identical to `bl_util.new_camera`: sensor_fit HORIZONTAL, 36 mm wide, 2.35:1 → 15.30 mm high). Re-run it after any change to a track or camera.

Conventions used below
- Positions = rig origin on the ground (x, y); facing 180 = +Y (shinobi), 0 = −Y (elder). Heights z in metres.
- Screen positions are NDC: x −1 (left) … +1 (right), y −1 (bottom) … +1 (top). "fig %H" = full standing figure (ground → head/hat top) as % of frame height (feet are in the grass, so the visible part is smaller).
- Camera azimuth φ is measured about the fighters' midpoint: φ = 0 is the +X profile, φ = −90 behind the shinobi, φ = +90 behind the elder. |φ| < 90 = the legal +X side. No cut in this lane leaves it.
- Sun: `az` = compass bearing of the sun seen from the arena, from +Y clockwise toward +X (0 = sun toward +Y, 90 = +X, 180 = −Y, 270 = −X); `el` = elevation above the horizon. Scene→sun unit vector `(sin az·cos el, cos az·cos el, sin el)` — the same convention as `environment.set_sun` (verified in environment.py; its `disk_deg` = apparent disc diameter, KEY_MIN_EL 2.5° keeps the key light up when the disc is lower).
- Grass clearance: `(r0, r1)` = camera-clearance ramp (grass scale 0 inside r0, 1 beyond r1 from the lens). Default (1.5, 4.0). "bottom ray" = where the ray through the frame's bottom edge first meets grass (never bare ground = OK).

## 1. Lane summary

| | |
|---|---|
| Shots | S05, S06, S07, S08, S09 — frames **433–936** (504 f = 21.0 s), **13 sub-cuts**, all hard cuts |
| Act / env | Act I "Act One · Blade", `dusk_gold` for the whole span; 92-BPM grid starts at 631 |
| Enters (HANDOFF[432]) | shinobi (0.0, −4.5) facing 180, katana **sheathed**; elder (0.0, 4.0) facing 0, katana **sheathed**, hat on, haori on, tasuki hidden, spear **slung** |
| Leaves (HANDOFF[936]) | shinobi (0.3, −1.8) facing 180, katana **drawn**, two-handed chudan; elder (0.0, 2.6) facing 0, katana **drawn** one-handed low guard (left hand on the saya), hat on, haori on, spear **slung** |
| Track error at the boundaries | 0.00 m at 433 and at 936 (geom.py prints it) |
| Clashes | 4 blade-on-blade contacts (595 heavy, 709, 725, 850), all sword/sword + 2 near misses (756 thrust, 866 counter) |
| Slow motion | only 595–630 (`config.SLOWMO[0]`, fx speed 0.25) |
| Full-frame flashes | one soft exposure lift at 595 (compositor white 0.25 → 0.10 → 0) — see §4 |

Story of the lane in one line: the student draws and starts to close the distance; the master's thumb frees his blade; a dash you never see the start of; the first clash hangs in slow motion; the master tests him one-handed (cut, cut, thrust); the student answers twice and the master, for the first time, gives ground → the fight's centre has moved **toward the elder's side** (+Y): the shinobi gains 2.7 m, which is exactly what HANDOFF[936] encodes.

Root tracks (key frames; interpolate with ease-in/out unless noted; geom.py `SH_TRACK` / `EL_TRACK` are the same data)

| frame | shinobi (x, y) | elder (x, y) | what happens |
|---|---|---|---|
| 433 | (0.00, −4.50) | (0.00, 4.00) | HANDOFF[432]; both still |
| 456–480 | (0.00, −4.50) | (0.00, 4.00) | shinobi draws into two-handed chudan |
| 486–516 | — | (0.00, 4.00) | elder sinks into the iai stance (hips −0.15 m) |
| 525→580 | (0.00, −4.50) → (0.00, −3.40) | — | shinobi's suriashi advance (0.25 m visible by 540, rest off-screen in S06) |
| 588 | (0.00, −3.40) | (0.00, 4.00) | end of S06; CONSTANT keys on both roots |
| 589 | (0.00, −3.30) | (0.00, 1.25) | **cut**: shinobi cheat +0.10; elder **ellipsis** jump (mid-dash) — see deviation D1 |
| 595 | (0.00, −2.75) | (0.00, −0.55) | FIRST CLASH (separation 2.20 m) |
| 630 | (0.00, −2.88) | (0.00, −0.70) | end of slow motion (bodies drift at ¼ speed) |
| 631→645 | → (0.00, −3.40) | (0.00, −0.70) | shinobi skids back 0.52 m (screen-left) |
| 648→662 | (0.00, −3.35) | → (0.00, −0.30) | elder one step back (on beat 2) |
| 678, 694 | (0.00, −3.28) | (0.00, −0.65), (0.00, −1.00) | elder's two steps in (beats 3, 4) |
| 709 | (0.00, −3.25) | (0.00, −1.05) | hit 1 (sep 2.20) |
| 725 | (0.00, −3.40) | (0.00, −1.20) | hit 2 (sep 2.20) |
| 746→756 | → (−0.50, −3.45) | (0.00, −1.20) → (0.00, −1.80) | thrust lunge; shinobi sidesteps to his left (−X) |
| 772 | (−0.50, −3.45) | (0.00, −1.80) | tableau ends; withdrawal starts |
| 800 | (0.30, −3.40) | (0.00, −1.35) mid-step | shinobi back on the line (x = +0.3 = his HANDOFF x); elder's step back 795→803 |
| 803, 819, 832 | → (0.30, −3.05) at 830 | (0.00, −1.20), (0.00, −0.75), (0.00, −0.50) | elder steps back (beats 11, 12) |
| 840 | (0.30, −3.00) | (0.00, −0.45) | S08/S09 boundary (sep 2.55) |
| 842 | (0.30, −3.00) | (0.00, −0.45) | shinobi launches (half beat 13.5) |
| 850 | (0.30, −2.40) | (0.00, −0.45) | counter 1 parried (sep 1.95) |
| 858 | (0.30, −2.30) | (0.00, −0.25) | elder's half step back |
| 866 | (0.30, −1.60) | (0.00, 0.00) | counter 2 misses (sep 1.60 — two-handed reach; tip ≈ 0.15 m short of the beard) |
| 876 | (0.30, −1.58) | (0.00, 0.70) | end of the elder's glide back |
| 897, 913, 928 | (0.30, −1.80) from 905 | (0.00, 1.75), (0.00, 2.40), (0.00, 2.60) | elder's measured steps back (beats 17, 18, settle 19) |
| 936 | (0.30, −1.80) | (0.00, 2.60) | HANDOFF[936] |

Facing never changes (shinobi 180, elder 0) except ±10° body twists inside poses; the sidestep keeps his facing 180.

Weapon / costume / hand states (all keyed with `characters.*` helpers, CONSTANT)

| frame | call | note |
|---|---|---|
| 433 | `set_weapon_state(SHINOBI_rig, 433, 'sheathed')`, `set_weapon_state(SAINT_rig, 433, 'sheathed')`, `set_costume(433, haori=True)`, spear `'slung'`, `SAINT_hat` visible | re-assert the handoff (lane isolation) |
| 456 | `set_weapon_state(SHINOBI_rig, 456, 'drawn')` | swap on the frame the right hand closes on the hilt: key `SHINOBI_sword_ctrl` at 456 to the world matrix of `SHINOBI_katana_sheathed` so the in-hand blade starts exactly in the scabbard (no pop), then slide it out along the saya axis 456→468 |
| 474 | `set_two_hand(SHINOBI_rig, 474, True)` | left hand joins in chudan; stays two-handed to 936 (DIRECTION §7) |
| 433–936 | `set_two_hand(SAINT_rig, f, False)` | elder is ONE-HANDED through the whole lane; off hand = local pose `elder_offhand_saya` (§5) |
| 560→566 | `SAINT_katana_sheathed` local offset along the saya axis 0 → 0.040 m | the koiguchi release seen in S06 (thumb push) |
| 589 | `set_weapon_state(SAINT_rig, 589, 'drawn')`; reset the 0.040 m offset on the (now hidden) sheathed blade | hidden by the cut: at 589 the drawn blade is already leaving the saya mouth |

Deviations (all deliberate; everything else follows config/HANDOFF exactly)
- **D1 — elder ellipsis jump 588→589 (2.75 m).** "Cut in with the elder already mid-dash (the quick-draw you don't see)" is an elided-time cut, not a reframing cheat, so it exceeds DIRECTION §2's ≤ 0.5 m cheat. Key the 588 root CONSTANT (SPEC pipeline rule 2) so motion blur does not smear the jump.
- **D2 — dash length.** docs/FILM_PLAN.md says an "8 m" iai dash; here the elder covers 4.55 m (4.0 → −0.55) because the shinobi has advanced 1.1 m (525–580) and steps 0.55 m into the block. A full 8 m dash would leave the elder at −4 and force him to back-pedal 6.6 m before 936. On screen the dash still reads as long: S05 shows 8.5 m of separation, S07a shows a blur entering from the frame edge.
- **D3 — "act card in the sky band".** `titles.py` (current version, re-measured by `out/dev/breakdown/act1a/act_card_box.py`) places the Act I card in the right third: ink NDC x +0.43…+0.77, y +0.01…+0.58 (0.21–0.50 H from the top), soft backdrop ellipse x +0.35…+0.85, y −0.29…+0.70. S05 puts the horizon at 0.724 H from the top, so the whole card sits on sky; the elder's hat top (NDC y ≤ −0.50) stays ≥ 204 px under the ink and ≥ 82 px under the backdrop (§6). Not a deviation from config — a layout contract with titles.py.
- **D4 — "sun ~1/3 picture height".** Read as both: disc centre at 1/3 picture height from the bottom (el 0.37°) and a stylised disc diameter ≈ 0.30 H = **1.95°** at 135 mm (3.7× the real sun). `environment.set_sun(f, az, el, disk_deg)` has the disc-size control (default dusk disc 2.2°). With the horizon at 0.276 H from the bottom, the lower ~30 % of the disc is below the far horizon: a setting sun (the Act I sunset completes in S14). Later cuts keep the sun within 1.2–3° of the horizon so it never looks higher than in S05.
- **D5 — S07a keeps 5 f after the first contact (595 → cut at 600/601).** DIRECTION §2 says cut 2–3 f after a contact, but 596–600 already run in slow motion (fx speed 0.25 = 1.25 story-frames), and the cut must stay ≥ 12 f. Every other contact cuts exactly 2 f after (711, 727, 758, 852, 868).
- **D6 — two long takes in a fight lane.** S08d 42 f and S09c 68 f carry no contact (tableau/withdrawal and the distance reset). S09c is the lane's breath before S10 (DIRECTION §2: stillness beats stay long). Fallback split in §7.
- **D7 — counter distances.** The shinobi stays two-handed (DIRECTION §7), so his reach is ~0.35 m shorter than the elder's one-handed reach: the counter is staged at 1.95 m (850) and 1.60 m (866) separation, then he eases back to HANDOFF[936] (0.3, −1.8).

## 2. Beat grid (Act I, 92 BPM, anchor 631)

`config.beat_frame('act1', b)` = round(631 + b·15.652). The grid starts at 631 (= `MUSIC_CUES['act1_bar1']`, the release of the slow motion); 4/4 bars. Frames before 631 are not on the grid (the first clash at 595 is a free dramatic hit and the music enters on the release, as config says).

| beat | frame | bar.beat | used for |
|---|---|---|---|
| −2 | 600 | — | (inside slow motion; not used) |
| 0 | **631** | 1.1 | slow-motion release, impact shake, shinobi skid starts, `music_cue act1_bar1` |
| 1 | 647 | 1.2 | skid ends (645) — no hit |
| 2 | 662 | 1.3 | elder's step back |
| 3 | 678 | 1.4 | elder step in #1 |
| 4 | 694 | 2.1 | elder step in #2 |
| 5 | **709** | 2.2 | **hit 1** diagonal down → deflected (clash) |
| 6 | **725** | 2.3 | **hit 2** rising cut → deflected (clash) |
| 7 | 741 | 2.4 | thrust chambered (stillness accent) |
| 8 | **756** | 3.1 | **thrust** fully extended — sidestepped (whoosh, no clash) |
| 9 | 772 | 3.2 | tableau breaks: elder starts to withdraw |
| 10 | 788 | 3.3 | blade withdrawn |
| 11 | 803 | 3.4 | elder step back |
| 12 | 819 | 4.1 | elder step back |
| 13 | 834 | 4.2 | (breath) |
| 13.5 | 842 | — | shinobi launches (dash event, half beat) |
| 14 | **850** | 4.3 | **counter 1** → parried (clash) |
| 15 | **866** | 4.4 | **counter 2** → evaded (whoosh past the beard) |
| 16 | 881 | 5.1 | elder's glide ends (876) / settles — no hit |
| 17 | 897 | 5.2 | elder step back |
| 18 | 913 | 5.3 | elder step back |
| 19 | 928 | 5.4 | elder settles; shinobi holds chudan |
| 20 | 944 | 6.1 | (act1b, S10) |

Hit rhythm: master = beats 5-6-(pause)-8 ("da-da … DA"), student = 14-15 (he answers with the master's own two-beat figure). The four clash frames 595 → 709 → 725 → 850 are 114, 16 and 125 f apart — never closer than 12 f.

## 3. Sub-cuts

Cut list (final; every block below repeats its frames). φ = camera azimuth about the fighters' midpoint (0 = +X profile).

| cut | frames | len | camera | lens | φ (f0→f1) | beat / story point |
|---|---|---|---|---|---|---|
| S05  | 433–540 | 108 | telephoto profile, locked (THE reusable axis) | 135 | 0 | act card; the draw; the iai stance |
| S06  | 541–588 | 48  | ECU scabbard mouth, locked | 100 | (+80) | koiguchi click 566, glint, wind drops |
| S07a | 589–600 | 12  | medium profile, locked | 40 | −7 → −2 | elder mid-dash, FIRST CLASH 595 |
| S07b | 601–630 | 30  | blade insert, slow push-in (slow motion) | 85 | −5 → −3 | the grind, hanging sparks |
| S07c | 631–672 | 42  | low wide profile, locked + impact shake | 32 | 0 | music bar 1, rebound, reset |
| S08a | 673–711 | 39  | orbit (3/4 behind the shinobi's right → front) | 35 | −52 → −19 | elder steps in; hit 1 709 |
| S08b | 712–727 | 16  | low near-profile, slight drift | 50 | +11 → +14 | hit 2 725 (rising) |
| S08c | 728–758 | 31  | OTS over the shinobi's RIGHT shoulder | 45 | −77 → −71 | thrust 756, sidestep |
| S08d | 759–800 | 42  | orbit around the frozen tableau, ends on the profile | 32 | −59 → −3 | tableau, withdrawal |
| S08e | 801–840 | 40  | clean single, shinobi 3/4 front, push-in | 65 | +31 → +25 | his resolve; elder gives room (off-screen) |
| S09a | 841–852 | 12  | OTS over the elder's LEFT shoulder | 40 | +79 → +78 | counter 1 parried 850 |
| S09b | 853–868 | 16  | 3/4 rear over the elder's LEFT shoulder, pull-back | 50 | +51 → +45 | counter 2 evaded 866 |
| S09c | 869–936 | 68  | elevated wide profile, lateral dolly | 28 | 0 | distance reset → HANDOFF[936] |

Shared conventions for every block
- `C = cameras`, `EV = events`, `ENV = environment`, `VFX = vfx`, `CH = characters`, `M = moves`, `RS = render_setup`.
- Every camera is `C.shot(cut_id, f0, f1, keys, dof=..., shake=..., handheld=..., subjects=..., framing=...)`; keys are `(frame, pos, look, lens)`; the last key of each channel is CONSTANT (cameras.shot does it).
- Screen numbers are from `geom_report.txt` (same pinhole as Blender; hat/hachimaki tops included in "top").
- Every clash goes through `M.clash(attacker, defender, f, point)` (Pipeline rule 9: it places both sword controllers so the blades cross at `point`, end_lane resolves ≤ 3–5 cm and emits sparks + the `clash` event). The explicit `VFX.sparks` lines below are the extra/secondary sparks only (do not double the primary burst).
- Sun: `ENV.set_sun(f0, az, el, disk_deg)` on the first frame of each cut (CONSTANT), values in each block.
- Grass: default camera clearance (1.5, 4.0) unless the block says `ENV.set_camera_clearance(f0, near, far)`; re-key the default on the next cut's f0 (CONSTANT keys hold forward).

Blade geometry summary (targets for `CH.key_sword(rig, f, grip=fist, direction=dir)`; reach-checked with the right shoulder 0.25 m forward in the lunge; arm lengths estimated 0.63 m shinobi / 0.68 m elder; tip distance from the fist 0.754 m shinobi / 0.877 m elder per `characters.DIMS`):

| frame | kind | attacker fist → dir | defender fist → dir | contact / miss point | along att. / def. blade | shoulder→fist |
|---|---|---|---|---|---|---|
| 595 | elder iai (horizontal, from his left) vs shinobi receiving block | (0.14, −1.30, 1.34) → (0.23, −0.97, 0.06) | (0.22, −2.33, 1.12) → (0.18, 0.79, 0.59) | (0.30, −1.98, 1.38) | 0.70 / 0.44 | 0.63 / 0.34 |
| 709 | elder diag_down_R vs shinobi high (left) | (−0.30, −1.85, 1.65) → (0.13, −0.97, −0.21) | (−0.05, −2.85, 1.25) → (−0.33, 0.78, 0.53) | (−0.22, −2.45, 1.52) | 0.62 / 0.51 | 0.58 / 0.33 |
| 725 | elder rising_L vs shinobi low (right) | (0.18, −1.85, 1.05) → (0.16, −0.94, 0.31) | (0.15, −2.95, 1.10) → (0.33, 0.87, 0.39) | (0.30, −2.55, 1.28) | 0.75 / 0.46 | 0.70 (lunge) / 0.37 |
| 756 | elder thrust — MISS (shinobi sidesteps to x −0.50) | (0.00, −2.61, 1.34) → (0.02, −1.00, −0.02) | — | tip (0.02, −3.48, 1.32) | 0.87 (tip) | 0.61 |
| 850 | shinobi diag_down_R vs elder mid_L (one-handed) | (0.42, −1.92, 1.66) → (−0.26, 0.93, −0.23) | (0.15, −0.88, 1.15) → (0.18, −0.77, 0.61) | (0.26, −1.35, 1.52) | 0.61 / 0.61 | 0.35 / 0.52 |
| 866 | shinobi horizontal_L — MISS (elder sways back) | (0.29, −1.00, 1.40) → (−0.25, 0.97, 0.03) | — | tip (0.10, −0.27, 1.42), beard tip ≈ (0, −0.08, 1.30) | 0.75 (tip) | 0.40 |

### S05 — 433–540 (108 f) — the stand-off under the sun (stillness beat)
**Purpose.** Establish the geometry and the scale in one held image: two small figures in profile, the huge setting sun between them, the student (left) draws, the master (right) sinks into his quick-draw. The act card sits in the sky.

**Camera — static telephoto profile = THE S05 AXIS (reused by S24a and S25).**
```python
S05_AXIS = dict(x=52.0, z=2.10, pitch_deg=1.45, lens=135.0, sensor=36.0)   # camera y = the fighters' midpoint
# S05: y_mid = (-4.5 + 4.0)/2 = -0.25  (S24a at HANDOFF[3072] has the SAME 8.5 m separation: y_mid = -1.75)
look_z = S05_AXIS["z"] + S05_AXIS["x"] * math.tan(math.radians(S05_AXIS["pitch_deg"]))   # = 3.416
C.shot("S05", 433, 540, keys=[(433, (52.0, -0.25, 2.10), (0.0, -0.25, 3.416), 135.0)],
       dof=None, handheld=0.0, subjects=["shinobi", "saint"], framing="wide")
```
- Camera looks exactly along −X (no yaw), pitch +1.45°, no roll; hfov 15.19°, vfov 6.49°; frame at 52 m = 13.9 × 5.9 m.
- DOF off (at 52 m / 135 mm everything from ~35 m to infinity is sharp anyway). No shake, no handheld.
- Horizon at NDC y −0.45 (0.724 H from the top): ~72 % sky for the card. Camera height 2.10 m keeps the far-field grass (1.1–1.5 m, x = 15…48 m) below the sight lines: grass line on both figures z 1.04 m nominal / 1.26 m with max grass.
- Grass clearance default; bottom ray meets grass at 25.6 m (never bare ground).

| frame | shinobi head (x, y) | shinobi fig %H | elder head (x, y) | elder fig %H | rule |
|---|---|---|---|---|---|
| 433 | (−0.61, −0.61) | 29.2 | (+0.61, −0.57) | 33.1 (hat top −0.50) | −0.61 < +0.61 OK |
| 482 | (−0.61, −0.64) | 28.2 | (+0.61, −0.57) | 33.1 (hat −0.498) | OK |
| 513 | (−0.61, −0.64) | 28.2 | (+0.60, −0.62) | 30.9 (hat −0.543) | OK |
| 540 | (−0.57, −0.64) | 28.1 | (+0.60, −0.63) | 30.6 | OK |
Visible part of each figure = grass line (NDC y −0.81) to the head top (≈ −0.60…−0.50): ~11–13 % H of upper body in silhouette against the backlit far field — read by silhouette + rim light, not detail.

**Action.**
| frames | shinobi (0, −4.50), facing 180 | elder (0, 4.00), facing 0 |
|---|---|---|
| 433–449 | still, relaxed guard-less stance (`M.stance(SH, 433, 'ready')`, katana sheathed), tails streaming | still, upright, hands low: `M.stance(SA, 433, 'ready')`, left hand resting on the saya |
| 450–456 | right hand to the hilt, left hand on the saya mouth (local pose `sh_hand_on_hilt`) | — |
| 456–474 | `M.draw_sword(SH, 450)` (expected end ≤ 474): `CH.set_weapon_state(SH, 456, 'drawn')`, sword ctrl keyed at 456 to `CH.sheathed_ctrl_matrix(SH, 456)` (no pop), pulled out along the saya axis 456→466, arcs forward into chudan 466→474 | — |
| 474–478 | `CH.set_two_hand(SH, 474, True)`; settles in chudan (`M.stance(SH, 478, 'chudan')`, hips −0.06, head fwd +0.04) — two-handed from here to 936 | — |
| 486–516 | holds chudan (breathing: chest ±1.5° every 24 f) | `M.stance(SA, 486, 'iai')` → local pose `elder_iai_crouch` (§5) reached at 516: right foot slides forward 0.35 m (root stays), hips −0.15, torso fwd 15°, right hand onto the tsuka (not gripping yet), left hand on the saya with the thumb on the tsuba; hat brim dips with the head −8° |
| 516–540 | 525→540 first sliding step of a suriashi advance (0.00 → 0.25 m, root (0, −4.25) at 540; continues to (0, −3.40) at 580, off-screen in S06) | frozen in the crouch (only beard/haori secondary motion) |
One-handed / two-handed: shinobi two-handed from 474; elder has no blade in hand (sheathed).

**Clashes.** none.

**Environment.**
```python
ENV.set_state(433, 'dusk_gold')                 # key_lane_defaults already snapshots it; re-assert for isolation
ENV.set_sun(433, 270.0, 0.37, disk_deg=1.95)   # disc centre NDC (0.00, -0.33), diameter 0.30 H, ~30 % below the horizon
ENV.set_wind(433, 1.0); ENV.set_wind(488, 1.0); ENV.set_wind(500, 1.35); ENV.set_wind(528, 1.0)   # one gust wave
ENV.set_camera_clearance(433, 1.5, 4.0)
```
**VFX.** `_local_glint(SHINOBI_katana_tip, 466, 471, peak=1.2)` — a small star glint on the blade as it clears the saya and turns into the sun (≈ 6 px at this size; §5). Nothing else: the image is the sun, the grass wave and two silhouettes.

**Events.**
```python
EV.emit(433, 'music_cue', cue='act1_start', tags=['act1_start'])
EV.emit(456, 'draw', who='shinobi')             # only if M.draw_sword does not emit it
EV.emit(492, 'step', who='saint', strength=0.5); EV.emit(500, 'step', who='saint', strength=0.3)
EV.emit(496, 'wind_gust', strength=0.4)
for i, f in enumerate((527, 543, 559, 575)):   # suriashi, one per ~beat (15.65 f): pre-echo of the 92-BPM grid
    EV.emit(f, 'step', who='shinobi', foot='RL'[i % 2], strength=0.25)
```
**Notes.**
- Long take by design (stillness beat). Nothing moves fast; the grass wave at ~500 is the only big motion and it runs *between* the figures (wind heading 205° = toward −Y/−X, the wave travels right→left across the frame).
- Feet and the draw's lower body are below the grass line: key legs roughly, but the hands/blade must read.
- Act card 445–528 (see §6): nothing may rise into the right-third sky band; the elder's hat top (NDC y ≤ −0.50) stays ≥ 204 px under the ink and ≥ 82 px under the card backdrop.
- Everything is backlit (sun az 270 = straight behind the pair from the lens): silhouettes with a gold rim. Do not add a fill light from the camera side.

### S06 — 541–588 (48 f) — the thumb frees the blade (click motif #1)
**Purpose.** The master's quick-draw is loaded: the tsuba is pushed off the saya mouth (koiguchi o kiru), a click, a glint on the exposed metal, then the wind dies. The audience holds its breath with the grass.

**Camera — static ECU, placed relative to the koiguchi** (the origin of `SAINT_saya` = the koiguchi centre).
```python
# create this camera AFTER the elder's S05/S06 pose keys exist (the saya follows the hips)
saya = bpy.data.objects["SAINT_saya"]
K = U.world_pos_of(saya, 560)                              # nominal (0.17, 3.85, 0.90) in the iai crouch
A = (U.world_matrix_of(saya, 560).to_3x3() @ Vector((0, -1, 0))).normalized()   # saya axis -> hilt
C.shot("S06", 541, 588,
       keys=[(541, K + Vector((0.52, -0.12, 0.05)), K + 0.012 * A, 100.0),
             (588, K + Vector((0.50, -0.12, 0.05)), K + 0.012 * A, 100.0)],      # 2 cm creep-in, imperceptible tension
       dof=dict(focus="SAINT_saya", fstop=5.6), subjects=["saint"], framing="ecu", clip=(0.02, 500.0))
```
- Distance lens→koiguchi 0.54 m, hfov 20.4°: the frame is ~19 × 8 cm at the focus plane; the view is ~perpendicular to the saya axis (dot 0.03) so the whole exposed strip is in the 6 mm focus slab. Camera on the elder's LEFT side (+X).
- Screen (nominal pose): koiguchi (+0.10, −0.12); seated tsuba face (−0.02, −0.04); tsuba at 566 after the 4.0 cm push (−0.40, +0.22); tsuka leaves the frame at the upper-left edge (≈ (−1.0, +0.65)); saya runs out lower-right (+1.0, −0.40).
- Single-character rule: the elder's facing (−Y) projects screen-LEFT ✓ (geom S06). Heads not in frame.
- Grass: default clearance (1.5, 4.0) — the lens sits 0.74 m from the elder's root inside his own grass parting; background = his out-of-focus kimono/hakama and, above the obi, a sliver of backlit grass bokeh.

**Action.**
| frames | elder (0, 4.00) frozen in `elder_iai_crouch` | shinobi |
|---|---|---|
| 541–559 | absolute stillness; only the haori sleeve and beard secondary motion (wind 1.0) | off-screen: suriashi continues (0, −4.25) → (0, −3.40) at 580, CONSTANT key at 588 |
| 560–566 | left thumb (whole left hand, no finger bones) pushes the tsuba: key `SAINT_katana_sheathed` along the saya's local −Y (toward the hilt) 0 → 0.040 m: 560 0.000, 562 0.004, 564 0.014, 565 0.028, **566 0.040**, 567 0.041, 568 0.040 (hard stop + 1 mm recoil). Left hand follows 0.02 m (it holds the saya; the thumb is the pusher). | — |
| 566–588 | frozen; the right hand (upper-left edge, dark) closes 2 mm on the tsuka at 580 (`sa_grip_close`, rotation of hand.R 4°) | — |
The 0.040 m exposes the 3.5 cm habaki + 5 mm of steel (DIMS SAINT habaki_length 0.035). Reset the offset to 0 at 589 (the sheathed prop is hidden then — see §1 weapon table). Elder one-handed state unchanged (blade not drawn).

**Clashes.** none.

**Environment.**
```python
ENV.set_sun(541, 262.0, 2.0, disk_deg=2.2)        # off-frame upper-left (-2.03, +1.60): rim/back light on lacquer + metal
ENV.set_wind(541, 1.0); ENV.set_wind(576, 1.0); ENV.set_wind(588, 0.0)   # LINEAR: the wind dies 576->588 (held breath)
ENV.set_camera_clearance(541, 1.5, 4.0)
```
**VFX.** `_local_glint(obj="SAINT_katana_sheathed", f0=566, f1=575, path=(habaki_base → +0.040 m along the blade), peak_frame=569, peak=1.5, size=0.012)` — a thin streak + small 4-point star sliding along the exposed metal from the koiguchi edge to the tsuba (right→left on screen), riding the bloom. No sparks, no light change.

**Events.**
```python
EV.emit(566, 'tsuba_click', pos=tuple(K), who='saint', tags=['tsuba_click', 'click_motif_1'])
EV.emit(576, 'wind_gust', strength=0.0, tags=['held_breath'])      # ambience hush 576-588 (ambience.py also knows it)
EV.emit(559, 'step', who='shinobi', strength=0.2); EV.emit(575, 'step', who='shinobi', strength=0.2)  # off-screen suriashi
```
**Notes.**
- The click must land on 566 exactly (motif frames 566 / 3150 / ≈3412). No camera motion at the click.
- Both hands read as dark masses at the frame edges (no fill light; the sun is behind). Only the metal catches light.
- The iai crouch must already be fully settled by 541 (keyed in S05 at 516) — no body motion at all in this cut.
- The shinobi's hidden advance 540→580 is what makes the dash distance 4.55 m instead of the 8.5 m seen in S05 (D2).

### S07a — 589–600 (12 f) — the dash you barely see, FIRST CLASH 595
**Purpose.** The master is already flying at the student, blade coming out of the saya in a blur; the student meets it. Clang at 595, and time stretches.

**Camera — static medium profile, locked through the impact (DIRECTION §3: Act I locks on impacts).**
```python
C.shot("S07a", 589, 600, keys=[(589, (7.50, -1.90, 1.50), (0.00, -1.90, 1.30), 40.0)],
       dof=dict(focus=(0.30, -1.98, 1.38), fstop=4.0), subjects=["shinobi", "saint"], framing="medium")
```
| frame | shinobi head | fig %H | elder head | fig %H | contact | rule |
|---|---|---|---|---|---|---|
| 589 | (−0.40, +0.16) | 56.9 | (+0.84, +0.10) mid-dash, right edge | 58.0 | — | OK |
| 595 | (−0.22, +0.12) | 54.8 | (+0.33, +0.14) | 60.1 | (−0.02, +0.05) frame centre | OK |
| 600 | (−0.24, +0.11) | 54.5 | (+0.32, +0.14) | 60.1 | — | OK |
Grass line z 1.01 m (NDC y −0.20): waist-up figures, feet hidden. φ −7° → −2°. Bottom ray: grass at 3.35 m.

**Action.**
| frames | elder — ONE-HANDED | shinobi — two-handed |
|---|---|---|
| 588→589 | root CONSTANT at (0, 4.00) on 588, **(0, 1.25) on 589** (ellipsis jump, D1); `CH.set_weapon_state(SA, 589, 'drawn')`, `CH.set_arm_mode(SA, 589, 'ik')`; sword ctrl at 589 = `CH.sheathed_ctrl_matrix(SA, 589)` translated 0.35 m toward the hilt (blade 40 % out); hat brim low, body pitched forward (head dz −0.28, lean +0.30) | root CONSTANT (0, −3.40) on 588 → (0, −3.30) on 589 (cheat +0.10); chudan |
| 589–595 | `M.dash(SA, 589, 595, (0, 1.25), (0, -0.55))` (1.8 m in 6 f = 7.2 m/s, grass wake) + `M.iai_slash(SA, 589, kind='horizontal', side='L')`: blade clears the saya at 591 and sweeps from his LEFT (+X) across toward his right (−X); at 595 fist ≈ (0.14, −1.30, 1.34), blade dir (0.23, −0.97, 0.06), deep lunge (hips fwd +0.12, front knee 70°) | steps into it 0.55 m (`M.walk`-free: root (0, −3.30) → (0, −2.75) with one lunge step at 592); `M.deflect(SH, 595, 'mid_R')` shaped as a forward-angled receiving block (uke-nagashi): right fist ≈ (0.22, −2.33, 1.12), blade dir (0.18, 0.79, 0.59) |
| 595–600 | slow-motion drift (¼ speed): root −0.55 → −0.58 | root −2.75 → −2.78, knees give 3° |

**Clash.** `M.clash(SA, SH, 595, point=(0.30, -1.98, 1.38), strength=1.0)` — sword/sword, **heavy**; contact 0.70 m along the elder's blade (monouchi), 0.44 m along the shinobi's blade (lower third, on the shinogi). Tag it `first_clash` (see Events). Contact point is on the camera side of both bodies (x = +0.30), unoccluded.

**Environment.**
```python
ENV.set_sun(589, 270.0, 1.0, disk_deg=2.2)     # disc at NDC (0.00, +0.23): the S05 image in motion, just above the contact
ENV.set_wind(589, 0.6)                          # the dash breaks the held breath (LINEAR -> 1.0 at 631)
ENV.set_camera_clearance(589, 1.5, 4.0)
```
**VFX.**
```python
VFX.blade_trail("SAINT_katana_tip", "SAINT_katana_base", 590, 596, owner="saint")        # gold draw arc
VFX.grass_burst(590, (0.0, 0.9, 0.6), direction=(0.0, 0.5, 0.6), count=70, speed=3.0, seed=crc("S07a:wake"))  # wake
VFX.grass_burst(595, (0.25, -1.95, 0.95), direction=(0, 0, 1), count=60, spread=80, seed=crc("S07a:ring"))    # pressure
VFX.dust_burst(596, (0.0, -2.95, 0.0), radius=0.6, life=48, seed=crc("S07a:plant"))      # shinobi's braced rear foot
# primary sparks come from M.clash: request count=120, speed=4.5, life=14, scale=1.6, color='gold',
# direction=(-0.35, 0.25, 0.90), spread=70 (fx-time life: they hang ~4x longer on screen in the slow motion)
```
Blade trails vanish at the next cut (vfx tend) — fine, S07b is an insert.

**Flash.** `RS.key_white_flash(594, 0.0); RS.key_white_flash(595, 0.25); RS.key_white_flash(596, 0.10); RS.key_white_flash(597, 0.0)`
+ `RS.key_dispersion(595, 0.04); RS.key_dispersion(598, 0.0)` (§4).

**Events.**
```python
EV.emit(589, 'dash', who='saint', strength=1.0)
EV.emit(591, 'draw', who='saint'); EV.emit(591, 'whoosh', who='saint', weapon='katana', strength=1.0)
EV.emit(592, 'step', who='shinobi', strength=0.6)
# ONE clash event at 595: M.clash(..., kind='clash_heavy', tags=['first_clash']) if supported, else emit=False +
EV.emit(595, 'clash_heavy', pos=(0.30, -1.98, 1.38), strength=1.0, tags=['first_clash'])
EV.emit(595, 'music_cue', cue='first_clash', tags=['first_clash'])
EV.emit(595, 'slowmo', duration=36)
```
**Notes.** D5: 5 slow-motion frames after the contact (596–600 = 1.25 story-frames) keep the cut ≥ 12 f. `config.SHOT_RENDER["S07"]` gives mb_steps 3 for this shot: the dash smears; the elder's 588→589 jump must be CONSTANT (Pipeline rule 2) or the first frame of S07a smears across 2.75 m.

### S07b — 601–630 (30 f) — slow-motion insert: the grind
**Purpose.** Hold the moment: the master's blade grinding up the student's angled blade, a stream of sparks crawling off the contact, the sun blurred behind. Slow motion on effects only — no bodies in frame (DIRECTION §4).

**Camera — slow push-in that follows the moving contact** (clearance tightened for the close lens).
```python
C.shot("S07b", 601, 630, keys=[(601, (1.88, -1.86, 1.44), (0.30, -1.98, 1.38), 85.0),
                               (630, (1.70, -1.78, 1.52), (0.33, -1.86, 1.47), 85.0)],
       dof=dict(focus=(0.30, -1.98, 1.38), fstop=4.0, distance_keys=[(601, 1.59), (630, 1.40)]),
       subjects=[], framing="insert")
ENV.set_camera_clearance(601, 1.0, 2.0)
```
- Contact at NDC (0.00, 0.00) at 601 and at 630 (the look follows it). Frame width at the contact ≈ 0.66 m: two blades and hands at the edges only. Heads projected off-frame but on the correct sides: 601 shinobi −1.71 / elder +3.10, 630 shinobi −2.55 / elder +2.93 (rule OK). The elder's blade enters from screen-RIGHT (fist at x ≈ +2.7), the shinobi's blade rises from the lower-LEFT (fists ≈ (−0.96, −1.60)) to the upper-right: screen direction preserved.
- Background: sun disc bokeh upper-left (sun az 262 el 1.5 → NDC (−0.30, +0.71) at 601, (−0.39, +0.70) at 630), golden grass-top bokeh along the bottom (bottom ray meets grass 2.9 m behind the contact).

**Action (keys at 601, 615, 630; bodies move at ¼ speed, off-frame).**
- Contact path P(f) = (0.30, −1.98, 1.38) + t·(0.027, 0.12, 0.09), t = (f − 595)/35 → (0.33, −1.86, 1.47) at 630: the elder's blade slides 0.15 m up the shinobi's blade toward his tip (the angled block lifts the cut).
- Key both sword controllers with `CH.key_sword` so the blades cross at P(f) at 601/615/630 (or `M.blade_lock(SA, SH, 598, 630)` if it accepts a moving point); the elder's blade pitches up 8° over the cut. Roots: elder −0.58 → −0.70, shinobi −2.78 → −2.88.
- Elder one-handed, shinobi two-handed (both fists stay off-frame).

**Clashes.** continuous grind of the 595 contact (no new clash event; the gate is checked at 601/615/630).

**Environment.** `ENV.set_sun(601, 262.0, 1.5, disk_deg=2.2)`. Wind as keyed (0.6 → 1.0 LINEAR to 631) — plays at fx 0.25.

**VFX.**
```python
for i, f in enumerate(range(599, 630, 3)):                    # 11 small bursts peeling off the grind point
    VFX.sparks(f, P(f), direction=(-0.2, 0.55, 0.8), count=14, speed=3.0, life=8, color='gold', scale=0.7,
               light=(i % 3 == 0), seed=crc(f"S07b:{i}"))
```
(fx-time life 8 at speed 0.25 ⇒ each needle lives ~32 film frames: the stream crawls and hangs.)

**Events.** `EV.emit(599, 'blade_lock', duration=31, strength=0.35, tags=['grind', 'slowmo'])` — the scrape under the slow motion (audio may fold it into the `slowmo` treatment).

**Notes.** Only effects move visibly (sparks, the sliding contact, bokeh). No full-body shot inside the slow motion.

### S07c — 631–672 (42 f) — real time, music bar 1, rebound and reset
**Purpose.** The spell breaks on the downbeat: the blades spring apart, the student is driven back through the grass, the master takes one calm step back. The fight is on.

**Camera — static low wide profile + impact shake on 631.**
```python
C.shot("S07c", 631, 672, keys=[(631, (7.20, -1.75, 1.25), (0.00, -1.75, 1.38), 32.0)],
       dof=None, shake=[(631, 0.8, 10)], subjects=["shinobi", "saint"], framing="wide")
ENV.set_camera_clearance(631, 1.5, 4.0)
```
| frame | shinobi head | fig %H | elder head | fig %H | rule |
|---|---|---|---|---|---|
| 631 | (−0.27, +0.03) | 45.1 | (+0.22, +0.09) | 51.1 | OK |
| 645 | (−0.40, +0.05) | 46.0 | (+0.24, +0.13) | 53.4 | OK |
| 662 | (−0.39, +0.07) | 47.3 | (+0.35, +0.17) | 55.0 | OK |
| 672 | (−0.38, +0.09) | 48.0 | (+0.35, +0.17) | 55.0 | OK |
Camera at 1.25 m, pitch +1°: the grass tops run through the lower fifth (grass line NDC y −0.20), sky dominant; bottom ray meets grass at 2.9 m (clearance scale 0.58). φ ≈ 0.

**Action.**
| frames | elder — ONE-HANDED | shinobi — two-handed |
|---|---|---|
| 631 | the blades spring apart: his blade is flung up and back over his right shoulder (sword ctrl: tip to ≈ (−0.45, −0.60, 2.35) by 636) | driven back |
| 631–645 | recovers into a one-handed low guard (`M.stance(SA, 648, 'low_one_hand')` = local pose `elder_low_guard_1h`, §5), left hand returns to the saya (`elder_offhand_saya`) by 646 | `M.skid(SH, 631, 645, (0, -2.88), (0, -3.40))`, knees deep, blade kept in chudan, left heel ploughs |
| 648–662 | one measured step BACK (beat 2): (0, −0.70) → (0, −0.30), blade low, hat level — he is looking at the student | rises from the skid crouch into chudan 646–660, root (0, −3.35) at 660 |
| 662–672 | still (tension); breathing | still; tails stream (wind 1.0) |

**Clashes.** none new (the 631 release belongs to the 595 contact).

**Environment.** `ENV.set_sun(631, 270.0, 1.5, disk_deg=2.2)` (disc just above the horizon between them, NDC (0.00, +0.03)); `ENV.set_wind(631, 1.0)` (end of the LINEAR ramp from 589).

**VFX.**
```python
VFX.sparks(631, (0.33, -1.86, 1.47), direction=(-0.3, 0.2, 0.9), count=40, speed=6.0, life=8, color='gold',
           seed=crc("S07c:release"))                                                 # real-time release burst
VFX.blade_trail("SAINT_katana_tip", "SAINT_katana_base", 631, 640, owner="saint")    # the flung arc (gold)
VFX.grass_burst(633, (0.0, -3.00, 0.3), direction=(0.0, -0.6, 0.6), count=70, speed=3.0, seed=crc("S07c:skid"))
VFX.dust_burst(634, (0.0, -3.20, 0.0), radius=0.7, life=40, seed=crc("S07c:dust"))
RS.key_dispersion(631, 0.04); RS.key_dispersion(634, 0.0)
```
**Events.**
```python
EV.emit(631, 'music_cue', cue='act1_bar1', tags=['act1_bar1'])
EV.emit(631, 'whoosh', who='saint', weapon='katana', strength=0.6)
EV.emit(632, 'skid', who='shinobi', duration=14, strength=0.7)
EV.emit(646, 'step', who='shinobi', strength=0.5)
EV.emit(650, 'step', who='saint', strength=0.35); EV.emit(662, 'step', who='saint', strength=0.4)
```
**Notes.** Real time from 631 exactly (TIME_WARP ends at 630). The skid carries the shinobi screen-LEFT (DIRECTION §1). The shake is the only camera motion; the frame is otherwise locked.

### S08a — 673–711 (39 f) — the master comes in: hit 1 (diagonal down) deflected on 709
**Purpose.** The test begins: the elder walks in on the beat, one-handed, and cuts down from his right shoulder; the student meets it high on his left. The orbit swings us from behind the student toward the profile.

**Camera — orbit on the +X side**, centre (0.00, −2.12), R 5.5 m, φ −50° → −20° (smoothstep 673→709), then −19° at 711.
```python
C.shot("S08a", 673, 711, keys=[
    (673, (3.54, -6.33, 1.62), (0.00, -2.05, 1.35), 35.0),   # phi -50.0
    (682, (3.87, -6.03, 1.61), (0.00, -2.07, 1.35), 35.0),   # phi -45.3
    (691, (4.51, -5.27, 1.60), (0.00, -2.10, 1.36), 35.0),   # phi -35.0
    (700, (5.00, -4.42, 1.59), (0.00, -2.13, 1.38), 35.0),   # phi -24.7
    (709, (5.17, -4.00, 1.58), (0.00, -2.15, 1.38), 35.0),   # phi -20.0  (locked on the impact: keys 709/711 nearly equal)
    (711, (5.20, -3.91, 1.58), (0.00, -2.15, 1.38), 35.0)],  # phi -19.0
    dof=dict(focus=(-0.22, -2.45, 1.52), fstop=4.0), subjects=["shinobi", "saint"], framing="medium")
```
| frame | shinobi head | fig %H | elder head | fig %H | φ | rule |
|---|---|---|---|---|---|---|
| 673 | (−0.34, +0.14) | 81.7 | (+0.30, +0.25) | 62.6 | −51.7 | OK |
| 694 | (−0.39, +0.14) | 79.0 | (+0.30, +0.25) | 72.7 | −31.0 | OK |
| 709 | (−0.39, +0.10) | 71.7 | (+0.31, +0.19) | 71.0 | −19.7 | OK — contact at NDC (−0.12, +0.12) |
| 711 | (−0.39, +0.10) | 71.4 | (+0.31, +0.19) | 71.3 | −18.5 | OK |
Grass line z 0.96–0.99 m (NDC y −0.44 … −0.20); bottom ray meets grass at 3.3 m (scale 0.71). Sun off-frame left.

**Action (hits on the grid: beats 3, 4 = steps, beat 5 = hit).**
| frames | elder — ONE-HANDED (left hand on the saya) | shinobi — two-handed |
|---|---|---|
| 673–694 | from the low guard, two steps IN on the beats: `M.walk(SA, 672, 694, (0,-0.30), (0,-1.00))` with foot plants 678 (−0.65) and 694 (−1.00); blade rises to a one-handed high chamber over the right shoulder by 700 (`elder_chamber_high_1h`, §5) | holds chudan, eases forward (0, −3.35) → (0, −3.28) at 694, tip tracking the elder's throat |
| 700–709 | `M.slash(SA, 700, 'diag_down_R')` (from his upper RIGHT (−X) to lower left (+X)), step to (0, −1.05) on 705–709; at 709 fist ≈ (−0.30, −1.85, 1.65), blade dir (0.13, −0.97, −0.21) | `M.deflect(SH, 709, 'high')` on his LEFT-high side: right fist ≈ (−0.05, −2.85, 1.25), blade dir (−0.33, 0.78, 0.53) (tip up-left-forward) |
| 709–711 | blade glances off down to his left (+X) | absorbs, root (0, −3.25) |

**Clash.** `M.clash(SA, SH, 709, point=(-0.22, -2.45, 1.52), strength=0.75)` — sword/sword, medium: 0.62 m along the elder's blade, 0.51 m along the shinobi's. Primary sparks (from M.clash): count 60, scale 1.0, gold, direction (0.55, −0.35, 0.35) (toward the lens side), spread 60.

**Environment.** `ENV.set_sun(673, 250.0, 3.0, disk_deg=2.2)` (off-frame left: back-left key/rim on both); `ENV.set_camera_clearance(673, 1.5, 4.0)`.

**VFX.** `VFX.blade_trail("SAINT_katana_tip", "SAINT_katana_base", 700, 710, owner="saint")` (gold); `VFX.grass_burst(694, (0.0, -1.10, 0.2), direction=(0, -0.3, 1), count=30, speed=2.0, seed=crc("S08a:step"))` (the planted step).

**Events.**
```python
EV.emit(678, 'step', who='saint', strength=0.45); EV.emit(694, 'step', who='saint', strength=0.5)
EV.emit(705, 'whoosh', who='saint', weapon='katana', strength=0.85)
# clash event (strength 0.75) at 709 comes from M.clash / end_lane
EV.emit(715, 'step', who='shinobi', strength=0.4)       # he re-plants after the parry (inside S08b)
```
**Notes.** Cut at 711 = 2 f after contact. The orbit is slow (≈ 2 m/s) and never crosses φ = −90°.

### S08b — 712–727 (16 f) — hit 2 (rising cut) deflected on 725
**Purpose.** The master reverses the blade without pause: a rising cut from low on his left. The student drops his blade to meet it and is pushed back a step. Low, near-profile, sparks toward the lens.

**Camera — low near-profile, slight drift toward the elder's side.**
```python
C.shot("S08b", 712, 727, keys=[(712, (5.09, -1.22, 1.22), (0.12, -2.35, 1.34), 50.0),
                               (727, (5.05, -1.04, 1.22), (0.12, -2.40, 1.34), 50.0)],
       dof=dict(focus=(0.30, -2.55, 1.28), fstop=2.8), subjects=["shinobi", "saint"], framing="medium")
```
| frame | shinobi head | fig %H | elder head (hat top) | fig %H | φ | rule |
|---|---|---|---|---|---|---|
| 712 | (−0.44, +0.19) | 97.9 | (+0.65, +0.35) (+0.65) | 121.6 | +10.7 | OK |
| 725 | (−0.46, +0.16) | 95.7 | (+0.61, +0.36) (+0.65) | 122.1 | +13.9 | OK — contact (−0.11, −0.07) |
| 727 | (−0.46, +0.17) | 95.9 | (+0.62, +0.36) (+0.66) | 122.5 | +14.0 | OK |
Camera 1.22 m (just above the grass tops, clearance (1.5, 4.0) opens the foreground): grass line on both z 1.03 m (NDC y −0.39); the elder, nearer the lens, frames bigger (the master dominates). Sun az 285 off-frame right.

**Action.**
| frames | elder — ONE-HANDED | shinobi — two-handed |
|---|---|---|
| 712–716 | blade finishes low on his LEFT (+X) side, wrist turns edge-up | gives ground after the parry: root (0, −3.25) at 709 → (0, −3.40) at 725 (re-plant 715), tip drops |
| 716–725 | `M.slash(SA, 716, 'rising_L')` (from his lower LEFT (+X) up toward his upper right (−X)); step (0, −1.05) → (0, −1.20); at 725 fist ≈ (0.18, −1.85, 1.05), blade dir (0.16, −0.93, 0.31) | `M.deflect(SH, 725, 'low')` on his RIGHT-low side: right fist ≈ (0.15, −2.95, 1.10), blade dir (0.33, 0.87, 0.39) (tip down-forward-out) |
| 725–727 | follow-through up to his right | absorbs hit 2 in the knees (−5°, no root motion), holds (0, −3.40) to 746 |

**Clash.** `M.clash(SA, SH, 725, point=(0.30, -2.55, 1.28), strength=0.85)` — sword/sword, medium-heavy: 0.75 m along the elder's blade, 0.46 m along the shinobi's. Sparks: count 70, scale 1.1, gold, direction (0.6, 0.1, 0.5) (at the lens).

**Environment.** `ENV.set_sun(712, 285.0, 2.0, disk_deg=2.2)`; `ENV.set_camera_clearance(712, 1.5, 4.0)`.

**VFX.** `VFX.blade_trail("SAINT_katana_tip", "SAINT_katana_base", 716, 726, owner="saint")` (gold, rising arc); `RS.key_dispersion(725, 0.03); RS.key_dispersion(727, 0.0)`.

**Events.**
```python
EV.emit(721, 'whoosh', who='saint', weapon='katana', strength=0.9)
# clash (0.85) at 725 from M.clash
EV.emit(731, 'step', who='shinobi', strength=0.35)     # weight shift after absorbing hit 2 (inside S08c)
```
**Notes.** Cut at 727 (2 f after). The two contacts sit on opposite sides of the shinobi (709 left-high, 725 right-low): the audience reads "one cut, then the other side" — the classical two-count.

### S08c — 728–758 (31 f) — the thrust, down the barrel; sidestep on 756
**Purpose.** The third attack comes straight at us over the student's right shoulder: the chamber on beat 7 (a held beat), the lunge, and the student is simply not there any more. Near miss, no contact.

**Camera — OTS over the shinobi's RIGHT shoulder (allowed side), nearly static; clearance tightened.**
```python
C.shot("S08c", 728, 758, keys=[(728, (0.72, -5.35, 1.66), (-0.05, -1.20, 1.46), 45.0),
                               (758, (0.72, -5.40, 1.64), (-0.05, -1.80, 1.40), 45.0)],
       dof=dict(focus=("SAINT_rig", "head"), fstop=2.8), subjects=["shinobi", "saint"], framing="ots")
ENV.set_camera_clearance(728, 1.0, 2.2)
```
| frame | shinobi head (foreground) | fig %H | elder head | fig %H | φ | rule |
|---|---|---|---|---|---|---|
| 728 | (−0.42, −0.20) | 222 | (+0.02, +0.21) | 127 | −76.7 | OK |
| 741 | (−0.38, −0.06) | 223 | (+0.06, +0.31) | 128 | −76.8 | OK |
| 748 | (−0.47, +0.00) | 219 | (+0.04, +0.27) | 132 | −75.3 | OK |
| 756 | (−0.91, −0.04) he has stepped left | 208 | (−0.00, +0.18) | 138 | −70.7 | OK — thrust tip (−0.36, −0.55) at 2.0 m from the lens |
| 758 | (−0.90, −0.03) | 208 | (−0.00, +0.19) | 138 | −70.7 | OK |
The shinobi (2.1–2.3 m from the lens) sits inside the tightened clearance (1.0, 2.2): his back/right shoulder is clean of grass blades; the frame bottom cuts him at the hips anyway. The elder stays in grass (grass line NDC y −0.71).

**Action.**
| frames | elder — ONE-HANDED | shinobi — two-handed |
|---|---|---|
| 728–741 | draws the blade back to his right hip, point level at the student (`elder_thrust_chamber_1h`, §5) — fully set on beat 7 (741) and HELD 741–746 | recovers into chudan at (0, −3.40) |
| 746–756 | `M.slash(SA, 746, 'thrust')` — lunge (0, −1.20) → (0, −1.80), arm and blade horizontal at 1.32 m, full extension on beat 8 (**756**): fist ≈ (0.00, −2.61, 1.34), tip (0.02, −3.48, 1.32) | `M.dodge(SH, 748, 'left')`: side-step to his LEFT (−X) (0, −3.40) → (−0.50, −3.45), torso turned 20° (right shoulder back); the blade passes ~0.3 m off his right side through where his sternum was |
| 756–758 | extended, still | still, blade kept two-handed high-left |

**Clashes.** none (near miss). Keep ≥ 0.25 m between the elder's blade and the shinobi's body/arms at 750–758 (check with `CH.blade_points` vs the shinobi's chest/upper_arm.R — the thrust must read as a miss, not a graze).

**Environment.** `ENV.set_sun(728, 290.0, 3.0, disk_deg=2.2)` (off-frame left-top: the elder's face stays in the hat shadow).

**VFX.**
```python
VFX.blade_trail("SAINT_katana_tip", "SAINT_katana_base", 750, 757, owner="saint", width=0.5)   # straight gold streak
VFX.grass_burst(752, (-0.35, -3.45, 0.4), direction=(-0.6, 0.0, 0.5), count=40, speed=2.5, seed=crc("S08c:side"))
VFX.dust_burst(756, (0.0, -2.20, 0.0), radius=0.5, life=36, seed=crc("S08c:lunge"))
```
**Events.**
```python
EV.emit(741, 'step', who='saint', strength=0.3)                       # the set on beat 7
EV.emit(752, 'whoosh', who='saint', weapon='katana', strength=0.9)    # thrust
EV.emit(752, 'step', who='shinobi', strength=0.6); EV.emit(756, 'step', who='saint', strength=0.7)   # lunge plant on beat 8
```
**Notes.** The thrust axis is ~8° off the lens axis, so the blade foreshortens into a short bright line coming at the viewer — rely on the trail and the tip glint. Cut at 758 (2 f after full extension).

### S08d — 759–800 (42 f) — the tableau, the camera circles
**Purpose.** Freeze the near miss so the audience can see it: the master fully extended, the student beside the blade. Then the master withdraws, calm, and the student slides back onto the line. The orbit ends on the +X profile.

**Camera — orbit on the +X side**, centre (−0.20, −2.60), R 5.5 m, φ −60° → 0° (smoothstep), z 1.72 → 1.52.
```python
C.shot("S08d", 759, 800, keys=[
    (759, (2.55, -7.36, 1.72), (-0.20, -2.60, 1.35), 32.0),   # phi -60.0
    (766, (2.93, -7.12, 1.70), (-0.19, -2.60, 1.35), 32.0),   # phi -55.4
    (773, (3.77, -6.41, 1.67), (-0.17, -2.59, 1.35), 32.0),   # phi -43.8
    (780, (4.61, -5.26, 1.62), (-0.15, -2.57, 1.35), 32.0),   # phi -28.9
    (787, (5.13, -3.96, 1.57), (-0.12, -2.56, 1.35), 32.0),   # phi -14.3
    (794, (5.29, -2.93, 1.53), (-0.11, -2.55, 1.35), 32.0),   # phi -3.5
    (800, (5.30, -2.60, 1.52), (-0.10, -2.55, 1.35), 32.0)],  # phi  0.0
    dof=None, subjects=["shinobi", "saint"], framing="medium")
ENV.set_camera_clearance(759, 1.5, 4.0)
```
| frame | shinobi head | fig %H | elder head | fig %H | φ | rule |
|---|---|---|---|---|---|---|
| 759 | (−0.25, +0.08) | 66.9 | (+0.14, +0.15) | 59.4 | −59.4 | OK |
| 772 | (−0.29, +0.11) | 65.3 | (+0.16, +0.15) | 61.9 | −43.9 | OK |
| 786 | (−0.27, +0.13) | 65.5 | (+0.27, +0.21) | 69.1 | −16.2 | OK |
| 800 | (−0.29, +0.14) | 68.6 | (+0.41, +0.24) | 73.8 | −2.8 | OK |
At 759 the extended blade runs past the shinobi's right (+X, camera) side — visible. Sun enters the frame at ~786 ((−0.50, +0.28)) and settles between them at 800 ((−0.02, +0.24)).

**Action.**
| frames | elder — ONE-HANDED | shinobi — two-handed |
|---|---|---|
| 759–772 | frozen in full extension (breathing only) | frozen beside the blade, eyes (head) turned 10° toward the blade |
| 772–790 | withdraws: blade slides back past the student, root (0, −1.80) → (0, −1.60) (front foot recovers), ends in `elder_low_guard_1h`, left hand on the saya | 772–800 slides back onto the line, facing kept 180: `M.walk(SH, 772, 800, (-0.50, -3.45), (0.30, -3.40))` (a lateral cross-step, blade pointed at the elder) |
| 790–800 | still until 795, then lifts the rear foot: first step BACK lands on beat 11 (803, in S08e) | re-settles chudan |

**Clashes.** none.

**Environment.** `ENV.set_sun(759, 270.0, 1.5, disk_deg=2.2)`; `ENV.set_wind(768, 1.0); ENV.set_wind(778, 1.4); ENV.set_wind(795, 1.0)` (a gust wave breaks the tableau).

**VFX.** none.

**Events.**
```python
EV.emit(772, 'wind_gust', strength=0.5)
EV.emit(776, 'step', who='saint', strength=0.3); EV.emit(790, 'step', who='saint', strength=0.3)
EV.emit(780, 'step', who='shinobi', strength=0.3); EV.emit(794, 'step', who='shinobi', strength=0.3)
```
**Notes.** D6: 42 f, no contact. The orbit moves at ≈ 3.5 m/s peak — slow enough to read the geometry; keep the look-at on the pair's midpoint so neither head leaves the middle half of the frame.

### S08e — 801–840 (40 f) — the student's resolve (clean single)
**Purpose.** A breath and a decision: close on the student, two-handed, re-gripping, stepping in on the beats while the master (off-screen right) steps back to give him room. We know he will attack.

**Camera — clean single, the shinobi 3/4 front from his right (+X) side, slow push-in, clearance tightened.**
```python
C.shot("S08e", 801, 840, keys=[(801, (2.45, -0.95, 1.52), (0.10, -3.17, 1.40), 65.0),
                               (840, (2.25, -0.75, 1.50), (0.12, -2.82, 1.40), 65.0)],
       dof=dict(focus=("SHINOBI_rig", "head"), fstop=2.8), subjects=["shinobi"], framing="mcu")
ENV.set_camera_clearance(801, 1.0, 2.0)
```
| frame | shinobi head | fig %H (head to waist in frame) | elder | rule |
|---|---|---|---|---|
| 801 | (−0.30, +0.36), hachimaki top +0.66 | 213.6 | off-frame right (+2.55) | single: faces screen-RIGHT OK |
| 819 | (−0.26, +0.37) | 223.7 | off (+3.68) | OK |
| 830 | (−0.27, +0.38) | 230.5 | off (+4.19) | OK |
| 840 | (−0.28, +0.39) | 233.2 | off (+4.44) | OK |
Lead room on screen-right (his facing). φ +31° → +25° (+X side). Bottom ray meets full-height grass at 3.0 m: a soft band of grass tips along the frame bottom, his hands in chudan just above it.

**Action.**
| frames | shinobi — two-handed | elder (off-screen) — one-handed |
|---|---|---|
| 801–830 | two suriashi steps ON beats 11 and 12: (0.30, −3.40) → (0.30, −3.22) 803–812, → (0.30, −3.05) 819–828 | steps BACK on the same beats: (0, −1.60) → (0, −1.20) 803, → (0, −0.75) 819, → (0, −0.50) 832 |
| 830–838 | re-grip on beat 13 (834): local move `sh_regrip` (§5): tip dips 5° and returns, fists tighten, shoulders drop 2 cm | settles `elder_low_guard_1h` at (0, −0.45) by 840 |
| 838–840 | loads: hips −0.03, weight onto the front foot | still |

**Clashes.** none. **VFX.** none.

**Environment.** `ENV.set_sun(801, 270.0, 1.5, disk_deg=2.2)` (off-frame right-front, NDC (+4.0, +0.65): he is backlit — a warm rim along his far (left) edge, mask and tails; the visible side is lit only by the state's soft fill. Keep it: dusk grammar).

**Events.**
```python
EV.emit(803, 'step', who='saint', strength=0.35); EV.emit(819, 'step', who='saint', strength=0.35)
EV.emit(832, 'step', who='saint', strength=0.25)
EV.emit(805, 'step', who='shinobi', strength=0.3); EV.emit(821, 'step', who='shinobi', strength=0.3)
```
**Notes.** The only single in the lane: his tails stream screen-left (wind heading 205°), the red headband and cool greys against the warm grass bokeh. Nothing moves fast. The elder's retreat is heard (panned right), not seen.

### S09a — 841–852 (12 f) — counter 1, parried on 850
**Purpose.** The student takes the initiative: he launches on the half beat and cuts down at the master's left shoulder; the master parries one-handed without moving his feet. Seen over the master's LEFT shoulder: we feel the attack coming at him.

**Camera — OTS over the elder's LEFT shoulder (allowed side), medium, near-static; clearance tightened.**
```python
C.shot("S09a", 841, 852, keys=[(841, (0.78, 1.55, 1.74), (0.25, -2.70, 1.38), 40.0),
                               (852, (0.78, 1.62, 1.74), (0.25, -2.40, 1.38), 40.0)],
       dof=dict(focus=("SHINOBI_rig", "head"), fstop=2.8), subjects=["shinobi", "saint"], framing="ots")
ENV.set_camera_clearance(841, 1.0, 2.2)
```
| frame | shinobi head | fig %H | elder head (foreground, hat top) | fig %H | φ | rule |
|---|---|---|---|---|---|---|
| 841 | (−0.04, +0.19) | 92.6 | (+0.55, +0.25) (+0.81) | 224 | +79.0 | OK |
| 850 | (−0.02, +0.09) | 98.5 | (+0.51, +0.23) (+0.78) | 215 | +78.3 | OK — contact (+0.10, +0.08) |
| 852 | (−0.02, +0.11) | 99.6 | (+0.53, +0.23) (+0.79) | 219 | +78.2 | OK |
Camera 2.15 m behind the elder, 0.78 m to his left (+X); his hat brim and left shoulder fill the right third, the shinobi is centred. In this reverse view +X is screen-LEFT: the elder's left shoulder is the one nearest frame centre. Bottom ray meets full grass at 2.5 m (the shinobi's grass line z 0.92, NDC y −0.59).

**Action.**
| frames | shinobi — two-handed | elder — ONE-HANDED |
|---|---|---|
| 841–842 | loaded in chudan at (0.30, −3.00) | low guard at (0, −0.45), left hand on the saya |
| 842–848 | launch on the half beat 13.5: `M.dash(SH, 842, 848, (0.30, -3.00), (0.30, -2.45))`, blade raised to his right shoulder 842–845 | watches; blade starts rising at 845 |
| 845–850 | `M.slash(SH, 845, 'diag_down_R')` (from his upper RIGHT (+X) toward the elder's LEFT shoulder); root (0.30, −2.40) at 850; at 850 right fist ≈ (0.42, −1.92, 1.66), blade dir (−0.26, 0.93, −0.23) | `M.deflect(SA, 850, 'mid_L')` one-handed on his LEFT (+X) side, feet planted: right fist ≈ (0.15, −0.88, 1.15), blade dir (0.18, −0.77, 0.61) (tip up-forward) |
| 850–852 | the cut is stopped dead; tip bounces up | holds, the parry absorbs it (no step) |

**Clash.** `M.clash(SH, SA, 850, point=(0.26, -1.35, 1.52), strength=0.7)` — attacker = the SHINOBI, sword/sword, medium: 0.61 m along his blade (monouchi), 0.61 m along the elder's. Sparks = attacker's colour code: **'white'** (cool white, red core), count 60, scale 1.0, direction (0.5, 0.3, 0.6) (toward screen-left/up, away from the elder's hat).

**Environment.** `ENV.set_sun(841, 250.0, 3.0, disk_deg=2.2)` (off-frame right, NDC (+4.4, +1.05): a low side key from screen-right on the shinobi's face/blade; the elder's back and hat brim stay a dark foreground shape).

**VFX.** `VFX.blade_trail("SHINOBI_katana_tip", "SHINOBI_katana_base", 844, 851, owner="shinobi")` (white, red core); `VFX.grass_burst(846, (0.30, -2.70, 0.3), direction=(0, 0.5, 0.6), count=40, speed=2.5, seed=crc("S09a:launch"))`.

**Events.**
```python
EV.emit(842, 'dash', who='shinobi', strength=0.6)
EV.emit(846, 'whoosh', who='shinobi', weapon='katana', strength=0.8)
# clash (0.7) at 850 from M.clash — beat 14
```
**Notes.** 12 f is the minimum; the whole attack is inside it (launch 842, contact 850, cut 852 = 2 f after).

### S09b — 853–868 (16 f) — counter 2, evaded by stepping back on 866
**Purpose.** The student turns the blade and sweeps back the other way; the master sways and steps back and the tip passes a hand's width short of his beard. For the first time the master gives ground.

**Camera — 3/4 rear over the elder's LEFT shoulder (φ ≈ +50), pulling back with his retreat.** The 30° shift from S09a opens the space in front of his chest, so the miss is visible past his left side (a straight OTS would hide it).
```python
C.shot("S09b", 853, 868, keys=[(853, (2.10, 1.00, 1.72), (0.12, -1.30, 1.45), 50.0),
                               (868, (2.35, 1.45, 1.72), (0.02, -0.62, 1.45), 50.0)],
       dof=dict(focus=("SAINT_rig", "head"), fstop=2.8), subjects=["shinobi", "saint"], framing="ots")
ENV.set_camera_clearance(853, 1.0, 2.2)
```
| frame | shinobi head | fig %H | elder head (hat top) | fig %H | φ | rule |
|---|---|---|---|---|---|---|
| 853 | (−0.57, +0.15) | 134.9 | (+0.80, +0.38) (+0.99) | 241 | +50.5 | OK |
| 858 | (−0.67, +0.20) | 135.4 | (+0.76, +0.38) (+0.98) | 236 | +49.9 | OK |
| 866 | (−0.62, +0.04) | 138.2 | (+0.61, +0.33) (+0.89) | 216 | +45.5 | OK — tip passes at (+0.25, −0.14), between them, in front of his chest |
| 868 | (−0.65, +0.07) | 138.8 | (+0.70, +0.34) (+0.92) | 222 | +44.7 | OK |
The hat brim (0.62 m) crops at the right/top edges by design (foreground OTS mass). Grass line on the shinobi z 0.91.

**Action.**
| frames | shinobi — two-handed | elder — ONE-HANDED |
|---|---|---|
| 853–858 | blade rebounds off the parry and is carried round to his LEFT (−X) hip; root (0.30, −2.40) → (0.30, −2.30) | half step back (0, −0.45) → (0, −0.25) on 853–858, blade low |
| 858–866 | `M.slash(SH, 858, 'horizontal_L')` (from his left (−X) sweeping to his right (+X)) with a deep step in: (0.30, −2.30) → (0.30, −1.60); at 866 the fists ≈ (0.29, −1.00, 1.40), blade dir (−0.25, 0.97, 0.03), tip ≈ (0.10, −0.27, 1.42) | sways back and steps: (0, −0.25) → (0, 0.00), torso leans back 10° (head −0.10 m), hat tilts up 5°, beard swings forward; beard tip ≈ (0, −0.08, 1.30) → the tip misses by ≈ 0.17 m |
| 866–868 | blade follows through to his right | begins the long glide back (to (0, 0.70) at 876) |

**Clashes.** none (near miss). Keep ≥ 0.12 m between the shinobi's blade and the beard/beard-cord bones at 862–868.

**Environment.** `ENV.set_sun(853, 250.0, 3.0, disk_deg=2.2)` (off-frame right-top).

**VFX.** `VFX.blade_trail("SHINOBI_katana_tip", "SHINOBI_katana_base", 859, 867, owner="shinobi")` (white/red, the horizontal arc — the trail is what sells the miss); `VFX.grass_burst(862, (0.30, -1.95, 0.3), direction=(0, 0.6, 0.5), count=35, seed=crc("S09b:step"))`.

**Events.**
```python
EV.emit(862, 'whoosh', who='shinobi', weapon='katana', strength=0.85)
EV.emit(866, 'step', who='saint', strength=0.7)           # beat 15: the step back that saves him
EV.emit(864, 'step', who='shinobi', strength=0.6)
```
**Notes.** The beard (secondary spring) reacts to the lean — it should swing into the space the blade just crossed. Cut at 868 (2 f after the miss).

### S09c — 869–936 (68 f) — distance reset (breath beat)
**Purpose.** Pull out and let it breathe: the master glides back and walks two measured steps on the beat, settles in his one-handed low guard; the student eases back to chudan. The gap (4.4 m) reads; S10 can begin its slow circle.

**Camera — elevated wide profile, slow lateral dolly following the midpoint (+X side, φ ≈ 0).**
```python
C.shot("S09c", 869, 936, keys=[(869, (8.60, -0.70, 2.55), (0.00, -0.70, 1.15), 28.0),
                               (936, (8.60, 0.40, 2.55), (0.00, 0.40, 1.15), 28.0)],
       dof=None, subjects=["shinobi", "saint"], framing="wide")
ENV.set_camera_clearance(869, 1.5, 4.0)
```
| frame | shinobi head | fig %H | elder head | fig %H | rule |
|---|---|---|---|---|---|
| 869 | (−0.17, +0.11) | 33.3 | (+0.21, +0.21) | 38.6 | OK |
| 897 | (−0.27, +0.14) | 34.7 | (+0.36, +0.22) | 39.3 | OK |
| 913 | (−0.35, +0.15) | 34.9 | (+0.41, +0.22) | 39.3 | OK |
| 936 | (−0.40, +0.15) | 34.9 | (+0.39, +0.22) | 39.1 | OK |
Pitch −9.25°: the grass sea fills the lower 60 %, horizon at NDC y +0.60, the sun disc between them just above it (el 1.2 → NDC (0.00, +0.67)). Grass line z 0.93 (NDC y −0.11): the figures read waist-up. Dolly speed 0.39 m/s.

**Action.**
| frames | shinobi — two-handed | elder — ONE-HANDED |
|---|---|---|
| 869–876 | recovers from the follow-through into chudan at (0.30, −1.58) | long glide back (0, 0.00 at 866) → (0, 0.70) at 876, blade low |
| 876–905 | two small steps back to (0.30, −1.80) (890, 905), tip on the elder's throat | measured steps back ON beats 17 and 18: (0, 1.75) at 897, (0, 2.40) at 913 |
| 905–936 | holds chudan; breathing; tails streaming | settles on beat 19 (928) at (0, 2.60) in `elder_low_guard_1h`, left hand on the saya, hat level; holds to 936 |
End state = HANDOFF[936] exactly (geom: 0.00 m error): shinobi (0.3, −1.8) facing 180 drawn two-handed; elder (0.0, 2.6) facing 0 drawn one-handed, hat on, haori on, spear slung.

**Clashes.** none. **VFX.** none (the parting grass wake behind the elder's glide comes from the environment).

**Environment.** `ENV.set_sun(869, 270.0, 1.2, disk_deg=2.2)`; `ENV.set_wind(869, 1.0)`.

**Events.**
```python
EV.emit(876, 'step', who='saint', strength=0.4)
EV.emit(897, 'step', who='saint', strength=0.4); EV.emit(913, 'step', who='saint', strength=0.4)
EV.emit(928, 'step', who='saint', strength=0.25)
EV.emit(890, 'step', who='shinobi', strength=0.3); EV.emit(905, 'step', who='shinobi', strength=0.3)
```
**Notes.** D6 long take. The last frame must be clean for the HANDOFF check (no motion blur smear: both roots CONSTANT-keyed from 930). Secondary motion keeps running (tails, beard, haori hem) — that is the only motion at 936.


## 4. Flash schedule + budget proof

Act I is classical: **one** full-frame lift in the whole lane. No `environment.flash` (lightning) anywhere in 433–936.

| frame | source / call | strength (share of full-frame white) | duration | why |
|---|---|---|---|---|
| 594 | `RS.key_white_flash(594, 0.0)` | 0 | — | clean pre-key (CONSTANT) |
| **595** | `RS.key_white_flash(595, 0.25)` | **0.25** | 1 f | FIRST CLASH exposure lift |
| 596 | `RS.key_white_flash(596, 0.10)` | 0.10 | 1 f | decay |
| 597 | `RS.key_white_flash(597, 0.0)` | 0 | — | off (total visible duration 2 f) |
| 595/631/725 | `RS.key_dispersion(…, 0.03–0.04)` → 0 after 2–3 f | 0 (colour fringe only) | 2–3 f | impact accent, no luminance |
| 595, 631, 709, 725, 850 (+ S07b stream 599–629) | spark pools' brief point lights (vfx.sparks light=True, 2–4 f, cutoff 8 m) | local, est. < 0.05 of frame luminance | 2–4 f | not a flash (area ≪ 25 %) |
| 466–471, 566–575 | `_local_glint` cards | local, < 0.02 | 5–10 f | not a flash |

Proof against DIRECTION §5 / config:
1. **Spacing ≥ 12 f (FLASH_MIN_GAP):** one flash event in the span, so trivially true; the nearest lift outside the lane is S13's ≈ 1367 (772 f later); the prologue has none near 432. The accent lights are also ≥ 16 f apart (595, 631, 709, 725, 850 → gaps 36, 78, 16, 125).
2. **≤ 70 % (non-FULL_WHITE):** peak mix 0.25 (render_setup clamps anything > 0.40 outside FULL_WHITE anyway); on a ~35–45 % luminance S07a frame the peak is ≈ 0.75·0.40 + 0.25 ≈ 55 % mean luminance.
3. **≤ 2 per second:** at most 1 lift per 24 f window; counting spark lights too, max 2 in any 24 f (709 + 725).
4. **flash_qc (> 3 opposing-flip pairs per 24 f = FAIL):** worst window 588–611. Turning points: 588 dark ECU → 595 peak (one merged rising flip: the 589 cut + the lift), 595 → 597/601 falling flip, possibly one rising flip at the 601 insert cut ⇒ ≤ 2 flashes ≤ 3 ✓. Other windows contain ≤ 1 cut-induced flip (541 S05→S06 is 48 f from 589). Keep S06 from going near-black (rim-lit lacquer + grass bokeh above the obi) and S07b's mean luminance within ±10 % of S07a (sun bokeh upper-left compensates the tighter, darker framing). Verify on the preview: `.venv/bin/python src/tools/flash_qc.py out/previews --start 433 --end 936 --strict`.
5. **FULL_WHITE (3265–3268):** not touched.

## 5. Local poses / moves not in the SPEC macro list

Implement in `acts/act1a.py` as `_local_*` helpers or as poses passed to `poses.key_pose` if the pose library lacks them (names below are the ones the blocks use). Degrees = bone-local Euler XYZ, +X = flexion (Pipeline rule 10).

| name | used | definition / intent |
|---|---|---|
| `_local_glint(obj, f0, f1, peak, size, path=None, peak_frame=None)` | S05 466–471, S06 566–575 | camera-facing emissive card (4-point star + one thin streak along the blade), parented to `obj` (a blade socket or `SAINT_katana_sheathed`), optional local `path` (start→end offsets) to slide along the metal; emission (1.0, 0.86, 0.62), strength keyed 0 → `peak` → 0 on film frames; material opaque DITHERED, no shadow; name `<shot>_glint`. Size 0.04 m (S05, reads ~6 px) / 0.012 m (S06). |
| `sh_hand_on_hilt` | S05 450–456 | shinobi reaches across: right hand on the tsuka 6 cm behind the tsuba (upper_arm.R flex 40°, adduct 35°; forearm.R 70°), left hand on the saya mouth, thumb at the tsuba (upper_arm.L flex 15°; forearm.L 60°); head level, eyes on the elder. Arm mode FK until the draw frame 456. |
| `elder_iai_crouch` | S05 486–516, held to 588 | hips −0.15 m (hips_offset z) and +0.05 fwd; right foot 0.35 m forward (thigh.R 35°, shin.R −40°), left foot back (thigh.L −10°, shin.L −25°); spine 8°, chest 7°, neck −3°, head −5° (brim low, eyes in shadow); right hand on the tsuka not gripping (upper_arm.R flex 45°, adduct 30°, forearm.R 55°); left hand on the saya at the koiguchi, thumb against the tsuba; hat and beard free (secondary). FK arms. |
| `sa_grip_close` | S06 580 | hand.R flex 4° (the fist closes on the tsuka) — the only motion after the click. |
| `M.iai_slash` fallback (horizontal, from the LEFT hip) | S07a 589–595 | 589: in-hand blade = sheathed matrix translated 0.35 m toward the hilt (40 % out) · 591: kissaki clears the koiguchi · 593: blade horizontal, pointing forward-left (+X), fist in front of the belly · 595: fist (0.14, −1.30, 1.34), dir (0.23, −0.97, 0.06), deep lunge (front knee 70°, hips +0.12 fwd, −0.10 down, chest turned 25° right-shoulder-forward). |
| receiving block `uke_nagashi_R` | S07a 592–595 (shinobi) | if `M.deflect(…, 'mid_R')` is vertical: override the sword ctrl with `CH.key_sword(SH, 595, grip=(0.22, -2.33, 1.12), direction=(0.18, 0.79, 0.59))`, edge toward +X/up; left hand stays on (IK_grip). The elder's blade then rides up this ramp during S07b. |
| `elder_low_guard_1h` | S07c 648 →, S08d 790 →, S08e, S09c 928 → | one-handed low guard: right fist 0.15 m in front of the right hip at 0.95 m, blade forward-down at −25° elevation (tip toward the opponent's knees), edge down; feet shoulder-width, right foot 0.2 m forward; torso upright, hat level. Left arm = `elder_offhand_saya`. |
| `elder_offhand_saya` | whole lane after 589 | left hand resting on the saya mouth (koiguchi), elbow out 20° (upper_arm.L flex 20°, abduct 20°, forearm.L 75°). DIRECTION §7: the one-handed master. |
| `elder_chamber_high_1h` | S08a 700 | blade raised over the right shoulder, one-handed: right fist beside the right ear, tip pointing up-back 45°, elbow high (upper_arm.R flex 150°, abduct 25°; forearm.R 60°); chest turned 15° right-shoulder-back. |
| `elder_thrust_chamber_1h` | S08c 728–746 | blade drawn back to the right hip, level (0° elevation), point at the shinobi's sternum; chest turned 25° right shoulder back; weight on the rear foot (hips −0.05, +0.05 back). Released by `M.slash(SA, 746, 'thrust')` → full extension 756: arm straight, chest turned square, front knee 75°. |
| `sh_regrip` | S08e 830–838 | two-handed: blade tip dips 5° (sword ctrl pitch) and returns over 6 f; shoulders drop 2 cm; chest −2° (exhale); fists stay on. |
| `_strafe_line(rig, f0, f1, p0, p1, facing)` | S08d 772–800 (shinobi) | lateral cross-step that keeps facing 180 (use if `M.walk` turns the rig toward its travel direction): root lerp with a 0.02 m vertical bob per step, steps every 9 f. |
| elder glide back | S09b 866 → S09c 876 | long sliding back-step (0.70 m in 10 f): feet drag (no lift), torso upright, blade low; then two measured steps 876–913 (`M.walk` backward, facing kept 0). |
| elder sway-back | S09b 858–866 | torso leans back 10° (spine −6°, chest −4°), head −0.10 m in y, hat tilts up 5°; beard springs swing forward into the space the blade crosses. |


## 6. Title overlays in the span

| id | frames | text | style | shot | legible | notes |
|---|---|---|---|---|---|---|
| `act1` | 445–528 | Act One / Blade | act | S05 (433–540) — the card lives entirely inside one locked shot, no cut under it | 478–513 (36 f); column ramps 461, accent 472, seal impact 473 | only title in 433–936 (`name_saint` ends 430) |

Card geometry (titles.py via `out/dev/breakdown/act1a/act_card_box.py`, NDC, +y up):
- big glyphs x +0.426…+0.658, y +0.006…+0.582 (0.21–0.50 H from the top); sub-column x +0.707…+0.769, y +0.058…+0.525; soft backdrop ellipse x +0.350…+0.845, y −0.294…+0.703.

How S05 leaves room:
- Horizon at NDC y −0.45: the whole card (ink and backdrop) is on sky, never on grass or figures.
- Elder (the figure under the card): hat top NDC (+0.61, −0.498) at 482 and (+0.60, −0.543) at 513 → 0.50 NDC = 206 px below the lowest ink and ≥ 0.20 NDC = 83 px below the backdrop. His iai sink (486–516) moves him *down*, away from it.
- Sun disc x −0.13…+0.13, y −0.63…−0.03: entirely left of the backdrop (x ≥ +0.35). The shinobi is on the left third.
- The camera is locked, so the card never slides against the background; the only big motion is the grass wave at ~500 running right→left across the lower quarter, below the card.
- Timing: the seal impact (473) lands one frame before the shinobi's hands settle into the two-handed grip (474); the elder's crouch (486–516) plays inside the legible window, so the card reads over a slow, readable action. If titles.py changes the card box again, re-run `act_card_box.py`; the hard limits are ink bottom ≥ −0.40 and backdrop bottom ≥ −0.45 (the horizon).

## 7. Risks + fallbacks

| # | risk | detection | fallback |
|---|---|---|---|
| 1 | S05 sun disc: far terrain/mountains hide more (or less) than the intended ~30 % of the 1.95° disc | preview frame 482 | raise `el` to 0.6° (more disc) or to 0.97° (disc bottom tangent to the horizon); never above 1.2° (continuity with S07–S09) |
| 2 | Far-field grass (1.1–1.5 m) in the S05 sight corridor (x 15…48 m) climbs to the figures' chests (grass line 1.26 m with max grass) | preview 433/540: visible upper body < 0.5 m | raise the S05 camera to z 2.40 (keep pitch 1.45°; checked: max-grass line 1.15 m, nominal 1.03 m, heads 0.10 NDC lower — shinobi y −0.74, elder hat −0.60) and tell the finale lane — the axis constant is `S05_AXIS` |
| 3 | S06: the elder's left sleeve pouch (`sleeve.L`) or hand hides the koiguchi from +X | layout render of 566 | rotate `sleeve.L` 30° back in `elder_iai_crouch`; else lower the camera 5 cm and yaw it 10° toward the elder's front |
| 4 | S06 click invisible (0.040 m slide too small at 100 mm) | preview 560–570 | increase the lens to 120 mm (same position) — the strip then spans ~0.5 NDC |
| 5 | 588→589 ellipsis jump smears (motion blur, START position) | final render frame 589 | make sure the 588 root/ctrl keys are CONSTANT (`U.set_key_interp_at`); if a smear remains, start the S07a dash 0.3 m further back (y 1.55) |
| 6 | First-clash gate (≤ 3–5 cm) fails at 595 | end_lane clash report / choreo_diag CSV | fix it with the elder's lunge (hips fwd offset 0.10–0.20, chest twist) — never by moving the roots (geometry proofs depend on them) |
| 7 | S07b grind looks mechanical or `M.blade_lock` cannot follow a moving point | preview 601–630 | key both sword ctrls explicitly at 601/615/630; reduce the slide to 0.08 m; keep the spark stream (it carries the shot) |
| 8 | S08c thrust reads as passing THROUGH the shinobi (foreshortening) | preview 750–758 | sidestep to x −0.65 and turn the torso 30°; or move the S08c camera +0.3 m in X (φ ≈ −70° at 756) so the gap opens on screen |
| 9 | Orbits (S08a, S08d) feel floaty / the chord cuts the arc | preview | keys every 7–9 f already approximate the arc (sag < 2 cm); if still floaty, reduce S08d to φ −45° → 0° or make S08a a straight lateral dolly (5.2, −4.6) → (5.2, −3.9) |
| 10 | S09b: the hat brim hides the miss at 866 | preview 862–868 | lower the camera 0.15 m and shift the look-at 0.10 m toward −Y; worst case push φ to +40° (still over the left shoulder) |
| 11 | Clash colour coding | review | attacker's colour: 595/709/725 gold (elder, Act I), 850 white/red-core (shinobi). Trails the same. |
| 12 | Cut-length QC complains about S08d (42 f ok) / S09c (68 f) | cut_list QC | split S09c at 905: S09c 869–904 as specified + **S09d 905–936** static medium-wide profile, camera (6.2, 0.40, 1.45) → look (0.0, 0.40, 1.30), 35 mm (checked: shinobi head (−0.71, +0.18) 64 % H, elder (+0.52 → +0.68, +0.28) 70 % H, rule OK, sun (0.00, +0.21)); add it to geom.py |
| 13 | flash_qc flags 588–611 | `flash_qc.py --strict` on the S05–S09 preview | drop the 595 lift to 0.15, then to 0 (the heavy spark bloom carries the hit); brighten S06 (sun el 3°) rather than darkening S07a |
| 14 | `moves` macros lack the kinds/params used (`stance` 'ready'/'chudan'/'iai'/'low_one_hand', `iai_slash` horizontal-from-left, `deflect` angles) | import/call errors | use the §5 local poses + `CH.key_sword` with the fists/directions given per clash (every clash block lists them) |
| 15 | Elder's reach at 709/725/850 short by > 5 cm | clash gate | extend with the lunge depth (front knee +10°, hips fwd +0.08) — never switch him to two hands before S13 (DIRECTION §7) |
| 16 | Secondary motion pops at intra-lane cuts | preview | springs reset on every sub-cut marker with a 24-f pre-roll (Pipeline rule 11) — keep poses still across 588/589 except the jump itself |
| 17 | HANDOFF drift at 936 (build QA tolerance 0.5 m) | geom.py / build QA | the tracks end exactly on (0.3, −1.8) and (0.0, 2.6) with CONSTANT keys from 930; do not add follow-through after 928 |

Simplification order if time runs short: drop the S07b spark stream to 5 bursts → drop the glints → replace the S08a/S08d orbits by straight dollies with the same end frames → merge S08e into a longer S08d (profile hold). Never drop: the click on 566, the first clash on 595 with the slow motion to 630, hits on 709/725/850 on the grid, the HANDOFF poses.

## 8. Implementation order for `acts/act1a.py` (suggested)

1. Re-assert HANDOFF[432] at 433 (roots, facing, weapon/costume/hat states — §1 tables); `ENV.set_state(433, 'dusk_gold')`.
2. Key both root tracks from §1 (CONSTANT at 588; ease elsewhere); check with `out/dev/breakdown/act1a/geom.py` tracks.
3. Poses/moves per block (§3), then sword ctrls + `M.clash` at 595, 709, 725, 850 (contact points in the blocks).
4. Cameras (13 `C.shot` calls, keys verbatim), clearance/sun/wind keys per cut, flashes (§4), VFX, events.
5. `bl_util.freeze_handles` on everything keyed; build the lane alone (`Blender -b --factory-startup --python src/blender/build_scene.py -- --lanes act1a --quality layout`), then run `cameras.check_screen_direction` / `framing_qa`, the clash report, `flash_qc`, and compare with `geom_report.txt`.

## Implementation notes (act1a implementer — `src/blender/acts/act1a.py`)

Deviations from the breakdown (same story beats, same frames) and why:
- **Flash strength.** `render_setup.key_white_flash` mixes toward LINEAR 16 (AgX display white): the planned 0.25 / 0.10 rendered a full-white frame. The soft exposure lift is keyed as 0.008 (595) → 0.003 (596) → 0 (597).
- **Lunges / sidesteps keyed locally** (`_local_root_path`): `moves.root_path` mis-normalises time when a macro passes a clock anchored at the impact frame (`slash(lunge=)`, `dodge`, `stagger`, `iai_slash`, spear lunges), so the whole root move landed in the single frame AFTER the impact (0.5–0.8 m teleports at 757, 851, 867). The lane passes `lunge=0` and keys the root glides itself on the breakdown's frames (hit 1 704→709, hit 2 718→725, thrust 749→756, sidestep 750→756, counters as `M.step` 842→850 / 859→866, elder sway 860→866).
- **S08c sidestep 0.65 m** (risk 8 fallback) and camera (1.02, −5.35, 1.50) instead of (0.72, −5.35, 1.66) so the gap between the thrust and the student opens on screen.
- **S09a counter 1** rebounds off the parry (`_retarget_strike(bounce=)`: 7 cm back, 5 cm up, tip +12°) instead of following through the elder's blade; the elder's blade is held in `low_1h` 860–869 so the counter-2 sweep cannot touch it (choreo_diag had flagged an unregistered blade contact at 865).
