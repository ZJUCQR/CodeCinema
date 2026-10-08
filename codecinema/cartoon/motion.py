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


def window(t, start, end, fade_in=0.25, fade_out=0.3):
    """0 outside [start, end], easing to 1 inside: how strongly an action holds."""
    if t <= start or t >= end:
        return 0.0
    return smooth((t - start) / max(fade_in, 1e-3)) * smooth((end - t) / max(fade_out, 1e-3))


def spring_step(tau, freq, damping):
    """Unit step response of a damped spring: 0 before tau = 0, then rising to 1 (overshooting if damping < 1)."""
    if tau <= 0:
        return 0.0
    w = TAU * freq
    if damping >= 0.999:
        return 1 - (1 + w * tau) * math.exp(-w * tau)
    root = math.sqrt(1 - damping * damping)
    wd = w * root
    return 1 - math.exp(-damping * w * tau) * (math.cos(wd * tau) + damping / root * math.sin(wd * tau))


# How springy each action's entry and exit is (lower: more overshoot), and which actions wind up first.
DAMPING = {name: 0.5 for name in ("wave", "wave_both", "point", "cheer", "clap", "beckon", "bow", "spin", "stomp",
                                  "reach", "offer", "flap", "stretch", "carry", "shrug", "surprise", "shield", "laugh",
                                  "hop", "nod", "shake", "tilt", "look_around", "hug", "pat")}
DAMPING.update({name: 0.65 for name in ("scared", "cover_ears", "dizzy", "think", "hand_on_heart", "peek", "crouch")})
WIND_UP = {"wave", "wave_both", "point", "cheer", "clap", "beckon", "bow", "spin", "stomp", "reach", "offer", "flap",
           "stretch", "carry", "shrug", "dive", "hug", "pat"}
WIND = 0.14
# Big changes of posture take time however briefly they are faded: (seconds in, seconds out).
MIN_FADE = {"fall": (0.12, 0.6), "sit": (0.35, 0.5), "limp": (0.4, 0.6), "crouch": (0.25, 0.35), "dive": (0.15, 0.4),
            "bow": (0.3, 0.35), "hug": (0.3, 0.35), "lean": (0.3, 0.3), "swim": (0.3, 0.4), "tread": (0.3, 0.4)}


def envelope(t, start, end, fade, name=None):
    """How strongly an action holds at t. A spring carries the pose in (lively actions overshoot a little and
    settle), holds it, and springs back out before `end`; actions in WIND_UP first dip the other way."""
    if fade <= 0.02:   # a pose held from a cut: already there when the shot starts, gone at the next cut
        return 1.0 if start <= t < end else 0.0
    damping = DAMPING.get(name, 0.82)
    fade_in, fade_out = (max(fade, f) for f in MIN_FADE.get(name, (0.0, 0.0)))
    off = max(start + fade_in, end - fade_out)
    w = (spring_step(t - start, 0.8 / max(fade_in, 0.08), damping)
         - spring_step(t - off, 0.8 / max(fade_out, 0.08), damping))
    if name in WIND_UP and start - WIND < t < start:
        w -= 0.16 * math.sin(math.pi * (t - start + WIND) / WIND)
    return w


def active(t, start, end):
    """Whether an envelope can be non-zero at t (wind-up before, settling after)."""
    return start - WIND <= t <= end + 1.0


def arc(a, b, w):
    """Blend two limb offsets along an arc around the joint they hang from, not a straight line."""
    la, lb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    if la > 1e-6 and lb > 1e-6:
        dot = clamp(sum(x * y for x, y in zip(a, b)) / (la * lb), -1.0, 1.0)
        ang = math.acos(dot)
        if 1e-3 < ang < 2.9:
            s = math.sin(ang)
            ka, kb = math.sin((1 - w) * ang) / s / la, math.sin(w * ang) / s / lb
            r = la + (lb - la) * w
            return tuple((ka * x + kb * y) * r for x, y in zip(a, b))
    return tuple(x + (y - x) * w for x, y in zip(a, b))


def spring_kernel(freq, damping, step, span=1.0):
    """Weights over past samples (spacing `step`) whose weighted sum is the response of a damped spring
    driven by the signal: the part lags its driver and swings past it when the driver stops."""
    w = TAU * freq
    root = math.sqrt(max(1e-4, 1 - damping * damping))
    n = max(2, min(int(span / step), int(math.ceil(5.0 / (damping * w) / step))))
    raw = [math.exp(-damping * w * k * step) * math.sin(w * root * k * step + 1e-9) for k in range(n)]
    raw[0] *= 0.5
    total = sum(raw)
    weights = [x / total for x in raw]
    delay = sum(x * k * step for k, x in enumerate(weights))
    return weights, delay


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


GRID = 48                                   # dynamics samples per second: two per frame at 24 fps
K_MASS = spring_kernel(2.2, 0.4, 1 / GRID)   # the body's mass against changes of speed
K_HEAD = spring_kernel(2.6, 0.42, 1 / GRID)
K_EARS = spring_kernel(1.9, 0.25, 1 / GRID)
K_TAIL = spring_kernel(1.5, 0.3, 1 / GRID)
K_HANDS = spring_kernel(3.0, 0.5, 1 / GRID)
K_WINGS = spring_kernel(2.6, 0.32, 1 / GRID)
K_SQUASH = spring_kernel(4.0, 0.45, 1 / GRID)
HISTORY = max(len(k[0]) for k in (K_MASS, K_HEAD, K_EARS, K_TAIL, K_HANDS, K_WINGS, K_SQUASH))
# How much a line's mood animates the speaker's head and hands.
TALK_MOODS = {"excited": 1.4, "happy": 1.2, "determined": 1.2, "angry": 1.4, "shout": 1.5, "pleading": 1.3,
              "proud": 1.1, "curious": 1.0, "surprised": 1.2, "neutral": 1.0, "wise": 0.8, "tender": 0.6,
              "sad": 0.5, "scared": 0.7, "sleepy": 0.4, "whisper": 0.4}


