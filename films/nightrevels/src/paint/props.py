"""
props.py - furniture, instruments and small props, drawn in local units with the origin at the base centre.

Lacquer furniture is dark with fine highlights; screens carry procedural ink landscapes; instruments are drawn at an
anchor (a paw) with an angle so the puppets can hold them.
"""
import math

import numpy as np
import skia

from ink import (INK, Xf, ellipse, fill, outline, poly, radial_glow, shade, shape,
                 smooth, stroke_line, tapered, wash)

LACQUER = (0.16, 0.11, 0.09)
LACQUER_HI = (0.36, 0.24, 0.17)
GOLD = (0.82, 0.66, 0.30)
VERMILION = (0.72, 0.18, 0.12)
SILK_PANEL = (0.86, 0.79, 0.62)


def _rect(x0, y0, x1, y1):
    return poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def lacquer_bar(canvas, x0, y0, x1, y1, c=LACQUER):
    p = _rect(x0, y0, x1, y1)
    shape(canvas, p, c, w=1.2)
    if abs(x1 - x0) > abs(y1 - y0):
        stroke_line(canvas, [(x0 + 3, y0 + 2), (x1 - 3, y0 + 2)], 0.8, LACQUER_HI, 0.8)
    else:
        stroke_line(canvas, [(x0 + 2, y0 + 3), (x0 + 2, y1 - 3)], 0.8, LACQUER_HI, 0.8)


# ------------------------------------------------------------------------------------------------ ink landscape
def ink_landscape(canvas, x0, y0, x1, y1, seed=0, kind="mountains"):
    """Procedural ink-wash landscape inside a rectangle (screen panels, bed panels)."""
    rng = np.random.default_rng(seed)
    w, h = x1 - x0, y1 - y0
    canvas.save()
    canvas.clipRect(skia.Rect.MakeLTRB(x0, y0, x1, y1), doAntiAlias=True)
    fill(canvas, _rect(x0, y0, x1, y1), SILK_PANEL)
    if kind == "mountains":
        for layer, (base, amp, alpha) in enumerate(((0.5, 0.3, 0.10), (0.68, 0.26, 0.18), (0.88, 0.2, 0.32))):
            pts = [(x0 - 10, y1 + 10)]
            n = 9
            ph = rng.uniform(0, 6)
            for i in range(n + 1):
                t = i / n
                yy = y0 + h * (base - amp * (0.5 + 0.5 * math.sin(t * 5.3 + ph)) * (0.6 + 0.4 * rng.random()))
                pts.append((x0 + w * t, yy))
            pts.append((x1 + 10, y1 + 10))
            p = smooth(pts)
            p2 = skia.Paint(AntiAlias=True, Color4f=skia.Color4f(0.18, 0.16, 0.14, alpha))
            p2.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 2.5 + layer))
            canvas.drawPath(p, p2)
            stroke_line(canvas, pts[1:-1], 1.0, INK, 0.35 + 0.15 * layer)
            # texture strokes (cun)
            for _ in range(int(w / 12)):
                sx = x0 + rng.uniform(0, w)
                sy = y0 + h * (base + rng.uniform(-0.1, 0.25))
                stroke_line(canvas, [(sx, sy), (sx + rng.uniform(-6, 6), sy + rng.uniform(4, 12))], 0.7, INK, 0.25)
        # a few pines
        for _ in range(3):
            tx, ty = x0 + rng.uniform(0.1, 0.9) * w, y0 + h * rng.uniform(0.6, 0.85)
            stroke_line(canvas, [(tx, ty), (tx + 2, ty - 26)], 1.2, INK, 0.7)
            for k in range(4):
                fill(canvas, ellipse(tx + rng.uniform(-6, 6), ty - 8 - k * 5, 8 - k, 2.5), (0.2, 0.26, 0.2), 0.75)
    elif kind == "waves":
        for i in range(int(h / 10)):
            yy = y0 + i * 10 + 4
            stroke_line(canvas, [(x0 + w * t, yy + math.sin(t * 12 + i) * 3) for t in np.linspace(0, 1, 9)], 0.8,
                        INK, 0.35)
    canvas.restore()


