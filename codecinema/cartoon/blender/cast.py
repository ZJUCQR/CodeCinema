"""Build library characters in Blender and pose them every frame.

A character is a small hierarchy of empties (root -> body -> chest -> neck)
carrying rigid parts, plus "noodle" limbs whose tube meshes are rebuilt from a
two-bone solve each frame. Faces are painted atlases projected onto the head;
`Rig.apply()` turns a semantic pose from `codecinema.cartoon.motion` into
transforms, limb shapes and face cells.
"""
import math

import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector

from codecinema.cartoon.blender import geometry as geo
from codecinema.cartoon.blender.look import add_outline, link, math_node, mix_color, node, rgba


SKIN_SHADOW = (0.86, 0.66, 0.70, 1.0)
FACE_SHADOW = (0.92, 0.80, 0.82, 1.0)


def _shade(color, k):
    c = color.lstrip("#")
    r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4))
    if k >= 0:
        r, g, b = (v + (255 - v) * k for v in (r, g, b))
    else:
        r, g, b = (v * (1 + k) for v in (r, g, b))
    return "#{:02x}{:02x}{:02x}".format(*(int(max(0, min(255, v))) for v in (r, g, b)))


def _faded(color, amount):
    """Sun-faded fabric: lighter and greyer, as an old scarf would be."""
    c = color.lstrip("#")
    r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4))
    grey = (r + g + b) / 3
    out = [v + (grey - v) * amount * 0.6 for v in (r, g, b)]
    out = [v + (235 - v) * amount * 0.25 for v in out]
    return "#{:02x}{:02x}{:02x}".format(*(int(v) for v in out))


def _sphere_point(radius, azimuth, elevation, center=(0, 0, 0)):
    """Azimuth 0 faces the front (-Y), positive toward the character's left (+X)."""
    a, e = math.radians(azimuth), math.radians(elevation)
    return Vector((center[0] + radius * math.cos(e) * math.sin(a), center[1] - radius * math.cos(e) * math.cos(a),
                   center[2] + radius * math.sin(e)))


def rest_hand(m, side):
    """Hand offset from the shoulder for relaxed arms, clearing round bellies."""
    clear = max(0.0, m["torso_r"] * 1.08 - m["shoulder"][0]) + m.get("hand_r", 0.05) * 0.4
    return (side * (0.03 + clear), -0.02 - clear * 0.3, -m["arm"] * (0.86 if clear < 0.1 else 0.7))


def solve_two_bone(start, target, upper, lower, pole):
    """Elbow or knee position for a limb reaching from `start` toward `target`, bending toward `pole`."""
    start, target, pole = Vector(start), Vector(target), Vector(pole)
    d = target - start
    dist = max(1e-5, min(d.length, (upper + lower) * 0.999))
    direction = d.normalized()
    target = start + direction * dist
    along = (upper * upper - lower * lower + dist * dist) / (2 * dist)
    height = math.sqrt(max(upper * upper - along * along, 0.0))
    bend = pole - direction * pole.dot(direction)
    bend = bend.normalized() if bend.length > 1e-6 else Vector((0, -1, 0))
    return start + direction * along + bend * height, target


