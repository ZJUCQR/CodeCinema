# Lane act1b — S10–S14 (frames 937–1632) — shot breakdown

Status: COMPLETE (all sections filled; history in out/dev/breakdown/PROGRESS_act1b.md). Owner file for the implementer: `src/blender/acts/act1b.py`. Numbers here are binding unless marked "(tune)". `config.py` wins if it disagrees with a number copied here (import it; never re-type TEMPO_MAP / HANDOFF / TITLES). Geometry proofs: `out/dev/breakdown/act1b/geom.py` → `geom_report.txt` (pinhole identical to `bl_util.new_camera`: sensor_fit HORIZONTAL, 36 mm wide, 2.35:1 → 15.30 mm high). Re-run it after any change to a track or camera.

Conventions used below (same as docs/shots/act1a.md)
- Positions = rig origin on the ground (x, y) [+ root z when airborne]; facing α = `rig.rotation_euler.z` in degrees, facing vector (sin α, −cos α): 0 = −Y (elder), 180 = +Y (shinobi). **Key facings as continuous angles** (the shinobi goes 180 → 208.9 → 183.45, never 180 → −151.1).
- Screen positions are NDC: x −1 (left) … +1 (right), y −1 (bottom) … +1 (top). "fig %H" = full standing figure (ground → head/hat top) as % of frame height (feet are in the grass, so the visible part is smaller; for an airborne figure it is root-to-top + root height).
- Sun: `az` = compass bearing (0 = +Y, 90 = +X, 270 = −X), `el` = elevation; the same convention as `environment.set_sun`. **The far ridge line is at 1.0–1.2° between az 258° and 282°** (replica of `environment._ridge_profile` in geom.py `horizon_el`; 1.5° at 255°, 2.0° at 291°): a 2.2° disc with its centre at el ≈ 1.1–1.3 shows its upper half/two-thirds above the hills — the "setting sun" look that act1a's S09c ends on (el 1.2).
- Grass clearance `(near, far)` = `ENV.set_camera_clearance(f0, near, far)` for that cut (default (1.5, 4.0)); re-key the default on the next cut's f0 (CONSTANT keys hold forward). Grass tops in the arena: 0.95–1.15 m.
- Abbreviations as in act1a: `C = cameras`, `EV = events`, `ENV = environment`, `VFX = vfx`, `CH = characters`, `M = moves`, `RS = render_setup`, `U = bl_util`, `SH = SHINOBI_rig`, `SA = SAINT_rig`.

## 1. Lane summary

| | |
|---|---|
| Shots | S10, S11, S12, S13, S14 — frames **937–1632** (696 f = 29.0 s), **26 sub-cuts**, all hard cuts |
| Act / env | Act I "Act One · Blade", `dusk_gold`; the default crimson blend 1537→1632 (env `default_timeline`) turns the sky red in S14; the sun's last sliver disappears at **1586** |
| Enters (HANDOFF[936]) | shinobi (0.30, −1.80) facing 180, katana **drawn**, two-handed chudan; elder (0.00, 2.60) facing 0, katana **drawn** one-handed low guard (left hand on the saya), hat **on**, haori **on**, tasuki hidden, spear **slung** |
| Leaves (HANDOFF[1632]) | shinobi (0.00, −1.50) facing 180, katana **drawn**, two-handed chudan; elder (0.00, 6.50) facing 0, katana **sheathed**, hat **off** (cut, halves lying in the grass), haori **off** (thrown, lying at (1.76, 8.54)), tasuki **visible**, spear **in hand** — raised for the butt slam (pose note D3) |
| Track error at the boundaries | 0.00 m at 937 and at 1632 (geom.py prints it) |
| Clashes | **8** sword/sword contacts: 1132 (heavy, overhead block), 1195, 1210, 1226, 1241, 1257, 1273 (flurry), 1367 (perfect deflect) + the blade lock 1276–1320; plus the hat cut 1420 (blade/hat, no clash) |
| Slow motion | only 1367–1408 (`config.SLOWMO[1]`, fx speed 0.2 from `config.TIME_WARP`) |
| Full-frame lifts | 1132 (0.20, 1 f) and 1367–1368 (0.35, 2 f) — see §4 |
| Elder's hands | ONE-HANDED 937–1345 (incl. the S11 overhead block); **first two-handed grip 1346** (S13a) → two-handed until he sheathes (1496); spear two-handed from 1594 |

Story of the lane in one line: the student circles and vanishes into the grass; the master closes his eyes, listens, re-sheathes and answers with one draw-cut that shears the whole field's tops; the student is flushed into the air and comes down on him; a flurry, a lock, a shove; the master goes two-handed for the first time — and is perfectly deflected; the counter splits his hat; bare-headed now, he sheds the haori and draws the spear as the sun goes down.

Root tracks (key frames; ease in/out between keys unless noted; geom.py `SH_TRACK` / `EL_TRACK` are the same data, α = facing, z = root height, "dz" = head drop used for the framing proofs)

| frame | shinobi (x, y) α [z] | elder (x, y) α | what happens |
|---|---|---|---|
| 937 | (0.30, −1.80) 180 | (0.00, 2.60) 0 | HANDOFF[936]; both still (5 f) |
| 942 → 982 | circle CCW around the elder, r 4.41: (0.30, −1.80) → (0.78, −1.74) 952 → (1.25, −1.63) 962 → (1.70, −1.47) 972 → (2.13, −1.26) 982; α 183.9 → 208.9 (always facing the elder) | pivots in place, α 3.9 → 28.9 (facing the shinobi) | circling stand-off, 25° (0.77 m/s crossing steps) |
| 976 → 988 | sinks while still sliding: (2.13, −1.26) 982 → (2.01, −1.36) 988; head top ≤ 0.83 m from 986 (hidden) | α 28.9; head lowers 990 (eyes closed) | hiding in the grass — he vanishes |
| 988 → 1040 | crouch-run CW back round the elder (the ripple): (1.77, −1.37) 1000 → (1.32, −1.46) 1012 → (0.88, −1.52) 1024 → (0.47, −1.53) 1034 → **H = (0.25, −1.54) 1040**, α 204 → 183.45 | still, α 28.9 (only the head turns, ≤ 12°, following the sound) | the ripple betrays him; it stops at H (4.15 m) |
| 1040 → 1098 | coiled at H | 1036–1054 sheathes (guard seats 1054, no click event); iai crouch by 1072 | stillness |
| 1099 → 1102 | — | draw-cut with a pivot α 28.9 → 3.45 (faces H); shear starts 1101 | THE DRAW (beat 30) |
| 1102 → 1132 | leap from H: z 0.51 (1104), 0.95 (1106), 1.62 (1110), **2.15 apex (1118)**, 1.60 (1126), 0.91 (1130), 0.46 (1132); xy (0.25, −1.54) → (0.04, 1.22) linearly | follow-through 1102–1110, blade up to the overhead block by 1126 | the cut-line passes under him at 1106 |
| 1132 | (0.04, 1.22) z 0.46 | (0.00, 2.60) α 3.45 | **overhead block, clash_heavy** (beat 32) |
| 1134 → 1176 | lands (0.03, 1.40) 1134; thrown off: hop back z 0.55 at 1146, lands low (0.00, 0.30) 1152, slides to (0.00, 0.15) 1158, rises 1166; (0.00, 0.20) 1176 | α → 0 by 1140; (0.00, 2.60) → (0.00, 2.50) 1176 | aftermath, reset |
| 1182 → 1273 | 0.30 → 0.80 (1190) → **0.88 (1195)** → 0.80 (1210) → 0.95 (1226) → 0.85 (1241) → 1.02 (1257) → 1.15 (1273) (all x 0, α 180) | 2.50 → **2.46 (1195)** → 2.40 (1210) → 2.55 (1226) → 2.42 (1241) → 2.62 (1257) → 2.40 (1273) (x 0, α 0) | flurry, separation 1.55–1.60 m at every contact (1.25 at 1273) |
| 1276 → 1320 | (0.00, 1.30) → (0.00, 1.34) 1298 → (0.00, 1.33) | (0.00, 2.22) → (0.00, 2.24) → (0.00, 2.23) | blade lock (0.92 m apart) |
| 1321 → 1344 | cheat to 1.23 at 1321 (−0.10, hidden by the cut), skids to −0.35 (1334), −0.55 (1340) | 2.30 (1321, cheat +0.07) → 2.95 (1336) | skid apart (shove on 1320 in the cut) |
| 1345 → 1367 | −0.55 → −0.50 (1360) → **−0.35 (1367)** | 2.95 → 2.80 (1355, jodan) → 1.30 (1365, lunge) → **1.25 (1367)** | first two-handed overhead; perfect deflect (sep 1.60) |
| 1367 → 1408 | → −0.32 | → 1.35 (posture broken, leaning back) | slow motion (8 story frames of motion) |
| 1409 → 1420 | −0.25 (1412) → 0.15 (1418) → **0.18 (1420)** | 1.38 (1416) → **1.40 (1420)** leaning back (head at y 1.58) | rising cut splits the hat 1420 |
| 1422 → 1450 | → 0.10 (1430) → −0.90 (1446) | hop back z 0.25 at 1430 (3.20), lands 3.70 (1434), skids to **6.20 (1446)**, 6.25 (1450) | skid back 4.8 m through the grass |
| 1451 → 1632 | −0.90 → −1.50 (1470–1488, two steps back, off-screen), holds | 6.25; half step back 1560–1568 → **6.50**; holds | S13e reveal, S14 ritual |
| 1632 | **(0.00, −1.50) 180** | **(0.00, 6.50) 0** | HANDOFF[1632] |

Weapon / costume / hand states (all keyed with `characters.*` helpers, CONSTANT)

| frame | call | note |
|---|---|---|
| 937 | `CH.set_weapon_state(SH, 937, 'drawn')`, `CH.set_two_hand(SH, 937, True)`; `CH.set_weapon_state(SA, 937, 'drawn')`, `CH.set_two_hand(SA, 937, False)`, `CH.set_costume(937, haori=True)`, `CH.set_hat(937, 'on')`, `CH.set_weapon_state(SA, 937, 'slung')` | re-assert HANDOFF[936] (lane isolation) |
| 1044 → 1054 | key `SAINT_sword_ctrl` so the in-hand blade slides into the saya: kissaki at the koiguchi at 1044, `CH.sheathed_ctrl_matrix(SA, 1054)` at 1054 | the in-hand blade coincides with the sheathed one on the swap frame (no pop) |
| 1054 | `CH.set_weapon_state(SA, 1054, 'sheathed')`, `CH.set_arm_mode(SA, 1054, 'fk')` | the guard seats = `sheathe` event 1054 |
| 1099 | `CH.set_arm_mode(SA, 1099, 'ik')`, key ctrl = `CH.sheathed_ctrl_matrix(SA, 1099)`, `CH.set_weapon_state(SA, 1099, 'drawn')` | the iai: blade out of the saya 1099→1100, horizontal sweep 1100→1103 |
| 937–1345 | elder one-handed; off hand = `elder_offhand_saya` (act1a §5) except the overhead block (left hand free, fist on the hip) | DIRECTION §7 |
| **1346** | `CH.set_two_hand(SA, 1346, True, blend=3)` | the master's FIRST two-handed grip (visible in S13a) |
| 1420 | `CH.set_hat(1420, 'cut')`; `CH.snap_free('SAINT_hat_half_A', 1420)`, same for `_B`; then `props.toss` (§3 S13c) | the hat splits (hidden by nothing — it IS the image) |
| 1496 | `CH.set_two_hand(SA, 1496, False, blend=3)` | he lowers the blade to sheathe |
| 1500 → 1510 | ctrl slides into the saya; `CH.sheathed_ctrl_matrix(SA, 1510)` at 1510 | as 1044–1054 |
| 1510 | `CH.set_weapon_state(SA, 1510, 'sheathed')`, `CH.set_arm_mode(SA, 1510, 'fk')` | `sheathe` event 1510 |
| 1532 | `CH.set_costume(1532, haori=False)` + haori snapshot → `SAINT_haori_thrown` toss (§3 S14b) | haori shed; tasuki visible from 1532 |
| 1580 | `CH.set_arm_mode(SA, 1580, 'ik')`, `CH.set_spear_grip(1580, grip_R=1.40)`, ctrl = `CH.slung_spear_ctrl_matrix(1580, grip_R=1.40)`, `CH.set_weapon_state(SA, 1580, 'in_hand')` | the right hand has the shaft above the right shoulder; `SAINT_spear_sheath_world` appears here and must FOLLOW the tip until 1588 (local helper §5) |
| 1588 | sheath released (`props.toss`, §3 S14d) | `sheath_drop` event 1592 (whirr; its thud lands 0.66 s later = 1608, when the sheath enters the grass) |
| 1590 → 1600 | `CH.set_spear_grip(…, grip_R 1.40 → 0.55)`; `CH.set_two_hand(SA, 1594, True, weapon='spear')`, `grip_L` 1.15 | the hands settle for the twirl |
| 1632 | spear in hand, raised (butt down) | HANDOFF[1632] |
| shinobi, whole lane | two-handed (`IK_grip` on) — incl. the crouch-run and the leap | DIRECTION: frequent two-handed grip |

