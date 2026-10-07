"""
config.py - single source of truth: timeline, scroll layout, cue frames, tempo, paths.

Frames are 1-based at 24 fps. Scroll units (su): the silk is SCROLL_H tall and SCROLL_L long; the story reads right
to left, so the camera travels toward x = 0.
"""

from codecinema.productions import film_root, source_root
import json

_story = json.loads((film_root("nightrevels") / "story.json").read_text(encoding="utf-8"))
import os

import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import settings as _settings  # noqa: E402  (pyproject.toml film settings + film.local.toml + environment)

ROOT = _settings.ROOT
SRC = str(source_root("nightrevels"))
OUT = _settings.path("paths", "out_dir")
FRAMES_DIR = os.path.join(OUT, "frames")
AUDIO_DIR = os.path.join(OUT, "audio")
EVENTS_JSON = os.path.join(OUT, "events.json")
NOTES_JSON = os.path.join(OUT, "notes.json")
SILK_NPY = os.path.join(OUT, "silk.npy")
FINAL_VIDEO = _settings.path("paths", "final_video")
FFMPEG = _settings.tool("ffmpeg")
FFPROBE = _settings.tool("ffprobe")
RENDER_JOBS = int(_settings.get("render", "jobs", 0)) or max(1, (os.cpu_count() or 4) - 2)
CHUNK = int(_settings.get("render", "chunk", 96))
RENDER_CRF = int(_settings.get("render", "crf", 15))
RENDER_PRESET = str(_settings.get("render", "preset", "medium"))
AUDIO_BITRATE = str(_settings.get("video", "audio_bitrate", "320k"))

FPS = 24
W, H = 1920, 1080
FRAME_START, FRAME_END = 1, 3072                    # 128 s
AUDIO_SR = int(_settings.get("audio", "sample_rate", 48000))

# ---------------------------------------------------------------- scroll
SCROLL_L, SCROLL_H = 13800, 1000
SS = 1.3                                            # scene scale (characters and furniture)
Z_SCROLL = H / SCROLL_H                             # zoom that fits the silk height
MOUNT_R = 13050                                     # brocade mounting starts right of this
MOUNT_L = 380                                       # ... and left of this
FLOOR = 900                                         # front baseline (feet / furniture bases)

# ---------------------------------------------------------------- sections (frames) and x spans (su)
SECTIONS = _story["sections"]
SCREENS_X = [12150, 9700, 7200, 5100, 2800]         # folding screens between the scenes

# ---------------------------------------------------------------- cue frames (story beats)
CUE = _story["cues"]

# ---------------------------------------------------------------- music (tempo per section)
TEMPO = _story["tempo"]
TONIC_MIDI = 62                                     # D: gong mode D E F# A B
SCALE_GONG = [0, 2, 4, 7, 9]
SCALE_YU = [0, 3, 5, 7, 10]                         # yu mode (B yu) for the night pieces


def f2s(frame):
    return (frame - FRAME_START) / FPS


def s2f(sec):
    return int(round(sec * FPS)) + FRAME_START
