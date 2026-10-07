"""
acts/act1b.py - lane act1b: S10-S14, frames 937-1632. Shot timing and staging are defined below.

Story: the student circles and vanishes into the grass (S10); the master listens, re-sheathes and answers with one
draw-cut that shears the grass tops; the student is flushed into the air and comes down on the master's one-handed
overhead block (S11); a flurry of six clashes on the 92-BPM grid, a blade lock against the sun, the shove on the cut
(S12); the master's first two-handed blow is perfectly deflected (slow motion), the counter splits his straw hat
(S13); bare-headed, he sheathes, sheds the haori, draws the vermilion spear over his shoulder as the sun disappears
and raises it for the butt slam that opens Act II (S14).

    Blender -b --factory-startup --python-exit-code 1 --python codecinema/productions/silvergrass/blender/build_scene.py -- --lanes act1b \
        --quality preview

Enters HANDOFF[936], leaves HANDOFF[1632] (config).  Every clash goes through moves.clash (resolved at end_lane),
every camera through cameras.shot (26 sub-cuts, keys from the breakdown), events through events.emit.
Local poses are registered into poses.POSES under the prefix 'a1b_' (this process only); local helpers are
prefixed _local_.
"""

import math
import zlib

import bpy
from mathutils import Vector

import config
import bl_util as U
import cameras as C
import events as EV
from acts import sub_cuts

LANE = "act1b"
SPAN = tuple(config.lane_span(LANE))                 # (937, 1632)
HIN = config.HANDOFF[SPAN[0] - 1]                    # HANDOFF[936]
HOUT = config.HANDOFF[SPAN[1]]                       # HANDOFF[1632]
# 26 sub-cuts: the config shots split at these starts (S10a 937-990 ... S14e 1605-1632)
CUTS = sub_cuts(LANE, {"S10": (991, 1013), "S11": (1073, 1097, 1119, 1135),
                       "S12": (1198, 1213, 1229, 1244, 1260, 1276, 1321), "S13": (1369, 1409, 1423, 1451),
                       "S14": (1525, 1553, 1575, 1605)})
CUT = {c: (a, b) for c, a, b in CUTS}
E0 = tuple(HIN["saint"]["pos"])                      # (0, 2.6): the elder's spot through S10-S12a
H_POS = (0.25, -1.54)                                # where the ripple stops (the hidden student, 4.15 m)
R_CIRCLE = math.hypot(HIN["shinobi"]["pos"][0] - E0[0], HIN["shinobi"]["pos"][1] - E0[1])   # 4.41 m


def _seed(tag):
    """Deterministic seed (zlib.crc32 of '<shot>:<i>' style tags, never hash())."""
    return zlib.crc32(str(tag).encode()) & 0x7FFFFFFF


def _beat(n):
    return config.beat_frame("act1", n)


def _face(src, dst):
    """facing (deg) so that (sin a, -cos a) points from src to dst."""
    return math.degrees(math.atan2(dst[0] - src[0], -(dst[1] - src[1])))


def _circ(center, r, ang_deg):
    a = math.radians(ang_deg)
    return (center[0] + r * math.cos(a), center[1] + r * math.sin(a))


def _unwrap(prev, a):
    """a (deg) moved by whole turns to be continuous with prev."""
    return prev + ((a - prev + 180.0) % 360.0 - 180.0)


# =============================================================================================================
# local poses (registered into poses.POSES; authored in SHINOBI metres like the library, rig space facing -Y)
# =============================================================================================================
def _local_register_poses(PZ):
    """Poses the library lacks.  Controllers of the library poses they derive from are
    re-used where the moves lane machine-tuned them for the wrists (poses.TUNED)."""
    P = PZ

    def add(name, p):
        p["_name"] = name
        P.POSES[name] = p

    # --- the student hidden in the grass: trunk folded, head top under the grass tops, blade two-handed, low
    #     (crouch_hide's tuned blade: level, forward, 0.42 m high - under the tops, ready)
    add("a1b_grass_crouch", P.pose(
        "S10 kusa-gakure crouch-run: deep squat, trunk folded over the knees, eyes forward, blade low and flat",
        "story", body=P.torso(lean=66, look_pitch=-44),
        hips=(0.0, -0.64, 0.0),
        legs={"R": P.foot(-0.16, -0.22, heel=28), "L": P.foot(0.16, 0.16, heel=42)},
        ctrl=P.blade((-0.05, -0.36, 0.42), (0.0, -0.9962, -0.0872), edge=(-0.0654, 0.087, -0.9941)), left="grip"))
    add("a1b_grass_coiled", P.pose(
        "S11 coiled in the grass: weight on the balls of the feet, blade two-handed at his right side, tip up "
        "toward the master but under the grass tops", "story",
        body=P.merge(P.torso(lean=60, twist=-8, look_pitch=-46)),
        hips=(0.0, -0.66, 0.02),
        legs={"R": P.foot(-0.17, -0.20, heel=40), "L": P.foot(0.17, 0.18, heel=55)},
        ctrl=P.blade((-0.12, -0.30, 0.46), P.elev(14, yaw=4)), left="grip"))
    # --- the elder listening: his one-handed low guard, head lowered (brim over the eyes), tip down in the tops
    add("a1b_elder_listen", P.pose(
        "S10 listening: low_1h with the head lowered 12 deg, blade tip down into the grass tops", "story",
        body=P.merge(P.torso(lean=3, twist=-10, look_pitch=14), P.arm("L", flex=15, abd=-30, elbow=70)),
        hips=(0.0, -0.05, 0.0),
        legs=P.stance(front=0.20, back=0.24, width=0.28, heel_back=6),
        ctrl=P.blade((-0.16, -0.22, 0.90), P.elev(-35, yaw=6)), left="saya"))
    # --- the elder's rebound after the perfect deflect: blade thrown up past vertical over his RIGHT shoulder
    #     (clear of the straw brim), trunk arched back, chin up, weight on the heels; two-handed
    add("a1b_posture_broken", P.pose(
        "S13 posture broken: blade flung up and back over the right shoulder, chest open, chin up, heels", "evade",
        body=P.torso(lean=-14, twist=8, look_pitch=-10, gaze=0.5),
        hips=(0.0, -0.10, -0.08),
        legs={"R": P.foot(-0.13, -0.26, heel=6), "L": P.foot(0.14, 0.34, heel=0)},
        ctrl=P.blade((-0.30, -0.02, 1.48), (-0.3061, 0.6122, 0.7291), edge=(0.326, -0.6521, 0.6845)), left="grip",
        elbow={"R": "auto", "L": "auto"}, hat_tilt=(18.0, 0.0)))
    # --- the elder's overhead at the moment of CONTACT (S12 1273, S13 1367): arms extended forward at forehead
    #     height, blade 22 deg above the horizontal - the blow is met high, above the student's head
    add("a1b_overhead_contact", P.pose(
        "overhead cut at the contact: fists forward at forehead height, blade 22 deg up, lunge", "attack",
        body=P.merge(P.torso(lean=10, look_pitch=-6), P.arm("L", flex=40, abd=10, elbow=35, wflex=-10)),
        hips=(0.0, -0.16, 0.04),
        legs=P.stance(front=0.46, back=0.40, width=0.26, heel_back=30),
        ctrl=P.blade((-0.05, -0.50, 1.52), P.elev(22), edge=(-0.86, -0.19, -0.47)), left="grip",
        elbow={"R": "auto", "L": "auto"}))
    # --- the elder's kesa met HIGH (S12d 1241, against the sun): one-handed, fist in front of the right shoulder,
    #     blade forward-down to his left, crossing above the student's head
    add("a1b_kesa_high", P.pose(
        "one-handed kesa at the contact: fist high in front of the right shoulder, blade forward-down-left", "attack",
        body=P.merge(P.torso(lean=8, twist=-14, look_pitch=-4), P.arm("L", flex=15, abd=-30, elbow=70)),
        hips=(0.0, -0.14, 0.03),
        legs=P.stance(front=0.40, back=0.36, width=0.26, heel_back=24),
        ctrl=P.blade((-0.13, -0.47, 1.51), P._norm((0.30, -0.88, -0.36)), edge=(0.41, 0.46, -0.79)),
        left="saya", elbow={"R": "auto"}))
    # --- the student's low chamber before the kiriage (blade at his right hip, tip back-down)
    add("a1b_low_chamber_R", P.pose(
        "S13c low chamber on the right before the rising cut", "attack",
        body=P.torso(lean=18, twist=-20, look_pitch=-8),
        hips=(0.0, -0.20, 0.02),
        legs=P.stance(front=0.34, back=0.36, width=0.26, heel_back=26),
        ctrl=P.blade((-0.30, -0.22, 0.88), P._norm((-0.58, 0.62, -0.53))), left="grip"))
    # --- the steep kiriage end: near-vertical blade plane in front of the elder's face
    add("a1b_kiriage", P.pose(
        "S13c steep rising cut (kiriage): arms extended up-forward, blade 75 deg up", "attack",
        body=P.torso(lean=10, twist=6, look_pitch=-16),
        hips=(0.0, -0.14, 0.05),
        legs=P.stance(front=0.50, back=0.40, width=0.26, heel_back=34),
        ctrl=P.blade((0.02, -0.52, 1.36), P._norm((0.06, -0.26, 0.96))), left="grip"))
    # --- the spear raised vertically in front of the right shoulder for the butt slam (S14e -> act2 1633)
    for nm, gz, lean, hips in (("a1b_spear_raise", 1.80, -4.0, -0.04), ("a1b_spear_drive", 1.56, 8.0, -0.12)):
        add(nm, P.pose(
            "S14e spear upright in front of the right shoulder, both hands, butt above the ground", "spear",
            body=P.merge(P.torso(lean=lean, twist=-10, look_pitch=-2),
                         P.arm("L", flex=50, abd=-10, elbow=80)),
            hips=(0.0, hips, 0.02),
            legs=P.stance(front=0.26, back=0.28, width=0.32, heel_back=8),
            ctrl={"grip": (0.04, -0.42, gz), "dir": (0.0, 0.0, 1.0), "edge": (0.0, -1.0, 0.0), "scale": False},
            weapon="spear", left="grip", chars=["SAINT"]))


