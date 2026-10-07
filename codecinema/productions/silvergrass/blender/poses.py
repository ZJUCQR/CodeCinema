"""
poses.py - the pose library shared by both duelists (SHINOBI_rig / SAINT_rig) + pose / root keying (Blender 5.2).

    import poses as PZ
    PZ.POSES["chudan"]                          # rich pose spec (see "Pose format")
    PZ.key_pose(rig, 120, "chudan")             # key body + legs + sword controller + left hand at frame 120
    PZ.key_pose(rig, 124, "diag_down_R_strike", weight=1.1, lag={"head": 1})   # overshoot, head one frame late
    PZ.key_root(rig, 120, (0.0, -3.0), 180)     # rig object on the ground, facing +Y
    spec = PZ.resolve("chudan", rig)            # per-character, rig-ready spec for characters.apply_pose

Pose format (a superset of characters.apply_pose specs, so tools/pose_atlas.py renders POSES directly):
    <bone>: (rx, ry, rz)        body FK Euler XYZ in DEGREES (+X = flexion, Y/Z mirrored between .L/.R)
                               - bones sit at the TOP level (: POSES = {name: {bone: (rx, ry, rz)}, hips_offset})
    hips_offset: (x, y, z)      hips.location, bone-local: x = his left, y = up (crouch < 0), z = forward
    legs: {'L'|'R': dict(ball=(x, y), yaw=0, heel=0, lift=0.0, air=False, knee=None)}
                                where the BALL of each foot is, in rig space (SHINOBI metres, scaled x1.85/1.72 for
                                the SAINT); yaw + = toes to his left; heel = heel lift in degrees (the ball stays on
                                the ground, the toes stay flat); lift = ball height above the ground; air=True = the
                                foot is not planted (kicks, jumps: the foot-plant bake leaves it alone); knee =
                                rig-space knee direction (default: forward, turned by yaw).  resolve() converts
                                this into characters.solve_leg input (ankle / foot_yaw / foot_pitch / toe).
    ctrl: None | {"grip": (x,y,z), "dir": (x,y,z), "edge": (x,y,z)} | "sheathed"
                                sword controller = right-fist grip centre, blade direction, cutting-edge direction,
                                RIG space, SHINOBI metres (scaled for the SAINT unless "scale": False); "sheathed" =
                                right fist on the hilt of the sheathed katana.  A pose with a ctrl puts the right arm
                                in IK; without one the right arm is FK (bones above).
    left: 'free' | 'grip' | 'saya'   left hand (two_hand=True is the same as left='grip')
    weapon: 'katana' | 'spear' ; spear_grip: (grip_R, grip_L) ; saya: (pull, roll) ; hat_tilt: (pitch, roll)
    elbow: {'R'|'L': 'auto' | (x, y, z)} ; chars: ['SAINT'] (pose exists only for these) ; arm: 'ik' | 'fk'
    per_char: {'SAINT': {...partial spec...}}   per-character override (bones / legs per side merged, rest replaced)
    desc, cat                    free text / category (atlas grouping, docs)

Rules of thumb : the SHINOBI is low, coiled and two-handed; the SAINT is
upright, grounded and economical (his rest pose already carries a stoop), one-handed with his left hand on the
saya through Act I (moves keep whatever left-hand state the lane set: key_pose(..., hands='keep')).
"""

from codecinema.productions import film_root, source_root
import math
import os
import sys

