A complete procedural motion-comic film in three connected episodes, adapting chapters 1–6 of Sanjiu Yinyu's novel in their original order.

**[Watch online](https://zjucqr.github.io/CodeCinema/xishen/watch.html)** · **[Film guide](https://github.com/ZJUCQR/CodeCinema/blob/main/films/xishen/README.md)** · **[All example films](https://zjucqr.github.io/CodeCinema/#films)**

| Specification | Details |
| --- | --- |
| Runtime | 11:00 (660 seconds) · 3 episodes |
| Picture | 1920 × 1080 · 24 fps · H.264 |
| Audio | Stereo AAC · emotion-directed Mandarin voices · scene-led chamber score and sound effects |
| Renderer | Skia motion comic throughout · 67 shots · shared, individually designed cast |

## Downloads

| MP4 | Runtime |
| --- | --- |
| [Complete film](https://github.com/ZJUCQR/CodeCinema/releases/download/xishen/xishen_complete.mp4) | 11:00 |
| [Episode 1 · The Ghost Comes Home](https://github.com/ZJUCQR/CodeCinema/releases/download/xishen/ep01.mp4) | 3:30 |
| [Episode 2 · We Are Watching You](https://github.com/ZJUCQR/CodeCinema/releases/download/xishen/ep02.mp4) | 3:30 |
| [Episode 3 · Chen's Directing Rules](https://github.com/ZJUCQR/CodeCinema/releases/download/xishen/ep03.mp4) | 4:00 |

Only finished MP4s are attached to this release. They include burned captions, a selectable subtitle track and chapter markers.

All three episodes share one visual style and cast. Rain, theatre, investigation, wonder and comedy scenes use distinct musical cues.

## Reproduce

Follow the [setup guide](https://github.com/ZJUCQR/CodeCinema/blob/main/docs/GETTING_STARTED.md), then run from the repository root:

```bash
codecinema run xishen all --narration required
```

Published voices use local Qwen3-TTS CustomVoice on Apple Silicon, with waveform-gated, syllable-aligned mouth animation. Install the optional speech pack with `python -m pip install -e ".[speech]"` and add `--speech-engine local` to reproduce this edition. Other platforms can supply WAV recordings. Use `--narration off` for a captions-and-music edition.

Repository author: **ZJUCQR**. Repository code: [MIT](https://github.com/ZJUCQR/CodeCinema/blob/main/LICENSE). Original novel: **Sanjiu Yinyu**, [official edition](https://fanqienovel.com/page/7276384138653862966); the novel's rights remain with its respective rights holders.
