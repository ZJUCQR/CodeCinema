"""Character performance as continuous functions of time.

A `Track` turns one character's timed events (place, move, turn, act, face,
look, say, blush, show/hide, scale) into a semantic pose at any time: root
position and facing, body/chest/head rotations, hand and foot targets, wings,
ears, tail and face cells. It is pure Python, so the Blender rig, the camera
director and the Foley planner all read the same performance: a footstep in
the sound lands on the frame where the foot touches the ground.
"""
from __future__ import annotations

import bisect
import math

from codecinema.cartoon import faces

TAU = 2 * math.pi


# ---------------------------------------------------------------------------- curves
def clamp(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


def smooth(u):
    u = clamp(u)
    return u * u * (3 - 2 * u)


def smoother(u):
    u = clamp(u)
    return u * u * u * (u * (u * 6 - 15) + 10)


def ease_out_back(u, k=1.6):
    u = clamp(u) - 1
    return 1 + u * u * ((k + 1) * u + k)


def window(t, start, end, fade_in=0.25, fade_out=0.3):
    """0 outside [start, end], easing to 1 inside: how strongly an action holds."""
    if t <= start or t >= end:
        return 0.0
    return smooth((t - start) / max(fade_in, 1e-3)) * smooth((end - t) / max(fade_out, 1e-3))


def keys(t, points):
    """Piecewise smooth interpolation through (time, value) pairs; values may be tuples."""
    if t <= points[0][0]:
        return points[0][1]
    for (t0, a), (t1, b) in zip(points, points[1:]):
        if t <= t1:
            u = smooth((t - t0) / max(t1 - t0, 1e-6))
            if isinstance(a, tuple):
                return tuple(x + (y - x) * u for x, y in zip(a, b))
            return a + (b - a) * u
    return points[-1][1]


def wrap_angle(a):
    return (a + math.pi) % TAU - math.pi


def heading_of(dx, dy):
    """Facing angle for motion along (dx, dy): characters face -Y at angle 0."""
    return math.atan2(dx, -dy)


def noise(t, seed=0.0):
    """Smooth deterministic wobble in [-1, 1] for idle life."""
    return (math.sin(t * 1.7 + seed * 3.1) * 0.5 + math.sin(t * 2.9 + seed * 1.3) * 0.3
            + math.sin(t * 0.83 + seed * 7.7) * 0.2)


# ---------------------------------------------------------------------------- paths
class Move:
    """Travel along waypoints between two times with eased speed (no foot sliding: steps follow distance)."""

    def __init__(self, start, end, points, gait, stride, ease=0.35, ground=None):
        self.start, self.end = start, max(end, start + 1e-3)
        self.points = [tuple(p) for p in points]
        self.ground = ground or (lambda x, y: 0.0)
        self.gait = gait
        seg = [math.dist(a[:2], b[:2]) for a, b in zip(self.points, self.points[1:])]
        self.cum = [0.0]
        for d in seg:
            self.cum.append(self.cum[-1] + d)
        self.length = self.cum[-1]
        steps = max(1, round(self.length / max(stride, 1e-3))) if self.length > 1e-3 else 0
        self.steps = steps
        self.stride = self.length / steps if steps else stride
        dur = self.end - self.start
        self.ease = min(ease, dur * 0.4)

    def progress(self, t):
        """Distance traveled at t with eased start and stop (trapezoid speed profile)."""
        dur = self.end - self.start
        e = self.ease
        x = clamp(t - self.start, 0, dur)
        if dur <= 0 or self.length <= 0:
            return 0.0
        vmax = 1.0 / (dur - e) if dur > e else 1.0 / dur
        if x < e:
            d = 0.5 * vmax * x * x / e
        elif x > dur - e:
            y = dur - x
            d = 1.0 - 0.5 * vmax * y * y / e
        else:
            d = 0.5 * vmax * e + vmax * (x - e)
        return clamp(d) * self.length

    def time_at(self, distance):
        lo, hi = self.start, self.end
        for _ in range(40):
            mid = (lo + hi) / 2
            if self.progress(mid) < distance:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    def point(self, s):
        """(x, y) on the ground, or (x, y, z) when either end of the segment has an absolute height."""
        s = clamp(s, 0, self.length)
        i = max(0, min(len(self.points) - 2, bisect.bisect_right(self.cum, s) - 1))
        a, b = self.points[i], self.points[i + 1]
        seg = self.cum[i + 1] - self.cum[i]
        u = (s - self.cum[i]) / seg if seg > 1e-9 else 0.0
        x, y = a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u
        heading = heading_of(b[0] - a[0], b[1] - a[1])
        if len(a) < 3 and len(b) < 3:
            return (x, y), heading
        za = a[2] if len(a) > 2 else self.ground(a[0], a[1])
        zb = b[2] if len(b) > 2 else self.ground(b[0], b[1])
        return (x, y, za + (zb - za) * u), heading

    def speed(self, t, dt=0.02):
        return (self.progress(t + dt) - self.progress(t - dt)) / (2 * dt)


# ---------------------------------------------------------------------------- actions
# An action maps (local time, duration, params, track) -> partial pose. Arm "hand" vectors are offsets
# from the shoulder in chest space (+x is the character's left, -y forward, +z up), in meters.

def _arm(m, side, x, y, z):
    """Offset scaled to the character's arm length."""
    a = m["arm"]
    return {"hand": (side * x * a, y * a, z * a)}


def act_wave(tau, dur, p, tr):
    m = tr.m
    side = -1 if p.get("hand", "r") == "r" else 1
    swing = 0.18 * math.sin(TAU * 2.0 * tau)
    out = {"arms": {"r" if side < 0 else "l": _arm(m, side, 0.35 + swing, -0.25, 0.75)},
           "head": {"roll": 0.12 * side}, "body": {"roll": -0.04 * side}}
    if tr.plan != "biped":
        out["wings"] = {"r" if side < 0 else "l": {"flap": 1.3 + 0.35 * math.sin(TAU * 2.4 * tau)}}
    return out


def act_wave_both(tau, dur, p, tr):
    m = tr.m
    s = 0.2 * math.sin(TAU * 2.2 * tau)
    out = {"arms": {"l": _arm(m, 1, 0.45 + s, -0.2, 0.8), "r": _arm(m, -1, 0.45 - s, -0.2, 0.8)},
           "body": {"z": 0.02 * abs(math.sin(TAU * 2.2 * tau)) * m["height"]}}
    if tr.plan != "biped":
        out["wings"] = {k: {"flap": 1.3 + 0.4 * math.sin(TAU * 2.6 * tau + i)} for i, k in enumerate("lr")}
    return out


def act_point(tau, dur, p, tr):
    side = -1 if p.get("hand", "r") == "r" else 1
    up = p.get("up", 0.15)
    out = {"arms": {"r" if side < 0 else "l": _arm(tr.m, side, 0.2, -0.95, up)}, "chest": {"yaw": -0.15 * side}}
    if tr.plan != "biped":
        out["wings"] = {"r" if side < 0 else "l": {"flap": 1.0, "sweep": -0.8}}
    return out


def act_cheer(tau, dur, p, tr):
    m = tr.m
    bounce = abs(math.sin(TAU * 1.6 * tau))
    out = {"arms": {"l": _arm(m, 1, 0.3, -0.1, 0.95), "r": _arm(m, -1, 0.3, -0.1, 0.95)},
           "body": {"z": 0.1 * bounce * m["height"], "squash": 1 + 0.08 * (bounce - 0.5)},
           "head": {"pitch": -0.15}, "airborne": 0.1 * bounce * m["height"]}
    if tr.plan != "biped":
        out["wings"] = {k: {"flap": 1.4 + 0.5 * math.sin(TAU * 3 * tau + i)} for i, k in enumerate("lr")}
    return out


def act_jump(tau, dur, p, tr):
    """Anticipate, launch, hang, land and recover: squash and stretch on a parabola."""
    m = tr.m
    h = p.get("height", 0.35) * m["height"]
    a, l, land = 0.18 * dur, 0.28 * dur, 0.78 * dur
    if tau < a:
        u = tau / a
        return {"body": {"z": -0.08 * m["height"] * smooth(u), "squash": 1 - 0.18 * smooth(u), "pitch": 0.15 * u},
                "arms": {"l": _arm(m, 1, 0.25, 0.4, -0.6), "r": _arm(m, -1, 0.25, 0.4, -0.6)}}
    if tau < land:
        u = (tau - a) / (land - a)
        z = h * 4 * u * (1 - u)
        stretch = 1 + 0.18 * (1 - smooth(abs(u - 0.15) / 0.4)) if u < 0.6 else 1.0
        return {"body": {"z": z, "squash": stretch, "pitch": -0.1}, "airborne": z,
                "arms": {"l": _arm(m, 1, 0.45, -0.1, 0.8), "r": _arm(m, -1, 0.45, -0.1, 0.8)},
                "wings": {"l": {"flap": 1.4}, "r": {"flap": 1.4}}, "_tuck": tau > l}
    u = (tau - land) / max(dur - land, 1e-3)
    sq = 1 - 0.22 * math.sin(math.pi * clamp(u * 1.4))
    return {"body": {"z": -0.06 * m["height"] * math.sin(math.pi * clamp(u * 1.4)), "squash": sq},
            "arms": {"l": _arm(m, 1, 0.4, -0.2, -0.3), "r": _arm(m, -1, 0.4, -0.2, -0.3)}}


def act_hop(tau, dur, p, tr):
    m = tr.m
    rate = p.get("rate", 2.2)
    u = (tau * rate) % 1.0
    z = 0.12 * m["height"] * 4 * u * (1 - u) * p.get("height", 1.0)
    return {"body": {"z": z, "squash": 1 + 0.12 * (0.5 - abs(u - 0.5)) - (0.1 if u < 0.08 or u > 0.92 else 0)},
            "airborne": z}


def act_nod(tau, dur, p, tr):
    return {"head": {"pitch": 0.28 * abs(math.sin(TAU * p.get("rate", 1.6) * tau))}}


def act_shake(tau, dur, p, tr):
    return {"head": {"yaw": 0.35 * math.sin(TAU * p.get("rate", 2.4) * tau)}}


def act_tilt(tau, dur, p, tr):
    return {"head": {"roll": p.get("amount", 0.28), "pitch": -0.05}}


def act_shrug(tau, dur, p, tr):
    m = tr.m
    up = math.sin(math.pi * clamp(tau / dur))
    return {"arms": {"l": _arm(m, 1, 0.55, -0.35, -0.2 + 0.2 * up), "r": _arm(m, -1, 0.55, -0.35, -0.2 + 0.2 * up)},
            "head": {"roll": 0.15}, "chest": {"pitch": -0.05}}


def act_look_around(tau, dur, p, tr):
    return {"head": {"yaw": 0.75 * math.sin(TAU * tau / max(dur, 0.5) * 1.0), "pitch": -0.08}}


def act_surprise(tau, dur, p, tr):
    m = tr.m
    jolt = math.sin(math.pi * clamp(tau / 0.35))
    return {"body": {"z": 0.06 * m["height"] * jolt, "y": 0.06 * m["height"] * smooth(tau / 0.3), "pitch": -0.18,
                     "squash": 1 + 0.1 * jolt},
            "arms": {"l": _arm(m, 1, 0.35, -0.45, 0.25), "r": _arm(m, -1, 0.35, -0.45, 0.25)},
            "head": {"pitch": -0.12}, "airborne": 0.06 * m["height"] * jolt,
            "wings": {"l": {"flap": 1.2}, "r": {"flap": 1.2}}, "ears": {"l": 0.3, "r": 0.3}}


def act_scared(tau, dur, p, tr):
    m = tr.m
    shake = 0.04 * math.sin(TAU * 9 * tau)
    return {"body": {"z": -0.07 * m["height"], "pitch": 0.25, "roll": shake},
            "arms": {"l": _arm(m, 1, 0.15, -0.55, 0.6), "r": _arm(m, -1, 0.15, -0.55, 0.6)},
            "head": {"pitch": 0.3}, "ears": {"droop": 1.0}, "wings": {"l": {"flap": 0.8}, "r": {"flap": 0.8}},
            "tail": {"lift": -0.5}}


def act_cover_ears(tau, dur, p, tr):
    """Paws pressed over the ears, head ducked, trembling."""
    m = tr.m
    shake = 0.03 * math.sin(TAU * 8 * tau)
    r, a = m["head_r"], m["arm"]
    x = (r * 1.02 - m["shoulder"][0]) / a
    z = (m["head_z"] - m["shoulder"][1] - 0.12 * r) / a
    return {"body": {"z": -0.06 * m["height"], "pitch": 0.2, "roll": shake},
            "arms": {"l": _arm(m, 1, x, 0.05, z), "r": _arm(m, -1, x, 0.05, z)},
            "head": {"pitch": 0.32}, "ears": {"droop": 1.0}, "tail": {"lift": -0.6}}


def act_sad(tau, dur, p, tr):
    m = tr.m
    return {"body": {"pitch": 0.18, "z": -0.02 * m["height"]}, "head": {"pitch": 0.38},
            "arms": {"l": _arm(m, 1, 0.12, 0.05, -0.95), "r": _arm(m, -1, 0.12, 0.05, -0.95)},
            "ears": {"droop": 0.8}, "tail": {"lift": -0.6, "wag": 0.0}, "wings": {"l": {"spread": 0.0},
                                                                                  "r": {"spread": 0.0}}}


def act_cry(tau, dur, p, tr):
    m = tr.m
    sob = abs(math.sin(TAU * 1.8 * tau))
    eye = (m["eye_z"] - m["shoulder"][1]) / m["arm"]
    return {"body": {"pitch": 0.15}, "chest": {"pitch": 0.08 * sob}, "head": {"pitch": 0.3 + 0.06 * sob},
            "arms": {"l": _arm(m, 1, 0.12, -0.45, eye * 0.9), "r": _arm(m, -1, 0.12, -0.45, eye * 0.9)},
            "ears": {"droop": 1.0}}


def act_laugh(tau, dur, p, tr):
    m = tr.m
    b = abs(math.sin(TAU * 3.2 * tau))
    return {"body": {"z": 0.015 * m["height"] * b, "pitch": -0.12, "squash": 1 + 0.04 * b},
            "head": {"pitch": -0.25 + 0.06 * b},
            "arms": {"l": _arm(m, 1, 0.25, -0.35, -0.35), "r": _arm(m, -1, 0.25, -0.35, -0.35)}}


def act_think(tau, dur, p, tr):
    m = tr.m
    chin = (m["head_z"] - m["head_r"] * 0.9 - m["shoulder"][1]) / m["arm"]
    return {"arms": {"r": _arm(m, -1, -0.15, -0.55, chin), "l": _arm(m, 1, 0.1, -0.35, -0.45)},
            "head": {"roll": 0.18, "pitch": -0.1}}


def act_sit(tau, dur, p, tr):
    """Sit on the ground or on a seat of height p['seat'] (meters), knees forward."""
    m = tr.m
    seat = p.get("seat", 0.0)
    drop = (m["hip"] - seat - m["head_r"] * 0.15) * smooth(tau / 0.6) * smooth((dur - tau) / 0.6)
    return {"body": {"z": -drop, "pitch": -0.05}, "sitting": drop / max(m["hip"], 1e-3),
            "arms": {"l": _arm(m, 1, 0.1, -0.5, -0.6), "r": _arm(m, -1, 0.1, -0.5, -0.6)}}


def act_crouch(tau, dur, p, tr):
    m = tr.m
    d = p.get("depth", 0.35)
    return {"body": {"z": -d * m["hip"], "pitch": 0.35}, "head": {"pitch": -0.2},
            "arms": {"l": _arm(m, 1, 0.15, -0.6, -0.55), "r": _arm(m, -1, 0.15, -0.6, -0.55)}}


def act_reach(tau, dur, p, tr):
    side = -1 if p.get("hand", "r") == "r" else 1
    if "at" in p:
        return {"arms": {"r" if side < 0 else "l": {"world": tuple(p["at"])}}, "body": {"pitch": 0.12}}
    return {"arms": {"r" if side < 0 else "l": _arm(tr.m, side, 0.1, -0.9, 0.05)}, "body": {"pitch": 0.1}}


def act_offer(tau, dur, p, tr):
    m = tr.m
    h = p.get("height", 0.0)
    return {"arms": {"l": _arm(m, 1, 0.05, -0.85, h), "r": _arm(m, -1, 0.05, -0.85, h)}, "body": {"pitch": 0.08},
            "head": {"pitch": 0.1}}


def act_hold(tau, dur, p, tr):
    m = tr.m
    h = p.get("height", -0.35)
    return {"arms": {"l": _arm(m, 1, 0.02, -0.55, h), "r": _arm(m, -1, 0.02, -0.55, h)}}


def act_hug(tau, dur, p, tr):
    m = tr.m
    squeeze = 0.05 * math.sin(TAU * 0.8 * tau)
    return {"arms": {"l": _arm(m, 1, -0.05 + squeeze, -0.75, -0.05), "r": _arm(m, -1, -0.05 + squeeze, -0.75, -0.05)},
            "body": {"pitch": 0.12}, "head": {"roll": 0.15, "pitch": 0.1}}


def act_clap(tau, dur, p, tr):
    m = tr.m
    c = 0.5 + 0.5 * math.cos(TAU * 2.6 * tau)
    return {"arms": {"l": _arm(m, 1, -0.08 + 0.25 * c, -0.6, -0.05), "r": _arm(m, -1, -0.08 + 0.25 * c, -0.6, -0.05)},
            "_clap": True}


def act_spin(tau, dur, p, tr):
    return {"spin": TAU * p.get("turns", 1) * smoother(tau / dur)}


def act_fall(tau, dur, p, tr):
    """A comic face-plant (belly flop), then lying there."""
    m = tr.m
    u = smooth(tau / min(0.5, dur * 0.4))
    return {"body": {"pitch": 1.45 * u, "z": -(m["hip"] - m["torso_r"] * 0.9) * u}, "head": {"pitch": -0.5 * u},
            "arms": {"l": _arm(m, 1, 0.6, -0.4, 0.3), "r": _arm(m, -1, 0.6, -0.4, 0.3)},
            "wings": {"l": {"spread": 1.2}, "r": {"spread": 1.2}}, "lying": u}


def act_flap(tau, dur, p, tr):
    rate = p.get("rate", 6.0)
    f = 0.9 + 0.9 * math.sin(TAU * rate * tau)
    out = {"wings": {"l": {"flap": f}, "r": {"flap": f}},
           "arms": {"l": _arm(tr.m, 1, 0.7, 0.0, 0.2 + 0.5 * math.sin(TAU * rate * tau)),
                    "r": _arm(tr.m, -1, 0.7, 0.0, 0.2 + 0.5 * math.sin(TAU * rate * tau))},
           "body": {"z": 0.01 * tr.m["height"] * abs(math.sin(TAU * rate * tau))}}
    if p.get("lift"):
        z = p["lift"] * tr.m["height"] * math.sin(math.pi * clamp(tau / dur))
        out["body"]["z"] += z
        out["airborne"] = z
    return out


def act_dizzy(tau, dur, p, tr):
    a = TAU * 1.2 * tau
    return {"head": {"roll": 0.2 * math.sin(a), "pitch": 0.15 * math.cos(a)}, "body": {"roll": 0.08 * math.sin(a)}}


def act_bow(tau, dur, p, tr):
    return {"body": {"pitch": 0.5 * math.sin(math.pi * clamp(tau / dur))}, "head": {"pitch": 0.2}}


def act_shiver(tau, dur, p, tr):
    m = tr.m
    s = 0.03 * math.sin(TAU * 11 * tau)
    return {"body": {"roll": s}, "arms": {"l": _arm(m, 1, -0.1, -0.5, -0.15), "r": _arm(m, -1, -0.1, -0.5, -0.15)},
            "head": {"pitch": 0.15}}


def act_sniff(tau, dur, p, tr):
    return {"head": {"pitch": 0.25 + 0.05 * math.sin(TAU * 4 * tau), "yaw": 0.1 * math.sin(TAU * 0.7 * tau)},
            "body": {"pitch": 0.15}}


def act_eat(tau, dur, p, tr):
    chew = 0.5 + 0.5 * math.sin(TAU * 3 * tau)
    m = tr.m
    mouth = (m["head_z"] - m["head_r"] * 0.6 - m["shoulder"][1]) / m["arm"]
    return {"head": {"pitch": 0.08 * chew}, "_mouth": "a" if chew > 0.6 else "smile",
            "arms": {"r": _arm(m, -1, -0.1, -0.55, mouth), "l": _arm(m, 1, 0.05, -0.5, -0.3)}}


def act_pat(tau, dur, p, tr):
    side = -1 if p.get("hand", "r") == "r" else 1
    out = {"body": {"pitch": 0.1}}
    if "at" in p:
        x, y, z = p["at"]
        out["arms"] = {"r" if side < 0 else "l": {"world": (x, y, z + 0.05 * abs(math.sin(TAU * 1.5 * tau)))}}
    return out


def act_hand_on_heart(tau, dur, p, tr):
    m = tr.m
    return {"arms": {"l": _arm(m, 1, -0.25, -0.45, -0.18), "r": _arm(m, -1, -0.05, -0.45, -0.2)},
            "head": {"pitch": 0.08, "roll": 0.1}}


def act_wipe_tears(tau, dur, p, tr):
    m = tr.m
    eye = (m["eye_z"] - m["shoulder"][1]) / m["arm"]
    s = 0.12 * math.sin(TAU * 1.5 * tau)
    return {"arms": {"r": _arm(m, -1, 0.05 + s, -0.5, eye * 0.95)}, "head": {"pitch": 0.15}}


def act_beckon(tau, dur, p, tr):
    m = tr.m
    s = 0.15 * math.sin(TAU * 2.0 * tau)
    out = {"arms": {"r": _arm(m, -1, 0.25, -0.6 + s, 0.2)}}
    if tr.plan != "biped":
        out["wings"] = {"r": {"flap": 1.0 + 0.4 * math.sin(TAU * 2 * tau)}}
    return out


def act_carry(tau, dur, p, tr):
    m = tr.m
    return {"arms": {"l": _arm(m, 1, 0.15, -0.15, 1.0), "r": _arm(m, -1, 0.15, -0.15, 1.0)}}


def act_stretch(tau, dur, p, tr):
    m = tr.m
    u = math.sin(math.pi * clamp(tau / dur))
    return {"arms": {"l": _arm(m, 1, 0.2, 0.0, 1.0 * u), "r": _arm(m, -1, 0.2, 0.0, 1.0 * u)},
            "body": {"squash": 1 + 0.08 * u, "pitch": -0.15 * u}, "head": {"pitch": -0.3 * u}}


def act_dive(tau, dur, p, tr):
    u = smooth(tau / min(dur, 0.4))
    return {"body": {"pitch": 1.5 * u}, "head": {"pitch": -0.4 * u},
            "arms": {"l": _arm(tr.m, 1, 0.2, 0.2, 0.95), "r": _arm(tr.m, -1, 0.2, 0.2, 0.95)},
            "wings": {"l": {"spread": 0.1, "flap": 1.6}, "r": {"spread": 0.1, "flap": 1.6}}}


def act_swim(tau, dur, p, tr):
    """Underwater flight: body level, flippers beating like wings."""
    rate = p.get("rate", 1.6)
    f = 0.6 + 0.7 * math.sin(TAU * rate * tau)
    return {"body": {"pitch": 1.35, "roll": 0.1 * math.sin(TAU * rate * 0.5 * tau)}, "head": {"pitch": -0.9},
            "wings": {"l": {"flap": f, "sweep": 0.6}, "r": {"flap": f, "sweep": 0.6}}, "_swim": True}


def act_tread(tau, dur, p, tr):
    """Hovering in water: body half-tilted, flippers sculling, a slow bob."""
    k = math.sin(TAU * 1.1 * tau)
    out = {"body": {"pitch": p.get("pitch", 0.55), "z": 0.03 * tr.m["height"] * math.sin(TAU * 0.45 * tau)},
           "wings": {"l": {"flap": 0.45 + 0.4 * k, "spread": 0.5}, "r": {"flap": 0.45 - 0.4 * k, "spread": 0.5}},
           "head": {"pitch": -0.35}}
    if tr.plan == "biped":
        m = tr.m
        out["arms"] = {"l": _arm(m, 1, 0.6, -0.1 + 0.2 * k, -0.2), "r": _arm(m, -1, 0.6, -0.1 - 0.2 * k, -0.2)}
    return out


def act_float(tau, dur, p, tr):
    z = p.get("height", 0.15) * tr.m["height"] * (0.6 + 0.4 * math.sin(TAU * 0.5 * tau))
    return {"body": {"z": z}, "airborne": z}


def act_peek(tau, dur, p, tr):
    side = 1 if p.get("side", "l") == "l" else -1
    return {"body": {"roll": 0.25 * side, "x": 0.12 * side * tr.m["height"]}, "head": {"roll": 0.2 * side}}


def act_knead(tau, dur, p, tr):
    """Hands together at table height, pinching and folding (making dumplings, kneading dough)."""
    m = tr.m
    k = math.sin(TAU * 1.3 * tau)
    h = p.get("height", -0.45)
    return {"arms": {"l": _arm(m, 1, -0.02 + 0.04 * k, -0.7, h + 0.04 * abs(k)),
                     "r": _arm(m, -1, -0.02 - 0.04 * k, -0.7, h + 0.04 * abs(math.cos(TAU * 1.3 * tau)))},
            "head": {"pitch": 0.32}, "body": {"pitch": 0.12}}


def act_shield(tau, dur, p, tr):
    """Arms flung wide to protect someone behind, chin up."""
    m = tr.m
    tremble = 0.02 * math.sin(TAU * 7 * tau)
    out = {"arms": {"l": _arm(m, 1, 0.95, -0.1, 0.25 + tremble), "r": _arm(m, -1, 0.95, -0.1, 0.25 - tremble)},
           "body": {"pitch": -0.06}, "head": {"pitch": -0.12}}
    if tr.plan != "biped":
        out["wings"] = {"l": {"flap": 1.2}, "r": {"flap": 1.2}}
    return out


def act_struggle(tau, dur, p, tr):
    """Thrashing to break free (a bird caught in a net)."""
    f = math.sin(TAU * 4.5 * tau)
    return {"wings": {"l": {"flap": 0.9 + 0.8 * f, "fold": 0.0}, "r": {"flap": 0.9 - 0.8 * f, "fold": 0.0}},
            "body": {"roll": 0.2 * f, "pitch": 0.3 * math.sin(TAU * 2.1 * tau)},
            "head": {"yaw": 0.4 * math.sin(TAU * 3 * tau)}}


def act_limp(tau, dur, p, tr):
    """Lying still, eyes closed: exhausted or unconscious."""
    return {"body": {"pitch": p.get("pitch", 0.4), "roll": 0.5, "z": -0.05 * tr.m["height"]},
            "head": {"pitch": 0.4, "roll": 0.3}, "wings": {"l": {"fold": 1.0, "flap": 0.0}, "r": {"fold": 1.0}},
            "ears": {"droop": 1.0}}


def act_rub_eyes(tau, dur, p, tr):
    m = tr.m
    eye = (m["eye_z"] - m["shoulder"][1]) / m["arm"]
    s = 0.08 * math.sin(TAU * 2.2 * tau)
    return {"arms": {"l": _arm(m, 1, 0.05 + s, -0.5, eye * 0.95), "r": _arm(m, -1, 0.05 - s, -0.5, eye * 0.95)},
            "head": {"pitch": 0.15}}


def act_stomp(tau, dur, p, tr):
    m = tr.m
    u = (tau * 2.5) % 1.0
    side = "l" if int(tau * 2.5) % 2 == 0 else "r"
    return {"legs": {side: {"lift": 0.15 * m["height"] * math.sin(math.pi * u)}},
            "arms": {"l": _arm(m, 1, 0.3, -0.2, -0.5), "r": _arm(m, -1, 0.3, -0.2, -0.5)},
            "body": {"pitch": 0.1}}


def act_wrap(tau, dur, p, tr):
    """Wrap something (a scarf) around another character's neck: both hands meet at a world point."""
    out = {"body": {"pitch": 0.15}, "head": {"pitch": 0.15}}
    if "at" in p:
        x, y, z = p["at"]
        swirl = 0.08 * math.sin(TAU * 1.2 * tau)
        out["arms"] = {"l": {"world": (x + 0.1 + swirl, y, z)}, "r": {"world": (x - 0.1 - swirl, y, z)}}
    return out


def act_lean(tau, dur, p, tr):
    return {"body": {"pitch": p.get("pitch", 0.2), "roll": p.get("roll", 0.0)}}


def act_tremble(tau, dur, p, tr):
    return {"body": {"roll": 0.015 * math.sin(TAU * 13 * tau)}, "head": {"roll": 0.02 * math.sin(TAU * 11 * tau)}}


def act_yawn(tau, dur, p, tr):
    m = tr.m
    u = math.sin(math.pi * clamp(tau / dur))
    return {"head": {"pitch": -0.3 * u}, "_mouth": "o" if u > 0.4 else None,
            "arms": {"l": _arm(m, 1, 0.3, 0.0, 0.8 * u), "r": _arm(m, -1, 0.3, 0.0, 0.8 * u)}}


ACTIONS = {name[4:]: fn for name, fn in globals().items() if name.startswith("act_")}

NOTES = {
    "wave": "wave one hand (hand: l or r)", "wave_both": "wave both hands overhead", "point": "point ahead",
    "cheer": "arms up, bouncing", "jump": "anticipate, leap and land (height)", "hop": "small repeated hops",
    "nod": "nod yes", "shake": "shake head no", "tilt": "tilt the head, curious", "shrug": "shrug",
    "look_around": "look left and right", "surprise": "jolt back in surprise", "scared": "cower and tremble",
    "sad": "slump, head down", "cry": "hands to eyes, sobbing", "laugh": "bounce with laughter",
    "think": "hand to chin", "sit": "sit on the ground or a seat (seat height)", "crouch": "crouch down",
    "reach": "reach a hand to a place or character (at)", "offer": "hold something out with both hands",
    "hold": "hold something at the chest", "hug": "hug", "clap": "clap", "spin": "spin around (turns)",
    "fall": "comic face-plant", "flap": "flap arms or wings (rate, lift)", "dizzy": "head circling, dizzy",
    "bow": "bow", "shiver": "shiver with cold", "sniff": "sniff around", "eat": "eat, chewing",
    "pat": "pat someone (at)", "hand_on_heart": "hand on heart", "wipe_tears": "wipe tears",
    "beckon": "beckon someone closer", "carry": "carry something overhead", "stretch": "stretch and yawn",
    "dive": "dive head first", "swim": "swim: body level, flippers beating", "float": "hover and bob",
    "peek": "peek out sideways (side)", "stomp": "stomp", "wrap": "wrap something around someone's neck (at)",
    "lean": "lean (pitch, roll)", "tremble": "tremble", "yawn": "yawn", "knead": "fold dumplings, knead dough",
    "shield": "fling arms wide to protect someone", "struggle": "thrash to break free", "limp": "lie still, eyes shut",
    "rub_eyes": "rub sleepy eyes", "tread": "tread water", "cover_ears": "press paws over the ears",
}


# ---------------------------------------------------------------------------- blending
def _blend(base, over, w):
    if w <= 0:
        return base
    for key, value in over.items():
        if key.startswith("_"):
            if w > 0.5:
                base[key] = value
            continue
        if isinstance(value, dict):
            node = base.setdefault(key, {})
            if key in ("arms", "legs", "wings") and isinstance(node, dict):
                for limb, spec in value.items():
                    cur = node.setdefault(limb, {})
                    for k, v in spec.items():
                        if k == "world":
                            if w > 0.02:
                                cur["world"] = v
                                cur["w"] = max(cur.get("w", 0.0), w)
                        elif isinstance(v, tuple) and isinstance(cur.get(k), tuple):
                            cur[k] = tuple(a + (b - a) * w for a, b in zip(cur[k], v))
                        elif isinstance(v, (int, float)) and isinstance(cur.get(k), (int, float)):
                            cur[k] = cur[k] + (v - cur[k]) * w
                        else:
                            cur[k] = v if w > 0.5 or k not in cur else cur[k]
                continue
            _blend(node, value, w)
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            cur = base.get(key, 0.0 if key != "squash" else 1.0)
            base[key] = cur + (value - cur) * w
        elif isinstance(value, tuple):
            cur = base.get(key)
            base[key] = tuple(a + (b - a) * w for a, b in zip(cur, value)) if cur else value
        elif value is not None and w > 0.5:
            base[key] = value
    return base


# ---------------------------------------------------------------------------- tracks
GAITS = {"walk": (1.0, 1.0), "run": (1.55, 1.8), "sneak": (0.7, 0.55), "tiptoe": (0.55, 0.5), "waddle": (0.55, 1.0),
         "hop": (1.4, 1.2), "skip": (1.3, 1.5), "trudge": (0.8, 0.7), "fly": (0.0, 1.0), "swim": (0.0, 1.0),
         "float": (0.0, 1.0), "slide": (0.0, 1.0)}


class Track:
    def __init__(self, cid, spec, metrics, events, ground=None, seed=0):
        self.id, self.spec, self.m = cid, spec, metrics
        self.plan = spec["plan"]
        self.ground = ground or (lambda x, y: 0.0)
        self.seed = seed
        self.events = sorted(events, key=lambda e: (e["t"], e.get("order", 0)))
        self.moves, self.places, self.acts = [], [], []
        self.faces, self.looks, self.says, self.blush, self.vis, self.scales = [], [], [], [], [], []
        self.wear = []
        self.facing_keys = []
        self._build()

    # Events are compiled once into sorted segment lists and facing keyframes.
    def _build(self):
        pos = None
        facing = 0.0
        stride0 = self.m["stride"]
        for e in self.events:
            kind = e["type"]
            t = e["t"]
            if kind == "place":
                pos = tuple(e["at"])
                self.places.append((t, pos))
                if e.get("facing") is not None:
                    facing = e["facing"]
                    self.facing_keys.append((t, facing, 0.0))
            elif kind == "move":
                if pos is None:
                    raise ValueError(f"{self.id}: move at {t:.2f}s before the character is placed")
                pts = [pos] + [tuple(p) for p in e["path"]]
                gait = e.get("gait", "walk" if self.plan == "biped" else "waddle" if self.plan == "penguin" else "hop")
                stride = stride0 * GAITS.get(gait, (1.0, 1.0))[0] or stride0
                length = sum(math.dist(a[:2], b[:2]) for a, b in zip(pts, pts[1:]))
                if "end" in e:
                    end = e["end"]
                else:
                    speed = e.get("speed") or self.default_speed(gait)
                    end = t + max(0.3, length / max(speed, 1e-3))
                mv = Move(t, end, pts, gait, stride, e.get("ease", 0.35), ground=lambda x, y: self.ground(x, y))
                mv.facing = e.get("facing", "path")
                self.moves.append(mv)
                pos = pts[-1]
                self.places.append((end, pos))
                if mv.facing == "path":
                    for i, (a, b) in enumerate(zip(pts, pts[1:])):
                        if math.dist(a[:2], b[:2]) < 1e-4:
                            continue
                        when = mv.time_at(mv.cum[i]) if i else t
                        h = heading_of(b[0] - a[0], b[1] - a[1])
                        self.facing_keys.append((when, h, 0.28))
                        facing = h
                elif isinstance(mv.facing, (int, float)):
                    self.facing_keys.append((t, mv.facing, 0.3))
                    facing = mv.facing
            elif kind == "turn":
                self.facing_keys.append((t, e["angle"], e.get("dur", 0.4)))
                facing = e["angle"]
            elif kind == "act":
                if e["name"] not in ACTIONS:
                    raise ValueError(f"{self.id}: unknown action '{e['name']}'. Actions: {', '.join(sorted(ACTIONS))}")
                dur = e.get("dur", 1.5)
                self.acts.append((t, t + dur, e["name"], e.get("params", {}), e.get("fade", 0.22)))
            elif kind == "face":
                self.faces.append((t, e["expr"]))
            elif kind == "look":
                self.looks.append((t, e.get("at"), e.get("dur", 0.3)))
            elif kind == "say":
                self.says.append((t, t + e["dur"], e))
            elif kind == "blush":
                self.blush.append((t, e["value"]))
            elif kind in ("show", "hide"):
                self.vis.append((t, kind == "show"))
            elif kind == "wear":
                self.wear.append((t, e["item"], bool(e.get("on", True))))
            elif kind == "scale":
                self.scales.append((t, e["value"], e.get("dur", 0.5)))
        self.facing_keys.sort(key=lambda k: k[0])
        if not self.places:
            raise ValueError(f"{self.id}: never placed; add a 'place' or an 'at' in the first shot")

    def default_speed(self, gait):
        base = {"biped": 1.0, "penguin": 0.55, "bird": 0.6}[self.plan] * (self.m["height"] / 1.1) ** 0.5
        return base * GAITS.get(gait, (1.0, 1.0))[1]

    # -------------------------------------------------------------- base state
    def position(self, t):
        for mv in self.moves:
            if mv.start <= t <= mv.end:
                s = mv.progress(t)
                p, _ = mv.point(s)
                return p, mv
        best = None
        for when, p in self.places:
            if when <= t:
                best = p
        return best if best is not None else self.places[0][1], None

    def facing(self, t):
        keys_ = self.facing_keys
        if not keys_:
            return 0.0
        value = keys_[0][1]
        for when, angle, dur in keys_:
            if when > t:
                break
            start = value
            if dur <= 0 or t >= when + dur:
                value = angle
            else:
                u = smooth((t - when) / dur)
                value = start + wrap_angle(angle - start) * u
        return value

    def visible(self, t):
        v = True
        for when, flag in self.vis:
            if when <= t:
                v = flag
        return v

    def scale(self, t):
        value = 1.0
        for when, target, dur in self.scales:
            if when <= t:
                u = smooth((t - when) / max(dur, 1e-3))
                value = value + (target - value) * u
        return value

    def expression(self, t):
        name = "neutral"
        for when, expr in self.faces:
            if when <= t:
                name = expr
        return faces.expression(name)

    def blush_at(self, t):
        value = 0.25
        last = (0.0, 0.25)
        for when, v in self.blush:
            if when <= t:
                value = last[1] + (v - last[1]) * smooth((t - when) / 0.6)
                last = (when, v)
        return value

    def look_target(self, t):
        target, weight = None, 0.0
        for when, at, dur in self.looks:
            if when <= t:
                if at is None:
                    weight = 1 - smooth((t - when) / max(dur, 1e-3))
                else:
                    target, weight = at, smooth((t - when) / max(dur, 1e-3))
        return target, weight

    # -------------------------------------------------------------- gait
    def _gait(self, t, mv, facing, pose):
        m = self.m
        h = m["height"]
        s = mv.progress(t)
        L = mv.stride
        k = min(int(s / L), mv.steps - 1) if mv.steps else 0
        u = clamp((s - k * L) / L) if mv.steps else 0.0
        speed = mv.speed(t)
        gait = mv.gait
        run = gait in ("run", "skip")
        moving = smooth(min(1.0, speed / max(self.default_speed(gait) * 0.3, 1e-3)))
        pose["gait"] = gait
        if gait in ("fly", "swim", "float", "slide"):
            self._travel(t, mv, facing, pose, speed, moving)
            return
        side_moving = "l" if k % 2 == 0 else "r"
        lift = (0.12 if run else 0.07) * h * (0.55 if gait in ("sneak", "tiptoe", "waddle") else 1.0)
        feet = {}
        for label, sign in (("l", 1), ("r", -1)):
            if gait == "hop":
                plant_a = mv.point(k * L)[0]
                plant_b = mv.point((k + 1) * L)[0]
                f = smooth(u)
                p = tuple(a + (b - a) * f for a, b in zip(plant_a, plant_b))
                z = 0.0
            elif label == side_moving:
                prev = max(0, k - 1) * L if k >= 1 else 0.0
                plant_a = mv.point(prev)[0] if k >= 1 else mv.point(0.0)[0]
                plant_b = mv.point((k + 1) * L)[0]
                f = smooth(u)
                p = tuple(a + (b - a) * f for a, b in zip(plant_a, plant_b))
                z = lift * math.sin(math.pi * u)
            else:
                p = mv.point(k * L)[0] if k >= 1 else mv.point(0.0)[0]
                z = 0.0
            feet[label] = (p, z, sign)
        root = mv.point(s)[0]
        cs, sn = math.cos(-facing), math.sin(-facing)
        legs = {}
        for label, (p, z, sign) in feet.items():
            dx, dy = p[0] - root[0], p[1] - root[1]
            lx, ly = dx * cs - dy * sn, dx * sn + dy * cs
            dz = 0.0 if len(root) > 2 else self.ground(*p[:2]) - self.ground(*root[:2])
            legs[label] = {"foot": (sign * m["hip_x"] + lx, ly, z + dz),
                           "pitch": -0.35 * math.sin(math.pi * u) if label == side_moving else 0.0}
        pose["legs"] = legs
        phase = (k + u) * math.pi
        bob = (0.035 if run else 0.018) * h
        if gait == "hop":
            hz = 0.16 * h * 4 * u * (1 - u)
            pose["body"]["z"] += hz
            pose["body"]["squash"] = 1 + 0.12 * math.sin(math.pi * u) - 0.12 * (u < 0.1 or u > 0.9)
            pose["airborne"] = hz
            for label in legs:
                x, y, z = legs[label]["foot"]
                legs[label]["foot"] = (x, y, z + hz)
        else:
            pose["body"]["z"] += bob * abs(math.sin(phase)) * moving - bob * 0.5 * moving
        lean = {"run": 0.22, "skip": 0.15, "sneak": 0.25, "walk": 0.06, "waddle": 0.0, "tiptoe": 0.05,
                "trudge": 0.2}.get(gait, 0.05)
        pose["body"]["pitch"] += lean * moving
        roll = (0.14 if gait == "waddle" else 0.035) * math.sin(phase) * moving
        pose["body"]["roll"] += roll
        pose["chest"]["yaw"] += 0.12 * math.sin(phase) * moving * (0.3 if gait == "waddle" else 1.0)
        swing = (0.55 if run else 0.32) * math.sin(phase) * moving
        bend = 0.35 if run else 0.05
        if self.plan == "biped" and gait != "sneak":
            pose["arms"]["l"]["hand"] = _arm(m, 1, 0.12, -swing, -0.85 + bend)["hand"]
            pose["arms"]["r"]["hand"] = _arm(m, -1, 0.12, swing, -0.85 + bend)["hand"]
        if gait == "sneak":
            pose["arms"]["l"]["hand"] = _arm(m, 1, 0.2, -0.5, -0.1)["hand"]
            pose["arms"]["r"]["hand"] = _arm(m, -1, 0.2, -0.5, -0.1)["hand"]
            pose["body"]["z"] -= 0.06 * h
        if self.plan == "penguin":
            pose["wings"]["l"]["spread"] = 0.35 + 0.1 * math.sin(phase)
            pose["wings"]["r"]["spread"] = 0.35 - 0.1 * math.sin(phase)
        pose["steps"] = (k, u)

    def _travel(self, t, mv, facing, pose, speed, moving):
        """Gliding, flapping, swimming and sliding: the body follows the path's slope."""
        m = self.m
        dt = 0.05
        a, _ = mv.point(mv.progress(t - dt))
        b, _ = mv.point(mv.progress(t + dt))
        rise = (b[2] - a[2]) if len(a) > 2 else 0.0
        run = math.hypot(b[0] - a[0], b[1] - a[1])
        slope = math.atan2(rise, max(run, 1e-4)) if run > 1e-4 or abs(rise) > 1e-4 else 0.0
        if mv.gait == "fly":
            rate = 3.2 if rise > -0.02 else 1.6
            flap = math.sin(TAU * rate * t)
            glide = 1.0 if rise < -0.03 else 0.0
            for k in ("l", "r"):
                pose["wings"][k] = {"flap": (0.55 + 0.75 * flap) * (1 - glide) + 0.45 * glide, "fold": 0.0,
                                    "spread": 1.0}
                pose["legs"][k]["tuck"] = 1.0
            pose["body"]["pitch"] += -0.35 * slope + 0.25 * moving
            pose["body"]["z"] += 0.03 * m["height"] * flap * (1 - glide)
            pose["body"]["roll"] += 0.12 * noise(t * 0.7, self.seed)
        elif mv.gait == "swim":
            rate = 1.4 + min(1.4, speed * 0.6)
            beat = math.sin(TAU * rate * t)
            for k in ("l", "r"):
                pose["wings"][k] = {"flap": 0.55 + 0.75 * beat, "sweep": 0.55, "spread": 0.2}
            pose["body"]["pitch"] += (1.4 - 0.9 * slope) * smooth(moving * 1.5)
            pose["head"]["pitch"] += -0.85 * smooth(moving * 1.5)
            pose["body"]["roll"] += 0.12 * math.sin(TAU * rate * 0.5 * t)
            pose["arms"]["l"]["hand"] = _arm(m, 1, 0.3, 0.6, 0.2 + 0.4 * beat)["hand"]
            pose["arms"]["r"]["hand"] = _arm(m, -1, 0.3, 0.6, 0.2 + 0.4 * beat)["hand"]
            pose["_swim"] = True
        elif mv.gait == "slide":
            pose["body"]["pitch"] += 1.35 * moving
            pose["head"]["pitch"] += -0.8 * moving
            for k in ("l", "r"):
                pose["wings"][k] = {"flap": 0.2, "spread": 0.5}
        else:
            pose["body"]["z"] += 0.04 * m["height"] * math.sin(TAU * 0.5 * t)

    def _settle(self, t, facing, pose):
        """After a walk the trailing foot steps in beside the other one."""
        for mv in self.moves:
            if mv.end <= t < mv.end + 0.3 and mv.steps and mv.gait not in ("fly", "swim", "float", "slide", "hop"):
                u = smooth((t - mv.end) / 0.3)
                trailing = "r" if (mv.steps - 1) % 2 == 0 else "l"
                sign = 1 if trailing == "l" else -1
                back = mv.point(max(0.0, (mv.steps - 1) * mv.stride))[0]
                end = mv.point(mv.length)[0]
                cs, sn = math.cos(-facing), math.sin(-facing)
                dx, dy = back[0] - end[0], back[1] - end[1]
                lx, ly = dx * cs - dy * sn, dx * sn + dy * cs
                rest = pose["legs"][trailing]["foot"]
                start = (sign * self.m["hip_x"] + lx, ly, 0.0)
                pose["legs"][trailing]["foot"] = tuple(a + (b - a) * u for a, b in zip(start, rest[:2] + (0.0,)))
                pose["legs"][trailing]["foot"] = (pose["legs"][trailing]["foot"][0], pose["legs"][trailing]["foot"][1],
                                                  0.05 * self.m["height"] * math.sin(math.pi * u))
                return

    # -------------------------------------------------------------- the pose
    def rest(self):
        m = self.m
        r = {"body": {"x": 0.0, "y": 0.0, "z": 0.0, "pitch": 0.0, "roll": 0.0, "yaw": 0.0, "squash": 1.0},
             "chest": {"pitch": 0.0, "roll": 0.0, "yaw": 0.0}, "head": {"pitch": 0.0, "roll": 0.0, "yaw": 0.0},
             "arms": {}, "legs": {}, "wings": {}, "tail": {"wag": 0.0, "lift": 0.0}, "ears": {"l": 0.0, "r": 0.0}}
        clear = max(0.0, m["torso_r"] * 1.08 - m["shoulder"][0]) + m.get("hand_r", 0.05) * 0.4
        for label, side in (("l", 1), ("r", -1)):
            r["arms"][label] = {"hand": (side * (0.03 + clear), -0.02 - clear * 0.3,
                                         -m["arm"] * (0.86 if clear < 0.1 else 0.7))}
            r["legs"][label] = {"foot": (side * m["hip_x"], 0.0, 0.0), "pitch": 0.0}
            r["wings"][label] = {"flap": 0.0, "spread": 0.2, "fold": 1.0 if self.plan == "bird" else 0.0}
        return r

    def pose(self, t, others=None, camera=None):
        """The full semantic pose at time t. `others` maps ids to head positions for looks."""
        m = self.m
        if not self.visible(t):
            return {"visible": False, "pos": (0, 0, -100), "facing": 0.0}
        p, mv = self.position(t)
        facing = self.facing(t)
        pose = self.rest()
        # Idle life: breathing, a little sway, occasional weight shifts.
        breath = math.sin(TAU * 0.28 * t + self.seed)
        pose["body"]["squash"] = 1 + 0.012 * breath
        pose["chest"]["pitch"] += 0.02 * breath
        pose["head"]["roll"] += 0.03 * noise(t * 0.4, self.seed)
        pose["head"]["yaw"] += 0.05 * noise(t * 0.3, self.seed + 2)
        pose["tail"]["wag"] = 0.35 * math.sin(TAU * 0.6 * t + self.seed)
        pose["ears"]["l"] = 0.05 * noise(t * 0.7, self.seed + 4)
        pose["ears"]["r"] = 0.05 * noise(t * 0.7, self.seed + 5)
        if mv is not None:
            self._gait(t, mv, facing, pose)
        else:
            self._settle(t, facing, pose)
        spin = 0.0
        airborne = pose.get("airborne", 0.0)
        mouth_override = None
        for start, end, name, params, fade in self.acts:
            w = window(t, start, end, fade, fade)
            if w <= 0:
                continue
            part = ACTIONS[name](t - start, end - start, params, self)
            spin += part.pop("spin", 0.0) * w
            airborne = max(airborne, part.pop("airborne", 0.0) * w)
            if part.get("_mouth"):
                mouth_override = part["_mouth"]
            if part.pop("_tuck", False) and self.plan == "bird":
                pose["legs"]["l"]["tuck"] = pose["legs"]["r"]["tuck"] = 1.0
            _blend(pose, part, w)
        z = p[2] if len(p) > 2 else self.ground(p[0], p[1])
        pose["pos"] = (p[0], p[1], z)
        pose["facing"] = facing + spin
        pose["airborne"] = airborne
        pose["scale"] = self.scale(t)
        # Gaze: head turns toward a target, the chest helps, the eyes lead.
        target, weight = self.look_target(t)
        gaze = (0.0, 0.0)
        if target is not None and weight > 0:
            point = None
            if isinstance(target, str):
                if target == "camera" and camera is not None:
                    point = camera
                elif others and target in others:
                    point = others[target]
            else:
                point = tuple(target) + ((m["head_z"],) if len(target) == 2 else ())
            if point is not None:
                hx, hy, hz = p[0], p[1], z + m["head_z"]
                dx, dy, dz = point[0] - hx, point[1] - hy, point[2] - hz
                yaw = wrap_angle(heading_of(dx, dy) - pose["facing"])
                pitch = -math.atan2(dz, math.hypot(dx, dy))
                head_yaw = max(-1.1, min(1.1, yaw)) * 0.75
                chest_yaw = max(-0.5, min(0.5, yaw - head_yaw)) * 0.6
                pose["head"]["yaw"] += head_yaw * weight
                pose["chest"]["yaw"] += chest_yaw * weight
                pose["head"]["pitch"] += max(-0.45, min(0.45, pitch)) * 0.7 * weight
                gaze = (max(-0.06, min(0.06, (yaw - head_yaw - chest_yaw) * 0.08)) * weight,
                        max(-0.04, min(0.04, -pitch * 0.05)) * weight)
        eyes, brows, mouth = self.expression(t)
        if self._blinking(t) and eyes in ("open", "wide", "sad", "angry", "determined", "teary", "sparkle", "soft",
                                          "look_down"):
            eyes = "closed" if self._blinking(t) > 0.5 else "half"
        opening = 0.0
        for start, end, e in self.says:
            if start <= t <= end:
                mouth, opening = self._lipsync(t - start, e, mouth)
        if mouth_override:
            mouth = mouth_override
        pose["face"] = {"eyes": eyes, "brows": brows, "mouth": mouth, "gaze": gaze, "blush": self.blush_at(t),
                        "open": opening}
        pose["visible"] = True
        if self.wear:
            worn = {}
            for when, item, on in self.wear:
                if when <= t:
                    worn[item] = on
                else:
                    worn.setdefault(item, not on)
            pose["wear"] = worn
        pose["wind"] = (0.25 * noise(t * 0.8, self.seed + 9), 0.0)
        if mv is not None:
            v = mv.speed(t)
            pose["wind"] = (pose["wind"][0], min(0.9, v * 0.25))
        return pose

    def _blinking(self, t):
        """Deterministic blinks every few seconds: 0 open, 0..1 how closed."""
        period = 3.1 + 1.3 * math.sin(self.seed * 1.7)
        k = math.floor((t + self.seed) / period)
        offset = (math.sin(k * 12.9898 + self.seed * 78.233) * 43758.5453) % 1.0
        when = (k + 0.2 + 0.6 * offset) * period - self.seed
        d = abs(t - when)
        return clamp(1 - d / 0.07) if d < 0.07 else 0.0

    @staticmethod
    def _lipsync(local, e, rest_mouth):
        """Mouth cell and opening from a take's energy envelope (and vowels when aligned)."""
        env = e.get("energy")
        if not env:
            k = (local * 7.5) % 1.0
            return ("a" if k < 0.45 else "o" if k < 0.7 else "m"), 0.5
        hz = e.get("envelope_hz", 100.0)
        i = int(local * hz)
        if i < 0 or i >= len(env):
            return rest_mouth, 0.0
        level = env[i]
        vowel = None
        for row in e.get("syllables", ()):
            if row["t0"] <= local <= row["t1"]:
                vowel = row.get("vowel")
                break
        if level < 0.12:
            return ("m" if rest_mouth in ("neutral", "m") else rest_mouth), 0.0
        if vowel in ("a", "e", "i", "o", "u"):
            cell = vowel if level > 0.3 or vowel in ("i", "e") else "e"
        else:
            cell = "a" if level > 0.6 else "o" if level > 0.35 else "e"
        return cell, clamp(level)

    # -------------------------------------------------------------- foley
    def footsteps(self):
        """Every foot plant: (time, side, x, y, gait, weight)."""
        out = []
        for mv in self.moves:
            if mv.gait in ("fly", "swim", "float", "slide") or not mv.steps:
                continue
            for k in range(mv.steps):
                t = mv.time_at((k + 1) * mv.stride)
                p = mv.point((k + 1) * mv.stride)[0]
                side = "l" if k % 2 == 0 else "r"
                out.append({"t": round(t, 4), "who": self.id, "side": side, "x": p[0], "y": p[1], "gait": mv.gait,
                            "weight": min(1.0, (self.m["height"] / 1.1) ** 1.5)})
        return out

    def head_position(self, t):
        p, _ = self.position(t)
        z = p[2] if len(p) > 2 else self.ground(p[0], p[1])
        lift = 0.0
        for start, end, name, params, fade in self.acts:
            w = window(t, start, end, fade, fade)
            if w > 0 and name in ("sit", "crouch", "jump", "hop", "cheer", "fall", "float", "flap", "scared",
                                  "cover_ears", "surprise", "bow"):
                part = ACTIONS[name](t - start, end - start, params, self)
                lift += part.get("body", {}).get("z", 0.0) * w
                if name == "bow":
                    lift -= 0.35 * self.m["head_z"] * math.sin(part.get("body", {}).get("pitch", 0.0)) * w
        return (p[0], p[1], z + (self.m["head_z"] + lift) * self.scale(t))
