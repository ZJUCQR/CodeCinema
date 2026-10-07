"""
cameras.py - shots / sub-cuts, camera keys, DOF, handheld + impact shake, and the headless camera QA
.

    import cameras as C
    mid = C.midpoint_target(shinobi_rig, saint_rig, z=1.3)
    C.shot("S12a", 1177, 1197,
           keys=[(1177, (4.5, -1.0, 1.5), (saint_rig, "head"), 50),      # (frame, pos, look, lens[, roll])
                 (1197, (4.4, -0.8, 1.5), (saint_rig, "head"))],
           dof=dict(focus=(saint_rig, "head"), fstop=2.0), handheld=0.4, shake=[(1195, 0.8, 8)])
    C.impact_shake(1241, strength=0.6, duration=6)                         # on whichever cut is active at 1241

Each cut (shot id "S12" or sub-cut id "S12a", "S22b" ...) is its own camera object "<cut>_cam" plus a timeline
marker named <cut> at f0 bound to it (marker switching = hard cuts, verified to be motion-blur clean).
Keys: location / rotation (baked look-at, Euler-compatible) on the object, lens / DOF on the camera data; the
last key of every channel is CONSTANT.  `look` may be a point, an object or (rig, bone): object/bone aims are
DEFERRED and evaluated at their key frame by resolve_pending() (lane_tools.end_lane calls it while the lane's
own actions are still active), so a lane may create its cameras before or after it animates the characters.
target=<object | (rig, bone) | point> instead tracks continuously with a TRACK_TO constraint (horizon level);
shakes then go onto '<cam>_shake' through Copy Rotation AFTER (bl_util.add_shake convention).
QA: check_screen_direction(report_path) and framing_qa(report_path) project both characters at the first and
last frame of every cut (world_to_camera_view) and write JSON reports.
"""

from codecinema.productions import film_root, source_root
import json
import math
import os
import sys
import zlib

import bpy
from mathutils import Vector

