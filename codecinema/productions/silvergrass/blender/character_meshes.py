"""
character_meshes.py - final look of Saku (SHINOBI_rig) and Tenkosai (SAINT_rig): stylised low-poly body
meshes, costumes, weapons and props with procedural materials (runs inside Blender 5.2; no image files).

Called by characters.build(meshes='auto') as  build_meshes(rigs, props, dims)  after the rigs, controllers, sockets
and placeholder props exist. Contract: prop OBJECTS keep their names / parents / sockets /
attach offsets - only their mesh data (and materials) are replaced; body meshes are new objects in CHAR_<C>.

Public API
  build_meshes(rigs, props, dims) -> dict(name -> object)   body + costume objects created (props are updated in place)
  key_headband_glow(frame, value, interp='LINEAR')           SHINOBI crimson hachimaki emission 0..1 (night, DIRECTION §6)
  key_eye_glint(frame, value, interp='LINEAR')               SAINT eye glint 0..1 (S04 ~392; invisible at 0)
  key_blade_wet(char, frame, value, interp='LINEAR')         blade 'Wet' 0..1, char 'SHINOBI'|'SAINT'|None (= both)
  key_haori_burn(frame, value, interp='LINEAR')              SAINT haori (worn + thrown copy) burn/dissolve 0..1
  input_paths() -> dict                                      the keyable node values (owner, data path) per input
  tri_counts() -> dict                                       triangles per character (body+costume / props)
  MATERIAL_INPUTS                                            {input name: (owner kind, owner name, node name)}
  crest_2d(R) / build_haori / build_props / build_shinobi / build_saint_body   (building blocks, used by build_meshes)
  kit: Part, Geo, loft, capsule, ellipsoid, rbox, tube, ribbon, grid, HeadShape, chain_weights, rigid_object,
       skinned_object, mat_cloth / mat_skin / mat_hair / mat_simple / mat_blade / mat_wrap / mat_straw / burn_group

Objects (CHAR_<C> collections; body objects are also merged into characters.build()'s props dict)
  rigid : <C>_body_<bone> for head, neck, hips, upper_arm/forearm/forearm_twist/hand/shin/foot/toe .L/.R
  skinned: <C>_torso, <C>_hakama (int point attribute 'region': 0 left leg, 1 right leg), SHINOBI_hachimaki_tails,
           SAINT_beard, SAINT_haori (prop object, final mesh: coat + lining + collar + himo + sleeves + crest)
  props (mesh data replaced in place): <C>_katana_hand/_sheathed, <C>_saya, SAINT_katana_hand_tip /
           _tip_broken, SAINT_spear_slung/_hand/_world/_sheath_world, SAINT_hat (+ halves), SAINT_beard_cord (+ cut),
           SAINT_tasuki, SHINOBI_kunai_1..3 (+ _hand); SAINT_haori_thrown = rest snapshot of the final haori.

Construction
  * RIGID segments: one object per body bone, <C>_body_<bone>, bone-parented (world = rig at rest), built in rig space
    at the rest pose; every joint is covered by a rounded end/cap on the child segment (shoulder caps, elbow/knee/wrist
    balls, ankle cuffs) so nothing gaps in extreme poses.
  * SOFT parts (skinned, Armature modifier, numpy weights, restricted per region, no heat weighting): <C>_torso
    (fitted jacket / kimono), <C>_hakama, SAINT_beard, SHINOBI_hachimaki_tails, SAINT_haori (the prop object).
    Weights = chain-projection hat functions: each vertex is projected onto its region's bone chain (closest point on
    the rest segments = distance-to-bone-segment) and blended across the joints with a smoothstep of half-width b, so
    every region is a partition of unity over its own bones only.
  * Materials: Principled; fabrics with sheen + subtle UV-space (metric) slub/weave noise + bump; everything that can
    get wet reads the environment's world prop env_wet (Attribute node VIEW_LAYER) and darkens / gets glossier.
    Keyable node values (see MATERIAL_INPUTS): Glow (headband), Glint (saint eyes), Wet (blades), Burn (haori group,
    time-varying embers on fx_time through fxclock.drive_node_value).
Deterministic: all noise seeds come from zlib.crc32 of fixed strings; no Python hash().
"""

from codecinema.productions import film_root, source_root
import math
import os
import sys
import time
import traceback
import zlib

import bpy
import numpy as np
from mathutils import Matrix

ROOT = str(film_root("silvergrass"))
for _p in (os.path.join(str(source_root("silvergrass")), "common"), os.path.join(str(source_root("silvergrass")), "blender")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import config  # noqa: E402
import bl_util as U  # noqa: E402

MESH_VERSION = 1
PAL = config.PALETTE
CHARS = ("SHINOBI", "SAINT")

# keyable material inputs: name -> (owner kind, owner name, node name)
MATERIAL_INPUTS = {
    "Glow": ("MATERIAL", "MESH_SHINOBI_hachimaki", "Glow"),
    "Glint": ("MATERIAL", "MESH_SAINT_eye_glint", "Glint"),
    "Wet_SHINOBI": ("MATERIAL", "MESH_SHINOBI_blade", "Wet"),
    "Wet_SAINT": ("MATERIAL", "MESH_SAINT_blade", "Wet"),
    "Burn": ("NODE_GROUP", "MESH_haori_burn", "Burn"),
}


def _seed(name):
    """Deterministic integer seed from a string (zlib.crc32, never hash())."""
    return zlib.crc32(name.encode("utf-8")) & 0x7FFFFFFF


# =============================================================================================
# vector helpers
# =============================================================================================
def _v(x):
    return np.asarray(x, dtype=float)


def _unit(x):
    x = _v(x)
    n = np.linalg.norm(x)
    return x / n if n > 1e-12 else x


def frame_yz(y, zref):
    """Right-handed orthonormal frame (X, Y, Z) with Y = y, Z = zref made perpendicular to y, X = Y x Z."""
    y = _unit(y)
    z = _v(zref) - y * np.dot(_v(zref), y)
    if np.linalg.norm(z) < 1e-9:
        z = np.array((0.0, 0.0, 1.0)) if abs(y[2]) < 0.9 else np.array((0.0, -1.0, 0.0))
        z = z - y * np.dot(z, y)
    z = _unit(z)
    x = np.cross(y, z)
    return x, y, z


def smoothstep(e0, e1, x):
    """Hermite 0 -> 1 as x goes from e0 to e1 (e0 > e1 allowed: a falling edge)."""
    d = e1 - e0
    if abs(d) < 1e-12:
        d = 1e-12
    t = np.clip((np.asarray(x, dtype=float) - e0) / d, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def catmull(points, samples_per_seg=6, closed=False):
    """Centripetal-ish (uniform) Catmull-Rom through `points` -> (m,3) ndarray."""
    P = [_v(p) for p in points]
    if closed:
        P = [P[-1]] + P + [P[0], P[1]]
    else:
        P = [P[0] * 2 - P[1]] + P + [P[-1] * 2 - P[-2]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(samples_per_seg):
            t = k / samples_per_seg
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    if not closed:
        out.append(P[-2])
    return np.array(out)


def resample(path, n):
    """Resample a polyline to n points evenly spaced by arc length."""
    path = _v(path)
    d = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))]
    s = np.linspace(0.0, d[-1], n)
    return np.stack([np.interp(s, d, path[:, i]) for i in range(3)], axis=1)


# =============================================================================================
# geometry kit - every builder returns a Part (V (n,3), F [tuple], UV [per-face tuple of (u,v)])
# =============================================================================================
class Part:
    """Mesh fragment: vertices, faces, per-corner UVs, one material index for all its faces, optional per-vertex
    region labels (skinning)."""
    __slots__ = ("V", "F", "UV", "mat", "region", "fmat")

    def __init__(self, V, F, UV=None, mat=0, region=None, fmat=None):
        self.V = _v(V).reshape(-1, 3)
        self.F = [tuple(int(i) for i in f) for f in F]
        self.UV = UV if UV is not None else [tuple((0.0, 0.0) for _ in f) for f in self.F]
        self.mat = mat
        self.region = region
        self.fmat = fmat                       # optional per-face material (key/index) overriding `mat`

    def copy(self):
        return Part(self.V.copy(), list(self.F), list(self.UV), self.mat, self.region,
                    list(self.fmat) if self.fmat is not None else None)

    def face_centres(self):
        return np.array([self.V[list(f)].mean(axis=0) for f in self.F])

    def set_face_mat(self, pred, mat):
        """Per-face material `mat` where pred(face_centre (3,)) is True."""
        C = self.face_centres()
        if self.fmat is None:
            self.fmat = [self.mat] * len(self.F)
        for i, c in enumerate(C):
            if pred(c):
                self.fmat[i] = mat
        return self

    def transformed(self, M):
        """Apply a 4x4 (Matrix or ndarray) to the vertices (returns a new Part; winding kept for det > 0)."""
        M = np.array(M, dtype=float)
        V = self.V @ M[:3, :3].T + M[:3, 3]
        F, UV = self.F, self.UV
        if np.linalg.det(M[:3, :3]) < 0:
            F = [tuple(reversed(f)) for f in F]
            UV = [tuple(reversed(u)) for u in UV]
        return Part(V, F, UV, self.mat, self.region, list(self.fmat) if self.fmat is not None else None)

    def mirrored_x(self):
        """Mirror across the rig's YZ plane (x -> -x), flipping the winding so normals stay outward."""
        return self.transformed(np.diag((-1.0, 1.0, 1.0, 1.0)))

    def with_mat(self, mat):
        p = self.copy()
        p.mat = mat
        return p

    def with_region(self, region):
        p = self.copy()
        p.region = region
        return p


class Geo:
    """Accumulator of Parts -> one bpy mesh (material slots by index, UV map 'UVMap', int attribute 'region')."""

    def __init__(self):
        self.parts = []

    def add(self, *parts):
        for p in parts:
            if p is None:
                continue
            if isinstance(p, (list, tuple)):
                self.add(*p)
            else:
                self.parts.append(p)
        return self

    @property
    def V(self):
        return np.concatenate([p.V for p in self.parts]) if self.parts else np.zeros((0, 3))

    def tri_count(self):
        return sum(len(f) - 2 for p in self.parts for f in p.F)

    def regions(self):
        """Per-vertex region labels (None where a part has none)."""
        out = []
        for p in self.parts:
            out.extend([p.region] * len(p.V))
        return out

    def mesh(self, name, materials, smooth=True, sharp_angle=None):
        """-> bpy Mesh. materials: list (Part.mat = slot index) or dict {key: Material} (Part.mat / fmat = key;
        slots are created in first-use order)."""
        V, F, UV, MI = [], [], [], []
        n = 0
        keyed = isinstance(materials, dict)
        slots = []
        for p in self.parts:
            V.append(p.V)
            fm = p.fmat if p.fmat is not None else [p.mat] * len(p.F)
            for f, uv, m in zip(p.F, p.UV, fm):
                F.append(tuple(i + n for i in f))
                UV.append(uv)
                if keyed:
                    if m not in slots:
                        slots.append(m)
                    MI.append(slots.index(m))
                else:
                    MI.append(m)
            n += len(p.V)
        if keyed:
            materials = [materials[k] for k in slots]
        V = np.concatenate(V) if V else np.zeros((0, 3))
        me = bpy.data.meshes.get(name)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)
        me = bpy.data.meshes.new(name)
        me.from_pydata(V.tolist(), [], F)
        for m in materials:
            me.materials.append(m)
        if MI:
            me.polygons.foreach_set("material_index", MI)
        uvl = me.uv_layers.new(name="UVMap")
        flat = np.array([c for uv in UV for c in uv], dtype=float).ravel()
        if len(flat) == len(me.loops) * 2:
            uvl.data.foreach_set("uv", flat)
        me.update()
        if smooth:
            me.shade_smooth()
            if sharp_angle is not None:
                me.set_sharp_from_angle(angle=math.radians(sharp_angle))
        else:
            me.shade_flat()
        return me


def superellipse(theta, e=2.0):
    """Unit superellipse points (cos-like, sin-like) for exponent e (2 = ellipse, >2 squarer)."""
    c, s = np.cos(theta), np.sin(theta)
    k = 2.0 / e
    return np.sign(c) * np.abs(c) ** k, np.sign(s) * np.abs(s) ** k


def loft(stations, n=16, phase=0.0, profile=None, loop=False, cap0=False, cap1=False, mat=0, region=None,
         uv_len=None):
    """Loft rings along `stations`: dict(c, X, Z, rx, rz, e=2, mod=None).
    Ring point j = c + X*rx*px_j + Z*rz*pz_j with (px, pz) the unit superellipse at theta_j = 2pi j/n + phase (or the
    explicit unit `profile` [(px, pz)], counter-clockwise from +X towards +Z). `mod(theta, station_index)` may return
    radial multipliers (array n). A station with rx = rz = 0 is a POLE (one vertex, triangle fan). Faces point
    outward when X = Y x Z with Y = loft direction (frame_yz). loop=True joins the last ring to the first.
    UVs are metric: u = perimeter position (m, mean ring perimeter), v = arc length along the centres (m)."""
    if profile is not None:
        prof = _v(profile)
        n = len(prof)
        theta = np.arctan2(prof[:, 1], prof[:, 0])
    else:
        theta = np.linspace(0.0, 2.0 * math.pi, n, endpoint=False) + phase
    V, idx = [], []
    per = []
    for si, st in enumerate(stations):
        c, X, Z = _v(st["c"]), _v(st["X"]), _v(st["Z"])
        rx, rz = float(st["rx"]), float(st["rz"])
        if rx <= 1e-9 and rz <= 1e-9:
            idx.append([len(V)])
            V.append(c)
            per.append(0.0)
            continue
        if profile is not None:
            px, pz = prof[:, 0].copy(), prof[:, 1].copy()
        else:
            px, pz = superellipse(theta, st.get("e", 2.0))
        if st.get("mod") is not None:
            m = np.asarray(st["mod"](theta, si), dtype=float)
            px, pz = px * m, pz * m
        pts = c + np.outer(px * rx, X) + np.outer(pz * rz, Z)
        ids = list(range(len(V), len(V) + n))
        V.extend(pts)
        idx.append(ids)
        per.append(float(np.sum(np.linalg.norm(np.diff(np.vstack([pts, pts[:1]]), axis=0), axis=1))))
    cs = np.array([_v(st["c"]) for st in stations])
    vv = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(cs, axis=0), axis=1))]
    if uv_len is not None:
        vv = vv / max(vv[-1], 1e-9) * uv_len
    P = max(np.mean([p for p in per if p > 0]) if any(p > 0 for p in per) else 1.0, 1e-6)
    uj = [P * j / n for j in range(n + 1)]
    F, UV = [], []
    pairs = list(zip(range(len(stations) - 1), range(1, len(stations))))
    if loop:
        pairs.append((len(stations) - 1, 0))
    for a, b in pairs:
        A, B = idx[a], idx[b]
        va, vb = vv[a], (vv[b] if b > a else vv[a] + np.linalg.norm(cs[a] - cs[b]))
        if len(A) == 1 and len(B) == 1:
            continue
        for j in range(n):
            j1 = (j + 1) % n
            if len(A) == 1:
                F.append((A[0], B[j], B[j1]))
                UV.append(((0.5 * (uj[j] + uj[j + 1]), va), (uj[j], vb), (uj[j + 1], vb)))
            elif len(B) == 1:
                F.append((A[j], B[0], A[j1]))
                UV.append(((uj[j], va), (0.5 * (uj[j] + uj[j + 1]), vb), (uj[j + 1], va)))
            else:
                F.append((A[j], B[j], B[j1], A[j1]))
                UV.append(((uj[j], va), (uj[j], vb), (uj[j + 1], vb), (uj[j + 1], va)))
    if cap0 and len(idx[0]) > 1:
        ci = len(V)
        V.append(cs[0])
        A = idx[0]
        for j in range(n):
            j1 = (j + 1) % n
            F.append((ci, A[j1], A[j]))
            UV.append(((0.0, 0.0), (0.0, 0.0), (0.0, 0.0)))
    if cap1 and len(idx[-1]) > 1:
        ci = len(V)
        V.append(cs[-1])
        B = idx[-1]
        for j in range(n):
            j1 = (j + 1) % n
            F.append((ci, B[j], B[j1]))
            UV.append(((0.0, 0.0), (0.0, 0.0), (0.0, 0.0)))
    return Part(np.array(V), F, UV, mat, region)


def stations_along(points, radii, zref, e=2.0, mod=None, flat=1.0):
    """Stations following a polyline `points` (parallel frames from zref), radii scalar/(rx, rz) per point."""
    P = _v(points)
    out = []
    for i, p in enumerate(P):
        if i == 0:
            t = P[1] - P[0]
        elif i == len(P) - 1:
            t = P[-1] - P[-2]
        else:
            t = P[i + 1] - P[i - 1]
        X, Y, Z = frame_yz(t, zref)
        r = radii[i]
        rx, rz = (r, r * flat) if np.isscalar(r) else (r[0], r[1])
        out.append(dict(c=p, X=X, Z=Z, rx=rx, rz=rz, e=e, mod=mod))
    return out


def capsule(p0, p1, r0, r1=None, n=12, ring=3, zref=(0.0, -1.0, 0.0), flat=1.0, e=2.0, mat=0, region=None,
            mid=()):
    """Tapered capsule p0 -> p1 with hemispherical ends (pole vertices). mid = [(t, r)] extra interior stations."""
    r1 = r0 if r1 is None else r1
    p0, p1 = _v(p0), _v(p1)
    X, Y, Z = frame_yz(p1 - p0, zref)
    L = np.linalg.norm(p1 - p0)
    st = []
    for k in range(ring, 0, -1):
        a = math.pi / 2 * k / ring
        r = r0 * math.cos(a)
        st.append(dict(c=p0 - Y * r0 * math.sin(a) * flat ** 0, X=X, Z=Z, rx=r, rz=r * flat, e=e))
    ts = [(0.0, r0)] + [(t, r) for t, r in mid] + [(1.0, r1)]
    for t, r in ts:
        st.append(dict(c=p0 + Y * L * t, X=X, Z=Z, rx=r, rz=r * flat, e=e))
    for k in range(1, ring + 1):
        a = math.pi / 2 * k / ring
        r = r1 * math.cos(a)
        st.append(dict(c=p1 + Y * r1 * math.sin(a), X=X, Z=Z, rx=r, rz=r * flat, e=e))
    return loft(st, n=n, mat=mat, region=region)


def ellipsoid(c, X, Y, Z, radii, nu=16, nv=10, mat=0, region=None, e=2.0, mod=None):
    """Ellipsoid centred at c with axes X, Y, Z (unit, right-handed) and radii (rx, ry, rz); poles on +-Y."""
    c, X, Y, Z = _v(c), _unit(X), _unit(Y), _unit(Z)
    rx, ry, rz = radii
    st = []
    for k in range(nv + 1):
        phi = -math.pi / 2 + math.pi * k / nv
        cy, sy = math.cos(phi), math.sin(phi)
        if k in (0, nv):
            st.append(dict(c=c + Y * ry * sy, X=X, Z=Z, rx=0.0, rz=0.0))
        else:
            ce, se = np.sign(cy) * abs(cy) ** (2.0 / e), np.sign(sy) * abs(sy) ** (2.0 / e)
            st.append(dict(c=c + Y * ry * se, X=X, Z=Z, rx=rx * ce, rz=rz * ce, e=e, mod=mod))
    return loft(st, n=nu, mat=mat, region=region)


def rbox(c, X, Y, Z, size, e=4.0, nu=12, nv=6, mat=0, region=None):
    """Rounded box (superellipsoid, exponent e) centred at c, axes X/Y/Z, full sizes (sx, sy, sz)."""
    return ellipsoid(c, X, Y, Z, (size[0] / 2, size[1] / 2, size[2] / 2), nu=nu, nv=nv, mat=mat, region=region, e=e)


def tube(path, radius, n=6, zref=(0.0, 0.0, 1.0), loop=False, cap=True, mat=0, region=None, flat=1.0, e=2.0):
    """Tube swept along a polyline with parallel-transported frames (cords, straps). radius scalar or per point.
    loop=True closes the path (the twist mismatch is spread along the loop)."""
    P = _v(path)
    m = len(P)
    R = np.full(m, radius) if np.isscalar(radius) else _v(radius)
    T = []
    for i in range(m):
        if loop:
            t = P[(i + 1) % m] - P[i - 1]
        else:
            t = P[min(i + 1, m - 1)] - P[max(i - 1, 0)]
        T.append(_unit(t))
    X0, _, Z0 = frame_yz(T[0], zref)
    Zs = [Z0]
    for i in range(1, m):
        z = Zs[-1] - T[i] * np.dot(Zs[-1], T[i])
        Zs.append(_unit(z))
    if loop:
        zl = Zs[-1] - T[0] * np.dot(Zs[-1], T[0])
        zl = _unit(zl)
        ang = math.atan2(np.dot(np.cross(zl, Zs[0]), T[0]), np.dot(zl, Zs[0]))
        for i in range(m):
            a = ang * i / m
            z, t = Zs[i], T[i]
            x = np.cross(t, z)
            Zs[i] = _unit(z * math.cos(a) + x * math.sin(a))
    st = []
    for i in range(m):
        X = np.cross(T[i], Zs[i])
        st.append(dict(c=P[i], X=X, Z=Zs[i], rx=R[i], rz=R[i] * flat, e=e))
    return loft(st, n=n, loop=loop, cap0=cap and not loop, cap1=cap and not loop, mat=mat, region=region)


def ribbon(path, widths, updirs, thickness=0.003, mat=0, region=None, twist_ok=True):
    """Flat ribbon (rectangular section) along `path`; widths per point; `updirs` per point = the ribbon's width
    direction hint (projected perpendicular to the path)."""
    P = _v(path)
    m = len(P)
    W = np.full(m, widths) if np.isscalar(widths) else _v(widths)
    Ud = np.tile(_v(updirs), (m, 1)) if np.ndim(updirs) == 1 else _v(updirs)
    st = []
    for i in range(m):
        t = P[min(i + 1, m - 1)] - P[max(i - 1, 0)]
        X, Y, Z = frame_yz(t, Ud[i])
        st.append(dict(c=P[i], X=X, Z=Z, rx=thickness * 0.5, rz=max(W[i] * 0.5, 1e-5)))
    prof = [(1.0, -1.0), (1.0, 1.0), (-1.0, 1.0), (-1.0, -1.0)]
    return loft(st, profile=prof, cap0=True, cap1=True, mat=mat, region=region)


def polygon_prism(pts2d, origin, X, Y, N, depth, mat=0, region=None):
    """Extrude a convex-ish 2D outline (counter-clockwise in X/Y) along N by `depth` (decal plates, soles)."""
    P = _v(pts2d)
    k = len(P)
    base = _v(origin) + np.outer(P[:, 0], _v(X)) + np.outer(P[:, 1], _v(Y))
    top = base + _v(N) * depth
    V = np.vstack([base, top])
    F = [tuple(range(k - 1, -1, -1)), tuple(range(k, 2 * k))]
    for i in range(k):
        i1 = (i + 1) % k
        F.append((i, i1, k + i1, k + i))
    return Part(V, F, None, mat, region)


def grid(P, wrap=True, mat=0, region=None, pole0=None, pole1=None):
    """Quad grid surface from points P (rows, cols, 3); wrap joins the last column to the first. pole0/pole1 = an
    extra vertex closing the first/last row with a triangle fan. Metric UVs (u along a row, v across rows)."""
    P = _v(P)
    nr, nc = P.shape[0], P.shape[1]
    V = [p for row in P for p in row]
    cols = nc if wrap else nc - 1
    du = np.linalg.norm(np.diff(np.concatenate([P, P[:, :1]], axis=1) if wrap else P, axis=1), axis=2).mean(axis=0)
    u = np.r_[0.0, np.cumsum(du)]
    dv = np.linalg.norm(np.diff(P, axis=0), axis=2).mean(axis=1) if nr > 1 else np.zeros(0)
    v = np.r_[0.0, np.cumsum(dv)]
    F, UV = [], []
    for i in range(nr - 1):
        for j in range(cols):
            j1 = (j + 1) % nc
            F.append((i * nc + j, (i + 1) * nc + j, (i + 1) * nc + j1, i * nc + j1))
            UV.append(((u[j], v[i]), (u[j], v[i + 1]), (u[j + 1], v[i + 1]), (u[j + 1], v[i])))
    for pole, row, sgn in ((pole0, 0, 1), (pole1, nr - 1, -1)):
        if pole is None:
            continue
        ci = len(V)
        V.append(_v(pole))
        for j in range(cols):
            j1 = (j + 1) % nc
            a, b = row * nc + j, row * nc + j1
            F.append((ci, b, a) if sgn > 0 else (ci, a, b))
            vv = v[row] - sgn * 0.01
            UV.append(((0.5 * (u[j] + u[j + 1]), vv), (u[j + 1], v[row]), (u[j], v[row])) if sgn > 0 else
                      ((0.5 * (u[j] + u[j + 1]), vv), (u[j], v[row]), (u[j + 1], v[row])))
    return Part(np.array(V), F, UV, mat, region)


