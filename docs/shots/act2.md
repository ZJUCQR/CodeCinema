# Lane act2 — S15–S20 (frames 1633–2496) — shot breakdown

Status: COMPLETE (all sections filled; history in out/dev/breakdown/PROGRESS_act2.md). Owner file for the implementer: `src/blender/acts/act2.py`. Numbers here are binding unless marked "(tune)". `config.py` wins if it disagrees with a number copied here (import it; never re-type TEMPO_MAP / HANDOFF / TITLES). Geometry proofs: `out/dev/breakdown/act2/geom.py` → `geom_report.txt` (pinhole identical to `bl_util.new_camera`: sensor_fit HORIZONTAL, 36 mm wide, 2.35:1). Re-run it after any change to a track or camera.

Conventions used below
- Positions = rig origin on the ground (x, y); facing 180 = +Y (shinobi), 0 = −Y (elder). Heights z in metres.
- Screen positions are NDC: x −1 (left) … +1 (right), y −1 (bottom) … +1 (top). "H%" = size as % of frame height.
- Camera azimuth φ about the fighters' midpoint: φ = 0 is the +X profile, φ = −90 behind the shinobi, φ = +90 behind the elder. |φ| < 90 = the legal +X side.
- Sun: `az` = compass bearing from +Y clockwise toward +X, `el` = elevation (environment.set_sun convention).

## 1. Lane summary

| | |
|---|---|
| Shots | S15, S16, S17, S18, S19, S20 — frames **1633–2496** (864 f = 36.0 s), **23 sub-cuts**, all hard cuts |
| Act / env | Act II "Act Two · Fire": `crimson_fire` (already full at 1633 from the default timeline) → default blend to `storm_night` 2353→2401 (thunder_first → rain_start); downpour + ring extinguished at 2401 |
| Music grid | 120 BPM, 12 f per beat from 1633 (`config.beat_frame('act2', b)`), 18 bars; every shot boundary is a bar line |
| Enters (HANDOFF[1632]) | shinobi (0.0, −1.5) facing 180, katana **drawn** (two-handed chudan); elder (0.0, 6.5) facing 0, katana **sheathed**, hat **off** (cut in S13), haori **off** (thrown), white tasuki **on**, spear **in_hand** |
| Leaves (HANDOFF[2496]) | shinobi (0.0, −3.0) facing 180, katana **drawn**, two-handed chudan; elder (0.0, 3.0) facing 0, katana **drawn**, pose **jodan** (two-handed, blade high), tasuki on, spear **gone** |
| Track error at the boundaries | 0.00 m at 1633 and at 2496 (`geom.py` prints it) |
| Contacts | **14 weapon contacts**: 13 clashes (1789, 1801, 1813 kunai + slide, 1837, 1945, 1951, 1957 kunai, 2089, 2101, 2113, 2125, 2137, 2281) + the bind opening at 2149 (grinding to 2158); 3 misses (1753 sweep, 1885 low sweep, 2077 thrust); 2 ground impacts (1633 butt, 2017 slam); 1 body contact hidden by a cut (kick 2173) |
| Slow motion | only 2280–2304 (`config.SLOWMO[2]`, fx speed 0.4 — `config.TIME_WARP`) |
| Full-frame flashes | 2 in-cloud lightning lifts, both after the ring's shadowed lights are gone (≥ 2422, Pipeline rule 5): 2425 (0.45), 2443 (0.30) — §4. The first thunder (2353) is heard, not seen. Fire eruption 1633 ramps over 9.6 f (no flash) |
| Titles | act card Act Two · Fire 1665–1726 (legible 1693–1715) over S15b — §6 |
| Geometry proof | `out/dev/breakdown/act2/geom.py` → `geom_report.txt` (23 cuts, ALL PASS); prop arcs `arcs.py` → `arcs_report.txt` |

Story of the lane in one line: the master's spear butt strikes the earth and the field ignites around them; the spear drives the student back (sweep, three thrusts — the third turned by a kunai as he slides in along the shaft, a low sweep he vaults); his three kunai ring off the spinning spear; the old man leaps and slams the ground into fire; the student slides under the spear into close quarters, is kicked away and brakes with his sword in the dirt; the spear is hurled like a javelin, knocked spinning into the flames; thunder; the master draws his sword again as the first drops hiss on the steel — the downpour drowns the ring in steam, and he lifts his blade into jodan.

Ring geometry (one call, owned by this lane): `vfx.fire_ring(1633, (0.0, 1.5, 0.0), radius=11.0, grow_frames=12, f_out=2401, height=2.2, …)` + `environment.grass_effect('burn', dict(center=(0.0, 1.5), radius=11.0, width=2.6, ramp_frames=18), 1638)`. Centre (0, 1.5) = midway between the handoff positions of both lane boundaries' fights; every fighter position of the lane is ≤ 5.6 m from it (the skid stop (0, −4.1)), and at the ignition the front passes under both at ≤ 47 % of its radius, where its tallest tongues are still ≤ 0.8 m (hidden by the 1.05 m grass) — see D1.

Root tracks (key frames; ease-in/out between keys unless noted; `geom.py SH_TRACK / EL_TRACK` are the same data, with the head-centre height in the 4th column). Facing: shinobi 180 = +Y, elder 0 (≡ 360) = −Y; rig z-rotation θ gives the forward vector (sin θ, −cos θ).

| frame | shinobi (x, y) facing | elder (x, y) facing | what happens |
|---|---|---|---|
| 1633 | (0.00, −1.50) 180 | (0.00, 6.50) 0 | HANDOFF[1632]; spear-butt impact at BUTT (0.08, 6.02, 0) |
| 1636→1646 | → (0.00, −1.75) | (0.00, 6.50) | shinobi's half step back from the eruption |
| 1669–1705 | (0.00, −1.75) | (0.00, 6.50) | elder lifts + twirls the spear (1669–1693), settles into the low spear guard 1705 |
| 1731→1747 | → (0.10, 3.10) | 1733→1745 → (0.00, 5.70), wind-up twist −30 | shinobi charges (6.2 m/s); elder two steps in, spear wound back |
| 1745→1765 | 1749–1753 slide-duck to (0.10, 3.45), head 1.15 | spin 360° in place (facing −30 → 330), tip crosses the front at **1753** | 360° sweep over the ducked head |
| 1758→1776 | back-step → (0.10, 2.70) | → (0.00, 5.85) | reset to thrust range (3.15 m) |
| 1789 / 1801 / 1813 | (0.10, 2.65) / (0.10, 2.62) / (0.08, 2.72) | lunges (0, 5.60) / (0, 5.50) / (0, 5.40), recovering 0.15 m between | thrusts 1–3 |
| 1813→1822 | → (−0.25, 4.30) facing 188 | (0.00, 5.40) extended | kunai slide along the shaft (on its −X side) |
| 1837 | (−0.22, 4.45) | (0.00, 5.45) facing 10 | one-handed cut blocked by the shaft |
| 1849→1861 | → (0.05, 2.80) facing 180 | → (0.00, 5.80) by 1866 | shaft shove, both reset (3.0 m) |
| 1873→1879 | → (0.05, 3.25) | (0.00, 5.80) | shinobi steps in |
| 1879→1897 | jump: apex 1885 (root z 0.55), lands (0.05, 3.05) | deep lunge 1880–1890 (head 1.25) | low sweep under the vault 1885 |
| 1899→1914 | two back-hops → (0.10, 1.15) | (0.00, 5.80) | distance for the throws (4.7 m) |
| 1937 / 1943 / 1949 | (0.10, 1.10) | (0.00, 5.80), spear spin 1935–1963 | kunai releases; deflects 1945 / 1951 / 1957 |
| 1975→1999 | (0.10, 1.10) | → (0.00, 4.60) take-off 1999 | three heavy strides |
| 1999→2017 | roll 2003→2019 → (−1.90, 1.25) facing 133, one knee | flight → lands (0.00, 3.00) at **2017**, apex 2008 (root z 0.55) | leaping slam; blade strikes IMPACT (0.10, 1.00) where the shinobi stood |
| 2021→2064 | rises 2030–2037; circles back → (−0.30, −0.90) facing 178 at 2060 | turns to face him (facing 330 → 313 at 2045), two steps → (0.00, 2.20) facing 355 at 2060 | aftermath, reset |
| 2065→2089 | sprint + knee-slide (2073→2085, head 0.95) → (−0.12, 1.10) | (0.00, 2.25) high thrust 2077 | slide under the spear, rising cut vs shaft 2089 |
| 2089→2172 | (−0.05…0.15, 1.10…1.20) | (0.00, 2.25…2.30) | close quarters: 2101, 2113, 2125, 2137, bind 2149–2158, kick chamber 2161–2172 |
| 2173→2204 | kicked: airborne → (0.10, −0.60) at 2180, skid → (0.00, −4.10) at 2204, head 1.10 | (0.00, 2.25) | kick contact 2173 is the CUT; sword-drag skid |
| 2185→2221 | rises 2209–2225 at (0.00, −4.10) | two steps back → (0.00, 3.00) | re-establish throwing distance |
| 2257→2269 | (0.00, −4.10) | cock 2257–2263, step → (0.00, 2.60), **release 2269** | javelin |
| 2281 | deflect at DEF (0.12, −3.45, 1.45) | (0.00, 2.55) | slow motion 2280–2304 |
| 2329→2345 | (0.00, −4.10) | steps back → (0.00, 3.00) | spear lands in the flames 2329 (beat 58) |
| 2370→2400 | (0.00, −4.10) | (0.00, 3.00) | katana drawn 2370–2384, raised to chudan by 2396 |
| 2410→2445 | three steps → (0.00, −3.00) | (0.00, 3.00) | in the downpour |
| 2460→2496 | (0.00, −3.00) | (0.00, 3.00), jodan 2460→2490 | HANDOFF[2496] |

Weapon / costume / hand states (`CH = characters`; all CONSTANT unless a blend is given)

| frame | call | note |
|---|---|---|
| 1633 | `CH.set_weapon_state(SHINOBI_rig, 1633, 'drawn')`; `CH.set_two_hand(SHINOBI_rig, 1633, True)`; `CH.set_kunai_in_hand(1633, False)`; `SHINOBI_kunai_1..3` hidden | re-assert the handoff (lane isolation) |
| 1633 | `CH.set_weapon_state(SAINT_rig, 1633, 'sheathed')` **then** `CH.set_weapon_state(SAINT_rig, 1633, 'in_hand')` (spear; order matters: the spear call sets `active_weapon`); `CH.set_two_hand(SAINT_rig, 1633, True, weapon='spear')`; `CH.set_costume(1633, haori=False)`; `CH.set_hat(1633, 'off')` | hat halves hidden from the S15 cut on (they lie in the grass; deviation D2) |
| 1633 | `CH.set_spear_grip(1633, grip_R=1.30, grip_L=0.85)` | vertical butt-down hold for the slam (right fist high) |
| 1633 | `SAINT_haori_thrown` location/rotation keyed CONSTANT at HAORI (0.80, 4.97, 0.88), back panel (roundel) up, tilted 35° toward +X | cheat across the hard cut (D2); burns 1641–1800 (§5 `_local_haori_burn`), `key_visible(False)` at 1801 |
| 1669–1705 | `CH.set_spear_grip(1669, 1.00, 1.30)` → `(1705, 0.35, 0.95)` | twirl grip (middle) → guard grip |
| 1741→1747 | `CH.set_spear_grip(1741, 0.35, 0.95)` → `(1747, 0.10, 0.50)` | both fists slide to the butt end: longest sweep radius (tip 2.2 m past the rear fist) |
| 1766→1776 | `CH.set_spear_grip(1776, 0.35, 0.95)` | thrust grip |
| 1805 | `CH.set_two_hand(SHINOBI_rig, 1805, False, blend=3)` | left hand leaves the hilt for the kunai (sword one-handed 1805–1866) |
| 1809 | `CH.set_kunai_in_hand(1809, True)` | kunai appears as the left fist comes up from the back of the sash (1806–1808 hand behind the hip) |
| 1861 | `CH.set_kunai_in_hand(1861, False)`; `CH.set_two_hand(SHINOBI_rig, 1866, True, blend=4)` | kunai tucked back into the sash; two-handed again |
| 1921→1927 | `CH.set_two_hand(SHINOBI_rig, 1921, False, blend=4)`; `CH.set_kunai_in_hand(1927, True)` | draws the kunai (sword in the right hand, low) |
| 1937 / 1943 / 1949 | `key_visible(SHINOBI_kunai_1/2/3, f, True)` at the fist + ballistic keys (§3 S17a); `CH.set_kunai_in_hand(1949, False)` | the in-hand kunai stands for "the next one" until the third release (D3) |
| 1960 | `CH.set_two_hand(SHINOBI_rig, 1960, True, blend=4)` | two-handed again |
| 1931 | `CH.set_spear_grip(1931, 1.00, 1.60)` | spin grip around the centre of mass (1.30 m) |
| 1963→1975 | `CH.set_spear_grip(1975, 0.20, 0.75)` | long grip for the overhead slam |
| 2021→2060 | `CH.set_spear_grip(2060, 0.50, 1.40)` | wide staff grip for close quarters (S18) |
| 2173 | `CH.set_two_hand(SHINOBI_rig, 2173, False)`; `CH.set_two_hand(SHINOBI_rig, 2215, True, blend=4)` | kicked: left hand drops to the ground in the skid, right hand drags the sword |
| 2236→2240 | `CH.set_spear_grip(2236, 1.30, 1.60)`; `CH.set_two_hand(SAINT_rig, 2240, False, blend=3)` | javelin grip at the centre of mass, right hand only |
| 2269 | `CH.set_weapon_state(SAINT_rig, 2269, 'world')` + `CH.snap_free(SAINT_spear_world, 2269)` then the ballistic keys (§3 S19a–c); `CH.set_arm_mode(SAINT_rig, 2272, 'fk', blend=4)` | release; empty right hand follows the pose library |
| 2329 | `SAINT_spear_world` keyed at rest in the flames: CoM SPEAR_LAND (−8.40, −5.60, 0.60), shaft tilted 25° (blade end down, in the fire) | stays there until the cut at 2401 |
| 2401 | `CH.set_weapon_state(SAINT_rig, 2401, 'gone')` | hidden on the S20 cut (HANDOFF spear = 'gone') |
| 2368→2370 | `CH.set_arm_mode(SAINT_rig, 2368, 'ik', blend=2)`; key `SAINT_sword_ctrl` at 2370 to `CH.sheathed_ctrl_matrix(SAINT_rig, 2370)`; `CH.set_weapon_state(SAINT_rig, 2370, 'drawn')` | pop-free draw: the in-hand blade starts exactly in the saya, slides out along the saya axis 2370→2382 |
| 2390 | `CH.set_two_hand(SAINT_rig, 2390, True, weapon='katana', blend=4)` | two-handed from chudan into jodan (DIRECTION §7: two-handed jodan in Act III) |

Deviations (all deliberate; everything else follows config / HANDOFF exactly)
- **D1 — ring centre is not the spear butt.** `vfx.fire_ring` grows its flame front from its own centre. Centred on the butt (0, 6.5) the ring would need R ≥ 16 m to pass under the shinobi (8 m away) while still low, or it would engulf him with ~1.5 m tongues. Centre (0, 1.5), R 11: the front passes under the shinobi at ρ = 0.27 (3.0 m, 1634, tongues ≤ 0.26 m) and the elder at ρ = 0.45 (5.0 m, 1635, tallest tongues ≤ 0.78 m) — inside the 1.05 m grass; it breaks out of the grass as a wall at r ≥ 7 m (1636–1637). Cause → effect is carried by the frame-exact impact + a local burst at the butt (dust, grass, sparks, `fire_ignite` event) and by the top-down of S15a. All Act II positions stay ≤ 5.6 m from the centre; Act III's worst case (shinobi (0, −6) at 3072) is 7.5 m from it — inside the steam band.
- **D2 — prop cheats across the S14→S15 hard cut.** `SAINT_haori_thrown` is re-keyed (CONSTANT) at 1633 to HAORI (0.80, 4.97, 0.88), draped on the grass tops 1.7 m in front-left of the elder (needed as the S15b foreground and to be seen from above in S15a); `SAINT_hat_half_A/B` are hidden from 1633 (`set_hat(1633, 'off')`). act1b's S14 rest poses are not used.
- **D3 — kunai count.** The shinobi carries three kunai (PLAN): the kunai that turns the third thrust (S16b, `SHINOBI_kunai_hand`) is tucked back at 1861 and is one of the three thrown in S17 (free `SHINOBI_kunai_1..3`).
- **D4 — the slam never sticks.** The S17 overhead slam strikes the ground with the blade + shaft flat and rebounds 15–25 cm; the elder lifts it with the recoil (deny-list: no spear pulled from the ground). Same for the butt at 1633.
- **D5 — S16c "reset" is a push-apart.** It contains one sword/shaft contact (1837) and a two-handed shaft shove through the crossed weapons (1849, weapon contact, not body contact → no cut needed), then both reset.
- **D6 — deflect on the beat.** Throw release 2269 (beat 53), deflect **2281** (beat 54) — config says "~2270 / ~2282"; 2281 lies inside the SLOWMO window (starts 2280).
- **D7 — drizzle before the downpour.** "first raindrops sizzle on the blade" needs rain before `rain_start`: the single rain call (D8) ramps 0 (2376) → 0.06 (2382) → 0.12 (2400) → 1.0 (2401). `rain_start` event + music cue stay at 2401.
- **D8 — this lane creates two film-long effects** (cross-lane contract, see §7 R1): the fire ring (flames 1633–2401, glowing steam band 2401–3456 via `f_out=2401`, default `f_end`) and the rain (`vfx.rain(2376, 3500, intensity=[…])`, exactly the vfx.py recipe incl. the S27 thinning 3470→3500). act3 / finale must not create a second ring or rain.
- **D9 — S20 is two high cuts.** DIRECTION: "S20 is a HIGH wide". S20a is the high wide (camera 14–15 m up); S20b (the jodan) is an elevated rear 3/4 over the elder's LEFT shoulder, camera 2.9 m up, 14° down — still a high angle, so S21's extreme wide opening is not a wide-to-wide cut.
- **D10 — the S17 roll goes toward −X** (away from the +X camera, perpendicular to the line): the slam's fire + dust at IMPACT sits between the lens and the rolled shinobi (S17d), a one-second "did he make it?" before S17e reveals him.

