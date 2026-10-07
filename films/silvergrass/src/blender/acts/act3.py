"""
acts/act3.py - lane act3: S21, S22, S22b, S23 (frames 2497-3072), Act III "Thunder".

Shot breakdown: 21 sub-cuts, all hard cuts, defined below.
Enters HANDOFF[2496] (shinobi (0, -3) chudan, elder (0, 3) jodan two-handed, spear gone, tasuki on) and leaves at
HANDOFF[3072] (shinobi (0, -6) kneeling on the planted sword, head bowed; elder (0, 2.5) two-handed gedan).

    S21a 2497-2508  extreme wide: the bolt comes down on the raised sword, he CUTS it, the fork splits the pine
    S21b 2509-2520  low MCU of the blade: a few frames of afterglow, rain hissing on the steel
    S21c 2521-2592  extreme low ultra-wide under the act card: the student stalks in, the master lifts into hasso
    S22a..S22j      the strobe (2593-2784): lit almost only by lightning; the master presses eight blows
    S22ba..S22bd    the counter (2785-2880): steady storm light, the student's three strikes, the master into jodan
    S23a..S23e      the low point (2881-3072): the grounded full-power cut splits the rain, the blast throws the
                    student 7 m screen-left; he ends on one knee, sword planted, head bowed; two unhurried steps.

Build: Blender -b --factory-startup --python src/blender/build_scene.py -- --lanes act3 --quality preview
Partial builds without act1b / act2 get local stand-ins for what those lanes own and this lane relies on (the S11
shear stubble, the burnt annulus, the drowned fire ring's glowing steam band, the film rain, wetness) - see
_local_upstream_standins(); in a build that contains those lanes nothing is duplicated.
"""
import math
import os
import sys
import zlib

import bpy
from mathutils import Vector

