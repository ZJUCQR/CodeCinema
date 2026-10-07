"""
environment.py - the world of Duel in the Silver Grass: terrain, silver-grass sea, lone pine, far mountains + pagoda, sky, the four
light states, wind, grass effects, lightning illumination (Blender 5.2.2, EEVEE). Owner: env lane.

Flash limits are defined in config and enforced by flash().
Look-dev renders + harnesses: out/dev/env/ (lookdev.py, bench.py,
windstrip.py; sheet_look.png = the current look-dev contact sheet).

Public API (see each docstring)
    build(scene=None, density=1.0, with_grass=True) -> dict            # everything below needs build() first
    set_state(frame, state, blend_frames=0)                              # dusk_gold | crimson_fire | storm_night | moon_clear
    set_sun(frame, azimuth_deg, elevation_deg, disk_deg=None, interp='CONSTANT')   # per-shot cheat (sun or moon)
    set_param(frame, name, value, interp='CONSTANT')                     # per-shot tweak of one state parameter (PARAMS)
    set_wind(frame, strength, direction_deg=None, interp='LINEAR')
    set_burn(frame, amount, interp='LINEAR') ; set_wetness(frame, amount, interp='LINEAR')
    flash(frame, strength=1.0, duration=3, tint=None, direction=None) -> applied strength (budget-checked)
    flash_direction(frame, evaluated=False) -> (az, el)                  # default bolt light: low, behind the fighters
    grass_effect(kind, params, f0, f1=None)                              # 'shear' | 'burn' | 'wet' | 'freeze'
    set_camera_clearance(frame, near=None, far=None, cone_deg=None, cone_len=None, interp='CONSTANT')
    set_cloud_shadow(frame, cover=None, edge=None, edge_dir_deg=None, edge_width=None, interp='LINEAR')
    set_grass_density(value)                                             # preview x0.25 (render_setup calls it)
    bind_characters() -> int                                             # grass parting -> SHINOBI_rig / SAINT_rig
    key_lane_defaults(lane_or_span)                                      # default env timeline inside a lane span
    finalize(scene=None, wake=True) -> dict                              # POST-ASSEMBLY pass: bake_wake + aim_flashes
    bake_wake(f0=None, f1=None, step=1, lags=None) ; aim_flashes(scene=None)
    ridge_elevation(az_deg, sun_az_deg=None, sun_el_deg=0.0, eye=(0, 0, 2)) -> deg   # skyline incl. the sunset gap
    wind_at(frame) -> (strength, (dx, dy)) ; default_state_at(frame) ; default_timeline() ; flash_log()
    terrain_height(x, y) ; grass_mask(x, y) ; expected_instances(density)
Objects: ENV_terrain, ENV_grass (GN_ENV_grass), ENV_pine + ENV_pine_half_A/B (hidden), ENV_rock_*, ENV_mtn_0..3
    (GN_ENV_ridge), ENV_pagoda, ENV_fog, ENV_sun_pivot > ENV_key, ENV_fill, ENV_bounce, ENV_flash, ENV_shadow_edge,
    ENV_cloud_deck, ENV_wake_SHINOBI_1/2 + ENV_wake_SAINT_1/2 (parked until bake_wake), ENV_shear_fluff_<slot>;
    world ENV_world; collections ENV, ENV_grass_clumps / ENV_fluff_parts (excluded instance sources).

Pipeline hooks (build_scene): env.build -> characters.build -> bind_characters() -> per lane: begin_lane ->
    key_lane_defaults(lane) -> lane.build -> end_lane -> assemble_nla -> env.finalize() (wake + flash aim; needs the
    final rig motion and marker cameras) -> secondary motion (wind_at, memoised) -> ... -> render_setup.configure.

Design (why)
  * STATE = a vector of named parameters (STATES table). set_state keys ALL of them at once (a complete snapshot, so a
    lane's NLA strip always carries a full state): world custom props "env_<name>" (read by every shader through
    Attribute nodes of type VIEW_LAYER - verified to update per frame in EEVEE) + light datablocks (energy/colour).
    Blends are plain F-curve interpolation between two snapshots.
  * NLA (Pipeline rule 1): env keys made inside a lane go to that lane's strips and HOLD FORWARD past the lane's span
    until a later lane keys the same channel. build() keys the whole default timeline (config-derived) before the
    lanes (-> BASE track). key_lane_defaults(lane) gives every lane strip a complete env timeline and re-keys the
    default sun + camera clearance at every shot start (a forgotten per-shot cheat never leaks past a cut).
    The default key-light direction only changes on cuts (storm key at the S19->S20 cut, moon at S26->S27); the S14
    sunset is the one intended in-shot move.
  * SKY: gradient + wide glow + tight lobes around the disk (a radial gradient even at 135 mm) + a limb-darkened
    sun / flat moon disk + halo; streaky clouds; storm billows (cloud_billow) whose undersides light up around the
    flash azimuth. The far ranges carry a SUN-FOLLOWING sunset gap (GN_ENV_ridge reads ENV_sun_pivot): any set_sun
    cheat with a low disk gets a clear horizon (ridge_elevation() answers "how low may the disk go").
  * GRASS: ~253k fixed instances (arena r < 25 m at 60 / m2, S05-axis foreground patch, thinning far field over the
    textured ground), 3 clump designs x 4 LODs picked by jittered projected distance (area-matched LODs: no bands;
    the telephoto boost is capped at LOD_FOCAL_MAX mm; clumps outside the active camera's padded frustum take LOD3 -
    they only cast shadows into the frame), feather-fan plumes above V-folded leaves. Wind = rigid base lean from
    travelling gust bands + a lagged bend and a per-clump flutter applied as a world-space SHEAR of each instance
    about its base (2-level hierarchy, all in GN: no shader displacement - perf, see _grass_material).
    Shading = ONE diffuse closure with wrap lighting (the shading normal leans toward the key light; fades when
    looking into it) + emissive fakes: backlit plume rims, leaf translucency, grazing sheen, gust brightness, embers.
  * TIME (rule 4): wind, gusts, flutter, shear, burn ramps, fluff and cloud drift read fx_time (fxclock); grass
    effects are static GN inputs gated on fx_time (NLA-immune). The freeze window stops the wind clock exactly (grass
    and the far-field ground sheen).
  * POOLS (rules 3, 8): grass instance count is fixed (static distribution); clearance, cut, burn and preview
    density never delete points - they scale instances to 0 or switch the instance variant. The shear fluff pool and
    the severed-tops pool (tops thrown up at their cut time, then lying on the stubble as litter) are fixed too.
  * SHADOWS (rule 5): only ENV_key (sun/moon) and ENV_flash cast shadows (+ vfx fire lights in Act II);
    fog / fluff / the grass host: visible_shadow=False. The grass CLUMPS do cast (instances take the ray visibility
    of their source objects): their self-shadowing is part of the look; kept cheap by the GN shear + frustum LOD.
  * FOG (rule 6): mesh box + Principled Volume (never a world volume); far haze is baked into materials (aerial
    perspective node group) so mountains and the far field fade into the sky of the current state.
  * FLASH (DIRECTION §5): outside config.FULL_WHITE strength is clamped to FLASH_MAX (<=70 % frame luminance,
    calibrated) and flashes closer than config.FLASH_MIN_GAP frames to an earlier one are refused; all logged. The
    flash light is low and behind the fighters (rim / silhouette), the ambient lift small (dark shadows survive).
"""
import math
import os
import sys
import zlib

import bpy
import bmesh
import numpy as np
from mathutils import Vector

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(_HERE, "..", "common"), _HERE):
    _p = os.path.abspath(_p)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config            # noqa: E402
import bl_util as U      # noqa: E402

FPS = float(config.FPS)
COLL = "ENV"

# ------------------------------------------------------------------------------------------------ object names
N_TERRAIN = "ENV_terrain"
N_GRASS = "ENV_grass"
N_PINE = "ENV_pine"
N_PINE_A = "ENV_pine_half_A"
N_PINE_B = "ENV_pine_half_B"
N_FOG = "ENV_fog"
N_KEY = "ENV_key"            # sun / moon lamp (shadows)
N_FILL = "ENV_fill"          # sky fill (no shadows)
N_BOUNCE = "ENV_bounce"      # glow from below (no shadows)
N_FLASH = "ENV_flash"        # lightning lamp (shadows)
N_PIVOT = "ENV_sun_pivot"    # carries ENV_key
N_GOBO = "ENV_shadow_edge"   # moving light-edge shadow deck (S27 sweep; invisible to camera)
N_CLOUDS = "ENV_cloud_deck"  # drifting cloud-shadow blobs (invisible to camera)
N_PAGODA = "ENV_pagoda"
WORLD_NAME = "ENV_world"

# ------------------------------------------------------------------------------------------------ layout (metres)
ARENA_R = 15.0               # exactly flat z=0 inside (rule 8)
NEAR_R = 25.0                # dense near patch
MID_R = 70.0
FAR_R = 200.0                # last grass instances; textured ground beyond
TERRAIN_R = 1840.0           # < 0.93 x FAR_CLIP_REF (config.CAMERA_CLIP far = 2000 m), behind the 1800 m range
PINE_RISE = 2.5              # ground height at config.PINE_POS
GUST_SPEED = 5.5             # m/s travelling gust waves
DEFAULT_WIND_DIR = config.WIND_DIR_DEFAULT   # heading the wind blows TOWARD, compass deg (0=+Y, 90=+X)

# ------------------------------------------------------------------------------------------------ light states
STATE_NAMES = ("dusk_gold", "crimson_fire", "storm_night", "moon_clear")

# Parameter table. kind 'C' = colour (linear RGB), 'F' = float.  target 'W' = world prop env_<name> (shaders),
# ('L', lamp, attr) = light datablock attribute.
PARAMS = [
    # sky gradient + atmosphere
    ("sky_zen", 'C', 'W'), ("sky_mid", 'C', 'W'), ("sky_hor", 'C', 'W'), ("sky_str", 'F', 'W'),
    ("glow_col", 'C', 'W'), ("glow_str", 'F', 'W'), ("glow_wide", 'F', 'W'),
    # sun / moon disk (position from set_sun)
    ("disk_col", 'C', 'W'), ("disk_str", 'F', 'W'), ("disk_vis", 'F', 'W'), ("disk_moon", 'F', 'W'),
    # clouds
    ("cloud_cover", 'F', 'W'), ("cloud_lit", 'C', 'W'), ("cloud_dark", 'C', 'W'), ("cloud_streak", 'F', 'W'),
    ("cloud_alpha", 'F', 'W'), ("star_str", 'F', 'W'), ("cloud_billow", 'F', 'W'),
    # world lighting (ambient seen by surfaces, independent of the visible sky)
    ("amb_col", 'C', 'W'), ("amb_str", 'F', 'W'),
    # aerial perspective (far haze in materials)
    ("haze_dist", 'F', 'W'), ("haze_max", 'F', 'W'),
    # fog box (Principled Volume)
    ("fog_den", 'F', 'W'), ("fog_col", 'C', 'W'), ("fog_aniso", 'F', 'W'), ("fog_height", 'F', 'W'),
    ("fog_noise", 'F', 'W'), ("fog_emit", 'C', 'W'),
    # surfaces
    ("grass_leaf", 'C', 'W'), ("grass_plume", 'C', 'W'), ("grass_trans", 'F', 'W'), ("grass_sheen", 'F', 'W'),
    ("grass_silk", 'F', 'W'), ("grass_wrap", 'F', 'W'),
    ("ground_near", 'C', 'W'), ("ground_far", 'C', 'W'), ("mtn_near", 'C', 'W'), ("mtn_far", 'C', 'W'),
    ("mtn_glow", 'F', 'W'), ("gobo_cover", 'F', 'W'),
    # lamps
    ("key_col", 'C', ('L', N_KEY, 'color')), ("key_pow", 'F', ('L', N_KEY, 'energy')),
    ("fill_col", 'C', ('L', N_FILL, 'color')), ("fill_pow", 'F', ('L', N_FILL, 'energy')),
    ("bounce_col", 'C', ('L', N_BOUNCE, 'color')), ("bounce_pow", 'F', ('L', N_BOUNCE, 'energy')),
]
PARAM_KIND = {n: k for n, k, _ in PARAMS}
PARAM_TARGET = {n: t for n, _, t in PARAMS}

STATES = {
    "dusk_gold": dict(
        sky_zen=(0.010, 0.018, 0.075), sky_mid=(0.18, 0.052, 0.034), sky_hor=(0.22, 0.045, 0.006), sky_str=1.0,
        glow_col=(1.0, 0.30, 0.04), glow_str=0.34, glow_wide=1.0,
        disk_col=(1.0, 0.46, 0.10), disk_str=5.0, disk_vis=1.0, disk_moon=0.0,
        cloud_cover=0.38, cloud_lit=(1.0, 0.33, 0.07), cloud_dark=(0.048, 0.026, 0.050), cloud_streak=4.5,
        cloud_alpha=0.85, star_str=0.0,
        amb_col=(0.45, 0.32, 0.42), amb_str=0.12,
        haze_dist=750.0, haze_max=0.90,
        fog_den=0.0007, fog_col=(1.0, 0.72, 0.48), fog_aniso=0.45, fog_height=9.0, fog_noise=0.25,
        fog_emit=(0.0, 0.0, 0.0),
        grass_leaf=(0.15, 0.085, 0.025), grass_plume=(0.82, 0.62, 0.42), grass_trans=0.30, grass_sheen=0.55,
        grass_silk=0.5, grass_wrap=1.0, cloud_billow=0.0,
        ground_near=(0.10, 0.065, 0.028), ground_far=(0.26, 0.17, 0.075),
        mtn_near=(0.045, 0.020, 0.022), mtn_far=(0.34, 0.13, 0.07), mtn_glow=0.8, gobo_cover=0.30,
        key_col=(1.0, 0.62, 0.32), key_pow=4.0, fill_col=(0.50, 0.42, 0.62), fill_pow=0.03,
        bounce_col=(1.0, 0.55, 0.25), bounce_pow=0.03),
    "crimson_fire": dict(
        sky_zen=(0.020, 0.012, 0.030), sky_mid=(0.30, 0.035, 0.035), sky_hor=(1.0, 0.13, 0.035), sky_str=1.0,
        glow_col=(1.0, 0.16, 0.04), glow_str=1.6, glow_wide=1.4,
        disk_col=(1.0, 0.25, 0.06), disk_str=3.0, disk_vis=0.0, disk_moon=0.0,
        cloud_cover=0.55, cloud_lit=(0.95, 0.14, 0.05), cloud_dark=(0.05, 0.015, 0.02), cloud_streak=5.0,
        cloud_alpha=0.9, star_str=0.0,
        amb_col=(0.40, 0.08, 0.06), amb_str=0.30,
        haze_dist=300.0, haze_max=0.95,
        fog_den=0.0040, fog_col=(0.75, 0.35, 0.28), fog_aniso=0.35, fog_height=12.0, fog_noise=0.55,
        fog_emit=(0.0, 0.0, 0.0),
        grass_leaf=(0.22, 0.12, 0.07), grass_plume=(0.85, 0.52, 0.38), grass_trans=0.45, grass_sheen=0.35,
        grass_silk=0.7, grass_wrap=1.0, cloud_billow=0.25,
        ground_near=(0.07, 0.04, 0.03), ground_far=(0.30, 0.10, 0.06),
        mtn_near=(0.04, 0.008, 0.015), mtn_far=(0.40, 0.06, 0.05), mtn_glow=0.8, gobo_cover=0.0,
        key_col=(1.0, 0.24, 0.07), key_pow=1.4, fill_col=(0.25, 0.10, 0.25), fill_pow=0.10,
        bounce_col=(1.0, 0.35, 0.08), bounce_pow=0.55),
    "storm_night": dict(
        sky_zen=(0.006, 0.008, 0.014), sky_mid=(0.020, 0.026, 0.043), sky_hor=(0.080, 0.090, 0.115), sky_str=1.0,
        glow_col=(0.25, 0.30, 0.42), glow_str=0.22, glow_wide=1.8,
        disk_col=(0.7, 0.8, 1.0), disk_str=0.5, disk_vis=0.0, disk_moon=1.0,
        cloud_cover=0.93, cloud_lit=(0.20, 0.24, 0.32), cloud_dark=(0.008, 0.010, 0.016), cloud_streak=2.5,
        cloud_alpha=1.0, star_str=0.0,
        amb_col=(0.06, 0.075, 0.11), amb_str=0.80,
        haze_dist=220.0, haze_max=0.97,
        fog_den=0.0045, fog_col=(0.50, 0.56, 0.66), fog_aniso=0.2, fog_height=14.0, fog_noise=0.45,
        fog_emit=(0.0, 0.0, 0.0),
        grass_leaf=(0.08, 0.09, 0.075), grass_plume=(0.25, 0.26, 0.28), grass_trans=0.25, grass_sheen=0.35,
        grass_silk=0.3, grass_wrap=0.0, cloud_billow=1.0,
        ground_near=(0.05, 0.05, 0.048), ground_far=(0.09, 0.095, 0.10),
        mtn_near=(0.006, 0.008, 0.013), mtn_far=(0.035, 0.045, 0.065), mtn_glow=0.2, gobo_cover=0.0,
        key_col=(0.55, 0.65, 0.90), key_pow=0.60, fill_col=(0.30, 0.36, 0.52), fill_pow=0.12,
        bounce_col=(0.9, 0.45, 0.2), bounce_pow=0.04),
    "moon_clear": dict(
        sky_zen=(0.004, 0.008, 0.028), sky_mid=(0.014, 0.028, 0.075), sky_hor=(0.050, 0.080, 0.16), sky_str=1.0,
        glow_col=(0.35, 0.45, 0.75), glow_str=0.55, glow_wide=0.8,
        disk_col=(0.88, 0.92, 1.0), disk_str=2.5, disk_vis=1.0, disk_moon=1.0,
        cloud_cover=0.14, cloud_lit=(0.30, 0.36, 0.52), cloud_dark=(0.02, 0.03, 0.06), cloud_streak=6.0,
        cloud_alpha=0.6, star_str=1.0,
        amb_col=(0.07, 0.10, 0.20), amb_str=0.26,
        haze_dist=380.0, haze_max=0.93,
        fog_den=0.0018, fog_col=(0.60, 0.70, 0.92), fog_aniso=0.4, fog_height=7.0, fog_noise=0.3,
        fog_emit=(0.0, 0.0, 0.0),
        grass_leaf=(0.05, 0.062, 0.08), grass_plume=(0.42, 0.45, 0.52), grass_trans=0.22, grass_sheen=0.8,
        grass_silk=0.45, grass_wrap=0.5, cloud_billow=0.0,
        ground_near=(0.05, 0.06, 0.08), ground_far=(0.12, 0.15, 0.22),
        mtn_near=(0.006, 0.010, 0.026), mtn_far=(0.05, 0.08, 0.16), mtn_glow=0.6, gobo_cover=0.0,
        key_col=(0.62, 0.74, 1.0), key_pow=2.6, fill_col=(0.20, 0.26, 0.42), fill_pow=0.07,
        bounce_col=(0.3, 0.35, 0.5), bounce_pow=0.0),
}

# Default sun/moon placement per state: (azimuth_deg, elevation_deg, disk_deg). Azimuth is a compass bearing
# (0 = +Y, 90 = +X, 270 = -X). The key light never goes below KEY_MIN_EL even when the disk has set.
SUN_DEFAULT = {
    "dusk_gold": (270.0, 4.0, 2.2),
    "crimson_fire": (270.0, -2.0, 2.2),
    "storm_night": (250.0, 38.0, 2.0),
    "moon_clear": (285.0, 24.0, 3.2),
}
KEY_MIN_EL = 2.5
KEY_VOLUME = 0.35            # key light -> fog scattering (backlit glow without washing the frame)

# Default env timeline derived from config (lanes override per shot; see key_lane_defaults).
def _shot(sid):
    return next(s for s in config.SHOTS if s["id"] == sid)


def default_timeline():
    """[(frame, state, blend_frames)] - the film's env states from config.ACTS / SHOTS / MUSIC_CUES:
    dusk (Act I) -> the sky turns crimson during S14 -> storm from the first thunder to the downpour ->
    moon during S27 (storm->moon blend, config.ACTS comment 3470-3550)."""
    s14 = _shot("S14")
    s27 = _shot("S27")
    tl = [(config.FRAME_START, "dusk_gold", 0)]
    tl.append((s14["start"] + 48, "crimson_fire", s14["end"] - s14["start"] - 48))
    tl.append((config.MUSIC_CUES["thunder_first"], "storm_night",
               config.MUSIC_CUES["rain_start"] - config.MUSIC_CUES["thunder_first"]))
    tl.append((s27["start"] + 13, "moon_clear", 80))
    return tl


def _cut_for_blend(frame, blend):
    """Start frame (a hard cut) of the shot in which a state blend starting at `frame` completes - key-light
    direction changes are placed on cuts, never mid-shot."""
    s = config.shot_at(int(frame + max(blend, 0)))
    return s["start"] if s else int(frame)


def default_sun_timeline():
    """[(frame, az, el, disk, interp)] default sun/moon keys: the sun sinks behind the horizon during S14 (the only
    intended in-shot move); every other direction change sits on the CUT that starts the shot in which its state
    blend completes (storm key at the S19->S20 cut 2401, moon key at the S26->S27 cut 3457), so shadows never jump
    inside a shot."""
    s14 = _shot("S14")
    az, el, dk = SUN_DEFAULT["dusk_gold"]
    out = [(config.FRAME_START, az, el, dk, 'CONSTANT'),
           (s14["start"], az, el, dk, 'LINEAR'),
           (s14["start"] + 96, az, -1.5, dk, 'CONSTANT')]
    for fr, st, bl in default_timeline()[2:]:
        a, e, d = SUN_DEFAULT[st]
        out.append((_cut_for_blend(fr, bl), a, e, d, 'CONSTANT'))
    return out


# ------------------------------------------------------------------------------------------------ flash budget
FLASH_MAX = 1.0              # strength 1.0 is calibrated to stay <= ~70 % frame luminance (look-dev)
FLASH_WHITE_MAX = 4.0        # inside config.FULL_WHITE
FLASH_ENVELOPE = (1.0, 0.42, 0.12, 0.03)
FLASH_KEY_POWER = 6.5       # ENV_flash energy at strength 1 (sun units)
FLASH_TINT = (0.72, 0.82, 1.0)
FLASH_VOLUME = 0.25         # flash lamp -> fog scattering (keeps the rain haze from turning into a white wall)
FLASH_AMB = 0.08            # flash -> world ambient (low: shadows stay dark, silhouettes survive the flash)
FLASH_EL = 22.0             # default flash elevation (deg): a LOW bolt light ...
FLASH_SIDE = 25.0           # ... from behind the subjects (the camera's view bearing + this), i.e. a rim / backlight
FLASH_AZ_FALLBACK = 270.0   # no camera known at that frame: from the -X side (behind the pair for the +X cameras)
DISK_LIMB = 0.6             # sun limb darkening (1 - DISK_LIMB at the rim)
DISK_LIMB_TINT = (1.0, 0.45, 0.22)   # the sun reddens toward its rim
DISK_HALO = 0.35            # tight (~3 deg) halo lobe around the disk (x disk_str)

_LOG = []                    # human-readable log of clamps / refusals (also printed)


def _log(msg):
    _LOG.append(msg)
    print(f"[environment] {msg}")


def _seed(*parts):
    return zlib.crc32(":".join(str(p) for p in parts).encode()) & 0x7FFFFFFF


def _rng(*parts):
    return np.random.default_rng(_seed(*parts))


# ------------------------------------------------------------------------------------------------ helpers
def _scene(scene=None):
    return scene or bpy.context.scene


def _world():
    w = bpy.data.worlds.get(WORLD_NAME)
    if w is None:
        raise RuntimeError("environment.build() has not been called (no ENV_world)")
    return w


def _obj(name):
    return bpy.data.objects.get(name)


def _lamp(name):
    ob = bpy.data.objects.get(name)
    return ob.data if ob is not None else None


def _as_value(kind, v):
    if kind == 'C':
        return [float(v[0]), float(v[1]), float(v[2])]
    return float(v)


def _state_values(state):
    if state not in STATES:
        raise ValueError(f"unknown env state {state!r}; expected one of {STATE_NAMES}")
    return STATES[state]


def _target_of(name):
    """(id_block, data_path) where a parameter is keyed."""
    tgt = PARAM_TARGET[name]
    if tgt == 'W':
        return _world(), f'["env_{name}"]'
    _, lamp, attr = tgt
    return _lamp(lamp), attr


def _fc_value(idb, path, kind, frame):
    """Value of the ACTIVE action's F-curve(s) at frame, or None when that channel has no keys."""
    n = 3 if kind == 'C' else 1
    vals = []
    for i in range(n):
        fc = U.fcurve(idb, path, i)
        if fc is None or len(fc.keyframe_points) == 0:
            return None
        vals.append(fc.evaluate(frame))
    return vals if kind == 'C' else vals[0]


def default_state_at(frame):
    """Name of the default (config-derived) state whose snapshot applies at frame (ignores blends)."""
    cur = STATE_NAMES[0]
    for fr, st, bl in default_timeline():
        if frame >= fr:
            cur = st
    return cur


def _default_value_at(name, frame):
    """Default-timeline value (blends included) of parameter `name` at frame."""
    tl = default_timeline()
    kind = PARAM_KIND[name]
    val = np.asarray(STATES[tl[0][1]][name], dtype=float)
    for fr, st, bl in tl[1:]:
        if frame < fr:
            break
        tgt = np.asarray(STATES[st][name], dtype=float)
        u = 1.0 if bl <= 0 else min(1.0, (frame - fr) / float(bl))
        val = val + (tgt - val) * u
    return _as_value(kind, val.tolist() if kind == 'C' else float(val))


def _current_value(name, frame):
    idb, path = _target_of(name)
    v = _fc_value(idb, path, PARAM_KIND[name], frame)
    return v if v is not None else _default_value_at(name, frame)


def _key_param(name, frame, value, interp):
    """Key one state parameter. Lamp parameters are also mirrored into world prop env_<name> (shaders use the key
    light colour/power, e.g. the backlit plume glow)."""
    idb, path = _target_of(name)
    value = _as_value(PARAM_KIND[name], value)
    if idb is not None:
        U.key(idb, path, frame, value, interp=interp)
    if PARAM_TARGET[name] != 'W':
        U.key(_world(), f'["env_{name}"]', frame, value, interp=interp)