def bumps(V, N, spec):
    """Sculpt: displace points V along normals N by a sum of anisotropic gaussians
    spec = [(centre (3,), radii (3,) or scalar, amplitude)]."""
    V = _v(V).copy()
    d = np.zeros(len(V))
    for c, r, a in spec:
        r = np.full(3, r) if np.isscalar(r) else _v(r)
        q = (V - _v(c)) / r
        d += a * np.exp(-np.sum(q * q, axis=1))
    return V + N * d[:, None]


# =============================================================================================
# rig rest data, parenting, skinning
# =============================================================================================
class RigRest:
    """Rest-pose (rig space) bone data of a rig: head/tail points, axes, frames."""

    def __init__(self, rig):
        self.rig = rig
        self.char = rig["char"]
        import characters as C
        self.s = C.RIG_PARAMS[self.char]["H"] / C.REF_HEIGHT
        self.B = rig.data.bones

    def h(self, b):
        return np.array(self.B[b].head_local[:])

    def t(self, b):
        return np.array(self.B[b].tail_local[:])

    def ax(self, b):
        m = self.B[b].matrix_local
        return (np.array([m[0][0], m[1][0], m[2][0]]), np.array([m[0][1], m[1][1], m[2][1]]),
                np.array([m[0][2], m[1][2], m[2][2]]))

    def M(self, b):
        return np.array(self.B[b].matrix_local)

    def at(self, b, x=0.0, y=0.0, z=0.0, frac=None):
        """Point in bone b's frame measured from its head (frac: y as a fraction of the bone length)."""
        X, Y, Z = self.ax(b)
        if frac is not None:
            y = frac * self.B[b].length
        return self.h(b) + X * x + Y * y + Z * z

    def length(self, b):
        return self.B[b].length


def _mesh_object(name, me, col):
    ob = bpy.data.objects.get(name)
    if ob is None:
        ob = U.new_object(name, me, col)
    else:
        old = ob.data
        ob.data = me
        if old is not None and old != me and old.users == 0:
            bpy.data.meshes.remove(old)
    ob["mesh_lane"] = MESH_VERSION
    return ob


def rigid_object(name, geo, mats, rig, bone, col, smooth=True, sharp=50.0):
    """Bone-parented rigid segment: verts in rig space at rest; world = rig.matrix_world in the rest pose."""
    me = geo.mesh(name + "_mesh", mats, smooth=smooth, sharp_angle=sharp)
    ob = _mesh_object(name, me, col)
    ob.parent = rig
    ob.parent_type = 'BONE'
    ob.parent_bone = bone
    ob.matrix_parent_inverse = Matrix.Identity(4)
    B = rig.data.bones[bone]
    ob.matrix_basis = Matrix.Translation((0.0, -B.length, 0.0)) @ B.matrix_local.inverted()
    return ob


def skinned_object(name, geo, mats, rig, col, weights, smooth=True, sharp=50.0, ob=None, regions=None):
    """Skinned soft part: verts in rig space, child of the rig (identity), Armature modifier, vertex groups from
    `weights` = {bone: ndarray (nverts,)} (already normalised, restricted per region)."""
    me = geo.mesh(name + "_mesh", mats, smooth=smooth, sharp_angle=sharp)
    if ob is None:
        ob = _mesh_object(name, me, col)
    else:
        old = ob.data
        ob.data = me
        if old is not None and old != me and old.users == 0:
            bpy.data.meshes.remove(old)
        ob["mesh_lane"] = MESH_VERSION
    ob.parent = rig
    ob.parent_type = 'OBJECT'
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_basis = Matrix.Identity(4)
    ob.vertex_groups.clear()
    for bn, w in sorted(weights.items()):        # sorted: deterministic group order (weights may come from sets)
        nz = np.nonzero(w > 1e-4)[0]
        if len(nz) == 0:
            continue
        vg = ob.vertex_groups.new(name=bn)
        # group vertices by (rounded) weight to keep the add() calls few
        wr = np.round(w[nz], 4)
        for val in np.unique(wr):
            ids = nz[wr == val]
            vg.add(ids.tolist(), float(val), 'REPLACE')
    mod = ob.modifiers.get("Armature") or ob.modifiers.new("Armature", 'ARMATURE')
    mod.object = rig
    mod.use_vertex_groups = True
    mod.use_deform_preserve_volume = False
    if regions is not None:                       # int point attribute 'region' (skinning region id, QA)
        a = ob.data.attributes.get("region") or ob.data.attributes.new("region", 'INT', 'POINT')
        a.data.foreach_set("value", np.asarray(regions, dtype=np.int32))
    return ob


def _closest_on_segment(V, a, b):
    ab = b - a
    t = np.clip(((V - a) @ ab) / max(ab @ ab, 1e-12), 0.0, 1.0)
    P = a + np.outer(t, ab)
    return np.linalg.norm(V - P, axis=1), t


def chain_weights(V, rr, chain, blend=0.05, blends=None, ends=None, segs=None):
    """Distance-to-bone-segment skinning restricted to one chain of bones.
    Each vertex is projected onto the closest segment of `chain` (rest pose) -> arc-length s along the chain; the
    weights are smoothstep hat functions across every joint (half-width `blend`, or per-joint `blends`), i.e. a
    partition of unity over exactly these bones. `ends` = (a, b) overrides the first segment start / last end.
    Returns {bone: w (n,)}."""
    V = _v(V)
    segs = [(_v(a), _v(b)) for a, b in segs] if segs is not None else [(rr.h(b), rr.t(b)) for b in chain]
    if ends is not None:
        if ends[0] is not None:
            segs[0] = (_v(ends[0]), segs[0][1])
        if ends[1] is not None:
            segs[-1] = (segs[-1][0], _v(ends[1]))
    L = [np.linalg.norm(b - a) for a, b in segs]
    S0 = np.r_[0.0, np.cumsum(L)]
    D = np.zeros((len(V), len(segs)))
    T = np.zeros((len(V), len(segs)))
    for k, (a, b) in enumerate(segs):
        D[:, k], T[:, k] = _closest_on_segment(V, a, b)
    k = np.argmin(D, axis=1)
    s = S0[k] + T[np.arange(len(V)), k] * np.array(L)[k]
    W = {}
    nb = len(chain)
    for i, bn in enumerate(chain):
        lo = 1.0 if i == 0 else smoothstep(-1.0, 1.0, (s - S0[i]) / (blends[i - 1] if blends else blend))
        hi = 0.0 if i == nb - 1 else smoothstep(-1.0, 1.0, (s - S0[i + 1]) / (blends[i] if blends else blend))
        W[bn] = np.clip(lo - hi, 0.0, 1.0)
    tot = sum(W.values())
    for bn in W:
        W[bn] = W[bn] / np.maximum(tot, 1e-9)
    return W


def merge_weights(parts, n):
    """Combine per-region weight dicts: parts = [(vertex index array, {bone: w})] -> {bone: w (n,)} normalised."""
    out = {}
    for ids, W in parts:
        for bn, w in W.items():
            if bn not in out:
                out[bn] = np.zeros(n)
            out[bn][ids] += w
    tot = sum(out.values())
    for bn in out:
        out[bn] = out[bn] / np.maximum(tot, 1e-9)
    return out


def blend_weights(Wa, Wb, t):
    """(1-t)*Wa + t*Wb per vertex (t array or scalar)."""
    out = {}
    for bn in set(Wa) | set(Wb):
        a = Wa.get(bn, 0.0)
        b = Wb.get(bn, 0.0)
        out[bn] = (1.0 - t) * a + t * b
    return out


# =============================================================================================
# materials (Principled, procedural, no image files)
# =============================================================================================
def _new_mat(name):
    """Fresh material `name` (node tree cleared) -> (mat, NB, principled NodeRef, output NodeRef)."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    nt = mat.node_tree
    nt.nodes.clear()
    nb = U.NB(nt, group_io=False)
    out = nb.n('ShaderNodeOutputMaterial')
    bsdf = nb.n('ShaderNodeBsdfPrincipled')
    nb.link(bsdf['BSDF'], out.inp('Surface'))
    mat["mesh_lane"] = MESH_VERSION
    return mat, nb, bsdf, out


def _tc(nb, kind="UV"):
    return nb.n('ShaderNodeTexCoord')[kind]


def _env(nb, name):
    """World prop env_<name> (environment.py keys them; VIEW_LAYER attributes read 0 when absent)."""
    a = nb.n('ShaderNodeAttribute', attribute_type='VIEW_LAYER')
    a.node.attribute_name = f"env_{name}"
    return a['Fac']


def _scale_vec(nb, vec, sx, sy, sz=1.0):
    return nb.vmath('MULTIPLY', vec, (sx, sy, sz))


def _noise(nb, vec, scale=5.0, detail=2.0, rough=0.5, w=None, dims='3D'):
    r = nb.noise(vector=vec, w=w, scale=scale, detail=detail, roughness=rough, dims=dims if w is None else '4D')
    return r['Fac']


def _mix_col(nb, fac, a, b):
    return nb.mix(fac, a, b, data_type='RGBA')


def _col_scale(nb, col, k):
    """colour * scalar socket/number."""
    return nb.mix(1.0, col, k, data_type='RGBA', blend='MULTIPLY') if not isinstance(k, (int, float)) else \
        nb.mix(1.0, col, (k, k, k, 1.0), data_type='RGBA', blend='MULTIPLY')


def _variation(nb, base, fac, amount):
    """base colour * (1 + amount * (fac - 0.5) * 2)."""
    k = nb.math('MULTIPLY_ADD', nb.math('SUBTRACT', fac, 0.5), 2.0 * amount, 1.0)
    return nb.mix(1.0, base, nb.n('ShaderNodeCombineXYZ', k, k, k)['Vector'], data_type='RGBA', blend='MULTIPLY')


def _wet_mix(nb, col, rough, dark=0.45, gloss=0.35, extra_wet=None):
    """Darken colour and lower roughness by env_wet (and optional extra wet socket, max of both)."""
    wet = _env(nb, "wet")
    if extra_wet is not None:
        wet = nb.math('MAXIMUM', wet, extra_wet)
    col2 = _mix_col(nb, wet, col, _col_scale(nb, col, 1.0 - dark))
    r2 = nb.math('MULTIPLY', rough, nb.math('MULTIPLY_ADD', wet, -gloss, 1.0))
    return col2, r2, wet


def mat_cloth(name, color, rough=0.82, sheen=0.55, sheen_tint=(1.0, 1.0, 1.0), slub=0.07, mottle=0.08,
              thread=320.0, bump=0.12, wet_dark=0.45, spec=0.3, emission=None):
    """Fabric: sheen + metric UV slub/weave noise (warp/weft streak noise) + large mottling + bump; env_wet darkens.
    emission = (colour, strength socket or float) for glowing cloth."""
    mat, nb, b, out = _new_mat(name)
    uv = _tc(nb, "UV")
    warp = _noise(nb, _scale_vec(nb, uv, thread * 0.08, thread), scale=1.0, detail=1.0)
    weft = _noise(nb, _scale_vec(nb, uv, thread, thread * 0.08), scale=1.0, detail=1.0)
    weave = nb.math('MULTIPLY', nb.math('ADD', warp, weft), 0.5)
    mott = _noise(nb, _tc(nb, "Object"), scale=6.0, detail=3.0, rough=0.55)
    col = _variation(nb, color, mott, mottle)
    col = _variation(nb, col, weave, slub)
    col, r, wet = _wet_mix(nb, col, nb.math('MULTIPLY_ADD', mott, 0.1, rough - 0.05), dark=wet_dark)
    nb.link(col, b.inp('Base Color'))
    nb.link(r, b.inp('Roughness'))
    b.inp('Sheen Weight').default_value = sheen
    b.inp('Sheen Roughness').default_value = 0.45
    b.inp('Sheen Tint').default_value = (*sheen_tint, 1.0)
    b.inp('Specular IOR Level').default_value = spec
    bm = nb.n('ShaderNodeBump', Strength=bump, Distance=0.002)
    nb.link(weave, bm.inp('Height'))
    nb.link(bm['Normal'], b.inp('Normal'))
    if emission is not None:
        ecol, estr = emission
        b.inp('Emission Color').default_value = (*ecol, 1.0)
        nb.set(b.inp('Emission Strength'), estr)
    mat.diffuse_color = (*color, 1.0)
    return mat, nb, b


def mat_skin(name, color, rough=0.48, sss=0.12, mottle=0.12, scar=None):
    """Skin: subsurface, fine mottling (redder / darker patches), wet -> glossier."""
    mat, nb, b, out = _new_mat(name)
    ob = _tc(nb, "Object")
    n1 = _noise(nb, ob, scale=28.0, detail=3.0, rough=0.6)
    n2 = _noise(nb, ob, scale=6.0, detail=2.0)
    col = _variation(nb, color, n1, mottle * 0.6)
    red = _mix_col(nb, nb.math('MULTIPLY', n2, 0.35), col, (color[0] * 1.15, color[1] * 0.85, color[2] * 0.8, 1.0))
    col, r, wet = _wet_mix(nb, red, nb.math('MULTIPLY_ADD', n1, 0.12, rough - 0.06), dark=0.12, gloss=0.5)
    nb.link(col, b.inp('Base Color'))
    nb.link(r, b.inp('Roughness'))
    b.inp('Subsurface Weight').default_value = sss
    b.inp('Subsurface Radius').default_value = (1.0, 0.35, 0.2)
    b.inp('Subsurface Scale').default_value = 0.02
    b.inp('Sheen Weight').default_value = 0.15
    b.inp('Specular IOR Level').default_value = 0.45
    bm = nb.n('ShaderNodeBump', Strength=0.08, Distance=0.001)
    nb.link(n1, bm.inp('Height'))
    nb.link(bm['Normal'], b.inp('Normal'))
    mat.diffuse_color = (*color, 1.0)
    return mat


def mat_hair(name, color, rough=0.5, streak=0.28, sheen=0.7):
    """Hair / beard / brows: streaks along the strands (UV v runs along the strand), sheen, wet -> darker, glossier."""
    mat, nb, b, out = _new_mat(name)
    uv = _tc(nb, "UV")
    s1 = _noise(nb, _scale_vec(nb, uv, 260.0, 9.0), scale=1.0, detail=2.0)
    s2 = _noise(nb, _tc(nb, "Object"), scale=9.0, detail=2.0)
    col = _variation(nb, color, s1, streak)
    col = _variation(nb, col, s2, 0.08)
    col, r, wet = _wet_mix(nb, col, nb.math('MULTIPLY_ADD', s1, 0.15, rough - 0.07), dark=0.35, gloss=0.45)
    nb.link(col, b.inp('Base Color'))
    nb.link(r, b.inp('Roughness'))
    b.inp('Sheen Weight').default_value = sheen
    b.inp('Sheen Roughness').default_value = 0.35
    b.inp('Specular IOR Level').default_value = 0.45
    bm = nb.n('ShaderNodeBump', Strength=0.3, Distance=0.002)
    nb.link(s1, bm.inp('Height'))
    nb.link(bm['Normal'], b.inp('Normal'))
    mat.diffuse_color = (*color, 1.0)
    return mat


def mat_simple(name, color, rough=0.5, metal=0.0, coat=0.0, coat_rough=0.05, noise=0.05, sheen=0.0,
               spec=0.5, wet=True):
    """Solid material with a little roughness/colour noise (lacquer: coat=1, metal fittings: metal=1)."""
    mat, nb, b, out = _new_mat(name)
    n1 = _noise(nb, _tc(nb, "Object"), scale=18.0, detail=3.0)
    col = _variation(nb, color, n1, noise)
    r = nb.math('MULTIPLY_ADD', n1, 0.12, rough - 0.06)
    if wet:
        col, r, _ = _wet_mix(nb, col, r, dark=0.15 if metal < 0.5 else 0.0, gloss=0.5)
    nb.link(col, b.inp('Base Color'))
    nb.link(r, b.inp('Roughness'))
    b.inp('Metallic').default_value = metal
    b.inp('Coat Weight').default_value = coat
    b.inp('Coat Roughness').default_value = coat_rough
    b.inp('Sheen Weight').default_value = sheen
    b.inp('Specular IOR Level').default_value = spec
    mat.diffuse_color = (*color, 1.0)
    return mat


def mat_eye(name, iris=(0.06, 0.035, 0.02)):
    """Glossy dark eye (iris/pupil fill the visible eye, stylised) - the key light leaves a tiny catch-light."""
    mat, nb, b, out = _new_mat(name)
    b.inp('Base Color').default_value = (*iris, 1.0)
    b.inp('Roughness').default_value = 0.06
    b.inp('Coat Weight').default_value = 1.0
    b.inp('Coat Roughness').default_value = 0.02
    b.inp('Specular IOR Level').default_value = 0.8
    mat.diffuse_color = (*iris, 1.0)
    return mat


def mat_glint(name):
    """Keyable emissive glint (node 'Glint' 0..1): invisible (alpha 0) at 0, a small warm-white spark at 1."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    nt = mat.node_tree
    nt.nodes.clear()
    nb = U.NB(nt, group_io=False)
    out = nb.n('ShaderNodeOutputMaterial')
    g = nb.n('ShaderNodeValue', name="Glint", label="Glint")
    g.node.outputs[0].default_value = 0.0
    em = nb.n('ShaderNodeEmission', Color=(1.0, 0.93, 0.8, 1.0))
    nb.link(nb.math('MULTIPLY', g['Value'], 24.0), em.inp('Strength'))
    tr = nb.n('ShaderNodeBsdfTransparent')
    mix = nb.n('ShaderNodeMixShader')
    nb.link(nb.math('MINIMUM', nb.math('MULTIPLY', g['Value'], 4.0), 1.0), mix.inp(0))
    nb.link(tr['BSDF'], mix.inp(1))
    nb.link(em['Emission'], mix.inp(2))
    nb.link(mix['Shader'], out.inp('Surface'))
    mat.surface_render_method = 'DITHERED'
    mat.use_transparent_shadow = True
    mat["mesh_lane"] = MESH_VERSION
    mat.diffuse_color = (1.0, 0.95, 0.85, 1.0)
    return mat


def mat_blade(name, polish=(0.60, 0.62, 0.66), hamon=(0.93, 0.94, 0.96), seed_name="blade"):
    """Polished steel with a lighter wavy hamon band along the edge (UV: u = metres along the blade, v = 0 at the
    edge .. 1 at the back). Node 'Wet' (0..1, max with env_wet): glossier, coated, beaded."""
    mat, nb, b, out = _new_mat(name)
    uv = nb.sep(_tc(nb, "UV"))
    u, v = uv['X'], uv['Y']
    wetv = nb.n('ShaderNodeValue', name="Wet", label="Wet")
    wetv.node.outputs[0].default_value = 0.0
    # hamon line: gunome-like waves + noise
    wave = nb.math('SINE', nb.math('MULTIPLY', u, 2.0 * math.pi * 11.0))
    wn = _noise(nb, nb.n('ShaderNodeCombineXYZ', nb.math('MULTIPLY', u, 14.0), 0.37, 0.0)['Vector'], scale=1.0,
                detail=2.0)
    h = nb.math('ADD', nb.math('MULTIPLY_ADD', wave, 0.045, 0.34), nb.math('MULTIPLY', nb.math('SUBTRACT', wn, 0.5), 0.10))
    # taper the hamon to the tip: yakiba narrower at the kissaki and at the machi fade-in
    m_ji = nb.map_range(nb.math('SUBTRACT', v, h), -0.035, 0.035, 0.0, 1.0)        # 0 hamon .. 1 ji
    nioi = nb.math('SUBTRACT', 1.0, nb.math('ABSOLUTE', nb.math('MULTIPLY', nb.math('SUBTRACT', m_ji, 0.5), 2.0)))
    col = _mix_col(nb, m_ji, (*hamon, 1.0), (*polish, 1.0))
    col = _mix_col(nb, nb.math('MULTIPLY', nioi, 0.45), col, (1.0, 1.0, 1.0, 1.0))
    rough = nb.math('ADD', nb.math('MULTIPLY_ADD', m_ji, -0.16, 0.30), 0.0)
    metal = nb.math('MULTIPLY_ADD', m_ji, 0.18, 0.80)
    wet = nb.math('MAXIMUM', wetv['Value'], nb.math('MULTIPLY', _env(nb, "wet"), 0.8))
    rough = nb.math('MULTIPLY', rough, nb.math('MULTIPLY_ADD', wet, -0.75, 1.0))
    drops = nb.n('ShaderNodeTexVoronoi', Scale=180.0)
    nb.link(_tc(nb, "Object"), drops.inp('Vector'))
    bead = nb.math('MULTIPLY', nb.math('LESS_THAN', drops['Distance'], 0.22), wet)
    bm = nb.n('ShaderNodeBump', Strength=0.35, Distance=0.0005)
    nb.link(bead, bm.inp('Height'))
    nb.link(col, b.inp('Base Color'))
    nb.link(rough, b.inp('Roughness'))
    nb.link(metal, b.inp('Metallic'))
    nb.link(wet, b.inp('Coat Weight'))
    b.inp('Coat Roughness').default_value = 0.02
    nb.link(bm['Normal'], b.inp('Normal'))
    nb.link(bm['Normal'], b.inp('Coat Normal'))
    mat.diffuse_color = (*polish, 1.0)
    return mat


def mat_wrap(name, wrap, window, rough_wrap=0.6, rough_win=0.35, period=0.030):
    """Tsuka-ito: diagonally crossing braid with diamond windows (samegawa / lacquer) in loft UV metres
    (UV.x around the handle, UV.y along it)."""
    mat, nb, b, out = _new_mat(name)
    uv = nb.sep(_tc(nb, "UV"))
    u = nb.math('DIVIDE', uv['Y'], period)                     # along the handle (loft v)
    v = nb.math('DIVIDE', uv['X'], period * 0.62)              # around it (loft u)
    du = nb.math('ABSOLUTE', nb.math('SUBTRACT', nb.math('FRACT', u), 0.5))
    dv = nb.math('ABSOLUTE', nb.math('SUBTRACT', nb.math('FRACT', v), 0.5))
    d = nb.math('ADD', du, dv)                                  # L1 distance to the diamond centre (0 .. 1)
    win = nb.map_range(d, 0.26, 0.31, 1.0, 0.0)                # 1 inside the diamond window
    ridge = nb.math('SUBTRACT', 1.0, nb.math('ABSOLUTE', nb.math('MULTIPLY', nb.math('SUBTRACT', nb.math('FRACT',
                    nb.math('MULTIPLY', nb.math('ADD', u, v), 2.0)), 0.5), 2.0)))
    tex = _noise(nb, _tc(nb, "Object"), scale=900.0, detail=1.0)
    wcol = _variation(nb, window, tex, 0.12)
    tcol = _variation(nb, wrap, ridge, 0.10)
    col = _mix_col(nb, win, tcol, wcol)
    rough = nb.math('ADD', nb.math('MULTIPLY', win, rough_win - rough_wrap), rough_wrap)
    col, rough, _ = _wet_mix(nb, col, rough, dark=0.3, gloss=0.4)
    nb.link(col, b.inp('Base Color'))
    nb.link(rough, b.inp('Roughness'))
    b.inp('Sheen Weight').default_value = 0.5
    bm = nb.n('ShaderNodeBump', Strength=0.5, Distance=0.0015)
    nb.link(nb.math('SUBTRACT', nb.math('MULTIPLY', ridge, 0.6), win), bm.inp('Height'))
    nb.link(bm['Normal'], b.inp('Normal'))
    mat.diffuse_color = (*wrap, 1.0)
    return mat