ROOT = (__import__("os").environ.get("SILVERGRASS_ROOT") or str(next(p for p in __import__("pathlib").Path(__file__).resolve().parents if (p / "src" / "common" / "config.py").is_file())))   # repo root (portable)
for _p in (os.path.join(ROOT, "src", "common"), os.path.join(ROOT, "src", "blender")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import config  # noqa: E402
import bl_util as U  # noqa: E402
import cameras as C  # noqa: E402
import events as EV  # noqa: E402
from acts import sub_cuts  # noqa: E402

LANE = "act3"
SPAN = tuple(config.lane_span(LANE))                  # (2497, 3072)
H_IN = config.HANDOFF[SPAN[0] - 1]                    # HANDOFF[2496]
H_OUT = config.HANDOFF[SPAN[1]]                       # HANDOFF[3072]

# ---------------------------------------------------------------------------------------------- sub-cuts (§3)
# config shots split at the sub-cut starts: S21a 2497-2508, S21b 2509-2520, S21c 2521-2592, S22a 2593-2622,
# S22c 2623-2643, S22d 2644-2664, S22e 2665-2684, S22f 2685-2705, S22g 2706-2725, S22h 2726-2746, S22i 2747-2766,
# S22j 2767-2784, S22ba 2785-2808, S22bb 2809-2828, S22bc 2829-2852, S22bd 2853-2880, S23a 2881-2925, S23b 2926-2952,
# S23c 2953-2972, S23d 2973-3009, S23e 3010-3072.  S22's sub-cuts skip the letter b (S22b is the next shot's id).
_S22_IDS = dict(zip(("S22" + c for c in "abcdefghi"), ("S22" + c for c in "acdefghij")))
CUTS = [(_S22_IDS.get(c, c), a, b) for c, a, b in sub_cuts(LANE, {
    "S21": (2509, 2521), "S22": (2623, 2644, 2665, 2685, 2706, 2726, 2747, 2767), "S22b": (2809, 2829, 2853),
    "S23": (2926, 2953, 2973, 3010)})]
CUT = {c: (a, b) for c, a, b in CUTS}

# ---------------------------------------------------------------------------------------------- anchors (§1, §3)
FORK_AT = (0.00, 2.40, 2.80)          # the bolt stops just above the blade and forks
STRUCK = (0.00, 2.42, 2.71)           # the struck point on the edge (u 0.8)
IMPACT = (0.00, 1.75, 0.00)           # S23: the grounded cut's tip strikes the flooded ground here
SH0 = tuple(H_IN["shinobi"]["pos"])   # HANDOFF[2496] / [3072] roots: (0, -3)
SA0 = tuple(H_IN["saint"]["pos"])     # (0, 3)
SH_END = tuple(H_OUT["shinobi"]["pos"])     # (0, -6)
SA_END = tuple(H_OUT["saint"]["pos"])       # (0, 2.5)
PLANT_TIP = (0.02, -5.46, 0.0)        # the planted sword's tip in the mud

# the eight blows of the strobe (the master) and the three of the counter (the student): contact frames
A = dict(a1=2620, a2=2641, a3=2662, a4=2682, a5=2703, a6=2723, a7=2744, a8=2764)
S = dict(s1=2795, s2=2806, s3=2826)
F_RAIKIRI = config.MUSIC_CUES["raikiri"]                 # 2497: the bolt is cut on the lane's first frame
FLASHES = [F_RAIKIRI, 2605, 2620, 2662, 2703, 2744, 2764]  # §4 (every onset >= 15 f apart)
CUT_FRAME = config.MUSIC_CUES["low_point"]                 # 2950: the grounded full-power cut (bar 12.1)
ECU_SPARK_W = 12.0                    # spark light (W) for clashes seen in ECU / insert from ~1 m (default 40 W x scale
                                      # blew the masked face out to white in S22c)


def seed(cut, i):
    """Pipeline rule 13 seeds: zlib.crc32(f"{shot}:{i}")."""
    return zlib.crc32(f"{cut}:{i}".encode()) & 0x7FFFFFFF


def _mods():
    import characters as CH
    import environment as ENV
    import moves as M
    import poses as PZ
    import vfx as VFX
    return CH, ENV, M, PZ, VFX


# ---------------------------------------------------------------------------------------------- local helpers
def _local_pine_top():
    """Top of ENV_pine (bbox top - 0.3 m) = the point vfx.tree_strike(pos=None) uses."""
    pine = bpy.data.objects.get("ENV_pine")
    if pine is None:
        return (config.PINE_POS[0], config.PINE_POS[1], 10.2)
    Mw = U.world_matrix_of(pine)
    top = max((Mw @ Vector(c)).z for c in pine.bound_box)
    return (float(config.PINE_POS[0]), float(config.PINE_POS[1]), float(top - 0.3))


def _local_hold_ids(rig):
    """Objects whose animation makes up a character's pose: the rig (root + bones + state props), its sword
    controller and elbow override empties."""
    c = "SHINOBI" if rig.name.startswith("SHINOBI") else "SAINT"
    obs = [rig]
    for n in (f"{c}_sword_ctrl", f"{c}_elbow_R", f"{c}_elbow_L"):
        ob = bpy.data.objects.get(n)
        if ob is not None:
            obs.append(ob)
    return obs


def _local_hold(rig, f, n=1):
    """Freeze a tableau for the lit frames of a strobe flash: every animated channel of the character is re-keyed
    at f+n with its value at f and the key at f becomes CONSTANT (the body holds f .. f+n, then moves on).  Rain,
    sparks and the secondary springs keep moving (they are not keyed here)."""
    for ob in _local_hold_ids(rig):
        for fc in U.fcurves_of(ob):
            if not fc.keyframe_points:
                continue
            v = fc.evaluate(f)
            kps = fc.keyframe_points
            k0 = kps.insert(f, v, options={'FAST'})
            k0.interpolation = 'CONSTANT'
            k1 = kps.insert(f + n, v, options={'FAST'})
            k1.interpolation = 'BEZIER'
            fc.update()


def _local_cheat(M, rig, f_last, f_next, xy, facing=None):
    """DIRECTION §2 cheat across the cut f_last | f_next (<= 0.5 m): the root holds CONSTANT on the outgoing
    cut's last frame and jumps to `xy` on the next cut's first frame; both feet are re-planted by the same offset
    on the cut (a one-frame 'step' the bake hides on the cut) so they do not slide in the new cut."""
    x, y, z, a = M.root_at(rig, f_last)
    fac = a if facing is None else facing
    dx, dy = xy[0] - x, xy[1] - y
    M.root(rig, f_last, (x, y), a, z=z, interp='CONSTANT')
    for side in ("L", "R"):
        keys = M._world_foot_keys(rig, side, -math.inf, f_last)
        if not keys:
            continue
        bw, yw = keys[-1]["bw"], keys[-1]["yw"]
        M.plant(rig, f_last, side, (bw.x, bw.y), yaw=yw)
        M.plant(rig, f_next, side, (bw.x + dx, bw.y + dy), yaw=yw + (fac - a))
    M.root(rig, f_next, xy, fac, z=z, interp='BEZIER')


def _local_flash(ENV, VFX, f, s, direction, bolt=None, tint=None):
    """One strobe flash through the vfx budget registry (a visible bolt or an in-cloud env_flash), then re-keyed
    on the same frame with its light direction (same frame = merged, max strength).  Returns the applied
    environment strength (asserted > 0: a refused flash would silently break the strobe grammar)."""
    if bolt is not None:
        VFX.lightning_bolt(f, flash=True, flash_strength=s, **bolt)
    else:
        VFX.env_flash(f, s, 2)
    kw = dict(direction=direction)
    if tint is not None:
        kw["tint"] = tint
    got = ENV.flash(f, s, 2, **kw)
    if not got:
        raise RuntimeError(f"act3: flash at {f} refused by the budget ({ENV.flash_log()[-3:]})")
    return got


def _local_upstream_standins(ENV, VFX):
    """Partial builds only: recreate the rain, fire ring and steam this lane relies on, using the exact
    environment and VFX calls from acts/act1b.py and acts/act2.py when
    those lanes are NOT part of the current build (lane_tools.lane_reports() lists the lanes ended before this
    one).  In a build that contains them nothing is added."""
    import lane_tools as LT
    done = set(LT.lane_reports().keys())
    made = []
    if "act1b" not in done:
        ENV.grass_effect('shear', dict(origin=(0.0, 2.6), radius=14.0, arc_deg=220.0, facing_deg=176.5,
                                       fluff=0, wind=1.0), 1101, 1118)
        made.append("shear")
    if "act2" not in done:
        ENV.grass_effect('burn', dict(center=(0.0, 1.5), radius=11.0, width=2.6, ramp_frames=18), 1638)
        VFX.fire_ring(1633, (0.0, 1.5, 0.0), radius=11.0, grow_frames=12, f_out=2401, height=2.2, seed=15,
                      ember_rate=40.0, shadow_angles=(150.0, 210.0), light_energy=400.0)
        VFX.rain(2376, 3500, intensity=[(2376, 0.0), (2382, 0.06), (2400, 0.12), (2401, 1.0), (3470, 1.0),
                                        (3500, 0.0)], seed=300)
        ENV.set_wetness(SPAN[0], 1.0, interp='CONSTANT')
        made.append("burn+fire_ring+rain+wet")
    return made


# ---------------------------------------------------------------------------------------------- local poses (§5)
def _register_local_poses(PZ):
    """Act III poses the library lacks (breakdown §5), added to poses.POSES under 'a3_*' for this process only
    (the shared module is not edited).  Poses format: SHINOBI metres, rig space (forward = -Y, his left = +X).
    Blades that must hit WORLD points (the raikiri, the grounded cut, the slide) are keyed with
    characters.key_sword / key_blade_tip on top of these bodies (their ctrl is None)."""
    P = PZ.POSES
    T, foot, stance, blade, elev, merge, arm = PZ.torso, PZ.foot, PZ.stance, PZ.blade, PZ.elev, PZ.merge, PZ.arm
    # --- the elder
    P["a3_raikiri_contact"] = PZ.pose(
        "raikiri: mid-downswing from jodan, face up at the bolt, front foot planted", "act3",
        body=T(lean=-6, look_pitch=-16, gaze=0.6), hips=(0.0, -0.08, 0.04),
        legs=stance(front=0.40, back=0.30, width=0.28, lead="L", heel_back=20), left="grip")
    P["a3_raikiri_follow"] = PZ.pose(
        "raikiri follow-through: the cut stops at waist height (zanshin), eyes on the student", "act3",
        body=T(lean=17, twist=-3), hips=(0.0, -0.12, 0.06),
        legs=stance(front=0.45, back=0.35, width=0.28, lead="L", heel_back=25), left="grip")
    P["a3_overcommit"] = PZ.pose(
        "A8 over-committed: the heavy blow slid off his blade into the mud, hips low, trunk folded", "act3",
        body=T(lean=42, twist=-12, look_pitch=-8), hips=(0.0, -0.28, 0.10),
        legs=stance(front=0.55, back=0.45, width=0.30, heel_back=35), left="grip")
    zl = stance(front=0.62, back=0.52, width=0.30, lead="L", heel_back=35)
    zl["L"]["knee"] = (0.0, -0.5, 1.0)                 # deep lunge: same thigh-flip guard as the kneel
    P["a3_zanshin_grounded"] = PZ.pose(
        "the grounded full-power cut: front foot stamped, rear leg long, trunk folded over the blade", "act3",
        body=T(lean=48, look_pitch=-14, gaze=0.8), hips=(0.0, -0.36, 0.10), legs=zl, left="grip")
    P["a3_cut_rise"] = PZ.pose(
        "the grounded cut's apex: blade raised further back over his head, weight rising onto the toes", "act3",
        body=T(lean=-10, look_pitch=4), hips=(0.0, -0.02, -0.03),
        legs=stance(front=0.30, back=0.30, width=0.26, lead="L", heel_back=25), left="grip")
    # --- the student
    P["a3_leap_back_arch"] = PZ.pose(
        "leaping back from the horizontal cut, arched, blade upright in front", "act3",
        body=T(lean=-26, look_pitch=-6, gaze=0.7), hips=(0.0, 0.0, -0.04),
        legs={"R": foot(-0.12, -0.26, lift=0.30, air=True, heel=20), "L": foot(0.12, 0.08, lift=0.26, air=True,
                                                                               heel=30)},
        ctrl=blade((-0.03, -0.36, 1.26), (0.0, -0.20, 0.98)), left="grip")
    blk = dict(P["deflect_overhead_block"])
    blk["hips_offset"] = (0.0, -0.30, 0.0)
    blk["desc"] = "roof block pressed down by the heavy blow: knees give"
    P["a3_block_pressed"] = blk
    P["a3_uke_nagashi"] = PZ.pose(
        "uke-nagashi: fists at his right temple, the blade a slanted roof down to his left", "act3",
        body=T(lean=6, twist=10, look_pitch=-4), hips=(0.0, -0.14, 0.0),
        legs=stance(front=0.30, back=0.32, width=0.26, heel_back=20),
        ctrl=blade((0.05, -0.35, 1.60), (0.60, -0.40, -0.69), edge=(0.56, -0.37, 0.71)), left="grip")
    P["a3_furikaburi"] = PZ.pose(
        "furikaburi: the blade circled up over the head, poised for the counter", "act3",
        body=T(lean=-4, twist=-6, look_pitch=4), hips=(0.0, -0.10, 0.0),
        legs=stance(front=0.30, back=0.30, width=0.24, heel_back=20),
        ctrl=blade((-0.03, -0.14, 1.84), (0.06, 0.55, 0.83), edge=(0.0, -0.83, 0.55)), left="grip")
    P["a3_chudan_settle"] = dict(P["chudan"], hips_offset=(0.0, -0.13, 0.06),
                                 ctrl=blade((-0.03, -0.38, 0.95), elev(24)))
    P["a3_chudan_coil"] = dict(P["chudan"], hips_offset=(0.0, -0.18, 0.05),
                               ctrl=blade((-0.03, -0.36, 0.95), elev(22)))
    # airborne / tumbling bodies: FK legs (thigh X = flexion, Z = abduction, mirrored per side; shin X = knee
    # flexion) - the pose library's ball/ankle solver picks hyper-extended or 360-degree-wrapped knees for these
    # extreme hip angles, so the feet are registered as 'air' by the caller (moves._feet_air) instead.
    def legs_fk(tL, sL, fL, tR, sR, fR):
        return {"thigh.L": tL, "shin.L": sL, "foot.L": fL, "toe.L": (0.0, 0.0, 0.0),
                "thigh.R": tR, "shin.R": sR, "foot.R": fR, "toe.R": (0.0, 0.0, 0.0)}
    P["a3_abort"] = PZ.pose(
        "the attack aborted: throwing himself back off the front foot, arched, blade pulled up in front of him",
        "act3", body=merge(T(lean=-22, look_pitch=-4, gaze=0.8),
                           legs_fk((34.0, 0.0, 6.0), (48.0, 0.0, 0.0), (-12.0, 0.0, 0.0),
                                   (-6.0, 0.0, 6.0), (22.0, 0.0, 0.0), (22.0, 0.0, 0.0))),
        hips=(0.0, -0.08, -0.08), ctrl=blade((-0.03, -0.30, 1.40), elev(72)), left="grip")
    P["a3_thrown"] = PZ.pose(
        "blown backward by the blast: head snapped back, left arm flung, sword held out to his right, knees bent "
        "with the legs trailing forward", "act3",
        body=merge(T(lean=-40, look_pitch=-22, gaze=0.0), arm("L", flex=40, abd=60, elbow=20),
                   legs_fk((52.0, 0.0, 10.0), (78.0, 0.0, 0.0), (-20.0, 0.0, 0.0),
                           (38.0, 0.0, 8.0), (62.0, 0.0, 0.0), (-15.0, 0.0, 0.0))),
        hips=(0.0, 0.0, -0.06), ctrl=blade((-0.36, -0.08, 1.02), (-0.30, 0.90, 0.30)), left="free")
    P["a3_land_back"] = PZ.pose(
        "landing on the back/left shoulder: trunk curled, knees up, sword out to the right", "act3",
        body=merge(T(lean=30, look_pitch=20, gaze=0.3), arm("L", flex=70, abd=20, elbow=60),
                   legs_fk((96.0, 0.0, 8.0), (104.0, 0.0, 0.0), (-10.0, 0.0, 0.0),
                           (88.0, 0.0, 8.0), (96.0, 0.0, 0.0), (-10.0, 0.0, 0.0))),
        hips=(0.0, -0.40, 0.0), ctrl=blade((-0.30, -0.10, 0.80), (-0.25, 0.92, 0.30)), left="free")
    tuck = {k: v for k, v in P["roll_tuck"].items() if k != "legs"}
    tuck.update(legs_fk((122.0, 0.0, 6.0), (138.0, 0.0, 0.0), (-20.0, 0.0, 0.0),
                        (118.0, 0.0, 6.0), (134.0, 0.0, 0.0), (-20.0, 0.0, 0.0)))
    tuck["desc"] = "backward roll, tucked ball (FK legs: knees to the chest)"
    P["a3_roll_tuck"] = tuck
    kn_legs = {s: dict(lg, air=True) for s, lg in P["kneel_planted"]["legs"].items()}
    # the raised front (left) thigh lies almost along 'forward': with the default knee hint the solver's thigh
    # frame flips 180 deg about the bone (thigh Z -176 + knee -103 = a twisted thigh) - hint up-forward instead
    kn_legs["L"]["knee_dir"] = (0.0, -0.5, 1.0)
    P["a3_knee_skid"] = PZ.pose(
        "skidding on the right knee (the kneel's legs held rigid while the body slides), left arm out for balance, "
        "sword low to the right", "act3",
        body=merge(T(lean=16, look_pitch=-6), arm("L", flex=30, abd=25, elbow=30)),
        hips=(0.0, -0.44, 0.0), legs=kn_legs,
        ctrl=blade((-0.26, -0.28, 0.62), (-0.20, -0.85, -0.45)), left="free")
    # the kneel from 2979 to the lane's end: the library's kneel_planted with its legs held rigid ('air': the root
    # does not move after 2991, so nothing slides) - one leg solution for the whole range, no per-frame re-solve
    kp = dict(P["kneel_planted"], legs=kn_legs)
    kp.update({"neck": (4.0, 0.0, 0.0), "head": (0.0, 0.0, 0.0), "desc": "kneel_planted, head still up"})
    P["a3_kneel_headup"] = kp
    P["a3_kneel_bowed"] = dict(P["kneel_planted"], legs=kn_legs, desc="kneel_planted (legs held rigid)")
    return [n for n in P if n.startswith("a3_")]


# ---------------------------------------------------------------------------------------------- choreography
def _norm(v):
    v = Vector(v)
    return tuple(v.normalized())


def _edge_fwd(d):
    """Edge of a blade lying in the Y-Z plane (the line of the duel), on the cutting side: (0, -dz, dy)."""
    return (0.0, -d[2], d[1])


def _entering_state(CH, SH, SA):
    """HANDOFF[2496] re-asserted at the lane's first frame (lane isolation; order matters for the SAINT)."""
    f = SPAN[0]
    CH.set_weapon_state(SH, f, "drawn")
    CH.set_arm_mode(SH, f, "ik")
    CH.set_two_hand(SH, f, True, weapon="katana")
    CH.set_weapon_state(SA, f, "gone")            # the spear (lost in the fire in S19)
    CH.set_weapon_state(SA, f, "drawn")           # the katana last: active_weapon = katana
    CH.set_arm_mode(SA, f, "ik")
    CH.set_two_hand(SA, f, True, weapon="katana")
    CH.set_costume(f, haori=False, thrown=False)  # tasuki on; the thrown haori burnt away in Act II
    CH.set_hat(f, "off")
    CH.set_beard_cord(f, False)
    CH.set_kunai_in_hand(f, False)
    for i in (1, 2, 3):
        ob = bpy.data.objects.get(f"SHINOBI_kunai_{i}")
        if ob is not None:
            U.key_visible(ob, f, False)


def _s21(CH, M, SH, SA):
    """S21a-c: the raikiri (blade already mid-cut on the first frame), zanshin, hasso; the student recoils from
    the crack, then stalks in under the act card."""
    # --- the elder: raikiri contact -> follow-through (keyed per frame, world blade frames from §3 S21a)
    M.root(SA, 2497, SA0, float(H_IN["saint"]["facing"]), interp='LINEAR')
    M.pose(SA, 2497, "a3_raikiri_contact", interp='LINEAR')
    for f, grip, d in ((2497, (0.00, 2.72, 2.05), (0.0, -0.42, 0.91)),
                       (2498, (0.00, 2.62, 1.75), (0.0, -0.88, 0.47)),
                       (2499, (0.00, 2.56, 1.45), (0.0, -0.99, -0.12)),
                       (2500, (0.00, 2.55, 1.30), (0.0, -0.94, -0.34))):
        d = _norm(d)
        CH.key_sword(SA, f, grip=grip, direction=d, edge=_edge_fwd(d), space='WORLD', interp='LINEAR')
    M.pose(SA, 2500, "a3_raikiri_follow", ctrl=False)
    M.hold(SA, 2530)                                            # zanshin 2500-2530
    M.stance(SA, 2548, "chudan", hands="keep")                  # straightens, blade to chudan
    M.stance(SA, 2580, "hasso", hands="keep", breathe=12)       # the slow hasso lift 2548 -> 2580
    M.hold(SA, 2594)
    # --- the student: recoil from the flash + crack, back to guard, then the stalk
    M.root(SH, 2497, SH0, float(H_IN["shinobi"]["facing"]), interp='LINEAR')
    M.stance(SH, 2497, "chudan")
    M.step(SH, 2498, 2506, (0.0, -3.15))
    M.overlay(SH, 2501, {"spine": (-8.0, 0.0, 0.0), "chest": (-4.0, 0.0, 0.0), "head": (0.0, -10.0, 4.0)})
    M.stance(SH, 2508, "chudan")
    M.hold(SH, 2530)
    M.walk(SH, 2530, 2590, (0.0, -3.15), (0.0, -1.25), upper="chudan", stride=0.48)
    M.stance(SH, 2592, "chudan")


CONTACT = {}                          # clash frame -> the placed contact point (cameras aim the ECUs at it)


def _clash(M, att, dfn, f, point, **kw):
    """moves.clash + remember where the blades were placed to cross (point None = the natural crossing of the
    keyed blades: no big controller jump in the wides; the ECU cameras are aimed at the result)."""
    reg = M.clash(att, dfn, f, point=point, **kw)
    CONTACT[f] = tuple(reg["point"]) if reg.get("point") else point
    return reg


def _s22(CH, M, SH, SA):
    """S22a-j, the strobe: the master's eight two-handed blows on every second beat, the student blocking,
    leaping, parrying, side-stepping, finally turning the heaviest blow aside.  Cheats across 7 cuts (D2)."""
    steel = dict(color="steel")
    # ---- S22a: he comes in (2605 reveal) / A1 kesagiri blocked (2620)
    M.step(SA, 2594, 2605, (0.0, 2.85))
    M.stance(SA, 2605, "hasso", hands="keep")
    M.walk(SH, 2593, 2612, (0.0, -1.25), (0.0, 0.75), upper="chudan", stride=0.62)
    M.step(SH, 2613, 2619, (0.0, 0.60))
    M.slash(SA, A["a1"], "diag_down_R", lunge=0.30, recover=8, recover_to="rising_L_windup")
    M.deflect(SH, A["a1"], "mid_L", recover=6)
    _clash(M, SA, SH, A["a1"], None, strength=0.75, sparks=steel)          # wide: the natural crossing
    # ---- S22c: A2 rising cut deflected low on his right (2641)
    M.step(SH, 2631, 2639, (0.0, 0.30))
    M.slash(SA, A["a2"], "rising_L", lunge=0.30, recover=7, recover_to="horizontal_R_windup")
    M.deflect(SH, A["a2"], "low", recover=6)
    _clash(M, SA, SH, A["a2"], None, strength=0.7, sparks=dict(steel, light_energy=ECU_SPARK_W))  # ECU S22c
    _local_cheat(M, SH, 2643, 2644, (0.0, 0.60))
    _local_cheat(M, SA, 2643, 2644, (0.0, 2.55))
    # ---- S22d: A3 horizontal, the student leaps back (near-miss 2662)
    M.slash(SA, A["a3"], "horizontal_R", lunge=0.25, recover=5, recover_to="thrust_windup")
    M.jump(SH, 2657, 2664, (0.0, 0.60), (0.0, 0.05), apex=0.20, crouch=3, air_pose="a3_leap_back_arch",
           recover=6)
    _local_cheat(M, SH, 2664, 2665, (0.0, 0.35))
    _local_cheat(M, SA, 2664, 2665, (0.0, 2.60))
    # ---- S22e: A4 thrust parried past his right ear (2682)
    M.step(SH, 2672, 2680, (0.0, 0.20))
    M.slash(SA, A["a4"], "thrust", lunge=0.45, recover=8, recover_to="overhead_windup")
    M.deflect(SH, A["a4"], "mid_R", recover=6)
    _clash(M, SA, SH, A["a4"], (0.10, 1.00, 1.40), strength=0.7,
            sparks=dict(color="steel", direction=(0.70, -0.55, 0.20), light_energy=ECU_SPARK_W))
    tip = Vector((0.35, 0.15, 1.55))
    CH.key_blade_tip(SA, 2684, tip=tuple(tip), direction=_norm((0.30, -0.95, 0.06)), space='WORLD')
    M.overlay(SH, 2684, {"head": (0.0, 10.0, 0.0)})
    _local_cheat(M, SH, 2684, 2685, (0.0, 0.55))
    _local_cheat(M, SA, 2684, 2685, (0.0, 2.50))
    # ---- S22f: A5 heavy overhead onto the roof block, knees give (2703)
    M.step(SH, 2690, 2700, (0.0, 0.50))
    M.slash(SA, A["a5"], "overhead", lunge=0.25, recover=8, recover_to="diag_down_L_windup")
    M.deflect(SH, A["a5"], "overhead_block", recoil=1.4, recover=8)
    M.pose(SH, A["a5"], "a3_block_pressed", ctrl=False)
    # the blow lands on the roof block beside his head, near the elder's kissaki (monouchi): the tip ends just past
    # the block above his right shoulder, never in his head (a natural crossing sat 9 cm from his skull)
    _clash(M, SA, SH, A["a5"], (0.30, 0.78, 1.47), strength=0.95, kind="clash_heavy", att_frac=0.84,
            sparks=dict(color="steel", scale=1.6, count=90, spread=110, direction=(0.0, -0.2, -0.9)))
    _local_cheat(M, SH, 2705, 2706, (0.0, 0.60))
    _local_cheat(M, SA, 2705, 2706, (0.0, 2.55))
    # ---- S22g: A6 reverse diagonal deflected high on his right (2723)
    M.step(SH, 2712, 2721, (0.0, 0.30))
    M.slash(SA, A["a6"], "diag_down_L", lunge=0.30, recover=8, recover_to="diag_down_R_windup")
    M.deflect(SH, A["a6"], "mid_R", recover=6)
    _clash(M, SA, SH, A["a6"], None, strength=0.75,
            sparks=dict(color="steel", direction=(0.55, 0.45, -0.20), spread=70, light_energy=1.6 * ECU_SPARK_W))
    _local_cheat(M, SH, 2725, 2726, (0.0, 0.60))
    _local_cheat(M, SA, 2725, 2726, (0.0, 2.55))
    # ---- S22h: A7 kesagiri through empty air, the sidestep (2744)
    M.slash(SA, A["a7"], "diag_down_R", lunge=0.20, recover=6, recover_to="overhead_windup")
    M.dodge(SH, A["a7"], "right", dist=0.5, recover=6)
    _local_cheat(M, SH, 2746, 2747, (0.45, 0.55), facing=183.0)
    _local_cheat(M, SA, 2746, 2747, (0.0, 2.50))
    # ---- S22i: A8 heavy overhead turned aside (uke-nagashi), the blade slides off into the mud (2764 -> 2770)
    M.step(SH, 2748, 2754, (0.25, 0.55), facing=180.0)
    M.pose(SH, 2756, "a3_uke_nagashi")
    M.hold(SH, 2762)
    M.slash(SA, A["a8"], "overhead", lunge=0.0, follow=2, recover=2, recover_to="overhead_follow")
    _clash(M, SA, SH, A["a8"], (0.11, 0.96, 1.50), strength=0.85, def_frac=0.25, sparks=steel)
    slide = [(2766, (-0.10, 1.10, 1.24), (-0.35, -0.75, -0.56)),
             (2768, (-0.30, 1.22, 0.70), (-0.30, -0.55, -0.78)),
             (2770, (-0.45, 1.30, 0.15), (-0.28, -0.45, -0.85))]
    M.pose(SA, 2770, "a3_overcommit", ctrl=False)
    for f, tp, d in slide:
        CH.key_blade_tip(SA, f, tip=tp, direction=_norm(d), space='WORLD')
    M.hold(SA, 2777)
    # ---- S22j: the opening: he circles the blade up over his head (furikaburi)
    M.step(SH, 2767, 2772, (0.15, 0.65))
    M.swing(SH, 2772, 2782, "a3_uke_nagashi", "a3_furikaburi")
    M.pose(SH, 2782, "a3_furikaburi", ctrl=False)
    M.stance(SA, 2787, "gedan", hands="keep")


def _s22b(CH, M, SH, SA):
    """S22ba-bd, the counter in steady storm light: diagonal cut, rising cut, lunging thrust (white sparks); the
    master parries, gives ground a full step, then gathers into jodan (set 2867, bar 10)."""
    white = dict(color="white")
    # ---- S22ba: S1 diagonal cut (2795), S2 rising cut (2806)
    M.slash(SH, S["s1"], "diag_down_R", lunge=0.25, follow=3, recover=2, recover_to="rising_L_windup")
    M.step(SA, 2786, 2794, (0.0, 2.70))
    M.deflect(SA, S["s1"], "mid_L", recover=3)
    _clash(M, SH, SA, S["s1"], None, strength=0.65, sparks=white)
    M.slash(SH, S["s2"], "rising_L", windup=2, hold_frames=1, strike=3, lunge=0.20, follow=3, recover=5,
            recover_to="thrust_windup")
    M.step(SA, 2797, 2805, (0.0, 2.95))
    M.deflect(SA, S["s2"], "low", recover=4)
    _clash(M, SH, SA, S["s2"], (-0.20, 2.05, 1.15), strength=0.65, sparks=white)
    # ---- S22bb: S3 lunging thrust swept aside to his left (2826)
    M.slash(SH, S["s3"], "thrust", lunge=0.45, recover=10)
    M.step(SA, 2816, 2825, (0.0, 3.15))
    M.deflect(SA, S["s3"], "mid_L", recover=6)
    M.overlay(SA, 2828, {"spine": (-8.0, 0.0, 0.0), "chest": (-4.0, 0.0, 0.0)})
    _clash(M, SH, SA, S["s3"], (0.10, 2.40, 1.40), strength=0.8,
            sparks=dict(color="white", direction=(0.4, 0.8, 0.1), light_energy=ECU_SPARK_W))
    # ---- S22bc: the master driven back a full step; the student recovers from the lunge
    M.step(SA, 2830, 2839, (0.0, 3.40))
    M.stance(SA, 2841, "chudan", hands="keep")
    M.step(SH, 2834, 2848, (0.0, 1.10))
    M.stance(SH, 2850, "chudan", breathe=24)
    # ---- S22bd: the half step back and the jodan lift (2847 -> 2867)
    M.step(SA, 2846, 2860, (0.0, 3.60))
    M.stance(SA, 2867, "jodan", hands="keep", breathe=60)


def _catmull(keys, f):
    """Catmull-Rom interpolation of [(frame, (values...))] at frame f (clamped at the ends)."""
    fr = [k[0] for k in keys]
    if f <= fr[0]:
        return keys[0][1]
    if f >= fr[-1]:
        return keys[-1][1]
    i = max(j for j in range(len(fr) - 1) if fr[j] <= f)
    f0, f1 = fr[i], fr[i + 1]
    t = (f - f0) / (f1 - f0)
    p0 = keys[max(0, i - 1)][1]
    p1, p2 = keys[i][1], keys[i + 1][1]
    p3 = keys[min(len(keys) - 1, i + 2)][1]
    out = []
    for a, b, c, d in zip(p0, p1, p2, p3):
        out.append(0.5 * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t * t
                          + (-a + 3 * b - 3 * c + d) * t * t * t))
    return tuple(out)


