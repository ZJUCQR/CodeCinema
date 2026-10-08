"""Paint expression atlases for cartoon faces.

Blender projects these images onto a character's head from the front, so a face
is drawn like an anime character sheet: eyes, brows and mouth on separate
layers that switch cells during the film. Every layer is one square atlas of
CELL x CELL pixel cells in a grid; face coordinates run from -1 to 1 across a
cell, with +y pointing up, matching the head's local x and z axes divided by
its projection radius.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

CELL = 512

EYES = ("open", "half", "closed", "happy", "wide", "sad", "angry", "teary", "cry", "sparkle",
        "determined", "sleepy", "dizzy", "wink", "look_down", "soft")
BROWS = ("neutral", "raised", "sad", "angry", "worried", "determined", "skeptical", "soft")
MOUTHS = ("neutral", "smile", "frown", "grin", "laugh", "small_o", "shout", "wavy", "cat", "teeth",
          "pout", "a", "e", "i", "o", "u", "m", "soft_smile", "tremble", "gasp")

# Expressions name a cell on each layer; any cell can also be addressed directly.
EXPRESSIONS = {
    "neutral": ("open", "neutral", "neutral"),
    "calm": ("soft", "soft", "soft_smile"),
    "happy": ("open", "raised", "smile"),
    "joy": ("happy", "raised", "grin"),
    "laugh": ("happy", "raised", "laugh"),
    "excited": ("sparkle", "raised", "grin"),
    "surprised": ("wide", "raised", "small_o"),
    "shocked": ("wide", "raised", "shout"),
    "gasp": ("wide", "worried", "gasp"),
    "sad": ("sad", "sad", "frown"),
    "teary": ("teary", "sad", "tremble"),
    "crying": ("cry", "sad", "wavy"),
    "angry": ("angry", "angry", "teeth"),
    "scared": ("wide", "worried", "wavy"),
    "worried": ("open", "worried", "wavy"),
    "determined": ("determined", "determined", "neutral"),
    "curious": ("open", "skeptical", "small_o"),
    "thinking": ("look_down", "skeptical", "pout"),
    "tender": ("soft", "soft", "soft_smile"),
    "moved": ("teary", "worried", "soft_smile"),
    "shy": ("look_down", "worried", "soft_smile"),
    "sleepy": ("sleepy", "neutral", "neutral"),
    "dizzy": ("dizzy", "worried", "wavy"),
    "proud": ("happy", "raised", "smile"),
    "wink": ("wink", "raised", "grin"),
    "cute": ("happy", "raised", "cat"),
    "pout": ("open", "angry", "pout"),
    "sorry": ("look_down", "sad", "frown"),
}

FACE_DEFAULTS = {
    "style": "anime",          # anime | dot | creature
    "iris": "#5a6ebf", "iris_light": "#9fd0ff", "line": "#2a1c24", "sclera": "#fffdfb",
    "eye_x": 0.38, "eye_y": -0.10, "eye_w": 0.36, "eye_h": 0.46,
    "lashes": False, "highlight": "#ffffff",
    "brow": "#3a2630", "brow_y": 0.30, "brow_w": 0.30, "brow_thick": 0.045,
    "mouth": True, "mouth_y": -0.50, "mouth_w": 0.17, "mouth_color": "#a3364a", "tongue": "#ec7c86",
    "teeth": "#ffffff", "nose": True, "nose_y": -0.33, "skin_line": "#c97f73",
    "blush": "#ff8c95", "blush_x": 0.50, "blush_y": -0.33, "blush_size": 0.17,
    "tear": "#9fe0ff",
}


def _skia():
    import skia
    return skia


def _color(value, alpha=1.0):
    skia = _skia()
    value = value.lstrip("#")
    r, g, b = (int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return skia.Color4f(r, g, b, alpha)


def _mix(a, b, t):
    a, b = a.lstrip("#"), b.lstrip("#")
    out = [round(int(a[i:i + 2], 16) * (1 - t) + int(b[i:i + 2], 16) * t) for i in (0, 2, 4)]
    return "#" + "".join(f"{v:02x}" for v in out)


def _fill(color, alpha=1.0):
    skia = _skia()
    return skia.Paint(AntiAlias=True, Color4f=_color(color, alpha), Style=skia.Paint.kFill_Style)


def _stroke(color, width, alpha=1.0):
    skia = _skia()
    return skia.Paint(AntiAlias=True, Color4f=_color(color, alpha), Style=skia.Paint.kStroke_Style,
                      StrokeWidth=width, StrokeCap=skia.Paint.kRound_Cap, StrokeJoin=skia.Paint.kRound_Join)


def _poly(points, close=False):
    skia = _skia()
    path = skia.Path()
    path.moveTo(*points[0])
    for p in points[1:]:
        path.lineTo(*p)
    if close:
        path.close()
    return path


def _smooth(points, close=False, samples=6):
    """Catmull-Rom through points, flattened so state changes stay simple to express."""
    pts = list(points)
    if close:
        pts = [pts[-1]] + pts + pts[:2]
    else:
        pts = [pts[0]] + pts + [pts[-1]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for k in range(samples):
            t = k / samples
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in (0, 1)))
    if not close:
        out.append(pts[-2])
    return _poly(out, close)


class _Eye:
    """One eye in pixel space; local x points away from the nose, local y points down."""

    def __init__(self, spec, side):
        self.s = spec
        self.side = side
        self.cx = CELL / 2 + side * spec["eye_x"] * CELL / 2
        self.cy = CELL / 2 - spec["eye_y"] * CELL / 2
        self.w = spec["eye_w"] * CELL / 2
        self.h = spec["eye_h"] * CELL / 2

    def p(self, x, y):
        return self.cx + self.side * x * self.w, self.cy + y * self.h

    # Outline of the open eye: anime eyes have a flatter, lash-weighted top; dot and creature eyes are round.
    def top(self, x, drop=0.0, tilt=0.0):
        if self.s["style"] == "anime":
            base = -0.50 + 0.40 * ((x - 0.04) / 0.54) ** 2 * (1.0 if x < 0.04 else 0.72)
        else:
            base = -self.bottom(x)
        low = self.bottom(x) - 0.03
        y = base + drop * (low - base)
        return min(y + tilt * (0.5 - (x + 0.5)) * 0.5, low)

    def bottom(self, x):
        if self.s["style"] == "dot":
            return 0.5 * math.sqrt(max(0.0, 1 - (x / 0.53) ** 2)) ** 0.8
        return 0.50 - 0.58 * (x / 0.54) ** 2

    def outline(self, drop=0.0, tilt=0.0):
        xs = [-0.52 + 1.06 * i / 24 for i in range(25)]
        upper = [self.p(x, self.top(x, drop, tilt)) for x in xs]
        lower = [self.p(x, self.bottom(x)) for x in reversed(xs)]
        return _poly(upper + lower, close=True), upper

    def draw_open(self, canvas, drop=0.0, tilt=0.0, iris_scale=1.0, look=(0.0, 0.0), extra=None):
        skia = _skia()
        s = self.s
        shape, lid = self.outline(drop, tilt)
        canvas.save()
        canvas.clipPath(shape, skia.ClipOp.kIntersect, True)
        if s["style"] == "dot":
            # A glossy dark bead: the clipped outline itself is the eye.
            canvas.drawPath(shape, _fill(s["line"]))
            if iris_scale < 1:
                canvas.drawPath(shape, _stroke(s["sclera"], 0.12 * self.w))
        else:
            canvas.drawPath(shape, _fill(s["sclera"]))
            rx, ry = 0.40 * self.w * iris_scale, 0.47 * self.h * iris_scale
            ix, iy = self.p(look[0], 0.07 + look[1])
            gradient = skia.GradientShader.MakeLinear(
                [skia.Point(ix, iy - ry), skia.Point(ix, iy + ry)],
                [_color(_mix(s["iris"], "#000000", 0.45)), _color(s["iris"]), _color(s["iris_light"])],
                [0.0, 0.55, 1.0])
            canvas.drawOval(skia.Rect.MakeLTRB(ix - rx, iy - ry, ix + rx, iy + ry),
                            skia.Paint(AntiAlias=True, Shader=gradient))
            canvas.drawOval(skia.Rect.MakeLTRB(ix - rx, iy - ry, ix + rx, iy + ry),
                            _stroke(_mix(s["iris"], "#000000", 0.6), max(2.0, 0.05 * self.w)))
            px, py = 0.42 * rx, 0.48 * ry
            canvas.drawOval(skia.Rect.MakeLTRB(ix - px, iy - py - 0.08 * ry, ix + px, iy + py - 0.08 * ry),
                            _fill(_mix(s["iris"], "#000000", 0.75)))
        # A soft lid shadow under the lash line gives the eye depth.
        shade = skia.GradientShader.MakeLinear(
            [skia.Point(0, self.cy - 0.55 * self.h), skia.Point(0, self.cy - 0.05 * self.h)],
            [_color(s["line"], 0.40), _color(s["line"], 0.0)])
        lid_band = _poly(lid + [self.p(0.6, -0.05), self.p(-0.6, -0.05)], close=True)
        if s["style"] != "dot":
            canvas.drawPath(lid_band, skia.Paint(AntiAlias=True, Shader=shade))
        if extra != "no_highlight":
            hx, hy = self.cx - 0.17 * self.w, self.cy - 0.12 * self.h + look[1] * self.h
            hw, hh = 0.15 * self.w * iris_scale, 0.13 * self.h * iris_scale
            if extra == "sparkle":
                self._star(canvas, hx, hy, 2.3 * hw)
                self._star(canvas, self.cx + 0.2 * self.w, self.cy + 0.26 * self.h, 1.2 * hw)
            else:
                canvas.drawOval(skia.Rect.MakeLTRB(hx - hw, hy - hh, hx + hw, hy + hh), _fill(s["highlight"]))
                sx, sy, sr = self.cx + 0.17 * self.w, self.cy + 0.25 * self.h, 0.065 * self.w * iris_scale
                canvas.drawCircle(sx, sy, sr, _fill(s["highlight"], 0.9))
            if extra == "wet":
                canvas.drawOval(skia.Rect.MakeLTRB(self.cx - 0.35 * self.w, self.cy + 0.30 * self.h,
                                                   self.cx + 0.35 * self.w, self.cy + 0.48 * self.h),
                                _fill(s["tear"], 0.55))
                canvas.drawCircle(self.cx + 0.05 * self.w, self.cy - 0.02 * self.h, 0.05 * self.w,
                                  _fill(s["highlight"], 0.9))
        canvas.restore()
        if s["style"] == "dot":
            if drop > 0.1 or tilt:
                canvas.drawPath(_poly(lid), _stroke(s["line"], max(3.0, 0.06 * self.h)))
            return
        canvas.drawPath(_poly(lid), _stroke(s["line"], max(3.0, 0.085 * self.h)))
        # Heavier lash weight toward the outer corner, with a small flick.
        outer = lid[len(lid) // 2:]
        canvas.drawPath(_poly(outer), _stroke(s["line"], max(4.0, 0.13 * self.h)))
        end = lid[-1]
        flick = self.p(0.66, self.top(0.52, drop, tilt) - 0.12)
        canvas.drawPath(_poly([end, flick]), _stroke(s["line"], max(3.0, 0.07 * self.h)))
        if s["lashes"]:
            for x, length in ((0.30, 0.16), (0.44, 0.2)):
                y = self.top(x, drop, tilt)
                a, b = self.p(x, y), self.p(x + 0.14, y - length)
                canvas.drawPath(_poly([a, b]), _stroke(s["line"], max(2.0, 0.045 * self.h)))
        if s["style"] != "dot":
            low = [self.p(x, self.bottom(x) + 0.02) for x in (0.12, 0.28, 0.42)]
            canvas.drawPath(_poly(low), _stroke(s["line"], max(2.0, 0.035 * self.h), 0.8))

    def _star(self, canvas, x, y, r):
        pts = []
        for i in range(8):
            a = math.pi * i / 4
            rr = r if i % 2 == 0 else r * 0.32
            pts.append((x + rr * math.sin(a), y - rr * math.cos(a)))
        canvas.drawPath(_smooth(pts, close=True, samples=3), _fill(self.s["highlight"]))

    def draw_arc(self, canvas, up, weight=1.0, lashes=True):
        """Closed eye: a lash line curving down (sleeping) or up (a happy ^ squint)."""
        s = self.s
        if up:
            pts = [self.p(-0.48, 0.12), self.p(-0.25, -0.16), self.p(0.02, -0.26), self.p(0.30, -0.16),
                   self.p(0.52, 0.10)]
        else:
            pts = [self.p(-0.50, 0.02), self.p(-0.25, 0.20), self.p(0.02, 0.26), self.p(0.30, 0.18),
                   self.p(0.54, -0.02)]
        canvas.drawPath(_smooth(pts), _stroke(s["line"], max(4.0, 0.11 * self.h * weight)))
        if lashes and not up:
            for x, length in ((0.3, 0.13), (0.48, 0.15)):
                y = 0.2 - 0.6 * (x / 0.54) ** 2 * 0.4
                a = self.p(x, y)
                b = self.p(x + 0.08, y + length)
                canvas.drawPath(_poly([a, b]), _stroke(s["line"], max(2.0, 0.045 * self.h)))

    def draw_tears(self, canvas, flowing):
        s = self.s
        x0, y0 = self.p(0.05, 0.42)
        if flowing:
            path = _smooth([(x0, y0), (x0 + self.side * 0.02 * self.w, y0 + 0.5 * self.h),
                            (x0 - self.side * 0.04 * self.w, y0 + 1.1 * self.h)])
            canvas.drawPath(path, _stroke(s["tear"], 0.13 * self.w, 0.85))
            canvas.drawPath(path, _stroke("#ffffff", 0.03 * self.w, 0.7))
        else:
            r = 0.07 * self.w
            canvas.drawPath(_smooth([(x0, y0 + 0.05 * self.h), (x0 + r, y0 + 0.25 * self.h),
                                     (x0, y0 + 0.33 * self.h), (x0 - r, y0 + 0.25 * self.h)], close=True),
                            _fill(s["tear"], 0.9))

    def draw_spiral(self, canvas):
        pts = []
        for i in range(90):
            a = i / 90 * math.tau * 2.6
            r = (0.05 + 0.40 * i / 90)
            pts.append(self.p(r * math.cos(a) * 1.0, r * math.sin(a) * 0.9 + 0.05))
        canvas.drawPath(_poly(pts), _stroke(self.s["line"], max(3.0, 0.06 * self.h)))


def _eyes(canvas, spec, state):
    for side in (-1, 1):
        eye = _Eye(spec, side)
        if state == "open":
            eye.draw_open(canvas)
        elif state == "half":
            eye.draw_open(canvas, drop=0.45)
        elif state == "soft":
            eye.draw_open(canvas, drop=0.22, look=(0.0, 0.05))
        elif state == "closed":
            eye.draw_arc(canvas, up=False)
        elif state == "happy":
            eye.draw_arc(canvas, up=True, weight=1.15)
        elif state == "wide":
            eye.draw_open(canvas, drop=-0.04, iris_scale=0.72)
        elif state == "sad":
            eye.draw_open(canvas, drop=0.25, tilt=-0.35, extra="wet")
        elif state == "angry":
            eye.draw_open(canvas, drop=0.30, tilt=0.55)
        elif state == "determined":
            eye.draw_open(canvas, drop=0.18, tilt=0.35)
        elif state == "teary":
            eye.draw_open(canvas, drop=0.12, tilt=-0.2, extra="wet")
            eye.draw_tears(canvas, flowing=False)
        elif state == "cry":
            eye.draw_arc(canvas, up=False, weight=1.2)
            eye.draw_tears(canvas, flowing=True)
        elif state == "sparkle":
            eye.draw_open(canvas, extra="sparkle")
        elif state == "sleepy":
            eye.draw_open(canvas, drop=0.62, tilt=-0.15)
        elif state == "dizzy":
            eye.draw_spiral(canvas)
        elif state == "wink":
            if side < 0:
                eye.draw_open(canvas)
            else:
                eye.draw_arc(canvas, up=True, weight=1.15)
        elif state == "look_down":
            eye.draw_open(canvas, drop=0.48, look=(0.0, 0.16))
        else:
            raise ValueError(f"Unknown eye state: {state}")


def _brows(canvas, spec, state):
    for side in (-1, 1):
        cx = CELL / 2 + side * spec["eye_x"] * CELL / 2
        base = CELL / 2 - spec["brow_y"] * CELL / 2
        w = spec["brow_w"] * CELL / 2
        inner, outer, arch = 0.0, 0.0, 0.10
        if state == "raised":
            inner, outer, arch = -0.10, -0.08, 0.14
        elif state == "sad":
            inner, outer, arch = -0.12, 0.10, 0.02
        elif state == "angry":
            inner, outer, arch = 0.14, -0.10, -0.02
        elif state == "worried":
            inner, outer, arch = -0.16, 0.06, -0.04
        elif state == "determined":
            inner, outer, arch = 0.09, -0.05, 0.03
        elif state == "skeptical":
            inner, outer, arch = (-0.14, -0.10, 0.16) if side > 0 else (0.04, 0.0, 0.06)
        elif state == "soft":
            inner, outer, arch = -0.05, 0.04, 0.07
        elif state != "neutral":
            raise ValueError(f"Unknown brow state: {state}")
        pts = []
        for i in range(9):
            u = i / 8
            x = -0.45 + 0.95 * u
            y = (inner * (1 - u) + outer * u) - arch * math.sin(math.pi * u)
            pts.append((cx + side * x * w * 1.2, base + y * w * 1.6))
        width = spec["brow_thick"] * CELL / 2
        canvas.drawPath(_smooth(pts), _stroke(spec["brow"], width))


def _mouth(canvas, spec, state):
    skia = _skia()
    cx, cy = CELL / 2, CELL / 2 - spec["mouth_y"] * CELL / 2
    w = spec["mouth_w"] * CELL / 2
    line = _stroke(spec["line"], max(3.0, 0.16 * w))
    if spec["nose"]:
        ny = CELL / 2 - spec["nose_y"] * CELL / 2
        canvas.drawPath(_poly([(cx - 0.12 * w, ny), (cx + 0.10 * w, ny + 0.06 * w)]),
                        _stroke(spec["skin_line"], max(2.0, 0.12 * w)))

    def opening(top, bottom, width, teeth=False, tongue=True):
        pts_top = [(cx - width * w, cy + top[0] * w), (cx, cy + top[1] * w), (cx + width * w, cy + top[0] * w)]
        pts_bottom = [(cx + width * w, cy + top[0] * w), (cx, cy + bottom * w), (cx - width * w, cy + top[0] * w)]
        path = skia.Path()
        path.moveTo(*pts_top[0])
        path.quadTo(pts_top[1][0], pts_top[1][1] - (top[0] - top[1]) * w, *pts_top[2])
        path.quadTo(pts_bottom[1][0], pts_bottom[1][1] + (bottom - top[0]) * w * 0.35, *pts_bottom[2])
        path.close()
        canvas.save()
        canvas.clipPath(path, skia.ClipOp.kIntersect, True)
        canvas.drawPath(path, _fill(spec["mouth_color"]))
        if tongue:
            canvas.drawOval(skia.Rect.MakeLTRB(cx - 0.6 * width * w, cy + (bottom * 0.62) * w,
                                               cx + 0.6 * width * w, cy + (bottom + 0.5) * w), _fill(spec["tongue"]))
        if teeth:
            canvas.drawRect(skia.Rect.MakeLTRB(cx - width * w, cy - 2 * w, cx + width * w,
                                               cy + top[0] * w + 0.22 * w), _fill(spec["teeth"]))
        canvas.restore()
        canvas.drawPath(path, _stroke(spec["line"], max(2.5, 0.11 * w)))

    if state in ("neutral", "m"):
        canvas.drawPath(_smooth([(cx - 0.35 * w, cy), (cx, cy + 0.04 * w), (cx + 0.35 * w, cy)]), line)
    elif state == "smile":
        canvas.drawPath(_smooth([(cx - 0.6 * w, cy - 0.12 * w), (cx, cy + 0.22 * w), (cx + 0.6 * w, cy - 0.12 * w)]),
                        line)
    elif state == "soft_smile":
        canvas.drawPath(_smooth([(cx - 0.42 * w, cy - 0.05 * w), (cx, cy + 0.12 * w), (cx + 0.42 * w, cy - 0.05 * w)]),
                        line)
    elif state == "frown":
        canvas.drawPath(_smooth([(cx - 0.5 * w, cy + 0.14 * w), (cx, cy - 0.12 * w), (cx + 0.5 * w, cy + 0.14 * w)]),
                        line)
    elif state == "tremble":
        pts = [(cx - 0.5 * w + 0.25 * w * i, cy + (0.06 if i % 2 else -0.02) * w + 0.05 * w) for i in range(5)]
        canvas.drawPath(_smooth(pts), line)
    elif state == "wavy":
        pts = [(cx - 0.6 * w + 0.2 * w * i, cy + (0.10 if i % 2 else -0.08) * w) for i in range(7)]
        canvas.drawPath(_poly(pts), line)
    elif state == "cat":
        pts = [(cx - 0.55 * w, cy - 0.1 * w), (cx - 0.28 * w, cy + 0.18 * w), (cx, cy - 0.02 * w),
               (cx + 0.28 * w, cy + 0.18 * w), (cx + 0.55 * w, cy - 0.1 * w)]
        canvas.drawPath(_smooth(pts), line)
    elif state == "pout":
        canvas.drawPath(_smooth([(cx - 0.22 * w, cy + 0.08 * w), (cx, cy - 0.08 * w), (cx + 0.22 * w, cy + 0.08 * w)]),
                        line)
    elif state == "grin":
        opening((-0.10, -0.02), 0.72, 0.62)
    elif state == "laugh":
        opening((-0.12, -0.04), 1.0, 0.72)
    elif state == "shout":
        canvas.drawOval(skia.Rect.MakeLTRB(cx - 0.42 * w, cy - 0.40 * w, cx + 0.42 * w, cy + 0.65 * w),
                        _fill(spec["mouth_color"]))
        canvas.drawOval(skia.Rect.MakeLTRB(cx - 0.28 * w, cy + 0.25 * w, cx + 0.28 * w, cy + 0.62 * w),
                        _fill(spec["tongue"]))
        canvas.drawOval(skia.Rect.MakeLTRB(cx - 0.42 * w, cy - 0.40 * w, cx + 0.42 * w, cy + 0.65 * w),
                        _stroke(spec["line"], max(2.5, 0.11 * w)))
    elif state in ("small_o", "u", "gasp"):
        r = {"small_o": 0.17, "u": 0.14, "gasp": 0.24}[state]
        canvas.drawOval(skia.Rect.MakeLTRB(cx - r * w, cy - r * 1.2 * w, cx + r * w, cy + r * 1.3 * w),
                        _fill(spec["mouth_color"]))
        canvas.drawOval(skia.Rect.MakeLTRB(cx - r * w, cy - r * 1.2 * w, cx + r * w, cy + r * 1.3 * w),
                        _stroke(spec["line"], max(2.5, 0.10 * w)))
    elif state == "o":
        canvas.drawOval(skia.Rect.MakeLTRB(cx - 0.26 * w, cy - 0.30 * w, cx + 0.26 * w, cy + 0.38 * w),
                        _fill(spec["mouth_color"]))
        canvas.drawOval(skia.Rect.MakeLTRB(cx - 0.26 * w, cy - 0.30 * w, cx + 0.26 * w, cy + 0.38 * w),
                        _stroke(spec["line"], max(2.5, 0.10 * w)))
    elif state == "a":
        opening((-0.06, 0.0), 0.62, 0.44)
    elif state == "e":
        opening((-0.04, 0.0), 0.34, 0.52, teeth=True, tongue=False)
    elif state == "i":
        opening((-0.02, 0.02), 0.22, 0.56, teeth=True, tongue=False)
    elif state == "teeth":
        opening((-0.06, -0.06), 0.30, 0.55, teeth=True, tongue=False)
        canvas.drawPath(_poly([(cx - 0.5 * w, cy + 0.06 * w), (cx + 0.5 * w, cy + 0.06 * w)]),
                        _stroke(spec["line"], max(1.5, 0.05 * w), 0.6))
    else:
        raise ValueError(f"Unknown mouth state: {state}")


def _markings(canvas, spec):
    """Fixed patches painted under the features: a penguin's white face, a creature's pale muzzle."""
    skia = _skia()
    for mark in spec.get("markings", []):
        cx, cy = CELL / 2 + mark.get("x", 0) * CELL / 2, CELL / 2 - mark.get("y", 0) * CELL / 2
        w, h = mark.get("w", 0.5) * CELL / 2, mark.get("h", 0.5) * CELL / 2
        paint = _fill(mark["color"])
        if mark.get("kind", "ellipse") == "heart":
            # Two lobes meeting above the beak, as on a cartoon penguin's face.
            path = skia.Path()
            path.moveTo(cx, cy - 0.55 * h)
            path.cubicTo(cx - 0.25 * w, cy - 1.15 * h, cx - 1.05 * w, cy - 0.85 * h, cx - 0.98 * w, cy - 0.05 * h)
            path.cubicTo(cx - 0.92 * w, cy + 0.65 * h, cx - 0.45 * w, cy + 1.0 * h, cx, cy + 1.0 * h)
            path.cubicTo(cx + 0.45 * w, cy + 1.0 * h, cx + 0.92 * w, cy + 0.65 * h, cx + 0.98 * w, cy - 0.05 * h)
            path.cubicTo(cx + 1.05 * w, cy - 0.85 * h, cx + 0.25 * w, cy - 1.15 * h, cx, cy - 0.55 * h)
            path.close()
            canvas.drawPath(path, paint)
        else:
            canvas.drawOval(skia.Rect.MakeLTRB(cx - w, cy - h, cx + w, cy + h), paint)


def _blush(canvas, spec):
    skia = _skia()
    for side in (-1, 1):
        cx = CELL / 2 + side * spec["blush_x"] * CELL / 2
        cy = CELL / 2 - spec["blush_y"] * CELL / 2
        r = spec["blush_size"] * CELL / 2
        shader = skia.GradientShader.MakeRadial(skia.Point(cx, cy), r,
                                                [_color(spec["blush"], 0.75), _color(spec["blush"], 0.0)])
        canvas.save()
        canvas.scale(1.0, 1.0)
        canvas.drawOval(skia.Rect.MakeLTRB(cx - r * 1.25, cy - r * 0.7, cx + r * 1.25, cy + r * 0.7),
                        skia.Paint(AntiAlias=True, Shader=shader))
        canvas.restore()
        for k in range(3):
            x = cx + (k - 1) * r * 0.42
            canvas.drawPath(_poly([(x + 0.12 * r, cy - 0.22 * r), (x - 0.12 * r, cy + 0.22 * r)]),
                            _stroke(_mix(spec["blush"], "#c0303a", 0.35), max(2.0, 0.07 * r), 0.7))


LAYERS = {"eyes": (EYES, _eyes), "brows": (BROWS, _brows), "mouth": (MOUTHS, _mouth)}


def face_spec(face):
    spec = dict(FACE_DEFAULTS)
    spec.update(face or {})
    return spec


def paint(face, folder):
    """Write the atlases for one face; returns {layer: {"file", "grid", "cells"}} and is cached by content."""
    skia = _skia()
    spec = face_spec(face)
    key = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:16]
    folder = Path(folder) / key
    index = folder / "atlas.json"
    if index.is_file():
        return json.loads(index.read_text(encoding="utf-8"))
    folder.mkdir(parents=True, exist_ok=True)
    result = {}
    for layer, (cells, draw) in LAYERS.items():
        if layer == "mouth" and not spec["mouth"]:
            cells = ("neutral",)
            draw = None
        grid = math.ceil(math.sqrt(len(cells)))
        surface = skia.Surface(grid * CELL, grid * CELL)
        canvas = surface.getCanvas()
        canvas.clear(skia.ColorTRANSPARENT)
        for i, cell in enumerate(cells):
            canvas.save()
            canvas.translate((i % grid) * CELL, (i // grid) * CELL)
            canvas.clipRect(skia.Rect.MakeWH(CELL, CELL))
            if draw:
                draw(canvas, spec, cell)
            canvas.restore()
        path = folder / f"{layer}.png"
        surface.makeImageSnapshot().save(str(path), skia.kPNG)
        result[layer] = {"file": str(path), "grid": grid, "cells": list(cells)}
    surface = skia.Surface(CELL, CELL)
    surface.getCanvas().clear(skia.ColorTRANSPARENT)
    _markings(surface.getCanvas(), spec)
    surface.makeImageSnapshot().save(str(folder / "markings.png"), skia.kPNG)
    result["markings"] = {"file": str(folder / "markings.png"), "grid": 1, "cells": ["markings"]}
    surface = skia.Surface(CELL, CELL)
    surface.getCanvas().clear(skia.ColorTRANSPARENT)
    _blush(surface.getCanvas(), spec)
    surface.makeImageSnapshot().save(str(folder / "blush.png"), skia.kPNG)
    result["blush"] = {"file": str(folder / "blush.png"), "grid": 1, "cells": ["blush"]}
    partial = index.with_suffix(".partial.json")
    partial.write_text(json.dumps(result, indent=1), encoding="utf-8")
    partial.replace(index)
    return result


def expression(name):
    """(eyes, brows, mouth) for a named expression or an 'eyes/brows/mouth' triple."""
    if name in EXPRESSIONS:
        return EXPRESSIONS[name]
    parts = name.split("/")
    if len(parts) == 3 and parts[0] in EYES and parts[1] in BROWS and parts[2] in MOUTHS:
        return tuple(parts)
    raise ValueError(f"Unknown expression '{name}'. Use one of: {', '.join(EXPRESSIONS)} or eyes/brows/mouth")


def sheet(face, path, expressions=None):
    """A labelled contact sheet of expressions over a plain skin disc, for documentation and review."""
    skia = _skia()
    spec = face_spec(face)
    names = list(expressions or EXPRESSIONS)
    cols = 6
    size = 256
    surface = skia.Surface(cols * size, math.ceil(len(names) / cols) * (size + 28))
    canvas = surface.getCanvas()
    canvas.clear(_color("#20232b"))
    font = skia.Font(None, 18)
    for i, name in enumerate(names):
        eyes, brows, mouth = expression(name)
        x, y = (i % cols) * size, (i // cols) * (size + 28)
        canvas.save()
        canvas.translate(x, y)
        canvas.drawCircle(size / 2, size / 2, size * 0.47, _fill(face.get("skin", "#f7dcc8")))
        canvas.scale(size / CELL, size / CELL)
        _markings(canvas, spec)
        _blush(canvas, spec)
        _eyes(canvas, spec, eyes)
        _brows(canvas, spec, brows)
        if spec["mouth"]:
            _mouth(canvas, spec, mouth)
        canvas.restore()
        canvas.drawString(name, x + 10, y + size + 20, font, _fill("#e8e8ee"))
    surface.makeImageSnapshot().save(str(path), skia.kPNG)
    return path