def mat_straw(name, color, dark_band=None):
    """Sedge/straw: fine fibres along UV v (u around, v along the fibre), colour variation per fibre, sheen."""
    mat, nb, b, out = _new_mat(name)
    uv = _tc(nb, "UV")
    fib = _noise(nb, _scale_vec(nb, uv, 420.0, 5.0), scale=1.0, detail=2.0)
    fib2 = _noise(nb, _scale_vec(nb, uv, 90.0, 2.0), scale=1.0, detail=1.0)
    mott = _noise(nb, _tc(nb, "Object"), scale=7.0, detail=2.0)
    col = _variation(nb, color, fib, 0.22)
    col = _variation(nb, col, fib2, 0.10)
    col = _variation(nb, col, mott, 0.10)
    col, r, wet = _wet_mix(nb, col, nb.math('MULTIPLY_ADD', fib, 0.15, 0.72), dark=0.4, gloss=0.3)
    nb.link(col, b.inp('Base Color'))
    nb.link(r, b.inp('Roughness'))
    b.inp('Sheen Weight').default_value = 0.35
    b.inp('Specular IOR Level').default_value = 0.35
    bm = nb.n('ShaderNodeBump', Strength=0.35, Distance=0.002)
    nb.link(fib, bm.inp('Height'))
    nb.link(bm['Normal'], b.inp('Normal'))
    mat.diffuse_color = (*color, 1.0)
    return mat


def burn_group():
    """Node group MESH_haori_burn (shared by every material of the haori, worn and thrown): Value 'Burn' 0..1
    (keyed by key_haori_burn) + Value 'FX Time' (driven by fxclock). Input Vector (Generated coords); outputs
    Alpha (0 = burnt away), Char (0..1 blackened), Ember (0..1 glowing front, flickering on fx_time)."""
    ng = bpy.data.node_groups.get("MESH_haori_burn")
    if ng is None:
        ng = bpy.data.node_groups.new("MESH_haori_burn", 'ShaderNodeTree')
        ng.interface.new_socket("Vector", in_out='INPUT', socket_type='NodeSocketVector')
        for s in ("Alpha", "Char", "Ember"):
            ng.interface.new_socket(s, in_out='OUTPUT', socket_type='NodeSocketFloat')
    ng.nodes.clear()
    nb = U.NB(ng, group_io=False)
    gi = nb.n('NodeGroupInput')
    go = nb.n('NodeGroupOutput')
    burn = nb.n('ShaderNodeValue', name="Burn", label="Burn")
    burn.node.outputs[0].default_value = 0.0
    fxt = nb.n('ShaderNodeValue', name="FX Time", label="FX Time")
    vec = gi['Vector']
    n = _noise(nb, vec, scale=3.2, detail=4.0, rough=0.6)
    gx = nb.sep(vec)['X']
    field = nb.math('ADD', nb.math('MULTIPLY', n, 0.65), nb.math('MULTIPLY', gx, 0.35))   # burns from local -x side
    t = nb.math('MULTIPLY_ADD', burn['Value'], 1.25, -0.15)
    d = nb.math('SUBTRACT', field, t)                          # < 0 burnt away
    alpha = nb.math('GREATER_THAN', d, 0.0)
    char = nb.map_range(d, 0.0, 0.10, 1.0, 0.0)
    flick = _noise(nb, vec, scale=9.0, detail=1.0, w=nb.math('MULTIPLY', fxt['Value'], 3.0))
    ember = nb.math('MULTIPLY', nb.map_range(d, 0.0, 0.028, 1.0, 0.0),
                    nb.math('MULTIPLY_ADD', flick, 1.2, 0.3))
    on = nb.math('GREATER_THAN', burn['Value'], 0.001)
    nb.link(nb.math('MAXIMUM', alpha, nb.math('SUBTRACT', 1.0, on)), go.inp('Alpha'))
    nb.link(nb.math('MULTIPLY', char, on), go.inp('Char'))
    nb.link(nb.math('MULTIPLY', nb.math('MULTIPLY', ember, alpha), on), go.inp('Ember'))
    ng["mesh_lane"] = MESH_VERSION
    try:
        import fxclock
        fxclock.drive_node_value(ng, "FX Time")
    except Exception as e:  # noqa: BLE001
        print("[character_meshes] FX Time driver not added:", e)
    return ng


def attach_burn(mat, nb, bsdf, base_col_socket=None):
    """Wire MESH_haori_burn into a Principled material: blackened char, orange ember emission, dissolve alpha."""
    ng = burn_group()
    g = nb.n('ShaderNodeGroup')
    g.node.node_tree = ng
    nb.link(_tc(nb, "Generated"), g.inp('Vector'))
    src = base_col_socket
    if src is None:
        lk = next((l for l in mat.node_tree.links if l.to_socket == bsdf.inp('Base Color')), None)
        src = lk.from_socket if lk else bsdf.inp('Base Color').default_value
    col = _mix_col(nb, g['Char'], src, (0.015, 0.012, 0.01, 1.0))
    nb.link(col, bsdf.inp('Base Color'))
    bsdf.inp('Emission Color').default_value = (1.0, 0.33, 0.06, 1.0)
    nb.link(nb.math('MULTIPLY', g['Ember'], 1.6), bsdf.inp('Emission Strength'))
    nb.link(g['Alpha'], bsdf.inp('Alpha'))
    mat.surface_render_method = 'DITHERED'
    return g


# =============================================================================================
# heads (built in the HEAD bone frame: x = his left, y = up the head bone from its head (neck top), z = forward)
# =============================================================================================
class HeadShape:
    """Sculpted head grid. `table` rows (y, W half-width, Zf front, Zb back, z0 centre) define superellipse rings
    (theta 0 = +x/left, 90 = front); `sculpt` = bumps [(centre, radii, amplitude)] displaced along the normals."""

    def __init__(self, table, sculpt, n=28, e=2.3, top=None, bottom=None):
        self.T = np.array(table, dtype=float)
        self.n = n
        self.e = e
        self.theta = np.linspace(0.0, 2.0 * math.pi, n, endpoint=False) - math.pi / 2   # col 0 = back
        rows = []
        for y, W, Zf, Zb, z0 in self.T:
            cx, sz = superellipse(self.theta, e)
            zz = z0 + np.where(sz > 0, Zf, Zb) * sz
            rows.append(np.stack([W * cx, np.full(n, y), zz], axis=1))
        P = np.array(rows)
        self.P0 = P.copy()
        N = self._normals(P)
        flat = bumps(P.reshape(-1, 3), N.reshape(-1, 3), sculpt).reshape(P.shape)
        self.P = flat
        self.N = self._normals(flat)
        self.top = top
        self.bottom = bottom

    def _normals(self, P):
        du = np.roll(P, -1, axis=1) - np.roll(P, 1, axis=1)
        dv = np.zeros_like(P)
        dv[1:-1] = P[2:] - P[:-2]
        dv[0] = P[1] - P[0]
        dv[-1] = P[-1] - P[-2]
        N = np.cross(dv, du)
        # orient outward (away from the ring centre)
        c = np.mean(P, axis=1, keepdims=True)
        sgn = np.sign(np.sum(N * (P - c), axis=2, keepdims=True))
        sgn[sgn == 0] = 1.0
        N = N * sgn
        return N / np.maximum(np.linalg.norm(N, axis=2, keepdims=True), 1e-9)

    def part(self, mat=0, rows=None):
        P = self.P if rows is None else self.P[rows[0]:rows[1]]
        pole1 = self.top if rows is None or rows[1] >= len(self.P) else None
        pole0 = self.bottom if rows is None or rows[0] == 0 else None
        return grid(P, wrap=True, mat=mat, pole0=pole0, pole1=pole1)

    def column_at(self, j, y):
        """Surface point + normal on column j at height y (linear between rows)."""
        ys = self.P[:, j, 1]
        order = np.argsort(ys)
        yy = ys[order]
        pts = self.P[order, j]
        nn = self.N[order, j]
        p = np.array([np.interp(y, yy, pts[:, k]) for k in range(3)])
        nv = np.array([np.interp(y, yy, nn[:, k]) for k in range(3)])
        return p, _unit(nv)

    def band(self, y_of_theta, offset, width, thick, n_sub=1):
        """Closed band around the head following the surface: centre height y(theta) per column, pushed out by
        `offset`; rectangular section (width along y, thickness along the normal). -> (P rows (4, n, 3))."""
        cs, ns = [], []
        for j in range(self.n):
            p, nv = self.column_at(j, y_of_theta(self.theta[j]))
            cs.append(p + nv * offset)
            ns.append(nv)
        return np.array(cs), np.array(ns)


def _head_to_rig(rr, P, bone="head"):
    """Map head-local points (…,3) to rig space."""
    X, Y, Z = rr.ax(bone)
    h = rr.h(bone)
    P = _v(P)
    return h + P[..., 0:1] * X + P[..., 1:2] * Y + P[..., 2:3] * Z


def _part_to_rig(rr, part, bone="head"):
    q = part.copy()
    q.V = _head_to_rig(rr, part.V, bone)
    return q


def band_part(centres, normals, width, thick, up=(0.0, 1.0, 0.0), mat=0, taper=None):
    """Closed ring band (rectangular section) from per-column centres/normals (head frame)."""
    C, N = _v(centres), _v(normals)
    n = len(C)
    upv = _v(up)
    rows = []
    for dz, dy in ((-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)):
        rows.append(C + N * (dz * thick) + upv * (dy * width))
    P = np.array(rows)                 # (4, n, 3): inner-bottom, outer-bottom, outer-top, inner-top
    P = np.concatenate([P, P[:1]], axis=0)
    g = grid(P[:4], wrap=True, mat=mat)
    # close the section (last row -> first row)
    V = g.V
    F = list(g.F)
    UV = list(g.UV)
    for j in range(n):
        j1 = (j + 1) % n
        F.append((3 * n + j, 0 * n + j, 0 * n + j1, 3 * n + j1))
        UV.append(((0, 0), (0, 0), (0, 0), (0, 0)))
    return Part(V, F, UV, mat)


def sphere_cap(c, r, axis, ang, n=14, rings=4, mat=0):
    """Spherical cap of radius r around unit `axis` through centre c with angular radius `ang` (rad)."""
    ax = _unit(axis)
    X, Y, Z = frame_yz(ax, (0.0, 1.0, 0.0) if abs(ax[1]) < 0.9 else (1.0, 0.0, 0.0))
    st = [dict(c=_v(c) + ax * r, X=X, Z=Z, rx=0.0, rz=0.0)]
    for k in range(1, rings + 1):
        a = ang * k / rings
        st.append(dict(c=_v(c) + ax * r * math.cos(a), X=X, Z=Z, rx=r * math.sin(a), rz=r * math.sin(a)))
    st = st[::-1]
    return loft(st, n=n, mat=mat)


def eye_parts(centre, r, mat_eye, mat_lid, mat_lash, open_up=0.62, open_dn=0.30, tilt=0.12, side=1.0,
              lid_thick=0.0022, n=14):
    """Eyeball + upper/lower lid shells + lash line, in the head frame. centre = eyeball centre, looking +z.
    open_up / open_dn: how far (in sphere 'height' units -1..1) the upper / lower lid opening reaches.
    tilt: outer corner lower (almond). side = +1 left eye, -1 right eye."""
    sclera, iris, pupil = mat_eye if isinstance(mat_eye, (tuple, list)) else (mat_eye, mat_eye, mat_eye)
    parts = [ellipsoid(centre, (1, 0, 0), (0, 0, 1), (0, -1, 0), (r, r, r), nu=16, nv=10, mat=sclera),
             sphere_cap(centre, r * 1.012, (0.0, 0.0, 1.0), 0.62, mat=iris),
             sphere_cap(centre, r * 1.022, (0.0, 0.0, 1.0), 0.27, mat=pupil)]
    rl = r + lid_thick
    c = _v(centre)
    # lids as partial spheres: sample (azimuth a in the x-z front half, height h)
    az = np.linspace(-math.pi * 0.62, math.pi * 0.62, n)            # around the front, 0 = straight ahead
    for upper in (True, False):
        rows = []
        hs = np.linspace(1.0, 0.0, 6) if upper else np.linspace(-1.0, 0.0, 5)
        for k, hh in enumerate(hs):
            row = []
            for a in az:
                edge = (open_up if upper else -open_dn) - tilt * side * math.sin(a) * (1 if upper else 0.5)
                # blend from the pole (hh=+-1) to the edge (hh=0)
                pole = 1.0 if upper else -1.0
                hv = pole + (edge - pole) * (1.0 - abs(hh))
                ch = math.sqrt(max(1.0 - hv * hv, 0.0))
                row.append(c + np.array((math.sin(a) * ch * rl, hv * rl, math.cos(a) * ch * rl)))
            rows.append(row)
        P = np.array(rows)
        if not upper:
            P = P[::-1]
        parts.append(grid(P, wrap=False, mat=mat_lid))
        if upper:
            lash = P[-1] + (P[-1] - c) * 0.06
            parts.append(tube(lash, 0.0011, n=4, mat=mat_lash, cap=True))
    return parts


def surface_front(hs, x, y):
    """Point + normal on the FRONT half of HeadShape `hs` at head-local (x, y) (bracketing columns interpolated)."""
    best = None
    for j in range(hs.n):
        j1 = (j + 1) % hs.n
        p0, n0 = hs.column_at(j, y)
        p1, n1 = hs.column_at(j1, y)
        if min(p0[2], p1[2]) < 0.0:
            continue
        if (p0[0] - x) * (p1[0] - x) <= 0.0 and abs(p1[0] - p0[0]) > 1e-9:
            t = (x - p0[0]) / (p1[0] - p0[0])
            q = p0 + (p1 - p0) * t
            nq = _unit(n0 + (n1 - n0) * t)
            if best is None or q[2] > best[0][2]:
                best = (q, nq)
    if best is None:
        j = int(np.argmin([abs(hs.column_at(j, y)[0][0] - x) + (1 if hs.column_at(j, y)[0][2] < 0 else 0)
                           for j in range(hs.n)]))
        best = hs.column_at(j, y)
    return best


def _rows_following(hs, y_lo_fn, y_hi_fn, nrows, off_fn, power=1.0):
    """Grid rows (nrows, n, 3) on the head surface between y_lo(theta) and y_hi(theta), pushed out by off_fn(t)."""
    rows = []
    for i in range(nrows):
        t = i / (nrows - 1)
        row = []
        for j in range(hs.n):
            th = hs.theta[j]
            y = y_lo_fn(th) + (y_hi_fn(th) - y_lo_fn(th)) * (t ** power)
            p, nv = hs.column_at(j, y)
            row.append(p + nv * off_fn(t))
        rows.append(row)
    return np.array(rows)


def spike(base, direction, length, radius, n=5, bend=(0.0, 0.0, 0.0), mat=0, twist=0.0):
    """Faceted hair clump: cone from `base` along `direction` (slightly bent), n-sided."""
    d = _unit(direction)
    b = _v(bend)
    pts = [base + d * length * t + b * (t * t) * length for t in (0.0, 0.35, 0.7, 1.0)]
    rad = [radius, radius * 0.72, radius * 0.38, 0.0]
    st = stations_along(pts, rad, zref=(0.0, 0.0, 1.0) if abs(d[2]) < 0.9 else (1.0, 0.0, 0.0))
    return loft(st, n=n, phase=twist, cap0=True, mat=mat)


def shinobi_head(rr, mats):
    """SHINOBI head (rigid on 'head'): skin head, eyes + lids + lashes, brows, ears, short dark hair cap + tuft,
    crimson hachimaki band + knot, charcoal face mask over nose/mouth/jaw. Returns (parts_head_frame, extras)
    with extras['knot'] = knot centre (head frame) for the tails."""
    SK, LID, LASH, HAIR, BAND, MASK = (mats[k] for k in ("skin", "skin", "hair", "hair", "band", "mask"))
    EY = (mats["eye"], mats["iris"], mats["pupil"])
    table = [
        (-0.040, 0.030, 0.060, 0.022, 0.018),
        (-0.030, 0.043, 0.078, 0.036, 0.010),
        (-0.012, 0.054, 0.086, 0.052, 0.004),
        (0.010, 0.062, 0.088, 0.066, 0.000),
        (0.032, 0.068, 0.090, 0.080, -0.004),
        (0.055, 0.073, 0.092, 0.090, -0.006),
        (0.080, 0.077, 0.094, 0.097, -0.007),
        (0.105, 0.079, 0.095, 0.100, -0.006),
        (0.130, 0.079, 0.093, 0.100, -0.005),
        (0.158, 0.074, 0.085, 0.094, -0.005),
        (0.182, 0.061, 0.069, 0.078, -0.005),
        (0.199, 0.042, 0.047, 0.054, -0.005),
        (0.208, 0.022, 0.024, 0.028, -0.005),
    ]
    sculpt = [
        ((0.032, 0.086, 0.09), (0.017, 0.011, 0.02), -0.0085),     # eye sockets
        ((-0.032, 0.086, 0.09), (0.017, 0.011, 0.02), -0.0085),
        ((0.030, 0.105, 0.095), (0.026, 0.008, 0.02), 0.0045),     # brow ridge
        ((-0.030, 0.105, 0.095), (0.026, 0.008, 0.02), 0.0045),
        ((0.0, 0.080, 0.098), (0.008, 0.022, 0.02), 0.009),        # nose bridge
        ((0.0, 0.052, 0.100), (0.012, 0.012, 0.02), 0.017),        # nose
        ((0.050, 0.066, 0.075), (0.018, 0.016, 0.02), 0.004),      # cheekbones
        ((-0.050, 0.066, 0.075), (0.018, 0.016, 0.02), 0.004),
        ((0.0, -0.028, 0.080), (0.020, 0.012, 0.02), 0.006),       # chin
    ]
    hs = HeadShape(table, sculpt, n=28, top=(0.0, 0.2115, -0.005), bottom=(0.0, -0.044, 0.022))
    parts = [hs.part(mat=SK)]
    # eyes + lids + brows
    r = 0.0128
    for side in (1.0, -1.0):
        p, nv = surface_front(hs, 0.0325 * side, 0.087)
        c = p - nv * (r - 0.0036) + np.array((0.0, 0.0, -0.001))
        parts += eye_parts(c, r, EY, LID, LASH, open_up=0.40, open_dn=0.30, tilt=0.14, side=side)
        brow = []
        for t in np.linspace(0.0, 1.0, 7):
            x = side * (0.012 + 0.044 * t)
            q, qn = surface_front(hs, x, 0.1005 + 0.0085 * t - 0.0065 * t * t)
            brow.append(q + qn * 0.0026)
        w = np.linspace(0.0095, 0.0045, 7)
        parts.append(ribbon(brow, w, (0.0, 1.0, 0.25), thickness=0.0045, mat=HAIR))
        ear_c = np.array((0.0755 * side, 0.074, -0.012))
        ea = _unit((side * 0.18, 0.0, -1.0))
        parts.append(ellipsoid(ear_c, _unit(np.cross((0, 1, 0), ea)) * side, (0.0, 1.0, 0.0), ea,
                               (0.0055, 0.024, 0.015), nu=10, nv=6, mat=SK))
    # hair cap: hairline under the band at the front, above the ears on the sides, nape at the back
    def hair_lo(th):
        return 0.112 + 0.022 * max(math.sin(th), 0.0) - 0.050 * max(-math.sin(th), 0.0) * (0.6 + 0.4 * math.cos(th) ** 2)
    rows = _rows_following(hs, hair_lo, lambda th: 0.2105, 7, lambda t: 0.004 + 0.008 * t, power=0.9)
    parts.append(grid(rows, wrap=True, mat=HAIR, pole1=(0.0, 0.2215, -0.005)))
    # tuft: broad faceted clumps - a spiky crest on the crown sweeping up/back, flatter clumps over the back and
    # sides, a few spilling over the band at the front
    rng = np.random.default_rng(_seed("SHINOBI:hair_tuft"))
    hair_rows = rows

    def cap_pt(th, t):
        j = int(round((th + math.pi / 2) / (2 * math.pi) * hs.n)) % hs.n
        i = min(int(round(t * (len(hair_rows) - 1))), len(hair_rows) - 1)
        return hair_rows[i, j]
    clumps = []
    for k in range(6):                                            # crown tuft, swept back
        th = math.radians(-90 + 180 * (k + 0.5) / 6)
        clumps.append((th, 0.82, (0.0, 0.55, -0.85), 0.062 + 0.010 * math.sin(k * 1.7), 0.024))
    for k in range(10):                                           # back / sides, lying down-back
        th = math.radians(-90 + (k - 4.5) * 24.0)
        clumps.append((th, 0.45, (0.0, -0.25, -1.0), 0.060, 0.022))
    for k in range(3):                                            # front, over the band
        th = math.radians(90 + (k - 1) * 22.0)
        clumps.append((th, 0.55, (0.0, 0.35, 1.0), 0.050, 0.020))
    for th, t, d, L, w in clumps:
        base = cap_pt(th, t)
        radial = _unit((base[0], 0.0, base[2] + 0.005))
        dd = _v(d)
        dd = _unit(dd + radial * 0.6 + rng.uniform(-0.15, 0.15, 3))
        parts.append(spike(base - dd * 0.012, dd, L, w, n=5, bend=(0.0, -0.3, 0.0) if d[1] > 0.5 else
                           (0.0, -0.15, 0.0), mat=HAIR, twist=float(rng.uniform(0, 1.2))))
    # hachimaki band (tilted: forehead high, knot low at the back)
    yb = lambda th: 0.1135 + 0.0145 * math.sin(th)                                   # noqa: E731
    C_, N_ = hs.band(yb, 0.0068, 0.034, 0.006)
    up = _unit((0.0, 1.0, -0.2))
    parts.append(band_part(C_, N_, 0.034, 0.0065, up=up, mat=BAND))
    knot_c = np.array((0.0, 0.100, -0.109))
    parts.append(ellipsoid(knot_c, (1, 0, 0), (0, 1, 0), (0, 0, 1), (0.019, 0.017, 0.012), nu=12, nv=6, mat=BAND))
    for side in (1.0, -1.0):                                                         # two short loops of the knot
        parts.append(rbox(knot_c + np.array((0.026 * side, 0.006, -0.004)), _unit((1, 0.3 * side, 0)), (0, 1, 0),
                          (0, 0, 1), (0.030, 0.022, 0.012), e=2.6, nu=10, nv=5, mat=BAND))
    # mask: from the nose bridge down over the chin to the throat, draped straight below the nose
    def m_top(th):
        return 0.0565 + 0.006 * math.sin(th) - 0.0115 * math.cos(2 * th)
    mrows = _rows_following(hs, m_top, lambda th: -0.030, 8, lambda t: 0.0055 + 0.001 * t)
    # extra rows under the chin -> ring around the neck axis
    neck_c = lambda y: np.array((0.0, y, -0.012 + (y + 0.03) * 0.25))                 # noqa: E731
    extra = []
    for y, k in ((-0.050, 0.45), (-0.068, 0.8), (-0.085, 1.0)):
        ring = []
        for j in range(hs.n):
            th = hs.theta[j]
            circ = neck_c(y) + np.array((math.cos(th) * 0.060, 0.0, math.sin(th) * 0.061))
            last = mrows[-1][j] + np.array((0.0, y + 0.030, 0.0))
            ring.append(last * (1 - k) + circ * k)
        extra.append(ring)
    M = np.concatenate([mrows, np.array(extra)], axis=0)
    # straight drape below the nose (front columns)
    for i in range(M.shape[0]):
        for j in range(hs.n):
            x, y, z = M[i, j]
            if z > 0.0 and y < 0.058:
                zl = 0.112 + (min(y, 0.05) - 0.05) * 0.30 - 38.0 * x * x
                if z < zl:
                    M[i, j, 2] = zl
    M = M[::-1]                                  # rows bottom -> top so the faces point outward
    parts.append(grid(M, wrap=True, mat=MASK))
    return parts, dict(knot=knot_c, hs=hs)


