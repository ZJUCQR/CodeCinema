"""Mesh primitives for cartoon characters, props and sets, built directly from vertex data.

Everything is generated with numpy and ``from_pydata`` so scenes build quickly in
background mode, and tube meshes can be re-posed every frame by rewriting their
vertices.
"""
import math

import bpy
import numpy as np


def _link(obj, collection=None, parent=None):
    (collection or bpy.context.scene.collection).objects.link(obj)
    if parent is not None:
        obj.parent = parent
    return obj


def mesh_object(name, verts, faces, material=None, smooth=True, collection=None, parent=None):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([tuple(v) for v in np.asarray(verts, dtype=float)], [], [tuple(f) for f in faces])
    mesh.validate(clean_customdata=False)
    mesh.update()
    if smooth:
        mesh.shade_smooth()
    obj = bpy.data.objects.new(name, mesh)
    if material is not None:
        if isinstance(material, (list, tuple)):
            for m in material:
                mesh.materials.append(m)
        else:
            mesh.materials.append(material)
    return _link(obj, collection, parent)


def empty(name, location=(0, 0, 0), parent=None, collection=None):
    obj = bpy.data.objects.new(name, None)
    obj.location = location
    obj.empty_display_size = 0.1
    return _link(obj, collection, parent)


def grid_faces(rows, cols, wrap=True, offset=0):
    """Quads for a rows x cols vertex grid; columns wrap around for surfaces of revolution."""
    faces = []
    span = cols if wrap else cols - 1
    for i in range(rows - 1):
        for j in range(span):
            a = offset + i * cols + j
            b = offset + i * cols + (j + 1) % cols
            faces.append((a, b, b + cols, a + cols))
    return faces


def lathe(name, profile, segments=40, scale=(1.0, 1.0), material=None, parent=None, collection=None,
          center=(0, 0, 0)):
    """Surface of revolution around Z from (radius, z) pairs ordered bottom to top; ends close at the axis.

    Sparse profiles are resampled through a Catmull-Rom spline so silhouettes stay round in close-ups."""
    profile = list(profile)
    if 2 < len(profile) < 24:
        pts = [profile[0]] + profile + [profile[-1]]
        dense = []
        for i in range(1, len(pts) - 2):
            p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
            for k in range(4):
                t = k / 4
                dense.append(tuple(0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j])
                                          * t * t + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t ** 3) for j in (0, 1)))
        dense.append(profile[-1])
        profile = [(max(0.0, r), z) for r, z in dense]
    angles = np.linspace(0, 2 * math.pi, segments, endpoint=False)
    verts = []
    for r, z in profile:
        for a in angles:
            verts.append((center[0] + r * math.cos(a) * scale[0], center[1] + r * math.sin(a) * scale[1],
                          center[2] + z))
    faces = grid_faces(len(profile), segments)
    bottom = len(verts)
    verts.append((center[0], center[1], center[2] + profile[0][1]))
    top = len(verts)
    verts.append((center[0], center[1], center[2] + profile[-1][1]))
    last = (len(profile) - 1) * segments
    for j in range(segments):
        faces.append((bottom, (j + 1) % segments, j))
        faces.append((top, last + j, last + (j + 1) % segments))
    return mesh_object(name, verts, faces, material, parent=parent, collection=collection)


def ellipsoid(name, radii, location=(0, 0, 0), material=None, parent=None, rings=24, segments=40,
              collection=None, squash_bottom=0.0):
    """A UV ellipsoid; squash_bottom flattens the lower half (for feet, buns and toon clouds)."""
    rx, ry, rz = radii
    profile = []
    for i in range(rings + 1):
        v = -math.pi / 2 + math.pi * i / rings
        r, z = math.cos(v), math.sin(v)
        if z < 0:
            z *= 1 - squash_bottom
        profile.append((r, z))
    angles = np.linspace(0, 2 * math.pi, segments, endpoint=False)
    verts = []
    for r, z in profile[1:-1]:
        for a in angles:
            verts.append((location[0] + rx * r * math.cos(a), location[1] + ry * r * math.sin(a),
                          location[2] + rz * z))
    faces = grid_faces(rings - 1, segments)
    south, north = len(verts), len(verts) + 1
    verts.append((location[0], location[1], location[2] - rz * (1 - squash_bottom)))
    verts.append((location[0], location[1], location[2] + rz))
    last = (rings - 2) * segments
    for j in range(segments):
        faces.append((south, (j + 1) % segments, j))
        faces.append((north, last + j, last + (j + 1) % segments))
    return mesh_object(name, verts, faces, material, parent=parent, collection=collection)


