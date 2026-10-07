"""
acts/prologue.py - PROLOGUE lane (S01-S04, frames 1-432) of Duel in the Silver Grass..
(binding; deviations are listed there under '## Implementation notes').

    Blender -b --factory-startup --python-exit-code 1 --python codecinema/productions/silvergrass/blender/build_scene.py -- --lanes prologue \
        --quality preview

Cuts (all hard, camera always on the +X side of the Y axis, env state dusk_gold throughout, no clash / flash /
slow motion in the span):
  S01  1-96     black (post), sound only: wind, a distant blade ring (40), a far thunder roll (70); a static clone of
                the S02 opening camera exists only for the marker + the event pan/dist.
  S02  97-240   20 mm crane push-in, sky dominant: the elder a tiny silhouette (hat + slung spear) waiting at the
                centre, the lone pine on its rise; the shinobi walks in from the bottom of frame (main title 140-236).
  S03  241-336  28 mm knee-height tracking behind the shinobi through the grass (front-cone clearance), tilting up to
                his back as he stops (288); name card 'Saku' 288-334.  Walk ellipsis across the S02->S03 cut (5.3 m).
  S04  337-432  85 mm MCU push on the elder: head lift under the hat brim (347-378, chin-up -13 deg), eye glint 392;
                name card 'Tenkosai' 380-430.  Leaves at config.HANDOFF[432].
"""

import math
import zlib

import bpy

import config
import bl_util as U
from acts import sub_cuts

LANE = "prologue"
SPAN = tuple(config.lane_span(LANE))                       # (1, 432)
CUTS = sub_cuts(LANE)                                      # the config shots S01-S04 (no sub-cuts)
CUT = {c: (a, b) for c, a, b in CUTS}
H432 = config.HANDOFF[SPAN[1]]

# key moments (film frames) for the beat grid and sub-cuts
F = dict(
    ring=40, thunder=70,                    # S01 sound-only omens
    walk2=(73, 240),                         # S02 walk (starts inside black S01 so he is in stride at 97)
    walk3=(241, 290), stop_step=288,         # S03 walk -> stopping step -> settled
    ready=300,                               # shinobi_stop_ready reached (head lifts to the elder)
    lift0=347, lift_neck=375, lift_head0=350, lift_end=378,   # S04 head lift
    glint=CUT["S04"][0] + 55,                # 392 (score's koto note)
    title=config.MUSIC_CUES["title"],        # 179
)
WALK_SPEED = 1.3                             # m/s, the S02 walk
# pre-roll so he passes config.SHINOBI_WALK_FROM (0, -20) at the S02 cut (97): (0, -21.3)
SH_WALK_START = (config.SHINOBI_WALK_FROM[0],
                 config.SHINOBI_WALK_FROM[1] - WALK_SPEED * (CUT["S02"][0] - F["walk2"][0]) / config.FPS)
SH_S02_END = (0.0, -12.25)                   # @240 (CONSTANT - the ellipsis)
SH_S03_START = (0.0, -6.96)                  # @241
SH_STOP = tuple(H432["shinobi"]["pos"])      # (0, -4.5)
SA_POS = tuple(H432["saint"]["pos"])         # (0, 4.0) = config.SAINT_START
WIND_HEADING = 250.0                         # compass bearing the wind blows TOWARD (streams tails screen-left)
HEAD_EXT = -6.0                              # elder's end-of-lift head flexion (deg)
FILL_W = 60.0                                # S04_beard_fill energy (W)
RIM_W = 60.0                                 # S03_rim energy (W)


def _seed(tag):
    """Deterministic seed (zlib.crc32, never hash())."""
    return zlib.crc32(f"prologue:{tag}".encode()) & 0x7FFFFFFF


def _mods():
    import characters as CH
    import moves as M
    import poses as PZ
    return CH, M, PZ


# =============================================================================================================
# local poses - built on the library's relaxed_saya (left fist on the saya via IK)
# =============================================================================================================
def _spec_from(base, body_over=None, hips=None, legs=None, name=None, rig=None):
    """Resolved pose spec = library pose `base` for `rig` with body bones replaced by `body_over` (degrees)."""
    import copy
    _, _, PZ = _mods()
    sp = copy.deepcopy(PZ.resolve(base, rig))
    for b, r in (body_over or {}).items():
        sp["body"][b] = tuple(float(v) for v in r)
    if hips is not None:
        sp["hips_offset"] = tuple(hips)
    if legs is not None:
        sp["legs"] = legs
    sp["_name"] = name or base
    return sp


