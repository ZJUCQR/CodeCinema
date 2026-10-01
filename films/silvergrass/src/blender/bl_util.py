"""
bl_util.py - verified Blender 5.2.2 helpers for the Duel in the Silver Grass pipeline.

The underlying
API behaviour (and the gotchas these helpers work around) is documented in
the Blender 5.2 Python API.

Dependencies: bpy, mathutils, numpy (+ bpy_extras, which ships with Blender). The only project imports are
fxclock (lazily, via film_clock(), used by gn_ballistic - Pipeline rule 4) and config (lazily, for defaults).

Path bootstrap - paste at the top of every Blender entry script:

    import sys, os; ROOT = os.environ.get("SILVERGRASS_ROOT") or <repo root>   # see any module header
    for p in (os.path.join(ROOT, "src", "common"), os.path.join(ROOT, "src", "blender")):
        sys.path.insert(0, p) if p not in sys.path else None
    import config, bl_util as U

Index
  scene/objects : clear_scene, ensure_collection, link_to, new_object, new_empty, mesh_from_data,
                  add_attribute, load_font, srgb_to_linear
  animation     : channelbag_of, fcurves_of, fcurve, key, key_eased, set_interp, set_key_interp_at,
                  key_visible, visible_between, delete_keys, freeze_handles, add_noise, ease
  transforms    : look_at_quat, look_at_euler, frame_set, world_matrix_of, world_pos_of, sample_positions,
                  muted_modifiers
  rigs          : build_armature, parent_to_bone, add_ik, key_bone_rot
  materials     : new_material, set_principled, principled_of, emission_material, attribute_node
  nodes         : socket_in, socket_out, NB + NodeRef (compact node builder), gn_new_tree, gn_modifier,
                  gn_socket_id, gn_input, gn_set, gn_key, gn_path, gn_ballistic, gn_instances, film_clock
  compositor    : comp_new, comp_post_chain, comp_key_flash
  cameras       : new_camera, key_camera, bind_camera_marker, add_shake
  render        : configure_png, render_still, render_frames
"""
import contextlib
import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Euler, Matrix, Quaternion, Vector
from bpy_extras import anim_utils as _au

ROOT = (__import__("os").environ.get("SILVERGRASS_ROOT") or str(next(p for p in __import__("pathlib").Path(__file__).resolve().parents if (p / "src" / "common" / "config.py").is_file())))   # repo root (portable)
def ensure_paths(root=ROOT):
    """Add src/common and src/blender to sys.path (idempotent)."""
    for p in (os.path.join(root, "src", "common"), os.path.join(root, "src", "blender")):
        if p not in sys.path:
            sys.path.insert(0, p)


# =============================================================================================
# scene / objects
# =============================================================================================
def clear_scene(fps=None):
    """Reset to an EMPTY factory scene (fps: config.FPS when None). All previously held bpy references become
    invalid."""
    if fps is None:
        ensure_paths()
        import config
        fps = config.FPS
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.fps = fps
    sc.render.fps_base = 1.0
    return sc


def _collection_in_tree(root, col):
    if root == col:
        return True
    return any(_collection_in_tree(c, col) for c in root.children)


def ensure_collection(name, parent=None, scene=None):
    """Get-or-create collection `name`, linked under `parent` (collection/name) or the scene root."""
    sc = scene or bpy.context.scene
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
    if isinstance(parent, str):
        parent = ensure_collection(parent, scene=sc)
    parent = parent or sc.collection
    if not _collection_in_tree(sc.collection, col):
        parent.children.link(col)
    return col


def link_to(obj, collection, exclusive=True):
    """Link obj into collection (object or name); with exclusive=True unlink it from all others."""
    if isinstance(collection, str):
        collection = ensure_collection(collection)
    if obj.name not in collection.objects:
        collection.objects.link(obj)
    if exclusive:
        for c in list(obj.users_collection):
            if c != collection:
                c.objects.unlink(obj)
    return obj


def new_object(name, data=None, collection=None):
    ob = bpy.data.objects.new(name, data)
    if isinstance(collection, str):
        collection = ensure_collection(collection)
    (collection or bpy.context.scene.collection).objects.link(ob)
    return ob


def new_empty(name, loc=(0, 0, 0), collection=None, display='PLAIN_AXES', size=0.2):
    ob = new_object(name, None, collection)
    ob.empty_display_type = display
    ob.empty_display_size = size
    ob.location = loc
    return ob


def mesh_from_data(name, verts, faces=(), edges=(), collection=None, smooth=False, materials=()):
    """Mesh object from python/numpy data. Points-only (no faces/edges) uses the fast foreach_set path."""
    me = bpy.data.meshes.new(name)
    verts = np.asarray(verts, dtype=np.float32).reshape(-1, 3)
    if len(faces) == 0 and len(edges) == 0:
        me.vertices.add(len(verts))
        me.vertices.foreach_set("co", verts.ravel())
    else:
        me.from_pydata(verts.tolist(), [tuple(e) for e in edges], [tuple(f) for f in faces])
    me.update()
    if smooth and len(me.polygons):
        me.shade_smooth()
    for m in materials:
        me.materials.append(m)
    return new_object(name, me, collection)


_ATTR_KEY = {'FLOAT': 'value', 'INT': 'value', 'BOOLEAN': 'value', 'FLOAT_VECTOR': 'vector',
             'FLOAT_COLOR': 'color', 'FLOAT2': 'vector', 'QUATERNION': 'value'}


def add_attribute(mesh, name, values, type=None, domain='POINT'):
    """Add/overwrite a generic attribute from an array. Type inferred from dtype/shape if None:
    (N,) float->FLOAT, int->INT, bool->BOOLEAN, (N,2)->FLOAT2, (N,3)->FLOAT_VECTOR, (N,4)->FLOAT_COLOR."""
    a = np.asarray(values)
    if type is None:
        if a.dtype == bool:
            type = 'BOOLEAN'
        elif np.issubdtype(a.dtype, np.integer):
            type = 'INT'
        elif a.ndim == 1:
            type = 'FLOAT'
        else:
            type = {2: 'FLOAT2', 3: 'FLOAT_VECTOR', 4: 'FLOAT_COLOR'}[a.shape[1]]
    if name in mesh.attributes:
        mesh.attributes.remove(mesh.attributes[name])
    at = mesh.attributes.new(name, type, domain)
    dt = {'INT': np.int32, 'BOOLEAN': bool}.get(type, np.float32)
    at.data.foreach_set(_ATTR_KEY[type], a.astype(dt).ravel())
    mesh.update()
    return at


def load_font(path):
    """Load a font file (.ttf/.otf/.ttc). For .ttc only the FIRST face is used (e.g. Songti -> 'Songti SC Black')."""
    return bpy.data.fonts.load(path, check_existing=True)


def srgb_to_linear(c):
    """sRGB display value(s) 0..1 -> linear (what Blender colour sockets expect)."""
    def f(x):
        return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4
    return tuple(f(x) for x in c)


# =============================================================================================
# animation (slotted actions, 5.x)
# =============================================================================================
def channelbag_of(id_or_obj):
    """ActionChannelbag of the action slot assigned to this ID (None if not animated)."""
    ad = getattr(id_or_obj, "animation_data", None)
    if ad is None or ad.action is None or ad.action_slot is None:
        return None
    return _au.animdata_get_channelbag_for_assigned_slot(ad)


def fcurves_of(id_or_obj, prefix=None):
    """List of F-curves of the ID's assigned action slot, optionally filtered by data_path prefix.
    Works for any ID: Object, Camera data (lens/dof), Light data, node groups (compositor/GN keys),
    material.node_tree / world.node_tree (shader node values). Object keys do NOT include obj.data keys."""
    cb = channelbag_of(id_or_obj)
    if cb is None:
        return []
    if prefix is None:
        return list(cb.fcurves)
    return [fc for fc in cb.fcurves if fc.data_path.startswith(prefix)]


def fcurve(id_or_obj, data_path, index=0, create=False, group=None):
    """Find (or create with create=True) one F-curve."""
    cb = channelbag_of(id_or_obj)
    fc = cb.fcurves.find(data_path, index=index) if cb is not None else None
    if fc is None and create:
        ad = id_or_obj.animation_data or id_or_obj.animation_data_create()
        if ad.action is None:
            ad.action = bpy.data.actions.new(id_or_obj.name + "Action")
        kw = {"group_name": group} if group else {}
        fc = ad.action.fcurve_ensure_for_datablock(id_or_obj, data_path, index=index, **kw)
    return fc


