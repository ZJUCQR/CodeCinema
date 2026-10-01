# Lane act3 — S21, S22, S22b, S23 (frames 2497–3072) — shot breakdown

Status: COMPLETE (all sections filled; history in out/dev/breakdown/PROGRESS_act3.md). Owner file for the implementer: `src/blender/acts/act3.py`. Numbers here are binding unless marked "(tune)". `config.py` wins if it disagrees with a number copied here (import it; never re-type TEMPO_MAP / HANDOFF / TITLES). Geometry proofs: `out/dev/breakdown/act3/geom.py` → `geom_report.txt`.

Conventions used below
- Positions = rig origin on the ground (x, y); facing 180 = +Y (shinobi), 0 = −Y (elder). Heights z in metres.
- Screen positions are NDC: x −1 (left) … +1 (right), y −1 (bottom) … +1 (top). "H%" = size as % of frame height.
- Camera azimuth φ about the fighters' midpoint: φ = 0 is the +X profile, φ = −90 behind the shinobi, φ = +90 behind the elder. |φ| < 90 = the legal +X side.

## 1. Lane summary

| | |
|---|---|
| Shots | S21, S22, S22b, S23 — frames **2497–3072** (576 f = 24.0 s), **21 sub-cuts**, all hard cuts |
| Act / env | Act III "Act Three · Thunder": `storm_night` (full since the S20 cut 2401, default timeline — no `set_state` needed except the S22 strobe dim and its restore, §3 S22a / S22ba); rain 1.0, wet 1.0, glowing steam band — all created by act2 (its D8: `fire_ring(..., f_out=2401)` steam band r 11 around (0, 1.5) until 3456; `rain(2376, 3500, …)`). **This lane creates no second rain / ring / steam band.** |
| Music grid | 140 BPM from 2497 (`config.beat_frame('act3', b)`), 14 bars to 3073 (§2). S22b starts on bar 8, the low-point cut is the bar-12 downbeat (2950) |
| Enters (HANDOFF[2496]) | shinobi (0.0, −3.0) facing 180, katana **drawn**, two-handed chudan; elder (0.0, 3.0) facing 0, katana **drawn**, pose **jodan** (two-handed; act2 §5 `jodan`: grip rig (−0.02, −0.12, 2.00), dir (0, 0.70, 0.71), tip ≈ world (−0.02, 3.49, 2.62)), hat off, haori off, tasuki on, spear **gone** |
| Leaves (HANDOFF[3072]) | shinobi (0.0, −6.0) facing 180, katana **drawn**, pose **`kneel_sword_planted`** (§5: right knee down, sword tip in the mud at world (0.02, −5.46, 0), both fists on the tsuka, head bowed); elder (0.0, 2.5) facing 0, katana **drawn**, two-handed **gedan** (tip low toward the shinobi, §5), hat off, haori off, tasuki on, spear gone |
| Track error at the boundaries | 0.00 m at 2497 and at 3072 (`geom.py` tracks start/end exactly on the HANDOFF values) |
| Contacts | **9 sword/sword clashes**: elder-initiated 2620, 2641, 2682, 2703 (heavy), 2723, 2764 (the turned blow, sliding to 2768); shinobi-initiated 2795, 2806, 2826. **2 near-misses** (2662, 2744). **1 lightning cut** (2497, blade vs bolt — not a clash). **1 ground strike** (2950, the grounded cut: spray ring + rain split + shockwave). No body contact (the S23 throw is by the blast, the shinobi is never touched) |
| Slow motion | none (no `config.SLOWMO` window in 2497–3072; S23 is real time) |
| Flashes | **7**: 2497 (raikiri, ENV 0.80 ≈ 56 %, blue, 2 f) + the S22 strobe 2605, 2620, 2662, 2703, 2744, 2764 (0.45–0.65 ≈ 31–45 %, 2 f each); none in S22b / S23 — §4 |
| Titles | act card Act Three · Thunder 2521–2588 (legible 2551–2577) over S21c — §6 |
| Geometry proof | `out/dev/breakdown/act3/geom.py` → `geom_report.txt` (21 cuts, **ALL PASS**: 180-degree side + order at f0 / key frames / f1, card clearance, steam-band clearance, rain-split plane angle) |

Story of the lane in one line: a bolt comes down on the old master and he cuts it — the forked lightning splits the lone pine; the storm is named (Act Three · Thunder) while the student stalks in; then the fight is seen only in lightning: every flash a new tableau, the master pressing blow after blow, the student blocking, dodging, finally turning a heavy cut aside; in the steady storm-light the student answers with three fast strikes and drives the master back — who gathers himself into jodan; the student attacks the open stance, the master's full-power cut splits the rain and the blast throws the student far back; he ends on one knee, leaning on his planted sword, head bowed, while the master walks two unhurried steps toward him and waits.

**Ground truth for readability (cross-lane, measured in `geom.py`):** act1b's S11 draw-cut sheared the grass tops in a 220° crescent in front of (0, 2.6), radius 14 m (`grass_effect('shear', …)`, `until=None` → the 0.59–0.71 m stubble **persists through Act III**), and act2's burn annulus (r 9.7–12.3 around (0, 1.5)) collapsed to stubble. So every fighter position of this lane on the −Y side of y = 2.6 stands in **0.65 m stubble**, not waist-high grass: the kneel at (0, −6) shows the whole torso (head 1.02, hilt 0.74). Behind the elder (y > 2.6, bearings 286.5°…66.5° from (0, 2.6)) the grass is full height (1.05–1.15). If act1b ever sets `until` < 3073, see R3 (§7).

Root tracks (key frames; ease-in/out between keys unless noted; `geom.py SH_TRACK / EL_TRACK` hold the same data with the head-centre height). Facing: shinobi 180 = +Y, elder 0 = −Y; rig z-rotation θ → forward (sin θ, −cos θ). **Cheats** (DIRECTION §2, ≤ 0.5 m, CONSTANT key on the cut's last frame, jump on the next cut's first frame) are marked ⟲.

| frame | shinobi (x, y) facing | elder (x, y) facing | what happens |
|---|---|---|---|
| 2497 | (0.00, −3.00) 180 | (0.00, 3.00) 0 | HANDOFF[2496]; the bolt, the cut (blade already in the contact pose on the S21a cut) |
| 2498→2506 | → (0.00, −3.15) | (0.00, 3.00) | shinobi recoils half a step from the blast of light and thunder |
| 2500→2545 | (0.00, −3.15) | (0.00, 3.00) | elder holds the follow-through (zanshin) 2500–2530, settles, rises into `hasso` 2548→2580 |
| 2530→2590 | stalk → (0.00, −1.25) (0.76 m/s, 4 slow steps 2536/2550/2564/2578) | (0.00, 3.00) hasso | under the act card |
| 2592→2612 | advance → (0.00, 0.75) at 2612 (2.3 m/s, low chudan) | 2594→2605 one step → (0.00, 2.85) | the strobe starts: 2605 reveal |
| 2620 | (0.00, 0.60) | (0.00, 2.55) | **A1** kesagiri blocked (clash 1) |
| 2641 | (0.00, 0.30) | (0.00, 2.25) | **A2** rising cut deflected (clash 2) |
| 2644 ⟲ | (0.00, 0.60) | (0.00, 2.55) | cheat +0.30 / +0.30 |
| 2662 | (0.00, 0.05) leaping back | (0.00, 2.30) | **A3** horizontal cut, near-miss |
| 2665 ⟲ | (0.00, 0.35) | (0.00, 2.60) | cheat +0.30 / +0.30 |
| 2682 | (0.00, 0.20) | (0.00, 2.15) lunge | **A4** thrust parried (clash 3) |
| 2685 ⟲ | (0.00, 0.55) | (0.00, 2.50) | cheat +0.35 / +0.35 |
| 2703 | (0.00, 0.45) pressed down (head 1.33) | (0.00, 2.40) | **A5** heavy two-handed overhead blocked (clash 4, heavy) |
| 2706 ⟲ | (0.00, 0.60) | (0.00, 2.55) | cheat +0.15 / +0.15 |
| 2723 | (0.00, 0.30) | (0.00, 2.25) | **A6** reverse diagonal deflected (clash 5) |
| 2726 ⟲ | (0.00, 0.60) | (0.00, 2.55) | cheat +0.30 / +0.30 |
| 2744 | (0.50, 0.40) facing 185 (sidestep to his right) | (0.00, 2.35) | **A7** kesagiri, near-miss |
| 2747 ⟲ | (0.45, 0.55) facing 183 | (0.00, 2.50) | cheat |
| 2764 | (0.25, 0.55) 180 | (0.00, 2.50) | **A8** heavy overhead turned aside (uke-nagashi, clash 6 sliding 2764→2768) |
| 2767→2784 | → (0.15, 0.65) | (0.00, 2.48 → 2.45) over-committed, blade low on −X | the opening |
| 2795 | (0.10, 0.90) | (0.00, 2.70) | **S1** his diagonal cut, parried (clash 7) |
| 2806 | (0.05, 1.10) | (0.00, 2.95) | **S2** his rising cut, parried (clash 8) |
| 2826 | (0.00, 1.55) lunge | (0.00, 3.15) | **S3** his lunging thrust, deflected (clash 9) |
| 2826→2838 | recovers → (0.00, 1.10) by 2850 | one full step back → (0.00, 3.40) | "drives the elder back a step" |
| 2838→2867 | (0.00, 1.10) chudan | half step back → (0.00, 3.60), rises into `jodan` (set 2867, bar 10) | he gathers himself |
| 2881→2925 | (0.00, 1.10) | (0.00, 3.60) jodan | the stand-off (S23a) |
| 2929→2939 | attacks: step-lunge → (0.00, 1.75) | (0.00, 3.60) | beat 42 |
| 2939→2950 | 2941 aborts, throws himself back → (0.00, 1.05) at 2950, root z 0.20 (airborne 2945–2951) | cut 2939→2950, front-foot stamp 2946 → (0.00, 3.45) | **2950 the grounded full-power cut**: blade tip strikes IMPACT (0.00, 1.75, 0) |
| 2950→2962 | thrown by the blast: flight → lands on back/shoulder (0.00, −2.30) at 2962 (root z apex 0.60 at 2955) | (0.00, 3.45) zanshin | spray ring, rain split |
| 2962→2980 | backward tumble (one roll) → (0.00, −4.90), comes up on one knee | (0.00, 3.45) zanshin until 2972, then rises | |
| 2980→2991 | one-knee skid → (0.00, −6.00) at 2991 (bar 13) | rising 2972→3000 to gedan | |
| 2986→3001 | sword planted 2986–2992 (tip into the mud at (0.02, −5.46)); head bows 2992→3001 | (0.00, 3.45) gedan | **the low point** (pose complete 3001) |
| 3011→3042 | (0.00, −6.00) `kneel_sword_planted`, breathing | step 1 3011→3022 → (0.00, 2.97); step 2 3030→3042 → (0.00, 2.50) | two unhurried steps |
| 3042→3072 | (0.00, −6.00) | (0.00, 2.50) gedan | hold → HANDOFF[3072] |

Weapon / costume / hand states (`CH = characters`; CONSTANT unless a blend is given)

| frame | call | note |
|---|---|---|
| 2497 | `CH.set_weapon_state(SHINOBI_rig, 2497, 'drawn')`; `CH.set_two_hand(SHINOBI_rig, 2497, True)` | re-assert (lane isolation) |
| 2497 | `CH.set_weapon_state(SAINT_rig, 2497, 'gone')` (spear) **then** `CH.set_weapon_state(SAINT_rig, 2497, 'drawn')` (katana); `CH.set_two_hand(SAINT_rig, 2497, True, weapon='katana')`; `CH.set_arm_mode(SAINT_rig, 2497, 'ik')`; `CH.set_costume(2497, haori=False)`; `CH.set_hat(2497, 'off')` | order matters: the katana call last sets `active_weapon` = katana; re-asserts HANDOFF[2496] |
| 2497 | `CH.set_arm_mode(SHINOBI_rig, 2497, 'ik')` | both swords are IK-controlled all lane (`<C>_sword_ctrl`, Pipeline rule 9) |
| 2950–2962 | `CH.set_two_hand(SHINOBI_rig, 2951, False, blend=2)`; `CH.set_two_hand(SHINOBI_rig, 2984, True, blend=3)` | thrown: the left hand flies off the hilt; it rejoins as he plants the sword |
| 2951–2980 | shinobi sword ctrl keyed so the blade trails his flight (tip back, away from the body — never through his head) | `CH.key_sword` every 3–4 f (§3 S23c) |
| 3072 | (no change) both drawn, both two-handed | HANDOFF[3072] |

Deviations / interpretations (deliberate; everything else follows config / HANDOFF exactly)
- **D1 — the elder's two steps go FORWARD** (menace, toward the kneeling student) from (0, 3.45) to HANDOFF (0, 2.50). That fixes the cut position at y 3.45 and therefore the fight's centre of gravity: the student's counter (S22b) drives the master back to 3.60 and the student charges the jodan from 1.10. The blast then throws him **7.05 m** (1.05 → −6.00; S18's kick threw him 5.3 m) — flight 3.35 m, tumble 2.6 m, skid 1.1 m.
- **D2 — S22 cheats.** The master presses in every S22 sub-cut (he advances 0.25–0.45 m, the student gives the same); across 7 of the 8 internal cuts both are shifted back +0.15…+0.35 m (⟲ rows) so the fight stays centred at y ≈ 1.5 instead of drifting 3 m toward −Y. Invisible in a strobe of extreme wides and ECUs (DIRECTION §2 allows ≤ 0.5 m).
- **D3 — the student engages first.** The S22 reveal (2605) shows HIM mid-advance and the master stepping in; from the first clash (2620) the master takes the initiative and presses (config: "the elder presses") until 2764.
- **D4 — the rain-split sub-cut (S23d) comes after the +X throw (S23c), not before.** DIRECTION §10 says "give it its own sub-cut … then return to +X for the spray ring". The vfx look-dev (`sheets/rain_split.png`) shows the corridor only reads clear from ≈ 2965 to 3000 (mist/sheet 2951–2957), while the spray ring and the throw happen 2950–2972. So: S23b (+X, the cut) → S23c (+X, spray ring throws him screen-left) → S23d (down the line, the open corridor 2973–3000, the refill 3000–3009) — chronological, and the +X return for the spray ring is S23c.
- **D5 — S23d looks down the corridor from the ELDER's end** (over his left shoulder, 0.85 m off the cut plane, ≤ 7°): inside the steam ring there is no room for a low camera behind the kneeling student (the steam band's inner edge is 2 m behind him at (0, −8)). The backlight is therefore behind the student (key az 190, el 16 — in front of the lens, ≈ 165° from the lens axis), which is the same physics as the vfx sheet's "light behind the elder" from the other end.
- **D6 — `low_point` tag.** config.MUSIC_CUES low_point = 2950 = the cut (bar 12): explicit `music_cue` at 2950 + tag on the impact events; the task/SHOTS "head bowed ~3000" pose event (3001, bar 13.2) also carries the tag (`events.py` / `timeline.py` let the explicit `music_cue` win; REQUIRED_BEATS low_point 2950 ± 30 is met by 2950).
- **D7 — not every S22 clash is a lightning flash.** 6 flashes for 8 blows: the wides are revealed by lightning, the ECUs of 2641 / 2682 / 2723 are lit by their own sparks (3-f local lights) — rhythm flash / spark / flash / spark … and every onset (flash or spark-lit ECU) stays ≥ 15 f from the next (§4).
- **D8 — S22's sub-cut ids skip the letter b** (S22a, S22c … S22j): `S22b` is a SHOT id (cameras._shot_of_cut matches the longest shot id first). S22b's sub-cuts are S22ba … S22bd.
- **D9 — the strobe dim.** For S22 the storm key/ambient are lowered (`ENV.set_param` key_pow 0.15, amb_str 0.18, fill_pow 0.04 at 2593) so the picture is "lit almost only by lightning" (+ the steam band glow, the burning pine's glow, sparks, trails, the slightly emissive headband); `ENV.set_state(2785, 'storm_night')` restores it on the S22b cut (the student's counter is the first thing seen in steady storm light).
- **D10 — raikiri flash strength** via `ENV.flash(2497, 0.80, 2, tint=(0.70, 0.80, 1.0), direction=(338, 76))` (≈ 56 % of full white, blue): `vfx.env_flash` caps at 0.70 (≈ 49 %), which is also acceptable (fallback).
- **D11 — "no glow" in S23**: the grounded cut gets NO blade trail (motion blur only); the blast is all water (spray ring, split rain, mist). The elder's S22 trails are steel-blue, the student's S22b trails white with a red core.
- **D12 — HANDOFF[3072] elder pose**: config gives none; this lane leaves him in two-handed **gedan** (§5), from which the finale's S24c lifts into jodan.
- **D13 — the afterglow starts on the S21b cut (2509–2512)**, not at 2498 as in the vfx recipe (`blade_afterglow(tip, base, 2498, 2501)`): at 2498 the blade is a few pixels wide in the extreme wide; config wants "a low-angle MCU of the blade with only a few frames of afterglow" — the 4-frame fade is that shot.
- **D14 — the elder's second step plants at 3042** (bar 14.2) instead of 3040 (config "3010–3040"): both steps sit on the grid (3022 / 3042, two beats apart — unhurried); motion 3011–3042.

