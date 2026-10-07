"""
build_scene.py - one-command scene build.

    Blender -b --factory-startup --python-exit-code 1 --python codecinema/productions/silvergrass/blender/build_scene.py -- \
        [--lanes act1b | act1a,act1b | all] [--quality layout|preview|final] [--out DIR] [--no-save]
        [--no-qa] [--no-digest] [--strict] [--stubs environment,...] [--fallback]

Pass order: env.build -> characters.build -> fxclock.ensure_clock -> for each lane: lane_tools.begin_lane ->
acts.<lane>.build(ctx) -> lane_tools.end_lane -> lane_tools.assemble_nla -> secondary motion
(characters.apply_secondary_motion with a memoised environment.wind_at, then lane secondary overrides) ->
vfx.finalize -> events.finalize -> global QA (handoffs <= 0.5 m + prop states, a camera marker at every shot
start + cut coverage, stray keys/markers, clash gate, screen direction, framing, cut smears, lane objects leaking
outside their lane) -> render_setup.configure(quality) (the partial range is restored afterwards) -> per-shot
content digests (render invalidation) -> save.  Sampling passes run inside bl_util.muted_modifiers.  The render
resolution is the film's 1920x816 from the start, so QA / event projections use the real 2.35:1 frame.
--quality defaults to 'final' for a full build and 'preview' for --lanes.
Outputs
    full build ('all')  : out/scene.blend, out/events.json, out/build_report.json (+ out/qa/*.json)
    partial (--lanes)   : out/lanes/<lane[+lane]>/scene.blend, events.json, build_report.json, qa/*.json
The previous scene.blend + events.json of the output dir are deleted when a build starts; build_report.json says
'running' / 'failed' (+ 'error') / 'ok'; events.json only appears when the whole build succeeded.  Exit codes:
0 ok, 1 the build raised, 2 --strict with QA FAILs.
Modules other lanes are still writing (environment, characters, vfx, render_setup, moves) are optional: when a
module is MISSING, a local placeholder (_local_*: ground + sun + world; two block rigs with the contract bone
names; Workbench/EEVEE presets) is used and reported under report["stubs"]. A module that exists but fails
raises (--fallback: placeholder instead).
"""

from codecinema.productions import film_root, source_root
import argparse
import hashlib
import importlib
import inspect
import json
import math
import os
import re
import sys
import time
import traceback