def turn_time(angle, base=0.22):
    """Seconds to turn through `angle` radians: big turns take longer."""
    return base + 0.42 * min(abs(angle), math.pi) / math.pi


# ---------------------------------------------------------------------------- paths
def round_corners(points, cut=0.25, passes=6, ground=None):
    """Chaikin corner cutting: a waypoint path becomes a smooth curve with the same two ends, so a character
    sweeps around a corner instead of changing direction in a single frame."""
    pts = [tuple(p) for p in points]
    if len(pts) < 3:
        return pts
    for _ in range(passes):
        out = [pts[0]]
        for i, (a, b) in enumerate(zip(pts, pts[1:])):
            if len(a) != len(b):    # one end on the ground, one at an absolute height: give both a height
                ground = ground or (lambda x, y: 0.0)
                a = a if len(a) > 2 else (a[0], a[1], ground(a[0], a[1]))
                b = b if len(b) > 2 else (b[0], b[1], ground(b[0], b[1]))
            q = tuple(x + (y - x) * cut for x, y in zip(a, b))
            r = tuple(x + (y - x) * (1 - cut) for x, y in zip(a, b))
            if i > 0:
                out.append(q)
            if i < len(pts) - 2:
                out.append(r)
        out.append(pts[-1])
        pts = out
    return pts


class Move:
    """Travel along waypoints between two times with eased speed (no foot sliding: steps follow distance)."""

    def __init__(self, start, end, points, gait, stride, ease=0.35, ground=None, cadence=None):
        self.start, self.end = start, max(end, start + 1e-3)
        self.ground = ground or (lambda x, y: 0.0)
        self.waypoints = [tuple(p) for p in points]
        self.points = round_corners(self.waypoints, ground=self.ground)
        self.until = self.end      # a later move can cut this one short
        self.gait = gait
        seg = [math.dist(a[:2], b[:2]) for a, b in zip(self.points, self.points[1:])]
        self.cum = [0.0]
        for d in seg:
            self.cum.append(self.cum[-1] + d)
        self.length = self.cum[-1]
        steps = max(1, round(self.length / max(stride, 1e-3))) if self.length > 1e-3 else 0
        if steps and cadence:   # never more than `cadence` steps a second: a hurried character takes longer strides
            steps = min(steps, max(1, math.floor(cadence * (self.end - self.start))))
        self.steps = steps
        self.natural = stride
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

    def _headings(self):
        """Direction of each segment of the rounded path, unwrapped so it never jumps by a full turn."""
        hs, prev = [], None
        for a, b in zip(self.points, self.points[1:]):
            if math.hypot(b[0] - a[0], b[1] - a[1]) < 1e-6:
                hs.append(None)
                continue
            h = heading_of(b[0] - a[0], b[1] - a[1])
            prev = h if prev is None else prev + wrap_angle(h - prev)
            hs.append(prev)
        first = next((h for h in hs if h is not None), None)
        out, last = [], first
        for h in hs:            # vertical stretches keep the heading they had
            last = h if h is not None else last
            out.append(last)
        return out if first is not None else None

    def heading(self, s, reach=0.15):
        """Unwrapped direction of travel at distance s, averaged over a short stretch so it turns smoothly
        (None for a vertical path)."""
        if not hasattr(self, "_hs"):
            self._hs = self._headings()
        if not self._hs:
            return None
        total = 0.0
        for d in (-0.5, 0.0, 0.5):
            x = clamp(s + d * reach, 0.0, self.length)
            i = max(0, min(len(self._hs) - 1, bisect.bisect_right(self.cum, x) - 1))
            total += self._hs[i]
        return total / 3

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
    """Anticipate, launch, hang, land and recover in one continuous motion: crouch and squash, release into a
    stretch on a parabola, tuck at the top, squash on landing and settle."""
    m = tr.m
    h = p.get("height", 0.35) * m["height"]
    a, land = 0.18 * dur, 0.78 * dur
    crouch = -0.08 * m["height"]
    if tau < a:
        z = crouch * smooth(tau / a)
    elif tau < land:
        v = (tau - a) / (land - a)
        z = crouch * (1 - smooth(v / 0.12)) + h * 4 * v * (1 - v)
    else:
        z = -0.06 * m["height"] * math.sin(math.pi * clamp((tau - land) / max(dur - land, 1e-3) * 1.4))
    air = (land - a) / dur
    t0, t1 = a / dur, land / dur
    u = tau / dur
    k = clamp(dur / 1.0, 0.4, 1.0)   # a quick hop tilts and squashes less than a big leap
    squash = 1 + k * (keys(u, [(0.0, 1.0), (t0, 0.82), (t0 + 0.12 * air, 1.16), (t0 + 0.5 * air, 1.0), (t1, 1.0),
                              (t1 + 0.08, 0.8), (t1 + 0.2, 1.04), (1.0, 1.0)]) - 1)
    pitch = k * keys(u, [(0.0, 0.0), (t0, 0.16), (t0 + 0.15 * air, -0.1), (t1 - 0.1 * air, 0.0), (t1 + 0.06, 0.14),
                         (1.0, 0.0)])
    back, up, out = (0.25, 0.4, -0.6), (0.45, -0.1, 0.8), (0.5, -0.25, -0.1)
    arm = keys(u, [(0.0, (0.1, 0.0, -0.85)), (t0, back), (t0 + 0.2 * air, up), (t1 - 0.1 * air, up),
                   (t1 + 0.06, out), (1.0, (0.12, -0.05, -0.8))])
    flap = keys(u, [(0.0, 0.2), (t0, 0.0), (t0 + 0.2 * air, 1.5), (t1, 1.2), (t1 + 0.1, 0.6), (1.0, 0.2)])
    return {"body": {"z": z, "squash": squash, "pitch": pitch}, "airborne": max(0.0, z),
            "arms": {"l": _arm(m, 1, *arm), "r": _arm(m, -1, *arm)},
            "wings": {"l": {"flap": flap}, "r": {"flap": flap}}, "_tuck": t0 + 0.3 * air < u < t1}