def _elder_wait_bowed(rig):
    """Waiting under the hat, head bowed: neck +8, head +18, chest +3, spine +2 (flexion), left fist on the saya,
    right arm hanging, feet as relaxed_saya."""
    base = _spec_from("relaxed_saya", rig=rig)
    b = base["body"]
    over = {"spine": (2.0, b["spine"][1], 0.0), "chest": (3.0, b["chest"][1], 0.0),
            "neck": (8.0, b["neck"][1], 0.0), "head": (18.0, b["head"][1], 0.0)}
    return _spec_from("relaxed_saya", over, hips=(0.0, -0.02, -0.01), name="elder_wait_bowed", rig=rig)


def _elder_wait_level(rig):
    """Head lifted (the S04 reveal / HANDOFF[432] pose): neck 0, head -13 (chin raised, looking down his nose -
    the eye clears the brim), chest 0, shoulders squared (Z -2)."""
    base = _spec_from("relaxed_saya", rig=rig)
    b = base["body"]
    over = {"spine": (1.0, b["spine"][1], 0.0), "chest": (0.0, b["chest"][1], 0.0),
            "neck": (0.0, b["neck"][1], 0.0), "head": (HEAD_EXT, b["head"][1], 0.0),
            "shoulder.L": (0.0, 0.0, -2.0), "shoulder.R": (0.0, 0.0, 2.0)}     # both dropped (Z mirrored L/R)
    return _spec_from("relaxed_saya", over, hips=(0.0, -0.02, -0.01), name="elder_wait_level", rig=rig)


def _shinobi_stop_ready(rig):
    """Stopped, ready but unhurried: chest open (-1), head -2 (eyes on the elder), shoulders dropped, left fist on
    the saya, right arm hanging; legs/hips exactly as the walk's closing step left them (feet stay planted)."""
    _, _, PZ = _mods()
    base = _spec_from("relaxed_saya", rig=rig)
    b = base["body"]
    over = {"spine": (0.0, b["spine"][1], 0.0), "chest": (-1.0, b["chest"][1], 0.0),
            "neck": (0.0, b["neck"][1], 0.0), "head": (-2.0, b["head"][1], 0.0),
            "shoulder.L": (0.0, 0.0, -1.0), "shoulder.R": (0.0, 0.0, 1.0)}
    legs = {"R": dict(ball=(-0.095, 0.0), yaw=-6.0, heel=0.0, lift=0.0, air=False),
            "L": dict(ball=(0.095, 0.0), yaw=6.0, heel=0.0, lift=0.0, air=False)}
    return _spec_from("relaxed_saya", over, hips=(0.0, -0.02, 0.0), legs=legs, name="shinobi_stop_ready", rig=rig)


def _key_spec(rig, f, spec, hands="pose", legs=True, interp="BEZIER"):
    _, _, PZ = _mods()
    return PZ.key_pose(rig, f, None, spec=spec, hands=hands, legs=legs, feet=legs, interp=interp)


def _local_breath(rig, f0, f1, amp, period, phase=0.0):
    """Breathing on a hold: chest X +-amp (deg) at quarter periods, shoulders rise on the inhale (Z -+0.3 amp).
    The base values are sampled BEFORE any key is added (so the overlay never compounds)."""
    _, _, PZ = _mods()
    frames = []
    q = period / 4.0
    k = 0
    while True:
        f = f0 + q * k
        if f > f1:
            break
        frames.append(round(f, 2))
        k += 1
    bones = ("chest", "shoulder.L", "shoulder.R")
    base = {f: {b: PZ.current_rot(rig, b, f) for b in bones} for f in frames}
    for i, f in enumerate(frames):
        s = math.sin(2.0 * math.pi * (f - f0) / period + phase)
        d = {"chest": (-amp * s, 0.0, 0.0), "shoulder.L": (0.0, 0.0, 0.3 * amp * s),
             "shoulder.R": (0.0, 0.0, -0.3 * amp * s)}
        for b in bones:
            v = tuple(c + e for c, e in zip(base[f][b], d[b]))
            U.key(rig.pose.bones[b], "rotation_euler", f, tuple(math.radians(x) for x in v), interp="BEZIER")


