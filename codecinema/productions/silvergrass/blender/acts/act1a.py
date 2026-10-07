"""
acts/act1a.py - lane act1a: S05-S09, frames 433-936.
Act I "Blade", dusk_gold, 92-BPM grid from 631; shared timing and staging are defined in config.py.

    Blender -b --factory-startup --python-exit-code 1 --python codecinema/productions/silvergrass/blender/build_scene.py -- --lanes act1a \
        --quality preview

Story: the student draws and closes the distance; the master's thumb frees his blade (click 566); a dash you never
see the start of; the first clash (595) hangs in slow motion (595-630); the master tests him ONE-HANDED (cut 709,
cut 725, thrust 756 - sidestepped); the student answers twice (850 parried, 866 evaded) and the master gives ground.
Enters from HANDOFF[432], leaves at HANDOFF[936].

13 sub-cuts (all hard cuts, every camera on the +X side of the Y action line):
    S05 433-540  S06 541-588  S07a 589-600  S07b 601-630  S07c 631-672  S08a 673-711  S08b 712-727
    S08c 728-758  S08d 759-800  S08e 801-840  S09a 841-852  S09b 853-868  S09c 869-936
"""

import math
import zlib

import bpy
from mathutils import Matrix, Vector

import config
import bl_util as U
import cameras as C
import events as EV
from acts import sub_cuts

LANE = "act1a"
SPAN = tuple(config.lane_span(LANE))                     # (433, 936)
H0 = config.HANDOFF[SPAN[0] - 1]                         # HANDOFF[432]
H1 = config.HANDOFF[SPAN[1]]                             # HANDOFF[936]

# config shots split at the sub-cut starts: S05 433-540, S06 541-588, S07a 589-600, S07b 601-630, S07c 631-672,
# S08a 673-711, S08b 712-727, S08c 728-758, S08d 759-800, S08e 801-840, S09a 841-852, S09b 853-868, S09c 869-936
CUTS = sub_cuts(LANE, {"S07": (601, 631), "S08": (712, 728, 759, 801), "S09": (853, 869)})
CUT = {c: (a, b) for c, a, b in CUTS}
S07_SLOWMO = config.slowmo_window(config.MUSIC_CUES["first_clash"])        # (595, 630): the grind

# key moments (film frames)
F = dict(
    sh_draw=466,          # kissaki clears the koiguchi (hand to hilt 455, swap 460, chudan 474)
    sa_crouch=(486, 516),
    suriashi=(525, 580),
    click=566,
    dash=CUT["S07a"][0], first_clash=config.MUSIC_CUES["first_clash"], slow_end=S07_SLOWMO[1],   # 589, 595, 630
    release=config.MUSIC_CUES["act1_bar1"],                                                        # 631 (bar 1)
    hit1=709, hit2=725, thrust=756, tableau_end=772,
    counter1=850, counter2=866,
)
S05_AXIS = dict(x=52.0, z=2.10, pitch_deg=1.45, lens=135.0)     # the reusable telephoto profile (S24a / S25)

# clash contact points (world) - breakdown "Blade geometry summary"
P595 = Vector((0.30, -1.98, 1.38))
P595_END = Vector((0.33, -1.86, 1.47))                   # the grind slides the contact up the student's blade
P709 = Vector((-0.22, -2.45, 1.52))
P725 = Vector((0.30, -2.55, 1.28))
P850 = Vector((0.26, -1.35, 1.52))


def _crc(tag):
    """Deterministic seed (zlib.crc32, never hash())."""
    return zlib.crc32(tag.encode()) & 0x7FFFFFFF


def _grind_point(f):
    """Contact point of the S07b grind at film frame f (595 -> 630)."""
    t = min(1.0, max(0.0, (f - F["first_clash"]) / (F["slow_end"] - F["first_clash"])))
    return P595.lerp(P595_END, t)


# =============================================================================================================
# small local helpers
# =============================================================================================================
def _xy(M, rig, f):
    x, y, _, _ = M.root_at(rig, f)
    return (x, y)


def _blade_matrix(CH, rig, f, point, dist, direction, edge=None):
    """Rig-space controller matrix that puts the in-hand katana through world `point` at `dist` m from the right
    fist, pointing along world `direction` (edge toward `edge`, default down)."""
    d = Vector(direction).normalized()
    grip = Vector(point) - d * dist
    return CH.sword_ctrl_matrix(rig, grip, d, edge, 'WORLD', f)


def _key_blade(CH, M, rig, f, point, dist, direction, edge=None, interp='BEZIER'):
    """Key the sword controller so the blade passes through `point` (see _blade_matrix); arm IK on."""
    Mx = _blade_matrix(CH, rig, f, point, dist, direction, edge)
    M.key_ctrl(rig, f, Mx, interp=interp)
    return Mx


def _pitch_up(direction, deg):
    """Tilt a world direction up by `deg` degrees (about the horizontal axis perpendicular to it)."""
    d = Vector(direction).normalized()
    side = d.cross(Vector((0.0, 0.0, 1.0)))
    if side.length < 1e-6:
        return d
    return (Matrix.Rotation(math.radians(deg), 3, side.normalized()) @ d).normalized()   # + about d x Z = up


def _edge_of(M, rig, f):
    """World edge direction (-Z of the controller) of the keyed sword controller at f."""
    import poses as PZ
    Mw = M.rig_matrix(rig, f) @ PZ.current_ctrl_matrix(rig, f)
    return tuple(-(Mw.to_3x3() @ Vector((0.0, 0.0, 1.0))))


def _grip_matrix(CH, M, rig, f, grip, direction, edge=None):
    """Rig-space controller matrix: right fist at world `grip`, blade along world `direction`; edge = the macro's
    keyed edge at f (orthogonalised) unless given - keeps the wrist roll the pose tuning chose."""
    e = edge if edge is not None else _edge_of(M, rig, f)
    return CH.sword_ctrl_matrix(rig, Vector(grip), Vector(direction).normalized(), e, 'WORLD', f)