def _local_body_track(M, rig, keys, facing, f0, f1, interp_last='BEZIER'):
    """Root keyed per frame from a BODY-CENTRE track [(frame, (cy, cz, pitch_deg, hc))] (x = 0): the character
    pitches about his hips (hc = hip height above the root along his body axis), not about his feet - so a
    backward throw / tumble rotates around the body like M.roll does.  pitch < 0 = tipping BACKWARD (+X rotation
    of the rig pitches forward)."""
    a = math.radians(facing)
    for f in range(int(f0), int(f1) + 1):
        cy, cz, th, hc = _catmull(keys, f)
        t = math.radians(th)
        # R = Rz(a) Rx(t) applied to (0, 0, -hc)
        oy, oz = hc * math.sin(t), -hc * math.cos(t)
        ox, oy = -math.sin(a) * oy, math.cos(a) * oy
        M.root(rig, f, (ox, cy + oy), facing, z=max(0.0, cz + oz), interp='LINEAR', tilt=(th, 0.0))
    U.set_key_interp_at(rig, int(f1), interp_last, "rotation_euler")


# rough body radii around the bone axes (m): the ground-contact solve keeps these surfaces >= 0
_LOCAL_RADII = {"head": 0.11, "neck": 0.07, "chest": 0.14, "spine": 0.13, "hips": 0.13, "shoulder": 0.07,
                "upper_arm": 0.06, "forearm": 0.05, "hand": 0.04, "thigh": 0.08, "shin": 0.06, "foot": 0.05,
                "toe": 0.03}


