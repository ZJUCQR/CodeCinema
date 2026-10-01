# The Night Revels of Han Xizai, Cat Edition (《韩熙载夜宴图 · 猫》): director's plan

## 1. Concept

Gu Hongzhong's 10th-century handscroll *The Night Revels of Han Xizai* is famous for two things: its five scenes read right to left and separated by folding screens, and its backstory. The Southern Tang emperor, suspicious of his minister Han Xizai, sent the court painter Gu Hongzhong to attend Han's night banquets in secret and paint what he saw.

This film brings the scroll to life with **cats**. Every figure is a cat of a different breed, dressed in sumptuous Tang-style court costume. The camera travels along the silk the way a viewer unrolls a handscroll, and each scene wakes up as it enters the frame. The spy story becomes the plot: a kitten painter sneaks from screen to screen, sketching. The elegant cats keep betraying that they are, after all, cats.

| Item | Content |
|---|---|
| Title | 《韩熙载夜宴图 · 猫》 *The Night Revels of Han Xizai, Cat Edition* |
| Length | ~122 s (2928 frames at 24 fps), 1920×1080, stereo |
| Look | Gongbi (工笔) figure painting on aged silk: fine even ink contours, flat mineral pigments with soft washes, fine hair strokes (丝毛) on the fur, plain silk ground, screens with ink landscapes |
| Camera | A continuous right-to-left journey along one long scroll (the canvas is about 11:1, like the original), with push-ins for faces and gags and a final pull-back that reveals the whole painting |
| Sound | An original score in the Chinese pentatonic modes for pipa, jiegu drum, clappers, flutes, bili and guqin, plus synthesized meows, purrs and foley. The music drives the playing paws, and the actions trigger the sounds |
| Technology | Python + skia (2D vector drawing, puppet animation), numpy/scipy (music and sound), Pillow (calligraphy and seals), ffmpeg (assembly) |

## 2. Cast (breed → role)