# =============================================================================================================
# small keying helpers
# =============================================================================================================
def _local_strike(M, PZ, rig, f, kind, two_hand=None, lunge=0.0, windup=None, hold_frames=None, strike=None,
                  whoosh=True, strength=0.8, strike_pose=None):
    """moves.slash WITHOUT the follow-through / recovery: anticipation -> windup -> arc into the strike pose at f
    (the next action - a blade lock, the perfect-deflect rebound - takes over from the contact).  Same timing
    tables as moves.slash.  Returns f."""
    tm = dict(M.SLASH_TIMING["default"], **M.SLASH_TIMING.get(kind, {}))
    if PZ.char_of(rig) == "SAINT":
        for k, v in M.SAINT_TIMING.items():
            tm[k] = tm[k] * v
    for k, v in (("windup", windup), ("hold", hold_frames), ("strike", strike)):
        if v is not None:
            tm[k] = v
    T = M.clock(f)
    w, h, s = tm["windup"], tm["hold"], tm["strike"]
    lag_d = {"hips": -1, "neck": 1, "head": 1}
    if two_hand is not None:
        import characters as CH
        CH.set_two_hand(rig, T(-(s + h + w)), bool(two_hand), blend=2)
    M.hold(rig, T(-(s + h + w)))
    wt = 0.85 if PZ.char_of(rig) == "SAINT" else 1.0
    M.pose(rig, T(-(s + h)), f"{kind}_windup", weight=wt)
    M.pose(rig, T(-s), f"{kind}_windup", weight=wt * 1.04, lag=lag_d, feet=False)
    Ma = PZ.current_ctrl_matrix(rig, T(-s))
    sp = strike_pose or f"{kind}_strike"
    M.swing(rig, T(-s), T(0), Ma, M.ctrl_matrix(rig, sp, T(0)), ease="in_quad", clk=T)
    M.pose(rig, T(0), sp, lag=lag_d, ctrl=False)
    if lunge:
        x, y, _, a = M.root_at(rig, T(-s - 1))
        M.root(rig, T(-s - 2), (x, y), a, interp='LINEAR')
        M.lunge_root(rig, T(-s - 1), T(1), lunge, ease="inout_quad", clk=T)
    if whoosh:
        M.emit(int(round(T(-1))), "whoosh", who=M.who(rig), weapon="katana", strength=round(strength, 2),
               target=(rig, "hand.R"))
    return f


def _local_sheathe(M, PZ, CH, rig, f, dur=12, end="relaxed_saya", end_after=8, release=True):
    """Quick noto WITHOUT the tsuba_click event (the click motif belongs to S06 / S24b / S26 - breakdown §2):
    f = the guard seats; the left hand goes to the saya, the kissaki finds the koiguchi, the blade slides home,
    then either the right hand leaves the hilt (release=True: IK -> FK into `end`) or it stays on the sheathed
    hilt and the body settles into `end` (release=False, e.g. the iai crouch).  Emits 'sheathe' at f.
    Returns the end frame."""
    T = M.clock(f)
    M.hold(rig, T(-dur))
    M.pose(rig, T(-dur * 0.62), "sheathe_quick_1", hands="pose", hand_blend=4)
    M.pose(rig, T(-dur * 0.30), "sheathe_quick_2")
    M.pose(rig, T(0), "sheathe_done", hands="pose")
    CH.set_weapon_state(rig, int(round(T(0))), "sheathed")
    M.emit(int(round(f)), "sheathe", who=M.who(rig))
    if release:
        CH.set_arm_mode(rig, T(3), "fk", blend=4)
        M.pose(rig, T(end_after), end, hands="pose", ctrl=False)
        PZ.key_saya(rig, T(end_after), 0.0, 0.0)
    else:
        M.pose(rig, T(end_after), end, hands="pose")
    return T(end_after)


def _local_root_arc(M, rig, f0, f1, a0, a1, r0, r1, center, face_to=None, step=2, ease="inout_quad", z=None):
    """Root along an arc about `center` (angles deg CCW from +X, radius r0 -> r1) with per-`step` LINEAR keys,
    facing `face_to` (xy) continuously.  z: None or callable(u) -> height."""
    prev = M.facing_of(rig, f0)
    fr = list(range(int(f0), int(f1) + 1, step))
    if fr[-1] != int(f1):
        fr.append(int(f1))
    for f in fr:
        u = U.ease((f - f0) / float(f1 - f0), ease) if f1 > f0 else 1.0
        a = a0 + (a1 - a0) * u
        r = r0 + (r1 - r0) * u
        p = _circ(center, r, a)
        fc = _unwrap(prev, _face(p, face_to)) if face_to is not None else prev
        prev = fc
        M.root(rig, f, p, fc, z=(z(u) if z else 0.0), interp='LINEAR')
    return f1


def _local_place_tip(M, PZ, CH, rig, f, tip_world, falloff=3, assist=0.15):
    """Translate the sword controller (cosine falloff +-falloff story frames) so that the blade TIP passes
    through `tip_world` at f; the horizontal part beyond `assist` m goes to the root (half a step, like moves.clash).
    Used for the hat cut (steel on straw - no clash)."""
    base, tip = M.ideal_segment(rig, f)
    delta = Vector(tip_world) - tip
    if assist is not None and delta.length > assist:
        horiz = Vector((delta.x, delta.y, 0.0))
        shift = horiz * max(0.0, 1.0 - assist / delta.length)
        if shift.length > 1e-3:
            M.offset_root(rig, f, shift, 6)
            delta = delta - shift
    if delta.length > 1e-4:
        M.offset_ctrl(rig, f, delta, falloff)
    return delta


# =============================================================================================================
# choreography
# =============================================================================================================
def _entering_state(M, CH, SH, SA):
    """Re-assert HANDOFF[936] at the lane's first frame (lane isolation: the first key extrapolates backwards)."""
    f = SPAN[0]
    CH.set_weapon_state(SH, f, "drawn")
    CH.set_arm_mode(SH, f, "ik")
    CH.set_two_hand(SH, f, True)
    CH.set_kunai_in_hand(f, False)
    for i in (1, 2, 3):
        U.key_visible(bpy.data.objects[f"SHINOBI_kunai_{i}"], f, False)
    CH.set_weapon_state(SA, f, "slung")            # spear on his back (keys active_weapon = katana)
    CH.set_weapon_state(SA, f, "drawn")
    CH.set_arm_mode(SA, f, "ik")
    CH.set_left_hand(SA, f, "saya")
    CH.set_costume(f, haori=True)
    CH.set_hat(f, "on")
    CH.set_hat_tilt(f, 0.0, 0.0)
    CH.set_beard_cord(f, False)
    CH.set_spear_grip(f, 0.35, 0.95)
    M.root(SH, f, HIN["shinobi"]["pos"], float(HIN["shinobi"]["facing"]))
    M.root(SA, f, E0, float(HIN["saint"]["facing"]))
    M.stance(SH, f, "chudan", hands="pose")
    M.stance(SA, f, "low_1h", hands="keep")