class Rig:
    def __init__(self, cid, spec, metrics, look, atlas, collection, outline=None):
        self.id, self.spec, self.m, self.look, self.atlas = cid, spec, metrics, look, atlas
        self.collection = collection
        self.outline = outline if outline is not None else 0.0075 * max(0.8, metrics["height"]) ** 0.6
        self.inked = []
        self.face_nodes = {}
        self.parts = {}
        m = metrics
        self.root = geo.empty(cid, collection=collection)
        self.body = geo.empty(f"{cid}.body", (0, 0, m["hip"]), self.root, collection)
        self.chest = geo.empty(f"{cid}.chest", (0, 0, m["chest"] - m["hip"]), self.body, collection)
        self.neck = geo.empty(f"{cid}.neck", (0, 0, m["neck"] - m["chest"]), self.chest, collection)
        self.limbs = {}
        self.wings = {}
        self.ears = {}
        self.tail = None
        self.beak = None
        self.props = {}
        plan = spec["plan"]
        getattr(self, f"_build_{plan}")()
        for obj in self.inked:
            add_outline(look, obj, self.outline * obj.get("ink", 1.0))

    # ------------------------------------------------------------------ materials
    def mat(self, label, color, **kw):
        return self.look.material(f"{self.id} {label}", color, **kw)

    def ink(self, obj, weight=1.0):
        obj["ink"] = weight
        self.inked.append(obj)
        return obj

    def _face_material(self, head, skin, radius):
        """Skin plus projected layers: markings, blush, eyes (with gaze), brows and mouth."""
        mat = bpy.data.materials.new(f"{self.id} face")
        mat.use_nodes = True
        t = mat.node_tree
        t.nodes.clear()
        coord = node(t, "ShaderNodeTexCoord", (-1600, 0))
        coord.object = head
        sep = node(t, "ShaderNodeSeparateXYZ", (-1400, 0))
        link(t, coord.outputs["Object"], sep.inputs[0])
        scale = 1 / (2 * radius)
        u = math_node(t, "MULTIPLY_ADD", sep.outputs["X"], scale, (-1200, 100))
        u.node.inputs[2].default_value = 0.5
        v = math_node(t, "MULTIPLY_ADD", sep.outputs["Z"], scale, (-1200, -100))
        v.node.inputs[2].default_value = 0.5
        uv = node(t, "ShaderNodeCombineXYZ", (-1000, 0))
        link(t, u, uv.inputs[0])
        link(t, v, uv.inputs[1])
        front = node(t, "ShaderNodeMapRange", (-1000, -300), clamp=True)
        link(t, sep.outputs["Y"], front.inputs["Value"])
        front.inputs["From Min"].default_value = 0.02 * radius
        front.inputs["From Max"].default_value = -0.18 * radius
        inside = front.outputs[0]
        for value, op, edge in ((u, "GREATER_THAN", 0.0), (u, "LESS_THAN", 1.0), (v, "GREATER_THAN", 0.0),
                                (v, "LESS_THAN", 1.0)):
            inside = math_node(t, "MULTIPLY", inside, math_node(t, op, value, edge, (-800, -400)), (-650, -400))
        color = None
        skin_rgb = node(t, "ShaderNodeRGB", (-800, 300))
        skin_rgb.outputs[0].default_value = rgba(skin)
        color = skin_rgb.outputs[0]
        x = -600
        for layer in ("markings", "blush", "eyes", "brows", "mouth"):
            info = self.atlas.get(layer)
            if not info:
                continue
            grid = info["grid"]
            mapping = node(t, "ShaderNodeMapping", (x, -200), vector_type="POINT")
            mapping.inputs["Scale"].default_value = (1 / grid, 1 / grid, 1)
            link(t, uv.outputs[0], mapping.inputs["Vector"])
            tex = node(t, "ShaderNodeTexImage", (x + 180, -200), interpolation="Cubic", extension="CLIP")
            tex.image = bpy.data.images.load(info["file"], check_existing=True)
            tex.image.alpha_mode = "STRAIGHT"
            link(t, mapping.outputs[0], tex.inputs["Vector"])
            alpha = math_node(t, "MULTIPLY", tex.outputs["Alpha"], inside, (x + 380, -350))
            if layer == "blush":
                amount = node(t, "ShaderNodeValue", (x + 200, -450), name="Blush", label="Blush")
                amount.outputs[0].default_value = 0.0
                alpha = math_node(t, "MULTIPLY", alpha, amount.outputs[0], (x + 450, -450))
            _, f, a, b, res = mix_color(t, "MIX", (x + 560, 100))
            link(t, alpha, f)
            link(t, color, a)
            link(t, tex.outputs["Color"], b)
            color = res
            self.face_nodes[layer] = (mapping, grid, info["cells"])
            x += 700
        group = node(t, "ShaderNodeGroup", (x, 0))
        group.node_tree = self.look.group
        link(t, color, group.inputs["Color"])
        group.inputs["Shadow"].default_value = FACE_SHADOW
        group.inputs["Soft"].default_value = 1.0
        group.inputs["Rim"].default_value = 0.25
        out = node(t, "ShaderNodeOutputMaterial", (x + 250, 0))
        link(t, group.outputs[0], out.inputs["Surface"])
        mat["outline"] = _shade(skin, -0.62)
        self.blush_node = t.nodes.get("Blush")
        return mat

    def set_face(self, eyes=None, brows=None, mouth=None, gaze=(0.0, 0.0), blush=None):
        for layer, cell in (("eyes", eyes), ("brows", brows), ("mouth", mouth)):
            if cell is None or layer not in self.face_nodes:
                continue
            mapping, grid, cells = self.face_nodes[layer]
            if cell not in cells:
                cell = cells[0]
            i = cells.index(cell)
            col, row = i % grid, grid - 1 - i // grid
            gx, gz = gaze if layer == "eyes" else (0.0, 0.0)
            mapping.inputs["Location"].default_value = ((col - gx) / grid, (row - gz) / grid, 0)
        if blush is not None and self.blush_node is not None:
            self.blush_node.outputs[0].default_value = blush

    # ------------------------------------------------------------------ shared pieces
    def _head(self, radius, shape=(1.0, 0.95, 0.93), chin=0.12, skin=None):
        m = self.m
        skin = skin or self.spec["skin"]
        head = geo.ellipsoid(f"{self.id}.head", (radius * shape[0], radius * shape[1], radius * shape[2]),
                             parent=self.neck, collection=self.collection, rings=40, segments=72)
        head.location = (0, 0, m["head_z"] - m["neck"])
        if chin:
            co = np.empty(len(head.data.vertices) * 3, dtype=np.float32)
            head.data.vertices.foreach_get("co", co)
            co = co.reshape(-1, 3)
            lower = np.clip(-co[:, 2] / radius, 0, 1)
            fwd = np.clip(-co[:, 1] / radius, 0, 1)
            co[:, 2] -= chin * radius * lower ** 2 * fwd
            co[:, 0] *= 1 - 0.10 * lower ** 1.5
            head.data.vertices.foreach_set("co", co.ravel())
            head.data.update()
        head.data.materials.append(self._face_material(head, skin, radius))
        self.parts["head"] = head
        return self.ink(head)

    def _hair(self, style, color, radius):
        if style in ("none",):
            return
        head = self.parts["head"]
        hair = self.mat("hair", color, rim=0.45)
        r = radius
        bangs_line = 0.52
        back_line = -0.62 if style not in ("bob", "braids", "twintails", "ponytail") else -0.75
        if style == "elder_bun":
            bangs_line, back_line = 0.42, -0.55
        if style == "bald":
            bangs_line, back_line = 0.05, -0.5
        cap = self._cap(r, bangs_line, back_line, fringe=(style == "bald"))
        cap.data.materials.append(hair)
        cap.visible_shadow = False
        self.ink(cap)
        locks = []

        def lock(az, el, length, width, droop=0.85, curl=0.0, thick=0.42, out=0.12, tip=0.08):
            root = _sphere_point(r * 0.95, az, el, (0, r * 0.03, r * 0.035))
            normal = (root - Vector((0, r * 0.03, r * 0.035))).normalized()
            mid = root + normal * r * out + Vector((0, 0, -1)) * length * 0.45 * droop + normal * length * 0.2
            side = Vector((math.sin(math.radians(az)), -math.cos(math.radians(az)), 0)) * curl * length
            end = root + normal * r * (out + 0.05) + Vector((0, 0, -1)) * length * droop + normal * length * (
                1 - droop) * 0.6 + side
            pts = geo.bezier(root, mid, end, 9)
            # Shrink-wrap: locks lie on the skull instead of sinking into it, fuller toward the tips.
            center = np.array((0, r * 0.03, r * 0.035))
            for k in range(1, len(pts)):
                d = pts[k] - center
                floor = r * (1.04 + 0.05 * k / (len(pts) - 1))
                if np.linalg.norm(d) < floor:
                    # Push out horizontally, keeping the height, so locks still fall over the brow.
                    flat = math.hypot(d[0], d[1])
                    reach = math.sqrt(max(floor * floor - d[2] * d[2], 0.0))
                    if flat > 1e-6:
                        pts[k][0] = center[0] + d[0] / flat * reach
                        pts[k][1] = center[1] + d[1] / flat * reach
            radii = geo.taper(9, width, width * tip, bulge=width * 0.15, power=1.4)
            verts = geo.tube_vertices(pts, radii, 8, thick, twist_up=tuple(normal))
            locks.append((verts, geo.tube_faces(9, 8)))

        if style in ("buns", "twintails", "bob", "short", "ponytail", "braids", "spiky"):
            n = 7 if style != "spiky" else 6
            for i in range(n):
                az = -60 + 120 * i / (n - 1)
                length = r * (0.62 + 0.09 * ((i * 3) % 2) - 0.08 * abs(az) / 60) * (1.1 if style == "bob" else 1.0)
                lock(az, 64 - 6 * abs(az) / 60, length, r * 0.21, droop=0.92, curl=0.1 * (1 if az > 0 else -1),
                     out=0.08, thick=0.38)
            for az in (-80, 80):
                lock(az, 40, r * (1.05 if style in ("bob", "twintails", "buns") else 0.7), r * 0.18, droop=0.96,
                     out=0.06)
        if style == "bob":
            for i in range(9):
                az = 100 + 160 * i / 8
                lock(az, 20, r * 0.95, r * 0.24, droop=0.95, out=0.08)
        if style == "spiky":
            for i in range(9):
                az = -150 + 300 * i / 8
                el = 45 + 25 * math.sin(i * 1.7)
                lock(az, el, r * 0.55, r * 0.2, droop=0.25, out=0.1, tip=0.05)
        if style == "short":
            for i in range(6):
                lock(120 + 24 * i, 25, r * 0.4, r * 0.22, droop=0.9)
        if locks:
            obj = geo.merge(f"{self.id}.locks", locks, hair, collection=self.collection, parent=head)
            obj.data.shade_smooth()
            obj.visible_shadow = False
            self.ink(obj, 0.8)
        ties = self.mat("hair tie", self.spec.get("hair", {}).get("tie", "#e04a43"))
        if style == "buns":
            for side in (-1, 1):
                c = _sphere_point(r * 0.98, side * 58, 50, (0, r * 0.03, r * 0.03))
                bun = geo.ellipsoid(f"{self.id}.bun", (r * 0.36, r * 0.34, r * 0.34), tuple(c), hair,
                                    parent=head, collection=self.collection, rings=16, segments=24)
                self.ink(bun)
                tie = geo.ellipsoid(f"{self.id}.ribbon", (r * 0.16, r * 0.08, r * 0.08),
                                    tuple(c + (c - Vector((0, 0, 0))).normalized() * r * 0.05
                                          + Vector((0, -r * 0.15, -r * 0.25))), ties, parent=head,
                                    collection=self.collection, rings=10, segments=16)
                self.ink(tie, 0.7)
        if style in ("twintails", "ponytail", "braids"):
            sides = (-1, 1) if style != "ponytail" else (0,)
            for side in sides:
                az = side * 105 if side else 180
                el = 25 if side else 38
                root = _sphere_point(r * 1.02, az, el, (0, r * 0.03, r * 0.03))
                if style == "braids":
                    for k in range(6):
                        p = root + Vector((side * r * 0.08, r * 0.05, -r * (0.15 + 0.22 * k)))
                        ball = geo.ellipsoid(f"{self.id}.braid", (r * 0.15 * (1 - k * 0.06),) * 3, tuple(p), hair,
                                             parent=head, collection=self.collection, rings=10, segments=16)
                        self.ink(ball, 0.7)
                    continue
                outward = Vector((side * 0.6, 0.6 if not side else 0.25, 0)).normalized()
                mid = root + outward * r * 0.45 + Vector((0, 0, -r * 0.55))
                end = root + outward * r * 0.55 + Vector((0, r * 0.12, -r * 1.6))
                pts = geo.bezier(root, mid, end, 12)
                tail = geo.tube(f"{self.id}.tail_hair", pts, geo.taper(12, r * 0.22, r * 0.03, bulge=r * 0.12),
                                hair, segments=10, flatten=0.8, parent=head, collection=self.collection)
                self.ink(tail, 0.8)
                band = geo.ellipsoid(f"{self.id}.tie", (r * 0.12, r * 0.12, r * 0.06), tuple(root), ties,
                                     parent=head, collection=self.collection, rings=8, segments=16)
                self.ink(band, 0.6)
        if style == "elder_bun":
            c = _sphere_point(r * 1.0, 180, 40, (0, r * 0.03, r * 0.03))
            bun = geo.ellipsoid(f"{self.id}.bun", (r * 0.42, r * 0.36, r * 0.36), tuple(c), hair, parent=head,
                                collection=self.collection)
            self.ink(bun)
            pin = self.mat("hairpin", "#c9a14a", rim=0.6)
            geo.tube(f"{self.id}.pin", [c + Vector((-r * 0.55, r * 0.05, r * 0.1)), c,
                                         c + Vector((r * 0.55, r * 0.05, -r * 0.05))], r * 0.035, pin,
                     segments=6, parent=head, collection=self.collection)

    def _cap(self, r, front, back, fringe=False):
        """A hair shell whose lower edge follows a smooth hairline: high over the brow, low at the nape."""
        center = Vector((0, r * 0.03, r * 0.035))
        radii = (r * 1.07, r * 1.05, r * 1.06)
        cols, rows = 48, 14
        verts = []
        for i in range(rows):
            for j in range(cols):
                az = 2 * math.pi * j / cols
                blend = (1 - math.cos(az)) / 2
                low = front * (1 - blend) + back * blend
                high = 0.995
                if fringe:
                    low, high = -0.55, 0.12 + 0.25 * (1 - blend)
                    if blend < 0.35:
                        high = low + 0.02
                el = math.asin(max(-0.99, min(0.99, low + (high - low) * (i / (rows - 1)) ** (0.85 if not fringe
                                                                                         else 1.0))))
                verts.append((center.x + radii[0] * math.cos(el) * math.sin(az),
                              center.y - radii[1] * math.cos(el) * math.cos(az),
                              center.z + radii[2] * math.sin(el)))
        faces = geo.grid_faces(rows, cols)
        if not fringe:
            pole = len(verts)
            verts.append((center.x, center.y, center.z + radii[2]))
            last = (rows - 1) * cols
            for j in range(cols):
                faces.append((pole, last + j, last + (j + 1) % cols))
        return geo.mesh_object(f"{self.id}.hair", verts, faces, parent=self.parts["head"], collection=self.collection)

    def _accessories(self):
        r = self.m["head_r"]
        head = self.parts["head"]
        face = self.spec.get("face", {})
        for item in self.spec.get("accessories", []):
            kind = item["kind"]
            if kind == "glasses":
                frame = self.mat("glasses", item.get("color", "#5a3a22"), rim=0.5)
                ex, ey = face.get("eye_x", 0.36) * r, face.get("eye_y", -0.1) * r
                for side in (-1, 1):
                    cx = side * ex
                    y = -math.sqrt(max(r * r - cx * cx - ey * ey, 0.0)) - r * 0.06
                    ring = [Vector((cx + r * 0.2 * math.cos(a), y, ey + r * 0.19 * math.sin(a)))
                            for a in np.linspace(0, 2 * math.pi, 25)]
                    obj = geo.tube(f"{self.id}.glasses", ring, r * 0.022, frame, segments=6, parent=head,
                                   collection=self.collection)
                    self.ink(obj, 0.5)
                bridge = [Vector((-ex + r * 0.2, -r * 0.98, ey + r * 0.05)), Vector((0, -r * 1.02, ey + r * 0.09)),
                          Vector((ex - r * 0.2, -r * 0.98, ey + r * 0.05))]
                geo.tube(f"{self.id}.bridge", bridge, r * 0.02, frame, segments=6, parent=head,
                         collection=self.collection)
            elif kind == "scarf":
                color = _faded(item.get("color", "#c0392b"), item.get("faded", 0.0))
                cloth = self.mat("scarf", color, rim=0.4, soft=0.2)
                m = self.m
                big = max(1.0, m["height"] / 1.1)
                ring_r = m["torso_r"] * (0.62 if self.spec["plan"] == "biped" else 0.82)
                z = (m["neck"] - m["chest"]) - r * 0.06
                thick = r * 0.13 * big ** 0.25
                loop = [Vector((ring_r * math.cos(a), ring_r * 0.92 * math.sin(a), z + thick * 0.25 * math.sin(2 * a)))
                        for a in np.linspace(0, 2 * math.pi, 33)]
                self.ink(geo.tube(f"{self.id}.scarf", loop, thick, cloth, segments=10, flatten=0.6,
                                  parent=self.chest, collection=self.collection))
                knot = Vector((ring_r * 0.42, -ring_r * 0.88, z - thick * 0.3))
                self.ink(geo.ellipsoid(f"{self.id}.scarf_knot", (thick * 1.1, thick * 0.8, thick * 1.0), tuple(knot),
                                       cloth, parent=self.chest, collection=self.collection, rings=10, segments=16))
                # Ends drape over whatever bulges below the neck: a padded jacket or a round belly.
                drape = max(0.0, m["torso_r"] * (1.12 if self.spec["plan"] == "biped" else 1.05) - ring_r)
                tails = []
                for k in range(2):
                    base = knot + Vector((thick * 0.3 * (k - 0.5), -thick * 0.2, -thick * 0.4))
                    obj = geo.tube(f"{self.id}.scarf_tail", [base, base + Vector((0, 0, -0.1)),
                                                              base + Vector((0, 0, -0.2))],
                                   thick * 0.95, cloth, segments=8, flatten=0.32, twist_up=(0, -1, 0),
                                   parent=self.chest, collection=self.collection)
                    obj["base"] = list(base)
                    obj["length"] = r * (0.75 + 0.22 * k) * big ** 0.4
                    obj["width"] = thick * (0.95 - 0.1 * k)
                    obj["splay"] = 0.18 + 0.22 * k
                    obj["drape"] = drape
                    self.ink(obj, 0.8)
                    tails.append(obj)
                self.parts["scarf_tails"] = tails
            elif kind == "earmuffs":
                pad = self.mat("earmuffs", item.get("color", "#f2d6e0"), rim=0.5, soft=0.4)
                band = self.mat("earmuff band", item.get("band", "#c94a6a"))
                az, el, k = item.get("azimuth", 92), item.get("elevation", 5), item.get("size", 1.0)
                for side in (-1, 1):
                    p = _sphere_point(r * (1.08 + 0.12 * (k - 1)), side * az, el)
                    muff = geo.ellipsoid(f"{self.id}.muff", (r * 0.12 * k, r * 0.24 * k, r * 0.26 * k), tuple(p), pad,
                                         parent=head, collection=self.collection)
                    self.ink(muff)
                arc = [_sphere_point(r * (1.12 + 0.1 * (k - 1)), -az + 2 * az * i / 12,
                                     el + 5 + (85 - el) * math.sin(math.pi * i / 12)) for i in range(13)]
                self.ink(geo.tube(f"{self.id}.muff_band", arc, r * 0.05, band, segments=6, parent=head,
                                  collection=self.collection), 0.6)
            elif kind == "ribbon":
                bow = self.mat("ribbon", item.get("color", "#e23b3b"))
                p = _sphere_point(r * 1.04, item.get("azimuth", 35), item.get("elevation", 62))
                for side in (-1, 1):
                    lobe = geo.ellipsoid(f"{self.id}.bow", (r * 0.17, r * 0.06, r * 0.11),
                                         tuple(p + Vector((side * r * 0.15, 0, 0))), bow, parent=head,
                                         collection=self.collection, rings=10, segments=16)
                    self.ink(lobe, 0.6)

    # ------------------------------------------------------------------ biped
    def _build_biped(self):
        s, m = self.spec, self.m
        r = m["head_r"]
        outfit = s.get("outfit", {})
        animal = s.get("animal", {})
        top = self.mat("top", outfit.get("top", "#d8473d"), soft=0.15)
        trim = self.mat("trim", outfit.get("trim", "#f3c75f"))
        tr = m["torso_r"]
        hem = -r * 0.32 if outfit.get("top_style") != "coat" else -r * 0.55
        top_z = m["neck"] - m["hip"] + r * 0.05
        style = outfit.get("top_style", "shirt")
        if style == "fur":
            # A round, fluffy belly in one piece, with a pale front patch.
            prof = [(tr * f, hem + (top_z - hem) * u) for u, f in
                    ((0.0, 0.55), (0.06, 0.92), (0.2, 1.08), (0.42, 1.1), (0.65, 1.0), (0.85, 0.78), (1.0, 0.45))]
        elif style == "padded":
            prof = [(tr * f, hem + (top_z - hem) * u) for u, f in
                    ((0.0, 1.06), (0.08, 1.1), (0.35, 1.02), (0.6, 1.0), (0.8, 0.92), (0.93, 0.7), (1.0, 0.42))]
        elif style == "dress":
            prof = [(tr * f, hem - r * 0.3 + (top_z - hem + r * 0.3) * u) for u, f in
                    ((0.0, 1.45), (0.25, 1.15), (0.45, 0.9), (0.65, 0.95), (0.85, 0.85), (1.0, 0.45))]
        elif style == "coat":
            prof = [(tr * f, hem + (top_z - hem) * u) for u, f in
                    ((0.0, 1.08), (0.3, 1.0), (0.55, 0.95), (0.75, 0.98), (0.9, 0.82), (1.0, 0.45))]
        else:
            prof = [(tr * f, hem + (top_z - hem) * u) for u, f in
                    ((0.0, 0.98), (0.3, 0.93), (0.6, 0.97), (0.85, 0.88), (1.0, 0.45))]
        belly = animal.get("belly") if style == "fur" else None
        if belly:
            mid = hem + (top_z - hem) * 0.4
            top = self.mat("top", outfit.get("top", "#d8473d"), soft=0.15,
                           patch=(belly, (0, -tr * 0.95, mid), (tr * 0.62, tr * 0.55, (top_z - hem) * 0.36)))
        torso = geo.lathe(f"{self.id}.torso", prof, 72, (1.0, 0.86), top, parent=self.body,
                          collection=self.collection)
        self.parts["torso"] = self.ink(torso)
        if style == "padded":
            # Frog buttons down the front of a padded jacket, and a soft collar.
            for k in range(3):
                z = hem + (top_z - hem) * (0.35 + 0.18 * k)
                geo.ellipsoid(f"{self.id}.button", (r * 0.06, r * 0.03, r * 0.035), (r * 0.05, -tr * 0.9, z),
                              trim, parent=self.body, collection=self.collection, rings=8, segments=12)
            collar = [Vector((tr * 0.52 * math.cos(a), tr * 0.47 * math.sin(a), top_z - r * 0.06))
                      for a in np.linspace(0, 2 * math.pi, 29)]
            self.ink(geo.tube(f"{self.id}.collar", collar, r * 0.07, trim, segments=8, parent=self.body,
                              collection=self.collection), 0.6)
        if outfit.get("bottom_style") == "skirt":
            skirt = self.mat("skirt", outfit.get("bottom", "#3b3b4f"))
            prof = [(tr * 1.5, -r * 0.75), (tr * 1.2, -r * 0.45), (tr * 0.95, -r * 0.1), (tr * 0.9, r * 0.1)]
            self.ink(geo.lathe(f"{self.id}.skirt", prof, 40, (1.0, 0.9), skirt, parent=self.body,
                               collection=self.collection))
        self._head(r, shape=(1.0, 0.95, 0.93), chin=0.12 if not animal else 0.04)
        hair = s.get("hair", {})
        self._hair(hair.get("style", "none"), hair.get("color", "#2c1d24"), r)
        if animal:
            self._animal(animal)
        self._accessories()
        # Limbs: noodle tubes re-solved every frame.
        skin = self.mat("skin", s["skin"], soft=0.1, shadow=SKIN_SHADOW if not animal else None)
        sleeve = top if style != "fur" else self.mat("fur", animal.get("fur", s["skin"]))
        legs = self.mat("legs", outfit.get("bottom", "#39334a")) if outfit.get("bottom_style") in (
            "pants",) else skin if style != "fur" else self.mat("fur", animal.get("fur", s["skin"]))
        shoe_color = outfit.get("shoes", "#3d2b2b")
        shoes = self.mat("shoes", shoe_color)
        hand_mat = skin if style != "fur" else self.mat("paw", _shade(animal.get("fur", s["skin"]), -0.15))
        rows = 10
        for side, label in ((1, "l"), (-1, "r")):
            arm = geo.tube(f"{self.id}.arm_{label}", [(0, 0, -0.01 * i) for i in range(rows)], r * 0.1, sleeve,
                           segments=10, parent=self.root, collection=self.collection)
            self.ink(arm, 0.8)
            hand = geo.ellipsoid(f"{self.id}.hand_{label}", (m["hand_r"], m["hand_r"] * 0.9, m["hand_r"]),
                                 material=hand_mat, parent=self.root, collection=self.collection, rings=12,
                                 segments=16)
            self.ink(hand, 0.8)
            leg = geo.tube(f"{self.id}.leg_{label}", [(0, 0, -0.01 * i) for i in range(rows)], r * 0.12, legs,
                           segments=10, parent=self.root, collection=self.collection)
            if outfit.get("bottom_style") == "shorts":
                leg.data.materials[0] = self.mat("shorts", outfit.get("bottom", "#e2b45c"))
                leg.data.materials.append(skin)
                geo.paint_rows(leg, lambda row: 0 if row < 4 else 1)
            self.ink(leg, 0.8)
            fl, fh = m["foot"]
            foot = geo.ellipsoid(f"{self.id}.foot_{label}", (fl * 0.55, fl, fh), material=shoes, parent=self.root,
                                 collection=self.collection, rings=12, segments=18, squash_bottom=0.6)
            for v in foot.data.vertices:
                v.co.y -= fl * 0.35
                v.co.z += fh * 0.42
            self.ink(foot, 0.8)
            self.limbs[label] = {"arm": arm, "hand": hand, "leg": leg, "foot": foot, "side": side}

    def _animal(self, animal):
        r = self.m["head_r"]
        head = self.parts["head"]
        fur = animal.get("fur", self.spec["skin"])
        furm = self.mat("fur", fur, rim=0.4)
        inner = self.mat("inner ear", animal.get("inner", "#f2a7a0"))
        kind = animal.get("ears")
        for side in (-1, 1):
            if not kind:
                break
            pivot = geo.empty(f"{self.id}.ear_pivot", parent=head, collection=self.collection)
            if kind in ("cat", "fox"):
                big = 1.0 if kind == "cat" else 1.3
                base = _sphere_point(r * 0.86, side * 38, 50)
                pivot.location = base
                pivot.rotation_euler = (math.radians(-10), math.radians(side * 22), 0)
                ear = geo.cone(f"{self.id}.ear", r * 0.3 * big, 0.0, r * 0.52 * big, material=furm, parent=pivot,
                               collection=self.collection, segments=16)
                ear.scale = (1.0, 0.55, 1.0)
                geo.cone(f"{self.id}.ear_in", r * 0.18 * big, 0.0, r * 0.36 * big, (0, -r * 0.07, r * 0.04),
                         inner, parent=pivot, collection=self.collection, segments=12).scale = (1.0, 0.4, 1.0)
            elif kind == "rabbit":
                base = _sphere_point(r * 0.86, side * 18, 70)
                pivot.location = base
                pivot.rotation_euler = (math.radians(-6), math.radians(side * 10), 0)
                ear = geo.ellipsoid(f"{self.id}.ear", (r * 0.16, r * 0.08, r * 0.62), (0, 0, r * 0.55), furm,
                                    parent=pivot, collection=self.collection)
                geo.ellipsoid(f"{self.id}.ear_in", (r * 0.09, r * 0.04, r * 0.45), (0, -r * 0.05, r * 0.55),
                              inner, parent=pivot, collection=self.collection)
            else:  # nian: wide, soft, sound-sensitive ears
                base = _sphere_point(r * 0.9, side * 82, 30)
                pivot.location = base
                pivot.rotation_euler = (0, math.radians(side * -25), 0)
                ear = geo.ellipsoid(f"{self.id}.ear", (r * 0.42, r * 0.12, r * 0.24), (side * r * 0.36, 0, 0),
                                    furm, parent=pivot, collection=self.collection)
                geo.ellipsoid(f"{self.id}.ear_in", (r * 0.28, r * 0.06, r * 0.14), (side * r * 0.38, -r * 0.06, 0),
                              inner, parent=pivot, collection=self.collection)
            self.ink(ear)
            pivot["rest"] = tuple(pivot.rotation_euler)
            self.ears[side] = pivot
        if animal.get("horns"):
            horn = self.mat("horn", animal.get("horn", "#f1d9a0"), rim=0.5)
            size = 1.0 if animal["horns"] == "nian" else 0.5
            for side in (-1, 1):
                base = _sphere_point(r * 0.9, side * 24, 58)
                tip = base + Vector((side * r * 0.12, r * 0.05, r * 0.42)) * size
                mid = (base + tip) / 2 + Vector((side * r * 0.08, -r * 0.03, 0)) * size
                self.ink(geo.tube(f"{self.id}.horn", geo.bezier(base, mid, tip, 8),
                                  geo.taper(8, r * 0.11 * size, r * 0.015, power=1.2), horn, segments=10,
                                  parent=head, collection=self.collection), 0.7)
        if animal.get("mane"):
            mane = self.mat("mane", animal["mane"], rim=0.4)
            tufts = []
            for i in range(16):
                az = -150 + 300 * i / 15
                if abs(az) < 40:
                    continue
                el = 15 + 30 * math.cos(math.radians(az) * 0.5)
                root = _sphere_point(r * 0.9, az, el - 10)
                out = (root - Vector((0, 0, 0))).normalized()
                tip = root + out * r * 0.38 + Vector((0, 0, -r * 0.12))
                mid = (root + tip) / 2 + Vector((0, 0, r * 0.05))
                tufts.append((geo.tube_vertices(geo.bezier(root, mid, tip, 6), geo.taper(6, r * 0.2, r * 0.02,
                                                                                          bulge=r * 0.06), 8, 0.6,
                                                twist_up=tuple(out)), geo.tube_faces(6, 8)))
            self.ink(geo.merge(f"{self.id}.mane", tufts, mane, collection=self.collection, parent=head), 0.8)
        if animal.get("snout") == "fox":
            snout = geo.cone(f"{self.id}.snout", r * 0.3, r * 0.06, r * 0.45, (0, 0, 0), furm, parent=head,
                             collection=self.collection, segments=16)
            snout.location = (0, -r * 0.82, -r * 0.28)
            snout.rotation_euler = (math.radians(95), 0, 0)
            self.ink(snout)
            geo.ellipsoid(f"{self.id}.nose", (r * 0.07, r * 0.06, r * 0.05), (0, -r * 1.27, -r * 0.27),
                          self.mat("nose", "#2a1a1a"), parent=head, collection=self.collection)
        tail = animal.get("tail")
        if tail:
            if tail == "puff":
                self.tail = geo.ellipsoid(f"{self.id}.tail", (r * 0.22,) * 3, (0, self.m["torso_r"] * 0.95, -r * 0.2),
                                          self.mat("tail", animal.get("belly", "#ffffff")), parent=self.body,
                                          collection=self.collection)
                self.ink(self.tail)
            else:
                size = {"cat": 0.11, "fox": 0.26, "nian": 0.3}[tail] * r
                length = {"cat": 1.5, "fox": 1.6, "nian": 1.2}[tail] * (self.m["hip"] + r * 0.3)
                mats = [self.mat("fur", fur)]
                if tail in ("fox", "nian"):
                    mats.append(self.mat("tail tip", animal.get("tip", animal.get("belly", "#ffffff"))))
                self.tail = geo.tube(f"{self.id}.tail", [(0, 0, -0.01 * i) for i in range(12)], size, mats,
                                     segments=12, parent=self.body, collection=self.collection)
                self.tail["size"] = size
                self.tail["length"] = length
                self.tail["kind"] = tail
                if len(mats) > 1:
                    geo.paint_rows(self.tail, lambda row: 1 if row >= 9 else 0)
                self.ink(self.tail, 0.8)

    # ------------------------------------------------------------------ penguin
    def _build_penguin(self):
        s, m = self.spec, self.m
        b = s.get("body", {})
        r = m["head_r"]
        back = self.mat("back", b.get("back", s["skin"]), rim=0.5)
        bw = m["torso_r"]
        top_z = m["neck"] - m["hip"] + r * 0.4
        prof = [(bw * f, -m["hip"] * 0.55 + (top_z + m["hip"] * 0.55) * u) for u, f in
                ((0.0, 0.35), (0.06, 0.8), (0.2, 1.0), (0.42, 1.02), (0.65, 0.88), (0.85, 0.62), (1.0, 0.3))]
        span = top_z + m["hip"] * 0.55
        coat = self.mat("coat", b.get("back", s["skin"]), rim=0.5,
                        patch=(b.get("belly", "#fbfbf7"), (0, -bw * 0.95, -m["hip"] * 0.55 + span * 0.38),
                               (bw * 0.82, bw * 0.62, span * 0.42)))
        body = geo.lathe(f"{self.id}.torso", prof, 72, (1.0, 0.9), coat, parent=self.body,
                         collection=self.collection)
        self.parts["torso"] = self.ink(body)
        head = self._head(r, shape=(1.0, 0.96, 0.96), chin=0.0)
        beak_mat = self.mat("beak", b.get("beak", "#f29a2e"), rim=0.4)
        pivot = geo.empty(f"{self.id}.beak", (0, -r * 0.9, -r * 0.18), head, self.collection)
        upper = geo.cone(f"{self.id}.beak_top", r * 0.2, 0.0, r * 0.36, (0, 0, 0), beak_mat, parent=pivot,
                         collection=self.collection, segments=16)
        upper.rotation_euler = (math.radians(100), 0, 0)
        upper.scale = (1.0, 0.55, 1.0)
        lower_pivot = geo.empty(f"{self.id}.jaw", (0, 0, -r * 0.02), pivot, self.collection)
        lower = geo.cone(f"{self.id}.beak_low", r * 0.16, 0.0, r * 0.28, (0, 0, 0), beak_mat, parent=lower_pivot,
                         collection=self.collection, segments=16)
        lower.rotation_euler = (math.radians(98), 0, 0)
        lower.scale = (1.0, 0.45, 1.0)
        self.ink(upper, 0.6)
        self.ink(lower, 0.6)
        self.beak = lower_pivot
        for i in range(int(b.get("tuft", 0))):
            az = (i - (b["tuft"] - 1) / 2) * 16
            base = _sphere_point(r * 0.95, az, 75)
            tip = base + Vector((az * 0.004 * r, r * 0.08, r * 0.28))
            self.ink(geo.tube(f"{self.id}.tuft", geo.bezier(base, (base + tip) / 2 + Vector((0, -r * 0.05, 0)), tip, 6),
                              geo.taper(6, r * 0.06, r * 0.01), back, segments=6, parent=head,
                              collection=self.collection), 0.5)
        self._accessories()
        feet = self.mat("feet", b.get("feet", "#f29a2e"))
        for side, label in ((1, "l"), (-1, "r")):
            pivot = geo.empty(f"{self.id}.flipper_{label}", (side * bw * 0.92, 0, m["shoulder"][1] - m["chest"]),
                              self.chest, self.collection)
            length = m["arm"]
            pts = [(side * length * u, 0.0, -length * 0.15 * u * u) for u in np.linspace(0, 1, 8)]
            flip = geo.tube(f"{self.id}.flipper", pts, geo.taper(8, r * 0.2, r * 0.05, bulge=r * 0.05), back,
                            segments=10, flatten=0.28, twist_up=(0, 1, 0), parent=pivot, collection=self.collection)
            self.ink(flip, 0.7)
            self.wings[side] = pivot
            fl, fh = m["foot"]
            foot = geo.ellipsoid(f"{self.id}.foot_{label}", (fl * 0.6, fl, fh), material=feet, parent=self.root,
                                 collection=self.collection, rings=10, segments=16, squash_bottom=0.5)
            for v in foot.data.vertices:
                v.co.y -= fl * 0.45
                v.co.z += fh * 0.5
            self.ink(foot, 0.6)
            self.limbs[label] = {"foot": foot, "side": side}

    # ------------------------------------------------------------------ bird
    def _build_bird(self):
        """A plump cartoon gull: teardrop body, big round head, folded wings that open into a wide span."""
        s, m = self.spec, self.m
        b = s.get("body", {})
        r, h = m["head_r"], m["height"]
        white = self.mat("body", s["skin"], soft=0.2)
        grey = self.mat("wing", b.get("back", "#9aa6b6"), rim=0.4,
                        patch=(b.get("wingtip", "#3a3f4a"), (h * 0.5, 0, 0), (h * 0.28, h * 0.5, h * 0.2)))
        length = h * 0.62
        body_r = h * 0.2
        prof = [(body_r * f, length * (u - 0.45)) for u, f in
                ((0.0, 0.08), (0.12, 0.42), (0.35, 0.82), (0.6, 1.0), (0.82, 0.88), (0.95, 0.55), (1.0, 0.2))]
        body = geo.lathe(f"{self.id}.torso", prof, 32, (1.0, 0.92), white, parent=self.body,
                         collection=self.collection)
        co = np.empty(len(body.data.vertices) * 3, np.float32)
        body.data.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        x, y, z = co[:, 0].copy(), co[:, 1].copy(), co[:, 2].copy()
        # Lay the lathe axis along -Y (the front), tilt the chest up and lift the tail a little.
        co[:, 0], co[:, 1], co[:, 2] = x, -z, y * 0.95 + 0.18 * z + 0.25 * np.maximum(-z, 0) ** 2 / length
        body.data.vertices.foreach_set("co", co.ravel())
        body.data.update()
        body.location = (0, h * 0.02, m["chest"] - m["hip"])
        self.parts["torso"] = self.ink(body)
        tail = geo.ellipsoid(f"{self.id}.tailfan", (h * 0.09, h * 0.14, h * 0.02), (0, 0, 0), grey,
                             parent=self.body, collection=self.collection, rings=8, segments=14)
        tail.location = (0, length * 0.62, m["chest"] - m["hip"] + h * 0.05)
        tail.rotation_euler = (math.radians(-12), 0, 0)
        self.ink(tail, 0.6)
        self.neck.location = (0, -length * 0.36, m["neck"] - m["chest"])
        head = self._head(r, shape=(0.96, 0.98, 0.96), chin=0.0)
        beak_mat = self.mat("beak", b.get("beak", "#f2c230"), rim=0.3)
        pivot = geo.empty(f"{self.id}.beak", (0, -r * 0.82, -r * 0.22), head, self.collection)
        upper = geo.cone(f"{self.id}.beak_top", r * 0.24, r * 0.05, r * 0.95, (0, 0, 0), beak_mat, parent=pivot,
                         collection=self.collection, segments=14)
        upper.rotation_euler = (math.radians(98), 0, 0)
        upper.scale = (0.78, 0.55, 1.0)
        jaw = geo.empty(f"{self.id}.jaw", (0, 0, -r * 0.06), pivot, self.collection)
        lower = geo.cone(f"{self.id}.beak_low", r * 0.17, r * 0.03, r * 0.78, (0, 0, 0), beak_mat, parent=jaw,
                         collection=self.collection, segments=12)
        lower.rotation_euler = (math.radians(94), 0, 0)
        lower.scale = (0.72, 0.42, 1.0)
        geo.ellipsoid(f"{self.id}.beakspot", (r * 0.06, r * 0.05, r * 0.05), (0, -r * 0.62, -r * 0.08),
                      self.mat("beak spot", "#e0473a"), parent=jaw, collection=self.collection)
        self.ink(upper, 0.5)
        self.ink(lower, 0.5)
        self.beak = jaw
        self._accessories()
        span = m["arm"] * 0.5
        chord = h * 0.5
        for side, label in ((1, "l"), (-1, "r")):
            shoulder = geo.empty(f"{self.id}.wing_{label}", (side * body_r * 0.75, -length * 0.12,
                                                            m["chest"] - m["hip"] + body_r * 0.45),
                                 self.body, self.collection)
            inner = geo.ellipsoid(f"{self.id}.wing_in", (span * 0.56, chord * 0.42, h * 0.028),
                                  (side * span * 0.48, chord * 0.14, 0), grey, parent=shoulder,
                                  collection=self.collection, rings=10, segments=24)
            elbow = geo.empty(f"{self.id}.wing_elbow", (side * span * 0.92, chord * 0.04, 0), shoulder,
                              self.collection)
            outer = geo.ellipsoid(f"{self.id}.wing_out", (span * 0.64, chord * 0.34, h * 0.02),
                                  (side * span * 0.56, chord * 0.2, 0), grey, parent=elbow,
                                  collection=self.collection, rings=10, segments=24)
            # Sweep the outer feathers back and taper them to a point, like a gull's hand.
            for v in outer.data.vertices:
                u = min(1.0, abs(v.co.x) / (span * 1.2))
                v.co.y = (v.co.y - chord * 0.2) * (1 - 0.55 * u) + chord * 0.2 + u * u * chord * 0.5
            self.ink(inner, 0.5)
            self.ink(outer, 0.5)
            self.wings[side] = (shoulder, elbow)
            legs = self.mat("legs", b.get("feet", "#f0b040"))
            leg = geo.tube(f"{self.id}.leg_{label}", [(0, 0, -0.01 * i) for i in range(6)], h * 0.016, legs,
                           segments=6, parent=self.root, collection=self.collection)
            fl, fh = m["foot"]
            foot = geo.ellipsoid(f"{self.id}.foot_{label}", (fl * 0.7, fl * 0.8, fh), material=legs, parent=self.root,
                                 collection=self.collection, rings=8, segments=12, squash_bottom=0.6)
            for v in foot.data.vertices:
                v.co.y -= fl * 0.3
            self.limbs[label] = {"leg": leg, "foot": foot, "side": side}

    # ------------------------------------------------------------------ attachments
    def anchor(self, name):
        """World matrix of an attachment point: hands, flipper/wing tips, head, chest or back."""
        if name in ("l", "r", "hand_l", "hand_r"):
            label = name[-1]
            parts = self.limbs.get(label, {})
            if "hand" in parts:
                return parts["hand"].matrix_world.copy()
            side = 1 if label == "l" else -1
            wing = self.wings.get(side)
            if wing is not None:
                pivot = wing[0] if isinstance(wing, tuple) else wing
                return pivot.matrix_world @ Matrix.Translation((side * self.m["arm"] * 0.9, 0, 0))
        if name in ("foot", "feet"):
            feet = [parts["foot"] for parts in self.limbs.values() if "foot" in parts]
            if feet:
                m = feet[0].matrix_world.copy()
                m.translation = sum((f.matrix_world.translation for f in feet), feet[0].matrix_world.translation * 0) / len(feet)
                return m
        if name == "beak" and self.beak is not None:
            return self.beak.matrix_world.copy()
        if name == "head":
            return self.parts["head"].matrix_world.copy()
        if name == "back":
            return self.chest.matrix_world @ Matrix.Translation((0, self.m["torso_r"] * 0.9, 0))
        return self.chest.matrix_world.copy()

    def wearables(self):
        """Accessory objects by kind, so a scarf or earmuffs can be put on mid-film."""
        out = {}
        for obj in self.root.children_recursive:
            for kind in ("scarf", "muff", "glasses", "bow", "ribbon"):
                if f".{kind}" in obj.name:
                    out.setdefault("earmuffs" if kind == "muff" else kind, []).append(obj)
        return out

    # ------------------------------------------------------------------ posing
    def body_matrix(self, pose):
        m = self.m
        b = pose.get("body", {})
        sq = b.get("squash", 1.0)
        mat = (Matrix.Translation((b.get("x", 0.0), b.get("y", 0.0), m["hip"] + b.get("z", 0.0)))
               @ Euler((b.get("pitch", 0.0) + m.get("hunch", 0.0) * 0.6, b.get("roll", 0.0), b.get("yaw", 0.0)),
                       "ZXY").to_matrix().to_4x4()
               @ Matrix.Diagonal((1 / math.sqrt(sq), 1 / math.sqrt(sq), sq, 1.0)))
        return mat

    def apply(self, pose):
        m = self.m
        visible = pose.get("visible", True)
        self.root.hide_render = not visible
        for child in self.root.children_recursive:
            child.hide_render = not visible
        if not visible:
            return
        wear = pose.get("wear")
        if wear:
            if not hasattr(self, "_wearables"):
                self._wearables = self.wearables()
            for kind, on in wear.items():
                for obj in self._wearables.get(kind, ()):
                    obj.hide_render = not on
        x, y, z = pose["pos"]
        self.root.location = (x, y, z)
        self.root.rotation_euler = (0, 0, pose.get("facing", 0.0))
        s = pose.get("scale", 1.0)
        self.root.scale = (s, s, s)
        b = pose.get("body", {})
        sq = b.get("squash", 1.0)
        self.body.location = (b.get("x", 0.0), b.get("y", 0.0), m["hip"] + b.get("z", 0.0))
        self.body.rotation_mode = "ZXY"
        self.body.rotation_euler = (b.get("pitch", 0.0) + m.get("hunch", 0.0) * 0.6, b.get("roll", 0.0),
                                    b.get("yaw", 0.0))
        self.body.scale = (1 / math.sqrt(sq), 1 / math.sqrt(sq), sq)
        c = pose.get("chest", {})
        self.chest.rotation_mode = "ZXY"
        self.chest.rotation_euler = (c.get("pitch", 0.0) + m.get("hunch", 0.0) * 0.4, c.get("roll", 0.0),
                                     c.get("yaw", 0.0))
        hd = pose.get("head", {})
        self.neck.rotation_mode = "ZXY"
        self.neck.rotation_euler = (hd.get("pitch", 0.0) - m.get("hunch", 0.0) * 0.8, hd.get("roll", 0.0),
                                    hd.get("yaw", 0.0))
        face = pose.get("face", {})
        self.set_face(face.get("eyes"), face.get("brows"), face.get("mouth"), face.get("gaze", (0.0, 0.0)),
                      face.get("blush"))
        if self.beak is not None:
            self.beak.rotation_euler = (math.radians(-28) * face.get("open", 0.0), 0, 0)
        for side, pivot in self.ears.items():
            rest = pivot["rest"]
            ear = pose.get("ears", {}).get("l" if side > 0 else "r", 0.0)
            droop = pose.get("ears", {}).get("droop", 0.0)
            pivot.rotation_euler = (rest[0] + droop * 0.4, rest[1] + side * (ear - droop * 0.5), rest[2])
        if self.tail is not None and "length" in self.tail.keys():
            self._pose_tail(pose.get("tail", {}))
        tails = self.parts.get("scarf_tails")
        if tails:
            wind = pose.get("wind", (0.0, 0.0))
            for k, obj in enumerate(tails):
                base = Vector(obj["base"])
                length, splay = obj["length"], obj["splay"]
                sway = wind[0] * (1 + 0.3 * k)
                lift = wind[1]
                drape = obj["drape"]
                mid = base + Vector(((splay * 0.3 + sway * 0.3) * length,
                                     -0.12 * length - drape * 0.9 - lift * 0.3 * length, -0.5 * length))
                end = base + Vector(((splay + sway * 0.8) * length,
                                     -0.18 * length - drape * 1.15 - lift * 0.8 * length,
                                     -length * (1 - 0.6 * abs(lift))))
                geo.update_tube(obj, geo.bezier(base, mid, end, 3), [obj["width"], obj["width"], obj["width"] * 1.1],
                                twist_up=(0, -1, 0))
        if self.spec["plan"] == "biped":
            self._pose_biped_limbs(pose)
        elif self.spec["plan"] == "penguin":
            self._pose_penguin(pose)
        else:
            self._pose_bird(pose)

    def _local_chest(self, pose):
        m = self.m
        c = pose.get("chest", {})
        return (self.body_matrix(pose) @ Matrix.Translation((0, 0, m["chest"] - m["hip"]))
                @ Euler((c.get("pitch", 0.0) + m.get("hunch", 0.0) * 0.4, c.get("roll", 0.0), c.get("yaw", 0.0)),
                        "ZXY").to_matrix().to_4x4())

    def _to_local(self, world):
        """World coordinates -> this character's root space."""
        x, y, z = world
        facing = self.root.rotation_euler.z
        dx, dy, dz = x - self.root.location.x, y - self.root.location.y, z - self.root.location.z
        cs, sn = math.cos(-facing), math.sin(-facing)
        s = self.root.scale.x or 1.0
        return Vector(((dx * cs - dy * sn) / s, (dx * sn + dy * cs) / s, dz / s))

    def _pose_biped_limbs(self, pose):
        m = self.m
        r = m["head_r"]
        chest = self._local_chest(pose)
        body = self.body_matrix(pose)
        arms = pose.get("arms", {})
        legs = pose.get("legs", {})
        upper = m["arm"] * 0.5
        for label, parts in self.limbs.items():
            side = parts["side"]
            shoulder_local = Vector((side * m["shoulder"][0], 0.0, m["shoulder"][1] - m["chest"]))
            shoulder = chest @ shoulder_local
            spec = arms.get(label, {})
            if spec.get("world") is not None:
                target = self._to_local(spec["world"])
            else:
                offset = Vector(spec.get("hand", rest_hand(m, side)))
                target = chest @ (shoulder_local + offset)
            pole = chest.to_3x3() @ Vector(spec.get("pole", (side * 0.3, 0.6, -0.2)))
            elbow, wrist = solve_two_bone(shoulder, target, upper, upper, shoulder + pole)
            pts = geo.bezier(shoulder, elbow, wrist, 10)
            lr = m.get("limb_r", r * 0.12)
            radii = geo.taper(10, lr * 1.05, lr * 0.85, bulge=lr * 0.08)
            geo.update_tube(parts["arm"], pts, radii)
            hand = parts["hand"]
            hand.location = wrist + (wrist - elbow).normalized() * m["hand_r"] * 0.55
            hand.rotation_euler = (0, 0, 0)
            leg = legs.get(label, {})
            hip = body @ Vector((side * m["hip_x"], 0.0, -r * 0.12))
            foot = Vector(leg.get("foot", (side * m["hip_x"], 0.0, 0.0)))
            ankle = foot + Vector((0, 0, m["foot"][1] * 0.9))
            lpole = Vector(leg.get("pole", (side * 0.15, -1.0, 0.0)))
            seg = (m["leg"] + r * 0.02) * 0.5
            knee, ankle = solve_two_bone(hip, ankle, seg, seg, hip + lpole)
            geo.update_tube(parts["leg"], geo.bezier(hip, knee, ankle, 10), geo.taper(10, lr * 1.3, lr * 0.95))
            parts["foot"].location = foot
            parts["foot"].rotation_euler = (leg.get("pitch", 0.0), 0, leg.get("yaw", 0.0))

    def _pose_penguin(self, pose):
        wings = pose.get("wings", {})
        for side, pivot in self.wings.items():
            label = "l" if side > 0 else "r"
            w = wings.get(label, {})
            flap = w.get("flap", 0.0)
            spread = w.get("spread", 0.2)
            pivot.rotation_euler = (w.get("sweep", 0.0), side * (1.25 - spread * 1.2 - flap),
                                    side * w.get("twist", 0.0))
        legs = pose.get("legs", {})
        for label, parts in self.limbs.items():
            leg = legs.get(label, {})
            side = parts["side"]
            parts["foot"].location = Vector(leg.get("foot", (side * self.m["hip_x"], 0.0, 0.0)))
            parts["foot"].rotation_euler = (leg.get("pitch", 0.0), 0, leg.get("yaw", 0.0) + side * 0.25)

    def _pose_bird(self, pose):
        wings = pose.get("wings", {})
        for side, (shoulder, elbow) in self.wings.items():
            label = "l" if side > 0 else "r"
            w = wings.get(label, {})
            flap = w.get("flap", 0.0)
            fold = w.get("fold", 0.0)
            # Folded: wings lie back along the body; open: they spread and beat around the shoulder.
            # Open wings beat around the shoulder; folded wings point back along the flank, flat side out,
            # trailing edge down. Blend the two orientations so a wing can fold or open smoothly.
            opened = Euler((0, -side * (flap - 0.35) * 0.95, 0)).to_quaternion()
            c, sn = math.cos(0.1), math.sin(0.1)
            span_dir = Vector((0, c, -sn)) * side
            chord_dir = Vector((0, -sn, -c))
            folded = Matrix((span_dir, chord_dir, span_dir.cross(chord_dir))).transposed().to_quaternion()
            shoulder.rotation_mode = "QUATERNION"
            shoulder.rotation_quaternion = opened.slerp(folded, max(0.0, min(1.0, fold)))
            # A folded wing tucks its hand over its arm: draw it shorter, so the tips end just past the tail.
            shoulder.scale = (1 - 0.5 * fold, 1 - 0.2 * fold, 1)
            elbow.rotation_euler = (0, -side * (flap - 0.35) * 0.45 * (1 - fold), side * fold * 0.1)
        m = self.m
        legs = pose.get("legs", {})
        body = self.body_matrix(pose)
        for label, parts in self.limbs.items():
            side = parts["side"]
            leg = legs.get(label, {})
            foot = Vector(leg.get("foot", (side * m["hip_x"], 0.0, 0.0)))
            hip = body @ Vector((side * m["hip_x"], 0.0, 0.0))
            tucked = leg.get("tuck", 0.0)
            if tucked:
                foot = hip + Vector((0, 0.08, -0.05))
            knee = (hip + foot) / 2 + Vector((0, 0.03, 0))
            geo.update_tube(parts["leg"], geo.bezier(hip, knee, foot + Vector((0, 0, m["foot"][1])), 6),
                            m["height"] * 0.018)
            parts["foot"].location = foot
            parts["foot"].rotation_euler = (leg.get("pitch", 0.0), 0, 0)

    def _pose_tail(self, tail):
        obj = self.tail
        length, size = obj["length"], obj["size"]
        wag, lift = tail.get("wag", 0.0), tail.get("lift", 0.0)
        base = Vector((0, self.m["torso_r"] * 0.85, -self.m["head_r"] * 0.15))
        kind = obj["kind"]
        pts = []
        for i in range(12):
            u = i / 11
            curl = (0.9 if kind == "cat" else 0.45) * u * u
            pts.append(base + Vector((math.sin(wag * u * 1.6) * length * u * 0.5,
                                      length * u * (0.75 - 0.25 * lift),
                                      length * (curl * (0.6 + lift) - 0.08 * u))))
        bulge = size * (0.6 if kind != "cat" else 0.05)
        radii = geo.taper(12, size * 0.55, size * 0.15 if kind != "cat" else size * 0.8, bulge=bulge, power=1.5)
        geo.update_tube(obj, pts, radii)