| Role | Breed | Costume and character |
|---|---|---|
| **Han Xizai** 韩熙载, the host (appears in every scene, as in the original's continuous narrative) | Maine Coon, grey-brown tabby, ear tufts, big ruff | Tall black gauze hat, dark long robe; wise, weary, amused. He knows more than he shows |
| **Lang Can** 郎粲, the top scholar | Ginger tabby | Vermilion round-collar robe; the mischief-maker (cup-pusher, fish thief) |
| **Lady Li** 李姬, pipa player | White Persian, blue eyes | Pale-blue high-waisted dress and a flowing shawl; serene, plays with closed eyes |
| **Li Jiaming** 李家明, music director | Tuxedo cat | Pale robe; attentive, counts the beat with his ears |
| **Wang Wushan** 王屋山, the dancer | Siamese | Blue dance dress with very long sleeves; graceful until the moth appears |
| **Monk Deming** 德明和尚 | Sphynx (bald, like a monk) | Ochre kasaya; embarrassed to be here, paws clasped, ears flat |
| Three flutists | Calico, Russian Blue, Scottish Fold | Colourful dresses; the Scottish Fold runs out of breath |
| Clapper player | Cream British Shorthair | Round, calm and dependable |
| Two attendants | Munchkin, Abyssinian | Short jackets, trays, tea |
| **Gu Hongzhong** 顾闳中, the painter-spy | Small brown tabby kitten | Grey scholar's robe, brush and sketchbook; our guide through the scroll |
| **The moth** | – | The running gag: every cat's instinct follows it |

## 3. Story (right to left, five scenes)

**Prologue (0:00–0:10).** Black, then silk. The right end of the scroll comes into view: brocade mounting and a title slip reading 《韩熙载夜宴图》 with a small red paw-print seal. A caption in brush script reads 南唐 · 韩府 · 夜 (Southern Tang · the Han residence · night). The kitten painter tiptoes in with brush and sketchbook and hides behind the first screen. A moth drifts past a candle.

**Scene 1, Listening to the pipa 听乐 (0:10–0:34).**
- Lord Han sits cross-legged on the curtained couch beside Lang Can. Tables are laid with fruit and wine ewers.
- Lady Li plays the pipa, and every listener's ears swivel toward each phrase.
- Lang Can, bored, holds eye contact with the camera while slowly pushing a wine cup to the table edge. It falls with a clink and the pipa stumbles on a sour note. Every head turns, and Lang Can licks his paw innocently. Lord Han closes his eyes, the music resumes, and the kitten sketches.

**Scene 2, Watching the dance 观舞 (0:34–1:00).**
- Wang Wushan dances the Liuyao (六幺), her long sleeves swirling. Lord Han stands and beats the red jiegu drum, the clappers keep time, and the monk looks away.
- The tempo builds, then the moth flies in. Every head snaps to it in unison and the drumming stops.
- The dancer freezes mid-turn with pupils huge, wiggles her hips and pounces, sleeves flying. She misses, and lands in a perfect dance pose exactly on Lord Han's final drum stroke.
- Paws applaud and the monk exhales.

**Scene 3, Intermission 暂歇 (1:00–1:16).**
- Candlelight and crickets. An attendant offers Lord Han a basin of water. He dips a toe, recoils, shakes his paw, and washes his face by licking instead.
- On the couch, one cat kneads the quilt, purring with eyes closed, and another gives an enormous yawn.
- Behind the screen the kitten sketches furiously. Lord Han's ear swivels toward him and the kitten freezes. Han's eyes narrow, then soften into a knowing smile, and he looks away.

**Scene 4, The wind ensemble 清吹 (1:16–1:38).**
- Lord Han sits cross-legged on a chair, robe open over his fluffy belly, fanning himself.
- Three flutists and a bili player perform a sweet melody while Li Jiaming claps the rhythm.
- The Scottish Fold holds a long note, puffs out her cheeks, runs out of breath and squeaks, and the ensemble giggles.
- Behind a screen, a guest and a lady touch noses through the gap, the original's flirtation turned into a cat greeting.

**Scene 5, Farewell 散宴 (1:38–1:52).**
- Guests take their leave. Lord Han stands, raising a drumstick in farewell as in the original.
- Lang Can pockets a fish on the way out and is caught by an attendant.
- A cat squeezes into a far-too-small tea basket and sits, satisfied.
- The moth finally lands on Lord Han's nose. He goes cross-eyed and blows it gently away.

**Epilogue (1:52–2:02).**
- The kitten finishes his sketch. Lord Han appears behind his screen, looks over the drawing, pats the kitten on the head and hands him a cup of tea: he knew all along.
- The camera pulls far back until the whole scroll is visible as one painting. A red seal 猫 stamps the corner and the moth settles on it.
- Title card and credits: *Every stroke, note and meow is generated by code.*

## 4. Visual design

- **Silk:** aged warm silk (procedural fibres, mottling, darker edges and foxing), with brocade mounting and a title slip at the start. Pigments sit *on* the silk, with a subtle multiply of the fibre texture over everything.
- **Line:** gongbi contours in warm ink of even width (铁线描), with hair strokes on fur, fold lines on robes and ink landscapes on the screens.
- **Colour:** mineral palette of vermilion, malachite green, azurite blue, ochre, lead white and ink black; furniture in dark lacquer.
- **Light:** candle stands with flickering warm halos; the whole scroll warms and dims through the night, and cool dawn arrives in the epilogue.
- **Faces:** eyes (slit to round pupils, blinks, happy ^ ^ eyes), ears (swivel, airplane ears), mouth (w, open, yawn), whiskers, blush. Every cat keeps an idle life of breathing, blinking, ear flicks and tail sways, so the painting is never frozen.

## 5. Sound

- **Score:** original pieces in the gong and yu pentatonic modes.
  - Scene 1: a pipa solo with lunzhi tremolo.
  - Scene 2: the Liuyao dance tune for pipa, flute, jiegu and clappers, accelerating to the pounce, a stop, then the final stroke.
  - Scene 3: sparse guqin over crickets.
  - Scene 4: a flute and bili ensemble.
  - Scene 5: a gentle coda. Epilogue: guqin, bell and a final pipa chord.
- **Instruments** are synthesized: pipa and guqin (plucked-string models), dizi and bili (breath and reed models), jiegu, clappers and a bell.
- **Cats and foley:** meows (formant glides), purrs, trills, a yawn squeak, cup clink, tea pour, paws on floorboards, sleeve swishes, fan, applause of soft paws, moth flutter.
- **Sync:** instrument-playing paws animate on the score's note onsets, and actions emit timed sound events. The mix is mastered to -14 LUFS.

## 6. Pipeline

```
src/common/config.py     timeline, scroll layout, cast, cues (single source of truth)
src/paint/               ink primitives, silk, cat puppets, costumes, furniture, props, scene graph, camera
src/story/               the five scenes + prologue/epilogue as keyed animation; events.json
src/audio/               instruments, score (note events), SFX, mix
src/post/                titles and seals, assembly + QC
src/run.py               check / render / audio / titles / assemble / all
```
Frames render in parallel across CPU cores (2D vector drawing takes well under a second a frame), so the whole film can be iterated quickly.