# ================================================================================================ public API
def build(scene=None, density=1.0, with_grass=True):
    """Build the whole environment into collection ENV (idempotent per fresh scene). Returns dict of the main
    objects: terrain, grass, pine, pine_half_A, pine_half_B, fog, key, fill, bounce, flash, gobo, world, ...
    density: grass density multiplier (1.0 final; 0.25 preview - can be changed later with set_grass_density).
    Keys the default env timeline (default_timeline / default_sun_timeline) - these keys land on the BASE NLA
    track when the lanes run (Pipeline rule 13: env.build is the first pass)."""
    sc = _scene(scene)
    _WIND_CACHE.clear()
    U.film_clock(sc)
    U.ensure_collection(COLL, scene=sc)
    out = {}
    out["world"] = _build_world(sc)
    _init_props()
    out.update(_build_lights(sc))
    out["fog"] = _build_fog(sc)
    out["terrain"] = _build_terrain(sc)
    out.update(_build_far(sc))
    out.update(_build_pine(sc))
    out["rocks"] = _build_rocks(sc)
    if with_grass:
        out["grass"] = _build_grass(sc, density)
    _init_props()
    for fr, st, bl in default_timeline():
        set_state(fr, st, bl)
    for fr, az, el, dk, it in default_sun_timeline():
        set_sun(fr, az, el, dk, interp=it)
    set_wind(config.FRAME_START, 1.0, interp='LINEAR')
    bind_characters()
    return out


def set_state(frame, state, blend_frames=0):
    """Key a complete light state. blend_frames == 0: the state applies from `frame` (CONSTANT - a cut).
    blend_frames > 0: the current values are keyed at `frame` and blend (smooth) into `state` at
    frame + blend_frames. Keys: world props env_* (sky, clouds, stars, ambient, haze, fog, grass/ground/mountain
    tints, cloud-shadow cover) and ENV_key / ENV_fill / ENV_bounce energy + colour."""
    vals = _state_values(state)
    frame = int(frame)
    if blend_frames and blend_frames > 0:
        cur = {n: _current_value(n, frame) for n, _, _ in PARAMS}
        for n, _, _ in PARAMS:
            _key_param(n, frame, cur[n], 'SINE')
        f1 = frame + int(blend_frames)
    else:
        f1 = frame
    for n, _, _ in PARAMS:
        _key_param(n, f1, vals[n], 'CONSTANT')
    _world()["env_state_last"] = state
    return f1


def set_param(frame, name, value, interp='CONSTANT'):
    """Key one state parameter (see PARAMS) - a per-shot tweak on top of set_state."""
    if name not in PARAM_KIND:
        raise KeyError(f"unknown env parameter {name!r}")
    _key_param(name, int(frame), value, interp)


def set_sun(frame, azimuth_deg, elevation_deg, disk_deg=None, interp='CONSTANT'):
    """Place the sun (or the moon in night states) for a shot: moves ENV_key (+ the shadow decks), the sky disk and its
    glow together. Keys are CONSTANT by default (a per-shot cheat holds until the next key); pass interp='LINEAR' /
    'SINE' on a key to animate from it to the NEXT key (e.g. the sun sinking during S14). Use continuous azimuths
    across animated keys (350 -> 370, not 350 -> 10).
    azimuth: compass bearing of the sun seen from the arena (0 = +Y, 90 = +X, 270 = -X).
    elevation: degrees above the horizon (the disk may set below it; the key light stays >= KEY_MIN_EL).
    disk_deg: apparent disk diameter (default: keep) - S05 wants ~1/3 picture height at 150 mm (~1.9 deg)."""
    w = _world()
    frame = int(frame)
    U.key(w, '["env_sun_az"]', frame, float(azimuth_deg), interp=interp)
    U.key(w, '["env_sun_el"]', frame, float(elevation_deg), interp=interp)
    if disk_deg is not None:
        U.key(w, '["env_disk"]', frame, float(disk_deg), interp=interp)
    piv = _obj(N_PIVOT)
    if piv is not None:
        U.key(piv, "rotation_euler", frame, _lamp_rot(azimuth_deg, max(elevation_deg, KEY_MIN_EL)), interp=interp)
    fill = _obj(N_FILL)
    if fill is not None:
        U.key(fill, "rotation_euler", frame, _lamp_rot(azimuth_deg + 180.0, 52.0), interp=interp)


def _grass_mod():
    ob = _obj(N_GRASS)
    if ob is None:
        return None, None
    return ob, ob.modifiers.get("GN")


def _key_grass_input(name, frame, value, interp):
    ob, mod = _grass_mod()
    if mod is None:
        return
    U.gn_key(ob, name, frame, value, interp=interp)


def set_wind(frame, strength, direction_deg=None, interp='LINEAR'):
    """Key the wind strength (1.0 = default breeze, 0 = calm, 2 = gale) and optionally its heading (compass
    deg the wind blows toward). LINEAR by default: the strength ramps between consecutive keys."""
    frame = int(frame)
    _WIND_CACHE.clear()
    U.key(_world(), '["env_wind"]', frame, float(strength), interp=interp)
    _key_grass_input("Wind", frame, float(strength), interp)
    if direction_deg is not None:
        U.key(_world(), '["env_wind_dir"]', frame, float(direction_deg), interp=interp)
        _key_grass_input("Wind Dir", frame, float(direction_deg), interp)


def set_burn(frame, amount, interp='LINEAR'):
    """Key the global scorch amount (0..1) applied inside the burn ring defined by grass_effect('burn', ...)
    (added to the ring's own fx-time ramp)."""
    frame = int(frame)
    U.key(_world(), '["env_burn"]', frame, float(amount), interp=interp)
    _key_grass_input("Burn Amount", frame, float(amount), interp)


def set_wetness(frame, amount, interp='LINEAR'):
    """Key wetness 0..1 (rain): grass droops + darkens + glossier, ground/rocks/pine darker and glossier."""
    frame = int(frame)
    U.key(_world(), '["env_wet"]', frame, float(amount), interp=interp)
    _key_grass_input("Wet", frame, float(amount), interp)


def _flash_registry():
    sc = bpy.context.scene
    import json
    try:
        reg = json.loads(sc.get("env_flash_log", "[]"))
    except ValueError:
        reg = []
    return sc, reg


def _fc_eval(ob, path, index, frame, default):
    """Value of ob.<path>[index] at frame from its ACTIVE action (lane build time), else `default`."""
    fc = U.fcurve(ob, path, index)
    if fc is not None and len(fc.keyframe_points):
        return float(fc.evaluate(frame))
    return float(default)


def _marker_camera(frame, scene=None):
    """The camera bound by the last timeline marker at or before `frame` (cameras.shot binds one per cut), else
    scene.camera (None when there is none)."""
    sc = _scene(scene)
    best = None
    for m in sc.timeline_markers:
        if m.camera is not None and m.frame <= frame and (best is None or m.frame > best.frame):
            best = m
    return best.camera if best is not None else sc.camera


def _subjects_xy(frame, evaluated=False):
    """Mid-point (x, y) of SHINOBI_rig / SAINT_rig at frame (the arena centre when neither exists)."""
    pts = []
    for _, _, name in PART_TARGETS:
        rig = bpy.data.objects.get(name)
        if rig is None:
            continue
        if evaluated:
            pts.append(tuple(U.world_pos_of(rig, frame))[:2])
        else:
            pts.append((_fc_eval(rig, "location", 0, frame, rig.location.x),
                        _fc_eval(rig, "location", 1, frame, rig.location.y)))
    if not pts:
        return 0.0, 0.0
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def flash_direction(frame, evaluated=False, scene=None):
    """Default lightning-light direction (azimuth_deg, elevation_deg) at `frame`: a LOW bolt light (FLASH_EL) from
    BEHIND the subjects as seen by the camera active at that frame (compass bearing camera -> fighters' mid-point,
    + FLASH_SIDE so one side rims brighter): silhouettes with bright rims, dark fronts, the lit cloud undersides
    behind them. evaluated=True reads NLA-evaluated positions (frame_set; used by aim_flashes after assembly);
    otherwise the active actions (lane build time). Falls back to FLASH_AZ_FALLBACK (behind the pair for the +X
    cameras) when no camera is known or the lens is right above the subjects."""
    sc = _scene(scene)
    cam = _marker_camera(frame, sc)
    if cam is None:
        return FLASH_AZ_FALLBACK, FLASH_EL
    sx, sy = _subjects_xy(frame, evaluated)
    if evaluated:
        cx, cy = tuple(U.world_pos_of(cam, frame))[:2]
    else:
        cx = _fc_eval(cam, "location", 0, frame, cam.location.x)
        cy = _fc_eval(cam, "location", 1, frame, cam.location.y)
    dx, dy = sx - cx, sy - cy
    if math.hypot(dx, dy) < 1.0:                     # top-down over the fighters: use the lens heading if any
        m = cam.matrix_world.to_3x3() @ Vector((0.0, 0.0, -1.0))
        dx, dy = m.x, m.y
        if math.hypot(dx, dy) < 0.05:
            return FLASH_AZ_FALLBACK, FLASH_EL
    return (math.degrees(math.atan2(dx, dy)) + FLASH_SIDE) % 360.0, FLASH_EL


def _key_flash_dir(frame, az, el):
    """Key the flash lamp orientation + the sky's flash lobe (env_flash_az / env_flash_el) at frame (CONSTANT)."""
    w = _world()
    U.key(w, '["env_flash_az"]', frame, float(az), interp='CONSTANT')
    U.key(w, '["env_flash_el"]', frame, float(el), interp='CONSTANT')
    fl = _obj(N_FLASH)
    if fl is not None:
        U.key(fl, "rotation_euler", frame, _lamp_rot(az, el), interp='CONSTANT')


def aim_flashes(scene=None):
    """Re-aim every flash of this scene (scene["env_flash_log"]) AFTER the cameras and rigs are final (build_scene:
    after lane_tools.assemble_nla): default-direction flashes get flash_direction(frame, evaluated=True) (marker
    cameras + NLA-evaluated rigs), explicit ones keep their direction; all are re-keyed so the result does not depend
    on the order in which a lane created its cameras and its flashes. Returns the number of flashes aimed."""
    import json
    sc, reg = _flash_registry()
    n = 0
    with U.muted_modifiers():
        for r in reg:
            if r.get("applied", 0.0) <= 0.0:
                continue
            if r.get("auto", True):
                r["az"], r["el"] = flash_direction(r["frame"], evaluated=True, scene=sc)
            _key_flash_dir(r["frame"], r["az"], r["el"])
            n += 1
    sc["env_flash_log"] = json.dumps(reg)
    return n


def flash(frame, strength=1.0, duration=3, tint=None, direction=None):
    """Lightning illumination at `frame`: ENV_flash lamp spike (shadowed sun lamp, visible only while flashing),
    a small world/ambient lift (FLASH_AMB: shadows stay dark) and cloud undersides lit around the flash azimuth,
    decaying over `duration` frames (CONSTANT steps - crisp strobe, envelope FLASH_ENVELOPE). Budget (DIRECTION §5):
    outside config.FULL_WHITE the strength is clamped to FLASH_MAX (calibrated <= ~70 % frame luminance) and a flash
    closer than config.FLASH_MIN_GAP frames to an existing one is refused (same frame = merged, max strength); every
    clamp/refusal is logged. tint: RGB (default FLASH_TINT, cold blue-white).
    direction: (azimuth_deg, elevation_deg) the light comes FROM (vfx may pass one per bolt); default
    flash_direction(frame): low (FLASH_EL) and from behind the fighters relative to the camera active at that frame
    (aim_flashes() re-aims defaults once the cameras are final). Returns the applied strength (0.0 if refused)."""
    import json
    frame = int(frame)
    duration = max(1, int(duration))
    sc, reg = _flash_registry()
    a0, a1 = config.FULL_WHITE
    white = a0 <= frame <= a1
    cap = FLASH_WHITE_MAX if white else FLASH_MAX
    s = float(strength)
    rec = dict(frame=frame, requested=s, applied=0.0, reason="")
    if s > cap:
        rec["reason"] = f"clamped {s:.2f}->{cap:.2f}"
        _log(f"flash @{frame}: strength {s:.2f} clamped to {cap:.2f} (DIRECTION §5)")
        s = cap
    same = [r for r in reg if r["frame"] == frame and r["applied"] > 0]
    if same:
        s = max(s, same[0]["applied"])
    else:
        for r in reg:
            if r["applied"] <= 0:
                continue
            gap = abs(r["frame"] - frame)
            both_white = white and a0 <= r["frame"] <= a1
            if 0 < gap < config.FLASH_MIN_GAP and not both_white:
                rec["reason"] = f"refused: {gap} f from flash @{r['frame']} (< FLASH_MIN_GAP {config.FLASH_MIN_GAP})"
                _log(f"flash @{frame}: {rec['reason']}")
                _FLASHES.append(rec)
                reg.append(rec)
                sc["env_flash_log"] = json.dumps(reg)
                return 0.0
    w = _world()
    fl = _obj(N_FLASH)
    env = list(FLASH_ENVELOPE[:duration]) + [0.0] * max(0, duration - len(FLASH_ENVELOPE))
    tint = tuple(tint) if tint is not None else FLASH_TINT
    if U.fcurve(w, '["env_flash"]', 0) is None or U._key_at(U.fcurve(w, '["env_flash"]', 0), frame - 1) is None:
        U.key(w, '["env_flash"]', frame - 1, 0.0, interp='CONSTANT')
    U.key(w, '["env_flash_col"]', frame, list(tint), interp='CONSTANT')
    for i, a in enumerate(env):
        U.key(w, '["env_flash"]', frame + i, float(a * s), interp='CONSTANT')
    U.key(w, '["env_flash"]', frame + duration, 0.0, interp='CONSTANT')
    if fl is not None:
        U.key_visible(fl, frame - 1, False)
        U.key_visible(fl, frame, True)
        U.key_visible(fl, frame + duration, False)
        U.key(fl.data, "color", frame, tint, interp='CONSTANT')
        U.key(fl.data, "energy", frame - 1, 0.0, interp='CONSTANT')
        for i, a in enumerate(env):
            U.key(fl.data, "energy", frame + i, float(a * s * FLASH_KEY_POWER), interp='CONSTANT')
        U.key(fl.data, "energy", frame + duration, 0.0, interp='CONSTANT')
    auto = direction is None
    az, el = flash_direction(frame, scene=sc) if auto else (float(direction[0]), float(direction[1]))
    _key_flash_dir(frame, az, el)
    rec.update(az=az, el=el, auto=auto)
    rec["applied"] = s
    reg = [r for r in reg if not (r["frame"] == frame and r["applied"] > 0)] + [rec]
    _FLASHES.append(rec)
    sc["env_flash_log"] = json.dumps(reg)
    return s


def _fx(frame):
    return float(U.film_clock().fx_time_at(float(frame)))


def grass_effect(kind, params, f0, f1=None):
    """Grass effects (Pipeline rule 8), all gated on the film clock (static GN inputs -> immune to NLA stashing;
    slow motion applies). Frames are film frames.
      'shear'  f0 = the cut starts at params['origin']; f1 = the frame the cut-line reaches params['radius']
               (speed derived; or pass params['speed'] m/s fx-time and f1=None). params: origin (x, y), radius (m),
               arc_deg (default 360), facing_deg (compass bearing of the arc centre, default 0), until (frame the
               clipped tips grow back, default None = never), fluff (pool size, default 3600; 0 = none),
               wind (fluff drift multiplier, default 1). Per-blade cut time = t0 + dist / speed; from then on the
               clump shows its stubble variant (tips above ~0.62 x height gone) and a fixed-count plume-fluff pool
               is born along the cut-line, bursting outward and drifting downwind. Up to N_SHEAR_SLOTS calls.
      'burn'   f0 = ignition, f1 = end (None = the scorch persists). params: center (x, y) (default arena centre),
               radius (m, ring centre line, default 9), width (m, default 2.5), ramp_frames (default 18).
               Ring grass chars (dark), collapses to stubble with transient embers; set_burn() adds on top.
      'wet'    f0 = wetting starts, f1 = drying starts (None = stays wet). params: amount (default 1),
               ramp_frames (default 48). Keys set_wetness.
      'freeze' the wind clock stops in [f0, f1] (S25-S26: grass frozen in place, wind 0; no pop on either end).
    Returns the fluff pool object for 'shear' (or None)."""
    bind_characters()
    ob, mod = _grass_mod()
    p = dict(params or {})
    if kind == "freeze":
        t0, t1 = _fx(f0), _fx(f1 if f1 is not None else config.FRAME_END + 1)
        w = _world()
        w["env_freeze_t0"], w["env_freeze_t1"] = t0, t1        # far-field ground sheen uses the same wind clock
        if mod is not None:
            U.gn_set(mod, "Freeze T0", t0)
            U.gn_set(mod, "Freeze T1", t1)
            ob.update_tag()
        return None
    if kind == "wet":
        amt = float(p.get("amount", 1.0))
        rf = int(p.get("ramp_frames", 48))
        set_wetness(f0, 0.0, interp='LINEAR')
        set_wetness(f0 + rf, amt, interp='CONSTANT' if f1 is None else 'LINEAR')
        if f1 is not None:
            set_wetness(f1, amt, interp='LINEAR')
            set_wetness(f1 + rf, 0.0, interp='CONSTANT')
        return None
    if kind == "burn":
        if mod is None:
            return None
        c = p.get("center", (0.0, 0.0))
        U.gn_set(mod, "Burn Center", (float(c[0]), float(c[1]), 0.0))
        U.gn_set(mod, "Burn Radius", float(p.get("radius", 9.0)))
        U.gn_set(mod, "Burn Width", float(p.get("width", 2.5)))
        t0 = _fx(f0)
        U.gn_set(mod, "Burn T0", t0)
        U.gn_set(mod, "Burn Ramp", max(_fx(f0 + int(p.get("ramp_frames", 18))) - t0, 1e-3))
        U.gn_set(mod, "Burn End", _fx(f1) if f1 is not None else 1e7)
        ob.update_tag()
        return None
    if kind != "shear":
        raise ValueError(f"unknown grass effect {kind!r} (shear | burn | wet | freeze)")
    if mod is None:
        return None
    slot = None
    for i in range(1, N_SHEAR_SLOTS + 1):
        if U.gn_input(mod, f"Shear{i} T0").value > 1e6:
            slot = i
            break
    if slot is None:
        _log(f"grass_effect shear @{f0}: all {N_SHEAR_SLOTS} shear slots used - ignored")
        return None
    org = p.get("origin", (0.0, 0.0))
    rad = float(p.get("radius", 10.0))
    t0 = _fx(f0)
    if "speed" in p:
        speed = float(p["speed"])
    elif f1 is not None and f1 > f0:
        speed = rad / max(_fx(f1) - t0, 1e-3)
    else:
        speed = 40.0
    until = p.get("until")
    U.gn_set(mod, f"Shear{slot} Origin", (float(org[0]), float(org[1]), 0.0))
    U.gn_set(mod, f"Shear{slot} T0", t0)
    U.gn_set(mod, f"Shear{slot} Speed", speed)
    U.gn_set(mod, f"Shear{slot} Radius", rad)
    U.gn_set(mod, f"Shear{slot} Arc", float(p.get("arc_deg", 360.0)))
    U.gn_set(mod, f"Shear{slot} Facing", float(p.get("facing_deg", 0.0)))
    U.gn_set(mod, f"Shear{slot} End", _fx(until) if until is not None else 1e7)
    ob.update_tag()
    n = int(p.get("fluff", 3600))
    if n <= 0:
        return None
    return _fluff_pool(f"ENV_shear_fluff_{slot}", org, rad, float(p.get("arc_deg", 360.0)),
                       float(p.get("facing_deg", 0.0)), t0, speed, n, float(p.get("wind", 1.0)), f"shear{slot}:{f0}")


FLUFF_COLL = "ENV_fluff_parts"
FLUFF_FRONT = 0.5            # m: every fluff piece is born within this distance behind the moving cut-line


def _fluff_parts():
    """Collection (excluded from the view layer) with the two fluff instance meshes (attributes match the grass
    clumps, part = 2 = plume shading): 0 = silky wisp fan (5-7 curved spindle ribbons 8-15 cm long, splayed like a
    torn-off tuft of plume), 1 = plume fragment (a 10-15 cm V-folded feather with two side wisps)."""
    col = bpy.data.collections.get(FLUFF_COLL)
    if col is not None and len(col.objects) == 2:
        return col
    col = U.ensure_collection(FLUFF_COLL, parent=COLL)
    mat = bpy.data.materials.get("ENV_grass") or _grass_material()
    rng = _rng("fluff_parts")

    def ribbon(direction, length, width, bend, lift, nseg=4, fold=0.0, lv=0.5):
        d = np.asarray(direction, dtype=float)
        d = d / np.linalg.norm(d)
        up = np.array([0.0, 0.0, 1.0])
        p2 = d * length * 0.92 + up * (lift - bend) * length
        p1 = d * length * 0.45 + up * lift * length
        pts = _bezier(np.zeros(3), p1, p2, nseg)
        u = np.linspace(0.0, 1.0, nseg + 1)
        w = width * np.power(np.sin(np.pi * np.clip(u * 0.88 + 0.06, 0.0, 1.0)), 0.75)
        return (pts, w, 2, lv, fold)

    wisp = []
    nfan = int(rng.integers(5, 8))
    a0 = rng.uniform(0, 2 * math.pi)
    for k in range(nfan):
        a = a0 + (k - (nfan - 1) / 2) * math.radians(70.0 / max(nfan - 1, 1)) + rng.uniform(-0.08, 0.08)
        wisp.append(ribbon((math.cos(a), math.sin(a), 0.0), rng.uniform(0.08, 0.15), rng.uniform(0.005, 0.008),
                           rng.uniform(0.15, 0.35), rng.uniform(0.05, 0.25), 4, 0.0, rng.uniform()))
    frag = [ribbon((1.0, 0.0, 0.0), rng.uniform(0.10, 0.15), 0.02, 0.25, 0.3, 5, 0.18, rng.uniform())]
    for sgn in (-1.0, 1.0):
        a = sgn * rng.uniform(0.35, 0.6)
        frag.append(ribbon((math.cos(a), math.sin(a), 0.0), rng.uniform(0.07, 0.1), 0.006, 0.3, 0.2, 3, 0.0,
                           rng.uniform()))
    obs = [_strands_to_mesh("ENV_fluff_0_wisp", wisp, collection=FLUFF_COLL),
           _strands_to_mesh("ENV_fluff_1_frag", frag, collection=FLUFF_COLL)]
    for ob in obs:
        ob.data.materials.append(mat)
        me = ob.data
        U.add_attribute(me, "hz", np.ones(len(me.vertices), dtype=np.float32))
    lc = _layer_coll(bpy.context.view_layer.layer_collection, col)
    if lc is not None:
        lc.exclude = True
    return col


def _fluff_tree():
    ng = bpy.data.node_groups.get("GN_ENV_fluff")
    if ng is not None:
        return ng
    ng = U.gn_new_tree("GN_ENV_fluff", inputs=[("Time", "FLOAT", 0.0), ("Wind Vec", "VECTOR", (0.0, 0.0, 0.0)),
                                               ("Parts", "COLLECTION")])
    nb = U.NB(ng)
    gi = nb.gi
    tau = nb.math('SUBTRACT', gi['Time'], nb.attr("tb"))
    life = nb.attr("life")
    tc = nb.math('MINIMUM', nb.math('MAXIMUM', tau, 0.0), life)
    kd = nb.math('MAXIMUM', nb.attr("kd"), 0.05)
    e = nb.math('DIVIDE', nb.math('SUBTRACT', 1.0, nb.math('EXPONENT', nb.math('MULTIPLY', nb.math('MULTIPLY', kd, tc), -1.0))), kd)
    v0 = nb.attr("vel0", 'FLOAT_VECTOR')
    vw = gi['Wind Vec']
    off = nb.vmath('ADD', nb.vmath('SCALE', vw, scale=tc), nb.vmath('SCALE', nb.vmath('SUBTRACT', v0, vw), scale=e))
    off = nb.vmath('ADD', off, nb.xyz(0.0, 0.0, nb.math('MULTIPLY', nb.math('MULTIPLY', tc, tc),
                                                          nb.math('MULTIPLY', nb.attr("gz"), 0.5))))
    ph = nb.attr("ph")
    sw = _gsmooth(nb, tc, 0.0, 1.0)
    swirl = nb.xyz(nb.math('SINE', nb.math('ADD', nb.math('MULTIPLY', tc, 1.7), ph)),
                   nb.math('COSINE', nb.math('ADD', nb.math('MULTIPLY', tc, 1.3), nb.math('MULTIPLY', ph, 2.0))),
                   nb.math('MULTIPLY', 0.4, nb.math('SINE', nb.math('ADD', nb.math('MULTIPLY', tc, 2.3), ph))))
    off = nb.vmath('ADD', off, nb.vmath('SCALE', swirl, scale=nb.math('MULTIPLY', sw, 0.15)))
    moved = nb.n('GeometryNodeSetPosition', gi['Geometry'], Offset=off)
    # fresh fluff is brighter (the burst right behind the racing cut-line reads as a luminous front)
    moved = nb.store(moved, "fburst", nb.math('EXPONENT', nb.math('DIVIDE', tc, -FLUFF_BURST_T)), 'FLOAT', 'POINT')
    alive = nb.bmath('AND', nb.cmp('GREATER_EQUAL', tau, 0.0), nb.cmp('LESS_EQUAL', tau, life))
    grow = _gsmooth(nb, tc, 0.0, 0.06)
    fade = nb.math('SUBTRACT', 1.0, nb.map_range(tc, nb.math('MULTIPLY', life, 0.65), life, 0.0, 1.0, clamp=True,
                                                   interp='SMOOTHSTEP'))
    sc = nb.math('MULTIPLY', nb.math('MULTIPLY', nb.attr("sz"), nb.math('MULTIPLY', grow, fade)), alive)
    rot = nb.n('FunctionNodeEulerToRotation', nb.xyz(nb.math('ADD', ph, nb.math('MULTIPLY', tc, 2.0)),
                                                     nb.math('ADD', nb.math('MULTIPLY', ph, 1.3), nb.math('MULTIPLY', tc, 1.5)),
                                                     nb.math('ADD', nb.math('MULTIPLY', ph, 0.7), nb.math('MULTIPLY', tc, 1.1))))
    parts = nb.n('GeometryNodeCollectionInfo', gi['Parts'], True, True, transform_space='RELATIVE')
    inst = nb.n('GeometryNodeInstanceOnPoints', Points=moved, Instance=parts, Pick_Instance=True,
                Instance_Index=nb.attr("kind", 'INT'), Rotation=rot, Scale=nb.xyz(sc, sc, sc))
    nb.link(inst, nb.go['Geometry'])          # fixed count at every frame: unborn / dead pieces have scale 0
    nb.layout()
    return ng


