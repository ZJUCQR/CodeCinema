"""
fxclock.py - the film's effects clock (runs inside Blender).

scene["fx_time"] (seconds) advances by speed/FPS per frame, where speed comes from config.TIME_WARP
(slow-motion windows; 1.0 elsewhere). Every time-driven procedural effect - grass wind, GN particle pools, rain,
fire, embers, trail reveal shaders, secondary springs - must read fx_time instead of Scene Time, so that the
slow-motion shots slow the effects as well as the keyed animation.

Mechanism (verified headless, no Python auto-exec needed): the scene custom property is keyed LINEAR at every
warp breakpoint; consumers get an AVERAGE driver with one SINGLE_PROP variable reading it.

    import fxclock
    fxclock.ensure_clock()                                   # build_scene calls this once, AFTER NLA assembly
    fxclock.drive_gn_input(obj, "Time")                      # GN modifier input named "Time"
    fxclock.drive_node_value(material, "FX Time")           # a Value node named "FX Time" in a node tree
    fxclock.fx_time_at(1234.5)                               # pure-python evaluation (springs, baking)

The clock is derived only from config, so it is identical in every partial/lane build.
NLA note: build_scene must not stash the scene's ["fx_time"] channel into lane strips (ensure_clock runs last).
"""

import bpy
import config

PROP = "fx_time"
PRE_ROLL = 200   # frames of clock before FRAME_START (springs/particles may pre-roll)


def clock_breakpoints():
    """[(frame, fx_time_seconds)] - piecewise-linear integral of the speed curve."""
    fps = float(config.FPS)
    f = float(config.FRAME_START - PRE_ROLL)
    t = (f - config.FRAME_START) / fps
    pts = [(f, t)]
    for a, b, speed in sorted(getattr(config, "TIME_WARP", [])):
        t += (a - f) / fps
        f = float(a)
        pts.append((f, t))
        t += (b - a) * float(speed) / fps
        f = float(b)
        pts.append((f, t))
    end = float(config.FRAME_END + PRE_ROLL)
    t += (end - f) / fps
    pts.append((end, t))
    return pts


def fx_time_at(frame):
    """fx_time (seconds) at a (possibly fractional) frame - identical to the keyed curve."""
    pts = clock_breakpoints()
    frame = float(frame)
    if frame <= pts[0][0]:
        (f0, t0), (f1, t1) = pts[0], pts[1]
    elif frame >= pts[-1][0]:
        (f0, t0), (f1, t1) = pts[-2], pts[-1]
    else:
        for (f0, t0), (f1, t1) in zip(pts, pts[1:]):
            if f0 <= frame <= f1:
                break
    if f1 == f0:
        return t0
    return t0 + (t1 - t0) * (frame - f0) / (f1 - f0)


def speed_at(frame):
    for a, b, speed in getattr(config, "TIME_WARP", []):
        if a <= frame < b:
            return float(speed)
    return 1.0


def _fcurve(scene):
    ad = scene.animation_data
    if not ad or not ad.action:
        return None
    from bpy_extras import anim_utils
    cb = anim_utils.animdata_get_channelbag_for_assigned_slot(ad)
    if cb is None:
        return None
    return cb.fcurves.find(f'["{PROP}"]')


def ensure_clock(scene=None):
    """(Re)build the fx_time curve on the scene. Idempotent. Returns the F-curve."""
    scene = scene or bpy.context.scene
    fc = _fcurve(scene)
    if fc is not None:
        fc.keyframe_points.clear()
    scene[PROP] = 0.0
    for f, t in clock_breakpoints():
        scene[PROP] = float(t)
        scene.keyframe_insert(data_path=f'["{PROP}"]', frame=f)
    fc = _fcurve(scene)
    for k in fc.keyframe_points:
        k.interpolation = 'LINEAR'
    fc.extrapolation = 'LINEAR'
    fc.update()
    return fc


def add_time_driver(id_owner, data_path, index=-1, scene=None):
    """Drive id_owner.<data_path> with scene["fx_time"] (AVERAGE of one SINGLE_PROP variable)."""
    scene = scene or bpy.context.scene
    fc = id_owner.driver_add(data_path) if index < 0 else id_owner.driver_add(data_path, index)
    drv = fc.driver
    drv.type = 'AVERAGE'
    while drv.variables:
        drv.variables.remove(drv.variables[0])
    var = drv.variables.new()
    var.name = "t"
    var.type = 'SINGLE_PROP'
    tgt = var.targets[0]
    tgt.id_type = 'SCENE'
    tgt.id = scene
    tgt.data_path = f'["{PROP}"]'
    for m in list(fc.modifiers):
        fc.modifiers.remove(m)
    return fc


def drive_gn_input(obj, input_name="Time", mod_name="GN", scene=None):
    """Drive a Geometry-Nodes modifier input (by interface name) with fx_time."""
    import bl_util as U
    return add_time_driver(obj, U.gn_path(obj, input_name, mod_name), scene=scene)


def drive_node_value(owner, node_name="FX Time", scene=None):
    """Drive the output of a Value node inside owner's node tree (material, world, light, node group)."""
    nt = owner if isinstance(owner, bpy.types.NodeTree) else owner.node_tree
    return add_time_driver(nt, f'nodes["{node_name}"].outputs[0].default_value', scene=scene)
