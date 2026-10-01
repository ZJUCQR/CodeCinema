"""
moves.py - move macros for the two duelists, built on poses.py (Blender 5.2).

    import moves as M
    M.walk(SH, 73, 240, (0, -21.3), (0, -12.25))                 # procedural gait, planted feet, step events
    M.draw_sword(SH, 456)                                         # f = the frame the kissaki clears the koiguchi
    end = M.slash(SA, 709, "diag_down_R", lunge=0.4)              # f = IMPACT frame; returns the frame it ends
    M.deflect(SH, 709, "high")                                    # f = contact frame
    M.clash(SA, SH, 709, point=(-0.22, -2.45, 1.52), strength=0.75)   # blades cross at the point; resolved at end_lane
    M.finalize()                                                  # stand-alone scripts: feet bake + clashes (build_scene
                                                                  # does this through lane_tools.end_lane)

Conventions
    * Frames are FILM frames.  Every macro times itself in STORY frames (24 fps real time) through a Clock anchored
      on its key frame, so inside config.TIME_WARP slow-motion windows the keys spread out proportionally (a 3-frame
      strike at speed 0.25 takes 12 film frames).  M.clock(f)(d) = film frame d story frames after f.
    * Attacks / deflects / clashes / kicks / lands take the KEY MOMENT (impact / contact / touchdown) as `f` -> put
      it on a beat: M.slash(SA, M.beat("act1", 12), ...).  Locomotion takes (f0, f1) = start / end.
    * Every macro returns the frame the move ends (its last key), emits its events through events.emit (local shim if
      events.py is missing) and keys only through poses.key_pose / key_root / characters helpers.
    * Hands: moves keep the left-hand state the lane set (one-handed elder with his left hand on the saya in Act I,
      two-handed shinobi); pass two_hand=True/False to change it.
    * Feet: every keyed pose registers where its feet are; bake_feet() (run by resolve_clashes at end_lane, or by
      finalize()) re-solves the legs per frame so planted feet do not slide and moving feet step in arcs.

Public API
    timing      clock(f) ; story_to_film(f, d) ; film_to_story(f0, f1) ; speed_at(f) ; beat(section, n) ;
                snap_to_beat(f, section)
    keying      pose(rig, f, name, **kw) ; root(rig, f, xy, facing, z=0) ; root_at(rig, f) ; facing_of(rig, f) ;
                forward_of(rig, f) ; swing(rig, f0, f1, a, b, ...) ; key_ctrl(rig, f, spec_or_matrix)
    locomotion  stance(rig, f, kind) ; walk / run / dash(rig, f0, f1, p0, p1, ...) ; strafe(rig, f0, f1, center,
                radius, a0, a1) ; step(rig, f0, f1, p1, ...) ; turn(rig, f0, f1, facing)
    sword       draw_sword(rig, f) ; sheathe(rig, f, speed) ; iai_slash(rig, f, kind) ; slash(rig, f, kind) ;
                deflect(rig, f, kind) ; perfect_deflect(rig, f, attacker, point)
    evasion     dodge(rig, f, direction) ; duck(rig, f) ; jump(rig, f0, f1, p0, p1, apex) ; plunge(rig, f0, f1, ...) ;
                roll(rig, f0, f1, p0, p1) ; stagger(rig, f, dir) ; skid(rig, f0, f1, p0, p1) ; kick(rig, f) ;
                slide_cut(rig, f0, f1, p0, p1)
    contact     clash(attacker, defender, f, point=None, strength=1.0, kind='clash', ...) ; blade_lock(a, b, f0, f1) ;
                resolve_clashes(frame_range=None) ; clash_report() ; clashes()
    spear       spear_draw(rig, f) ; spear_spin(rig, f0, f1) ; spear_sweep(rig, f) ; spear_thrust(rig, f) ;
                spear_slam(rig, f) ; spear_butt_slam(rig, f) ; spear_throw(rig, f, target)
    story       raise_to_sky(rig, f) ; kneel(rig, f) ; rise(rig, f0, f1) ; bow(rig, f) ; hide_in_grass(rig, f) ;
                listen(rig, f) ; shed_haori(rig, f) ; throw_kunai(rig, f, i, target) ; kunai_parry(rig, f)
    props       toss(obj, f0, p0, v0, spin, ground_z, settle) (props.toss when a props module exists)
    finishing   bake_feet(rig=None, frame_range=None) ; finalize(frame_range=None) ; reset()
"""
import math
import os
import sys
import zlib

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