def _fluff_pool(name, origin, radius, arc, facing, t0, speed, n, wind, seed):
    """Fixed-count plume-fluff pool for a shear: n points born (fx time) when the cut-line passes them, at plume
    height, bursting outward from the origin, then dragged into the wind drift (exponential drag), slowly sinking,
    swirling and tumbling; scale grows in, fades out, 0 when unborn/dead (Pipeline rule 3)."""
    rng = _rng("fluff", seed)
    u = rng.uniform(0, 1, n)
    d = 0.6 + (radius - 0.6) * np.sqrt(u)
    bearing = np.radians(facing + (rng.uniform(0, 1, n) - 0.5) * arc)
    x = origin[0] + d * np.sin(bearing)
    y = origin[1] + d * np.cos(bearing)
    z = terrain_height(x, y) + rng.uniform(0.62, 1.08, n)
    radial = np.stack([np.sin(bearing), np.cos(bearing), np.zeros(n)], 1)
    v0 = radial * rng.uniform(1.0, 3.5, n)[:, None] + np.stack(
        [rng.uniform(-0.6, 0.6, n), rng.uniform(-0.6, 0.6, n), rng.uniform(1.0, 3.2, n)], 1)
    tb = t0 + d / max(speed, 0.01) + rng.uniform(0.0, FLUFF_FRONT, n) / max(speed, 0.01)   # just behind the line
    life = rng.uniform(2.5, 5.5, n)
    kind = (rng.uniform(0, 1, n) < 0.3).astype(np.int32)
    ob = U.mesh_from_data(name, np.stack([x, y, z], 1), collection=COLL)
    me = ob.data
    U.add_attribute(me, "vel0", v0.astype(np.float32), 'FLOAT_VECTOR')
    U.add_attribute(me, "tb", tb.astype(np.float32), 'FLOAT')
    U.add_attribute(me, "life", life.astype(np.float32), 'FLOAT')
    U.add_attribute(me, "kd", rng.uniform(0.8, 1.7, n).astype(np.float32), 'FLOAT')
    U.add_attribute(me, "gz", np.where(kind == 1, -0.9, -0.3).astype(np.float32) * rng.uniform(0.7, 1.3, n).astype(
        np.float32), 'FLOAT')
    U.add_attribute(me, "ph", rng.uniform(0, 6.2832, n).astype(np.float32), 'FLOAT')
    U.add_attribute(me, "sz", np.where(kind == 1, 1.0, 1.25).astype(np.float32) * rng.uniform(1.0, 1.5, n).astype(
        np.float32), 'FLOAT')
    U.add_attribute(me, "kind", kind, 'INT')
    U.add_attribute(me, "fluffy", np.ones(n, dtype=np.float32), 'FLOAT')
    hd = math.radians(float(_world().get("env_wind_dir", DEFAULT_WIND_DIR)))
    vw = (math.sin(hd) * 1.3 * wind, math.cos(hd) * 1.3 * wind, 0.05)
    U.gn_modifier(ob, _fluff_tree(), Parts=_fluff_parts(), **{"Wind Vec": vw})
    U.film_clock().drive_gn_input(ob, "Time")
    ob.visible_shadow = False
    return ob


CLEAR_NEAR, CLEAR_FAR = config.GRASS_CAMERA_CLEAR


def set_camera_clearance(frame, near=None, far=None, cone_deg=None, cone_len=None, interp='CONSTANT'):
    """Key the grass clearance around the ACTIVE camera: instances scale 0 -> 1 between `near` and `far` metres
    (defaults CLEAR_NEAR / CLEAR_FAR). cone_deg > 0 switches to the narrow FRONT-CONE mode (S03 knee-height
    tracking): only grass inside a cone of half-angle cone_deg around the view axis, up to cone_len metres, is
    cleared (the spherical clearance is then off). CONSTANT by default (per-shot values hold until the next key)."""
    frame = int(frame)
    ob, mod = _grass_mod()
    if mod is None:
        return
    if near is not None:
        U.gn_key(ob, "Clear Near", frame, float(near), interp=interp)
    if far is not None:
        far = max(float(far), float(near if near is not None else U.gn_input(ob, "Clear Near").value) + 0.05)
        U.gn_key(ob, "Clear Far", frame, far, interp=interp)
    if cone_deg is not None:
        U.gn_key(ob, "Cone Angle", frame, float(cone_deg), interp=interp)
    if cone_len is not None:
        U.gn_key(ob, "Cone Length", frame, float(cone_len), interp=interp)


def set_cloud_shadow(frame, cover=None, edge=None, edge_dir_deg=None, edge_width=None, interp='LINEAR'):
    """Key the ground light pattern the shadow decks cast with the key light: cover = drifting cloud-shadow
    amount (0..1, also part of each state as gobo_cover); edge = position (m, measured from the arena centre along
    compass heading edge_dir_deg) of a moving light edge: ground with (g . dir) > edge is lit, the rest is in
    shadow (S27 moonlight sweep: point edge_dir from the foreground to the background and key edge from +far to
    -near, e.g. set_cloud_shadow(3505, edge=40, edge_dir_deg=..) -> set_cloud_shadow(3550, edge=-30)).
    edge='off' switches the edge mode off. edge_width = softness (m)."""
    w = _world()
    frame = int(frame)
    if cover is not None:
        _key_param("gobo_cover", frame, float(cover), interp)
    if edge is not None:
        if edge == 'off':
            U.key(w, '["env_edge_on"]', frame, 0.0, interp='CONSTANT')
        else:
            U.key(w, '["env_edge_on"]', frame, 1.0, interp='CONSTANT')
            U.key(w, '["env_edge_pos"]', frame, float(edge), interp=interp)
    if edge_dir_deg is not None:
        U.key(w, '["env_edge_dir"]', frame, float(edge_dir_deg), interp='CONSTANT')
    if edge_width is not None:
        U.key(w, '["env_edge_w"]', frame, float(edge_width), interp=interp)


def set_grass_density(value):
    """Static grass density multiplier (1.0 final, 0.25 preview). Changes the distribution (not animated)."""
    ob, mod = _grass_mod()
    if mod is not None:
        U.gn_set(mod, "Density", float(value))
        ob.update_tag()          # 5.2: an RNA set of a modifier input does not re-evaluate the object by itself


PART_TARGETS = (("Char A", "Char A On", "SHINOBI_rig"), ("Char B", "Char B On", "SAINT_rig"))


def bind_characters():
    """Point the grass parting inputs at SHINOBI_rig / SAINT_rig when they exist (idempotent, cheap). Returns the
    number of bound characters. build_scene should call it after characters.build(); grass_effect and
    key_lane_defaults call it too."""
    ob, mod = _grass_mod()
    if mod is None:
        return 0
    k = 0
    for inp, flag, name in PART_TARGETS:
        rig = bpy.data.objects.get(name)
        U.gn_set(mod, inp, rig)
        U.gn_set(mod, flag, rig is not None)
        k += rig is not None
    ob.update_tag()
    return k


def _default_sun_at(frame):
    """(az, el, disk) of the default sun timeline at frame (LINEAR segments honoured)."""
    tl = default_sun_timeline()
    cur = tl[0]
    for i, k in enumerate(tl):
        if frame < k[0]:
            prev = tl[i - 1] if i > 0 else k
            if prev[4] != 'CONSTANT' and k[0] > prev[0]:
                u = (frame - prev[0]) / float(k[0] - prev[0])
                return tuple(prev[j] + (k[j] - prev[j]) * u for j in (1, 2, 3))
            return prev[1], prev[2], prev[3]
        cur = k
    return cur[1], cur[2], cur[3]


def key_lane_defaults(lane_or_span):
    """Key the default env timeline inside a lane's span (a complete snapshot at the span start + every default
    transition inside it + wind 1, no flash, no light edge), so the lane's NLA strip never holds a stale env
    forward. The per-shot cheats (set_sun, set_camera_clearance) are CONSTANT keys that hold forward, so the default
    sun and the default clearance are also keyed at EVERY shot start inside the span: a lane that forgets to restore
    them cannot leak a cheat into its next shot (lane keys on the same frame are made later and replace these).
    Call right after lane_tools.begin_lane(lane) (build_scene) - lanes then override per shot by calling
    set_state / set_sun / ... inside their span."""
    s, e = config.lane_span(lane_or_span) if isinstance(lane_or_span, str) else lane_or_span
    s, e = int(s), int(e)
    bind_characters()
    for n, _, _ in PARAMS:
        _key_param(n, s, _default_value_at(n, s), 'CONSTANT')
    for fr, st, bl in default_timeline():
        if s < fr <= e:
            set_state(fr, st, bl)
        elif fr <= s < fr + bl:           # a default blend in progress at the span start
            f1 = fr + bl
            if f1 <= e + 1:
                for n, _, _ in PARAMS:
                    _key_param(n, s, _default_value_at(n, s), 'SINE')
                    _key_param(n, f1, STATES[st][n], 'CONSTANT')
    az, el, dk = _default_sun_at(s)
    tl = default_sun_timeline()
    nxt = [k for k in tl if s < k[0] <= e]
    first_interp = 'CONSTANT'
    prev = [k for k in tl if k[0] <= s]
    if prev and prev[-1][4] != 'CONSTANT' and nxt:
        first_interp = prev[-1][4]
    set_sun(s, az, el, dk, interp=first_interp)
    for fr, a, el2, d, it in nxt:
        set_sun(fr, a, el2, d, interp=it)
    starts = sorted({int(sh["start"]) for sh in config.SHOTS if s < sh["start"] <= e})
    keyed = {k[0] for k in nxt}
    for fr in starts:                 # default sun at every shot start (cheats never leak across a cut)
        if fr in keyed:
            continue
        a, el2, d = _default_sun_at(fr)
        prev = [k for k in tl if k[0] <= fr]
        it = prev[-1][4] if prev and prev[-1][4] != 'CONSTANT' and any(k[0] > fr for k in tl) else 'CONSTANT'
        set_sun(fr, a, el2, d, interp=it)
    set_wind(s, 1.0, interp='LINEAR')
    w = _world()
    U.key(w, '["env_flash"]', s, 0.0, interp='CONSTANT')
    U.key(w, '["env_edge_on"]', s, 0.0, interp='CONSTANT')
    fl = _obj(N_FLASH)
    if fl is not None:
        U.key_visible(fl, s, False)
    for fr in [s] + starts:           # default clearance at every shot start
        set_camera_clearance(fr, CLEAR_NEAR, CLEAR_FAR, 0.0, 0.0)


def bake_wake(f0=None, f1=None, step=1, lags=None):
    """Parting WAKE (rule 8, optional): key the wake samples ENV_wake_SHINOBI_1/2 and ENV_wake_SAINT_1/2 to follow
    SHINOBI_rig / SAINT_rig `lags` (default WAKE_LAGS) seconds of FILM CLOCK behind (slow motion honoured), so the
    grass stays parted along the path for ~1 s and closes behind the walker (S02 / S03 / S28). The wake parts with
    WAKE_STRENGTH (decaying along the trail) and fades like the rig when the sample is > 0.8 m up.
    Call ONCE after the rigs' animation is final (build_scene: after lane_tools.assemble_nla; it frame_sets through
    [f0, f1] with GN modifiers muted). Keys are LINEAR every `step` frames. Returns the number of keyed samples."""
    ob, mod = _grass_mod()
    if mod is None:
        return 0
    bind_characters()
    lags = tuple(lags) if lags is not None else WAKE_LAGS
    f0 = config.FRAME_START if f0 is None else int(f0)
    f1 = config.FRAME_END if f1 is None else int(f1)
    clk = U.film_clock()
    lead = int(math.ceil(max(lags) * FPS / 0.1)) + 2          # worst case: slowest time warp 0.125 -> ~8x frames
    fr_all = np.arange(max(config.FRAME_START - int(FPS), f0 - lead), f1 + 1)
    fx_all = np.array([clk.fx_time_at(float(f)) for f in fr_all])
    rigs = {tag: bpy.data.objects.get(name) for (inp, _, name), tag in zip(PART_TARGETS, ("A", "B"))}
    rigs = {k: v for k, v in rigs.items() if v is not None}
    if not rigs:
        return 0
    with U.muted_modifiers():
        pos = U.sample_positions(rigs, [int(f) for f in fr_all])
    n = 0
    keyed = np.arange(f0, f1 + 1, max(1, int(step)))
    fx_k = np.array([clk.fx_time_at(float(f)) for f in keyed])
    for tag, P in pos.items():
        for i, lag in enumerate(lags[:2]):
            e = bpy.data.objects.get(WAKE_NAMES[f"Wake {tag}{i + 1}"])
            if e is None:
                continue
            src = np.interp(fx_k - lag, fx_all, fr_all.astype(float))
            xyz = np.stack([np.interp(src, fr_all, P[:, j]) for j in range(3)], 1)
            if e.animation_data is not None:
                e.animation_data_clear()
            for j in range(3):
                fc = U.fcurve(e, "location", j, create=True)
                kp = fc.keyframe_points
                kp.add(len(keyed))
                co = np.empty(2 * len(keyed), np.float32)
                co[0::2] = keyed
                co[1::2] = xyz[:, j]
                kp.foreach_set("co", co)
                kp.foreach_set("interpolation", [bpy.types.Keyframe.bl_rna.properties["interpolation"].enum_items[
                    'LINEAR'].value] * len(keyed))
                fc.update()
            n += len(keyed)
    U.gn_set(mod, "Wake On", True)
    ob.update_tag()
    return n


def finalize(scene=None, wake=True, span=None):
    """Post-assembly env pass (build_scene: right after lane_tools.assemble_nla, before render_setup.configure):
    bake_wake() (parting wake behind both rigs, needs their final motion) + aim_flashes() (default flash
    directions from the final marker cameras). span=(f0, f1) limits the wake bake to the built frames (partial /
    dev-lane builds; default the whole film). Idempotent. Returns dict(wake_keys, flashes)."""
    n_w = (bake_wake(*span) if span is not None else bake_wake()) if wake else 0
    n_f = aim_flashes(scene)
    return dict(wake_keys=n_w, flashes=n_f)


def _frame_value(idb, path, frame, index=0):
    """Evaluated (NLA included) value of a keyed property at frame: frame_set with GN modifiers muted."""
    sc = bpy.context.scene
    with U.muted_modifiers():
        U.frame_set(frame, sc)
        v = idb.path_resolve(path)
    try:
        return float(v[index])
    except TypeError:
        return float(v)


_WIND_CACHE = {}


def wind_at(frame):
    """(strength, (dx, dy)) of the wind at frame (NLA included; for characters.apply_secondary_motion).
    (dx, dy) is the unit heading the wind blows toward. Memoised per frame (one scene evaluation per frame; the
    cache is cleared by set_wind / key_lane_defaults / build)."""
    k = (bpy.context.scene.name, round(float(frame), 4))
    if k not in _WIND_CACHE:
        w = _world()
        st = _frame_value(w, '["env_wind"]', frame)
        hd = math.radians(float(w.get("env_wind_dir", DEFAULT_WIND_DIR)))
        _WIND_CACHE[k] = (st, (math.sin(hd), math.cos(hd)))
    return _WIND_CACHE[k]


def flash_log():
    """List of dicts (frame, strength, applied, reason) of every flash request in this session."""
    return list(_FLASHES)


_FLASHES = []


# ================================================================================================ shader helpers
# Extra world props that are not part of a state snapshot (keyed by set_sun / flash / set_cloud_shadow / ...).
EXTRA_PROPS = dict(sun_az=270.0, sun_el=4.0, disk=2.2, flash=0.0, flash_col=FLASH_TINT, wind=1.0, wet=0.0,
                   burn=0.0, edge_on=0.0, edge_pos=0.0, edge_dir=0.0, edge_w=6.0, wind_dir=DEFAULT_WIND_DIR,
                   flash_az=FLASH_AZ_FALLBACK, flash_el=FLASH_EL, freeze_t0=1e7, freeze_t1=1e7)


def _init_props():
    """Create every world prop env_* with the dusk_gold defaults (VIEW_LAYER attributes read 0 when missing)."""
    w = _world()
    for n, k, t in PARAMS:
        if f"env_{n}" not in w.keys():
            w[f"env_{n}"] = _as_value(k, STATES["dusk_gold"][n])
    for n, v in EXTRA_PROPS.items():
        if f"env_{n}" not in w.keys():
            w[f"env_{n}"] = list(v) if isinstance(v, tuple) else float(v)


def _va(nb, name):
    """Attribute node (VIEW_LAYER) reading world prop env_<name>: NodeRef with outputs Color / Fac."""
    r = nb.n('ShaderNodeAttribute', attribute_type='VIEW_LAYER')
    r.node.attribute_name = f"env_{name}"
    return r


def _vf(nb, name):
    return _va(nb, name)['Fac']


def _vc(nb, name):
    return _va(nb, name)['Color']


def _smooth(nb, v, a, b):
    """smoothstep(a, b, v) (a > b allowed -> inverted)."""
    if a > b:
        return nb.map_range(v, b, a, 1.0, 0.0, clamp=True, interp='SMOOTHSTEP')
    return nb.map_range(v, a, b, 0.0, 1.0, clamp=True, interp='SMOOTHSTEP')


def _powpos(nb, v, k):
    return nb.math('POWER', nb.math('MAXIMUM', v, 0.0), k)


def _cmul(nb, c, f):
    """colour * float (Vector Math SCALE keeps it a 3-vector; colour sockets accept it)."""
    return nb.vmath('SCALE', c, scale=f)


def _shader_group(name, inputs, outputs):
    """New ShaderNodeTree group. inputs/outputs: [(name, socket_type)] -> (ng, nb, gi, go)."""
    old = bpy.data.node_groups.get(name)
    if old is not None:
        bpy.data.node_groups.remove(old)
    ng = bpy.data.node_groups.new(name, 'ShaderNodeTree')
    for n, t in inputs:
        ng.interface.new_socket(n, in_out='INPUT', socket_type=t)
    for n, t in outputs:
        ng.interface.new_socket(n, in_out='OUTPUT', socket_type=t)
    nb = U.NB(ng, group_io=False)
    gi = nb.n('NodeGroupInput')
    go = nb.n('NodeGroupOutput')
    return ng, nb, gi, go


def _sun_dir(nb, az=None, el=None):
    """World-space unit vector towards the sun/moon from world props env_sun_az / env_sun_el (degrees)."""
    az = nb.math('RADIANS', az if az is not None else _vf(nb, "sun_az"))
    el = nb.math('RADIANS', el if el is not None else _vf(nb, "sun_el"))
    ce = nb.math('COSINE', el)
    return nb.xyz(nb.math('MULTIPLY', nb.math('SINE', az), ce), nb.math('MULTIPLY', nb.math('COSINE', az), ce),
                  nb.math('SINE', el))


def _group_node(nb, group, *args, **kw):
    return nb.n('ShaderNodeGroup', *args, node_tree=group, **kw)


def _sky_atmos_group():
    """ENV_SkyAtmos(Dir) -> Color (state sky gradient + sun glow + horizon band, no disk/clouds/stars), Mu (dot
    with the sun), Elev (dir.z). Shared by the world and by every material's aerial perspective, so distant
    things fade exactly into the sky of the current state."""
    ng, nb, gi, go = _shader_group("ENV_SkyAtmos", [("Dir", 'NodeSocketVector'), ("Tight", 'NodeSocketFloat')],
                                   [("Color", 'NodeSocketColor'), ("Mu", 'NodeSocketFloat'),
                                    ("Elev", 'NodeSocketFloat')])
    d = nb.vmath('NORMALIZE', gi['Dir'])
    e = nb.sep(d)['Z']
    ec = nb.math('MAXIMUM', e, 0.0)
    hor, mid, zen = _vc(nb, "sky_hor"), _vc(nb, "sky_mid"), _vc(nb, "sky_zen")
    c = nb.mix(_smooth(nb, ec, 0.0, 0.16), hor, mid, 'RGBA')
    c = nb.mix(nb.math('POWER', _smooth(nb, ec, 0.05, 0.75), 0.8), c, zen, 'RGBA')
    below = _cmul(nb, hor, 0.55)
    c = nb.mix(_smooth(nb, e, 0.0, -0.06), c, below, 'RGBA')
    s = _sun_dir(nb)
    mu = nb.vmath('DOT_PRODUCT', d, s)
    wide = _vf(nb, "glow_wide")
    k1 = nb.math('DIVIDE', 5.0, nb.math('MAXIMUM', wide, 0.05))
    hb = nb.math('ADD', 0.30, nb.math('MULTIPLY', 0.70, nb.math('POWER', nb.math('SUBTRACT', 1.0, ec), 5.0)))
    # glow = a wide lobe (glow_wide) + tight lobes around the disk (~10, ~6 and ~2.5 deg): a radial gradient even
    # inside a telephoto frame; the tight part shifts toward the disk colour (hotter, yellower near the sun)
    tight = nb.math('ADD', nb.math('ADD', nb.math('MULTIPLY', _powpos(nb, mu, 40.0), 0.30),
                                   nb.math('MULTIPLY', _powpos(nb, mu, 250.0), 0.55)),
                    nb.math('MULTIPLY', _powpos(nb, mu, 1500.0), 0.50))
    tight = nb.math('MULTIPLY', nb.math('MULTIPLY', nb.math('MULTIPLY', tight, gi['Tight']), hb), _vf(nb, "glow_str"))
    g = nb.math('MULTIPLY', _powpos(nb, mu, k1), 0.45)
    g = nb.math('MULTIPLY', nb.math('MULTIPLY', g, hb), _vf(nb, "glow_str"))
    # horizon band: the whole horizon brightens towards the sun azimuth (low sun / afterglow)
    dxy = nb.vmath('NORMALIZE', nb.vmath('MULTIPLY', d, (1.0, 1.0, 0.0)))
    sxy = nb.vmath('NORMALIZE', nb.vmath('MULTIPLY', s, (1.0, 1.0, 0.0)))
    band = nb.math('MULTIPLY', _powpos(nb, nb.vmath('DOT_PRODUCT', dxy, sxy), 2.0),
                   nb.math('EXPONENT', nb.math('MULTIPLY', ec, -14.0)))
    g = nb.math('ADD', g, nb.math('MULTIPLY', band, nb.math('MULTIPLY', _vf(nb, "glow_str"), 0.22)))
    c = nb.vmath('ADD', c, _cmul(nb, _vc(nb, "glow_col"), g))
    c = nb.vmath('ADD', c, _cmul(nb, nb.mix(0.35, _vc(nb, "glow_col"), _vc(nb, "disk_col"), 'RGBA'), tight))
    c = _cmul(nb, c, _vf(nb, "sky_str"))
    nb.link(c, go.inp('Color'))
    nb.link(mu, go.inp('Mu'))
    nb.link(e, go.inp('Elev'))
    return ng


def _aerial_group(sky):
    """ENV_Aerial(Shader, Amount) -> Shader: aerial perspective. Mixes the surface towards the state's horizon sky
    colour seen in the same direction: a = haze_max * (1 - exp(-dist / haze_dist)) * Amount."""
    ng, nb, gi, go = _shader_group("ENV_Aerial", [("Shader", 'NodeSocketShader'), ("Amount", 'NodeSocketFloat')],
                                   [("Shader", 'NodeSocketShader')])
    ng.interface.items_tree["Amount"].default_value = 1.0
    geo = nb.n('ShaderNodeNewGeometry')
    d = nb.vmath('SCALE', geo['Incoming'], scale=-1.0)
    dh = nb.vmath('ADD', nb.vmath('MULTIPLY', d, (1.0, 1.0, 0.0)), (0.0, 0.0, 0.035))
    atm = _group_node(nb, sky, dh, HAZE_TIGHT)
    dist = nb.n('ShaderNodeCameraData')['View Distance']
    a = nb.math('SUBTRACT', 1.0, nb.math('EXPONENT', nb.math('DIVIDE', nb.math('MULTIPLY', dist, -1.0),
                                                                   nb.math('MAXIMUM', _vf(nb, "haze_dist"), 1.0))))
    a = nb.math('MULTIPLY', nb.math('MULTIPLY', a, _vf(nb, "haze_max")), gi['Amount'])
    em = nb.n('ShaderNodeEmission', atm['Color'], 1.0)
    mix = nb.n('ShaderNodeMixShader', a, gi['Shader'], em)
    nb.link(mix, go.inp('Shader'))
    return ng


def _groups():
    sky = bpy.data.node_groups.get("ENV_SkyAtmos") or _sky_atmos_group()
    aer = bpy.data.node_groups.get("ENV_Aerial") or _aerial_group(sky)
    return sky, aer


def _fx_value(nb, name="FX Time"):
    """Value node named 'FX Time' (driven by fx_time after the material/world exists: _drive_fx)."""
    r = nb.n('ShaderNodeValue', name=name)
    r.node.outputs[0].default_value = 0.0
    return r.node.outputs[0]


def _drive_fx(owner, name="FX Time"):
    fxc = U.film_clock()
    fxc.drive_node_value(owner, name)


