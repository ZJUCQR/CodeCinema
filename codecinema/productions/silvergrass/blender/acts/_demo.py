"""
acts/_demo.py - integration dev lane on a PRIVATE frame range (4001-4288, after the film): a 12 s mini-duel that
drives EVERY module through its real API, so one partial build exercises the whole chain end to end.

    Blender -b --factory-startup --python-exit-code 1 --python codecinema/productions/silvergrass/blender/build_scene.py -- --lanes _demo \
        [--quality layout|preview|final]

Story (4 shots / 9 sub-cuts, all cameras on the +X side of the Y action line - DIRECTION §1; frames in F / CUTS):
  D01   4001-4040  telephoto profile (135 mm, ~40 m), sun disk between them: the shinobi walks in through the
                   grass (parting + wake) and draws; the elder waits, sinking into his iai crouch.
  D02a  4041-4061  wide: the elder's iai draw-cut SHEARS the grass tops in an expanding arc (environment 'shear');
                   the shinobi leaps over the cut-line and plunges - heavy clash on the overhead block (shake).
  D02b  4062-4098  handheld medium: the elder's kesa + rising cut, both deflected (sparks, trails, shake).
  D02c  4099-4119  over the ELDER'S LEFT shoulder (DOF on the shinobi): thrust -> sidestep.
  D03a  4120-4150  close profile (DOF): the elder's first two-handed overhead -> PERFECT DEFLECT (flash ring,
                   stagger); the shinobi's rising counter cuts the straw hat in two (props.cut_hat).
  D03b  4151-4191  low angle on the elder: he sheathes and sheds the haori (costume swap); dusk -> storm begins.
  D03c  4192-4217  3/4 from behind his left: the spear drawn over the shoulder, the sheath spins off.
  D04a  4218-4256  high wide 24 mm with the lone pine: a ring of fire erupts for a moment, the rain comes,
                   lightning splits the pine (tree_strike, flash), the fire drowns into steam; spear clash.
  D04b  4257-4288  handheld medium on the shinobi (DOF), cut on the kick contact: he skids back screen-left and
                   kneels with the sword planted in the rain; a second (distant) lightning flash.
Modules exercised: characters (+ meshes: weapon states, costume swap, hat halves, spear sheath), moves (walk, draw,
iai, plunge, clash combo, perfect deflect, dodge, sheathe, shed_haori, spear_draw, spear_thrust, kick, skid,
kneel), secondary motion (build_scene), environment (states + blend, set_sun cheat, wind, shear, burn, wet,
clearance, flash; wake via build_scene env.finalize), vfx (trails, sparks, flash ring via moves, fire ring,
rain, lightning, tree strike, env flash), cameras (9 sub-cuts, handheld, impact shakes, DOF), events.
Setting dev.demo_raise (config.DEV_DEMO_RAISE; env SILVERGRASS_DEV_DEMO_RAISE=1) makes build() raise half-way
(failure-path tests of build_scene / lane_preview).
"""

import zlib

import bpy

import config
import bl_util as U
import cameras as C
import events as EV

