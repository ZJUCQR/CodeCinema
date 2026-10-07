"""
acts/finale.py - lane `finale`: S24-S29 (frames 3073-3840) of Duel in the Silver Grass - the mirrored-iai stand-off in the rain,
the white-out pass, the slow noto + the snap, the kneel under the moon, the walk away, the still life.

    Blender -b --factory-startup --python-exit-code 1 --python codecinema/productions/silvergrass/blender/build_scene.py -- --lanes finale \
        [--quality layout|preview|final]

Shot timing and camera staging are defined below.
Enters from config.HANDOFF[3072] (shinobi kneeling on his planted sword at (0, -6), elder in gedan at (0, 2.5));
the film ends in this lane (everything holds to 3840).

Cut list (hard cuts; every camera on the +X side of the Y action line; the S25 pass swaps the sides by action):
  S24a 3073-3120  135 mm telephoto profile on the S05 axis: silence; the shinobi rises out of the grass
  S24b 3121-3156  100 mm ECU of his scabbard mouth: the noto, click #2 at 3150
  S24c 3157-3196   28 mm low angle on the elder: gedan -> jodan, rain bouncing off the steel
  S24d 3197-3232   85 mm profile medium: the shinobi sinks into the elder's own iai crouch; tails hang
  S24e 3233-3264  100 mm ECU of the tail tip: the drop falls 3250, drip 3256, launch 3257
  S25a 3265-3270  135 mm S05 axis: white 3265-3268, black silhouettes meet 3269 / pass 3270
  S25b 3271-3360  same framing (marker only): back to back, the storm image returns by 3300, slow rain
  S26a 3361-3428   40 mm deep 3/4: slow noto in front; click #3 3412 = the elder's blade snaps; cord 3414
  S26b 3429-3456   50 mm low insert: the tip plants 3440
  S27  3457-3600   30 mm deep two-shot: kneel 3470, stub 3476, moon, turn 3552-3568, bow 3570-3600
  S28  3601-3744   50->24 mm crane: he walks away toward the moon; the wind returns
  S29  3745-3840   35 mm low still life: the broken tip; bell + the 'End' card 3758 (post fades 3770-3811)
"""

from codecinema.productions import film_root, source_root
import math
import os
import sys
import zlib

import bpy
from mathutils import Matrix, Quaternion, Vector

