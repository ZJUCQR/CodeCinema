"""
events.py - the animation event table that drives the procedural sound track ("events.py",
docs/STAGING.md §8).

    import events
    events.emit(595, "clash", pos=(0.1, -0.4, 1.3), strength=0.9, tags=["first_clash"])
    events.emit(612, "step", who="shinobi")                      # position = the rig (feet height for steps)
    events.emit(640, "whoosh", target=(saint_rig, "hand.R"), who="saint", weapon="katana", strength=0.7)
    events.emit(1633, "music_cue", cue="act2_start")
    doc = events.finalize()                                      # -> out/events.json (full builds)

Every event is stored with the lane that emitted it (lane_tools.begin_lane -> events.begin_lane), so partial
builds export only their lanes.  Positions given as `target` (object, (rig, bone) or object name) or `who`
('shinobi' | 'saint') are resolved at finalize() time - after the NLA assembly - at the event frame.
finalize() adds, from the camera that is active at that frame according to the timeline markers:
    pan  -1..1  (screen x of the event position; behind the camera folded to +-0.8)
    dist metres from the camera,  onscreen bool,  cut  (marker name, e.g. 'S12a')
Output: {fps, frame_start, frame_end, acts, shots, cuts, events:[{frame, type, ..., pos?, pan?, dist?,
tags?}], music_cues:{name: frame}, music_cue_sources, unknown_types, missing_beats, lanes, partial, warnings}.
music_cues = config.MUSIC_CUES, overridden by tags (earliest event carrying a cue name as tag), overridden by
explicit music_cue events (attr cue=...).  Unknown event types are allowed, kept, and listed in unknown_types.
"""
import json
import math
import os
import sys
import time

try:
    import bpy
    from mathutils import Vector
except ImportError:                       # importable outside Blender (reading/merging only)
    bpy = None
    Vector = None

ROOT = (__import__("os").environ.get("SILVERGRASS_ROOT") or str(next(p for p in __import__("pathlib").Path(__file__).resolve().parents if (p / "src" / "common" / "config.py").is_file())))   # repo root (portable)
for _p in (os.path.join(ROOT, "src", "common"), os.path.join(ROOT, "src", "blender")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import config  # noqa: E402

KNOWN_TYPES = {
    "whoosh", "clash", "raikiri", "tree_split", "haori_shed", "spear_draw", "sheath_drop", "clash_heavy",
    "perfect_deflect", "blade_lock", "hit", "kick", "step", "dash", "jump", "land", "roll", "skid", "kneel",
    "body_fall", "draw", "sheathe", "tsuba_click", "spear_pull", "spear_spin", "kunai_throw", "kunai_deflect",
    "hat_cut", "sword_break", "cord_cut", "wind_gust", "grass_shear", "fire_ignite", "fire_burst", "thunder",
    "lightning_strike", "electric_crackle", "rain_split", "rain_start", "rain_stop", "steam_hiss", "shockwave",
    "bell", "heartbeat", "stinger", "slowmo", "music_cue",
    "drip",                 # audio extension (src/audio/timeline.py): a single drop into a puddle (S24e)
}
GROUND_TYPES = {"step", "land", "skid", "roll", "kneel", "body_fall", "dash", "jump", "drip"}
WHO_RIGS = {"shinobi": "SHINOBI_rig", "saku": "SHINOBI_rig", "saint": "SAINT_rig", "elder": "SAINT_rig",
            "tenkosai": "SAINT_rig"}
REQUIRED_BEATS = [tuple(b) for b in config.STORY_BEATS]
EVENT_SPAN_TOL = config.LANE_KEY_TOLERANCE   # an event may lie this far outside its emitting lane's span

_EVENTS = []
_STATE = dict(lane=None, seq=0)


# =============================================================================================
# registry
# =============================================================================================
def begin_lane(lane):
    """Called by lane_tools.begin_lane: subsequent emits belong to `lane`; the lane's old events are dropped."""
    clear(lane)
    _STATE["lane"] = lane


def end_lane(lane):
    """Called by lane_tools.end_lane."""
    if _STATE["lane"] == lane:
        _STATE["lane"] = None


def set_lane(lane):
    """Set the emitting lane explicitly (None = global / build_scene)."""
    _STATE["lane"] = lane


def clear(lane=None):
    """Drop all events (lane=None) or the events of one lane."""
    global _EVENTS
    _EVENTS = [] if lane is None else [e for e in _EVENTS if e["_lane"] != lane]


def _target_ref(target):
    """Store targets by name so references survive undo/reload: ('obj', name) | ('bone', rig, bone)."""
    if target is None:
        return None
    if isinstance(target, str):
        if ":" in target:
            rig, bone = target.split(":", 1)
            return ("bone", rig, bone)
        return ("obj", target)
    if isinstance(target, (tuple, list)) and len(target) == 2 and isinstance(target[1], str):
        rig = target[0] if isinstance(target[0], str) else target[0].name
        return ("bone", rig, target[1])
    if hasattr(target, "name") and hasattr(target, "matrix_world"):
        return ("obj", target.name)
    raise TypeError(f"events: unsupported target {target!r}")


def _jsonable(v):
    if v is None or isinstance(v, (bool, int, str)):
        return v
    if isinstance(v, float):
        return round(v, 4) if math.isfinite(v) else None
    if hasattr(v, "tolist"):
        return _jsonable(v.tolist())
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set)) or (Vector is not None and isinstance(v, Vector)):
        return [_jsonable(x) for x in v]
    if hasattr(v, "name"):
        return v.name
    return str(v)


