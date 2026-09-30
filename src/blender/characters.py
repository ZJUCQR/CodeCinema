"""
characters.py - rigs, sword/spear controllers, props and sockets of the two duelists (runs inside Blender 5.2).

    Saku           -> SHINOBI_rig   (1.72 m, slim, masterless shinobi)
    Tenkosai       -> SAINT_rig     (1.85 m standing height, broad, slight stoop, old lay-monk (nyudo) swordmaster)

Public API:
  build          build(meshes='auto'|'placeholder'|'none', place=True) -> dict(shinobi, saint, props, dims)
                 (calls character_meshes.build_meshes(rigs, props, DIMS) when that module exists; idempotent)
  states         set_weapon_state(rig_or_name, f, state)   katana: sheathed|drawn|broken ; spear: slung|in_hand|world|gone
                 set_arm_mode(rig, f, 'ik'|'fk', blend=0) ; set_left_hand(rig, f, 'free'|'grip'|'saya', blend=0, weapon)
                 set_two_hand(rig, f, on, weapon=None, blend=0) ; left_hand(rig, f) ; active_weapon(rig, f)
                 set_costume(f, haori=True, thrown=None) (-> snapshot_haori) ; set_hat(f, 'on'|'cut'|'off')
                 set_hat_tilt(f, pitch, roll) ; set_beard_cord(f, cut) ; set_kunai_in_hand(f, on)
                 set_spear_grip(f, grip_R=None, grip_L=None) ; spear_grip(f) ; key_saya(rig, f, pull, roll) ; saya_basis
  sword          blade_frame(grip, direction, edge=None) ; sword_ctrl_matrix(rig, grip, direction, edge, space, frame)
                 key_sword(rig, f, grip, direction, edge=None, space='WORLD') ; key_blade_tip(rig, f, tip, direction, ...)
                 key_ctrl_matrix(obj, f, local) ; tip_distance(rig, weapon=None) ; blade_points(rig, f=None)
                 sheathed_ctrl_matrix(rig, f) ; slung_spear_ctrl_matrix(f, grip_R=None)
  QA             reach_report(rig, f=None) ; reach_ok(rig, f=None, tol=0.002) ; wrist_report(rig, f=None)
                 wrist_issues(rig, f=None) ; wrist_ok(rig, f=None) ; hat_clearance(f=None) ; hat_ok(f=None, min_clear)
  elbows         auto_elbow(rig, f=None, side='R', key=True) ; key_elbow(rig, f, side, point, influence, blend, space)
                 release_elbow(rig, f, side, blend=0)
  free props     detach_matrix(name_or_obj, f) ; snap_free(name_or_obj, f, interp='CONSTANT') ; snapshot_haori(f)
  poses          apply_pose(rig, spec) ; pose_bones(rig, body, frame=None, ...) ; mirror_pose(body) ; mirror_name(bone)
                 solve_leg(rig, side, ankle, hips_rot, hips_offset, knee_dir, foot_yaw, foot_pitch)
  secondary      apply_secondary_motion(rig | [rigs], f0, f1, wind=1.0|callable|(strength,(dx,dy)), cuts=None,
                 preroll=None (1 s), wetness=None) ; settle_secondary(rig, wind=0, wetness=0) ; env_wetness(f)
  rig data       DIMS, RIG_PARAMS, BODY_BONES, TWIST_BONES, SECONDARY_BONES, SECONDARY_CHAINS, WET, WRIST_LIMITS,
                 rig_template(char), build_rig(char), bone_axes(rig, bone), weapon_frame_in_hand(rig, side),
                 saya_fist_matrix(char), skin_by_distance(obj, rig, regions)

Conventions:
    * rig object origin = ground point between the feet; rotation_euler.z = 0 -> faces -Y; +X = character's LEFT.
    * every bone: local +Y along the bone; the roll is computed from a reference vector for the local +Z axis
      (ZREF below, mirrored for .L/.R) so both rigs share identical conventions:
      +X = anatomical flexion (spine/chest/neck/head forward bend, hip flexion = leg forward, knee flexion = heel
      back, elbow flexion = forearm forward/up, shoulder flexion = arm forward/up, wrist flexion = palm side).
      Y/Z rotations are mirrored between .L and .R (Blender's symmetric convention): mirror a pose with
      (rx, -ry, -rz) + swap .L/.R  (mirror_pose()).
    * pose bones use rotation_mode 'XYZ'; pose data is in DEGREES in the pose library, radians in Blender.
    * <C>_sword_ctrl (empty, child of the rig object) is the BLADE frame: origin = centre of the right fist on
      the grip, local +Y = blade direction (grip -> tip), local -Z = cutting edge, +X = flat normal.
      Chudan (blade forward-up 30 deg, edge down) = rotation (30, 0, 180) deg in rig space.
      Internally a child empty <C>_sword_ctrl_wrist (fixed offset = right-hand grip) is the IK target of
      forearm.R (chain 2, pole <C>_pole_R) and the Copy Rotation (WORLD) source of hand.R, so weapon.R (and the
      in-hand prop) lands exactly on the controller frame whenever the target is reachable.
"""
import math
import os
import sys
import time
import zlib

import bpy
import numpy as np
from mathutils import Euler, Matrix, Quaternion, Vector