def _s10(M, PZ, CH, SH, SA):
    """S10 937-1032: the circle, hiding in the grass, the ripple, the master listens."""
    # ---- the student circles CCW around the master (4.41 m), then sinks into the grass while still sliding
    M.stance(SH, 941, "chudan", hands="keep")
    a_sink = -86.1 + 25.0 * 36.0 / 40.0                                   # angle reached at 978
    M.strafe(SH, 942, 978, center=E0, radius=R_CIRCLE, a0=-86.1, a1=a_sink, upper="chudan")
    M.hold(SH, 978)
    p_hide = (2.01, -1.36)
    x, y, _, a = M.root_at(SH, 978)
    M.root_path(SH, 978, 988, (x, y), p_hide, facing1=_unwrap(a, _face(p_hide, E0)), ease="out_quad")
    M.pose(SH, 983, "a1b_grass_crouch", weight=0.55, feet=False)
    M.pose(SH, 987, "a1b_grass_crouch", weight=1.04, feet=False)
    M.pose(SH, 988, "a1b_grass_crouch")
    # ---- hidden: crouch-run back round the master (CW) to H - only the grass ripple betrays him
    a0 = math.degrees(math.atan2(p_hide[1] - E0[1], p_hide[0] - E0[0]))
    r0 = math.hypot(p_hide[0] - E0[0], p_hide[1] - E0[1])
    aH = math.degrees(math.atan2(H_POS[1] - E0[1], H_POS[0] - E0[0]))
    rH = math.hypot(H_POS[0] - E0[0], H_POS[1] - E0[1])
    _local_root_arc(M, SH, 988, 1040, a0, aH, r0, rH, E0, face_to=E0, step=2, ease="smooth")
    for i, f in enumerate(range(994, 1040, 6)):                          # a low stride every 6 f (feet re-plant)
        M.pose(SH, f, "a1b_grass_crouch", mirror=bool(i % 2 == 0))
    M.pose(SH, 1040, "a1b_grass_coiled")
    M.pose(SH, 1046, "a1b_grass_coiled", feet=False)
    # ---- the master: pivots in place with the student (two shuffles), then lowers his head and listens
    M.stance(SA, 941, "low_1h", hands="keep")
    f_mid = 960
    x, y, _, _ = M.root_at(SH, f_mid)
    M.turn(SA, 942, f_mid, _face(E0, (x, y)))
    x, y, _, _ = M.root_at(SH, 978)
    M.turn(SA, f_mid, 980, _face(E0, (x, y)))
    M.hold(SA, 983)
    M.pose(SA, 991, "a1b_elder_listen", hands="keep")
    M.pose(SA, 1004, "a1b_elder_listen", hands="keep", feet=False)
    M.pose(SA, 1012, "a1b_elder_listen", hands="keep", feet=False)
    M.overlay(SA, 1012, {"neck": (0.0, -3.0, 0.0), "head": (0.0, -3.0, 0.0)})     # turns an ear to his right
    M.hold(SA, 1018)
    M.pose(SA, 1026, "a1b_elder_listen", hands="keep", feet=False)
    M.overlay(SA, 1026, {"neck": (0.0, -7.0, 0.0), "head": (0.0, -7.0, 0.0)})
    M.hold(SA, 1034)


def _s11(M, PZ, CH, SH, SA, marks):
    """S11 1033-1176: re-sheathe, iai crouch, THE DRAW-CUT (1101) that shears the grass tops, the leap, the
    one-handed overhead block (1132), the heave, the reset."""
    # ---- the master re-sheathes one-handed (seats 1054, no click) and sinks into his iai crouch
    _local_sheathe(M, PZ, CH, SA, 1054, dur=18, end="iai_crouch", end_after=14, release=False)
    M.pose(SA, 1076, "iai_crouch", hands="keep", feet=False)
    # the student: coiled, head lifts a little at the sound, legs load
    M.pose(SH, 1078, "a1b_grass_coiled", feet=False)
    M.overlay(SH, 1084, {"head": (-4.0, 0.0, 0.0), "neck": (-2.0, 0.0, 0.0)})
    M.pose(SH, 1090, "a1b_grass_coiled", feet=False)
    M.overlay(SH, 1090, {"head": (-4.0, 0.0, 0.0)})
    # ---- THE DRAW-CUT (beat 30 = 1101) with the iai pivot toward the sound (28.9 -> 3.45 deg)
    f_cut = _beat(30)                                                        # 1101
    fa = M.facing_of(SA, 1090)
    M.root(SA, 1094, E0, fa, interp='BEZIER')
    a_cut = _unwrap(fa, _face(E0, H_POS))                                    # 3.45
    M.root(SA, f_cut + 1, E0, a_cut, interp='BEZIER')
    M.iai_slash(SA, f_cut, "horizontal", "L", lunge=0.0, recover=12, recover_to="deflect_overhead_block")
    marks["cut"] = f_cut
    # ---- the leap: take-off 1102 above the cut-line, the plunge onto the raised blade at 1132 (beat 32)
    f_imp = _beat(32)                                                        # 1132
    f_land = f_imp + 2
    p_land = (0.03, 1.40)
    M.plunge(SH, f_cut + 1, f_land, H_POS, p_land, apex=2.15, impact=f_imp, recover=4, recover_to="plunge_land")
    U.delete_keys(SH, (f_land - 1, f_land - 1), "pose.bones")              # moves.plunge: jump's T1(-1) air key
    M.root(SH, f_land, p_land, 180.0, interp='LINEAR')                     # squares up on the landing
    # the master's one-handed overhead block, held; knees give on the hit; the heave throws the student off
    M.deflect(SA, f_imp, "overhead_block", approach=4, recoil=1.3, hold_frames=6, recover=10)
    M.root(SA, f_imp + 2, E0, a_cut, interp='BEZIER')
    M.root(SA, f_imp + 8, E0, 0.0, interp='BEZIER')
    M.shift_ctrl(SA, f_imp + 11, (0.0, -0.20, 0.16))                        # the heave: fist up-forward
    M.clash(SH, SA, f_imp, point=None, strength=1.0, kind="clash_heavy", tags=["overhead_block"],
            sparks=dict(color="white", count=120, scale=1.6, direction=(0.0, -0.3, 1.0)))
    marks["block"] = f_imp
    # ---- thrown off: a hop back, landing low, a short slide, up to chudan
    M.jump(SH, 1140, 1152, (p_land[0], p_land[1] - 0.05), (0.0, 0.30), apex=0.55, crouch=0,
           land_pose="jump_land", recover=14)
    # moves.jump drops into the full landing crouch on the touchdown frame (head -0.48 m in 1 f): absorb it over 3 f
    U.delete_keys(SH, (1151, 1152), "pose.bones")
    U.delete_keys(PZ._ctrl_obj(SH), (1151, 1152))
    M.pose(SH, 1152, "jump_land", weight=0.45, feet=False)
    M._feet_air(SH, 1152.5)                                                 # the feet slide with him ...
    M.root_path(SH, 1152, 1158, (0.0, 0.30), (0.0, 0.15), ease="out_cubic")
    M.pose(SH, 1158, "jump_land", weight=0.9)                               # ... and plant when he stops
    M.emit(1152, "skid", who="shinobi", duration=6)
    M.step(SA, 1170, 1176, (0.0, 2.50))


# S12 root tracks (y on the x = 0 line; the student faces 180, the master 0) - separations 1.55-1.60 m at the
# contacts (1.25 at 1273), 0.92 m in the lock; intermediate keys give each strike its weight transfer
SH_Y12 = [(1176, 0.20), (1181, 0.25), (1189, 0.60), (1195, 0.88), (1201, 0.86), (1210, 0.80), (1219, 0.82),
          (1226, 0.95), (1233, 0.92), (1241, 0.85), (1249, 0.87), (1257, 1.02), (1265, 1.04), (1273, 1.15),
          (1276, 1.30), (1288, 1.37), (1296, 1.37), (1304, 1.28), (1312, 1.29), (1320, 1.33)]
SA_Y12 = [(1176, 2.50), (1190, 2.50), (1195, 2.46), (1203, 2.46), (1210, 2.40), (1218, 2.48), (1226, 2.55),
          (1233, 2.52), (1241, 2.42), (1250, 2.52), (1257, 2.62), (1266, 2.45), (1273, 2.40), (1276, 2.22),
          (1288, 2.29), (1296, 2.29), (1304, 2.20), (1312, 2.21), (1320, 2.23)]
# the six contacts on beats 36-41 (config S12 desc: 1195 for beat 36, D2)
F12 = dict(c1=1195, c2=_beat(37), c3=_beat(38), c4=_beat(39), c5=_beat(40), c6=_beat(41), shove=_beat(44))


