"""The cartoon look: cel-shaded materials, ink outlines, sky, lights and finishing.

EEVEE turns real lighting into flat bands with Shader to RGB, so lamps, shadows
and colored light all read as cel animation. Cycles has no Shader to RGB; there
the same materials fall back to soft diffuse shading, so a film still renders on
machines without a GPU, with a softer look.
"""
import math

import bpy

GROUP = "CodeCinema Toon"


def linear(value):
    """'#rrggbb' (sRGB, as artists pick colors) -> scene-linear RGB."""
    if not isinstance(value, str):
        return tuple(value[:3])
    value = value.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(value[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return tuple(out)


def rgba(value, alpha=1.0):
    return (*linear(value), alpha)


def node(tree, kind, location=(0, 0), **props):
    n = tree.nodes.new(kind)
    n.location = location
    for key, value in props.items():
        setattr(n, key, value)
    return n


def socket(sockets, name, kind=None):
    """A socket by name (and type), since Mix nodes repeat names across data types."""
    for s in sockets:
        if s.name == name and (kind is None or s.type == kind) and s.enabled:
            return s
    for s in sockets:
        if s.name == name and (kind is None or s.type == kind):
            return s
    raise KeyError(f"No socket {name} ({kind})")


def link(tree, a, b):
    tree.links.new(a, b)


def mix_color(tree, blend="MIX", location=(0, 0)):
    n = node(tree, "ShaderNodeMix", location, data_type="RGBA", blend_type=blend)
    n.clamp_factor = True
    return n, socket(n.inputs, "Factor", "VALUE"), socket(n.inputs, "A", "RGBA"), socket(n.inputs, "B", "RGBA"), \
        socket(n.outputs, "Result", "RGBA")


def math_node(tree, op, a=None, b=None, location=(0, 0), clamp=False):
    n = node(tree, "ShaderNodeMath", location, operation=op, use_clamp=clamp)
    for i, value in enumerate((a, b)):
        if value is None:
            continue
        if isinstance(value, (int, float)):
            n.inputs[i].default_value = value
        else:
            link(tree, value, n.inputs[i])
    return n.outputs[0]


class Look:
    """Scene-wide shading parameters shared by every toon material."""

    def __init__(self, engine="BLENDER_EEVEE"):
        self.engine = engine
        self.group = bpy.data.node_groups.get(GROUP) or self._build_group()
        self.materials = {}

    @property
    def cel(self):
        return self.engine == "BLENDER_EEVEE"

    def _build_group(self):
        g = bpy.data.node_groups.new(GROUP, "ShaderNodeTree")
        for name, kind, default in (("Color", "NodeSocketColor", (0.8, 0.8, 0.8, 1)),
                                    ("Shadow", "NodeSocketColor", (0.55, 0.52, 0.72, 1)),
                                    ("Rim", "NodeSocketFloat", 0.35), ("Glow", "NodeSocketFloat", 0.0),
                                    ("Soft", "NodeSocketFloat", 0.0)):
            s = g.interface.new_socket(name=name, in_out="INPUT", socket_type=kind)
            s.default_value = default
        g.interface.new_socket(name="Shader", in_out="OUTPUT", socket_type="NodeSocketShader")
        inp = node(g, "NodeGroupInput", (-1400, 0))
        out = node(g, "NodeGroupOutput", (1300, 0))
        if self.cel:
            # Light arriving at a white diffuse surface, measured, banded and recolored.
            diffuse = node(g, "ShaderNodeBsdfDiffuse", (-1200, 200))
            diffuse.inputs["Color"].default_value = (1, 1, 1, 1)
            rgb = node(g, "ShaderNodeShaderToRGB", (-1000, 200))
            link(g, diffuse.outputs[0], rgb.inputs[0])
            sep = node(g, "ShaderNodeSeparateColor", (-820, 260))
            link(g, rgb.outputs["Color"], sep.inputs[0])
            peak = math_node(g, "MAXIMUM", math_node(g, "MAXIMUM", sep.outputs[0], sep.outputs[1], (-640, 300)),
                             sep.outputs[2], (-480, 300))
            scale = node(g, "ShaderNodeValue", (-640, 120), name="Light Scale", label="Light Scale")
            scale.outputs[0].default_value = 1.0
            level = math_node(g, "MULTIPLY", peak, scale.outputs[0], (-320, 300))
            ramp = node(g, "ShaderNodeValToRGB", (-160, 380), name="Bands", label="Bands")
            ramp.color_ramp.interpolation = "CONSTANT"
            ramp.color_ramp.elements[0].position = 0.0
            ramp.color_ramp.elements[0].color = (0, 0, 0, 1)
            ramp.color_ramp.elements[1].position = 0.36
            ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
            mid = ramp.color_ramp.elements.new(0.2)
            mid.color = (0.45, 0.45, 0.45, 1)
            link(g, level, ramp.inputs[0])
            soft = node(g, "ShaderNodeMapRange", (-160, 160), clamp=True)
            link(g, level, soft.inputs["Value"])
            soft.inputs["From Min"].default_value = 0.05
            soft.inputs["From Max"].default_value = 0.6
            band = node(g, "ShaderNodeMix", (60, 300), data_type="FLOAT")
            link(g, inp.outputs["Soft"], socket(band.inputs, "Factor", "VALUE"))
            link(g, ramp.outputs["Color"], socket(band.inputs, "A", "VALUE"))
            link(g, soft.outputs[0], socket(band.inputs, "B", "VALUE"))
            band_value = socket(band.outputs, "Result", "VALUE")
            # Hue of the light, so lanterns warm what they light and moonlight cools it.
            safe = math_node(g, "MAXIMUM", peak, 1e-4, (-480, 120))
            hue = node(g, "ShaderNodeVectorMath", (-320, 120), operation="DIVIDE")
            link(g, rgb.outputs["Color"], hue.inputs[0])
            comb = node(g, "ShaderNodeCombineXYZ", (-480, 0))
            for i in range(3):
                link(g, safe, comb.inputs[i])
            link(g, comb.outputs[0], hue.inputs[1])
            tinted, f, a, b, res = mix_color(g, "MIX", (60, 100))
            f.default_value = 0.85
            a.default_value = (1, 1, 1, 1)
            link(g, hue.outputs[0], b)
            lit = res
            scene_shadow = node(g, "ShaderNodeRGB", (-160, 560), name="Scene Shadow", label="Scene Shadow")
            scene_shadow.outputs[0].default_value = (1, 1, 1, 1)
            _, fs, as_, bs, tinted_shadow = mix_color(g, "MULTIPLY", (60, 520))
            fs.default_value = 1.0
            link(g, inp.outputs["Shadow"], as_)
            link(g, scene_shadow.outputs[0], bs)
            shade, f2, a2, b2, res2 = mix_color(g, "MIX", (260, 200))
            link(g, band_value, f2)
            link(g, tinted_shadow, a2)
            link(g, lit, b2)
            colored, f3, a3, b3, res3 = mix_color(g, "MULTIPLY", (440, 200))
            f3.default_value = 1.0
            link(g, inp.outputs["Color"], a3)
            link(g, res2, b3)
            # A thin rim catches the light on silhouettes.
            weight = node(g, "ShaderNodeLayerWeight", (60, -160))
            weight.inputs["Blend"].default_value = 0.35
            rim_ramp = node(g, "ShaderNodeValToRGB", (240, -160))
            rim_ramp.color_ramp.interpolation = "CONSTANT"
            rim_ramp.color_ramp.elements[1].position = 0.62
            link(g, weight.outputs["Facing"], rim_ramp.inputs[0])
            rim_lit = math_node(g, "MULTIPLY", rim_ramp.outputs["Color"], band_value, (440, -160))
            rim = math_node(g, "MULTIPLY", rim_lit, inp.outputs["Rim"], (600, -160))
            brighten, f4, a4, b4, res4 = mix_color(g, "SCREEN", (620, 120))
            link(g, rim, f4)
            link(g, res3, a4)
            link(g, lit, b4)
            # Atmospheric perspective: distance fades toward the scene's fog color.
            cam = node(g, "ShaderNodeCameraData", (420, -420))
            density = node(g, "ShaderNodeValue", (420, -560), name="Fog Density", label="Fog Density")
            density.outputs[0].default_value = 0.0
            fog_color = node(g, "ShaderNodeRGB", (620, -560), name="Fog Color", label="Fog Color")
            fog_color.outputs[0].default_value = (0.8, 0.85, 0.9, 1)
            travel = math_node(g, "MULTIPLY", cam.outputs["View Distance"], density.outputs[0], (600, -420))
            kept = math_node(g, "EXPONENT", math_node(g, "MULTIPLY", travel, -1.0, (700, -420)), None, (780, -420))
            amount = math_node(g, "SUBTRACT", 1.0, kept, (860, -420), clamp=True)
            fogged, f5, a5, b5, res5 = mix_color(g, "MIX", (900, -200))
            link(g, amount, f5)
            link(g, res4, a5)
            link(g, fog_color.outputs[0], b5)
            emission = node(g, "ShaderNodeEmission", (1080, 40))
            link(g, res5, emission.inputs["Color"])
            strength = math_node(g, "ADD", 1.0, inp.outputs["Glow"], (620, -60))
            link(g, strength, emission.inputs["Strength"])
            link(g, emission.outputs[0], out.inputs[0])
        else:
            bsdf = node(g, "ShaderNodeBsdfPrincipled", (300, 0))
            link(g, inp.outputs["Color"], bsdf.inputs["Base Color"])
            bsdf.inputs["Roughness"].default_value = 0.9
            link(g, inp.outputs["Color"], bsdf.inputs["Emission Color"])
            link(g, inp.outputs["Glow"], bsdf.inputs["Emission Strength"])
            link(g, bsdf.outputs[0], out.inputs[0])
        return g

    def set_fog(self, color, density):
        d = self.group.nodes.get("Fog Density")
        c = self.group.nodes.get("Fog Color")
        if d is not None:
            d.outputs[0].default_value = density
            c.outputs[0].default_value = rgba(color)

    def set_scene_shadow(self, tint):
        """Shift every material's shadows toward a scene's tint (night is bluer, sunset warmer)."""
        n = self.group.nodes.get("Scene Shadow")
        if n is not None:
            base = Look.shadow_tint
            n.outputs[0].default_value = tuple(min(2.0, a / b) for a, b in zip(tint, base)) + (1.0,)

    def set_key(self, strength):
        """Normalize bands to the key light: a surface facing a sun of this strength reads as 1."""
        n = self.group.nodes.get("Light Scale")
        if n:
            n.outputs[0].default_value = math.pi / max(strength, 1e-3)

    def material(self, name, color, shadow=None, rim=0.35, glow=0.0, soft=0.0, outline=None, patch=None):
        """A toon material; `outline` is the ink color for this material's silhouette.

        `patch` = (color, center, radii) paints a soft-edged ellipsoidal patch in object space,
        such as a penguin's white belly or a creature's pale tummy.
        """
        key = (name, color, shadow, rim, glow, soft, outline, repr(patch))
        if key in self.materials:
            return self.materials[key]
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        tree = m.node_tree
        tree.nodes.clear()
        group = node(tree, "ShaderNodeGroup", (0, 0))
        group.node_tree = self.group
        group.inputs["Color"].default_value = rgba(color)
        if patch:
            pcolor, center, radii = patch[:3]
            coord = node(tree, "ShaderNodeTexCoord", (-900, 0))
            offset = node(tree, "ShaderNodeVectorMath", (-700, 0), operation="SUBTRACT")
            link(tree, coord.outputs["Object"], offset.inputs[0])
            offset.inputs[1].default_value = center
            scaled = node(tree, "ShaderNodeVectorMath", (-520, 0), operation="DIVIDE")
            link(tree, offset.outputs[0], scaled.inputs[0])
            scaled.inputs[1].default_value = radii
            length = node(tree, "ShaderNodeVectorMath", (-340, 0), operation="LENGTH")
            link(tree, scaled.outputs[0], length.inputs[0])
            edge = node(tree, "ShaderNodeMapRange", (-180, 0), clamp=True)
            link(tree, length.outputs["Value"], edge.inputs["Value"])
            edge.inputs["From Min"].default_value = 1.0
            edge.inputs["From Max"].default_value = 0.96
            _, f, a, b, res = mix_color(tree, "MIX", (-150, 200))
            link(tree, edge.outputs[0], f)
            a.default_value = rgba(color)
            b.default_value = rgba(pcolor)
            link(tree, res, group.inputs["Color"])
        if isinstance(shadow, str):
            shadow = rgba(shadow)
        elif shadow is not None:
            shadow = tuple(shadow)[:3] + (1.0,)
        group.inputs["Shadow"].default_value = shadow or self.shadow_of(color)
        group.inputs["Rim"].default_value = rim
        group.inputs["Glow"].default_value = glow
        group.inputs["Soft"].default_value = soft
        out = node(tree, "ShaderNodeOutputMaterial", (300, 0))
        link(tree, group.outputs[0], out.inputs["Surface"])
        m.diffuse_color = rgba(color)
        m["outline"] = outline or ink_of(color)
        self.materials[key] = m
        return m

    shadow_tint = (0.60, 0.56, 0.80)

    def shadow_of(self, color):
        """Anime shadows shift toward a cool tone but keep some of the fill's own hue, never plain grey."""
        rgb = linear(color)
        peak = max(max(rgb), 1e-4)
        tint = self.shadow_tint
        return tuple(t * (0.72 + 0.28 * c / peak) for t, c in zip(tint, rgb)) + (1.0,)

    def outline_material(self, color):
        name = f"Ink {color}"
        m = bpy.data.materials.get(name)
        if m:
            return m
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        tree = m.node_tree
        tree.nodes.clear()
        emission = node(tree, "ShaderNodeEmission", (0, 100))
        emission.inputs["Color"].default_value = rgba(color)
        clear = node(tree, "ShaderNodeBsdfTransparent", (0, -60))
        geometry = node(tree, "ShaderNodeNewGeometry", (-200, 200))
        path = node(tree, "ShaderNodeLightPath", (-200, -100))
        hidden = math_node(tree, "MAXIMUM", geometry.outputs["Backfacing"], path.outputs["Is Shadow Ray"], (0, 260))
        mix = node(tree, "ShaderNodeMixShader", (200, 60))
        link(tree, hidden, mix.inputs[0])
        link(tree, emission.outputs[0], mix.inputs[1])
        link(tree, clear.outputs[0], mix.inputs[2])
        out = node(tree, "ShaderNodeOutputMaterial", (400, 60))
        link(tree, mix.outputs[0], out.inputs["Surface"])
        m.use_backface_culling = True
        if hasattr(m, "use_backface_culling_shadow"):
            m.use_backface_culling_shadow = True
        m.diffuse_color = rgba(color)
        return m


def ink_of(color):
    """A darker, warmer line color derived from the fill, as in colored-line animation."""
    r, g, b = (int(color.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    return "#{:02x}{:02x}{:02x}".format(int(r * 0.32 + 18), int(g * 0.26 + 10), int(b * 0.30 + 18))


def add_outline(look, obj, thickness=0.012):
    """Inverted-hull ink lines: a flipped shell whose back faces show only at silhouettes."""
    mats = [slot.material for slot in obj.material_slots]
    if not mats or obj.type != "MESH":
        return None
    for m in mats:
        obj.data.materials.append(look.outline_material(m.get("outline", "#2a1c24") if m else "#2a1c24"))
    mod = obj.modifiers.new("Ink", "SOLIDIFY")
    mod.thickness = thickness
    mod.offset = 1.0
    mod.use_flip_normals = True
    mod.use_rim = False
    mod.material_offset = len(mats)
    mod.use_quality_normals = True
    return mod


def render_settings(scene, width, height, fps, samples=16, engine="BLENDER_EEVEE"):
    scene.render.engine = engine
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.fps = fps
    scene.render.film_transparent = False
    scene.render.filter_size = 1.15
    scene.render.use_motion_blur = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.compression = 15
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    if engine == "BLENDER_EEVEE":
        ee = scene.eevee
        ee.taa_render_samples = samples
        for prop, value in (("use_raytracing", False), ("shadow_ray_count", 1), ("shadow_step_count", 2),
                            ("use_shadows", True), ("use_volumetric_shadows", False),
                            ("clamp_surface_indirect", 1.0), ("fast_gi_quality", 0.25)):
            if hasattr(ee, prop):
                setattr(ee, prop, value)
    else:
        scene.cycles.samples = max(16, samples)
        scene.cycles.use_denoising = True
        scene.cycles.device = "CPU"
        scene.cycles.max_bounces = 2
        scene.cycles.transparent_max_bounces = 8


def finishing(scene, bloom=0.35, threshold=1.0):
    """Blender 5 keeps compositor nodes in a node group: soft bloom on lamps, glows and highlights."""
    group = bpy.data.node_groups.new("Cartoon finishing", "CompositorNodeTree")
    group.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    scene.compositing_node_group = group
    layer = group.nodes.new("CompositorNodeRLayers")
    out = group.nodes.new("NodeGroupOutput")
    if bloom > 0:
        glare = group.nodes.new("CompositorNodeGlare")
        glare.inputs["Type"].default_value = "Bloom"
        glare.inputs["Strength"].default_value = bloom
        glare.inputs["Threshold"].default_value = threshold
        group.links.new(layer.outputs["Image"], glare.inputs["Image"])
        group.links.new(glare.outputs["Image"], out.inputs["Image"])
    else:
        group.links.new(layer.outputs["Image"], out.inputs["Image"])
    return group


def sky_material(name, top, horizon, bottom=None, sun=None, stars=0.0, clouds=0.0, seed=0):
    """An emissive dome: vertical gradient, optional sun glow, star field and soft painted clouds."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    t = m.node_tree
    t.nodes.clear()
    coord = node(t, "ShaderNodeTexCoord", (-1200, 0))
    sep = node(t, "ShaderNodeSeparateXYZ", (-1000, 0))
    norm = node(t, "ShaderNodeVectorMath", (-1100, -200), operation="NORMALIZE")
    link(t, coord.outputs["Object"], norm.inputs[0])
    link(t, norm.outputs[0], sep.inputs[0])
    ramp = node(t, "ShaderNodeValToRGB", (-800, 100))
    elements = ramp.color_ramp.elements
    elements[0].position = 0.0
    elements[0].color = rgba(bottom or horizon)
    elements[1].position = 1.0
    elements[1].color = rgba(top)
    mid = elements.new(0.5)
    mid.color = rgba(horizon)
    up = node(t, "ShaderNodeMapRange", (-900, 100))
    up.inputs["From Min"].default_value = -0.25
    up.inputs["From Max"].default_value = 0.6
    up.inputs["To Min"].default_value = 0.0
    up.inputs["To Max"].default_value = 1.0
    link(t, sep.outputs["Z"], up.inputs["Value"])
    shaped = node(t, "ShaderNodeMapRange", (-850, 300), interpolation_type="SMOOTHERSTEP")
    link(t, up.outputs[0], shaped.inputs["Value"])
    link(t, shaped.outputs[0], ramp.inputs[0])
    color = ramp.outputs["Color"]
    x = -560
    if sun:
        direction, sun_color, size = sun
        dot = node(t, "ShaderNodeVectorMath", (x, -200), operation="DOT_PRODUCT")
        link(t, norm.outputs[0], dot.inputs[0])
        dot.inputs[1].default_value = direction
        glow = node(t, "ShaderNodeMapRange", (x + 180, -200), interpolation_type="SMOOTHSTEP")
        link(t, dot.outputs["Value"], glow.inputs["Value"])
        glow.inputs["From Min"].default_value = 1 - size * 14
        glow.inputs["From Max"].default_value = 1.0
        disc = node(t, "ShaderNodeMapRange", (x + 180, -400), interpolation_type="SMOOTHSTEP")
        link(t, dot.outputs["Value"], disc.inputs["Value"])
        disc.inputs["From Min"].default_value = 1 - size
        disc.inputs["From Max"].default_value = 1 - size * 0.8
        haze, f, a, b, res = mix_color(t, "SCREEN", (x + 380, 0))
        link(t, math_node(t, "MULTIPLY", glow.outputs[0], 0.55, (x + 360, -200)), f)
        link(t, color, a)
        b.default_value = rgba(sun_color)
        core, f2, a2, b2, res2 = mix_color(t, "MIX", (x + 560, 0))
        link(t, disc.outputs[0], f2)
        link(t, res, a2)
        b2.default_value = (*[min(1.0, c * 1.4 + 0.25) for c in linear(sun_color)], 1)
        color = res2
        x += 760
    if clouds > 0:
        noise = node(t, "ShaderNodeTexNoise", (x, -300), noise_dimensions="3D")
        noise.inputs["Scale"].default_value = 2.2
        noise.inputs["Detail"].default_value = 6.0
        noise.inputs["Roughness"].default_value = 0.55
        stretch = node(t, "ShaderNodeMapping", (x - 180, -300))
        stretch.inputs["Scale"].default_value = (1.0, 1.0, 3.2)
        stretch.inputs["Location"].default_value = (seed * 1.7, seed * 0.3, 0)
        link(t, norm.outputs[0], stretch.inputs["Vector"])
        link(t, stretch.outputs[0], noise.inputs["Vector"])
        band = node(t, "ShaderNodeMapRange", (x + 180, -300), interpolation_type="SMOOTHSTEP")
        link(t, noise.outputs["Fac"], band.inputs["Value"])
        band.inputs["From Min"].default_value = 0.56
        band.inputs["From Max"].default_value = 0.66
        height = node(t, "ShaderNodeMapRange", (x + 180, -500), interpolation_type="SMOOTHSTEP")
        link(t, sep.outputs["Z"], height.inputs["Value"])
        height.inputs["From Min"].default_value = 0.02
        height.inputs["From Max"].default_value = 0.22
        amount = math_node(t, "MULTIPLY", math_node(t, "MULTIPLY", band.outputs[0], height.outputs[0], (x + 360, -400)),
                           clouds, (x + 520, -400))
        cloud, f, a, b, res = mix_color(t, "MIX", (x + 700, 0))
        link(t, amount, f)
        link(t, color, a)
        b.default_value = (1.0, 0.98, 0.96, 1)
        color = res
        x += 900
    if stars > 0:
        vor = node(t, "ShaderNodeTexVoronoi", (x, -300), voronoi_dimensions="3D", feature="F1")
        vor.inputs["Scale"].default_value = 140.0
        link(t, norm.outputs[0], vor.inputs["Vector"])
        dots = node(t, "ShaderNodeMapRange", (x + 180, -300))
        link(t, vor.outputs["Distance"], dots.inputs["Value"])
        dots.inputs["From Min"].default_value = 0.06
        dots.inputs["From Max"].default_value = 0.0
        pick = node(t, "ShaderNodeMapRange", (x + 180, -500))
        link(t, vor.outputs["Color"], pick.inputs["Value"])
        pick.inputs["From Min"].default_value = 0.82
        pick.inputs["From Max"].default_value = 1.0
        high = node(t, "ShaderNodeMapRange", (x + 180, -700))
        link(t, sep.outputs["Z"], high.inputs["Value"])
        high.inputs["From Min"].default_value = 0.05
        high.inputs["From Max"].default_value = 0.35
        lit = math_node(t, "MULTIPLY", math_node(t, "MULTIPLY", dots.outputs[0], pick.outputs[0], (x + 360, -400)),
                        high.outputs[0], (x + 520, -400))
        twinkle, f, a, b, res = mix_color(t, "ADD", (x + 700, 0))
        link(t, math_node(t, "MULTIPLY", lit, stars, (x + 600, -400)), f)
        link(t, color, a)
        b.default_value = (1.0, 0.97, 0.9, 1)
        color = res
        x += 900
    emission = node(t, "ShaderNodeEmission", (x, 0))
    link(t, color, emission.inputs["Color"])
    out = node(t, "ShaderNodeOutputMaterial", (x + 200, 0))
    link(t, emission.outputs[0], out.inputs["Surface"])
    return m


def ambient_world(scene, color, strength):
    world = bpy.data.worlds.new("Ambient")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = rgba(color)
    bg.inputs["Strength"].default_value = strength
    scene.world = world
    return world


def sun(name, direction_deg, color, strength, angle_deg=1.0, shadow=True):
    """A sun from (azimuth, elevation) in degrees; azimuth 0 shines from -Y (behind the camera's usual side)."""
    data = bpy.data.lights.new(name, "SUN")
    data.energy = strength
    data.color = linear(color)
    data.angle = math.radians(angle_deg)
    data.use_shadow = shadow
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    az, el = (math.radians(v) for v in direction_deg)
    # The light travels along -Z of the object; aim it from the given direction toward the origin.
    obj.rotation_euler = (math.pi / 2 - el, 0.0, az)
    return obj


def point(name, location, color, power, radius=0.1, shadow=False):
    data = bpy.data.lights.new(name, "POINT")
    data.energy = power
    data.color = linear(color)
    data.shadow_soft_size = radius
    data.use_shadow = shadow
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    return obj