ROOT = str(film_root("silvergrass"))
for _p in (os.path.join(str(source_root("silvergrass")), "common"), os.path.join(str(source_root("silvergrass")), "blender")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import config  # noqa: E402
import bl_util as U  # noqa: E402

CAM_COLLECTION = "CAMERAS"
RIGS = dict(shinobi="SHINOBI_rig", saint="SAINT_rig")
GRASS_CLEAR_R = config.GRASS_CAMERA_CLEAR   # grass scale 0 -> 1 between these distances from the camera
GRASS_HEIGHT = 1.1                  # arena grass (0.95-1.15 m)
CLIP_LIMIT = 0.30                   # framing_qa: > 30 % of a subject's projected box outside the frame
CLOSE_FRAMINGS = {"close", "ecu", "insert", "ots", "cu", "mcu"}

_CUTS = {}                          # cut_id -> dict (in-process registry; cameras also carry custom props)
_PENDING = []                       # deferred aim keys


def reset():
    """Forget the in-process registries (tests / fresh scenes)."""
    _CUTS.clear()
    _PENDING.clear()
    _PENDING_SHAKES.clear()


def _seed(*parts):
    return zlib.crc32(":".join(str(p) for p in parts).encode()) & 0xFFFF


def _current_lane():
    try:
        import lane_tools
        return lane_tools.current_lane()
    except ImportError:
        return None


def _collection(lane):
    if lane:
        import lane_tools
        return lane_tools.lane_collection(lane)
    return U.ensure_collection(CAM_COLLECTION)


# =============================================================================================
# targets
# =============================================================================================
def _ref(t):
    """Normalise a look target: None | ('point', xyz) | ('obj', name) | ('bone', rig_name, bone)."""
    if t is None:
        return None
    if isinstance(t, (tuple, list)) and len(t) == 2 and isinstance(t[1], str):
        rig = t[0] if isinstance(t[0], str) else t[0].name
        return ("bone", rig, t[1])
    if isinstance(t, str):
        return ("bone",) + tuple(t.split(":", 1)) if ":" in t else ("obj", t)
    if hasattr(t, "matrix_world"):
        return ("obj", t.name)
    v = tuple(float(x) for x in t)
    if len(v) != 3:
        raise ValueError(f"look target must be xyz / object / (rig, bone): {t!r}")
    return ("point", v)


def _ref_pos(ref, frame=None):
    """World position of a target ref (evaluated at frame; None = current frame)."""
    if ref[0] == "point":
        return Vector(ref[1])
    if ref[0] == "bone":
        rig = bpy.data.objects[ref[1]]
        return U.world_pos_of((rig, ref[2]), frame)
    return U.world_pos_of(bpy.data.objects[ref[1]], frame)


def midpoint_target(obj_a, obj_b, z=None, name=None):
    """Empty that sits halfway between two objects / (rig, bone) targets (constraints, so it follows them
    continuously); z fixes its height (Limit Location). Usable as `look` or `target`."""
    ra, rb = _ref(obj_a), _ref(obj_b)
    nm = name or f"MID_{ra[1]}_{rb[1]}" + (f"_{z:g}" if z is not None else "")
    emp = bpy.data.objects.get(nm)
    if emp is not None:
        return emp
    emp = U.new_empty(nm, (0, 0, 0), _collection(_current_lane()), display='SPHERE', size=0.1)
    for i, r in enumerate((ra, rb)):
        c = emp.constraints.new('COPY_LOCATION')
        c.target = bpy.data.objects[r[1]]
        if r[0] == "bone":
            c.subtarget = r[2]
        c.influence = 1.0 if i == 0 else 0.5
    if z is not None:
        lim = emp.constraints.new('LIMIT_LOCATION')
        lim.use_min_z = lim.use_max_z = True
        lim.min_z = lim.max_z = float(z)
    return emp


# =============================================================================================
# shots
# =============================================================================================
def _norm_key(k):
    if isinstance(k, dict):
        d = dict(k)
    else:
        k = tuple(k)
        d = dict(frame=k[0], pos=k[1] if len(k) > 1 else None, look=k[2] if len(k) > 2 else None,
                 lens=k[3] if len(k) > 3 else None, roll=k[4] if len(k) > 4 else None)
    d.setdefault("pos", None)
    d.setdefault("look", None)
    d.setdefault("lens", None)
    d.setdefault("roll", None)
    return d


def _shot_of_cut(cut_id):
    for s in sorted(config.SHOTS, key=lambda s: -len(s["id"])):       # 'S22b' before 'S22'
        if cut_id.startswith(s["id"]):
            return s
    return None


def shot(cut_id, f0, f1, keys, lens=35, target=None, dof=None, shake=None, handheld=0.0, subjects=None,
         framing=None, clip=config.CAMERA_CLIP, interp='BEZIER', lane=None, sensor=36.0):
    """Create cut `cut_id` over [f0, f1]: camera '<cut>_cam' + marker <cut> at f0. Returns the camera.

    keys     [(frame, pos, look=None, lens=None, roll_deg=None)] or dicts with those names (+ 'interp').
             pos None -> previous key's position. look: point | object | (rig, bone) | None (= previous look).
    lens     default focal length (mm) when no key sets one.
    target   continuous tracking target (TRACK_TO); per-key looks are then ignored.
    dof      None | f-stop (float, focus on the look/target) | dict(focus=obj|(rig,bone)|distance|xyz,
             fstop=2.8, fstop_keys=[(f, v)], distance_keys=[(f, d)]).
    shake    [(frame, strength 0..1, duration_frames)] impact shakes inside the cut.
    handheld slow handheld drift amplitude in degrees (0 = locked off).
    subjects which characters must be in frame ('shinobi', 'saint'); None = auto (framing_qa).
    framing  'wide' | 'medium' | 'close' | 'ecu' | 'insert' | 'ots' ... ('close' kinds may clip subjects)."""
    lane = lane if lane is not None else _current_lane()
    warn = []
    ks = sorted((_norm_key(k) for k in keys), key=lambda d: d["frame"])
    if not ks or ks[0]["pos"] is None:
        raise ValueError(f"shot {cut_id}: the first key needs a position")
    for d in ks:
        if not (f0 - 2 <= d["frame"] <= f1 + 2):
            warn.append(f"key at {d['frame']} outside the cut {f0}-{f1}")
    s = _shot_of_cut(cut_id)
    if s is not None and not (s["start"] <= f0 and f1 <= s["end"]):
        warn.append(f"cut {f0}-{f1} not inside shot {s['id']} {s['start']}-{s['end']}")
    name = f"{cut_id}_cam"
    if bpy.data.objects.get(name) is not None:
        raise ValueError(f"shot {cut_id}: camera {name} already exists")
    first_look = next((d["look"] for d in ks if d["look"] is not None), None)
    aim0 = _ref(target) if target is not None else _ref(first_look)
    p0 = Vector(ks[0]["pos"])
    look0 = Vector(aim0[1]) if aim0 is not None and aim0[0] == "point" else p0 + Vector((0, 1, 0))
    cam = U.new_camera(name, tuple(p0), tuple(look0), lens=float(ks[0]["lens"] or lens), sensor=sensor,
                       clip=clip, collection=_collection(lane))
    cam["cut"], cam["cut_f0"], cam["cut_f1"] = cut_id, int(f0), int(f1)
    cam["framing"] = framing or ""
    if subjects is not None:
        cam["subjects"] = ",".join(subjects)
    # --- location + lens keys
    pos = None
    any_lens = any(d["lens"] is not None for d in ks)
    for d in ks:
        pos = Vector(d["pos"]) if d["pos"] is not None else pos
        d["pos"] = tuple(pos)
        it = d.get("interp", interp)
        U.key(cam, "location", d["frame"], tuple(pos), interp=it)
        if d["lens"] is not None:
            U.key(cam.data, "lens", d["frame"], float(d["lens"]), interp=it)
    if not any_lens:
        cam.data.lens = float(lens)
    # --- aim
    if target is not None:
        if any(d["look"] is not None for d in ks):
            warn.append("per-key looks ignored (continuous target set)")
        tr = cam.constraints.new('TRACK_TO')
        tr.track_axis, tr.up_axis = 'TRACK_NEGATIVE_Z', 'UP_Y'
        if aim0[0] == "point":
            tr.target = U.new_empty(f"{cut_id}_aim", aim0[1], cam.users_collection[0], size=0.1)
        else:
            tr.target = bpy.data.objects[aim0[1]]
            if aim0[0] == "bone":
                tr.subtarget = aim0[2]
    else:
        look = None
        for d in ks:
            look = _ref(d["look"]) if d["look"] is not None else look
            if look is None:
                raise ValueError(f"shot {cut_id}: no look target for key {d['frame']}")
            _PENDING.append(dict(cam=cam.name, frame=d["frame"], pos=d["pos"], look=look,
                                 roll=float(d["roll"] or 0.0), interp=d.get("interp", interp), lane=lane))
        mine = [p for p in _PENDING if p["cam"] == cam.name]
        if all(p["look"][0] == "point" for p in mine):
            resolve_pending(camera=cam.name)
        else:       # placeholders (overwritten by resolve_pending) so that shake noise never adds stray keys
            for p in mine:
                U.key(cam, "rotation_euler", p["frame"], tuple(cam.rotation_euler), interp=p["interp"])
    # --- DOF
    _setup_dof(cam, ks, dof, target, interp)
    last = ks[-1]["frame"]
    U.set_key_interp_at(cam, last, 'CONSTANT')
    U.set_key_interp_at(cam.data, last, 'CONSTANT')
    # --- marker, shakes
    if any(m.frame == f0 for m in bpy.context.scene.timeline_markers):
        warn.append(f"replacing an existing marker at {f0}")
    U.bind_camera_marker(int(f0), cam, name=cut_id)
    _CUTS[cut_id] = dict(cut=cut_id, f0=int(f0), f1=int(f1), cam=cam.name, lane=lane, subjects=subjects,
                         framing=framing, warnings=warn)
    if handheld:
        _noise(cam, f0, f1 + 1, amp_deg=float(handheld), scale=16.0, blend_in=0, blend_out=0,
               seed=_seed(cut_id, "handheld"))
    for sh in shake or ():
        impact_shake(*sh, camera=cam)
    for w in warn:
        print(f"[cameras] WARNING {cut_id}: {w}")
    return cam


def _setup_dof(cam, ks, dof, target, interp):
    cd = cam.data
    if dof is None or dof is False:
        cd.dof.use_dof = False
        return
    if isinstance(dof, (int, float)):
        dof = dict(fstop=float(dof))
    cd.dof.use_dof = True
    cd.dof.aperture_fstop = float(dof.get("fstop", 2.8))
    focus = dof.get("focus", "target")
    if focus == "target":
        focus = target if target is not None else next((d["look"] for d in ks if d["look"] is not None), None)
    ref = None
    if isinstance(focus, (int, float)):
        cd.dof.focus_distance = float(focus)
    elif focus is not None:
        ref = _ref(focus)
    if ref is not None and ref[0] in ("obj", "bone"):
        cd.dof.focus_object = bpy.data.objects[ref[1]]
        if ref[0] == "bone":
            cd.dof.focus_subtarget = ref[2]
    elif ref is not None:                               # a point: key the distance per camera key
        for d in ks:
            U.key(cd, "dof.focus_distance", d["frame"], (Vector(d["pos"]) - Vector(ref[1])).length,
                  interp=d.get("interp", interp))
    for f, v in dof.get("fstop_keys", ()):
        U.key(cd, "dof.aperture_fstop", f, float(v), interp=interp)
    for f, v in dof.get("distance_keys", ()):
        U.key(cd, "dof.focus_distance", f, float(v), interp=interp)


def resolve_pending(lane=None, camera=None):
    """Bake the deferred look-at rotation keys (objects / bones evaluated at their key frames). Called by
    lane_tools.end_lane (lane=<lane>) while the lane's actions are still active. Returns #keys baked."""
    todo = [p for p in _PENDING if (lane is None or p["lane"] == lane) and (camera is None or p["cam"] == camera)]
    if camera is None:
        for sh in [x for x in _PENDING_SHAKES if lane is None or x["lane"] == lane]:
            _PENDING_SHAKES.remove(sh)
            cut, cam = cut_at(sh["frame"])
            if cam is None:
                print(f"[cameras] WARNING impact_shake({sh['frame']}): no camera covers that frame")
                continue
            impact_shake(sh["frame"], sh["strength"], sh["duration"], camera=cam)
    if not todo:
        return 0
    sc = bpy.context.scene
    fnow = sc.frame_current
    n = 0
    with U.muted_modifiers():
        for cname in sorted({p["cam"] for p in todo}):
            cam = bpy.data.objects.get(cname)
            keys = sorted((p for p in todo if p["cam"] == cname), key=lambda p: p["frame"])
            if cam is None:
                continue
            compat = None
            for p in keys:
                tgt = _ref_pos(p["look"], p["frame"])
                e = U.look_at_euler(p["pos"], tgt, math.radians(p["roll"]), compat=compat)
                compat = e
                U.key(cam, "rotation_euler", p["frame"], tuple(e), interp=p["interp"])
                n += 1
            U.set_key_interp_at(cam, keys[-1]["frame"], 'CONSTANT', "rotation_euler")
    for p in todo:
        _PENDING.remove(p)
    sc.frame_set(fnow)
    return n


# =============================================================================================
# shake
# =============================================================================================
def _carrier(cam):
    """Object that receives rotation noise: the camera, or '<cam>_shake' (Copy Rotation AFTER) when tracked."""
    if not any(c.type in ('TRACK_TO', 'DAMPED_TRACK', 'LOCKED_TRACK') for c in cam.constraints):
        return cam
    nm = cam.name + "_shake"
    car = bpy.data.objects.get(nm)
    if car is None:
        car = U.new_empty(nm, (0, 0, 0), cam.users_collection[0] if cam.users_collection else None)
        cr = cam.constraints.new('COPY_ROTATION')
        cr.name = "shake"
        cr.target = car
        cr.mix_mode = 'AFTER'
        cr.owner_space = 'WORLD'
        cr.target_space = 'WORLD'
    return car


def _noise(cam, f0, f1, amp_deg, scale, blend_in, blend_out, seed):
    car = _carrier(cam)
    strength = math.radians(amp_deg) / 0.33
    mods = []
    for i in (0, 1, 2):
        m = U.add_noise(car, "rotation_euler", i, strength * (0.35 if i == 2 else 1.0), scale=scale,
                        frame_range=(f0, f1), blend=0.0, phase=(seed % 997) * 0.731 + i * 11.3)
        m.blend_in, m.blend_out = float(blend_in), float(blend_out)
        mods.append(m)
    return mods


def cut_at(frame, scene=None):
    """(cut_id, camera) active at `frame` according to the timeline markers (None, scene.camera if none)."""
    sc = scene or bpy.context.scene
    best = None
    for m in sorted((m for m in sc.timeline_markers if m.camera is not None), key=lambda m: m.frame):
        if m.frame <= frame:
            best = (m.name, m.camera)
        else:
            break
    return best if best is not None else (None, sc.camera)


_PENDING_SHAKES = []


def impact_shake(frame, strength=1.0, duration=8, camera=None):
    """Sharp shake starting at `frame` on the camera active then (or `camera`): peak ~1.2 deg * strength,
    fast noise, decays over `duration` frames, clamped to the cut's last frame. Returns the modifiers.
    If no cut covers `frame` yet (the lane creates that camera later), the shake is deferred to
    resolve_pending() (lane_tools.end_lane) and [] is returned."""
    if camera is None:
        cut, camera = cut_at(frame)
        f1c = camera.get("cut_f1") if camera is not None else None
        if camera is None or (f1c is not None and frame > int(f1c)):
            _PENDING_SHAKES.append(dict(frame=frame, strength=strength, duration=duration, lane=_current_lane()))
            return []
    f1 = frame + max(2, int(duration))
    cf1 = camera.get("cut_f1")
    if cf1 is not None:
        f1 = min(f1, int(cf1) + 1)
    return _noise(camera, frame, f1, amp_deg=1.2 * float(strength), scale=1.6, blend_in=0.5,
                  blend_out=max(1.0, 0.7 * (f1 - frame)), seed=_seed(camera.name, frame))


# =============================================================================================
# QA
# =============================================================================================
def cut_list(scene=None):
    """[(cut_id, f0, f1, camera)] for every marker bound to a camera, sorted by f0 (f1 from the camera's
    cut_f1 property, else the next marker - 1)."""
    sc = scene or bpy.context.scene
    ms = sorted((m for m in sc.timeline_markers if m.camera is not None), key=lambda m: m.frame)
    out = []
    for i, m in enumerate(ms):
        nxt = ms[i + 1].frame - 1 if i + 1 < len(ms) else config.FRAME_END
        f1 = int(m.camera.get("cut_f1", nxt)) if m.camera.get("cut", m.name) == m.name else nxt
        out.append((m.name, m.frame, f1, m.camera))
    return out


def _rig(who):
    return bpy.data.objects.get(RIGS[who])


def _head(rig):
    if rig.pose is not None and "head" in rig.pose.bones:
        pb = rig.pose.bones["head"]
        return rig.matrix_world @ ((pb.head + pb.tail) * 0.5)
    return rig.matrix_world @ Vector((0, 0, 1.6))


def _project(sc, cam, p):
    from bpy_extras.object_utils import world_to_camera_view
    co = world_to_camera_view(sc, cam, p)
    return co.x, co.y, co.z


def _rig_points(rig):
    pts = []
    if rig.pose is not None and len(rig.pose.bones):
        for pb in rig.pose.bones:
            pts.append(rig.matrix_world @ pb.head)
            pts.append(rig.matrix_world @ pb.tail)
        h = _head(rig)
        for d in ((0.13, 0, 0), (-0.13, 0, 0), (0, 0.13, 0), (0, -0.13, 0), (0, 0, 0.14)):
            pts.append(h + Vector(d))
    else:
        base = rig.matrix_world.translation
        for z in (0.0, 0.9, 1.8):
            for dx, dy in ((0.25, 0), (-0.25, 0), (0, 0.25), (0, -0.25)):
                pts.append(base + Vector((dx, dy, z)))
    return pts


def _frames_of(f0, f1):
    return sorted({int(f0), int(f1)})


LINE_MIN_DIST = 0.4                 # m: characters closer than this -> the action line is undefined (SKIP)
ON_LINE_SIN = 0.03                  # |sin| of the camera's bearing to the line below this -> neutral shot ON the line


def line_side(shinobi_xy, elder_xy, cam_xy):
    """Signed sine of the camera's bearing relative to the action line shinobi -> elder (top view, XY).
    Negative: seen from the camera the shinobi is screen-LEFT of the elder (DIRECTION §1 before the S25 pass);
    positive: screen-right (after the pass).  Works for single shots too - no projection, the off-screen
    character's world position defines the line.  Returns (sine, line length m)."""
    dx, dy = elder_xy[0] - shinobi_xy[0], elder_xy[1] - shinobi_xy[1]
    cx, cy = cam_xy[0] - shinobi_xy[0], cam_xy[1] - shinobi_xy[1]
    ld, lc = math.hypot(dx, dy), math.hypot(cx, cy)
    if ld < 1e-9 or lc < 1e-9:
        return 0.0, ld
    return (dx * cy - dy * cx) / (ld * lc), ld


def check_screen_direction(report_path=None, cuts=None, scene=None):
    """180-degree rule (DIRECTION §1) at the first + last frame of every cut from SCREEN_DIRECTION.first_frame:
      side   (every cut with a character in or near the view, singles included) the camera must be on the side
             of the shinobi->elder action line from
             which the shinobi reads screen-LEFT before swap_frame and screen-RIGHT after it (line_side < 0 / > 0);
             SKIP when the characters overlap (line undefined) or the camera sits on the line (neutral shot).
      order  (two-shots: both heads on screen) projected head x order must agree.
      facing (single shots) projected facing of the visible character - INFO only (characters legitimately
             turn away: haori shed, tumbles, the back-to-back staging after the pass).
    FAIL if side or order fails.  Writes JSON when report_path is given. Returns dict(passed, failed, skipped,
    items)."""
    sc = scene or bpy.context.scene
    sd = config.SCREEN_DIRECTION
    rigs = {w: _rig(w) for w in RIGS}
    items = []
    fnow = sc.frame_current
    with U.muted_modifiers():
        for cut, f0, f1, cam in (cuts or cut_list(sc)):
            if f1 < sd["first_frame"]:
                continue
            for f in _frames_of(max(f0, sd["first_frame"]), f1):
                sc.frame_set(f)
                before = f < sd["swap_frame"] or f > config.FRAME_END     # dev lanes after the film: default staging
                it = dict(cut=cut, frame=f, rule="shinobi_left" if before else "shinobi_right", checks={})
                proj, heads = {}, {}
                for w, rig in rigs.items():
                    if rig is None:
                        continue
                    heads[w] = _head(rig)
                    x, y, z = _project(sc, cam, heads[w])
                    on = z > 0 and -0.02 <= x <= 1.02 and -0.02 <= y <= 1.02
                    proj[w] = (x, y, z, on)
                    it[w] = dict(x=round(x, 3), y=round(y, 3), depth=round(z, 2), onscreen=on)
                statuses = []
                in_view = [w for w in proj if proj[w][2] > 0 and -0.5 <= proj[w][0] <= 1.5]
                if len(heads) == 2 and not in_view:
                    it["checks"]["side"] = "SKIP (no character in view)"
                elif len(heads) == 2:
                    cpos = cam.matrix_world.translation
                    sn, ld = line_side(heads["shinobi"].xy, heads["saint"].xy, cpos.xy)
                    it["side_sin"] = round(sn, 4)
                    if ld < LINE_MIN_DIST:
                        it["checks"]["side"] = "SKIP (characters overlap: no line)"
                    elif abs(sn) < ON_LINE_SIN:
                        it["checks"]["side"] = "SKIP (camera on the line: neutral shot)"
                    else:
                        ok = (sn < 0) == before
                        it["checks"]["side"] = "PASS" if ok else "FAIL"
                        statuses.append(ok)
                vis = [w for w in proj if proj[w][3]]
                if len(vis) == 2:
                    ok = (proj["shinobi"][0] < proj["saint"][0]) == before
                    it["checks"]["order"] = "PASS" if ok else "FAIL"
                    statuses.append(ok)
                elif len(vis) == 1:
                    w = vis[0]
                    rig = rigs[w]
                    fwd = rig.matrix_world.to_3x3() @ Vector((0, -1, 0))
                    fwd.z = 0
                    x1 = _project(sc, cam, heads[w] + fwd.normalized() * 0.5)[0] if fwd.length > 1e-6 else proj[w][0]
                    dx = x1 - proj[w][0]
                    it["facing_dx"] = round(dx, 4)
                    if abs(dx) >= 0.01:
                        want_right = (w == "shinobi") == before
                        it["checks"]["facing"] = "INFO " + ("as staged" if (dx > 0) == want_right else
                                                           "turned away (allowed)")
                if not statuses:
                    it["status"] = "SKIP"
                else:
                    it["status"] = "PASS" if all(statuses) else "FAIL"
                it["check"] = ",".join(k for k, v in it["checks"].items() if not v.startswith(("SKIP", "INFO")))
                items.append(it)
    sc.frame_set(fnow)
    res = dict(passed=sum(i["status"] == "PASS" for i in items), failed=sum(i["status"] == "FAIL" for i in items),
               skipped=sum(i["status"] == "SKIP" for i in items), items=items)
    if report_path:
        _write_json(report_path, res)
    return res


def framing_qa(report_path=None, cuts=None, scene=None, clear_r=None):
    """Framing checks at the first + last frame of every cut: per character the projected box (bones + head
    padding) -> visible fraction, head on screen, distance to the camera. Flags (for the cut's subjects;
    auto = characters whose head is on screen): 'offscreen' (FAIL, listed subjects only), 'clipped>30%'
    (WARN unless the cut's framing is close/ecu/insert/ots), 'grass_clearance' (WARN: any character within the
    active-camera grass clearance radius with its feet on screen), 'camera_in_ground' (WARN).
    Writes JSON when report_path is given. Returns dict(fails, warns, items)."""
    sc = scene or bpy.context.scene
    r_clear = (clear_r or GRASS_CLEAR_R)[1]
    items = []
    fnow = sc.frame_current
    with U.muted_modifiers():
        for cut, f0, f1, cam in (cuts or cut_list(sc)):
            framing = str(cam.get("framing", "") or "").lower()
            listed = [s for s in str(cam.get("subjects", "")).split(",") if s] if "subjects" in cam.keys() else None
            for f in _frames_of(f0, f1):
                if any(a <= f <= b for a, b in config.RENDER_SKIP):
                    continue
                sc.frame_set(f)
                cpos = cam.matrix_world.translation
                it = dict(cut=cut, frame=f, framing=framing, flags=[], chars={})
                if cpos.z < 0.05:
                    it["flags"].append(("WARN", "camera_in_ground", round(cpos.z, 2)))
                for w in RIGS:
                    rig = _rig(w)
                    if rig is None:
                        continue
                    pr = [_project(sc, cam, p) for p in _rig_points(rig)]
                    front = [(x, y) for x, y, z in pr if z > 0]
                    hx, hy, hz = _project(sc, cam, _head(rig))
                    head_on = hz > 0 and 0 <= hx <= 1 and 0 <= hy <= 1
                    vis = 0.0
                    if front:
                        x0, x1 = min(p[0] for p in front), max(p[0] for p in front)
                        y0, y1 = min(p[1] for p in front), max(p[1] for p in front)
                        area = max(1e-9, (x1 - x0) * (y1 - y0))
                        ix = max(0.0, min(1.0, x1) - max(0.0, x0))
                        iy = max(0.0, min(1.0, y1) - max(0.0, y0))
                        vis = (ix * iy) / area
                    base = rig.matrix_world.translation
                    feet = _project(sc, cam, base + Vector((0, 0, 0.05)))
                    feet_on = feet[2] > 0 and 0 <= feet[0] <= 1 and 0 <= feet[1] <= 1
                    dxy = math.hypot(base.x - cpos.x, base.y - cpos.y)
                    it["chars"][w] = dict(head_on=head_on, visible=round(vis, 3), dist_xy=round(dxy, 2),
                                          feet_on=feet_on)
                    if dxy < r_clear and feet_on:        # any visible character, subject or not
                        it["flags"].append(("WARN", f"{w}:grass_clearance", round(dxy, 2)))
                    subject = (w in listed) if listed is not None else head_on
                    if not subject:
                        continue
                    if listed is not None and (vis <= 0.0 or not front):
                        it["flags"].append(("FAIL", f"{w}:offscreen", round(vis, 3)))
                    elif 1.0 - vis > CLIP_LIMIT and framing not in CLOSE_FRAMINGS:
                        it["flags"].append(("WARN", f"{w}:clipped>30%", round(1.0 - vis, 3)))
                items.append(it)
    sc.frame_set(fnow)
    res = dict(fails=sum(1 for i in items for fl in i["flags"] if fl[0] == "FAIL"),
               warns=sum(1 for i in items for fl in i["flags"] if fl[0] == "WARN"), items=items)
    if report_path:
        _write_json(report_path, res)
    return res


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
