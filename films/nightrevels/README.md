<div align="center">

# Night Revels

<p><sub>An example film made with <a href="../../README.md"><b>CodeCinema</b></a></sub></p>

<p><b><i>The Night Revels of Han Xizai, Cat Edition</i>: a 128-second living handscroll in which every figure of the famous painting is a cat.</b></p>

[![Homepage](https://img.shields.io/badge/homepage-watch%20the%20film-e0a948?logo=githubpages&logoColor=white)](https://zjucqr.github.io/CodeCinema/)
[![License: MIT](https://img.shields.io/badge/license-MIT-2ea44f.svg)](../../LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776ab?logo=python&logoColor=white)](https://www.python.org/)
[![skia](https://img.shields.io/badge/2D-skia-4285f4.svg)](https://kyamagu.github.io/skia-python/)
[![ffmpeg](https://img.shields.io/badge/ffmpeg-required-007808?logo=ffmpeg&logoColor=white)](https://ffmpeg.org/)

**English** · [简体中文](README.zh-CN.md)

<img src="assets/images/still_470.jpg" width="92%" alt="Lady Li plays the pipa for the court cats">

</div>

---

**A night banquet in Southern Tang, painted on silk, and every guest is a cat.** The emperor's painter, a small tabby kitten, sneaks from screen to screen to sketch the minister Han Xizai's revels. The court cats are elegant in Tang silk, until their instincts give them away.

The camera travels right to left along one long scroll, as a viewer unrolls a handscroll, through the original's five scenes: listening to the pipa, the dance, the intermission, the wind ensemble and the farewell. Each scene wakes up as it enters the frame.
- **Picture:** gongbi painting (fine ink outlines, mineral pigments, hair strokes on fur) drawn as 2D vector puppets with skia on procedural silk.
- **Sound:** an original pentatonic score for pipa, jiegu, clappers, flutes, bili and guqin, plus synthesized meows, purrs and foley.

## ✨ Highlights

- 🤖 **Made by a coding agent.** Directed in plain language: a coding agent planned the story, designed the cats, wrote the renderer, animated every scene and composed the score.
- 🐈 **Thirteen breeds, one painting.** A Maine Coon host, a ginger troublemaker, a Persian pipa player, a Siamese dancer, a Sphynx monk and more, each a puppet with blinking, ear flicks, breathing and tail sway.
- 🎭 **A plot of cat instincts.** A cup pushed off the table, a moth that stops the dance, a refused wash, a flute that squeaks, a basket far too small, and a host who knew about the spy all along.
- 🎼 **The music moves the paws.** The score is note data first: the pipa player plucks, the drummer strikes and the clappers snap on the exact notes, and every gag lands on its sound within a frame.
- ⚡ **Fast to iterate.** A frame renders in well under a second; the whole film renders in about 90 s and its sound in about 10 s.

## 🚀 Quick start

```bash
git clone https://github.com/ZJUCQR/CodeCinema.git && cd CodeCinema
python3 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install .                                          # the framework + all dependencies

codecinema run nightrevels all      # build → render → audio → assemble
```

The finished film is written to `assets/film/`. Every command below is a step: `codecinema run nightrevels <step>` from anywhere in the repo, or `python src/run.py <step>` inside `films/nightrevels/`.

| Command | What it does |
|---|---|
| `build` | Write the sound-event list and the score (note data) |
| `still F[,F…]` | Render single frames to `out/stills/` |
| `render [--force] [--jobs N]` | Render the picture in parallel, resumable chunks |
| `audio` | Synthesize the score, cat voices, foley and ambience, then mix and master |
| `assemble` | Mux picture and sound into the film |
| `all` | Run the whole pipeline end to end |

## 🖼 Gallery

<div align="center">

| | |
|:---:|:---:|
| <img src="assets/images/still_600.jpg" alt="The ginger cat nudges a cup to the table edge"> | <img src="assets/images/still_1300.jpg" alt="The dancer pounces at the moth"> |
| **Listening to the pipa:** a cup, nudged to the edge | **The dance:** the moth, and the pounce |
| <img src="assets/images/still_1560.jpg" alt="Han refuses the wash basin"> | <img src="assets/images/still_2230.jpg" alt="The flute players giggle after the squeak"> |
| **Intermission:** water? no, thank you | **The wind ensemble:** after the squeak |
| <img src="assets/images/still_2650.jpg" alt="The moth lands on Han's nose"> | <img src="assets/images/still_3060.jpg" alt="The whole scroll"> |
| **Farewell:** the moth lands | **The whole scroll** |

</div>

## 🎨 Customize

The story is data plus code. The timeline and cue frames live in `src/common/config.py`, the score in `src/common/music.py`, the cast in `src/story/cast.py`, and the choreography and camera in `src/story/film.py`. Machine settings (output, parallel jobs, encoding, loudness) live in `film.toml` under `[settings]`.

| To change… | Edit |
|---|---|
| Story beats and their timing | `CUE` and `SECTIONS` in config |
| The music (melodies, tempo, which instrument plays) | `music.py`; playing paws follow the notes automatically |
| A cat's breed, coat, eyes, costume | `BREEDS` and the costumes in `cast.py` |
| Who stands where, gestures, gags, camera moves | `film.py` (keyed actor tracks and `Camera` keys) |
| The painting style (ink, silk, faces, furniture) | `src/paint/` |
| Parallel jobs, quality, loudness | `[settings]` in `film.toml` |

You can create your own configuration or override any setting:

```toml
# film.local.toml
[render]
jobs = 4
crf = 12
```

```bash
NIGHTREVELS_RENDER_JOBS=2 codecinema run nightrevels render
```

## 🗂 Project layout

```
films/nightrevels/
├── src/
│   ├── run.py              # the film's steps
│   ├── common/             # timeline + layout (config), the score as note data (music)
│   ├── paint/              # gongbi drawing: ink, silk, cat heads, robes and sleeves, props
│   ├── story/              # cast, animation tracks, the stage renderer, the whole film (film.py)
│   └── audio/              # instruments, cat voices, foley, ambience, score, mix
├── docs/                   # the director's plan
├── assets/                 # README images
└── film.toml               # the film's steps and settings
```

## 🧭 How it works

1. **The score comes first.** `music.py` writes every note as data. The choreography reads the same notes, so paws pluck, strike and snap on the beat.
2. **Actors on a scroll.** Every cat and prop is an actor with keyed tracks (position, gaze, ears, mouth, paws) plus idle life. The camera is keyed too, and slides along a silk scroll about 14 times wider than it is tall.
3. **Painted, not rendered.** Each frame is drawn in 2D: silk, mounting, furniture, puppets sorted by depth, candlelight and night tint, a vignette and fibre grain.
4. **Motion is sound.** Actions emit timed events (clink, chirp, purr, squeak…) that the audio engine places sample-accurately, beside the rendered score.
5. **Fast and resumable.** Frames render in parallel straight into encoded chunks, and the sound is synthesized and mastered to -14 LUFS in seconds.

The director's plan is in [docs/FILM_PLAN.md](docs/FILM_PLAN.md).

## 📜 License

Released under the [MIT License](../../LICENSE) © 2026 ZJUCQR.
