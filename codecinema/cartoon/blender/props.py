"""Props (things characters carry or that move on their own) and visual effects.

Props follow their timed events: placed in the set, held in a hand (or on a
penguin's flipper), moved along a path, scaled, lit or hidden. Effects are
deterministic particle bursts (splashes, sparkles, fireworks, firecrackers,
steam, bubbles) and weather, all re-evaluated from scratch at any time so a
render can resume or run in parallel on any frame.
"""
import math
import random

import bpy
import numpy as np
from mathutils import Matrix, Vector

from codecinema.cartoon.blender import geometry as geo
from codecinema.cartoon.blender.look import add_outline
from codecinema.cartoon.motion import smooth


# ---------------------------------------------------------------------------- props
class Prop:
    def __init__(self, pid, spec, events, look, collection):
        self.id, self.spec, self.look = pid, spec, look
        self.events = sorted(events, key=lambda e: e["t"])
        self.root = geo.empty(f"prop {pid}", collection=collection)
        self.collection = collection
        self.glow_mats = []
        self.size = float(spec.get("size", 0.3))
        getattr(self, f"_build_{spec['kind']}", self._build_default)()
        self.parts = list(self.root.children_recursive)

    def mat(self, name, color, **kw):
        m = self.look.material(f"{self.id} {name}", color, **kw)
        return m

    def _glowing(self, name, color, glow):
        m = bpy.data.materials.new(f"{self.id} {name}")
        m.use_nodes = True
        t = m.node_tree
        t.nodes.clear()
        group = t.nodes.new("ShaderNodeGroup")
        group.node_tree = self.look.group
        from codecinema.cartoon.blender.look import rgba
        group.inputs["Color"].default_value = rgba(color)
        group.inputs["Glow"].default_value = glow
        group.inputs["Soft"].default_value = 0.6
        out = t.nodes.new("ShaderNodeOutputMaterial")
        t.links.new(group.outputs[0], out.inputs["Surface"])
        self.glow_mats.append((group, glow))
        return m

    def part(self, obj, ink=0.008):
        obj.parent = self.root
        if ink:
            add_outline(self.look, obj, ink)
        return obj

    def _build_default(self):
        s = self.size
        self.part(geo.ellipsoid(f"{self.id}.body", (s, s, s), (0, 0, s), self.mat("body", self.spec["color"]),
                                collection=self.collection))

    def _build_lantern(self):
        s = self.size
        red = self._glowing("paper", self.spec["color"], self.spec.get("glow", 1.0))
        gold = self.mat("gold", self.spec.get("trim", "#f2c14e"))
        self.part(geo.ellipsoid(f"{self.id}.paper", (s * 0.5, s * 0.5, s * 0.42), (0, 0, -s * 0.5), red,
                                collection=self.collection))
        self.part(geo.cone(f"{self.id}.cap", s * 0.22, s * 0.2, s * 0.08, (0, 0, -s * 0.15), gold, segments=12,
                           collection=self.collection), 0)
        self.part(geo.cone(f"{self.id}.base", s * 0.2, s * 0.22, s * 0.08, (0, 0, -s * 0.96), gold, segments=12,
                           collection=self.collection), 0)

    def _build_hand_lantern(self):
        s = self.size
        stick = self.mat("stick", "#7a5232")
        self.part(geo.tube(f"{self.id}.stick", [(0, 0, -0.02), (0, -s * 0.9, s * 1.6), (0, -s * 1.4, s * 1.5)],
                           0.012, stick, segments=6, collection=self.collection), 0)
        red = self._glowing("paper", self.spec["color"], self.spec.get("glow", 1.0))
        self.part(geo.ellipsoid(f"{self.id}.paper", (s * 0.5, s * 0.5, s * 0.45), (0, -s * 1.4, s * 0.95), red,
                                collection=self.collection), 0.006)
        self.light = None
        lamp = bpy.data.lights.new(f"{self.id} glow", "POINT")
        lamp.energy = 25
        lamp.color = (1.0, 0.55, 0.3)
        lamp.shadow_soft_size = 0.1
        lamp.use_shadow = False
        obj = bpy.data.objects.new(f"{self.id} glow", lamp)
        self.collection.objects.link(obj)
        obj.parent = self.root
        obj.location = (0, -s * 1.4, s * 0.95)

    def _build_bowl(self):
        s = self.size
        white = self.mat("porcelain", self.spec["color"], rim=0.4)
        blue = self.mat("glaze", self.spec.get("trim", "#3a6ab0"))
        self.part(geo.lathe(f"{self.id}.bowl", [(s * 0.45, 0.0), (s * 0.85, s * 0.25), (s, s * 0.6), (s * 0.95, s * 0.62)],
                            24, material=white, collection=self.collection))
        self.part(geo.tube(f"{self.id}.band", [(s * 0.97 * math.cos(a), s * 0.97 * math.sin(a), s * 0.5)
                                                for a in np.linspace(0, math.tau, 25)], s * 0.05, blue, segments=6,
                           collection=self.collection), 0)
        dough = self.mat("dumpling", "#f8f2e4", rim=0.3, soft=0.4)
        for i in range(int(self.spec.get("dumplings", 5))):
            a = i / max(1, self.spec.get("dumplings", 5)) * math.tau
            d = geo.ellipsoid(f"{self.id}.dumpling", (s * 0.28, s * 0.17, s * 0.15),
                              (math.cos(a) * s * 0.42, math.sin(a) * s * 0.42, s * 0.62), dough,
                              collection=self.collection, rings=10, segments=12, squash_bottom=0.5)
            d.rotation_euler.z = a
            self.part(d, 0.004)

    def _build_dumpling(self):
        s = self.size
        self.part(geo.ellipsoid(f"{self.id}.dumpling", (s * 1.6, s, s * 0.9), (0, 0, s * 0.5),
                                self.mat("dough", self.spec["color"], rim=0.3, soft=0.4), collection=self.collection,
                                squash_bottom=0.5), 0.004)

    def _build_scarf(self):
        s = self.size
        cloth = self.mat("wool", self.spec["color"], rim=0.3, soft=0.2)
        pts = [(s * (u - 0.5), -0.05 * math.sin(math.pi * u), -0.25 * s * math.sin(math.pi * u))
               for u in np.linspace(0, 1, 14)]
        self.part(geo.tube(f"{self.id}.wool", pts, s * 0.09, cloth, segments=8, flatten=0.35, twist_up=(0, -1, 0),
                           collection=self.collection), 0.006)

    def _build_earmuffs(self):
        s = self.size
        pad = self.mat("pad", self.spec["color"], rim=0.5, soft=0.5)
        band = self.mat("band", self.spec.get("band", "#c94a6a"))
        for k in (-1, 1):
            self.part(geo.ellipsoid(f"{self.id}.pad", (s * 0.35, s * 0.5, s * 0.5), (k * s, 0, 0), pad,
                                    collection=self.collection), 0.004)
        self.part(geo.tube(f"{self.id}.band", [(s * math.cos(a), 0, s * math.sin(a))
                                                for a in np.linspace(0, math.pi, 12)], s * 0.08, band, segments=6,
                           collection=self.collection), 0)

    def _build_firecrackers(self):
        s = self.size
        pole = self.mat("bamboo", "#c9b46a")
        red = self.mat("paper", self.spec["color"], rim=0.3)
        self.part(geo.tube(f"{self.id}.pole", [(0, 0, 0), (0, -0.6 * s, 1.1 * s), (0, -1.1 * s, 1.5 * s)], 0.025,
                           pole, segments=6, collection=self.collection), 0)
        parts = []
        for i in range(18):
            z = 1.45 * s - 0.08 * i
            for k in (-1, 1):
                parts.append(geo.ellipsoid_data((0.018, 0.018, 0.05), (-1.1 * s + k * 0.03, -0.0, z), 4, 6))
        cluster = geo.merge(f"{self.id}.crackers", parts, red, collection=self.collection)
        cluster.location = (0, -1.1 * s + 1.1 * s, 0)
        self.part(cluster, 0)

    def _build_table(self):
        s = self.size
        wood = self.mat("wood", self.spec["color"], rim=0.2)
        self.part(geo.rounded_box(f"{self.id}.top", (s * 1.4, s * 1.1, 0.06), 0.02, (0, 0, s * 0.9), wood,
                                  collection=self.collection), 0.012)

    def _build_stool(self):
        s = self.size
        wood = self.mat("wood", self.spec["color"], rim=0.2)
        self.part(geo.rounded_box(f"{self.id}.seat", (s, s, 0.05), 0.02, (0, 0, s * 1.1), wood,
                                  collection=self.collection), 0.01)

    def _build_leaf_wings(self):
        s = self.size
        leaf = self.mat("leaf", self.spec["color"], rim=0.3)
        vein = self.mat("vein", "#3f7a36")
        pts = [(0, 0, 0), (s * 0.5, 0, s * 0.08), (s, 0, 0)]
        self.part(geo.tube(f"{self.id}.leaf", pts, geo.taper(3, s * 0.08, s * 0.02, bulge=s * 0.18), leaf,
                           segments=10, flatten=0.12, twist_up=(0, 1, 0), collection=self.collection), 0.006)
        self.part(geo.tube(f"{self.id}.vein", pts, s * 0.01, vein, segments=4, collection=self.collection), 0)

    def _build_fish(self):
        s = self.size
        body = self.mat("scales", self.spec["color"], rim=0.6)
        self.part(geo.ellipsoid(f"{self.id}.fish", (s * 0.35, s, s * 0.45), (0, 0, 0), body,
                                collection=self.collection), 0.004)
        self.part(geo.cone(f"{self.id}.tail", s * 0.45, 0.0, s * 0.5, (0, s * 0.9, 0), body, segments=8,
                           collection=self.collection), 0)

    def _build_net(self):
        s = self.size
        rope = self.mat("rope", self.spec["color"])
        rng = random.Random(self.id)
        parts = []
        for i in range(9):
            a = rng.uniform(0, math.tau)
            pts = [(s * 0.5 * math.cos(a + u * 2), s * 0.5 * math.sin(a * 1.3 + u), s * (u - 0.5) * 0.6)
                   for u in np.linspace(0, 1, 8)]
            parts.append((geo.tube_vertices(pts, 0.012, 4), geo.tube_faces(8, 4)))
        self.part(geo.merge(f"{self.id}.net", parts, rope, collection=self.collection), 0)
        self.part(geo.ellipsoid(f"{self.id}.float", (s * 0.12,) * 3, (s * 0.4, 0, s * 0.35),
                                self.mat("float", "#ff8a3a", rim=0.4), collection=self.collection), 0.004)

    def _build_kite(self):
        s = self.size
        cloth = self.mat("kite", self.spec["color"], rim=0.3)
        verts = [(0, 0, s), (s * 0.6, 0, 0), (0, 0, -s * 1.2), (-s * 0.6, 0, 0)]
        self.part(geo.mesh_object(f"{self.id}.sail", verts, [(0, 1, 2, 3)], cloth, collection=self.collection), 0)

    def _build_star(self):
        s = self.size
        gold = self._glowing("star", self.spec["color"], self.spec.get("glow", 3.0))
        pts = []
        for i in range(10):
            a = math.pi / 2 + i * math.pi / 5
            r = s if i % 2 == 0 else s * 0.45
            pts.append((r * math.cos(a), 0, r * math.sin(a)))
        verts = pts + [(0, -s * 0.25, 0), (0, s * 0.25, 0)]
        faces = []
        for i in range(10):
            faces.append((i, (i + 1) % 10, 10))
            faces.append(((i + 1) % 10, i, 11))
        self.part(geo.mesh_object(f"{self.id}.star", verts, faces, gold, collection=self.collection), 0.004)

    # ------------------------------------------------------------------ state
    def state(self, t):
        visible = False
        place, hold, move, scale, glow = None, None, None, 1.0, None
        for e in self.events:
            if e["t"] > t:
                break
            kind = e["type"]
            if kind == "show":
                visible = True
            elif kind == "hide":
                visible = False
            elif kind == "place":
                place, hold, move = e, None, None
            elif kind == "hold":
                hold, place, move = e, None, None
            elif kind == "move":
                move, hold = e, None
            elif kind == "scale":
                u = smooth((t - e["t"]) / max(e["dur"], 1e-3))
                scale = scale + (e["value"] - scale) * u
            elif kind == "glow":
                glow = e
        return visible, place, hold, move, scale, glow

    def update(self, t, rigs):
        visible, place, hold, move, scale, glow = self.state(t)
        for o in [self.root] + self.parts:
            o.hide_render = not visible
        if not visible:
            return
        self.root.scale = (scale, scale, scale)
        if hold is not None and hold["who"] in rigs:
            anchor = rigs[hold["who"]].anchor(hold.get("hand", "r"))
            off = Vector(hold.get("offset", (0, 0, 0)))
            self.root.matrix_world = anchor @ Matrix.Translation(off) @ Matrix.Diagonal((scale, scale, scale, 1))
        elif move is not None and t <= move["t"] + move["dur"]:
            u = smooth((t - move["t"]) / max(move["dur"], 1e-3))
            pts = [Vector(p) for p in move["path"]]
            if len(pts) == 1:
                pos = pts[0]
            else:
                f = u * (len(pts) - 1)
                i = min(int(f), len(pts) - 2)
                pos = pts[i].lerp(pts[i + 1], f - i)
            self.root.location = pos
            self.root.rotation_euler = (0, 0, move.get("spin", 0.0) * u * math.tau)
        elif place is not None:
            self.root.location = place["at"]
            self.root.rotation_euler = [math.radians(v) for v in place.get("rot", (0, 0, 0))]
        if glow is not None:
            u = smooth((t - glow["t"]) / max(glow["dur"], 1e-3))
            for group, base in self.glow_mats:
                group.inputs["Glow"].default_value = base * glow["value"] * u + base * (1 - u) * 0.0


