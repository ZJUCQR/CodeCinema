"""
props.py - free props in flight: deterministic ballistic keys with bounce / settle / stick,
the evaluated-mesh snapshot for the thrown haori, and helpers for the story beats (runs inside Blender 5.2).

Public API
  toss(obj, f0, p0=None, v0=(0,0,0), spin=(0,0,0), ground_z=0.0, settle=True, ...) -> dict
        Keys obj.location / obj.rotation_euler (LINEAR, every `step` frames) from f0 until the prop rests.
        Physics runs on the FILM clock (fxclock.fx_time_at): inside config.TIME_WARP slow-motion windows the prop
        slows down with everything else. Bounce (restitution, friction, spin damping), then a short settle onto
        its flattest side (principal axes of its mesh), or stick=True: plants where it first touches the ground.
        ground_z: float or callable(x, y) -> z (e.g. environment.terrain_height).
  snapshot_evaluated(src_obj, frame, name, shape_keys=True, collection=None) -> obj
        Evaluated (deformed) mesh of src at `frame` copied into object `name` (created if missing) so that it sits
        exactly on src at that frame (0 mm, no pop): local frame = src's world rotation at the vertex centroid.
        Adds shape keys 'spread' (opened flat, in flight) and 'crumple' (collapsed heap) at value 0.
  cloth_shapes(obj) -> obj              rebuild good 'spread' / 'crumple' keys on an existing snapshot mesh
  key_shape(obj, key_name, frame, value, interp='BEZIER')
  Story helpers (each keys the state switch, snaps the free piece onto its attached twin, then tosses it):
  cut_hat(frame, away=(0,1,0), speed=2.2, seed='S13')             SAINT_hat -> halves A/B flying apart
  drop_spear_sheath(frame, v0=None, spin=None, ground_z=0.0)       SAINT_spear_sheath_world spins off (S14)
  break_tip(frame, v0=None, spin=None, ground_z=0.0, stick=True)   SAINT katana tip snaps and plants (S26)
  cut_cord(frame, drift=(0.35, 0.15, 0.05), frames=90, seed='S26') SAINT_beard_cord_cut flutters away (light, drag)
  fly_haori(frame, v0=(0.6,-0.3,1.6), spin=(0,0,2.5), ground_z=0.0, spread=(2,10), crumple=6)
        after characters.set_costume(frame, haori=False): throws SAINT_haori_thrown, opens it (spread) in flight
        and crumples it on landing.
  throw_kunai(i, frame, target, speed=18.0, stick=True, ground_z=0.0)   SHINOBI_kunai_<i> flies point-first
Deterministic: no randomness except seeds from zlib.crc32 of fixed strings; no Python hash().
"""
import os
import sys
import zlib

import bpy
import numpy as np
from mathutils import Euler, Matrix, Quaternion, Vector