# =============================================================================================
# bodies - shared pieces
# =============================================================================================
def fix_winding(part, axis_pts):
    """Flip all faces of `part` if most face normals point towards the polyline `axis_pts` (inward)."""
    V = part.V
    A = _v(axis_pts)
    score = 0.0
    for f in part.F[:: max(1, len(part.F) // 200)]:
        p = V[list(f)]
        c = p.mean(axis=0)
        nrm = np.cross(p[1] - p[0], p[2] - p[0])
        best, q = 1e9, A[0]
        for a, b in zip(A[:-1], A[1:]):
            d, t = _closest_on_segment(c[None, :], a, b)
            if d[0] < best:
                best, q = d[0], a + (b - a) * t[0]
        score += np.sign(np.dot(nrm, c - q))
    if score < 0:
        part.F = [tuple(reversed(f)) for f in part.F]
        part.UV = [tuple(reversed(u)) for u in part.UV]
    return part


def torso_rings(table, n=32, spine=None, mod=None):
    """Horizontal rings (rows, n, 3) from a table [(z, hw, hd, cy, e)] (+ optional spine x/y offset by z).
    Column 0 = back (+y), counter-clockwise seen from above: back -> his right? (orientation fixed by fix_winding)."""
    th = np.linspace(0.0, 2.0 * math.pi, n, endpoint=False) + math.pi / 2
    rows = []
    for i, (z, hw, hd, cy, e) in enumerate(table):
        cx, sy = superellipse(th, e)
        if mod is not None:
            m = mod(th, z)
            cx, sy = cx * m, sy * m
        ox = 0.0
        oy = cy
        rows.append(np.stack([ox + hw * cx, oy + hd * sy, np.full(n, z)], axis=1))
    return np.array(rows), th


def torso_front_y(table, x, z):
    """Front surface y (most negative) of the torso table at (x, z) (superellipse section)."""
    T = np.array(table)
    hw = np.interp(z, T[:, 0], T[:, 1])
    hd = np.interp(z, T[:, 0], T[:, 2])
    cy = np.interp(z, T[:, 0], T[:, 3])
    e = np.interp(z, T[:, 0], T[:, 4])
    u = min(abs(x) / hw, 0.999)
    return cy - hd * (1.0 - u ** e) ** (1.0 / e)


def torso_surface(table, ang, z, off=0.0):
    """Point on the torso table surface at polar angle `ang` (0 = +x/left, -90 deg = front (-y)) and height z."""
    T = np.array(table)
    hw = np.interp(z, T[:, 0], T[:, 1])
    hd = np.interp(z, T[:, 0], T[:, 2])
    cy = np.interp(z, T[:, 0], T[:, 3])
    e = np.interp(z, T[:, 0], T[:, 4])
    c, s_ = superellipse(np.array([ang]), e)
    p = np.array((hw * c[0], cy + hd * s_[0], z))
    nrm = _unit((c[0] / hw, s_[0] / hd, 0.0))
    return p + nrm * off


def leg_rings(rr, side, table, n=20, spine_x=0.0, pleats=None):
    """Hakama leg rings (rows, n, 3) morphing from the waist D-shape (half of the waist superellipse, closed at
    x = 0) to a circle around the leg. table rows: (z, k, hw, hd, r_leg, e). Leg centre follows thigh/shin."""
    sx = 1.0 if side == "L" else -1.0
    pts = [rr.h(f"thigh.{side}"), rr.t(f"thigh.{side}"), rr.t(f"shin.{side}")]
    zs = np.array([p[2] for p in pts])[::-1]
    xs = np.array([p[0] for p in pts])[::-1]
    ys = np.array([p[1] for p in pts])[::-1]
    phi = np.linspace(0.0, 2.0 * math.pi, n, endpoint=False)
    rows = []
    for (z, k, hw, hd, r, e) in table:
        lx = np.interp(z, zs, xs) if z <= zs[-1] else pts[0][0]
        ly = np.interp(z, zs, ys) if z <= zs[-1] else pts[0][1]
        c = np.array((lx, ly))
        dirs = np.stack([np.cos(phi), np.sin(phi)], axis=1)
        # D shape: ray from the leg centre to the half-superellipse (x*sx >= 0) or the x = 0 line
        tD = np.full(n, 1e3)
        for j, d in enumerate(dirs):
            dxs = d[0] * sx
            if dxs < -1e-9:
                t0 = -(c[0] * sx) / dxs
                yy = c[1] + t0 * d[1]
                if abs(yy) <= hd:
                    tD[j] = t0
            lo, hi = 0.0, 1.0
            for _ in range(40):
                mid = 0.5 * (lo + hi)
                q = c + d * mid
                f = abs(q[0] / hw) ** e + abs(q[1] / hd) ** e
                if f < 1.0:
                    lo = mid
                else:
                    hi = mid
            if lo < tD[j]:
                tD[j] = lo
        Dp = c + dirs * tD[:, None]
        rr_ = r * (1.0 + (pleats(phi, z) if pleats is not None else 0.0))
        Cp = c + dirs * rr_[:, None] if np.ndim(rr_) else c + dirs * rr_
        P2 = Dp * (1.0 - k) + Cp * k
        rows.append(np.stack([P2[:, 0], P2[:, 1], np.full(n, z)], axis=1))
    return np.array(rows)


def fist_parts(rr, side, mats, glove, finger, s=1.0, chunky=1.0):
    """Stylised fist in the hand.<side> frame (rig space at rest): palm/back block, finger roll wrapped around the
    held-handle axis (weapon frame of that hand), knuckle ridge, thumb over the mune side."""
    import characters as C
    rig = rr.rig
    Gh = np.array(C.weapon_frame_in_hand(rig, side))                  # grip frame in the hand frame
    Mh = rr.M(f"hand.{side}")
    G = Mh @ Gh                                                        # grip frame in rig space
    g0, gX, gY, gZ = G[:3, 3], G[:3, 0], G[:3, 1], G[:3, 2]
    hX, hY, hZ = rr.ax(f"hand.{side}")
    h0 = rr.h(f"hand.{side}")
    k = s * chunky
    parts = []
    # palm / back of the hand block (wrist -> knuckles), palm normal = hZ
    parts.append(rbox(h0 + hY * 0.046 * s + hZ * 0.006 * s, hX, hY, hZ, (0.080 * k, 0.086 * s, 0.040 * k),
                      e=3.2, nu=14, nv=8, mat=glove))
    # finger roll around the grip axis
    L = 0.088 * s
    roll_c = g0 - gY * 0.006 * s
    st = []
    for t, r in ((-0.5, 0.0), (-0.47, 0.018), (-0.42, 0.024), (-0.2, 0.026), (0.1, 0.027), (0.35, 0.026),
                 (0.45, 0.022), (0.5, 0.0)):
        st.append(dict(c=roll_c + gY * (t * L), X=gX, Z=gZ, rx=r * k * 1.05, rz=r * k, e=2.4))
    parts.append(loft(st, n=12, mat=finger))
    # knuckle ridge on the back of the hand (towards the fingers)
    kn = h0 + hY * 0.084 * s - hZ * 0.004 * s
    parts.append(capsule(kn - hX * 0.034 * s, kn + hX * 0.034 * s, 0.013 * k, n=8, ring=2, mat=glove))
    # thumb: from the thenar (radial side near the wrist) over the mune side of the handle
    radial = hX if side == "R" else -hX
    t0 = h0 + hY * 0.030 * s + radial * 0.024 * s + hZ * 0.012 * s
    t1 = g0 + gZ * 0.020 * s + gY * 0.022 * s
    tm = (t0 + t1) * 0.5 + gZ * 0.006 * s
    parts.append(loft(stations_along(catmull([t0, tm, t1], 3), [(0.0125 * k, 0.011 * k)] * 7, gZ), n=8,
                      cap0=True, cap1=True, mat=finger))
    return parts


# =============================================================================================
# Saku - SHINOBI
# =============================================================================================
SHINOBI_TORSO = [   # (z, half-width, half-depth, centre y, superellipse e) - fitted charcoal jacket
    (0.880, 0.150, 0.108, 0.000, 2.4), (0.940, 0.143, 0.101, 0.000, 2.4), (1.000, 0.132, 0.093, -0.002, 2.4),
    (1.060, 0.130, 0.092, -0.004, 2.4), (1.120, 0.137, 0.096, -0.006, 2.5), (1.190, 0.148, 0.101, -0.008, 2.6),
    (1.260, 0.158, 0.106, -0.010, 2.7), (1.320, 0.165, 0.105, -0.008, 2.8), (1.370, 0.172, 0.098, -0.004, 2.9),
    (1.405, 0.172, 0.088, 0.000, 2.8), (1.428, 0.152, 0.076, 0.004, 2.6), (1.447, 0.104, 0.065, 0.006, 2.3),
    (1.462, 0.068, 0.059, 0.006, 2.0), (1.474, 0.060, 0.056, 0.006, 2.0),
]
SHINOBI_HAKAMA = [  # per leg: (z, k D->circle, waist hw, waist hd, leg radius, e)
    (1.012, 0.00, 0.141, 0.100, 0.10, 2.4), (0.975, 0.00, 0.149, 0.105, 0.10, 2.4),
    (0.930, 0.06, 0.160, 0.110, 0.104, 2.4), (0.880, 0.22, 0.167, 0.114, 0.106, 2.4),
    (0.830, 0.48, 0.170, 0.115, 0.105, 2.4), (0.780, 0.78, 0.170, 0.115, 0.103, 2.4),
    (0.730, 1.00, 0.170, 0.115, 0.108, 2.4), (0.650, 1.0, 0.1, 0.1, 0.106, 2.0), (0.570, 1.0, 0.1, 0.1, 0.100, 2.0),
    (0.500, 1.0, 0.1, 0.1, 0.093, 2.0), (0.440, 1.0, 0.1, 0.1, 0.082, 2.0), (0.390, 1.0, 0.1, 0.1, 0.069, 2.0),
    (0.350, 1.0, 0.1, 0.1, 0.059, 2.0),
]


def shinobi_materials():
    """MESH_SHINOBI_* materials keyed by role."""
    M = {}
    cool = (0.26, 0.28, 0.34)
    M["cloth"] = mat_cloth("MESH_SHINOBI_jacket", PAL["shinobi_cloth"], rough=0.8, sheen=0.45, sheen_tint=cool)[0]
    M["under"] = mat_cloth("MESH_SHINOBI_under", PAL["shinobi_under"], sheen=0.5)[0]
    M["collar"] = mat_cloth("MESH_SHINOBI_collar", (0.055, 0.058, 0.068), sheen=0.6, sheen_tint=cool)[0]
    M["hakama"] = mat_cloth("MESH_SHINOBI_hakama", PAL["shinobi_hakama"], sheen=0.5, sheen_tint=cool)[0]
    M["sash"] = mat_cloth("MESH_SHINOBI_sash", PAL["shinobi_red"], sheen=0.6, sheen_tint=(1.0, 0.55, 0.5))[0]
    band, nb, b = mat_cloth("MESH_SHINOBI_hachimaki", PAL["shinobi_red"], sheen=0.6, sheen_tint=(1.0, 0.55, 0.5))
    g = nb.n('ShaderNodeValue', name="Glow", label="Glow")
    g.node.outputs[0].default_value = 0.0
    b.inp('Emission Color').default_value = (1.0, 0.07, 0.04, 1.0)
    nb.link(nb.math("MULTIPLY", g["Value"], 0.55), b.inp("Emission Strength"))
    M["band"] = band
    M["mask"] = mat_cloth("MESH_SHINOBI_mask", (0.040, 0.042, 0.050), sheen=0.6, sheen_tint=cool)[0]
    M["skin"] = mat_skin("MESH_SHINOBI_skin", (0.50, 0.33, 0.24))
    M["hair"] = mat_hair("MESH_SHINOBI_hair", (0.013, 0.012, 0.012), rough=0.5, sheen=0.3)
    M["eye"] = mat_simple("MESH_SHINOBI_sclera", (0.60, 0.56, 0.52), rough=0.3, coat=0.8, coat_rough=0.03, wet=False)
    M["iris"] = mat_eye("MESH_SHINOBI_iris", iris=(0.035, 0.021, 0.013))
    M["pupil"] = mat_eye("MESH_SHINOBI_pupil", iris=(0.004, 0.003, 0.003))
    M["guard"] = mat_simple("MESH_SHINOBI_guard", (0.040, 0.041, 0.047), rough=0.38, metal=0.6, coat=0.25)
    M["glove"] = mat_simple("MESH_SHINOBI_glove", (0.032, 0.030, 0.030), rough=0.62, sheen=0.35)
    M["wrap"] = mat_cloth("MESH_SHINOBI_wrap", (0.078, 0.080, 0.090), sheen=0.55, sheen_tint=cool)[0]
    M["tabi"] = mat_cloth("MESH_SHINOBI_tabi", (0.030, 0.030, 0.034), sheen=0.45)[0]
    M["cord"] = mat_simple("MESH_SHINOBI_cord", (0.022, 0.022, 0.025), rough=0.7, sheen=0.3)
    return M


def _torso_weights(V, rr, top_bone="chest", sh_x=(0.07, 0.16), sh_z=(1.30, 1.40), neck_z=None, lo=0.86):
    """Torso cloth weights: hips/spine/chest chain by height + shoulder.L/R towards the shoulders
    (+ optional neck blend above neck_z)."""
    top = rr.t(top_bone) + rr.ax(top_bone)[1] * 0.08
    segs = [(np.array((0.0, 0.0, lo)), rr.t("hips")), (rr.h("spine"), rr.t("spine")), (rr.h("chest"), top)]
    W = chain_weights(V, rr, ["hips", "spine", "chest"], blends=[0.05, 0.06], segs=segs)
    ax = np.abs(V[:, 0])
    w_sh = smoothstep(sh_x[0], sh_x[1], ax) * smoothstep(sh_z[0], sh_z[1], V[:, 2]) * 0.85
    WL = {"shoulder.L": np.where(V[:, 0] > 0, 1.0, 0.0), "shoulder.R": np.where(V[:, 0] <= 0, 1.0, 0.0)}
    W = blend_weights(W, WL, w_sh)
    if neck_z is not None:
        w_n = smoothstep(neck_z[0], neck_z[1], V[:, 2]) * 0.5
        W = blend_weights(W, {"neck": np.ones(len(V))}, w_n)
    return W


def _arm_blend(P, W, amount=0.75, x=(0.10, 0.23), z=(1.36, 1.51)):
    """Armhole region follows the upper arm partially (cloth over the shoulder joint stretches with a raised arm);
    applied identically to every layer over the SAINT's shoulders so they deform together."""
    w = smoothstep(x[0], x[1], np.abs(P[:, 0])) * smoothstep(z[0], z[1], P[:, 2]) * amount
    return blend_weights(W, {"upper_arm.L": np.where(P[:, 0] > 0, 1.0, 0.0),
                             "upper_arm.R": np.where(P[:, 0] <= 0, 1.0, 0.0)}, w)


def _collar_path(table, side_top, z_top, z_apex, z_end, x_end, back_y, off):
    """Crossed-collar band path on the torso surface: back of the neck -> over the shoulder near the neck ->
    down the front to the V apex -> diagonally to (x_end, z_end). side_top = +1 (his left) / -1."""
    pts = [np.array((0.0, back_y, z_top - 0.004)),
           np.array((side_top * 0.050, back_y * 0.35, z_top)),
           np.array((side_top * 0.060, -0.030, z_top - 0.012))]
    for t in np.linspace(0.0, 1.0, 6):
        z = z_top - 0.035 - (z_top - 0.035 - z_apex) * t
        x = side_top * (0.052 * (1.0 - t)) + (-side_top) * 0.004 * t
        pts.append(np.array((x, torso_front_y(table, x, z) - off, z)))
    if z_end is not None:
        for t in np.linspace(0.2, 1.0, 5):
            z = z_apex - (z_apex - z_end) * t
            x = x_end * t
            pts.append(np.array((x, torso_front_y(table, x, z) - off, z)))
    return catmull(pts, 4)


def v_patch(table, path_l, path_r, z0, z1, mat, nz=7, nx=5, off=0.0018):
    """Under-layer patch visible in the crossed-collar V: between the two collar paths (front parts) from the
    apex height z0 to z1, lying just outside the torso surface (the collar bands hide its edges)."""
    def x_at(path, z):
        P = path[path[:, 1] < 0.0]
        order = np.argsort(P[:, 2])
        return float(np.interp(z, P[order, 2], P[order, 0]))
    rows = []
    for z in np.linspace(z0, z1, nz):
        xl, xr = x_at(path_l, z), x_at(path_r, z)
        row = []
        for u in np.linspace(0.0, 1.0, nx):
            x = xr + (xl - xr) * u
            row.append((x, torso_front_y(table, x, z) - off, z))
        rows.append(row)
    return fix_winding(grid(np.array(rows), wrap=False, mat=mat), [(0, 0, z0), (0, 0, z1)])


def build_shinobi(rig, col, D):
    """All SHINOBI body/costume objects (rigid segments + skinned torso/hakama/tails). Returns {name: obj}."""
    rr = RigRest(rig)
    M = shinobi_materials()
    out = {}
    K = {k: k for k in M}

    # ---------------- head (rigid) + neck
    hparts, hx = shinobi_head(rr, K)
    geo = Geo().add([_part_to_rig(rr, p) for p in hparts])
    out["SHINOBI_body_head"] = rigid_object("SHINOBI_body_head", geo, M, rig, "head", col)
    a, b = rr.h("neck") - rr.ax("neck")[1] * 0.03, rr.t("neck") + rr.ax("neck")[1] * 0.02
    geo = Geo().add(capsule(a, b, 0.054, 0.052, n=16, ring=2, zref=rr.ax("neck")[2], mat="mask"))
    out["SHINOBI_body_neck"] = rigid_object("SHINOBI_body_neck", geo, M, rig, "neck", col)

    # ---------------- torso jacket (skinned)
    T = SHINOBI_TORSO
    rows, th = torso_rings(T, n=36)
    torso = grid(rows, wrap=True, mat="cloth")
    fix_winding(torso, [(0, 0, 0.8), (0, 0, 1.5)])
    geo_t = Geo().add(torso)
    paths = {}
    for side in (1.0, -1.0):
        z_end = 0.96 if side > 0 else None
        path = _collar_path(T, side, 1.470, 1.245 if side > 0 else 1.262, z_end, -0.085, 0.055, 0.004)
        paths[side] = path
        w = np.full(len(path), 0.030)
        ups = [np.array((0.0, 0.0, 1.0)) for _ in path]
        n_ = [_unit((pp[0], pp[1] - 0.0, 0.0)) for pp in path]
        rb = ribbon(path, w, [np.cross(nn, _unit(path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]))
                                for i, nn in enumerate(n_)], thickness=0.007, mat="collar")
        geo_t.add(rb)
    geo_t.add(v_patch(T, paths[1.0], paths[-1.0], 1.25, 1.462, mat="under"))
    Vt = geo_t.V
    Wt = _torso_weights(Vt, rr)
    out["SHINOBI_torso"] = skinned_object("SHINOBI_torso", geo_t, M, rig, col, Wt)

    # ---------------- sash (rigid on hips): crimson obi, lower in front, flat knot at the back
    sash_T = [(z, hw, hd, cy, 2.4) for z, hw, hd, cy in
              ((0.948, 0.153, 0.110, -0.002), (0.965, 0.155, 0.112, -0.002), (1.010, 0.152, 0.109, -0.002),
               (1.028, 0.149, 0.106, -0.002))]
    srows, _ = torso_rings(sash_T, n=36)
    srows = srows.copy()
    srows[..., 2] += 0.016 * (srows[..., 1] / 0.11)          # higher at the back, lower in front
    sash = fix_winding(grid(srows, wrap=True, mat="sash"), [(0, 0, 0.8), (0, 0, 1.2)])
    geo_h = Geo().add(sash)
    kc = np.array((-0.03, 0.118, 1.004))
    geo_h.add(rbox(kc, (1, 0, 0), (0, 0, 1), (0, 1, 0), (0.085, 0.052, 0.028), e=3.0, nu=14, nv=6, mat="sash"))
    geo_h.add(rbox(kc + np.array((0.0, 0.012, 0.0)), (1, 0, 0), (0, 0, 1), (0, 1, 0), (0.032, 0.058, 0.02), e=3.0,
                   nu=10, nv=5, mat="sash"))
    out["SHINOBI_body_hips"] = rigid_object("SHINOBI_body_hips", geo_h, M, rig, "hips", col)

    # ---------------- arms (rigid; built on the left, right = mirror) + fists per side
    for side in ("L", "R"):
        sx = 1.0 if side == "L" else -1.0
        J, E = rr.h(f"upper_arm.{side}"), rr.t(f"upper_arm.{side}")
        Wr = rr.t(f"forearm.{side}")
        Mt = rr.h(f"forearm_twist.{side}")
        Xu, Yu, Zu = rr.ax(f"upper_arm.{side}")
        up_part = capsule(J + np.array((sx * 0.008, 0.0, -0.006)), E, 0.052, 0.046, n=14, ring=3, zref=Zu, flat=0.94,
                          mid=[(0.16, 0.056), (0.5, 0.051), (0.8, 0.047)], mat="cloth")
        out[f"SHINOBI_body_upper_arm.{side}"] = rigid_object(f"SHINOBI_body_upper_arm.{side}", Geo().add(up_part),
                                                            M, rig, f"upper_arm.{side}", col)
        Xf, Yf, Zf = rr.ax(f"forearm.{side}")
        fa = capsule(E, Mt + Yf * 0.012, 0.046, 0.044, n=14, ring=3, zref=Zf, flat=0.94, mat="cloth")
        cuff = loft([dict(c=Mt - Yf * 0.004, X=Xf, Z=Zf, rx=0.0485, rz=0.0465),
                     dict(c=Mt + Yf * 0.014, X=Xf, Z=Zf, rx=0.0485, rz=0.0465)], n=14, cap0=False, cap1=False,
                    mat="cloth")
        out[f"SHINOBI_body_forearm.{side}"] = rigid_object(f"SHINOBI_body_forearm.{side}", Geo().add(fa, cuff), M,
                                                          rig, f"forearm.{side}", col)
        # bracer (tekko) on the twist bone: flattened sleeve + dorsal plate + two cords
        Xt, Yt, Zt = rr.ax(f"forearm_twist.{side}")
        a0, a1 = Mt - Yt * 0.010, Wr + Yt * 0.016
        hZ = rr.ax(f"hand.{side}")[2]
        dors = _unit(-hZ - Yt * np.dot(-hZ, Yt))
        side_ax = np.cross(Yt, dors)
        st = []
        for t, r in ((0.0, 0.047), (0.35, 0.045), (0.75, 0.040), (1.0, 0.036)):
            st.append(dict(c=a0 + (a1 - a0) * t, X=dors, Z=side_ax, rx=r, rz=r * 0.9, e=2.2))
        br = loft(st, n=14, mat="guard")
        fix_winding(br, [a0, a1])
        plate_rows = []
        for t in np.linspace(0.1, 0.92, 6):
            c = a0 + (a1 - a0) * t
            r = np.interp(t, [0, 0.35, 0.75, 1.0], [0.047, 0.045, 0.040, 0.036]) + 0.0045
            row = []
            for ang in np.linspace(-1.0, 1.0, 7):
                row.append(c + dors * r * math.cos(ang) + side_ax * r * 0.9 * math.sin(ang))
            plate_rows.append(row)
        plate = fix_winding(grid(np.array(plate_rows), wrap=False, mat="guard"), [a0, a1])
        cords = []
        for t in (0.30, 0.86):
            c = a0 + (a1 - a0) * t
            r = np.interp(t, [0, 0.35, 0.75, 1.0], [0.047, 0.045, 0.040, 0.036]) + 0.002
            ring = [c + dors * r * math.cos(u) + side_ax * r * 0.9 * math.sin(u)
                    for u in np.linspace(0, 2 * math.pi, 16, endpoint=False)]
            cords.append(tube(ring, 0.0028, n=5, loop=True, mat="cord"))
        out[f"SHINOBI_body_forearm_twist.{side}"] = rigid_object(
            f"SHINOBI_body_forearm_twist.{side}", Geo().add(br, plate, cords), M, rig, f"forearm_twist.{side}", col)
        # fist + wrist ball
        fparts = fist_parts(rr, side, M, "glove", "glove", s=1.0)
        wb = ellipsoid(rr.h(f"hand.{side}") + rr.ax(f"hand.{side}")[1] * 0.004, *rr.ax(f"hand.{side}"),
                       (0.033, 0.030, 0.026), nu=12, nv=6, mat="glove")
        out[f"SHINOBI_body_hand.{side}"] = rigid_object(f"SHINOBI_body_hand.{side}", Geo().add(fparts, wb), M, rig,
                                                       f"hand.{side}", col)

    # ---------------- hakama (skinned, two D->circle leg tubes)
    geo_k = Geo()
    regions = []
    for side in ("L", "R"):
        pleat = (lambda ph, z: (0.045 * np.sin(5 * ph + 0.4) + 0.02 * np.sin(11 * ph)) * smoothstep(0.86, 0.62, z)
                 * smoothstep(0.34, 0.45, z))
        rows = leg_rings(rr, side, SHINOBI_HAKAMA, n=22, pleats=pleat)
        part = grid(rows, wrap=True, mat="hakama")
        fix_winding(part, [rr.h(f"thigh.{side}") + np.array((0, 0, 0.2)), rr.t(f"thigh.{side}"),
                           rr.t(f"shin.{side}")])
        n0 = sum(len(p.V) for p in geo_k.parts)
        geo_k.add(part)
        regions.append((side, np.arange(n0, n0 + len(part.V))))
    Vk = geo_k.V
    parts_w = []
    for side, ids in regions:
        V = Vk[ids]
        hj = rr.h(f"thigh.{side}")
        segs = [(np.array((0.0, 0.0, 1.04)), hj), (hj, rr.t(f"thigh.{side}")), (rr.h(f"shin.{side}"), rr.t(f"shin.{side}"))]
        W = chain_weights(V, rr, ["hips", f"thigh.{side}", f"shin.{side}"], blends=[0.14, 0.08], segs=segs)
        W = blend_weights(W, {"hips": np.ones(len(V))}, smoothstep(0.95, 0.99, V[:, 2]))
        parts_w.append((ids, W))
    Wk = merge_weights(parts_w, len(Vk))
    reg = np.zeros(len(Vk), dtype=np.int32)
    for side, ids in regions:
        reg[ids] = 0 if side == "L" else 1
    out["SHINOBI_hakama"] = skinned_object("SHINOBI_hakama", geo_k, M, rig, col, Wk, regions=reg)

    # ---------------- legs below the knee: shin wraps (rigid shin), tabi (foot/toe), ankle ball
    for side in ("L", "R"):
        sx = 1.0 if side == "L" else -1.0
        K0, A0 = rr.h(f"shin.{side}"), rr.t(f"shin.{side}")
        Xs, Ys, Zs = rr.ax(f"shin.{side}")

        def at_z(z):
            t = (K0[2] - z) / (K0[2] - A0[2])
            return K0 + (A0 - K0) * t
        st = []
        for z, r in ((0.405, 0.0), (0.404, 0.064), (0.400, 0.071), (0.388, 0.069), (0.340, 0.064), (0.260, 0.058),
                     (0.190, 0.052), (0.140, 0.049), (0.105, 0.048), (0.098, 0.043), (0.097, 0.0)):
            st.append(dict(c=at_z(z), X=Xs, Z=Zs, rx=r, rz=r * 0.96, e=2.0,
                           mod=(lambda th, i, z=z: 1.0 + 0.045 * (0.5 + 0.5 * np.sin(th * 1.0 + z * 150.0)) ** 3)
                           if 0.11 < z < 0.38 else None))
        wraps = loft(st, n=16, mat="wrap")
        fix_winding(wraps, [K0, A0])
        tie = [at_z(0.392) + (Xs * math.cos(u) + Zs * math.sin(u)) * 0.071 for u in np.linspace(0, 2 * math.pi, 18, endpoint=False)]
        out[f"SHINOBI_body_shin.{side}"] = rigid_object(f"SHINOBI_body_shin.{side}",
                                                       Geo().add(wraps, tube(tie, 0.003, n=5, loop=True, mat="cord")),
                                                       M, rig, f"shin.{side}", col)
        # tabi foot: loft heel -> ball along -y, flat sole at z = 0.003
        ank = rr.h(f"foot.{side}")
        ball = rr.t(f"foot.{side}")
        xc = lambda y: ank[0] + (ball[0] - ank[0]) * (ank[1] - y) / max(ank[1] - ball[1], 1e-6)   # noqa: E731
        fst = []
        for y, hw, top in ((0.068, 0.0, 0.030), (0.064, 0.020, 0.040), (0.050, 0.031, 0.072), (0.020, 0.035, 0.098),
                           (-0.020, 0.037, 0.090), (-0.070, 0.041, 0.066), (-0.110, 0.043, 0.050),
                           (-0.132, 0.043, 0.044), (-0.134, 0.0, 0.040)):
            zc = 0.5 * (top + 0.004)
            hh = 0.5 * (top - 0.004)
            fst.append(dict(c=np.array((xc(y), y, zc)), X=np.array((1.0, 0.0, 0.0)), Z=np.array((0.0, 0.0, 1.0)),
                            rx=hw, rz=hh if hw > 0 else 0.0, e=3.2))
        for d in fst:
            d["X"], d["Z"] = np.array((-1.0, 0.0, 0.0)), np.array((0.0, 0.0, 1.0))
        foot = loft(fst, n=14, mat="tabi")
        fix_winding(foot, [np.array((ank[0], 0.1, 0.03)), np.array((ball[0], -0.2, 0.03))])
        ankle = ellipsoid(ank + np.array((0.0, 0.004, 0.012)), (1, 0, 0), (0, 0, 1), (0, -1, 0), (0.043, 0.050, 0.046),
                          nu=14, nv=8, mat="tabi")
        out[f"SHINOBI_body_foot.{side}"] = rigid_object(f"SHINOBI_body_foot.{side}", Geo().add(foot, ankle), M, rig,
                                                       f"foot.{side}", col)
        med = -sx
        parts = []
        for off_x, hw, L_, h in ((med * 0.013, 0.012, 0.074, 0.030), (-med * 0.011, 0.020, 0.064, 0.028)):
            c0 = np.array((ball[0] + off_x, ball[1] + 0.012, 0.004 + h * 0.5))
            c1 = np.array((ball[0] + off_x, ball[1] - L_ + 0.012, 0.004 + h * 0.36))
            tst = [dict(c=c0, X=np.array((-1.0, 0, 0)), Z=np.array((0, 0, 1.0)), rx=hw, rz=h * 0.5, e=2.6),
                   dict(c=(c0 + c1) / 2, X=np.array((-1.0, 0, 0)), Z=np.array((0, 0, 1.0)), rx=hw * 0.98, rz=h * 0.45, e=2.6),
                   dict(c=c1 + np.array((0, 0.006, 0)), X=np.array((-1.0, 0, 0)), Z=np.array((0, 0, 1.0)), rx=hw * 0.8,
                        rz=h * 0.34, e=2.4),
                   dict(c=c1 - np.array((0, 0.006, 0)), X=np.array((-1.0, 0, 0)), Z=np.array((0, 0, 1.0)), rx=0.0, rz=0.0)]
            toe = loft(tst, n=12, cap0=True, mat="tabi")
            fix_winding(toe, [c0 + np.array((0, 0.05, 0)), c1 - np.array((0, 0.03, 0))])
            parts.append(toe)
        out[f"SHINOBI_body_toe.{side}"] = rigid_object(f"SHINOBI_body_toe.{side}", Geo().add(parts), M, rig,
                                                      f"toe.{side}", col)

    # ---------------- hachimaki tails (skinned ribbons along tail1.* / tail2.*)
    knot = _head_to_rig(rr, hx["knot"])
    geo_tl = Geo()
    tails = []
    for i, sx in ((1, 1.0), (2, -1.0)):
        chain = [f"tail{i}.{j}" for j in (1, 2, 3, 4)]
        pts = [knot + np.array((sx * 0.012, 0.004, -0.004))]
        for bn in chain:
            h_, t_ = rr.h(bn), rr.t(bn)
            for u in (0.33, 0.66, 1.0):
                pts.append(h_ + (t_ - h_) * u)
        pts[-1] = pts[-1] + _unit(pts[-1] - pts[-2]) * 0.02
        pts = np.array(pts)
        n_ = len(pts)
        widths = np.linspace(0.036, 0.031, n_)
        ups = [rr.ax(chain[min(max(k - 1, 0) // 3, 3)])[0] for k in range(n_)]
        rb = ribbon(pts, widths, ups, thickness=0.0042, mat="band")
        n0 = sum(len(p.V) for p in geo_tl.parts)
        geo_tl.add(rb)
        tails.append((i, chain, np.arange(n0, n0 + len(rb.V)), pts))
    Vtl = geo_tl.V
    pw = []
    for i, chain, ids, pts in tails:
        segs = [(pts[0] - (pts[1] - pts[0]) * 0.5, rr.h(chain[0]))] + [(rr.h(b_), rr.t(b_)) for b_ in chain]
        segs[-1] = (segs[-1][0], pts[-1] + (pts[-1] - pts[-2]))
        Vs = Vtl[ids]
        near = np.argmin(np.linalg.norm(Vs[:, None, :] - pts[None, :, :], axis=2), axis=1)
        W = chain_weights(pts[near], rr, ["head"] + chain, blends=[0.03, 0.04, 0.04, 0.04], segs=segs)
        pw.append((ids, W))
    Wtl = merge_weights(pw, len(Vtl))
    out["SHINOBI_hachimaki_tails"] = skinned_object("SHINOBI_hachimaki_tails", geo_tl, M, rig, col, Wtl, sharp=70)
    return out, M


# =============================================================================================
# Tenkosai - SAINT
# =============================================================================================
def saint_materials():
    """MESH_SAINT_* materials keyed by role (colours from config.PALETTE)."""
    M = {}
    warm = (0.55, 0.45, 0.36)
    M["kimono"] = mat_cloth("MESH_SAINT_kimono", PAL["saint_kimono"], rough=0.82, sheen=0.5, sheen_tint=warm)[0]
    M["juban"] = mat_cloth("MESH_SAINT_juban", (0.62, 0.60, 0.55), rough=0.8, sheen=0.4)[0]
    M["hakama"] = mat_cloth("MESH_SAINT_hakama", PAL["saint_hakama"], rough=0.85, sheen=0.45,
                            sheen_tint=(0.45, 0.45, 0.47))[0]
    M["himo"] = mat_cloth("MESH_SAINT_himo", (0.075, 0.075, 0.078), rough=0.8, sheen=0.4)[0]
    M["obi"] = mat_cloth("MESH_SAINT_obi", (0.035, 0.028, 0.022), rough=0.75, sheen=0.4)[0]
    m, nb, b = mat_cloth("MESH_SAINT_haori", PAL["saint_haori"], rough=0.82, sheen=0.5, sheen_tint=(0.7, 0.6, 0.4))
    attach_burn(m, nb, b)
    M["haori"] = m
    lc = tuple(c * 0.72 for c in PAL["saint_haori"])      # lining: the ochre, darker (folds stay unobtrusive)
    m, nb, b = mat_cloth("MESH_SAINT_haori_lining", lc, rough=0.85, sheen=0.3)
    attach_burn(m, nb, b)
    M["lining"] = m
    m, nb, b = mat_cloth("MESH_SAINT_haori_collar", (0.24, 0.15, 0.045), rough=0.8, sheen=0.45,
                         sheen_tint=(0.7, 0.6, 0.4))
    attach_burn(m, nb, b)
    M["haori_collar"] = m
    m, nb, b = mat_cloth("MESH_SAINT_crest", (0.80, 0.78, 0.70), rough=0.75, sheen=0.35, slub=0.03, mottle=0.04)
    attach_burn(m, nb, b)
    M["crest"] = m
    m, nb, b = mat_cloth("MESH_SAINT_haori_himo", (0.72, 0.68, 0.58), rough=0.7, sheen=0.4)
    attach_burn(m, nb, b)
    M["haori_himo"] = m
    M["skin"] = mat_skin("MESH_SAINT_skin", PAL["saint_skin"], mottle=0.16)
    M["scar"] = mat_skin("MESH_SAINT_scar", (0.56, 0.36, 0.30), rough=0.38, mottle=0.08)
    M["hair"] = mat_hair("MESH_SAINT_beard", PAL["saint_beard"], rough=0.52, streak=0.3, sheen=0.55)
    M["eye"] = mat_simple("MESH_SAINT_sclera", (0.50, 0.46, 0.40), rough=0.3, coat=0.8, coat_rough=0.03, wet=False)
    M["iris"] = mat_eye("MESH_SAINT_iris", iris=(0.028, 0.02, 0.016))
    M["pupil"] = mat_eye("MESH_SAINT_pupil", iris=(0.004, 0.003, 0.003))
    M["glint"] = mat_glint("MESH_SAINT_eye_glint")
    M["tabi"] = mat_cloth("MESH_SAINT_tabi", (0.70, 0.68, 0.63), rough=0.8, sheen=0.35)[0]
    M["zori"] = mat_straw("MESH_SAINT_zori", (0.42, 0.32, 0.17))
    M["hanao"] = mat_cloth("MESH_SAINT_hanao", (0.05, 0.035, 0.03), rough=0.7, sheen=0.4)[0]
    return M


SAINT_HEAD = [
    (-0.055, 0.030, 0.078, 0.020, 0.030), (-0.042, 0.050, 0.098, 0.034, 0.022), (-0.022, 0.064, 0.106, 0.055, 0.012),
    (0.000, 0.072, 0.108, 0.072, 0.006), (0.025, 0.078, 0.108, 0.086, 0.002), (0.050, 0.082, 0.108, 0.096, 0.000),
    (0.078, 0.085, 0.108, 0.103, 0.000), (0.105, 0.087, 0.108, 0.106, 0.000), (0.135, 0.087, 0.104, 0.107, 0.000),
    (0.165, 0.081, 0.094, 0.101, 0.000), (0.192, 0.067, 0.076, 0.084, 0.000), (0.212, 0.046, 0.051, 0.057, 0.000),
    (0.223, 0.024, 0.026, 0.030, 0.000),
]
SAINT_SCULPT = [
    ((0.034, 0.090, 0.10), (0.020, 0.014, 0.02), -0.016), ((-0.034, 0.090, 0.10), (0.020, 0.014, 0.02), -0.016),
    ((0.034, 0.108, 0.105), (0.030, 0.011, 0.02), 0.011), ((-0.034, 0.108, 0.105), (0.030, 0.011, 0.02), 0.011),
    ((0.0, 0.104, 0.108), (0.012, 0.010, 0.02), 0.005),
    ((0.0, 0.085, 0.108), (0.011, 0.022, 0.02), 0.014), ((0.0, 0.054, 0.110), (0.018, 0.016, 0.02), 0.028),
    ((0.018, 0.049, 0.10), (0.011, 0.010, 0.02), 0.008), ((-0.018, 0.049, 0.10), (0.011, 0.010, 0.02), 0.008),
    ((0.057, 0.073, 0.085), (0.020, 0.014, 0.02), 0.008), ((-0.057, 0.073, 0.085), (0.020, 0.014, 0.02), 0.008),
    ((0.052, 0.045, 0.085), (0.016, 0.016, 0.02), -0.006), ((-0.052, 0.045, 0.085), (0.016, 0.016, 0.02), -0.006),
    ((0.080, 0.115, 0.040), (0.020, 0.020, 0.02), -0.005), ((-0.080, 0.115, 0.040), (0.020, 0.020, 0.02), -0.005),
    ((0.0, -0.032, 0.105), (0.022, 0.014, 0.02), 0.006), ((0.0, 0.120, -0.105), (0.040, 0.040, 0.03), 0.005),
    ((0.0, 0.132, 0.106), (0.045, 0.0028, 0.02), -0.0018), ((0.0, 0.143, 0.104), (0.040, 0.0028, 0.02), -0.0016),
    ((0.006, 0.102, 0.110), (0.0025, 0.010, 0.02), -0.0025), ((-0.006, 0.102, 0.110), (0.0025, 0.010, 0.02), -0.0025),
]


def saint_head(rr, K):
    """SAINT head (rigid on 'head'), head frame: bald skin head with a faint scar, deep-set eyes + glint discs,
    bushy grey brows, big ears with long lobes, drooping moustache. The beard is a separate skinned mesh."""
    hs = HeadShape(SAINT_HEAD, SAINT_SCULPT, n=30, top=(0.0, 0.2275, 0.0), bottom=(0.0, -0.058, 0.03))
    parts = [hs.part(mat=K["skin"])]
    EY = (K["eye"], K["iris"], K["pupil"])
    r = 0.0134
    glints = []
    for side in (1.0, -1.0):
        p, nv = surface_front(hs, 0.034 * side, 0.090)
        c = p - nv * (r - 0.0030)
        parts += eye_parts(c, r, EY, K["skin"], K["hair"], open_up=0.24, open_dn=0.36, tilt=0.26, side=side,
                           lid_thick=0.0030)
        gd = _unit((side * -0.25, 0.30, 1.0))
        glints.append(sphere_cap(c, r * 1.045, gd, 0.15, n=8, rings=2, mat=K["glint"]))
        # thick grey brows: heavy base + short clumps sweeping outward, drooping at the outer end
        base = []
        for t in np.linspace(0.0, 1.0, 7):
            x = side * (0.008 + 0.052 * t)
            q, qn = surface_front(hs, x, 0.1065 + 0.005 * t - 0.009 * t * t)
            base.append(q + qn * 0.0045)
        parts.append(ribbon(base, np.linspace(0.017, 0.010, 7), (0.0, 1.0, 0.3), thickness=0.009, mat=K["hair"]))
        for k, t in enumerate(np.linspace(0.02, 1.0, 6)):
            q = base[int(round(t * 6))]
            d = _unit((side * (0.55 + 0.45 * t), 0.20 - 0.60 * t, 0.55))
            parts.append(spike(q - d * 0.005, d, 0.014 + 0.005 * math.sin(k * 2.1), 0.0068, n=4, mat=K["hair"],
                               bend=(0.0, -0.5, 0.0)))
        # ears + long lobes
        ear_c = np.array((0.0855 * side, 0.082, -0.006))
        ea = _unit((side * 0.2, 0.0, -1.0))
        ex = _unit(np.cross((0, 1, 0), ea)) * side
        parts.append(ellipsoid(ear_c, ex, (0.0, 1.0, 0.0), ea, (0.0065, 0.032, 0.019), nu=10, nv=6, mat=K["skin"]))
        parts.append(ellipsoid(ear_c + np.array((-0.001 * side, -0.036, 0.004)), ex, (0.0, 1.0, 0.0), ea,
                               (0.0058, 0.014, 0.011), nu=8, nv=5, mat=K["skin"]))
        # moustache strand
        pts = [np.array((0.004 * side, 0.041, 0.121)), np.array((0.020 * side, 0.037, 0.119)),
               np.array((0.035 * side, 0.025, 0.110)), np.array((0.043 * side, 0.004, 0.102)),
               np.array((0.045 * side, -0.020, 0.098))]
        pts = catmull(pts, 3)
        rad = np.linspace(0.0085, 0.004, len(pts))
        parts.append(loft(stations_along(pts, [(r_ * 1.3, r_) for r_ in rad], (0.0, 0.0, 1.0)), n=7, cap0=True,
                          cap1=True, mat=K["hair"]))
    # scar over the left crown (faint, slightly raised)
    sc = []
    for th, y in ((math.radians(62), 0.176), (math.radians(40), 0.192), (math.radians(12), 0.200),
                  (math.radians(-18), 0.196), (math.radians(-42), 0.182)):
        j = int(round((th + math.pi / 2) / (2 * math.pi) * hs.n)) % hs.n
        q, qn = hs.column_at(j, y)
        sc.append(q + qn * 0.0009)
    sc = catmull(sc, 3)
    parts.append(ribbon(sc, 0.0048 * np.sin(np.linspace(0.15, math.pi - 0.15, len(sc))) + 0.0012,
                        [_unit(q) for q in sc], thickness=0.0016, mat=K["scar"]))
    return parts, glints, hs


def saint_beard(rr, hs, K):
    """Long grey beard (skinned: jaw shell + moustache region -> head; long beard -> beard.1..3), gathered by the
    vermilion cord at 45 % of beard.3 and flaring into a short tuft below it. Returns (Geo, weights)."""
    geo = Geo()
    # jaw shell (head frame): sideburns in front of the ears, over the cheeks/jaw/chin, open at the back
    cols = [j for j in range(hs.n) if math.radians(12) <= hs.theta[j] <= math.radians(168)]

    def y_top(th):
        d = abs(th - math.pi / 2)
        return float(np.interp(d, [0.0, 0.35, 0.75, 1.2, 1.4], [0.018, 0.028, 0.050, 0.086, 0.094]))
    rows = []
    th_lo, th_hi = hs.theta[cols[0]], hs.theta[cols[-1]]
    for t in np.linspace(0.0, 1.0, 8):
        row = []
        for j in cols:
            th = hs.theta[j]
            y = y_top(th) + (-0.050 - y_top(th)) * t
            q, qn = hs.column_at(j, y)
            edge = min(1.0, min(th - th_lo, th_hi - th) / 0.30)       # side edges meet the skin (no dark gap)
            thick = (0.006 + 0.010 * t + 0.004 * math.sin(t * math.pi)) * (0.15 + 0.85 * edge)
            row.append(q + qn * thick)
        rows.append(row)
    shell = grid(np.array(rows)[::-1], wrap=False, mat=K["hair"])
    shell = fix_winding(shell, [(0.0, -0.1, 0.0), (0.0, 0.2, 0.0)])
    shell_rig = _part_to_rig(rr, shell)
    n_shell = len(shell_rig.V)
    geo.add(shell_rig)
    # long beard loft along the chain (rig space)
    chain = ["beard.1", "beard.2", "beard.3"]
    b1h = rr.h("beard.1")
    X1, Y1, Z1 = rr.ax("beard.1")
    start = b1h - Y1 * 0.035 - Z1 * 0.012
    pts, rad = [start], [(0.064, 0.030)]
    prof = {"beard.1": [(0.3, (0.056, 0.030)), (0.7, (0.047, 0.027)), (1.0, (0.041, 0.025))],
            "beard.2": [(0.35, (0.033, 0.022)), (0.7, (0.026, 0.019)), (1.0, (0.021, 0.016))],
            "beard.3": [(0.25, (0.016, 0.0135)), (0.45, (0.0115, 0.0105)), (0.62, (0.015, 0.012)),
                        (0.85, (0.013, 0.010)), (1.08, (0.0, 0.0))]}
    for bn in chain:
        h_, t_ = rr.h(bn), rr.t(bn)
        for u, r_ in prof[bn]:
            pts.append(h_ + (t_ - h_) * u)
            rad.append(r_)
    pts = np.array(pts)
    st = []
    for i, p_ in enumerate(pts):
        tdir = pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]
        X, Y, Z = frame_yz(tdir, (0.0, -1.0, 0.0))
        rx, rz = rad[i]
        ph = i * 0.7
        st.append(dict(c=p_, X=X, Z=Z, rx=rx, rz=rz, e=2.2,
                       mod=(lambda th, si, ph=ph: 1.0 + 0.07 * np.sin(7 * th + ph) + 0.03 * np.sin(13 * th))))
    beard = loft(st, n=18, cap0=False, mat=K["hair"])
    fix_winding(beard, pts)
    geo.add(beard)
    V = geo.V
    n = len(V)
    W_head = {"head": np.ones(n_shell)}
    segs = [(start - (pts[1] - start) * 0.5, b1h)] + [(rr.h(b), rr.t(b)) for b in chain]
    segs[-1] = (segs[-1][0], pts[-1] + (pts[-1] - pts[-2]))
    Wb = chain_weights(V[n_shell:], rr, ["head"] + chain, blends=[0.03, 0.045, 0.04, 0.035], segs=segs)
    W = merge_weights([(np.arange(n_shell), W_head), (np.arange(n_shell, n), Wb)], n)
    return geo, W


SAINT_SPINE_Y = ([0.90, 1.0, 1.263, 1.527, 1.623], [0.0, 0.0, -0.006, -0.052, -0.099])
SAINT_TORSO_ROWS = [   # (z, half-width, half-depth, extra y, e) ; centre y = spine y(z) + extra (stoop)
    (0.960, 0.180, 0.128, 0.004, 2.3), (1.050, 0.176, 0.126, 0.000, 2.3), (1.150, 0.180, 0.128, -0.004, 2.4),
    (1.250, 0.190, 0.133, -0.008, 2.5), (1.330, 0.200, 0.134, -0.006, 2.6), (1.410, 0.207, 0.130, -0.002, 2.7),
    (1.470, 0.213, 0.122, 0.000, 2.8), (1.515, 0.214, 0.110, 0.004, 2.8), (1.545, 0.192, 0.098, 0.008, 2.6),
    (1.568, 0.142, 0.086, 0.010, 2.3), (1.588, 0.092, 0.077, 0.010, 2.0), (1.603, 0.079, 0.072, 0.008, 2.0),
]


def saint_torso_table():
    return [(z, hw, hd, float(np.interp(z, *SAINT_SPINE_Y)) + ex, e) for z, hw, hd, ex, e in SAINT_TORSO_ROWS]


SAINT_HAKAMA = [    # per leg: (z, k, waist hw, waist hd, leg radius, e)
    (1.112, 0.00, 0.186, 0.136, 0.16, 2.4), (1.060, 0.00, 0.194, 0.141, 0.16, 2.4),
    (1.000, 0.05, 0.207, 0.149, 0.160, 2.4), (0.920, 0.25, 0.226, 0.158, 0.172, 2.4),
    (0.840, 0.55, 0.240, 0.165, 0.177, 2.4), (0.760, 0.85, 0.250, 0.170, 0.180, 2.4),
    (0.680, 1.00, 0.1, 0.1, 0.182, 2.0), (0.560, 1.0, 0.1, 0.1, 0.185, 2.0), (0.440, 1.0, 0.1, 0.1, 0.188, 2.0),
    (0.320, 1.0, 0.1, 0.1, 0.190, 2.0), (0.200, 1.0, 0.1, 0.1, 0.192, 2.0), (0.110, 1.0, 0.1, 0.1, 0.192, 2.0),
    (0.078, 1.0, 0.1, 0.1, 0.190, 2.0),
]


def _collar_path_saint(table, side, z_top, z_apex, z_end, x_end, off, inset=0.0):
    """Kimono eri path (back of the neck -> shoulder -> down the front to the V apex -> diagonal)."""
    T = np.array(table)
    cy_top = float(np.interp(z_top, T[:, 0], T[:, 3]))
    pts = [np.array((0.0, cy_top + 0.070, z_top - 0.006)),
           np.array((side * 0.062, cy_top + 0.030, z_top)),
           np.array((side * 0.076, cy_top - 0.030, z_top - 0.016))]
    for t in np.linspace(0.0, 1.0, 7):
        z = z_top - 0.045 - (z_top - 0.045 - z_apex) * t
        x = side * ((0.072 - inset) * (1.0 - t) ** 1.1) + (-side) * 0.006 * t
        pts.append(np.array((x, torso_front_y(table, x, z) - off, z)))
    if z_end is not None:
        for t in np.linspace(0.2, 1.0, 5):
            z = z_apex - (z_apex - z_end) * t
            x = x_end * t
            pts.append(np.array((x, torso_front_y(table, x, z) - off, z)))
    return catmull(pts, 4)


def _band_on_torso(table, path, width, thick, mat):
    """Ribbon lying on the torso surface along `path` (width direction perpendicular to the path and the
    surface normal)."""
    T = np.array(table)
    ups = []
    for i, pp in enumerate(path):
        cy = float(np.interp(pp[2], T[:, 0], T[:, 3]))
        nn = _unit((pp[0], pp[1] - cy, 0.0))
        tg = _unit(path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)])
        ups.append(np.cross(nn, tg))
    return ribbon(path, np.full(len(path), width), ups, thickness=thick, mat=mat)


def build_saint_body(rig, col, D, M):
    """SAINT body + costume except the haori/props: head, beard, neck, kimono torso (skinned), tied-back sleeves,
    bare forearms, fists, wide pleated hakama (skinned), obi/himo/koshi-ita, white tabi + zori."""
    rr = RigRest(rig)
    s = rr.s
    K = {k: k for k in M}
    out = {}
    # ---------------- head + glint (rigid) + beard (skinned) + neck
    hparts, glints, hs = saint_head(rr, K)
    geo = Geo().add([_part_to_rig(rr, p) for p in hparts]).add([_part_to_rig(rr, g) for g in glints])
    out["SAINT_body_head"] = rigid_object("SAINT_body_head", geo, M, rig, "head", col)
    gb, Wb = saint_beard(rr, hs, K)
    out["SAINT_beard"] = skinned_object("SAINT_beard", gb, M, rig, col, Wb, sharp=80)
    a, b = rr.h("neck") - rr.ax("neck")[1] * 0.04, rr.t("neck") + rr.ax("neck")[1] * 0.02
    geo = Geo().add(capsule(a, b, 0.066, 0.062, n=16, ring=2, zref=rr.ax("neck")[2], mat="skin"))
    out["SAINT_body_neck"] = rigid_object("SAINT_body_neck", geo, M, rig, "neck", col)

    # ---------------- kimono torso (skinned) + crossed eri (left over right) + juban stripe + V patch
    T = saint_torso_table()
    rows, _ = torso_rings(T, n=40)
    torso = fix_winding(grid(rows, wrap=True, mat="kimono"), [(0, 0, 0.9), (0, -0.05, 1.6)])
    geo_t = Geo().add(torso)
    paths = {}
    for side in (1.0, -1.0):
        z_end = 1.06 if side > 0 else None
        paths[side] = _collar_path_saint(T, side, 1.600, 1.315 if side > 0 else 1.335, z_end, -0.11, 0.0065)
        jp = _collar_path_saint(T, side, 1.598, 1.330 if side > 0 else 1.345, None, 0.0, 0.0030, inset=0.020)
        geo_t.add(_band_on_torso(T, jp, 0.034, 0.005, "juban"))
        geo_t.add(_band_on_torso(T, paths[side], 0.046, 0.010, "kimono"))
    geo_t.add(v_patch(T, paths[1.0], paths[-1.0], 1.31, 1.585, mat="skin", off=0.0012))
    Vt = geo_t.V
    Wt = _arm_blend(Vt, _torso_weights(Vt, rr, sh_x=(0.09, 0.19), sh_z=(1.42, 1.51), lo=0.90))
    out["SAINT_torso"] = skinned_object("SAINT_torso", geo_t, M, rig, col, Wt)

    # ---------------- arms: tied-back kimono sleeve (bunched) + bare arm, forearms, fists
    for side in ("L", "R"):
        sx = 1.0 if side == "L" else -1.0
        J, E = rr.h(f"upper_arm.{side}"), rr.t(f"upper_arm.{side}")
        Wr = rr.t(f"forearm.{side}")
        Mt = rr.h(f"forearm_twist.{side}")
        Xu, Yu, Zu = rr.ax(f"upper_arm.{side}")
        arm = capsule(J + np.array((sx * 0.004, 0.0, -0.010)), E, 0.053, 0.050, n=14, ring=3, zref=Zu, flat=0.95,
                      mid=[(0.4, 0.057)], mat="skin")
        Ls = np.linalg.norm(E - J)
        st = []
        for t, r in ((0.08, 0.0), (0.09, 0.050), (0.14, 0.064), (0.22, 0.071), (0.40, 0.072), (0.56, 0.070),
                     (0.66, 0.065), (0.70, 0.059), (0.705, 0.0)):
            st.append(dict(c=J + Yu * (Ls * t) + np.array((0.0, 0.0, -0.004)), X=Xu, Z=Zu, rx=r, rz=r * 0.96,
                           mod=(lambda th, i: 1.0 + 0.045 * np.sin(5 * th + i) + 0.02 * np.sin(9 * th + 2 * i))
                           if 0.1 < t < 0.7 else None))
        sleeve = fix_winding(loft(st, n=16, mat="kimono"), [J - Yu * 0.1, E])
        rim = [J + Yu * (Ls * 0.68) + (Xu * math.cos(u) + Zu * math.sin(u)) * 0.066
               for u in np.linspace(0, 2 * math.pi, 18, endpoint=False)]
        out[f"SAINT_body_upper_arm.{side}"] = rigid_object(
            f"SAINT_body_upper_arm.{side}", Geo().add(arm, sleeve, tube(rim, 0.006, n=5, loop=True, mat="kimono")),
            M, rig, f"upper_arm.{side}", col)
        Xf, Yf, Zf = rr.ax(f"forearm.{side}")
        fa = capsule(E, Mt + Yf * 0.02, 0.050, 0.047, n=14, ring=3, zref=Zf, flat=0.9, mid=[(0.3, 0.052)],
                     mat="skin")
        out[f"SAINT_body_forearm.{side}"] = rigid_object(f"SAINT_body_forearm.{side}", Geo().add(fa), M, rig,
                                                        f"forearm.{side}", col)
        Xt, Yt, Zt = rr.ax(f"forearm_twist.{side}")
        ft = capsule(Mt - Yt * 0.01, Wr, 0.047, 0.037, n=14, ring=3, zref=Zt, flat=0.82, mat="skin")
        out[f"SAINT_body_forearm_twist.{side}"] = rigid_object(f"SAINT_body_forearm_twist.{side}", Geo().add(ft), M,
                                                              rig, f"forearm_twist.{side}", col)
        fparts = fist_parts(rr, side, M, "skin", "skin", s=s, chunky=1.08)
        wb = ellipsoid(rr.h(f"hand.{side}") + rr.ax(f"hand.{side}")[1] * 0.004, *rr.ax(f"hand.{side}"),
                       (0.036, 0.032, 0.028), nu=12, nv=6, mat="skin")
        out[f"SAINT_body_hand.{side}"] = rigid_object(f"SAINT_body_hand.{side}", Geo().add(fparts, wb), M, rig,
                                                     f"hand.{side}", col)

    # ---------------- hakama (skinned): wide pleated legs
    geo_k = Geo()
    regions = []
    for side in ("L", "R"):
        pleat = (lambda ph, z: (0.055 * (np.abs(np.sin(2.5 * ph + 0.3)) - 0.55) + 0.015 * np.sin(9 * ph))
                 * smoothstep(1.06, 0.85, z))
        rows = leg_rings(rr, side, SAINT_HAKAMA, n=28, pleats=pleat)
        part = fix_winding(grid(rows, wrap=True, mat="hakama"),
                           [rr.h(f"thigh.{side}") + np.array((0, 0, 0.2)), rr.t(f"thigh.{side}"), rr.t(f"shin.{side}")])
        n0 = sum(len(p_.V) for p_ in geo_k.parts)
        geo_k.add(part)
        regions.append((side, np.arange(n0, n0 + len(part.V))))
    Vk = geo_k.V
    parts_w = []
    for side, ids in regions:
        V = Vk[ids]
        hj = rr.h(f"thigh.{side}")
        segs = [(np.array((0.0, 0.0, 1.14)), hj), (hj, rr.t(f"thigh.{side}")), (rr.h(f"shin.{side}"), rr.t(f"shin.{side}"))]
        W = chain_weights(V, rr, ["hips", f"thigh.{side}", f"shin.{side}"], blends=[0.14, 0.12], segs=segs)
        W = blend_weights(W, {"hips": np.ones(len(V))}, smoothstep(1.02, 1.07, V[:, 2]))
        parts_w.append((ids, W))
    Wk = merge_weights(parts_w, len(Vk))
    reg = np.zeros(len(Vk), dtype=np.int32)
    for side, ids in regions:
        reg[ids] = 0 if side == "L" else 1
    out["SAINT_hakama"] = skinned_object("SAINT_hakama", geo_k, M, rig, col, Wk, regions=reg)

    # ---------------- hips (rigid): obi strip above the hakama, himo band + front knot, koshi-ita at the back
    ob_T = [(1.080, 0.197, 0.143, 0.000, 2.4), (1.118, 0.192, 0.139, 0.000, 2.4), (1.140, 0.189, 0.137, 0.0, 2.4)]
    obi = fix_winding(grid(torso_rings(ob_T, n=36)[0], wrap=True, mat="obi"), [(0, 0, 1.0), (0, 0, 1.2)])
    hm_T = [(1.078, 0.203, 0.149, 0.000, 2.4), (1.096, 0.203, 0.149, 0.000, 2.4)]
    himo = fix_winding(grid(torso_rings(hm_T, n=36)[0], wrap=True, mat="himo"), [(0, 0, 1.0), (0, 0, 1.2)])
    knot = rbox(np.array((0.0, -0.152, 1.086)), (1, 0, 0), (0, 0, 1), (0, -1, 0), (0.060, 0.030, 0.016), e=3.0,
                nu=12, nv=5, mat="himo")
    kp = []
    for z, hw in ((1.07, 0.105), (1.13, 0.095), (1.19, 0.078)):
        row = []
        for x in np.linspace(-hw, hw, 7):
            u = min(abs(x) / 0.214, 0.99)
            yb = 0.150 * (1.0 - u ** 2.4) ** (1 / 2.4) + 0.006
            row.append((x, yb, z))
        kp.append(row)
    koshi = fix_winding(grid(np.array(kp), wrap=False, mat="hakama"), [(0, 0, 1.0), (0, 0, 1.3)])
    out["SAINT_body_hips"] = rigid_object("SAINT_body_hips", Geo().add(obi, himo, knot, koshi), M, rig, "hips", col)

    # ---------------- legs: under-leggings (safety under the hakama), white tabi, zori
    for side in ("L", "R"):
        sx = 1.0 if side == "L" else -1.0
        K0, A0 = rr.h(f"shin.{side}"), rr.t(f"shin.{side}")
        Zs = rr.ax(f"shin.{side}")[2]
        sh = capsule(K0, A0 + (A0 - K0) * 0.02, 0.066, 0.050, n=12, ring=2, zref=Zs, mat="juban")
        out[f"SAINT_body_shin.{side}"] = rigid_object(f"SAINT_body_shin.{side}", Geo().add(sh), M, rig,
                                                     f"shin.{side}", col)
        ank, ball = rr.h(f"foot.{side}"), rr.t(f"foot.{side}")
        xc = lambda y: ank[0] + (ball[0] - ank[0]) * (ank[1] - y) / max(ank[1] - ball[1], 1e-6)   # noqa: E731
        fst = []
        for y, hw, top in ((0.074, 0.0, 0.040), (0.070, 0.022, 0.050), (0.056, 0.034, 0.080), (0.022, 0.038, 0.106),
                           (-0.020, 0.040, 0.098), (-0.075, 0.045, 0.072), (-0.118, 0.047, 0.056),
                           (-0.144, 0.047, 0.050), (-0.146, 0.0, 0.046)):
            zc = 0.5 * (top + 0.016)
            hh = 0.5 * (top - 0.016)
            fst.append(dict(c=np.array((xc(y), y, zc)), X=np.array((-1.0, 0.0, 0.0)), Z=np.array((0.0, 0.0, 1.0)),
                            rx=hw, rz=hh if hw > 0 else 0.0, e=3.2))
        foot = fix_winding(loft(fst, n=14, mat="tabi"), [np.array((ank[0], 0.1, 0.04)), np.array((ball[0], -0.2, 0.04))])
        ankle = ellipsoid(ank + np.array((0.0, 0.004, 0.014)), (1, 0, 0), (0, 0, 1), (0, -1, 0), (0.047, 0.056, 0.050),
                          nu=14, nv=8, mat="tabi")
        sole = []
        for y, hw in ((0.084, 0.0), (0.080, 0.030), (0.060, 0.046), (0.0, 0.050), (-0.080, 0.054), (-0.128, 0.054)):
            sole.append(dict(c=np.array((xc(y), y, 0.009)), X=np.array((-1.0, 0.0, 0.0)), Z=np.array((0.0, 0.0, 1.0)),
                             rx=hw, rz=0.008 if hw > 0 else 0.0, e=6.0))
        sole = fix_winding(loft(sole, n=16, cap1=True, mat="zori"), [np.array((ank[0], 0.1, 0.0)),
                                                                     np.array((ball[0], -0.2, 0.0))])
        # hanao (thong): from between the toes (front) to both sides of the foot
        tp = np.array((xc(-0.13) - sx * 0.014, -0.128, 0.03))
        straps = []
        for sgn in (1.0, -1.0):
            q1 = np.array((xc(-0.035) + sgn * 0.044, -0.035, 0.022))
            mid = np.array((xc(-0.08) + sgn * 0.030, -0.085, 0.066))
            straps.append(tube(catmull([tp, mid, q1], 4), 0.0055, n=6, mat="hanao"))
        out[f"SAINT_body_foot.{side}"] = rigid_object(f"SAINT_body_foot.{side}", Geo().add(foot, ankle, sole, straps),
                                                     M, rig, f"foot.{side}", col)
        med = -sx
        tparts = []
        for off_x, hw, L_, h in ((med * 0.014, 0.013, 0.080, 0.032), (-med * 0.012, 0.022, 0.070, 0.030)):
            c0 = np.array((ball[0] + off_x, ball[1] + 0.012, 0.016 + h * 0.5))
            c1 = np.array((ball[0] + off_x, ball[1] - L_ + 0.012, 0.016 + h * 0.36))
            X_, Z_ = np.array((-1.0, 0, 0)), np.array((0, 0, 1.0))
            tst = [dict(c=c0, X=X_, Z=Z_, rx=hw, rz=h * 0.5, e=2.6),
                   dict(c=(c0 + c1) / 2, X=X_, Z=Z_, rx=hw * 0.98, rz=h * 0.45, e=2.6),
                   dict(c=c1 + np.array((0, 0.006, 0)), X=X_, Z=Z_, rx=hw * 0.8, rz=h * 0.34, e=2.4),
                   dict(c=c1 - np.array((0, 0.006, 0)), X=X_, Z=Z_, rx=0.0, rz=0.0)]
            tparts.append(fix_winding(loft(tst, n=12, cap0=True, mat="tabi"),
                                      [c0 + np.array((0, 0.05, 0)), c1 - np.array((0, 0.03, 0))]))
        ts = []
        for y, hw in ((ball[1] + 0.016, 0.054), (ball[1] - 0.03, 0.050), (ball[1] - 0.068, 0.036),
                      (ball[1] - 0.074, 0.0)):
            ts.append(dict(c=np.array((ball[0], y, 0.009)), X=np.array((-1.0, 0.0, 0.0)), Z=np.array((0.0, 0.0, 1.0)),
                           rx=hw, rz=0.008 if hw > 0 else 0.0, e=6.0))
        tparts.append(fix_winding(loft(ts, n=16, cap0=True, mat="zori"),
                                  [np.array((ball[0], 0.0, 0.0)), np.array((ball[0], -0.3, 0.0))]))
        out[f"SAINT_body_toe.{side}"] = rigid_object(f"SAINT_body_toe.{side}", Geo().add(tparts), M, rig,
                                                    f"toe.{side}", col)
    return out


HAORI_ROWS = [   # (z, half-width, half-depth, extra y, e, front half-gap)
    (1.600, 0.092, 0.084, 0.012, 2.0, 0.060), (1.580, 0.154, 0.100, 0.012, 2.2, 0.064),
    (1.555, 0.214, 0.119, 0.010, 2.5, 0.068), (1.524, 0.248, 0.137, 0.010, 2.8, 0.070),
    (1.470, 0.246, 0.149, 0.008, 2.8, 0.070), (1.400, 0.236, 0.156, 0.008, 2.7, 0.068),
    (1.320, 0.230, 0.159, 0.010, 2.6, 0.068), (1.230, 0.231, 0.162, 0.012, 2.5, 0.070),
    (1.140, 0.238, 0.168, 0.014, 2.5, 0.072), (1.060, 0.252, 0.174, 0.016, 2.5, 0.075),
    (0.960, 0.274, 0.184, 0.018, 2.5, 0.079), (0.860, 0.291, 0.194, 0.020, 2.5, 0.083),
    (0.760, 0.301, 0.202, 0.022, 2.5, 0.087), (0.660, 0.308, 0.208, 0.024, 2.5, 0.091),
    (0.575, 0.312, 0.212, 0.026, 2.5, 0.094),
]


def haori_table():
    return [(z, hw, hd, float(np.interp(z, *SAINT_SPINE_Y)) + ex, e, g) for z, hw, hd, ex, e, g in HAORI_ROWS]


def haori_body_rows(table, ncol=44, inset=0.0):
    """Open-front coat rows (rows, ncol, 3): columns run from the LEFT front edge around the back to the RIGHT
    front edge (superellipse rings; `inset` shrinks the ring = lining)."""
    rows = []
    for z, hw, hd, cy, e, g in table:
        hw_, hd_ = hw - inset, hd - inset
        sd = min((g / hw_) ** (e / 2.0), 0.999)
        d = math.asin(sd)
        th = np.linspace(1.5 * math.pi + d, 3.5 * math.pi - d, ncol)
        cx, sy = superellipse(th, e)
        rows.append(np.stack([hw_ * cx, cy + hd_ * sy, np.full(ncol, z)], axis=1))
    return np.array(rows)


def _haori_back_point(table, x, z, off):
    T = np.array([r[:5] for r in table])
    hw = np.interp(z, T[::-1, 0], T[::-1, 1])
    hd = np.interp(z, T[::-1, 0], T[::-1, 2])
    cy = np.interp(z, T[::-1, 0], T[::-1, 3])
    e = np.interp(z, T[::-1, 0], T[::-1, 4])
    u = min(abs(x) / hw, 0.999)
    y = cy + hd * (1.0 - u ** e) ** (1.0 / e)
    nrm = _unit((np.sign(x) * (u ** (e - 1)) / hw if x != 0 else 0.0, (1.0 - u ** e) ** ((e - 1) / e) / hd, 0.0))
    return np.array((x, y, z)) + nrm * off


def _qstroke(p0, p1, p2, w0, w1, m=16):
    """Quadratic Bezier stroke p0 -> (ctrl p1) -> p2, width w0 -> w1 (tapered): (pts (m,2), widths (m,))."""
    t = np.linspace(0.0, 1.0, m)[:, None]
    P = (1 - t) ** 2 * _v(p0) + 2 * (1 - t) * t * _v(p1) + t ** 2 * _v(p2)
    return P, np.linspace(w0, w1, m)


def crest_2d(R=0.068):
    """'Moon over silver grass' roundel (original design; no text, no tomoe/comma shapes) in 2D metres, R = outer radius:
    a ring, a full moon disc upper left, three silver-grass leaves fanning from a common base and two arching
    plumes with fine hanging barbs. Preview/iteration tool: out/dev/meshes/crest/crest_preview.py.
    Returns (discs [(centre, r)], rings [(r0, r1)], strokes [(pts (m,2), widths (m,))])."""
    strokes = [_qstroke((0.06, -0.80), (-0.10, -0.32), (-0.66, -0.16), 0.13, 0.012),
               _qstroke((0.10, -0.80), (0.08, -0.30), (0.36, 0.06), 0.12, 0.012),
               _qstroke((0.14, -0.80), (0.34, -0.48), (0.74, -0.36), 0.11, 0.012)]
    for p0, p1, p2, droop in (((0.12, -0.55), (0.16, 0.30), (0.62, 0.22), (0.35, -1.0)),
                              ((0.08, -0.55), (-0.02, 0.05), (-0.36, -0.02), (-0.30, -1.0))):
        P, W = _qstroke(p0, p1, p2, 0.050, 0.012, m=20)
        strokes.append((P, W))
        d = _v(droop) / np.linalg.norm(droop)
        for k, i in enumerate(range(9, 20, 2)):
            q = P[i]
            L = 0.15 - 0.012 * k
            strokes.append(_qstroke(q, q + d * L * 0.5 + (P[i] - P[i - 1]) * 1.5, q + d * L, 0.030, 0.004, m=6))
    discs = [((-0.28 * R, 0.40 * R), 0.29 * R)]
    rings = [(0.87 * R, R)]
    strokes = [(P * R, W * R) for P, W in strokes]
    return discs, rings, strokes


def crest_part(table, zc, R, off, mat):
    """Map crest_2d onto the haori back (viewed from behind: 2D +u = the viewer's right = his RIGHT = -x)."""
    discs, rings, strokes = crest_2d(R)
    parts = []

    def to3(u, v):
        return _haori_back_point(table, -u, zc + v, off)
    for (cu, cv), r in discs:
        a = np.linspace(0, 2 * math.pi, 24, endpoint=False)
        ring = [to3(cu + r * math.cos(t), cv + r * math.sin(t)) for t in a]
        V = np.array([to3(cu, cv)] + ring)
        F = [(0, 1 + (i + 1) % 24, 1 + i) for i in range(24)]
        parts.append(Part(V, F, None, mat))
    for r0, r1 in rings:
        a = np.linspace(0, 2 * math.pi, 64, endpoint=False)
        V = np.array([to3(r0 * math.cos(t), r0 * math.sin(t)) for t in a] +
                     [to3(r1 * math.cos(t), r1 * math.sin(t)) for t in a])
        F = [(i, 64 + i, 64 + (i + 1) % 64, (i + 1) % 64) for i in range(64)]
        parts.append(Part(V, F, None, mat))
    for pts, w in strokes:
        pts = np.asarray(pts)
        m = len(pts)
        L, Rr = [], []
        for i in range(m):
            tg = pts[min(i + 1, m - 1)] - pts[max(i - 1, 0)]
            tg = tg / max(np.linalg.norm(tg), 1e-9)
            nrm = np.array((-tg[1], tg[0]))
            L.append(to3(*(pts[i] + nrm * w[i] * 0.5)))
            Rr.append(to3(*(pts[i] - nrm * w[i] * 0.5)))
        V = np.array(L + Rr)
        F = [(i, i + 1, m + i + 1, m + i) for i in range(m - 1)]
        parts.append(Part(V, F, None, mat))
    out = []
    for p_ in parts:
        c = p_.V.mean(axis=0)
        out.append(fix_winding(p_, [c - np.array((0, 0.2, 0)), c - np.array((0, 0.19, 0))]))
    return out


def _sleeve_rows(rr, side, r_arm=0.096, pouch=0.23, n=22, t_end=0.88, lining=0.0):
    """Wide haori sleeve rows along the arm (shoulder seam -> cuff): section = circle around the arm (top half)
    stretched downward into the hanging pouch (world-down projected perpendicular to the arm). Returns
    (rows (m, n, 3), per-row arm points, per-row depth direction, per-row t)."""
    J, E, Wr = rr.h(f"upper_arm.{side}"), rr.t(f"upper_arm.{side}"), rr.t(f"forearm.{side}")
    La, Lf = np.linalg.norm(E - J), np.linalg.norm(Wr - E)
    Ltot = La + Lf
    ts = [-0.02, 0.06, 0.16, 0.28, 0.40, 0.50, 0.60, 0.70, 0.80, t_end - 0.02, t_end]
    rows, ctrs, downs, tt = [], [], [], []
    for t in ts:
        d = t * Ltot
        if d <= La:
            c = J + (E - J) * (d / La)
        else:
            c = E + (Wr - E) * ((d - La) / Lf)
        ax_ = _unit(Wr - J)                  # parallel section planes: no fold on the inside of the elbow bend
        down = np.array((0.0, 0.0, -1.0)) - ax_ * (-ax_[2])
        down = _unit(down)
        sideways = np.cross(ax_, down)
        p = pouch * smoothstep(0.05, 0.55, t)
        ra = (r_arm + 0.012 * smoothstep(0.0, 0.4, t)) - lining
        a = np.linspace(0.0, 2.0 * math.pi, n, endpoint=False)
        pts = []
        for ang in a:
            cs, sn = math.cos(ang), math.sin(ang)
            if sn >= 0:            # upper half (away from `down`)
                q = c + sideways * ra * cs - down * ra * 0.92 * sn
            else:
                q = c + sideways * ra * cs * (1.0 - 0.25 * smoothstep(0.0, 1.0, -sn) * (p / max(pouch, 1e-6)))
                q = q + down * (ra + p - lining * 0.5) * (-sn) ** 0.85
            pts.append(q)
        rows.append(pts)
        ctrs.append(c)
        downs.append(down)
        tt.append(t)
    return np.array(rows), np.array(ctrs), np.array(downs), np.array(tt)


def build_haori(rig, haori_obj, col, M):
    """SAINT_haori (the prop object, skinned): ochre open-front knee-length coat with lining, dark collar band,
    cream himo ties, wide sleeves with hanging pouches (-> sleeve.* bones) and the 'moon over silver grass' crest on the back.
    Replaces the object's mesh + vertex groups (object, name and parent unchanged)."""
    rr = RigRest(rig)
    T = haori_table()
    geo = Geo()
    reg = []

    def add(part, region, ref=None):
        """ref: positions used for skinning instead of the part's own (linings copy their outer shell's
        weights vertex for vertex, so the two layers can never cross)."""
        n0 = sum(len(p_.V) for p_ in geo.parts)
        geo.add(part)
        reg.append((region, np.arange(n0, n0 + len(part.V)), None if ref is None else _v(ref).reshape(-1, 3)))
    outer = haori_body_rows(T, ncol=44)
    inner = haori_body_rows(T, ncol=44, inset=0.006)
    ob = grid(outer, wrap=False, mat="haori")
    ib = grid(inner, wrap=False, mat="lining")
    axis = [(0, 0, 0.5), (0, -0.05, 1.7)]
    fix_winding(ob, axis)
    ib.F = [tuple(reversed(f)) for f in ob.F]
    ib.UV = [tuple(reversed(u)) for u in ob.UV]
    add(ob, "body")
    add(ib, "body", ref=ob.V)
    # hem rim (outer -> inner)
    rim = grid(np.array([outer[-1], inner[-1]]), wrap=False, mat="haori")
    add(rim, "body", ref=np.array([outer[-1], outer[-1]]))
    # collar band: up the left front edge, around the neck, down the right front edge
    le = outer[:, 0]
    re_ = outer[:, -1]
    neck = []
    for a in np.linspace(math.radians(-60), math.radians(240), 11):
        neck.append(np.array((0.098 * math.cos(a), T[0][3] + 0.092 * math.sin(a) + 0.004, 1.592 + 0.006 * math.sin(a))))
    path = [q + np.array((0.004, -0.004, 0.0)) for q in le[::-1][:-1]] + neck[::-1] + [q + np.array((-0.004, -0.004, 0.0)) for q in re_[1:]]
    path = catmull(path, 2)
    ups = []
    for i, q in enumerate(path):
        cy = float(np.interp(q[2], [r[0] for r in T][::-1], [r[3] for r in T][::-1]))
        nn = _unit((q[0], q[1] - cy, 0.0))
        tg = _unit(path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)])
        up = np.cross(nn, tg)
        if q[2] > 1.50:                        # around the neck the collar folds down onto the shoulders
            k = smoothstep(1.50, 1.575, q[2])
            up = _unit(up * (1.0 - k) + _unit(nn * 0.9 + np.array((0.0, 0.0, 0.45))) * k)
        ups.append(up)
    add(ribbon(path, np.full(len(path), 0.052), ups, thickness=0.016, mat="haori_collar"), "body")
    # himo: two short cords from the front edges to a small knot at the centre
    zc = 1.37
    iz = int(np.argmin([abs(r[0] - zc) for r in T]))
    kc = np.array((0.0, T[iz][3] - T[iz][2] - 0.012, zc - 0.012))
    for q in (outer[iz, 0], outer[iz, -1]):
        mid = (q + kc) / 2 + np.array((0.0, -0.01, -0.012))
        add(tube(catmull([q + np.array((0, -0.006, 0)), mid, kc], 4), 0.0045, n=6, mat="haori_himo"), "body")
    add(ellipsoid(kc, (1, 0, 0), (0, 0, 1), (0, -1, 0), (0.014, 0.010, 0.008), nu=10, nv=6, mat="haori_himo"), "body")
    for sx in (1.0, -1.0):          # two short tassel ends
        a0 = kc + np.array((sx * 0.004, -0.002, -0.004))
        add(capsule(a0, a0 + np.array((sx * 0.012, -0.004, -0.040)), 0.0045, 0.0032, n=6, ring=2, mat="haori_himo"),
            "body")
    # crest on the back
    for cp in crest_part(T, 1.415, 0.088, 0.0022, "crest"):
        add(cp, "body")
    # sleeves (outer + lining + cuff rim)
    for side in ("L", "R"):
        rows, ctrs, downs, tt = _sleeve_rows(rr, side)
        irows = rows.copy()
        for i in range(len(rows)):                       # lining = the outer section scaled about its centre
            cen = rows[i].mean(axis=0)
            irows[i] = cen + (rows[i] - cen) * 0.95
        so = grid(rows, wrap=True, mat="haori")
        fix_winding(so, ctrs)
        si = grid(irows, wrap=True, mat="lining")
        si.F = [tuple(reversed(f)) for f in so.F]
        si.UV = [tuple(reversed(u)) for u in so.UV]
        add(so, ("sleeve", side))
        add(si, ("sleeve", side), ref=so.V)
        add(grid(np.array([rows[-1], irows[-1]]), wrap=True, mat="haori"), ("sleeve", side),
            ref=np.array([rows[-1], rows[-1]]))
        # sewn end of the pouch: close the last section below the cuff opening (strip to a chord under the arm)
        last = rows[-1]
        n_ = len(last)
        c0, dd = ctrs[-1], downs[-1]
        ax_ = _unit(ctrs[-1] - ctrs[0])
        sw = _unit(np.cross(ax_, dd))
        low = [j for j in range(n_) if np.dot(last[j] - c0, dd) > 0.075]
        V, F = [], []
        for k, j in enumerate(low):
            q = last[j]
            chord = c0 + sw * np.dot(q - c0, sw) * 0.97 + dd * 0.075
            V += [q, chord]
            if k:
                F.append((2 * k - 2, 2 * k, 2 * k + 1, 2 * k - 1))
        if F:
            add(Part(np.array(V), F, None, "haori"), ("sleeve", side))
    V = geo.V
    n = len(V)
    Wparts = []
    for region, ids, ref in reg:
        P = V[ids] if ref is None else ref
        if region == "body":
            Wt = _arm_blend(P, _torso_weights(P, rr, sh_x=(0.09, 0.19), sh_z=(1.42, 1.51), lo=0.90))
            ang = np.arctan2(P[:, 1] - 0.0, P[:, 0])                   # +x = 0, back = +90 deg
            wb = np.clip(np.sin(ang), 0.0, 1.0) ** 1.5
            wl = np.clip(np.cos(ang), 0.0, 1.0) * (1.0 - wb) + np.where((P[:, 1] < 0) & (P[:, 0] > 0), 1.0, 0.0) * 0.6
            wr = np.clip(-np.cos(ang), 0.0, 1.0) * (1.0 - wb) + np.where((P[:, 1] < 0) & (P[:, 0] <= 0), 1.0, 0.0) * 0.6
            tot = wb + wl + wr + 1e-9
            Wh = {"hem.B": wb / tot, "hem.L": wl / tot, "hem.R": wr / tot}
            front = np.clip(-P[:, 1] / 0.2, 0.0, 1.0) * smoothstep(1.0, 0.75, P[:, 2]) * 0.35
            Wth = {"thigh.L": np.where(P[:, 0] > 0, 1.0, 0.0), "thigh.R": np.where(P[:, 0] <= 0, 1.0, 0.0)}
            Wh = blend_weights(Wh, Wth, front)
            Wh = blend_weights(Wh, {"hips": np.ones(len(P))}, 0.25 * smoothstep(0.9, 1.1, P[:, 2]))
            W = blend_weights(Wt, Wh, smoothstep(1.13, 0.98, P[:, 2]))
        else:
            _, side = region
            J = rr.h(f"upper_arm.{side}")
            seam = J - np.array(((1.0 if side == "L" else -1.0) * 0.06, 0.0, -0.01))
            segs = [(seam, J), (J, rr.t(f"upper_arm.{side}")), (rr.h(f"forearm.{side}"), rr.t(f"forearm.{side}")
                                                              + _unit(rr.t(f"forearm.{side}") - rr.h(f"forearm.{side}")) * 0.1)]
            Wa = chain_weights(P, rr, [f"shoulder.{side}", f"upper_arm.{side}", f"forearm.{side}"],
                               blends=[0.035, 0.08], segs=segs)
            Wa = blend_weights(Wa, {f"upper_arm.{side}": np.ones(len(P))}, 0.35 * Wa[f"shoulder.{side}"])
            # hanging pouch -> sleeve.<side> (distance below the arm axis along world down)
            Wr = rr.t(f"forearm.{side}")
            dist, t = _closest_on_segment(P, rr.h(f"upper_arm.{side}"), Wr)
            axp = rr.h(f"upper_arm.{side}") + np.outer(t, Wr - rr.h(f"upper_arm.{side}"))
            below = -(P[:, 2] - axp[:, 2])
            wp = smoothstep(-0.02, 0.28, below) * smoothstep(0.38, 0.70, t) * 0.8
            W = blend_weights(Wa, {f"sleeve.{side}": np.ones(len(P))}, wp)
        Wparts.append((ids, W))
    Wall = merge_weights(Wparts, n)
    return skinned_object("SAINT_haori", geo, M, rig, col, Wall, ob=haori_obj)