# ================================================================================================ world / sky
def _build_world(sc):
    """ENV_world: sky gradient + glow (ENV_SkyAtmos) + sun/moon disk + streaky clouds (lit undersides on flash) +
    stars; camera rays see the sky, lighting rays see a controlled ambient (amb_col * amb_str + flash)."""
    sky, _ = _groups()
    w = bpy.data.worlds.get(WORLD_NAME) or bpy.data.worlds.new(WORLD_NAME)
    sc.world = w
    w.color = (0.45, 0.30, 0.22)          # workbench/layout background
    w.sun_threshold = 0.0
    w.use_sun_shadow = False
    nt = w.node_tree
    nt.nodes.clear()
    nb = U.NB(nt, group_io=False)
    out = nb.n('ShaderNodeOutputWorld')
    tc = nb.n('ShaderNodeTexCoord')
    d = nb.vmath('NORMALIZE', tc['Generated'])
    atm = _group_node(nb, sky, d, 1.0)
    mu, e = atm['Mu'], atm['Elev']
    ec = nb.math('MAXIMUM', e, 0.0)
    t = _fx_value(nb)
    # ---- disk (sun or moon): the SUN is a saturated core with limb darkening that reddens toward its rim, the MOON a
    # flat bright disk with maria; inside its outline the disk REPLACES the sky (keeps it saturated under AgX); a
    # tight halo lobe (~3 deg, DISK_HALO) sits around it and the bloom (threshold 0.9) finishes the glow
    r = nb.math('MAXIMUM', nb.math('MULTIPLY', nb.math('RADIANS', _vf(nb, "disk")), 0.5), 1e-4)
    c_in = nb.math('COSINE', nb.math('MULTIPLY', r, 0.97))
    c_out = nb.math('COSINE', nb.math('MULTIPLY', r, 1.03))
    mask = nb.map_range(mu, c_out, c_in, 0.0, 1.0, clamp=True, interp='SMOOTHSTEP')
    rr = nb.math('MINIMUM', nb.math('DIVIDE', nb.math('SQRT', nb.math('MAXIMUM', nb.math(
        'MULTIPLY', nb.math('SUBTRACT', 1.0, mu), 2.0), 0.0)), r), 1.0)
    limb = nb.math('SUBTRACT', 1.0, nb.math('MULTIPLY', DISK_LIMB, nb.math('SUBTRACT', 1.0, nb.math(
        'SQRT', nb.math('MAXIMUM', nb.math('SUBTRACT', 1.0, nb.math('MULTIPLY', rr, rr)), 0.0)))))
    moon_tex = nb.noise(nb.vmath('SCALE', d, scale=1.0), scale=70.0, detail=4.0, roughness=0.6)
    maria = nb.map_range(moon_tex['Fac'], 0.42, 0.62, 0.62, 1.0, clamp=True)
    look = nb.mix(_vf(nb, "disk_moon"), limb, maria)
    horiz = _smooth(nb, e, -0.004, 0.004)
    dstr = nb.math('MULTIPLY', nb.math('MULTIPLY', mask, _vf(nb, "disk_vis")),
                   nb.math('MULTIPLY', _vf(nb, "disk_str"), look))
    dstr = nb.math('MULTIPLY', dstr, horiz)
    dmask = nb.math('MULTIPLY', nb.math('MULTIPLY', mask, _vf(nb, "disk_vis")), horiz)
    rim_mix = nb.math('MULTIPLY', nb.math('MULTIPLY', rr, rr), nb.math('SUBTRACT', 1.0, _vf(nb, "disk_moon")))
    dcol = nb.mix(rim_mix, _vc(nb, "disk_col"), nb.vmath('MULTIPLY', _vc(nb, "disk_col"), DISK_LIMB_TINT), 'RGBA')
    col = nb.mix(dmask, atm['Color'], _cmul(nb, dcol, nb.math('DIVIDE', dstr, nb.math('MAXIMUM', dmask, 1e-4))),
                 'RGBA')
    halo = nb.math('MULTIPLY', _powpos(nb, mu, 2000.0), nb.math('MULTIPLY', nb.math(
        'MULTIPLY', _vf(nb, "disk_vis"), _vf(nb, "disk_str")), DISK_HALO))
    halo = nb.math('MULTIPLY', nb.math('MULTIPLY', halo, nb.math('SUBTRACT', 1.0, dmask)), _smooth(nb, e, -0.01, 0.004))
    col = nb.vmath('ADD', col, _cmul(nb, nb.mix(0.5, _vc(nb, "glow_col"), _vc(nb, "disk_col"), 'RGBA'), halo))
    # ---- stars (moon state): sparse voronoi points, hidden near the horizon and under clouds
    vor = nb.n('ShaderNodeTexVoronoi', voronoi_dimensions='3D', feature='F1', Vector=d, Scale=420.0)
    cr = nb.sep(vor['Color'])
    mag = nb.math('ADD', nb.math('MULTIPLY', _smooth(nb, cr['X'], 0.86, 0.995), 0.8),
                  nb.math('MULTIPLY', _smooth(nb, cr['Y'], 0.97, 1.0), 3.0))
    star = nb.math('MULTIPLY', _smooth(nb, vor['Distance'], 0.15, 0.02), mag)
    star = nb.math('MULTIPLY', star, nb.math('MULTIPLY', _vf(nb, "star_str"), 5.0))
    star = nb.math('MULTIPLY', star, _smooth(nb, e, 0.03, 0.30))
    # ---- clouds: a plane layer projected on the view ray, streaked along its own axis, drifting on fx time
    uvz = nb.math('ADD', ec, 0.055)
    sd = nb.sep(d)
    u = nb.math('DIVIDE', sd['X'], uvz)
    v = nb.math('DIVIDE', sd['Y'], uvz)
    ang = math.radians(28.0)
    ca, sa = math.cos(ang), math.sin(ang)
    ur = nb.math('ADD', nb.math('MULTIPLY', u, ca), nb.math('MULTIPLY', v, sa))
    vr = nb.math('SUBTRACT', nb.math('MULTIPLY', v, ca), nb.math('MULTIPLY', u, sa))
    streak = nb.math('MAXIMUM', _vf(nb, "cloud_streak"), 1.0)
    cu = nb.math('ADD', nb.math('DIVIDE', ur, streak), nb.math('MULTIPLY', t, 0.004))
    cv = nb.math('ADD', vr, nb.math('MULTIPLY', t, 0.0015))
    cvec = nb.xyz(nb.math('MULTIPLY', cu, 0.9), nb.math('MULTIPLY', cv, 0.9), nb.math('MULTIPLY', t, 0.002))
    n1 = nb.noise(cvec, scale=1.0, detail=5.0, roughness=0.52)
    thr = nb.math('SUBTRACT', 0.66, nb.math('MULTIPLY', _vf(nb, "cloud_cover"), 0.38))
    dens = nb.map_range(n1['Fac'], nb.math('SUBTRACT', thr, 0.06), nb.math('ADD', thr, 0.16), 0.0, 1.0, clamp=True,
                        interp='SMOOTHSTEP')
    dens = nb.math('MULTIPLY', dens, _smooth(nb, e, 0.004, 0.05))
    thin = nb.math('SUBTRACT', 1.0, nb.map_range(n1['Fac'], thr, nb.math('ADD', thr, 0.34), 0.0, 1.0,
                                                   clamp=True, interp='SMOOTHSTEP'))
    litf = nb.math('ADD', nb.math('MULTIPLY', _powpos(nb, mu, 3.0), 0.85), nb.math('MULTIPLY', thin, 0.55))
    litf = nb.math('MINIMUM', nb.math('MULTIPLY', litf, nb.math('ADD', 0.35, nb.math(
        'MULTIPLY', 0.65, nb.math('POWER', nb.math('SUBTRACT', 1.0, ec), 3.0)))), 1.0)
    ccol = nb.mix(litf, _vc(nb, "cloud_dark"), _vc(nb, "cloud_lit"), 'RGBA')
    # lightning inside the clouds: undersides light up (regional variation from a second noise)
    n2 = nb.noise(nb.vmath('SCALE', cvec, scale=0.35), scale=1.0, detail=2.0, roughness=0.5)
    fdir = _sun_dir(nb, _vf(nb, "flash_az"), _vf(nb, "flash_el"))
    flobe = nb.math('ADD', 0.12, nb.math('MULTIPLY', 0.88, _powpos(nb, nb.vmath('DOT_PRODUCT', d, fdir), 4.0)))
    fl = nb.math('MULTIPLY', nb.math('MULTIPLY', _vf(nb, "flash"), flobe),
                 nb.math('ADD', 0.08, nb.math('MULTIPLY', 9.0, _powpos(nb, nb.math('SUBTRACT', n2['Fac'], 0.42), 1.6))))
    ccol = nb.vmath('ADD', ccol, _cmul(nb, _vc(nb, "flash_col"), nb.math('MULTIPLY', fl, nb.math('ADD', thin, 0.4))))
    calpha = nb.math('MULTIPLY', dens, _vf(nb, "cloud_alpha"))
    col = nb.vmath('ADD', col, _cmul(nb, (1.0, 1.0, 1.0), nb.math('MULTIPLY', star, nb.math('SUBTRACT', 1.0, calpha))))
    col = nb.mix(calpha, col, ccol, 'RGBA')
    # ---- storm billows (cloud_billow): a LOWER, heavy, turbulent cloud mass (unstreaked, high contrast) whose
    # undersides light up around the flash azimuth (Act III cloud-underside glow behind the silhouettes)
    uvb = nb.math('ADD', ec, 0.12)
    ub = nb.math('DIVIDE', sd['X'], uvb)
    vb = nb.math('DIVIDE', sd['Y'], uvb)
    bvec = nb.xyz(nb.math('ADD', nb.math('MULTIPLY', ub, 0.62), nb.math('MULTIPLY', t, 0.006)),
                  nb.math('ADD', nb.math('MULTIPLY', vb, 0.62), nb.math('MULTIPLY', t, 0.002)),
                  nb.math('MULTIPLY', t, 0.003))
    b1 = nb.noise(bvec, scale=1.0, detail=4.0, roughness=0.62)
    b2 = nb.noise(nb.vmath('ADD', nb.vmath('SCALE', bvec, scale=2.3), (5.1, 2.7, 0.0)), scale=1.0, detail=3.0,
                  roughness=0.55)
    bden = nb.math('MULTIPLY', nb.map_range(b1['Fac'], 0.40, 0.60, 0.0, 1.0, clamp=True, interp='SMOOTHSTEP'),
                   nb.math('MULTIPLY', _smooth(nb, e, 0.0, 0.06), _vf(nb, "cloud_billow")))
    bshade = nb.map_range(b2['Fac'], 0.35, 0.75, 0.0, 1.0, clamp=True, interp='SMOOTHSTEP')
    blit = nb.math('MINIMUM', nb.math('ADD', nb.math('MULTIPLY', bshade, 0.5), nb.math('MULTIPLY', _powpos(nb, mu, 2.0),
                                                                                     0.3)), 1.0)
    bcol = nb.mix(blit, _vc(nb, "cloud_dark"), _vc(nb, "cloud_lit"), 'RGBA')
    bfl = nb.math('MULTIPLY', nb.math('MULTIPLY', _vf(nb, "flash"), flobe),
                  nb.math('ADD', 0.4, nb.math('MULTIPLY', nb.math('SUBTRACT', 1.0, bshade), 2.5)))
    bcol = nb.vmath('ADD', bcol, _cmul(nb, _vc(nb, "flash_col"), bfl))
    col = nb.mix(bden, col, bcol, 'RGBA')
    # flash also lifts the whole sky a little
    col = nb.vmath('ADD', col, _cmul(nb, _vc(nb, "flash_col"), nb.math('MULTIPLY', nb.math(
        'MULTIPLY', _vf(nb, "flash"), flobe), 0.05)))
    # ---- lighting rays: ambient (sky-dome shaped) + flash
    up = nb.math('ADD', 0.45, nb.math('MULTIPLY', 0.55, _smooth(nb, e, -0.3, 0.7)))
    amb = _cmul(nb, _vc(nb, "amb_col"), nb.math('MULTIPLY', _vf(nb, "amb_str"), up))
    amb = nb.vmath('ADD', amb, _cmul(nb, _vc(nb, "flash_col"), nb.math('MULTIPLY', _vf(nb, "flash"), FLASH_AMB)))
    lp = nb.n('ShaderNodeLightPath')
    final = nb.mix(lp['Is Camera Ray'], amb, col, 'RGBA')
    bg = nb.n('ShaderNodeBackground', final, 1.0)
    nb.link(bg, out.inp('Surface'))
    _drive_fx(w)
    return w


# ================================================================================================ lights
def _sun_lamp(name, shadow, energy=1.0, angle_deg=1.0, parent=None):
    ob = bpy.data.objects.get(name)
    if ob is None:
        la = bpy.data.lights.new(name, 'SUN')
        ob = U.new_object(name, la, COLL)
    la = ob.data
    la.energy = energy
    la.use_shadow = shadow
    la.angle = math.radians(angle_deg)
    if parent is not None:
        ob.parent = parent
    ob.rotation_mode = 'XYZ'
    return ob


def _lamp_rot(az_deg, el_deg):
    """Euler for a sun lamp whose light travels FROM direction (az, el) (lamp -Z = -sun_dir)."""
    return (math.radians(90.0 - el_deg), 0.0, math.radians(180.0 - az_deg))


def _build_lights(sc):
    """ENV_sun_pivot (rotated by set_sun) carrying ENV_key (sun/moon, shadows) + the shadow decks; ENV_fill (no
    shadow), ENV_bounce (glow from below, no shadow), ENV_flash (lightning, shadows, hidden unless flashing)."""
    piv = bpy.data.objects.get(N_PIVOT) or U.new_empty(N_PIVOT, (0, 0, 0), COLL, 'SINGLE_ARROW', 5.0)
    piv.rotation_mode = 'XYZ'
    key = _sun_lamp(N_KEY, True, 4.0, 1.2, parent=piv)
    key.location = (0, 0, 0)
    key.rotation_euler = (0, 0, 0)
    key.data.shadow_maximum_resolution = 0.02
    fill = _sun_lamp(N_FILL, False, 0.25, 30.0)
    bounce = _sun_lamp(N_BOUNCE, False, 0.1, 40.0)
    bounce.rotation_euler = (math.pi, 0.0, 0.0)          # shines straight up
    fl = _sun_lamp(N_FLASH, True, 0.0, 3.0)
    fl.rotation_euler = _lamp_rot(FLASH_AZ_FALLBACK, FLASH_EL)
    fl.data.color = FLASH_TINT
    for ob in (key, fill, bounce):
        ob.data.volume_factor = 1.0
    key.data.volume_factor = KEY_VOLUME
    fl.data.volume_factor = FLASH_VOLUME
    fl.hide_render = True
    fl.hide_viewport = True
    gobo = _build_gobo(piv)
    return dict(key=key, fill=fill, bounce=bounce, flash=fl, pivot=piv, gobo=gobo)


def _driver(owner, path, index, expr, variables):
    """SCRIPTED driver with a SIMPLE expression (evaluated natively, no Python auto-exec needed).
    variables: {name: (id_type, id, data_path)}."""
    fc = owner.driver_add(path, index) if index is not None and index >= 0 else owner.driver_add(path)
    d = fc.driver
    d.type = 'SCRIPTED'
    while d.variables:
        d.variables.remove(d.variables[0])
    for nm, (idt, idb, dp) in variables.items():
        v = d.variables.new()
        v.name = nm
        v.type = 'SINGLE_PROP'
        v.targets[0].id_type = idt
        v.targets[0].id = idb
        v.targets[0].data_path = dp
    d.expression = expr
    for m in list(fc.modifiers):
        fc.modifiers.remove(m)
    if not d.is_simple_expression:
        raise RuntimeError(f"driver expression is not simple: {expr!r}")
    return fc


def _wvars(w, *names):
    return {n: ('WORLD', w, f'["env_{n}"]') for n in names}


def _shadow_caster(name, verts, faces):
    ob = bpy.data.objects.get(name)
    if ob is None:
        ob = U.mesh_from_data(name, verts, faces=faces, collection=COLL)
    for attr in ("visible_camera", "visible_diffuse", "visible_glossy", "visible_transmission",
                 "visible_volume_scatter"):
        setattr(ob, attr, False)
    ob.visible_shadow = True
    ob.hide_select = True
    ob.display_type = 'WIRE'
    ob.color = (0, 0, 0, 1)
    return ob


def _build_gobo(piv):
    """Opaque shadow decks that shape the key light on the ground (cheap in the virtual shadow map, unlike an
    alpha-hashed gobo which measured +5 s/frame at 8 spp):
      ENV_shadow_edge  - a huge horizontal plane EDGE_H m up whose edge line casts the moving light edge of
                         set_cloud_shadow(edge=...) (S27 moonlight sweep); dark side = ground with g.dir < edge.
      ENV_cloud_deck   - horizontal cloud blobs CLOUD_H m up drifting downwind on fx_time; their size follows
                         env_gobo_cover through a shape key.
    Both are world-space and positioned by simple-expression drivers from env_sun_az / env_sun_el so the pattern
    stays anchored on the ground whatever set_sun cheat a shot uses."""
    w = _world()
    L = 4000.0
    edge = _shadow_caster(N_GOBO, [(-L, -L, 0), (0, -L, 0), (0, L, 0), (-L, L, 0)], [(0, 1, 2, 3)])
    kel = f"max(el, {KEY_MIN_EL})"
    v = _wvars(w, "sun_az", "sun_el", "edge_pos", "edge_dir", "edge_on")
    v = {"az": v["sun_az"], "el": v["sun_el"], "e": v["edge_pos"], "ed": v["edge_dir"], "on": v["edge_on"]}
    H = EDGE_H
    _driver(edge, "location", 0, f"e * sin(radians(ed)) + {H} * sin(radians(az)) / tan(radians({kel}))", v)
    _driver(edge, "location", 1, f"e * cos(radians(ed)) + {H} * cos(radians(az)) / tan(radians({kel}))", v)
    _driver(edge, "location", 2, f"{H} if on > 0.5 else -3000.0", v)
    _driver(edge, "rotation_euler", 2, "radians(90.0 - ed)", v)
    # cloud blobs
    rng = _rng("cloud_deck")
    verts, faces = [], []
    centers = []
    for i in range(70):
        cx, cy = rng.uniform(-1700, 1700), rng.uniform(-1700, 1700)
        rad = rng.uniform(22, 95)
        el_ = rng.uniform(1.3, 2.6)
        rot = rng.uniform(0, math.pi)
        k = 14
        base = len(verts)
        for j in range(k):
            a = 2 * math.pi * j / k
            rr = rad * (1.0 + 0.28 * math.sin(3 * a + i) + 0.12 * math.sin(7 * a + 2 * i))
            x, y = rr * math.cos(a) * el_, rr * math.sin(a)
            verts.append((cx + x * math.cos(rot) - y * math.sin(rot), cy + x * math.sin(rot) + y * math.cos(rot), 0.0))
            centers.append((cx, cy, 0.0))
        faces.append(tuple(range(base, base + k)))
    deck = _shadow_caster("ENV_cloud_deck", verts, faces)
    if deck.data.shape_keys is None:
        deck.shape_key_add(name="Basis")
        sk = deck.shape_key_add(name="gone")
        sk.data.foreach_set("co", np.array(centers, dtype=np.float32).ravel())
    sc = bpy.context.scene
    vv = _wvars(w, "sun_az", "sun_el", "wind_dir", "gobo_cover")
    vv = {"az": vv["sun_az"], "el": vv["sun_el"], "wd": vv["wind_dir"], "c": vv["gobo_cover"],
          "t": ('SCENE', sc, '["fx_time"]')}
    Hc = CLOUD_H
    _driver(deck, "location", 0, f"{Hc} * sin(radians(az)) / tan(radians({kel})) + sin(radians(wd)) * t * 2.2", vv)
    _driver(deck, "location", 1, f"{Hc} * cos(radians(az)) / tan(radians({kel})) + cos(radians(wd)) * t * 2.2", vv)
    _driver(deck, "location", 2, f"{Hc} if c > 0.01 else -3000.0", vv)
    _driver(deck.data.shape_keys.key_blocks["gone"], "value", -1, "1.0 - min(c * 2.5, 1.0)", vv)
    return edge


EDGE_H = 60.0
CLOUD_H = 110.0


HAZE_TIGHT = 0.25            # fraction of the tight sun glow used as aerial-haze colour (keeps silhouettes)


# ================================================================================================ fog box
def _build_fog(sc):
    """ENV_fog: mesh box (FOG_HALF x FOG_HALF x FOG_TOP) with a Principled Volume: density fog_den with exponential
    height falloff (fog_height) and slow fx-time noise (fog_noise), colour fog_col, anisotropy fog_aniso,
    emission fog_emit. Never a world volume (rule 6); visible_shadow False."""
    ob = bpy.data.objects.get(N_FOG)
    if ob is None:
        h, z0, z1 = FOG_HALF, -3.0, FOG_TOP
        v = [(-h, -h, z0), (h, -h, z0), (h, h, z0), (-h, h, z0), (-h, -h, z1), (h, -h, z1), (h, h, z1), (-h, h, z1)]
        f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        ob = U.mesh_from_data(N_FOG, v, faces=f, collection=COLL)
    mat = bpy.data.materials.get("ENV_fog_mat") or bpy.data.materials.new("ENV_fog_mat")
    nt = mat.node_tree
    nt.nodes.clear()
    nb = U.NB(nt, group_io=False)
    out = nb.n('ShaderNodeOutputMaterial')
    geo = nb.n('ShaderNodeNewGeometry')
    p = geo['Position']
    z = nb.math('MAXIMUM', nb.sep(p)['Z'], 0.0)
    hf = nb.math('EXPONENT', nb.math('DIVIDE', nb.math('MULTIPLY', z, -1.0),
                                     nb.math('MAXIMUM', _vf(nb, "fog_height"), 0.5)))
    t = _fx_value(nb)
    q = nb.vmath('ADD', nb.vmath('MULTIPLY', p, (0.018, 0.018, 0.05)), nb.xyz(nb.math('MULTIPLY', t, 0.03),
                                                                           nb.math('MULTIPLY', t, 0.012), 0.0))
    nz = nb.noise(q, scale=1.0, detail=3.0, roughness=0.5)
    var = nb.math('ADD', 1.0, nb.math('MULTIPLY', nb.math('SUBTRACT', nz['Fac'], 0.5),
                                      nb.math('MULTIPLY', _vf(nb, "fog_noise"), 2.4)))
    den = nb.math('MULTIPLY', nb.math('MULTIPLY', _vf(nb, "fog_den"), hf), nb.math('MAXIMUM', var, 0.0))
    vol = nb.n('ShaderNodeVolumePrincipled', Color=_vc(nb, "fog_col"), Density=den, Anisotropy=_vf(nb, "fog_aniso"),
               Emission_Color=_vc(nb, "fog_emit"), Emission_Strength=1.0)
    nb.link(vol, out.inp('Volume'))
    mat.diffuse_color = (0.8, 0.7, 0.6, 0.05)
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    ob.visible_shadow = False
    ob.display_type = 'BOUNDS'
    ob.hide_select = True
    ob.color = (0.8, 0.7, 0.6, 0.0)
    _drive_fx(mat)
    return ob


FOG_HALF = 320.0
FOG_TOP = 70.0


# ================================================================================================ terrain
def _fbm2(x, y, seed, octaves=4, freq=1.0, gain=0.5):
    """Deterministic smooth 2-D fBm in [-1, 1] (sum of randomly oriented sines; numpy, no hash())."""
    rng = _rng("fbm", seed)
    out = np.zeros_like(np.asarray(x, dtype=float))
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        for _ in range(3):
            a = rng.uniform(0, 2 * math.pi)
            ph = rng.uniform(0, 2 * math.pi)
            k = freq * (2.0 ** o) * rng.uniform(0.8, 1.25)
            out += amp * np.sin((np.cos(a) * x + np.sin(a) * y) * k + ph)
            tot += amp
        amp *= gain
    return out / tot


def west_weight(az_deg):
    """1 inside the dusk sky sector WEST_SECTOR (compass az), smooth 0 outside (numpy or float)."""
    a0, a1, rp = WEST_SECTOR
    az = np.mod(np.asarray(az_deg, dtype=float), 360.0)
    u = np.clip((az - (a0 - rp)) / rp, 0.0, 1.0) * np.clip(((a1 + rp) - az) / rp, 0.0, 1.0)
    return u * u * (3 - 2 * u)


def terrain_height(x, y):
    """Ground height (m) at world x, y (numpy arrays or floats): exactly 0 inside the arena (r < ARENA_R), gentle
    undulation beyond, the low rise under the pine (PINE_RISE at config.PINE_POS), rolling far field (flattened
    over the dusk sky sector WEST_SECTOR so the sunset disk meets a flat grass horizon)."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    r = np.hypot(x, y)
    ramp = np.clip((r - ARENA_R) / 30.0, 0.0, 1.0)
    ramp = ramp * ramp * (3 - 2 * ramp)
    px, py = config.PINE_POS
    dp2 = (x - px) ** 2 + (y - py) ** 2
    rise = PINE_RISE * np.exp(-dp2 / (2 * 8.0 ** 2)) * np.clip((r - ARENA_R) / 4.0, 0.0, 1.0)
    near = 0.55 * _fbm2(x, y, "near", 3, 1.0 / 22.0)
    far_amp = np.clip((r - 120.0) / 900.0, 0.0, 1.0)
    far = (2.5 + 14.0 * far_amp) * _fbm2(x, y, "far", 4, 1.0 / 260.0)
    far = far * (1.0 - 0.9 * west_weight(np.degrees(np.arctan2(x, y))))   # flat grass horizon under the dusk sky
    und = (near + np.clip((r - 60.0) / 200.0, 0.0, 1.0) * far)
    und = und * (1.0 - np.exp(-dp2 / (2 * 10.0 ** 2)))          # keep the rise clean
    h = ramp * und + rise
    return np.where(r < ARENA_R, 0.0, h)


# boulders: (x, y, radius m, height factor, seed) - outside the arena, around the pine rise and in the field
ROCKS = [(-17.5, 6.0, 1.1, 0.55, "r0"), (19.0, -9.5, 0.8, 0.7, "r1"), (16.5, 15.0, 1.4, 0.45, "r2"),
         (10.2, 27.0, 1.0, 0.6, "r3"), (2.4, 33.5, 1.3, 0.5, "r4"), (8.8, 34.2, 0.7, 0.8, "r5"),
         (-41.0, 26.0, 2.2, 0.45, "r6"), (36.0, -31.0, 1.8, 0.5, "r7"), (-29.0, -46.0, 2.6, 0.4, "r8")]
PINE_CLEAR = 1.1             # no grass within this radius of the trunk


def grass_mask(x, y):
    """1 where grass may grow, 0 under rocks / at the pine trunk (terrain point attribute 'gmask')."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    m = np.ones_like(x)
    for rx, ry, rad, _, _ in ROCKS + [(config.PINE_POS[0], config.PINE_POS[1], PINE_CLEAR, 0, "pine")]:
        d = np.hypot(x - rx, y - ry)
        u = np.clip((d - rad * 0.85) / (rad * 0.35 + 0.2), 0.0, 1.0)
        m *= u * u * (3 - 2 * u)
    return m


def _terrain_rings():
    rings = [0.0] + [float(r) for r in range(2, 15, 2)] + [float(r) for r in range(15, 61)]
    r = 60.0
    while r < TERRAIN_R:
        r *= 1.06
        rings.append(min(r, TERRAIN_R))
    return np.array(rings)


def _build_terrain(sc):
    """ENV_terrain: radial mesh to TERRAIN_R (256 segments), heights from terrain_height. Material ENV_ground:
    dark litter near the arena, grass-sea colour with drifting wind-wave sheen in the far field (where instances
    thin out), wetness, aerial perspective."""
    ob = bpy.data.objects.get(N_TERRAIN)
    if ob is not None:
        return ob
    rings = _terrain_rings()
    seg = 256
    ang = np.linspace(0, 2 * math.pi, seg, endpoint=False)
    verts = [(0.0, 0.0, 0.0)]
    for r in rings[1:]:
        x, y = r * np.cos(ang), r * np.sin(ang)
        z = terrain_height(x, y)
        verts.extend(zip(x.tolist(), y.tolist(), z.tolist()))
    faces = []
    for j in range(seg):
        faces.append((0, 1 + j, 1 + (j + 1) % seg))
    for i in range(1, len(rings) - 1):
        a0 = 1 + (i - 1) * seg
        b0 = 1 + i * seg
        for j in range(seg):
            j1 = (j + 1) % seg
            faces.append((a0 + j, b0 + j, b0 + j1, a0 + j1))
    ob = U.mesh_from_data(N_TERRAIN, verts, faces=faces, collection=COLL, smooth=True)
    vv = np.array(verts)
    U.add_attribute(ob.data, "gmask", grass_mask(vv[:, 0], vv[:, 1]).astype(np.float32))
    ob.data.materials.append(_ground_material())
    ob.color = (0.45, 0.33, 0.18, 1.0)
    return ob