## 2. Beat grid (Act II, 120 BPM = 12 f per beat, anchor 1633)

`config.beat_frame('act2', b)` = 1633 + 12·b exactly (no rounding), 4/4, 18 bars; bar n starts at 1633 + 48·(n−1). Every shot boundary is a bar line (S16 1729 = bar 3, S17 1921 = bar 7, S18 2065 = bar 10, S19 2257 = bar 14, S20 2401 = bar 17, S21 2497 = act3 anchor). Hits in **bold** are contacts/impacts; *italics* = cut frames on the grid.

| bar | .1 | .2 | .3 | .4 |
|---|---|---|---|---|
| 1 | **1633** *S15a* butt impact, `fire_ignite`, `music_cue act2_start`, ring grows to 1645 | 1645 ring complete (radius 11 m) | *1657 S15b* | 1669 spear lift → twirl starts |
| 2 | 1681 twirl | 1693 twirl ends, card legible from 1693 | 1705 elder settles in the low spear guard | 1717 (breath; card legible to 1715) |
| 3 | *1729 S16a* shinobi launches (1731) | 1741 elder's wind-up, grip slides to the butt | **1753** 360° sweep over the ducked head (miss, whoosh) | 1765 spin completes |
| 4 | *1777 S16b* | **1789** thrust 1 deflected | **1801** thrust 2 deflected | **1813** thrust 3 turned by the kunai → slide 1813–1822 |
| 5 | *1825 S16c* | **1837** cut blocked by the shaft | 1849 shaft shove (weapons only) | 1861 both reset; kunai tucked |
| 6 | *1873 S16d* | **1885** low sweep under the vault (miss), grass burst | 1897 shinobi lands | 1909 back-hop 2 |
| 7 | *1921 S17a* left hand to the sash | 1933 (spin starts 1935) | **1945** kunai 1 deflected (release 1937) | **1957** kunai 3 deflected (1951 = kunai 2 on the half beat; releases 1943, 1949) |
| 8 | *1969 S17c* (menace hold ends 1975) | 1981 stride | 1993 stride (take-off 1999 on the half beat) | 2005 apex (2008) |
| 9 | **2017** leaping slam: ground impact, fire + dust, `shockwave` | 2029 shinobi on one knee | 2041 elder turned to him | 2053 re-approach |
| 10 | *2065 S18a* sprint | **2077** high thrust over the knee-slide (miss) | **2089** rising cut vs shaft | **2101** cut vs shaft |
| 11 | **2113** cut vs shaft | **2125** butt strike vs sword | **2137** spear head vs sword | **2149** overhead cut caught on the shaft → bind 2149–2158 |
| 12 | 2161 bind breaks, kick chambers | **2173** kick = the CUT (contact hidden) | 2185 skid (sword drag 2182–2204) | 2197 elder steps back |
| 13 | *2209 S18f* shinobi rises | 2221 elder at throwing distance | 2233 grip shift | 2245 javelin raised |
| 14 | *2257 S19a* cock | **2269** release (javelin) | **2281** deflect (slow motion 2280–2304) | 2293 (slow) spear rising out of frame |
| 15 | *2305 S19c* real time | 2317 spear past its apex (2311) | **2329** spear lands in the flames (`fire_burst`) | 2341 elder's hand to the hilt |
| 16 | *2353 S19d* `thunder` (tag thunder_first), `music_cue` (sound only, no flash) | 2365 hilt grip (draw 2370–2384) | 2377 blade clears the saya (2382) | 2389 first drops hiss on the steel; two-handed 2390 |
| 17 | *2401 S20a* `rain_start` + music cue, ring collapses (20 f, shadowed ring lights off at 2422) | 2413 steam band rising | 2425 in-cloud flash 0.45 | 2437 (flash 0.30 on 2443, half-way to 18.1) |
| 18 | *2449 S20b* | 2461 jodan lift starts (2460) | 2473 blade passing the head | 2485 jodan set (2490), hold to 2496 |

Rhythm: the spear owns bars 3–9 (sweep · thrust-thrust-THRUST · low sweep · spin-spin-spin · SLAM on the downbeat of bar 9), the student answers in bars 10–11 on every beat (his densest passage), bar 12.2 is the kick, bar 14 is the throw/deflect pair (.2/.3), and bars 16–18 empty out into thunder, rain and a stance: 14 weapon contacts in 36 s, the closest two 6 f apart (kunai 1945/1951/1957, deliberate half beats) and all others ≥ 12 f apart.

## 3. Sub-cuts

Cut list (final; every block repeats its frames). φ = camera azimuth about the fighters' midpoint (0 = +X profile, −90 = behind the shinobi, +90 = behind the elder). Screen numbers: `geom_report.txt` / `summary.txt`.

| cut | frames | len | camera | lens | φ (f0→f1) | beat / story point |
|---|---|---|---|---|---|---|
| S15a | 1633–1656 | 24 | top-down, descending 50 → 38 m, impact shake | 28 | (overhead) | butt impact 1633, ring races out to R 11 by 1645 |
| S15b | 1657–1728 | 72 | low single on the elder, burning haori foreground, slow push, rack focus | 32 | +22 → +26 | twirl → low spear guard; act card 1665–1726 |
| S16a | 1729–1776 | 48 | low wide profile, slow lateral dolly | 28 | +2 → −9 | charge; 360° sweep over the ducked head 1753 |
| S16b | 1777–1824 | 48 | OTS over the elder's LEFT shoulder, down the thrust axis, creeping push | 50 | +75 → +66 | thrusts 1789 / 1801 / 1813, kunai turn + slide |
| S16c | 1825–1872 | 48 | handheld medium profile, drifting back | 40 | −24 → −24 | cut vs shaft 1837, shove 1849, reset |
| S16d | 1873–1920 | 48 | elevated lateral wide (2.3 m), dolly −0.6 m | 28 | −8 → −6 | low sweep 1885 under the vault, land 1897, back-hops |
| S17a | 1921–1947 | 27 | OTS over the shinobi's RIGHT shoulder, locked-ish | 40 | −79 | kunai releases 1937 / 1943, deflect 1 1945 |
| S17b | 1948–1968 | 21 | low medium single on the elder, handheld | 45 | +16 → +18 | deflects 1951 / 1957, spin stops |
| S17c | 1969–2004 | 36 | ground-level low angle, handheld, tilts up | 28 | −27 → −15 | menace hold, charge, take-off 1999 |
| S17d | 2005–2020 | 16 | wide profile, locked, heavy impact shake | 28 | −7 → −3 | slam 2017 (fire + dust), roll to −X |
| S17e | 2021–2064 | 44 | medium-wide, slow drift | 35 | −15 → −11 | aftermath, he rises, both reset |
| S18a | 2065–2091 | 27 | handheld tracking alongside the slide | 35 | −37 → −26 | knee-slide under the thrust 2077, rising cut 2089 |
| S18b | 2092–2115 | 24 | handheld OTS over the shinobi's RIGHT shoulder | 40 | −61 → −62 | cuts vs shaft 2101, 2113 |
| S18c | 2116–2139 | 24 | handheld OTS over the elder's LEFT shoulder | 45 | +64 → +62 | butt strike 2125, spear-head chop 2137 |
| S18d | 2140–2172 | 33 | handheld medium profile | 40 | −2 → −5 | bind 2149–2158, kick chambers; CUT on the contact |
| S18e | 2173–2208 | 36 | low wide, pans left with the skid, impact shake | 24 | −23 → −16 | kicked, skids screen-left, sword drag, stops 2204 |
| S18f | 2209–2256 | 48 | low wide profile, near-locked | 24 | +1 | he rises; javelin grip |
| S19a | 2257–2276 | 20 | low medium single on the elder (+15° up) | 35 | +59 | javelin release 2269 exits screen-left |
| S19b | 2277–2304 | 28 | MCU from the shinobi's right-rear 3/4, locked, **slow motion 2280–2304** | 50 | −67 | deflect 2281, spear rises out of frame |
| S19c | 2305–2352 | 48 | low wide from the −Y/+X quadrant, small pan | 24 | −28 → −24 | spear cartwheels into the flames 2329 |
| S19d | 2353–2400 | 48 | low medium single on the elder, creeping in | 45 | +42 → +45 | thunder 2353, draw 2370–2384, drops hiss |
| S20a | 2401–2448 | 48 | HIGH wide (15 m up, −31°), slow descending push | 24 | −23 → −25 | downpour, ring drowns into steam, lightning 2425 / 2443 |
| S20b | 2449–2496 | 48 | elevated rear 3/4 over the elder's LEFT shoulder (2.9 m up, −14°) | 32 | +72 | jodan 2460–2490 against the steam band |

23 cuts / 864 f = 37.6 f average (fights 16–48 f; the long ones — S15b 72 f with the act card, S16/S19/S20 48 f — carry either the card, a single held stance, or three hits each).

Shared conventions for every block
- `C = cameras`, `EV = events`, `ENV = environment`, `VFX = vfx`, `CH = characters`, `M = moves`, `U = bl_util`.
- Every camera: `C.shot(cut_id, f0, f1, keys, dof=..., shake=..., handheld=..., subjects=..., framing=...)`; keys are `(frame, pos, look, lens)`; cameras.shot makes the last key CONSTANT. Lenses are fixed per cut (no zooms).
- Screen numbers are NDC heads (x, y) and "fig" = ground→head-top as % of frame height (the grass hides everything below the quoted grass line). "fire tops" = NDC y of the ring's 2.2 m tongue tops straight behind the subjects.
- Every contact goes through `M.clash(attacker, defender, f, point)` (Pipeline rule 9: both controllers are placed so the weapon segments cross at `point`; `end_lane` resolves ≤ 3–5 cm and emits the sparks + `clash` event). The explicit `VFX.sparks` lines below are *extra* sparks only (scrapes, ground strikes, kunai) — never double the clash burst. Spark colour (vfx.py): elder-initiated = `'fire'`, shinobi-initiated (his cuts, his kunai) = `'white'`.
- Spear as a weapon for `M.clash`: segment `SAINT_spear_base → SAINT_spear_tip` for blade contacts; for shaft contacts pass the point on the shaft (the resolver uses the whole spear segment butt→tip: `CH.blade_points(SAINT_rig, weapon='spear')` returns the socket pair; if it only returns the head, add a `_local_shaft_points()` helper that extends base→butt by `DIMS['SAINT']['spear_length'] − spear_blade_length`).
- Key light: `ENV.set_sun(f0, az, −2.0)` on each cut's first frame (CONSTANT) with the az in the block — always chosen so the light (KEY_MIN_EL 2.5°) comes from behind the subjects = rim/backlight (geom_report: "from behind the subjects? YES" on all 23 cuts). 270 = from −X (the default for +X profiles), 180 = from −Y, 0 = from +Y.
- Grass: default camera clearance (1.5, 4.0) everywhere (`key_lane_defaults`); no overrides needed (no camera inside the burn annulus 9.7–12.3 m: all cameras are at ring-r ≤ 8.6 m (S16d) or outside the ring (S20a, 22–25 m)).
- Hard cuts: every character/prop root keyed CONSTANT on each cut's last frame when the next cut cheats a position (Pipeline rule 2); cheats in this lane ≤ 0.10 m except the D2 prop cheats at 1633.
- Seeds: `zlib.crc32(f"{cut}:{i}".encode())`; the `seed=` values below are placeholders for "one distinct seed each".
- Secondary motion: hachimaki tails + beard get `wind` from `ENV.set_wind` (Act II 1.6–1.8: whipping in the fire, DIRECTION §7); springs reset on every cut marker (Pipeline rule 11).

Ballistic props (all on the fx clock: t = `fxclock.fx_time_at(f) − fxclock.fx_time_at(f0)`, so the S19 slow motion slows them; `arcs.py` prints every frame):

| prop | from → to | frames | v0 (m/s) | apex |
|---|---|---|---|---|
| `SHINOBI_kunai_1` | (−0.15, 1.45, 1.55) → (0.35, 5.15, 1.55) | 1937 → 1945 | (+1.50, +11.10, +1.63) | 1.69 m @1941 |
| `SHINOBI_kunai_2` | (−0.15, 1.45, 1.50) → (−0.30, 5.15, 1.20) | 1943 → 1951 | (−0.45, +11.10, +0.73) | 1.53 m @1945 |
| `SHINOBI_kunai_3` | (−0.15, 1.45, 1.55) → (0.10, 5.15, 1.75) | 1949 → 1957 | (+0.75, +11.10, +2.23) | 1.80 m @1954 |
| kunai 1 deflected | (0.35, 5.15, 1.55) → (2.8, 4.2, 0.0) | 1945 → 1969 | (+2.45, −0.95, +3.36) | 2.12 m, spin 18 rad/s |
| kunai 2 deflected | (−0.30, 5.15, 1.20) → (−3.1, 6.2, 0.0) | 1951 → 1969 | (−3.73, +1.40, +2.08) | 1.42 m, spin 15 rad/s |
| kunai 3 deflected | (0.10, 5.15, 1.75) → (0.8, 8.0, 0.0) | 1957 → 1985 | (+0.60, +2.44, +4.22) | 2.66 m, spin 20 rad/s |
| `SAINT_spear_world` (CoM) javelin | REL (−0.25, 2.05, 1.95) → DEF (0.12, −3.45, 1.45) | 2269 → 2281 | (+0.78, −11.58, +1.28) | 2.03 m; tip forward, no spin (slight 2° wobble) |
| `SAINT_spear_world` deflected | DEF → SPEAR_LAND (−8.40, −5.60, 0.60) | 2281 → 2329 | (−5.98, −1.51, +6.39) | 3.53 m @2310; end-over-end 1.2 rev/s (fx) → 1.7 rev |

(The deflected kunai / spear land and stay: the kunai lie in the grass (hidden by it); the spear rests in the flames, blade end down, until the 2401 cut.) Use `props.toss` if it exists and accepts an fx-time mapping; otherwise key the closed-form positions per frame with `_local_ballistic(obj, f0, p0, v0, f1, spin_axis, spin_rate)` (§5), rotation from the spin, CONSTANT on the landing frame.

### S15a — 1633–1656 (24 f) — the ignition, seen from above
Purpose: the spear butt strikes the earth on the downbeat and a circle of fire races outward through the grass until it closes around both fighters: the arena of Act II is a ring you cannot leave.

Camera (straight down; image right = +Y, image top = −X — the continuation of every +X profile tilted down):
```python
C.shot("S15a", 1633, 1656,
       keys=[(1633, (0.60, 1.50, 50.0), (0.0, 1.50, 0.0), 28.0),     # 0.60 m x-offset keeps look-at defined:
             (1656, (0.46, 1.50, 38.0), (0.0, 1.50, 0.0), 28.0)],    # pitch -89.3 deg, roll 0 -> right = +Y
       dof=None, shake=[(1633, 0.25, 6)], handheld=0.0, subjects=["shinobi", "saint"], framing="wide")
```
- Ground footprint 64.3 × 27.3 m (1633) → 55.7 × 23.7 (1645) → 48.9 × 20.8 m (1656). The finished ring (Ø 22 m): ±Y ends at NDC x ±0.34 / ±0.39 / ±0.45, ±X ends at NDC y ∓0.81 / ∓0.93 / ∓1.06 → the circle is complete and fully in frame when it closes (1645) and is just kissing the top/bottom edges at the cut (the descent tightens it).
- Heads: shinobi NDC x −0.10 → −0.14, elder +0.16 → +0.21, both on the horizontal centre line (y ±0.00); 180 rule OK (shinobi left of the elder). They are small (shoulders ≈ 15–20 px): the ring is the subject; the elder is marked by the dust puff at BUTT (NDC (+0.14, −0.01)) and his spear (≈ 75 px long). Haori at NDC (+0.11..+0.15, −0.06..−0.08), just below-left of him — its small fire patch (from 1641) is a second bright point beside the elder.
- Bottom/top of frame: grass (the camera is 38–50 m up; the clearance sphere never touches the ground).

Action
- Elder (0, 6.5) facing 0: local pose `spear_butt_slam` (§5) keyed at 1633 (the S14 last frame is the spear coming down — see §7 R2), recoil 1633→1637 (hips −0.10 → −0.14, knees give), hold to 1645, straightens 1645→1656 (hips −0.06), spear upright, butt resting on BUTT (never planted).
- Shinobi (0, −1.5) facing 180, chudan: `M.step` back 1636→1646 to (0.00, −1.75); head turns right 15° (1640) and left 15° (1648), tracking the flames as they rise around him; back to centre 1656.

