"""Blender-native geometry, lighting and continuous-time performance.

Executed by Blender; no external models, textures or add-ons are required.
"""

from codecinema.productions import film_root

import argparse
import math
import os
import random
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).parent))
from story import CUES, FPS, FRAMES, HEIGHT, SHOTS, WIDTH, smooth

ROOT = film_root("beacon")
os.environ["CODECINEMA_FILM_DIR"] = str(ROOT)
sys.path.insert(0, str(ROOT.parents[1]))
from codecinema.workspace import settings

RNG = random.Random(71)


def material(name, color, metallic=0, rough=0.35, glow=0):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    p = m.node_tree.nodes.get("Principled BSDF")
    p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Metallic"].default_value = metallic
    p.inputs["Roughness"].default_value = rough
    if glow:
        p.inputs["Emission Color"].default_value = (*color, 1)
        p.inputs["Emission Strength"].default_value = glow
    return m


def finish(ob, name, mat, parent=None):
    ob.name = name
    ob.data.materials.append(mat)
    if parent:
        ob.parent = parent
    if hasattr(ob.data, "polygons"):
        for p in ob.data.polygons:
            p.use_smooth = True
    return ob


def orb(name, loc, scale, mat, parent=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=20, location=loc)
    ob = finish(bpy.context.object, name, mat, parent)
    ob.scale = scale
    return ob


def box(name, loc, scale, mat, bevel=0.1, parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    ob = finish(bpy.context.object, name, mat, parent)
    ob.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    mod = ob.modifiers.new("Soft manufactured edges", "BEVEL")
    mod.width = bevel
    mod.segments = 4
    ob.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
    return ob


def cylinder(name, loc, radius, depth, mat):
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=radius, depth=depth, location=loc)
    ob = finish(bpy.context.object, name, mat)
    m = ob.modifiers.new("Machined edge", "BEVEL")
    m.width = 0.04
    m.segments = 3
    ob.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
    return ob


def ring(name, loc, radius, tube, mat, rotation=(0, 0, 0), parent=None):
    bpy.ops.mesh.primitive_torus_add(
        major_segments=96, minor_segments=12, location=loc, major_radius=radius, minor_radius=tube, rotation=rotation
    )
    return finish(bpy.context.object, name, mat, parent)


def empty(name, loc):
    ob = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(ob)
    ob.location = loc
    return ob


def beam(name, a, b, radius, mat):
    ob = orb(name, (0, 0, 0), (radius, radius, 1), mat)
    place_beam(ob, a, b, radius)
    return ob


def place_beam(ob, a, b, radius):
    a, b = Vector(a), Vector(b)
    ob.location = (a + b) / 2
    ob.rotation_euler = (b - a).to_track_quat("Z", "Y").to_euler()
    ob.scale = (radius, radius, (b - a).length / 2 + radius * 0.3)


def light(name, loc, color, energy, size, target):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.color = color
    data.shape = "DISK"
    data.size = size
    ob = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector(target) - ob.location).to_track_quat("-Z", "Y").to_euler()
    return ob