def _retarget_strike(CH, M, rig, f, grip, direction, t_in, t_out, edge=None, hold=None, bounce=None):
    """Re-aim a macro strike so the blade follows the requested line at the impact frame f:
    the controller arcs from the macro's windup (story f - t_in) into the target
    at f, then out to the macro's follow pose (f + t_out) - or holds the target to `hold` (film frame) when given.
    Returns the target matrix (rig space)."""
    import poses as PZ
    T = M.clock(f)
    fa, fb = T(-t_in), T(t_out)
    A = PZ.current_ctrl_matrix(rig, fa)
    E = PZ.current_ctrl_matrix(rig, fb)
    B = _grip_matrix(CH, M, rig, f, grip, direction, edge)
    ctrl = PZ._ctrl_obj(rig)
    U.delete_keys(ctrl, (fa + 0.01, (hold if hold else fb) - 0.01))
    M.swing(rig, fa, f, A, B, ease="in_quad", clk=T)
    if hold:
        C_ = B.copy()
        M.key_ctrl(rig, hold, C_)
    elif bounce:
        # the cut is stopped dead by a parry: the blade rebounds (back along itself + up) instead of following
        # through - `bounce` = (back_m, up_m, pitch_up_deg), reached at f + t_out
        back, up, pitch = bounce
        Rw = M.rig_matrix(rig, f).to_3x3()
        d_w = (Rw @ B.to_3x3() @ Vector((0.0, 1.0, 0.0))).normalized()
        R = _grip_matrix(CH, M, rig, f, Vector(grip) - d_w * back + Vector((0.0, 0.0, up)),
                         _pitch_up(d_w, pitch), edge)
        M.swing(rig, f, fb, B, R, ease="out_cubic", clk=T, include_start=False)
    else:
        M.swing(rig, f, fb, B, E, ease="out_cubic", clk=T, include_start=False)
    return B


def _retarget_block(CH, M, rig, f, grip, direction, blow, recoil=1.0, edge=None):
    """Re-aim a macro deflect: the block is on the breakdown's line at f-1 (4 cm short) and f, then recoils
    7 cm x recoil along the blow (world direction) and 3 cm down two frames later (the macro's recovery stays)."""
    T = M.clock(f)
    B = _grip_matrix(CH, M, rig, f, grip, direction, edge)
    b = Vector(blow).normalized()
    Rinv = M.rig_matrix(rig, f).to_3x3().inverted()
    M.key_ctrl(rig, T(-1), Matrix.Translation(Rinv @ (-b * 0.04)) @ B)
    M.key_ctrl(rig, f, B)
    M.key_ctrl(rig, T(2), Matrix.Translation(Rinv @ (b * 0.07 * recoil + Vector((0.0, 0.0, -0.03)))) @ B)
    return B


def _local_root_path(M, rig, f0, f1, p1, ease="inout_quad"):
    """Root glide from wherever the rig is at f0 to p1 at f1 (per-frame LINEAR keys, facing kept), replacing any
    root keys a macro left inside (f0, f1).  Work-around for a moves.py bug: root_path() normalises
    clk.span(f) / clk.span(f1) without subtracting clk.span(f0), and slash(lunge=)/dodge()/stagger() pass a clock
    anchored at the IMPACT frame - the whole lunge / sidestep then happens in the single frame after the impact."""
    x, y, _, a = M.root_at(rig, f0)
    U.delete_keys(rig, (f0 + 0.01, f1 + 1.5), 'location')
    U.delete_keys(rig, (f0 + 0.01, f1 + 1.5), 'rotation_euler')
    M.root(rig, f0, (x, y), a, interp='LINEAR')
    return M.root_path(rig, f0, f1, (x, y), p1, ease=ease)


def _local_raise_guard(M, rig, f0, f1, pitch, lift):
    """Tilt every sword-controller key in [f0, f1] up by `pitch` degrees about the fist and lift it `lift` m (rig
    space; the facing is constant there).  S05: the student's chudan becomes a high seigan - at the telephoto's
    grass line (1.05-1.26 m) the plain chudan blade (tip 1.32 m) vanished into the grass."""
    import poses as PZ
    ctrl = PZ._ctrl_obj(rig)
    frames = sorted({round(k.co.x, 3) for fc in U.fcurves_of(ctrl) for k in fc.keyframe_points
                     if f0 - 1e-3 <= k.co.x <= f1 + 1e-3})
    new = {}
    for f in frames:
        Mr = PZ.current_ctrl_matrix(rig, f)
        d = (Mr.to_3x3() @ Vector((0.0, 1.0, 0.0))).normalized()
        side = d.cross(Vector((0.0, 0.0, 1.0)))
        if side.length < 1e-6:
            continue
        R = Matrix.Rotation(math.radians(pitch), 4, side.normalized())
        new[f] = Matrix.Translation(Mr.translation + Vector((0.0, 0.0, lift))) @ R @ Mr.to_3x3().to_4x4()
    for f, Mx in new.items():
        M.key_ctrl(rig, f, Mx)
    return len(new)


def _delete_rig_keys(rig, ctrl, f0, f1):
    """Remove body (pose bones incl. hips offset) and sword-controller keys of a rig in [f0, f1] - used where a macro's
    follow-through / recovery has to be replaced by this lane's own keys (the S07 grind)."""
    n = U.delete_keys(rig, (f0, f1), 'pose.bones')
    n += U.delete_keys(ctrl, (f0, f1))
    return n


# =============================================================================================================
# choreography
# =============================================================================================================
def _entering_state(SH, SA, CH, M):
    """HANDOFF[432] re-asserted at 433 (lane isolation: the first key of a state channel extrapolates backwards)."""
    f0 = SPAN[0]
    for r in (SH, SA):
        CH.set_weapon_state(r, f0, "sheathed")
        CH.set_arm_mode(r, f0, "fk")
    CH.set_weapon_state(SA, f0, "slung")
    CH.set_left_hand(SH, f0, "free")
    CH.set_left_hand(SA, f0, "saya")
    CH.set_hat(f0, "on")
    CH.set_costume(f0, haori=True)
    CH.set_beard_cord(f0, False)
    CH.set_kunai_in_hand(f0, False)
    for i in (1, 2, 3):
        ob = bpy.data.objects.get(f"SHINOBI_kunai_{i}")
        if ob is not None:
            U.key_visible(ob, f0, False)
    CH.set_spear_grip(f0, 0.35, 0.95)
    sh, sa = H0["shinobi"], H0["saint"]
    M.root(SH, f0, sh["pos"], float(sh["facing"]))
    M.root(SA, f0, sa["pos"], float(sa["facing"]))
    M.stance(SH, f0, "relaxed")
    M.stance(SA, f0, "relaxed_saya")


