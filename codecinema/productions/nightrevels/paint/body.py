"""
body.py - robes, sleeves (2-bone IK arms), paws, tails and hats for the cat courtiers.

Local frame: origin at the base of the neck, facing LEFT, y down. The head is drawn centred at HEAD_AT (+ pose offset).
Postures place the ground: "stand" (feet at y=+270), "cross" (cross-legged, base at y=+150), "stool" (feet at +215).

Costume dict keys:
    kind      "robe" (round-collar official robe) | "dress" (high-waisted skirt + short jacket) | "kasaya" | "jacket"
    color     main colour hex ; trim: collar / hem colour ; belt: belt colour ; inner: under-robe colour
    sleeve    sleeve width factor (1 = wide court sleeve, 1.8 = dancer's long sleeves)
    shawl     shawl colour (dresses) or None
    hat       None | "tall" (Han's gauze hat) | "futou" (black cap with soft tails) | "bun" (hair bun + pins)
    shoes     shoe colour
    open      0..1 robe opened over the belly (scene 4)
"""

import math

from ink import (INK, Xf, edge_fur, ellipse, fill, fur, hexc, outline, poly, shade, shape, smooth, stroke_line,
                 tapered, wash)

HEAD_AT = (-6.0, -50.0)
GROUND = dict(stand=270.0, cross=150.0, stool=215.0, kneel=130.0)


def _c(v, default):
    return hexc(v) if isinstance(v, str) else (v if v is not None else default)


# ------------------------------------------------------------------------------------------------ arms
def ik2(sx, sy, tx, ty, l1, l2, bend=1.0):
    """Two-bone IK in 2D: shoulder (sx,sy) -> target (tx,ty); returns elbow and clamped wrist. bend=+1/-1 side."""
    dx, dy = tx - sx, ty - sy
    d = max(1e-3, math.hypot(dx, dy))
    d_c = min(d, l1 + l2 - 1e-3)
    wx, wy = sx + dx / d * d_c, sy + dy / d * d_c
    a = (l1 * l1 - l2 * l2 + d_c * d_c) / (2 * d_c)
    h = math.sqrt(max(0.0, l1 * l1 - a * a))
    mx, my = sx + dx / d * a, sy + dy / d * a
    ex, ey = mx + (-dy / d) * h * bend, my + (dx / d) * h * bend
    return (ex, ey), (wx, wy)


def sleeve(canvas, S, P, color, trim, width=1.0, hang=1.0, bend=1.0, l1=62.0, l2=60.0, line=1.5, inner=None):
    """A wide Tang sleeve from shoulder S to paw target P. Returns (wrist point, forearm angle)."""
    E, W = ik2(S[0], S[1], P[0], P[1], l1, l2, bend)
    fa = math.atan2(W[1] - E[1], W[0] - E[0])
    ua = math.atan2(E[1] - S[1], E[0] - S[0])
    w0, w1, w2 = 22 * width, 20 * width, 22 * width
    n0 = (-math.sin(ua), math.cos(ua))
    n1 = (-math.sin((ua + fa) / 2), math.cos((ua + fa) / 2))
    n2 = (-math.sin(fa), math.cos(fa))
    # the "top" edge (away from gravity) and the hanging bag under the forearm
    top = [(S[0] - n0[0] * w0, S[1] - n0[1] * w0), (E[0] - n1[0] * w1, E[1] - n1[1] * w1),
           (W[0] - n2[0] * w2, W[1] - n2[1] * w2)]
    drop = 44.0 * hang * width
    cuff_low = (W[0] + n2[0] * w2, W[1] + n2[1] * w2)
    bag = (cuff_low[0] - math.cos(fa) * 14, max(cuff_low[1], E[1]) + drop)
    bot = [cuff_low, bag, (E[0] + n1[0] * w1, E[1] + n1[1] * w1 + drop * 0.35), (S[0] + n0[0] * w0, S[1] + n0[1] * w0)]
    path = smooth(top + bot)
    shape(canvas, path, color, w=line)
    wash(canvas, path, smooth([bag, (E[0], E[1] + drop * 0.5), cuff_low]), shade(color, -0.35), 0.35, 7)
    # fold lines
    stroke_line(canvas, [((E[0] + W[0]) / 2, (E[1] + W[1]) / 2 + 4), (bag[0] + 6, bag[1] - 10)], 1.0, INK, 0.5)
    # cuff trim: a band just inside the opening
    k = 4.5
    cuff = poly([top[2], cuff_low, (cuff_low[0] - math.cos(fa) * k, cuff_low[1] - math.sin(fa) * k),
                 (top[2][0] - math.cos(fa) * k, top[2][1] - math.sin(fa) * k)])
    shape(canvas, cuff, trim, w=1.1)
    return W, fa


