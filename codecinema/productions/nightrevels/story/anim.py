"""
anim.py - keyframe tracks, easing, idle life and the actor model.

    tr = Track(0.0); tr.key(10, 1.0, "inout"); tr(15) -> eased value
    a = Actor("han", char, x, y); a.key("look", 120, -0.8); a.at(frame) -> pose dict for Character.draw
Values may be floats or tuples (interpolated element-wise). Frames are film frames (24 fps).
"""

import math

import numpy as np

FPS = 24.0

EASE = {
    "lin": lambda u: u,
    "in": lambda u: u * u,
    "out": lambda u: 1 - (1 - u) * (1 - u),
    "inout": lambda u: u * u * (3 - 2 * u),
    "step": lambda u: 0.0,
    "back": lambda u: 1 + 2.2 * (u - 1) ** 3 + 1.2 * (u - 1) ** 2,          # slight overshoot
    "snap": lambda u: 1 - (1 - u) ** 4,
}


def _lerp(a, b, u):
    if isinstance(a, tuple):
        return tuple(x + (y - x) * u for x, y in zip(a, b))
    return a + (b - a) * u


class Track:
    def __init__(self, value):
        self.keys = [(-1e9, value, "lin")]

    def key(self, frame, value, ease="inout"):
        self.keys.append((float(frame), value, ease))
        self.keys.sort(key=lambda k: k[0])
        return self

    def hold(self, f0, f1, value, ease="inout", ramp=6):
        """Move to value by f0 (ramping over `ramp` frames), hold it until f1, then return to the previous value."""
        prev = self(f0 - ramp)
        self.key(f0 - ramp, prev, "inout")
        self.key(f0, value, ease)
        self.key(f1, value, "lin")
        self.key(f1 + ramp, prev, "inout")
        return self

    def __call__(self, f):
        ks = self.keys
        if f <= ks[0][0]:
            return ks[0][1]
        for i in range(1, len(ks)):
            if f < ks[i][0]:
                f0, v0, _ = ks[i - 1]
                f1, v1, e = ks[i]
                u = (f - f0) / max(1e-6, f1 - f0)
                return _lerp(v0, v1, EASE[e](min(1.0, max(0.0, u))))
        return ks[-1][1]


def _hash(*a):
    return abs(hash(a)) % (2 ** 32)


class Idle:
    """Procedural life: blinks, ear flicks, breathing, tail sway, whisker twitch. Deterministic per actor."""

    def __init__(self, seed, blink_every=4.2, ear_every=5.5, tail_speed=0.25, breath_rate=0.28, frames=4000):
        r = np.random.default_rng(seed)
        self.blinks = []
        t = r.uniform(0.5, 3.0)
        while t * FPS < frames:
            self.blinks.append(t * FPS)
            t += r.uniform(0.6, 1.6) * blink_every
            if r.random() < 0.15:           # double blink
                self.blinks.append(t * FPS - 5)
        self.ears = []
        t = r.uniform(1, 4)
        while t * FPS < frames:
            self.ears.append((t * FPS, r.choice([-1, 1]), r.uniform(12, 26)))
            t += r.uniform(0.5, 1.8) * ear_every
        self.tail_speed, self.breath_rate = tail_speed * r.uniform(0.8, 1.2), breath_rate * r.uniform(0.85, 1.15)
        self.phase = r.uniform(0, 1)

    def at(self, f):
        t = f / FPS
        blink = 0.0
        for b in self.blinks:
            d = f - b
            if -3 <= d <= 4:
                blink = max(blink, 1.0 - abs(d) / (3.5 if d < 0 else 4.5))
            if b > f + 5:
                break
        ear_l = ear_r = 0.0
        for fe, side, amp in self.ears:
            d = f - fe
            if 0 <= d <= 10:
                v = amp * math.sin(math.pi * d / 10)
                if side < 0:
                    ear_l = v
                else:
                    ear_r = v
            if fe > f + 1:
                break
        return dict(blink=blink, ear_l=ear_l, ear_r=ear_r,
                    breath=math.sin(2 * math.pi * (t * self.breath_rate + self.phase)),
                    tail=t * self.tail_speed + self.phase,
                    whisker=2.5 * math.sin(t * 0.9 + self.phase * 6))