def _s05_s06(SH, SA, CH, M):
    """S05 the stand-off (the student draws, the master sinks into iai) + S06 the koiguchi click (566)."""
    # ---- shinobi: still -> draw (hand on hilt 455, kissaki clears 466, chudan 474) -> suriashi 525-580
    M.stance(SH, 449, "relaxed")
    M.draw_sword(SH, F["sh_draw"], end="chudan")                   # two-handed from here to 936
    M.stance(SH, 480, "chudan", hands="keep", breathe=40)
    M.walk(SH, F["suriashi"][0], F["suriashi"][1], H0["shinobi"]["pos"], (0.0, -3.40), facing=180.0,
           upper="chudan", stride=0.36, lead="R", body_weight=0.4)
    M.stance(SH, 588, "chudan", hands="keep")
    _local_raise_guard(M, SH, 479, 562, pitch=14.0, lift=0.05)      # S05 seigan: the blade reads above the grass
    # ---- elder: upright, left hand on the saya -> iai crouch 486-516, frozen to 588
    M.stance(SA, F["sa_crouch"][0], "relaxed_saya")
    M.stance(SA, F["sa_crouch"][1], "iai_crouch")
    M.stance(SA, 540, "iai_crouch")
    M.stance(SA, 559, "iai_crouch")
    # ---- S06: the left thumb pushes the tsuba 4 cm off the koiguchi (560-566), 1 mm recoil, held to 588.
    ks = bpy.data.objects["SAINT_katana_sheathed"]
    ctrl = bpy.data.objects["SAINT_sword_ctrl"]
    y_rest = ks.location.y
    W = U.world_matrix_of(ks, 560)
    out_w = -(W.to_3x3() @ Vector((0.0, 1.0, 0.0))).normalized()          # toward the hilt (out of the saya)
    Rinv = U.world_matrix_of(SA, 560).to_3x3().inverted()
    import poses as PZ
    M0 = PZ.current_ctrl_matrix(SA, 560)
    for f, d in ((559, 0.0), (560, 0.0), (562, 0.004), (564, 0.014), (565, 0.028), (566, 0.040), (567, 0.041),
                 (568, 0.040), (586, 0.040), (588, 0.040)):
        U.key(ks, "location", f, value=y_rest - d, index=1, interp='BEZIER' if f < 568 else 'CONSTANT')
        # the right fist rests on the tsuka: it rides out with the hilt
        CH.key_ctrl_matrix(ctrl, f, Matrix.Translation(Rinv @ (out_w * d)) @ M0,
                           'BEZIER' if f < 568 else 'CONSTANT')
    U.key(ks, "location", 589, value=y_rest, index=1, interp='CONSTANT')     # hidden from 589 (drawn)
    M.overlay(SA, 580, {"hand.R": (4.0, 0.0, 0.0)})                         # sa_grip_close
    M.overlay(SA, 588, {"hand.R": (4.0, 0.0, 0.0)})
    return M0, out_w, Rinv


def _s07(SH, SA, CH, M):
    """S07a the dash + FIRST CLASH 595, S07b the slow-motion grind 595-630, S07c release on 631 + reset to 672."""
    import poses as PZ
    # ---------------- roots: 588 CONSTANT (the ellipsis cut), 589 mid-dash / cheated
    M.root(SA, 588, H0["saint"]["pos"], 0.0, interp='CONSTANT')
    M.root(SA, 589, (0.0, 1.25), 0.0, interp='LINEAR')
    M.root_path(SA, 589, 595, (0.0, 1.25), (0.0, -0.55), ease="out_quad")
    M.root(SH, 588, (0.0, -3.40), 180.0, interp='CONSTANT')
    M.root(SH, 589, (0.0, -3.30), 180.0, interp='LINEAR')
    # ---------------- elder: the quick-draw you don't see (local iai: blade 28 cm out at 589, clears 591, cut 595)
    M.hold(SA, 586)
    M.pose(SA, 588, "iai_crouch", ctrl=False)            # feet pinned in the crouch up to the cut
    M.pose(SH, 588, "chudan", ctrl=False)
    CH.set_weapon_state(SA, 589, "drawn")
    M.pose(SA, 589, "iai_draw_1")
    M.overlay(SA, 589, {"spine": (8.0, 0.0, 0.0), "chest": (6.0, 0.0, 0.0)})    # pitched into the dash
    M.pose(SA, 591, "iai_draw_2")
    CH.release_elbow(SA, 592, "R")
    d_sa = Vector((0.23, -0.97, 0.06)).normalized()
    B595 = _blade_matrix(CH, SA, 595, P595, 0.70, d_sa, edge=(-1.0, 0.0, -0.25))
    T = M.clock(595)
    M.swing(SA, 591, 595, PZ.current_ctrl_matrix(SA, 591), B595, ease="in_quad", clk=T)
    M.pose(SA, 595, "iai_cut", ctrl=False, lag={"hips": -1, "head": 1})
    M.emit(591, "draw", who="saint", weapon="katana", tags=["iai"])
    M.emit(594, "whoosh", who="saint", weapon="katana", strength=1.0, target=(SA, "hand.R"))
    # ---------------- shinobi: one lunge step in (592) and a forward-angled receiving block (uke-nagashi)
    M.step(SH, 589, 594, (0.0, -2.75), facing=180.0)
    M.hold(SH, 590)
    M.pose(SH, 594, "deflect_mid_R", lag={"head": 1}, ctrl=False)
    M.pose(SH, 595, "deflect_mid_R", feet=False, ctrl=False)
    d_sh = Vector((0.18, 0.79, 0.59)).normalized()
    _key_blade(CH, M, SH, 594, P595 - Vector((0.03, 0.10, 0.0)), 0.44, d_sh, edge=(1.0, 0.0, 0.2))
    _key_blade(CH, M, SH, 595, P595, 0.44, d_sh, edge=(1.0, 0.0, 0.2))
    # ---------------- S07b grind (slow motion, fx 0.25): the master's blade rides up the angled block
    M.root_path(SA, 595, 630, (0.0, -0.55), (0.0, -0.60), ease="out_quad")
    M.root_path(SH, 595, 630, (0.0, -2.75), (0.0, -2.80), ease="out_quad")
    for f in (601, 615, 630):
        t = (f - F["first_clash"]) / (F["slow_end"] - F["first_clash"])
        P = _grind_point(f)
        _key_blade(CH, M, SA, f, P, 0.70 - 0.08 * t, _pitch_up(d_sa, 8.0 * t), edge=(-1.0, 0.0, -0.25))
        _key_blade(CH, M, SH, f, P, 0.44 + 0.15 * t, d_sh, edge=(1.0, 0.0, 0.2))
        M.pose(SA, f, "iai_cut", ctrl=False, feet=False)
        M.pose(SH, f, "deflect_mid_R", ctrl=False, feet=False)
    M.overlay(SH, 630, {"shin.L": (3.0, 0.0, 0.0), "shin.R": (3.0, 0.0, 0.0), "chest": (-2.0, 0.0, 0.0)})
    M.overlay(SA, 630, {"chest": (3.0, 0.0, 0.0)})
    # ---------------- S07c: 631 the blades spring apart (bar 1)
    M.root(SA, 631, (0.0, -0.60), 0.0, interp='LINEAR')
    M.swing(SA, 630, 636, PZ.current_ctrl_matrix(SA, 630), "diag_down_R_windup", ease="out_cubic")
    M.pose(SA, 636, "diag_down_R_windup", ctrl=False, weight=0.7)
    M.pose(SA, 648, "low_1h")
    M.step(SA, 650, 662, (0.0, -0.30), facing=0.0)
    M.stance(SA, 672, "low_1h", hands="keep")
    M.skid(SH, 631, 645, (0.0, -2.80), (0.0, -3.40), sword_drag=False, recover=6)
    M.stance(SH, 651, "chudan", hands="keep")
    M.step(SH, 652, 660, (0.0, -3.35), facing=180.0)
    M.stance(SH, 672, "chudan", hands="keep")
    # the first clash (heavy) + the grind contacts (gate checked, no extra clash events; sparks = the stream)
    M.clash(SA, SH, 595, point=tuple(P595), strength=1.0, kind="clash_heavy", tags=["first_clash"], place=False,
            sparks=dict(count=120, speed=4.5, life=14, scale=1.6, color="gold", light_energy=20.0, direction=(-0.35, 0.25, 0.90),
                        spread=70))
    for f in (601, 615, 630):
        M.clash(SA, SH, f, point=tuple(_grind_point(f)), strength=0.3, place=False, emit_event=False,
                falloff=1, sparks=dict(count=14, speed=3.0, life=8, scale=0.7, color="gold",
                                       direction=(-0.2, 0.55, 0.8), light=False))


