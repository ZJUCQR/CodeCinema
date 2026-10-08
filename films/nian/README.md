<div align="center">

# Nian

<p><sub>An example film made with <a href="../../README.md"><b>CodeCinema</b></a></sub></p>

<p><b>《年》: a three-and-a-half-minute Mandarin 3D cartoon about the New Year beast, written as one screenplay.</b></p>

[![Homepage](https://img.shields.io/badge/homepage-watch%20the%20film-e0a948?logo=githubpages&logoColor=white)](https://zjucqr.github.io/CodeCinema/#nian)
[![License: MIT](https://img.shields.io/badge/license-MIT-2ea44f.svg)](../../LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776ab?logo=python&logoColor=white)](https://www.python.org/)
[![Blender 5.2+](https://img.shields.io/badge/Blender-5.2%2B-ea7600?logo=blender&logoColor=white)](https://www.blender.org/)
[![ffmpeg](https://img.shields.io/badge/ffmpeg-required-007808?logo=ffmpeg&logoColor=white)](https://ffmpeg.org/)

**English** · [简体中文](README.zh-CN.md)

<img src="../../assets/nian/images/poster.jpg" width="92%" alt="The Nian beast in a snowy forest at night">

</div>

---

**Every New Year's Eve, the legend says, the beast Nian comes down from the mountains, and it fears the color red and loud noise.** While her grandmother tells the old story over a bowl of dumplings, little Xiaoman wonders why it keeps coming back. She slips out into the snow with a lantern and the dumplings and meets the beast in the forest: huge, gentle and hungry, wearing a faded red scarf.

When the villagers' firecrackers go off, Nian presses its paws over its ears and cowers, and Xiaoman stands in front of it. Then her grandmother sees the scarf. Sixty winters ago, as a little girl, she wrapped it around a shivering cub. It was never afraid of red. What it feared was spending the New Year alone.

- **Picture:** a snowy village with tiled roofs, couplets and lanterns, a warm kitchen, a moonlit pine forest and a sepia memory, all built from the set library and cel-shaded in Blender.
- **Sound:** a pentatonic theme for guzheng, erhu and dizi, festive gongs, drums and suona, Mandarin voices, the beast's wordless hums and whimpers, firecrackers, fireworks and falling snow.

## ✨ Highlights

- 🤖 **Made by a coding agent.** Directed in plain language: a coding agent wrote the story, the screenplay, the themes and every shot.
- 🧧 **A legend turned around.** The beast that fears red wears a red scarf, and the clues are on screen from its first appearance.
- 🏮 **Festival detail.** Upside-down 福 characters, couplets, swinging lanterns, a string of lights over the lane, firecrackers and fireworks.
- 🎞 **A memory in sepia.** The flashback is the same forest in warm memory light, with a grade, grain and vignette applied during assembly.
- 🗣 **Voices on every platform.** The Mandarin takes are stored as small recordings in `assets/nian/voices/`, with Chinese and English subtitle tracks.

## 🚀 Quick start

Follow the [setup guide](../../README.md#quick-start), then install [Blender 5.2 or later](https://www.blender.org/download/). Run from the repository root. On Windows, use `.\.venv\Scripts\python.exe` in place of `.venv/bin/python`.

```bash
.venv/bin/python -m codecinema run nian all
```

The finished film appears at `assets/nian/film/Nian.mp4`, with Chinese and English subtitle tracks. The couplets and titles use the bundled ZCOOL KuaiLe font, so the Chinese text renders the same on every platform.

## 🎬 Make it your own

Everything lives in [`screenplay.json`](screenplay.json). A character's voice is set once in the cast and each line carries its mood:

```json
"nainai": {"from": "grandma", "name": "奶奶",
           "voice": {"profile": "grandma", "speaker": "Serena", "pitch": -1.5,
                     "direction": "用七十多岁慈祥老奶奶的语气，声音温和，略带沙哑。"}}
```

```json
{"t": 0.6, "who": "nainai", "say": "它怕的，是一个人过年。", "mood": "tender",
 "en": "What it feared... was spending the New Year alone."}
```

Check the timing after changing lines: `codecinema run nian plan` warns when a spoken line runs into the next one. See the [Pebble guide](../pebble/README.md#-make-it-your-own) for the step-by-step commands.

## 📜 Credits

Story, screenplay, staging and score by a coding agent with CodeCinema. Music sampled from [GeneralUser GS](https://www.schristiancollins.com/generaluser.php) by S. Christian Collins. Chinese text set in ZCOOL KuaiLe (SIL Open Font License). Released under the [MIT License](../../LICENSE).
