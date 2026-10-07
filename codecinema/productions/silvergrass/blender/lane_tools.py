"""
lane_tools.py - lane isolation through the NLA + the machine-wide render lock.

Why: six choreography lanes (acts/<lane>.py) key the SAME rigs, props, cameras, materials and world.  In one
shared action, keys of the next lane change the previous lane's curve through AUTO_CLAMPED handles and any
`set_interp` / F-modifier without a frame range leaks across lanes.  So every lane's keys end up in their own
actions, played by NLA strips:

    begin_lane(lane)          # pre-lane keys (env/characters build) -> BASE track; lane collection active
    <lane>.build(ctx)         # keys normally (bl_util.key ...) -> fresh active actions
    end_lane(lane)            # moves.resolve_clashes(span) then cameras.resolve_pending (own actions still
                              # active), auto-hide of lane-made objects outside the lane, key-range audit (discard
                              # keys outside [s-0.3-6, e+0.7+6]), then every animated ID's action -> strip on
                              # track LANE_<lane> (s-0.3 .. e+0.7, HOLD_FORWARD, REPLACE)
    assemble_nla(lanes)       # BASE (HOLD) at the bottom, lanes chronologically above, '*secondary*' tracks on
                              # top; channels a lane animates but BASE lacks get a BASE key = the value at the
                              # start of the first lane that animates them (= single-action semantics).

Resulting semantics at frame f for a channel c: the latest-starting lane (start <= f) that animates c wins; its
value holds forward after its span until a later lane keys c; before the first lane that animates c the BASE
value applies.  Strip edges sit at s-0.3 / e+0.7 so that motion blur with motion_blur_position='START'
(shutter [f, f+0.5]) never mixes two lanes: frame e samples only lane A, frame e+1 only lane B.

Covered IDs: objects, materials (+ embedded node trees), worlds (+ trees), lights (+ trees), cameras, scenes
(never the scene's ["fx_time"] channel, which stays in the scene's active action - fxclock), node groups
(compositor, GN), meshes, armatures, shape keys (Key), curves, textures, lattices, particles, ...
Tools that read keys after assembly must look inside the strip actions: keys_in_range / live_fcurves.
Lane-made objects (renderable, in LANE_<lane>, no visibility keys/drivers, not ob['persist']) are keyed hidden
outside their lane.  secondary_override(rig, f0, f1, bones) lets a lane's own keys drive secondary-motion bones
over a range (applied by build_scene after characters.apply_secondary_motion: apply_secondary_masks).

render_lock(): file-lock semaphore (procutil.lock_file) with config.RENDER_SLOTS slots in config.LOCK_DIR shared by
every process on the machine; every render (stills included) takes a slot:
`with lane_tools.render_lock(label="act1b still"): U.render_still(...)`.
This module is importable without bpy (the render supervisor imports render_lock from the .venv Python).
"""

from codecinema.productions import film_root, source_root
import contextlib
import json
import math
import os
import sys
import time

try:                                    # render_lock must work outside Blender
    import bpy
except ImportError:                     # pragma: no cover - outside Blender
    bpy = None

