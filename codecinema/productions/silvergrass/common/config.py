"""
Single source of truth for timing, paths and global constants.
Pure Python (no deps) — importable from Blender's Python 3.13 and the .venv Python 3.14.

Film: "Duel in the Silver Grass" — an ORIGINAL homage duel (original characters, original score).
    Shinobi : Saku, the masterless shinobi                     — rig object "SHINOBI_rig"
    Elder   : Tenkosai, founder of the Tenko school, an old lay-monk (nyudo) swordmaster — rig object "SAINT_rig"
              (on-screen text never calls him "Sword Saint"; internal code names keep SAINT_*)
Design notes:
    Saint  : shaven head (lay monk) with an old scar, thick grey brows, long grey beard bound near the tip with a
             vermilion cord; persimmon-brown (kakishibu) kimono, ash-grey (nibi-iro) hakama, ochre haori with a
             'moon over silver grass' roundel on the back; wide straw hat (Act I, cut in S13);
             long katana; vermilion straight yari carried SLUNG diagonally on his back in a black-lacquer
             spear sheath (drawn over the shoulder in S14); white tasuki cord revealed when he sheds the haori (S14).
    Shinobi: charcoal fitted garb, symmetric cloth sleeves + arm guards, ash-grey tapered hakama, crimson sash,
             crimson hachimaki with two long (untattered) tails, cloth face mask; no scarf, no orange/ochre;
             black-scabbard katana (often two-handed), three kunai.
"""

from codecinema.productions import film_root, source_root
import json

_story = json.loads((film_root("silvergrass") / "story.json").read_text(encoding="utf-8"))
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))) if os.path.dirname(os.path.abspath(__file__)) not in sys.path else None
import settings as _settings   # noqa: E402  (machine / taste settings: the film settings in pyproject.toml, env overrides)

S = _settings.SETTINGS

# ---------------------------------------------------------------- paths (all derived from the repo root + settings)
ROOT = _settings.ROOT
SRC = str(source_root("silvergrass"))
OUT = _settings.path("paths", "out_dir")
FRAMES_DIR = os.path.join(OUT, "frames")          # final renders: 00001.png ...
PREVIEW_DIR = os.path.join(OUT, "previews")
AUDIO_DIR = os.path.join(OUT, "audio")
TITLES_DIR = os.path.join(OUT, "titles")
LANES_DIR = os.path.join(OUT, "lanes")            # single-lane builds (scene.blend, events.json, build_report.json)
DEV_DIR = os.path.join(OUT, "dev")                # diagnostic sheets (pose atlas, choreography plots)
LOCK_DIR = _settings.path("paths", "lock_dir") or os.path.join(OUT, ".locks")
SCENE_BLEND = os.path.join(OUT, "scene.blend")
EVENTS_JSON = os.path.join(OUT, "events.json")
BUILD_REPORT_NAME = "build_report.json"
BUILD_REPORT_JSON = os.path.join(OUT, BUILD_REPORT_NAME)
RENDER_LOG_NAME = "render_log.jsonl"              # written next to the frames
FINAL_MIX_WAV = os.path.join(AUDIO_DIR, "final_mix.wav")
DEMO_MIX_WAV = os.path.join(AUDIO_DIR, "demo_mix.wav")
MIX_REPORT_JSON = os.path.join(AUDIO_DIR, "mix_report.json")
DRAFT_EVENTS_JSON = os.path.join(AUDIO_DIR, "draft_events.json")
FINAL_QC_JSON = os.path.join(OUT, "final_qc.json")
FINAL_VIDEO = _settings.path("paths", "final_video")
FRAME_DIGITS = 5
FRAME_PATTERN = os.path.join(FRAMES_DIR, "#" * FRAME_DIGITS)     # Blender output pattern


def frame_name(frame, ext=".png"):
    """File name of a rendered frame: 00001.png"""
    return f"{int(frame):0{FRAME_DIGITS}d}{ext}"


def lane_dir(lane):
    return os.path.join(LANES_DIR, lane)

# ---------------------------------------------------------------- external tools + fonts (auto-detected, overridable)
BLENDER_BIN = _settings.tool("blender")
MIN_BLENDER_VERSION = (5, 2)
FFMPEG = _settings.tool("ffmpeg")
FFPROBE = _settings.tool("ffprobe")
PYTHON = _settings.tool("python")                 # the project interpreter (.venv), also when launched from Blender
VENV_PY = PYTHON


def blender_cmd(script, *args, blend=None):
    """Headless Blender command line running `script` (path, absolute or relative to the repo root) on `blend`."""
    from codecinema.blender import command
    return command(script, *args, blend=blend, root=ROOT, executable=BLENDER_BIN)