def _gust_shader(nb, pos, t):
    """Travelling gust bands (0..1) in a shader: the same formula as the grass GN (_gust_gn) on the WIND CLOCK
    (fx time t with the freeze window env_freeze_t0 .. env_freeze_t1 removed), heading env_wind_dir."""
    tw = nb.math('ADD', nb.math('MINIMUM', t, _vf(nb, "freeze_t0")),
                 nb.math('MAXIMUM', nb.math('SUBTRACT', t, _vf(nb, "freeze_t1")), 0.0))
    hd = nb.math('RADIANS', _vf(nb, "wind_dir"))
    wx, wy = nb.math('SINE', hd), nb.math('COSINE', hd)
    sp = nb.sep(pos)
    along = nb.math('ADD', nb.math('MULTIPLY', sp['X'], wx), nb.math('MULTIPLY', sp['Y'], wy))
    across = nb.math('SUBTRACT', nb.math('MULTIPLY', sp['X'], wy), nb.math('MULTIPLY', sp['Y'], wx))
    s = nb.math('SUBTRACT', along, nb.math('MULTIPLY', tw, GUST_SPEED))
    warp = nb.noise(nb.xyz(nb.math('DIVIDE', across, GUST_ACROSS), nb.math('DIVIDE', s, GUST_WAVE * 2.2),
                           nb.math('MULTIPLY', tw, 0.03)), scale=1.0, detail=1.0, roughness=0.5)
    band = nb.math('SINE', nb.math('ADD', nb.math('MULTIPLY', s, 2 * math.pi / GUST_WAVE),
                                   nb.math('MULTIPLY', warp['Fac'], 5.0)))
    env = nb.noise(nb.xyz(nb.math('DIVIDE', across, GUST_ACROSS * 0.6),
                          nb.math('ADD', nb.math('DIVIDE', s, GUST_WAVE * 1.7), 17.3), 0.37),
                   scale=1.0, detail=1.0, roughness=0.5)
    envm = nb.map_range(env['Fac'], 0.35, 0.65, 0.2, 1.0, clamp=True)
    return nb.math('MULTIPLY', nb.map_range(band, -0.4, 0.9, 0.0, 1.0, clamp=True, interp='SMOOTHSTEP'), envm)


def _ground_material():
    _, aer = _groups()
    mat = bpy.data.materials.get("ENV_ground") or bpy.data.materials.new("ENV_ground")
    nt = mat.node_tree
    nt.nodes.clear()
    nb = U.NB(nt, group_io=False)
    out = nb.n('ShaderNodeOutputMaterial')
    geo = nb.n('ShaderNodeNewGeometry')
    p = geo['Position']
    sp = nb.sep(p)
    r = nb.vmath('LENGTH', nb.xyz(sp['X'], sp['Y'], 0.0))
    t = _fx_value(nb)
    far = _smooth(nb, r, 45.0, 160.0)
    n1 = nb.noise(nb.vmath('MULTIPLY', p, (0.9, 0.9, 0.9)), scale=1.0, detail=4.0, roughness=0.6)
    n2 = nb.noise(nb.vmath('MULTIPLY', p, (0.035, 0.012, 0.03)), scale=1.0, detail=3.0, roughness=0.55)
    # near ground = dry litter (fallen blades): streaky straw strokes over the soil tone, so ground revealed by
    # parting / clearance reads as flattened grass, not as dark holes
    ls = nb.noise(nb.vmath('MULTIPLY', p, (7.0, 1.3, 1.0)), scale=1.0, detail=3.0, roughness=0.6)
    ls2 = nb.noise(nb.vmath('MULTIPLY', p, (1.2, 6.5, 1.0)), scale=1.0, detail=3.0, roughness=0.6)
    straws = nb.math('MAXIMUM', _smooth(nb, ls['Fac'], 0.52, 0.66), _smooth(nb, ls2['Fac'], 0.54, 0.68))
    near_col = _cmul(nb, _vc(nb, "ground_near"), nb.math('ADD', 0.55, nb.math('MULTIPLY', n1['Fac'], 0.6)))
    near_col = nb.mix(nb.math('MULTIPLY', straws, 0.55), near_col, _cmul(nb, _vc(nb, "grass_plume"), 0.30), 'RGBA')
    streak = nb.math('ADD', 0.55, nb.math('MULTIPLY', n2['Fac'], 0.9))
    g = _gust_shader(nb, p, t)
    sheen = nb.math('ADD', streak, nb.math('MULTIPLY', nb.math('SUBTRACT', g, 0.4), nb.math(
        'MULTIPLY', _vf(nb, "grass_sheen"), nb.math('MULTIPLY', _vf(nb, "wind"), 0.8))))
    far_col = _cmul(nb, _vc(nb, "ground_far"), sheen)
    col = nb.mix(far, near_col, far_col, 'RGBA')
    wet = _vf(nb, "wet")
    col = _cmul(nb, col, nb.math('SUBTRACT', 1.0, nb.math('MULTIPLY', wet, 0.45)))
    rough = nb.math('SUBTRACT', 1.0, nb.math('MULTIPLY', wet, 0.42))
    bsdf = nb.n('ShaderNodeBsdfPrincipled', Base_Color=col, Roughness=rough,
                Specular_IOR_Level=nb.math('MULTIPLY', wet, 0.3))
    ae = _group_node(nb, aer, bsdf, 1.0)
    nb.link(ae, out.inp('Surface'))
    mat.diffuse_color = (0.45, 0.33, 0.18, 1.0)
    _drive_fx(mat)
    return mat


# ================================================================================================ far layers
MOUNTAINS = [   # (distance m, base height m, relief m, feature scale (cycles/turn), sharpness 0..1, seed)
    (340.0, 7.0, 12.0, 9.0, 0.0, "m0"),   # (the western arc is lowered: the dusk sun sets over low hills)
    (680.0, 16.0, 30.0, 7.0, 0.25, "m1"),
    (1350.0, 38.0, 72.0, 5.0, 0.55, "m2"),
    # the tallest range sits inside the cameras' default clip_end (cameras.shot clip 2000 m, camera up to ~60 m off
    # centre): 1800 m with its heights scaled by 1800/2700 keeps the angular size of the original 2700 m design
    (1800.0, 60.0, 126.7, 4.0, 0.8, "m3"),
]
FAR_CLIP_REF = config.CAMERA_CLIP[1]   # cameras.shot / bl_util.new_camera default clip_end; every visible ENV vertex < 0.93 x
SUNSET_AZ = 270.0            # the far ranges are low around this bearing (dusk sun between the figures, S05)
PAGODA_AZ = 27.0             # compass bearing of the pagoda hill (behind the pine as seen from the south)
PAGODA_LAYER = 1
# Sun-following sunset gap (GN_ENV_ridge on every ENV_mtn_*): within NOTCH_HALF deg of the sun/moon azimuth every
# ridge is pulled down to <= NOTCH_EL deg above the eye-level horizon, ramping back to full height at
# NOTCH_HALF + NOTCH_RAMP; the gap closes when the disk is high (NOTCH_FADE: full below el0, none above el1).
NOTCH_HALF = 12.0
NOTCH_RAMP = 10.0
NOTCH_EL = 0.10
NOTCH_FADE = (6.0, 10.0)
NOTCH_EYE_Z = 2.0            # reference eye height of the notch floor (S05 axis camera z = 2.10)
# the far terrain undulation is flattened over the dusk sky sector (static) so the grass sea meets the sunset flat
WEST_SECTOR = (238.0, 342.0, 14.0)   # compass az from, to, ramp (deg)


def _ridge_profile(theta, spec):
    """Ridge height (m) along the ring angle theta (radians, 0 = +X counter-clockwise) for one mountain layer."""
    dist, base, relief, scale, sharp, seed = spec
    rng = _rng("ridge", seed)
    h = np.zeros_like(theta)
    tot = 0.0
    for o in range(5):
        k = max(1, int(round(scale * (2 ** o) * rng.uniform(0.85, 1.2))))
        amp = 0.55 ** o
        for _ in range(2):
            ph = rng.uniform(0, 2 * math.pi)
            h += amp * np.sin(k * theta + ph)
            tot += amp
    h = h / tot                                   # ~[-1, 1]
    ridged = 1.0 - np.abs(h)                      # sharp crests
    soft = 0.5 * (h + 1.0)
    prof = (1.0 - sharp) * soft + sharp * ridged ** 1.6
    az = (90.0 - np.degrees(theta)) % 360.0
    dwest = np.abs(((az - SUNSET_AZ) + 180.0) % 360.0 - 180.0)
    low = np.clip((dwest - 8.0) / 42.0, 0.0, 1.0)
    low = low * low * (3 - 2 * low)
    k = 0.25 + 0.75 * low if spec is not MOUNTAINS[-1] else 0.22 + 0.78 * low
    out = (base + relief * prof) * k
    if spec is MOUNTAINS[PAGODA_LAYER]:           # a gentle hill for the pagoda
        th0 = math.radians(90.0 - PAGODA_AZ)
        dth = np.angle(np.exp(1j * (theta - th0)))
        out = out + 14.0 * np.exp(-(dth / 0.035) ** 2)
    return out