def emit(frame, type, pos=None, target=None, who=None, tags=None, lane=None, **attrs):
    """Record an event at `frame` (int or float) of `type` (see KNOWN_TYPES; unknown types are kept + listed).
    pos: world xyz; target: object | (rig, bone) | 'Name' | 'Rig:bone' resolved at finalize; who: 'shinobi' |
    'saint' (also used as position when pos/target are missing: the rig at 1.1 m, feet height for step-like
    types).  tags: list of story-beat / music-cue names (e.g. ['first_clash']).  Any other keyword (strength,
    duration [frames], weapon, distance, cue, ...) is exported verbatim.  Returns the stored event dict."""
    fr = float(frame)
    e = dict(frame=int(fr) if fr.is_integer() else round(fr, 3), type=str(type))
    if who is not None:
        e["who"] = str(who)
    for k, v in attrs.items():
        e[k] = _jsonable(v)
    if pos is not None:
        e["pos"] = [round(float(x), 4) for x in pos]
    if tags:
        e["tags"] = [tags] if isinstance(tags, str) else [str(t) for t in tags]
    e["_lane"] = lane if lane is not None else _STATE["lane"]
    e["_target"] = _target_ref(target)
    e["_seq"] = _STATE["seq"]
    _STATE["seq"] += 1
    _EVENTS.append(e)
    return e


def events(lane=None, types=None):
    """Copies of the registered events (optionally of one lane / some types), in emission order."""
    out = []
    for e in _EVENTS:
        if lane is not None and e["_lane"] != lane:
            continue
        if types is not None and e["type"] not in types:
            continue
        out.append(dict(e))
    return out


def summary():
    """{lane: {type: count}}"""
    out = {}
    for e in _EVENTS:
        d = out.setdefault(str(e["_lane"]), {})
        d[e["type"]] = d.get(e["type"], 0) + 1
    return out


def matches(e, name):
    """True if event e is a `name` beat: its type, one of its tags, or a music_cue with cue == name."""
    return e.get("type") == name or name in (e.get("tags") or []) or \
        (e.get("type") == "music_cue" and e.get("cue") == name)


# =============================================================================================
# camera + position resolution
# =============================================================================================
def marker_cameras(scene=None):
    """Sorted [(frame, camera_object, marker_name)] of the timeline markers bound to cameras."""
    sc = scene or bpy.context.scene
    return sorted(((m.frame, m.camera, m.name) for m in sc.timeline_markers if m.camera is not None),
                  key=lambda t: t[0])


def active_camera(frame, scene=None, cam_map=None):
    """(camera, marker_name) active at `frame` according to the marker map (scene.camera if no marker)."""
    sc = scene or bpy.context.scene
    cm = cam_map if cam_map is not None else marker_cameras(sc)
    best = None
    for f, cam, name in cm:
        if f <= frame + 1e-6:
            best = (cam, name)
        else:
            break
    if best is None:
        return sc.camera, None
    return best


def _resolve_pos(e):
    """World position of the event at the current (already set) frame, or None."""
    if "pos" in e:
        return Vector(e["pos"])
    ref = e.get("_target")
    if ref is not None:
        if ref[0] == "bone":
            rig = bpy.data.objects.get(ref[1])
            if rig is not None and rig.pose is not None and ref[2] in rig.pose.bones:
                return (rig.matrix_world @ rig.pose.bones[ref[2]].matrix).translation.copy()
            if rig is not None:
                return rig.matrix_world.translation.copy()
            return None
        ob = bpy.data.objects.get(ref[1])
        if ob is not None:
            import bl_util as U
            return U.world_pos_of(ob)
        return None
    who = str(e.get("who", "")).lower()
    rig = bpy.data.objects.get(WHO_RIGS.get(who, "")) if who else None
    if rig is None:
        return None
    base = rig.matrix_world.translation.copy()
    if e["type"] in GROUND_TYPES:
        return base + Vector((0.0, 0.0, 0.05))
    if rig.pose is not None and "chest" in rig.pose.bones:
        return (rig.matrix_world @ rig.pose.bones["chest"].matrix).translation.copy()
    return base + Vector((0.0, 0.0, 1.1))