ROOT = (__import__("os").environ.get("SILVERGRASS_ROOT") or str(next(p for p in __import__("pathlib").Path(__file__).resolve().parents if (p / "src" / "common" / "config.py").is_file())))   # repo root (portable)
for _p in (os.path.join(ROOT, "src", "common"), os.path.join(ROOT, "src", "blender")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import config  # noqa: E402
import bl_util as U  # noqa: E402

CHARS = ("SHINOBI", "SAINT")
COLLECTION = "CHARACTERS"
REF_HEIGHT = config.SHINOBI_HEIGHT   # all proportions are authored for the shinobi's body height

# =============================================================================================
# DIMS - dimensions the meshes lane MUST honour (sockets / controllers are derived from them)
# All lengths in metres.
# =============================================================================================
DIMS = {
    "SHINOBI": dict(
        height=config.SHINOBI_HEIGHT, build="slim",
        # --- katana (uchigatana, black saya). Local frame of <C>_katana_hand / _katana_sheathed:
        #     origin = right-fist grip centre on the tsuka axis, +Y = towards the tip, -Z = edge side.
        blade_length=0.70,        # tsuba face -> kissaki tip (chord, along +Y)
        tsuka_length=0.25,        # tsuba back face -> kashira end
        grip_to_tsuba=0.050,      # right-fist centre -> tsuba centre plane (+Y)
        hand_spacing=0.160,       # right-fist centre -> left-fist centre along -Y (two-handed grip)
        tsuba_diameter=0.078, tsuba_thickness=0.008, habaki_length=0.032,
        blade_width=0.043,        # edge-to-back at the habaki  (1.4 x a real 3.1 cm)
        blade_width_tip=0.032,    # just below the kissaki
        blade_thickness=0.0105,   # kasane at the base (1.4 x 7.5 mm)
        sori=0.017,               # max curvature sagitta; the blade bulges towards the EDGE (-Z); tip stays on +Y
        tsuka_width=0.036, tsuka_depth=0.028,
        saya_length=0.745, saya_width=0.050, saya_depth=0.030,   # saya local frame: origin = koiguchi, +Y = to kojiri
        saya_grip_L=0.055,        # left-fist centre behind the koiguchi (along +Y of the saya): thumb reaches the tsuba
        kunai_length=0.20,
    ),
    "SAINT": dict(
        height=config.SAINT_HEIGHT, build="broad, slight stoop",
        blade_length=0.82, tsuka_length=0.31, grip_to_tsuba=0.052, hand_spacing=0.190,
        tsuba_diameter=0.085, tsuba_thickness=0.009, habaki_length=0.035,
        blade_width=0.046, blade_width_tip=0.033, blade_thickness=0.011, sori=0.021,
        tsuka_width=0.038, tsuka_depth=0.030,
        saya_length=0.87, saya_width=0.052, saya_depth=0.032, saya_grip_L=0.058,
        break_from_tip=0.33,      # the blade snaps this far below the tip (S26); tip piece = SAINT_katana_tip_broken
        # --- straight yari. Local frame of SAINT_spear_hand/_slung/_world(*): origin = BUTT end (ishizuki),
        #     +Y = towards the spear tip, -Z = one edge of the (two-edged) blade.   (*) _world: origin at the CoM
        spear_length=2.30, spear_blade_length=0.30, spear_shaft_diameter=0.034,
        spear_grip_R=0.35,        # default right-fist position measured from the butt (keyable, set_spear_grip)
        spear_grip_L=0.95,        # default left-fist position from the butt (front hand)
        spear_sheath_length=0.36, spear_sheath_diameter=0.060,  # black-lacquer sheath over the blade (slung state)
        spear_com=1.30,           # centre of mass from the butt (origin of SAINT_spear_world)
        hat_diameter=0.62, hat_height=0.13,   # sugegasa; origin = rim-plane centre, +Z up; halves split at local X=0
        hat_seat=0.105,           # rim plane sits this far below the crown top (head tail)
        beard_length=0.32, beard_cord_diameter=0.034,
    ),
}

# =============================================================================================
# rig templates (A-pose, faces -Y). Positions are computed from a few proportion parameters.
# =============================================================================================
RIG_PARAMS = {
    "SHINOBI": dict(
        H=config.SHINOBI_HEIGHT, z_hips=0.930,
        seg=dict(hips=0.090, spine=0.150, chest=0.240, neck=0.100, head=0.210),   # before height fit
        lean=dict(hips=0.0, spine=0.0, chest=-1.0, neck=10.0, head=-2.0),        # deg forward from vertical
        shoulder_half=0.185, clav_inner=0.022, hip_half=0.088, ankle_half=0.100,
        upper_arm=0.298, forearm=0.255, hand=0.090, arm_down=45.0, elbow_bend=16.0,
        knee_bend=10.0, z_hipjoint=0.903, z_ankle=0.077, foot=(0.130, 0.055), toe=(0.065, 0.006),
        head_depth=0.20,
    ),
    "SAINT": dict(
        H=config.SAINT_HEIGHT, z_hips=1.000,
        seg=dict(hips=0.097, spine=0.160, chest=0.262, neck=0.105, head=0.222),
        lean=dict(hips=0.0, spine=2.0, chest=10.0, neck=26.0, head=4.0),          # slight stoop (kyphosis)
        shoulder_half=0.215, clav_inner=0.026, hip_half=0.100, ankle_half=0.115,
        upper_arm=0.322, forearm=0.275, hand=0.098, arm_down=46.0, elbow_bend=16.0,
        knee_bend=10.0, z_hipjoint=0.972, z_ankle=0.083, foot=(0.142, 0.060), toe=(0.070, 0.006),
        head_depth=0.215,
    ),
}

BODY_BONES = ["hips", "spine", "chest", "neck", "head",
              "shoulder.L", "upper_arm.L", "forearm.L", "hand.L",
              "shoulder.R", "upper_arm.R", "forearm.R", "hand.R",
              "thigh.L", "shin.L", "foot.L", "toe.L",
              "thigh.R", "shin.R", "foot.R", "toe.R"]
SOCKET_BONES = ["weapon.R"]
# forearm twist helpers (non-IK, deform the distal half of the forearm): a Transformation constraint copies
# TWIST_SHARE of the hand's twist about the forearm axis (SWING_TWIST_Y), so pronation/supination is spread over
# forearm -> cuff -> hand instead of showing as a broken wrist
TWIST_BONES = ["forearm_twist.L", "forearm_twist.R"]
TWIST_SHARE = 0.5
SECONDARY_BONES = {
    "SHINOBI": [f"tail{i}.{j}" for i in (1, 2) for j in (1, 2, 3, 4)],
    "SAINT": ["beard.1", "beard.2", "beard.3", "sleeve.L", "sleeve.R", "hem.L", "hem.R", "hem.B"],
}

FWD = Vector((0.0, -1.0, 0.0))     # character forward in rig space
BACK = Vector((0.0, 1.0, 0.0))
UP = Vector((0.0, 0.0, 1.0))
DOWN = Vector((0.0, 0.0, -1.0))
LEFT = Vector((1.0, 0.0, 0.0))     # character's left = +X

# reference vector for each bone's local +Z (projected perpendicular to the bone by align_roll).
# .R entries are the mirror images of .L (x -> -x) => Blender symmetric convention.
ZREF = {
    "hips": FWD, "spine": FWD, "chest": FWD, "neck": FWD, "head": FWD,
    "shoulder": FWD, "upper_arm": FWD, "forearm": FWD, "forearm_twist": FWD,
    "hand.L": -LEFT, "hand.R": LEFT,            # palm normal = medial at rest (palms face the thighs)
    "thigh": FWD, "shin": BACK, "foot": DOWN, "toe": DOWN,
    "tail": BACK, "beard": FWD, "sleeve": FWD, "hem": BACK,
}

# grip geometry: where the fist holds a handle, in the HAND bone frame (X, Y along the hand, Z = palm normal)
GRIP_IN_HAND = dict(y=0.070, z=0.026)   # fist centre in the hand frame, metres for a 1.72 m body (x H/1.72)
GRIP_BETA_DEG = 35.0                    # "handshake" grip: blade leaves the fist this far from the hand axis
                                        # towards the thumb; palm faces the blade flat, thumb on the mune side


def _lean_dir(deg):
    """Unit vector 'up, leaning forward by deg' in rig space (forward = -Y)."""
    a = math.radians(deg)
    return Vector((0.0, -math.sin(a), math.cos(a)))


def _frame_from_yz(y, zref):
    """Orthonormal (X, Y, Z) with Y = y and Z = zref projected perpendicular to y."""
    y = Vector(y).normalized()
    z = Vector(zref) - y * Vector(zref).dot(y)
    z.normalize()
    x = y.cross(z)
    return x, y, z


def _zref_for(name):
    base = name.split(".")[0]
    if name in ZREF:
        return Vector(ZREF[name])
    if base.startswith("tail"):
        return Vector(ZREF["tail"])
    if base.startswith("beard"):
        return Vector(ZREF["beard"])
    if base in ("sleeve", "hem"):
        return Vector(ZREF[base])
    return Vector(ZREF[base])


def rig_template(char):
    """Bone list for `char` ('SHINOBI'|'SAINT'): [dict(name, head, tail, parent, connect, deform, zref)] in rig
    space (A-pose, facing -Y, origin on the ground between the feet). Pure math, no bpy writes."""
    P = RIG_PARAMS[char]
    H = P["H"]
    s = H / REF_HEIGHT
    bones = []

    def add(name, head, tail, parent=None, connect=False, deform=True, zref=None):
        bones.append(dict(name=name, head=Vector(head), tail=Vector(tail), parent=parent, connect=connect,
                          deform=deform, zref=Vector(zref) if zref is not None else _zref_for(name)))

    # ---- spine chain, lengths scaled so the head top lands exactly on H with the lean (stoop)
    order = ["hips", "spine", "chest", "neck", "head"]
    vert = sum(P["seg"][b] * math.cos(math.radians(P["lean"][b])) for b in order)
    k = (H - P["z_hips"]) / vert
    p = Vector((0.0, 0.0, P["z_hips"]))
    spine_pts = {}
    for i, b in enumerate(order):
        q = p + _lean_dir(P["lean"][b]) * (P["seg"][b] * k)
        spine_pts[b] = (p.copy(), q.copy())
        add(b, p, q, parent=order[i - 1] if i else None, connect=bool(i))
        p = q

    # ---- chest frame (for the clavicles)
    c0, c1 = spine_pts["chest"]
    cx, cy, cz = _frame_from_yz(c1 - c0, FWD)
    clen = (c1 - c0).length

    def chest_pt(x, y, z):
        return c0 + cx * x + cy * (y * clen) + cz * z

    arm_info = {}
    for side, sx in (("L", 1.0), ("R", -1.0)):
        sc_in = chest_pt(sx * P["clav_inner"], 0.90, 0.045 * s)
        sh = chest_pt(sx * P["shoulder_half"], 0.985, -0.012 * s)
        add(f"shoulder.{side}", sc_in, sh, parent="chest")
        # A-pose arm: down-out by arm_down, elbow flexed forward by elbow_bend (>= 3 cm off the straight line)
        d = math.radians(P["arm_down"])
        u = Vector((sx * math.cos(d), 0.0, -math.sin(d)))
        ux, uy, uz = _frame_from_yz(u, FWD)
        f = (u * math.cos(math.radians(P["elbow_bend"])) + uz * math.sin(math.radians(P["elbow_bend"]))).normalized()
        el = sh + u * P["upper_arm"]
        wr = el + f * P["forearm"]
        kn = wr + f * P["hand"]
        add(f"upper_arm.{side}", sh, el, parent=f"shoulder.{side}", connect=True)
        add(f"forearm.{side}", el, wr, parent=f"upper_arm.{side}", connect=True)
        add(f"hand.{side}", wr, kn, parent=f"forearm.{side}", connect=True)
        add(f"forearm_twist.{side}", el + (wr - el) * 0.5, wr, parent=f"forearm.{side}")
        arm_info[side] = (sh, el, wr, kn)

    # ---- legs (knee flexed forward by knee_bend: knee >= 3 cm in front of the hip-ankle line)
    for side, sx in (("L", 1.0), ("R", -1.0)):
        hj = Vector((sx * P["hip_half"], 0.0, P["z_hipjoint"]))
        an = Vector((sx * P["ankle_half"], 0.0, P["z_ankle"]))
        D = (an - hj).length
        half = math.radians(P["knee_bend"]) * 0.5
        mid = (hj + an) * 0.5
        kn = mid + FWD * (0.5 * D * math.tan(half))
        fy, fz = P["foot"]
        ball = an + Vector((sx * 0.006 * s, -fy, -fz))
        ty, tz = P["toe"]
        tip = ball + Vector((sx * 0.003 * s, -ty, -tz))
        add(f"thigh.{side}", hj, kn, parent="hips")
        add(f"shin.{side}", kn, an, parent=f"thigh.{side}", connect=True)
        add(f"foot.{side}", an, ball, parent=f"shin.{side}", connect=True)
        add(f"toe.{side}", ball, tip, parent=f"foot.{side}", connect=True)

    # ---- weapon.R socket: at the right-fist grip centre, pointing along the held blade, -Z = edge
    wr, kn = arm_info["R"][2], arm_info["R"][3]
    hx, hy, hz = _frame_from_yz(kn - wr, _zref_for("hand.R"))
    gpos = wr + hy * (GRIP_IN_HAND["y"] * s) + hz * (GRIP_IN_HAND["z"] * s)
    bdir, edge = grip_axes_in_hand("R", hx, hy, hz)
    add("weapon.R", gpos, gpos + bdir * 0.12 * s, parent="hand.R", deform=False, zref=-edge)

    # ---- secondary chains
    h0, h1 = spine_pts["head"]
    hx_, hy_, hz_ = _frame_from_yz(h1 - h0, FWD)
    hlen = (h1 - h0).length
    if char == "SHINOBI":
        knot = h0 + hy_ * (0.50 * hlen) - hz_ * (0.5 * P["head_depth"])   # back of the head, headband height
        for i, sx in ((1, 1.0), (2, -1.0)):
            d = Vector((sx * 0.10, 0.36, -0.93)).normalized()
            p = knot + Vector((sx * 0.016, 0.0, 0.0))
            seglen = 0.55 / 4.0
            for j in range(1, 5):
                q = p + d * seglen
                add(f"tail{i}.{j}", p, q, parent="head" if j == 1 else f"tail{i}.{j - 1}", connect=j > 1)
                p = q
                d = (d + Vector((0, 0.03, -0.02))).normalized()        # gentle hang curve
    else:
        chin = h0 - hy_ * 0.035 * s + hz_ * 0.098 * s
        d = Vector((0.0, -0.22, -0.975)).normalized()
        p = chin
        for j, L in ((1, 0.115), (2, 0.110), (3, 0.095)):
            q = p + d * L
            add(f"beard.{j}", p, q, parent="head" if j == 1 else f"beard.{j - 1}", connect=j > 1)
            p = q
            d = (d + Vector((0.0, 0.10, 0.0))).normalized()          # follows the chest curve
        # hanging kimono/haori sleeve pouches (tamoto) and haori hem: secondary-motion chains (1 bone each)
        for side, sx in (("L", 1.0), ("R", -1.0)):
            el, wr = arm_info[side][1], arm_info[side][2]
            top = el + (wr - el) * 0.30 + DOWN * (0.03 * s)
            add(f"sleeve.{side}", top, top + DOWN * (0.25 * s), parent=f"forearm.{side}")
        zt, zb = 0.93 * s, 0.63 * s
        for nm, x, y in (("hem.L", 0.19, 0.03), ("hem.R", -0.19, 0.03), ("hem.B", 0.0, 0.17)):
            add(nm, Vector((x * s, y * s, zt)), Vector((x * s * 1.08, y * s * 1.15, zb)), parent="hips")
    return bones


def grip_axes_in_hand(side, hx, hy, hz):
    """(blade_dir, edge_dir) of a handle held in a fist, given the hand frame axes (rig-space Vectors).
    Handshake grip (both hands, mirror-symmetric): the blade leaves the fist between thumb and index finger,
    rotated GRIP_BETA_DEG from the hand's length axis (hy, wrist->knuckles) towards the thumb side
    (radial = +X on hand.R, -X on hand.L); the edge faces the little-finger side; the palm faces the flat.
    In chudan this gives: palm medial, thumb on top, knuckles forward, wrist behind the fist."""
    radial = hx if side == "R" else -hx
    b = math.radians(GRIP_BETA_DEG)
    bdir = (hy * math.cos(b) + radial * math.sin(b)).normalized()
    edge = (hy * math.sin(b) - radial * math.cos(b)).normalized()
    return bdir, edge


# =============================================================================================
# armature
# =============================================================================================
def _set_active(obj):
    vl = bpy.context.view_layer
    prev = vl.objects.active
    vl.objects.active = obj
    return prev


def build_rig(char, collection=None):
    """Create <char>_rig from rig_template(char): edit bones with rolls from ZREF (align_roll), rotation_mode
    'XYZ' on every pose bone, deform flags, display settings. Returns the armature object."""
    tpl = rig_template(char)
    name = f"{char}_rig"
    arm = bpy.data.armatures.new(name + "_data")
    arm.display_type = 'OCTAHEDRAL'
    rig = U.new_object(name, arm, collection)
    rig.show_in_front = False
    prev = _set_active(rig)
    bpy.ops.object.mode_set(mode='EDIT')
    try:
        eb = arm.edit_bones
        for b in tpl:
            e = eb.new(b["name"])
            e.head = b["head"]
            e.tail = b["tail"]
            e.use_deform = b["deform"]
            e.align_roll(b["zref"])
        for b in tpl:
            if b["parent"]:
                e = eb[b["name"]]
                e.parent = eb[b["parent"]]
                e.use_connect = b["connect"]
    finally:
        bpy.ops.object.mode_set(mode='OBJECT')
        if prev is not None:
            bpy.context.view_layer.objects.active = prev
    for pb in rig.pose.bones:
        pb.rotation_mode = 'XYZ'
    rig["char"] = char
    rig["rig_version"] = 1
    return rig


def bone_axes(rig, bone):
    """Rest-pose local axes (X, Y, Z) of `bone` in rig space (columns of bone.matrix_local)."""
    m = rig.data.bones[bone].matrix_local.to_3x3()
    return m.col[0].copy(), m.col[1].copy(), m.col[2].copy()


# =============================================================================================
# small geometry kit (numpy) for placeholder meshes
# =============================================================================================
def _circle_profile(n=10, phase=0.0):
    a = np.linspace(0.0, 2.0 * math.pi, n, endpoint=False) + phase
    return np.stack([np.cos(a), np.sin(a)], axis=1)


# katana cross-section (unit): x = flat direction (thickness), z = edge(-)/back(+) direction (width)
_BLADE_PROFILE = np.array([(0.0, -1.0), (0.55, -0.35), (0.62, 0.55), (0.30, 1.0),
                           (-0.30, 1.0), (-0.62, 0.55), (-0.55, -0.35)])
_DIAMOND_PROFILE = np.array([(0.0, -1.0), (1.0, 0.0), (0.0, 1.0), (-1.0, 0.0)])


def _loft(stations, profile, cap0=True, cap1=True):
    """Loft a 2D profile along stations [(centre, xaxis, zaxis, sx, sz)] (all rig/world/local Vectors).
    Returns (verts ndarray (N,3), faces list). Degenerate stations (sx=sz=0) collapse to a point (pointy tips)."""
    prof = np.asarray(profile, dtype=float)
    n = len(prof)
    verts, faces = [], []
    for c, ax, az, sx, sz in stations:
        c, ax, az = np.array(c), np.array(ax), np.array(az)
        for px, pz in prof:
            verts.append(c + ax * (px * sx) + az * (pz * sz))
    m = len(stations)
    for i in range(m - 1):
        a0, b0 = i * n, (i + 1) * n
        for j in range(n):
            j1 = (j + 1) % n
            faces.append((a0 + j, a0 + j1, b0 + j1, b0 + j))
    if cap0:
        faces.append(tuple(reversed(range(0, n))))
    if cap1:
        faces.append(tuple(range((m - 1) * n, m * n)))
    return np.array(verts), faces


def _capsule(p0, p1, r0, r1=None, n=10, ring=4, zdir=None, flat=1.0):
    """Tapered capsule from p0 to p1 (radii r0 -> r1) with hemispherical ends. flat<1 squashes the
    cross-section along zdir (elliptical limbs / torso). Returns (verts, faces)."""
    r1 = r0 if r1 is None else r1
    p0, p1 = Vector(p0), Vector(p1)
    d = (p1 - p0)
    L = d.length
    y = d.normalized()
    zr = Vector(zdir) if zdir is not None else (UP if abs(y.dot(UP)) < 0.9 else FWD)
    ax, _, az = _frame_from_yz(y, zr)
    st = []
    for k in range(ring, 0, -1):                      # start hemisphere
        phi = math.pi / 2 * k / ring
        st.append((p0 - y * (r0 * math.sin(phi)), ax, az, r0 * math.cos(phi), r0 * math.cos(phi) * flat))
    for t in (0.0, 0.5, 1.0):
        r = r0 + (r1 - r0) * t
        st.append((p0 + y * (L * t), ax, az, r, r * flat))
    for k in range(1, ring + 1):                      # end hemisphere
        phi = math.pi / 2 * k / ring
        st.append((p1 + y * (r1 * math.sin(phi)), ax, az, r1 * math.cos(phi), r1 * math.cos(phi) * flat))
    st[0] = (st[0][0], ax, az, 0.0, 0.0)
    st[-1] = (st[-1][0], ax, az, 0.0, 0.0)
    return _loft(st, _circle_profile(n), cap0=False, cap1=False)


def _box(center, size, axes=None):
    """Axis-aligned (or `axes`=(X,Y,Z) Vectors) box. Returns (verts, faces)."""
    c = np.array(center, dtype=float)
    sx, sy, sz = (np.array(size, dtype=float) * 0.5)
    X, Y, Z = (np.array(a, dtype=float) for a in (axes or ((1, 0, 0), (0, 1, 0), (0, 0, 1))))
    v = [c + X * i * sx + Y * j * sy + Z * k * sz for i in (-1, 1) for j in (-1, 1) for k in (-1, 1)]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return np.array(v), f


def _torus(center, axis, R, r, n=24, m=8, xref=None):
    """Torus around `axis` through `center` (major radius R, minor r)."""
    ax = Vector(axis).normalized()
    xr = Vector(xref) if xref is not None else (LEFT if abs(ax.dot(LEFT)) < 0.9 else FWD)
    X, _, Z = _frame_from_yz(ax, xr)       # Y = axis
    verts, faces = [], []
    for i in range(n):
        a = 2 * math.pi * i / n
        d = X * math.cos(a) + Z * math.sin(a)
        for j in range(m):
            b = 2 * math.pi * j / m
            verts.append(np.array(Vector(center) + d * (R + r * math.cos(b)) + ax * (r * math.sin(b))))
    for i in range(n):
        for j in range(m):
            i1, j1 = (i + 1) % n, (j + 1) % m
            faces.append((i * m + j, i1 * m + j, i1 * m + j1, i * m + j1))
    return np.array(verts), faces


class _MeshAcc:
    """Accumulate several (verts, faces) parts with per-part material index into one mesh."""

    def __init__(self):
        self.v, self.f, self.mi = [], [], []
        self.n = 0

    def add(self, part, mat_index=0):
        v, f = part
        self.v.append(np.asarray(v, dtype=float).reshape(-1, 3))
        for face in f:
            self.f.append(tuple(i + self.n for i in face))
            self.mi.append(mat_index)
        self.n += len(v)
        return self

    def mesh(self, name, materials=(), smooth=False):
        me = bpy.data.meshes.new(name)
        V = np.concatenate(self.v) if self.v else np.zeros((0, 3))
        me.from_pydata(V.tolist(), [], self.f)
        for m in materials:
            me.materials.append(m)
        if self.mi and len(me.polygons) == len(self.mi):
            me.polygons.foreach_set("material_index", self.mi)
        me.update()
        if smooth:
            me.shade_smooth()
        return me


def _mat(name, color, rough=0.6, metal=0.0, emission=None, strength=0.0):
    return U.new_material(name, color=color, rough=rough, metal=metal, emission=emission,
                          emission_strength=strength)


# =============================================================================================
# prop meshes, each built in its documented LOCAL frame
# =============================================================================================
def _katana_parts(D, part="all"):
    """Katana in the katana frame (origin = right-fist centre, +Y tip, -Z edge). part: 'all' | 'main' (all
    but the broken-off tip piece) | 'tip' (only the tip piece, SAINT). Returns _MeshAcc with material slots
    0 blade steel, 1 tsuka wrap, 2 tsuba/habaki fittings."""
    acc = _MeshAcc()
    yt, tt = D["grip_to_tsuba"], D["tsuba_thickness"]
    y0 = yt + tt * 0.5                                       # tsuba face = blade base (machi)
    L = D["blade_length"]
    X, Z = LEFT, UP                                          # local axes as Vectors (frame axes)
    brk = L - D.get("break_from_tip", 0.0) if D.get("break_from_tip") else None
    if part in ("all", "main"):
        # tsuka (oval), kashira cap
        ya, yb = yt - tt * 0.5 - D["tsuka_length"], yt - tt * 0.5
        st = [(Vector((0, y, 0)), X, Z, D["tsuka_depth"] * 0.5 * k, D["tsuka_width"] * 0.5 * k)
              for y, k in ((ya, 0.0), (ya + 0.004, 1.02), (ya + 0.02, 1.0), (yb - 0.01, 1.04), (yb, 1.04))]
        acc.add(_loft(st, _circle_profile(10), cap0=False), 1)
        # tsuba (oval disc) + habaki
        r = D["tsuba_diameter"] * 0.5
        st = [(Vector((0, yt - tt * 0.5, 0)), X, Z, r * 0.86, r), (Vector((0, yt + tt * 0.5, 0)), X, Z, r * 0.86, r)]
        acc.add(_loft(st, _circle_profile(16)), 2)
        hb = D["habaki_length"]
        st = [(Vector((0, y0, 0)), X, Z, D["blade_thickness"] * 0.75, D["blade_width"] * 0.56),
              (Vector((0, y0 + hb, 0)), X, Z, D["blade_thickness"] * 0.7, D["blade_width"] * 0.54)]
        acc.add(_loft(st, _BLADE_PROFILE), 2)
    # blade: stations along the chord, sori bulge towards the edge (-Z), kissaki tapers onto the axis
    n = 24
    ts = np.linspace(0.0, 1.0, n + 1)
    kiss = 0.045 / L
    st = []
    for t in ts:
        y = y0 + L * t
        if part == "main" and brk is not None and y > y0 + brk + 1e-6:
            continue
        if part == "tip" and brk is not None and y < y0 + brk - 1e-6:
            continue
        zoff = -D["sori"] * 4.0 * t * (1.0 - t)
        w = D["blade_width"] + (D["blade_width_tip"] - D["blade_width"]) * min(1.0, t / (1.0 - kiss))
        th = D["blade_thickness"] * (1.0 - 0.4 * t)
        if t > 1.0 - kiss:
            u = (1.0 - t) / kiss
            w *= math.sqrt(max(u, 0.0))
            th *= max(u, 0.0) ** 0.5
        st.append((Vector((0, y, zoff)), X, Z, th * 0.5, w * 0.5))
    if brk is not None and part in ("main", "tip"):
        tb = brk / L                                          # insert the exact break station
        zoff = -D["sori"] * 4.0 * tb * (1.0 - tb)
        w = D["blade_width"] + (D["blade_width_tip"] - D["blade_width"]) * tb
        s_brk = (Vector((0, y0 + brk, zoff)), X, Z, D["blade_thickness"] * (1 - 0.4 * tb) * 0.5, w * 0.5)
        st = (st + [s_brk]) if part == "main" else ([s_brk] + st)
    if part != "tip":
        st = [(Vector((0, y0 + D["habaki_length"] * 0.5, 0)), X, Z, st[0][3], st[0][4])] + st[1:]
    acc.add(_loft(st, _BLADE_PROFILE, cap0=True, cap1=True), 0)
    return acc


def _saya_part(D):
    """Scabbard in the saya frame (origin = koiguchi centre, +Y towards the kojiri, -Z = edge side)."""
    L = D["saya_length"]
    st = [(Vector((0, y, 0)), LEFT, UP, D["saya_depth"] * 0.5 * k, D["saya_width"] * 0.5 * k)
          for y, k in ((0.0, 1.0), (0.03, 1.0), (L * 0.6, 0.97), (L - 0.03, 0.9), (L, 0.55))]
    return _MeshAcc().add(_loft(st, _circle_profile(10)), 0)


def _spear_parts(D, sheath=False, origin_y=0.0):
    """Straight yari in the spear frame (origin = butt, +Y towards the tip, -Z = one blade edge); origin_y shifts
    the origin along +Y (SAINT_spear_world uses the CoM). Material slots: 0 steel, 1 vermilion shaft,
    2 fittings (black/brass), 3 lacquer sheath."""
    acc = _MeshAcc()
    L, bl, r = D["spear_length"], D["spear_blade_length"], D["spear_shaft_diameter"] * 0.5
    o = -origin_y
    ys = L - bl - 0.07
    acc.add(_loft([(Vector((0, o + y, 0)), LEFT, UP, r * k, r * k) for y, k in
                   ((0.0, 0.0), (0.004, 1.15), (0.07, 1.12))], _circle_profile(10), cap0=False), 2)
    acc.add(_loft([(Vector((0, o + y, 0)), LEFT, UP, r, r) for y in (0.07, ys)], _circle_profile(10)), 1)
    acc.add(_loft([(Vector((0, o + y, 0)), LEFT, UP, r * k, r * k) for y, k in
                   ((ys, 1.1), (L - bl, 1.05))], _circle_profile(10)), 2)
    w, th = 0.036 * 1.3, 0.012 * 1.3                        # readable (1.3x) su-yari blade
    st = []
    for t in np.linspace(0.0, 1.0, 9):
        k = 1.0 - t ** 1.6 if t < 1.0 else 0.0
        st.append((Vector((0, o + L - bl + bl * t, 0)), LEFT, UP, th * 0.5 * max(k, 0), w * 0.5 * max(k, 0)
                   * (0.75 + 0.25 * min(1.0, t * 6))))
    acc.add(_loft(st, _DIAMOND_PROFILE, cap1=False), 0)
    if sheath:
        acc.add(_sheath_part(D, o), 3)
    return acc


def _sheath_part(D, o=0.0):
    """Spear-blade sheath (verts, faces) in the spear frame shifted by o along Y."""
    L, sl, sd = D["spear_length"], D["spear_sheath_length"], D["spear_sheath_diameter"]
    st = [(Vector((0, o + y, 0)), LEFT, UP, sd * 0.30 * k, sd * 0.5 * k) for y, k in
          ((L - sl, 0.75), (L - sl + 0.02, 1.0), (L - 0.05, 1.0), (L + 0.02, 0.45))]
    return _loft(st, _circle_profile(12))


def _hat_parts(D, half=None, origin=(0.0, 0.0, 0.0)):
    """Sugegasa in the hat frame (origin = rim-plane centre, +Z up). half='A' (x>=0) | 'B' (x<=0) | None.
    `origin` shifts the object origin (halves use their centroid). Slot 0 straw, 1 dark band."""
    R, h = D["hat_diameter"] * 0.5, D["hat_height"]
    o = np.array(origin)
    rings = [(0.0, h), (0.10 * R, h * 0.93), (0.45 * R, h * 0.56), (0.85 * R, h * 0.13), (R, -0.012)]
    thick = 0.012
    if half is None:
        angs = list(np.linspace(0, 2 * math.pi, 28, endpoint=False))
        closed = True
    else:
        a0 = -math.pi / 2 if half == "A" else math.pi / 2
        angs = list(np.linspace(a0, a0 + math.pi, 15))
        closed = False
    na = len(angs)
    verts, faces = [], []
    for layer, dz in ((0, 0.0), (1, -thick)):
        for rr, z in rings:
            for a in angs:
                verts.append(np.array((rr * math.cos(a), rr * math.sin(a), z + dz)) - o)
    nr = len(rings)

    def vid(layer, i, j):
        return layer * nr * na + i * na + j
    jmax = na if closed else na - 1
    for i in range(nr - 1):
        for j in range(jmax):
            j1 = (j + 1) % na
            faces.append((vid(0, i, j), vid(0, i + 1, j), vid(0, i + 1, j1), vid(0, i, j1)))
            faces.append((vid(1, i, j), vid(1, i, j1), vid(1, i + 1, j1), vid(1, i + 1, j)))
    for j in range(jmax):                                       # rim edge
        j1 = (j + 1) % na
        faces.append((vid(0, nr - 1, j), vid(1, nr - 1, j), vid(1, nr - 1, j1), vid(0, nr - 1, j1)))
    if not closed:                                              # cut faces
        for j in (0, na - 1):
            for i in range(nr - 1):
                faces.append((vid(0, i, j), vid(1, i, j), vid(1, i + 1, j), vid(0, i + 1, j)))
    acc = _MeshAcc().add((np.array(verts), faces), 0)
    return acc


def _kunai_part(D, origin_y=0.0):
    """Kunai (origin at the blade/handle junction ~ CoM, +Y towards the point). Slot 0 steel, 1 wrap."""
    Lk = D["kunai_length"]
    o = -origin_y
    acc = _MeshAcc()
    acc.add(_torus(Vector((0, o - 0.095, 0)), LEFT, 0.014, 0.004, n=12, m=6), 0)
    acc.add(_loft([(Vector((0, o + y, 0)), LEFT, UP, 0.007, 0.008) for y in (-0.08, 0.0)], _circle_profile(8)), 1)
    bl = Lk - 0.1
    st = [(Vector((0, o + y, 0)), LEFT, UP, th, w) for y, th, w in
          ((0.0, 0.004, 0.012), (bl * 0.35, 0.0045, 0.020), (bl, 0.0, 0.0))]
    acc.add(_loft(st, _DIAMOND_PROFILE, cap1=False), 0)
    return acc


# =============================================================================================
# parenting helpers (rest-pose based, independent of the current pose / constraints)
# =============================================================================================
def _axes_matrix(origin, x, y, z):
    """4x4 from an origin and axis columns."""
    M = Matrix.Identity(4)
    for i in range(3):
        M[i][0], M[i][1], M[i][2], M[i][3] = x[i], y[i], z[i], origin[i]
    return M


def _bone_rest(rig, bone):
    """Rest head-frame of a bone in WORLD space (translation = bone head)."""
    return rig.matrix_world @ rig.data.bones[bone].matrix_local


def _bone_child(obj, rig, bone, local=None):
    """Parent obj to rig/bone so that its world matrix = (bone HEAD frame) @ local, in any pose.
    (Blender bone parenting uses the bone TAIL; we compensate with T(0,-length,0) in matrix_basis.)"""
    obj.parent = rig
    obj.parent_type = 'BONE'
    obj.parent_bone = bone
    obj.matrix_parent_inverse = Matrix.Identity(4)
    L = rig.data.bones[bone].length
    obj.matrix_basis = Matrix.Translation((0.0, -L, 0.0)) @ (local if local is not None else Matrix.Identity(4))
    return obj


def _bone_child_world(obj, rig, bone, world):
    """Parent obj to rig/bone keeping `world` as its REST-pose world matrix."""
    local = _bone_rest(rig, bone).inverted() @ world
    return _bone_child(obj, rig, bone, local)


def _obj_child(obj, parent, local=None):
    """Plain object parenting with an explicit local matrix (matrix_parent_inverse = identity)."""
    obj.parent = parent
    obj.parent_type = 'OBJECT'
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.matrix_basis = local if local is not None else Matrix.Identity(4)
    return obj


def _mesh_obj(name, acc, materials, collection, smooth=False):
    ob = bpy.data.objects.get(name)
    me = acc.mesh(name + "_mesh", materials=materials, smooth=smooth)
    if ob is None:
        ob = U.new_object(name, me, collection)
    else:
        ob.data = me
    return ob


def _empty(name, collection, display='PLAIN_AXES', size=0.05):
    ob = U.new_empty(name, (0, 0, 0), collection, display=display, size=size)
    ob.rotation_mode = 'XYZ'
    return ob


def _set_attach(free, attach_to, offset, bone=""):
    """Record where a FREE object sits while still attached (used by detach_matrix / snap_free)."""
    free["attach_to"] = attach_to
    free["attach_bone"] = bone
    free["attach_offset"] = [float(offset[i][j]) for i in range(4) for j in range(4)]


def _flat_to_matrix(vals):
    return Matrix([vals[0:4], vals[4:8], vals[8:12], vals[12:16]])


# =============================================================================================
# grip frames
# =============================================================================================
def _scale(char):
    return RIG_PARAMS[char]["H"] / REF_HEIGHT


def weapon_frame_in_hand(rig, side):
    """Matrix of the held-weapon frame (grip centre, +Y blade, -Z edge) expressed in the hand.<side> bone frame.
    For 'R' this is exactly weapon.R's rest relation; for 'L' the mirror-built virtual left-hand weapon frame."""
    char = rig["char"]
    hb = rig.data.bones[f"hand.{side}"]
    if side == "R":
        return hb.matrix_local.inverted() @ rig.data.bones["weapon.R"].matrix_local
    s = _scale(char)
    hx, hy, hz = bone_axes(rig, "hand.L")
    gpos = hb.head_local + hy * (GRIP_IN_HAND["y"] * s) + hz * (GRIP_IN_HAND["z"] * s)
    bdir, edge = grip_axes_in_hand("L", hx, hy, hz)
    x, y, z = _frame_from_yz(bdir, -edge)
    return hb.matrix_local.inverted() @ _axes_matrix(gpos, x, y, z)


# spear left-hand grip: the front hand is rolled about the shaft so the palm faces up/in (support grip)
SPEAR_LEFT_ROLL_DEG = -45.0                          # measured: min wrist strain in the spear guard (p6_scan)
# Elbow poles. Hand component: a point behind the WRIST target along -Y_hand (hand frame: X radial(R)/ulnar(L),
# Y wrist->knuckles, Z palm) = where the elbow sits for a straight wrist -> the elbow plane follows the hand
# (low wrist swing) but is undefined when the arm is straight. Body component: a fixed chest-space point
# out/back/down of the shoulder -> defined twist on straight arms, but big wrist swings in guards.
# 'hybrid' blends both (see _make_pole); per pole KIND: 'R' sword arm, 'L' katana two-hand grip, 'L_spear' spear
# front hand, 'L_saya' left hand on the scabbard. Measured in out/dev/characters/probe/p8_polescan.py (R) and
# p17_leftpole.py (L kinds).
POLE_LOCAL = {"R": (-0.10, -0.40, -0.10), "L": (0.10, -0.40, -0.10), "L_spear": (0.10, -0.40, -0.10),
              "L_saya": (0.10, -0.40, -0.10)}            # metres x H/1.72 in the wrist-target frame
POLE_LOCAL_R = POLE_LOCAL["R"]                        # (compat)
POLE_MODE = "hybrid"                                  # 'hybrid' | 'hand' | 'chest'
POLE_OFFSET = dict(out=0.33, back=0.10, down=0.55)    # body pole relative to the shoulder joint (x s, chest space)
POLE_BLEND = {"R": 0.4, "L": 0.6, "L_spear": 0.4, "L_saya": 0.4}   # hybrid: weight of the body pole
# 'L' 0.6 (was 0.4): the two-handed kesa follow-through snapped the left elbow 43/70 mm per 2 deg of swing at 0.4;
# at 0.6 the left elbow-plane step is <= 2 deg / 2 deg and <= 9 mm on all test arcs (p19_leftpole.py)
POLE_ANGLE_DEG = -90.0                                # verified in tests (elbow bends towards the pole)


def _make_pole(name, side, char, rig, socket, col, kind=None, override=None):
    """Create the IK elbow pole `name` (+ helpers) for POLE_MODE and pole kind ('R', 'L', 'L_spear', 'L_saya'):
      'hand'   -> child of the wrist-target socket at POLE_LOCAL[kind];
      'chest'  -> child of the chest bone at POLE_OFFSET from the shoulder;
      'hybrid' -> `name` (child of the rig) = lerp(<name>_hand, <name>_body, POLE_BLEND[kind]) through two Copy
                  Location constraints: wherever one helper is degenerate (on the shoulder-wrist line) the elbow
                  plane falls back to the other.
    override: the side's shared <C>_elbow_<side> empty -> a third Copy Location 'POLE_override' (influence 0; keyed by
    key_elbow / auto_elbow) that puts the pole exactly on it. Returns {name: obj, ...helpers}."""
    kind = kind or side
    objs = {}
    s = _scale(char)
    sx = 1.0 if side == "L" else -1.0
    sh = rig.data.bones[f"upper_arm.{side}"].head_local
    body_w = rig.matrix_world @ Matrix.Translation(
        sh + Vector((sx * POLE_OFFSET["out"], POLE_OFFSET["back"], -POLE_OFFSET["down"])) * s)
    pole = _empty(name, col, display='SPHERE', size=0.04)
    objs[name] = pole
    local = Matrix.Translation(Vector(POLE_LOCAL[kind]) * s)
    if POLE_MODE == "hand":
        _obj_child(pole, socket, local)
    elif POLE_MODE == "chest":
        _bone_child_world(pole, rig, "chest", body_w)
    else:
        ph = _empty(name + "_hand", col, display='PLAIN_AXES', size=0.02)
        _obj_child(ph, socket, local)
        pb = _empty(name + "_body", col, display='PLAIN_AXES', size=0.02)
        _bone_child_world(pb, rig, "chest", body_w)
        _obj_child(pole, rig)
        for tgt, infl, nm in ((ph, 1.0, "POLE_hand"), (pb, POLE_BLEND[kind], "POLE_body")):
            c = pole.constraints.new('COPY_LOCATION')
            c.name = nm
            c.target = tgt
            c.target_space = 'WORLD'
            c.owner_space = 'WORLD'
            c.influence = infl
        objs[ph.name], objs[pb.name] = ph, pb
    if override is not None:
        c = pole.constraints.new('COPY_LOCATION')
        c.name = "POLE_override"
        c.target = override
        c.target_space = 'WORLD'
        c.owner_space = 'WORLD'
        c.influence = 0.0
    pole["pole_kind"] = kind
    return objs


def _pole_local(side, char, kind=None):
    """(compat) hand-pole offset matrix for a pole kind."""
    return Matrix.Translation(Vector(POLE_LOCAL[kind or side]) * _scale(char))


# =============================================================================================
# per-character construction
# =============================================================================================
PAL = config.PALETTE
SAYA_PLACE = {   # koiguchi position (rig space, rest) and scabbard direction; worn edge-up through the obi
    "SHINOBI": dict(pos=(0.118, -0.118, 0.985), dir=(0.26, 1.0, -0.58)),
    "SAINT": dict(pos=(0.135, -0.140, 1.050), dir=(0.26, 1.0, -0.58)),
}
# slung spear: point where the shaft crosses the back, its distance from the butt, direction butt -> head.
# Moved 3 cm back and tilted back at the top (was cross y 0.25, dir (-0.34, 0.07, 0.94)) so the S04 head lift under
# the hat clears the sheath: hat clearance 5.6 / 4.4 / 3.5 cm at 20 / 25 / 30 deg lift (was 1.0 / -0.2 / -1.1),
# shaft axis still 5 cm off the placeholder haori (p21_slung.py).
SPEAR_SLUNG = dict(cross=(0.0, 0.28, 1.36), cross_at=1.22, dir=(-0.34, 0.14, 0.93))


def _prop_materials():
    return dict(
        steel=_mat("PROP_steel", PAL["steel"], rough=0.25, metal=1.0),
        wrap=_mat("PROP_tsuka_wrap", (0.02, 0.02, 0.025), rough=0.8),
        fitting=_mat("PROP_fitting", (0.18, 0.13, 0.06), rough=0.4, metal=0.8),
        lacquer=_mat("PROP_lacquer", PAL["lacquer_black"], rough=0.25),
        shaft=_mat("PROP_spear_shaft", PAL["spear_shaft"], rough=0.35),
        straw=_mat("PROP_straw", PAL["straw"], rough=0.9),
        band=_mat("PROP_hat_band", (0.05, 0.035, 0.02), rough=0.8),
        haori=_mat("SAINT_haori_ph", PAL["saint_haori"], rough=0.9),
        tasuki=_mat("SAINT_tasuki_ph", PAL["tasuki"], rough=0.9),
        cord=_mat("SAINT_cord_ph", PAL["beard_cord"], rough=0.7),
    )


SAYA_LEFT_ROLL_DEG = -15.0    # roll of the left fist about the saya axis: measured optimum (p18_sayaroll.py)


def saya_fist_matrix(char):
    """Left-fist frame (grip centre, +Y = 'blade' axis of the fist = towards the koiguchi, -Z = little-finger side)
    in the SAYA frame: saya_grip_L behind the mouth on the saya axis, rolled SAYA_LEFT_ROLL_DEG."""
    d = DIMS[char]["saya_grip_L"]
    return (Matrix.Translation((0.0, d, 0.0)) @ Matrix.Rotation(math.radians(SAYA_LEFT_ROLL_DEG), 4, 'Y')
            @ Matrix.Rotation(math.pi, 4, 'X'))


def _build_controllers(char, rig, col):
    """<C>_sword_ctrl (+ internal _wrist child), the elbow override empties <C>_elbow_R/_L (children of the rig,
    keyed by key_elbow / auto_elbow) and the right elbow pole (child of the wrist target)."""
    objs = {}
    ctrl = _empty(f"{char}_sword_ctrl", col, display='ARROWS', size=0.12)
    _obj_child(ctrl, rig, rig.data.bones["weapon.R"].matrix_local.copy())       # rest = weapon.R rest frame
    ctrl.rotation_mode = 'XYZ'
    wrist = _empty(f"{char}_sword_ctrl_wrist", col, display='PLAIN_AXES', size=0.03)
    _obj_child(wrist, ctrl, weapon_frame_in_hand(rig, "R").inverted())
    wrist.hide_select = True
    objs[ctrl.name], objs[wrist.name] = ctrl, wrist
    for side in ("R", "L"):
        el = _empty(f"{char}_elbow_{side}", col, display='CUBE', size=0.03)
        B = rig.data.bones
        _obj_child(el, rig, Matrix.Translation(B[f"forearm.{side}"].head_local
                                               + (B[f"forearm.{side}"].head_local - B[f"upper_arm.{side}"].head_local) * 0.5))
        objs[el.name] = el
    objs.update(_make_pole(f"{char}_pole_R", "R", char, rig, wrist, col, kind="R", override=objs[f"{char}_elbow_R"]))
    return objs


def _build_katana(char, rig, col, M):
    """Katana (in hand + sheathed), saya, sockets and (SAINT) the break pieces."""
    D = DIMS[char]
    objs = {}
    mats = [M["steel"], M["wrap"], M["fitting"]]
    yt, tt = D["grip_to_tsuba"], D["tsuba_thickness"]
    y0 = yt + tt * 0.5
    saint = char == "SAINT"
    kh = _mesh_obj(f"{char}_katana_hand", _katana_parts(D, "main" if saint else "all"), mats, col)
    _bone_child(kh, rig, "weapon.R")
    objs[kh.name] = kh
    for nm, y in ((f"{char}_katana_tip", y0 + D["blade_length"]), (f"{char}_katana_base", y0 + D["habaki_length"])):
        e = _empty(nm, col, size=0.03)
        _obj_child(e, kh, Matrix.Translation((0.0, y, 0.0)))
        objs[nm] = e
    # left-hand grip socket: the LEFT WRIST frame for a fist on the tsuka end (IK_grip target)
    gl = _empty(f"{char}_grip_L", col, display='PLAIN_AXES', size=0.04)
    _obj_child(gl, kh, Matrix.Translation((0.0, -D["hand_spacing"], 0.0)) @ weapon_frame_in_hand(rig, "L").inverted())
    objs[gl.name] = gl
    elbow_L = bpy.data.objects[f"{char}_elbow_L"]
    objs.update(_make_pole(f"{char}_pole_L", "L", char, rig, gl, col, kind="L", override=elbow_L))
    # scabbard at the left hip + the sheathed copy of the katana
    sp = SAYA_PLACE[char]
    x, y, z = _frame_from_yz(Vector(sp["dir"]), DOWN)       # -Z (edge) points up: worn edge-up
    saya = _mesh_obj(f"{char}_saya", _saya_part(D), [M["lacquer"]], col)
    _bone_child_world(saya, rig, "hips", rig.matrix_world @ _axes_matrix(Vector(sp["pos"]), x, y, z))
    saya["rest_basis"] = [float(saya.matrix_basis[i][j]) for i in range(4) for j in range(4)]
    objs[saya.name] = saya
    # left hand on the scabbard (iai: thumb on the tsuba): LEFT-WRIST frame of a fist around the saya saya_grip_L
    # behind the koiguchi, the fist's 'blade' axis pointing at the mouth (thumb side forward, on the edge side)
    sg = _empty(f"{char}_saya_grip_L", col, display='PLAIN_AXES', size=0.04)
    _obj_child(sg, saya, saya_fist_matrix(char) @ weapon_frame_in_hand(rig, "L").inverted())
    objs[sg.name] = sg
    objs.update(_make_pole(f"{char}_pole_L_saya", "L", char, rig, sg, col, kind="L_saya", override=elbow_L))
    if saint:
        ks = _mesh_obj(f"{char}_katana_sheathed", _katana_parts(D, "all"), mats, col)
    else:
        ks = U.new_object(f"{char}_katana_sheathed", kh.data, col)            # shares the in-hand mesh
    _obj_child(ks, saya, Matrix.Translation((0.0, -y0, 0.0)))
    objs[ks.name] = ks
    if saint:
        brk = y0 + D["blade_length"] - D["break_from_tip"]
        tipm = _mesh_obj("SAINT_katana_hand_tip", _katana_parts(D, "tip"), mats, col)
        _obj_child(tipm, kh)
        objs[tipm.name] = tipm
        eb = _empty("SAINT_katana_break", col, size=0.03)
        _obj_child(eb, kh, Matrix.Translation((0.0, brk, 0.0)))
        objs[eb.name] = eb
        ymid = brk + D["break_from_tip"] * 0.5
        acc = _katana_parts(D, "tip")
        acc.v = [v - np.array((0.0, ymid, 0.0)) for v in acc.v]
        free = _mesh_obj("SAINT_katana_tip_broken", acc, mats, col)
        off = Matrix.Translation((0.0, ymid, 0.0))
        _set_attach(free, kh.name, off)
        free.matrix_world = _bone_rest(rig, "weapon.R") @ off
        objs[free.name] = free
    return objs


def _build_spear(rig, col, M, G_L):
    """SAINT spear: slung (with sheath, on the chest), in-hand (+ sockets, grip offsets), world, sheath_world."""
    D = DIMS["SAINT"]
    objs = {}
    mats = [M["steel"], M["shaft"], M["fitting"], M["lacquer"]]
    # slung on the back: butt low-left, sheathed head above the right shoulder
    d = Vector(SPEAR_SLUNG["dir"]).normalized()
    x, y, z = _frame_from_yz(d, BACK)
    butt = Vector(SPEAR_SLUNG["cross"]) - d * SPEAR_SLUNG["cross_at"]
    sl = _mesh_obj("SAINT_spear_slung", _spear_parts(D, sheath=True), mats, col)
    _bone_child_world(sl, rig, "chest", rig.matrix_world @ _axes_matrix(butt, x, y, z))
    objs[sl.name] = sl
    # in hand: origin = butt, hung under weapon.R at -grip_R so the right fist sits at grip_R
    sh = _mesh_obj("SAINT_spear_hand", _spear_parts(D), mats, col)
    _bone_child(sh, rig, "weapon.R", Matrix.Translation((0.0, -D["spear_grip_R"], 0.0)))
    objs[sh.name] = sh
    for nm, yy in (("SAINT_spear_tip", D["spear_length"]), ("SAINT_spear_base", D["spear_length"] - D["spear_blade_length"])):
        e = _empty(nm, col, size=0.03)
        _obj_child(e, sh, Matrix.Translation((0.0, yy, 0.0)))
        objs[nm] = e
    gls = _empty("SAINT_grip_L_spear", col, display='PLAIN_AXES', size=0.04)
    _obj_child(gls, sh, Matrix.Translation((0.0, D["spear_grip_L"], 0.0))
               @ Matrix.Rotation(math.radians(SPEAR_LEFT_ROLL_DEG), 4, 'Y') @ G_L.inverted())
    # the socket is the left WRIST frame: its location.y differs from the fist centre along the shaft by this
    # constant (set_spear_grip / spear_grip / apply_pose convert fist <-> socket with it)
    gls["fist_offset"] = float(gls.location.y - D["spear_grip_L"])
    objs[gls.name] = gls
    objs.update(_make_pole("SAINT_pole_L_spear", "L", "SAINT", rig, gls, col, kind="L_spear",
                           override=bpy.data.objects["SAINT_elbow_L"]))
    # free copies
    wm = _mesh_obj("SAINT_spear_world", _spear_parts(D, origin_y=D["spear_com"]), mats, col)
    off = Matrix.Translation((0.0, D["spear_com"], 0.0))
    _set_attach(wm, sh.name, off)
    objs[wm.name] = wm
    yc = D["spear_length"] - D["spear_sheath_length"] * 0.5 + 0.01
    sw = _mesh_obj("SAINT_spear_sheath_world", _MeshAcc().add(_sheath_part(D, -yc), 0), [M["lacquer"]], col)
    off = Matrix.Translation((0.0, yc, 0.0))
    _set_attach(sw, sl.name, off)
    objs[sw.name] = sw
    return objs


def _build_saint_costume_props(rig, col, M):
    """Hat (+ halves), beard cord (+ cut copy), tasuki, thrown haori (the skinned haori is built with the
    placeholder body because the meshes lane replaces it)."""
    D = DIMS["SAINT"]
    objs = {}
    hb = rig.data.bones["head"]
    hx, hy, hz = bone_axes(rig, "head")
    top = rig.matrix_world @ hb.tail_local
    hat_w = _axes_matrix(top - hy * D["hat_seat"], hx, -hz, hy)
    hat = _mesh_obj("SAINT_hat", _hat_parts(D), [M["straw"], M["band"]], col)
    _bone_child_world(hat, rig, "head", hat_w)
    hat["rest_basis"] = [float(hat.matrix_basis[i][j]) for i in range(4) for j in range(4)]
    objs[hat.name] = hat
    for half, sx in (("A", 1.0), ("B", -1.0)):
        o = (sx * 0.115, 0.0, 0.03)
        h = _mesh_obj(f"SAINT_hat_half_{half}", _hat_parts(D, half=half, origin=o), [M["straw"], M["band"]], col)
        off = Matrix.Translation(o)
        _set_attach(h, hat.name, off)
        h.matrix_world = hat_w @ off
        objs[h.name] = h
    # beard cord around the middle of beard.3
    b3 = rig.data.bones["beard.3"]
    cord_local = Matrix.Translation((0.0, b3.length * 0.45, 0.0))
    # torus axis follows the bone's +Y (cord wraps the beard)
    acc = _MeshAcc().add(_torus(Vector((0, 0, 0)), Vector((0, 1, 0)), D["beard_cord_diameter"] * 0.5, 0.0065, n=16, m=6))
    cord = _mesh_obj("SAINT_beard_cord", acc, [M["cord"]], col)
    _bone_child(cord, rig, "beard.3", cord_local)
    objs[cord.name] = cord
    acc2 = _MeshAcc().add(_torus(Vector((0, 0, 0)), Vector((0, 1, 0)), D["beard_cord_diameter"] * 0.5, 0.0065, n=16, m=6))
    cut = _mesh_obj("SAINT_beard_cord_cut", acc2, [M["cord"]], col)
    _set_attach(cut, cord.name, Matrix.Identity(4))
    cut.matrix_world = _bone_rest(rig, "beard.3") @ cord_local
    objs[cut.name] = cut
    # tasuki: two crossed loops around the chest (X on the back), rigid on the chest bone
    c0 = rig.data.bones["chest"].head_local
    c1 = rig.data.bones["chest"].tail_local
    cx, cy, cz = bone_axes(rig, "chest")
    ctr = c0 + (c1 - c0) * 0.55
    acc = _MeshAcc()
    for sgn in (1.0, -1.0):
        ax = (cy * math.cos(math.radians(38)) + cx * (sgn * math.sin(math.radians(38)))).normalized()
        v, f = _torus(ctr, ax, 1.0, 0.009, n=28, m=5, xref=cz)
        v = np.array(v)
        rel = v - np.array(ctr)
        # squash the loop into a torso-shaped ellipse (wide, shallow)
        X = np.array(cx); Z = np.array(cz)
        px, pz = rel @ X, rel @ Z
        rel = rel - np.outer(px, X) * (1 - 0.20) - np.outer(pz, Z) * (1 - 0.16)
        acc.add((np.array(ctr) + rel, f))
    tas = _mesh_obj("SAINT_tasuki", acc, [M["tasuki"]], col)
    _bone_child_world(tas, rig, "chest", rig.matrix_world.copy())
    objs[tas.name] = tas
    # thrown haori (free cloth): T-shaped wavy sheet, origin at its centre, local Z = sheet normal
    W, Hh, sw = 0.64, 0.95, 0.34
    nx, ny = 16, 12
    verts, faces = [], []
    for j in range(ny + 1):
        for i in range(nx + 1):
            u, v = i / nx, j / ny
            xx = (u - 0.5) * (W + 2 * sw)
            yy = (v - 0.5) * Hh
            if abs(xx) > W * 0.5 and v < 0.55:              # sleeves only on the upper part
                yy = 0.5 * Hh - (1 - v) * 0.45 * Hh * 0.55
            zz = 0.03 * math.sin(u * 7.0) * math.cos(v * 5.0)
            verts.append((xx, yy, zz))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + 1, a + nx + 2, a + nx + 1))
    ht = _mesh_obj("SAINT_haori_thrown", _MeshAcc().add((np.array(verts), faces)), [M["haori"]], col)
    _set_attach(ht, rig.name, Matrix.Translation((0.0, 0.0, 0.0)), bone="chest")
    ht.matrix_world = _bone_rest(rig, "chest")
    objs[ht.name] = ht
    objs.update(build_placeholder_haori(rig, col))       # always present (meshes lane replaces it)
    return objs