def _s12(M, PZ, CH, SH, SA, marks):
    """S12 1177-1344: six clashes on the beat grid (student / master alternating), the lock against the sun, the
    shove hidden by the cut (1320), the skid apart."""
    for f, y in SH_Y12:
        M.root(SH, f, (0.0, y), 180.0, interp='BEZIER')
    for f, y in SA_Y12:
        M.root(SA, f, (0.0, y), 0.0, interp='BEZIER')
    M.stance(SA, 1176, "low_1h", hands="keep")
    M.stance(SH, 1178, "chudan", hands="keep")
    c = F12
    # 1 - the student's kesa, the master's one-handed block on his left
    M.slash(SH, c["c1"], "diag_down_R", follow=3, recover=7, strength=0.7)
    M.deflect(SA, c["c1"], "mid_L", recover=3)
    M.clash(SH, SA, c["c1"], strength=0.70, sparks=dict(color="white"))
    # 2 - the master's horizontal cut, the student blocks on his left
    M.slash(SA, c["c2"], "horizontal_R", recover=6, strength=0.75)
    M.deflect(SH, c["c2"], "mid_L", recover=3)
    M.clash(SA, SH, c["c2"], strength=0.75)
    # 3 - the student's rising cut, the master's low block on his right
    M.slash(SH, c["c3"], "rising_L", follow=3, recover=6, strength=0.7, recover_to="deflect_high")
    M.deflect(SA, c["c3"], "low", recover=4, recover_to="diag_down_R_windup")
    M.clash(SH, SA, c["c3"], strength=0.70, sparks=dict(color="white"))
    # 4 - the master's kesa from high, the student's high block
    _local_strike(M, PZ, SA, c["c4"], "diag_down_R", strength=0.8, strike_pose="a1b_kesa_high")
    M.swing(SA, c["c4"], c["c4"] + 4, "a1b_kesa_high", "diag_down_R_follow", ease="out_cubic", include_start=False)
    M.pose(SA, c["c4"] + 4, "diag_down_R_follow", weight=1.04, ctrl=False, feet=False)
    M.pose(SA, c["c4"] + 7, "diag_down_R_follow")
    M.deflect(SH, c["c4"], "high", recover=5, recover_to="thrust_windup")
    M.clash(SA, SH, c["c4"], strength=0.80, sparks=dict(count=90))
    # 5 - the student's thrust, swept aside to the master's left
    M.slash(SH, c["c5"], "thrust", windup=5, hold_frames=1, recover=7, strength=0.75)
    M.deflect(SA, c["c5"], "mid_L", recover=4, recover_to="overhead_windup")
    M.clash(SH, SA, c["c5"], strength=0.65, sparks=dict(color="white", light_energy=12.0))   # 2.4 m from the OTS lens
    # 6 - the master's overhead (one-handed), the student's roof block -> the blades slide to the guards: the lock
    _local_strike(M, PZ, SA, c["c6"], "overhead", strength=0.85, strike_pose="a1b_overhead_contact")
    M.deflect(SH, c["c6"], "overhead_block", recover=1, recover_to="blade_lock")
    f_lock = c["c6"] + 3                                                    # 1276
    M.blade_lock(SH, SA, f_lock, c["shove"], point=(0.02, 1.77, 1.62), pusher="a")
    f_mid = M.clock(f_lock)(M.clock(f_lock).span(c["shove"]) * 0.5)       # moves.blade_lock keys its poses
    for rig in (SH, SA):                                                    # WITH the controller at mid / f1:
        U.delete_keys(PZ._ctrl_obj(rig), (f_mid, f_mid))                    # the blades left the lock point
        U.delete_keys(PZ._ctrl_obj(rig), (c["shove"], c["shove"]))
    # the clash placement offsets the EXISTING controller curves (+-3 story frames): key what follows first
    M.clash(SA, SH, c["c6"], strength=0.85)
    marks.update(c)
    marks["lock"] = f_lock
    # ---- the shove happens ON the cut (1320 -> 1321): hold everything CONSTANT at 1320, cheat both roots
    f_sh = c["shove"]
    for rig in (SH, SA):
        M.hold(rig, f_sh)
        U.set_key_interp_at(rig, f_sh, 'CONSTANT')
        U.set_key_interp_at(PZ._ctrl_obj(rig), f_sh, 'CONSTANT')
    M._feet_air(SH, f_sh + 0.5)
    M._feet_air(SA, f_sh + 0.5)
    M.pose(SH, f_sh + 1, "skid", feet=False)
    M.pose(SA, f_sh + 1, "skid", feet=False)
    M.skid(SH, f_sh + 1, 1340, (0.0, 1.23), (0.0, -0.55), recover=4)
    M.skid(SA, f_sh + 1, 1336, (0.0, 2.30), (0.0, 2.95), recover=8)
    for rig in (SH, SA):                          # moves.skid plants its first skid pose: the feet must slide
        _local_skid_feet(M, PZ, rig, f_sh + 1)
    M.emit(f_sh, "whoosh", who="saint", weapon="body", strength=0.7)


def _local_retoss_haori(CH, f, v0, spin):
    """props.fly_haori (via moves.shed_haori) starts its toss from SAINT_haori_thrown.matrix_world, which is stale
    when the scene frame is not `f` (measured: a 2.0 m jump on the frame after the shed).  Re-toss from
    characters.detach_matrix (the coat exactly where it was worn at f) and re-key the spread / crumple shapes."""
    import props as PR
    ob = bpy.data.objects["SAINT_haori_thrown"]
    for path in ("location", "rotation_euler"):
        U.delete_keys(ob, (f + 0.5, f + 600), path)
    Mw = CH.detach_matrix(ob, f)
    res = PR.toss(ob, f, p0=tuple(Mw.translation), v0=v0, spin=spin, rot0=Mw, ground_z=0.0, key_start=False,
                  restitution=0.05, friction=0.8, settle=True, settle_frames=6)
    key = ob.data.shape_keys
    if key is not None:
        for nm in ("spread", "crumple"):
            U.delete_keys(key, (f - 0.5, f + 600), f'key_blocks["{nm}"].value')
        land = res.get("contact") or (f + 14)
        # never fully 'spread' (a flat sheet reads as a board): half open, with a crumple flutter in the air
        keys = [("spread", f, 0.0), ("spread", f + 3, 0.30), ("spread", f + 8, 0.50), ("spread", land, 0.45),
                ("crumple", f, 0.0), ("crumple", land + 6, 0.85), ("spread", land + 6, 0.25)]
        for i, fr in enumerate(range(f + 2, int(land) - 1, 3)):
            keys.append(("crumple", fr, (0.18, 0.40, 0.26, 0.45)[i % 4]))
        for nm, fr, v in keys:
            PR.key_shape(ob, nm, fr, v)
    return res


def _local_sheath_follow(CH, f_grab, f_rel, v0, spin_rev):
    """The black spear sheath rides the blade from the grab (f_grab, the in_hand swap) to its release (f_rel),
    then spins off (props.toss) - moves.spear_draw leaves it hanging where the slung spear was while the spear
    is pulled up through it (breakdown §5 _local_follow_socket).  Replaces spear_draw's sheath toss and its
    sheath_drop event (re-emitted on this toss's landing)."""
    import props as PR
    sh = bpy.data.objects["SAINT_spear_sheath_world"]
    slung = bpy.data.objects["SAINT_spear_slung"]
    hand = bpy.data.objects["SAINT_spear_hand"]
    M_off = U.world_matrix_of(slung, f_grab).inverted() @ CH.detach_matrix(sh, f_grab)
    for path in ("location", "rotation_euler"):
        U.delete_keys(sh, (f_grab - 0.5, f_grab + 600), path)
    for f in range(int(f_grab), int(f_rel) + 1):
        CH.key_ctrl_matrix(sh, f, U.world_matrix_of(hand, f) @ M_off, 'LINEAR')
    Mw = U.world_matrix_of(hand, f_rel) @ M_off
    ax = (Mw.to_3x3() @ Vector((1.0, 0.0, 0.0))).normalized()
    res = PR.toss(sh, int(f_rel), p0=tuple(Mw.translation), v0=v0, spin=tuple(ax * spin_rev * 2.0 * math.pi),
                  rot0=Mw, ground_z=0.0, key_start=False, f_end=SPAN[1] + 4)
    EV._EVENTS[:] = [e for e in EV._EVENTS if not (e["type"] == "sheath_drop" and e.get("_lane") == LANE)]
    land = res.get("contact") or (f_rel + 20)
    EV.emit(f_rel + 6, "sheath_drop", pos=tuple(Mw.translation), tags=["sheath_drop"], land=int(land))
    return res


def _local_smooth_spear_reach(M, PZ, CH, rig, f_sp):
    """moves.spear_draw lets go of the saya with a CONSTANT switch at f-6 (the left hand jumped 0.45 m in 1 f) and
    blends the right arm to the slung grip in 3 f (f-9..f-6) along a straight line through the chest.  Here: the
    left hand fades off the saya over f-10..f-6; the right arm blends to IK over f-11..f-6 while its FK arm rises
    beside the head (f-8), so the hand goes UP past the shoulder and back to the shaft, not through the body."""
    f_g = f_sp - 6
    CH.set_left_hand(rig, f_sp - 10, "free", blend=4)
    for bone, cn in (("forearm.R", "IK_sword"), ("hand.R", "COPYROT_sword")):
        U.delete_keys(rig, (f_sp - 9, f_sp - 9), f'pose.bones["{bone}"].constraints["{cn}"]')
    f0 = f_sp - 11
    ctrl = PZ._ctrl_obj(rig)
    Rw = U.world_matrix_of(rig, f0)
    S_loc = M.ctrl_matrix(rig, {"slung": 1.45}, f_sp - 9)                  # the grip on the slung shaft
    U.frame_set(f0)
    hand0 = rig.matrix_world @ rig.pose.bones["hand.R"].head               # where the FK hand hangs at f0
    fwd = Vector((math.sin(math.radians(M.facing_of(rig, f0))), -math.cos(math.radians(M.facing_of(rig, f0))), 0.0))
    right = Vector((-fwd.y, fwd.x, 0.0)) * -1.0                            # his right
    base = Vector((Rw.translation.x, Rw.translation.y, 0.0))
    # world path of the hand: hip -> out beside the shoulder -> above the right shoulder -> down to the shaft
    path = [(f0, hand0),
            (f_sp - 9, base + right * 0.40 + fwd * 0.08 + Vector((0.0, 0.0, 1.50))),
            (f_sp - 8, base + right * 0.26 - fwd * 0.04 + Vector((0.0, 0.0, 1.88)))]
    Rinv = Rw.inverted()
    for f, pw in path:
        Ml = S_loc.copy()
        Ml.translation = Rinv @ pw
        CH.key_ctrl_matrix(ctrl, f, Ml, 'BEZIER')
    CH.set_arm_mode(rig, f0, "ik", blend=3)
    return f_g


def _local_skid_feet(M, PZ, rig, f0):
    """moves.skid registers PLANTED feet with its first skid pose (T(1)) after marking them airborne at T(0.5): the
    bake then plants them for one frame and steps them 2 m in an arc to the end pose.  Drop that planted
    registration so the feet slide with the rig until the skid's end pose."""
    t1 = M.clock(f0)(1)
    PZ.clear_feet(rig, (t1 - 0.01, t1 + 0.01))
    M._feet_air(rig, t1)


