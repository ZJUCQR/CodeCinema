"""
draft_events.py -- plausible stand-in for out/events.json (produced later by the Blender build).

Writes out/audio/draft_events.json in the exact events.json format of :
    {fps, frame_start, frame_end, acts, shots, events:[{frame,type,...,pos,pan,dist,tags?}], music_cues}

Follows config.SHOTS description keyframes and the required events in config; fight hits sit on
the config.TEMPO_MAP beat grids via config.beat_frame().  Character positions follow a rough blocking and every
shot has a simple virtual camera on the +X side (180-degree rule), so `pan` / `dist` are computed the way
events.finalize() will compute them (camera-relative azimuth / distance).

usage:  .venv/bin/python codecinema/productions/silvergrass/audio/draft_events.py [--out out/audio/draft_events.json]
"""

import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
import config  # noqa: E402

bf = config.beat_frame      # bf("act1", beat) -> frame on the 92/120/140 BPM grids

# --------------------------------------------------------------------------- blocking (rig ground pos)
def _handoff(frame, who):
    """blocking key on a lane boundary: the rig position config.HANDOFF prescribes there"""
    return (frame, tuple(config.HANDOFF[frame][who]["pos"]))


SHINOBI_KEYS = [
    (1, (0.0, -21.0)), (97, config.SHINOBI_WALK_FROM), (240, (0.0, -12.5)), (241, (0.0, -12.0)),
    (286, config.SHINOBI_START), (589, config.SHINOBI_START), (600, (0.0, -3.6)), (700, (0.1, -3.2)),
    (840, (0.3, -2.4)), _handoff(936, "shinobi"),
    (980, (1.8, -1.3)), (1032, (2.2, 0.2)), (1090, (1.4, -1.0)), (1125, (0.6, 0.6)), (1176, (0.4, 0.9)),
    (1260, (0.2, 0.3)), (1330, (0.1, -0.8)), (1488, (0.0, -1.2)), _handoff(1632, "shinobi"), (1760, (0.3, 1.5)),
    (1920, (0.8, 3.0)), (2010, (3.0, 4.5)), (2064, (3.2, 5.0)), (2150, (1.5, 6.2)), (2190, (1.2, 5.6)),
    (2230, (0.0, -1.0)), (2256, (0.0, -1.5)), (2400, (0.0, -3.0)), _handoff(2496, "shinobi"), (2700, (0.6, -1.4)),
    (2880, (0.9, 0.2)), (2950, (0.5, -2.5)), (3000, (0.0, -6.0)), _handoff(3072, "shinobi"), (3257, (0.0, -6.0)),
    (3271, (0.0, 3.0)), (3840, (0.0, 3.0)),
]
SAINT_KEYS = [
    (1, config.SAINT_START), (588, config.SAINT_START), (595, (0.0, -2.6)), (672, (0.0, -2.2)), (840, (0.0, 1.2)),
    _handoff(936, "saint"), (980, (-1.6, 2.2)), (1032, (-2.1, 0.6)), (1176, (-0.6, 2.4)), (1330, (0.0, 1.9)),
    (1380, (0.1, 1.5)), (1440, (0.6, 5.5)), (1500, (0.6, 5.8)), (1575, (0.2, 6.4)), _handoff(1632, "saint"),
    (1760, (1.6, 5.8)), (1920, (1.0, 5.2)), (1990, (2.4, 6.0)), (2064, (1.9, 7.0)), (2256, (0.6, 7.3)),
    (2400, (0.0, 3.0)), _handoff(2496, "saint"), (2700, (0.0, 1.3)), (2880, (0.2, 2.5)), (2950, (0.0, 0.8)),
    (3010, (0.0, 0.8)), (3040, (0.0, 2.5)), (3257, (0.0, 2.5)), (3271, (0.0, -3.0)), (3840, (0.0, -3.0)),
]


def _interp(keys, f):
    if f <= keys[0][0]:
        return keys[0][1]
    for (f0, p0), (f1, p1) in zip(keys, keys[1:]):
        if f0 <= f <= f1:
            u = (f - f0) / max(1, f1 - f0)
            return (p0[0] + (p1[0] - p0[0]) * u, p0[1] + (p1[1] - p0[1]) * u)
    return keys[-1][1]