def _s08(SH, SA, CH, M):
    """S08: the master's test on the grid - steps in (678, 694), cut 709 (deflected high-left), rising cut 725
    (deflected right), thrust 756 (sidestepped), tableau to 772, withdrawal; the student steps in on 803/819."""
    # ---- S08a: two steps in on beats 3, 4; the student eases forward
    M.walk(SA, 672, 694, (0.0, -0.30), (0.0, -1.00), facing=0.0, upper="low_1h", stride=0.33, lead="R",
           body_weight=0.6)
    M.step(SH, 680, 694, (0.0, -3.28), facing=180.0)
    # hit 1 - diagonal down from his right shoulder, one-handed (left hand stays on the saya)
    M.slash(SA, F["hit1"], "diag_down_R", recover=3)
    _local_root_path(M, SA, 704, F["hit1"], (0.0, -1.05))          # the step into the cut (705-709)
    M.deflect(SH, F["hit1"], "high", recover=6)
    _retarget_strike(CH, M, SA, F["hit1"], (-0.30, -1.85, 1.65), (0.13, -0.97, -0.21), t_in=2.7, t_out=4)
    _retarget_block(CH, M, SH, F["hit1"], (-0.05, -2.85, 1.25), (-0.33, 0.78, 0.53), blow=(0.4, -0.6, -0.6))
    M.clash(SA, SH, F["hit1"], point=tuple(P709), strength=0.75,
            sparks=dict(count=60, scale=1.0, color="gold", direction=(0.55, -0.35, 0.35), spread=60, light_energy=12.0))
    # the student gives ground after the parry (re-plant 715)
    M.step(SH, 711, 718, (0.0, -3.40), facing=180.0)
    # ---- S08b: hit 2 - rising cut from his low left, deflected on the student's right
    M.slash(SA, F["hit2"], "rising_L", recover=5)
    _local_root_path(M, SA, 718, F["hit2"], (0.0, -1.20))          # drives in behind the rising cut
    M.deflect(SH, F["hit2"], "mid_R", recoil=1.2, recover=6)
    _retarget_strike(CH, M, SA, F["hit2"], (0.18, -1.85, 1.05), (0.16, -0.94, 0.31), t_in=2.7, t_out=4)
    _retarget_block(CH, M, SH, F["hit2"], (0.15, -2.95, 1.10), (0.33, 0.87, 0.39), blow=(-0.5, -0.4, 0.7),
                    recoil=1.2)
    M.clash(SA, SH, F["hit2"], point=tuple(P725), strength=0.85,
            sparks=dict(count=70, scale=1.1, color="gold", direction=(0.6, 0.1, 0.5), light_energy=12.0))
    # ---- S08c: the thrust chambered on beat 7 (741), held, lunge 746-756; the student sidesteps to his left
    M.pose(SA, 741, "thrust_windup", weight=0.9)
    M.pose(SA, 746, "thrust_windup", weight=0.95)
    M.slash(SA, F["thrust"], "thrust", follow=2, recover=34, hold_frames=0.5)
    _local_root_path(M, SA, 749, F["thrust"], (0.0, -1.80), ease="inout_quad")   # the lunge, 0.60 m
    M.pose(SA, 772, "thrust_follow")                   # the tableau: held at full extension to 772
    B = _retarget_strike(CH, M, SA, F["thrust"], (0.0, -2.61, 1.34), (0.02, -1.0, -0.02), t_in=2.7, t_out=2,
                         hold=772)
    M.swing(SA, 772, 792, B, "low_1h", ease="inout_quad")
    M.dodge(SH, F["thrust"] - 1, "left", dist=0.65, recover=14)
    _local_root_path(M, SH, 750, F["thrust"], (-0.65, -3.45), ease="out_cubic")   # out of the line before the tip
    M.pose(SH, 766, "dodge_side", feet=False)             # frozen beside the blade until the tableau breaks
    # ---- S08d: withdrawal (772-790), the student slides back onto the line (lateral cross-steps, facing kept)
    M.step(SA, 776, 790, (0.0, -1.60), facing=0.0)
    M.step(SH, 776, 786, (-0.10, -3.42), facing=180.0)
    M.step(SH, 788, 798, (0.30, -3.40), facing=180.0)
    M.stance(SH, 800, "chudan", hands="keep")
    # ---- S08e: the master gives room (803, 819, 832) while the student steps in (805, 821) and re-grips (834)
    M.step(SA, 795, 803, (0.0, -1.20), facing=0.0)
    M.step(SA, 811, 819, (0.0, -0.75), facing=0.0)
    M.step(SA, 826, 832, (0.0, -0.50), facing=0.0)
    M.step(SA, 835, 840, (0.0, -0.45), facing=0.0)
    M.stance(SA, 840, "low_1h", hands="keep")
    M.step(SH, 803, 812, (0.30, -3.22), facing=180.0)
    M.step(SH, 819, 828, (0.30, -3.05), facing=180.0)
    M.stance(SH, 830, "chudan", hands="keep")
    M.overlay(SH, 834, {"chest": (-2.0, 0.0, 0.0), "shoulder.L": (0.0, 0.0, -3.0), "shoulder.R": (0.0, 0.0, 3.0)})
    M.shift_ctrl(SH, 834, (0.0, 0.0, -0.025))           # sh_regrip: the tip dips and comes back
    M.stance(SH, 838, "chudan", hands="keep")
    M.step(SH, 834, 840, (0.30, -3.00), facing=180.0)


