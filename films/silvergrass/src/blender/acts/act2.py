"""
acts/act2.py - lane act2: S15-S20 (frames 1633-2496), Act II "Fire" (docs/shots/act2.md = the binding breakdown).

    Blender -b --factory-startup --python-exit-code 1 --python src/blender/build_scene.py -- --lanes act2 \
        [--quality layout|preview|final]

Story: the spear butt strikes the earth on the downbeat and the field ignites into a ring of fire (S15a top-down);
the master, bare-headed in his white tasuki, twirls the spear while his discarded haori burns (S15b, act card);
the spear drives the student back - a 360 sweep he ducks, three thrusts (deflect, deflect, the third turned by a
kunai as he slides in along the shaft), a shove back out, a low sweep he vaults (S16); his three kunai ring off the
spinning spear, the old man leaps and slams the ground into fire, the student rolls clear (S17); the student slides
under a thrust into close quarters - sword vs shaft on every beat - and is kicked away, braking with his sword in the
dirt (S18); the spear is hurled like a javelin, deflected in slow motion, and cartwheels into the flames; thunder;
the master draws his katana as the first drops hiss on the steel (S19); the downpour drowns the ring in steam and he
lifts his sword into jodan (S20).

Layout of this file: constants (world anchors from the breakdown) -> _local_* helpers (poses, ballistic props, the
through-the-fist spear twirl, the burning haori) -> entering state (HANDOFF[1632]) -> one function per shot (action,
vfx, events of that shot, chronological so macros read the right roots) -> environment -> cameras (23 sub-cuts) ->
build(ctx).  Deviations from the breakdown are listed in docs/shots/act2.md "Implementation notes".
"""
import math
import os
import sys
import zlib

import bpy
from mathutils import Matrix, Vector

