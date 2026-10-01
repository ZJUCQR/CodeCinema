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
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))) if os.path.dirname(os.path.abspath(__file__)) not in sys.path else None
import settings as _settings   # noqa: E402  (machine / taste settings: [settings] in film.toml, env overrides)

S = _settings.SETTINGS

# ---------------------------------------------------------------- paths (all derived from the repo root + settings)
ROOT = _settings.ROOT
SRC = os.path.join(ROOT, "src")
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
    return [BLENDER_BIN, "-b", "--factory-startup", *([blend] if blend else []), "--python-exit-code", "1",
            "--python", os.path.join(ROOT, script), "--", *[str(a) for a in args]]


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
ACTS = [
    dict(id="prologue", name="序",           start=1,    end=432,  env="dusk_gold"),
    dict(id="act1",     name="一之幕 · 剑",   start=433,  end=1632, env="dusk_gold"),     # sun sinks during S14
    dict(id="act2",     name="二之幕 · 焰",   start=1633, end=2496, env="crimson_fire"),  # downpour hits at 2401 (S20)
    dict(id="act3",     name="三之幕 · 雷",   start=2497, end=3456, env="storm_night"),
    dict(id="epilogue", name="终",           start=3457, end=3840, env="moon_clear"),     # storm->moon blend 3470-3550
]