ROOT = (__import__("os").environ.get("SILVERGRASS_ROOT") or str(next(p for p in __import__("pathlib").Path(__file__).resolve().parents if (p / "src" / "common" / "config.py").is_file())))   # repo root (portable)
for _p in (os.path.join(ROOT, "src", "common"), os.path.join(ROOT, "src", "blender")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import config  # noqa: E402
import bl_util as U  # noqa: E402
import characters as C  # noqa: E402
import poses as PZ  # noqa: E402

FPS = float(config.FPS)
LOG = []                    # human-readable notes (clamps, unreachable clashes ...) - printed by finalize()


def _log(msg):
    LOG.append(msg)
    print("[moves]", msg)


def seed(*parts):
    """Deterministic seed from any parts (zlib.crc32 of their text; never Python hash())."""
    return zlib.crc32(":".join(str(p) for p in parts).encode()) & 0x7FFFFFFF


# =============================================================================================
# optional modules: events (emit), vfx (sparks, flash_ring), props (toss) - switch automatically
# =============================================================================================
LOCAL_EVENTS = []           # used only when events.py is missing


def _module(name):
    try:
        return __import__(name)
    except ImportError as e:
        if getattr(e, "name", None) == name:
            return None
        raise


def emit(frame, type, **attrs):
    """events.emit(frame, type, **attrs) - or a local list with the same API when events.py is absent."""
    ev = _module("events")
    if ev is not None and hasattr(ev, "emit"):
        return ev.emit(frame, type, **attrs)
    e = dict(frame=frame, type=type, **attrs)
    LOCAL_EVENTS.append(e)
    return e


def who(rig):
    """'shinobi' | 'saint' (events 'who')."""
    return "saint" if PZ.char_of(rig) == "SAINT" else "shinobi"


# =============================================================================================
# timing: story frames <-> film frames through config.TIME_WARP (same curve as fxclock)
# =============================================================================================
def _breakpoints():
    f = float(config.FRAME_START - 400)
    t = (f - config.FRAME_START) / FPS
    out = [(f, t)]
    for a, b, spd in sorted(getattr(config, "TIME_WARP", [])):
        t += (a - f) / FPS
        f = float(a)
        out.append((f, t))
        t += (b - a) * float(spd) / FPS
        f = float(b)
        out.append((f, t))
    end = float(config.FRAME_END + 4000)
    t += (end - f) / FPS
    out.append((end, t))
    return out


_BP = _breakpoints()


def fx_time(frame):
    """Film clock (seconds) at a film frame - identical to fxclock.fx_time_at (tested)."""
    f = float(frame)
    pts = _BP
    if f <= pts[0][0]:
        (f0, t0), (f1, t1) = pts[0], pts[1]
    elif f >= pts[-1][0]:
        (f0, t0), (f1, t1) = pts[-2], pts[-1]
    else:
        for (f0, t0), (f1, t1) in zip(pts, pts[1:]):
            if f0 <= f <= f1:
                break
    return t0 if f1 == f0 else t0 + (t1 - t0) * (f - f0) / (f1 - f0)


def _film_at_time(t):
    pts = _BP
    for (f0, t0), (f1, t1) in zip(pts, pts[1:]):
        if t0 <= t <= t1 and t1 > t0:
            return f0 + (f1 - f0) * (t - t0) / (t1 - t0)
    (f0, t0), (f1, t1) = (pts[0], pts[1]) if t < pts[0][1] else (pts[-2], pts[-1])
    return f0 + (f1 - f0) * (t - t0) / (t1 - t0)


def speed_at(frame):
    """Story speed at a film frame (config.TIME_WARP; 1.0 outside the slow-motion windows)."""
    for a, b, spd in getattr(config, "TIME_WARP", []):
        if a <= frame < b:
            return float(spd)
    return 1.0


def story_to_film(f, d):
    """Film frame reached `d` story frames (real-time 24 fps frames, may be negative) after film frame `f`."""
    if d == 0:
        return float(f)
    return round(_film_at_time(fx_time(f) + d / FPS), 3)


def film_to_story(f0, f1):
    """Story frames elapsed between two film frames."""
    return (fx_time(f1) - fx_time(f0)) * FPS


class Clock:
    """clock(f)(d) -> film frame of story offset d from anchor film frame f (TIME_WARP aware)."""

    def __init__(self, anchor):
        self.anchor = float(anchor)
        self.slow = any(a - 60 <= anchor <= b + 60 for a, b, _ in getattr(config, "TIME_WARP", []))

    def __call__(self, d):
        if not self.slow:
            return self.anchor + d
        return story_to_film(self.anchor, d)

    def span(self, f):
        """story offset of film frame f from the anchor"""
        return film_to_story(self.anchor, f)


def clock(f):
    return Clock(f)


def beat(section, n):
    """config.beat_frame(section, n) (Act I 92 BPM from 631, Act II 120 BPM from 1633, Act III 140 BPM from 2497)."""
    return config.beat_frame(section, n)


def snap_to_beat(f, section, subdiv=1):
    """Nearest beat (or 1/subdiv beat) frame of a TEMPO_MAP section to film frame f."""
    t = next(t for t in config.TEMPO_MAP if t["section"] == section)
    per = FPS * 60.0 / t["bpm"] / subdiv
    n = round((f - t["anchor"]) / per)
    return int(round(t["anchor"] + n * per))


# =============================================================================================
# rig / root helpers
# =============================================================================================
def rig_of(rig_or_name):
    return C.get_rig(rig_or_name)


def S(rig):
    """Height scale of a rig relative to the SHINOBI (poses are authored in SHINOBI metres)."""
    return PZ.SCALE[PZ.char_of(rig)]


def root_at(rig, f):
    """(x, y, z, facing_deg) of the rig object at film frame f from its keys."""
    return PZ.root_at(rig_of(rig), f)


def facing_of(rig, f):
    return root_at(rig, f)[3]


def forward_vec(facing_deg):
    """World forward (x, y) of a facing angle (0 -> -Y, 180 -> +Y)."""
    a = math.radians(facing_deg)
    return Vector((math.sin(a), -math.cos(a), 0.0))


def left_vec(facing_deg):
    """World direction of the character's LEFT for a facing angle."""
    a = math.radians(facing_deg)
    return Vector((math.cos(a), math.sin(a), 0.0))


def forward_of(rig, f):
    return forward_vec(facing_of(rig, f))


def facing_to(p_from, p_to):
    """Facing angle (deg) that looks from p_from toward p_to (xy)."""
    dx, dy = p_to[0] - p_from[0], p_to[1] - p_from[1]
    return math.degrees(math.atan2(dx, -dy))


def rig_matrix(rig, f):
    """World matrix of the rig object at film frame f from its keys (no depsgraph)."""
    x, y, z, a = root_at(rig, f)
    rig = rig_of(rig)
    rx = PZ._ev(rig, "rotation_euler", f, rig.rotation_euler[0], 0)
    ry = PZ._ev(rig, "rotation_euler", f, rig.rotation_euler[1], 1)
    return Matrix.Translation((x, y, z)) @ Euler((rx, ry, math.radians(a)), 'XYZ').to_matrix().to_4x4()


def root(rig, f, xy, facing, z=0.0, interp='BEZIER', tilt=(0.0, 0.0)):
    """Key the root (rig object) - poses.key_root."""
    return PZ.key_root(rig_of(rig), f, xy, facing, z=z, interp=interp, tilt=tilt)


def root_path(rig, f0, f1, p0, p1, facing0=None, facing1=None, ease="inout_cubic", z=None, step=1, clk=None,
              arc=0.0):
    """Key the root per frame from p0 at f0 to p1 at f1 along an eased path (LINEAR keys, `step` film frames apart).
    facing None = keep the facing at f0; z: None = ground, float or callable(u) -> height; arc = sideways bow (m,
    + = to the left of the travel direction).  The easing runs in story time (slow-motion aware)."""
    rig = rig_of(rig)
    x0, y0, z0, a0 = root_at(rig, f0)
    p0 = Vector((x0, y0)) if p0 is None else Vector(p0[:2])
    p1 = Vector(p1[:2])
    fa = a0 if facing0 is None else facing0
    fb = fa if facing1 is None else facing1
    clk = clk or Clock(f0)
    total = max(1e-6, clk.span(f1))
    frames = _frame_list(f0, f1, step)
    d = p1 - p0
    side = Vector((-d.y, d.x)).normalized() if d.length > 1e-6 else Vector((0, 0))
    for f in frames:
        u = U.ease(clk.span(f) / total, ease)
        p = p0 + d * u + side * (arc * 4.0 * u * (1.0 - u))
        zz = 0.0 if z is None else (z(u) if callable(z) else float(z))
        root(rig, f, (p.x, p.y), fa + _angle_diff(fb, fa) * u, z=zz, interp='LINEAR')
    return f1


def _frame_list(f0, f1, step=1):
    out = []
    f = float(f0)
    while f < f1 - 1e-6:
        out.append(round(f, 3))
        f += step
    out.append(round(float(f1), 3))
    return out


def _angle_diff(a, b):
    """a - b wrapped to (-180, 180]."""
    return (a - b + 180.0) % 360.0 - 180.0


# =============================================================================================
# pose keying wrappers
# =============================================================================================
def pose(rig, f, name, weight=1.0, mirror=False, interp='BEZIER', hands="keep", ctrl=True, legs=True, lag=None,
         clk=None, hand_blend=0, feet=True, elbows=True):
    """poses.key_pose with moves' defaults (hands='keep': the lane's left-hand state is kept) and lag given in
    STORY frames (converted through the clock of f)."""
    rig = rig_of(rig)
    if lag:
        clk = clk or Clock(f)
        base = clk.span(f)
        lag = {b: clk(base + d) - f for b, d in lag.items()}
    sp = PZ.key_pose(rig, f, name, weight=weight, mirror=mirror, interp=interp, hands=hands, ctrl=ctrl, legs=legs,
                     lag=lag, hand_blend=hand_blend, feet=feet, elbows=elbows)
    if PZ.char_of(rig) == "SAINT":           # a pose that tilted the straw hat hands it back to level on the next pose
        tilt = sp.get("hat_tilt")
        if tilt and any(abs(v) > 1e-6 for v in tilt):
            _HAT["tilted"] = True
        elif _HAT["tilted"]:
            C.set_hat_tilt(f, 0.0, 0.0)
            _HAT["tilted"] = False
    return sp


_HAT = dict(tilted=False)


def key_ctrl(rig, f, spec, interp='BEZIER', mirror=False):
    """Key the sword controller from a pose name, a ctrl spec (rig space, SHINOBI metres) or a rig-space Matrix;
    turns the arm IK on if needed.  Returns the rig-space matrix."""
    rig = rig_of(rig)
    M = ctrl_matrix(rig, spec, f, mirror)
    C.key_ctrl_matrix(PZ._ctrl_obj(rig), f, M, interp)
    _ensure_ik(rig, f)
    return M


def ctrl_matrix(rig, spec, f=None, mirror=False):
    """Rig-space controller matrix of a pose name / ctrl spec / Matrix (sheathed specs evaluate the rig at f)."""
    if isinstance(spec, Matrix):
        return spec.copy()
    if isinstance(spec, str) and spec != "sheathed":
        spec = PZ.resolve(spec, rig, mirror)["ctrl"]
    elif mirror and isinstance(spec, dict):
        spec = PZ.resolve({"ctrl": spec}, rig, True)["ctrl"]
    if spec == "sheathed" or (isinstance(spec, dict) and "sheathed" in spec):
        pull = 0.0 if spec == "sheathed" else float(spec["sheathed"]) * S(rig)
        U.frame_set(f)
        return C.sheathed_ctrl_matrix(rig, f) @ Matrix.Translation((0.0, -pull, 0.0))
    if isinstance(spec, dict) and "slung" in spec:
        U.frame_set(f)
        return C.slung_spear_ctrl_matrix(f, float(spec["slung"]))
    return PZ.ctrl_matrix(rig, spec)


def _ensure_ik(rig, f):
    ik = C._con(rig, "forearm.R", "IK_sword")
    if PZ._ev(rig, ik.path_from_id("influence"), f, ik.influence) < 0.5:
        C.set_arm_mode(rig, f, "ik")


def arm_is_ik(rig, f):
    ik = C._con(rig_of(rig), "forearm.R", "IK_sword")
    return PZ._ev(rig_of(rig), ik.path_from_id("influence"), f, ik.influence) > 0.5


def katana_drawn(rig, f):
    rig = rig_of(rig)
    return PZ._ev(rig, '["katana_state"]', f, rig.get("katana_state", 0)) > 0.5


def weapon_at(rig, f):
    """'katana' | 'spear' in hand at f (SAINT only has the spear)."""
    rig = rig_of(rig)
    return C.active_weapon(rig, f) if PZ.char_of(rig) == "SAINT" else "katana"


# =============================================================================================
# blade arcs
# =============================================================================================
PIVOT = Vector((0.0, -0.02, 1.22))      # rig space, SHINOBI metres: centre of the sword arcs (sternum)


def swing(rig, f0, f1, a, b, ease="inout_quad", pivot=None, step=1, clk=None, mirror=False, via=None,
          interp='LINEAR', include_start=True):
    """Key the sword controller along an ARC from `a` (at f0) to `b` (at f1): rotation slerped, the grip moved on a
    sphere around `pivot` (rig space; default the sternum) with its radius interpolated - so blades travel in arcs,
    not straight lines.  a / b: pose names, ctrl specs or rig-space matrices; via: optional middle spec the arc
    passes at u=0.5.  Keys every `step` film frames (LINEAR, eased in story time).  Returns f1."""
    rig = rig_of(rig)
    clk = clk or Clock(f0)
    A = ctrl_matrix(rig, a, f0, mirror)
    B = ctrl_matrix(rig, b, f1, mirror)
    P = (Vector(pivot) if pivot is not None else PIVOT) * S(rig)
    if via is not None:
        V = ctrl_matrix(rig, via, f0, mirror)
        fm = clk((clk.span(f0) + clk.span(f1)) * 0.5)
        _arc_keys(rig, f0, fm, A, V, P, "in_quad" if ease != "linear" else "linear", step, clk, interp, include_start)
        _arc_keys(rig, fm, f1, V, B, "out_quad" if ease != "linear" else "linear", step, clk, interp, False)
    else:
        _arc_keys(rig, f0, f1, A, B, P, ease, step, clk, interp, include_start)
    _ensure_ik(rig, f0)
    return f1


def _arc_point(A, B, P, u):
    ra, rb = A.translation - P, B.translation - P
    la, lb = ra.length, rb.length
    if la < 1e-6 or lb < 1e-6:
        return A.translation.lerp(B.translation, u)
    da, db = ra / la, rb / lb
    if da.dot(db) < -0.999:
        return A.translation.lerp(B.translation, u)
    d = da.slerp(db, u) if da.dot(db) < 0.9999 else da
    return P + d * (la + (lb - la) * u)


def arc_matrix(A, B, P, u):
    """Controller matrix at parameter u of the arc A -> B around pivot P (rotation slerp, grip on the sphere)."""
    qa, qb = A.to_quaternion(), B.to_quaternion()
    if qa.dot(qb) < 0:
        qb = -qb
    q = qa.slerp(qb, u)
    return Matrix.Translation(_arc_point(A, B, P, u)) @ q.to_matrix().to_4x4()


def _arc_keys(rig, f0, f1, A, B, P, ease, step, clk, interp, include_start):
    ob = PZ._ctrl_obj(rig)
    s0, s1 = clk.span(f0), clk.span(f1)
    for f in _frame_list(f0, f1, step):
        if not include_start and abs(f - f0) < 1e-6:
            continue
        u = U.ease((clk.span(f) - s0) / max(1e-6, s1 - s0), ease)
        C.key_ctrl_matrix(ob, f, arc_matrix(A, B, P, u), interp)


# =============================================================================================
# feet: per-frame leg solve from the registered foot keys (no sliding planted feet, arcs for steps)
# =============================================================================================
PLANT_TOL = 0.06            # m: a foot whose target moves less than this between two keys stays planted
_EVENTED_STEPS = set()


def _ball_rest_z(rig, side):
    return rig.data.bones[f"foot.{side}"].tail_local.z


def _world_foot_keys(rig, side, lo=-math.inf, hi=math.inf):
    """Registered foot keys of one side converted to WORLD (ball xyz, yaw deg, heel deg), sorted by frame."""
    out = []
    for k in PZ.FOOT_KEYS.get(rig.name, []):
        if k["side"] != side or not (lo - 1e-3 <= k["frame"] <= hi + 1e-3):
            continue
        f = k["frame"]
        if k["space"] == "WORLD":
            b = Vector(k["ball"])
            yaw = k["yaw"]
        else:
            M = rig_matrix(rig, f)
            b = M @ Vector(k["ball"])
            yaw = facing_of(rig, f) + k["yaw"]
        out.append(dict(k, bw=b, yw=yaw))
    out.sort(key=lambda k: k["frame"])
    return out


def _segments(keys, rig, side):
    """Plant / step / air segments between consecutive foot keys: [(ka, kb, kind, pa, pb)]."""
    segs = []
    plant = None
    zrest = _ball_rest_z(rig, side)
    for ka, kb in zip(keys, keys[1:]):
        if ka["air"] or kb["air"]:
            plant = None if kb["air"] else Vector((kb["bw"].x, kb["bw"].y, zrest))
            segs.append((ka, kb, "air", None, None))
            continue
        pa = plant if plant is not None else Vector((ka["bw"].x, ka["bw"].y, zrest))
        pb = Vector((kb["bw"].x, kb["bw"].y, zrest))
        if (pb - pa).length < PLANT_TOL:
            segs.append((ka, kb, "plant", pa, pa))
            plant = pa
        else:
            segs.append((ka, kb, "step", pa, pb))
            plant = pb
    return segs


def _reachable(rig, side, f, ball_w, yaw_w, zrest, heel_max=70.0):
    """True when the planted ball ball_w (world) can be reached at film frame f with some heel lift <= heel_max."""
    M = rig_matrix(rig, f)
    br = M.inverted() @ Vector((ball_w.x, ball_w.y, zrest))
    yaw_r = _angle_diff(yaw_w, facing_of(rig, f))
    H = PZ.hip_joint(rig, side, PZ.current_rot(rig, "hips", f), PZ.current_hips_offset(rig, f))
    ank = PZ.ball_to_ankle(rig, side, (br.x, br.y), yaw_r, heel_max, br.z - zrest)
    return (ank - H).length <= PZ.leg_length(rig, side) * PZ.REACH_FRAC


def _early_lifts(segs, rig, side):
    """A planted foot that the moving body would over-stretch lifts early: the plant ends (and the following step
    starts) on the last frame it is still reachable."""
    out = list(segs)
    for i, (ka, kb, kind, pa, pb) in enumerate(out):
        if kind != "plant" or i + 1 >= len(out) or out[i + 1][2] != "step":
            continue
        f = math.ceil(ka["frame"] + 1)
        last_ok = None
        while f <= kb["frame"]:
            if not _reachable(rig, side, f, pa, ka["yw"], pa.z):
                break
            last_ok = f
            f += 1
        else:
            continue
        cut = max(ka["frame"] + 1.0, float(last_ok if last_ok is not None else ka["frame"] + 1))
        if cut >= kb["frame"] - 1e-3:
            continue
        kb2 = dict(kb, frame=cut)
        nk, nkb, nkind, npa, npb = out[i + 1]
        out[i] = (ka, kb2, kind, pa, pb)
        out[i + 1] = (kb2, nkb, nkind, npa, npb)
    return out


def _key_leg(rig, side, f, sol, heel):
    for part in ("thigh", "shin", "foot"):
        U.key(rig.pose.bones[f"{part}.{side}"], "rotation_euler", f, tuple(math.radians(a) for a in sol[part]),
              interp='BEZIER')
    U.key(rig.pose.bones[f"toe.{side}"], "rotation_euler", f, (math.radians(-max(0.0, heel)), 0.0, 0.0),
          interp='BEZIER')


def _step_evented(rig_name, side, frame):
    """True when a footfall of this rig already has a step event close to `frame`: the same foot within 1 frame
    (a gait / step macro registers its footfall at a fractional frame, the bake finds the landing at the next pose
    key) or the other foot on the same integer frame (a closing shuffle = one sound)."""
    f_int = int(round(frame))
    for n, sd, fr in _EVENTED_STEPS:
        if n != rig_name:
            continue
        if (sd == side and abs(fr - frame) <= 1.0) or int(round(fr)) == f_int:
            return True
    return False


def bake_feet(rig=None, frame_range=None, events=True):
    """Re-solve the legs of `rig` (or every rig with registered foot keys) per frame inside `frame_range` so that
    planted feet stay put in WORLD space while the root and hips move, and moving feet step along lifted arcs
    (heel roll included).  Consecutive foot keys whose world ball positions differ by less than PLANT_TOL keep the
    foot planted; larger differences become a step over that interval (a 'step' event at touchdown); 'air' keys
    (jumps, kicks) keep the keyed leg rotations.  Returns dict(rig -> frames baked)."""
    rigs = [rig_of(rig)] if rig is not None else [bpy.data.objects[n] for n in PZ.FOOT_KEYS if n in bpy.data.objects]
    lo, hi = (frame_range if frame_range is not None else (-math.inf, math.inf))
    rep = {}
    for r in rigs:
        n = 0
        for side in ("L", "R"):
            keys = _world_foot_keys(r, side, lo - 0.5, hi + 0.5)
            for ka, kb, kind, pa, pb in _early_lifts(_segments(keys, r, side), r, side):
                if kind == "air":
                    continue
                fa, fb = ka["frame"], kb["frame"]
                if fb - fa < 1e-3:
                    continue
                n += _bake_segment(r, side, ka, kb, kind, pa, pb)
                if kind == "step" and events:
                    dist = (pb - pa).length
                    tag = (r.name, side, round(fb, 2))
                    if dist > 0.12 and not _step_evented(r.name, side, fb):
                        _EVENTED_STEPS.add(tag)
                        emit(int(round(fb)), "step", who=who(r), strength=round(min(1.0, 0.3 + dist), 2))
        rep[r.name] = n
    return rep


def _bake_segment(rig, side, ka, kb, kind, pa, pb):
    fa, fb = ka["frame"], kb["frame"]
    frames = sorted({fa, fb} | {float(x) for x in range(int(math.ceil(fa)), int(math.floor(fb)) + 1)})
    for part in ("thigh", "shin", "foot", "toe"):          # clear old keys strictly inside (sparse pose keys)
        pb_ = rig.pose.bones[f"{part}.{side}"]
        fc_path = pb_.path_from_id("rotation_euler")
        for i in range(3):
            fc = U.fcurve(rig, fc_path, i)
            if fc is None:
                continue
            kps = fc.keyframe_points
            idx = [j for j, k in enumerate(kps) if fa + 1e-3 < k.co.x < fb - 1e-3]
            for j in reversed(idx):
                kps.remove(kps[j], fast=True)
            if idx:
                fc.update()
    dist = (pb - pa).length
    h = min(0.16, max(0.035, 0.30 * dist)) * S(rig)
    zrest = pa.z
    for f in frames:
        u = (f - fa) / (fb - fa)
        if kind == "plant":
            b = pa
            lift = 0.0
            heel = ka["heel"] + (kb["heel"] - ka["heel"]) * u
        else:
            us = U.ease(u, "inout_quad")
            b = pa.lerp(pb, us)
            lift = h * math.sin(math.pi * min(1.0, u * 1.15))
            heel = ka["heel"] + (kb["heel"] - ka["heel"]) * u + 18.0 * math.sin(math.pi * u) * (1.0 - u)
        yaw_w = ka["yw"] + _angle_diff(kb["yw"], ka["yw"]) * u
        M = rig_matrix(rig, f)
        br = M.inverted() @ Vector((b.x, b.y, zrest + lift))
        yaw_r = _angle_diff(yaw_w, facing_of(rig, f))
        hr, ho = PZ.current_rot(rig, "hips", f), PZ.current_hips_offset(rig, f)
        H = PZ.hip_joint(rig, side, hr, ho)
        lim = PZ.leg_length(rig, side) * PZ.REACH_FRAC
        while True:                     # heel peel: rise onto the ball rather than lift / slide the planted ball
            ank = PZ.ball_to_ankle(rig, side, (br.x, br.y), yaw_r, heel, br.z - zrest)
            if (ank - H).length <= lim or heel >= 70.0:
                break
            heel = min(70.0, heel + 6.0)
        sol = C.solve_leg(rig, side, ank, hips_rot=hr, hips_offset=ho, knee_dir=ka.get("knee"),
                          foot_yaw=yaw_r, foot_pitch=heel)
        _key_leg(rig, side, f, sol, heel)
    return len(frames)


def plant(rig, f, side, ball_xy=None, yaw=None, heel=0.0):
    """Register a WORLD foot plant (ball at ball_xy, world yaw) at film frame f (None = where the foot is now)."""
    rig = rig_of(rig)
    if ball_xy is None:
        keys = _world_foot_keys(rig, side, -math.inf, f)
        if keys:
            ball_xy, yaw = tuple(keys[-1]["bw"][:2]), keys[-1]["yw"] if yaw is None else yaw
        else:
            U.frame_set(f)
            p = rig.matrix_world @ rig.pose.bones[f"toe.{side}"].head
            ball_xy = (p.x, p.y)
    if yaw is None:
        yaw = facing_of(rig, f)
    return PZ.register_foot(rig, f, side, (ball_xy[0], ball_xy[1], _ball_rest_z(rig, side)), yaw, heel,
                            space="WORLD", src="plant")


# =============================================================================================
# clash system
# =============================================================================================
_CLASHES = []
CLASH_GATE = 0.03           # m: resolve until the blade segments are this close (build_scene gate: 5 cm)
AXIS_Y = Vector((0.0, 1.0, 0.0))


def weapon_range(rig, weapon, part="blade", f=None):
    """(y0, y1) of a weapon along the controller's +Y (right-fist origin): katana blade (habaki -> tip), spear
    'blade' / 'shaft' / 'full' (butt -> tip)."""
    rig = rig_of(rig)
    c = PZ.char_of(rig)
    if weapon == "spear":
        D = C.DIMS["SAINT"]
        gR = C.spear_grip(f)[0] if f is not None else D["spear_grip_R"]
        tip = D["spear_length"] - gR
        base = tip - D["spear_blade_length"]
        return {"blade": (base, tip), "shaft": (-gR, base), "full": (-gR, tip)}[part]
    D = C.DIMS[c]
    y0 = D["grip_to_tsuba"] + D["tsuba_thickness"] * 0.5
    return y0 + D["habaki_length"], y0 + D["blade_length"]


def ideal_segment(rig, f, weapon=None, part=None):
    """World (base, tip) of the in-hand weapon from the KEYED controller at f (what the IK aims at)."""
    rig = rig_of(rig)
    w = weapon or weapon_at(rig, f)
    part = part or ("full" if w == "spear" else "blade")
    y0, y1 = weapon_range(rig, w, part, f)
    M = rig_matrix(rig, f) @ PZ.current_ctrl_matrix(rig, f)
    return M @ Vector((0.0, y0, 0.0)), M @ Vector((0.0, y1, 0.0))


def actual_segment(rig, f, weapon=None, part=None):
    """World (base, tip) of the weapon as EVALUATED at f (IK result; the depsgraph frame is set)."""
    rig = rig_of(rig)
    w = weapon or weapon_at(rig, f)
    U.frame_set(f)
    if w == "kunai":
        ob = bpy.data.objects.get("SHINOBI_kunai_hand")
        M = U.world_matrix_of(ob) if ob is not None else rig.matrix_world @ rig.pose.bones["hand.L"].matrix
        L = C.DIMS["SHINOBI"]["kunai_length"]
        return M @ Vector((0.0, -0.25 * L, 0.0)), M @ Vector((0.0, 0.75 * L, 0.0))
    part = part or ("full" if w == "spear" else "blade")
    if w == "spear":
        hand = bpy.data.objects["SAINT_spear_hand"]
        Mh = U.world_matrix_of(hand)
        D = C.DIMS["SAINT"]
        base = D["spear_length"] - D["spear_blade_length"]
        r = {"blade": (base, D["spear_length"]), "shaft": (0.0, base), "full": (0.0, D["spear_length"])}[part]
        return Mh @ Vector((0.0, r[0], 0.0)), Mh @ Vector((0.0, r[1], 0.0))
    c = PZ.char_of(rig)
    return (U.world_pos_of(bpy.data.objects[f"{c}_katana_base"]), U.world_pos_of(bpy.data.objects[f"{c}_katana_tip"]))


def seg_seg(p1, q1, p2, q2):
    """Closest points of segments p1q1 and p2q2: (distance, c1, c2, s, t)."""
    d1, d2, r = q1 - p1, q2 - p2, p1 - p2
    a, e, f = d1.dot(d1), d2.dot(d2), d2.dot(r)
    if a <= 1e-12 and e <= 1e-12:
        return (p1 - p2).length, p1, p2, 0.0, 0.0
    if a <= 1e-12:
        s, t = 0.0, min(1.0, max(0.0, f / e))
    else:
        c = d1.dot(r)
        if e <= 1e-12:
            t, s = 0.0, min(1.0, max(0.0, -c / a))
        else:
            b = d1.dot(d2)
            den = a * e - b * b
            s = min(1.0, max(0.0, (b * f - c * e) / den)) if den > 1e-12 else 0.0
            t = (b * s + f) / e
            if t < 0.0:
                t, s = 0.0, min(1.0, max(0.0, -c / a))
            elif t > 1.0:
                t, s = 1.0, min(1.0, max(0.0, (b - c) / a))
    c1, c2 = p1 + d1 * s, p2 + d2 * t
    return (c1 - c2).length, c1, c2, s, t


def offset_ctrl(rig, f, delta_world, falloff=3, clk=None):
    """Translate the sword controller by `delta_world` at film frame f, fading out over +-falloff STORY frames
    (cosine weights; the frames just outside are anchored at their current values) - the clash nudge."""
    rig = rig_of(rig)
    clk = clk or Clock(f)
    ob = PZ._ctrl_obj(rig)
    base = clk.span(f)
    samples = []
    for k in range(-falloff - 1, falloff + 2):
        fk = round(clk(base + k), 3)
        w = 0.5 * (1.0 + math.cos(math.pi * k / (falloff + 1)))
        samples.append((fk, w, PZ.current_ctrl_matrix(rig, fk).translation.copy(), rig_matrix(rig, fk).to_3x3()))
    for fk, w, loc, R in samples:
        U.key(ob, "location", fk, tuple(loc + R.inverted() @ (Vector(delta_world) * w)), interp='BEZIER')
    _ensure_ik(rig, f)


def offset_root(rig, f, delta_world, falloff=6, clk=None):
    """Translate the ROOT horizontally by delta_world (x, y) at film frame f with a cosine falloff over +-falloff
    story frames (the reach assist of clash(): a half step closer instead of an over-stretched arm)."""
    rig = rig_of(rig)
    clk = clk or Clock(f)
    base = clk.span(f)
    dx, dy = float(delta_world[0]), float(delta_world[1])
    samples = []
    for k in range(-falloff - 1, falloff + 2):
        fk = round(clk(base + k), 3)
        w = 0.5 * (1.0 + math.cos(math.pi * k / (falloff + 1)))
        x, y, z, a = root_at(rig, fk)
        samples.append((fk, w, x, y, z))
    for fk, w, x, y, z in samples:
        U.key(rig, "location", fk, (x + dx * w, y + dy * w, z), interp='BEZIER')


FRAC_RANGE = {   # where along each blade a contact may slide when the fraction is automatic (0 = base, 1 = tip)
    "att": {"katana": (0.45, 0.92), "spear": (0.55, 0.95)},
    "def": {"katana": (0.15, 0.80), "spear": (0.30, 0.90)},
}


def _default_fracs(wa, wb, kind):
    fa = {"katana": 0.72, "spear": 0.86, "kunai": 0.6}[wa]
    fb = {"katana": 0.40, "spear": 0.72, "kunai": 0.6}[wb]
    if kind == "blade_lock":
        fa = fb = 0.12
    return fa, fb


def _act_color(f):
    if f < 1633:
        return "gold"
    if f < 2497:
        return "fire"
    return "steel"


def clash(attacker, defender, f, point=None, strength=1.0, kind="clash", tags=None, emit_event=True, sparks=None,
          att_frac=None, def_frac=None, weapon_a=None, weapon_b=None, nudge="defender", falloff=3, place=True,
          gate=None, flash=None, assist=0.15, root_falloff=6):
    """Blade contact at film frame f.

    place=True: both sword controllers are translated (their blade directions kept, cosine falloff over +-falloff
    story frames) so that the blades cross at `point` (world) - the attacker at att_frac of its blade, the defender
    at def_frac (None = automatic: the contact slides along each blade to the smallest, perpendicular move, within
    FRAC_RANGE - attacker 0.45-0.92, defender 0.15-0.80 of the blade); point=None -> the midpoint of the keyed
    blades' closest points.  Reach assist: the horizontal part of a controller move beyond `assist` m is given to
    the ROOT instead (offset_root, +-root_falloff story frames: a half step in, not an over-stretched arm).  weapon_a / weapon_b: 'katana' | 'spear' (the saint's spear: its shaft + blade
    segment) | 'kunai' (the shinobi's off-hand kunai - no controller: the attacker is nudged instead).
    The contact is REGISTERED and resolved later by resolve_clashes (lane_tools.end_lane): segment distance gate
    (CLASH_GATE 3 cm), nudge of the defender's controller, then vfx.sparks + events.emit(kind, pos, strength) at the
    final contact point.  kind: 'clash' | 'clash_heavy' | 'perfect_deflect' (adds vfx.flash_ring) | 'kunai_deflect'.
    sparks: dict of vfx.sparks overrides (count, speed, life, scale, color, direction, spread ...).
    Returns the registry entry (dict)."""
    a, d = rig_of(attacker), rig_of(defender)
    wa = weapon_a or weapon_at(a, f)
    wb = weapon_b or weapon_at(d, f)
    fa0, fb0 = _default_fracs(wa, wb, kind)
    auto_a, auto_b = att_frac is None, def_frac is None
    att_frac = fa0 if att_frac is None else att_frac
    def_frac = fb0 if def_frac is None else def_frac
    if wb == "kunai" and nudge == "defender":
        nudge = "attacker"
    clk = Clock(f)
    placed = {}
    if place:
        if point is None:
            if wb == "kunai":
                pb0, qb0 = actual_segment(d, f, "kunai")
            else:
                pb0, qb0 = ideal_segment(d, f, wb)
            pa0, qa0 = ideal_segment(a, f, wa)
            _, c1, c2, _, _ = seg_seg(pa0, qa0, pb0, qb0)
            point = (c1 + c2) * 0.5
        point = Vector(point)
        for r, w, frac, auto, rng in ((a, wa, att_frac, auto_a, FRAC_RANGE["att"].get(wa, (0.45, 0.92))),
                                      (d, wb, def_frac, auto_b, FRAC_RANGE["def"].get(wb, (0.15, 0.80)))):
            if w == "kunai":
                continue
            y0, y1 = weapon_range(r, w, "full" if w == "spear" else "blade", f)
            Mw = rig_matrix(r, f) @ PZ.current_ctrl_matrix(r, f)
            dirw = (Mw.to_3x3() @ AXIS_Y).normalized()
            if auto and kind != "blade_lock":     # slide the contact along the blade: the smallest (perpendicular) move
                t = ((point - Mw.translation).dot(dirw) - y0) / (y1 - y0)
                frac = min(rng[1], max(rng[0], t))
            want = point - dirw * (y0 + (y1 - y0) * frac)
            delta = want - Mw.translation
            placed[r.name] = round(delta.length, 4)
            if assist is not None and delta.length > assist:
                horiz = Vector((delta.x, delta.y, 0.0))
                shift = horiz * max(0.0, 1.0 - assist / delta.length)
                if shift.length > 1e-3:
                    offset_root(r, f, shift, root_falloff, clk)
                    placed[r.name + ":root"] = round(shift.length, 4)
                    delta = delta - shift
            if delta.length > 0.30:
                _log(f"clash {f}: {r.name} controller moved {delta.length:.2f} m to reach the contact point")
            if delta.length > 1e-4:
                offset_ctrl(r, f, delta, falloff, clk)
    reg = dict(frame=float(f), attacker=a.name, defender=d.name, weapon_a=wa, weapon_b=wb, point=tuple(point) if point is not None else None,
               strength=float(strength), kind=kind, tags=list(tags or []), emit=bool(emit_event), sparks=dict(sparks or {}),
               nudge=nudge, falloff=int(falloff), gate=float(gate if gate is not None else CLASH_GATE), placed=placed,
               flash=flash, resolved=False, gap=None, gap_before=None, pos=None)
    _CLASHES.append(reg)
    _save_registry()
    return reg


def _save_registry():
    """Mirror the clash registry into scene['moves_clashes'] (JSON) so a saved scene keeps it (clash_report,
    choreo_diag on a .blend)."""
    import json
    try:
        bpy.context.scene["moves_clashes"] = json.dumps(_CLASHES, default=str)
    except Exception:                        # noqa: BLE001 - bookkeeping only
        pass


def _load_registry():
    """Restore the registry from scene['moves_clashes'] when this process has none (a scene opened from disk)."""
    import json
    if _CLASHES:
        return
    raw = bpy.context.scene.get("moves_clashes")
    if raw:
        try:
            _CLASHES.extend(json.loads(raw))
        except ValueError:
            pass


def clashes():
    """The clash registry (list of dicts; restored from the scene when opened from disk)."""
    _load_registry()
    return _CLASHES


def _measure(reg):
    a, d = bpy.data.objects[reg["attacker"]], bpy.data.objects[reg["defender"]]
    f = reg["frame"]
    pa, qa = actual_segment(a, f, reg["weapon_a"])
    pb, qb = actual_segment(d, f, reg["weapon_b"])
    return seg_seg(pa, qa, pb, qb) + (pa, qa, pb, qb)


def resolve_clashes(frame_range=None, gate=None, events_on=True, vfx_on=True):
    """Resolve every registered, unresolved clash with its frame inside frame_range (None = all): first the
    foot-plant bake of that range (bake_feet), then per clash: measure the evaluated blade segments, nudge the
    defender's (or, for kunai / nudge='attacker', the attacker's) controller until the segments are within the
    gate (3 cm; up to 4 passes), then vfx.sparks + events.emit at the contact point.  Called by
    lane_tools.end_lane(lane) with the lane span while the lane's actions are still active.  Returns a report
    dict(count, max_gap, over_gate, items)."""
    lo, hi = frame_range if frame_range is not None else (-math.inf, math.inf)
    bake_feet(None, (lo - 0.5, hi + 0.5) if frame_range is not None else None)
    items = []
    vfx = _module("vfx") if vfx_on else None
    for i, reg in enumerate(_CLASHES):
        if reg["resolved"] or not (lo - 6 <= reg["frame"] <= hi + 6):
            continue
        g = gate if gate is not None else reg["gate"]
        f = reg["frame"]
        dist, c1, c2, s, t, pa, qa, pb, qb = _measure(reg)
        reg["gap_before"] = round(dist, 4)
        for _ in range(5):
            if dist <= 0.5 * g:
                break
            mover = reg["defender"] if reg["nudge"] == "defender" else reg["attacker"]
            delta = (c1 - c2) if mover == reg["defender"] else (c2 - c1)
            prev = dist
            offset_ctrl(bpy.data.objects[mover], f, delta, reg["falloff"])
            dist, c1, c2, s, t, pa, qa, pb, qb = _measure(reg)
            if dist > 0.5 * prev and dist > 0.5 * g:        # the arm cannot follow (reach): half a step closer
                d2 = (c1 - c2) if mover == reg["defender"] else (c2 - c1)
                offset_root(bpy.data.objects[mover], f, (d2.x, d2.y), 5)
                dist, c1, c2, s, t, pa, qa, pb, qb = _measure(reg)
        pos = (c1 + c2) * 0.5
        reg.update(resolved=True, gap=round(dist, 4), pos=tuple(round(v, 4) for v in pos))
        if dist > g:
            _log(f"clash {f}: blades still {dist * 100:.1f} cm apart after nudging (IK reach?)")
        a = bpy.data.objects[reg["attacker"]]
        # spark direction: along the attacker's tip motion, lifted, away from the defender's blade
        tp0 = ideal_segment(a, f - 1, reg["weapon_a"])[1] if reg["weapon_a"] != "kunai" else qa
        vel = (qa - tp0)
        n = (qb - pb).normalized()
        vel = vel - n * vel.dot(n)
        dirn = (vel.normalized() * 0.8 + Vector((0.0, 0.0, 0.7))).normalized() if vel.length > 1e-4 else Vector((0, 0, 1))
        st = reg["strength"]
        if vfx is not None and hasattr(vfx, "sparks"):
            kw = dict(direction=tuple(dirn), count=int(40 + 70 * st), speed=3.5 + 1.8 * st, life=8 + 6 * st,
                      color=_act_color(f), scale=0.7 + 0.7 * st, seed=seed("clash", reg["attacker"], f, i))
            kw.update(reg["sparks"])
            try:
                vfx.sparks(f, tuple(pos), **kw)
            except Exception as e:           # noqa: BLE001 - never break a lane build on an effect
                _log(f"vfx.sparks failed at {f}: {e}")
            if reg["kind"] == "perfect_deflect" and hasattr(vfx, "flash_ring"):
                try:
                    vfx.flash_ring(f, tuple(pos), **(reg["flash"] or {}))
                except Exception as e:       # noqa: BLE001
                    _log(f"vfx.flash_ring failed at {f}: {e}")
        if reg["emit"] and events_on:
            etype = reg["kind"] if reg["kind"] in ("clash", "clash_heavy", "perfect_deflect", "kunai_deflect") else "clash"
            emit(int(round(f)), etype, pos=tuple(pos), strength=round(st, 3), tags=reg["tags"] or None,
                 who=who(a), weapons=f"{reg['weapon_a']}/{reg['weapon_b']}")
        items.append(dict(frame=f, attacker=reg["attacker"], defender=reg["defender"], kind=reg["kind"],
                          gap_before=reg["gap_before"], gap=reg["gap"], pos=reg["pos"]))
    _save_registry()
    gaps = [it["gap"] for it in items]
    return dict(count=len(items), max_gap=max(gaps) if gaps else 0.0,
                over_gate=[it for it in items if it["gap"] > (gate or CLASH_GATE)], items=items)


def clash_report(measure=True):
    """Every registered clash with its CURRENT blade gap in metres (build_scene's clash gate reads 'gap'):
    re-measured on the evaluated scene (after NLA assembly) when measure=True."""
    _load_registry()
    out = []
    for reg in _CLASHES:
        it = dict(frame=reg["frame"], attacker=reg["attacker"], defender=reg["defender"], kind=reg["kind"],
                  weapons=f"{reg['weapon_a']}/{reg['weapon_b']}", gap_resolved=reg["gap"], pos=reg["pos"],
                  span=reg.get("span"))
        if measure and reg["attacker"] in bpy.data.objects and reg["defender"] in bpy.data.objects:
            try:
                it["gap"] = round(_measure(reg)[0], 4)
            except Exception as e:           # noqa: BLE001
                it["gap"] = reg["gap"]
                it["note"] = str(e)
        else:
            it["gap"] = reg["gap"]
        out.append(it)
    return out


# =============================================================================================
# small keying helpers used by the macros
# =============================================================================================
def overlay(rig, f, deltas, interp='BEZIER'):
    """Add rotations {bone: (drx, dry, drz) deg} on top of the rig's keyed pose at film frame f and key them
    (breathing, recoils, hit reactions).  Returns f."""
    rig = rig_of(rig)
    for b, dr in deltas.items():
        cur = PZ.current_rot(rig, b, f)
        U.key(rig.pose.bones[b], "rotation_euler", f, tuple(math.radians(c + d) for c, d in zip(cur, dr)), interp=interp)
    return f


def hold(rig, f, bones=None, ctrl=True, hips=True):
    """Key the rig's CURRENT (evaluated from keys) body pose / controller at film frame f - pins a pose so a later
    key does not start its interpolation earlier (anticipation holds)."""
    rig = rig_of(rig)
    for b in (bones or PZ.BODY_BONES):
        cur = PZ.current_rot(rig, b, f)
        U.key(rig.pose.bones[b], "rotation_euler", f, tuple(math.radians(c) for c in cur), interp='BEZIER')
    if hips:
        U.key(rig.pose.bones["hips"], "location", f, PZ.current_hips_offset(rig, f), interp='BEZIER')
    if ctrl and arm_is_ik(rig, f):
        C.key_ctrl_matrix(PZ._ctrl_obj(rig), f, PZ.current_ctrl_matrix(rig, f), 'BEZIER')
    return f


def shift_ctrl(rig, f, delta_rig, spec=None, interp='BEZIER'):
    """Key the controller at f = (spec or its current matrix) translated by delta_rig (rig space, SHINOBI m)."""
    rig = rig_of(rig)
    M = ctrl_matrix(rig, spec, f) if spec is not None else PZ.current_ctrl_matrix(rig, f)
    M = Matrix.Translation(Vector(delta_rig) * S(rig)) @ M
    C.key_ctrl_matrix(PZ._ctrl_obj(rig), f, M, interp)
    return M


def lunge_root(rig, f0, f1, dist, ease="inout_quad", clk=None, facing=None):
    """Root moves `dist` m along its facing (negative = back) between film frames f0 and f1 (per-frame keys)."""
    rig = rig_of(rig)
    x, y, _, a = root_at(rig, f0)
    fwd = forward_vec(a if facing is None else facing)
    p1 = Vector((x, y, 0.0)) + fwd * dist
    root(rig, f0, (x, y), a, interp='LINEAR')
    return root_path(rig, f0, f1, (x, y), (p1.x, p1.y), ease=ease, clk=clk)


def default_guard(rig, f):
    """The guard a move recovers to: SAINT with his left hand on the saya -> 'low_1h'; spear in hand ->
    'spear_low'; otherwise 'chudan'."""
    rig = rig_of(rig)
    if PZ.char_of(rig) == "SAINT":
        if weapon_at(rig, f) == "spear":
            return "spear_low"
        if C.left_hand(rig, f) == "saya":
            return "low_1h"
    return "chudan"


# =============================================================================================
# stances, draw, sheathe
# =============================================================================================
def stance(rig, f, kind="chudan", hands="pose", hand_blend=3, mirror=False, breathe=0, clk=None):
    """Key a guard / stand pose (any POSES name: chudan, chudan_1h, low_1h, hasso, jodan, waki, gedan, relaxed,
    relaxed_saya, iai_crouch, listen, spear_high ...) at f.  hands='pose' applies its left hand (blend frames).
    breathe=N adds a subtle breath (chest +-0.8 deg) held for N story frames after f.  Returns f (+N)."""
    rig = rig_of(rig)
    pose(rig, f, kind, hands=hands, hand_blend=hand_blend, mirror=mirror)
    if breathe:
        clk = clk or Clock(f)
        n = max(1, int(breathe // 40))
        for i in range(1, n + 1):
            fk = clk(i * breathe / n)
            pose(rig, fk, kind, hands="keep", mirror=mirror, feet=False)
            overlay(rig, fk, {"chest": (0.8 * (-1) ** i, 0.0, 0.0), "neck": (-0.4 * (-1) ** i, 0.0, 0.0)})
        return clk(breathe)
    return f


def draw_sword(rig, f, end="chudan", two_hand=None):
    """Draw the katana: f = the frame the kissaki clears the koiguchi.  Right hand to the hilt (FK -> IK blend) and
    left hand to the saya from f-11, saya turned edge-out, the in-hand katana swapped in on the sheathed one
    (pop-free), pulled out along the saya with saya-biki, then swung up into `end` with the left hand joining the
    grip (two_hand None: the shinobi grips, the elder keeps his hand on the saya).  Events: draw.
    Returns the frame the guard is reached (f+8)."""
    rig = rig_of(rig)
    T = Clock(f)
    char = PZ.char_of(rig)
    hold(rig, T(-12), ctrl=False)
    pose(rig, T(-8), "draw_grab", hands="pose", hand_blend=3)
    M0 = ctrl_matrix(rig, "sheathed", T(-11))
    C.key_ctrl_matrix(PZ._ctrl_obj(rig), T(-11), M0, 'BEZIER')
    C.set_arm_mode(rig, T(-11), "ik", blend=3)
    C.key_ctrl_matrix(PZ._ctrl_obj(rig), T(-6), ctrl_matrix(rig, "sheathed", T(-6)), 'BEZIER')
    C.set_weapon_state(rig, T(-6), "drawn")
    pose(rig, T(-3), "draw_pull")
    pose(rig, T(0), "draw_clear")
    C.release_elbow(rig, T(1), "R")
    pose(rig, T(4), "draw_swing", hands="keep")
    if two_hand is None:
        two_hand = char == "SHINOBI"
    pose(rig, T(8), end, hands="pose" if two_hand else "keep", hand_blend=3)
    if not two_hand and PZ.spec_of(end).get("left") == "grip":
        C.set_left_hand(rig, T(8), "saya")
    PZ.key_saya(rig, T(10), 0.0, 0.0)
    emit(int(round(f)), "draw", who=who(rig), weapon="katana")
    emit(int(round(T(2))), "whoosh", who=who(rig), weapon="katana", strength=0.4)
    return T(8)


def sheathe(rig, f, speed="quick", end="relaxed_saya"):
    """Sheathe the katana: f = the click (tsuba home on the koiguchi).  quick: 10 story frames from the guard;
    slow: chiburi flick at f-40, the back of the blade laid across the left fist at the koiguchi at f-28, a slow slide
    to the click (S24b / S26 noto).  Afterwards the right hand leaves the hilt (IK -> FK) into `end`.
    Events: sheathe + tsuba_click at f.  Returns the end frame."""
    rig = rig_of(rig)
    T = Clock(f)
    if speed == "slow":
        hold(rig, T(-46))
        pose(rig, T(-40), "sheathe_slow_chiburi")
        emit(int(round(T(-41))), "whoosh", who=who(rig), weapon="katana", strength=0.3)
        pose(rig, T(-30), "sheathe_slow_1", hands="pose", hand_blend=4)
        pose(rig, T(-26), "sheathe_slow_1")
        for d, pull in ((-20, 0.62), (-14, 0.45), (-9, 0.30), (-5, 0.16), (-2, 0.06)):
            sp = PZ.resolve("sheathe_slow_2", rig)
            sp["ctrl"] = {"sheathed": pull}
            PZ.key_pose(rig, T(d), None, spec=sp, hands="keep")
    else:
        hold(rig, T(-12))
        pose(rig, T(-8), "sheathe_quick_1", hands="pose", hand_blend=2)
        pose(rig, T(-4), "sheathe_quick_2")
    pose(rig, T(0), "sheathe_done", hands="pose")
    C.set_weapon_state(rig, T(0), "sheathed")
    emit(int(round(f)), "sheathe", who=who(rig))
    emit(int(round(f)), "tsuba_click", who=who(rig), target=(rig, "hips"))
    C.set_arm_mode(rig, T(3), "fk", blend=4)
    pose(rig, T(8), end, hands="pose", ctrl=False)
    PZ.key_saya(rig, T(8), 0.0, 0.0)
    return T(8)


# =============================================================================================
# attacks
# =============================================================================================
SLASH_KINDS = ("diag_down_R", "diag_down_L", "rising_L", "rising_R", "horizontal_R", "horizontal_L", "overhead",
               "thrust")
SLASH_TIMING = {        # story frames: anticipation (to the windup), hold, strike (windup -> impact), follow, recover
    "default": dict(windup=6, hold=2, strike=3, follow=4, recover=9),
    "horizontal_R": dict(windup=6, hold=2, strike=4, follow=5, recover=9),
    "horizontal_L": dict(windup=6, hold=2, strike=4, follow=5, recover=9),
    "overhead": dict(windup=7, hold=3, strike=3, follow=4, recover=10),
    "thrust": dict(windup=7, hold=2, strike=3, follow=3, recover=10),
}
SAINT_TIMING = dict(windup=0.8, hold=0.5, strike=0.9)       # economical: shorter anticipation, same snap


def slash(rig, f, kind, windup=None, hold_frames=None, strike=None, follow=None, recover=None, lunge=0.0,
          two_hand=None, mirror=False, recover_to=None, whoosh=True, amplitude=1.0, lag=True, strength=0.8):
    """A sword cut; f = IMPACT frame (the blade crosses the target line - put it on the beat / the clash frame).
    kind in SLASH_KINDS.  Timeline (story frames, SLASH_TIMING; the SAINT anticipates less, SAINT_TIMING):
      f-(strike+hold+windup) .. f-(strike+hold): into the coiled windup pose (weight back)
      hold: coils 4 % further (anticipation)          f-strike .. f: the blade on an ARC to the strike pose
      f .. f+follow: follow-through arc, 6 % overshoot, settle 3 later       f+follow+recover: back to guard
    Hips lead / head lags one frame (successive breaking of joints).  lunge = metres the root drives forward
    between f-strike-1 and f+1 (the stepping foot is planted by the bake).  amplitude < 1 = smaller windup.
    two_hand True/False changes the grip at the windup; None keeps the lane's.  Events: whoosh at f-1.
    Returns the frame it ends (guard recovered)."""
    rig = rig_of(rig)
    if kind not in SLASH_KINDS:
        raise ValueError(f"unknown slash kind {kind!r}; one of {SLASH_KINDS}")
    tm = dict(SLASH_TIMING["default"], **SLASH_TIMING.get(kind, {}))
    if PZ.char_of(rig) == "SAINT":
        for k, v in SAINT_TIMING.items():
            tm[k] = tm[k] * v
    for k, v in (("windup", windup), ("hold", hold_frames), ("strike", strike), ("follow", follow),
                 ("recover", recover)):
        if v is not None:
            tm[k] = v
    T = Clock(f)
    w, h, s, fo, rc = tm["windup"], tm["hold"], tm["strike"], tm["follow"], tm["recover"]
    n_w, n_s, n_f = f"{kind}_windup", f"{kind}_strike", f"{kind}_follow"
    lag_d = {"hips": -1, "neck": 1, "head": 1} if lag else None
    recover_to = recover_to or default_guard(rig, f)
    if two_hand is not None:
        C.set_two_hand(rig, T(-(s + h + w)), bool(two_hand), blend=2)
    hold(rig, T(-(s + h + w)))
    wt = amplitude * (0.85 if PZ.char_of(rig) == "SAINT" else 1.0)
    pose(rig, T(-(s + h)), n_w, weight=wt, mirror=mirror)
    pose(rig, T(-s), n_w, weight=wt * 1.04, mirror=mirror, lag=lag_d, feet=False)
    Ma = PZ.current_ctrl_matrix(rig, T(-s))
    swing(rig, T(-s), T(0), Ma, ctrl_matrix(rig, n_s, T(0), mirror), ease="in_quad", clk=T)
    pose(rig, T(0), n_s, mirror=mirror, lag=lag_d, ctrl=False)
    swing(rig, T(0), T(fo), n_s, n_f, ease="out_cubic", clk=T, mirror=mirror, include_start=False)
    pose(rig, T(fo), n_f, weight=1.06, mirror=mirror, ctrl=False, feet=False)
    pose(rig, T(fo + 3), n_f, mirror=mirror)
    if lunge:
        x, y, _, a = root_at(rig, T(-s - 1))
        root(rig, T(-s - 2), (x, y), a, interp='LINEAR')
        lunge_root(rig, T(-s - 1), T(1), lunge, ease="inout_quad", clk=T)
    end = T(fo + rc)
    if recover_to:
        pose(rig, end, recover_to, hands="keep")
    if whoosh:
        emit(int(round(T(-1))), "whoosh", who=who(rig), weapon=weapon_at(rig, f), strength=round(strength, 2),
             target=(rig, "hand.R"))
    return end


def iai_slash(rig, f, kind="horizontal", side="L", lunge=0.5, recover=10, recover_to=None, pivot=None):
    """The quick-draw cut from the iai crouch; f = IMPACT.  f-9 fist on the hilt (in-hand blade swapped in on the
    sheathed one), f-6 blade 30 cm out with saya-biki, f-4 kissaki at the koiguchi, f-4..f the blade whips out on an
    arc into a one-handed horizontal cut from the left hip (kind 'horizontal', side 'L'; the left hand keeps pulling
    the saya back), f+4 follow-through out to the right, root lunging `lunge` m from f-6.  kind 'rising' ends in a
    rising cut instead.  Events: draw (f-4), whoosh (f-1).  Returns the recovered frame."""
    rig = rig_of(rig)
    T = Clock(f)
    hold(rig, T(-12))
    pose(rig, T(-9), "iai_crouch", hands="pose", hand_blend=2)
    C.key_ctrl_matrix(PZ._ctrl_obj(rig), T(-8), ctrl_matrix(rig, "sheathed", T(-8)), 'BEZIER')
    _ensure_ik(rig, T(-9))
    C.set_weapon_state(rig, T(-8), "drawn")
    pose(rig, T(-6), "iai_draw_1")
    pose(rig, T(-4), "iai_draw_2")
    C.release_elbow(rig, T(-3), "R")
    n_cut = "iai_cut" if kind == "horizontal" else "rising_R_strike"
    n_fo = "iai_follow" if kind == "horizontal" else "rising_R_follow"
    swing(rig, T(-4), T(0), PZ.current_ctrl_matrix(rig, T(-4)), ctrl_matrix(rig, n_cut, T(0), side == "R"),
          ease="in_quad", clk=T, pivot=pivot)
    pose(rig, T(0), n_cut, ctrl=False, mirror=side == "R", lag={"hips": -1, "head": 1})
    swing(rig, T(0), T(4), n_cut, n_fo, ease="out_cubic", clk=T, include_start=False, mirror=side == "R")
    pose(rig, T(4), n_fo, weight=1.05, ctrl=False, feet=False, mirror=side == "R")
    pose(rig, T(7), n_fo, mirror=side == "R")
    if lunge:
        lunge_root(rig, T(-6), T(0), lunge, ease="in_quad", clk=T)
    end = T(4 + recover)
    pose(rig, end, recover_to or default_guard(rig, end), hands="keep")
    PZ.key_saya(rig, end, 0.0, 0.0)
    emit(int(round(T(-4))), "draw", who=who(rig), weapon="katana", tags=["iai"])
    emit(int(round(T(-1))), "whoosh", who=who(rig), weapon="katana", strength=1.0, target=(rig, "hand.R"))
    return end


# =============================================================================================
# defence
# =============================================================================================
DEFLECT_KINDS = ("high", "mid_L", "mid_R", "low", "overhead_block")


def deflect(rig, f, kind, approach=4, recoil=1.0, recover=8, recover_to=None, hold_frames=0):
    """Parry / block; f = CONTACT frame.  The block pose is reached one story frame before the contact from the pose
    keyed `approach` frames earlier (pinned), recoils `recoil` x 7 cm back along the blow two frames after (trunk
    rocks back 4 deg, knees give), then recovers to guard.  kind in DEFLECT_KINDS.  Returns the end frame."""
    rig = rig_of(rig)
    if kind not in DEFLECT_KINDS:
        raise ValueError(f"unknown deflect kind {kind!r}; one of {DEFLECT_KINDS}")
    T = Clock(f)
    name = f"deflect_{kind}"
    hold(rig, T(-approach - 1))
    pose(rig, T(-1), name, lag={"head": 1})
    pose(rig, T(0), name, feet=False)
    if recoil:
        pose(rig, T(2), name, ctrl=False, feet=False)
        shift_ctrl(rig, T(2), (0.0, 0.07 * recoil, -0.03 * recoil), spec=name)
        overlay(rig, T(2), {"chest": (-4.0 * recoil, 0.0, 0.0), "spine": (-2.0 * recoil, 0.0, 0.0)})
    end = T(2 + hold_frames + recover)
    if hold_frames:
        pose(rig, T(2 + hold_frames), name, feet=False)
    pose(rig, end, recover_to or default_guard(rig, f), hands="keep")
    return end


def perfect_deflect(rig, f, attacker=None, point=None, strength=1.0, flash=None, stagger_attacker=True, **clash_kw):
    """The sharp perfect-deflect snap; f = contact.  The defender snaps into 'perfect_deflect' in 2 story frames
    (8 % overshoot, settle), a clash of kind 'perfect_deflect' is registered with the attacker (flash ring + event at
    resolve time) and the attacker is thrown off balance (stagger 2 frames later).  Returns the end frame."""
    rig = rig_of(rig)
    T = Clock(f)
    hold(rig, T(-2))
    pose(rig, T(0), "perfect_deflect", lag={"head": 1})
    pose(rig, T(1), "perfect_deflect", weight=1.08, feet=False)
    pose(rig, T(5), "perfect_deflect")
    if attacker is not None:
        clash(attacker, rig, f, point=point, strength=strength, kind="perfect_deflect", flash=flash, **clash_kw)
        if stagger_attacker:
            stagger(attacker, T(2), direction="back", dist=0.35)
    else:
        emit(int(round(f)), "perfect_deflect", who=who(rig), strength=strength)
    return T(12)


# =============================================================================================
# locomotion: procedural gait (root profile + world footfalls + body keys)
# =============================================================================================
GAITS = {   # step = step length (SHINOBI m), stance = fraction of a cycle a foot is on the ground, ahead = where the
            # foot lands ahead of the pelvis (fraction of a step), body = (contact, pass) poses, strength = step event
    "walk": dict(step=0.66, stance=0.62, ahead=0.5, body=("walk_contact", "walk_pass"), strength=0.35, heel_off=28),
    "run": dict(step=1.30, stance=0.38, ahead=0.18, body=("run_contact", "run_flight"), strength=0.6, heel_off=35),
    "dash": dict(step=1.15, stance=0.45, ahead=0.22, body=("dash", "dash"), strength=0.8, heel_off=40),
}
TRUNK = ("hips", "spine", "chest", "neck", "head")
ARMS = ("shoulder.L", "upper_arm.L", "forearm.L", "hand.L", "shoulder.R", "upper_arm.R", "forearm.R", "hand.R")


def _speed_profile(n, start, stop, ramp):
    """Cumulative distance fraction g[i] for story frames i = 0..n of a trapezoid velocity profile (smooth ramps)."""
    n = max(1, int(round(n)))
    rs = min(0.45, ramp / n) if start else 0.0
    re = min(0.45, ramp / n) if stop else 0.0
    v = []
    for i in range(n + 1):
        x = i / n
        a = 1.0
        if rs > 0 and x < rs:
            a = U.ease(x / rs, "smooth")
        if re > 0 and x > 1 - re:
            a = min(a, U.ease((1 - x) / re, "smooth"))
        v.append(max(a, 0.02))
    g = [0.0]
    for i in range(1, n + 1):
        g.append(g[-1] + 0.5 * (v[i - 1] + v[i]))
    return [x / g[-1] for x in g]


def _partial_spec(rig, name, bones, mirror=False, weight_bones=None):
    sp = PZ.resolve(name, rig, mirror)
    sp["body"] = {b: r for b, r in sp["body"].items() if b in bones}
    sp.pop("legs", None)
    sp["ctrl"] = None
    sp["partial"] = True
    return sp


def _last_foot_world(rig, side, f):
    keys = _world_foot_keys(rig, side, -math.inf, f)
    return (Vector((keys[-1]["bw"].x, keys[-1]["bw"].y)), keys[-1]["yw"]) if keys else (None, None)


def walk(rig, f0, f1, p0, p1, facing=None, phase=0.0, stride=None, start=True, stop=True, upper=None, gait="walk",
         lead="L", width=None, events=True, end_pose=None, body_weight=1.0):
    """Walk (gait 'walk' | 'run' | 'dash') from world p0 at f0 to p1 at f1 (xy).  facing None = along the path;
    a fixed facing walks sideways / backwards.  The root follows a trapezoid speed profile (ease in when start,
    ease out when stop; phase > 0 = already moving at f0 - mid-stride, no ramp); feet are planted as WORLD foot
    keys at computed footfalls (stride = step length, SHINOBI m; `lead` foot moves first; the trailing foot closes
    at the end) and baked by bake_feet; the trunk / arms follow the gait keys (walk_contact / walk_pass, mirrored per
    side); upper = a pose whose arms / sword controller / left hand ride on top (e.g. 'relaxed_saya', 'chudan').
    Events: step at every footfall (+ dash).  Returns f1."""
    rig = rig_of(rig)
    g = GAITS[gait]
    s = S(rig)
    p0 = Vector(p0[:2]) if p0 is not None else Vector(root_at(rig, f0)[:2])
    p1 = Vector(p1[:2])
    D = (p1 - p0).length
    clk = Clock(f0)
    N = clk.span(f1)
    u = (p1 - p0).normalized() if D > 1e-6 else forward_of(rig, f0).to_2d()
    head = facing_to((0, 0), tuple(u)) if facing is None else facing
    L = (stride or g["step"]) * s
    n_steps = max(1, int(round(D / L))) if D > 0.05 else 0
    L = D / n_steps if n_steps else L
    w = (width if width is not None else 0.19) * s
    moving_start = (phase or 0.0) > 0.0 or not start
    prof = _speed_profile(N, start and not moving_start, stop, ramp=14.0 if gait == "walk" else 8.0)
    nf = len(prof) - 1

    def s_at(story):                      # path distance at story time
        x = min(max(story, 0.0), nf)
        i = min(int(x), nf - 1)
        return D * (prof[i] + (prof[i + 1] - prof[i]) * (x - i))

    def t_at(dist):                       # story time at path distance
        target = dist / D if D > 0 else 0.0
        for i in range(nf):
            if prof[i + 1] >= target:
                seg = prof[i + 1] - prof[i]
                return i + ((target - prof[i]) / seg if seg > 1e-9 else 0.0)
        return float(nf)

    # ---- root
    a0 = root_at(rig, f0)[3]
    for i in range(nf + 1):
        fk = clk(i)
        if fk > f1 + 1e-6:
            break
        q = p0 + u * s_at(i)
        fa = head if facing is not None or D < 1e-6 else head
        turn_u = min(1.0, i / max(1.0, min(8.0, nf)))
        root(rig, fk, (q.x, q.y), a0 + _angle_diff(fa, a0) * U.ease(turn_u, "smooth"), interp='LINEAR')
    if n_steps == 0:
        return f1
    # ---- footfalls
    lat = left_vec(head).to_2d()
    phi0 = 0.25 if not moving_start else 0.25 + float(phase)
    first = "L" if lead == "L" else "R"
    other = "R" if first == "L" else "L"
    side_sign = {"L": 1.0, "R": -1.0}
    swing_cycles = 1.0 - g["stance"]
    contacts = []
    m = 1
    while True:
        phi_c = m * 0.5
        dist_c = (phi_c - phi0) * 2 * L
        if dist_c > D - 1e-6 or dist_c < 0:
            if dist_c < 0:
                m += 1
                continue
            break
        foot = first if m % 2 == 1 else other
        land = min(D, dist_c + g["ahead"] * L)
        lift = max(phi0, phi_c - swing_cycles) if contacts or not moving_start else phi_c - swing_cycles
        contacts.append(dict(foot=foot, t=t_at(dist_c), land=land, t_lift=t_at(max(0.0, (lift - phi0) * 2 * L))))
        m += 1
    last = {}
    for sd in ("L", "R"):
        pw, yw = _last_foot_world(rig, sd, f0)
        if pw is None or moving_start:
            pw = p0 + lat * side_sign[sd] * w * 0.5
        last[sd] = pw
        if not moving_start:
            PZ.register_foot(rig, f0, sd, (pw.x, pw.y, _ball_rest_z(rig, sd)), head, 0.0, space="WORLD", src=gait)
    for c in contacts:
        sd = c["foot"]
        fl, fc = clk(c["t_lift"]), clk(c["t"])
        if fc - fl < 1.0:
            fl = fc - 1.0
        PZ.register_foot(rig, fl, sd, (last[sd].x, last[sd].y, _ball_rest_z(rig, sd)), head, g["heel_off"],
                         space="WORLD", src=gait)
        q = p0 + u * c["land"] + lat * side_sign[sd] * w * 0.5
        PZ.register_foot(rig, fc, sd, (q.x, q.y, _ball_rest_z(rig, sd)), head, 0.0, space="WORLD", src=gait)
        last[sd] = q
        if events:
            _EVENTED_STEPS.add((rig.name, sd, round(fc, 2)))
            emit(int(round(fc)), "step", who=who(rig), strength=g["strength"], gait=gait)
    # closing step of the trailing foot when stopping
    if stop:
        last_c = contacts[-1]["foot"]
        trail = "L" if last_c == "R" else "R"
        q = p1 + lat * side_sign[trail] * w * 0.5
        if (q - last[trail]).length > PLANT_TOL:
            fl = clk(contacts[-1]["t"] + 0.5)
            fc = max(fl + 4.0, min(clk(N), clk(contacts[-1]["t"] + 8.5)))
            PZ.register_foot(rig, fl, trail, (last[trail].x, last[trail].y, _ball_rest_z(rig, trail)), head, 15.0,
                             space="WORLD", src=gait)
            PZ.register_foot(rig, fc, trail, (q.x, q.y, _ball_rest_z(rig, trail)), head, 0.0, space="WORLD", src=gait)
            if events:
                _EVENTED_STEPS.add((rig.name, trail, round(fc, 2)))
                emit(int(round(fc)), "step", who=who(rig), strength=g["strength"] * 0.6, gait=gait)
        lead_f = last_c
        PZ.register_foot(rig, f1, lead_f, (last[lead_f].x, last[lead_f].y, _ball_rest_z(rig, lead_f)), head, 0.0,
                         space="WORLD", src=gait)
    # ---- body
    body_bones = TRUNK + (() if upper else ARMS)
    back = facing is not None and abs(_angle_diff(facing_to((0, 0), tuple(u)), facing)) > 100
    cn, pn = g["body"]
    for i, c in enumerate(contacts):
        fc = clk(c["t"])
        mir = c["foot"] == "L"
        wgt = body_weight * (0.5 if back else 1.0)
        sp = _partial_spec(rig, cn, body_bones, mirror=mir)
        PZ.key_pose(rig, fc, None, spec=sp, weight=wgt, legs=False, feet=False, ctrl=False, hands="keep")
        t_next = contacts[i + 1]["t"] if i + 1 < len(contacts) else min(nf, c["t"] + (contacts[1]["t"] - contacts[0]["t"] if len(contacts) > 1 else 8))
        fp = clk((c["t"] + t_next) * 0.5)
        if fp < f1 - 0.5:
            sp = _partial_spec(rig, pn, body_bones, mirror=mir)
            PZ.key_pose(rig, fp, None, spec=sp, weight=wgt, legs=False, feet=False, ctrl=False, hands="keep")
        if upper:
            pose(rig, fc, upper, legs=False, feet=False)
    if upper:
        pose(rig, f0, upper, legs=False, feet=False, hands="pose", hand_blend=3)
        pose(rig, f1, upper, legs=False, feet=False)
    if stop:
        ep = end_pose or upper or ("relaxed" if not arm_is_ik(rig, f1) else default_guard(rig, f1))
        sp = _partial_spec(rig, ep, TRUNK + (() if upper else ARMS))
        PZ.key_pose(rig, f1, None, spec=sp, legs=False, feet=False, ctrl=False, hands="keep")
    if gait == "dash" and events:
        emit(int(round(f0)), "dash", who=who(rig), strength=1.0)
    return f1


def run(rig, f0, f1, p0, p1, **kw):
    """walk(..., gait='run'): flight phase, forward lean, pumping arms."""
    kw.setdefault("gait", "run")
    return walk(rig, f0, f1, p0, p1, **kw)


def dash(rig, f0, f1, p0, p1, start=False, stop=True, upper=None, **kw):
    """Explosive low dash (gait 'dash': long low strides, trunk pitched forward, blade trailing - the elder's iai
    dash in S07): already at speed at f0 unless start=True.  Returns f1."""
    kw.setdefault("gait", "dash")
    rig = rig_of(rig)
    out = walk(rig, f0, f1, p0, p1, start=start, stop=stop, upper=upper, phase=0.0 if start else 0.3, **kw)
    if upper is None:
        pose(rig, f0, "dash", legs=False, feet=False, ctrl=arm_is_ik(rig, f0))
    return out


def strafe(rig, f0, f1, center, radius, a0, a1, face=None, step=0.42, events=True, upper=None):
    """Circle-strafe around `center` (xy) at `radius` from angle a0 to a1 (degrees CCW from +X about the centre,
    the act1b convention), facing the centre (or face = a fixed facing angle / an (x, y) target).  Shuffle footwork:
    the foot on the travel side steps out, the other closes - legs never cross.  Body alternates strafe_open /
    strafe_cross (or `upper` rides on top).  Events: step.  Returns f1."""
    rig = rig_of(rig)
    clk = Clock(f0)
    N = clk.span(f1)
    s = S(rig)
    cx, cy = center
    arc_len = abs(math.radians(a1 - a0)) * radius
    n = max(1, int(round(arc_len / (step * s))))
    prof = _speed_profile(N, True, True, ramp=6.0)

    def pos(frac):
        a = math.radians(a0 + (a1 - a0) * frac)
        return Vector((cx + radius * math.cos(a), cy + radius * math.sin(a)))

    def face_at(q):
        if face is None:
            return facing_to(tuple(q), (cx, cy))
        if isinstance(face, (int, float)):
            return float(face)
        return facing_to(tuple(q), face)

    nf = len(prof) - 1
    for i in range(nf + 1):
        q = pos(prof[i])
        root(rig, clk(i), (q.x, q.y), face_at(q), interp='LINEAR')
    # travel side: tangent direction vs the character's left
    q0, q1 = pos(0.0), pos(0.05)
    tangent = (q1 - q0).normalized()
    fa = face_at(q0)
    lead = "L" if tangent.dot(left_vec(fa).to_2d()) > 0 else "R"
    trail = "R" if lead == "L" else "L"
    w = 0.26 * s
    sign = {"L": 1.0, "R": -1.0}
    last = {}
    for sd in ("L", "R"):
        pw, _ = _last_foot_world(rig, sd, f0)
        last[sd] = pw if pw is not None else q0 + left_vec(fa).to_2d() * sign[sd] * w * 0.5
        PZ.register_foot(rig, f0, sd, (last[sd].x, last[sd].y, _ball_rest_z(rig, sd)), fa, 0.0, space="WORLD",
                         src="strafe")

    def t_at(frac):
        for i in range(nf):
            if prof[i + 1] >= frac:
                seg = prof[i + 1] - prof[i]
                return i + ((frac - prof[i]) / seg if seg > 1e-9 else 0.0)
        return float(nf)

    for k in range(1, n + 1):
        for sd, lag_frac, extra in ((lead, -0.35, 1.25), (trail, 0.15, -0.25)):
            frac = min(1.0, (k + lag_frac) / n)
            q = pos(frac)
            fq = face_at(q)
            target = q + left_vec(fq).to_2d() * sign[sd] * (w * 0.5 + (0.06 * s if sd == lead and k < n else 0.0))
            fl = clk(max(0.0, t_at(max(0.0, (k - 1 + lag_frac) / n))))
            fc = clk(t_at(frac))
            if fc - fl < 2.0:
                fl = fc - 2.0
            PZ.register_foot(rig, fl, sd, (last[sd].x, last[sd].y, _ball_rest_z(rig, sd)), fq, 8.0, space="WORLD",
                             src="strafe")
            PZ.register_foot(rig, fc, sd, (target.x, target.y, _ball_rest_z(rig, sd)), fq, 0.0, space="WORLD",
                             src="strafe")
            last[sd] = target
            if events:
                _EVENTED_STEPS.add((rig.name, sd, round(fc, 2)))
                emit(int(round(fc)), "step", who=who(rig), strength=0.3, gait="strafe")
            b = "strafe_open" if sd == lead else "strafe_cross"
            sp = _partial_spec(rig, b, TRUNK, mirror=(lead == "L"))
            PZ.key_pose(rig, fc, None, spec=sp, legs=False, feet=False, ctrl=False, hands="keep")
    if upper:
        pose(rig, f0, upper, legs=False, feet=False)
        pose(rig, f1, upper, legs=False, feet=False)
    return f1


def step(rig, f0, f1, p1, facing=None, lead=None, events=True):
    """One adjusting step (shuffle): the root glides from where it is to p1 (xy) and turns to `facing`; the foot on
    the travel side steps first, the other closes.  Returns f1."""
    rig = rig_of(rig)
    x, y, _, a = root_at(rig, f0)
    fa = a if facing is None else facing
    root(rig, f0, (x, y), a, interp='LINEAR')
    root_path(rig, f0, f1, (x, y), p1, facing1=fa, ease="inout_quad")
    d = Vector(p1[:2]) - Vector((x, y))
    if d.length < 0.02:
        return f1
    ld = lead or ("L" if d.normalized().dot(left_vec(fa).to_2d()) > 0 or
                  d.normalized().dot(forward_vec(fa).to_2d()) > 0.7 else "R")
    tr = "R" if ld == "L" else "L"
    clk = Clock(f0)
    n = clk.span(f1)
    for sd, t0, t1 in ((ld, 0.0, 0.6), (tr, 0.4, 1.0)):
        pw, yw = _last_foot_world(rig, sd, f0)
        if pw is None:
            continue
        PZ.register_foot(rig, clk(n * t0), sd, (pw.x, pw.y, _ball_rest_z(rig, sd)), yw, 10.0, space="WORLD", src="step")
        q = pw + d
        PZ.register_foot(rig, clk(n * t1), sd, (q.x, q.y, _ball_rest_z(rig, sd)), fa + _angle_diff(yw, a), 0.0,
                         space="WORLD", src="step")
        if events:
            _EVENTED_STEPS.add((rig.name, sd, round(clk(n * t1), 2)))
            emit(int(round(clk(n * t1))), "step", who=who(rig), strength=0.3)
    return f1


def turn(rig, f0, f1, facing, pivot_feet=True):
    """Turn on the spot to `facing` (deg) between f0 and f1 (feet pivot on their balls, then re-plant).  Returns f1."""
    rig = rig_of(rig)
    x, y, _, a = root_at(rig, f0)
    root(rig, f0, (x, y), a, interp='BEZIER')
    root(rig, f1, (x, y), facing, interp='BEZIER')
    if pivot_feet:
        for sd in ("L", "R"):
            pw, yw = _last_foot_world(rig, sd, f0)
            if pw is None:
                continue
            PZ.register_foot(rig, f0, sd, (pw.x, pw.y, _ball_rest_z(rig, sd)), yw, 0.0, space="WORLD", src="turn")
            loc = Matrix.Rotation(math.radians(_angle_diff(facing, a)), 3, 'Z') @ Vector((pw.x - x, pw.y - y, 0.0))
            PZ.register_foot(rig, f1, sd, (x + loc.x, y + loc.y, _ball_rest_z(rig, sd)), yw + _angle_diff(facing, a),
                             0.0, space="WORLD", src="turn")
    return f1


# =============================================================================================
# evasion, falls, contact moves
# =============================================================================================
def _feet_air(rig, f):
    """Register both feet as NOT planted at f (sliding / airborne phases: the bake leaves them to the pose)."""
    for sd in ("L", "R"):
        PZ.register_foot(rig, f, sd, (0.0, 0.0, 0.0), 0.0, 0.0, space="RIG", air=True, src="air")


def dodge(rig, f, direction="left", dist=0.75, recover=8, recover_to=None):
    """Evasion; f = the moment the attack passes (the dodge is complete).  'left' / 'right' = sidestep (weight thrown
    over the outside foot, trunk leaning away), 'back' = hop back.  The root travels `dist` m from f-4 to f+1 (fast
    out, soft stop).  Events: dash (f-3).  Returns the end frame."""
    rig = rig_of(rig)
    T = Clock(f)
    x, y, _, a = root_at(rig, T(-4))
    if direction in ("left", "right"):
        v = left_vec(a) * (1.0 if direction == "left" else -1.0)
        name, mir = "dodge_side", direction == "right"
    else:
        v = -forward_vec(a)
        name, mir = "dodge_back", False
    hold(rig, T(-5))
    pose(rig, T(-2), name, weight=0.6, mirror=mir, feet=False)
    pose(rig, T(0), name, mirror=mir)
    root(rig, T(-4), (x, y), a, interp='LINEAR')
    p1 = Vector((x, y, 0.0)) + v * dist
    root_path(rig, T(-4), T(1), (x, y), (p1.x, p1.y), ease="out_cubic", clk=T)
    pose(rig, T(2), name, mirror=mir, feet=False)
    end = T(2 + recover)
    pose(rig, end, recover_to or default_guard(rig, f))
    emit(int(round(T(-3))), "dash", who=who(rig), strength=0.5)
    return end


def duck(rig, f, hold_frames=6, recover=8, recover_to=None):
    """Drop under a sweep; f = lowest moment (the weapon passes over).  Down in 3 story frames, held, back up to
    guard.  Returns the end frame."""
    rig = rig_of(rig)
    T = Clock(f)
    hold(rig, T(-4))
    pose(rig, T(-1), "duck", weight=1.05)
    pose(rig, T(0), "duck", feet=False)
    pose(rig, T(hold_frames), "duck")
    end = T(hold_frames + recover)
    pose(rig, end, recover_to or default_guard(rig, f))
    return end


def jump(rig, f0, f1, p0=None, p1=None, apex=0.9, crouch=5, land=None, recover=8, air_pose="jump_air",
         land_pose="jump_land", recover_to=None, events=True):
    """Jump: f0 = take-off, f1 = touchdown; root from p0 to p1 (xy; None = where it is / same place) on a parabola
    with its apex `apex` m above the ground (root height).  Anticipation crouch `crouch` story frames before f0, air
    pose at the apex (feet not planted), landing crouch at f1 (+2 deeper), recovery.  Events: jump, land.
    Returns the end frame."""
    rig = rig_of(rig)
    T0, T1 = Clock(f0), Clock(f1)
    x, y, _, a = root_at(rig, f0)
    p0 = (x, y) if p0 is None else p0
    p1 = p0 if p1 is None else p1
    hold(rig, T0(-crouch - 2))
    pose(rig, T0(-crouch * 0.4), "jump_crouch")
    pose(rig, f0, "jump_crouch", weight=0.7)
    root(rig, T0(-crouch - 2), p0, a, interp='LINEAR')
    root(rig, f0, p0, a, interp='LINEAR')
    n = T0.span(f1)
    for i in range(1, int(math.ceil(n))):
        fk = T0(i)
        u = i / n
        q = Vector(p0).lerp(Vector(p1), u)
        root(rig, fk, (q.x, q.y), a, z=4.0 * apex * u * (1.0 - u), interp='LINEAR')
    root(rig, f1, p1, a, interp='LINEAR')
    pose(rig, T0(n * 0.45), air_pose)
    pose(rig, T1(-1), air_pose, weight=0.5, feet=False)
    pose(rig, f1, land_pose, weight=0.8)
    pose(rig, T1(2), land_pose, weight=1.05, feet=False)
    end = T1(2 + recover)
    pose(rig, end, recover_to or default_guard(rig, f1))
    if events:
        emit(int(round(f0)), "jump", who=who(rig))
        emit(int(round(f1)), "land", who=who(rig), strength=round(min(1.0, 0.4 + apex * 0.5), 2))
    return end


def plunge(rig, f0, f1, p0=None, p1=None, apex=1.2, impact=None, recover=10, recover_to=None):
    """Aerial overhead strike: take-off f0, touchdown f1 (jump parabola, apex m); in the air the blade is raised
    high behind the head (plunge_windup) and driven down onto the target at `impact` (default f1-3, the clash
    frame), landing in a deep crouch (plunge_land).  Events: jump, whoosh (impact-1), land.  Returns the end frame."""
    rig = rig_of(rig)
    T1 = Clock(f1)
    impact = impact if impact is not None else T1(-3)
    Ti = Clock(impact)
    end = jump(rig, f0, f1, p0, p1, apex=apex, air_pose="plunge_windup", land_pose="plunge_land", recover=recover,
               recover_to=recover_to)
    pose(rig, Ti(-3), "plunge_windup", feet=False)
    swing(rig, Ti(-3), impact, "plunge_windup", "plunge_strike", ease="in_quad", clk=Ti)
    pose(rig, impact, "plunge_strike", ctrl=False, lag={"head": 1})
    swing(rig, impact, f1, "plunge_strike", "plunge_land", ease="out_quad", clk=Ti, include_start=False)
    emit(int(round(Ti(-1))), "whoosh", who=who(rig), weapon="katana", strength=1.0, target=(rig, "hand.R"))
    return end


def roll(rig, f0, f1, p0=None, p1=None, face_end=None, recover=6, recover_to=None):
    """Forward shoulder roll from p0 (f0) to p1 (f1) (DIRECTION: rolls go perpendicular to the line, never past the
    opponent - the lane picks p1).  The rig faces the travel direction, tucks (roll_tuck) and turns 360 deg about
    its lateral axis around the tucked body centre (the root is keyed per frame), comes up on one knee (roll_rise)
    and turns to `face_end` (default: its facing at f0).  Events: roll.  Returns the end frame."""
    rig = rig_of(rig)
    T = Clock(f0)
    x, y, _, a = root_at(rig, f0)
    p0 = (x, y) if p0 is None else p0
    d = Vector(p1[:2]) - Vector(p0[:2])
    head = facing_to(p0, p1) if d.length > 1e-3 else a
    face_end = a if face_end is None else face_end
    hold(rig, T(-4))
    pose(rig, T(-2), "jump_crouch", weight=0.8)
    root(rig, T(-2), p0, a, interp='LINEAR')
    n = T.span(f1)
    hc = 0.42 * S(rig)
    pose(rig, T(1), "roll_tuck")
    _feet_air(rig, T(0.5))
    pose(rig, T(n - 2), "roll_tuck", feet=False)
    last_i = int(math.floor(n)) - 1
    for i in range(0, last_i + 1):
        fk = T(i)
        u = i / max(1, last_i)
        th = 360.0 * U.ease(u, "inout_quad")
        c = Vector(p0[:2]).lerp(Vector(p1[:2]), U.ease(i / n, "inout_quad"))
        R = Matrix.Rotation(math.radians(head), 3, 'Z') @ Matrix.Rotation(math.radians(th), 3, 'X')
        off = R @ Vector((0.0, 0.0, -hc))
        z = hc * U.ease(min(1.0, i / 2.0), "smooth") * (1.0 - U.ease(max(0.0, (i - last_i + 2) / 2.0), "smooth"))
        yaw = a + _angle_diff(head, a) * U.ease(min(1.0, i / 2.0), "smooth")
        root(rig, fk, (c.x + off.x, c.y + off.y), yaw, z=max(0.0, z + hc + off.z - hc), interp='LINEAR', tilt=(th, 0.0))
    fl = T(last_i)
    U.set_key_interp_at(rig, fl, 'CONSTANT', "rotation_euler")
    root(rig, f1, p1, head, interp='BEZIER', tilt=(0.0, 0.0))
    pose(rig, f1, "roll_rise")
    end = T(n + recover)
    x1, y1 = p1[:2]
    root(rig, end, (x1, y1), face_end, interp='BEZIER')
    pose(rig, end, recover_to or default_guard(rig, f1))
    emit(int(round(T(1))), "roll", who=who(rig))
    return end


def stagger(rig, f, direction="back", dist=0.6, recover=14, recover_to=None):
    """Thrown off balance at f (hit / perfect-deflected / shoved): snaps into stagger_back, the root is pushed
    `dist` m ('back' = away from its facing, or a world (dx, dy) direction) with a fast start and soft stop, then
    recovers to guard.  Returns the end frame."""
    rig = rig_of(rig)
    T = Clock(f)
    x, y, _, a = root_at(rig, f)
    v = -forward_vec(a) if direction == "back" else Vector((direction[0], direction[1], 0.0)).normalized()
    hold(rig, T(-1))
    pose(rig, T(1), "stagger_back", lag={"head": 1, "neck": 1})
    pose(rig, T(5), "stagger_back", weight=0.8)
    root(rig, T(-1), (x, y), a, interp='LINEAR')
    p1 = Vector((x, y, 0.0)) + v * dist
    root_path(rig, T(-1), T(8), (x, y), (p1.x, p1.y), ease="out_cubic", clk=T)
    end = T(8 + recover)
    pose(rig, end, recover_to or default_guard(rig, f))
    return end


def skid(rig, f0, f1, p0=None, p1=None, sword_drag=True, recover=10, recover_to=None):
    """Skid back low, feet sliding, sword tip dragging in the dirt in front (S18): root from p0 (f0) to p1 (f1) with
    a fast start and a braking end; the feet slide with the rig (not planted) until f1.  Events: skid (duration).
    Returns the end frame."""
    rig = rig_of(rig)
    T = Clock(f0)
    x, y, _, a = root_at(rig, f0)
    p0 = (x, y) if p0 is None else p0
    pose(rig, T(1), "skid" if sword_drag else "jump_land")
    _feet_air(rig, T(0.5))
    pose(rig, f1, "skid" if sword_drag else "jump_land", feet=True)
    root(rig, f0, p0, a, interp='LINEAR')
    root_path(rig, f0, f1, p0, p1, ease="out_cubic")
    end = Clock(f1)(recover)
    pose(rig, end, recover_to or default_guard(rig, f1), hands="keep")
    emit(int(round(f0)), "skid", who=who(rig), duration=int(round(f1 - f0)))
    return end


def kick(rig, f, recover=8, recover_to=None, target=None):
    """Front push kick with the right leg; f = CONTACT.  Chamber (knee up) 3 story frames before, snap out, retract,
    recover.  Events: kick at f (position = the kicking foot).  Returns the end frame."""
    rig = rig_of(rig)
    T = Clock(f)
    kc = weapon_at(rig, f) != "spear"          # a spear stays in its guard (the kick poses carry a katana guard)
    hold(rig, T(-6))
    pose(rig, T(-3), "kick_chamber", ctrl=kc)
    pose(rig, T(0), "kick_extend", lag={"head": 1}, ctrl=kc)
    pose(rig, T(1), "kick_extend", weight=1.04, feet=False, ctrl=kc)
    pose(rig, T(4), "kick_chamber", weight=0.8, ctrl=kc)
    end = T(4 + recover)
    pose(rig, end, recover_to or default_guard(rig, f))
    emit(int(round(f)), "kick", who=who(rig), target=(rig, "foot.R"), strength=1.0)
    return end


def slide_cut(rig, f0, f1, p0=None, p1=None, impact=None, recover=10, recover_to=None):
    """Sliding low cut (S18): from f0 the body drops into a slide along p0 -> p1 (fast start, braking), the blade
    sweeps low across at `impact` (default mid-slide), feet sliding with the rig.  Events: skid, whoosh.
    Returns the end frame."""
    rig = rig_of(rig)
    T = Clock(f0)
    x, y, _, a = root_at(rig, f0)
    p0 = (x, y) if p0 is None else p0
    impact = impact if impact is not None else T(T.span(f1) * 0.5)
    Ti = Clock(impact)
    hold(rig, T(-3))
    pose(rig, T(2), "slide_cut", weight=0.9)
    _feet_air(rig, T(1))
    root(rig, f0, p0, a, interp='LINEAR')
    root_path(rig, f0, f1, p0, p1, ease="out_quad")
    swing(rig, Ti(-3), impact, "horizontal_R_windup", "slide_cut", ease="in_quad", clk=Ti, pivot=(0.0, -0.05, 0.75))
    pose(rig, impact, "slide_cut", ctrl=False, feet=False)
    pose(rig, f1, "slide_cut")
    end = Clock(f1)(recover)
    pose(rig, end, recover_to or default_guard(rig, f1))
    emit(int(round(f0)), "skid", who=who(rig), duration=int(round(f1 - f0)))
    emit(int(round(Ti(-1))), "whoosh", who=who(rig), weapon="katana", strength=0.8, target=(rig, "hand.R"))
    return end


def blade_lock(a, b, f0, f1, point=None, pusher="a", wobble=0.025, height=None, strength=0.6, emit_event=True):
    """Tsubazeriai between rigs a and b from f0 to f1: both in blade_lock (the pusher in blade_lock_push from the
    middle), blades crossed like an X near their guards (12 % along each blade) at `point` (default between their
    chests at head height), the contact drifting / shaking along the line between them (deterministic).  A clash is
    registered at f0 (resolved like any other) and a blade_lock event (duration) is emitted.  The lane stages the
    distance (roots ~0.7-0.9 m apart).  Returns f1."""
    a, b = rig_of(a), rig_of(b)
    T = Clock(f0)
    ra, rb = Vector(root_at(a, f0)[:2]), Vector(root_at(b, f0)[:2])
    gap = (rb - ra).length
    if not 0.45 <= gap <= 1.2:
        _log(f"blade_lock {f0}: roots {gap:.2f} m apart (stage them 0.7-0.9 m)")
    z = height if height is not None else 1.30 * (S(a) + S(b)) * 0.5
    P0 = Vector(point) if point is not None else Vector(((ra.x + rb.x) * 0.5, (ra.y + rb.y) * 0.5, z))
    line = (rb - ra).normalized().to_3d() if gap > 1e-3 else Vector((0.0, 1.0, 0.0))
    for r in (a, b):
        hold(r, T(-4))
        pose(r, f0, "blade_lock")
    mid = T(T.span(f1) * 0.5)
    pose(a if pusher == "a" else b, mid, "blade_lock_push")
    pose(a if pusher == "a" else b, f1, "blade_lock_push")
    pose(b if pusher == "a" else a, f1, "blade_lock")
    n = int(T.span(f1))
    rs = seed("blade_lock", a.name, f0)
    for k in range(0, n + 1, 3):
        fk = T(k)
        ph = (rs % 1000) / 159.0
        drift = (0.5 * math.sin(0.61 * k + ph) + 0.3 * math.sin(1.37 * k + 2 * ph)) * wobble
        push = (k / max(1, n)) * 0.06 * (1 if pusher == "a" else -1)
        P = P0 + line * (drift + push) + Vector((0.0, 0.0, 0.01 * math.sin(0.9 * k + ph)))
        for r, sgn in ((a, 1.0), (b, 1.0)):
            fa = facing_of(r, fk)
            fwd, side = forward_vec(fa), left_vec(fa)
            d = (Vector((0, 0, 0.92)) + fwd * 0.30 + side * 0.22 * sgn).normalized()
            y0, y1 = weapon_range(r, weapon_at(r, fk), "blade", fk)
            grip = P - d * (y0 + (y1 - y0) * 0.12)
            Mw = C.blade_frame(grip, d, fwd)
            C.key_ctrl_matrix(PZ._ctrl_obj(r), fk, rig_matrix(r, fk).inverted() @ Mw, 'BEZIER')
            _ensure_ik(r, fk)
    reg = clash(a, b, f0, point=None, strength=strength, kind="clash", place=False, emit_event=True)
    reg["span"] = (float(f0), float(f1))            # the blades stay in contact over the whole lock
    _save_registry()
    if emit_event:
        emit(int(round(f0)), "blade_lock", duration=int(round(f1 - f0)), pos=tuple(P0))
    return f1


# =============================================================================================
# props: ballistic toss (props.toss when a props module exists)
# =============================================================================================
def toss(obj, f0, p0=None, v0=(0.0, 0.0, 0.0), spin=(0.0, 0.0, 0.0), ground_z=0.0, settle=True, restitution=0.25,
         friction=0.55, max_frames=96, radius=0.03, align_velocity=False, rot0=None, stick=False):
    """Deterministic ballistic flight of a free prop from film frame f0: position p0 (None = where
    it is at f0), velocity v0 (m/s, world), spin (deg/s about its local X, Y, Z), bounces on ground_z with
    `restitution`, slides with `friction`, settles (CONSTANT last key); stick=True stops at the first touchdown
    (a thrown spear / blade planting itself).  Time follows the film clock (slow motion slows it).  align_velocity:
    the object's +Y follows its velocity (thrown spear / kunai).  Uses props.toss when a props module provides it
    (not for align_velocity).  Returns dict(land=first touchdown frame, end=settle frame)."""
    ob = bpy.data.objects[obj] if isinstance(obj, str) else obj
    pm = _module("props")
    if pm is not None and hasattr(pm, "toss") and not align_velocity and ob.parent is None:
        fi = int(round(f0))
        M0 = U.world_matrix_of(ob, fi)
        res = pm.toss(ob, fi, p0=tuple(p0) if p0 is not None else tuple(M0.translation), v0=tuple(v0),
                      spin=tuple(math.radians(x) for x in spin), ground_z=ground_z, settle=settle,
                      rot0=rot0 if rot0 is not None else M0, restitution=restitution, friction=friction,
                      max_frames=max_frames, stick=stick)
        fr = res.get("frames") or [fi]
        return dict(land=res.get("contact"), end=res.get("rest") or fr[-1], props=True)
    M0 = U.world_matrix_of(ob, f0)
    p = Vector(p0) if p0 is not None else M0.translation.copy()
    v = Vector(v0)
    R = (rot0.copy() if rot0 is not None else M0.to_quaternion())
    wv = Vector(tuple(math.radians(x) for x in spin))
    ob.rotation_mode = 'XYZ'
    land = None
    f = float(f0)
    prev_e = None
    for i in range(int(max_frames) + 1):
        if align_velocity and v.length > 1e-3:
            q = v.normalized().to_track_quat('Y', 'Z')
            q = q @ Quaternion((0.0, 1.0, 0.0), wv.y * (fx_time(f) - fx_time(f0)))
        else:
            q = R
        e = q.to_euler('XYZ', prev_e) if prev_e is not None else q.to_euler('XYZ')
        prev_e = e
        loc = p if ob.parent is None else ob.parent.matrix_world.inverted() @ p
        U.key(ob, "location", f, tuple(loc), interp='LINEAR')
        U.key(ob, "rotation_euler", f, tuple(e), interp='LINEAR')
        dt = fx_time(f + 1) - fx_time(f)
        v.z -= 9.81 * dt
        p = p + v * dt
        if not align_velocity:
            R = (R @ Quaternion(wv.normalized(), wv.length * dt)) if wv.length > 1e-6 else R
        if p.z <= ground_z + radius:
            p.z = ground_z + radius
            if land is None:
                land = f + 1
            if stick:
                f += 1
                loc = p if ob.parent is None else ob.parent.matrix_world.inverted() @ p
                U.key(ob, "location", f, tuple(loc), interp='CONSTANT')
                U.key(ob, "rotation_euler", f, tuple(q.to_euler('XYZ', prev_e)), interp='CONSTANT')
                break
            if abs(v.z) < 1.0 or not settle:
                v = Vector((v.x * friction, v.y * friction, 0.0))
                wv *= 0.3
            else:
                v = Vector((v.x * friction, v.y * friction, -v.z * restitution))
                wv *= 0.5
            if align_velocity:
                align_velocity = False
                R = q
            if v.length < 0.15:
                f += 1
                loc = p if ob.parent is None else ob.parent.matrix_world.inverted() @ p
                U.key(ob, "location", f, tuple(loc), interp='CONSTANT')
                U.key(ob, "rotation_euler", f, tuple(R.to_euler('XYZ', prev_e)), interp='CONSTANT')
                break
        f += 1
    return dict(land=land, end=f)


# =============================================================================================
# spear (SAINT)
# =============================================================================================
def spear_draw(rig, f, twirl=True):
    """Over-the-shoulder draw of the slung spear (S14); f = the frame the spear comes free (the sheath flies off).
    f-8 the right hand reaches back to the shaft (FK -> IK), f-5 the in-hand spear is swapped in on the slung one
    (pop-free), f the spear is pulled up over the shoulder in one arc while the black sheath spins off (toss), f+6
    both hands on the shaft (grips sliding to 0.35 / 0.95), spear_high.  Events: spear_draw (f), sheath_drop (when
    the sheath lands).  Returns the end frame."""
    rig = rig_of(rig)
    T = Clock(f)
    hold(rig, T(-11), ctrl=False)
    C.set_spear_grip(T(-8), 1.45, 1.45)
    pose(rig, T(-6), "spear_draw_reach", hands="pose")
    C.key_ctrl_matrix(PZ._ctrl_obj(rig), T(-9), ctrl_matrix(rig, {"slung": 1.45}, T(-9)), 'BEZIER')
    C.set_arm_mode(rig, T(-9), "ik", blend=3)
    C.key_ctrl_matrix(PZ._ctrl_obj(rig), T(-5), ctrl_matrix(rig, {"slung": 1.45}, T(-5)), 'BEZIER')
    C.set_weapon_state(rig, T(-5), "in_hand")
    C.snap_free("SAINT_spear_sheath_world", T(-5))
    C.key_ctrl_matrix(PZ._ctrl_obj(rig), T(-2), ctrl_matrix(rig, {"slung": 1.45}, T(-2)) @
                      Matrix.Translation((0.0, 0.25, 0.0)), 'BEZIER')
    C.snap_free("SAINT_spear_sheath_world", T(-2))
    swing(rig, T(-2), T(0), PZ.current_ctrl_matrix(rig, T(-2)), "spear_draw_arc", ease="in_quad", clk=T)
    pose(rig, T(0), "spear_draw_arc", ctrl=False)
    fwd = forward_of(rig, f)
    sh = bpy.data.objects["SAINT_spear_sheath_world"]
    pm = _module("props")
    if pm is not None and hasattr(pm, "drop_spear_sheath"):
        r = pm.drop_spear_sheath(int(round(T(-1))))
        res = dict(land=r.get("contact"), end=r.get("rest"))
    else:
        res = toss(sh, T(-1), None, tuple(fwd * -1.5 + Vector((0.8, 0.0, 3.2))), spin=(900.0, 200.0, 60.0))
    C.set_spear_grip(T(4), 0.35, 0.95)
    C.set_weapon_state(rig, T(5), "in_hand")
    pose(rig, T(6), "spear_high", hands="pose", hand_blend=3)
    emit(int(round(f)), "spear_draw", who="saint", tags=["spear_draw"])
    emit(int(round(T(0))), "whoosh", who="saint", weapon="spear", strength=0.8)
    if res.get("land"):
        emit(int(round(res["land"])), "sheath_drop", target="SAINT_spear_sheath_world")
    end = T(6)
    if twirl:
        end = spear_spin(rig, T(8), T(24), turns=1.5)
    return end


def spear_spin(rig, f0, f1, turns=2.0, figure8=False, end_pose="spear_high"):
    """Twirl the spear in front of the body (held at its middle, one-handed) from f0 to f1: the shaft spins `turns`
    times in the frontal plane (figure8: alternating sides).  Events: spear_spin (duration), a whoosh every half
    turn.  Returns f1 (+ the regrip)."""
    rig = rig_of(rig)
    T = Clock(f0)
    n = T.span(f1)
    C.set_spear_grip(f0, 1.15, 1.45)
    C.set_left_hand(rig, f0, "free", blend=2)
    pose(rig, f0, "spear_spin", ctrl=False)
    base = PZ.ctrl_matrix(rig, PZ.resolve("spear_spin", rig)["ctrl"])
    g = base.translation.copy()
    fwd = Vector((0.0, -1.0, 0.0))
    for i in range(0, int(math.ceil(n)) + 1):
        fk = T(min(i, n))
        u = U.ease(min(i, n) / n, "inout_quad")
        th = 360.0 * turns * u
        axis = fwd if not figure8 else Matrix.Rotation(math.radians(25 * math.sin(math.radians(th))), 3, 'Z') @ fwd
        Rm = Matrix.Rotation(math.radians(th), 4, axis)
        M = Matrix.Translation(g + Vector((0.06 * math.sin(math.radians(th)), 0.0, 0.04 * math.cos(math.radians(th))))
                               * S(rig)) @ Rm @ base.to_3x3().to_4x4()
        C.key_ctrl_matrix(PZ._ctrl_obj(rig), fk, M, 'LINEAR')
        if i and (th // 180) != ((360.0 * turns * U.ease((i - 1) / n, "inout_quad")) // 180):
            emit(int(round(fk)), "whoosh", who="saint", weapon="spear", strength=0.5)
    _ensure_ik(rig, f0)
    emit(int(round(f0)), "spear_spin", who="saint", duration=int(round(f1 - f0)))
    C.set_spear_grip(T(n + 3), 0.35, 0.95)
    pose(rig, T(n + 4), end_pose, hands="pose", hand_blend=2)
    return T(n + 4)


def spear_sweep(rig, f, full=True, recover=10, recover_to=None):
    """Wide spear sweep; f = the moment the shaft passes in front (low - the target ducks under it).  Windup wound
    right, arc through the front, follow-through left; full=True turns the elder a whole revolution on his feet so
    the spear sweeps 360 deg around him (S16).  Events: whoosh.  Returns the end frame."""
    rig = rig_of(rig)
    T = Clock(f)
    hold(rig, T(-10))
    pose(rig, T(-6), "spear_sweep_windup", hands="pose")
    pose(rig, T(-4), "spear_sweep_windup", weight=1.04, feet=False)
    swing(rig, T(-4), T(0), "spear_sweep_windup", "spear_sweep_strike", ease="in_quad", clk=T, pivot=(0.0, 0.0, 1.05))
    pose(rig, T(0), "spear_sweep_strike", ctrl=False)
    swing(rig, T(0), T(5), "spear_sweep_strike", "spear_sweep_follow", ease="out_cubic", clk=T, include_start=False,
          pivot=(0.0, 0.0, 1.05))
    pose(rig, T(5), "spear_sweep_follow", ctrl=False)
    end = T(5 + recover)
    if full:
        x, y, _, a = root_at(rig, T(0))
        root(rig, T(0), (x, y), a, interp='LINEAR')
        for i in range(1, 11):
            root(rig, T(i), (x, y), a + 360.0 * U.ease(i / 10.0, "out_quad"), interp='LINEAR')
        pose(rig, T(10), "spear_sweep_follow", feet=False)
        emit(int(round(T(6))), "whoosh", who="saint", weapon="spear", strength=0.7)
        end = T(10 + recover)
    pose(rig, end, recover_to or "spear_low")
    emit(int(round(T(-1))), "whoosh", who="saint", weapon="spear", strength=1.0, target=(rig, "hand.R"))
    return end


def spear_thrust(rig, f, lunge=0.35, recover=9, recover_to=None):
    """Spear thrust; f = full extension (the shaft slides through the front hand: grips 0.35/0.95 -> 0.35/0.62).
    Events: whoosh.  Returns the end frame."""
    rig = rig_of(rig)
    T = Clock(f)
    hold(rig, T(-8))
    pose(rig, T(-5), "spear_thrust_windup", hands="pose")
    pose(rig, T(-3), "spear_thrust_windup", weight=1.03, feet=False)
    swing(rig, T(-3), T(0), "spear_thrust_windup", "spear_thrust_extend", ease="in_quad", clk=T)
    pose(rig, T(0), "spear_thrust_extend", ctrl=False, lag={"head": 1})
    C.set_spear_grip(T(0), 0.35, 0.62)
    pose(rig, T(3), "spear_thrust_windup", weight=0.6)
    C.set_spear_grip(T(3), 0.35, 0.85)
    if lunge:
        lunge_root(rig, T(-3), T(1), lunge, clk=T)
    end = T(3 + recover)
    pose(rig, end, recover_to or "spear_low")
    C.set_spear_grip(end, 0.35, 0.95)
    emit(int(round(T(-1))), "whoosh", who="saint", weapon="spear", strength=0.9, target=(rig, "hand.R"))
    return end


def spear_slam(rig, f, lunge=0.3, recover=14, recover_to=None, leap=0.0):
    """Overhead slam of the spear into the ground; f = impact.  Raised high (spear_slam_windup) 10 story frames
    before, driven down on an arc; leap > 0 adds a small hop (root apex m) before the impact.  Events: whoosh, hit
    (tag spear_slam, position = the spear tip).  Returns the end frame."""
    rig = rig_of(rig)
    T = Clock(f)
    hold(rig, T(-14))
    pose(rig, T(-9), "spear_slam_windup", hands="pose")
    pose(rig, T(-4), "spear_slam_windup", weight=1.04, feet=False)
    swing(rig, T(-4), T(0), "spear_slam_windup", "spear_slam", ease="in_cubic", clk=T, pivot=(0.0, 0.0, 1.2))
    pose(rig, T(0), "spear_slam", ctrl=False, lag={"head": 1})
    pose(rig, T(3), "spear_slam", weight=1.03, feet=False)
    if leap:
        x, y, _, a = root_at(rig, T(-6))
        for i in range(-6, 1):
            u = (i + 6) / 6.0
            q = Vector((x, y, 0.0)) + forward_vec(a) * lunge * u
            root(rig, T(i), (q.x, q.y), a, z=4 * leap * u * (1 - u), interp='LINEAR')
    elif lunge:
        lunge_root(rig, T(-4), T(0), lunge, clk=T)
    end = T(3 + recover)
    pose(rig, end, recover_to or "spear_low")
    emit(int(round(T(-1))), "whoosh", who="saint", weapon="spear", strength=1.0)
    emit(int(round(f)), "hit", who="saint", strength=1.0, target="SAINT_spear_tip", tags=["spear_slam"])
    return end


def spear_butt_slam(rig, f, recover=10, recover_to=None):
    """Spear held vertical, the butt driven into the ground by the right foot; f = impact (S15 1633).  Events: hit
    (tag butt_slam).  Returns the end frame."""
    rig = rig_of(rig)
    T = Clock(f)
    hold(rig, T(-10))
    C.set_spear_grip(T(-8), 1.12, 1.46)
    pose(rig, T(-6), "spear_butt_windup", hands="pose")
    pose(rig, T(-2), "spear_butt_windup", weight=1.03, feet=False)
    pose(rig, T(0), "spear_butt_slam")
    end = T(recover)
    if recover_to:
        pose(rig, end, recover_to)
    emit(int(round(f)), "hit", who="saint", strength=1.0, target="SAINT_spear_hand", tags=["butt_slam"])
    return end


def spear_throw(rig, f, target=None, speed=24.0, spin=0.0, recover=12, recover_to="relaxed"):
    """Javelin throw (S19); f = release.  Windup 8 story frames before, release arc, follow-through; at f the free
    SAINT_spear_world takes over (snap_free) and flies to `target` (world xyz; None = 12 m ahead) on a ballistic
    path at `speed` m/s, aligned to its velocity, and sticks where it lands.  Returns dict(end, arrive) (arrive = frame it reaches the target / lands)."""
    rig = rig_of(rig)
    T = Clock(f)
    hold(rig, T(-13))
    C.set_spear_grip(T(-11), 1.20, 1.55)
    pose(rig, T(-8), "spear_throw_windup", hands="pose", hand_blend=2)
    pose(rig, T(-3), "spear_throw_windup", weight=1.04, feet=False)
    swing(rig, T(-3), T(0), "spear_throw_windup", "spear_throw_release", ease="in_quad", clk=T)
    pose(rig, T(0), "spear_throw_release", ctrl=False, lag={"head": 1})
    C.set_weapon_state(rig, f, "world")
    C.snap_free("SAINT_spear_world", f)
    sw = bpy.data.objects["SAINT_spear_world"]
    p0 = U.world_matrix_of(sw, f).translation.copy()
    if target is None:                       # default: 12 m ahead, into the ground
        q = Vector(root_at(rig, f)[:2]) + forward_of(rig, f).to_2d() * 12.0
        target = (q.x, q.y, 0.0)
    tgt = Vector(target)
    dist = (tgt - p0).length
    tflight = dist / speed
    v = (tgt - p0) / tflight
    v.z += 0.5 * 9.81 * tflight
    res = toss(sw, f, p0, tuple(v), spin=(0.0, spin, 0.0), ground_z=0.0, align_velocity=True, stick=True)
    arrive = story_to_film(f, tflight * FPS)
    end = T(4 + recover)
    pose(rig, T(4), "spear_throw_release", weight=1.04, ctrl=False, feet=False)
    C.set_arm_mode(rig, T(6), "fk", blend=4)
    pose(rig, end, recover_to, ctrl=False, hands="pose")
    emit(int(round(f)), "whoosh", who="saint", weapon="spear", strength=1.0, tags=["javelin"])
    return dict(end=end, arrive=arrive, land=res.get("land"))


# =============================================================================================
# kunai (SHINOBI)
# =============================================================================================
def throw_kunai(rig, f, i, target, speed=20.0, spin=1440.0):
    """Throw kunai i (1..3) with the LEFT hand; f = release.  Windup 6 story frames before (left hand cocked by the
    ear), release snap; SHINOBI_kunai_<i> appears in the fist (snap_free) and flies point-first to `target` (world
    xyz) spinning about its long axis.  Events: kunai_throw.  Returns dict(end, arrive)."""
    rig = rig_of(rig)
    T = Clock(f)
    hold(rig, T(-9))
    pose(rig, T(-5), "kunai_throw_windup", hands="pose", hand_blend=2)
    pose(rig, T(-2), "kunai_throw_windup", weight=1.04, feet=False)
    pose(rig, T(0), "kunai_throw_release", lag={"head": 1})
    name = f"SHINOBI_kunai_{int(i)}"
    ob = bpy.data.objects[name]
    fr = int(round(T(-1)))
    U.key_visible(ob, fr - 1, False)
    U.key_visible(ob, fr, True)
    C.snap_free(name, fr)
    p0 = U.world_matrix_of(ob, fr).translation.copy()
    tgt = Vector(target)
    tfl = (tgt - p0).length / speed
    pm = _module("props")
    if pm is not None and hasattr(pm, "throw_kunai"):
        r = pm.throw_kunai(int(i), fr, tuple(tgt), speed=speed)
        res = dict(land=r.get("contact"), end=r.get("rest"))
    else:
        v = (tgt - p0) / tfl
        v.z += 0.5 * 9.81 * tfl
        res = toss(ob, fr, p0, tuple(v), spin=(0.0, spin, 0.0), align_velocity=True, stick=True,
                   max_frames=int(tfl * FPS) + 40)
    emit(int(round(f)), "kunai_throw", who="shinobi", index=int(i))
    end = T(8)
    pose(rig, end, default_guard(rig, f))
    return dict(end=end, arrive=story_to_film(T(-1), tfl * FPS), land=res.get("land"))


def kunai_parry(rig, f, attacker=None, point=None, strength=0.8, recover=8, **clash_kw):
    """Off-hand kunai parry (S16): the kunai appears in the left fist 6 story frames before, the left forearm comes
    up to turn the spear shaft aside at f; with an attacker a 'kunai_deflect' clash is registered (the ATTACKER's
    controller is nudged - the kunai has none).  Returns the end frame."""
    rig = rig_of(rig)
    T = Clock(f)
    C.set_kunai_in_hand(T(-6), True)
    hold(rig, T(-5))
    C.set_left_hand(rig, T(-5), "free", blend=2)
    pose(rig, T(-1), "kunai_parry")
    pose(rig, T(0), "kunai_parry", feet=False)
    if attacker is not None:
        clash(attacker, rig, f, point=point, strength=strength, kind="kunai_deflect", weapon_b="kunai", **clash_kw)
    else:
        emit(int(round(f)), "kunai_deflect", who="shinobi", strength=strength)
    end = T(recover + 2)
    pose(rig, T(3), "kunai_parry", weight=0.9, feet=False)
    return end


# =============================================================================================
# story moves
# =============================================================================================
def raise_to_sky(rig, f, approach=10):
    """Two-handed jodan facing the storm (S20) - a stance, not a summoning: reached at f.  Returns f."""
    rig = rig_of(rig)
    T = Clock(f)
    hold(rig, T(-approach))
    pose(rig, T(-3), "jodan", hands="pose", hand_blend=3)
    pose(rig, f, "jodan_sky", hands="pose")
    return f


def kneel(rig, f, approach=8):
    """Drop onto the right knee with the sword planted point-down (HANDOFF[3072] shinobi / S27 elder); f = knee
    touches the ground.  Events: kneel.  Returns f."""
    rig = rig_of(rig)
    T = Clock(f)
    hold(rig, T(-approach))
    pose(rig, T(-3), "rise_kneel", hands="pose", hand_blend=2)
    pose(rig, f, "kneel_planted", hands="pose")
    pose(rig, T(2), "kneel_planted", weight=1.03, feet=False)
    emit(int(round(f)), "kneel", who=who(rig))
    return f


def rise(rig, f0, f1, end="chudan"):
    """Rise from the planted-sword kneel (S24a 3085-3115): weight over the left foot at the middle, standing in
    `end` at f1.  Returns f1."""
    rig = rig_of(rig)
    T = Clock(f0)
    hold(rig, f0)
    pose(rig, T(T.span(f1) * 0.45), "rise_kneel")
    pose(rig, f1, end, hands="pose", hand_blend=3)
    return f1


def bow(rig, f, hold_frames=14, recover=12, end="relaxed"):
    """Standing bow (rei); f = the bow reached (30 deg from the hips), held, then upright.  The katana should be
    sheathed first (sheathe).  Returns the end frame."""
    rig = rig_of(rig)
    T = Clock(f)
    hold(rig, T(-10), ctrl=False)
    pose(rig, T(-4), "bow", weight=0.7, ctrl=False)
    pose(rig, f, "bow", ctrl=False)
    pose(rig, T(hold_frames), "bow", ctrl=False, feet=False)
    end_f = T(hold_frames + recover)
    pose(rig, end_f, end, ctrl=False)
    return end_f


def hide_in_grass(rig, f, approach=10):
    """Drop below the grass line (kusa-gakure, S10); f = hidden.  Returns f."""
    rig = rig_of(rig)
    T = Clock(f)
    hold(rig, T(-approach))
    pose(rig, T(-3), "crouch_hide", weight=0.8)
    pose(rig, f, "crouch_hide")
    return f


def listen(rig, f, approach=12):
    """Eyes-closed listening stance (S10), hand resting on the hilt; reached at f.  Returns f."""
    rig = rig_of(rig)
    T = Clock(f)
    hold(rig, T(-approach), ctrl=False)
    pose(rig, f, "listen", hands="pose", hand_blend=4)
    return f


def shed_haori(rig, f, throw=(1.6, 1.2, 2.6), spin=(80.0, 260.0, 40.0)):
    """SAINT sheds the haori with one sweep (S14); f = the swap frame (the coat leaves the body).  haori_grab 8 story
    frames before, haori_sweep at f+2; characters.set_costume snapshots the evaluated coat at f and the thrown copy
    flies (toss, spread shape key -> crumpled when it lands).  throw = velocity (m/s) in the rig's frame (x = his
    left, y = his back, z = up).  Events: haori_shed.  Returns the end frame."""
    rig = rig_of(rig)
    T = Clock(f)
    hold(rig, T(-12), ctrl=False)
    pose(rig, T(-8), "haori_grab", ctrl=False)
    pose(rig, f, "haori_grab", weight=0.4, ctrl=False, feet=False)
    C.set_costume(f, haori=False)
    pose(rig, T(3), "haori_sweep", ctrl=False)
    R = rig_matrix(rig, f).to_3x3()
    v = R @ Vector(throw)
    pm = _module("props")
    ob = bpy.data.objects["SAINT_haori_thrown"]
    if pm is not None and hasattr(pm, "fly_haori"):
        r = pm.fly_haori(int(round(f)), v0=tuple(v), spin=tuple(math.radians(x) for x in spin))
        res = dict(land=r.get("contact"), end=r.get("rest"))
    else:
        res = toss("SAINT_haori_thrown", f, None, tuple(v), spin=spin, radius=0.02)
    if pm is None and ob.data.shape_keys is not None:
        kb = ob.data.shape_keys.key_blocks
        for fr, sp, cr in ((f, 0.0, 0.0), (T(4), 1.0, 0.0), (res.get("land") or T(20), 0.6, 0.2), (res["end"], 0.2, 0.9)):
            if "spread" in kb:
                U.key(kb["spread"], "value", fr, sp)
            if "crumple" in kb:
                U.key(kb["crumple"], "value", fr, cr)
    emit(int(round(f)), "haori_shed", who="saint", tags=["haori_shed"])
    end = T(12)
    pose(rig, end, "relaxed", ctrl=False)
    return end


# =============================================================================================
# finishing
# =============================================================================================
def finalize(frame_range=None):
    """For stand-alone scripts (build_scene does this through lane_tools.end_lane): bake the feet and resolve the
    clashes of frame_range (None = everything).  Returns resolve_clashes' report."""
    rep = resolve_clashes(frame_range)
    for msg in LOG[-20:]:
        print("[moves] note:", msg)
    return rep


def reset():
    """Forget every registry (clashes, foot keys, evented steps, log) - a fresh scene."""
    _CLASHES.clear()
    if "moves_clashes" in bpy.context.scene:
        del bpy.context.scene["moves_clashes"]
    PZ.FOOT_KEYS.clear()
    _EVENTED_STEPS.clear()
    _HAT["tilted"] = False
    LOG.clear()
    LOCAL_EVENTS.clear()