ROOT = str(film_root("silvergrass"))
for _p in (os.path.join(str(source_root("silvergrass")), "common"), os.path.join(str(source_root("silvergrass")), "blender")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import config  # noqa: E402

BODY_BONES = ["hips", "spine", "chest", "neck", "head",
              "shoulder.L", "upper_arm.L", "forearm.L", "hand.L",
              "shoulder.R", "upper_arm.R", "forearm.R", "hand.R",
              "thigh.L", "shin.L", "foot.L", "toe.L",
              "thigh.R", "shin.R", "foot.R", "toe.R"]
LEG_BONES = ("thigh", "shin", "foot", "toe")
META_KEYS = ("desc", "cat", "per_char", "partial", "arm", "chars", "_name")
SCALE = {"SHINOBI": 1.0, "SAINT": config.SAINT_HEIGHT / config.SHINOBI_HEIGHT}   # poses are authored in SHINOBI metres


# =============================================================================================
# authoring helpers (pure data: usable without bpy)
# =============================================================================================
def torso(lean=0.0, twist=0.0, side=0.0, look_pitch=0.0, look_yaw=0.0, look_roll=0.0, gaze=1.0,
          pelvis=0.3, neck_share=0.55):
    """Trunk rotations {hips, spine, chest, neck, head} in degrees.

    lean  + = bend forward (flexion), twist + = turn to his LEFT, side + = side-bend to his RIGHT (),
    distributed pelvis / spine / chest (pelvis = share of the hips bone; the legs are re-solved to the planted
    feet, so a pelvis tilt reads as a bend at the hip joints).  Neck + head counter-rotate by `gaze` (1 = the eyes
    stay level and on the opponent, 0 = the head follows the trunk) and then add look_pitch (+ = look down),
    look_yaw (+ = look to his left), look_roll (+ = tilt right)."""
    rest = 1.0 - pelvis
    d = {
        "hips": (lean * pelvis, twist * 0.40, side * 0.20),
        "spine": (lean * rest * 0.5, twist * 0.30, side * 0.40),
        "chest": (lean * rest * 0.5, twist * 0.30, side * 0.40),
    }
    ln, tw, sd = -gaze * lean + look_pitch, -gaze * twist + look_yaw, -gaze * side + look_roll
    d["neck"] = (ln * neck_share, tw * neck_share, sd * neck_share)
    d["head"] = (ln * (1 - neck_share), tw * (1 - neck_share), sd * (1 - neck_share))
    return d


def arm(side, flex=0.0, abd=0.0, rot=0.0, elbow=10.0, pron=0.0, wflex=0.0, wdev=0.0, wtwist=0.0,
        sh_fwd=0.0, sh_up=0.0):
    """FK arm {shoulder, upper_arm, forearm, hand}.<side> authored with LEFT-side semantics and mirrored for
    side='R' (Y/Z negated), so arm('L', ...) and arm('R', ...) with the same numbers are mirror images.
    flex + = arm forward/up, abd + = arm out/up (-40 = hanging along the body from the 45 deg A-pose),
    rot + = internal rotation, elbow = elbow flexion (0 = the rest bend, -16 = straight), pron = forearm roll,
    wflex/wdev/wtwist = wrist, sh_fwd = clavicle protraction, sh_up = shrug."""
    k = 1.0 if side == "L" else -1.0
    return {
        f"shoulder.{side}": (sh_fwd, 0.0, k * sh_up),
        f"upper_arm.{side}": (flex, k * rot, k * abd),
        f"forearm.{side}": (elbow, k * pron, 0.0),
        f"hand.{side}": (wflex, k * wtwist, k * wdev),
    }


def foot(x, y, yaw=0.0, heel=0.0, lift=0.0, air=False, knee=None):
    """One foot for a pose's legs dict: BALL of the foot at (x, y) in rig space (SHINOBI metres; right foot x < 0,
    forward = -y), yaw + = toes to his left, heel = heel lift (deg), lift = ball height, air = not planted."""
    d = dict(ball=(float(x), float(y)), yaw=float(yaw), heel=float(heel), lift=float(lift), air=bool(air))
    if knee is not None:
        d["knee"] = tuple(knee)
    return d


def stance(front=0.30, back=0.28, width=0.22, lead="R", yaw_front=0.0, yaw_back=18.0, heel_back=0.0,
           heel_front=0.0, shift=0.0):
    """Two-foot stance: lead foot `front` m ahead of the hips line, rear foot `back` m behind, feet `width` apart,
    shifted sideways by `shift` (+ = to his left).  Returns a legs dict."""
    sx = -1.0 if lead == "R" else 1.0
    other = "L" if lead == "R" else "R"
    return {
        lead: foot(sx * width * 0.5 + shift, -front, yaw=-sx * yaw_front, heel=heel_front),
        other: foot(-sx * width * 0.5 + shift, back, yaw=-sx * yaw_back, heel=heel_back),
    }


def blade(grip, direction, edge=None, roll=0.0):
    """Sword-controller spec (rig space, SHINOBI metres): right-fist grip, blade direction, edge direction
    (default: down), roll = extra turn of the edge about the blade axis in degrees (wrist comfort)."""
    d = {"grip": tuple(float(v) for v in grip), "dir": tuple(float(v) for v in direction)}
    if edge is not None:
        d["edge"] = tuple(float(v) for v in edge)
    if roll:
        d["roll"] = float(roll)
    return d


def elev(deg, yaw=0.0):
    """Unit direction in rig space: `deg` above the forward horizontal (forward = -Y), turned `yaw` deg to his
    LEFT (+X)."""
    e, a = math.radians(deg), math.radians(yaw)
    return (math.cos(e) * math.sin(a), -math.cos(e) * math.cos(a), math.sin(e))


def pose(desc="", cat="misc", body=None, hips=(0.0, 0.0, 0.0), legs=None, ctrl=None, left="free", **extra):
    """Assemble a POSES entry: body bones at the top level, plus hips_offset, legs, ctrl, left,
    and any other apply_pose key (weapon, spear_grip, saya, elbow, hat_tilt, chars, per_char, arm, ...)."""
    p = {}
    for b, r in (body or {}).items():
        p[b] = tuple(float(v) for v in r)
    p["hips_offset"] = tuple(float(v) for v in hips)
    if legs is not None:
        p["legs"] = legs
    p["ctrl"] = ctrl
    p["left"] = left
    p["desc"] = desc
    p["cat"] = cat
    p.update(extra)
    return p


def merge(*dicts):
    """Shallow merge of body dicts (later wins)."""
    out = {}
    for d in dicts:
        out.update(d or {})
    return out


POSES = {}


def _add(name, p):
    if name in POSES:
        raise KeyError(f"duplicate pose {name!r}")
    p["_name"] = name
    POSES[name] = p
    return p


TUNED = {}      # machine-tuned controllers (generated block at the end of this file, see out/dev/moves/tune.py)


def ctrl_sig(ctrl):
    """Short signature of an authored controller spec (TUNED entries apply only while it is unchanged)."""
    if not isinstance(ctrl, dict):
        return repr(ctrl)
    parts = []
    for k in ("grip", "dir", "edge", "roll"):
        v = ctrl.get(k)
        if v is None:
            continue
        parts.append(k + ":" + (",".join(f"{x:.3f}" for x in v) if isinstance(v, (tuple, list)) else f"{v:.2f}"))
    return ";".join(parts)


# =============================================================================================
# resolving a spec for one character / rig (pure data unless a rig object is given)
# =============================================================================================
def char_of(rig_or_char):
    """'SHINOBI' | 'SAINT' from a rig object, a rig/object name or a character name (None -> None)."""
    if rig_or_char is None:
        return None
    n = rig_or_char if isinstance(rig_or_char, str) else rig_or_char.name
    for c in ("SHINOBI", "SAINT"):
        if n == c or n.startswith(c + "_"):
            return c
    raise ValueError(f"not a character rig/name: {n!r}")


def mirror_name(bone):
    """.L <-> .R (and hachimaki tail1.* <-> tail2.*)."""
    if bone.startswith("tail1."):
        return "tail2." + bone[6:]
    if bone.startswith("tail2."):
        return "tail1." + bone[6:]
    if bone.endswith(".L"):
        return bone[:-2] + ".R"
    if bone.endswith(".R"):
        return bone[:-2] + ".L"
    return bone


def mirror_body(body):
    """Mirror {bone: (rx, ry, rz)} left <-> right (swap .L/.R, negate Y and Z) = characters.mirror_pose."""
    return {mirror_name(b): (r[0], -r[1], -r[2]) for b, r in body.items()}


def _mirror_vec(v):
    return (-v[0],) + tuple(v[1:])


def _norm(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return tuple(x / n for x in v)


def _rotate(v, axis, deg):
    """Rodrigues rotation of v about a unit axis (pure python)."""
    k = _norm(axis)
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    kv = sum(x * y for x, y in zip(k, v))
    cr = (k[1] * v[2] - k[2] * v[1], k[2] * v[0] - k[0] * v[2], k[0] * v[1] - k[1] * v[0])
    return tuple(v[i] * c + cr[i] * s + k[i] * kv * (1 - c) for i in range(3))


def default_edge(direction):
    """characters.blade_frame's default edge for a blade direction: world-down, or forward for a vertical blade."""
    d = _norm(direction)
    return (0.0, -1.0, 0.0) if abs(d[2]) > 0.98 else (0.0, 0.0, -1.0)


def rolled_ctrl(ctrl):
    """ctrl spec with "roll" (deg, about the blade axis, + = right-handed about grip->tip) folded into "edge"."""
    c = dict(ctrl)
    roll = float(c.pop("roll", 0.0) or 0.0)
    if roll and "dir" in c:
        d = _norm(c["dir"])
        e = c.get("edge") or default_edge(d)
        ed = sum(x * y for x, y in zip(e, d))
        e = _norm(tuple(x - ed * y for x, y in zip(e, d)))
        c["edge"] = _rotate(e, d, roll)
    return c


def spec_of(name_or_spec):
    """POSES entry for a name, or the spec itself."""
    if isinstance(name_or_spec, str):
        try:
            return POSES[name_or_spec]
        except KeyError:
            raise KeyError(f"unknown pose {name_or_spec!r}") from None
    return name_or_spec


def _copy(v):
    if isinstance(v, dict):
        return {k: _copy(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_copy(x) for x in v]
    return v


def _is_bone_key(k, v):
    return isinstance(v, (tuple, list)) and len(v) == 3 and (k in BODY_BONES or k.startswith(("tail", "beard")))


def resolve(name_or_spec, rig_or_char=None, mirror=False):
    """Per-character, optionally mirrored copy of a pose spec in characters.apply_pose format:
    {"body": {bone: rot}, "hips_offset", "legs": {side: {ankle, foot_yaw, foot_pitch, toe, knee_dir, scale,
    ball_w, air}}, "ctrl", "left", ...}.  With a rig OBJECT the ball-authored legs are converted into rig-space
    ankles (exact for that rig) and the hips are lowered when a planted leg could not reach its foot
    ("_auto_crouch" = metres added).  With only a character name the legs keep their ball form."""
    base = spec_of(name_or_spec)
    char = char_of(rig_or_char)
    sp = _copy({k: v for k, v in base.items() if k != "per_char"})
    ov = (base.get("per_char") or {}).get(char) if char else None
    if ov:
        for k, v in _copy(ov).items():
            if k == "legs" and isinstance(v, dict) and isinstance(sp.get("legs"), dict):
                for side, lg in v.items():
                    sp["legs"][side] = dict(sp["legs"].get(side, {}), **lg) if lg is not None else None
                sp["legs"] = {s: l for s, l in sp["legs"].items() if l is not None}
            else:
                sp[k] = v
    nm = base.get("_name")
    if nm and isinstance(sp.get("ctrl"), dict) and "grip" in sp["ctrl"]:
        key = nm + "@SAINT" if (char == "SAINT" and isinstance(ov, dict) and "ctrl" in ov) else nm
        t = TUNED.get(key)
        if t is not None and t.get("src") == ctrl_sig(sp["ctrl"]):
            extra = {k: v for k, v in sp["ctrl"].items() if k not in ("grip", "dir", "edge", "roll")}
            sp["ctrl"] = dict(t["ctrl"], **extra)
            sp["_tuned"] = key
    if isinstance(sp.get("ctrl"), dict) and sp["ctrl"].get("roll"):
        sp["ctrl"] = rolled_ctrl(sp["ctrl"])
    body = dict(sp.pop("body", {}) or {})
    for k in list(sp.keys()):
        if _is_bone_key(k, sp[k]):
            body[k] = tuple(sp.pop(k))
    if mirror:
        body = mirror_body(body)
        if sp.get("legs"):
            ml = {}
            for side, lg in sp["legs"].items():
                lg = dict(lg)
                if "ball" in lg:
                    lg["ball"] = _mirror_vec(lg["ball"])
                if "ankle" in lg:
                    lg["ankle"] = _mirror_vec(lg["ankle"])
                for yk in ("yaw", "foot_yaw"):
                    if yk in lg:
                        lg[yk] = -lg[yk]
                if lg.get("knee") is not None:
                    lg["knee"] = _mirror_vec(lg["knee"])
                ml["L" if side == "R" else "R"] = lg
            sp["legs"] = ml
        c = sp.get("ctrl")
        if isinstance(c, dict) and ("grip" in c or "loc" in c):
            c = dict(c)
            for k in ("grip", "dir", "edge", "loc"):
                if k in c:
                    c[k] = _mirror_vec(c[k])
            if "rot" in c:
                c["rot"] = (c["rot"][0], -c["rot"][1], -c["rot"][2])
            sp["ctrl"] = c
        ho = sp.get("hips_offset")
        if ho:
            sp["hips_offset"] = (-ho[0], ho[1], ho[2])
        if sp.get("hat_tilt"):
            sp["hat_tilt"] = (sp["hat_tilt"][0], -sp["hat_tilt"][1])
    sp["body"] = body
    sp.setdefault("hips_offset", (0.0, 0.0, 0.0))
    if rig_or_char is not None and not isinstance(rig_or_char, str) and sp.get("legs"):
        _legs_for_rig(rig_or_char, sp)
    return sp


# ---------------------------------------------------------------------------------------------- legs (bpy)
def _foot_rest(rig, side):
    """(ankle, ball, v=ball-ankle, foot X axis) of the rest foot bone in rig space."""
    b = rig.data.bones[f"foot.{side}"]
    a, t = b.head_local.copy(), b.tail_local.copy()
    return a, t, t - a, b.matrix_local.to_3x3().col[0].copy()


def ball_to_ankle(rig, side, ball, yaw=0.0, heel=0.0, lift=0.0):
    """Rig-space ankle (shin tail) that puts the BALL of the foot at `ball` (x, y) (rig metres, this rig's scale)
    on the ground (+ lift), foot turned `yaw` deg (toes to his left) and heel lifted `heel` deg (toes down about
    the ball) - the same rotation characters.solve_leg applies to the foot."""
    from mathutils import Matrix, Vector
    a, t, v, xax = _foot_rest(rig, side)
    R = Matrix.Rotation(math.radians(yaw), 3, 'Z') @ Matrix.Rotation(math.radians(heel), 3, xax)
    b = Vector((ball[0], ball[1], t.z + lift))
    return b - R @ v


def ankle_to_ball(rig, side, ankle, yaw=0.0, heel=0.0):
    """Inverse of ball_to_ankle: ball position (Vector, rig space) of a foot with its ankle at `ankle`."""
    from mathutils import Matrix, Vector
    a, t, v, xax = _foot_rest(rig, side)
    R = Matrix.Rotation(math.radians(yaw), 3, 'Z') @ Matrix.Rotation(math.radians(heel), 3, xax)
    return Vector(ankle) + R @ v


def hip_joint(rig, side, hips_rot=(0.0, 0.0, 0.0), hips_offset=(0.0, 0.0, 0.0)):
    """Rig-space hip-joint position (thigh head) for a hips pose (degrees, bone-local offset)."""
    from mathutils import Euler, Matrix
    B = rig.data.bones
    hr = Euler(tuple(math.radians(x) for x in hips_rot), 'XYZ').to_matrix().to_4x4()
    hips_pose = B["hips"].matrix_local @ Matrix.Translation(hips_offset) @ hr
    return (hips_pose @ B["hips"].matrix_local.inverted() @ B[f"thigh.{side}"].matrix_local).translation


def leg_length(rig, side="R"):
    B = rig.data.bones
    return B[f"thigh.{side}"].length + B[f"shin.{side}"].length


REACH_FRAC = 0.975          # a planted leg is never straighter than this fraction of its length (no knee pop)


def _legs_for_rig(rig, sp):
    """Convert ball-authored legs of a resolved spec into solve_leg input for `rig` (in place) and lower the hips
    when a planted foot is out of reach."""
    char = char_of(rig)
    s = SCALE[char]
    hips_rot = sp["body"].get("hips", (0.0, 0.0, 0.0))
    out = {}
    for side, lg in sp["legs"].items():
        lg = dict(lg)
        if "ball" in lg:
            yaw, heel = lg.get("yaw", 0.0), lg.get("heel", 0.0)
            ank = ball_to_ankle(rig, side, (lg["ball"][0] * s, lg["ball"][1] * s), yaw, heel, lg.get("lift", 0.0) * s)
            knee = lg.get("knee")
            out[side] = dict(ankle=tuple(ank), foot_yaw=yaw, foot_pitch=heel,
                             toe=tuple(lg.get("toe", (-heel, 0.0, 0.0))), knee_dir=tuple(knee) if knee else None,
                             scale=False, air=bool(lg.get("air", False)), ball_w=(lg["ball"][0] * s, lg["ball"][1] * s))
        else:
            if lg.get("scale", True) and "ankle" in lg:
                lg["ankle"] = tuple(x * s for x in lg["ankle"])
                lg["scale"] = False
            out[side] = lg
    sp["legs"] = out
    # auto-crouch: lower the hips until every planted foot is reachable (reported, so authoring can be fixed)
    ho = list(sp.get("hips_offset", (0.0, 0.0, 0.0)))
    extra = 0.0
    for side, lg in out.items():
        if lg.get("air") or "ankle" not in lg:
            continue
        from mathutils import Vector
        L = leg_length(rig, side) * REACH_FRAC
        H = hip_joint(rig, side, hips_rot, ho)
        A = Vector(lg["ankle"])
        horiz = math.hypot(H.x - A.x, H.y - A.y)
        if (H - A).length > L and horiz < L:
            need = (H.z - A.z) - math.sqrt(L * L - horiz * horiz)
            if need > 0:
                ho[1] -= need + 1e-4
                extra += need
    if extra > 0:
        sp["hips_offset"] = tuple(ho)
        sp["_auto_crouch"] = round(extra, 4)
    return sp


def leg_solution(rig, spec):
    """{bone: (rx, ry, rz)} for thigh/shin/foot/toe of every leg in a resolved spec (characters.solve_leg)."""
    import characters as C
    out = {}
    body = spec["body"]
    for side, lg in (spec.get("legs") or {}).items():
        if "ankle" not in lg:
            continue
        sol = C.solve_leg(rig, side, lg["ankle"], hips_rot=body.get("hips", (0.0, 0.0, 0.0)),
                          hips_offset=spec.get("hips_offset", (0.0, 0.0, 0.0)), knee_dir=lg.get("knee_dir"),
                          foot_yaw=lg.get("foot_yaw", 0.0), foot_pitch=lg.get("foot_pitch", 0.0))
        for part in ("thigh", "shin", "foot"):
            out[f"{part}.{side}"] = sol[part]
        out[f"toe.{side}"] = tuple(lg.get("toe", (0.0, 0.0, 0.0)))
    return out


# =============================================================================================
# foot-plant registry (read by moves.bake_feet): every planted foot of every keyed pose, in RIG space
# =============================================================================================
FOOT_KEYS = {}      # rig name -> [dict(frame, side, space 'RIG'|'WORLD', ball (x,y,z), yaw, heel, knee, air, src)]


def register_foot(rig, frame, side, ball, yaw=0.0, heel=0.0, space="RIG", air=False, knee=None, src="pose",
                  lift=0.0):
    """Record where a foot is at `frame` for the foot-plant bake (moves.bake_feet): ball position (rig space of
    that frame, or WORLD), yaw (deg, rig-relative for RIG / world heading offset for WORLD), heel lift (deg).
    A later entry for the same rig/side/frame replaces the earlier one."""
    lst = FOOT_KEYS.setdefault(rig.name if not isinstance(rig, str) else rig, [])
    fr = round(float(frame), 3)
    lst[:] = [k for k in lst if not (k["side"] == side and abs(k["frame"] - fr) < 1e-3)]
    lst.append(dict(frame=fr, side=side, space=space, ball=tuple(float(v) for v in ball), yaw=float(yaw),
                    heel=float(heel), air=bool(air), knee=tuple(knee) if knee else None, src=src, lift=float(lift)))
    return lst[-1]


def clear_feet(rig=None, frame_range=None):
    """Forget registered foot keys (all, one rig, or one rig inside [f0, f1])."""
    if rig is None:
        FOOT_KEYS.clear()
        return
    name = rig if isinstance(rig, str) else rig.name
    if frame_range is None:
        FOOT_KEYS.pop(name, None)
        return
    f0, f1 = frame_range
    FOOT_KEYS[name] = [k for k in FOOT_KEYS.get(name, []) if not (f0 - 1e-3 <= k["frame"] <= f1 + 1e-3)]


# =============================================================================================
# keying (bpy)
# =============================================================================================
def _ev(idb, path, frame, default, index=0):
    """Animated value of a channel at `frame` (keys of the active action first, then earlier lanes)."""
    import characters as C
    return C._fc_value(idb, path, frame, default, index=index)


def current_rot(rig, bone, frame):
    """Evaluated Euler (degrees) of a pose bone at `frame` from its F-curves (current value when unkeyed)."""
    pb = rig.pose.bones[bone]
    path = pb.path_from_id("rotation_euler")
    return tuple(math.degrees(_ev(rig, path, frame, pb.rotation_euler[i], i)) for i in range(3))


def current_hips_offset(rig, frame):
    pb = rig.pose.bones["hips"]
    path = pb.path_from_id("location")
    return tuple(_ev(rig, path, frame, pb.location[i], i) for i in range(3))


def _ctrl_obj(rig):
    import bpy
    return bpy.data.objects[f"{char_of(rig)}_sword_ctrl"]


def current_ctrl_matrix(rig, frame):
    """Rig-space matrix of <C>_sword_ctrl evaluated from its F-curves at `frame`."""
    from mathutils import Euler, Matrix, Vector
    ob = _ctrl_obj(rig)
    loc = Vector(tuple(_ev(ob, "location", frame, ob.location[i], i) for i in range(3)))
    rot = Euler(tuple(_ev(ob, "rotation_euler", frame, ob.rotation_euler[i], i) for i in range(3)), 'XYZ')
    return Matrix.Translation(loc) @ rot.to_matrix().to_4x4()


def ctrl_matrix(rig, ctrl, char=None):
    """Rig-space controller matrix of a ctrl spec dict (grip/dir/edge or loc/rot, SHINOBI metres scaled)."""
    import characters as C
    from mathutils import Euler, Matrix, Vector
    char = char or char_of(rig)
    if char in ctrl and isinstance(ctrl[char], dict):
        ctrl = dict(ctrl[char], scale=False)
    k = SCALE[char] if ctrl.get("scale", True) else 1.0
    if ctrl.get("roll"):
        ctrl = rolled_ctrl(ctrl)
    if "grip" in ctrl:
        return C.blade_frame(Vector(ctrl["grip"]) * k, ctrl["dir"], ctrl.get("edge"))
    return Matrix.Translation(Vector(ctrl["loc"]) * k) @ \
        Euler(tuple(math.radians(a) for a in ctrl["rot"]), 'XYZ').to_matrix().to_4x4()


def blend_matrix(A, B, w):
    """Location lerp + rotation slerp from A (w=0) to B (w=1); w > 1 extrapolates (overshoot)."""
    from mathutils import Matrix
    la, ra, _ = A.decompose()
    lb, rb, _ = B.decompose()
    if ra.dot(rb) < 0:
        rb = -rb
    if 0.0 <= w <= 1.0:
        r = ra.slerp(rb, w)
    else:
        d = ra.rotation_difference(rb)
        ax, ang = d.to_axis_angle()
        from mathutils import Quaternion
        r = Quaternion(ax, ang * w) @ ra
    return Matrix.Translation(la.lerp(lb, w)) @ r.to_matrix().to_4x4()


def _lerp3(a, b, w):
    return tuple(x + (y - x) * w for x, y in zip(a, b))


def _unwrap_deg(cur, tgt):
    """tgt shifted by 360 so that it is closest to cur (Euler continuity)."""
    return tuple(t + 360.0 * round((c - t) / 360.0) for c, t in zip(cur, tgt))


def key_pose(rig, frame, name, weight=1.0, mirror=False, interp='BEZIER', hands="pose", ctrl=True, legs=True,
             lag=None, hand_blend=0, elbows=True, feet=True, spec=None):
    """Key a POSES entry on `rig` at `frame`.

    weight: blend from the rig's current (keyed) pose at `frame` towards the pose (1 = full pose, 0.5 = half way,
            1.1 = 10 % overshoot past it - used for overshoot-and-settle).
    mirror: the left/right mirror image (body, feet, blade position; the sword stays in the right hand).
    hands:  'pose' = apply the pose's left-hand state (set_left_hand, `hand_blend` frames) | 'keep' = leave it.
    ctrl:   key the sword controller (+ IK arm mode) when the pose has one.
    legs:   solve + key the legs; feet: register the planted feet for the foot-plant bake (moves.bake_feet).
    lag:    {bone: frames} keys those bones later (> 0) or earlier (< 0) - successive breaking of joints.
    spec:   a ready spec (resolve()) instead of `name`.
    Every body bone of a full pose is keyed (unmentioned bones -> 0); a pose with "partial": True keys only its
    own bones.  Returns the resolved spec (with '_legs' = the solved leg Eulers)."""
    import characters as C
    import bl_util as U
    from mathutils import Vector
    rig = C.get_rig(rig)
    char = char_of(rig)
    sp = spec if spec is not None else resolve(name, rig, mirror)
    frame = float(frame)
    body = dict(sp["body"])
    partial = bool(sp.get("partial"))
    lag = lag or {}
    # hips offset (blended)
    ho = tuple(sp.get("hips_offset", (0.0, 0.0, 0.0)))
    if weight != 1.0:
        ho = _lerp3(current_hips_offset(rig, frame), ho, weight)
    leg_rot = leg_solution(rig, dict(sp, hips_offset=ho)) if (legs and sp.get("legs")) else {}
    bones = BODY_BONES if not partial else [b for b in BODY_BONES if b in body or b in leg_rot]
    for b in bones:
        if not legs and b.split(".")[0] in LEG_BONES and b not in body:
            continue
        tgt = leg_rot.get(b, body.get(b, (0.0, 0.0, 0.0)))
        f = frame + float(lag.get(b, 0.0))
        cur = current_rot(rig, b, f)
        tgt = _unwrap_deg(cur, tgt)
        val = tgt if weight == 1.0 else _lerp3(cur, tgt, weight)
        U.key(rig.pose.bones[b], "rotation_euler", f, tuple(math.radians(v) for v in val), interp=interp)
    if not partial or any(abs(v) > 1e-9 for v in ho):
        U.key(rig.pose.bones["hips"], "location", frame + float(lag.get("hips", 0.0)), ho, interp=interp)
    # feet for the plant bake
    if feet and legs and sp.get("legs"):
        for side, lg in sp["legs"].items():
            if "ankle" not in lg:
                continue
            ball = ankle_to_ball(rig, side, lg["ankle"], lg.get("foot_yaw", 0.0), lg.get("foot_pitch", 0.0))
            register_foot(rig, frame, side, tuple(ball), lg.get("foot_yaw", 0.0), lg.get("foot_pitch", 0.0),
                          space="RIG", air=lg.get("air", False), knee=lg.get("knee_dir"), src="pose")
    # sword controller + arm mode
    c = sp.get("ctrl")
    if ctrl and c is not None:
        ob = _ctrl_obj(rig)
        if isinstance(c, dict) and "slung" in c:
            U.frame_set(frame)
            M = C.slung_spear_ctrl_matrix(frame, float(c["slung"]))
        elif c == "sheathed" or (isinstance(c, dict) and "sheathed" in c):
            from mathutils import Matrix
            U.frame_set(frame)
            pull = 0.0 if c == "sheathed" else float(c["sheathed"]) * SCALE[char]
            M = C.sheathed_ctrl_matrix(rig, frame) @ Matrix.Translation((0.0, -pull, 0.0))
        else:
            M = ctrl_matrix(rig, c, char)
        if weight != 1.0:
            M = blend_matrix(current_ctrl_matrix(rig, frame), M, weight)
        C.key_ctrl_matrix(ob, frame, M, interp)
        ik = C._con(rig, "forearm.R", "IK_sword")
        if _ev(rig, ik.path_from_id("influence"), frame, ik.influence) < 0.5:
            C.set_arm_mode(rig, frame, "ik")
    elif ctrl and sp.get("arm") == "fk":
        ik = C._con(rig, "forearm.R", "IK_sword")
        if _ev(rig, ik.path_from_id("influence"), frame, ik.influence) > 0.5:
            C.set_arm_mode(rig, frame, "fk")
    # left hand
    if hands == "pose":
        want = sp.get("left") or ("grip" if sp.get("two_hand") else "free")
        if want == "grip":
            w = sp.get("weapon") or ("spear" if (char == "SAINT" and C.active_weapon(rig, frame) == "spear") else "katana")
            if w == "katana" and _ev(rig, '["katana_state"]', frame, rig.get("katana_state", 0)) < 0.5:
                want = "free"          # nothing in hand to grip
        cur = C.left_hand(rig, frame)
        if want != cur:
            C.set_left_hand(rig, frame, want, blend=hand_blend)
    if char == "SAINT" and sp.get("spear_grip") and (sp.get("weapon") == "spear"):
        C.set_spear_grip(frame, *sp["spear_grip"])
    # scabbard / hat
    if sp.get("saya") is not None:
        key_saya(rig, frame, *sp["saya"])
    if char == "SAINT" and sp.get("hat_tilt") is not None:
        C.set_hat_tilt(frame, *sp["hat_tilt"])
    # elbows
    want_el = sp.get("elbow") or {}
    for side in ("R", "L"):
        v = want_el.get(side)
        if v is None:
            if elbows and _elbow_on(rig, side, frame):
                C.release_elbow(rig, frame, side)
            continue
        if isinstance(v, str) and v == "auto":
            C.auto_elbow(rig, frame, side)
        else:
            C.key_elbow(rig, frame, side, tuple(Vector(v) * SCALE[char]), space='RIG')
    sp["_legs"] = leg_rot
    return sp


def saya_matrix(rig, pull=0.0, roll=0.0, turn=0.0, tilt=0.0):
    """matrix_basis of <C>_saya: characters.saya_basis (pull back along its axis, roll about it) turned about the
    koiguchi: turn + = the kojiri swings out to his LEFT (the blade then leaves the mouth toward his right front -
    the iai saya-biki that makes a full draw reachable), tilt + = the kojiri drops (the blade exits higher)."""
    import characters as C
    from mathutils import Matrix
    M = C.saya_basis(rig, pull, roll)
    if not turn and not tilt:
        return M
    o = M.translation.copy()
    R = Matrix.Rotation(math.radians(-turn), 4, 'Y') @ Matrix.Rotation(math.radians(tilt), 4, 'X')
    return Matrix.Translation(o) @ R @ Matrix.Translation(-o) @ M


def key_saya(rig, frame, pull=0.0, roll=0.0, turn=0.0, tilt=0.0, interp='BEZIER'):
    """Key the scabbard (child of hips) at `frame` with pull / roll (characters.key_saya semantics) + turn / tilt
    about the koiguchi (saya_matrix).  sheathed_ctrl_matrix and the left saya grip follow it."""
    import bpy
    import characters as C
    rig = C.get_rig(rig)
    return C.key_ctrl_matrix(bpy.data.objects[f"{char_of(rig)}_saya"], frame, saya_matrix(rig, pull, roll, turn, tilt),
                             interp)


def _elbow_on(rig, side, frame):
    """True when the POLE_override of `side` is on at `frame`."""
    import characters as C
    for pole in C._side_poles(rig, side):
        con = pole.constraints.get("POLE_override")
        if con is not None and _ev(pole, con.path_from_id("influence"), frame, con.influence) > 0.5:
            return True
    return False


def key_root(rig, frame, xy, facing_deg, z=0.0, interp='BEZIER', tilt=(0.0, 0.0)):
    """Key the rig object (root motion) at `frame`: ground point (x, y), height z, facing in degrees (0 -> faces
    -Y, 180 -> +Y; unwrapped to the nearest turn of the curve at that frame, so 170 -> -170 turns 20 deg, not
    340), optional tilt (pitch about his lateral axis, roll about his forward axis) in degrees for rolls/falls."""
    import characters as C
    import bl_util as U
    rig = C.get_rig(rig)
    cur = _ev(rig, "rotation_euler", frame, rig.rotation_euler[2], 2)
    a = math.radians(facing_deg)
    a = cur + ((a - cur + math.pi) % (2 * math.pi) - math.pi)
    U.key(rig, "location", frame, (float(xy[0]), float(xy[1]), float(z)), interp=interp)
    U.key(rig, "rotation_euler", frame, (math.radians(tilt[0]), math.radians(tilt[1]), a), interp=interp)
    return a


def root_at(rig, frame):
    """(x, y, z, facing_deg) of the rig object at `frame` from its keys (current values when unkeyed)."""
    x, y, z = (_ev(rig, "location", frame, rig.location[i], i) for i in range(3))
    a = _ev(rig, "rotation_euler", frame, rig.rotation_euler[2], 2)
    return x, y, z, math.degrees(a)


def apply_pose(rig, name_or_spec, mirror=False, update=True):
    """Set a pose WITHOUT keys (atlas, previews, tests): characters.apply_pose on resolve(name, rig) plus what
    apply_pose does not know - {'sheathed': pull} controllers (blade pulled out along the saya), {'slung': grip}
    spear grabs and 4-value saya settings (turn / tilt).  Returns the resolved spec."""
    import bpy
    import characters as C
    from mathutils import Matrix
    rig = C.get_rig(rig)
    char = char_of(rig)
    sp = resolve(name_or_spec, rig, mirror)
    ap = dict(sp)
    c = sp.get("ctrl")
    pull = slung = None
    if isinstance(c, dict) and "sheathed" in c:
        pull = float(c["sheathed"]) * SCALE[char]
        ap["ctrl"] = "sheathed"
    if isinstance(c, dict) and "slung" in c:
        slung = float(c["slung"])
        ap["ctrl"] = {"grip": (0.0, -0.3, 1.0), "dir": (0.0, -1.0, 0.0)}
    saya = sp.get("saya")
    if saya is not None and len(saya) > 2:
        ap["saya"] = tuple(saya[:2])
    C.apply_pose(rig, ap, update)
    ctrl_ob = bpy.data.objects[f"{char}_sword_ctrl"]
    if saya is not None and len(saya) > 2:
        bpy.data.objects[f"{char}_saya"].matrix_basis = saya_matrix(rig, *saya)
        bpy.context.view_layer.update()
        if ap.get("ctrl") == "sheathed":
            ctrl_ob.matrix_basis = C.sheathed_ctrl_matrix(rig, None)
            bpy.context.view_layer.update()
    if slung is not None:
        ctrl_ob.matrix_basis = C.slung_spear_ctrl_matrix(None, slung)
        bpy.context.view_layer.update()
    if pull:
        ctrl_ob.matrix_basis = C.sheathed_ctrl_matrix(rig, None) @ Matrix.Translation((0.0, -pull, 0.0))
        for n, vis in ((f"{char}_katana_hand", True), (f"{char}_katana_sheathed", False)):
            o = bpy.data.objects.get(n)
            if o is not None:
                o.hide_render = o.hide_viewport = not vis
        if char == "SAINT" and bpy.data.objects.get("SAINT_katana_hand_tip") is not None:
            o = bpy.data.objects["SAINT_katana_hand_tip"]
            o.hide_render = o.hide_viewport = False
        bpy.context.view_layer.update()
    if slung is not None or pull:
        for sd, v in (sp.get("elbow") or {}).items():
            if v == "auto":
                C.auto_elbow(rig, None, sd, key=True)
    return sp


def names(cat=None, char=None):
    """Pose names (optionally of one category / usable by one character)."""
    out = []
    for n, p in POSES.items():
        if cat is not None and p.get("cat") != cat:
            continue
        if char is not None and p.get("chars") and char not in p["chars"]:
            continue
        out.append(n)
    return out


def _n(x, y, z):
    """Normalised direction tuple."""
    return _norm((x, y, z))


def scale_legs(legs, k=1.0, kx=None):
    """legs dict with every ball position scaled (k along y, kx along x; stance length / width)."""
    if legs is None:
        return None
    kx = k if kx is None else kx
    out = {}
    for side, lg in legs.items():
        lg = dict(lg)
        if "ball" in lg:
            lg["ball"] = (lg["ball"][0] * kx, lg["ball"][1] * k)
        out[side] = lg
    return out


SAINT_STYLE = dict(lean=0.55, twist=0.75, side=0.6, crouch=0.55, stance=0.85, width=1.0)


def duo(desc, cat, t=None, arms=None, hips=(0.0, 0.0, 0.0), legs=None, ctrl=None, left="free", saint=None,
        extra_body=None, **kw):
    """A pose for both duelists from trunk parameters `t` (torso() kwargs): the SHINOBI gets them as written
    (low, coiled); the SAINT gets an automatic calmer variant - lean x0.55, twist x0.75, crouch x0.55, stance
    x0.85 (SAINT_STYLE) - merged with `saint` (explicit per_char overrides: any spec key, torso kwargs under
    "t")."""
    t = dict(t or {})
    body = merge(torso(**t), arms or {}, extra_body or {})
    p = pose(desc, cat, body=body, hips=hips, legs=legs, ctrl=ctrl, left=left, **kw)
    s = dict(saint or {})
    ts = dict(t)
    for k in ("lean", "twist", "side"):
        if k in ts:
            ts[k] = ts[k] * SAINT_STYLE[k]
    ts.update(s.pop("t", {}) or {})
    sb = merge(torso(**ts), extra_body or {})
    ov = dict(sb)
    if "hips_offset" not in s:
        ov["hips_offset"] = (hips[0], hips[1] * SAINT_STYLE["crouch"], hips[2] * 0.7)
    if "legs" not in s and legs is not None:
        ov["legs"] = scale_legs(legs, SAINT_STYLE["stance"], SAINT_STYLE["width"])
    ov.update(s)
    p["per_char"] = {"SAINT": ov}
    return p


# =============================================================================================
# THE POSE LIBRARY
# Rig space, facing -Y (forward = -y), his left = +x, SHINOBI metres (x1.85/1.72 for the SAINT).
# SHINOBI: low, coiled, two-handed.  SAINT (per_char): upright, grounded, economical.
# =============================================================================================
HANG_L = arm("L", flex=6, abd=-40, elbow=12, wflex=5)
HANG_R = arm("R", flex=6, abd=-40, elbow=12, wflex=5)
GUARD_ARMS = merge(arm("L", flex=35, abd=-25, rot=10, elbow=55), arm("R", flex=35, abd=-25, rot=10, elbow=55))
SAINT_UP = dict(hips_offset=(0.0, -0.04, 0.01))

# ---------------------------------------------------------------------------------------------- stands / guards
_add("relaxed", pose(
    "relaxed stand, katana sheathed, arms hanging", "stand",
    body=merge(torso(lean=2), HANG_L, HANG_R),
    hips=(0.0, -0.015, 0.0),
    legs={"R": foot(-0.11, -0.10, yaw=-8), "L": foot(0.11, -0.08, yaw=8)},
    arm="fk"))

_add("relaxed_saya", pose(
    "relaxed stand, left hand resting on the saya mouth (thumb on the tsuba), right arm hanging", "stand",
    body=merge(torso(lean=2, twist=3), HANG_R, arm("L", flex=15, abd=-30, elbow=70)),
    hips=(0.0, -0.02, 0.0),
    legs={"R": foot(-0.11, -0.12, yaw=-8), "L": foot(0.11, -0.06, yaw=10)},
    left="saya", arm="fk"))

_add("chudan", pose(
    "two-handed middle guard (seigan): tip at the opponent's throat, right foot forward, rear heel up", "guard",
    body=merge(torso(lean=9, twist=-5), GUARD_ARMS),
    hips=(0.0, -0.11, 0.02),
    legs=stance(front=0.30, back=0.32, width=0.24, heel_back=22),
    ctrl=blade((-0.03, -0.38, 0.98), elev(27)),
    left="grip",
    per_char={"SAINT": dict(torso(lean=2, twist=-4), hips_offset=(0.0, -0.05, 0.01),
                            legs=stance(front=0.24, back=0.26, width=0.26, heel_back=10),
                            ctrl=blade((-0.03, -0.37, 1.00), elev(24)))}))

_add("chudan_1h", pose(
    "one-handed middle guard, left hand on the saya (the elder testing a student, Act I)", "guard",
    body=merge(torso(lean=3, twist=-12), arm("L", flex=15, abd=-30, elbow=70)),
    hips=(0.0, -0.06, 0.0),
    legs=stance(front=0.26, back=0.26, width=0.26, heel_back=10),
    ctrl=blade((-0.14, -0.40, 1.02), elev(20, yaw=4)),
    left="saya"))

_add("low_1h", pose(
    "one-handed low guard: right fist in front of the right hip, blade forward-down at the knees, left hand on the "
    "saya - the elder's resting guard in Act I", "guard",
    body=merge(torso(lean=2, twist=-10), arm("L", flex=15, abd=-30, elbow=70)),
    hips=(0.0, -0.04, 0.0),
    legs=stance(front=0.20, back=0.24, width=0.28, heel_back=6),
    ctrl=blade((-0.16, -0.24, 0.92), elev(-25, yaw=6)),
    left="saya"))

_add("hasso", pose(
    "hasso: blade upright beside the right shoulder, tilted back, edge forward; left foot forward", "guard",
    body=merge(torso(lean=6, twist=-14), GUARD_ARMS),
    hips=(0.0, -0.10, 0.0),
    legs=stance(front=0.28, back=0.30, width=0.24, lead="L", heel_back=18),
    ctrl=blade((-0.14, -0.20, 1.36), (0.06, 0.40, 0.91), edge=(0.0, -0.91, 0.40), roll=-30),
    left="grip",
    per_char={"SAINT": dict(torso(lean=1, twist=-10), hips_offset=(0.0, -0.05, 0.0))}))

_add("jodan", pose(
    "jodan (upper guard): blade high over the head, tip back-up, edge forward; left foot forward", "guard",
    body=merge(torso(lean=-4, twist=-6, look_pitch=4), GUARD_ARMS),
    hips=(0.0, -0.08, 0.0),
    legs=stance(front=0.30, back=0.30, width=0.24, lead="L", heel_back=18),
    ctrl=blade((-0.03, -0.24, 1.76), (0.0, 0.62, 0.78), edge=(0.0, -0.78, 0.62)),
    left="grip",
    per_char={"SAINT": dict(torso(lean=-2, twist=-4), hips_offset=(0.0, -0.04, 0.0),
                            ctrl=blade((-0.03, -0.34, 1.74), (0.0, 0.55, 0.83), edge=(0.0, -0.83, 0.55)),
                            hat_tilt=(8.0, 0.0))}))

_add("waki", pose(
    "waki-gamae: blade hidden low behind the right hip, tip back and down, body turned, left foot forward", "guard",
    body=merge(torso(lean=10, twist=-32, look_yaw=0), GUARD_ARMS),
    hips=(0.0, -0.13, 0.0),
    legs=stance(front=0.30, back=0.32, width=0.26, lead="L", yaw_back=-30, heel_back=15),
    ctrl=blade((-0.18, -0.10, 0.88), (-0.40, 0.85, -0.34), roll=30),
    left="grip"))

_add("gedan", pose(
    "gedan (lower guard): tip low at the opponent's knees", "guard",
    body=merge(torso(lean=12, twist=-4), GUARD_ARMS),
    hips=(0.0, -0.12, 0.02),
    legs=stance(front=0.30, back=0.32, width=0.24, heel_back=20),
    ctrl=blade((-0.09, -0.42, 0.84), elev(-36), roll=-30),
    left="grip",
    per_char={"SAINT": dict(torso(lean=4, twist=-3), hips_offset=(0.0, -0.05, 0.01))}))

_add("iai_crouch", pose(
    "iai crouch: sunk low, right fist on the sheathed hilt, left fist on the saya (turned edge-out), weight forward",
    "iai",
    body=merge(torso(lean=16, twist=10, look_pitch=-4), {"shoulder.R": (20.0, 0.0, 0.0)}),
    hips=(0.0, -0.17, 0.02),
    legs=stance(front=0.36, back=0.34, width=0.26, heel_back=25),
    ctrl="sheathed", left="saya", saya=(0.0, 60.0),
    elbow={"R": "auto", "L": "auto"},
    per_char={"SAINT": dict(torso(lean=12, twist=8, look_pitch=-6), hips_offset=(0.0, -0.13, 0.02))}))

# ---------------------------------------------------------------------------------------------- stances used by attacks
ST_GUARD = stance(front=0.30, back=0.32, width=0.24, heel_back=22)
ST_COIL = stance(front=0.24, back=0.36, width=0.25, heel_back=8, heel_front=10)       # weight back, front foot light
ST_LUNGE = stance(front=0.50, back=0.40, width=0.26, heel_back=34)                    # weight forward
ST_DEEP = stance(front=0.62, back=0.42, width=0.28, heel_back=40)                     # deep lunge (thrust, iai)
ST_WIDE = stance(front=0.18, back=0.22, width=0.46, heel_back=12, yaw_back=25)        # square, wide (horizontal cuts)
FREE_BAL_L = arm("L", flex=40, abd=10, elbow=35, wflex=-10)                           # free left arm, balancing

# ---------------------------------------------------------------------------------------------- attacks
# Each attack kind has _windup (anticipation, coiled, weight back), _strike (impact: the blade crosses the target
# line, weight forward) and _follow (follow-through).  moves.slash keys them with arcs between them; the SAINT's
# one-handed Act-I cuts use the same blade poses with his left hand on the saya (moves keep the lane's left hand).
_add("diag_down_R_windup", duo(
    "kesa windup: blade cocked over the right shoulder, trunk wound right, weight back", "attack",
    t=dict(lean=-4, twist=-30, side=-4), arms=FREE_BAL_L, hips=(0.0, -0.14, -0.03), legs=ST_COIL,
    ctrl=blade((-0.22, -0.06, 1.50), _n(-0.30, 0.52, 0.80), edge=_n(0.0, -0.8, 0.6)), left="grip"))
_add("diag_down_R_strike", duo(
    "kesa strike (right shoulder -> left hip): blade crossing the line down-left, lunge", "attack",
    t=dict(lean=16, twist=12, side=4), arms=FREE_BAL_L, hips=(0.0, -0.19, 0.05), legs=ST_LUNGE,
    ctrl=blade((-0.06, -0.48, 1.12), _n(-0.30, -0.91, -0.28), edge=_n(0.39, -0.38, -0.84)), left="grip"))
_add("diag_down_R_follow", duo(
    "kesa follow-through: blade low at the left hip, trunk turned left, head up", "attack",
    t=dict(lean=22, twist=30, side=6, look_pitch=-6), arms=FREE_BAL_L, hips=(0.0, -0.21, 0.05), legs=ST_LUNGE,
    ctrl=blade((0.12, -0.30, 0.84), _n(0.45, -0.30, -0.84), edge=_n(0.8, 0.3, 0.3)), left="grip"))

_add("diag_down_L_windup", duo(
    "gyaku-kesa windup: blade cocked over the LEFT shoulder, trunk wound left", "attack",
    t=dict(lean=-4, twist=28, side=4), arms=FREE_BAL_L, hips=(0.0, -0.13, -0.03), legs=ST_COIL,
    ctrl=blade((0.10, -0.12, 1.50), _n(0.32, 0.50, 0.80), edge=_n(0.0, -0.8, 0.6)), left="grip",
    saint=dict(hat_tilt=(8.0, -4.0))))
_add("diag_down_L_strike", duo(
    "gyaku-kesa strike (left shoulder -> right hip): blade crossing the line down-right", "attack",
    t=dict(lean=16, twist=-12, side=-4), arms=FREE_BAL_L, hips=(0.0, -0.19, 0.05), legs=ST_LUNGE,
    ctrl=blade((0.0, -0.48, 1.12), _n(0.30, -0.91, -0.28), edge=_n(-0.39, -0.38, -0.84)), left="grip"))
_add("diag_down_L_follow", duo(
    "gyaku-kesa follow-through: blade low at the right hip", "attack",
    t=dict(lean=22, twist=-30, side=-6, look_pitch=-6), arms=FREE_BAL_L, hips=(0.0, -0.21, 0.05), legs=ST_LUNGE,
    ctrl=blade((-0.18, -0.30, 0.84), _n(-0.45, -0.30, -0.84), edge=_n(-0.8, 0.3, 0.3)), left="grip"))

_add("rising_L_windup", duo(
    "gyaku kiriage windup: blade low in front on the LEFT, tip down-left, trunk wound left, sunk", "attack",
    t=dict(lean=14, twist=32, side=6), arms=FREE_BAL_L, hips=(0.0, -0.16, -0.02), legs=ST_COIL,
    ctrl=blade((0.02, -0.34, 0.86), _n(0.35, -0.60, -0.72), edge=_n(0.5, 0.5, 0.3)), left="grip"))
_add("rising_L_strike", duo(
    "rising cut from his lower left to upper right: blade rising across the line, lunge", "attack",
    t=dict(lean=10, twist=-6, side=-4), arms=FREE_BAL_L, hips=(0.0, -0.18, 0.04), legs=ST_LUNGE,
    ctrl=blade((-0.04, -0.46, 1.10), _n(-0.25, -0.90, 0.36), edge=_n(-0.5, -0.2, 0.84)), left="grip"))
_add("rising_L_follow", duo(
    "rising cut follow-through: blade high on the right, trunk opened right, rising", "attack",
    t=dict(lean=-2, twist=-26, side=-8), arms=FREE_BAL_L, hips=(0.0, -0.12, 0.03), legs=ST_LUNGE,
    ctrl=blade((-0.22, -0.30, 1.48), _n(-0.50, -0.42, 0.76), edge=_n(-0.6, 0.3, 0.7)), left="grip"))

_add("rising_R_windup", duo(
    "kiriage windup: blade low on the RIGHT (waki), trunk wound right, sunk", "attack",
    t=dict(lean=14, twist=-32, side=-6), arms=FREE_BAL_L, hips=(0.0, -0.16, -0.02), legs=ST_COIL,
    ctrl=blade((-0.20, -0.14, 0.88), _n(-0.45, 0.62, -0.64), edge=_n(-0.2, 0.3, -0.9)), left="grip"))
_add("rising_R_strike", duo(
    "rising cut from his lower right to upper left", "attack",
    t=dict(lean=10, twist=6, side=4), arms=FREE_BAL_L, hips=(0.0, -0.18, 0.04), legs=ST_LUNGE,
    ctrl=blade((-0.02, -0.46, 1.10), _n(0.25, -0.90, 0.36), edge=_n(0.5, -0.2, 0.84)), left="grip"))
_add("rising_R_follow", duo(
    "rising cut follow-through: blade high on the left", "attack",
    t=dict(lean=-2, twist=26, side=8), arms=FREE_BAL_L, hips=(0.0, -0.12, 0.03), legs=ST_LUNGE,
    ctrl=blade((0.14, -0.30, 1.48), _n(0.50, -0.42, 0.76), edge=_n(0.6, 0.3, 0.7)), left="grip"))

_add("horizontal_R_windup", duo(
    "horizontal windup: blade drawn back on the right at chest height, tip back-right, trunk wound right", "attack",
    t=dict(lean=4, twist=-42), arms=FREE_BAL_L, hips=(0.0, -0.12, -0.02), legs=ST_WIDE,
    ctrl=blade((-0.32, -0.10, 1.18), _n(-0.85, 0.50, 0.15), edge=_n(-0.5, -0.86, 0.0)), left="grip"))
_add("horizontal_R_strike", duo(
    "horizontal cut right -> left: blade level across the front, edge leading left", "attack",
    t=dict(lean=10, twist=-4), arms=FREE_BAL_L, hips=(0.0, -0.15, 0.03), legs=ST_WIDE,
    ctrl=blade((-0.06, -0.52, 1.14), _n(0.12, -0.99, 0.04), edge=_n(0.99, 0.12, 0.0)), left="grip"))
_add("horizontal_R_follow", duo(
    "horizontal follow-through: blade swept round to the left, trunk turned left", "attack",
    t=dict(lean=12, twist=38), arms=FREE_BAL_L, hips=(0.0, -0.15, 0.03), legs=ST_WIDE,
    ctrl=blade((0.30, -0.34, 1.10), _n(0.92, -0.38, -0.05), edge=_n(0.38, 0.92, 0.0)), left="grip"))

_add("horizontal_L_windup", duo(
    "backhand horizontal windup: blade carried to the LEFT, tip out left-forward, trunk wound left", "attack",
    t=dict(lean=4, twist=40), arms=FREE_BAL_L, hips=(0.0, -0.12, -0.02), legs=ST_WIDE,
    ctrl=blade((0.10, -0.30, 1.10), _n(0.85, -0.50, 0.15), edge=_n(0.5, 0.86, 0.0)), left="grip"))
_add("horizontal_L_strike", duo(
    "horizontal cut left -> right: blade level across the front, edge leading right", "attack",
    t=dict(lean=10, twist=4), arms=FREE_BAL_L, hips=(0.0, -0.15, 0.03), legs=ST_WIDE,
    ctrl=blade((-0.02, -0.52, 1.14), _n(-0.12, -0.99, 0.04), edge=_n(-0.99, 0.12, 0.0)), left="grip"))
_add("horizontal_L_follow", duo(
    "backhand follow-through: blade swept round to the right", "attack",
    t=dict(lean=12, twist=-38), arms=FREE_BAL_L, hips=(0.0, -0.15, 0.03), legs=ST_WIDE,
    ctrl=blade((-0.36, -0.30, 1.10), _n(-0.92, -0.38, -0.05), edge=_n(-0.38, 0.92, 0.0)), left="grip"))

_add("overhead_windup", duo(
    "shomen windup: blade raised high behind the head, back arched, weight back", "attack",
    t=dict(lean=-8, twist=-4, look_pitch=-4), arms=FREE_BAL_L, hips=(0.0, -0.13, -0.04), legs=ST_COIL,
    ctrl=blade((-0.03, -0.12, 1.79), _n(0.0, 0.78, 0.62), edge=_n(0.0, -0.62, 0.78)), left="grip",
    saint=dict(ctrl=blade((-0.03, -0.54, 1.70), _n(0.0, 0.62, 0.78), edge=_n(0.0, -0.78, 0.62)), hat_tilt=(24.0, 0.0))))
_add("overhead_strike", duo(
    "shomen strike: blade straight down the centre line at head height, arms extended, lunge", "attack",
    t=dict(lean=16, look_pitch=-4), arms=FREE_BAL_L, hips=(0.0, -0.19, 0.05), legs=ST_LUNGE,
    ctrl=blade((-0.03, -0.56, 1.26), elev(-6)), left="grip"))
_add("overhead_follow", duo(
    "shomen follow-through: blade driven down to gedan, trunk folded", "attack",
    t=dict(lean=26, look_pitch=-10), arms=FREE_BAL_L, hips=(0.0, -0.23, 0.05), legs=ST_LUNGE,
    ctrl=blade((-0.03, -0.44, 0.90), elev(-40)), left="grip"))

_add("thrust_windup", duo(
    "tsuki windup: blade pulled back level at the right hip, point at the target, weight back", "attack",
    t=dict(lean=6, twist=-26), arms=FREE_BAL_L, hips=(0.0, -0.13, -0.04), legs=ST_COIL,
    ctrl=blade((-0.16, -0.06, 1.02), elev(4, yaw=6)), left="grip"))
_add("thrust_strike", duo(
    "tsuki: full extension, deep lunge, trunk square, point driven forward", "attack",
    t=dict(lean=18, twist=2), arms=FREE_BAL_L, hips=(0.0, -0.22, 0.06), legs=ST_DEEP,
    ctrl=blade((-0.06, -0.66, 1.12), elev(3)), left="grip"))
_add("thrust_follow", duo(
    "tsuki follow-through: extension held, rear leg driving", "attack",
    t=dict(lean=22, twist=4), arms=FREE_BAL_L, hips=(0.0, -0.24, 0.07), legs=ST_DEEP,
    ctrl=blade((-0.05, -0.72, 1.10), elev(1)), left="grip"))


# ---------------------------------------------------------------------------------------------- iai, draw, sheathe
_add("iai_draw_1", duo(
    "iai draw: rising out of the crouch, blade 30 cm out along the saya, saya pulled back", "iai",
    t=dict(lean=14, twist=6), hips=(0.0, -0.16, 0.03), legs=stance(front=0.42, back=0.36, width=0.26, heel_back=28),
    ctrl={"sheathed": 0.28}, left="saya", saya=(0.06, 60.0), elbow={"R": "auto"}))
_add("iai_draw_2", duo(
    "iai draw: the kissaki at the koiguchi, right arm driving forward, deep step", "iai",
    t=dict(lean=16, twist=0), hips=(0.0, -0.19, 0.05), legs=ST_DEEP,
    ctrl={"sheathed": 0.66}, left="saya", saya=(0.11, 60.0)))
_add("iai_cut", duo(
    "iai draw-cut: one-handed horizontal from the left hip, arm extended, saya-biki pulls the scabbard back",
    "iai", t=dict(lean=14, twist=-10), hips=(0.0, -0.21, 0.06), legs=ST_DEEP,
    ctrl=blade((-0.10, -0.60, 1.16), _n(-0.30, -0.95, 0.03), edge=_n(-0.95, 0.30, 0.0)), left="saya",
    saya=(0.06, 60.0), elbow={"L": "auto"}))
_add("iai_follow", duo(
    "iai follow-through: blade swept out to the right, chest open, eyes on the opponent", "iai",
    t=dict(lean=12, twist=-30), hips=(0.0, -0.20, 0.05), legs=ST_DEEP,
    ctrl=blade((-0.46, -0.36, 1.22), _n(-0.92, -0.38, 0.08), edge=_n(-0.38, 0.92, 0.0)), left="saya",
    saya=(0.04, 50.0), elbow={"L": "auto"}))

_add("draw_grab", duo(
    "draw 1/4: right fist on the hilt, left fist turns the saya edge-out (koiguchi o kiru)", "draw",
    t=dict(lean=8, twist=8), hips=(0.0, -0.06, 0.0), legs=stance(front=0.22, back=0.24, width=0.26, heel_back=8),
    ctrl="sheathed", left="saya", saya=(0.0, 45.0), elbow={"R": "auto", "L": "auto"}))
_add("draw_pull", duo(
    "draw 2/4: blade half out along the saya axis, saya pulled back (saya-biki)", "draw",
    t=dict(lean=6, twist=2), hips=(0.0, -0.07, 0.0), legs=stance(front=0.24, back=0.24, width=0.26, heel_back=10),
    ctrl={"sheathed": 0.40}, left="saya", saya=(0.08, 45.0), elbow={"R": "auto"}))
_add("draw_clear", duo(
    "draw 3/4: the kissaki clears the koiguchi, right arm extended forward-right", "draw",
    t=dict(lean=6, twist=-8), hips=(0.0, -0.08, 0.0), legs=stance(front=0.26, back=0.26, width=0.26, heel_back=12),
    ctrl={"sheathed": 0.75}, left="saya", saya=(0.11, 30.0)))
_add("draw_swing", duo(
    "draw 4/4: blade swung up and over into guard, left hand coming to the kashira", "draw",
    t=dict(lean=6, twist=-6), hips=(0.0, -0.09, 0.0), legs=ST_GUARD,
    ctrl=blade((-0.10, -0.34, 1.12), elev(45, yaw=-10)), left="free", arms=arm("L", flex=40, abd=-20, elbow=60)))

_add("sheathe_quick_1", duo(
    "quick noto 1/3: the kissaki at the koiguchi on the saya axis, left fist on the saya", "sheathe",
    t=dict(lean=6, twist=10, look_pitch=0), hips=(0.0, -0.05, 0.0),
    legs=stance(front=0.22, back=0.24, width=0.26, heel_back=8),
    ctrl={"sheathed": 0.76}, left="saya", saya=(0.06, 30.0)))
_add("sheathe_quick_2", duo(
    "quick noto 2/3: blade half in", "sheathe",
    t=dict(lean=4, twist=6), hips=(0.0, -0.04, 0.0), legs=stance(front=0.22, back=0.24, width=0.26, heel_back=6),
    ctrl={"sheathed": 0.35}, left="saya", saya=(0.03, 15.0), elbow={"R": "auto"}))
_add("sheathe_done", duo(
    "noto 3/3: tsuba home on the koiguchi (the click), fist still on the hilt", "sheathe",
    t=dict(lean=2, twist=4), hips=(0.0, -0.03, 0.0), legs=stance(front=0.20, back=0.22, width=0.26, heel_back=4),
    ctrl="sheathed", left="saya", saya=(0.0, 0.0), elbow={"R": "auto", "L": "auto"}))
_add("sheathe_slow_chiburi", duo(
    "slow noto 1/4: chiburi - the blade flicked out and down to the right, one-handed", "sheathe",
    t=dict(lean=8, twist=-18), hips=(0.0, -0.08, 0.0), legs=stance(front=0.24, back=0.26, width=0.30, heel_back=8),
    ctrl=blade((-0.44, -0.32, 0.96), _n(-0.55, -0.72, -0.42)), left="saya", saya=(0.0, 20.0)))
_add("sheathe_slow_1", duo(
    "slow noto 2/4: the back of the blade laid across the left fist, kissaki at the koiguchi, head bowed", "sheathe",
    t=dict(lean=8, twist=12, look_pitch=14), hips=(0.0, -0.06, 0.0),
    legs=stance(front=0.22, back=0.24, width=0.28, heel_back=6),
    ctrl={"sheathed": 0.78}, left="saya", saya=(0.05, 20.0)))
_add("sheathe_slow_2", duo(
    "slow noto 3/4: blade sliding in, half way", "sheathe",
    t=dict(lean=6, twist=8, look_pitch=10), hips=(0.0, -0.05, 0.0),
    legs=stance(front=0.22, back=0.24, width=0.28, heel_back=5),
    ctrl={"sheathed": 0.40}, left="saya", saya=(0.03, 10.0), elbow={"R": "auto"}))

# ---------------------------------------------------------------------------------------------- aerial, sliding
_add("plunge_windup", duo(
    "aerial overhead windup (in the air): back arched, blade high behind the head, knees tucked", "aerial",
    t=dict(lean=-12, look_pitch=-6), hips=(0.0, 0.0, 0.0),
    legs={"R": foot(-0.12, -0.22, lift=0.34, air=True, heel=20), "L": foot(0.12, 0.10, lift=0.26, air=True, heel=30)},
    ctrl=blade((-0.03, -0.10, 1.86), _n(0.0, 0.82, 0.57), edge=_n(0.0, -0.57, 0.82)), left="grip"))
_add("plunge_strike", duo(
    "aerial overhead strike (descending): trunk folded over the blade, arms extended, legs reaching down", "aerial",
    t=dict(lean=24, look_pitch=-8), hips=(0.0, 0.0, 0.02),
    legs={"R": foot(-0.12, -0.30, lift=0.06, air=True, heel=10), "L": foot(0.12, 0.26, lift=0.14, air=True, heel=25)},
    ctrl=blade((-0.03, -0.60, 1.28), elev(-18)), left="grip"))
_add("plunge_land", duo(
    "aerial strike landing: deep crouch absorbing, blade driven low forward", "aerial",
    t=dict(lean=30, look_pitch=-16), hips=(0.0, -0.36, 0.04), legs=stance(front=0.30, back=0.30, width=0.32, heel_back=30),
    ctrl=blade((-0.03, -0.46, 0.78), elev(-42)), left="grip"))
_add("slide_cut", duo(
    "sliding low cut: lead leg extended forward (sliding), rear knee near the ground, blade swept low", "aerial",
    t=dict(lean=18, twist=-10), hips=(0.0, -0.46, 0.0),
    legs={"R": foot(-0.14, -0.80, heel=-25), "L": foot(0.16, 0.26, heel=55)},
    arms=arm("L", flex=-25, abd=25, elbow=15),
    ctrl=blade((-0.18, -0.44, 0.52), _n(0.35, -0.93, 0.05), edge=_n(0.93, 0.35, 0.0)), left="free"))

# ---------------------------------------------------------------------------------------------- defence
_add("deflect_high", duo(
    "high block (jodan-uke): blade flat above the head, tip to his right, edge up, knees braced", "deflect",
    t=dict(lean=-2, look_pitch=-6), hips=(0.0, -0.15, 0.0), legs=ST_GUARD,
    ctrl=blade((-0.02, -0.30, 1.62), _n(-0.95, -0.12, 0.28), edge=(0.0, 0.0, 1.0)), left="grip",
    saint=dict(hat_tilt=(14.0, 0.0), ctrl=blade((-0.02, -0.42, 1.58), _n(-0.95, -0.12, 0.28), edge=(0.0, 0.0, 1.0)))))
_add("deflect_mid_L", duo(
    "middle block on his LEFT: blade upright, tip up-left, edge out to the left", "deflect",
    t=dict(lean=6, twist=14), hips=(0.0, -0.13, 0.0), legs=ST_GUARD,
    ctrl=blade((0.06, -0.36, 1.04), _n(0.40, -0.30, 0.87), edge=_n(0.85, -0.45, -0.25)), left="grip"))
_add("deflect_mid_R", duo(
    "middle block on his RIGHT: blade upright, tip up-right, edge out to the right", "deflect",
    t=dict(lean=6, twist=-14), hips=(0.0, -0.13, 0.0), legs=ST_GUARD,
    ctrl=blade((-0.14, -0.36, 1.04), _n(-0.40, -0.30, 0.87), edge=_n(-0.85, -0.45, -0.25)), left="grip"))
_add("deflect_low", duo(
    "low block on his right: tip down, edge out-right, sunk", "deflect",
    t=dict(lean=14, twist=-10), hips=(0.0, -0.21, 0.0), legs=ST_GUARD,
    ctrl=blade((-0.12, -0.34, 1.06), _n(-0.30, -0.35, -0.89), edge=_n(-0.85, -0.40, 0.30)), left="grip"))
_add("deflect_overhead_block", duo(
    "roof block: fists high on the left, blade slanting down to the right over the head so the blow slides off",
    "deflect", t=dict(lean=2, twist=-8, look_pitch=-8), hips=(0.0, -0.16, 0.0), legs=ST_GUARD,
    ctrl=blade((0.02, -0.30, 1.60), _n(-0.85, -0.20, -0.48), edge=_n(-0.4, 0.0, 0.9)), left="grip"))
_add("perfect_deflect", duo(
    "perfect-deflect snap: the blade driven forward-out into the blow, body compressed behind it", "deflect",
    t=dict(lean=14, twist=-10), hips=(0.0, -0.18, 0.03), legs=stance(front=0.34, back=0.34, width=0.26, heel_back=26),
    ctrl=blade((-0.10, -0.44, 1.12), _n(-0.50, -0.55, 0.67), edge=_n(-0.70, -0.60, -0.30)), left="grip"))

# ---------------------------------------------------------------------------------------------- evasion, falls, contact
_add("dodge_side", duo(
    "sidestep to his left: weight shifted over the left foot, trunk leaning away, blade kept in guard", "evade",
    t=dict(lean=10, side=-12, look_roll=4), hips=(0.16, -0.16, 0.0),
    legs={"L": foot(0.36, -0.02, yaw=15), "R": foot(-0.14, 0.06, heel=20)},
    ctrl=blade((0.08, -0.36, 0.96), elev(22)), left="grip"))
_add("dodge_back", duo(
    "hop back: front foot pushing off, trunk upright, blade in guard", "evade",
    t=dict(lean=-6), hips=(0.0, -0.14, -0.08), legs={"R": foot(-0.12, -0.34, heel=28), "L": foot(0.12, 0.30)},
    ctrl=blade((-0.03, -0.34, 1.00), elev(24)), left="grip"))
_add("duck", duo(
    "duck under a sweep: deep squat, trunk folded, eyes up, blade low", "evade",
    t=dict(lean=38, look_pitch=-30), hips=(0.0, -0.52, 0.0),
    legs=stance(front=0.30, back=0.30, width=0.34, heel_back=35, heel_front=10),
    ctrl=blade((-0.03, -0.34, 0.60), elev(20)), left="grip"))
_add("jump_crouch", duo(
    "jump anticipation: loaded crouch, trunk forward, blade low", "evade",
    t=dict(lean=28, look_pitch=-16), hips=(0.0, -0.30, 0.0), legs=stance(front=0.12, back=0.12, width=0.30, heel_back=10),
    ctrl=blade((-0.10, -0.26, 0.70), elev(-20)), left="grip"))
_add("jump_air", duo(
    "jump (air): knees tucked, trunk upright, blade raised", "evade",
    t=dict(lean=8), hips=(0.0, 0.0, 0.0),
    legs={"R": foot(-0.12, -0.22, lift=0.40, air=True, heel=15), "L": foot(0.12, 0.06, lift=0.32, air=True, heel=25)},
    ctrl=blade((-0.03, -0.30, 1.40), elev(40)), left="grip"))
_add("jump_land", duo(
    "landing: deep crouch absorbing the impact, blade low forward", "evade",
    t=dict(lean=26, look_pitch=-14), hips=(0.0, -0.36, 0.02),
    legs=stance(front=0.22, back=0.24, width=0.34, heel_back=25),
    ctrl=blade((-0.03, -0.40, 0.72), elev(-10)), left="grip"))
_add("roll_tuck", duo(
    "roll (tucked ball): trunk fully folded, chin in, knees to the chest, blade held along the body", "evade",
    t=dict(lean=70, look_pitch=30, gaze=0.3), hips=(0.0, -0.50, 0.0),
    legs={"R": foot(-0.10, -0.16, lift=0.24, air=True, heel=30), "L": foot(0.10, -0.10, lift=0.30, air=True, heel=30)},
    arms=arm("L", flex=60, abd=-20, elbow=100),
    ctrl=blade((-0.12, -0.22, 0.72), _n(0.25, 0.90, 0.35)), left="free"))
_add("roll_rise", duo(
    "coming up out of a roll on one knee, blade low in guard", "evade",
    t=dict(lean=16, look_pitch=-8), hips=(0.0, -0.42, 0.0),
    legs={"L": foot(0.14, -0.34), "R": foot(-0.12, 0.40, heel=60)},
    ctrl=blade((-0.08, -0.40, 0.72), elev(15)), left="grip"))
_add("stagger_back", duo(
    "stagger back: hit off balance, trunk thrown back, blade and free arm flung out", "evade",
    t=dict(lean=-18, twist=10, look_pitch=10, gaze=0.5), hips=(0.0, -0.16, -0.10),
    legs={"R": foot(-0.12, -0.25, heel=20), "L": foot(0.14, 0.42)},
    arms=arm("L", flex=30, abd=40, elbow=20),
    ctrl=blade((-0.26, 0.04, 1.42), _n(-0.30, 0.60, 0.74)), left="free"))
_add("skid", duo(
    "skid back: very low, sliding, one-handed blade dragging its tip in the dirt, free hand forward", "evade",
    t=dict(lean=28, twist=-15, look_pitch=-10), hips=(0.0, -0.40, 0.0),
    legs={"R": foot(-0.14, -0.42, yaw=-20), "L": foot(0.18, 0.30, heel=30, yaw=25)},
    arms=arm("L", flex=70, abd=0, elbow=20),
    ctrl=blade((-0.24, -0.36, 0.62), _n(-0.10, -0.55, -0.83)), left="free"))
_add("kick_chamber", duo(
    "front kick chamber: right knee drawn up high, standing leg braced", "contact",
    t=dict(lean=-6), hips=(0.0, -0.06, -0.02),
    legs={"L": foot(0.10, 0.10, yaw=10), "R": foot(-0.10, -0.26, lift=0.52, air=True, heel=30, knee=(0.0, -0.6, 0.8))},
    ctrl=blade((-0.03, -0.30, 1.06), elev(35)), left="grip"))
_add("kick_extend", duo(
    "front push kick: leg driven out at belly height, sole forward, trunk leaning back", "contact",
    t=dict(lean=-14), hips=(0.0, -0.04, -0.06),
    legs={"L": foot(0.10, 0.12, yaw=12), "R": foot(-0.08, -0.74, lift=0.74, air=True, heel=-40)},
    ctrl=blade((-0.03, -0.26, 1.10), elev(45)), left="grip"))
_add("blade_lock", duo(
    "tsubazeriai: blades crossed near the guards at head height, chests close, rear leg driving", "contact",
    t=dict(lean=18, twist=-6), hips=(0.0, -0.15, 0.04), legs=stance(front=0.36, back=0.42, width=0.26, heel_back=36),
    ctrl=blade((-0.02, -0.30, 1.30), _n(0.10, -0.25, 0.96), edge=_n(0.2, -0.95, 0.0)), left="grip"))
_add("blade_lock_push", duo(
    "tsubazeriai, pressing: more lean, sunk lower, fists driven forward", "contact",
    t=dict(lean=24, twist=-8), hips=(0.0, -0.19, 0.06), legs=stance(front=0.40, back=0.46, width=0.26, heel_back=42),
    ctrl=blade((-0.02, -0.36, 1.26), _n(0.10, -0.32, 0.94), edge=_n(0.2, -0.94, 0.0)), left="grip",
    saint=dict(hat_tilt=(8.0, 0.0))))

# ---------------------------------------------------------------------------------------------- ceremony, stealth, story
_add("kneel_planted", pose(
    "kneel on the right knee, sword planted point-down in front, both fists on the hilt, head bowed "
    "(HANDOFF[3072] shinobi low point; the elder's S27 echo)", "story",
    body={"spine": (12, 0, 0), "chest": (8, 0, 0), "neck": (22, 0, 0), "head": (18, 0, 0)},
    hips=(0.0, -0.44, 0.0),
    legs={"L": {"ankle": (0.12, -0.42, 0.077)}, "R": {"ankle": (-0.11, 0.36, 0.11), "foot_pitch": 20, "toe": (-60, 0, 0)}},
    ctrl=blade((-0.03, -0.45, 0.66), (0.0, -0.15, -1.0), edge=(0.0, -1.0, 0.0)), left="grip",
    elbow={"R": "auto", "L": "auto"}))
_add("kneel_sword_planted", dict(POSES["kneel_planted"], desc="alias of kneel_planted (config.HANDOFF[3072] pose name)"))
_add("rise_kneel", duo(
    "rising from the kneel: left foot planted, weight coming over it, sword lifting out of the ground", "story",
    t=dict(lean=24, look_pitch=-6), hips=(0.0, -0.30, 0.02),
    legs={"L": foot(0.12, -0.32), "R": foot(-0.11, 0.30, heel=40)},
    ctrl=blade((-0.03, -0.40, 0.80), elev(-50)), left="grip"))
_add("bow", pose(
    "standing bow (rei): feet together, trunk 30 deg from the hips, hands along the thighs, katana sheathed", "story",
    body=merge(torso(lean=32, pelvis=0.55, gaze=0.25), arm("L", flex=-4, abd=-38, elbow=8), arm("R", flex=-4, abd=-38, elbow=8)),
    hips=(0.0, -0.02, -0.03),
    legs={"R": foot(-0.09, -0.10), "L": foot(0.09, -0.10)}, arm="fk"))
_add("crouch_hide", duo(
    "grass hiding (kusa-gakure): deep squat below the grass line, trunk folded, blade held low and flat", "story",
    t=dict(lean=45, look_pitch=-35), hips=(0.0, -0.60, 0.0),
    legs={"R": foot(-0.16, -0.20, heel=25), "L": foot(0.16, 0.14, heel=40)},
    ctrl=blade((-0.05, -0.36, 0.42), elev(-5)), left="grip",
    saint=dict(hips_offset=(0.0, -0.50, 0.0))))
_add("listen", duo(
    "eyes closed, listening: upright, head lowered and turned an ear toward the grass, hand resting on the hilt",
    "story", t=dict(lean=4, look_pitch=12, look_yaw=14), hips=(0.0, -0.05, 0.0),
    legs=stance(front=0.18, back=0.22, width=0.30, heel_back=0),
    ctrl="sheathed", left="saya", saya=(0.0, 20.0), elbow={"R": "auto", "L": "auto"}))
_add("jodan_sky", dict(POSES["jodan"], desc="jodan facing the storm (raise_to_sky): the head tipped up to the sky",
                       cat="guard", **torso(lean=-6, twist=-6, look_pitch=-26)))
_add("haori_grab", pose(
    "haori shed 1/2: right hand at the left collar, left shoulder rolled forward", "story",
    body=merge(torso(lean=4, twist=16), arm("R", flex=75, abd=-55, rot=25, elbow=105),
               arm("L", flex=20, abd=-30, elbow=40)),
    hips=(0.0, -0.05, 0.0), legs=stance(front=0.20, back=0.24, width=0.32, heel_back=4), arm="fk", chars=["SAINT"]))
_add("haori_sweep", pose(
    "haori shed 2/2: the coat flung off in one sweep, right arm thrown wide back-right, chest opened", "story",
    body=merge(torso(lean=2, twist=-34, side=6), arm("R", flex=25, abd=62, rot=-20, elbow=12),
               arm("L", flex=30, abd=38, elbow=22)),
    hips=(0.0, -0.08, 0.0), legs=stance(front=0.22, back=0.26, width=0.36, heel_back=8), arm="fk", chars=["SAINT"]))


# ---------------------------------------------------------------------------------------------- locomotion keys
# (moves.walk / run plant the feet procedurally; these keys give the body, bob and arm swing, and read in the atlas)
_add("walk_contact", pose(
    "walk: right heel strike, left toe-off, arms swinging opposite", "locomotion",
    body=merge(torso(lean=4, twist=6), arm("R", flex=-16, abd=-40, elbow=14), arm("L", flex=20, abd=-40, elbow=26)),
    hips=(0.0, -0.06, 0.0), legs={"R": foot(-0.09, -0.36, heel=-12), "L": foot(0.09, 0.28, heel=34)}, arm="fk"))
_add("walk_down", pose(
    "walk: weight accepted on the right leg (lowest point)", "locomotion",
    body=merge(torso(lean=5, twist=3), arm("R", flex=-8, abd=-40, elbow=14), arm("L", flex=12, abd=-40, elbow=22)),
    hips=(0.0, -0.06, 0.0), legs={"R": foot(-0.09, -0.18), "L": foot(0.09, 0.28, heel=48)}, arm="fk"))
_add("walk_pass", pose(
    "walk: passing (left leg swinging through, highest body)", "locomotion",
    body=merge(torso(lean=4), arm("R", flex=0, abd=-40, elbow=14), arm("L", flex=2, abd=-40, elbow=18)),
    hips=(0.0, -0.012, 0.0), legs={"R": foot(-0.09, 0.02), "L": foot(0.09, -0.02, lift=0.09, air=True, heel=12)},
    arm="fk"))
_add("walk_up", pose(
    "walk: right leg pushing, left leg reaching", "locomotion",
    body=merge(torso(lean=4, twist=-3), arm("R", flex=10, abd=-40, elbow=18), arm("L", flex=-8, abd=-40, elbow=16)),
    hips=(0.0, 0.0, 0.0), legs={"R": foot(-0.09, 0.20, heel=22), "L": foot(0.09, -0.26, lift=0.05, air=True, heel=-10)},
    arm="fk"))
_add("run_contact", pose(
    "run: right foot striking under the hips, left leg trailing high, arms pumping", "locomotion",
    body=merge(torso(lean=14, twist=8), arm("R", flex=-35, abd=-35, elbow=80), arm("L", flex=50, abd=-35, elbow=85)),
    hips=(0.0, -0.09, 0.02),
    legs={"R": foot(-0.08, -0.30, heel=-5), "L": foot(0.10, 0.46, lift=0.26, air=True, heel=40)}, arm="fk"))
_add("run_flight", pose(
    "run: flight phase, legs scissored", "locomotion",
    body=merge(torso(lean=16, twist=-6), arm("R", flex=40, abd=-35, elbow=85), arm("L", flex=-30, abd=-35, elbow=80)),
    hips=(0.0, -0.03, 0.02),
    legs={"R": foot(-0.08, 0.34, lift=0.30, air=True, heel=40), "L": foot(0.10, -0.36, lift=0.20, air=True, heel=-5)},
    arm="fk"))
_add("dash", duo(
    "dash: explosive low forward drive, trunk pitched over the lead knee, blade trailing low", "locomotion",
    t=dict(lean=30, twist=-8, look_pitch=-20), hips=(0.0, -0.22, 0.06),
    legs={"R": foot(-0.10, -0.46, heel=10), "L": foot(0.12, 0.50, heel=45)},
    ctrl=blade((-0.16, -0.10, 0.80), _n(-0.25, 0.60, -0.35)), left="grip"))
_add("strafe_open", duo(
    "strafe: side step open (feet wide), guard held", "locomotion",
    t=dict(lean=8, twist=-4), hips=(0.0, -0.13, 0.0),
    legs={"R": foot(-0.28, -0.14), "L": foot(0.22, 0.18, heel=15, yaw=15)},
    ctrl=blade((-0.03, -0.38, 0.98), elev(26)), left="grip"))
_add("strafe_cross", duo(
    "strafe: feet drawn together mid-step, guard held", "locomotion",
    t=dict(lean=8, twist=-4), hips=(0.0, -0.10, 0.0),
    legs={"R": foot(-0.08, -0.16), "L": foot(0.02, 0.20, heel=22, yaw=15)},
    ctrl=blade((-0.03, -0.38, 0.99), elev(26)), left="grip"))

# ---------------------------------------------------------------------------------------------- spear (SAINT)
SP = dict(chars=["SAINT"], weapon="spear", left="grip", hide=["SAINT_hat"])     # Act II: the hat is already cut
_add("spear_high", pose(
    "spear high guard: right fist by the right hip-chest, shaft angled down-forward at the face", "spear",
    body=torso(lean=6, twist=-22), hips=(0.0, -0.08, 0.0),
    legs=stance(front=0.34, back=0.32, width=0.28, lead="L", yaw_back=-25, heel_back=15),
    ctrl=blade((-0.20, 0.02, 1.36), elev(-8, yaw=8)), spear_grip=(0.35, 0.95), **SP))
_add("spear_low", pose(
    "spear low guard: shaft low, blade at the knees, weight settled", "spear",
    body=torso(lean=10, twist=-22), hips=(0.0, -0.12, 0.0),
    legs=stance(front=0.36, back=0.34, width=0.28, lead="L", yaw_back=-25, heel_back=15),
    ctrl=blade((-0.22, 0.02, 1.00), elev(-16, yaw=6)), spear_grip=(0.35, 0.95), **SP))
_add("spear_sweep_windup", pose(
    "360 sweep windup: spear wound back to the right, trunk turned far right, weight back", "spear",
    body=torso(lean=10, twist=-58), hips=(0.0, -0.12, -0.02),
    legs=stance(front=0.30, back=0.34, width=0.36, lead="L", yaw_back=-30, heel_back=10),
    ctrl=blade((-0.22, 0.02, 1.06), _n(-0.90, 0.35, 0.10)), spear_grip=(0.30, 0.55), **SP))
_add("spear_sweep_strike", pose(
    "360 sweep: the shaft passing in front at hip-chest height, trunk unwinding", "spear",
    body=torso(lean=12, twist=-6), hips=(0.0, -0.16, 0.02),
    legs=stance(front=0.34, back=0.34, width=0.40, lead="L", yaw_back=-20, heel_back=20),
    ctrl=blade((-0.12, -0.28, 1.05), _n(0.40, -0.92, -0.02)), spear_grip=(0.30, 0.90), **SP))
_add("spear_sweep_follow", pose(
    "360 sweep follow-through: spear carried round to the left, trunk turned far left", "spear",
    body=torso(lean=12, twist=52), hips=(0.0, -0.16, 0.02),
    legs=stance(front=0.34, back=0.34, width=0.40, lead="L", yaw_back=-10, heel_back=24),
    ctrl=blade((0.18, -0.12, 1.02), _n(0.88, 0.46, -0.05)), spear_grip=(0.30, 0.90), **SP))
_add("spear_thrust_windup", pose(
    "spear thrust windup: rear fist drawn back to the right hip, point level at the target, weight back", "spear",
    body=torso(lean=6, twist=-28), hips=(0.0, -0.12, -0.04),
    legs=stance(front=0.30, back=0.36, width=0.28, lead="L", yaw_back=-25, heel_back=8),
    ctrl=blade((-0.24, 0.26, 1.06), elev(4, yaw=4)), spear_grip=(0.35, 0.95), **SP))
_add("spear_thrust_extend", pose(
    "spear thrust: the shaft driven through the front hand, deep lunge, trunk square", "spear",
    body=torso(lean=16, twist=-4), hips=(0.0, -0.20, 0.05),
    legs=stance(front=0.56, back=0.42, width=0.28, lead="L", yaw_back=-20, heel_back=34),
    ctrl=blade((-0.10, -0.52, 1.10), elev(2)), spear_grip=(0.35, 0.62), **SP))
_add("spear_slam_windup", pose(
    "overhead slam windup: spear raised high overhead, back arched, rising on the toes", "spear",
    body=torso(lean=-10, look_pitch=-8), hips=(0.0, -0.04, -0.03),
    legs=stance(front=0.26, back=0.30, width=0.30, lead="L", heel_back=20),
    ctrl=blade((-0.12, -0.10, 1.80), _n(0.0, 0.25, 0.97)), spear_grip=(0.35, 0.62), **SP))
_add("spear_slam", pose(
    "overhead slam: spear driven into the ground far in front, deep lunge, trunk folded over it", "spear",
    body=torso(lean=30, look_pitch=-10), hips=(0.0, -0.26, 0.05),
    legs=stance(front=0.56, back=0.44, width=0.30, lead="L", heel_back=38),
    ctrl=blade((-0.08, -0.42, 1.02), _n(0.0, -0.83, -0.55)), spear_grip=(0.35, 0.95), **SP))
_add("spear_butt_windup", pose(
    "butt slam windup: spear vertical in both hands, lifted, butt 0.45 m off the ground", "spear",
    body=torso(lean=0, twist=-10), hips=(0.0, -0.04, 0.0), legs=stance(front=0.18, back=0.22, width=0.34, heel_back=5),
    ctrl=blade((-0.24, -0.22, 1.58), (0.0, 0.0, 1.0), edge=(0.0, -1.0, 0.0)), spear_grip=(1.12, 1.46), **SP))
_add("spear_butt_slam", pose(
    "butt slam: spear driven straight down, the butt striking the ground by the right foot", "spear",
    body=torso(lean=10, twist=-10), hips=(0.0, -0.14, 0.0), legs=stance(front=0.20, back=0.24, width=0.38, heel_back=8),
    ctrl=blade((-0.24, -0.22, 1.13), (0.0, 0.0, 1.0), edge=(0.0, -1.0, 0.0)), spear_grip=(1.12, 1.46), **SP))
_add("spear_throw_windup", pose(
    "javelin windup: spear cocked above the right shoulder at its balance, left arm aiming, weight back", "spear",
    body=merge(torso(lean=-6, twist=-44), arm("L", flex=80, abd=10, elbow=10)), hips=(0.0, -0.10, -0.05),
    legs=stance(front=0.40, back=0.40, width=0.30, lead="L", yaw_back=-35, heel_back=5),
    ctrl=blade((-0.34, 0.28, 1.58), elev(14)), spear_grip=(1.20, 1.55), chars=["SAINT"], weapon="spear",
    left="free", hide=["SAINT_hat"]))
_add("spear_throw_release", pose(
    "javelin release: throwing arm extended high forward, trunk whipped round, weight on the front foot", "spear",
    body=merge(torso(lean=16, twist=18), arm("L", flex=-20, abd=20, elbow=60)), hips=(0.0, -0.14, 0.05),
    legs=stance(front=0.50, back=0.40, width=0.30, lead="L", yaw_back=-20, heel_back=38),
    ctrl=blade((-0.12, -0.56, 1.62), elev(6)), spear_grip=(1.20, 1.55), chars=["SAINT"], weapon="spear",
    left="free", hide=["SAINT_hat"]))
_add("spear_draw_reach", pose(
    "spear draw 1/2: right hand reaching back over the right shoulder to the slung shaft", "spear",
    body=merge(torso(lean=4, twist=-12, side=-4), arm("L", flex=15, abd=-30, elbow=70)), hips=(0.0, -0.06, 0.0),
    legs=stance(front=0.24, back=0.26, width=0.34, lead="L", heel_back=6),
    ctrl={"slung": 1.45}, spear_grip=(1.45, 1.45), chars=["SAINT"], weapon="spear", left="free",
    elbow={"R": "auto"}))
_add("spear_draw_arc", pose(
    "spear draw 2/2: spear pulled up over the shoulder in one arc, head of the spear swinging forward", "spear",
    body=merge(torso(lean=-4, twist=-6), arm("L", flex=40, abd=10, elbow=40)), hips=(0.0, -0.08, 0.0),
    legs=stance(front=0.26, back=0.28, width=0.34, lead="L", heel_back=10),
    ctrl=blade((-0.22, -0.10, 1.92), _n(0.25, -0.55, 0.80)), spear_grip=(1.45, 1.45), chars=["SAINT"],
    weapon="spear", left="free"))
_add("spear_spin", pose(
    "spear twirl: held at its middle in front of the chest, shaft horizontal", "spear",
    body=merge(torso(lean=6, twist=-6), arm("L", flex=30, abd=10, elbow=40)), hips=(0.0, -0.10, 0.0),
    legs=stance(front=0.26, back=0.28, width=0.34, lead="L", heel_back=10),
    ctrl=blade((-0.10, -0.42, 1.24), (1.0, 0.0, 0.0), edge=(0.0, 0.0, -1.0)), spear_grip=(1.15, 1.45),
    chars=["SAINT"], weapon="spear", left="free"))

# ---------------------------------------------------------------------------------------------- kunai (SHINOBI)
KN = dict(chars=["SHINOBI"], left="free")
_add("kunai_throw_windup", pose(
    "kunai throw windup: left hand cocked beside the ear, left shoulder back, katana low in the right hand", "kunai",
    body=merge(torso(lean=-2, twist=30), arm("L", flex=125, abd=25, rot=-10, elbow=115, wflex=-30)),
    hips=(0.0, -0.10, -0.03), legs=stance(front=0.30, back=0.32, width=0.28, heel_back=10),
    ctrl=blade((-0.22, -0.30, 0.90), elev(-22, yaw=-10)), **KN))
_add("kunai_throw_release", pose(
    "kunai release: left arm whipped forward and extended, trunk turned through, weight forward", "kunai",
    body=merge(torso(lean=12, twist=-22), arm("L", flex=88, abd=2, elbow=4, wflex=20)),
    hips=(0.0, -0.14, 0.04), legs=stance(front=0.38, back=0.34, width=0.28, heel_back=25),
    ctrl=blade((-0.26, -0.20, 0.90), elev(-24, yaw=-20)), **KN))
_add("kunai_parry", pose(
    "off-hand kunai parry: left forearm up in front with the kunai turning the shaft aside, katana low right, "
    "sliding in", "kunai",
    body=merge(torso(lean=14, twist=20), arm("L", flex=72, abd=12, rot=18, elbow=78, wflex=-10)),
    hips=(0.0, -0.18, 0.03), legs=stance(front=0.40, back=0.34, width=0.28, heel_back=28),
    ctrl=blade((-0.26, -0.20, 0.94), elev(-16, yaw=-22)), **KN))


# ---------------------------------------------------------------------------------------------- scabbard settings
# (pull, roll, turn, tilt) of the saya per draw / sheathe / iai pose, measured with out/dev/moves/probe_saya.py (least
# wrist strain on both rigs).  The frames with the kissaki AT the koiguchi (iai_draw_2, draw_clear, sheathe_quick_1,
# sheathe_slow_1) stay above the 75 deg wrist QA limit on the RIGHT wrist (~85-100 deg: the arm is fully extended
# while the blade still lies along the saya) - they last 1-2 frames in a draw and happen under the hand in S24b.
SAYA_SETTINGS = {
    "iai_crouch": (0.0, 75.0, 0.0, 10.0), "iai_draw_1": (0.06, 75.0, 15.0, 10.0), "iai_draw_2": (0.11, 60.0, 45.0, 0.0),
    "draw_grab": (0.0, 75.0, 0.0, 10.0), "draw_pull": (0.08, 60.0, 30.0, 10.0), "draw_clear": (0.11, 45.0, 45.0, -10.0),
    "sheathe_quick_1": (0.06, 45.0, 45.0, -20.0), "sheathe_quick_2": (0.03, 75.0, 30.0, 10.0),
    "sheathe_done": (0.0, 75.0, 0.0, 10.0), "sheathe_slow_1": (0.05, 45.0, 45.0, -20.0),
    "sheathe_slow_2": (0.03, 75.0, 30.0, 10.0), "listen": (0.0, 75.0, 0.0, 10.0),
}
for _n, _v in SAYA_SETTINGS.items():
    POSES[_n]["saya"] = _v
    for _ov in (POSES[_n].get("per_char") or {}).values():
        _ov.pop("saya", None)


# >>> TUNED (generated by out/dev/moves/tune.py - do not edit by hand; re-run the tool after re-authoring)
TUNED = {
    'blade_lock': dict(src='grip:-0.020,-0.300,1.300;dir:0.100,-0.251,0.963;edge:0.206,-0.979,0.000', ctrl={'grip': [-0.02, -0.34, 1.33], 'dir': [0.1003, -0.2507, 0.9628], 'edge': [-0.0733, -0.967, -0.2442]}),
    'blade_lock_push': dict(src='grip:-0.020,-0.360,1.260;dir:0.100,-0.321,0.942;edge:0.208,-0.978,0.000', ctrl={'grip': [-0.04, -0.37, 1.28], 'dir': [0.0753, -0.2411, 0.9676], 'edge': [-0.0669, -0.9694, -0.2363]}),
    'chudan': dict(src='grip:-0.030,-0.380,0.980;dir:0.000,-0.891,0.454', ctrl={'grip': [-0.03, -0.38, 0.98], 'dir': [0.0, -0.891, 0.454], 'edge': [0.0, -0.454, -0.891]}),
    'chudan@SAINT': dict(src='grip:-0.030,-0.370,1.000;dir:0.000,-0.914,0.407', ctrl={'grip': [-0.03, -0.37, 1.0], 'dir': [0.0, -0.9135, 0.4067], 'edge': [-0.1951, -0.3989, -0.896]}),
    'chudan_1h': dict(src='grip:-0.140,-0.400,1.020;dir:0.066,-0.937,0.342', ctrl={'grip': [-0.14, -0.4, 1.02], 'dir': [0.0655, -0.9374, 0.342], 'edge': [0.0239, -0.3412, -0.9397]}),
    'crouch_hide': dict(src='grip:-0.050,-0.360,0.420;dir:0.000,-0.996,-0.087', ctrl={'grip': [-0.05, -0.36, 0.42], 'dir': [0.0, -0.9962, -0.0872], 'edge': [-0.0654, 0.087, -0.9941]}),
    'dash': dict(src='grip:-0.160,-0.100,0.800;dir:-0.339,0.813,-0.474', ctrl={'grip': [-0.2, 0.0, 0.68], 'dir': [-0.4777, 0.8071, -0.3469], 'edge': [0.1767, -0.2986, -0.9379]}),
    'deflect_high': dict(src='grip:-0.020,-0.300,1.620;dir:-0.952,-0.120,0.281;edge:0.000,0.000,1.000', ctrl={'grip': [-0.02, -0.3, 1.62], 'dir': [-0.9522, -0.1203, 0.2807], 'edge': [0.3014, -0.2228, 0.9271]}),
    'deflect_high@SAINT': dict(src='grip:-0.020,-0.420,1.580;dir:-0.952,-0.120,0.281;edge:0.000,0.000,1.000', ctrl={'grip': [-0.02, -0.42, 1.58], 'dir': [-0.9522, -0.1203, 0.2807], 'edge': [0.2972, -0.5761, 0.7615]}),
    'deflect_low': dict(src='grip:-0.120,-0.340,1.060;dir:-0.299,-0.349,-0.888;edge:-0.862,-0.406,0.304', ctrl={'grip': [0.0, -0.24, 1.18], 'dir': [-0.345, -0.3041, -0.888], 'edge': [0.2878, -0.9348, 0.2084]}),
    'deflect_mid_L': dict(src='grip:0.060,-0.360,1.040;dir:0.399,-0.299,0.867;edge:0.855,-0.453,-0.252', ctrl={'grip': [0.18, -0.42, 1.16], 'dir': [0.4352, -0.4332, 0.7892], 'edge': [-0.2535, -0.9001, -0.3543]}),
    'deflect_mid_R': dict(src='grip:-0.140,-0.360,1.040;dir:-0.399,-0.299,0.867;edge:-0.855,-0.453,-0.252', ctrl={'grip': [-0.16, -0.36, 1.09], 'dir': [-0.4576, -0.3432, 0.8203], 'edge': [-0.3975, -0.7463, -0.5339]}),
    'deflect_overhead_block': dict(src='grip:0.020,-0.300,1.600;dir:-0.853,-0.201,-0.482;edge:-0.406,0.000,0.914', ctrl={'grip': [0.02, -0.27, 1.56], 'dir': [-0.8461, -0.3289, -0.4194], 'edge': [0.0692, -0.8481, 0.5254]}),
    'diag_down_L_follow': dict(src='grip:-0.180,-0.300,0.840;dir:-0.450,-0.300,-0.841;edge:-0.883,0.331,0.331', ctrl={'grip': [-0.3, -0.18, 0.72], 'dir': [-0.4877, -0.4344, -0.7573], 'edge': [-0.2207, 0.9006, -0.3744]}),
    'diag_down_L_strike': dict(src='grip:0.000,-0.480,1.120;dir:0.301,-0.912,-0.280;edge:-0.390,-0.380,-0.839', ctrl={'grip': [-0.1, -0.58, 1.0], 'dir': [0.3059, -0.928, -0.2129], 'edge': [-0.8797, -0.19, -0.4359]}),
    'diag_down_L_windup': dict(src='grip:0.100,-0.120,1.500;dir:0.321,0.502,0.803;edge:0.000,-0.800,0.600', ctrl={'grip': [0.16, -0.12, 1.52], 'dir': [0.3212, 0.5019, 0.8031], 'edge': [0.4509, -0.8268, 0.3364]}),
    'diag_down_R_follow': dict(src='grip:0.120,-0.300,0.840;dir:0.450,-0.300,-0.841;edge:0.883,0.331,0.331', ctrl={'grip': [0.0, -0.18, 0.72], 'dir': [0.4877, -0.4344, -0.7573], 'edge': [-0.7854, 0.1605, -0.5979]}),
    'diag_down_R_strike': dict(src='grip:-0.060,-0.480,1.120;dir:-0.301,-0.912,-0.280;edge:0.390,-0.380,-0.839', ctrl={'grip': [0.06, -0.6, 1.0], 'dir': [-0.3098, -0.9398, -0.1442], 'edge': [-0.1451, 0.1966, -0.9697]}),
    'diag_down_R_windup': dict(src='grip:-0.220,-0.060,1.500;dir:-0.300,0.520,0.800;edge:0.000,-0.800,0.600', ctrl={'grip': [-0.2, -0.08, 1.48], 'dir': [-0.2999, 0.5199, 0.7998], 'edge': [-0.5139, -0.7944, 0.3237]}),
    'dodge_back': dict(src='grip:-0.030,-0.340,1.000;dir:0.000,-0.914,0.407', ctrl={'grip': [-0.03, -0.34, 1.0], 'dir': [0.0, -0.9135, 0.4067], 'edge': [0.0, -0.4067, -0.9135]}),
    'dodge_side': dict(src='grip:0.080,-0.360,0.960;dir:0.000,-0.927,0.375', ctrl={'grip': [0.08, -0.36, 0.96], 'dir': [0.0, -0.9272, 0.3746], 'edge': [-0.2588, -0.3618, -0.8956]}),
    'draw_swing': dict(src='grip:-0.100,-0.340,1.120;dir:-0.123,-0.696,0.707', ctrl={'grip': [-0.1, -0.34, 1.12], 'dir': [-0.1228, -0.6964, 0.7071], 'edge': [-0.1228, -0.6964, -0.7071]}),
    'duck': dict(src='grip:-0.030,-0.340,0.600;dir:0.000,-0.940,0.342', ctrl={'grip': [0.02, -0.41, 0.65], 'dir': [0.0, -0.9613, 0.2756], 'edge': [-0.1951, -0.2703, -0.9428]}),
    'gedan': dict(src='grip:-0.090,-0.420,0.840;dir:0.000,-0.809,-0.588;roll:-30.00', ctrl={'grip': [-0.09, -0.43, 0.83], 'dir': [0.0, -0.809, -0.5878], 'edge': [-0.6088, 0.4663, -0.6418]}),
    'hasso': dict(src='grip:-0.140,-0.200,1.360;dir:0.060,0.400,0.910;edge:0.000,-0.910,0.400;roll:-30.00', ctrl={'grip': [-0.12, -0.21, 1.38], 'dir': [0.0603, 0.4017, 0.9138], 'edge': [-0.4991, -0.7807, 0.3761]}),
    'horizontal_L_follow': dict(src='grip:-0.360,-0.300,1.100;dir:-0.923,-0.381,-0.050;edge:-0.382,0.924,0.000', ctrl={'grip': [-0.43, -0.36, 0.98], 'dir': [-0.9238, -0.3816, -0.0327], 'edge': [0.2913, -0.6447, -0.7067]}),
    'horizontal_L_strike': dict(src='grip:-0.020,-0.520,1.140;dir:-0.120,-0.992,0.040;edge:-0.993,0.120,0.000', ctrl={'grip': [-0.01, -0.6, 1.04], 'dir': [-0.1202, -0.9919, 0.0401], 'edge': [-0.2616, -0.0073, -0.9651]}),
    'horizontal_L_windup': dict(src='grip:0.100,-0.300,1.100;dir:0.852,-0.501,0.150;edge:0.503,0.865,0.000', ctrl={'grip': [0.14, -0.38, 1.1], 'dir': [0.8521, -0.5013, 0.1504], 'edge': [-0.374, -0.7843, -0.495]}),
    'horizontal_R_follow': dict(src='grip:0.300,-0.340,1.100;dir:0.923,-0.381,-0.050;edge:0.382,0.924,0.000', ctrl={'grip': [0.33, -0.34, 1.0], 'dir': [0.9231, -0.3813, -0.0502], 'edge': [-0.3027, -0.64, -0.7062]}),
    'horizontal_R_strike': dict(src='grip:-0.060,-0.520,1.140;dir:0.120,-0.992,0.040;edge:0.993,0.120,0.000', ctrl={'grip': [-0.07, -0.58, 1.1], 'dir': [0.1202, -0.9919, 0.0401], 'edge': [-0.7847, -0.1197, -0.6083]}),
    'horizontal_R_windup': dict(src='grip:-0.320,-0.100,1.180;dir:-0.852,0.501,0.150;edge:-0.503,-0.865,0.000', ctrl={'grip': [-0.32, -0.1, 1.18], 'dir': [-0.8521, 0.5013, 0.1504], 'edge': [-0.5181, -0.7675, -0.3776]}),
    'iai_cut': dict(src='grip:-0.100,-0.600,1.160;dir:-0.301,-0.953,0.030;edge:-0.954,0.301,0.000', ctrl={'grip': [-0.09, -0.6, 1.15], 'dir': [-0.301, -0.9532, 0.0301], 'edge': [0.751, -0.2564, -0.6085]}),
    'iai_follow': dict(src='grip:-0.460,-0.360,1.220;dir:-0.921,-0.381,0.080;edge:-0.382,0.924,0.000', ctrl={'grip': [-0.46, -0.43, 1.16], 'dir': [-0.9213, -0.3805, 0.0801], 'edge': [0.2578, -0.7519, -0.6068]}),
    'jodan': dict(src='grip:-0.030,-0.240,1.760;dir:0.000,0.620,0.780;edge:0.000,-0.780,0.620', ctrl={'grip': [-0.03, -0.24, 1.76], 'dir': [0.0, 0.6222, 0.7828], 'edge': [0.0, -0.7828, 0.6222]}),
    'jodan@SAINT': dict(src='grip:-0.030,-0.340,1.740;dir:0.000,0.550,0.830;edge:0.000,-0.830,0.550', ctrl={'grip': [0.07, -0.3, 1.74], 'dir': [-0.0686, 0.4881, 0.8701], 'edge': [-0.7119, -0.6349, 0.3001]}),
    'jodan_sky': dict(src='grip:-0.030,-0.240,1.760;dir:0.000,0.620,0.780;edge:0.000,-0.780,0.620', ctrl={'grip': [-0.03, -0.24, 1.76], 'dir': [0.0, 0.6222, 0.7828], 'edge': [0.0, -0.7828, 0.6222]}),
    'jodan_sky@SAINT': dict(src='grip:-0.030,-0.340,1.740;dir:0.000,0.550,0.830;edge:0.000,-0.830,0.550', ctrl={'grip': [0.07, -0.3, 1.74], 'dir': [-0.0686, 0.4881, 0.8701], 'edge': [-0.7119, -0.6349, 0.3001]}),
    'jump_air': dict(src='grip:-0.030,-0.300,1.400;dir:0.000,-0.766,0.643', ctrl={'grip': [0.0, -0.31, 1.34], 'dir': [0.0, -0.766, 0.6428], 'edge': [-0.1951, -0.6304, -0.7513]}),
    'jump_crouch': dict(src='grip:-0.100,-0.260,0.700;dir:0.000,-0.940,-0.342', ctrl={'grip': [-0.1, -0.26, 0.7], 'dir': [0.0, -0.9397, -0.342], 'edge': [-0.3827, 0.316, -0.8682]}),
    'jump_land': dict(src='grip:-0.030,-0.400,0.720;dir:0.000,-0.985,-0.174', ctrl={'grip': [-0.02, -0.39, 0.67], 'dir': [0.0, -0.9848, -0.1736], 'edge': [-0.1305, 0.1722, -0.9764]}),
    'kick_chamber': dict(src='grip:-0.030,-0.300,1.060;dir:0.000,-0.819,0.574', ctrl={'grip': [-0.03, -0.3, 1.06], 'dir': [0.0, -0.8192, 0.5736], 'edge': [-0.5, -0.4967, -0.7094]}),
    'kick_extend': dict(src='grip:-0.030,-0.260,1.100;dir:0.000,-0.707,0.707', ctrl={'grip': [-0.03, -0.27, 1.12], 'dir': [0.0, -0.7071, 0.7071], 'edge': [-0.5556, -0.5879, -0.5879]}),
    'kneel_planted': dict(src='grip:-0.030,-0.450,0.660;dir:0.000,-0.150,-1.000;edge:0.000,-1.000,0.000', ctrl={'grip': [-0.03, -0.45, 0.66], 'dir': [0.0, -0.1483, -0.9889], 'edge': [-0.1305, -0.9805, 0.1471]}),
    'kneel_sword_planted': dict(src='grip:-0.030,-0.450,0.660;dir:0.000,-0.150,-1.000;edge:0.000,-1.000,0.000', ctrl={'grip': [-0.03, -0.45, 0.66], 'dir': [0.0, -0.1483, -0.9889], 'edge': [-0.1305, -0.9805, 0.1471]}),
    'kunai_parry': dict(src='grip:-0.260,-0.200,0.940;dir:-0.360,-0.891,-0.276', ctrl={'grip': [-0.26, -0.2, 0.94], 'dir': [-0.3601, -0.8913, -0.2756], 'edge': [0.1033, 0.2556, -0.9613]}),
    'kunai_throw_release': dict(src='grip:-0.260,-0.200,0.900;dir:-0.312,-0.858,-0.407', ctrl={'grip': [-0.26, -0.2, 0.9], 'dir': [-0.3125, -0.8585, -0.4067], 'edge': [0.1391, 0.3822, -0.9135]}),
    'kunai_throw_windup': dict(src='grip:-0.220,-0.300,0.900;dir:-0.161,-0.913,-0.375', ctrl={'grip': [-0.22, -0.3, 0.9], 'dir': [-0.161, -0.9131, -0.3746], 'edge': [0.065, 0.3689, -0.9272]}),
    'low_1h': dict(src='grip:-0.160,-0.240,0.920;dir:0.095,-0.901,-0.423', ctrl={'grip': [-0.16, -0.24, 0.92], 'dir': [0.0947, -0.9013, -0.4226], 'edge': [-0.0442, 0.4203, -0.9063]}),
    'overhead_follow': dict(src='grip:-0.030,-0.440,0.900;dir:0.000,-0.766,-0.643', ctrl={'grip': [-0.15, -0.32, 0.78], 'dir': [0.0, -0.848, -0.5299], 'edge': [-0.7934, 0.3226, -0.5163]}),
    'overhead_strike': dict(src='grip:-0.030,-0.560,1.260;dir:0.000,-0.995,-0.105', ctrl={'grip': [-0.11, -0.68, 1.14], 'dir': [0.1045, -0.9939, 0.0349], 'edge': [-0.8595, -0.1079, -0.4997]}),
    'overhead_windup': dict(src='grip:-0.030,-0.120,1.790;dir:0.000,0.783,0.622;edge:0.000,-0.622,0.783', ctrl={'grip': [-0.03, -0.12, 1.79], 'dir': [0.0, 0.7828, 0.6222], 'edge': [0.0, -0.6222, 0.7828]}),
    'overhead_windup@SAINT': dict(src='grip:-0.030,-0.540,1.700;dir:0.000,0.622,0.783;edge:0.000,-0.783,0.622', ctrl={'grip': [0.05, -0.42, 1.62], 'dir': [0.0, 0.5072, 0.8618], 'edge': [-0.0654, -0.86, 0.5062]}),
    'perfect_deflect': dict(src='grip:-0.100,-0.440,1.120;dir:-0.500,-0.550,0.670;edge:-0.722,-0.619,-0.309', ctrl={'grip': [-0.1, -0.44, 1.12], 'dir': [-0.4997, -0.5496, 0.6695], 'edge': [-0.405, -0.5351, -0.7414]}),
    'plunge_land': dict(src='grip:-0.030,-0.460,0.780;dir:0.000,-0.743,-0.669', ctrl={'grip': [0.03, -0.34, 0.66], 'dir': [0.0, -0.829, -0.5592], 'edge': [-0.5556, 0.465, -0.6893]}),
    'plunge_strike': dict(src='grip:-0.030,-0.600,1.280;dir:0.000,-0.951,-0.309', ctrl={'grip': [-0.11, -0.68, 1.16], 'dir': [0.0498, -0.9498, -0.309], 'edge': [-0.8729, 0.109, -0.4755]}),
    'plunge_windup': dict(src='grip:-0.030,-0.100,1.860;dir:0.000,0.821,0.571;edge:0.000,-0.571,0.821', ctrl={'grip': [-0.03, -0.1, 1.86], 'dir': [0.0512, 0.7319, 0.6795], 'edge': [-0.0474, -0.6778, 0.7337]}),
    'rise_kneel': dict(src='grip:-0.030,-0.400,0.800;dir:0.000,-0.643,-0.766', ctrl={'grip': [0.0, -0.28, 0.68], 'dir': [0.0, -0.7431, -0.6691], 'edge': [-0.7071, 0.4731, -0.5255]}),
    'rising_L_follow': dict(src='grip:-0.220,-0.300,1.480;dir:-0.499,-0.419,0.758;edge:-0.619,0.309,0.722', ctrl={'grip': [-0.25, -0.36, 1.4], 'dir': [-0.499, -0.4192, 0.7585], 'edge': [-0.0681, -0.8536, -0.5165]}),
    'rising_L_strike': dict(src='grip:-0.040,-0.460,1.100;dir:-0.250,-0.899,0.360;edge:-0.501,-0.200,0.842', ctrl={'grip': [-0.04, -0.47, 1.07], 'dir': [-0.2497, -0.8991, 0.3596], 'edge': [-0.0503, -0.3588, -0.932]}),
    'rising_L_windup': dict(src='grip:0.020,-0.340,0.860;dir:0.350,-0.600,-0.720;edge:0.651,0.651,0.391', ctrl={'grip': [-0.08, -0.42, 0.78], 'dir': [0.3743, -0.6416, -0.6695], 'edge': [-0.653, 0.3303, -0.6816]}),
    'rising_R_follow': dict(src='grip:0.140,-0.300,1.480;dir:0.499,-0.419,0.758;edge:0.619,0.309,0.722', ctrl={'grip': [0.13, -0.3, 1.48], 'dir': [0.442, -0.3098, 0.8418], 'edge': [0.1386, -0.9036, -0.4054]}),
    'rising_R_strike': dict(src='grip:-0.020,-0.460,1.100;dir:0.250,-0.899,0.360;edge:0.501,-0.200,0.842', ctrl={'grip': [-0.02, -0.47, 1.07], 'dir': [0.2497, -0.8991, 0.3596], 'edge': [-0.5488, -0.4374, -0.7124]}),
    'rising_R_windup': dict(src='grip:-0.200,-0.140,0.880;dir:-0.451,0.621,-0.641;edge:-0.206,0.309,-0.928', ctrl={'grip': [-0.32, -0.26, 0.88], 'dir': [-0.5789, 0.6213, -0.5281], 'edge': [-0.2386, -0.7483, -0.6189]}),
    'roll_rise': dict(src='grip:-0.080,-0.400,0.720;dir:0.000,-0.966,0.259', ctrl={'grip': [-0.08, -0.4, 0.72], 'dir': [0.0, -0.9816, 0.1908], 'edge': [-0.2588, -0.1843, -0.9482]}),
    'roll_tuck': dict(src='grip:-0.120,-0.220,0.720;dir:0.251,0.902,0.351', ctrl={'grip': [-0.24, -0.22, 0.61], 'dir': [0.2506, 0.9023, 0.3509], 'edge': [0.0939, 0.3381, -0.9364]}),
    'sheathe_slow_chiburi': dict(src='grip:-0.440,-0.320,0.960;dir:-0.551,-0.721,-0.421', ctrl={'grip': [-0.44, -0.32, 0.96], 'dir': [-0.5507, -0.721, -0.4206], 'edge': [0.2553, 0.3342, -0.9073]}),
    'skid': dict(src='grip:-0.240,-0.360,0.620;dir:-0.100,-0.550,-0.829', ctrl={'grip': [-0.25, -0.24, 0.6], 'dir': [-0.11, -0.6052, -0.7884], 'edge': [0.5068, 0.6482, -0.5683]}),
    'slide_cut': dict(src='grip:-0.180,-0.440,0.520;dir:0.352,-0.935,0.050;edge:0.936,0.352,0.000', ctrl={'grip': [-0.18, -0.4, 0.6], 'dir': [0.3518, -0.9347, 0.0503], 'edge': [-0.1046, -0.0926, -0.9902]}),
    'spear_butt_slam': dict(src='grip:-0.240,-0.220,1.130;dir:0.000,0.000,1.000;edge:0.000,-1.000,0.000', ctrl={'grip': (-0.24, -0.22, 1.13), 'dir': (0.0, 0.0, 1.0), 'edge': (0.0, -1.0, 0.0)}),
    'spear_butt_windup': dict(src='grip:-0.240,-0.220,1.580;dir:0.000,0.000,1.000;edge:0.000,-1.000,0.000', ctrl={'grip': (-0.2, -0.18, 1.5), 'dir': (0.0, 0.0698, 0.9976), 'edge': (0.2588, -0.9636, 0.0674)}),
    'spear_draw_arc': dict(src='grip:-0.220,-0.100,1.920;dir:0.249,-0.549,0.798', ctrl={'grip': (-0.22, -0.1, 1.92), 'dir': (0.2494, -0.5486, 0.798), 'edge': (-0.9625, -0.0498, 0.2665)}),
    'spear_high': dict(src='grip:-0.200,0.020,1.360;dir:0.138,-0.981,-0.139', ctrl={'grip': (-0.3, 0.01, 1.41), 'dir': (0.1391, -0.9897, -0.0349), 'edge': (-0.9167, -0.1154, -0.3825)}),
    'spear_low': dict(src='grip:-0.220,0.020,1.000;dir:0.100,-0.956,-0.276', ctrl={'grip': (-0.22, 0.02, 1.0), 'dir': (0.1669, -0.9467, -0.2756), 'edge': (0.0166, 0.2822, -0.9592)}),
    'spear_slam': dict(src='grip:-0.080,-0.420,1.020;dir:0.000,-0.834,-0.552', ctrl={'grip': (0.04, -0.3, 1.14), 'dir': (0.0, -0.8947, -0.4467), 'edge': (0.9979, -0.0292, 0.0585)}),
    'spear_slam_windup': dict(src='grip:-0.120,-0.100,1.800;dir:0.000,0.250,0.968', ctrl={'grip': (0.0, -0.1, 1.72), 'dir': (0.0532, 0.3782, 0.9242), 'edge': (0.7519, -0.6242, 0.2122)}),
    'spear_spin': dict(src='grip:-0.100,-0.420,1.240;dir:1.000,0.000,0.000;edge:0.000,0.000,-1.000', ctrl={'grip': (-0.1, -0.42, 1.24), 'dir': (1.0, 0.0, 0.0), 'edge': (0.0, -0.1951, -0.9808)}),
    'spear_sweep_follow': dict(src='grip:0.180,-0.120,1.020;dir:0.885,0.463,-0.050', ctrl={'grip': (0.18, -0.12, 1.02), 'dir': (0.8851, 0.4627, -0.0503), 'edge': (-0.339, 0.5668, -0.7509)}),
    'spear_sweep_strike': dict(src='grip:-0.120,-0.280,1.050;dir:0.399,-0.917,-0.020', ctrl={'grip': (-0.12, -0.24, 1.05), 'dir': (0.3982, -0.9159, 0.0499), 'edge': (0.1984, 0.0329, -0.9796)}),
    'spear_sweep_windup': dict(src='grip:-0.220,0.020,1.060;dir:-0.927,0.361,0.103', ctrl={'grip': (-0.22, 0.02, 1.06), 'dir': (-0.927, 0.3605, 0.103), 'edge': (-0.2464, -0.3787, -0.8921)}),
    'spear_throw_release': dict(src='grip:-0.120,-0.560,1.620;dir:0.000,-0.995,0.105', ctrl={'grip': (-0.12, -0.56, 1.62), 'dir': (0.0, -0.9945, 0.1045), 'edge': (-0.8969, 0.0462, 0.4399)}),
    'spear_throw_windup': dict(src='grip:-0.340,0.280,1.580;dir:0.000,-0.970,0.242', ctrl={'grip': (-0.34, 0.28, 1.58), 'dir': (0.0, -0.9703, 0.2419), 'edge': (-0.9979, -0.0158, -0.0635)}),
    'spear_thrust_extend': dict(src='grip:-0.100,-0.520,1.100;dir:0.000,-0.999,0.035', ctrl={'grip': (-0.06, -0.52, 1.09), 'dir': (0.0694, -0.9921, 0.1045), 'edge': (0.7548, -0.0163, -0.6557)}),
    'spear_thrust_windup': dict(src='grip:-0.240,0.260,1.060;dir:0.070,-0.995,0.070', ctrl={'grip': (-0.25, 0.23, 1.05), 'dir': (0.0696, -0.9951, 0.0698), 'edge': (0.0049, -0.0696, -0.9976)}),
    'stagger_back': dict(src='grip:-0.260,0.040,1.420;dir:-0.300,0.601,0.741', ctrl={'grip': [-0.3, 0.0, 1.42], 'dir': [-0.3061, 0.6122, 0.7291], 'edge': [0.326, -0.6521, 0.6845]}),
    'strafe_cross': dict(src='grip:-0.030,-0.380,0.990;dir:0.000,-0.899,0.438', ctrl={'grip': [-0.03, -0.38, 0.99], 'dir': [0.0, -0.8988, 0.4384], 'edge': [-0.2588, -0.4234, -0.8682]}),
    'strafe_open': dict(src='grip:-0.030,-0.380,0.980;dir:0.000,-0.899,0.438', ctrl={'grip': [-0.03, -0.38, 0.98], 'dir': [0.0, -0.8988, 0.4384], 'edge': [-0.2588, -0.4234, -0.8682]}),
    'thrust_follow': dict(src='grip:-0.050,-0.720,1.100;dir:0.000,-1.000,0.017', ctrl={'grip': [-0.03, -0.72, 1.04], 'dir': [0.0173, -0.9924, 0.1219], 'edge': [-0.7055, -0.0985, -0.7018]}),
    'thrust_strike': dict(src='grip:-0.060,-0.660,1.120;dir:0.000,-0.999,0.052', ctrl={'grip': [-0.04, -0.7, 1.06], 'dir': [0.0, -0.9925, 0.1219], 'edge': [-0.7071, -0.0862, -0.7018]}),
    'thrust_windup': dict(src='grip:-0.160,-0.060,1.020;dir:0.104,-0.992,0.070', ctrl={'grip': [-0.24, -0.18, 1.01], 'dir': [-0.0348, -0.997, 0.0698], 'edge': [-0.8667, -0.0046, -0.4988]}),
    'waki': dict(src='grip:-0.180,-0.100,0.880;dir:-0.400,0.850,-0.340;roll:30.00', ctrl={'grip': [-0.19, -0.07, 0.85], 'dir': [-0.4004, 0.8508, -0.3403], 'edge': [-0.3269, -0.4796, -0.8143]}),
}
# <<< TUNED