def _s09(SH, SA, CH, M):
    """S09: the student's two-beat answer - counter 1 parried (850), counter 2 evaded (866) - then the reset to
    HANDOFF[936]."""
    # ---- S09a: launch on the half beat (842), diagonal cut at the elder's left shoulder, parried one-handed
    M.slash(SH, F["counter1"], "diag_down_R", follow=2, recover=2, recover_to="rising_L_windup")
    M.step(SH, 842, F["counter1"], (0.30, -2.40), facing=180.0)     # the launch on the half beat, 0.60 m
    M.deflect(SA, F["counter1"], "mid_L", recoil=0.8, recover=4)
    _retarget_strike(CH, M, SH, F["counter1"], (0.42, -1.92, 1.66), (-0.26, 0.93, -0.23), t_in=3, t_out=2,
                     bounce=(0.07, 0.05, 12.0))
    _retarget_block(CH, M, SA, F["counter1"], (0.15, -0.88, 1.15), (0.18, -0.77, 0.61), blow=(-0.5, 0.5, -0.7),
                    recoil=0.8)
    M.clash(SH, SA, F["counter1"], point=tuple(P850), strength=0.7,
            sparks=dict(count=60, scale=1.0, color="white", direction=(0.5, 0.3, 0.6), light_energy=6.0))
    # ---- S09b: the blade comes round the other way; the master half-steps, sways back and gives ground
    M.step(SA, 853, 858, (0.0, -0.25), facing=0.0)
    # counter 2 as a RISING cut (gyaku kiriage) instead of a flat horizontal_L: from S09b's 3/4-rear camera the flat
    # sweep was seen edge-on and read as a poke; the rising diagonal passes the master's chin/beard as he sways back.
    M.slash(SH, F["counter2"], "rising_L", recover=10)
    M.step(SH, 853, 858, (0.30, -2.30), facing=180.0)
    M.step(SH, 859, F["counter2"], (0.30, -1.60), facing=180.0)     # the deep step in behind the sweep
    _retarget_strike(CH, M, SH, F["counter2"], (0.22, -0.96, 1.22), (-0.18, 0.70, 0.36), t_in=4, t_out=5)
    M.dodge(SA, F["counter2"], "back", dist=0.25, recover=4)
    _local_root_path(M, SA, 860, F["counter2"], (0.0, 0.0), ease="out_cubic")     # sways back and steps
    M.overlay(SA, 866, {"spine": (-6.0, 0.0, 0.0), "chest": (-4.0, 0.0, 0.0)})
    U.delete_keys(bpy.data.objects["SAINT_sword_ctrl"], (860.5, 869.5))
    for f in (860, 863, 866, 869):                  # his blade stays low, out of the sweep's path (no stray contact)
        M.key_ctrl(SA, f, "low_1h")
    # ---- S09c: the glide back, measured steps on beats 17 / 18, settle on 19; the student eases back
    M.step(SA, 867, 876, (0.0, 0.70), facing=0.0)
    M.step(SA, 884, 897, (0.0, 1.75), facing=0.0)
    M.step(SA, 903, 913, (0.0, 2.40), facing=0.0)
    M.step(SA, 920, 928, H1["saint"]["pos"], facing=0.0)
    M.stance(SA, 930, "low_1h", hands="keep")
    M.stance(SA, 936, "low_1h", hands="keep")
    M.step(SH, 882, 890, (0.30, -1.70), facing=180.0)
    M.step(SH, 897, 905, H1["shinobi"]["pos"], facing=180.0)
    M.stance(SH, 906, "chudan", hands="keep", breathe=24)
    M.stance(SH, 936, "chudan", hands="keep")
    # handoff: both roots CONSTANT from 930 (clean last frame)
    M.root(SA, 930, H1["saint"]["pos"], float(H1["saint"]["facing"]), interp='CONSTANT')
    M.root(SA, 936, H1["saint"]["pos"], float(H1["saint"]["facing"]), interp='CONSTANT')
    M.root(SH, 930, H1["shinobi"]["pos"], float(H1["shinobi"]["facing"]), interp='CONSTANT')
    M.root(SH, 936, H1["shinobi"]["pos"], float(H1["shinobi"]["facing"]), interp='CONSTANT')


def choreograph(SH, SA):
    import characters as CH
    import moves as M
    _entering_state(SH, SA, CH, M)
    _s05_s06(SH, SA, CH, M)
    _s07(SH, SA, CH, M)
    _s08(SH, SA, CH, M)
    _s09(SH, SA, CH, M)
    # cut rule (Pipeline rule 2): the ellipsis jump 588 -> 589 must not smear
    for r in (SH, SA):
        U.set_key_interp_at(r, 588, 'CONSTANT', 'location')


# =============================================================================================================
# environment: dusk_gold for the whole lane, per-cut sun cheats, wind, grass clearance
# =============================================================================================================
SUN = {   # cut -> (azimuth, elevation, disk_deg)   (disk 1.95 deg = D4 in S05)
    "S05": (270.0, 0.37, 1.95), "S06": (262.0, 2.0, 2.2), "S07a": (270.0, 1.0, 2.2), "S07b": (262.0, 1.5, 2.2),
    "S07c": (270.0, 1.5, 2.2), "S08a": (250.0, 3.0, 2.2), "S08b": (285.0, 2.0, 2.2), "S08c": (290.0, 3.0, 2.2),
    "S08d": (270.0, 1.5, 2.2), "S08e": (270.0, 1.5, 2.2), "S09a": (290.0, 3.0, 2.2), "S09b": (290.0, 3.0, 2.2),
    "S09c": (270.0, 1.2, 2.2),
}
CLEAR = {  # cut -> camera grass clearance (near, far); default config.GRASS_CAMERA_CLEAR (1.5, 4.0)
    "S07b": (1.0, 2.0), "S08c": (1.6, 3.0), "S08e": (1.0, 2.0), "S09a": (1.0, 2.2), "S09b": (1.0, 2.2),
}