# =============================================================================================================
# choreography
# =============================================================================================================
def entering_state(SH, SA):
    """Film start: key every state channel at frame 1 (the first key of a visibility channel extrapolates
    backwards).  Leaves exactly config.HANDOFF[432] (nothing changes state inside the prologue)."""
    CH, M, PZ = _mods()
    f0 = SPAN[0]
    for r in (SH, SA):
        CH.set_weapon_state(r, f0, "sheathed")
        CH.set_arm_mode(r, f0, "fk")
    CH.set_weapon_state(SA, f0, "slung")
    CH.set_hat(f0, "on")
    CH.set_costume(f0, haori=True)
    CH.set_beard_cord(f0, False)
    CH.set_kunai_in_hand(f0, False)
    for i in (1, 2, 3):
        ob = bpy.data.objects.get(f"SHINOBI_kunai_{i}")
        if ob is not None:
            U.key_visible(ob, f0, False)
    CH.set_spear_grip(f0, 0.35, 0.95)
    CH.set_hat_tilt(f0, 0.0, 0.0)
    for r in (SH, SA):
        CH.set_left_hand(r, f0, "saya")
        CH.key_saya(r, f0, pull=0.0, roll=0.0)


def _contacts(rig, f0, f1):
    """[(frame, side)] of the planted footfalls registered by moves.walk inside [f0, f1] (world keys, heel 0)."""
    _, _, PZ = _mods()
    out = []
    for k in PZ.FOOT_KEYS.get(rig.name, []):
        if f0 <= k["frame"] <= f1 and k["space"] == "WORLD" and abs(k["heel"]) < 1e-6 and not k["air"]:
            out.append((k["frame"], k["side"]))
    return sorted(set(out))


def _local_plant(rig, f, side, xy, z, heel=0.0):
    """Register a WORLD foot plant (ball) for the foot bake - the cut-aware counterpart of moves.plant."""
    _, _, PZ = _mods()
    PZ.register_foot(rig, f, side, (xy[0], xy[1], z), 180.0, heel, space="WORLD", src="walk")


def _last_plant_y(rig, side, f):
    """y of the last planted (heel 0, WORLD) footfall of `side` at or before f."""
    _, _, PZ = _mods()
    ks = [k for k in PZ.FOOT_KEYS.get(rig.name, []) if k["side"] == side and k["space"] == "WORLD"
          and k["frame"] <= f and abs(k["heel"]) < 1e-6 and not k["air"]]
    return max(ks, key=lambda k: k["frame"])["ball"][1]


def _arm_swing(rig, f0, f1, amp=12.0, elbow=(15.0, 25.0), until=None):
    """Right-arm swing riding the walk (the left fist stays on the saya): upper_arm.R X +-amp in antiphase with the
    right leg (right foot planted in front -> right arm back), forearm.R bends a little more on the forward swing.
    Keys at every footfall and half-way between (passing = arm hanging)."""
    _, _, PZ = _mods()
    cs = _contacts(rig, f0, f1)
    if not cs:
        return
    base_u = PZ.current_rot(rig, "upper_arm.R", cs[0][0])
    base_f = PZ.current_rot(rig, "forearm.R", cs[0][0])
    keys = []
    for i, (f, side) in enumerate(cs):
        s = -1.0 if side == "R" else 1.0            # right foot lands in front -> right arm swings back
        keys.append((f, s))
        if i + 1 < len(cs):
            keys.append(((f + cs[i + 1][0]) * 0.5, 0.0))
    for f, s in keys:
        if until is not None and f > until:
            break
        ua = (base_u[0] + amp * s, base_u[1], base_u[2])
        fa = (elbow[0] + (elbow[1] - elbow[0]) * max(0.0, s), base_f[1], base_f[2])
        U.key(rig.pose.bones["upper_arm.R"], "rotation_euler", f, tuple(math.radians(v) for v in ua))
        U.key(rig.pose.bones["forearm.R"], "rotation_euler", f, tuple(math.radians(v) for v in fa))