SPAN = (4001, 4288)
assert SPAN[0] > config.FRAME_END, "_demo's private frame range must lie after the film"
SHOTS = [
    dict(id="D01", start=4001, end=4040, desc="telephoto profile: walk-in through the grass, the shinobi draws"),
    dict(id="D02", start=4041, end=4119, desc="a: iai grass shear + jump/plunge clash; b: combo; c: OTS thrust/dodge"),
    dict(id="D03", start=4120, end=4217, desc="a: perfect deflect + hat cut; b: sheathe, haori shed; c: spear draw"),
    dict(id="D04", start=4218, end=4288, desc="a: fire ring, rain, pine strike, spear clash, kick; b: kneel"),
]
# the key moments (film frames) - everything below is timed from these (contact = the clash frame)
F = dict(
    walk=(4001, 4028), sh_draw=4033, iai=4046, shear_end=4056, jump=(4048, 4062), plunge=4059,
    kesa=4080, rising=4096, thrust=4110, overhead=4132, hat=4148,
    sheathe=4168, shed=4188, spear=4211, storm=(4160, 50),
    fire=4219, fire_out=4238, rain=4226, strike=4230, spear_thrust=4240, kick=4257, skid=(4258, 4268),
    kneel=4280, flash2=4284,
    # staging beats between the moves (the lane's own timing): the elder sinks into iai, adjusting steps, kick step
    sa_crouch=(4020, 4032), stage1=(4070, 4074), stage2=(4114, 4119), stage3=(4219, 4227), kick_step=(4247, 4251),
)
# sub-cuts: (cut id, f0, f1) - every cut 2-3 f after a contact (DIRECTION §2); the kick contact is ON the cut
CUTS = [("D01", 4001, 4040), ("D02a", 4041, 4061), ("D02b", 4062, 4098), ("D02c", 4099, 4119),
        ("D03a", 4120, 4150), ("D03b", 4151, 4191), ("D03c", 4192, 4217), ("D04a", 4218, 4256),
        ("D04b", 4257, 4288)]
CUT = {c: (a, b) for c, a, b in CUTS}
SA_START = (0.0, 2.0)
SH_START = (0.0, -6.0)
SH_WALK_TO = (0.0, -3.0)


def _seed(tag):
    """Deterministic seed for an effect of this lane (zlib.crc32, never hash())."""
    return zlib.crc32(f"_demo:{tag}".encode()) & 0x7FFFFFFF


def _xy(rig, f, M):
    """(x, y) of a rig's keyed root at film frame f."""
    x, y, _, _ = M.root_at(rig, f)
    return (x, y)


def _stage(M, mover, other, f0, f1, dist, facing=None):
    """One adjusting step of `mover` (f0 -> f1) along the line to `other` so that the root-to-root distance is
    `dist` m at f1 (staging distances); the step also re-centres the mover on the x = 0 line."""
    from mathutils import Vector
    mx, my = _xy(mover, f0, M)
    ox, oy = _xy(other, f1, M)
    d = Vector((mx - ox, my - oy))
    d = d.normalized() if d.length > 1e-6 else Vector((0.0, -1.0))
    p = Vector((ox, oy)) + d * dist
    return M.step(mover, f0, f1, (p.x * 0.5, p.y), facing=facing)


