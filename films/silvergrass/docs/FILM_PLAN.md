# Duel in the Silver Grass (《芒原决战》): director's plan

> An **original homage** short film. It pays tribute to the rhythm and aesthetics of the final boss duel in action games of the "Sekiro" kind: a silver-grass field, sunset, spear and fire, thunderstorm, one decisive stroke. The characters, designs, names, techniques, music and on-screen text are **all original**. No character models, names, music or UI from FromSoftware games are used (no "shinobi execution" or "death" kanji, no posture bar).

## 1. Overview

| Item | Content |
|---|---|
| Title | 《芒原决战》 *Duel in the Silver Grass* |
| Length | 160 s (3840 frames at 24 fps) |
| Format | Rendered at 2.35:1 (1920×816), letterboxed to 1920×1080, H.264 + AAC stereo |
| Style | Stylised low-poly with cinematic light (silhouettes, backlight, volumetric haze, bloom, motion blur, depth of field) and the camera language of samurai cinema |
| Hero | **Saku (朔)**, a masterless shinobi. Lean; charcoal shinobi garb (symmetric cloth sleeves and arm guards), ash-grey tapered hakama, crimson sash, crimson headband with two long tails, cloth mask; a black-scabbard katana (often two-handed) and three kunai |
| Final boss | **Tenkosai (天鼓斋)**, founder of the Tenko school, an old lay-monk sword master. Tall; shaven head with an old scar, thick grey brows, long grey beard bound near the tip with a vermilion cord; persimmon-brown kimono, ash-grey hakama, ochre haori with an original "moon over silver grass" crest on the back, straw hat; a long katana, and a vermilion straight spear carried slung across his back in a black-lacquer sheath |
| Technology | Blender 5.2 (fully procedural modelling, rigging, animation, VFX and cameras in Python; EEVEE rendering), numpy/scipy for all music and sound, Pillow for the calligraphic titles, ffmpeg for assembly |

## 2. Story in three acts (the three phases of a boss fight)