# =============================================================================================
# weapons and props (each in its documented LOCAL frame)
# =============================================================================================
KATANA_PROFILE = np.array([(0.0, -1.0), (0.50, -0.30), (1.0, 0.42), (0.62, 0.88), (0.0, 1.02), (-0.62, 0.88),
                           (-1.0, 0.42), (-0.50, -0.30)])     # (x thickness, z width): edge at z=-1, shinogi ridge


def prop_materials(char):
    """Weapon materials of one character: blade (hamon + Wet), habaki, tsuba, wrap, fittings, saya lacquer."""
    c = char
    M = {"blade": mat_blade(f"MESH_{c}_blade")}
    if c == "SHINOBI":
        M["habaki"] = mat_simple("MESH_SHINOBI_habaki", (0.55, 0.30, 0.16), rough=0.3, metal=1.0)
        M["tsuba"] = mat_simple("MESH_SHINOBI_tsuba", (0.030, 0.029, 0.030), rough=0.42, metal=0.85, noise=0.12)
        M["wrap"] = mat_wrap("MESH_SHINOBI_tsuka", (0.018, 0.018, 0.020), PAL["shinobi_red"], rough_win=0.3)
        M["fitting"] = mat_simple("MESH_SHINOBI_fitting", (0.028, 0.027, 0.028), rough=0.35, metal=0.9)
        M["saya"] = mat_simple("MESH_SHINOBI_saya", PAL["lacquer_black"], rough=0.18, coat=1.0, coat_rough=0.05)
        M["kunai"] = mat_simple("MESH_SHINOBI_kunai", (0.10, 0.10, 0.11), rough=0.3, metal=1.0, noise=0.1)
        M["cord"] = mat_simple("MESH_SHINOBI_kunai_cord", (0.30, 0.03, 0.03), rough=0.7, sheen=0.4)
    else:
        M["habaki"] = mat_simple("MESH_SAINT_gold", PAL["gold"], rough=0.28, metal=1.0)
        M["tsuba"] = M["habaki"]
        M["wrap"] = mat_wrap("MESH_SAINT_tsuka", (0.74, 0.72, 0.66), (0.86, 0.84, 0.76), rough_wrap=0.55,
                             rough_win=0.45)
        M["fitting"] = M["habaki"]
        M["saya"] = mat_simple("MESH_SAINT_lacquer", PAL["lacquer_black"], rough=0.18, coat=1.0, coat_rough=0.05)
        M["shaft"] = mat_simple("MESH_SAINT_spear_shaft", PAL["spear_shaft"], rough=0.25, coat=1.0, coat_rough=0.08)
        M["black"] = mat_simple("MESH_SAINT_black_fitting", (0.02, 0.02, 0.02), rough=0.35, metal=0.6)
        M["straw"] = mat_straw("MESH_SAINT_straw", PAL["straw"])
        M["hatband"] = mat_simple("MESH_SAINT_hat_binding", (0.05, 0.035, 0.022), rough=0.6, sheen=0.3)
        M["cord"] = mat_simple("MESH_SAINT_beard_cord", PAL["beard_cord"], rough=0.55, sheen=0.5, noise=0.1)
        M["tasuki"] = mat_cloth("MESH_SAINT_tasuki", PAL["tasuki"], rough=0.75, sheen=0.4, thread=500.0)[0]
    return M