def choreograph_shinobi(SH):
    """S01 pre-roll + S02 walk (1.3 m/s), the ellipsis cut at 240/241, the S03 walk ending on a short stopping step
    (288) and the settled ready stance; breathing to the end of the lane."""
    CH, M, PZ = _mods()
    f0 = SPAN[0]
    M.root(SH, f0, SH_WALK_START, 180.0, interp="CONSTANT")
    _key_spec(SH, f0, _spec_from("relaxed_saya", rig=SH))
    a, b = F["walk2"]
    M.root(SH, a, SH_WALK_START, 180.0, interp="LINEAR")
    M.walk(SH, a, b, SH_WALK_START, SH_S02_END, facing=180.0, start=True, stop=False, upper="relaxed_saya")
    _arm_swing(SH, a, b)
    # the walk was cut off mid-gait (stop=False): close the S02 gait on a heel strike at 240 so no foot floats
    # (the trailing foot stays planted, the swinging one lands 0.35 m ahead of the hips)
    zL, zR = M._ball_rest_z(SH, "L"), M._ball_rest_z(SH, "R")
    rx, ry = SH_S02_END
    _local_plant(SH, b, "R", (rx + 0.095, _last_plant_y(SH, "R", b)), zR, heel=12.0)
    _local_plant(SH, b, "L", (rx - 0.095, ry + 0.35), zL)
    b_s02 = b
    # --- the ellipsis: root CONSTANT at 240, S03 enters mid-stride at 241 (pipeline rule 2)
    a, b = F["walk3"]
    M.root(SH, a, SH_S03_START, 180.0, interp="LINEAR")
    M.walk(SH, a, b, SH_S03_START, SH_STOP, facing=180.0, phase=0.5, start=False, stop=True, upper="relaxed_saya")
    # footfall events around the cut: the S02 closing heel strike is a normal step; the bake must not emit the
    # 5 m 'step' that the right foot makes across the ellipsis (moves' evented-steps registry)
    M.emit(b_s02, "step", who="shinobi", strength=0.35, gait="walk")
    M._EVENTED_STEPS.update({(SH.name, "L", float(b_s02)), (SH.name, "R", float(a))})
    # mid-stride entry: the LEFT foot is the stance foot at 241 (planted under the hips until it peels off at its
    # lift key), the right one is swinging through - without these keys the bake would drag the feet 5 m from S02
    _local_plant(SH, a, "L", (SH_S03_START[0] - 0.095, SH_S03_START[1]), zL)
    _arm_swing(SH, a, b, until=F["stop_step"])
    U.set_key_interp_at(SH, F["walk2"][1], "CONSTANT")
    # --- settle: the ready stance (head lifts to the elder) at 300; legs stay as the walk's closing step left them
    rs = _shinobi_stop_ready(SH)
    _key_spec(SH, F["ready"], rs, hands="keep", legs=False)
    _key_spec(SH, SPAN[1] + 2, rs, hands="keep", legs=False)
    _local_breath(SH, F["ready"] + 4, SPAN[1] + 2, amp=0.8, period=72.0, phase=0.0)


def choreograph_elder(SA):
    """Static wait (bowed under the hat) through S02-S04, the head lift 347-378, then the level wait (HANDOFF)."""
    CH, M, PZ = _mods()
    f0 = SPAN[0]
    M.root(SA, f0, SA_POS, 0.0, interp="CONSTANT")
    bowed = _elder_wait_bowed(SA)
    level = _elder_wait_level(SA)
    _key_spec(SA, f0, bowed)
    _key_spec(SA, F["lift0"], bowed, hands="keep")
    _local_breath(SA, f0 + 6, F["lift0"] - 10, amp=0.6, period=80.0, phase=1.3)
    # --- the head lift: neck leads by 3 f, chest inhales (-1.5 at 366) and settles; shoulders square
    lv = level["body"]
    pb = SA.pose.bones
    U.key(pb["neck"], "rotation_euler", F["lift_neck"], tuple(math.radians(v) for v in lv["neck"]))
    U.key(pb["head"], "rotation_euler", F["lift_head0"], tuple(math.radians(v) for v in bowed["body"]["head"]))
    ch = lv["chest"]
    U.key(pb["chest"], "rotation_euler", 366, tuple(math.radians(v) for v in (-1.5, ch[1], ch[2])))
    _key_spec(SA, F["lift_end"], level, hands="keep")
    _key_spec(SA, SPAN[1] + 2, level, hands="keep")
    _local_breath(SA, F["lift_end"] + 6, SPAN[1] + 2, amp=0.6, period=80.0, phase=0.4)