ADDITIVE = {"blink", "ear_l", "ear_r", "whisker", "breath"}
DEFAULTS = {}                      # pose defaults (film.py fills this with cat.POSE0)


class Actor:
    """A character (or prop) placed on the scroll with keyed parameters and idle life."""

    def __init__(self, name, char=None, x=0.0, y=0.0, z=0.0, idle=True, seed=None, draw=None, **base):
        self.name, self.char, self.z = name, char, z
        self.tracks = {"x": Track(float(x)), "y": Track(float(y)), "visible": Track(1.0)}
        self.base = dict(base)
        self.idle = Idle(seed if seed is not None else _hash(name)) if idle else None
        self.draw_fn = draw            # custom draw for props: draw(canvas, actor, frame, values)
        self.hold = None               # hold(canvas, frame, values) for held props
        self.extra = None

    def track(self, name, default=None):
        if name not in self.tracks:
            if default is None:
                default = self.base.get(name, DEFAULTS.get(name, 0.0))
            self.tracks[name] = Track(default)
        return self.tracks[name]

    def key(self, name, frame, value, ease="inout"):
        if name not in self.tracks and isinstance(value, tuple) and not isinstance(
                self.base.get(name, DEFAULTS.get(name)), tuple):
            self.track(name, value)
        tr = self.track(name)
        if len(tr.keys) == 1 and frame > 10 and tr.keys[0][1] != value:
            # the first real key: hold the resting value until just before it (no drift from the distant past)
            tr.key(frame - (1 if ease == "step" else 8), tr.keys[0][1], "lin")
        tr.key(frame, value, ease)
        return self

    def keys(self, name, pairs, ease="inout"):
        for f, v in pairs:
            self.key(name, f, v, ease)
        return self

    def value(self, name, f, default=0.0):
        if name in self.tracks:
            return self.tracks[name](f)
        return self.base.get(name, default)

    def at(self, f):
        """Pose dict for Character.draw (keyed values + idle life)."""
        out = dict(self.base)
        for k, tr in self.tracks.items():
            out[k] = tr(f)
        if self.idle is not None and out.get("idle", 1.0) > 0.5:
            life = self.idle.at(f)
            for k, v in life.items():
                if k in ADDITIVE:
                    if k == "blink":
                        out[k] = max(out.get(k, 0.0), v) if out.get("blink_lock", 0.0) < 0.5 else out.get(k, 0.0)
                    else:
                        out[k] = out.get(k, 0.0) + v
                elif k == "tail":
                    out[k] = out.get("tail_off", 0.0) + v * out.get("tail_speed", 1.0)
        w = out.get("walk", 0.0)
        if w > 0.01:                    # walking bob
            out["body_y"] = out.get("body_y", 0.0) - abs(math.sin(f * 0.42)) * 7 * w
            out["head_rot"] = out.get("head_rot", 0.0) + math.sin(f * 0.42) * 2.0 * w
        return out


class Camera:
    def __init__(self, x, y=500.0, z=1.08):
        self.x, self.y, self.z = Track(x), Track(y), Track(z)

    def key(self, f, x=None, y=None, z=None, ease="inout"):
        """Keys given components; the others hold their current value at f (keys are authored in time order)."""
        for tr, v in ((self.x, x), (self.y, y), (self.z, z)):
            tr.key(f, tr(f) if v is None else v, ease)
        return self

    def at(self, f):
        return self.x(f), self.y(f), self.z(f)


class Events:
    """Timed sound / story events for the audio engine."""

    def __init__(self):
        self.items = []

    def emit(self, frame, kind, **kw):
        self.items.append(dict(frame=float(frame), type=kind, **kw))

    def sorted(self):
        return sorted(self.items, key=lambda e: e["frame"])