def _local_lowest(rig, skip=()):
    """Lowest body SURFACE point (z of the bone joints minus the local radius) of the evaluated rig at the current
    frame, ignoring tails / beard / weapon sockets and the bones in `skip`."""
    mw = rig.matrix_world
    lo, who = math.inf, None
    for pb in rig.pose.bones:
        base = pb.name.split(".")[0]
        if base not in _LOCAL_RADII or pb.name in skip:
            continue
        r = _LOCAL_RADII[base]
        z = min((mw @ pb.head).z, (mw @ pb.tail).z) - r
        if z < lo:
            lo, who = z, pb.name
    return lo, who


def _local_ground_contact(rig, frames, contact=(), skip=(), clearance=0.0):
    """Per-frame root-z correction for tumbling bodies (the thrown / rolling student): on `contact` frames the
    lowest body surface is put ON the ground (a roll always touches it - no floating, no sinking); on the other
    frames it is only lifted when it would go below `clearance`.  Needs per-frame root z keys (body track)."""
    sc = bpy.context.scene
    fcz = next((fc for fc in U.fcurves_of(rig) if fc.data_path == "location" and fc.array_index == 2), None)
    if fcz is None:
        return []
    out = []
    for f in frames:
        sc.frame_set(f)
        lo, who = _local_lowest(rig, skip)
        want = 0.0 if f in contact else max(lo, clearance)
        dz = want - lo
        if abs(dz) < 1e-4:
            continue
        for kp in fcz.keyframe_points:
            if abs(kp.co.x - f) < 1e-3:
                kp.co.y += dz
                kp.handle_left.y += dz
                kp.handle_right.y += dz
                out.append((f, round(dz, 3), who))
                break
        fcz.update()
    return out