def choreograph(SH, SA):
    """Key both rigs through the poses / moves / characters / props APIs. Returns marks {name: frame}."""
    import characters as CH
    import moves as M
    import props as PR
    f0 = SPAN[0]
    # ---- entering state (the first key of a visibility / state channel extrapolates backwards)
    for r in (SH, SA):
        CH.set_weapon_state(r, f0, "sheathed")
        CH.set_arm_mode(r, f0, "fk")
        CH.set_left_hand(r, f0, "free")
    CH.set_weapon_state(SA, f0, "slung")
    CH.set_hat(f0, "on")
    CH.set_costume(f0, haori=True)
    CH.set_beard_cord(f0, False)
    CH.set_kunai_in_hand(f0, False)
    for i in (1, 2, 3):
        U.key_visible(bpy.data.objects[f"SHINOBI_kunai_{i}"], f0, False)
    CH.set_spear_grip(f0, 0.35, 0.95)
    # ---- D01: the walk-in; the elder waits, then sinks into his iai crouch
    M.root(SA, f0, SA_START, 0.0)
    M.stance(SA, f0, "relaxed_saya")
    M.stance(SA, F["sa_crouch"][0], "relaxed_saya")
    M.stance(SA, F["sa_crouch"][1], "iai_crouch")
    M.root(SH, f0, SH_START, 180.0)
    M.stance(SH, f0, "relaxed")
    M.walk(SH, F["walk"][0], F["walk"][1], SH_START, SH_WALK_TO, upper="relaxed_saya")
    M.draw_sword(SH, F["sh_draw"], end="chudan")
    # ---- D02a: iai draw-cut (grass shear) -> the shinobi leaps the cut-line and plunges onto the overhead block
    M.iai_slash(SA, F["iai"], "horizontal", "L", lunge=0.3, recover=3)
    xa, ya = _xy(SA, F["plunge"], M)
    M.plunge(SH, F["jump"][0], F["jump"][1], SH_WALK_TO, (xa, ya - 1.25), apex=0.9, impact=F["plunge"],
             recover=6)
    M.deflect(SA, F["plunge"], "overhead_block", recoil=1.4)
    M.clash(SH, SA, F["plunge"], strength=1.0, kind="clash_heavy")
    # ---- D02b: the elder's kesa + rising cut, both deflected
    _stage(M, SH, SA, *F["stage1"], 1.75, facing=180.0)
    M.slash(SA, F["kesa"], "diag_down_R", lunge=0.25)
    M.deflect(SH, F["kesa"], "mid_L")
    M.clash(SA, SH, F["kesa"], strength=0.8)
    M.slash(SA, F["rising"], "rising_L", lunge=0.10)
    M.deflect(SH, F["rising"], "mid_R")
    M.clash(SA, SH, F["rising"], strength=0.7)
    # ---- D02c: thrust -> sidestep (the shinobi's left = away from the +X camera side)
    M.slash(SA, F["thrust"], "thrust", lunge=0.35)
    M.dodge(SH, F["thrust"], "left", dist=0.7)
    _stage(M, SH, SA, *F["stage2"], 1.9, facing=180.0)
    # ---- D03a: the first two-handed overhead -> perfect deflect (flash ring, stagger); the counter cuts the hat
    M.slash(SA, F["overhead"], "overhead", two_hand=True, lunge=0.45, recover=6)
    M.perfect_deflect(SH, F["overhead"], attacker=SA, strength=1.0)
    M.slash(SH, F["hat"], "rising_R", lunge=0.35)
    PR.cut_hat(F["hat"], away=(0.0, 1.0, 0.0), seed="_demo")
    # ---- D03b/c: sheathe, shed the haori (costume swap), draw the spear over the shoulder
    M.sheathe(SA, F["sheathe"], speed="quick", end="relaxed")
    M.shed_haori(SA, F["shed"])
    M.spear_draw(SA, F["spear"], twirl=False)
    # ---- D04a: spear thrust clash, then the kick
    _stage(M, SH, SA, *F["stage3"], 2.5, facing=180.0)
    M.spear_thrust(SA, F["spear_thrust"], recover=4)
    M.deflect(SH, F["spear_thrust"], "mid_R")
    M.clash(SA, SH, F["spear_thrust"], strength=0.8, weapon_a="spear")
    xs, ys = _xy(SH, F["kick_step"][0], M)
    M.step(SA, *F["kick_step"], (xs, ys + 1.12))
    M.kick(SA, F["kick"])
    # ---- D04b: skid back screen-left (-Y), kneel with the sword planted
    xs, ys = _xy(SH, F["skid"][0], M)
    M.skid(SH, F["skid"][0], F["skid"][1], None, (xs, ys - 1.4), recover=4)
    M.kneel(SH, F["kneel"])
    return dict(F)


def _pine_top():
    """World position just below the top of ENV_pine (config.PINE_POS + a guess when the pine is missing)."""
    from mathutils import Vector
    pine = bpy.data.objects.get("ENV_pine")
    if pine is None:
        return (config.PINE_POS[0], config.PINE_POS[1], 12.0)
    Mw = U.world_matrix_of(pine)
    corners = [Mw @ Vector(c) for c in pine.bound_box]
    return (Mw.translation.x, Mw.translation.y, max(c.z for c in corners) - 0.3)