def _smoothstep(e0, e1, x):
    """numpy smoothstep identical to GN/shader Map Range SMOOTHSTEP from e0 -> e1 (e0 > e1 allowed: inverted)."""
    t = np.clip((np.asarray(x, dtype=float) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _notch_floor(dist):
    """Ridge height (m) of the sunset-gap floor for a ring at `dist` m: NOTCH_EL deg above a NOTCH_EYE_Z eye."""
    return NOTCH_EYE_Z + dist * math.tan(math.radians(NOTCH_EL))


def _notch_weight(az_deg, sun_az_deg, sun_el_deg):
    """0..1 strength of the sun-following gap at compass bearing az_deg (numpy mirror of GN_ENV_ridge)."""
    d = np.abs(np.mod(np.asarray(az_deg, dtype=float) - sun_az_deg + 540.0, 360.0) - 180.0)
    return _smoothstep(NOTCH_HALF + NOTCH_RAMP, NOTCH_HALF, d) * \
        float(_smoothstep(NOTCH_FADE[1], NOTCH_FADE[0], sun_el_deg))


_PROF_RANGE = {}


def _prof01(spec, top_at):
    """Normalised (0..1) crest profile of a ring, using the ring's full-circle min/max (cached)."""
    key = spec[5]
    if key not in _PROF_RANGE:
        full = _ridge_profile(np.linspace(0, 2 * math.pi, 1440, endpoint=False), spec)
        _PROF_RANGE[key] = (float(full.min()), float(full.max()))
    lo, hi = _PROF_RANGE[key]
    return np.clip((np.asarray(top_at, dtype=float) - lo) / max(hi - lo, 1e-6), 0.0, 1.0)


def ridge_elevation(az_deg, sun_az_deg=None, sun_el_deg=0.0, eye=(0.0, 0.0, NOTCH_EYE_Z)):
    """Skyline elevation (degrees above the eye's horizontal) toward compass bearing az_deg (0 = +Y, 90 = +X) as seen
    from `eye` (x, y, z in m): the highest point of the terrain along that ray and of every mountain ring, with the
    sun-following sunset gap for a sun/moon at (sun_az_deg, sun_el_deg). sun_az_deg=None means the disk itself sits
    on this bearing (the usual question: 'how low may a disk centred at az_deg go?'): a disk of diameter D deg is
    fully clear when el - D/2 >= ridge_elevation(az). Grass tops are ignored (they only cover the near field).
    Accepts a float or an array of bearings; returns the same shape."""
    az_arr = np.atleast_1d(np.asarray(az_deg, dtype=float))
    ex, ey, ez = float(eye[0]), float(eye[1]), float(eye[2])
    out = np.empty(az_arr.shape)
    ts = np.geomspace(20.0, TERRAIN_R * 1.2, 500)
    for k, az in enumerate(az_arr):
        saz = az if sun_az_deg is None else float(sun_az_deg)
        dx, dy = math.sin(math.radians(az)), math.cos(math.radians(az))
        best = -90.0
        # terrain samples inside the terrain disk
        px, py = ex + ts * dx, ey + ts * dy
        inside = np.hypot(px, py) < TERRAIN_R
        if inside.any():
            h = terrain_height(px[inside], py[inside])
            best = max(best, float(np.degrees(np.arctan2(h - ez, ts[inside])).max()))
        for spec in MOUNTAINS:
            R = spec[0]
            b = ex * dx + ey * dy
            c = ex * ex + ey * ey - R * R
            t = -b + math.sqrt(max(b * b - c, 0.0))
            qx, qy = ex + t * dx, ey + t * dy
            th = np.array([math.atan2(qy, qx)])
            top = _ridge_profile(th, spec)
            w = _notch_weight(90.0 - math.degrees(th[0]), saz, sun_el_deg)
            floor = _notch_floor(R) * (0.55 + 0.45 * _prof01(spec, top))
            top = top - w * np.maximum(top - floor, 0.0)
            best = max(best, math.degrees(math.atan2(float(top[0]) - ez, t)))
        out[k] = best
    return float(out[0]) if np.ndim(az_deg) == 0 else out.reshape(np.shape(az_deg))


def _ridge_tree():
    """GN_ENV_ridge: sun-following sunset gap on a mountain ring. The sun/moon direction comes from the rotation of
    ENV_sun_pivot (Object Info; set_sun keys it), so the gap follows every per-shot cheat without drivers. Crest
    vertices (attribute h01 = 1) within NOTCH_HALF deg of the sun azimuth are pulled down to Floor x (0.55 + 0.45 x
    prof) (prof = normalised crest height: the gap keeps a low, ridge-shaped relief), ramping back over NOTCH_RAMP
    deg; the gap closes for a high disk (NOTCH_FADE)."""
    ng = bpy.data.node_groups.get("GN_ENV_ridge")
    if ng is not None:
        return ng
    ng = U.gn_new_tree("GN_ENV_ridge", inputs=[("Pivot", "OBJECT"), ("Floor", "FLOAT", 3.0)])
    nb = U.NB(ng)
    gi = nb.gi
    p = nb.sep(nb.n('GeometryNodeInputPosition')['Position'])
    az = nb.math('DEGREES', nb.math('ARCTAN2', p['X'], p['Y']))
    poi = nb.n('GeometryNodeObjectInfo', gi['Pivot'], transform_space='ORIGINAL')
    s = nb.sep(nb.n('FunctionNodeRotateVector', (0.0, 0.0, 1.0), poi['Rotation']))
    saz = nb.math('DEGREES', nb.math('ARCTAN2', s['X'], s['Y']))
    sel = nb.math('DEGREES', nb.math('ARCSINE', nb.math('MINIMUM', nb.math('MAXIMUM', s['Z'], -1.0), 1.0)))
    d = nb.math('ABSOLUTE', nb.math('SUBTRACT', nb.math('FLOORED_MODULO', nb.math(
        'ADD', nb.math('SUBTRACT', az, saz), 540.0), 360.0), 180.0))
    w = nb.map_range(d, NOTCH_HALF, NOTCH_HALF + NOTCH_RAMP, 1.0, 0.0, clamp=True, interp='SMOOTHSTEP')
    fade = nb.map_range(sel, NOTCH_FADE[0], NOTCH_FADE[1], 1.0, 0.0, clamp=True, interp='SMOOTHSTEP')
    w = nb.math('MULTIPLY', nb.math('MULTIPLY', w, fade), nb.attr("h01"))
    floor = nb.math('MULTIPLY', gi['Floor'], nb.math('ADD', 0.55, nb.math('MULTIPLY', nb.attr("prof"), 0.45)))
    drop = nb.math('MULTIPLY', w, nb.math('MAXIMUM', nb.math('SUBTRACT', p['Z'], floor), 0.0))
    moved = nb.n('GeometryNodeSetPosition', gi['Geometry'], Offset=nb.xyz(0.0, 0.0, nb.math('MULTIPLY', drop, -1.0)))
    nb.link(moved, nb.go['Geometry'])
    nb.layout()
    return ng


def _build_far(sc):
    """Layered mountain silhouettes (4 rings, ENV_mtn_0..3) with atmospheric perspective + the original five-tier
    pagoda silhouette (ENV_pagoda) on a hill of layer 1. Unlit emission (painterly flat layers) through the
    aerial-perspective group; a mesh attribute 'h01' (0 at the base, 1 at the crest) adds valley mist. Every ring
    carries GN_ENV_ridge (sun-following sunset gap, see ridge_elevation)."""
    _, aer = _groups()
    out = {}
    seg = 1440
    theta = np.linspace(0, 2 * math.pi, seg, endpoint=False)
    for i, spec in enumerate(MOUNTAINS):
        name = f"ENV_mtn_{i}"
        if bpy.data.objects.get(name) is not None:
            out[name] = bpy.data.objects[name]
            continue
        dist = spec[0]
        top = _ridge_profile(theta, spec)
        zb = -40.0
        x, y = dist * np.cos(theta), dist * np.sin(theta)
        verts = np.concatenate([np.stack([x, y, np.full(seg, zb)], 1), np.stack([x, y, top], 1)])
        faces = [(j, (j + 1) % seg, seg + (j + 1) % seg, seg + j) for j in range(seg)]
        ob = U.mesh_from_data(name, verts, faces=faces, collection=COLL)
        U.add_attribute(ob.data, "h01", np.concatenate([np.zeros(seg), np.ones(seg)]).astype(np.float32))
        U.add_attribute(ob.data, "prof", np.concatenate([np.zeros(seg), _prof01(spec, top)]).astype(np.float32))
        U.gn_modifier(ob, _ridge_tree(), Pivot=bpy.data.objects.get(N_PIVOT), Floor=_notch_floor(dist))
        ob.data.materials.append(_mountain_material(i, aer))
        ob.visible_shadow = False
        ob.visible_diffuse = False
        ob.visible_glossy = False
        ob.color = (0.3, 0.2, 0.25, 1.0)
        out[name] = ob
    out["pagoda"] = _build_pagoda(aer)
    return out


def _mountain_material(i, aer):
    name = f"ENV_mtn_mat_{i}"
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    nt = mat.node_tree
    nt.nodes.clear()
    nb = U.NB(nt, group_io=False)
    out = nb.n('ShaderNodeOutputMaterial')
    geo = nb.n('ShaderNodeNewGeometry')
    frac = i / float(len(MOUNTAINS) - 1)
    base = nb.mix(frac, _vc(nb, "mtn_near"), _vc(nb, "mtn_far"), 'RGBA')
    d = nb.vmath('SCALE', geo['Incoming'], scale=-1.0)
    dh = nb.vmath('NORMALIZE', nb.vmath('MULTIPLY', d, (1.0, 1.0, 0.0)))
    sh = nb.vmath('NORMALIZE', nb.vmath('MULTIPLY', _sun_dir(nb), (1.0, 1.0, 0.0)))
    toward = _powpos(nb, nb.vmath('DOT_PRODUCT', dh, sh), 6.0)
    base = _cmul(nb, base, nb.math('ADD', 1.0, nb.math('MULTIPLY', toward, nb.math('MULTIPLY', _vf(nb, "mtn_glow"),
                                                                                         0.9))))
    h01 = U.attribute_node(mat, "h01", 'GEOMETRY')
    mist = nb.math('MULTIPLY', _smooth(nb, h01.outputs['Fac'], 0.75, 0.0), 0.55)
    em = nb.n('ShaderNodeEmission', base, 1.0)
    ae = _group_node(nb, aer, em, nb.math('ADD', 1.0, mist))
    nb.link(ae, out.inp('Surface'))
    mat.diffuse_color = (0.3, 0.2, 0.25, 1.0)
    return mat


def _pagoda_mesh():
    """Original five-tier pagoda silhouette (unit: metres, base at z=0): shrinking tiers, each with a flared hip
    roof whose corners turn up, and a slender spire with rings."""
    bm = bmesh.new()

    def box(cx, cy, z0, hx, hy, hz):
        r = bmesh.ops.create_cube(bm, size=1.0)
        for v in r["verts"]:
            v.co = Vector((cx + v.co.x * 2 * hx, cy + v.co.y * 2 * hy, z0 + (v.co.z + 0.5) * hz))

    def roof(z, half_in, half_out, rise, lift):
        """Flared roof: inner square at z+rise, outer eave square at z with corners lifted by `lift`."""
        vin = [bm.verts.new((sx * half_in, sy * half_in, z + rise)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        vmid = []
        vout = []
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            vout.append(bm.verts.new((sx * half_out, sy * half_out, z + lift)))
        for k, (sx, sy) in enumerate(((0, -1), (1, 0), (0, 1), (-1, 0))):
            vmid.append(bm.verts.new((sx * half_out * 0.98, sy * half_out * 0.98, z - 0.15)))
        order_out = []
        for k in range(4):
            order_out += [vout[k], vmid[k]]
        for k in range(4):
            a, b = vin[k], vin[(k + 1) % 4]
            o0, m, o1 = vout[k], vmid[k], vout[(k + 1) % 4]
            bm.faces.new((a, o0, m))
            bm.faces.new((a, m, b))
            bm.faces.new((b, m, o1))
        thick = [bm.verts.new((v.co.x, v.co.y, v.co.z - 0.5)) for v in order_out]
        for k in range(8):
            a, b = order_out[k], order_out[(k + 1) % 8]
            c, d = thick[(k + 1) % 8], thick[k]
            bm.faces.new((a, b, c, d))
        bm.faces.new(list(reversed(thick)))

    z = 0.0
    box(0, 0, z, 6.0, 6.0, 1.2)                   # stone base
    z = 1.2
    widths = [4.6, 4.1, 3.6, 3.15, 2.7]
    for i, w in enumerate(widths):
        h = 3.6 if i == 0 else 2.9
        box(0, 0, z, w, w, h)
        z += h
        roof(z, w * 0.72, w + 2.4 - 0.15 * i, 1.1, 1.0 + 0.1 * i)
        z += 1.1
    box(0, 0, z, 1.0, 1.0, 1.0)
    z += 1.0
    spire = 9.0
    box(0, 0, z, 0.22, 0.22, spire)
    for k in range(9):
        zz = z + 1.0 + k * 0.62
        box(0, 0, zz, 0.55 - 0.02 * k, 0.55 - 0.02 * k, 0.12)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(N_PAGODA)
    bm.to_mesh(me)
    bm.free()
    return me


def _build_pagoda(aer):
    ob = bpy.data.objects.get(N_PAGODA)
    if ob is not None:
        return ob
    spec = MOUNTAINS[PAGODA_LAYER]
    th = math.radians(90.0 - PAGODA_AZ)
    zt = float(_ridge_profile(np.array([th]), spec)[0])
    dist = spec[0] - 6.0
    me = _pagoda_mesh()
    ob = U.new_object(N_PAGODA, me, COLL)
    ob.location = (dist * math.cos(th), dist * math.sin(th), zt - 1.5)
    ob.rotation_euler = (0.0, 0.0, th + 0.4)
    ob.scale = (1.45, 1.45, 1.45)
    mat = _mountain_material(PAGODA_LAYER, aer)
    me.materials.append(mat)
    U.add_attribute(me, "h01", np.ones(len(me.vertices), dtype=np.float32))
    ob.visible_shadow = False
    ob.color = (0.3, 0.2, 0.25, 1.0)
    return ob


# ================================================================================================ lone pine
PINE_HEIGHT = 8.6
PINE_SPLIT_NORMAL = (0.0, 1.0, 0.0)   # the halves separate along +-this (screen left/right from +X cameras)
PINE_LEAN = (1.0, 0.0, 0.0)          # the trunk's S-curve lies in the split plane (plane = span(Z, lean))


def _tube(bm, path, radii, sides, seed, bark=0.10, cap=True):
    """Closed tube along `path` (k,3) with per-ring radii and radial bark noise; parallel-transport frames (no
    twisting). Returns the new faces."""
    rng = _rng("tube", seed)
    k = len(path)
    tang = np.gradient(path, axis=0)
    tang /= np.linalg.norm(tang, axis=1, keepdims=True)
    u = np.cross(tang[0], [0.0, 0.0, 1.0] if abs(tang[0][2]) < 0.9 else [1.0, 0.0, 0.0])
    u /= np.linalg.norm(u)
    rings = []
    ph = rng.uniform(0, 6.28, 4)
    for i in range(k):
        t = tang[i]
        u = u - np.dot(u, t) * t
        u /= max(np.linalg.norm(u), 1e-9)
        v = np.cross(t, u)
        ring = []
        for j in range(sides):
            a = 2 * math.pi * j / sides
            n = 1.0 + bark * (math.sin(5 * a + ph[0] + i * 0.35) * 0.6 + math.sin(11 * a + ph[1] - i * 0.25) * 0.4)
            p = path[i] + (u * math.cos(a) + v * math.sin(a)) * radii[i] * n
            ring.append(bm.verts.new(p))
        rings.append(ring)
    faces = []
    for i in range(k - 1):
        for j in range(sides):
            j1 = (j + 1) % sides
            faces.append(bm.faces.new((rings[i][j], rings[i][j1], rings[i + 1][j1], rings[i + 1][j])))
    if cap:
        faces.append(bm.faces.new(list(reversed(rings[0]))))
        faces.append(bm.faces.new(rings[-1]))
    return faces


def _blob(bm, center, rx, ry, rz, yaw, seed):
    """One lumpy, flattened ellipsoid (flat-ish underside, billowing top)."""
    rng = _rng("blob", seed)
    r = bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
    ph = rng.uniform(0, 6.28, 5)
    cy, sy = math.cos(yaw), math.sin(yaw)
    for v in r["verts"]:
        x, y, z = v.co
        lump = 1.0 + 0.14 * math.sin(3.3 * x + ph[0]) * math.sin(2.9 * y + ph[1]) + 0.09 * math.sin(6.1 * z + ph[2]) \
            + 0.06 * math.sin(9.7 * x + 8.3 * y + ph[3])
        z = z * (0.45 if z < 0 else 1.0)
        x, y, z = x * rx * lump, y * ry * lump, z * rz * lump
        v.co = Vector((center[0] + x * cy - y * sy, center[1] + x * sy + y * cy, center[2] + z))
    return {f for v in r["verts"] for f in v.link_faces}


def _needle_tufts(bm, center, rx, ry, rz, yaw, seed, n=18):
    """Opaque needle fringes around a blob's rim: n fans of 5 thin needles (1.2 cm wide, 12-26 cm long) radiating
    outward and a little downward from the blob's lower equator, so a foliage pad reads as pine needles (spiky
    silhouette), not as a smooth stone. Returns the new faces."""
    rng = _rng("tuft", seed)
    faces = []
    cy, sy = math.cos(yaw), math.sin(yaw)
    for k in range(n):
        a = 2 * math.pi * (k + rng.uniform(-0.3, 0.3)) / n
        ex, ey = math.cos(a) * rx * 0.92, math.sin(a) * ry * 0.92
        base = Vector((center[0] + ex * cy - ey * sy, center[1] + ex * sy + ey * cy,
                       center[2] - rz * rng.uniform(0.05, 0.25)))
        out = Vector((base.x - center[0], base.y - center[1], 0.0)).normalized()
        side = Vector((-out.y, out.x, 0.0))
        for j in range(5):
            sp = math.radians((j - 2) * 16.0 + rng.uniform(-6, 6))
            d = (out * math.cos(sp) + side * math.sin(sp) + Vector((0, 0, rng.uniform(-0.45, 0.1)))).normalized()
            L = rng.uniform(0.12, 0.26)
            w = side * 0.006
            v0, v1, v2 = bm.verts.new(base - w), bm.verts.new(base + w), bm.verts.new(base + d * L)
            faces.append(bm.faces.new((v0, v1, v2)))
    return faces


def _pad(bm, center, size, yaw, seed):
    """Cloud-like niwaki foliage pad: an irregular horizontal cluster of 4-7 lumpy blobs, ~size m across, each with
    a fringe of needle tufts round its rim."""
    rng = _rng("pad", seed)
    faces = set()
    nb_ = int(rng.integers(4, 8))
    cy, sy = math.cos(yaw), math.sin(yaw)
    for i in range(nb_):
        a = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(0.0, 0.5) * size
        ox, oy = d * math.cos(a) * 1.3, d * math.sin(a) * 0.8
        c = (center[0] + ox * cy - oy * sy, center[1] + ox * sy + oy * cy,
             center[2] + rng.uniform(-0.08, 0.18) * size - 0.05 * d)
        r0 = size * rng.uniform(0.28, 0.45)
        bx, bz = r0 * rng.uniform(1.0, 1.4), r0 * rng.uniform(0.42, 0.6)
        byaw = yaw + rng.uniform(-0.6, 0.6)
        faces |= _blob(bm, c, bx, r0, bz, byaw, f"{seed}:{i}")
        faces |= set(_needle_tufts(bm, c, bx, r0, bz, byaw, f"{seed}:{i}", n=int(10 + 14 * r0)))
    return faces


def _pine_bmesh():
    """Trunk (S-curve in the split plane, flared base, twisting bark), 8 main branches with sub-branches, cloud pads.
    Material indices: 0 bark, 1 foliage."""
    rng = _rng("pine")
    bm = bmesh.new()
    lean = np.array(PINE_LEAN, dtype=float)
    side = np.array(PINE_SPLIT_NORMAL, dtype=float)
    n = 30
    t = np.linspace(0, 1, n)
    x = (1.25 * np.sin(t * 2.6) - 1.1 * t ** 2.2) * 1.7
    wob = 0.16 * np.sin(t * 7.0 + 0.5) * t
    z = t * PINE_HEIGHT - 0.6
    path = np.outer(x, lean) + np.outer(wob, side) + np.outer(z, [0, 0, 1])
    radii = 0.46 * (1.0 - 0.74 * t) + 0.34 * np.exp(-(t + 0.03) * 16.0)
    trunk = _tube(bm, path, radii, 16, "trunk", bark=0.10)
    bark_faces = set(trunk)
    fol_faces = set()
    # main branches: (height fraction, azimuth deg, length, droop)
    specs = [(0.40, 200, 4.2, -0.16), (0.47, 25, 3.4, -0.05), (0.55, 115, 2.9, -0.10), (0.62, 295, 3.3, 0.02),
             (0.70, 165, 2.6, 0.06), (0.77, 55, 2.3, 0.04), (0.85, 240, 1.9, 0.10), (0.93, 340, 1.4, 0.12)]
    for bi, (hf, az, ln, droop) in enumerate(specs):
        i0 = int(hf * (n - 1))
        p0 = path[i0]
        a = math.radians(az + rng.uniform(-10, 10))
        d = np.array([math.cos(a), math.sin(a), 0.0])
        m = 9
        tt = np.linspace(0, 1, m)
        bp = p0 + np.outer(tt * ln, d) + np.outer(0.35 * np.sin(tt * math.pi) * ln * 0.22 + droop * tt * ln, [0, 0, 1])
        bp = bp + np.outer(0.2 * np.sin(tt * 4.2 + bi) * tt, np.cross(d, [0, 0, 1]))
        br = radii[i0] * 0.5 * (1.0 - 0.8 * tt) + 0.025
        bark_faces |= set(_tube(bm, bp, br, 8, f"br{bi}", bark=0.06))
        fol_faces |= _pad(bm, bp[-1] + np.array([0, 0, 0.22]), 1.5 + 0.25 * ln, a, f"pad{bi}")
        j = m // 2 + int(rng.integers(0, 2))
        sa = a + rng.choice([-1, 1]) * rng.uniform(0.7, 1.1)
        sd = np.array([math.cos(sa), math.sin(sa), 0.0])
        sp = bp[j] + np.outer(np.linspace(0, 1, 5) * ln * 0.5, sd) + np.outer(np.linspace(0, 0.3, 5), [0, 0, 1])
        bark_faces |= set(_tube(bm, sp, np.linspace(br[j] * 0.7, 0.03, 5), 6, f"sb{bi}", bark=0.05))
        fol_faces |= _pad(bm, sp[-1] + np.array([0, 0, 0.18]), 1.1 + 0.1 * ln, sa, f"spad{bi}")
    fol_faces |= _pad(bm, path[-1] + np.array([0, 0, 0.3]), 1.9, 0.3, "crown")
    for f in bm.faces:
        f.material_index = 1 if f in fol_faces else 0
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def _split_half(src_bm, keep_positive, name, split_mat_index=2):
    """Copy of the pine bmesh cut by the vertical split plane through the trunk base; cut holes filled with the
    split-wood material (index 2)."""
    bm = src_bm.copy()
    geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
    res = bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-5, plane_co=(0.0, 0.0, 0.0), plane_no=PINE_SPLIT_NORMAL,
                                 clear_outer=keep_positive is False, clear_inner=keep_positive is True)
    cut_edges = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
    before = set(bm.faces)
    bmesh.ops.holes_fill(bm, edges=cut_edges, sides=0)
    for f in bm.faces:
        if f not in before:
            nbr = [lf.material_index for e in f.edges for lf in e.link_faces if lf is not f and lf in before]
            fol = sum(1 for m in nbr if m == 1) > len(nbr) * 0.5
            f.material_index = 1 if fol else split_mat_index
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def _pine_materials():
    _, aer = _groups()
    mats = []
    for name, col, rough in (("ENV_pine_bark", (0.045, 0.035, 0.030), 0.85),
                             ("ENV_pine_foliage", (0.030, 0.055, 0.030), 0.75),
                             ("ENV_pine_split", (0.55, 0.43, 0.30), 0.7)):
        mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        nt = mat.node_tree
        nt.nodes.clear()
        nb = U.NB(nt, group_io=False)
        out = nb.n('ShaderNodeOutputMaterial')
        geo = nb.n('ShaderNodeNewGeometry')
        nz = nb.noise(nb.vmath('MULTIPLY', geo['Position'], (3.0, 3.0, 0.8)), scale=1.0, detail=3.0)
        c = _cmul(nb, col, nb.math('ADD', 0.7, nb.math('MULTIPLY', nz['Fac'], 0.6)))
        if name == "ENV_pine_foliage":
            top = _smooth(nb, nb.sep(geo['Normal'])['Z'], -0.2, 0.9)
            c = _cmul(nb, c, nb.math('ADD', 0.6, nb.math('MULTIPLY', top, 0.8)))
        wet = _vf(nb, "wet")
        c = _cmul(nb, c, nb.math('SUBTRACT', 1.0, nb.math('MULTIPLY', wet, 0.35)))
        fol = name == "ENV_pine_foliage"
        # wet foliage stays matte (needle masses never mirror the sky: specular <= 0.2, roughness >= 0.6)
        rgh = nb.math('SUBTRACT', rough, nb.math('MULTIPLY', wet, 0.15 if fol else 0.45))
        bsdf = nb.n('ShaderNodeBsdfPrincipled', Base_Color=c, Roughness=rgh,
                    Specular_IOR_Level=0.2 if fol else 0.5)
        ae = _group_node(nb, aer, bsdf, 1.0)
        nb.link(ae, out.inp('Surface'))
        mat.diffuse_color = tuple(col) + (1.0,)
        mats.append(mat)
    return mats


def _build_pine(sc):
    """ENV_pine (intact, visible) + ENV_pine_half_A / ENV_pine_half_B (hidden; the two halves of the same tree cut
    by the vertical plane through the trunk with normal PINE_SPLIT_NORMAL: A = negative side, B = positive side;
    cut faces use ENV_pine_split). All three have their origin at the trunk base on the rise (config.PINE_POS,
    ground PINE_RISE m) so the vfx lane can hinge the halves apart (vfx.tree_strike keys their visibility and
    rotation). The trunk's S-curve lies in the split plane, so each half carries half of the trunk all the way up."""
    if bpy.data.objects.get(N_PINE) is not None:
        return dict(pine=bpy.data.objects[N_PINE], pine_half_A=bpy.data.objects[N_PINE_A],
                    pine_half_B=bpy.data.objects[N_PINE_B])
    mats = _pine_materials()
    bm = _pine_bmesh()
    me = bpy.data.meshes.new(N_PINE)
    bm.to_mesh(me)
    me_a = _split_half(bm, False, N_PINE_A)
    me_b = _split_half(bm, True, N_PINE_B)
    bm.free()
    base = (config.PINE_POS[0], config.PINE_POS[1], float(terrain_height(*config.PINE_POS)))
    out = {}
    for key, name, m in (("pine", N_PINE, me), ("pine_half_A", N_PINE_A, me_a), ("pine_half_B", N_PINE_B, me_b)):
        for mt in mats:
            m.materials.append(mt)
        for poly in m.polygons:
            poly.use_smooth = True
        ob = U.new_object(name, m, COLL)
        ob.location = base
        ob.color = (0.05, 0.07, 0.04, 1.0)
        out[key] = ob
    for key in ("pine_half_A", "pine_half_B"):
        out[key].hide_render = True
        out[key].hide_viewport = True
    return out


# ================================================================================================ rocks
def _build_rocks(sc):
    """A few weathered boulders (ROCKS): noise-displaced, flattened icospheres sunk into the terrain."""
    _, aer = _groups()
    mat = bpy.data.materials.get("ENV_rock") or bpy.data.materials.new("ENV_rock")
    nt = mat.node_tree
    nt.nodes.clear()
    nb = U.NB(nt, group_io=False)
    out = nb.n('ShaderNodeOutputMaterial')
    geo = nb.n('ShaderNodeNewGeometry')
    nz = nb.noise(nb.vmath('SCALE', geo['Position'], scale=1.3), scale=1.0, detail=5.0, roughness=0.6)
    lich = _smooth(nb, nb.noise(nb.vmath('SCALE', geo['Position'], scale=0.7), scale=1.0, detail=3.0)['Fac'], 0.55, 0.68)
    c = nb.mix(lich, _cmul(nb, (0.10, 0.095, 0.085), nb.math('ADD', 0.6, nz['Fac'])), (0.16, 0.15, 0.10, 1.0), 'RGBA')
    wet = _vf(nb, "wet")
    c = _cmul(nb, c, nb.math('SUBTRACT', 1.0, nb.math('MULTIPLY', wet, 0.45)))
    bsdf = nb.n('ShaderNodeBsdfPrincipled', Base_Color=c, Roughness=nb.math('SUBTRACT', 0.9, nb.math('MULTIPLY', wet, 0.6)))
    ae = _group_node(nb, aer, bsdf, 1.0)
    nb.link(ae, out.inp('Surface'))
    mat.diffuse_color = (0.12, 0.11, 0.10, 1.0)
    obs = []
    for x, y, rad, hf, seed in ROCKS:
        name = f"ENV_rock_{seed}"
        if bpy.data.objects.get(name) is not None:
            obs.append(bpy.data.objects[name])
            continue
        rng = _rng("rock", seed)
        bm = bmesh.new()
        r = bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
        ph = rng.uniform(0, 6.28, 6)
        for v in r["verts"]:
            px, py, pz = v.co
            k = 1.0 + 0.22 * math.sin(2.1 * px + ph[0]) * math.cos(1.7 * py + ph[1]) + \
                0.12 * math.sin(4.3 * pz + ph[2]) + 0.06 * math.sin(9.1 * px + 7.3 * py + ph[3])
            v.co = Vector((px * rad * k * rng.uniform(0.95, 1.05), py * rad * k * 0.8, pz * rad * hf * k))
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        me.materials.append(mat)
        for poly in me.polygons:
            poly.use_smooth = True
        ob = U.new_object(name, me, COLL)
        ob.location = (x, y, float(terrain_height(x, y)) - 0.25 * rad * hf)
        ob.rotation_euler = (rng.uniform(-0.1, 0.1), rng.uniform(-0.1, 0.1), rng.uniform(0, 6.28))
        ob.color = (0.12, 0.11, 0.10, 1.0)
        obs.append(ob)
    return obs


# ================================================================================================ grass: clump meshes
CLUMP_COLL = "ENV_grass_clumps"
STUB_Z = 0.62                # normalised cut height of the stubble variants (x clump height 0.95-1.15 -> ~0.6-0.7 m)
N_SPECIES = 3                # clump designs; every design exists in each LOD (subsets of the same design)
# LODs by PROJECTED distance (m * 35 / focal mm from the active camera; every instance's thresholds are jittered by
# +-LOD_JITTER so a switch is a wide stochastic blend, never a line):
# (max projected dist, leaves, leaf segs, V-fold leaves, stems, stem segs, feathers per plume, plume segs, plumes)
CLUMP_LODS = [(12.0, 9, 8, True, 3, 4, 3, 5, 3),
              (32.0, 6, 4, False, 3, 2, 2, 3, 3),
              (80.0, 4, 2, False, 2, 1, 1, 2, 3),
              (1e9, 3, 2, False, 1, 1, 1, 2, 2)]
LOD_JITTER = 0.25
FRUSTUM_PAD = (2.0, 0.15)    # (m, fraction of the half-FOV) around the active camera's frustum before a clump drops
                             # to the coarsest LOD (covers the clump radius, its wind bend and a frame of camera motion)
LOD_FOCAL_MAX = 1.0e4        # mm: the LOD projection uses min(lens, this) (perf cap of the telephoto LOD boost)
PLUME_LEN = (0.20, 0.28)     # feather-plume length at unit clump height (~21-30 cm on a 1.05 m clump)
PLUME_W = 0.042              # max width of one feather of the full design; the open 3-feather fan is ~10 cm wide
PLUME_SPLAY = 0.50           # rad between the feathers of a fan (an open feather-duster, not a wheat ear)
LEAF_FOLD = 0.28             # V-fold depth (x width) of the LOD0 leaves (3 vertices across: edge, midrib, edge)
N_VARIANTS = N_SPECIES * len(CLUMP_LODS)      # + the same number of stubble variants


def _bezier(p0, p1, p2, n):
    t = np.linspace(0.0, 1.0, n + 1)[:, None]
    return (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t ** 2 * p2


def _clump_design(species):
    """Full-detail design of one miscanthus clump at unit height: list of strand dicts ctrl=(p0, p1, p2) (quadratic
    Bezier), w0 (base/max width), part (0 leaf, 1 stem, 2 plume feather), plume (index of the flowering stem a
    feather belongs to), feather (0..2 inside its fan), lv (random 0..1 per strand: shading + flutter phase).
    Leaves arch out and droop, tapering to a point; three flowering culms rise to 0.80-0.92 and each carries ONE
    plume: an opaque feather fan (3 soft-spindle feathers splayed PLUME_SPLAY apart, 20-28 cm long, the open fan
    ~10 cm wide) that rises from the culm top and nods over to one side (~25 deg), well above the leaf mass."""
    rng = _rng("clump2", species)
    out = []
    base_yaw = rng.uniform(0, 2 * math.pi)
    for i in range(9):
        a = base_yaw + 2 * math.pi * i / 9 + rng.uniform(-0.3, 0.3)
        d = np.array([math.cos(a), math.sin(a), 0.0])
        L = rng.uniform(0.55, 0.85)
        reach = L * rng.uniform(0.35, 0.62)
        top = L * rng.uniform(0.62, 0.82)
        p0 = d * rng.uniform(0.0, 0.035)
        p1 = d * reach * 0.22 + np.array([0, 0, top * 1.05])
        p2 = d * reach + np.array([0, 0, top * rng.uniform(0.5, 0.8)])
        out.append(dict(ctrl=(p0, p1, p2), w0=0.016 * rng.uniform(0.85, 1.2), part=0, plume=-1, feather=-1,
                        lv=rng.uniform()))
    droop = base_yaw + rng.uniform(0, 2 * math.pi)
    up = np.array([0.0, 0.0, 1.0])
    for i in range(3):
        a = base_yaw + 2.1 * i + rng.uniform(-0.5, 0.5)
        d = np.array([math.cos(a), math.sin(a), 0.0])
        h = rng.uniform(0.80, 0.92)
        lean = rng.uniform(0.03, 0.10)
        p0 = d * rng.uniform(0.0, 0.03)
        p2 = d * lean + np.array([0, 0, h])
        p1 = (p0 + p2) * 0.5 + d * lean * 0.3
        out.append(dict(ctrl=(p0, p1, p2), w0=0.006, part=1, plume=i, feather=-1, lv=rng.uniform()))
        axis = (p2 - p1) / max(np.linalg.norm(p2 - p1), 1e-6)
        sa = droop + rng.uniform(-0.7, 0.7)
        L = rng.uniform(*PLUME_LEN)
        for j in range(3):
            b = sa + (j - 1) * PLUME_SPLAY + rng.uniform(-0.08, 0.08)
            sd = np.array([math.cos(b), math.sin(b), 0.0])
            Lj = L * (1.0 if j == 1 else rng.uniform(0.84, 0.96))
            q0 = p2 - axis * 0.02
            q1 = q0 + up * 0.62 * Lj + sd * 0.08 * Lj
            q2 = q0 + up * rng.uniform(0.62, 0.80) * Lj + sd * rng.uniform(0.28, 0.42) * Lj
            out.append(dict(ctrl=(q0, q1, q2), w0=PLUME_W * rng.uniform(0.85, 1.1), part=2, plume=i, feather=j,
                            lv=rng.uniform()))
    return out


def _strand_poly(s, nseg):
    """(points (n+1, 3), widths (n+1,)) of a design strand sampled with nseg segments (width profile per part:
    leaves taper to a point, culms slightly, feathers are spindles - thin base, full middle, soft tip)."""
    pts = _bezier(*s["ctrl"], nseg)
    u = np.linspace(0.0, 1.0, nseg + 1)
    if s["part"] == 0:
        w = s["w0"] * np.maximum(1.0 - 0.96 * u ** 1.5, 0.04)
    elif s["part"] == 1:
        w = s["w0"] * (1.0 - 0.25 * u)
    else:
        w = s["w0"] * np.power(np.sin(np.pi * np.clip(u * 0.80 + 0.10, 0.0, 1.0)), 0.5)
    return pts, w


def _poly_area(pts, w):
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    return float((seg * 0.5 * (w[:-1] + w[1:])).sum())


def _lod_selection(des, lod):
    """[(strand, nseg, fold)] kept at LOD `lod`: an evenly spread subset of the leaves, the first culms and their
    plumes, fewer feathers per fan (1 = the centre one, 2 = the outer pair)."""
    _, nl, ls, vf, ns, ss, nf, ps, npl = CLUMP_LODS[lod]
    leaves = [s for s in des if s["part"] == 0]
    keep_l = sorted(set(int(round(k)) for k in np.linspace(0, len(leaves), nl, endpoint=False)))
    sel = [(leaves[k], ls, LEAF_FOLD if vf else 0.0) for k in keep_l]
    sel += [(s, ss, 0.0) for s in des if s["part"] == 1 and s["plume"] < ns]
    fe = {1: (1,), 2: (0, 2), 3: (0, 1, 2)}[nf]
    sel += [(s, ps, 0.18 if vf else 0.0) for s in des if s["part"] == 2 and s["plume"] < npl and s["feather"] in fe]
    return sel


def _clump_strands(species, lod):
    """Polylines [(pts, widths, part, lv, fold)] of `species` at LOD `lod`. Widths are compensated per part so every
    LOD keeps the leaf / culm / plume AREA of the full design (same mean colour and coverage -> no LOD bands)."""
    des = _clump_design(species)
    full = {0: 0.0, 1: 0.0, 2: 0.0}
    for s, nseg, _ in _lod_selection(des, 0):
        full[s["part"]] += _poly_area(*_strand_poly(s, nseg))
    sel = _lod_selection(des, lod)
    kept = {0: 0.0, 1: 0.0, 2: 0.0}
    polys = []
    for s, nseg, fold in sel:
        pts, w = _strand_poly(s, nseg)
        kept[s["part"]] += _poly_area(pts, w)
        polys.append((s, pts, w, fold))
    mult = {p: (full[p] / kept[p] if kept[p] > 0 else 1.0) for p in full}
    return [(pts, w * mult[s["part"]], s["part"], s["lv"], fold) for s, pts, w, fold in polys]


def _clip_strand(pts, w, zc, keep="below"):
    """Split a polyline (base first) where it first rises through height zc: keep='below' returns the part from the
    base to the cut (the stubble), keep='above' everything after the cut (the severed top, drooping tip included).
    Returns (pts, w) or None when that part is empty."""
    if pts[0, 2] >= zc:
        return None if keep == "below" else (pts, w)
    for i in range(1, len(pts)):
        if pts[i, 2] > zc:
            u = (zc - pts[i - 1, 2]) / max(pts[i, 2] - pts[i - 1, 2], 1e-9)
            pc = pts[i - 1] + (pts[i] - pts[i - 1]) * u
            wc = w[i - 1] + (w[i] - w[i - 1]) * u
            if keep == "below":
                return np.vstack([pts[:i], pc[None]]), np.concatenate([w[:i], [wc]])
            return np.vstack([pc[None], pts[i:]]), np.concatenate([[wc], w[i:]])
    return (pts, w) if keep == "below" else None


def _strands_to_mesh(name, strands, clip=None, keep="below", z_shift=0.0, collection=None):
    """Ribbons along each polyline (width across the horizontal perpendicular, slightly twisted; fold > 0 = V-shaped
    cross-section with a raised midrib: 3 vertices across). clip: cut height (keep 'below' = stubble without the
    plume feathers, 'above' = the severed top). Mesh point attributes: hz (height 0..1 of the uncut clump), part
    (0 leaf / 1 culm / 2 plume), tip (0 base .. 1 tip), lv (per-strand random), cut (1 at a stubble's cut end, fading
    over 10 cm: pale cut straw in the shader)."""
    verts, faces, hz, part, tip, lvs, cuts = [], [], [], [], [], [], []
    for pts, w, pt, lv, fold in strands:
        if clip is not None:
            if pt == 2 and keep == "below":
                continue
            c = _clip_strand(pts, w, clip, keep)
            if c is None:
                continue
            pts, w = c
        n = len(pts)
        tan = np.gradient(pts, axis=0)
        tan /= np.maximum(np.linalg.norm(tan, axis=1, keepdims=True), 1e-9)
        side = np.cross(tan, np.array([0.0, 0.0, 1.0]))
        for i in range(n):
            if np.linalg.norm(side[i]) < 1e-6:
                side[i] = np.array([1.0, 0.0, 0.0])
        side /= np.linalg.norm(side, axis=1, keepdims=True)
        base = len(verts)
        ring = 3 if fold > 0 else 2
        for i in range(n):
            tw = 0.35 * i / max(n - 1, 1)
            sd = side[i] * math.cos(tw) + np.array([0, 0, 1.0]) * math.sin(tw) * 0.3
            sd /= np.linalg.norm(sd)
            nrm = np.cross(sd, tan[i])
            nrm /= max(np.linalg.norm(nrm), 1e-9)
            u = i / max(n - 1, 1)
            ring_pts = [pts[i] - sd * w[i] * 0.5, pts[i] + nrm * w[i] * fold, pts[i] + sd * w[i] * 0.5] if ring == 3 \
                else [pts[i] - sd * w[i] * 0.5, pts[i] + sd * w[i] * 0.5]
            for q in ring_pts:
                verts.append(q + np.array([0.0, 0.0, -z_shift]))
                cuts.append(max(0.0, 1.0 - (clip - pts[i][2]) / 0.10) if (clip is not None and keep == "below") else 0.0)
                hz.append(q[2])
                part.append(float(pt))
                tip.append(u)
                lvs.append(lv)
        for i in range(n - 1):
            a = base + ring * i
            b = a + ring
            for k in range(ring - 1):
                faces.append((a + k, a + k + 1, b + k + 1, b + k))
    ob = U.mesh_from_data(name, np.array(verts).reshape(-1, 3), faces=faces, collection=collection or CLUMP_COLL)
    me = ob.data
    U.add_attribute(me, "hz", np.clip(np.array(hz, dtype=np.float32), 0, 1.2))
    U.add_attribute(me, "part", np.array(part, dtype=np.float32))
    U.add_attribute(me, "tip", np.array(tip, dtype=np.float32))
    U.add_attribute(me, "lv", np.array(lvs, dtype=np.float32))
    U.add_attribute(me, "cut", np.array(cuts, dtype=np.float32))
    return ob


TOP_LOD = 1                  # detail of the severed-top meshes (shear pool)


def _build_clumps(mat):
    """Collection ENV_grass_clumps (excluded from the view layer), in instance-index order: N_VARIANTS clumps
    (index = species + N_SPECIES * lod), their N_VARIANTS stubble copies (cut at STUB_Z, plumes removed), then
    N_SPECIES severed tops (the part above STUB_Z of the TOP_LOD clump, origin at the cut point) used by the shear
    pool."""
    col = bpy.data.collections.get(CLUMP_COLL)
    if col is not None and len(col.objects) == 2 * N_VARIANTS + N_SPECIES:
        return col, list(col.objects)
    col = U.ensure_collection(CLUMP_COLL, parent=COLL)
    obs = []
    for stub in (False, True):
        for lod in range(len(CLUMP_LODS)):
            for sp in range(N_SPECIES):
                i = len(obs)
                st = _clump_strands(sp, lod)
                obs.append(_strands_to_mesh(f"ENV_clump_{i:02d}_{'stub' if stub else 'lod'}{lod}_s{sp}", st,
                                            clip=STUB_Z if stub else None))
    for sp in range(N_SPECIES):
        i = len(obs)
        obs.append(_strands_to_mesh(f"ENV_clump_{i:02d}_top_s{sp}", _clump_strands(sp, TOP_LOD), clip=STUB_Z,
                                    keep="above", z_shift=STUB_Z))
    for ob in obs:
        ob.data.materials.append(mat)
        ob.location = (0, 0, 0)
        ob.color = (0.62, 0.48, 0.25, 1.0)          # layout (Workbench object colour) of the instances
        # instances take their ray visibility from the SOURCE object (ENV_grass.visible_shadow = False does not
        # reach them): the clumps DO cast - their self-shadowing is part of the look (without it front-lit fields
        # read 15-35 % brighter and flat, out/dev/perf/cmp_shadow_*.png). Kept affordable by the GN wind shear (no
        # displaced shadow shader) and the frustum LOD (off-screen casters at LOD3)
        ob.visible_shadow = True
    lc = _layer_coll(bpy.context.view_layer.layer_collection, col)
    if lc is not None:
        lc.exclude = True
    return col, obs


def _layer_coll(lc, col):
    if lc.collection == col:
        return lc
    for ch in lc.children:
        r = _layer_coll(ch, col)
        if r is not None:
            return r
    return None


def _grass_material():
    """ENV_grass: leaves (env_grass_leaf) / straw culms / feather plumes (env_grass_plume). ONE lit closure (diffuse;
    measured: a Principled + Translucent + emission stack costs ~0.15 s per sample more at 1920x816) plus emissive
    fakes driven by the key light:
      * backlit glow: plumes only, upper part only (hz 0.6..1), when looking into the key light (vs^12); bright
        rims, dim bodies (BACKLIT_BODY + (1 - BACKLIT_BODY) rim^3);
      * leaf translucency: blades seen against the light (upper leaves);
      * grazing silver sheen on the plumes (rim^3, stronger toward the light) - the silver read comes from this,
        not from a high diffuse albedo;
      * gust brightness: +-30 % on the plumes (+-10 % leaves) with the travelling gust field (instance attr gust);
      * burn: grey ash albedo + thin ember front (instance attrs burn / ember), wetness (env_wet), aerial haze.
    No displacement: both wind levels live in GN_ENV_grass (base lean = rigid tilt, lagged bend + flutter = a shear
    of the instance transform). A displaced material has to run its own vertex shader in the depth, shadow and
    velocity passes: with the clumps casting shadows that cost 2-4x the whole frame (perf TD, out/dev/perf/)."""
    _, aer = _groups()
    mat = bpy.data.materials.get("ENV_grass") or bpy.data.materials.new("ENV_grass")
    nt = mat.node_tree
    nt.nodes.clear()
    nb = U.NB(nt, group_io=False)
    out = nb.n('ShaderNodeOutputMaterial')
    hz = U.attribute_node(mat, "hz", 'GEOMETRY').outputs['Fac']
    part = U.attribute_node(mat, "part", 'GEOMETRY').outputs['Fac']
    tip = U.attribute_node(mat, "tip", 'GEOMETRY').outputs['Fac']
    lv = U.attribute_node(mat, "lv", 'GEOMETRY').outputs['Fac']
    gust = U.attribute_node(mat, "gust", 'INSTANCER').outputs['Fac']
    burn = U.attribute_node(mat, "burn", 'INSTANCER').outputs['Fac']
    var = U.attribute_node(mat, "var", 'INSTANCER').outputs['Fac']
    ember = U.attribute_node(mat, "ember", 'INSTANCER').outputs['Fac']
    plume = _smooth(nb, part, 1.4, 1.9)
    stem = nb.math('MULTIPLY', _smooth(nb, part, 0.5, 0.9), nb.math('SUBTRACT', 1.0, plume))
    leaf_c = _vc(nb, "grass_leaf")
    plume_c = _vc(nb, "grass_plume")
    straw = nb.mix(0.45, leaf_c, plume_c, 'RGBA')
    c = nb.mix(stem, leaf_c, straw, 'RGBA')
    c = nb.mix(plume, c, plume_c, 'RGBA')
    c = _cmul(nb, c, nb.math('ADD', 0.62, nb.math('ADD', nb.math('MULTIPLY', var, 0.5), nb.math('MULTIPLY', lv, 0.3))))
    dry = nb.math('MULTIPLY', _smooth(nb, var, 0.7, 1.0), nb.math('SUBTRACT', 1.0, plume))
    c = nb.mix(nb.math('MULTIPLY', dry, 0.5), c, straw, 'RGBA')
    cutf = U.attribute_node(mat, "cut", 'GEOMETRY').outputs['Fac']
    c = nb.mix(nb.math('MULTIPLY', cutf, 0.7), c, _cmul(nb, straw, 1.3), 'RGBA')      # pale cut ends of the stubble
    ao = nb.math('ADD', 0.12, nb.math('MULTIPLY', 0.88, _smooth(nb, hz, 0.0, 0.85)))
    c = _cmul(nb, c, nb.math('MULTIPLY', ao, nb.math('ADD', 1.0, nb.math('MULTIPLY', tip, 0.25))))
    # travelling gust bands: +-30 % on the plumes, +-10 % on the leaves
    gb = nb.math('MULTIPLY', nb.math('SUBTRACT', gust, 0.4), nb.math('ADD', 0.2, nb.math('MULTIPLY', plume, 0.55)))
    c = _cmul(nb, c, nb.math('ADD', 1.0, nb.math('MULTIPLY', gb, GUST_BRIGHT)))
    wet = _vf(nb, "wet")
    c = _cmul(nb, c, nb.math('SUBTRACT', 1.0, nb.math('MULTIPLY', wet, 0.38)))
    c = nb.mix(_smooth(nb, burn, 0.15, 0.7), c, ASH_COL, 'RGBA')
    geo = nb.n('ShaderNodeNewGeometry')
    S = _sun_dir(nb)
    upb = nb.math('ADD', 0.25, nb.math('MULTIPLY', plume, 0.25))
    # wrap lighting: the shading normal leans toward the key light (plumes are fuzzy: side-lit plumes catch the light
    # on the camera side too; exactly backlit ones stay dark with glowing rims); shadows still apply (lit closure)
    vdir0 = nb.vmath('SCALE', geo['Incoming'], scale=-1.0)
    wrapw = nb.math('ADD', LEAF_WRAP, nb.math('MULTIPLY', plume, PLUME_WRAP - LEAF_WRAP))
    wrapw = nb.math('MULTIPLY', nb.math('MULTIPLY', wrapw, _vf(nb, "grass_wrap")),
                    _smooth(nb, nb.vmath('DOT_PRODUCT', vdir0, S), WRAP_FADE[1], WRAP_FADE[0]))
    nrm = nb.vmath('NORMALIZE', nb.vmath('ADD', nb.vmath('ADD', geo['Normal'], nb.xyz(0.0, 0.0, upb)),
                                         nb.vmath('SCALE', S, scale=wrapw)))
    bsdf = nb.n('ShaderNodeBsdfDiffuse', c, 0.0, nrm)
    em = _cmul(nb, EMBER_COL, nb.math('MULTIPLY', ember, nb.math('MULTIPLY', nb.math('SUBTRACT', 1.0, hz), 1.4)))
    vdir = nb.vmath('SCALE', geo['Incoming'], scale=-1.0)          # view direction (camera -> surface)
    ndv = nb.math('ABSOLUTE', nb.vmath('DOT_PRODUCT', geo['Normal'], vdir))
    rim3 = _powpos(nb, nb.math('SUBTRACT', 1.0, ndv), 3.0)
    rimk = nb.math('ADD', BACKLIT_BODY, nb.math('MULTIPLY', 1.0 - BACKLIT_BODY, rim3))
    vs = nb.vmath('DOT_PRODUCT', vdir, S)
    back = _powpos(nb, vs, BACKLIT_LOBE)
    through = nb.math('MAXIMUM', nb.math('MULTIPLY', nb.vmath('DOT_PRODUCT', geo['Normal'], S), -1.0), 0.0)
    top = _smooth(nb, hz, 0.6, 1.0)
    silk = nb.math('MULTIPLY', nb.math('MULTIPLY', plume, rimk), nb.math('MULTIPLY', back, top))
    silk = nb.math('MULTIPLY', silk, nb.math('MULTIPLY', _vf(nb, "grass_silk"), BACKLIT_GAIN))
    # shear fluff (instance attr fluffy = 1): loose silk catches the light from almost any side (broad forward lobe)
    fluffy = U.attribute_node(mat, "fluffy", 'INSTANCER').outputs['Fac']
    flobe = _powpos(nb, nb.math('ADD', nb.math('MULTIPLY', vs, 0.5), 0.5), 2.0)
    fsilk = nb.math('MULTIPLY', nb.math('MULTIPLY', fluffy, nb.math('ADD', 0.45, nb.math('MULTIPLY', rim3, 0.55))),
                    nb.math('ADD', 0.25, nb.math('MULTIPLY', flobe, 0.75)))
    fburst = U.attribute_node(mat, "fburst", 'INSTANCER').outputs['Fac']
    fsilk = nb.math('MULTIPLY', fsilk, nb.math('ADD', 1.0, nb.math('MULTIPLY', fburst, FLUFF_BURST)))
    silk = nb.math('ADD', silk, nb.math('MULTIPLY', fsilk, FLUFF_GLOW))
    trans = nb.math('MULTIPLY', nb.math('MULTIPLY', through, _smooth(nb, hz, 0.25, 0.9)),
                    nb.math('MULTIPLY', nb.math('SUBTRACT', 1.0, plume), nb.math('MULTIPLY', _vf(nb, "grass_trans"),
                                                                                    TRANS_GAIN)))
    lobe = _powpos(nb, nb.math('ADD', nb.math('MULTIPLY', vs, 0.5), 0.5), 2.0)
    sheen = nb.math('MULTIPLY', nb.math('MULTIPLY', plume, rim3), nb.math('ADD', 0.35, nb.math('MULTIPLY', lobe, 0.65)))
    sheen = nb.math('MULTIPLY', sheen, nb.math('MULTIPLY', _vf(nb, "grass_sheen"), SHEEN_GAIN))
    sheen = nb.math('MULTIPLY', sheen, nb.math('ADD', 1.0, nb.math('MULTIPLY', gb, GUST_BRIGHT)))
    glow = nb.math('ADD', nb.math('ADD', silk, trans), sheen)
    glow = nb.math('MULTIPLY', glow, nb.math('MULTIPLY', _vf(nb, "key_pow"), nb.math('SUBTRACT', 1.0, nb.math(
        'MULTIPLY', wet, 0.6))))
    glow = nb.math('MULTIPLY', glow, nb.math('SUBTRACT', 1.0, _smooth(nb, burn, 0.1, 0.5)))
    em = nb.vmath('ADD', em, _cmul(nb, nb.vmath('MULTIPLY', _vc(nb, "key_col"), c), glow))
    emn = nb.n('ShaderNodeEmission', em, 1.0)
    add = nb.n('ShaderNodeAddShader', bsdf, emn)
    ae = _group_node(nb, aer, add, 1.0)
    nb.link(ae, out.inp('Surface'))
    # no shader displacement (perf): the second wind level (lagged bend + flutter) is a per-clump shear of the
    # instance transform in GN_ENV_grass. A displaced material cannot use EEVEE's shared depth / shadow shaders -
    # with the clumps casting shadows that made every final frame 2-4x slower
    mat.displacement_method = 'BUMP'
    mat.diffuse_color = (0.62, 0.48, 0.25, 1.0)
    return mat


BACKLIT_GAIN = 0.16          # plume forward-scatter glow per unit of key power when looking into the key light
PLUME_WRAP = 0.8             # plume shading-normal lean toward the key light (fuzzy panicle: side light wraps round)
LEAF_WRAP = 0.3              # the same for leaves / culms (thin blades: a little)
WRAP_FADE = (0.5, 0.97)      # the wrap fades out as the view turns INTO the key light (view . sun 0.5 -> 0.97): a
                             # backlit field stays a dark mass with glowing rims (S05), side/front light wraps
BACKLIT_LOBE = 6.0           # width of the backlit lobe: (view . sun)^k (~ +-33 deg at half strength)
FLUFF_GLOW = 0.70            # shear fluff silk glow per unit of key power (broad lobe; the S11 burst must read)
FLUFF_BURST = 2.0            # extra glow of freshly cut fluff (x exp(-age / FLUFF_BURST_T)): a luminous front
FLUFF_BURST_T = 0.35         # s
BACKLIT_BODY = 0.06          # ... on the plume body (x this) vs its rims (x 1): thin bright edges, dim cores
SHEEN_GAIN = 0.05            # grazing silver sheen of the plumes per unit of key power (x state grass_sheen)
TRANS_GAIN = 0.08            # leaf translucency (light through upper blades seen against the key light)
GUST_BRIGHT = 0.55           # gust brightness modulation (x (gust - 0.4) x part weight) -> ~+-30 % on plumes
EMBER_DECAY = 6.0            # s (fx time) the burnt ring keeps a faint glow after its ramp
EMBER_COL = (1.0, 0.28, 0.04)
ASH_COL = (0.07, 0.066, 0.062, 1.0)   # grey ash albedo of the burnt ring (not char black)

# GN interface of the grass modifier: (name, type, default[, min, max])
GRASS_INPUTS = [
    ("Terrain", "OBJECT"), ("Clumps", "COLLECTION"), ("Time", "FLOAT", 0.0), ("Density", "FLOAT", 1.0),
    ("Seed", "INT", 7), ("Wind", "FLOAT", 1.0), ("Wind Dir", "FLOAT", DEFAULT_WIND_DIR),
    ("Char A", "OBJECT"), ("Char B", "OBJECT"), ("Char A On", "BOOL", False), ("Char B On", "BOOL", False),
    ("Wake A1", "OBJECT"), ("Wake A2", "OBJECT"), ("Wake B1", "OBJECT"), ("Wake B2", "OBJECT"),
    ("Wake On", "BOOL", False),
    ("Part In", "FLOAT", 0.38), ("Part Out", "FLOAT", 1.25), ("Part Angle", "FLOAT", 0.6),
    ("Clear Near", "FLOAT", 1.5), ("Clear Far", "FLOAT", 4.0), ("Clear Min", "FLOAT", 0.85),
    ("Cone Angle", "FLOAT", 0.0),
    ("Cone Length", "FLOAT", 0.0), ("Cone Radius", "FLOAT", 0.30),
    ("Freeze T0", "FLOAT", 1e7), ("Freeze T1", "FLOAT", 1e7),
    ("Burn Center", "VECTOR", (0.0, 0.0, 0.0)), ("Burn Radius", "FLOAT", 9.0), ("Burn Width", "FLOAT", 2.5),
    ("Burn T0", "FLOAT", 1e7), ("Burn Ramp", "FLOAT", 1.0), ("Burn End", "FLOAT", 1e7),
    ("Burn Amount", "FLOAT", 0.0), ("Wet", "FLOAT", 0.0),
    ("LOD Force", "INT", -1), ("LOD Focal Max", "FLOAT", LOD_FOCAL_MAX), ("Wind Bend", "FLOAT", 1.0),
    ("Frustum LOD", "BOOL", True),
]
N_SHEAR_SLOTS = 2
for _i in range(1, N_SHEAR_SLOTS + 1):
    GRASS_INPUTS += [(f"Shear{_i} Origin", "VECTOR", (0.0, 0.0, 0.0)), (f"Shear{_i} T0", "FLOAT", 1e7),
                     (f"Shear{_i} Speed", "FLOAT", 30.0), (f"Shear{_i} Radius", "FLOAT", 0.0),
                     (f"Shear{_i} Arc", "FLOAT", 360.0), (f"Shear{_i} Facing", "FLOAT", 0.0),
                     (f"Shear{_i} End", "FLOAT", 1e7)]
# distribution: clumps / m2 by distance from the arena centre (piecewise linear). Near patch r < 25 m at 60 / m2
# (rule 8); the field thins fast beyond it (at grazing views >= 1 clump / m2 is already opaque) and every clump there
# is widened (COVER_REF / COVER_MAX) to keep the coverage seen from high cameras. Total <= GRASS_BUDGET.
DENSITY_TABLE = [(0.0, 60.0), (25.0, 60.0), (27.5, 8.0), (60.0, 2.2), (120.0, 0.6), (FAR_R, 0.2)]
# art-directed dense patches (x0, x1, y0, y1, clumps / m2, feather m): the S05 telephoto axis (reused by S24a / S25:
# camera x = 52 looking -X at the pair, y = the fighters' mid-point -0.25 .. -1.75) keeps a dense foreground between
# the lens and the arena - two rectangles hugging the 135 mm frustum (+-7.6 deg + 1.5 m margin), nothing behind the lens
DENSITY_PATCHES = [(14.0, 34.0, -8.0, 6.5, 26.0, 2.0), (34.0, 53.0, -5.0, 3.5, 26.0, 2.0)]
GRASS_BUDGET = 300000
COVER_REF = 12.0             # clumps / m2 below which clumps are widened by sqrt(COVER_REF / density) ...
COVER_MAX = 1.6              # ... up to this factor
PREVIEW_COVER_MAX = 2.0      # low preview densities widen every clump by sqrt(1 / Density) up to this factor
GUST_WAVE = 32.0             # m wavelength of the travelling gust bands (along the wind)
GUST_ACROSS = 70.0           # m feature size across the wind
WIND_LAG = 0.3               # s phase lag of the culm / plume bend behind the base lean
FLUTTER_SHEAR = 0.02        # per-clump flutter shear amplitude (x wamp): ~2 cm at the tip of a 1 m clump
FLUTTER_HZ = (0.9, 2.0)      # per-clump flutter frequency range (Hz of the wind clock)
GN_BEND_K = 0.8             # GN shear per rad of bend (tip offset / clump height; shader: culms 1.0, leaves 0.55)
TOP_LEAN_GAIN = 1.75         # culm / plume lean relative to the base lean (the GN shear applies the difference)
BASE_LEAN_MAX = 0.35         # rad cap of the rigid clump tilt from the wind
TILT_MAX = 0.75              # rad cap of the total rigid tilt (wind + parting + wet droop)
WAKE_STRENGTH = (0.6, 0.3)   # parting strength of the two wake samples (lag WAKE_LAGS s behind the rig)
WAKE_LAGS = (0.55, 1.15)
BURN_STANDING = 0.15         # fraction of the ring's clumps that stay standing (scorched only)
TOP_LIFE = 2.2               # s a severed top flies / tumbles before it lies on the stubble (then it stays: litter)
SHEAR_EDGE = (6.0, 1.2)      # ragged shear boundary: +- deg on the arc ends, +- m on the outer radius


def _piecewise(nb, x, table):
    """GN float field: piecewise-linear table [(x, y), ...] (constant beyond the ends), nested Switch nodes."""
    out = nb.value(float(table[-1][1]))
    for (x0, y0), (x1, y1) in reversed(list(zip(table, table[1:]))):
        seg = nb.map_range(x, x0, x1, y0, y1, clamp=True)
        out = nb.switch(nb.cmp('LESS_THAN', x, x1), out, seg)
    return out


def _density_np(x, y):
    """numpy mirror of the GN density field (clumps / m2 at density 1, masks ignored)."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    r = np.hypot(x, y)
    d = np.interp(r, [t[0] for t in DENSITY_TABLE], [t[1] for t in DENSITY_TABLE])
    for x0, x1, y0, y1, dn, fe in DENSITY_PATCHES:
        w = np.clip((x - x0) / fe, 0, 1) * np.clip((x1 - x) / fe, 0, 1) * np.clip((y - y0) / fe, 0, 1) * \
            np.clip((y1 - y) / fe, 0, 1)
        d = np.maximum(d, dn * w)
    return np.where(r < FAR_R, d, 0.0)


def expected_instances(density=1.0):
    """Analytic instance count of the grass distribution (ignores rock/pine masks)."""
    g = np.linspace(-FAR_R, FAR_R, 1601)
    X, Y = np.meshgrid(g, g)
    cell = (g[1] - g[0]) ** 2
    return float(_density_np(X, Y).sum() * cell * density)


def _density_field(nb, x, y, r):
    d = _piecewise(nb, r, DENSITY_TABLE)
    for x0, x1, y0, y1, dn, fe in DENSITY_PATCHES:
        w = nb.math('MULTIPLY', nb.math('MULTIPLY', nb.map_range(x, x0, x0 + fe), nb.map_range(x, x1, x1 - fe)),
                    nb.math('MULTIPLY', nb.map_range(y, y0, y0 + fe), nb.map_range(y, y1, y1 - fe)))
        d = nb.math('MAXIMUM', d, nb.math('MULTIPLY', w, dn))
    return d


def _gust_gn(nb, x, y, t, wx, wy):
    """Travelling gust bands (0..1) at world (x, y) and wind-clock time t: sine bands of GUST_WAVE m moving
    downwind at GUST_SPEED, their fronts warped and their strength modulated by slow noise (same formula as the
    ground shader's _gust_shader)."""
    along = nb.math('ADD', nb.math('MULTIPLY', x, wx), nb.math('MULTIPLY', y, wy))
    across = nb.math('SUBTRACT', nb.math('MULTIPLY', x, wy), nb.math('MULTIPLY', y, wx))
    s = nb.math('SUBTRACT', along, nb.math('MULTIPLY', t, GUST_SPEED))
    warp = nb.noise(nb.xyz(nb.math('DIVIDE', across, GUST_ACROSS), nb.math('DIVIDE', s, GUST_WAVE * 2.2),
                           nb.math('MULTIPLY', t, 0.03)), scale=1.0, detail=1.0, roughness=0.5)
    band = nb.math('SINE', nb.math('ADD', nb.math('MULTIPLY', s, 2 * math.pi / GUST_WAVE),
                                   nb.math('MULTIPLY', warp['Fac'], 5.0)))
    env = nb.noise(nb.xyz(nb.math('DIVIDE', across, GUST_ACROSS * 0.6),
                          nb.math('ADD', nb.math('DIVIDE', s, GUST_WAVE * 1.7), 17.3), 0.37),
                   scale=1.0, detail=1.0, roughness=0.5)
    envm = nb.map_range(env['Fac'], 0.35, 0.65, 0.2, 1.0, clamp=True)
    return nb.math('MULTIPLY', nb.map_range(band, -0.4, 0.9, 0.0, 1.0, clamp=True, interp='SMOOTHSTEP'), envm)


def _grass_tree():
    """GN_ENV_grass: distribute clumps on the terrain (static density field + patches, fixed count <= GRASS_BUDGET),
    per-clump height / species / yaw / coverage widening, jittered projected-distance LOD (lens boost capped at
    'LOD Focal Max'; off-frustum clumps -> LOD3 when 'Frustum LOD'), wind (base lean from the travelling gust bands,
    capped BASE_LEAN_MAX; the lagged bend + a per-clump flutter as a world-space shear of the instance about its base,
    x 'Wind Bend'), freeze window, parting around the two characters + their wakes, camera clearance (sphere or front
    cone around the ACTIVE camera), burn ring (noisy, ignition front, standing survivors), shear slots (per-clump cut
    time, stubble variant) and the severed-tops pool (a static subset of the same points, born at the cut time).
    Instances are never deleted (scale 0 / variant switch only)."""
    old = bpy.data.node_groups.get("GN_ENV_grass")
    if old is not None:
        bpy.data.node_groups.remove(old)
    ng = U.gn_new_tree("GN_ENV_grass", inputs=GRASS_INPUTS)
    nb = U.NB(ng)
    gi = nb.gi
    ter = nb.n('GeometryNodeObjectInfo', gi['Terrain'], False, transform_space='RELATIVE')
    pos = nb.n('GeometryNodeInputPosition')['Position']
    sp = nb.sep(pos)
    r = nb.vmath('LENGTH', nb.xyz(sp['X'], sp['Y'], 0.0))
    dens = _density_field(nb, sp['X'], sp['Y'], r)
    dens = nb.math('MULTIPLY', dens, nb.math('MULTIPLY', gi['Density'], nb.cmp('LESS_THAN', r, FAR_R)))
    dens = nb.math('MULTIPLY', dens, nb.attr("gmask"))
    dist = nb.n('GeometryNodeDistributePointsOnFaces', ter['Geometry'], distribute_method='RANDOM',
                Density=dens, Seed=gi['Seed'])
    pts = dist['Points']
    # ---- per-point constants
    idn = nb.n('GeometryNodeInputID')['ID']

    def rnd(seed, lo=0.0, hi=1.0):
        return nb.rand('FLOAT', lo, hi, seed=seed, id=idn)

    P = nb.n('GeometryNodeInputPosition')['Position']
    sP = nb.sep(P)
    rr = nb.vmath('LENGTH', nb.xyz(sP['X'], sP['Y'], 0.0))
    h_ar = nb.math('ADD', 0.95, nb.math('MULTIPLY', rnd(11), 0.20))
    h_fd = nb.math('ADD', 1.10, nb.math('MULTIPLY', rnd(11), 0.40))
    hgt = nb.mix(_gsmooth(nb, rr, ARENA_R, ARENA_R + 5.0), h_ar, h_fd)
    species = nb.math('FLOOR', nb.math('MULTIPLY', rnd(13), N_SPECIES - 0.001))
    yaw = rnd(17, 0.0, 2 * math.pi)
    nloc = nb.math('MAXIMUM', _density_field(nb, sP['X'], sP['Y'], rr), 0.05)
    cover = nb.math('MINIMUM', nb.math('SQRT', nb.math('MAXIMUM', nb.math('DIVIDE', COVER_REF, nloc), 1.0)), COVER_MAX)
    cover = nb.math('MULTIPLY', cover, nb.math('MINIMUM', nb.math('SQRT', nb.math(
        'DIVIDE', 1.0, nb.math('MAXIMUM', gi['Density'], 0.01))), PREVIEW_COVER_MAX))
    # ---- time: fx time with the freeze window removed (wind clock)
    t = gi['Time']
    tw = nb.math('ADD', nb.math('MINIMUM', t, gi['Freeze T0']),
                 nb.math('MAXIMUM', nb.math('SUBTRACT', t, gi['Freeze T1']), 0.0))
    # ---- wind: base lean (rigid clump tilt) + lagged culm / plume bend for the shader
    hd = nb.math('RADIANS', gi['Wind Dir'])
    wx, wy = nb.math('SINE', hd), nb.math('COSINE', hd)
    gust = _gust_gn(nb, sP['X'], sP['Y'], tw, wx, wy)
    gust_lag = _gust_gn(nb, sP['X'], sP['Y'], nb.math('SUBTRACT', tw, WIND_LAG), wx, wy)
    wind = gi['Wind']
    ph = rnd(19, 0.0, 2 * math.pi)
    fr = rnd(23, 1.2, 2.2)
    flut = nb.math('MULTIPLY', nb.math('SINE', nb.math('ADD', nb.math('MULTIPLY', tw, fr), ph)), 0.02)
    lean = nb.math('MINIMUM', nb.math('MULTIPLY', wind, nb.math('ADD', nb.math('ADD', 0.07, nb.math(
        'MULTIPLY', gust, 0.16)), flut)), BASE_LEAN_MAX)
    lean_lag = nb.math('MINIMUM', nb.math('MULTIPLY', wind, nb.math('ADD', 0.07, nb.math('MULTIPLY', gust_lag, 0.16))),
                       BASE_LEAN_MAX)
    bend_ang = nb.math('SUBTRACT', nb.math('MULTIPLY', lean_lag, TOP_LEAN_GAIN), lean)
    sway = nb.math('MULTIPLY', wind, nb.math('MULTIPLY', 0.03, nb.math('SINE', nb.math(
        'ADD', nb.math('MULTIPLY', tw, 1.7), rnd(29, 0.0, 6.2832)))))
    wet = gi['Wet']
    bx = nb.math('ADD', nb.math('MULTIPLY', wx, lean), nb.math('MULTIPLY', wy, sway))
    by = nb.math('SUBTRACT', nb.math('MULTIPLY', wy, lean), nb.math('MULTIPLY', wx, sway))
    droop = nb.math('MULTIPLY', wet, 0.28)
    bx = nb.math('ADD', bx, nb.math('MULTIPLY', nb.math('COSINE', yaw), droop))
    by = nb.math('ADD', by, nb.math('MULTIPLY', nb.math('SINE', yaw), droop))
    B = nb.xyz(bx, by, 0.0)
    # ---- parting around the two characters and their wakes (fades when the rig / sample is > 0.8 m up)
    parters = [("Char A", gi["Char A On"], 0.0, 1.0), ("Char B", gi["Char B On"], 0.07, 1.0),
               ("Wake A1", nb.bmath('AND', gi["Wake On"], gi["Char A On"]), 0.0, WAKE_STRENGTH[0]),
               ("Wake A2", nb.bmath('AND', gi["Wake On"], gi["Char A On"]), 0.0, WAKE_STRENGTH[1]),
               ("Wake B1", nb.bmath('AND', gi["Wake On"], gi["Char B On"]), 0.07, WAKE_STRENGTH[0]),
               ("Wake B2", nb.bmath('AND', gi["Wake On"], gi["Char B On"]), 0.07, WAKE_STRENGTH[1])]
    for ch, on, pin, strength in parters:
        oi = nb.n('GeometryNodeObjectInfo', gi[ch], False, transform_space='RELATIVE')
        cl = nb.sep(oi['Location'])
        v = nb.vmath('SUBTRACT', nb.xyz(sP['X'], sP['Y'], 0.0), nb.xyz(cl['X'], cl['Y'], 0.0))
        dd = nb.vmath('LENGTH', v)
        f = nb.map_range(dd, gi['Part Out'], nb.math('ADD', gi['Part In'], pin), 0.0, 1.0, clamp=True,
                         interp='SMOOTHSTEP')
        f = nb.math('MULTIPLY', f, nb.map_range(cl['Z'], 0.3, 0.8, 1.0, 0.0, clamp=True, interp='SMOOTHSTEP'))
        f = nb.math('MULTIPLY', nb.math('MULTIPLY', f, on), strength)
        B = nb.vmath('ADD', B, nb.vmath('SCALE', nb.vmath('NORMALIZE', v), scale=nb.math('MULTIPLY', f, gi['Part Angle'])))
    blen = nb.vmath('LENGTH', B)
    ang = nb.math('MINIMUM', blen, TILT_MAX)
    sB = nb.sep(B)
    axis = nb.vmath('NORMALIZE', nb.xyz(nb.math('MULTIPLY', sB['Y'], -1.0), sB['X'], 1e-6))
    tilt = nb.n('FunctionNodeAxisAngleToRotation', axis, ang)
    yrot = nb.n('FunctionNodeEulerToRotation', nb.xyz(0.0, 0.0, yaw))
    rot = nb.n('FunctionNodeRotateRotation', yrot, tilt, rotation_space='GLOBAL')
    # ---- camera clearance (active camera): sphere (Clear Near..Far) or front cone (Cone Angle > 0)
    cam = nb.n('GeometryNodeInputActiveCamera')
    coi = nb.n('GeometryNodeObjectInfo', cam, False, transform_space='RELATIVE')
    pc = nb.vmath('ADD', P, nb.xyz(0.0, 0.0, nb.math('MULTIPLY', hgt, 0.55)))
    vcam = nb.vmath('SUBTRACT', pc, coi['Location'])
    dcam = nb.vmath('LENGTH', vcam)
    s_sph = nb.map_range(dcam, gi['Clear Near'], gi['Clear Far'], 0.0, 1.0, clamp=True, interp='SMOOTHSTEP')
    fwd = nb.n('FunctionNodeRotateVector', (0.0, 0.0, -1.0), coi['Rotation'])
    al = nb.vmath('DOT_PRODUCT', vcam, fwd)
    latv = nb.vmath('SUBTRACT', vcam, nb.vmath('SCALE', fwd, scale=al))
    lat = nb.vmath('LENGTH', latv)
    rad = nb.math('ADD', gi['Cone Radius'], nb.math('MULTIPLY', nb.math('MAXIMUM', al, 0.0),
                                                     nb.math('TANGENT', nb.math('RADIANS', gi['Cone Angle']))))
    in_lat = nb.map_range(nb.math('DIVIDE', lat, nb.math('MAXIMUM', rad, 1e-3)), 0.75, 1.15, 1.0, 0.0, clamp=True,
                          interp='SMOOTHSTEP')
    in_len = nb.math('MULTIPLY', nb.map_range(al, -0.3, 0.1, 0.0, 1.0, clamp=True),
                     nb.map_range(al, nb.math('SUBTRACT', gi['Cone Length'], 0.8), gi['Cone Length'], 1.0, 0.0,
                                  clamp=True, interp='SMOOTHSTEP'))
    s_cone = nb.math('SUBTRACT', 1.0, nb.math('MULTIPLY', in_lat, in_len))
    s_clear = nb.switch(nb.cmp('GREATER_THAN', gi['Cone Angle'], 0.0), s_sph, s_cone)
    s_min = nb.map_range(dcam, gi['Clear Min'], nb.math('ADD', gi['Clear Min'], 0.5), 0.0, 1.0, clamp=True,
                         interp='SMOOTHSTEP')
    s_clear = nb.math('MINIMUM', s_clear, s_min)
    # ---- LOD by projected distance (35 mm equivalent) from the active camera; every clump's thresholds are
    # jittered by +-LOD_JITTER (a switch is a wide stochastic blend) and all LODs keep the same leaf / culm / plume
    # area (_clump_strands), so a switch changes neither the mean colour nor the coverage
    focal = nb.math('MINIMUM', nb.n('GeometryNodeCameraInfo', cam)['Focal Length'], gi['LOD Focal Max'])
    mproj = nb.math('DIVIDE', nb.math('MULTIPLY', dcam, 35.0), nb.math('MAXIMUM', focal, 1.0))
    mproj = nb.math('DIVIDE', mproj, rnd(43, 1.0 - LOD_JITTER, 1.0 + LOD_JITTER))
    lod = nb.value(float(len(CLUMP_LODS) - 1))
    for li in range(len(CLUMP_LODS) - 2, -1, -1):
        lod = nb.switch(nb.cmp('LESS_THAN', mproj, CLUMP_LODS[li][0]), lod, float(li))
    # clumps outside the (padded) view frustum of the active camera only matter through the shadows they cast
    # into the frame: coarsest LOD (the view pass culls them anyway; the key light's shadow maps otherwise render
    # every off-screen clump at the lens-boosted LOD - 62 M triangles for a 135 mm shot)
    camd = nb.n('GeometryNodeCameraInfo', cam)
    thw = nb.math('DIVIDE', nb.math('MULTIPLY', nb.sep(U.socket_out(camd.node, "Sensor"))['X'], 0.5),
                  nb.math('MAXIMUM', U.socket_out(camd.node, "Focal Length"), 1.0))
    thw = nb.math('MULTIPLY', thw, 1.0 + FRUSTUM_PAD[1])
    thh = nb.math('MULTIPLY', thw, float(config.RES_Y) / float(config.RES_X))
    xc = nb.math('ABSOLUTE', nb.vmath('DOT_PRODUCT', vcam, nb.n('FunctionNodeRotateVector', (1.0, 0.0, 0.0),
                                                                    coi['Rotation'])))
    yc = nb.math('ABSOLUTE', nb.vmath('DOT_PRODUCT', vcam, nb.n('FunctionNodeRotateVector', (0.0, 1.0, 0.0),
                                                                    coi['Rotation'])))
    zc = nb.math('MAXIMUM', al, 0.0)
    in_view = nb.bmath('AND', nb.cmp('GREATER_THAN', al, -FRUSTUM_PAD[0]), nb.bmath(
        'AND', nb.cmp('LESS_THAN', xc, nb.math('ADD', nb.math('MULTIPLY', thw, zc), FRUSTUM_PAD[0])),
        nb.cmp('LESS_THAN', yc, nb.math('ADD', nb.math('MULTIPLY', thh, zc), FRUSTUM_PAD[0]))))
    off_view = nb.bmath('AND', gi['Frustum LOD'], nb.bmath('NOT', in_view))
    lod = nb.switch(off_view, lod, float(len(CLUMP_LODS) - 1))
    lod = nb.switch(nb.cmp('GREATER_EQUAL', gi['LOD Force'], 0, 'INT'), lod, gi['LOD Force'])
    variant = nb.math('ADD', species, nb.math('MULTIPLY', lod, float(N_SPECIES)))
    # ---- burn ring: radius / width modulated by noise, ignition front spreading from the ring's centre line,
    # BURN_STANDING survivors, thin ember front + a few smouldering clumps; Burn Amount (keyed) adds on top
    bc = nb.sep(gi['Burn Center'])
    bxy = nb.xyz(nb.math('SUBTRACT', sP['X'], bc['X']), nb.math('SUBTRACT', sP['Y'], bc['Y']), 0.0)
    bd = nb.vmath('LENGTH', bxy)
    n1 = nb.noise(nb.vmath('SCALE', bxy, scale=1.0 / 6.5), scale=1.0, detail=2.0, roughness=0.5)
    n2 = nb.noise(nb.vmath('ADD', nb.vmath('SCALE', bxy, scale=1.0 / 7.5), (13.1, 7.7, 0.0)), scale=1.0, detail=1.0)
    r_eff = nb.math('ADD', gi['Burn Radius'], nb.math('MULTIPLY', nb.math('SUBTRACT', n1['Fac'], 0.5), 6.0))
    w_eff = nb.math('MULTIPLY', gi['Burn Width'], nb.math('ADD', 1.0, nb.math('MULTIPLY', nb.math(
        'SUBTRACT', n2['Fac'], 0.5), 1.4)))
    u_ring = nb.math('DIVIDE', nb.math('ABSOLUTE', nb.math('SUBTRACT', bd, r_eff)),
                     nb.math('MAXIMUM', nb.math('MULTIPLY', w_eff, 0.5), 0.05))
    u_ring = nb.math('MULTIPLY', u_ring, rnd(31, 0.85, 1.15))
    ring = nb.map_range(u_ring, 0.8, 1.25, 1.0, 0.0, clamp=True, interp='SMOOTHSTEP')
    t_ign = nb.math('ADD', gi['Burn T0'], nb.math('ADD', nb.math('MULTIPLY', gi['Burn Ramp'], nb.math(
        'ADD', 0.15, nb.math('MULTIPLY', nb.math('MINIMUM', u_ring, 1.0), 0.85))), rnd(33, 0.0, 0.35)))
    bt = _gsmooth(nb, t, t_ign, nb.math('ADD', t_ign, 0.5))
    bt = nb.math('MULTIPLY', bt, nb.cmp('LESS_THAN', t, gi['Burn End']))
    standing = nb.cmp('LESS_THAN', rnd(35), BURN_STANDING)
    burn = nb.math('MINIMUM', nb.math('MULTIPLY', ring, nb.math('ADD', bt, gi['Burn Amount'])), 1.0)
    burn = nb.switch(standing, burn, nb.math('MINIMUM', burn, 0.3))
    front = nb.math('MULTIPLY', _gsmooth(nb, t, nb.math('SUBTRACT', t_ign, 0.1), nb.math('ADD', t_ign, 0.15)),
                    nb.map_range(t, nb.math('ADD', t_ign, 0.3), nb.math('ADD', t_ign, 1.2), 1.0, 0.0, clamp=True,
                                 interp='SMOOTHSTEP'))
    tb_end = nb.math('ADD', gi['Burn T0'], gi['Burn Ramp'])
    smoulder = nb.math('MULTIPLY', nb.math('MULTIPLY', nb.cmp('LESS_THAN', rnd(39), 0.12), 0.35),
                       nb.map_range(t, tb_end, nb.math('ADD', tb_end, EMBER_DECAY), 1.0, 0.0, clamp=True,
                                    interp='SMOOTHSTEP'))
    smoulder = nb.math('MULTIPLY', smoulder, nb.cmp('GREATER_THAN', t, nb.math('ADD', t_ign, 0.3)))
    ember = nb.math('MULTIPLY', ring, nb.math('MAXIMUM', front, smoulder))
    ember = nb.math('MULTIPLY', ember, nb.math('SUBTRACT', 1.0, nb.math('MULTIPLY', standing, 0.7)))
    ember = nb.math('MAXIMUM', ember, nb.math('MULTIPLY', nb.math('MULTIPLY', ring, gi['Burn Amount']),
                                              nb.math('SUBTRACT', 1.0, _gsmooth(nb, gi['Burn Amount'], 0.8, 1.0))))
    # ---- shear slots: per-clump cut time T0 + dist / speed inside the arc; tcut = earliest active slot
    cut = nb.value(0.0)
    tcut = nb.value(1e9)
    org = nb.value(0.0)
    orgs = []
    # ragged boundary: the arc ends and the outer radius wander by +-SHEAR_EDGE (noise, ~3 m features) - a physical
    # cut, not a ruler-straight sector
    en = nb.noise(nb.vmath('SCALE', nb.xyz(sP['X'], sP['Y'], 0.0), scale=0.33), scale=1.0, detail=2.0, roughness=0.5)
    en2 = nb.noise(nb.vmath('ADD', nb.vmath('SCALE', nb.xyz(sP['X'], sP['Y'], 0.0), scale=0.27), (7.3, 1.9, 0.0)),
                   scale=1.0, detail=2.0, roughness=0.5)
    e_ang = nb.math('MULTIPLY', nb.math('SUBTRACT', en['Fac'], 0.5), 2.0 * SHEAR_EDGE[0] * 2.5)
    e_rad = nb.math('MULTIPLY', nb.math('SUBTRACT', en2['Fac'], 0.5), 2.0 * SHEAR_EDGE[1] * 2.5)
    for i in range(1, N_SHEAR_SLOTS + 1):
        o = nb.sep(gi[f"Shear{i} Origin"])
        dx = nb.math('SUBTRACT', sP['X'], o['X'])
        dy = nb.math('SUBTRACT', sP['Y'], o['Y'])
        dsh = nb.vmath('LENGTH', nb.xyz(dx, dy, 0.0))
        bearing = nb.math('DEGREES', nb.math('ARCTAN2', dx, dy))
        dang = nb.math('ABSOLUTE', nb.math('SUBTRACT', nb.math('FLOORED_MODULO', nb.math(
            'ADD', nb.math('SUBTRACT', bearing, gi[f"Shear{i} Facing"]), 180.0), 360.0), 180.0))
        in_arc = nb.cmp('LESS_EQUAL', dang, nb.math('ADD', nb.math('MULTIPLY', gi[f"Shear{i} Arc"], 0.5), e_ang))
        in_r = nb.cmp('LESS_EQUAL', dsh, nb.math('ADD', gi[f"Shear{i} Radius"], e_rad))
        region = nb.bmath('AND', nb.bmath('AND', in_arc, in_r), nb.cmp('LESS_THAN', gi[f"Shear{i} T0"], 1e6))
        tci = nb.math('ADD', gi[f"Shear{i} T0"], nb.math('DIVIDE', dsh, nb.math('MAXIMUM', gi[f"Shear{i} Speed"], 0.01)))
        on = nb.bmath('AND', region,
                      nb.bmath('AND', nb.cmp('GREATER_EQUAL', t, tci), nb.cmp('LESS_THAN', t, gi[f"Shear{i} End"])))
        cut = nb.math('MAXIMUM', cut, on)
        tci_r = nb.switch(region, 1e9, tci)
        first = nb.cmp('LESS_THAN', tci_r, tcut)
        org = nb.switch(first, org, float(i))
        tcut = nb.math('MINIMUM', tcut, tci_r)
        orgs.append(gi[f"Shear{i} Origin"])
    stub = nb.bmath('OR', nb.cmp('GREATER_THAN', cut, 0.5), nb.cmp('GREATER_THAN', burn, 0.45))
    variant = nb.switch(stub, variant, nb.math('ADD', variant, float(N_VARIANTS)))
    # ---- scale
    sxy = nb.math('MULTIPLY', nb.math('MULTIPLY', hgt, rnd(37, 0.85, 1.15)), cover)
    sz = nb.math('MULTIPLY', hgt, nb.math('SUBTRACT', 1.0, nb.math('MULTIPLY', burn, 0.55)))
    sz = nb.math('MULTIPLY', sz, nb.math('SUBTRACT', 1.0, nb.math('MULTIPLY', wet, 0.08)))
    sxy = nb.math('MULTIPLY', sxy, s_clear)
    sz = nb.math('MULTIPLY', sz, s_clear)
    # ---- instance attributes (stored on points: they propagate to the instances) for the shader
    bend = nb.xyz(nb.math('MULTIPLY', wx, bend_ang), nb.math('MULTIPLY', wy, bend_ang), 0.0)
    wamp = nb.math('MULTIPLY', wind, nb.math('ADD', 0.35, nb.math('MULTIPLY', gust, 0.65)))
    pts = nb.store(pts, "gust", gust, 'FLOAT', 'POINT')
    pts = nb.store(pts, "burn", burn, 'FLOAT', 'POINT')
    pts = nb.store(pts, "ember", ember, 'FLOAT', 'POINT')
    pts = nb.store(pts, "var", rnd(41), 'FLOAT', 'POINT')
    # GN wind shear per clump (read on the instance domain below): the lagged bend x GN_BEND_K + a per-clump flutter
    # (FLUTTER_SHEAR x wamp at FLUTTER_HZ: a whole clump shaking at the old per-strand 2-5 Hz reads as jitter and
    # smears near the lens under motion blur) - stored once on the points
    fq = rnd(61, *FLUTTER_HZ)
    fph = rnd(63, 0.0, 2 * math.pi)
    fa = nb.math('ADD', nb.math('MULTIPLY', nb.math('MULTIPLY', tw, fq), 2 * math.pi), fph)
    famp_g = nb.math('MULTIPLY', wamp, FLUTTER_SHEAR)
    flt = nb.xyz(nb.math('MULTIPLY', famp_g, nb.math('SINE', fa)),
                 nb.math('MULTIPLY', famp_g, nb.math('COSINE', nb.math('ADD', nb.math('MULTIPLY', fa, 0.83), fph))), 0.0)
    pts = nb.store(pts, "shr", nb.vmath('ADD', nb.vmath('SCALE', bend, scale=GN_BEND_K), flt), 'FLOAT_VECTOR', 'POINT')
    coll = nb.n('GeometryNodeCollectionInfo', gi['Clumps'], True, True, transform_space='RELATIVE')
    inst = nb.n('GeometryNodeInstanceOnPoints', Points=pts, Instance=coll, Pick_Instance=True,
                Instance_Index=nb.math('ROUND', variant), Rotation=rot['Rotation'], Scale=nb.xyz(sxy, sxy, sz))
    # ---- second wind level in GN (instance domain): a world-space SHEAR of the whole clump about its base,
    # x' = x + s.x h, y' = y + s.y h (h = height above the base), s = bend x GN_BEND_K (the tip offset of the old
    # shader bend at hz = 1)
    s_b = nb.vmath('SCALE', nb.attr("shr", 'FLOAT_VECTOR'), scale=gi['Wind Bend'])
    sb = nb.sep(s_b)
    # z scale of the shear chosen so the (tilted) clump axis keeps its length: |z1| = |z0| (a bending culm does not
    # stretch; its tip drops), floored at 20 % of the height
    m0 = nb.n('GeometryNodeInstanceTransform')
    z0 = nb.n('FunctionNodeTransformDirection', (0.0, 0.0, 1.0), m0)
    sz0 = nb.sep(z0)
    h0sq = nb.vmath('DOT_PRODUCT', z0, z0)
    zxy = nb.vmath('ADD', nb.xyz(sz0['X'], sz0['Y'], 0.0), nb.vmath('SCALE', s_b, scale=sz0['Z']))
    z1z = nb.math('SQRT', nb.math('MAXIMUM', nb.math('SUBTRACT', h0sq, nb.vmath('DOT_PRODUCT', zxy, zxy)),
                                  nb.math('MULTIPLY', h0sq, 0.04)))
    szc = nb.math('DIVIDE', z1z, nb.math('MAXIMUM', sz0['Z'], 1e-4))
    pz = nb.sep(nb.n('GeometryNodeInputPosition'))['Z']
    shm = nb.n('FunctionNodeCombineMatrix')
    for k, v in (("Column 3 Row 1", sb['X']), ("Column 3 Row 2", sb['Y']), ("Column 3 Row 3", szc),
                 ("Column 4 Row 1", nb.math('MULTIPLY', nb.math('MULTIPLY', sb['X'], pz), -1.0)),
                 ("Column 4 Row 2", nb.math('MULTIPLY', nb.math('MULTIPLY', sb['Y'], pz), -1.0)),
                 ("Column 4 Row 3", nb.math('MULTIPLY', nb.math('SUBTRACT', 1.0, szc), pz))):
        nb.set(U.socket_in(shm.node, k), v)
    mtx = nb.n('FunctionNodeMatrixMultiply', shm, m0)
    inst = nb.n('GeometryNodeSetInstanceTransform', inst, True, mtx)
    # ---- severed tops (shear): a STATIC subset of the same points (the shear regions never change during the film,
    # so the pool's count and order are constant), born at the clump's cut time, thrown up and outward, tumbling,
    # settling into the stubble after TOP_LIFE s (scale 0 when unborn / settled - rule 3)
    tsel = nb.cmp('LESS_THAN', tcut, 1e8)
    tpts = nb.n('GeometryNodeSeparateGeometry', pts, tsel, domain='POINT')['Selection']
    trel = nb.math('SUBTRACT', t, tcut)
    tc = nb.math('MAXIMUM', trel, 0.0)
    o_sel = orgs[0]
    for i in range(2, N_SHEAR_SLOTS + 1):
        o_sel = nb.switch(nb.cmp('GREATER_THAN', org, i - 0.5), o_sel, orgs[i - 1], 'VECTOR')
    so = nb.sep(o_sel)
    radial = nb.vmath('NORMALIZE', nb.xyz(nb.math('SUBTRACT', sP['X'], so['X']), nb.math('SUBTRACT', sP['Y'], so['Y']),
                                         1e-4))
    srad = nb.sep(radial)
    tang = nb.xyz(nb.math('MULTIPLY', srad['Y'], -1.0), srad['X'], 0.0)
    v0 = nb.vmath('ADD', nb.vmath('ADD', nb.vmath('SCALE', radial, scale=rnd(51, 1.6, 3.6)),
                                  nb.vmath('SCALE', tang, scale=rnd(53, -0.7, 0.7))),
                  nb.xyz(0.0, 0.0, rnd(55, 2.4, 4.2)))
    kdrag = 1.3                  # light, draggy heads: up ~0.4-0.8 m above the cut, 1-2 m out, tumbling
    e = nb.math('DIVIDE', nb.math('SUBTRACT', 1.0, nb.math('EXPONENT', nb.math('MULTIPLY', tc, -kdrag))), kdrag)
    disp = nb.vmath('ADD', nb.vmath('SCALE', v0, scale=e),
                    nb.xyz(0.0, 0.0, nb.math('MULTIPLY', nb.math('MULTIPLY', tc, tc), -3.0)))
    cut_pt = nb.n('FunctionNodeRotateVector', nb.xyz(0.0, 0.0, nb.math('MULTIPLY', STUB_Z, sz)), rot['Rotation'])
    tp = nb.vmath('ADD', cut_pt, disp)
    stp = nb.sep(tp)
    floor_z = nb.math('MULTIPLY', sz, STUB_Z * 0.92)          # they come to rest ON the stubble (litter)
    tp = nb.xyz(stp['X'], stp['Y'], nb.math('MAXIMUM', stp['Z'], floor_z))
    tumble = nb.n('FunctionNodeAxisAngleToRotation', tang, nb.math('MINIMUM', nb.math('MULTIPLY', tc, rnd(57, 3.0, 7.0)),
                                                                  1.35))
    trot = nb.n('FunctionNodeRotateRotation', rot['Rotation'], tumble, rotation_space='GLOBAL')
    tsc = cut                    # 1 from the clump's cut time while it stays cut (Shear End = regrowth), else 0
    # every per-top field is evaluated at the CLUMP position (before the top is moved) and carried as attributes:
    # after Set Position, position-dependent fields (cut region, cut time, height, clearance) would be re-evaluated at
    # the flying top's position (tops flung across the region edge would vanish)
    tpts = nb.store(tpts, "k_rot", nb.n('FunctionNodeRotationToEuler', trot['Rotation'])['Euler'], 'FLOAT_VECTOR',
                    'POINT')
    tpts = nb.store(tpts, "k_sc", nb.xyz(nb.math('MULTIPLY', sxy, tsc), nb.math('MULTIPLY', sxy, tsc),
                                         nb.math('MULTIPLY', sz, tsc)), 'FLOAT_VECTOR', 'POINT')
    tpts = nb.store(tpts, "k_idx", nb.math('ADD', species, float(2 * N_VARIANTS)), 'FLOAT', 'POINT')
    tpts = nb.n('GeometryNodeSetPosition', tpts, Offset=tp)
    # ... except the CAMERA clearance, which must also hold at the top's own (flung) position: tops land 1-2 m out
    # from their clump, so a low camera inside a shear region (S12-S14) otherwise gets full-size tops right at
    # the lens (integration: _demo D03b, severed tops 0.14 m from the lens). Sphere mode + Clear Min (the front
    # cone of S03 happens before any shear).
    dtop = nb.vmath('LENGTH', nb.vmath('SUBTRACT', nb.n('GeometryNodeInputPosition')['Position'], coi['Location']))
    c_top = nb.map_range(dtop, gi['Clear Near'], gi['Clear Far'], 0.0, 1.0, clamp=True, interp='SMOOTHSTEP')
    c_top = nb.switch(nb.cmp('GREATER_THAN', gi['Cone Angle'], 0.0), c_top, 1.0)
    c_top = nb.math('MINIMUM', c_top, nb.map_range(dtop, gi['Clear Min'], nb.math('ADD', gi['Clear Min'], 0.5),
                                                   0.0, 1.0, clamp=True, interp='SMOOTHSTEP'))
    tinst = nb.n('GeometryNodeInstanceOnPoints', Points=tpts, Instance=coll, Pick_Instance=True,
                 Instance_Index=nb.math('ROUND', nb.attr("k_idx")),
                 Rotation=nb.n('FunctionNodeEulerToRotation', nb.attr("k_rot", 'FLOAT_VECTOR'))['Rotation'],
                 Scale=nb.vmath('SCALE', nb.attr("k_sc", 'FLOAT_VECTOR'), scale=c_top))
    joined = nb.n('GeometryNodeJoinGeometry', tinst, inst)
    nb.link(joined, nb.go['Geometry'])
    nb.layout()
    return ng


def _gsmooth(nb, v, a, b):
    return nb.map_range(v, a, b, 0.0, 1.0, clamp=True, interp='SMOOTHSTEP')


WAKE_NAMES = {"Wake A1": "ENV_wake_SHINOBI_1", "Wake A2": "ENV_wake_SHINOBI_2",
              "Wake B1": "ENV_wake_SAINT_1", "Wake B2": "ENV_wake_SAINT_2"}
WAKE_PARK = (0.0, 0.0, 50.0)          # parked (faded: > 0.8 m up) until bake_wake keys them


def _build_grass(sc, density):
    """ENV_grass: an empty mesh object carrying GN_ENV_grass (instances only, never realized) + the four wake
    empties (parked until bake_wake)."""
    ob = bpy.data.objects.get(N_GRASS)
    if ob is not None:
        return ob
    mat = _grass_material()
    col, _ = _build_clumps(mat)
    ob = U.mesh_from_data(N_GRASS, np.zeros((0, 3)), collection=COLL)
    ng = _grass_tree()
    wakes = {}
    for inp, name in WAKE_NAMES.items():
        e = bpy.data.objects.get(name) or U.new_empty(name, WAKE_PARK, COLL, 'SPHERE', 0.3)
        e.location = WAKE_PARK
        wakes[inp] = e
    U.gn_modifier(ob, ng, Terrain=bpy.data.objects[N_TERRAIN], Clumps=col, Density=float(density), **wakes)
    U.film_clock().drive_gn_input(ob, "Time")
    ob.visible_shadow = False
    ob.color = (0.62, 0.48, 0.25, 1.0)
    return ob
