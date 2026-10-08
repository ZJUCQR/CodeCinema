<div align="center">

# Pebble

<p><sub>An example film made with <a href="../../README.md"><b>CodeCinema</b></a></sub></p>

<p><b>A little penguin with a big dream: a three-minute 3D cartoon written as one screenplay.</b></p>

[![Homepage](https://img.shields.io/badge/homepage-watch%20the%20film-e0a948?logo=githubpages&logoColor=white)](https://zjucqr.github.io/CodeCinema/#pebble)
[![License: MIT](https://img.shields.io/badge/license-MIT-2ea44f.svg)](../../LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776ab?logo=python&logoColor=white)](https://www.python.org/)
[![Blender 5.2+](https://img.shields.io/badge/Blender-5.2%2B-ea7600?logo=blender&logoColor=white)](https://www.blender.org/)
[![ffmpeg](https://img.shields.io/badge/ffmpeg-required-007808?logo=ffmpeg&logoColor=white)](https://ffmpeg.org/)

**English** · [简体中文](README.zh-CN.md)

<img src="../../assets/pebble/images/poster.jpg" width="92%" alt="Pebble beams as he flies underwater">

</div>

---

**Pebble wants to fly.** Every morning he climbs his rock, flaps as hard as he can and lands face first in the sand, while his friend Skye the seagull laughs from the sky. Leaf wings, a palm-leaf glider and a dizzying flap-a-thon all end the same way. At sunset Grandpa tells him that his wings aren't wrong; maybe his sky just isn't where he thinks it is.

The next day Skye dives for a fish, catches his foot in an old net and sinks. Pebble jumps from the cliff after him, and under the waves his "wrong" wings carry him like a bird.

- **Picture:** library characters (two penguins of different ages, two penguin chicks and two gulls) on the beach and underwater sets, cel-shaded in Blender with ink outlines.
- **Sound:** one hand-written theme arranged as playful, comic chase, tender, adventure, wonder and triumph cues, with English voices, babble giggles, Foley footsteps, splashes and the sea.

## ✨ Highlights

- 🤖 **Made by a coding agent.** Directed in plain language: a coding agent wrote the story, the screenplay, the theme and every shot.
- 🎭 **One screenplay, a whole film.** About 40 shots of beats like `{"who": "pebble", "waddle": "shore"}`. CodeCinema animates the walks, flaps, dives and expressions, frames each shot and places the sound.
- 🌊 **Two worlds.** A sunny beach through morning, noon, sunset and golden hour, and a sunlit cove under the sea with kelp, coral, fish and light shafts.
- 🎼 **A real orchestra.** Ukulele, glockenspiel, pizzicato, harp, strings, brass and choir from the General MIDI sound bank, mixed to −16 LUFS with ducking under dialogue.
- 🗣 **Voices on every platform.** The English takes are stored as small recordings in `assets/pebble/voices/`, so the film sounds the same without a speech model.

## 🚀 Quick start

Follow the [setup guide](../../README.md#quick-start), then install [Blender 5.2 or later](https://www.blender.org/download/). Run from the repository root. On Windows, use `.\.venv\Scripts\python.exe` in place of `.venv/bin/python`.

```bash
.venv/bin/python -m codecinema run pebble all
```

The finished film appears at `assets/pebble/film/Pebble.mp4`, with English subtitles as a selectable track. The first audio step downloads the 32 MB General MIDI sound bank once. Without a network connection the score uses the built-in synthesized instruments.

## 🎬 Make it your own

Everything lives in [`screenplay.json`](screenplay.json): the cast, sets, music themes and every shot. A shot names its camera and lists timed beats:

```json
{"id": "today", "dur": 4.0, "camera": {"size": "close", "on": ["pebble"], "side": "front_left"},
 "do": [{"t": 0.2, "who": "pebble", "face": "determined"},
        {"t": 0.4, "who": "pebble", "say": "Today's the day, Skye. I can feel it!", "mood": "determined"}]}
```

Work in small steps:

```bash
.venv/bin/python -m codecinema run pebble plan               # check the screenplay and the timeline
.venv/bin/python -m codecinema run pebble stills             # one frame per shot as a storyboard
.venv/bin/python -m codecinema run pebble render --preview   # a fast half-size pass of the whole film
.venv/bin/python -m codecinema run pebble render --frames 12s,40s   # or only a few moments
.venv/bin/python -m codecinema run pebble voices             # speak changed lines again
.venv/bin/python -m codecinema run pebble audio              # score, voices, Foley and ambience
.venv/bin/python -m codecinema run pebble assemble           # titles, subtitles and the MP4
```

Run `codecinema library` to browse the characters, sets, actions, expressions, sounds, instruments and music styles a shot can use.

## 📜 Credits

Story, screenplay, staging and score by a coding agent with CodeCinema. Music sampled from [GeneralUser GS](https://www.schristiancollins.com/generaluser.php) by S. Christian Collins. Titles set in Fredoka (SIL Open Font License). Released under the [MIT License](../../LICENSE).