def pos_of(who, f, z=0.0):
    x, y = _interp(SHINOBI_KEYS if who == "shinobi" else SAINT_KEYS, f)
    return [round(x, 3), round(y, 3), z]


def mid(f, z=1.2):
    a, b = pos_of("shinobi", f), pos_of("saint", f)
    return [round((a[0] + b[0]) / 2, 3), round((a[1] + b[1]) / 2, 3), z]


# --------------------------------------------------------------------------- per-shot virtual cameras (+X side)
CAMERAS = {
    "S01": ((0, -30, 2), (0, 0, 1)), "S02": ((0, -34, 7), (0, 0, 1)), "S03": ("behind_shinobi", None),
    "S04": ((1.4, 2.4, 1.6), "saint_head"), "S05": ((48, 0, 2.0), (0, 0, 1.2)), "S06": ((0.45, 3.4, 1.0), (0.15, 3.85, 1.0)),
    "S07": ((5.5, -1.5, 1.3), "mid"), "S08": ("orbit", 5.5), "S09": ((0.6, 4.2, 1.7), "shinobi_head"),
    "S10": ((6.5, -0.4, 0.8), "mid"), "S11": ((9, -2, 2.0), "mid"), "S12": ("cuts", 3.2), "S13": ((4.0, -1.5, 1.3), "mid"),
    "S14": ((2.0, 5.5, 0.5), "saint_head"), "S15": ((1, 1, 14), (0.0, 1.0, 0)), "S16": ((6, 1, 1.5), "mid"),
    "S17": ((10, 2, 2.5), "mid"), "S18": ("cuts", 3.0), "S19": ((6, 1, 1.3), "mid"), "S20": ((18, -6, 12), (0, 0, 0)),
    "S21": ((40, -10, 3.0), (0, 0, 3.0)), "S22": ("cuts", 4.0), "S22b": ("cuts", 3.0), "S23": ((7, -1, 1.5), "mid"),
    "S24": ((45, 0, 1.8), (0, -2, 1.2)), "S25": ((45, 0, 1.8), (0, 0, 1.2)), "S26": ((3.0, 3.8, 1.2), "shinobi_head"),
    "S27": ((9.0, 0, 1.4), (0, 0, 1.0)), "S28": ((14, -14, 12), (0, 0, 0)), "S29": ((1.2, -2.0, 0.4), (-0.8, -2.2, 0.2)),
}


# focal lengths (mm) per shot and the S24 sub-cuts, each with its own camera:
# (start, end, camera xyz, look-at, lens) -- the real export carries cuts[{id, start, end, camera, lens}] + event 'cut'
LENS = {"S02": 18, "S05": 135, "S06": 100, "S15": 24, "S20": 24, "S21": 18, "S24": 135, "S25": 135, "S26": 50,
        "S28": 24, "S29": 50}
SUBCUTS = {
    "S24a": (3073, 3120, (45, 0, 1.8), (0, -2, 1.2), 135),
    "S24b": (3121, 3156, (0.35, -6.4, 0.95), (0.05, -6.05, 0.9), 85),        # ECU of the shinobi's scabbard mouth
    "S24c": (3157, 3196, (6.0, 1.8, 0.4), (0, 2.5, 1.8), 35),
    "S24d": (3197, 3232, (4.5, -5.0, 1.2), (0, -6, 1.0), 50),
    "S24e": (3233, 3264, (0.5, -6.3, 1.3), (0.1, -6.15, 1.2), 100),        # the drop on the headband tail
}


def shot_at(frame):
    for s in config.SHOTS:
        if s["start"] <= frame <= s["end"]:
            return s
    return config.SHOTS[-1]


def cut_at(frame):
    for cid, (a, b, cam, look, lens) in SUBCUTS.items():
        if a <= frame <= b:
            return cid, lens
    s = shot_at(frame)
    return s["id"], LENS.get(s["id"], 35)