def blade_part(D, y0, t0=0.0, t1=1.0, profile=KATANA_PROFILE, n=26, mat="blade", origin_y=0.0):
    """Katana blade between blade fractions t0..t1 (0 = machi, 1 = tip), sori towards -Z, kissaki taper, hamon UVs
    (u = metres along the blade, v = 0 edge .. 1 back)."""
    L = D["blade_length"]
    kiss = 0.055 / L
    prof = _v(profile)
    ts = np.unique(np.r_[np.linspace(0.0, 1.0 - kiss, n), np.linspace(1.0 - kiss, 1.0, 6), [t0, t1]])
    ts = ts[(ts >= t0 - 1e-9) & (ts <= t1 + 1e-9)]
    V, uvv = [], []
    rows = []
    for t in ts:
        y = y0 + L * t
        zoff = -D["sori"] * 4.0 * t * (1.0 - t)
        w = D["blade_width"] + (D["blade_width_tip"] - D["blade_width"]) * min(1.0, t / (1.0 - kiss))
        th = D["blade_thickness"] * (1.0 - 0.45 * t)
        if t > 1.0 - kiss:
            u = (1.0 - t) / kiss
            w *= math.sqrt(max(u, 0.0)) * 0.85 + 0.15 * u
            th *= max(u, 0.0) ** 0.6
        ids = []
        for px, pz in prof:
            zz = pz * w * 0.5
            if t > 1.0 - kiss and pz < 0:          # fukura: the edge sweeps up to the tip
                zz *= 0.55 + 0.45 * ((1.0 - t) / kiss)
            ids.append(len(V))
            V.append((px * th * 0.5, y - origin_y, zoff + zz))
            uvv.append((L * t, (pz + 1.0) / 2.0))
        rows.append(ids)
    F, UV = [], []
    m = len(prof)
    for a, b in zip(rows[:-1], rows[1:]):
        for j in range(m):
            j1 = (j + 1) % m
            f = (a[j], b[j], b[j1], a[j1])
            F.append(f)
            UV.append(tuple(uvv[k] for k in f))
    for ids, rev in ((rows[0], True), (rows[-1], False)):
        f = tuple(reversed(ids)) if rev else tuple(ids)
        F.append(f)
        UV.append(tuple(uvv[k] for k in f))
    part = Part(np.array(V), F, UV, mat)
    return fix_winding(part, [(0.0, y0 - origin_y - 1.0, 0.0), (0.0, y0 - origin_y + 2.0, 0.0)])