def environment_timeline(SH, SA):
    """Light states, sun cheat, wind, the S11-style shear, burn, rain wetness and per-cut grass clearance."""
    import environment as ENV
    import moves as M
    ENV.set_state(SPAN[0], "dusk_gold")
    ENV.set_sun(SPAN[0], 270.0, 1.0, 2.0)                 # D01 cheat: a big low disk between the two figures
    ENV.set_sun(CUT["D02a"][0], 270.0, 4.0, 2.2)          # back to the dusk default on the next cut
    ENV.set_wind(SPAN[0], 1.0)
    xa, ya = _xy(SA, F["iai"], M)
    ENV.grass_effect("shear", dict(origin=(xa, ya), radius=9.0, arc_deg=150.0, facing_deg=180.0, fluff=2400),
                     F["iai"], F["shear_end"])
    # D03b low angle: no half-grown blades at the lens, full grass at the elder (2.8 m away)
    ENV.set_camera_clearance(CUT["D03b"][0], near=1.7, far=2.5)
    ENV.set_camera_clearance(CUT["D03c"][0], near=ENV.CLEAR_NEAR, far=ENV.CLEAR_FAR)
    ENV.set_state(F["storm"][0], "storm_night", blend_frames=F["storm"][1])
    ENV.set_wind(F["storm"][0], 1.0)
    ENV.set_wind(F["storm"][0] + F["storm"][1], 1.8)
    mx, my = _mid(SH, SA, F["fire"], M)
    ENV.grass_effect("burn", dict(center=(mx, my), radius=6.5, width=2.0, ramp_frames=10), F["fire"], None)
    ENV.grass_effect("wet", dict(amount=1.0, ramp_frames=30), F["rain"], None)