def _build_kunai(rig, col, M, G_L):
    D = DIMS["SHINOBI"]
    objs = {}
    off = G_L @ Matrix.Translation((0.0, 0.04, 0.0))       # held in the LEFT fist, point along the fist axis
    for i in (1, 2, 3):
        k = _mesh_obj(f"SHINOBI_kunai_{i}", _kunai_part(D), [M["steel"], M["wrap"]], col)
        _set_attach(k, rig.name, off, bone="hand.L")
        k.matrix_world = _bone_rest(rig, "hand.L") @ off
        objs[k.name] = k
    kh = _mesh_obj("SHINOBI_kunai_hand", _kunai_part(D), [M["steel"], M["wrap"]], col)
    _bone_child(kh, rig, "hand.L", off)
    objs[kh.name] = kh
    return objs


LEFT_ALT_TARGETS = {"saya": ("{c}_saya_grip_L", "{c}_pole_L_saya"), "spear": ("SAINT_grip_L_spear", "SAINT_pole_L_spear")}


def _build_left_switch(char, rig, col, objs):
    """<C>_hand_L_target / <C>_pole_L_alt: switcher empties (children of the rig) that copy the chosen left-hand
    socket / its pole through Copy Transforms / Copy Location constraints 'TGT_saya', 'TGT_spear' (SAINT)
    (influence 0/1, keyed CONSTANT by set_left_hand). They feed the single IK_alt + COPYROT_alt pair."""
    out = {}
    tg = _empty(f"{char}_hand_L_target", col, display='PLAIN_AXES', size=0.03)
    _obj_child(tg, rig)
    pl = _empty(f"{char}_pole_L_alt", col, display='SPHERE', size=0.03)
    _obj_child(pl, rig)
    for key, (tn, pn) in LEFT_ALT_TARGETS.items():
        tn, pn = tn.format(c=char), pn.format(c=char)
        if tn not in objs or pn not in objs:
            continue
        c = tg.constraints.new('COPY_TRANSFORMS')
        c.name = f"TGT_{key}"
        c.target = objs[tn]
        c.target_space = c.owner_space = 'WORLD'
        c.influence = 0.0
        c = pl.constraints.new('COPY_LOCATION')
        c.name = f"TGT_{key}"
        c.target = objs[pn]
        c.target_space = c.owner_space = 'WORLD'
        c.influence = 0.0
    out[tg.name], out[pl.name] = tg, pl
    return out