def act_hop(tau, dur, p, tr):
    m = tr.m
    rate = p.get("rate", 2.2)
    u = (tau * rate) % 1.0
    z = 0.12 * m["height"] * 4 * u * (1 - u) * p.get("height", 1.0)
    contact = math.exp(-(min(u, 1 - u) / 0.07) ** 2)
    return {"body": {"z": z, "squash": 1 + 0.1 * math.sin(math.pi * u) - 0.14 * contact}, "airborne": z}


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
    shake = 0.04 * math.sin(TAU * 5.5 * tau)
    return {"body": {"z": -0.07 * m["height"], "pitch": 0.25, "roll": shake},
            "arms": {"l": _arm(m, 1, 0.15, -0.55, 0.6), "r": _arm(m, -1, 0.15, -0.55, 0.6)},
            "head": {"pitch": 0.3}, "ears": {"droop": 1.0}, "wings": {"l": {"flap": 0.8}, "r": {"flap": 0.8}},
            "tail": {"lift": -0.5}}


def act_cover_ears(tau, dur, p, tr):
    """Paws pressed over the ears, head ducked, trembling."""
    m = tr.m
    shake = 0.03 * math.sin(TAU * 5 * tau)
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
    return {"arms": {"l": _arm(m, 1, 0.08, -0.64, h - 0.2), "r": _arm(m, -1, 0.08, -0.64, h - 0.2)},
            "body": {"pitch": 0.08}, "head": {"pitch": 0.1}}


def act_hold(tau, dur, p, tr):
    m = tr.m
    h = p.get("height", -0.35)
    return {"arms": {"l": _arm(m, 1, 0.04, -0.46, h - 0.05), "r": _arm(m, -1, 0.04, -0.46, h - 0.05)}}


def act_hug(tau, dur, p, tr):
    m = tr.m
    squeeze = 0.05 * math.sin(TAU * 0.8 * tau)
    return {"arms": {"l": _arm(m, 1, -0.05 + squeeze, -0.62, -0.14), "r": _arm(m, -1, -0.05 + squeeze, -0.62, -0.14)},
            "body": {"pitch": 0.12}, "head": {"roll": 0.15, "pitch": 0.1}}


def act_clap(tau, dur, p, tr):
    m = tr.m
    c = 0.5 + 0.5 * math.cos(TAU * 2.6 * tau)
    return {"arms": {"l": _arm(m, 1, -0.06 + 0.22 * c, -0.46, -0.3), "r": _arm(m, -1, -0.06 + 0.22 * c, -0.46, -0.3)},
            "_clap": True}


def act_spin(tau, dur, p, tr):
    """Spin around a whole number of turns (the body ends facing the way it started)."""
    return {"spin": TAU * max(1, round(p.get("turns", 1))) * smoother(tau / dur) if tau < dur else 0.0}


def act_fall(tau, dur, p, tr):
    """A comic face-plant (belly flop), then lying there."""
    m = tr.m
    u = smooth(tau / min(0.5, dur * 0.4))
    return {"body": {"pitch": 1.45 * u, "z": -(m["hip"] - m["torso_r"] * 0.9) * u}, "head": {"pitch": -0.5 * u},
            "arms": {"l": _arm(m, 1, 0.6, -0.4, 0.3), "r": _arm(m, -1, 0.6, -0.4, 0.3)},
            "wings": {"l": {"spread": 1.2}, "r": {"spread": 1.2}}, "lying": u}


def stroke(phase, down=0.4):
    """One wing beat in [-1, 1]: a quick, hard downstroke from the top, then a slower recovery."""
    phase %= 1.0
    if phase < down:
        return 1 - 2 * smooth(phase / down)
    return -1 + 2 * smooth((phase - down) / (1 - down))


def act_flap(tau, dur, p, tr):
    """Flap arms or wings. Beats never go faster than MAX_BEAT (each must last several frames); asking for a
    higher rate makes them wider and harder instead, with the body bouncing on every downstroke."""
    want = p.get("rate", 3.4)
    rate = min(want, MAX_BEAT)
    effort = clamp((want - 2.5) / 6.0)
    amp = 0.85 + 0.45 * effort
    beat_l = stroke(tau * rate)
    beat_r = stroke(tau * rate - 0.04)
    m = tr.m
    out = {"wings": {"l": {"flap": 0.9 + amp * beat_l, "fold": 0.0}, "r": {"flap": 0.9 + amp * beat_r, "fold": 0.0}},
           "arms": {"l": _arm(m, 1, 0.7, 0.0, 0.2 + 0.55 * beat_l), "r": _arm(m, -1, 0.7, 0.0, 0.2 + 0.55 * beat_r)},
           "body": {"z": (0.012 + 0.02 * effort) * m["height"] * (1 - beat_l), "pitch": -0.04 * effort},
           "head": {"pitch": 0.04 * beat_l * effort}}
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
    s = 0.03 * math.sin(TAU * 6 * tau)
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
    f = math.sin(TAU * 3.6 * tau)
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
    return {"body": {"roll": 0.015 * math.sin(TAU * 7 * tau)}, "head": {"roll": 0.02 * math.sin(TAU * 6.3 * tau)}}


def act_yawn(tau, dur, p, tr):
    m = tr.m
    u = math.sin(math.pi * clamp(tau / dur))
    return {"head": {"pitch": -0.3 * u}, "_mouth": "o" if u > 0.4 else None,
            "arms": {"l": _arm(m, 1, 0.3, 0.0, 0.8 * u), "r": _arm(m, -1, 0.3, 0.0, 0.8 * u)}}