ROOT = str(film_root("silvergrass"))
for _p in (os.path.join(str(source_root("silvergrass")), "common"), os.path.join(str(source_root("silvergrass")), "blender")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import config  # noqa: E402
import bl_util as U  # noqa: E402
import cameras as C  # noqa: E402
import events as EV  # noqa: E402
from acts import sub_cuts  # noqa: E402

LANE = "finale"
SPAN = tuple(config.lane_span(LANE))                      # (3073, 3840)
F0, F1 = SPAN
H_IN = config.HANDOFF[F0 - 1]                             # HANDOFF[3072]
MC = config.MUSIC_CUES

# ------------------------------------------------------------------------------------------------ cut table
# config shots split at the sub-cut starts: S24a 3073-3120, S24b 3121-3156, S24c 3157-3196, S24d 3197-3232,
# S24e 3233-3264, S25a 3265-3270, S25b 3271-3360, S26a 3361-3428, S26b 3429-3456, S27 3457-3600, S28 3601-3744,
# S29 3745-3840
CUTS = sub_cuts(LANE, {"S24": (3121, 3157, 3197, 3233), "S25": (3271,), "S26": (3429,)})
CUT = {c: (a, b) for c, a, b in CUTS}

# ------------------------------------------------------------------------------------------------ key moments
F = dict(
    silence=MC["silence"], rise=(3085, 3112), noto_click=3150, jodan=(3162, 3184), crouch=(3202, 3226),
    drop=3250, drip=3256, launch_sh=3257, launch_el=3258, white=config.FULL_WHITE, contact=3269, overlap=3270,
    tableau=config.SCREEN_DIRECTION["swap_frame"], blade_ring=MC["blade_ring"], final_pass=MC["final_pass"],
    slow_noto=3361, snap=3412, cord=3414, tip_plant=3440, knees=3462, kneel=3470, stub=3476,
    epilogue=MC["epilogue"], turn=(3552, 3568), bow=(3570, 3582, 3592, 3600), turn2=(3601, 3614),
    walk=(3614, 3744), bell=MC["end_card"],
)   # silence 3073, white (3265, 3268), tableau 3271, blade_ring 3277, final_pass 3300, epilogue 3505, bell 3758

# ------------------------------------------------------------------------------------------------ blocking
SH0 = tuple(H_IN["shinobi"]["pos"])  # HANDOFF[3072] shinobi (0, -6) (kneeling, facing 180)
EL0 = tuple(H_IN["saint"]["pos"])    # HANDOFF[3072] elder (0, 2.5) (gedan, facing 0)
SH_CROUCH = (0.0, -5.90)            # after the suriashi (S24d)
SH_DASH_END = (-0.35, -2.41)        # 3268
EL_DASH0, EL_DASH_END = (0.02, 2.48), (0.35, -0.12)
SH_PASS = {3269: (-0.35, -2.00), 3270: (-0.35, -1.55)}
EL_PASS = {3269: (0.35, -0.46), 3270: (0.35, -0.80)}
SH_TAB = (-0.25, 1.10)              # back to back from 3271, facing 180
EL_TAB = (0.30, -3.50)              # facing 0
SH_WALK_END = (2.00, 7.50)          # 3744, facing 160.6 (toward the moon)
PASS_POINT = Vector((0.02, -1.28, 1.55))  # where the two blades cross at 3269 (silhouette X)

# S05 axis (act1a constant, DIRECTION §3: reuse this exact axis + lens for S24a and S25)
S05_AXIS = dict(x=52.0, z=2.10, pitch_deg=1.45, lens=135.0)

TAIL_BONES = [f"tail{t}.{i}" for t in (1, 2) for i in (1, 2, 3, 4)]


def _seed(tag):
    """Deterministic seed (zlib.crc32 of '<shot>:<i>' style tags, never hash())."""
    return zlib.crc32(str(tag).encode()) & 0x7FFFFFFF


def _obj(name):
    return bpy.data.objects.get(name)


def _v(x):
    return Vector(tuple(x))


def _facing_from(p_from, p_to):
    """Facing angle (deg) looking from p_from to p_to (xy): forward = (sin θ, -cos θ)."""
    dx, dy = p_to[0] - p_from[0], p_to[1] - p_from[1]
    return math.degrees(math.atan2(dx, -dy))


def _norm(v):
    v = Vector(v)
    return v.normalized() if v.length > 1e-9 else v


def _perp(v, d):
    """Component of v perpendicular to unit d, normalised."""
    v, d = Vector(v), Vector(d).normalized()
    return (v - v.dot(d) * d).normalized()


# =============================================================================================
# lane-local poses - POSES-format dicts keyed through poses.key_pose(spec=resolve(...))
# =============================================================================================
def _local_poses():
    """Local pose specs (authored with the poses helpers, SHINOBI metres unless 'scale': False)."""
    import poses as PZ
    P = {}
    lib = PZ.POSES
    # --- shinobi: rising out of the kneel, left hand pushing on the left knee (blade keyed separately)
    push_L = PZ.arm("L", flex=38, abd=-12, elbow=62, wflex=18)
    P["sh_rise_push"] = PZ.pose(
        "rise 1/3: weight over the planted left foot, left hand pushing on the left knee, blade coming out",
        "story", body=PZ.merge(PZ.torso(lean=26, look_pitch=-10), push_L),
        hips=(0.0, -0.32, 0.02), legs={"L": PZ.foot(0.12, -0.32), "R": PZ.foot(-0.11, 0.30, heel=40)},
        ctrl=None, left="free")
    P["sh_rise_mid"] = PZ.pose(
        "rise 2/3: half risen, back knee lifting, head coming up to the elder", "story",
        body=PZ.merge(PZ.torso(lean=14, look_pitch=-4), PZ.arm("L", flex=20, abd=-18, elbow=40)),
        hips=(0.0, -0.15, 0.02), legs={"L": PZ.foot(0.12, -0.26), "R": PZ.foot(-0.12, 0.26, heel=20)},
        ctrl=None, left="free")
    # --- shinobi noto variants with the RIGHT foot back (S24b: the ECU looks across the front of his right thigh)
    for nm in ("sheathe_quick_1", "sheathe_done"):
        sp = dict(lib[nm])
        sp["legs"] = PZ.stance(front=0.20, back=0.26, width=0.26, lead="L", heel_back=8)
        sp.pop("per_char", None)
        sp.pop("_name", None)
        P[nm + "_L"] = sp
    # the S24b slide: sheathe_done body, left foot forward, fixed saya, ctrl {"sheathed": s} set per key
    sl = dict(lib["sheathe_done"])
    sl["legs"] = PZ.stance(front=0.20, back=0.26, width=0.26, lead="L", heel_back=8)
    sl.pop("per_char", None)
    sl.pop("_name", None)
    sl["elbow"] = {"R": "auto"}
    P["noto_slide_L"] = sl
    # --- relaxed stand, head bowed (after the noto, S26-S27)
    rb = dict(lib["relaxed_saya"])
    rb.update(PZ.merge({k: v for k, v in lib["relaxed_saya"].items() if k in ("neck", "head")}))
    rb["neck"] = (6.0, rb.get("neck", (0, 0, 0))[1], 0.0)
    rb["head"] = (5.0, rb.get("head", (0, 0, 0))[1], 0.0)
    rb.pop("_name", None)
    P["sh_relaxed_bowed"] = rb
    # --- the pass (S25a): contact / overlap keyed with explicit blades (see _pass_blades)
    # --- the tableau (S25b-S26a): shinobi one-handed zanshin, blade horizontal pointing back-right
    P["sh_zanshin_pass"] = PZ.pose(
        "zanshin after the pass: knees bent, trunk upright, right arm extended back-right at shoulder height, "
        "blade horizontal pointing back-right, left fist on the saya", "iai",
        body=PZ.torso(lean=4, twist=-34, look_yaw=0.0),
        hips=(0.0, -0.14, 0.04), legs=PZ.stance(front=0.36, back=0.34, width=0.30, lead="R", heel_back=20),
        ctrl=PZ.blade((-0.62, 0.16, 1.30), (-0.45, 0.89, 0.0)), left="saya", saya=(0.0, 60.0),
        elbow={"R": "auto"})
    # --- elder tableau: two-handed, blade held HIGH (D4), 10 deg below horizontal pointing forward-left;
    #     LEFT foot forward so that he can drop straight onto the right knee later (S27, same knee as S23)
    P["elder_zanshin_high"] = PZ.pose(
        "elder zanshin after the pass: fists 1.22 m in front of the belly, blade forward-left 10 deg down",
        "iai", body=PZ.torso(lean=6, twist=8),
        hips=(0.0, -0.10, 0.03), legs=PZ.stance(front=0.40, back=0.36, width=0.30, lead="L", heel_back=18),
        ctrl={"SAINT": {"grip": (0.10, -0.50, 1.28), "dir": (0.38, -0.91, -0.10)}}, left="grip",
        elbow={"R": "auto", "L": "auto"})
    low = dict(P["elder_zanshin_high"])
    low["ctrl"] = {"SAINT": {"grip": (0.10, -0.50, 1.21), "dir": (0.38, -0.91, -0.15)}}
    low["neck"], low["head"] = (6.0, 0.0, 0.0), (4.0, 0.0, 0.0)
    P["elder_zanshin_sunk"] = low
    # knees giving way (S27 3462 / 3466)
    k1 = dict(P["elder_zanshin_high"])
    k1["hips_offset"] = (0.0, -0.20, 0.03)
    k1["ctrl"] = {"SAINT": {"grip": (0.08, -0.48, 1.00), "dir": (0.30, -0.90, -0.32)}}
    k1.update(PZ.torso(lean=10, twist=6, look_pitch=10))
    P["elder_knees_1"] = k1
    kp = lib["kneel_planted"]
    P["elder_knees_2"] = PZ.pose(
        "knees buckling: hips dropping, right knee 15 cm above the ground, the stub still held forward", "story",
        body={"spine": (14, 0, 0), "chest": (10, 0, 0), "neck": (18, 0, 0), "head": (12, 0, 0)},
        hips=(0.0, -0.34, 0.0),
        legs={"L": {"ankle": (0.12, -0.42, 0.077)}, "R": {"ankle": (-0.11, 0.30, 0.16), "foot_pitch": 14,
                                                          "toe": (-40, 0, 0)}},
        ctrl={"SAINT": {"grip": (0.04, -0.48, 0.80), "dir": (0.10, -0.55, -0.83), "edge": (0.0, -0.83, 0.55)}},
        left="grip", elbow={"R": "auto", "L": "auto"})
    P["elder_kneel_broken"] = PZ.pose(
        "the elder kneeling on the right knee, the broken blade planted, both fists on the hilt, head bowed deep "
        "(the echo of the shinobi's S23 low point)", "story",
        body={"spine": (18, 0, 0), "chest": (12, 0, 0), "neck": (25, 0, 0), "head": (20, 0, 0)},
        hips=kp["hips_offset"], legs=kp["legs"],
        ctrl={"SAINT": {"grip": (0.0, -0.46, 0.50), "dir": (0.0, -0.10, -1.0), "edge": (0.0, -1.0, 0.0)}},
        left="grip", elbow={"R": "auto", "L": "auto"})
    kb = dict(P["elder_kneel_broken"])
    kb["neck"], kb["head"] = (18.0, 0.0, 0.0), (14.0, 0.0, 0.0)
    P["elder_kneel_broken_0"] = kb                         # before the head sinks further (3476 -> 3490)
    # the S27 bow, deeper than the library rei (32 deg read as a nod at 8 m in the 30 mm two-shot): 48 deg from
    # the hips, head following - the formal bow to a master, and it has to read at 15 %H
    P["sh_bow_deep"] = PZ.pose(
        "deep standing bow to the master's back: trunk 48 deg from the hips, hands along the thighs, sheathed",
        "story", body=PZ.merge(PZ.torso(lean=48, pelvis=0.55, gaze=0.3), PZ.arm("L", flex=-2, abd=-36, elbow=10),
                               PZ.arm("R", flex=-2, abd=-36, elbow=10)),
        hips=(0.0, -0.03, -0.05), legs={"R": PZ.foot(-0.09, -0.10), "L": PZ.foot(0.09, -0.10)}, ctrl=None,
        left="free")
    # jodan settle (S24c 3186-3190: a 2 cm sink on the exhale)
    js = dict(lib["jodan"])
    js.pop("_name", None)
    pc = dict(js.get("per_char") or {})
    sa = dict(pc.get("SAINT") or {})
    sa["hips_offset"] = (0.0, -0.06, 0.0)
    pc["SAINT"] = sa
    js["per_char"] = pc
    P["jodan_settled"] = js
    return P


_POSES = {}


def _P(name):
    """A local pose (built once) or a library pose name."""
    import poses as PZ
    if not _POSES:
        _POSES.update(_local_poses())
    return _POSES.get(name) or PZ.POSES[name]


def _local_presaya(rig, f, sp, kw):
    """Workaround (shared-module bug, reported): poses.key_pose computes a 'sheathed' controller from the saya
    state BEFORE it keys the pose's own saya setting, so a pose that changes the saya lands its blade on the old
    scabbard axis (up to 0.3 m off). Key the pose's saya first; key_pose then re-keys the same values."""
    import poses as PZ
    c = sp.get("ctrl")
    if kw.get("ctrl", True) and sp.get("saya") is not None and (c == "sheathed" or (isinstance(c, dict) and "sheathed" in c)):
        PZ.key_saya(rig, f, *sp["saya"])


def _key(rig, f, name, **kw):
    """poses.key_pose for a library OR a local pose; hands default 'keep' (the lane owns the left hand)."""
    import poses as PZ
    kw.setdefault("hands", "keep")
    if name in PZ.POSES and name not in _POSES:
        sp = PZ.resolve(name, rig)
    else:
        sp = PZ.resolve(_P(name), rig)
    _local_presaya(rig, f, sp, kw)
    return PZ.key_pose(rig, f, None, spec=sp, **kw)


def _key_slide(rig, f, s, base="noto_slide_L", saya=None, **kw):
    """One key of a noto slide: body `base`, sword controller s metres out of the saya along its axis."""
    import poses as PZ
    sp = PZ.resolve(_P(base), rig)
    sp["ctrl"] = {"sheathed": float(s)}
    if saya is not None:
        sp["saya"] = tuple(saya)
    kw.setdefault("hands", "keep")
    _local_presaya(rig, f, sp, kw)
    return PZ.key_pose(rig, f, None, spec=sp, **kw)


# =============================================================================================
# entering state (HANDOFF[3072]) - every state channel keyed on the lane's first frame
# =============================================================================================
def entering_state(SH, SA):
    import characters as CH
    import moves as M
    f = F0
    CH.set_weapon_state(SH, f, "drawn")
    CH.set_arm_mode(SH, f, "ik")
    CH.set_two_hand(SH, f, True)
    CH.set_kunai_in_hand(f, False)
    CH.set_weapon_state(SA, f, "gone")                  # spear gone (thrown into the fire in S19)
    CH.set_weapon_state(SA, f, "drawn")                 # katana in hand (sets active weapon = katana)
    CH.set_arm_mode(SA, f, "ik")
    CH.set_two_hand(SA, f, True, weapon="katana")
    CH.set_hat(f, "off")
    CH.set_costume(f, haori=False, thrown=False)
    CH.set_beard_cord(f, False)
    M.root(SH, f, SH0, float(H_IN["shinobi"]["facing"]), interp='CONSTANT')
    M.root(SA, f, EL0, float(H_IN["saint"]["facing"]), interp='CONSTANT')
    for nm in ("SAINT_katana_tip_broken", "SAINT_beard_cord_cut"):
        ob = _obj(nm)
        if ob is not None:
            U.key_visible(ob, f, False)


# =============================================================================================
# the shinobi
# =============================================================================================
def shinobi(SH):
    import characters as CH
    import moves as M
    import poses as PZ
    # ---- S24a: kneeling on the planted blade, one heavy breath, then he rises out of the grass
    _key(SH, 3073, "kneel_sword_planted", hands="pose")
    _key(SH, 3084, "kneel_sword_planted", ctrl=False)
    M.overlay(SH, 3079, {"chest": (1.8, 0.0, 0.0), "neck": (-0.8, 0.0, 0.0)})
    M.overlay(SH, 3085, {"hand.R": (4.0, 0.0, 0.0)})
    CH.set_two_hand(SH, 3086, False, blend=4)           # the right hand alone draws the blade out of the mud
    CH.key_sword(SH, 3086, grip=(0.03, -5.55, 0.66), direction=(0.0, 0.15, -1.0), edge=(0.0, 1.0, 0.0))
    CH.key_sword(SH, 3090, grip=(0.04, -5.57, 0.80), direction=(0.05, 0.25, -0.97), edge=(0.0, 1.0, 0.0))
    CH.key_sword(SH, 3094, grip=(0.06, -5.60, 0.95), direction=(0.12, 0.38, -0.92), edge=(0.0, 1.0, 0.2))
    _key(SH, 3094, "sh_rise_push", ctrl=False)
    _key(SH, 3104, "sh_rise_mid", ctrl=False)
    CH.key_sword(SH, 3104, grip=(0.13, -5.68, 0.94), direction=(0.02, 0.72, -0.69))
    _key(SH, 3112, "low_1h")                            # standing, blade lowered on his right, one-handed
    CH.set_left_hand(SH, 3112, "saya", blend=4)
    # the blade swings up and across to the left hip: the kissaki meets the koiguchi (right foot drawn back)
    _key(SH, 3118, "sheathe_quick_1_L")
    # ---- S24b: the noto slide along the saya axis - click on 3150 (S_KEYS: s = tsuba distance from the mouth)
    saya_fix = (0.0, 75.0, 0.0, 10.0)
    # the left hand brings the scabbard round onto the blade (turn 45 -> 0) while the first 40 cm go in
    saya_turn = {3121: (0.05, 50.0, 40.0, -16.0), 3128: (0.025, 64.0, 18.0, -3.0)}
    for f, s in ((3121, 0.52), (3128, 0.30), (3134, 0.16), (3137, 0.11), (3140, 0.075), (3142, 0.055),
                 (3145, 0.030), (3148, 0.008)):
        _key_slide(SH, f, s, saya=saya_turn.get(f, saya_fix))
    _key_slide(SH, 3150, 0.0, saya=saya_fix)
    _key(SH, 3150, "sheathe_done_L", ctrl=False)
    PZ.key_saya(SH, 3150, *saya_fix)
    CH.set_weapon_state(SH, 3150, "sheathed")
    _key_slide(SH, 3156, 0.0, saya=saya_fix)            # fist stays on the hilt through the cut
    _local_noto_ctrl(SH, [(3118, 0.76), (3121, 0.52), (3128, 0.30), (3134, 0.16), (3137, 0.11), (3140, 0.075),
                          (3142, 0.055), (3145, 0.030), (3148, 0.008), (3150, 0.0), (3156, 0.0)], 3119, 3156)
    CH.set_arm_mode(SH, 3158, "fk", blend=6)
    _key(SH, 3168, "relaxed_saya", ctrl=True)
    PZ.key_saya(SH, 3168, *saya_fix)
    PZ.key_saya(SH, 3182, 0.0, 0.0)
    # ---- S24d: koiguchi o kiru + the elder's own iai crouch (S05 silhouette)
    _key(SH, 3197, "relaxed_saya", ctrl=False)
    PZ.key_saya(SH, 3200, 0.0, 0.0)
    PZ.key_saya(SH, 3212, 0.0, 60.0)                    # edge turns outward - no push, no click
    M.hold(SH, 3202)
    M.root(SH, 3204, SH0, 180.0, interp='BEZIER')
    M.root(SH, 3214, SH_CROUCH, 180.0, interp='BEZIER')  # suriashi: the right foot slides forward 10 cm
    _key(SH, 3214, "iai_crouch", weight=0.65, ctrl=False)
    CH.key_ctrl_matrix(_obj("SHINOBI_sword_ctrl"), 3208, _sheathed_M(SH, 3208))
    CH.set_arm_mode(SH, 3208, "ik", blend=6)
    CH.key_ctrl_matrix(_obj("SHINOBI_sword_ctrl"), 3214, _sheathed_M(SH, 3214))
    CH.auto_elbow(SH, 3214, "R")
    CH.auto_elbow(SH, 3214, "L")
    _key(SH, 3226, "iai_crouch")
    _key(SH, 3256, "iai_crouch")                        # absolute stillness (held breath)
    EV.emit(3205, "step", who="shinobi", strength=0.2)
    # ---- S24e -> S25a: the launch (3257) - dash with the iai hands, the draw inside the white
    M.dash(SH, F["launch_sh"], 3268, (SH_CROUCH[0] - 0.02, SH_CROUCH[1]), SH_DASH_END, start=True, stop=False,
           upper="iai_crouch")
    _key(SH, 3266, "iai_draw_1")
    CH.key_ctrl_matrix(_obj("SHINOBI_sword_ctrl"), 3268, _sheathed_M(SH, 3268))
    CH.set_weapon_state(SH, 3268, "drawn")
    _key(SH, 3268, "iai_draw_2")


def _local_noto_ctrl(rig, table, f0, f1):
    """Re-key the sword controller on EVERY frame f0..f1 at sheathed_ctrl_matrix(f) pulled s(f) along the saya
    axis (s from `table` [(frame, s)], eased per segment): between sparse pose keys the separately interpolated
    controller and scabbard drift apart (up to 4 cm at the koiguchi in the S24b ECU); per-frame keys on the
    evaluated saya keep the blade exactly on the scabbard axis (LINEAR keys)."""
    import characters as CH
    ctrl = _obj(f"{rig.name.split('_')[0]}_sword_ctrl")
    tb = sorted(table)

    def s_at(f):
        if f <= tb[0][0]:
            return tb[0][1]
        for (fa, sa), (fb, sb) in zip(tb, tb[1:]):
            if fa <= f <= fb:
                u = (f - fa) / float(fb - fa)
                return sa + (sb - sa) * U.ease(u, "smooth")
        return tb[-1][1]
    for f in range(int(f0), int(f1) + 1):
        M = _sheathed_M(rig, f) @ Matrix.Translation((0.0, -s_at(f), 0.0))
        CH.key_ctrl_matrix(ctrl, f, M, interp='LINEAR')


def _sheathed_M(rig, f):
    """characters.sheathed_ctrl_matrix evaluated at f (the saya follows the keyed hips)."""
    import characters as CH
    U.frame_set(f)
    return CH.sheathed_ctrl_matrix(rig, f)


def _set_interp_range(rig, f0, f1, interp, prefix=None, ctrl=False):
    """Interpolation of every key of `rig` (and optionally its sword controller) with f0 <= frame < f1."""
    obs = [rig]
    if ctrl:
        c = _obj(f"{rig.name.split('_')[0]}_sword_ctrl")
        if c is not None:
            obs.append(c)
    for ob in obs:
        for fc in U.fcurves_of(ob, prefix):
            for k in fc.keyframe_points:
                if f0 - 1e-3 <= k.co.x < f1 - 1e-3:
                    k.interpolation = interp


def _pass_blades():
    """World blade frames at the contact frame 3269, crossing at PASS_POINT like an X in the S05-axis silhouette
    (the camera looks along -X, so only (y, z) reads): the shinobi's one-handed rising draw-cut (edge up, 45 deg)
    under the elder's two-handed downswing that is still above horizontal (both 'forward-up' -> an X, not one line).
    Wrists checked on the real rigs (out/dev/acts/finale/probe_pass.py). Returns {rig: (grip, dir, edge)}."""
    P = PASS_POINT
    g_s = Vector((-0.20, -1.58, 1.18))
    d_s = (P - g_s).normalized()
    e_s = _perp((-0.2, 0.0, 1.0), d_s)
    g_e = Vector((0.20, -0.95, 1.40))
    d_e = (P - g_e).normalized()
    e_e = _perp((-0.3, 0.0, -1.0), d_e)
    return {"SHINOBI_rig": (g_s, d_s, e_s), "SAINT_rig": (g_e, d_e, e_e)}


def the_pass(SH, SA):
    """S25a: 3269 contact (blades touching), 3270 overlap (the draw-cut through, heads at the same screen x),
    3271 the tableau 2-3 m further on (D2: a two-frame time jump hidden by the white-out). Everything keyed on
    3270 is CONSTANT: no motion-blur streak toward the tableau."""
    import characters as CH
    import moves as M
    bl = _pass_blades()
    for f in (3269, 3270):
        M.root(SH, f, SH_PASS[f], 180.0, interp='LINEAR')
        M.root(SA, f, EL_PASS[f], 0.0, interp='LINEAR')
    _key(SH, 3269, "iai_cut", ctrl=False)
    g, d, e = bl["SHINOBI_rig"]
    CH.key_sword(SH, 3269, grip=tuple(g), direction=tuple(d), edge=tuple(e))
    _key(SH, 3270, "iai_follow", ctrl=False)
    CH.key_sword(SH, 3270, grip=(-0.10, -1.12, 1.45), direction=tuple(_norm((0.15, 0.85, 0.50))),
                 edge=tuple(_perp((-0.2, 0.0, 1.0), _norm((0.15, 0.85, 0.50)))))
    _key(SA, 3269, "overhead_strike", ctrl=False)
    g, d, e = bl["SAINT_rig"]
    CH.key_sword(SA, 3269, grip=tuple(g), direction=tuple(d), edge=tuple(e))
    _key(SA, 3270, "overhead_follow", ctrl=False)
    CH.key_sword(SA, 3270, grip=(0.22, -1.28, 1.06), direction=tuple(_norm((-0.18, -0.92, -0.26))),
                 edge=tuple(_perp((-0.3, 0.0, -1.0), _norm((-0.18, -0.92, -0.26)))))
    # the tableau: back to back, 4.6 m apart
    M.root(SH, 3271, SH_TAB, 180.0, interp='CONSTANT')
    M.root(SA, 3271, EL_TAB, 0.0, interp='CONSTANT')
    _key(SH, 3271, "sh_zanshin_pass", hands="pose")
    _key(SA, 3271, "elder_zanshin_high", hands="pose")
    for rig in (SH, SA):
        c = _obj(f"{rig.name.split('_')[0]}_sword_ctrl")
        for ob in (rig, c, _obj(f"{rig.name.split('_')[0]}_saya")):
            if ob is not None:
                U.set_key_interp_at(ob, 3270, 'CONSTANT')
    for rig in (SH, SA):
        M.root(rig, 3360, SH_TAB if rig is SH else EL_TAB, 180.0 if rig is SH else 0.0, interp='CONSTANT')


def shinobi_after(SH):
    """S25b hold -> S26a slow noto (click 3412) -> S27 turn + bow -> S28 turn + walk away toward the moon."""
    import characters as CH
    import moves as M
    import poses as PZ
    _key(SH, 3360, "sh_zanshin_pass")                   # frozen tableau (identical keys 3271 / 3360)
    # ---- S26a: the slow noto (film-frame paced; the rain hangs at 1/8)
    _key(SH, 3370, "sheathe_slow_chiburi")
    EV.emit(3366, "whoosh", who="shinobi", weapon="katana", strength=0.12)
    _key(SH, 3384, "sheathe_slow_1")
    for f, s in ((3398, 0.35), (3406, 0.06), (3410, 0.01)):
        _key_slide(SH, f, s, base="sheathe_slow_2")
    _key(SH, 3412, "sheathe_done")
    CH.set_weapon_state(SH, 3412, "sheathed")
    _local_noto_ctrl(SH, [(3384, 0.78), (3398, 0.35), (3406, 0.06), (3410, 0.01), (3412, 0.0)], 3385, 3412)
    CH.set_arm_mode(SH, 3413, "fk", blend=8)
    _key(SH, 3428, "sh_relaxed_bowed", ctrl=False)
    PZ.key_saya(SH, 3428, 0.0, 0.0)
    _key(SH, 3456, "sh_relaxed_bowed", ctrl=False)
    # ---- S27: he lifts his head to the opening sky, turns (toward the camera side) and bows to the master's back
    _key(SH, 3505, "sh_relaxed_bowed", ctrl=False)
    M.overlay(SH, 3525, {"neck": (-7.0, 0.0, 0.0), "head": (-5.0, 0.0, 0.0)})
    _key(SH, 3545, "relaxed_saya", ctrl=False)
    M.turn(SH, 3552, 3560, 90.0)
    M.turn(SH, 3560, 3568, 0.0)
    CH.set_left_hand(SH, 3570, "free", blend=6)
    M.hold(SH, 3572, ctrl=False)
    _key(SH, 3577, "sh_bow_deep", weight=0.7, ctrl=False)
    _key(SH, 3582, "sh_bow_deep", ctrl=False)            # lowest 3582-3592 (the koto home figure 3587)
    _key(SH, 3592, "sh_bow_deep", ctrl=False, feet=False)
    CH.set_left_hand(SH, 3596, "saya", blend=4)
    _key(SH, 3600, "relaxed_saya", ctrl=False)
    # ---- S28: turn toward the moon and walk away (still walking on the last frame)
    M.turn(SH, F["turn2"][0], F["turn2"][1], 160.6)
    x, y, _, _ = M.root_at(SH, F["walk"][0])
    M.walk(SH, F["walk"][0], F["walk"][1], (x, y), SH_WALK_END, upper="relaxed_saya", stop=False)


# =============================================================================================
# the elder
# =============================================================================================
def elder(SA):
    import moves as M
    # ---- S24a-b: gedan in the downpour, unhurried breathing
    _key(SA, 3073, "gedan", hands="pose")
    for i, f in enumerate(range(3088, 3160, 30)):
        M.overlay(SA, f, {"chest": (0.8 if i % 2 == 0 else -0.8, 0.0, 0.0)})
    _key(SA, 3162, "gedan")
    # ---- S24c: the lift into jodan (25 f), a 2 cm sink on the exhale, then stillness
    _key(SA, 3172, "chudan")
    _key(SA, 3184, "jodan")
    _key(SA, 3190, "jodan_settled")
    _key(SA, 3257, "jodan_settled")
    EV.emit(3176, "whoosh", who="saint", weapon="katana", strength=0.25)
    # ---- S24e/S25a: the charge in jodan (heard, then seen as a silhouette in the white)
    M.dash(SA, F["launch_el"], 3268, EL_DASH0, EL_DASH_END, start=True, stop=False, upper="jodan")


def elder_after(SA):
    """After the pass (keyed by the_pass): frozen tableau, the snap, the arms sink, the kneel under the moon."""
    import characters as CH
    import moves as M
    # ---- S25b-S26a: the tableau (the pass is keyed in the_pass); frozen until the snap, then the arms sink 8 cm
    _key(SA, 3360, "elder_zanshin_high")
    _key(SA, 3412, "elder_zanshin_high")
    _key(SA, 3456, "elder_zanshin_sunk")
    # ---- S27: the knees give with the sigh (3462), knee down 3470, stub planted 3476, head sinks (3490)
    _key(SA, 3461, "elder_zanshin_sunk")
    _key(SA, F["knees"], "elder_knees_1")
    _key(SA, 3466, "elder_knees_2")
    _key(SA, F["kneel"], "elder_kneel_broken_0", ctrl=False)
    CH.key_sword(SA, F["kneel"], grip=(0.30, -3.99, 0.62), direction=(0.0, -0.22, -0.975), edge=(0.0, -1.0, 0.2))
    _key(SA, 3472, "elder_kneel_broken_0", weight=1.03, ctrl=False, feet=False)
    _key(SA, F["stub"], "elder_kneel_broken_0")
    _key(SA, 3490, "elder_kneel_broken")
    for i, f in enumerate(range(3526, F1, 36)):
        M.overlay(SA, f, {"chest": (0.6 if i % 2 == 0 else -0.6, 0.0, 0.0)})
    _key(SA, F1, "elder_kneel_broken")
    M.root(SA, F1, EL_TAB, 0.0, interp='CONSTANT')


# =============================================================================================
# props: the broken tip (fx-clock toss, planted 3440, quiver) and the cut beard cord (3414)
# =============================================================================================
def _fx(f):
    import fxclock
    return fxclock.fx_time_at(f)


def _key_matrix(ob, f, M, interp='LINEAR', prev=None):
    """Key location + XYZ Euler (continuity-compatible with `prev`) of a free object from a world matrix."""
    loc, rot, _ = M.decompose()
    e = rot.to_euler('XYZ', prev) if prev is not None else rot.to_euler('XYZ')
    U.key(ob, "location", f, tuple(loc), interp=interp)
    U.key(ob, "rotation_euler", f, tuple(e), interp=interp)
    return e


def _local_toss_fx(name, f0, f1, p0, v0, R0, R1, extra_turns=1, g=-9.81, p1=None):
    """Ballistic keys EVERY frame f0..f1 on the FILM CLOCK (t = fx(f) - fx(f0), so the S25-S26 1/8 slow motion
    slows the flight like the rain), orientation slerped R0 -> R1 about their common axis plus `extra_turns`
    full tumbles; p1 (optional) = the exact end position (a small linear correction is blended in so the
    parabola lands there).  Last key CONSTANT."""
    ob = _obj(name)
    q0, q1 = R0.to_quaternion(), R1.to_quaternion()
    if q0.dot(q1) < 0:
        q1 = -q1
    dq = q1 @ q0.inverted()
    ax, ang = dq.to_axis_angle()
    ang_tot = ang + 2.0 * math.pi * extra_turns
    T = _fx(f1) - _fx(f0)
    v0, p0 = Vector(v0), Vector(p0)
    end_ball = p0 + v0 * T + Vector((0.0, 0.0, 0.5 * g * T * T))
    corr = (Vector(p1) - end_ball) if p1 is not None else Vector()
    prev = None
    for f in range(int(f0), int(f1) + 1):
        t = _fx(f) - _fx(f0)
        u = t / T if T > 0 else 1.0
        p = p0 + v0 * t + Vector((0.0, 0.0, 0.5 * g * t * t)) + corr * u
        q = Quaternion(ax, ang_tot * U.ease(u, "inout_quad")) @ q0
        prev = _key_matrix(ob, f, Matrix.Translation(p) @ q.to_matrix().to_4x4(), prev=prev)
    U.set_key_interp_at(ob, int(f1), 'CONSTANT')
    return ob


TIP_PLANT = (1.00, -4.85, 0.09)          # CoM of the planted tip (S26b / S29)
S29_CAM = (2.36, -3.94, 0.32)            # still-life lens: 1.6 m from the tip (breakdown 2.2 m: the tip read too thin)


S29_KEY = (146.0, 24.0)                  # S29 moon-key cheat (az, el): side-front, so the steel flat can mirror it


def _compass_dir(az, el):
    a, e = math.radians(az), math.radians(el)
    return Vector((math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e)))