def _s23(CH, M, SH, SA):
    """S23a-e, the low point: stand-off; the student attacks the open jodan, aborts, the grounded full-power cut
    strikes the flooded ground between them; the blast throws him 7 m screen-left (never touched), he tumbles,
    skids on one knee, plants his sword and bows his head; the master walks two unhurried steps."""
    # ---- S23a: stillness (the master holds jodan: stance breathe from S22bd)
    M.hold(SH, 2898)
    M.pose(SH, 2910, "a3_chudan_settle")
    M.hold(SH, 2918)
    M.pose(SH, 2926, "a3_chudan_coil")
    # ---- S23b: the attack (2929-2939: step-lunge thrust at the open torso), the abort (2941), thrown (2950)
    # keyed by hand, not moves.slash: its follow-through / settle keys (f+1, f+3, f+4) would land inside the abort
    M.hold(SH, 2929)
    M.pose(SH, 2933, "thrust_windup")
    M.pose(SH, 2935, "thrust_windup", weight=1.04, feet=False)
    M.swing(SH, 2935, 2939, M.ctrl_matrix(SH, "thrust_windup", 2935), M.ctrl_matrix(SH, "thrust_strike", 2939),
            ease="in_quad")
    M.pose(SH, 2939, "thrust_strike", ctrl=False, lag={"hips": -1, "head": 1})
    M.root(SH, 2933, (0.0, 1.10), 180.0, interp='LINEAR')
    M.lunge_root(SH, 2934, 2940, 0.65)
    M.hold(SH, 2941)
    M.pose(SH, 2944, "a3_abort")
    M._feet_air(SH, 2944)
    CH.set_two_hand(SH, 2951, False, blend=2)                   # the blast tears the left hand off the hilt
    # body-centre track: (frame, (cy, cz, pitch, hc)); hc ~ the pose's hip height above the feet
    thrown = [(2941, (1.75, 0.82, 0.0, 0.82)), (2944, (1.58, 0.86, -6.0, 0.84)),
              (2947, (1.33, 0.96, -10.0, 0.86)), (2950, (1.05, 1.04, -12.0, 0.88)),
              (2952, (0.78, 1.26, -18.0, 0.90)), (2953, (0.60, 1.32, -22.0, 0.90)),
              (2955, (-0.25, 1.42, -35.0, 0.90)), (2958, (-1.30, 1.08, -55.0, 0.88)),
              (2960, (-1.90, 0.72, -68.0, 0.80)), (2962, (-2.35, 0.34, -80.0, 0.70)),
              # the backward tumble: one revolution about the hips, up onto the left foot / right knee
              (2965, (-2.95, 0.36, -140.0, 0.48)), (2968, (-3.55, 0.42, -205.0, 0.44)),
              (2971, (-4.10, 0.46, -265.0, 0.46)), (2975, (-4.60, 0.48, -325.0, 0.50)),
              (2978, (-4.84, 0.50, -352.0, 0.52)), (2980, (-4.90, 0.51, -360.0, 0.51))]
    _local_body_track(M, SH, thrown, 180.0, 2941, 2980)
    for f, name, kw in ((2950, "a3_thrown", dict(weight=0.6)), (2955, "a3_thrown", {}),
                        (2962, "a3_land_back", dict(ctrl=False)), (2965, "a3_roll_tuck", dict(ctrl=False)),
                        (2974, "a3_roll_tuck", dict(ctrl=False))):
        M.pose(SH, f, name, **kw)
        M._feet_air(SH, f)
    M.pose(SH, 2979, "a3_knee_skid", ctrl=False)
    # ---- S23d: the knee skid (2979-2990: kneel legs held rigid, sliding), sword planted (2986-2992), head bows
    M.root(SH, 2980, (0.0, -4.90), 180.0, interp='BEZIER', tilt=(0.0, 0.0))
    M.root_path(SH, 2981, 2991, (0.0, -4.92), SH_END, ease="out_cubic", facing0=180.0, facing1=180.0)
    M.pose(SH, 2988, "a3_knee_skid", ctrl=False)
    # the tumbling body always touches the ground while it rolls (no floating, nothing sinks into the mud)
    rarm = ("upper_arm.R", "forearm.R", "hand.R", "shoulder.R")
    fixed = _local_ground_contact(SH, range(2942, 2980), contact=set(range(2962, 2979)), skip=rarm)
    print(f"[act3] ground contact: {len(fixed)} root-z fixes, max {max([abs(d) for _, d, _ in fixed] or [0]):.2f} m")
    # the sword during the flight / tumble: held out on his right side, tip UP out of the mud (never through him)
    sc = bpy.context.scene
    for f in range(2957, 2980, 2):
        sc.frame_set(f)
        sh = SH.matrix_world @ SH.pose.bones["upper_arm.R"].head
        grip = Vector((sh.x + 0.34, sh.y, max(0.30, sh.z - 0.05)))
        d = _norm((0.30, -0.25 if f < 2966 else 0.10, 0.92))
        CH.key_sword(SH, f, grip=tuple(grip), direction=d, edge=(0.0, -1.0, 0.0), space='WORLD')
    sc.frame_set(2981)
    hip = SH.matrix_world @ SH.pose.bones["hips"].head
    CH.key_sword(SH, 2981, grip=(0.30, hip.y + 0.25, 0.55), direction=_norm((0.10, 0.80, -0.35)),
                 edge=(0.0, 0.0, -1.0), space='WORLD')        # blade low forward-right, tip above the stubble
    CH.set_two_hand(SH, 2984, True, blend=3)
    CH.key_blade_tip(SH, 2987, tip=(PLANT_TIP[0], PLANT_TIP[1] - 0.04, 0.40), direction=_norm((0.0, 0.18, -0.98)),
                     space='WORLD')
    M.pose(SH, 2991, "a3_kneel_headup")
    M.pose(SH, 3001, "a3_kneel_bowed")
    for f, d in ((3016, 2.0), (3036, -1.5), (3056, 2.0), (3072, 0.0)):
        M.overlay(SH, f, {"chest": (d, 0.0, 0.0)})
    # ---- the elder: jodan held to 2939, the full-power cut, zanshin, rise to gedan, two steps
    M.hold(SA, 2939)
    M.pose(SA, 2943, "a3_cut_rise", ctrl=False)
    CH.key_sword(SA, 2943, grip=(-0.02, 3.66, 2.00), direction=_norm((0.0, 0.80, 0.60)),
                 edge=_edge_fwd(_norm((0.0, 0.80, 0.60))), space='WORLD')
    M.step(SA, 2943, 2946, (0.0, 3.45), events=False)             # the stamp is emitted below (strength 1)
    d48 = (0.0, -1.0, 0.0)
    CH.key_sword(SA, 2948, grip=(0.0, 2.98, 1.45), direction=d48, edge=(0.0, 0.0, -1.0), space='WORLD',
                 interp='LINEAR')
    M.pose(SA, 2950, "a3_zanshin_grounded", ctrl=False)
    dz = _norm((0.0, -0.78, -0.62))
    for f, tp in ((2950, (0.0, 1.75, 0.02)), (2951, (0.0, 1.77, 0.07)), (2952, (0.0, 1.78, 0.06))):
        CH.key_blade_tip(SA, f, tip=tp, direction=dz, edge=_edge_fwd(dz), space='WORLD', interp='LINEAR')
    M.hold(SA, 2972)
    M.stance(SA, 3000, "gedan", hands="keep")
    M.step(SA, 3011, 3022, (0.0, 2.97))
    M.step(SA, 3030, 3042, SA_END)
    M.stance(SA, 3042, "gedan", hands="keep", breathe=30)
    M.hold(SA, 3072)
    M.hold(SH, 3072)


