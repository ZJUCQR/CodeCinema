"""
vfx.py - every visual effect of Duel in the Silver Grass, procedural, deterministic, bake-free (Blender 5.2.2, EEVEE).

Flash budgets and effect colors follow the staging constants in config.

Design rules (why things are built the way they are)
  * TIME: every effect reads the film clock scene["fx_time"] (codecinema/productions/silvergrass/blender/fxclock.py): GN inputs named "Time" are
    driven by it, shader Value nodes named "FX Time" are driven by it, and light energies / positions use
    "time curves" (a driver on fx_time whose F-curve keys map fx seconds -> value). So config.TIME_WARP slow-motion
    windows slow the effects too, and NOTHING here depends on keyframes: effects gate themselves on fx_time
    (GN Switch -> empty geometry outside their window), which keeps them immune to the NLA stashing of lanes.
    (Exceptions, by contract: tree_strike keys the visibility/rotation of the environment's pine objects.)
  * POOLS (rule 3): particle systems are fixed-count point clouds; unborn/dead slots get scale 0 via a Switch.
    Never Delete Geometry / merge / sort on anything that is motion-blurred (EEVEE matches instances by index).
  * SHADOWS (rule 5): visible_shadow=False on particles, rain, volumes; lights added here are unshadowed except the
    two fire-ring lights (<= 3 shadow-casting lights per shot including the sun/moon).
  * EMISSION (rule 7): fire / sparks 0.5-1.5 (hot cores up to ~3), bloom does the rest; lightning tubes 50-200 for
    2-4 frames; never full-frame white (only config.FULL_WHITE, done in the compositor by render_setup).
  * DETERMINISM: seeds via zlib.crc32 (never hash()); object names derived from kind + frame + seed.
  * COLLECTIONS: every object lives in collection "VFX_<kind>" under a parent collection "VFX".

Public API (see each docstring):
  sparks, blade_trail, flash_ring, wind_blade, grass_burst, dust_burst, fire_ring, embers, smoke, steam,
  lightning_bolt, blade_afterglow, tree_strike, grass_shear (forwards to environment.grass_effect), rain,
  rain_split, spray_ring, shockwave, red_mist, strobe, finalize, owner_color, reset.
"""

import math
import os
import sys
import zlib

import bpy
import numpy as np
from mathutils import Matrix, Vector

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(_HERE, "..", "common"), _HERE):
    _p = os.path.abspath(_p)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config            # noqa: E402
import bl_util as U      # noqa: E402

FPS = float(config.FPS)

# ------------------------------------------------------------------------------------------------ palette
# Linear RGB. Effects are colour-coded by owner (DIRECTION §6): the elder's trails/sparks follow the act
# (gold -> fire-orange -> cold steel-blue); the shinobi stays cool white with a red core.
# 'steel' (the elder's Act III blade effects) is a DESATURATED cold steel, deliberately far from 'electric'
# (= config.PALETTE['electric'], lightning only): blade effects must never read as electrified (deny-list).
COLORS = {
    "gold":      (1.00, 0.55, 0.12),
    "fire":      (1.00, 0.36, 0.06),
    "steel":     (0.72, 0.78, 0.85),
    "white":     (0.92, 0.96, 1.00),
    "red":       (0.95, 0.06, 0.03),
    "electric":  tuple(config.PALETTE["electric"]),
    "ember":     (1.00, 0.30, 0.04),
    "water":     (0.70, 0.80, 0.95),
    "dust":      (0.42, 0.34, 0.24),
    "steam":     (0.80, 0.82, 0.86),
    "smoke":     (0.05, 0.045, 0.04),
    "mist_red":  tuple(config.PALETTE["beard_cord"]),     # S26 red mist = the vermilion cord's colour
    "grass":     (0.62, 0.50, 0.28),
    "plume":     (0.95, 0.90, 0.80),
    "afterglow": (0.86, 0.92, 1.00),                      # hot white, a hint of blue (S21, on the blade only)
}
_COLOR_ALIASES = {"orange": "fire", "blue": "electric", "cold": "steel", "lightning": "electric"}

_STATE = {"trails": [], "afterglows": [], "splits": [], "rains": [], "names": set(), "flash_frames": [],
          "report": {}}


def reset():
    """Forget the deferred registry (trails, splits, rain systems). Call after clearing the scene in tests."""
    for k in ("trails", "afterglows", "splits", "rains", "flash_frames", "sparks", "mb", "warnings"):
        _STATE[k] = []
    _STATE["names"] = set()
    _STATE["report"] = {}


# ================================================================================================ helpers
def _seed(*parts):
    """Deterministic 31-bit seed from any parts (zlib.crc32 of their repr)."""
    return zlib.crc32(":".join(str(p) for p in parts).encode()) & 0x7FFFFFFF


def _rng(*parts):
    return np.random.default_rng(_seed(*parts))


def _color(c):
    """Colour name or RGB tuple -> linear RGB tuple."""
    if isinstance(c, str):
        c = COLORS[_COLOR_ALIASES.get(c, c)] if _COLOR_ALIASES.get(c, c) in COLORS else COLORS[c]
    return tuple(float(x) for x in c[:3])


def act_of(frame):
    """'prologue' | 'act1' | 'act2' | 'act3' | 'epilogue' for a frame (config.ACTS)."""
    for a in config.ACTS:
        if a["start"] <= frame <= a["end"]:
            return a["id"]
    return "act1"


def owner_color(owner, frame):
    """Colour coding (DIRECTION §6) -> (edge_rgb, core_rgb).
    owner 'saint'/'SAINT'/rig: gold (Act I) -> fire-orange (Act II) -> cold steel-blue (Act III+);
    owner 'shinobi': cool white edge with a red core."""
    name = owner if isinstance(owner, str) else getattr(owner, "name", "")
    name = name.lower()
    if "shinobi" in name:
        return COLORS["white"], COLORS["red"]
    act = act_of(frame)
    if act in ("prologue", "act1"):
        return COLORS["gold"], (1.0, 0.80, 0.42)
    if act == "act2":
        return COLORS["fire"], (1.0, 0.66, 0.30)
    return COLORS["steel"], (0.90, 0.93, 0.96)


def _clock():
    """fxclock module, making sure scene['fx_time'] exists (bl_util.film_clock)."""
    return U.film_clock()


def fx_time(frame):
    """fx_time (seconds) at a (fractional) frame - pure python, identical to the keyed clock."""
    return _clock().fx_time_at(frame)


def _collection(kind):
    parent = U.ensure_collection("VFX")
    return U.ensure_collection("VFX_" + kind, parent=parent)


def _shot_prefix(base):
    """'S08_' for names like 'VFX_sparks_700_1' (first 1-4 digit field = the effect's frame -> config.shot_at),
    so every effect object carries its shot id like lane objects do (QC / lane reports); '' otherwise."""
    import re
    if not base.startswith("VFX_") or base.startswith("VFX_src"):
        return ""
    m = re.search(r"_(\d{1,4})(?:_|$)", base)
    if not m:
        return ""
    shot = config.shot_at(int(m.group(1)))
    return (shot["id"] + "_") if shot else ""


def _uname(base):
    """Unique, deterministic object name '<shot>_VFX_<kind>_<frame>_<seed>' (suffix _2, _3 ... on clashes)."""
    base = _shot_prefix(base) + base
    name = base
    i = 2
    while name in _STATE["names"] or bpy.data.objects.get(name) is not None:
        name = f"{base}_{i}"
        i += 1
    _STATE["names"].add(name)
    return name


def _no_shadow(ob):
    """Particles / volumes / emitters never cast shadows (Pipeline rule 5)."""
    ob.visible_shadow = False
    return ob


def _hidden_source(name, verts, faces, collection, material=None, smooth=False, attrs=None):
    """A mesh used only as an instance source: hidden from render/viewport, parked in the collection."""
    ob = bpy.data.objects.get(name)
    if ob is not None:
        return ob
    ob = U.mesh_from_data(name, verts, faces=faces, collection=collection, smooth=smooth,
                          materials=[material] if material else ())
    for k, v in (attrs or {}).items():
        U.add_attribute(ob.data, k, v)
    ob.hide_render = True
    ob.hide_viewport = True
    ob.visible_shadow = False
    return ob


# ------------------------------------------------------------------------------------------------ time curves
MS = 1000.0     # time curves run on fx MILLIseconds: F-curve updates merge keys closer than 0.01 x-units
TIME_EPS_MS = 0.1   # keys lead their frame by 0.1 ms (0.0024 f; 0.019 f at 1/8 slow motion) - float32 safety


def _time_driver(id_owner, data_path, index=-1):
    """Driver whose value is fx_time in milliseconds (simple expression 't*1000', no auto-exec needed), with an
    EMPTY key list (the 5.2 default driver curve carries keys (0,0),(1,1))."""
    fc = time_expr(id_owner, data_path, "t*1000.0", index=index)
    fc.keyframe_points.clear()
    return fc


def time_curve(id_owner, data_path, points, index=-1, interp='LINEAR', frames=True):
    """Drive id_owner.<data_path>[index] by a curve of the film clock: points = [(frame, value[, interp]), ...]
    (frames=True: x converted with fx_time_at; frames=False: x already in fx seconds). A point's interp governs
    the segment AFTER it ('CONSTANT' = hold until the next point -> clean steps without near-duplicate keys).
    Constant extrapolation. Independent of keyframes/NLA and follows slow motion. Returns the F-curve."""
    fc = _time_driver(id_owner, data_path, index)
    ck = _clock()
    pts = []
    for p in points:
        # keys sit 0.1 ms BEFORE their instant: fx_time and key x are float32 (ulp ~0.016 ms at 160 s), so a key
        # placed exactly on a frame could evaluate as 'just before' it and a step would land one frame late
        x = (ck.fx_time_at(p[0]) if frames else float(p[0])) * MS - TIME_EPS_MS
        pts.append((x, float(p[1]), p[2] if len(p) > 2 else interp))
    pts.sort(key=lambda p: p[0])
    xs = []
    for i, (x, y, it) in enumerate(pts):
        if xs and x <= xs[-1] + 1e-3:
            x = xs[-1] + 1e-3        # strictly increasing x
        xs.append(x)
        pts[i] = (x, y, it)
    kps = fc.keyframe_points
    kps.add(len(pts))
    for k, (x, y, it) in zip(kps, pts):
        k.co = (x, y)
        k.interpolation = it
        k.handle_left_type = k.handle_right_type = 'VECTOR'
    fc.extrapolation = 'CONSTANT'
    fc.update()
    return fc


def time_expr(id_owner, data_path, expression, index=-1):
    """Drive a property with a SIMPLE expression of t = fx_time (seconds) - evaluated without Python
    auto-exec (Blender's simple-expression evaluator: + - * / ** min max abs floor sin cos clamp smoothstep ...).
    Raises if the expression is not 'simple' (it would need auto-exec in background renders)."""
    fc = id_owner.driver_add(data_path) if index < 0 else id_owner.driver_add(data_path, index)
    for m in list(fc.modifiers):
        fc.modifiers.remove(m)
    drv = fc.driver
    drv.type = 'SCRIPTED'
    while drv.variables:
        drv.variables.remove(drv.variables[0])
    v = drv.variables.new()
    v.name = "t"
    v.type = 'SINGLE_PROP'
    v.targets[0].id_type = 'SCENE'
    v.targets[0].id = bpy.context.scene
    v.targets[0].data_path = '["fx_time"]'
    if len(expression) > 255:        # Blender stores driver expressions in a 256-char buffer (silently cut)
        raise ValueError(f"time_expr: expression longer than 255 characters ({len(expression)}): {expression}")
    drv.expression = expression
    if not getattr(drv, "is_simple_expression", True):
        raise ValueError(f"time_expr: not a simple expression (needs autoexec): {expression}")
    return fc


def _n(x, nd=4):
    """Compact float literal for driver expressions (<= nd decimals, no trailing zeros)."""
    s = f"{float(x):.{nd}f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _drive_value_node(tree, node_name="FX Time"):
    """Drive a Value node (named node_name) of a shader/GN tree with fx_time."""
    return _clock().drive_node_value(tree, node_name)


# ------------------------------------------------------------------------------------------------ GN helpers
def _gn_object(name, collection, verts=((0.0, 0.0, 0.0),)):
    """A tiny mesh object that carries a GN modifier (the modifier generates everything)."""
    ob = U.mesh_from_data(name, np.asarray(verts, dtype=np.float32), collection=collection)
    _no_shadow(ob)
    return ob


def _fx_gate(nb, geo, t_from, t_to):
    """Switch geometry -> empty outside [t_from, t_to] (fx seconds, Group Input 'Time')."""
    active = nb.bmath('AND', nb.cmp('GREATER_EQUAL', nb.gi['Time'], t_from),
                      nb.cmp('LESS_EQUAL', nb.gi['Time'], t_to))
    return nb.switch(active, None, geo, 'GEOMETRY')


def _finish_gn(ob, ng, **inputs):
    U.gn_modifier(ob, ng, **inputs)
    _clock().drive_gn_input(ob, "Time")
    return ob.modifiers["GN"]


def _drive_rate(ob, input_name="Rate"):
    """Drive a GN input with the film-clock SPEED (fx seconds per real second: 1.0, or the config.TIME_WARP
    factor inside slow-motion windows). Used to scale velocity pre-stretch so slow-motion streaks get shorter."""
    pts = [(config.FRAME_START - 400, 1.0)]
    for a, b, speed in sorted(config.TIME_WARP):
        pts += [(a, float(speed)), (b, 1.0)]
    return time_curve(ob, U.gn_path(ob, input_name), pts, interp='CONSTANT')


def _pool(name, kind, p0, vel, birth, life, *, gravity=-9.81, drag=0.0, instance=None, instances=None,
          pick=None, material=None, size=1.0, shrink=0.0, grow=0.0, stretch=0.0, len0=1.0, align='velocity',
          rot0=None, spin=None, turb=0.0, turb_scale=0.6, turb_speed=0.8, extra_attrs=None, margin_frames=2.0):
    """General fixed-count, film-clock particle pool (Pipeline rules 3+4) - superset of bl_util.gn_ballistic.

    Per slot i (arrays broadcast to n = len(p0)): start p0, velocity vel (m/s), birth (frame), life (frames at
    normal speed), size, optional drag (1/s, linear air drag), rot0/spin (Euler rad, rad/s) and pick (index into
    `instances`, a collection). Motion (tc = clamp(fx_time - birth_t, 0, life_t)):
        drag k > 0 :  x = p0 + g/k*tc + (v - g/k)(1 - e^-k tc)/k      (else ballistic p0 + v tc + g tc^2 / 2)
        + turbulence: 4D-noise offset (amplitude turb m, growing over the first 0.5 s of age)
    Unborn/dead slots have scale 0 (Switch) - the pool never changes size. align:
        'velocity': instance +Z along the current velocity, scale (s, s, s*len0 + stretch*Rate*|v|)
                    (source meshes are modelled with unit length along -Z: head at z=0, tail at z=-1)
        'random'  : Euler rot0 + spin*tc, uniform scale s
        None      : no rotation, uniform scale s
    Size envelope: s = size * (1 - shrink*age01) * min(1, age01/grow) (grow = fraction of life to scale in).
    Instance attributes for shaders (Attribute node, INSTANCER): age01, plus every point attribute (seed01 is
    always present: a per-slot random 0..1). Outside [first birth, last death] (+margin) the modifier outputs
    nothing (dormant, ~0 cost). Returns the object (modifier 'GN': inputs Time + Rate driven)."""
    fxc = _clock()
    p0 = np.asarray(p0, dtype=np.float32).reshape(-1, 3)
    n = len(p0)

    def bc(a, shape, dt=np.float32):
        return np.broadcast_to(np.asarray(a, dtype=dt), shape).copy()
    vel = bc(vel, (n, 3))
    birth = bc(birth, (n,), np.float64)
    life = np.maximum(bc(life, (n,), np.float64), 1e-3)
    size_a = bc(size, (n,))
    uniq = {float(b): fxc.fx_time_at(float(b)) for b in np.unique(birth)}
    birth_t = np.array([uniq[float(b)] for b in birth], dtype=np.float64)
    life_t = life / FPS
    col = _collection(kind)
    ob = U.mesh_from_data(_uname(name), p0, collection=col)
    _no_shadow(ob)
    me = ob.data
    rng = _rng("pool", name, n)
    attrs = dict(vel=(vel, 'FLOAT_VECTOR'), birth_t=(birth_t.astype(np.float32), 'FLOAT'),
                 life_t=(life_t.astype(np.float32), 'FLOAT'), size=(size_a, 'FLOAT'),
                 seed01=(rng.random(n).astype(np.float32), 'FLOAT'))
    use_drag = np.any(np.asarray(drag) > 0)
    if use_drag:
        attrs["drag"] = (np.maximum(bc(drag, (n,)), 0.05), 'FLOAT')
    if align == 'random':
        attrs["rot0"] = (bc(rot0 if rot0 is not None else rng.uniform(0, 2 * math.pi, (n, 3)), (n, 3)),
                         'FLOAT_VECTOR')
        attrs["spin"] = (bc(spin if spin is not None else 0.0, (n, 3)), 'FLOAT_VECTOR')
    if instances is not None:
        attrs["pick"] = (bc(pick if pick is not None else 0, (n,), np.int32), 'INT')
    for k, (v, t) in attrs.items():
        U.add_attribute(me, k, v, t)
    for k, v in (extra_attrs or {}).items():
        U.add_attribute(me, k, v)
    margin = float(margin_frames) / FPS
    act_from = float(birth_t.min() - margin) if n else 0.0
    act_to = float((birth_t + life_t).max() + margin) if n else -1.0

    g = (0.0, 0.0, float(gravity)) if np.ndim(gravity) == 0 else tuple(float(x) for x in gravity)
    ng = U.gn_new_tree("GN_" + ob.name, inputs=[
        ("Time", "FLOAT", 0.0), ("Rate", "FLOAT", 1.0), ("Gravity", "VECTOR", g), ("Instance", "OBJECT"),
        ("Instances", "COLLECTION"), ("Material", "MATERIAL"), ("Shrink", "FLOAT", float(shrink)),
        ("Grow", "FLOAT", float(grow)), ("Stretch", "FLOAT", float(stretch)), ("Len0", "FLOAT", float(len0)),
        ("Turb", "FLOAT", float(turb)), ("Active From", "FLOAT", act_from), ("Active To", "FLOAT", act_to)])
    nb = U.NB(ng)
    gi = nb.gi
    eps = 1e-4
    life_s = nb.attr("life_t")
    t = nb.math('SUBTRACT', gi['Time'], nb.attr("birth_t"))
    tc = nb.math('MINIMUM', nb.math('MAXIMUM', t, 0.0), life_s)
    v = nb.attr("vel", 'FLOAT_VECTOR')
    if use_drag:
        k = nb.attr("drag")
        e = nb.math('EXPONENT', nb.math('MULTIPLY', nb.math('MULTIPLY', k, tc), -1.0))
        inv_k = nb.math('DIVIDE', 1.0, k)
        g_k = nb.vmath('SCALE', gi['Gravity'], scale=inv_k)
        rel = nb.vmath('SUBTRACT', v, g_k)
        disp = nb.vmath('ADD', nb.vmath('SCALE', g_k, scale=tc),
                        nb.vmath('SCALE', rel, scale=nb.math('MULTIPLY', nb.math('SUBTRACT', 1.0, e), inv_k)))
        v_now = nb.vmath('ADD', g_k, nb.vmath('SCALE', rel, scale=e))
    else:
        half_t2 = nb.math('MULTIPLY', nb.math('MULTIPLY', tc, tc), 0.5)
        disp = nb.vmath('ADD', nb.vmath('SCALE', v, scale=tc), nb.vmath('SCALE', gi['Gravity'], scale=half_t2))
        v_now = nb.vmath('ADD', v, nb.vmath('SCALE', gi['Gravity'], scale=tc))
    if turb:
        pos0 = nb.n('GeometryNodeInputPosition')['Position']
        seedv = nb.vmath('SCALE', nb.xyz(nb.attr("seed01"), nb.attr("seed01"), 0.0), scale=37.0)
        nz = nb.noise(vector=nb.vmath('ADD', nb.vmath('SCALE', pos0, scale=turb_scale), seedv),
                      w=nb.math('MULTIPLY', gi['Time'], turb_speed), scale=1.0, detail=1.0, dims='4D')
        amp = nb.math('MULTIPLY', gi['Turb'], nb.math('MINIMUM', nb.math('MULTIPLY', tc, 2.0), 1.0))
        tvec = nb.vmath('SCALE', nb.vmath('SUBTRACT', nz['Color'], (0.5, 0.5, 0.5)), scale=nb.math('MULTIPLY', amp, 2.0))
        disp = nb.vmath('ADD', disp, tvec)
    moved = nb.n('GeometryNodeSetPosition', gi['Geometry'], Offset=disp)
    alive = nb.bmath('AND', nb.cmp('GREATER_EQUAL', t, -eps), nb.cmp('LESS_EQUAL', t, nb.math('ADD', life_s, eps)))
    age01 = nb.math('DIVIDE', tc, nb.math('MAXIMUM', life_s, 1e-6))
    grow_in = nb.math('MINIMUM', 1.0, nb.math('DIVIDE', age01, nb.math('MAXIMUM', gi['Grow'], 1e-4)))
    s_live = nb.math('MULTIPLY', nb.math('MULTIPLY', nb.attr("size"),
                                         nb.math('SUBTRACT', 1.0, nb.math('MULTIPLY', gi['Shrink'], age01))), grow_in)
    s_uni = nb.switch(alive, 0.0, s_live)
    rot = None
    scale = nb.xyz(s_uni, s_uni, s_uni)
    if align == 'velocity':
        rot = nb.n('FunctionNodeAlignRotationToVector', axis='Z', Vector=v_now)['Rotation']
        s_z = nb.math('ADD', nb.math('MULTIPLY', s_uni, gi['Len0']),
                      nb.math('MULTIPLY', nb.math('MULTIPLY', gi['Stretch'], gi['Rate']), nb.vmath('LENGTH', v_now)))
        s_z = nb.switch(alive, 0.0, s_z)
        scale = nb.xyz(s_uni, s_uni, s_z)
    elif align == 'random':
        eul = nb.vmath('ADD', nb.attr("rot0", 'FLOAT_VECTOR'), nb.vmath('SCALE', nb.attr("spin", 'FLOAT_VECTOR'), scale=tc))
        rot = nb.n('FunctionNodeEulerToRotation', eul)['Rotation']
    if instances is not None:
        ci = nb.n('GeometryNodeCollectionInfo', gi['Instances'], True, True, transform_space='ORIGINAL')
        inst = nb.n('GeometryNodeInstanceOnPoints', Points=moved, Instance=ci['Instances'], Pick_Instance=True,
                    Instance_Index=nb.attr("pick", 'INT'), Rotation=rot, Scale=scale)
    else:
        oi = nb.n('GeometryNodeObjectInfo', gi['Instance'], False)
        inst = nb.n('GeometryNodeInstanceOnPoints', Points=moved, Instance=oi['Geometry'], Rotation=rot, Scale=scale)
    stored = nb.store(inst, "age01", age01, 'FLOAT', 'INSTANCE')
    with_mat = nb.n('GeometryNodeSetMaterial', stored, None, gi['Material']) if material is not None else stored
    active = nb.bmath('AND', nb.cmp('GREATER_EQUAL', gi['Time'], gi['Active From']),
                      nb.cmp('LESS_EQUAL', gi['Time'], gi['Active To']))
    nb.link(nb.switch(active, None, with_mat, 'GEOMETRY'), nb.go['Geometry'])
    nb.layout()
    kw = dict(Instance=instance, Material=material)
    if instances is not None:
        kw["Instances"] = instances
    U.gn_modifier(ob, ng, **{k: v for k, v in kw.items() if v is not None})
    fxc.drive_gn_input(ob, "Time")
    _drive_rate(ob)
    ob["vfx_window"] = (float(birth.min()), float((birth + life).max()))
    return ob


# ================================================================================================ shapes
def _needle_source():
    """Spark streak source: 4-sided needle, head at z=0 (tiny rounded tip), widest (1.0) at z=-0.1, tail point at
    z=-1. Vertex attribute 'u' = 0 at the head .. 1 at the tail (shader gradient)."""
    col = _collection("sources")
    v = [(0, 0, 0.03), (0.5, 0, -0.06), (0, 0.5, -0.06), (-0.5, 0, -0.06), (0, -0.5, -0.06), (0, 0, -1.0)]
    f = [(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1), (5, 2, 1), (5, 3, 2), (5, 4, 3), (5, 1, 4)]
    u = np.array([0.0, 0.06, 0.06, 0.06, 0.06, 1.0], np.float32)
    return _hidden_source("VFX_src_needle", v, f, col, attrs={"u": u})


def _glint_source():
    """Contact glint: a small 4-point star (two crossed thin diamonds in XZ and YZ + one in XY) - reads as a
    hot point with rays from any view; used for the spark core (1-2 frames)."""
    col = _collection("sources")
    v, f = [], []
    for ax in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
        a = Vector(ax)
        b = Vector((0, 0, 1)) if ax[2] == 0 else Vector((1, 0, 0))
        c = a.cross(b).normalized()
        base = len(v)
        for p in (a * 0.5, c * 0.07, -a * 0.5, -c * 0.07):
            v.append(tuple(p))
        f.append((base, base + 1, base + 2, base + 3))
        base = len(v)
        for p in (b * 0.5, c * 0.07, -b * 0.5, -c * 0.07):
            v.append(tuple(p))
        f.append((base, base + 1, base + 2, base + 3))
    return _hidden_source("VFX_src_glint", v, f, col, attrs={"u": np.zeros(len(v), np.float32)})