def _key_at(fc, frame, tol=1e-3):
    """Binary search a keyframe at `frame` (keys are kept sorted by Blender)."""
    kps = fc.keyframe_points
    lo, hi = 0, len(kps) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        x = kps[mid].co.x
        if abs(x - frame) <= tol:
            return kps[mid]
        if x < frame:
            lo = mid + 1
        else:
            hi = mid - 1
    return None


def _split_path(path):
    """'pose.bones["a.b"].rotation_euler' -> ('pose.bones["a.b"]', 'rotation_euler')."""
    depth, quote = 0, None
    for i in range(len(path) - 1, -1, -1):
        ch = path[i]
        if quote:
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
        elif ch == "]":
            depth += 1
        elif ch == "[":
            depth -= 1
        elif ch == "." and depth == 0:
            return path[:i], path[i + 1:]
    return "", path


def _set_path_value(id_or_obj, data_path, value, index=-1):
    owner_path, prop = _split_path(data_path)
    owner = id_or_obj.path_resolve(owner_path) if owner_path else id_or_obj
    if prop.startswith('["') and prop.endswith('"]'):          # custom property: '["wetness"]'
        name = prop[2:-2]
        if index is None or index < 0:
            owner[name] = value
        else:
            owner[name][index] = value
        return
    if index is None or index < 0:
        setattr(owner, prop, value)
    else:
        arr = getattr(owner, prop)
        arr[index] = value


def _path_len(id_or_obj, data_path):
    v = id_or_obj.path_resolve(data_path)
    if isinstance(v, str):
        return 1
    try:
        return len(v)
    except TypeError:
        return 1


def _style_key(k, interp=None, easing=None, handles=None):
    if interp:
        k.interpolation = interp
    if easing:
        k.easing = easing
    if handles:
        k.handle_left_type = handles
        k.handle_right_type = handles


def key(id_or_obj, data_path, frame, value=None, index=-1, interp='BEZIER', easing=None, handles=None,
        group=None):
    """Set `value` (optional) at `data_path` and insert keyframe(s) at `frame`.

    ALWAYS sets interpolation (and optional easing / handle type) on the inserted keys, because in 5.2 a new
    key silently copies a non-Bezier interpolation (CONSTANT/LINEAR/...) from the previous key (or the
    next key when inserted before the first).  data_path may be nested:
        key(rig, 'pose.bones["hand.R"].rotation_euler', 12, (0, 0.3, 0))
        key(obj, 'modifiers["GN"].properties.inputs.Socket_2.value', 30, 1.0)
        key(obj, '["wetness"]', 40, 0.8)                         # custom property (create it first: obj["wetness"] = 0.0)
    id_or_obj may also be a non-ID struct (PoseBone, node socket, constraint, modifier input struct): the path is
    re-rooted at its ID via path_from_id, e.g. key(rig.pose.bones["hand.R"], "location", 5, (0, 0, 0.1)).
    Returns the list of keyframes it touched."""
    if not isinstance(id_or_obj, bpy.types.ID):
        data_path = id_or_obj.path_from_id(data_path)
        id_or_obj = id_or_obj.id_data
    if value is not None:
        _set_path_value(id_or_obj, data_path, value, index)
    kw = {"index": index, "frame": frame}
    if group:
        kw["group"] = group
    if not id_or_obj.keyframe_insert(data_path, **kw):
        raise RuntimeError(f"keyframe_insert failed: {id_or_obj.name} {data_path}[{index}] @ {frame}")
    cb = channelbag_of(id_or_obj)
    idxs = [index] if (index is not None and index >= 0) else range(_path_len(id_or_obj, data_path))
    touched = []
    for i in idxs:
        fc = cb.fcurves.find(data_path, index=i)
        if fc is None:
            continue
        k = _key_at(fc, frame)
        if k is not None:
            _style_key(k, interp, easing, handles)
            touched.append(k)
    return touched


def ease(t, kind="inout_cubic"):
    """Easing curves on t in [0,1] (clamped). kinds: linear, smooth(step), smoother,
    in/out/inout _quad _cubic _expo _back, back (=out_back), snap (very fast attack, soft landing),
    hold (0 until t>=1)."""
    t = min(1.0, max(0.0, float(t)))
    c1 = 1.70158
    c3 = c1 + 1.0
    c2 = c1 * 1.525
    if kind == "linear":
        return t
    if kind == "smooth":
        return t * t * (3 - 2 * t)
    if kind == "smoother":
        return t * t * t * (t * (t * 6 - 15) + 10)
    if kind == "in_quad":
        return t * t
    if kind == "out_quad":
        return 1 - (1 - t) ** 2
    if kind == "inout_quad":
        return 2 * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 2 / 2
    if kind == "in_cubic":
        return t ** 3
    if kind == "out_cubic":
        return 1 - (1 - t) ** 3
    if kind == "inout_cubic":
        return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2
    if kind == "in_expo":
        return 0.0 if t == 0 else 2 ** (10 * t - 10)
    if kind == "out_expo":
        return 1.0 if t == 1 else 1 - 2 ** (-10 * t)
    if kind == "inout_expo":
        if t in (0.0, 1.0):
            return t
        return 2 ** (20 * t - 10) / 2 if t < 0.5 else (2 - 2 ** (-20 * t + 10)) / 2
    if kind == "in_back":
        return c3 * t ** 3 - c1 * t * t
    if kind in ("out_back", "back"):
        return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2
    if kind == "inout_back":
        if t < 0.5:
            return ((2 * t) ** 2 * ((c2 + 1) * 2 * t - c2)) / 2
        return ((2 * t - 2) ** 2 * ((c2 + 1) * (t * 2 - 2) + c2) + 2) / 2
    if kind == "snap":
        return 1 - (1 - t) ** 6
    if kind == "hold":
        return 1.0 if t >= 1.0 else 0.0
    raise ValueError(f"unknown ease kind {kind!r}")


def key_eased(id_or_obj, data_path, f0, f1, v0, v1, kind="inout_cubic", step=1, index=-1):
    """Bake an eased transition v0->v1 over [f0,f1] as LINEAR keys every `step` frames (deterministic custom
    easing for camera moves etc.). v0/v1 scalars or sequences. Returns number of keys per channel."""
    v0 = np.atleast_1d(np.asarray(v0, dtype=float))
    v1 = np.atleast_1d(np.asarray(v1, dtype=float))
    frames = list(range(int(f0), int(f1), max(1, int(step)))) + [int(f1)]
    for f in frames:
        u = ease((f - f0) / max(1e-9, (f1 - f0)), kind)
        v = v0 + (v1 - v0) * u
        val = float(v[0]) if v.size == 1 else tuple(float(x) for x in v)
        key(id_or_obj, data_path, f, val, index=index, interp='LINEAR')
    return len(frames)


def set_interp(obj, data_path_prefix=None, interp='BEZIER', easing=None, frame_range=None, handles=None):
    """Set interpolation (+easing/handles) on all keys of obj (optionally only F-curves whose data_path
    starts with prefix, and only keys with frame in [f0, f1] inclusive). Returns count."""
    n = 0
    for fc in fcurves_of(obj, data_path_prefix):
        changed = False
        for k in fc.keyframe_points:
            if frame_range is not None and not (frame_range[0] - 1e-3 <= k.co.x <= frame_range[1] + 1e-3):
                continue
            _style_key(k, interp, easing, handles)
            n += 1
            changed = True
        if changed:
            fc.update()
    return n


def set_key_interp_at(obj, frame, interp, data_path_prefix=None, easing=None):
    """Set interpolation of every key exactly at `frame` (e.g. CONSTANT on a shot's last key)."""
    n = 0
    for fc in fcurves_of(obj, data_path_prefix):
        k = _key_at(fc, frame)
        if k is not None:
            _style_key(k, interp, easing)
            n += 1
    return n


def key_visible(obj, frame, visible):
    """Key hide_render AND hide_viewport (CONSTANT) at frame. Remember F-curve extrapolation: the first key's
    state also applies to all earlier frames -> key the initial state explicitly (see visible_between)."""
    obj.hide_render = not visible
    obj.hide_viewport = not visible
    key(obj, "hide_render", frame, interp='CONSTANT')
    key(obj, "hide_viewport", frame, interp='CONSTANT')


