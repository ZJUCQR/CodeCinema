"""Blender-only scene builder. Run through the shared renderer, not host Python."""

import json
import math
from pathlib import Path
import random
import sys

import bpy
from mathutils import Vector
from codecinema.renderers.palettes import PALETTES


def rgb(value):
    # Convert art-direction sRGB values to Blender's scene-linear colors.
    values = [int(value[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in values)


def material(name, color, metallic=0, roughness=0.5, emission=0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    node = mat.node_tree.nodes.get("Principled BSDF")
    node.inputs["Base Color"].default_value = (*color, 1)
    node.inputs["Metallic"].default_value = metallic
    node.inputs["Roughness"].default_value = roughness
    node.inputs["Emission Color"].default_value = (*color, 1)
    node.inputs["Emission Strength"].default_value = emission
    return mat


def sphere(name, position, scale, mat, subdivisions=2):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdivisions, radius=1, location=position)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    for face in obj.data.polygons:
        face.use_smooth = True
    return obj


def light(name, position, color, power, size):
    data = bpy.data.lights.new(name, "AREA")
    data.energy, data.color, data.shape, data.size = power, color, "DISK", size
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = position
    obj.rotation_euler = (Vector((0, 3, 0)) - obj.location).to_track_quat("-Z", "Y").to_euler()


def world(spec, seed):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rng = random.Random(seed)
    look = spec["preset"]
    palette = PALETTES[look]
    accent = rgb(spec.get("accent", palette["accent"]))
    scene = bpy.context.scene
    scene.world = bpy.data.worlds.new("Atmosphere")
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (*rgb(palette["sky"][1]), 1)
    bg.inputs["Strength"].default_value = 0.35 if look != "ink" else 0.8
    stone = material("Sculpted stone", rgb(palette["hills"][1]), 0.18, 0.38)
    luminous = material("Light", accent, 0.15, 0.22, 3)
    water = material("Still water", rgb(palette["water"]), 0.65, 0.19)
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -0.3))
    bpy.context.object.data.materials.append(water)
    for i in range(18):
        x, y = rng.uniform(-24, 24), rng.uniform(10, 36)
        sphere("Distant ridge", (x, y, -1), (rng.uniform(2, 6), rng.uniform(2, 5), rng.uniform(2, 7)), stone)
    moon = sphere("Moon", (5, 19, 9), (2, 2, 2), luminous, 4)
    if look == "cosmos":
        moon.scale = (3, 3, 3)
        bpy.ops.mesh.primitive_torus_add(
            major_radius=4.5, minor_radius=0.085, major_segments=96, location=moon.location, rotation=(0.4, 0.35, 0)
        )
        bpy.context.object.data.materials.append(luminous)
    if look == "neon":
        for i in range(35):
            x, y, height = rng.uniform(-16, 16), rng.uniform(3, 22), rng.uniform(1, 8)
            bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, height / 2))
            obj = bpy.context.object
            obj.scale = (0.8, 0.8, height)
            obj.data.materials.append(stone)
            bevel = obj.modifiers.new("Edges", "BEVEL")
            bevel.width = 0.08
            bevel.segments = 2
            for z in range(1, int(height * 2)):
                sphere("Window", (x, y - 0.43, z / 2), (0.14, 0.025, 0.04), luminous, 1)
    elif look in ("ember", "aurora"):
        foliage = material("Canopy", rgb(palette["hills"][2]), roughness=0.65)
        for i in range(24):
            x, y = rng.uniform(-18, 18), rng.uniform(4, 24)
            if abs(x) < 3 and y < 10:
                continue
            h = rng.uniform(2, 6)
            bpy.ops.mesh.primitive_cone_add(vertices=12, radius1=1.3, depth=h, location=(x, y, h / 2))
            bpy.context.object.data.materials.append(foliage)
        for i in range(40):
            sphere("Firefly", (rng.uniform(-9, 9), rng.uniform(0, 15), rng.uniform(0.4, 5)), (0.025,) * 3, luminous, 1)
        if look == "aurora":
            for band in range(3):
                glow = material(
                    "Aurora", ((0.07, 0.65, 0.38), (0.12, 0.28, 0.75), (0.45, 0.12, 0.55))[band], emission=2
                )
                curve = bpy.data.curves.new("Ribbon", "CURVE")
                curve.dimensions = "3D"
                curve.bevel_depth = 0.065
                spline = curve.splines.new("POLY")
                spline.points.add(60)
                for j, p in enumerate(spline.points):
                    x = (j / 60 - 0.5) * 45
                    p.co = (x, 25 + band * 2, 10 + math.sin(x * 0.18 + band) * 2 + band * 0.7, 1)
                obj = bpy.data.objects.new("Aurora", curve)
                bpy.context.collection.objects.link(obj)
                obj.data.materials.append(glow)
    else:
        # A sculptural gateway is a clear foreground subject against the open horizon.
        for i in range(7):
            a = math.pi * i / 6
            sphere("Gateway stone", (math.cos(a) * 2.6, 5, math.sin(a) * 2.6 + 0.1), (0.55, 0.65, 0.65), stone, 3)
        sphere("Reflection light", (0, 5, 1.15), (0.24,) * 3, luminous, 4)
    light("Soft key", (1, -1, 10), (1, 0.78, 0.55), 1800, 8)
    light("Cool rim", (-6, 10, 8), (0.42, 0.7, 1), 2400, 6)
    cam = bpy.data.cameras.new("Camera")
    camera = bpy.data.objects.new("Camera", cam)
    bpy.context.collection.objects.link(camera)
    scene.camera = camera
    cam.lens = 42
    return scene