Environment
- `ENV.key_lane_defaults` already gives `crimson_fire` + the default sun (270, −2.0) at 1633 — no set_state needed.
- `ENV.set_wind(1633, 1.6, direction_deg=205)` (fire draft; tails whip) — holds for the act until 2353.
- `ENV.grass_effect('burn', dict(center=(0.0, 1.5), radius=11.0, width=2.6, ramp_frames=18), 1638)` — the ring's annulus chars and collapses to stubble (visible in the S15a descent and in every later wide).

VFX
```python
RING = VFX.fire_ring(1633, (0.0, 1.5, 0.0), radius=11.0, grow_frames=12, f_out=2401, height=2.2, seed=15,
              ember_rate=40.0, shadow_angles=(150.0, 210.0), light_energy=400.0)   # ONE call: flames + smoke + embers
              # + 8 lights (2 shadowed on the -X side) now; f_out 2401 -> flames die over 20 f, glowing steam band
              # until the default f_end (end of Act III, 3456) = the Act III backlight layer (DIRECTION §6)
VFX.dust_burst(1633, BUTT, radius=0.9, seed=151)                      # BUTT = (0.08, 6.02, 0.0)
VFX.grass_burst(1633, (0.08, 6.02, 0.30), (0.0, 0.0, 1.0), count=90, speed=3.0, seed=152)
VFX.sparks(1633, (0.08, 6.02, 0.05), direction=(0, 0, 1), count=24, speed=2.5, life=8, color='fire',
           scale=0.6, light=False, seed=153)                           # iron ishizuki on a stone
VFX.embers(1633, 2405, (0.0, 1.5, 0.0), 11.0, rate=25.0, height=(0.3, 2.5), seed=154)   # arena-wide drift
# the discarded haori catches as the (grass-hidden) front passes under it (~1635):
_local_haori_burn("SAINT_haori_thrown", ignite=1641, gone=1800)       # §5: dissolve + glowing edge on fx_time
VFX.fire_ring(1641, (0.80, 4.97, 0.80), radius=0.45, grow_frames=10, count=36, height=0.9, lights=False,
              smoke=False, ember_rate=10.0, ground_glow=False, extinguish=False, f_out=1776, f_end=1800, seed=155)
```
Events
```python
EV.emit(1633, "fire_ignite", pos=BUTT, strength=1.0, tags=["act2_start"])
EV.emit(1633, "music_cue", cue="act2_start")
EV.emit(1633, "land", who="saint", pos=BUTT, strength=0.8, tags=["spear_butt"])   # the thud of the butt
EV.emit(1638, "fire_burst", pos=(0.0, 1.5, 0.5), strength=1.0, tags=["ring"])     # the roar as it breaks the grass
EV.emit(1641, "fire_burst", pos=HAORI, strength=0.35, tags=["haori"])
EV.emit(1636, "step", who="shinobi"); EV.emit(1646, "step", who="shinobi")
```
Notes: no white flash on the impact (red-flash rule): the only brightness change is the fire's own ramp — the tongue height ramps over max(7 f, 0.8 × grow) = 9.6 f (≥ 6 f, DIRECTION §5), the ring lights follow the same curve. The flame front passes under the shinobi at 1634 (tongues ≤ 0.26 m) and under the elder at 1635 (≤ 0.78 m) — hidden in the 1.05 m grass (D1); it breaks out of the grass as a visible wall from r ≈ 7 m (≈ 1636–1637; 1.6 m tongues by r 9 m).

### S15b — 1657–1728 (72 f) — the master re-armed (act card Act Two · Fire)
Purpose: the new phase: the old man, bare-headed and in his white tasuki, stands inside a wall of fire with the spear; his old haori burns at his feet; the act card. The spear twirl happens while the card writes itself in; he is still when it is legible.

Camera (low, 1.05 m, looking up 6–7°; slow push-in 0.45 m; rack focus haori → elder):
```python
C.shot("S15b", 1657, 1728,
       keys=[(1657, (4.60, 4.20, 1.05), (0.20, 6.30, 1.55), 32.0),
             (1728, (4.20, 4.40, 1.05), (0.10, 6.40, 1.60), 32.0)],
       dof=dict(fstop=2.8, distance_keys=[(1657, 3.72), (1672, 3.72), (1684, 5.00), (1728, 4.73)]),
       handheld=0.25, subjects=["saint"], framing="wide")
```
- Elder head NDC (+0.03, +0.07) → (+0.02, −0.03); figure 74 → 78 % H (the grass line at NDC y −0.43..−0.57 → he reads from the belt up). Single-character check: he faces −Y → projects screen-LEFT (toward the off-screen shinobi, x −8) ✓.
- Burning haori (0.80, 4.97, 0.88): NDC (−0.45, −0.62), depth 3.7 m — the lower-left foreground (the roundel panel tilted 35° toward the lens so the crest is legible as it chars).
- Spear: during the twirl (1669–1693) the wheel stays within NDC x −0.17…+0.18 (§6); in the guard (1705–1728) the tip (0.06, 4.49, 1.25) is at NDC (−0.79…−0.82, −0.27), pointing left toward the off-screen shinobi.
- Fire ring behind him at 10.4–13.1 m, **height cheated to 1.3 m for this cut** (below): the grass hides everything below NDC y −0.43; typical tongues reach ≈ −0.15, big ones ≈ −0.10, rare flicker peaks (2.5 m) ≈ +0.12..+0.20 on the card side → a band of fire behind his hips, smoke + crimson sky above; the ring surges to its 2.2 m wall 1717→1729.
- Act card (§6): the card backdrop is x +0.34…+0.86, y −0.29…+0.70; the elder's head top stays at x +0.02..+0.03 (≥ 0.31 NDC clear), the spear in the guard points LEFT; nothing but smoke and sky under the card.
- Bottom ray: grass at 3.0–3.2 m (clearance scale 0.62–0.69) — the frame bottom is soft grass in front of the haori.

Action
- Elder (0, 6.5): 1657–1669 holds the spear upright (butt on the ground, breathing); 1669–1693 `M.spear_spin(SAINT_rig, 1669, 1693)` — a two-handed side-wheel in the vertical plane through his shoulders (world X-Z; hub at his right hip (−0.25, 6.45, 1.35), 1.5 turns, grip (1.00, 1.30)) — NOT in his facing plane (§6: it would cross under the card) — ending with the head swinging down to point at the shinobi; 1693–1705 settles into the local pose `spear_guard_low` (§5): left foot forward, hips −0.12, spear diagonal, tip (0.06, 4.49, 1.25), rear fist at the right hip; 1705–1728 still (breathing only; beard, tasuki ends and sleeves move in the heat wind).
- Shinobi off-screen at (0, −1.75) in chudan (keep keys: he is seen again at 1729).