def visible_between(obj, f0, f1, frame_start=1):
    """Hidden before f0, visible f0..f1 (inclusive), hidden from f1+1 on."""
    if f0 > frame_start:
        key_visible(obj, frame_start, False)
    key_visible(obj, f0, True)
    key_visible(obj, f1 + 1, False)


def delete_keys(obj, frame_range, data_path_prefix=None):
    """Remove keys with frame in [f0, f1] (inclusive). Returns number removed."""
    n = 0
    f0, f1 = frame_range
    for fc in fcurves_of(obj, data_path_prefix):
        kps = fc.keyframe_points
        idx = [i for i, k in enumerate(kps) if f0 - 1e-3 <= k.co.x <= f1 + 1e-3]
        for i in reversed(idx):
            kps.remove(kps[i], fast=True)
        if idx:
            fc.update()
        n += len(idx)
    return n


def freeze_handles(obj, frame_range=None, data_path_prefix=None):
    """Convert AUTO/AUTO_CLAMPED/VECTOR handles of keys (in range) to FREE at their current positions, so keys
    added later by OTHER scripts next to this range can no longer change this range's curve shape.
    Call at the end of a lane, after all its keys exist."""
    n = 0
    for fc in fcurves_of(obj, data_path_prefix):
        fc.update()   # make sure auto handles are current
        for k in fc.keyframe_points:
            if frame_range is not None and not (frame_range[0] - 1e-3 <= k.co.x <= frame_range[1] + 1e-3):
                continue
            hl, hr = tuple(k.handle_left), tuple(k.handle_right)
            k.handle_left_type = 'FREE'
            k.handle_right_type = 'FREE'
            k.handle_left, k.handle_right = hl, hr
            n += 1
    return n


def add_noise(id_or_obj, data_path, index, strength, scale=3.0, frame_range=None, blend=0.0, phase=None,
              offset=0.0, blend_type='REPLACE'):
    """F-curve NOISE modifier (REPLACE = centred on the curve; peak ~= +-0.33*strength, std ~= 0.1*strength).
    Ensures the F-curve has a key (a NOISE modifier on a key-less F-curve is ignored). frame_range restricts it
    with blend in/out frames. Multiple calls stack (one modifier each)."""
    fc = fcurve(id_or_obj, data_path, index)
    if fc is None or len(fc.keyframe_points) == 0:
        f = frame_range[0] if frame_range else bpy.context.scene.frame_current
        key(id_or_obj, data_path, f, index=index, interp='BEZIER')
        fc = fcurve(id_or_obj, data_path, index)
    m = fc.modifiers.new('NOISE')
    m.blend_type = blend_type
    m.strength = strength
    m.scale = scale
    m.offset = offset
    m.phase = phase if phase is not None else (index * 17.13 + len(fc.modifiers) * 3.7)
    if frame_range is not None:
        m.use_restricted_range = True
        m.frame_start, m.frame_end = float(frame_range[0]), float(frame_range[1])
        m.blend_in = m.blend_out = float(blend)
    return m


# =============================================================================================
# transforms / evaluation
# =============================================================================================
def look_at_quat(from_xyz, to_xyz, roll=0.0):
    """Quaternion orienting a camera/light (-Z forward, +Y up, world Z up) from->to; roll in radians."""
    d = Vector(to_xyz) - Vector(from_xyz)
    q = d.to_track_quat('-Z', 'Y')
    if roll:
        q = q @ Quaternion((0.0, 0.0, 1.0), roll)
    return q


def look_at_euler(from_xyz, to_xyz, roll=0.0, compat=None):
    """Euler (XYZ) version of look_at_quat. Pass compat=<previous Euler> when keying a sequence to avoid
    +-360 degree flips between keys."""
    q = look_at_quat(from_xyz, to_xyz, roll)
    return q.to_euler('XYZ', compat) if compat is not None else q.to_euler('XYZ')


def frame_set(frame, scene=None):
    """scene.frame_set with float support (subframe)."""
    sc = scene or bpy.context.scene
    fi = int(math.floor(frame))
    sc.frame_set(fi, subframe=float(frame) - fi)


def _is_bone_target(target):
    return isinstance(target, (tuple, list)) and len(target) == 2 and isinstance(target[1], str)


def _manual_world(ob):
    """World matrix rebuilt from (animated) matrix_basis + parent chain. Used for objects whose
    hide_viewport is True: those are NOT in the depsgraph, so their matrix_world is stale after frame_set.
    (Constraints on such hidden objects are ignored.)"""
    M = ob.matrix_basis.copy()
    if ob.parent is None:
        return M
    par = ob.parent
    P = _manual_world(par) if par.hide_viewport else par.matrix_world.copy()
    if ob.parent_type == 'BONE' and ob.parent_bone:
        pb = par.pose.bones[ob.parent_bone]
        P = P @ pb.matrix @ Matrix.Translation((0.0, pb.bone.length, 0.0))
    return P @ ob.matrix_parent_inverse @ M


def world_matrix_of(target, frame=None, scene=None):
    """Evaluated world matrix of an object or (rig, bone_name) (bone: head at the matrix translation).
    Viewport-hidden objects (hide_viewport=True at that frame) are handled via _manual_world."""
    if frame is not None:
        frame_set(frame, scene)
    if _is_bone_target(target):
        rig, bone = target
        return rig.matrix_world @ rig.pose.bones[bone].matrix
    if target.hide_viewport:
        return _manual_world(target)
    dg = bpy.context.evaluated_depsgraph_get()
    return target.evaluated_get(dg).matrix_world.copy()


def world_pos_of(target, frame=None, where="head", offset=None, scene=None):
    """Evaluated world position of an object or (rig, bone_name) at `frame` (None = current).
    where: 'head' | 'tail' | 'center' (bones); offset: point in the bone's / object's local space."""
    M = world_matrix_of(target, frame, scene)
    if offset is not None:
        return M @ Vector(offset)
    if _is_bone_target(target):
        rig, bone = target
        tail = rig.matrix_world @ rig.pose.bones[bone].tail
        if where == "tail":
            return tail
        if where == "center":
            return (M.translation + tail) * 0.5
    return M.translation.copy()


def sample_positions(targets, frames, where="head", scene=None):
    """{key: np.array(len(frames),3)} for several targets with ONE frame_set per frame.
    targets: dict name->target or list of targets (keys = index)."""
    items = targets.items() if isinstance(targets, dict) else enumerate(targets)
    items = list(items)
    out = {k: np.zeros((len(frames), 3)) for k, _ in items}
    for i, f in enumerate(frames):
        frame_set(f, scene)
        for k, t in items:
            out[k][i] = tuple(world_pos_of(t, None, where))
    return out


@contextlib.contextmanager
def muted_modifiers(objects=None, types=('NODES',)):
    """Temporarily set show_viewport=False on (GN) modifiers -> frame_set gets much cheaper while sampling
    (renders use show_render, unaffected). objects=None -> all objects."""
    saved = []
    for ob in (objects if objects is not None else bpy.data.objects):
        for m in ob.modifiers:
            if m.type in types and m.show_viewport:
                saved.append(m)
                m.show_viewport = False
    try:
        yield saved
    finally:
        for m in saved:
            m.show_viewport = True


# =============================================================================================
# rigs
# =============================================================================================
def build_armature(name, bones, collection=None, location=(0, 0, 0), display='STICK'):
    """bones: iterable of dicts {name, head, tail, parent=None, roll=0.0 (radians), connect=False,
    deform=True}. Creates the rig via edit_bones (headless OK), sets every pose bone rotation_mode='XYZ'."""
    arm = bpy.data.armatures.new(name + "_data")
    arm.display_type = display
    rig = new_object(name, arm, collection)
    rig.location = location
    vl = bpy.context.view_layer
    prev_active = vl.objects.active
    vl.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    try:
        eb = arm.edit_bones
        for b in bones:
            e = eb.new(b["name"])
            e.head = b["head"]
            e.tail = b["tail"]
            e.roll = b.get("roll", 0.0)
            e.use_deform = b.get("deform", True)
        for b in bones:
            if b.get("parent"):
                e = eb[b["name"]]
                e.parent = eb[b["parent"]]
                e.use_connect = b.get("connect", False)
    finally:
        bpy.ops.object.mode_set(mode='OBJECT')
        if prev_active is not None:
            vl.objects.active = prev_active
    for pb in rig.pose.bones:
        pb.rotation_mode = 'XYZ'
    return rig