# ------------------------------------------------------------------------------------------------ furniture
def screen(canvas, w=300, h=520, seed=0, kind="mountains"):
    """A large standing screen seen edge-on-ish (frontal panel), base on the ground."""
    fx0, fx1 = -w / 2, w / 2
    top = -h
    # feet
    for fx in (fx0 + 20, fx1 - 20):
        foot = smooth([(fx - 34, 0), (fx - 20, -14), (fx + 20, -14), (fx + 34, 0)])
        shape(canvas, foot, LACQUER, w=1.2)
    lacquer_bar(canvas, fx0, top, fx1, top + 16)
    lacquer_bar(canvas, fx0, -40, fx1, -26)
    lacquer_bar(canvas, fx0, top, fx0 + 14, -14)
    lacquer_bar(canvas, fx1 - 14, top, fx1, -14)
    ink_landscape(canvas, fx0 + 16, top + 18, fx1 - 16, -42, seed, kind)
    outline(canvas, _rect(fx0 + 16, top + 18, fx1 - 16, -42), 1.0)


def couch(canvas, w=420, canopy=True, seed=1, quilt=(0.55, 0.22, 0.18), panels=True):
    """Han's couch-bed (ta) with an optional canopy and painted panels. Seat height 110."""
    seat = -110
    if canopy:
        for px in (-w / 2 + 8, w / 2 - 8):
            lacquer_bar(canvas, px - 6, -560, px + 6, seat)
        lacquer_bar(canvas, -w / 2, -572, w / 2, -556)
        # tied-back curtains
        for side in (-1, 1):
            cx = side * (w / 2 - 20)
            cur = smooth([(cx - 26 * side, -556), (cx + 30 * side, -556), (cx + 10 * side, -420), (cx + 4 * side, -300),
                          (cx - 10 * side, -300), (cx - 16 * side, -430)])
            shape(canvas, cur, (0.62, 0.3, 0.26), w=1.1, a=0.9)
            wash(canvas, cur, ellipse(cx, -430, 14, 120), (0.35, 0.12, 0.1), 0.4, 8)
            stroke_line(canvas, [(cx - 10, -360), (cx + 10, -352)], 2.0, GOLD, 0.9)
    if panels:      # back panel with an ink painting
        lacquer_bar(canvas, -w / 2, -330, w / 2, -316)
        ink_landscape(canvas, -w / 2 + 8, -316, w / 2 - 8, seat - 6, seed, "mountains")
        outline(canvas, _rect(-w / 2 + 8, -316, w / 2 - 8, seat - 6), 1.0)
    # platform
    top = poly([(-w / 2 - 10, seat), (w / 2 + 10, seat), (w / 2 + 10, seat + 18), (-w / 2 - 10, seat + 18)])
    shape(canvas, top, LACQUER, w=1.3)
    stroke_line(canvas, [(-w / 2 - 6, seat + 3), (w / 2 + 6, seat + 3)], 0.9, LACQUER_HI, 0.9)
    apron = poly([(-w / 2, seat + 18), (w / 2, seat + 18), (w / 2 - 6, -18), (-w / 2 + 6, -18)])
    shape(canvas, apron, shade(LACQUER, 0.05), w=1.2)
    for k in range(-2, 3):          # kunmen openings
        ox = k * w / 5.4
        op = smooth([('c', ox - 24, seat + 36), ('c', ox + 24, seat + 36), (ox + 22, -40), ('c', ox + 10, -30),
                     (ox, -36), ('c', ox - 10, -30), (ox - 22, -40)])
        fill(canvas, op, (0.1, 0.07, 0.06))
        outline(canvas, op, 0.8, LACQUER_HI, 0.7)
    for lx in (-w / 2 + 6, w / 2 - 18):
        lacquer_bar(canvas, lx, -20, lx + 12, 0)


