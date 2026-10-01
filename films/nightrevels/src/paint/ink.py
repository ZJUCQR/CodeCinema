"""
ink.py - drawing primitives for the gongbi look: smooth outlines, ink strokes, pigment fills, washes, fur strokes.

All shapes are built from control points and turned into Catmull-Rom splines, so a character or a prop is authored as a
short list of points. Units are "scroll units" (su); the canvas transform decides the pixel scale.
"""
import math

import numpy as np
import skia

INK = (0.13, 0.10, 0.09)          # warm black ink
INK_SOFT = (0.28, 0.22, 0.19)


# ------------------------------------------------------------------------------------------------ colour helpers
def hexc(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def mix(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def shade(c, k):
    """k < 0 darkens toward ink, k > 0 lightens toward silk white."""
    return mix(c, (0.12, 0.09, 0.08), -k) if k < 0 else mix(c, (0.98, 0.95, 0.88), k)


def c4(c, a=1.0):
    return skia.Color4f(c[0], c[1], c[2], a)


# ------------------------------------------------------------------------------------------------ paths
def _cr_to_bezier(p0, p1, p2, p3, t=0.5):
    k = 1.0 / 6.0
    c1 = (p1[0] + (p2[0] - p0[0]) * k, p1[1] + (p2[1] - p0[1]) * k)
    c2 = (p2[0] - (p3[0] - p1[0]) * k, p2[1] - (p3[1] - p1[1]) * k)
    return c1, c2


def smooth(points, closed=True):
    """Catmull-Rom spline through points -> skia.Path. A point given as ('c', x, y) makes a sharp corner."""
    pts, corners = [], set()
    for i, p in enumerate(points):
        if len(p) == 3:
            corners.add(i)
            p = p[1:]
        pts.append((float(p[0]), float(p[1])))
    n = len(pts)
    path = skia.Path()
    if n < 2:
        return path
    path.moveTo(*pts[0])
    rng = range(n) if closed else range(n - 1)
    for i in rng:
        p1, p2 = pts[i], pts[(i + 1) % n]
        if closed:
            p0, p3 = pts[(i - 1) % n], pts[(i + 2) % n]
        else:
            p0 = pts[i - 1] if i > 0 else p1
            p3 = pts[i + 2] if i + 2 < n else p2
        if i in corners:
            p0 = p1
        if (i + 1) % n in corners:
            p3 = p2
        c1, c2 = _cr_to_bezier(p0, p1, p2, p3)
        path.cubicTo(c1[0], c1[1], c2[0], c2[1], p2[0], p2[1])
    if closed:
        path.close()
    return path


def poly(points, closed=True):
    path = skia.Path()
    path.moveTo(*points[0])
    for p in points[1:]:
        path.lineTo(*p)
    if closed:
        path.close()
    return path


def ellipse(cx, cy, rx, ry):
    path = skia.Path()
    path.addOval(skia.Rect.MakeLTRB(cx - rx, cy - ry, cx + rx, cy + ry))
    return path


# ------------------------------------------------------------------------------------------------ paints
def fill_paint(c, a=1.0):
    return skia.Paint(AntiAlias=True, Color4f=c4(c, a), Style=skia.Paint.kFill_Style)


def ink_paint(w=1.6, c=INK, a=0.92):
    return skia.Paint(AntiAlias=True, Color4f=c4(c, a), Style=skia.Paint.kStroke_Style, StrokeWidth=w,
                      StrokeCap=skia.Paint.kRound_Cap, StrokeJoin=skia.Paint.kRound_Join)


def fill(canvas, path, c, a=1.0):
    canvas.drawPath(path, fill_paint(c, a))


def outline(canvas, path, w=1.6, c=INK, a=0.92):
    canvas.drawPath(path, ink_paint(w, c, a))


def shape(canvas, path, c, w=1.6, a=1.0, line=True, lc=INK):
    """Pigment fill + ink contour (the basic gongbi move)."""
    fill(canvas, path, c, a)
    if line:
        outline(canvas, path, w, lc)


def wash(canvas, clip, path, c, a=0.35, blur=8.0):
    """A soft shading wash (yunran) of colour `c` inside `clip`."""
    canvas.save()
    canvas.clipPath(clip, doAntiAlias=True)
    p = fill_paint(c, a)
    p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
    canvas.drawPath(path, p)
    canvas.restore()


def gradient_fill(canvas, path, p0, p1, c0, c1, a=1.0):
    shader = skia.GradientShader.MakeLinear([skia.Point(*p0), skia.Point(*p1)], [c4(c0, a), c4(c1, a)])
    p = skia.Paint(AntiAlias=True, Shader=shader)
    canvas.drawPath(path, p)


def radial_glow(canvas, cx, cy, r, c, a=0.5):
    shader = skia.GradientShader.MakeRadial(skia.Point(cx, cy), r, [c4(c, a), c4(c, 0.0)])
    canvas.drawCircle(cx, cy, r, skia.Paint(AntiAlias=True, Shader=shader, BlendMode=skia.BlendMode.kScreen))


def stroke_line(canvas, pts, w=1.2, c=INK, a=0.85, closed=False):
    canvas.drawPath(smooth(pts, closed=closed), ink_paint(w, c, a))


def tapered(canvas, pts, w0, w1, c=INK, a=0.9, samples=18):
    """A brush stroke that tapers from width w0 to w1 along a smooth curve (filled polygon)."""
    path = smooth(pts, closed=False)
    meas = skia.PathMeasure(path, False)
    L = meas.getLength()
    if L <= 0:
        return
    left, right = [], []
    for i in range(samples + 1):
        d = L * i / samples
        pos, tan = meas.getPosTan(d)
        w = (w0 + (w1 - w0) * (i / samples)) * 0.5
        nx, ny = -tan.y(), tan.x()
        left.append((pos.x() + nx * w, pos.y() + ny * w))
        right.append((pos.x() - nx * w, pos.y() - ny * w))
    fill(canvas, poly(left + right[::-1]), c, a)


def fur(canvas, clip, strokes, c, a=0.55, w=0.8):
    """Fine hair strokes (si mao): strokes = [(x, y, angle_rad, length)], clipped to `clip` when given."""
    if clip is not None:
        canvas.save()
        canvas.clipPath(clip, doAntiAlias=True)
    p = ink_paint(w, c, a)
    path = skia.Path()
    for x, y, ang, ln in strokes:
        path.moveTo(x, y)
        mx, my = x + math.cos(ang) * ln * 0.5 + math.cos(ang + 1.57) * ln * 0.08, y + math.sin(ang) * ln * 0.5
        path.quadTo(mx, my, x + math.cos(ang) * ln, y + math.sin(ang) * ln)
    canvas.drawPath(path, p)
    if clip is not None:
        canvas.restore()


def edge_fur(path, count, length, seed=0, inward=True, jitter=0.35, start=0.0, end=1.0):
    """Fur strokes along an outline, pointing inward (or outward) with a slight random lean."""
    r = np.random.default_rng(seed)
    meas = skia.PathMeasure(path, True)
    L = meas.getLength()
    out = []
    for i in range(count):
        d = L * (start + (end - start) * (i + r.random() * 0.8) / count)
        pos, tan = meas.getPosTan(d % L)
        ang = math.atan2(tan.y(), tan.x()) + (math.pi / 2 if inward else -math.pi / 2) + r.normal(0, jitter)
        out.append((pos.x(), pos.y(), ang, length * (0.6 + 0.8 * r.random())))
    return out


# ------------------------------------------------------------------------------------------------ transforms
class Xf:
    """canvas.save/translate/rotate/scale as a context manager: with Xf(c, x, y, rot_deg, sx, sy): ..."""

    def __init__(self, canvas, x=0.0, y=0.0, rot=0.0, sx=1.0, sy=None):
        self.c, self.args = canvas, (x, y, rot, sx, sx if sy is None else sy)

    def __enter__(self):
        x, y, rot, sx, sy = self.args
        self.c.save()
        self.c.translate(x, y)
        if rot:
            self.c.rotate(rot)
        if sx != 1.0 or sy != 1.0:
            self.c.scale(sx, sy)
        return self.c

    def __exit__(self, *exc):
        self.c.restore()