def environment_timeline():
    import environment as ENV
    ENV.set_state(SPAN[0], config.env_at(SPAN[0]))                  # dusk_gold
    for cut, f0, _ in CUTS:
        az, el, disk = SUN[cut]
        ENV.set_sun(f0, az, el, disk_deg=disk)
        near, far = CLEAR.get(cut, config.GRASS_CAMERA_CLEAR)
        ENV.set_camera_clearance(f0, near, far)
    # S06 ECU: a soft fill so the lacquer / the dark kimono read as shapes behind the lit steel (restored at 589)
    for name, v in (("fill_pow", 0.22), ("amb_str", 0.22)):
        ENV.set_param(CUT["S06"][0], name, v)
        ENV.set_param(CUT["S07a"][0], name, float(ENV._default_value_at(name, CUT["S07a"][0])))
    for f, w in ((433, 1.0), (488, 1.0), (500, 1.35), (528, 1.0),       # S05: one gust wave between them
                 (541, 1.0), (576, 1.0), (588, 0.0),                     # S06: the wind dies (held breath)
                 (589, 0.6), (631, 1.0),                                  # S07: the dash breaks it, back on bar 1
                 (768, 1.0), (778, 1.4), (795, 1.0),                      # S08d: a gust breaks the tableau
                 (869, 1.0), (936, 1.0)):
        ENV.set_wind(f, w)


# =============================================================================================================
# vfx
# =============================================================================================================
GLINT_COL = (1.0, 0.86, 0.62)