TIP_SHEEN_OFFSET = 7.0                   # deg: the flat is turned off the exact mirror (14 deg miss): a sheen, not a tube
S26B_CAM = (2.15, -5.20, 0.30)


def _tip_mirror_normal():
    v = (Vector(S29_CAM) - Vector(TIP_PLANT)).normalized()
    return (v + _compass_dir(*S29_KEY)).normalized()


def _tip_planted_basis():
    """World basis (columns: flat normal X, point direction Y, spine Z) of the planted tip. The flat is (almost)
    the MIRROR normal between the S29 lens and the S29 key (n = v + l), turned TIP_SHEEN_OFFSET about the blade
    axis: the wet steel catches the moonlight as a sheen (a backlit vertical flat only reflects the dark sky and
    read as a grey post; the exact mirror read as a fluorescent tube). The blade axis lies in the flat, as vertical
    as possible (lean = the normal's elevation, ~21 deg, top away from the lens)."""
    n0 = _tip_mirror_normal()
    up = Vector((0.0, 0.0, 1.0))
    ax = (up - up.dot(n0) * n0).normalized()
    n = (Matrix.Rotation(math.radians(TIP_SHEEN_OFFSET), 3, ax) @ n0).normalized()
    d_pt = -ax
    z = n.cross(d_pt).normalized()
    return Matrix((n, d_pt, z)).transposed()