# ---------------------------------------------------------------------------------------------- cameras (§3)
def _cameras(SH, SA):
    """21 sub-cuts, all on the legal +X side of the Y action line (or on it for S23d, 0.85 m toward +X).
    Keys: (frame, pos, look, lens); lenses fixed per cut; cameras.shot makes the last key CONSTANT."""
    both = ["shinobi", "saint"]
    C.shot("S21a", *CUT["S21a"],
           keys=[(2497, (22.0, -20.0, 14.0), (2.0, 8.0, 9.0), 18.0),
                 (2508, (21.8, -19.8, 14.0), (2.0, 8.0, 9.0), 18.0)],
           dof=None, handheld=0.0, shake=[(2497, 0.25, 8)], subjects=both, framing="wide")
    C.shot("S21b", *CUT["S21b"],
           keys=[(2509, (1.55, 1.45, 0.90), (0.00, 2.20, 1.25), 35.0),
                 (2520, (1.53, 1.42, 0.90), (0.00, 2.20, 1.27), 35.0)],
           dof=dict(focus="SAINT_katana_tip", fstop=2.0), handheld=0.08, subjects=["saint"], framing="mcu")
    C.shot("S21c", *CUT["S21c"],
           keys=[(2521, (7.80, -0.30, 1.50), (0.00, 0.20, 4.00), 16.0),
                 (2592, (7.80, -0.30, 1.50), (0.00, 0.20, 4.00), 16.0)],
           dof=None, handheld=0.0, subjects=both, framing="wide")
    C.shot("S22a", *CUT["S22a"],
           keys=[(2593, (22.0, -17.0, 16.0), (0.0, 2.0, 1.0), 24.0),
                 (2622, (22.0, -17.0, 16.0), (0.0, 2.0, 1.0), 24.0)],
           dof=None, handheld=0.0, subjects=both, framing="wide")
    p = Vector(CONTACT.get(A["a2"], (0.22, 1.10, 1.10)))          # breakdown: lens 1.1 m from the contact
    cam, look = p + Vector((1.08, -0.35, -0.05)), p + Vector((-0.02, 0.02, 0.05))
    C.shot("S22c", *CUT["S22c"],
           keys=[(2623, tuple(cam), tuple(look), 65.0), (2643, tuple(cam), tuple(look), 65.0)],
           dof=dict(focus=tuple(p), fstop=2.8), handheld=0.15, subjects=[], framing="ecu")
    C.shot("S22d", *CUT["S22d"],
           keys=[(2644, (7.6, -1.6, 1.0), (0.0, 1.6, 3.6), 16.0),
                 (2664, (7.6, -1.6, 1.0), (0.0, 1.6, 3.6), 16.0)],
           dof=None, handheld=0.1, subjects=both, framing="wide")
    C.shot("S22e", *CUT["S22e"],
           keys=[(2665, (0.62, -0.55, 1.62), (-0.05, 1.30, 1.45), 45.0),
                 (2684, (0.62, -0.65, 1.62), (-0.05, 1.20, 1.45), 45.0)],
           dof=dict(focus=(SA, "head"), fstop=2.8), handheld=0.2, subjects=both, framing="ots")
    C.shot("S22f", *CUT["S22f"],
           keys=[(2685, (44.0, 1.0, 15.0), (0.0, 1.5, 2.0), 35.0),
                 (2705, (44.0, 1.0, 15.0), (0.0, 1.5, 2.0), 35.0)],
           dof=None, handheld=0.0, shake=[(2703, 0.2, 6)], subjects=both, framing="wide")
    # S22g: the face ECU aims at the evaluated head CENTRE (a (rig, 'head') target aims at the head bone's root =
    # the chin/neck: at 75 mm from 1.2 m the face sat above the frame), re-aimed every 3 frames as he steps in
    sc = bpy.context.scene
    # lens 30-35 deg off his facing (was 57: his left profile, the wind-up arm across the face)
    pos = {2706: (0.85, 1.50, 1.60), 2715: (0.80, 1.38, 1.60), 2723: (0.72, 1.25, 1.58), 2725: (0.72, 1.25, 1.58)}
    gk = []
    for f in (2706, 2709, 2712, 2715, 2718, 2721, 2723, 2725):
        sc.frame_set(f)
        pb = SA.pose.bones["head"]
        hc = SA.matrix_world @ ((pb.head + pb.tail) * 0.5)
        fr = sorted(pos)
        i = max(j for j in range(len(fr)) if fr[j] <= f)
        a, b = fr[i], fr[min(i + 1, len(fr) - 1)]
        t = 0.0 if b == a else (f - a) / (b - a)
        cp = tuple(pa + (pb_ - pa) * t for pa, pb_ in zip(pos[a], pos[b]))
        gk.append((f, cp, (hc.x, hc.y, hc.z + 0.02), 75.0))
    C.shot("S22g", *CUT["S22g"], keys=gk, dof=dict(focus=(SA, "head"), fstop=2.0), handheld=0.15,
           subjects=["saint"], framing="ecu")
    C.shot("S22h", *CUT["S22h"],                  # 20 m (not 30): at 30 m the pair was a few pixels (deviation)
           keys=[(2726, (4.6, 1.5, 20.0), (0.0, 1.5, 0.0), 35.0),
                 (2746, (4.6, 1.5, 20.0), (0.0, 1.5, 0.0), 35.0)],
           dof=None, handheld=0.0, subjects=both, framing="wide")
    C.shot("S22i", *CUT["S22i"],                  # pulled back to 1.9 m (deviation): his whole slanted guard + the
           keys=[(2747, (1.90, 1.00, 1.38), (0.0, 1.05, 1.30), 35.0),       # descending blade in one frame
                 (2766, (1.90, 1.00, 1.38), (0.0, 1.05, 1.30), 35.0)],
           dof=dict(focus=(0.0, 1.07, 1.31), fstop=4.0), handheld=0.15, subjects=[], framing="ecu")
    C.shot("S22j", *CUT["S22j"],
           keys=[(2767, (0.85, 1.35, 1.30), (SH, "head"), 50.0), (2784, (0.85, 1.35, 1.30), (SH, "head"), 50.0)],
           dof=dict(focus=(SH, "head"), fstop=2.0), handheld=0.1, subjects=["shinobi"], framing="ecu")
    C.shot("S22ba", *CUT["S22ba"],
           keys=[(2785, (8.2, 1.2, 1.45), (0.0, 1.7, 1.55), 24.0),
                 (2808, (8.2, 1.6, 1.45), (0.0, 2.0, 1.55), 24.0)],
           dof=None, handheld=0.1, subjects=both, framing="wide")
    C.shot("S22bb", *CUT["S22bb"],
           keys=[(2809, (1.00, 1.90, 1.45), (0.0, 2.55, 1.45), 60.0),
                 (2828, (1.00, 1.95, 1.45), (0.0, 2.60, 1.45), 60.0)],
           dof=dict(focus=(0.10, 2.40, 1.40), fstop=2.8), handheld=0.2, subjects=[], framing="insert")
    C.shot("S22bc", *CUT["S22bc"],
           keys=[(2829, (7.0, 1.4, 1.35), (0.0, 2.4, 1.60), 28.0),
                 (2852, (7.0, 1.9, 1.35), (0.0, 2.7, 1.60), 28.0)],
           dof=None, handheld=0.1, subjects=both, framing="wide")
    C.shot("S22bd", *CUT["S22bd"],
           keys=[(2853, (1.30, -1.50, 1.70), (-0.25, 4.0, 2.10), 35.0),
                 (2880, (1.30, -1.35, 1.70), (-0.25, 4.0, 2.15), 35.0)],
           dof=dict(focus=(SA, "head"), fstop=2.8), handheld=0.1, subjects=both, framing="ots")
    C.shot("S23a", *CUT["S23a"],
           keys=[(2881, (8.6, 1.2, 1.30), (0.0, 2.3, 1.85), 20.0),
                 (2925, (8.4, 1.3, 1.30), (0.0, 2.3, 1.85), 20.0)],
           dof=None, handheld=0.0, subjects=both, framing="wide")
    C.shot("S23b", *CUT["S23b"],
           keys=[(2926, (6.2, 1.6, 1.5), (0.0, 2.4, 1.35), 28.0),
                 (2952, (6.2, 1.6, 1.5), (0.0, 2.4, 1.35), 28.0)],
           dof=None, handheld=0.0, shake=[(2950, 0.7, 10)], subjects=both, framing="medium")
    C.shot("S23c", *CUT["S23c"],
           keys=[(2953, (9.0, -1.5, 5.0), (0.0, -1.8, 0.8), 18.0),
                 (2972, (9.0, -1.5, 5.0), (0.0, -1.8, 0.8), 18.0)],
           dof=None, handheld=0.0, shake=[(2962, 0.25, 6)], subjects=both, framing="wide")
    C.shot("S23d", *CUT["S23d"],                  # 1.3 m off the plane, 2.6 m up: over (not behind) his shoulder
           keys=[(2973, (1.3, 8.4, 2.6), (0.0, -6.0, 0.9), 45.0),
                 (3009, (1.3, 8.4, 2.6), (0.0, -6.0, 0.9), 45.0)],
           dof=dict(focus=(SH, "head"), fstop=4.0), handheld=0.0, subjects=both, framing="ots")
    C.shot("S23e", *CUT["S23e"],                  # elevated 3/4 two-shot (deviation): the kneel seen over the stubble
           keys=[(3010, (5.0, -5.0, 3.2), (0.0, -2.5, 0.9), 22.0),
                 (3072, (5.0, -5.0, 3.2), (0.0, -2.5, 0.9), 22.0)],
           dof=dict(focus=(SH, "head"), fstop=5.6), handheld=0.0, subjects=both, framing="wide")


