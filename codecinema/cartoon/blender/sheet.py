"""Blender side of `codecinema library --sheet`: the library's characters side by side on the studio set."""
import json
import math
import sys
from pathlib import Path

JOB = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))
sys.path.insert(0, JOB["import_root"])

import bpy  # noqa: E402
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402
from mathutils import Vector  # noqa: E402

from codecinema.cartoon import motion, sets  # noqa: E402
from codecinema.cartoon.blender import cast, look as looks  # noqa: E402
from codecinema.cartoon.blender.sets import Lighting, SetBuild  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
look = looks.Look()
looks.render_settings(scene, JOB["width"], JOB["height"], 24, 24)
looks.finishing(scene, bloom=0.1)
stage = SetBuild("stage", sets.resolve({"from": "stage"}, "stage"), look)
Lighting("stage", "studio", look).activate(scene)
col = bpy.data.collections.new("Cast")
scene.collection.children.link(col)
rows = JOB["characters"]
widths = [max(r["metrics"]["height"] * 0.55, r["metrics"]["torso_r"] * 2.4)
          + (0.6 if r["spec"]["plan"] == "bird" else 0.0) for r in rows]
span = sum(widths) + 0.3 * len(widths)
x, placed = -span / 2, []                   # centered on the stage, which is built around the origin
for row, width in zip(rows, widths):
    m = row["metrics"]
    x += width / 2
    rig = cast.Rig(row["id"], row["spec"], m, look, row["atlas"], col)
    # Each character shows off in its own signature pose, turned its own way.
    show = row["spec"].get("sheet", {})
    facing = math.radians(show.get("facing", -12))
    events = [{"t": 0, "type": "place", "at": [x, 0], "facing": facing}]
    if show.get("act"):
        events.append({"t": 0.0, "type": "act", "name": show["act"], "dur": 4.0, "params": show.get("params", {})})
    track = motion.Track(row["id"], row["spec"], m, events)
    pose = track.pose(float(show.get("at", 0.6)))
    pose.update({"pos": (x, 0.0, pose["pos"][2]), "facing": facing})
    pose["face"] = {"eyes": "open", "brows": "raised", "mouth": "smile", "blush": 0.5, "gaze": (0.0, 0.0)}
    rig.apply(pose)
    placed.append((row["id"], x, m["height"]))
    x += width / 2 + 0.3
cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
scene.collection.objects.link(cam)
scene.camera = cam
tallest = max(h for _, _, h in placed)
cam.data.type = "ORTHO"
cam.data.ortho_scale = max(span * 1.04, tallest * 1.3 * JOB["width"] / JOB["height"])
visible = cam.data.ortho_scale * JOB["height"] / JOB["width"]
cam.location = (-0.15, -20, visible * 0.5 - visible * 0.16)
cam.rotation_euler = (math.radians(90), 0, 0)
bpy.context.view_layer.update()
labels = []
for name, px, h in placed:
    p = world_to_camera_view(scene, cam, Vector((px, 0, -0.02)))
    labels.append({"name": name, "x": p.x, "y": p.y})
Path(JOB["out"] + ".labels.json").write_text(json.dumps(labels), encoding="utf-8")
scene.render.filepath = JOB["out"]
bpy.ops.render.render(write_still=True)