def _hat_brim_front(CH, f):
    """World point on the straw hat's front brim (6 cm inside the rim, 3 cm above the rim plane) at frame f."""
    hat = bpy.data.objects["SAINT_hat"]
    Mw = U.world_matrix_of(hat, f)
    r = CH.DIMS["SAINT"]["hat_diameter"] * 0.5 - 0.06
    return Mw @ Vector((0.0, -r, 0.03))


def _s13(M, PZ, CH, SH, SA, marks):
    """S13 1345-1488: the master's first two-handed blow -> PERFECT DEFLECT (1367, slow motion to 1408) -> the
    counter splits the straw hat (1420) -> the master hops back and skids 4.8 m -> the reveal."""
    f_pd = config.MUSIC_CUES["perfect_deflect"]                             # 1367 (beat 47)
    # ---- the master: left hand leaves the saya and closes on the tsuka (FIRST two-handed grip), jodan, lunge
    CH.set_two_hand(SA, 1346, True, blend=3)
    M.hold(SA, 1349)
    M.stance(SA, 1355, "jodan", hands="keep")
    M.root(SA, 1349, (0.0, 2.95), 0.0, interp='BEZIER')
    M.root(SA, 1355, (0.0, 2.80), 0.0, interp='LINEAR')
    M.root_path(SA, 1356, f_pd, (0.0, 2.78), (0.0, 1.25), ease="inout_quad")
    _local_strike(M, PZ, SA, f_pd, "overhead", strength=1.0, strike_pose="a1b_overhead_contact")
    # ---- the student steps in and meets it at the perfect instant (flash ring, white sparks)
    M.step(SH, 1350, 1360, (0.0, -0.50))
    M.root_path(SH, 1362, f_pd, (0.0, -0.50), (0.0, -0.35), ease="out_quad")
    M.stance(SH, 1362, "chudan", hands="keep")
    # ---- slow motion 1367-1408: the master's blade is thrown up and back, his posture breaks (keyed BEFORE the
    #      clash placement, which offsets the existing curves over +-3 story frames = +-15 film frames here)
    M.hold(SA, f_pd)
    M.pose(SA, M.story_to_film(f_pd, 1.0), "a1b_posture_broken", weight=0.45, hands="keep", feet=False)
    M.pose(SA, 1388, "a1b_posture_broken", weight=0.9, hands="keep", feet=False)
    M.pose(SA, 1408, "a1b_posture_broken", hands="keep")
    M.perfect_deflect(SH, f_pd, attacker=SA, point=None, strength=1.0, stagger_attacker=False,
                      flash=dict(radius=0.6, color="white", duration=10, strength=2.5, star=0.3, light=True,
                                 light_energy=150.0, seed=_seed("S13a:2")),
                      sparks=dict(color="white", count=140, scale=1.6, life=14), tags=["perfect_deflect"])
    marks["perfect_deflect"] = f_pd
    M.root(SA, f_pd, (0.0, 1.25), 0.0, interp='BEZIER')
    M.root(SA, 1408, (0.0, 1.35), 0.0, interp='BEZIER')
    M.root(SA, 1416, (0.0, 1.38), 0.0, interp='BEZIER')
    M.root(SA, 1420, (0.0, 1.40), 0.0, interp='BEZIER')
    M.pose(SA, 1416, "a1b_posture_broken", hands="keep", feet=False)
    M.pose(SA, 1420, "a1b_posture_broken", hands="keep", feet=False)
    M.overlay(SA, 1420, {"neck": (-6.0, -4.0, 0.0), "head": (-6.0, -6.0, 0.0)})   # chin up, recoiling
    M.root(SH, 1408, (0.0, -0.32), 180.0, interp='BEZIER')
    # ---- the counter: a steep rising cut (kiriage) through the front of the straw hat (1420)
    f_hat = config.MUSIC_CUES["hat_cut"]                                    # 1420
    M.hold(SH, 1409)
    M.root(SH, 1409, (0.0, -0.32), 180.0, interp='BEZIER')
    M.root(SH, 1413, (0.0, -0.25), 180.0, interp='LINEAR')
    M.root_path(SH, 1414, f_hat + 1, (0.0, -0.25), (0.0, 0.18), ease="inout_quad")
    M.pose(SH, 1413, "rising_R_windup")
    M.pose(SH, 1416, "rising_R_windup", weight=1.04, feet=False)
    M.swing(SH, 1416, f_hat, PZ.current_ctrl_matrix(SH, 1416), "a1b_kiriage", ease="in_quad")
    M.pose(SH, f_hat, "a1b_kiriage", ctrl=False, lag={"head": 1})
    M.swing(SH, f_hat, f_hat + 4, "a1b_kiriage", "rising_R_follow", ease="out_cubic", include_start=False)
    M.pose(SH, f_hat + 4, "rising_R_follow", weight=1.05, ctrl=False, feet=False)
    M.pose(SH, f_hat + 7, "rising_R_follow")
    M.pose(SH, 1433, "chudan", hands="keep")
    tip = _hat_brim_front(CH, f_hat)
    _local_place_tip(M, PZ, CH, SH, f_hat, tip + Vector((0.0, 0.0, 0.06)))
    M.emit(f_hat - 1, "whoosh", who="shinobi", weapon="katana", strength=0.95, target=(SH, "hand.R"))
    # the hat splits along its sagittal plane; the halves separate in +-Y/Z for the profile camera
    import props as PR
    CH.set_hat(f_hat, "cut")
    for half, v0, spin in (("A", (0.9, -1.6, 2.4), (4.0, 1.0, 6.0)), ("B", (-0.9, 1.4, 2.0), (-3.0, 2.0, -5.0))):
        nm = f"SAINT_hat_half_{half}"
        CH.snap_free(nm, f_hat)
        Mw = CH.detach_matrix(nm, f_hat)
        PR.toss(nm, f_hat, p0=tuple(Mw.translation), v0=v0, spin=spin, rot0=Mw, ground_z=0.0, settle=True,
                key_start=False)
    marks["hat"] = f_hat
    # ---- the master hops back (z 0.25) and skids 2.5 m through the grass, blade low in both hands
    M.hold(SA, 1422)
    M._feet_air(SA, 1422.5)
    M.root_path(SA, 1422, 1434, (0.0, 1.45), (0.0, 3.70), ease="out_quad",
                z=lambda u: 1.0 * u * (1.0 - u) * 1.15)
    M.pose(SA, 1428, "jump_air", weight=0.45, hands="keep", feet=False)
    M.pose(SA, 1434, "skid", weight=0.9, hands="keep", feet=False)
    M.skid(SA, 1434, 1446, (0.0, 3.70), (0.0, 6.20), recover=6, recover_to="skid")
    _local_skid_feet(M, PZ, SA, 1434)
    M.root_path(SA, 1446, 1450, (0.0, 6.20), (0.0, 6.25), ease="out_quad")
    M.pose(SA, 1470, "gedan", hands="keep")
    M.stance(SA, 1488, "gedan", hands="keep")
    M.emit(1422, "jump", who="saint")
    M.emit(1434, "land", who="saint", strength=0.7)
    # ---- the student recovers and backs off in guard (two steps), then two more (off-screen) to (0, -1.5)
    M.walk(SH, 1434, 1447, (0.0, 0.18), (0.0, -0.90), facing=180.0, upper="chudan")
    M.stance(SH, 1450, "chudan", hands="keep")
    M.walk(SH, 1470, 1488, (0.0, -0.90), (0.0, -1.50), facing=180.0, upper="chudan")
    _local_hat_tilts(CH)


def _local_hat_tilts(CH):
    """The straw brim clears the raised forearms / blade: front brim up during the overhead block (S11d-e), the lock
    (S12g) and the jodan rise (S13a) - keyed last so these keys are the final say on their frames."""
    for f, pitch in ((1122, 0.0), (1127, 16.0), (1142, 16.0), (1150, 0.0),
                     (1234, 0.0), (1238, 12.0), (1244, 12.0), (1248, 0.0),
                     (1270, 0.0), (1274, 14.0), (1320, 14.0), (1321, 4.0), (1336, 0.0),
                     (1349, 0.0), (1355, 14.0), (1362, 20.0), (1367, 20.0), (1377, 18.0)):
        CH.set_hat_tilt(f, pitch, 0.0)