# ---------------------------------------------------------------------------------------------- environment (§3, §4)
SUNS = {"S21a": (250.0, 38.0), "S21b": (300.0, 28.0), "S21c": (270.0, 30.0), "S22a": (330.0, 35.0),
        "S22c": (270.0, 25.0), "S22d": (270.0, 30.0), "S22e": (10.0, 25.0), "S22f": (270.0, 30.0),
        "S22g": (330.0, 20.0), "S22h": (250.0, 38.0), "S22i": (300.0, 30.0), "S22j": (190.0, 20.0),
        "S22ba": (270.0, 30.0), "S22bb": (300.0, 25.0), "S22bc": (270.0, 28.0), "S22bd": (10.0, 22.0),
        "S23a": (270.0, 28.0), "S23b": (270.0, 25.0), "S23c": (270.0, 30.0), "S23d": (190.0, 16.0),
        "S23e": (292.0, 24.0)}                # key light (az, el) per cut, keyed on the cut's first frame
WIND = [(2497, 2.2), (2521, 1.4), (2593, 1.8), (2785, 1.2), (2881, 1.0), (2953, 0.5)]


def _environment(ENV):
    """Key light per cut (always in front of the lens: rim/backlight on the rain), wind (steps on cuts), the S22
    strobe dim and its restore on the S22b cut (D9)."""
    for cut, f0, _ in CUTS:
        az, el = SUNS[cut]
        ENV.set_sun(f0, az, el)
    for i, (f, w) in enumerate(WIND):
        ENV.set_wind(f, w, direction_deg=config.WIND_DIR_DEFAULT if i == 0 else None, interp='CONSTANT')
    ENV.set_param(2593, "key_pow", 0.15)
    ENV.set_param(2593, "amb_str", 0.18)
    ENV.set_param(2593, "fill_pow", 0.04)
    ENV.set_state(2785, "storm_night")


def _effects(ENV, VFX):
    """Every vfx call of the lane + the seven flashes (§4), in frame order."""
    pine = _local_pine_top()
    # ---- S21a: the cut bolt forks to the pine (+ a short strike behind the elder), the pine splits and burns
    VFX.lightning_bolt(F_RAIKIRI, start=(-14.0, 34.0, 150.0), end=pine, branches=4, duration=4, seed=seed("S21a", 0),
                       fork_at=FORK_AT, fork_ends=[pine, (-2.20, 5.00, 0.0)], fork_delay=0, strength=120.0,
                       flash=True, flash_strength=0.7, light=True, light_energy=4.0e4, arch=0.34, guard="raise")
    VFX.tree_strike(F_RAIKIRI, pos=None, seed=seed("S21a", 1), split_deg=26.0, split_frames=16, flame=True,
                    flame_until=2592, steam_until=None, flash=True)
    ENV.flash(F_RAIKIRI, 0.80, 2, tint=(0.70, 0.80, 1.0), direction=(338.0, 76.0))
    VFX.sparks(F_RAIKIRI, STRUCK, direction=(0.0, 0.3, 1.0), count=40, speed=5.0, life=6, color="white", scale=1.0,
               seed=seed("S21a", 2), light=False)
    VFX.blade_trail("SAINT_katana_tip", "SAINT_katana_base", F_RAIKIRI, 2500, owner="saint", strength=1.2)
    # ---- S21b: the afterglow on the edge (D13), steam + drops flashing to vapour on the hot steel
    VFX.blade_afterglow("SAINT_katana_tip", "SAINT_katana_base", 2509, 2512, color="afterglow", strength=2.0,
                        strike_u=0.8)
    VFX.steam(2509, 2545, (0.00, 1.95, 1.10), 0.22, height=0.9, glow=False, density=0.35, rise=1.2,
              seed=seed("S21b", 0))
    for i, f in enumerate((2510, 2513, 2516, 2519)):
        VFX.sparks(f, (0.00, 1.90 + 0.05 * i, 1.08), direction=(0.0, 0.0, 1.0), count=6, speed=1.2, life=6,
                   color=(0.70, 0.75, 0.80), scale=0.3, seed=seed("S21b", 1 + i), light=False, core=False)
    # ---- S22: the strobe (flashes via the vfx budget registry, then aimed)
    _local_flash(ENV, VFX, 2605, 0.60, (344.0, 70.0),
                 bolt=dict(start=(-14.0, 40.0, 160.0), end=(-10.0, 34.0, 0.0), branches=3, duration=3,
                           seed=seed("S22a", 0), strength=90.0, light=None, guard="raise"))
    _local_flash(ENV, VFX, 2620, 0.50, (300.0, 55.0))
    _local_flash(ENV, VFX, 2662, 0.55, (250.0, 62.0),
                 bolt=dict(start=(-50.0, -20.0, 170.0), end=(-38.0, -14.0, 0.0), branches=3, duration=3,
                           seed=seed("S22d", 0), strength=90.0, light=None, guard="raise"))
    _local_flash(ENV, VFX, 2703, 0.65, (283.0, 60.0),
                 bolt=dict(start=(-70.0, 20.0, 160.0), end=(-52.0, 12.0, 0.0), branches=4, duration=4,
                           seed=seed("S22f", 0), strength=110.0, light=None, guard="raise"))
    _local_flash(ENV, VFX, 2744, 0.50, (200.0, 80.0))
    _local_flash(ENV, VFX, 2764, 0.45, (250.0, 45.0))
    for i, (a, b) in enumerate(((2614, 2621), (2635, 2642), (2656, 2663), (2677, 2683), (2697, 2704),
                                (2717, 2724), (2738, 2745), (2758, 2769))):
        VFX.blade_trail("SAINT_katana_tip", "SAINT_katana_base", a, b, owner="saint", name=f"A3_trail_saint_{i}")
    VFX.sparks(2664, (0.0, 0.02, 0.05), direction=(0.0, -1.0, 0.3), count=20, speed=2.0, life=10,
               color=(0.60, 0.65, 0.70), scale=0.4, seed=seed("S22d", 1), light=False, core=False)
    p0, p1 = Vector((0.11, 0.96, 1.50)), Vector((-0.22, 1.18, 1.12))
    for i, f in enumerate((2765, 2766, 2767)):
        VFX.sparks(f, tuple(p0.lerp(p1, (i + 1) / 3.0)), direction=(-0.6, 0.3, -0.7), count=25, speed=3.0,
                   life=8, color="steel", seed=seed("S22i", i), light=(i == 1))
    VFX.sparks(2776, "SHINOBI_katana_tip", direction=(0.0, 0.0, 1.0), count=12, speed=2.5, life=8,
               color=(0.65, 0.70, 0.75), scale=0.35, seed=seed("S22j", 0), light=False, core=False)
    # ---- S22b: the student's trails (cool white, red core); the faint arc of the jodan lift
    for i, (a, b) in enumerate(((2789, 2796), (2800, 2807), (2819, 2827))):
        VFX.blade_trail("SHINOBI_katana_tip", "SHINOBI_katana_base", a, b, owner="shinobi",
                        name=f"A3_trail_shinobi_{i}")
    VFX.blade_trail("SAINT_katana_tip", "SAINT_katana_base", 2850, 2866, owner="saint", strength=0.6,
                    name="A3_trail_saint_jodan")
    for f in (2870, 2875, 2879):
        VFX.sparks(f, "SAINT_katana_tip", direction=(0.0, 0.0, -1.0), count=5, speed=1.0, life=10,
                   color=(0.65, 0.70, 0.75), scale=0.3, seed=seed("S22bd", f), light=False, core=False)
    # ---- S23: the grounded cut - water and air only (no trail on the master's cut, no flash: D11)
    VFX.blade_trail("SHINOBI_katana_tip", "SHINOBI_katana_base", 2932, 2939, owner="shinobi",
                    name="A3_trail_shinobi_attack")
    VFX.spray_ring(CUT_FRAME, IMPACT, radius=4.0, seed=seed("S23b", 0))
    VFX.rain_split(CUT_FRAME, 3010, plane_origin=(0.00, 3.45, 0.00), plane_normal=(1.0, 0.0, 0.0), width=2.2,
                   length=22.0, height=12.0, direction=(0.0, -1.0, 0.0), seed=seed("S23b", 1), sheet=True,
                   mist=True)
    VFX.sparks(CUT_FRAME, (0.00, 1.75, 0.05), direction=(0.0, -0.3, 1.0), count=60, speed=5.0, life=12,
               color=(0.55, 0.50, 0.45), scale=1.2, seed=seed("S23b", 2), light=False, core=False)
    VFX.sparks(2962, (0.00, -2.60, 0.10), direction=(0.0, -0.8, 0.6), count=40, speed=3.0, life=14,
               color=(0.55, 0.60, 0.65), scale=0.8, seed=seed("S23c", 0), light=False, core=False)
    VFX.grass_burst(2962, (0.00, -2.60, 0.4), direction=(0.0, -0.6, 0.8), count=40, seed=seed("S23c", 1), fluff=0.1)
    VFX.sparks(2970, (0.00, -3.90, 0.10), direction=(0.0, -0.8, 0.6), count=20, speed=3.0, life=14,
               color=(0.55, 0.60, 0.65), scale=0.8, seed=seed("S23c", 2), light=False, core=False)
    VFX.grass_burst(2970, (0.00, -3.90, 0.4), direction=(0.0, -0.6, 0.8), count=20, seed=seed("S23c", 3), fluff=0.1)
    VFX.sparks(2990, (PLANT_TIP[0], PLANT_TIP[1], 0.05), direction=(0.0, 0.0, 1.0), count=10, speed=1.5, life=10,
               color=(0.55, 0.60, 0.65), scale=0.4, seed=seed("S23d", 1), light=False, core=False)
    VFX.sparks(2991, (0.00, -6.00, 0.10), direction=(0.0, -1.0, 0.4), count=25, speed=2.0, life=12,
               color=(0.55, 0.60, 0.65), scale=0.6, seed=seed("S23d", 0), light=False, core=False)