## 2. Beat grid (Act III, 140 BPM from 2497)

`config.beat_frame('act3', b)` = round(2497 + b · 10.2857); a bar = 41.14 f; 14 bars end exactly on 3073 (the finale's hard stop). Bar n, beat k (1–4) = `beat_frame('act3', 4·(n−1) + k−1)`. **Bold** = contacts / impacts (hits locked to the grid), *italics* = cut frames. The audio's `SPLIT_CUES` bends the act3 grid so that `low_point` sits on a bar line: 2950 is already bar 12.1 (2949.57 rounded), so nothing bends.

| bar | .1 | .2 | .3 | .4 |
|---|---|---|---|---|
| 1 | **2497** *S21a* RAIKIRI: bolt + cut + fork + pine split, flash, `music_cue` act3_start + raikiri | 2507 halves falling (to 2513), flames | 2518 (*S21b* 2509: blade MCU, afterglow 2509–2512) | 2528 (*S21c* 2521: act card starts) |
| 2 | 2538 shinobi stalking | 2548 card seal-impact 2545; elder lifts into hasso 2548→2580 | 2559 card legible 2551–2577 | 2569 |
| 3 | 2579 card fading (gone 2588) | 2590 shinobi's stalk ends | 2600 (*S22a* 2593) he advances | 2610 |
| 4 | **2620** A1 kesagiri blocked — FLASH (2605 flash = reveal, beat 10.5, a bolt ignores the bar) | 2631 | **2641** A2 rising cut deflected (spark-lit ECU) *S22c* 2623 | 2651 *S22d* 2644 |
| 5 | **2662** A3 horizontal, near-miss — FLASH + bolt | 2672 *S22e* 2665 | **2682** A4 thrust parried (spark-lit) | 2692 *S22f* 2685 |
| 6 | **2703** A5 heavy overhead blocked — FLASH + bolt, `clash_heavy` | 2713 *S22g* 2706 | **2723** A6 reverse diagonal deflected (sparks light his face) | 2734 *S22h* 2726 |
| 7 | **2744** A7 kesagiri, near-miss — FLASH (top-down) *S22i* 2747 | 2754 | **2764** A8 heavy overhead turned aside — FLASH, sparks stream to 2768 | 2775 *S22j* 2767 the opening |
| 8 | *2785 S22ba* steady storm light returns; the counter | **2795** S1 his diagonal cut | **2806** S2 his rising cut | 2816 *S22bb* 2809 |
| 9 | **2826** S3 lunging thrust deflected; master steps back (to 2838) *S22bc* 2829 | 2836 | 2847 master starts the jodan lift *S22bd* 2853 | 2857 |
| 10 | **2867** jodan set (hold) | 2878 *S23a* 2881 | 2888 the stand-off | 2898 |
| 11 | 2908 far thunder (sound only) | 2919 | **2929** the student launches his attack *S23b* 2926 | **2939** the master's cut begins |
| 12 | **2950** GROUNDED CUT: impact, spray ring, rain split, shockwave, `music_cue` low_point | 2960 (lands 2962) *S23c* 2953 | 2970 tumbling | 2980 up on one knee, skidding *S23d* 2973 |
| 13 | **2991** stops on one knee (sword planted 2986–2992) | **3001** head bowed — the low-point pose complete | 3011 master's step 1 lifts *S23e* 3010 | **3022** step 1 lands |
| 14 | 3032 step 2 lifts (3030) | **3042** step 2 lands (config: "3010–3040") | 3052 hold | 3063 hold → 3072; music hard-stops 3073 (finale) |

Rhythm: bars 1–3 are the lightning and the breath (the cut, then the card); bars 4–7 are the master's eight blows on every second beat (.1 / .3) — relentless, metronomic, "the elder presses"; bar 8 the student breaks the pattern with three quicker strikes on .2 / .3 / 9.1 (10, 20 f apart — his speed against the master's weight); bars 10–11 empty out (jodan, stand-off); the one great downbeat 12.1 is the low point; bars 13–14 are aftermath at walking pace.

## 3. Sub-cuts

Cut list (final; every block repeats its frames). φ = camera azimuth about the fighters' midpoint (0 = +X profile, −90 = behind the shinobi, +90 = behind the elder; |φ| < 90 = the legal +X side). All numbers: `geom_report.txt`, `summary.txt` (same directory). Contiguous 2497 → 3072, every cut 2–3 f after its contact.

| cut | frames | len | camera | lens | φ (f0→f1) | beat / story point |
|---|---|---|---|---|---|---|
| S21a | 2497–2508 | 12 | EXTREME wide, high (14 m) from the −Y/+X quadrant, locked, light shake | 18 | −42 | the bolt, the cut (2497), the fork to the pine, the split |
| S21b | 2509–2520 | 12 | low-angle MCU of the blade (lens 0.9 m up, 1.6 m from the edge) | 35 | +45 | afterglow 2509–2512, rain hissing on the steel |
| S21c | 2521–2592 | 72 | EXTREME low ultra-wide, sky 5/6 of the frame, locked | 16 | −2 → −9 | act card Act Three · Thunder; the student stalks in, the master into hasso |
| S22a | 2593–2622 | 30 | EXTREME wide, HIGH (16 m, −27°) over the steam ring, locked | 24 | −39 | strobe: 2605 bolt = reveal, 2620 flash = clash 1 |
| S22c | 2623–2643 | 21 | ECU of the blades (1.1 m), spark-lit | 65 | −31 → −22 | clash 2 (2641) |
| S22d | 2644–2664 | 21 | EXTREME low ultra-wide (lens 1.0 m, +17° up), bolt in frame | 16 | −23 → −20 | near-miss 2662 (flash + bolt) |
| S22e | 2665–2684 | 20 | OTS over the shinobi's RIGHT shoulder (0.9 m behind his head) | 45 | −73 | thrust parried past his ear (2682, spark-lit) |
| S22f | 2685–2705 | 21 | EXTREME wide profile, HIGH (15 m) from 44 m, bolt in frame | 35 | −1 | heavy overhead blocked 2703 (flash + bolt) |
| S22g | 2706–2725 | 20 | ECU of the elder's face, lit by the sparks of 2723 | 75 | +5 | reverse diagonal deflected (2723) |
| S22h | 2726–2746 | 21 | EXTREME top-down (30 m, −77°), locked | 35 | −1 → +1 | near-miss 2744 (flash): the sidestep seen from the sky |
| S22i | 2747–2766 | 20 | ECU: the heavy blow slides down his slanted blade | 40 | −26 | uke-nagashi 2764 (flash), sparks stream to 2768 |
| S22j | 2767–2784 | 18 | ECU of the shinobi's masked face / headband, blade rising past | 50 | −14 | the opening — he coils |
| S22ba | 2785–2808 | 24 | low profile wide, slow lateral dolly (+Y) — steady storm light returns | 24 | −3 | his strikes 2795, 2806 |
| S22bb | 2809–2828 | 20 | insert: the thrust meets the parry (1.1 m) | 60 | −10 → −22 | his thrust 2826 |
| S22bc | 2829–2852 | 24 | profile medium-wide, dolly +Y with the retreat | 28 | −8 → −3 | the master driven back a step |
| S22bd | 2853–2880 | 28 | OTS over the shinobi's RIGHT shoulder, looking up at the jodan | 35 | −71 | the master gathers into jodan (set 2867) |
| S23a | 2881–2925 | 45 | low profile wide, locked (stillness) | 20 | −8 → −7 | the stand-off in the rain |
| S23b | 2926–2952 | 27 | profile medium, locked, impact shake | 28 | −7 → −4 | his attack 2929, the grounded cut 2950 |
| S23c | 2953–2972 | 20 | wide, elevated (5 m, −25°), locked | 18 | −20 → −8 | spray ring; the blast throws him screen-left |
| S23d | 2973–3009 | 37 | DOWN THE CUT PLANE over the elder's LEFT shoulder (0.85 m off the plane) | 32 | +84 | the parted rain corridor; he tumbles to one knee (2991), sword planted, head bowed (3001) |
| S23e | 3010–3072 | 63 | profile wide two-shot, locked (stillness) | 22 | −4 → 0 | the master's two unhurried steps (3011–3042); hold |

21 cuts / 576 f = 27.4 f average: the strobe (S22, 9 cuts of 18–30 f) is the fastest cutting of the film; the lane opens (S21c 72 f) and closes (S23a 45 f, S23e 63 f) on long takes. Vocabulary (DIRECTION §3, Act III = extremes): 6 extreme wides (S21a, S21c, S22a, S22d, S22f, S22h), 6 ECU / inserts (S21b, S22c, S22g, S22i, S22j, S22bb), 2 OTS (S22e, S22bd), one axis-of-the-cut shot (S23d); the mediums are only where the geography must read (S22ba/bc, S23a–c, S23e). High angles (S21a, S22a, S22f, S22h, S23c) break up the low ones (S21b, S21c, S22d).