def build(preview=False):
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    s = bpy.context.scene
    s.render.engine = "BLENDER_EEVEE"
    s.eevee.taa_render_samples = int(
        settings.get("render", "samples_preview" if preview else "samples_final", 24 if preview else 48)
    )
    s.render.resolution_x = WIDTH
    s.render.resolution_y = HEIGHT
    s.render.resolution_percentage = 50 if preview else 100
    s.render.fps = FPS
    s.frame_start = 1
    s.frame_end = FRAMES
    s.render.image_settings.file_format = "PNG"
    s.render.image_settings.color_mode = "RGB"
    s.render.image_settings.compression = 15
    s.view_settings.view_transform = "AgX"
    s.view_settings.look = "AgX - Medium High Contrast"
    s.view_settings.exposure = float(settings.get("render", "exposure", -0.4))
    s.world.color = (0.018, 0.026, 0.05)
    s.world.use_nodes = True
    wn = s.world.node_tree.nodes
    wl = s.world.node_tree.links
    coordinate = wn.new("ShaderNodeTexCoord")
    separate = wn.new("ShaderNodeSeparateXYZ")
    wl.new(coordinate.outputs["Normal"], separate.inputs[0])
    mapping = wn.new("ShaderNodeMapRange")
    mapping.inputs["From Min"].default_value = -0.4
    mapping.inputs["From Max"].default_value = 0.5
    wl.new(separate.outputs["Z"], mapping.inputs["Value"])
    ramp = wn.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements.remove(ramp.color_ramp.elements[1])
    for i, (position, color) in enumerate(
        (
            (0, (0.012, 0.027, 0.075, 1)),
            (0.4, (0.065, 0.16, 0.24, 1)),
            (0.65, (0.23, 0.36, 0.40, 1)),
            (1, (0.40, 0.29, 0.25, 1)),
        )
    ):
        e = ramp.color_ramp.elements[0] if i == 0 else ramp.color_ramp.elements.new(position)
        e.position = position
        e.color = color
    wl.new(mapping.outputs[0], ramp.inputs[0])
    wl.new(ramp.outputs[0], wn["Background"].inputs[0])
    wn["Background"].inputs[1].default_value = 0.45
    ivory = material("Glazed warm porcelain", settings.get("art", "porcelain", [0.72, 0.79, 0.75]), 0.3, 0.24)
    gold = material("Brushed champagne brass", settings.get("art", "brass", [0.52, 0.28, 0.085]), 0.8, 0.26)
    dark = material("Midnight enamel", (0.022, 0.06, 0.072), 0.65, 0.28)
    glass = material("Obsidian faceplate", (0.012, 0.033, 0.04), 0.65, 0.16)
    teal = material("Sea glass light", (0.12, 0.8, 0.72), 0.2, 0.24, 3)
    amber = material("Warm filament", (1, 0.45, 0.10), 0.15, 0.3, 4)
    ringlight = material("Dormant ring engraving", (0.12, 0.8, 0.72), 0.2, 0.24, 0.1)
    red = material("Vermilion woven scarf", settings.get("art", "scarf", [0.38, 0.035, 0.027]), 0.05, 0.6)
    stone = material("Blue slate", (0.045, 0.095, 0.12), 0.25, 0.5)
    cloudmat = bpy.data.materials.new("Cloud scattering")
    cloudmat.use_nodes = True
    cn = cloudmat.node_tree.nodes
    cn.clear()
    cl = cloudmat.node_tree.links
    co = cn.new("ShaderNodeOutputMaterial")
    volume = cn.new("ShaderNodeVolumePrincipled")
    volume.inputs["Color"].default_value = (0.55, 0.7, 0.85, 1)
    volume.inputs["Anisotropy"].default_value = 0.25
    noise = cn.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 2.8
    noise.inputs["Detail"].default_value = 3
    density = cn.new("ShaderNodeMath")
    density.operation = "MULTIPLY"
    density.inputs[1].default_value = 0.65
    cl.new(noise.outputs["Fac"], density.inputs[0])
    cl.new(density.outputs[0], volume.inputs["Density"])
    cl.new(volume.outputs[0], co.inputs["Volume"])
    stars = material("Distant starlight", (0.55, 0.76, 1), 0, 0.3, 3)
    # Observatory: concentric terraces, inlays, radial seams and individual brass fasteners.
    cylinder("Floating foundation", (0, 0, -0.55), 5.0, 0.8, dark)
    cylinder("Slate observation deck", (0, 0, -0.09), 4.85, 0.18, stone)
    for r in (2.7, 4.15, 4.72):
        ring("Concentric brass inlay", (0, 0, 0.015), r, 0.016, gold)
    for r in (1.5, 1.56, 2.64, 3.45, 3.49):
        ring("Fine astrolabe engraving", (0, 0, 0.018), r, 0.006, gold)
    for i in range(72):
        a = i * math.tau / 72
        length = 0.16 if i % 6 == 0 else 0.065
        ob = box("Dial graduation", (3.35 * math.cos(a), 3.35 * math.sin(a), 0.02), (length, 0.008, 0.006), gold, 0.002)
        ob.rotation_euler.z = a
    for i in range(48):
        a = i * math.tau / 48
        ob = box("Radial deck joint", (4.45 * math.cos(a), 4.45 * math.sin(a), 0.01), (0.55, 0.018, 0.012), gold, 0.005)
        ob.rotation_euler.z = a
        orb("Deck rivet", (4.68 * math.cos(a), 4.68 * math.sin(a), 0.04), (0.035, 0.035, 0.025), gold)
    for i in range(13):
        a = 0.10 + i * math.pi / 12
        x, y = 4.35 * math.cos(a), 4.35 * math.sin(a)
        cylinder("Balustrade post", (x, y, 0.5), 0.045, 1, gold)
        orb("Rail lamp", (x, y, 1.04), (0.07, 0.07, 0.09), amber)
    # Rails follow the back half, leaving a clean foreground silhouette.
    for z in (0.48, 0.88):
        for i in range(32):
            a = 0.08 + i * math.pi / 32
            b = 0.08 + (i + 1) * math.pi / 32
            beam(
                "Curved brass rail",
                (4.35 * math.cos(a), 4.35 * math.sin(a), z),
                (4.35 * math.cos(b), 4.35 * math.sin(b), z),
                0.024,
                gold,
            )
    # Beacon with open gimbals, stepped plinth, a continuous rotation and emissive seed.
    center = Vector((1.15, 0.65, 2.0))
    cylinder("Beacon foot", (1.15, 0.65, 0.12), 0.73, 0.24, gold)
    cylinder("Beacon pedestal", (1.15, 0.65, 0.48), 0.48, 0.7, dark)
    for z in (0.23, 0.38, 0.65, 0.8):
        ring("Pedestal moulding", (1.15, 0.65, z), 0.49, 0.035, gold)
    cylinder("Instrument column", (1.15, 0.65, 1.12), 0.14, 0.7, gold)
    orb("Instrument cradle", center + Vector((0, 0, -0.23)), (0.27, 0.27, 0.10), gold)
    core = orb("Heart of the beacon", center, (0.18, 0.18, 0.18), amber)
    gimbals = []
    for i, r in enumerate((0.7, 0.94, 1.16)):
        pivot = empty("Orbital axis " + str(i), center)
        ring("Brass celestial ring", (0, 0, 0), r, 0.037, gold, parent=pivot)
        ring("Luminous engraving", (0, 0, 0.015), r - 0.055, 0.012, ringlight, parent=pivot)
        for j in range(12):
            a = j * math.tau / 12
            orb("Ring index", (r * math.cos(a), r * math.sin(a), 0), (0.05, 0.05, 0.05), gold, pivot)
        gimbals.append(pivot)
    # Console is within the keeper's reach; the contact point is used by the animation.
    console = box("Touch console", (-0.05, -0.38, 1.35), (0.52, 0.4, 0.13), dark, 0.08)
    console.rotation_euler.x = 0.18
    orb("Contact lens", (-0.13, -0.46, 1.44), (0.105, 0.095, 0.035), teal)
    beam("Console support", (0.15, -0.25, 0.4), (-0.05, -0.38, 1.3), 0.05, gold)
    # Character: a crafted humanoid automaton with ceramic armor and articulated fingers.
    body = empty("Keeper body", (-1.28, -0.55, 0))
    for side in (-1, 1):
        x = -1.28 + side * 0.22
        box("Boot", (x, -0.64, 0.16), (0.33, 0.56, 0.28), dark, 0.11)
        orb("Boot cap", (x, -0.82, 0.19), (0.165, 0.23, 0.13), ivory)
        for z in (0.48, 0.88):
            orb("Leg armor", (x, -0.55, z), (0.13, 0.14, 0.24), ivory)
        orb("Knee bearing", (x, -0.58, 0.69), (0.125, 0.125, 0.12), gold)
    orb("Hip shell", (0, 0, 1.05), (0.36, 0.23, 0.24), dark, body)
    orb("Ceramic breastplate", (0, 0, 1.48), (0.4, 0.245, 0.47), ivory, body)
    orb("Chest medallion", (0, -0.24, 1.56), (0.10, 0.027, 0.10), gold, body)
    orb("Chest heartbeat", (0, -0.27, 1.56), (0.05, 0.015, 0.05), teal, body)
    for x in (-0.25, 0.25):
        ob = box("Chest harness", (x, -0.19, 1.52), (0.045, 0.065, 0.5), gold, 0.02, body)
        ob.rotation_euler.y = -x * 0.5
    cylinder("Neck bearing", (-1.28, -0.55, 1.94), 0.14, 0.17, gold)
    head = empty("Keeper head", (-1.28, -0.55, 2.2))
    orb("Ceramic head", (0, 0, 0), (0.42, 0.34, 0.39), ivory, head)
    orb("Face rim", (0, -0.265, -0.025), (0.355, 0.115, 0.27), gold, head)
    orb("Face glass", (0, -0.307, -0.023), (0.325, 0.09, 0.24), glass, head)
    eyes = []
    for x in (-0.135, 0.135):
        eye = orb("Inlaid expressive eye", (x, -0.390, 0.015), (0.06, 0.018, 0.077), teal, head)
        eyes.append(eye)
        orb("Eye glint", (x - 0.012, -0.409, 0.043), (0.012, 0.007, 0.014), ivory, head)
    for side in (-1, 1):
        orb("Ear bearing", (side * 0.40, 0, 0), (0.075, 0.14, 0.14), gold, head)
        orb("Ear enamel", (side * 0.447, -0.01, 0), (0.03, 0.10, 0.10), dark, head)
    # Scarf collar and a deformed ribbon that responds gently to the wind.
    ring("Scarf collar", (-1.28, -0.55, 1.90), 0.21, 0.075, red)
    verts = []
    faces = []
    for i in range(21):
        for j in (-1, 1):
            verts.append((-1.48 - i * 0.038, -0.40, 1.88 - i * 0.021 + j * 0.075))
    for i in range(20):
        faces.append((i * 2, i * 2 + 1, i * 2 + 3, i * 2 + 2))
    mesh = bpy.data.meshes.new("Woven scarf ribbon")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    scarf = bpy.data.objects.new("Scarf in the breeze", mesh)
    bpy.context.collection.objects.link(scarf)
    finish(scarf, scarf.name, red)
    sol = scarf.modifiers.new("Fabric thickness", "SOLIDIFY")
    sol.thickness = 0.012
    sub = scarf.modifiers.new("Smooth fabric", "SUBSURF")
    sub.levels = 2
    arms = []
    for side in (-1, 1):
        shoulder = (-1.28 + side * 0.40, -0.55, 1.7)
        orb("Shoulder shell", shoulder, (0.19, 0.2, 0.20), ivory)
        upper = beam("Upper arm", shoulder, (shoulder[0] + side * 0.1, -0.6, 1.29), 0.105, ivory)
        elbow = orb("Elbow bearing", (0, 0, 0), (0.10, 0.10, 0.10), gold)
        lower = beam("Forearm", (0, 0, 0), (0, 0, 1), 0.09, ivory)
        hand = empty("Articulated hand", (0, 0, 0))
        orb("Palm", (0, 0, 0), (0.105, 0.065, 0.13), ivory, hand)
        for j in range(4):
            x = (j - 1.5) * 0.047
            orb("Finger proximal", (x, -0.015, -0.13), (0.022, 0.027, 0.074), gold, hand)
            orb("Finger ceramic tip", (x, -0.031, -0.215 + abs(j - 1.5) * 0.012), (0.023, 0.028, 0.046), ivory, hand)
        orb("Thumb", (-side * 0.10, -0.04, -0.08), (0.035, 0.04, 0.085), gold, hand)
        arms.append((side, shoulder, upper, elbow, lower, hand))
    # A sea of softly lit clouds and floating satellite rocks gives the island scale.
    for i in range(36):
        x = RNG.uniform(-32, 32)
        y = RNG.uniform(-4, 36)
        z = RNG.uniform(-5, -3.2)
        orb("Cloud bank", (x, y, z), (RNG.uniform(3, 7), RNG.uniform(3, 6), RNG.uniform(1.2, 2.2)), cloudmat)
    sun_data = bpy.data.lights.new("Dawn across the cloud sea", "SUN")
    sun_data.energy = 0.65
    sun_data.color = (0.60, 0.77, 1)
    sun_data.angle = 0.3
    sun = bpy.data.objects.new("Dawn across the cloud sea", sun_data)
    bpy.context.collection.objects.link(sun)
    sun.rotation_euler = (0.4, -0.5, -0.5)
    # Fine star-chart arcs trace the celestial vault behind the island.
    chart = material("Subtle celestial chart", (0.13, 0.24, 0.3), 0, 0.6, 0.4)
    for radius in (10, 13, 17):
        ring("Celestial meridian", (0, 28, 3), radius, 0.010, chart, (math.pi / 2, 0.15, 0.25))
    aurora = material("Faint polar light", (0.06, 0.28, 0.26), 0, 0.8, 0.4)
    for layer in range(3):
        av = []
        af = []
        for i in range(81):
            x = -32 + i * 0.8
            z = 8 + layer * 1.5 + 2 * math.sin(i * 0.07 + layer * 0.4)
            av.extend(((x, 33 + layer * 2, z), (x, 33 + layer * 2, z + 0.20 + 0.12 * math.sin(i * 0.12))))
        for i in range(80):
            af.append((2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2))
        am = bpy.data.meshes.new("Polar ribbon")
        am.from_pydata(av, [], af)
        am.update()
        ao = bpy.data.objects.new("Polar ribbon", am)
        bpy.context.collection.objects.link(ao)
        finish(ao, ao.name, aurora)
    for i in range(160):
        x = RNG.uniform(-55, 55)
        y = RNG.uniform(25, 48)
        z = RNG.uniform(3, 30)
        r = RNG.uniform(0.018, 0.06)
        orb("Star", (x, y, z), (r, r, r), stars)
    moonmat = material("Ivory moon", (0.62, 0.77, 0.83), 0, 0.7, 0.6)
    orb("Distant moon", (-10, 30, 3.8), (2.8, 1, 2.8), moonmat)
    ring("Moon orbital halo", (-10, 29.8, 3.8), 3.4, 0.017, stars, (math.pi / 2, 0, 0.25))
    # Signal particles rise along a spiral, answering lamps appear across the horizon.
    particles = [orb("Signal mote", (0, 0, -20), (0.035, 0.035, 0.035), amber) for _ in range(48)]
    answers = []
    for i in range(7):
        x, y, z = -15 + i * 5, 22 + (i % 2) * 4, 1.6 + (i % 3) * 0.8
        answers.append(orb("Distant answering beacon", (x, y, z), (0.06, 0.06, 0.18), amber))
    light("Moon key", (-4, -3, 8), (0.53, 0.72, 1), 1800, 7, (0, 0, 1))
    light("Warm rim", (3, 4, 6), (1, 0.56, 0.26), 2400, 5, (0, 0, 1))
    light("Face softbox", (-2, -5, 3), (0.7, 0.9, 1), 400, 4, (-1, 0, 1.5))
    glow = light("Beacon bounce", (1, -0.3, 2.7), (1, 0.42, 0.12), 30, 2, (-1, 0, 1))
    bpy.ops.object.camera_add()
    cam = bpy.context.object
    s.camera = cam
    cam.data.lens = 48
    cam.data.dof.use_dof = True
    cam.data.dof.aperture_fstop = 5.6
    focus = empty("Focus target", (0, 0, 1.5))
    cam.data.dof.focus_object = focus
    # Blender 5 compositor nodes live in a compositing node group.
    group = bpy.data.node_groups.new("Beacon finishing", "CompositorNodeTree")
    group.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    s.compositing_node_group = group
    layer = group.nodes.new("CompositorNodeRLayers")
    bloom = group.nodes.new("CompositorNodeGlare")
    bloom.inputs["Type"].default_value = "Bloom"
    bloom.inputs["Strength"].default_value = 0.25
    bloom.inputs["Threshold"].default_value = 1.5
    out = group.nodes.new("NodeGroupOutput")
    group.links.new(layer.outputs["Image"], bloom.inputs["Image"])
    group.links.new(bloom.outputs["Image"], out.inputs["Image"])

    def animate(frame):
        t = (frame - 1) / FPS
        breathe = 0.012 * math.sin(t * 1.6)
        body.location.z = breathe
        body.rotation_euler.y = (
            0.035
            * smooth(CUES["touch"] - 4, CUES["touch"], t)
            * (1 - smooth(CUES["ignition"] + 1, CUES["ignition"] + 5, t))
        )
        head.location.z = 2.2 + breathe
        head.rotation_euler = (
            0.04 * math.sin(t * 0.65) - 0.12 * smooth(36, 43, t),
            0.045 * math.sin(t * 0.5),
            0.42 * smooth(10, 17, t) - 0.18 * smooth(34, 44, t),
        )
        blink = 1 - 0.93 * math.exp(-(((t % 5.7 - 4.9) / 0.085) ** 2))
        for eye in eyes:
            eye.scale.z = 0.077 * blink
        for i, v in enumerate(mesh.vertices):
            k = i // 2
            j = -1 if i % 2 == 0 else 1
            v.co = (
                -1.48 - k * 0.038,
                -0.40 + 0.11 * (k / 20) * math.sin(t * 2.2 - k * 0.19),
                1.88 - k * 0.021 + j * 0.075 + 0.08 * (k / 20) * math.sin(t * 1.7 - k * 0.2),
            )
        for side, shoulder, upper, elbow, lower, hand in arms:
            reach = (
                smooth(CUES["touch"] - 4, CUES["touch"], t)
                * (1 - smooth(CUES["ignition"] + 1, CUES["ignition"] + 5, t))
                if side == 1
                else 0
            )
            start = Vector(shoulder) + Vector((0, 0, breathe))
            rest = Vector((shoulder[0] + side * 0.10, -0.63, 1.0 + breathe))
            target = Vector((-0.13, -0.49, 1.70))
            wrist = rest.lerp(target, reach)
            mid = (start + wrist) / 2 + Vector((side * 0.13, -0.09, -0.035))
            elbow.location = mid
            place_beam(upper, start, mid, 0.105)
            place_beam(lower, mid, wrist, 0.085)
            hand.location = wrist
            hand.rotation_euler = (reach * -0.2, reach * -0.05, 0.03 * math.sin(t))
        ignition = smooth(CUES["ignition"], CUES["ignition"] + 5, t)
        core.scale = (0.13 + 0.11 * ignition,) * 3
        amber.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 1.3 + 4 * ignition
        ringlight.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.12 + 3 * ignition
        glow.data.energy = 30 + 420 * ignition
        for i, pivot in enumerate(gimbals):
            pivot.rotation_euler = (
                0.25 + i * 0.5 + ignition * (0.5 + 0.2 * math.sin(t * 0.3 + i)),
                0.3 + i * 0.7 + ignition * t * 0.07,
                t * (0.025 + ignition * 0.10) * (1 if i % 2 else -1),
            )
        for i, p in enumerate(particles):
            q = (t - CUES["signal"] - i * 0.065) / 6
            p.hide_render = not 0 < q < 1.6
            a = i * 0.62 + q * 2
            p.location = (1.15 + (1 + q) * math.cos(a) * 0.6, 0.65 + (1 + q) * math.sin(a) * 0.6, 2 + q * 7)
            p.scale = (0.025 + 0.015 * math.sin(i),) * 3
        for i, p in enumerate(answers):
            v = smooth(CUES["answer"] + i * 0.35, CUES["answer"] + 1 + i * 0.35, t)
            p.scale = (0.13 * v, 0.13 * v, 0.22 * v)
        shot = next((i for i, (start, end, _) in enumerate(SHOTS) if start <= t < end), len(SHOTS) - 1)
        u = smooth(SHOTS[shot][0], SHOTS[shot][1], t)
        setups = [
            ((8, -14, 6), (6.8, -11, 4.8), (0, 1, 2.0), 40),
            ((-3.6, -5.6, 2.85), (-2.5, -4.5, 2.55), (-1.22, -0.45, 1.98), 64),
            ((1.0, -4.0, 2.6), (0.65, -3.5, 2.35), (-0.45, -0.3, 1.55), 58),
            ((4.5, -5.2, 3.6), (3.8, -5.6, 3.3), (0.55, 0.4, 1.9), 48),
            ((-4.8, -7.2, 3.4), (-5.8, -8.5, 4.9), (0.6, 0.6, 2.6), 43),
            ((6.8, -11, 4.8), (9, -15, 6), (0, 1, 2.0), 43),
        ]
        a, b, target, lens = setups[shot]
        cam.location = Vector(a).lerp(Vector(b), u)
        cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
        cam.data.lens = lens
        focus.location = target
        cam.data.dof.aperture_fstop = 4 if shot in (1, 2) else 7.1

    return s, animate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames")
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--end", type=int, default=FRAMES)
    ap.add_argument("--preview", action="store_true")
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    scene, animate = build(args.preview)
    folder = ROOT / "out" / ("stills" if args.frames else ("preview_frames" if args.preview else "frames"))
    folder.mkdir(parents=True, exist_ok=True)
    frames = [int(f) for f in args.frames.split(",")] if args.frames else range(args.start, args.end + 1)
    for frame in frames:
        if not 1 <= frame <= FRAMES:
            raise ValueError(f"Frame must be in 1..{FRAMES}: {frame}")
        path = folder / f"{frame:05d}.png"
        if path.exists() and not args.frames:
            continue
        scene.frame_set(frame)
        animate(frame)
        bpy.context.view_layer.update()
        temporary = folder / f".{frame:05d}.part.png"
        scene.render.filepath = str(temporary)
        bpy.ops.render.render(write_still=True)
        temporary.replace(path)
        print(f"BEACON {frame}/{FRAMES}", flush=True)


if __name__ == "__main__":
    main()