def _shard_sources():
    """Grass-fragment / debris sources (collection VFX_src_shards): a thin blade strip, a bent blade, a small
    plume tuft (for the silver-grass fluff) and a clod. All ~unit size, centred on the origin. Names are prefixed
    s0..s3 because Collection Info 'Separate Children' orders the children ALPHABETICALLY (= pick index)."""
    col = bpy.data.collections.get("VFX_src_shards")
    if col is not None:
        return col
    col = U.ensure_collection("VFX_src_shards", parent=_collection("sources"))
    col.hide_render = False
    # 1) straight blade strip (length 1 along Z, width 0.08)
    v = [(-0.04, 0, -0.5), (0.04, 0, -0.5), (0.03, 0.01, 0.0), (-0.03, 0.01, 0.0), (0.0, 0.03, 0.5)]
    f = [(0, 1, 2, 3), (3, 2, 4)]
    a = _hidden_source("VFX_src_s0_blade", v, f, col)
    # 2) bent blade
    v = [(-0.04, 0, -0.5), (0.04, 0, -0.5), (0.035, 0.06, -0.1), (-0.035, 0.06, -0.1), (0.0, 0.22, 0.4)]
    b = _hidden_source("VFX_src_s1_bent", v, f, col)
    # 3) fluff tuft: three crossed thin diamonds
    v, f = [], []
    for i in range(3):
        ang = i * math.pi / 3
        c, s = math.cos(ang), math.sin(ang)
        base = len(v)
        v += [(0, 0, -0.5), (0.18 * c, 0.18 * s, 0.0), (0, 0, 0.5), (-0.18 * c, -0.18 * s, 0.0)]
        f += [(base, base + 1, base + 2, base + 3)]
    c3 = _hidden_source("VFX_src_s2_tuft", v, f, col)
    # 4) clod: octahedron
    v = [(0.5, 0, 0), (-0.5, 0, 0), (0, 0.4, 0), (0, -0.4, 0), (0, 0, 0.35), (0, 0, -0.35)]
    f = [(0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4), (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)]
    d = _hidden_source("VFX_src_s3_clod", v, f, col)
    mats = (_lit_material("VFX_debris_grass", config.PALETTE["grass_dusk"], (0.45, 0.36, 0.18), translucent=0.45),
            _lit_material("VFX_debris_grass", config.PALETTE["grass_dusk"], (0.45, 0.36, 0.18), translucent=0.45),
            _lit_material("VFX_debris_plume", config.PALETTE["plume"], (0.8, 0.76, 0.66), translucent=0.6),
            _lit_material("VFX_debris_dirt", (0.09, 0.07, 0.05), (0.05, 0.04, 0.03), translucent=0.0))
    for ob, m in zip((a, b, c3, d), mats):   # instance sources must be renderable inside the collection instance
        ob.data.materials.clear()
        ob.data.materials.append(m)
        ob.hide_render = False
        ob.hide_viewport = False
    col.hide_viewport = False
    # keep the source collection itself out of the view layer (only instanced)
    for vl in bpy.context.scene.view_layers:
        lc = _find_layer_collection(vl.layer_collection, col.name)
        if lc is not None:
            lc.exclude = True
    return col


def _find_layer_collection(lc, name):
    if lc.collection.name == name:
        return lc
    for ch in lc.children:
        r = _find_layer_collection(ch, name)
        if r is not None:
            return r
    return None


# ================================================================================================ materials
def _mat(name):
    """Fresh material with an empty node tree + NB builder + output node."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    nt = mat.node_tree
    nt.nodes.clear()
    nb = U.NB(nt)
    out = nb.n('ShaderNodeOutputMaterial')
    return mat, nb, out


def _ramp(nb, fac, stops):
    """Color Ramp node from [(pos, rgb), ...]; returns the Color output socket."""
    r = nb.n('ShaderNodeValToRGB')
    cr = r.node.color_ramp
    while len(cr.elements) > 1:
        cr.elements.remove(cr.elements[-1])
    for i, (pos, rgb) in enumerate(stops):
        el = cr.elements[0] if i == 0 else cr.elements.new(pos)
        el.position = pos
        el.color = (*rgb[:3], 1.0)
    nb.link(fac, U.socket_in(r.node, "Fac"))
    return U.socket_out(r.node, "Color")


def _spark_material(color, strength=1.5):
    """Hot-core emissive spark material: colour from instance age (age01, INSTANCER) and position along the
    streak (u, GEOMETRY): white-hot head/young -> the variant colour -> deep red tail/old. Emission only."""
    key = color if isinstance(color, str) else "c%02x%02x%02x" % tuple(int(255 * c) for c in _color(color))
    name = f"VFX_spark_{key}_{strength:.2f}"
    if bpy.data.materials.get(name):
        return bpy.data.materials[name]
    base = _color(color)
    hot = tuple(min(1.0, 0.62 * c + 0.38) for c in base)
    cool = tuple(c * f for c, f in zip(base, (0.75, 0.35, 0.3)))
    if isinstance(color, str) and _COLOR_ALIASES.get(color, color) in ("steel", "white", "electric"):
        cool = tuple(c * f for c, f in zip(base, (0.45, 0.6, 0.95)))
    mat, nb, out = _mat(name)
    age = U.attribute_node(mat, "age01", 'INSTANCER').outputs["Fac"]
    u = U.attribute_node(mat, "u", 'GEOMETRY').outputs["Fac"]
    fac = nb.math('ADD', nb.math('MULTIPLY', age, 0.75), nb.math('MULTIPLY', u, 0.45), clamp=True)
    colr = _ramp(nb, fac, [(0.0, hot), (0.35, base), (1.0, cool)])
    s = nb.math('MULTIPLY', nb.math('SUBTRACT', 1.0, nb.math('MULTIPLY', age, 0.65)),
                nb.math('SUBTRACT', 1.0, nb.math('MULTIPLY', u, 0.55)))
    em = nb.n('ShaderNodeEmission', Color=colr, Strength=nb.math('MULTIPLY', s, strength))
    nb.link(em, U.socket_in(out.node, "Surface"))
    mat.diffuse_color = (*base, 1.0)
    return mat


def _lit_material(name, c1, c2, translucent=0.4, rough=0.7, emission=0.0):
    """Lit two-sided material for debris / fragments: Diffuse (+ Translucent so backlit bits glow) with a
    per-instance tone between c1 and c2 (seed01, INSTANCER); optional faint self-emission (reads at night)."""
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    mat, nb, out = _mat(name)
    sd = U.attribute_node(mat, "seed01", 'INSTANCER').outputs["Fac"]
    colr = nb.mix(sd, (*c1, 1.0), (*c2, 1.0), data_type='RGBA')
    dif = nb.n('ShaderNodeBsdfDiffuse', Color=colr, Roughness=rough)
    sh = dif
    if translucent > 0:
        tr = nb.n('ShaderNodeBsdfTranslucent', Color=colr)
        sh = nb.n('ShaderNodeMixShader', translucent, dif, tr)
    if emission > 0:
        sh = nb.n('ShaderNodeAddShader', sh, nb.n('ShaderNodeEmission', Color=colr, Strength=emission))
    nb.link(sh, U.socket_in(out.node, "Surface"))
    mat.use_backface_culling = False
    mat.diffuse_color = (*c1, 1.0)
    return mat


def _point_light(name, pos, color, kind, radius=0.05, shadow=False, cutoff=None, window=None):
    """Unshadowed (default) point light in VFX_<kind>; energy is left at 0 - drive it with time_curve().
    window=(f0, f1): the light is hidden from renders outside [f0, f1] (driven hide_render on the film clock, so
    idle effect lights - and the fire ring's shadowed ones - cost nothing in other shots)."""
    ld = bpy.data.lights.new(name, 'POINT')
    ld.color = _color(color)
    ld.energy = 0.0
    ld.shadow_soft_size = radius
    ld.use_shadow = bool(shadow)
    if cutoff:
        ld.use_custom_distance = True
        ld.cutoff_distance = float(cutoff)
    ob = U.new_object(name, ld, _collection(kind))
    ob.location = tuple(pos)
    if window is not None:
        time_curve(ob, "hide_render", [(window[0] - 1.0, 1.0, 'CONSTANT'), (window[0], 0.0, 'CONSTANT'),
                                       (window[1] + 1.0, 1.0, 'CONSTANT')])
    return ob


def _flash_curve(frame, peak, attack=0.0, hold=1.0, decay=3.0):
    """[(frame, value)] for a brief light: 0 just before `frame` (or ramp over `attack`), peak for `hold`
    frames, linear decay to 0 over `decay` frames."""
    f = float(frame)
    pts = [(f - attack, 0.0, 'LINEAR'), (f, peak, 'LINEAR')] if attack > 0 else [(f - 1.0, 0.0, 'CONSTANT'),
                                                                                  (f, peak, 'LINEAR')]
    if hold > 0:
        pts.append((f + hold, peak, 'LINEAR'))
    pts.append((f + hold + decay, 0.0, 'LINEAR'))
    return pts


# ================================================================================================ sparks
def _cone_dirs(rng, n, direction, spread_deg):
    """n unit vectors within a cone of half-angle spread_deg around direction (uniform on the cap)."""
    d = Vector(direction).normalized() if direction is not None and Vector(direction).length > 1e-6 else Vector((0, 0, 1))
    cos_max = math.cos(math.radians(min(179.0, spread_deg)))
    z = rng.uniform(cos_max, 1.0, n)
    phi = rng.uniform(0, 2 * math.pi, n)
    r = np.sqrt(np.maximum(0.0, 1.0 - z * z))
    local = np.column_stack([r * np.cos(phi), r * np.sin(phi), z])
    q = d.to_track_quat('Z', 'Y')
    M = np.array(q.to_matrix())
    return local @ M.T


def _is_target(pos):
    """True for an object / object name / (rig, bone) - i.e. a position to sample later, not coordinates."""
    if isinstance(pos, (bpy.types.Object, str)):
        return True
    return isinstance(pos, (tuple, list)) and len(pos) == 2 and isinstance(pos[1], str)


def _target_pos(t, frame):
    if isinstance(t, str):
        t = bpy.data.objects[t]
    if isinstance(t, (tuple, list)) and isinstance(t[0], str):
        t = (bpy.data.objects[t[0]], t[1])
    return tuple(U.world_pos_of(t, frame))


def _finalize_sparks(scene=None):
    regs = [r for r in _STATE.get("sparks", []) if r["result"] is None]
    with U.muted_modifiers():
        pos = [(_target_pos(r["target"], r["frame"])) for r in regs]
    for r, p in zip(regs, pos):
        r["result"] = sparks(r["frame"], p, **r["kw"])
    return dict(n=len(regs))


def sparks(frame, pos, direction=None, count=60, speed=4.5, life=10, color='gold', scale=1.0, seed=0,
           spread=70.0, light=True, light_energy=None, strength=1.5, gravity=-9.81, core=True, name=None):
    """Blade-clash sparks: a fixed pool of hot, velocity-stretched needles (+ an optional brief light).

    frame: birth frame (float ok); pos: contact point (x, y, z) - or an object / name / (rig, bone) to sample
    at `frame` from the FINAL animation (deferred to finalize()); direction: main ejection direction (None -> up,
    e.g. pass the contact normal or the attacker's swing direction); count / speed (m/s) / life (frames);
    color: 'gold' | 'fire' | 'steel' ('electric', 'blue' alias) | 'white' | (r,g,b); scale scales speeds and
    streak widths together (1 = a normal clash, 1.6 = heavy clash); spread: cone half-angle (deg);
    light: add a brief unshadowed point light (2-4 frames, energy 40*scale W, cutoff 8 m) - also good for the
    blade glint; strength: emission strength of the hot core (Pipeline rule 7: 0.5-1.5, bloom does the rest).
    Sparks are born over ~1 frame, slowed by air drag, pulled by gravity, cool from white-hot to the variant
    colour to deep red and shrink with age. Returns dict(obj, light)."""
    if _is_target(pos):                       # DEFERRED: position sampled from the final animation in finalize()
        reg = dict(frame=float(frame), target=pos, kw=dict(direction=direction, count=count, speed=speed, life=life,
                   color=color, scale=scale, seed=seed, spread=spread, light=light, light_energy=light_energy,
                   strength=strength, gravity=gravity, core=core, name=name), result=None)
        _STATE.setdefault("sparks", []).append(reg)
        return reg
    rng = _rng("sparks", frame, seed, count)
    _STATE.setdefault("mb", []).append(float(frame))        # birth frames -> finalize() -> scene['vfx_mb_frames']
    pos = np.asarray(pos, dtype=np.float64)
    dirs = _cone_dirs(rng, count, direction if direction is not None else (0, 0, 1),
                      spread if direction is not None else 80.0)
    spd = speed * scale * rng.lognormal(0.0, 0.45, count)
    spd *= np.where(rng.random(count) < 0.10, 1.5, 1.0)                     # a few fast outliers
    vel = dirs * spd[:, None]
    birth = float(frame) + rng.uniform(0.0, 1.0, count) ** 2 * 1.2           # most sparks on the contact frame
    lifes = life * rng.uniform(0.35, 1.35, count)
    sizes = 0.0075 * math.sqrt(scale) * rng.uniform(0.6, 1.3, count)
    p0 = pos[None, :] + rng.normal(0, 0.008, (count, 3))
    nm = name or f"VFX_sparks_{int(frame)}_{seed}"
    ob = _pool(nm, "sparks", p0, vel, birth, lifes, gravity=gravity, drag=rng.uniform(2.0, 4.5, count),
               instance=_needle_source(), material=_spark_material(color, strength), size=sizes,
               shrink=0.55, stretch=0.045, len0=3.0, align='velocity')
    core_ob = None
    if core:
        core_ob = _pool(nm + "_core", "sparks", pos[None, :], (0.0, 0.0, 0.0), float(frame), 2.5, gravity=0.0,
                        instance=_glint_source(), material=_spark_material(color, min(2.5, strength * 1.7)),
                        size=0.05 * scale, shrink=0.9, align=None)
    lob = None
    if light:
        e = (light_energy if light_energy is not None else 40.0 * scale)
        lob = _point_light(ob.name + "_L", pos, _color(color), "sparks", radius=0.05, cutoff=8.0,
                           window=(frame - 1, frame + 5))
        time_curve(lob.data, "energy", _flash_curve(frame, e, hold=0.6, decay=3.0))
    return dict(obj=ob, core=core_ob, light=lob)


# ================================================================================================ finalize
def finalize(scene=None):
    """Build everything that needs the finished animation: blade trails (tip/base sampled at 4 subframes per
    frame, inside bl_util.muted_modifiers, ribbons broken at camera cuts), rain splits. Called once by
    build_scene after NLA assembly + secondary motion (Pipeline rule 13). Idempotent per registration.
    Returns a report dict (counts, seconds)."""
    import time as _time
    t0 = _time.time()
    rep = _STATE["report"]
    fin = globals().get("_finalize_sparks")
    if fin:
        rep["sparks"] = fin(scene)
    fin = globals().get("_finalize_trails")
    if fin:
        rep["trails"] = fin(scene)
    fin = globals().get("_finalize_splits")
    if fin:
        rep["splits"] = fin(scene)
    rep["mb_frames"] = _write_mb_frames(scene)
    rep["warnings"] = list(_STATE.get("warnings", []))
    rep["seconds"] = round(_time.time() - t0, 3)
    return rep


# Spark bursts: [birth, birth + 2] want >= MB_BIRTH_STEPS motion-blur steps (EEVEE 1-step motion blur hatches
# tiny, fast, diverging sparks on their first frames). Steps: settings render.mb_steps_sparks.
MB_BIRTH_FRAMES = 3
MB_BIRTH_STEPS = config.MB_STEPS_SPARKS


def _write_mb_frames(scene=None):
    """Merge the registered spark birth frames into ranges and store them on the scene as JSON
    scene['vfx_mb_frames'] = [[f0, f1, steps], ...] (inclusive) - read by mb_frames() / mb_steps_at() in the
    render pass (render_setup.apply_shot_overrides), which travels with scene.blend. Returns the ranges."""
    import json
    sc = scene or bpy.context.scene
    births = sorted({int(math.floor(f)) for f in _STATE.get("mb", [])})
    ranges = []
    for b in births:
        e = b + MB_BIRTH_FRAMES - 1
        if ranges and b <= ranges[-1][1] + 1:
            ranges[-1][1] = max(ranges[-1][1], e)
        else:
            ranges.append([b, e, MB_BIRTH_STEPS])
    sc["vfx_mb_frames"] = json.dumps(ranges)
    return ranges


def mb_frames(scene=None):
    """[[f0, f1, steps], ...] frame ranges (inclusive) that need >= `steps` EEVEE motion-blur steps - the first
    frames of every spark burst (stored on the scene by finalize(); works after loading scene.blend)."""
    import json
    sc = scene or bpy.context.scene
    try:
        return [list(r) for r in json.loads(sc.get("vfx_mb_frames", "[]"))]
    except ValueError:
        return []


def mb_steps_at(frame, scene=None, base=1):
    """Motion-blur steps the vfx lane asks for at `frame`: max(base, steps of any mb_frames() range containing
    it). For render_setup.apply_shot_overrides: E.motion_blur_steps = vfx.mb_steps_at(frame, sc, shot_steps)."""
    f = int(math.floor(float(frame)))
    need = [r[2] for r in mb_frames(scene) if r[0] <= f <= r[1]]
    return max([int(base)] + need)


# ================================================================================================ blade trails
def _as_obj(o):
    """Object | name | (rig, bone) | (rig_name, bone) -> Object or (rig, bone). KeyError if a name is missing."""
    if isinstance(o, str):
        return bpy.data.objects[o]
    if isinstance(o, (tuple, list)) and len(o) == 2 and isinstance(o[1], str):
        return (bpy.data.objects[o[0]] if isinstance(o[0], str) else o[0], o[1])
    return o


def _owner_of(obj, owner=None):
    if owner is not None:
        return owner
    n = getattr(obj, "name", str(obj)).upper()
    return "shinobi" if "SHINOBI" in n else "saint"


def blade_trail(tip_obj, base_obj, f0, f1, color=None, strength=1.0, name=None, owner=None, width=0.72,
                fade=0.15, min_speed=3.0, full_speed=10.0, samples=4, core=None):
    """Blade trail (DEFERRED - built by vfx.finalize() from the final animation).

    tip_obj/base_obj: the blade sockets (objects or names, e.g. 'SAINT_katana_tip' / 'SAINT_katana_base' or the
    spear sockets). [f0, f1]: the frames the blade sweeps (the swing). At finalize the sockets are sampled at
    `samples` subframes per frame (one frame_set per subframe shared by all trails, grass GN muted) into a STATIC
    world-space ribbon between the tip and the point `width` of the way to the base. Per-vertex attributes: t
    (fx seconds of the sample), tend (fx seconds of the next camera cut after it - the trail vanishes at a cut),
    w (0 inner edge .. 1 tip edge), spd (0..1 opacity from the tip speed in fx-time m/s between min_speed and
    full_speed, so slow blade motion leaves nothing). The shader reveals each sample when fx_time passes t and
    fades it over `fade` fx seconds (slow motion => trails hang longer), with a bright band near the edge.
    Colour: DIRECTION §6 owner coding when color is None (elder: gold -> fire-orange -> steel-blue by act;
    shinobi: cool white with a red core); or color=(edge_rgb | name) with optional core=(rgb | name).
    strength: emission of the brightest part (~1.0-1.5; bloom does the rest). Returns the registration dict
    (its 'obj' is filled in by finalize)."""
    own = _owner_of(tip_obj if isinstance(tip_obj, str) else
                    (tip_obj[0] if isinstance(tip_obj, (tuple, list)) else tip_obj), owner)
    edge, core_c = owner_color(own, f0)
    if color is not None:
        edge = _color(color)
        core_c = _color(core) if core is not None else tuple(min(1.0, 0.5 * c + 0.5) for c in edge)
    # body fill follows the ambient level: a faint crescent reads at dusk, at night only the line should remain
    act = act_of(f0)
    body_w = {"prologue": 0.35, "act1": 0.35, "act2": 0.30}.get(act, 0.14)
    if own == "shinobi":
        body_w *= 0.6
    reg = dict(tip=tip_obj, base=base_obj, f0=float(f0), f1=float(f1), edge=edge, core=core_c, strength=float(strength),
               width=float(width), fade=float(fade), vmin=float(min_speed), vmax=float(full_speed),
               samples=max(1, int(samples)), owner=own, body=float(body_w),
               name=name or f"VFX_trail_{own}_{int(f0)}", obj=None)
    _STATE["trails"].append(reg)
    return reg


def _trail_material(edge, core, strength, fade, owner, body_w=0.3):
    """Unlit, ADDITIVE ribbon shader (Transparent + Emission, BLENDED - it only adds light, never darkens):
    a crisp hot line along the tip path + a faint body (weight body_w, lower at night) that falls off toward the
    base; reveal at t, fade over `fade` s (the body faster than the line), gone at the next camera cut (tend).
    Elder: the line keeps the act colour (saturated, moderate emission so AgX does not bleach it to cream).
    Shinobi: white line, faint cool-white body with a thin red heart band (w 0.72-0.84). Driven 'FX Time'."""
    key = "%s_%02x%02x%02x_%02x%02x%02x_%.2f_%.3f_%.2f" % ((owner,) + tuple(int(255 * c) for c in edge)
                                                            + tuple(int(255 * c) for c in core)
                                                            + (strength, fade, body_w))
    name = "VFX_trail_" + key
    if bpy.data.materials.get(name):
        return bpy.data.materials[name]
    mat, nb, out = _mat(name)
    now = nb.n('ShaderNodeValue', name="FX Time")
    t = U.attribute_node(mat, "t", 'GEOMETRY').outputs["Fac"]
    tend = U.attribute_node(mat, "tend", 'GEOMETRY').outputs["Fac"]
    w = U.attribute_node(mat, "w", 'GEOMETRY').outputs["Fac"]
    spd = U.attribute_node(mat, "spd", 'GEOMETRY').outputs["Fac"]
    age = nb.math('SUBTRACT', now.out, t)
    reveal = nb.map_range(age, -0.006, 0.0, 0.0, 1.0)                    # leading edge ~1/4 frame soft
    life = nb.math('SUBTRACT', 1.0, nb.math('DIVIDE', age, fade), clamp=True)
    life_body = nb.math('POWER', life, 2.5)
    life_line = nb.math('POWER', life, 1.2)
    gate = nb.math('MULTIPLY', nb.math('MULTIPLY', reveal, spd), nb.math('LESS_THAN', now.out, tend))
    body = nb.math('MULTIPLY', nb.math('POWER', w, 2.2), float(body_w))
    line = nb.math('MULTIPLY', nb.map_range(w, 0.86, 0.985, 0.0, 1.0, interp='SMOOTHSTEP'),
                   nb.math('SUBTRACT', 1.0, nb.math('MULTIPLY', nb.map_range(w, 0.985, 1.0, 0.0, 1.0), 0.5)))
    if owner == "shinobi":
        hot = (0.9, 0.95, 1.0)
        line_gain = 1.6
        # a thin red heart band inside the faint cool-white body, white line at the tip
        band = nb.math('MULTIPLY', nb.map_range(w, 0.72, 0.76, 0.0, 1.0, interp='SMOOTHSTEP'),
                       nb.math('SUBTRACT', 1.0, nb.map_range(w, 0.80, 0.84, 0.0, 1.0, interp='SMOOTHSTEP')))
        body_col = nb.mix(band, (*edge, 1.0), (*core, 1.0), data_type='RGBA')
        body = nb.math('ADD', body, nb.math('MULTIPLY', band, 0.2))
    else:
        hot = tuple(0.9 * e + 0.1 * c for e, c in zip(edge, core))      # saturated act colour
        line_gain = 1.25
        body_col = (*edge, 1.0)
    e_body = nb.math('MULTIPLY', nb.math('MULTIPLY', body, life_body), strength)
    e_line = nb.math('MULTIPLY', nb.math('MULTIPLY', line, life_line), strength * line_gain)
    em_b = nb.n('ShaderNodeEmission', Color=body_col, Strength=nb.math('MULTIPLY', e_body, gate))
    em_l = nb.n('ShaderNodeEmission', Color=(*hot, 1.0), Strength=nb.math('MULTIPLY', e_line, gate))
    tr = nb.n('ShaderNodeBsdfTransparent')
    add1 = nb.n('ShaderNodeAddShader', em_b, em_l)
    add2 = nb.n('ShaderNodeAddShader', tr, add1)
    nb.link(add2, U.socket_in(out.node, "Surface"))
    mat.surface_render_method = 'BLENDED'
    mat.use_backface_culling = False
    try:
        mat.use_transparency_overlap = False
    except AttributeError:
        pass
    mat.diffuse_color = (*edge, 1.0)
    _drive_value_node(mat.node_tree, "FX Time")
    return mat


def _gate_group():
    """Shared GN group 'VFX_gate': passes the geometry only while From <= Time <= To (fx seconds)."""
    ng = bpy.data.node_groups.get("VFX_gate")
    if ng is not None:
        return ng
    ng = U.gn_new_tree("VFX_gate", inputs=[("Time", "FLOAT", 0.0), ("From", "FLOAT", 0.0), ("To", "FLOAT", 0.0)])
    nb = U.NB(ng)
    active = nb.bmath('AND', nb.cmp('GREATER_EQUAL', nb.gi['Time'], nb.gi['From']),
                      nb.cmp('LESS_EQUAL', nb.gi['Time'], nb.gi['To']))
    nb.link(nb.switch(active, None, nb.gi['Geometry'], 'GEOMETRY'), nb.go['Geometry'])
    return ng


def _add_gate(ob, t_from, t_to):
    """Make a mesh object self-hiding outside [t_from, t_to] (fx seconds) - no keys involved."""
    mod = U.gn_modifier(ob, _gate_group(), name="GN", From=float(t_from), To=float(t_to))
    _clock().drive_gn_input(ob, "Time")
    return mod


def _catmull_rom(P, k):
    """Uniform Catmull-Rom through the rows of P (n,3), k samples per interval (+ the last point)."""
    P = np.asarray(P, dtype=np.float64)
    n = len(P)
    if n < 2 or k <= 1:
        return P.copy()
    ext = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    out = []
    for i in range(n - 1):
        p0, p1, p2, p3 = ext[i], ext[i + 1], ext[i + 2], ext[i + 3]
        for j in range(k):
            u = j / k
            u2, u3 = u * u, u * u * u
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u2
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * u3))
    out.append(P[-1])
    return np.array(out)


def _cut_frames(scene):
    """Frames where the active camera changes (timeline markers bound to cameras), sorted."""
    return sorted({m.frame for m in scene.timeline_markers if m.camera is not None})