def katana_parts(char, D, part="all", origin_y=0.0):
    """Katana in the katana frame (origin right-fist centre, +Y tip, -Z edge): blade (+hamon), habaki, seppa,
    tsuba, tsuka (diamond wrap) with fuchi/kashira/menuki. part: 'all' | 'main' (without the broken tip) | 'tip'."""
    yt, tt = D["grip_to_tsuba"], D["tsuba_thickness"]
    y0 = yt + tt * 0.5
    L = D["blade_length"]
    X, Z = np.array((1.0, 0.0, 0.0)), np.array((0.0, 0.0, 1.0))
    o = np.array((0.0, origin_y, 0.0))
    parts = []
    brk = (L - D["break_from_tip"]) / L if D.get("break_from_tip") else None
    if part == "tip":
        return [blade_part(D, y0, brk, 1.0, origin_y=origin_y)]
    parts.append(blade_part(D, y0, 0.0, brk if part == "main" else 1.0, origin_y=origin_y))
    # habaki + seppa
    hb = D["habaki_length"]
    st = [dict(c=np.array((0, y0 - 0.001, 0)) - o, X=X, Z=Z, rx=D["blade_thickness"] * 0.95,
               rz=D["blade_width"] * 0.58, e=3.0),
          dict(c=np.array((0, y0 + hb, -0.0015)) - o, X=X, Z=Z, rx=D["blade_thickness"] * 0.80,
               rz=D["blade_width"] * 0.56, e=3.0)]
    parts.append(loft(st, n=12, cap0=True, cap1=True, mat="habaki"))
    for yy in (yt + tt * 0.5 + 0.0012, yt - tt * 0.5 - 0.0012):
        st = [dict(c=np.array((0, yy - 0.0012, 0)) - o, X=X, Z=Z, rx=0.017, rz=0.024),
              dict(c=np.array((0, yy + 0.0012, 0)) - o, X=X, Z=Z, rx=0.017, rz=0.024)]
        parts.append(loft(st, n=14, cap0=True, cap1=True, mat="habaki"))
    # tsuba (SHINOBI round iron with a raised rim; SAINT gold, gently four-lobed)
    R = D["tsuba_diameter"] * 0.5
    lobed = (lambda th, i: 1.0 - 0.05 * np.abs(np.sin(2.0 * th))) if char == "SAINT" else None
    st = []
    for yy, k in ((yt - tt * 0.5, 0.965), (yt - tt * 0.5 + 0.0015, 1.0), (yt + tt * 0.5 - 0.0015, 1.0),
                  (yt + tt * 0.5, 0.965)):
        st.append(dict(c=np.array((0, yy, 0)) - o, X=X, Z=Z, rx=R * 0.90 * k, rz=R * k, mod=lobed))
    parts.append(loft(st, n=28, cap0=True, cap1=True, mat="tsuba"))
    # tsuka + fuchi + kashira + menuki
    ya, yb = yt - tt * 0.5 - D["tsuka_length"], yt - tt * 0.5 - 0.004
    dx, dz = D["tsuka_depth"] * 0.5, D["tsuka_width"] * 0.5
    st = []
    for y, k in ((ya + 0.012, 1.0), (ya + 0.05, 0.985), (0.5 * (ya + yb), 0.955), (yb - 0.03, 0.99), (yb - 0.016, 1.0)):
        st.append(dict(c=np.array((0, y, 0)) - o, X=X, Z=Z, rx=dx * k, rz=dz * k, e=2.3))
    parts.append(loft(st, n=16, mat="wrap"))
    st = [dict(c=np.array((0, yb - 0.018, 0)) - o, X=X, Z=Z, rx=dx * 1.04, rz=dz * 1.04, e=2.3),
          dict(c=np.array((0, yb + 0.003, 0)) - o, X=X, Z=Z, rx=dx * 1.06, rz=dz * 1.06, e=2.3)]
    parts.append(loft(st, n=16, cap0=True, cap1=True, mat="fitting"))
    st = [dict(c=np.array((0, ya + 0.016, 0)) - o, X=X, Z=Z, rx=dx * 1.05, rz=dz * 1.05, e=2.3),
          dict(c=np.array((0, ya + 0.003, 0)) - o, X=X, Z=Z, rx=dx * 0.98, rz=dz * 0.98, e=2.3),
          dict(c=np.array((0, ya - 0.002, 0)) - o, X=X, Z=Z, rx=dx * 0.7, rz=dz * 0.7, e=2.3),
          dict(c=np.array((0, ya - 0.003, 0)) - o, X=X, Z=Z, rx=0.0, rz=0.0)]
    parts.append(loft(st, n=16, cap0=True, mat="fitting"))
    ym = ya + D["tsuka_length"] * 0.58
    for sxm in (1.0, -1.0):
        parts.append(ellipsoid(np.array((sxm * dx * 0.93, ym, 0.0)) - o, (0, 0, 1), (0, 1, 0), (1, 0, 0),
                               (0.006, 0.013, 0.0035), nu=8, nv=4, mat="fitting"))
    return parts