def _tip_key_for(cam, half_deg):
    """(az, el) of a key that the planted tip's cross-section facets mirror toward `cam` at `half_deg` off its
    main flat (the smooth-shaded facets span about -14..+12 deg around the flat normal): a small half angle lights
    the whole flat (a glowing tube), ~12 deg lights only the steep edge facet (a thin line of light on the steel)."""
    B = _tip_planted_basis()
    n, ax = B.col[0].copy(), -B.col[1].copy()
    nh = (Matrix.Rotation(math.radians(-half_deg), 3, ax) @ n).normalized()
    v = (Vector(cam) - Vector(TIP_PLANT)).normalized()
    l = (2.0 * nh.dot(v) * nh - v).normalized()
    return (math.degrees(math.atan2(l.x, l.y)) % 360.0, math.degrees(math.asin(max(-1.0, min(1.0, l.z)))))


def _s26b_key():
    """S26b key: the tip flashes its steel as it stabs into the soaked mud (wet = narrow lobe: a 7 deg facet line)."""
    return _tip_key_for(S26B_CAM, TIP_SHEEN_OFFSET)


def _s29_key():
    """S29 key: only the edge facet catches the moon (a line of light, not a tube; wetness 0.3 = broader lobe)."""
    return _tip_key_for(S29_CAM, 12.5)