def _s14(M, PZ, CH, SH, SA, marks):
    """S14 1489-1632: the katana goes home (1510), the haori is shed (1532) - white tasuki, the spear is drawn over
    the shoulder as the sun disappears (1586), the sheath spins away, the twirl, the spear raised for the butt slam
    (act2 lands it on 1633)."""
    # ---- sheathe: the left hand leaves the tsuka (1496) for the saya, the blade goes home at 1510
    CH.set_two_hand(SA, 1496, False, blend=3)
    _local_sheathe(M, PZ, CH, SA, 1510, dur=14, end="relaxed_saya", end_after=8, release=True)
    # ---- the haori: grip the collar, one sweep, flung away behind him (lands ~ (-0.4, 8.3); act2 re-drapes it at its
    #      own S15 spot and burns it)
    f_shed = 1532
    M.shed_haori(SA, f_shed, throw=(-0.50, 2.40, 2.60))
    _local_retoss_haori(CH, f_shed, v0=(-0.50, 2.40, 2.60), spin=(0.8, 2.0, 0.5))
    marks["haori"] = f_shed
    M.stance(SA, 1552, "relaxed", hands="keep")
    M.step(SA, 1560, 1568, (0.0, HOUT["saint"]["pos"][1]))
    # ---- the spear drawn over the right shoulder on beat 61 (1586) - the sun's last sliver goes on that frame
    f_sp = _beat(61)                                                        # 1586
    M.spear_draw(SA, f_sp, twirl=False)
    _local_smooth_spear_reach(M, PZ, CH, SA, f_sp)
    _local_sheath_follow(CH, f_sp - 5, f_sp, v0=(-0.5, -3.0, 3.2), spin_rev=5.0)
    marks["spear"] = f_sp
    # ---- the twirl, then upright in front of the right shoulder and the downward drive (butt 0.45 m at 1632)
    M.spear_spin(SA, 1598, 1616, turns=1.5)
    CH.set_spear_grip(1624, 1.10, 0.70)
    M.pose(SA, 1625, "a1b_spear_raise", hands="pose", hand_blend=2)
    M.emit(1622, "step", who="saint", strength=0.6)
    CH.set_spear_grip(SPAN[1], 1.25, 0.85)
    M.pose(SA, SPAN[1], "a1b_spear_drive", hands="keep")
    M.emit(1628, "whoosh", who="saint", weapon="spear", strength=0.8, target=(SA, "hand.R"))
    # ---- the student: holds at (0, -1.5) in chudan, breathing; a regrip on beat 60 (1570)
    M.stance(SH, 1500, "chudan", hands="keep", breathe=48)
    M.stance(SH, 1560, "chudan", hands="keep")
    M.overlay(SH, 1565, {"chest": (-2.0, 0.0, 0.0), "shoulder.L": (0.0, 0.0, -2.0), "shoulder.R": (0.0, 0.0, 2.0)})
    M.shift_ctrl(SH, 1565, (0.0, 0.0, -0.03))
    M.stance(SH, _beat(60), "chudan", hands="keep")
    M.stance(SH, SPAN[1], "chudan", hands="keep")
    # ---- HANDOFF[1632]: both roots CONSTANT on the lane's last frame
    M.root(SH, SPAN[1], HOUT["shinobi"]["pos"], float(HOUT["shinobi"]["facing"]))
    M.root(SA, SPAN[1], HOUT["saint"]["pos"], float(HOUT["saint"]["facing"]))
    for rig in (SH, SA):
        U.set_key_interp_at(rig, SPAN[1], 'CONSTANT', "location")
        U.set_key_interp_at(rig, SPAN[1], 'CONSTANT', "rotation_euler")


def choreograph(SH, SA):
    """Key both rigs through poses / moves / characters / props. Returns marks {name: frame}."""
    import characters as CH
    import moves as M
    import poses as PZ
    _local_register_poses(PZ)
    marks = {}
    _entering_state(M, CH, SH, SA)
    _s10(M, PZ, CH, SH, SA)
    _s11(M, PZ, CH, SH, SA, marks)
    _s12(M, PZ, CH, SH, SA, marks)
    _s13(M, PZ, CH, SH, SA, marks)
    _s14(M, PZ, CH, SH, SA, marks)
    return marks


# =============================================================================================================
# environment: per-cut sun cheats + grass clearance, wind, the S11 shear, the S14 sunset (breakdown §3, D5)
# =============================================================================================================
# cut -> (sun (az, el) or None = keep, clearance (near, far)), keyed on the cut's first frame
CLEAR_DEFAULT = config.GRASS_CAMERA_CLEAR                                   # (1.5, 4.0)
ENV_CUTS = [
    ("S10a", (257.0, 1.35), (0.9, 1.4)), ("S10b", (262.0, 1.25), (0.5, 1.0)),
    ("S10c", (262.0, 1.25), (0.5, 1.0)), ("S11a", (262.0, 1.25), (0.8, 1.6)),
    ("S11b", (262.0, 1.25), (0.45, 0.95)), ("S11c", (262.0, 1.25), CLEAR_DEFAULT),
    ("S11d", (262.0, 1.25), (0.4, 0.9)), ("S11e", (271.0, 1.25), (0.5, 1.0)),
    ("S12a", (268.0, 1.1), (0.5, 1.0)), ("S12b", (268.0, 1.1), (0.5, 1.0)),
    ("S12c", (268.0, 1.1), (0.6, 1.2)), ("S12d", (268.0, 1.1), (0.5, 1.0)),
    ("S12e", (268.0, 1.1), (0.5, 1.0)), ("S12f", (268.0, 1.1), (0.6, 1.2)),
    ("S12g", (270.0, 0.78), CLEAR_DEFAULT), ("S12h", (262.0, 1.1), (0.5, 1.0)),
    ("S13a", (264.0, 1.1), (0.6, 1.2)), ("S13b", (264.0, 1.1), (0.5, 1.0)),
    ("S13c", (273.4, 1.68), CLEAR_DEFAULT), ("S13d", (262.0, 1.0), (0.5, 1.0)),
    ("S13e", (232.0, 7.0), CLEAR_DEFAULT), ("S14a", (268.0, 0.9), (0.6, 1.0)),
    ("S14b", (200.0, 3.0), (1.2, 2.2)), ("S14c", (268.0, 0.6), (0.5, 1.0)),
    ("S14d", None, (0.5, 1.0)), ("S14e", (276.0, -1.60), (0.8, 1.6)),
]
SUN_DISK = 2.2
# S14d sunset: environment's far ranges open a gap under the sun (ridge_elevation ~0.05 deg toward it), so the
# 2.2-deg disc is gone when its centre is ~1.1 deg below that skyline: cap shrinking 1575 -> gone on the draw
SUNSET = (-0.15, -1.08)
WIND_KEYS = [(937, 1.0), (976, 1.0), (992, 0.35), (1060, 0.35), (1080, 0.12), (1101, 0.12), (1104, 1.3),
             (1130, 1.0), (1489, 1.0), (1516, 1.4), (1540, 1.0), (1553, 1.2), (1605, 1.2)]
SHEAR = dict(origin=E0, radius=14.0, arc_deg=220.0, facing_deg=176.5, fluff=3600, wind=1.0)


def environment_timeline(marks):
    import environment as ENV
    for cut, sun, clr in ENV_CUTS:
        f0 = CUT[cut][0]
        if sun is not None:
            ENV.set_sun(f0, sun[0], sun[1], SUN_DISK)
        ENV.set_camera_clearance(f0, clr[0], clr[1])
    # the sunset (D5): the disc cap sinks behind the far ridge and is gone on the spear draw (1586)
    f_sp = marks.get("spear", _beat(61))
    el0, el1 = SUNSET
    ENV.set_sun(1575, 276.0, el0, SUN_DISK, interp='LINEAR')
    ENV.set_sun(f_sp - 1, 276.0, el0 + (el1 - el0) * (f_sp - 1 - 1575) / float(f_sp - 1575), SUN_DISK,
                interp='LINEAR')                                            # replaces the default 1585 key
    ENV.set_sun(f_sp, 276.0, el1, SUN_DISK, interp='LINEAR')
    ENV.set_sun(1597, 276.0, el1 - 0.55, SUN_DISK, interp='CONSTANT')
    ENV.set_param(f_sp, "disk_vis", 1.0, 'LINEAR')
    ENV.set_param(f_sp + 4, "disk_vis", 0.0, 'CONSTANT')
    for f, w in WIND_KEYS:
        ENV.set_wind(f, w)
    # THE DRAW-CUT: the grass tops sheared in a 220-deg arc racing out 14 m (19.8 m/s) - reaches H at ~1106
    f_cut = marks.get("cut", _beat(30))
    ENV.grass_effect("shear", dict(SHEAR), f_cut, 1118)


# =============================================================================================================
# effects (sparks + the flash ring of registered clashes come from moves' clash resolution)
# =============================================================================================================
TRAILS = [  # (owner, f0, f1) - the fast part of each swing up to its contact
    ("SAINT_katana", 1098, 1104), ("SHINOBI_katana", 1127, 1132),
    ("SHINOBI_katana", 1190, 1195), ("SAINT_katana", 1206, 1210), ("SHINOBI_katana", 1221, 1226),
    ("SAINT_katana", 1237, 1241), ("SHINOBI_katana", 1253, 1257), ("SAINT_katana", 1269, 1273),
    ("SAINT_katana", 1362, 1367), ("SHINOBI_katana", 1364, 1368),
    ("SHINOBI_katana", 1415, 1422), ("SAINT_spear", 1583, 1590), ("SAINT_spear", 1600, 1616),
]


