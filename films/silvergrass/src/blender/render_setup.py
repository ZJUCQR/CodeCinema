"""
render_setup.py - render presets, colour management and the compositor chain of Duel in the Silver Grass (Blender 5.2.2).
Owner: env lane. Contract: Pipeline rule 14 (+ rules 2, 5, 6, 7), config.SHOT_RENDER.

Public API
    configure(quality='final', scene=None, percent=None, grass_density=None) -> dict   # 'layout' | 'preview' | 'final'
    apply_shot_overrides(scene, frame) -> dict                         # per-frame, called by the render loop
    mute_viewport_gn(scene=None, mute=True) -> int                     # (apply_shot_overrides does it headless + MB)
    ensure_compositor(scene=None) -> dict                              # idempotent post chain (lanes may key it)
    key_white_flash(frame, amount, duration=1, scene=None)            # white pulse (full only in config.FULL_WHITE)
    key_dispersion(frame, amount, release=6, scene=None)               # lens-dispersion pulse (impact frames)
    quality_of(scene=None) -> str

Presets (rule 14)
    layout  : Workbench, object colours, 1/3 resolution, no compositor (~0.2 s/f).
    preview : EEVEE 1/3 resolution, 8 spp, no motion blur, grass x0.25, compositor on.
    final   : EEVEE 1920x816, 32 spp, filter 1.5, AgX (LOOK), fast GI on, raytracing off, motion blur shutter 0.5
              START steps 1 (16 spp final, director 09-30 for render time), motion_blur_max 40, shadow pool 1024 MB, volumetrics tile 8 / 64 samples,
              compositor chain (bloom, lens dispersion, vignette, grain, white flash), PNG RGB 8-bit c15.
Per-shot overrides: config.SHOT_RENDER[shot_id] keys samples, mb_steps, raytrace, vol_end, exposure, bloom
(baseline restored on frames of other shots). Colour: AgX with LOOK (chosen in look-dev, see out/dev/env/).
"""
import os
import sys

import bpy

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(_HERE, "..", "common"), _HERE):
    _p = os.path.abspath(_p)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config            # noqa: E402
import bl_util as U      # noqa: E402

COMP_NAME = "SG_post"
VIEW_TRANSFORM = "AgX"
LOOK = "AgX - Punchy"
EXPOSURE = 0.0
FLASH_LEVEL = 16.0              # linear white needed for display white after AgX (api notes §7)
BLOOM = dict(strength=0.55, threshold=0.9, size=0.6)
VIGNETTE = 0.32
GRAIN = 0.035
DISPERSION = 0.0                # resting value; key_dispersion() raises it on impact frames
VOL_END = 220.0                 # default volumetric_end (m); SHOT_RENDER 'vol_end' overrides
GRASS_DENSITY = config.GRASS_DENSITY    # settings render.grass_density_*
WORKBENCH_HIDDEN = ("ENV_fog", "ENV_shadow_edge", "ENV_cloud_deck")

_PREVIEW_PCT = round(config.PREVIEW_SCALE * 100, 2)        # 33.33 -> 33 % after int(round())
_SPP = config.RENDER_SAMPLES
PRESETS = {
    "layout": dict(engine='BLENDER_WORKBENCH', percent=_PREVIEW_PCT, samples=1, mb=False),
    "preview": dict(engine='BLENDER_EEVEE', percent=_PREVIEW_PCT, samples=_SPP["preview"], mb=False),
    "final": dict(engine='BLENDER_EEVEE', percent=100, samples=_SPP["final"], mb=config.MOTION_BLUR),
}
_BASE_KEYS = ("samples", "mb_steps", "raytrace", "vol_end", "exposure", "bloom")


def quality_of(scene=None):
    sc = scene or bpy.context.scene
    return sc.get("sg_quality", "final")


def _eevee_common(sc, preset):
    E = sc.eevee
    E.taa_render_samples = preset["samples"]
    E.use_shadows = True
    E.shadow_ray_count = 1
    E.shadow_step_count = 6
    E.shadow_resolution_scale = 1.0
    E.shadow_pool_size = str(config.SHADOW_POOL_MB)
    E.use_raytracing = False
    E.use_fast_gi = True
    E.fast_gi_method = 'GLOBAL_ILLUMINATION'
    E.volumetric_tile_size = str(config.VOLUMETRIC["tile"])
    E.volumetric_samples = config.VOLUMETRIC["samples"]
    E.volumetric_start = 0.1
    E.volumetric_end = VOL_END
    E.volumetric_sample_distribution = 0.8
    E.use_volumetric_shadows = False
    E.clamp_surface_indirect = 10.0
    sc.render.use_motion_blur = bool(preset["mb"])
    sc.render.motion_blur_shutter = config.MB_SHUTTER
    sc.render.motion_blur_position = 'START'      # rule 2 (global, even when MB is off)
    E.motion_blur_steps = config.MB_STEPS
    E.motion_blur_max = config.MB_MAX
    E.motion_blur_depth_scale = 100.0