def props_break(SA):
    """3412: the blade snaps (click #3); the tip sinks and tumbles on the fx clock and plants point-down 3440,
    quivers about its base in slow motion, then stands untouched to 3840 (S29). 3414: the cord falls away."""
    import characters as CH
    import props as PR
    CH.set_weapon_state(SA, F["snap"], "broken")
    CH.snap_free("SAINT_katana_tip_broken", F["snap"])
    M0 = CH.detach_matrix("SAINT_katana_tip_broken", F["snap"])
    # planted point-down 7 cm deep at TIP_PLANT; the flat faces the S29 lens and the top leans 20 deg away from it,
    # so the steel reflects the moonlit sky above the camera (edge-on it read as a hairline in the layout pass)
    com_end = Vector(TIP_PLANT)
    R1 = _tip_planted_basis()
    tip_ob = _obj("SAINT_katana_tip_broken")
    _local_toss_fx("SAINT_katana_tip_broken", F["snap"], F["tip_plant"], M0.translation, (2.27, -1.42, -6.21),
                   M0.to_3x3(), R1, extra_turns=1, p1=com_end)
    # quiver about the base (a 20 Hz ring seen at 1/8): 3440 0, 3443 +4, 3448 -2.5, 3453 +1, 3456 0 deg
    d_pt = R1.col[1].copy()
    base = com_end + d_pt * 0.16
    q_ax = R1.col[0].copy()
    Mp = Matrix.Translation(com_end) @ R1.to_4x4()
    prev = tip_ob.rotation_euler.copy()
    for f, a in ((3443, 4.0), (3448, -2.5), (3453, 1.0), (3456, 0.0), (F1, 0.0)):
        Rq = Matrix.Translation(base) @ Matrix.Rotation(math.radians(a), 4, q_ax) @ Matrix.Translation(-base)
        prev = _key_matrix(tip_ob, f, Rq @ Mp, interp='BEZIER', prev=prev)
    U.set_key_interp_at(tip_ob, F1, 'CONSTANT')
    # the cord: cut 3414, drifts to screen-left (+X) on the slow clock; on the S27 cut it lies in the grass
    CH.set_beard_cord(F["cord"], True)
    CH.snap_free("SAINT_beard_cord_cut", F["cord"])
    Mc = CH.detach_matrix("SAINT_beard_cord_cut", F["cord"])
    PR.toss("SAINT_beard_cord_cut", F["cord"], p0=Mc.translation, v0=(5.0, -0.5, 0.8), spin=(1.5, -3.0, 4.0),
            rot0=Mc, drag=3.0, wind=(0.8, -0.1, -0.3), gravity=-1.6, f_end=3456, settle=False, key_start=False)
    cord = _obj("SAINT_beard_cord_cut")
    U.set_key_interp_at(cord, 3456, 'CONSTANT')
    rest = Matrix.Translation((1.05, -3.92, 0.02)) @ \
        (Matrix.Rotation(math.radians(35.0), 4, 'Z') @ Mc.to_quaternion().to_matrix().to_4x4())
    _key_matrix(cord, 3457, rest, interp='CONSTANT')
    _key_matrix(cord, F1, rest, interp='CONSTANT')


# =============================================================================================
# S24d/e: soaked tails hanging under a secondary override (D10), the drop, the whip; water droplet pools
# =============================================================================================
def _local_align_chain(rig, bones, f, dirs, interp='BEZIER'):
    """Key `bones` (a parent->child chain) at frame f so that each bone's +Y points along the WORLD direction in
    `dirs` (minimal rotation from its identity-basis pose under the evaluated parent)."""
    U.frame_set(f)
    mw = rig.matrix_world.to_3x3()
    for b, d in zip(bones, dirs):
        pb = rig.pose.bones[b]
        par = pb.parent
        rest_rel = par.bone.matrix_local.inverted() @ pb.bone.matrix_local
        M0 = par.matrix @ rest_rel
        R0w = (mw @ M0.to_3x3()).normalized()
        y0 = (R0w @ Vector((0.0, 1.0, 0.0))).normalized()
        q = y0.rotation_difference(Vector(d).normalized())
        Rb = R0w.inverted() @ q.to_matrix() @ R0w
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = Rb.to_euler('XYZ', pb.rotation_euler)
        U.key(pb, "rotation_euler", f, tuple(pb.rotation_euler), interp=interp)
        bpy.context.view_layer.update()


HANG_DEG = (40.0, 30.0, 15.0, 4.0)     # per segment, degrees behind the vertical (knot -> tip)
TAIL_MESH_END = 0.02                   # the hachimaki cloth runs 2 cm past the last bone's tail (measured)


def _hang_dirs(side_sign, extra_deg=0.0, fwd=(0.0, 1.0, 0.0), seg=None):
    """World directions of a soaked tail draped over his crouched back: segments hang HANG_DEG behind the vertical
    (+ extra, toward his back), the last one almost plumb so the drop falls straight; side_sign spreads the two
    tails (tail1 = his left = -X at facing 180). seg=None -> the 4 segment directions, else that one."""
    back = -Vector(fwd)
    out = []
    for i, a0 in enumerate(HANG_DEG):
        a = math.radians(a0 + (extra_deg[i] if isinstance(extra_deg, (list, tuple)) else extra_deg))
        d = back * math.sin(a) + Vector((0.0, 0.0, -math.cos(a)))
        d.x += side_sign * 0.04
        out.append(d.normalized())
    return out if seg is None else out[seg]


def tails(SH):
    """D10: the soaked tails drape down his back 3226-3256 (the ECU finds the tip where the camera aims, clear of
    the crouched hips), the unloaded tip bounces up after the drop leaves (3250-3253), then the tails whip back as
    he launches (3257-3264; the springs resume on the S25a marker)."""
    import lane_tools as LT
    LT.secondary_override(SH, 3226, 3264, bones=TAIL_BONES)
    t1 = [f"tail1.{i}" for i in (1, 2, 3, 4)]
    t2 = [f"tail2.{i}" for i in (1, 2, 3, 4)]
    for f in (3226, 3232, 3240, 3249, 3256):
        _local_align_chain(SH, t1, f, _hang_dirs(-1.0))
        _local_align_chain(SH, t2, f, _hang_dirs(+1.0))
    # release of the drop: the tip flicks up (damped) - a few mm at the end of a 0.138 m segment
    for f, dd in ((3251, -2.0), (3252, 1.0), (3253, -0.5), (3255, 0.0)):
        _local_align_chain(SH, t2, f, _hang_dirs(+1.0, extra_deg=[0.0, 0.0, 0.0, dd]))
    # the whip: each segment lags the one above by ~0.5 f, up to +55 deg back/up, still rising on 3264
    for f in range(3257, 3265):
        for chain, sgn in ((t1, -1.0), (t2, +1.0)):
            ex = []
            for i in range(4):
                u = max(0.0, min(1.0, (f - 3257.5 - 0.5 * i) / 4.0))
                ex.append(55.0 * U.ease(u, "inout_quad") + 10.0 * u * i)
            _local_align_chain(SH, chain, f, _hang_dirs(sgn, extra_deg=ex), interp='LINEAR')


def _tail_end(SH, f):
    """World position of the tail2 cloth's end (bone tail + TAIL_MESH_END along the last bone) at frame f."""
    h = U.world_pos_of((SH, "tail2.4"), f, where='head')
    t = U.world_pos_of((SH, "tail2.4"), f, where='tail')
    return t + (t - h).normalized() * TAIL_MESH_END


def _local_water_material(name="finale_water_drop", emission=0.22, tint=None):
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    mat = bpy.data.materials.new(name)
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    col = tuple(tint) if tint is not None else (0.72, 0.80, 0.90)
    tr = nt.nodes.new("ShaderNodeBsdfTranslucent")
    tr.inputs["Color"].default_value = (*col, 1.0)
    gl = nt.nodes.new("ShaderNodeBsdfGlossy")
    gl.inputs["Roughness"].default_value = 0.05
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.inputs[0].default_value = 0.75
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*col, 1.0)
    em.inputs["Strength"].default_value = emission
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(gl.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs["Surface"])
    mat.surface_render_method = 'DITHERED'
    mat.diffuse_color = (*col, 1.0)
    return mat


def _drop_mesh(name, r=0.0035):
    """UV sphere r (12 x 8) whose +Y half is stretched 1.15 (teardrop hanging along +Y)."""
    verts, faces = [], []
    nu, nv = 12, 8
    verts.append((0.0, -r, 0.0))
    for j in range(1, nv):
        th = math.pi * j / nv
        y = -r * math.cos(th)
        rr = r * math.sin(th)
        if y > 0:
            y *= 1.15
        for i in range(nu):
            ph = 2 * math.pi * i / nu
            verts.append((rr * math.cos(ph), y, rr * math.sin(ph)))
    verts.append((0.0, r * 1.15, 0.0))
    top, bot = 0, len(verts) - 1
    for i in range(nu):
        faces.append((top, 1 + (i + 1) % nu, 1 + i))
    for j in range(nv - 2):
        a0, b0 = 1 + j * nu, 1 + (j + 1) * nu
        for i in range(nu):
            faces.append((a0 + i, a0 + (i + 1) % nu, b0 + (i + 1) % nu, b0 + i))
    last = 1 + (nv - 2) * nu
    for i in range(nu):
        faces.append((last + i, last + (i + 1) % nu, bot))
    ob = U.mesh_from_data(name, verts, faces=faces, smooth=True, materials=[_local_water_material()])
    ob.visible_shadow = False
    return ob