ROOT = (__import__("os").environ.get("SILVERGRASS_ROOT") or str(next(p for p in __import__("pathlib").Path(__file__).resolve().parents if (p / "src" / "common" / "config.py").is_file())))   # repo root (portable)
for _p in (os.path.join(ROOT, "src", "common"), os.path.join(ROOT, "src", "blender")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import config  # noqa: E402
import bl_util as U  # noqa: E402
import cameras as CAM  # noqa: E402
import events as EV  # noqa: E402
from acts import sub_cuts  # noqa: E402

LANE = "act2"
SPAN = tuple(config.lane_span(LANE))                   # (1633, 2496)
H_IN = config.HANDOFF[SPAN[0] - 1]                     # HANDOFF[1632]
H_OUT = config.HANDOFF[SPAN[1]]                        # HANDOFF[2496]
F_IGNITE = config.MUSIC_CUES["act2_start"]            # 1633: spear-butt slam = fire_ignite = downbeat
F_THUNDER = config.MUSIC_CUES["thunder_first"]        # 2353
F_RAIN = config.MUSIC_CUES["rain_start"]              # 2401: the downpour hits on the S20 cut

# ---------------------------------------------------------------- world anchors (docs/shots/act2.md, cams.py)
BUTT = (0.08, 6.02, 0.00)          # spear-butt impact 1633
HAORI = (0.80, 4.97, 0.98)         # SAINT_haori_thrown centre on the grass tops (S15 cheat, D2)
IMPACT = (0.10, 1.00, 0.05)        # S17 slam: the spear blade hits the ground 2017
REL = (-0.25, 2.05, 1.95)          # S19 javelin release 2269
DEF = (0.12, -3.45, 1.45)          # S19 deflect 2281
SPEAR_LAND = (-8.40, -5.60, 0.60)  # S19 spear lands in the flames 2329
RING_C = (0.0, 1.5, 0.0)
RING_R = 11.0
HUB = (0.0, 5.15, 1.40)            # S17 spear wheel hub
G = 9.81
VAULT_APEX = 0.72                  # S16d tuck vault apex (root z)

# cut list (id, f0, f1) - every boundary a hard cut (breakdown §3): config shots S15-S20 split at the sub-cut starts
# S15a 1633-1656, S15b 1657-1728, S16a 1729-1776, S16b 1777-1824, S16c 1825-1872, S16d 1873-1920, S17a 1921-1947,
# S17b 1948-1968, S17c 1969-2004, S17d 2005-2020, S17e 2021-2064, S18a 2065-2091, S18b 2092-2115, S18c 2116-2139,
# S18d 2140-2172, S18e 2173-2208, S18f 2209-2256, S19a 2257-2276, S19b 2277-2304, S19c 2305-2352, S19d 2353-2400,
# S20a 2401-2448, S20b 2449-2496
CUTS = sub_cuts(LANE, {"S15": (1657,), "S16": (1777, 1825, 1873), "S17": (1948, 1969, 2005, 2021),
                       "S18": (2092, 2116, 2140, 2173, 2209), "S19": (2277, 2305, 2353), "S20": (2449,)})
CUT = {c: (a, b) for c, a, b in CUTS}

# modules bound in build() (imported late: build_scene may run with placeholders)
M = PZ = CH = ENV = VFX = FXC = None
SH = SA = None
RING = {}
LOG = []


def _log(msg):
    LOG.append(msg)
    print(f"[act2] {msg}")


def _seed(tag):
    """Deterministic seed (zlib.crc32, never hash())."""
    return zlib.crc32(f"act2:{tag}".encode()) & 0x7FFFFFFF


def _fx(f):
    return float(FXC.fx_time_at(float(f)))


# =============================================================================================
# local poses (docs/shots/act2.md §5) - POSES-format specs keyed through moves.pose / poses.key_pose
# =============================================================================================
def _spec(desc="", body=None, hips=(0.0, 0.0, 0.0), legs=None, ctrl=None, left="free", **extra):
    """A POSES-format spec (poses.pose); ctrl dicts may carry "scale": False for exact SAINT metres."""
    return PZ.pose(desc, "act2", body=body, hips=hips, legs=legs, ctrl=ctrl, left=left, **extra)


TUNE = set()        # (rig name, frame) of controller keys made by this lane's poses -> wrist roll tuning
NO_TUNE = []        # (f0, f1) SAINT twirl windows (_local_twirl) excluded from the roll tuning


def _kp(rig, f, spec, **kw):
    """Key a library pose name or a local spec (moves.pose: the lane's left hand is kept unless hands='pose')."""
    sp = PZ.spec_of(spec)
    if not isinstance(spec, str) and kw.get("ctrl", True) and isinstance(sp.get("ctrl"), dict) and "grip" in sp["ctrl"]:
        TUNE.add((rig.name, float(f)))
    return M.pose(rig, f, spec, **kw)


def _local_poses():
    """The act2 pose table (rig space: character faces -Y, his left = +X; SHINOBI metres unless scale False)."""
    T, A, F, B, st, n = PZ.torso, PZ.arm, PZ.foot, PZ.blade, PZ.stance, PZ._norm
    SPg = dict(weapon="spear", hide=["SAINT_hat"])
    P = {}
    # --- SAINT ------------------------------------------------------------------------------------------
    P["butt_slam"] = _spec(
        "spear vertical, butt driven onto BUTT, right fist high", body=T(lean=10, twist=-6, look_pitch=-4),
        hips=(0.0, -0.10, 0.0), legs={"L": F(0.20, -0.20), "R": F(-0.18, 0.24, heel=8)}, left="grip",
        ctrl=None, **SPg)
    P["spear_upright"] = _spec(
        "spear upright beside him, butt on the ground, breathing", body=T(lean=3, twist=-4),
        hips=(0.0, -0.05, 0.0), legs={"L": F(0.16, -0.16), "R": F(-0.16, 0.18, heel=5)}, left="grip", **SPg)
    P["twirl"] = _spec(
        "propeller twirl in front of the chest: right fist at the hub, left arm free for balance",
        body=A("L", flex=35, abd=25, elbow=45) | T(lean=5, twist=-4), hips=(0.0, -0.08, 0.0),
        legs=st(front=0.26, back=0.28, width=0.34, lead="L", heel_back=10),
        ctrl=dict(grip=(-0.06, -0.58, 1.45), dir=(1.0, 0.0, 0.0), edge=(0.0, 0.0, -1.0), scale=False), **SPg)
    P["guard_low"] = _spec(
        "low spear guard: left foot forward, rear fist at the right hip, tip at the shinobi's chest",
        body=T(lean=10, twist=-15), hips=(0.0, -0.12, 0.0),
        legs={"L": F(0.18, -0.35), "R": F(-0.15, 0.30, heel=10, yaw=-20)},
        ctrl=dict(grip=(-0.18, -0.10, 0.95), dir=(0.125, -0.98, 0.156), scale=False), spear_grip=(0.35, 0.95),
        left="grip", **SPg)
    P["sweep_wind"] = _spec(
        "sweep wind-up: fists slid to the butt, spear wound to his right-rear, trunk turned right",
        body=T(lean=8, twist=-40), hips=(0.0, -0.14, 0.0),
        legs=st(front=0.30, back=0.36, width=0.40, lead="L", yaw_back=-30, heel_back=10),
        ctrl=dict(grip=(-0.20, 0.00, 1.40), dir=n((-0.80, 0.58, 0.06)), scale=False), spear_grip=(0.10, 0.30),
        left="grip", **SPg)
    P["sweep_spin"] = _spec(
        "360 sweep: spear rigid, forward-right at shoulder height, fists together at the butt end",
        body=T(lean=6, twist=-28), hips=(0.0, -0.16, 0.0),
        legs=st(front=0.30, back=0.34, width=0.40, lead="L", yaw_back=-20, heel_back=15),
        ctrl=dict(grip=(-0.10, -0.40, 1.40), dir=n((-0.71, -0.70, 0.02)), scale=False), spear_grip=(0.10, 0.30),
        left="grip", **SPg)
    P["thrust_wind"] = _spec(
        "thrust wind-up: rear fist drawn back to the right hip, point level", body=T(lean=6, twist=-26),
        hips=(0.0, -0.13, -0.04), legs=st(front=0.30, back=0.36, width=0.28, lead="L", yaw_back=-25, heel_back=8),
        ctrl=dict(grip=(-0.22, 0.22, 1.08), dir=n((0.02, -1.0, 0.10)), scale=False), spear_grip=(0.35, 0.95),
        left="grip", **SPg)
    P["thrust_ext"] = _spec(
        "thrust: shaft driven through the front hand, deep lunge", body=T(lean=16, twist=-4),
        hips=(0.0, -0.20, 0.05), legs=st(front=0.56, back=0.42, width=0.28, lead="L", yaw_back=-20, heel_back=34),
        ctrl=dict(grip=(-0.10, -0.55, 1.20), dir=n((0.0, -1.0, 0.02)), scale=False), spear_grip=(0.35, 0.62),
        left="grip", **SPg)
    P["staff_block"] = _spec(
        "staff guard: shaft across the body, hands wide", body=T(lean=6, twist=-6), hips=(0.0, -0.12, 0.0),
        legs=st(front=0.28, back=0.32, width=0.34, lead="L", heel_back=12),
        ctrl=dict(grip=(-0.25, -0.30, 1.05), dir=n((0.55, -0.10, 0.83)), scale=False), spear_grip=(0.50, 1.40),
        left="grip", **SPg)
    P["staff_high"] = _spec(
        "staff held horizontal above the head, hands wide (the bind)", body=T(lean=-4, twist=-4, look_pitch=-6),
        hips=(0.0, -0.14, 0.0), legs=st(front=0.30, back=0.34, width=0.34, lead="L", heel_back=12),
        ctrl=dict(grip=(-0.40, -0.25, 1.95), dir=(1.0, 0.0, 0.0), edge=(0.0, 0.0, 1.0), scale=False),
        spear_grip=(0.50, 1.40), left="grip", **SPg)
    P["staff_left"] = _spec(
        "staff block on his LEFT: torso turned left, shaft vertical at his left front, butt down",
        body=T(lean=6, twist=22), hips=(0.0, -0.12, 0.0),
        legs=st(front=0.28, back=0.32, width=0.34, lead="L", heel_back=12),
        ctrl=dict(grip=(0.12, -0.35, 0.97), dir=(0.05, -0.05, 1.0), edge=(0.0, -1.0, 0.0), scale=False),
        spear_grip=(0.62, 1.40), left="grip", **SPg)
    P["low_lunge"] = _spec(
        "low sweep lunge: deep, trunk folded over the front knee, spear flat at shin height",
        body=A("L", flex=25, abd=45, elbow=20) | T(lean=30, twist=-10, look_pitch=-15), hips=(0.0, -0.35, 0.05),
        legs={"L": F(0.30, -0.55), "R": F(-0.25, 0.55, heel=35)},
        ctrl=None, spear_grip=(0.12, 0.60), left="free", **SPg)
    P["spear_overhead"] = _spec(
        "spear raised overhead in both hands, tip forward-up (the menace before the leap)",
        body=T(lean=-6, twist=-4, look_pitch=-4), hips=(0.0, -0.10, 0.0),
        legs=st(front=0.30, back=0.34, width=0.32, lead="L", heel_back=12),
        ctrl=dict(grip=(-0.12, 0.05, 1.80), dir=n((0.0, -0.75, 0.66)), scale=False), spear_grip=(0.20, 0.50),
        left="grip", **SPg)
    P["slam_wind"] = _spec(
        "slam wind-up in the air: spear swung back over the head, head of the spear up-back",
        body=T(lean=-12, look_pitch=-10), hips=(0.0, -0.02, -0.03),
        legs={"L": F(0.14, -0.20, lift=0.25, air=True, heel=20), "R": F(-0.14, 0.18, lift=0.35, air=True, heel=30)},
        ctrl=dict(grip=(-0.10, 0.05, 1.75), dir=n((0.0, 0.6, 0.8)), scale=False), spear_grip=(0.20, 0.50),
        left="grip", **SPg)
    P["slam"] = _spec(
        "slam: landed deep, trunk folded over the spear flat on the ground", body=T(lean=34, look_pitch=-12),
        hips=(0.0, -0.42, 0.05), legs=st(front=0.46, back=0.42, width=0.34, lead="L", heel_back=38),
        ctrl=None, spear_grip=(0.20, 0.50), left="grip", **SPg)
    P["kick_chamber"] = _spec(
        "front kick chamber, spear held high-left in both hands", body=T(lean=-6), hips=(0.0, -0.06, -0.02),
        legs={"L": F(0.10, 0.10, yaw=10), "R": F(-0.10, -0.26, lift=0.55, air=True, heel=30, knee=(0.0, -0.6, 0.8))},
        ctrl=dict(grip=(-0.30, -0.25, 1.25), dir=n((1.0, -0.10, 0.30)), scale=False), spear_grip=(0.50, 1.30),
        left="grip", **SPg)
    P["kick_ext"] = _spec(
        "front push kick: leg driven out at chest height, leaning back", body=T(lean=-15), hips=(0.0, -0.02, 0.10),
        legs={"L": F(0.10, 0.12, yaw=12), "R": F(-0.06, -0.80, lift=1.10, air=True, heel=-40)},
        ctrl=dict(grip=(-0.30, -0.10, 1.30), dir=n((1.0, 0.0, 0.35)), scale=False), spear_grip=(0.50, 1.30),
        left="grip", **SPg)
    P["javelin_ready"] = _spec(
        "javelin ready: spear at the right shoulder at its balance, left arm aimed at the target",
        body=A("L", flex=95, abd=10, elbow=5) | T(lean=-4, twist=-30), hips=(0.0, -0.10, -0.03),
        legs={"L": F(0.15, -0.45), "R": F(-0.12, 0.35, heel=10, yaw=-25)},
        ctrl=dict(grip=(-0.25, 0.25, 1.80), dir=n((0.05, -0.99, 0.12)), scale=False), spear_grip=(1.30, 1.60),
        left="free", **SPg)
    P["javelin_cock"] = _spec(
        "javelin cocked: weight back, spear drawn back past the shoulder", body=A("L", flex=90, abd=15, elbow=8) |
        T(lean=-8, twist=-40), hips=(0.0, -0.12, -0.08), legs={"L": F(0.15, -0.45, heel=15), "R": F(-0.12, 0.35, yaw=-30)},
        ctrl=dict(grip=(-0.30, 0.55, 1.85), dir=n((0.05, -0.99, 0.14)), scale=False), spear_grip=(1.30, 1.60),
        left="free", **SPg)
    P["javelin_release"] = _spec(
        "javelin release: throwing arm high forward, trunk whipped through", body=A("L", flex=-10, abd=25, elbow=40) |
        T(lean=14, twist=18), hips=(0.0, -0.14, 0.06), legs={"L": F(0.15, -0.62), "R": F(-0.12, 0.35, heel=40)},
        ctrl=dict(grip=(-0.25, -0.45, 1.85), dir=n((0.05, -0.99, 0.06)), scale=False), spear_grip=(1.30, 1.60),
        left="free", **SPg)
    P["javelin_follow"] = _spec(
        "follow-through: right arm across the body, trunk turned 35", body=A("R", flex=60, abd=-10, rot=30, elbow=30) |
        A("L", flex=10, abd=20, elbow=40) | T(lean=18, twist=35), hips=(0.0, -0.14, 0.06),
        legs={"L": F(0.15, -0.62), "R": F(-0.12, 0.30, heel=45)}, ctrl=None, arm="fk", left="free")
    P["empty_watch"] = _spec(
        "empty-handed, watching the spear go: upright, right hand open at the side",
        body=A("R", flex=15, abd=-30, elbow=25) | A("L", flex=15, abd=-30, elbow=70) | T(lean=0, twist=-6, look_pitch=-6),
        hips=(0.0, -0.05, 0.0), legs=st(front=0.24, back=0.26, width=0.30, heel_back=6), ctrl=None, arm="fk",
        left="free")
    P["hilt_ready"] = _spec(
        "hand to the hilt: right fist on the sheathed hilt, left hand on the saya", body=T(lean=6, twist=8),
        hips=(0.0, -0.10, 0.0), legs=st(front=0.28, back=0.30, width=0.28, heel_back=12),
        ctrl="sheathed", left="saya", saya=(0.0, 45.0), elbow={"R": "auto", "L": "auto"})
    P["chudan"] = "chudan"
    P["jodan"] = _spec(
        "classical jodan: fists above the forehead, blade 45 deg back-up, left foot forward",
        body=PZ.merge(PZ.GUARD_ARMS, T(lean=-3, twist=-4)), hips=(0.0, -0.06, 0.0),
        legs={"L": F(0.15, -0.40), "R": F(-0.15, 0.25, heel=15)},
        ctrl=dict(grip=(-0.02, -0.12, 2.00), dir=n((0.0, 0.70, 0.71)), edge=n((0.0, -0.71, 0.70)), scale=False),
        left="grip")
    # --- SHINOBI ------------------------------------------------------------------------------------------
    P["slide_duck"] = _spec(
        "sliding duck under the sweep: hips dropped 0.45, torso upright, sword low at his right side (waki)",
        body=T(lean=10, look_pitch=-12), hips=(0.0, -0.36, 0.05),
        legs={"L": F(0.18, -0.45, heel=-10), "R": F(-0.12, 0.35, heel=55)},
        ctrl=B((-0.22, -0.12, 0.88), n((-0.35, 0.80, -0.48))), left="grip")
    P["vault_tuck"] = _spec(
        "tuck vault: knees to the chest, sword up two-handed", body=T(lean=20),
        hips=(0.0, -0.10, 0.0),
        legs={"R": F(-0.12, -0.25, lift=0.52, air=True, heel=20), "L": F(0.12, -0.10, lift=0.48, air=True, heel=25)},
        ctrl=B((0.0, -0.30, 1.35), n((0.0, -0.5, 0.87))), left="grip")
    P["one_hand_high"] = _spec(
        "sword one-handed, cocked high-right; left hand coming off the hilt", body=A("L", flex=40, abd=10, elbow=60) |
        T(lean=8, twist=16), hips=(0.0, -0.14, 0.02), legs=st(front=0.34, back=0.32, width=0.28, heel_back=22),
        ctrl=B((-0.25, 0.10, 1.55), n((0.2, 0.3, 0.93))), left="free")
    P["sash_reach"] = _spec(
        "left hand behind the right hip at the sash, sword high-back one-handed",
        body=A("L", flex=-10, abd=-20, rot=30, elbow=80) | T(lean=10, twist=22), hips=(0.0, -0.15, 0.02),
        legs=st(front=0.34, back=0.32, width=0.28, heel_back=22),
        ctrl=B((-0.25, 0.10, 1.55), n((0.2, 0.3, 0.93))), left="free")
    P["kunai_slide"] = _spec(
        "sliding in along the shaft: left forearm across, kunai on the shaft, sword cocked high-right",
        body=A("L", flex=70, abd=0, rot=20, elbow=45) | T(lean=12, twist=20), hips=(0.0, -0.18, 0.03),
        legs=st(front=0.40, back=0.34, width=0.28, lead="L", heel_back=28),
        ctrl=B((-0.25, 0.10, 1.55), n((0.2, 0.3, 0.93))), left="free")
    P["kneel_guard"] = _spec(
        "one knee down after the roll, sword two-handed, point at the elder", body=T(lean=10, look_pitch=-4),
        hips=(0.0, -0.55, 0.0), legs={"L": F(0.15, -0.35), "R": F(-0.12, 0.40, heel=70)},
        ctrl=B((0.0, -0.30, 0.95), n((0.0, -0.85, 0.53))), left="grip")
    P["knee_slide"] = _spec(
        "knee slide: left shin on the ground leading, leaning back 35, blade across the chest edge-up",
        body=T(lean=-30, look_pitch=12), hips=(0.0, -0.62, 0.0),
        legs={"L": F(0.12, -0.55, heel=-40, lift=0.02), "R": F(-0.14, 0.25, heel=70)},
        ctrl=B((-0.20, -0.20, 0.95), n((0.97, 0.0, 0.26)), edge=(0.0, 0.0, 1.0)), left="grip")
    P["kicked_fold"] = _spec(
        "hit in the chest: folded, head snapped back, arms flung forward-out, knees bent",
        body=A("L", flex=40, abd=60, elbow=20) | T(lean=35, look_pitch=-40, gaze=0.2), hips=(0.0, -0.10, -0.12),
        legs={"R": F(-0.12, -0.30, lift=0.20, air=True, heel=20), "L": F(0.12, -0.10, lift=0.15, air=True, heel=20)},
        ctrl=B((-0.30, 0.05, 1.05), n((-0.3, 0.5, -0.8))), left="free")
    P["skid_drag"] = _spec(
        "skid, sword dragged: crouched low, left hand trailing on the ground, right hand driving the tip into the dirt",
        body=A("L", flex=-20, abd=30, elbow=10) | T(lean=40, twist=25, look_pitch=-30), hips=(0.0, -0.50, -0.10),
        legs={"R": F(-0.14, -0.40, yaw=-20), "L": F(0.20, 0.30, heel=30, yaw=25)},
        ctrl=B((-0.31, 0.14, 0.48), n((-0.32, -0.72, -0.61))), left="free")
    P["deflect_rise_a"] = _spec(
        "rising deflect windup: blade low right, tip down-forward", body=T(lean=10, twist=-18),
        hips=(0.0, -0.16, 0.0), legs=st(front=0.32, back=0.32, width=0.28, heel_back=22),
        ctrl=B((-0.30, -0.25, 0.95), n((-0.5, -0.6, 0.6))), left="grip")
    P["deflect_rise_b"] = _spec(
        "rising deflect: blade crossing up-left through the spear line", body=T(lean=6, twist=10, look_pitch=-8),
        hips=(0.0, -0.14, 0.0), legs=st(front=0.32, back=0.32, width=0.28, heel_back=22),
        ctrl=B((-0.10, -0.40, 1.30), n((0.45, -0.55, 0.70))), left="grip")
    P["deflect_rise_c"] = _spec(
        "rising deflect follow-through: blade high over the left shoulder", body=T(lean=0, twist=24, look_pitch=-16),
        hips=(0.0, -0.12, 0.0), legs=st(front=0.32, back=0.32, width=0.28, heel_back=22),
        ctrl=B((0.10, -0.25, 1.55), n((0.55, 0.10, 0.83))), left="grip")
    return P


POSE = {}


def _pose(rig, f, name, **kw):
    """Key a local pose (POSE table) or a library pose."""
    sp = POSE.get(name, name)
    return _kp(rig, f, sp, **kw)


# =============================================================================================
# local helpers
# =============================================================================================
def _root(rig, f, xy, facing, z=0.0, interp='BEZIER'):
    return M.root(rig, f, xy, facing, z=z, interp=interp)


def _xy(rig, f):
    x, y, _, _ = M.root_at(rig, f)
    return (x, y)


def _world_to_rig(rig, f, p):
    """World point -> rig space of `rig` at frame f (from its keyed root)."""
    return M.rig_matrix(rig, f).inverted() @ Vector(p)


def _key_ctrl_world(rig, f, grip, direction, edge=None, interp='BEZIER'):
    """Controller keyed from a WORLD grip / direction / edge using the rig's KEYED root at f (not the depsgraph)."""
    Mw = CH.blade_frame(Vector(grip), Vector(direction), Vector(edge) if edge is not None else None)
    local = M.rig_matrix(rig, f).inverted() @ Mw
    CH.key_ctrl_matrix(PZ._ctrl_obj(rig), f, local, interp)
    M._ensure_ik(rig, f)
    TUNE.add((rig.name, float(f)))
    return local


def _wrist_cost(rig, f):
    """Anatomy cost of the evaluated arms at f (depsgraph already at f): wrist bend > 55, forearm twist > 70, IK
    residuals (the right arm always; the left when it grips)."""
    w = CH.wrist_report(rig, update=False)
    rr = CH.reach_report(rig)
    cost = 0.0
    sides = ["R"] + (["L"] if CH.left_hand(rig, f) == "grip" else [])
    for sd in sides:
        cost += max(0.0, w[sd]["wrist_swing"] - 55.0) ** 2 + max(0.0, abs(w[sd]["wrist_twist"]) - 70.0) ** 2
    cost += 40.0 * (rr["sword_mm"] or 0.0) + (40.0 * (rr["grip_mm"] or 0.0) if "L" in sides else 0.0)
    return cost


def _tune_rolls(rolls=(-75.0, -50.0, -25.0, 25.0, 50.0, 75.0)):
    """Wrist QA: at every controller key this lane made with a local pose / world placement, roll the weapon about
    its own axis (the blade LINE and the contact points are unchanged) to the orientation with the least wrist
    strain - poses.TUNED does the same for the library poses.  Keys that are already fine are left alone."""
    done, improved = 0, 0
    for name, f in sorted(TUNE, key=lambda t: (t[0], t[1])):
        if name == "SAINT_rig" and any(a - 3 <= f <= b + 3 for a, b in NO_TUNE):
            continue            # twirl windows: the wheel turns about the controller's local X - a roll about the
            # spear axis would tilt the wheel's plane (the kunai hit points are computed on the untuned wheel)
        rig = bpy.data.objects[name]
        if not M.arm_is_ik(rig, f):
            continue
        ctrl = PZ._ctrl_obj(rig)
        fc = U.fcurve(ctrl, "rotation_euler", 0)
        k = U._key_at(fc, f) if fc is not None else None
        if k is None:
            continue
        interp = k.interpolation
        M0 = PZ.current_ctrl_matrix(rig, f)
        U.frame_set(f)
        c0 = _wrist_cost(rig, f)
        done += 1
        if c0 < 50.0:
            continue
        best, bc = 0.0, c0
        for r in rolls:
            CH.key_ctrl_matrix(ctrl, f, M0 @ Matrix.Rotation(math.radians(r), 4, 'Y'), interp)
            U.frame_set(f)
            c = _wrist_cost(rig, f)
            if c < bc - 1e-6:
                best, bc = r, c
        CH.key_ctrl_matrix(ctrl, f, M0 @ Matrix.Rotation(math.radians(best), 4, 'Y'), interp)
        if best:
            improved += 1
    _log(f"wrist roll tuning: {done} keys checked, {improved} rolled")


def _key_tip_world(rig, f, tip, direction, edge=None, interp='BEZIER', weapon=None):
    """Weapon TIP at a world point (grip = tip - dir * tip distance; spear: from its keyed grip at f)."""
    d = Vector(direction).normalized()
    w = weapon or M.weapon_at(rig, f)
    if w == "spear":
        gR = CH.spear_grip(f)[0]
        dist = CH.DIMS["SAINT"]["spear_length"] - gR
    else:
        c = PZ.char_of(rig)
        D = CH.DIMS[c]
        dist = D["grip_to_tsuba"] + D["tsuba_thickness"] * 0.5 + D["blade_length"]
    return _key_ctrl_world(rig, f, Vector(tip) - d * dist, d, edge, interp)


def _key_butt_world(rig, f, butt, direction, edge=None, interp='BEZIER'):
    """Spear BUTT at a world point (grip = butt + dir * grip_R at f)."""
    d = Vector(direction).normalized()
    gR = CH.spear_grip(f)[0]
    return _key_ctrl_world(rig, f, Vector(butt) + d * gR, d, edge, interp)


def _local_ballistic(obj, f0, p0, v0, f1, spin_axis=None, spin_rate=0.0, align_velocity=False, rot0=None,
                     visible_from=None):
    """Closed-form ballistic keys every frame f0..f1 on the fx clock (slow motion slows it): p = p0 + v t + g t^2/2;
    rotation aligned to the velocity (+Y = travel) or spinning spin_rate rad/s (fx) about a world axis from rot0.
    CONSTANT on f1 (the landing pose).  obj must be unparented (free prop)."""
    from mathutils import Quaternion
    ob = bpy.data.objects[obj] if isinstance(obj, str) else obj
    ob.rotation_mode = 'XYZ'
    p0, v0 = Vector(p0), Vector(v0)
    q0 = rot0.to_quaternion() if rot0 is not None else U.world_matrix_of(ob, f0).to_quaternion()
    t0 = _fx(f0)
    prev = None
    for f in range(int(f0), int(f1) + 1):
        t = _fx(f) - t0
        p = p0 + v0 * t + Vector((0.0, 0.0, -0.5 * G * t * t))
        if align_velocity:
            v = v0 + Vector((0.0, 0.0, -G * t))
            q = v.normalized().to_track_quat('Y', 'Z')
            if spin_rate:
                q = q @ Quaternion((0.0, 1.0, 0.0), spin_rate * t)
        elif spin_axis is not None and spin_rate:
            q = Quaternion(Vector(spin_axis).normalized(), spin_rate * t) @ q0
        else:
            q = q0
        e = q.to_euler('XYZ', prev) if prev is not None else q.to_euler('XYZ')
        prev = e
        it = 'CONSTANT' if f == int(f1) else 'LINEAR'
        U.key(ob, "location", f, tuple(p), interp=it)
        U.key(ob, "rotation_euler", f, tuple(e), interp=it)
    if visible_from is not None:
        U.key_visible(ob, visible_from - 1, False)
        U.key_visible(ob, visible_from, True)
    return p


def _ballistic_v0(p0, p1, f0, f1):
    """Launch velocity so a point leaves p0 at f0 and reaches p1 at f1 (fx-clock time)."""
    T = _fx(f1) - _fx(f0)
    p0, p1 = Vector(p0), Vector(p1)
    v = (p1 - p0) / T
    v.z = (p1.z - p0.z + 0.5 * G * T * T) / T
    return v


def _spear_hand_rest(f):
    """(L, gR): weapon.R length and the keyed right-fist grip (m from the butt) at f."""
    ob = bpy.data.objects["SAINT_spear_hand"]
    L = ob.parent.data.bones["weapon.R"].length
    return L, CH.spear_grip(f)[0]


def _local_twirl(f0, f1, turns, ease="inout_quad", step=1, whoosh=True, strength=0.5):
    """The spear spins THROUGH the still right fist (a baton / staff twirl) about the fist's flat normal (the
    controller's local X): SAINT_spear_hand's basis = T(0,-L,0) @ Rx(theta) @ T(0,-gR,0).  With the controller
    pointing the spear along world X (edge down), the wheel turns in the world XZ plane (a propeller in front of him,
    perpendicular to the line).  No wrist roll on the IK hand (docs/shots/act2.md R7).  Ends at theta = 0 mod 360.
    Emits a whoosh every half turn."""
    ob = bpy.data.objects["SAINT_spear_hand"]
    n = int(round(f1 - f0))
    NO_TUNE.append((f0, f1))
    last_half = 0
    L, gR = _spear_hand_rest(f0)            # the grip is constant during a twirl (read once: keys change below)
    rx = U.fcurve(ob, "rotation_euler", 0)
    base = 2 * math.pi * round((rx.evaluate(f0) if rx is not None and len(rx.keyframe_points) else 0.0)
                               / (2 * math.pi))
    for i in range(0, n + 1, step):
        f = f0 + i
        u = ease(i / max(1, n)) if callable(ease) else U.ease(i / max(1, n), ease)
        th = math.radians(360.0 * turns * u)
        U.key(ob, "location", f, (0.0, -L - gR * math.cos(th), -gR * math.sin(th)), interp='LINEAR')
        U.key(ob, "rotation_euler", f, (base + th, 0.0, 0.0), interp='LINEAR')
        half = int((360.0 * turns * u) // 180.0)
        if whoosh and half > last_half:
            EV.emit(f, "whoosh", who="saint", weapon="spear", strength=strength)
            last_half = half
    # land exactly on the resting basis (theta = 0 mod 360) with the grip; the next keys take over
    U.key(ob, "location", f1, (0.0, -L - gR, 0.0), interp='BEZIER')
    U.key(ob, "rotation_euler", f1, (base + math.radians(360.0 * round(turns)), 0.0, 0.0), interp='BEZIER')


def _twirl_reset(f):
    """Key SAINT_spear_hand's twirl channels at rest (theta 0, z 0) - before/after a twirl."""
    ob = bpy.data.objects["SAINT_spear_hand"]
    L, gR = _spear_hand_rest(f)
    rx = U.fcurve(ob, "rotation_euler", 0)
    cur = rx.evaluate(f) if rx is not None and len(rx.keyframe_points) else 0.0
    turns = round(cur / (2 * math.pi))
    U.key(ob, "location", f, 0.0, index=2, interp='BEZIER')
    U.key(ob, "rotation_euler", f, turns * 2 * math.pi, index=0, interp='BEZIER')


def _local_haori_burn(obj_name, ignite, gone):
    """Burn SAINT_haori_thrown away on the film clock: a copy of its material where a noise + distance-from-the-hem
    field n is compared with a threshold tau(fx time): n < tau-0.15 transparent (dithered), tau-0.15..tau-0.06 char,
    tau-0.06..tau glowing edge (emission).  Hidden from gone+1."""
    ob = bpy.data.objects.get(obj_name)
    if ob is None:
        _log(f"haori burn: {obj_name} missing")
        return None
    src = ob.active_material
    mat = (src.copy() if src is not None else bpy.data.materials.new("haori_src"))
    mat.name = "S15_haori_burn"
    try:
        mat.surface_render_method = 'DITHERED'
    except AttributeError:
        pass
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    out = next((n for n in nodes if n.type == 'OUTPUT_MATERIAL'), None) or nodes.new("ShaderNodeOutputMaterial")
    orig = out.inputs["Surface"].links[0].from_socket if out.inputs["Surface"].links else None
    if orig is None:
        bsdf = nodes.new("ShaderNodeBsdfPrincipled")
        orig = bsdf.outputs[0]
    tc = nodes.new("ShaderNodeTexCoord")
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 3.0
    noise.inputs["Detail"].default_value = 4.0
    links.new(tc.outputs["Object"], noise.inputs["Vector"])
    # gradient from the hem: object-space distance along -Z-ish (the snapshot's local frame = chest axes) - use
    # the distance from a corner point, normalised by the half diagonal
    sep = nodes.new("ShaderNodeVectorMath")
    sep.operation = 'DISTANCE'
    dims = ob.dimensions
    corner = (0.0, -dims.y * 0.5, -dims.z * 0.5)
    sep.inputs[1].default_value = corner
    links.new(tc.outputs["Object"], sep.inputs[0])
    norm = nodes.new("ShaderNodeMath")
    norm.operation = 'DIVIDE'
    norm.inputs[1].default_value = max(0.3, (dims.y ** 2 + dims.z ** 2) ** 0.5)
    links.new(sep.outputs["Value"], norm.inputs[0])
    mix_n = nodes.new("ShaderNodeMix")
    mix_n.data_type = 'FLOAT'
    mix_n.inputs[0].default_value = 0.45
    links.new(norm.outputs[0], mix_n.inputs[2])
    links.new(noise.outputs["Fac"], mix_n.inputs[3])
    n_out = mix_n.outputs[0]
    tau = nodes.new("ShaderNodeValue")
    tau.name = tau.label = "Burn Tau"
    VFX.time_curve(tau.outputs[0], "default_value",
                   [(ignite, -0.05), (1690, 0.35), (1760, 0.80), (gone, 1.10)], frames=True)

    def sub(a, b_val=None, b_sock=None, op='SUBTRACT'):
        m = nodes.new("ShaderNodeMath")
        m.operation = op
        links.new(a, m.inputs[0])
        if b_sock is not None:
            links.new(b_sock, m.inputs[1])
        else:
            m.inputs[1].default_value = b_val
        return m.outputs[0]
    d = sub(n_out, b_sock=tau.outputs[0])                          # n - tau  (< 0: burnt)
    alpha = sub(d, 0.15, op='ADD')                                 # n - tau + 0.15 >= 0: still there
    alpha = sub(sub(alpha, 0.0, op='GREATER_THAN'), 1.0, op='MINIMUM')
    edge_a = sub(sub(d, 0.0, op='LESS_THAN'), 1.0, op='MINIMUM')   # within tau: char / glowing
    glow_a = sub(sub(d, -0.06, op='GREATER_THAN'), b_sock=edge_a, op='MULTIPLY')
    char = nodes.new("ShaderNodeBsdfDiffuse")
    char.inputs["Color"].default_value = (0.02, 0.015, 0.012, 1.0)
    em = nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (1.0, 0.35, 0.06, 1.0)
    em.inputs["Strength"].default_value = 1.4
    m1 = nodes.new("ShaderNodeMixShader")
    links.new(edge_a, m1.inputs[0])
    links.new(orig, m1.inputs[1])
    links.new(char.outputs[0], m1.inputs[2])
    m2 = nodes.new("ShaderNodeMixShader")
    links.new(glow_a, m2.inputs[0])
    links.new(m1.outputs[0], m2.inputs[1])
    links.new(em.outputs[0], m2.inputs[2])
    tr = nodes.new("ShaderNodeBsdfTransparent")
    m3 = nodes.new("ShaderNodeMixShader")
    links.new(alpha, m3.inputs[0])
    links.new(tr.outputs[0], m3.inputs[1])
    links.new(m2.outputs[0], m3.inputs[2])
    links.new(m3.outputs[0], out.inputs["Surface"])
    ob.data.materials.clear() if len(ob.material_slots) <= 1 else None
    if len(ob.material_slots) == 0:
        ob.data.materials.append(mat)
    else:
        for s in ob.material_slots:
            s.link = 'OBJECT'
            s.material = mat
    U.key_visible(ob, gone + 1, False)
    return mat


def _head_turn(rig, f, yaw=0.0, pitch=0.0, base_frame=None, interp='BEZIER'):
    """Key neck + head at f = their rotation at base_frame (a keyed pose) + a look offset (yaw + = to his left,
    pitch + = down), split 45 % neck / 55 % head."""
    bf = f if base_frame is None else base_frame
    for b, w in (("neck", 0.45), ("head", 0.55)):
        cur = PZ.current_rot(rig, b, bf)
        U.key(rig.pose.bones[b], "rotation_euler", f,
              tuple(math.radians(v) for v in (cur[0] + pitch * w, cur[1] + yaw * w, cur[2])), interp=interp)


def _haori_drape(f):
    """Key SAINT_haori_thrown (CONSTANT) lying on the grass tops at HAORI (D2): the mesh's principal axes (PCA of
    its vertices) are laid down - the longest (hem -> collar) along world +Y, the thinnest (the coat's depth) up,
    tilted 35 deg toward +X so its back reads from the +X cameras - its origin (vertex centroid) on HAORI.  Works
    for the build placeholder and for act1b's evaluated snapshot alike."""
    import numpy as np
    ob = bpy.data.objects.get("SAINT_haori_thrown")
    if ob is None or not len(ob.data.vertices):
        return
    V = np.array([v.co[:] for v in ob.data.vertices], dtype=float)
    kb = ob.data.shape_keys.key_blocks if ob.data.shape_keys else None
    if kb is not None and "spread" in kb:
        # the snapshot is the worn coat = a TUBE (it read as a dark tent on the grass): lay it down OPENED FLAT
        # (characters.snapshot_haori's 'spread' shape), keyed on the shape keys (lane-stashed like any key)
        V = np.array([p.co[:] for p in kb["spread"].data], dtype=float)
        for nm, v in (("spread", 1.0), ("crumple", 0.0)):
            if nm in kb:
                kb[nm].value = v
                kb[nm].keyframe_insert("value", frame=f)
                fc = U.fcurve(ob.data.shape_keys, f'key_blocks["{nm}"].value')
                if fc is not None:
                    for k in fc.keyframe_points:
                        k.interpolation = 'CONSTANT'
    c = V.mean(axis=0)
    w, E = np.linalg.eigh(np.cov((V - c).T))            # ascending variance
    e_thin, e_long = Vector(E[:, 0]), Vector(E[:, 2])
    e_mid = e_long.cross(e_thin)                              # right-handed (X = Y x Z)
    a = math.radians(30.0)
    up = Vector((math.sin(a), 0.0, math.cos(a)))
    Yw = Vector((0.0, 1.0, 0.0))
    Xw = Yw.cross(up)
    B_local = Matrix((e_mid, e_long, e_thin)).transposed()      # columns: local principal axes
    B_world = Matrix((Xw, Yw, up)).transposed()
    R = B_world @ B_local.inverted()                            # maps the principal axes onto the world frame
    loc = Vector(HAORI) - R @ Vector(c)
    ob.rotation_mode = 'XYZ'
    U.key(ob, "location", f, tuple(loc), interp='CONSTANT')
    U.key(ob, "rotation_euler", f, tuple(R.to_euler('XYZ')), interp='CONSTANT')


# =============================================================================================
# entering state (HANDOFF[1632]) - the first key of every state channel extrapolates backwards
# =============================================================================================
def _enter():
    f = SPAN[0]
    sh_in, sa_in = H_IN["shinobi"], H_IN["saint"]
    _root(SH, f, sh_in["pos"], sh_in["facing"])
    _root(SA, f, sa_in["pos"], sa_in["facing"])
    CH.set_weapon_state(SH, f, "drawn")
    CH.set_arm_mode(SH, f, "ik")
    CH.set_two_hand(SH, f, True)
    CH.set_kunai_in_hand(f, False)
    for i in (1, 2, 3):
        U.key_visible(bpy.data.objects[f"SHINOBI_kunai_{i}"], f, False)
    CH.set_weapon_state(SA, f, "sheathed")          # katana in the saya ...
    CH.set_weapon_state(SA, f, "in_hand")           # ... spear in hand (this call sets active_weapon = spear)
    CH.set_arm_mode(SA, f, "ik")
    CH.set_spear_grip(f, 1.30, 1.62)
    CH.set_two_hand(SA, f, True, weapon="spear")
    CH.set_costume(f, haori=False, thrown=False)    # tasuki on; no re-snapshot of act1b's thrown coat
    U.key_visible(bpy.data.objects["SAINT_haori_thrown"], f, True)
    CH.set_hat(f, "off")                            # the hat halves lie in the grass (D2)
    U.key_visible(bpy.data.objects["SAINT_spear_sheath_world"], f, False)   # the sheath too (D2)
    CH.set_beard_cord(f, False)
    CH.set_hat_tilt(f, 0.0, 0.0)
    for r in (SH, SA):
        CH.release_elbow(r, f, "R")
        CH.release_elbow(r, f, "L")
    _twirl_reset(f)
    PZ.key_saya(SA, f, 0.0, 0.0)


# =============================================================================================
# S15 (1633-1728): the ignition (top-down) + the master re-armed (act card)
# =============================================================================================
def _s15():
    global RING
    # ---------------- elder: the butt strike, recoil, upright hold, twirl, low guard
    _pose(SA, 1633, "butt_slam")
    _key_butt_world(SA, 1633, BUTT, (0.0, 0.0, 1.0), edge=(0.0, -1.0, 0.0))
    b2 = dict(POSE["butt_slam"], hips_offset=(0.0, -0.14, 0.0))
    _kp(SA, 1637, b2, feet=False)
    _key_butt_world(SA, 1637, (BUTT[0], BUTT[1], 0.04), (0.0, 0.0, 1.0), edge=(0.0, -1.0, 0.0))   # rebound (D4)
    _kp(SA, 1645, b2, feet=False)
    _key_butt_world(SA, 1645, (BUTT[0], BUTT[1], 0.005), (0.0, 0.0, 1.0), edge=(0.0, -1.0, 0.0))
    _pose(SA, 1656, "spear_upright")
    _key_butt_world(SA, 1656, (BUTT[0] - 0.02, BUTT[1] + 0.02, 0.005), (0.0, 0.0, 1.0), edge=(0.0, -1.0, 0.0))
    _pose(SA, 1664, "spear_upright", feet=False)
    _key_butt_world(SA, 1664, (BUTT[0] - 0.02, BUTT[1] + 0.02, 0.005), (0.0, 0.0, 1.0), edge=(0.0, -1.0, 0.0))
    # lift: left hand leaves, the spear comes up to the horizontal twirl hold in front of the chest
    CH.set_two_hand(SA, 1664, False, blend=3)
    CH.set_spear_grip(1664, 1.30, 1.62)
    CH.set_spear_grip(1670, 1.15, 1.62)
    _pose(SA, 1670, "twirl")
    _twirl_reset(1670)
    _local_twirl(1670, 1692, 2, strength=0.5)
    _pose(SA, 1692, "twirl", feet=False)
    # the head swings down to point at the shinobi: settle into the low spear guard
    CH.set_spear_grip(1692, 1.15, 1.62)
    _pose(SA, 1703, "guard_low")                      # grips slide to 0.35 / 0.95 (spear_grip in the pose)
    CH.set_two_hand(SA, 1697, True, weapon="spear", blend=4)
    _pose(SA, 1716, "guard_low", feet=False)
    M.overlay(SA, 1716, {"chest": (1.2, 0.0, 0.0)})
    _pose(SA, 1728, "guard_low", feet=False)
    # ---------------- shinobi: half step back from the eruption, eyes on the flames, chudan
    M.stance(SH, 1633, "chudan")
    M.step(SH, 1636, 1646, (0.0, -1.75), facing=180.0)
    M.stance(SH, 1656, "chudan")
    _head_turn(SH, 1640, yaw=-15.0, base_frame=1633)
    _head_turn(SH, 1648, yaw=15.0, base_frame=1633)
    M.stance(SH, 1700, "chudan")
    M.overlay(SH, 1700, {"chest": (1.0, 0.0, 0.0)})
    # off-screen during S15b he closes in (stalking, chudan) so that S16a's closer wide holds BOTH at its first
    # frame (framing QA: a listed subject may not start off-screen); the charge is then 3.3 m instead of 4.8 m
    M.step(SH, 1702, 1709, (0.0, -1.25), facing=180.0)
    M.step(SH, 1711, 1718, (0.0, -0.72), facing=180.0)
    M.step(SH, 1719, 1726, (0.0, -0.20), facing=180.0)
    M.stance(SH, 1728, "chudan")
    # ---------------- vfx
    RING = VFX.fire_ring(F_IGNITE, RING_C, radius=RING_R, grow_frames=12, f_out=F_RAIN, height=2.2,
                         seed=_seed("ring"), ember_rate=40.0, shadow_angles=(150.0, 210.0), light_energy=400.0)
    ring = RING.get("flames")
    if ring is not None:        # S15b card-legibility cheat: the tongues settle at 1.3 m, surge back after the card
        U.gn_key(ring, "Height", 1633, 2.2, interp='CONSTANT')
        U.gn_key(ring, "Height", 1657, 1.6, interp='CONSTANT')
        U.gn_key(ring, "Height", 1715, 1.6, interp='SINE')
        U.gn_key(ring, "Height", 1729, 2.2, interp='CONSTANT')
    VFX.dust_burst(1633, BUTT, radius=0.9, seed=_seed("S15a_dust"))
    VFX.grass_burst(1633, (BUTT[0], BUTT[1], 0.30), (0.0, 0.0, 1.0), count=90, speed=3.0, fluff=0.15,
                    seed=_seed("S15a_grass"))
    VFX.sparks(1633, (BUTT[0], BUTT[1], 0.05), direction=(0, 0, 1), count=24, speed=2.5, life=8, color='fire',
               scale=0.6, light=False, seed=_seed("S15a_sparks"))
    VFX.embers(1633, 2405, RING_C, RING_R, rate=25.0, height=(0.3, 2.5), seed=_seed("S15a_embers"))
    _haori_drape(1633)
    _local_haori_burn("SAINT_haori_thrown", ignite=1641, gone=1800)
    VFX.fire_ring(1641, (HAORI[0], HAORI[1], 0.86), radius=0.55, grow_frames=10, count=30, height=0.36, lights=False,
                  smoke=False, ember_rate=10.0, ground_glow=False, extinguish=False, f_out=1776, f_end=1800,
                  seed=_seed("S15_haori_fire"))
    VFX.blade_trail("SAINT_spear_tip", "SAINT_spear_base", 1672, 1692, owner="saint", width=0.72)
    # ---------------- events
    EV.emit(F_IGNITE, "fire_ignite", pos=BUTT, strength=1.0, tags=["act2_start"])
    EV.emit(F_IGNITE, "music_cue", cue="act2_start")
    EV.emit(1633, "land", who="saint", pos=BUTT, strength=0.8, tags=["spear_butt"])
    EV.emit(1638, "fire_burst", pos=(0.0, 1.5, 0.5), strength=1.0, tags=["ring"])
    EV.emit(1641, "fire_burst", pos=HAORI, strength=0.35, tags=["haori"])
    EV.emit(1670, "spear_spin", who="saint", duration=22)
    EV.emit(1699, "step", who="saint", strength=0.5)


def _place(rig, f, point, direction, along, edge=None, interp='BEZIER'):
    """Key the controller so the weapon point `along` metres from the right FIST (along the weapon direction;
    negative = toward the butt / kashira) sits on the world `point`."""
    d = Vector(direction).normalized()
    return _key_ctrl_world(rig, f, Vector(point) - d * along, d, edge, interp)


def _spear_along(f, s_from_butt):
    """Distance from the right fist to the point s metres from the butt of the spear (keyed grip at f)."""
    return s_from_butt - CH.spear_grip(f)[0]


def _hold_pose(rig, f0, f1, name, step=8, breathe=1.0):
    """Re-key a pose every `step` frames between f0 and f1 with a tiny chest breath (keeps a held stance alive)."""
    f = f0
    k = 0
    while f <= f1:
        _pose(rig, f, name, feet=(f == f0))
        if breathe and 0 < f < f1:
            M.overlay(rig, f, {"chest": (breathe * (1 if k % 2 else -1), 0.0, 0.0)})
        f += step
        k += 1
    if f - step < f1:
        _pose(rig, f1, name, feet=False)


def _smooth_angles(keys, f):
    """Monotone cubic (PCHIP-like) interpolation of [(frame, angle)] at f."""
    ks = sorted(keys)
    if f <= ks[0][0]:
        return ks[0][1]
    if f >= ks[-1][0]:
        return ks[-1][1]
    xs = [k[0] for k in ks]
    ys = [k[1] for k in ks]
    n = len(ks)
    d = [(ys[i + 1] - ys[i]) / (xs[i + 1] - xs[i]) for i in range(n - 1)]
    m = [d[0]] + [0.0 if d[i - 1] * d[i] <= 0 else 2.0 / (1.0 / d[i - 1] + 1.0 / d[i]) for i in range(1, n - 1)] + [d[-1]]
    for i in range(n - 1):
        if xs[i] <= f <= xs[i + 1]:
            h = xs[i + 1] - xs[i]
            t = (f - xs[i]) / h
            h00, h10 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t
            h01, h11 = -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
            return h00 * ys[i] + h10 * h * m[i] + h01 * ys[i + 1] + h11 * h * m[i + 1]
    return ys[-1]


# =============================================================================================
# S16 (1729-1920): the spear onslaught
# =============================================================================================
def _s16a():
    # ---------------- shinobi: dash, sliding duck under the 360 sweep, rise, two back-hops
    M.stance(SH, 1729, "chudan")
    x0, y0 = _xy(SH, 1729)
    _root(SH, 1729, (x0, y0), 180.0, interp='LINEAR')
    M.dash(SH, 1731, 1747, (x0, y0), (0.10, 3.10), upper="dash")
    M.root_path(SH, 1747, 1753, (0.10, 3.10), (0.10, 3.45), ease="out_quad")
    M._feet_air(SH, 1747.5)
    _pose(SH, 1750, "slide_duck", weight=0.8, feet=False)
    _pose(SH, 1753, "slide_duck")
    _pose(SH, 1758, "slide_duck", feet=False)
    _root(SH, 1758, (0.10, 3.45), 180.0, interp='BEZIER')
    _pose(SH, 1766, "chudan")
    _root(SH, 1766, (0.10, 3.35), 180.0, interp='BEZIER')
    M.root_path(SH, 1767, 1771, (0.10, 3.35), (0.10, 2.98), z=lambda u: 0.14 * 4 * u * (1 - u))
    M.root_path(SH, 1772, 1776, (0.10, 2.98), (0.10, 2.70), z=lambda u: 0.10 * 4 * u * (1 - u))
    _pose(SH, 1769, "dodge_back", weight=0.7, feet=False)
    _pose(SH, 1776, "chudan")
    # ---------------- elder: two steps in winding the spear, 360 spin sweep, back to the thrust guard
    _pose(SA, 1733, "guard_low", feet=False)
    M.step(SA, 1733, 1739, (0.0, 6.10), facing=340.0)
    M.step(SA, 1739, 1745, (0.0, 5.70), facing=300.0)
    CH.set_spear_grip(1741, 0.35, 0.95)
    _pose(SA, 1745, "sweep_wind")                                   # grips slide to 0.10 / 0.30 (pose)
    spin = [(1745, 300.0), (1753, 405.0), (1759, 520.0), (1765, 660.0), (1769, 700.0)]
    for f in range(1745, 1770):
        _root(SA, f, (0.0, 5.70), _smooth_angles(spin, f), interp='LINEAR')
    for f in (1747, 1753, 1759):
        _pose(SA, f, "sweep_spin", feet=(f == 1747))
    _pose(SA, 1765, "sweep_spin", feet=False)
    M.step(SA, 1769, 1776, (0.0, 5.85), facing=720.0)
    _pose(SA, 1776, "guard_low")
    # ---------------- vfx + events
    VFX.blade_trail("SAINT_spear_tip", "SAINT_spear_base", 1747, 1765, owner="saint")
    VFX.dust_burst(1750, (0.10, 3.30, 0.0), radius=0.6, seed=_seed("S16a_dust"))
    VFX.grass_burst(1752, (0.10, 3.45, 0.55), (0.0, 0.4, 1.0), count=50, fluff=0.15, seed=_seed("S16a_grass"))
    EV.emit(1749, "whoosh", who="saint", weapon="spear", strength=1.0)
    EV.emit(1749, "skid", who="shinobi", duration=6)
    EV.emit(1759, "whoosh", who="saint", weapon="spear", strength=0.6)


def _thrust(f, y_from, y_to, tip, recover_y=None, hold_to=None, knock=0.0):
    """Elder spear thrust with the TIP reaching `tip` at f (the clash refines it): wind-up f-6, drive f-3 -> f
    (the shaft slides through the front hand), lunge y_from -> y_to; recover to recover_y by f+6 (or stay
    extended until hold_to)."""
    _pose(SA, f - 6, "thrust_wind")
    _pose(SA, f - 3, "thrust_wind", weight=1.03, feet=False)
    _root(SA, f - 3, (0.0, y_from), 0.0, interp='LINEAR')
    M.root_path(SA, f - 3, f, (0.0, y_from), (0.0, y_to), ease="in_quad")
    _pose(SA, f, "thrust_ext", ctrl=False)
    d = Vector(tip) - (M.rig_matrix(SA, f) @ Vector((-0.10, -0.55, 1.20)))
    _key_tip_world(SA, f, tip, d)
    if hold_to is not None:
        _pose(SA, hold_to, "thrust_ext", ctrl=False, feet=False)
        return
    if knock:        # the parry knocks the spear head aside (+ = toward +X) before he draws it back
        Wf = M.rig_matrix(SA, f) @ PZ.current_ctrl_matrix(SA, f)
        R = Matrix.Rotation(math.radians(knock), 4, 'Z')
        grip = Wf.translation
        W2 = Matrix.Translation(grip) @ R @ Matrix.Translation(-grip) @ Wf
        _pose(SA, f + 2, "thrust_ext", weight=0.9, ctrl=False, feet=False)
        CH.key_ctrl_matrix(PZ._ctrl_obj(SA), f + 2, M.rig_matrix(SA, f + 2).inverted() @ W2, 'BEZIER')
    _pose(SA, f + 6, "thrust_wind")
    M.root_path(SA, f + 1, f + 6, (0.0, y_to), (0.0, recover_y), ease="inout_quad")


def _s16b():
    # ---------------- elder: three thrusts 1789 / 1801 / 1813, the third stays extended
    _thrust(1789, 5.85, 5.60, (-0.02, 3.18, 1.40), recover_y=5.75, knock=-7.0)
    _thrust(1801, 5.75, 5.50, (0.20, 3.10, 1.33), recover_y=5.65, knock=7.0)
    _thrust(1813, 5.65, 5.40, (-0.08, 3.15, 1.33), hold_to=1816)
    # the kunai turns the shaft: the head swings past his right side (+X), >= 8 deg
    CH.set_spear_grip(1816, 0.35, 0.62)
    for f, ang in ((1816, 6.0), (1820, 10.0), (1824, 11.0)):
        a = math.radians(ang)
        d = Vector((math.sin(a), -math.cos(a), -0.02))
        _pose(SA, f, "thrust_ext", ctrl=False, feet=False)
        grip = M.rig_matrix(SA, f) @ Vector((-0.10, -0.55, 1.20))
        _key_ctrl_world(SA, f, grip + Vector((0.03 * (ang / 10.0), 0.0, 0.0)), d)
    M.overlay(SA, 1820, {"chest": (0.0, -6.0, 0.0), "hips": (0.0, -3.0, 0.0)})
    # ---------------- shinobi: deflect L, deflect R, then the kunai turn + slide along the shaft
    _root(SH, 1777, (0.10, 2.70), 180.0)
    _root(SH, 1789, (0.10, 2.65), 180.0)
    M.deflect(SH, 1789, "mid_L", recover=4)
    M.clash(SA, SH, 1789, point=(-0.05, 3.30, 1.38), strength=0.7)
    _root(SH, 1801, (0.10, 2.62), 180.0)
    M.deflect(SH, 1801, "mid_R", recover=3)
    M.clash(SA, SH, 1801, point=(0.22, 3.25, 1.30), strength=0.75)
    CH.set_two_hand(SH, 1805, False, blend=3)
    _pose(SH, 1806, "one_hand_high")
    _pose(SH, 1808, "sash_reach", feet=False)
    CH.set_kunai_in_hand(1809, True)
    _pose(SH, 1811, "kunai_slide", weight=0.8, feet=False)
    _pose(SH, 1813, "kunai_slide")
    _root(SH, 1813, (0.08, 2.72), 185.0, interp='LINEAR')
    M.clash(SA, SH, 1813, point=(-0.10, 3.30, 1.32), strength=0.8, weapon_b="kunai")
    M.root_path(SH, 1813, 1822, (0.08, 2.72), (-0.25, 4.30), facing0=185.0, facing1=188.0, ease="out_quad")
    M._feet_air(SH, 1814)
    _pose(SH, 1818, "kunai_slide", feet=False)
    _pose(SH, 1822, "kunai_slide")
    _root(SH, 1824, (-0.25, 4.35), 188.0)
    _pose(SH, 1824, "kunai_slide", feet=False)
    # ---------------- vfx + events
    for f0, f1 in ((1785, 1789), (1797, 1801), (1809, 1813)):
        VFX.blade_trail("SAINT_spear_tip", "SAINT_spear_base", f0, f1, owner="saint")
    VFX.blade_trail("SHINOBI_katana_tip", "SHINOBI_katana_base", 1786, 1791, owner="shinobi")
    VFX.blade_trail("SHINOBI_katana_tip", "SHINOBI_katana_base", 1798, 1803, owner="shinobi")
    for k, f in enumerate(range(1814, 1823, 2)):              # the kunai scraping along the shaft
        VFX.sparks(f, (-0.10, 3.40 + 0.24 * k, 1.33 + 0.01 * k), direction=(-0.3, -0.6, 0.7), count=12, speed=2.0,
                   life=6, color="white", scale=0.5, light=(k == 0), seed=_seed(f"S16b_scrape{k}"))
    for f in (1785, 1797, 1809):
        EV.emit(f, "whoosh", who="saint", weapon="spear", strength=0.8)
    EV.emit(1814, "skid", who="shinobi", duration=8, tags=["blade", "scrape"])


def _s16c():
    # ---------------- shinobi: one-handed cut at the front hand (blocked by the vertical shaft), press, shoved back
    _root(SH, 1830, (-0.24, 4.38), 188.0)
    _root(SH, 1837, (-0.22, 4.45), 186.0)
    _blocked_cut(SH, 1837, "diag_down_R", (-0.10, 4.95, 1.45), (0.45, 0.75, 0.48), 0.45, windup=4,
                 hold_frames=1, strike=3, rebound=0.08, settle=1, recover=1, recover_to="kunai_slide", strength=0.7)
    _root(SH, 1841, (-0.21, 4.47), 186.0)
    _pose(SH, 1841, "kunai_slide", feet=False)
    _place(SH, 1841, (-0.10, 4.92, 1.45), (0.55, 0.30, 0.78), 0.40)
    _pose(SH, 1848, "kunai_slide", feet=False)
    _place(SH, 1848, (-0.10, 4.88, 1.42), (0.60, 0.25, 0.76), 0.36)
    _root(SH, 1849, (-0.20, 4.40), 184.0, interp='LINEAR')
    M.root_path(SH, 1850, 1861, (-0.20, 4.40), (0.05, 2.80), facing0=184.0, facing1=180.0, ease="out_cubic")
    M._feet_air(SH, 1850.5)
    _pose(SH, 1852, "stagger_back", weight=0.6, feet=False)
    _pose(SH, 1858, "dodge_back", weight=0.8, feet=False)
    CH.set_kunai_in_hand(1861, False)
    _pose(SH, 1861, "one_hand_high")
    CH.set_two_hand(SH, 1863, True, blend=3)
    _pose(SH, 1866, "chudan")
    _pose(SH, 1872, "chudan", feet=False)
    # ---------------- elder: front hand off, pivot, vertical shaft block, lock, shove, flourish, guard
    CH.set_two_hand(SA, 1826, False, blend=2)
    CH.set_spear_grip(1827, 0.35, 1.30)
    _root(SA, 1825, (0.0, 5.40), 360.0)
    _root(SA, 1834, (0.0, 5.45), 370.0)
    _pose(SA, 1831, "staff_block", ctrl=False, feet=True)
    _key_ctrl_world(SA, 1831, (-0.20, 5.05, 0.80), (0.10, -0.05, 1.0), edge=(0.0, -1.0, 0.0))
    CH.set_two_hand(SA, 1832, True, weapon="spear", blend=2)
    _pose(SA, 1837, "staff_block", ctrl=False, feet=False)
    _key_ctrl_world(SA, 1837, (-0.13, 4.97, 0.95), (0.05, -0.03, 1.0), edge=(0.0, -1.0, 0.0))
    M.clash(SH, SA, 1837, point=(-0.10, 4.95, 1.45), strength=0.75)
    _pose(SA, 1845, "staff_block", ctrl=False, feet=False)
    _key_ctrl_world(SA, 1845, (-0.12, 5.00, 0.97), (0.02, -0.02, 1.0), edge=(0.0, -1.0, 0.0))
    # the shove: the shaft swings horizontal at chest height and both arms drive it out
    CH.set_spear_grip(1846, 0.35, 1.30)
    sh = dict(POSE["staff_block"], hips_offset=(0.0, -0.05, 0.10))
    _kp(SA, 1849, sh, ctrl=False)
    _key_ctrl_world(SA, 1849, (-0.45, 4.78, 1.40), (1.0, 0.02, 0.05), edge=(0.0, -1.0, 0.0))
    _root(SA, 1849, (0.0, 5.40), 365.0)
    _kp(SA, 1853, sh, ctrl=False, feet=False)
    _key_ctrl_world(SA, 1853, (-0.40, 4.85, 1.38), (1.0, 0.0, 0.05), edge=(0.0, 0.0, -1.0))
    # flourish: one turn of the spear through the fist, then the thrust guard at (0, 5.80)
    CH.set_two_hand(SA, 1853, False, blend=2)
    CH.set_spear_grip(1855, 1.10, 1.30)
    _pose(SA, 1855, "twirl")
    _twirl_reset(1855)
    _local_twirl(1855, 1864, 1, strength=0.45)
    M.step(SA, 1856, 1866, (0.0, 5.80), facing=360.0)
    CH.set_spear_grip(1864, 1.10, 1.30)
    _pose(SA, 1870, "guard_low")
    CH.set_two_hand(SA, 1866, True, weapon="spear", blend=3)
    _pose(SA, 1872, "guard_low", feet=False)
    # ---------------- vfx + events
    VFX.blade_trail("SHINOBI_katana_tip", "SHINOBI_katana_base", 1831, 1837, owner="shinobi")
    VFX.dust_burst(1851, (0.00, 3.90, 0.0), radius=0.6, seed=_seed("S16c_dust"))
    VFX.grass_burst(1855, (0.02, 3.30, 0.40), (0.0, -1.0, 0.6), count=40, fluff=0.1, seed=_seed("S16c_grass"))
    VFX.blade_trail("SAINT_spear_tip", "SAINT_spear_base", 1855, 1864, owner="saint")
    EV.emit(1841, "blade_lock", duration=8, pos=(-0.10, 4.90, 1.45))
    EV.emit(1850, "skid", who="shinobi", duration=11)
    EV.emit(1855, "spear_spin", who="saint", duration=10)


def _s16d():
    # ---------------- shinobi: two quick steps in, tuck vault over the low sweep, land, two back-hops
    M.step(SH, 1873, 1879, (0.05, 3.25), facing=180.0)
    _pose(SH, 1876, "hasso", feet=False)
    # vault: take-off 1879, apex 1885 (root z 0.72: the sweep runs at thigh height, see below), touchdown 1897
    _pose(SH, 1878, "jump_crouch", weight=0.8, feet=False)
    _root(SH, 1879, (0.05, 3.25), 180.0, interp='LINEAR')
    for f in range(1880, 1897):
        u = (f - 1879) / 18.0
        z = VAULT_APEX * (1.0 - ((f - 1885) / (6.0 if f <= 1885 else 12.0)) ** 2)
        _root(SH, f, (0.05, 3.25 - 0.20 * u), 180.0, z=max(0.0, z), interp='LINEAR')
    _root(SH, 1897, (0.05, 3.05), 180.0, interp='LINEAR')
    M._feet_air(SH, 1879.5)
    _pose(SH, 1882, "vault_tuck", weight=0.8, feet=False)
    _pose(SH, 1885, "vault_tuck", feet=False)
    _pose(SH, 1889, "vault_tuck", weight=0.9, feet=False)
    _pose(SH, 1895, "jump_air", weight=0.6, feet=False)
    _pose(SH, 1897, "jump_land")
    _pose(SH, 1899, "jump_land", weight=1.05, feet=False)
    M.root_path(SH, 1899, 1905, (0.05, 3.05), (0.08, 2.00), z=lambda u: 0.20 * 4 * u * (1 - u), ease="out_quad")
    M.root_path(SH, 1906, 1914, (0.08, 2.00), (0.10, 1.15), z=lambda u: 0.18 * 4 * u * (1 - u), ease="out_quad")
    M._feet_air(SH, 1899.5)
    _pose(SH, 1902, "dodge_back", feet=False)
    _pose(SH, 1905, "chudan")
    _pose(SH, 1909, "dodge_back", feet=False)
    _pose(SH, 1914, "chudan")
    _root(SH, 1920, (0.10, 1.10), 180.0)
    _pose(SH, 1920, "chudan", feet=False)
    # ---------------- elder: deep lunge, 200 deg low sweep (tip compass 290 -> 180 @1885 -> 90) - at THIGH height
    # (tip z ~0.78, fist 0.82, level) instead of shin height: at 0.40 m the spear ran inside the 1.05 m grass and
    # the sweep was invisible from every angle; at 0.78 it mows the grass tops (the shear fan) and still passes
    # ~0.25 m under his tucked feet (vault apex root z 0.72)
    _root(SA, 1873, (0.0, 5.80), 360.0)
    CH.set_two_hand(SA, 1874, False, blend=3)
    _pose(SA, 1876, "low_lunge", weight=0.7, ctrl=False)
    CH.set_spear_grip(1876, 0.12, 0.60)
    root = Vector((0.0, 5.80, 0.0))
    sweep = [(1878, 300.0), (1880, 290.0), (1885, 180.0), (1893, 90.0), (1896, 70.0)]
    for f in range(1878, 1897):
        b = math.radians(_smooth_angles(sweep, f))
        dh = Vector((math.sin(b), math.cos(b), 0.0))
        tilt = math.radians(-1.0)
        d = Vector((dh.x * math.cos(tilt), dh.y * math.cos(tilt), math.sin(tilt)))
        fist = root + dh * 0.45 + Vector((0.0, 0.0, 0.82))
        _key_ctrl_world(SA, f, fist, d, edge=(0.0, 0.0, -1.0), interp='LINEAR')
        if f in (1880, 1885, 1890):
            _pose(SA, f, "low_lunge", ctrl=False, feet=(f == 1880))
    M.overlay(SA, 1880, {"chest": (0.0, -12.0, 0.0), "spine": (0.0, -8.0, 0.0)})
    M.overlay(SA, 1890, {"chest": (0.0, 14.0, 0.0), "spine": (0.0, 8.0, 0.0)})
    CH.set_spear_grip(1897, 0.12, 0.60)
    _pose(SA, 1902, "guard_low")
    CH.set_two_hand(SA, 1898, True, weapon="spear", blend=3)
    _pose(SA, 1912, "spear_overhead", weight=0.35, feet=False)
    _pose(SA, 1920, "guard_low", feet=False)
    # ---------------- environment (the mown fan) + vfx + events
    ENV.grass_effect("shear", dict(origin=(0.0, 5.8), radius=3.0, arc_deg=200.0, facing_deg=180.0, fluff=1200),
                     1880, 1890)
    reach = 0.45 + CH.DIMS["SAINT"]["spear_length"] - 0.12 - 0.35          # fist offset + spear past the fist
    arc_pts = []
    for f in (1881, 1883, 1885, 1887, 1889):                                 # along the tip's arc (x0.85 radius)
        b = math.radians(_smooth_angles(sweep, f))
        arc_pts.append((f, (root.x + math.sin(b) * reach, root.y + math.cos(b) * reach)))
    for k, (f, p) in enumerate(arc_pts):
        VFX.grass_burst(f, (p[0], p[1], 0.80), (0.3, -0.4, 0.8), count=70, speed=3.5, fluff=0.2,
                        seed=_seed(f"S16d_arc{k}"))
    VFX.dust_burst(1897, (0.05, 3.05, 0.0), radius=0.7, seed=_seed("S16d_land"))
    VFX.blade_trail("SAINT_spear_tip", "SAINT_spear_base", 1880, 1891, owner="saint")
    EV.emit(1879, "jump", who="shinobi")
    EV.emit(1881, "whoosh", who="saint", weapon="spear", strength=1.0)
    EV.emit(1882, "grass_shear", pos=(0.0, 3.0, 0.5), strength=0.6)
    EV.emit(1897, "land", who="shinobi", strength=0.6)
    EV.emit(1875, "step", who="saint", strength=0.6)


# =============================================================================================
# S17 (1921-2064): three kunai on the wheel, the leaping slam, out of the dust
# =============================================================================================
def _wheel_ease(u):
    """Wheel angle profile 0..1: ramps up over the first 15 %, constant, brakes over the last 22 % (fraction of
    the total angle; integrates a trapezoid speed)."""
    a, b = 0.15, 0.78
    vmax = 1.0 / (1.0 - 0.5 * a - 0.5 * (1.0 - b))
    if u < a:
        return 0.5 * vmax * u * u / a
    if u < b:
        return 0.5 * vmax * a + vmax * (u - a)
    r = 1.0 - u
    return 1.0 - 0.5 * vmax * r * r / (1.0 - b)


def _s17():
    # ================= S17a/b: the throws; the wheel
    # shinobi: left hand to the sash, kunai drawn, three left-hand flicks 6 f apart (sword one-handed low right)
    CH.set_two_hand(SH, 1921, False, blend=4)
    _pose(SH, 1921, "chudan", feet=False)
    _pose(SH, 1925, "sash_reach", feet=False)
    CH.set_kunai_in_hand(1927, True)
    _pose(SH, 1930, "kunai_throw_windup", weight=0.7, feet=False)
    kun = {}
    for i, f in ((1, 1937), (2, 1943), (3, 1949)):
        _pose(SH, f - 3, "kunai_throw_windup", feet=False)
        _pose(SH, f, "kunai_throw_release", feet=False)
        kun[i] = f
    _pose(SH, 1953, "kunai_throw_release", weight=0.5, feet=False)
    CH.set_kunai_in_hand(1949, False)
    CH.set_two_hand(SH, 1958, True, blend=4)
    _pose(SH, 1962, "chudan")
    _pose(SH, 1995, "chudan", feet=False)
    # elder: grip to the centre, the propeller wheel 1935-1963 (spear spun through the fist), raised overhead
    CH.set_two_hand(SA, 1929, False, blend=2)
    CH.set_spear_grip(1929, 0.35, 0.95)
    CH.set_spear_grip(1933, 1.30, 1.60)
    w = dict(POSE["twirl"])
    w["ctrl"] = dict(grip=(0.0, -0.62, 1.45), dir=(1.0, 0.0, 0.0), edge=(0.0, 0.0, -1.0), scale=False)
    _kp(SA, 1933, w)
    _twirl_reset(1935)
    wheel_grip = CH.spear_grip(1935)[0]
    _local_twirl(1935, 1963, 3, ease=_wheel_ease, strength=0.6)
    _kp(SA, 1949, w, feet=False)
    _kp(SA, 1963, w, feet=False)
    CH.set_spear_grip(1963, 1.30, 1.60)
    CH.set_spear_grip(1969, 0.20, 0.75)
    _pose(SA, 1969, "spear_overhead")
    CH.set_two_hand(SA, 1965, True, weapon="spear", blend=3)
    M.overlay(SA, 1968, {"chest": (6.0, 0.0, 0.0), "spine": (4.0, 0.0, 0.0)})     # weight shifts forward
    # kunai flights (fx clock) to the wheel, then deflected arcs into the grass
    hits = {1: ((0.35, 5.15, 1.55), (2.8, 4.2, 0.0), 1969, 18.0), 2: ((-0.30, 5.15, 1.20), (-3.1, 6.2, 0.0), 1969, 15.0),
            3: ((0.10, 5.15, 1.75), (0.8, 8.0, 0.0), 1985, 20.0)}
    # each kunai meets the spinning shaft exactly: the hit point is the point of the evaluated spear 0.40 m from
    # the fist (on the side nearest the planned point) at the deflect frame
    for i, f in kun.items():
        fh = f + 8
        butt, tip = M.actual_segment(SA, fh, "spear", part="full")
        axis = (tip - butt).normalized()
        # the grip at the twirl (CH.spear_grip(fh) reads SAINT_spear_hand location.y, which _local_twirl uses for
        # the rotation: inside a twirl window it returns gR*cos(theta), not the grip)
        fist = butt + axis * wheel_grip
        want = Vector(hits[i][0])
        cand = [fist + axis * 0.40, fist - axis * 0.40]
        best = min(cand, key=lambda c: (c - want).length)
        hits[i] = (tuple(best),) + hits[i][1:]
    for i, f in kun.items():
        ob = bpy.data.objects[f"SHINOBI_kunai_{i}"]
        M0 = CH.detach_matrix(ob, f)
        p0 = M0.translation.copy()
        hit, land, f_land, spin = hits[i]
        v0 = _ballistic_v0(p0, hit, f, f + 8)
        U.key_visible(ob, f - 1, False)
        _local_ballistic(ob, f, p0, v0, f + 8, align_velocity=True, visible_from=f)
        v1 = _ballistic_v0(hit, land, f + 8, f_land)
        ax = Vector(v1).cross(Vector((0.0, 0.0, 1.0)))
        q_end = (Vector(v0) + Vector((0.0, 0.0, -G * (_fx(f + 8) - _fx(f))))).normalized().to_track_quat('Y', 'Z')
        _local_ballistic(ob, f + 8, hit, v1, f_land, spin_axis=ax, spin_rate=spin, rot0=q_end.to_matrix())
        U.key_visible(ob, f_land + 30, False)                   # lies in the grass, then gone from the lane
    # ================= S17c/d: menace hold, three heavy strides, the leap and the slam
    _pose(SA, 1975, "spear_overhead", feet=False)
    M.walk(SA, 1975, 1993, (0.0, 5.80), (0.0, 4.90), facing=0.0, upper=POSE["spear_overhead"])
    _pose(SA, 1994, "spear_overhead", feet=False)
    crouch = dict(POSE["spear_overhead"], hips_offset=(0.0, -0.22, 0.04))
    _kp(SA, 1997, crouch, feet=False)
    _root(SA, 1994, (0.0, 4.90), 360.0, interp='LINEAR')
    M.root_path(SA, 1994, 1999, (0.0, 4.90), (0.0, 4.60), ease="in_quad")
    # flight 1999 -> 2017, apex 2008 (root z 0.55)
    for f in range(2000, 2017):
        u = (f - 1999) / 18.0
        z = 0.55 * (1.0 - ((f - 2008) / 9.0) ** 2)
        _root(SA, f, (0.0, 4.60 - 1.60 * u), 360.0, z=max(0.0, z), interp='LINEAR')
    _root(SA, 2017, (0.0, 3.00), 360.0, interp='LINEAR')
    M._feet_air(SA, 1999.5)
    _pose(SA, 2002, "slam_wind", weight=0.8, feet=False)
    _pose(SA, 2008, "slam_wind", feet=False)
    _pose(SA, 2012, "slam_wind", weight=0.9, ctrl=False, feet=False)
    # the swing over the head and down: the controller on an arc, then the blade flat on the ground along the line
    tip = Vector((0.10, 0.75, 0.03))
    d_imp = Vector((0.03, -0.97, -0.25)).normalized()
    _pose(SA, 2017, "slam", ctrl=False)
    _key_tip_world(SA, 2017, tip, d_imp, edge=(0.0, 0.0, -1.0))
    M.swing(SA, 2012, 2017, PZ.current_ctrl_matrix(SA, 2012), PZ.current_ctrl_matrix(SA, 2017), ease="in_cubic",
            pivot=(0.0, 0.0, 1.35))
    # rebound (D4): the spear jumps 15-25 cm off the ground and is lifted with the recoil
    _pose(SA, 2020, "slam", weight=0.9, ctrl=False, feet=False)
    _key_tip_world(SA, 2020, tip + Vector((0.0, 0.05, 0.22)), (d_imp + Vector((0.0, 0.0, 0.12))).normalized(),
                   edge=(0.0, 0.0, -1.0))
    # shinobi: rolls clear to -X (perpendicular to the line), up on one knee facing the elder
    M.roll(SH, 2003, 2019, (0.10, 1.10), (-1.90, 1.25), face_end=133.0, recover=5,
           recover_to=POSE["kneel_guard"])
    # ================= S17e: out of the dust; he rises and circles back; the elder turns and closes
    _pose(SH, 2030, "kneel_guard", feet=False)
    _root(SH, 2030, (-1.95, 1.25), 133.0)
    _pose(SH, 2037, "chudan")
    _root(SH, 2037, (-1.95, 1.20), 135.0)
    M.step(SH, 2038, 2044, (-1.40, 0.55), facing=150.0)
    M.step(SH, 2045, 2051, (-0.85, -0.20), facing=165.0)
    M.step(SH, 2052, 2060, (-0.30, -0.90), facing=176.0)
    _pose(SH, 2060, "chudan")
    _root(SH, 2064, (-0.30, -0.90), 178.0)
    _pose(SH, 2064, "chudan", feet=False)
    # elder: straightens, lifts the spear out of the rebound into a high guard, turns to him, two steps in
    _pose(SA, 2026, "slam", weight=0.5, ctrl=False, feet=False)
    _key_tip_world(SA, 2026, tip + Vector((0.0, 0.3, 0.9)), (0.0, -0.85, 0.52))
    _pose(SA, 2035, "spear_high")
    _root(SA, 2035, (0.0, 3.00), 330.0)
    _root(SA, 2045, (0.0, 3.00), 313.0)
    _pose(SA, 2045, "spear_high", feet=False)
    M.step(SA, 2046, 2052, (0.0, 2.60), facing=335.0)
    M.step(SA, 2053, 2060, (0.0, 2.20), facing=352.0)
    CH.set_spear_grip(2050, 0.35, 0.95)
    CH.set_spear_grip(2060, 0.50, 1.40)
    _pose(SA, 2060, "staff_block")
    _root(SA, 2064, (0.0, 2.20), 355.0)
    _pose(SA, 2064, "staff_block", feet=False)
    # ---------------- vfx
    VFX.blade_trail("SAINT_spear_tip", "SAINT_spear_base", 1935, 1963, owner="saint", fade=0.08)
    VFX.sparks(1945, hits[1][0], direction=(0.6, -0.3, 0.7), count=45, speed=5.0, life=8, color="white", scale=0.8,
               seed=_seed("S17a_k1"))
    VFX.sparks(1951, hits[2][0], direction=(-0.7, -0.2, 0.5), count=45, speed=5.0, life=8, color="white",
               scale=0.8, seed=_seed("S17b_k2"))
    VFX.sparks(1957, hits[3][0], direction=(0.1, -0.2, 1.0), count=50, speed=5.0, life=9, color="white",
               scale=0.9, seed=_seed("S17b_k3"))
    VFX.dust_burst(1981, (0.00, 5.30, 0.0), radius=0.5, seed=_seed("S17c_d1"))
    VFX.dust_burst(1993, (0.00, 4.80, 0.0), radius=0.5, seed=_seed("S17c_d2"))
    VFX.dust_burst(1999, (0.00, 4.60, 0.0), radius=0.8, seed=_seed("S17c_d3"))
    VFX.grass_burst(1999, (0.00, 4.60, 0.30), (0.0, 0.3, 1.0), count=70, fluff=0.15, seed=_seed("S17c_g"))
    VFX.shockwave(2017, IMPACT, radius=3.5, seed=_seed("S17d_shock"))
    VFX.dust_burst(2017, IMPACT, radius=2.2, density=7.0, seed=_seed("S17d_dust"))
    VFX.sparks(2017, (0.10, 1.05, 0.10), direction=(0, 0, 1), count=90, speed=5.0, life=14, color="fire", scale=1.6,
               seed=_seed("S17d_sparks"))
    VFX.fire_ring(2017, (0.10, 1.00, 0.0), radius=1.3, grow_frames=6, height=1.6, count=60, lights=False,
                  smoke=False, ember_rate=60.0, ground_glow=True, extinguish=False, f_out=2035, f_end=2060,
                  seed=_seed("S17d_fire"))
    VFX.embers(2017, 2040, IMPACT, 1.5, rate=80.0, rise=2.0, seed=_seed("S17d_embers"))
    VFX.grass_burst(2017, (0.10, 1.00, 0.30), (0.0, 0.0, 1.0), count=160, speed=5.0, fluff=0.2,
                    seed=_seed("S17d_grass"))
    VFX.dust_burst(2011, (-1.00, 1.15, 0.0), radius=0.7, seed=_seed("S17d_roll"))
    VFX.blade_trail("SAINT_spear_tip", "SAINT_spear_base", 2009, 2017, owner="saint")
    # ---------------- events
    EV.emit(1921, "draw", who="shinobi", weapon="kunai", strength=0.3)
    for f in (1937, 1943, 1949):
        EV.emit(f, "kunai_throw", who="shinobi")
    EV.emit(1935, "spear_spin", who="saint", duration=28)
    EV.emit(1945, "kunai_deflect", pos=hits[1][0], strength=0.6, tags=["kunai_deflect"])
    EV.emit(1951, "kunai_deflect", pos=hits[2][0], strength=0.6, tags=["kunai_deflect"])
    EV.emit(1957, "kunai_deflect", pos=hits[3][0], strength=0.7, tags=["kunai_deflect"])
    EV.emit(1999, "jump", who="saint")
    EV.emit(2002, "whoosh", who="saint", weapon="spear", strength=0.5)
    EV.emit(2012, "whoosh", who="saint", weapon="spear", strength=1.0)
    EV.emit(2017, "land", who="saint", strength=1.0)
    EV.emit(2017, "fire_burst", pos=IMPACT, strength=1.0, tags=["slam"])
    EV.emit(2019, "shockwave", pos=IMPACT, strength=0.6)


# =============================================================================================
# S18 (2065-2256): close quarters under the spear, the bind, the kick, the skid
# =============================================================================================
def _cut(rig, f, kind, windup=4, hold_frames=2, strike=3, lag=True):
    """The first half of moves.slash (hold -> windup -> coil -> strike arc to the strike pose at f) WITHOUT the
    follow-through / recovery: the caller keys what happens after the contact (binds, grinds)."""
    T = M.clock(f)
    w, h, s = windup, hold_frames, strike
    lag_d = {"hips": -1, "neck": 1, "head": 1} if lag else None
    M.hold(rig, T(-(s + h + w)))
    M.pose(rig, T(-(s + h)), f"{kind}_windup")
    M.pose(rig, T(-s), f"{kind}_windup", weight=1.04, lag=lag_d, feet=False)
    Ma = PZ.current_ctrl_matrix(rig, T(-s))
    M.swing(rig, T(-s), T(0), Ma, M.ctrl_matrix(rig, f"{kind}_strike", T(0)), ease="in_quad", clk=T)
    M.pose(rig, T(0), f"{kind}_strike", lag=lag_d, ctrl=False)
    EV.emit(int(round(T(-1))), "whoosh", who=M.who(rig), weapon="katana", strength=0.9, target=(rig, "hand.R"))
    return f


def _blocked_cut(rig, f, kind, point, direction, along, windup=5, hold_frames=1, strike=3, rebound=0.10,
                 settle=2, recover=5, recover_to="chudan", edge=None, strength=0.8):
    """A cut that is BLOCKED at f: library windup (kind_windup) -> strike arc into an explicit world placement (the
    blade point `along` m from the fist on `point`, blade along `direction`) -> the blade bounces back `rebound` m
    against its travel (T+2) -> settles and recovers into `recover_to` (T+2+settle+recover).  Unlike moves.slash
    the follow-through never carries the blade THROUGH the blocking weapon.  Returns the end frame."""
    T = M.clock(f)
    w, h, s = windup, hold_frames, strike
    lag_d = {"hips": -1, "neck": 1, "head": 1}
    M.hold(rig, T(-(s + h + w)))
    M.pose(rig, T(-(s + h)), f"{kind}_windup")
    M.pose(rig, T(-s), f"{kind}_windup", weight=1.04, lag=lag_d, feet=False)
    Ma = PZ.current_ctrl_matrix(rig, T(-s))
    tip_a = M.rig_matrix(rig, T(-s)) @ Ma @ Vector((0.0, 0.7, 0.0))
    Mb = _place(rig, f, point, direction, along, edge)
    M.swing(rig, T(-s), f, Ma, Mb, ease="in_quad", clk=T)
    M.pose(rig, f, f"{kind}_strike", lag=lag_d, ctrl=False, feet=False)
    Wb = M.rig_matrix(rig, f) @ Mb
    travel = (Wb @ Vector((0.0, 0.7, 0.0))) - tip_a
    back = -travel.normalized() * rebound if travel.length > 1e-4 else Vector((0.0, 0.0, 0.0))
    f2 = T(2)
    W2 = Matrix.Translation(back) @ Wb
    M.pose(rig, f2, f"{kind}_strike", weight=0.85, ctrl=False, feet=False)
    CH.key_ctrl_matrix(PZ._ctrl_obj(rig), f2, M.rig_matrix(rig, f2).inverted() @ W2, 'BEZIER')
    end = T(2 + settle + recover)
    _pose(rig, end, recover_to)
    EV.emit(int(round(T(-1))), "whoosh", who=M.who(rig), weapon="katana", strength=strength, target=(rig, "hand.R"))
    return end


def _staff(f, point, direction, s_from_butt, grip=None, pose="staff_block", feet=False, edge=None):
    """Elder staff block at f: the body pose + the controller placed so the shaft point `s_from_butt` m from the
    butt lies on the world `point`, shaft along `direction`."""
    if grip is not None:
        CH.set_spear_grip(f, *grip)
    _pose(SA, f, pose, ctrl=False, feet=feet)
    return _place(SA, f, point, direction, _spear_along(f, s_from_butt), edge=edge)


def _s18():
    # ================= S18a: sprint, knee-slide under the high thrust, rising cut vs the shaft
    _root(SH, 2065, (-0.30, -0.90), 178.0, interp='LINEAR')
    M.dash(SH, 2065, 2073, (-0.30, -0.90), (-0.25, -0.30), start=False, stop=False, upper="dash")
    M.root_path(SH, 2073, 2085, (-0.25, -0.30), (-0.15, 1.05), facing1=180.0, ease="out_quad")
    M._feet_air(SH, 2073.5)
    _pose(SH, 2075, "knee_slide", weight=0.8, feet=False)
    _pose(SH, 2078, "knee_slide", feet=False)
    _pose(SH, 2084, "knee_slide", feet=False)
    M.root_path(SH, 2085, 2089, (-0.15, 1.05), (-0.12, 1.10), ease="out_quad")
    _blocked_cut(SH, 2089, "rising_R", (0.15, 1.70, 1.35), (-0.45, 0.80, 0.40), 0.45, windup=2, hold_frames=0,
                 strike=3, rebound=0.10, settle=1, recover=2)
    # elder: high thrust over the slide at 2077, retract choking up into the staff grip, block the rising cut
    _pose(SA, 2068, "staff_block", feet=False)
    CH.set_spear_grip(2069, 0.35, 0.95)
    _pose(SA, 2071, "thrust_wind")
    _pose(SA, 2074, "thrust_wind", weight=1.03, feet=False)
    _pose(SA, 2077, "thrust_ext", ctrl=False)
    _key_tip_world(SA, 2077, (0.20, 0.45, 1.55), (0.10, -1.0, -0.10))
    _root(SA, 2074, (0.0, 2.25), 360.0, interp='LINEAR')
    _root(SA, 2077, (0.0, 2.10), 363.0, interp='BEZIER')
    _root(SA, 2085, (0.0, 2.25), 360.0)
    CH.set_spear_grip(2081, 0.50, 1.40)
    _staff(2084, (0.05, 1.80, 1.30), (0.55, -0.10, 0.83), 0.90)
    _staff(2089, (0.15, 1.70, 1.35), (0.60, -0.15, 0.79), 0.90)
    M.clash(SH, SA, 2089, point=(0.15, 1.70, 1.35), strength=0.8)
    # ================= S18b: he presses - two cuts caught on the shaft
    _root(SH, 2095, (-0.10, 1.12), 180.0)
    _root(SH, 2101, (-0.05, 1.15), 180.0)
    _blocked_cut(SH, 2101, "diag_down_L", (0.10, 1.74, 1.55), (-0.45, 0.75, 0.48), 0.45, windup=3, hold_frames=1,
                 strike=3, rebound=0.10, settle=1, recover=2)
    CH.set_spear_grip(2093, 0.50, 1.40)
    _staff(2097, (0.05, 1.78, 1.45), (0.60, -0.05, 0.80), 0.90, grip=(0.50, 1.30))
    _staff(2101, (0.10, 1.74, 1.55), (0.55, -0.05, 0.84), 0.95, grip=(0.50, 1.30))
    M.clash(SH, SA, 2101, point=(0.10, 1.72, 1.55), strength=0.7)
    _root(SH, 2107, (0.05, 1.18), 180.0)
    _root(SH, 2113, (0.15, 1.20), 180.0)
    _blocked_cut(SH, 2113, "horizontal_R", (0.14, 1.86, 1.25), (0.35, 0.94, -0.05), 0.45, windup=3,
                 hold_frames=1, strike=3, rebound=0.10, settle=2, recover=3)
    _staff(2108, (0.12, 1.90, 1.30), (0.10, -0.05, 1.0), 0.90, pose="staff_left", grip=(0.62, 1.40))
    _staff(2113, (0.14, 1.86, 1.25), (0.05, -0.08, 1.0), 0.90, pose="staff_left", grip=(0.62, 1.40))
    M.clash(SH, SA, 2113, point=(0.14, 1.86, 1.25), strength=0.75)
    # ================= S18c: the staff answers - butt strike, spear-head chop; he blocks, yields 0.1 m
    _root(SH, 2125, (0.15, 1.15), 180.0)
    M.deflect(SH, 2125, "high", recover=4)
    CH.set_spear_grip(2117, 0.50, 0.85)
    _staff(2119, (-0.20, 2.00, 0.95), (0.15, 0.80, -0.58), 0.02, grip=(0.50, 0.85))    # butt low at his right hip
    _pose(SA, 2125, "staff_block", ctrl=False, feet=False)
    _key_butt_world(SA, 2125, (0.05, 1.65, 1.40), (0.20, 0.85, -0.49))
    M.overlay(SA, 2125, {"chest": (0.0, 10.0, 0.0), "spine": (0.0, 6.0, 0.0)})
    M.clash(SA, SH, 2125, point=(0.05, 1.65, 1.40), strength=0.75, att_frac=0.02)
    _root(SH, 2137, (0.15, 1.10), 180.0)
    M.deflect(SH, 2137, "mid_R", recover=1)
    CH.set_spear_grip(2128, 1.10, 1.50)
    CH.set_spear_grip(2138, 1.10, 1.50)
    _pose(SA, 2131, "spear_overhead", ctrl=False, feet=False)
    _key_tip_world(SA, 2131, (-0.60, 2.20, 2.55), (-0.30, 0.20, 0.93))
    _pose(SA, 2137, "staff_block", ctrl=False, feet=False)
    dchop = Vector((0.45, -0.62, -0.60)).normalized()
    _place(SA, 2137, (0.20, 1.68, 1.60), dchop, 0.95)
    M.clash(SA, SH, 2137, point=(0.20, 1.68, 1.60), strength=0.85)
    # ================= S18d: the bind (sword trapped on the shaft), the heave, the kick (contact on the cut)
    _root(SH, 2149, (0.15, 1.20), 180.0)
    _cut(SH, 2149, "overhead", windup=4, hold_frames=2, strike=3)
    CH.set_spear_grip(2141, 0.50, 1.40)
    _pose(SA, 2146, "staff_high")
    _staff(2149, (0.10, 1.72, 1.50), (1.0, 0.0, 0.03), 0.95, pose="staff_high")
    M.clash(SH, SA, 2149, point=(0.10, 1.72, 1.50), strength=0.6)
    # the grind: his edge slides 0.25 m along the shaft toward the elder's left hand, pressing down
    sw_d = (0.15, 0.80, -0.58)
    for f, x in ((2152, 0.18), (2155, 0.27), (2158, 0.35)):
        _pose(SH, f, "blade_lock_push", ctrl=False, feet=False)
        _place(SH, f, (x, 1.72, 1.50 - 0.01 * (f - 2149) / 3.0), sw_d, 0.42)
        _staff(f, (x, 1.72, 1.49 - 0.01 * (f - 2149) / 3.0), (1.0, 0.0, 0.03), 0.95, pose="staff_high")
    # the heave: the shaft thrown up and to his right; the sword flung up-right, the student's torso opened
    _staff(2161, (0.00, 1.90, 1.80), (1.0, 0.10, 0.35), 0.95, pose="staff_high")
    _pose(SH, 2161, "stagger_back", weight=0.7, ctrl=False, feet=False)
    _place(SH, 2161, (0.40, 1.30, 1.85), (0.55, 0.25, 0.80), 0.30)
    _pose(SH, 2168, "stagger_back", weight=0.5, feet=False)
    _pose(SH, 2172, "chudan", weight=0.4, feet=False)
    _root(SH, 2172, (0.15, 1.20), 180.0, interp='CONSTANT')
    # the kick: chamber 2163-2168, sole 10 cm short of his chest at 2172 (CUT), contact frame 2173 = S18e
    _root(SA, 2160, (0.0, 2.25), 360.0)
    _pose(SA, 2163, "kick_chamber", weight=0.7)
    _pose(SA, 2168, "kick_chamber", feet=False)
    _root(SA, 2168, (0.0, 2.30), 360.0)
    k172 = dict(POSE["kick_ext"])
    k172["legs"] = dict(k172["legs"], R=PZ.foot(-0.06, -0.72, lift=1.08, air=True, heel=-40))
    _kp(SA, 2172, k172, feet=False)
    U.set_key_interp_at(SA, 2172, 'CONSTANT')
    _kp(SA, 2173, POSE["kick_ext"], feet=False)
    _root(SA, 2173, (0.0, 2.25), 360.0)
    # ================= S18e: kicked back screen-left, the sword dragged through the dirt
    CH.set_two_hand(SH, 2173, False)
    _pose(SH, 2173, "kicked_fold", feet=False)
    _root(SH, 2173, (0.15, 1.10), 180.0, z=0.12, interp='LINEAR')
    _root(SH, 2176, (0.13, 0.30), 180.0, z=0.25, interp='LINEAR')
    _root(SH, 2178, (0.11, -0.20), 180.0, z=0.15, interp='LINEAR')
    _root(SH, 2180, (0.10, -0.60), 180.0, z=0.0, interp='LINEAR')
    M._feet_air(SH, 2173.5)
    _pose(SH, 2177, "kicked_fold", weight=0.9, feet=False)
    M.root_path(SH, 2180, 2204, (0.10, -0.60), (0.0, -4.10), ease="out_cubic")
    _pose(SH, 2182, "skid_drag", feet=False)
    _pose(SH, 2192, "skid_drag", feet=False)
    _pose(SH, 2204, "skid_drag")
    # elder: recovers the kicking leg, two measured steps back, spear held low
    _pose(SA, 2177, "kick_chamber", weight=0.8, feet=False)
    _pose(SA, 2183, "guard_low")
    M.step(SA, 2186, 2197, (0.0, 2.65), facing=360.0)
    _pose(SA, 2200, "guard_low", feet=False)
    # ================= S18f: he rises; the master shifts the spear into a javelin grip
    _pose(SH, 2209, "skid_drag", feet=False)
    _pose(SH, 2216, "rise_kneel")
    CH.set_two_hand(SH, 2215, True, blend=4)
    _pose(SH, 2225, "chudan")
    _hold_pose(SH, 2233, 2256, "chudan", step=11)
    M.step(SA, 2209, 2221, (0.0, 3.00), facing=360.0)
    _pose(SA, 2222, "guard_low", feet=False)
    CH.set_spear_grip(2225, 0.35, 0.95)
    CH.set_spear_grip(2236, 1.30, 1.60)
    CH.set_two_hand(SA, 2240, False, blend=3)
    _pose(SA, 2236, "guard_low", feet=False)
    _pose(SA, 2248, "javelin_ready")
    _pose(SA, 2256, "javelin_ready", feet=False)
    # ---------------- vfx
    VFX.grass_burst(2075, (-0.22, 0.00, 0.30), (0.0, 1.0, 0.6), count=70, fluff=0.1, seed=_seed("S18a_g1"))
    VFX.grass_burst(2081, (-0.18, 0.70, 0.30), (0.0, 1.0, 0.6), count=60, fluff=0.1, seed=_seed("S18a_g2"))
    VFX.dust_burst(2079, (-0.20, 0.40, 0.0), radius=0.7, seed=_seed("S18a_dust"))
    VFX.blade_trail("SAINT_spear_tip", "SAINT_spear_base", 2072, 2077, owner="saint")
    VFX.blade_trail("SHINOBI_katana_tip", "SHINOBI_katana_base", 2085, 2089, owner="shinobi")
    VFX.blade_trail("SHINOBI_katana_tip", "SHINOBI_katana_base", 2096, 2101, owner="shinobi")
    VFX.blade_trail("SHINOBI_katana_tip", "SHINOBI_katana_base", 2108, 2113, owner="shinobi")
    VFX.blade_trail("SAINT_spear_tip", "SAINT_spear_base", 2131, 2137, owner="saint")
    VFX.blade_trail("SHINOBI_katana_tip", "SHINOBI_katana_base", 2144, 2149, owner="shinobi")
    for k, (f, p) in enumerate(((2152, (0.18, 1.72, 1.52)), (2156, (0.30, 1.72, 1.51)))):
        VFX.sparks(f, p, direction=(0, 0, 1), count=15, speed=2.0, life=6, color="white", scale=0.5, light=False,
                   seed=_seed(f"S18d_grind{k}"))
    for k, f in enumerate(range(2182, 2203, 3)):                    # steel dragging through stones
        u = (f - 2180) / 24.0
        y = -0.20 - 3.50 * (1 - (1 - u) ** 3)
        VFX.sparks(f, (0.55, y, 0.03), direction=(0.2, 0.8, 0.6), count=10, speed=2.5, life=6, color="white",
                   scale=0.5, light=(k in (0, 3)), seed=_seed(f"S18e_drag{k}"))
        VFX.grass_burst(f, (0.45, y, 0.25), (0.1, -0.6, 0.8), count=30, speed=2.5, fluff=0.1,
                        seed=_seed(f"S18e_dirt{k}"))
    VFX.dust_burst(2180, (0.10, -0.60, 0.0), radius=0.6, seed=_seed("S18e_d1"))
    VFX.dust_burst(2204, (0.00, -4.10, 0.0), radius=0.8, seed=_seed("S18e_d2"))
    # ---------------- events
    EV.emit(2073, "skid", who="shinobi", duration=12)
    EV.emit(2075, "whoosh", who="saint", weapon="spear", strength=0.9)
    EV.emit(2121, "whoosh", who="saint", weapon="spear", strength=0.7)
    EV.emit(2133, "whoosh", who="saint", weapon="spear", strength=0.8)
    EV.emit(2149, "blade_lock", duration=9, pos=(0.10, 1.72, 1.50))
    EV.emit(2159, "whoosh", who="saint", weapon="spear", strength=0.5)
    EV.emit(2166, "whoosh", who="saint", weapon="body", strength=0.7)
    EV.emit(2173, "kick", pos=(0.15, 1.33, 1.25), strength=1.0, tags=["kick"])
    EV.emit(2180, "land", who="shinobi", strength=0.7)
    EV.emit(2180, "skid", who="shinobi", duration=24, tags=["blade"])
    EV.emit(2230, "whoosh", who="saint", weapon="spear", strength=0.2)


# =============================================================================================
# S19 (2257-2400): the javelin, the deflect (slow motion 2280-2304), into the flames; thunder; the sword again
# =============================================================================================
def _s19():
    # ================= S19a: cock, step, hurl
    _pose(SA, 2257, "javelin_ready", feet=False)
    _root(SA, 2257, (0.0, 3.00), 360.0)
    _pose(SA, 2263, "javelin_cock")
    _root(SA, 2263, (0.0, 3.00), 360.0, interp='LINEAR')
    M.root_path(SA, 2263, 2269, (0.0, 3.00), (0.0, 2.60), ease="in_quad")
    _pose(SA, 2266, "javelin_cock", weight=0.5, feet=False)
    _pose(SA, 2269, "javelin_release")
    CH.set_weapon_state(SA, 2269, "world")
    CH.snap_free("SAINT_spear_world", 2269)
    CH.set_arm_mode(SA, 2272, "fk", blend=4)
    _pose(SA, 2276, "javelin_follow")
    _root(SA, 2276, (0.0, 2.55), 360.0)
    # the javelin: aligned to its velocity, CoM from the hand (REL) to DEF at 2281
    sw = bpy.data.objects["SAINT_spear_world"]
    rel = CH.detach_matrix(sw, 2269).translation.copy()
    # the sword meets the shaft JUST BEHIND THE HEAD (0.60 m ahead of the CoM = 0.10 m behind the blade base):
    # the CoM (the object origin) arrives 0.60 m short of DEF along the flight direction (with the CoM on DEF the
    # head had already passed his shoulder at the contact - read as a near hit)
    ahead = CH.DIMS["SAINT"]["spear_length"] - CH.DIMS["SAINT"]["spear_blade_length"] - CH.DIMS["SAINT"]["spear_com"] \
        - 0.10
    d_in = (Vector(DEF) - rel).normalized()
    for _ in range(3):
        com_def = Vector(DEF) - d_in * ahead
        v0 = _ballistic_v0(rel, com_def, 2269, 2281)
        v_in = v0 + Vector((0.0, 0.0, -G * (_fx(2281) - _fx(2269))))
        d_in = v_in.normalized()
    _local_ballistic(sw, 2269, rel, v0, 2281, align_velocity=True)
    # deflected: end over end (1.2 rev/s on the fx clock), into the flames at SPEAR_LAND 2329
    q_def = v_in.normalized().to_track_quat('Y', 'Z')
    v1 = _ballistic_v0(com_def, SPEAR_LAND, 2281, 2329)
    ax = Vector(v1).cross(Vector((0.0, 0.0, 1.0))).normalized()
    _local_ballistic(sw, 2281, com_def, v1, 2328, spin_axis=ax, spin_rate=-2 * math.pi * 1.2, rot0=q_def.to_matrix())
    # at rest in the fire: blade end down, shaft tilted 25 deg (keyed CONSTANT, hidden on the S20 cut)
    d = Vector((-0.55, -0.35, 0.0)).normalized()
    a = math.radians(-25.0)
    ydir = Vector((d.x * math.cos(a), d.y * math.cos(a), math.sin(a)))
    q = ydir.to_track_quat('Y', 'Z')
    U.key(sw, "location", 2329, SPEAR_LAND, interp='CONSTANT')
    U.key(sw, "rotation_euler", 2329, tuple(q.to_euler('XYZ', sw.rotation_euler)), interp='CONSTANT')
    CH.set_weapon_state(SA, 2401, "gone")
    # ================= S19b: the deflect (slow motion 2280-2304: the macros' story clock spreads the keys)
    T = M.clock(2281)
    _root(SH, 2277, (0.0, -4.10), 180.0)
    _pose(SH, 2272, "chudan", feet=False)
    _pose(SH, T(-4), "deflect_rise_a")
    _pose(SH, T(-1), "deflect_rise_b", weight=0.8, ctrl=False, feet=False)
    _pose(SH, 2281, "deflect_rise_b", ctrl=False, feet=False)
    dw = Vector((-0.45, 0.55, 0.70)).normalized()                    # rig (0.45,-0.55,0.70) -> world (facing 180)
    _place(SH, 2281, DEF, dw, 0.46)
    M.swing(SH, T(-4), 2281, PZ.current_ctrl_matrix(SH, T(-4)), PZ.current_ctrl_matrix(SH, 2281), ease="in_quad",
            clk=T)
    _pose(SH, T(3), "deflect_rise_c", feet=False)
    _pose(SH, T(6), "deflect_rise_c", weight=1.04, feet=False)
    _root(SH, T(6), (0.0, -4.15), 180.0)
    # ================= S19c: into the flames; he watches it go; the master empty-handed, steps back, hand to hilt
    _pose(SH, 2310, "deflect_rise_c", feet=False)
    _head_turn(SH, 2318, yaw=18.0, pitch=-18.0, base_frame=2310)
    _head_turn(SH, 2328, yaw=35.0, pitch=-4.0, base_frame=2310)
    _pose(SH, 2340, "chudan")
    _root(SH, 2340, (0.0, -4.10), 180.0)
    _hold_pose(SH, 2352, 2400, "chudan", step=12)
    _pose(SA, 2284, "javelin_follow", feet=False)
    _pose(SA, 2296, "empty_watch")
    _head_turn(SA, 2318, yaw=-25.0, pitch=-6.0, base_frame=2296)
    _head_turn(SA, 2328, yaw=-30.0, pitch=4.0, base_frame=2296)
    _pose(SA, 2332, "empty_watch", feet=False)
    M.step(SA, 2331, 2336, (0.0, 2.80), facing=360.0)
    M.step(SA, 2339, 2345, (0.0, 3.00), facing=360.0)
    fk_body = dict(POSE["empty_watch"])
    fk_body.update(PZ.arm("R", flex=35, abd=-15, rot=35, elbow=95))
    _kp(SA, 2352, fk_body, feet=False)
    # ================= S19d: thunder (head lifts), the draw 2370-2384 (clears the koiguchi 2382), chudan by 2390
    _head_turn(SA, 2358, yaw=0.0, pitch=-8.0, base_frame=2352)
    _kp(SA, 2366, fk_body, feet=False)
    M.draw_sword(SA, 2382, end="chudan", two_hand=True)
    _pose(SA, 2396, "chudan", feet=False)
    _pose(SA, 2400, "chudan", feet=False)
    # ---------------- vfx
    VFX.blade_trail("SAINT_spear_tip", "SAINT_spear_base", 2265, 2269, owner="saint")
    VFX.sparks(2281, DEF, direction=(-0.3, 0.2, 1.0), count=120, speed=4.5, life=14, color="fire", scale=1.4,
               seed=_seed("S19b_sparks"))
    VFX.blade_trail("SHINOBI_katana_tip", "SHINOBI_katana_base", 2277, 2292, owner="shinobi")
    VFX.sparks(2329, SPEAR_LAND, direction=(0, 0, 1), count=50, speed=3.0, life=16, color="fire", scale=1.0,
               seed=_seed("S19c_land"))
    VFX.embers(2329, 2350, SPEAR_LAND, 1.0, rate=120.0, rise=2.5, seed=_seed("S19c_embers"))
    VFX.fire_ring(2329, (SPEAR_LAND[0], SPEAR_LAND[1], 0.0), radius=0.9, grow_frames=6, height=2.4, count=40,
                  lights=False, smoke=False, extinguish=False, f_out=2345, f_end=2370, seed=_seed("S19c_flare"))
    VFX.rain(2376, 3500, intensity=[(2376, 0.0), (2382, 0.06), (2400, 0.12), (F_RAIN, 1.0), (3470, 1.0), (3500, 0.0)],
             seed=_seed("rain"))
    for k, (f, sock) in enumerate(((2386, "SAINT_katana_tip"), (2390, "SAINT_katana_base"), (2393, "SAINT_katana_tip"),
                                   (2396, "SAINT_katana_base"), (2399, "SAINT_katana_tip"))):
        VFX.sparks(f, sock, direction=(0, 0, 1), count=6, speed=1.2, life=5, color=VFX.COLORS["water"], scale=0.35,
                   light=False, core=False, strength=0.6, seed=_seed(f"S19d_drop{k}"))
    VFX.steam(2386, 2400, (0.15, 2.60, 1.30), 0.15, height=0.5, density=0.3, seed=_seed("S19d_steam"))
    # ---------------- events
    EV.emit(2266, "step", who="saint", strength=0.8)
    EV.emit(2266, "whoosh", who="saint", weapon="spear", strength=1.0, tags=["javelin"])
    EV.emit(2281, "clash_heavy", pos=DEF, strength=0.9, who="shinobi", weapons="katana/spear")
    EV.emit(2280, "slowmo", duration=24)       # as authored (config.SLOWMO 2280-2304 spans 25 f inclusive)
    EV.emit(2286, "spear_spin", pos=(-0.5, -3.6, 2.1), duration=43)
    EV.emit(2329, "fire_burst", pos=SPEAR_LAND, strength=0.7)
    EV.emit(F_THUNDER, "thunder", distance="far", strength=0.8, tags=["thunder_first"])
    EV.emit(F_THUNDER, "music_cue", cue="thunder_first")
    EV.emit(F_THUNDER, "wind_gust", strength=0.6)
    for f in (2386, 2393, 2399):
        EV.emit(f, "steam_hiss", target=("SAINT_rig", "hand.R"), strength=0.25, tags=["blade"])
    EV.emit(2388, "steam_hiss", pos=(-9.8, 3.0, 0.5), strength=0.4, tags=["ring"])


# =============================================================================================
# S20 (2401-2496): the downpour drowns the ring; jodan facing the storm
# =============================================================================================
def _s20():
    # elder: chudan in the rain, head lowered; 2460-2490 into jodan (a stance, not a summoning), hold
    _pose(SA, 2410, "chudan", feet=False)
    _head_turn(SA, 2416, pitch=5.0, base_frame=2410)
    _hold_pose(SA, 2424, 2460, "chudan", step=12)
    _pose(SA, 2474, "jodan", weight=0.55, feet=False)
    _pose(SA, 2486, "jodan")
    _pose(SA, 2490, "jodan", weight=1.02, feet=False)
    _pose(SA, 2496, "jodan", feet=False)
    # shinobi: three steps forward in the downpour, chudan
    M.step(SH, 2402, 2410, (0.0, -3.73), facing=180.0)
    M.step(SH, 2414, 2422, (0.0, -3.37), facing=180.0)
    M.step(SH, 2426, 2434, (0.0, -3.00), facing=180.0)
    _pose(SH, 2445, "chudan")
    _hold_pose(SH, 2457, 2496, "chudan", step=13)
    # vfx: water splashing off the raised blade
    for k, f in enumerate((2474, 2481, 2488, 2494)):
        VFX.sparks(f, "SAINT_katana_tip", direction=(0, 0, 1), count=5, speed=1.2, life=5, color=VFX.COLORS["water"],
                   scale=0.3, light=False, core=False, strength=0.6, seed=_seed(f"S20b_drop{k}"))
    # the drowned ring boils: a short extra steam burst over the ring (breakdown S20a (tune)): the ring's own band
    # was invisible from the high wide
    VFX.steam(F_RAIN, 2490, (RING_C[0], RING_C[1], 0.0), RING_R, height=5.0, ring=True, glow=True, density=0.8,
              seed=_seed("S20a_steam"))
    # a distant environmental bolt with the first in-cloud flash (R15: a flash must have a source)
    VFX.lightning_bolt(2425, (-150.0, 110.0, 120.0), (-140.0, 95.0, 0.0), branches=2, flash=False, light=False,
                       seed=_seed("S20a_bolt"), guard='warn')
    # events
    EV.emit(F_RAIN, "rain_start", strength=1.0, tags=["rain_start"])
    EV.emit(F_RAIN, "music_cue", cue="rain_start")
    for k, p in enumerate(((-11.0, 1.5), (0.0, 12.5), (11.0, 1.5), (0.0, -9.5))):
        EV.emit(F_RAIN + k, "steam_hiss", pos=(p[0], p[1], 0.5), strength=1.0, duration=40)
    EV.emit(2429, "thunder", distance="mid", strength=0.7)
    EV.emit(2451, "thunder", distance="far", strength=0.5)
    EV.emit(2462, "whoosh", who="saint", weapon="katana", strength=0.35)


# =============================================================================================
# environment (per-cut key-light cheats, wind, burn, wet, flashes)
# =============================================================================================
SUN = {"S15a": (270.0, -2.0), "S15b": (270.0, -2.0), "S16a": (270.0, -2.0), "S16b": (180.0, -2.0),
       "S16c": (270.0, -2.0), "S16d": (270.0, -2.0), "S17a": (0.0, -2.0), "S17b": (270.0, -2.0),
       "S17c": (270.0, -2.0), "S17d": (270.0, -2.0), "S17e": (270.0, -2.0), "S18a": (270.0, -2.0),
       "S18b": (0.0, -2.0), "S18c": (180.0, -2.0), "S18d": (270.0, -2.0), "S18e": (270.0, -2.0),
       "S18f": (270.0, -2.0), "S19a": (270.0, -2.0), "S19b": (20.0, -2.0), "S19c": (270.0, -2.0),
       "S19d": (270.0, -2.0), "S20a": (300.0, 38.0), "S20b": (200.0, 30.0)}


def _environment():
    for cut, f0, f1 in CUTS:
        az, el = SUN[cut]
        ENV.set_sun(f0, az, el)
    ENV.set_wind(F_IGNITE, 1.6, direction_deg=config.WIND_DIR_DEFAULT)
    ENV.set_wind(F_THUNDER, 1.9)
    ENV.set_wind(2380, 2.2)
    ENV.set_wind(F_RAIN, 2.2, direction_deg=config.WIND_DIR_DEFAULT)
    ENV.set_wind(SPAN[1], 2.2)
    ENV.grass_effect("burn", dict(center=RING_C[:2], radius=RING_R, width=2.6, ramp_frames=18), 1638)
    ENV.grass_effect("wet", dict(amount=1.0, ramp_frames=48), F_RAIN)
    # S17c: the ground-level low angle needs a wider clearance (grass thinned to ~5.5 m) so the charging body
    # is not a head over a wall of grass; restored on the S17d cut (per-shot cheats hold forward)
    ENV.set_camera_clearance(CUT["S17c"][0], near=ENV.CLEAR_NEAR, far=5.5)
    ENV.set_camera_clearance(CUT["S17d"][0], near=ENV.CLEAR_NEAR, far=ENV.CLEAR_FAR)
    ENV.flash(2425, strength=0.45, duration=2, direction=(300.0, 60.0))
    ENV.flash(2443, strength=0.30, duration=2, direction=(240.0, 55.0))


# =============================================================================================
# cameras: 23 sub-cuts (docs/shots/act2.md §3; keys = out/dev/breakdown/act2/cams.py), all on the +X side
# =============================================================================================
def _cameras():
    S = CAM.shot
    both = ["shinobi", "saint"]
    S("S15a", *CUT["S15a"], [(1633, (0.60, 1.50, 50.0), (0.0, 1.50, 0.0), 28.0),
                             (1656, (0.46, 1.50, 38.0), (0.0, 1.50, 0.0), 28.0)],
      dof=None, shake=[(1633, 0.25, 6)], handheld=0.0, subjects=both, framing="wide")
    S("S15b", *CUT["S15b"], [(1657, (4.60, 4.20, 1.25), (0.20, 6.30, 1.55), 32.0),
                             (1728, (4.20, 4.40, 1.25), (0.10, 6.40, 1.60), 32.0)],
      dof=dict(fstop=2.8, distance_keys=[(1657, 3.72), (1672, 3.72), (1684, 5.00), (1728, 4.73)]),
      handheld=0.25, subjects=["saint"], framing="wide")
    S("S16a", *CUT["S16a"], [(1729, (6.00, 2.60, 2.10), (0.0, 2.70, 1.25), 28.0),
                             (1753, (5.40, 3.20, 2.00), (0.0, 4.30, 1.25), 28.0),
                             (1776, (5.40, 3.30, 2.00), (0.0, 4.30, 1.25), 28.0)],
      dof=dict(fstop=5.6, focus=5.6), handheld=0.15, subjects=both, framing="wide")
    S("S16b", *CUT["S16b"], [(1777, (0.62, 7.25, 1.78), (0.00, 3.00, 1.48), 50.0),
                             (1824, (0.85, 7.05, 1.78), (-0.10, 3.70, 1.45), 50.0)],
      dof=dict(fstop=2.8, distance_keys=[(1777, 4.60), (1813, 4.50), (1822, 3.05)]), handheld=0.35,
      shake=[(1789, 0.25, 5), (1801, 0.25, 5), (1813, 0.35, 6)], subjects=both, framing="ots")
    S("S16c", *CUT["S16c"], [(1825, (3.60, 3.20, 1.45), (-0.10, 4.90, 1.45), 40.0),
                             (1849, (3.90, 3.00, 1.45), (-0.05, 4.50, 1.42), 40.0),
                             (1872, (4.60, 2.80, 1.50), (0.00, 4.20, 1.40), 40.0)],
      dof=dict(fstop=4.0, focus=4.3), handheld=0.6, shake=[(1837, 0.4, 6), (1849, 0.3, 5)], subjects=both,
      framing="medium")
    S("S16d", *CUT["S16d"], [(1873, (5.60, 3.20, 2.25), (0.0, 3.90, 1.05), 28.0),
                             (1920, (5.60, 2.50, 2.25), (0.0, 3.20, 1.05), 28.0)],
      dof=None, handheld=0.1, shake=[(1897, 0.2, 4)], subjects=both, framing="wide")
    S("S17a", *CUT["S17a"], [(1921, (0.95, -1.20, 1.75), (0.0, 5.50, 1.45), 40.0),
                             (1947, (0.95, -1.10, 1.75), (0.0, 5.50, 1.45), 40.0)],
      dof=dict(fstop=2.8, focus=7.0), handheld=0.3, subjects=both, framing="ots")
    S("S17b", *CUT["S17b"], [(1948, (3.30, 4.40, 1.15), (0.0, 5.40, 1.50), 45.0),
                             (1968, (3.30, 4.50, 1.15), (0.0, 5.50, 1.55), 45.0)],
      dof=dict(fstop=2.8, focus=3.6), handheld=0.4, shake=[(1951, 0.3, 4), (1957, 0.35, 5)], subjects=["saint"],
      framing="mcu")
    S("S17c", *CUT["S17c"], [(1969, (3.60, 2.40, 1.05), (0.0, 5.00, 1.65), 24.0),
                             (2004, (3.50, 2.50, 1.05), (0.0, 3.90, 2.40), 24.0)],
      dof=dict(fstop=4.0, distance_keys=[(1969, 4.95), (2004, 3.9)]), handheld=0.7,
      shake=[(1981, 0.2, 4), (1993, 0.25, 4), (1999, 0.3, 5)], subjects=["saint"], framing="wide")
    S("S17d", *CUT["S17d"], [(2005, (5.80, 1.90, 1.55), (-0.20, 2.30, 1.60), 28.0),
                             (2020, (5.80, 1.90, 1.55), (-0.20, 2.20, 1.45), 28.0)],
      dof=None, shake=[(2017, 0.8, 10)], subjects=both, framing="wide")
    S("S17e", *CUT["S17e"], [(2021, (6.20, 0.20, 2.15), (-0.80, 1.90, 1.15), 35.0),
                             (2064, (5.90, -0.60, 2.10), (-0.20, 0.70, 1.25), 35.0)],
      dof=dict(fstop=4.0, distance_keys=[(2021, 8.5), (2064, 6.5)]), handheld=0.3, subjects=both, framing="medium")
    S("S18a", *CUT["S18a"], [(2065, (2.60, -1.40, 1.35), (-0.20, 0.30, 1.30), 35.0),
                             (2091, (2.40, 0.50, 1.35), (-0.05, 1.60, 1.35), 35.0)],
      dof=dict(fstop=2.8, distance_keys=[(2065, 2.95), (2077, 2.80), (2085, 2.70), (2091, 2.58)]), handheld=0.8,
      shake=[(2089, 0.4, 5)], subjects=both, framing="medium")
    S("S18b", *CUT["S18b"], [(2092, (1.20, -0.60, 1.70), (0.0, 2.20, 1.50), 40.0),
                             (2115, (1.25, -0.50, 1.70), (0.0, 2.20, 1.50), 40.0)],
      dof=dict(fstop=2.8, focus=3.05), handheld=0.8, shake=[(2101, 0.35, 5), (2113, 0.4, 5)], subjects=both,
      framing="ots")
    S("S18c", *CUT["S18c"], [(2116, (1.00, 3.60, 1.80), (0.10, 1.00, 1.45), 45.0),
                             (2139, (1.05, 3.55, 1.80), (0.10, 1.00, 1.45), 45.0)],
      dof=dict(fstop=2.8, focus=2.6), handheld=0.8, shake=[(2125, 0.4, 5), (2137, 0.45, 6)], subjects=both,
      framing="ots")
    S("S18d", *CUT["S18d"], [(2140, (3.20, 1.60, 1.40), (0.05, 1.70, 1.35), 40.0),
                             (2172, (3.10, 1.50, 1.40), (0.05, 1.70, 1.35), 40.0)],
      dof=dict(fstop=4.0, focus=3.1), handheld=0.6, shake=[(2149, 0.3, 4)], subjects=both, framing="medium")
    S("S18e", *CUT["S18e"], [(2173, (6.00, -0.60, 2.30), (0.0, 0.80, 1.00), 24.0),
                             (2208, (6.00, -1.60, 2.30), (0.0, -1.20, 1.00), 24.0)],
      dof=None, handheld=0.3, shake=[(2173, 0.6, 8)], subjects=both, framing="wide")
    S("S18f", *CUT["S18f"], [(2209, (6.50, -0.55, 2.10), (0.0, -0.50, 1.30), 24.0),
                             (2256, (6.40, -0.45, 2.10), (0.0, -0.45, 1.33), 24.0)],
      dof=None, handheld=0.15, subjects=both, framing="wide")
    S("S19a", *CUT["S19a"], [(2257, (2.60, 3.80, 1.05), (0.0, 2.70, 1.80), 35.0),
                             (2276, (2.60, 3.60, 1.05), (0.0, 2.40, 1.80), 35.0)],
      dof=dict(fstop=2.8, focus=2.8), handheld=0.4, shake=[(2269, 0.3, 5)], subjects=["saint"], framing="mcu")
    S("S19b", *CUT["S19b"], [(2277, (1.90, -5.20, 1.35), (0.0, -3.50, 1.45), 50.0),
                             (2304, (1.85, -5.10, 1.35), (0.0, -3.50, 1.50), 50.0)],
      dof=dict(fstop=2.0, focus=2.5), handheld=0.0, shake=[(2281, 0.3, 6)], subjects=["shinobi"], framing="mcu")
    S("S19c", *CUT["S19c"], [(2305, (6.00, -4.00, 2.00), (-2.0, -1.00, 1.95), 24.0),
                             (2329, (6.00, -4.00, 2.00), (-2.4, -1.40, 1.70), 24.0),
                             (2352, (6.00, -3.80, 2.00), (-2.0, -0.80, 1.60), 24.0)],
      dof=None, handheld=0.2, subjects=both, framing="wide")
    S("S19d", *CUT["S19d"], [(2353, (2.80, 2.00, 1.10), (0.0, 3.00, 1.55), 45.0),
                             (2400, (2.70, 2.10, 1.10), (0.0, 3.00, 1.65), 45.0)],
      dof=dict(fstop=2.8, distance_keys=[(2353, 3.05), (2380, 2.95), (2390, 2.80)]), handheld=0.25,
      subjects=["saint"], framing="mcu")
    S("S20a", *CUT["S20a"], [(2401, (15.0, -8.0, 10.0), (0.0, 1.00, 0.50), 28.0),
                             (2448, (14.0, -7.4, 9.3), (0.0, 1.00, 0.50), 28.0)],
      dof=None, handheld=0.0, subjects=both, framing="wide")
    S("S20b", *CUT["S20b"], [(2449, (1.90, 5.80, 2.90), (-0.20, 0.00, 1.30), 32.0),
                             (2496, (1.80, 5.62, 2.86), (-0.20, 0.00, 1.32), 32.0)],
      dof=dict(fstop=4.0, focus=3.6), handheld=0.0, subjects=both, framing="ots")


# =============================================================================================
# lane entry
# =============================================================================================
def build(ctx):
    """Lane entry (acts contract): keys only inside SPAN, cameras through cameras.shot, events through events.emit."""
    global M, PZ, CH, ENV, VFX, FXC, SH, SA, POSE
    stubs = ctx.get("stubs", {})
    missing = [m for m in ("characters", "moves", "environment", "vfx") if stubs.get(m)]
    if missing:
        raise RuntimeError(f"act2 needs the real modules (placeholders: {missing})")
    import moves as _M
    import poses as _PZ
    import characters as _CH
    import environment as _ENV
    import vfx as _VFX
    import fxclock as _FXC
    M, PZ, CH, ENV, VFX, FXC = _M, _PZ, _CH, _ENV, _VFX, _FXC
    SH, SA = ctx["chars"]["shinobi"], ctx["chars"]["saint"]
    POSE = _local_poses()
    TUNE.clear()
    NO_TUNE.clear()
    LOG.clear()
    _enter()
    _s15()
    _s16a()
    _s16b()
    _s16c()
    _s16d()
    _s17()
    _s18()
    _s19()
    _s20()
    _environment()
    _cameras()
    _tune_rolls()
    for ob in (SH, SA):
        U.freeze_handles(ob, SPAN)
    for L in LOG:
        print("[act2] note:", L)