def saya_parts(char, D):
    """Scabbard (origin koiguchi, +Y to the kojiri, -Z edge side), curved with the blade's sori so the sheathed
    blade stays inside; lacquer + koiguchi/kurikata/kojiri fittings."""
    L = D["saya_length"]
    Lb = D["blade_length"]
    X, Z = np.array((1.0, 0.0, 0.0)), np.array((0.0, 0.0, 1.0))

    def zc(y):
        t = np.clip(y / Lb, 0.0, 1.0)                  # the blade's machi sits at the koiguchi (saya y = 0)
        return -D["sori"] * 4.0 * t * (1.0 - t)
    ys = np.r_[[0.0, 0.02, 0.04, 0.06], np.linspace(0.08, L - 0.035, 12), [L - 0.02, L - 0.006, L]]
    st = []
    for y in ys:
        k = 1.0 if y < L - 0.035 else (0.95 if y < L - 0.01 else 0.7)
        k *= 1.0 + 0.10 * smoothstep(0.075, 0.035, y)          # mouth wide enough for the habaki
        taper = 1.0 - 0.10 * (y / L)
        st.append(dict(c=np.array((0.0, y, zc(y))), X=X, Z=Z, rx=D["saya_depth"] * 0.5 * taper * k,
                       rz=D["saya_width"] * 0.5 * taper * k, e=2.4))
    parts = [loft(st, n=16, cap0=True, cap1=True, mat="saya")]
    # koiguchi ring, kojiri cap, kurikata (on the +X flat, near the mouth)
    st = [dict(c=np.array((0.0, -0.001, zc(0.0))), X=X, Z=Z, rx=D["saya_depth"] * 0.575, rz=D["saya_width"] * 0.575, e=2.4),
          dict(c=np.array((0.0, 0.024, zc(0.024))), X=X, Z=Z, rx=D["saya_depth"] * 0.565, rz=D["saya_width"] * 0.565, e=2.4)]
    parts.append(loft(st, n=16, cap0=True, cap1=False, mat="fitting"))
    st = [dict(c=np.array((0.0, L - 0.04, zc(L - 0.04))), X=X, Z=Z, rx=D["saya_depth"] * 0.47, rz=D["saya_width"] * 0.47, e=2.4),
          dict(c=np.array((0.0, L - 0.004, zc(L))), X=X, Z=Z, rx=D["saya_depth"] * 0.36, rz=D["saya_width"] * 0.36, e=2.4),
          dict(c=np.array((0.0, L + 0.002, zc(L))), X=X, Z=Z, rx=0.0, rz=0.0)]
    parts.append(loft(st, n=16, cap0=True, mat="fitting"))
    parts.append(rbox(np.array((D["saya_depth"] * 0.55, 0.10, zc(0.10))), (1, 0, 0), (0, 1, 0), (0, 0, 1),
                      (0.012, 0.026, 0.014), e=3.0, nu=10, nv=5, mat="fitting"))
    return parts


def spear_parts(D, sheath=False, naked=True, origin_y=0.0):
    """Straight vermilion yari (origin butt, +Y tip, -Z one edge): ishizuki, lacquered shaft with black rings,
    gold collar, diamond-section su-yari blade (hamon UV); optional black-lacquer sheath with a gold mouth."""
    L, bl, r = D["spear_length"], D["spear_blade_length"], D["spear_shaft_diameter"] * 0.5
    X, Z = np.array((1.0, 0.0, 0.0)), np.array((0.0, 0.0, 1.0))
    o = np.array((0.0, origin_y, 0.0))
    parts = []
    if naked or sheath:
        st = [dict(c=np.array((0, y, 0)) - o, X=X, Z=Z, rx=r * k, rz=r * k) for y, k in
              ((-0.004, 0.0), (0.0, 0.85), (0.012, 1.14), (0.075, 1.10), (0.082, 1.0))]
        parts.append(loft(st, n=12, mat="black"))
        ys = L - bl - 0.075
        parts.append(loft([dict(c=np.array((0, y, 0)) - o, X=X, Z=Z, rx=r, rz=r) for y in (0.08, ys)], n=12,
                          mat="shaft"))
        for yy in (0.46, 0.50, ys - 0.12, ys - 0.08):
            parts.append(loft([dict(c=np.array((0, yy, 0)) - o, X=X, Z=Z, rx=r * 1.09, rz=r * 1.09),
                               dict(c=np.array((0, yy + 0.018, 0)) - o, X=X, Z=Z, rx=r * 1.09, rz=r * 1.09)],
                              n=12, cap0=True, cap1=True, mat="black"))
        st = [dict(c=np.array((0, y, 0)) - o, X=X, Z=Z, rx=r * k, rz=r * k) for y, k in
              ((ys, 1.12), (ys + 0.04, 1.08), (ys + 0.055, 1.18), (L - bl, 0.95))]
        parts.append(loft(st, n=12, cap0=True, cap1=True, mat="habaki"))
        # blade: diamond section, straight; UV v = 0 at both edges .. 1 on the ridge
        w, th = 0.036 * 1.3, 0.012 * 1.3
        prof = np.array([(0.0, -1.0), (1.0, 0.0), (0.0, 1.0), (-1.0, 0.0)])
        V, uvv, rows = [], [], []
        for t in np.linspace(0.0, 1.0, 10):
            k = (1.0 - t ** 1.7) * (0.78 + 0.22 * min(1.0, t * 6.0)) if t < 1.0 else 0.0
            ids = []
            for px, pz in prof:
                ids.append(len(V))
                V.append((px * th * 0.5 * max(k, 0.0) ** 0.8, L - bl + bl * t - origin_y, pz * w * 0.5 * max(k, 0.0)))
                uvv.append((bl * t, 1.0 - abs(pz)))
            rows.append(ids)
        F, UV = [], []
        for a, b in zip(rows[:-1], rows[1:]):
            for j in range(4):
                j1 = (j + 1) % 4
                f = (a[j], b[j], b[j1], a[j1])
                F.append(f)
                UV.append(tuple(uvv[q] for q in f))
        f = tuple(reversed(rows[0]))
        F.append(f)
        UV.append(tuple(uvv[q] for q in f))
        parts.append(fix_winding(Part(np.array(V), F, UV, "blade"), [(0, -10, 0), (0, 10, 0)]))
    if sheath:
        parts += spear_sheath_parts(D, origin_y)
    return parts


def spear_sheath_parts(D, origin_y=0.0):
    L, sl, sd = D["spear_length"], D["spear_sheath_length"], D["spear_sheath_diameter"]
    X, Z = np.array((1.0, 0.0, 0.0)), np.array((0.0, 0.0, 1.0))
    o = np.array((0.0, origin_y, 0.0))
    st = []
    for y, k in ((L - sl, 0.62), (L - sl + 0.004, 0.80), (L - sl + 0.03, 1.0), (L - 0.07, 1.0), (L - 0.01, 0.82),
                 (L + 0.025, 0.40), (L + 0.030, 0.0)):
        st.append(dict(c=np.array((0, y, 0)) - o, X=X, Z=Z, rx=sd * 0.34 * k, rz=sd * 0.5 * k, e=2.3))
    parts = [loft(st, n=16, cap0=True, mat="saya")]
    st = [dict(c=np.array((0, L - sl - 0.002, 0)) - o, X=X, Z=Z, rx=sd * 0.36, rz=sd * 0.52, e=2.3),
          dict(c=np.array((0, L - sl + 0.022, 0)) - o, X=X, Z=Z, rx=sd * 0.36, rz=sd * 0.52, e=2.3)]
    parts.append(loft(st, n=16, cap0=True, cap1=False, mat="habaki"))
    return parts


def hat_parts(D, half=None, origin=(0.0, 0.0, 0.0)):
    """Sugegasa (origin rim-plane centre, +Z up; halves split at local X = 0): straw cone with a gently convex
    profile, concentric stitch rings, dark rim binding, head ring underneath. half 'A' (x >= 0) | 'B' | None."""
    R, h = D["hat_diameter"] * 0.5, D["hat_height"]
    o = _v(origin)
    prof = [(0.0, h), (0.05, h - 0.004), (0.12, h - 0.018), (0.25, h - 0.045), (0.40, h - 0.074), (0.55, h - 0.099),
            (0.70, h - 0.119), (0.85, h - 0.134), (0.95, h - 0.141), (1.0, h - 0.143)]
    rs = np.array([p[0] for p in prof]) * R
    zs = np.array([p[1] for p in prof])
    thick = 0.011
    if half is None:
        angs = np.linspace(0.0, 2.0 * math.pi, 40, endpoint=False)
        wrap = True
    else:
        a0 = -math.pi / 2 if half == "A" else math.pi / 2
        angs = np.linspace(a0, a0 + math.pi, 21)
        wrap = False

    def surf(dz, rscale=1.0):
        rows = []
        for r_, z_ in zip(rs, zs):
            rr_ = max(r_ * rscale, 1e-4)
            rows.append([np.array((rr_ * math.cos(a), rr_ * math.sin(a), z_ + dz)) - o for a in angs])
        return np.array(rows)
    top = surf(0.0)
    bot = surf(-thick, 0.985)
    parts = [grid(top, wrap=wrap, mat="straw"), grid(bot[::-1], wrap=wrap, mat="straw")]
    parts[0] = fix_winding(parts[0], [(0, 0, -1.0) - o, (0, 0, -0.9) - o])
    parts[1].F = [tuple(reversed(f)) for f in parts[1].F]
    parts[1] = fix_winding(parts[1], [(0, 0, 1.0) - o, (0, 0, 0.9) - o])
    parts[1].F = [tuple(reversed(f)) for f in parts[1].F]
    parts.append(grid(np.array([top[-1], bot[-1]]), wrap=wrap, mat="hatband"))
    # rim binding + stitch rings (ridges)
    for k in (0.36, 0.62, 0.86):
        z_ = float(np.interp(k * R, rs, zs)) + 0.0015
        ring = [np.array((k * R * math.cos(a), k * R * math.sin(a), z_)) - o for a in angs]
        parts.append(tube(ring, 0.0022, n=4, loop=wrap, cap=not wrap, mat="hatband"))
    ring = [np.array((R * 0.995 * math.cos(a), R * 0.995 * math.sin(a), zs[-1] - thick * 0.4)) - o for a in angs]
    parts.append(tube(ring, 0.0068, n=6, loop=wrap, cap=not wrap, mat="hatband"))
    ring = [np.array((0.083 * math.cos(a), 0.083 * math.sin(a), 0.058)) - o for a in angs]
    parts.append(tube(ring, 0.006, n=5, loop=wrap, cap=not wrap, mat="hatband"))
    if not wrap:                                     # cut faces of the half
        for j in (0, len(angs) - 1):
            parts.append(grid(np.array([top[:, j], bot[:, j]]).transpose(1, 0, 2), wrap=False, mat="straw"))
    return parts


def cord_parts(D, r_in=0.0118, turns=3, opened=False):
    """Vermilion cord coil around the beard (local frame: +Y = beard.3 axis, origin = cord centre).
    opened=True: the cut cord - an unwinding helix with loose ends."""
    rt = D["beard_cord_diameter"] * 0.13
    pts = []
    m = 18 * turns
    for i in range(m + 1):
        t = i / m
        a = 2 * math.pi * turns * t
        y = (t - 0.5) * 0.0105 * turns
        rad = r_in + rt
        if opened:
            rad *= 1.0 + 1.2 * t * t
            y *= 1.0 + 0.8 * t
        pts.append(np.array((rad * math.cos(a), y, rad * math.sin(a))))
    ends = []
    if opened:
        ends = [pts[0] + np.array((0.012, -0.010, 0.01)), pts[0]]
        pts = [ends[0]] + pts + [pts[-1] + np.array((0.0, 0.012, 0.022))]
    parts = [tube(pts, rt, n=6, cap=True, mat="cord")]
    if not opened:
        parts.append(ellipsoid(np.array((r_in + rt * 1.6, 0.0, 0.0)), (0, 1, 0), (1, 0, 0), (0, 0, 1),
                               (0.006, 0.006, 0.0075), nu=8, nv=5, mat="cord"))
    return parts


def kunai_parts(D, origin_y=0.0):
    """Kunai (origin blade/handle junction ~ CoM, +Y point): ring pommel, cord-wrapped grip, leaf blade."""
    o = np.array((0.0, origin_y, 0.0))
    parts = []
    ring = [np.array((0.0, -0.100 + 0.014 * math.sin(a), 0.014 * math.cos(a))) - o
            for a in np.linspace(0, 2 * math.pi, 16, endpoint=False)]
    parts.append(tube(ring, 0.0032, n=6, loop=True, mat="kunai"))
    X, Z = np.array((1.0, 0.0, 0.0)), np.array((0.0, 0.0, 1.0))
    parts.append(loft([dict(c=np.array((0, y, 0)) - o, X=X, Z=Z, rx=0.0062, rz=0.0075) for y in (-0.087, -0.004)],
                      n=8, cap0=True, cap1=True, mat="cord"))
    for y in np.linspace(-0.08, -0.01, 6):
        parts.append(loft([dict(c=np.array((0, y, 0)) - o, X=X, Z=Z, rx=0.0071, rz=0.0084),
                           dict(c=np.array((0, y + 0.006, 0)) - o, X=X, Z=Z, rx=0.0071, rz=0.0084)], n=8,
                          cap0=True, cap1=True, mat="cord"))
    bl = D["kunai_length"] - 0.1
    st = [dict(c=np.array((0, y, 0)) - o, X=X, Z=Z, rx=th, rz=w) for y, th, w in
          ((-0.004, 0.0045, 0.011), (0.004, 0.0045, 0.012), (bl * 0.32, 0.0042, 0.021), (bl * 0.75, 0.0025, 0.012),
           (bl, 0.0, 0.0))]
    parts.append(loft(st, profile=[(0.0, -1.0), (1.0, 0.0), (0.0, 1.0), (-1.0, 0.0)], cap0=True, mat="kunai"))
    return parts


def tasuki_path(T):
    """Figure-8 tasuki path (rig space) around the kimono torso: an X on the back, loops over the shoulders and
    under the armpits."""
    pts = []
    spec = [(62, 1.565, 0.012), (90, 1.43, 0.012), (160, 1.305, 0.012), (190, 1.33, 0.010), (238, 1.41, 0.010),
            (205, 1.563, 0.012), (118, 1.565, 0.012), (90, 1.43, 0.018), (20, 1.305, 0.012), (-10, 1.33, 0.010),
            (-58, 1.41, 0.010), (-25, 1.563, 0.012)]
    for ang, z, off in spec:
        pts.append(torso_surface(T, math.radians(ang), z, off))
    return catmull(pts, 5, closed=True)


def _set_mesh(obj, geo, mats, smooth=True, sharp=40.0):
    """Replace a prop object's mesh (object, name, parent, constraints and custom props untouched)."""
    me = geo.mesh(obj.name + "_mesh", mats, smooth=smooth, sharp_angle=sharp)
    old = obj.data
    obj.data = me
    if old is not None and old != me and old.users == 0:
        bpy.data.meshes.remove(old)
    obj["mesh_lane"] = MESH_VERSION
    return obj


def build_props(rigs, props, dims):
    """Replace the mesh data of every weapon / costume prop with the final look (objects keep their contract)."""
    P = props
    for char in CHARS:
        D = dims[char]
        M = prop_materials(char)
        if char == "SHINOBI":
            kat = Geo().add(katana_parts(char, D))
            _set_mesh(P["SHINOBI_katana_hand"], kat, M)
            P["SHINOBI_katana_sheathed"].data = P["SHINOBI_katana_hand"].data
            _set_mesh(P["SHINOBI_saya"], Geo().add(saya_parts(char, D)), M)
            for nm in ("SHINOBI_kunai_1", "SHINOBI_kunai_2", "SHINOBI_kunai_3", "SHINOBI_kunai_hand"):
                if nm in P:
                    _set_mesh(P[nm], Geo().add(kunai_parts(D)), M)
        else:
            L = D["blade_length"]
            yt, tt = D["grip_to_tsuba"], D["tsuba_thickness"]
            y0 = yt + tt * 0.5
            brk = y0 + L - D["break_from_tip"]
            ymid = brk + D["break_from_tip"] * 0.5
            _set_mesh(P["SAINT_katana_hand"], Geo().add(katana_parts(char, D, "main")), M)
            _set_mesh(P["SAINT_katana_hand_tip"], Geo().add(katana_parts(char, D, "tip")), M)
            _set_mesh(P["SAINT_katana_sheathed"], Geo().add(katana_parts(char, D, "all")), M)
            _set_mesh(P["SAINT_katana_tip_broken"], Geo().add(katana_parts(char, D, "tip", origin_y=ymid)), M)
            _set_mesh(P["SAINT_saya"], Geo().add(saya_parts(char, D)), M)
            _set_mesh(P["SAINT_spear_slung"], Geo().add(spear_parts(D, sheath=True)), M)
            _set_mesh(P["SAINT_spear_hand"], Geo().add(spear_parts(D)), M)
            _set_mesh(P["SAINT_spear_world"], Geo().add(spear_parts(D, origin_y=D["spear_com"])), M)
            yc = D["spear_length"] - D["spear_sheath_length"] * 0.5 + 0.01
            _set_mesh(P["SAINT_spear_sheath_world"], Geo().add(spear_sheath_parts(D, origin_y=yc)), M)
            _set_mesh(P["SAINT_hat"], Geo().add(hat_parts(D)), M, sharp=60)
            for half, sx in (("A", 1.0), ("B", -1.0)):
                _set_mesh(P[f"SAINT_hat_half_{half}"], Geo().add(hat_parts(D, half=half, origin=(sx * 0.115, 0.0, 0.03))),
                          M, sharp=60)
            _set_mesh(P["SAINT_beard_cord"], Geo().add(cord_parts(D)), M)
            _set_mesh(P["SAINT_beard_cord_cut"], Geo().add(cord_parts(D, opened=True)), M)
            T = saint_torso_table()
            _set_mesh(P["SAINT_tasuki"], Geo().add(tube(tasuki_path(T), 0.0085, n=8, loop=True, mat="tasuki")), M)


# =============================================================================================
# keyable look inputs (lanes key these; lane_tools stashes material / node-group actions per lane)
# =============================================================================================
def _input_socket(name):
    kind, owner, node = MATERIAL_INPUTS[name]
    tree = bpy.data.materials[owner].node_tree if kind == "MATERIAL" else bpy.data.node_groups[owner]
    return tree.nodes[node].outputs[0]


def input_paths():
    """{input: (ID owner, data path)} of every keyable look input, e.g. the S04 glint:
    (bpy.data.materials['MESH_SAINT_eye_glint'].node_tree, 'nodes["Glint"].outputs[0].default_value')."""
    out = {}
    for name, (kind, owner, node) in MATERIAL_INPUTS.items():
        tree = bpy.data.materials[owner].node_tree if kind == "MATERIAL" else bpy.data.node_groups[owner]
        out[name] = (tree, f'nodes["{node}"].outputs[0].default_value')
    return out


def _key_input(name, frame, value, interp):
    sock = _input_socket(name)
    sock.default_value = float(value)
    return U.key(sock, "default_value", frame, float(value), interp=interp)


def key_headband_glow(frame, value, interp='LINEAR'):
    """SHINOBI hachimaki emission 0..1 (1 = the 'slightly emissive at night' level, DIRECTION §6)."""
    return _key_input("Glow", frame, value, interp)


def key_eye_glint(frame, value, interp='LINEAR'):
    """SAINT eye glint 0..1 (0 = invisible; S04 ~392: key 0 at 389, 1 at 392, 0 at 396)."""
    return _key_input("Glint", frame, value, interp)


def key_blade_wet(char, frame, value, interp='LINEAR'):
    """Blade 'Wet' 0..1 for 'SHINOBI' | 'SAINT' | None (both). The steel also follows env_wet (max of both), so
    this is for explicit moments (e.g. the first raindrops on the elder's blade in S19)."""
    chars = CHARS if char is None else (char,)
    return [_key_input(f"Wet_{c}", frame, value, interp) for c in chars]


def key_haori_burn(frame, value, interp='LINEAR'):
    """SAINT haori burn/dissolve 0..1 (shared node group: the worn coat and the thrown snapshot). 0 = intact; the
    ember front flickers on fx_time. S15: e.g. key 0 at 1640, 1 at ~1700 (slower = LINEAR over more frames)."""
    return _key_input("Burn", frame, value, interp)


def tri_counts():
    """Triangles per character: {'SHINOBI': {'body': n, 'props': n, 'objects': {...}}, ...} (body = body +
    costume objects built here, props = every other mesh in CHAR_<C> incl. free copies)."""
    out = {}
    for c in CHARS:
        col = bpy.data.collections.get(f"CHAR_{c}")
        body, props, objs = 0, 0, {}
        if col is None:
            continue
        for ob in col.all_objects:
            if ob.type != 'MESH':
                continue
            n = sum(len(p.vertices) - 2 for p in ob.data.polygons)
            objs[ob.name] = n
            if ob.name.startswith((f"{c}_body_", f"{c}_torso", f"{c}_hakama", "SAINT_beard", "SAINT_haori",
                                   "SHINOBI_hachimaki")) and not ob.name.endswith(("_thrown", "_cord", "_cord_cut")):
                body += n
            else:
                props += n
        out[c] = dict(body=body, props=props, objects=objs)
    return out


# =============================================================================================
# entry point (fallback-protected: a failure never breaks another lane's scene build)
# =============================================================================================
def _placeholder_fallback(rigs, err):
    import characters as C
    print(f"[character_meshes] WARNING: final meshes failed ({err}); using placeholder bodies")
    out = {}
    for char in CHARS:
        out.update(C.build_placeholder_body(char, rigs[char], U.ensure_collection(f"CHAR_{char}")))
    return out


def _fallback_into(props, out):
    props.update(out)
    return out


def build_meshes(rigs, props, dims):
    """Build both characters' final meshes (called by characters.build(meshes='auto')).
    rigs = {'SHINOBI': rig, 'SAINT': rig}; props = {name: obj}: prop objects get new mesh data + materials (same
    objects, names, parents, sockets); the new body/costume objects are created in CHAR_<C> and merged into `props`.
    dims = characters.DIMS. Returns {name: obj} of the body objects. Never raises: on any exception the partial body
    objects are removed and the rig lane's placeholder bodies are built instead (a warning is printed), so a
    problem here can never break another lane's scene build. Cost ~0.7 s for both characters."""
    t0 = time.time()
    try:
        out = _build_all(rigs, props, dims)
    except Exception as e:  # noqa: BLE001 - never break other lanes' builds
        traceback.print_exc()
        _cleanup_partial()
        out = _fallback_into(props, _placeholder_fallback(rigs, e))
        for r in rigs.values():
            r["mesh_fallback"] = str(e)[:200]
    for r in rigs.values():
        r["mesh_seconds"] = time.time() - t0
    return out


def _cleanup_partial():
    """Remove the body objects created by a failed build (prop objects are never deleted - only their data was
    replaced, and the placeholder bodies take over)."""
    for ob in list(bpy.data.objects):
        if ob.get("mesh_lane") and ob.name.startswith(("SHINOBI_body_", "SAINT_body_", "SHINOBI_torso",
                                                          "SAINT_torso", "SHINOBI_hakama", "SAINT_hakama",
                                                          "SAINT_beard", "SHINOBI_hachimaki_tails")) \
                and not ob.name.startswith("SAINT_beard_cord"):
            bpy.data.objects.remove(ob, do_unlink=True)


def _build_all(rigs, props, dims):
    import characters as C
    out = {}
    col = U.ensure_collection("CHAR_SHINOBI")
    o, _ = build_shinobi(rigs["SHINOBI"], col, dims["SHINOBI"])
    out.update(o)
    colS = U.ensure_collection("CHAR_SAINT")
    MS = saint_materials()
    out.update(build_saint_body(rigs["SAINT"], colS, dims["SAINT"], MS))
    build_haori(rigs["SAINT"], props["SAINT_haori"], colS, MS)
    build_props(rigs, props, dims)
    try:                                   # the thrown copy starts as the rest-pose snapshot of the final haori
        C.snapshot_haori(bpy.context.scene.frame_current)
    except Exception as e:  # noqa: BLE001
        print("[character_meshes] snapshot_haori failed:", e)
    props.update(out)
    return out
