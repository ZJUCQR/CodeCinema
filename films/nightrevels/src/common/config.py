"""
config.py - single source of truth: timeline, scroll layout, cue frames, tempo, paths.

Frames are 1-based at 24 fps. Scroll units (su): the silk is SCROLL_H tall and SCROLL_L long; the story reads right
to left, so the camera travels toward x = 0.
"""
import os

import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import settings as _settings  # noqa: E402  (film.toml [settings] + film.local.toml + environment)

ROOT = _settings.ROOT
SRC = os.path.join(ROOT, "src")
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
SECTIONS = [
    dict(id="prologue", name="序",     f0=1,    f1=264,  x0=12150, x1=13050),
    dict(id="listen",   name="听乐",   f0=265,  f1=840,  x0=9700,  x1=12150),
    dict(id="dance",    name="观舞",   f0=841,  f1=1464, x0=7200,  x1=9700),
    dict(id="rest",     name="暂歇",   f0=1465, f1=1848, x0=5100,  x1=7200),
    dict(id="winds",    name="清吹",   f0=1849, f1=2376, x0=2800,  x1=5100),
    dict(id="farewell", name="散宴",   f0=2377, f1=2712, x0=1100,  x1=2800),
    dict(id="epilogue", name="终",     f0=2713, f1=3072, x0=380,   x1=1100),
]
SCREENS_X = [12150, 9700, 7200, 5100, 2800]         # folding screens between the scenes

# ---------------------------------------------------------------- cue frames (story beats)
CUE = dict(
    fade_in=1, title_slip=40, caption=110, kitten_enter=150, kitten_hide=236,
    pipa_start=300, cup_push=560, cup_fall=628, sour_note=630, pipa_stop=632, lick=650, pipa_resume=680,
    pipa_end=820,
    drum_start=880, moth_enter=1170, heads_snap=1200, music_stop=1236, wiggle=1256, pounce=1290, land=1330,
    applause=1338, monk_sigh=1392,
    basin_offer=1500, toe_dip=1540, recoil=1546, shake=1550, lick_face=1580, knead=1510, yawn=1650,
    ear_turn=1740, kitten_freeze=1744, han_smile=1776, han_away=1800,
    flutes_start=1880, long_note=2150, squeak=2214, giggle=2222, flutes_resume=2262, boop=2320, flutes_end=2350,
    coda_start=2400, fish_grab=2470, fish_caught=2508, basket=2550, moth_nose=2632, blow=2676, coda_end=2700,
    sketch_done=2760, han_behind=2790, pat=2830, tea=2860, pull_back=2890, seal=2998, moth_seal=3012,
    title_card=3010, end=3072,
)

# ---------------------------------------------------------------- music (tempo per section)
TEMPO = dict(listen=76, dance=(96, 132), rest=60, winds=84, farewell=72)
TONIC_MIDI = 62                                     # D: gong mode D E F# A B
SCALE_GONG = [0, 2, 4, 7, 9]
SCALE_YU = [0, 3, 5, 7, 10]                         # yu mode (B yu) for the night pieces


def f2s(frame):
    return (frame - FRAME_START) / FPS


def s2f(sec):
    return int(round(sec * FPS)) + FRAME_START