def pan_dist(scene, cam, pos):
    """(pan -1..1, dist m, onscreen) of world point pos seen from cam (already evaluated at the frame)."""
    from bpy_extras.object_utils import world_to_camera_view
    p = Vector(pos)
    M = cam.matrix_world
    local = M.inverted() @ p
    dist = (p - M.translation).length
    if local.z < -1e-4:                                  # in front (camera looks down -Z)
        co = world_to_camera_view(scene, cam, p)
        pan = max(-1.0, min(1.0, (co.x - 0.5) * 2.0))
        onscreen = 0.0 <= co.x <= 1.0 and 0.0 <= co.y <= 1.0
    else:                                                # behind: fold to the sides, softer
        pan = 0.0 if abs(local.x) < 1e-6 else math.copysign(0.8, local.x)
        onscreen = False
    return round(pan, 3), round(dist, 2), bool(onscreen)


# =============================================================================================
# export
# =============================================================================================
def _music_cues(evs, warnings):
    cues = dict(config.MUSIC_CUES)
    src = {k: "config" for k in cues}
    tagged = {}
    for e in evs:
        for t in e.get("tags") or []:
            if t in config.MUSIC_CUES and t not in tagged:
                tagged[t] = e
    for t, e in tagged.items():
        cues[t] = e["frame"]
        src[t] = f"tag on {e['type']}"
    explicit = {}
    for e in evs:
        if e["type"] == "music_cue":
            name = str(e.get("cue", "")).strip()
            if not name:
                warnings.append(f"music_cue event at {e['frame']} without cue=")
                continue
            if name in explicit:
                warnings.append(f"music_cue {name!r} emitted twice ({explicit[name]['frame']}, {e['frame']}); "
                                f"keeping the first")
                continue
            explicit[name] = e
            if name not in config.MUSIC_CUES:
                warnings.append(f"music_cue {name!r} is not a config.MUSIC_CUES key")
    for name, e in explicit.items():
        cues[name] = e["frame"]
        src[name] = "music_cue event"
    return cues, src


def _missing_beats(evs, spans):
    out = []
    for beat in REQUIRED_BEATS:
        name, fr, tol = beat[:3]
        count = int(beat[3]) if len(beat) > 3 else 1
        if not any(a <= fr <= b for a, b in spans):
            continue
        n = sum(1 for e in evs if matches(e, name) and abs(float(e["frame"]) - fr) <= tol)
        if n < count:
            out.append(dict(name=name, frame=fr, tolerance=tol, count=count, found=n))
    return out


def audit(evs, lane_spans=None):
    """Warnings for events outside their emitting lane's span (+-EVENT_SPAN_TOL) and duplicated events (same
    frame, type, who, cue - e.g. moves.clash and the lane both emitting the clash)."""
    warnings = []
    for e in evs:
        span = (lane_spans or {}).get(e.get("_lane"))
        if span is not None and not (span[0] - EVENT_SPAN_TOL <= float(e["frame"]) <= span[1] + EVENT_SPAN_TOL):
            warnings.append(f"event {e['type']!r} at {e['frame']} from lane {e['_lane']!r} lies outside its span "
                            f"{tuple(span)}")
    seen = {}
    for e in evs:
        k = (round(float(e["frame"]), 2), e["type"], e.get("who"), e.get("cue"))
        seen[k] = seen.get(k, 0) + 1
    for (fr, typ, who, cue), n in sorted(seen.items(), key=lambda kv: kv[0][0]):
        if n > 1:
            warnings.append(f"duplicate event: {n} x {typ!r} at {fr:g}" + (f" (who={who})" if who else "") +
                            (f" (cue={cue})" if cue else ""))
    return warnings