ACTIONS = {name[4:]: fn for name, fn in globals().items() if name.startswith("act_")}
MAX_BEAT = 4.5   # Hz: at 24 fps a faster beat strobes instead of reading as motion

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
                            cur[k] = arc(cur[k], v, w) if k == "hand" else tuple(a + (b - a) * w
                                                                                 for a, b in zip(cur[k], v))
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
TRAVEL = ("fly", "swim", "float", "slide")
# Steps per second a gait can take before it turns into a blur (faster moves lengthen the stride instead).
MAX_CADENCE = {"walk": 2.6, "run": 4.2, "sneak": 2.0, "tiptoe": 3.2, "waddle": 4.0, "hop": 2.6, "skip": 3.2,
               "trudge": 1.8}
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
        self._memo = {}
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
                last = self.moves[-1] if self.moves else None
                if last is not None and last.start < t < last.until:
                    # a new move while still moving: cut the old one and set off from where the character is
                    last.until = t
                    pos = last.point(last.progress(t))[0]
                    self.places.append((t, pos))
                    if getattr(last, "end_key", None):
                        last.end_key[0] = t
                        h = last.heading(last.progress(t))
                        last.end_key[1] = facing = last.offset + h if h is not None else last.end_key[1]
                pts = [pos] + [tuple(p) for p in e["path"]]
                gait = e.get("gait", "walk" if self.plan == "biped" else "waddle" if self.plan == "penguin" else "hop")
                stride = stride0 * GAITS.get(gait, (1.0, 1.0))[0] or stride0
                length = sum(math.dist(a[:2], b[:2]) for a, b in zip(pts, pts[1:]))
                if "end" in e:
                    end = e["end"]
                else:
                    speed = e.get("speed") or self.default_speed(gait)
                    end = t + max(0.3, length / max(speed, 1e-3))
                mv = Move(t, end, pts, gait, stride, e.get("ease", 0.35), ground=lambda x, y: self.ground(x, y),
                          cadence=MAX_CADENCE.get(gait, 3.0) * (1.4 if self.plan == "bird" else 1.0))
                mv.facing = e.get("facing", "path")
                self.moves.append(mv)
                pos = pts[-1]
                self.places.append((end, pos))
                if mv.facing == "path":
                    # Turn toward the way out, then face along the curve (see facing()); once there, keep facing the
                    # way the path ends.
                    self.facing_keys.sort(key=lambda k: k[0])
                    before = self._key_facing(t)
                    first = mv.heading(0.0)
                    if first is None:
                        mv.facing = None
                    else:
                        start_value = before + wrap_angle(first - before)
                        mv.turn = turn_time(start_value - before)
                        mv.offset = start_value - first
                        self.facing_keys.append([t, first, mv.turn])
                        mv.end_key = [end, mv.offset + mv.heading(mv.length), 0.0, True]
                        self.facing_keys.append(mv.end_key)
                        facing = mv.end_key[1]
                elif isinstance(mv.facing, (int, float)):
                    self.facing_keys.append([t, mv.facing, 0.3])
                    facing = mv.facing
            elif kind == "turn":
                dur = e["dur"] if e.get("dur") is not None else turn_time(wrap_angle(e["angle"] - facing), 0.3)
                self.facing_keys.append((t, e["angle"], dur))
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
        # Teleports and appearances break the motion's continuity: the dynamics never look across them.
        self.breaks = sorted({e["t"] for e in self.events if e["type"] in ("place", "show", "hide")
                              or (e["type"] == "turn" and e.get("dur") == 0)})
        if not self.places:
            raise ValueError(f"{self.id}: never placed; add a 'place' or an 'at' in the first shot")

    def default_speed(self, gait):
        base = {"biped": 1.0, "penguin": 0.55, "bird": 0.6}[self.plan] * (self.m["height"] / 1.1) ** 0.5
        return base * GAITS.get(gait, (1.0, 1.0))[1]

    # -------------------------------------------------------------- base state
    def position(self, t):
        for mv in self.moves:
            if mv.start <= t < mv.until:   # at the end time the character stands at its destination
                s = mv.progress(t)
                p, _ = mv.point(s)
                return p, mv
        best = None
        for when, p in self.places:
            if when <= t:
                best = p
        return best if best is not None else self.places[0][1], None

    def facing(self, t):
        """Facing angle at t: keyed turns, and along a path the direction of travel on the rounded curve."""
        value = self._key_facing(t)
        for mv in self.moves:
            if mv.start <= t < mv.until and mv.facing == "path":
                along = mv.offset + mv.heading(mv.progress(t))
                value += (along - value) * smoother((t - mv.start) / max(mv.turn, 1e-3))
                break
        return value

    def _key_facing(self, t):
        keys_ = self.facing_keys
        if not keys_:
            return 0.0
        value = keys_[0][1]
        for key in keys_:
            when, angle, dur = key[0], key[1], key[2]
            if when > t:
                break
            # stay continuous: arrive at the target's equivalent nearest the current angle, not the raw value
            # (keys marked absolute hand over an exact accumulated angle, such as the end of a curving path)
            target = angle if len(key) > 3 and key[3] else value + wrap_angle(angle - value)
            if dur <= 0 or t >= when + dur:
                value = target
            else:
                value += (target - value) * smoother((t - when) / dur)
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

    def look_targets(self, t):
        """What the character looks at: (target, weight) pairs. A new look turns smoothly from the previous
        target (it fades out as the new one fades in) instead of snapping back to straight ahead first."""
        state = []
        for i, (when, at, dur) in enumerate(self.looks):
            if when > t:
                break
            # this look's progress when the next one began (or now): earlier weights freeze at that moment
            until = self.looks[i + 1][0] if i + 1 < len(self.looks) and self.looks[i + 1][0] <= t else t
            u = smooth((until - when) / max(dur, 1e-3))
            state = [(tg, w * (1 - u)) for tg, w in state] + ([(at, u)] if at is not None else [])
            state = [(tg, w) for tg, w in state if w > 1e-3][-3:]
        return state

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
        if gait in TRAVEL:
            _blend(pose, self._travel(t, mv, pose, moving), smooth((t - mv.start) / 0.3))
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
            if label == side_moving:
                pitch = -0.35 * math.sin(math.pi * u)
            else:   # the standing foot peels off heel first as the other one swings through
                pitch = 0.4 * smooth((u - 0.55) / 0.45) * (gait not in ("hop", "waddle"))
                z += m["foot"][0] * 0.45 * math.sin(pitch)
            legs[label] = {"foot": (sign * m["hip_x"] + lx, ly, z + dz), "pitch": pitch}
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
        # The body rides over the standing foot: it shifts and rolls toward it (a penguin rocks right over).
        waddle = gait == "waddle"
        over = math.sin(phase) * moving
        pose["body"]["x"] -= (0.035 if waddle else 0.012) * h * over
        roll = -(0.16 if waddle else 0.035) * over
        pose["body"]["roll"] += roll
        pose["head"]["roll"] -= 0.55 * roll
        # Arms swing against the legs, peaking at each foot contact and trailing the legs a little; the
        # shoulders turn with the arms and the hips with the legs.
        contact = math.cos(phase - 0.35) * moving
        pose["body"]["yaw"] += (0.02 if waddle else 0.05) * math.cos(phase) * moving
        pose["chest"]["yaw"] -= (0.05 if waddle else 0.16) * contact
        swing = (0.55 if run else 0.32) * contact
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

    def _travel(self, t, mv, pose, moving):
        """Flying, swimming, floating and sliding as a partial pose, blended in and out at the ends of the move.
        The body follows the path's slope, read over a short stretch so corners in the path don't jerk it."""
        m = self.m
        dt = 0.15
        a, _ = mv.point(mv.progress(t - dt))
        b, _ = mv.point(mv.progress(t + dt))
        rise = (b[2] - a[2]) if len(a) > 2 and len(b) > 2 else 0.0
        run = math.hypot(b[0] - a[0], b[1] - a[1])
        slope = math.atan2(rise, max(run, 1e-4)) if run > 1e-4 or abs(rise) > 1e-4 else 0.0
        local = t - mv.start
        body, head = pose["body"], pose["head"]
        part = {"body": {}, "head": {}, "wings": {}, "legs": {}}
        if mv.gait == "fly":
            # Beat steadily; on the way down hold the wings out and glide.
            flap = stroke(3.0 * local + self.seed)
            glide = smooth(clamp((-slope - 0.1) / 0.25))
            for k in ("l", "r"):
                part["wings"][k] = {"flap": (0.55 + 0.75 * flap) * (1 - glide) + 0.45 * glide, "fold": 0.0,
                                    "spread": 1.0}
                part["legs"][k] = {"tuck": 1.0}
            part["body"] = {"pitch": body["pitch"] - 0.35 * slope + 0.25 * moving,
                            "z": body["z"] + 0.03 * m["height"] * flap * (1 - glide),
                            "roll": body["roll"] + 0.12 * noise(t * 0.7, self.seed)}
        elif mv.gait == "swim":
            # One stroke per stretch of distance (plus a slow beat when barely moving), never above 3.5 a second.
            if not hasattr(mv, "stroke_len"):
                vmax = mv.length / max(mv.end - mv.start - mv.ease, 1e-3)
                mv.stroke_len = max(0.9 * m["height"], vmax / 3.0)
            cycles = mv.progress(t) / mv.stroke_len + 0.5 * local
            beat = stroke(cycles + self.seed, 0.45)
            for k in ("l", "r"):
                part["wings"][k] = {"flap": 0.55 + 0.75 * beat, "sweep": 0.55, "spread": 0.2}
            level = smooth(moving * 1.5)
            part["body"] = {"pitch": body["pitch"] + (1.4 - 0.9 * slope) * level,
                            "roll": body["roll"] + 0.12 * math.sin(math.pi * cycles)}
            part["head"] = {"pitch": head["pitch"] - 0.85 * level}
            part["arms"] = {"l": _arm(m, 1, 0.3, 0.6, 0.2 + 0.4 * beat), "r": _arm(m, -1, 0.3, 0.6, 0.2 + 0.4 * beat)}
            part["_swim"] = True
        elif mv.gait == "slide":
            part["body"] = {"pitch": body["pitch"] + 1.35 * moving}
            part["head"] = {"pitch": head["pitch"] - 0.8 * moving}
            for k in ("l", "r"):
                part["wings"][k] = {"flap": 0.2, "spread": 0.5}
        else:
            part["body"] = {"z": body["z"] + 0.04 * m["height"] * math.sin(TAU * 0.5 * t)}
        return part

    def _settle(self, t, facing, pose):
        """After a walk the trailing foot steps in beside the other one."""
        for mv in self.moves:
            if (mv.end <= t < mv.end + 0.3 and mv.until == mv.end and mv.steps
                    and mv.gait not in ("fly", "swim", "float", "slide", "hop")):
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
            r["legs"][label] = {"foot": (side * m["hip_x"], 0.0, 0.0), "pitch": 0.0, "tuck": 0.0}
            r["wings"][label] = {"flap": 0.0, "spread": 0.2, "fold": 1.0 if self.plan == "bird" else 0.0}
        return r

    def _body(self, t):
        """Root, body, limbs and actions at t: everything before follow-through, face and gaze."""
        if not self.visible(t):
            return None, None
        p, mv = self.position(t)
        facing = self.facing(t)
        pose = self.rest()
        self._idle(t, pose, mv)
        if mv is not None:
            self._gait(t, mv, facing, pose)
        else:
            self._settle(t, facing, pose)
            self._turn_steps(t, pose)
            for done in reversed(self.moves):   # ease out of a flight or swim into standing
                if done.gait in TRAVEL and done.until == done.end and done.end <= t < done.end + 0.45:
                    moving = smooth(min(1.0, done.speed(done.end - 0.08) / max(self.default_speed(done.gait) * 0.3,
                                                                            1e-3)))
                    _blend(pose, self._travel(done.end, done, pose, moving), 1 - smooth((t - done.end) / 0.45))
                    break
        self._talk(t, pose, mv is not None)
        spin = 0.0
        airborne = pose.get("airborne", 0.0)
        for start, end, name, params, fade in self.acts:
            if not active(t, start, end):
                continue
            w = envelope(t, start, end, fade, name)
            if abs(w) < 1e-3:
                continue
            part = ACTIONS[name](max(0.0, t - start), end - start, params, self)
            spin += part.pop("spin", 0.0)   # whole turns: never faded, or the body would unwind backwards
            airborne = max(airborne, part.pop("airborne", 0.0) * w)
            if part.pop("_tuck", False) and self.plan == "bird" and w > 0.5:
                pose["legs"]["l"]["tuck"] = pose["legs"]["r"]["tuck"] = 1.0
            _blend(pose, part, w)
        z = p[2] if len(p) > 2 else self.ground(p[0], p[1])
        pose["pos"] = (p[0], p[1], z)
        pose["facing"] = facing + spin
        pose["airborne"] = airborne
        return pose, mv

    def _span(self, t):
        """Grid steps [first, last] of the continuous stretch of motion around t (between breaks)."""
        i = bisect.bisect_right(self.breaks, t)
        first = math.ceil(self.breaks[i - 1] * GRID) if i > 0 else -(1 << 40)
        last = math.ceil(self.breaks[i] * GRID) - 1 if i < len(self.breaks) else 1 << 40
        return first, last

    def _primary(self, k):
        """The pose before follow-through at grid step k (time k / GRID), cached: the dynamics read the recent
        past, and consecutive frames share almost all of it."""
        hit = self._memo.get(k)
        if hit is None:
            hit = self._body(k / GRID)[0]
            if len(self._memo) > 6000:
                self._memo.clear()
            self._memo[k] = hit
        return hit

    def pose(self, t, others=None, camera=None):
        """The full semantic pose at time t. `others` maps ids to head positions for looks."""
        m = self.m
        pose, mv = self._body(t)
        if pose is None:
            return {"visible": False, "pos": (0, 0, -100), "facing": 0.0}
        self._dynamics(t, pose)
        p, z = pose["pos"], pose["pos"][2]
        # Turning: the eyes lead, the head follows, the chest comes along and the body arrives last.
        i = bisect.bisect_right(self.breaks, t)
        within = (self.breaks[i] - t - 1e-4) if i < len(self.breaks) else 1.0   # never look ahead across a cut
        lead = wrap_angle(self.facing(t + min(0.14, within)) - self.facing(t)) if within > 0.02 else 0.0
        pose["head"]["yaw"] += clamp(lead * 0.7, -0.9, 0.9)
        pose["chest"]["yaw"] += clamp(lead * 0.25, -0.35, 0.35)
        eyes_lead = clamp(wrap_angle(self.facing(t + min(0.26, max(within, 0.0))) - self.facing(t)) * 0.05,
                          -0.05, 0.05)
        pose["scale"] = self.scale(t)
        # Gaze: head turns toward a target, the chest helps, the eyes lead.
        looks = self.look_targets(t)
        fixed = sum(w for _, w in looks)
        gaze = self._saccade(t, 0.3 if fixed > 0.5 else 1.0)
        gaze = (gaze[0] + eyes_lead, gaze[1])
        for target, weight in looks:
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
                weight *= smooth((2.9 - abs(yaw)) / 0.8)   # a target behind the back can't be looked at
                head_yaw = max(-1.1, min(1.1, yaw)) * 0.75
                chest_yaw = max(-0.5, min(0.5, yaw - head_yaw)) * 0.6
                # The eyes get there first, the head a moment later and the chest last.
                eyes_w, head_w, chest_w = (clamp(weight * 2.2), weight, weight * weight)
                pose["head"]["yaw"] += head_yaw * head_w
                pose["chest"]["yaw"] += chest_yaw * chest_w
                pose["head"]["pitch"] += max(-0.45, min(0.45, pitch)) * 0.7 * head_w
                gaze = (gaze[0] + max(-0.06, min(0.06, (yaw - head_yaw * head_w - chest_yaw * chest_w) * 0.08))
                        * eyes_w, gaze[1] + max(-0.04, min(0.04, -pitch * 0.05)) * eyes_w)
        eyes, brows, mouth = self.expression(t)
        blink = self._blinking(t) or (0.8 if abs(lead) > 0.7 else 0.0)
        if blink and eyes in ("open", "wide", "sad", "angry", "determined", "teary", "sparkle", "soft", "look_down"):
            eyes = "closed" if blink > 0.5 else "half"
        opening = 0.0
        for start, end, e in self.says:
            if start <= t <= end:
                mouth, opening = self._lipsync(t - start, e, mouth)
        if pose.get("_mouth"):
            mouth = pose["_mouth"]
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
        sway = pose.pop("_sway", 0.0)
        pose["wind"] = (0.25 * noise(t * 0.8, self.seed + 9) + sway, 0.0)
        if mv is not None:
            pose["wind"] = (pose["wind"][0], min(0.9, mv.speed(t) * 0.25))
        return pose

    # -------------------------------------------------------------- life
    def _idle(self, t, pose, mv):
        """Standing still is never frozen: breathing, small drifts of the head, and the weight moving slowly
        from one foot to the other (the hips shift, the free hip drops, the chest balances it)."""
        breath = math.sin(TAU * 0.28 * t + self.seed)
        pose["body"]["squash"] = 1 + 0.012 * breath
        pose["chest"]["pitch"] += 0.02 * breath
        pose["head"]["roll"] += 0.03 * noise(t * 0.4, self.seed)
        pose["head"]["yaw"] += 0.05 * noise(t * 0.3, self.seed + 2)
        pose["tail"]["wag"] = 0.35 * math.sin(TAU * 0.6 * t + self.seed)
        pose["ears"]["l"] = 0.05 * noise(t * 0.7, self.seed + 4)
        pose["ears"]["r"] = 0.05 * noise(t * 0.7, self.seed + 5)
        if mv is None and self.plan != "bird":
            s = math.sin(TAU * t / (5.5 + 1.5 * math.sin(self.seed)) + self.seed * 3)
            shift = math.copysign(abs(s) ** 0.45, s)
            pose["body"]["x"] += 0.012 * self.m["height"] * shift
            pose["body"]["roll"] -= 0.025 * shift
            pose["chest"]["roll"] += 0.035 * shift
            pose["head"]["roll"] += 0.015 * shift

    def _saccade(self, t, amount=1.0):
        """Eyes are never still: quick small jumps to a new spot every second or so."""
        k = math.floor((t + 0.4 * math.sin(t * 0.7 + self.seed)) / 1.15 + self.seed)
        a = (math.sin(k * 12.9898 + self.seed * 78.233) * 43758.5453) % 1.0
        b = (math.sin(k * 39.3468 + self.seed * 11.135) * 24634.6345) % 1.0
        return ((a * 2 - 1) * 0.018 * amount, (b * 2 - 1) * 0.008 * amount)

    def _talk(self, t, pose, moving):
        """Speaking moves more than the mouth: the head nods on stressed syllables and drifts, the chest leans
        in, and a hand (or flipper) beats with the voice when it is free."""
        for start, end, e in self.says:
            if not start - 0.2 <= t <= end + 0.5:
                continue
            k = TALK_MOODS.get(e.get("mood"), 1.0)
            env, hz = e.get("energy"), e.get("envelope_hz", 100.0)

            def level(s):
                i = int((s - start) * hz)
                return env[i] if env and 0 <= i < len(env) else 0.0
            accent = sum(level(t - 0.05 - j * 0.025) for j in range(6)) / 6
            on = window(t, start - 0.15, end + 0.45, 0.3, 0.45)
            local = t - start
            pose["head"]["pitch"] += (0.08 * accent - 0.015) * k * on
            pose["head"]["yaw"] += 0.06 * k * on * math.sin(TAU * 0.31 * local + self.seed)
            pose["head"]["roll"] += 0.035 * k * on * math.sin(TAU * 0.23 * local + self.seed * 2)
            pose["chest"]["pitch"] += 0.03 * k * on
            if moving:
                continue
            side = "r" if int(start * 3 + self.seed) % 2 == 0 else "l"
            sign = -1 if side == "r" else 1
            if self.plan == "biped":
                lift = (0.15 + 0.3 * accent) * k
                target = _arm(self.m, sign, 0.3, -0.5, -0.6 + lift)["hand"]
                pose["arms"][side]["hand"] = arc(pose["arms"][side]["hand"], target, on * min(0.85, 0.35 + 0.3 * k))
            else:
                pose["wings"][side]["flap"] += (0.15 + 0.45 * accent) * k * on

    def _turn_steps(self, t, pose):
        """Turning on the spot is done with small steps, not by swiveling on planted feet."""
        rate = (self.facing(t + 0.03) - self.facing(t - 0.03)) / 0.06
        if abs(rate) < 0.4 or self.plan == "bird":
            return
        phase = self.facing(t) / (math.pi / 3)
        k = math.floor(phase)
        u = phase - k
        side = "l" if k % 2 == 0 else "r"
        lift = 0.06 * self.m["height"] * math.sin(math.pi * u) * smooth((abs(rate) - 0.4) / 1.5)
        x, y, z = pose["legs"][side]["foot"]
        pose["legs"][side]["foot"] = (x, y, z + lift)
        pose["body"]["z"] -= 0.15 * lift

    def _dynamics(self, t, pose):
        """Follow-through and overlap from the recent motion: parts that hang off the body (head, ears, tail,
        hands, flippers, scarves) lag behind it and swing past when it stops; the upper body leans against
        changes of speed; the body squashes when it lands and stretches when it moves fast."""
        m = self.m
        h = m["height"]
        first, last = self._span(t)
        n0 = min(max(round(t * GRID), first), last)
        now = self._primary(n0)
        if now is None:
            return
        hist = [now]
        for k in range(1, HISTORY + 1):
            q = self._primary(max(n0 - k, first))
            hist.append(q if q is not None else hist[-1])
        f0 = now["facing"]
        cs, sn = math.cos(-f0), math.sin(-f0)
        px, py, _ = now["pos"]

        def local(q):
            """(side, forward) offset of q's root from now, in the current facing frame."""
            dx, dy = q["pos"][0] - px, q["pos"][1] - py
            return dx * cs - dy * sn, -(dx * sn + dy * cs)

        def lag(kernel, get):
            return sum(w * get(hist[k]) for k, w in enumerate(kernel[0]))

        ahead, behind = self._primary(min(n0 + 1, last)), self._primary(max(n0 - 1, first))
        ahead = ahead if ahead is not None else now
        behind = behind if behind is not None else now
        va, vb = local(ahead), local(behind)
        v_side, v_fwd = (va[0] - vb[0]) * GRID / 2, (va[1] - vb[1]) * GRID / 2
        delay = K_MASS[1]
        # Inertia: when the character speeds up the upper body is left behind, when it stops it carries on.
        fwd = lag(K_MASS, lambda q: local(q)[1]) + v_fwd * delay
        side = lag(K_MASS, lambda q: local(q)[0]) + v_side * delay
        # The body leans into a change of speed and banks into turns (as a runner or a bird does); the head
        # stays nearly level while the loose parts below trail behind.
        w2 = (TAU * 2.2) ** 2
        lean_f = clamp(0.55 * math.atan(-fwd * w2 / 9.8), -0.3, 0.3)
        lean_s = clamp(0.55 * math.atan(-side * w2 / 9.8), -0.3, 0.3)
        pose["body"]["pitch"] += 0.4 * lean_f
        pose["chest"]["pitch"] += 0.6 * lean_f
        pose["body"]["roll"] += 0.5 * lean_s
        pose["chest"]["roll"] += 0.5 * lean_s
        pose["head"]["pitch"] -= 0.6 * lean_f
        pose["head"]["roll"] -= 0.6 * lean_s

        def height(q):
            return q["pos"][2] + q["body"]["z"]
        zs = [height(q) for q in (ahead, now, behind)]
        vz = (zs[0] - zs[2]) * GRID / 2
        rise = lag(K_MASS, height) - zs[1] + vz * delay
        # The head is carried by the torso: it lags the torso's rotation and its rise and fall.
        torso_pitch = lambda q: q["body"]["pitch"] + q["chest"]["pitch"]   # noqa: E731
        torso_roll = lambda q: q["body"]["roll"] + q["chest"]["roll"]      # noqa: E731
        pose["head"]["pitch"] += 0.55 * (lag(K_HEAD, torso_pitch) - torso_pitch(now)) - clamp(1.5 * rise / h, -0.2, 0.2)
        pose["head"]["roll"] += 0.55 * (lag(K_HEAD, torso_roll) - torso_roll(now))
        # Squash on impact (upward acceleration), stretch with vertical speed, both through a quick spring so
        # a landing squashes for a few frames and rebounds.
        z = [height(ahead)] + [height(q) for q in hist]
        weights = K_SQUASH[0]
        impact = sum(w * max(0.0, z[k] - 2 * z[k + 1] + z[k + 2]) for k, w in enumerate(weights)) * GRID * GRID
        speed = sum(w * abs(z[k] - z[k + 2]) for k, w in enumerate(weights)) * GRID / 2
        squash = 1 + 0.035 * math.tanh(speed / (1.5 * h)) - 0.12 * math.tanh(impact / (30 * h))
        pose["body"]["squash"] = clamp(pose["body"].get("squash", 1.0) * squash, 0.7, 1.35)
        # Ears flop against the head's rotation and its rise and fall; tails swing out of turns.
        head_pitch = lambda q: torso_pitch(q) + q["head"]["pitch"]   # noqa: E731
        head_roll = lambda q: torso_roll(q) + q["head"]["roll"]      # noqa: E731
        ears = pose["ears"]
        ears["droop"] = ears.get("droop", 0.0) + clamp(1.1 * (lag(K_EARS, head_pitch) - head_pitch(now))
                                                       - 2.5 * rise / h, -0.6, 0.6)
        flop = clamp(1.4 * (lag(K_EARS, head_roll) - head_roll(now)), -0.5, 0.5)
        ears["l"] = ears.get("l", 0.0) + flop
        ears["r"] = ears.get("r", 0.0) - flop
        turn = lag(K_TAIL, lambda q: wrap_angle(q["facing"] - f0))
        tail = pose["tail"]
        tail["wag"] = tail.get("wag", 0.0) + clamp(1.2 * turn + 4.0 * side / h, -1.0, 1.0)
        tail["lift"] = tail.get("lift", 0.0) - clamp(3.0 * rise / h, -0.5, 0.5)
        pose["_sway"] = clamp(0.8 * turn + 3.0 * side / h, -0.8, 0.8)
        # Hands overshoot and settle after every move; flippers and wing tips trail their beat.
        if self.plan == "biped":
            for label in ("l", "r"):
                arm = pose["arms"].get(label, {})
                if arm.get("world") is not None:
                    continue
                cur = now["arms"][label]["hand"]
                lagged = [lag(K_HANDS, lambda q, i=i: q["arms"][label]["hand"][i]) for i in range(3)]
                arm["hand"] = tuple(a + 0.9 * (b - c) for a, b, c in zip(arm["hand"], lagged, cur))
        for label in ("l", "r"):
            wing = pose["wings"].get(label)
            if wing is None:
                continue
            rate = (ahead["wings"][label]["flap"] - behind["wings"][label]["flap"]) * GRID / 2
            wing["curl"] = clamp(-0.018 * rate, -0.8, 0.8)
            wing["flap"] = wing.get("flap", 0.0) - clamp(1.6 * rise / h, -0.4, 0.4)
            wing["spread"] = wing.get("spread", 0.2) + (1 if label == "l" else -1) * clamp(
                0.8 * (lag(K_WINGS, torso_roll) - torso_roll(now)), -0.3, 0.3)

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
                if t > mv.until:
                    break
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
            if name in ("sit", "crouch", "jump", "hop", "cheer", "fall", "float", "flap", "scared", "cover_ears",
                        "surprise", "bow") and active(t, start, end):
                w = envelope(t, start, end, fade, name)
                part = ACTIONS[name](max(0.0, t - start), end - start, params, self)
                lift += part.get("body", {}).get("z", 0.0) * w
                if name == "bow":
                    lift -= 0.35 * self.m["head_z"] * math.sin(part.get("body", {}).get("pitch", 0.0)) * w
        return (p[0], p[1], z + (self.m["head_z"] + lift) * self.scale(t))


def motion_warnings(plan):
    """Moves too fast for their gait: the strides would have to stretch past what the legs can do."""
    out = []
    for cid, info in plan["cast"].items():
        track = Track(cid, info["spec"], info["metrics"], plan["tracks"][cid])
        for mv in track.moves:
            if mv.gait in TRAVEL or not mv.steps or mv.stride <= 1.7 * mv.natural:
                continue
            dur = mv.end - mv.start
            out.append(f"{cid} covers {mv.length:.1f} m in {dur:.1f}s from {mv.start:.1f}s ({mv.length / dur:.1f} m/s), "
                       f"too fast to {mv.gait}: allow more time, shorten the path or change the gait")
    return out