def _add_constraints(char, rig, objs):
    """Sword arm IK + Copy Rotation, left-hand grip IK(s) + Copy Rotation(s); all influences start at 0 (FK)."""
    pbs = rig.pose.bones

    def ik(bone, name, target, pole):
        c = pbs[bone].constraints.new('IK')
        c.name = name
        c.target = target
        c.pole_target = pole
        c.pole_angle = math.radians(POLE_ANGLE_DEG)
        c.chain_count = 2
        c.use_tail = True
        c.use_stretch = False
        c.iterations = 500
        c.influence = 0.0
        return c

    def cr(bone, name, target):
        c = pbs[bone].constraints.new('COPY_ROTATION')
        c.name = name
        c.target = target
        c.owner_space = 'WORLD'
        c.target_space = 'WORLD'
        c.mix_mode = 'REPLACE'
        c.influence = 0.0
        return c

    ik("forearm.R", "IK_sword", objs[f"{char}_sword_ctrl_wrist"], objs[f"{char}_pole_R"])
    cr("hand.R", "COPYROT_sword", objs[f"{char}_sword_ctrl_wrist"])
    ik("forearm.L", "IK_grip", objs[f"{char}_grip_L"], objs[f"{char}_pole_L"])
    cr("hand.L", "COPYROT_grip", objs[f"{char}_grip_L"])
    # Blender's IK solver only honours the first TWO IK constraints on a bone (measured: a 3rd is ignored), so every
    # other left-hand target goes through ONE IK_alt aimed at a switcher empty that copies the chosen socket
    ik("forearm.L", "IK_alt", objs[f"{char}_hand_L_target"], objs[f"{char}_pole_L_alt"])
    cr("hand.L", "COPYROT_alt", objs[f"{char}_hand_L_target"])
    # forearm twist helpers: TWIST_SHARE of the hand's twist (swing-twist decomposition about Y, local spaces)
    for side in ("L", "R"):
        c = pbs[f"forearm_twist.{side}"].constraints.new('TRANSFORM')
        c.name = "TWIST_from_hand"
        c.target = rig
        c.subtarget = f"hand.{side}"
        c.owner_space = 'LOCAL'
        c.target_space = 'LOCAL'
        c.map_from = 'ROTATION'
        c.from_rotation_mode = 'SWING_TWIST_Y'
        c.map_to = 'ROTATION'
        c.map_to_x_from, c.map_to_y_from, c.map_to_z_from = 'X', 'Y', 'Z'
        c.from_min_y_rot, c.from_max_y_rot = -math.pi, math.pi
        c.to_min_y_rot, c.to_max_y_rot = -math.pi * TWIST_SHARE, math.pi * TWIST_SHARE
        c.mix_mode_rot = 'REPLACE'
        c.influence = 1.0


# =============================================================================================
# build
# =============================================================================================
def _prefix(rig_or_name):
    """'SHINOBI' / 'SAINT' from a rig object or a name like 'SAINT', 'SAINT_rig'."""
    n = rig_or_name if isinstance(rig_or_name, str) else rig_or_name.name
    for c in CHARS:
        if n == c or n.startswith(c + "_"):
            return c
    raise ValueError(f"not a character rig/name: {n!r}")


def get_rig(rig_or_name):
    """Resolve a rig object from a rig or a character name."""
    if not isinstance(rig_or_name, str):
        return rig_or_name
    return bpy.data.objects[f"{_prefix(rig_or_name)}_rig"]


def build(meshes="auto", place=True):
    """Build both characters: rigs, controllers, poles, props, sockets, constraints and meshes.

    meshes: 'auto'  -> character_meshes.build_meshes(rigs, props, DIMS) if that module exists, else placeholders
            'placeholder' -> always the flat-coloured placeholder bodies
            'none'  -> no body meshes (props keep their placeholder geometry)
    place:  put the rigs at their first-appearance marks (config.SAINT_START / SHINOBI_START + HANDOFF facing).
    Default state (NOT keyed): katana sheathed, spear slung, haori on, tasuki hidden, hat on, all free pieces
    hidden, arms in FK (every IK / Copy Rotation influence 0), two-hand off.
    Idempotent: when both rigs of a COMPLETE earlier build exist in the file, they are returned unchanged
    (reused=True, props = the objects of the CHAR_* collections); a partial build (some SHINOBI_* / SAINT_*
    objects without a complete rig) raises RuntimeError before anything is created.
    Returns dict(shinobi=rig, saint=rig, props={name: obj}, dims=DIMS)."""
    prev = _existing_build()
    if prev is not None:
        return prev
    t0 = time.time()
    root = U.ensure_collection(COLLECTION)
    M = _prop_materials()
    rigs, props = {}, {}
    for char in CHARS:
        col = U.ensure_collection(f"CHAR_{char}", parent=root)
        rig = build_rig(char, col)
        rigs[char] = rig
        objs = _build_controllers(char, rig, col)
        objs.update(_build_katana(char, rig, col, M))
        G_L = weapon_frame_in_hand(rig, "L")
        if char == "SAINT":
            objs.update(_build_spear(rig, col, M, G_L))
            objs.update(_build_saint_costume_props(rig, col, M))
        else:
            objs.update(_build_kunai(rig, col, M, G_L))
        objs.update(_build_left_switch(char, rig, col, objs))
        _add_constraints(char, rig, objs)
        props.update(objs)
    # body meshes
    mode = meshes
    if meshes == "auto":
        try:
            import character_meshes  # noqa: F401
            mode = "final"
        except ImportError:
            mode = "placeholder"
    if mode == "final":
        import character_meshes
        character_meshes.build_meshes(rigs, props, DIMS)
    elif mode == "placeholder":
        for char in CHARS:
            props.update(build_placeholder_body(char, rigs[char], U.ensure_collection(f"CHAR_{char}")))
    if place:
        h = config.HANDOFF[min(config.HANDOFF)]
        for char, key, start in (("SHINOBI", "shinobi", config.SHINOBI_START), ("SAINT", "saint", config.SAINT_START)):
            rigs[char].location = (start[0], start[1], 0.0)
            rigs[char].rotation_euler = (0.0, 0.0, math.radians(h[key]["facing"]))
    apply_default_state(rigs, props)
    bpy.context.view_layer.update()
    for ob in props.values():                     # hidden free pieces start on their attached counterparts
        if "attach_offset" in ob:
            ob.matrix_world = detach_matrix(ob, None)
    for r in rigs.values():
        r["build_seconds"] = time.time() - t0
        r["mesh_mode"] = mode
        r["build_complete"] = 1
    return dict(shinobi=rigs["SHINOBI"], saint=rigs["SAINT"], props=props, dims=DIMS)


def _existing_build():
    """The result of an earlier complete build() in this file, None when there is none; RuntimeError for a
    partial one (so a second build() never half-creates '.001' duplicates)."""
    rigs = {c: bpy.data.objects.get(f"{c}_rig") for c in CHARS}
    if all(r is not None and r.get("build_complete") for r in rigs.values()):
        props = {}
        for c in CHARS:
            col = bpy.data.collections.get(f"CHAR_{c}")
            if col is not None:
                props.update({o.name: o for o in col.all_objects if o.name != f"{c}_rig"})
        return dict(shinobi=rigs["SHINOBI"], saint=rigs["SAINT"], props=props, dims=DIMS, reused=True)
    stray = sorted(o.name for o in bpy.data.objects if o.name.startswith(tuple(c + "_" for c in CHARS)))
    if stray:
        raise RuntimeError("characters.build(): the file already holds a partial character build "
                           f"({len(stray)} objects, e.g. {stray[:4]}); clear the scene first (bl_util.clear_scene())")
    return None




def apply_default_state(rigs, props):
    """Un-keyed start-of-film state (see build())."""
    hidden = ["SAINT_katana_tip_broken", "SAINT_hat_half_A", "SAINT_hat_half_B", "SAINT_tasuki",
              "SAINT_haori_thrown", "SAINT_beard_cord_cut", "SAINT_spear_hand", "SAINT_spear_world",
              "SAINT_spear_sheath_world", "SHINOBI_kunai_1", "SHINOBI_kunai_2", "SHINOBI_kunai_3",
              "SHINOBI_kunai_hand", "SHINOBI_katana_hand", "SAINT_katana_hand", "SAINT_katana_hand_tip"]
    for n in hidden:
        if n in props:
            props[n].hide_render = props[n].hide_viewport = True
    for r in rigs.values():
        r["katana_state"] = 0      # 0 sheathed, 1 drawn, 2 broken
        r["spear_state"] = 0       # 0 slung, 1 in_hand, 2 world, 3 gone   (SAINT only)
        r["active_weapon"] = 0     # 0 katana, 1 spear
        r["two_hand"] = 0
        r["left_hand"] = 0         # 0 free, 1 grip, 2 saya


# =============================================================================================
# placeholder bodies (flat colours per body part; replaced by character_meshes.build_meshes)
# =============================================================================================
PH_COLORS = {   # display colours (brighter than the final palette so poses read in Workbench)
    "SHINOBI": dict(torso=(0.09, 0.095, 0.115), arm=(0.11, 0.12, 0.15), guard=(0.20, 0.21, 0.26),
                    hakama=(0.24, 0.245, 0.28), sash=(0.50, 0.04, 0.04), band=(0.55, 0.05, 0.05),
                    skin=(0.45, 0.28, 0.20), mask=(0.06, 0.06, 0.07), hood=(0.075, 0.078, 0.09),
                    foot=(0.05, 0.05, 0.06), glove=(0.07, 0.07, 0.08)),
    "SAINT": dict(torso=(0.30, 0.11, 0.05), arm=(0.30, 0.11, 0.05), guard=(0.30, 0.11, 0.05),
                  hakama=(0.20, 0.20, 0.20), sash=(0.12, 0.10, 0.08), band=(0.12, 0.10, 0.08),
                  skin=(0.47, 0.30, 0.22), mask=(0.47, 0.30, 0.22), foot=(0.06, 0.05, 0.05), glove=(0.47, 0.30, 0.22),
                  beard=(0.62, 0.62, 0.58)),
}
PH_RADII = {    # (r_start, r_end) per segment, metres
    "SHINOBI": dict(neck=0.050, upper_arm=(0.050, 0.042), forearm=(0.043, 0.034), thigh=(0.085, 0.062),
                    shin=(0.060, 0.045), shoulder=0.048, chest=(0.125, 0.145), spine=(0.118, 0.122), hips=0.135,
                    head=0.086, chest_flat=0.66, spine_flat=0.70, hips_flat=0.72),
    "SAINT": dict(neck=0.062, upper_arm=(0.064, 0.054), forearm=(0.055, 0.044), thigh=(0.118, 0.105),
                  shin=(0.105, 0.088), shoulder=0.060, chest=(0.150, 0.170), spine=(0.148, 0.150), hips=0.160,
                  head=0.094, chest_flat=0.68, spine_flat=0.72, hips_flat=0.74),
}


PH_LR_TINT = False    # QA only (pose_atlas --lr-tint): warm LEFT / cool RIGHT limbs to read sides in the atlas.
                      # Off by default: the costume is symmetric (deny-list: no odd-coloured / prosthetic-looking arm)


def _tint(c, side):
    if not PH_LR_TINT:
        return c
    if side == "L":
        return (min(1, c[0] * 1.18), c[1] * 1.0, c[2] * 0.85)
    if side == "R":
        return (c[0] * 0.85, c[1] * 1.0, min(1, c[2] * 1.18))
    return c


def _ph_mat(char, key, side=""):
    c = _tint(PH_COLORS[char][key], side)
    return _mat(f"{char}_ph_{key}{('_' + side) if side else ''}", c, rough=0.8)


def _seg(rig, bone):
    b = rig.data.bones[bone]
    return Vector(b.head_local), Vector(b.tail_local)


def build_placeholder_body(char, rig, col):
    """Rigid, bone-parented placeholder segments (one object per bone, named <C>_ph_<bone>)."""
    R = PH_RADII[char]
    objs = {}

    def put(bone, acc, mats):
        ob = _mesh_obj(f"{char}_ph_{bone}", acc, mats, col, smooth=True)
        _bone_child_world(ob, rig, bone, rig.matrix_world.copy())   # verts are in rig space
        objs[ob.name] = ob
        return ob

    # spine chain
    for bone, key in (("spine", "spine"), ("chest", "chest")):
        a, b = _seg(rig, bone)
        x, y, z = bone_axes(rig, bone)
        r0, r1 = R[key]
        ext = 0.02 if bone == "chest" else 0.0
        put(bone, _MeshAcc().add(_capsule(a, b + y * ext, r0, r1, n=14, zdir=z, flat=R[key + "_flat"])),
            [_ph_mat(char, "torso")])
    a, b = _seg(rig, "hips")
    x, y, z = bone_axes(rig, "hips")
    acc = _MeshAcc().add(_capsule(a - y * 0.02, b, R["hips"], R["hips"] * 0.95, n=14, zdir=z, flat=R["hips_flat"]), 0)
    acc.add(_capsule(a + y * 0.045, a + y * 0.105, R["hips"] * 1.04, R["hips"] * 1.02, n=16, zdir=z,
                     flat=R["hips_flat"] + 0.02, ring=2), 1)                                          # obi / sash
    put("hips", acc, [_ph_mat(char, "hakama"), _ph_mat(char, "sash")])
    a, b = _seg(rig, "neck")
    put("neck", _MeshAcc().add(_capsule(a, b, R["neck"], R["neck"] * 0.92, n=10)), [_ph_mat(char, "skin" if char == "SAINT" else "mask")])
    # head
    a, b = _seg(rig, "head")
    x, y, z = bone_axes(rig, "head")
    L = (b - a).length
    hr = R["head"]
    acc = _MeshAcc()
    acc.add(_capsule(a + y * (L - hr - 0.064) + z * 0.012, a + y * (L - hr) + z * 0.012, hr, hr * 0.97, n=16, zdir=z, flat=1.08), 0)
    acc.add(_box(a + y * 0.055 + z * (hr * 0.78), (0.035, 0.03, 0.03), (x, y, z)), 1)                 # nose/face cue
    if char == "SHINOBI":
        # dark hood over the skull, cloth mask band over the lower face (flat-ended), skin only in the eye slit
        st = [(a + y * yy + z * 0.018, x, z, hr * 1.03, hr * 1.03 * 1.08) for yy in (-0.01, 0.072)]
        acc.add(_loft(st, _circle_profile(16), cap0=True, cap1=True), 2)
        acc.add(_box(a + y * 0.084 + z * (hr * 0.97), (0.085, 0.017, 0.03), (x, y, z)), 4)             # eye slit
        acc.add(_torus(a + y * (L * 0.50) + z * 0.012, y, hr * 1.02, 0.013, n=24, m=6, xref=z), 3)      # hachimaki
        mats = [_ph_mat(char, "hood"), _ph_mat(char, "mask"), _ph_mat(char, "mask"), _ph_mat(char, "band"),
                _ph_mat(char, "skin")]
    else:
        acc.add(_box(a + y * 0.095 + z * (hr * 0.85), (0.11, 0.02, 0.02), (x, y, z)), 2)               # heavy brows
        mats = [_ph_mat(char, "skin"), _ph_mat(char, "skin"), _ph_mat(char, "beard")]
    put("head", acc, mats)
    # limbs
    for side in ("L", "R"):
        a, b = _seg(rig, f"shoulder.{side}")
        put(f"shoulder.{side}", _MeshAcc().add(_capsule(a, b, R["shoulder"], R["shoulder"] * 1.05, n=10)), [_ph_mat(char, "torso", side)])
        a, b = _seg(rig, f"upper_arm.{side}")
        r0, r1 = R["upper_arm"]
        put(f"upper_arm.{side}", _MeshAcc().add(_capsule(a, b, r0, r1, n=12)), [_ph_mat(char, "arm", side)])
        # forearm: proximal half rigid on forearm, distal half (+ a dorsal guard plate) on forearm_twist, so the
        # twist helper is visible (it takes TWIST_SHARE of the hand's pronation)
        a, b = _seg(rig, f"forearm.{side}")
        r0, r1 = R["forearm"]
        m = (a + b) * 0.5
        rm = 0.5 * (r0 + r1)
        put(f"forearm.{side}", _MeshAcc().add(_capsule(a, m, r0, rm, n=12)), [_ph_mat(char, "guard", side)])
        fy = (b - a).normalized()
        lat = Vector(((1.0 if side == "L" else -1.0), 0.0, 0.0))
        lat = (lat - fy * lat.dot(fy)).normalized()
        sc_ = _scale(char)
        acc = _MeshAcc().add(_capsule(m, b, rm, r1, n=12), 0)
        acc.add(_box(m + (b - m) * 0.45 + lat * (rm * 0.95), (0.012 * sc_, (b - m).length * 0.8, 0.05 * sc_),
                     (lat, fy, lat.cross(fy).normalized())), 1)
        put(f"forearm_twist.{side}", acc, [_ph_mat(char, "guard", side), _ph_mat(char, "arm", side)])
        # fist
        a, b = _seg(rig, f"hand.{side}")
        x, y, z = bone_axes(rig, f"hand.{side}")
        s = _scale(char)
        acc = _MeshAcc().add(_box(a + y * (0.050 * s) + z * (0.014 * s), (0.078 * s, 0.100 * s, 0.062 * s), (x, y, z)))
        radial = x if side == "R" else -x
        acc.add(_capsule(a + y * (0.02 * s) + radial * (0.03 * s) + z * 0.02 * s,
                         a + y * (0.06 * s) + radial * (0.045 * s) + z * 0.03 * s, 0.014 * s, 0.012 * s, n=8))   # thumb
        put(f"hand.{side}", acc, [_ph_mat(char, "glove", side)])
        for bone, key in (("thigh", "thigh"), ("shin", "shin")):
            a, b = _seg(rig, f"{bone}.{side}")
            r0, r1 = R[key]
            put(f"{bone}.{side}", _MeshAcc().add(_capsule(a, b, r0, r1, n=12)), [_ph_mat(char, "hakama", side)])
        # foot / toe boxes are built LEVEL with the ground in the rest pose (sole at z = 3 mm)
        a, b = _seg(rig, f"foot.{side}")
        heel_y, ball_y = a.y + 0.055 * s, b.y
        top = a.z + 0.012 * s
        put(f"foot.{side}", _MeshAcc().add(_box(Vector((0.5 * (a.x + b.x), 0.5 * (heel_y + ball_y), 0.5 * (top + 0.003))),
                                                (0.085 * s, heel_y - ball_y, top - 0.003))), [_ph_mat(char, "foot", side)])
        a2, b2 = _seg(rig, f"toe.{side}")
        put(f"toe.{side}", _MeshAcc().add(_box(Vector((0.5 * (a2.x + b2.x), 0.5 * (a2.y + b2.y) - 0.004, 0.003 + 0.017 * s)),
                                               (0.08 * s, (a2.y - b2.y) + 0.012, 0.034 * s))), [_ph_mat(char, "foot", side)])
    # secondary chains
    if char == "SHINOBI":
        for i in (1, 2):
            for j in (1, 2, 3, 4):
                bn = f"tail{i}.{j}"
                a, b = _seg(rig, bn)
                x, y, z = bone_axes(rig, bn)
                w = 0.022 * (1.0 - 0.1 * (j - 1))
                st = [(a, x, z, w, 0.004), (b, x, z, w * 0.95, 0.004)]
                put(bn, _MeshAcc().add(_loft(st, [(1, 0), (0, 1), (-1, 0), (0, -1)])), [_ph_mat(char, "band")])
    else:
        rr = {1: (0.050, 0.040), 2: (0.040, 0.028), 3: (0.028, 0.012)}
        for j in (1, 2, 3):
            bn = f"beard.{j}"
            a, b = _seg(rig, bn)
            x, y, z = bone_axes(rig, bn)
            put(bn, _MeshAcc().add(_capsule(a, b, rr[j][0], rr[j][1], n=10, zdir=z, flat=0.6)), [_ph_mat(char, "beard")])
    return objs


def _dist_to_segments(V, segs):
    """(N, S) distances from points V (N,3) to segments [(a, b)]."""
    V = np.asarray(V, dtype=float)
    out = np.zeros((len(V), len(segs)))
    for k, (a, b) in enumerate(segs):
        a, b = np.array(a), np.array(b)
        ab = b - a
        t = np.clip(((V - a) @ ab) / max(ab @ ab, 1e-12), 0.0, 1.0)
        out[:, k] = np.linalg.norm(V - (a + np.outer(t, ab)), axis=1)
    return out