ROOT = str(film_root("silvergrass"))
for _p in (os.path.join(str(source_root("silvergrass")), "common"), os.path.join(str(source_root("silvergrass")), "blender")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
import config  # noqa: E402
import bl_util as U  # noqa: E402
import fxclock  # noqa: E402
import lane_tools as LT  # noqa: E402
import events as EV  # noqa: E402
import cameras as C  # noqa: E402
import acts  # noqa: E402

HANDOFF_TOL = 0.5          # m
FACING_TOL = 30.0          # deg (warning only)
CLASH_GATE = 0.05          # m (Pipeline rule 9: 3-5 cm)
SMEAR_MOVE, SMEAR_JUMP = 0.05, 0.30   # m: half-frame move before a cut / jump across it
SMEAR_RATIO = 2.0                    # a jump is > 2x the neighbouring frames' moves (else: fast motion)


def _optional(name):
    """Import a module other lanes own; None if it does not exist yet (a broken module raises)."""
    try:
        return importlib.import_module(name)
    except ImportError as e:
        if getattr(e, "name", None) == name:
            return None
        raise


def _discard_new(before_objects, before_collections):
    """Remove objects/collections created since the snapshot (a real module failed half-way)."""
    for ob in [o for o in bpy.data.objects if o.name not in before_objects]:
        bpy.data.objects.remove(ob, do_unlink=True)
    for col in [c for c in bpy.data.collections if c.name not in before_collections]:
        bpy.data.collections.remove(col)


def _real_or_stub(report, key, mod, fn_name, stub, forced, **kw):
    """Run mod.<fn_name>(**kw) or the local placeholder. Falls back (with a warning) when the module is missing,
    forced via --stubs, or raises NotImplementedError (module still being written); other errors raise."""
    if mod is None or key in forced or not hasattr(mod, fn_name):
        report["stubs"][key] = True
        return stub()
    objs, cols = set(o.name for o in bpy.data.objects), set(c.name for c in bpy.data.collections)
    try:
        res = _call(getattr(mod, fn_name), **kw)
        report["stubs"][key] = False
        return res
    except NotImplementedError as e:
        report["warnings"].append(f"{key}.{fn_name} not implemented yet ({e}) -> local placeholder")
        _discard_new(objs, cols)
        report["stubs"][key] = True
        return stub()
    except Exception as e:                       # noqa: BLE001 - only with --fallback (module mid-edit)
        if not report.get("fallback"):
            raise
        report["warnings"].append(f"{key}.{fn_name} FAILED ({type(e).__name__}: {e}) -> local placeholder "
                                  f"(--fallback)")
        print(f"[build] WARNING {key}.{fn_name} failed -> placeholder:\n{traceback.format_exc()}", flush=True)
        _discard_new(objs, cols)
        report["stubs"][key] = True
        return stub()


def _env_hook(report, env_mod, name, *args):
    """Call an optional environment hook (bind_characters, key_lane_defaults); tolerate missing /
    not-yet-implemented ones (noted in the report)."""
    fn = getattr(env_mod, name, None) if env_mod is not None else None
    if fn is None:
        return None
    try:
        return fn(*args)
    except NotImplementedError as e:
        msg = f"environment.{name} not implemented yet ({e})"
        if msg not in report["warnings"]:
            report["warnings"].append(msg)
        return None


def _call(fn, **kw):
    """Call fn with only the keyword arguments it accepts."""
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return fn()
    if any(p.kind == p.VAR_KEYWORD for p in params.values()):
        return fn(**kw)
    return fn(**{k: v for k, v in kw.items() if k in params})


# =============================================================================================
# local placeholders (used only while the real modules do not exist)
# =============================================================================================
STUB_BONES = [
    # name, head, tail, parent  (unit figure 1.8 m tall, faces -Y, .L = +X)
    ("hips", (0, 0, 0.95), (0, 0, 1.05), None), ("spine", (0, 0, 1.05), (0, 0, 1.25), "hips"),
    ("chest", (0, 0, 1.25), (0, 0, 1.45), "spine"), ("neck", (0, 0, 1.45), (0, 0, 1.55), "chest"),
    ("head", (0, 0, 1.55), (0, 0, 1.78), "neck"),
    ("shoulder.L", (0.02, 0, 1.42), (0.18, 0, 1.42), "chest"), ("shoulder.R", (-0.02, 0, 1.42), (-0.18, 0, 1.42), "chest"),
    ("upper_arm.L", (0.18, 0, 1.42), (0.30, 0.03, 1.16), "shoulder.L"),
    ("upper_arm.R", (-0.18, 0, 1.42), (-0.30, 0.03, 1.16), "shoulder.R"),
    ("forearm.L", (0.30, 0.03, 1.16), (0.38, -0.02, 0.93), "upper_arm.L"),
    ("forearm.R", (-0.30, 0.03, 1.16), (-0.38, -0.02, 0.93), "upper_arm.R"),
    ("hand.L", (0.38, -0.02, 0.93), (0.40, -0.05, 0.85), "forearm.L"),
    ("hand.R", (-0.38, -0.02, 0.93), (-0.40, -0.05, 0.85), "forearm.R"),
    ("weapon.R", (-0.40, -0.05, 0.85), (-0.40, -0.20, 0.87), "hand.R"),
    ("thigh.L", (0.10, 0, 0.95), (0.11, -0.03, 0.52), "hips"), ("thigh.R", (-0.10, 0, 0.95), (-0.11, -0.03, 0.52), "hips"),
    ("shin.L", (0.11, -0.03, 0.52), (0.11, 0.0, 0.10), "thigh.L"), ("shin.R", (-0.11, -0.03, 0.52), (-0.11, 0.0, 0.10), "thigh.R"),
    ("foot.L", (0.11, 0.0, 0.10), (0.11, -0.12, 0.03), "shin.L"), ("foot.R", (-0.11, 0.0, 0.10), (-0.11, -0.12, 0.03), "shin.R"),
    ("toe.L", (0.11, -0.12, 0.03), (0.11, -0.18, 0.02), "foot.L"), ("toe.R", (-0.11, -0.12, 0.03), (-0.11, -0.18, 0.02), "foot.R"),
]
STUB_WIDTH = {"hips": 0.30, "spine": 0.28, "chest": 0.36, "neck": 0.10, "head": 0.20, "shoulder": 0.09,
              "upper_arm": 0.09, "forearm": 0.08, "hand": 0.07, "thigh": 0.13, "shin": 0.10, "foot": 0.08, "toe": 0.07}


def _box_along_y(name, length, w, d, color, collection):
    v = [(x * w / 2, y * length, z * d / 2) for y in (0, 1) for x in (-1, 1) for z in (-1, 1)]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    mat = bpy.data.materials.get("STUB_" + name.split("_")[0]) or U.new_material("STUB_" + name.split("_")[0], color[:3])
    ob = U.mesh_from_data(name, v, faces=f, collection=collection, materials=[mat])
    ob.color = tuple(color[:3]) + (1.0,)
    return ob


def _local_stub_characters():
    """Placeholder rigs with the contract names: SHINOBI_rig / SAINT_rig (facing -Y at rotation 0, origin at the
    feet), block meshes parented to the bones, katana '<C>_katana_hand' on weapon.R with '<C>_katana_tip' /
    '<C>_katana_base' sockets. Placed at the config start positions (shinobi faces +Y)."""
    col = U.ensure_collection("CHARACTERS")
    out = dict(props={}, stub=True)
    spec = dict(shinobi=("SHINOBI", config.SHINOBI_HEIGHT, (0.16, 0.22, 0.40), config.SHINOBI_START, 180.0),
                saint=("SAINT", config.SAINT_HEIGHT, (0.62, 0.42, 0.14), config.SAINT_START, 0.0))
    for who, (C_, h, color, start, facing) in spec.items():
        k = h / 1.8
        bones = [dict(name=n, head=tuple(c * k for c in hd), tail=tuple(c * k for c in tl), parent=p,
                      connect=False) for n, hd, tl, p in STUB_BONES]
        rig = U.build_armature(f"{C_}_rig", bones, collection=col)
        for pb in rig.pose.bones:
            pb.rotation_mode = 'XYZ'
        rig.location = (start[0], start[1], 0.0)
        rig.rotation_euler = (0, 0, math.radians(facing))
        bpy.context.view_layer.update()
        for b in rig.data.bones:
            base = b.name.split(".")[0]
            if base not in STUB_WIDTH:
                continue
            w = STUB_WIDTH[base] * k
            part = _box_along_y(f"{C_}_stub_{b.name}", b.length, w, w * 0.8,
                                (0.5, 0.05, 0.04) if (who == "shinobi" and base == "head") else color, col)
            part.matrix_world = rig.matrix_world @ b.matrix_local
            U.parent_to_bone(part, rig, b.name, keep_world=True)
        wb = rig.data.bones["weapon.R"]
        blade = _box_along_y(f"{C_}_katana_hand", 1.0 * k, 0.035, 0.012, (0.8, 0.8, 0.85), col)
        blade.matrix_world = rig.matrix_world @ wb.matrix_local
        U.parent_to_bone(blade, rig, "weapon.R", keep_world=True)
        tip = U.new_empty(f"{C_}_katana_tip", (0, 0, 0), col, size=0.05)
        base_e = U.new_empty(f"{C_}_katana_base", (0, 0, 0), col, size=0.05)
        for e, y in ((tip, 1.0 * k), (base_e, 0.03)):
            e.parent = blade
            e.location = (0, y, 0)
        out[who] = rig
        out["props"].update({blade.name: blade, tip.name: tip, base_e.name: base_e})
    return out


def _local_stub_env():
    """Placeholder environment: 400 m ground, a low warm sun, a gradient world. Returns dict(stub=True, ...)."""
    col = U.ensure_collection("ENVIRONMENT")
    s = 200.0
    mat = U.new_material("STUB_ground", config.PALETTE["grass_dusk"], rough=0.9)
    ground = U.mesh_from_data("ENV_ground", [(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], faces=[(0, 1, 2, 3)],
                              collection=col, materials=[mat])
    ground.color = (0.55, 0.45, 0.25, 1.0)
    sun_d = bpy.data.lights.new("ENV_sun", 'SUN')
    sun_d.energy = 3.0
    sun_d.color = (1.0, 0.75, 0.5)
    sun_d.angle = math.radians(1.0)
    sun = U.new_object("ENV_sun", sun_d, col)
    sun.rotation_euler = (math.radians(75), 0, math.radians(100))
    w = bpy.data.worlds.new("ENV_world")
    bpy.context.scene.world = w
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.9, 0.45, 0.18, 1.0)
    bg.inputs["Strength"].default_value = 0.6
    return dict(ground=ground, sun=sun, world=w, stub=True)


def _local_configure(quality, scene=None):
    """Placeholder render presets (Pipeline rule 14): layout (Workbench, object colours, preview scale),
    preview (EEVEE, preview scale + samples, no motion blur), final (EEVEE full res, final samples, motion blur
    START per config.MOTION_BLUR). Same config keys as render_setup."""
    sc = scene or bpy.context.scene
    r = sc.render
    r.resolution_x, r.resolution_y = config.RES_X, config.RES_Y
    r.fps, r.fps_base = config.FPS, 1.0
    r.motion_blur_position = 'START'
    U.configure_png(sc)
    r.filepath = config.FRAME_PATTERN
    if quality == "layout":
        r.engine = 'BLENDER_WORKBENCH'
        r.resolution_percentage = int(round(config.PREVIEW_SCALE * 100))
        sh = sc.display.shading
        sh.light = 'STUDIO'
        sh.color_type = 'OBJECT'
        sh.show_shadows = True
        sh.show_object_outline = True
        r.use_motion_blur = False
        sc.view_settings.view_transform = 'Standard'
    else:
        r.engine = 'BLENDER_EEVEE'
        E = sc.eevee
        sc.view_settings.view_transform = 'AgX'
        E.shadow_pool_size = str(config.SHADOW_POOL_MB)
        if quality == "preview":
            r.resolution_percentage = int(round(config.PREVIEW_SCALE * 100))
            E.taa_render_samples = config.RENDER_SAMPLES["preview"]
            r.use_motion_blur = False
        else:
            r.resolution_percentage = 100
            E.taa_render_samples = config.RENDER_SAMPLES["final"]
            r.filter_size = config.RENDER_FILTER
            E.use_fast_gi = True
            E.use_raytracing = False
            r.use_motion_blur = config.MOTION_BLUR
            r.motion_blur_shutter = config.MB_SHUTTER
            E.motion_blur_steps = config.MB_STEPS
            E.motion_blur_max = config.MB_MAX
    return dict(quality=quality, stub=True)


def _local_apply_shot_overrides(scene, frame, quality):
    """Placeholder for render_setup.apply_shot_overrides: config.SHOT_RENDER mb_steps/samples (final only)."""
    s = config.shot_at(frame)
    ov = config.SHOT_RENDER.get(s["id"], {}) if s else {}
    if quality == "final" and scene.render.engine == 'BLENDER_EEVEE':
        scene.eevee.motion_blur_steps = int(ov.get("mb_steps", config.MB_STEPS))
        if "samples" in ov:
            scene.eevee.taa_render_samples = int(ov["samples"])
    return ov


# =============================================================================================
# helpers
# =============================================================================================
def source_hashes():
    """{relative path: sha1[:16]} of every source that can change the scene (render fingerprints)."""
    out = {}
    for d in (os.path.join(config.SRC, "common"), os.path.join(config.SRC, "blender"),
              os.path.join(config.SRC, "blender", "acts")):
        for f in sorted(os.listdir(d)):
            if f.endswith(".py"):
                p = os.path.join(d, f)
                with open(p, "rb") as fh:
                    out[os.path.relpath(p, config.ROOT)] = hashlib.sha1(fh.read()).hexdigest()[:16]
    with open(os.path.join(config.ROOT, "story.json"), "rb") as fh:
        out["story.json"] = hashlib.sha1(fh.read()).hexdigest()[:16]
    return out


class _Timer:
    def __init__(self, report, name):
        self.report, self.name = report, name

    def __enter__(self):
        self.t0 = time.time()
        print(f"[build] >> {self.name}", flush=True)
        return self

    def __exit__(self, *exc):
        dt = round(time.time() - self.t0, 2)
        self.report["timings"][self.name] = dt
        print(f"[build] << {self.name} {dt:.2f}s", flush=True)
        return False


def _merge_spans(spans):
    out = []
    for a, b in sorted(spans):
        if out and a <= out[-1][1] + 1:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def memo_wind(wind_at):
    """environment.wind_at evaluates the scene (frame_set) on every call and apply_secondary_motion asks once per
    frame per chain: evaluate each frame once and share it between chains and rigs."""
    cache = {}

    def wind(frame):
        k = round(float(frame), 4)
        if k not in cache:
            cache[k] = wind_at(frame)
        return cache[k]
    wind.cache = cache
    return wind


def _facing_of(rig):
    f = rig.matrix_world.to_3x3() @ Vector((0, -1, 0))
    return math.degrees(math.atan2(f.x, -f.y)) % 360.0


def _angle_diff(a, b):
    return abs((a - b + 180.0) % 360.0 - 180.0)


# =============================================================================================
# global QA
# =============================================================================================
def handoff_props(who, state):
    """{prop object name: should be visible} for a character's HANDOFF state: katana
    'drawn' | 'sheathed' -> <C>_katana_hand / <C>_katana_sheathed; the elder's hat, haori / tasuki (tasuki
    defaults to 'not haori'), spear 'slung' | 'in_hand' | 'world' | 'gone' -> SAINT_spear_slung / _hand / _world."""
    C_ = "SHINOBI" if who == "shinobi" else "SAINT"
    exp = {}
    if "katana" in state:
        exp[f"{C_}_katana_hand"] = state["katana"] == "drawn"
        exp[f"{C_}_katana_sheathed"] = state["katana"] == "sheathed"
    if who == "saint":
        if "hat" in state:
            exp["SAINT_hat"] = bool(state["hat"])
        if "haori" in state:
            exp["SAINT_haori"] = bool(state["haori"])
        tas = state.get("tasuki", (not state["haori"]) if "haori" in state else None)
        if tas is not None:
            exp["SAINT_tasuki"] = bool(tas)
        sp = state.get("spear")
        if sp is not None:
            exp["SAINT_spear_slung"] = sp == "slung"
            exp["SAINT_spear_hand"] = sp == "in_hand"
            exp["SAINT_spear_world"] = sp == "world"
    return exp


def _pose_distance(rig, pose):
    """Max |angle difference| (deg) between the rig's current bone rotations and a POSES entry (INFO)."""
    worst = 0.0
    for bone, rot in pose.items():
        pb = rig.pose.bones.get(bone) if rig.pose is not None else None
        if pb is None or not isinstance(rot, (tuple, list)) or len(rot) != 3:
            continue
        cur = [math.degrees(a) for a in pb.rotation_euler]
        worst = max(worst, max(_angle_diff(c, float(w)) for c, w in zip(cur, rot)))
    return round(worst, 1)


def qa_handoffs(lane_spans):
    """At each lane boundary b of config.HANDOFF (frame b if a built lane ends there, b + 1 if one starts there):
    rig positions (FAIL beyond 0.5 m) + facing (WARN beyond 30 deg), the discrete prop states of the prop
    contract (katana hand/sheathed, hat, haori/tasuki, spear slung/hand/world: FAIL on a mismatch; missing
    props are INFO) and the named pose (INFO: max joint difference to poses.POSES[name] when poses exists)."""
    sc = bpy.context.scene
    rigs = {w: bpy.data.objects.get(n) for w, n in C.RIGS.items()}
    poses_mod = _optional("poses")
    pose_lib = getattr(poses_mod, "POSES", {}) if poses_mod is not None else {}
    items = []
    for b, state in sorted(config.HANDOFF.items()):
        frames = sorted({f for (s, e) in lane_spans.values() for f in ((b,) if e == b else ()) + ((b + 1,) if s == b + 1 else ())})
        for f in frames:
            sc.frame_set(f)
            for who, rig in rigs.items():
                if rig is None or who not in state:
                    continue
                want = state[who]
                p = rig.matrix_world.translation
                d = math.hypot(p.x - want["pos"][0], p.y - want["pos"][1])
                fa = _facing_of(rig)
                df = _angle_diff(fa, want.get("facing", fa))
                st = "PASS" if d <= HANDOFF_TOL else "FAIL"
                if st == "PASS" and df > FACING_TOL:
                    st = "WARN"
                items.append(dict(boundary=b, frame=f, who=who, check="position", pos=[round(p.x, 3), round(p.y, 3)],
                                  want=list(want["pos"]), dist=round(d, 3), facing=round(fa, 1),
                                  facing_want=want.get("facing"), status=st))
                for prop, vis_want in handoff_props(who, want).items():
                    ob = bpy.data.objects.get(prop)
                    if ob is None:
                        items.append(dict(boundary=b, frame=f, who=who, check="prop", prop=prop, status="INFO",
                                          note="prop object missing"))
                        continue
                    vis = not ob.hide_render
                    items.append(dict(boundary=b, frame=f, who=who, check="prop", prop=prop, visible=vis,
                                      want_visible=vis_want, status="PASS" if vis == vis_want else "FAIL"))
                if want.get("pose"):
                    it = dict(boundary=b, frame=f, who=who, check="pose", pose=want["pose"], status="INFO")
                    if want["pose"] in pose_lib and rig.pose is not None:
                        it["max_joint_diff_deg"] = _pose_distance(rig, pose_lib[want["pose"]])
                    else:
                        it["note"] = "poses.POSES has no such entry" if poses_mod is not None else "poses.py missing"
                    items.append(it)
    return items


def _cut_ranges(sc):
    ms = sorted((m for m in sc.timeline_markers if m.camera is not None), key=lambda m: m.frame)
    return [(m.name, m.frame, m.camera) for m in ms]


def qa_markers(shots, lane_spans):
    """A camera marker at every shot start (shots fully inside RENDER_SKIP exempt); stray / camera-less /
    duplicate markers; cut coverage: every cut's planned last frame (camera['cut_f1']) must be the frame before
    the next marker (or the end of its built span) - a gap means the camera silently overstays, an overlap that
    the next cut starts early."""
    sc = bpy.context.scene
    ms = [(m.name, m.frame, m.camera) for m in sc.timeline_markers]
    missing = []
    for s in shots:
        if any(a <= s["start"] and s["end"] <= b for a, b in config.RENDER_SKIP):
            continue
        if not any(f == s["start"] and cam is not None for _, f, cam in ms):
            missing.append(dict(shot=s["id"], start=s["start"]))
    spans = list(lane_spans.values())
    merged = _merge_spans(spans)
    stray = [dict(name=n, frame=f) for n, f, _ in ms if not any(a <= f <= b for a, b in spans)]
    nocam = [dict(name=n, frame=f) for n, f, cam in ms if cam is None]
    frames = [f for _, f, _ in ms]
    dup = sorted({f for f in frames if frames.count(f) > 1})
    coverage = []
    cuts = [c for c in _cut_ranges(sc) if any(a <= c[1] <= b for a, b in merged)]
    for i, (name, f0, cam) in enumerate(cuts):
        if "cut_f1" not in cam.keys():
            continue
        span_end = next(b for a, b in merged if a <= f0 <= b)
        nxt = cuts[i + 1][1] if i + 1 < len(cuts) and cuts[i + 1][1] <= span_end else None
        want = (nxt - 1) if nxt is not None else span_end
        got = int(cam["cut_f1"])
        if got != want:
            coverage.append(dict(cut=name, start=f0, cut_f1=got, expected=want,
                                 problem="gap: camera overstays" if got < want else "overlap: next cut starts early"))
    return dict(missing_shot_markers=missing, stray=stray, no_camera=nocam, duplicate_frames=dup,
                cut_coverage=coverage,
                status="PASS" if not (missing or stray or dup or coverage) else "FAIL")


def qa_lane_objects(lane_reports, lane_spans):
    """Objects a lane created must not render outside its span: each new renderable object of a lane is sampled
    at frames outside [s - 6, e + 6] (config shot starts/ends, the other built lanes' edges, the film's ends).
    Visible there -> FAIL (objects filed in LANE_<lane>) / INFO (objects of shared modules such as vfx, or
    ob['persist'] = True)."""
    sc = bpy.context.scene
    marks = {config.FRAME_START, config.FRAME_END}
    for s_ in config.SHOTS:
        marks |= {s_["start"], s_["end"]}
    for a, b in lane_spans.values():
        marks |= {a, b}
    items = []
    for ln, rep in lane_reports.items():
        s, e = lane_spans[ln]
        frames = sorted(f for f in marks if not (s - 6 <= f <= e + 6))
        obs = [bpy.data.objects.get(n) for n in rep.get("new_object_names", [])]
        obs = [o for o in obs if o is not None and o.type in RENDERABLE]
        if not obs or not frames:
            continue
        leaks = {}
        for f in frames:
            sc.frame_set(f)
            for o in obs:
                if not o.hide_render:
                    leaks.setdefault(o.name, []).append(f)
        for name, fs in sorted(leaks.items()):
            o = bpy.data.objects[name]
            own = any(c.name == LT.LANE_PREFIX + ln for c in o.users_collection)
            st = "FAIL" if own and not o.get("persist") else "INFO"
            items.append(dict(lane=ln, object=name, visible_at=fs[:12], n_frames=len(fs), status=st,
                              note="lane object visible outside its lane" if st == "FAIL" else
                              ("persist=True" if o.get("persist") else "module-owned object (vfx/env)")))
    return dict(status="FAIL" if any(i["status"] == "FAIL" for i in items) else "PASS", items=items)


def qa_clashes():
    """Clash gate via moves.clash_report() (list of dicts with 'gap' metres) when moves provides it."""
    mv = _optional("moves")
    fn = getattr(mv, "clash_report", None) if mv is not None else None
    if fn is None:
        return dict(status="SKIP", reason="moves.clash_report() not available")
    rep = fn() or []
    rep = [dict(r) if isinstance(r, dict) else dict(value=str(r)) for r in rep]
    fails = [r for r in rep if float(r.get("gap", 0.0) or 0.0) > CLASH_GATE]
    return dict(status="FAIL" if fails else "PASS", clashes=len(rep), over_gate=fails[:50])


def qa_cut_smear(lane_spans):
    """Objects that jump across an intra-lane cut while their key before the cut is not CONSTANT: sampled at
    f-1, f-0.5, f for every cut marker f (START shutter of frame f-1 covers [f-1, f-0.5]).  A jump is a
    DISCONTINUITY: the move f-1 -> f must also exceed SMEAR_RATIO x the moves of the neighbouring frames
    (f-2 -> f-1, f -> f+1), so genuinely fast motion that happens to span a cut (a leap landing, a dash) is not
    reported as a teleport."""
    sc = bpy.context.scene
    cuts = sorted({m.frame for m in sc.timeline_markers if m.camera is not None})
    cuts = [f for f in cuts if any(a < f <= b for a, b in lane_spans.values())]
    objs = [o for o in bpy.data.objects if o.parent is None and o.type in ('ARMATURE', 'MESH', 'CURVE', 'EMPTY')
            and o.animation_data is not None and o.type != 'CAMERA' and not o.name.endswith(("_cam", "_shake", "_aim"))]
    out = []
    for f in cuts:
        pos = {}
        for t in (f - 2.0, f - 1.0, f - 0.5, float(f), f + 1.0):
            U.frame_set(t)
            for o in objs:
                pos.setdefault(o.name, []).append(U.world_pos_of(o).copy())
        U.frame_set(f - 1)
        for o in objs:
            pm, p0, ph, p1, pp = pos[o.name]
            around = max((p0 - pm).length, (pp - p1).length)
            if ((p1 - p0).length > SMEAR_JUMP and (ph - p0).length > SMEAR_MOVE
                    and (p1 - p0).length > SMEAR_RATIO * around and not o.hide_render):
                out.append(dict(cut_frame=f, object=o.name, jump=round((p1 - p0).length, 3),
                                half_frame_move=round((ph - p0).length, 3)))
    return dict(status="WARN" if out else "PASS", smears=out)      # run_qa upgrades to FAIL (full / --strict)


def run_qa(report, lane_spans, shots, qa_dir, smear_fails=False):
    """Global QA (Pipeline rule 13); smear_fails: cut smears count as FAILs (full builds, --strict)."""
    os.makedirs(qa_dir, exist_ok=True)
    r = bpy.context.scene.render
    qa = dict(resolution=[r.resolution_x, r.resolution_y, r.resolution_percentage,
                          round(r.resolution_x * r.pixel_aspect_x / (r.resolution_y * r.pixel_aspect_y), 4)])
    with U.muted_modifiers():
        qa["handoffs"] = qa_handoffs(lane_spans)
        qa["markers"] = qa_markers(shots, lane_spans)
        qa["clashes"] = qa_clashes()
        qa["cut_smear"] = qa_cut_smear(lane_spans)
        if smear_fails and qa["cut_smear"]["smears"]:
            qa["cut_smear"]["status"] = "FAIL"
        qa["lane_objects"] = qa_lane_objects(report.get("lane_reports", {}), lane_spans)
    cuts = [c for c in C.cut_list() if any(a <= c[1] <= b for a, b in lane_spans.values())]
    have_rigs = all(bpy.data.objects.get(n) for n in C.RIGS.values())
    if have_rigs and cuts:
        sd = C.check_screen_direction(os.path.join(qa_dir, "screen_direction.json"), cuts=cuts)
        qa["screen_direction"] = dict(passed=sd["passed"], failed=sd["failed"], skipped=sd["skipped"],
                                      fails=[i for i in sd["items"] if i["status"] == "FAIL"][:40])
        fr = C.framing_qa(os.path.join(qa_dir, "framing.json"), cuts=cuts)
        qa["framing"] = dict(fails=fr["fails"], warns=fr["warns"],
                             flagged=[dict(cut=i["cut"], frame=i["frame"], flags=i["flags"])
                                      for i in fr["items"] if i["flags"]][:60])
    else:
        qa["screen_direction"] = qa["framing"] = dict(status="SKIP", reason="no rigs or no cuts")
    with open(os.path.join(qa_dir, "handoffs.json"), "w") as f:
        json.dump(qa["handoffs"], f, indent=1)
    n_fail = sum(1 for h in qa["handoffs"] if h["status"] == "FAIL")
    n_fail += qa["markers"]["status"] == "FAIL"
    n_fail += qa["clashes"].get("status") == "FAIL"
    n_fail += qa["screen_direction"].get("failed", 0) or 0
    n_fail += qa["framing"].get("fails", 0) or 0
    n_fail += len(qa["cut_smear"]["smears"]) if qa["cut_smear"]["status"] == "FAIL" else 0
    n_fail += sum(1 for i in qa["lane_objects"]["items"] if i["status"] == "FAIL")
    qa["fail_count"] = int(n_fail)
    report["qa"] = qa
    return qa


# =============================================================================================
# the build
# =============================================================================================
def resolve_lanes(spec):
    """'all' | 'a,b' -> (lanes, partial). 'all' = every real lane whose module exists (missing ones warned)."""
    have = acts.available_lanes()
    if spec in (None, "", "all"):
        lanes = [ln for ln in config.LANES if ln in have]
        return lanes, lanes != list(config.LANES)
    lanes = [x.strip() for x in spec.split(",") if x.strip()]
    for ln in lanes:
        if ln not in have:
            raise SystemExit(f"build_scene: no lane module acts/{ln}.py (have: {have})")
    order = {ln: i for i, ln in enumerate(config.LANES)}
    lanes.sort(key=lambda ln: (order.get(ln, 99), ln))
    return lanes, True


SCENE_BLEND_NAME = os.path.basename(config.SCENE_BLEND)            # scene.blend (in every output dir)
EVENTS_JSON_NAME = os.path.basename(config.EVENTS_JSON)            # events.json
EVENTS_STAGED_NAME = EVENTS_JSON_NAME + ".building"                # renamed to EVENTS_JSON_NAME on success
QA_DIRNAME = "qa"                                                  # <out>/qa/*.json
OUTPUT_FILES = (SCENE_BLEND_NAME, EVENTS_JSON_NAME)   # removed at the start of a build (no stale results)


def _clear_outputs(out_dir):
    """Delete the previous build's blend + events of this output dir, so a failed build can never leave a stale
    scene behind that looks like a fresh one (lane_preview / the supervisor would render it)."""
    removed = []
    for name in OUTPUT_FILES + (EVENTS_STAGED_NAME,):
        p = os.path.join(out_dir, name)
        if os.path.exists(p):
            os.remove(p)
            removed.append(name)
    return removed


def build(lanes="all", quality=None, out_dir=None, save=True, qa=True, strict=False, stubs=(),
          fallback=False, digest=True):
    """Build the scene for `lanes` ('all' or 'a,b' or a list) at `quality`; returns the build report dict.
    quality None -> 'final' for a full build, 'preview' for a partial one.
    stubs: module names forced to their local placeholders (environment, characters, vfx, render_setup, moves).
    fallback: a real environment/characters module that raises is replaced by its placeholder (warned) instead
    of aborting the build - for lane previews while a shared module is mid-edit.
    digest: compute the per-shot content digests (build_report['shot_digest']) used by the render supervisor.
    The previous <out>/scene.blend + events.json are deleted first; the report is written with status
    'running' at once, 'failed' (+ 'error') when anything raises (the exception propagates -> non-zero exit via
    main()), 'ok' at the end."""
    t_start = time.time()
    lane_list, partial = resolve_lanes(",".join(lanes) if isinstance(lanes, (list, tuple)) else lanes)
    if not lane_list:
        raise SystemExit(f"build_scene: no lane modules to build (acts/ has {acts.available_lanes()})")
    if quality is None:
        quality = "preview" if partial else "final"
    if out_dir is None:
        out_dir = config.lane_dir("+".join(lane_list)) if partial else config.OUT
    os.makedirs(out_dir, exist_ok=True)
    report = dict(status="running", lanes=lane_list, partial=partial, quality=quality, out_dir=out_dir,
                  timings={}, stubs={}, fallback=bool(fallback),
                  warnings=[], lane_reports={}, started=time.strftime("%Y-%m-%d %H:%M:%S"),
                  blender=bpy.app.version_string, pid=os.getpid(), sources=source_hashes())
    report["strict"] = bool(strict)
    report["removed_outputs"] = _clear_outputs(out_dir)
    _write_report(report, out_dir)
    try:
        _build(report, lane_list, partial, quality, out_dir, save, qa, stubs, fallback, digest)
    except BaseException as e:
        if isinstance(e, SystemExit) and e.code in (None, 0):
            raise
        report["status"] = "failed"
        report.setdefault("error", f"{type(e).__name__}: {e}\n{traceback.format_exc()}")
        report["seconds"] = round(time.time() - t_start, 2)
        report["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _write_report(report, out_dir)
        print(f"[build] FAILED after {report['seconds']:.1f}s: {type(e).__name__}: {e}", flush=True)
        raise
    report["status"] = "ok"
    report["seconds"] = round(time.time() - t_start, 2)
    report["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _write_report(report, out_dir)
    n_fail = report.get("qa", {}).get("fail_count", 0)
    print(f"[build] done {lane_list} quality={quality} in {report['seconds']:.1f}s; QA fails: {n_fail}; "
          f"warnings: {len(report['warnings'])}; stubs: {[k for k, v in report['stubs'].items() if v]}", flush=True)
    if strict and n_fail:
        raise SystemExit(2)
    return report


def _build(report, lane_list, partial, quality, out_dir, save, qa, stubs, fallback, digest):
    """The pass order of Pipeline rule 13 (see build())."""
    if not partial and set(lane_list) != set(config.LANES):
        report["warnings"].append(f"full build without lanes {sorted(set(config.LANES) - set(lane_list))}")
    U.clear_scene(config.FPS)
    LT.reset()
    EV.clear()
    C.reset()
    sc = bpy.context.scene
    # the film's 2.35:1 frame from the start: QA projections + events 'onscreen' use the render aspect
    sc.render.resolution_x, sc.render.resolution_y = config.RES_X, config.RES_Y
    sc.render.pixel_aspect_x = sc.render.pixel_aspect_y = 1.0
    sc.render.resolution_percentage = 100
    mods = {ln: acts.lane_module(ln) for ln in lane_list}
    lane_spans = {ln: acts.lane_span(ln, mods[ln]) for ln in lane_list}
    shots = [s for ln in lane_list for s in acts.lane_shots(ln, mods[ln])]
    if partial:
        sc.frame_start = min(a for a, _ in lane_spans.values())
        sc.frame_end = max(b for _, b in lane_spans.values())
    else:
        sc.frame_start, sc.frame_end = config.FRAME_START, config.FRAME_END
    sc.render.motion_blur_position = 'START'
    report["frame_range"] = [sc.frame_start, sc.frame_end]
    report["shots"] = [dict(id=s_["id"], start=s_["start"], end=s_["end"], lane=s_.get("lane", ln))
                       for ln in lane_list for s_ in acts.lane_shots(ln, mods[ln])]
    report["lane_spans"] = {ln: list(v) for ln, v in lane_spans.items()}

    forced = set(stubs or ())
    env_mod = None if "environment" in forced else _optional("environment")
    chars_mod = None if "characters" in forced else _optional("characters")
    density = config.GRASS_DENSITY[quality]                  # Pipeline rule 8/14: preview grass x0.25
    with _Timer(report, "env.build"):
        env = _real_or_stub(report, "environment", env_mod, "build", _local_stub_env, forced, quality=quality,
                            density=density, scene=sc)
    if report["stubs"]["environment"]:
        env_mod = None
    with _Timer(report, "characters.build"):
        chars = _real_or_stub(report, "characters", chars_mod, "build", _local_stub_characters, forced,
                              quality=quality)
    if report["stubs"]["characters"]:
        chars_mod = None
    _env_hook(report, env_mod, "bind_characters")               # grass parting -> the rigs
    for name in ("vfx", "render_setup", "moves", "poses"):
        report["stubs"][name] = name in forced or _optional(name) is None
    with _Timer(report, "fxclock"):
        fxclock.ensure_clock(sc)
    for ln in lane_list:
        ctx = dict(chars=chars, env=env, config=config, lane=ln, span=lane_spans[ln], quality=quality,
                   shots=acts.lane_shots(ln, mods[ln]), stubs=dict(report["stubs"]))
        with _Timer(report, f"lane:{ln}"):
            LT.begin_lane(ln, span=lane_spans[ln])
            # complete default env timeline inside the lane's strip (environment.py design note)
            _env_hook(report, env_mod, "key_lane_defaults", ln if ln in config.LANES else lane_spans[ln])
            # lanes key + sample the rigs (moves / characters evaluate the depsgraph thousands of times: IK scans,
            # foot bakes, clash resolution); the GN grass / effects re-evaluate on every rig change unless muted
            # (x10+ slower at final grass density) and nothing a lane samples depends on GN output
            with U.muted_modifiers():
                try:
                    mods[ln].build(ctx)
                except Exception:
                    LT._STATE["current"] = None
                    report["error"] = f"lane {ln} failed:\n{traceback.format_exc()}"
                    _write_report(report, out_dir)
                    raise
                report["lane_reports"][ln] = LT.end_lane(ln)
    with _Timer(report, "assemble_nla"):
        report["assemble"] = LT.assemble_nla(lane_list)
        report["warnings"] += [f"unstashed keys: {u}" for u in report["assemble"]["unstashed"]]
        left = C.resolve_pending()                     # aims of cameras created outside any lane
        if left:
            report["warnings"].append(f"{left} camera aim keys resolved after assembly (created outside a lane)")
        clock = U.fcurve(sc, f'["{fxclock.PROP}"]', 0)
        if clock is None or len(clock.keyframe_points) < 2:
            report["warnings"].append("fx_time clock missing after assembly -> rebuilt")
            fxclock.ensure_clock(sc)
    with _Timer(report, "env.finalize"):
        # post-assembly env pass (environment.finalize docstring): grass wake behind both rigs over the built
        # spans (needs the final rig motion) + default lightning-flash directions from the marker cameras
        if env_mod is not None and hasattr(env_mod, "finalize"):
            spans = _merge_spans(lane_spans.values())
            report["env_finalize"] = _call(env_mod.finalize, scene=sc, wake=True,
                                           span=(min(a for a, _ in spans), max(b for _, b in spans)))
    with _Timer(report, "secondary_motion"):
        fn = getattr(chars_mod, "apply_secondary_motion", None) if chars_mod is not None else None
        wind = None
        if fn is not None:
            wind = getattr(env_mod, "wind_at", None) if env_mod is not None else None
            wind = memo_wind(wind) if wind is not None else None
            with U.muted_modifiers():
                for f0, f1 in _merge_spans(lane_spans.values()):
                    for who in ("shinobi", "saint"):
                        rig = chars.get(who) if isinstance(chars, dict) else None
                        if rig is not None:
                            try:
                                fn(rig, f0, f1, wind=wind if wind is not None else 1.0)
                            except NotImplementedError as e:
                                report["warnings"].append(f"apply_secondary_motion not implemented ({e})")
                                report["stubs"]["secondary_motion"] = True
        else:
            report["stubs"]["secondary_motion"] = True
        if wind is not None:
            report["wind_frames_evaluated"] = len(wind.cache)
        masks = LT.apply_secondary_masks()
        if masks:
            report["secondary_masks"] = masks
    with _Timer(report, "vfx.finalize"):
        vfx = None if "vfx" in forced else _optional("vfx")
        if vfx is not None and hasattr(vfx, "finalize"):
            try:
                vfx.finalize()
            except NotImplementedError as e:
                report["warnings"].append(f"vfx.finalize not implemented ({e})")
    with _Timer(report, "events.finalize"):
        # staged name: events.json only appears (next to the blend) when the whole build succeeded
        doc = EV.finalize(os.path.join(out_dir, EVENTS_STAGED_NAME), lanes=lane_list if partial else None,
                          spans=list(lane_spans.values()), lane_spans=lane_spans)
        report["events"] = dict(count=len(doc["events"]), unknown_types=doc["unknown_types"],
                                missing_beats=doc["missing_beats"], warnings=doc["warnings"][:50],
                                per_lane=EV.summary())
    if qa:
        with _Timer(report, "qa"):
            run_qa(report, lane_spans, shots, os.path.join(out_dir, QA_DIRNAME),
                   smear_fails=(not partial) or bool(report.get("strict")))
    with _Timer(report, "render_setup"):
        rs = None if "render_setup" in forced else _optional("render_setup")
        if rs is not None and hasattr(rs, "configure"):
            try:
                report["render_setup"] = str(_call(rs.configure, quality=quality))[:300]
            except NotImplementedError as e:
                report["warnings"].append(f"render_setup.configure not implemented ({e}) -> local preset")
                _local_configure(quality, sc)
            except (ValueError, KeyError, TypeError) as e:
                if quality != "layout":
                    raise
                report["warnings"].append(f"render_setup.configure('layout') failed ({e}) -> local layout preset")
                _local_configure("layout", sc)
        else:
            _local_configure(quality, sc)
        if sc.render.motion_blur_position != 'START':
            report["warnings"].append("motion_blur_position forced to START (Pipeline rule 2)")
            sc.render.motion_blur_position = 'START'
        # render_setup.configure resets the range to the whole film: partial / dev builds keep their lane range
        want_range = tuple(report["frame_range"])
        if (sc.frame_start, sc.frame_end) != want_range:
            sc.frame_start, sc.frame_end = want_range
        sc["build_quality"] = quality
        sc["build_lanes"] = ",".join(lane_list)
        sc["build_shots"] = json.dumps(report["shots"])
        pct = sc.render.resolution_percentage
        report["resolution"] = [sc.render.resolution_x * pct // 100, sc.render.resolution_y * pct // 100]
        report["engine"] = sc.render.engine
        try:
            sys.path.insert(0, config.SRC)
            import render_supervisor as RS
            report["shot_config"] = {s_["id"]: RS.config_hash(s_) for s_ in report["shots"]}
        except Exception as e:                        # noqa: BLE001 - fingerprints fall back to the live config
            report["warnings"].append(f"shot config digests unavailable ({e})")
    if digest:
        with _Timer(report, "shot_digest"):
            report["shot_digest"] = shot_digests(report["shots"], report)
    for ln, lr in report["lane_reports"].items():
        report["warnings"] += [f"{ln}: {w}" for w in lr["warnings"]]
    report["saved_frame_range"] = [sc.frame_start, sc.frame_end]
    if save:
        with _Timer(report, "save"):
            path = os.path.join(out_dir, SCENE_BLEND_NAME)
            bpy.context.preferences.filepaths.save_version = 0      # no scene.blend1 backups
            bpy.ops.wm.save_as_mainfile(filepath=path, check_existing=False)
            report["blend"] = path
            report["blend_sha1"] = file_sha1(path)
            report["blend_bytes"] = os.path.getsize(path)
    staged = os.path.join(out_dir, EVENTS_STAGED_NAME)
    if os.path.exists(staged):
        os.replace(staged, os.path.join(out_dir, EVENTS_JSON_NAME))
    return report


# =============================================================================================
# per-shot content digests (render invalidation: render_supervisor compares them between builds)
# =============================================================================================
DIGEST_VERSION = 2
DIGEST_Q = 1e5                      # floats quantised to 1e-5 (robust against float noise, exact otherwise)
# shot [a, b] depends on scene time [a, b + shutter] (START shutter 0.5 -> pad 0.6); the pad stays inside the lane
# strip edges (s - LT.PRE, e + LT.POST) so neighbouring lanes never leak into a shot's digest
DIGEST_PAD = (0.0, config.MB_SHUTTER + 0.1)
assert DIGEST_PAD[1] < LT.POST, f"motion-blur shutter {config.MB_SHUTTER} too long for the lane strip pad {LT.POST}"
RENDERABLE = {"MESH", "CURVE", "SURFACE", "META", "FONT", "CURVES", "POINTCLOUD", "VOLUME", "GREASEPENCIL",
              "LIGHT", "LIGHT_PROBE"}   # + EMPTY instancing a collection; cameras/armatures/empties only matter
                                        # when referenced (parent, constraint, modifier, node, marker camera)
# evaluated / UI-only / bookkeeping properties never part of a static hash
_SKIP = {
    "rna_type", "name_full", "session_uid", "is_evaluated", "original", "users", "use_fake_user", "use_extra_user",
    "is_embedded_data", "is_missing", "is_runtime_data", "is_editmode", "tag", "is_library_indirect", "library",
    "library_weak_reference", "asset_data", "override_library", "preview", "id_type", "id_data", "bl_rna",
    "select", "select_head", "select_tail", "hide_select", "hide_viewport", "hide", "display", "display_type",
    "bound_box", "dimensions", "matrix_world", "matrix_local", "matrix_basis", "mode", "is_from_instancer",
    "is_from_set", "active_material_index", "active_shape_key_index", "active_material", "show_name",
    "show_axis", "show_bounds", "show_texture_space", "show_wire", "show_in_front", "show_only_shape_key",
    "empty_display_size", "empty_display_type", "location_in_editor", "location", "width", "width_hidden",
    "height", "label", "use_custom_color", "color_tag", "parent_bone_ui", "matrix", "matrix_channel", "head", "tail",
    "is_active_output", "is_linked", "link_limit", "is_multi_input", "enabled", "show_expanded",
    "show_in_editmode", "show_on_cage", "show_viewport", "is_override_data", "is_override_data_editable",
    "use_pin_id", "filepath_raw", "is_dirty", "has_data", "bindcode", "is_float", "frame_duration",
    "is_active", "active_index", "active", "is_valid", "use_node_tree_update", "is_embedded", "users_collection",
    "users_scene", "is_instancer", "animation_visualization", "motion_path", "field", "collision",
    "image_user",
}
_KEEP_LOCATION = {"Object", "PoseBone"}       # 'location' is real data there (nodes: UI position -> skipped)
_NO_RECURSE = {"parent", "bone", "child", "children", "id_data", "original", "animation_data", "pose", "data",
               "node_tree", "custom_shape", "bone_group", "parent_bone", "grease_pencil", "shape_keys",
               "evaluated_get", "depsgraph", "view_layers", "world", "camera", "scene", "collection"}


def file_sha1(path, _cache={}):
    """sha1 of a file's content (memoised per (path, size, mtime)); None if missing."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    k = (path, st.st_size, st.st_mtime_ns)
    if k not in _cache:
        h = hashlib.sha1()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        _cache[k] = h.hexdigest()
    return _cache[k]


def _q(v):
    """Quantised, repr-stable value."""
    if isinstance(v, bool) or v is None or isinstance(v, (int, str)):
        return v
    if isinstance(v, float):
        return int(round(v * DIGEST_Q)) if math.isfinite(v) else str(v)
    if isinstance(v, bpy.types.ID):
        return ("ID", type(v).__name__, v.name)
    if isinstance(v, (set, frozenset)):
        return tuple(sorted(str(x) for x in v))
    try:
        return tuple(_q(x) for x in v)
    except TypeError:
        return str(v)


def _np_q(arr):
    import numpy as np
    a = np.asarray(arr, dtype=np.float64)
    return np.round(a * DIGEST_Q).astype(np.int64).tobytes()


def animated_paths(idb):
    """{data_path} animated on idb: active action, every NLA strip action (the ID's slot) and drivers."""
    out = set()
    ad = getattr(idb, "animation_data", None)
    if ad is None:
        return out
    for fc, *_ in LT.live_fcurves(idb, include_muted=True):
        out.add(fc.data_path)
    for fc in ad.drivers:
        out.add(fc.data_path)
    return out


def _walk(st, path, skip_paths, out, depth=0, kind=None):
    """Generic RNA walk of a struct: simple properties (quantised), ID pointers by name, non-ID pointers
    recursively (depth-limited). Properties whose data path is animated (skip_paths) are left out: their value
    depends on the frame; the animation itself is hashed per shot window."""
    kind = kind or type(st).__name__
    for pr in st.bl_rna.properties:
        idn = pr.identifier
        if idn in _SKIP and not (idn == "location" and kind in _KEEP_LOCATION):
            continue
        p = f"{path}.{idn}" if path else idn
        if p in skip_paths:
            continue
        if pr.type == 'COLLECTION':
            continue                                    # collections are handled explicitly per type
        try:
            v = getattr(st, idn)
        except (AttributeError, RuntimeError, TypeError):
            continue
        if pr.type == 'POINTER':
            if v is None:
                out.append((p, None))
            elif isinstance(v, bpy.types.ID):
                out.append((p, ("ID", type(v).__name__, v.name)))
            elif depth < 3 and idn not in _NO_RECURSE:
                _walk(v, p, skip_paths, out, depth + 1)
            continue
        out.append((p, _q(v)))
    return out


_VOLATILE_PROP = re.compile(r"(seconds|_secs|timestamp|elapsed|^(generated|started|finished|built_at)$)")


def _custom_props(owner, path, skip_paths, out):
    """Custom properties (render-relevant values such as world env_* props or GN inputs); bookkeeping props
    that change on every build (timings, timestamps) are left out."""
    try:
        keys = owner.keys()
    except TypeError:                       # struct without IDProperties
        return
    for k in keys:
        p = f'{path}["{k}"]' if path else f'["{k}"]'
        if p in skip_paths or k.startswith("_RNA_UI") or k in ("cycles",) or _VOLATILE_PROP.search(k):
            continue
        v = owner[k]
        if hasattr(v, "to_dict"):
            v = v.to_dict()
        elif hasattr(v, "to_list"):
            v = v.to_list()
        out.append((p, _q(v) if not isinstance(v, dict) else json.dumps(v, sort_keys=True, default=str)))


def _fcurve_blob(fc):
    """Everything that shapes an F-curve's value: keys (co, handles, interpolation, easing, back/amp/period),
    extrapolation, modifiers."""
    import numpy as np
    n = len(fc.keyframe_points)
    parts = [fc.data_path, fc.array_index, fc.extrapolation, fc.mute]
    if n:
        for prop, w in (("co", 2), ("handle_left", 2), ("handle_right", 2), ("back", 1), ("amplitude", 1),
                        ("period", 1)):
            buf = np.zeros(n * w, dtype=np.float32)
            fc.keyframe_points.foreach_get(prop, buf)
            parts.append(_np_q(buf))
        for prop in ("interpolation", "easing"):
            buf = np.zeros(n, dtype=np.int32)
            fc.keyframe_points.foreach_get(prop, buf)
            parts.append(buf.tobytes())
    for m in fc.modifiers:
        mo = []
        _walk(m, "", set(), mo)
        parts.append(repr(mo))
    return parts


def _driver_blob(fc):
    d = fc.driver
    parts = _fcurve_blob(fc) + [d.type, d.expression, d.use_self]
    for v in d.variables:
        parts.append((v.name, v.type))
        for t in v.targets:
            parts.append((("ID", t.id_type, t.id.name) if t.id is not None else None, t.data_path, t.bone_target,
                          t.transform_type, t.transform_space, t.rotation_mode))
    return parts


class _Digest:
    """Memoised static hashes of IDs (see static_hash)."""

    def __init__(self):
        self.memo = {}
        self.anim = {}
        self.records = {}

    def _skip_paths(self, idb):
        k = idb.as_pointer()
        if k not in self.anim:
            self.anim[k] = animated_paths(idb)
        return self.anim[k]

    def static_hash(self, idb):
        """sha1 of an ID's render-relevant static data + the IDs it depends on (materials, node groups, images,
        object data, shape keys). Animated properties are excluded (hashed per shot window)."""
        if idb is None:
            return None
        k = idb.as_pointer()
        if k in self.memo:
            return self.memo[k]
        self.memo[k] = "cycle"
        h = hashlib.sha1()
        out = [("type", type(idb).__name__), ("name", idb.name)]
        self.records[k] = out                       # debug dumps (SILVERGRASS_DIGEST_DUMP)
        skip = self._skip_paths(idb)
        deps = []
        try:
            _walk(idb, "", skip, out)
            _custom_props(idb, "", skip, out)
            fn = getattr(self, "_h_" + type(idb).__name__, None) or \
                (self._h_NodeTree if isinstance(idb, bpy.types.NodeTree) else None)
            if fn is not None:
                deps += fn(idb, skip, out, h) or []
            ad = getattr(idb, "animation_data", None)
            if ad is not None:
                for fc in ad.drivers:
                    out.append(("driver", repr(_driver_blob(fc))))
            nt = getattr(idb, "node_tree", None)
            if nt is not None and not isinstance(idb, bpy.types.NodeTree):
                deps.append(nt)
        except ReferenceError:
            pass
        h.update(repr(out).encode())
        for d in deps:
            h.update(f"|{type(d).__name__}:{d.name}:{self.static_hash(d)}".encode())
        self.memo[k] = h.hexdigest()
        return self.memo[k]

    # ---- per type
    def _h_Object(self, ob, skip, out, h):
        deps = [ob.data] if ob.data is not None else []
        out.append(("collections", tuple(sorted(c.name for c in ob.users_collection))))
        out.append(("vertex_groups", tuple(vg.name for vg in ob.vertex_groups)))
        for i, m in enumerate(ob.modifiers):
            mo = []
            _walk(m, f'modifiers["{m.name}"]', skip, mo)
            _custom_props(m, f'modifiers["{m.name}"]', skip, mo)        # GN inputs
            out.append(("modifier", m.name, m.type, repr(mo)))
            ng = getattr(m, "node_group", None)
            if ng is not None:
                deps.append(ng)
        for c in ob.constraints:
            co = []
            _walk(c, f'constraints["{c.name}"]', skip, co)
            out.append(("constraint", c.name, c.type, repr(co)))
        for i, s in enumerate(ob.material_slots):
            out.append(("slot", i, s.link, s.material.name if s.material else None))
            if s.material is not None:
                deps.append(s.material)
        if ob.pose is not None:
            for pb in ob.pose.bones:
                bp = f'pose.bones["{pb.name}"]'
                po = []
                _walk(pb, bp, skip, po, kind="PoseBone")
                _custom_props(pb, bp, skip, po)
                for c in pb.constraints:
                    _walk(c, f'{bp}.constraints["{c.name}"]', skip, po)
                    po.append(("constraint", c.name, c.type))
                out.append(("posebone", pb.name, repr(po)))
        if ob.instance_collection is not None:
            out.append(("instance_collection", ob.instance_collection.name,
                        tuple(sorted(o.name for o in ob.instance_collection.all_objects))))
            deps += list(ob.instance_collection.all_objects)
        return deps

    def _h_Mesh(self, me, skip, out, h):
        import numpy as np
        for coll, prop, w, dt in (("vertices", "co", 3, np.float32), ("edges", "vertices", 2, np.int32),
                                  ("polygons", "loop_start", 1, np.int32), ("polygons", "loop_total", 1, np.int32),
                                  ("polygons", "material_index", 1, np.int32), ("loops", "vertex_index", 1, np.int32)):
            c = getattr(me, coll)
            buf = np.zeros(len(c) * w, dtype=dt)
            if len(c):
                c.foreach_get(prop, buf)
            h.update(_np_q(buf) if dt == np.float32 else buf.tobytes())
        for a in me.attributes:
            if a.name in ("position",) or a.name.startswith("."):
                continue
            n = len(a.data)
            key = "value"
            w = 1
            if a.data_type in ('FLOAT_VECTOR',):
                key, w = "vector", 3
            elif a.data_type in ('FLOAT_COLOR', 'BYTE_COLOR'):
                key, w = "color", 4
            elif a.data_type in ('FLOAT2',):
                key, w = "vector", 2
            elif a.data_type in ('QUATERNION',):
                key, w = "value", 4
            elif a.data_type in ('FLOAT4X4', 'STRING'):
                out.append(("attr", a.name, a.domain, a.data_type, n))
                continue
            dt = np.float32 if a.data_type.startswith(("FLOAT", "BYTE", "QUAT")) else np.int32
            if a.data_type in ('BOOLEAN',):
                dt = bool
            buf = np.zeros(n * w, dtype=dt)
            try:
                if n:
                    a.data.foreach_get(key, buf)
            except (TypeError, RuntimeError, AttributeError):
                out.append(("attr?", a.name))
                continue
            out.append(("attr", a.name, a.domain, a.data_type))
            h.update(_np_q(buf) if dt == np.float32 else np.asarray(buf).tobytes())
        for uv in me.uv_layers:
            buf = np.zeros(len(uv.data) * 2, dtype=np.float32)
            if len(uv.data):
                uv.data.foreach_get("uv", buf)
            out.append(("uv", uv.name))
            h.update(_np_q(buf))
        idx, wts = [], []                                # vertex-group weights (skinning)
        for v in me.vertices:
            for g in v.groups:
                idx.append((v.index, g.group))
                wts.append(g.weight)
        if idx:
            h.update(np.asarray(idx, dtype=np.int32).tobytes())
            h.update(_np_q(wts))
        deps = [m for m in me.materials if m is not None]
        if me.shape_keys is not None:
            deps.append(me.shape_keys)
        out.append(("materials", tuple(m.name if m else None for m in me.materials)))
        return deps

    def _h_Key(self, key, skip, out, h):
        import numpy as np
        for kb in key.key_blocks:
            buf = np.zeros(len(kb.data) * 3, dtype=np.float32)
            if len(kb.data):
                kb.data.foreach_get("co", buf)
            ko = []
            _walk(kb, f'key_blocks["{kb.name}"]', skip, ko)
            out.append(("keyblock", kb.name, repr(ko)))
            h.update(_np_q(buf))
        return []

    def _h_Curve(self, cu, skip, out, h):
        import numpy as np
        for i, sp in enumerate(cu.splines):
            so = []
            _walk(sp, f"splines[{i}]", skip, so)
            out.append(("spline", i, repr(so)))
            for coll, prop, w in (("points", "co", 4), ("bezier_points", "co", 3),
                                  ("bezier_points", "handle_left", 3), ("bezier_points", "handle_right", 3),
                                  ("points", "radius", 1), ("bezier_points", "radius", 1),
                                  ("bezier_points", "tilt", 1)):
                c = getattr(sp, coll)
                buf = np.zeros(len(c) * w, dtype=np.float32)
                if len(c):
                    c.foreach_get(prop, buf)
                h.update(_np_q(buf))
        return [m for m in cu.materials if m is not None]

    _h_TextCurve = _h_Curve
    _h_SurfaceCurve = _h_Curve

    def _h_Armature(self, arm, skip, out, h):
        import numpy as np
        n = len(arm.bones)
        for prop, w in (("head_local", 3), ("tail_local", 3), ("matrix_local", 16)):
            buf = np.zeros(n * w, dtype=np.float32)
            if n:
                arm.bones.foreach_get(prop, buf)
            h.update(_np_q(buf))
        out.append(("bones", tuple((b.name, b.parent.name if b.parent else None, b.use_deform, b.use_connect,
                                    b.inherit_scale, b.use_inherit_rotation, b.use_local_location)
                                   for b in arm.bones)))
        return []

    def _h_Material(self, mat, skip, out, h):
        return []

    def _h_Image(self, img, skip, out, h):
        import numpy as np
        out.append(("image", img.source, tuple(img.size), bpy.path.abspath(img.filepath) if img.filepath else "",
                    img.colorspace_settings.name, img.alpha_mode))
        path = bpy.path.abspath(img.filepath) if img.filepath else ""
        if img.packed_file is not None:
            out.append(("packed", hashlib.sha1(bytes(img.packed_file.data)).hexdigest()))
        elif path and os.path.exists(path):
            out.append(("file", file_sha1(path)))
        elif img.size[0] * img.size[1] > 0 and img.has_data:
            buf = np.zeros(img.size[0] * img.size[1] * img.channels, dtype=np.float32)
            img.pixels.foreach_get(buf)
            h.update(_np_q(np.round(buf * 1024) / 1024))
        return []

    def _h_NodeTree(self, nt, skip, out, h):
        deps = []
        for node in sorted(nt.nodes, key=lambda n: n.name):
            np_ = f'nodes["{node.name}"]'
            no = [("node", node.name, node.bl_idname, node.mute)]
            _walk(node, np_, skip, no, kind="Node")
            for sock_coll in ("inputs", "outputs"):
                for i, s in enumerate(getattr(node, sock_coll)):
                    if hasattr(s, "default_value"):
                        p = f"{np_}.{sock_coll}[{i}].default_value"
                        if p not in skip:
                            try:
                                no.append((sock_coll, i, s.identifier, _q(s.default_value)))
                            except (TypeError, AttributeError):
                                no.append((sock_coll, i, s.identifier, str(s.default_value)))
                    no.append((sock_coll, i, s.identifier, getattr(s, "hide_value", False)))
            for attr in ("color_ramp",):
                cr = getattr(node, attr, None)
                if cr is not None:
                    no.append(("ramp", cr.interpolation, cr.color_mode,
                               tuple((_q(e.position), _q(tuple(e.color))) for e in cr.elements)))
            mp = getattr(node, "mapping", None)
            if mp is not None and hasattr(mp, "curves"):
                no.append(("mapping", tuple(tuple((_q(tuple(p.location)), p.handle_type) for p in c.points)
                                            for c in mp.curves)))
            for coll_name in ("capture_items", "repeat_items", "state_items", "enum_items", "bake_items",
                              "format_items", "generation_items", "input_items", "main_items"):
                items = getattr(node, coll_name, None)
                if items is not None:
                    no.append((coll_name, tuple((getattr(it, "name", ""), getattr(it, "data_type", getattr(
                        it, "socket_type", ""))) for it in items)))
            for attr in ("node_tree", "image", "object", "collection", "material", "texture"):
                v = getattr(node, attr, None)
                if isinstance(v, bpy.types.ID):
                    deps.append(v)
            out.append(repr(no))
        out.append(("links", tuple(sorted((l.from_node.name, l.from_socket.identifier, l.to_node.name,
                                           l.to_socket.identifier, l.is_muted) for l in nt.links))))
        iface = getattr(nt, "interface", None)
        if iface is not None:
            for it in iface.items_tree:
                io = []
                _walk(it, "", set(), io)
                out.append(("iface", repr(io)))
        # object / material pointers inside socket defaults (GN Object Info etc.)
        for node in nt.nodes:
            for s in node.inputs:
                v = getattr(s, "default_value", None)
                if isinstance(v, bpy.types.ID):
                    deps.append(v)
        return deps

    def _h_World(self, w, skip, out, h):
        return []

    def _h_Light(self, li, skip, out, h):
        return []

    def _h_Camera(self, cam, skip, out, h):
        return []


def _window_slice(xs, t0, t1):
    """Index range [i0, i1) of the keys that shape an F-curve over [t0, t1]: from the last key <= t0 to the first
    key >= t1 (the segments covering the window; auto-handle changes caused by keys further away show up in the
    stored handles of these keys)."""
    import numpy as np
    n = len(xs)
    if n == 0:
        return 0, 0
    i0 = int(np.searchsorted(xs, t0 + 1e-6, side="right")) - 1
    i1 = int(np.searchsorted(xs, t1 - 1e-6, side="left"))
    return max(0, i0), min(n, max(i1, i0) + 1)


class _AnimIndex:
    """Every F-curve source of every animated ID with its reach on the scene timeline and the lane-supersede
    information: for channel c of ID i, a LANE_* strip is superseded from the frame a later LANE_* strip that
    also animates c starts (REPLACE, influence 1 - assemble_nla enforces it); BASE until the first lane strip
    with c starts.  Other tracks (secondary, foreign) and the active action are always considered."""

    def __init__(self):
        import numpy as np
        self.channels = {}                      # (id label, path, index) -> [source dict]
        for idb in LT.iter_anim_ids(with_nla=True):
            label = LT.id_label(idb)
            ad = idb.animation_data
            srcs = []
            for fc in LT.active_fcurves(idb):
                srcs.append((fc, dict(kind="active", track="<active>", fs=-math.inf, fe=math.inf,
                                      reach=(-math.inf, math.inf), map=(0.0, 0.0),
                                      params=(ad.action_blend_type, _q(ad.action_influence),
                                              ad.action_extrapolation))))
            for tr in ad.nla_tracks:
                if tr.mute:
                    continue
                for st in tr.strips:
                    if st.mute:
                        continue
                    cb = LT.channelbag(st.action, st.action_slot)
                    if cb is None:
                        continue
                    ext = st.extrapolation
                    reach = (-math.inf if ext == 'HOLD' else st.frame_start,
                             math.inf if ext in ('HOLD', 'HOLD_FORWARD') else st.frame_end)
                    simple = abs(st.scale - 1.0) < 1e-6 and abs(st.repeat - 1.0) < 1e-6 and not st.use_reverse
                    params = [tr.name, _q(st.frame_start), _q(st.frame_end), _q(st.action_frame_start),
                              _q(st.action_frame_end), _q(st.scale), _q(st.repeat), st.blend_type, _q(st.influence),
                              ext, st.use_reverse, _q(st.blend_in), _q(st.blend_out), st.use_auto_blend]
                    for sfc in st.fcurves:                       # animated influence / strip time
                        params.append(repr(_fcurve_blob(sfc)))
                    kind = "base" if tr.name == LT.BASE_TRACK else ("lane" if tr.name.startswith(LT.LANE_PREFIX)
                                                                    else "other")
                    for fc in cb.fcurves:
                        srcs.append((fc, dict(kind=kind, track=tr.name, fs=st.frame_start, fe=st.frame_end,
                                              reach=reach, map=(st.frame_start, st.action_frame_start) if simple else None,
                                              params=tuple(params))))
            for fc, s in srcs:
                n = len(fc.keyframe_points)
                xs = np.zeros(n * 2, dtype=np.float32)
                if n:
                    fc.keyframe_points.foreach_get("co", xs)
                s = dict(s, fc=fc, xs=xs[0::2].astype(np.float64))
                self.channels.setdefault((label, fc.data_path, fc.array_index), []).append(s)
        self.blobs = {}

    def _blob(self, fc):
        k = fc.as_pointer()
        if k not in self.blobs:
            import numpy as np
            n = len(fc.keyframe_points)
            arrs = {}
            for prop, w in (("co", 2), ("handle_left", 2), ("handle_right", 2), ("back", 1), ("amplitude", 1),
                            ("period", 1)):
                buf = np.zeros(n * w, dtype=np.float32)
                if n:
                    fc.keyframe_points.foreach_get(prop, buf)
                arrs[prop] = (np.round(buf.astype(np.float64) * DIGEST_Q).astype(np.int64), w)
            for prop in ("interpolation", "easing"):
                buf = np.zeros(n, dtype=np.int32)
                if n:
                    fc.keyframe_points.foreach_get(prop, buf)
                arrs[prop] = (buf, 1)
            mods = []
            for m in fc.modifiers:
                mo = []
                _walk(m, "", set(), mo)
                mods.append(repr(mo))
            self.blobs[k] = (arrs, (fc.extrapolation, fc.mute, tuple(mods)))
        return self.blobs[k]

    def window_digest(self, lo, hi):
        """sha1 over every channel's contributing key slices within the scene window [lo, hi]."""
        h = hashlib.sha1()
        for key in sorted(self.channels):
            srcs = self.channels[key]
            lane_starts = sorted(s["fs"] for s in srcs if s["kind"] == "lane")
            first_lane = lane_starts[0] if lane_starts else math.inf
            used = []
            for s in srcs:
                r0, r1 = s["reach"]
                a, b = max(lo, r0), min(hi, r1)
                if a > b:
                    continue
                if s["kind"] == "lane":             # superseded over [a, b] by a later-starting lane strip?
                    later = [f for f in lane_starts if f > s["fs"] + 1e-6]
                    if later and later[0] <= a:
                        continue
                    if later:
                        b = min(b, later[0])
                elif s["kind"] == "base":
                    if first_lane <= a:
                        continue
                    b = min(b, first_lane)
                if s["map"] is None:                # foreign timing: the whole curve
                    i0, i1 = 0, len(s["xs"])
                else:
                    fs, afs = s["map"]
                    t0 = min(max(a, s["fs"]), s["fe"]) - (fs if math.isfinite(fs) else 0.0) + afs
                    t1 = min(max(b, s["fs"]), s["fe"]) - (fs if math.isfinite(fs) else 0.0) + afs
                    i0, i1 = _window_slice(s["xs"], t0, t1)
                arrs, extra = self._blob(s["fc"])
                used.append((s["track"], s["params"], i0, i1, extra))
                h.update(repr((key, s["track"], s["params"], extra)).encode())
                for prop in ("co", "handle_left", "handle_right", "back", "amplitude", "period", "interpolation",
                             "easing"):
                    arr, w = arrs[prop]
                    h.update(arr[i0 * w:i1 * w].tobytes())
        return h.hexdigest()


def _visibility_table(frames):
    """{frame: bool array (object visible = not hide_render)} over bpy.data.objects order, sampled with the
    modifiers muted (drivers + NLA included)."""
    import numpy as np
    sc = bpy.context.scene
    n = len(bpy.data.objects)
    buf = np.zeros(n, dtype=bool)
    now = sc.frame_current
    with U.muted_modifiers():
        for f in frames:
            U.frame_set(f, sc)
            bpy.data.objects.foreach_get("hide_render", buf)
            yield f, ~buf
    sc.frame_set(now)


def shot_digests(shots, report=None):
    """{shot id: sha1} of everything that can change the rendered pixels of each shot: the static data of every
    object that is visible somewhere in the shot (sampled at f and f+0.5) or referenced by another ID
    (constraint / modifier / parent / node / driver target), with its data, materials, node groups, images; the
    scene / world / compositor / view-layer settings; the markers + cameras of the shot; and the key slices of
    every animation source that can act on the shot window (lane supersede logic, see _AnimIndex).  Evaluated at
    a fixed frame (scene start) so derived values are deterministic.  Also stores report['digest_stats']."""
    import numpy as np
    t0 = time.time()
    sc = bpy.context.scene
    D = _Digest()
    sc.frame_set(sc.frame_start)
    objs = list(bpy.data.objects)
    names = [o.name for o in objs]
    cols = list(bpy.data.collections)
    users = bpy.data.user_map(subset=objs + cols)
    passive = (bpy.types.Scene, bpy.types.Collection)
    referenced = {o.name for o in objs if any(not isinstance(u, passive) for u in users.get(o, ()))}
    for c in cols:                  # collections used by nodes / instancers -> all their objects matter
        if any(not isinstance(u, passive) for u in users.get(c, ())):
            referenced |= {o.name for o in c.all_objects}
    renderable = [o.type in RENDERABLE or (o.type == 'EMPTY' and o.instance_type == 'COLLECTION'
                                           and o.instance_collection is not None) for o in objs]
    wins = {}
    frames = set()
    for s in shots:
        a, b = int(s["start"]), int(s["end"])
        wins[s["id"]] = (a - DIGEST_PAD[0], b + DIGEST_PAD[1])
        for f in range(a, b + 1):
            frames.add(float(f))
            frames.add(f + 0.5)
    seen = {sid: np.zeros(len(objs), dtype=bool) for sid in wins}
    order = sorted(frames)
    shot_ranges = [(sid, lo, hi) for sid, (lo, hi) in wins.items()]
    for f, vis in _visibility_table(order):
        for sid, lo, hi in shot_ranges:
            if lo <= f <= hi:
                seen[sid] |= vis
    sc.frame_set(sc.frame_start)
    obj_hash = {o.name: D.static_hash(o) for o in objs}
    # scene-level record (render / eevee / view / display settings, world, compositor, view layers)
    scene_parts = []
    for owner, p in ((sc.render, "render"), (sc.eevee, "eevee"), (sc.view_settings, "view_settings"),
                     (sc.display_settings, "display_settings"), (sc.display, "display")):
        _walk(owner, p, D._skip_paths(sc) | {"render.filepath", "render.frame_path"}, scene_parts)
    _custom_props(sc, "", D._skip_paths(sc) | {'["fx_time"]', '["build_shots"]', '["build_lanes"]'}, scene_parts)
    scene_parts.append(("world", sc.world.name if sc.world else None, D.static_hash(sc.world)))
    comp = getattr(sc, "compositing_node_group", None)
    scene_parts.append(("compositor", comp.name if comp else None, D.static_hash(comp), sc.render.use_compositing))

    def _lc(lc, out):
        out.append((lc.name, lc.exclude, lc.holdout, lc.indirect_only, lc.collection.hide_render))
        for ch in lc.children:
            _lc(ch, out)
    lcs = []
    for vl in sc.view_layers:
        lcs.append(("view_layer", vl.name, vl.use))
        _lc(vl.layer_collection, lcs)
    scene_parts.append(("layers", tuple(lcs)))
    scene_hash = hashlib.sha1(repr(scene_parts).encode()).hexdigest()
    anim = _AnimIndex()
    markers = sorted(((m.frame, m.name, m.camera.name if m.camera else None) for m in sc.timeline_markers))
    out = {}
    stats = {}
    for sid, (lo, hi) in wins.items():
        active = [m for m in markers if m[0] <= lo]
        ms = ([active[-1]] if active else []) + [m for m in markers if lo < m[0] <= hi]
        cams = {m[2] for m in ms if m[2]}
        keep = [i for i, n in enumerate(names)
                if (renderable[i] and seen[sid][i]) or n in referenced or n in cams]
        h = hashlib.sha1()
        h.update(f"v{DIGEST_VERSION}|{scene_hash}|{ms!r}".encode())
        for i in sorted(keep, key=lambda i: names[i]):
            h.update(f"|{names[i]}:{obj_hash[names[i]]}".encode())
        h.update(anim.window_digest(lo, hi).encode())
        out[sid] = h.hexdigest()[:24]
        stats[sid] = len(keep)
    dump = os.environ.get("SILVERGRASS_DIGEST_DUMP")
    if dump:                                        # debugging non-determinism: diff two dumps
        with open(dump, "w", encoding="utf-8") as f:
            json.dump(dict(scene=repr(scene_parts), objects=obj_hash,
                           records={f"{type(i).__name__}:{i.name}": repr(D.records.get(i.as_pointer()))
                                    for i in list(bpy.data.objects) + list(bpy.data.meshes) + list(bpy.data.materials)
                                    + list(bpy.data.node_groups) + list(bpy.data.cameras) + list(bpy.data.lights)
                                    + list(bpy.data.worlds) + list(bpy.data.armatures)},
                           anim={sid: anim.window_digest(lo, hi) for sid, (lo, hi) in wins.items()}),
                      f, indent=0)
    if report is not None:
        report["digest_stats"] = dict(version=DIGEST_VERSION, seconds=round(time.time() - t0, 2),
                                      objects=len(objs), referenced=len(referenced),
                                      channels=len(anim.channels), frames_sampled=len(order),
                                      objects_per_shot=stats)
    return out


def _write_report(report, out_dir):
    path = os.path.join(out_dir, config.BUILD_REPORT_NAME)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1, default=str)
    os.replace(path + ".tmp", path)


def main():
    """CLI entry. Exit codes: 0 ok, 1 the build raised (traceback printed, build_report status 'failed'),
    2 --strict and QA FAILs.  (Blender itself exits 0 when a --python script raises, hence the explicit exit.)"""
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="build_scene.py")
    ap.add_argument("--lanes", default="all")
    ap.add_argument("--quality", default=None, choices=["layout", "preview", "final"],
                    help="default: final for a full build, preview for --lanes")
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-save", action="store_true",
                    help="QA / report only (the output dir's previous scene.blend is removed all the same)")
    ap.add_argument("--no-qa", action="store_true")
    ap.add_argument("--no-digest", action="store_true", help="skip the per-shot content digests")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--stubs", default="", help="force placeholders: environment,characters,vfx,render_setup,moves")
    ap.add_argument("--fallback", action="store_true", help="use placeholders when env/characters build fails")
    try:
        a = ap.parse_args(argv)
        build(a.lanes, a.quality, a.out, save=not a.no_save, qa=not a.no_qa, strict=a.strict,
              stubs=[x.strip() for x in a.stubs.split(",") if x.strip()], fallback=a.fallback,
              digest=not a.no_digest)
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        if isinstance(e.code, str):
            print(e.code, file=sys.stderr, flush=True)
        sys.stdout.flush()
        sys.exit(code)
    except BaseException:                              # noqa: BLE001 - any failure = non-zero exit
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        sys.exit(1)


if __name__ == "__main__":
    main()