def parent_to_bone(obj, rig, bone, keep_world=True):
    """Bone-parent obj to rig/bone. NOTE Blender puts bone children at the bone TAIL (parent matrix =
    rig.matrix_world @ pose_bone.matrix @ T(0, length, 0)). keep_world=True preserves obj's current world
    transform (evaluated with the rig's current pose)."""
    bpy.context.view_layer.update()
    W = obj.matrix_world.copy()
    pb = rig.pose.bones[bone]
    obj.parent = rig
    obj.parent_type = 'BONE'
    obj.parent_bone = bone
    if keep_world:
        P = rig.matrix_world @ pb.matrix @ Matrix.Translation((0.0, pb.bone.length, 0.0))
        obj.matrix_parent_inverse = Matrix.Identity(4)
        obj.matrix_basis = P.inverted() @ W
    return obj


def add_ik(rig, bone, target, chain=2, pole=None, pole_angle_deg=-90.0, name="IK", subtarget=""):
    """IK constraint on pose bone `bone`. With a pole target the rest chain MUST be slightly bent
    (a perfectly straight chain + pole fails to reach the target)."""
    c = rig.pose.bones[bone].constraints.new('IK')
    c.name = name
    c.target = target
    if subtarget:
        c.subtarget = subtarget
    c.chain_count = chain
    if pole is not None:
        c.pole_target = pole
        c.pole_angle = math.radians(pole_angle_deg)
    return c


def key_bone_rot(rig, bone, frame, rot_deg, interp='BEZIER', easing=None):
    """Key a pose bone's Euler rotation given in degrees."""
    return key(rig, f'pose.bones["{bone}"].rotation_euler', frame,
               tuple(math.radians(a) for a in rot_deg), interp=interp, easing=easing)


# =============================================================================================
# materials (EEVEE 5.2)
# =============================================================================================
_PRINCIPLED_ALIASES = {
    "base_color": "Base Color", "color": "Base Color", "metallic": "Metallic", "metal": "Metallic",
    "roughness": "Roughness", "rough": "Roughness", "ior": "IOR", "alpha": "Alpha",
    "emission": "Emission Color", "emission_color": "Emission Color", "emission_strength": "Emission Strength",
    "coat": "Coat Weight", "coat_roughness": "Coat Roughness", "sheen": "Sheen Weight", "sheen_tint": "Sheen Tint",
    "sheen_roughness": "Sheen Roughness", "subsurface": "Subsurface Weight", "subsurface_radius": "Subsurface Radius",
    "specular": "Specular IOR Level", "specular_tint": "Specular Tint", "transmission": "Transmission Weight",
    "anisotropic": "Anisotropic", "normal": "Normal",
}


def _rgba(c):
    c = tuple(c)
    return c if len(c) == 4 else (c[0], c[1], c[2], 1.0)


def _set_socket_value(sock, value):
    if sock.type == 'RGBA':
        sock.default_value = _rgba(value)
    else:
        sock.default_value = value


def principled_of(mat):
    for n in mat.node_tree.nodes:
        if n.bl_idname == 'ShaderNodeBsdfPrincipled':
            return n
    return None


def set_principled(mat, **inputs):
    """set_principled(mat, base_color=(..), roughness=.4, emission=(..), emission_strength=3, alpha=.5, coat=1)
    (aliases above; exact socket names also accepted with underscores for spaces)."""
    b = principled_of(mat)
    for k, v in inputs.items():
        name = _PRINCIPLED_ALIASES.get(k, k.replace("_", " "))
        sock = socket_in(b, name)
        if isinstance(v, (bpy.types.NodeSocket,)):
            mat.node_tree.links.new(v, sock)
        else:
            _set_socket_value(sock, v)
    return b


def new_material(name, color=(0.8, 0.8, 0.8), rough=0.5, metal=0.0, emission=None, emission_strength=0.0,
                 alpha=None, blended=False, backface_culling=False):
    """Get-or-create a Principled material (idempotent by name). alpha<1 -> transparent: DITHERED (default,
    correct sorting, noisy at low samples) or BLENDED=True (smooth, sorted per object)."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    nt = mat.node_tree          # 5.x: node tree always exists; use_nodes is deprecated
    b = principled_of(mat)
    if b is None:
        b = nt.nodes.new('ShaderNodeBsdfPrincipled')
        out = next((n for n in nt.nodes if n.bl_idname == 'ShaderNodeOutputMaterial'), None) \
            or nt.nodes.new('ShaderNodeOutputMaterial')
        nt.links.new(b.outputs[0], out.inputs["Surface"])
    set_principled(mat, base_color=color, roughness=rough, metallic=metal)
    if emission is not None:
        set_principled(mat, emission=emission, emission_strength=emission_strength)
    if alpha is not None:
        set_principled(mat, alpha=alpha)
        mat.surface_render_method = 'BLENDED' if blended else 'DITHERED'
    mat.use_backface_culling = backface_culling
    mat.diffuse_color = _rgba(color)          # viewport / workbench colour
    return mat


def emission_material(name, color=(1, 1, 1), strength=1.0, alpha=None, attr_fac=None):
    """Cheap unlit material: Emission (optionally mixed with Transparent by `alpha`, BLENDED).
    attr_fac=(attr_name, 'INSTANCER'|'GEOMETRY') multiplies strength by that attribute's Factor."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    nt = mat.node_tree
    nt.nodes.clear()
    nb = NB(nt)
    out = nb.n('ShaderNodeOutputMaterial')
    em = nb.n('ShaderNodeEmission', Color=_rgba(color), Strength=strength)
    if attr_fac is not None:
        at = attribute_node(mat, attr_fac[0], attr_fac[1])
        nb.link(nb.math('MULTIPLY', at.outputs["Factor"], strength), socket_in(em, "Strength"))
    shader = em
    if alpha is not None:
        tr = nb.n('ShaderNodeBsdfTransparent')
        mix = nb.n('ShaderNodeMixShader')
        nb.link(alpha if isinstance(alpha, bpy.types.NodeSocket) else nb.value(alpha), mix.inputs[0])
        nb.link(tr, mix.inputs[1])
        nb.link(em, mix.inputs[2])
        shader = mix
        mat.surface_render_method = 'BLENDED'
    nb.link(shader, socket_in(out, "Surface"))
    mat.diffuse_color = _rgba(color)
    return mat


def attribute_node(mat_or_tree, name, attribute_type='GEOMETRY'):
    """Shader Attribute node. 'INSTANCER' reads attributes of (unrealized) GN instances,
    'GEOMETRY' reads mesh/point attributes (incl. realized instances), 'OBJECT' reads custom props."""
    nt = mat_or_tree.node_tree if hasattr(mat_or_tree, "node_tree") else mat_or_tree
    a = nt.nodes.new('ShaderNodeAttribute')
    a.attribute_type = attribute_type
    a.attribute_name = name
    return a


# =============================================================================================
# node building (GN / shader / compositor)
# =============================================================================================
def socket_in(node, key):
    """Input socket by identifier (e.g. 'A_Color'), else by name preferring ENABLED sockets, else int index.
    (node.inputs['A'] returns the FIRST socket named 'A', often a disabled one on Mix/Map Range/Random Value.)"""
    if isinstance(key, int):
        return node.inputs[key]
    for s in node.inputs:
        if s.identifier == key:
            return s
    fallback = None
    for s in node.inputs:
        if s.name == key:
            if s.enabled:
                return s
            fallback = fallback or s
    if fallback is not None:
        return fallback
    raise KeyError(f"{node.bl_idname}: no input {key!r}; have {[(s.name, s.identifier) for s in node.inputs]}")


def socket_out(node, key=None):
    """Output socket by identifier/name (enabled preferred); key=None -> first enabled output."""
    if key is None:
        for s in node.outputs:
            if s.enabled:
                return s
        return node.outputs[0]
    if isinstance(key, int):
        return node.outputs[key]
    for s in node.outputs:
        if s.identifier == key:
            return s
    fallback = None
    for s in node.outputs:
        if s.name == key:
            if s.enabled:
                return s
            fallback = fallback or s
    if fallback is not None:
        return fallback
    raise KeyError(f"{node.bl_idname}: no output {key!r}; have {[(s.name, s.identifier) for s in node.outputs]}")