# ---------------------------------------------------------------------------------------------- events (§3, DIRECTION §8)
def _events():
    """Tagged story beats + the sounds the macros do not emit themselves (slash whooshes, steps, jumps, dodges and
    clashes come from moves; never duplicated here - R14)."""
    e = EV.emit
    # S21
    e(F_RAIKIRI, "raikiri", pos=FORK_AT, who="saint", strength=1.0, tags=["raikiri"])
    e(config.MUSIC_CUES["act3_start"], "music_cue", cue="act3_start")
    e(F_RAIKIRI, "music_cue", cue="raikiri")
    e(F_RAIKIRI, "lightning_strike", pos=FORK_AT, strength=1.0)
    e(F_RAIKIRI, "thunder", distance="near", strength=1.0, pos=(0.0, 2.4, 20.0))
    e(F_RAIKIRI, "whoosh", who="saint", weapon="katana", strength=0.9)
    e(2498, "electric_crackle", duration=5, pos=FORK_AT)
    e(2499, "tree_split", pos=(*config.PINE_POS, 6.0), strength=1.0, tags=["tree_split"])
    e(2500, "fire_burst", pos=(*config.PINE_POS, 5.0), strength=0.6)
    e(2509, "steam_hiss", pos=(0.0, 1.95, 1.1), strength=0.5, duration=30)
    e(2540, "thunder", distance="far", strength=0.5)
    e(2555, "wind_gust", strength=0.4)
    # S22 strobe: bolts + thunder (delays by distance)
    e(2605, "lightning_strike", pos=(-10.0, 34.0, 0.0), strength=0.8)
    e(2607, "thunder", distance="near", strength=0.8)
    e(2630, "thunder", distance="mid", strength=0.6)
    e(2662, "lightning_strike", pos=(-38.0, -14.0, 0.0), strength=0.8)
    e(2665, "thunder", distance="near", strength=0.8)
    e(2703, "lightning_strike", pos=(-52.0, 12.0, 0.0), strength=0.9)
    e(2707, "thunder", distance="near", strength=0.9)
    e(2752, "thunder", distance="mid", strength=0.6)
    e(2765, "blade_lock", duration=4, strength=0.6, pos=(-0.05, 1.07, 1.31))
    e(2770, "hit", pos=(-0.45, 1.30, 0.1), strength=0.4)
    e(2775, "whoosh", who="shinobi", weapon="katana", strength=0.4)
    e(2780, "thunder", distance="far", strength=0.5)
    # S22b
    e(2821, "dash", who="shinobi", strength=0.5)
    e(2852, "whoosh", who="saint", weapon="katana", strength=0.35)
    # S23
    e(2908, "thunder", distance="far", strength=0.4)
    e(2929, "dash", who="shinobi", strength=0.7)
    e(2933, "whoosh", who="shinobi", weapon="katana", strength=0.5)
    e(2941, "jump", who="shinobi", strength=0.6)
    e(2944, "whoosh", who="saint", weapon="katana", strength=1.0)
    e(2946, "land", who="saint", strength=1.0)  # the front-foot stamp (the bake emits the step)
    e(CUT_FRAME, "music_cue", cue="low_point")
    e(CUT_FRAME, "shockwave", pos=(0.00, 1.75, 0.3), strength=1.0, tags=["low_point"])
    e(CUT_FRAME, "rain_split", pos=(0.00, 1.75, 1.5), strength=1.0, tags=["low_point"])
    e(CUT_FRAME, "hit", pos=IMPACT, strength=1.0)
    e(2951, "hit", who="shinobi", strength=0.8, pos=(0.0, 1.05, 1.2))
    e(2962, "body_fall", who="shinobi", strength=0.9, pos=(0.0, -2.6, 0.2))
    e(2963, "roll", who="shinobi", strength=0.6)
    e(2980, "skid", who="shinobi", duration=11, strength=0.6)
    e(2985, "steam_hiss", pos=(0.0, -9.5, 1.0), strength=0.3, duration=24)
    e(2991, "kneel", who="shinobi", strength=0.6)
    e(2991, "land", who="shinobi", strength=0.35, pos=(PLANT_TIP[0], PLANT_TIP[1], 0.0))
    e(3001, "heartbeat", bpm=52, duration=71, strength=0.5, tags=["low_point"])


# ---------------------------------------------------------------------------------------------- entry point
def build(ctx):
    """Lane entry (acts contract): keys only inside SPAN (+- handles), cameras through cameras.shot, events through
    events.emit; clashes are resolved by lane_tools.end_lane."""
    CH, ENV, M, PZ, VFX = _mods()
    SH, SA = ctx["chars"]["shinobi"], ctx["chars"]["saint"]
    _register_local_poses(PZ)
    made = _local_upstream_standins(ENV, VFX)
    if made:
        print(f"[act3] partial build: upstream stand-ins {made}")
    _entering_state(CH, SH, SA)
    _s21(CH, M, SH, SA)
    _s22(CH, M, SH, SA)
    _s22b(CH, M, SH, SA)
    _s23(CH, M, SH, SA)
    for f in FLASHES[1:]:                     # the strobe tableaux: bodies frozen for the 2 lit frames (§3 S22)
        _local_hold(SH, f)
        _local_hold(SA, f)
    _environment(ENV)
    _effects(ENV, VFX)
    _events()
    _cameras(SH, SA)
    obs = set()
    for r in (SH, SA):
        obs.update(_local_hold_ids(r))
    for ob in obs:
        U.freeze_handles(ob, SPAN)