Deviations and decisions (everything else follows config / HANDOFF exactly)
- **D1 — facings during the circle.** HANDOFF[936] facings (180 / 0) rotate by +28.9° with the S10 circle (the elder pivots in place, the shinobi circles him) and come back: the elder to 3.45 at the draw (1102) and 0 by 1140, the shinobi to 183.45 at H and 180 on landing (1134). The fight after 1134 is on the Y axis (x ≤ 0.05).
- **D2 — 1195 vs the beat grid.** `beat_frame('act1', 36)` = 1194 (1194.48); config S12 desc says 1195 (and cuts 1177–1197 around it). We follow config: 1195 is 0.52 f after the exact beat, inside the ±1 f sync budget. All other hits are exact beats (1101, 1132, 1210, 1226, 1241, 1257, 1273, 1320, 1351, 1367, 1586).
- **D3 — HANDOFF[1632] pose.** HANDOFF lists positions/states only; this lane ends with the spear raised vertically in both hands, butt 0.45 m above the ground and moving down, so act2 can open S15 on the butt impact at 1633 (a cut on the contact). **Act2 must key the slam's impact on 1633 from this pose** (open question Q1).
- **D4 — spear_draw at 1586, not 1584.** "≈1584" in config/DIRECTION; 1586 = beat 61 (1585.78), where the score's `G.q(t_sd, 2)` would snap anyway. The sun's last sliver disappears on the same frame.
- **D5 — the sunset is keyed explicitly.** `key_lane_defaults` sinks the sun linearly 4.0° → −1.5° over 1489–1585, but the far ridge is at ≈ 1.1° near az 270, so the default disc would vanish at ≈ 1557; and the default crimson blend (1537–1632) fades `disk_vis` 1 → 0 over the same frames. This lane keys `set_sun` per cut (below) and holds `disk_vis` at 1.0 until 1586 (`ENV.set_param(1586, 'disk_vis', 1.0, 'LINEAR')`, `ENV.set_param(1590, 'disk_vis', 0.0, 'CONSTANT')`); the rest of the crimson blend stays default.
- **D6 — shear height.** `environment.grass_effect('shear')` clips every clump above ≈ 0.62 × its height (stubble 0.59–0.71 m; the vfx wrapper's `cut_height` is not used by the env). The crouching shinobi's head top is at 0.83 m, so he MUST be airborne before the line reaches H: take-off 1102, line at H at 1106 (feet at 0.95 m) — see S11c.
- **D7 — one extra reaction cut (S14c, the shinobi).** S14 is the elder's ritual; a 22-f reaction of the shinobi between the haori and the spear keeps the geography alive (he is 8 m away) and gives the draw a "cut-in" moment.
- **D8 — the elder's 4.8 m skid (1422–1446).** Needed to reach y 6.2–6.5 for HANDOFF[1632] (the ring of fire in act2 needs the 8 m gap). Staged as a hop back (z 0.25) + a long skid, not a walk.

## 2. Beat grid (Act I, 92 BPM, anchor 631)

`config.beat_frame('act1', b)` = round(631 + b·15.652); 4/4 bars (bar = b//4 + 1). 64 beats from 631 land on 1633 (the act2 downbeat = the spear-butt slam). The score (`src/audio/score.py arr_act1`) is event-driven in this span: it reads the first `grass_shear` (the draw-cut hit, quantised to half beats), the first `clash_heavy` 0.2–4 s after it (the overhead block → tutti), `blade_lock` + its duration (→ the shove), the first `whoosh` after the shove + 0.3 s and before the deflect (the two-handed overhead → odaiko + tremolo), `perfect_deflect` / `hat_cut` (drums drop out in the slow motion and return on the hat cut), `haori_shed` (the shakuhachi sigh) and `spear_draw` (the build into Act II). Those events are therefore placed on the frames below.

| beat | frame | bar.beat | used for |
|---|---|---|---|
| 20 | 944 | 6.1 | the "hide" music section starts (first bar inside S10); `heartbeat` event starts; circling under way (942) |
| 21 | 960 | 6.2 | circling step accent |
| 22 | 975 | 6.3 | the shinobi starts to sink (976) |
| 23 | 991 | 6.4 | **S10b** cut — the ripple |
| 24 | 1007 | 7.1 | ripple mid-crossing |
| 25 | 1022 | 7.2 | (S10c) listening, head turn toward the sound |
| 26 | 1038 | 7.3 | ripple stops at H (1040); sheathing starts (1036) |
| 27 | **1054** | 7.4 | **the elder's blade seats in the saya** (`sheathe`, no separate tsuba_click — the click motif stays S06/S24/S26) |
| 28 | 1069 | 8.1 | iai crouch complete (1072) |
| 29 | 1085 | 8.2 | (stillness; heartbeat at its fastest) |
| 30 | **1101** | 8.3 | **THE DRAW-CUT**: `grass_shear` (origin = the elder), shear t0 |
| 31 | 1116 | 8.4 | the leap's apex (1118) |
| 32 | **1132** | 9.1 | **overhead block** — `clash_heavy` (strength 1.0), impact shake, exposure lift 0.20 |
| 33 | 1148 | 9.2 | the shinobi's hop back lands (1152) |
| 34 | 1163 | 9.3 | he rises to chudan (1166) |
| 35 | 1179 | 9.4 | the dash starts (1180) |
| 36 | 1194 (config: **1195**) | 10.1 | **clash 1** — shinobi `diag_down_R` vs elder block (D2) |
| 37 | **1210** | 10.2 | **clash 2** — elder `horizontal_R` vs shinobi `mid_L` |
| 38 | **1226** | 10.3 | **clash 3** — shinobi `rising_L` vs elder `low` |
| 39 | **1241** | 10.4 | **clash 4** — elder `diag_down_R` vs shinobi `high` |
| 40 | **1257** | 11.1 | **clash 5** — shinobi `thrust` vs elder sweep (`mid_L`) |
| 41 | **1273** | 11.2 | **clash 6** — elder `overhead` vs shinobi `overhead_block` → lock |
| 42 | 1288 | 11.3 | lock: pressure pulse 1 |
| 43 | 1304 | 11.4 | lock: pressure pulse 2 |
| 44 | **1320** | 12.1 | **the shove** (on the cut, hidden) — `blade_lock` 1276 + 44 f ends here |
| 45 | 1335 | 12.2 | skid stops (1336/1340) |
| 46 | **1351** | 12.3 | the elder's two-handed rise to jodan — `whoosh` (the score's "heavy overhead" hit) |
| 47 | **1367** | 12.4 | **perfect deflect** (`perfect_deflect`, `music_cue perfect_deflect`), slow motion 1367–1408 |
| 48–50 | 1382, 1398, 1414 | 13.1–13.3 | (slow motion; drums out) |
| 50.4 | **1420** | — | **hat cut** (config MUSIC_CUES; the score hits on the event, not the grid) |
| 52 | 1445 | 14.1 | skid ends (1446) |
| 56 | 1508 | 15.1 | the elder's katana seats (sheathe 1510, 2 f late — a breath, not a hit) |
| 57 | 1523 | 15.2 | hand to the haori collar |
| 58 | ≈1532 | 15.3 (1539) | **haori shed** 1532 — deliberately off-beat (the sigh is free) |
| 60 | 1570 | 16.1 | the shinobi's regrip (S14c) |
| 61 | **1586** | 16.2 | **spear draw** (`spear_draw`), the sun's last sliver disappears (D4) |
| 62 | 1601 | 16.3 | twirl under way (1592–1620) |
| 63 | 1617 | 16.4 | twirl ends; raise for the slam |
| 64 | 1633 | 17.1 | (act2) butt impact = `fire_ignite` |

Hit rhythm: the draw (beat 30) → the block on the bar line (32); the flurry is six consecutive beats 36–41 (student / master alternating: S M S M S M), the lock holds a full bar (41→44), the shove lands on the bar line 44, the overhead rises on 46 and is deflected on 47. Contacts are never closer than 15 f apart (1195 → 1210).

## 3. Sub-cuts

Cut list (final; every block below repeats its frames). All hard cuts; lengths 12–48 f for fight cuts, longer only for stillness beats (S10a, S11a, S13e, S14a) and the blade lock (S12g, 45 f).

| cut | frames | len | camera | lens | z (m) | beat / story point |
|---|---|---|---|---|---|---|
| S10a | 937–990 | 54 | orbit / lateral dolly through foreground grass, 22.6° with the circle | 50 | 1.20 | circling; the sun passes from him to the master; hiding in the grass |
| S10b | 991–1012 | 22 | locked OTS over the elder's LEFT shoulder | 50 | 1.70 | the ripple crawls toward the master |
| S10c | 1013–1032 | 20 | MCU 3/4 front, slow push | 85 | 1.80 | the master listens, eyes under the brim; heartbeat |
| S11a | 1033–1072 | 40 | locked medium 3/4 front, sun in frame | 45 | 1.30 | re-sheathe (1054), iai crouch |
| S11b | 1073–1096 | 24 | inside the grass, OTS behind the shinobi's RIGHT shoulder, rack focus | 32 | 0.95 | the hidden student, poised |
| S11c | 1097–1118 | 22 | elevated wide (pitch −23°) | 24 | 5.2 | THE DRAW (1101), the shear arc, the leap |
| S11d | 1119–1134 | 16 | low angle in the stubble, tilt down | 18 | 0.70 | the plunge; overhead block **1132** |
| S11e | 1135–1176 | 42 | crane down (high wide → two-shot) | 24→30 | 7.8→2.2 | the sheared crescent; thrown off; reset |
| S12a | 1177–1197 | 21 | OTS over the shinobi's RIGHT shoulder, travelling | 40 | 1.70 | clash **1195** |
| S12b | 1198–1212 | 15 | OTS over the elder's LEFT shoulder | 40 | 1.80 | clash **1210** |
| S12c | 1213–1228 | 16 | low OTS over the shinobi's RIGHT shoulder | 35 | 1.30 | clash **1226** (rising) |
| S12d | 1229–1243 | 15 | blade insert, near profile, sun behind the steel | 55 | 1.66 | clash **1241** |
| S12e | 1244–1259 | 16 | OTS over the elder's LEFT shoulder | 45 | 1.72 | clash **1257** (thrust turned) |
| S12f | 1260–1275 | 16 | low 3/4 two-shot behind the shinobi's right | 28 | 1.05 | clash **1273** → lock |
| S12g | 1276–1320 | 45 | backlit telephoto profile, the lock on the sun disc | 150 | 1.12 | blade lock; shove on the cut |
| S12h | 1321–1344 | 24 | wide profile, lateral pan | 28 | 1.25 | skid apart |
| S13a | 1345–1368 | 24 | low profile, locked from 1362 | 30 | 1.10 | first two-handed grip 1346; overhead; **perfect deflect 1367** |
| S13b | 1369–1408 | 40 | tight 3/4, slow push (slow motion) | 35 | 1.50 | the ring, hanging sparks, posture broken |
| S13c | 1409–1422 | 14 | backlit telephoto profile, hat on the sun | 85 | 1.55 | rising cut; **hat cut 1420** |
| S13d | 1423–1450 | 28 | wide profile, lateral pan | 24 | 1.70 | hat halves fall; the master skids back 4.8 m |
| S13e | 1451–1488 | 38 | low MCU, tilt up | 65 | 1.30 | the shaven, scarred head (reveal) |
| S14a | 1489–1524 | 36 | low angle through foreground grass | 40 | 0.98 | sheathe (1510) |
| S14b | 1525–1552 | 28 | low angle wide | 28 | 1.02 | **haori shed 1532**; tasuki |
| S14c | 1553–1574 | 22 | MCU 3/4 front of the shinobi | 50 | 1.50 | the student's reaction (D7) |
| S14d | 1575–1604 | 30 | low-angle profile from 11 m against the setting sun | 50 | 1.35 | **spear draw 1586**, **sheath drop 1588/1592**, the sun gone 1586 |
| S14e | 1605–1632 | 28 | low wide | 24 | 0.95 | twirl; raised for the butt slam (1633 = act2) |

Shared conventions for every block
- Every camera is `C.shot(cut_id, f0, f1, keys, dof=..., shake=..., handheld=..., subjects=..., framing=...)`; keys are `(frame, pos, look, lens)` exactly as listed (look = a world point; geom.py produced them with an aim solver that places the subject at the stated NDC). The last key of each channel is CONSTANT (cameras.shot does it).
- Screen tables: head centres (NDC) + fig %H from `out/dev/breakdown/act1b/geom_report.txt` ("off" = outside the frame, allowed in singles/inserts). "rule" = shinobi_x < elder_x (two-shots) or the projected facing of the single (the shinobi must face screen-right, the elder screen-left). **All 26 cuts pass at every checked frame.**
- "bottom ray" = what the ray through the frame's bottom-centre hits first, and the camera-clearance grass scale there (1.00 = full height). No cut shows bare ground; the only sub-1.0 value is the intended near stubble in S11d.
- Every clash goes through `M.clash(attacker, defender, f, point)` (Pipeline rule 9). The contact points below are targets; end_lane nudges the defender ±3 f. Primary sparks/`clash` events come from `M.clash`; explicit `VFX.sparks` lines are extras only.
- `ENV.set_sun(f0, az, el, disk_deg=2.2)` and `ENV.set_camera_clearance(f0, near, far)` on each cut's first frame (CONSTANT) — values in each block; the sun disc keeps the default 2.2° everywhere in this lane.
- Colour coding (DIRECTION §6): the elder's trails/sparks **gold** (Act I), the shinobi's **white with a red core** (`VFX.owner_color`). Trails: `VFX.blade_trail('<C>_katana_tip', '<C>_katana_base', f0, f1)` windows listed per block.

### S10a — 937–990 (54 f) — the circle; hiding in the grass (stillness beat)
**Purpose.** The distance reset turns into a slow circle: the student probes, the master only turns. The sun slides from behind the student to behind the master (the circle made visible). At the edge of the arc the student sinks into the grass and is gone.

**Camera — orbit / lateral dolly through foreground grass, following the rotation (22.6° of arc), 50 mm.**
```python
C.shot("S10a", 937, 990, keys=[(937, (9.13, 1.01, 1.20), (0.15, 0.40, 1.30), 50.0),
                               (950, (9.23, 1.82, 1.20), (0.34, 0.42, 1.30), 50.0),
                               (962, (9.26, 3.03, 1.20), (0.62, 0.48, 1.30), 50.0),
                               (974, (9.12, 4.23, 1.20), (0.89, 0.59, 1.30), 50.0),
                               (990, (9.04, 4.63, 1.20), (0.99, 0.62, 1.30), 50.0)],
       dof=dict(focus=9.0, fstop=2.8), handheld=0.0,         # focus distance 9.0 m = the orbit radius
       subjects=["shinobi", "saint"], framing="wide")
ENV.set_camera_clearance(937, 0.9, 1.4)       # foreground blades from 1.4 m: the soft grass wipe across the bottom
```
(camera = midpoint of the pair + 9.0 m along the right normal of the shinobi→elder line, z 1.20; the keys are that formula sampled every ~12 f — BEZIER between them sags < 3 cm.) DOF: focus = the pair's midpoint (≈ 9.0 m), f/2.8, so the foreground blades at 1.4–3 m are pure bokeh.

| frame | shinobi head | fig %H | elder head | fig %H | rule |
|---|---|---|---|---|---|
| 937 | (−0.67, +0.17) | 60 | (+0.67, +0.27) | 69 | OK |
| 962 | (−0.67, +0.16) | 60 | (+0.67, +0.27) | 69 | OK |
| 976 | (−0.66, +0.05) | 54 | (+0.67, +0.27) | 69 | OK |
| 988 | (−0.61, −0.44) hidden | 30 | (+0.66, +0.24) | 67 | OK |
| 990 | (−0.61, −0.44) hidden | 30 | (+0.66, +0.23) | 67 | OK |

Bottom ray: foreground grass at 1.3 m (scale 0.98). Pitch +0.6°: grass line at the fighters' distance at NDC −0.18; the sinking shinobi's head top reaches NDC −0.35 at 988 (0.25 m under the grass tops). **Sun** az 257, el 1.35 (ridge 1.33 there → the upper half of the disc shows): NDC (−0.45, +0.08) at 937 → (+0.17, +0.08) at 962 (between them) → (+0.67, +0.09) at 990, directly behind the elder's shoulders = a gold rim around the master.

**Action.**
| frames | shinobi — two-handed chudan | elder — one-handed low guard |
|---|---|---|
| 937–941 | holds (breathing) | holds `elder_low_guard_1h` |
| 942–982 | `M.strafe(SH, 942, 982, center=(0.0, 2.6), radius=4.41, a0=-86.1, a1=-61.1)` (angles CCW from +X about the elder; root keys as §1; facing tracks the elder 183.9 → 208.9, continuous) — crossing side-steps, tip on the elder's throat | pivots in place, facing 3.9 → 28.9 (two small foot shuffles 950, 970); blade tip follows the student |
| 976–988 | sinks into `sh_grass_crouch` (§5) while still sliding (982 → 988: (2.13, −1.26) → (2.01, −1.36)); head top ≤ 0.83 m from 986 | — |
| 984–990 | hidden | lowers his head into `elder_listen` (§5): head −12°, brim over the eyes, blade tip into the grass tops |

**Clashes.** none. **VFX.** none (the parting of the grass around `SHINOBI_rig` is the environment's).

**Environment.** `ENV.set_sun(937, 257.0, 1.35, disk_deg=2.2)`; `ENV.set_wind(937, 1.0)`, `ENV.set_wind(976, 1.0)`, `ENV.set_wind(992, 0.35)` (LINEAR ramp: the field calms as he vanishes, so the ripple reads).

**Events.**
```python
EV.emit(944, 'heartbeat', bpm=60, duration=157)          # runs to the draw (1101)
EV.emit(962, 'wind_gust', strength=0.7)
for f in (946, 956, 966, 976): EV.emit(f, 'step', who='shinobi', strength=0.25, surface='grass')
for f in (950, 970): EV.emit(f, 'step', who='saint', strength=0.2)
```
**Notes.** 180° rule: the camera turns WITH the line (22.6°), so both stay on their sides; the move is continuous and ends on the +X side of the rotated line (DIRECTION §1). The drop is the only fast motion; cut 2 f after he is gone.

### S10b — 991–1012 (22 f) — the ripple
**Purpose.** Only a ripple betrays him: a travelling dent in the grass tops crawls toward the master's flank, seen past the master's own shoulder.

**Camera — locked OTS over the elder's LEFT shoulder, 50 mm.**
```python
C.shot("S10b", 991, 1012, keys=[(991, (0.30, 3.80, 1.70), (0.58, -1.18, 1.35), 50.0),
                                (1012, (0.30, 3.80, 1.70), (0.58, -1.18, 1.35), 50.0)],
       dof=dict(focus=(1.6, -1.4, 0.95), fstop=4.0), subjects=["shinobi", "saint"], framing="ots")
ENV.set_camera_clearance(991, 0.5, 1.0)
```
Camera 0.9 m behind and 0.84 m to the left of the elder (who faces 28.9°); pitch −4.0°; the elder's hat + left shoulder are a soft dark shape on the right edge.

| frame | shinobi head (hidden) | fig %H | elder head | fig %H | rule |
|---|---|---|---|---|---|
| 991 | (−0.69, −0.83) | 47 | (+0.72, +0.02) | 466 | OK |
| 1000 | (−0.59, −0.83) | 47 | (+0.72, +0.02) | 466 | OK |
| 1012 | (−0.36, −0.82) | 46 | (+0.72, +0.02) | 466 | OK |

The ripple (parting centre at grass-top height) enters at NDC (−0.71, −0.47) and crawls to (−0.40, −0.47) — toward the master's shoulder (screen-right). The shinobi's head stays 0.35 NDC under the grass surface. Bottom ray: grass at 2.9 m, scale 1.00. Sun az 262 el 1.25: behind-right of camera (side light from screen-right: the bent blades flash as the ripple passes).

**Action.** Shinobi (hidden): crouch-run in `sh_grass_crouch`, 988 → 1012 along the arc (§1), 4 low steps (994, 1000, 1006, 1012). Elder: still in `elder_listen`; 1004–1012 his head turns 6° to his right (toward the sound) — the only motion on the right edge.

**Environment.** `ENV.set_sun(991, 262.0, 1.25)`; wind stays 0.35. Optional parting softening (§5 `_local_part_angle`): 0.6 rad during 988–1101 so the ripple is a wave, not a hole.

**Events.** `for f in (994, 1000, 1006, 1012): EV.emit(f, 'step', who='shinobi', strength=0.15, surface='grass_crawl')` (heartbeat continues).

**Notes.** Keep the camera ≤ 1.8 m: from higher, the parting hollow would reveal his back.

### S10c — 1013–1032 (20 f) — the master listens (eyes closed)
**Purpose.** The master does not search: head lowered, eyes gone under the brim, he listens. The heartbeat is ours.

**Camera — MCU, 85 mm, eye level, slow push 0.25 m, 3/4 front from his left (+X side).**
```python
C.shot("S10c", 1013, 1032, keys=[(1013, (2.56, 2.17, 1.80), (-2.41, 2.56, 1.39), 85.0),
                                 (1032, (2.32, 2.21, 1.79), (-2.65, 2.59, 1.36), 85.0)],
       dof=dict(focus=(SA, "head"), fstop=2.0), subjects=["saint"], framing="mcu")
ENV.set_camera_clearance(1013, 0.5, 1.0)
```
| frame | shinobi | elder head | fig %H | rule |
|---|---|---|---|---|
| 1013 | off | (+0.28, +0.10) | 377 | faces L OK |
| 1032 | off | (+0.28, +0.10) | 414 | faces L OK |

Head at the right third, looking screen-left with lead room; bottom ray: grass at 4.3 m (scale 1.00). The camera stays at ≥ 1.78 m so the brim hides the eyes (the rig has no eyelids — the lowered brim IS "eyes closed"). Sun az 262 el 1.25 at NDC (−1.06, +1.16), just outside the top-left corner: a gold rim along the brim edge and the beard.

**Action.** Elder: `elder_listen`, motionless except 1018–1026 a further 8° head turn to his right (following the crawl) and the secondary motion of beard, cord and haori hem in the dying wind. Shinobi off-screen: (0.88, −1.52) 1024 → (0.47, −1.53) 1034 → stops at H (0.25, −1.54) 1040.

**Environment.** `ENV.set_sun(1013, 262.0, 1.25)`; wind 0.35.

**Events.** `EV.emit(1018, 'step', who='shinobi', strength=0.12, surface='grass_crawl')`, `EV.emit(1024, ...)` same; heartbeat continues.

**Notes.** Pure stillness; do not add handheld. The push-in is the tension.

### S11a — 1033–1072 (40 f) — the master re-sheathes (stillness beat)
**Purpose.** An answer is being prepared: the drawn blade goes home, the master sinks into the same iai stance the audience saw in S05 — still facing where the student vanished, head still lowered.

**Camera — locked medium, 45 mm, 3/4 front from his left; a 1-cm-per-frame tilt down with his crouch.**
```python
C.shot("S11a", 1033, 1072, keys=[(1033, (3.85, 1.95, 1.30), (-1.15, 2.10, 1.25), 45.0),
                                 (1072, (3.85, 1.95, 1.30), (-1.15, 2.07, 1.17), 45.0)],
       dof=dict(focus=3.75, fstop=2.8), subjects=["saint"], framing="medium")
ENV.set_camera_clearance(1033, 0.8, 1.6)
```
| frame | shinobi | elder head | fig %H | rule |
|---|---|---|---|---|
| 1033 | off | (+0.30, +0.55) | 140 | faces L OK |
| 1054 | off | (+0.31, +0.59) | 139 | faces L OK |
| 1072 | off | (+0.30, +0.55) | 135 | faces L OK |

The koiguchi (saya mouth, left hip) projects at (+0.33, −0.34): the sheathing plays in the lower right-centre. Bottom ray: foreground grass at 1.5 m (scale 0.98). **Sun** az 262 el 1.25 IN FRAME at (−0.43, +0.19): the disc half above the far hills, on the left — in the direction he faces and where the student hides.

**Action (elder, one-handed; shinobi off-screen, coiled at H).**
| frames | elder |
|---|---|
| 1033–1036 | `elder_listen` (still) |
| 1036–1044 | lifts the blade from the grass, turns the edge up, brings the back of the blade across his body to the left hand at the koiguchi (`M.sheathe(SA, 1036)` if it supports a 18-f sheathe; else local keys) |
| 1044 | kissaki enters the koiguchi — key `SAINT_sword_ctrl` there, then slide along the saya axis |
| 1054 | `CH.sheathed_ctrl_matrix(SA, 1054)` → `set_weapon_state(SA, 1054, 'sheathed')`, `set_arm_mode(SA, 1054, 'fk')`; the guard seats (beat 27) |
| 1056–1072 | sinks into `elder_iai_crouch` (act1a §5: hips −0.15, right foot forward, right hand on the tsuka not gripping, left thumb on the tsuba); body facing stays 28.9 (the student is now 25° to his right — the pivot comes with the draw) |

**Environment.** `ENV.set_sun(1033, 262.0, 1.25)`; `ENV.set_wind(1060, 0.35)`, `ENV.set_wind(1080, 0.12)` (the field holds its breath).

**Events.** `EV.emit(1054, 'sheathe', who='saint')` (the SFX pre-rolls the slide; NO `tsuba_click` — the click motif belongs to S06/S24b/S26); `EV.emit(1062, 'step', who='saint', strength=0.3)` (the front foot slides forward).

### S11b — 1073–1096 (24 f) — inside the grass: the hunter and the hunted
**Purpose.** We are with the student, inside the grass, blades across the lens; the master is a small iai silhouette beyond. We know where he is — and that the master knows.

**Camera — creeping OTS behind the shinobi's RIGHT shoulder, inside the grass (z 0.95), 32 mm.**
```python
C.shot("S11b", 1073, 1096, keys=[(1073, (1.60, -2.41, 0.95), (-1.23, 1.71, 0.84), 32.0),
                                 (1096, (1.54, -2.29, 0.95), (-1.40, 1.75, 0.76), 32.0)],
       dof=dict(focus=1.8, fstop=2.8, distance_keys=[(1073, 1.8), (1088, 1.8), (1095, 5.0)]),
       subjects=["shinobi", "saint"], framing="ots")
ENV.set_camera_clearance(1073, 0.25, 0.55)   # blades right up to the lens: the hiding place
```
| frame | shinobi head | fig %H | elder head | fig %H | rule |
|---|---|---|---|---|---|
| 1073 | (−0.50, −0.55) | 114 | (+0.55, +0.61) | 75 | OK |
| 1096 | (−0.50, −0.55) | 121 | (+0.61, +0.70) | 78 | OK |

Bottom ray: grass at 0.5 m (scale 0.86) — intended soft blades in the foreground. Rack focus 1088→1095 from the student (1.8 m) to the master (5.0 m): the cut to the draw is motivated by where the focus lands. Sun out of frame left (side light from screen-left).

**Action.** Shinobi: `sh_grass_crouch_coiled` (§5) — weight on the balls of the feet, sword two-handed along his right side, tip up but under the grass tops (tip z ≤ 0.92); head top 0.81 m; 1078–1084 head turns 5° toward the master (he heard the sheathing); 1090–1096 the legs load (hips −0.04). Elder: iai crouch, motionless.

**Environment.** `ENV.set_sun(1073, 262.0, 1.25)`; wind 0.12 (keyed in S11a).

**Events.** none new (the heartbeat runs until 1101).

**Notes.** His head top must stay under 0.95 m (the lowest grass tops).

### S11c — 1097–1118 (22 f) — THE DRAW-CUT: the grass tops sheared; flushed out
**Purpose.** One draw. A cut-line races out through the grass tops in a 220° arc, plumes bursting into silver fluff behind it; the student explodes out of the grass and rises ABOVE the line as it passes under him. No glowing anything — only grass that is suddenly shorter, and fluff.

**Camera — elevated wide, 24 mm, slow drift + tilt up with his rise (pitch −23° → −20°).**
```python
C.shot("S11c", 1097, 1118, keys=[(1097, (10.50, 0.20, 5.20), (0.00, 0.80, 0.70), 24.0),
                                 (1118, (10.30, 0.35, 5.00), (0.00, 0.90, 1.20), 24.0)],
       dof=None, subjects=["shinobi", "saint"], framing="wide")
ENV.set_camera_clearance(1097, 1.5, 4.0)
```
| frame | shinobi head | fig %H | elder head | fig %H | rule |
|---|---|---|---|---|---|
| 1097 | (−0.25, −0.05) hidden | 10 | (+0.20, +0.23) | 22 | OK |
| 1102 | (−0.27, −0.07) take-off | 10 | (+0.19, +0.20) | 22 | OK |
| 1106 | (−0.24, +0.34) | 32 | (+0.20, +0.18) | 23 | OK |
| 1112 | (−0.18, +0.53) | 44 | (+0.20, +0.15) | 24 | OK |
| 1118 | (−0.11, +0.60) apex | 48 | (+0.21, +0.13) | 24 | OK |

Bottom ray: grass at 4.8 m (scale 1.00). The draw happens at (+0.21, +0.07); the cut-line passes H at 1106 at (−0.29, −0.10) — directly under the rising student (head at +0.34); the south end of the arc runs out of the left edge (radius 14 m → NDC x −1.50); the east end passes under the camera ≈ 1114 (fluff bursting up past the frame bottom). **Sun** az 262 el 1.25 is above the top edge (NDC y +1.43): the camera looks down-sun, so every plume and every fluff tuft is back-lit gold.

**Action.**
| frames | elder (one-handed) | shinobi |
|---|---|---|
| 1097–1098 | thumb pushes the tsuba (no click event), right hand closes on the tsuka | coiled |
| 1099–1103 | `M.iai_slash(SA, 1099, ...)`: set_arm_mode 'ik', ctrl = `sheathed_ctrl_matrix(SA, 1099)`, `set_weapon_state(SA, 1099, 'drawn')`; blade out of the saya by 1100, one horizontal sweep from his left hip across the front to his right at 0.95–1.05 m (through the grass tops at his feet); root **pivots 28.9 → 3.45 by 1102** (the iai turn toward the sound) | 1102 take-off: `M.jump(SH, 1102, 1134, p0=(0.25, -1.54), p1=(0.03, 1.40), apex=2.15)`; root z = 6.5·t − 4.905·t² (t in s from 1102): 0.51 (1104), 0.95 (1106), 1.62 (1110), 2.02 (1114), 2.15 (1118) |
| 1103–1110 | follow-through: blade extended to his right (−X), horizontal, one-handed; left hand stays on the saya | tucked (knees to chest, sword two-handed along the body, tip back) — his feet are at 0.95 m when the line (0.59–0.71 m) passes H at 1106 |
| 1110–1118 | brings the blade up and over (the block is coming); head rises 1112–1118 — he looks up for the first time since 984 | unfolds at the apex, sword rising to jodan (two-handed) |

**Grass shear (the environment's).**
```python
ENV.grass_effect('shear', dict(origin=(0.0, 2.6), radius=14.0, arc_deg=220.0, facing_deg=176.5,
                                fluff=3600, wind=1.0), 1101, 1118)
# speed = 14 m / (17 f / 24) = 19.8 m/s (fx) -> the line reaches H (4.15 m) at 1106.0, the camera side (~11 m) at 1114
# arc = bearings 66.5 .. 286.5 (his whole front); stubble persists through Act I (until=None); fluff drifts downwind
```
(`VFX.grass_shear(1101, 1118, (0.0, 2.6), 14.0, 220.0, 176.5)` is the same call through the vfx wrapper — use ONE of them.)

**VFX.** `VFX.blade_trail('SAINT_katana_tip', 'SAINT_katana_base', 1100, 1104)` (gold, strength 1.0 — the only light the cut makes); `VFX.grass_burst(1102, (0.25, -1.54, 0.5), direction=(0.0, 0.3, 1.0), count=90, speed=3.0, fluff=0.5, seed=zlib.crc32(b"S11c:0"))` (his take-off tears the grass).

**Environment.** `ENV.set_sun(1097, 262.0, 1.25)`; `ENV.set_wind(1101, 0.12)`, `ENV.set_wind(1104, 1.3)`, `ENV.set_wind(1130, 1.0)` (the air of the cut, then the breeze back).

**Events.**
```python
EV.emit(1099, 'draw', who='saint')
EV.emit(1101, 'grass_shear', pos=(0.0, 2.6, 0.9))              # the score's draw-cut hit (beat 30)
EV.emit(1101, 'whoosh', who='saint', weapon='katana', strength=1.0)
EV.emit(1102, 'jump', who='shinobi')
EV.emit(1104, 'wind_gust', strength=1.2)
```
**Notes.** Deny-list: one physical cut only — no crescent, no projectile, no slash-lines filling the frame; the trail lives ≤ 4 f at the elder. The shot must start before the draw (1097) so the swing is whole.

### S11d — 1119–1134 (16 f) — the plunge; the overhead block (clash_heavy 1132)
**Purpose.** From the stubble, looking up: he comes down out of the sky, two-handed; the master's single raised blade takes it. Clash burst.

**Camera — low angle in the cut stubble (z 0.70), 18 mm, tilting down with the fall (pitch +28.5° → +19°).**
```python
C.shot("S11d", 1119, 1134, keys=[(1119, (3.10, 0.70, 0.70), (-1.17, 1.73, 3.09), 18.0),
                                 (1134, (3.10, 0.70, 0.70), (-1.20, 2.70, 2.29), 18.0)],
       dof=None, shake=[(1132, 0.9, 8)], subjects=["shinobi", "saint"], framing="wide")
ENV.set_camera_clearance(1119, 0.4, 0.9)     # stubble tips as blurred foreground
```
| frame | shinobi head | fig %H | elder head | fig %H | rule |
|---|---|---|---|---|---|
| 1119 | (−0.34, +0.63) | 144 | (+0.32, −0.56) | 78 | OK |
| 1126 | (−0.25, +0.66) | 128 | (+0.23, −0.38) | 71 | OK |
| 1132 | (−0.22, +0.07) | 81 | (+0.13, −0.22) | 64 | OK |
| 1134 | (−0.17, −0.50) landed | 51 | (+0.11, −0.19) | 64 | OK |

Contact at 1132 projects at (+0.05, +0.11) — frame centre. Bottom ray: stubble at 0.7 m (scale 0.76, intended). The camera stands inside the sheared zone (3.6 m from the elder, cut at 1105), so there is no tall grass in front of it. Sun az 262 el 1.25 enters the lower-left as the camera tilts down (NDC (−0.68, −0.72) at 1134): back light through the drifting fluff.

**Action.**
| frames | shinobi (two-handed) | elder (ONE-handed) |
|---|---|---|
| 1119–1126 | falling from the apex; jodan overhead | `M.deflect(SA, 1126, 'overhead_block')`: right fist (−0.22, 2.35, 1.98), blade (0.95, −0.15, 0.27) — horizontal above and in front of his head, edge up, angled so the strike slides to his left; left hand on the saya; knees start to bend |
| 1126–1132 | `M.slash(SH, 1126, 'overhead')` in the air (`M.plunge(SH, 1119, 1134, ...)` if available): fists (0.04, 1.62, 2.15), blade (0.0, 0.97, −0.14) at contact | holds; takes the hit 1132, knees give 5 cm (dz 0.14) |
| 1132 | contact, feet 0.46 m above the stubble | — |
| 1134 | lands in a deep crouch at (0.03, 1.40), blades still crossed | — |

**Clash.** `M.clash(SH, SA, 1132, (0.05, 2.28, 2.07))` — sword/sword, strength 1.0, kind `clash_heavy` (tags `['overhead_block']`); ≈ 0.65 m along his blade, 0.28 m along the elder's. Primary sparks from M.clash: white/red-core (attacker = shinobi), count 120, scale 1.6, direction (0, −0.3, 1). Extra: `VFX.sparks(1132, (0.05, 2.28, 2.07), direction=(0.0, 0.4, 0.9), count=50, color='gold', scale=1.2, seed=zlib.crc32(b"S11d:1"))` (the elder's steel).

**Clash burst VFX.** `VFX.grass_burst(1132, (0.0, 2.0, 0.45), direction=(0, 0, 1), count=160, speed=4.5, spread=80, fluff=0.6, seed=zlib.crc32(b"S11d:2"))` (stubble and fluff blown up and out); `VFX.dust_burst(1133, (0.0, 2.6, 0.0), radius=1.2, seed=zlib.crc32(b"S11d:3"))` (his feet driven down). Trail: `VFX.blade_trail('SHINOBI_katana_tip', 'SHINOBI_katana_base', 1122, 1132)`.

**Flash.** `RS.key_white_flash(1132, 0.20)` (1 f) + `RS.key_dispersion(1132, 0.04)` — §4.

**Events.**
```python
EV.emit(1128, 'whoosh', who='shinobi', weapon='katana', strength=0.9)
# clash_heavy at 1132 comes from M.clash (else: EV.emit(1132, 'clash_heavy', pos=(0.05, 2.28, 2.07), strength=1.0))
EV.emit(1134, 'land', who='shinobi', strength=0.8)
```
**Notes.** Cut 2 f after the contact (DIRECTION §2). The elder's left hand never joins (DIRECTION §7).

### S11e — 1135–1176 (42 f) — aftermath: the sheared field; thrown off; reset
**Purpose.** The payoff image of the draw: from above, the field around them is a 14-m crescent of stubble under drifting fluff. The master heaves the student off one-handed; the student lands, slides, rises. Reset.

**Camera — crane down: high wide → two-shot (pitch −33° → −7°), 24 → 30 mm.**
```python
C.shot("S11e", 1135, 1176, keys=[(1135, (11.50, 0.90, 7.80), (0.00, 1.20, 0.30), 24.0),
                                 (1176, (7.60, 1.35, 2.20), (0.00, 1.35, 1.25), 30.0)],
       dof=None, shake=[(1135, 0.5, 6)], subjects=["shinobi", "saint"], framing="wide")
ENV.set_camera_clearance(1135, 0.5, 1.0)     # the camera never goes below 2.2 m
```
| frame | shinobi head | fig %H | elder head | fig %H | rule |
|---|---|---|---|---|---|
| 1135 | (+0.03, +0.15) | 12 | (+0.14, +0.26) | 18 | OK |
| 1146 | (−0.04, +0.32) hop | 23 | (+0.16, +0.28) | 22 | OK |
| 1156 | (−0.13, +0.10) | 19 | (+0.19, +0.29) | 30 | OK |
| 1176 | (−0.24, +0.14) | 41 | (+0.24, +0.21) | 48 | OK |

Bottom ray: stubble at 5.5 m (scale 1.00). At 1135 the uncut grass wall at the arc's far end (−13.4, 6.6) is at the top edge (NDC y +0.96): the frame is all stubble and fluff with the two small figures at its centre.

**Action.**
| frames | shinobi | elder |
|---|---|---|
| 1135–1140 | crouched, pressing up into the crossed blades | holds the block, one-handed |
| 1140–1152 | thrown: `_local_heave` (§5) sends him back — hop z 0.55 at 1146, lands low at (0.00, 0.30) 1152 | 1140 heaves the blade up-and-forward (one arm), facing squares to 0 |
| 1152–1166 | `M.skid(SH, 1152, 1158, (0.0, 0.30), (0.0, 0.15))`, rises to chudan by 1166 | `elder_low_guard_1h` by 1150; half step in to (0.00, 2.50) 1170–1176 |

**VFX.** `VFX.dust_burst(1152, (0.0, 0.30, 0.0), radius=0.7, seed=zlib.crc32(b"S11e:0"))`; `VFX.grass_burst(1152, (0.0, 0.30, 0.3), direction=(0, -1, 0.6), count=50, speed=2.5, seed=zlib.crc32(b"S11e:1"))`. The shear fluff (env pool, life 2.5–5.5 s) drifts through the whole cut.

**Environment.** `ENV.set_sun(1135, 262.0, 1.25)`; wind 1.0 (keyed at 1130).

**Events.**
```python
EV.emit(1141, 'whoosh', who='saint', weapon='katana', strength=0.6)
EV.emit(1141, 'jump', who='shinobi')
EV.emit(1152, 'land', who='shinobi', strength=0.6); EV.emit(1152, 'skid', who='shinobi', duration=6)
EV.emit(1172, 'step', who='saint', strength=0.3)
```
**Notes.** Smooth two-key crane (no shake after 1141). Ends on a clean profile two-shot that S12a cuts in on.

### S12 — the flurry (1177–1344): shared data
Six contacts on six consecutive beats (36–41), student and master alternating; each cut ends **2 f after its contact** (config: 1177–1197, 1198–1212, 1213–1228, 1229–1243, 1244–1259, 1260–1275). OTS alternation: shinobi-right (a), elder-left (b), shinobi-right low (c), **blade insert** (d), elder-left (e), low 3/4 behind the shinobi's right (f). Separation at every contact 1.55–1.60 m (1.25 at 1273). The elder stays ONE-handed (left hand on the saya).

| frame | attacker → move | defender → move | contact point (world) | strength | sparks colour | trail window |
|---|---|---|---|---|---|---|
| 1195 | shinobi `slash('diag_down_R')` (from 1188) | elder `deflect('mid_L')` (1-h, blade vertical on his left) | (0.20, 1.66, 1.55) | 0.70 | white / red core | SH 1189–1195 |
| 1210 | elder `slash('horizontal_R')` (from 1204) | shinobi `deflect('mid_L')` | (−0.26, 1.38, 1.42) | 0.75 | gold | SA 1204–1210 |
| 1226 | shinobi `slash('rising_L')` (from 1219) | elder `deflect('low')` (his right side, tip down) | (−0.22, 1.74, 1.08) | 0.70 | white / red core | SH 1220–1226 |
| 1241 | elder `slash('diag_down_R')` (from 1235, chamber `elder_chamber_high_1h`) | shinobi `deflect('high')` (blade across above his left shoulder) | (−0.20, 1.40, 1.72) | 0.80 | gold | SA 1235–1241 |
| 1257 | shinobi `slash('thrust')` (from 1250, lunge) | elder `deflect('mid_L')` — sweeps the point to his left | (0.12, 2.02, 1.32) | 0.65 (+ scrape) | white / red core | SH 1251–1257 |
| 1273 | elder `slash('overhead')` (from 1266, 1-h, steps in) | shinobi `deflect('overhead_block')` | (0.04, 1.62, 1.95) → slides to the lock | 0.85 | gold | SA 1266–1273 |

`M.clash(att, def, f, point, strength=...)` for each row; `EV` clash events come from it. Whooshes: shinobi 1192, 1223, 1254; elder 1207, 1238, 1270 (`EV.emit(f, 'whoosh', who=..., weapon='katana', strength=0.6–0.8)`).

### S12a — 1177–1197 (21 f) — the student re-engages; clash 1 (1195)
**Camera — OTS over the shinobi's RIGHT shoulder, travelling with his dash, 40 mm.**
```python
C.shot("S12a", 1177, 1197, keys=[(1177, (0.80, -0.98, 1.70), (-0.81, 3.75, 1.60), 40.0),
                                 (1195, (0.80, -0.32, 1.70), (-1.07, 4.31, 1.52), 40.0),
                                 (1197, (0.80, -0.32, 1.70), (-1.07, 4.31, 1.52), 40.0)],
       dof=dict(focus=(SA, "head"), fstop=2.8), shake=[(1195, 0.5, 3)], subjects=["shinobi", "saint"], framing="ots")
ENV.set_camera_clearance(1177, 0.5, 1.0); ENV.set_sun(1177, 268.0, 1.1)
```
| frame | shinobi head | fig %H | elder head | fig %H | rule |
|---|---|---|---|---|---|
| 1177 | (−0.55, −0.54) | 301 | (+0.22, +0.05) | 138 | OK |
| 1188 | (−0.44, −0.63) | 282 | (+0.23, +0.09) | 156 | OK |
| 1195 | (−0.40, −0.71) | 277 | (+0.22, +0.05) | 165 | OK |
| 1197 | (−0.41, −0.68) | 281 | (+0.22, +0.06) | 166 | OK |

Contact 1195 at (+0.20, −0.19). Bottom ray: grass at 3.1 m (1.00). Sun off-frame left (side light on the master's face from screen-left).

**Action.** Shinobi: 1177–1180 set; `M.dash(SH, 1180, 1190, (0.0, 0.20), (0.0, 0.80))`; `M.slash(SH, 1188, 'diag_down_R')` → 1195 (root 0.88). Elder: `elder_low_guard_1h` (2.50) → `M.deflect(SA, 1195, 'mid_L')` (2.46). **Clash** 1195 (table). **Trail** SH 1189–1195. **Events** `dash` 1180 (shinobi), `whoosh` 1192, clash 1195.

### S12b — 1198–1212 (15 f) — the master answers; clash 2 (1210)
**Camera — OTS over the elder's LEFT shoulder, 40 mm, near-locked.**
```python
C.shot("S12b", 1198, 1212, keys=[(1198, (0.85, 3.70, 1.80), (-1.07, -0.88, 1.22), 40.0),
                                 (1212, (0.85, 3.65, 1.80), (-1.06, -0.93, 1.21), 40.0)],
       dof=dict(focus=(SH, "head"), fstop=2.8), shake=[(1210, 0.5, 3)], subjects=["shinobi", "saint"], framing="ots")
ENV.set_camera_clearance(1198, 0.5, 1.0)
```
| frame | shinobi head | fig %H | elder head | fig %H | rule |
|---|---|---|---|---|---|
| 1198 | (−0.22, +0.00) | 131 | (+0.40, +0.04) | 292 | OK |
| 1210 | (−0.22, −0.00) | 130 | (+0.40, −0.04) | 286 | OK |
| 1212 | (−0.22, +0.01) | 131 | (+0.42, −0.02) | 292 | OK |

Contact 1210 at (+0.13, −0.16). Bottom ray: grass at 2.4 m (1.00). Sun off-frame right (rim on the shinobi's left side).

**Action.** Elder: 1198–1204 chambers the blade to his right side (one-handed, horizontal); `M.slash(SA, 1204, 'horizontal_R')` → 1210 (root 2.44 → 2.40). Shinobi: recovers (0.84) → `M.deflect(SH, 1210, 'mid_L')` (0.80). **Clash** 1210. **Trail** SA 1204–1210 (gold). **Events** `whoosh` 1207 (saint), clash 1210.

### S12c — 1213–1228 (16 f) — the rising cut; clash 3 (1226)
**Camera — low OTS over the shinobi's RIGHT shoulder (z 1.30), 35 mm, small push.**
```python
C.shot("S12c", 1213, 1228, keys=[(1213, (0.92, -0.18, 1.30), (-1.25, 4.33, 1.35), 35.0),
                                 (1228, (0.92, -0.05, 1.30), (-1.26, 4.45, 1.36), 35.0)],
       dof=dict(focus=2.3, fstop=2.8), shake=[(1226, 0.45, 3)], subjects=["shinobi", "saint"], framing="ots")
ENV.set_camera_clearance(1213, 0.6, 1.2)
```
| frame | shinobi head | fig %H | elder head | fig %H | rule |
|---|---|---|---|---|---|
| 1213 | (−0.53, +0.52) | 278 | (+0.20, +0.50) | 155 | OK |
| 1226 | (−0.52, +0.37) | 271 | (+0.20, +0.50) | 155 | OK |
| 1228 | (−0.54, +0.42) | 277 | (+0.20, +0.51) | 157 | OK |

Contact 1226 (low) at (−0.23, −0.53). Bottom ray: grass at 1.2 m (1.00) — grass tops brush the bottom edge.

**Action.** Shinobi: 1213–1219 drops into `sh_low_chamber_L` (§5); `M.slash(SH, 1219, 'rising_L')` → 1226, stepping 0.86 → 0.95. Elder: `M.deflect(SA, 1226, 'low')` on his right side, gives 7 cm (2.48 → 2.55). **Clash** 1226. **Trail** SH 1220–1226. **Events** `whoosh` 1223 (shinobi), clash 1226.

### S12d — 1229–1243 (15 f) — blade insert; clash 4 (1241)
**Camera — insert on the blades, near-profile from +X, 55 mm at 2.3 m, locked on the impact (12-cm drift in).**
```python
C.shot("S12d", 1229, 1243, keys=[(1229, (2.30, 1.35, 1.66), (0.02, 1.52, 1.70), 55.0),
                                 (1243, (2.18, 1.38, 1.66), (0.02, 1.52, 1.70), 55.0)],
       dof=dict(focus=2.35, fstop=2.0), shake=[(1241, 0.4, 3)], subjects=["shinobi", "saint"], framing="insert")
ENV.set_camera_clearance(1229, 0.5, 1.0)
```
| frame | shinobi head | fig %H | elder head | fig %H | rule |
|---|---|---|---|---|---|
| 1229 | (−0.71, −0.80) | 252 | (+1.21, −0.21) off | 284 | OK |
| 1241 | (−0.87, −0.82) | 267 | (+1.14, −0.34) off | 295 | OK |
| 1243 | (−0.85, −0.80) | 269 | (+1.17, −0.31) off | 297 | OK |

Contact 1241 at (−0.17, +0.05) — the frame centre; the shinobi's head/shoulder is a dark mass bottom-left, the elder's arm enters from the right. **Sun** az 268 el 1.1 IN FRAME at (−0.34, +0.01) behind the blades (disc 60 % above the ridge 1.03): the steel crosses in front of the sun — the glint frame of the flurry.

**Action.** Elder: 1229–1235 `elder_chamber_high_1h` (act1a §5); `M.slash(SA, 1235, 'diag_down_R')` → 1241. Shinobi: `M.deflect(SH, 1241, 'high')`. **Clash** 1241 (strength 0.8, gold, count 90 — the insert sees them big). **Trail** SA 1235–1241. **Events** `whoosh` 1238 (saint), clash 1241.

### S12e — 1244–1259 (16 f) — the thrust turned aside; clash 5 (1257)
**Camera — OTS over the elder's LEFT shoulder, 45 mm, drifting back 0.17 m with his step.**
```python
C.shot("S12e", 1244, 1259, keys=[(1244, (0.92, 3.75, 1.72), (-1.04, -0.83, 1.29), 45.0),
                                 (1259, (0.92, 3.92, 1.72), (-1.02, -0.66, 1.23), 45.0)],
       dof=dict(focus=(SH, "head"), fstop=2.8), shake=[(1257, 0.35, 3)], subjects=["shinobi", "saint"], framing="ots")
ENV.set_camera_clearance(1244, 0.5, 1.0)
```
| frame | shinobi head | fig %H | elder head | fig %H | rule |
|---|---|---|---|---|---|
| 1244 | (−0.22, −0.00) | 148 | (+0.49, +0.11) | 321 | OK |
| 1257 | (−0.22, −0.00) | 142 | (+0.50, +0.16) | 318 | OK |
| 1259 | (−0.22, +0.02) | 144 | (+0.46, +0.20) | 312 | OK |

Contact 1257 at (0.00, −0.55) — the point comes straight at the lens and is swept to screen-right.

**Action.** Shinobi: 1244–1250 `sh_thrust_chamber` (§5); `M.slash(SH, 1250, 'thrust')` lunging 0.92 → 1.02. Elder: `M.deflect(SA, 1257, 'mid_L')` sweeping the point to his left (+X), stepping back 2.52 → 2.62. **Clash** 1257 + scrape: `VFX.sparks(1258, (0.20, 2.10, 1.34), direction=(0.6, 0.4, 0.5), count=25, scale=0.6, color='white', light=False, seed=zlib.crc32(b"S12e:1"))`. **Trail** SH 1251–1257. **Events** `whoosh` 1254, clash 1257.

### S12f — 1260–1275 (16 f) — the master's overhead; clash 6 (1273) → the lock
**Camera — low 3/4 two-shot from behind the shinobi's right (z 1.05), 28 mm, small push.**
```python
C.shot("S12f", 1260, 1275, keys=[(1260, (2.35, -0.70, 1.05), (-1.03, 2.90, 1.82), 28.0),
                                 (1275, (2.30, -0.55, 1.05), (-1.17, 2.96, 1.85), 28.0)],
       dof=None, shake=[(1273, 0.5, 4)], subjects=["shinobi", "saint"], framing="medium")
ENV.set_camera_clearance(1260, 0.6, 1.2)
```
| frame | shinobi head | fig %H | elder head | fig %H | rule |
|---|---|---|---|---|---|
| 1260 | (−0.25, −0.07) | 104 | (+0.19, −0.04) | 88 | OK |
| 1273 | (−0.21, −0.09) | 106 | (+0.17, −0.04) | 94 | OK |
| 1275 | (−0.17, −0.09) | 105 | (+0.13, −0.02) | 97 | OK |

Contact 1273 at (−0.04, +0.43) — high centre, against the sky (pitch +8.9°). Bottom ray: foreground grass at 1.1 m (0.90, intended). Sun off-frame left.

**Action.** Elder: steps in 2.45 → 2.40 raising the blade high behind his head (one-handed); `M.slash(SA, 1266, 'overhead')` → 1273. Shinobi: `M.deflect(SH, 1273, 'overhead_block')` stepping 1.08 → 1.15; 1273–1276 the blades slide down edge-on-edge to the guards. **Clash** 1273. **Trail** SA 1266–1273. **Events** `whoosh` 1270 (saint), clash 1273.

### S12g — 1276–1320 (45 f) — the blade lock: one backlit silhouette
**Purpose.** Guard against guard, faces 0.9 m apart, the sun disc behind the crossed steel: the student pushes with two hands, the master holds him with one.

**Camera — backlit telephoto profile, 150 mm at 18 m, a 0.4-m creep in.**
```python
C.shot("S12g", 1276, 1320, keys=[(1276, (18.00, 1.76, 1.12), (0.00, 1.76, 1.52), 150.0),
                                 (1320, (17.60, 1.78, 1.12), (0.00, 1.78, 1.52), 150.0)],
       dof=dict(focus=18.0, fstop=4.0), subjects=["shinobi", "saint"], framing="medium")
ENV.set_camera_clearance(1276, 1.5, 4.0); ENV.set_sun(1276, 270.0, 1.55)
```
| frame | shinobi head | fig %H | elder head | fig %H | rule |
|---|---|---|---|---|---|
| 1276 | (−0.19, −0.06) | 86 | (+0.19, +0.11) | 101 | OK |
| 1298 | (−0.17, −0.07) | 87 | (+0.19, +0.12) | 102 | OK |
| 1320 | (−0.18, −0.08) | 87 | (+0.18, +0.12) | 103 | OK |

Lock point (0.02, 1.77, 1.62) at (0.00, +0.11); **sun** az 270 el 1.55 at (0.00, +0.09) — exactly behind the lock; the 2.2° disc is 38 % of the frame height (NDC y −0.29 … +0.47), its lower third hidden by the far hills (ridge 1.18°). Bottom ray: grass at 3.7 m (0.97); the sight line clears the arena grass (≥ 1.23 m at 4 m from the lens).

**Action.** `M.blade_lock(SH, SA, 1276, 1320)` at the lock point; pressure pulses on beats 42 (1288: the lock drifts 3 cm toward the elder, the shinobi's knees drop 2 cm) and 43 (1304: the elder takes it back, 5 cm toward the student); elder one-handed, left hand on the saya, leaning in (chest +5°); hats and headband tails the only other motion. Grind sparks: `VFX.sparks(1288, (0.02, 1.78, 1.62), count=20, scale=0.6, color='gold', light=False, seed=zlib.crc32(b"S12g:0"))`, same at 1304 (seed 1).

**Events.** `EV.emit(1276, 'blade_lock', pos=(0.02, 1.77, 1.62), duration=44)` (the score's shove = 1276 + 44 = 1320).

**Notes.** Silhouette read: keep both heads inside the disc; no fill light. The shove happens ON the cut (1320 → 1321): nothing of the body contact is shown (DIRECTION §2). Key both roots CONSTANT at 1320 (cheat below).

### S12h — 1321–1344 (24 f) — skid apart
**Camera — wide profile, 28 mm, lateral pan with the separating pair.**
```python
C.shot("S12h", 1321, 1344, keys=[(1321, (7.80, 1.70, 1.25), (0.00, 1.70, 1.10), 28.0),
                                 (1344, (7.80, 1.25, 1.25), (0.00, 1.25, 1.10), 28.0)],
       dof=None, subjects=["shinobi", "saint"], framing="wide")
ENV.set_camera_clearance(1321, 0.5, 1.0); ENV.set_sun(1321, 262.0, 1.1)
```
| frame | shinobi head | fig %H | elder head | fig %H | rule |
|---|---|---|---|---|---|
| 1321 | (−0.09, +0.14) | 36 | (+0.11, +0.25) | 43 | OK |
| 1334 | (−0.34, +0.10) | 33 | (+0.28, +0.24) | 43 | OK |
| 1344 | (−0.35, +0.18) | 37 | (+0.34, +0.26) | 44 | OK |

Bottom ray: grass at 0.9 m (0.96). Sun in frame at (−0.22, +0.14), between them (disc half over the hills).

**Action.** Cheat across the cut (hidden): shinobi 1.33 → 1.23, elder 2.23 → 2.30 (CONSTANT at 1320). `M.skid(SH, 1321, 1340, (0.0, 1.23), (0.0, -0.55))` crouched (dz 0.30), rises to chudan 1340–1344; `M.skid(SA, 1321, 1336, (0.0, 2.30), (0.0, 2.95))`, blade low one-handed. Two furrows open in the grass (parting). **VFX.** `VFX.dust_burst(1322, (0.0, 1.20, 0.0), radius=0.6)`, `VFX.dust_burst(1322, (0.0, 2.32, 0.0), radius=0.5)`, `VFX.grass_burst(1326, (0.0, 0.70, 0.35), direction=(0, -1, 0.5), count=40, speed=2.0)` (seeds `crc32("S12h:i")`). **Events.** `EV.emit(1320, 'whoosh', who='saint', weapon='body', strength=0.7)` (the shove, on the cut); `EV.emit(1322, 'skid', who='shinobi', duration=18)`; `EV.emit(1323, 'skid', who='saint', duration=13)`.

### S13a — 1345–1368 (24 f) — the master's first two-handed blow; PERFECT DEFLECT 1367
**Purpose.** We SEE the left hand leave the saya and close on the hilt — for the first time the master takes him seriously. Jodan, a lunging heavy overhead — and the student meets it at the perfect instant: a white ring.

**Camera — low profile (z 1.10), 30 mm, drifting with the lunge, LOCKED from 1362 (camera still on the impact).**
```python
C.shot("S13a", 1345, 1368, keys=[(1345, (5.90, 1.25, 1.10), (0.00, 1.25, 1.60), 30.0),
                                 (1362, (5.90, 0.90, 1.10), (0.00, 0.90, 1.62), 30.0),
                                 (1368, (5.90, 0.90, 1.10), (0.00, 0.90, 1.62), 30.0)],
       dof=None, shake=[(1367, 0.3, 3)], subjects=["shinobi", "saint"], framing="medium")
ENV.set_camera_clearance(1345, 0.6, 1.2); ENV.set_sun(1345, 264.0, 1.1)
```
| frame | shinobi head | fig %H | elder head | fig %H | rule |
|---|---|---|---|---|---|
| 1345 | (−0.49, −0.08) | 54 | (+0.47, +0.03) | 63 | OK |
| 1355 | (−0.44, −0.09) | 54 | (+0.48, +0.05) | 64 | OK |
| 1367 | (−0.33, −0.14) | 51 | (+0.04, −0.10) | 57 | OK |
| 1368 | (−0.32, −0.14) | 51 | (+0.04, −0.09) | 57 | OK |

Contact 1367 at (−0.14, +0.11). Bottom ray: foreground grass at 1.1 m (0.90). Sun az 264 el 1.1 in frame between them at (−0.18, −0.26) (top half over the ridge 1.13).

**Action.**
| frames | elder (TWO-HANDED from 1346) | shinobi (two-handed) |
|---|---|---|
| 1345–1349 | **`CH.set_two_hand(SA, 1346, True, blend=3)`**: the left hand leaves the saya and closes on the tsuka below the right | chudan, (−0.55) |
| 1349–1355 | rises to jodan (`M.stance(SA, 1355, 'jodan')`), weight back (2.95 → 2.80) | one small step in (→ −0.50 by 1360) |
| 1355–1365 | the lunge: 2.80 → 1.30 (stamp 1356); downswing `M.slash(SA, 1360, 'overhead')` two-handed | 1360–1367 `M.deflect(SH, 1367, 'high')` stepping INTO it (→ −0.35): a short upward-outward snap, blade crossing at 30°, so the master's blade glances up and to HIS right (−X) |
| 1367 | contact (1.25) | contact |

**Clash (perfect deflect).** `M.clash(SA, SH, 1367, (0.06, 0.40, 1.78), strength=1.0, kind='perfect_deflect', tags=['perfect_deflect'])` — sword/sword; primary sparks **white**, count 140, scale 1.6, life 14 (fx: they hang ≈ 5× in the slow motion); extra `VFX.sparks(1367, (0.06, 0.40, 1.78), direction=(-0.5, 0.2, 0.8), count=60, color='gold', scale=1.2, seed=zlib.crc32(b"S13a:1"))`. **Flash ring.** `VFX.flash_ring(1367, (0.06, 0.40, 1.78), radius=0.6, color='white', duration=10, strength=2.5, star=0.9, light=True, light_energy=150.0, seed=zlib.crc32(b"S13a:2"))` (10 fx frames = ≈ 43 film frames through the slow motion; camera-facing, so it reads as a circle in S13b too). **Exposure lift.** `RS.key_white_flash(1367, 0.35, duration=2)` (1367–1368, ≤ 0.40) + `RS.key_dispersion(1367, 0.05)`. **Trails.** SA 1360–1367 (gold), SH 1363–1367 (white/red).

**Events.**
```python
EV.emit(1351, 'whoosh', who='saint', weapon='katana', strength=0.8)   # the rise to jodan = the score's overhead hit
EV.emit(1356, 'step', who='saint', strength=0.8)
EV.emit(1364, 'whoosh', who='saint', weapon='katana', strength=1.0)
# 1367 'perfect_deflect' comes from M.clash (else EV.emit(1367, 'perfect_deflect', pos=(0.06, 0.40, 1.78), tags=['perfect_deflect']))
EV.emit(1367, 'music_cue', cue='perfect_deflect')
EV.emit(1367, 'slowmo', duration=41)
```
**Notes.** DIRECTION §7: this IS the first two-handed blow. The camera must not move after 1362. Cut at 1369 (2 f after the contact); the slow motion (fx 0.2) starts on 1367 automatically (`config.TIME_WARP`).

### S13b — 1369–1408 (40 f) — slow motion: the ring and the hanging sparks
**Purpose.** Time stretches: the white ring opens around the crossed blades, sparks hang in the air, the master's blade is thrown back — his posture is broken. Framed on effects and silhouettes (DIRECTION §4).

**Camera — tight 3/4 from the +X side, 35 mm, slow push-in 0.37 m.**
```python
C.shot("S13b", 1369, 1408, keys=[(1369, (3.30, -0.50, 1.50), (-1.50, 0.83, 1.86), 35.0),
                                 (1408, (2.95, -0.38, 1.52), (-1.86, 0.92, 1.90), 35.0)],
       dof=dict(focus=(0.06, 0.40, 1.78), fstop=2.0), subjects=["shinobi", "saint"], framing="close")
ENV.set_camera_clearance(1369, 0.5, 1.0)
```
| frame | shinobi head | fig %H | elder head | fig %H | rule |
|---|---|---|---|---|---|
| 1369 | (−0.39, −0.47) | 112 | (+0.33, −0.36) | 111 | OK |
| 1408 | (−0.43, −0.53) | 127 | (+0.59, −0.23) | 131 | OK |

Contact at (0.00, +0.05) — dead centre; the ring (radius 0.6) reaches NDC y +0.85 at full size (inside the frame). Bottom ray: grass at 3.1 m (1.00). Sun off-frame left (−0.77, −0.24 … just inside at the left edge: a warm glow).

**Action (slow — ≈ 8.2 story frames of motion over 41 film frames; key at 1369, 1388, 1408 only).** Elder: the rebound — blade thrown up and back past vertical, arms high, torso tilting back into `elder_posture_broken` (§5), root 1.25 → 1.35. Shinobi: the deflect's follow-through carries his blade to his upper left; weight transfers to the front foot (the counter is loading), root −0.35 → −0.32.

**VFX.** The 1367 sparks and ring play out (fx time). Optional second slow shower: `VFX.sparks(1372, (0.06, 0.40, 1.78), count=30, speed=1.5, life=20, color='gold', scale=0.8, light=False, seed=zlib.crc32(b"S13b:0"))`.

**Environment.** `ENV.set_sun(1369, 264.0, 1.1)`; the grass and fluff slow down by themselves (fx_time).

**Events.** none (the audio's `slowmo` event covers the window; drums are out until the hat cut).

### S13c — 1409–1422 (14 f) — the counter: the hat cut in two (1420)
**Purpose.** Real time again: the student steps through with a rising cut; the tip passes a hand's width in front of the master's face and splits the straw hat — in silhouette, in front of the sun.

**Camera — backlit telephoto profile, 85 mm at 9.5 m.**
```python
C.shot("S13c", 1409, 1422, keys=[(1409, (9.50, 0.95, 1.55), (0.00, 0.95, 1.62), 85.0),
                                 (1422, (9.50, 1.00, 1.55), (0.00, 1.00, 1.62), 85.0)],
       dof=dict(focus=9.5, fstop=2.8), subjects=["shinobi", "saint"], framing="medium")
ENV.set_camera_clearance(1409, 1.5, 4.0); ENV.set_sun(1409, 273.4, 1.68)
```
| frame | shinobi head | fig %H | elder head | fig %H | rule |
|---|---|---|---|---|---|
| 1409 | (−0.58, −0.27) | 88 | (+0.26, −0.01) | 107 | OK |
| 1420 | (−0.37, −0.13) | 95 | (+0.29, +0.01) | 102 | OK |
| 1422 | (−0.38, −0.14) | 95 | (+0.30, −0.02) | 101 | OK |

The hat (0.0, 1.58, 1.83) at (+0.29, +0.25) and the **sun** (az 273.4, el 1.68 — a per-cut cheat; 0.56° above the ridge, 75 % of the disc visible) at (+0.28, +0.24): the hat sits on the disc. The blade crosses the front brim (0.0, 1.27, 1.78) at (+0.14, +0.19). Bottom ray: grass at 6.1 m (1.00).

**Action.**
| frames | shinobi | elder |
|---|---|---|
| 1409–1412 | steps in low (−0.32 → −0.25), blade low at his right hip (`sh_low_chamber_R`, §5) | posture broken, leaning back (head at y 1.58) |
| 1412–1420 | steps through (→ 0.15 at 1418, 0.18 at 1420); `M.slash(SH, 1414, 'rising_R')` as a steep kiriage (blade plane ≈ x 0, 80° elevation at the end): tip (0.0, 1.30, 1.95) at 1420, moving up ≈ 8 m/s | recoils further, chin up (1416–1420); the blade passes 0.12 m in front of his nose |
| 1420 | — | **`CH.set_hat(1420, 'cut')`**, `CH.snap_free('SAINT_hat_half_A', 1420)`, `CH.snap_free('SAINT_hat_half_B', 1420)`; tosses below |
| 1420–1422 | follow-through high | the bare, shaven, scarred head in silhouette against the sun |

**Hat halves (props.toss, deterministic).** The prop splits along the head's sagittal plane (local X = 0), which is edge-on to this profile camera, so the tosses carry ±Y/Z components to separate on screen: `props.toss('SAINT_hat_half_A', 1420, p0=<snap>, v0=(0.9, -1.6, 2.4), spin=(4.0, 1.0, 6.0), ground_z=0.0, settle=True)` (enters the grass tops 1438 at (0.68, 0.38)); `props.toss('SAINT_hat_half_B', 1420, p0=<snap>, v0=(-0.9, 1.4, 2.0), spin=(-3.0, 2.0, -5.0), ground_z=0.0, settle=True)` (1437 at (−0.64, 2.57)). On screen at 1422: A (+0.22, +0.47), B (+0.34, +0.42) — already two silhouettes.

**VFX.** `VFX.blade_trail('SHINOBI_katana_tip', 'SHINOBI_katana_base', 1414, 1421)` (white/red core); `VFX.grass_burst(1420, (0.0, 1.45, 1.85), direction=(0, 0.3, 1), count=40, speed=2.0, spread=60, fluff=0.0, scale=0.5, seed=zlib.crc32(b"S13c:0"))` (straw splinters; tune colour to `PALETTE['straw']` if the pool allows).

**Events.**
```python
EV.emit(1417, 'whoosh', who='shinobi', weapon='katana', strength=0.95)
EV.emit(1420, 'hat_cut', pos=(0.0, 1.58, 1.83), tags=['hat_cut'])
EV.emit(1420, 'music_cue', cue='hat_cut')
```
**Notes.** No clash (steel on straw). DIRECTION §7: "The hat split (S13) is a backlit profile" — no fill, face in silhouette; the scar reads in S13e, not here.

### S13d — 1423–1450 (28 f) — the master skids back through the grass
**Camera — wide, 24 mm, lateral pan following the skid (+X side).**
```python
C.shot("S13d", 1423, 1450, keys=[(1423, (9.00, 2.40, 1.70), (0.00, 2.60, 1.00), 24.0),
                                 (1450, (9.00, 2.80, 1.70), (0.00, 3.00, 1.00), 24.0)],
       dof=None, subjects=["shinobi", "saint"], framing="wide")
ENV.set_camera_clearance(1423, 0.5, 1.0); ENV.set_sun(1423, 262.0, 1.0)
```
| frame | shinobi head | fig %H | elder head | fig %H | rule |
|---|---|---|---|---|---|
| 1423 | (−0.35, +0.17) | 28 | (−0.12, +0.22) | 30 | OK |
| 1434 | (−0.42, +0.17) | 28 | (+0.13, +0.15) | 27 | OK |
| 1446 | (−0.57, +0.18) | 29 | (+0.46, +0.16) | 27 | OK |
| 1450 | (−0.58, +0.18) | 29 | (+0.47, +0.18) | 28 | OK |

Bottom ray: grass at 1.6 m (1.00). Hat halves: A (−0.18, +0.38) → (−0.39, −0.06) into the grass at 1438; B (−0.12, +0.36) → (−0.03, −0.05) at 1437 — two tumbling pieces falling left and centre while the master slides right. Sun (−0.22, +0.30), 40 % over the ridge.

**Action.** Elder: hop back 1422–1430 (root z 0.25 at 1430; 1.45 → 3.20), lands 1434 (3.70) into `M.skid(SA, 1434, 1446, (0.0, 3.70), (0.0, 6.20))` crouched (dz 0.30), blade low in both hands, a furrow opening behind him; settles 1446–1450 (6.25). Shinobi: recovers the follow-through, backs off in guard: 0.10 (1430) → −0.90 (1446), steps 1434, 1442. **VFX.** `VFX.dust_burst(1434, (0.0, 3.70, 0.0), radius=0.8)`; `VFX.grass_burst(1436, (0.0, 4.0, 0.3), direction=(0, 1, 0.4), count=70, speed=3.0)`; `VFX.grass_burst(1444, (0.0, 5.8, 0.3), direction=(0, 1, 0.3), count=40, speed=2.0)` (seeds `crc32("S13d:i")`). **Events.** `EV.emit(1423, 'jump', who='saint')`; `EV.emit(1434, 'land', who='saint', strength=0.7)`; `EV.emit(1434, 'skid', who='saint', duration=12)`; `EV.emit(1434, 'step', who='shinobi', strength=0.3)`; `EV.emit(1442, 'step', who='shinobi', strength=0.3)`.

### S13e — 1451–1488 (38 f) — the reveal: the shaven, scarred head (stillness beat)
**Camera — low MCU, 65 mm, tilting up as he straightens, then locked.**
```python
C.shot("S13e", 1451, 1488, keys=[(1451, (1.95, 4.95, 1.30), (-2.45, 7.29, 1.69), 65.0),
                                 (1470, (1.85, 5.00, 1.30), (-2.46, 7.43, 1.98), 65.0),
                                 (1488, (1.85, 5.00, 1.30), (-2.46, 7.43, 1.98), 65.0)],
       dof=dict(focus=(SA, "head"), fstop=2.0), subjects=["saint"], framing="mcu")
ENV.set_camera_clearance(1451, 1.5, 4.0); ENV.set_sun(1451, 262.0, 1.0)
```
| frame | shinobi | elder head | fig %H | rule |
|---|---|---|---|---|
| 1451 | off | (+0.28, +0.12) | 311 | faces L OK |
| 1470 | off | (+0.26, +0.30) | 372 | faces L OK |
| 1488 | off | (+0.26, +0.34) | 373 | faces L OK |

Head at the right third against the sky (from 1470 the frame bottom is his shoulders, no ground). The sun is off-frame left-front: a hard rim along the far edge of the scalp and the scar, the beard and cord lit from behind.

**Action.** Elder: rises out of the skid crouch (dz 0.22 → 0.04, 1451–1470), head lifts to level — looking at the student (off-screen left); blade low in both hands; 1470–1488 motionless except beard/cord/haori secondary motion. Shinobi (off-screen): two steps back to (0.00, −1.50) 1470–1488 (HANDOFF position; guard held). **Events.** `EV.emit(1455, 'step', who='saint', strength=0.3)`. No heartbeat event here: the score adds its own quickening heart from ≈ 1441 to the spear draw only when none is emitted (score.py `events_in` check).

### S14a — 1489–1524 (36 f) — the katana goes home (stillness beat)
**Purpose.** Bare-headed now, the master calmly sheathes his sword — he is not finished, he is changing weapons. Low angle, head against the sky, waist-up through foreground grass.

**Camera — low angle (z 0.98, inside the grass tops), 40 mm, 14-cm creep.**
```python
C.shot("S14a", 1489, 1524, keys=[(1489, (2.90, 4.70, 0.98), (-1.71, 6.50, 1.68), 40.0),
                                 (1524, (2.80, 4.80, 0.98), (-1.83, 6.53, 1.72), 40.0)],
       dof=dict(focus=(SA, "head"), fstop=2.8), subjects=["saint"], framing="medium")
ENV.set_camera_clearance(1489, 0.6, 1.0); ENV.set_sun(1489, 268.0, 0.9)
```
| frame | shinobi | elder head | fig %H | rule |
|---|---|---|---|---|
| 1489 | off | (+0.25, +0.40) | 150 | faces L OK |
| 1524 | off | (+0.25, +0.40) | 157 | faces L OK |

Pitch +8°: head in the upper right third against the sky; bottom ray: grass tops at 0.9 m (0.90) — a blurred band of blades across the lower frame (the waist-up framing). Sun at the left edge (−0.96, −0.64), glowing through the blades.

**Action.** 1489–1496 still, blade low in both hands. `CH.set_two_hand(SA, 1496, False, blend=3)` (left hand back to the saya); 1496–1500 edge up, blade across the body; 1500 kissaki at the koiguchi; 1500–1510 slides home (ctrl along the saya axis, `CH.sheathed_ctrl_matrix(SA, 1510)` at 1510); **1510** `set_weapon_state(SA, 1510, 'sheathed')`, `set_arm_mode(SA, 1510, 'fk')`; 1514–1524 the right hand rises to his left lapel, the left hand to the right lapel (`elder_haori_grip`, §5).

**Environment.** `ENV.set_wind(1489, 1.0)`, `ENV.set_wind(1516, 1.4)`, `ENV.set_wind(1540, 1.0)` (a gust that will carry the haori). Still `dusk_gold` (the default crimson blend starts 1537).

**Events.** `EV.emit(1510, 'sheathe', who='saint')`; `EV.emit(1520, 'wind_gust', strength=0.8)`.

### S14b — 1525–1552 (28 f) — the haori shed; the white tasuki
**Purpose.** One sweep: the ochre haori comes off the shoulders and is flung away behind him; under it, the white tasuki crossed over the persimmon kimono — the costume of a man going to war.

**Camera — low angle wider (z 1.02), 28 mm, locked (10-cm drift).**
```python
C.shot("S14b", 1525, 1552, keys=[(1525, (4.60, 4.20, 1.02), (-0.02, 6.06, 1.41), 28.0),
                                 (1552, (4.70, 4.30, 1.02), (0.03, 6.04, 1.41), 28.0)],
       dof=None, subjects=["saint"], framing="wide")
ENV.set_camera_clearance(1525, 0.6, 1.0); ENV.set_sun(1525, 268.0, 0.75)
```
| frame | shinobi | elder head | fig %H | rule |
|---|---|---|---|---|
| 1525 | off | (+0.05, +0.20) | 67 | faces L OK |
| 1552 | off | (+0.05, +0.20) | 66 | faces L OK |

Haori flight on screen: (+0.24, +0.19) 1534 → apex (+0.40, +0.35) 1538 → (+0.74, +0.04) 1546 → leaves the right edge ≈ 1551 (lands off-screen 1553). Bottom ray: blades at 0.9 m (0.84, intended). Sun (−0.69, −0.24) left of him, low.

**Action.** 1525–1530 grip tightens; 1530–1532 the sweep — shoulders roll back, both hands throw the haori open and back off the shoulders; **1532** `CH.set_costume(1532, haori=False)` with the SPEC rule-12 snapshot (the evaluated skinned haori at 1532 becomes `SAINT_haori_thrown`, no pop); 1532–1536 the right hand flings it up and to his left-back. Toss: `props.toss('SAINT_haori_thrown', 1532, p0=(0.30, 6.50, 1.45), v0=(1.67, 2.33, 2.80), spin=(0.5, 1.5, 3.0), ground_z=0.0, settle=True)` + shape keys spread 1532–1542 → crumple 1546–1556; lands at **(1.76, 8.54) at 1553** (r = 8.72 m from the arena centre — inside act2's default burn band 7.75–10.25 m, so it can catch fire in S15; act2 needs this position). 1536–1552 he stands square, arms lowering; tasuki visible.

**Environment.** The default crimson blend starts at 1537 (sky, fog, grass tints, key light 4.0 → 1.4 by 1632).

**Events.** `EV.emit(1532, 'haori_shed', pos=(0.30, 6.50, 1.45), tags=['haori_shed'])` (the SFX lands its grass-crunch 0.9 s later = 1553.6, on the landing frame).

**Notes.** The haori flies out of frame right: its landing is heard over S14c (a J-cut for free).

### S14c — 1553–1574 (22 f) — the student's reaction (D7)
**Purpose.** Eight metres away, the student understands: the master has only now begun. He resets his grip; the crimson sky is spreading behind him; the wind lifts his headband tails.

**Camera — MCU, 3/4 front from his right (+X side), 50 mm, 14-cm creep.**
```python
C.shot("S14c", 1553, 1574, keys=[(1553, (2.30, -2.85, 1.50), (-1.72, 0.12, 1.45), 50.0),
                                 (1574, (2.20, -2.75, 1.50), (-1.86, 0.17, 1.45), 50.0)],
       dof=dict(focus=(SH, "head"), fstop=2.0), subjects=["shinobi"], framing="mcu")
ENV.set_camera_clearance(1553, 0.5, 1.0); ENV.set_sun(1553, 268.0, 0.6)
```
| frame | shinobi head | fig %H | elder | rule |
|---|---|---|---|---|
| 1553 | (−0.26, +0.15) | 202 | off (+2.27) | faces R OK |
| 1574 | (−0.26, +0.15) | 213 | off (+2.40) | faces R OK |

Head at the left third with lead room to screen-right (toward the elder). Bottom ray: grass at 2.8 m (1.00). Sun off-frame left: a rim on the back of his head and the red headband.

**Action.** Shinobi at (0.00, −1.50), chudan: 1560–1570 `sh_regrip` (act1a §5: tip dips 5° and returns, shoulders drop 2 cm); settles on beat 60 (1570); hachimaki tails streaming harder (wind 1.2). Elder (off-screen): half step back 1560–1568 (6.25 → 6.50).

**Environment.** `ENV.set_wind(1553, 1.2)`. **Events.** `EV.emit(1562, 'wind_gust', strength=0.6)`; `EV.emit(1564, 'step', who='saint', strength=0.3)` (off-screen).

### S14d — 1575–1604 (30 f) — the spear drawn as the sun goes down
**Purpose.** The hero image of the act: in profile against the last of the sun, the master draws the vermilion spear from his back over his shoulder in one arc; the black sheath spins away against the red sky; the sun's last sliver vanishes behind the hills on the draw (1586).

**Camera — low-angle profile from 11 m (z 1.35), 50 mm, locked.**
```python
C.shot("S14d", 1575, 1604, keys=[(1575, (10.76, 4.01, 1.35), (5.80, 4.56, 1.60), 50.0),
                                 (1604, (10.76, 4.01, 1.35), (5.80, 4.56, 1.60), 50.0)],
       dof=dict(focus=10.9, fstop=4.0), subjects=["saint"], framing="medium")
ENV.set_camera_clearance(1575, 0.5, 1.0)
```
| frame | shinobi | elder head | fig %H | rule |
|---|---|---|---|---|
| 1575 | off | (+0.32, −0.12) | 55 | faces L OK |
| 1584 | off | (+0.32, −0.12) | 54 | faces L OK |
| 1586 | off | (+0.32, −0.12) | 54 | faces L OK |
| 1604 | off | (+0.32, −0.13) | 54 | faces L OK |

**Sun** (az 276) at (−0.02, −0.26), 0.34 NDC in front of him (on the side he faces, toward the student): the disc (2.2° = 0.25 NDC ≈ 103 px wide) shows a cap above the ridge (1.14°) that shrinks 0.51° (1575) → 0.24° (1580) → 0.02° (1584) → gone (1586). Spear tip: (+0.38, +0.27) 1580 → (+0.30, +0.66) 1584 (overhead) → (+0.09, +0.23) 1588. Sheath: release (+0.12, +0.31) 1588 → (−0.01, +0.43) 1592 (crossing above the sun) → (−0.27, +0.18) 1600 → (−0.41, −0.18) 1604 → into the grass 1608 (−0.77, 3.08). Bottom ray: grass at 2.9 m (1.00).

**Action (elder at (0.00, 6.50), facing 0).**
| frames | action |
|---|---|
| 1575–1580 | `elder_spear_reach` (§5): the right hand goes up over the right shoulder to the shaft (1.40 m from the butt); the left hand finds the butt behind the left hip and pushes it up |
| **1580** | `CH.set_arm_mode(SA, 1580, 'ik')`; `CH.set_spear_grip(1580, grip_R=1.40)`; ctrl = `CH.slung_spear_ctrl_matrix(1580, grip_R=1.40)`; **`CH.set_weapon_state(SA, 1580, 'in_hand')`** — the free `SAINT_spear_sheath_world` appears: `_local_follow_socket` (§5) keys it to the blade every frame 1580–1588 |
| 1580–1584 | pulls the spear up along its axis and over his head: tip (−0.25, 6.45, 3.05) at 1584, the hand ≈ 2.15 m |
| 1584–1588 | the arc forward over the right shoulder (tip sweeps forward and down, butt goes up-back); 45° at 1586; tip (−0.30, 5.60, 2.30) at 1588 — the snap |
| **1588** | sheath released: `props.toss('SAINT_spear_sheath_world', 1588, p0=(-0.35, 5.75, 2.45), v0=(-0.5, -3.2, 2.0), spin=<5 rev/s end-over-end about its local X>, ground_z=0.0, settle=True)` |
| 1588–1596 | brings the spear down level in front; `CH.set_two_hand(SA, 1594, True, weapon='spear')`; grips slide 1590–1600: `set_spear_grip(1590, grip_R=1.40, grip_L=1.15)` → `set_spear_grip(1600, grip_R=0.55)` |
| 1598–1604 | `M.spear_spin(SA, 1598, 1620)` begins (continues in S14e) |

**Environment (the sunset — D5).**
```python
ENV.set_sun(1575, 276.0, 0.55, interp='LINEAR')
ENV.set_sun(1586, 276.0, -0.05, interp='LINEAR')     # last sliver 1584, gone 1586
ENV.set_sun(1597, 276.0, -0.60, interp='CONSTANT')
ENV.set_param(1586, 'disk_vis', 1.0, 'LINEAR'); ENV.set_param(1590, 'disk_vis', 0.0, 'CONSTANT')
```
**VFX.** `VFX.blade_trail('SAINT_spear_tip', 'SAINT_spear_base', 1584, 1590)` (gold; `min_speed` default keeps the slow pull clean); `VFX.embers(1590, 1640, center=(0.0, 6.0, 0.0), radius=7.0, rate=5.0, height=(0.3, 2.2), rise=0.6, seed=zlib.crc32(b"S14d:emb"))` — the first embers, sparse (≈ 12 alive), drifting across the red sky.

**Events.**
```python
EV.emit(1586, 'spear_draw', pos=(-0.25, 6.45, 2.90), tags=['spear_draw'])   # beat 61 (D4)
EV.emit(1592, 'sheath_drop', pos=(-0.43, 5.22, 2.65), tags=['sheath_drop']) # whirr now, thud +0.66 s = 1608 (lands)
```
**Notes.** The deny-list: the spear comes off his BACK, never out of the ground; the sheath is a physical prop.

### S14e — 1605–1632 (28 f) — the twirl; raised for the slam (→ HANDOFF[1632])
**Purpose.** The spear comes alive in his hands — a twirl, then he raises it vertically and drives the butt down: the cut to S15 lands on the impact (1633).

**Camera — low wide (z 0.95, inside the grass tops), 24 mm, locked.**
```python
C.shot("S14e", 1605, 1632, keys=[(1605, (4.00, 3.90, 0.95), (-0.49, 6.00, 1.64), 24.0),
                                 (1632, (4.00, 3.90, 0.95), (-0.49, 6.00, 1.64), 24.0)],
       dof=None, subjects=["saint"], framing="wide")
ENV.set_camera_clearance(1605, 0.6, 1.2); ENV.set_sun(1605, 276.0, -0.60)
```
| frame | shinobi | elder head | fig %H | rule |
|---|---|---|---|---|
| 1605 | off | (+0.18, +0.05) | 61 | faces L OK |
| 1632 | off | (+0.18, +0.04) | 61 | faces L OK |

The twirl disc (radius 1.15 m about the hands) spans NDC y −0.97 … +0.58 and x ±0.32 around him — inside the frame (its bottom arc disappears into the foreground grass). At 1628 the raised spear's tip (3.35 m) leaves the top edge (+1.10) — intended; the butt at 1632 is at (+0.16, −0.79). Bottom ray: blades at 1.0 m (0.78, intended low angle).

**Action.** 1605–1620 `M.spear_spin(SA, 1598, 1620)`: a two-handed figure-eight, 1.5 turns, ending tip-up; 1620–1626 he brings the spear vertical in front of his right shoulder, hands high (right fist 1.9 m, left 1.5 m), butt 0.9 m above the ground; 1622 plants the front foot; 1626–1632 the downward drive: butt 0.9 → **0.45 m at 1632**, fast. Shinobi (off-screen): (0.00, −1.50), chudan.

**Environment.** `ENV.set_wind(1605, 1.2)`; the crimson blend completes at 1632 (default); embers continue.

**Events.**
```python
EV.emit(1598, 'spear_spin', who='saint', duration=22)
EV.emit(1622, 'step', who='saint', strength=0.6)
EV.emit(1628, 'whoosh', who='saint', weapon='spear', strength=0.8)
```
**Notes.** HANDOFF[1632] (D3): elder (0.00, 6.50) facing 0, spear in hand vertical and descending, katana sheathed, hat off, haori off (at (1.76, 8.54)), tasuki on; shinobi (0.00, −1.50) facing 180, drawn. Key both roots CONSTANT at 1632; no key after 1632 (act2 owns the impact frame).

## 4. Flash schedule + budget proof

Act I is classical: **two** full-frame lifts in the whole lane, no `environment.flash` (lightning) anywhere in 937–1632.

| frame | source / call | strength (share of full-frame white) | duration | why |
|---|---|---|---|---|
| 1131 | `RS.key_white_flash(1132, 0.20)` keys 0 here | 0 | — | clean pre-key (CONSTANT) |
| **1132** | `RS.key_white_flash(1132, 0.20, duration=1)` | **0.20** | 1 f | the overhead block (clash burst) |
| 1133 | (auto 0) | 0 | — | off |
| 1366 | `RS.key_white_flash(1367, 0.35, duration=2)` keys 0 here | 0 | — | clean pre-key |
| **1367–1368** | `RS.key_white_flash(1367, 0.35, duration=2)` | **0.35** | 2 f | the perfect deflect — DIRECTION §5 "≤ 40 % for 2 f" |
| 1369 | (auto 0) = the cut to S13b | 0 | — | off |
| 1132, 1367 | `RS.key_dispersion(…, 0.04 / 0.05)` → 0 after 6 f | 0 (colour fringe only) | 6 f | impact accent, no luminance |
| 1367 | `VFX.flash_ring` light (150 W, ≈ 2 f, cutoff 10 m) | local, est. < 0.05 | 2 f (fx) | not a full-frame flash |
| 1132, 1195, 1210, 1226, 1241, 1257, 1273, 1367 | spark point lights from `M.clash` (`light=True`, 2–4 f, cutoff 8 m) | local, est. < 0.05 each | 2–4 f | not flashes (area ≪ 25 %) |
| 1288, 1304, 1258, 1372 | grind / scrape / slow sparks | `light=False` | — | no light at all |

Proof against DIRECTION §5 / config:
1. **Spacing ≥ 12 f (FLASH_MIN_GAP):** the two lifts are 235 f apart; the nearest lifts outside the lane are act1a's 595 (537 f earlier) and act2's S15 fire eruption from 1633 (265 f later, itself a ≥ 6 f ramp). Spark lights are ≥ 15 f apart (1195 → 1210 → 1226 → 1241 → 1257 → 1273).
2. **≤ 70 % outside FULL_WHITE:** peak mixes 0.20 / 0.35 (render_setup clamps anything > 0.40 outside FULL_WHITE); on a 40 %-mean frame the 0.35 mix gives ≈ 0.65 · 0.40 + 0.35 ≈ 61 % mean luminance ≤ 70 %. S13's lift is exactly the "≤ 40 % for 2 f" DIRECTION asks for.
3. **≤ 2 per second:** at most one lift in any 24-f window; spark lights at most 2 per 24 f (e.g. 1195 + 1210).
4. **flash_qc (> 3 opposing ≥ 10 % flips per 24 f = FAIL):** worst windows — 1120–1143: 1132 up, 1133 down, cut 1135 (S11d low-angle sky → S11e high-angle sunlit stubble; keep S11e's first frames within ±10 % of S11d) ⇒ ≤ 3 ✓. 1355–1378: 1367 up, 1369 down (= the cut) ⇒ 2 ✓. S12 flurry 1190–1280: two cuts per 24 f (every 15–16 f) + local spark lights (< 10 %) ⇒ ≤ 2 flips if the six OTS angles stay within ±10 % mean luminance — that is why every S12 cut keeps the sun cheat at az 268 el 1.1 and the same side-light; verify with `.venv/bin/python src/tools/flash_qc.py out/previews --start 937 --end 1632 --strict`.
5. **FULL_WHITE (3265–3268):** not touched. **S15 red-flash rule:** not in this lane (the embers are dim specks).

## 5. Local poses / moves not in the SPEC macro list

Implement in `acts/act1b.py` as `_local_*` helpers or as poses passed to `poses.key_pose` if the pose library lacks them. Degrees = bone-local Euler XYZ, +X = flexion (Pipeline rule 10). Re-used from act1a §5: `elder_low_guard_1h`, `elder_offhand_saya`, `elder_iai_crouch`, `elder_chamber_high_1h`, `sh_regrip`.

| name | used | definition / intent |
|---|---|---|
| `sh_grass_crouch` | 976–1040 (S10a–S10c) | the hiding crouch-run: hips_offset z −0.55 (hips at ≈ 0.45 m), thighs flexed 110°, knees 130°, spine 35°, chest 20°, neck −20° (eyes forward), **head top ≤ 0.83 m**; sword two-handed held vertical along the right side, tip ≤ 0.92 m; run cycle: a step every 6 f, 0.03 m bob, root follows the §1 arc |
| `sh_grass_crouch_coiled` | 1040–1102 (S11a–S11c) | as above, weight on the balls of the feet, hips −0.04 more at 1090–1096 (loading), elbows tucked |
| `sh_air_tuck` → `sh_air_jodan` | 1104–1118 → 1118–1126 | leap: knees to chest, sword two-handed along the body, tip back; at the apex unfold: legs extend, sword to jodan above the head |
| plunge strike | 1126–1134 | `M.slash(SH, 1126, 'overhead')` while airborne (or `M.plunge`), fists (0.04, 1.62, 2.15) and blade (0.0, 0.97, −0.14) at 1132; landing crouch 1134 (hips −0.45) |
| `elder_listen` | 984–1098 | `elder_low_guard_1h` + head lowered 12° (neck 6°, head 6°), blade tip down into the grass tops (−35° elevation), shoulders −1 cm; listening turns = head yaw only: −6° (1004–1012), −14° (1018–1026) to his right |
| iai with a pivot | 1099–1103 | `M.iai_slash(SA, 1099, ...)` if it takes a pivot; else local: root rotation z 28.9 → 3.45 over 1099–1102 (ease-out), blade out of the saya by 1100, one horizontal sweep from the left hip across the front to his right at 0.95–1.05 m, one-handed; follow-through extended to his right 1103–1110 |
| overhead block, one-handed | 1126–1140 | right fist (−0.22, 2.35, 1.98), blade dir (0.95, −0.15, 0.27), edge up; left hand stays on the saya; knees dip 5 cm at 1132 |
| `_local_heave` | 1140–1144 | the elder's one-armed heave: right fist travels 0.25 m up-forward in 4 f, chest rises 3 cm; drives the shinobi's `M.jump(SH, 1140, 1152, (0.02, 1.35), (0.0, 0.30), apex=0.55)` (backward lean 15°) |
| `sh_low_chamber_L` / `_R` | 1213–1219 / 1409–1412 | blade drawn low to the left (right) hip, tip back-down, knees bent (hips −0.10), chest turned 20° toward the chamber side |
| `sh_thrust_chamber` | 1244–1250 | both fists at the right hip, blade level at the elder's chest, rear foot loaded (hips −0.05, +0.05 back) |
| `elder_posture_broken` | 1367–1420 | the rebound: upper arms flexed 150° (blade thrown up and back past vertical), spine −8°, chest −6°, neck −10° (chin up), weight on the heels; root +0.10 m in y over the slow motion |
| steep rising cut (kiriage) | 1414–1421 | `M.slash(SH, 1414, 'rising_R')` driven to a near-vertical plane (x ≈ 0, 80° elevation at the end); tip (0.0, 1.30, 1.95) at 1420 |
| `elder_haori_grip` | 1514–1532 | right hand at the left lapel (upper_arm.R flex 60°, adduct 40°; forearm.R 110°), left hand at the right lapel (mirror) |
| haori shed | 1530–1536 | shoulders roll back (chest −8°, both upper arms extend back 30°) 1530–1532; right arm flings up-back (upper_arm.R abduct 80°, extend 40°) 1532–1536 |
| `elder_spear_reach` | 1575–1580 | right arm up over the right shoulder (upper_arm.R flex 165°, abduct 20°; forearm.R 120°), hand behind the right ear on the shaft; left arm behind the back (upper_arm.L extend −40°, forearm.L 90°), hand at the butt; chest turned 10° right |
| `_local_follow_socket(free, parent_obj, f0, f1)` | sheath 1580–1588 | keys `SAINT_spear_sheath_world`'s world matrix every frame to `SAINT_spear_hand`'s world matrix @ the slung sheath's local offset (the offset `SAINT_spear_sheath_world['attach_offset']` already describes) — no pop at 1580; the toss at 1588 continues from the last keyed matrix |
| spear twirl | 1598–1620 | `M.spear_spin(SA, 1598, 1620)`; fallback: key the sword ctrl rotating 540° about the axis through the fists (frontal plane), ease in/out, grips alternating (grip_R 0.55 ↔ 1.15) |
| `elder_slam_raise` | 1620–1632 | spear vertical in front of the right shoulder, right fist 1.9 m, left 1.5 m, butt 0.9 m; 1626–1632 the drive down (both arms extend, hips −0.12): butt 0.45 m at 1632 |
| `_local_part_angle(frame, v)` (optional, see Q2) | 988 (0.6) → 1101 (1.0) | `U.gn_key(bpy.data.objects['ENV_grass'], 'Part Angle', frame, v)` — softer parting so the ripple is a wave, not a hole; use only if the env lane agrees |
| `_local_toss` (if `props` is not yet available) | hat halves, haori, sheath | ballistic keys p(t) = p0 + v0·t − ½·g·t² (+ spin about the given axes), first ground/grass contact → 2 damped bounces (e = 0.25) → settle; one key per frame, CONSTANT after settling |

## 6. Title overlays in the span

**None.** `config.TITLES` has nothing between `act1` (445–528) and `act2` (1665–1726); the whole of 937–1632 is title free, so no cut reserves space for a card. Two notes for neighbours:
- The act2 card (1665–1726) plays over S15 (act2's lane); our last frame (1632) is a low wide with the sky in the upper half — nothing of ours constrains it.
- Keep the upper-right third of S14d/S14e free of bright VFX anyway (embers are sparse there) — it is the same region the act cards use, and the audience's eye is trained there after the act-I card.

## 7. Risks + fallbacks

| # | risk | detection | fallback |
|---|---|---|---|
| 1 | The ripple reads as a hole that shows the shinobi's back (S10b/S11b) | preview 1000, 1080 | keep those cameras ≤ 1.8 m and grazing (they are); `_local_part_angle` 0.6 (Q2); lower the crouch (head top 0.75) |
| 2 | The shear line is not legible from the S11c high wide (1.05 → 0.65 m tops is subtle from 11 m) | preview 1104–1114 | the fluff pool carries it (raise `fluff` to 5000); drop the camera to z 3.5 at 8 m (pitch −18°) so the tops are seen more edge-on; darker stubble variant is an env ask |
| 3 | The line reaches H after his feet pass 0.7 m only if the jump is fast enough | geom: feet 0.95 m at 1106 | if the leap is slowed (apex < 2 m), slow the line instead: `f1 = 1120` (reaches H at 1106.6) — never let the stubble height cross his crouched body |
| 4 | The arc includes the S11c camera's bearing (east): fluff born right under the lens 1112–1115 | preview 1110–1118 | if messy: `arc_deg=180, facing_deg=196.5` (bearings 106.5–286.5, the camera side excluded) |
| 5 | Leap feels floaty (29 f of air) | preview S11c/S11d | take-off 1104, apex 1.9 m (v0 5.9 m/s), same contact 1132; or cut S11c at 1114 and start S11d at 1115 |
| 6 | 1132 contact gate fails (contact near his tip, 0.65 along the blade) | end_lane clash report | move his 1130–1132 root 0.10 m closer (y 1.13 → 1.30), landing unchanged |
| 7 | The one-handed overhead block reads weak | review | knee dip 8 cm + `dust_burst` + a heavier impact shake — NEVER add the left hand before 1346 (DIRECTION §7) |
| 8 | S12g: the far hills cover the lower disc and the heads fall below the sky line | preview 1298 | raise the sun to el 1.9 and the camera to z 1.25 (re-run geom.py; keep the lock inside the disc) |
| 9 | S12 flurry fails flash_qc (6 cuts in 80 f) | `flash_qc.py --strict` | equalise OTS exposure (same sun cheat, ±10 % mean); halve the spark `light_energy`; last resort: merge S12c+S12d into one 31-f cut (1213–1243) from the S12d insert angle |
| 10 | Slow-motion bodies look like stutter (S13b) | preview 1369–1408 | key bodies only at 1369/1388/1408 (BEZIER); tighten to 50 mm (effects fill the frame) |
| 11 | Hat halves overlap on screen (split plane edge-on to the profile camera) | preview 1420–1424 | the tosses already separate in ±Y/Z; add a 20° recoil head-turn to his right at 1418–1420 so the split opens toward the camera |
| 12 | Haori toss looks rigid | preview 1532–1552 | shape keys spread→crumple; if still stiff, cut S14b at 1537 and let the landing play off-screen (the SFX sells it) |
| 13 | Sun timing: the real ridge differs from the geom.py replica | preview 1580–1588 | read the disc cap on the preview; shift the 1586 key by ±0.1° (every 0.1° ≈ 2 f) |
| 14 | `disk_vis` override fights the default crimson blend | curve check at 1560/1586/1590 | the keys at 1586 (1.0) and 1590 (0.0) must sit between the blend keys 1537/1632; if the env API rejects it, set `disk_deg` 2.2 → 0 at 1590 instead |
| 15 | Spear arc intersects the head or the sheath pops at 1580 | layout render 1580–1590 | tune grip_R 1.30–1.50; the follow helper must copy the slung sheath's exact offset |
| 16 | HANDOFF[1632] pose disagrees with act2's S15 opening | build QA / act2 review | Q1: agree the slam pose; worst case end with the spear raised and still (butt 0.9 m) and let act2 animate the whole drive in its first frames |
| 17 | `moves` macros lack the kinds/params used (strafe angle convention, iai pivot, plunge, spear_spin figure-eight, jump apex) | import/call errors | the §5 definitions are complete enough to key locally (`_local_*`) |
| 18 | The 4.8 m skid (1422–1446) looks like ice | preview S13d | split it: hop 1.75 m + skid 2.5 m + two dragging steps 0.5 m; dust + grass bursts at every foot contact |
| 19 | Secondary motion pops at the 26 intra-lane cuts | preview | springs reset per sub-cut marker with a 24-f pre-roll (Pipeline rule 11); hold poses still across cuts except the listed cheats (1320/1321) |

Simplification order if time runs short: drop S11b's rack focus → S11e as a static high wide → drop S14c (S14b to 1560, S14d from 1561 with the same end) → S13d without the hop → S12f from the S12a angle. **Never drop:** the draw-cut + shear (1101), the overhead block (1132), the six flurry clashes on the grid, the lock 1276–1320 against the sun, the first two-handed grip (1346), the perfect deflect + slow motion (1367–1408), the hat cut (1420), the haori shed (1532), the spear draw on the sunset (1586), HANDOFF[1632].

## 8. Implementation order for `acts/act1b.py` (suggested)

1. Re-assert HANDOFF[936] at 937 (roots, facings, weapon/costume/hat states — §1 tables); the env defaults come from `ENV.key_lane_defaults('act1b')` (build_scene) — override per cut only.
2. Key both root tracks from §1 (geom.py `SH_TRACK` / `EL_TRACK` hold the same numbers; facings continuous; CONSTANT at 1320 for the 1321 cheat; CONSTANT at 1632).
3. Poses/moves per block (§3, §5), then sword ctrls + `M.clash` at 1132, 1195, 1210, 1226, 1241, 1257, 1273, 1367 and `M.blade_lock` 1276–1320 (contact points in the blocks); weapon swaps at 1054, 1099, 1510, 1580; two-hand switches at 1346, 1496, 1594; hat 1420; costume 1532.
4. Props: hat halves (1420), haori (1532), sheath (follow 1580–1588, toss 1588) — `props.toss` or `_local_toss`.
5. Cameras (26 `C.shot` calls, keys verbatim), clearance/sun/wind keys per cut, the grass shear (1101), flashes (§4), VFX, events (incl. `music_cue` perfect_deflect 1367 and hat_cut 1420, tags `perfect_deflect`, `hat_cut`, `haori_shed`, `spear_draw`, `sheath_drop`).
6. `bl_util.freeze_handles` on everything keyed; build the lane alone (`Blender -b --factory-startup --python src/blender/build_scene.py -- --lanes act1b --quality layout`), then run `cameras.check_screen_direction` / `framing_qa`, the clash report, `flash_qc`, and compare with `out/dev/breakdown/act1b/geom_report.txt` (`.venv/bin/python out/dev/breakdown/act1b/geom.py`).

### Open questions (for the orchestrator / neighbouring lanes)
- **Q1 (act2):** S15 must open on the butt impact at 1633 from this lane's 1632 pose (elder (0, 6.5), spear vertical in both hands, butt 0.45 m and falling). Props left lying for act2: haori at (1.76, 8.54) (r 8.72 — in the default burn band, so it can catch fire), spear sheath ≈ (−0.8, 3.1), hat halves ≈ (0.68, 0.38) and (−0.64, 2.57).
- **Q2 (env):** may a lane key the grass GN input `Part Angle` (optional softer parting in 988–1101)? If not, an `environment.set_parting(frame, angle)` setter would do; the lane works without it.
- **Q3 (moves):** `strafe` angle convention (this doc: degrees CCW from +X about `center`); `iai_slash` pivot parameter; `plunge` signature; `spear_spin` figure-eight option; `jump(..., apex)` = root apex height?
- **Q4 (props):** SPEC rule 12 names `props.toss(...)` but no `props.py` exists yet — which module will own it?
- **Q5 (env):** the S11 stubble persists through Act I (`until=None`); act2's burn ring (r 9 ± 1.25 around the origin) lies inside the sheared crescent — fine visually (burning stubble), just confirm the shear slot is not reused.

## Implementation notes

(implementer, `src/blender/acts/act1b.py`; deviations from the breakdown above and why — everything not listed here follows the breakdown's frames, cameras, tracks and events)

- **Sunset / sun heights (D5, S12g, S14d).** `environment` opens a *sun-following gap* in the far ranges: `environment.ridge_elevation(az)` toward the sun is ≈ 0.05° (not the 1.0–1.2° ridge the geometry proofs assumed). So the S14d disc is gone only when its centre is ≈ 1.1° below that skyline: sun keys 1575 el −0.15 → 1585/1586 el −1.08 (LINEAR, `SUNSET` in the file; the default 1585 key is overwritten) → 1597 −1.63, `disk_vis` 1 → 0 at 1586 → 1590. S14e uses el −1.60. S12g: the camera is raised to z 1.40 (the field grass between an 18 m telephoto and the pair hid everything below the chest at z 1.12) and the sun lowered to el 0.78 so the disc still sits behind the lock (NDC ≈ 0) — the gap keeps the disc clear.
- **Contact heights.** The library strike poses meet their target low (kesa / shomen impact at waist height); with them the S13 perfect deflect put the elder's tip at the student's chest. Local strike-at-contact poses `a1b_overhead_contact` (fists forward at forehead height, blade 22° up — S12 1273 one-handed, S13 1367 two-handed) and `a1b_kesa_high` (one-handed kesa met high, S12d 1241) make the blades meet at 1.50–1.66 m on the +X (camera) side; the strikes are keyed by `_local_strike` (moves.slash timing, no follow-through where a lock / rebound takes over).
- **No tsuba_click on the elder's sheathes (1054, 1510).** `moves.sheathe` always emits one; `_local_sheathe` (same poses) emits only `sheathe` — the click motif stays S06 / S24b / S26.
- **Thrown haori.** `moves.shed_haori` → `props.fly_haori` starts the toss from `SAINT_haori_thrown.matrix_world`, which is stale unless the scene is on the shed frame (measured: a 2.0 m jump toward the camera on 1533). `_local_retoss_haori` re-tosses from `characters.detach_matrix` (+ spread / crumple re-keyed); it lands at ≈ (1.4, 8.1).
- **Spear sheath.** `moves.spear_draw` leaves the sheath where the slung spear was while the spear is pulled up through it (the blade pierced its own sheath for 3 f). `_local_sheath_follow` keys the sheath on the blade from the grab (1581) to the release on the draw (1586), then tosses it forward-up across the sun (v0 (−0.5, −3.0, 3.2), 5 rev/s); `sheath_drop` is re-emitted at 1592 (tag), its landing frame in the event's `land`.
- **Plunge hitch.** `moves.plunge` inherits `jump`'s T1(−1) air-pose key (1133) one frame after the strike (1132): the trunk snapped back toward the windup between strike and landing. The body key at 1133 is deleted.
- **Hidden crouch.** `a1b_grass_crouch` / `a1b_grass_coiled` fold the trunk to 60–66° so the head top stays at 0.83 m (probe) — under the 0.95–1.15 m arena tops.
- **Hat clearance.** `set_hat_tilt` keys (front brim up 12–20°) through the overhead block, the S12d kesa, the lock and the jodan rise keep the brim off the raised forearms / blade (probe: ≥ −1.6 cm, was −4.4 cm).
- **Camera changes (seen on the previews).** S11b: z 0.95 → 1.10, clearance (0.45, 0.95) and the look raised — at 0.95 m the plumes at the lens covered the master completely. S11c: the 5.2 m top-down was a murky brown carpet (everything backlit); now z 3.4 at 8.6 m tilting up with the rise (look z 0.9 → 2.1), so the stubble crescent is seen edge-on and the leap ends against the sky. **S11e:** the high crane (7.8 → 2.2 m) showed the pair as two specks in a dark hollow — the stubble/uncut contrast does not read from above in backlight. Now a low 3/4 two-shot standing IN the stubble, (6.8, 0.2, 2.3) → (6.0, 1.0, 1.6), 26 → 30 mm, sun cheat az 271 so the disc sits between them: the heave, the hop back and the slide read, the pair is visible from the thighs up (the sheared field IS the payoff) and the fluff drifts through the frame. S12e: look lowered 0.21 m (the 1257 contact sat on the bottom edge); its spark light 12 W (the default lit a white blob 2.4 m from the lens). S12h: 28 → 35 mm, z 1.35 (heads against the sky). **S13d:** 24 → 32 mm, z 1.45 looking level, pan 1.8 → 3.0 (figures were 10 % of the frame height). S14b: z 1.02 → 1.28, 34 mm, clearance (1.2, 2.2) — at 1.02 m the foreground blades hid the tasuki. S14c: the listed camera sat BEHIND the student (a 3/4 back view); now a 3/4 front MCU from the +X side (1.62, −0.42, 1.52) → (−0.28, −1.62, 1.50), he still faces screen-right. **S14d:** 50 → 60 mm, look z 1.64 (the sun must stay on the bottom third, so the gain is limited: the figure is larger, the disc too). **S14e:** the z 0.95 camera inside the grass hid everything below his collar; now z 1.30, 32 mm, (4.2, 3.6) → (−0.4, 6.3, 1.95): the elder waist-up against the crimson sky, the twirl and the raised spear read (the tip leaves the top edge at 1628, as planned).
- **Reveal lighting (per-cut sun cheats).** S13e (the shaven, scarred head) was a black silhouette — no scar, no beard: sun az 232 el 7 (a high 3/4 back-side key from screen-left, out of frame) models the scalp, the scar and the beard. S14b (haori → white tasuki): sun az 200 el 3 (side-front key, out of frame) so the ochre coat and the white cross cord read. Both cuts are the act's two costume reveals; every other cut stays backlit.
- **Haori flight.** The thrown coat read as a rigid board (fully 'spread' = a flat sheet) flying toward the lens. Now thrown behind him (v0 (−0.5, 2.4, 2.6), spin (0.8, 2.0, 0.5) rad/s), 'spread' only to 0.5 with a 'crumple' flutter (0.18–0.45 every 3 f) in the air; lands ≈ (−0.4, 8.3) — act2 re-drapes it at its own S15 spot (act2 D2).
- **Spear reach (S14d).** `moves.spear_draw` switches the left hand saya → free with a CONSTANT key at 1580 (0.45 m jump in 1 f) and blends the right arm to the slung grip in 3 f along a line through the chest. `_local_smooth_spear_reach`: the left hand fades off the saya 1576–1580; the right arm goes IK from 1575 with the controller keyed along hip → out beside the shoulder (1577) → above the right shoulder (1578) → the shaft (1580).
- **Sheathe hand.** `_local_sheathe` blends the left hand onto the saya over 4 f (was 2: a 0.29 m/f jump at 1503).
- **Framing labels.** The waist-up cuts S11a, S11d, S12f, S12g, S13c, S14a are labelled `close` (framing_qa accepts > 30 % clipping only for close kinds); the breakdown's %H tables already show them waist-up.
- **Dust.** `vfx.dust_burst` volumes read as dark smudges in the backlit dusk (the 1133 burst covered the pair for the whole S11e crane): every dust call in the lane is radius ≤ 0.6, density 2, life 30; grass bursts carry the impacts.