def _star_mesh(name, size, streak=2.6):
    """A flat 4-point star (+ one long thin streak along local X) in the local XY plane, normal +Z."""
    verts, faces = [(0.0, 0.0, 0.0)], []
    n = 8
    for i in range(n):
        a = math.pi * 2.0 * i / n
        r = size * (0.5 if i % 2 == 0 else 0.09)
        verts.append((r * math.cos(a), r * math.sin(a), 0.0))
    for i in range(n):
        faces.append((0, 1 + i, 1 + (i + 1) % n))
    k = len(verts)
    L, w = size * 0.5 * streak, size * 0.035
    verts += [(-L, 0.0, 0.0), (0.0, -w, 0.0), (L, 0.0, 0.0), (0.0, w, 0.0)]
    faces += [(k, k + 1, k + 2, k + 3)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    return me


def _local_glint(name, f0, f1, peak, size, camera, parent=None, local=(0.0, 0.0, 0.0), world_keys=None,
                 peak_frame=None):
    """Camera-facing emissive star glint: parented to `parent` at `local`, or keyed in
    world space (`world_keys` = [(frame, xyz)]); strength 0 -> peak -> 0 over [f0, f1]; visible only in [f0, f1]."""
    import lane_tools  # noqa: F401  (collection handling is the lane's: objects land in LANE_act1a)
    col = bpy.context.collection
    ob = bpy.data.objects.new(name, _star_mesh(name + "_mesh", size))
    col.objects.link(ob)
    mat = U.emission_material(name + "_mat", GLINT_COL, 0.0)
    mat.surface_render_method = 'DITHERED'
    ob.data.materials.append(mat)
    ob.visible_shadow = False
    if parent is not None:
        ob.parent = parent
        ob.matrix_parent_inverse = Matrix.Identity(4)
        ob.location = local
    for f, p in (world_keys or ()):
        U.key(ob, "location", f, tuple(p), interp='LINEAR')
    tr = ob.constraints.new('TRACK_TO')
    tr.target = camera
    tr.track_axis, tr.up_axis = 'TRACK_Z', 'UP_Y'
    em = next(n for n in mat.node_tree.nodes if n.bl_idname == 'ShaderNodeEmission')
    sock = em.inputs["Strength"]
    pk = peak_frame if peak_frame is not None else (f0 + f1) // 2
    for f, v in ((f0, 0.0), (pk, float(peak)), (f1, 0.0)):
        U.key(sock, "default_value", f, v, interp='BEZIER')
    U.key_visible(ob, SPAN[0], False)
    U.key_visible(ob, f0, True)
    U.key_visible(ob, f1 + 1, False)
    return ob


def effects(SH, SA):
    import vfx
    tr = vfx.blade_trail
    # blade trails (owner colour coding: elder gold in Act I, shinobi cool white / red core)
    tr("SAINT_katana_tip", "SAINT_katana_base", 590, 596, owner="saint", name="S07a_trail_iai")
    tr("SAINT_katana_tip", "SAINT_katana_base", 631, 640, owner="saint", name="S07c_trail_release")
    tr("SAINT_katana_tip", "SAINT_katana_base", 700, 710, owner="saint", name="S08a_trail_hit1")
    tr("SAINT_katana_tip", "SAINT_katana_base", 716, 726, owner="saint", name="S08b_trail_hit2")
    tr("SAINT_katana_tip", "SAINT_katana_base", 750, 757, owner="saint", width=0.5, name="S08c_trail_thrust")
    tr("SHINOBI_katana_tip", "SHINOBI_katana_base", 844, 851, owner="shinobi", name="S09a_trail_counter1")
    tr("SHINOBI_katana_tip", "SHINOBI_katana_base", 859, 867, owner="shinobi", name="S09b_trail_counter2")
    # S07a: the dash wake, the pressure ring at the clash, the student's braced rear foot
    vfx.grass_burst(590, (0.0, 0.9, 0.6), direction=(0.0, 0.5, 0.6), count=70, speed=3.0, fluff=0.15,
                    seed=_crc("S07a:wake"))
    vfx.grass_burst(595, (0.25, -1.95, 0.95), direction=(0.0, 0.0, 1.0), count=60, spread=80, fluff=0.15,
                    seed=_crc("S07a:ring"))
    vfx.dust_burst(596, (0.0, -2.95, 0.0), radius=0.6, life=48, seed=_crc("S07a:plant"))
    # S07b: the spark stream peeling off the grind (the clash registrations at 601 / 615 / 630 add three more)
    for i, f in enumerate((599, 605, 608, 611, 618, 621, 624, 627)):
        vfx.sparks(f, tuple(_grind_point(f)), direction=(-0.2, 0.55, 0.8), count=14, speed=3.0, life=8,
                   color="gold", scale=0.7, light=(i % 3 == 0), seed=_crc(f"S07b:{i}"))
    # S07c: the real-time release, the skid through the grass
    vfx.sparks(631, tuple(P595_END), direction=(-0.3, 0.2, 0.9), count=40, speed=6.0, life=8, color="gold",
               seed=_crc("S07c:release"))
    vfx.grass_burst(633, (0.0, -3.00, 0.3), direction=(0.0, -0.6, 0.6), count=70, speed=3.0, fluff=0.15,
                    seed=_crc("S07c:skid"))
    vfx.dust_burst(634, (0.0, -3.20, 0.0), radius=0.7, life=40, seed=_crc("S07c:dust"))
    # S08
    vfx.grass_burst(694, (0.0, -1.10, 0.2), direction=(0.0, -0.3, 1.0), count=30, speed=2.0, fluff=0.1,
                    seed=_crc("S08a:step"))
    vfx.grass_burst(752, (-0.35, -3.45, 0.4), direction=(-0.6, 0.0, 0.5), count=40, speed=2.5, fluff=0.1,
                    seed=_crc("S08c:side"))
    vfx.dust_burst(756, (0.0, -2.20, 0.0), radius=0.5, life=36, seed=_crc("S08c:lunge"))
    # S09
    vfx.grass_burst(846, (0.30, -2.70, 0.3), direction=(0.0, 0.5, 0.6), count=40, speed=2.5, fluff=0.1,
                    seed=_crc("S09a:launch"))
    vfx.grass_burst(862, (0.30, -1.95, 0.3), direction=(0.0, 0.6, 0.5), count=35, fluff=0.1,
                    seed=_crc("S09b:step"))


def glints(SH, SA):
    """S05 draw glint on the student's blade (466-471) and the S06 sun glint along the exposed steel (566-575)."""
    import characters as CH
    cam05, cam06 = bpy.data.objects["S05_cam"], bpy.data.objects["S06_cam"]
    _local_glint("S05_glint", 466, 471, 1.2, 0.05, cam05, parent=bpy.data.objects["SHINOBI_katana_tip"],
                 local=(0.0, -0.18, 0.0), peak_frame=468)
    ks = bpy.data.objects["SAINT_katana_sheathed"]
    D = CH.DIMS["SAINT"]
    y0 = D["grip_to_tsuba"] + D["tsuba_thickness"] * 0.5            # tsuba face = the koiguchi before the push
    keys = []
    for f in range(566, 576):
        u = (f - 566) / 9.0
        W = U.world_matrix_of(ks, f)
        p = W @ Vector((0.0, y0 + 0.040 - 0.035 * u, 0.0))            # koiguchi edge -> tsuba (right -> left)
        c = U.world_matrix_of(cam06, f).translation
        keys.append((f, p + (c - p).normalized() * 0.035))     # in front of the blade width (saya rolled 60 deg)
    _local_glint("S06_glint", 566, 575, 1.5, 0.012, cam06, world_keys=keys, peak_frame=569)


# =============================================================================================================
# flashes (compositor) - one soft exposure lift in the whole lane
# =============================================================================================================
def flashes():
    import render_setup as RS
    # the Flash node mixes toward LINEAR 16 (render_setup.FLASH_LEVEL): 0.25 would be a full-white frame.
    # 0.005 adds ~0.08 linear (a soft exposure lift on the impact frame); 0.0015 on the decay frame.  0.008 / 0.003
    # read as a grey haze over two frames on the preview.
    RS.key_white_flash(595, 0.005)                       # 594: 0, 595: lift, 596: 0 ...
    U.comp_key_flash(596, 0.0015, interp='CONSTANT')     # ... decay on 596
    U.comp_key_flash(597, 0.0, interp='CONSTANT')
    RS.key_dispersion(595, 0.04, release=3)
    RS.key_dispersion(631, 0.04, release=3)
    RS.key_dispersion(725, 0.03, release=2)


# =============================================================================================================
# story events (the macros emit steps / whooshes / draws / clashes / skids themselves)
# =============================================================================================================
def story_events(SH, SA):
    saya = bpy.data.objects["SAINT_saya"]
    K = U.world_pos_of(saya, F["click"])
    EV.emit(config.MUSIC_CUES["act1_start"], "music_cue", cue="act1_start", tags=["act1_start"])
    EV.emit(496, "wind_gust", strength=0.4)
    EV.emit(F["click"], "tsuba_click", pos=tuple(K), who="saint", tags=["tsuba_click", "click_motif_1"])
    EV.emit(576, "wind_gust", strength=0.0, tags=["held_breath"])
    EV.emit(F["dash"], "dash", who="saint", strength=1.0)
    EV.emit(config.MUSIC_CUES["first_clash"], "music_cue", cue="first_clash", tags=["first_clash"])
    EV.emit(S07_SLOWMO[0], "slowmo", duration=S07_SLOWMO[1] - S07_SLOWMO[0] + 1)
    EV.emit(599, "blade_lock", duration=31, strength=0.35, pos=tuple(_grind_point(612)), tags=["grind", "slowmo"])
    EV.emit(config.MUSIC_CUES["act1_bar1"], "music_cue", cue="act1_bar1", tags=["act1_bar1"])
    EV.emit(F["release"], "whoosh", who="saint", weapon="katana", strength=0.6)
    EV.emit(772, "wind_gust", strength=0.5)
    EV.emit(842, "dash", who="shinobi", strength=0.6)          # the student launches on the half beat 13.5


# =============================================================================================================
# cameras - 13 sub-cuts (keys verbatim from the breakdown; the S06 ECU is placed on the koiguchi)
# =============================================================================================================
def cameras(SH, SA):
    ax = S05_AXIS
    y_mid = (H0["shinobi"]["pos"][1] + H0["saint"]["pos"][1]) * 0.5                     # -0.25
    look_z = ax["z"] + ax["x"] * math.tan(math.radians(ax["pitch_deg"]))                 # 3.416
    both = ["shinobi", "saint"]
    C.shot("S05", *CUT["S05"], keys=[(433, (ax["x"], y_mid, ax["z"]), (0.0, y_mid, look_z), ax["lens"])],
           dof=None, handheld=0.0, subjects=both, framing="wide")
    # S06 - ECU on the koiguchi (origin of SAINT_saya), camera on the elder's LEFT (+X)
    saya = bpy.data.objects["SAINT_saya"]
    K = U.world_pos_of(saya, 560)
    A = (U.world_matrix_of(saya, 560).to_3x3() @ Vector((0.0, -1.0, 0.0))).normalized()
    C.shot("S06", *CUT["S06"],
           keys=[(541, K + Vector((0.52, -0.12, 0.05)), K + 0.012 * A, 100.0),
                 (588, K + Vector((0.50, -0.12, 0.05)), K + 0.012 * A, 100.0)],
           dof=dict(focus=saya, fstop=5.6), subjects=["saint"], framing="ecu", clip=(0.02, 500.0))
    # 50 mm instead of 40 (Implementation notes): the figures stand chest-deep in the grass, 40 mm left the first
    # clash small; at 50 mm the elder is just off the right edge on 589 and bursts in on 590-591 (D2's "blur
    # entering from the frame edge").
    C.shot("S07a", *CUT["S07a"], keys=[(589, (7.50, -1.90, 1.50), (0.00, -1.90, 1.30), 50.0)],
           dof=dict(focus=tuple(P595), fstop=4.0), subjects=both, framing="medium")
    C.shot("S07b", *CUT["S07b"], keys=[(601, (1.88, -1.86, 1.44), (0.30, -1.98, 1.38), 85.0),
                                       (630, (1.70, -1.78, 1.52), (0.33, -1.86, 1.47), 85.0)],
           dof=dict(focus=tuple(P595), fstop=4.0, distance_keys=[(601, 1.59), (630, 1.40)]),
           subjects=[], framing="insert")
    C.shot("S07c", *CUT["S07c"], keys=[(631, (7.20, -1.75, 1.25), (0.00, -1.75, 1.38), 32.0)],
           dof=None, shake=[(631, 0.8, 10)], subjects=both, framing="wide")
    C.shot("S08a", *CUT["S08a"], keys=[
        (673, (3.54, -6.33, 1.62), (0.00, -2.05, 1.35), 35.0),
        (682, (3.87, -6.03, 1.61), (0.00, -2.07, 1.35), 35.0),
        (691, (4.51, -5.27, 1.60), (0.00, -2.10, 1.36), 35.0),
        (700, (5.00, -4.42, 1.59), (0.00, -2.13, 1.38), 35.0),
        (709, (5.17, -4.00, 1.58), (0.00, -2.15, 1.38), 35.0),
        (711, (5.20, -3.91, 1.58), (0.00, -2.15, 1.38), 35.0)],
        dof=dict(focus=tuple(P709), fstop=4.0), subjects=both, framing="medium")
    C.shot("S08b", *CUT["S08b"], keys=[(712, (5.09, -1.22, 1.22), (0.12, -2.35, 1.34), 50.0),
                                       (727, (5.05, -1.04, 1.22), (0.12, -2.40, 1.34), 50.0)],
           dof=dict(focus=tuple(P725), fstop=2.8), subjects=both, framing="medium")
    # risk-8 camera (+0.3 m X, lower) so the gap opens; the operator follows the sidestep (look pans 0.25 m left
    # 748 -> 758) so the student stays at the left edge beside the thrust.
    C.shot("S08c", *CUT["S08c"], keys=[(728, (1.02, -5.35, 1.50), (-0.05, -1.20, 1.42), 45.0),
                                       (748, (1.02, -5.38, 1.49), (-0.05, -1.60, 1.39), 45.0),
                                       (758, (1.02, -5.40, 1.48), (-0.30, -1.80, 1.36), 45.0)],
           dof=dict(focus=(SA, "head"), fstop=2.8), subjects=both, framing="ots")
    C.shot("S08d", *CUT["S08d"], keys=[
        (759, (2.55, -7.36, 1.72), (-0.20, -2.60, 1.35), 32.0),
        (766, (2.93, -7.12, 1.70), (-0.19, -2.60, 1.35), 32.0),
        (773, (3.77, -6.41, 1.67), (-0.17, -2.59, 1.35), 32.0),
        (780, (4.61, -5.26, 1.62), (-0.15, -2.57, 1.35), 32.0),
        (787, (5.13, -3.96, 1.57), (-0.12, -2.56, 1.35), 32.0),
        (794, (5.29, -2.93, 1.53), (-0.11, -2.55, 1.35), 32.0),
        (800, (5.30, -2.60, 1.52), (-0.10, -2.55, 1.35), 32.0)],
        dof=None, subjects=both, framing="medium")
    C.shot("S08e", *CUT["S08e"], keys=[(801, (2.45, -0.95, 1.52), (0.10, -3.17, 1.40), 65.0),
                                       (840, (2.25, -0.75, 1.50), (0.12, -2.82, 1.40), 65.0)],
           dof=dict(focus=(SH, "head"), fstop=2.8), subjects=["shinobi"], framing="mcu")
    C.shot("S09a", *CUT["S09a"], keys=[(841, (0.78, 1.55, 1.74), (0.25, -2.70, 1.38), 40.0),
                                       (852, (0.78, 1.62, 1.74), (0.25, -2.40, 1.38), 40.0)],
           dof=dict(focus=(SH, "head"), fstop=2.8), subjects=both, framing="ots")
    C.shot("S09b", *CUT["S09b"], keys=[(853, (2.10, 1.00, 1.72), (0.18, -1.50, 1.45), 50.0),
                                       (868, (2.35, 1.45, 1.72), (0.10, -0.90, 1.45), 50.0)],
           dof=dict(focus=(SA, "head"), fstop=2.8), subjects=both, framing="ots")
    C.shot("S09c", *CUT["S09c"], keys=[(869, (8.60, -0.70, 2.55), (0.00, -0.70, 1.15), 28.0),
                                       (936, (8.60, 0.40, 2.55), (0.00, 0.40, 1.15), 28.0)],
           dof=None, subjects=both, framing="wide")


# =============================================================================================================
# lane entry
# =============================================================================================================
def build(ctx):
    """Lane entry (acts contract): keys only inside SPAN, cameras via cameras.shot, events via events.emit."""
    sh, sa = ctx["chars"]["shinobi"], ctx["chars"]["saint"]
    stubs = ctx.get("stubs", {})
    missing = [m for m in ("characters", "moves", "environment", "vfx") if stubs.get(m)]
    if missing:
        raise RuntimeError(f"act1a needs the real modules (placeholders: {missing})")
    choreograph(sh, sa)
    environment_timeline()
    effects(sh, sa)
    story_events(sh, sa)
    cameras(sh, sa)
    glints(sh, sa)
    flashes()
    for ob in (sh, sa):
        U.freeze_handles(ob, SPAN)