def cone(name, r1, r2, depth, location=(0, 0, 0), material=None, parent=None, segments=24, collection=None,
         rounded=0.0):
    profile = [(0.0, 0.0), (r1 * (1 - rounded), 0.0)]
    if rounded:
        profile.append((r1, rounded * depth * 0.3))
    profile += [(r2, depth)]
    if r2 > 0:
        profile.append((0.0, depth))
    return lathe(name, profile[1:-1] if r2 > 0 else profile[1:], segments, material=material, parent=parent,
                 collection=collection, center=location)


def rounded_box(name, size, radius, location=(0, 0, 0), material=None, parent=None, collection=None,
                bevel_segments=3):
    """A box with bevelled edges (a modifier, so the silhouette stays soft at any distance)."""
    sx, sy, sz = (s / 2 for s in size)
    verts = [(x * sx, y * sy, z * sz) for z in (-1, 1) for y in (-1, 1) for x in (-1, 1)]
    verts = [(v[0] + location[0], v[1] + location[1], v[2] + location[2]) for v in verts]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    obj = mesh_object(name, verts, faces, material, smooth=False, parent=parent, collection=collection)
    if radius > 0:
        mod = obj.modifiers.new("Soft edges", "BEVEL")
        mod.width = radius
        mod.segments = bevel_segments
        mod.limit_method = "NONE"
        obj.modifiers.new("Normals", "WEIGHTED_NORMAL")
        obj.data.shade_smooth()
    return obj