# ---------------------------------------------------------------------------- particles
class Particles:
    """Many small shapes in one mesh; positions and sizes are rewritten each frame."""

    def __init__(self, name, count, shape, material, collection, radius=1.0):
        verts, faces = shape
        self.base = np.asarray(verts, dtype=np.float32) * radius
        self.n = count
        k = len(self.base)
        all_faces = [tuple(i + p * k for i in f) for p in range(count) for f in faces]
        self.obj = geo.mesh_object(name, np.zeros((count * k, 3)), all_faces, material, collection=collection)
        self.obj.visible_shadow = False

    def update(self, positions, sizes):
        pos = np.asarray(positions, dtype=np.float32).reshape(self.n, 1, 3)
        size = np.asarray(sizes, dtype=np.float32).reshape(self.n, 1, 1)
        co = (self.base[None, :, :] * size + pos).reshape(-1)
        self.obj.data.vertices.foreach_set("co", co)
        self.obj.data.update()

    def hide(self, hidden=True):
        self.obj.hide_render = hidden


def _glow_material(look, name, color, strength=2.0):
    from codecinema.cartoon.blender.look import rgba
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    t = m.node_tree
    t.nodes.clear()
    em = t.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = rgba(color)
    em.inputs["Strength"].default_value = strength
    out = t.nodes.new("ShaderNodeOutputMaterial")
    t.links.new(em.outputs[0], out.inputs["Surface"])
    return m