def paw(canvas, x, y, ang, coat, pad=None, size=1.0, grip=False):
    """A mitten paw at (x,y) pointing along ang (radians)."""
    with Xf(canvas, x, y, math.degrees(ang), size):
        p = smooth([(-4, -9), (8, -10), (15, -5), (16, 3), (10, 9), (-4, 9)])
        shape(canvas, p, coat, w=1.3)
        for dy in (-4, 1) if not grip else (-3,):
            stroke_line(canvas, [(9, dy - 1), (14, dy + 1)], 1.0)
        if pad is not None and grip:
            fill(canvas, ellipse(6, 3, 4, 3), pad, 0.8)


def ribbon(canvas, pts, width, color, a=0.95, twist=0.0, line=1.1):
    """A flowing silk strip (shawl / water sleeve) along pts, with a slow width modulation (twists)."""
    import skia
    path = smooth(pts, closed=False)
    meas = skia.PathMeasure(path, False)
    L = meas.getLength()
    if L <= 1:
        return
    left, right = [], []
    for i in range(33):
        d = L * i / 32
        pos, tan = meas.getPosTan(d)
        w = width * (0.55 + 0.45 * abs(math.cos(i / 32 * math.pi * 2.2 + twist)))
        nx, ny = -tan.y(), tan.x()
        left.append((pos.x() + nx * w * 0.5, pos.y() + ny * w * 0.5))
        right.append((pos.x() - nx * w * 0.5, pos.y() - ny * w * 0.5))
    strip = smooth(left + right[::-1])
    shape(canvas, strip, color, w=line, a=a)
    stroke_line(canvas, pts, 0.8, INK, 0.3)


def flow(anchor, direction, length, phase, amp=1.0, n=6, sag=0.35):
    """Points of a hanging / trailing cloth strip from anchor; direction in degrees (90 = straight down)."""
    ax, ay = anchor
    out = []
    for i in range(n):
        t = i / (n - 1)
        a = math.radians(direction) + math.sin(phase * 2 * math.pi + t * 3.0) * 0.35 * amp * t
        out.append((ax + math.cos(a) * length * t + math.sin(t * 3.1 + phase * 6.28) * 6 * amp * t,
                    ay + math.sin(a) * length * t + sag * length * t * t * 0.3))
    return out


# ------------------------------------------------------------------------------------------------ tail
def tail(canvas, b, root, phase, amp=1.0, length=150.0, curl=1.0, fluffy=1.0, up=False):
    """A swaying tail from root, growing to the right (behind a left-facing cat)."""
    x0, y0 = root
    pts = []
    n = 7
    for i in range(n):
        t = i / (n - 1)
        a = (-0.35 if up else 0.25) + t * (1.2 * curl) * (-1 if up else 1) + math.sin(phase * 2 * math.pi + t * 2.4) * 0.45 * amp * t
        r = length * t
        pts.append((x0 + math.cos(-a) * r * 0.9 + t * 20, y0 - math.sin(a) * r * (0.8 if up else 0.35) - (t * 60 if up else 0)))
    w0, w1 = 18 * fluffy, 9 * fluffy
    import skia
    path = smooth(pts, closed=False)
    meas = skia.PathMeasure(path, False)
    L = meas.getLength()
    left, right = [], []
    for i in range(25):
        d = L * i / 24
        pos, tan = meas.getPosTan(d)
        w = (w0 + (w1 - w0) * (i / 24)) * (1.0 if i < 22 else (24 - i) / 2.5)
        nx, ny = -tan.y(), tan.x()
        left.append((pos.x() + nx * w * 0.5, pos.y() + ny * w * 0.5))
        right.append((pos.x() - nx * w * 0.5, pos.y() - ny * w * 0.5))
    outline_path = smooth(left + right[::-1])
    c = b.mask or b.base
    fill(canvas, outline_path, c)
    canvas.save()
    canvas.clipPath(outline_path, doAntiAlias=True)
    if b.pattern == "tabby" or b.pattern == "tuxedo" and False:
        for i in range(3, 24, 4):
            pos, tan = meas.getPosTan(L * i / 24)
            nx, ny = -tan.y(), tan.x()
            tapered(canvas, [(pos.x() - nx * 12, pos.y() - ny * 12), (pos.x() + nx * 12, pos.y() + ny * 12)], 4, 3,
                    b.dark, 0.8)
    for cc, *_ in b.patches[:1]:
        pos, _t = meas.getPosTan(L * 0.75)
        fill(canvas, ellipse(pos.x(), pos.y(), 16, 16), cc)
    canvas.restore()
    if not b.hairless:
        fur(canvas, None, edge_fur(outline_path, int(46 * fluffy), 7 * fluffy, seed=b.seed + 21, inward=False),
            shade(c, -0.3), 0.5, 0.7)
    outline(canvas, outline_path, 1.4)