ROOT = str(film_root("silvergrass"))
for _p in (os.path.join(str(source_root("silvergrass")), "common"), os.path.join(str(source_root("silvergrass")), "blender")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import config  # noqa: E402
import procutil  # noqa: E402

BASE_TRACK = "BASE"
LANE_PREFIX = "LANE_"
SECONDARY_TAG = "secondary"          # tracks whose name contains this stay on top (Pipeline rule 11)
PRE, POST = 0.3, 0.7                 # strip = [s - PRE, e + POST]
TOLERANCE = config.LANE_KEY_TOLERANCE   # keys up to 6 f beyond the strip edges are kept (curve shape), else deleted
PROTECTED = {"Scene": {'["fx_time"]'}}   # channels never stashed (per ID class name)
LOCK_DIR = config.LOCK_DIR           # settings paths.lock_dir (env SILVERGRASS_PATHS_LOCK_DIR); default <out>/.locks

# every bpy.data collection whose IDs may carry animation_data (missing ones are skipped)
ANIM_COLLECTIONS = ("objects", "scenes", "materials", "worlds", "lights", "cameras", "node_groups", "meshes",
                    "armatures", "shape_keys", "curves", "textures", "lattices", "particles", "speakers",
                    "volumes", "pointclouds", "hair_curves", "grease_pencils", "linestyles", "cache_files",
                    "masks", "movieclips", "metaballs", "lightprobes")
# object types that render (auto-hide of lane objects outside their lane, QA)
RENDERABLE_TYPES = {"MESH", "CURVE", "SURFACE", "META", "FONT", "CURVES", "POINTCLOUD", "VOLUME", "GREASEPENCIL",
                    "LIGHT", "LIGHT_PROBE"}
MODULE_PREFIXES = ("VFX_", "ENV_", "MID_", "CHAR_", "SHINOBI_", "SAINT_")   # objects named by shared modules
AUTO_HIDE_AFTER = 0.6                # lane objects are hidden from e + 0.6 (inside the strip, after the shutter)
EMBEDDED_TREE_OWNERS = ("materials", "worlds", "lights", "textures", "linestyles")

# in-process registry (the NLA itself is the durable record: tracks LANE_<lane>, action["lane"])
_STATE = dict(current=None, spans={}, reports={}, begin_objects=None, begin_markers=None, prev_collection=None,
              base_log=[], order=[])


def _log(msg):
    print(f"[lane_tools] {msg}")


def reset():
    """Forget the in-process lane registry (fresh scene / tests). The NLA data itself is untouched."""
    _STATE.update(current=None, spans={}, reports={}, begin_objects=None, begin_markers=None,
                  prev_collection=None, base_log=[], order=[], secondary_masks=[])


# =============================================================================================
# spans
# =============================================================================================
def lane_span(lane):
    """(start, end) of a lane: registered span (begin_lane(span=...)) or config.lane_span."""
    if lane in _STATE["spans"]:
        return _STATE["spans"][lane]
    return tuple(config.lane_span(lane))


def strip_range(span):
    """NLA strip range [s - 0.3, e + 0.7] for a lane span."""
    s, e = span
    return (float(s) - PRE, float(e) + POST)


def keep_range(span):
    """Keys outside this range are deleted by the audit: [s - 0.3 - 6, e + 0.7 + 6]."""
    a, b = strip_range(span)
    return (a - TOLERANCE, b + TOLERANCE)


# =============================================================================================
# animated IDs / channelbags
# =============================================================================================
def iter_anim_ids(with_nla=False):
    """Yield every ID that has animation_data with an active action (or, with with_nla=True, also those with
    NLA tracks). Includes embedded node trees of materials / worlds / lights / textures."""
    seen = set()
    for coll in ANIM_COLLECTIONS:
        for idb in getattr(bpy.data, coll, ()):
            ad = idb.animation_data
            if ad is not None and (ad.action is not None or (with_nla and len(ad.nla_tracks))):
                if id(idb) not in seen:
                    seen.add(id(idb))
                    yield idb
    for coll in EMBEDDED_TREE_OWNERS:
        for owner in getattr(bpy.data, coll, ()):
            nt = getattr(owner, "node_tree", None)
            if nt is None:
                continue
            ad = nt.animation_data
            if ad is not None and (ad.action is not None or (with_nla and len(ad.nla_tracks))):
                yield nt


def id_label(idb):
    """Human readable 'Type:name' (embedded trees: 'NodeTree:<owner>.node_tree')."""
    owner = getattr(idb, "id_data", idb)
    name = idb.name
    try:
        if idb.is_embedded_data:
            name = f"{_embedded_owner_name(idb)}.node_tree"
    except AttributeError:
        pass
    return f"{type(owner).__name__}:{name}"


def _embedded_owner_name(tree):
    for coll in EMBEDDED_TREE_OWNERS:
        for owner in getattr(bpy.data, coll, ()):
            if getattr(owner, "node_tree", None) == tree:
                return owner.name
    return tree.name


def _protected_paths(idb):
    return PROTECTED.get(type(idb).__name__, set())


def channelbag(action, slot):
    """Channelbag of (action, slot) or None."""
    if action is None or slot is None:
        return None
    from bpy_extras import anim_utils
    return anim_utils.action_get_channelbag_for_slot(action, slot)


def _slot_by_identifier(action, identifier):
    for s in action.slots:
        if s.identifier == identifier:
            return s
    return None


def active_fcurves(idb):
    """F-curves of the ID's active action (assigned slot), [] if none."""
    ad = idb.animation_data
    if ad is None or ad.action is None or ad.action_slot is None:
        return []
    cb = channelbag(ad.action, ad.action_slot)
    return list(cb.fcurves) if cb is not None else []


def _unprotected(idb, fcs):
    prot = _protected_paths(idb)
    return [fc for fc in fcs if fc.data_path not in prot]


def _split_protected(idb):
    """For IDs with protected channels (scene fx_time): move all OTHER channels of the active action into a copy
    and return (copy_action, copy_slot) - the active action keeps only the protected channels.  Returns None when
    there is nothing unprotected.  For other IDs returns (active_action, active_slot)."""
    ad = idb.animation_data
    act, slot = ad.action, ad.action_slot
    fcs = active_fcurves(idb)
    if not _unprotected(idb, fcs):
        return None
    prot = _protected_paths(idb)
    if not prot or not any(fc.data_path in prot for fc in fcs):
        return act, slot
    cp = act.copy()
    cslot = _slot_by_identifier(cp, slot.identifier)
    cb_copy = channelbag(cp, cslot)
    for fc in list(cb_copy.fcurves):
        if fc.data_path in prot:
            cb_copy.fcurves.remove(fc)
    cb_orig = channelbag(act, slot)
    for fc in list(cb_orig.fcurves):
        if fc.data_path not in prot:
            cb_orig.fcurves.remove(fc)
    return cp, cslot


def _new_strip(idb, track_name, action, slot, f0, f1, extrapolation='HOLD_FORWARD', blend='REPLACE',
               prev_track=None):
    """Create a track (on top, or after prev_track) with one strip playing action[slot] 1:1 over [f0, f1]."""
    ad = idb.animation_data or idb.animation_data_create()
    tr = ad.nla_tracks.new(prev=prev_track) if prev_track is not None else ad.nla_tracks.new()
    tr.name = track_name
    st = tr.strips.new(track_name, int(math.floor(f0)), action)
    if slot is not None and st.action_slot != slot:
        st.action_slot = slot
    _set_strip_range(st, f0, f1)
    st.extrapolation = extrapolation
    st.blend_type = blend
    st.influence = 1.0
    return tr, st


def _set_strip_range(st, f0, f1):
    """Play action time == scene time over [f0, f1] (scale 1, no repeat)."""
    st.use_sync_length = False
    st.scale = 1.0
    st.repeat = 1.0
    # widen first so that start < end holds at every intermediate step
    lo, hi = min(st.frame_start, f0), max(st.frame_end, f1)
    st.frame_end = hi
    st.frame_start = lo
    st.action_frame_start = f0
    st.action_frame_end = f1
    st.frame_start = f0
    st.frame_end = f1
    if abs(st.frame_start - f0) > 1e-3 or abs(st.frame_end - f1) > 1e-3 or abs(st.scale - 1.0) > 1e-6 \
            or abs(st.action_frame_start - f0) > 1e-3:
        raise RuntimeError(f"NLA strip range not applied: {st.name} {st.frame_start}-{st.frame_end} "
                           f"action {st.action_frame_start}-{st.action_frame_end} scale {st.scale} (want {f0}-{f1})")
    return st


# =============================================================================================
# BASE (pre-lane keys: environment / characters build)
# =============================================================================================
def _base_range(fcs=()):
    lo = float(config.FRAME_START - 200)
    hi = float(config.FRAME_END + 400)
    for fc in fcs:
        if len(fc.keyframe_points):
            lo = min(lo, fc.keyframe_points[0].co.x - 1.0)
            hi = max(hi, fc.keyframe_points[-1].co.x + 1.0)
    return lo, hi


def _base_track(idb):
    ad = idb.animation_data
    if ad is None:
        return None
    for tr in ad.nla_tracks:
        if tr.name == BASE_TRACK:
            return tr
    return None


def stash_pre_lane_keys(reason="pre-lane"):
    """Move every active action (except protected channels) into the ID's BASE track (bottom, HOLD).
    Called by begin_lane; keys made outside any lane (env.build, characters.build) become the BASE state.
    If a BASE strip already exists, the new channels are merged into its action. Returns #IDs touched."""
    n = 0
    for idb in list(iter_anim_ids()):
        fcs = _unprotected(idb, active_fcurves(idb))
        if not fcs:
            continue
        ad = idb.animation_data
        tr = _base_track(idb)
        if tr is None or not len(tr.strips):
            split = _split_protected(idb)
            if split is None:
                continue
            act, slot = split
            lo, hi = _base_range(channelbag(act, slot).fcurves)
            tr, st = _new_strip(idb, BASE_TRACK, act, slot, lo, hi, extrapolation='HOLD')
            if act == ad.action:                    # (a split scene action keeps its clock active)
                ad.action = None
            act["lane"] = BASE_TRACK
            _move_track_to_bottom(idb, tr)
        else:
            st = tr.strips[0]
            dst = channelbag(st.action, st.action_slot)
            for fc in fcs:
                old = dst.fcurves.find(fc.data_path, index=fc.array_index)
                if old is not None:
                    dst.fcurves.remove(old)
                dst.fcurves.new_from_fcurve(fc, data_path=fc.data_path)
            src_cb = channelbag(ad.action, ad.action_slot)
            for fc in fcs:
                src_cb.fcurves.remove(fc)
            if not _protected_paths(idb) or not active_fcurves(idb):
                ad.action = None
            lo, hi = _base_range(dst.fcurves)
            _set_strip_range(st, min(lo, st.frame_start), max(hi, st.frame_end))
        n += 1
        _STATE["base_log"].append(f"{reason}: {id_label(idb)} ({len(fcs)} curves)")
    return n


def _track_state(tr):
    strips = []
    for st in tr.strips:
        strips.append(dict(name=st.name, action=st.action, slot=st.action_slot.identifier if st.action_slot else None,
                           frame_start=st.frame_start, frame_end=st.frame_end,
                           action_frame_start=st.action_frame_start, action_frame_end=st.action_frame_end,
                           extrapolation=st.extrapolation, blend_type=st.blend_type, influence=st.influence,
                           mute=st.mute, scale=st.scale, repeat=st.repeat, use_reverse=st.use_reverse,
                           blend_in=st.blend_in, blend_out=st.blend_out, use_auto_blend=st.use_auto_blend,
                           use_animated_influence=st.use_animated_influence,
                           use_animated_time=st.use_animated_time,
                           strip_fcurves=[(fc.data_path, [(k.co.x, k.co.y, k.interpolation, k.handle_left.x,
                                                           k.handle_left.y, k.handle_right.x, k.handle_right.y)
                                                          for k in fc.keyframe_points]) for fc in st.fcurves],
                           n_modifiers=len(st.modifiers)))
    return dict(name=tr.name, mute=tr.mute, lock=tr.lock, strips=strips)


def _rebuild_tracks(idb, ordered_states):
    """Remove all NLA tracks of idb and recreate them bottom->top from captured states."""
    ad = idb.animation_data
    for tr in list(ad.nla_tracks):
        ad.nla_tracks.remove(tr)
    prev = None
    for ts in ordered_states:
        tr = ad.nla_tracks.new(prev=prev) if prev is not None else ad.nla_tracks.new()
        tr.name = ts["name"]
        for s in ts["strips"]:
            act = s["action"]
            st = tr.strips.new(s["name"], int(math.floor(s["frame_start"])), act)
            slot = _slot_by_identifier(act, s["slot"]) if s["slot"] else None
            if slot is not None and st.action_slot != slot:
                st.action_slot = slot
            st.use_sync_length = False
            if abs(s["scale"] - 1.0) < 1e-6 and abs(s["repeat"] - 1.0) < 1e-6 \
                    and abs((s["frame_start"] - s["action_frame_start"])) < 1e-4:
                _set_strip_range(st, s["frame_start"], s["frame_end"])
            else:                                   # foreign strip (not ours): restore verbatim
                st.action_frame_start, st.action_frame_end = s["action_frame_start"], s["action_frame_end"]
                st.scale, st.repeat = s["scale"], s["repeat"]
                st.frame_start, st.frame_end = s["frame_start"], s["frame_end"]
            for k in ("extrapolation", "blend_type", "influence", "mute", "use_reverse", "blend_in", "blend_out",
                      "use_auto_blend"):
                try:
                    setattr(st, k, s[k])
                except (AttributeError, TypeError, ValueError):
                    pass
            _restore_strip_animation(st, s)
        tr.mute, tr.lock = ts["mute"], ts["lock"]
        prev = tr
    return ad.nla_tracks


def _restore_strip_animation(st, s):
    """Re-create animated strip influence / strip time keys captured by _track_state (strip F-curves are not
    copied by strips.new); strip F-modifiers cannot be recreated -> warning."""
    if s.get("use_animated_influence"):
        st.use_animated_influence = True
    if s.get("use_animated_time"):
        st.use_animated_time = True
    for path, keys in s.get("strip_fcurves", ()):
        fc = st.fcurves.find(path)
        if fc is None:
            continue
        while len(fc.keyframe_points):
            fc.keyframe_points.remove(fc.keyframe_points[0], fast=True)
        for x, y, interp, hlx, hly, hrx, hry in keys:
            k = fc.keyframe_points.insert(x, y, options={'FAST'})
            k.interpolation = interp
            k.handle_left_type = k.handle_right_type = 'FREE'
            k.handle_left = (hlx, hly)
            k.handle_right = (hrx, hry)
        fc.update()
    if s.get("n_modifiers"):
        _log(f"WARNING strip {s['name']!r}: {s['n_modifiers']} strip F-modifier(s) not preserved by the NLA reorder")


def _move_track_to_bottom(idb, track):
    ad = idb.animation_data
    tracks = list(ad.nla_tracks)
    if tracks and tracks[0] == track:
        return
    states = [_track_state(track)] + [_track_state(t) for t in tracks if t != track]
    _rebuild_tracks(idb, states)


# =============================================================================================
# lanes
# =============================================================================================
def _optional_module(name):
    """Import a sibling module if it exists (other lanes' modules may not be written yet)."""
    try:
        return __import__(name)
    except ImportError as e:
        if getattr(e, "name", None) == name:
            return None
        raise


def _layer_collection_of(layer_coll, col):
    if layer_coll.collection == col:
        return layer_coll
    for ch in layer_coll.children:
        r = _layer_collection_of(ch, col)
        if r is not None:
            return r
    return None


def lane_collection(lane):
    """Collection LANE_<lane> (created under the scene collection)."""
    sc = bpy.context.scene
    name = LANE_PREFIX + lane
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
    if col.name not in sc.collection.children:
        sc.collection.children.link(col)
    return col


def current_lane():
    """Name of the lane being built (between begin_lane and end_lane) or None."""
    return _STATE["current"]


def begin_lane(lane, span=None):
    """Start building `lane`: pre-existing active actions -> BASE, remember objects/markers, make LANE_<lane> the
    active collection, tell events.py which lane emits.  span defaults to config.lane_span(lane) (dev lanes such
    as _demo pass their own)."""
    if _STATE["current"] is not None:
        raise RuntimeError(f"begin_lane({lane!r}) while lane {_STATE['current']!r} is still open")
    span = tuple(int(x) for x in (span or config.lane_span(lane)))
    _STATE["spans"][lane] = span
    if lane not in _STATE["order"]:
        _STATE["order"].append(lane)
    n = stash_pre_lane_keys(reason=f"before {lane}")
    sc = bpy.context.scene
    _STATE["begin_objects"] = set(o.name for o in bpy.data.objects)
    _STATE["snapshot"] = snapshot_state()
    _STATE["begin_markers"] = set((m.name, m.frame) for m in sc.timeline_markers)
    col = lane_collection(lane)
    vl = bpy.context.view_layer
    _STATE["prev_collection"] = vl.active_layer_collection.collection.name
    lc = _layer_collection_of(vl.layer_collection, col)
    if lc is not None:
        vl.active_layer_collection = lc
    ev = _optional_module("events")
    if ev is not None and hasattr(ev, "begin_lane"):
        ev.begin_lane(lane)
    _STATE["current"] = lane
    _STATE["t0"] = time.time()
    _log(f"begin {lane} span {span} (stashed {n} pre-lane IDs into {BASE_TRACK})")
    return dict(lane=lane, span=span, collection=col)


def _audit_fcurves(idb, fcs, span, report):
    """Delete keys outside keep_range(span) (warning), count keys in the tolerance zone (info)."""
    lo_keep, hi_keep = keep_range(span)
    lo_s, hi_s = strip_range(span)
    eps = 1e-3
    for fc in list(fcs):
        kps = fc.keyframe_points
        xs = [k.co.x for k in kps]
        bad = [i for i, x in enumerate(xs) if x < lo_keep - eps or x > hi_keep + eps]
        tol = [x for x in xs if (lo_keep - eps <= x < lo_s - eps) or (hi_s + eps < x <= hi_keep + eps)]
        if tol:
            report["tolerated_keys"] += len(tol)
        if bad:
            fr = [xs[i] for i in bad]
            report["deleted_keys"] += len(bad)
            report["warnings"].append(
                f"{id_label(idb)} {fc.data_path}[{fc.array_index}]: {len(bad)} key(s) outside "
                f"[{lo_keep:.1f}, {hi_keep:.1f}] deleted (frames {min(fr):g}..{max(fr):g})")
            f_in = float(span[0]) - 1.0                  # state the early keys produced at the lane start
            v_in = fc.evaluate(f_in)
            early = any(xs[i] < lo_keep for i in bad)
            for i in reversed(bad):
                kps.remove(kps[i], fast=True)
            fc.update()
            if early and (not len(kps) or abs(fc.evaluate(f_in) - v_in) > 1e-6):
                k = kps.insert(f_in, v_in, options={'FAST'})   # e.g. visible_between(..., frame_start=1)
                k.interpolation = 'CONSTANT'
                fc.update()
                report["info"].append(f"{id_label(idb)} {fc.data_path}[{fc.array_index}]: kept the pre-span "
                                      f"state {v_in:g} as a CONSTANT key at {f_in:g}")
        for m in fc.modifiers:
            if not m.use_restricted_range and m.type not in ('CYCLES',):
                report["info"].append(f"{id_label(idb)} {fc.data_path}[{fc.array_index}]: unrestricted "
                                      f"{m.type} modifier (only evaluated inside the lane strip)")
        if xs:
            report["key_range"][0] = min(report["key_range"][0], min(xs))
            report["key_range"][1] = max(report["key_range"][1], max(xs))


DISCRETE_PATHS = ("hide_render", "hide_viewport")


def snapshot_state():
    """Static values of the channels that typically act as STATE SWITCHES, taken at begin_lane: object
    visibility, object + pose-bone constraint influences, numeric object custom properties.
    {(object name, data_path, index): value}. Used as the 'state before this lane' for channels no earlier
    strip animates (e.g. characters.build's un-keyed defaults: free props hidden, IK influences 0)."""
    snap = {}
    for o in bpy.data.objects:
        snap[(o.name, "hide_render", 0)] = float(o.hide_render)
        snap[(o.name, "hide_viewport", 0)] = float(o.hide_viewport)
        for c in o.constraints:
            snap[(o.name, f'constraints["{c.name}"].influence', 0)] = float(c.influence)
        if o.pose is not None:
            for pb in o.pose.bones:
                for c in pb.constraints:
                    snap[(o.name, f'pose.bones["{pb.name}"].constraints["{c.name}"].influence', 0)] = float(c.influence)
        for k in o.keys():
            v = o[k]
            if isinstance(v, (bool, int, float)):
                snap[(o.name, f'["{k}"]', 0)] = float(v)
    return snap


def _prior_value(idb, path, index, frame):
    """Value of a channel at `frame` from the ID's EXISTING NLA strips (the state before the current lane):
    the strip with the latest start <= frame wins (HOLD_FORWARD holds its end value), BASE (HOLD) lowest.
    Falls back to the begin_lane snapshot (visibility, constraint influences, custom props). None if unknown."""
    ad = idb.animation_data
    best, prio = None, -math.inf
    for tr in (ad.nla_tracks if ad is not None else ()):
        if tr.mute:
            continue
        for st in tr.strips:
            cb = channelbag(st.action, st.action_slot)
            fc = cb.fcurves.find(path, index=index) if cb is not None else None
            if fc is None:
                continue
            hold_back = st.extrapolation == 'HOLD'
            if not hold_back and frame < st.frame_start - 1e-6:
                continue
            p = -1e12 if tr.name == BASE_TRACK else st.frame_start
            if p >= prio:
                t = min(max(frame, st.frame_start), st.frame_end) - st.frame_start + st.action_frame_start
                best, prio = fc.evaluate(t), p
    if best is None and isinstance(idb, bpy.types.Object):
        best = (_STATE.get("snapshot") or {}).get((idb.name, path, index))
    return best


def _hold_prior_state(idb, fcs, span, report):
    """Single-action semantics for DISCRETE channels: when a lane's first key on a CONSTANT/visibility channel
    comes after the lane start, the state from before the lane (earlier strips / BASE / visibility snapshot)
    holds until that key (CONSTANT key at s-1).  Continuous channels keep pure isolation (first key value from
    the lane start - pops hide in the hard cut at the lane boundary)."""
    s0 = float(span[0])
    for fc in fcs:
        kps = fc.keyframe_points
        if not len(kps):
            continue
        k0 = kps[0]
        if k0.co.x <= s0 + 1e-3:                   # keyed at/before the lane's first frame: nothing to hold
            continue
        if not (k0.interpolation == 'CONSTANT' or fc.data_path in DISCRETE_PATHS):
            continue
        prev = _prior_value(idb, fc.data_path, fc.array_index, s0 - 1.0)
        if prev is None or abs(prev - k0.co.y) <= 1e-6:
            continue
        k = kps.insert(s0 - 1.0, prev, options={'FAST'})
        k.interpolation = 'CONSTANT'
        fc.update()
        report["held_states"] += 1


def _call_with_span(fn, span):
    """fn(span) or fn(f0, f1), chosen from the signature (never by catching TypeError, which would also swallow
    TypeErrors raised inside fn)."""
    import inspect
    try:
        params = [p for p in inspect.signature(fn).parameters.values()
                  if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
        var = any(p.kind == p.VAR_POSITIONAL for p in inspect.signature(fn).parameters.values())
    except (TypeError, ValueError):
        return fn(span)
    required = [p for p in params if p.default is p.empty]
    if len(required) >= 2 or (var and not params):
        return fn(span[0], span[1])
    return fn(span)


def _has_visibility_animation(ob):
    ad = ob.animation_data
    if ad is None:
        return False
    if any(fc.data_path in DISCRETE_PATHS for fc in ad.drivers):
        return True
    return any(fc.data_path in DISCRETE_PATHS for fc, *_ in live_fcurves(ob, include_muted=True))


def _auto_hide_new_objects(lane, span, rep):
    """Objects this lane created in its own collection (renderable, statically visible, no visibility keys or
    drivers, not ob['persist']) get CONSTANT visibility keys: hidden at s-1, visible at s, hidden from
    e + AUTO_HIDE_AFTER - so a per-shot rim light or puddle mesh never renders in other lanes. Objects of shared
    modules (vfx, environment: their own collections / time windows) are left alone. Returns the names keyed."""
    col_name = LANE_PREFIX + lane
    s, e = span
    done = []
    for ob in bpy.data.objects:
        if ob.name in _STATE["begin_objects"] or ob.type not in RENDERABLE_TYPES or ob.get("persist"):
            continue
        cols = [c.name for c in ob.users_collection]
        if cols and any(c != col_name and c != bpy.context.scene.collection.name for c in cols):
            continue
        if ob.hide_render or _has_visibility_animation(ob):
            continue
        import bl_util as U
        for f, vis in ((s - 1.0, False), (float(s), True), (e + AUTO_HIDE_AFTER, False)):
            ob.hide_render = ob.hide_viewport = not vis
            for path in DISCRETE_PATHS:
                U.key(ob, path, f, interp='CONSTANT')
        ob.hide_render = ob.hide_viewport = False
        done.append(ob.name)
    if done:
        rep["info"].append(f"auto-hidden outside the lane ({s - 1}/{e + AUTO_HIDE_AFTER}): {done[:20]}"
                           + (f" (+{len(done) - 20})" if len(done) > 20 else ""))
    return done


def end_lane(lane, resolve=True):
    """Finish `lane`: resolve registered clashes, then deferred camera aims (while the lane's actions are still
    active), auto-hide lane-made objects outside the lane, audit key ranges, stash every animated ID's action
    into a strip on track LANE_<lane>, file new objects into LANE_<lane> (names in report['new_object_names']),
    audit new markers.  Returns the lane report dict (also kept for build reports)."""
    if _STATE["current"] != lane:
        raise RuntimeError(f"end_lane({lane!r}) but the open lane is {_STATE['current']!r}")
    span = lane_span(lane)
    rep = dict(lane=lane, span=list(span), warnings=[], info=[], deleted_keys=0, tolerated_keys=0, ids=0, held_states=0,
               key_range=[math.inf, -math.inf], new_objects=0, markers=[], clashes=None, cameras_resolved=0,
               auto_hidden=[])
    sc = bpy.context.scene
    if resolve:
        # clashes first (they nudge sword controllers), then the camera aims that may look at those bones
        mv = _optional_module("moves")
        if mv is not None and hasattr(mv, "resolve_clashes"):
            try:
                rep["clashes"] = _call_with_span(mv.resolve_clashes, span)
            except NotImplementedError as e:
                rep["warnings"].append(f"moves.resolve_clashes not implemented yet ({e})")
            if rep["clashes"] is not None and not isinstance(rep["clashes"], (dict, list, int, float, str)):
                rep["clashes"] = str(rep["clashes"])
        cams = _optional_module("cameras")
        if cams is not None and hasattr(cams, "resolve_pending"):
            rep["cameras_resolved"] = cams.resolve_pending(lane)
        rep["auto_hidden"] = _auto_hide_new_objects(lane, span, rep)
    lo_s, hi_s = strip_range(span)
    named = set()
    for idb in list(iter_anim_ids()):
        fcs = _unprotected(idb, active_fcurves(idb))
        if not fcs:
            continue
        _audit_fcurves(idb, fcs, span, rep)
        _hold_prior_state(idb, fcs, span, rep)
        cb = channelbag(idb.animation_data.action, idb.animation_data.action_slot)
        for fc in list(fcs):                           # drop curves emptied by the audit
            if len(fc.keyframe_points) == 0 and not len(fc.modifiers):
                cb.fcurves.remove(fc)
        split = _split_protected(idb)
        if split is None:
            continue
        act, slot = split
        ad = idb.animation_data
        _new_strip(idb, LANE_PREFIX + lane, act, slot, lo_s, hi_s, extrapolation='HOLD_FORWARD')
        if act == ad.action:
            ad.action = None
        if act.name not in named:
            act["lane"] = lane
            act["lane_span"] = list(span)
            if not act.name.startswith(lane + "|"):
                act.name = (f"{lane}|{act.name}")[:63]
            named.add(act.name)
        rep["ids"] += 1
    # new objects -> LANE_<lane>
    col = lane_collection(lane)
    shot_ids = [s["id"] for s in config.shots_for_lane(lane)]
    rep["new_object_names"] = []
    for ob in bpy.data.objects:
        if ob.name in _STATE["begin_objects"]:
            continue
        rep["new_objects"] += 1
        rep["new_object_names"].append(ob.name)
        users = list(ob.users_collection)
        if not users or all(c == sc.collection for c in users):
            col.objects.link(ob)
            if sc.collection in users:
                sc.collection.objects.unlink(ob)
        if shot_ids and not ob.name.startswith(tuple(shot_ids) + (lane,) + MODULE_PREFIXES):
            rep["info"].append(f"object {ob.name!r} lacks a <shot>_ prefix")
    # markers
    for m in sc.timeline_markers:
        if (m.name, m.frame) in _STATE["begin_markers"]:
            continue
        rep["markers"].append(dict(name=m.name, frame=m.frame, camera=m.camera.name if m.camera else None))
        if not (span[0] <= m.frame <= span[1]):
            rep["warnings"].append(f"marker {m.name!r} at {m.frame} outside the lane span {span}")
    if rep["key_range"][0] == math.inf:
        rep["key_range"] = None
    vl = bpy.context.view_layer
    prev = bpy.data.collections.get(_STATE["prev_collection"] or "")
    lc = _layer_collection_of(vl.layer_collection, prev) if prev else vl.layer_collection
    vl.active_layer_collection = lc or vl.layer_collection
    ev = _optional_module("events")
    if ev is not None and hasattr(ev, "end_lane"):
        ev.end_lane(lane)
    rep["seconds"] = round(time.time() - _STATE.get("t0", time.time()), 2)
    _STATE["current"] = None
    _STATE["reports"][lane] = rep
    for w in rep["warnings"]:
        _log(f"WARNING {lane}: {w}")
    _log(f"end {lane}: {rep['ids']} IDs stashed, {rep['deleted_keys']} keys deleted, "
         f"{rep['tolerated_keys']} in tolerance, {rep['new_objects']} new objects, {len(rep['markers'])} markers")
    return rep


def lane_reports():
    """{lane: report} of the lanes ended in this session."""
    return dict(_STATE["reports"])


# =============================================================================================
# assembly
# =============================================================================================
def _lane_of_track(tr):
    return tr.name[len(LANE_PREFIX):] if tr.name.startswith(LANE_PREFIX) else None


def _lane_start(lane, tr=None):
    if lane in _STATE["spans"]:
        return _STATE["spans"][lane][0]
    if tr is not None and len(tr.strips):
        act = tr.strips[0].action
        if act is not None and "lane_span" in act.keys():
            return float(act["lane_span"][0])
        return tr.strips[0].frame_start + PRE
    try:
        return config.lane_span(lane)[0]
    except ValueError:
        return 1e9


def _track_rank(tr):
    if tr.name == BASE_TRACK:
        return (0, 0.0)
    lane = _lane_of_track(tr)
    if lane is not None:
        return (1, float(_lane_start(lane, tr)))
    if SECONDARY_TAG in tr.name.lower():
        return (3, 0.0)
    return (2, 0.0)


def _fill_base(idb, report):
    """Give BASE a constant key for every channel a lane animates but BASE lacks (value = that channel at the
    start of the earliest lane strip animating it). Creates the BASE action/track when needed."""
    ad = idb.animation_data
    first = {}
    for tr in ad.nla_tracks:
        if _lane_of_track(tr) is None or tr.mute:
            continue
        for st in tr.strips:
            cb = channelbag(st.action, st.action_slot)
            if cb is None:
                continue
            for fc in cb.fcurves:
                k = (fc.data_path, fc.array_index)
                if k not in first or st.frame_start < first[k][0]:
                    first[k] = (st.frame_start, fc, st)
    if not first:
        return 0
    base = _base_track(idb)
    have = set()
    if base is not None and len(base.strips):
        cbb = channelbag(base.strips[0].action, base.strips[0].action_slot)
        have = {(fc.data_path, fc.array_index) for fc in cbb.fcurves} if cbb is not None else set()
    missing = [k for k in first if k not in have]
    if not missing:
        return 0
    saved_act, saved_slot = ad.action, ad.action_slot
    if base is not None and len(base.strips):
        bst = base.strips[0]
        act = bst.action
        ad.action = act
        if bst.action_slot is not None:
            ad.action_slot = bst.action_slot
    else:
        act = bpy.data.actions.new(f"BASE|{idb.name}"[:63])
        act["lane"] = BASE_TRACK
        ad.action = act
    f_key = float(config.FRAME_START)
    for (path, idx) in missing:
        start, src_fc, st = first[(path, idx)]
        value = src_fc.evaluate(st.action_frame_start)
        fc = act.fcurve_ensure_for_datablock(idb, path, index=idx)
        k = fc.keyframe_points.insert(f_key, value, options={'FAST'})
        k.interpolation = 'CONSTANT'
        fc.update()
    slot = ad.action_slot
    ad.action = saved_act
    if saved_act is not None and saved_slot is not None:
        ad.action_slot = saved_slot
    if base is None or not len(base.strips):
        lo, hi = _base_range(channelbag(act, slot).fcurves)
        _new_strip(idb, BASE_TRACK, act, slot, lo, hi, extrapolation='HOLD')
    report["base_filled"] += len(missing)
    return len(missing)


def assemble_nla(lanes=None):
    """Order every ID's NLA stack: BASE (HOLD) at the bottom, LANE_<lane> tracks chronologically by lane start,
    other tracks, '*secondary*' tracks on top; enforce lane strip ranges (s-0.3 .. e+0.7), HOLD_FORWARD, REPLACE;
    fill BASE for channels that only lanes animate.  lanes: restrict to these lanes' tracks (others are muted
    -> partial builds); None = all.  Returns a report dict."""
    rep = dict(ids=0, reordered=0, base_filled=0, strips=0, warnings=[], unstashed=[])
    for idb in list(iter_anim_ids(with_nla=True)):
        ad = idb.animation_data
        leftovers = _unprotected(idb, active_fcurves(idb))
        if leftovers:
            rep["unstashed"].append(f"{id_label(idb)}: {len(leftovers)} active curve(s) evaluated over all lanes")
        if not len(ad.nla_tracks):
            continue
        rep["ids"] += 1
        for tr in ad.nla_tracks:
            lane = _lane_of_track(tr)
            if lane is None:
                continue
            if lanes is not None:
                tr.mute = lane not in lanes
            if lane in _STATE["spans"]:
                span = _STATE["spans"][lane]
            else:
                st0 = tr.strips[0] if len(tr.strips) else None
                act = st0.action if st0 is not None else None
                span = tuple(act["lane_span"]) if act is not None and "lane_span" in act.keys() else None
            for st in tr.strips:
                if span is not None:
                    a, b = strip_range(span)
                    if abs(st.frame_start - a) > 1e-3 or abs(st.frame_end - b) > 1e-3:
                        _set_strip_range(st, a, b)
                st.extrapolation = 'HOLD_FORWARD'
                st.blend_type = 'REPLACE'
                rep["strips"] += 1
        _fill_base(idb, rep)
        tracks = list(ad.nla_tracks)
        desired = sorted(tracks, key=_track_rank)
        if [t.name for t in tracks] != [t.name for t in desired] or any(a != b for a, b in zip(tracks, desired)):
            _rebuild_tracks(idb, [_track_state(t) for t in desired])
            rep["reordered"] += 1
        base = _base_track(idb)
        if base is not None and len(base.strips):
            base.strips[0].extrapolation = 'HOLD'
    for u in rep["unstashed"]:
        _log(f"note: {u}")
    _log(f"assembled NLA on {rep['ids']} IDs ({rep['strips']} lane strips, {rep['reordered']} stacks reordered, "
         f"{rep['base_filled']} BASE channels filled)")
    return rep


def secondary_override(rig, f0, f1, bones=None):
    """Let the lane's OWN keys drive secondary-motion bones over [f0, f1] (e.g. the S24e ECU of the headband tail
    tip): after characters.apply_secondary_motion, build_scene moves those bones' channels of the
    '<rig>_secondary' action onto a '<rig>_secondary_mask' track whose influence is keyed 0 inside every
    registered range (1 elsewhere, so nothing else changes).  bones None = every secondary bone of the rig.
    Call from acts/<lane>.build (the lane keys the bones itself inside the range)."""
    name = rig if isinstance(rig, str) else rig.name
    _STATE.setdefault("secondary_masks", []).append(dict(rig=name, f0=float(f0), f1=float(f1),
                                                         bones=sorted(bones) if bones else None,
                                                         lane=_STATE["current"]))


def _bone_of(path):
    return path.split('"')[1] if path.startswith('pose.bones["') else None


def apply_secondary_masks():
    """Apply the secondary_override registrations (see there). Returns a list of dicts (per rig: bones, ranges)."""
    import numpy as np
    out = []
    masks = _STATE.get("secondary_masks") or []
    for rig_name in sorted({m["rig"] for m in masks}):
        rig = bpy.data.objects.get(rig_name)
        ad = rig.animation_data if rig is not None else None
        mine = [m for m in masks if m["rig"] == rig_name]
        tr = None
        if ad is not None:
            tr = next((t for t in reversed(list(ad.nla_tracks)) if SECONDARY_TAG in t.name.lower()
                       and not t.name.endswith("_mask") and len(t.strips)), None)
        if tr is None:
            _log(f"WARNING secondary_override on {rig_name}: no secondary track (apply_secondary_motion missing?)")
            out.append(dict(rig=rig_name, applied=False, ranges=[(m["f0"], m["f1"]) for m in mine]))
            continue
        st = tr.strips[0]
        cb = channelbag(st.action, st.action_slot)
        want = None if any(m["bones"] is None for m in mine) else {b for m in mine for b in m["bones"]}
        move = [fc for fc in cb.fcurves if _bone_of(fc.data_path) and (want is None or _bone_of(fc.data_path) in want)]
        if not move:
            out.append(dict(rig=rig_name, applied=False, reason="no matching secondary channels"))
            continue
        mact = bpy.data.actions.new(f"{rig_name}_secondary_mask")
        saved, saved_slot = ad.action, ad.action_slot
        for fc in move:
            ad.action = mact
            nf = mact.fcurve_ensure_for_datablock(rig, fc.data_path, index=fc.array_index)
            n = len(fc.keyframe_points)
            nf.keyframe_points.add(n)
            for prop, w, dt in (("co", 2, np.float32), ("handle_left", 2, np.float32),
                                ("handle_right", 2, np.float32), ("interpolation", 1, np.int32)):
                buf = np.zeros(n * w, dtype=dt)
                fc.keyframe_points.foreach_get(prop, buf)
                nf.keyframe_points.foreach_set(prop, buf)
            nf.extrapolation = fc.extrapolation
            nf.update()
        slot = ad.action_slot
        ad.action = saved
        if saved is not None and saved_slot is not None:
            ad.action_slot = saved_slot
        for fc in move:
            cb.fcurves.remove(fc)
        mtr, mst = _new_strip(rig, f"{rig_name}_secondary_mask", mact, slot, st.frame_start, st.frame_end,
                              extrapolation=st.extrapolation)
        mst.use_animated_influence = True
        ifc = mst.fcurves.find("influence")
        pts = [(st.frame_start, 1.0)]                   # influence 0 over [f0, f1 + 1): frame f1's shutter too
        for m in sorted(mine, key=lambda m: m["f0"]):
            pts += [(m["f0"], 0.0), (m["f1"] + 1.0, 1.0)]
        for x, y in pts:
            k = ifc.keyframe_points.insert(x, y, options={'FAST'})
            k.interpolation = 'CONSTANT'
        ifc.update()
        out.append(dict(rig=rig_name, applied=True, channels=len(move),
                        bones=sorted({_bone_of(f.data_path) for f in channelbag(mact, slot).fcurves}),
                        ranges=[(m["f0"], m["f1"]) for m in mine]))
        _log(f"secondary override on {rig_name}: {len(move)} channels masked over {out[-1]['ranges']}")
    return out


def push_track(idb, action, name, frame_range=None, slot=None, extrapolation='HOLD_FORWARD', blend='REPLACE'):
    """Put `action` on a new TOP track of idb (e.g. '<rig>_secondary', Pipeline rule 11). The slot defaults to
    the one matching the ID (or the action's only slot). frame_range defaults to the action's key range."""
    if slot is None:
        cands = [s for s in action.slots if s.identifier[2:] == idb.name] or list(action.slots)
        slot = cands[0] if cands else None
    if frame_range is None:
        cb = channelbag(action, slot)
        xs = [k.co.x for fc in (cb.fcurves if cb else ()) for k in fc.keyframe_points]
        frame_range = (min(xs), max(xs) + 1.0) if xs else (config.FRAME_START, config.FRAME_END)
    tr, st = _new_strip(idb, name, action, slot, float(frame_range[0]), float(frame_range[1]),
                        extrapolation=extrapolation, blend=blend)
    return tr, st


# =============================================================================================
# reading keys after assembly
# =============================================================================================
def live_fcurves(idb, include_muted=False):
    """[(fcurve, source, (lo, hi), offset)] for the active action (source 'active', whole timeline) and every
    NLA strip (source '<track>/<strip>', live over the strip range; scene frame = key frame + offset)."""
    out = []
    ad = getattr(idb, "animation_data", None)
    if ad is None:
        return out
    for fc in active_fcurves(idb):
        out.append((fc, "active", (-math.inf, math.inf), 0.0))
    for tr in ad.nla_tracks:
        if tr.mute and not include_muted:
            continue
        for st in tr.strips:
            if st.mute and not include_muted:
                continue
            cb = channelbag(st.action, st.action_slot)
            if cb is None:
                continue
            off = st.frame_start - st.action_frame_start
            for fc in cb.fcurves:
                out.append((fc, f"{tr.name}/{st.name}", (st.frame_start, st.frame_end), off))
    return out


def keys_in_range(idb, f0, f1, prefix=None, live_only=True):
    """Keys of idb with scene frame in [f0, f1], looking inside the active action AND all NLA strip actions.
    live_only: only keys inside their strip's range (those that actually play). Returns a list of dicts
    {frame, value, data_path, index, source, interpolation}, sorted by frame."""
    out = []
    for fc, src, (lo, hi), off in live_fcurves(idb):
        if prefix and not fc.data_path.startswith(prefix):
            continue
        for k in fc.keyframe_points:
            t = k.co.x + off
            if live_only and not (lo - 1e-3 <= t <= hi + 1e-3):
                continue
            if f0 - 1e-3 <= t <= f1 + 1e-3:
                out.append(dict(frame=t, value=k.co.y, data_path=fc.data_path, index=fc.array_index, source=src,
                                interpolation=k.interpolation))
    out.sort(key=lambda d: (d["frame"], d["data_path"], d["index"]))
    return out


def keyed_frames(idb, prefix=None, live_only=True):
    """Sorted unique scene frames with keys (see keys_in_range)."""
    return sorted({round(d["frame"], 3) for d in keys_in_range(idb, -math.inf, math.inf, prefix, live_only)})


def lane_tracks(idb):
    """Names of LANE_* tracks on idb (bottom -> top)."""
    ad = getattr(idb, "animation_data", None)
    return [t.name for t in ad.nla_tracks if t.name.startswith(LANE_PREFIX)] if ad else []


# =============================================================================================
# render lock (machine-wide semaphore; no bpy needed)
# =============================================================================================
_HELD = dict(depth=0, slot=None, fh=None)


def _lock_dir():
    return LOCK_DIR


def _slot_count(slots=None):
    return max(1, int(slots or config.RENDER_SLOTS))


def lock_holders(lock_dir=None, slots=None):
    """[{slot, held, info}] - probes each slot file without blocking."""
    d = lock_dir or _lock_dir()
    out = []
    for i in range(_slot_count(slots)):
        p = os.path.join(d, f"render_slot_{i}.lock")
        if not os.path.exists(p):
            out.append(dict(slot=i, held=False, info=None))
            continue
        with open(p, "a+") as fh:
            held = not procutil.lock_file(fh)
            if not held:
                procutil.unlock_file(fh)
            try:
                fh.seek(0)
                txt = fh.read().strip()
            except OSError:             # Windows: a held byte-range lock also blocks reads
                txt = ""
        info = None
        if held and txt:
            try:
                info = json.loads(txt)
            except ValueError:
                info = txt
        out.append(dict(slot=i, held=held, info=info))
    return out


@contextlib.contextmanager
def render_lock(label=None, slots=None, timeout=None, poll=0.5, lock_dir=None, log=True):
    """Machine-wide render semaphore (config.RENDER_SLOTS slots, settings render.slots) using procutil.lock_file on
    <config.LOCK_DIR>/render_slot_<i>.lock.  Blocks until a slot is free (timeout -> TimeoutError); the OS releases
    the lock if the process dies.  Re-entrant within a process.  config.RENDER_LOCK = False (settings render.lock,
    env SILVERGRASS_RENDER_LOCK=0) disables it.  Yields the slot index (None when disabled)."""
    if not config.RENDER_LOCK:
        yield None
        return
    if _HELD["depth"] > 0:
        _HELD["depth"] += 1
        try:
            yield _HELD["slot"]
        finally:
            _HELD["depth"] -= 1
        return
    d = lock_dir or _lock_dir()
    os.makedirs(d, exist_ok=True)
    n = _slot_count(slots)
    t0 = time.time()
    said = False
    fh = slot = None
    while fh is None:
        for i in range(n):
            f = open(os.path.join(d, f"render_slot_{i}.lock"), "a+")
            if not procutil.lock_file(f):
                f.close()
                continue
            fh, slot = f, i
            break
        if fh is not None:
            break
        if timeout is not None and time.time() - t0 > timeout:
            raise TimeoutError(f"render_lock: no free slot after {timeout:.0f}s ({lock_holders(d, n)})")
        if log and not said:
            print(f"[render_lock] waiting for one of {n} render slots ({label or ''})", flush=True)
            said = True
        time.sleep(poll)
    try:
        fh.seek(0)
        fh.truncate()
        fh.write(json.dumps(dict(pid=os.getpid(), label=label, since=time.strftime("%Y-%m-%d %H:%M:%S"))))
        fh.flush()
    except OSError:
        pass
    waited = time.time() - t0
    if log and waited > 1.0:
        print(f"[render_lock] got slot {slot} after {waited:.1f}s ({label or ''})", flush=True)
    _HELD.update(depth=1, slot=slot, fh=fh)
    try:
        yield slot
    finally:
        _HELD.update(depth=0, slot=None, fh=None)
        try:
            fh.seek(0)
            fh.truncate()
        except OSError:
            pass
        procutil.unlock_file(fh)
        fh.close()


def locked_render_still(filepath, frame=None, label=None, scene=None):
    """bl_util.render_still inside a render_lock slot. Returns seconds spent rendering (excl. waiting)."""
    import bl_util as U
    with render_lock(label=label or os.path.basename(filepath)):
        return U.render_still(filepath, frame, scene)