def cuts_list():
    out = []
    for s in config.SHOTS:
        subs = [(cid, v) for cid, v in SUBCUTS.items() if cid.startswith(s["id"]) and cid[len(s["id"]):].isalpha()]
        if subs:
            for cid, (a, b, cam, look, lens) in subs:
                out.append(dict(id=cid, start=a, end=b, camera=f"CAM_{cid}", lens=float(lens)))
        else:
            out.append(dict(id=s["id"], start=s["start"], end=s["end"], camera=f"CAM_{s['id']}",
                            lens=float(LENS.get(s["id"], 35))))
    return out


def camera_at(frame):
    for cid, (a, b, cam, look, lens) in SUBCUTS.items():
        if a <= frame <= b:
            return cam, look
    s = shot_at(frame)
    a, b = CAMERAS.get(s["id"], ((10, 0, 1.5), "mid"))
    sp, ep = pos_of("shinobi", frame), pos_of("saint", frame)
    m = mid(frame)
    if a == "behind_shinobi":
        return (sp[0] + 0.3, sp[1] - 1.6, 0.5), (sp[0], sp[1] + 4, 0.9)
    if a == "orbit":
        u = (frame - s["start"]) / (s["end"] - s["start"])
        ang = math.radians(-50 + 100 * u)
        return (m[0] + b * math.cos(ang), m[1] + b * math.sin(ang), 1.5), m
    if a == "cuts":   # fast cutting, all on the +X side: camera angle changes every ~1.2 s
        k = (frame - s["start"]) // 29
        ang = math.radians([-35, 30, -10, 45, 0, -45][k % 6])
        return (m[0] + b * math.cos(ang), m[1] + b * math.sin(ang), 1.4), m
    look = {"mid": m, "saint_head": [ep[0], ep[1], 1.7], "shinobi_head": [sp[0], sp[1], 1.6]}.get(b, b)
    return a, look


def pan_dist(frame, pos):
    cam, look = camera_at(frame)
    fx, fy = look[0] - cam[0], look[1] - cam[1]
    fl = math.hypot(fx, fy) or 1.0
    fx, fy = fx / fl, fy / fl
    rx, ry = fy, -fx                      # right vector (z-up, camera looking along f)
    dx, dy, dz = pos[0] - cam[0], pos[1] - cam[1], pos[2] - cam[2]
    dh = math.hypot(dx, dy) or 1e-6
    pan = max(-1.0, min(1.0, 1.3 * (dx * rx + dy * ry) / dh))
    if dx * fx + dy * fy < 0:             # behind the camera -> fold towards the sides, softer
        pan *= 0.8
    dist = math.sqrt(dx * dx + dy * dy + dz * dz)
    return round(pan, 3), round(dist, 2)


# --------------------------------------------------------------------------- event helpers
EVENTS = []


def ev(frame, etype, pos=None, who=None, tags=None, **attrs):
    frame = int(round(frame))
    e = dict(frame=frame, type=etype)
    if who:
        e["who"] = who
    e.update(attrs)
    if pos is None and who in ("shinobi", "saint"):
        pos = pos_of(who, frame, 0.9)
    if pos is not None:
        e["pos"] = [round(float(v), 3) for v in pos]
        e["pan"], e["dist"] = pan_dist(frame, e["pos"])
    if tags:
        e["tags"] = list(tags)
    e["cut"] = cut_at(frame)[0]
    EVENTS.append(e)
    return e


def steps(who, f0, f1, period, jitter=(0, 1, -1, 0, 1), **kw):
    f = f0
    i = 0
    while f <= f1:
        ev(f + jitter[i % len(jitter)], "step", who=who, pos=pos_of(who, f, 0.05), foot="LR"[i % 2], **kw)
        f += period
        i += 1


def exchange(f_contact, attacker, strength=0.7, weapon="katana", kind="clash", lead=4, **kw):
    """a swing (whoosh `lead` frames before) meeting a block at f_contact"""
    ev(f_contact - lead, "whoosh", who=attacker, weapon=weapon, strength=round(min(1.0, strength + 0.1), 2))
    if kind:
        ev(f_contact, kind, pos=mid(f_contact), strength=strength, **kw)