def _workbench(sc):
    sh = sc.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'OBJECT'
    sh.show_shadows = False
    sh.show_cavity = False
    sh.background_type = 'WORLD'
    sc.render.use_motion_blur = False
    sc.render.motion_blur_position = 'START'


def _colour(sc):
    vs = sc.view_settings
    vs.view_transform = VIEW_TRANSFORM
    try:
        vs.look = LOOK
    except TypeError:                       # enum is dynamic; fall back silently to no look
        vs.look = 'None'
    vs.exposure = EXPOSURE
    vs.gamma = 1.0
    sc.display_settings.display_device = 'sRGB'


def ensure_compositor(scene=None):
    """Create (once) the post chain RenderLayers -> Bloom -> Lens dispersion -> vignette -> grain -> white flash ->
    output, named COMP_NAME. Idempotent: an existing chain (possibly already keyed by lanes) is kept.
    Returns dict(tree, glare, lens, flash)."""
    sc = scene or bpy.context.scene
    ng = sc.compositing_node_group
    if ng is None or ng.name != COMP_NAME:
        ng = bpy.data.node_groups.get(COMP_NAME)
        if ng is None:
            nodes = U.comp_post_chain(sc, bloom=BLOOM["strength"], bloom_threshold=BLOOM["threshold"],
                                      bloom_size=BLOOM["size"], dispersion=max(DISPERSION, 1e-4),
                                      vignette=VIGNETTE, grain=GRAIN, flash_level=FLASH_LEVEL)
            ng = nodes["tree"]
            ng.name = COMP_NAME
            if nodes["glare"] is not None:
                nodes["glare"].name = "Bloom"
            if nodes["lens"] is not None:
                nodes["lens"].name = "Lens"
        sc.compositing_node_group = ng
    sc.render.use_compositing = True
    for n in ng.nodes:          # the render-layers node must point at THIS scene
        if n.bl_idname == 'CompositorNodeRLayers':
            n.scene = sc
    return dict(tree=ng, glare=ng.nodes.get("Bloom"), lens=ng.nodes.get("Lens"), flash=ng.nodes.get("Flash"))


def key_white_flash(frame, amount, duration=1, scene=None):
    """Key a compositor white-flash PULSE: factor `amount` (0..1 mix towards linear FLASH_LEVEL white) on frames
    [frame, frame + duration - 1], 0 on frame - 1 and frame + duration (CONSTANT - crisp). Full white is only allowed
    in config.FULL_WHITE (DIRECTION §5); elsewhere amount is clamped to 0.4 (S13 exposure lift <= 40 %).
    Example (S25): key_white_flash(3265, 1.0, duration=4)."""
    sc = scene or bpy.context.scene
    ensure_compositor(sc)
    a0, a1 = config.FULL_WHITE
    amt = float(amount)
    last = int(frame) + int(duration) - 1
    if not (a0 <= frame and last <= a1) and amt > 0.4:
        print(f"[render_setup] white flash {amt:.2f} at {frame}-{last} outside FULL_WHITE {config.FULL_WHITE} -> 0.4")
        amt = 0.4
    U.comp_key_flash(int(frame) - 1, 0.0, sc, interp='CONSTANT', node_name="Flash")
    for f in range(int(frame), last + 1):
        U.comp_key_flash(f, amt, sc, interp='CONSTANT', node_name="Flash")
    return U.comp_key_flash(last + 1, 0.0, sc, interp='CONSTANT', node_name="Flash")


def key_dispersion(frame, amount, release=6, scene=None):
    """Key a lens-dispersion (chromatic fringing) PULSE for an impact: 0 at frame - 1, `amount` (e.g. 0.04) at
    frame, back to 0 at frame + release (LINEAR)."""
    sc = scene or bpy.context.scene
    comp = ensure_compositor(sc)
    lens = comp["lens"]
    if lens is None:
        return None
    sock = U.socket_in(lens, "Dispersion")
    U.key(sock, "default_value", int(frame) - 1, 0.0, interp='LINEAR')
    U.key(sock, "default_value", int(frame), float(amount), interp='LINEAR')
    return U.key(sock, "default_value", int(frame) + int(release), 0.0, interp='LINEAR')