# =============================================================================================================
# environment (calls per cut; sun cheats keep the sun on the -X half of the sky)
# =============================================================================================================
def environment_timeline():
    import environment as ENV
    ENV.set_state(SPAN[0], config.env_at(SPAN[0]), blend_frames=0)       # dusk_gold
    # sun cheats (compass azimuth, elevation): S01/S02 disk left of the title, S03 raking rim from his left,
    # S04 behind the elder's right shoulder, beyond the left frame edge
    ENV.set_sun(CUT["S01"][0], 321.9, 4.0)
    ENV.set_sun(CUT["S02"][0], 321.9, 4.0)
    ENV.set_sun(CUT["S03"][0], 290.0, 5.0)
    ENV.set_sun(CUT["S04"][0], 315.0, 5.0)
    # wind (1.0 = breeze), heading 250 deg: gusts peak ~19 f after the audio wind_gust events
    for f, s in ((SPAN[0], 1.2), (CUT["S02"][0], 1.2), (116, 1.6), (140, 1.2), (169, 1.5), (200, 1.2),
                 (CUT["S02"][1], 1.2), (CUT["S03"][0], 1.1), (300, 1.1), (319, 1.5), (CUT["S03"][1], 1.2),
                 (CUT["S04"][0], 1.1), (350, 1.1), (369, 1.6), (395, 1.2), (SPAN[1], 1.2)):
        ENV.set_wind(f, s, direction_deg=WIND_HEADING)
    # grass clearance: S03 front-cone mode (blades frame the edges, a clean line lens -> him), S04 back to default
    ENV.set_camera_clearance(CUT["S01"][0], near=ENV.CLEAR_NEAR, far=ENV.CLEAR_FAR, cone_deg=0.0)
    # (deviation: once he stops, his parting WAKE closes between the lens and him ~1 s later - plumes rose over
    #  him from ~300; the cone grows to 1.75 m / 33 deg over 278-292 so the line lens -> him stays open)
    ENV.set_camera_clearance(CUT["S03"][0], near=0.25, far=0.35, cone_deg=24.0, cone_len=1.25)
    ENV.set_camera_clearance(276, cone_deg=24.0, cone_len=1.25, interp="LINEAR")
    ENV.set_camera_clearance(292, cone_deg=33.0, cone_len=1.75)
    ENV.set_camera_clearance(CUT["S04"][0], near=ENV.CLEAR_NEAR, far=ENV.CLEAR_FAR, cone_deg=0.0)