FONT_CALLIGRAPHY = _settings.font("calligraphy")   # running-script calligraphy: title, name cards, act cards
FONT_WEIBEI = _settings.font("weibei")             # heavy display face
FONT_KAITI = _settings.font("kaiti")               # regular script: epigraph, credits
FONT_SONG = _settings.font("song")                 # small print
FONT_UI = _settings.font("ui")                     # diagnostic-sheet labels
FONT_MONO = _settings.font("mono")                 # contact-sheet captions

# ---------------------------------------------------------------- video / render / audio settings
FPS = 24                         # the film is authored at 24 fps (all frame numbers below assume it)
FRAME_START = 1
FRAME_END = 3840                 # 160.0 s
RES_X, RES_Y = int(S["render"]["width"]), int(S["render"]["height"])      # 2.35:1 render, letterboxed in post
DELIVERY_X, DELIVERY_Y = int(S["video"]["delivery_width"]), int(S["video"]["delivery_height"])
PREVIEW_SCALE = float(S["render"]["preview_scale"])
RENDER_SAMPLES = dict(final=int(S["render"]["samples_final"]), preview=int(S["render"]["samples_preview"]))
MOTION_BLUR = bool(S["render"]["motion_blur"])
MB_SHUTTER = float(S["render"]["mb_shutter"])
MB_STEPS = int(S["render"]["mb_steps"])
MB_STEPS_SPARKS = int(S["render"]["mb_steps_sparks"])
MB_MAX = int(S["render"]["mb_max_px"])
RENDER_FILTER = float(S["render"]["filter_size"])
SHADOW_POOL_MB = int(S["render"]["shadow_pool_mb"])
VOLUMETRIC = dict(tile=int(S["render"]["volumetric_tile"]), samples=int(S["render"]["volumetric_samples"]))
FRAME_PNG = dict(depth=str(S["render"]["png_depth"]), compression=int(S["render"]["png_compression"]))
GRASS_DENSITY = dict(layout=float(S["render"]["grass_density_layout"]),
                     preview=float(S["render"]["grass_density_preview"]),
                     final=float(S["render"]["grass_density_final"]))
RENDER_SLOTS = int(S["render"]["slots"])
RENDER_MIN_FREE_MEM_GB = float(S["render"]["min_free_mem_gb"])
RENDER_EXPECTED_SPF = float(S["render"]["expected_seconds_per_frame"])
RENDER_RETRIES = int(S["render"]["retries"])
RENDER_LOCK = bool(S["render"]["lock"])
RENDER_WATCHDOG_FACTOR = float(S["render"]["watchdog_factor"])
RENDER_WATCHDOG_GRACE_S = float(S["render"]["watchdog_grace_s"])
RENDER_PROGRESS_S = float(S["render"]["progress_interval_s"])
RENDER_TMP_MAX_AGE = float(S["render"]["tmp_max_age_s"])
VIDEO = dict(S["video"])
AUDIO_SR = int(S["audio"]["sample_rate"])
AUDIO_TARGET_LUFS = float(S["audio"]["target_lufs"])
AUDIO_TRUE_PEAK_DB = float(S["audio"]["true_peak_db"])
AUDIO_LOUDNESS_TOL_LU = float(S["audio"]["loudness_tolerance_lu"])
AUDIO_AAC_PRE_LIMITER_DB = float(S["audio"]["aac_pre_limiter_db"])
TITLE_JOBS = int(S["post"]["title_jobs"]) or max(1, min(8, (os.cpu_count() or 4) - 2))
TITLES_LOCK_TIMEOUT_S = float(S["post"]["titles_lock_timeout_s"])
DEV_DEMO_RAISE = bool(S["dev"]["demo_raise"])

# film identity (container metadata, slates)
FILM_TITLE = "芒原决战"
FILM_TITLE_EN = "Duel in the Silver Grass"
FILM_COMMENT = "Original homage short - procedural Blender + original score"

def f2s(frame):
    """frame number (1-based) -> seconds from film start"""
    return (frame - FRAME_START) / FPS

def s2f(sec):
    return int(round(sec * FPS)) + FRAME_START