def _finalize_trails(scene=None):
    """Sample every registered trail (shared subframes) and build its ribbon. Returns a report."""
    import bisect
    import time as _time
    sc = scene or bpy.context.scene
    regs = []
    missing = []
    for r in _STATE["trails"]:
        if r["obj"] is not None:
            continue
        try:                                   # sockets are resolved now (names may be registered early)
            r["tip"], r["base"] = _as_obj(r["tip"]), _as_obj(r["base"])
            regs.append(r)
        except KeyError as ex:
            r["obj"] = False
            missing.append(f"{r['name']}: {ex}")
            print(f"[vfx] blade_trail {r['name']} skipped - socket not found: {ex}")
    if not regs:
        return dict(n=0, missing=missing)
    t0 = _time.time()
    ck = _clock()
    cuts = _cut_frames(sc)
    cut_t = [ck.fx_time_at(c) for c in cuts]
    need = {}
    for r in regs:
        n = r["samples"]
        fr = np.arange(r["f0"] * n, r["f1"] * n + 0.5) / n
        r["_frames"] = [round(float(x), 4) for x in fr]
        for x in r["_frames"]:
            need.setdefault(x, []).append(r)
    pos = {id(r): {} for r in regs}
    keep = sc.frame_current
    with U.muted_modifiers():
        for x in sorted(need):
            U.frame_set(x, sc)
            for r in need[x]:
                pos[id(r)][x] = (np.array(U.world_pos_of(r["tip"])), np.array(U.world_pos_of(r["base"])))
    sc.frame_set(keep)
    built = 0
    for r in regs:
        fr = r["_frames"]
        P = pos[id(r)]
        tips = np.array([P[x][0] for x in fr])
        bases = np.array([P[x][1] for x in fr])
        ts = np.array([ck.fx_time_at(x) for x in fr])
        inner = tips + (bases - tips) * r["width"]
        dt = np.maximum(np.diff(ts), 1e-6)
        step = np.linalg.norm(np.diff(tips, axis=0), axis=1)
        v = np.concatenate([[step[0] / dt[0] if len(step) else 0.0], step / dt])
        v = np.convolve(np.pad(v, 1, mode='edge'), [0.25, 0.5, 0.25], mode='valid')   # light smoothing
        spd = np.clip((v - r["vmin"]) / max(1e-6, r["vmax"] - r["vmin"]), 0.0, 1.0)
        spd = spd * spd * (3 - 2 * spd)
        # breaks: camera cuts between samples, teleports (> 1.2 m per subframe)
        brk = np.zeros(len(fr), bool)
        for i in range(1, len(fr)):
            if bisect.bisect_right(cuts, fr[i - 1]) != bisect.bisect_right(cuts, fr[i]):
                brk[i] = True
            if step[i - 1] > 1.2:
                brk[i] = True
        tend = np.array([cut_t[j] if j < len(cut_t) else 1e6
                         for j in (bisect.bisect_right(cuts, x) for x in fr)])
        verts, faces, at_t, at_te, at_w, at_s = [], [], [], [], [], []
        starts = [0] + [i for i in range(1, len(fr)) if brk[i]] + [len(fr)]
        for a0, a1 in zip(starts[:-1], starts[1:]):
            if a1 - a0 < 2:
                continue
            T = _catmull_rom(tips[a0:a1], 3)
            I = _catmull_rom(inner[a0:a1], 3)
            m = len(T)
            lin = np.linspace(0, a1 - a0 - 1, m)
            tt = np.interp(lin, np.arange(a1 - a0), ts[a0:a1])
            ss = np.interp(lin, np.arange(a1 - a0), spd[a0:a1])
            te = np.interp(lin, np.arange(a1 - a0), tend[a0:a1])
            b = len(verts)
            for i in range(m):
                verts += [tuple(I[i]), tuple(T[i])]
                at_t += [tt[i], tt[i]]
                at_te += [te[i], te[i]]
                at_w += [0.0, 1.0]
                at_s += [ss[i], ss[i]]
                if i > 0:
                    a = b + 2 * (i - 1)
                    faces.append((a, a + 2, a + 3, a + 1))
        if not faces:
            r["obj"] = False
            continue
        mat = _trail_material(r["edge"], r["core"], r["strength"], r["fade"], r["owner"], r.get("body", 0.3))
        ob = U.mesh_from_data(_uname(r["name"]), verts, faces=faces, collection=_collection("trails"),
                              materials=[mat])
        me = ob.data
        U.add_attribute(me, "t", np.array(at_t, np.float32), 'FLOAT')
        U.add_attribute(me, "tend", np.array(at_te, np.float32), 'FLOAT')
        U.add_attribute(me, "w", np.array(at_w, np.float32), 'FLOAT')
        U.add_attribute(me, "spd", np.array(at_s, np.float32), 'FLOAT')
        _no_shadow(ob)
        _add_gate(ob, ts[0] - 0.05, min(ts[-1] + r["fade"] + 0.05, float(tend.max())))
        r["obj"] = ob
        built += 1
    return dict(n=built, subframes=len(need), seconds=round(_time.time() - t0, 3), missing=missing)


# ================================================================================================ flash ring
def _annulus_source(name, r_in, r_out, seg=96):
    """Flat ring in XY (normal +Z) with vertex attribute 'rr' 0 (inner edge) .. 1 (outer edge)."""
    col = _collection("sources")
    a = np.linspace(0, 2 * math.pi, seg + 1)                 # duplicated seam vertex: 'ang' runs 0..1 cleanly
    rings = [(r_in + q * (r_out - r_in), q) for q in (0.0, 0.35, 0.7, 0.88, 1.0)]
    v, rr, ang = [], [], []
    for r, q in rings:
        for i, x in enumerate(a):
            v.append((r * math.cos(x), r * math.sin(x), 0.0))
            rr.append(q)
            ang.append(i / seg)
    f = []
    n = seg + 1
    for k in range(len(rings) - 1):
        for i in range(seg):
            f.append((k * n + i, k * n + i + 1, (k + 1) * n + i + 1, (k + 1) * n + i))
    return _hidden_source(name, v, f, col, attrs={"rr": np.array(rr, np.float32), "ang": np.array(ang, np.float32)})


def _star_source(name="VFX_src_star"):
    """Screen-plane star glint (XY plane): long horizontal ray, shorter vertical, two short diagonals. Vertex
    attribute 'rr' = 1 at the centre .. 0 at the ray tips."""
    col = _collection("sources")
    v, f, rr = [], [], []
    for ang, length, wid in ((0, 1.0, 0.022), (90, 0.62, 0.02), (45, 0.26, 0.016), (135, 0.26, 0.016)):
        c, s_ = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        d = Vector((c, s_, 0))
        n = Vector((-s_, c, 0))
        b = len(v)
        for p, q in ((d * length, 0.0), (n * wid, 1.0), (-d * length, 0.0), (-n * wid, 1.0)):
            v.append(tuple(p))
            rr.append(q)
        f.append((b, b + 1, b + 2, b + 3))
    return _hidden_source(name, v, f, col, attrs={"rr": np.array(rr, np.float32)})


def _glow_material(name, color, strength, profile="ring"):
    """Additive unlit material for billboard glows: strength * fade(INSTANCER) * profile(rr, GEOMETRY)."""
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    mat, nb, out = _mat(name)
    rr = U.attribute_node(mat, "rr", 'GEOMETRY').outputs["Fac"]
    fade = U.attribute_node(mat, "fade", 'INSTANCER').outputs["Fac"]
    if profile == "ring":        # a HAIRLINE at the outer edge (no inner haze), broken up along the angle as it ages
        prof = nb.math('MULTIPLY', nb.math('POWER', rr, 12.0), nb.map_range(rr, 0.985, 1.0, 1.0, 0.3))
        ang = U.attribute_node(mat, "ang", 'GEOMETRY').outputs["Fac"]
        age = U.attribute_node(mat, "age", 'INSTANCER').outputs["Fac"]
        rnd = nb.n('ShaderNodeObjectInfo')['Random']
        # periodic noise around the ring (4D noise on the unit circle -> no seam)
        cx = nb.math('COSINE', nb.math('MULTIPLY', ang, 2 * math.pi))
        cy = nb.math('SINE', nb.math('MULTIPLY', ang, 2 * math.pi))
        nz = nb.noise(vector=nb.xyz(cx, cy, 0.0), w=nb.math('MULTIPLY', rnd, 20.0), scale=2.2, detail=3.0,
                      roughness=0.55, dims='4D')
        keep = nb.map_range(nb.math('SUBTRACT', nz['Fac'], nb.math('MULTIPLY', age, 0.75)), 0.12, 0.3, 0.0, 1.0,
                            interp='SMOOTHSTEP')
        vary = nb.map_range(nz['Fac'], 0.3, 0.7, 0.55, 1.25)
        prof = nb.math('MULTIPLY', prof, nb.math('MULTIPLY', keep, vary))
    else:                        # star: bright centre, thin tips
        prof = nb.math('POWER', rr, 1.5)
    em = nb.n('ShaderNodeEmission', Color=(*_color(color), 1.0),
              Strength=nb.math('MULTIPLY', nb.math('MULTIPLY', prof, fade), strength))
    add = nb.n('ShaderNodeAddShader', nb.n('ShaderNodeBsdfTransparent'), em)
    nb.link(add, U.socket_in(out.node, "Surface"))
    mat.surface_render_method = 'BLENDED'
    mat.use_backface_culling = False
    mat.diffuse_color = (*_color(color), 1.0)
    return mat


def flash_ring(frame, pos, radius=0.6, color='white', duration=10, strength=2.0, star=0.15, light=True,
               light_energy=150.0, seed=0, normal=None, name=None):
    """Perfect-deflect flash (S13): a restrained white HAIRLINE ring expanding to `radius` (ease-out; 0.5-0.7 m
    for the S13 medium close-up) over `duration` frames of fx time (the S13 slow motion stretches it) and gone
    by 60 % of it, plus a small star glint (`star` = ray length in m, <= 0.35; 0 = none) that lives on REAL
    frames only (1 -> 0.5 -> 0.15 over 3 frames, also inside the slow motion) - bloom on the glint does the rest.
    Local only: the brief light is unshadowed (light_energy W, ~2 frames, cutoff 10 m), well inside the
    DIRECTION §5 budget (<= 40 % exposure lift for 2 f is the whole-frame limit; any global lift is a
    render_setup/compositor decision). The ring faces the ACTIVE camera (GN Active Camera) unless `normal` lays it
    in a fixed world plane (e.g. the blade-cross normal - a more physical read); its line breaks up along the
    circumference (seeded noise) as it fades, so it never reads as a UI circle. Emission `strength` ~2 (a
    hairline needs a little more to bloom - documented exception to rule 7). Returns dict(obj, light)."""
    fxc = _clock()
    t0 = fxc.fx_time_at(frame)
    T = duration / FPS
    col = _collection("flash")
    nm = _uname(name or f"VFX_flash_ring_{int(frame)}_{seed}")
    ob = U.mesh_from_data(nm, [tuple(pos)], collection=col)
    _no_shadow(ob)
    ring_src = _annulus_source("VFX_src_ring_thin", 0.93, 1.0)
    star_src = _star_source()
    ring_mat = _glow_material(f"VFX_flash_hairline_{color}", color, strength, "ring")
    star_mat = _glow_material(f"VFX_flash_star_{color}", color, min(2.5, strength * 1.2), "star")
    ng = U.gn_new_tree("GN_" + nm, inputs=[("Time", "FLOAT", 0.0), ("T0", "FLOAT", t0), ("Dur", "FLOAT", T),
                                           ("Radius", "FLOAT", float(radius)), ("Star", "FLOAT", float(min(star, 0.35))),
                                           ("StarEnv", "FLOAT", 0.0), ("Ring", "OBJECT"), ("StarObj", "OBJECT"),
                                           ("RingMat", "MATERIAL"), ("StarMat", "MATERIAL")])
    nb = U.NB(ng)
    gi = nb.gi
    t = nb.math('SUBTRACT', gi['Time'], gi['T0'])
    a = nb.math('DIVIDE', t, gi['Dur'])
    ac = nb.math('MINIMUM', nb.math('MAXIMUM', a, 0.0), 1.0)
    alive = nb.bmath('AND', nb.cmp('GREATER_EQUAL', a, 0.0), nb.cmp('LESS_EQUAL', a, 0.62))
    om = nb.math('SUBTRACT', 1.0, ac)
    ease = nb.math('SUBTRACT', 1.0, nb.math('MULTIPLY', om, nb.math('MULTIPLY', om, om)))       # out-cubic
    r_s = nb.math('MULTIPLY', gi['Radius'], nb.math('ADD', 0.12, nb.math('MULTIPLY', ease, 0.88)))
    r_s = nb.switch(alive, 0.0, r_s)
    gone = nb.math('SUBTRACT', 1.0, nb.math('MINIMUM', 1.0, nb.math('DIVIDE', ac, 0.6)))        # gone at 60 %
    ring_fade = nb.math('MULTIPLY', nb.math('POWER', gone, 1.5), nb.map_range(a, 0.0, 0.04, 0.0, 1.0))
    # star: envelope on REAL frames (a GN input driven by a frame-keyed time curve), shrinking as it fades
    env = gi['StarEnv']
    st_s = nb.math('MULTIPLY', gi['Star'], nb.math('POWER', env, 0.5))
    cam = nb.n('GeometryNodeInputActiveCamera')
    ci = nb.n('GeometryNodeObjectInfo', cam, False, transform_space='ORIGINAL')
    rot = ci['Rotation']
    ring_rot = rot if normal is None else \
        nb.n('FunctionNodeAlignRotationToVector', axis='Z', Vector=tuple(Vector(normal).normalized()))['Rotation']
    ring_i = nb.n('GeometryNodeInstanceOnPoints', Points=gi['Geometry'],
                  Instance=nb.n('GeometryNodeObjectInfo', gi['Ring'], False)['Geometry'],
                  Rotation=ring_rot, Scale=nb.xyz(r_s, r_s, r_s))
    ring_i = nb.store(ring_i, "fade", ring_fade, 'FLOAT', 'INSTANCE')
    ring_i = nb.store(ring_i, "age", ac, 'FLOAT', 'INSTANCE')
    ring_i = nb.n('GeometryNodeSetMaterial', ring_i, None, gi['RingMat'])
    star_i = nb.n('GeometryNodeInstanceOnPoints', Points=gi['Geometry'],
                  Instance=nb.n('GeometryNodeObjectInfo', gi['StarObj'], False)['Geometry'],
                  Rotation=rot, Scale=nb.xyz(st_s, st_s, st_s))
    star_i = nb.store(star_i, "fade", env, 'FLOAT', 'INSTANCE')
    star_i = nb.n('GeometryNodeSetMaterial', star_i, None, gi['StarMat'])
    joined = nb.n('GeometryNodeJoinGeometry', star_i, ring_i)
    nb.link(_fx_gate(nb, joined, nb.math('SUBTRACT', gi['T0'], 0.1), nb.math('ADD', nb.math('ADD', gi['T0'], gi['Dur']), 0.1)),
            nb.go['Geometry'])
    nb.layout()
    U.gn_modifier(ob, ng, Ring=ring_src, StarObj=star_src, RingMat=ring_mat, StarMat=star_mat)
    fxc.drive_gn_input(ob, "Time")
    f = float(frame)
    time_curve(ob, U.gn_path(ob, "StarEnv"), [(f - 1.0, 0.0, 'CONSTANT'), (f, 1.0, 'CONSTANT'),
                                              (f + 1.0, 0.5, 'CONSTANT'), (f + 2.0, 0.15, 'CONSTANT'),
                                              (f + 3.0, 0.0, 'CONSTANT')])
    lob = None
    if light:
        lob = _point_light(nm + "_L", pos, color, "flash", radius=0.1, cutoff=10.0, window=(frame - 1, frame + 4))
        time_curve(lob.data, "energy", _flash_curve(frame, light_energy, hold=1.0, decay=2.0))
    ob["vfx_window"] = (float(frame), float(frame) + float(duration))
    return dict(obj=ob, light=lob)