# ------------------------------------------------------------------------------------------------ robes
def _robe_stand(C, color, trim, inner, open_):
    body = [(-26, -4), (-40, 12), (-46, 60), (-52, 120), (-60, 200), ('c', -72, 262), (-10, 268), ('c', 62, 262),
            (54, 200), (46, 120), (42, 60), (36, 12), (24, -4)]
    return smooth(body)


def draw_body(canvas, b, costume, posture, p, hold=None):
    """Draws far sleeve, tail, robe, belt, collar, near sleeve; returns anchor dict for head/props."""
    kind = costume.get("kind", "robe")
    color = _c(costume.get("color"), (0.3, 0.3, 0.32))
    trim = _c(costume.get("trim"), shade(color, -0.35))
    belt = _c(costume.get("belt"), (0.12, 0.1, 0.1))
    inner = _c(costume.get("inner"), (0.93, 0.9, 0.84))
    shawl = _c(costume.get("shawl"), None) if costume.get("shawl") else None
    sw = costume.get("sleeve", 1.0)
    shoes = _c(costume.get("shoes"), (0.12, 0.1, 0.1))
    open_ = costume.get("open", 0.0)
    coat = b.mask or b.base
    by = p["body_y"]
    br = 1.0 + 0.012 * p["breath"]
    anchors = {}
    with Xf(canvas, p.get("body_x", 0.0), by, 0, 1.0, br):
        FS, NS = (-24, 10), (24, 12)           # far / near shoulders
        paw_far = (-44 + p["paw_l"][0], 96 + p["paw_l"][1])
        paw_near = (-10 + p["paw_r"][0], 104 + p["paw_r"][1])
        if posture == "cross":
            paw_far = (-50 + p["paw_l"][0], 110 + p["paw_l"][1])
            paw_near = (-8 + p["paw_r"][0], 118 + p["paw_r"][1])
        # --- tail behind everything
        if costume.get("tail", True):
            troot = (34, GROUND[posture] - 30) if posture != "cross" else (60, GROUND[posture] - 14)
            tail(canvas, b, troot, p["tail"], p["tail_amp"], length=costume.get("tail_len", 150),
                 fluffy=costume.get("tail_fluff", 1.0) * (1.3 if b.fluff > 1.2 else 1.0))
        # --- far sleeve (behind body)
        rl, rr = p.get("reach_l", 1.0), p.get("reach_r", 1.0)
        Wf, af = sleeve(canvas, FS, paw_far, shade(color, -0.12), trim, sw, bend=-1.0, l1=62 * rl, l2=60 * rl)
        paws = [(Wf, af, costume.get("grip_far", False))]
        water = costume.get("water")
        if water:
            wl = p.get("water_l", (math.degrees(af) + 40, 0.0))
            ribbon(canvas, flow((Wf[0], Wf[1]), wl[0], water, wl[1], 1.4, n=8), 22, _c(costume.get("water_c"), (0.97, 0.95, 0.9)), 0.95, twist=wl[1])
        # --- robe
        if posture == "stand":
            if kind == "dress":
                body = smooth([(-22, -2), (-34, 10), (-36, 40), (-44, 70), (-62, 170), ('c', -80, 262), (-10, 270),
                               ('c', 66, 262), (52, 170), (40, 70), (34, 40), (30, 10), (20, -2)])
            else:
                body = _robe_stand(canvas, color, trim, inner, open_)
            ground = GROUND["stand"]
            # shoes
            for sx in (-40, -6):
                sh = smooth([(sx - 14, ground - 6), (sx + 8, ground - 8), (sx + 12, ground + 2), ('c', sx - 22, ground + 2)])
                shape(canvas, sh, shoes, w=1.2)
        elif posture == "stool":
            body = smooth([(-26, -4), (-40, 12), (-46, 60), (-60, 118), (-92, 132), (-100, 160), (-86, 206),
                           ('c', -70, 214), (-20, 212), (40, 206), (52, 160), (48, 110), (40, 60), (34, 12), (24, -4)])
            ground = GROUND["stool"]
            sh = smooth([(-102, ground - 6), (-80, ground - 8), (-76, ground + 2), ('c', -110, ground + 2)])
            shape(canvas, sh, shoes, w=1.2)
        else:   # cross-legged
            body = smooth([(-26, -4), (-40, 12), (-50, 60), (-70, 100), (-104, 118), (-110, 140), ('c', -96, 152),
                           (-10, 156), ('c', 76, 150), (80, 124), (58, 96), (44, 56), (36, 12), (24, -4)])
            ground = GROUND["cross"]
        shape(canvas, body, color, w=1.7)
        # soft shading + fold lines
        wash(canvas, body, ellipse(46, 120, 40, 140), shade(color, -0.3), 0.4, 18)
        wash(canvas, body, ellipse(-30, 40, 26, 50), shade(color, 0.25), 0.25, 14)
        folds = {"stand": [[(-30, 130), (-38, 200), (-46, 258)], [(8, 140), (10, 200), (16, 262)],
                           [(30, 150), (36, 210)]],
                 "stool": [[(-60, 150), (-30, 170), (10, 176)], [(-80, 170), (-60, 200)], [(20, 120), (30, 190)]],
                 "cross": [[(-80, 120), (-40, 136), (0, 140)], [(10, 110), (40, 130)], [(-40, 70), (-50, 100)]]}[posture]
        for f in folds:
            stroke_line(canvas, f, 1.0, INK, 0.45)
        # garment details
        if kind == "robe":
            if open_ > 0:
                belly = smooth([(-18, 30), (4, 24), (14, 60 + 40 * open_), (0, 110 + 20 * open_), (-26, 100),
                                (-34, 60)])
                fill(canvas, belly, b.light)
                fur(canvas, belly, edge_fur(belly, 50, 8, seed=b.seed + 30), shade(b.light, -0.25), 0.5, 0.7)
                outline(canvas, belly, 1.2)
            # round collar
            collar = smooth([(-26, -6), (-10, 6), (14, 4), (26, -6), (22, 4), (0, 14), (-22, 6)])
            shape(canvas, collar, trim, w=1.3)
            # belt
            if posture != "cross" or True:
                belt_p = smooth([(-44, 92), (0, 100), (44, 94), (44, 104), (0, 110), (-45, 102)])
                shape(canvas, belt_p, belt, w=1.2)
                for bx in (-30, -12, 8, 26):
                    fill(canvas, ellipse(bx, 101 + bx * 0.02, 3.2, 3.2), (0.82, 0.68, 0.34))
        elif kind == "dress":
            jacket = smooth([(-26, -4), (-36, 12), (-38, 48), (0, 56), (32, 48), (32, 12), (22, -4)])
            shape(canvas, jacket, _c(costume.get("jacket"), shade(color, 0.35)), w=1.3)
            band = smooth([(-38, 44), (0, 52), (34, 44), (34, 56), (0, 64), (-39, 56)])
            shape(canvas, band, trim, w=1.1)
            neck = smooth([(-22, -4), (0, 14), (22, -4), (10, -2), (0, 6), (-10, -2)])
            fill(canvas, neck, b.light)
        elif kind == "kasaya":
            # patchwork mantle over the left shoulder, crossing diagonally to the right hip
            drape = smooth([(-28, -2), (-10, 6), (28, 60), (48, 130), (40, 176), (10, 150), (-40, 120), (-50, 60),
                            (-40, 10)])
            shape(canvas, drape, shade(color, -0.12), w=1.3)
            canvas.save()
            canvas.clipPath(drape, doAntiAlias=True)
            for i in range(-4, 6):
                stroke_line(canvas, [(-60 + i * 22, -10), (-20 + i * 22, 190)], 1.1, shade(color, -0.45), 0.6)
            for j in range(0, 200, 38):
                stroke_line(canvas, [(-70, j), (70, j + 30)], 1.1, shade(color, -0.45), 0.6)
            canvas.restore()
            fill(canvas, ellipse(26, 58, 5, 5), (0.8, 0.66, 0.3))
        # shawl (pibo): a loop behind the shoulders, over the chest, trailing from both forearms
        if shawl is not None:
            ph = p.get("cloth", 0.0)
            ribbon(canvas, [(-30, 4), (-40, 40), (-6, 64), (30, 44), (26, 6)], 16, shawl, 0.9)
            ribbon(canvas, flow((-46, 70), 100, 150, ph, 0.8), 14, shawl, 0.9, twist=ph)
            ribbon(canvas, flow((50, 60), 80, 170, ph + 0.3, 0.8), 14, shawl, 0.9, twist=ph + 1)
        if hold is not None:            # held instrument / prop between the body and the near arm
            hold(canvas)
        # --- near sleeve (in front)
        Wn, an = sleeve(canvas, NS, paw_near, color, trim, sw, bend=-1.0, l1=62 * rr, l2=60 * rr)
        paws.append((Wn, an, costume.get("grip_near", False)))
        if water:
            wr = p.get("water_r", (math.degrees(an) + 40, 0.3))
            ribbon(canvas, flow((Wn[0], Wn[1]), wr[0], water, wr[1], 1.4, n=8), 22, _c(costume.get("water_c"), (0.97, 0.95, 0.9)), 0.95, twist=wr[1])
        for (W_, a_, g_), ang_over in zip(paws, (p.get("paw_ang_l"), p.get("paw_ang_r"))):
            aa = math.radians(ang_over) if ang_over is not None else a_
            paw(canvas, W_[0] + math.cos(a_) * 6, W_[1] + math.sin(a_) * 6, aa, coat, b.nose, size=1.3, grip=g_)
        anchors.update(paw_far=(Wf[0] + math.cos(af) * 14, Wf[1] + math.sin(af) * 14 + by),
                       paw_near=(Wn[0] + math.cos(an) * 14, Wn[1] + math.sin(an) * 14 + by), ground=ground)
    return anchors