def quilt(canvas, w=200, color=(0.55, 0.22, 0.18), seed=3):
    q = smooth([(-w / 2, -20), (-w / 2 + 30, -46), (w / 2 - 20, -40), (w / 2, -12), (w / 2 - 10, 0), (-w / 2 + 6, 0)])
    shape(canvas, q, color, w=1.2)
    rng = np.random.default_rng(seed)
    for _ in range(9):
        x, y = rng.uniform(-w / 2 + 20, w / 2 - 20), rng.uniform(-36, -8)
        fill(canvas, ellipse(x, y, 5, 4), GOLD, 0.8)
    wash(canvas, q, ellipse(w / 3, -10, w / 3, 20), shade(color, -0.4), 0.4, 10)


def table(canvas, w=220, h=90, items=()):
    """Low lacquer table; items = list of (kind, dx) drawn on the top."""
    top = -h
    shape(canvas, poly([(-w / 2 - 6, top), (w / 2 + 6, top), (w / 2 + 6, top + 12), (-w / 2 - 6, top + 12)]),
          LACQUER, w=1.3)
    stroke_line(canvas, [(-w / 2, top + 3), (w / 2, top + 3)], 0.9, LACQUER_HI, 0.8)
    for lx in (-w / 2 + 4, w / 2 - 14):
        lacquer_bar(canvas, lx, top + 12, lx + 10, 0)
    lacquer_bar(canvas, -w / 2 + 4, -18, w / 2 - 4, -12)
    for kind, dx in items:
        with Xf(canvas, dx, top):
            dish(canvas, kind)