# ================================================================================================ volumes
def _volume_box(name, kind, center, size, f0, f1, shape="ball", color=(0.5, 0.5, 0.5), density=1.0,
                anisotropy=0.3, noise_scale=1.2, detail=3.0, rise=0.6, expand=1.0, evolve=0.35,
                emission=None, emission_strength=0.0, fade_in=0.08, fade_out=0.45, ring_radius=0.6,
                ring_width=0.18, wind=(0.0, 0.0), seed=0, grow_frames=None, ring_h=(0.25, 0.55),
                contrast=(0.42, 0.72), noise2=0.0, squash=1.25, glow_h=0.6, flare=0.0):
    """Mesh-box volume (Pipeline rule 6: never World > Volume) with a procedural, fx_time-driven density.
    The box (object scale = size/2, mesh = unit cube +-1) spans center +- size/2; local coords q in [-1,1]^3.
      density = density * shape(q, age01) * noise(world_m * noise_scale + advection, W = t*evolve) * envelope
    shapes: 'ball' (expanding puff: radius 0.3 -> expand over life; squash > 1 flattens it), 'ring' (horizontal
    ring of radius ring_radius*expand, width ring_width, hugging the ground and rising from ring_h[0] to
    ring_h[0]+ring_h[1] of the box height), 'column' (rising column: horizontal
    falloff, density fed from the bottom), 'ringcol' (column over a ring: fire-ring steam band), 'slab'
    (fills the box, soft edges), 'sheet' (thin vertical sheet, local X thin, thickening). Advection: rise (m/s up) +
    wind (m/s). Envelope: fade_in / fade_out fractions
    of [f0, f1] (fx time). Noise -> density through map_range(contrast) (narrower = crisper edges); noise2 > 0
    adds a second, finer octave (x noise2 frequency). Optional emission (colour, strength) weighted toward the
    bottom of the box, falling off over the lowest glow_h of its height (glow from embers / flames beneath).
    flare > 0 widens a 'column' upward (a plume). visible_shadow False. Returns the object."""
    fxc = _clock()
    t0, t1 = fxc.fx_time_at(f0), fxc.fx_time_at(f1)
    col = _collection(kind)
    nm = _uname(name)
    v = [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    mat, nb, out = _mat("VFX_vol_" + nm)
    ob = U.mesh_from_data(nm, v, faces=faces, collection=col, materials=[mat])
    ob.location = tuple(center)
    ob.scale = tuple(0.5 * float(x) for x in (size if np.ndim(size) else (size, size, size)))
    _no_shadow(ob)
    for attr in ("visible_diffuse", "visible_glossy"):
        if hasattr(ob, attr):
            setattr(ob, attr, False)
    sx, sy, sz = ob.scale
    now = nb.n('ShaderNodeValue', name="FX Time")
    t = nb.math('SUBTRACT', now.out, t0)
    age = nb.math('DIVIDE', t, max(1e-4, t1 - t0))
    agec = nb.math('MINIMUM', nb.math('MAXIMUM', age, 0.0), 1.0)
    env = nb.math('MULTIPLY', nb.map_range(age, 0.0, max(1e-3, fade_in), 0.0, 1.0, interp='SMOOTHSTEP'),
                  nb.map_range(age, 1.0 - fade_out, 1.0, 1.0, 0.0, interp='SMOOTHSTEP'))
    tc = nb.n('ShaderNodeTexCoord')
    q = tc['Object']
    qs = nb.sep(q)
    qx, qy, qz = qs['X'], qs['Y'], qs['Z']
    zn = nb.math('MULTIPLY', nb.math('ADD', qz, 1.0), 0.5)                  # 0 bottom .. 1 top
    rxy = nb.math('SQRT', nb.math('ADD', nb.math('MULTIPLY', qx, qx), nb.math('MULTIPLY', qy, qy)))
    grow = agec if grow_frames is None else nb.math('MINIMUM', 1.0, nb.math(
        'DIVIDE', nb.math('MAXIMUM', t, 0.0), max(1e-3, grow_frames / FPS)))
    eo = nb.math('SUBTRACT', 1.0, nb.math('POWER', nb.math('SUBTRACT', 1.0, grow), 3.0))   # out-cubic 0..1
    if shape == "ball":         # a puff born low (centre near the bottom) that swells and rises to the middle
        R = nb.math('ADD', 0.3, nb.math('MULTIPLY', eo, 0.62 * expand))
        lift = nb.math('MULTIPLY', nb.math('SUBTRACT', 1.0, eo), -0.5)
        qb = nb.vmath('SUBTRACT', q, nb.xyz(0.0, 0.0, lift))
        r = nb.vmath('LENGTH', nb.vmath('MULTIPLY', qb, (1.0, 1.0, float(squash))))
        shp = nb.map_range(nb.math('DIVIDE', r, R), 0.35, 1.0, 1.0, 0.0, interp='SMOOTHSTEP')
    elif shape == "ring":
        R = nb.math('MULTIPLY', ring_radius, nb.math('ADD', 0.25, nb.math('MULTIPLY', eo, 0.75 * expand)))
        wdt = nb.math('ADD', ring_width, nb.math('MULTIPLY', eo, ring_width * 1.2))
        d = nb.math('ABSOLUTE', nb.math('SUBTRACT', rxy, R))
        h = nb.math('ADD', float(ring_h[0]), nb.math('MULTIPLY', eo, float(ring_h[1])))
        shp = nb.math('MULTIPLY', nb.map_range(nb.math('DIVIDE', d, wdt), 0.3, 1.0, 1.0, 0.0, interp='SMOOTHSTEP'),
                      nb.map_range(zn, 0.0, h, 1.0, 0.0, interp='SMOOTHSTEP'))
    elif shape in ("column", "ringcol"):
        if shape == "column":           # flare > 0: narrower at the bottom (a plume widening as it rises)
            rw = nb.math('DIVIDE', rxy, nb.math('ADD', 1.0 - float(flare), nb.math('MULTIPLY', zn, float(flare))))
            hx = nb.map_range(rw, 0.2, 0.95, 1.0, 0.0, interp='SMOOTHSTEP')
        else:
            d = nb.math('ABSOLUTE', nb.math('SUBTRACT', rxy, ring_radius))
            hx = nb.map_range(nb.math('DIVIDE', d, nb.math('ADD', ring_width, nb.math('MULTIPLY', zn, ring_width))),
                              0.3, 1.0, 1.0, 0.0, interp='SMOOTHSTEP')
        # the column fills upward from the bottom at the rise speed (front at zn = rise*t / height)
        front = nb.math('DIVIDE', nb.math('MULTIPLY', nb.math('MAXIMUM', t, 0.0), rise), 2.0 * sz)
        vz = nb.math('MULTIPLY', nb.map_range(nb.math('SUBTRACT', zn, front), -0.25, 0.05, 1.0, 0.0,
                                              interp='SMOOTHSTEP'),
                     nb.map_range(zn, 0.55, 1.0, 1.0, 0.0, interp='SMOOTHSTEP'))
        shp = nb.math('MULTIPLY', hx, vz)
    elif shape == "sheet":        # thin vertical sheet (local X = the thin axis) that thickens over its life
        thick = nb.math('ADD', 0.15, nb.math('MULTIPLY', eo, 0.85))
        shp = nb.math('MULTIPLY', nb.map_range(nb.math('DIVIDE', nb.math('ABSOLUTE', qx), thick), 0.3, 1.0, 1.0, 0.0,
                                               interp='SMOOTHSTEP'),
                      nb.math('MULTIPLY', nb.map_range(nb.math('ABSOLUTE', qy), 0.45, 1.0, 1.0, 0.0, interp='SMOOTHSTEP'),
                              nb.map_range(nb.math('ABSOLUTE', qz), 0.2, 1.0, 1.0, 0.0, interp='SMOOTHSTEP')))
    else:                                                                   # slab
        shp = nb.math('MULTIPLY', nb.map_range(rxy, 0.7, 1.0, 1.0, 0.0, interp='SMOOTHSTEP'),
                      nb.map_range(nb.math('ABSOLUTE', qz), 0.6, 1.0, 1.0, 0.0, interp='SMOOTHSTEP'))
    # noise in metres, advected
    pm = nb.vmath('MULTIPLY', q, (sx, sy, sz))
    adv = nb.vmath('SCALE', (-float(wind[0]), -float(wind[1]), -float(rise)), scale=t)
    rs = (_seed("vol", nm, seed) % 1000) * 0.137
    nz = nb.noise(vector=nb.vmath('ADD', nb.vmath('SCALE', nb.vmath('ADD', pm, adv), scale=noise_scale), (rs, rs, 0.0)),
                  w=nb.math('MULTIPLY', now.out, evolve), scale=1.0, detail=detail, roughness=0.6, dims='4D')
    fac = nz['Fac']
    if noise2 > 0:              # a second, finer octave breaks up the edges (dust / mist detail)
        nz2 = nb.noise(vector=nb.vmath('ADD', nb.vmath('SCALE', nb.vmath('ADD', pm, adv), scale=noise_scale * noise2),
                                       (rs + 17.0, rs, 3.0)),
                       w=nb.math('MULTIPLY', now.out, evolve * 1.7), scale=1.0, detail=2.0, roughness=0.5, dims='4D')
        fac = nb.math('ADD', nb.math('MULTIPLY', fac, 0.68), nb.math('MULTIPLY', nz2['Fac'], 0.32))
    nd = nb.map_range(fac, float(contrast[0]), float(contrast[1]), 0.0, 1.0)
    dens = nb.math('MULTIPLY', nb.math('MULTIPLY', shp, nd), nb.math('MULTIPLY', env, float(density)))
    pv = nb.n('ShaderNodeVolumePrincipled')
    nb.set(U.socket_in(pv.node, "Color"), (*_color(color), 1.0))
    nb.set(U.socket_in(pv.node, "Density"), dens)
    nb.set(U.socket_in(pv.node, "Anisotropy"), float(anisotropy))
    if emission is not None and emission_strength > 0:
        nb.set(U.socket_in(pv.node, "Emission Color"), (*_color(emission), 1.0))
        glow = nb.math('MULTIPLY', nb.map_range(zn, 0.0, float(glow_h), 1.0, 0.03, interp='SMOOTHSTEP'),
                       nb.math('MULTIPLY', nb.math('MULTIPLY', nd, env), shp))   # masked by the shape (was box-wide)
        nb.set(U.socket_in(pv.node, "Emission Strength"), nb.math('MULTIPLY', glow, float(emission_strength)))
    nb.link(pv, U.socket_in(out.node, "Volume"))
    _drive_value_node(mat.node_tree, "FX Time")
    _add_gate(ob, t0 - 0.05, t1 + 0.05)
    ob["vfx_window"] = (float(f0), float(f1))
    return ob


# ================================================================================================ grass / dust
_PICK_BLADE, _PICK_BENT, _PICK_TUFT, _PICK_CLOD = 0, 1, 2, 3


def grass_burst(frame, pos, direction=(0.0, 0.0, 1.0), count=80, seed=0, speed=3.5, spread=55.0, life=40,
                fluff=0.2, scale=1.0, name=None):
    """Cut grass bursting from pos (a foot plant, a low sweep, a slam through the grass): lit blade fragments
    (spinning, fluttering, drag) + silver-grass plume fluff that floats and drifts (high drag, low gravity,
    turbulence). Fixed pool, seeded; materials are lit (diffuse + translucent: backlit fragments glow at dusk).
    direction: main throw direction (cone half-angle `spread`); fluff: fraction of plume tufts (keep <= 0.2
    for dodges/landings - big white plume clouds would evoke the deny-listed 'feather-burst dodges'); life:
    frames for the blades (fluff lives ~2.5x longer). Spawn at foot / grass level only (pos z <= ~1.2 m), never
    at body height. Grass SHEAR (S11) belongs to environment.grass_effect. Returns the pool object."""
    if float(pos[2]) > 1.3:
        print(f"[vfx] WARNING grass_burst @{frame}: pos z={pos[2]:.2f} m is above the grass (spawn at foot level)")
    rng = _rng("grass_burst", frame, seed, count)
    n_f = int(round(count * fluff))
    n_b = count - n_f
    dirs = _cone_dirs(rng, count, direction, spread)
    spd = speed * scale * np.concatenate([rng.uniform(0.35, 1.0, n_b), rng.uniform(0.25, 0.7, n_f)])
    vel = dirs * spd[:, None]
    birth = float(frame) + rng.uniform(0.0, 2.0, count)
    lifes = np.concatenate([life * rng.uniform(0.7, 1.3, n_b), 2.5 * life * rng.uniform(0.7, 1.3, n_f)])
    sizes = np.concatenate([rng.uniform(0.08, 0.22, n_b), rng.uniform(0.04, 0.075, n_f)]) * scale
    drag = np.concatenate([rng.uniform(1.5, 3.0, n_b), rng.uniform(4.0, 6.5, n_f)])
    pick = np.concatenate([rng.choice([_PICK_BLADE, _PICK_BENT], n_b), np.full(n_f, _PICK_TUFT)]).astype(np.int32)
    spin = np.concatenate([rng.uniform(-14, 14, (n_b, 3)), rng.uniform(-2.5, 2.5, (n_f, 3))])
    # gravity per slot is not supported by the pool: light fluff = strong drag (terminal velocity g/k ~ 0.3 m/s)
    p0 = np.asarray(pos, np.float64)[None, :] + rng.normal(0, 0.06 * scale, (count, 3))
    ob = _pool(name or f"VFX_grass_burst_{int(frame)}_{seed}", "grass", p0, vel, birth, lifes, gravity=-2.2,
               drag=drag, instances=_shard_sources(), pick=pick, size=sizes, shrink=0.15, align='random',
               spin=spin, turb=0.22 * scale, turb_scale=0.8, turb_speed=0.9)
    return ob


def dust_burst(frame, pos, radius=1.0, seed=0, color='dust', density=6.0, life=48, debris=True, rise=None,
               low=None, name=None):
    """Dust + chaff kicked up through the grass: a billowing volume (noise density on fx_time, two octaves,
    crisp edges) + optional clods and grass bits thrown outward (fixed pool). radius: final radius (m); life:
    frames until it has settled. low (default: radius < 1.5): a flatter, wider, ground-hugging cloud for
    landings / rolls / skids (0.6-1.2 m); otherwise a taller puff rising above the grass (the S17 slam, 2-3 m).
    Returns dict(volume, debris)."""
    r = float(radius)
    low = (r < 1.5) if low is None else bool(low)
    nm = name or f"VFX_dust_{int(frame)}_{seed}"
    if low:
        H = 1.5 * r + 0.7
        vol = _volume_box(nm, "dust", (pos[0], pos[1], pos[2] + 0.5 * H - 0.15), (4.6 * r, 4.6 * r, H), frame,
                          frame + life, shape="ball", color=color, density=density, anisotropy=0.4,
                          noise_scale=1.7 / max(0.4, r) ** 0.5, rise=0.2 if rise is None else rise, expand=1.25,
                          evolve=0.45, fade_in=0.03, fade_out=0.6, seed=seed, grow_frames=life * 0.4,
                          squash=2.3, contrast=(0.5, 0.65), noise2=2.4)
    else:
        vol = _volume_box(nm, "dust", (pos[0], pos[1], pos[2] + 1.1 * r), (3.2 * r, 3.2 * r, 2.6 * r), frame,
                          frame + life, shape="ball", color=color, density=density, anisotropy=0.4,
                          noise_scale=1.5 / max(0.4, r) ** 0.5, rise=0.45 if rise is None else rise, expand=1.0,
                          evolve=0.45, fade_in=0.03, fade_out=0.65, seed=seed, grow_frames=life * 0.45,
                          contrast=(0.5, 0.65), noise2=2.2)
    deb = None
    if debris:
        rng = _rng("dust_debris", frame, seed)
        n = int(18 + 14 * r)
        ang = rng.uniform(0, 2 * math.pi, n)
        up = rng.uniform(0.35, 1.0, n) * (0.6 if low else 1.0)
        hs = rng.uniform(1.0, 3.2, n) * math.sqrt(r)
        vel = np.column_stack([np.cos(ang) * hs, np.sin(ang) * hs, up * 2.6 * math.sqrt(r)])
        p0 = np.asarray(pos, np.float64)[None, :] + np.column_stack(
            [np.cos(ang) * 0.2 * r, np.sin(ang) * 0.2 * r, np.full(n, 0.05)])
        pick = rng.choice([_PICK_CLOD, _PICK_CLOD, _PICK_BLADE, _PICK_BENT], n).astype(np.int32)
        sizes = np.where(pick == _PICK_CLOD, rng.uniform(0.02, 0.05, n), rng.uniform(0.06, 0.14, n))
        deb = _pool(nm + "_debris", "dust", p0, vel, float(frame) + rng.uniform(0, 1.5, n),
                    rng.uniform(14, 26, n), gravity=-9.81, drag=rng.uniform(0.8, 1.8, n),
                    instances=_shard_sources(), pick=pick, size=sizes, align='random',
                    spin=rng.uniform(-12, 12, (n, 3)))
    return dict(volume=vol, debris=deb)


# ================================================================================================ fire ring
def _tongue_mesh(rings, seg=6, curl=0.16, twist=0.35, lobes=((0.0, 0.0, 1.0),)):
    """Vertices/faces/h of a low-poly flame tongue: `rings` = [(z, r)] (unit height, last r = 0 = the tip), tip
    curled toward +X by curl*z^2, twisting twist*z rad; lobes = [(x offset, lean rad about Y, height scale)]."""
    v, f, h = [], [], []
    for x0, lean, hs in lobes:
        base = len(v)
        cl, sl = math.cos(lean), math.sin(lean)
        for z, r in rings[:-1]:
            for i in range(seg):
                a = 2 * math.pi * i / seg + twist * z
                px, py, pz = curl * z * z + r * math.cos(a), r * math.sin(a), z * hs
                v.append((x0 + px * cl + pz * sl, py, -px * sl + pz * cl))
                h.append(z)
        v.append((x0 + (curl + 0.0) * cl + hs * sl, 0.0, -curl * sl + hs * cl))
        h.append(1.0)
        nr = len(rings) - 1
        for k in range(nr - 1):
            for i in range(seg):
                j = (i + 1) % seg
                f.append((base + k * seg + i, base + k * seg + j, base + (k + 1) * seg + j, base + (k + 1) * seg + i))
        tip = len(v) - 1
        for i in range(seg):
            f.append((base + (nr - 1) * seg + i, base + (nr - 1) * seg + (i + 1) % seg, tip))
        f.append(tuple(base + i for i in reversed(range(seg))))
    return v, f, np.array(h, np.float32)


def _tongue_sources():
    """Flame-tongue variants (collection VFX_src_fire, pick index = alphabetical order): f0 teardrop (belly
    0.5), f1 slim licking tongue, f2 forked (two slim lobes leaning apart). Unit height, vertex attribute 'h'
    0 (base) .. 1 (tip)."""
    col = bpy.data.collections.get("VFX_src_fire")
    if col is not None:
        return col
    col = U.ensure_collection("VFX_src_fire", parent=_collection("sources"))
    tear = [(0.0, 0.3), (0.08, 0.5), (0.2, 0.47), (0.34, 0.4), (0.48, 0.31), (0.62, 0.22), (0.76, 0.14),
            (0.89, 0.07), (1.0, 0.0)]
    slim = [(0.0, 0.2), (0.1, 0.32), (0.25, 0.3), (0.4, 0.26), (0.55, 0.2), (0.7, 0.14), (0.84, 0.08),
            (0.94, 0.035), (1.0, 0.0)]
    variants = (("VFX_src_f0_tear", _tongue_mesh(tear)),
                ("VFX_src_f1_slim", _tongue_mesh(slim, curl=0.28, twist=0.7)),
                ("VFX_src_f2_fork", _tongue_mesh(slim, curl=0.2, twist=0.5,
                                                 lobes=((-0.1, -0.22, 1.0), (0.12, 0.3, 0.72)))))
    for nm, (v, f, h) in variants:
        ob = _hidden_source(nm, v, f, col, smooth=True, attrs={"h": h})
        ob.hide_render = False
        ob.hide_viewport = False
    for vl in bpy.context.scene.view_layers:
        lc = _find_layer_collection(vl.layer_collection, col.name)
        if lc is not None:
            lc.exclude = True
    return col


def _fire_material(name="VFX_fire", strength=1.0):
    """Emissive flame (DITHERED): a hot yellow-white base band (h < 0.15), orange body, darker red upper third,
    a rising 4D-noise flame texture (object space advected upward on the film clock: internal flicker + ragged,
    licking tips/edges through dithered alpha), a hotter camera-facing core and soft (fresnel) alpha at grazing
    angles instead of dark silhouettes, per-instance flicker ('flick', GEOMETRY after realize). Emission ~0.5-1.6
    in the body; the thin base band reaches ~2.4 so AgX turns it yellow-white (documented exception to rule 7 -
    a small area; bloom does the glow)."""
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    mat, nb, out = _mat(name)
    now = nb.n('ShaderNodeValue', name="FX Time")
    h = U.attribute_node(mat, "h", 'GEOMETRY').outputs["Fac"]
    fl = U.attribute_node(mat, "flick", 'GEOMETRY').outputs["Fac"]        # realized: instance attr -> points
    facing = nb.n('ShaderNodeLayerWeight', Blend=0.35)['Facing']          # 0 facing the camera .. 1 grazing
    tc = nb.n('ShaderNodeTexCoord')
    adv = nb.vmath('SUBTRACT', nb.vmath('MULTIPLY', tc['Object'], (2.4, 2.4, 1.5)),
                   nb.xyz(0.0, 0.0, nb.math('MULTIPLY', now.out, 2.6)))
    nz = nb.noise(vector=adv, w=nb.math('MULTIPLY', now.out, 1.1), scale=1.0, detail=3.0, roughness=0.55, dims='4D')
    tex = nb.map_range(nz['Fac'], 0.3, 0.7, -0.5, 0.5)                    # -0.5 .. 0.5
    heat = nb.math('ADD', nb.math('ADD', nb.math('MULTIPLY', h, 0.8), nb.math('MULTIPLY', facing, 0.28)),
                   nb.math('SUBTRACT', nb.math('MULTIPLY', tex, 0.28), 0.06), clamp=True)
    colr = _ramp(nb, heat, [(0.0, (1.0, 0.9, 0.58)), (0.13, (1.0, 0.6, 0.15)), (0.36, (1.0, 0.3, 0.04)),
                            (0.7, (0.72, 0.1, 0.012)), (1.0, (0.32, 0.03, 0.006))])
    base = nb.map_range(h, 0.0, 0.16, 1.5, 0.0, interp='SMOOTHSTEP')      # hot base band
    body = nb.math('ADD', nb.math('MULTIPLY', nb.math('POWER', nb.math('SUBTRACT', 1.0, heat), 1.4), 1.45), 0.08)
    st = nb.math('MULTIPLY', nb.math('ADD', body, base),
                 nb.math('MULTIPLY', nb.math('ADD', 0.7, nb.math('MULTIPLY', fl, 0.6)), nb.math('ADD', 1.0, tex)))
    em = nb.n('ShaderNodeEmission', Color=colr, Strength=nb.math('MULTIPLY', st, strength))
    # ragged tips: the upper part is cut by the rising noise (dithered alpha), soft fresnel edges
    top = nb.map_range(nb.math('ADD', h, nb.math('MULTIPLY', tex, 0.5)), 0.5, 0.92, 0.0, 1.0, interp='SMOOTHSTEP')
    alpha = nb.math('MULTIPLY', nb.math('SUBTRACT', 1.0, nb.math('MULTIPLY', top, 0.95)),
                    nb.map_range(facing, 0.5, 1.0, 1.0, 0.15))
    mix = nb.n('ShaderNodeMixShader', alpha, nb.n('ShaderNodeBsdfTransparent'), em)
    nb.link(mix, U.socket_in(out.node, "Surface"))
    mat.surface_render_method = 'DITHERED'
    mat.use_backface_culling = False
    mat.diffuse_color = (*COLORS["fire"], 1.0)
    _drive_value_node(mat.node_tree, "FX Time")
    return mat


def _ember_glow_material(name, t0, t_grow, t_out, t_end, strength=1.0):
    """Ground ember glow for the fire ring: emissive noise specks on the ground annulus; level ramps up with the
    ring, drops to a low ember glow after the extinguish (t_out) and dies out by t_end (fx seconds)."""
    mat, nb, out = _mat(name)
    now = nb.n('ShaderNodeValue', name="FX Time")
    rr = U.attribute_node(mat, "rr", 'GEOMETRY').outputs["Fac"]
    tc = nb.n('ShaderNodeTexCoord')
    nz = nb.noise(vector=nb.vmath('SCALE', tc['Object'], scale=1.0), w=nb.math('MULTIPLY', now.out, 0.6),
                  scale=4.5, detail=3.0, roughness=0.6, dims='4D')
    speck = nb.math('POWER', nb.map_range(nz['Fac'], 0.45, 0.78, 0.0, 1.0), 2.0)
    band = nb.math('MULTIPLY', nb.map_range(rr, 0.0, 0.45, 0.0, 1.0, interp='SMOOTHSTEP'),
                   nb.map_range(rr, 0.55, 1.0, 1.0, 0.0, interp='SMOOTHSTEP'))
    up = nb.map_range(now.out, t0, t0 + t_grow + 0.2, 0.0, 1.0, interp='SMOOTHSTEP')
    down = nb.map_range(now.out, t_out, t_out + 2.5, 1.0, 0.22, interp='SMOOTHSTEP')
    end = nb.map_range(now.out, t_end - 1.5, t_end, 1.0, 0.0, interp='SMOOTHSTEP')
    lvl = nb.math('MULTIPLY', nb.math('MULTIPLY', up, down), end)
    colr = _ramp(nb, speck, [(0.0, (0.35, 0.03, 0.005)), (0.6, (1.0, 0.3, 0.04)), (1.0, (1.0, 0.7, 0.3))])
    em = nb.n('ShaderNodeEmission', Color=colr,
              Strength=nb.math('MULTIPLY', nb.math('MULTIPLY', nb.math('ADD', 0.08, speck), band),
                               nb.math('MULTIPLY', lvl, strength)))
    dark = nb.n('ShaderNodeBsdfDiffuse', Color=(0.02, 0.015, 0.012, 1.0))
    add = nb.n('ShaderNodeAddShader', dark, em)
    nb.link(add, U.socket_in(out.node, "Surface"))
    _drive_value_node(mat.node_tree, "FX Time")
    return mat


def fire_ring(f0, center, radius=8.0, grow_frames=12, f_out=None, count=None, height=1.5, seed=0,
              extinguish=True, f_end=None, lights=True, light_energy=400.0, shadow_angles=(150.0, 210.0),
              smoke=True, ember_rate=70.0, ground_glow=True, wind=(0.4, 0.15), n_lights=8, name=None):
    """S15 ring of fire. At f0 a wave of flame races out from `center` to `radius` over grow_frames (ease-out;
    DIRECTION §5: brightness ramps over >= 6 frames, never a flash), leaving a burning ring.

    Flames: a FIXED pool of low-poly opaque emissive tongues (count default ~10 per metre of circumference)
    riding the growing radius; height erupts (+30 %) then settles; per-tongue flicker and sway from fx_time
    noise; realized and vertex-displaced (licking tips). Lights: 8 point lights on the ring moving with the radius
    (time-expression drivers on fx_time; energy flickers) - the two at `shadow_angles` (deg, 180 = -X side, i.e.
    behind the action for the +X camera) cast shadows, six do not (rule 5: sun/moon + 2). Ground glow: ember
    speckle annulus. smoke: dark smoke band rising over the ring, glowing orange from the flames beneath.
    Embers: embers(...) at ember_rate per second from the ring (2.8 cm specks).
    f_out (e.g. the S20 downpour 2401): flames shrink and die over ~20 frames, lights fall to an ember glow,
    and (extinguish=True) steam rises from the ring - the glowing steam band that backlights Act III
    (DIRECTION §6) - until f_end (default: end of Act III). Returns dict of the created objects."""
    fxc = _clock()
    center = tuple(float(x) for x in center)
    R = float(radius)
    t0 = fxc.fx_time_at(f0)
    tg = max(1.0, float(grow_frames)) / FPS
    act3_end = next(a["end"] for a in config.ACTS if a["id"] == "act3")
    if f_end is None:
        f_end = act3_end if f_out is not None else next(a["end"] for a in config.ACTS if a["id"] == "act2")
    t_out = fxc.fx_time_at(f_out) if f_out is not None else 1e6
    t_end = fxc.fx_time_at(f_end)
    out_dur = 20.0 / FPS
    rng = _rng("fire_ring", f0, seed)
    # tongues grow in CLUSTERS (2-5, one tall leader), cluster centres at random (irregular gaps): a burning
    # front, never a regular picket fence
    n_target = int(count or max(60, round(2 * math.pi * R * 8.5)))
    theta, hf, pick = [], [], []
    while len(theta) < n_target:
        c0 = float(rng.uniform(0, 2 * math.pi))
        k = int(rng.integers(2, 6))
        lead = int(rng.integers(0, k))
        for j in range(k):
            theta.append(c0 + float(rng.normal(0.0, 0.2)) / max(R, 0.3))
            hf.append(float(rng.uniform(1.05, 1.5)) if j == lead else float(rng.uniform(0.35, 0.9)))
            pick.append(int(rng.choice([0, 1, 1, 2])))
    n = len(theta)
    theta = np.mod(np.array(theta), 2 * math.pi)
    col = _collection("fire")
    nm = _uname(name or f"VFX_fire_ring_{int(f0)}_{seed}")
    ob = U.mesh_from_data(nm, np.zeros((n, 3)), collection=col)
    ob.location = center
    _no_shadow(ob)
    me = ob.data
    for k, v in dict(theta=theta, dr=rng.normal(0, 0.25, n), hf=np.array(hf), wf=rng.uniform(0.7, 1.25, n),
                     ph=rng.uniform(0, 100, n), rz=rng.uniform(0, 2 * math.pi, n),
                     lean=rng.normal(0, 0.12, n)).items():
        U.add_attribute(me, k, np.asarray(v, np.float32), 'FLOAT')
    U.add_attribute(me, "pick", np.array(pick, np.int32), 'INT')
    ng = U.gn_new_tree("GN_" + nm, inputs=[
        ("Time", "FLOAT", 0.0), ("T0", "FLOAT", t0), ("TGrow", "FLOAT", tg), ("Radius", "FLOAT", R),
        ("Height", "FLOAT", float(height)), ("TOut", "FLOAT", t_out), ("OutDur", "FLOAT", out_dur),
        ("TEnd", "FLOAT", t_end), ("Wind", "VECTOR", (float(wind[0]), float(wind[1]), 0.0)),
        ("Tongues", "COLLECTION"), ("Material", "MATERIAL")])
    nb = U.NB(ng)
    gi = nb.gi
    t = nb.math('SUBTRACT', gi['Time'], gi['T0'])
    g = nb.math('MINIMUM', nb.math('MAXIMUM', nb.math('DIVIDE', t, gi['TGrow']), 0.0), 1.0)
    om = nb.math('SUBTRACT', 1.0, g)
    e = nb.math('SUBTRACT', 1.0, nb.math('MULTIPLY', om, nb.math('MULTIPLY', om, om)))
    ramp = nb.map_range(t, 0.0, max(7.0 / FPS, tg * 0.8), 0.0, 1.0, interp='SMOOTHSTEP')
    burst = nb.math('ADD', 1.0, nb.math('MULTIPLY', 0.3, nb.math('EXPONENT', nb.math(
        'DIVIDE', nb.math('MAXIMUM', t, 0.0), -0.45))))
    outf = nb.map_range(gi['Time'], gi['TOut'], nb.math('ADD', gi['TOut'], gi['OutDur']), 1.0, 0.0,
                        interp='SMOOTHSTEP')
    th = nb.attr("theta")
    r = nb.math('MULTIPLY', nb.math('ADD', gi['Radius'], nb.attr("dr")), e)
    posn = nb.xyz(nb.math('MULTIPLY', nb.math('COSINE', th), r), nb.math('MULTIPLY', nb.math('SINE', th), r), 0.0)
    placed = nb.n('GeometryNodeSetPosition', gi['Geometry'], Position=posn)
    ph = nb.attr("ph")
    nz1 = nb.noise(vector=nb.xyz(ph, 0.0, 0.0), w=nb.math('MULTIPLY', gi['Time'], 2.4), scale=1.0, detail=1.0,
                   dims='4D')
    nz2 = nb.noise(vector=nb.xyz(0.0, ph, 0.0), w=nb.math('MULTIPLY', gi['Time'], 1.3), scale=1.0, detail=1.0,
                   dims='4D')
    flick = nb.map_range(nz1['Fac'], 0.3, 0.7, 0.0, 1.0)
    hz = nb.math('MULTIPLY', nb.math('MULTIPLY', gi['Height'], nb.attr("hf")),
                 nb.math('MULTIPLY', nb.math('MULTIPLY', ramp, burst),
                         nb.math('MULTIPLY', outf, nb.math('ADD', 0.65, nb.math('MULTIPLY', flick, 0.7)))))
    wxy = nb.math('MULTIPLY', nb.math('MULTIPLY', gi['Height'], nb.math('MULTIPLY', nb.attr("wf"), 0.3)),
                  nb.math('MULTIPLY', nb.math('ADD', 0.45, nb.math('MULTIPLY', ramp, 0.55)),
                          nb.math('SQRT', outf)))
    alive = nb.bmath('AND', nb.cmp('GREATER_EQUAL', t, 0.0), nb.cmp('GREATER_THAN', outf, 0.002))
    hz = nb.switch(alive, 0.0, hz)
    wxy = nb.switch(alive, 0.0, wxy)
    sway = nb.vmath('SCALE', nb.vmath('SUBTRACT', nz2['Color'], (0.5, 0.5, 0.5)), scale=0.7)
    wind_tilt = nb.vmath('SCALE', nb.xyz(nb.math('MULTIPLY', nb.sep(gi['Wind'])['Y'], -1.0),
                                         nb.sep(gi['Wind'])['X'], 0.0), scale=0.35)
    eul = nb.vmath('ADD', nb.vmath('ADD', nb.xyz(nb.attr("lean"), nb.attr("lean"), nb.attr("rz")),
                                   nb.vmath('MULTIPLY', sway, (1.0, 1.0, 0.0))), wind_tilt)
    rot = nb.n('FunctionNodeEulerToRotation', eul)['Rotation']
    tci = nb.n('GeometryNodeCollectionInfo', gi['Tongues'], True, True, transform_space='ORIGINAL')
    inst = nb.n('GeometryNodeInstanceOnPoints', Points=placed, Instance=tci['Instances'], Pick_Instance=True,
                Instance_Index=nb.attr("pick", 'INT'), Rotation=rot, Scale=nb.xyz(wxy, wxy, hz))
    inst = nb.store(inst, "flick", flick, 'FLOAT', 'INSTANCE')
    real = nb.n('GeometryNodeRealizeInstances', inst)
    # licking tips: world-space noise displacement growing with the vertex height attribute
    p = nb.n('GeometryNodeInputPosition')['Position']
    hh = nb.attr("h")
    nz3 = nb.noise(vector=nb.vmath('ADD', nb.vmath('SCALE', p, scale=0.75),
                                   nb.vmath('SCALE', (0.0, 0.0, -1.0), scale=nb.math('MULTIPLY', gi['Time'], 1.6))),
                   w=nb.math('MULTIPLY', gi['Time'], 0.9), scale=1.0, detail=2.0, dims='4D')
    amp = nb.math('MULTIPLY', nb.math('POWER', hh, 1.3), nb.math('MULTIPLY', gi['Height'], 0.4))
    off = nb.vmath('MULTIPLY', nb.vmath('SCALE', nb.vmath('SUBTRACT', nz3['Color'], (0.5, 0.5, 0.5)), scale=amp),
                   (2.0, 2.0, 0.8))
    disp = nb.n('GeometryNodeSetPosition', real, Offset=off)
    mat_n = nb.n('GeometryNodeSetMaterial', disp, None, gi['Material'])
    nb.link(_fx_gate(nb, mat_n, nb.math('SUBTRACT', gi['T0'], 0.05),
                     nb.math('MINIMUM', nb.math('ADD', nb.math('ADD', gi['TOut'], gi['OutDur']), 0.1), gi['TEnd'])),
            nb.go['Geometry'])
    nb.layout()
    U.gn_modifier(ob, ng, Tongues=_tongue_sources(), Material=_fire_material())
    fxc.drive_gn_input(ob, "Time")
    ob["vfx_window"] = (float(f0), float(f_end))
    res = dict(flames=ob, lights=[])
    # ---- lights riding the radius
    if lights:
        # Pipeline rule 5 (<= 3 shadow casters per shot incl. sun/moon + the Act III ENV_flash): the two SHADOWED
        # lights live only while the flames burn - they fade out with the flames over out_dur after f_out and
        # are hidden from f_out + out_frames on; an UNSHADOWED twin at the same spot takes over the ember /
        # steam-band glow (their sum is the old single-light curve, so the look is unchanged).
        ember_level = 0.12
        out_frames = int(round(out_dur * FPS))
        res["shadow_window"] = (f0 - 1, (f_out + out_frames + 1) if f_out is not None else f_end + 1)
        for k in range(int(n_lights)):
            ang = 360.0 * k / max(1, int(n_lights)) + 22.5
            shadow = any(abs(((ang - a) + 180) % 360 - 180) < 22.6 for a in shadow_angles[:2])
            split = shadow and f_out is not None
            rl = R - 0.2
            ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
            grow = f"(1-pow(1-clamp((t-{_n(t0)})/{_n(tg)},0,1),3))"
            p1, p2 = float(rng.uniform(0, 50)), float(rng.uniform(0, 50))
            ramp_e = f"clamp((t-{_n(t0)})/{_n(max(8.0 / FPS, tg))},0,1)"
            c2 = f"clamp((t-{_n(t_out, 3)})/{_n(out_dur * 2)},0,1)"
            c1 = f"clamp((t-{_n(t_out, 3)})/{_n(out_dur)},0,1)"
            endf = f"(1-clamp((t-{_n(t_end - 1.5, 3)})/1.5,0,1))"
            total = f"(1-{_n(1.0 - ember_level, 3)}*{c2})*{endf}"
            fl = f"(.78+.14*sin(t*13.7+{_n(p1, 2)})+.08*sin(t*31.3+{_n(p2, 2)}))"
            parts = [(f"{nm}_L{k}", shadow, res["shadow_window"] if split else (f0 - 1, f_end + 1),
                      f"{ramp_e}*(1-{c1})" if split else f"{ramp_e}*{total}")]
            if split:           # the fire has burnt for a while at f_out: the twin needs no ramp-in term
                parts.append((f"{nm}_L{k}e", False, (f_out - 1, f_end + 1), f"max(0,{total}-1+{c1})"))
            for lname, shad, win, lvl in parts:
                L = _point_light(lname, center, COLORS["fire"], "fire", radius=0.6, shadow=shad, cutoff=R * 2.6,
                                 window=win)
                L.data.color = (1.0, 0.42, 0.12)
                time_expr(L, "location", f"{_n(center[0])}+{_n(ca * rl)}*{grow}", index=0)
                time_expr(L, "location", f"{_n(center[1])}+{_n(sa * rl)}*{grow}", index=1)
                L.location.z = center[2] + 1.1
                time_expr(L.data, "energy", f"{_n(light_energy, 2)}*{lvl}*{fl}")
                res["lights"].append(L)
    if ground_glow:
        ring = _annulus_source("VFX_src_ring_glow", 0.86, 1.14, seg=128)
        gm = _ember_glow_material(nm + "_glow_mat", t0, tg, t_out, t_end)
        g_ob = U.new_object(nm + "_glow", ring.data.copy(), col)
        g_ob.data.materials.clear()
        g_ob.data.materials.append(gm)
        g_ob.location = (center[0], center[1], center[2] + 0.03)
        for i in range(3):
            if i < 2:
                time_expr(g_ob, "scale", f"{R:.4f} * max(0.02, 1.0 - pow(1.0 - clamp((t - {t0:.5f}) / {tg:.5f},"
                                         f" 0.0, 1.0), 3.0))", index=i)
        g_ob.scale.z = 1.0
        _no_shadow(g_ob)
        _add_gate(g_ob, t0 - 0.05, t_end + 0.05)
        res["glow"] = g_ob
    if smoke and globals().get("smoke") is not None:
        # the smoke band glows from the flames beneath (the fire glows instead of looking cut out)
        res["smoke"] = globals()["smoke"](f0 + 6, (f_out + 12) if f_out is not None else f_end, center,
                                          R + 1.0, ring=True, height=11.0, seed=seed, density=1.8,
                                          glow=(1.0, 0.36, 0.07), glow_strength=0.55, glow_h=0.16,
                                          name=nm + "_smoke")
    if ember_rate and globals().get("embers") is not None:
        res["embers"] = globals()["embers"](f0 + 3, (f_out + 30) if f_out is not None else f_end, center, R,
                                            ember_rate, seed=seed, ring=True, size=0.028, name=nm + "_embers")
    if f_out is not None and extinguish and globals().get("steam") is not None:
        res["steam"] = globals()["steam"](f_out, f_end, center, R, ring=True, glow=True, seed=seed,
                                          name=nm + "_steam")
    return res


# ================================================================================================ embers
def _ember_material(name="VFX_ember", strength=2.2):
    """Tiny emissive embers: yellow-orange cooling to deep red with age ('age01', INSTANCER), twinkling
    ('tw', INSTANCER)."""
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    mat, nb, out = _mat(name)
    age = U.attribute_node(mat, "age01", 'INSTANCER').outputs["Fac"]
    tw = U.attribute_node(mat, "tw", 'INSTANCER').outputs["Fac"]
    colr = _ramp(nb, age, [(0.0, (1.0, 0.72, 0.3)), (0.4, (1.0, 0.36, 0.06)), (1.0, (0.6, 0.05, 0.01))])
    st = nb.math('MULTIPLY', nb.math('MULTIPLY', nb.math('SUBTRACT', 1.0, nb.math('MULTIPLY', age, 0.6)),
                                     nb.math('ADD', 0.35, tw)), strength)
    nb.link(nb.n('ShaderNodeEmission', Color=colr, Strength=st), U.socket_in(out.node, "Surface"))
    mat.diffuse_color = (*COLORS["ember"], 1.0)
    return mat


def embers(f0, f1, center, radius, rate=30.0, seed=0, ring=False, rise=1.3, life=(1.4, 3.2), height=(0.2, 1.6),
           size=0.018, wind=(0.5, 0.2), turb=0.5, color_strength=1.8, name=None):
    """Drifting embers: a FIXED pool of respawning glowing specks (count = rate * mean life). Slot i cycles with
    its own period; each cycle respawns at a new seeded spot (GN Random Value with ID = slot*4099 + cycle) on
    the disc of `radius` around center (ring=True: on the circle, e.g. the fire ring), at a height in `height`,
    then rises (rise m/s) with wind + 4D-noise turbulence, twinkles and cools. A cycle only exists when it is born
    inside [f0, f1] (fx time) - no popping at the ends. Rule 3: scale is exactly 0 during the last 6 % of each
    period and the first 3 % of the next, so the respawn jump never happens on a visible (motion-blurred) ember.
    Returns the object."""
    fxc = _clock()
    t0, t1 = fxc.fx_time_at(f0), fxc.fx_time_at(f1)
    rng = _rng("embers", f0, seed)
    mean_life = 0.5 * (life[0] + life[1])
    n = int(max(8, math.ceil(rate * mean_life * 1.06)))
    col = _collection("embers")
    nm = _uname(name or f"VFX_embers_{int(f0)}_{seed}")
    ob = U.mesh_from_data(nm, np.zeros((n, 3)), collection=col)
    ob.location = tuple(center)
    _no_shadow(ob)
    per = rng.uniform(life[0], life[1], n) / 0.94            # 6 % dead zone at the end of each period
    U.add_attribute(ob.data, "per", per.astype(np.float32), 'FLOAT')
    U.add_attribute(ob.data, "phase", rng.random(n).astype(np.float32), 'FLOAT')
    U.add_attribute(ob.data, "slot", np.arange(n, dtype=np.int32), 'INT')
    src = bpy.data.objects.get("VFX_src_s3_clod") or _shard_sources().objects["VFX_src_s3_clod"]
    ng = U.gn_new_tree("GN_" + nm, inputs=[
        ("Time", "FLOAT", 0.0), ("T0", "FLOAT", t0), ("T1", "FLOAT", t1), ("Radius", "FLOAT", float(radius)),
        ("Rise", "FLOAT", float(rise)), ("Wind", "VECTOR", (float(wind[0]), float(wind[1]), 0.0)),
        ("Turb", "FLOAT", float(turb)), ("Size", "FLOAT", float(size)), ("Ring", "BOOL", bool(ring)),
        ("HMin", "FLOAT", float(height[0])), ("HMax", "FLOAT", float(height[1])),
        ("Speck", "OBJECT"), ("Material", "MATERIAL")])
    nb = U.NB(ng)
    gi = nb.gi
    per_a = nb.attr("per")
    u = nb.math('ADD', nb.math('DIVIDE', nb.math('SUBTRACT', gi['Time'], gi['T0']), per_a), nb.attr("phase"))
    cyc = nb.math('FLOOR', u)
    a01 = nb.math('SUBTRACT', u, cyc)                            # 0..1 within the period
    age = nb.math('MULTIPLY', a01, per_a)                        # seconds since this cycle's birth
    birth = nb.math('SUBTRACT', gi['Time'], age)
    allowed = nb.bmath('AND', nb.cmp('GREATER_EQUAL', birth, gi['T0']), nb.cmp('LESS_EQUAL', birth, gi['T1']))
    cid = nb.n('FunctionNodeFloatToInt', nb.math('ADD', nb.math('MULTIPLY', nb.attr("slot", 'INT'), 4099.0), cyc),
               rounding_mode='FLOOR')
    rnd = nb.rand('FLOAT_VECTOR', (0.0, 0.0, 0.0), (1.0, 1.0, 1.0), seed=int(_seed("emb", nm) % 100000), id=cid)
    rs = nb.sep(rnd)
    ang = nb.math('MULTIPLY', rs['X'], 2 * math.pi)
    rr = nb.switch(gi['Ring'], nb.math('MULTIPLY', gi['Radius'], nb.math('SQRT', rs['Y'])),
                   nb.math('ADD', gi['Radius'], nb.math('MULTIPLY', nb.math('SUBTRACT', rs['Y'], 0.5), 0.8)))
    hz = nb.math('ADD', gi['HMin'], nb.math('MULTIPLY', rs['Z'], nb.math('SUBTRACT', gi['HMax'], gi['HMin'])))
    spawn = nb.xyz(nb.math('MULTIPLY', nb.math('COSINE', ang), rr), nb.math('MULTIPLY', nb.math('SINE', ang), rr), hz)
    rise_v = nb.math('MULTIPLY', gi['Rise'], nb.math('ADD', 0.6, nb.math('MULTIPLY', rs['X'], 0.8)))
    drift = nb.vmath('SCALE', nb.vmath('ADD', gi['Wind'], nb.xyz(0.0, 0.0, rise_v)), scale=age)
    nz = nb.noise(vector=nb.vmath('ADD', nb.vmath('SCALE', rnd, scale=40.0), nb.xyz(0.0, 0.0, 0.0)),
                  w=nb.math('MULTIPLY', gi['Time'], 0.9), scale=1.0, detail=1.0, dims='4D')
    wob = nb.vmath('SCALE', nb.vmath('SUBTRACT', nz['Color'], (0.5, 0.5, 0.5)),
                   scale=nb.math('MULTIPLY', gi['Turb'], nb.math('MINIMUM', age, 1.5)))
    pos = nb.vmath('ADD', nb.vmath('ADD', spawn, drift), wob)
    placed = nb.n('GeometryNodeSetPosition', gi['Geometry'], Position=pos)
    life01 = nb.math('DIVIDE', a01, 0.94)
    env = nb.math('MULTIPLY', nb.map_range(life01, 0.03, 0.11, 0.0, 1.0),
                  nb.map_range(life01, 0.65, 1.0, 1.0, 0.0))
    # dead zones: last 6 % of the period AND first 3 % of the next one (> 0.5 frame at any speed) - the
    # respawn jump can never fall inside the shutter of a visible ember
    visible = nb.bmath('AND', allowed, nb.bmath('AND', nb.cmp('LESS_THAN', a01, 0.94),
                                                nb.cmp('GREATER_THAN', life01, 0.03)))
    sc = nb.switch(visible, 0.0, nb.math('MULTIPLY', gi['Size'], nb.math('MULTIPLY', env, nb.math(
        'ADD', 0.6, nb.math('MULTIPLY', rs['Z'], 0.8)))))
    tw = nb.noise(vector=nb.vmath('SCALE', rnd, scale=17.0), w=nb.math('MULTIPLY', gi['Time'], 6.0), scale=1.0,
                  detail=0.0, dims='4D')
    inst = nb.n('GeometryNodeInstanceOnPoints', Points=placed,
                Instance=nb.n('GeometryNodeObjectInfo', gi['Speck'], False)['Geometry'], Scale=nb.xyz(sc, sc, sc))
    inst = nb.store(inst, "age01", nb.math('MINIMUM', life01, 1.0), 'FLOAT', 'INSTANCE')
    inst = nb.store(inst, "tw", nb.map_range(tw['Fac'], 0.3, 0.7, 0.0, 1.0), 'FLOAT', 'INSTANCE')
    inst = nb.n('GeometryNodeSetMaterial', inst, None, gi['Material'])
    nb.link(_fx_gate(nb, inst, nb.math('SUBTRACT', gi['T0'], 0.05), nb.math('ADD', gi['T1'], float(per.max()) + 0.1)),
            nb.go['Geometry'])
    nb.layout()
    U.gn_modifier(ob, ng, Speck=src, Material=_ember_material(strength=color_strength))
    fxc.drive_gn_input(ob, "Time")
    ob["vfx_window"] = (float(f0), float(f1))
    return ob


# ================================================================================================ smoke / steam
def smoke(f0, f1, center, radius, height=8.0, ring=False, density=1.6, color='smoke', rise=1.4, seed=0,
          glow=None, glow_strength=0.0, glow_h=0.6, wind=(0.4, 0.15), name=None):
    """Rising smoke (mesh-box volume, noise density on fx_time; visible_shadow False): a column over a disc of
    `radius`, or (ring=True) a band rising over a ring of that radius (the fire ring's smoke). glow=(rgb|name)
    adds emission weighted toward the bottom (lit from the fire beneath). Returns the volume object."""
    R = float(radius)
    box_r = R + 2.0 if ring else R * 1.25
    return _volume_box(name or f"VFX_smoke_{int(f0)}_{seed}", "smoke",
                       (center[0], center[1], center[2] + 0.5 * height), (2 * box_r, 2 * box_r, height), f0, f1,
                       shape="ringcol" if ring else "column", color=color, density=density, anisotropy=0.2,
                       noise_scale=0.55, detail=3.0, rise=rise, evolve=0.25, fade_in=0.12, fade_out=0.3,
                       ring_radius=R / box_r, ring_width=1.6 / box_r, emission=glow, emission_strength=glow_strength,
                       glow_h=glow_h, wind=wind, seed=seed)


def steam(f0, f1, center, radius, height=4.5, ring=False, glow=False, density=0.55, rise=0.9, seed=0,
          wind=(0.3, 0.1), glow_strength=0.3, glow_h=0.6, flare=0.0, name=None):
    """White steam rising (the drowned fire ring in the rain, the struck pine): mesh-box volume column / ring
    band. glow=True: warm emission (glow_strength, weighted to the bottom) from the embers beneath (DIRECTION §6:
    the orange-lit steam band that puts a brighter layer behind the silhouettes in Act III; the struck pine uses
    >= 1.0 so it reads between the S22 strobe flashes). Returns the volume object."""
    R = float(radius)
    box_r = R + 1.5 if ring else R * 1.3
    return _volume_box(name or f"VFX_steam_{int(f0)}_{seed}", "steam",
                       (center[0], center[1], center[2] + 0.5 * height), (2 * box_r, 2 * box_r, height), f0, f1,
                       shape="ringcol" if ring else "column", color='steam', density=density, anisotropy=0.45,
                       noise_scale=0.8, detail=3.0, rise=rise, evolve=0.3, fade_in=0.05, fade_out=0.15,
                       ring_radius=R / box_r, ring_width=1.2 / box_r,
                       emission=(1.0, 0.35, 0.08) if glow else None,
                       emission_strength=float(glow_strength) if glow else 0.0, glow_h=glow_h, flare=flare,
                       contrast=(0.45, 0.7) if not ring else (0.42, 0.72), noise2=1.8 if not ring else 0.0,
                       wind=wind, seed=seed)


# ================================================================================================ lightning
def _perp(d, rng):
    """Random unit vector perpendicular to d."""
    d = d / (np.linalg.norm(d) + 1e-12)
    a = np.array([1.0, 0.0, 0.0]) if abs(d[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = np.cross(d, a)
    u /= np.linalg.norm(u)
    w = np.cross(d, u)
    ang = rng.uniform(0, 2 * math.pi)
    return u * math.cos(ang) + w * math.sin(ang)


def bolt_path(a, b, rng, rough=0.2, levels=7):
    """Midpoint-displacement polyline from a to b (numpy (n,3)): each level splits every segment and displaces
    the midpoint perpendicular to it by N(0, rough * segment length). Deterministic for a seeded rng."""
    pts = [np.asarray(a, float), np.asarray(b, float)]
    for lev in range(levels):
        r = rough * (0.93 ** max(0, lev - 2))                  # finer levels a little calmer (no knots)
        out = [pts[0]]
        for p, q in zip(pts[:-1], pts[1:]):
            d = q - p
            L = np.linalg.norm(d)
            off = float(np.clip(rng.normal(0.0, r), -0.32, 0.32))   # |offset| <= 0.32 L: never folds back
            m = 0.5 * (p + q) + _perp(d, rng) * off * L
            out += [m, q]
        pts = out
    return np.array(pts)


# clearance rules for the CUT bolt's forks (review: no ground-crawling lightning, nothing aimed at a fighter)
GRASS_TOP_ARENA = 1.15       # Pipeline rule 8: arena grass 0.95-1.15 m (r < 15 m) ...
GRASS_TOP_FIELD = 1.5        # ... field grass 1.1-1.5 m
FORK_CLEAR = 1.5             # fork vertices stay >= grass top + FORK_CLEAR + FORK_SLOPE * (horizontal distance
FORK_SLOPE = 0.2             #   from fork_at), except inside the strike zone (last ~10 % / the final plunge)
BOLT_GUARD_R = 5.0           # environmental strike points / branch tips must stay this far (XY) from the fighters
BOLT_LIGHT_RANGE = 60.0      # bolts striking farther than this from the arena centre get no point light (default)
FIGHTERS = ("SHINOBI_rig", "SAINT_rig")


def _ground_z(x, y):
    """Terrain height (environment.terrain_height when importable - a pure function, no build needed; else 0)."""
    env = _env()
    th = getattr(env, "terrain_height", None) if env is not None else None
    x, y = np.asarray(x, float), np.asarray(y, float)
    if th is None:
        return np.zeros(np.broadcast(x, y).shape)
    return np.asarray(th(x, y), float)


def _grass_top(x, y):
    """World z of the grass tops at (x, y): ground + arena/field grass height (Pipeline rule 8)."""
    r = np.hypot(np.asarray(x, float), np.asarray(y, float))
    return _ground_z(x, y) + np.where(r < 15.0, GRASS_TOP_ARENA, GRASS_TOP_FIELD)


def fork_floor(points, fork_at):
    """Clearance floor (world z) for fork vertices `points` (n,3) of a bolt cut at `fork_at`:
    grass top + FORK_CLEAR + FORK_SLOPE * horizontal distance from fork_at (capped near the blade so the fork can
    leave the fork point, which may sit a little lower)."""
    P = np.asarray(points, float).reshape(-1, 3)
    fa = np.asarray(fork_at, float)
    h = np.hypot(P[:, 0] - fa[0], P[:, 1] - fa[1])
    std = _grass_top(P[:, 0], P[:, 1]) + FORK_CLEAR + FORK_SLOPE * h
    return np.minimum(std, fa[2] + 0.8 * h)


def _fork_line(fork_at, e, rng, arch):
    """One fork of the cut bolt, fork_at -> e. Returns (points (n,3), strike_from index).
    Elevated target (> 2.5 m above the ground, e.g. the pine top): one jagged path lifted by a parabolic arch
    (apex >= arch * span above the chord, never skimming the grass); strike zone = the last 10 %.
    Ground target: out (and a little up) to a knee above the floor at ~85-90 % of the horizontal distance, then a
    steep plunge (> 60 deg) to the strike point = the strike zone. The clearance floor is enforced before it."""
    fork_at, e = np.asarray(fork_at, float), np.asarray(e, float)
    d = e - fork_at
    H = math.hypot(d[0], d[1])
    span = float(np.linalg.norm(d))
    elevated = (e[2] - float(_ground_z(e[0], e[1]))) > 2.5          # a tree top / pole, not the ground
    if elevated or H < 0.8:
        pts = bolt_path(fork_at, e, rng, 0.17, 6)
        u = np.linspace(0.0, 1.0, len(pts))
        bump = 4.0 * u * (1.0 - u)
        pts[:, 2] += arch * bump * span
        chord_z = fork_at[2] + u * d[2]
        for _ in range(4):                     # the jagged path must still reach apex >= arch * span
            rel = pts[:, 2] - chord_z
            i = int(np.argmax(rel))
            short = arch * span - float(rel[i])
            if short <= 1e-3:
                break
            pts[:, 2] += bump * (short / max(0.25, float(bump[i])))
        strike_from = int(0.9 * (len(pts) - 1))
    else:
        kf = float(rng.uniform(0.84, 0.9))
        kxy = fork_at[:2] + d[:2] * kf
        kz = max(float(fork_at[2]), float(fork_floor(np.array([[kxy[0], kxy[1], 0.0]]), fork_at)[0])) \
            + float(rng.uniform(0.3, 0.7))
        knee = np.array([kxy[0], kxy[1], kz])
        a = bolt_path(fork_at, knee, rng, 0.17, 5)
        u = np.linspace(0.0, 1.0, len(a))
        a[:, 2] += 0.12 * 4.0 * u * (1.0 - u) * float(np.linalg.norm(knee - fork_at))
        b = bolt_path(knee, e, rng, 0.12, 3)
        pts = np.vstack([a, b[1:]])
        strike_from = len(a) - 1
    fl = fork_floor(pts[:strike_from], fork_at) + 0.12
    pts[:strike_from, 2] = np.maximum(pts[:strike_from, 2], fl)
    pts[0] = fork_at
    return pts, strike_from


def _second_fork_end(fork_at, end, away_from, rng):
    """Default end of the cut bolt's second fork: a short ground strike BEHIND/beside the cutter, away from the
    opponent (never towards them), on the side opposite the main fork. None when away_from is unknown."""
    if away_from is None:
        return None
    fa = np.asarray(fork_at, float)
    a = fa[:2] - np.asarray(away_from, float)[:2]
    if np.linalg.norm(a) < 1e-6:
        return None
    a /= np.linalg.norm(a)
    m = np.asarray(end, float)[:2] - fa[:2]
    side = 1.0 if (a[0] * m[1] - a[1] * m[0]) > 0 else -1.0       # main fork is left(+)/right(-) of 'away'
    ang = -side * math.radians(float(rng.uniform(40.0, 60.0)))    # rotate towards the other side
    c, s_ = math.cos(ang), math.sin(ang)
    dv = np.array([a[0] * c - a[1] * s_, a[0] * s_ + a[1] * c])
    xy = fa[:2] + dv * float(rng.uniform(2.4, 3.4))
    return np.array([xy[0], xy[1], float(_ground_z(xy[0], xy[1]))])


def _bolt_geometry(start, end, branches, rng, width, fork_at=None, fork_ends=None, arch=0.34, away_from=None,
                   second_fork=True):
    """-> (lines, info): lines = [(points (n,3), radius (n,), level, u0, u1, kind)] with kind 'main' | 'fork' |
    'branch'; u runs 0 (bolt origin) .. 1 (strike). info = dict(fork_ends, strike_from) for the checks.
    fork_at (the CUT bolt): channel start -> fork_at, then one fork per fork_ends (default [end] + an automatic
    second fork away from `away_from`, see _second_fork_end). Forks never auto-mirror; branches of a cut bolt
    stay >= 8 m above the ground (nothing crawls over the grass)."""
    start, end = np.asarray(start, float), np.asarray(end, float)
    lines = []
    info = dict(fork_ends=[], strike_from=[])
    if fork_at is None:
        main = bolt_path(start, end, rng, 0.24, 7)
        lines.append((main, np.linspace(1.0, 0.7, len(main)) * width, 0, 0.0, 1.0, "main"))
        chans = [main]
    else:
        fork_at = np.asarray(fork_at, float)
        up = bolt_path(start, fork_at, rng, 0.24, 6)
        lines.append((up, np.linspace(1.0, 0.85, len(up)) * width, 0, 0.0, 0.6, "main"))
        ends = [np.asarray(e, float) for e in fork_ends] if fork_ends else [end]
        if not fork_ends and second_fork:
            e2 = _second_fork_end(fork_at, end, away_from, rng)
            if e2 is not None:
                ends.append(e2)
        chans = [up]
        for k, e in enumerate(ends):
            fk, sf = _fork_line(fork_at, e, rng, arch if k == 0 else 0.12)
            lines.append((fk, np.linspace(0.85 if k == 0 else 0.6, 0.55, len(fk)) * width, 0, 0.6, 1.0, "fork"))
            info["fork_ends"].append(e)
            info["strike_from"].append(sf)
            chans.append(fk)
    main = chans[0]
    Lm = np.linalg.norm(main[-1] - main[0])
    down = np.array([0.0, 0.0, -1.0])
    z_min_branch = (float(_ground_z(*fork_at[:2])) + 8.0) if fork_at is not None else None
    for bi in range(int(branches)):
        ch = chans[bi % len(chans)] if fork_at is None else chans[0]
        i = int(len(ch) * rng.uniform(0.12, 0.7))
        p = ch[i]
        d_main = ch[min(i + 3, len(ch) - 1)] - ch[max(i - 3, 0)]
        d_main /= np.linalg.norm(d_main) + 1e-9
        side = _perp(d_main, rng)
        d = d_main * 0.55 + side * rng.uniform(0.5, 0.9) + down * 0.3
        d /= np.linalg.norm(d)
        L = Lm * rng.uniform(0.18, 0.4) * (1.0 - 0.5 * i / len(ch))
        if z_min_branch is not None and d[2] < 0 and p[2] + d[2] * L < z_min_branch:
            L = max(0.5, (p[2] - z_min_branch) / -d[2])          # a cut bolt's branches stay high
        q = p + d * L
        br = bolt_path(p, q, rng, 0.24, 5)
        lines.append((br, np.linspace(0.45, 0.08, len(br)) * width, 1, 0.3, 0.8, "branch"))
        if rng.random() < 0.6:                                   # one sub-branch
            j = int(len(br) * rng.uniform(0.2, 0.6))
            d2 = d * 0.6 + _perp(d, rng) * 0.8
            d2 /= np.linalg.norm(d2)
            L2 = L * rng.uniform(0.25, 0.5)
            if z_min_branch is not None and d2[2] < 0 and br[j][2] + d2[2] * L2 < z_min_branch:
                L2 = max(0.3, (br[j][2] - z_min_branch) / -d2[2])
            sb = bolt_path(br[j], br[j] + d2 * L2, rng, 0.25, 4)
            lines.append((sb, np.linspace(0.25, 0.05, len(sb)) * width, 2, 0.5, 0.9, "branch"))
    return lines, info


def _bolt_material(name, color, strength_node_name="Bolt", halo=False):
    """Additive (Transparent + Emission, BLENDED) bolt shader: white-hot core, tinted rim (Layer Weight), level
    dimming (lvl attribute), strength from a Value node 'Bolt' (driven by a time curve = flicker schedule).
    halo=True: soft cylindrical falloff ((1 - facing)^3) so the wide glow tube shows no polygon edges."""
    mat, nb, out = _mat(name)
    val = nb.n('ShaderNodeValue', name=strength_node_name)
    val.node.outputs[0].default_value = 0.0
    lvl = U.attribute_node(mat, "lvl", 'GEOMETRY').outputs["Fac"]
    edge = nb.n('ShaderNodeLayerWeight', Blend=0.4)['Facing']
    tint = _color(color)
    colr = nb.mix(nb.math('POWER', edge, 0.7), (1.0, 1.0, 1.0, 1.0), (*tint, 1.0), data_type='RGBA')
    dim = nb.map_range(lvl, 0.0, 2.0, 1.0, 0.3)
    if halo:
        colr = (*tint, 1.0)
        dim = nb.math('MULTIPLY', dim, nb.math('POWER', nb.math('SUBTRACT', 1.0, edge), 4.0))
    em = nb.n('ShaderNodeEmission', Color=colr, Strength=nb.math('MULTIPLY', val.out, dim))
    add = nb.n('ShaderNodeAddShader', nb.n('ShaderNodeBsdfTransparent'), em)
    nb.link(add, U.socket_in(out.node, "Surface"))
    mat.surface_render_method = 'BLENDED'
    mat.diffuse_color = (*tint, 1.0)
    return mat, val.node


def _bolt_schedule(frame, duration, rng):
    """Per-frame flicker levels (CONSTANT steps): a bright first stroke, 1-3 re-strokes, dark gaps."""
    f = float(frame)
    lv = [1.0]
    for i in range(1, int(duration)):
        lv.append(float(rng.uniform(0.55, 0.9)) if i % 2 == 0 else float(rng.uniform(0.08, 0.3)))
    pts = [(f - 1.0, 0.0, 'CONSTANT')]
    pts += [(f + i, v, 'CONSTANT') for i, v in enumerate(lv)]
    pts.append((f + len(lv), 0.0, 'CONSTANT'))
    return pts, lv


def _env():
    """The environment module if it is importable and built (degrade gracefully otherwise)."""
    try:
        import environment
        return environment
    except Exception:
        return None


def _flash_ok(frame):
    """True if a flash at `frame` keeps >= config.FLASH_MIN_GAP frames from every flash issued so far (a flash
    on the SAME frame merges with it: bolt light + environment.flash of one strike)."""
    f = int(round(float(frame)))
    return all(g == f or abs(f - g) >= config.FLASH_MIN_GAP for g in _STATE["flash_frames"])


def _register_flash(frame):
    f = int(round(float(frame)))
    if f not in _STATE["flash_frames"]:
        _STATE["flash_frames"].append(f)


def env_flash(frame, strength=0.7, duration=2):
    """environment.flash within the flash budget (DIRECTION §5: >= config.FLASH_MIN_GAP frames apart,
    <= 70 % outside config.FULL_WHITE). Returns True if the flash was issued."""
    fw0, fw1 = config.FULL_WHITE
    if not (fw0 <= frame <= fw1):
        strength = min(float(strength), 0.7)
    if not _flash_ok(frame):
        return False
    env = _env()
    if env is None or not hasattr(env, "flash"):
        return False
    try:
        applied = env.flash(int(frame), strength=strength, duration=int(duration))
    except Exception as ex:                                  # environment not built in this scene
        print(f"[vfx] environment.flash skipped at {frame}: {ex}")
        return False
    if applied is not None and float(applied) <= 0.0:       # refused by the environment's own budget
        return False
    _register_flash(frame)
    return True


def _fighters_at(frame):
    """{rig name: world location (Vector)} of SHINOBI_rig / SAINT_rig at `frame` (rig object = ground point
    between the feet). Restores the current frame. {} when no rig exists."""
    obs = [(n, bpy.data.objects.get(n)) for n in FIGHTERS]
    obs = [(n, o) for n, o in obs if o is not None]
    if not obs:
        return {}
    sc = bpy.context.scene
    keep = (sc.frame_current, sc.frame_subframe)
    try:
        with U.muted_modifiers():
            U.frame_set(frame, sc)
            out = {n: U.world_matrix_of(o).translation.copy() for n, o in obs}
    finally:
        sc.frame_set(keep[0], subframe=keep[1])
    return out


def _as_point(p, frame):
    """Point (x, y[, z]) | object | name | (rig, bone) -> np.array(3) at `frame`."""
    if p is None:
        return None
    if _is_target(p):
        sc = bpy.context.scene
        keep = (sc.frame_current, sc.frame_subframe)
        try:
            return np.asarray(_target_pos(p, frame), float)
        finally:
            sc.frame_set(keep[0], subframe=keep[1])
    p = [float(x) for x in p]
    return np.array(p + [0.0] * (3 - len(p)))


def bolt_guard(frame, points, exempt=(), radius=BOLT_GUARD_R, label="bolt", mode="warn"):
    """Environmental lightning must never land on or near a fighter (DIRECTION / deny-list): warn (or raise when
    mode='raise') for every point of `points` within `radius` m (XY) of SHINOBI_rig / SAINT_rig at `frame`
    (rigs named in `exempt` are skipped - e.g. the cutter of the S21 bolt). Returns the list of warnings."""
    if mode is None:
        return []
    rigs = _fighters_at(frame)
    msgs = []
    for nm, loc in rigs.items():
        if nm in exempt:
            continue
        for p in points:
            d = math.hypot(float(p[0]) - loc.x, float(p[1]) - loc.y)
            if d < radius:
                msgs.append(f"{label} @{frame}: point ({p[0]:.1f}, {p[1]:.1f}, {p[2]:.1f}) is {d:.1f} m from {nm} "
                            f"(< {radius:.0f} m)")
    for m in msgs:
        print("[vfx] WARNING " + m)
    _STATE.setdefault("warnings", []).extend(msgs)
    if msgs and mode == "raise":
        raise ValueError("; ".join(msgs))
    return msgs


def lightning_bolt(frame, start, end, branches=3, duration=4, seed=0, fork_at=None, fork_ends=None,
                   away_from=None, second_fork=True, fork_delay=0, strength=80.0, color='electric', width=0.06,
                   halo=True, flash=True, flash_strength=0.7, light=None, light_energy=4.0e4, arch=0.34,
                   guard="warn", name=None):
    """Environmental lightning: midpoint-displacement polylines (main channel + `branches` branches with
    sub-branches) -> thin emissive tubes (GN Curve to Mesh, radius tapering) + a faint wide halo tube.
    Visible `duration` frames (2-4) from `frame` with a per-frame flicker on the TUBES only (bright stroke, dim,
    re-stroke ...); emission `strength` 50-200 (rule 7), bloom does the glow; colour 'electric' (lightning only).
    Light: an unshadowed point light (light_energy W) as ONE decaying pulse (1.0 -> 0.45 -> 0, no re-stroke),
    only if the flash budget allows (>= config.FLASH_MIN_GAP frames from every earlier flash; same frame merges)
    - light=None: only for strikes within BOLT_LIGHT_RANGE m of the arena centre. flash=True: also
    environment.flash(frame, flash_strength, 2) within the same budget.
    CUT bolt (S21 Raikiri): fork_at = just above the blade; the channel stops there and forks. fork_ends=[p1, p2]
    gives the forks explicitly (recipe: [pine_top, ground point behind the elder]); otherwise one fork goes to
    `end` and, if away_from (the OPPONENT: point, object, name or (rig, bone)) is known - given, or the fighter
    rig farther from fork_at - a short steep second fork strikes the ground 2.4-3.4 m BEHIND/beside the cutter,
    away from the opponent (second_fork=False: none). Forks never mirror toward anyone; the first fork arches
    (apex >= arch * span above its chord) and every fork keeps the clearance floor (fork_floor) until its strike
    zone; a cut bolt's branches stay >= 8 m up. Forks appear fork_delay frames after the channel.
    guard ('warn' | 'raise' | None): bolt_guard() on the strike point / fork ends / branch tips vs the fighters
    (the cutter is exempt for a cut bolt). Returns dict(obj, light, mat, levels, lines, warnings)."""
    rng = _rng("bolt", frame, seed)
    rigs = {}
    if fork_at is not None and away_from is None and not fork_ends and second_fork:
        rigs = _fighters_at(frame)
        if len(rigs) >= 2:              # the rig nearer the fork point is the cutter, the other the opponent
            far = max(rigs, key=lambda n: math.hypot(rigs[n].x - fork_at[0], rigs[n].y - fork_at[1]))
            away_from = tuple(rigs[far])
    away = _as_point(away_from, frame)
    lines, info = _bolt_geometry(start, end, branches, rng, width, fork_at, fork_ends, arch=arch, away_from=away,
                                 second_fork=second_fork)
    verts, edges, rad, lvl, uu = [], [], [], [], []
    for pts, r, lv, u0, u1, _kind in lines:
        b = len(verts)
        verts += [tuple(p) for p in pts]
        rad += list(r)
        lvl += [float(lv)] * len(pts)
        uu += list(np.linspace(u0, u1, len(pts)))
        edges += [(b + i, b + i + 1) for i in range(len(pts) - 1)]
    # guard: strike points / fork ends / branch tips vs the fighters
    tips = [pts[-1] for pts, _r, _lv, _u0, _u1, kind in lines if kind == "branch"]
    warn = []
    if guard:
        if fork_at is None:
            warn = bolt_guard(frame, [np.asarray(end, float)] + tips, mode=guard)
        else:
            cutter = ()
            rigs = rigs or _fighters_at(frame)
            if rigs:
                cutter = (min(rigs, key=lambda n: math.hypot(rigs[n].x - fork_at[0], rigs[n].y - fork_at[1])),)
            warn = bolt_guard(frame, list(info["fork_ends"]) + tips, exempt=cutter, mode=guard)
    col = _collection("lightning")
    nm = _uname(name or f"VFX_bolt_{int(frame)}_{seed}")
    ob = U.mesh_from_data(nm, verts, edges=edges, collection=col)
    U.add_attribute(ob.data, "rad", np.array(rad, np.float32), 'FLOAT')
    U.add_attribute(ob.data, "lvl", np.array(lvl, np.float32), 'FLOAT')
    U.add_attribute(ob.data, "u", np.array(uu, np.float32), 'FLOAT')
    _no_shadow(ob)
    mat, val = _bolt_material(nm + "_mat", color)
    pts, lv = _bolt_schedule(frame, duration, rng)
    time_curve(mat.node_tree, f'nodes["{val.name}"].outputs[0].default_value', [(p[0], p[1] * strength, p[2])
                                                                                 for p in pts])
    halo_mat = None
    if halo:
        halo_mat, hval = _bolt_material(nm + "_halo_mat", color, halo=True)
        time_curve(halo_mat.node_tree, f'nodes["{hval.name}"].outputs[0].default_value',
                   [(p[0], p[1] * strength * 0.01, p[2]) for p in pts])
    fxc = _clock()
    t0 = fxc.fx_time_at(frame)
    t1 = fxc.fx_time_at(frame + len(lv))
    ng = U.gn_new_tree("GN_" + nm, inputs=[("Time", "FLOAT", 0.0), ("Material", "MATERIAL"),
                                           ("HaloMat", "MATERIAL"), ("Halo", "BOOL", bool(halo)),
                                           ("Fork T", "FLOAT", fxc.fx_time_at(frame + fork_delay))])
    nb = U.NB(ng)
    gi = nb.gi
    # forks (u >= 0.6 on a cut bolt) wait for fork_delay
    keep = nb.bmath('OR', nb.cmp('LESS_THAN', nb.attr("u"), 0.6 if fork_at is not None else 2.0),
                    nb.cmp('GREATER_EQUAL', gi['Time'], gi['Fork T']))
    curve = nb.n('GeometryNodeMeshToCurve', gi['Geometry'])
    # 5.x: Curve to Mesh no longer scales the profile by the curve radius implicitly -> feed 'Scale'
    rad = nb.math('MULTIPLY', nb.attr("rad"), nb.switch(keep, 0.0, 1.0))
    prof = nb.n('GeometryNodeCurvePrimitiveCircle', Resolution=6, Radius=1.0)
    tube = nb.n('GeometryNodeCurveToMesh', curve, prof['Curve'], Scale=rad, Fill_Caps=False)
    tube = nb.n('GeometryNodeSetMaterial', tube, None, gi['Material'])
    prof2 = nb.n('GeometryNodeCurvePrimitiveCircle', Resolution=8, Radius=7.0)
    tube2 = nb.n('GeometryNodeCurveToMesh', curve, prof2['Curve'], Scale=rad, Fill_Caps=False)
    tube2 = nb.n('GeometryNodeSetMaterial', tube2, None, gi['HaloMat'])
    tube2 = nb.switch(gi['Halo'], None, tube2, 'GEOMETRY')
    joined = nb.n('GeometryNodeJoinGeometry', tube2, tube)
    gate = nb.bmath('AND', nb.cmp('GREATER_EQUAL', gi['Time'], t0 - 0.02), nb.cmp('LESS_EQUAL', gi['Time'], t1 + 0.02))
    nb.link(nb.switch(gate, None, joined, 'GEOMETRY'), nb.go['Geometry'])
    nb.layout()
    U.gn_modifier(ob, ng, Material=mat, **({"HaloMat": halo_mat} if halo_mat else {}))
    fxc.drive_gn_input(ob, "Time")
    ob["vfx_window"] = (float(frame), float(frame + len(lv)))
    strike = np.asarray(end if fork_at is None else fork_at, float)
    if light is None:
        c0 = config.ARENA_CENTER
        light = math.hypot(strike[0] - c0[0], strike[1] - c0[1]) <= BOLT_LIGHT_RANGE
    lob = None
    if light:
        if _flash_ok(frame):
            _register_flash(frame)
            e = np.asarray(end, float)
            lob = _point_light(nm + "_L", tuple(e + (strike - e) * 0.3) if fork_at is not None else
                               tuple(strike + (np.asarray(start, float) - strike) * 0.3), color, "lightning",
                               radius=1.5, cutoff=250.0, window=(frame - 1, frame + 3))
            f = float(frame)
            time_curve(lob.data, "energy", [(f - 1.0, 0.0, 'CONSTANT'), (f, light_energy, 'CONSTANT'),
                                            (f + 1.0, 0.45 * light_energy, 'CONSTANT'), (f + 2.0, 0.0, 'CONSTANT')])
        else:
            print(f"[vfx] lightning_bolt @{frame}: point light skipped (flash budget, FLASH_MIN_GAP)")
    if flash:
        env_flash(frame, flash_strength, 2)
    return dict(obj=ob, light=lob, mat=mat, levels=lv, lines=lines, warnings=warn, fork_ends=info["fork_ends"],
                strike_from=info["strike_from"])


# ================================================================================================ afterglow
def _blade_dims(tip):
    """(blade width at the base, near the tip, sori) for the character owning a blade socket (characters.DIMS)."""
    nm = getattr(tip, "name", str(tip)).upper()
    try:
        import characters
        D = characters.DIMS["SHINOBI" if "SHINOBI" in nm else "SAINT"]
        return float(D["blade_width"]), float(D["blade_width_tip"]), float(D["sori"])
    except Exception:
        return 0.046, 0.033, 0.021


def blade_afterglow(tip_obj, base_obj, f0, f1, color='afterglow', strength=2.0, width=0.0016, strike_u=0.8,
                    name=None):
    """S21, after the Raikiri cut: the CUTTING EDGE glows for a few frames - a thin hot line (not a sheath,
    not arcs, nothing leaves the blade: deny-list) along the edge (-Z of the blade frame, following the blade
    width and sori from characters.DIMS), brightest at the struck point (strike_u: 0 = base .. 1 = tip) and
    fading toward the base; over [f0, f1] (keep it 3-4 frames) the glow dims 1 -> 0.55 -> 0.25 -> 0 and draws
    back toward the struck point (real frames). Parented to the tip socket (follows the blade, motion blur
    included). Colour 'afterglow' = hot white with a hint of blue (never the lightning's electric blue).
    Returns the object."""
    tip = _as_obj(tip_obj)
    base = _as_obj(base_obj)
    Mt = U.world_matrix_of(tip)
    pb = Mt.inverted() @ U.world_pos_of(base)
    L = pb.length
    axis = pb.normalized()                                        # tip -> base (tip-local)
    edge = None
    for cand in ((0.0, 0.0, -1.0), (0.0, -1.0, 0.0), (1.0, 0.0, 0.0)):   # blade frame: -Z = cutting edge
        e = Vector(cand)
        e = e - axis * e.dot(axis)
        if e.length > 0.3:                                        # (not along the blade: sockets of other rigs)
            edge = e.normalized()
            break
    side = axis.cross(edge).normalized()
    wb, wt, sori = _blade_dims(tip)
    seg, rings = 6, 25
    v, f, uu = [], [], []
    for i in range(rings):
        u = 1.0 - i / (rings - 1)                                 # 1 at the tip .. 0 at the base
        wu = (wb + (wt - wb) * u) * (1.0 - _smooth01((u - 0.93) / 0.07))
        off = sori * 4.0 * u * (1.0 - u) + 0.5 * wu + 0.0012        # centre line bulges to the edge + half width
        c = axis * (L * (1.0 - u)) + edge * off
        r = width * (0.35 + 0.65 * math.sqrt(max(0.0, min(1.0, 4.0 * u * (1.0 - u) + 0.3))))
        for j in range(seg):
            a = 2 * math.pi * j / seg
            v.append(tuple(c + (edge * math.cos(a) + side * math.sin(a)) * r))
            uu.append(u)
    for i in range(rings - 1):
        for j in range(seg):
            k = (j + 1) % seg
            f.append((i * seg + j, i * seg + k, (i + 1) * seg + k, (i + 1) * seg + j))
    col = _collection("afterglow")
    nm = _uname(name or f"VFX_afterglow_{int(f0)}")
    mat, nb, out = _mat(nm + "_mat")
    glow = nb.n('ShaderNodeValue', name="Glow")
    spread = nb.n('ShaderNodeValue', name="Spread")
    u_at = U.attribute_node(mat, "u", 'GEOMETRY').outputs["Fac"]
    du = nb.math('DIVIDE', nb.math('SUBTRACT', u_at, float(strike_u)), spread.out)
    prof = nb.math('EXPONENT', nb.math('MULTIPLY', nb.math('MULTIPLY', du, du), -1.0))
    em = nb.n('ShaderNodeEmission', Color=(*_color(color), 1.0),
              Strength=nb.math('MULTIPLY', glow.out, prof))
    nb.link(nb.n('ShaderNodeAddShader', nb.n('ShaderNodeBsdfTransparent'), em), U.socket_in(out.node, "Surface"))
    mat.surface_render_method = 'BLENDED'
    ob = U.mesh_from_data(nm, v, faces=f, collection=col, materials=[mat], smooth=True)
    U.add_attribute(ob.data, "u", np.array(uu, np.float32), 'FLOAT')
    _no_shadow(ob)
    ob.parent = tip
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_basis = Matrix.Identity(4)
    env = (1.0, 0.55, 0.25, 0.0)
    n = max(1, int(round(f1 - f0)))
    g_pts, s_pts = [(f0 - 1.0, 0.0, 'CONSTANT')], []
    for i in range(n + 1):
        e = env[min(len(env) - 1, int(round(i * 3.0 / n)))]
        g_pts.append((f0 + i, strength * e, 'CONSTANT'))
        s_pts.append((f0 + i, 0.4 - 0.25 * i / n, 'CONSTANT'))
    g_pts.append((f0 + n + 1, 0.0, 'CONSTANT'))
    time_curve(mat.node_tree, 'nodes["Glow"].outputs[0].default_value', g_pts)
    time_curve(mat.node_tree, 'nodes["Spread"].outputs[0].default_value', s_pts)
    fxc = _clock()
    _add_gate(ob, fxc.fx_time_at(f0) - 0.02, fxc.fx_time_at(f0 + n + 1) + 0.02)
    ob["vfx_window"] = (float(f0), float(f1))
    return ob


def _smooth01(x):
    x = min(1.0, max(0.0, float(x)))
    return x * x * (3.0 - 2.0 * x)


# ================================================================================================ tree strike
def _pine_objects():
    names = ("ENV_pine", "ENV_pine_half_A", "ENV_pine_half_B")
    return [bpy.data.objects.get(n) for n in names]


def _pivot_rotation_keys(ob, f0, frames, pivot, axis, angle_deg, kind="out_back"):
    """Bake LINEAR keys rotating `ob` about a world pivot/axis by an eased angle over `frames`."""
    from mathutils import Quaternion
    M0 = U.world_matrix_of(ob)                      # hidden objects: rebuilt from matrix_basis (stale matrix_world)
    P = Vector(pivot)
    ob.rotation_mode = 'XYZ'
    for i in range(frames + 1):
        a = math.radians(angle_deg) * U.ease(i / frames, kind)
        R = Quaternion(Vector(axis).normalized(), a).to_matrix().to_4x4()
        W = Matrix.Translation(P) @ R @ Matrix.Translation(-P) @ M0
        if ob.parent is not None:
            W = (ob.parent.matrix_world @ ob.matrix_parent_inverse).inverted() @ W
        loc, rot, _sc = W.decompose()
        U.key(ob, "location", f0 + i, tuple(loc), interp='LINEAR')
        U.key(ob, "rotation_euler", f0 + i, tuple(rot.to_euler('XYZ', ob.rotation_euler)), interp='LINEAR')


def _split_face_points(half, n, z_lo, z_hi, rng):
    """n points (half-local coords) on the half's split faces (material named '*split*', else the faces nearest
    the local plane y = 0) between local heights z_lo..z_hi, area-weighted."""
    me = half.data
    idx = {i for i, m in enumerate(me.materials) if m is not None and "split" in m.name.lower()}
    polys = [p for p in me.polygons if p.material_index in idx and z_lo <= p.center.z <= z_hi]
    if not polys:
        polys = [p for p in me.polygons if abs(p.center.y) < 0.05 and z_lo <= p.center.z <= z_hi]
    if not polys:
        return None
    tris, areas = [], []
    for p in polys:
        vs = [me.vertices[i].co.copy() for i in p.vertices]
        for k in range(1, len(vs) - 1):
            a, b, c = vs[0], vs[k], vs[k + 1]
            tris.append((a, b, c))
            areas.append(max(1e-9, (b - a).cross(c - a).length * 0.5))
    w = np.array(areas) / np.sum(areas)
    pick = rng.choice(len(tris), n, p=w)
    r1, r2 = rng.random(n), rng.random(n)
    out = []
    for t, x, y in zip(pick, r1, r2):
        sx = math.sqrt(x)
        a, b, c = tris[t]
        out.append(tuple(a * (1 - sx) + b * (sx * (1 - y)) + c * (sx * y)))
    return np.array(out)


def _fire_patch(name, f0, f_out, points, parent=None, height=0.9, seed=0, out_frames=20):
    """Static flames at `points` (local coords of `parent` when given - the object is parented with an identity
    inverse, so it moves with e.g. a falling pine half): the ring's tongue shapes / shader / flicker / licking,
    igniting over ~4 frames at f0, dying over out_frames after f_out. Fixed pool, gated. Returns the object."""
    fxc = _clock()
    t0, t_out = fxc.fx_time_at(f0), fxc.fx_time_at(f_out)
    out_dur = out_frames / FPS
    P = np.asarray(points, float).reshape(-1, 3)
    n = len(P)
    rng = _rng("fire_patch", name, seed, n)
    ob = U.mesh_from_data(_uname(name), P, collection=_collection("fire"))
    _no_shadow(ob)
    me = ob.data
    lead = rng.random(n) < 0.3
    for k, v in dict(hf=np.where(lead, rng.uniform(1.0, 1.6, n), rng.uniform(0.35, 0.9, n)),
                     wf=rng.uniform(0.7, 1.2, n), ph=rng.uniform(0, 100, n), rz=rng.uniform(0, 2 * math.pi, n),
                     lean=rng.normal(0, 0.1, n)).items():
        U.add_attribute(me, k, np.asarray(v, np.float32), 'FLOAT')
    U.add_attribute(me, "pick", rng.choice([0, 1, 1, 2], n).astype(np.int32), 'INT')
    ng = U.gn_new_tree("GN_" + ob.name, inputs=[
        ("Time", "FLOAT", 0.0), ("T0", "FLOAT", t0), ("TOut", "FLOAT", t_out), ("OutDur", "FLOAT", out_dur),
        ("Height", "FLOAT", float(height)), ("Tongues", "COLLECTION"), ("Material", "MATERIAL")])
    nb = U.NB(ng)
    gi = nb.gi
    t = nb.math('SUBTRACT', gi['Time'], gi['T0'])
    ramp = nb.map_range(t, 0.0, 4.0 / FPS, 0.0, 1.0, interp='SMOOTHSTEP')
    outf = nb.map_range(gi['Time'], gi['TOut'], nb.math('ADD', gi['TOut'], gi['OutDur']), 1.0, 0.0,
                        interp='SMOOTHSTEP')
    ph = nb.attr("ph")
    nz1 = nb.noise(vector=nb.xyz(ph, 0.0, 0.0), w=nb.math('MULTIPLY', gi['Time'], 2.6), scale=1.0, detail=1.0,
                   dims='4D')
    nz2 = nb.noise(vector=nb.xyz(0.0, ph, 0.0), w=nb.math('MULTIPLY', gi['Time'], 1.4), scale=1.0, detail=1.0,
                   dims='4D')
    flick = nb.map_range(nz1['Fac'], 0.3, 0.7, 0.0, 1.0)
    hz = nb.math('MULTIPLY', nb.math('MULTIPLY', gi['Height'], nb.attr("hf")),
                 nb.math('MULTIPLY', nb.math('MULTIPLY', ramp, outf), nb.math('ADD', 0.65, nb.math('MULTIPLY', flick, 0.7))))
    wxy = nb.math('MULTIPLY', nb.math('MULTIPLY', gi['Height'], nb.math('MULTIPLY', nb.attr("wf"), 0.32)),
                  nb.math('MULTIPLY', nb.math('ADD', 0.5, nb.math('MULTIPLY', ramp, 0.5)), nb.math('SQRT', outf)))
    alive = nb.bmath('AND', nb.cmp('GREATER_EQUAL', t, 0.0), nb.cmp('GREATER_THAN', outf, 0.002))
    hz = nb.switch(alive, 0.0, hz)
    wxy = nb.switch(alive, 0.0, wxy)
    sway = nb.vmath('SCALE', nb.vmath('SUBTRACT', nz2['Color'], (0.5, 0.5, 0.5)), scale=0.6)
    eul = nb.vmath('ADD', nb.xyz(nb.attr("lean"), nb.attr("lean"), nb.attr("rz")),
                   nb.vmath('MULTIPLY', sway, (1.0, 1.0, 0.0)))
    rot = nb.n('FunctionNodeEulerToRotation', eul)['Rotation']
    tci = nb.n('GeometryNodeCollectionInfo', gi['Tongues'], True, True, transform_space='ORIGINAL')
    inst = nb.n('GeometryNodeInstanceOnPoints', Points=gi['Geometry'], Instance=tci['Instances'], Pick_Instance=True,
                Instance_Index=nb.attr("pick", 'INT'), Rotation=rot, Scale=nb.xyz(wxy, wxy, hz))
    inst = nb.store(inst, "flick", flick, 'FLOAT', 'INSTANCE')
    real = nb.n('GeometryNodeRealizeInstances', inst)
    p = nb.n('GeometryNodeInputPosition')['Position']
    nz3 = nb.noise(vector=nb.vmath('ADD', nb.vmath('SCALE', p, scale=1.1),
                                   nb.vmath('SCALE', (0.0, 0.0, -1.0), scale=nb.math('MULTIPLY', gi['Time'], 1.8))),
                   w=nb.math('MULTIPLY', gi['Time'], 1.0), scale=1.0, detail=2.0, dims='4D')
    amp = nb.math('MULTIPLY', nb.math('POWER', nb.attr("h"), 1.3), nb.math('MULTIPLY', gi['Height'], 0.45))
    off = nb.vmath('MULTIPLY', nb.vmath('SCALE', nb.vmath('SUBTRACT', nz3['Color'], (0.5, 0.5, 0.5)), scale=amp),
                   (2.0, 2.0, 0.8))
    disp = nb.n('GeometryNodeSetPosition', real, Offset=off)
    mat_n = nb.n('GeometryNodeSetMaterial', disp, None, gi['Material'])
    nb.link(_fx_gate(nb, mat_n, nb.math('SUBTRACT', gi['T0'], 0.05),
                     nb.math('ADD', nb.math('ADD', gi['TOut'], gi['OutDur']), 0.1)), nb.go['Geometry'])
    nb.layout()
    U.gn_modifier(ob, ng, Tongues=_tongue_sources(), Material=_fire_material())
    fxc.drive_gn_input(ob, "Time")
    if parent is not None:
        ob.parent = parent
        ob.matrix_parent_inverse = Matrix.Identity(4)
    ob["vfx_window"] = (float(f0), float(f_out + out_frames))
    return ob


def tree_strike(frame, pos=None, seed=0, split_deg=26.0, split_frames=16, flame=True, flame_until=None,
                steam_until=None, flash=True, light_energy=6.0e4):
    """S21: the forked bolt splits the lone pine. At `frame`: swap ENV_pine -> ENV_pine_half_A/B (environment
    objects; keyed with bl_util.key_visible like every prop swap), the halves fall apart (rotation about their
    base, eased with a small overshoot, split_deg over split_frames), a white-blue light pulse (2 f, only within
    the flash budget) + environment.flash, a burst of hot sparks, then FLAMES ALONG THE SPLIT: tongues on both
    split faces between ~1.2 and ~5 m up the trunk (a 2.5-4 m tall burning seam, parented to the falling halves)
    burning until flame_until (default: the end of the strike's shot = S21 2592) and dying over 20 f; then STEAM
    rising in the rain until steam_until (default: end of Act III) with an ember glow at its base (emission >= 1.0,
    readable between the S22 strobe flashes). pos: the strike point (default: the top of ENV_pine). Missing pine
    objects -> the swap is skipped (logged) and the flames burn in a column below pos. Returns dict."""
    res = {}
    pine, ha, hb = _pine_objects()
    if pos is None:
        if pine is None:
            raise ValueError("tree_strike: pos is required when ENV_pine does not exist")
        M = U.world_matrix_of(pine)
        corners = [M @ Vector(c) for c in pine.bound_box]
        pos = (M.translation.x, M.translation.y, max(c.z for c in corners) - 0.3)
    pos = tuple(float(x) for x in pos)
    act3_end = next(a["end"] for a in config.ACTS if a["id"] == "act3")
    shot = config.shot_at(int(frame))
    f_fl = float(flame_until if flame_until is not None else (shot["end"] if shot else frame + 95))
    rng = _rng("tree_strike", frame, seed)
    halves_ok = pine is not None and ha is not None and hb is not None
    if halves_ok:
        U.key_visible(pine, frame - 1, True)
        U.key_visible(pine, frame, False)
        for h in (ha, hb):
            U.key_visible(h, frame - 1, False)
            U.key_visible(h, frame, True)
        bpy.context.view_layer.update()
        mats = {h.name: U.world_matrix_of(h) for h in (ha, hb)}     # halves are hidden now: no stale matrices
        base = Vector((pos[0], pos[1], min(m.translation.z for m in mats.values())))
        for sign, h in ((1.0, ha), (-1.0, hb)):
            corners = [mats[h.name] @ Vector(c) for c in h.bound_box]
            cen = sum(corners, Vector()) / 8.0
            zmin = min(c.z for c in corners)
            out = Vector((cen.x - pos[0], cen.y - pos[1], 0.0))
            if out.length < 1e-3:
                out = Vector((sign, 0.0, 0.0))
            out.normalize()
            axis = Vector((0.0, 0.0, 1.0)).cross(out)
            _pivot_rotation_keys(h, frame, split_frames, (base.x + out.x * 0.15, base.y + out.y * 0.15, zmin),
                                 axis, split_deg * (1.0 if sign > 0 else 0.85))
        res["halves"] = (ha, hb)
    else:
        print("[vfx] tree_strike: ENV_pine / ENV_pine_half_A / ENV_pine_half_B not found - swap skipped")
    if _flash_ok(frame):
        _register_flash(frame)
        L = _point_light(f"VFX_tree_strike_{int(frame)}_L", pos, 'electric', "lightning", radius=2.0, cutoff=120.0,
                         window=(frame - 1, frame + 3))
        time_curve(L.data, "energy", [(frame - 1, 0.0, 'CONSTANT'), (frame, light_energy, 'CONSTANT'),
                                      (frame + 1, light_energy * 0.45, 'CONSTANT'), (frame + 2, 0.0, 'CONSTANT')])
        res["light"] = L
    if flash:
        env_flash(frame, 0.7, 2)
    res["sparks"] = sparks(frame, pos, direction=(0, 0, 1), count=90, speed=7.0, life=16, color='white',
                           scale=1.6, seed=seed + 11, spread=110.0, light=False, name=f"VFX_tree_sparks_{int(frame)}")
    ground = pos[2] - 8.0
    if halves_ok:
        ground = min(m.translation.z for m in mats.values())
    if flame:
        fires = []
        if halves_ok:
            for h in (ha, hb):
                pts = _split_face_points(h, 34, 1.2, 5.2, rng)
                if pts is not None:
                    fires.append(_fire_patch(f"VFX_tree_fire_{int(frame)}_{h.name[-1]}", frame + 1, f_fl, pts,
                                             parent=h, height=0.95, seed=seed))
        if not fires:                                   # no halves: a burning column under the strike point
            zs = np.linspace(ground + 1.2, ground + 5.2, 30)
            pts = np.column_stack([np.full(30, pos[0]) + rng.normal(0, 0.12, 30),
                                   np.full(30, pos[1]) + rng.normal(0, 0.12, 30), zs])
            fires.append(_fire_patch(f"VFX_tree_fire_{int(frame)}", frame + 1, f_fl, pts, height=0.95, seed=seed))
        res["fire"] = fires
        fl_pos = (pos[0], pos[1], ground + 3.2)
        res["fire_lights"] = []
        for k in range(2):
            FL = _point_light(f"VFX_tree_fire_{int(frame)}_L{k}", (fl_pos[0] + (0.6 if k else -0.6), fl_pos[1],
                                                                   fl_pos[2] + k), COLORS["fire"], "fire",
                              radius=0.5, cutoff=40.0, window=(frame, f_fl + 21))
            FL.data.color = (1.0, 0.42, 0.12)
            t1, t2 = fx_time(frame + 1), fx_time(f_fl)
            time_expr(FL.data, "energy", f"300*clamp((t-{_n(t1)})/0.2,0,1)*(1-clamp((t-{_n(t2)})/0.83,0,1))"
                                         f"*(.8+.12*sin(t*14.1+{k * 1.7:.1f})+.08*sin(t*29.3+{k:.1f}))")
            res["fire_lights"].append(FL)
        res["embers"] = embers(frame + 2, f_fl + 10, (pos[0], pos[1], ground + 1.0), 0.8, rate=14.0,
                               seed=seed + 3, height=(0.5, 4.5), rise=1.6, size=0.02,
                               name=f"VFX_tree_embers_{int(frame)}")
    res["steam"] = steam(f_fl - 30, steam_until or act3_end, (pos[0], pos[1], ground), 2.0, height=10.0,
                         density=1.8, rise=2.0, glow=True, glow_strength=1.3, glow_h=0.32, flare=0.55, seed=seed,
                         name=f"VFX_tree_steam_{int(frame)}")
    return res


# ================================================================================================ strobe
def strobe(frames, strength=0.7, duration=2, bolts=True, seed=0, center=(0.0, 0.0), dist=(90.0, 220.0),
           bolt_strength=60.0):
    """S22 lightning-only lighting: for each requested frame (sorted) issue environment.flash(frame, strength,
    duration), dropping frames closer than config.FLASH_MIN_GAP to an accepted one (DIRECTION §5: >= 12 f apart,
    <= 70 %). bolts=True also draws a distant environmental bolt for each accepted flash (random azimuth,
    `dist` metres from center, no extra light/flash). Returns the list of accepted frames."""
    acc = []
    for f in sorted(int(x) for x in frames):
        if acc and f - acc[-1] < config.FLASH_MIN_GAP:
            continue
        if not _flash_ok(f):
            continue
        acc.append(f)
    rng = _rng("strobe", seed, len(acc))
    for f in acc:
        env_flash(f, strength, duration)
        if bolts:
            az = rng.uniform(0, 2 * math.pi)
            d = rng.uniform(*dist)
            x, y = center[0] + d * math.cos(az), center[1] + d * math.sin(az)
            drift = rng.normal(0, 12.0, 2)
            lightning_bolt(f, (x + drift[0], y + drift[1], rng.uniform(80, 120)), (x, y, 0.0),
                           branches=int(rng.integers(2, 5)), duration=duration + 1, seed=seed * 1000 + f,
                           strength=bolt_strength, width=0.12 * d / 100.0, light=False, flash=False,
                           name=f"VFX_strobe_bolt_{f}")
    return acc


# ================================================================================================ rain
def _drop_source():
    """Rain streak source: a thin quad in the YZ plane (normal +X), length 1 along -Z (head at z=0), width 1
    along Y (+-0.5), 3 segments along the length. Vertex attributes: ru (0 edge .. 1 centre line across),
    rv (0 head .. 1 tail) for the soft alpha profile."""
    col = _collection("sources")
    v, f, ru, rv = [], [], [], []
    zs = (0.0, -0.15, -0.6, -1.0)
    ys = (-0.5, 0.0, 0.5)
    for z in zs:
        for y in ys:
            v.append((0.0, y, z))
            ru.append(1.0 - abs(y) * 2.0)
            rv.append(-z)
    for i in range(len(zs) - 1):
        for j in range(len(ys) - 1):
            a = i * 3 + j
            f.append((a, a + 1, a + 4, a + 3))
    return _hidden_source("VFX_src_drop", v, f, col, attrs={"ru": np.array(ru, np.float32),
                                                             "rv": np.array(rv, np.float32)})


def _rain_material(name="VFX_rain", color='water', brightness=1.0):
    """DITHERED streak material that reads when backlit: Translucent (lit through from lights behind the drops)
    + Glossy (catches rim/flash lights) + a faint emission floor (so the curtain never vanishes in the dark).
    Alpha: soft across (ru) and tapered along (rv) the streak, times 'fade' (INSTANCER: box-edge fade x
    width-compensation). 'rim' (INSTANCER, 0..1: drops bunched at the faces of a rain_split gap) and 'big'
    (hero drops) raise the glossy share, the emission floor and the opacity."""
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    mat, nb, out = _mat(name)
    ru = U.attribute_node(mat, "ru", 'GEOMETRY').outputs["Fac"]
    rv = U.attribute_node(mat, "rv", 'GEOMETRY').outputs["Fac"]
    fade = U.attribute_node(mat, "fade", 'INSTANCER').outputs["Fac"]
    rim = U.attribute_node(mat, "rim", 'INSTANCER').outputs["Fac"]
    big = U.attribute_node(mat, "big", 'INSTANCER').outputs["Fac"]
    c = _color(color)
    tr = nb.n('ShaderNodeBsdfTranslucent', Color=(*c, 1.0))
    gl = nb.n('ShaderNodeBsdfGlossy', Color=(1.0, 1.0, 1.0, 1.0), Roughness=0.2)
    gmix = nb.math('ADD', 0.25, nb.math('ADD', nb.math('MULTIPLY', rim, 0.4), nb.math('MULTIPLY', big, 0.2)),
                   clamp=True)
    boost = nb.math('ADD', 1.0, nb.math('ADD', nb.math('MULTIPLY', rim, 3.0), nb.math('MULTIPLY', big, 0.8)))
    em = nb.n('ShaderNodeEmission', Color=(*c, 1.0), Strength=nb.math('MULTIPLY', boost, 0.035 * brightness))
    lit = nb.n('ShaderNodeAddShader', nb.n('ShaderNodeMixShader', gmix, tr, gl), em)
    prof = nb.math('MULTIPLY', nb.math('POWER', ru, 0.8),
                   nb.math('MULTIPLY', nb.map_range(rv, 0.0, 0.12, 0.35, 1.0), nb.map_range(rv, 0.55, 1.0, 1.0, 0.0)))
    dens = nb.math('ADD', 1.0, nb.math('ADD', nb.math('MULTIPLY', rim, 0.6), nb.math('MULTIPLY', big, 0.3)))
    alpha = nb.math('MINIMUM', 1.0, nb.math('MULTIPLY', nb.math('MULTIPLY', prof, fade),
                                            nb.math('MULTIPLY', dens, 0.75 * brightness)))
    mix = nb.n('ShaderNodeMixShader', alpha, nb.n('ShaderNodeBsdfTransparent'), lit)
    nb.link(mix, U.socket_in(out.node, "Surface"))
    mat.surface_render_method = 'DITHERED'
    mat.use_backface_culling = False
    mat.diffuse_color = (*c, 1.0)
    return mat


def _curve_points(values, f0, f1, default):
    """float or [(frame, value), ...] -> [(frame, value)] covering [f0, f1]."""
    if values is None:
        values = default
    if np.ndim(values) == 0:
        return [(f0, float(values)), (f1, float(values))]
    return [(float(a), float(b)) for a, b in values]


def _scene_driver(owner, data_path, prop_path, index=-1, points=None):
    """Driver = a scene property (e.g. 'camera.data.lens', 'render.resolution_x'); optional mapping curve."""
    fc = owner.driver_add(data_path) if index < 0 else owner.driver_add(data_path, index)
    for m in list(fc.modifiers):
        fc.modifiers.remove(m)
    d = fc.driver
    d.type = 'AVERAGE'
    while d.variables:
        d.variables.remove(d.variables[0])
    v = d.variables.new()
    v.type = 'SINGLE_PROP'
    v.targets[0].id_type = 'SCENE'
    v.targets[0].id = bpy.context.scene
    v.targets[0].data_path = prop_path
    fc.keyframe_points.clear()
    if points:
        kps = fc.keyframe_points
        kps.add(len(points))
        for k, (x, y) in zip(kps, points):
            k.co = (x, y)
            k.interpolation = 'LINEAR'
        fc.extrapolation = 'CONSTANT'
    else:
        kps = fc.keyframe_points
        kps.add(2)
        kps[0].co, kps[1].co = (0.0, 0.0), (1.0, 1.0)
        for k in kps:
            k.interpolation = 'LINEAR'
        fc.extrapolation = 'LINEAR'
    fc.update()
    return fc


# lens (mm) -> how far ahead of the camera the rain box sits, and its size: wide lenses get a box around the
# camera, telephotos a bigger box pushed out to the subject distance (S05/S24a/S25 are ~135-150 mm from ~50 m)
RAIN_LENS_FORWARD = [(14.0, 7.0), (24.0, 9.0), (35.0, 12.0), (50.0, 16.0), (85.0, 26.0), (135.0, 42.0), (150.0, 46.0)]
RAIN_LENS_BOX = [(14.0, 26.0), (35.0, 30.0), (50.0, 34.0), (85.0, 44.0), (135.0, 58.0), (150.0, 62.0)]
RAIN_NEAR_MAX = 12.0     # the 'near' pool serves DOF shots focused closer than this (m)
SPLIT_RIM = 0.35         # rain_split: rim band width (fraction of the half-width) at each face of the gap ...
SPLIT_SHELL = 0.35       # ... fed by the inner shell of this width (rim density ~2x); deeper drops are blown out
SPLIT_REFILL = 12.0      # m/s: the rain refills the gap from the top, reaching the ground at the window's end


def _rain_object(nm, f0, f1, count, seed, near=False, speed=9.0, wind=(1.3, 0.5), height=16.0, width=0.007,
                 stretch=0.028, color='water', brightness=1.0, hero=0.08):
    """One rain pool (GN, fixed count) - the lens-sized curtain (near=False) or the focus-plane 'near' pool
    (near=True: box centred on the active camera's focus point, only while that camera has DOF on and focuses
    closer than RAIN_NEAR_MAX). See rain()."""
    fxc = _clock()
    sc = bpy.context.scene
    rng = _rng("rain", nm, f0, seed, count)
    n = int(count)
    col = _collection("rain")
    ob = U.mesh_from_data(nm, np.zeros((n, 3)), collection=col)
    _no_shadow(ob)
    me = ob.data
    big = (rng.random(n) < hero).astype(np.float32)            # hero drops: wider, brighter
    U.add_attribute(me, "u0", rng.random((n, 3)).astype(np.float32), 'FLOAT_VECTOR')
    U.add_attribute(me, "spd", rng.uniform(0.85, 1.15, n).astype(np.float32), 'FLOAT')
    U.add_attribute(me, "vis", rng.random(n).astype(np.float32), 'FLOAT')
    U.add_attribute(me, "wf", np.where(big > 0, rng.uniform(1.5, 2.1, n), rng.uniform(0.7, 1.2, n)).astype(np.float32),
                    'FLOAT')
    U.add_attribute(me, "big", big, 'FLOAT')
    t0, t1 = fxc.fx_time_at(f0), fxc.fx_time_at(f1)
    ng = U.gn_new_tree("GN_" + nm, inputs=[
        ("Time", "FLOAT", 0.0), ("Rate", "FLOAT", 1.0), ("Intensity", "FLOAT", 1.0), ("Forward", "FLOAT", 12.0),
        ("BoxXY", "FLOAT", 30.0), ("BoxZ", "FLOAT", float(height)), ("Speed", "FLOAT", float(speed)),
        ("Wind", "VECTOR", (float(wind[0]), float(wind[1]), 0.0)), ("Width", "FLOAT", float(width)),
        ("Stretch", "FLOAT", float(stretch)), ("ResX", "FLOAT", float(sc.render.resolution_x)),
        ("Pct", "FLOAT", float(sc.render.resolution_percentage)), ("Drop", "OBJECT"), ("Material", "MATERIAL"),
        ("Splits", "OBJECT"), ("Has Splits", "BOOL", False), ("Clock", "FLOAT", 0.0), ("DOF", "FLOAT", 0.0),
        ("Near Max", "FLOAT", RAIN_NEAR_MAX),
        ("Active From", "FLOAT", t0 - 0.05), ("Active To", "FLOAT", t1 + 0.05)])
    nb = U.NB(ng)
    gi = nb.gi
    cam = nb.n('GeometryNodeInputActiveCamera')
    ci = nb.n('GeometryNodeObjectInfo', cam, False, transform_space='ORIGINAL')
    camd = nb.n('GeometryNodeCameraInfo', cam)
    focus = U.socket_out(camd.node, "Focus Distance")             # honours dof.focus_object (probe p14)
    L = ci['Location']
    fwd = nb.n('FunctionNodeRotateVector', (0.0, 0.0, -1.0), ci['Rotation'])
    fwd = U.socket_out(fwd.node, "Vector")
    if near:
        fcl = nb.math('MAXIMUM', focus, 0.3)
        fwd_d = fcl
        bxy = nb.math('MINIMUM', nb.math('MAXIMUM', nb.math('ADD', nb.math('MULTIPLY', fcl, 0.9), 3.5), 4.5), 12.0)
        bz = nb.math('MINIMUM', nb.math('MAXIMUM', nb.math('ADD', nb.math('MULTIPLY', fcl, 0.9), 3.5), 4.5), 10.0)
    else:
        fwd_d, bxy, bz = gi['Forward'], gi['BoxXY'], gi['BoxZ']
    C = nb.vmath('ADD', L, nb.vmath('SCALE', fwd, scale=fwd_d))
    Cs = nb.sep(C)
    B = nb.xyz(bxy, bxy, bz)
    # keep the box's bottom at/below the ground unless the camera looks far up
    cz = nb.math('MAXIMUM', nb.math('SUBTRACT', nb.math('MULTIPLY', bz, 0.5), 1.0),
                 nb.math('MINIMUM', Cs['Z'], nb.math('MULTIPLY', bz, 0.5)))
    C = nb.xyz(Cs['X'], Cs['Y'], cz)
    lo = nb.vmath('SUBTRACT', C, nb.vmath('SCALE', B, scale=0.5))
    spd = nb.attr("spd")
    vel = nb.vmath('SCALE', nb.vmath('ADD', gi['Wind'], nb.xyz(0.0, 0.0, nb.math('MULTIPLY', gi['Speed'], -1.0))),
                   scale=spd)
    T = gi['Clock']
    home = nb.vmath('ADD', nb.vmath('MULTIPLY', nb.attr("u0", 'FLOAT_VECTOR'), B), nb.vmath('SCALE', vel, scale=T))
    rel = nb.vmath('DIVIDE', nb.vmath('SUBTRACT', home, lo), B)
    fr = nb.vmath('FRACTION', rel)
    pos = nb.vmath('ADD', lo, nb.vmath('MULTIPLY', fr, B))
    frs = nb.sep(fr)

    def edge(x, dead, ramp):
        """0 inside the dead band at each face (the wrap happens there), smooth ramp to 1 over `ramp`."""
        return nb.math('MULTIPLY', nb.map_range(x, dead, dead + ramp, 0.0, 1.0, interp='SMOOTHSTEP'),
                       nb.map_range(x, 1.0 - dead - ramp, 1.0 - dead, 1.0, 0.0, interp='SMOOTHSTEP'))
    # XY: 6 % dead band covers box motion up to ~0.12 box/frame (whip pans move the box centre fast);
    # Z: 2.5 % covers the fall (~0.023 box/frame)
    efade = nb.math('MULTIPLY', nb.math('MULTIPLY', edge(frs['X'], 0.06, 0.06), edge(frs['Y'], 0.06, 0.06)),
                    edge(frs['Z'], 0.025, 0.055))
    # rain_split (inert until finalize() sets 'Splits' / 'Has Splits'): the gap's drops are BLOWN OUT - an
    # inner shell is pushed into a dense, brighter rim band at each face, the deeper ones shrink to 0 (fixed pool:
    # scale, never delete) - so the parting also reads obliquely (a bunching-only remap conserves the drop count
    # along any oblique line of sight and stays invisible). The rain then falls back into the gap from the top:
    # a refill front descends at SPLIT_REFILL m/s (faster than any drop -> every drop is restored exactly once,
    # smoothly) and reaches the ground at the end of the window.
    sp = nb.n('GeometryNodeObjectInfo', gi['Splits'], False, transform_space='ORIGINAL')
    prox = nb.n('GeometryNodeProximity', sp['Geometry'], target_element='FACES')
    nb.set(U.socket_in(prox.node, "Source Position"), pos)
    near_f = nb.n('GeometryNodeSampleNearest', sp['Geometry'], domain='FACE')
    nb.set(U.socket_in(near_f.node, "Sample Position"), pos)
    idx = U.socket_out(near_f.node, "Index")

    def face_attr(name, dtype='FLOAT'):
        si = nb.n('GeometryNodeSampleIndex', data_type=dtype, domain='FACE')
        nb.set(U.socket_in(si.node, "Geometry"), sp['Geometry'])
        nb.set(U.socket_in(si.node, "Value"), nb.attr(name, dtype))
        nb.set(U.socket_in(si.node, "Index"), idx)
        return U.socket_out(si.node, "Value")
    nrm = face_attr("nrm", 'FLOAT_VECTOR')
    s0, s1, swd, top = face_attr("st0"), face_attr("st1"), face_attr("swd"), face_attr("top")
    q = U.socket_out(prox.node, "Position")
    sd = nb.vmath('DOT_PRODUCT', nb.vmath('SUBTRACT', pos, q), nrm)
    inside = nb.cmp('LESS_THAN', nb.math('SUBTRACT', U.socket_out(prox.node, "Distance"), nb.math('ABSOLUTE', sd)),
                    0.05)
    tnow = gi['Time']
    opn = nb.map_range(tnow, s0, nb.math('ADD', s0, 0.12), 0.0, 1.0, interp='SMOOTHSTEP')
    t_hold = nb.math('SUBTRACT', s1, nb.math('DIVIDE', top, SPLIT_REFILL))
    zf = nb.math('SUBTRACT', top, nb.math('MULTIPLY', nb.math('SUBTRACT', tnow, t_hold), SPLIT_REFILL))
    restored = nb.map_range(nb.math('SUBTRACT', nb.sep(pos)['Z'], zf), -0.6, 0.6, 0.0, 1.0, interp='SMOOTHSTEP')
    openness = nb.math('MULTIPLY', opn, nb.math('SUBTRACT', 1.0, restored))
    w = nb.math('MULTIPLY', swd, openness)
    bw = nb.math('MULTIPLY', swd, SPLIT_RIM)                              # rim band width
    sh = nb.math('MULTIPLY', nb.math('MULTIPLY', swd, SPLIT_SHELL), openness)   # shell pushed into the rim
    lo = nb.math('SUBTRACT', w, sh)                                       # deeper drops are blown out
    asd = nb.math('ABSOLUTE', sd)
    x = nb.math('DIVIDE', nb.math('SUBTRACT', asd, lo), nb.math('MAXIMUM', nb.math('ADD', sh, bw), 1e-4), clamp=True)
    new_abs = nb.math('ADD', w, nb.math('MULTIPLY', x, bw))               # [lo, w + b] -> [w, w + b]; identity closed
    in_zone = nb.math('MULTIPLY', nb.cmp('LESS_THAN', asd, nb.math('ADD', w, bw)), inside)
    in_zone = nb.switch(gi['Has Splits'], 0.0, in_zone)
    push = nb.math('MULTIPLY', nb.math('MULTIPLY', nb.math('SIGN', sd), nb.math('SUBTRACT', new_abs, asd)), in_zone)
    keep = nb.math('SUBTRACT', 1.0, nb.math('MULTIPLY', in_zone, nb.math(
        'SUBTRACT', 1.0, nb.map_range(asd, nb.math('SUBTRACT', lo, 0.35), lo, 0.0, 1.0, interp='SMOOTHSTEP'))))
    rimf = nb.math('MULTIPLY', nb.math('MULTIPLY', in_zone, openness), keep)
    pos = nb.vmath('ADD', pos, nb.vmath('SCALE', nrm, scale=push))
    placed = nb.n('GeometryNodeSetPosition', gi['Geometry'], Position=pos)
    inten = gi['Intensity']
    if near:          # only while the active camera uses DOF and focuses close
        inten = nb.math('MULTIPLY', nb.math('MULTIPLY', inten, gi['DOF']),
                        nb.map_range(focus, nb.math('MULTIPLY', gi['Near Max'], 0.7), gi['Near Max'], 1.0, 0.0))
    shown = nb.cmp('LESS_THAN', nb.attr("vis"), inten)
    # screen-space width floor: >= 1.1 px at the drop's distance
    focal = U.socket_out(camd.node, "Focal Length")
    sensor = nb.sep(U.socket_out(camd.node, "Sensor"))['X']
    res = nb.math('MAXIMUM', 16.0, nb.math('MULTIPLY', gi['ResX'], nb.math('DIVIDE', gi['Pct'], 100.0)))
    pix = nb.math('DIVIDE', nb.math('DIVIDE', sensor, nb.math('MAXIMUM', focal, 1.0)), res)   # rad per pixel
    dist = nb.vmath('DISTANCE', pos, L)
    w_phys = nb.math('MULTIPLY', gi['Width'], nb.attr("wf"))
    w_min = nb.math('MULTIPLY', nb.math('MULTIPLY', dist, pix), 1.1)
    w_draw = nb.math('MAXIMUM', w_phys, w_min)
    fade = nb.math('MULTIPLY', efade, nb.math('DIVIDE', w_phys, w_draw))
    if near:          # no drops inside the lens: fade in between 25 % and 60 % of the focus distance
        fcl = nb.math('MAXIMUM', focus, 0.3)
        fade = nb.math('MULTIPLY', fade, nb.map_range(dist, nb.math('MULTIPLY', fcl, 0.25),
                                                      nb.math('MULTIPLY', fcl, 0.6), 0.0, 1.0))
    else:
        fade = nb.math('MULTIPLY', fade, nb.map_range(dist, 0.6, 2.0, 0.0, 1.0))
    vlen = nb.vmath('LENGTH', vel)
    # streak = motion over the shutter + a length floor that grows in slow motion (>= ~7x the drawn width at
    # 1/8 speed) so slowed rain stays elongated drops instead of round 'snow' specks
    slow = nb.math('SUBTRACT', 1.0, nb.math('MINIMUM', gi['Rate'], 1.0))
    ln = nb.math('ADD', nb.math('MULTIPLY', nb.math('MULTIPLY', vlen, gi['Rate']), gi['Stretch']),
                 nb.math('MULTIPLY', w_draw, nb.math('ADD', 2.5, nb.math('MULTIPLY', slow, 5.5))))
    ok = nb.bmath('AND', shown, nb.cmp('GREATER_THAN', efade, 0.001))
    sx = nb.math('MULTIPLY', nb.switch(ok, 0.0, 1.0), keep)
    rot1 = nb.n('FunctionNodeAlignRotationToVector', axis='Z', Vector=vel)['Rotation']
    to_cam = nb.vmath('SUBTRACT', L, pos)
    rot = nb.n('FunctionNodeAlignRotationToVector', rot1, axis='X', pivot_axis='Z', Vector=to_cam)['Rotation']
    inst = nb.n('GeometryNodeInstanceOnPoints', Points=placed,
                Instance=nb.n('GeometryNodeObjectInfo', gi['Drop'], False)['Geometry'], Rotation=rot,
                Scale=nb.xyz(sx, nb.math('MULTIPLY', w_draw, sx), nb.math('MULTIPLY', ln, sx)))
    inst = nb.store(inst, "fade", fade, 'FLOAT', 'INSTANCE')
    inst = nb.store(inst, "rim", rimf, 'FLOAT', 'INSTANCE')
    inst = nb.store(inst, "big", nb.attr("big"), 'FLOAT', 'INSTANCE')
    inst = nb.n('GeometryNodeSetMaterial', inst, None, gi['Material'])
    active = nb.bmath('AND', nb.cmp('GREATER_EQUAL', gi['Time'], gi['Active From']),
                      nb.cmp('LESS_EQUAL', gi['Time'], gi['Active To']))
    nb.link(nb.switch(active, None, inst, 'GEOMETRY'), nb.go['Geometry'])
    nb.layout()
    U.gn_modifier(ob, ng, Drop=_drop_source(), Material=_rain_material(color=color, brightness=brightness))
    fxc.drive_gn_input(ob, "Time")
    _scene_driver(ob, U.gn_path(ob, "ResX"), "render.resolution_x")
    _scene_driver(ob, U.gn_path(ob, "Pct"), "render.resolution_percentage")
    if near:
        _scene_driver(ob, U.gn_path(ob, "DOF"), "camera.data.dof.use_dof")
    else:
        _scene_driver(ob, U.gn_path(ob, "Forward"), "camera.data.lens", points=RAIN_LENS_FORWARD)
        _scene_driver(ob, U.gn_path(ob, "BoxXY"), "camera.data.lens", points=RAIN_LENS_BOX)
    ob["vfx_window"] = (float(f0), float(f1))
    ob["vfx_rain_kind"] = "near" if near else "curtain"
    return ob


def rain(f0, f1, intensity=1.0, time_scale=1.0, count=40000, speed=9.0, wind=(1.3, 0.5), height=16.0,
         width=0.007, stretch=0.028, seed=0, color='water', brightness=1.0, near=8000, near_width=0.0028,
         hero=0.08, name=None):
    """Rain around the ACTIVE camera: fixed pools of pre-stretched streaks (DITHERED, lit Translucent+Glossy so
    they read when backlit, faint emission floor).
      * the CURTAIN (`count` drops): every drop has a home position in a world-anchored lattice tile; the box
        (size + forward offset from the active camera's lens via scene drivers, RAIN_LENS_*) follows the camera
        and drops wrap inside it:  p = C - B/2 + B * fract((u0*B + v*T - (C - B/2)) / B),  v = (wind, -speed)
        per drop, so they stay put in the world while the camera moves (correct parallax, no swimming) and the
        fall is fract(z0 - v*T).
      * the NEAR pool (`near` drops, 0 = none, width `near_width`): a 4.5-12 m box centred on the active camera's
        FOCUS point (GN Camera Info 'Focus Distance', which honours dof.focus_object), shown only while that
        camera has DOF on and focuses closer than RAIN_NEAR_MAX m - the dense band around the subject for ECU /
        telephoto inserts (S24b/c/e) that the lens-sized curtain misses.
    Scale is exactly 0 in a dead band at every box face (XY 6 %, Z 2.5 %) with a smooth ramp inside it, so wrap
    jumps only ever happen on invisible drops (rule 3); `intensity` (float or [(frame, value), ...]) thins the
    rain (e.g. 3470-3500). Streak length = |v| * Rate * stretch + a width-based floor that grows in slow motion
    (>= ~7x the drawn width at 1/8 speed: slowed rain stays elongated, never 'snow'); width >= ~1.1 px at any
    distance (Camera Info + render resolution drivers) with alpha compensated; `hero` = fraction of wider,
    brighter drops. time_scale: float or [(frame, scale), ...] - an extra rain-only clock factor, integrated (no
    jumps); the film clock (config.TIME_WARP) already slows rain 1/8 in S25-S26. rain_split() parts every pool
    (finalize). Gated to [f0, f1]. Returns the curtain object (the near pool: ob['near'] / vfx._STATE['rains'])."""
    fxc = _clock()
    base = name or f"VFX_rain_{int(f0)}"
    obs = [_rain_object(_uname(base), f0, f1, count, seed, near=False, speed=speed, wind=wind, height=height,
                        width=width, stretch=stretch, color=color, brightness=brightness, hero=hero)]
    if near:
        obs.append(_rain_object(_uname(base + "_near"), f0, f1, near, seed + 1, near=True, speed=speed, wind=wind,
                                height=height, width=near_width, stretch=stretch, color=color,
                                brightness=brightness, hero=hero * 1.5))
    ts = _curve_points(time_scale, f0, f1, 1.0)
    ip = _curve_points(intensity, f0, f1, 1.0)
    for ob in obs:
        if all(abs(v - 1.0) < 1e-9 for _, v in ts):     # rain clock = the film clock
            fxc.drive_gn_input(ob, "Clock")
            _drive_rate(ob)
        else:                                            # rain clock = integral of time_scale over the film clock
            fr_ = np.arange(int(f0) - 30, int(f1) + 31)
            tsv = np.interp(fr_, [a for a, _ in ts], [b for _, b in ts])
            fxv = np.array([fxc.fx_time_at(x) for x in fr_])
            clk = np.concatenate([[fxv[0]], fxv[0] + np.cumsum(np.diff(fxv) * tsv[:-1])])
            time_curve(ob, U.gn_path(ob, "Clock"), list(zip(fxv, clk)), frames=False)
            rate = [(x, fxc.speed_at(f) * s, 'CONSTANT') for f, x, s in zip(fr_, fxv, tsv)]
            time_curve(ob, U.gn_path(ob, "Rate"), rate, frames=False)
        time_curve(ob, U.gn_path(ob, "Intensity"), ip, interp='LINEAR')
        _STATE["rains"].append(ob)
    if len(obs) > 1:
        obs[0]["near"] = obs[1].name
    return obs[0]


def rain_split(f0, f1, plane_origin, plane_normal, width=2.2, length=30.0, height=12.0, direction=None, seed=0,
               sheet=True, mist=True):
    """S23: the full-power jodan cut parts the curtain of rain along a vertical plane (no glow - it is all rain).
    The slab around the plane (half-width `width` m, default 2.2) opens within ~0.12 s of fx time after f0: an
    inner shell of its drops is pushed into a dense, brighter rim band (SPLIT_RIM x width, ~2x density, stronger
    glossy) at each face and the deeper drops are blown out (scaled to 0 - the flung sheet shows them go), leaving a
    clear corridor. It holds, then the rain falls back in from the top: a refill
    front descends from `height` at SPLIT_REFILL m/s and reaches the ground at f1 (every drop smooth in time ->
    clean motion blur).
    sheet=True: at f0 a thin vertical sheet of droplets is flung out of the cut plane (+-normal, 0.2-0.4 s) and
    mist=True a thin mist sheet blooms along it - both mark the cut line even face-on. The plane passes through
    plane_origin with (horizontal) normal plane_normal and extends `length` m along `direction` (default: both
    ways along the plane) and from 1 m below ground to `height`. The parting itself is DEFERRED: finalize() builds
    one split mesh (faces carry nrm/st0/st1/swd) and hands it to every rain() pool.
    Staging (measured, sheets rain_split / _oblique / _faceon): the corridor is a gap IN DEPTH, so it only reads
    when the camera looks ALONG the plane - lens axis within ~10 deg of it, camera inside the slab or <= ~2 m from
    it, subject (the elder) inside the corridor: the corridor stays open to a subject D m away while the view
    angle is below asin(width / D). A camera 6 m off the plane at 13 deg (or face-on from the standard +X side)
    sees no gap - only the flung sheet + mist veil mark the cut there. Backlight 150-170 deg from the lens.
    Returns the registration (+ 'sheet', 'mist' objects)."""
    n = Vector(plane_normal)
    n.z = 0.0
    n = n.normalized() if n.length > 1e-6 else Vector((1.0, 0.0, 0.0))
    reg = dict(f0=float(f0), f1=float(f1), origin=tuple(float(x) for x in plane_origin), normal=tuple(n),
               width=float(width), length=float(length), height=float(height),
               direction=None if direction is None else tuple(direction))
    _STATE["splits"].append(reg)
    t, a, b = _split_frame(reg)
    o = Vector(reg["origin"])
    hs = min(float(height), 7.0)
    if sheet:
        rng = _rng("split_sheet", f0, seed)
        cnt = int(max(300, 55 * (b - a)))
        s_ = rng.uniform(a, b, cnt)
        z = o.z + 0.15 + hs * rng.random(cnt) ** 1.3
        nv, tv = np.array(n[:]), np.array(t[:])
        side = np.where(rng.random(cnt) < 0.5, -1.0, 1.0)
        p0 = (np.array(o[:])[None, :] + np.outer(s_, tv) + np.outer(rng.normal(0, 0.06, cnt), nv))
        p0[:, 2] = z
        vel = (np.outer(side * rng.uniform(3.0, 8.0, cnt), nv) + np.outer(rng.normal(0, 0.6, cnt), tv)
               + np.outer(rng.uniform(-0.8, 1.6, cnt), [0.0, 0.0, 1.0]))
        reg["sheet"] = _pool(f"VFX_split_sheet_{int(f0)}_{seed}", "rain", p0, vel, f0 + rng.uniform(0.0, 1.5, cnt),
                             rng.uniform(5.0, 10.0, cnt), gravity=-9.81, drag=rng.uniform(2.0, 3.0, cnt),
                             instance=_needle_source(), material=_water_material(),
                             size=rng.uniform(0.007, 0.014, cnt), shrink=0.3, stretch=0.03, len0=2.5,
                             align='velocity')
    if mist:
        # a thin, wispy veil along the first ~10 m of the cut (seen along the plane it integrates over its whole
        # length, so it stays faint: it marks the line, never a wall)
        a2, b2 = (a, min(b, a + 11.0)) if r_dir(reg) else (max(a, -5.5), min(b, 5.5))
        c = o + t * (0.5 * (a2 + b2))
        mv = _volume_box(f"VFX_split_mist_{int(f0)}_{seed}", "rain", (c.x, c.y, o.z + 0.5 * hs),
                         (1.5 * float(width), (b2 - a2), hs), f0, f0 + 16, shape="sheet", color='steam',
                         density=0.045, anisotropy=0.5, noise_scale=1.6, rise=0.3, evolve=0.6, fade_in=0.05,
                         fade_out=0.8, seed=seed, grow_frames=8, noise2=2.5, contrast=(0.52, 0.72))
        mv.rotation_euler.z = math.atan2(n.y, n.x)          # local X = the plane normal (the thin axis)
        reg["mist"] = mv
    return reg


def r_dir(r):
    """True when a rain_split registration extends one way (from its origin along `direction`)."""
    return r.get("direction") is not None


def _split_frame(r):
    """(in-plane horizontal unit vector t, extent a, b along t) of a rain_split registration."""
    n = Vector(r["normal"])
    t = Vector((0.0, 0.0, 1.0)).cross(n).normalized()
    if r["direction"] is not None:
        d = Vector(r["direction"])
        d.z = 0
        t = d.normalized() if d.length > 1e-6 else t
        return t, -1.0, r["length"]
    return t, -0.5 * r["length"], 0.5 * r["length"]


def _finalize_splits(scene=None):
    regs = _STATE["splits"]
    if not regs or not _STATE["rains"]:
        return dict(n=len(regs), rains=len(_STATE["rains"]))
    fxc = _clock()
    verts, faces, nrm, st0, st1, swd, top = [], [], [], [], [], [], []
    for r in regs:
        n = Vector(r["normal"])
        t, a, b = _split_frame(r)
        o = Vector(r["origin"])
        z0, z1 = -1.0, r["height"]
        base = len(verts)
        for s_, z in ((a, z0), (b, z0), (b, z1), (a, z1)):
            p = o + t * s_
            verts.append((p.x, p.y, z))
        faces.append((base, base + 1, base + 2, base + 3))
        nrm.append(tuple(n))
        st0.append(fxc.fx_time_at(r["f0"]))
        st1.append(fxc.fx_time_at(r["f1"]))
        swd.append(r["width"])
        top.append(r["height"])
    col = _collection("rain")
    ob = bpy.data.objects.get("VFX_rain_splits")
    if ob is not None:
        bpy.data.objects.remove(ob)
    ob = U.mesh_from_data("VFX_rain_splits", verts, faces=faces, collection=col)
    U.add_attribute(ob.data, "nrm", np.array(nrm, np.float32), 'FLOAT_VECTOR', 'FACE')
    U.add_attribute(ob.data, "st0", np.array(st0, np.float32), 'FLOAT', 'FACE')
    U.add_attribute(ob.data, "st1", np.array(st1, np.float32), 'FLOAT', 'FACE')
    U.add_attribute(ob.data, "swd", np.array(swd, np.float32), 'FLOAT', 'FACE')
    U.add_attribute(ob.data, "top", np.array(top, np.float32), 'FLOAT', 'FACE')
    ob.hide_render = True
    ob.visible_camera = False
    ob.visible_shadow = False
    for rn in _STATE["rains"]:
        U.gn_set(rn, "Splits", ob)
        U.gn_set(rn, "Has Splits", True)
    return dict(n=len(regs), rains=len(_STATE["rains"]))


# ================================================================================================ spray / shock
def _water_material(name="VFX_water_drop", glossy=0.65, emission=0.06, rim=False):
    """Lit water droplets: Translucent + a strong Glossy (sparkle in back/rim light) + a faint emission floor
    (reads at night), alpha from age (age01, INSTANCER), young drops a little brighter. DITHERED (rule 5).
    rim=True: extra per-instance brightness from the instance attribute 'rim' (0..1)."""
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    mat, nb, out = _mat(name)
    age = U.attribute_node(mat, "age01", 'INSTANCER').outputs["Fac"]
    c = COLORS["water"]
    young = nb.map_range(age, 0.0, 0.35, 1.6, 1.0)
    em_s = nb.math('MULTIPLY', young, float(emission))
    if rim:
        em_s = nb.math('MULTIPLY', em_s, nb.math('ADD', 1.0, nb.math(
            'MULTIPLY', U.attribute_node(mat, "rim", 'INSTANCER').outputs["Fac"], 2.0)))
    lit = nb.n('ShaderNodeAddShader', nb.n('ShaderNodeMixShader', float(glossy),
                                           nb.n('ShaderNodeBsdfTranslucent', Color=(*c, 1.0)),
                                           nb.n('ShaderNodeBsdfGlossy', Color=(1, 1, 1, 1), Roughness=0.12)),
               nb.n('ShaderNodeEmission', Color=(*c, 1.0), Strength=em_s))
    alpha = nb.map_range(age, 0.6, 1.0, 0.9, 0.0)
    nb.link(nb.n('ShaderNodeMixShader', alpha, nb.n('ShaderNodeBsdfTransparent'), lit), U.socket_in(out.node, "Surface"))
    mat.surface_render_method = 'DITHERED'
    mat.use_backface_culling = False
    mat.diffuse_color = (*c, 1.0)
    return mat


def spray_ring(frame, pos, radius=4.0, count=2400, seed=0, life=30, grow_frames=10, mist=True, name=None):
    """Water shockwave (S23, the grounded jodan): an expanding CROWN of spray. A front races from pos out to
    `radius` over grow_frames; drops are born where the front passes (denser toward the rim), thrown UP at
    6-9 m/s and a little outward (air drag 1-1.5/s: median apex ~1.9 m, i.e. clearly above the waist-high arena
    grass of 0.95-1.15 m), plus a central burst (25 %) thrown hard outward. Drops are larger (1.2-2.8 cm) velocity-
    stretched streaks, lit Translucent + strong Glossy (they sparkle in the backlight). mist: a ring of spray mist
    (volume, 3.4 m tall box) riding the front and rising above the grass. Returns dict(drops, mist)."""
    rng = _rng("spray", frame, seed, count)
    pos = np.asarray(pos, float)
    n_c = int(round(count * 0.75))
    n_b = count - n_c
    ang = rng.uniform(0, 2 * math.pi, count)
    # crown: birth radius ~ sqrt (area-uniform) biased to the rim; the front reaches r at frame + grow*(r/R)
    rb = radius * np.sqrt(rng.uniform(0.08, 1.0, n_c)) ** 0.8
    rb = np.concatenate([rb, np.full(n_b, 0.3)])
    birth = np.concatenate([frame + grow_frames * rb[:n_c] / radius + rng.uniform(0.0, 1.5, n_c),
                            frame + rng.uniform(0.0, 1.5, n_b)])
    vz = np.concatenate([rng.uniform(6.0, 9.0, n_c), rng.uniform(5.0, 8.5, n_b)])
    vh = np.concatenate([rng.uniform(0.8, 3.2, n_c), rng.uniform(3.0, 7.0, n_b)])
    tang = rng.normal(0.0, 0.5, count)
    k = rng.uniform(1.0, 1.5, count)                               # linear air drag (1/s)
    c, s_ = np.cos(ang), np.sin(ang)
    vel = np.column_stack([c * vh - s_ * tang, s_ * vh + c * tang, vz])
    p0 = pos[None, :] + np.column_stack([c * rb, s_ * rb, np.full(count, 0.05)])
    nm = name or f"VFX_spray_{int(frame)}_{seed}"
    drops = _pool(nm, "spray", p0, vel, birth, life * rng.uniform(0.8, 1.1, count), gravity=-9.81, drag=k,
                  instance=_needle_source(), material=_water_material("VFX_spray_drop", glossy=0.7, emission=0.24),
                  size=rng.uniform(0.014, 0.03, count), shrink=0.35, stretch=0.03, len0=2.5, align='velocity')
    mv = None
    if mist:
        H = 3.4
        mv = _volume_box(nm + "_mist", "spray", (pos[0], pos[1], pos[2] + 0.5 * H - 0.2),
                         (2.7 * radius, 2.7 * radius, H), frame, frame + life * 2.4, shape="ring",
                         color='steam', density=0.22, anisotropy=0.45, noise_scale=1.5, rise=0.45,
                         ring_radius=0.74, ring_width=0.075, ring_h=(0.3, 0.5), expand=1.0, evolve=0.5,
                         fade_in=0.02, fade_out=0.7, seed=seed, grow_frames=grow_frames * 1.4,
                         contrast=(0.5, 0.72), noise2=2.4)
    return dict(drops=drops, mist=mv)


def shockwave(frame, pos, radius=4.0, seed=0, color='dust', debris=True, name=None):
    """Dry shockwave (the S17 spear slam, heavy landings): a fast ring of dust racing out to `radius` (ring
    volume, most of the growth in ~8 frames) + grass/dirt debris kicked outward. No glow, no distortion shell.
    Returns dict(volume, debris)."""
    pos = tuple(float(x) for x in pos)
    nm = name or f"VFX_shock_{int(frame)}_{seed}"
    # a ring of dust racing out and rising ABOVE the waist-high grass (box 2.8 m tall)
    vol = _volume_box(nm, "shock", (pos[0], pos[1], pos[2] + 1.2), (2.5 * radius, 2.5 * radius, 2.8), frame,
                      frame + 44, shape="ring", color=color, density=1.2, anisotropy=0.35, noise_scale=1.5,
                      rise=0.4, ring_radius=0.78, ring_width=0.07, ring_h=(0.35, 0.45), expand=1.0, evolve=0.5,
                      fade_in=0.02, fade_out=0.6, seed=seed, grow_frames=10, contrast=(0.48, 0.7), noise2=2.2)
    deb = None
    if debris:
        rng = _rng("shock_debris", frame, seed)
        n = int(40 + 10 * radius)
        ang = rng.uniform(0, 2 * math.pi, n)
        hs = rng.uniform(3.0, 7.0, n) * math.sqrt(radius / 4.0)
        vel = np.column_stack([np.cos(ang) * hs, np.sin(ang) * hs, rng.uniform(0.8, 3.0, n)])
        p0 = np.column_stack([pos[0] + np.cos(ang) * 0.4, pos[1] + np.sin(ang) * 0.4, np.full(n, pos[2] + 0.1)])
        pick = rng.choice([_PICK_BLADE, _PICK_BENT, _PICK_TUFT, _PICK_CLOD], n).astype(np.int32)
        deb = _pool(nm + "_debris", "shock", p0, vel, float(frame) + rng.uniform(0, 3, n), rng.uniform(16, 30, n),
                    gravity=-6.0, drag=rng.uniform(1.5, 3.0, n), instances=_shard_sources(), pick=pick,
                    size=rng.uniform(0.05, 0.14, n), align='random', spin=rng.uniform(-12, 12, (n, 3)),
                    turb=0.2)
    return dict(volume=vol, debris=deb)


def _mist_material(name, color, emission=0.55, opacity=0.5):
    """Soft translucent wisp material for tiny specks: Emission + Translucent in the given colour, mixed with
    Transparent by alpha = opacity * fade-in * (1 - age)^1.3 (age01, INSTANCER) - DITHERED, so many overlapping
    specks read as a haze, never as solid droplets."""
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    mat, nb, out = _mat(name)
    age = U.attribute_node(mat, "age01", 'INSTANCER').outputs["Fac"]
    c = _color(color)
    lit = nb.n('ShaderNodeAddShader', nb.n('ShaderNodeBsdfTranslucent', Color=(*c, 1.0)),
               nb.n('ShaderNodeEmission', Color=(*c, 1.0), Strength=float(emission)))
    alpha = nb.math('MULTIPLY', nb.math('MULTIPLY', nb.map_range(age, 0.0, 0.12, 0.0, 1.0),
                                        nb.math('POWER', nb.math('SUBTRACT', 1.0, age), 1.3)), float(opacity))
    nb.link(nb.n('ShaderNodeMixShader', alpha, nb.n('ShaderNodeBsdfTransparent'), lit), U.socket_in(out.node, "Surface"))
    mat.surface_render_method = 'DITHERED'
    mat.use_backface_culling = False
    mat.diffuse_color = (*c, 1.0)
    return mat


def red_mist(frame, pos, direction, count=2200, seed=0, life=(5.0, 8.0), spread=0.05, speed=3.6, name=None):
    """S26: the cut vermilion beard cord flutters away 'with a thin line of red mist' - a thin, soft, translucent
    wisp in the cord's colour (config.PALETTE['beard_cord']), never droplets or spatter (deny-list: no blood).
    ~2200 tiny (1.5-3 mm) alpha-soft specks, elongated along the drift (velocity-aligned needles), DITHERED,
    slightly emissive + translucent (reads backlit in the storm night), emitted over ~0.12 fx s from the cut and
    drifting along `direction` at ~`speed` m/s with little drag and a faint curl: at S26's 1/8 slow motion the
    line travels ~0.5-1 m by the end of the shot (3414 -> 3456). life = (min, max) in frames at normal speed.
    Returns the pool object."""
    rng = _rng("red_mist", frame, seed, count)
    d = np.asarray(direction, float)
    d = d / (np.linalg.norm(d) + 1e-9)
    along = rng.uniform(0.0, 0.12, count)
    p0 = np.asarray(pos, float)[None, :] + d[None, :] * along[:, None] + rng.normal(0, 0.012, (count, 3))
    vel = (d[None, :] * (speed * rng.uniform(0.55, 1.3, count))[:, None]
           + rng.normal(0, spread * speed, (count, 3)) + np.array([0.0, 0.0, 0.12 * speed]))
    mat = _mist_material("VFX_red_mist", "mist_red", emission=0.35, opacity=0.28)
    return _pool(name or f"VFX_red_mist_{int(frame)}_{seed}", "mist", p0, vel,
                 float(frame) + rng.uniform(0, 3.0, count), rng.uniform(life[0], life[1], count), gravity=-0.3,
                 drag=rng.uniform(0.4, 0.8, count), instance=_needle_source(), material=mat,
                 size=rng.uniform(0.0015, 0.003, count), shrink=0.2, stretch=0.02, len0=9.0, align='velocity',
                 turb=0.04, turb_scale=3.0, turb_speed=1.2)


# ================================================================================================ wind / grass
def wind_blade(f0, f1, start, end, width=1.0, count=160, seed=0, name=None):
    """A gust line: silver-grass fluff and cut blade bits carried from `start` to `end` over [f0, f1] (births
    spread over the window, strong turbulence, `width` m wide). Physical debris only - never a glowing blade of
    wind (deny-list). The grass itself bends via the environment's wind (environment.set_wind). Returns the pool."""
    rng = _rng("wind_blade", f0, seed, count)
    a, b = np.asarray(start, float), np.asarray(end, float)
    d = b - a
    dur_s = max(1.0, f1 - f0) / FPS
    u = rng.random(count)
    side = np.cross(d / (np.linalg.norm(d) + 1e-9), [0, 0, 1])
    p0 = a[None, :] + d[None, :] * (u * 0.25)[:, None] + side[None, :] * rng.normal(0, width * 0.4, count)[:, None]
    p0[:, 2] = a[2] + rng.uniform(0.6, 1.6, count)
    vel = d[None, :] / dur_s * rng.uniform(0.8, 1.3, count)[:, None] + np.array([0, 0, 0.4])
    pick = np.where(rng.random(count) < 0.65, _PICK_TUFT, _PICK_BLADE).astype(np.int32)
    return _pool(name or f"VFX_wind_blade_{int(f0)}_{seed}", "wind", p0, vel,
                 f0 + rng.uniform(0, 0.6, count) * (f1 - f0), (f1 - f0) * rng.uniform(0.5, 0.9, count),
                 gravity=-0.3, drag=rng.uniform(0.2, 0.6, count), instances=_shard_sources(), pick=pick,
                 size=np.where(pick == _PICK_TUFT, rng.uniform(0.04, 0.07, count), rng.uniform(0.07, 0.15, count)),
                 align='random', spin=rng.uniform(-6, 6, (count, 3)), turb=0.6, turb_scale=0.7, turb_speed=1.4)


def grass_shear(f0, f1, origin, radius_end, arc_deg, facing_deg, speed=None, cut_height=0.66, fluff=2400):
    """S11 grass-shearing draw-cut. OWNED BY THE ENVIRONMENT (Pipeline rule 8: the grass GN, per-blade cut
    times, clipped tips and the plume-fluff pool) - this forwards to
    environment.grass_effect('shear', {...}, f0, f1) so callers of the earlier vfx API still work.
    speed defaults to radius_end / (f1 - f0) (m per fx second). Returns what the environment returns."""
    env = _env()
    if env is None or not hasattr(env, "grass_effect"):
        raise RuntimeError("vfx.grass_shear: environment.grass_effect is not available")
    sp = speed if speed is not None else float(radius_end) / max(1e-3, (f1 - f0) / FPS)
    params = dict(origin=tuple(origin)[:2], radius=float(radius_end), speed=float(sp), arc_deg=float(arc_deg),
                  facing_deg=float(facing_deg), cut_height=float(cut_height), fluff=int(fluff))
    return env.grass_effect('shear', params, f0, f1)