# ---------------------------------------------------------------- shot list (every boundary is a hard cut)
# lane = which choreography module owns the shot (src/blender/acts/<lane>.py).
# Each lane splits its shots into SUB-CUTS (e.g. "S12a", "S12b" ...) — see docs/STAGING.md for per-shot staging.
SHOTS = [
    # --- PROLOGUE -----------------------------------------------------------------
    dict(id="S01", start=1,    end=96,   lane="prologue", desc="Black. Wind rises; a distant blade ring (~40) and a far thunder roll (~70), sound only. Epigraph card (post overlay). Render black."),
    dict(id="S02", start=97,   end=240,  lane="prologue", desc="Extreme wide establishing, sky dominant (horizon ~2/3 down): endless silver-grass sea at golden sunset, wind waves; the elder a tiny silhouette (straw hat, spear slung diagonally on his back) below the title area; lone pine on the rise; the shinobi small in the foreground walking in from the bottom of frame. Slow crane push-in. Main title 140-236."),
    dict(id="S03", start=241,  end=336,  lane="prologue", desc="Knee-height tracking shot behind the shinobi walking through the grass (feet stay below the grass line; the parting grass carries the shot), tilting up to his back, settled by ~286. Name card 朔 288-334."),
    dict(id="S04", start=337,  end=432,  lane="prologue", desc="Medium close-up of the elder, camera slightly toward +X, elder right of centre looking screen-left: the hat brim keeps his eyes in shadow through the whole head lift (done by ~378); the reveal is beard and jaw plus one tiny eye glint at ~392; grey beard (vermilion cord) and ochre haori move in the wind; spear shaft rises diagonally behind his shoulder. Name card 天鼓斋 380-430 (lower-left)."),
    # --- ACT I : BLADE --------------------------------------------------------------
    dict(id="S05", start=433,  end=540,  lane="act1a", desc="Telephoto (135-150 mm) profile two-shot from ~50 m on the +X side, camera ~2 m high so the grass line crosses the figures at the waist; a stylized low sun ~1/3 picture height between them. Shinobi (screen-left) draws into guard; elder (screen-right) sinks into an iai stance, hand on hilt. Act card 一之幕·剑 in the sky band."),
    dict(id="S06", start=541,  end=588,  lane="act1a", desc="ECU of the elder's scabbard mouth only: the sheathed blade slides 3-4 cm out of the saya 560-566, click at 566, a sun glint sweeps the exposed steel 566-575; the hand is an unlit dark mass. Wind drops out 576-588 (held breath)."),
    dict(id="S07", start=589,  end=672,  lane="act1a", desc="Cut in with the elder already mid-dash (the quick-draw you don't see). Contact ~595 = FIRST CLASH (sparks, clang); slow-motion ramp 595-630 on a tight angle of blades and sparks; real time from 631 (music bar 1) with impact shake. The elder fights ONE-HANDED through S12."),
    dict(id="S08", start=673,  end=840,  lane="act1a", desc="Elder's 3-hit combo (diagonal down, rising cut, thrust): the shinobi deflects two (sparks) and sidesteps the thrust. 3-5 sub-cuts; any orbit ends back on the +X side."),
    dict(id="S09", start=841,  end=936,  lane="act1a", desc="Over the ELDER'S LEFT shoulder: the shinobi counters with two quick cuts; the elder parries the first, evades the second by stepping back. Distance resets."),
    dict(id="S10", start=937,  end=1032, lane="act1b", desc="Slow lateral dolly through foreground grass (circling at most 90 deg, dolly follows the rotation): the shinobi drops into the tall grass and vanishes (草隠れ) - only a ripple betrays him; the elder closes his eyes, listening. Heartbeat."),
    dict(id="S11", start=1033, end=1176, lane="act1b", desc="The elder re-sheathes and answers with one draw-cut so fast that it SHEARS THE GRASS TOPS in an expanding arc (a physical cut-line racing outward, silver plumes bursting into drifting fluff - no glowing projectile); this flushes the shinobi out: he leaps above the cut-line and comes down with an overhead strike; the elder blocks overhead - clash burst."),
    dict(id="S12", start=1177, end=1344, lane="act1b", desc="Flurry on the 92-BPM grid: clashes at 1195/1210/1226/1241/1257/1273, cutting 2 f after each (1177-1197, 1198-1212, 1213-1228, 1229-1243, 1244-1259, 1260-1275), alternating over the shinobi's right / the elder's left shoulder plus one blade insert; blade lock 1276-1320 as one backlit profile silhouette; shove on 1320 (hidden by the cut); they skid apart 1321-1344."),
    dict(id="S13", start=1345, end=1488, lane="act1b", desc="The elder's FIRST TWO-HANDED blow, a heavy overhead (~1350); the shinobi's perfect deflect ~1367 (local flash ring, exposure lift <=40% for 2 f), slow motion 1367-1408 on the ring and hanging sparks; real-time counter: his rising cut slices the straw hat in two at 1420 (backlit profile, face in silhouette), revealing the shaven, scarred head; halves tumble away; the elder skids back through the grass."),
    dict(id="S14", start=1489, end=1632, lane="act1b", desc="Low angle, head against the reddening sky, framed waist-up through foreground grass: the elder sheathes his katana, sheds the ochre haori with one sweep (flung aside), revealing the white tasuki; draws the vermilion spear from his back over the shoulder in one arc (~1584, as the sun's last sliver disappears) - the black-lacquer sheath spins off into the grass - and twirls it. Sky turns crimson, first embers drift."),
    # --- ACT II : SPEAR & FIRE ----------------------------------------------------------
    dict(id="S15", start=1633, end=1728, lane="act2", desc="Hard cut on the spear-butt impact at 1633 (downbeat + fire_ignite): a ring of fire erupts outward through the grass (ramping up over >= 6 f), enclosing the arena; the discarded haori catches fire. Top-down -> level. Act card 二之幕·焰 1665-1726."),
    dict(id="S16", start=1729, end=1920, lane="act2", desc="Spear onslaught on the 12-f grid: 1729-1776 low wide, 360-deg sweep over the ducking shinobi at 1753; 1777-1824 lens on the thrust axis, thrusts 1789/1801/1813 (deflect, deflect, the third turned aside by a kunai in his off-hand as he slides along the shaft); 1825-1872 handheld medium reset; 1873-1920 lateral wide, low sweep 1885, the shinobi vaults it, lands 1897."),
    dict(id="S17", start=1921, end=2064, lane="act2", desc="The shinobi throws three kunai; the elder spins the spear, deflecting them at 1945/1951/1957 (sparks); the elder's leaping overhead slam erupts fire and dust; the shinobi rolls clear (perpendicular to the line)."),
    dict(id="S18", start=2065, end=2256, lane="act2", desc="Handheld close quarters: a low sliding cut takes the shinobi under the spear and inside its reach; sword vs shaft clashes; the elder's kick (contact hidden by a cut) sends the shinobi skidding back screen-left, sword dragged in the dirt to stop."),
    dict(id="S19", start=2257, end=2400, lane="act2", desc="The elder hurls the spear like a javelin (~2270); the shinobi deflects it (~2282, short speed-ramp 2280-2304); it spins away into the flames (~2330); first thunder ~2353; the elder draws his katana again 2370-2400 as the first raindrops sizzle on the blade."),
    dict(id="S20", start=2401, end=2496, lane="act2", desc="High wide: the downpour hits on the cut (rain_start 2401), the fire ring collapses into steam; lightning inside the clouds; the elder takes jodan (上段, katana high in both hands) 2460-2496 facing the storm - a stance, not a summoning."),
    # --- ACT III : THUNDER -------------------------------------------------------------
    dict(id="S21", start=2497, end=2592, lane="act3", desc="雷切 (Raikiri legend): open on an extreme wide (tiny figures, a bolt spanning the frame) - the bolt comes down on the elder at 2497 and he CUTS it; the bolt forks aside and one branch splits the lone pine (flash <=2 f at <=70%, blue-tinted; flame, then steam in the rain); cut to a low-angle medium close-up of the blade with only a few frames of afterglow. He never channels or throws lightning. Act card 三之幕·雷 2521-2588."),
    dict(id="S22", start=2593, end=2784, lane="act3", desc="Strobe flurry, the elder presses: lit almost only by lightning flashes >= 12 f apart (<= 2 per second) - each flash reveals a new tableau (clash, near-miss, deflect), near-darkness between; sparks; bolts strike the field (environmental only). Extreme wides against extreme close-ups."),
    dict(id="S22b", start=2785, end=2880, lane="act3", desc="The shinobi's counter-attack, the only time he presses in Act III: three strikes (his trails cool white with a red core vs the elder's cold steel-blue) drive the elder back a step; ends with the elder gathering himself into jodan for S23."),
    dict(id="S23", start=2881, end=3072, lane="act3", desc="The LOW POINT: the elder's grounded full-power jodan cut (~2950, on a bar line) splits the curtain of rain (a vertical parting); the spray-ring shockwave throws the shinobi screen-left; he tumbles and ends on one knee, sword planted in the mud, head bowed (~3000). The elder takes two unhurried steps (3010-3040). Hold to 3072. Real time, no glow."),
    # --- FINALE (climax + epilogue) ---------------------------------------------------
    dict(id="S24", start=3073, end=3264, lane="finale", desc="Mirrored-iai stand-off in the rain; ALL music hard-stops at 3073. 24a 3073-3120 telephoto profile on the S05 axis and lens, the shinobi rises 3085-3115; 24b 3121-3156 ECU of the shinobi's scabbard mouth (mirror of S06): he sheathes, click at 3150 over rain alone; 24c 3157-3196 low-angle profile, the elder lifts into jodan, rain bouncing off the steel; 24d 3197-3232 the shinobi sinks into the elder's own quick-draw stance from S05, tails hang, no wind; 24e 3233-3264 ECU of a drop gathering at the tip of the soaked headband tail - it falls at 3250, hits a puddle at 3256; both launch 3257-3264. No lightning in S24."),
    dict(id="S25", start=3265, end=3360, lane="finale", desc="3265-3268: the ONLY full-white frames of the film (the lightning). 3269-3276: pure black silhouettes on white cross in two frames (the shinobi's iai draw-cut), standing back to back from 3271. The storm image returns by ~3300 while they hold; rain at ~1/8 speed, grass frozen (wind 0). Sound: silence 3265-3276, a thin blade ring 3277, thunderclap 3300."),
    dict(id="S26", start=3361, end=3456, lane="finale", desc="The shinobi, in the foreground with his back to the elder, slowly sheathes; the guard clicks home at ~3412 and on that exact frame the elder's blade snaps (the third click of the S06/S24/S26 motif); the cut vermilion beard cord flutters away with a thin line of red mist at 3414 (slow motion); the broken tip plants in the earth ~3440."),
    dict(id="S27", start=3457, end=3600, lane="finale", desc="One composed deep two-shot from the +X side: the elder kneeling in the foreground screen-left (knee lands 3470, broken blade planted 3476 - echo of S23), the shinobi in the background screen-right. Rain thins 3470-3500; storm_night -> moon_clear 3470-3550, the edge of moonlight sweeping from background to foreground 3505-3550; the shinobi turns 3552-3568 and bows 3570-3600."),
    dict(id="S28", start=3601, end=3744, lane="finale", desc="Crane up while the shinobi walks away screen-right into depth (~7 m), the grass closing behind him (bookend to S03); the elder stays the still point; the wind returns, silver grass waves under the moon."),
    dict(id="S29", start=3745, end=3840, lane="finale", desc="A quiet still life: the broken blade tip standing in moonlit grass; bell and 终 at 3758; the picture fades to black ~3770-3810."),
]

LANES = ["prologue", "act1a", "act1b", "act2", "act3", "finale"]

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

# ---------------------------------------------------------------- staging rules (see docs/STAGING.md)
# 180-degree rule: from S05 until the S25 pass the camera stays on the +X side of the Y-axis line:
# shinobi (at -Y) is SCREEN-LEFT facing right, elder (at +Y) SCREEN-RIGHT facing left. The S25 pass swaps them
# through action; keep the same physical camera side afterwards (shinobi screen-right).
SCREEN_DIRECTION = dict(camera_side="+X", swap_frame=3271, first_frame=433)
# Slow-motion budget (only these): S07 ramp, S13 deflect, a short S19 speed-ramp, the S25-S26 climax.
# Effects clock (src/blender/fxclock.py): scene["fx_time"] advances at speed/FPS per frame. Every procedural,
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
# Story beats checked by the build QA (docs/STAGING.md §8): (name, frame, tolerance[, count]); name matches an event
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