def _local_drop(SH):  # noqa: C901
    """S24e: the drop swells at the tail2 tip (3233-3249, parented to bone tail2.4), detaches at 3250 into a free
    copy falling in REAL time (not slowed - the slow motion starts at 3269), leaves the frame ~3252, hidden 3254."""
    hang = _drop_mesh("S24e_finale_drop_hang", r=0.0042)
    U.parent_to_bone(hang, SH, "tail2.4", keep_world=False)
    hang.matrix_parent_inverse = Matrix.Identity(4)
    hang.location = (0.0, TAIL_MESH_END + 0.0035, 0.0)
    U.key_visible(hang, F0, False)
    U.key_visible(hang, 3233, True)
    U.key_visible(hang, F["drop"], False)
    for f, s, sy in ((3233, 0.35, 1.0), (3240, 0.62, 1.0), (3244, 0.86, 1.0), (3249, 1.0, 1.4)):
        U.key(hang, "scale", f, (s, s * sy, s), interp='BEZIER')
    U.frame_set(3249)
    M = U.world_matrix_of(hang, 3249)
    fall = _drop_mesh("S24e_finale_drop_fall", r=0.0042)
    U.key_visible(fall, F0, False)
    U.key_visible(fall, F["drop"], True)
    U.key_visible(fall, 3254, False)
    loc, rot, sca = M.decompose()
    fall.rotation_mode = 'QUATERNION'
    fall.rotation_quaternion = rot
    fall.scale = (sca.x * 0.9, sca.y * 1.25, sca.z * 0.9)
    for f in range(F["drop"], 3255):
        t = (f - F["drop"]) / config.FPS
        U.key(fall, "location", f, (loc.x, loc.y, loc.z - 0.5 * 9.81 * t * t - 0.004), interp='LINEAR')
    return hang, fall


def _local_droplets(frame, pos, direction, count, speed, spread, life, size, seed, tint=None):
    """A tiny fixed-count water-drop pool (vfx pool recipe: fx-time ballistics, scale 0 when unborn/dead,
    DITHERED, no shadow). Births frame + U[0, 1.5) f, v0 = cone(direction, spread) x speed x U[0.6, 1.3]."""
    import numpy as np
    import vfx
    rng = np.random.default_rng(seed)
    d = Vector(direction).normalized()
    a = d.orthogonal().normalized()
    b = d.cross(a).normalized()
    vel = []
    for _ in range(count):
        th = math.radians(spread) * math.sqrt(rng.random())
        ph = 2 * math.pi * rng.random()
        v = (d * math.cos(th) + (a * math.cos(ph) + b * math.sin(ph)) * math.sin(th)) * speed * rng.uniform(0.6, 1.3)
        vel.append(tuple(v))
    p0 = np.tile(np.asarray(pos, float), (count, 1)) + rng.normal(0.0, size * 0.8, (count, 3))
    birth = frame + rng.uniform(0.0, 1.5, count)
    lifes = life * rng.uniform(0.7, 1.3, count)
    shot = config.shot_at(int(frame))
    nm = f"{shot['id'] if shot else 'S'}_finale_droplets_{int(frame)}_{seed % 10000}"
    mat = _local_water_material("finale_mud_drop", 0.03, tint) if tint is not None else \
        vfx._water_material("VFX_spray_drop", glossy=0.7, emission=0.24)
    ob = vfx._pool(nm, "spray", p0, np.asarray(vel, float), birth, lifes, gravity=-9.81, drag=0.6,
                   instance=vfx._needle_source(), material=mat, size=size * rng.uniform(0.6, 1.2, count),
                   shrink=0.3, stretch=0.012, len0=1.6, align='velocity')
    ob.visible_shadow = False
    return ob


# =============================================================================================
# environment per cut (breakdown §3 env blocks; D7 white-out, D8 moon cheats, D9 clearance)
# =============================================================================================
W_SKY = 1.8            # scene-linear white of the camera-ray sky + aerial haze in the white-out (tuned on flash_qc)


def _local_whiteout(f):
    """D7: the env snapshot under the lightning: every environment surface IS the white sky (2 m haze distance),
    nothing lights the characters (no lamps, no ambient) -> black silhouettes on white. CONSTANT keys."""
    import environment as ENV
    for n in ("sky_zen", "sky_mid", "sky_hor"):
        ENV.set_param(f, n, (W_SKY, W_SKY, W_SKY))
    for n, v in (("sky_str", 1.0), ("glow_str", 0.0), ("disk_vis", 0.0), ("star_str", 0.0), ("cloud_alpha", 0.0),
                 ("cloud_billow", 0.0), ("cloud_cover", 0.0),
                 ("amb_str", 0.0), ("haze_dist", 2.0), ("haze_max", 1.0), ("fog_den", 0.0), ("mtn_glow", 0.0),
                 ("gobo_cover", 0.0), ("key_pow", 0.0), ("fill_pow", 0.0), ("bounce_pow", 0.0)):
        ENV.set_param(f, n, v)
    ENV.set_param(f, "fog_emit", (0.0, 0.0, 0.0))


def environment_timeline():
    import environment as ENV
    import render_setup as RS
    # ---- S24a: lane-start snapshot; the storm holds its breath (wind 0 until S28)
    near, far = ENV.CLEAR_NEAR, ENV.CLEAR_FAR
    ENV.set_state(3073, "storm_night")
    ENV.set_sun(3073, 272.0, 28.0)
    ENV.set_wind(3073, 0.0, direction_deg=config.WIND_DIR_DEFAULT, interp='CONSTANT')
    ENV.set_wetness(3073, 1.0, interp='CONSTANT')
    ENV.set_camera_clearance(3073, near, far, 0.0, 0.0)
    ENV.set_cloud_shadow(3073, edge='off')
    # ---- per-cut key light cheats (backlight 150-170 deg from each lens) + grass clearance
    key0 = ENV.STATES["storm_night"]["key_pow"]
    ENV.set_sun(3121, 236.0, 40.0)
    ENV.set_camera_clearance(3121, near, far)
    ENV.set_param(3121, "key_pow", key0 * 2.0)          # insert lighting cheat: lacquer + steel catch the key
    ENV.set_param(3157, "key_pow", key0)
    ENV.set_sun(3157, 268.0, 22.0)
    ENV.set_camera_clearance(3157, near, far)
    ENV.set_sun(3197, 262.0, 26.0)
    ENV.set_camera_clearance(3197, 3.0, 6.0)
    ENV.set_sun(3233, 268.0, 22.0)
    ENV.set_camera_clearance(3233, near, far)
    ENV.set_param(3233, "key_pow", key0 * 2.5)          # backlight the tail + the drop (ECU insert cheat)
    # ---- S25: the white-out (compositor 3265-3268 + env snapshot), fading back to the storm 3277 -> 3300
    w0, w1 = F["white"]
    RS.key_white_flash(w0, 1.0, duration=w1 - w0 + 1)
    _local_whiteout(w0)
    ENV.set_sun(w0, 270.0, 26.0)
    ENV.set_camera_clearance(w0, near, far)
    ENV.set_state(3277, "storm_night", blend_frames=23)
    ENV.set_wind(3269, 0.0, interp='CONSTANT')
    ENV.grass_effect("freeze", {}, 3269, 3456)
    # ---- S26
    ENV.set_sun(3361, 212.0, 28.0)
    ENV.set_camera_clearance(3361, near, far)
    ENV.set_sun(3429, *_s26b_key())                      # deviation: the flat mirrors it (breakdown 290/30)
    ENV.set_camera_clearance(3429, near, far)
    # ---- S27: storm -> moon (clouds part 3470-3550), the moonlight edge sweeps toward the lens 3505-3552
    ENV.set_state(3457, "storm_night")
    ENV.set_sun(3457, 347.0, 11.0, disk_deg=4.2)        # el 9 -> 11: the lens is lower + level (disk at y ~+0.7)
    ENV.set_state(3470, "moon_clear", blend_frames=80)
    ENV.set_wind(3457, 0.0, interp='CONSTANT')
    ENV.set_wetness(3457, 1.0, interp='CONSTANT')
    ENV.set_wetness(3560, 1.0, interp='LINEAR')
    ENV.set_camera_clearance(3457, 3.7, 5.5)
    # moonlit fill (az key+180, el 52): the backlit kneeling master read as a black hole in the foreground grass
    # (preview 3565); keyed on the blend's end key so the storm -> moon blend carries it (holds through S28/S29)
    ENV.set_param(3550, "fill_pow", 0.40)
    ENV.set_cloud_shadow(3457, edge=45.0, edge_dir_deg=326.0, edge_width=5.0, interp='CONSTANT')
    ENV.set_cloud_shadow(3505, edge=45.0, interp='LINEAR')
    ENV.set_cloud_shadow(3528, edge=8.0)
    ENV.set_cloud_shadow(3538, edge=0.5)
    ENV.set_cloud_shadow(3547, edge=-3.6)
    ENV.set_cloud_shadow(3552, edge=-14.0)
    ENV.set_cloud_shadow(3553, edge='off')
    # ---- S28: the low huge moon; the wind returns (silver waves rolling toward the lens)
    ENV.set_sun(3601, 350.0, 3.5, disk_deg=4.8)
    ENV.set_wind(3601, 0.0, direction_deg=170.0)
    for f, w in ((3625, 0.7), (3650, 1.1), (3668, 1.4), (3690, 1.0), (3715, 1.3), (3744, 1.0)):
        ENV.set_wind(f, w)
    ENV.set_wetness(3640, 0.55)
    ENV.set_camera_clearance(3601, near, far)
    # ---- S29
    ENV.set_sun(3745, *_s29_key())                       # deviation: side-front key (disk behind the lens)
    ENV.set_wind(3745, 0.6, direction_deg=170.0)
    ENV.set_wetness(3745, 0.30, interp='CONSTANT')      # the bare mud patch read as a pale mirror floor
    ENV.set_camera_clearance(3745, 2.2, 4.2)


def _window_overlaps(win, a, b):
    if win is None:
        return True
    try:
        w0, w1 = float(win[0]), float(win[1])
    except Exception:
        return True
    return w0 <= b and w1 >= a


VEIL_COLLECTIONS = ("VFX_rain", "VFX_steam", "VFX_smoke", "VFX_fire", "VFX_embers")


def _veil_objects():
    """Objects of other lanes' rain / steam / smoke / fire / ember effects alive during the white-out (D6)."""
    out = []
    for col in bpy.data.collections:
        if col.name not in VEIL_COLLECTIONS:
            continue
        for ob in col.all_objects:
            if ob.name.startswith("VFX_src"):
                continue
            if _window_overlaps(ob.get("vfx_window"), F["white"][0], F["blade_ring"] - 1):
                out.append(ob)
    return sorted(set(out), key=lambda o: o.name)


