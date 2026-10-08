"""Build library sets (terrain, architecture, nature, water) and their time-of-day lighting.

Every set lives in its own collection at the world origin; the renderer shows
the collection of the scene being filmed. Sets expose `animate(t)` for the
little motions that keep a frame alive: drifting clouds, lapping foam, swaying
kelp, flickering lanterns.
"""
import math
import random

import bpy
import numpy as np
from mathutils import Vector

from codecinema.cartoon import sets as library
from codecinema.cartoon.blender import geometry as geo
from codecinema.cartoon.blender.look import (add_outline, link, math_node, mix_color, node, point, rgba, sky_material,
                                             sun)


def _shade(color, k):
    c = color.lstrip("#")
    r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4))
    if k >= 0:
        r, g, b = (v + (255 - v) * k for v in (r, g, b))
    else:
        r, g, b = (v * (1 + k) for v in (r, g, b))
    return "#{:02x}{:02x}{:02x}".format(*(int(max(0, min(255, v))) for v in (r, g, b)))


class SetBuild:
    def __init__(self, sid, spec, look, seed=1, font=None):
        self.id, self.spec, self.look = sid, spec, look
        self.rng = random.Random(f"{sid}-{seed}")
        self.font = font
        self.collection = bpy.data.collections.new(f"Set {sid}")
        bpy.context.scene.collection.children.link(self.collection)
        self.ground = library.ground_function(spec)
        self.animated = []
        self.lamps = []
        self.water_time = []
        self.solids = []          # (x, y, radius, top) columns that cameras keep out of
        self.params = spec.get("params", {})
        getattr(self, f"_build_{spec['kind']}")()

    # ------------------------------------------------------------------ helpers
    def mat(self, name, color, **kw):
        return self.look.material(f"{self.id} {name}", color, **kw)

    def obj(self, name, verts, faces, material, smooth=True, ink=0.0):
        o = geo.mesh_object(f"{self.id}.{name}", verts, faces, material, smooth=smooth, collection=self.collection)
        if ink:
            add_outline(self.look, o, ink)
        return o

    def show(self, visible):
        self.collection.hide_render = not visible
        for o in self.collection.all_objects:
            o.hide_render = not visible
        for light in self.lamps:
            light.hide_render = not visible

    def terrain(self, name, size, res, material, center=(0, 0), fn=None):
        fn = fn or self.ground
        return geo.heightfield(f"{self.id}.{name}", size, res, fn, material, collection=self.collection,
                               center=center)

    def rock(self, name, location, size, material, seed, flat=0.35, ink=0.012):
        rng = random.Random(seed)
        waves = [(Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))).normalized(),
                  rng.uniform(1.5, 3.5), rng.uniform(0, 6.3), rng.uniform(0.05, 0.12)) for _ in range(6)]
        verts, faces = geo.ellipsoid_data((1, 1, 1), rings=12, segments=18)
        out = []
        for v in verts:
            d = Vector(v)
            n = d.normalized() if d.length > 1e-6 else Vector((0, 0, 1))
            r = 1 + sum(a * math.sin(n.dot(k) * f + ph) for k, f, ph, a in waves)
            z = n.z * r
            if z < 0:
                z *= flat
            out.append((location[0] + n.x * r * size[0], location[1] + n.y * r * size[1], location[2] + z * size[2]))
        o = self.obj(name, out, faces, material, ink=ink)
        if size[0] < 8:
            self.solids.append((location[0], location[1], max(size[0], size[1]) * 1.05, location[2] + size[2] * 1.2))
        return o

    def cloud(self, name, center, scale, material, seed):
        rng = random.Random(seed)
        parts = []
        for i in range(rng.randint(5, 8)):
            dx = rng.uniform(-1.0, 1.0) * scale * 1.4
            dz = abs(rng.gauss(0, 0.25)) * scale
            r = scale * rng.uniform(0.45, 0.8) * (1.15 - abs(dx) / (scale * 2.2))
            parts.append(geo.ellipsoid_data((r * 1.25, r * 0.9, r * 0.85),
                                            (center[0] + dx, center[1] + rng.uniform(-0.3, 0.3) * scale,
                                             center[2] + dz), rings=10, segments=16))
        o = geo.merge(f"{self.id}.{name}", parts, material, collection=self.collection)
        o.data.shade_smooth()
        return o

    def sky_props(self, clouds=10, radius=220, height=(35, 75), color="#ffffff", shadow=(0.72, 0.78, 0.95)):
        mat = self.mat("cloud", color, shadow=shadow, rim=0.6, soft=0.35)
        objs = []
        for i in range(clouds):
            a = self.rng.uniform(math.radians(20), math.radians(160))
            d = radius * self.rng.uniform(0.7, 1.0)
            c = (math.cos(a) * d * 1.3, math.sin(a) * d, self.rng.uniform(*height))
            o = self.cloud(f"cloud{i}", c, self.rng.uniform(12, 24), mat, self.rng.random())
            o.visible_shadow = False
            objs.append((o, c))

        def drift(t, objs=objs):
            for o, c in objs:
                o.location.x = t * 0.6
        self.animated.append(drift)

    def mountains(self, count=7, distance=(90, 150), height=(18, 40), color="#5f7aa8", snow="#eef3fb", spread=170):
        mats = [self.mat("mountain", color, rim=0.2, soft=0.2), self.mat("mountain snow", snow, rim=0.2, soft=0.2)]
        for i in range(count):
            a = math.radians(spread * (i + 0.5) / count + (180 - spread) / 2) + self.rng.uniform(-0.1, 0.1)
            d = self.rng.uniform(*distance)
            h = self.rng.uniform(*height)
            base = h * self.rng.uniform(1.2, 1.8)
            o = geo.cone(f"{self.id}.mountain{i}", base, base * 0.08, h, (0, 0, 0), mats, segments=28,
                         collection=self.collection)
            o.location = (math.cos(a) * d * 1.4, math.sin(a) * d, -2)
            co = np.empty(len(o.data.vertices) * 3, np.float32)
            o.data.vertices.foreach_get("co", co)
            co = co.reshape(-1, 3)
            ang = np.arctan2(co[:, 1], co[:, 0])
            co[:, 0] *= 1 + 0.18 * np.sin(ang * 3 + i)
            co[:, 1] *= 1 + 0.18 * np.sin(ang * 3 + i)
            o.data.vertices.foreach_set("co", co.ravel())
            for poly in o.data.polygons:
                poly.material_index = 1 if poly.center.z > h * 0.62 else 0
            o.visible_shadow = False

    # ------------------------------------------------------------------ water
    def water_material(self, shallow, deep, foam=True, shore_y=None, sparkle=1.0, name="water"):
        m = bpy.data.materials.new(f"{self.id} {name}")
        m.use_nodes = True
        t = m.node_tree
        t.nodes.clear()
        coord = node(t, "ShaderNodeTexCoord", (-1400, 0))
        sep = node(t, "ShaderNodeSeparateXYZ", (-1200, 0))
        link(t, coord.outputs["Object"], sep.inputs[0])
        clock = node(t, "ShaderNodeValue", (-1400, -300), name="Time", label="Time")
        depth = node(t, "ShaderNodeMapRange", (-1000, 200), clamp=True)
        link(t, sep.outputs["Y"], depth.inputs["Value"])
        depth.inputs["From Min"].default_value = (shore_y or 0) + 1.0
        depth.inputs["From Max"].default_value = (shore_y or 0) + 30.0
        _, f, a, b, color = mix_color(t, "MIX", (-800, 200))
        link(t, depth.outputs[0], f)
        a.default_value = rgba(shallow)
        b.default_value = rgba(deep)
        noise = node(t, "ShaderNodeTexNoise", (-900, -200), noise_dimensions="4D")
        noise.inputs["Scale"].default_value = 0.9
        noise.inputs["Detail"].default_value = 3.0
        link(t, coord.outputs["Object"], noise.inputs["Vector"])
        link(t, math_node(t, "MULTIPLY", clock.outputs[0], 0.25, (-1100, -300)), noise.inputs["W"])
        out = color
        if foam:
            lines = node(t, "ShaderNodeMapRange", (-700, -200), clamp=True)
            link(t, noise.outputs["Fac"], lines.inputs["Value"])
            lines.inputs["From Min"].default_value = 0.62
            lines.inputs["From Max"].default_value = 0.64
            if shore_y is not None:
                band = node(t, "ShaderNodeMapRange", (-700, -400), clamp=True)
                wave = math_node(t, "ADD", sep.outputs["Y"],
                                 math_node(t, "MULTIPLY", math_node(t, "SINE", math_node(
                                     t, "MULTIPLY", clock.outputs[0], 0.9, (-1000, -500)), None, (-900, -500)),
                                           0.35, (-800, -500)), (-750, -500))
                link(t, wave, band.inputs["Value"])
                band.inputs["From Min"].default_value = shore_y + 0.9
                band.inputs["From Max"].default_value = shore_y + 0.1
                foam_amt = math_node(t, "MAXIMUM", lines.outputs[0], math_node(
                    t, "MULTIPLY", band.outputs[0], math_node(t, "GREATER_THAN", noise.outputs["Fac"], 0.38,
                                                              (-600, -450)), (-500, -450)), (-400, -300))
            else:
                foam_amt = math_node(t, "MULTIPLY", lines.outputs[0], 0.7, (-500, -300))
            _, f2, a2, b2, res = mix_color(t, "MIX", (-300, 100))
            link(t, foam_amt, f2)
            link(t, out, a2)
            b2.default_value = (0.95, 0.99, 1.0, 1)
            out = res
        if sparkle:
            vor = node(t, "ShaderNodeTexVoronoi", (-700, -700), voronoi_dimensions="4D")
            vor.inputs["Scale"].default_value = 3.0
            link(t, coord.outputs["Object"], vor.inputs["Vector"])
            link(t, math_node(t, "MULTIPLY", clock.outputs[0], 0.6, (-900, -700)), vor.inputs["W"])
            glint = node(t, "ShaderNodeMapRange", (-500, -700), clamp=True)
            link(t, vor.outputs["Distance"], glint.inputs["Value"])
            glint.inputs["From Min"].default_value = 0.05
            glint.inputs["From Max"].default_value = 0.0
            _, f3, a3, b3, res3 = mix_color(t, "ADD", (-100, 100))
            link(t, math_node(t, "MULTIPLY", glint.outputs[0], sparkle * 1.6, (-300, -700)), f3)
            link(t, out, a3)
            b3.default_value = (1.0, 1.0, 0.95, 1)
            out = res3
        group = node(t, "ShaderNodeGroup", (100, 0))
        group.node_tree = self.look.group
        link(t, out, group.inputs["Color"])
        group.inputs["Shadow"].default_value = (0.75, 0.82, 0.92, 1)
        group.inputs["Soft"].default_value = 1.0
        group.inputs["Rim"].default_value = 0.0
        o = node(t, "ShaderNodeOutputMaterial", (300, 0))
        link(t, group.outputs[0], o.inputs["Surface"])
        self.water_time.append(clock)
        return m

    def animate(self, t):
        for clock in self.water_time:
            clock.outputs[0].default_value = t
        for fn in self.animated:
            fn(t)

    # ------------------------------------------------------------------ sets
    def _build_stage(self):
        p = self.params
        floor = self.mat("floor", p.get("floor", "#e9e2d6"), rim=0.0, soft=0.6)
        back = self.mat("backdrop", p.get("backdrop", "#cfe0ea"), rim=0.0, soft=0.8)
        # A cyclorama: the floor sweeps up into the backdrop without a visible corner.
        prof = [(-12, 0)] + [(4 + 3 * math.sin(i / 20 * math.pi / 2), 3 - 3 * math.cos(i / 20 * math.pi / 2))
                             for i in range(21)] + [(7, 14)]
        verts, faces = [], []
        for y, z in prof:
            verts += [(-30, y, z), (30, y, z)]
        for i in range(len(prof) - 1):
            faces.append((2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2))
        cyc = self.obj("cyc", verts, faces, [floor, back])
        for poly in cyc.data.polygons:
            poly.material_index = 1 if poly.center.y > 4.5 else 0

    def _build_meadow(self):
        p = self.params
        grass = self.mat("grass", p.get("grass", "#8cc26a"), rim=0.1, soft=0.3)
        self.terrain("hills", (160, 160), (120, 120), grass)
        self.sky_props()
        self.mountains(color="#7da0c8", snow="#f2f6fb")
        trunk = self.mat("trunk", "#7a5238")
        leaves = [self.mat("leaves", c, rim=0.3, soft=0.2) for c in ("#5aa04a", "#6fb357", "#4d8f45")]
        for i in range(p.get("trees", 14)):
            a = self.rng.uniform(0, math.tau)
            d = self.rng.uniform(9, 40)
            x, y = math.cos(a) * d, abs(math.sin(a)) * d + 4
            self.tree((x, y, self.ground(x, y)), self.rng.uniform(0.8, 1.4), trunk, self.rng.choice(leaves))
        colors = ("#ffffff", "#ffd84a", "#ff8fb0", "#c9a0ff", "#ff7a5a")
        petals = [self.mat(f"flower{i}", c, rim=0.0, soft=0.5) for i, c in enumerate(colors)]
        parts = {i: [] for i in range(len(colors))}
        for i in range(p.get("flowers", 260)):
            x, y = self.rng.uniform(-25, 25), self.rng.uniform(-8, 30)
            k = self.rng.randrange(len(colors))
            parts[k].append(geo.ellipsoid_data((0.07, 0.07, 0.03), (x, y, self.ground(x, y) + 0.08), 4, 6))
        for k, items in parts.items():
            if items:
                geo.merge(f"{self.id}.flowers{k}", items, petals[k], collection=self.collection)

    def tree(self, base, scale, trunk_mat, leaf_mat):
        x, y, z = base
        h = 2.6 * scale
        trunk = geo.cone(f"{self.id}.trunk", 0.18 * scale, 0.1 * scale, h * 0.6, (x, y, z), trunk_mat, segments=10,
                         collection=self.collection)
        add_outline(self.look, trunk, 0.03)
        parts = []
        for k in range(5):
            a = k * 1.3
            r = scale * self.rng.uniform(0.7, 1.0)
            parts.append(geo.ellipsoid_data((r, r, r * 0.85), (x + math.cos(a) * 0.45 * scale,
                                                                y + math.sin(a) * 0.45 * scale,
                                                                z + h * 0.62 + (k % 2) * 0.35 * scale), 10, 14))
        crown = geo.merge(f"{self.id}.crown", parts, leaf_mat, collection=self.collection)
        crown.data.shade_smooth()
        add_outline(self.look, crown, 0.035)

    def _build_beach(self):
        p = self.params
        sand = self.mat("sand", p["sand"], rim=0.05, soft=0.25)
        cliff = self.mat("cliff", p["cliff"], rim=0.15)
        grass = self.mat("cliff grass", "#8fc06a", rim=0.1)
        ground = self.terrain("beach", (90, 60), (300, 200), [sand, cliff, grass], center=(5, -8))
        for poly in ground.data.polygons:
            c = poly.center
            if c.z > 2.9 and c.x > 9:
                poly.material_index = 2
            elif poly.normal.z < 0.75 and c.x > 8:
                poly.material_index = 1
        water = self.water_material(p["sea"], p["deep"], shore_y=2.3, sparkle=1.0)
        sea = geo.mesh_object(f"{self.id}.sea", [(-150, -2, 0), (150, -2, 0), (150, 300, 0), (-150, 300, 0)],
                              [(0, 1, 2, 3)], water, collection=self.collection)
        sea.visible_shadow = False
        rock = self.mat("rock", p["rock"], rim=0.25)
        dark = self.mat("wet rock", _shade(p["rock"], -0.25), rim=0.25)
        spots = [(-3.2, -1.2, 0.9, 1.1, 0.75), (-4.6, -0.2, 0.6, 0.55, 0.5), (-2.0, 0.4, 0.4, 0.35, 0.3),
                 (4.5, 3.5, 1.2, 1.0, 0.8), (6.5, 5.0, 0.8, 0.7, 0.6), (-9, 1.5, 1.5, 1.2, 1.1),
                 (-12, -4, 1.0, 0.9, 0.7), (8.6, -2.6, 0.7, 0.6, 0.5), (11.5, 5.5, 1.6, 1.3, 1.2),
                 (13.5, 4.8, 1.0, 0.8, 1.6), (-6, 9, 1.4, 1.1, 1.0), (2.5, 12, 0.9, 0.8, 0.7)]
        for i, (x, y, sx, sy, sz) in enumerate(spots):
            z = self.ground(x, y)
            self.rock(f"rock{i}", (x, y, z - 0.1 * sz), (sx, sy, sz), rock if y < 2.5 else dark, i * 7 + 1)
        # Little touches: shells, beach grass and a far headland.
        shell = self.mat("shell", "#f4b8a8", rim=0.3)
        for i in range(14):
            x, y = self.rng.uniform(-10, 8), self.rng.uniform(-8, 1.8)
            o = geo.ellipsoid(f"{self.id}.shell", (0.06, 0.05, 0.02), (x, y, self.ground(x, y) + 0.01), shell,
                              collection=self.collection, rings=6, segments=8)
            o.rotation_euler.z = self.rng.uniform(0, 6)
        blades = self.mat("beach grass", "#9fbf5a", rim=0.2)
        tufts = []
        for i in range(70):
            x, y = self.rng.uniform(-14, -2), self.rng.uniform(-14, -5)
            z = self.ground(x, y)
            for k in range(5):
                a = k / 5 * math.tau + self.rng.uniform(0, 1)
                tip = (x + math.cos(a) * 0.25, y + math.sin(a) * 0.25, z + self.rng.uniform(0.35, 0.6))
                pts = geo.bezier((x, y, z), ((x + tip[0]) / 2, (y + tip[1]) / 2, z + 0.3), tip, 4)
                tufts.append((geo.tube_vertices(pts, geo.taper(4, 0.025, 0.002), 4), geo.tube_faces(4, 4)))
        geo.merge(f"{self.id}.grass", tufts, blades, collection=self.collection)
        tufts = []
        for i in range(160):
            x, y = self.rng.uniform(11.2, 22), self.rng.uniform(-9, 2.4)
            z = self.ground(x, y)
            if z < 3.0:
                continue
            for k in range(4):
                a = k / 4 * math.tau + self.rng.uniform(0, 1)
                tip = (x + math.cos(a) * 0.18, y + math.sin(a) * 0.18, z + self.rng.uniform(0.2, 0.42))
                pts = geo.bezier((x, y, z), ((x + tip[0]) / 2, (y + tip[1]) / 2, z + 0.22), tip, 4)
                tufts.append((geo.tube_vertices(pts, geo.taper(4, 0.022, 0.002), 4), geo.tube_faces(4, 4)))
        geo.merge(f"{self.id}.cliff_grass", tufts, self.mat("cliff blades", "#7fb357", rim=0.2),
                  collection=self.collection)
        bloom = self.mat("cliff flowers", "#fff3a0", rim=0.0, soft=0.5)
        dots = []
        for i in range(70):
            x, y = self.rng.uniform(11.5, 22), self.rng.uniform(-9, 2.2)
            z = self.ground(x, y)
            if z > 3.0:
                dots.append(geo.ellipsoid_data((0.05, 0.05, 0.025), (x, y, z + 0.05), 4, 6))
        if dots:
            geo.merge(f"{self.id}.cliff_flowers", dots, bloom, collection=self.collection)
        head = self.mat("headland", "#6f93b8", rim=0.1, soft=0.4)
        for i, (x, y, s) in enumerate(((-70, 120, 22), (-40, 140, 14), (90, 130, 26))):
            o = self.rock(f"headland{i}", (x, y, -3), (s * 2.2, s, s * 0.7), head, 90 + i, flat=0.1, ink=0)
            o.visible_shadow = False
        self.sky_props(clouds=12)
        self.cliff_x = 10.5

    def _build_underwater(self):
        p = self.params
        sand = self.mat("seabed", p["sand"], rim=0.05, soft=0.5)
        self.terrain("seabed", (160, 160), (140, 140), sand, center=(0, 10))
        rock = self.mat("reef rock", "#7f8f96", rim=0.3)
        for i in range(16):
            x, y = self.rng.uniform(-16, 16), self.rng.uniform(2, 30)
            s = self.rng.uniform(0.6, 2.2)
            self.rock(f"reef{i}", (x, y, self.ground(x, y) - 0.2), (s, s * 0.8, s * 0.7), rock, 200 + i)
        coral_colors = ("#ff7a7a", "#ffb35a", "#c98aff", "#ff8fc0", "#7ad6c8")
        for i in range(26):
            x, y = self.rng.uniform(-12, 12), self.rng.uniform(3, 24)
            c = self.mat(f"coral{i % 5}", coral_colors[i % 5], rim=0.4, soft=0.3)
            z = self.ground(x, y)
            parts = []
            for k in range(self.rng.randint(3, 6)):
                h = self.rng.uniform(0.3, 0.9)
                parts.append(geo.ellipsoid_data((0.12, 0.12, h), (x + self.rng.uniform(-0.3, 0.3),
                                                                  y + self.rng.uniform(-0.3, 0.3), z + h * 0.8),
                                                8, 10))
            o = geo.merge(f"{self.id}.coral", parts, c, collection=self.collection)
            o.data.shade_smooth()
        kelp_mat = self.mat("kelp", p["kelp"], rim=0.3, soft=0.3)
        kelps = []
        for i in range(34):
            x, y = self.rng.uniform(-14, 14), self.rng.uniform(4, 26)
            if abs(x) < 2.5 and y < 9:
                continue
            z = self.ground(x, y)
            h = self.rng.uniform(2.5, 5.5)
            o = geo.tube(f"{self.id}.kelp", [(x, y, z + h * k / 7) for k in range(8)], geo.taper(8, 0.09, 0.03),
                         kelp_mat, segments=6, flatten=0.45, collection=self.collection)
            kelps.append((o, x, y, z, h, self.rng.uniform(0, 6)))

        def sway(t, kelps=kelps):
            for o, x, y, z, h, ph in kelps:
                pts = [(x + 0.35 * (k / 7) ** 1.5 * math.sin(t * 0.8 + ph + k * 0.4),
                        y + 0.2 * (k / 7) ** 1.5 * math.cos(t * 0.6 + ph), z + h * k / 7) for k in range(8)]
                geo.update_tube(o, pts, geo.taper(8, 0.09, 0.03))
        self.animated.append(sway)
        # The surface seen from below: a bright, rippling ceiling.
        surf = bpy.data.materials.new(f"{self.id} surface")
        surf.use_nodes = True
        t = surf.node_tree
        t.nodes.clear()
        coord = node(t, "ShaderNodeTexCoord", (-800, 0))
        clock = node(t, "ShaderNodeValue", (-800, -200), name="Time", label="Time")
        vor = node(t, "ShaderNodeTexVoronoi", (-500, 0), voronoi_dimensions="4D", feature="F1")
        vor.inputs["Scale"].default_value = 0.6
        link(t, coord.outputs["Object"], vor.inputs["Vector"])
        link(t, math_node(t, "MULTIPLY", clock.outputs[0], 0.3, (-650, -200)), vor.inputs["W"])
        ramp = node(t, "ShaderNodeValToRGB", (-300, 0))
        ramp.color_ramp.elements[0].color = rgba("#dffcff")
        ramp.color_ramp.elements[1].position = 0.45
        ramp.color_ramp.elements[1].color = rgba("#62cfe0")
        link(t, vor.outputs["Distance"], ramp.inputs[0])
        em = node(t, "ShaderNodeEmission", (0, 0))
        link(t, ramp.outputs["Color"], em.inputs["Color"])
        em.inputs["Strength"].default_value = 0.85
        out = node(t, "ShaderNodeOutputMaterial", (200, 0))
        link(t, em.outputs[0], out.inputs["Surface"])
        self.water_time.append(clock)
        ceiling = geo.mesh_object(f"{self.id}.ceiling", [(-120, -60, 0), (120, -60, 0), (120, 120, 0),
                                                         (-120, 120, 0)], [(0, 3, 2, 1)], surf,
                                  collection=self.collection)
        ceiling.visible_shadow = False
        # Light shafts: soft additive planes slanting down from the surface.
        shaft = bpy.data.materials.new(f"{self.id} shaft")
        shaft.use_nodes = True
        t = shaft.node_tree
        t.nodes.clear()
        coord = node(t, "ShaderNodeTexCoord", (-600, 0))
        sep = node(t, "ShaderNodeSeparateXYZ", (-400, 0))
        link(t, coord.outputs["Generated"], sep.inputs[0])
        fade = node(t, "ShaderNodeMapRange", (-200, 0), interpolation_type="SMOOTHSTEP")
        link(t, sep.outputs["Z"], fade.inputs["Value"])
        edge = math_node(t, "SINE", math_node(t, "MULTIPLY", sep.outputs["X"], math.pi, (-300, -150)), None,
                         (-150, -150))
        alpha = math_node(t, "MULTIPLY", math_node(t, "MULTIPLY", fade.outputs[0], edge, (0, -100)), 0.22, (100, -100))
        em = node(t, "ShaderNodeEmission", (0, 150))
        em.inputs["Color"].default_value = (0.85, 1.0, 0.95, 1)
        em.inputs["Strength"].default_value = 1.0
        clear = node(t, "ShaderNodeBsdfTransparent", (0, 300))
        mix = node(t, "ShaderNodeMixShader", (250, 100))
        link(t, alpha, mix.inputs[0])
        link(t, clear.outputs[0], mix.inputs[1])
        link(t, em.outputs[0], mix.inputs[2])
        out = node(t, "ShaderNodeOutputMaterial", (450, 100))
        link(t, mix.outputs[0], out.inputs["Surface"])
        if hasattr(shaft, "surface_render_method"):
            shaft.surface_render_method = "BLENDED"
        for i in range(9):
            x, y = self.rng.uniform(-12, 12), self.rng.uniform(2, 22)
            w = self.rng.uniform(0.6, 1.6)
            o = geo.mesh_object(f"{self.id}.shaft", [(x - w, y, 0), (x + w, y, 0), (x + w + 2.5, y + 1, -9),
                                                     (x - w + 2.5, y + 1, -9)], [(0, 1, 2, 3)], shaft,
                                smooth=False, collection=self.collection)
            o.visible_shadow = False
        self.fish_school()

    def fish_school(self):
        body = self.mat("fish", "#e8f0f8", rim=0.5)
        stripe = self.mat("fish stripe", "#ffb347", rim=0.5)
        schools = []
        for s in range(3):
            cx, cy, cz = self.rng.uniform(-8, 8), self.rng.uniform(8, 20), self.rng.uniform(-4.5, -1.5)
            fish = []
            for i in range(14):
                o = geo.ellipsoid(f"{self.id}.fish", (0.05, 0.16, 0.08), (0, 0, 0), [body, stripe][i % 2],
                                  collection=self.collection, rings=8, segments=10)
                fish.append((o, self.rng.uniform(0, math.tau), self.rng.uniform(0.6, 1.4), self.rng.uniform(-0.6, 0.6)))
            schools.append((cx, cy, cz, self.rng.uniform(2, 4), fish, self.rng.choice((-1, 1))))

        def swim(t, schools=schools):
            for cx, cy, cz, r, fish, d in schools:
                for o, ph, rr, dz in fish:
                    a = d * t * 0.25 + ph * 0.18
                    o.location = (cx + math.cos(a) * r * rr, cy + math.sin(a) * r * rr * 0.6,
                                  cz + dz + 0.15 * math.sin(t * 1.3 + ph))
                    o.rotation_euler = (0, 0.2 * math.sin(t * 6 + ph), a + (math.pi if d > 0 else 0))
        self.animated.append(swim)

    def roof(self, center, length, depth, ridge_h, color, snow=True, eave=0.55):
        """A Chinese hip-less gable roof: concave slopes, upturned eave corners, a ridge and snow on top."""
        x0, y0, z0 = center
        mats = [self.mat("roof", color, rim=0.25), self.mat("roof snow", "#f4f7fd", rim=0.15, soft=0.3)]
        cols, rows = 28, 10
        verts, faces = [], []
        half_l = length / 2 + eave
        for side in (-1, 1):
            base = len(verts)
            for i in range(rows):
                v = i / (rows - 1)
                for j in range(cols):
                    u = j / (cols - 1)
                    xx = x0 - half_l + 2 * half_l * u
                    corner = abs(2 * u - 1) ** 4
                    yy = y0 + side * (depth / 2 + eave) * v
                    zz = z0 + ridge_h * (1 - v) - 0.35 * ridge_h * v * (1 - v) + corner * v * 0.45
                    verts.append((xx, yy, zz))
            for i in range(rows - 1):
                for j in range(cols - 1):
                    a = base + i * cols + j
                    quad = (a, a + 1, a + cols + 1, a + cols) if side > 0 else (a, a + cols, a + cols + 1, a + 1)
                    faces.append(quad)
        roof = geo.mesh_object(f"{self.id}.roof", verts, faces, mats[0], collection=self.collection)
        mod = roof.modifiers.new("Tiles", "SOLIDIFY")
        mod.thickness = 0.12
        add_outline(self.look, roof, 0.03)
        if snow:
            sv = [(x, y, z + 0.09) for x, y, z in verts]
            keep = [f for f in faces if all(math.hypot(0, sv[k][1] - y0) < (depth / 2 + eave) * 0.86 for k in f)]
            cap = geo.mesh_object(f"{self.id}.roof_snow", sv, keep, mats[1], collection=self.collection)
            m2 = cap.modifiers.new("Depth", "SOLIDIFY")
            m2.thickness = 0.08
        ridge = geo.tube(f"{self.id}.ridge", [(x0 - half_l * 0.92 + 1.84 * half_l * u,
                                               y0, z0 + ridge_h + 0.08 + 0.25 * abs(2 * u - 1) ** 6)
                                              for u in np.linspace(0, 1, 16)], 0.13, mats[0], segments=8,
                         collection=self.collection)
        add_outline(self.look, ridge, 0.025)
        return roof

    def lantern(self, location, size=0.36, light=True, swing=True, color="#e0302a"):
        red = self.mat("lantern", color, glow=1.2, rim=0.2, soft=0.5)
        gold = self.mat("lantern gold", "#f2c14e", glow=0.4)
        x, y, z = location
        body = geo.ellipsoid(f"{self.id}.lantern", (size * 0.5, size * 0.5, size * 0.42), (0, 0, 0), red,
                             collection=self.collection, rings=14, segments=18)
        body.location = location
        geo.cone(f"{self.id}.lantern_cap", size * 0.22, size * 0.2, size * 0.08, (0, 0, size * 0.38), gold,
                 segments=12, collection=self.collection, parent=body)
        geo.cone(f"{self.id}.lantern_base", size * 0.2, size * 0.22, size * 0.08, (0, 0, -size * 0.46), gold,
                 segments=12, collection=self.collection, parent=body)
        geo.cone(f"{self.id}.tassel", size * 0.07, size * 0.02, size * 0.4, (0, 0, -size * 0.88),
                 self.mat("tassel", "#ffd040", glow=0.3), segments=8, collection=self.collection, parent=body)
        add_outline(self.look, body, 0.012)
        if light:
            lamp = point(f"{self.id} lantern light", (x, y, z), "#ff8a4a", 60 * size / 0.36, radius=0.2)
            self.collection.objects.link(lamp)
            bpy.context.scene.collection.objects.unlink(lamp)
            self.lamps.append(lamp)
        if swing:
            ph = self.rng.uniform(0, 6)

            def sway(t, o=body, ph=ph, base=location):
                o.rotation_euler = (0.05 * math.sin(t * 1.1 + ph), 0.04 * math.sin(t * 0.9 + ph * 2), 0)
            self.animated.append(sway)
        return body

    def text(self, body, location, size, color, rotation=(math.pi / 2, 0, 0), glow=0.3):
        if not self.font:
            return None
        curve = bpy.data.curves.new(f"{self.id} text", "FONT")
        curve.body = body
        curve.font = bpy.data.fonts.load(self.font, check_existing=True)
        curve.size = size
        curve.align_x = "CENTER"
        curve.align_y = "CENTER"
        curve.extrude = 0.004
        o = bpy.data.objects.new(f"{self.id}.text", curve)
        self.collection.objects.link(o)
        o.location = location
        o.rotation_euler = rotation
        curve.materials.append(self.mat("ink text", color, glow=glow, rim=0.0))
        return o

    def house(self, x, y, facing=0, width=6.0, depth=4.2, height=2.6, door=True, home=False):
        """A village house facing -Y (facing=0) or +Y (facing=pi): plaster walls, timber, roof, lanterns, couplets."""
        p = self.params
        wall = self.mat("wall", p.get("wall", "#d9cdbb"), rim=0.1, soft=0.2)
        stone = self.mat("stone", "#8f8a86", rim=0.1)
        wood = self.mat("timber", p.get("wood", "#7a3b2a"), rim=0.2)
        window_glow = self.mat("window", "#ffcf7a", glow=0.8 if self.spec.get("lit", True) else 0.0, soft=1.0)
        f = 1 if facing == 0 else -1
        for k in range(-2, 3):
            self.solids.append((x + k * width / 5, y, depth / 2 + 0.3, 0.35 + height + 1.6))
        geo.rounded_box(f"{self.id}.plinth", (width + 0.4, depth + 0.4, 0.35), 0.04, (x, y, 0.17), stone,
                        collection=self.collection)
        body = geo.rounded_box(f"{self.id}.walls", (width, depth, height), 0.05, (x, y, 0.35 + height / 2), wall,
                               collection=self.collection)
        add_outline(self.look, body, 0.02)
        front = y - f * depth / 2
        for k in (-1, 1):
            post = geo.rounded_box(f"{self.id}.post", (0.22, 0.22, height), 0.02,
                                   (x + k * (width / 2 - 0.05), front - f * 0.06, 0.35 + height / 2), wood,
                                   collection=self.collection)
            add_outline(self.look, post, 0.015)
        beam = geo.rounded_box(f"{self.id}.beam", (width + 0.1, 0.24, 0.24), 0.02,
                               (x, front - f * 0.07, 0.35 + height - 0.12), wood, collection=self.collection)
        add_outline(self.look, beam, 0.015)
        if door:
            d = geo.rounded_box(f"{self.id}.door", (1.3, 0.12, 2.0), 0.02, (x, front - f * 0.05, 1.35), wood,
                                collection=self.collection)
            add_outline(self.look, d, 0.015)
            knob = self.mat("door ring", "#e2b04a", glow=0.2)
            for k in (-1, 1):
                geo.ellipsoid(f"{self.id}.ring", (0.05, 0.03, 0.05), (x + k * 0.12, front - f * 0.13, 1.35), knob,
                              collection=self.collection, rings=6, segments=10)
            red = self.mat("couplet", "#d42a24", glow=0.15, rim=0.0)
            for k in (-1, 1):
                geo.rounded_box(f"{self.id}.couplet", (0.3, 0.03, 1.6), 0.0, (x + k * 0.95, front - f * 0.1, 1.45),
                                red, collection=self.collection)
            geo.rounded_box(f"{self.id}.lintel", (1.5, 0.03, 0.32), 0.0, (x, front - f * 0.1, 2.6), red,
                            collection=self.collection)
            diamond = geo.rounded_box(f"{self.id}.fu", (0.5, 0.03, 0.5), 0.0, (x, front - f * 0.13, 1.55), red,
                                      collection=self.collection)
            diamond.rotation_euler = (0, math.radians(45), 0)
            gold = "#f2c14e"
            rot = (math.pi / 2, 0, 0) if f > 0 else (math.pi / 2, 0, math.pi)
            # 福 hangs upside down on purpose: "fu dao" (福倒) sounds like "fortune arrives".
            fu_rot = (math.pi / 2, math.pi, 0) if f > 0 else (math.pi / 2, math.pi, math.pi)
            self.text("福", (x, front - f * 0.15, 1.55), 0.36, gold, fu_rot)
            if home:
                for k, words in ((-1, "瑞雪兆丰年"), (1, "红梅报新春")):
                    tx = self.text("\n".join(words), (x + k * 0.95, front - f * 0.12, 1.45), 0.21, gold, rot)
                    if tx:
                        tx.data.space_line = 0.95
                self.text("新春大吉", (x, front - f * 0.12, 2.6), 0.2, gold, rot)
        for k in (-1, 1):
            geo.rounded_box(f"{self.id}.window", (1.1, 0.06, 0.9), 0.0, (x + k * width * 0.3, front - f * 0.02, 1.8),
                            window_glow, collection=self.collection)
            frame = []
            for i in range(5):
                xx = x + k * width * 0.3 - 0.55 + 1.1 * i / 4
                frame.append(geo.tube_vertices([(xx, front - f * 0.06, 1.35), (xx, front - f * 0.06, 2.25)], 0.025, 4))
            for i in range(4):
                zz = 1.35 + 0.9 * i / 3
                frame.append(geo.tube_vertices([(x + k * width * 0.3 - 0.55, front - f * 0.06, zz),
                                                (x + k * width * 0.3 + 0.55, front - f * 0.06, zz)], 0.025, 4))
            geo.merge(f"{self.id}.lattice", [(v, geo.tube_faces(2, 4)) for v in frame], wood,
                      collection=self.collection)
        self.roof((x, y, 0.35 + height), width, depth, 1.3, self.params.get("roof", "#3b4150"))
        for k in (-1, 1):
            self.lantern((x + k * 1.05, front - f * 0.75, 0.35 + height - 0.45), light=home or k > 0)

    def pine(self, x, y, scale, snow=True):
        z = self.ground(x, y)
        green = self.mat("pine", self.params.get("pine", "#2f5a4f"), rim=0.25)
        white = self.mat("pine snow", "#f2f6fd", rim=0.15, soft=0.3)
        bark = self.mat("bark", self.params.get("bark", "#5a4034"))
        parts_g, parts_s = [], []
        tiers = 4
        for k in range(tiers):
            r = scale * (1.25 - 0.25 * k)
            h = scale * 1.25
            base = z + scale * (0.6 + 0.85 * k)
            v, f = _cone_data(r, h, (x, y, base), 12)
            parts_g.append((v, f))
            if snow:
                vs, fs = _cone_data(r * 0.82, h * 0.55, (x, y, base + h * 0.42), 12)
                parts_s.append((vs, fs))
        o = geo.merge(f"{self.id}.pine", parts_g, green, collection=self.collection)
        add_outline(self.look, o, 0.03)
        if parts_s:
            s = geo.merge(f"{self.id}.pine_snow", parts_s, white, collection=self.collection)
            add_outline(self.look, s, 0.02)
        geo.cone(f"{self.id}.pine_trunk", scale * 0.18, scale * 0.12, scale * 1.0, (x, y, z), bark, segments=8,
                 collection=self.collection)
        self.solids.append((x, y, scale * 1.15, z + scale * (0.6 + 0.85 * tiers + 0.4)))
        return o

    def bare_tree(self, x, y, scale):
        z = self.ground(x, y)
        bark = self.mat("bare bark", "#4a3a34", rim=0.2)
        snow = self.mat("branch snow", "#f2f6fd", soft=0.3)
        parts, caps = [], []

        def branch(a, b, r, depth):
            pts = geo.bezier(a, (Vector(a) + Vector(b)) / 2 + Vector((0, 0, 0.1 * scale)), b, 5)
            parts.append((geo.tube_vertices(pts, geo.taper(5, r, r * 0.6), 6), geo.tube_faces(5, 6)))
            if r > 0.06 * scale:
                caps.append((geo.tube_vertices(pts + np.array((0, 0, r * 0.8)), geo.taper(5, r * 0.7, r * 0.3), 6,
                                               0.5), geo.tube_faces(5, 6)))
            if depth == 0:
                return
            for k in range(2 + (depth > 1)):
                ang = self.rng.uniform(0, math.tau)
                d = Vector(b) - Vector(a)
                length = d.length * 0.62
                tip = Vector(b) + (d.normalized() * 0.6 + Vector((math.cos(ang), math.sin(ang), 0.55)) * 0.7
                                   ).normalized() * length
                branch(tuple(b), tuple(tip), r * 0.6, depth - 1)

        branch((x, y, z), (x, y, z + 2.2 * scale), 0.22 * scale, 3)
        self.solids.append((x, y, 0.45 * scale, z + 4.0 * scale))
        o = geo.merge(f"{self.id}.tree", parts, bark, collection=self.collection)
        add_outline(self.look, o, 0.02)
        if caps:
            geo.merge(f"{self.id}.tree_snow", caps, snow, collection=self.collection)

    def _build_snow_village(self):
        p = self.params
        snow = self.mat("snow", p["snow"], rim=0.05, soft=0.55, shadow=(0.62, 0.68, 0.92))
        self.terrain("snow", (120, 90), (120, 90), snow, center=(0, 10))
        self.house(0, 4.0, home=True)
        self.house(-8.5, 4.6, width=5.2)
        self.house(8.5, 4.2, width=5.6)
        self.house(-16, 5.0, width=5.0, door=False)
        self.house(15.5, 5.2, width=5.0, door=False)
        self.house(-5, -13.5, facing=math.pi, width=6.0)
        self.house(6, -13.0, facing=math.pi, width=5.4)
        wall = self.mat("yard wall", "#cfc3b2", rim=0.1)
        cap = self.mat("wall tiles", "#3b4150")
        for x0, x1, yy in ((-4.2, -3.2, 1.0), (3.2, 4.2, 1.0)):
            geo.rounded_box(f"{self.id}.wall", (abs(x1 - x0) + 0.02, 0.3, 1.5), 0.03, ((x0 + x1) / 2, yy, 0.75),
                            wall, collection=self.collection)
        for i in range(10):
            x = self.rng.uniform(-30, 30)
            y = self.rng.uniform(-30, -16) if i % 2 else self.rng.uniform(14, 30)
            self.pine(x, y, self.rng.uniform(1.3, 2.2))
        for x, y, s in ((-11, -0.5, 1.2), (12, -1.5, 1.1), (3.5, -6.5, 0.9)):
            self.bare_tree(x, y, s)
        # A string of small lanterns across the lane.
        for i in range(9):
            u = i / 8
            x = -9 + 18 * u
            self.lantern((x, -2.8, 4.1 - 0.5 * math.sin(math.pi * u)), size=0.22, light=i % 3 == 1)
        rope = [(-9.5 + 19 * u, -2.8, 4.45 - 0.55 * math.sin(math.pi * u)) for u in np.linspace(0, 1, 20)]
        geo.tube(f"{self.id}.rope", rope, 0.012, cap, segments=4, collection=self.collection)
        well = self.mat("well", "#8f8a86", rim=0.2)
        o = geo.cone(f"{self.id}.well", 0.6, 0.6, 0.7, (3.5, -4.5, 0), well, segments=18, collection=self.collection)
        add_outline(self.look, o, 0.02)
        self.solids.append((3.5, -4.5, 0.65, 0.75))
        self.mountains(color="#3d4f78", snow="#c9d6f0", distance=(70, 110), height=(15, 32))

    def _build_snow_forest(self):
        p = self.params
        snow = self.mat("snow", p["snow"], rim=0.05, soft=0.55, shadow=(0.6, 0.66, 0.92))
        self.terrain("snow", (90, 90), (100, 100), snow, center=(0, 10))
        placed = 0
        while placed < 80:
            a = self.rng.uniform(0, math.tau)
            d = self.rng.uniform(9, 40)
            x, y = math.cos(a) * d * 1.15 - 2, math.sin(a) * d * 0.95 + 1
            # Keep the clearing and the path from the village open.
            if ((x + 3) / 12.5) ** 2 + ((y + 0.5) / 7.0) ** 2 < 1.0:
                continue
            self.pine(x, y, self.rng.uniform(1.0, 2.1))
            placed += 1
        for x, y, sc in ((0.0, 7.2, 1.7), (3.4, 7.8, 1.5), (-2.8, 8.0, 1.6), (5.6, 6.0, 1.3), (-5.4, 6.6, 1.4)):
            self.pine(x, y, sc)
        rock = self.mat("rock", "#7d8592", rim=0.2)
        snowcap = self.mat("rock snow", "#f2f6fd", soft=0.4)
        x, y = 2.8, 2.2
        self.rock("rock", (x, y, self.ground(x, y) - 0.1), (0.8, 0.7, 0.6), rock, 31)
        self.rock("rock_snow", (x, y + 0.05, self.ground(x, y) + 0.28), (0.66, 0.56, 0.3), snowcap, 31, flat=0.9)
        log = self.mat("log", "#6a4a3a", rim=0.2)
        o = geo.tube(f"{self.id}.log", [(-3.6, 2.4, self.ground(-3.6, 2.4) + 0.25),
                                        (-0.8, 2.9, self.ground(-0.8, 2.9) + 0.25)], 0.25, log, segments=12,
                     collection=self.collection)
        add_outline(self.look, o, 0.02)
        geo.tube(f"{self.id}.log_snow", [(-3.5, 2.4, self.ground(-3.6, 2.4) + 0.45),
                                         (-0.9, 2.9, self.ground(-0.8, 2.9) + 0.45)], 0.16, snowcap, segments=10,
                 flatten=0.5, collection=self.collection)
        self.mountains(color="#34466e", snow="#c9d6f0", distance=(70, 110), height=(18, 36))

    def _build_room(self):
        p = self.params
        floor = self.mat("floor", p["floor"], rim=0.05, soft=0.3)
        wall = self.mat("wall", p["wall"], rim=0.05, soft=0.5)
        wood = self.mat("furniture", p["wood"], rim=0.2)
        geo.mesh_object(f"{self.id}.floor", [(-4, -4, 0), (4, -4, 0), (4, 3, 0), (-4, 3, 0)], [(0, 1, 2, 3)], floor,
                        collection=self.collection)
        geo.mesh_object(f"{self.id}.back", [(-4, 3, 0), (4, 3, 0), (4, 3, 3.2), (-4, 3, 3.2)], [(0, 1, 2, 3)], wall,
                        collection=self.collection)
        for x in (-4, 4):
            geo.mesh_object(f"{self.id}.side", [(x, -4, 0), (x, 3, 0), (x, 3, 3.2), (x, -4, 3.2)], [(0, 1, 2, 3)],
                            wall, collection=self.collection)
        night = self.mat("window night", "#1f2d5a", glow=0.6, soft=1.0)
        geo.rounded_box(f"{self.id}.window", (1.6, 0.05, 1.1), 0.0, (0, 2.98, 1.7), night, collection=self.collection)
        frame = self.mat("window frame", "#5a2e1e", rim=0.2)
        bars = []
        for i in range(7):
            x = -0.8 + 1.6 * i / 6
            bars.append((geo.tube_vertices([(x, 2.93, 1.15), (x, 2.93, 2.25)], 0.02, 4), geo.tube_faces(2, 4)))
        for i in range(5):
            z = 1.15 + 1.1 * i / 4
            bars.append((geo.tube_vertices([(-0.8, 2.93, z), (0.8, 2.93, z)], 0.02, 4), geo.tube_faces(2, 4)))
        geo.merge(f"{self.id}.window_frame", bars, frame, collection=self.collection)
        papercut = self.mat("paper cut", "#d8262a", glow=0.2)
        for x, z in ((-0.42, 1.95), (0.42, 1.95), (0, 1.45)):
            geo.ellipsoid(f"{self.id}.papercut", (0.17, 0.01, 0.17), (x, 2.9, z), papercut,
                          collection=self.collection, rings=6, segments=12)
        self.text("福", (0, 2.89, 1.95), 0.22, "#f2c14e", (math.pi / 2, math.pi, 0))
        table = geo.rounded_box(f"{self.id}.table", (1.2, 1.0, 0.07), 0.02, (0, 0.6, 0.72), wood,
                                collection=self.collection)
        add_outline(self.look, table, 0.015)
        for dx in (-0.52, 0.52):
            for dy in (-0.42, 0.42):
                geo.rounded_box(f"{self.id}.leg", (0.07, 0.07, 0.7), 0.01, (dx, 0.6 + dy, 0.35), wood,
                                collection=self.collection)
        for x in (-0.75, 0.75):
            s = geo.rounded_box(f"{self.id}.stool", (0.36, 0.36, 0.06), 0.02, (x, 0.35, 0.38), wood,
                                collection=self.collection)
            add_outline(self.look, s, 0.012)
            for dx in (-0.14, 0.14):
                for dy in (-0.14, 0.14):
                    geo.rounded_box(f"{self.id}.stool_leg", (0.04, 0.04, 0.36), 0.0, (x + dx, 0.35 + dy, 0.18), wood,
                                    collection=self.collection)
        stove = self.mat("stove", "#9a8f86", rim=0.15)
        o = geo.rounded_box(f"{self.id}.stove", (1.0, 0.8, 0.85), 0.05, (2.4, 1.9, 0.43), stove,
                            collection=self.collection)
        add_outline(self.look, o, 0.015)
        pot = self.mat("pot", "#3a3a40", rim=0.4)
        geo.cone(f"{self.id}.pot", 0.32, 0.36, 0.3, (2.4, 1.9, 0.86), pot, segments=20, collection=self.collection)
        geo.rounded_box(f"{self.id}.shelf", (1.4, 0.3, 0.05), 0.01, (-2.6, 2.8, 1.8), wood, collection=self.collection)
        jar = self.mat("jar", "#4a6e9a", rim=0.4)
        for i in range(3):
            geo.ellipsoid(f"{self.id}.jar", (0.13, 0.13, 0.17), (-3.0 + 0.4 * i, 2.8, 2.0), jar,
                          collection=self.collection, rings=10, segments=12)
        self.lantern((0, 0.5, 2.55), size=0.42, light=False, swing=False)
        lamp = point(f"{self.id} lamp", (0, 0.4, 2.3), "#ffb066", 220, radius=0.3, shadow=True)
        self.collection.objects.link(lamp)
        bpy.context.scene.collection.objects.unlink(lamp)
        self.lamps.append(lamp)
        fire = point(f"{self.id} stove glow", (2.4, 1.5, 0.5), "#ff7a3a", 60, radius=0.2)
        self.collection.objects.link(fire)
        bpy.context.scene.collection.objects.unlink(fire)
        self.lamps.append(fire)

        def flicker(t, fire=fire):
            fire.data.energy = 60 * (0.85 + 0.15 * math.sin(t * 13) * math.sin(t * 7.3))
        self.animated.append(flicker)


