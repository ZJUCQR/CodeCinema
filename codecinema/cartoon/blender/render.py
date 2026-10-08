"""Render frames of a compiled cartoon plan inside Blender.

    blender -b --factory-startup --python render.py -- job.json

The job names the plan, the dialogue timings, the output folder and the frames
to render. Every frame is computed from scratch (poses, camera, effects), so
renders resume after interruption and split freely across processes. Only the
sets of the scenes in the requested frames are built.
"""
import json
import sys
import time
from pathlib import Path

JOB = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))
sys.path.insert(0, JOB["import_root"])

import bpy  # noqa: E402
from mathutils import Quaternion, Vector  # noqa: E402

from codecinema.cartoon import camera as directing  # noqa: E402
from codecinema.cartoon import motion  # noqa: E402
from codecinema.cartoon import sets as setlib  # noqa: E402
from codecinema.cartoon.blender import cast, look as looks, props, sets  # noqa: E402
from codecinema.cartoon.screenplay import hash_seed  # noqa: E402


def lipsync(events, voices):
    """Give every spoken beat its take's duration and mouth envelope."""
    out = []
    for e in events:
        if e.get("type") == "say" and e.get("line") in voices:
            take = voices[e["line"]]
            e = dict(e, dur=take["duration"], energy=take.get("energy"), envelope_hz=take.get("envelope_hz", 100.0),
                     syllables=take.get("syllables", []))
        out.append(e)
    return out


def main():
    plan = json.loads(Path(JOB["plan"]).read_text(encoding="utf-8"))
    voice_file = Path(JOB.get("voices") or "")
    voices = json.loads(voice_file.read_text(encoding="utf-8")) if voice_file.is_file() else {}
    fps = plan["fps"]
    frames = JOB["frames"]
    times = [(f - 1) / fps for f in frames]
    scenes = [s for s in plan["scenes"] if any(s["start"] <= t < s["end"] + 1e-6 for t in times)]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    engine = JOB.get("engine", "BLENDER_EEVEE")
    look = looks.Look(engine)
    looks.render_settings(scene, JOB["width"], JOB["height"], fps, JOB.get("samples", 16), engine)
    bloom = max(looks_bloom(s) for s in scenes) if scenes else 0.3
    looks.finishing(scene, bloom=bloom, threshold=1.0)
    scene.frame_start, scene.frame_end = 1, plan["frames"]

    cast_col = bpy.data.collections.new("Cast")
    scene.collection.children.link(cast_col)
    tracks, rigs = {}, {}
    present = set(c for s in scenes for c in s["present"])
    for cid, info in plan["cast"].items():
        events = lipsync(plan["tracks"][cid], voices)
        tracks[cid] = motion.Track(cid, info["spec"], info["metrics"], events, seed=hash_seed(cid))
        if cid in present:
            rigs[cid] = cast.Rig(cid, info["spec"], info["metrics"], look, info["atlas"], cast_col)

    builds, lights = {}, {}
    for s in scenes:
        if s["set"] not in builds:
            builds[s["set"]] = sets.SetBuild(s["set"], plan["sets"][s["set"]], look, plan["seed"], JOB.get("font"))
        key = f"{s['set']}:{s['time']}"
        if key not in lights:
            lights[key] = sets.Lighting(key, s["time"], look)
    prop_col = bpy.data.collections.new("Props")
    scene.collection.children.link(prop_col)
    items = {pid: props.Prop(pid, p["spec"], p["events"], look, prop_col) for pid, p in plan["props"].items()}
    fx_col = bpy.data.collections.new("Effects")
    scene.collection.children.link(fx_col)
    effects = props.Effects(plan, look, fx_col)
    for s in scenes:
        if s.get("weather"):
            effects.weather(s["weather"])

    cam_data = bpy.data.cameras.new("Camera")
    cam_data.sensor_width = 36.0
    cam_data.clip_start = 0.05
    cam_data.clip_end = 1200.0
    camera = bpy.data.objects.new("Camera", cam_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    director = directing.Director(tracks, {}, JOB["width"] / JOB["height"])

    folder = Path(JOB["folder"])
    folder.mkdir(parents=True, exist_ok=True)
    active = None
    begin = time.monotonic()
    done = 0
    for frame in frames:
        target = folder / f"{frame:05d}.png"
        if target.exists() and not JOB.get("force"):
            continue
        t = (frame - 1) / fps
        sc = next((s for s in plan["scenes"] if s["start"] <= t < s["end"]), plan["scenes"][-1])
        shot = next((s for s in plan["shots"] if s["start"] <= t < s["end"]), plan["shots"][-1])
        if sc["id"] != active:
            for sid, b in builds.items():
                b.show(sid == sc["set"])
            for key, light in lights.items():
                if key == f"{sc['set']}:{sc['time']}":
                    light.activate(scene)
                else:
                    light.hide()
            active = sc["id"]
            spec = plan["sets"][sc["set"]]
            ground = setlib.ground_function(spec)
            for tr in tracks.values():
                tr.ground = ground
            director.ground = ground
            director.solids = builds[sc["set"]].solids
            director.marks = dict(spec["marks"])
            for raw in plan.get("scene_marks", {}).get(sc["id"], {}).items():
                director.marks[raw[0]] = raw[1]
        view = director.solve(shot, t)
        heads = {cid: tr.head_position(t) for cid, tr in tracks.items()}
        for cid, rig in rigs.items():
            rig.apply(tracks[cid].pose(t, others=heads, camera=view["pos"]))
        builds[sc["set"]].animate(t)
        effects.update(t)
        effects.update_weather(sc.get("weather"), t, view["pos"])
        bpy.context.view_layer.update()
        for item in items.values():
            item.update(t, rigs)
        place_camera(camera, view)
        partial = folder / f".{frame:05d}.partial.png"
        scene.render.filepath = str(partial)
        bpy.ops.render.render(write_still=True)
        partial.replace(target)
        done += 1
        print(f"CARTOON frame {frame} ({done}/{len(frames)}) {time.monotonic() - begin:.1f}s", flush=True)


def looks_bloom(scene_row):
    return setlib.TIMES[scene_row["time"]].get("bloom", 0.3)


def place_camera(camera, view):
    pos, target = Vector(view["pos"]), Vector(view["target"])
    direction = target - pos
    if direction.length < 1e-6:
        direction = Vector((0, 1, 0))
    quat = direction.to_track_quat("-Z", "Y")
    if view.get("roll"):
        quat = quat @ Quaternion((0, 0, 1), view["roll"])
    camera.location = pos
    camera.rotation_mode = "QUATERNION"
    camera.rotation_quaternion = quat
    camera.data.lens = view["lens"]
    camera.data.dof.use_dof = bool(view.get("dof"))
    camera.data.dof.focus_distance = max(0.1, view.get("focus", 5.0))
    camera.data.dof.aperture_fstop = view.get("fstop", 5.6)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