Shared conventions for every block
- `C = cameras`, `EV = events`, `ENV = environment`, `VFX = vfx`, `CH = characters`, `M = moves`, `U = bl_util`; `SH = SHINOBI_rig`, `SA = SAINT_rig`; `S(cut, i) = zlib.crc32(f"{cut}:{i}".encode())` (Pipeline rule 13 seeds).
- Every camera: `C.shot(cut_id, f0, f1, keys, dof=..., shake=..., handheld=..., subjects=..., framing=...)`; keys are `(frame, pos, look, lens)`; lenses are fixed per cut (no zooms). cameras.shot makes the last key CONSTANT.
- Screen numbers are NDC heads (x, y); "fig" = ground → head top as % of frame height, "vis" = the part above the local grass top (0.65 m stubble in the S11 crescent, 1.05–1.15 m elsewhere — §1).
- Every sword contact goes through `M.clash(attacker, defender, f, point)` (Pipeline rule 9: both `<C>_sword_ctrl` are placed so the blade segments cross at `point`; `end_lane` resolves ≤ 3–5 cm and emits the sparks + `clash` event). Spark colour (vfx.py): elder-initiated in Act III = `'steel'`, shinobi-initiated = `'white'`; heavy = `scale=1.6, count=90`. Explicit `VFX.sparks` lines in the blocks are EXTRA sparks only (never double the clash burst).
- Blade trails: `VFX.blade_trail('<C>_katana_tip', '<C>_katana_base', f0, f1, owner='saint'|'shinobi')` — the owner colour comes from `vfx.owner_color` (elder Act III steel-blue; shinobi cool white with a red core). Windows = the fast part of each swing only.
- Positions/poses: moves macros where SPEC has one (`M.slash`, `M.deflect`, `M.dodge`, `M.roll`, `M.skid`, `M.kneel`, `M.walk`, `M.stagger`), otherwise the local poses of §5 via `CH.pose_bones` / `CH.apply_pose`-style specs and `CH.key_sword` / `CH.key_blade_tip` for every blade position given in WORLD coordinates below.
- Key light: `ENV.set_sun(f0, az, el)` on each cut's first frame (CONSTANT; az = compass bearing from +Y clockwise: 0 = from +Y, 90 = from +X, 180 = from −Y, 270 = from −X) — always placed in front of the lens (rim/backlight on the rain, 150–170° from the lens axis, DIRECTION §6).
- Grass: default camera clearance (1.5, 4.0) everywhere; no overrides (`geom.py`: no camera is < 4 m (XY) from a character whose feet are on screen — the `framing_qa` grass warning never fires; the close cameras only see the fighters from the waist up).
- Wind: `ENV.set_wind(2497, 2.2)` (act2's value) → 1.4 at 2521 (the storm steadies) → 1.8 in the strobe (2593) → 1.2 at 2785 → 1.0 at 2881 → **0.5 at 2953** (after the blast the air goes still: the soaked headband tails HANG from S23, DIRECTION §7), direction 205 throughout. Secondary-motion springs reset on every cut marker (Pipeline rule 11).
- Hard cuts: every root / controller keyed CONSTANT on each cut's last frame when the next cut cheats (⟲ in §1).
- Steam-band clearance: every camera is either inside the ring (r ≤ 9.5 m from (0, 1.5); the band's dense core is r 10.6–11.4) or outside and high enough that the sight lines to both heads cross r = 11 at ≥ 4.9 m (S21a, S22a, S22f); S23c is inside (r 9.5) at 5 m; `geom.py` prints it.

### S21a — 2497–2508 (12 f) — RAIKIRI: the bolt is cut, the pine splits
Purpose: the legend in one image. A bolt comes down out of the storm onto the old master's raised sword — it never reaches him: it breaks at the blade and forks aside, one branch arching over the field into the lone pine, which splits and bursts into flame. The student is a tiny figure on the left. (Raikiri legend: he CUTS the bolt; he never channels, holds or throws lightning — the blade is already mid-cut on the first frame.)

Camera (EXTREME wide, 14 m up outside the steam ring, 18 mm, locked + a short thunder shake):
```python
C.shot("S21a", 2497, 2508,
       keys=[(2497, (22.0, -20.0, 14.0), (2.0, 8.0, 9.0), 18.0),
             (2508, (21.8, -19.8, 14.0), (2.0, 8.0, 9.0), 18.0)],      # 0.28 m drift: the frame "breathes"
       dof=None, handheld=0.0, shake=[(2497, 0.25, 8)], subjects=["shinobi", "saint"], framing="wide")
```
Screen (2497 → 2508): shinobi (−0.29, −0.71) fig 6.5 % (vis 4.0 %), elder (−0.14, −0.55) fig 6.2 % — tiny figures in the lower third, order OK, side sin −0.79. Horizon y +0.34 (storm sky = top third). The bolt enters the frame top at x ≈ −0.10 (25 m up it is at (−0.11, +1.30)) and comes down to the fork point FORK_AT → (−0.15, −0.48), just above the elder's head: **a bolt spanning the frame**. The main fork arches to the pine top (+0.32, +0.16) (pine base (+0.31, −0.19); the arch apex ≥ 0.34 × span above the chord, i.e. ≈ 10 m over the field); the short second fork plunges behind the elder to (−0.14, −0.57). Sight lines to the heads cross the steam band at 4.98 / 6.35 m (band top 4.5 m): the glowing ring lies below the figures as a ground ellipse, not a veil.

Action
- Elder (0.00, 3.00), facing 0, two-handed, IK sword. The swing from jodan happens ACROSS the S20b→S21a hard cut: on 2497 he is already in `raikiri_contact` (§5) — `CH.key_sword(SA, 2497, grip=(0.00, 2.72, 2.05), direction=(0.0, -0.42, 0.91), edge=(0.0, -0.91, -0.42), interp='LINEAR')` → tip (0.00, 2.35, 2.85); the struck point (u = 0.8 of the edge) is at (0.00, 2.42, 2.71), 0.1 m under FORK_AT. Body: hips_offset (0, −0.08, 0.04), spine (5, 0, 0), chest (−5, 0, 0), head (−18, 0, 0) (face up at the bolt); legs L (0.15, −0.40, 0.08) forward, R (−0.15, 0.30, 0.08). The cut continues through the channel: 2498 grip (0.00, 2.62, 1.75) dir (0.0, −0.88, 0.47); 2499 grip (0.00, 2.56, 1.45) dir (0.0, −0.99, −0.12); **2500 `raikiri_follow`** grip (0.00, 2.55, 1.30) dir (0.0, −0.94, −0.34) → tip (0.00, 1.73, 1.00) (a disciplined stop at waist height, not into the ground); head level (0, 0, 0) by 2500 (eyes on the student). Hold (zanshin) 2500–2530.
- Shinobi (0.00, −3.00) facing 180, two-handed chudan: recoils from the flash and the crack — 2498→2506 half step back to (0.00, −3.15), torso 8° back (spine (−8, 0, 0)), head turned 10° away (head (0, 0, 10)) 2498–2503, back to the guard by 2508 (sword tip stays toward the elder).

Clashes: none (the blade vs the bolt is the `raikiri` event, not `M.clash`). Environment
- `ENV.set_sun(2497, 250.0, 38.0)` (the storm key, default direction; it is dim — the flash does the work).
- `ENV.set_wind(2497, 2.2, direction_deg=205.0)`.
- Flash (the only one of S21): after the two vfx calls below, `ENV.flash(2497, 0.80, 2, tint=(0.70, 0.80, 1.0), direction=(338.0, 76.0))` — same frame as the vfx flashes → merged (max strength 0.80 ≈ 56 % of full white), keys the ENV_flash lamp to come from the bolt (az 338, el 76), cold blue. 2 frames: 2497 = 0.80, 2498 = 0.34 (envelope). VFX
```python
PINE_TOP = _local_pine_top()                         # ENV_pine bbox top - 0.3 m ≈ (6.00, 30.00, 10.20) (tree_strike's default pos)
bolt = VFX.lightning_bolt(2497, start=(-14.0, 34.0, 150.0), end=PINE_TOP, branches=4, duration=4, seed=S("S21a", 0),
                          fork_at=(0.00, 2.40, 2.80), fork_ends=[PINE_TOP, (-2.20, 5.00, 0.0)], fork_delay=0,
                          strength=120.0, flash=True, flash_strength=0.7, light=True, light_energy=4.0e4,
                          arch=0.34, guard="raise")      # fork 2: 3.4 m behind-right of the elder, away from the student
tree = VFX.tree_strike(2497, pos=None, seed=S("S21a", 1), split_deg=26.0, split_frames=16, flame=True,
                       flame_until=2592, steam_until=None, flash=True)   # halves fall 2497-2513; seam fire to 2592 (+20 f
                                                                         # dying); ember-lit steam plume to 3456
VFX.sparks(2497, (0.00, 2.42, 2.71), direction=(0.0, 0.3, 1.0), count=40, speed=5.0, life=6, color='white',
           scale=1.0, seed=S("S21a", 2), light=False)            # a spit of white sparks where the bolt meets the steel
VFX.blade_trail("SAINT_katana_tip", "SAINT_katana_base", 2497, 2500, owner="saint", strength=1.2)  # steel-blue arc of the cut
```
(The afterglow is NOT started here — it would be invisible at this scale; it starts on the S21b cut, §3 S21b / D13.) Events
```python
EV.emit(2497, "raikiri", pos=(0.00, 2.40, 2.80), who="saint", strength=1.0, tags=["raikiri"])
EV.emit(2497, "music_cue", cue="act3_start")
EV.emit(2497, "music_cue", cue="raikiri")
EV.emit(2497, "lightning_strike", pos=(0.00, 2.40, 2.80), strength=1.0)
EV.emit(2497, "thunder", distance="near", strength=1.0, pos=(0.0, 2.4, 20.0))   # the crack is on the frame (0 m)
EV.emit(2497, "whoosh", who="saint", weapon="katana", strength=0.9)
EV.emit(2498, "electric_crackle", duration=5, pos=(0.0, 2.4, 2.8))             # the bolt's own crackle (environmental)
EV.emit(2499, "tree_split", pos=(6.0, 30.0, 6.0), strength=1.0, tags=["tree_split"])   # 32 m away: +0.1 s
EV.emit(2500, "fire_burst", pos=(6.0, 30.0, 5.0), strength=0.6)
EV.emit(2500, "step", who="shinobi", strength=0.3)
```
Notes: everything decisive happens in 2497–2500 (flash 2 f, tubes flicker 4 f: stroke / dim / re-stroke / dim); 2501–2508 show the halves of the pine still opening and the first flames, the master frozen in zanshin, the student recovering. The pose jump jodan → contact across the 2496/2497 hard cut is clean with motion blur START (act2's strip holds to 2496.7, this lane's key at 2497 is CONSTANT-in → LINEAR out). `guard="raise"` makes a mis-placed fork fail the build instead of warning (vfx.py:). The pine top is ≥ 26 m from both fighters.

### S21b — 2509–2520 (12 f) — the blade: afterglow
Purpose: the proof, up close — the steel that cut lightning, its edge still glowing for a few frames and fading, rain hissing on it. Then the storm goes on.

Camera (low-angle MCU of the blade, lens 0.9 m above the ground, 1.6 m from the struck point, locked):
```python
C.shot("S21b", 2509, 2520,
       keys=[(2509, (1.55, 1.45, 0.90), (0.00, 2.20, 1.25), 35.0),
             (2520, (1.53, 1.42, 0.90), (0.00, 2.20, 1.27), 35.0)],
       dof=dict(focus="SAINT_katana_tip", fstop=2.0), handheld=0.08, subjects=["saint"], framing="mcu")
```
Screen: the blade crosses the frame on a falling diagonal — grip (+0.32, +0.04), struck point (−0.36, −0.48), tip (−0.55, −0.62); the elder's head soft in the upper right (+0.64, +0.64) (fig 204 %: belly-to-head fills the right half), facing screen-LEFT (toward the unseen student) ✓; side sin −0.32. Horizon y −0.93 (almost only sky and the master above the blade). The lens is in the S11 stubble (0.65 m) at 0.9 m: nothing between it and the blade.

Action
- Elder: holds `raikiri_follow` (grip (0.00, 2.55, 1.30), dir (0, −0.94, −0.34)); breathing only (chest 2° 2509→2516→2520); the tip settles 1 cm (2509→2520).
- Shinobi: off-screen at (0.00, −3.15). Environment: `ENV.set_sun(2509, 300.0, 28.0)` (in front of the lens: rims the blade's back and the rain); wind 2.2 → `ENV.set_wind(2521, 1.4)` keyed later. VFX
```python
VFX.blade_afterglow("SAINT_katana_tip", "SAINT_katana_base", 2509, 2512, color="afterglow", strength=2.0,
                    strike_u=0.8)                       # 1 -> 0.55 -> 0.25 -> 0 over 2509-2512, draws back to u 0.8
VFX.steam(2509, 2545, (0.00, 1.95, 1.10), 0.22, height=0.9, glow=False, density=0.35, rise=1.2, seed=S("S21b", 0))
for i, f in enumerate((2510, 2513, 2516, 2519)):         # drops flashing to vapour on the hot edge (tiny, no light)
    VFX.sparks(f, (0.00, 1.90 + 0.05 * i, 1.08), direction=(0.0, 0.0, 1.0), count=6, speed=1.2, life=6,
               color=(0.70, 0.75, 0.80), scale=0.3, seed=S("S21b", 1 + i), light=False, core=False)
```
Events: `EV.emit(2509, "steam_hiss", pos=(0.0, 1.95, 1.1), strength=0.5, duration=30)`. Notes: **D13** — the afterglow starts on this cut (2509), not at 2498 as in the vfx recipe: at 2498 the blade is 3 px wide in the extreme wide; here the 4-frame fade (vfx: "keep it 3–4 frames") is the shot. Hot white with a hint of blue, a LINE on the edge — no arcs, nothing leaves the blade (deny-list).

### S21c — 2521–2592 (72 f) — Act Three · Thunder (the act card)
Purpose: the breath after the miracle. Under an immense storm sky two small figures face each other across the steaming ring; the student starts to stalk in, the master lifts his sword into hasso. The act card sits in the dark clouds on the right.

Camera (EXTREME low ultra-wide, sky 5/6 of the frame, locked for the card):
```python
C.shot("S21c", 2521, 2592,
       keys=[(2521, (7.80, -0.30, 1.50), (0.00, 0.20, 4.00), 16.0),
             (2592, (7.80, -0.30, 1.50), (0.00, 0.20, 4.00), 16.0)],
       dof=None, handheld=0.0, subjects=["shinobi", "saint"], framing="wide")
```
Screen: shinobi (−0.41, −0.65) → (−0.33, −0.66) @2551 → (−0.23, −0.67) @2577 → (−0.17, −0.67) @2592 (fig 26–27 %, vis 15 % above the stubble), elder (+0.32, −0.61) all shot (fig 27–28 %), order OK, side sin −0.94 → −0.99. Horizon y −0.67; the far steam band (r 11, behind them at x ≈ −10.9) glows along the bottom with its top at y −0.32 … −0.29 — the brighter layer behind both silhouettes (DIRECTION §6). The pine is far off-frame right (NDC x +4.3). The hasso blade tip (−0.23, 2.92, 2.43) projects at (+0.30, −0.42): below the card's backdrop (y ≥ −0.292). Card clearance (backdrop x +0.356…+0.839, y −0.292…+0.704): **clear at 2551, 2564, 2577, 2592** (§6).

Action
- Elder (0.00, 3.00): zanshin to 2530; 2530→2548 straightens (hips_offset 0 → normal stance, blade to chudan: grip (−0.05, 2.62, 1.20), dir (0, −0.80, 0.60)); **2548→2580 lifts into `hasso`** (§5: fists at his right shoulder, blade near vertical, edge forward; grip world (−0.19, 2.81, 1.56), tip (−0.23, 2.92, 2.43)) — slow, 32 f; holds to 2592.
- Shinobi: 2521–2530 still in chudan at (0.00, −3.15); **2530→2590 stalks** in four slow, low steps (`M.walk(SH, 2530, 2590, (0.00, -3.15), (0.00, -1.25))`, stride 0.48 m, knees bent 25°, head centre 1.50, sword low chudan, feet planted 2536 / 2550 / 2564 / 2578); 2590–2592 settles. Environment: `ENV.set_sun(2521, 270.0, 30.0)` (from −X: in front of the lens, ≈ 165° from its axis — the rain and both silhouettes rim-lit); `ENV.set_wind(2521, 1.4)`. **No flash** in 2499–2604 (the card must not flicker; next flash 2605). VFX: none new (the pine's seam fire burns off-frame until 2592 and dies over 20 f; its steam plume stays). Events: `for f in (2536, 2550, 2564, 2578): EV.emit(f, "step", who="shinobi", strength=0.25)`; `EV.emit(2540, "thunder", distance="far", strength=0.5)` (the long roll after the raikiri — sound only); `EV.emit(2555, "wind_gust", strength=0.4)`. Notes: the card is legible 2551–2577 (titles.py); the only motion then is the student's slow stalk in the lower left and the master's hasso lift at the lower right, both ≥ 0.1 NDC below / left of the backdrop. Locked camera, no rack.

### S22 — shared: the strobe (2593–2784)
- **Light.** `ENV.set_param(2593, "key_pow", 0.15)`, `ENV.set_param(2593, "amb_str", 0.18)`, `ENV.set_param(2593, "fill_pow", 0.04)` (CONSTANT; storm_night has 0.60 / 0.55 / 0.12) → between flashes the frame is near-dark: silhouettes against the orange steam band, the pine's ember-lit steam plume (glow 1.3), sparks, blade trails and the slightly emissive red headband carry it. Restored by `ENV.set_state(2785, "storm_night")` (S22ba).
- **Flashes** (§4): 2605, 2620, 2662, 2703, 2744, 2764 — each one issued once through the vfx budget registry (`VFX.lightning_bolt(..., flash=True, flash_strength=s)` for the three visible bolts, `VFX.env_flash(f, s, 2)` for the in-cloud ones) and then re-keyed on the same frame with its direction: `ENV.flash(f, s, 2, direction=(az, el))` (same frame = merge, max strength). Poses **hold for 2 frames on every flash frame** (f, f+1: the blade and bodies keyed CONSTANT across f → f+1), then move on. (`VFX.strobe([...])` is NOT used: it adds random distant bolts.)
- **Wind** `ENV.set_wind(2593, 1.8)` (the storm gusts; the tails whip — they only hang from S23).
- **Blows** (the master, two-handed, every second beat): A1 2620 kesagiri · A2 2641 rising cut · A3 2662 horizontal (miss) · A4 2682 thrust · A5 2703 heavy overhead · A6 2723 reverse diagonal · A7 2744 kesagiri (miss) · A8 2764 heavy overhead turned aside. Trails: `VFX.blade_trail("SAINT_katana_tip", "SAINT_katana_base", a, b, owner="saint")` for each fast part (2614–2621, 2635–2642, 2656–2663, 2677–2683, 2697–2704, 2717–2724, 2738–2745, 2758–2769) — steel-blue; a flash freezes each arc for a frame. The student gets no trails in S22 (he only defends — his first trails are S22b).

### S22a — 2593–2622 (30 f) — two flashes: he comes in / the first blow
Purpose: the strobe is established in one locked extreme wide: darkness, a bolt → the student advancing on the master (tableau A); darkness; a flash → the blades crossed, sparks (tableau B). Then everything is close.

Camera (EXTREME wide, HIGH over the steam ring from the −Y/+X side, locked):
```python
C.shot("S22a", 2593, 2622,
       keys=[(2593, (22.0, -17.0, 16.0), (0.0, 2.0, 1.0), 24.0),
             (2622, (22.0, -17.0, 16.0), (0.0, 2.0, 1.0), 24.0)],
       dof=None, handheld=0.0, subjects=["shinobi", "saint"], framing="wide")
```
Screen: shinobi (−0.10, −0.05) → (−0.06, −0.02) @2605 → (−0.04, 0.00) @2620; elder (+0.03, +0.09) → (+0.02, +0.07); fig 7 % (vis 3–5 % above the stubble) — tiny, dead centre, inside the steam ring's glowing ellipse; order OK, side sin −0.81 → −0.78. Pitch −27°, no sky (horizon above the frame). The 2605 bolt strikes the far field at (−10, 34) → NDC (+0.40, +0.65), its channel entering at the top edge (x ≈ +0.58); the pine's steam plume leans in at the top-right corner (pine top (+0.82, +1.12)). Contact 2620 at (−0.02, +0.04). Sight lines cross the steam band at 6.5 / 7.5 m (clear).

Action
| frame | elder (root, facing 0) | shinobi (root, facing 180) |
|---|---|---|
| 2593 | (0.00, 3.00) `hasso` | (0.00, −1.20) low chudan |
| 2594→2605 | one step in → (0.00, 2.85), hasso | advances, quick low steps 2596 / 2601 / 2605 → (0.00, 0.05) |
| **2605–2606 HOLD** | hasso, front foot planted | mid-stride, blade forward-low (tableau A) |
| 2606→2612 | winds up: grip (−0.25, 2.62, 1.75), dir (−0.30, 0.35, 0.89) | closes → (0.00, 0.75), rising into a high left guard |
| 2612→2620 | **A1 kesagiri** from his right shoulder, step → (0.00, 2.55) | `M.deflect(SH, 2620, "mid_L")`: blade up on his left (−X), settles back → (0.00, 0.60) |
| **2620–2621 HOLD** | blade across at the contact | block at the contact (tableau B) |
| 2621→2622 | recoil begins | — |

Clash: `M.clash(SA, SH, 2620, (-0.20, 1.40, 1.58), strength=0.75)` → steel sparks (swing dir (0.55, −0.25, −0.80)). Environment: dim keys at 2593 (S22 shared); `ENV.set_sun(2593, 330.0, 35.0)` (beyond the pair, in front of the lens). Flashes: 2605 = the bolt (below), then `ENV.flash(2605, 0.60, 2, direction=(344.0, 70.0))`; 2620 = in-cloud: `VFX.env_flash(2620, 0.50, 2)` → `ENV.flash(2620, 0.50, 2, direction=(300.0, 55.0))`. VFX
```python
VFX.lightning_bolt(2605, start=(-14.0, 40.0, 160.0), end=(-10.0, 34.0, 0.0), branches=3, duration=3,
                   seed=S("S22a", 0), strength=90.0, flash=True, flash_strength=0.60, light=None, guard="raise")
VFX.blade_trail("SAINT_katana_tip", "SAINT_katana_base", 2614, 2621, owner="saint")
```
Events
```python
EV.emit(2605, "lightning_strike", pos=(-10.0, 34.0, 0.0), strength=0.8)
EV.emit(2607, "thunder", distance="near", strength=0.8)          # 35 m: +0.1 s
EV.emit(2616, "whoosh", who="saint", weapon="katana", strength=0.8)
EV.emit(2630, "thunder", distance="mid", strength=0.6)           # the in-cloud flash of 2620, heard late
for f in (2596, 2601, 2605): EV.emit(f, "step", who="shinobi", strength=0.35)
EV.emit(2600, "step", who="saint", strength=0.4)
```
Notes: two tableaux in ONE locked frame is the strobe's grammar ("each flash reveals a new tableau"): the figures "jump" between flashes because the frames between are near-dark. Cut 2623 = 3 f after the contact.

### S22c — 2623–2643 (21 f) — ECU: the second blow, lit by its sparks
Purpose: close to the steel in the dark — the last sparks of blow 1 falling, then the master's rising cut meets the student's low parry; the burst of sparks is the only light.

Camera (ECU of the blades, 1.1 m from the contact, locked):
```python
C.shot("S22c", 2623, 2643,
       keys=[(2623, (1.30, 0.75, 1.05), (0.20, 1.12, 1.15), 65.0),
             (2643, (1.30, 0.75, 1.05), (0.20, 1.12, 1.15), 65.0)],
       dof=dict(focus=(0.22, 1.10, 1.10), fstop=2.8), handheld=0.15, subjects=[], framing="ecu")
```
Screen: frame width ≈ 0.6 m at the contact; contact 2641 at (−0.04, −0.36); both heads above the frame (shinobi (−1.8…−2.8, +2.1…+2.4), elder (+2.1…+2.5, +1.9…+2.0)) — the check still sees them "near the view": side sin −0.99 → −0.94 ✓. The student's blade enters from the left, the master's from the right/below (the camera's right ≈ +Y). Action
- 2623 (elder (0.00, 2.55), shinobi (0.00, 0.60)): the blades part after A1, the master's blade ending low at his left (+X); 2629→2635 the master turns the wrists (blade low, edge up); **2635→2641 A2 rising cut** from his left-low up toward his right-high, step → (0.00, 2.25); the student drops his blade to a low guard on his right (+X) and parries (`M.deflect(SH, 2641, "low")` variant: tip down-right), giving 0.3 m → (0.00, 0.30). **2641–2642 HOLD**. Clash: `M.clash(SA, SH, 2641, (0.22, 1.10, 1.10), strength=0.7)` → steel sparks (dir (−0.45, −0.25, 0.85)). No flash: the spark light (40 W, 3 f) is the lighting of the cut. Environment: `ENV.set_sun(2623, 270.0, 25.0)` (behind the blades from this lens: rims both edges against the steam glow). VFX: `VFX.blade_trail(... 2635, 2642, owner="saint")`. Events: `EV.emit(2637, "whoosh", who="saint", weapon="katana", strength=0.7)`; `EV.emit(2641, "step", who="shinobi", strength=0.3)`.

### S22d — 2644–2664 (21 f) — the horizontal cut misses (flash + bolt)
Purpose: scale and danger: under the whole storm sky, a bolt cracks into the field on the left as the master's horizontal cut sweeps just short of the leaping student.

Camera (EXTREME low ultra-wide, lens 1.0 m above the stubble, 17.5° up, locked):
```python
C.shot("S22d", 2644, 2664,
       keys=[(2644, (7.6, -1.6, 1.0), (0.0, 1.6, 3.6), 16.0),
             (2664, (7.6, -1.6, 1.0), (0.0, 1.6, 3.6), 16.0)],
       dof=None, handheld=0.1, subjects=["shinobi", "saint"], framing="wide")
```
Screen: shinobi (−0.11, −0.53) → (−0.17, −0.53) @2662, elder (+0.09, −0.50) → (+0.07, −0.50); fig 23–24 %, vis 13–15 %; order OK, side sin −0.96 → −0.98. Horizon y −0.66, sky 80 % of the frame; the far steam band behind them (−0.22, −0.54). The bolt strikes the field at (−38, −14) → (−0.74, −0.72) (40 m from the pair), its channel entering the top at x ≈ −0.57: a vertical crack of light on the left third, the tiny pair lower centre. Action
| frame | elder | shinobi |
|---|---|---|
| 2644 ⟲ | (0.00, 2.55) | (0.00, 0.60) guard |
| 2648→2656 | draws the blade back to his right hip, horizontal, pointing back (+Y) | holds, blade centred |
| 2656→2662 | **A3 horizontal cut** right → left at chest height, step → (0.00, 2.30); blade straight at him at 2662 (`yoko`, §5: tip at world y 0.87, z 1.25) | leaps back → (0.00, 0.05) (root z 0.18 at 2659), arched back (spine −20°, head −15°), blade upright in front |
| **2662–2663 HOLD** | blade fully extended, tip ≈ 0.75 m short of the student's chest (where his chest was at 2656) | mid-leap, arched (tableau) |
| 2663→2664 | follow-through | lands (0.00, 0.02) |
Clash: none (near-miss). Environment: `ENV.set_sun(2644, 270.0, 30.0)`; flash via the bolt, then `ENV.flash(2662, 0.55, 2, direction=(250.0, 62.0))`. VFX
```python
VFX.lightning_bolt(2662, start=(-50.0, -20.0, 170.0), end=(-38.0, -14.0, 0.0), branches=3, duration=3,
                   seed=S("S22d", 0), strength=90.0, flash=True, flash_strength=0.55, light=None, guard="raise")
VFX.blade_trail("SAINT_katana_tip", "SAINT_katana_base", 2656, 2663, owner="saint")   # the flash freezes the arc
VFX.sparks(2664, (0.0, 0.02, 0.05), direction=(0.0, -1.0, 0.3), count=20, speed=2.0, life=10,
           color=(0.60, 0.65, 0.70), scale=0.4, seed=S("S22d", 1), light=False, core=False)   # water off his landing
```
Events: `EV.emit(2657, "whoosh", who="saint", weapon="katana", strength=0.9)`; `EV.emit(2662, "lightning_strike", pos=(-38.0, -14.0, 0.0), strength=0.8)`; `EV.emit(2665, "thunder", distance="near", strength=0.8)`; `EV.emit(2656, "jump", who="shinobi", strength=0.4)`; `EV.emit(2664, "land", who="shinobi", strength=0.4)`.

### S22e — 2665–2684 (20 f) — the thrust, past his ear
Purpose: from behind the student: the master's thrust comes straight at him (and at us) and is beaten aside at the last moment — the blade slides past his right ear toward the lens in a burst of sparks.

Camera (OTS over the shinobi's RIGHT shoulder, 0.9 m behind his head, locked + a creep of 0.1 m):
```python
C.shot("S22e", 2665, 2684,
       keys=[(2665, (0.62, -0.55, 1.62), (-0.05, 1.30, 1.45), 45.0),
             (2684, (0.62, -0.65, 1.62), (-0.05, 1.20, 1.45), 45.0)],
       dof=dict(focus=(SA, "head"), fstop=2.8), handheld=0.2, subjects=["shinobi", "saint"], framing="ots")
```
Screen: the student's head/right shoulder big at the left (−0.65, −0.27) → (−0.75, −0.20) (fig ≈ 400 %, soft); the master waist-up (+0.39, +0.55) → (+0.33, +0.42) (fig 158–170 %), facing screen-left; contact 2682 at (+0.06, −0.28) between them. Order OK, side sin −0.57 → −0.60. Action
| frame | elder | shinobi |
|---|---|---|
| 2665 ⟲ | (0.00, 2.60) | (0.00, 0.35) |
| 2670→2677 | draws back for the thrust: blade level at the student's chest, fists at his right hip | holds, blade centred |
| 2677→2682 | **A4 thrust**, lunge → (0.00, 2.15) | rising sweep to his right (+X), steps back → (0.00, 0.20) |
| **2682–2683 HOLD** | blade extended, deflected | parry at the contact |
| 2683→2684 | the deflected blade slides past his right ear toward the lens, tip stops at (0.35, 0.15, 1.55) (0.7 m from the lens) | head turns 10° away |
Clash: `M.clash(SA, SH, 2682, (0.10, 1.00, 1.40), strength=0.7)` → steel sparks toward the lens side (dir (0.70, −0.55, 0.20)). No flash (spark-lit). Environment: `ENV.set_sun(2665, 10.0, 25.0)` (from +Y, behind the master = in front of the lens). VFX: `VFX.blade_trail(... 2677, 2683, owner="saint")`. Events: `EV.emit(2678, "whoosh", who="saint", weapon="katana", strength=0.7)`; `EV.emit(2679, "step", who="saint", strength=0.5)`.

### S22f — 2685–2705 (21 f) — the heavy blow blocked (flash + bolt)
Purpose: the weight of the old man: seen from far and high, the whole arena lit by a bolt behind them — his two-handed overhead crashes onto the student's raised blade and drives him down.

Camera (EXTREME wide profile, 15 m up at 44 m, locked, light thunder shake):
```python
C.shot("S22f", 2685, 2705,
       keys=[(2685, (44.0, 1.0, 15.0), (0.0, 1.5, 2.0), 35.0),
             (2705, (44.0, 1.0, 15.0), (0.0, 1.5, 2.0), 35.0)],
       dof=None, handheld=0.0, shake=[(2703, 0.2, 6)], subjects=["shinobi", "saint"], framing="wide")
```
Screen: shinobi (−0.04, −0.05), elder (+0.04, −0.04) (fig 7–8 %, vis 4–5 %), order OK, side sin −1.00. The far arc of the steam ring glows across the frame at y ≈ +0.45 (behind them); the near arc passes below. The bolt strikes the far field at (−52, 12) → (+0.20, +0.61), channel from the top at x ≈ +0.26: directly behind the pair. Contact (−0.03, −0.03). Sight line to the elder crosses the band at 4.94 m (above its 4.5 m top). Action
| frame | elder | shinobi |
|---|---|---|
| 2685 ⟲ | (0.00, 2.50) | (0.00, 0.55) |
| 2688→2697 | raises the sword high overhead in one sweep (both fists above the forehead, blade back 30°) | raises a horizontal overhead block (`M.deflect(SH, 2703, "overhead_block")`) |
| 2697→2703 | **A5 heavy overhead** (men), step → (0.00, 2.40) | knees give: head 1.50 → 1.33 |
| **2703–2704 HOLD** | blade on the block | pressed down (tableau) |
| 2704→2705 | bears down (bind) | holds |
Clash: `M.clash(SA, SH, 2703, (0.00, 0.85, 1.70), strength=0.95)` + heavy sparks (`scale=1.6, count=90`, spread 110, dir (0, −0.2, −0.9) — they fountain sideways off the horizontal block); event `clash_heavy`. Environment: `ENV.set_sun(2685, 270.0, 30.0)`; flash via the bolt, then `ENV.flash(2703, 0.65, 2, direction=(283.0, 60.0))`. VFX
```python
VFX.lightning_bolt(2703, start=(-70.0, 20.0, 160.0), end=(-52.0, 12.0, 0.0), branches=4, duration=4,
                   seed=S("S22f", 0), strength=110.0, flash=True, flash_strength=0.65, light=None, guard="raise")
VFX.blade_trail("SAINT_katana_tip", "SAINT_katana_base", 2697, 2704, owner="saint")
```
Events: `EV.emit(2698, "whoosh", who="saint", weapon="katana", strength=1.0)`; `EV.emit(2703, "clash_heavy", pos=(0.0, 0.85, 1.70), strength=0.95)` (only if `M.clash` emits plain `clash` — never both, events.audit flags duplicates); `EV.emit(2703, "lightning_strike", pos=(-52.0, 12.0, 0.0), strength=0.9)`; `EV.emit(2707, "thunder", distance="near", strength=0.9)`; `EV.emit(2699, "step", who="saint", strength=0.6)`.

### S22g — 2706–2725 (20 f) — the master's face in spark-light
Purpose: the one face of the strobe: the old master, rain streaming down his brow and beard, relentless — lit from below for three frames by the sparks of the next blow.

Camera (ECU of the elder's face, tracking the head, 75 mm):
```python
C.shot("S22g", 2706, 2725,
       keys=[(2706, (1.30, 1.70, 1.66), (SA, "head"), 75.0), (2715, (1.30, 1.55, 1.65), (SA, "head"), 75.0),
             (2723, (1.30, 1.40, 1.64), (SA, "head"), 75.0), (2725, (1.30, 1.40, 1.64), (SA, "head"), 75.0)],
       dof=dict(focus=(SA, "head"), fstop=2.0), handheld=0.15, subjects=["saint"], framing="ecu")
```
Screen (point-aim equivalent in `geom.py`): head (0.00, −0.13) → (0.00, −0.06), fig ≈ 540 % (the head fills ≈ 70 % of the frame height), facing screen-LEFT ✓; side sin −0.76. The contact of 2723 is 0.6 m from the lens, off-frame lower left: the sparks spray through the foreground bokeh and light his face for 3 f. Action: elder 2706 ⟲ (0.00, 2.55); 2708→2716 winds up high on his left (+X); **2716→2723 A6 reverse diagonal** (gyaku-kesa, +X high → −X low), step → (0.00, 2.25); head steady, chin down 5°, beard cord swinging (secondary); 2723–2724 HOLD. Shinobi (off-frame) 2706 ⟲ (0.00, 0.60) → (0.00, 0.30): `M.deflect(SH, 2723, "mid_R")` high on his right. Clash: `M.clash(SA, SH, 2723, (0.25, 1.10, 1.50), strength=0.75)` → steel sparks dir (0.55, 0.45, −0.20), spread 70 (some fly past the lens). No flash. Environment: `ENV.set_sun(2706, 330.0, 20.0)` (from behind him, rim on the shaven head and beard). VFX: `VFX.blade_trail(... 2717, 2724, owner="saint")` (a streak crossing the foreground). Events: `EV.emit(2718, "whoosh", who="saint", weapon="katana", strength=0.8)`.

### S22h — 2726–2746 (21 f) — from the sky: the sidestep (flash)
Purpose: the god's-eye tableau: the flash reveals the whole field from above — the grass sea, the glowing ring of steam, the burnt annulus and Act I's sheared crescent (the fight's history on the ground), two tiny figures, the master's blade through empty air where the student stood.

Camera (EXTREME top-down, 30 m up, −77°, locked; image-up = −X, so +Y = screen-right):
```python
C.shot("S22h", 2726, 2746,
       keys=[(2726, (7.0, 1.5, 30.0), (0.0, 1.5, 0.0), 35.0),
             (2746, (7.0, 1.5, 30.0), (0.0, 1.5, 0.0), 35.0)],
       dof=None, handheld=0.0, subjects=["shinobi", "saint"], framing="wide")
```
Screen: shinobi (−0.06, +0.05) → (−0.07, −0.02) @2744 (the sidestep moves him down-screen = +X), elder (+0.07, +0.06); fig ≈ 3 % (tiny); order OK, side sin −0.99 → −1.00. The ring crosses the frame: its −Y / +Y points at x ∓0.69 (its ±X arcs are just off the top / bottom). XY distance lens → fighters ≥ 6.6 m, so `framing_qa` raises no grass warning. Action: elder 2726 ⟲ (0.00, 2.55); 2730→2738 hasso wind-up; **2738→2744 A7 kesagiri** → (0.00, 2.35), tip ends at (−0.15, 0.85, 0.75); student 2726 ⟲ (0.00, 0.60); `M.dodge(SH, 2740, "right")` → (0.50, 0.40) facing 185 by 2744. **2744–2745 HOLD** (the blade through the empty space at his side). Near-miss. Environment: `ENV.set_sun(2726, 250.0, 38.0)`; `VFX.env_flash(2744, 0.50, 2)` → `ENV.flash(2744, 0.50, 2, direction=(200.0, 80.0))` (from almost overhead: short shadows). VFX: `VFX.blade_trail(... 2738, 2745, owner="saint")`. Events: `EV.emit(2739, "whoosh", who="saint", weapon="katana", strength=0.9)`; `EV.emit(2741, "step", who="shinobi", strength=0.4)`; `EV.emit(2752, "thunder", distance="mid", strength=0.6)`.

### S22i — 2747–2766 (20 f) — the heavy blow turned aside (flash)
Purpose: the turn of the fight, in one ECU: the master's heaviest overhead meets the student's slanted blade and SLIDES off it in a stream of sparks — the blow is wasted, the master over-committed.

Camera (ECU of the slanted blade, 1.2–1.7 m, locked):
```python
C.shot("S22i", 2747, 2766,
       keys=[(2747, (1.40, 0.75, 1.40), (-0.05, 1.07, 1.31), 40.0),
             (2766, (1.40, 0.75, 1.40), (-0.05, 1.07, 1.31), 40.0)],
       dof=dict(focus=(0.0, 1.07, 1.31), fstop=4.0), handheld=0.15, subjects=[], framing="ecu")
```
Screen: the contact starts at (−0.13, +0.72) (2764) and slides down to (+0.09, −0.55) (2768): the spark line crosses the frame top → bottom; the student's masked head in at the left edge (−0.91, +0.41), the master off-right (+1.8); side sin −1.00. Action
| frame | elder | shinobi |
|---|---|---|
| 2747 ⟲ | (0.00, 2.50) | (0.45, 0.55) facing 183 → 180 by 2752 |
| 2750→2758 | heavy overhead wind-up (both fists above the head) | sets the slanted guard (`uke_nagashi`, §5): fists at his right temple, grip (0.20, 0.90, 1.60), dir (−0.60, 0.40, −0.69) → tip (−0.25, 1.20, 1.08); root → (0.25, 0.55) |
| 2758→2764 | **A8 overhead** comes down | holds the slant |
| **2764–2765 HOLD** (flash) | blade meets the slant near its forte (0.11, 0.96, 1.50) | — |
| 2764→2768 | his blade slides down the slant to its tip (−0.22, 1.18, 1.12) and off to the student's left (−X), on to the ground at (−0.45, 1.30, 0.15) by 2770: hips low, torso bent 45° — guard open | turns the wrists outward as it slides |
Clash: `M.clash(SA, SH, 2764, (0.11, 0.96, 1.50), strength=0.85)`; the slide: extra sparks `for i, f in enumerate((2765, 2766, 2767)): VFX.sparks(f, p_i, direction=(-0.6, 0.3, -0.7), count=25, speed=3.0, life=8, color='steel', seed=S("S22i", i), light=(i == 1))` with p_i = (0.11, 0.96, 1.50) + i/3 · ((−0.22, 1.18, 1.12) − (0.11, 0.96, 1.50)) — a streaming line of sparks along his blade. (The slide past 2766 continues in S22j off-frame.) Environment: `ENV.set_sun(2747, 300.0, 30.0)`; `VFX.env_flash(2764, 0.45, 2)` → `ENV.flash(2764, 0.45, 2, direction=(250.0, 45.0))`. VFX: `VFX.blade_trail(... 2758, 2769, owner="saint")`. Events: `EV.emit(2759, "whoosh", who="saint", weapon="katana", strength=1.0)`; `EV.emit(2765, "blade_lock", duration=4, strength=0.6)` (the scrape); `EV.emit(2770, "hit", pos=(-0.45, 1.30, 0.1), strength=0.4)` (the blade striking the mud, off-frame); `EV.emit(2780, "thunder", distance="far", strength=0.5)`.

### S22j — 2767–2784 (18 f) — the opening
Purpose: the student's eyes: he sees the master open — and his blade rises. The last frame of the strobe.

Camera (ECU of the masked face from his front-right, 1.0 m, locked):
```python
C.shot("S22j", 2767, 2784,
       keys=[(2767, (0.85, 1.35, 1.52), (SH, "head"), 50.0), (2784, (0.85, 1.35, 1.52), (SH, "head"), 50.0)],
       dof=dict(focus=(SH, "head"), fstop=2.0), handheld=0.1, subjects=["shinobi"], framing="ecu")
```
Screen (point-aim equivalent): face (−0.08, −0.13) → (0.00, −0.13), fig ≈ 500 %; he faces screen-RIGHT ✓; the master is behind the lens (off-frame); side sin −0.73 → −0.76. Behind him: the −Y arc of the steam band glowing (rim). Action: shinobi (0.20, 0.60) → (0.15, 0.65): 2767–2772 still, eyes forward (the head turns 5° toward the lens = toward the open master); **2772→2782 furikaburi** — from the slant he circles the blade up and over his head (the steel crosses the frame in front of his face 2774–2778, flicking water), poised high by 2784; the soaked red headband tails lift with the motion (whipping, wind 1.8). Elder (off-frame) recovering: (0.00, 2.48) → (0.00, 2.45), blade dragging up from the mud on his left. Clash: none. Environment: `ENV.set_sun(2767, 190.0, 20.0)` (from −Y behind him). VFX: water flicked off the rising blade — `VFX.sparks(2776, "SHINOBI_katana_tip", direction=(0.0, 0.0, 1.0), count=12, speed=2.5, life=8, color=(0.65, 0.70, 0.75), scale=0.35, seed=S("S22j", 0), light=False, core=False)`. Events: `EV.emit(2775, "whoosh", who="shinobi", weapon="katana", strength=0.4)`.

### S22b — shared: the counter (2785–2880)
- **Light back**: `ENV.set_state(2785, "storm_night")` (CONSTANT: the full storm snapshot — undoes the S22 dim) — the student's counter is the first action seen in steady light, lit by the storm key + the steam band. **No flash** in S22b (the lightning "pauses" while he takes the initiative; next flash is the finale's 3265).
- `ENV.set_wind(2785, 1.2)`.
- **His trails** (owner colour: cool white with a red core): `VFX.blade_trail("SHINOBI_katana_tip", "SHINOBI_katana_base", a, b, owner="shinobi")` for 2789–2796, 2800–2807, 2819–2827; the master's parries get short steel-blue trails only on the jodan lift 2847–2866 (none on the blocks).
- **Sparks** are the student's: `'white'` (shinobi-initiated).

### S22ba — 2785–2808 (24 f) — two strikes
Purpose: the tide turns: in steady light, the student attacks — a diagonal cut, a rising cut, fast — and the master, parrying, gives ground for the first time.

Camera (low profile wide, 1.45 m, slow lateral dolly +Y with the push):
```python
C.shot("S22ba", 2785, 2808,
       keys=[(2785, (8.2, 1.2, 1.45), (0.0, 1.7, 1.55), 24.0),
             (2808, (8.2, 1.6, 1.45), (0.0, 2.0, 1.55), 24.0)],
       dof=None, handheld=0.1, subjects=["shinobi", "saint"], framing="wide")
```
Screen: shinobi (−0.17, −0.03) → (−0.14, −0.05), elder (+0.12, −0.01) → (+0.16, +0.03); fig 30–34 % (vis 13–19 % above the stubble: both visible from the knees up); order OK, side sin −1.00. Horizon −0.04. The far steam band (x −10.9) glows directly behind both figures at y ≈ +0.08 (its 2.2 m mid-height) — the brighter layer behind the silhouettes. Strike 1 contact at (+0.02, 0.00), strike 2 at (+0.05, −0.15). Action
| frame | shinobi | elder |
|---|---|---|
| 2785 | (0.15, 0.65), blade high (from S22j) | (0.00, 2.45), recovering from the over-committed blow: blade low on his left (+X)… rising |
| 2785→2795 | **S1 diagonal cut** from his right-high (+X) down to his left, step in → (0.10, 0.90) | brings the blade up to a vertical block on his LEFT (+X), steps back → (0.00, 2.70) |
| 2795 | contact (0.20, 1.80, 1.55) | parry |
| 2795→2806 | **S2 rising cut** from his left-low (−X) up to his right, step → (0.05, 1.10) | block low on his right (−X), steps back → (0.00, 2.95) |
| 2806 | contact (−0.20, 2.05, 1.15) | parry |
| 2806→2808 | recoils into the thrust coil (blade drawn back along his right side, tip forward) | — |
Clashes: `M.clash(SH, SA, 2795, (0.20, 1.80, 1.55), strength=0.65)`, `M.clash(SH, SA, 2806, (-0.20, 2.05, 1.15), strength=0.65)` → white sparks (swing dirs (−0.6, 0.3, −0.7) and (0.6, 0.3, 0.7)). Environment: `ENV.set_sun(2785, 270.0, 30.0)` (from −X, in front of the lens: rims both and backlights the rain). VFX: `VFX.blade_trail(... "SHINOBI" ..., 2789, 2796, owner="shinobi")`, `(... 2800, 2807, owner="shinobi")`. Events: `EV.emit(2790, "whoosh", who="shinobi", weapon="katana", strength=0.7)`; `EV.emit(2801, "whoosh", who="shinobi", weapon="katana", strength=0.7)`; steps: shinobi 2791, 2802; saint 2794, 2805 (strength 0.4).

### S22bb — 2809–2828 (20 f) — the thrust (insert)
Purpose: the third strike, close: the student's lunging thrust arrives at the master's chest and is swept aside at the last hand's breadth — white sparks.

Camera (insert on the thrust line from the +X side, 1.0–1.6 m, locked):
```python
C.shot("S22bb", 2809, 2828,
       keys=[(2809, (1.00, 1.90, 1.45), (0.0, 2.55, 1.45), 60.0),
             (2828, (1.00, 1.95, 1.45), (0.0, 2.60, 1.45), 60.0)],
       dof=dict(focus=(0.10, 2.40, 1.40), fstop=2.8), handheld=0.2, subjects=[], framing="insert")
```
Screen: thrust contact 2826 at (−0.23, −0.38); the master's head in the upper-right corner at 2809 (+0.84, +0.92), then out as he leans back; the student's blade enters from the left. Side sin −0.81 → −0.93. Action: shinobi 2809→2819 coils (blade drawn back, tip forward at chest height, weight back); **2819→2826 S3 lunging thrust** → (0.00, 1.55) (front knee deep, head 1.38); elder (0.00, 2.95) → (0.00, 3.15): sweeps it to his left (+X) at 2826 and leans back; 2826–2828 the deflected blade passes his left side. Clash: `M.clash(SH, SA, 2826, (0.10, 2.40, 1.40), strength=0.8)` → white sparks (dir (0.4, 0.8, 0.1)). Environment: `ENV.set_sun(2809, 300.0, 25.0)`. VFX: `VFX.blade_trail(... 2819, 2827, owner="shinobi")`. Events: `EV.emit(2820, "whoosh", who="shinobi", weapon="katana", strength=0.8)`; `EV.emit(2821, "dash", who="shinobi", strength=0.5)`.

### S22bc — 2829–2852 (24 f) — driven back a step
Purpose: the geography of the counter: the master steps back — screen-right — a full step, and begins to gather himself; the student recovers from the lunge and holds.

Camera (profile medium-wide, dolly +Y 0.5 m with the retreat):
```python
C.shot("S22bc", 2829, 2852,
       keys=[(2829, (7.0, 1.4, 1.35), (0.0, 2.4, 1.60), 28.0),
             (2852, (7.0, 1.9, 1.35), (0.0, 2.7, 1.60), 28.0)],
       dof=None, handheld=0.1, subjects=["shinobi", "saint"], framing="wide")
```
Screen: shinobi (−0.20, −0.10) → (−0.36, −0.02), elder (+0.17, +0.01) → (+0.17, +0.05); fig 40–47 %; order OK, side sin −1.00 → −0.99 (the gap opens from 0.37 to 0.53 NDC). Action: elder 2829→2838 **one full step back** (right foot first) → (0.00, 3.40), blade returning to chudan; 2838→2852 begins to raise the sword (fists rising past the chest: grip (−0.02, 3.20, 1.45) at 2852) with the left foot sliding back (the half step starts 2846); shinobi 2829→2850 recovers from the lunge → (0.00, 1.10), chudan, head 1.55. Environment: `ENV.set_sun(2829, 270.0, 28.0)`. Events: `EV.emit(2833, "step", who="saint", strength=0.5)`, `EV.emit(2838, "step", who="saint", strength=0.4)`, `EV.emit(2840, "step", who="shinobi", strength=0.3)`.

### S22bd — 2853–2880 (28 f) — he gathers into jodan
Purpose: the master raises his sword into jodan again — the same stance that met the lightning; seen past the student's shoulder, looking up: the stance is a wall.

Camera (OTS over the shinobi's RIGHT shoulder, 1.7 m, looking up +4°, slow creep):
```python
C.shot("S22bd", 2853, 2880,
       keys=[(2853, (1.30, -1.50, 1.70), (-0.25, 4.0, 2.10), 35.0),
             (2880, (1.30, -1.35, 1.70), (-0.25, 4.0, 2.15), 35.0)],
       dof=dict(focus=(SA, "head"), fstop=2.8), handheld=0.1, subjects=["shinobi", "saint"], framing="ots")
```
Screen: the student's head/shoulder lower left (−0.37, −0.56) → (−0.41, −0.63) (fig 140–149 %, soft), the master centred (+0.04, −0.32) → (+0.05, −0.35) (fig 83–85 %); the jodan tip rises to (+0.08, +0.47) at 2868; order OK, side sin −0.45 → −0.47. Action: elder (0.00, 3.40) → half step back → (0.00, 3.60) by 2860; **2847→2867 lifts into `jodan`** (act2 §5 spec: grip rig (−0.02, −0.12, 2.00), dir (0, 0.70, 0.71), two-handed; tip world (−0.02, 4.09, 2.62)); set on bar 10 (2867); holds 2867–2880, rain running off the raised blade. Shinobi (0.00, 1.10) chudan, still (breathing). Environment: `ENV.set_sun(2853, 10.0, 22.0)` (from +Y behind the master: his silhouette + the raised blade rimmed). VFX: `VFX.blade_trail("SAINT_katana_tip", "SAINT_katana_base", 2850, 2866, owner="saint", strength=0.6)` (a slow faint arc — the lift, not a strike); drops off the blade: `for f in (2870, 2875, 2879): VFX.sparks(f, "SAINT_katana_tip", direction=(0.0, 0.0, -1.0), count=5, speed=1.0, life=10, color=(0.65, 0.70, 0.75), scale=0.3, seed=S("S22bd", f), light=False, core=False)`. Events: `EV.emit(2852, "whoosh", who="saint", weapon="katana", strength=0.35)`; `EV.emit(2856, "step", who="saint", strength=0.3)`. Notes: no lightning with the jodan (act2's rule: "a stance, not a summoning").

### S23 — shared: the low point (2881–3072)
- Real time, **no flash, no glow**: storm_night (restored at 2785), rain 1.0; the only "effects" are water and air.
- `ENV.set_wind(2881, 1.0)` → `ENV.set_wind(2953, 0.5)` (after the blast the air goes still; wet + low wind = the soaked headband tails hang from here, DIRECTION §7).
- The grounded cut (IMPACT = (0.00, 1.75, 0.00), 2950):
```python
VFX.spray_ring(2950, (0.00, 1.75, 0.00), radius=4.0, seed=S("S23b", 0))      # crown of lit drops, 90 % above 1.3 m
VFX.rain_split(2950, 3010, plane_origin=(0.00, 3.45, 0.00), plane_normal=(1.0, 0.0, 0.0), width=2.2, length=22.0,
               height=12.0, direction=(0.0, -1.0, 0.0), seed=S("S23b", 1), sheet=True, mist=True)
               # vfx.py recipe: origin = the elder, corridor toward the student; mist/sheet mark the cut 2951-2957,
               # clear corridor ~2965-3000, refill from the top reaches the ground at 3010
VFX.sparks(2950, (0.00, 1.75, 0.05), direction=(0.0, -0.3, 1.0), count=60, speed=5.0, life=12,
           color=(0.55, 0.50, 0.45), scale=1.2, seed=S("S23b", 2), light=False, core=False)   # mud + water thrown up
```
  (no `shockwave` — it is a DRY dust ring; no `dust_burst` — everything is soaked.)
- Events at the impact (emit these BEFORE the 3001 pose event):
```python
EV.emit(2950, "music_cue", cue="low_point")
EV.emit(2950, "shockwave", pos=(0.00, 1.75, 0.3), strength=1.0, tags=["low_point"])
EV.emit(2950, "rain_split", pos=(0.00, 1.75, 1.5), strength=1.0, tags=["low_point"])
EV.emit(2950, "hit", pos=(0.00, 1.75, 0.0), strength=1.0)               # the blade into the flooded ground
```

### S23a — 2881–2925 (45 f) — the stand-off in the rain
Purpose: stillness. The master in jodan, the student in chudan, 2.5 m apart, two silhouettes against the glowing steam band; rain everywhere. The next move decides it.

Camera (low profile wide, 1.3 m, locked; 0.2 m creep in):
```python
C.shot("S23a", 2881, 2925,
       keys=[(2881, (8.6, 1.2, 1.30), (0.0, 2.3, 1.85), 20.0),
             (2925, (8.4, 1.3, 1.30), (0.0, 2.3, 1.85), 20.0)],
       dof=None, handheld=0.0, subjects=["shinobi", "saint"], framing="wide")
```
Screen: shinobi (−0.16, −0.09) fig 26 % (vis 16 %), elder (+0.16, −0.04) fig 28 % (vis 11 % — the grass behind the S11 crescent is full height at his feet); order OK, side sin −1.00. Horizon −0.17; the far steam band (x −10.9) straight behind them (−0.07, −0.04); the jodan tip (+0.22, +0.24) against the storm clouds. Symmetric. Action: elder (0.00, 3.60) jodan, motionless (breathing only, chest 1°); shinobi (0.00, 1.10) chudan: 2898→2910 his weight settles forward (hips_offset z +0.04), the tip of his sword lowers 3 cm (resolve); 2918→2925 he coils (knees +10°). Nothing else. Environment: `ENV.set_sun(2881, 270.0, 28.0)` (in front of the lens: backlit rain, rims both); `ENV.set_wind(2881, 1.0)`. Events: `EV.emit(2908, "thunder", distance="far", strength=0.4)` (bar 11 — sound only, no flash).

### S23b — 2926–2952 (27 f) — the attack and the grounded cut
Purpose: the student attacks the open jodan; the master's full-power cut comes down; the student throws himself back and the blade — missing him by a breath — strikes the flooded ground between them: the spray bursts up, the rain splits.

Camera (profile medium, 1.5 m, locked, impact shake):
```python
C.shot("S23b", 2926, 2952,
       keys=[(2926, (6.2, 1.6, 1.5), (0.0, 2.4, 1.35), 28.0),
             (2952, (6.2, 1.6, 1.5), (0.0, 2.4, 1.35), 28.0)],
       dof=None, handheld=0.0, shake=[(2950, 0.7, 10)], subjects=["shinobi", "saint"], framing="medium")
```
Screen: shinobi (−0.33, +0.11) → (−0.18, +0.03) @2944 (attacking) → (−0.34, +0.09) @2950 → (−0.49, +0.15) @2952 (flung); elder (+0.29, +0.21) → (+0.25, −0.06) @2950 (sunk into the cut); fig 39–52 %; order OK, side sin ≥ |0.98|. The blade passes horizontal at (−0.05, +0.15) at 2948 (at the height where the student's head was at 2941); IMPACT at (−0.16, −0.80) in the lower third, between them; the jodan tip starts at (+0.41, +0.77). Action
| frame | shinobi | elder |
|---|---|---|
| 2926→2929 | coils (hips −0.05) | jodan |
| **2929→2939** | launches: step-lunge thrust at the open torso → (0.00, 1.75) (bar 11.3) | jodan (he lets him come) |
| **2939→2950** | 2941 sees the cut, aborts: throws himself back → (0.00, 1.05) at 2950 (root z 0 → 0.20, airborne 2945–2951), torso arched back, blade pulled in front of his face | **the grounded full-power cut**: 2939–2943 the blade rises from jodan over his head (pivoting on the fists); 2943–2950 it comes down in the line plane; 2946 the front foot stamps (0.00, 3.60 → 3.45); blade horizontal at 2948 (tip ≈ (0.00, 2.20, 1.60)); **2950** `zanshin_grounded` (§5): tip strikes IMPACT (0.00, 1.75, 0.02) |
| 2950→2952 | the blast lifts him (root z 0.20 → 0.45), arms flung forward, head snapping back | the blade rebounds 5 cm off the ground (never sticks), holds |
Clashes: none (no blade contact). `CH.key_blade_tip(SA, 2950, tip=(0.00, 1.75, 0.02), direction=(0.0, -0.78, -0.62))` → grip ≈ (0.00, 2.43, 0.56); 2951: tip (0.00, 1.77, 0.07) (rebound), 2952: (0.00, 1.78, 0.06). Environment: `ENV.set_sun(2926, 270.0, 25.0)`. VFX: the three impact calls (S23 shared) at 2950; student's short trail `VFX.blade_trail(... "SHINOBI" ..., 2932, 2939, owner="shinobi")`; **no trail on the master's cut** (D11: no glow — motion blur only). Events: `EV.emit(2929, "dash", who="shinobi", strength=0.7)`; `EV.emit(2933, "whoosh", who="shinobi", weapon="katana", strength=0.5)`; `EV.emit(2941, "jump", who="shinobi", strength=0.6)` (the throw-back); `EV.emit(2944, "whoosh", who="saint", weapon="katana", strength=1.0)`; `EV.emit(2946, "step", who="saint", strength=1.0)` (the stamp); + the impact events (S23 shared); `EV.emit(2951, "hit", who="shinobi", strength=0.8, pos=(0.0, 1.05, 1.2))` (the blast hits him — no blade). Notes: cut at 2953 = 3 f after the impact. The student is NEVER touched by the blade: at 2948 the edge passes 0.9 m in front of his face.

### S23c — 2953–2972 (20 f) — the blast throws him screen-left
Purpose: the consequence, from above: the ring of spray racing out from the cut, the thin sheet of the split rain standing up along the line, and the student hurled screen-left through the air, crashing and tumbling.

Camera (wide, elevated 5 m looking down 25°, locked):
```python
C.shot("S23c", 2953, 2972,
       keys=[(2953, (9.0, -1.5, 5.0), (0.0, -1.8, 0.8), 18.0),
             (2972, (9.0, -1.5, 5.0), (0.0, -1.8, 0.8), 18.0)],
       dof=None, handheld=0.0, shake=[(2962, 0.25, 6)], subjects=["shinobi", "saint"], framing="wide")
```
Screen: shinobi flung from (+0.21, +0.18) @2953 → (+0.16, +0.21) @2955 (apex) → lands (−0.05, −0.02) @2962 → tumbling (−0.21, −0.02) @2972: **0.42 NDC screen-left** (fig 19 % in the air, 8 % tumbling in the stubble); elder (+0.55, +0.08) in zanshin (fig 15 %); order OK, side sin −0.98 → −0.97. The spray crown expands around IMPACT (+0.35, −0.18) to r 4 m → from (−0.05, 0.00) to (+0.78, −0.03): the student flies out through its −Y rim. Lens inside the ring (r 9.5). Action
- Shinobi (`_local_thrown_back`, §5): 2953 (0.00, 0.60, root z 0.45) → apex 2955 (0.00, −0.30, z 0.60; flung: arms forward-out, legs trailing, head back) → 2962 lands on his back/left shoulder at (0.00, −2.30) → `M.roll(SH, 2962, 2980, (0.00, -2.30), (0.00, -4.90))` backward roll (the sword held out to his right side, tip back — never through his body) → cut at 2972 mid-roll at ≈ (0.00, −4.10). Left hand off the hilt 2951 (§1).
- Elder (0.00, 3.45): holds `zanshin_grounded` (blade tip 5 cm above the mud at IMPACT), beard/sleeves settling. Environment: `ENV.set_sun(2953, 270.0, 30.0)` (backlights the spray crown and the flung sheet); `ENV.set_wind(2953, 0.5)`. VFX: `VFX.sparks(2962, (0.00, -2.30, 0.10), direction=(0.0, -0.8, 0.6), count=40, speed=3.0, life=14, color=(0.55, 0.60, 0.65), scale=0.8, seed=S("S23c", 0), light=False, core=False)` (the splash of his landing); `VFX.grass_burst(2962, (0.00, -2.30, 0.4), direction=(0.0, -0.6, 0.8), count=40, seed=S("S23c", 1), fluff=0.1)`; the same pair at 2970 (0.00, −3.70) with count 20 (the tumble). Events: `EV.emit(2962, "body_fall", who="shinobi", strength=0.9, pos=(0.0, -2.3, 0.2))`; `EV.emit(2963, "roll", who="shinobi", strength=0.6)`.

### S23d — 2973–3009 (37 f) — the parted rain; one knee (THE LOW POINT)
Purpose: down the line of the cut: through a corridor of air where the rain has been cut away, the student comes to rest far away on one knee, plants his sword in the mud and bows his head; the master, in the foreground, rises from his cut. Then the rain closes the corridor from the top.

Camera (on the cut plane, over the elder's LEFT shoulder, 0.85 m off the plane, 2.1 m high, locked):
```python
C.shot("S23d", 2973, 3009,
       keys=[(2973, (0.85, 8.4, 2.1), (0.0, -4.0, 1.0), 32.0),
             (3009, (0.85, 8.4, 2.1), (0.0, -4.0, 1.0), 32.0)],
       dof=dict(focus=(SH, "head"), fstop=4.0), handheld=0.0, subjects=["shinobi", "saint"], framing="ots")
```
Screen: shinobi (−0.00, −0.09) @2973 → (−0.02, +0.09) @2990 → (−0.02, +0.06) @2998–3009: small and distant (fig 14–18 %, vis 7–8 % over the stubble), dead centre in the corridor; the master in the right foreground (+0.18, −0.31) → (+0.18, +0.05) as he rises (fig 57 → 75 %, soft). Order OK; side sin −0.07 → −0.06 (the camera is legally on +X, 0.85 m off the line: the 180-degree check counts it, |sin| > 0.03). **Rain split:** lens 7.3° / 0.85 m off the cut plane (DIRECTION §10: ≤ ~10°, ≤ ~2 m ✓), the camera itself inside the 2.2-m slab (the corridor runs 22 m from the elder toward −Y, past the student); corridor edges at the student's distance at x −0.29 / +0.25; the steam band (−Y arc) glows straight behind him (−0.04, +0.11): his kneeling silhouette is framed by the orange glow at the end of the clear corridor. Backlight = key from −Y (in front of the lens). Action
| frame | shinobi | elder |
|---|---|---|
| 2973→2980 | finishes the backward roll → comes up on his left foot / right knee at (0.00, −4.90) | zanshin |
| 2980→2991 | **skids on one knee** → (0.00, −6.00) (`M.skid(SH, 2980, 2991, (0.00, -4.90), (0.00, -6.00))`; the right knee and the left foot plough the mud) | 2972→3000 rises slowly out of the cut stance (hips up, torso 50° → 5°) |
| 2984→2992 | left hand back on the hilt (2984); **plants the sword**: tip into the mud at (0.02, −5.46) 2986–2992, both fists on the tsuka | lifts the blade off the ground to gedan (tip 0.35 m above the stubble) |
| **2992→3001** | **head bows** (neck 0 → 15, head 0 → 30) — `kneel_sword_planted` complete at 3001 (bar 13.2) | gedan, still (3000) |
| 3001→3009 | holds; shoulders rise and fall (breathing, chest ±2°) | holds |
Environment: `ENV.set_sun(2973, 190.0, 16.0)` (from −Y, behind the student: ≈ 165° from the lens axis — rims the rain walls of the corridor and the student's silhouette); `ENV.set_wind(2973, 0.5)`. VFX: (the corridor is the rain_split call of S23 shared); `VFX.sparks(2991, (0.00, -6.00, 0.10), direction=(0.0, -1.0, 0.4), count=25, speed=2.0, life=12, color=(0.55, 0.60, 0.65), scale=0.6, seed=S("S23d", 0), light=False, core=False)` (mud-water off the skid); `VFX.sparks(2990, (0.02, -5.46, 0.05), ..., count=10, scale=0.4, seed=S("S23d", 1))` (the blade entering the mud). Events
```python
EV.emit(2980, "skid", who="shinobi", duration=11, strength=0.6)
EV.emit(2991, "kneel", who="shinobi", strength=0.6)
EV.emit(2991, "land", who="shinobi", strength=0.35, pos=(0.02, -5.46, 0.0))    # the sword tip into the mud
EV.emit(3001, "heartbeat", bpm=52, duration=71, strength=0.5, tags=["low_point"])   # D6: the pose beat (music cue = 2950)
EV.emit(2985, "steam_hiss", pos=(0.0, -9.5, 1.0), strength=0.3, duration=24)  # the steam band behind him (ambience)
```
Notes: the corridor is clear only 2965–3000 (vfx sheet) — this cut opens at 2973 inside that window and holds through the refill (3000–3009: the rain falls back in from the top, reaching the ground at 3010, the S23e cut). The student's face is never seen: the low point is a silhouette at the end of the cut.

### S23e — 3010–3072 (63 f) — two unhurried steps
Purpose: the stillness beat: the student on one knee leaning on his sword, head bowed, screen-left; the master walks two slow steps toward him out of the tall grass into the stubble and stops. Nobody moves. (The music stops on the cut to S24.)

Camera (profile wide two-shot, 2.0 m, locked; −7° pitch):
```python
C.shot("S23e", 3010, 3072,
       keys=[(3010, (7.8, -1.8, 2.0), (0.0, -1.5, 1.1), 22.0),
             (3072, (7.8, -1.8, 2.0), (0.0, -1.5, 1.1), 22.0)],
       dof=dict(focus=(SH, "head"), fstop=5.6), handheld=0.0, subjects=["shinobi", "saint"], framing="wide")
```
Screen: shinobi (−0.71, −0.04) (fig 21 %, vis 9 % — the whole kneeling profile above the stubble: bowed head, both fists on the hilt (−0.65, −0.11), the blade down into the mud (−0.62, −0.41)), facing screen-RIGHT; elder (+0.76, +0.23) @3010 → (+0.69) @3025 → (+0.62, +0.23) @3040–3072 (fig 33 %; vis 14 % → 21 % as he leaves the tall grass behind the S11 crescent), facing screen-LEFT; order OK, side sin −0.88. The far steam band glows behind the whole frame at y ≈ +0.33 (−0.06, +0.33 straight behind the gap between them): two silhouettes on either side of an empty, rainy middle. Action
- Shinobi (0.00, −6.00): holds `kneel_sword_planted`; breathing (chest ±2° over ~40 f); the soaked tails hang (wind 0.5).
- Elder: 3010 (0.00, 3.45) gedan; **step 1** 3011→3022 (right foot) → (0.00, 2.97); **step 2** 3030→3042 (left foot) → (0.00, 2.50) (`M.walk(SA, 3011, 3042, (0.00, 3.45), (0.00, 2.50))` with 2 steps, slow: lift 11 f, plant; torso upright, head level, eyes on the student); gedan blade steady (tip ≈ 0.35 m above the stubble, 1.1 m in front); **holds 3042–3072** → HANDOFF[3072]. Environment: `ENV.set_sun(3010, 270.0, 25.0)`; wind 0.5; rain 1.0. VFX: none. (Optional (tune): `VFX.sparks` splashes at each planted foot 3022 / 3042, count 8, scale 0.3.) Events: `EV.emit(3022, "step", who="saint", strength=0.45)`; `EV.emit(3042, "step", who="saint", strength=0.45)`. Notes: 3042 is the second step's plant (bar 14.2; config "3010–3040"). Hold 30 f of real time. The final frame 3072 is exactly HANDOFF[3072] (both roots keyed CONSTANT at 3072; the finale's S24a cuts in on the telephoto axis at 3073).


## 4. Flash schedule + budget proof

`ENV.flash` strength 1.0 is calibrated to ≤ ~70 % frame luminance (`environment.FLASH_MAX`), so "full-white equivalent" ≈ 0.7 × strength; envelope `FLASH_ENVELOPE` (1.0, 0.42, …) × strength, duration 2 → 2 frames. Tint = the environment's cold blue-white `FLASH_TINT` (0.72, 0.82, 1.0) unless given.

| frame | cut | source | ENV strength | ≈ full-white | duration | direction (az, el) | reveals |
|---|---|---|---|---|---|---|---|
| **2497** | S21a | the raikiri bolt (`lightning_bolt(flash=True, 0.7)` + `tree_strike(flash=True)` merge) re-keyed `ENV.flash(2497, 0.80, 2, tint=(0.70, 0.80, 1.0), direction=(338, 76))` | 0.80 | ≈ 56 % (2497), 24 % (2498) | 2 f | 338, 76 | the cut bolt, the fork, the pine |
| **2605** | S22a | bolt at (−10, 34) (`flash_strength=0.60`) + `ENV.flash(…, direction=(344, 70))` | 0.60 | ≈ 42 % | 2 f | 344, 70 | tableau A: he advances |
| **2620** | S22a | in-cloud `VFX.env_flash(2620, 0.50, 2)` + direction | 0.50 | ≈ 35 % | 2 f | 300, 55 | clash 1 |
| **2662** | S22d | bolt at (−38, −14) (`0.55`) + direction | 0.55 | ≈ 38 % | 2 f | 250, 62 | the near-miss |
| **2703** | S22f | bolt at (−52, 12) (`0.65`) + direction | 0.65 | ≈ 45 % | 2 f | 283, 60 | the heavy block |
| **2744** | S22h | in-cloud `VFX.env_flash(2744, 0.50, 2)` + direction | 0.50 | ≈ 35 % | 2 f | 200, 80 | the sidestep from the sky |
| **2764** | S22i | in-cloud `VFX.env_flash(2764, 0.45, 2)` + direction | 0.45 | ≈ 31 % | 2 f | 250, 45 | the blow turned aside |

Not flashes (listed because flash_qc measures luminance, not intent):
- Spark-lit ECU contacts (local 3-f spark lights, 40 W × scale, cutoff 8 m): 2641 (S22c), 2682 (S22e), 2723 (S22g), 2826 (S22bb insert, white). In an ECU a spark burst may lift a quadrant's mean luminance ≥ 10 % → treat them as potential onsets: they are placed exactly between the flashes (≥ 20 f from any flash, see below).
- Visible bolt tubes flicker for 3–4 f (stroke / dim / re-stroke) but cover < 2 % of the frame (thin tubes + halo in extreme wides); their point lights are ONE decaying pulse on the flash frame (vfx budget registry).
- S21b afterglow (a 1.6-mm line on the edge), S21a/b steam, the tree's seam fire (ramps in over 0.2 s from 2498, lasts to 2592, dies over 20 f) — no transitions.
- Cuts: every S22 cut is 3 f after its contact, i.e. 1 f after the flash's 2-frame envelope has ended — no cut opens on a lit frame; the S22→S22b cut (2785) raises the base light from the dimmed strobe level to storm_night (a single step up on a cut, not an opposing pair; ≈ +3–5 % mean luminance, below the 10 % transition threshold) (tune: if QC counts it, ramp `key_pow` 0.15 → 0.60 over 2785–2791 instead).

Proof
- **Gaps** (all onsets, flashes and spark-lit ECUs, sorted): 2497 → 2605 (108) → 2620 (15) → 2641 (21) → 2662 (21) → 2682 (20) → 2703 (21) → 2723 (20) → 2744 (21) → 2764 (20) → 2826 (62) → (finale 3265). Minimum 15 f ≥ `config.FLASH_MIN_GAP` 12 ✓. Previous lane's last flash 2443 → 2497 = 54 f ✓. No flash 2765–3072 (S22b, S23: real storm light; "no glow").
- **≤ 2 per second**: every 24-frame window holds at most 2 onsets (the only 15-f pair is 2605/2620; all other adjacent onsets are ≥ 20 f apart, so no window contains 3) ✓ — flash_qc WARN is > 2, FAIL > 3 flashes (≥ 7 transitions) per 24 f.
- **≤ 70 %**: max ≈ 56 % (2497); S22 ≤ 45 % ✓. Nothing near `config.FULL_WHITE` (3265–3268) ✓. The S21 bolt is 2 f and blue-tinted ✓ (DIRECTION §5).
- **Quadrant rule** (flash_qc: the general-flash rule per 25 % of the screen): the bolts of 2605 / 2662 / 2703 strike in one quadrant each (upper-right, lower-left, upper-centre-right) but on flash frames that are anyway counted; the spark ECUs (2641, 2682, 2723) sit 20–21 f from their neighbours ✓.
- **Shadow casters** (Pipeline rule 5): key (ENV_key) + ENV_flash (shadowed) = 2; act2's two shadowed ring lights are hidden since 2422 (its `shadow_window`); bolt / tree / spark / fire lights are unshadowed ✓.
- **Budget plumbing**: `ENV.flash` refuses flashes < 12 f apart and clamps > FLASH_MAX; `vfx.env_flash` / `lightning_bolt` / `tree_strike` share vfx's registry (same frame merges). After the lane build check `ENV.flash_log()` — expected: 7 accepted, 0 refused, 0 clamped.
- **Red flashes**: none (no crimson in Act III; the tree fire is small and ramps in).

## 5. Local poses / moves not in the SPEC macro list

Format = `characters.pose_bones` / `apply_pose` spec: body = bone Euler degrees (+X = flexion); `hips_offset` = hips.location bone-local (x = his left, y = up, z = forward); `legs` = ankle targets in **rig space** (the character faces −Y in rig space: forward = −Y, his left = +X; SHINOBI metres, scaled by height for the SAINT). **Blades are given in WORLD coordinates at the stated root** — key them with `CH.key_sword(rig, f, grip, direction, edge, space='WORLD')` or `CH.key_blade_tip(...)` (unambiguous; no scaling question) and `CH.set_arm_mode(rig, f, 'ik')`. World ↔ rig: elder (facing 0) world = root + rig; shinobi (facing 180) world = root + (−x, −y, z). Define them in `acts/act3.py` as `_local_POSES` / `_local_*` moves; if `moves.py` ships a macro with the same intent, use it and keep these numbers as its targets.

| name | who / frames | spec (key numbers) | intent / check |
|---|---|---|---|
| `raikiri_contact` | SAINT 2497 (root (0, 3.00)) | hips_offset (0, −0.08, 0.04); spine (5,0,0), chest (−5,0,0), neck (−8,0,0), head (−18,0,0); legs L (0.15, −0.40, 0.08), R (−0.15, 0.30, 0.08); blade grip (0.00, 2.72, 2.05), dir (0, −0.42, 0.91), edge (0, −0.91, −0.42); two-handed | mid-downswing from jodan, blade 65° up-forward: the struck point (u 0.8) at (0.00, 2.42, 2.71) sits 0.1 m under the bolt's `fork_at` (0.00, 2.40, 2.80); face up at the bolt |
| `raikiri_follow` | SAINT 2500–2530 | hips_offset (0, −0.12, 0.06); spine (12,0,0), chest (5,0,0), head (−10,0,0); legs L (0.15, −0.45, 0.08), R (−0.15, 0.35, 0.08); blade grip (0.00, 2.55, 1.30), dir (0, −0.94, −0.34), edge (0, 0.34, −0.94) | the cut stops at waist height, tip (0.00, 1.73, 1.00) (never into the ground); in-betweens 2498 grip (0, 2.62, 1.75) dir (0, −0.88, 0.47), 2499 grip (0, 2.56, 1.45) dir (0, −0.99, −0.12) |
| `hasso` | SAINT 2548–2605 | spine (0, −10, 0), chest (0, −10, 0), head (0, 8, 0) (eyes stay on the student); legs L (0.15, −0.35, 0.08), R (−0.15, 0.25, 0.08); blade (root (0, 3.00)) grip (−0.19, 2.81, 1.56), dir (−0.05, 0.12, 0.99), edge (0, −1, 0) | fists at his RIGHT shoulder (world −X), blade near vertical, tip (−0.23, 2.92, 2.43) — in S21c at NDC (+0.30, −0.42), under the card |
| `kesagiri` (A1, A7) | SAINT wind-up → strike | wind-up = `hasso` raised: grip root + (−0.25, −0.23, 1.75), dir (−0.30, 0.35, 0.89); contact via `M.clash`; follow-through grip root + (0.25, −0.45, 0.95), dir (0.55, −0.60, −0.58); spine Y −15 → +20 (the hips turn into it); front foot steps 0.25–0.30 m | two-handed diagonal from his right shoulder to his left hip (use `M.slash(SA, f, "diag_down_R")` if its arc matches) |
| `kiriage` (A2) | SAINT 2629–2641 | from the kesagiri follow-through (low left, edge turned up 2629–2635) rising to grip root + (−0.20, −0.45, 1.55), dir (−0.55, −0.55, 0.63) | `M.slash(SA, f, "rising_L")` equivalent |
| `yoko` (A3) | SAINT 2648–2663 | wind-up grip root + (−0.35, 0.05, 1.20), dir (−0.20, 0.98, 0) (blade back at his right hip); at 2662 grip root + (0.00, −0.55, 1.25), dir (0, −1, 0) (straight at the student, tip world y 0.87); ends 2663 dir (0.70, −0.71, 0) | horizontal plane z 1.20–1.25; the student's chest is ≈ 0.75 m beyond the tip at 2662 (he leapt 0.55 m) |
| `tsuki` (A4) | SAINT 2670–2684 | coil grip root + (−0.20, 0.15, 1.10), dir (0.15, −0.99, 0.10); lunge 2677→2682 root 2.60 → 2.15, grip root + (−0.05, −0.65, 1.35), dir (0.05, −1, 0.03); after the parry 2683–2684 tip to (0.35, 0.15, 1.55) | `M.slash(SA, f, "thrust")` equivalent |
| `men_heavy` (A5, A8) | SAINT | wind-up grip root + (0.00, 0.10, 2.05), dir (0, 0.55, 0.84) (both fists above the forehead, blade back 30°); strike to the contact (`M.clash`); A5 bind 2704–2705 (blades pressed, spine 25°); A8 slide keyed per frame (S22i table) ending tip on the ground (−0.45, 1.30, 0.15) at 2770, hips_offset (0, −0.30, 0.10), spine (45,0,0) | the only overheads of S22 |
| `gyaku_kesa` (A6) | SAINT 2708–2724 | wind-up grip root + (0.25, −0.20, 1.75), dir (0.30, 0.35, 0.89) (on his LEFT, +X); follow-through grip root + (−0.25, −0.45, 0.95), dir (−0.55, −0.60, −0.58) | `M.slash(SA, f, "diag_down_L")` equivalent |
| `leap_back_arch` | SHINOBI 2656–2664 | root z 0 → 0.18 (2659) → 0; spine (−20,0,0), chest (−10,0,0), head (−15,0,0); thighs (35,0,±8), shins (40,0,0) in the air; blade upright in front: grip rig (0, −0.35, 1.25), dir rig (0, −0.20, 0.98), two-handed | `M.dodge(SH, 2656, "back")` with this arch; hold the arch 2662–2663 |
| `parry_sweep_R` | SHINOBI 2677–2684 | rising sweep to HIS right (world +X): grip rig (0.10, −0.40, 1.20) → (−0.15, −0.45, 1.45), dir rig (0.55, −0.60, 0.58) → (−0.35, −0.55, 0.76); head turns 10° left 2683 (away from the passing blade) | contact (0.10, 1.00, 1.40) via `M.clash`; the elder's blade must pass OUTSIDE his head (≥ 0.2 m) |
| `overhead_block_pressed` | SHINOBI 2697–2705 | `M.deflect(SH, 2703, "overhead_block")`: blade horizontal above the forehead, along world X (grip rig (−0.25, −0.25, 1.62), dir rig (1, 0, 0.05)); hips_offset (0, −0.12, 0) at 2703 (knees give, head 1.50 → 1.33) | the heavy blow drives him down |
| `uke_nagashi` | SHINOBI 2752–2768 (root (0.25, 0.55)) | blade world grip (0.20, 0.90, 1.60), dir (−0.60, 0.40, −0.69) (= rig grip (0.05, −0.35, 1.60), dir (0.60, −0.40, −0.69)); edge up-out; spine Y +10 (right shoulder forward); 2764→2768 the wrists turn out 15° as the blade slides | the slanted roof: the attacking blade meets it at (0.11, 0.96, 1.50) and slides to its tip (−0.22, 1.18, 1.12) |
| `furikaburi` | SHINOBI 2772–2784 | from the slant the blade circles up and over: end grip rig (0.00, 0.05, 1.95), dir rig (0.10, 0.55, 0.83), two-handed; head steady | poised for S1 |
| `kesa_R` (S1) | SHINOBI 2785–2796 | wind-up = `furikaburi` shifted to his right: grip rig (−0.25, 0.05, 1.85), dir rig (−0.30, 0.40, 0.87); step-in 0.25 m; follow-through grip rig (0.25, −0.40, 0.95), dir rig (0.55, −0.60, −0.58) | `M.slash(SH, 2795, "diag_down_R")` |
| `kiriage_L` (S2) | SHINOBI 2796–2807 | from low left rising: end grip rig (−0.20, −0.45, 1.55), dir rig (−0.55, −0.55, 0.63); step-in 0.2 m | `M.slash(SH, 2806, "rising_L")` |
| `lunge_thrust` (S3) | SHINOBI 2809–2830 | coil 2809–2819: grip rig (−0.15, 0.25, 1.20), dir rig (0.10, −0.99, 0.10); lunge 2819→2826: hips_offset (0, −0.15, 0.10), legs L (0.15, −0.70, 0.08), R (−0.12, 0.45, 0.08), grip rig (0.00, −0.60, 1.35), dir rig (0, −1, 0.02); recover 2830–2850 | `M.slash(SH, 2826, "thrust")` + `M.dash`-like root push (0.45 m) |
| `parry_block_L` / `_R` | SAINT 2789–2828 | blade vertical on his left (+X) (grip root + (0.20, −0.40, 1.30), dir (0.10, −0.20, 0.97)) for S1; low on his right (grip root + (−0.20, −0.40, 1.05), dir (−0.35, −0.45, −0.82)) for S2; S3 sweep to his left (grip root + (0.05, −0.45, 1.30) → (0.30, −0.35, 1.35), dir (0.50, −0.75, 0.43)) + lean back (spine −10) | `M.deflect(SA, f, "mid_L" / "low" / "mid_L")` equivalents |
| `jodan` | SAINT 2847–2941 | act2 §5 spec verbatim (grip rig (−0.02, −0.12, 2.00), dir (0, 0.70, 0.71), legs L (0.15, −0.40, 0.08), R (−0.15, 0.25, 0.08), two-handed); at root (0, 3.60) tip ≈ (−0.02, 4.09, 2.62) | the same stance as 2496 — a visual rhyme with the raikiri |
| `zanshin_grounded` | SAINT 2950–2972 (root (0, 3.45)) | hips_offset (0, −0.40, 0.10); spine (35,0,0), chest (15,0,0), neck (−10,0,0), head (−20,0,0); legs L (0.18, −0.62, 0.08) (the stamped front foot), R (−0.15, 0.55, 0.08) (rear leg long); blade tip (0.00, 1.75, 0.02), dir (0, −0.78, −0.62) → grip (0.00, 2.43, 0.56); two-handed | the grounded full-power cut ends with the tip ON the flooded ground (rebound 5 cm 2951, never stuck); rises 2972→3000 |
| `gedan` | SAINT 3000–3072 (HANDOFF[3072]) | upright: hips_offset (0, −0.03, 0); legs L (0.15, −0.30, 0.08), R (−0.15, 0.25, 0.08); blade grip root + (0.00, −0.45, 0.95), dir (0, −0.94, −0.34) → tip root + (0, −1.27, 0.65); two-handed; during the walk only the legs cycle | tip at the stubble tops, 1.25 m ahead, pointing at the kneeling student |
| `_local_thrown_back` | SHINOBI 2950–2962 | root keyed per frame: y 1.05 (2950) → 0.60 (2953) → −0.30 (2955) → −1.40 (2958) → −2.30 (2962); root z 0.20 → 0.45 → 0.60 → 0.45 → 0.05; rig **pitch** (rotation_euler.x) 0 → −20° (2955) → −50° (2960) → −75° (2962: landing on his back/left shoulder); body: spine (−30,0,0), chest (−15,0,0), head (−25,0,0) (snapped back), upper_arm.L (40,0,60) (flung), right arm holding the sword out to his right side, blade back (world grip ≈ root + (0.35, 0.10, 1.0), dir (0.3, −0.9, 0.3)); thighs (45,0,±10), shins (70,0,0) | blown backward feet-first, never touched; the blade never crosses his head (check with `CH.blade_points` 2950–2962) |
| `_local_back_roll` | SHINOBI 2962–2980 | if `M.roll` turns him toward the travel direction, use: root y −2.30 → −4.90 (ease-out), root z +0.35 at mid-roll, rig pitch −75° → −360° (2976) → 0 (continuous, one backward revolution about the hips), tucked body (thighs (110,0,0), shins (120,0,0), spine (40,0,0)), sword along his right side tip back; 2976–2980 comes up onto the left foot / right knee | facing stays 180 (he tumbles backward away from the master) |
| `kneel_sword_planted` | SHINOBI 2991–3072 (HANDOFF[3072], root (0, −6.00)) | hips_offset (0, −0.52, 0.05); legs L ankle rig (0.14, −0.38, 0.08) (left foot forward, knee up), R ankle rig (−0.12, 0.42, 0.06), foot_pitch 60 (toes tucked, right knee on the ground); spine (25,0,0), chest (10,0,0), neck (15,0,0) → head (30,0,0) by 3001 (bowed; 0/0 at 2991); blade world grip (0.02, −5.58, 0.74), dir (0, 0.16, −0.987), edge (0, 1, 0) (rig grip (−0.02, −0.42, 0.74), dir (0, −0.16, −0.987)) → tip (0.02, −5.46, 0.00) in the mud; two-handed (the left fist above the right, on the tsuka end) | head centre ≈ 1.02, fists ≈ 0.74–0.90 — above the 0.65 m stubble; the finale rises from this exact pose (S24a 3085–3115) and S27 echoes it with the elder |

Local helpers (prefix `_local_`, SPEC file-ownership rule):
- `_local_pine_top()`: `M = U.world_matrix_of(bpy.data.objects["ENV_pine"])`; top = max z of the 8 bbox corners − 0.3; returns (config.PINE_POS[0], config.PINE_POS[1], top) — the same point `vfx.tree_strike(pos=None)` uses.
- `_local_hold(rig, f, n=1)`: for the S22 flash frames — re-key every animated pose/controller channel of `rig` at f+n with its value at f (CONSTANT on f) so the tableau is frozen for the 2 lit frames (also the root).
- `_local_flash(f, s, direction, bolt=None)`: `VFX.lightning_bolt(**bolt, flash=True, flash_strength=s)` if a bolt is given else `VFX.env_flash(f, s, 2)`; then `ENV.flash(f, s, 2, direction=direction)` (same frame → merged, only the lamp direction is added); assert the returned strength > 0.
- `_local_cheat(rig, f_last, f_next, xy, facing)`: CONSTANT root key at f_last, new root key at f_next (Pipeline rule 2) — the ⟲ rows of §1.

## 6. Title overlays in the span

Only one: `config.TITLES` id `act3` — "Act Three" + the Thunder glyph, style `act`, **2521–2588**, over S21c (2521–2592).
- Timing (titles.py `ActTitle.moments()`, measured by `out/dev/breakdown/act3/act_card_box.py`): column ramps in ≈ 2535, accent Thunder glyph ≈ 2544, seal impact 2545, **legible 2551–2577**, faded by 2588; the S22a cut is 2593 (5 f later).
- Geometry: accent glyph ink NDC x +0.430…+0.654, y +0.005…+0.583; column ink x +0.703…+0.765, y +0.059…+0.542; soft dark backdrop ellipse x +0.356…+0.839, y −0.292…+0.704 — the upper-right third. The glyphs are light (off-white with a dark halo): they want a dark background.
- How S21c leaves room: a locked 16 mm low angle whose upper 5/6 is the dark cloud deck (storm_night, no flash in 2499–2604). Everything that moves is below / left of the backdrop: the student's stalk at y −0.65…−0.67, x −0.41 → −0.17; the master at (+0.32, −0.61) (0.04 left of the backdrop's left edge and 0.32 below its bottom); his hasso blade tip at (+0.30, −0.42). The far steam band's top edge is at y −0.32…−0.29 — it glows under the bottom rim of the backdrop, never behind the glyphs (ink starts at y +0.005). The burning pine is 4 frame-widths off to the right. `geom.py` card check: **clear at 2551, 2564, 2577, 2592**.
- Motion vs legibility: during 2551–2577 the only motion is the slow stalk (0.76 m/s, lower left) and the hasso lift (lower right, 2548–2580); no flash, no cut, locked camera.
- Request to the titles lane (not this file): none expected; if the steam band's top reads too bright behind the lower part of the backdrop in preview, lower `fire_ring`'s steam glow for this cut via a per-shot key (act2 owns the call) or darken the act3 backdrop slightly.
- No other titles in 2497–3072 (act2 card ends 1726, the end card starts 3758).

## 7. Risks + fallbacks

| # | risk | what to watch | fallback / simplification |
|---|---|---|---|
| R1 | The raikiri reads as the elder SUMMONING / holding lightning (deny-list) | S21a 2497–2500 | the blade is already mid-cut on frame 1 (no raised-sword pause under the bolt), the bolt ends ABOVE the blade (`fork_at`), forks go away from both fighters, no electrified trail (steel-blue trail only), afterglow is a thin hot line for 4 f in S21b — keep all of it; if still ambiguous, drop the S21a blade trail and add 1 f: bolt 2497 without forks, `fork_delay=1` (forks + tree split at 2498; tree_strike's flash then refused → pass `flash=False`, keep its light via the same-frame budget only if merged) |
| R2 | Bolt / fork unreadable at 18 mm from 30 m (thin tubes) | S21a preview | `width=0.10` on the cut bolt, `strength` 150; or move the camera to (18, −16, 12) (sight lines cross the steam band at ≈ 4.4 m — acceptable) |
| R3 | act1b's S11 stubble does NOT persist (someone sets `until` < 3073) → the kneeling student (head 1.02) sinks into 1.05–1.15 m grass | S23d / S23e | keep `until=None` (cross-lane note to act1b / env); otherwise S23e camera to (6.0, −4.2, 3.2) looking down 18° and S23d to z 3.0, or env `set_camera_clearance(3010, near=1.5, far=9.5)` for S23e |
| R4 | Strobe too dark between flashes (nothing reads) or too bright (no strobe) | S22 previews | tune `key_pow` 0.10–0.25 / `amb_str` 0.12–0.25 at 2593 (only these); the steam band + pine plume + trails must carry the silhouettes; never add flashes (budget) |
| R5 | flash_qc counts the spark-lit ECUs (2641, 2682, 2723, 2826) as flashes | QC on the preview | already spaced ≥ 20 f from every flash (§4); if a quadrant FAILs, drop `light=True` on those clashes' sparks (`M.clash(..., light=False)` or `light_energy` × 0.5) |
| R6 | The pose "HOLD" on flash frames looks like a render glitch (dropped frame) | S22 flash frames | hold only the bodies; let the rain and the sparks keep moving (they run on fx_time, so they do); or hold 1 f instead of 2 |
| R7 | 9 cuts in 8 s (S22) confuse the geography | S22 in sequence | the wides (S22a, d, f, h) keep the pair centred with the student left / the master right; if confusing, merge S22e into S22d (drop the OTS, 41-f wide with two blows) and S22j into S22i |
| R8 | The rain split corridor does not read from S23d (the elder's end, reverse of the vfx look-dev) | S23d 2973–3000 | move the lens onto the plane (x 0.40) and lower to 1.6 m; `width=2.6`; key light az 185 el 12 (stronger rim on the corridor walls); worst case a second, short rain-split view from behind the student inside the ring (0.4, −7.9, 1.9) 24 mm for 2973–2985 (camera inside the steam band's thin inner edge) |
| R9 | The 7-m knockback looks floaty / wire-work | S23c | shorten airtime: land 2960 at (0, −1.9) and extend the tumble (2 rolls, 2960–2980); the throw stays screen-left; the spray ring must hit him (front at r 0.7 m at ≈ 2951) |
| R10 | `M.roll` makes a forward roll (turns him to face −Y) | S23c/d | `_local_back_roll` (§5) — facing stays 180 |
| R11 | Blade passes through a body (A4 past his ear, A8 slide, the thrown sword) | 2682–2684, 2764–2770, 2950–2980 | `CH.blade_points` + a capsule distance check per frame in `end_lane` (≥ 0.12 m from the head/torso capsules); move the tip, not the body |
| R12 | "No glow" vs the bolts' blue in S22: the S23 cut must not look electric | S23b | no trail on the master's cut, no flash in S23; the spray is lit only by the storm key (az 270 backlight) |
| R13 | The act card's lower edge over the steam band glow | S21c 2551–2577 | the band top is at y −0.29…−0.32 — if its glow bleeds upward (volume + bloom), pitch the camera +2° (to 19.7°): the band drops to −0.40 |
| R14 | Double events: `M.clash` / `M.slash` emit clash/whoosh, and this doc lists whooshes | events.audit duplicates | emit the doc's whooshes only where the lane keys the swing with local poses (not through a macro); never emit `clash` by hand |
| R15 | Rain box coverage for the high cameras (S21a 14 m, S22a 16 m, S22f 15 m, S22h 30 m) | ground dry in those wides | vfx.py: key the rain object's GN `Forward` / `BoxXY` per cut (or raise `count`); for S22h (top-down) the rain is seen end-on as dots — acceptable |
| R16 | The pine top / halves are behind the rise or off the frame edge in S21a | S21a preview | the pine is at NDC (+0.31, −0.19…+0.16): if the rise hides the base, raise the camera 1 m; if the fork's arch leaves the frame top, `arch=0.25` |
| R17 | The shinobi's hachimaki tails do not "hang" in S23 | S23d/e | wind 0.5 from 2953 + wetness 1.0 feed `apply_secondary_motion`; if they still stream, key wind 0.2 for 2973–3072 |
| R18 | S22d fighters overlap (0.24 NDC apart at 8 m, φ −23°) | S22d | move the lens to (7.8, −0.4, 1.0) (φ ≈ −10°) — the bolt then strikes at x ≈ −0.9: use end (−40, −6, 0) |

Cross-lane notes
- **act2** (done): this lane relies on its steam band (to 3456) and rain (to 3500) and creates neither; its S20b ends in `jodan` at (0, 3) — the S21a first frame jumps to `raikiri_contact` across the hard cut (fine).
- **act1b / environment**: please keep the S11 shear's `until=None` (or ≥ 3456): Act III's readability (the kneel, every S22/S23 fighter from the knees up) depends on the 0.65 m stubble in front of (0, 2.6).
- **finale**: HANDOFF[3072] = the student in `kneel_sword_planted` (§5, sword tip in the mud at (0.02, −5.46)), the master in two-handed `gedan` at (0, 2.5); wind 0.5 (tails hanging), rain 1.0, storm_night, no flash since 2764; the rain-split corridor has closed by 3010; the pine is split (halves lying open, ember-lit steam plume until 3456). The S23e composition (kneeling figure left, standing figure right, profile, the steam band behind) is offered as the rhyme for S27.
- **audio**: `music_cue` act3_start + raikiri at 2497, low_point at 2950 (explicit); 7 lightning flashes with thunder delays in §3; the heartbeat 3001–3072 (tag low_point, D6) leads into the finale's silence at 3073.

## 8. Implementation order for `acts/act3.py` (suggested)
1. Constants from this doc (FORK_AT, IMPACT, PINE_TOP via `_local_pine_top`, contact points, cheat frames) + the `_local_*` helpers and `_local_POSES` (§5).
2. Root tracks (§1 table, incl. the ⟲ cheats with CONSTANT keys) for both rigs → verify against `out/dev/breakdown/act3/geom.py` (`SH_TRACK` / `EL_TRACK` hold the same data).
3. Weapon/costume states (§1) → poses per block (§3/§5) → the 9 `M.clash` contacts → the flash holds (`_local_hold`).
4. Cameras (21 `C.shot` calls, keys copied from the blocks) → `cameras.check_screen_direction` + `framing_qa`.
5. Environment per block (dim 2593 / restore 2785, sun per cut, wind keys) → flashes via `_local_flash` (7) → check `ENV.flash_log()` (7 accepted, 0 refused).
6. VFX per block (bolt + tree + afterglow; S22 bolts, trails; S23 spray ring + rain split + splashes).
7. Events per block (+ the music cues 2497 ×2 and 2950).
8. Layout preview 2497–3072 → contact sheet → compare with `geom_report.txt` / `summary.txt`; flash_qc on the preview.

## Implementation notes (act3 implementer, `src/blender/acts/act3.py`)

Deviations from the breakdown above, each with its reason (same story beats, same timing):
- **S23 thrown / tumble / kneel legs are FK or held rigid** (`a3_abort`, `a3_thrown`, `a3_land_back`, `a3_roll_tuck` with explicit thigh/shin/foot Eulers + `moves._feet_air`; `a3_knee_skid`, `a3_kneel_headup`, `a3_kneel_bowed` = the library `kneel_planted` legs marked `air`). The ball/ankle solver produced knees wrapped by 360 deg (the kneel's knee spun a full turn 2988→2991), hyper-extended knees in the flight and a 180-deg-twisted front thigh in the kneel (fixed with `knee_dir` (0, −0.5, 1) on the raised front leg; same guard on the elder's `zanshin_grounded` lunge).
- **Tumble ground contact**: the body track's root z is corrected per frame (`_local_ground_contact`) so the rolling body always touches the ground 2962–2978 (the head went 19 cm under the ground mid-roll) and never sinks in flight.
- **Sword during the flight/tumble** is keyed in world space upright on his right side (tip up out of the mud; it pointed into the ground on the landing).
- **A5 (2703)** contact given explicitly at (0.30, 0.78, 1.47) with the elder's `att_frac` 0.84 (monouchi): the natural crossing put the elder's kissaki 9 cm from the student's skull; now 38 cm, the tip ends past the roof block over his right shoulder.
- **S23b thrust** keyed by hand (windup / swing / strike + a 0.65 m lunge) instead of `moves.slash`, whose follow / settle keys at f+1..f+4 jittered into the abort.
- **ECU spark light** 12 W (19 W for S22g's face) instead of 40 W for the clashes seen from ~1 m (S22c/e/g, S22bb): the default blew the masked face out to white.
- **S22g** re-aims every 3 f at the evaluated head centre (a `(rig, 'head')` target is the head bone's root, i.e. the chin: at 75 mm the face sat above the frame).
- **S22h** top-down from 20 m (not 30 m): at 30 m the two fighters were a few pixels; the ring's ±Y arcs now touch the frame edges.
- **S23d** camera (1.3, 8.4, 2.6) → (0, −6, 0.9) (5° off the cut plane, over the elder's left shoulder): at (0.85, 8.4, 2.1) the master's shoulder covered the kneeling student at the end of the corridor.
- **S23e** deep two-shot from (4.8, −7.0, 1.3), 24 mm, key light az 318: the student kneeling in right profile, large, screen-left (head NDC −0.66), the master walking in 3/4 front screen-right (+0.53…0.59) with the far steam band behind him. The planned profile wide left the kneel as a head in the stubble at the frame edge; this also rhymes with the finale's S27 camera ((3.3, −6.3, 1.35)).
- Events: the 2946 stamp is a `land` (strength 1.0) — the foot bake already emits the `step` there; `whoosh` 2933 emitted by the lane (the thrust is hand-keyed).