def skin_by_distance(obj, rig, region_bones, power=4.0, max_influences=3):
    """Numpy distance-to-bone-segment weights.
    region_bones: callable(vertex_rig_space ndarray (N,3)) -> list per vertex of allowed bone names, or a
    fixed list. Adds vertex groups + an Armature modifier (object=rig). Verts must be in rig space with the
    object parented to the rig with an identity local matrix."""
    me = obj.data
    V = np.array([v.co[:] for v in me.vertices])
    names = [b.name for b in rig.data.bones if b.use_deform]
    segs = [_seg(rig, n) for n in names]
    D = _dist_to_segments(V, segs)
    W = 1.0 / np.maximum(D, 1e-3) ** power
    allowed = region_bones(V) if callable(region_bones) else [region_bones] * len(V)
    idx = {n: i for i, n in enumerate(names)}
    mask = np.zeros_like(W)
    for vi, al in enumerate(allowed):
        for n in al:
            mask[vi, idx[n]] = 1.0
    W *= mask
    if max_influences:
        cut = np.sort(W, axis=1)[:, -max_influences][:, None]
        W = np.where(W >= cut, W, 0.0)
    W /= np.maximum(W.sum(axis=1, keepdims=True), 1e-12)
    for n in names:
        if n not in obj.vertex_groups:
            obj.vertex_groups.new(name=n)
    for bi, n in enumerate(names):
        vg = obj.vertex_groups[n]
        nz = np.nonzero(W[:, bi] > 1e-4)[0]
        for vi in nz:
            vg.add([int(vi)], float(W[vi, bi]), 'REPLACE')
    mod = obj.modifiers.get("Armature") or obj.modifiers.new("Armature", 'ARMATURE')
    mod.object = rig
    mod.use_vertex_groups = True
    return W


def build_placeholder_haori(rig, col):
    """SAINT_haori placeholder: coat tube shoulders -> mid-thigh + sleeve tubes around the upper arm / forearm and a
    hanging pouch (tamoto). Skinned with numpy distance weights restricted per PART (torso by height, sleeve tubes
    rigid on their arm bone, pouch on sleeve.*, lower coat on hem.*)."""
    zs = [1.50, 1.40, 1.25, 1.10, 0.95, 0.80, 0.64]
    pts = [rig.data.bones[b].head_local for b in ("hips", "spine", "chest", "neck")]
    zz = np.array([p.z for p in pts])
    yy = np.array([p.y for p in pts])
    hw = {1.50: (0.25, 0.16), 1.40: (0.27, 0.185), 1.25: (0.26, 0.19), 1.10: (0.245, 0.185),
          0.95: (0.255, 0.195), 0.80: (0.265, 0.20), 0.64: (0.28, 0.21)}
    st = [(Vector((0.0, float(np.interp(z, zz, yy)) + 0.01, z)), LEFT, Vector((0, 1, 0)), hw[z][0], hw[z][1]) for z in zs]
    acc = _MeshAcc()
    parts = []                                    # (vertex count, region spec)

    def add(part, region):
        acc.add(part)
        parts.append((len(part[0]), region))
    add(_loft(st, _circle_profile(20), cap0=False, cap1=False), "torso")
    for side in ("L", "R"):
        sh = rig.data.bones[f"upper_arm.{side}"].head_local
        el = rig.data.bones[f"upper_arm.{side}"].tail_local
        wr = rig.data.bones[f"forearm.{side}"].tail_local
        add(_capsule(sh + (el - sh) * 0.12, el, 0.088, 0.098, n=12, ring=2), [f"upper_arm.{side}"])
        add(_capsule(el, el + (wr - el) * 0.62, 0.098, 0.115, n=12, ring=2), [f"forearm.{side}"])
        top = el + (wr - el) * 0.32
        fy = (wr - el).normalized()
        add(_box(top + DOWN * 0.10, (0.07, 0.20, 0.15), (fy.cross(DOWN).normalized(), fy, -DOWN)), [f"sleeve.{side}"])
    ob = _mesh_obj("SAINT_haori", acc, [_mat("SAINT_haori_ph", PAL["saint_haori"], rough=0.9)], col, smooth=True)
    _obj_child(ob, rig)
    per_vertex = []
    V = np.array([v.co[:] for v in ob.data.vertices])
    i = 0
    for cnt, region in parts:
        for v in V[i:i + cnt]:
            if region != "torso":
                per_vertex.append(region)
            elif v[2] > 1.12:
                per_vertex.append(["chest", "spine", "shoulder.L", "shoulder.R"])
            elif v[2] > 0.90:
                per_vertex.append(["spine", "hips", "chest"])
            else:
                per_vertex.append(["hem.L", "hem.R", "hem.B"])
        i += cnt
    skin_by_distance(ob, rig, lambda _V: per_vertex)
    return {ob.name: ob}


# =============================================================================================
# state helpers (all switches keyed CONSTANT)
# =============================================================================================
def _obj(name):
    return bpy.data.objects[name]


def _key_vis(name, frame, visible):
    ob = bpy.data.objects.get(name)
    if ob is not None:
        U.key_visible(ob, frame, visible)


def _local_nla_value(idb, data_path, index, frame):
    """Value of a channel at `frame` from the ID's NLA strips (earlier lanes after stashing): the unmuted strip
    with the latest start <= frame that animates it wins (HOLD_FORWARD semantics, scene -> action time); strips
    with extrapolation 'HOLD' (lane_tools' BASE track) also answer for frames before their start, with the lowest
    priority. None if no strip animates the channel."""
    ad = getattr(idb, "animation_data", None)
    if ad is None:
        return None
    from bpy_extras import anim_utils
    best, best_prio = None, -math.inf
    for tr in ad.nla_tracks:
        if tr.mute:
            continue
        for st in tr.strips:
            if st.mute or st.action is None:
                continue
            before = st.frame_start > frame + 1e-6
            if before and st.extrapolation != 'HOLD':
                continue
            prio = -1e12 if before else st.frame_start
            if prio < best_prio:
                continue
            cb = anim_utils.action_get_channelbag_for_slot(st.action, st.action_slot) if st.action_slot else None
            fc = cb.fcurves.find(data_path, index=index) if cb is not None else None
            if fc is None or not len(fc.keyframe_points):
                continue
            t = min(max(frame, st.frame_start), st.frame_end) - st.frame_start + st.action_frame_start
            best, best_prio = fc.evaluate(t), prio
    return best


def _prior_value(idb, data_path, index, frame):
    """State of a channel at `frame` from BEFORE the current lane's keys: lane_tools._prior_value when available
    (earlier strips, BASE, the begin_lane snapshot), else this module's _local_nla_value. None if unknown."""
    try:
        import lane_tools
        fn = getattr(lane_tools, "_prior_value", None)
    except ImportError:
        fn = None
    if fn is not None:
        try:
            return fn(idb, data_path, index, frame)
        except Exception:                          # noqa: BLE001 - fall back to the local reader
            pass
    return _local_nla_value(idb, data_path, index, frame)


def _fc_value(id_or_obj, data_path, frame, default, index=0):
    """Value of a (possibly animated) property at `frame`, independent of the order in which a lane keys it:
      * frame at/after the active action's first key on the channel -> that F-curve;
      * frame BEFORE it (or no active key) -> the state from before the current lane (earlier lanes' NLA strips,
        lane_tools' BASE track / begin_lane snapshot) - lane_tools holds that state until the lane's first key
        (single-action semantics for switches); if nothing earlier animates the channel, the active F-curve
        (Blender's constant back-extrapolation) or `default` (the current static value)."""
    fc = U.fcurve(id_or_obj, data_path, index)
    has = fc is not None and len(fc.keyframe_points) > 0
    if has and frame >= fc.keyframe_points[0].co.x - 1e-6:
        return fc.evaluate(frame)
    if has and fc.keyframe_points[0].interpolation != 'CONSTANT' and not data_path.startswith("hide_"):
        # continuous channel: inside the open lane the lane's own curve rules from the lane start (lane_tools:
        # "pure isolation" for continuous channels); before the lane start the earlier state applies
        lane = _current_lane()
        if lane is not None and frame >= _lane_start(lane) - 0.3:
            return fc.evaluate(frame)
    v = _prior_value(id_or_obj, data_path, index, frame)
    if v is not None:
        return v
    return fc.evaluate(frame) if has else default


def _current_lane():
    """Name of the lane_tools lane being built, or None (no lane_tools / no open lane)."""
    try:
        import lane_tools
        return lane_tools.current_lane()
    except (ImportError, AttributeError):
        return None


def _lane_start(lane):
    try:
        import lane_tools
        return float(lane_tools.lane_span(lane)[0])
    except Exception:                               # noqa: BLE001
        return -math.inf


def _key_switch(owner, data_path, frame, value, blend=0, owner_id=None):
    """Key a switch-like scalar. blend=0: one CONSTANT key. blend>0: keep the old value at `frame`
    (BEZIER) and reach `value` at frame+blend (CONSTANT)."""
    idv = owner_id or owner
    if not isinstance(owner, bpy.types.ID):
        data_path = owner.path_from_id(data_path)
        idv = owner.id_data
    if blend and blend > 0:
        old = _fc_value(idv, data_path, frame, idv.path_resolve(data_path))
        U.key(idv, data_path, frame, float(old), interp='BEZIER')
        U.key(idv, data_path, frame + blend, float(value), interp='CONSTANT')
    else:
        U.key(idv, data_path, frame, float(value), interp='CONSTANT')


def _con(rig, bone, name):
    return rig.pose.bones[bone].constraints.get(name)


def set_arm_mode(rig, frame, mode, blend=0):
    """Right (sword) arm: 'ik' -> forearm.R IK_sword + hand.R COPYROT_sword influence 1 (blade follows
    <C>_sword_ctrl); 'fk' -> 0 (arm follows the pose library, e.g. hand on the sheathed hilt). CONSTANT key
    at `frame`, or a smooth `blend`-frame transition starting at `frame`."""
    rig = get_rig(rig)
    v = 1.0 if mode == "ik" else 0.0
    if mode not in ("ik", "fk"):
        raise ValueError("mode must be 'ik' or 'fk'")
    for bone, cn in (("forearm.R", "IK_sword"), ("hand.R", "COPYROT_sword")):
        _key_switch(_con(rig, bone, cn), "influence", frame, v, blend)


def active_weapon(rig, frame):
    """'katana' | 'spear' held at `frame` (from the keyed rig['active_weapon'])."""
    rig = get_rig(rig)
    return "spear" if _fc_value(rig, '["active_weapon"]', frame, rig.get("active_weapon", 0)) > 0.5 else "katana"


LEFT_MODES = ("free", "grip", "saya")


def _left_state(rig, frame):
    """Left-hand state at `frame`: None (free) | 'grip:katana' | 'grip:spear' | 'saya' (keyed influences, earlier
    lanes included)."""
    c = _prefix(rig)
    ik = _con(rig, "forearm.L", "IK_grip")
    if _fc_value(rig, ik.path_from_id("influence"), frame, ik.influence) > 0.5:
        return "grip:katana"
    alt = _con(rig, "forearm.L", "IK_alt")
    if _fc_value(rig, alt.path_from_id("influence"), frame, alt.influence) > 0.5:
        tg = _obj(f"{c}_hand_L_target")
        for key in ("spear", "saya"):
            con = tg.constraints.get(f"TGT_{key}")
            if con is not None and _fc_value(tg, f'constraints["TGT_{key}"].influence', frame, con.influence) > 0.5:
                return "grip:spear" if key == "spear" else "saya"
    return None


def left_hand(rig, frame):
    """'free' | 'grip' | 'saya' at `frame` (from the keyed constraint influences, earlier lanes included)."""
    st = _left_state(get_rig(rig), frame)
    return "free" if st is None else ("saya" if st == "saya" else "grip")


def _key_left_channels(rig, frame, state, blend_in=0, blend_out=0, keep_select=False):
    """Key the left-hand channels for `state` at `frame` (see set_left_hand)."""
    c = _prefix(rig)
    want_grip = 1.0 if state == "grip:katana" else 0.0
    want_alt = 1.0 if state in ("grip:spear", "saya") else 0.0
    for bone, cn, v in (("forearm.L", "IK_grip", want_grip), ("hand.L", "COPYROT_grip", want_grip),
                        ("forearm.L", "IK_alt", want_alt), ("hand.L", "COPYROT_alt", want_alt)):
        con = _con(rig, bone, cn)
        cur = _fc_value(rig, con.path_from_id("influence"), frame, con.influence)
        b = blend_in if v > cur else blend_out
        _key_switch(con, "influence", frame, v, b if abs(v - cur) > 1e-6 else 0)
    if keep_select:
        return
    for obn in (f"{c}_hand_L_target", f"{c}_pole_L_alt"):
        ob = _obj(obn)
        for key in ("saya", "spear"):
            con = ob.constraints.get(f"TGT_{key}")
            if con is not None:
                v = 1.0 if (state == "saya" and key == "saya") or (state == "grip:spear" and key == "spear") else 0.0
                _key_switch(con, "influence", frame, v)


def set_left_hand(rig, frame, mode, blend=0, weapon=None):
    """Left hand target at `frame` - exactly one target on (IK + Copy Rotation):
      'free' -> FK left arm (pose library);
      'grip' -> the in-hand weapon's grip: <C>_grip_L on the katana (IK_grip + COPYROT_grip) or SAINT_grip_L_spear
                on the spear (IK_alt + COPYROT_alt via the <C>_hand_L_target switcher); weapon=None -> the active
                weapon at `frame` (call set_weapon_state first);
      'saya' -> <C>_saya_grip_L (IK_alt via the switcher): left fist around the scabbard just behind the koiguchi,
                thumb side on the tsuba (iai stance, koiguchi push, sheathing, saya-biki with key_saya).
    blend=0: CONSTANT switch. blend=n: the previous target fades out over [frame, frame+n]; a new target fades in
    over [frame+n, frame+2n] when another one was on (the arm passes through its FK pose - two IK targets are never
    cross-faded), else over [frame, frame+n]. Also keys rig['left_hand'] (0 free, 1 grip, 2 saya), rig['two_hand']."""
    rig = get_rig(rig)
    if mode not in LEFT_MODES:
        raise ValueError(f"mode must be one of {LEFT_MODES}")
    state = None
    if mode == "grip":
        w = weapon or active_weapon(rig, frame)
        if w not in (("katana", "spear") if _prefix(rig) == "SAINT" else ("katana",)):
            raise ValueError(f"{_prefix(rig)} has no weapon {w!r}")
        state = f"grip:{w}"
    elif mode == "saya":
        state = "saya"
    cur = _left_state(rig, frame)
    b = int(blend or 0)
    if b <= 0 or cur == state:
        _key_left_channels(rig, frame, state)
    elif cur is None:                               # free -> target: fade in
        _key_left_channels(rig, frame, state, blend_in=b)
    elif state is None:                             # target -> free: fade out (keep the selector)
        _key_left_channels(rig, frame, None, blend_out=b, keep_select=True)
    else:                                           # target -> other target: out, switch, in
        _key_left_channels(rig, frame, None, blend_out=b, keep_select=True)
        _key_left_channels(rig, frame + b, state, blend_in=b)
    U.key(rig, '["left_hand"]', frame, float(LEFT_MODES.index(mode)), interp='CONSTANT')
    U.key(rig, '["two_hand"]', frame, 1.0 if mode == "grip" else 0.0, interp='CONSTANT')


def set_two_hand(rig, frame, on, weapon=None, blend=0):
    """Left hand joins (on=True) or leaves the in-hand weapon = set_left_hand(rig, frame, 'grip' | 'free', ...):
    keys IK_grip (forearm.L) + COPYROT_grip (hand.L) for the katana, or IK_alt + COPYROT_alt with the
    <C>_hand_L_target switcher on SAINT_grip_L_spear for the saint's spear; any other left target (incl. the saya
    grip) is released.
    weapon=None -> the active weapon at `frame` (call set_weapon_state first)."""
    set_left_hand(rig, frame, "grip" if on else "free", blend=blend, weapon=weapon)


KATANA_STATES = ("sheathed", "drawn", "broken")
SPEAR_STATES = ("slung", "in_hand", "world", "gone")


def set_weapon_state(rig_or_name, frame, state):
    """Visibility swap of the weapon props at `frame` (CONSTANT keys via bl_util.key_visible).
    katana: 'sheathed' (in the saya) | 'drawn' (in hand) | 'broken' (SAINT: in-hand blade loses its tip piece,
            SAINT_katana_tip_broken appears - animate it with snap_free/props.toss);
    spear (SAINT): 'slung' (on the back) | 'in_hand' (sheath comes off: SAINT_spear_sheath_world appears) |
            'world' (free SAINT_spear_world for flying/lying) | 'gone'.
    Also keys rig['katana_state'|'spear_state'|'active_weapon'] and drops the left-hand grip on a weapon that
    leaves the hand."""
    rig = get_rig(rig_or_name)
    c = _prefix(rig)
    if state in KATANA_STATES:
        if state == "broken" and c != "SAINT":
            raise ValueError("only the SAINT's katana breaks")
        drawn = state in ("drawn", "broken")
        _key_vis(f"{c}_katana_hand", frame, drawn)
        _key_vis(f"{c}_katana_sheathed", frame, not drawn)
        if c == "SAINT":
            _key_vis("SAINT_katana_hand_tip", frame, state == "drawn")
            _key_vis("SAINT_katana_tip_broken", frame, state == "broken")
        U.key(rig, '["katana_state"]', frame, float(KATANA_STATES.index(state)), interp='CONSTANT')
        if not drawn and _left_state(rig, frame) == "grip:katana":
            _key_left_channels(rig, frame, None, keep_select=True)
        if drawn and c == "SAINT":
            U.key(rig, '["active_weapon"]', frame, 0.0, interp='CONSTANT')
        return
    if state in SPEAR_STATES:
        if c != "SAINT":
            raise ValueError("only the SAINT has a spear")
        _key_vis("SAINT_spear_slung", frame, state == "slung")
        _key_vis("SAINT_spear_hand", frame, state == "in_hand")
        _key_vis("SAINT_spear_world", frame, state == "world")
        if state in ("slung", "in_hand"):
            _key_vis("SAINT_spear_sheath_world", frame, state == "in_hand")
        U.key(rig, '["spear_state"]', frame, float(SPEAR_STATES.index(state)), interp='CONSTANT')
        U.key(rig, '["active_weapon"]', frame, 1.0 if state == "in_hand" else 0.0, interp='CONSTANT')
        if state != "in_hand" and _left_state(rig, frame) == "grip:spear":
            _key_left_channels(rig, frame, None, keep_select=True)
        return
    raise ValueError(f"unknown weapon state {state!r}")


def set_costume(frame, haori=True, thrown=None):
    """SAINT costume at `frame`: haori on (tasuki hidden) or shed (haori hidden, white tasuki visible,
    SAINT_haori_thrown visible unless thrown=False). Shedding with the thrown copy (thrown None/True) first calls
    snapshot_haori(frame) + snap_free (the thrown mesh IS the evaluated skinned haori at the swap
    frame - no pop), so key the body pose of the swap frame BEFORE calling it; then fly it with props.toss."""
    show_thrown = (not haori) if thrown is None else bool(thrown)
    if not haori and show_thrown:
        snapshot_haori(frame)
        snap_free("SAINT_haori_thrown", frame)
    _key_vis("SAINT_haori", frame, haori)
    _key_vis("SAINT_tasuki", frame, not haori)
    _key_vis("SAINT_haori_thrown", frame, show_thrown)