# ---------------------------------------------------------------- world anchors (Z-up, metres)
# Rig facing convention: rig.rotation_euler.z = 0  -> character faces -Y.
ARENA_CENTER = (0.0, 0.0)
PINE_POS = (6.0, 30.0)            # lone pine on a low rise (ground ~2.5 m high there)
# (no planted spear: the saint carries his yari slung on his back until S14)
SAINT_START = (0.0, 4.0)          # faces -Y
SHINOBI_WALK_FROM = (0.0, -20.0)  # walks in during S02-S03
SHINOBI_START = (0.0, -4.5)       # faces +Y (rotation z = 180 deg)
SHINOBI_HEIGHT = 1.72
SAINT_HEIGHT = 1.85
WIND_DIR_DEFAULT = 205.0          # prevailing wind heading (deg)
CAMERA_CLIP = (0.05, 2000.0)      # camera near / far clip (m); terrain and mountains are sized to the far clip
GRASS_CAMERA_CLEAR = (1.5, 4.0)   # grass cleared around the camera: full-clear radius, fade-out radius (m)

# ---------------------------------------------------------------- acts / environment states
# env states: 'dusk_gold' | 'crimson_fire' | 'storm_night' | 'moon_clear'
ACTS = _story["acts"]

# ---------------------------------------------------------------- shot list (every boundary is a hard cut)
# lane = which choreography module owns the shot (codecinema/productions/silvergrass/blender/acts/<lane>.py).
# Each lane splits its shots into SUB-CUTS (e.g. "S12a", "S12b" ...) — staging is defined in codecinema/productions/silvergrass/blender/acts/.
SHOTS = _story["shots"]

LANES = _story["lanes"]

def shots_for_lane(lane):
    return [s for s in SHOTS if s["lane"] == lane]

def lane_ranges(lane):
    return [(s["start"], s["end"]) for s in shots_for_lane(lane)]

def lane_span(lane):
    r = lane_ranges(lane)
    return (min(a for a, _ in r), max(b for _, b in r))

def shot_at(frame):
    for s in SHOTS:
        if s["start"] <= frame <= s["end"]:
            return s
    return None

# Handoff states at lane boundaries (positions are rig origins at ground; facing: 0 -> -Y, 180 -> +Y)
# spear states: 'slung' (on his back, in its sheath) | 'in_hand' | 'world' (flying/lying) | 'gone'
HANDOFF = {
    432:  dict(shinobi=dict(pos=(0.0, -4.5), facing=180, katana="sheathed"),
               saint=dict(pos=(0.0, 4.0), facing=0, katana="sheathed", hat=True, haori=True, spear="slung")),
    936:  dict(shinobi=dict(pos=(0.3, -1.8), facing=180, katana="drawn"),
               saint=dict(pos=(0.0, 2.6), facing=0, katana="drawn", hat=True, haori=True, spear="slung")),
    1632: dict(shinobi=dict(pos=(0.0, -1.5), facing=180, katana="drawn"),
               saint=dict(pos=(0.0, 6.5), facing=0, katana="sheathed", hat=False, haori=False, tasuki=True, spear="in_hand")),
    2496: dict(shinobi=dict(pos=(0.0, -3.0), facing=180, katana="drawn"),
               saint=dict(pos=(0.0, 3.0), facing=0, katana="drawn", pose="jodan", hat=False, haori=False, tasuki=True, spear="gone")),
    3072: dict(shinobi=dict(pos=(0.0, -6.0), facing=180, katana="drawn", pose="kneel_sword_planted"),
               saint=dict(pos=(0.0, 2.5), facing=0, katana="drawn", hat=False, haori=False, tasuki=True, spear="gone")),
}

# ---------------------------------------------------------------- staging rules
# 180-degree rule: from S05 until the S25 pass the camera stays on the +X side of the Y-axis line:
# shinobi (at -Y) is SCREEN-LEFT facing right, elder (at +Y) SCREEN-RIGHT facing left. The S25 pass swaps them
# through action; keep the same physical camera side afterwards (shinobi screen-right).
SCREEN_DIRECTION = dict(camera_side="+X", swap_frame=3271, first_frame=433)
# Slow-motion budget (only these): S07 ramp, S13 deflect, a short S19 speed-ramp, the S25-S26 climax.
# Effects clock (codecinema/productions/silvergrass/blender/fxclock.py): scene["fx_time"] advances at speed/FPS per frame. Every procedural,
# time-driven effect (grass wind, particles, rain, fire, embers, trail reveal, springs) reads fx_time, so these
# slow-motion windows slow the effects too. (f0, f1, speed) — speed 1.0 elsewhere.
TIME_WARP = [(595, 630, 0.25), (1367, 1408, 0.2), (2280, 2304, 0.4), (3269, 3456, 0.125)]
SLOWMO = [(a, b) for a, b, _ in TIME_WARP]


def slowmo_window(frame):
    """The (f0, f1) slow-motion window containing `frame`, or None."""
    return next(((a, b) for a, b in SLOWMO if a <= frame <= b), None)