SIL_PROP = "fin_sil"                    # world prop read by the F2 holdout mix (VIEW_LAYER attribute)


def _local_sil_holdout(f0, f1):
    """Breakdown R1 fallback F2: the white-out silhouettes came out mid-grey (fast-GI bounce from the white haze
    field onto the figures). Insert in every character material a Mix Shader (fac = VIEW_LAYER attribute fin_sil,
    a world prop keyed 1 on [f0, f1), 0 elsewhere, CONSTANT) between the surface and a Holdout -> exact black
    with correct AA / motion blur. Outside the window the mix passes the original shader through."""
    w = bpy.context.scene.world
    w[SIL_PROP] = 0.0
    for f, v in ((F0, 0.0), (f0, 1.0), (f1, 0.0)):
        U.key(w, f'["{SIL_PROP}"]', f, v, interp='CONSTANT')
    obs, stack = set(), [o for o in bpy.data.objects if o.name.startswith(("SHINOBI_", "SAINT_"))]
    while stack:
        o = stack.pop()
        if o in obs:
            continue
        obs.add(o)
        stack.extend(o.children)
    mats = {sl.material for o in obs if o.type in ('MESH', 'CURVE') for sl in o.material_slots if sl.material}
    n = 0
    for m in sorted(mats, key=lambda m: m.name):
        nt = m.node_tree
        if nt is None:
            continue
        for o in [nd for nd in nt.nodes if nd.type == 'OUTPUT_MATERIAL']:
            sock = o.inputs["Surface"]
            if not sock.is_linked or sock.links[0].from_node.name.startswith("fin_sil_mix"):
                continue
            src = sock.links[0].from_socket
            mix = nt.nodes.new("ShaderNodeMixShader")
            mix.name = "fin_sil_mix"
            hold = nt.nodes.new("ShaderNodeHoldout")
            att = nt.nodes.new("ShaderNodeAttribute")
            att.attribute_type = 'VIEW_LAYER'
            att.attribute_name = SIL_PROP
            nt.links.new(att.outputs["Fac"], mix.inputs[0])
            nt.links.new(src, mix.inputs[1])
            nt.links.new(hold.outputs[0], mix.inputs[2])
            nt.links.new(mix.outputs[0], sock)
            n += 1
    return n


def _local_driver_hide(ob, f_hide, f_show):
    """An object whose hide_render is DRIVEN by a vfx time window (fire-ring lights): extend the driver's
    fx-time curve with a hidden step [f_hide, f_show) (driver curves are not NLA-stashed; the step only exists
    inside this lane's span). Returns True if a driver was extended."""
    import fxclock
    ad = ob.animation_data
    fc = next((d for d in ad.drivers if d.data_path == "hide_render"), None) if ad else None
    if fc is None:
        return False
    xh = fxclock.fx_time_at(f_hide) * 1000.0 - 0.1
    xs = fxclock.fx_time_at(f_show) * 1000.0 - 0.1
    v_show = float(fc.evaluate(xs + 0.05))
    for k in list(fc.keyframe_points)[::-1]:
        if xh - 1e-3 <= k.co.x <= xs + 1e-3:
            fc.keyframe_points.remove(k)
    for x, v in ((xh, 1.0), (xs, v_show)):
        k = fc.keyframe_points.insert(x, v, options={'FAST'})
        k.interpolation = 'CONSTANT'
    for k in fc.keyframe_points:
        k.interpolation = 'CONSTANT'
    fc.update()
    return True


def _local_hide(objs, f_hide, f_show):
    """Visible at the lane start, hidden [f_hide, f_show) (D6). Objects with a driven hide_render (vfx time
    windows: the ring lights) get the hidden step on their driver curve instead (_local_driver_hide)."""
    n = 0
    for ob in objs:
        ad = ob.animation_data
        driven = ad is not None and any(d.data_path == "hide_render" for d in ad.drivers)
        if driven:
            n += int(_local_driver_hide(ob, f_hide, f_show))
            continue
        U.key_visible(ob, F0, True)
        U.key_visible(ob, f_hide, False)
        U.key_visible(ob, f_show, True)
        n += 1
    return n


def dev_standins(ctx):
    """Partial builds of this lane alone lack act2's film rain (2376-3500) and the fire ring's glowing steam band
    (to 3456) that every finale image leans on. Only when NO rain object covers 3073 (i.e. act2 was not built in
    this scene) create stand-ins with the same recipes; a full build skips this."""
    import vfx
    have_rain = any(_window_overlaps(ob.get("vfx_window"), F0, CUT["S26b"][1]) and ob.get("vfx_window") is not None
                    for col in bpy.data.collections if col.name == "VFX_rain" for ob in col.all_objects
                    if not ob.name.startswith("VFX_src"))
    made = []
    if not have_rain:
        made.append(vfx.rain(2376, 3500, intensity=[(2376, 0.0), (2401, 1.0), (3470, 1.0), (3500, 0.0)],
                             seed=_seed("finale:rain_standin"), name="VFX_rain_3073_finale_standin"))
        # act2's ring call verbatim (act2.py RING): in this span only its extinguished state shows - the glowing
        # steam band, the ember ground glow and the dimmed ring lights (vfx fixed the unmasked glow centrally)
        ring = vfx.fire_ring(1633, (0.0, 1.5, 0.0), radius=11.0, grow_frames=12, f_out=2401, height=2.2,
                             seed=_seed("finale:ring_standin"), ember_rate=40.0, shadow_angles=(150.0, 210.0),
                             light_energy=400.0, name="VFX_ring_3073_finale_standin")
        made.extend(o for o in (ring.values() if isinstance(ring, dict) else []) if hasattr(o, "name"))
        print("[finale] dev stand-ins created (act2 rain / steam band absent in this build):",
              [getattr(o, "name", o) for o in made])
    return made


# =============================================================================================
# vfx
# =============================================================================================
def _blade_point(base, tip, f, u):
    with U.muted_modifiers():
        a = U.world_pos_of(_obj(base), f)
        b = U.world_pos_of(_obj(tip), f)
    return a.lerp(b, u)


def effects(SH, SA):
    import vfx
    # S24b: the click shakes the beads off the guard
    K = U.world_pos_of(_obj("SHINOBI_saya"), 3150)
    A = (U.world_matrix_of(_obj("SHINOBI_saya"), 3150).to_3x3() @ Vector((0.0, 1.0, 0.0))).normalized()
    _local_droplets(3150, K - A * 0.012, (0.2, 0.3, 1.0), 8, 0.6, 40, 10, 0.0016, _seed("S24b:0"))
    # S24c: rain bouncing off the rising steel (small, backlit - never a spray cloud)
    for i, f in enumerate(range(3168, 3197, 2)):
        p = _blade_point("SAINT_katana_base", "SAINT_katana_tip", f, 0.25 + 0.75 * ((i * 0.618) % 1.0))
        _local_droplets(f, p + Vector((0.0, 0.0, 0.012)), (0.0, 0.0, 1.0), 6, 1.0, 50, 9, 0.002,
                        _seed(f"S24c:{i}"))
    # S24e: the drop, then the tail flick flings water as he launches
    _local_drop(SH)
    T = _tail_end(SH, 3257)
    _local_droplets(3258, T, (0.0, 0.6, 0.8), 24, 2.2, 35, 10, 0.002, _seed("S24e:0"))
    # S26a: the thin vermilion wisp from the cut cord (cord colour, not blood), drifting to screen-left (+X)
    cord = U.world_pos_of(_obj("SAINT_beard_cord"), F["cord"] - 1)
    vfx.red_mist(F["cord"], tuple(cord), (1.0, -0.15, 0.12), seed=_seed("S26a:0"))
    # S26b: muddy beads hanging in the slow motion where the tip plants
    _local_droplets(F["tip_plant"], (0.98, -4.90, 0.01), (0.0, 0.0, 1.0), 14, 0.9, 55, 12, 0.0025,
                    _seed("S26b:0"), tint=(0.25, 0.22, 0.18))


# =============================================================================================
# cameras (all on the +X side of the action line; the S25 pass swaps the sides by action)
# =============================================================================================
def _s05_keys(f0, y):
    look_z = S05_AXIS["z"] + S05_AXIS["x"] * math.tan(math.radians(S05_AXIS["pitch_deg"]))
    return [(f0, (S05_AXIS["x"], y, S05_AXIS["z"]), (0.0, y, look_z), S05_AXIS["lens"])]