def effects(SH, SA, marks):
    import vfx
    for i, (w, a, b) in enumerate(TRAILS):
        vfx.blade_trail(f"{w}_tip", f"{w}_base", a, b, name=f"S1x_trail_{i}_{a}")
    # S11c: his take-off tears the grass; S11d: the heavy block drives stubble + fluff up, his feet down
    vfx.grass_burst(1102, (H_POS[0], H_POS[1], 0.45), direction=(0.0, 0.3, 1.0), count=90, speed=3.0, fluff=0.2,
                    seed=_seed("S11c:0"))
    f_b = marks.get("block", _beat(32))
    pos = _clash_pos(f_b)
    if pos is not None:
        vfx.sparks(f_b, pos, direction=(0.0, 0.4, 0.9), count=50, color="gold", scale=1.2, light=False,
                   seed=_seed("S11d:1"))
    vfx.grass_burst(f_b, (0.0, 2.0, 0.45), direction=(0.0, 0.0, 1.0), count=160, speed=4.5, spread=80.0,
                    fluff=0.3, seed=_seed("S11d:2"))
    vfx.dust_burst(f_b + 1, (0.0, 2.6, 0.0), radius=0.6, density=2.0, life=30, seed=_seed("S11d:3"))
    # S11e: landing low after the heave
    vfx.dust_burst(1152, (0.0, 0.30, 0.0), radius=0.5, density=2.0, life=30, seed=_seed("S11e:0"))
    vfx.grass_burst(1152, (0.0, 0.30, 0.3), direction=(0.0, -1.0, 0.6), count=50, speed=2.5, fluff=0.1,
                    seed=_seed("S11e:1"))
    # S12e scrape of the turned thrust; S12g grind sparks in the lock (no light)
    p = _clash_pos(marks.get("c5", F12["c5"]))
    if p is not None:
        vfx.sparks(marks.get("c5", F12["c5"]) + 1, p, direction=(0.6, 0.4, 0.5), count=25, scale=0.6, color="white",
                   light=False, seed=_seed("S12e:1"))
    for i, f in enumerate((1288, 1304)):
        vfx.sparks(f, ("SAINT_katana_base"), count=20, scale=0.6, color="gold", light=False,
                   seed=_seed(f"S12g:{i}"))
    # S12h: the skid apart opens two furrows
    vfx.dust_burst(1322, (0.0, 1.20, 0.0), radius=0.5, density=2.0, life=30, seed=_seed("S12h:0"))
    vfx.dust_burst(1322, (0.0, 2.32, 0.0), radius=0.45, density=2.0, life=30, seed=_seed("S12h:1"))
    vfx.grass_burst(1326, (0.0, 0.70, 0.35), direction=(0.0, -1.0, 0.5), count=40, speed=2.0, fluff=0.1,
                    seed=_seed("S12h:2"))
    # S13a/b: the elder's steel answers in gold; a second slow shower hangs in the slow motion
    f_pd = marks.get("perfect_deflect", config.MUSIC_CUES["perfect_deflect"])
    p = _clash_pos(f_pd)
    if p is not None:
        vfx.sparks(f_pd, p, direction=(-0.5, 0.2, 0.8), count=60, color="gold", scale=1.2, light=False,
                   seed=_seed("S13a:1"))
        vfx.sparks(1372, p, count=30, speed=1.5, life=20, color="gold", scale=0.8, light=False,
                   seed=_seed("S13b:0"))
    # S13c: straw splinters from the split brim
    f_hat = marks.get("hat", config.MUSIC_CUES["hat_cut"])
    vfx.grass_burst(f_hat, tuple(_hat_pos_at(f_hat - 1)), direction=(0.0, 0.3, 1.0), count=40, speed=2.0,
                    spread=60.0, fluff=0.0, scale=0.5, seed=_seed("S13c:0"))
    # S13d: the hop back lands and skids
    vfx.dust_burst(1434, (0.0, 3.70, 0.0), radius=0.6, density=2.0, life=30, seed=_seed("S13d:0"))
    vfx.grass_burst(1436, (0.0, 4.0, 0.3), direction=(0.0, 1.0, 0.4), count=70, speed=3.0, fluff=0.1,
                    seed=_seed("S13d:1"))
    vfx.grass_burst(1444, (0.0, 5.8, 0.3), direction=(0.0, 1.0, 0.3), count=40, speed=2.0, fluff=0.1,
                    seed=_seed("S13d:2"))
    # S14d: the first embers drift across the reddening sky
    vfx.embers(1588, SPAN[1] + 8, center=(0.0, 6.0, 0.0), radius=7.0, rate=5.0, height=(0.3, 2.2), rise=0.6,
               seed=_seed("S14d:emb"))
    # exposure lifts (DIRECTION §5): the overhead block 0.20 for 1 f, the perfect deflect 0.35 for 2 f
    import render_setup as RS
    RS.key_white_flash(f_b, 0.20, duration=1)
    RS.key_dispersion(f_b, 0.04)
    RS.key_white_flash(f_pd, 0.35, duration=2)
    RS.key_dispersion(f_pd, 0.05)


def _clash_pos(f):
    """Current (pre-resolution) contact estimate of the registered clash at frame f: midpoint of the keyed blades'
    closest points (the resolver moves it by <= a few cm)."""
    import moves as M
    for reg in M.clashes():
        if abs(reg["frame"] - f) < 0.5:
            if reg.get("point") is not None:
                return tuple(reg["point"])
    return None


def _hat_pos_at(f):
    hat = bpy.data.objects["SAINT_hat"]
    return U.world_matrix_of(hat, f).translation


# =============================================================================================================
# events the macros do not emit themselves (audio + music sync, DIRECTION §8, breakdown §2)
# =============================================================================================================
def story_events(SH, SA, marks):
    EV.emit(_beat(20), "heartbeat", bpm=60, duration=marks.get("cut", _beat(30)) - _beat(20), who="shinobi")
    EV.emit(962, "wind_gust", strength=0.7)
    f_cut = marks.get("cut", _beat(30))
    EV.emit(f_cut, "grass_shear", pos=(0.0, 2.6, 0.9), tags=["draw_cut"])
    EV.emit(f_cut + 3, "wind_gust", strength=1.2)
    EV.emit(1141, "whoosh", who="saint", weapon="katana", strength=0.6)
    EV.emit(1180, "dash", who="shinobi", strength=0.6)
    EV.emit(_beat(46), "whoosh", who="saint", weapon="katana", strength=0.8)     # 1351: the rise to jodan
    EV.emit(1356, "step", who="saint", strength=0.8)
    f_pd = marks.get("perfect_deflect", config.MUSIC_CUES["perfect_deflect"])
    EV.emit(f_pd, "music_cue", cue="perfect_deflect")
    s0, s1 = config.slowmo_window(f_pd)                                     # (1367, 1408)
    EV.emit(f_pd, "slowmo", duration=s1 - s0 + 1)
    f_hat = marks.get("hat", config.MUSIC_CUES["hat_cut"])
    EV.emit(f_hat, "hat_cut", pos=tuple(_hat_pos_at(f_hat)), tags=["hat_cut"])
    EV.emit(f_hat, "music_cue", cue="hat_cut")
    EV.emit(1520, "wind_gust", strength=0.8)
    EV.emit(1562, "wind_gust", strength=0.6)