def _cone_data(r, h, base, segments):
    x, y, z = base
    verts = [(x + r * math.cos(a), y + r * math.sin(a), z) for a in np.linspace(0, math.tau, segments, endpoint=False)]
    verts += [(x, y, z + h), (x, y, z)]
    top, bottom = segments, segments + 1
    faces = []
    for j in range(segments):
        k = (j + 1) % segments
        faces.append((j, k, top))
        faces.append((k, j, bottom))
    return verts, faces


class Lighting:
    """Sun, sky dome and world for one scene's time of day."""

    def __init__(self, key, time, look):
        recipe = library.TIMES[time]
        self.time, self.recipe, self.look = time, recipe, look
        self.collection = bpy.data.collections.new(f"Light {key}")
        bpy.context.scene.collection.children.link(self.collection)
        az, el, color, strength = recipe["sun"]
        self.sun = sun(f"Sun {key}", (az, el), color, strength, angle_deg=1.2)
        self.collection.objects.link(self.sun)
        bpy.context.scene.collection.objects.unlink(self.sun)
        top, horizon, bottom = recipe["sky"]
        sun_dir = None
        if el > 0 and time not in ("underwater",):
            # The visible sun or moon sits where the light comes from.
            a, e = math.radians(az), math.radians(el)
            sun_dir = (math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))
        disc = "#fff8e0" if time not in ("night", "moonlight", "dusk") else "#eef2ff"
        mat = sky_material(f"Sky {key}", top, horizon, bottom,
                           sun=(sun_dir, disc, 0.012 if time in ("night", "moonlight") else 0.02) if sun_dir else None,
                           stars=recipe.get("stars", 0), clouds=0.0)
        self.dome = geo.ellipsoid(f"Sky {key}", (400, 400, 400), (0, 0, 0), mat, collection=self.collection,
                                  rings=24, segments=48)
        self.dome.visible_shadow = False
        for poly in self.dome.data.polygons:
            poly.flip()

    def activate(self, scene):
        self.collection.hide_render = False
        for o in self.collection.all_objects:
            o.hide_render = False
        r = self.recipe
        az, el, color, strength = r["sun"]
        self.look.set_key(strength)
        self.look.set_scene_shadow(r["shadow"])
        fog = r.get("fog")
        self.look.set_fog(fog[0] if fog else "#ffffff", fog[1] if fog else 0.0)
        world = scene.world or bpy.data.worlds.new("Ambient")
        scene.world = world
        world.use_nodes = True
        bg = world.node_tree.nodes.get("Background")
        bg.inputs["Color"].default_value = rgba(r["ambient"][0])
        bg.inputs["Strength"].default_value = r["ambient"][1]

    def hide(self):
        self.collection.hide_render = True
        for o in self.collection.all_objects:
            o.hide_render = True