# ------------------------------------------------------------------------------------------------ hats
def hat_back(canvas, b, costume, p):
    """Parts of the hat behind the head (soft cap tails)."""
    h = costume.get("hat")
    if h == "futou":
        for dx, ln in ((24, 78), (32, 70)):
            tapered(canvas, [(dx, -46), (dx + 16, -20), (dx + 20, -46 + ln)], 8, 6, (0.1, 0.09, 0.09), 0.95)


def hat_front(canvas, b, costume, p):
    h = costume.get("hat")
    if h == "tall":        # Han Xizai's tall gauze hat
        crown = smooth([('c', -30, -38), (-32, -80), (-26, -118), ('c', -20, -124), (22, -122), ('c', 28, -116),
                        (30, -76), ('c', 26, -38), (0, -44)])
        shape(canvas, crown, (0.12, 0.11, 0.11), w=1.5)
        wash(canvas, crown, ellipse(-10, -90, 10, 30), (0.4, 0.38, 0.38), 0.35, 6)
        for x in (-18, -4, 10, 22):
            stroke_line(canvas, [(x, -44), (x + 1, -118)], 0.7, (0.35, 0.33, 0.33), 0.6)
        band = smooth([(-30, -44), (0, -50), (27, -44), (27, -36), (0, -42), (-30, -36)])
        shape(canvas, band, (0.2, 0.18, 0.18), w=1.2)
    elif h == "futou":
        cap = smooth([('c', -34, -34), (-34, -54), (-22, -64), (-6, -66), (-2, -84), (8, -92), (18, -86), (20, -66),
                      (30, -58), ('c', 32, -34), (0, -40)])
        shape(canvas, cap, (0.1, 0.09, 0.09), w=1.4)
        wash(canvas, cap, ellipse(4, -76, 8, 12), (0.42, 0.4, 0.4), 0.45, 4)
        stroke_line(canvas, [(-32, -44), (0, -50), (30, -44)], 0.8, (0.4, 0.38, 0.38), 0.7)
    elif h == "bun":
        bun = ellipse(4, -52, 18, 14)
        shape(canvas, bun, shade(b.base, -0.25) if not b.mask else b.mask, w=1.3)
        for dx, c in ((-10, (0.85, 0.65, 0.2)), (16, (0.85, 0.65, 0.2))):
            stroke_line(canvas, [(dx, -56), (dx + 18, -66)], 1.6, c, 0.95)
            fill(canvas, ellipse(dx + 18, -66, 3, 3), (0.86, 0.2, 0.2))
        flower = costume.get("flower")
        if flower:
            fc = hexc(flower)
            for k in range(5):
                a = k * 2 * math.pi / 5
                fill(canvas, ellipse(-14 + math.cos(a) * 5, -48 + math.sin(a) * 5, 4.2, 4.2), fc)
            fill(canvas, ellipse(-14, -48, 2.4, 2.4), (0.95, 0.8, 0.3))
