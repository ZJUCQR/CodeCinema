"""Camera direction: shot sizes, angles and moves become a camera position, aim and lens per frame.

A shot names its subjects and a size ("close", "medium", "wide", ...); the
director frames them from the side and angle asked for, keeps the eyes near
the upper third, then applies the move over the shot's duration. Explicit
`from`/`look` coordinates are always allowed for hand-placed shots.
"""
from __future__ import annotations

import math

from codecinema.cartoon.motion import noise, smooth

FRAMING = {"extreme_close": ("head", 2.8), "close": ("head", 4.3), "medium_close": ("body", 0.62),
           "medium": ("body", 0.85), "full": ("body", 1.35), "wide": ("body", 3.4), "extreme_wide": ("body", 10.0)}
LENS = {"extreme_close": 70, "close": 55, "medium_close": 45, "medium": 38, "full": 32, "wide": 28,
        "extreme_wide": 24}
FSTOP = {"extreme_close": 2.0, "close": 2.2, "medium_close": 2.8, "medium": 3.5, "full": 5.0, "wide": 9.0,
         "extreme_wide": 16.0}
ANGLES = {"eye": 2.0, "low": -14.0, "high": 24.0, "bird": 62.0, "worm": -28.0, "slight_high": 10.0}
SIDES = {"front": 0.0, "front_left": 35.0, "front_right": -35.0, "left": 80.0, "right": -80.0, "back": 180.0,
         "back_left": 140.0, "back_right": -140.0, "three_quarter_left": 50.0, "three_quarter_right": -50.0}


def _add(a, b, k=1.0):
    return tuple(x + y * k for x, y in zip(a, b))


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _len(a):
    return math.sqrt(sum(x * x for x in a))