def _mid(SH, SA, f, M):
    a, b = _xy(SH, f, M), _xy(SA, f, M)
    return ((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5)


def effects(SH, SA):
    """vfx calls: blade trails of every fast cut (sparks + the flash ring come from moves' clash resolution),
    landing dust, the fire ring, rain, the pine strike and a second (distant) lightning flash."""
    import moves as M
    import vfx
    trails = [("SAINT_katana", F["iai"] - 4, F["iai"] + 1), ("SHINOBI_katana", F["plunge"] - 3, F["plunge"] + 1),
              ("SAINT_katana", F["kesa"] - 3, F["kesa"] + 1), ("SAINT_katana", F["rising"] - 3, F["rising"] + 1),
              ("SAINT_katana", F["thrust"] - 3, F["thrust"] + 1),
              ("SAINT_katana", F["overhead"] - 3, F["overhead"] + 1), ("SHINOBI_katana", F["hat"] - 3, F["hat"] + 2),
              ("SAINT_spear", F["spear_thrust"] - 3, F["spear_thrust"] + 1)]
    for i, (w, a, b) in enumerate(trails):
        vfx.blade_trail(f"{w}_tip", f"{w}_base", a, b, name=f"D_trail_{i}")
    xs, ys = _xy(SH, F["jump"][1], M)
    vfx.dust_burst(F["jump"][1], (xs, ys, 0.05), radius=0.7, seed=_seed("land"))
    vfx.grass_burst(F["jump"][1], (xs, ys, 0.3), count=40, fluff=0.15, seed=_seed("land_grass"))
    xs, ys = _xy(SH, F["skid"][0] + 4, M)                  # the skid is in the rain: wet grass bits, no dust
    vfx.grass_burst(F["skid"][0] + 2, (xs, ys, 0.25), direction=(0.0, -0.5, 1.0), count=50, fluff=0.1,
                    seed=_seed("skid"))
    mx, my = _mid(SH, SA, F["fire"], M)
    tail = SPAN[1] + config.FPS             # effect envelopes end 1 s after the lane: no fade-out inside the last cut
    vfx.fire_ring(F["fire"], (mx, my, 0.0), radius=6.5, grow_frames=10, f_out=F["fire_out"], f_end=tail,
                  seed=_seed("fire"))
    vfx.rain(F["rain"], tail, intensity=[(F["rain"], 0.25), (F["rain"] + 6, 1.0)], seed=_seed("rain"))
    top = _pine_top()
    vfx.lightning_bolt(F["strike"], (top[0] - 14.0, top[1] + 30.0, 90.0), top, branches=3, seed=_seed("bolt"))
    vfx.tree_strike(F["strike"], flame_until=F["strike"] + 34, steam_until=tail, seed=_seed("pine"))
    vfx.lightning_bolt(F["flash2"], (-70.0, 140.0, 95.0), (-55.0, 110.0, 0.0), branches=2, seed=_seed("bolt2"),
                       flash_strength=0.6)


def story_events(SH, SA):
    """Tagged beats the moves / vfx calls do not emit themselves (audio + music sync)."""
    import moves as M
    xa, ya = _xy(SA, F["iai"], M)
    EV.emit(F["iai"], "grass_shear", pos=(xa, ya - 1.0, 0.8), tags=["demo"])
    EV.emit(F["iai"] + 2, "wind_gust", strength=0.8)
    EV.emit(F["hat"], "hat_cut", target=("SAINT_rig", "head"))
    EV.emit(F["storm"][0], "stinger", strength=0.5)
    mx, my = _mid(SH, SA, F["fire"], M)
    EV.emit(F["fire"], "fire_ignite", pos=(mx, my, 0.3))
    EV.emit(F["fire"] + 6, "fire_burst", pos=(mx, my, 0.8), strength=0.6)
    EV.emit(F["rain"], "rain_start")
    top = _pine_top()
    EV.emit(F["strike"], "lightning_strike", pos=top)
    EV.emit(F["strike"], "tree_split", pos=top)
    EV.emit(F["strike"] + 3, "thunder", distance="near", strength=1.0)
    EV.emit(F["fire_out"], "steam_hiss", pos=(mx, my, 0.5), duration=24)
    EV.emit(F["flash2"] + 3, "thunder", distance="far", strength=0.5)


def cameras(SH, SA):
    """9 sub-cuts, all on the +X side of the action line (shinobi screen-left): telephoto profile, wide, handheld
    medium with impact shakes, OTS over the elder's LEFT shoulder with DOF, close profile with DOF, low angle,
    3/4 medium, pine wide, handheld medium with DOF."""
    import moves as M
    from mathutils import Vector
    head_sh = (SH, "head")
    # D01 telephoto profile (135 mm from ~40 m): slow lateral drift following the walk
    a, b = CUT["D01"]
    C.shot("D01", a, b, [(a, (40.0, -2.3, 2.0), (0.0, -2.0, 1.15), 135.0),
                         (b, (40.0, -1.2, 2.0), (0.0, -0.9, 1.15))],
           subjects=["shinobi", "saint"], framing="wide")
    # D02a wide 28 mm: the cut-line races through the grass, the leap, the heavy clash (shake)
    a, b = CUT["D02a"]
    mx, my = _mid(SH, SA, F["jump"][0] + 2, M)
    C.shot("D02a", a, b, [(a, (9.0, my - 1.8, 2.3), (0.0, my - 0.3, 1.1), 28.0),
                          (b, (8.6, my - 1.2, 2.2), (0.0, my + 0.4, 1.3))],
           shake=[(F["plunge"], 0.7, 8)], subjects=["shinobi", "saint"], framing="wide")
    # D02b handheld medium 45 mm: kesa + rising cut (shake on the first clash)
    mx, my = _mid(SH, SA, F["kesa"], M)
    a, b = CUT["D02b"]
    C.shot("D02b", a, b, [(a, (5.4, my - 0.2, 1.5), (0.0, my, 1.2), 40.0),
                          (b, (5.2, my + 0.1, 1.5), (0.0, my + 0.1, 1.2))],
           handheld=0.4, shake=[(F["kesa"], 0.5, 6)], subjects=["shinobi", "saint"], framing="medium")
    # D02c OTS over the elder's LEFT shoulder (+X side of the line), DOF on the shinobi: the camera sits 1.3 m
    # behind and 1.1 m to the side of the elder's head, so his shoulder frames screen-right and never hides him
    keys = []
    a, b = CUT["D02c"]
    for f in (a, b):
        (xs, ys), (xa, ya) = _xy(SH, f, M), _xy(SA, f, M)
        u = Vector((xa - xs, ya - ys)).normalized()
        n = Vector((u.y, -u.x))                   # perpendicular toward +X for a shinobi -> elder line along +Y
        p = Vector((xa, ya)) + u * 1.2 + n * 1.1
        keys.append((f, (p.x, p.y, 1.6), head_sh, 35.0 if f == a else None))      # below the hat brim
    C.shot("D02c", a, b, keys, dof=dict(focus=head_sh, fstop=2.8), subjects=["shinobi"], framing="ots")
    # D03a close profile 50 mm, DOF on the exchange point: perfect deflect + hat cut
    mx, my = _mid(SH, SA, F["overhead"], M)
    a, b = CUT["D03a"]
    C.shot("D03a", a, b, [(a, (3.4, my, 1.45), (0.0, my, 1.45), 50.0)],
           dof=dict(focus=(0.0, my, 1.45), fstop=2.8), shake=[(F["overhead"], 0.35, 5)],
           subjects=["shinobi", "saint"], framing="close")
    # D03b low angle on the elder (head against the sky): sheathe + haori shed
    a, b = CUT["D03b"]
    xa, ya = _xy(SA, F["sheathe"] + 2, M)
    C.shot("D03b", a, b, [(a, (xa + 2.6, ya - 1.0, 0.45), (xa, ya, 1.55), 30.0),
                          (b, (xa + 2.5, ya - 0.8, 0.45), (xa, ya, 1.6))],
           subjects=["saint"], framing="mcu")
    # D03c 3/4 medium from behind the elder's left (+X side): the spear draw, the sheath spins off
    xa, ya = _xy(SA, F["spear"], M)
    a, b = CUT["D03c"]
    C.shot("D03c", a, b, [(a, (xa + 3.2, ya + 1.6, 1.6), (xa, ya - 0.3, 1.6), 35.0)],
           subjects=["saint"], framing="mcu")
    # D04a wide 24 mm with the lone pine: fire ring, rain, the strike, the spear clash
    mx, my = _mid(SH, SA, F["spear_thrust"], M)
    top = Vector(_pine_top())
    cam = Vector((mx + 9.0, my - 7.0, 3.4))                                 # high enough to see over the flames
    to_fight = (Vector((mx, my, 1.2)) - cam).normalized()
    to_pine = (top - cam).normalized()
    look = cam + (to_fight * 0.6 + to_pine * 0.4).normalized() * 15.0       # both in a 24 mm frame
    a, b = CUT["D04a"]
    C.shot("D04a", a, b, [(a, tuple(cam), tuple(look), 24.0),
                          (b, (cam.x - 0.6, cam.y + 0.6, cam.z), tuple(look))],
           subjects=["shinobi", "saint"], framing="wide")
    # D04b handheld medium on the shinobi (DOF): skid, kneel in the rain, the second flash
    xs, ys = _xy(SH, F["kneel"], M)
    a, b = CUT["D04b"]
    C.shot("D04b", a, b, [(a, (xs + 4.1, ys - 1.4, 1.3), (xs, ys + 0.7, 1.1), 35.0),   # inside the ring, steam
                          (b, (xs + 3.9, ys - 1.4, 1.15), (xs, ys + 0.4, 0.8))],      # band behind; > 4 m from him
                                                                                      # (grass clearance radius)
           handheld=0.25, dof=dict(focus=head_sh, fstop=2.8), subjects=["shinobi"], framing="medium")


def build(ctx):
    """Lane entry (acts contract): keys only inside SPAN, cameras through cameras.shot, events through events.emit."""
    sh, sa = ctx["chars"]["shinobi"], ctx["chars"]["saint"]
    stubs = ctx.get("stubs", {})
    missing = [m for m in ("characters", "moves", "environment", "vfx") if stubs.get(m)]
    if missing:
        raise RuntimeError(f"_demo needs the real modules (placeholders: {missing})")
    choreograph(sh, sa)
    if config.DEV_DEMO_RAISE:
        raise RuntimeError("_demo: simulated lane failure (config.DEV_DEMO_RAISE)")
    environment_timeline(sh, sa)
    effects(sh, sa)
    story_events(sh, sa)
    cameras(sh, sa)
    for ob in (sh, sa):
        U.freeze_handles(ob, SPAN)