# =============================================================================================================
# cameras: 26 sub-cuts, all on the +X side of the action line (keys from the breakdown's geometry proofs)
# =============================================================================================================
def cameras(SH, SA):
    head_sa, head_sh = (SA, "head"), (SH, "head")
    C.shot("S10a", *CUT["S10a"], [(937, (9.13, 1.01, 1.20), (0.15, 0.40, 1.30), 50.0),
                                  (950, (9.23, 1.82, 1.20), (0.34, 0.42, 1.30), 50.0),
                                  (962, (9.26, 3.03, 1.20), (0.62, 0.48, 1.30), 50.0),
                                  (974, (9.12, 4.23, 1.20), (0.89, 0.59, 1.30), 50.0),
                                  (990, (9.04, 4.63, 1.20), (0.99, 0.62, 1.30), 50.0)],
           dof=dict(focus=9.0, fstop=2.8), subjects=["shinobi", "saint"], framing="wide")
    C.shot("S10b", *CUT["S10b"], [(991, (0.30, 3.80, 1.70), (0.58, -1.18, 1.35), 50.0),
                                  (1012, (0.30, 3.80, 1.70), (0.58, -1.18, 1.35), 50.0)],
           dof=dict(focus=(1.6, -1.4, 0.95), fstop=4.0), subjects=["shinobi", "saint"], framing="ots")
    C.shot("S10c", *CUT["S10c"], [(1013, (2.56, 2.17, 1.80), (-2.41, 2.56, 1.39), 85.0),
                                  (1032, (2.32, 2.21, 1.79), (-2.65, 2.59, 1.36), 85.0)],
           dof=dict(focus=head_sa, fstop=2.0), subjects=["saint"], framing="mcu")
    C.shot("S11a", *CUT["S11a"], [(1033, (3.85, 1.95, 1.30), (-1.15, 2.10, 1.25), 45.0),
                                  (1072, (3.85, 1.95, 1.30), (-1.15, 2.07, 1.17), 45.0)],
           dof=dict(focus=3.75, fstop=2.8), subjects=["saint"], framing="close")
    C.shot("S11b", *CUT["S11b"], [(1073, (1.55, -2.45, 1.10), (-0.55, 1.20, 1.02), 32.0),
                                  (1096, (1.49, -2.33, 1.10), (-0.62, 1.25, 1.00), 32.0)],
           dof=dict(focus=1.8, fstop=2.8, distance_keys=[(1073, 1.8), (1088, 1.8), (1095, 5.0)]),
           subjects=["shinobi", "saint"], framing="ots")
    C.shot("S11c", *CUT["S11c"], [(1097, (8.60, 0.20, 3.40), (0.00, 0.90, 0.90), 24.0),
                                  (1106, (8.55, 0.25, 3.38), (0.00, 0.90, 1.25), 24.0),
                                  (1118, (8.40, 0.35, 3.30), (0.00, 0.90, 2.10), 24.0)],
           subjects=["shinobi", "saint"], framing="wide")
    C.shot("S11d", *CUT["S11d"], [(1119, (3.10, 0.70, 0.70), (-1.17, 1.73, 3.09), 18.0),
                                  (1134, (3.10, 0.70, 0.70), (-1.20, 2.70, 2.29), 18.0)],
           shake=[(1132, 0.9, 8)], subjects=["shinobi", "saint"], framing="close")
    C.shot("S11e", *CUT["S11e"], [(1135, (6.80, 0.20, 2.30), (0.00, 1.50, 1.00), 26.0),
                                  (1176, (6.00, 1.00, 1.60), (0.00, 1.35, 1.20), 30.0)],
           shake=[(1135, 0.5, 6)], subjects=["shinobi", "saint"], framing="wide")
    C.shot("S12a", *CUT["S12a"], [(1177, (0.80, -0.98, 1.70), (-0.81, 3.75, 1.60), 40.0),
                                  (1195, (0.80, -0.32, 1.70), (-1.07, 4.31, 1.52), 40.0),
                                  (1197, (0.80, -0.32, 1.70), (-1.07, 4.31, 1.52), 40.0)],
           dof=dict(focus=head_sa, fstop=2.8), shake=[(1195, 0.5, 3)], subjects=["shinobi", "saint"],
           framing="ots")
    C.shot("S12b", *CUT["S12b"], [(1198, (0.85, 3.70, 1.80), (-1.07, -0.88, 1.22), 40.0),
                                  (1212, (0.85, 3.65, 1.80), (-1.06, -0.93, 1.21), 40.0)],
           dof=dict(focus=head_sh, fstop=2.8), shake=[(1210, 0.5, 3)], subjects=["shinobi", "saint"],
           framing="ots")
    C.shot("S12c", *CUT["S12c"], [(1213, (0.92, -0.18, 1.30), (-1.25, 4.33, 1.35), 35.0),
                                  (1228, (0.92, -0.05, 1.30), (-1.26, 4.45, 1.36), 35.0)],
           dof=dict(focus=2.3, fstop=2.8), shake=[(1226, 0.45, 3)], subjects=["shinobi", "saint"],
           framing="ots")
    C.shot("S12d", *CUT["S12d"], [(1229, (2.30, 1.35, 1.66), (0.02, 1.52, 1.70), 55.0),
                                  (1243, (2.18, 1.38, 1.66), (0.02, 1.52, 1.70), 55.0)],
           dof=dict(focus=2.35, fstop=2.0), shake=[(1241, 0.4, 3)], subjects=["shinobi", "saint"],
           framing="insert")
    C.shot("S12e", *CUT["S12e"], [(1244, (0.92, 3.75, 1.72), (-1.04, -0.83, 1.08), 45.0),
                                  (1259, (0.92, 3.92, 1.72), (-1.02, -0.66, 1.02), 45.0)],
           dof=dict(focus=head_sh, fstop=2.8), shake=[(1257, 0.35, 3)], subjects=["shinobi", "saint"],
           framing="ots")
    C.shot("S12f", *CUT["S12f"], [(1260, (2.35, -0.70, 1.05), (-1.03, 2.90, 1.82), 28.0),
                                  (1275, (2.30, -0.55, 1.05), (-1.17, 2.96, 1.85), 28.0)],
           shake=[(1273, 0.5, 4)], subjects=["shinobi", "saint"], framing="close")
    C.shot("S12g", *CUT["S12g"], [(1276, (18.00, 1.76, 1.40), (0.00, 1.76, 1.62), 150.0),
                                  (1320, (17.60, 1.78, 1.40), (0.00, 1.78, 1.62), 150.0)],
           dof=dict(focus=18.0, fstop=4.0), subjects=["shinobi", "saint"], framing="close")
    C.shot("S12h", *CUT["S12h"], [(1321, (7.80, 1.70, 1.35), (0.00, 1.70, 1.22), 35.0),
                                  (1344, (7.80, 1.22, 1.35), (0.00, 1.22, 1.22), 35.0)],
           subjects=["shinobi", "saint"], framing="wide")
    C.shot("S13a", *CUT["S13a"], [(1345, (5.90, 1.25, 1.10), (0.00, 1.25, 1.60), 30.0),
                                  (1362, (5.90, 0.90, 1.10), (0.00, 0.90, 1.62), 30.0),
                                  (1368, (5.90, 0.90, 1.10), (0.00, 0.90, 1.62), 30.0)],
           shake=[(1367, 0.3, 3)], subjects=["shinobi", "saint"], framing="medium")
    C.shot("S13b", *CUT["S13b"], [(1369, (3.30, -0.50, 1.50), (-1.50, 0.83, 1.86), 35.0),
                                  (1408, (2.95, -0.38, 1.52), (-1.86, 0.92, 1.90), 35.0)],
           dof=dict(focus=(0.06, 0.40, 1.78), fstop=2.0), subjects=["shinobi", "saint"], framing="close")
    C.shot("S13c", *CUT["S13c"], [(1409, (9.50, 0.95, 1.55), (0.00, 0.95, 1.62), 85.0),
                                  (1422, (9.50, 1.00, 1.55), (0.00, 1.00, 1.62), 85.0)],
           dof=dict(focus=9.5, fstop=2.8), subjects=["shinobi", "saint"], framing="close")
    C.shot("S13d", *CUT["S13d"], [(1423, (9.00, 1.80, 1.45), (0.00, 1.80, 1.22), 32.0),
                                  (1450, (9.00, 2.90, 1.45), (0.00, 3.00, 1.22), 32.0)],
           subjects=["shinobi", "saint"], framing="wide")
    C.shot("S13e", *CUT["S13e"], [(1451, (1.95, 4.95, 1.30), (-2.45, 7.29, 1.69), 65.0),
                                  (1470, (1.85, 5.00, 1.30), (-2.46, 7.43, 1.98), 65.0),
                                  (1488, (1.85, 5.00, 1.30), (-2.46, 7.43, 1.98), 65.0)],
           dof=dict(focus=head_sa, fstop=2.0), subjects=["saint"], framing="mcu")
    C.shot("S14a", *CUT["S14a"], [(1489, (2.90, 4.70, 0.98), (-1.71, 6.50, 1.68), 40.0),
                                  (1524, (2.80, 4.80, 0.98), (-1.83, 6.53, 1.72), 40.0)],
           dof=dict(focus=head_sa, fstop=2.8), subjects=["saint"], framing="close")
    C.shot("S14b", *CUT["S14b"], [(1525, (3.70, 4.55, 1.28), (-0.02, 6.20, 1.45), 34.0),
                                  (1552, (3.80, 4.62, 1.28), (0.03, 6.22, 1.45), 34.0)],
           subjects=["saint"], framing="medium")
    C.shot("S14c", *CUT["S14c"], [(1553, (1.62, -0.42, 1.52), (-0.28, -1.62, 1.50), 50.0),
                                  (1574, (1.52, -0.48, 1.52), (-0.30, -1.62, 1.50), 50.0)],
           dof=dict(focus=head_sh, fstop=2.0), subjects=["shinobi"], framing="mcu")
    C.shot("S14d", *CUT["S14d"], [(1575, (10.76, 4.01, 1.35), (5.80, 4.56, 1.64), 60.0),
                                  (1604, (10.76, 4.01, 1.35), (5.80, 4.56, 1.64), 60.0)],
           dof=dict(focus=10.9, fstop=4.0), subjects=["saint"], framing="medium")
    C.shot("S14e", *CUT["S14e"], [(1605, (4.20, 3.60, 1.30), (-0.40, 6.30, 1.95), 32.0),
                                  (1632, (4.10, 3.66, 1.28), (-0.40, 6.30, 1.95), 32.0)],
           subjects=["saint"], framing="medium")


# =============================================================================================================
# lane entry
# =============================================================================================================
def build(ctx):
    """Lane entry (acts contract): keys only inside SPAN (+- handles), cameras through cameras.shot, events through
    events.emit."""
    sh, sa = ctx["chars"]["shinobi"], ctx["chars"]["saint"]
    stubs = ctx.get("stubs", {})
    missing = [m for m in ("characters", "moves", "environment", "vfx") if stubs.get(m)]
    if missing:
        raise RuntimeError(f"act1b needs the real modules (placeholders: {missing})")
    marks = choreograph(sh, sa)
    environment_timeline(marks)
    effects(sh, sa, marks)
    story_events(sh, sa, marks)
    cameras(sh, sa)
    keyed = [sh, sa] + [bpy.data.objects[n] for n in ("SHINOBI_sword_ctrl", "SAINT_sword_ctrl", "SHINOBI_saya",
                                                       "SAINT_saya")
                        if n in bpy.data.objects]
    for ob in keyed:
        U.freeze_handles(ob, (SPAN[0] - 2, SPAN[1] + 2))
    return marks