class Director:
    def __init__(self, tracks, marks, aspect=16 / 9, ground=None, solids=()):
        self.tracks = tracks
        self.marks = marks
        self.aspect = aspect
        self.ground = ground or (lambda x, y: 0.0)
        self.solids = list(solids)   # (x, y, radius, top) columns the camera must not sit in or look through

    def _blocked(self, pos, target):
        """How badly solids obstruct the camera: inside one, or crossing the line of sight near the camera."""
        score = 0.0
        px, py, pz = pos
        tx, ty, tz = target
        dx, dy = tx - px, ty - py
        length = math.hypot(dx, dy)
        for x, y, r, top in self.solids + getattr(self, "_others", []):
            if pz > top + 0.3:
                continue
            d = math.hypot(px - x, py - y)
            if d < r + 0.35:
                score += 10.0
                continue
            if length < 1e-6:
                continue
            u = ((x - px) * dx + (y - py) * dy) / (length * length)
            if 0.0 < u < 0.92:
                cx, cy = px + dx * u, py + dy * u
                z_line = pz + (tz - pz) * u
                if math.hypot(cx - x, cy - y) < r + 0.1 and z_line < top:
                    score += 3.0 * (1 - u)
        return score

    def _clear(self, pos, target):
        """Orbit the camera around its subject (and nudge it closer) until the view is unobstructed."""
        if not (self.solids or getattr(self, "_others", None)) or self._blocked(pos, target) == 0:
            return pos
        tx, ty, tz = target
        dx, dy, dz = (a - b for a, b in zip(pos, target))
        base = math.atan2(dy, dx)
        dist = math.hypot(dx, dy)
        best, best_score = pos, self._blocked(pos, target)
        for k in (0.85, 0.7, 1.0, 0.55):
            for step in (0, 12, -12, 24, -24, 38, -38, 55, -55, 75, -75):
                a = base + math.radians(step)
                cand = (tx + math.cos(a) * dist * k, ty + math.sin(a) * dist * k, tz + dz * k)
                score = self._blocked(cand, target) + abs(step) / 200 + (1 - k) * 0.4
                if score < best_score:
                    best, best_score = cand, score
            if best_score < 0.3:
                break
        return best

    # ------------------------------------------------------------------ subjects
    def _subject(self, name, t):
        """(feet, head, height) for a character, or a point for a mark/coordinates."""
        if isinstance(name, str) and name in self.tracks:
            tr = self.tracks[name]
            head = tr.head_position(t)
            p, _ = tr.position(t)
            feet = (p[0], p[1], head[2] - tr.m["head_z"] * tr.scale(t))
            return feet, head, tr.m["height"] * tr.scale(t), tr.m["head_r"] * tr.scale(t), tr.facing(t)
        point = self._point(name)
        return point, point, 1.0, 0.2, 0.0

    def _point(self, value):
        if isinstance(value, str):
            if value in self.marks:
                p = tuple(self.marks[value])
            else:
                raise ValueError(f"Unknown camera target '{value}'")
        else:
            p = tuple(value)
        if len(p) == 2:
            p = (p[0], p[1], self.ground(p[0], p[1]) + 0.6)
        return p

    def _group(self, names, t, samples):
        """Subject points over several times (a static camera must hold the whole action in frame)."""
        feet, heads, heights, radii, facings = [], [], [], [], []
        for n in names:
            f, h, H, r, fa = self._subject(n, max(0.0, t))
            heights.append(H)
            radii.append(r)
            facings.append(fa)
        for s in samples:
            for n in names:
                f, h, H, r, fa = self._subject(n, max(0.0, s))
                feet.append(f)
                heads.append(h)
        return feet, heads, heights, radii, facings, len(samples)

    # ------------------------------------------------------------------ solve
    def solve(self, shot, t):
        cam = shot["camera"]
        u = smooth((t - shot["start"]) / max(shot["end"] - shot["start"], 1e-3))
        if "from" in cam:
            return self._explicit(cam, shot, t, u)
        size = cam.get("size", "medium")
        names = cam.get("on") or []
        if isinstance(names, str):
            names = [names]
        if not names:
            raise ValueError(f"Shot {shot['id']}: the camera needs 'on' subjects or explicit 'from'/'look'")
        follow = cam.get("move") in ("follow", "track") or cam.get("follow", False)
        start, end = shot["start"], shot["end"]
        if follow:
            when, samples = t, [t - 0.4, t - 0.2, t, t + 0.2, t + 0.4]
        elif "frame_at" in cam:
            when = start + float(cam["frame_at"])
            samples = [when]
        else:
            # A locked-off camera frames the whole action and faces the subject's mid-shot direction.
            when = (start + end) / 2
            samples = [start + (end - start) * k / 6 for k in range(7)]
            samples[-1] = end - 1e-3
        feet, heads, heights, radii, facings, k = self._group(names, when, samples)
        # Other characters are obstacles too: the camera must not sit inside a bystander.
        self._others = []
        for cid, tr in self.tracks.items():
            if cid in names or not tr.visible(t):
                continue
            p, _ = tr.position(t)
            ground = p[2] if len(p) > 2 else self.ground(p[0], p[1])
            self._others.append((p[0], p[1], tr.m["torso_r"] * 1.15, ground + tr.m["height"]))
        mode, factor = FRAMING[size]
        H = max(heights)
        if mode == "head":
            frame_h = factor * max(radii)
        else:
            frame_h = factor * H
        xs = [p[0] for p in heads + feet]
        ys = [p[1] for p in heads + feet]
        spread = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
        frame_h = max(frame_h, spread / self.aspect * 1.35)
        if size in ("full", "wide", "extreme_wide") or len(names) > 1:
            top = max(p[2] for p in heads) + max(radii)
            bottom = min(p[2] for p in feet)
            frame_h = max(frame_h, (top - bottom) * 1.25)
        cx = (max(p[0] for p in heads) + min(p[0] for p in heads)) / 2
        cy = (max(p[1] for p in heads) + min(p[1] for p in heads)) / 2
        eye_z = sum(p[2] for p in heads) / len(heads)
        foot_z = sum(p[2] for p in feet) / len(feet)
        if mode == "head":
            target = (cx, cy, eye_z - frame_h * 0.02)
        elif size in ("medium", "medium_close"):
            target = (cx, cy, eye_z - frame_h * 0.22)
        elif size == "full":
            target = (cx, cy, foot_z + frame_h * 0.46)
        else:
            target = (cx, cy, foot_z + frame_h * 0.32)
        lens = float(cam.get("lens", LENS[size]))
        vfov = 2 * math.atan(36.0 / self.aspect / 2 / lens)
        distance = frame_h / 2 / math.tan(vfov / 2)
        facing = facings[0]
        side = cam.get("side", "front")
        if isinstance(side, str) and side.startswith("ots"):
            return self._over_shoulder(cam, names, side, t, u, lens, size)
        az = math.radians(SIDES[side] if isinstance(side, str) else float(side))
        if "bearing" in cam:
            az = 0.0
            facing = math.radians(float(cam["bearing"]))
        elev = math.radians(ANGLES.get(cam.get("angle", "eye"), 2.0) if isinstance(cam.get("angle", "eye"), str)
                            else float(cam["angle"]))
        move = cam.get("move", "static")
        amount = float(cam.get("amount", 1.0))
        if move == "push":
            distance *= 1 - 0.2 * amount * u
        elif move == "pull":
            distance *= 1 - 0.2 * amount * (1 - u)
        elif move in ("orbit_left", "orbit_right"):
            az += math.radians(30 * amount) * (u - 0.5) * (1 if move == "orbit_left" else -1)
        elif move in ("crane_up", "crane_down"):
            elev += math.radians(16 * amount) * (u - 0.5) * (1 if move == "crane_up" else -1)
        heading = facing + az
        forward = (math.sin(heading), -math.cos(heading))
        horiz = distance * math.cos(elev)
        pos = (target[0] + forward[0] * horiz, target[1] + forward[1] * horiz, target[2] + distance * math.sin(elev))
        right = (math.cos(heading), math.sin(heading))
        if move in ("truck_left", "truck_right"):
            shift = frame_h * self.aspect * 0.3 * amount * (u - 0.5) * (1 if move == "truck_right" else -1)
            pos = (pos[0] - right[0] * shift, pos[1] - right[1] * shift, pos[2])
            target = (target[0] - right[0] * shift, target[1] - right[1] * shift, target[2])
        if move in ("pan_left", "pan_right"):
            shift = frame_h * self.aspect * 0.35 * amount * (u - 0.5) * (1 if move == "pan_right" else -1)
            target = (target[0] - right[0] * shift, target[1] - right[1] * shift, target[2])
        if move in ("tilt_up", "tilt_down"):
            target = (target[0], target[1], target[2] + frame_h * 0.4 * amount * (u - 0.5) *
                      (1 if move == "tilt_up" else -1))
        if "offset" in cam:
            o = cam["offset"]
            pos = _add(pos, (o[0], o[1], o[2] if len(o) > 2 else 0.0))
        if not cam.get("exact"):
            pos = self._clear(pos, target)
        floor = self.ground(pos[0], pos[1]) + 0.12
        if pos[2] < floor and not cam.get("below", False):
            pos = (pos[0], pos[1], floor)
        if "lens_to" in cam:
            lens = lens + (float(cam["lens_to"]) - lens) * u
        return self._finish(cam, pos, target, lens, size, t, distance)

    def _over_shoulder(self, cam, names, side, t, u, lens, size):
        over = cam.get("over") or side.split("_", 1)[1]
        f_o, h_o, H_o, r_o, fa_o = self._subject(over, t if cam.get("follow") else cam.get("_t0", t))
        f_a, h_a, H_a, r_a, fa_a = self._subject(names[0], t)
        to_a = _sub(h_a, h_o)
        flat = math.hypot(to_a[0], to_a[1]) or 1.0
        dirx, diry = to_a[0] / flat, to_a[1] / flat
        right = (diry, -dirx)
        sign = -1 if cam.get("shoulder", "right") == "left" else 1
        back = H_o * 0.55 + r_o * 1.5
        pos = (h_o[0] - dirx * back + right[0] * sign * r_o * 1.6,
               h_o[1] - diry * back + right[1] * sign * r_o * 1.6, h_o[2] + r_o * 0.5)
        target = (h_a[0], h_a[1], h_a[2] - r_a * 0.3)
        if cam.get("move") == "push":
            pos = _add(pos, _sub(target, pos), 0.12 * u)
        return self._finish(cam, pos, target, float(cam.get("lens", 45)), size, t, _len(_sub(target, pos)))

    def _explicit(self, cam, shot, t, u):
        a = self._point(cam["from"])
        b = self._point(cam.get("to", cam["from"]))
        pos = tuple(x + (y - x) * u for x, y in zip(a, b))
        look = cam.get("look", "center")
        look_to = cam.get("look_to", look)

        def resolve(v):
            if isinstance(v, str) and v in self.tracks:
                tr = self.tracks[v]
                h = tr.head_position(t)
                return (h[0], h[1], h[2] - tr.m["head_r"] * 0.5)
            return self._point(v)

        la, lb = resolve(look), resolve(look_to)
        target = tuple(x + (y - x) * u for x, y in zip(la, lb))
        lens = float(cam.get("lens", 35))
        if "lens_to" in cam:
            lens += (float(cam["lens_to"]) - lens) * u
        return self._finish(cam, pos, target, lens, cam.get("size", "wide"), t, _len(_sub(target, pos)))

    def _finish(self, cam, pos, target, lens, size, t, distance):
        roll = math.radians(float(cam.get("roll", 0.0)))
        if cam.get("move") == "handheld" or cam.get("handheld"):
            k = float(cam.get("amount", 1.0)) * 0.012
            target = (target[0] + k * distance * noise(t * 0.9, 1.0), target[1] + k * distance * noise(t * 0.8, 2.0),
                      target[2] + k * distance * noise(t * 1.1, 3.0))
            roll += 0.01 * noise(t * 0.7, 4.0)
        for shake in cam.get("shakes", ()):
            start, dur, amp = shake
            if start <= t <= start + dur:
                fall = 1 - (t - start) / dur
                k = amp * 0.02 * fall * distance
                target = (target[0] + k * math.sin(t * 61), target[1] + k * math.sin(t * 53 + 1),
                          target[2] + k * math.sin(t * 47 + 2))
        dof = cam.get("dof", size in ("extreme_close", "close", "medium_close", "medium"))
        return {"pos": pos, "target": target, "lens": lens, "roll": roll,
                "focus": distance, "fstop": float(cam.get("fstop", FSTOP.get(size, 5.6))), "dof": bool(dof)}