def finalize(path=None, lanes=None, scene=None, spans=None, cuts=None, write=True, extra=None, lane_spans=None):
    """Resolve positions + pan/dist/cut for every event (lanes=None: all) at its frame and write the events
    document. path defaults to config.EVENTS_JSON. spans: [(f0, f1)] of the built lanes (for the story-beat
    check; default: spans of `lanes` / all events). lane_spans: {lane: (f0, f1)} for the out-of-span audit
    (default: lane_tools' registered spans). cuts: optional [(cut_id, f0, f1, camera)] (default: from the
    markers). Warnings: unknown types, missing beats (with counts), out-of-span + duplicate events, music cues
    that fall back to config frames inside a built span. Returns the document dict."""
    sc = scene or bpy.context.scene
    path = path or config.EVENTS_JSON
    def _keep(e):
        if lanes is None or e["_lane"] in lanes:
            return True        # lane-less events (e.g. from vfx.finalize) belong to the built spans they fall in
        return e["_lane"] is None and any(a <= float(e["frame"]) <= b for a, b in (spans or ()))
    evs = [dict(e) for e in _EVENTS if _keep(e)]                               # copies: targets stay live
    evs.sort(key=lambda e: (float(e["frame"]), e["_seq"]))
    warnings = []
    cam_map = marker_cameras(sc)
    frame_now = sc.frame_current
    import bl_util as U
    with U.muted_modifiers():
        by_frame = {}
        for e in evs:
            by_frame.setdefault(float(e["frame"]), []).append(e)
        for fr in sorted(by_frame):
            U.frame_set(fr, sc)
            for e in by_frame[fr]:
                cam, cut = active_camera(fr, sc, cam_map)
                if cut is not None:
                    e["cut"] = cut
                p = _resolve_pos(e)
                if p is None:
                    continue
                e["pos"] = [round(float(x), 3) for x in p]
                if cam is not None:
                    e["pan"], e["dist"], e["onscreen"] = pan_dist(sc, cam, p)
    sc.frame_set(frame_now)
    unknown = sorted({e["type"] for e in evs if e["type"] not in KNOWN_TYPES})
    for t in unknown:
        warnings.append(f"unknown event type {t!r} (kept; audio may ignore it)")
    if lane_spans is None:
        try:
            import lane_tools
            lane_spans = dict(lane_tools._STATE.get("spans") or {})
        except ImportError:
            lane_spans = {}
    warnings += audit(evs, lane_spans)
    cues, cue_src = _music_cues(evs, warnings)
    if spans is None:
        if lanes is not None:
            spans = []
            for ln in lanes:
                try:
                    spans.append(tuple(config.lane_span(ln)))
                except ValueError:
                    pass
        else:
            spans = [(config.FRAME_START, config.FRAME_END)] if evs else []
    missing = _missing_beats(evs, spans)
    for m in missing:
        warnings.append(f"story beat {m['name']!r} (~{m['frame']}) not emitted" +
                        (f" ({m['found']}/{m['count']} found)" if m["count"] > 1 else ""))
    for name, src in sorted(cue_src.items()):
        fr = cues[name]
        if src == "config" and any(a <= fr <= b for a, b in spans) and name != "prologue_start":
            warnings.append(f"music cue {name!r} falls back to config frame {fr} inside a built span "
                            f"(emit music_cue(cue={name!r}) or tag the event where it really happens)")
    if cuts is None:
        cuts = []
        for i, (f, cam, name) in enumerate(cam_map):
            f1 = cam_map[i + 1][0] - 1 if i + 1 < len(cam_map) else int(cam.get("cut_f1", config.FRAME_END))
            cuts.append((name, f, int(cam.get("cut_f1", f1)), cam))
    out_events = []
    for e in evs:
        d = {k: v for k, v in e.items() if not k.startswith("_")}
        d["lane"] = e["_lane"]
        out_events.append(d)
    doc = dict(
        fps=config.FPS, frame_start=config.FRAME_START, frame_end=config.FRAME_END,
        acts=config.ACTS,
        shots=[dict(id=s["id"], start=s["start"], end=s["end"], lane=s["lane"]) for s in config.SHOTS],
        cuts=[dict(id=c[0], start=int(c[1]), end=int(c[2]), camera=c[3].name if c[3] is not None else None,
                   lens=round(c[3].data.lens, 2) if c[3] is not None else None) for c in cuts],
        events=out_events,
        music_cues=cues, music_cue_sources=cue_src,
        unknown_types=unknown, missing_beats=missing,
        lanes=sorted({str(e["_lane"]) for e in evs}) if lanes is None else list(lanes),
        partial=lanes is not None,
        generated=time.strftime("%Y-%m-%d %H:%M:%S"),
        warnings=warnings,
    )
    if extra:
        doc.update(extra)
    if write:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
        print(f"[events] wrote {len(out_events)} events -> {path} ({len(unknown)} unknown types, "
              f"{len(missing)} missing beats)")
    return doc


def load(path=None):
    """Read an events document (no bpy needed)."""
    with open(path or config.EVENTS_JSON, "r", encoding="utf-8") as f:
        return json.load(f)