- **Prologue (0:00–0:18):** black with the epigraph "剑者，以一生赴一瞬。" (*For a swordsman, a whole life goes to meet a single instant.*) → an extreme wide of the sunset grass sea and the title 《芒原决战》 → Saku walks in through the grass → under his straw hat the old master lifts his head.
- **Act I · Blade (0:18–1:08):** the draw and the stand-off, a quick-draw dash, the first clash of sparks, a three-hit combo, the counter. Saku drops into the grass and vanishes; Tenkosai closes his eyes and listens, then answers with a draw-cut so fast it **shears the grass tops** and flushes Saku out. Saku leaps and strikes down, the blades lock, and a **perfect deflect** breaks the master's balance: the straw hat is cut in two, revealing the shaven, scarred head. He sheathes, sheds the haori to reveal a white tasuki cord, and draws the vermilion spear over his shoulder, its sheath spinning away. The sun sets and the sky turns crimson.
- **Act II · Fire (1:08–1:44):** the spear butt strikes the ground and a **ring of fire** erupts through the grass, enclosing the arena; the discarded haori catches fire. Sweeps, a string of thrusts (the third turned aside by Saku's off-hand kunai as he slides along the shaft) and a low sweep; kunai against the spinning spear and a leaping slam; Saku slides inside the spear's reach, fights close and is kicked away. The thrown spear is deflected into the flames, Tenkosai draws his katana again, and the first thunder rolls.
- **Act III · Thunder (1:44–2:08):** the downpour turns the fire to steam and Tenkosai raises his sword into jodan, facing the storm. **Raikiri:** a bolt comes down on him and he cuts it; it forks and splits the lone pine on the rise. From then on the fight is lit only by lightning, each flash freezing a new moment of the duel. Saku's one counter-attack drives him back a step; a grounded full-power cut splits the curtain of rain and its spray ring throws Saku to one knee.
- **Finale (2:08–2:40):** the rain stand-off and total silence, a mirrored quick-draw, and in a white flash of lightning **a single crossing pass**; they stand back to back. Tenkosai's blade snaps; the vermilion cord of his beard is cut and drifts away in slow motion with a thin line of red mist. He kneels on one knee, leaning on the broken sword. The rain stops, the clouds part, the full moon rises; Saku sheathes and bows deeply. The camera cranes up over the moonlit grass: 「终」 (*The End*).

## 3. Shot list (30 shots; every shot boundary is a hard cut)

| Shot | Frames | Length | Content | Camera |
|---|---|---|---|---|
| S01 | 1–96 | 4.0 s | Black, the wind rises, epigraph | Title overlay |
| S02 | 97–240 | 6.0 s | Extreme wide of the sunset grass sea; Tenkosai a tiny silhouette (straw hat, spear slung on his back), the lone pine on the rise; Saku walks in from the bottom of frame; main title | Ultra-wide, slow crane push-in |
| S03 | 241–336 | 4.0 s | Low tracking shot behind Saku through the grass (the grass parts), tilting up to his back; name card 朔 | Knee-height tracking, tilt up |
| S04 | 337–432 | 4.0 s | Medium close-up of Tenkosai, eyes shaded by the hat, the corded beard and haori in the wind, the spear shaft behind his shoulder; he lifts his head; name card 天鼓斋 | Slow push, shallow depth of field |
| S05 | 433–540 | 4.5 s | Profile two-shot with a huge setting sun between them; Saku draws into guard, Tenkosai sinks into an iai stance; act card 一之幕 · 剑 | Telephoto profile, silhouettes |
| S06 | 541–588 | 2.0 s | ECU: the blade slides out of the scabbard mouth, *click*, a line of light on steel | Extreme close-up |
| S07 | 589–672 | 3.5 s | The quick-draw dash; Saku deflects: **the first sparks** | Speed ramp, impact shake |
| S08 | 673–840 | 7.0 s | Three-hit combo (diagonal, rising cut, thrust): two deflected, one dodged | Moving medium shots |
| S09 | 841–936 | 4.0 s | Saku counters with two cuts: one parried, one evaded | Over the shoulder |
| S10 | 937–1032 | 4.0 s | Circling stand-off; Saku vanishes into the tall grass, only ripples betray him; Tenkosai listens with closed eyes; heartbeat | Lateral dolly through foreground grass |
| S11 | 1033–1176 | 6.0 s | A draw-cut shears a whole arc of grass tops (plumes burst into fluff, no glowing projectile); Saku leaps over the cut line and strikes down; overhead block | Wide, following the leap |
| S12 | 1177–1344 | 7.0 s | A flurry of six clashes on the beat, a blade lock, the shove | Fast multi-angle cutting |
| S13 | 1345–1488 | 6.0 s | Perfect deflect (flash ring) → Tenkosai loses balance → the hat is cut in two → he skids back | Slow motion, close-ups |
| S14 | 1489–1632 | 6.0 s | He sheathes, sheds the haori, draws the spear over his shoulder, the sheath spins away; the sun sets, the sky turns red, embers rise | Low angle |
| S15 | 1633–1728 | 4.0 s | Spear butt strikes, the ring of fire erupts, the haori burns; act card 二之幕 · 焰 | Top-down → level |
| S16 | 1729–1920 | 8.0 s | Spear onslaught: a 360° sweep, three thrusts (the third turned aside by a kunai), a low sweep vaulted | Medium, following |
| S17 | 1921–2064 | 6.0 s | Three kunai deflected by the spinning spear; a leaping slam erupts fire and dust; Saku rolls clear | Wide |
| S18 | 2065–2256 | 8.0 s | A low sliding cut inside the spear's reach, sword against shaft, the kick, Saku stops his skid with his sword | Handheld |
| S19 | 2257–2400 | 6.0 s | The spear is hurled, deflected and spins into the flames; Tenkosai draws again; first thunder | Short speed ramp |
| S20 | 2401–2496 | 4.0 s | The downpour hits, the fire collapses into steam, lightning in the clouds; Tenkosai raises jodan toward the storm (a stance, not a summoning) | High wide |
| S21 | 2497–2592 | 4.0 s | **Raikiri:** the bolt is cut, it forks and splits the lone pine (flash → flame → steam in the rain); a few frames of afterglow on the blade; act card 三之幕 · 雷 | White flash, low angle |
| S22 | 2593–2784 | 8.0 s | Strobe flurry lit almost only by lightning, each flash a new tableau, near-darkness between; bolts strike the field | Strobe cutting |
| S22b | 2785–2880 | 4.0 s | Saku's counter-attack, his only push in Act III: three strikes drive Tenkosai back a step | Following |
| S23 | 2881–3072 | 8.0 s | The low point: a grounded full-power cut splits the curtain of rain; the spray ring throws Saku to one knee | Real time, wide |
| S24 | 3073–3264 | 8.0 s | Rain stand-off in total musical silence: mirrored iai, the click of a sheathing guard, a drop falling from the headband tail; both launch | Alternating close-ups |
| S25 | 3265–3360 | 4.0 s | **A single crossing pass inside the white flash**; they stand back to back | Full white → slow motion |
| S26 | 3361–3456 | 4.0 s | Saku sheathes; on the click Tenkosai's blade snaps; the beard cord is cut and drifts away with red mist | Locked off |
| S27 | 3457–3600 | 6.0 s | Tenkosai kneels on the broken sword; the rain stops and the moon rises; Saku turns and bows | Composed two-shot |
| S28 | 3601–3744 | 6.0 s | Crane up as Saku walks away, the grass closing behind him; the silver grass sea under the moon | Crane up |
| S29 | 3745–3840 | 4.0 s | The broken blade tip in moonlit grass; bell and 「终」; fade to black | Still life, title |

## 4. Art direction

- **Setting:** an endless silver-grass field (about 250k geometry-nodes clumps with plumes; travelling gusts driven by flowing noise; grass parts around the fighters); shorter grass in an arena about 8 m across; a lone pine on a gentle rise; layered mountain silhouettes and a distant pagoda; atmospheric haze.
- **Four lighting states:** `dusk_gold` (low warm key, strong rim light, a huge sun disc) → `crimson_fire` (blood-red dusk and the ring of fire: orange firelight, embers, smoke) → `storm_night` (dark blue-grey, rain streaks, lightning inside the clouds) → `moon_clear` (cold silver moonlight, stars, a huge full moon).
- **VFX:** clash sparks, blade trails, the grass-shearing cut line and flying plume fluff, fire ring flames and embers, dust and grass debris, procedural lightning (main channel plus branches, forking where it is cut), the lightning-struck pine, blade afterglow, rain and the parting rain curtain, steam, the spray-ring shockwave, restrained red mist.
- **Originality guard-rails:** no summoning or throwing of lightning (Act III follows the public-domain *Raikiri* legend: the master cuts a falling bolt), no spear pulled from the ground, no glowing sword projectiles, no HUD, posture bar or on-screen kanji, no prosthetic arm or scarf on the hero; the score uses only the film's own leitmotifs.
- **Post:** AgX colour management, glare, vignette, film grain, a slight chromatic aberration on impact frames. The sun direction may be cheated per shot for the best composition, a common film practice.

## 5. Sound design (all procedurally synthesised and original, 48 kHz stereo)

- **Score:** the Japanese *miyako-bushi* (in) scale (D–E♭–G–A–B♭). It uses only the two original leitmotifs in `config.LEITMOTIFS` and their variations: "Tenko", solemn and descending, ending on the E♭→D half-step sigh; and "Saku", a nimble leaping koto figure. Every instrument is synthesised: large taiko, shime-daiko, hyoshigi, shakuhachi (breath, vibrato, pitch bends), koto (Karplus-Strong), shamisen (with *sawari* buzz), sustained low strings, choir pads, temple bell (modal synthesis) and heartbeat.
  - Prologue: wind, sparse shakuhachi, a low drone, a bell on the main title.
  - Act I: taiko groove at 92 BPM, a koto ostinato and shakuhachi melody; the music lifts on the first clash.
  - Hat cut: an accent, then tense drones and heartbeat.
  - Act II: furious taiko at 120 BPM, a shamisen riff, crackling fire ambience.
  - Act III: storm at 140 BPM with choir, string tremolo and thunder accents; in S24 the music stops dead and only the rain remains.
  - The crossing pass: a huge impact with a long reverb tail → epilogue: solo shakuhachi, koto and temple bell, resolving to the tonic and fading out.
- **Sound effects** (driven frame by frame by the event list `out/events.json`, so picture and sound stay in sync): metallic clashes (modal inharmonic partials plus noise transients), sword whooshes, the spear's hiss, footsteps in grass, cloth, drawing / sheathing / guard clicks, the hat splitting, fire ignition and crackle, thunder (far and near), lightning strikes, electric crackle, rain, steam hiss, shockwaves, the blade snapping, falls, wind. Each sound is panned by the character's horizontal position on screen.
- **Mix:** separate music, SFX and ambience stems, side-chain ducking, loudness normalised to about −14 LUFS with true peak ≤ −1 dBTP.

## 6. Technical pipeline

```
src/common/config.py        single source of truth for the timeline (shots, acts, handoffs, titles, cues, palette)
src/blender/                runs inside Blender 5.2
  bl_util.py                5.2 API helpers (keyframes, fcurves / channelbags, easing, materials)
  characters.py             both characters: skeleton, skinned meshes, costume, weapons, props, sockets
  poses.py / moves.py       pose library and move macros (slash, deflect, dodge, jump, roll, dash, iai … all emit events)
  environment.py            terrain, grass, sky, the four lighting states, wind, wetness, flashes
  vfx.py                    every effect (procedural, no baking)
  cameras.py                cameras, cuts, shake, depth of field
  events.py                 event registry and export (with stereo panning)
  render_setup.py           EEVEE, colour management, compositor
  acts/<lane>.py            six choreography lanes: prologue / act1a / act1b / act2 / act3 / finale
  build_scene.py            builds the whole scene → out/scene.blend + out/events.json
  render_frames.py          renders (final / preview, frame ranges)
src/render_supervisor.py    resumable multi-slot final render
src/audio/                  dsp / instruments / sfx / ambience / score / mix → out/audio/final_mix.wav
src/post/                   titles (calligraphic title frames) / assemble (ffmpeg master) / film QC
```

## 7. Production process

1. **Pre-production review:** film language, technical feasibility and originality / copyright distance, plus a tested Blender 5.2 API handbook → a revised plan.
2. **Parallel asset build** (per track: build → render self-check → review → fix): characters and rigs, poses and move macros, environment and lighting, the VFX library, the audio engine and score, the title and assembly pipeline.
3. **Choreography and cameras** (the six lanes in parallel, each owning its own frame span) → low-resolution previews → review → fix → a joint review of the whole film in low resolution.
4. **Final render** (in the background, in chunks, resumable) → mix against the final event list → ffmpeg assembly → film QC (frame sampling, A/V sync, loudness).

## 8. Quality gates

- Every module has a visual self-check (stills, contact sheets or spectrograms) and passes an independent review.
- Every shot gets at least one low-resolution preview review; clash sparks must sit at the closest point between the two blades.
- The film has no black or wrong frames (except the designed black of S01 and the end of S29), A/V sync within one frame, and no clipping.