def env_at(frame):
    """Environment state name of the act that contains `frame`."""
    return next(a["env"] for a in ACTS if a["start"] <= frame <= a["end"])
# Photosensitivity: only FULL_WHITE frames may exceed ~90% full-frame white; other flashes <= 70% and <= 2 per second
# (>= 12 f apart); S13 exposure lift <= 40% for 2 f; S15 fire ramps over >= 6 f.
FULL_WHITE = (3265, 3268)
# Per-shot final-render overrides (applied per frame by render_frames): samples, mb_steps, raytrace, vol_end, ...
SHOT_RENDER = {
    "S07": dict(mb_steps=3),     # first clash hero frames
    "S13": dict(mb_steps=2),
    "S25": dict(mb_steps=3),     # the pass
}
FADE_TO_BLACK = (3770, 3811)             # S29: the picture fades to black; black from the last frame on
RENDER_SKIP = [(SHOTS[0]["start"], SHOTS[0]["end"]), (FADE_TO_BLACK[1], FRAME_END)]   # black frames made in post
FLASH_MIN_GAP = 12
PHOTOSENSITIVITY = dict(full_white_max=0.90, flash_max=0.70, flashes_per_s=2, flash_min_gap=FLASH_MIN_GAP,
                        deflect_lift_max=0.40, deflect_lift_frames=2, fire_ramp_min_frames=6)
QC_BLACKDETECT = dict(black_min_s=0.5, black_pix_th=0.04, black_pic_th=0.995)


def letterbox(width=None, height=None):
    """(picture_height, top_offset) of the render aspect letterboxed into width x height (even rounding)."""
    width, height = width or DELIVERY_X, height or DELIVERY_Y
    ph = int(round(width * RES_Y / RES_X / 2.0)) * 2
    return ph, (height - ph) // 2

# ---------------------------------------------------------------- post: title overlays (frames inclusive)
TITLES = [
    dict(id="epigraph",     start=13,   end=90,   text="剑者，以一生赴一瞬。", sub="天正某年 秋 · 芒原",    style="epigraph"),
    dict(id="main_title",   start=140,  end=236,  text="芒原决战",           sub="",                    style="main"),
    dict(id="name_shinobi", start=288,  end=334,  text="朔",               sub="无主之忍",             style="name"),
    dict(id="name_saint",   start=380,  end=430,  text="天鼓斋",            sub="天鼓流 开祖",          style="name"),
    dict(id="act1",         start=445,  end=528,  text="一之幕",            sub="剑",                  style="act"),
    dict(id="act2",         start=1665, end=1726, text="二之幕",            sub="焰",                  style="act"),
    dict(id="act3",         start=2521, end=2588, text="三之幕",            sub="雷",                  style="act"),
    dict(id="end",          start=3758, end=3840, text="终",               sub="原创动画短片 · 以 Blender 程序化生成 · 配乐原创", style="end"),
]

# ---------------------------------------------------------------- music: cue points + tempo map (frames)
# Real frames for tagged events come from out/events.json when present (music_cue events / tags override these).
MUSIC_CUES = {
    "prologue_start": 1,
    "title": 179,            # the seal stamp of the main title (main_title.start + 39)
    "act1_start": 433,
    "first_clash": 595,      # the clang; the music drops in at act1_bar1
    "act1_bar1": 631,        # bar 1 of the 92-BPM act-I grid (S07 slow-motion release)
    "perfect_deflect": 1367, # drums drop out through the slow motion ...
    "hat_cut": 1420,         # ... and come back with the taiko here
    "act2_start": 1633,      # spear-butt slam = fire_ignite = downbeat
    "thunder_first": 2353,
    "rain_start": 2401,
    "act3_start": 2497,      # = the Raikiri cut
    "raikiri": 2497,
    "low_point": 2950,
    "silence": 3073,         # HARD stop of all music on the S23/S24 cut (ambience only)
    "white_silence": 3265,   # every stem, rain included, to digital silence 3265-3276
    "blade_ring": 3277,
    "final_pass": 3300,      # the flash's thunder arriving late = the huge hit + long tail; rain returns low-passed
    "epilogue": 3505,        # with the moonlight
    "end_card": 3758,
}
# Story beats checked by the build QA: (name, frame, tolerance[, count]); name matches an event
# type, a tag or a music_cue's cue; at least `count` matching events must lie within frame +- tolerance.
STORY_BEATS = [
    ("tsuba_click", 566, 3), ("first_clash", MUSIC_CUES["first_clash"], 3),
    ("perfect_deflect", MUSIC_CUES["perfect_deflect"], 12), ("hat_cut", MUSIC_CUES["hat_cut"], 6),
    ("haori_shed", 1540, 50), ("spear_draw", 1584, 14), ("sheath_drop", 1600, 32),
    ("fire_ignite", MUSIC_CUES["act2_start"], 2), ("kunai_deflect", 1951, 12, 3), ("kick", 2160, 96),
    ("thunder_first", MUSIC_CUES["thunder_first"], 14), ("rain_start", MUSIC_CUES["rain_start"], 2),
    ("raikiri", MUSIC_CUES["raikiri"], 2), ("tree_split", 2510, 20),
    ("lightning_strike", 2688, 95), ("thunder", 2688, 95),     # S22 strobe flashes
    ("low_point", MUSIC_CUES["low_point"], 30), ("sheathe", 3150, 3), ("tsuba_click", 3150, 3),
    ("final_pass", MUSIC_CUES["final_pass"], 3), ("sheathe", 3412, 8), ("tsuba_click", 3412, 8),
    ("sword_break", 3412, 8), ("cord_cut", 3414, 4), ("rain_stop", 3480, 40), ("bell", MUSIC_CUES["end_card"], 3),
]
LANE_KEY_TOLERANCE = 6.0         # keys / events may lie this many frames outside their lane's span
TEMPO_MAP = [
    dict(section="act1", bpm=92,  anchor=631,  start=631,  end=1632),   # 64 beats from 631 lands on 1633
    dict(section="act2", bpm=120, anchor=1633, start=1633, end=2496),   # exactly 12 f per beat, 18 bars
    dict(section="act3", bpm=140, anchor=2497, start=2497, end=3072),   # 14 bars to the silence at 3073
]