def _volume_only(ob):
    """True for a mesh whose every material feeds only the Volume of its output (vfx dust / smoke / steam / mist
    boxes, the env fog box): Workbench draws such boxes as opaque solids."""
    if ob.type != 'MESH' or not ob.material_slots:
        return False
    for slot in ob.material_slots:
        mat = slot.material
        nt = mat.node_tree if mat is not None else None
        if nt is None:
            return False
        outs = [n for n in nt.nodes if n.bl_idname == 'ShaderNodeOutputMaterial']
        if not outs or any(o.inputs["Surface"].is_linked or not o.inputs["Volume"].is_linked for o in outs):
            return False
    return True


def _workbench_volumes(sc, hide):
    """Layout (Workbench) previews: hide volume-only boxes (else they cover the frame as grey solids); switching
    back to EEVEE shows again exactly the ones hidden here (tag '_wb_hidden'). Objects whose hide_render is
    animated / driven (lane or vfx visibility windows) are left alone."""
    for ob in sc.objects:
        ad = ob.animation_data
        animated = ad is not None and (any(fc.data_path == "hide_render" for fc in ad.drivers)
                                       or any(fc.data_path == "hide_render" for fc in U.fcurves_of(ob))
                                       or len(ad.nla_tracks) > 0)
        if hide:
            if not ob.hide_render and not animated and _volume_only(ob):
                ob.hide_render = True
                ob["_wb_hidden"] = 1
        elif ob.get("_wb_hidden"):
            ob.hide_render = False
            del ob["_wb_hidden"]


def configure(quality='final', scene=None, percent=None, grass_density=None):
    """Apply a render preset (rule 14) to the scene. percent overrides the resolution percentage.
    Also sets the environment grass density (GRASS_DENSITY: x1 final, x0.25 preview, 0.12 layout) when the env grass
    exists - this REPLACES any density given to environment.build(density=...); pass grass_density= to keep / force
    another value (e.g. a final-quality test at reduced density). Also colour management (AgX + LOOK), the output
    (PNG RGB 8-bit c15 -> out/frames/#####) and the compositor. Returns a dict of the applied settings."""
    if quality not in PRESETS:
        raise ValueError(f"quality must be one of {tuple(PRESETS)}")
    sc = scene or bpy.context.scene
    p = PRESETS[quality]
    mute_viewport_gn(sc, mute=False)
    sc.render.engine = p["engine"]
    sc.render.fps = config.FPS
    sc.render.fps_base = 1.0
    sc.render.resolution_x, sc.render.resolution_y = config.RES_X, config.RES_Y
    sc.render.resolution_percentage = int(round(percent if percent is not None else p["percent"]))
    sc.render.pixel_aspect_x = sc.render.pixel_aspect_y = 1.0
    sc.render.filter_size = config.RENDER_FILTER
    sc.render.film_transparent = False
    sc.render.use_border = False
    sc.frame_start, sc.frame_end = config.FRAME_START, config.FRAME_END
    _colour(sc)
    if p["engine"] == 'BLENDER_WORKBENCH':
        _workbench(sc)
        sc.render.use_compositing = False
    else:
        _eevee_common(sc, p)
        ensure_compositor(sc)
    # Workbench ignores volumes / ray visibility: the fog box and the invisible shadow decks would render as solids
    for name in WORKBENCH_HIDDEN:
        ob = bpy.data.objects.get(name)
        if ob is not None:
            ob.hide_render = (p["engine"] == 'BLENDER_WORKBENCH')
    _workbench_volumes(sc, p["engine"] == 'BLENDER_WORKBENCH')
    U.configure_png(sc, rgb=True)       # depth / compression: config.FRAME_PNG
    sc.render.filepath = config.FRAME_PATTERN
    sc.render.use_file_extension = True
    sc.render.use_overwrite = True
    sc.render.use_placeholder = False
    sc["sg_quality"] = quality
    base = dict(samples=p["samples"], mb_steps=config.MB_STEPS, raytrace=False, vol_end=VOL_END, exposure=EXPOSURE,
                bloom=BLOOM["strength"])
    sc["sg_render_base"] = base
    dens = GRASS_DENSITY[quality] if grass_density is None else float(grass_density)
    try:
        import environment
        if bpy.data.objects.get(environment.N_GRASS) is not None:
            environment.set_grass_density(dens)
    except Exception as exc:        # env optional (e.g. character-only scenes)
        print(f"[render_setup] grass density not set: {exc}")
    return dict(quality=quality, engine=p["engine"], percent=sc.render.resolution_percentage,
                samples=p["samples"], motion_blur=bool(p["mb"]), look=sc.view_settings.look, grass_density=dens)