def render(job):
    if bpy.app.version < (5, 2, 0):
        raise ValueError("Use Blender 5.2 or later")
    active = None
    for index, frame in enumerate(job["frames"]):
        scene_index = next(i for i, (_, a, b) in enumerate(job["scenes"]) if a <= frame < b)
        spec, start, end = job["scenes"][scene_index]
        custom = spec.get("blender", {})
        if scene_index != active:
            if custom.get("file"):
                bpy.ops.wm.open_mainfile(filepath=str(Path(job["film"]) / custom["file"]))
                scene = bpy.data.scenes.get(custom.get("scene", "")) if custom.get("scene") else bpy.context.scene
                if scene is None:
                    raise ValueError("Requested Blender scene does not exist")
                bpy.context.window.scene = scene
                native_fps = scene.render.fps / scene.render.fps_base
                if custom.get("camera"):
                    scene.camera = scene.objects.get(custom["camera"])
                if scene.camera is None or scene.camera.type != "CAMERA":
                    raise ValueError("Choose a valid camera in the .blend scene")
            else:
                scene = world(spec, job["seed"])
            if not custom.get("file"):
                scene.render.engine = "CYCLES"
            # CPU works without a configured GPU and provides consistent reflections.
            if scene.render.engine == "CYCLES":
                scene.cycles.device = "CPU"
                scene.cycles.samples = job["samples"]
                scene.cycles.use_denoising = True
            scene.render.resolution_x = job["width"]
            scene.render.resolution_y = job["height"]
            scene.render.resolution_percentage = 100
            scene.render.image_settings.file_format = "PNG"
            scene.render.image_settings.color_mode = "RGBA"
            scene.render.film_transparent = False
            active = scene_index
        local = (frame - start) / job["fps"]
        if custom.get("file"):
            scene.frame_set(custom.get("frame_start", 1) + round(local * native_fps))
        else:
            progress = (frame - start) / max(1, end - start - 1)
            mode = spec.get("camera", "wide")
            x = math.sin(progress * 0.5) * 1.3 if mode == "drift" else 0.2
            distance = 14 if mode == "wide" else 11 if mode == "drift" else 8
            scene.camera.location = (x, -distance + progress * 0.5, 3.5)
            scene.camera.rotation_euler = (
                (Vector((0, 6, 3.2)) - scene.camera.location).to_track_quat("-Z", "Y").to_euler()
            )
            scene.frame_set(frame + 1)
        destination = Path(job["folder"]) / f"{frame:06d}.png"
        partial = destination.with_name(destination.stem + ".partial.png")
        scene.render.filepath = str(partial)
        bpy.ops.render.render(write_still=True)
        partial.replace(destination)
        print(f"Blender plate {index + 1}/{len(job['frames'])}", flush=True)


if __name__ == "__main__":
    render(json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8")))