class NodeRef:
    """Thin wrapper: ref['Frame'] -> output socket (for a Group OUTPUT node: its input socket),
    ref.inp('Scale') -> input socket, ref.node -> bpy Node."""
    __slots__ = ("node",)

    def __init__(self, node):
        self.node = node

    def __getitem__(self, key):
        if self.node.bl_idname == 'NodeGroupOutput':
            return socket_in(self.node, key)
        return socket_out(self.node, key)

    def inp(self, key):
        return socket_in(self.node, key)

    def __getattr__(self, name):
        return getattr(self.node, name)

    @property
    def out(self):
        return socket_out(self.node)


def _as_node(x):
    return x.node if isinstance(x, NodeRef) else x


class NB:
    """Compact node-tree builder for GeometryNodeTree / CompositorNodeTree node groups and material/world
    node trees.

        ng = gn_new_tree("GN_demo", inputs=[("Height", "FLOAT", 1.0)])
        nb = NB(ng)                                   # nb.gi / nb.go: Group Input / Output nodes
        t  = nb.n('GeometryNodeInputSceneTime')       # -> NodeRef; t['Frame'] is an output socket
        z  = nb.math('MULTIPLY', t['Seconds'], nb.gi['Height'])
        sp = nb.n('GeometryNodeSetPosition', nb.gi['Geometry'], Offset=nb.xyz(0, 0, z))
        nb.link(sp, nb.go['Geometry'])

    n(bl_idname, *positional, **kw): kw that are node RNA properties (data_type, operation, domain, mode, ...)
    are applied FIRST (they rebuild dynamic sockets), then positional values map onto ENABLED inputs in order
    (all remaining positionals go into a multi-input socket such as Join Geometry), then keyword inputs by
    identifier/name (underscores = spaces, e.g. Start_Location=...). A value may be a NodeSocket, NodeRef/Node
    (first enabled output), None (skip) or a constant."""

    def __init__(self, tree, group_io=True):
        self.tree = tree
        self.nodes = tree.nodes
        self.links = tree.links
        self._count = len(self.nodes)
        self.gi = self.go = None
        if group_io and getattr(tree, "bl_idname", "") in ("GeometryNodeTree", "CompositorNodeTree"):
            gi = next((n for n in self.nodes if n.bl_idname == 'NodeGroupInput'), None)
            go = next((n for n in self.nodes if n.bl_idname == 'NodeGroupOutput'), None)
            self.gi = NodeRef(gi or self._place(self.nodes.new('NodeGroupInput')))
            self.go = NodeRef(go or self._place(self.nodes.new('NodeGroupOutput')))
            self.go.node.location.x = 3000

    # ---- core
    def _place(self, node):
        i = self._count
        self._count += 1
        node.location = (200 * (i % 14), -220 * (i // 14))
        return node

    def link(self, src, dst):
        """src: NodeSocket | NodeRef | Node ; dst: NodeSocket | NodeRef | Node (first enabled input)."""
        if not isinstance(src, bpy.types.NodeSocket):
            src = socket_out(_as_node(src))
        if not isinstance(dst, bpy.types.NodeSocket):
            dn = _as_node(dst)
            dst = next(s for s in dn.inputs if s.enabled)
        return self.links.new(src, dst)

    def set(self, sock, value):
        if value is None:
            return
        if isinstance(value, (bpy.types.NodeSocket, NodeRef, bpy.types.Node)):
            self.link(value, sock)
        else:
            _set_socket_value(sock, value)

    def n(self, bl_idname, *args, name=None, label=None, **kw):
        node = self._place(self.nodes.new(bl_idname))
        if name:
            node.name = name
        if label:
            node.label = label
        props = node.bl_rna.properties
        for k in list(kw):
            if k in props and not props[k].is_readonly:
                setattr(node, k, kw.pop(k))
        if args:
            ins = [s for s in node.inputs if s.enabled]
            j = 0
            for a in args:
                if j >= len(ins):
                    raise IndexError(f"{bl_idname}: too many positional inputs")
                s = ins[j]
                self.set(s, a)
                if not s.is_multi_input:
                    j += 1
        for k, v in kw.items():
            try:
                s = socket_in(node, k)
            except KeyError:
                s = socket_in(node, k.replace("_", " "))
            self.set(s, v)
        return NodeRef(node)

    def find(self, bl_idname):
        n = next((n for n in self.nodes if n.bl_idname == bl_idname), None)
        return NodeRef(n) if n else None

    # ---- shortcuts (return OUTPUT SOCKETS unless noted)
    def value(self, v):
        r = self.n('ShaderNodeValue')
        r.node.outputs[0].default_value = v
        return r.node.outputs[0]

    def math(self, op, a, b=None, c=None, clamp=False):
        r = self.n('ShaderNodeMath', operation=op, use_clamp=clamp)
        ins = [s for s in r.node.inputs if s.enabled]
        for s, v in zip(ins, (a, b, c)):
            self.set(s, v)
        return r.node.outputs[0]

    def vmath(self, op, a, b=None, c=None, scale=None):
        r = self.n('ShaderNodeVectorMath', operation=op)
        vec_ins = [s for s in r.node.inputs if s.enabled and s.type == 'VECTOR']
        for s, v in zip(vec_ins, (a, b, c)):
            self.set(s, v)
        if scale is not None:
            self.set(socket_in(r.node, "Scale"), scale)
        return socket_out(r.node, "Value" if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else "Vector")

    def cmp(self, op, a, b, data_type='FLOAT'):
        r = self.n('FunctionNodeCompare', data_type=data_type, operation=op)
        self.set(socket_in(r.node, "A"), a)
        self.set(socket_in(r.node, "B"), b)
        return socket_out(r.node, "Result")

    def bmath(self, op, a, b=None):
        r = self.n('FunctionNodeBooleanMath', operation=op)
        ins = [s for s in r.node.inputs if s.enabled]
        for s, v in zip(ins, (a, b)):
            self.set(s, v)
        return r.node.outputs[0]

    def xyz(self, x=0.0, y=0.0, z=0.0):
        return self.n('ShaderNodeCombineXYZ', x, y, z).node.outputs[0]

    def sep(self, v):
        """-> NodeRef with outputs X, Y, Z."""
        return self.n('ShaderNodeSeparateXYZ', v)

    def map_range(self, v, fmin, fmax, tmin=0.0, tmax=1.0, clamp=True, interp='LINEAR'):
        r = self.n('ShaderNodeMapRange', data_type='FLOAT', interpolation_type=interp, clamp=clamp)
        for k, val in (("Value", v), ("From Min", fmin), ("From Max", fmax), ("To Min", tmin), ("To Max", tmax)):
            self.set(socket_in(r.node, k), val)
        return socket_out(r.node, "Result")

    def mix(self, fac, a, b, data_type='FLOAT', blend='MIX', clamp=False):
        suffix = {'FLOAT': 'Float', 'VECTOR': 'Vector', 'RGBA': 'Color', 'ROTATION': 'Rotation'}[data_type]
        r = self.n('ShaderNodeMix', data_type=data_type, blend_type=blend, clamp_result=clamp)
        self.set(socket_in(r.node, "Factor_Float"), fac)
        self.set(socket_in(r.node, "A_" + suffix), a)
        self.set(socket_in(r.node, "B_" + suffix), b)
        return socket_out(r.node, "Result_" + suffix)

    def switch(self, cond, if_false, if_true, input_type='FLOAT'):
        r = self.n('GeometryNodeSwitch', input_type=input_type)
        self.set(socket_in(r.node, "Switch"), cond)
        self.set(socket_in(r.node, "False"), if_false)
        self.set(socket_in(r.node, "True"), if_true)
        return socket_out(r.node, "Output")

    def attr(self, name, data_type='FLOAT'):
        """GN Named Attribute -> 'Attribute' output socket."""
        r = self.n('GeometryNodeInputNamedAttribute', data_type=data_type)
        socket_in(r.node, "Name").default_value = name
        return socket_out(r.node, "Attribute")

    def store(self, geo, name, value, data_type='FLOAT', domain='POINT'):
        r = self.n('GeometryNodeStoreNamedAttribute', data_type=data_type, domain=domain)
        self.set(socket_in(r.node, "Geometry"), geo)
        socket_in(r.node, "Name").default_value = name
        self.set(socket_in(r.node, "Value"), value)
        return socket_out(r.node, "Geometry")

    def rand(self, data_type='FLOAT', lo=0.0, hi=1.0, seed=0, id=None, probability=None):
        r = self.n('FunctionNodeRandomValue', data_type=data_type)
        if data_type == 'BOOLEAN':
            self.set(socket_in(r.node, "Probability"), 0.5 if probability is None else probability)
        else:
            self.set(socket_in(r.node, "Min"), lo)
            self.set(socket_in(r.node, "Max"), hi)
        self.set(socket_in(r.node, "Seed"), seed)
        if id is not None:
            self.set(socket_in(r.node, "ID"), id)
        return socket_out(r.node, "Value")

    def time(self):
        """GN Scene Time NodeRef (outputs 'Seconds', 'Frame'); compositor trees use CompositorNodeSceneTime."""
        if self.tree.bl_idname == "CompositorNodeTree":
            return self.n('CompositorNodeSceneTime')
        return self.n('GeometryNodeInputSceneTime')

    def noise(self, vector=None, w=None, scale=5.0, detail=2.0, roughness=0.5, dims='3D'):
        """Noise Texture NodeRef (outputs 'Fac' (named Factor) and 'Color'). dims '4D' enables W."""
        r = self.n('ShaderNodeTexNoise', noise_dimensions=dims)
        self.set(socket_in(r.node, "Vector"), vector)
        if w is not None:
            self.set(socket_in(r.node, "W"), w)
        self.set(socket_in(r.node, "Scale"), scale)
        self.set(socket_in(r.node, "Detail"), detail)
        self.set(socket_in(r.node, "Roughness"), roughness)
        return r

    def menu(self, node, name, value):
        """Set a MENU input socket (5.x compositor/GN options such as Glare 'Type' = 'Bloom')."""
        socket_in(_as_node(node), name).default_value = value

    def layout(self, dx=220, dy=180):
        """Arrange nodes left->right by link depth (only for readability in the GUI)."""
        depth = {n.name: 0 for n in self.nodes}
        for _ in range(len(self.nodes)):
            changed = False
            for l in self.links:
                a, b = l.from_node.name, l.to_node.name
                if depth[b] < depth[a] + 1:
                    depth[b] = depth[a] + 1
                    changed = True
            if not changed:
                break
        rows = {}
        for n in self.nodes:
            d = depth[n.name]
            n.location = (d * dx, -rows.get(d, 0) * dy)
            rows[d] = rows.get(d, 0) + 1


_SOCKET_TYPES = {
    'GEOMETRY': 'NodeSocketGeometry', 'FLOAT': 'NodeSocketFloat', 'INT': 'NodeSocketInt',
    'BOOL': 'NodeSocketBool', 'BOOLEAN': 'NodeSocketBool', 'VECTOR': 'NodeSocketVector',
    'COLOR': 'NodeSocketColor', 'RGBA': 'NodeSocketColor', 'OBJECT': 'NodeSocketObject',
    'COLLECTION': 'NodeSocketCollection', 'MATERIAL': 'NodeSocketMaterial', 'STRING': 'NodeSocketString',
    'ROTATION': 'NodeSocketRotation', 'MATRIX': 'NodeSocketMatrix', 'IMAGE': 'NodeSocketImage',
}


def gn_new_tree(name, inputs=(), outputs=(), geometry=True):
    """New GeometryNodeTree (is_modifier=True). geometry=True adds 'Geometry' in+out sockets first.
    inputs/outputs: tuples (name, TYPE[, default[, min, max]]) with TYPE in FLOAT INT BOOL VECTOR COLOR OBJECT
    COLLECTION MATERIAL STRING ROTATION MATRIX IMAGE GEOMETRY. Modifier-side identifiers are 'Socket_<n>' in
    creation order (outputs consume numbers too) - look them up with gn_socket_id()."""
    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    ng.is_modifier = True
    itf = ng.interface
    if geometry:
        itf.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
        itf.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    for spec in inputs:
        s = itf.new_socket(spec[0], in_out='INPUT', socket_type=_SOCKET_TYPES[spec[1].upper()])
        if len(spec) > 2 and spec[2] is not None:
            s.default_value = _rgba(spec[2]) if spec[1].upper() in ('COLOR', 'RGBA') else spec[2]
        if len(spec) > 4:
            s.min_value, s.max_value = spec[3], spec[4]
    for spec in outputs:
        itf.new_socket(spec[0], in_out='OUTPUT', socket_type=_SOCKET_TYPES[spec[1].upper()])
    return ng


def gn_socket_id(ng_or_mod, name):
    """Interface input socket identifier ('Socket_3') for the input called `name`."""
    ng = ng_or_mod.node_group if isinstance(ng_or_mod, bpy.types.NodesModifier) else ng_or_mod
    for it in ng.interface.items_tree:
        if it.item_type == 'SOCKET' and it.in_out == 'INPUT' and it.name == name:
            return it.identifier
    raise KeyError(f"{ng.name}: no input socket {name!r}")


def _gn_mod(obj_or_mod, mod_name="GN"):
    return obj_or_mod if isinstance(obj_or_mod, bpy.types.NodesModifier) else obj_or_mod.modifiers[mod_name]


def gn_input(obj_or_mod, name, mod_name="GN"):
    """The 5.2 modifier input struct (has .value, .type 'VALUE'|'ATTRIBUTE', .attribute_name)."""
    mod = _gn_mod(obj_or_mod, mod_name)
    return getattr(mod.properties.inputs, gn_socket_id(mod, name))


def gn_set(obj_or_mod, name, value, mod_name="GN"):
    """Set a GN modifier input by interface name (5.2: mod.properties.inputs.Socket_N.value)."""
    gn_input(obj_or_mod, name, mod_name).value = value


def gn_path(obj_or_mod, name, mod_name="GN"):
    """F-curve data path of a modifier input: 'modifiers["GN"].properties.inputs.Socket_N.value'."""
    mod = _gn_mod(obj_or_mod, mod_name)
    return f'modifiers["{mod.name}"].properties.inputs.{gn_socket_id(mod, name)}.value'


def gn_key(obj, name, frame, value=None, interp='BEZIER', mod_name="GN", index=-1):
    """Keyframe a GN modifier input (value optional). Returns the data path."""
    path = gn_path(obj, name, mod_name)
    key(obj, path, frame, value, index=index, interp=interp)
    return path


def gn_modifier(obj, ng, name="GN", **inputs):
    """Add a Nodes modifier with node group ng and set inputs by interface name (underscores = spaces)."""
    mod = obj.modifiers.new(name, 'NODES')
    mod.node_group = ng
    for k, v in inputs.items():
        try:
            gn_set(mod, k, v)
        except KeyError:
            gn_set(mod, k.replace("_", " "), v)
    return mod


def _is_zero_scale(m, eps=1e-9):
    """True when a 4x4 matrix has (numerically) zero scale on some axis - a hidden slot of a fixed pool."""
    return min(m.col[0].xyz.length, m.col[1].xyz.length, m.col[2].xyz.length) < eps


def gn_instances(obj, frame=None, include_hidden=False):
    """[(matrix_world copy, persistent_id tuple, random_id)] of the evaluated instances generated by obj.
    Fixed-count pools (Pipeline rule 3) keep dead/unborn slots as ZERO-SCALE instances: those are skipped
    unless include_hidden=True (then every slot of the pool is returned, e.g. to check the count is constant).
    (DepsgraphObjectInstance refs are only valid inside the iteration - values are copied here.)"""
    if frame is not None:
        frame_set(frame)
    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    for inst in dg.object_instances:
        if inst.is_instance and inst.parent is not None and inst.parent.original == obj:
            m = inst.matrix_world.copy()
            if include_hidden or not _is_zero_scale(m):
                out.append((m, tuple(inst.persistent_id), inst.random_id))
    return out


def film_clock(scene=None):
    """The film effects clock module (src/blender/fxclock.py), imported lazily (with config, bl_util's only
    project imports; Pipeline rule 4: time-driven effects read scene["fx_time"], never Scene Time). Makes sure the
    scene carries the fx_time curve (fxclock.ensure_clock when missing; the clock is derived from config only,
    so building it early is harmless and build_scene may rebuild it). Returns the fxclock module."""
    ensure_paths()
    import fxclock
    sc = scene or bpy.context.scene
    if fxclock.PROP not in sc.keys() or fcurve(sc, f'["{fxclock.PROP}"]', 0) is None:
        fxclock.ensure_clock(sc)
    return fxclock


def gn_ballistic(name, p0, vel, birth, life, gravity=-9.81, fps=None, instance=None, material=None, size=1.0,
                 shrink=0.0, stretch=0.0, align=True, collection=None, extra_attrs=None, margin_frames=2.0):
    """Time-driven, bake-free particle POOL (fixed count, film clock; tested incl. motion blur).

    Points carry attributes vel (m/s), birth (frame), life (frames at normal speed), size, plus the clock-space
    copies birth_t = fxclock.fx_time_at(birth) and life_t = life/fps (seconds of fx time). The GN modifier input
    'Time' is driven by scene["fx_time"] (fxclock.drive_gn_input), so slow-motion windows (config.TIME_WARP)
    slow the particles too:
        t = Time - birth_t ;  tc = clamp(t, 0, life_t) ;  pos = p0 + vel*tc + 0.5*g*tc^2  (g on Z, or a 3-vector)
    Pipeline rule 3: the pool never changes size - every point always instances `instance` (object); points
    that are unborn (t < 0) or dead (t > life_t) get SCALE 0 through a Switch (no Delete Geometry), so EEVEE
    motion blur matches instances by index. Live instances are aligned so the object's +Z follows the current
    velocity, scaled by size*(1 - shrink*age01) and stretched along Z by (1 + stretch*|v|). Instance attribute
    'age01' (0..1) is stored for shaders (Attribute node, type INSTANCER); extra_attrs {name: array} are copied
    to points and reach instances too.
    Dormancy: outside [first birth - margin_frames, last death + margin_frames] (converted to fx time) the
    modifier outputs nothing, so idle pools cost ~0; while any slot can be visible the count is constant.
    Returns the object; its modifier 'GN' exposes inputs 'Time' (driven), 'Gravity' (vector), 'Instance',
    'Material', 'Shrink', 'Stretch', 'Active From', 'Active To' (fx seconds). fps: config.FPS when None."""
    fxc = film_clock()
    if fps is None:
        fps = fxc.config.FPS
    p0 = np.asarray(p0, dtype=np.float32).reshape(-1, 3)
    n = len(p0)
    vel = np.broadcast_to(np.asarray(vel, dtype=np.float32), (n, 3))
    birth = np.broadcast_to(np.asarray(birth, dtype=np.float64), (n,))
    life = np.broadcast_to(np.asarray(life, dtype=np.float64), (n,))
    size_a = np.broadcast_to(np.asarray(size, dtype=np.float32), (n,))
    uniq = {float(b): fxc.fx_time_at(float(b)) for b in np.unique(birth)}
    birth_t = np.array([uniq[float(b)] for b in birth], dtype=np.float64)
    life_t = life / float(fps)
    ob = mesh_from_data(name, p0, collection=collection)
    me = ob.data
    add_attribute(me, "vel", vel, 'FLOAT_VECTOR')
    add_attribute(me, "birth", birth.astype(np.float32), 'FLOAT')
    add_attribute(me, "life", life.astype(np.float32), 'FLOAT')
    add_attribute(me, "birth_t", birth_t.astype(np.float32), 'FLOAT')
    add_attribute(me, "life_t", life_t.astype(np.float32), 'FLOAT')
    add_attribute(me, "size", size_a, 'FLOAT')
    for k, v in (extra_attrs or {}).items():
        add_attribute(me, k, v)
    margin = float(margin_frames) / float(fps)
    act_from = float(birth_t.min() - margin) if n else 0.0
    act_to = float((birth_t + life_t).max() + margin) if n else -1.0

    g = (0.0, 0.0, float(gravity)) if np.ndim(gravity) == 0 else tuple(float(x) for x in gravity)
    ng = gn_new_tree("GN_" + name, inputs=[("Time", "FLOAT", 0.0), ("Gravity", "VECTOR", g),
                                           ("Instance", "OBJECT"), ("Material", "MATERIAL"),
                                           ("Shrink", "FLOAT", float(shrink)), ("Stretch", "FLOAT", float(stretch)),
                                           ("Active From", "FLOAT", act_from), ("Active To", "FLOAT", act_to)])
    nb = NB(ng)
    gi = nb.gi
    eps = 1e-4                                  # ~0.0024 frames: bounds are inclusive despite float32 time
    life_s = nb.attr("life_t")
    t = nb.math('SUBTRACT', gi['Time'], nb.attr("birth_t"))
    tc = nb.math('MINIMUM', nb.math('MAXIMUM', t, 0.0), life_s)
    v = nb.attr("vel", 'FLOAT_VECTOR')
    half_t2 = nb.math('MULTIPLY', nb.math('MULTIPLY', tc, tc), 0.5)
    offset = nb.vmath('ADD', nb.vmath('SCALE', v, scale=tc), nb.vmath('SCALE', gi['Gravity'], scale=half_t2))
    moved = nb.n('GeometryNodeSetPosition', gi['Geometry'], Offset=offset)
    alive = nb.bmath('AND', nb.cmp('GREATER_EQUAL', t, -eps),
                     nb.cmp('LESS_EQUAL', t, nb.math('ADD', life_s, eps)))
    age01 = nb.math('DIVIDE', tc, nb.math('MAXIMUM', life_s, 1e-6))
    v_now = nb.vmath('ADD', v, nb.vmath('SCALE', gi['Gravity'], scale=tc))
    rot = nb.n('FunctionNodeAlignRotationToVector', axis='Z', Vector=v_now)['Rotation'] if align else None
    s_live = nb.math('MULTIPLY', nb.attr("size"),
                     nb.math('SUBTRACT', 1.0, nb.math('MULTIPLY', gi['Shrink'], age01)))
    s_uni = nb.switch(alive, 0.0, s_live)                      # fixed pool: dead/unborn -> scale 0
    s_z = nb.math('MULTIPLY', s_uni, nb.math('ADD', 1.0, nb.math('MULTIPLY', gi['Stretch'],
                                                                  nb.vmath('LENGTH', v_now))))
    obj_info = nb.n('GeometryNodeObjectInfo', gi['Instance'], False)
    inst = nb.n('GeometryNodeInstanceOnPoints', Points=moved, Instance=obj_info['Geometry'], Rotation=rot,
                Scale=nb.xyz(s_uni, s_uni, s_z))
    stored = nb.store(inst, "age01", age01, 'FLOAT', 'INSTANCE')
    with_mat = nb.n('GeometryNodeSetMaterial', stored, None, gi['Material'])
    active = nb.bmath('AND', nb.cmp('GREATER_EQUAL', gi['Time'], gi['Active From']),
                      nb.cmp('LESS_EQUAL', gi['Time'], gi['Active To']))
    out = nb.switch(active, None, with_mat, 'GEOMETRY')        # dormant -> empty (single value, lazy)
    nb.link(out, nb.go['Geometry'])
    nb.layout()
    gn_modifier(ob, ng, Instance=instance, Material=material)
    fxc.drive_gn_input(ob, "Time")
    return ob


# =============================================================================================
# compositor (5.2: node group assigned to scene.compositing_node_group, output = Group Output)
# =============================================================================================
def comp_new(scene=None, name="Compositor"):
    """Create + assign a CompositorNodeTree with an 'Image' output socket and a Render Layers node.
    Returns (tree, nb, render_layers_node). Link your last node into nb.go['Image']."""
    sc = scene or bpy.context.scene
    ng = bpy.data.node_groups.new(name, 'CompositorNodeTree')
    ng.interface.new_socket("Image", in_out='OUTPUT', socket_type='NodeSocketColor')
    nb = NB(ng)
    rl = nb.n('CompositorNodeRLayers')
    rl.node.scene = sc
    rl.node.layer = sc.view_layers[0].name
    sc.compositing_node_group = ng
    sc.render.use_compositing = True
    return ng, nb, rl


def comp_post_chain(scene=None, bloom=0.5, bloom_threshold=1.0, bloom_size=0.5, dispersion=0.01,
                    vignette=0.35, grain=0.04, flash_level=16.0):
    """Tested reference chain: RenderLayers -> Glare(Bloom) -> Lens Distortion(dispersion) -> vignette
    (analytic radial falloff from Image Coordinates 'Normalized' -> Map Range SMOOTHSTEP -> Mix MULTIPLY)
    -> film grain (4D White Noise on 'Pixel' coords, W = frame) -> white flash (Mix, factor keyable via
    comp_key_flash) -> Group Output.
    flash_level: linear value of the flash colour (AgX maps linear 1.0 to ~0.77 display; 16 -> ~1.0 white).
    Returns dict of nodes (keys: tree, rl, glare, lens, vignette, grain, flash)."""
    sc = scene or bpy.context.scene
    ng, nb, rl = comp_new(sc)
    img = rl['Image']
    glare = None
    if bloom:
        glare = nb.n('CompositorNodeGlare', img)
        nb.menu(glare, "Type", 'Bloom')
        nb.menu(glare, "Quality", 'Medium')
        glare.inp("Threshold").default_value = bloom_threshold
        glare.inp("Strength").default_value = bloom
        glare.inp("Size").default_value = bloom_size
        img = glare['Image']
    lens = None
    if dispersion:
        lens = nb.n('CompositorNodeLensdist', img, Distortion=0.0, Dispersion=dispersion)
        img = lens['Image']
    vig = None
    if vignette:
        # analytic, resolution-independent (a blurred Ellipse Mask needs a blur size in PIXELS, which changes
        # the look between preview and final resolution): d = |(uv-0.5)*2| (0 centre, 1 edge, 1.41 corner)
        coords = nb.n('CompositorNodeImageCoordinates', rl['Image'])
        d = nb.vmath('LENGTH', nb.vmath('SCALE', nb.vmath('SUBTRACT', coords['Normalized'], (0.5, 0.5, 0.0)),
                                        scale=2.0))
        fac = nb.map_range(d, 0.55, 1.45, 1.0, 1.0 - vignette, clamp=True, interp='SMOOTHSTEP')
        vig = nb.mix(1.0, img, fac, data_type='RGBA', blend='MULTIPLY')
        img = vig
    gr = None
    if grain:
        coords = nb.n('CompositorNodeImageCoordinates', rl['Image'])
        wn = nb.n('ShaderNodeTexWhiteNoise', coords['Pixel'], nb.time()['Frame'], noise_dimensions='4D')
        gr = nb.mix(grain, img, wn['Color'], data_type='RGBA', blend='OVERLAY')
        img = gr
    fl = nb.n('ShaderNodeMix', name="Flash", data_type='RGBA', blend_type='MIX')
    socket_in(fl.node, "Factor_Float").default_value = 0.0
    socket_in(fl.node, "B_Color").default_value = (flash_level, flash_level, flash_level, 1.0)
    nb.link(img, socket_in(fl.node, "A_Color"))
    nb.link(socket_out(fl.node, "Result_Color"), nb.go['Image'])
    nb.layout()
    return dict(tree=ng, rl=rl.node, glare=glare and glare.node, lens=lens and lens.node,
                vignette=vig, grain=gr, flash=fl.node)


def comp_key_flash(frame, amount, scene=None, interp='LINEAR', node_name="Flash"):
    """Key the compositor white-flash factor (0..1) at frame. F-curves live on the compositor node group."""
    sc = scene or bpy.context.scene
    ng = sc.compositing_node_group
    return key(ng, f'nodes["{node_name}"].inputs[0].default_value', frame, float(amount), interp=interp)


# =============================================================================================
# cameras
# =============================================================================================
def new_camera(name, loc=(0, -10, 1.6), look_at=(0, 0, 1.0), lens=35.0, sensor=36.0, clip=(0.05, 2000.0),
               collection=None):
    cam = new_object(name, bpy.data.cameras.new(name), collection)
    cam.data.sensor_fit = 'HORIZONTAL'
    cam.data.sensor_width = sensor
    cam.data.lens = lens
    cam.data.clip_start, cam.data.clip_end = clip
    cam.location = loc
    cam.rotation_mode = 'XYZ'
    cam.rotation_euler = look_at_euler(loc, look_at)
    return cam


def key_camera(cam, frame, loc=None, look_at=None, lens=None, roll_deg=0.0, interp='BEZIER', easing=None):
    """Key camera location / explicit aim rotation (no constraint needed) / lens at frame.
    Rotation keys use Euler compatibility with the current value to avoid flips."""
    if loc is not None:
        key(cam, "location", frame, tuple(loc), interp=interp, easing=easing)
    if look_at is not None:
        src = loc if loc is not None else world_pos_of(cam, frame)
        e = look_at_euler(src, look_at, math.radians(roll_deg), compat=cam.rotation_euler.copy())
        key(cam, "rotation_euler", frame, tuple(e), interp=interp, easing=easing)
    if lens is not None:
        key(cam.data, "lens", frame, float(lens), interp=interp, easing=easing)


def bind_camera_marker(frame, cam, name=None, scene=None):
    """Timeline marker at frame bound to cam (switches the active camera there in renders and frame_set).
    Replaces an existing marker on the same frame."""
    sc = scene or bpy.context.scene
    for m in list(sc.timeline_markers):
        if m.frame == frame:
            sc.timeline_markers.remove(m)
    m = sc.timeline_markers.new(name or f"cam_{frame}", frame=frame)
    m.camera = cam
    return m


def add_shake(obj, f0, f1, amp_deg=1.0, scale=2.5, blend=3, seed=0, axes=(0, 1, 2)):
    """Rotational shake in [f0,f1] (NOISE F-modifiers, REPLACE, restricted range with blend in/out).
    amp_deg ~ peak deviation. If obj has a TRACK_TO / DAMPED_TRACK / LOCKED_TRACK constraint (which would
    override rotation keys), the noise goes onto an empty '<obj>_shake' that is added AFTER the tracking via a
    Copy Rotation constraint (mix_mode AFTER, WORLD/WORLD spaces = shake in camera-local axes).
    Returns the object carrying the noise."""
    tracked = any(c.type in ('TRACK_TO', 'DAMPED_TRACK', 'LOCKED_TRACK') for c in obj.constraints)
    carrier = obj
    if tracked:
        nm = obj.name + "_shake"
        carrier = bpy.data.objects.get(nm)
        if carrier is None:
            carrier = new_empty(nm, (0, 0, 0), obj.users_collection[0] if obj.users_collection else None)
            cr = obj.constraints.new('COPY_ROTATION')
            cr.name = "shake"
            cr.target = carrier
            cr.mix_mode = 'AFTER'
            cr.owner_space = 'WORLD'
            cr.target_space = 'WORLD'
    strength = math.radians(amp_deg) / 0.33
    for i in axes:
        add_noise(carrier, "rotation_euler", i, strength * (0.35 if i == 2 else 1.0), scale=scale,
                  frame_range=(f0, f1), blend=blend, phase=seed * 31.7 + i * 11.3 + f0 * 0.37)
    return carrier


# =============================================================================================
# render
# =============================================================================================
def configure_png(scene=None, rgb=True, depth=None, compression=None):
    """PNG output; depth / compression default to config.FRAME_PNG (settings render.png_*)."""
    if depth is None or compression is None:
        ensure_paths()
        import config
        depth = config.FRAME_PNG["depth"] if depth is None else depth
        compression = config.FRAME_PNG["compression"] if compression is None else compression
    sc = scene or bpy.context.scene
    im = sc.render.image_settings
    im.media_type = 'IMAGE'
    im.file_format = 'PNG'
    im.color_mode = 'RGB' if rgb else 'RGBA'
    im.color_depth = depth
    im.compression = compression
    return im


def _subst_hashes(path, frame):
    """Replace the last run of '#' with the zero-padded frame (write_still does NOT do this)."""
    j = path.rfind("#")
    if j < 0:
        return path
    i = j
    while i > 0 and path[i - 1] == "#":
        i -= 1
    return path[:i] + str(int(frame)).zfill(j - i + 1) + path[j + 1:]


def render_still(filepath, frame=None, scene=None):
    """Render one frame (composited, marker camera honoured) to filepath ('#####' -> frame). Returns seconds."""
    sc = scene or bpy.context.scene
    if frame is not None:
        sc.frame_set(int(frame))
    path = _subst_hashes(bpy.path.abspath(filepath), sc.frame_current)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    sc.render.filepath = path
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    return time.time() - t0


def render_frames(frames, pattern, scene=None, skip_existing=True, log=print):
    """Render explicit frames one by one ('/dir/#####.png' pattern), resumable (skips existing non-empty
    files when skip_existing). Returns {frame: seconds}."""
    sc = scene or bpy.context.scene
    times = {}
    for f in frames:
        path = _subst_hashes(pattern, f)
        if skip_existing and os.path.exists(path) and os.path.getsize(path) > 0:
            continue
        times[f] = render_still(path, f, sc)
        if log:
            log(f"frame {f}: {times[f]:.2f}s -> {path}")
    return times