VP_MUTE_TAG = "_rs_vp_muted"   # object prop: names of the GN modifiers mute_viewport_gn() hid from the viewport


def mute_viewport_gn(scene=None, mute=True):
    """Hide (mute=True) / restore (False) every Geometry Nodes modifier of the scene's objects in the VIEWPORT
    depsgraph. Renders read show_render, so nothing rendered changes. Why: EEVEE motion blur re-evaluates the
    view-layer depsgraph at each motion step as well as the render one - with the grass GN (~0.5 s per evaluation)
    that is ~1.5 s per final frame (perf TD, out/dev/perf/). apply_shot_overrides() calls it in background EEVEE
    renders with motion blur; configure() and mute=False restore exactly the modifiers hidden here (tagged).
    Returns the number of modifiers changed."""
    sc = scene or bpy.context.scene
    n = 0
    for ob in sc.objects:
        if mute:
            names = [m.name for m in ob.modifiers if m.type == 'NODES' and m.show_viewport and m.show_render]
            if names:
                for nm in names:
                    ob.modifiers[nm].show_viewport = False
                ob[VP_MUTE_TAG] = list(ob.get(VP_MUTE_TAG, [])) + names
                n += len(names)
        elif VP_MUTE_TAG in ob:
            for nm in ob[VP_MUTE_TAG]:
                m = ob.modifiers.get(nm)
                if m is not None:
                    m.show_viewport = True
                    n += 1
            del ob[VP_MUTE_TAG]
    return n


def _shot_id_at(frame):
    s = config.shot_at(int(frame))
    return s["id"] if s else None


def apply_shot_overrides(scene, frame):
    """Apply config.SHOT_RENDER overrides for the shot containing `frame` (keys: samples, mb_steps, raytrace,
    vol_end, exposure, bloom), restoring the preset baseline for every key the shot does not override.
    Motion-blur / sample overrides only apply in 'final' quality. Returns the dict of values applied."""
    sc = scene or bpy.context.scene
    if sc.render.engine != 'BLENDER_EEVEE':
        return {}
    base = dict(sc.get("sg_render_base", {}))
    if not base:
        base = dict(samples=sc.eevee.taa_render_samples, mb_steps=config.MB_STEPS, raytrace=False, vol_end=VOL_END,
                    exposure=EXPOSURE, bloom=BLOOM["strength"])
    q = quality_of(sc)
    if q in PRESETS:                # the CURRENT preset wins over the build-time copy (director: final 16 spp)
        base["samples"] = PRESETS[q]["samples"]
    ov = dict(config.SHOT_RENDER.get(_shot_id_at(frame), {}))
    vals = {k: ov.get(k, base.get(k)) for k in _BASE_KEYS}
    E = sc.eevee
    if q == 'final':
        E.taa_render_samples = int(vals["samples"])
        steps = int(vals["mb_steps"])
        try:                        # spark-birth frames want >= 2 steps (vfx registry scene["vfx_mb_frames"])
            import vfx
            steps = vfx.mb_steps_at(frame, sc, steps)
        except Exception as exc:    # noqa: BLE001 - vfx optional (character-only scenes)
            print(f"[render_setup] vfx.mb_steps_at unavailable: {exc}")
        vals["mb_steps"] = steps
        E.motion_blur_steps = steps
    E.use_raytracing = bool(vals["raytrace"])
    E.volumetric_end = float(vals["vol_end"])
    sc.view_settings.exposure = float(vals["exposure"])
    ng = sc.compositing_node_group
    if ng is not None and ng.nodes.get("Bloom") is not None:
        U.socket_in(ng.nodes["Bloom"], "Strength").default_value = float(vals["bloom"])
    if bpy.app.background and sc.render.use_motion_blur:
        mute_viewport_gn(sc)            # headless final renders only (the UI viewport is never touched)
    return vals