ROOT = (__import__("os").environ.get("SILVERGRASS_ROOT") or str(next(p for p in __import__("pathlib").Path(__file__).resolve().parents if (p / "src" / "common" / "config.py").is_file())))   # repo root (portable)
for _p in (os.path.join(ROOT, "src", "common"), os.path.join(ROOT, "src", "blender")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import config  # noqa: E402
import bl_util as U  # noqa: E402

GRAVITY = -9.81


def _seed(s):
    return zlib.crc32(s.encode("utf-8")) & 0x7FFFFFFF


def _obj(o):
    return bpy.data.objects[o] if isinstance(o, str) else o


def _dt(frame, use_fx_time=True):
    """Seconds of film time between frame-1 and frame (slow motion aware)."""
    if not use_fx_time:
        return 1.0 / config.FPS
    import fxclock
    return max(fxclock.fx_time_at(frame) - fxclock.fx_time_at(frame - 1), 0.0)


def _local_verts(obj):
    """Object-space vertex positions (basis mesh) as (n, 3) ndarray."""
    me = obj.data
    n = len(me.vertices)
    co = np.zeros(n * 3)
    me.vertices.foreach_get("co", co)
    return co.reshape(-1, 3) if n else np.zeros((1, 3))


def _principal_axes(V):
    """Principal axes (columns) of a point cloud sorted by extent, largest first."""
    C = V - V.mean(axis=0)
    w, E = np.linalg.eigh(C.T @ C / max(len(V), 1))
    order = np.argsort(w)[::-1]
    return E[:, order], np.sqrt(np.maximum(w[order], 0.0))


def _ground(ground_z, x, y):
    return float(ground_z(x, y)) if callable(ground_z) else float(ground_z)


def _rest_quat(q, V):
    """Nearest orientation to q in which the prop lies on its flattest side (smallest principal axis vertical)."""
    E, _ = _principal_axes(V)
    small = Vector(E[:, 2])
    world = q @ small
    up = Vector((0.0, 0.0, 1.0 if world.z >= 0 else -1.0))
    d = world.rotation_difference(up)
    return d @ q


def toss(obj, f0, p0=None, v0=(0.0, 0.0, 0.0), spin=(0.0, 0.0, 0.0), ground_z=0.0, settle=True, f_end=None,
         gravity=GRAVITY, restitution=0.32, friction=0.45, spin_damp=0.55, rot0=None, stick=False,
         stick_depth=0.04, drag=0.0, wind=(0.0, 0.0, 0.0), settle_frames=8, max_frames=240, step=1,
         use_fx_time=True, interp='LINEAR', key_start=True):
    """Deterministic ballistic flight of a FREE object (no parent) from frame f0.
    p0: start position (world; None = the object's current location), v0: m/s, spin: angular velocity (rad/s,
    world axes), rot0: start rotation (Euler/Quaternion/Matrix; None = current). Collides its lowest vertex with
    ground_z (float | callable(x, y)); bounces with `restitution`, loses `friction` of the horizontal speed and
    `spin_damp` of the spin per bounce; when slow it settles onto its flattest side over `settle_frames` frames
    (settle=True) or simply stops. stick=True: stops at the FIRST contact, pushed `stick_depth` into the ground
    along its travel (blades, kunai, spear). drag (1/s) pulls the velocity towards `wind` (light props).
    Keys location + rotation_euler every `step` frames (interp LINEAR) and returns
    dict(frames=[...], contact=frame|None, rest=frame|None, final_loc, final_rot, bounces)."""
    ob = _obj(obj)
    if ob.parent is not None:
        raise ValueError(f"toss(): {ob.name} is parented to {ob.parent.name}; toss free objects only")
    ob.rotation_mode = 'XYZ'
    V = _local_verts(ob)
    p = Vector(p0) if p0 is not None else ob.location.copy()
    if rot0 is None:
        q = ob.rotation_euler.to_quaternion()
    elif isinstance(rot0, Quaternion):
        q = rot0.copy()
    elif isinstance(rot0, Matrix):
        q = rot0.to_quaternion()
    else:
        q = Euler(rot0, 'XYZ').to_quaternion()
    v = Vector(v0)
    w = Vector(spin)
    g = Vector((0.0, 0.0, gravity))
    wind_v = Vector(wind)
    frames, bounces = [], 0
    contact = rest = None
    prev_e = ob.rotation_euler.copy()
    last = f0 + max_frames if f_end is None else f_end
    settling = None
    q_start = q_rest = None
    f = f0

    def lowest(pos, quat):
        R = np.array(quat.to_matrix())
        P = V @ R.T + np.array(pos)
        i = int(np.argmin(P[:, 2]))
        return P[i], i

    def key(frame, pos, quat):
        nonlocal prev_e
        e = quat.to_euler('XYZ', prev_e)
        prev_e = e
        if frame == f0 and not key_start:
            return
        U.key(ob, "location", frame, tuple(pos), interp=interp)
        U.key(ob, "rotation_euler", frame, tuple(e), interp=interp)
        frames.append(frame)

    key(f, p, q)
    while f < last:
        f_next = f + step
        dt = sum(_dt(ff, use_fx_time) for ff in range(f + 1, f_next + 1))
        if settling is not None:
            k = min(1.0, (f_next - settling) / max(settle_frames, 1))
            s = k * k * (3 - 2 * k)
            qq = q_start.slerp(q_rest, s)
            low, _ = lowest(p, qq)
            gz = _ground(ground_z, low[0], low[1])
            pp = p.copy()
            pp.z += gz - low[2]
            key(f_next, pp, qq)
            if k >= 1.0:
                rest = f_next
                p, q = pp, qq
                break
            f = f_next
            continue
        # integrate (semi-implicit Euler, 4 substeps)
        sub = 4
        for _ in range(sub):
            h = dt / sub
            if drag > 0.0:
                v += (wind_v - v) * min(drag * h, 1.0)
            v += g * h
            p += v * h
            ang = w.length * h
            if ang > 1e-9:
                q = Quaternion(w.normalized(), ang) @ q
        low, _ = lowest(p, q)
        gz = _ground(ground_z, low[0], low[1])
        if low[2] < gz:
            if contact is None:
                contact = f_next
            if stick:
                d = v.normalized() if v.length > 1e-6 else Vector((0.0, 0.0, -1.0))
                pen = gz - low[2]
                p.z += pen
                p += d * stick_depth
                key(f_next, p, q)
                rest = f_next
                break
            p.z += gz - low[2]
            if v.z < 0:
                v.z = -v.z * restitution
            v.x *= (1.0 - friction)
            v.y *= (1.0 - friction)
            w *= (1.0 - spin_damp)
            bounces += 1
            if v.z < 0.45 and Vector((v.x, v.y, 0.0)).length < 0.4:
                if settle:
                    settling = f_next
                    q_start = q.copy()
                    q_rest = _rest_quat(q, V)
                    key(f_next, p, q)
                    f = f_next
                    continue
                key(f_next, p, q)
                rest = f_next
                break
        key(f_next, p, q)
        f = f_next
    return dict(frames=frames, contact=contact, rest=rest, final_loc=tuple(p), final_rot=tuple(q.to_euler('XYZ')),
                bounces=bounces)


# =============================================================================================
# snapshot of an evaluated (skinned) mesh + cloth shape keys
# =============================================================================================
def snapshot_evaluated(src_obj, frame, name, shape_keys=True, collection=None):
    """Copy the EVALUATED mesh of `src_obj` at `frame` into object `name` (created in `collection` / the source's
    collection when missing), placed so every vertex coincides with the deformed source at that frame (no pop).
    Local frame: the source's world rotation, origin at the vertex centroid. Materials and UVs are kept.
    shape_keys: adds 'spread' and 'crumple' (value 0) via cloth_shapes(). Returns the object."""
    src = _obj(src_obj)
    sc = bpy.context.scene
    fcur = sc.frame_current
    U.frame_set(frame)
    hv = src.hide_viewport
    src.hide_viewport = False
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = src.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    Mw = ev.matrix_world.copy()
    src.hide_viewport = hv
    n = len(me.vertices)
    co = np.zeros(n * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    Mn = np.array(Mw)
    world = co @ Mn[:3, :3].T + Mn[:3, 3] if n else co
    cen = world.mean(axis=0) if n else np.zeros(3)
    R = Mw.to_quaternion().to_matrix().to_4x4()
    F = Matrix.Translation(Vector(cen)) @ R
    Fi = np.array(F.inverted())
    local = world @ Fi[:3, :3].T + Fi[:3, 3]
    me.vertices.foreach_set("co", local.ravel())
    me.update()
    me.name = f"{name}_mesh"
    ob = bpy.data.objects.get(name)
    if ob is None:
        ob = bpy.data.objects.new(name, me)
        col = collection or (src.users_collection[0] if src.users_collection else sc.collection)
        col.objects.link(ob)
    else:
        old = ob.data
        if ob.data is not None and ob.data.shape_keys is not None:
            ob.shape_key_clear()
        ob.data = me
        if old is not None and old != me and old.users == 0:
            bpy.data.meshes.remove(old)
        for m in list(ob.modifiers):
            ob.modifiers.remove(m)
        ob.vertex_groups.clear()
    ob.parent = None
    ob.matrix_world = F
    ob.rotation_mode = 'XYZ'
    if shape_keys and n:
        cloth_shapes(ob)
    U.frame_set(fcur)
    return ob


def cloth_shapes(obj, seed_name=None):
    """(Re)build shape keys on a snapshot cloth mesh: 'spread' = opened flat in flight (flattened along its
    thinnest principal axis, widened 25 %, a gentle sail curve) and 'crumple' = a collapsed heap (flattened to
    ~22 % height in the local frame's thinnest axis, pulled towards the centre, deterministic folds).
    Both at value 0 (Blender 5.2 creates new keys at 1.0 - reset explicitly)."""
    ob = _obj(obj)
    if ob.data.shape_keys is not None:
        ob.shape_key_clear()
    V = _local_verts(ob)
    E, ext = _principal_axes(V)
    c = V.mean(axis=0)
    L = (V - c) @ E                                   # coordinates in principal axes (a0 largest .. a2 thinnest)
    sp = L.copy()
    sp[:, 0] *= 1.25
    sp[:, 1] *= 1.15
    r = np.sqrt((sp[:, 0] / max(ext[0] * 2.0, 1e-6)) ** 2 + (sp[:, 1] / max(ext[1] * 2.0, 1e-6)) ** 2)
    sp[:, 2] = sp[:, 2] * 0.12 - 0.10 * r * r * max(ext[0], 0.1)
    spread = c + sp @ E.T
    rng = np.random.default_rng(_seed(seed_name or f"{ob.name}:crumple"))
    cr = L.copy()
    cr[:, 0] *= 0.62
    cr[:, 1] *= 0.55
    fold = np.sin(L[:, 0] * 23.0 + 1.3) * np.cos(L[:, 1] * 17.0) * 0.035
    cr[:, 2] = cr[:, 2] * 0.22 + fold + rng.uniform(-0.012, 0.012, len(L))
    crumple = c + cr @ E.T
    ob.shape_key_add(name="Basis", from_mix=False)
    k1 = ob.shape_key_add(name="spread", from_mix=False)
    k2 = ob.shape_key_add(name="crumple", from_mix=False)
    k1.data.foreach_set("co", spread.ravel())
    k2.data.foreach_set("co", crumple.ravel())
    k1.value = k2.value = 0.0
    return ob


def key_shape(obj, key_name, frame, value, interp='BEZIER'):
    """Key a shape-key value (lives on the mesh's Key datablock)."""
    ob = _obj(obj)
    kb = ob.data.shape_keys.key_blocks[key_name]
    kb.value = float(value)
    U.key(kb, "value", frame, float(value), interp=interp)


# =============================================================================================
# story helpers
# =============================================================================================
def _C():
    import characters
    return characters


def _snap_world(name, frame):
    """Snap a free piece onto its attached twin at `frame` (CONSTANT) and return its world matrix there."""
    C = _C()
    ob = _obj(name)
    C.snap_free(ob, frame)
    return C.detach_matrix(ob, frame)


def cut_hat(frame, away=(0.0, 1.0, 0.0), speed=2.2, up=1.6, seed="S13", ground_z=0.0, **kw):
    """S13: set_hat('cut') at `frame`; the two halves fly apart sideways (along the hat's local +-X) and away
    (world `away`), tumbling, then bounce and settle in the grass. Returns {half: toss result}."""
    C = _C()
    C.set_hat(frame, "cut")
    out = {}
    for half, sx in (("A", 1.0), ("B", -1.0)):
        nm = f"SAINT_hat_half_{half}"
        M = _snap_world(nm, frame)
        side = (M.to_3x3() @ Vector((sx, 0.0, 0.0))).normalized()
        rng = np.random.default_rng(_seed(f"{seed}:{half}"))
        v0 = side * speed * 0.8 + Vector(away).normalized() * speed * 0.6 + Vector((0.0, 0.0, up))
        spin = (M.to_3x3() @ Vector((0.0, 1.0, 0.0))) * (sx * (6.0 + rng.uniform(0, 2))) + \
            Vector(rng.uniform(-1.5, 1.5, 3).tolist())
        out[half] = toss(nm, frame, p0=M.translation, v0=v0, spin=spin, rot0=M, ground_z=ground_z,
                         key_start=False, **kw)
    return out


def drop_spear_sheath(frame, v0=None, spin=None, ground_z=0.0, seed="S14", **kw):
    """S14: the black-lacquer spear sheath comes off the blade at `frame` and spins away into the grass
    (call after characters.set_weapon_state('SAINT', frame, 'in_hand'))."""
    M = _snap_world("SAINT_spear_sheath_world", frame)
    ax = (M.to_3x3() @ Vector((0.0, 1.0, 0.0))).normalized()
    v0 = Vector(v0) if v0 is not None else ax * 2.5 + Vector((0.0, 0.0, 1.8))
    rng = np.random.default_rng(_seed(seed))
    spin = Vector(spin) if spin is not None else (M.to_3x3() @ Vector((1.0, 0.0, 0.0))) * 11.0 + \
        Vector(rng.uniform(-1, 1, 3).tolist())
    return toss("SAINT_spear_sheath_world", frame, p0=M.translation, v0=v0, spin=spin, rot0=M, ground_z=ground_z,
                key_start=False, **kw)


def break_tip(frame, v0=None, spin=None, ground_z=0.0, stick=True, seed="S26", **kw):
    """S26: the elder's blade snaps at `frame` (set_weapon_state 'broken'); the tip spins and plants point-first
    (stick) or bounces. Returns the toss result (contact = the planting frame)."""
    C = _C()
    C.set_weapon_state("SAINT", frame, "broken")
    M = _snap_world("SAINT_katana_tip_broken", frame)
    ax = (M.to_3x3() @ Vector((0.0, 1.0, 0.0))).normalized()
    v0 = Vector(v0) if v0 is not None else ax * 1.2 + Vector((0.0, 0.0, 3.2))
    spin = Vector(spin) if spin is not None else (M.to_3x3() @ Vector((1.0, 0.0, 0.0))) * 9.0
    return toss("SAINT_katana_tip_broken", frame, p0=M.translation, v0=v0, spin=spin, rot0=M, ground_z=ground_z,
                stick=stick, key_start=False, **kw)


def cut_cord(frame, drift=(0.35, 0.15, 0.05), frames=90, seed="S26", ground_z=0.0, **kw):
    """S26: the vermilion beard cord is cut at `frame`; the light cord drifts away on the air (strong drag
    towards `drift` m/s, weak effective gravity, slow tumble) - slowed by the S25-S26 slow-motion clock."""
    C = _C()
    C.set_beard_cord(frame, True)
    M = _snap_world("SAINT_beard_cord_cut", frame)
    rng = np.random.default_rng(_seed(seed))
    spin = Vector(rng.uniform(-3.0, 3.0, 3).tolist())
    kw.setdefault("gravity", -1.2)
    return toss("SAINT_beard_cord_cut", frame, p0=M.translation, v0=Vector(drift) * 0.5, spin=spin, rot0=M,
                drag=2.5, wind=drift, ground_z=ground_z, f_end=frame + frames, key_start=False, **kw)


def fly_haori(frame, v0=(0.6, -0.3, 1.6), spin=(0.0, 0.0, 2.5), ground_z=0.0, spread=(2, 10), crumple=6, **kw):
    """S14: throw the shed haori. Call AFTER characters.set_costume(frame, haori=False) (which snapshots the
    evaluated coat into SAINT_haori_thrown and snaps it). Rebuilds its spread/crumple keys, tosses it (no settle
    tumble: it lands flat), keys 'spread' 0 -> 1 over frames spread=(a, b) after the throw and 'crumple' 0 -> 1
    over `crumple` frames after landing. Returns the toss result."""
    ob = _obj("SAINT_haori_thrown")
    cloth_shapes(ob)
    M = ob.matrix_world.copy()
    res = toss(ob, frame, p0=M.translation, v0=v0, spin=spin, rot0=M, ground_z=ground_z, key_start=False,
               restitution=0.05, friction=0.8, settle=True, settle_frames=6, **kw)
    key_shape(ob, "spread", frame, 0.0)
    key_shape(ob, "spread", frame + spread[0], 0.25)
    key_shape(ob, "spread", frame + spread[1], 1.0)
    key_shape(ob, "crumple", frame, 0.0)
    land = res["contact"] or (frame + spread[1] + 4)
    key_shape(ob, "crumple", land, 0.0)
    key_shape(ob, "crumple", land + crumple, 0.85)
    key_shape(ob, "spread", land + crumple, 0.3)
    return res


def throw_kunai(i, frame, target, speed=18.0, stick=True, ground_z=0.0, **kw):
    """Throw SHINOBI_kunai_<i> from his left fist at `frame` towards world `target` (point first, a little
    spin about its axis). Deflections are keyed by the lane with a second toss from the contact frame."""
    nm = f"SHINOBI_kunai_{i}"
    M = _snap_world(nm, frame)
    p0 = M.translation
    d = (Vector(target) - p0)
    T = d.length / speed
    v0 = d / max(T, 1e-3) - Vector((0.0, 0.0, GRAVITY)) * (T * 0.5)
    rot = v0.normalized().to_track_quat('Y', 'Z')
    ax = v0.normalized()
    return toss(nm, frame, p0=p0, v0=v0, spin=ax * 20.0, rot0=rot, stick=stick, ground_z=ground_z,
                key_start=False, **kw)