OCTA = ([(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)],
        [(0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4), (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)])


class Effects:
    """Every timed effect in the film, built once and posed per frame."""

    def __init__(self, plan, look, collection):
        self.look, self.collection = look, collection
        self.items = []
        for i, e in enumerate(plan.get("fx", [])):
            builder = getattr(self, f"_fx_{e['name']}", None)
            if builder is None:
                raise ValueError(f"Unknown effect '{e['name']}'")
            self.items.append((e, builder(e, random.Random(i * 7919 + 13))))
        self.snow = None

    def weather(self, kind):
        if kind == "snow" and self.snow is None:
            mat = _glow_material(self.look, "snowflake", "#f4f8ff", 1.1)
            self.snow = Particles("snowfall", 1400, OCTA, mat, self.collection, 1.0)
            rng = np.random.default_rng(5)
            self.snow_seed = rng.random((1400, 4))
        return self.snow

    def update_weather(self, kind, t, camera):
        if self.snow is not None:
            self.snow.hide(kind != "snow")
        if kind != "snow" or self.snow is None:
            return
        s = self.snow_seed
        box = np.array((26.0, 26.0, 14.0))
        cam = np.asarray(camera, dtype=float)
        base = s[:, :3] * box
        base[:, 2] -= t * (0.55 + 0.4 * s[:, 3])
        base[:, 0] += t * 0.35 + 0.25 * np.sin(t * 0.8 + s[:, 3] * 9)
        # Flakes live in a world-space lattice repeated every box; show the copy nearest the camera.
        base = np.mod(base, box)
        pos = base + box * np.round((cam - base) / box)
        sizes = 0.018 + 0.02 * s[:, 3]
        # Flakes right at the lens would read as big white diamonds: fade them out near the camera.
        near = np.linalg.norm(pos - cam, axis=1)
        sizes = sizes * np.clip((near - 1.0) / 2.5, 0.0, 1.0)
        self.snow.update(pos, sizes)

    def update(self, t):
        for e, fx in self.items:
            local = t - e["t"]
            active = 0 <= local <= e["dur"]
            fx(local if active else None)

    # ------------------------------------------------------------------ effects
    def _burst(self, e, rng, count, color, speed, gravity, life, size, glow=2.0, shape=OCTA, spread=1.0, up=0.6,
               drag=0.0, fade=True):
        mat = _glow_material(self.look, f"fx {e['name']}", color, glow)
        p = Particles(f"fx {e['name']}", count, shape, mat, self.collection)
        origin = np.array(e["pos"] or (0, 0, 0), dtype=float)
        dirs = rng_dirs(rng, count, up)
        speeds = np.array([rng.uniform(0.5, 1.0) for _ in range(count)]) * speed
        delays = np.array([rng.uniform(0, 0.15) for _ in range(count)])

        def pose(local):
            if local is None:
                p.hide(True)
                return
            p.hide(False)
            tt = np.maximum(local - delays, 0)[:, None]
            v = dirs * speeds[:, None] * spread
            k = np.exp(-drag * tt) if drag else 1.0
            pos = origin + v * (tt if not drag else (1 - k) / drag) + np.array((0, 0, -0.5 * gravity)) * tt ** 2
            age = np.clip(tt[:, 0] / life, 0, 1)
            sz = size * (1 - age ** 2 if fade else 1.0) * (tt[:, 0] > 0)
            p.update(pos, sz)
        return pose

    def _fx_splash(self, e, rng):
        return self._burst(e, rng, 60, "#e8fbff", 3.0, 9.8, 0.9, 0.05, glow=1.2, up=1.6)

    def _fx_big_splash(self, e, rng):
        return self._burst(e, rng, 160, "#e8fbff", 5.0, 9.8, 1.2, 0.08, glow=1.2, up=2.0)

    def _fx_sparkles(self, e, rng):
        mat = _glow_material(self.look, "fx sparkle", e["params"].get("color", "#fff2a8"), 4.0)
        n = 40
        p = Particles("fx sparkles", n, OCTA, mat, self.collection)
        origin = np.array(e["pos"] or (0, 0, 0), dtype=float) + np.array((0, 0, e["params"].get("height", 0.8)))
        offs = rng_dirs(rng, n, 0.0) * np.array([[rng.uniform(0.2, 1.0)] for _ in range(n)]) * e["params"].get(
            "radius", 0.8)
        phase = np.array([rng.uniform(0, 6.3) for _ in range(n)])

        def pose(local):
            if local is None:
                p.hide(True)
                return
            p.hide(False)
            tw = np.clip(np.sin(local * 7 + phase), 0, 1) ** 3
            env = math.sin(math.pi * min(1.0, local / max(e["dur"], 1e-3)))
            p.update(origin + offs + np.array((0, 0, 0.15)) * local, 0.035 * tw * env + 0.002)
        return pose

    def _fx_bubbles(self, e, rng):
        mat = _glow_material(self.look, "fx bubble", "#d8fbff", 1.3)
        n = 30
        p = Particles("fx bubbles", n, geo.ellipsoid_data((1, 1, 1), rings=6, segments=8), mat, self.collection)
        origin = np.array(e["pos"] or (0, 0, 0), dtype=float)
        delays = np.array([rng.uniform(0, e["dur"] * 0.7) for _ in range(n)])
        offs = np.array([(rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), 0) for _ in range(n)])
        sizes = np.array([rng.uniform(0.01, 0.03) for _ in range(n)])

        def pose(local):
            if local is None:
                p.hide(True)
                return
            p.hide(False)
            tt = np.maximum(local - delays, 0)
            pos = origin + offs + np.stack([0.08 * np.sin(tt * 6 + delays * 9), 0.0 * tt, tt * 1.2], axis=1)
            p.update(pos, sizes * (tt > 0))
        return pose

    def _fx_dust(self, e, rng):
        return self._burst(e, rng, 24, "#e8dcc0", 0.8, -0.2, 0.8, 0.12, glow=0.9, up=0.3, drag=2.0)

    def _fx_snow_puff(self, e, rng):
        return self._burst(e, rng, 30, "#f4f8ff", 1.2, 1.0, 0.8, 0.1, glow=1.0, up=0.6, drag=2.0)

    def _fx_smoke(self, e, rng):
        return self._burst(e, rng, 26, "#c8c4d0", 0.5, -0.6, 2.0, 0.22, glow=0.5, up=1.2, drag=1.0)

    def _fx_steam(self, e, rng):
        return self._burst(e, rng, 18, "#ffffff", 0.25, -0.35, 1.8, 0.05, glow=0.7, up=3.0, drag=0.5)

    def _fx_ripples(self, e, rng):
        return self._burst(e, rng, 40, "#e8fbff", 1.2, 0.0, 1.2, 0.03, glow=1.2, up=0.0, drag=1.2)

    def _fx_light_burst(self, e, rng):
        return self._burst(e, rng, 80, e["params"].get("color", "#fff2c0"), 3.0, 0.0, 0.8, 0.05, glow=6.0, up=0.0,
                           drag=1.5)

    def _fx_tears(self, e, rng):
        return self._burst(e, rng, 12, "#9fe0ff", 1.6, 9.8, 0.6, 0.03, glow=1.0, up=1.0)

    def _fx_sweat(self, e, rng):
        return self._burst(e, rng, 3, "#9fe0ff", 0.4, 2.0, 0.6, 0.04, glow=1.0, up=1.0)

    def _fx_hearts(self, e, rng):
        return self._burst(e, rng, 10, "#ff7aa8", 0.5, -0.8, 1.6, 0.06, glow=2.0, up=3.0, drag=0.8)

    def _fx_firecracker_burst(self, e, rng):
        """Crackling sparks, red paper bits and smoke along a string, popping in quick succession."""
        sparks = self._burst(e, rng, 220, "#ffd36a", 2.6, 4.0, 0.35, 0.025, glow=8.0, up=0.4, fade=True)
        paper = self._burst(e, rng, 90, "#e0302a", 1.4, 2.5, 1.6, 0.03, glow=0.8, up=0.6, drag=1.5)
        smoke = self._burst(e, rng, 30, "#d8d4e0", 0.5, -0.4, 2.5, 0.25, glow=0.35, up=1.0, drag=1.0)
        cycle = 0.32

        def pose(local):
            if local is None:
                sparks(None), paper(None), smoke(None)
                return
            sparks(local % cycle)
            paper(local)
            smoke(local)
        return pose

    def _fx_fireworks(self, e, rng):
        """Shells rise and bloom; each burst has its own color, glitter and falling trails."""
        palette = e["params"].get("colors", ["#ff5a5a", "#ffd34a", "#7ad0ff", "#c48aff", "#7affb2"])
        shells = []
        count = int(e["params"].get("count", 5))
        for k in range(count):
            when = rng.uniform(0, max(0.1, e["dur"] - 2.0))
            pos = np.array(e["pos"] or (0, 30, 0), dtype=float) + np.array(
                (rng.uniform(-12, 12), rng.uniform(-4, 6), rng.uniform(16, 26)))
            sub = {"pos": tuple(pos), "name": "firework"}
            color = palette[k % len(palette)]
            burst = self._burst(sub, rng, 240, color, 9.5, 3.0, 2.0, 0.16, glow=10.0, up=0.0, drag=1.1)
            shells.append((when, burst))

        def pose(local):
            for when, burst in shells:
                if local is None or local < when or local > when + 2.0:
                    burst(None)
                else:
                    burst(local - when)
        return pose


def rng_dirs(rng, n, up):
    out = []
    for _ in range(n):
        z = rng.uniform(-1, 1)
        a = rng.uniform(0, math.tau)
        r = math.sqrt(max(0.0, 1 - z * z))
        v = np.array((r * math.cos(a), r * math.sin(a), z + up))
        out.append(v / max(np.linalg.norm(v), 1e-6))
    return np.array(out)