def snapshot_haori(frame, shape_keys=True):
    """copy the EVALUATED skinned SAINT_haori at `frame` (whatever mesh + modifiers the meshes lane gave
    it) into SAINT_haori_thrown's mesh, in a local frame = the chest bone at `frame` moved to the vertex centroid,
    and set the thrown object's matrix + attach_offset so detach_matrix / snap_free land it exactly on the worn coat
    at `frame`. shape_keys: adds 'spread' (opened flat in the air) and 'crumple' (collapsed heap) for the props lane.
    Returns the thrown object's world matrix at `frame`."""
    rig = _obj("SAINT_rig")
    src, dst = _obj("SAINT_haori"), _obj("SAINT_haori_thrown")
    sc = bpy.context.scene
    fcur = sc.frame_current
    U.frame_set(frame)
    hv = src.hide_viewport
    src.hide_viewport = False                      # the swap key may already hide it: evaluate it anyway
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = src.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=False, depsgraph=dg)
    Mw = ev.matrix_world.copy()
    chest = rig.matrix_world @ rig.pose.bones["chest"].matrix
    src.hide_viewport = hv
    n = len(me.vertices)
    co = np.zeros(n * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    Mn = np.array(Mw)
    world = co @ Mn[:3, :3].T + Mn[:3, 3]
    cen = world.mean(axis=0) if n else np.zeros(3)
    frame_w = chest.copy()
    frame_w.translation = Vector(cen)
    Fi = np.array(frame_w.inverted())
    local = world @ Fi[:3, :3].T + Fi[:3, 3]
    me.vertices.foreach_set("co", local.ravel())
    me.update()
    old = dst.data
    me.name = "SAINT_haori_thrown_mesh"
    dst.data = me
    if old is not None and old.users == 0:
        bpy.data.meshes.remove(old)
    for m in list(dst.modifiers):
        dst.modifiers.remove(m)
    dst.vertex_groups.clear()
    if shape_keys and n:
        dst.shape_key_add(name="Basis", from_mix=False)
        sp = dst.shape_key_add(name="spread", from_mix=False)
        cr = dst.shape_key_add(name="crumple", from_mix=False)
        loc = local.copy()
        spread = loc * np.array((1.30, 1.05, 0.12))                     # opened: wider, flat (chest z = depth)
        rng = np.random.default_rng(zlib.crc32(b"SAINT_haori_thrown:crumple"))
        crumple = loc * np.array((0.75, 0.40, 0.30)) + rng.uniform(-0.02, 0.02, loc.shape)
        sp.data.foreach_set("co", spread.ravel())
        cr.data.foreach_set("co", crumple.ravel())
        sp.value = cr.value = 0.0                      # Blender 5.2 creates new shape keys at value 1.0
    _set_attach(dst, rig.name, (rig.matrix_world @ rig.pose.bones["chest"].matrix).inverted() @ frame_w, bone="chest")
    dst.matrix_world = frame_w
    U.frame_set(fcur)
    return frame_w


def set_hat(frame, state):
    """SAINT straw hat: 'on' (worn) | 'cut' (hidden; the two free halves appear - animate them with
    snap_free/props.toss) | 'off' (everything hidden)."""
    if state not in ("on", "cut", "off"):
        raise ValueError("state must be on|cut|off")
    _key_vis("SAINT_hat", frame, state == "on")
    for h in ("SAINT_hat_half_A", "SAINT_hat_half_B"):
        _key_vis(h, frame, state == "cut")


def set_beard_cord(frame, cut):
    """SAINT beard cord: intact (on beard.3) or cut (free SAINT_beard_cord_cut appears)."""
    _key_vis("SAINT_beard_cord", frame, not cut)
    _key_vis("SAINT_beard_cord_cut", frame, bool(cut))


def set_kunai_in_hand(frame, on):
    """SHINOBI: show/hide the kunai held in his LEFT fist (SHINOBI_kunai_hand, S16 off-hand deflect)."""
    _key_vis("SHINOBI_kunai_hand", frame, bool(on))


def set_spear_grip(frame, grip_R=None, grip_L=None, interp='BEZIER'):
    """Slide the spear through the saint's hands: grip_R / grip_L = FIST CENTRE positions measured from the butt
    (m). Keys SAINT_spear_hand.location.y (= -weapon.R length - grip_R, in the weapon.R tail frame) and
    SAINT_grip_L_spear.location.y (= grip_L + socket['fist_offset']: the socket is the left wrist frame)."""
    if grip_R is not None:
        ob = _obj("SAINT_spear_hand")
        L = ob.parent.data.bones["weapon.R"].length
        U.key(ob, "location", frame, -L - float(grip_R), index=1, interp=interp)
    if grip_L is not None:
        gl = _obj("SAINT_grip_L_spear")
        U.key(gl, "location", frame, float(grip_L) + gl.get("fist_offset", 0.0), index=1, interp=interp)


def spear_grip(frame=None):
    """(grip_R, grip_L) of the saint's spear at `frame` (None = current values)."""
    sh, gl = _obj("SAINT_spear_hand"), _obj("SAINT_grip_L_spear")
    L = sh.parent.data.bones["weapon.R"].length
    y1 = sh.location.y if frame is None else _fc_value(sh, "location", frame, sh.location.y, index=1)
    y2 = gl.location.y if frame is None else _fc_value(gl, "location", frame, gl.location.y, index=1)
    return -y1 - L, y2 - gl.get("fist_offset", 0.0)


def saya_basis(rig, pull=0.0, roll=0.0):
    """matrix_basis of <C>_saya pulled `pull` metres back along its axis (saya-biki: towards the kojiri) and rolled
    `roll` degrees about its axis (+ = the edge turns OUTWARD, away from the body: koiguchi o kiru / the draw)."""
    rig = get_rig(rig)
    sy = _obj(f"{_prefix(rig)}_saya")
    rest = _flat_to_matrix(list(sy["rest_basis"]))
    return rest @ Matrix.Translation((0.0, float(pull), 0.0)) @ Matrix.Rotation(math.radians(roll), 4, 'Y')


def key_saya(rig, frame, pull=0.0, roll=0.0, interp='BEZIER'):
    """Key the scabbard (child of hips) at `frame`: saya-biki pull (m, + = back towards the kojiri) and roll (deg,
    + = edge outward). The sheathed katana and <C>_saya_grip_L ride along; key pull/roll back to 0 to re-seat it.
    sheathed_ctrl_matrix(rig, f) follows the keyed scabbard, so a draw grab stays exact."""
    rig = get_rig(rig)
    return key_ctrl_matrix(_obj(f"{_prefix(rig)}_saya"), frame, saya_basis(rig, pull, roll), interp)


def set_hat_tilt(frame, pitch=0.0, roll=0.0, interp='BEZIER'):
    """Key SAINT_hat's tilt on the head at `frame`, composed onto its rest placement (never key its raw rotation:
    the rest basis is rotated -90 deg about X). pitch > 0 lifts the FRONT brim (hat pushed back, e.g. to clear the
    forearms in jodan), pitch < 0 pulls it down over the eyes; roll > 0 tips it towards his LEFT (left brim down).
    Rotation about the rim-plane centre."""
    hat = _obj("SAINT_hat")
    rest = _flat_to_matrix(list(hat["rest_basis"]))
    R = Matrix.Rotation(math.radians(-pitch), 4, 'X') @ Matrix.Rotation(math.radians(roll), 4, 'Y')
    return key_ctrl_matrix(hat, frame, rest @ R, interp)


# =============================================================================================
# sword controller API
# =============================================================================================
def blade_frame(grip, direction, edge=None):
    """World/rig matrix of a blade frame: origin `grip`, +Y = direction, -Z = edge (orthogonalised).
    edge=None -> the edge faces 'down' (world -Z projected); for a vertical blade it faces the character's
    forward (-Y) instead."""
    y = Vector(direction).normalized()
    if edge is None:
        e = Vector((0.0, 0.0, -1.0))
        if abs(e.dot(y)) > 0.98:
            e = Vector((0.0, -1.0, 0.0))
    else:
        e = Vector(edge)
    z = -(e - y * e.dot(y))
    if z.length < 1e-6:
        raise ValueError("edge parallel to the blade direction")
    z.normalize()
    x = y.cross(z)
    return _axes_matrix(Vector(grip), x, y, z)


def sword_ctrl_matrix(rig, grip, direction, edge=None, space='WORLD', frame=None):
    """Local (rig-space) matrix for <C>_sword_ctrl that puts the right-fist grip centre at `grip`, the blade
    along `direction` and the edge towards `edge` (vectors in `space`: 'WORLD' or 'RIG'). With space='WORLD'
    the rig's world matrix at `frame` (None = current) is used for the conversion."""
    rig = get_rig(rig)
    B = blade_frame(grip, direction, edge)
    if space == 'WORLD':
        Mw = U.world_matrix_of(rig, frame) if frame is not None else rig.matrix_world
        B = Mw.inverted() @ B
    return B


def _euler_compat(obj, frame):
    fcs = [U.fcurve(obj, "rotation_euler", i) for i in range(3)]
    if all(fc is not None and len(fc.keyframe_points) for fc in fcs):
        return Euler(tuple(fc.evaluate(frame) for fc in fcs), 'XYZ')
    return obj.rotation_euler.copy()


def key_ctrl_matrix(obj, frame, local, interp='BEZIER'):
    """Key location + XYZ Euler (continuity-compatible with the curve at `frame`) of an object from a local
    matrix."""
    loc, rot, _ = local.decompose()
    e = rot.to_euler('XYZ', _euler_compat(obj, frame))
    U.key(obj, "location", frame, tuple(loc), interp=interp)
    U.key(obj, "rotation_euler", frame, tuple(e), interp=interp)
    return e


def key_sword(rig, frame, grip, direction, edge=None, space='WORLD', interp='BEZIER'):
    """Key <C>_sword_ctrl so the in-hand weapon's grip centre is at `grip`, pointing along `direction`,
    edge towards `edge` (default: down). Does not change the arm mode (call set_arm_mode(rig, f, 'ik'))."""
    rig = get_rig(rig)
    ctrl = _obj(f"{_prefix(rig)}_sword_ctrl")
    return key_ctrl_matrix(ctrl, frame, sword_ctrl_matrix(rig, grip, direction, edge, space, frame), interp)


def tip_distance(rig, weapon=None, frame=None):
    """Distance along +Y from the controller origin (right-fist centre) to the in-hand weapon's tip."""
    rig = get_rig(rig)
    c = _prefix(rig)
    w = weapon or (active_weapon(rig, frame if frame is not None else bpy.context.scene.frame_current)
                   if c == "SAINT" else "katana")
    if w == "spear":
        gR, _ = spear_grip(frame)
        return DIMS["SAINT"]["spear_length"] - gR
    D = DIMS[c]
    return D["grip_to_tsuba"] + D["tsuba_thickness"] * 0.5 + D["blade_length"]


def key_blade_tip(rig, frame, tip, direction, edge=None, space='WORLD', interp='BEZIER', weapon=None):
    """Like key_sword but places the weapon TIP at `tip` (grip = tip - direction * tip_distance)."""
    d = Vector(direction).normalized()
    grip = Vector(tip) - d * tip_distance(rig, weapon, frame)
    return key_sword(rig, frame, grip, d, edge, space, interp)


def blade_points(rig, frame=None, weapon=None):
    """(base, tip) world positions of the in-hand weapon at `frame` (None = current): katana -> <C>_katana_base
    / _tip, spear -> SAINT_spear_base / _tip."""
    rig = get_rig(rig)
    c = _prefix(rig)
    if frame is not None:
        U.frame_set(frame)
    f = bpy.context.scene.frame_current
    w = weapon or (active_weapon(rig, f) if c == "SAINT" else "katana")
    names = ("SAINT_spear_base", "SAINT_spear_tip") if w == "spear" else (f"{c}_katana_base", f"{c}_katana_tip")
    return tuple(U.world_pos_of(_obj(n)) for n in names)


def reach_report(rig, frame=None):
    """Evaluated IK residuals at `frame`: dict(sword_mm, sword_deg, grip_mm (or None), wrist_dist, arm_len,
    active: which constraints are on). Errors are measured on the evaluated pose (depsgraph)."""
    rig = get_rig(rig)
    c = _prefix(rig)
    if frame is not None:
        U.frame_set(frame)
    else:
        bpy.context.view_layer.update()
    pb = rig.pose.bones
    Mw = rig.matrix_world
    out = dict(sword_mm=None, sword_deg=None, grip_mm=None)
    ik = _con(rig, "forearm.R", "IK_sword")
    wt = _obj(f"{c}_sword_ctrl_wrist")
    arm = rig.data.bones["upper_arm.R"].length + rig.data.bones["forearm.R"].length
    out["arm_len"] = arm
    out["wrist_dist"] = (U.world_pos_of(wt) - Mw @ pb["upper_arm.R"].head).length
    if ik.influence > 0.5:
        W = Mw @ pb["hand.R"].matrix
        T = U.world_matrix_of(wt)
        out["sword_mm"] = (W.translation - T.translation).length * 1000.0
        out["sword_deg"] = math.degrees(W.to_quaternion().rotation_difference(T.to_quaternion()).angle)
    for cn in ("IK_grip", "IK_alt"):
        con = _con(rig, "forearm.L", cn)
        if con is not None and con.influence > 0.5:
            out["grip_mm"] = (Mw @ pb["hand.L"].head - U.world_pos_of(con.target)).length * 1000.0
            break
    return out


def reach_ok(rig, frame=None, tol=0.002):
    """True when every active IK (sword arm, left-hand grip) reaches its target within `tol` metres."""
    r = reach_report(rig, frame)
    errs = [v for v in (r["sword_mm"], r["grip_mm"]) if v is not None]
    return all(e <= tol * 1000.0 for e in errs)


def sheathed_ctrl_matrix(rig, frame):
    """Controller local matrix that makes <C>_katana_hand coincide with <C>_katana_sheathed at `frame`
    (key it on the draw frame for a pop-free sheathed->drawn swap, then pull along -Y to draw)."""
    rig = get_rig(rig)
    c = _prefix(rig)
    W = U.world_matrix_of(_obj(f"{c}_katana_sheathed"), frame)
    return U.world_matrix_of(rig, frame).inverted() @ W


def slung_spear_ctrl_matrix(frame, grip_R=None):
    """Controller local matrix that makes SAINT_spear_hand coincide with SAINT_spear_slung at `frame` when
    the right fist holds the shaft at grip_R metres from the butt (default: current spear grip)."""
    rig = _obj("SAINT_rig")
    if grip_R is None:
        grip_R, _ = spear_grip(frame)
    S = U.world_matrix_of(_obj("SAINT_spear_slung"), frame)
    return U.world_matrix_of(rig, frame).inverted() @ S @ Matrix.Translation((0.0, float(grip_R), 0.0))


# =============================================================================================
# free props: where they are while still attached
# =============================================================================================
def detach_matrix(free, frame):
    """World matrix a FREE prop must have at `frame` to coincide with its attached counterpart (hat halves
    <- SAINT_hat, broken tip <- katana, cut cord <- beard cord, spear_world <- spear_hand, sheath_world <-
    spear_slung, kunai <- left fist, thrown haori <- chest)."""
    ob = _obj(free) if isinstance(free, str) else free
    target = _obj(ob["attach_to"])
    bone = ob.get("attach_bone", "")
    off = _flat_to_matrix(list(ob["attach_offset"]))
    if bone:
        return U.world_matrix_of((target, bone), frame) @ off
    return U.world_matrix_of(target, frame) @ off


def snap_free(free, frame, interp='CONSTANT'):
    """Key the free prop's location/rotation at `frame` onto detach_matrix (continuity at the swap frame)."""
    ob = _obj(free) if isinstance(free, str) else free
    M = detach_matrix(ob, frame)
    ob.rotation_mode = 'XYZ'
    return key_ctrl_matrix(ob, frame, M, interp)


# =============================================================================================
# pose helpers (degrees in, radians in Blender)
# =============================================================================================
def mirror_name(bone):
    """Left/right partner of a bone name (.L <-> .R; hachimaki tail1.* (left) <-> tail2.* (right))."""
    if bone.startswith("tail1."):
        return "tail2." + bone[6:]
    if bone.startswith("tail2."):
        return "tail1." + bone[6:]
    if bone.endswith(".L"):
        return bone[:-2] + ".R"
    if bone.endswith(".R"):
        return bone[:-2] + ".L"
    return bone


def mirror_pose(body):
    """Mirror a {bone: (rx, ry, rz)} pose left<->right: swap .L/.R, negate Y and Z rotations."""
    return {mirror_name(b): (r[0], -r[1], -r[2]) for b, r in body.items()}


def pose_bones(rig, body, frame=None, interp='BEZIER', reset=False, hips_offset=None):
    """Set (and key at `frame` if given) pose-bone Euler rotations from {bone: (rx, ry, rz) degrees}.
    reset=True zeroes every other body bone first. hips_offset=(x, y, z) sets hips.location (bone-local:
    x = character's left, y = up, z = forward)."""
    rig = get_rig(rig)
    if reset:
        for pb in rig.pose.bones:
            if pb.name in body:
                continue
            pb.rotation_euler = (0.0, 0.0, 0.0)
            if frame is not None and pb.name in BODY_BONES:
                U.key(pb, "rotation_euler", frame, interp=interp)
    for b, r in body.items():
        pb = rig.pose.bones[b]
        val = tuple(math.radians(a) for a in r)
        if frame is None:
            pb.rotation_euler = val
        else:
            U.key(pb, "rotation_euler", frame, val, interp=interp)
    if hips_offset is not None:
        pb = rig.pose.bones["hips"]
        if frame is None:
            pb.location = hips_offset
        else:
            U.key(pb, "location", frame, tuple(hips_offset), interp=interp)


def _euler_deg(R3, compat=None):
    e = R3.to_euler('XYZ', compat) if compat is not None else R3.to_euler('XYZ')
    return tuple(round(math.degrees(a), 4) for a in e)


def solve_leg(rig, side, ankle, hips_rot=(0.0, 0.0, 0.0), hips_offset=(0.0, 0.0, 0.0), knee_dir=None,
              foot_yaw=0.0, foot_pitch=0.0):
    """Analytic 2-bone leg solve -> FK Eulers (degrees) that put the ankle (shin tail) at `ankle` (RIG space)
    for a given hips pose (hips_rot degrees, hips_offset bone-local metres). The knee bends towards `knee_dir`
    (rig space, default forward -Y turned by foot_yaw); the foot keeps its rest (flat) orientation turned by
    foot_yaw (deg, + = toes to the character's left) and pitched by foot_pitch (deg, + = toes down).
    Returns dict(thigh=(rx,ry,rz), shin=(...), foot=(...), reach=bool, dist=float). Pure math (no depsgraph);
    use it to plant feet for crouches, lunges and kneels while the body stays FK."""
    rig = get_rig(rig)
    B = rig.data.bones
    hr = Euler(tuple(math.radians(a) for a in hips_rot), 'XYZ').to_matrix().to_4x4()
    hips_pose = B["hips"].matrix_local @ Matrix.Translation(hips_offset) @ hr
    th, sh, ft = B[f"thigh.{side}"], B[f"shin.{side}"], B[f"foot.{side}"]
    P_th = hips_pose @ B["hips"].matrix_local.inverted() @ th.matrix_local
    H = P_th.translation
    A = Vector(ankle)
    a, b = th.length, sh.length
    v = A - H
    d = v.length
    reach = d <= a + b - 1e-4
    d = min(max(d, abs(a - b) + 1e-4), a + b - 1e-4)
    u = v.normalized()
    yaw = Matrix.Rotation(math.radians(foot_yaw), 3, 'Z')
    hint = Vector(knee_dir) if knee_dir is not None else yaw @ FWD
    w = hint - u * hint.dot(u)
    if w.length < 1e-6:
        w = FWD - u * FWD.dot(u)
    w.normalize()
    cos_al = (a * a + d * d - b * b) / (2 * a * d)
    al = math.acos(max(-1.0, min(1.0, cos_al)))
    K = H + (u * math.cos(al) + w * math.sin(al)) * a
    A2 = H + u * d
    yt = (K - H).normalized()
    zt = hint - yt * hint.dot(yt)
    zt = zt.normalized() if zt.length > 1e-6 else w
    xt = yt.cross(zt)
    R_th = Matrix((xt, yt, zt)).transposed()
    loc_th = P_th.to_3x3().inverted() @ R_th
    th_pose = P_th @ loc_th.to_4x4()
    th_pose.translation = H
    P_sh = th_pose @ th.matrix_local.inverted() @ sh.matrix_local
    ys = (A2 - K).normalized()
    zs = ys.cross(xt)
    zs = zs.normalized() if zs.length > 1e-6 else -zt
    xs = ys.cross(zs)
    R_sh = Matrix((xs, ys, zs)).transposed()
    loc_sh = P_sh.to_3x3().inverted() @ R_sh
    sh_pose = P_sh @ loc_sh.to_4x4()
    P_ft = sh_pose @ sh.matrix_local.inverted() @ ft.matrix_local
    R_ft = yaw @ Matrix.Rotation(math.radians(foot_pitch), 3, ft.matrix_local.to_3x3().col[0]) @ ft.matrix_local.to_3x3()
    loc_ft = P_ft.to_3x3().inverted() @ R_ft
    return dict(thigh=_euler_deg(loc_th), shin=_euler_deg(loc_sh), foot=_euler_deg(loc_ft), reach=reach,
                dist=(A - H).length)


def _set_vis(name, visible):
    ob = bpy.data.objects.get(name)
    if ob is not None:
        ob.hide_render = ob.hide_viewport = not visible


def _ctrl_spec_for(char, ctrl):
    """Resolve a ctrl spec for `char` (per-character entries, height scaling of SHINOBI-authored positions)."""
    if ctrl is None:
        return None
    if char in ctrl:
        return dict(ctrl[char], scale=False)
    return ctrl


def apply_pose(rig, spec, update=True):
    """Set a pose spec on `rig` WITHOUT keys (atlas / previews / tests). spec keys (all optional):
      body: {bone: (rx, ry, rz) deg}        (bone keys may also sit at the top level of spec)
      hips_offset: (x, y, z) hips.location (bone-local: x = left, y = up, z = forward)
      legs: {'L'|'R': dict(ankle=(x,y,z) rig space, knee_dir=None, foot_yaw=0, foot_pitch=0, toe=(rx,ry,rz))}
            -> solve_leg() fills thigh/shin/foot
      ctrl: None (FK arm, katana sheathed) | dict(loc=(x,y,z), rot=(rx,ry,rz) deg) | dict(grip=, dir=, edge=)
            in RIG space, authored in SHINOBI metres and scaled by height for the SAINT unless scale=False;
            or {'SHINOBI': {...}, 'SAINT': {...}} per character;
            or "sheathed": right fist on the hilt of the SHEATHED katana (sheathed_ctrl_matrix; blade stays in)
      two_hand: bool (= left 'grip') ; left: 'free' | 'grip' | 'saya' (overrides two_hand)
      weapon: 'katana' | 'spear' (SAINT) ; spear_grip: (grip_R, grip_L) fist positions from the butt
      saya: (pull, roll) scabbard saya-biki (key_saya semantics) ; hat_tilt: (pitch, roll) (SAINT, set_hat_tilt)
      elbow: {'R'|'L': (x, y, z) rig-space pole point (SHINOBI metres, scaled) | 'auto'} (key_elbow / auto_elbow)
      hide: [object names] hidden for this pose (e.g. ["SAINT_haori"] to judge the legs)"""
    rig = get_rig(rig)
    char = _prefix(rig)
    body = dict(spec.get("body", {}))
    body.update({k: v for k, v in spec.items() if k in rig.pose.bones})
    body = {k: tuple(v) for k, v in body.items()                  # ignore metadata / unknown bones
            if k in rig.pose.bones and isinstance(v, (tuple, list)) and len(v) == 3}
    for pb in rig.pose.bones:
        pb.rotation_euler = (0.0, 0.0, 0.0)
        pb.location = (0.0, 0.0, 0.0)
    hips_offset = tuple(spec.get("hips_offset", (0.0, 0.0, 0.0)))
    rig.pose.bones["hips"].location = hips_offset
    for b, r in body.items():
        rig.pose.bones[b].rotation_euler = tuple(math.radians(a) for a in r)
    s = _scale(char)
    for side, leg in (spec.get("legs") or {}).items():
        ank = Vector(leg["ankle"]) * (s if leg.get("scale", True) else 1.0)
        sol = solve_leg(rig, side, ank, hips_rot=body.get("hips", (0, 0, 0)), hips_offset=hips_offset,
                        knee_dir=leg.get("knee_dir"), foot_yaw=leg.get("foot_yaw", 0.0),
                        foot_pitch=leg.get("foot_pitch", 0.0))
        for part in ("thigh", "shin", "foot"):
            rig.pose.bones[f"{part}.{side}"].rotation_euler = tuple(math.radians(a) for a in sol[part])
        if "toe" in leg:
            rig.pose.bones[f"toe.{side}"].rotation_euler = tuple(math.radians(a) for a in leg["toe"])
    # scabbard / hat placement (static, reset to rest unless given)
    pull, roll = spec.get("saya", (0.0, 0.0))
    _obj(f"{char}_saya").matrix_basis = saya_basis(rig, pull, roll)
    if char == "SAINT":
        hp, hr = spec.get("hat_tilt", (0.0, 0.0))
        hat = _obj("SAINT_hat")
        hat.matrix_basis = _flat_to_matrix(list(hat["rest_basis"])) @ Matrix.Rotation(math.radians(-hp), 4, 'X') \
            @ Matrix.Rotation(math.radians(hr), 4, 'Y')
    weapon = spec.get("weapon", "katana")
    raw_ctrl = spec.get("ctrl")
    sheathed = raw_ctrl == "sheathed"
    ctrl = None if sheathed else _ctrl_spec_for(char, raw_ctrl)
    on = ctrl is not None                       # weapon in hand
    ik_on = on or sheathed                      # right arm in IK
    if char == "SAINT":
        spear = weapon == "spear" and on
        _set_vis("SAINT_spear_hand", spear)
        _set_vis("SAINT_spear_slung", not spear)
        _set_vis("SAINT_spear_world", False)
        _set_vis("SAINT_spear_sheath_world", False)
        _set_vis("SAINT_katana_hand", on and not spear)
        _set_vis("SAINT_katana_hand_tip", on and not spear)
        _set_vis("SAINT_katana_sheathed", not (on and not spear))
        rig["active_weapon"] = 1 if spear else 0
        if spec.get("spear_grip"):
            gR, gL = spec["spear_grip"]
            sh = _obj("SAINT_spear_hand")
            sh.location.y = -rig.data.bones["weapon.R"].length - gR
            gl = _obj("SAINT_grip_L_spear")
            gl.location.y = gL + gl.get("fist_offset", 0.0)
    else:
        _set_vis(f"{char}_katana_hand", on)
        _set_vis(f"{char}_katana_sheathed", not on)
    for bone, cn in (("forearm.R", "IK_sword"), ("hand.R", "COPYROT_sword")):
        _con(rig, bone, cn).influence = 1.0 if ik_on else 0.0
    if on:
        k = s if ctrl.get("scale", True) else 1.0
        if "grip" in ctrl:
            M = blade_frame(Vector(ctrl["grip"]) * k, ctrl["dir"], ctrl.get("edge"))
        else:
            M = Matrix.Translation(Vector(ctrl["loc"]) * k) @ \
                Euler(tuple(math.radians(a) for a in ctrl["rot"]), 'XYZ').to_matrix().to_4x4()
        _obj(f"{char}_sword_ctrl").matrix_basis = M
    # left hand target
    left = spec.get("left") or ("grip" if spec.get("two_hand") else "free")
    if left == "grip" and not on:
        left = "free"
    want = {"grip": "grip:spear" if (char == "SAINT" and weapon == "spear") else "grip:katana",
            "saya": "saya", "free": None}[left]
    for bone, cn, v in (("forearm.L", "IK_grip", want == "grip:katana"), ("hand.L", "COPYROT_grip", want == "grip:katana"),
                        ("forearm.L", "IK_alt", want in ("grip:spear", "saya")),
                        ("hand.L", "COPYROT_alt", want in ("grip:spear", "saya"))):
        _con(rig, bone, cn).influence = 1.0 if v else 0.0
    for obn in (f"{char}_hand_L_target", f"{char}_pole_L_alt"):
        for key in ("saya", "spear"):
            con = _obj(obn).constraints.get(f"TGT_{key}")
            if con is not None:
                con.influence = 1.0 if want in (key, f"grip:{key}") else 0.0
    rig["left_hand"] = LEFT_MODES.index(left)
    rig["two_hand"] = 1 if left == "grip" else 0
    for ob in spec.get("hide", ()):
        _set_vis(ob, False)
    # elbow overrides off unless requested
    for sd in ("R", "L"):
        for pole in _side_poles(rig, sd):
            con = pole.constraints.get("POLE_override")
            if con is not None:
                con.influence = 0.0
    if sheathed or spec.get("elbow"):
        bpy.context.view_layer.update()
    if sheathed:                                 # the scabbard follows the posed hips: evaluate, then grab the hilt
        _obj(f"{char}_sword_ctrl").matrix_basis = sheathed_ctrl_matrix(rig, None)
    for sd, val in (spec.get("elbow") or {}).items():
        if isinstance(val, str) and val == "auto":
            auto_elbow(rig, None, sd, key=True)
        else:
            el = _obj(f"{char}_elbow_{sd}")
            el.location = Vector(val) * s
            for pole in _side_poles(rig, sd):
                con = pole.constraints.get("POLE_override")
                if con is not None:
                    con.influence = 1.0
    if update:
        bpy.context.view_layer.update()
    return rig


def _swing_twist(R, axis=Vector((0.0, 1.0, 0.0))):
    """Decompose rotation matrix R (3x3) into swing (deg) and twist about `axis` (deg, signed)."""
    q = R.to_quaternion()
    p = Vector((q.x, q.y, q.z))
    proj = axis * p.dot(axis)
    tw = Quaternion((q.w, proj.x, proj.y, proj.z))
    if tw.magnitude < 1e-9:
        twist = 180.0
        tw = Quaternion((1, 0, 0, 0))
    else:
        tw.normalize()
        twist = math.degrees(2.0 * math.atan2(Vector((tw.x, tw.y, tw.z)).dot(axis), tw.w))
    sw = q @ tw.inverted()
    swing = math.degrees(2.0 * math.acos(max(-1.0, min(1.0, abs(sw.w)))))
    if twist > 180:
        twist -= 360
    if twist < -180:
        twist += 360
    return swing, twist


def wrist_report(rig, frame=None, update=True):
    """Evaluated joint angles for QA (degrees), per side dict(
        wrist_swing  hand vs forearm bend (flexion/extension + deviation magnitude),
        flexion      signed flexion component (+ towards the palm), deviation (signed, +Z of the hand bone),
        wrist_twist  hand vs forearm twist relative to the rest relation = the anatomical pronation/supination the
                     forearm has to deliver (rest = neutral, palm facing the thigh),
        cuff_twist   hand vs forearm_twist (what the distal forearm skin/guard shows after the twist helper),
        elbow        elbow flexion from straight, forearm_twist (forearm vs upper arm; ~0: hinge)).
    frame=None -> current state (update=False skips the depsgraph update when the caller just did it)."""
    rig = get_rig(rig)
    if frame is not None:
        U.frame_set(frame)
    elif update:
        bpy.context.view_layer.update()
    out = {}
    B, P = rig.data.bones, rig.pose.bones

    def rel(parent, child):
        rest = B[parent].matrix_local.to_3x3().inverted() @ B[child].matrix_local.to_3x3()
        pose = P[parent].matrix.to_3x3().inverted() @ P[child].matrix.to_3x3()
        return rest.inverted() @ pose
    for side in ("L", "R"):
        fa, ha, ua, tw = f"forearm.{side}", f"hand.{side}", f"upper_arm.{side}", f"forearm_twist.{side}"
        R = rel(fa, ha)
        ws, wt = _swing_twist(R)
        # swing axis (in the hand's rest frame, XZ plane) -> signed flexion (X) / deviation (Z) components
        q = R.to_quaternion()
        tq = Quaternion((q.w, 0.0, q.y, 0.0))
        if tq.magnitude > 1e-9:
            tq.normalize()
        sw = q @ tq.inverted()
        ax = Vector((sw.x, sw.y, sw.z))
        ang = 2.0 * math.degrees(math.atan2(ax.length, abs(sw.w)))
        ax = ax.normalized() * (1.0 if sw.w >= 0 else -1.0) if ax.length > 1e-9 else Vector((0.0, 0.0, 0.0))
        es, et = _swing_twist(rel(ua, fa))
        ey = (P[ua].matrix.to_3x3().col[1]).angle(P[fa].matrix.to_3x3().col[1])
        ct = _swing_twist(rel(tw, ha))[1] if tw in P else wt
        out[side] = dict(wrist_swing=round(ws, 1), flexion=round(ang * ax.x, 1), deviation=round(ang * ax.z, 1),
                         wrist_twist=round(wt, 1), cuff_twist=round(ct, 1), elbow=round(math.degrees(ey), 1),
                         forearm_twist=round(et, 1))
    return out


WRIST_LIMITS = dict(swing=75.0, twist=100.0)    # QA: wrist bend magnitude / forearm pronation-supination (deg)


def wrist_issues(rig, frame=None, sides=("L", "R"), max_swing=None, max_twist=None, update=True):
    """List of human-readable wrist problems at `frame` (empty = anatomically plausible): swing > max_swing or
    |twist| > max_twist (defaults WRIST_LIMITS) on the given sides."""
    ms = WRIST_LIMITS["swing"] if max_swing is None else max_swing
    mt = WRIST_LIMITS["twist"] if max_twist is None else max_twist
    w = wrist_report(rig, frame, update=update)
    out = []
    for sd in sides:
        if w[sd]["wrist_swing"] > ms:
            out.append(f"{sd} wrist swing {w[sd]['wrist_swing']:.0f}>{ms:.0f}")
        if abs(w[sd]["wrist_twist"]) > mt:
            out.append(f"{sd} wrist twist {w[sd]['wrist_twist']:.0f}>{mt:.0f}")
    return out


def wrist_ok(rig, frame=None, sides=("L", "R"), max_swing=None, max_twist=None):
    """True when no wrist exceeds WRIST_LIMITS (swing 75 deg, |twist| 100 deg) - the QA gate next to reach_ok."""
    return not wrist_issues(rig, frame, sides, max_swing, max_twist)


# ---------------------------------------------------------------------------------------------- elbow override
def _side_poles(rig, side):
    c = _prefix(rig)
    names = [f"{c}_pole_R"] if side == "R" else [f"{c}_pole_L", f"{c}_pole_L_saya", "SAINT_pole_L_spear"]
    return [bpy.data.objects[n] for n in names if n in bpy.data.objects and (c == "SAINT" or not n.startswith("SAINT"))]


def key_elbow(rig, frame, side="R", point=None, influence=1.0, blend=0, space='WORLD'):
    """Override the automatic elbow pole of `side` at `frame`: the elbow bends towards `point` (the pole position;
    'WORLD' or 'RIG' space), e.g. to open a cramped elbow or to pick the low-twist elbow of a grab (auto_elbow).
    Keys <C>_elbow_<side>.location (BEZIER, so successive points glide) and the POLE_override influence of every
    pole of that side (CONSTANT, or a `blend`-frame fade). influence=0 hands the elbow back (release_elbow)."""
    rig = get_rig(rig)
    el = _obj(f"{_prefix(rig)}_elbow_{side}")
    if point is not None:
        pt = Vector(point)
        if space == 'WORLD':
            pt = U.world_matrix_of(rig, frame).inverted() @ pt
        U.key(el, "location", frame, tuple(pt), interp='BEZIER')
    for pole in _side_poles(rig, side):
        con = pole.constraints.get("POLE_override")
        if con is not None:
            _key_switch(con, "influence", frame, float(influence), blend)


def release_elbow(rig, frame, side="R", blend=0):
    """Hand the elbow of `side` back to the automatic hybrid pole at `frame` (optionally fading over `blend`)."""
    key_elbow(rig, frame, side, None, 0.0, blend)


def _active_arm_target(rig, side):
    """World-space IK target object of the side's active arm IK (None when that arm is FK)."""
    c = _prefix(rig)
    if side == "R":
        con = _con(rig, "forearm.R", "IK_sword")
        return con.target if con.influence > 0.5 else None
    for cn in ("IK_grip", "IK_alt"):
        con = _con(rig, "forearm.L", cn)
        if con.influence > 0.5:
            return con.target
    return None


def auto_elbow(rig, frame=None, side="R", key=True, step=10.0, blend=0):
    """Pick the elbow direction with the least wrist strain for the CURRENT hand target of `side` (scan of the pole
    around the shoulder-wrist axis every `step` deg; cost = wrist swing beyond 35 deg + |twist| beyond 45 deg, with
    penalties for an elbow pointing up or into the torso) and, key=True, key it with key_elbow at `frame`.
    Use it on grabs / planted-sword kneels / cramped guards, then release_elbow when the arm is free again.
    Returns dict(point (world), wrist (wrist_report of that side), before (wrist_report without override), cost)."""
    rig = get_rig(rig)
    c = _prefix(rig)
    if frame is not None:
        U.frame_set(frame)
    else:
        bpy.context.view_layer.update()
    tgt = _active_arm_target(rig, side)
    if tgt is None:
        return None
    before = wrist_report(rig, None, update=False)[side]
    el = _obj(f"{c}_elbow_{side}")
    poles = _side_poles(rig, side)
    cons = [p.constraints.get("POLE_override") for p in poles]
    saved = (el.location.copy(), [cn.influence for cn in cons if cn is not None])
    Mw = rig.matrix_world
    S = Mw @ rig.pose.bones[f"upper_arm.{side}"].head
    W = U.world_pos_of(tgt)
    axis = (W - S).normalized()
    up = Mw.to_3x3() @ UP
    e1 = up - axis * up.dot(axis)
    if e1.length < 1e-3:
        e1 = (Mw.to_3x3() @ FWD) - axis * (Mw.to_3x3() @ FWD).dot(axis)
    e1.normalize()
    e2 = axis.cross(e1)
    medial = Mw.to_3x3() @ (LEFT if side == "R" else -LEFT)
    mid = (S + W) * 0.5
    R = 0.45 * _scale(c)
    best = None
    for cn in cons:
        if cn is not None:
            cn.influence = 1.0
    for i in range(int(round(360.0 / step))):
        ph = math.radians(i * step)
        d = e1 * math.cos(ph) + e2 * math.sin(ph)
        P = mid + d * R
        el.location = Mw.inverted() @ P
        bpy.context.view_layer.update()
        w = wrist_report(rig, None, update=False)[side]
        cost = (max(0.0, w["wrist_swing"] - 35.0) ** 2 + 0.6 * max(0.0, abs(w["wrist_twist"]) - 45.0) ** 2
                + 4000.0 * max(0.0, d.dot(up) - 0.35) ** 2 + 4000.0 * max(0.0, d.dot(medial) - 0.55) ** 2)
        if best is None or cost < best[0] - 1e-9:
            best = (cost, P.copy(), w, i * step)
    el.location = saved[0]
    for cn, v in zip([cn for cn in cons if cn is not None], saved[1]):
        cn.influence = v
    bpy.context.view_layer.update()
    if key and frame is not None:
        key_elbow(rig, frame, side, best[1], 1.0, blend)
    elif key:
        el.location = Mw.inverted() @ best[1]
        for cn in cons:
            if cn is not None:
                cn.influence = 1.0
        bpy.context.view_layer.update()
    return dict(point=best[1], wrist=best[2], before=before, cost=round(best[0], 1), phi=best[3])


# ---------------------------------------------------------------------------------------------- hat clearance
HAT_CLEAR_RADII = dict(forearm=0.05, blade=0.025, spear=0.02, sheath=0.03)


def _hat_points(M, n=72):
    """World sample points of the hat surface (5 profile rings x n azimuths) for world matrix M."""
    D = DIMS["SAINT"]
    R, h = D["hat_diameter"] * 0.5, D["hat_height"]
    rings = [(0.0, h), (0.10 * R, h * 0.93), (0.45 * R, h * 0.56), (0.85 * R, h * 0.13), (R, -0.012)]
    a = np.linspace(0.0, 2.0 * math.pi, n, endpoint=False)
    pts = np.concatenate([np.stack([rr * np.cos(a), rr * np.sin(a), np.full(n, z)], axis=1) for rr, z in rings])
    Mn = np.array(M)
    return pts @ Mn[:3, :3].T + Mn[:3, 3]


def _pts_seg_dist(P, a, b):
    a, b = np.array(a), np.array(b)
    ab = b - a
    t = np.clip(((P - a) @ ab) / max(ab @ ab, 1e-12), 0.0, 1.0)
    return float(np.min(np.linalg.norm(P - (a + np.outer(t, ab)), axis=1)))


def hat_clearance(frame=None):
    """Clearance (m, surface to surface with HAT_CLEAR_RADII) between the worn SAINT_hat and his forearms, the
    in-hand katana / spear and the slung spear at `frame` (None = current). {} when the hat is not worn.
    Negative = interpenetration. Watch it in jodan with the hat on (S13 before 1420) and in the S04 head lift."""
    rig = _obj("SAINT_rig")
    if frame is not None:
        U.frame_set(frame)
    else:
        bpy.context.view_layer.update()
    hat = _obj("SAINT_hat")
    if hat.hide_render:
        return {}
    P = _hat_points(hat.matrix_world)
    Mw = rig.matrix_world
    out = {}
    for sd in ("L", "R"):
        pb = rig.pose.bones[f"forearm.{sd}"]
        out[f"forearm.{sd}"] = _pts_seg_dist(P, Mw @ pb.head, Mw @ pb.tail) - HAT_CLEAR_RADII["forearm"]
    kh = _obj("SAINT_katana_hand")
    if not kh.hide_render:
        M = kh.matrix_world
        D = DIMS["SAINT"]
        y0 = D["grip_to_tsuba"] - D["tsuba_thickness"] * 0.5 - D["tsuka_length"]
        out["katana"] = _pts_seg_dist(P, M @ Vector((0, y0, 0)), U.world_pos_of(_obj("SAINT_katana_tip"))) \
            - HAT_CLEAR_RADII["blade"]
    for nm, key, r in (("SAINT_spear_hand", "spear", "spear"), ("SAINT_spear_slung", "spear_slung", "sheath")):
        ob = _obj(nm)
        if not ob.hide_render:
            M = ob.matrix_world
            out[key] = _pts_seg_dist(P, M @ Vector((0, 0, 0)), M @ Vector((0, DIMS["SAINT"]["spear_length"], 0))) \
                - HAT_CLEAR_RADII[r]
    return out


def hat_ok(frame=None, min_clear=0.01):
    """True when the worn hat clears forearms / weapons by >= min_clear metres (always True with the hat off)."""
    c = hat_clearance(frame)
    return all(v >= min_clear for v in c.values())


# =============================================================================================
# secondary motion: lagged springs for hachimaki tails, beard (+cord), sleeves, hem
# =============================================================================================
WIND_SPEED = 3.0            # m/s of air at wind strength 1.0 (environment.set_wind scale: 1 breeze, 2 gale)
DEFAULT_WIND_HEADING = config.WIND_DIR_DEFAULT  # compass deg the wind blows TOWARD when wind is a float
SECONDARY_CHAINS = {
    # k: spring towards the (gravity-aware) target shape per particle (1/s^2); hang: per segment, how far the
    # target direction is turned from the parent-relative rest direction towards world DOWN (0 = keeps the rest
    # shape relative to the parent, 1 = hangs straight down) - cloth hangs, hair keeps its shape; damp: velocity
    # damping (1/s); drag: air coupling (1/s); grav: gravity scale; flutter: fx_time wind turbulence;
    # colliders: [(bone, t along bone, forward offset (m), radius (m))]
    "SHINOBI": [
        dict(bones=["tail1.1", "tail1.2", "tail1.3", "tail1.4"], k=(8.0, 4.0, 2.5, 2.0), hang=(0.5, 0.8, 0.95, 1.0),
             damp=2.2, drag=3.2, grav=0.9, flutter=1.0,
             colliders=[("head", 0.45, 0.012, 0.10), ("chest", 0.75, 0.0, 0.14)]),
        dict(bones=["tail2.1", "tail2.2", "tail2.3", "tail2.4"], k=(8.0, 4.0, 2.5, 2.0), hang=(0.5, 0.8, 0.95, 1.0),
             damp=2.2, drag=3.2, grav=0.9, flutter=1.0,
             colliders=[("head", 0.45, 0.012, 0.10), ("chest", 0.75, 0.0, 0.14)]),
    ],
    "SAINT": [
        dict(bones=["beard.1", "beard.2", "beard.3"], k=(60.0, 40.0, 28.0), hang=(0.0, 0.1, 0.2), damp=5.0,
             drag=1.2, grav=0.6, flutter=0.5, colliders=[("chest", 0.80, 0.0, 0.16)]),
        dict(bones=["sleeve.L"], k=(10.0,), hang=(0.9,), damp=4.0, drag=1.4, grav=0.9, flutter=0.6, colliders=[]),
        dict(bones=["sleeve.R"], k=(10.0,), hang=(0.9,), damp=4.0, drag=1.4, grav=0.9, flutter=0.6, colliders=[]),
        dict(bones=["hem.L"], k=(35.0,), hang=(0.5,), damp=5.0, drag=1.0, grav=0.6, flutter=0.5, colliders=[]),
        dict(bones=["hem.R"], k=(35.0,), hang=(0.5,), damp=5.0, drag=1.0, grav=0.6, flutter=0.5, colliders=[]),
        dict(bones=["hem.B"], k=(35.0,), hang=(0.5,), damp=5.0, drag=1.0, grav=0.6, flutter=0.5, colliders=[]),
    ],
}
# wet cloth / hair (rain, S20-S26 "soaked and hanging"): heavier (springs and air coupling / mass), more damped,
# hangs straighter, no flutter.  wetness w in 0..1 scales these (see _chain_params).
WET = dict(mass=1.5, damp=0.8, hang=0.85, flutter=0.85)
PREROLL_DAMP = 8.0          # extra damping (1/s) at the start of a cut's pre-roll, faded out by 2/3 of it
_SAMPLE_CACHE = {}


def _chain_params(ch, w):
    """Effective spring parameters of chain `ch` at wetness w (0 dry .. 1 soaked)."""
    w = min(1.0, max(0.0, float(w or 0.0)))
    n = len(ch["bones"])
    hang = ch.get("hang", (0.0,) * n)
    m = 1.0 + WET["mass"] * w
    return dict(k=tuple(k / m for k in ch["k"]), drag=ch["drag"] / m, damp=ch["damp"] * (1.0 + WET["damp"] * w),
                hang=tuple(h + (1.0 - h) * WET["hang"] * w for h in hang), grav=ch["grav"],
                flutter=ch["flutter"] * (1.0 - WET["flutter"] * w))


def env_wetness(frame):
    """Environment wetness 0..1 at `frame` (world["env_wet"] keyed by environment.set_wetness; earlier lanes'
    NLA strips included). 0 when the environment has no wetness channel."""
    w = bpy.context.scene.world
    if w is None or "env_wet" not in w:
        return 0.0
    return float(_fc_value(w, '["env_wet"]', frame, w.get("env_wet", 0.0)))


def _wetness_fn(wetness):
    """wetness: None -> env_wetness (the environment's keyed wetness), float, or callable(frame) -> float."""
    if wetness is None:
        cache = {}

        def fn(f):
            f = int(round(f))
            if f not in cache:
                cache[f] = env_wetness(f)
            return cache[f]
        return fn
    if callable(wetness):
        return wetness
    return lambda f, _w=float(wetness): _w


def _wind_vector(wind, frame):
    """World wind velocity (m/s) at `frame` from wind = float strength | callable(frame) -> float |
    (strength, (dx, dy)) | (vx, vy, vz)."""
    w = wind(frame) if callable(wind) else wind
    if isinstance(w, (int, float)):
        hd = math.radians(DEFAULT_WIND_HEADING)
        return Vector((math.sin(hd), math.cos(hd), 0.0)) * (float(w) * WIND_SPEED)
    if len(w) == 2:
        st, (dx, dy) = w
        return Vector((dx, dy, 0.0)).normalized() * (float(st) * WIND_SPEED)
    return Vector(w) * WIND_SPEED


def secondary_cuts(f0, f1, scene=None):
    """Hard-cut frames in (f0, f1]: timeline markers (shot + sub-cut cameras) and config shot starts."""
    sc = scene or bpy.context.scene
    cuts = {m.frame for m in sc.timeline_markers if f0 < m.frame <= f1}
    cuts |= {s["start"] for s in config.SHOTS if f0 < s["start"] <= f1}
    return sorted(cuts)


def _chain_bones_to_sample(r):
    """Parent bones + collider bones needed by the rig's secondary chains."""
    need = set()
    for ch in SECONDARY_CHAINS[r["char"]]:
        if all(b in r.data.bones for b in ch["bones"]):
            need.add(r.data.bones[ch["bones"][0]].parent.name)
            need |= {c[0] for c in ch["colliders"]}
    return sorted(need)


def _anim_fingerprint(scene=None):
    """Cheap checksum of everything that can move a rig's bones: every action's F-curve keys, every object's NLA
    layout / active action, static object transforms, static pose-bone transforms and constraint influences.
    Used to invalidate the anchor-sampling cache when the animation changed between two calls."""
    # the '<rig>_secondary' output itself is excluded (it never moves an anchor bone), so the second rig's call
    # for the same span still hits the cache after the first rig wrote its keys
    crc = zlib.crc32(str((scene or bpy.context.scene).as_pointer()).encode())
    sec = {b for bl in SECONDARY_BONES.values() for b in bl}
    for act in bpy.data.actions:
        if act.name.endswith("_secondary"):
            continue
        crc = zlib.crc32(act.name.encode(), crc)
        for layer in getattr(act, "layers", ()):
            for strip in layer.strips:
                for cb in getattr(strip, "channelbags", ()):
                    for fc in cb.fcurves:
                        n = len(fc.keyframe_points)
                        buf = np.zeros(n * 2, dtype=np.float32)
                        if n:
                            fc.keyframe_points.foreach_get("co", buf)
                        crc = zlib.crc32(fc.data_path.encode() + bytes([fc.array_index % 256]) + buf.tobytes()
                                         + bytes([int(fc.mute)]), crc)
    for ob in bpy.data.objects:
        vals = [v for row in ob.matrix_basis for v in row]
        ad = ob.animation_data
        if ad is not None:
            crc = zlib.crc32(((ad.action.name if ad.action else "") + str(ad.action_slot)).encode(), crc)
            for tr in ad.nla_tracks:
                if "secondary" in tr.name:
                    continue
                for st in tr.strips:
                    crc = zlib.crc32(f"{tr.name}|{tr.mute}|{st.name}|{st.action.name if st.action else ''}|"
                                     f"{st.frame_start:.3f}|{st.frame_end:.3f}|{st.action_frame_start:.3f}|"
                                     f"{st.extrapolation}|{st.mute}|{st.influence:.4f}".encode(), crc)
        vals += [c.influence for c in ob.constraints]
        if ob.pose is not None:
            for pb in ob.pose.bones:
                if pb.name in sec:
                    continue
                vals += [v for row in pb.matrix_basis for v in row]
                vals += [c.influence for c in pb.constraints]
        crc = zlib.crc32(ob.name.encode() + np.asarray(vals, dtype=np.float32).tobytes(), crc)
    return crc


def _sample_anchors(f0, f1, rigs=None):
    """World matrices of the secondary chains' parent + collider bones, frames f0..f1 (one frame_set per frame).
    rigs=None -> every character rig in the file; the result is cached for the per-rig calls of the same span
    (build_scene calls apply_secondary_motion once per rig) under (scene, f0, f1, _anim_fingerprint()), so a
    re-run after the animation changed (or in a new scene) re-samples instead of reusing stale anchors."""
    sc = bpy.context.scene
    all_rigs = [o for o in bpy.data.objects if o.type == 'ARMATURE' and o.get("char") in CHARS]
    rigs = all_rigs if rigs is None else list(rigs)
    key = (sc.as_pointer(), int(f0), int(f1), tuple(sorted(r.name for r in rigs)))
    fp = _anim_fingerprint(sc)
    hit = _SAMPLE_CACHE.get(key)
    if hit is not None and hit["fingerprint"] == fp:
        return hit
    _SAMPLE_CACHE.clear()                           # one live entry at a time (spans are sampled in order)
    want = {r.name: _chain_bones_to_sample(r) for r in rigs}
    data = {r.name: {a: [] for a in want[r.name]} for r in rigs}
    fcur = sc.frame_current
    for f in range(int(f0), int(f1) + 1):
        U.frame_set(f)
        for r in rigs:
            Mw = r.matrix_world
            for a in want[r.name]:
                data[r.name][a].append(Mw @ r.pose.bones[a].matrix)
    U.frame_set(fcur)
    entry = dict(data=data, left=set(data), fingerprint=_anim_fingerprint(sc), key=key)
    _SAMPLE_CACHE[key] = entry
    return entry


def _simulate_chain(rig, ch, anchors, frames, cuts, wind, preroll, substeps, wet=None):
    """One particle chain, follow-the-leader position-based dynamics.
    The spring target of each joint is the rest shape carried by the evaluated parent bone, with every segment
    direction turned towards world DOWN by the chain's `hang` factor (cloth hangs whatever the head/arm does);
    `wet` (callable frame -> 0..1) makes the chain heavier / more damped / straighter-hanging (_chain_params).
    Returns {bone: [3x3 local rotation Matrix per frame]} (rotation relative to the bone's rest pose)."""
    import fxclock
    B = rig.data.bones
    bones = ch["bones"]
    n = len(bones)
    parent = B[bones[0]].parent.name
    Pinv = B[parent].matrix_local.inverted()
    rest = [Pinv @ B[bones[0]].head_local] + [Pinv @ B[b].tail_local for b in bones]   # in the parent frame
    lens = [B[b].length for b in bones]
    Lrel = [B[b].parent.matrix_local.inverted() @ B[b].matrix_local for b in bones]
    cols = []
    for cb, t, fwd, r in ch["colliders"]:
        hb = B[cb]
        wpt = hb.head_local + (hb.tail_local - hb.head_local) * t + hb.matrix_local.to_3x3().col[2] * fwd
        cols.append((cb, hb.matrix_local.inverted() @ wpt, r))
    seed = zlib.crc32(f"{rig.name}:{bones[0]}".encode())
    ph = [(seed % 997) / 997.0 * 6.283, (seed % 613) / 613.0 * 6.283, (seed % 389) / 389.0 * 6.283]
    fi = {f: i for i, f in enumerate(frames)}
    MA = anchors[parent]
    wet = wet or (lambda f: 0.0)
    down = Vector((0.0, 0.0, -1.0))

    def targets(M, prm):
        """Joint targets: rest shape on the parent frame M, segment directions blended towards DOWN by hang."""
        R = [M @ q for q in rest]
        out = [R[0]]
        for i in range(n):
            d0 = R[i + 1] - R[i]
            d0.normalize()
            h = prm["hang"][i]
            d = d0 * (1.0 - h) + down * h
            if d.length < 1e-3:                            # rest direction straight up and h = 0.5
                d = d0 + Vector((0.0, 0.03, 0.0))
            d.normalize()
            out.append(out[i] + d * lens[i])
        return out

    def collide(P, idx, off=None):
        """Push particles out of the collision spheres (anchors of frame index idx, translated by off)."""
        if not cols:
            return P
        out = [P[0]]
        for p in P[1:]:
            for cb, lp, r in cols:
                c = anchors[cb][idx] @ lp
                if off is not None:
                    c = c + off
                d = p - c
                dl = d.length
                if dl < r:
                    p = c + (d / dl if dl > 1e-9 else Vector((0.0, 0.0, 1.0))) * r
            out.append(p)
        return out

    def air(ft, base, prm):
        """Wind velocity + deterministic flutter on the film clock (fx_time)."""
        t = fxclock.fx_time_at(ft)
        fl = prm["flutter"]
        a = 1.0 + fl * (0.22 * math.sin(4.4 * t + ph[0]) + 0.12 * math.sin(13.1 * t + ph[1]))
        side = Vector((-base.y, base.x, 0.0)) * (0.18 * fl * math.sin(9.7 * t + ph[2]))
        up = Vector((0.0, 0.0, base.length * 0.08 * fl * math.sin(6.3 * t + ph[1])))
        return base * a + side + up

    def step(P, V, T, h, u, prm):
        if h <= 0.0:
            return [T[0]] + P[1:]
        g = Vector((0.0, 0.0, -9.81 * prm["grav"]))
        newP = [T[0]]
        for i in range(1, n + 1):
            acc = (T[i] - P[i]) * prm["k"][i - 1] + g + (u - V[i]) * prm["drag"]
            V[i] = (V[i] + acc * h) * math.exp(-prm["damp"] * h)
            newP.append(P[i] + V[i] * h)
        for i in range(1, n + 1):                      # follow-the-leader: keep the bone lengths
            d = newP[i] - newP[i - 1]
            dl = d.length
            newP[i] = newP[i - 1] + (d / dl if dl > 1e-9 else (T[i] - T[i - 1]).normalized()) * lens[i - 1]
        for i in range(1, n + 1):                      # velocity = actual displacement (PBD)
            V[i] = (newP[i] - P[i]) / h
        return newP

    out = {b: [] for b in bones}
    starts = [frames[0]] + [c for c in cuts if frames[0] < c <= frames[-1]]
    for si, s in enumerate(starts):
        e = starts[si + 1] - 1 if si + 1 < len(starts) else frames[-1]
        i0 = fi[s]
        prm0 = _chain_params(ch, wet(s))
        u0 = _wind_vector(wind, s)
        h0 = 1.0 / (float(config.FPS) * substeps)
        # pre-roll: the cut's first pose, carried at the cut's entry velocity (a walk enters walking - no start
        # transient); damping boosted early in the pre-roll so the chain settles into its wind equilibrium
        vel = Vector((0.0, 0.0, 0.0))
        if s + 1 <= e:
            fxdt = fxclock.fx_time_at(s + 1) - fxclock.fx_time_at(s)
            if fxdt > 1e-6:
                vel = (MA[i0 + 1].translation - MA[i0].translation) / fxdt
        n_pre = int(preroll) * substeps
        T0 = targets(Matrix.Translation(-vel * (n_pre * h0)) @ MA[i0], prm0)
        P = list(T0)
        V = [vel.copy() for _ in P]
        for k in range(n_pre):
            tau = (k + 1 - n_pre) * h0                 # seconds before the cut frame (<= 0)
            T = targets(Matrix.Translation(vel * tau) @ MA[i0], prm0)
            prm = dict(prm0, damp=prm0["damp"] + PREROLL_DAMP * max(0.0, 1.0 - 1.5 * k / n_pre))
            P = collide(step(P, V, T, h0, air(s - preroll + k / substeps, u0, prm0), prm), i0, vel * tau)
        for f in range(s, e + 1):
            idx = fi[f]
            if f > s:
                prm = _chain_params(ch, wet(f))
                Ta, Tb = targets(MA[idx - 1], prm), targets(MA[idx], prm)
                dt = max(0.0, fxclock.fx_time_at(f) - fxclock.fx_time_at(f - 1))
                u = _wind_vector(wind, f)
                for k in range(1, substeps + 1):
                    w = k / substeps
                    T = [a.lerp(b, w) for a, b in zip(Ta, Tb)]
                    P = collide(step(P, V, T, dt / substeps, air(f - 1 + w, u, prm), prm), idx)
            par = MA[idx]
            for j, b in enumerate(bones):             # particle directions -> local rotations
                B0 = par @ Lrel[j]
                R0 = B0.to_3x3().normalized()
                y0 = R0.col[1]
                y1 = (P[j + 1] - P[j]).normalized()
                Rl = R0.inverted() @ y0.rotation_difference(y1).to_matrix() @ R0
                out[b].append(Rl)
                par = B0 @ Rl.to_4x4()
    return out


def _local_push_secondary(rig, action, slot):
    """Put `action` on the TOP NLA track '<rig>_secondary' (create it, or widen its strip to the key range)."""
    from bpy_extras import anim_utils
    name = f"{rig.name}_secondary"
    ad = rig.animation_data or rig.animation_data_create()
    cbag = anim_utils.action_get_channelbag_for_slot(action, slot)
    xs = [k.co.x for fc in cbag.fcurves for k in (fc.keyframe_points[0], fc.keyframe_points[-1])]
    lo, hi = min(xs), max(xs)
    if hi <= lo:
        hi = lo + 1.0
    tr = next((t for t in ad.nla_tracks if t.name == name), None)
    if tr is None:
        tr = ad.nla_tracks.new()
        tr.name = name
        st = tr.strips.new(name, int(math.floor(lo)), action)
    else:
        st = tr.strips[0]
    if st.action_slot != slot:
        st.action_slot = slot
    st.use_sync_length = False
    st.scale = 1.0
    st.repeat = 1.0
    st.frame_end = max(st.frame_end, hi)
    st.frame_start = min(st.frame_start, lo)
    st.action_frame_start = lo
    st.action_frame_end = hi
    st.frame_start = lo
    st.frame_end = hi
    st.extrapolation = 'HOLD'
    st.blend_type = 'REPLACE'
    st.influence = 1.0
    return tr, st


def settle_secondary(rig, wind=0.0, wetness=0.0, preroll=48):
    """Static previews (pose atlas, stills): let the secondary chains settle under gravity/wind for the CURRENT pose and
    write their rotations straight into the pose bones (no keys). Same physics as apply_secondary_motion."""
    rig = get_rig(rig)
    bpy.context.view_layer.update()
    f = bpy.context.scene.frame_current
    need = _chain_bones_to_sample(rig)
    anchors = {a: [rig.matrix_world @ rig.pose.bones[a].matrix] for a in need}
    for ch in SECONDARY_CHAINS[_prefix(rig)]:
        if not all(b in rig.pose.bones for b in ch["bones"]):
            continue
        rots = _simulate_chain(rig, ch, anchors, [f], [], wind, preroll, 4, _wetness_fn(wetness))
        for b, Rs in rots.items():
            rig.pose.bones[b].rotation_euler = Rs[0].to_euler('XYZ')
    bpy.context.view_layer.update()


def apply_secondary_motion(rig, f0, f1, wind=1.0, cuts=None, preroll=None, substeps=4, wetness=None):
    """Procedural lagged springs for the secondary chains (SHINOBI hachimaki tails; SAINT beard (+ the cord riding
    beard.3), sleeve pouches, haori hem) over frames [f0, f1]:
      * rig: one rig (or name) - or a list of rigs, sampled together in ONE pass over the frames;
      * the chains are pinned to their parent bones as EVALUATED at each frame (call after all lanes / NLA assembly,
        inside bl_util.muted_modifiers); springs pull towards the rest shape turned towards world down by each
        chain's `hang` (cloth hangs, hair keeps its shape), gravity, air drag towards the wind velocity with a
        deterministic fx_time flutter, head/chest collision spheres;
      * reset at every hard cut (timeline markers + config shot starts, or `cuts`) with a `preroll`-frame pre-roll
        (None = one second, config.FPS frames) holding the cut's first pose -> no settling transient after a cut;
      * dt per frame = fx_time(f) - fx_time(f-1) (slow-motion windows slow the springs; 0 = frozen);
      * wind: float strength (heading DEFAULT_WIND_HEADING) | callable(frame) -> float | (strength, (dx, dy)) such as
        environment.wind_at | (vx, vy, vz) in units of WIND_SPEED;
      * wetness: None (default) -> the environment's keyed wetness (env_wetness: rain soaks the tails - heavier,
        hanging, no flutter) | float 0..1 | callable(frame) -> float (per-shot override, e.g. S24 soaked = 1.0);
      * keys (LINEAR, every frame) go to action '<rig>_secondary', played by the TOP NLA track of the same name
        (only the secondary bones' rotation channels). Repeated calls for other spans add to the same action.
      * anchor samples are shared between the per-rig calls of the same span only while the animation is
        unchanged (fingerprinted cache), so re-running a span after editing keys always re-samples.
    Returns dict(frames=n, bones=[...], cuts=[...], seconds=t) (a list of those for a list of rigs)."""
    if preroll is None:
        preroll = int(config.FPS)
    if isinstance(rig, (list, tuple)):
        rigs = [get_rig(r) for r in rig]
        f0, f1 = int(f0), int(f1)
        data = _sample_anchors(f0, f1, rigs)["data"]
        _SAMPLE_CACHE.clear()
        return [_secondary_one(r, data[r.name], f0, f1, wind, cuts, preroll, substeps, wetness) for r in rigs]
    rig = get_rig(rig)
    f0, f1 = int(f0), int(f1)
    cache = _sample_anchors(f0, f1)
    anchors = cache["data"][rig.name]
    cache["left"].discard(rig.name)
    if not cache["left"]:
        _SAMPLE_CACHE.clear()
    return _secondary_one(rig, anchors, f0, f1, wind, cuts, preroll, substeps, wetness)


def _secondary_one(rig, anchors, f0, f1, wind, cuts, preroll, substeps, wetness):
    """Simulate + key one rig's secondary chains from pre-sampled anchors (see apply_secondary_motion)."""
    t0 = time.time()
    char = _prefix(rig)
    chains = [c for c in SECONDARY_CHAINS[char] if all(b in rig.pose.bones for b in c["bones"])]
    if not chains:
        return dict(frames=0, bones=[], cuts=[], seconds=0.0)
    frames = list(range(f0, f1 + 1))
    cuts = secondary_cuts(f0, f1) if cuts is None else sorted(c for c in cuts if f0 < c <= f1)
    wet = _wetness_fn(wetness)
    rots = {}
    for ch in chains:
        rots.update(_simulate_chain(rig, ch, anchors, frames, cuts, wind, preroll, substeps, wet))
    # ---- write keys into '<rig>_secondary'
    name = f"{rig.name}_secondary"
    act = bpy.data.actions.get(name) or bpy.data.actions.new(name)
    ad = rig.animation_data or rig.animation_data_create()
    prev_act, prev_slot = ad.action, ad.action_slot
    ad.action = act
    for b, Rs in rots.items():
        prev = Euler((0.0, 0.0, 0.0), 'XYZ')
        E = []
        for R in Rs:
            e = R.to_euler('XYZ', prev)
            E.append(e)
            prev = e
        path = f'pose.bones["{b}"].rotation_euler'
        for i in range(3):
            fc = act.fcurve_ensure_for_datablock(rig, path, index=i, group_name=b)
            kp = fc.keyframe_points
            old = np.zeros(len(kp) * 2)
            if len(kp):
                kp.foreach_get("co", old)
            old = old.reshape(-1, 2)
            old = old[(old[:, 0] < f0 - 1e-3) | (old[:, 0] > f1 + 1e-3)] if len(old) else old.reshape(0, 2)
            new = np.array([(f, e[i]) for f, e in zip(frames, E)])
            allk = np.concatenate([old, new]) if len(old) else new
            allk = allk[np.argsort(allk[:, 0])]
            kp.clear()
            kp.add(len(allk))
            kp.foreach_set("co", allk.ravel())
            kp.foreach_set("interpolation", [1] * len(allk))        # 1 = LINEAR
            fc.update()
    slot = ad.action_slot
    ad.action = prev_act
    if prev_act is not None and prev_slot is not None:
        ad.action_slot = prev_slot
    _local_push_secondary(rig, act, slot)
    return dict(frames=len(frames), bones=sorted(rots), cuts=cuts, seconds=round(time.time() - t0, 3))