# =============================================================================================================
# cameras
# =============================================================================================================
def _ease_io(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


def _dir(yaw_deg, elev_deg):
    """unit vector toward yaw (0 = +Y, + = toward -X) / elevation (breakdown geom.py convention)"""
    y, e = math.radians(yaw_deg), math.radians(elev_deg)
    return (-math.sin(y) * math.cos(e), math.cos(y) * math.cos(e), math.sin(e))


def camera_s01_s02():
    import cameras as CAM
    k0 = ((5.500, -26.000, 3.600), (1.397, -6.589, 6.127))
    CAM.shot("S01", *CUT["S01"], keys=[(CUT["S01"][0], k0[0], k0[1], 20.0)], lens=20.0, framing="wide", subjects=[])
    a, b = CUT["S02"]
    CAM.shot("S02", a, b, lens=20.0, framing="wide", subjects=["saint"], interp="LINEAR", keys=[
        (a, (5.500, -26.000, 3.600), (1.397, -6.589, 6.127), 20.0),
        (168, (5.093, -24.014, 3.302), (1.021, -4.597, 5.830), 20.0),
        (b, (4.680, -22.000, 3.000), (0.639, -2.576, 5.527), 20.0)])


def camera_s03(SH):
    """Knee-height steadicam behind him: rides his REAL root (moves.walk profile), tilt/rise/yaw ease 256->286,
    forward travel stops with him (~290), then a 0.08 m breath-in to 336; walk float gone by 292."""
    import cameras as CAM
    _, M, _ = _mods()
    a, b = CUT["S03"]
    keys = []
    frames = list(range(a, 293, 3)) + [296, 304, 316, 326, b]
    stop_f = F["walk3"][1]
    for f in frames:
        u = _ease_io((f - 256) / 30.0)
        ry = M.root_at(SH, min(f, stop_f))[1]
        creep = 0.08 * max(0.0, f - stop_f) / (b - stop_f)
        x = 0.18 - 0.08 * u
        z = 0.48 + 0.12 * u + 0.01 * max(0.0, f - stop_f) / (b - stop_f)
        y = ry - (1.90 + 0.12 * u) + creep
        pitch, yaw = 6.0 + 14.3 * u, 11.0 - 1.2 * u
        d = _dir(yaw, pitch)
        look = (x + d[0] * 2.5, y + d[1] * 2.5, z + d[2] * 2.5)
        keys.append((f, (x, y, z), look, 28.0))
    cam = CAM.shot("S03", a, b, keys=keys, lens=28.0, framing="close", subjects=["shinobi"],
                   dof=dict(focus=(SH, "chest"), fstop=2.8))
    U.add_shake(cam, a, 292, amp_deg=0.35, scale=6.0, blend=8, seed=_seed("S03:float"))
    return cam


S04_A = (0.000, 3.921, 1.744)          # breakdown's end-pose head point (camera keys ride on it)
S04_KEYS = [
    (CUT["S04"][0], (1.191, -0.523, 1.450), (-0.119, 3.255, 1.555)),
    (347, (1.186, -0.506, 1.451), (-0.124, 3.272, 1.556)),
    (362, (1.166, -0.432, 1.453), (-0.144, 3.346, 1.560)),
    (378, (1.134, -0.311, 1.458), (-0.176, 3.467, 1.568)),
    (392, (1.103, -0.195, 1.462), (-0.207, 3.583, 1.576)),
    (410, (1.068, -0.064, 1.467), (-0.242, 3.714, 1.584)),
    (CUT["S04"][1], (1.048, 0.009, 1.470), (-0.262, 3.786, 1.589)),
]


def _head_point(SA, f):
    """Mid-head point of the elder at frame f (evaluated): halfway along the head bone, 2 cm forward."""
    from mathutils import Vector
    Mw = U.world_matrix_of((SA, "head"), f)
    pb = SA.pose.bones["head"]
    L = pb.bone.length
    p = Mw @ Vector((0.0, L * 0.5, 0.0))
    return p


def camera_s04(SA, shift=(0.0, 0.0, 0.0)):
    import cameras as CAM
    a, b = CUT["S04"]
    keys = []
    for f, loc, look in S04_KEYS:
        keys.append((f, tuple(l + s for l, s in zip(loc, shift)), tuple(l + s for l, s in zip(look, shift)), 85.0))
    return CAM.shot("S04", a, b, keys=keys, lens=85.0, framing="mcu", subjects=["saint"],
                    dof=dict(focus=(SA, "head"), fstop=2.0))


# =============================================================================================================
# the S04 eye glint (character_meshes' glint discs on the elder's eyes), events
# =============================================================================================================
def eye_glint():
    """One tiny glint peaking on 392 = S04.start + 55 (the score's koto note); invisible at 0."""
    try:
        import character_meshes as CM
    except Exception:          # placeholder meshes: no glint discs
        return False
    g = F["glint"]
    for f, v, it in ((g - 5, 0.0, "LINEAR"), (g - 2, 0.35, "LINEAR"), (g, 1.0, "LINEAR"), (g + 2, 0.35, "LINEAR"),
                     (g + 6, 0.0, "CONSTANT")):
        CM.key_eye_glint(f, v, interp=it)
    CM.key_eye_glint(SPAN[0], 0.0, interp="CONSTANT")
    return True


def _local_light(name, kind, loc, aim, energy, color, size=0.8, visible=(1, 1), shadow=False):
    """Lane-local unshadowed light (keeps the <= 3 shadow-caster budget), visible only on frames visible[0..1]."""
    from mathutils import Vector
    ld = bpy.data.lights.get(name) or bpy.data.lights.new(name, kind)
    ld.energy = float(energy)
    ld.color = color
    if kind == "AREA":
        ld.shape = "SQUARE"
        ld.size = size
    ld.use_shadow = bool(shadow)
    ob = bpy.data.objects.get(name) or bpy.data.objects.new(name, ld)
    col = U.ensure_collection(f"LANE_{LANE}")
    if ob.name not in col.objects:
        col.objects.link(ob)
    ob.location = loc
    d = Vector(aim) - Vector(loc)
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    ob.visible_camera = False
    U.key_visible(ob, SPAN[0], False)
    U.key_visible(ob, visible[0], True)
    # hide INSIDE the lane strip (it ends at e + 0.7 and HOLDS FORWARD its last value): half a frame after the
    # last visible frame
    U.key_visible(ob, visible[1] + 0.5, False)
    return ob


def beard_fill():
    """S04_beard_fill (deviation from breakdown §5: a SHADOWED spot from above the camera side instead of a low
    unshadowed area light - the low fill lit the eyes under the brim; from above, the brim throws its shadow over
    the eyes while beard, moustache and jaw read).  Shadow casters in S04: ENV_key + this (+ ENV_flash, unused)."""
    a, b = CUT["S04"]
    ob = _local_light("S04_beard_fill", "SPOT", (0.95, 2.45, 2.75), (0.0, 3.86, 1.45), FILL_W,
                      (1.0, 0.80, 0.58), visible=(a, b), shadow=True)
    ob.data.spot_size = math.radians(38.0)
    ob.data.spot_blend = 0.65
    ob.data.shadow_soft_size = 0.25
    return ob


def s03_rim():
    """S03_rim: unshadowed warm area light low ahead-left of him (toward the sun), riding his root, so the legs,
    sash and scabbard get a rim against the dark grass during the knee-height walk; eases down once he stands
    in silhouette against the sky."""
    _, M, _ = _mods()
    sh = bpy.data.objects["SHINOBI_rig"]
    a, b = CUT["S03"]
    ob = _local_light("S03_rim", "AREA", (0.0, 0.0, 0.0), (0.0, 1.0, 0.0), RIM_W, (1.0, 0.64, 0.38), size=1.2,
                      visible=(a, b))
    from mathutils import Vector
    for f in list(range(a, F["walk3"][1] + 1, 4)) + [b]:
        x, y, _, _ = M.root_at(sh, min(f, F["walk3"][1]))
        loc = Vector((x - 1.3, y + 1.9, 0.75))
        aim = Vector((x, y, 0.75))
        ob.location = loc
        ob.rotation_euler = (aim - loc).to_track_quat("-Z", "Y").to_euler()
        U.key(ob, "location", f, tuple(loc))
        U.key(ob, "rotation_euler", f, tuple(ob.rotation_euler))
    for f, e in ((a, RIM_W), (280, RIM_W), (296, RIM_W * 0.25), (b, RIM_W * 0.25)):
        U.key(ob.data, "energy", f, e)
    return ob


def story_events():
    """Tagged beats the moves calls do not emit."""
    import events as EV
    EV.emit(config.MUSIC_CUES["prologue_start"], "music_cue", cue="prologue_start")
    EV.emit(28, "wind_gust", strength=0.45)
    EV.emit(F["ring"], "clash", strength=0.6, pos=(0.0, 70.0, 1.5), tags=["distant", "omen"])
    EV.emit(F["thunder"], "thunder", distance="far", pos=(-900.0, 2600.0, 500.0), tags=["distant", "omen"])
    EV.emit(84, "wind_gust", strength=0.55)
    EV.emit(97, "wind_gust", strength=0.7)
    EV.emit(150, "wind_gust", strength=0.6)
    EV.emit(F["title"], "music_cue", cue="title")
    EV.emit(300, "wind_gust", strength=0.5)
    # the walk's closing step is THE stopping step (Saku's name card on it): make it read
    for e in EV._EVENTS:                           # (events.events() returns copies: edit the registry entry)
        if e.get("type") != "step" or e.get("_lane") != LANE:
            continue
        if e.get("who") == "shinobi" and F["stop_step"] - 3 <= e["frame"] <= F["stop_step"] + 2:
            e["strength"] = 0.5
            e.setdefault("tags", []).append("stop")
    EV.emit(350, "wind_gust", strength=0.6)


def build(ctx):
    """Lane entry (acts contract): keys only inside [1, 432] (+2 f handles), cameras through cameras.shot, events
    through events.emit.  Leaves config.HANDOFF[432]."""
    sh, sa = ctx["chars"]["shinobi"], ctx["chars"]["saint"]
    stubs = ctx.get("stubs", {}) or {}
    missing = [m for m in ("characters", "moves", "environment") if stubs.get(m)]
    if missing:
        raise RuntimeError(f"prologue needs the real modules (placeholders: {missing})")
    entering_state(sh, sa)
    choreograph_elder(sa)
    choreograph_shinobi(sh)
    environment_timeline()
    camera_s01_s02()
    camera_s03(sh)
    camera_s04(sa)
    eye_glint()
    beard_fill()
    s03_rim()
    story_events()
    for ob in (sh, sa):
        U.freeze_handles(ob, (SPAN[0], SPAN[1] + 2))