def cameras(SH, SA):
    a, b = CUT["S24a"]
    C.shot("S24a", a, b, _s05_keys(a, (SH0[1] + EL0[1]) * 0.5), dof=dict(focus=S05_AXIS["x"], fstop=5.6),
           subjects=["shinobi", "saint"], framing="wide")
    # S24b: ECU of the koiguchi from below-front-right, perpendicular to the saya axis (mirror of S06)
    saya = _obj("SHINOBI_saya")
    K = U.world_pos_of(saya, 3140)
    A = (U.world_matrix_of(saya, 3140).to_3x3() @ Vector((0.0, 1.0, 0.0))).normalized()
    u = _perp((0.69, 0.22, -0.69), A)
    a, b = CUT["S24b"]
    C.shot("S24b", a, b, [(a, tuple(K + u * 0.60), tuple(K - A * 0.015), 100.0),
                          (b, tuple(K + u * 0.59), tuple(K - A * 0.015), 100.0)],
           dof=dict(focus="SHINOBI_saya", fstop=4.0), subjects=["shinobi"], framing="ecu", clip=(0.02, 500.0))
    a, b = CUT["S24c"]
    C.shot("S24c", a, b, [(a, (3.80, 1.90, 0.50), (0.00, 2.02, 1.60), 28.0),
                          (b, (3.74, 1.92, 0.50), (0.00, 2.02, 1.62), 28.0)],
           dof=dict(focus=(SA, "head"), fstop=2.8), subjects=["saint"], framing="mcu")
    a, b = CUT["S24d"]
    C.shot("S24d", a, b, [(a, (6.30, -5.75, 1.62), (0.00, -5.82, 1.22), 85.0),
                          (b, (6.00, -5.75, 1.60), (0.00, -5.82, 1.22), 85.0)],
           dof=dict(focus=(SH, "chest"), fstop=2.8), subjects=["shinobi"], framing="mcu")
    # S24e: the tail tip where the override hangs it (evaluated), lens 0.5 m to +X
    T = _tail_end(SH, 3240)
    a, b = CUT["S24e"]
    # deviation: the lens sits 6 cm BELOW the tip looking up 6 deg (breakdown: level) so the drop hangs against
    # the glowing steam band / storm sky above the grass line instead of the black grass wall (read as black)
    C.shot("S24e", a, b, [(a, tuple(T + Vector((0.50, 0.0, -0.06))), tuple(T + Vector((0.0, 0.0225, -0.0074))),
                           100.0)],
           dof=dict(focus=0.50, fstop=2.8), subjects=[], framing="ecu", clip=(0.02, 500.0))
    y25 = -1.20
    for cut in ("S25a", "S25b"):
        a, b = CUT[cut]
        C.shot(cut, a, b, _s05_keys(a, y25), dof=dict(focus=S05_AXIS["x"], fstop=5.6), subjects=["shinobi", "saint"],
               framing="wide")
    C.impact_shake(F["final_pass"], strength=0.12, duration=14)
    a, b = CUT["S26a"]
    C.shot("S26a", a, b, [(a, (2.00, 4.50, 1.40), (-0.20, -1.30, 1.15), 40.0)],
           dof=dict(focus=3.85, fstop=2.8, distance_keys=[(3361, 3.85), (3398, 3.85), (3410, 8.8), (3428, 8.8)]),
           subjects=["shinobi", "saint"], framing="mcu")
    a, b = CUT["S26b"]
    C.shot("S26b", a, b, [(a, (2.15, -5.20, 0.30), (1.00, -4.87, 0.12), 50.0)],
           dof=dict(focus="SAINT_katana_tip_broken", fstop=2.8), subjects=[], framing="insert",
           clip=(0.02, 500.0))
    a, b = CUT["S27"]
    # deviation: lens 0.95 m (breakdown 1.35): the kneeling master's head and shoulders rise above the far grass line
    # against the moonlit field (at 1.35 m he sat below it, a black shape on black grass - preview 3565)
    C.shot("S27", a, b, [(a, (3.30, -6.30, 0.95), (-1.10, 0.25, 1.05), 30.0),
                         (b, (3.28, -6.27, 0.95), (-1.10, 0.25, 1.05), 30.0)],
           dof=dict(focus=3.8, fstop=5.6), subjects=["shinobi", "saint"], framing="medium")
    a, b = CUT["S28"]
    C.shot("S28", a, b, [(a, (1.55, -4.85, 1.05), (SA, "head"), 50.0),
                         (3672, (2.70, -7.90, 2.30), (0.55, 0.20, 1.05), 32.0),
                         (b, (4.30, -12.30, 4.50), (0.95, 5.20, 1.60), 24.0)],
           dof=dict(focus=1.66, fstop=2.8, fstop_keys=[(3601, 2.8), (3650, 8.0)],
                    distance_keys=[(3601, 1.66), (3640, 6.0), (3744, 12.0)]),
           subjects=["saint"], framing="mcu")
    a, b = CUT["S29"]
    cam = Vector(S29_CAM)
    to_tip = Vector(TIP_PLANT) + Vector((0.0, 0.0, 0.05)) - cam
    ang = math.atan(0.42 * 18.0 / 35.0)                 # the tip at NDC x ~ +0.42 (outside the title ellipse)
    look_dir = Matrix.Rotation(ang, 3, 'Z') @ Vector((to_tip.x, to_tip.y, 0.0)).normalized()
    look = cam + look_dir * 3.0 + Vector((0.0, 0.0, -0.10))
    C.shot("S29", a, b, [(a, tuple(cam), tuple(look), 35.0)],
           dof=dict(focus="SAINT_katana_tip_broken", fstop=4.0), subjects=[], framing="insert")


# =============================================================================================
# events (DIRECTION §8 + breakdown §2: every music cue explicit; nothing in the white silence 3265-3276)
# =============================================================================================
def story_events():
    EV.emit(F["silence"], "music_cue", cue="silence")
    EV.emit(3090, "step", who="shinobi", strength=0.25)
    EV.emit(3104, "step", who="shinobi", strength=0.30)
    EV.emit(3116, "whoosh", who="shinobi", weapon="katana", strength=0.15)
    EV.emit(3150, "sheathe", who="shinobi", tags=["sheathe"])
    EV.emit(3150, "tsuba_click", target="SHINOBI_saya", who="shinobi", tags=["tsuba_click", "click_motif_2"])
    EV.emit(F["drip"], "drip", pos=(0.03, -6.10, 0.0), tags=["drip"])
    # the two 'dash' events (3257 shinobi / 3258 saint) are emitted by moves.dash itself
    EV.emit(F["white"][0], "music_cue", cue="white_silence")
    slow = config.slowmo_window(F["contact"])            # (3269, 3456): 188 f
    EV.emit(F["contact"], "slowmo", duration=slow[1] - slow[0] + 1)
    EV.emit(F["blade_ring"], "music_cue", cue="blade_ring")
    EV.emit(F["final_pass"], "music_cue", cue="final_pass")
    EV.emit(F["final_pass"], "thunder", distance="near", pos=(-400.0, -1.2, 300.0), tags=["final_pass"])
    EV.emit(F["snap"], "sheathe", who="shinobi", tags=["sheathe"])
    EV.emit(F["snap"], "tsuba_click", target="SHINOBI_saya", who="shinobi", tags=["tsuba_click", "click_motif_3"])
    EV.emit(F["snap"], "sword_break", pos=(0.61, -4.49, 1.13), tags=["sword_break"])
    EV.emit(F["cord"], "cord_cut", pos=(0.30, -3.72, 1.38), tags=["cord_cut"])
    EV.emit(F["tip_plant"], "land", pos=(0.98, -4.90, 0.0), strength=0.25, tags=["blade_tip"])
    EV.emit(F["kneel"], "kneel", who="saint", tags=["kneel"])
    EV.emit(F["kneel"], "rain_stop")
    EV.emit(F["stub"], "hit", pos=(0.30, -3.98, 0.05), strength=0.3, tags=["plant_blade"])
    EV.emit(F["epilogue"], "music_cue", cue="epilogue")
    EV.emit(3610, "wind_gust", strength=0.5)
    EV.emit(3680, "wind_gust", strength=0.35)
    EV.emit(3746, "wind_gust", strength=0.2)
    EV.emit(F["bell"], "music_cue", cue="end_card")
    EV.emit(F["bell"], "bell", pos=(0.0, 60.0, 5.0), tags=["end_card"])


# =============================================================================================
# lane entry
# =============================================================================================
def _local_silence_events(f0, f1):
    """Breakdown S25: NOTHING may sound in the white silence 3265-3276 (reverb tails would leak past it). The dash
    macro and the foot bake emit steps there (the dash, the 3269/3270 pass keys and the 3271 tableau jump). Bake
    the feet of the span now (end_lane's own bake then finds every step already evented and emits none - the bake
    is deterministic, re-running it re-solves the same keys) and drop this lane's sound events in [f0, f1];
    control events (music_cue, slowmo) stay."""
    import moves as M
    M.bake_feet(None, (F0 - 0.5, F1 + 0.5))
    keep = {"music_cue", "slowmo"}
    before = len(EV._EVENTS)
    EV._EVENTS[:] = [e for e in EV._EVENTS
                     if not (e.get("_lane") == LANE and f0 <= float(e["frame"]) <= f1 and e["type"] not in keep)]
    print(f"[finale] white silence: dropped {before - len(EV._EVENTS)} sound events in {f0}-{f1}")


def build(ctx):
    """Lane entry (acts contract): keys only inside SPAN, cameras through cameras.shot, events through events.emit."""
    sh, sa = ctx["chars"]["shinobi"], ctx["chars"]["saint"]
    stubs = ctx.get("stubs", {})
    missing = [m for m in ("characters", "moves", "environment", "vfx", "poses") if stubs.get(m)]
    if missing:
        raise RuntimeError(f"finale needs the real modules (placeholders: {missing})")
    _POSES.clear()
    entering_state(sh, sa)
    shinobi(sh)
    elder(sa)
    the_pass(sh, sa)
    elder_after(sa)
    shinobi_after(sh)
    props_break(sa)
    tails(sh)
    environment_timeline()
    made = dev_standins(ctx)
    veil = _veil_objects()
    rain = [o for o in veil if any(c.name == "VFX_rain" for c in o.users_collection)]
    other = [o for o in veil if o not in rain]
    n_hidden = _local_hide(rain, F["white"][0], F["blade_ring"])      # the rain returns hanging (1/8) at 3277
    n_hidden += _local_hide(other, F["white"][0], F["final_pass"])    # steam band back with the thunderclap
    print(f"[finale] white-out veil: {n_hidden}/{len(veil)} objects keyed hidden 3265-3276 "
          f"({[o.name for o in veil]})")
    n_sil = _local_sil_holdout(F["contact"] - 4, F["blade_ring"])     # 3265 (under the white) .. 3276
    print(f"[finale] white-out holdout silhouettes: {n_sil} material outputs")
    effects(sh, sa)
    cameras(sh, sa)
    story_events()
    _local_silence_events(F["white"][0], F["blade_ring"] - 1)
    for ob in (sh, sa, _obj("SHINOBI_sword_ctrl"), _obj("SAINT_sword_ctrl"), _obj("SHINOBI_saya"),
               _obj("SAINT_saya"), _obj("SAINT_katana_tip_broken"), _obj("SAINT_beard_cord_cut")):
        if ob is not None:
            U.freeze_handles(ob, SPAN)
    return dict(standins=[getattr(o, "name", str(o)) for o in made])