def beat_frame(section, beat):
    """frame of the given beat (0 = anchor) in a TEMPO_MAP section, rounded to the nearest frame"""
    t = next(t for t in TEMPO_MAP if t["section"] == section)
    return int(round(t["anchor"] + beat * FPS * 60.0 / t["bpm"]))

# ---------------------------------------------------------------- palette (linear-ish sRGB tuples 0..1)
PALETTE = dict(
    shinobi_cloth=(0.035, 0.037, 0.045), shinobi_under=(0.05, 0.07, 0.13), shinobi_hakama=(0.11, 0.115, 0.13),
    shinobi_red=(0.45, 0.03, 0.03),
    saint_kimono=(0.20, 0.07, 0.03),   # persimmon-brown kakishibu (linear)
    saint_haori=(0.42, 0.28, 0.07),    # ochre; back crest = the 'moon over silver grass' roundel, off-white
    saint_hakama=(0.12, 0.12, 0.12),   # ash grey (nibi-iro)
    saint_beard=(0.55, 0.55, 0.52), saint_skin=(0.45, 0.28, 0.2), beard_cord=(0.6, 0.08, 0.03),
    tasuki=(0.8, 0.8, 0.78), lacquer_black=(0.015, 0.015, 0.015),
    straw=(0.55, 0.42, 0.22), spear_shaft=(0.35, 0.03, 0.02),
    steel=(0.8, 0.8, 0.82), gold=(0.8, 0.55, 0.15),
    grass_dusk=(0.75, 0.6, 0.35), plume=(0.95, 0.9, 0.8),
    spark=(1.0, 0.65, 0.2), electric=(0.55, 0.75, 1.0), fire=(1.0, 0.35, 0.05), blood=(0.5, 0.0, 0.01),
)


# ---------------------------------------------------------------- ORIGINAL leitmotifs (the score may only use these,
# plus their inversions / augmentations / fragments / sequences). Written for this film; do not replace with
# anything transcribed or "in the style of" an existing soundtrack.
# Scales as semitone offsets from the tonic. Notes: (scale_degree_index, octave_offset, beats).
TONIC_MIDI = 62                          # D4
SCALE_IN = [0, 1, 5, 7, 8]               # miyako-bushi / in-sen on D: D Eb G A Bb
SCALE_YO = [0, 2, 5, 7, 9]               # yo scale on D (epilogue resolution): D E G A B
LEITMOTIFS = {
    # Tenko — grave, dignified; shakuhachi / low strings; the Eb->D half-step sigh is its signature
    "tenko": dict(scale="in", notes=[(0, 0, 2.0), (4, -1, 1.0), (3, -1, 1.0), (0, 0, 0.5), (1, 0, 1.5), (0, 0, 3.0)]),
    # Saku — nimble koto figure, leaps then darts back down
    "saku":  dict(scale="in", notes=[(0, 1, 0.25), (3, 0, 0.25), (4, 0, 0.5), (0, 1, 0.25), (1, 1, 0.25), (0, 1, 0.25), (3, 0, 0.75)]),
}