Environment: `ENV.set_sun(1657, 270, −2.0)` (backlight from −X, the glow behind the ring). Wind 1.6 continues. VFX
```python
# card legibility cheat (§6): the ring's tongues are lowered for this cut only and surge back after the card
ring = RING["flames"]            # RING = the dict returned by the S15a fire_ring call; GN input "Height" on its modifier
U.gn_key(ring, "Height", 1633, 2.2, interp='CONSTANT')
U.gn_key(ring, "Height", 1657, 1.3, interp='CONSTANT')          # S15b: settled 1.3 m, big tongues 1.9, peaks 2.5
U.gn_key(ring, "Height", 1717, 1.3, interp='SINE')              # beat 7: the ring surges as the card fades
U.gn_key(ring, "Height", 1729, 2.2, interp='CONSTANT')          # the S16 wall (2.2 m) from the next cut on
VFX.blade_trail("SAINT_spear_tip", "SAINT_spear_base", 1671, 1693, owner="saint", width=0.72)  # fire-orange arcs
# haori: the local burn + patch from S15a continue (flames peak ~1655-1700, die 1776-1796, gone 1800)
```
Events
```python
EV.emit(1669, "spear_spin", who="saint", duration=24)
for f in (1675, 1683, 1691): EV.emit(f, "whoosh", who="saint", weapon="spear", strength=0.5)
EV.emit(1699, "step", who="saint", strength=0.5)
```
Notes: card timing (titles.py measured): column ramps 1678, accent 1686, seal impact 1687, legible 1693–1715 — the twirl ends exactly at 1693, so the image is still under the legible card. Keep the haori flames ≤ 0.9 m so they never reach the card box (they are at the frame's lower-left, far from it).

### S16a — 1729–1776 (48 f) — the charge meets the 360° sweep
Purpose: the student attacks first; the master answers with a full-body sweep that would take his head — he drops under it at full speed. The spear's reach is established.

Camera (low wide profile, 1.35 m, level; lateral dolly +0.4 m in Y):
```python
C.shot("S16a", 1729, 1776,
       keys=[(1729, (8.20, 2.60, 1.35), (0.0, 3.60, 1.35), 28.0),
             (1776, (8.20, 3.00, 1.35), (0.0, 4.00, 1.35), 28.0)],
       dof=dict(fstop=5.6, focus=8.4), handheld=0.15, subjects=["shinobi", "saint"], framing="wide")
```
| frame | shinobi head NDC / fig | elder head NDC / fig | note |
|---|---|---|---|
| 1729 | (−1.08, +0.09) off-screen left | (+0.52, +0.10) 36 % | he bursts in from the left edge ≈ 1733 |
| 1747 | (−0.12, +0.05) 35 % | (+0.36, +0.08) 36 % | end of the dash |
| 1753 | (−0.07, −0.09) 29 %, head top y −0.04 | (+0.34, +0.07) 35 % | grass line y −0.15 → 0.11 NDC of head visible; the spear passes over at NDC (−0.07, +0.11) |
| 1765 | (−0.15, +0.05) 36 % | (+0.32, +0.09) 36 % | spin completes |
| 1776 | (−0.25, +0.09) 38 % | (+0.34, +0.10) 37 % | reset at thrust range |
180 rule OK on every checked frame. Fire ring behind at 18.7 m: tongue tops at NDC y +0.17, grass line −0.15 → both figures' chests and heads stand against the flame band (DIRECTION §3: low angle against the fire).

Action
- Shinobi: 1729–1731 chudan → `M.dash(SHINOBI_rig, 1731, 1747, (0.00, −1.70), (0.10, 3.10))` (sword two-handed, held low right, point back); 1747–1753 sliding duck (local `slide_duck`, §5): the feet keep sliding 0.35 m to (0.10, 3.45), hips drop 0.45 m, torso upright, sword low at his right side (waki, point back — kept out of the spear's path) — head centre **1.15 m** at 1753 (never lower: the grass line is 1.02–1.05 m); holds 1753–1758; rises 1758–1766; two small back-hops 1766–1776 to (0.10, 2.70) into chudan.
- Elder: 1729–1733 guard; steps 1735, 1742 → (0.00, 5.70) while winding the spear to his right-rear (tip compass 300°) and sliding both fists to the butt end (grip 0.10 / 0.50, see §1 table); 1745–1765 `M.spear_sweep(SAINT_rig, 1745, kind="spin360", height=1.60)` (local if the macro lacks it, §5): pivot on the left foot, facing −30 → 330 continuous; the spear horizontal at z 1.55–1.65; tip compass 300 → **180 (straight at the shinobi) at 1753** → 90 → 0 → ≈300 at 1765 (≈13°/f to the front, ≈21°/f after; rig z-rotation keys in §5). Tip radius 2.65 m: at 1753 the head (radius 2.35–2.65) passes over the ducked shinobi (2.25 m from the elder's axis) with 0.25 m clearance above his head top (1.27 m). 1765–1776 steps back to (0.00, 5.85), levels the spear into the thrust guard (grip 0.35 / 0.95).
- Contacts: none (1753 is a miss).

Environment: `ENV.set_sun(1729, 270, −2.0)`. VFX
```python
VFX.blade_trail("SAINT_spear_tip", "SAINT_spear_base", 1747, 1761, owner="saint")
VFX.dust_burst(1750, (0.10, 3.30, 0.0), radius=0.6, seed=161)               # the sliding duck
VFX.grass_burst(1752, (0.10, 3.45, 0.55), (0.0, 0.4, 1.0), count=50, seed=162)
```
Events
```python
EV.emit(1731, "dash", who="shinobi")
for f, w in ((1735, "saint"), (1742, "saint"), (1739, "shinobi"), (1744, "shinobi")): EV.emit(f, "step", who=w)
EV.emit(1749, "whoosh", who="saint", weapon="spear", strength=1.0)      # the front half of the sweep, peak 1753
EV.emit(1749, "skid", who="shinobi", duration=6)
EV.emit(1759, "whoosh", who="saint", weapon="spear", strength=0.6)      # the back half of the spin
EV.emit(1768, "step", who="shinobi"); EV.emit(1773, "step", who="shinobi")
```
Notes: the duck must read as a duck, not a vanish: keep the head centre ≥ 1.15 m; the tails flick up as he drops (secondary motion) and the spear passes 0.25 m over his head top — no blade contact. Cut 1776/1777 on the bar line (no contact to protect).

### S16b — 1777–1824 (48 f) — three thrusts down the barrel
Purpose: the spear's speed and the student's answer: two clean sword deflections, then the third thrust turned aside by a kunai in his off hand while he slides in along the shaft — the spear's reach is beaten.

Camera (OTS over the elder's LEFT shoulder, on the thrust axis, eye level 1.78 m, creeping push):
```python
C.shot("S16b", 1777, 1824,
       keys=[(1777, (0.62, 7.25, 1.78), (0.00, 3.00, 1.48), 50.0),
             (1824, (0.62, 7.05, 1.78), (-0.10, 3.70, 1.45), 50.0)],
       dof=dict(fstop=2.8, distance_keys=[(1777, 4.60), (1813, 4.50), (1822, 3.05)]),
       handheld=0.35, shake=[(1789, 0.25, 5), (1801, 0.25, 5), (1813, 0.35, 6)],
       subjects=["shinobi", "saint"], framing="ots")
```
| frame | shinobi head NDC / fig | elder head NDC / fig | contact NDC |
|---|---|---|---|
| 1777 | (−0.09, +0.12) 116 % | (+0.75, −0.43) 344 % (fg shoulder, soft) | — |
| 1789 | (−0.11, +0.11) 113 % | (+0.59, −0.52) 295 % | (+0.04, −0.18) depth 4.0 m |
| 1801 | (−0.17, +0.16) 114 % | (+0.51, −0.44) 287 % | (−0.18, −0.13) |
| 1813 | (−0.21, +0.15) 115 % | (+0.43, −0.43) 275 % | (−0.03, −0.08) |
| 1824 | (+0.28, −0.09) 173 % (slid in toward the lens) | (+0.41, −0.34) 281 % | — |
180 rule OK throughout (the closest is 1824: +0.28 < +0.41). Behind the shinobi the ring (16.6–16.9 m) fills the upper half: tongue tops at NDC y +0.62 → +0.80 — he is framed against the flames, the elder's dark back in the foreground right.

Action
- Elder (seen from behind): three `M.spear_thrust(SAINT_rig, f)` at **1789 / 1801 / 1813**, each a 6-f drive with a lunge (root (0, 5.85) → 5.60 / 5.50 / 5.40) and a 6-f recovery of 0.15 m; tip at full extension ≈ 2.45 m ahead of the root (grip 0.35 / 0.95). Third thrust stays extended 1813–1824 while the shinobi slides along it.
- Shinobi (0.10, 2.65–2.72), facing 180:
  - 1789 `M.deflect(SHINOBI_rig, 1789, "mid_L")` two-handed: the blade knocks the spear head to his left (−X);
  - 1801 `M.deflect(SHINOBI_rig, 1801, "mid_R")` to his right (+X);
  - 1805 left hand leaves the hilt (sword one-handed in the right hand, held high-back), 1806–1808 the left hand goes behind the right hip to the sash, 1809 kunai in the left fist (`CH.set_kunai_in_hand(1809, True)`);
  - 1813 local move `kunai_parry_slide` (§5): the left forearm sweeps the kunai across his centre line and meets the shaft on its −X side just behind the spear head, pushing the head past his right side (+X); he steps forward-left and slides along the shaft 1813→1822 from (0.08, 2.72) to (−0.25, 4.30), facing 185 → 188, the kunai edge scraping along the shaft (contact moving from (−0.10, 3.30, 1.32) to (−0.10, 4.35, 1.38)); the sword cocked high-right for a cut. At 1824 he is 1.1 m from the elder, inside the reach.
- Contacts: 1789 sword/spear head (−0.05, 3.30, 1.38) s 0.7; 1801 sword/spear head (0.22, 3.25, 1.30) s 0.75; 1813 kunai/shaft (−0.10, 3.30, 1.32) s 0.8 (+ scrape).

Environment: `ENV.set_sun(1777, 180, −2.0)` — key + glow from −Y: rim on the shinobi, the elder's back in shadow. VFX
```python
for f0, f1 in ((1785, 1789), (1797, 1801), (1809, 1813)):
    VFX.blade_trail("SAINT_spear_tip", "SAINT_spear_base", f0, f1, owner="saint")
VFX.blade_trail("SHINOBI_katana_tip", "SHINOBI_katana_base", 1786, 1791, owner="shinobi")
VFX.blade_trail("SHINOBI_katana_tip", "SHINOBI_katana_base", 1798, 1803, owner="shinobi")
for k, f in enumerate(range(1814, 1823, 2)):                               # the kunai scraping along the shaft
    VFX.sparks(f, (-0.10, 3.40 + 0.24 * k, 1.33 + 0.01 * k), direction=(-0.3, -0.6, 0.7), count=12, speed=2.0,
               life=6, color="white", scale=0.5, light=(k == 0), seed=170 + k)
```
Events
```python
for f in (1785, 1797, 1809): EV.emit(f, "whoosh", who="saint", weapon="spear", strength=0.8)
# clashes 1789, 1801 via M.clash (strength 0.7 / 0.75); the kunai contact:
M.clash(SAINT_rig, SHINOBI_rig, 1813, (-0.10, 3.30, 1.32), strength=0.8, weapon_b="kunai")   # or emit
EV.emit(1814, "skid", who="shinobi", duration=8, tags=["blade", "scrape"])                    # the slide
```
(If `M.clash` cannot take the kunai as the defender's weapon, emit `EV.emit(1813, "clash", pos=…, strength=0.8, weapon="kunai")` + the first `VFX.sparks` above at count 40 instead.)

Notes: the kunai is small — make the contact read by (1) the white spark scrape running up the shaft toward the lens, (2) the spear head swinging wide past his right side, (3) the shaft's orientation change (≥ 8° deflection).

### S16c — 1825–1872 (48 f) — inside the reach, and pushed back out
Purpose: inside the spear's reach the student strikes, the master blocks with the shaft and shoves him back out: distance restored — the reset.

Camera (handheld medium profile, drifting back and widening as they separate):
```python
C.shot("S16c", 1825, 1872,
       keys=[(1825, (3.60, 3.20, 1.45), (-0.10, 4.90, 1.45), 40.0),
             (1849, (3.90, 3.00, 1.45), (-0.05, 4.50, 1.42), 40.0),
             (1872, (4.60, 2.80, 1.50), (0.00, 4.20, 1.40), 40.0)],
       dof=dict(fstop=4.0, focus=4.3), handheld=0.6, shake=[(1837, 0.4, 6), (1849, 0.3, 5)],
       subjects=["shinobi", "saint"], framing="medium")
```
Screen: 1825 sh (−0.31, +0.03) 104 %, el (+0.26, +0.09) 103 %; 1837 sh (−0.15, +0.04), el (+0.37, +0.14), contact (+0.12, +0.02); 1849 sh (−0.08, +0.10), el (+0.42, +0.15); 1861 sh (−0.80, +0.15), el (+0.58, +0.18); 1872 sh (−0.68, +0.17), el (+0.65, +0.19). Waist-up (grass line NDC y ≈ −1.0). Fire tops at +0.30..+0.36 behind the torsos.

Action
- Shinobi: 1825–1837 one-handed `M.slash(SHINOBI_rig, 1837, "diag_down_R")` at the elder's front hand/shoulder (the kunai hand guards at chest height); 1837–1849 presses both weapons crossed against the shaft; 1849 is shoved: `M.skid(SHINOBI_rig, 1850, 1861, (−0.20, 4.40), (0.05, 2.80))` facing 184 → 180; 1861 tucks the kunai (`CH.set_kunai_in_hand(1861, False)`), 1866 two-handed chudan (blend 4).
- Elder: 1825–1837 releases the front hand and pivots (facing 360 → 370), the shaft vertical at his right side (grip 0.35 / 1.30 after a quick slide of the left hand) → blocks at 1837; 1841–1849 `M.blade_lock(SAINT_rig, SHINOBI_rig, 1841, 1849)` (shaft vs sword + kunai), 1849 local `shaft_shove` (§5: both arms extend, shaft horizontal at chest height); 1853–1865 `M.spear_spin(SAINT_rig, 1853, 1865)` (a one-turn flourish at his side) into the thrust guard at (0.00, 5.80) by 1866.
- Contacts: 1837 sword/shaft (−0.10, 4.95, 1.45) s 0.75 (shinobi-initiated → white sparks); 1841–1849 lock.

Environment: `ENV.set_sun(1825, 270, −2.0)`. VFX
```python
VFX.blade_trail("SHINOBI_katana_tip", "SHINOBI_katana_base", 1830, 1837, owner="shinobi")
VFX.dust_burst(1851, (0.00, 3.90, 0.0), radius=0.6, seed=181)       # the skid back
VFX.grass_burst(1855, (0.02, 3.30, 0.40), (0.0, -1.0, 0.6), count=40, seed=182)
VFX.blade_trail("SAINT_spear_tip", "SAINT_spear_base", 1853, 1865, owner="saint")
```
Events
```python
EV.emit(1831, "whoosh", who="shinobi", weapon="katana", strength=0.7)
# clash 1837 via M.clash; lock:
EV.emit(1841, "blade_lock", duration=8, pos=(-0.10, 4.90, 1.45))
EV.emit(1850, "skid", who="shinobi", duration=11)
EV.emit(1853, "spear_spin", who="saint", duration=12)
EV.emit(1866, "step", who="saint")
```
Notes: the shove is weapon-on-weapon (no body contact) so it plays on screen. The camera drifts back 1849→1872 so the reset distance (3.0 m) is felt; cut on the bar line 1873.

### S16d — 1873–1920 (48 f) — the low sweep, vaulted
Purpose: the spear sweeps at shin height through the grass; the student vaults it, lands, and hops back out of range — now he needs another weapon to reach the old man.

Camera (lateral wide, elevated to 2.3 m and looking 9° down so the grass surface — and the sweep's burst through it — reads; lateral dolly −0.6 m following the back-hops):
```python
C.shot("S16d", 1873, 1920,
       keys=[(1873, (8.40, 3.20, 2.30), (0.0, 3.80, 1.00), 28.0),
             (1920, (8.40, 2.60, 2.30), (0.0, 3.20, 1.00), 28.0)],
       dof=None, handheld=0.1, shake=[(1897, 0.2, 4)], subjects=["shinobi", "saint"], framing="wide")
```
Screen: 1873 sh (−0.17, +0.23) 35 %, el (+0.36, +0.24) 35 %; 1885 sh (−0.09, +0.41) 44 % (apex), el (+0.38, +0.11) (deep lunge); the sweep passes under him at NDC (−0.09, −0.28) — inside the grass: the sweep reads as the burst of cut grass racing round the elder; 1897 sh (−0.08, +0.15), el (+0.42, +0.24); 1914 sh (−0.39, +0.18); 1920 sh (−0.40, +0.23), el (+0.47, +0.26). Horizon at +0.57, the ring's far side (19 m) tops at +0.55.

Action
- Shinobi: 1873–1879 two quick steps in to (0.05, 3.25), sword raised (attack prep); 1879 `M.jump(SHINOBI_rig, 1879, 1897, (0.05, 3.25), (0.05, 3.05), apex=0.55)` — a tuck vault: knees to the chest at 1885 (root z 0.55, feet ≈ 0.85–0.90 m = 0.45 m over the spear at 0.40 m; head centre 1.95), sword held up two-handed; lands 1897 in a crouch (head 1.35); back-hops 1899–1905 and 1906–1914 to (0.10, 1.15); stands 1920.
- Elder: 1873–1880 drops into a deep lunge (hips −0.35, head 1.25); `M.spear_sweep(SAINT_rig, 1880, kind="low", height=0.40)`: a 200° sweep from his right round the front to his left, tip compass 290 → **180 at 1885** → 90 at 1893, tip radius 2.9 m (grip 0.20 / 0.75); 1893–1897 recovers (head 1.55); 1905–1920 raises the spear, watching.
- Contacts: none (1885 miss: the spear passes ≈ 0.45 m under his feet). Tip rate ≈ 22°/f before 1885, ≈ 11°/f after.

Environment
- `ENV.set_sun(1873, 270, −2.0)`.
- (tune) `ENV.grass_effect("shear", dict(origin=(0.0, 5.8), radius=3.0, arc_deg=200, facing_deg=180, fluff=1200), 1880, 1890)` — the sweep mows the grass tops in a 200° fan in front of him (shear slot 2; S11 uses slot 1). The cut tips persist (a scar in front of the elder's S16–S17 position). Fallback: grass bursts only (below). VFX
```python
for k, (f, p) in enumerate(((1881, (-2.90, 5.70)), (1883, (-2.01, 3.71)), (1885, (0.05, 2.95)),
                             (1887, (1.10, 3.10)), (1889, (1.90, 3.70)))):   # tip bearings 268/224/180/158/136
    VFX.grass_burst(f, (p[0], p[1], 0.50), (0.3, -0.4, 0.8), count=50, speed=3.5, seed=190 + k)   # along the arc
VFX.dust_burst(1897, (0.05, 3.05, 0.0), radius=0.7, seed=196)               # landing
VFX.blade_trail("SAINT_spear_tip", "SAINT_spear_base", 1880, 1891, owner="saint")   # mostly hidden by grass
```
Events
```python
EV.emit(1875, "step", who="shinobi"); EV.emit(1878, "step", who="shinobi")
EV.emit(1879, "jump", who="shinobi")
EV.emit(1881, "whoosh", who="saint", weapon="spear", strength=1.0)
EV.emit(1882, "grass_shear", pos=(0.0, 3.0, 0.5), strength=0.6)        # the mown grass (keep even if the shear is off)
EV.emit(1897, "land", who="shinobi", strength=0.6)
EV.emit(1905, "step", who="shinobi"); EV.emit(1914, "step", who="shinobi")
```
Notes: the elevated camera is the one exception to the low-angle vocabulary in S16 — a low camera would hide the sweep entirely in the grass. The vault reads by the whole body rising (head 1.61 → 1.95, knees up); the feet stay just inside the grass tops (0.85–0.90 m) while the spear passes 0.45 m below them — the grass burst under him sells the pass.

### S17a — 1921–1947 (27 f) — three kunai
Purpose: out of reach, the student throws; the master is already spinning the spear into a wheel — the first kunai rings off it.

Camera (OTS over the shinobi's RIGHT shoulder, 1.75 m, near-locked; focus on the elder):
```python
C.shot("S17a", 1921, 1947,
       keys=[(1921, (0.95, -1.20, 1.75), (0.0, 5.50, 1.45), 40.0),
             (1947, (0.95, -1.10, 1.75), (0.0, 5.50, 1.45), 40.0)],
       dof=dict(fstop=2.8, focus=7.0), handheld=0.3, subjects=["shinobi", "saint"], framing="ots")
```
Screen: shinobi foreground (−0.48 → −0.51, −0.20 → −0.22) 176–183 % (right shoulder, head and the throwing arm on the left third, cropped by the frame bottom); elder centred (+0.01, +0.12 → +0.14) 63–65 %. Kunai 1 crosses the frame 1937 (−0.59, −0.15) → 1941 (−0.11, +0.16) → **1945 (+0.11, +0.07)** (deflect, in frame); kunai 2 leaves the hand 1943 at (−0.60, −0.25), (−0.26, −0.07) at 1947. Behind the elder the ring (13.7 m) fills y −0.35 … +0.40: he stands in front of a wall of flame; the spinning spear draws an orange disc over it.

Action
- Shinobi (0.10, 1.10) facing 180: 1921 left hand leaves the hilt (blend 4), 1925 to the sash, 1927 kunai in the left fist (`set_kunai_in_hand`), sword one-handed low at his right side; `M.throw_kunai(SHINOBI_rig, 1937, 1, …)`, `(…, 1943, 2, …)`, `(…, 1949, 3, …)`: left-hand overhand flicks, 6 f apart, releases at (−0.15, 1.45, 1.55); each release shows the free `SHINOBI_kunai_i` at the fist with the ballistic keys of the §3 table (8-f flights, 11.1–11.4 m/s); the in-hand kunai hides at 1949.
- Elder (0.00, 5.80): 1931 grip to the centre (1.00 / 1.60), 1935–1963 `M.spear_spin(SAINT_rig, 1935, 1963)` as a propeller wheel in front of him — spear in the vertical plane ⟂ the line (the XZ plane at y ≈ 5.15), hub at (0.00, 5.15, 1.40), 2.5 rev/s (≈ 37°/f), both hands at the centre.
- Contact: **1945** kunai 1 / spinning shaft at (0.35, 5.15, 1.55), s 0.6.

Environment: `ENV.set_sun(1921, 0, −2.0)` (glow + key from +Y: behind the elder). VFX
```python
VFX.blade_trail("SAINT_spear_tip", "SAINT_spear_base", 1935, 1963, owner="saint", fade=0.08)   # the orange wheel
VFX.sparks(1945, (0.35, 5.15, 1.55), direction=(0.6, -0.3, 0.7), count=45, speed=5.0, life=8, color="white",
           scale=0.8, seed=201)                                                               # kunai 1
# kunai 1 deflected: toss (0.35, 5.15, 1.55) -> (2.8, 4.2, 0.0), 1945 -> 1969, spin 18 rad/s (table above)
```
Events
```python
EV.emit(1921, "draw", who="shinobi", weapon="kunai", strength=0.3)
for f in (1937, 1943, 1949): EV.emit(f, "kunai_throw", who="shinobi")
EV.emit(1935, "spear_spin", who="saint", duration=28)
EV.emit(1945, "kunai_deflect", pos=(0.35, 5.15, 1.55), strength=0.6, tags=["kunai_deflect"])
```

### S17b — 1948–1968 (21 f) — the wheel
Purpose: the second and third kunai spark off the wheel; the spin stops, the spear rises overhead — he is coming.

Camera (low medium single on the elder, 1.15 m, looking up 6°, handheld):
```python
C.shot("S17b", 1948, 1968,
       keys=[(1948, (3.30, 4.40, 1.15), (0.0, 5.40, 1.50), 45.0),
             (1968, (3.30, 4.50, 1.15), (0.0, 5.50, 1.55), 45.0)],
       dof=dict(fstop=2.8, focus=3.6), handheld=0.4, shake=[(1951, 0.3, 4), (1957, 0.35, 5)],
       subjects=["saint"], framing="medium")
```
Screen: elder (+0.27, +0.18) → (+0.20, +0.08) 148 % (knees-up medium); single-character check: he faces −Y → projects screen-LEFT ✓ (the kunai arrive from the left: kunai 3 enters at 1955 (−0.92, +0.62)). Contacts **1951 (−0.23, −0.52)**, **1957 (−0.19, +0.44)**. Kunai 2 deflected falls through (−0.18, −0.26) → (−0.12, −0.81) 1955–1963; kunai 3 flies up out of the top 1959. Fire tops at −0.11 … −0.19: the flames low behind his legs, torso + wheel against the smoke and crimson sky.

Action
- Elder: the wheel continues; deflects kunai 2 (1951) and kunai 3 (1957); 1957–1963 the spin decelerates (37 → 0°/f) and stops with the spear raised overhead in both hands, tip forward-up (grip slides to 0.20 / 0.75 by 1975); 1963–1968 weight shifts forward (hips −0.05, chest forward 10°): the charge is coming.
- Contacts: **1951** kunai 2 (−0.30, 5.15, 1.20) s 0.6; **1957** kunai 3 (0.10, 5.15, 1.75) s 0.65.

Environment: `ENV.set_sun(1948, 270, −2.0)`. VFX
```python
VFX.sparks(1951, (-0.30, 5.15, 1.20), direction=(-0.7, -0.2, 0.5), count=45, speed=5.0, life=8, color="white",
           scale=0.8, seed=202)
VFX.sparks(1957, (0.10, 5.15, 1.75), direction=(0.1, -0.2, 1.0), count=50, speed=5.0, life=9, color="white",
           scale=0.9, seed=203)
# tosses: kunai 2 (-0.30, 5.15, 1.20) -> (-3.1, 6.2, 0.0) 1951 -> 1969; kunai 3 (0.10, 5.15, 1.75) -> (0.8, 8.0, 0.0)
# 1957 -> 1985 (table above); CONSTANT on the landing frames, hidden in the grass afterwards
```
Events
```python
EV.emit(1951, "kunai_deflect", pos=(-0.30, 5.15, 1.20), strength=0.6, tags=["kunai_deflect"])
EV.emit(1957, "kunai_deflect", pos=(0.10, 5.15, 1.75), strength=0.7, tags=["kunai_deflect"])
EV.emit(1961, "whoosh", who="saint", weapon="spear", strength=0.6)          # the last turn of the wheel
```
Notes: three `kunai_deflect` events at 1945 / 1951 / 1957 = DIRECTION §8's "kunai_deflect ×3" (events.REQUIRED_BEATS checks 1951 ± 12). The half-beat spacing (6 f) is the only sub-12-f contact spacing in the lane — the sparks are small and local (no flash).

### S17c — 1969–2004 (36 f) — the charge and the leap
Purpose: the old man charges and leaps — a big, heavy body in the air, spear raised against the crimson sky.

Camera (ground-level low angle, 0.90 m, tilting up with the leap, strong handheld):
```python
C.shot("S17c", 1969, 2004,
       keys=[(1969, (4.50, 1.20, 0.90), (0.0, 4.80, 1.35), 28.0),
             (2004, (4.40, 1.40, 0.90), (0.0, 4.10, 1.75), 28.0)],
       dof=dict(fstop=4.0, distance_keys=[(1969, 6.5), (2004, 5.3)]), handheld=0.7,
       shake=[(1981, 0.2, 4), (1993, 0.25, 4), (1999, 0.3, 5)], subjects=["saint"], framing="wide")
```
Screen: elder (+0.19, +0.12) 50 % at 1969 → (+0.17, 0.00) at 1985 → (+0.11, −0.14) crouched at the take-off 1999 → (+0.01, +0.07) 71 % at 2004, rising, spear overhead toward the frame top. The shinobi is off-screen left (x −1.1 … −1.3) — the 180 rule holds (he is left of the elder). Fire tops +0.04 → −0.27 as the camera tilts up: the elder rises out of the fire band into smoke and sky.

Action
- Elder: 1969–1975 menace hold (spear overhead, two hands, grip 0.20 / 0.75); strides 1975–1999 from (0.00, 5.80) to (0.00, 4.60), foot plants 1981 and 1993 (beats), gather step 1997; take-off 1999: `M.jump(SAINT_rig, 1999, 2017, (0.00, 4.60), (0.00, 3.00), apex=0.55)` with the spear swung back over his head (head of the spear behind him, pointing up-back) — the wind-up of the slam.
- Shinobi (off-screen): at (0.10, 1.10); starts his roll at 2003 (seen in S17d).

VFX
```python
VFX.dust_burst(1981, (0.00, 5.30, 0.0), radius=0.5, seed=211)
VFX.dust_burst(1993, (0.00, 4.80, 0.0), radius=0.5, seed=212)
VFX.dust_burst(1999, (0.00, 4.60, 0.0), radius=0.8, seed=213)
VFX.grass_burst(1999, (0.00, 4.60, 0.30), (0.0, 0.3, 1.0), count=70, seed=214)
```
Events
```python
EV.emit(1981, "step", who="saint", strength=0.9); EV.emit(1993, "step", who="saint", strength=0.9)
EV.emit(1999, "jump", who="saint")
EV.emit(2002, "whoosh", who="saint", weapon="spear", strength=0.5)
```
Notes: camera clearance default: the elder is 5.3–6.5 m away (grass line on him ≈ 1.10–1.14 m) — only the charging torso and the airborne body read; the legs are in the grass until the leap lifts them out.

### S17d — 2005–2020 (16 f) — the slam
Purpose: the leap comes down; the spear smashes the ground where the student stood — fire and dust erupt between us and him. He rolled clear (perpendicular to the line), but the eruption hides it for a moment.

Camera (wide profile, 1.70 m, locked; heavy impact shake):
```python
C.shot("S17d", 2005, 2020,
       keys=[(2005, (8.30, 1.60, 1.70), (-0.30, 2.00, 1.20), 28.0),
             (2020, (8.30, 1.60, 1.70), (-0.30, 1.90, 1.10), 28.0)],
       dof=None, shake=[(2017, 0.8, 10)], subjects=["shinobi", "saint"], framing="wide")
```
| frame | shinobi head NDC / fig | elder head NDC / fig | note |
|---|---|---|---|
| 2005 | (−0.16, −0.03) 27 % | (+0.39, +0.31) 44 % | elder airborne, high in frame |
| 2008 | (−0.15, −0.11) 21 % | (+0.34, +0.39) 48 % | apex |
| 2011 | (−0.14, −0.19) 15 % (mid-roll, head 0.65: mostly in the grass) | (+0.29, +0.29) 43 % | spear coming over |
| 2017 | (−0.11, −0.02) 19 % (on one knee, 10 m from the lens, beyond the impact) | (+0.20, +0.08) 31 % | IMPACT at NDC (−0.17, −0.48), depth 8.3 m |
| 2020 | (−0.11, +0.02) 21 % | (+0.21, +0.10) 32 % | cut 3 f after the impact |
180 rule OK throughout. Fire tops +0.31..+0.35 (the far ring at 19.3 m).

Action
- Elder: 2005–2017 descends from the apex, `M.spear_slam(SAINT_rig, 2017)`: the spear swings over and down (grip 0.20 / 0.75), blade and shaft strike **flat along the line** at IMPACT (0.10, 1.00, 0.05) (blade head y 0.85–1.15) as his feet land at (0.00, 3.00) (deep knee bend, head 1.30); 2017–2020 the spear rebounds 0.15–0.25 m (D4).
- Shinobi: `M.roll(SHINOBI_rig, 2003, 2019, (0.00, 1.10), (−1.90, 1.25))` to his left (−X), perpendicular to the line, away from the lens; facing 180 → 133 (toward the elder) by 2019, ending on one knee (local `kneel_guard`, §5), sword two-handed, point at the elder.

VFX (the eruption — every piece ramps ≥ 6 f, no white flash)
```python
VFX.shockwave(2017, IMPACT, radius=3.5, seed=221)
VFX.dust_burst(2017, IMPACT, radius=2.2, density=7.0, seed=222)
VFX.sparks(2017, (0.10, 1.05, 0.10), direction=(0, 0, 1), count=90, speed=5.0, life=14, color="fire", scale=1.6,
           seed=223)                                                           # the blade on stones (heavy)
VFX.fire_ring(2017, (0.10, 1.00, 0.0), radius=1.3, grow_frames=6, height=1.6, count=60, lights=False, smoke=False,
              ember_rate=60.0, ground_glow=True, extinguish=False, f_out=2035, f_end=2060, seed=224)   # fire erupts
VFX.embers(2017, 2040, IMPACT, 1.5, rate=80.0, rise=2.0, seed=225)
VFX.grass_burst(2017, (0.10, 1.00, 0.30), (0.0, 0.0, 1.0), count=160, speed=5.0, seed=226)
VFX.dust_burst(2011, (-1.00, 1.15, 0.0), radius=0.7, seed=227)               # the roll
```
Events
```python
EV.emit(2003, "roll", who="shinobi")
EV.emit(2012, "whoosh", who="saint", weapon="spear", strength=1.0)
EV.emit(2017, "land", who="saint", strength=1.0)
EV.emit(2017, "fire_burst", pos=IMPACT, strength=1.0, tags=["slam"])
EV.emit(2019, "shockwave", pos=IMPACT, strength=0.6)
```
Notes: the dust volume (radius 2.2, rising 1.1 × r) stands between the lens and the kneeling shinobi 2017–2030: he is a shape behind the dust (D10). The fire burst ramps over 7 f (fire_ring: max(7 f, 0.8 × 6 f)); its 60 tongues use no lights (the sparks' 64 W light is the only local lift, 3 f, cutoff 8 m).

### S17e — 2021–2064 (44 f) — out of the dust
Purpose: the dust clears: he is alive, on one knee; he rises and they reset — the fight will come to close quarters.

Camera (medium-wide, 1.40 m, slow drift following his return to the line):
```python
C.shot("S17e", 2021, 2064,
       keys=[(2021, (6.50, 0.20, 1.40), (-0.80, 1.90, 1.30), 35.0),
             (2064, (6.20, -0.60, 1.40), (-0.20, 0.70, 1.40), 35.0)],
       dof=dict(fstop=4.0, distance_keys=[(2021, 8.5), (2064, 6.5)]), handheld=0.3,
       subjects=["shinobi", "saint"], framing="medium")
```
Screen: 2021 sh (−0.20, −0.12) 32 % (one knee, head just above the grass line y −0.15, behind the settling dust), el (+0.35, +0.04) 49 %; 2037 sh (−0.14, +0.11) 44 % (standing), el (+0.44, +0.19); 2050 sh (−0.30, +0.10), el (+0.51, +0.19); 2064 sh (−0.49, +0.11) 60 %, el (+0.44, +0.17) 61 %. 180 rule OK. Fire tops +0.21..+0.27.

Action
- Shinobi: holds `kneel_guard` at (−1.90, 1.25) to 2030; rises 2030–2037; circles back 2037–2060 (side-steps 2041, 2047, 2053; facing 135 → 176) to (−0.30, −0.90); chudan by 2064.
- Elder: 2020–2035 straightens, lifts the spear out of the rebound into a high guard (never pulled from the ground); turns to face him (facing 360 → 330 at 2035 → 313 at 2045); two steps forward 2048, 2058 → (0.00, 2.20), facing 352 by 2060; wide staff grip (0.50 / 1.40) by 2060.
- The IMPACT fire patch shrinks from 2035 and is out by 2055; smoke and embers drift across.

VFX: none new (the S17d effects play out). Events
```python
for f in (2041, 2047, 2053): EV.emit(f, "step", who="shinobi")
EV.emit(2048, "step", who="saint"); EV.emit(2058, "step", who="saint")
```

### S18a — 2065–2091 (27 f) — under the spear
Purpose: the student's answer to reach: he slides under a thrust and comes up inside it, cutting.

Camera (handheld tracking alongside at 1.35 m, 2.6–2.95 m from him, moving +1.9 m in Y with the slide):
```python
C.shot("S18a", 2065, 2091,
       keys=[(2065, (2.60, -1.40, 1.35), (-0.20, 0.30, 1.30), 35.0),
             (2091, (2.40, 0.50, 1.35), (-0.05, 1.60, 1.35), 35.0)],
       dof=dict(fstop=2.8, distance_keys=[(2065, 2.95), (2077, 2.80), (2085, 2.70), (2091, 2.58)]),
       handheld=0.8, shake=[(2089, 0.4, 5)], subjects=["shinobi", "saint"], framing="medium")
```
| frame | shinobi head NDC / fig | elder head NDC / fig | note |
|---|---|---|---|
| 2065 | (−0.72, +0.38) 136 % | (+0.82, +0.40) 99 % | sprint starts |
| 2077 | (−0.48, −0.35) 102 % (dropping into the slide) | (+0.70, +0.37) 111 % | the thrust passes over him at NDC (−0.17, +0.54) |
| 2085 | (−0.27, −0.59) 95 % (head 1.00, end of the slide) | (+0.49, +0.41) 130 % | |
| 2089 | (−0.35, +0.18) 140 % (rising cut) | (+0.42, +0.42) 137 % | contact at NDC (+0.15, +0.01) |
180 rule OK. The shinobi stays inside the camera's clearance ramp (2.6–2.95 m: grass scaled to 0.44–0.58), so the knee-slide is visible although his head drops to 0.95–1.00 m. Fire tops +0.29..+0.34 (ring at 13.6–14.7 m).

Action
- Shinobi: 2065–2073 sprint (−0.30, −0.90) → (−0.25, −0.35); 2073–2085 local `knee_slide` (§5): drops onto the left shin, torso leaning back 35°, sword two-handed across his chest edge-up, slides 1.4 m to (−0.15, 1.05) (head 0.95–1.00); 2085–2089 surges up out of the slide into `M.slash(SHINOBI_rig, 2089, "rising_R")`.
- Elder (0.00, 2.25): 2071–2077 `M.spear_thrust(SAINT_rig, 2077)` at head height (tip to (0.20, 0.45, 1.55)) — it passes over the sliding shinobi (miss); 2077–2089 retracts, choking up to the staff grip (0.50 / 1.40), the shaft across his body at chest height, and blocks the rising cut.
- Contact: **2089** sword/shaft (0.15, 1.70, 1.35) s 0.8 (shinobi-initiated → white).

Environment: `ENV.set_sun(2065, 270, −2.0)`. VFX
```python
VFX.grass_burst(2075, (-0.22, 0.00, 0.30), (0.0, 1.0, 0.6), count=70, seed=231)       # the slide ploughs the grass
VFX.grass_burst(2081, (-0.18, 0.70, 0.30), (0.0, 1.0, 0.6), count=60, seed=232)
VFX.dust_burst(2079, (-0.20, 0.40, 0.0), radius=0.7, seed=233)
VFX.blade_trail("SAINT_spear_tip", "SAINT_spear_base", 2072, 2077, owner="saint")
VFX.blade_trail("SHINOBI_katana_tip", "SHINOBI_katana_base", 2085, 2089, owner="shinobi")
```
Events
```python
EV.emit(2065, "dash", who="shinobi")
EV.emit(2073, "skid", who="shinobi", duration=12)
EV.emit(2075, "whoosh", who="saint", weapon="spear", strength=0.9)
EV.emit(2087, "whoosh", who="shinobi", weapon="katana", strength=0.8)
# clash 2089 via M.clash (0.8)
```

### S18b — 2092–2115 (24 f) — he presses (over his shoulder)
Purpose: inside the reach the sword is faster than the spear: two cuts, both caught on the shaft.

Camera (handheld OTS over the shinobi's RIGHT shoulder, 1.70 m):
```python
C.shot("S18b", 2092, 2115,
       keys=[(2092, (1.20, -0.60, 1.70), (0.0, 2.20, 1.50), 40.0),
             (2115, (1.25, -0.50, 1.70), (0.0, 2.20, 1.50), 40.0)],
       dof=dict(fstop=2.8, focus=3.05), handheld=0.8, shake=[(2101, 0.35, 5), (2113, 0.4, 5)],
       subjects=["shinobi", "saint"], framing="ots")
```
Screen: shinobi foreground-left (−0.55 → −0.31, −0.25 → −0.16) 188–201 %; elder centred (+0.01..+0.02, +0.20) 143–146 %. Contacts **2101 (−0.09, +0.04)**, **2113 (−0.04, −0.60)**. Fire tops at +0.54 behind the elder's head. 180 rule OK.

Action
- Shinobi: 2095–2101 `M.slash(SHINOBI_rig, 2101, "diag_down_L")`; 2107–2113 `M.slash(SHINOBI_rig, 2113, "horizontal_R")` low at the hip; steps (−0.12, 1.10) → (−0.05, 1.15) → (0.15, 1.20) (pressing, drifting right).
- Elder (0.00, 2.25), staff grip: 2101 blocks with the shaft diagonal (hands wide), 2113 with the shaft vertical on his left side (butt down) — local `staff_block_diag` / `staff_block_vert` (§5).
- Contacts: **2101** sword/shaft (0.10, 1.72, 1.55) s 0.7; **2113** sword/shaft (0.18, 1.70, 1.25) s 0.75 (white).

Environment: `ENV.set_sun(2092, 0, −2.0)` (glow behind the elder, +Y). VFX
```python
VFX.blade_trail("SHINOBI_katana_tip", "SHINOBI_katana_base", 2096, 2101, owner="shinobi")
VFX.blade_trail("SHINOBI_katana_tip", "SHINOBI_katana_base", 2108, 2113, owner="shinobi")
```
Events: `EV.emit(2097, "whoosh", who="shinobi", weapon="katana", strength=0.7)`; `EV.emit(2109, "whoosh", who="shinobi", weapon="katana", strength=0.75)`; clashes 2101 / 2113 via `M.clash`.

### S18c — 2116–2139 (24 f) — the staff answers (over his shoulder)
Purpose: the old man turns the spear into a staff: butt, then head — the student is now the one blocking.

Camera (handheld OTS over the elder's LEFT shoulder, 1.80 m):
```python
C.shot("S18c", 2116, 2139,
       keys=[(2116, (1.00, 3.60, 1.80), (0.10, 1.00, 1.45), 45.0),
             (2139, (1.05, 3.55, 1.80), (0.10, 1.00, 1.45), 45.0)],
       dof=dict(fstop=2.8, focus=2.6), handheld=0.8, shake=[(2125, 0.4, 5), (2137, 0.45, 6)],
       subjects=["shinobi", "saint"], framing="ots")
```
Screen: elder foreground-right (+0.78 → +0.83, +0.03..+0.05) 282 % (shoulder and head, soft); shinobi centred (0.00, +0.07..+0.11) 168–172 %. Contacts **2125 (+0.30, −0.34)**, **2137 (+0.17, +0.18)**. The ring's −Y arc (13.3 m) fills the whole background behind the shinobi (fire tops +0.93). 180 rule OK.

Action
- Elder: 2119–2125 local `staff_butt_strike` (§5): the butt end swings up from his right hip at the shinobi's head; 2131–2137 the head swings round in a short diagonal chop (`M.slash`-like, local `staff_head_chop`).
- Shinobi (0.15, 1.20 → 1.10): 2125 `M.deflect(SHINOBI_rig, 2125, "high")` (blade vertical), 2137 `M.deflect(SHINOBI_rig, 2137, "mid_R")`; yields 0.1 m.
- Contacts: **2125** butt/sword (0.05, 1.65, 1.40) s 0.75; **2137** spear head/sword (0.20, 1.68, 1.60) s 0.85 (elder-initiated → fire sparks).

Environment: `ENV.set_sun(2116, 180, −2.0)` (glow behind the shinobi, −Y). VFX
```python
VFX.blade_trail("SAINT_spear_tip", "SAINT_spear_base", 2131, 2137, owner="saint")
```
Events: `EV.emit(2121, "whoosh", who="saint", weapon="spear", strength=0.7)`; `EV.emit(2133, "whoosh", who="saint", weapon="spear", strength=0.8)`; clashes via `M.clash`.

### S18d — 2140–2172 (33 f) — the bind, and the kick (contact on the cut)
Purpose: the student's overhead cut is trapped on the shaft; they grind; the master throws the blade up and his foot comes — the contact itself is never shown.

Camera (handheld medium profile, 1.40 m):
```python
C.shot("S18d", 2140, 2172,
       keys=[(2140, (3.20, 1.60, 1.40), (0.05, 1.70, 1.35), 40.0),
             (2172, (3.10, 1.50, 1.40), (0.05, 1.70, 1.35), 40.0)],
       dof=dict(fstop=4.0, focus=3.1), handheld=0.6, shake=[(2149, 0.3, 4)],
       subjects=["shinobi", "saint"], framing="medium")
```
Screen: sh (−0.42 … −0.37, +0.26 … +0.35) 139–148 %; el (+0.38 … +0.42, +0.41 … +0.52) 140–147 %; the bind point at NDC (0.00, +0.17). Fire tops +0.38. 180 rule OK.

Action
- Shinobi: 2140–2149 `M.slash(SHINOBI_rig, 2149, "overhead")` (a big two-handed wind-up 2140–2145); 2149–2158 `M.blade_lock(SHINOBI_rig, SAINT_rig, 2149, 2158)` — pressing down, his blade sliding 0.25 m along the shaft toward the elder's left hand; 2158–2161 his sword is thrown up and right (arms high, torso open); 2161–2172 trying to recover.
- Elder: 2147–2158 holds the shaft horizontal above his head (both hands wide); 2158–2161 heaves it up and to his right; 2161–2172 `M.kick(SAINT_rig, 2173)` — the right knee chambers to 1.0 m (2163–2168), the foot drives toward the shinobi's sternum; at **2172 the sole is 0.10 m from his chest**. CUT.
- Contacts: **2149** sword/shaft (0.10, 1.70, 1.45) s 0.6 (clash, beat 43) then grinding to 2158 (lock); kick at 2173 = hidden.

Environment: `ENV.set_sun(2140, 270, −2.0)`. VFX
```python
VFX.sparks(2152, (0.08, 1.72, 1.47), direction=(0, 0, 1), count=15, speed=2.0, life=6, color="white", scale=0.5,
           light=False, seed=241)                                              # the grind
VFX.sparks(2156, (0.00, 1.74, 1.47), direction=(0, 0, 1), count=15, speed=2.0, life=6, color="white", scale=0.5,
           light=False, seed=242)
```
Events
```python
EV.emit(2140, "whoosh", who="shinobi", weapon="katana", strength=0.8)
# clash 2149 via M.clash (0.6)
EV.emit(2149, "blade_lock", duration=9, pos=(0.10, 1.70, 1.45))
EV.emit(2159, "whoosh", who="saint", weapon="spear", strength=0.5)            # the heave
EV.emit(2166, "whoosh", who="saint", weapon="body", strength=0.7)             # the kick
EV.emit(2173, "kick", pos=(0.15, 1.33, 1.25), strength=1.0, tags=["kick"])     # contact frame = first frame of S18e
```
Notes: DIRECTION §2 "hide every body contact on a cut": S18d's last frame is the foot 10 cm short; S18e's first frame already has him folded and airborne. Key the elder's kicking leg CONSTANT at 2172 and set the 2173 pose (leg extended, foot at the contact point's former position) so motion blur does not smear the foot across the cut.

### S18e — 2173–2208 (36 f) — kicked back, the blade in the dirt
Purpose: the kick throws him back screen-left; he stops himself by dragging the sword through the dirt.

Camera (low wide, 1.20 m, panning/dollying left with the skid; impact shake on the first frame):
```python
C.shot("S18e", 2173, 2208,
       keys=[(2173, (7.80, -1.60, 1.20), (0.0, -1.20, 1.00), 24.0),
             (2208, (7.60, -2.80, 1.20), (0.0, -2.40, 1.00), 24.0)],
       dof=None, handheld=0.3, shake=[(2173, 0.6, 8)], subjects=["shinobi", "saint"], framing="wide")
```
Screen: 2173 sh (+0.40, +0.20) 33 % (folded, leaving the ground), el (+0.58, +0.25); 2180 sh (+0.13, +0.16); 2190 sh (−0.05, +0.11); 2204 sh (−0.31, +0.04) 25 % (stopped, crouched), el (+0.86, +0.28) 36 %. He travels screen-LEFT +0.40 → −0.31 (DIRECTION §1: knockbacks carry the shinobi screen-left) ✓; 180 rule OK. Fire tops +0.25.

Action
- Shinobi: 2173–2180 airborne backwards (root z to 0.25 m) from (0.15, 1.10) to (0.10, −0.60), torso folded 30°, arms flung back, left hand off the hilt; 2180 feet touch; 2180–2204 local `skid_sword_drag` (§5): crouched low, left hand trailing on the ground, right hand driving the sword tip into the dirt in front-right of his right foot (tip ≈ root + (+0.55, +0.40, 0.02): the blade drags like an anchor on the side he is being pushed away from) — `M.skid(SHINOBI_rig, 2180, 2204, (0.10, −0.60), (0.00, −4.10))`, decelerating (ease-out); stops at 2204 (head 1.10), facing 180 throughout.
- Elder: 2173–2181 recovers the kicking leg; 2185–2221 two measured steps back (2197 → (0.00, 2.65), 2221 → (0.00, 3.00)), spear held low. VFX
```python
for k, f in enumerate(range(2182, 2203, 3)):                                   # steel dragging through stones
    u = (f - 2180) / 24.0
    y = -0.20 - 3.50 * (1 - (1 - u) ** 2)                                        # tip = root (ease-out) + 0.40
    VFX.sparks(f, (0.55, y, 0.03), direction=(0.2, 0.8, 0.6), count=10, speed=2.5, life=6, color="white",
               scale=0.5, light=(k in (0, 3)), seed=250 + k)
    VFX.grass_burst(f, (0.45, y, 0.25), (0.1, -0.6, 0.8), count=30, speed=2.5, seed=260 + k)   # dirt + grass spray
VFX.dust_burst(2180, (0.10, -0.60, 0.0), radius=0.6, seed=270)
VFX.dust_burst(2204, (0.00, -4.10, 0.0), radius=0.8, seed=271)
```
Events
```python
EV.emit(2180, "land", who="shinobi", strength=0.7)
EV.emit(2180, "skid", who="shinobi", duration=24, tags=["blade"])             # the sword-drag scrape
EV.emit(2197, "step", who="saint")
```

### S18f — 2209–2256 (48 f) — the breath before the throw
Purpose: 7 m apart again, framed by the ring: he rises; the master shifts the spear into a javelin grip — the audience sees the throw coming.

Camera (low wide profile, 1.35 m, near-locked creep):
```python
C.shot("S18f", 2209, 2256,
       keys=[(2209, (7.90, -0.55, 1.35), (0.0, -0.50, 1.35), 24.0),
             (2256, (7.80, -0.45, 1.35), (0.0, -0.45, 1.40), 24.0)],
       dof=None, handheld=0.15, subjects=["shinobi", "saint"], framing="wide")
```
Screen: sh (−0.61, −0.10 → +0.05) 24 → 33 % (rising), el (+0.56 … +0.59, +0.10 … +0.14) 36 %. Two silhouettes 7.1 m apart, the far ring (18.7 m) tops at +0.12..+0.14 behind both. 180 rule OK.

Action
- Shinobi (0.00, −4.10): rises 2209–2225 (head 1.10 → 1.55), two-handed again at 2215 (blend 4), chudan by 2225, still to 2256 (breathing).
- Elder: 2209–2221 second step back to (0.00, 3.00); 2225–2236 lets the shaft slide through his hands to the centre-of-mass grip (1.30); 2240 the left hand leaves; 2240–2256 raises the spear to the right shoulder, the local pose `javelin_ready` (§5): the tip aimed at the shinobi, left arm extended toward him. Events: `EV.emit(2221, "step", who="saint")`; `EV.emit(2230, "whoosh", who="saint", weapon="spear", strength=0.2)`.

### S19a — 2257–2276 (20 f) — the javelin
Purpose: the master hurls the spear like a javelin — everything he has, at the student's chest.

Camera (low medium single on the elder, 1.05 m, looking up 15° against the sky; slight follow):
```python
C.shot("S19a", 2257, 2276,
       keys=[(2257, (2.60, 3.80, 1.05), (0.0, 2.70, 1.80), 35.0),
             (2276, (2.60, 3.60, 1.05), (0.0, 2.40, 1.80), 35.0)],
       dof=dict(fstop=2.8, focus=2.8), handheld=0.4, shake=[(2269, 0.3, 5)], subjects=["saint"], framing="medium")
```
Screen: elder (+0.19, −0.18) → **(+0.07, −0.29) at the release** → (+0.11, −0.23), 157–168 % (belt-up, low angle); release point REL (−0.25, 2.05, 1.95) (right hand, high) at NDC (−0.17, +0.06); the spear then crosses the frame 2270 (−0.40, +0.06) → 2271 (−0.61, +0.04) → 2272 (−0.80, 0.00) → 2273 (−0.98, −0.06) and exits LEFT at 2274 (toward the shinobi) ✓. Single-character check: the elder faces −Y → projects screen-LEFT ✓. Background: crimson sky and smoke (the ring is below frame, tops −0.82).

Action
- Elder: 2257–2263 cocks (weight onto the right/back foot, right arm back with the spear at the centre of mass, left arm extended at the target); 2263–2269 steps with the left foot to (0.00, 2.60) and throws — `M.spear_throw(SAINT_rig, 2269)`; release at REL (−0.25, 2.05, 1.95) (2269): `CH.set_weapon_state(SAINT_rig, 2269, 'world')`, `CH.snap_free("SAINT_spear_world", 2269)`, then the javelin keys (§3 table: v0 (+0.78, −11.58, +1.28) m/s, tip forward); 2269–2276 follow-through (right arm across the body, torso rotated 35°); `CH.set_arm_mode(SAINT_rig, 2272, 'fk', blend=4)`. Environment: `ENV.set_sun(2257, 270, −2.0)`. VFX: `VFX.blade_trail("SAINT_spear_tip", "SAINT_spear_base", 2265, 2269, owner="saint")` (the hand-held spear's last arc; the flying `SAINT_spear_world` has no sockets — motion blur carries the flight). Events: `EV.emit(2266, "step", who="saint", strength=0.8)`; `EV.emit(2266, "whoosh", who="saint", weapon="spear", strength=1.0)`.

### S19b — 2277–2304 (28 f) — the deflect (slow motion 2280–2304)
Purpose: the spear arrives; the student's blade meets it and sends it spinning up — sparks hang in the air.

Camera (medium close-up from the shinobi's right-rear 3/4, 1.35 m, locked with a slight push; the spear enters from the upper right):
```python
C.shot("S19b", 2277, 2304,
       keys=[(2277, (1.90, -5.20, 1.35), (0.0, -3.50, 1.45), 50.0),
             (2304, (1.85, -5.10, 1.35), (0.0, -3.50, 1.50), 50.0)],
       dof=dict(fstop=2.0, focus=2.5), handheld=0.0, shake=[(2281, 0.3, 6)], subjects=["shinobi"], framing="mcu")
```
Screen: shinobi (−0.58, +0.21) → (−0.67, +0.15), 252–274 % (right shoulder, head, arms, sword); single-character check: he faces +Y → projects screen-RIGHT ✓ (the elder is off-screen right at x +1.9, where the spear comes from). The javelin: 2277 (+0.95, +0.60) → 2278 (+0.77, +0.51) → 2279 (+0.55, +0.36) → 2280 (+0.27, +0.12) → **2281 contact (+0.13, 0.00)** at 2.5 m; the deflected spear rises to (−0.14, +0.72) by 2284 and leaves the top of frame ≈ 2286 (slow motion). Fire tops +0.09 → −0.05 (ring at 16 m behind).

Action (keyed at real speed to 2280, then at 0.4× — the 24 frames 2280–2304 hold 9.6 frames of motion; the fx clock does the same for sparks, embers, fire, trails and the tails' springs):
- Shinobi (0.00, −4.10), two-handed: 2277–2281 `M.deflect(SHINOBI_rig, 2281, "mid_R")` played as a rising diagonal from his right: the blade meets the shaft just behind the spear head at DEF (0.12, −3.45, 1.45), knocking it up and over his left side; 2281–2304 the follow-through continues up-left in slow motion; hachimaki tails lift slowly.
- Spear: `SAINT_spear_world` deflected (§3 table: v0 (−5.98, −1.51, +6.39), end-over-end 1.2 rev/s on the fx clock), keyed per frame with t = fx_time(f) − fx_time(2281).
- Contact: **2281** sword/spear (DEF) s 0.9, heavy. VFX
```python
M.clash(SAINT_rig, SHINOBI_rig, 2281, DEF, strength=0.9)          # emits the clash (use kind='clash_heavy' if supported)
VFX.sparks(2281, DEF, direction=(-0.3, 0.2, 1.0), count=120, speed=4.5, life=14, color="fire", scale=1.4,
           seed=281)   # extra hanging sparks: fx speed 0.4 -> they hang ~2.5x longer on screen
VFX.blade_trail("SHINOBI_katana_tip", "SHINOBI_katana_base", 2277, 2292, owner="shinobi")   # the trail hangs
```
Events
```python
EV.emit(2280, "slowmo", duration=24)
# the clash at 2281 comes from M.clash; if it only emits "clash", add:
EV.emit(2281, "clash_heavy", pos=DEF, strength=0.9)
EV.emit(2286, "spear_spin", pos=(-0.5, -3.6, 2.1), duration=43)      # the whirr of the tumbling spear 2286-2329
```
Notes: slow motion only inside `config.SLOWMO[2]` (2280–2304) and framed on the effect (sparks, blade, spear) — no full-body mechanics (DIRECTION §4). Real time resumes on the cut at 2305 exactly when the window ends.

### S19c — 2305–2352 (48 f) — into the flames
Purpose: the spear cartwheels over the arena and drops into the wall of fire; the master is empty-handed.

Camera (low wide from the −Y/+X quadrant, 1.30 m; a small pan with the falling spear, then settle):
```python
C.shot("S19c", 2305, 2352,
       keys=[(2305, (6.00, -4.00, 1.30), (-2.0, -1.00, 2.00), 24.0),
             (2329, (6.00, -4.00, 1.30), (-2.4, -1.40, 1.80), 24.0),
             (2352, (6.00, -3.80, 1.30), (-2.0, -0.80, 1.70), 24.0)],
       dof=None, handheld=0.2, subjects=["shinobi", "saint"], framing="wide")
```
Screen: sh (−0.54, −0.13) 47 % → (−0.44, −0.05) at 2329 → (−0.58, 0.00); el (+0.68, −0.11) 36 % → (+0.79, −0.02) → (+0.71, +0.02). The spear: 2305 (−0.50, +0.57) → apex ≈ 2310 (−0.55, +0.57, 3.5 m high) → 2320 (−0.56, +0.27) → **2329 lands in the flames at SPEAR_LAND, NDC (−0.58, −0.34)**, 13.2 m away — a parabola down into the far-left fire behind the shinobi. 180 rule OK. Fire tops −0.10 … +0.01 (the far ring behind both at 18 m).

Action
- Shinobi (0.00, −4.10): 2304–2310 finishes the follow-through; 2310–2330 turns his head up-left following the spear; 2335–2345 back to the elder, settles into chudan.
- Elder (0.00, 2.55): watches it go, empty right hand open; steps back 2333, 2341 → (0.00, 3.00); 2345–2352 the right hand rises to the katana hilt, left thumb on the tsuba (no click — the click motif is reserved for 566/3150/3412).
- Spear: lands **2329** (beat 58) at SPEAR_LAND (−8.40, −5.60, 0.60), blade end down, shaft tilted 25°, half in the flames; keyed static (CONSTANT) to 2400. VFX
```python
VFX.sparks(2329, SPEAR_LAND, direction=(0, 0, 1), count=50, speed=3.0, life=16, color="fire", scale=1.0, seed=291)
VFX.embers(2329, 2350, SPEAR_LAND, 1.0, rate=120.0, rise=2.5, seed=292)
VFX.fire_ring(2329, (-8.40, -5.60, 0.0), radius=0.9, grow_frames=6, height=2.4, count=40, lights=False, smoke=False,
              extinguish=False, f_out=2345, f_end=2370, seed=293)                       # the flare as it drops in
```
Events: `EV.emit(2329, "fire_burst", pos=SPEAR_LAND, strength=0.7)`; `EV.emit(2333, "step", who="saint")`; `EV.emit(2341, "step", who="saint")`.

### S19d — 2353–2400 (48 f) — thunder; the sword comes out again
Purpose: the first thunder; the master draws his katana — Act II's weapon is gone, Act III's is in his hands; the first drops hiss on the steel.

Camera (low medium single on the elder, 1.10 m, creeping in and tilting up 9 → 11°):
```python
C.shot("S19d", 2353, 2400,
       keys=[(2353, (2.80, 2.00, 1.10), (0.0, 3.00, 1.55), 45.0),
             (2400, (2.70, 2.10, 1.10), (0.0, 3.00, 1.65), 45.0)],
       dof=dict(fstop=2.8, distance_keys=[(2353, 3.05), (2380, 2.95), (2390, 2.80)]),   # hilt -> blade
       handheld=0.25, subjects=["saint"], framing="medium")
```
Screen: elder (0.00, +0.32) → (0.00, +0.10), 190–202 % (belt-up); he faces −Y → projects screen-LEFT ✓. The ring low behind his hips (tops −0.40 → −0.64); above him the sky turns from crimson to storm grey (default blend 2353→2401).

Action
- Elder (0.00, 3.00): 2353 thunder — his head lifts 8° toward the sky (2353–2362) and returns; 2360–2370 right hand closes on the hilt, left hand on the saya; draw 2370–2384 (`CH.set_arm_mode(SAINT_rig, 2368, 'ik', blend=2)`, `SAINT_sword_ctrl` keyed at 2370 to `CH.sheathed_ctrl_matrix(SAINT_rig, 2370)`, `set_weapon_state(..., 2370, 'drawn')`, the blade slides out along the saya axis and clears the koiguchi at 2382); 2384–2396 brings it round to chudan, two-handed from 2390; 2396–2400 still, rain beading on the blade.
- Shinobi off-screen at (0.00, −4.10).

Environment
- storm transition = the default timeline (`storm_night` blend 2353 → 2401); `ENV.set_sun(2353, 270, −2.0)`.
- `ENV.set_wind(2353, 1.9)`, `ENV.set_wind(2380, 2.2)` (the gust front before the rain).
- **No flash at 2353**: the ring's two shadowed lights + the key are already 3 shadow casters (Pipeline rule 5; the ENV_flash lamp is shadowed) — the first thunder is heard and felt (the head lift, the gust, the sky starting to darken), not seen. The first lightning is 2425. VFX
```python
VFX.rain(2376, 3500, intensity=[(2376, 0.0), (2382, 0.06), (2400, 0.12), (2401, 1.0), (3470, 1.0), (3500, 0.0)],
         seed=300)                               # THE film rain (D8): drizzle -> downpour on the S20 cut -> S27 thinning
for k, (f, sock) in enumerate(((2386, "SAINT_katana_tip"), (2390, "SAINT_katana_base"), (2393, "SAINT_katana_tip"),
                                (2396, "SAINT_katana_base"), (2399, "SAINT_katana_tip"))):
    VFX.sparks(f, sock, direction=(0, 0, 1), count=6, speed=1.2, life=5, color=VFX.COLORS["water"], scale=0.35,
               light=False, core=False, strength=0.6, seed=301 + k)            # drops splashing on the steel
VFX.steam(2386, 2400, (0.15, 2.60, 1.30), 0.15, height=0.5, density=0.3, seed=306)   # faint hiss-wisps off the blade
```
Events
```python
EV.emit(2353, "thunder", distance="far", strength=0.8, tags=["thunder_first"])
EV.emit(2353, "music_cue", cue="thunder_first")
EV.emit(2353, "wind_gust", strength=0.6)
EV.emit(2370, "draw", who="saint")
for f in (2386, 2393, 2399): EV.emit(f, "steam_hiss", target=("SAINT_rig", "hand.R"), strength=0.25, tags=["blade"])
EV.emit(2388, "steam_hiss", pos=(-9.8, 3.0, 0.5), strength=0.4, tags=["ring"])      # first drops on the fire
```

### S20a — 2401–2448 (48 f) — the downpour drowns the ring (HIGH wide)
Purpose: the sky opens on the cut: the ring of fire collapses into a ring of steam; lightning moves inside the clouds; two small figures stand in the middle of it — the world has changed.

Camera (HIGH wide: 15 m up, looking 31° down at the ring centre, slow descending push):
```python
C.shot("S20a", 2401, 2448,
       keys=[(2401, (22.0, -10.0, 15.0), (0.0, 1.50, 0.0), 24.0),
             (2448, (20.0, -9.2, 13.6), (0.0, 1.50, 0.0), 24.0)],
       dof=None, handheld=0.0, subjects=["shinobi", "saint"], framing="wide")
```
Screen: shinobi (−0.25, 0.00) 8 %, elder (+0.06, +0.20) 9 % (small, in the ring's centre; 180 rule OK: −0.25 < +0.06). The ring as a full ellipse: near point (+X−Y) (−0.22, −0.85) → (−0.25, −1.0) at 2448 (touching the bottom edge at the end), far point (+0.12, +0.45), ±Y ends (+0.39, +0.25) / (−0.53, −0.34), ±X ends (−0.18, +0.42) / (+0.33, −0.77). The horizon is above the frame (no sky): the lightning reads as the whole field and the steam lighting up from above.

Action
- Elder (0.00, 3.00): chudan, still in the rain (head lowered 5° against the rain).
- Shinobi: three steps forward 2410–2445 (plants 2410, 2422, 2434, settle 2445) from (0.00, −4.10) to (0.00, −3.00).

Environment
- `ENV.set_sun(2401, 300, 38.0)` — the storm key from beyond the arena (in front of the lens): backlit rain + steam.
- `ENV.grass_effect("wet", dict(amount=1.0, ramp_frames=48), 2401)` (stays wet; nobody dries it).
- `ENV.set_wind(2401, 2.2, direction_deg=205)`.
- **Flashes** (in-cloud, no bolts), both after 2422 when the ring's shadowed lights are hidden (vfx `shadow_window` = (1632, 2422)) so the shot keeps ≤ 3 shadow casters (key + ENV_flash): `ENV.flash(2425, strength=0.45, duration=2, direction=(300.0, 60.0))`, `ENV.flash(2443, strength=0.30, duration=2, direction=(240.0, 55.0))`. VFX: the ring extinguishes by itself (`f_out=2401` in the S15a call: flames shrink over 20 f, lights to an ember glow, glowing steam band from 2401 on). Rain intensity 1.0 from 2401 (S19d call). (tune) if the steam band reads thin from this height: `VFX.steam(2401, 2470, (0.0, 1.5, 0.0), 11.0, height=5.0, ring=True, glow=True, density=0.8, seed=311)` as a short extra burst. Rain box: check coverage from this high camera (vfx.py: key the rain GN `Forward` / `BoxXY` for this cut if the near ground is dry). Events
```python
EV.emit(2401, "rain_start", strength=1.0, tags=["rain_start"])
EV.emit(2401, "music_cue", cue="rain_start")
for k, p in enumerate(((-11.0, 1.5), (0.0, 12.5), (11.0, 1.5), (0.0, -9.5))):
    EV.emit(2401 + k, "steam_hiss", pos=(p[0], p[1], 0.5), strength=1.0, duration=40)   # the whole ring hissing
EV.emit(2429, "thunder", distance="mid", strength=0.7)       # after the 2425 flash
EV.emit(2451, "thunder", distance="far", strength=0.5)       # after the 2443 flash (rolls over the S20b cut)
for f in (2410, 2422, 2434): EV.emit(f, "step", who="shinobi")
```

### S20b — 2449–2496 (48 f) — jodan, facing the storm
Purpose: the master raises his sword into jodan — a stance, not a summoning — while the drowned ring steams behind the student. (S21's bolt comes down on this pose at 2497.)

Camera (elevated rear 3/4 over the elder's LEFT shoulder, 2.9 m up, 14° down; slow push):
```python
C.shot("S20b", 2449, 2496,
       keys=[(2449, (1.90, 5.80, 2.90), (-0.20, 0.00, 1.30), 32.0),
             (2496, (1.80, 5.62, 2.86), (-0.20, 0.00, 1.32), 32.0)],
       dof=dict(fstop=4.0, focus=3.6), handheld=0.0, subjects=["shinobi", "saint"], framing="ots")
```
Screen: elder (+0.43, −0.41) 93 % → (+0.45, −0.43) 100 % (from behind-left: head, shoulders, white tasuki cross on the back, lower right); the jodan blade tip at 2490 (−0.02, 3.49, 2.62) at NDC (+0.67, +0.67) — the raised sword rises through the upper right third, rain streaming off it; shinobi (−0.24, +0.43) 37 % (upper left-centre, chudan, facing him). The ring's −Y arc (15.6 m, steam) fills the top third behind the shinobi (its flame-top line at +0.89) — the brighter steam layer behind his silhouette (DIRECTION §6). 180 rule OK.

Action
- Elder (0.00, 3.00): 2449–2460 two-handed chudan; 2460–2490 lifts into the local pose `jodan` (§5): both fists above the forehead, blade 45° above horizontal pointing back-up, tip ≈ (−0.02, 3.49, 2.62), left foot forward; 2490–2496 holds — HANDOFF[2496] pose "jodan".
- Shinobi (0.00, −3.00): chudan, still. Environment: `ENV.set_sun(2449, 200, 30.0)` (storm key from −Y, in front of the lens: rims the elder and backlights the rain); rain 1.0, wet, wind 2.2 — **no flash in S20b** (the lift is not synchronised with lightning; next flash is act3's 2497 bolt, 54 f after 2443). VFX: `VFX.sparks(f, "SAINT_katana_tip", …)` water splashes as in S19d at 2474, 2481, 2488, 2494 (count 5, scale 0.3). Events: `EV.emit(2462, "whoosh", who="saint", weapon="katana", strength=0.35)`; `EV.emit(2458, "step", who="saint", strength=0.3)`.

## 4. Flash schedule + budget proof

`ENV.flash` strength 1.0 is calibrated to ≤ ~70 % frame luminance (environment.FLASH_MAX), so "full-frame white equivalent" ≈ 0.7 × strength. Envelope per frame = FLASH_ENVELOPE (1.0, 0.42, 0.12, 0.03) × strength.

| frame | source | strength (env) | ≈ full-white equiv. | duration | purpose |
|---|---|---|---|---|---|
| 1633–1643 | fire ring eruption (`fire_ring` height ramp + its 8 lights) | — | luminance *ramp* (est. +0.10) over 9.6 f, no return | ramp | NOT a flash: monotonic rise ≥ 6 f (red-flash rule, DIRECTION §5) |
| 2017–2024 | slam fire burst (local fire_ring r 1.3, no lights) + spark light 64 W / 8 m | — | local, < 0.05 | 7 f ramp | NOT a flash |
| 2329–2336 | spear-landing flare (local, no lights) | — | local, < 0.03 | 7 f ramp | NOT a flash |
| 2353 | first thunder | — | — | — | sound only (no flash: 3 shadow casters already lit — see S19d) |
| **2425** | `ENV.flash(2425, 0.45, 2, direction=(300, 60))` in-cloud | 0.45 | ≈ 0.32 | 2 f (0.45 / 0.19) | storm arrives (S20a) |
| **2443** | `ENV.flash(2443, 0.30, 2, direction=(240, 55))` in-cloud | 0.30 | ≈ 0.21 | 2 f (0.30 / 0.13) | S20a |
| (2497) | act3: the S21 bolt (≤ 0.70, 2 f, blue) | | | | next lane — 54 f after 2443 |

Clash sparks carry 3-frame local point lights (40–64 W, cutoff 8 m): local glints, not full-frame flashes. No compositor white (`render_setup.key_white_flash`) is used in this lane.

Proof
- Gaps: 2425 → 2443 = 18 f, 2443 → 2497 (act3) = 54 f; no flash in this lane before 2425 (so no interaction with act1b's span) — all ≥ `config.FLASH_MIN_GAP` (12) ✓.
- ≤ 2 per second: the 24-frame windows containing both 2425 and 2443 hold exactly 2 ✓ (flash_qc WARN is > 2, FAIL > 3).
- ≤ 70 %: max ≈ 0.32 of full white (2425) ✓; nothing in the span is near `config.FULL_WHITE` (3265–3268) ✓.
- Shadow casters (Pipeline rule 5): 1633–2422 = key + the ring's 2 shadowed lights (3) and no flash; 2425/2443 = key + ENV_flash (2) ✓.
- `ENV.flash` enforces the gap and the clamp itself (refuses < 12 f, clamps > FLASH_MAX); call it with exactly these frames and check `ENV.flash_log()` after the lane build (no refusals expected).
- Red flashes (flash_qc's saturated-red area rule, ≥ 25 % of the picture): the S14 → S15a cut (crimson sky → mostly grass seen from above) and the S15a → S15b cut (back to a crimson sky) are one down/up pair within 24 f = at most one "red flash" → below both thresholds. Every other Act II cut keeps the crimson sky/fire band in frame, so no red-area alternation; the 2401 cut (fire → steam) is a single downward transition.
- No lightning, flash or glow is synchronised with the jodan lift (S20b is flash-free: "a stance, not a summoning").

## 5. Local poses / moves not in the SPEC macro list

Format = `characters.apply_pose` / `pose_bones` spec: **rig space** (character faces −Y: forward = −Y, his left = +X, up = +Z), SHINOBI metres (scaled by height for the SAINT unless noted), degrees with +X = flexion. `ctrl` = the right-fist grip centre + weapon direction for `CH.key_sword` (or `CH.key_blade_tip` where a tip/contact point is given in world space — preferred for every contact). World ↔ rig: elder (facing 0) world = root + rig; shinobi (facing 180) world = root + (−x, −y, z). Define them in `acts/act2.py` as `_local_POSES` / `_local_*` moves; if `moves.py` ships a macro with the same intent, use the macro and keep these numbers as its targets.

| name | who / frames | spec (key numbers) | intent / check |
|---|---|---|---|
| `spear_butt_slam` | SAINT 1633–1645 | hips_offset (0, −0.10, 0); spine (8,0,0), chest (5,0,0), head (−8,0,0); legs L ankle (0.22, −0.20, 0.08), R ankle (−0.20, 0.25, 0.08); weapon spear, spear_grip (1.30, 0.85), two_hand; ctrl grip (0.08, −0.48, 1.30), dir (0, 0, 1) | spear vertical, butt exactly on BUTT (rig (0.08, −0.48, 0)); recoil 1633→1637 hips −0.10 → −0.14 |
| `spear_guard_low` | SAINT 1705–1728, reused 1776, 1866 | hips_offset (0, −0.12, 0); spine (10, −15, 0), chest (5, −10, 0); legs L (0.18, −0.35, 0.08), R (−0.15, 0.30, 0.08); spear_grip (0.35, 0.95); ctrl grip (−0.18, −0.10, 0.95), dir (0.125, −0.98, 0.156) | rear fist at the right hip, tip ≈ rig (0.06, −2.01, 1.25) = world (0.06, 4.49, 1.25) aimed at the shinobi's chest |
| `spin360` (spear_sweep kind) | SAINT 1745–1765 | rig z-rotation keys 1745 −30°, **1753 75°**, 1759 190°, 1765 330° (continuous); spear held rigidly to his right: rig dir (−0.97, −0.26, 0), fists near the butt (grip 0.10 / 0.50) at rig (−0.35, −0.20, 1.50); chest Y −25 (wind-up) → +15 (1753) → 0 | the tip points world −Y (compass 180) exactly at 1753 at z 1.55–1.65, radius 2.65 m; at 1753 his body faces +X (toward the S16a lens) with the spear extended screen-left over the ducked shinobi |
| `slide_duck` | SHINOBI 1747–1758 | hips_offset (0, −0.45, 0.05) at 1753; spine (15,0,0), chest (−5,0,0), head (−10,0,0); legs L (0.18, −0.45, 0.08), R (−0.12, 0.35, 0.10) knee near the ground; ctrl grip (−0.20, 0.05, 0.85), dir (−0.2, 0.9, −0.4) (point back-down, waki), two_hand | head centre ≥ 1.15 m (grass line 1.02–1.05); the root keeps sliding 0.35 m forward 1747→1753 |
| `kunai_parry_slide` | SHINOBI 1809–1824 | left fist (FK arm: upper_arm.L ≈ (70, 0, 20), forearm.L ≈ (45, 0, 0)) from rig (0.35, −0.45, 1.30) at 1810 to (0.05, −0.60, 1.32) at 1814 — crossing his centre line, meeting the shaft on its world −X side at (−0.10, 3.30, 1.32); then the fist stays on the shaft (world x −0.10) while the root slides (0.08, 2.72) → (−0.25, 4.30); torso turned 20° right (left shoulder leads), left foot forward; right hand: ctrl grip (−0.25, 0.10, 1.55), dir (0.2, 0.3, 0.93) (sword cocked high-back, one-handed) | the shaft is pushed ≥ 8° to world +X (the spear head passes his right side); `CH.wrist_report` for the left wrist; if the FK arm cannot hold the shaft line, drive `SHINOBI_grip_L` as a free IK target (left = 'grip' on an empty keyed along the shaft) |
| `shaft_shove` | SAINT 1841–1849 | hips_offset (0, −0.05, 0.10); both arms extended: fists at rig (∓0.30, −0.60, 1.35), shaft horizontal along X (ctrl dir (1, 0, 0) after flipping the grip, spear_grip (0.35, 1.30)); right foot steps forward 0.3 m at 1847 | the shaft pushes on the crossed sword + kunai (weapon contact only) |
| `low_sweep_lunge` | SAINT 1880–1893 | hips_offset (0, −0.35, 0.05); spine (35, −20, 0), chest (15, −10, 0); legs L (0.30, −0.55, 0.08), R (−0.25, 0.55, 0.08); spear_grip (0.20, 0.75); ctrl at z 0.55, dir rotating in the horizontal plane with −3° tilt: tip compass 290 (1880) → **180 (1885)** → 90 (1893), radius 2.9 m, tip z 0.40 | head centre 1.25 at 1885 (stays above the grass) |
| `vault_tuck` | SHINOBI 1881–1889 (apex 1885) | thighs (110, 0, ±10), shins (130, 0, 0), spine (20,0,0); ctrl grip (0, −0.30, 1.35) (relative to the root, which is 0.55 m up), dir (0, −0.5, 0.87), two_hand | feet ≈ 0.85–0.90 m at the apex (0.45 m over the spear); head 1.95 |
| `kunai_throw_L` | SHINOBI 1931–1949 | per throw (release f = 1937 / 1943 / 1949): cock at f−3: upper_arm.L (150, 0, 30), forearm.L (110, 0, 0), chest Y +20; release at f: upper_arm.L (60, 0, 10), forearm.L (10, 0, 0), chest Y −15; left fist at release = rig (0.15, −0.35, 1.55) → world (−0.15, 1.45, 1.55) | if `M.throw_kunai` assumes the right hand, mirror it (`CH.mirror_pose`) — the sword stays in the right |
| `spear_wheel` | SAINT 1935–1963 | swap to the free spear: `CH.snap_free("SAINT_spear_world", 1935)` + `set_weapon_state(…, 1935, 'world')`; parent-free keys: the spear's CoM at the hub world (0.00, 5.15, 1.40), rotation about the world Y axis +37°/f (2.5 rev/s) easing out 1957→1963; hands posed at the hub (both fists ±0.12 m around it, `left='free'`, FK arms rolling ±20°); at 1963 key `SAINT_sword_ctrl` so the hand spear coincides with the world spear (grip 1.00) and swap back to 'in_hand' (CONSTANT) | no 360° wrist roll on the IK hand; the swap frames must match to the millimetre (check with `CH.blade_points`) |
| `slam_windup` → slam | SAINT 1999–2017 | 1999–2008: ctrl grip rig (−0.10, 0.10, 1.95), dir (0, 0.6, 0.8) (spear up-back over the head, grip 0.20 / 0.75); 2008→2017 rotates forward-down over the head; **2017**: `CH.key_blade_tip(SAINT_rig, 2017, tip=(0.10, 0.85, 0.03), direction=(0.03, −0.99, −0.12))` (world) → grip ≈ world (0.04, 2.78, 0.26); hips_offset (0, −0.45, 0.05), deep knees | blade flat on the ground along the line, midpoint ≈ IMPACT; 2017→2020 rebound: tip up 0.15–0.25 m (D4) |
| `kneel_guard` | SHINOBI 2019–2030 | hips_offset (0, −0.55, 0); legs L (0.15, −0.35, 0.08) (left foot forward), R knee on the ground (R ankle (−0.12, 0.40, 0.05), toes tucked); ctrl grip (0.0, −0.30, 0.95), dir (0, −0.85, 0.53), two_hand | head 1.05–1.10 (just above the grass line at 8.5 m: reads as a head + raised blade behind the dust) |
| `knee_slide` | SHINOBI 2073–2085 | hips_offset (0, −0.62, 0); left shin on the ground leading (thigh.L (−10,0,0), shin.L (120,0,0)), right leg bent forward (thigh.R (80,0,0), shin.R (95,0,0)); spine (−20,0,0), chest (−15,0,0) (leaning back 35°), head (15,0,0); ctrl grip (−0.20, −0.20, 0.95), dir (0.97, 0, 0.26) (blade across the chest, edge up), two_hand | head 0.95–1.00; the thrust passes 0.5 m above him at 2077; the root slides 1.4 m on the ground |
| `staff_block_diag` / `_vert` / `_high` | SAINT 2089–2158 | spear_grip (0.50, 1.40) (wide). diag: ctrl grip (−0.25, −0.30, 1.05), dir (0.55, −0.10, 0.83); vert: grip (0.20, −0.35, 0.80), dir (0, 0, 1); high (bind): grip (−0.35, −0.20, 1.95), dir (1, 0, 0) | use `CH.key_blade_tip`/`M.clash` so the SHAFT passes through each contact point (2089, 2101, 2113, 2143) |
| `staff_butt_strike` | SAINT 2119–2125 | the butt leads: ctrl dir (0.2, 0.6, −0.77) (tip down-back), grip rises from rig (−0.30, −0.10, 0.90) to (−0.15, −0.35, 1.35); the butt point = grip − dir × 0.50 reaches world (0.05, 1.65, 1.40) at 2125 | the butt (not the blade) meets the sword |
| `staff_head_chop` | SAINT 2131–2137 | short diagonal chop from his high right: spear head from rig (−0.60, −0.40, 2.00) to world (0.20, 1.68, 1.60) at 2137 (grip 0.50 / 1.40) | elder-initiated → fire sparks |
| `kick_front` (M.kick for the SAINT) | SAINT 2161–2181 | chamber 2168: thigh.R (95,0,0), shin.R (100,0,0) (knee 1.0 m); extension 2173: thigh.R (80,0,0), shin.R (5,0,0), spine (−15,0,0) (leans back), hips forward 0.10; the sole at world (0.15, 1.33, 1.25); spear held high-left in both hands | 2172 = sole 0.10 m short (last frame of S18d), 2173 = contact on the cut |
| `kicked_fold` | SHINOBI 2173–2180 | spine (35,0,0), chest (20,0,0), head (−20,0,0) (head snaps back), upper_arm.L/R (40, 0, ±60) (arms flung forward-out), knees 40°, root z up to 0.25; sword in the right hand pointing back-down | readable as "hit in the chest" without seeing the foot |
| `skid_sword_drag` | SHINOBI 2180–2204 | hips_offset (0, −0.50, −0.10); spine (40, 25, 0); ctrl grip (−0.31, 0.14, 0.48), dir (−0.32, −0.72, −0.61) → sword tip in the dirt at rig (−0.55, −0.40, 0.02) = world offset (+0.55, +0.40) (front-right, toward the elder: it trails the backward slide like an anchor); left arm down to the ground behind-left (upper_arm.L (−20,0,30), forearm.L (10,0,0)), palm at rig (0.35, 0.25, 0.10) | one-handed (`two_hand` off 2173–2215); the spark/dirt trail follows the tip (§3 S18e) |
| `javelin_ready` / throw | SAINT 2240–2276 | spear_grip (1.30, —), one hand; ready: ctrl grip (−0.25, 0.25, 1.80), dir (0.05, −0.99, 0.12); left arm at the target (upper_arm.L (95,0,10), forearm.L (5,0,0)); chest Y −30; legs L (0.15, −0.45, 0.08), R (−0.12, 0.35, 0.08); cock 2263: grip → (−0.30, 0.55, 1.85); release 2269: grip → rig (−0.25, −0.55, 1.95) = REL; follow-through 2276: right arm across the body, chest Y +35 | the spear leaves the hand on 2269 (swap to `SAINT_spear_world`) |
| `deflect_rising_R` (M.deflect "mid_R" variant) | SHINOBI 2277–2290 | 2277: ctrl grip (−0.30, −0.25, 0.95), dir (−0.5, −0.6, 0.6); 2281: grip (−0.10, −0.40, 1.30), dir (0.45, −0.55, 0.70) — blade crosses DEF = rig (−0.12, −0.65, 1.45); 2281–2304 continues up-left at 0.4× speed | two-handed |
| katana draw (SAINT) | 2368–2396 | `M.draw_sword(SAINT_rig, 2370)` if it starts from `CH.sheathed_ctrl_matrix`; else local: ctrl = sheathed matrix at 2370, pulled 0.87 m along the saya axis by 2382 (blade clears the koiguchi), then to chudan grip (−0.05, −0.35, 1.15), dir (0, −0.80, 0.60) by 2396 | pop-free: the in-hand blade coincides with the sheathed one at 2370 |
| `jodan` | SAINT 2460–2496 | hips_offset (0, −0.06, 0); legs L (0.15, −0.40, 0.08), R (−0.15, 0.25, 0.08); spine (−3,0,0), chest (−5,0,0), head (0,0,0); ctrl grip (−0.02, −0.12, 2.00), dir (0, 0.70, 0.71), edge up-forward; two_hand (left fist 0.19 m below on the tsuka) | classical jodan: blade angled back 45°, tip ≈ world (−0.02, 3.49, 2.62). **Do not use `raise_to_sky`** (a vertical blade at the sky reads as a summoning) |

Local helpers (prefix `_local_`, SPEC file-ownership rule):
- `_local_haori_burn(obj, ignite, gone)`: copy `SAINT_haori_thrown`'s material; Noise Texture (object coords, scale 3.0, detail 4) + a distance gradient from the corner nearest the fire patch → value n; threshold τ keyed on the film clock with `vfx.time_curve(mat.node_tree, <Value node>, [(ignite, −0.05), (1690, 0.35), (1760, 0.80), (gone, 1.05)])`; n < τ − 0.15 → Transparent (Mix Shader; `surface_render_method='DITHERED'`); τ − 0.15 … τ − 0.06 → char (base 0.02); τ − 0.06 … τ → emission (1.0, 0.35, 0.06) × 1.2 (the burning edge; bloom does the rest). `key_visible(obj, gone+1, False)`. The roundel panel should be the last part to go (start the gradient at the hem).
- `_local_ballistic(obj, f0, p0, v0, f1, spin_axis=None, spin_rate=0.0, align_velocity=False)`: keys location every frame f0…f1 with t = `fxclock.fx_time_at(f) − fxclock.fx_time_at(f0)`, p = p0 + v0·t + ½·g·t² (g = −9.81 on z); rotation = align to the velocity (kunai, javelin) or accumulate `spin_rate × t` about `spin_axis` (deflected kunai, tumbling spear); `U.key_visible(obj, f0, True)`; CONSTANT on f1 (the landing pose). Use `props.toss` instead when it exists and takes a time mapping.
- `_local_shaft_points(frame)`: (butt, tip) of the in-hand spear = `SAINT_spear_base` extended back to the butt by (spear_length − spear_blade_length) along the spear axis — for `M.clash` on shaft contacts if the resolver only knows the blade segment.

## 6. Title overlays in the span

Only one: `config.TITLES` id `act2` — "Act Two" + the Fire glyph, style `act`, **1665–1726**, over S15b (1657–1728).
- Timing (out/titles/timeline.json, titles.py): column ramps in ≈ 1678, accent Fire glyph ≈ 1686, seal impact 1687, **legible 1693–1715**, fades out by 1726; the cut to S16a is 1729 (3 f after the card is gone).
- Geometry (measured from titles.py by `out/dev/breakdown/act2/act_card_box.py`): accent glyph ink NDC x +0.416…+0.668, y +0.005…+0.583; column ink x +0.717…+0.779, y +0.059…+0.537; soft dark backdrop ellipse x +0.336…+0.859, y −0.292…+0.704 (22 % black) — the upper-right third of the picture.
- How S15b leaves room: the elder is centred (head top x +0.02…+0.03, ≥ 0.31 NDC left of the backdrop), faces screen-left, and his spear points left in the guard; the burning haori is lower-left (−0.45, −0.62). Under the card there is only smoke and crimson sky: the ring's tongues are cheated to 1.3 m for this cut (§3 S15b): typical tongue tops ≈ −0.15, big ones ≈ −0.10, rare flicker peaks (2.5 m) ≈ +0.12…+0.20 — they may lick into the bottom fifth of the ink box for a frame or two; nothing else crosses it. The 1669–1693 twirl is a side-wheel in the vertical plane through his shoulders (world X-Z, hub at his right hip (−0.25, 6.45, 1.35), radius 1.15 m), which from the S15b lens stays within NDC x −0.17…+0.18, y −1.2…+0.72 (never under the card backdrop, which starts at x +0.336); a wheel in his facing plane would reach x +0.30 — do not use it.
- Motion vs legibility: the big motion (twirl) happens while the card is still writing (1678–1692); from 1693 (legible) the elder is still (guard settled 1705) and the camera push is 0.4 m over 72 f.
- Request to the titles lane (not this file): check S15b's preview for flame tips behind the Fire glyph; if they hurt legibility, raise the act2 backdrop from 22 % to ~30 % or tint the act2 glow darker.
- No other titles in 1633–2496 (act1 card ends 528, act3 card starts 2521).

## 7. Risks + fallbacks

| # | risk | what to watch | fallback / simplification |
|---|---|---|---|
| R1 | **Cross-lane ownership** of the fire ring's steam band (2401–3456) and of the film rain (2376–3500), both created here (D8, per vfx.py's "one call" recipes) | act3 / finale also calling `fire_ring` / `steam(ring)` / `rain` → doubled rain or steam; or nobody calling them | agree once: act2 owns both (this doc). If the others prefer to own their spans: act2 passes `f_end=2498` to `fire_ring`, `rain(2376, 2498, …)` and act3 re-creates steam band + rain from 2497 (a hard cut hides the object switch) |
| R2 | S14 → S15 continuity (act1b's last frames) | S14 should end on the spear coming down butt-first near BUTT; the haori / hat halves where act1b left them | S15a is a top-down from 50 m: a pose/prop mismatch across the hard cut is invisible; the D2 cheats (haori re-keyed, hat halves hidden at 1633) make act2 independent of act1b's rest poses |
| R3 | Fire ring cost (R 11 → ≈ 690 tongues + 8 lights + smoke + embers) | render time per frame (vfx measured 0.6 s at R 8; steam overlap 0.9 s) | `count=520`; `n_lights=6`; smoke density 1.2 |
| R4 | The growing flame front passes through both fighters' positions (1634–1635), visible from the top-down as a thin bright ring crossing them | S15a frames 1634–1636 | acceptable (reads as "the wave rushes out under their feet"); or `grow_frames=8` (passes both within 1 f) |
| R5 | Flame tips behind the act card (S15b) | preview 1693–1715 | the per-cut `Height` cheat (1.3) is in; lower to 1.1 for 1665–1716; titles lane darkens the act2 backdrop (§6) |
| R6 | Kunai too small to read (S16b parry, S17 throws) | 1813, 1937–1957 at preview resolution | kunai ×1.4 thicker (like the blades); a 3-frame thin white streak behind each flying kunai (a stretched card or `blade_trail` on two empties parented to it); the spark bursts carry the deflects |
| R7 | The spear-wheel swap (hand ↔ `SAINT_spear_world`) pops | 1935 / 1963 | keep the spear in hand and fake the wheel as a fast ±150° oscillating twirl + the orange trail disc + motion blur |
| R8 | 360° spin (1745–1765) reads as a pirouette, not a sweep | S16a | reduce to a 270° sweep (wind-up further back, 1747–1761) — the 1753 pass over the head is unchanged |
| R9 | Knee-slide / sliding duck vanish in the waist-high grass | S16a 1753, S18a 2077–2085 | S18a camera up to 1.6 m and pitched −5°; slide head height 1.10; the grass parting radius around the rig does the rest |
| R10 | Kick contact visible or reads as a miss across the cut | 2172/2173 | foot 0.05 m short at 2172; start S18e 1 f later in the fold (the flight pose), never show the foot touching |
| R11 | Slow-motion mismatch: characters/spear keyed in real time inside 2280–2304 while fx run at 0.4 | S19b | all motion inside the window keyed at 0.4× (24 frames = 9.6 frames of action); ballistic keys use fx time (`arcs.py`) |
| R12 | The low sweep (1885) invisible in the grass | S16d | the elevated camera + grass bursts along the arc are in; the (tune) shear adds the mown fan; worst case raise the sweep to 0.55 m (still under the vault) |
| R13 | Shear slot 2 already used by act1b | S16d | drop the shear, keep the bursts (the event `grass_shear` stays for sound) |
| R14 | Rain coverage from the high S20a camera (the rain box follows the camera; vfx.py:) | S20a ground looks dry | key the rain object's GN `Forward` / `BoxXY` for 2401–2448 (drivers can be removed per shot) or raise `count` |
| R15 | In-cloud flashes without a visible bolt read as a render glitch | S20a 2425 / 2443 | add one distant environmental bolt at 2425 with `vfx.lightning_bolt(2425, far_sky, far_ground, flash=False, light=False)` 150–250 m away toward az 300 (not near the elder, not synchronised with the jodan) |
| R16 | The ring's two shadowed lights + key + ENV_flash > 3 shadow casters | any flash before 2422 | none scheduled (§4); keep it that way — the first thunder stays sound-only |
| R17 | `M.clash` resolves only katana segments (spear shaft contacts 1837, 2089–2149, 2281) | clash gate report in `end_lane` | `_local_shaft_points()` (§5); worst case emit the clash events + sparks by hand at the listed points with `emit=False` resolution |
| R18 | Red-area alternation around S15a (crimson sky → grass top-down → crimson sky) | flash_qc red rule | one pair only (≤ WARN); if flagged, tint S15a's grass warmer via `ENV.set_param(1633, 'grass_leaf', …)` for the cut |
| R19 | Old man's 1.0-s-scale leap looks floaty | S17c/S17d | shorter airtime: take-off 2003, apex 2010 (root z 0.40) — the slam stays on 2017 |
| R20 | The deflected spear's screen path in S19c is mostly vertical | S19c | accept (it reads as "up, then down into the fire"); or land it at (−6.9, −7.1) for more lateral travel (re-run `arcs.py`) |

Cross-lane notes (for the act1b / act3 / finale implementers)
- act3 enters with: the elder in **jodan** at (0, 3), the ring's glowing **steam band** alive (radius 11 around (0, 1.5), until 3456), the **rain** at intensity 1.0, the grass **wet** (1.0, held), wind 2.2 (dir 205), env `storm_night`; the thrown spear hidden ('gone'); the burnt annulus (grass_effect 'burn', never ends).
- act1b: please end S14 with the spear coming down butt-first (the S15a impact is 1633); no other requirement (D2 cheats handle the haori and the hat halves).

## 8. Implementation order for `acts/act2.py` (suggested)
1. Constants from this doc (BUTT, HAORI, IMPACT, REL, DEF, SPEAR_LAND, RING centre/radius) + `_local_*` helpers (§5).
2. Root tracks (§1 table) for both rigs → verify with `out/dev/breakdown/act2/geom.py` (it reads the same data).
3. Weapon/costume state keys (§1 table) → poses per block (§3) → `M.clash` contacts (13) → props (kunai, haori, spear: `_local_ballistic` with the §3 table).
4. Cameras (23 `C.shot` calls, keys copied from `cams.py`) → run `cameras.check_screen_direction` + `framing_qa`.
5. Environment + vfx calls per block; the two film-long calls (ring, rain) once.
6. Events per block (+ the music cues 1633 / 2353 / 2401).
7. Layout preview of 1633–2496 → contact sheet → compare with `summary.txt` numbers.