# --------------------------------------------------------------------------- the draft, shot by shot
def build():
    EVENTS.clear()
    C = config.MUSIC_CUES
    for name, fr in C.items():
        ev(fr, "music_cue", cue=name)

    # ---------------- PROLOGUE (mirrors codecinema/productions/silvergrass/blender/acts/prologue.py events)
    ev(28, "wind_gust", strength=0.45)
    ev(40, "clash", pos=[0.0, 70.0, 1.5], strength=0.6, tags=["distant", "omen"])  # distant blade ring (sound only)
    ev(70, "thunder", distance="far", pos=[-900.0, 2600.0, 500.0], tags=["distant", "omen"])
    ev(73, "step", who="shinobi", pos=pos_of("shinobi", 73, 0.05), strength=0.4)   # faint steps under the black
    ev(86, "step", who="shinobi", pos=pos_of("shinobi", 86, 0.05), strength=0.4)
    ev(84, "wind_gust", strength=0.55)
    ev(97, "wind_gust", strength=0.7)
    f = 99.0
    while f <= 239:                                                                 # S02 walk, ~12.9 f per step
        ev(f, "step", who="shinobi", pos=pos_of("shinobi", f, 0.05), strength=0.55)
        f += 12.9
    ev(150, "wind_gust", strength=0.6)
    for f in (241, 254, 267, 280):                                                  # S03 knee-height walk
        ev(f, "step", who="shinobi", pos=pos_of("shinobi", f, 0.05), strength=0.6)
    ev(288, "step", who="shinobi", pos=pos_of("shinobi", 288, 0.05), strength=0.5)  # the stopping step
    ev(300, "wind_gust", strength=0.5)
    ev(350, "wind_gust", strength=0.6)
    # ---------------- ACT I
    ev(458, "draw", who="shinobi")
    ev(492, "step", who="saint", strength=0.6)
    ev(500, "step", who="saint", strength=0.4)
    ev(470, "wind_gust", strength=0.4)
    ev(566, "tsuba_click", pos=[0.2, 3.85, 1.0])                                     # click motif #1
    ev(589, "dash", who="saint", strength=1.0)
    ev(591, "whoosh", who="saint", weapon="katana", strength=1.0)
    ev(C["first_clash"], "clash_heavy", pos=mid(C["first_clash"]), strength=1.0, tags=["first_clash"])
    ev(C["first_clash"], "slowmo", duration=35)
    ev(632, "skid", who="shinobi", duration=12)
    # S08 3-hit combo: deflect, deflect, sidestep (hits on the 92-BPM grid)
    steps("saint", 676, 694, 9)
    exchange(bf("act1", 5), "saint", 0.75)
    ev(bf("act1", 5) + 6, "step", who="shinobi", strength=0.5)
    exchange(bf("act1", 7), "saint", 0.85)
    ev(bf("act1", 7) + 6, "step", who="shinobi", strength=0.5)
    ev(bf("act1", 9) - 4, "whoosh", who="saint", weapon="katana", strength=0.9)      # thrust, dodged
    ev(bf("act1", 9), "step", who="shinobi", strength=0.7)
    ev(bf("act1", 9) + 5, "step", who="shinobi", strength=0.5)
    steps("saint", 800, 832, 16)
    # S09 counters: parried, then evaded
    ev(bf("act1", 14) - 8, "dash", who="shinobi", strength=0.6)
    exchange(bf("act1", 14), "shinobi", 0.7)
    ev(bf("act1", 16) - 4, "whoosh", who="shinobi", weapon="katana", strength=0.85)
    ev(bf("act1", 16), "step", who="saint", strength=0.7)
    ev(bf("act1", 16) + 8, "step", who="saint", strength=0.5)
    steps("shinobi", 910, 930, 10)
    # S10 circling; the shinobi sinks into the tall grass (hiding in the grass); the elder listens; heartbeat
    steps("shinobi", 940, 986, 16)
    steps("saint", 948, 1030, 18, jitter=(1, 0, 2, -1))
    ev(992, "step", who="shinobi", strength=0.25, surface="grass_crawl")
    ev(1008, "step", who="shinobi", strength=0.15, surface="grass_crawl")
    ev(944, "heartbeat", bpm=62, duration=86)
    ev(962, "wind_gust", strength=0.85)
    ev(1010, "wind_gust", strength=0.6)
    # S11 re-sheathe; one draw-cut shears the grass tops; the shinobi is flushed out, leaps, overhead block
    ev(1054, "sheathe", who="saint")                                                # act1b: beat 27
    ev(1066, "step", who="saint", strength=0.6)
    ev(bf("act1", 30) - 2, "whoosh", who="saint", weapon="katana", strength=1.0)
    ev(bf("act1", 30), "grass_shear", pos=pos_of("saint", 1101, 0.9))              # act1b: the draw-cut, beat 30
    ev(1102, "jump", who="shinobi")
    ev(bf("act1", 32) - 7, "whoosh", who="shinobi", weapon="katana", strength=1.0)
    ev(bf("act1", 32), "clash_heavy", pos=mid(1132, 1.8), strength=0.9)
    ev(bf("act1", 32) + 6, "land", who="shinobi", strength=0.8)
    # S12 flurry on the grid: 1195/1210/1226/1241/1257/1273, blade lock 1276-1320, shove 1320, skid apart
    for i, beat in enumerate(range(36, 42)):
        fc = bf("act1", beat)
        exchange(fc, "saint" if i % 2 == 0 else "shinobi", 0.6 + 0.06 * (i % 3), lead=4)
        if i % 2 == 1:
            ev(fc + 5, "step", who="shinobi", strength=0.4)
    ev(1276, "blade_lock", pos=mid(1276), duration=44)
    ev(1320, "whoosh", who="saint", weapon="body", strength=0.7)
    ev(1322, "skid", who="shinobi", duration=20)
    ev(1323, "skid", who="saint", duration=16)
    # S13 first two-handed overhead ~1350, perfect deflect ~1367, hat cut 1420, skid back
    ev(1351, "whoosh", who="saint", weapon="katana", strength=1.0)                  # act1b: beat 46
    ev(C["perfect_deflect"], "perfect_deflect", pos=mid(C["perfect_deflect"], 1.7), strength=1.0)
    ev(C["perfect_deflect"], "slowmo", duration=41)
    ev(1414, "whoosh", who="shinobi", weapon="katana", strength=0.95)
    ev(C["hat_cut"], "hat_cut", pos=pos_of("saint", C["hat_cut"], 1.85))
    ev(1432, "skid", who="saint", duration=22)
    # S14 sheathe, shed the haori, draw the spear over the shoulder ~1584 (sheath spins off), twirl
    ev(1508, "sheathe", who="saint")
    ev(1530, "haori_shed", pos=pos_of("saint", 1530, 1.4))
    ev(1520, "wind_gust", strength=0.8)
    ev(1586, "spear_draw", pos=pos_of("saint", 1586, 1.8))                          # act1b D4: beat 61
    ev(1590, "sheath_drop", pos=[1.8, 7.5, 0.5])
    ev(1600, "spear_spin", who="saint", duration=28)
    # ---------------- ACT II (120 BPM, 12 f per beat from 1633)
    ev(C["act2_start"], "land", pos=[0.0, 6.5, 0.0], strength=1.0)                  # spear-butt slam
    ev(C["act2_start"], "fire_ignite", pos=[0.0, 0.0, 0.2])
    ev(1648, "fire_burst", pos=[-6.0, 2.0, 0.5])
    ev(1668, "fire_burst", pos=[2.0, 8.0, 0.3], strength=0.5, tags=["haori"])
    ev(1753 - 6, "whoosh", who="saint", weapon="spear", strength=1.0)               # 360 sweep over the ducking shinobi
    ev(1753, "step", who="shinobi", strength=0.6)
    exchange(1789, "saint", 0.75, weapon="spear")
    exchange(1801, "saint", 0.8, weapon="spear")
    ev(1813 - 4, "whoosh", who="saint", weapon="spear", strength=0.9)
    ev(1813, "kunai_deflect", pos=mid(1813), strength=0.7)                          # third thrust turned by a kunai
    ev(1815, "skid", who="shinobi", duration=10, tags=["blade"])                    # slides along the shaft
    ev(1880, "jump", who="shinobi")
    ev(1885 - 4, "whoosh", who="saint", weapon="spear", strength=1.0)
    ev(1897, "land", who="shinobi", strength=0.6)
    steps("saint", 1900, 1916, 8)
    ev(1936, "spear_spin", who="saint", duration=26)
    for i, fd in enumerate((1945, 1951, 1957)):
        ev(fd - 9, "kunai_throw", who="shinobi")
        ev(fd, "kunai_deflect", pos=pos_of("saint", fd, 1.4))
    ev(1984, "jump", who="saint")
    ev(2005, "whoosh", who="saint", weapon="spear", strength=1.0)
    ev(2006, "roll", who="shinobi")
    ev(bf("act2", 31), "land", who="saint", strength=1.0)                           # leaping slam (2005 f)
    ev(bf("act2", 31), "fire_burst", pos=pos_of("saint", 2005, 0.3), strength=1.0)
    ev(bf("act2", 31) + 2, "shockwave", pos=pos_of("saint", 2007, 0.2), strength=0.5)
    ev(2068, "skid", who="shinobi", duration=14)                                    # low sliding cut
    ev(2070, "whoosh", who="shinobi", weapon="katana", strength=0.8)
    for i, beat in enumerate((38, 39, 40, 41.5, 43)):
        fc = bf("act2", beat)
        exchange(fc, "saint" if i % 2 else "shinobi", 0.65 + 0.05 * i, weapon="katana" if i % 2 == 0 else "spear", lead=4)
    ev(2170, "step", who="shinobi", strength=0.6)
    ev(bf("act2", 46) - 3, "whoosh", who="saint", weapon="body", strength=0.8)
    ev(bf("act2", 46), "kick", pos=pos_of("shinobi", 2185, 1.0))
    ev(bf("act2", 46) + 3, "skid", who="shinobi", duration=32, tags=["blade"])
    steps("saint", 2205, 2250, 15)
    ev(2266, "whoosh", who="saint", weapon="spear", strength=1.0)                    # javelin ~2270
    ev(2281, "clash_heavy", pos=pos_of("shinobi", 2281, 1.3), strength=0.9)          # deflected (act2 lane: 2281)
    ev(2280, "slowmo", duration=24)
    ev(2290, "spear_spin", pos=[3.0, -2.0, 1.5], duration=30)
    ev(2330, "fire_burst", pos=[7.5, -4.0, 0.5], strength=0.7)                       # into the flames
    ev(C["thunder_first"], "thunder", distance="far", tags=["thunder_first"])
    ev(2372, "draw", who="saint")
    ev(2392, "steam_hiss", pos=pos_of("saint", 2392, 1.5), strength=0.3, tags=["blade"])
    ev(C["rain_start"], "rain_start")
    ev(2408, "steam_hiss", pos=[-5.0, 3.0, 0.3])
    ev(2440, "steam_hiss", pos=[5.0, 5.0, 0.3], strength=0.7)
    ev(2430, "thunder", distance="far")
    ev(2462, "whoosh", who="saint", weapon="body", strength=0.35)                   # jodan
    # ---------------- ACT III (140 BPM from 2497)
    ev(C["raikiri"] - 3, "whoosh", who="saint", weapon="katana", strength=1.0)
    ev(C["raikiri"], "raikiri", pos=pos_of("saint", C["raikiri"], 2.4), tags=["raikiri"])
    ev(C["raikiri"] + 4, "tree_split", pos=[6.0, 30.0, 4.0])
    ev(2560, "steam_hiss", pos=[6.0, 30.0, 3.0], strength=0.5)
    # S22 strobe flurry: flashes >= 12 f apart; clashes / near-miss / deflect on the grid; environmental bolts
    ev(2598, "lightning_strike", pos=[14.0, 20.0, 0.0])
    for i, beat in enumerate((12, 14, 16, 18, 21, 24)):
        fc = bf("act3", beat)
        if i == 2:
            ev(fc - 4, "whoosh", who="saint", weapon="katana", strength=0.9)       # near-miss
            ev(fc, "step", who="shinobi", strength=0.7)
        else:
            exchange(fc, "saint", 0.72 + 0.05 * (i % 3), lead=4)
    ev(bf("act3", 10) - 1, "thunder", distance="near")
    ev(2700, "electric_crackle", pos=[-9.0, 12.0, 0.2], duration=20)
    ev(2744, "lightning_strike", pos=[-11.0, 3.0, 0.0])
    # S22b the shinobi's counter-attack: three strikes drive the elder back
    for beat in (29, 30.5, 32):
        exchange(bf("act3", beat), "shinobi", 0.8, lead=4)
    ev(bf("act3", 32) + 6, "step", who="saint", strength=0.8)
    # S23 low point: the grounded jodan cut (~2950) splits the rain; spray ring; tumble; kneel ~3000; two steps
    ev(bf("act3", 44) - 5, "whoosh", who="saint", weapon="katana", strength=1.0)
    ev(bf("act3", 44), "rain_split", pos=mid(2950, 1.5), tags=["low_point"])
    ev(bf("act3", 44) + 2, "shockwave", pos=pos_of("saint", 2952, 0.1), strength=0.8, tags=["water"])
    ev(2962, "roll", who="shinobi")
    ev(3000, "kneel", who="shinobi")
    ev(3003, "hit", pos=pos_of("shinobi", 3003, 0.3), strength=0.3, tags=["plant_blade"])
    ev(3012, "step", who="saint", strength=0.9)
    ev(3040, "step", who="saint", strength=0.9)
    # ---------------- FINALE
    ev(3100, "step", who="shinobi", strength=0.3)                                   # rises
    ev(3150, "sheathe", who="shinobi")                                              # click motif #2 (rain alone)
    ev(3150, "tsuba_click", pos=pos_of("shinobi", 3150, 1.0))
    ev(3176, "whoosh", who="saint", weapon="body", strength=0.3)                    # lifts into jodan
    ev(3256, "drip", pos=pos_of("shinobi", 3256, 0.0))                              # the drop hits the puddle
    ev(3257, "dash", who="shinobi", strength=1.0)
    ev(3258, "dash", who="saint", strength=1.0)
    ev(C["final_pass"], "thunder", distance="near", tags=["final_pass"])            # the flash's thunderclap
    ev(3269, "slowmo", duration=187)
    ev(3412, "sheathe", who="shinobi")                                              # the guard seats = click #3 ...
    ev(3412, "tsuba_click", pos=pos_of("shinobi", 3412, 1.0))                       # (the tsuba_click owns the click)
    ev(3412, "sword_break", pos=pos_of("saint", 3412, 1.3))                         # ... on the exact frame
    ev(3414, "cord_cut", pos=pos_of("saint", 3414, 1.2))
    ev(3440, "land", pos=[-0.8, -2.2, 0.0], strength=0.25, tags=["blade_tip"])
    ev(3470, "kneel", who="saint")
    ev(3476, "hit", pos=pos_of("saint", 3476, 0.3), strength=0.3, tags=["plant_blade"])
    ev(3480, "rain_stop")
    ev(3556, "step", who="shinobi", strength=0.35)
    ev(3566, "step", who="shinobi", strength=0.3)
    steps("shinobi", 3620, 3730, 18, strength=0.35)
    ev(3610, "wind_gust", strength=0.5)
    ev(3680, "wind_gust", strength=0.35)
    ev(C["end_card"], "bell", pos=[0.0, 60.0, 5.0])
    EVENTS.sort(key=lambda e: (e["frame"], e["type"]))
    return EVENTS


def to_doc(events):
    return dict(
        fps=config.FPS, frame_start=config.FRAME_START, frame_end=config.FRAME_END,
        acts=config.ACTS,
        shots=[dict(id=s["id"], start=s["start"], end=s["end"]) for s in config.SHOTS],
        cuts=cuts_list(),
        events=events,
        music_cues=dict(config.MUSIC_CUES),
        draft=True,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=config.DRAFT_EVENTS_JSON)
    a = ap.parse_args()
    evs = build()
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(to_doc(evs), f, ensure_ascii=False, indent=1)
    by = {}
    for e in evs:
        by[e["type"]] = by.get(e["type"], 0) + 1
    per_shot = {}
    for e in evs:
        sid = shot_at(e["frame"])["id"]
        per_shot[sid] = per_shot.get(sid, 0) + 1
    print(f"wrote {a.out}: {len(evs)} events")
    print("by type:", dict(sorted(by.items())))
    print("per shot:", per_shot)


if __name__ == "__main__":
    main()