def _frames(points):
    """Parallel-transport frames along a polyline: tangents, normals, binormals."""
    p = np.asarray(points, dtype=float)
    t = np.gradient(p, axis=0)
    t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-9)
    up = np.array([0.0, 0.0, 1.0]) if abs(t[0][2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    n = np.cross(t[0], up)
    n /= max(np.linalg.norm(n), 1e-9)
    normals = [n]
    for i in range(1, len(p)):
        n = normals[-1] - t[i] * np.dot(normals[-1], t[i])
        length = np.linalg.norm(n)
        n = n / length if length > 1e-9 else normals[-1]
        normals.append(n)
    normals = np.array(normals)
    binormals = np.cross(t, normals)
    return t, normals, binormals


def tube_vertices(points, radii, segments=10, flatten=1.0, twist_up=None):
    """Ring vertices around a centerline (rows x segments + 2 cap centers), as a flat float array."""
    p = np.asarray(points, dtype=float)
    radii = np.broadcast_to(np.asarray(radii, dtype=float), (len(p),))
    t, n, b = _frames(p)
    if twist_up is not None:
        # Orient flattened cross-sections (hair locks, flippers) toward a preferred direction.
        up = np.asarray(twist_up, dtype=float)
        for i in range(len(p)):
            u = up - t[i] * np.dot(up, t[i])
            if np.linalg.norm(u) > 1e-6:
                n[i] = u / np.linalg.norm(u)
                b[i] = np.cross(t[i], n[i])
    ang = np.linspace(0, 2 * math.pi, segments, endpoint=False)
    c, s = np.cos(ang), np.sin(ang)
    rings = (p[:, None, :] + radii[:, None, None] * (c[None, :, None] * b[:, None, :] * 1.0
                                                      + s[None, :, None] * n[:, None, :] * flatten))
    verts = np.concatenate([rings.reshape(-1, 3), p[:1], p[-1:]])
    return verts


def tube_faces(rows, segments):
    faces = grid_faces(rows, segments)
    start, end = rows * segments, rows * segments + 1
    last = (rows - 1) * segments
    for j in range(segments):
        faces.append((start, (j + 1) % segments, j))
        faces.append((end, last + j, last + (j + 1) % segments))
    return faces


def tube(name, points, radii, material=None, segments=10, flatten=1.0, twist_up=None, parent=None,
         collection=None):
    verts = tube_vertices(points, radii, segments, flatten, twist_up)
    obj = mesh_object(name, verts, tube_faces(len(points), segments), material, parent=parent, collection=collection)
    obj["tube"] = [len(points), segments, float(flatten)]
    return obj


def paint_rows(obj, material_of_row):
    """Assign materials along a tube: material_of_row(row) for rows 0..n-1 (the caps belong to the end rows)."""
    rows, segments = int(obj["tube"][0]), int(obj["tube"][1])
    grid = (rows - 1) * segments
    for poly in obj.data.polygons:
        if poly.index < grid:
            row = poly.index // segments
        else:
            row = 0 if (poly.index - grid) % 2 == 0 else rows - 1
        poly.material_index = material_of_row(row)


def update_tube(obj, points, radii, twist_up=None):
    segments, flatten = int(obj["tube"][1]), float(obj["tube"][2])
    verts = tube_vertices(points, radii, segments, flatten, twist_up)
    obj.data.vertices.foreach_set("co", verts.astype(np.float32).ravel())
    obj.data.update()


def bezier(a, c, b, count):
    """Points on a quadratic Bezier that passes through `c` at its midpoint."""
    a, c, b = (np.asarray(v, dtype=float) for v in (a, c, b))
    ctrl = 2 * c - (a + b) / 2
    u = np.linspace(0, 1, count)[:, None]
    return (1 - u) ** 2 * a + 2 * (1 - u) * u * ctrl + u ** 2 * b


def taper(count, start, end, bulge=0.0, power=1.0):
    u = np.linspace(0, 1, count)
    return start + (end - start) * u ** power + bulge * np.sin(math.pi * u)


def heightfield(name, size, resolution, height, material=None, collection=None, center=(0, 0)):
    """A ground mesh from a height function h(x, y) (the same function the motion planner uses)."""
    nx, ny = resolution
    xs = np.linspace(center[0] - size[0] / 2, center[0] + size[0] / 2, nx)
    ys = np.linspace(center[1] - size[1] / 2, center[1] + size[1] / 2, ny)
    verts = [(x, y, height(x, y)) for y in ys for x in xs]
    faces = grid_faces(ny, nx, wrap=False)
    return mesh_object(name, verts, faces, material, collection=collection)


def merge(name, parts, material=None, collection=None, parent=None):
    """Join several (verts, faces) parts into one mesh object."""
    verts, faces = [], []
    for v, f in parts:
        base = len(verts)
        verts.extend(map(tuple, np.asarray(v, dtype=float)))
        faces.extend(tuple(i + base for i in face) for face in f)
    return mesh_object(name, verts, faces, material, collection=collection, parent=parent)


def ellipsoid_data(radii, location=(0, 0, 0), rings=10, segments=16):
    rx, ry, rz = radii
    verts = []
    for i in range(1, rings):
        v = -math.pi / 2 + math.pi * i / rings
        for j in range(segments):
            a = 2 * math.pi * j / segments
            verts.append((location[0] + rx * math.cos(v) * math.cos(a), location[1] + ry * math.cos(v) * math.sin(a),
                          location[2] + rz * math.sin(v)))
    faces = grid_faces(rings - 1, segments)
    south, north = len(verts), len(verts) + 1
    verts.append((location[0], location[1], location[2] - rz))
    verts.append((location[0], location[1], location[2] + rz))
    last = (rings - 2) * segments
    for j in range(segments):
        faces.append((south, (j + 1) % segments, j))
        faces.append((north, last + j, last + (j + 1) % segments))
    return verts, faces