def dish(canvas, kind):
    """Small table-top objects, origin at the table surface."""
    if kind in ("fruit", "peach", "cakes"):
        shape(canvas, ellipse(0, -4, 26, 6), (0.92, 0.9, 0.84), w=1.1)
        cols = {"fruit": [(0.86, 0.36, 0.16), (0.9, 0.6, 0.2), (0.78, 0.24, 0.16)],
                "peach": [(0.95, 0.62, 0.55), (0.92, 0.5, 0.45)], "cakes": [(0.93, 0.85, 0.66)] * 3}[kind]
        for i, c in enumerate(cols * 2):
            x = -14 + (i % 3) * 14
            y = -12 - (i // 3) * 9
            shape(canvas, ellipse(x, y, 7.5, 6.5), c, w=1.0)
    elif kind == "ewer":         # wine ewer in a warming bowl (zhuzi and zhuwan)
        bowl = smooth([(-24, -30), (24, -30), (18, -4), (-18, -4)])
        shape(canvas, bowl, (0.88, 0.86, 0.78), w=1.2)
        body = smooth([(-12, -30), (-14, -52), (-6, -64), (6, -64), (14, -52), (12, -30)])
        shape(canvas, body, (0.9, 0.88, 0.8), w=1.2)
        stroke_line(canvas, [(-12, -48), (-26, -60), ('c', -30, -66)], 2.0, INK, 0.8)
        shape(canvas, ellipse(0, -68, 5, 4), (0.9, 0.88, 0.8), w=1.0)
        for x in (-10, 0, 10):
            stroke_line(canvas, [(x, -28), (x * 1.2, -8)], 0.7, INK, 0.4)
    elif kind == "celadon":
        shape(canvas, smooth([('c', -10, -16), ('c', 10, -16), (6, -2), (-6, -2)]), (0.56, 0.74, 0.64), w=1.1)
        fill(canvas, ellipse(0, -16, 10, 2.4), (0.72, 0.86, 0.78))
        shape(canvas, ellipse(0, -1, 6.5, 2), (0.5, 0.68, 0.58), w=0.9)
    elif kind == "cup":
        shape(canvas, smooth([(-9, -14), (9, -14), (5, -2), (-5, -2)]), (0.92, 0.9, 0.84), w=1.1)
        shape(canvas, ellipse(0, -1, 6, 2), (0.92, 0.9, 0.84), w=0.9)
    elif kind == "teabowl":
        shape(canvas, smooth([(-14, -14), (14, -14), (8, -2), (-8, -2)]), (0.36, 0.3, 0.26), w=1.1)
        fill(canvas, ellipse(0, -14, 14, 3), (0.62, 0.56, 0.34))
    elif kind == "fish":
        shape(canvas, ellipse(0, -4, 30, 6), (0.92, 0.9, 0.84), w=1.1)
        fish = smooth([(-22, -10), (-8, -18), (12, -14), (20, -10), ('c', 30, -18), ('c', 30, -4), (20, -10), (10, -6),
                       (-8, -4)])
        shape(canvas, fish, (0.82, 0.68, 0.46), w=1.1)
        fill(canvas, ellipse(-14, -12, 1.8, 1.8), INK)


def chair(canvas, facing=-1):
    """Yoke-back chair seen from the side; seat at -120. facing -1: sitter faces left."""
    with Xf(canvas, 0, 0, 0, -facing, 1):
        lacquer_bar(canvas, -40, -124, 44, -112)
        for lx in (-38, 32):
            lacquer_bar(canvas, lx, -112, lx + 8, 0)
        lacquer_bar(canvas, 34, -300, 44, -124)          # back post
        yoke = smooth([(24, -306), (48, -312), (58, -304), (40, -298)])
        shape(canvas, yoke, LACQUER, w=1.1)
        lacquer_bar(canvas, -36, -30, 40, -24)


def candle(canvas, t, h=380, flicker_seed=0):
    """Tall candle stand; flame flickers with time t (seconds)."""
    base = smooth([(-40, 0), (-30, -16), (30, -16), (40, 0)])
    shape(canvas, base, LACQUER, w=1.2)
    lacquer_bar(canvas, -4, -h, 4, -16)
    dishp = poly([(-26, -h), (26, -h), (20, -h + 8), (-20, -h + 8)])
    shape(canvas, dishp, GOLD, w=1.1)
    shape(canvas, _rect(-6, -h - 40, 6, -h), (0.93, 0.25, 0.18), w=1.0)
    f = 1.0 + 0.12 * math.sin(t * 13.0 + flicker_seed) + 0.08 * math.sin(t * 29.0 + flicker_seed * 2)
    sway = 2.0 * math.sin(t * 7.0 + flicker_seed)
    flame = smooth([(0 + sway, -h - 40 - 30 * f), ('c', 7, -h - 46), (5, -h - 38), (-5, -h - 38), ('c', -7, -h - 46)])
    radial_glow(canvas, sway * 0.5, -h - 52, 150 * f, (1.0, 0.72, 0.35), 0.28)
    fill(canvas, flame, (1.0, 0.8, 0.35), 0.95)
    fill(canvas, ellipse(sway * 0.5, -h - 46, 3, 6), (1.0, 0.97, 0.85))


def drum(canvas, t_hit=99.0):
    """Jiegu drum on a red stand; t_hit = seconds since the last stroke (skin shiver)."""
    for lx, ang in ((-30, -10), (30, 10)):
        with Xf(canvas, lx, 0, ang):
            lacquer_bar(canvas, -4, -150, 4, 0, VERMILION)
    lacquer_bar(canvas, -40, -150, 40, -142, VERMILION)
    body = smooth([(-44, -210), (-54, -176), (-44, -142), (44, -142), (54, -176), (44, -210)])
    shape(canvas, body, (0.78, 0.2, 0.14), w=1.4)
    wash(canvas, body, ellipse(20, -176, 30, 30), (0.4, 0.06, 0.04), 0.45, 10)
    for yy in (-196, -156):
        stroke_line(canvas, [(-50, yy), (0, yy + 4), (50, yy)], 1.4, GOLD, 0.9)
    s = 1.0 + (0.06 * math.exp(-t_hit * 18) * math.sin(t_hit * 90) if t_hit < 0.5 else 0)
    for cx in (-50, 50):
        shape(canvas, ellipse(cx, -176, 6 * s, 34 * s), (0.93, 0.88, 0.74), w=1.3)


def pipa(canvas, x, y, ang=-55.0, scale=1.0, pluck=0.0):
    """Pipa held with its body at (x,y), neck pointing along ang (deg). pluck: 0..1 string vibration."""
    with Xf(canvas, x, y, ang, scale):
        body = smooth([(-10, -30), (20, -34), (54, -26), (70, 0), (54, 26), (20, 34), (-10, 30), (-22, 0)])
        shape(canvas, body, (0.62, 0.38, 0.18), w=1.4)
        wash(canvas, body, ellipse(40, 10, 30, 20), (0.35, 0.18, 0.08), 0.4, 10)
        neck = smooth([(-22, -8), (-110, -6), ('c', -128, -10), ('c', -128, 10), (-110, 6), (-22, 8)])
        shape(canvas, neck, (0.45, 0.26, 0.12), w=1.3)
        for fx in (-40, -58, -74, -88, -100):
            stroke_line(canvas, [(fx, -8), (fx, 8)], 1.4, (0.9, 0.86, 0.75), 0.9)
        for k in (-4, 4):
            tapered(canvas, [(-128, k * 1.6 - 4), (-138, k * 2.4 - 6)], 3, 1.5, INK, 0.9)
        shape(canvas, _rect(38, -12, 44, 12), (0.25, 0.14, 0.07), w=1.0)      # bridge
        vib = pluck * 1.5
        for i, k in enumerate((-4.5, -1.5, 1.5, 4.5)):
            wob = vib * math.sin(i * 1.7 + pluck * 20)
            stroke_line(canvas, [(-118, k * 0.9), (-40, k + wob), (40, k)], 0.6, (0.95, 0.93, 0.85), 0.95)
        fill(canvas, ellipse(20, -10, 8, 5), (0.3, 0.16, 0.08), 0.7)


def flute(canvas, x, y, ang=0.0, length=150, kind="dizi"):
    with Xf(canvas, x, y, ang):
        if kind == "bili":
            b = smooth([(0, -4), (70, -5), (82, -10), (86, 10), (70, 5), (0, 4)])
            shape(canvas, b, (0.46, 0.3, 0.14), w=1.2)
            for hx in (18, 30, 42, 54):
                fill(canvas, ellipse(hx, 0, 1.8, 1.8), INK)
            return
        tube = _rect(0, -4, length, 4)
        shape(canvas, tube, (0.72, 0.6, 0.32), w=1.2)
        for hx in np.linspace(length * 0.35, length * 0.85, 6):
            fill(canvas, ellipse(hx, 0, 1.7, 1.7), INK)
        for bx in (length * 0.15, length * 0.95):
            stroke_line(canvas, [(bx, -4), (bx, 4)], 1.5, VERMILION, 0.9)
        ribbon_y = 4
        stroke_line(canvas, [(length * 0.95, ribbon_y), (length * 0.97, ribbon_y + 24), (length, ribbon_y + 40)], 1.6,
                    VERMILION, 0.9)


def clappers(canvas, x, y, ang=0.0, open_=0.0):
    with Xf(canvas, x, y, ang):
        for i in range(5):
            a = (i - 2) * 3.5 * open_
            with Xf(canvas, 0, 0, a):
                shape(canvas, _rect(-5 + i * 1.5, -70, 5 + i * 1.5, 0), (0.62, 0.45, 0.25), w=1.0)
        stroke_line(canvas, [(-6, -8), (12, -8)], 2.2, VERMILION, 0.9)


def fan(canvas, x, y, ang=0.0):
    with Xf(canvas, x, y, ang):
        tapered(canvas, [(0, 0), (0, -40)], 4, 3, LACQUER)
        face = ellipse(0, -72, 34, 34)
        shape(canvas, face, (0.93, 0.9, 0.82), w=1.2, a=0.95)
        ink_landscape(canvas, -24, -96, 24, -50, 5, "mountains")
        outline(canvas, face, 1.3)


def drumstick(canvas, x, y, ang=-60.0):
    with Xf(canvas, x, y, ang):
        tapered(canvas, [(0, 0), (70, 0)], 4.5, 3, (0.55, 0.36, 0.18))
        fill(canvas, ellipse(72, 0, 4, 4), (0.55, 0.36, 0.18))


def basin(canvas, water=True, splash=0.0):
    stand = smooth([(-30, 0), (-20, -80), (20, -80), (30, 0)])
    shape(canvas, stand, LACQUER, w=1.2)
    bowl = smooth([(-46, -110), (46, -110), (36, -82), (-36, -82)])
    shape(canvas, bowl, (0.78, 0.74, 0.62), w=1.3)
    if water:
        fill(canvas, ellipse(0, -110, 44, 6), (0.62, 0.74, 0.78), 0.9)
    if splash > 0:
        rng = np.random.default_rng(int(splash * 100))
        for _ in range(8):
            a = rng.uniform(-2.6, -0.5)
            r = 20 + splash * 30
            fill(canvas, ellipse(math.cos(a) * r, -112 + math.sin(a) * r * 0.8, 2.5, 3.5), (0.7, 0.82, 0.88), 0.8)


def basket(canvas, w=90, h=60):
    b = smooth([(-w / 2, -h), (w / 2, -h), (w / 2 - 8, 0), (-w / 2 + 8, 0)])
    shape(canvas, b, (0.64, 0.5, 0.3), w=1.3)
    for i in range(1, 6):
        stroke_line(canvas, [(-w / 2 + 4, -h + i * h / 6), (w / 2 - 4, -h + i * h / 6)], 0.8, INK, 0.45)
    for i in range(1, 8):
        x = -w / 2 + i * w / 8
        stroke_line(canvas, [(x, -h), (x * 0.9, 0)], 0.7, INK, 0.35)


def moth(canvas, x, y, t, scale=1.0, ang=0.0):
    """Fluttering moth; t in seconds drives the wing beat."""
    flap = abs(math.sin(t * 22.0))
    with Xf(canvas, x, y, ang, scale):
        for side in (-1, 1):
            with Xf(canvas, 0, 0, 0, 0.3 + 0.7 * flap, 1):
                w1 = smooth([(0, -2), (side * 9, -12), (side * 20, -9), (side * 18, 1), (side * 4, 2)])
                shape(canvas, w1, (0.78, 0.72, 0.6), w=0.8, a=0.95)
                stroke_line(canvas, [(side * 4, -3), (side * 14, -6)], 0.6, (0.45, 0.38, 0.3), 0.8)
                fill(canvas, ellipse(side * 12, -6, 1.8, 1.8), (0.42, 0.34, 0.26), 0.9)
                w2 = smooth([(0, 1), (side * 12, 3), (side * 11, 10), (side * 3, 7)])
                shape(canvas, w2, (0.72, 0.66, 0.54), w=0.8, a=0.95)
        shape(canvas, ellipse(0, 2, 2.6, 7.5), (0.5, 0.42, 0.32), w=0.8)
        for side in (-1, 1):
            stroke_line(canvas, [(0, -5), (side * 3, -11), (side * 6, -13)], 0.6, INK, 0.8)


def cushion(canvas, w=110, color=(0.3, 0.45, 0.4)):
    c = smooth([(-w / 2, -8), (-w / 2 + 10, -26), (w / 2 - 10, -26), (w / 2, -8), (w / 2 - 6, 0), (-w / 2 + 6, 0)])
    shape(canvas, c, color, w=1.2)
    for tx in (-w / 2 + 4, w / 2 - 4):
        stroke_line(canvas, [(tx, -10), (tx + (6 if tx > 0 else -6), -2)], 1.6, GOLD, 0.9)


def stool(canvas):
    shape(canvas, poly([(-40, -96), (40, -96), (40, -84), (-40, -84)]), LACQUER, w=1.2)
    for lx in (-36, 28):
        lacquer_bar(canvas, lx, -84, lx + 8, 0)
    shape(canvas, ellipse(0, -100, 42, 8), (0.55, 0.25, 0.22), w=1.0)
