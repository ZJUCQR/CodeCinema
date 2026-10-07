"""
cat.py - the cat-courtier puppet: a gongbi-style cat head on a robed, seated or standing body.

A character = Breed (coat, face and ear shape) + Costume (robe, sleeves, hat, accessories) + Pose (per-frame values).
Everything is drawn facing LEFT in local units (head radius ~50 su); a negative x-scale mirrors a character.

Pose keys (all optional, defaults in POSE0):
    head_x, head_y, head_rot      head offset from the neck and tilt (deg)
    look                          pupil offset (-1..1, -1 = far left) ; look_y
    pupil                         pupil width 0.15 (slit) .. 1.0 (round, excited)
    blink                         0 open .. 1 closed ; happy (^ ^ eyes) 0..1
    ear_l, ear_r                  ear rotation (deg, + = back / flattened)
    mouth                         0 closed 'w' .. 1 wide open (yawn / meow)
    whisker                       whisker angle offset (deg)
    body_y, breath                body offset, breathing scale 0..1
    arm_l, arm_r                  sleeve swing (deg) ; paw_l, paw_r: (x, y) paw target offsets
    tail                          tail curl phase ; tail_amp
"""

import math

import numpy as np

from ink import (INK, Xf, edge_fur, ellipse, fill, fur, hexc, mix, outline, shade, shape, smooth, stroke_line,
                 tapered, wash)

POSE0 = dict(crosseyed=0.0, body_x=0.0, head_x=0.0, head_y=0.0, head_rot=0.0, look=0.0, look_y=0.0, pupil=0.35, blink=0.0, happy=0.0,
             ear_l=0.0, ear_r=0.0, mouth=0.0, whisker=0.0, body_y=0.0, breath=0.0, arm_l=0.0, arm_r=0.0,
             paw_l=(0.0, 0.0), paw_r=(0.0, 0.0), tail=0.0, tail_amp=1.0, blush=0.0)


# ------------------------------------------------------------------------------------------------ breeds
class Breed:
    def __init__(self, name, base, light=None, dark=None, pattern="solid", eye="#d9b04a", nose="#d98f8a",
                 face="round", ears="upright", ear_size=1.0, cheek=1.0, fluff=1.0, mask=None, patches=(),
                 tufts=False, ruff=False, hairless=False, seed=0):
        self.name = name
        self.base = hexc(base)
        self.light = hexc(light) if light else shade(self.base, 0.55)
        self.dark = hexc(dark) if dark else shade(self.base, -0.45)
        self.pattern, self.eye, self.nose = pattern, hexc(eye), hexc(nose)
        self.face, self.ears, self.ear_size, self.cheek, self.fluff = face, ears, ear_size, cheek, fluff
        self.mask = hexc(mask) if mask else None
        self.patches = [(hexc(c), x, y, r) for c, x, y, r in patches]
        self.tufts, self.ruff, self.hairless, self.seed = tufts, ruff, hairless, seed


# ------------------------------------------------------------------------------------------------ head
def _head_outline(b):
    """Face facing left (3/4). Returns control points of the head silhouette (without ears)."""
    k = b.cheek
    if b.face == "wedge":          # Siamese: narrower, longer muzzle
        return [(-8, -44), (22, -40), (42, -20), (44, 6), (32, 30), (4, 46), (-20, 46), (-40, 30), (-48, 8),
                (-44, -18), (-30, -36)]
    if b.face == "flat":           # Persian: round, full cheeks, short face
        return [(-6, -46), (28, -42), (50, -20), (54, 8), (42, 34), (10, 48), (-20, 48), (-48 * k, 36),
                (-60 * k, 12), (-50, -18), (-34, -38)]
    return [(-6, -44), (26, -40), (46, -20), (50, 6), (40, 30), (8, 44), (-18, 44), (-44 * k, 34), (-56 * k, 14),
            (-48, -14), (-34, -36)]


def _ear(canvas, b, side, rot, fold=False):
    """side 'far' (left, in front of face) or 'near' (right, behind the skull line)."""
    s = b.ear_size
    if side == "far":
        base, tip = [(-44, -26), (-14, -44)], (-40 * s - 6, -84 * s)
        pivot = (-28, -36)
    else:
        base, tip = [(6, -46), (36, -32)], (30 * s + 4, -82 * s)
        pivot = (22, -40)
    with Xf(canvas, pivot[0], pivot[1], rot):
        bx0, by0 = base[0][0] - pivot[0], base[0][1] - pivot[1]
        bx1, by1 = base[1][0] - pivot[0], base[1][1] - pivot[1]
        tx, ty = tip[0] - pivot[0], tip[1] - pivot[1]
        if fold:                   # Scottish fold: short, folded forward
            tx, ty = (bx0 + bx1) / 2 - 4, (by0 + by1) / 2 - 18
        outer = smooth([(bx0, by0), ((bx0 + tx) / 2 - 3, (by0 + ty) / 2), ('c', tx, ty),
                        ((bx1 + tx) / 2 + 3, (by1 + ty) / 2), (bx1, by1)], closed=True)
        ear_c = b.mask or (b.dark if b.pattern in ("tabby", "tuxedo") else b.base)
        shape(canvas, outer, ear_c, w=1.5)
        if not fold:
            inner = smooth([(bx0 * 0.7 + tx * 0.3 + 3, by0 * 0.7 + ty * 0.3), ('c', tx * 0.85 + (bx0 + bx1) * 0.075,
                            ty * 0.8 + (by0 + by1) * 0.1), (bx1 * 0.7 + tx * 0.3 - 3, by1 * 0.7 + ty * 0.3),
                            ((bx0 + bx1) / 2, (by0 + by1) / 2 - 3)], closed=True)
            fill(canvas, inner, mix(b.nose, (0.97, 0.9, 0.85), 0.35), 0.9)
            if b.tufts:
                for i in range(4):
                    tapered(canvas, [(tx * 0.9, ty * 0.9), (tx + (i - 1.5) * 3, ty - 10 - i * 2)], 1.6, 0.2, INK, 0.7)
            if not b.hairless:
                fur(canvas, inner, [(tx * 0.5 + (i - 3) * 3, ty * 0.45, -1.57 + (i - 3) * 0.15, 14) for i in range(7)],
                    (0.98, 0.96, 0.92), 0.8, 0.7)


def _eye(canvas, b, cx, cy, w, h, p, near):
    """Almond eye with a slit pupil; p = pose."""
    blink, happy = p["blink"], p["happy"]
    if happy > 0.5:
        stroke_line(canvas, [(cx - w, cy + 2), (cx, cy - h * 0.7), (cx + w, cy + 1)], 1.9)
        return
    eye = smooth([('c', cx - w, cy + 1), (cx - w * 0.2, cy - h), ('c', cx + w, cy - 2), (cx + w * 0.1, cy + h * 0.75)])
    fill(canvas, eye, b.eye)
    canvas.save()
    canvas.clipPath(eye, doAntiAlias=True)
    wash(canvas, eye, ellipse(cx, cy - h, w * 1.3, h * 0.6), shade(b.eye, -0.55), 0.6, 2.5)
    look = p["look"] + (p.get("crosseyed", 0.0) * (0.9 if near else -0.9))
    px = cx + max(-1.0, min(1.0, look)) * w * 0.45
    py = cy + p["look_y"] * h * 0.3
    pw = w * (0.14 + 0.52 * p["pupil"])
    fill(canvas, ellipse(px, py, pw, h * 0.92), (0.06, 0.05, 0.05))
    fill(canvas, ellipse(px - pw * 0.4 - 1.2, py - h * 0.38, 1.4 + w * 0.09, 1.4 + w * 0.09), (1, 1, 1), 0.95)
    if blink > 0.02:
        lid_y = cy - h + (1.9 * h) * min(1.0, blink)
        fill(canvas, smooth([(cx - w - 3, cy - h - 4), (cx + w + 3, cy - h - 4), (cx + w + 3, lid_y - 2),
                             (cx, lid_y + 1), (cx - w - 3, lid_y)]), b.mask or b.base)
    canvas.restore()
    outline(canvas, eye, 1.5)
    if blink > 0.02:
        lid_y = cy - h + (1.9 * h) * min(1.0, blink)
        stroke_line(canvas, [(cx - w, min(cy + 1, lid_y)), (cx, lid_y + 1), (cx + w, min(cy - 2, lid_y - 1))], 1.5)


def draw_head(canvas, b, p, hat=None):
    rot_far = p["ear_l"]
    rot_near = p["ear_r"]
    fold = b.ears == "fold"
    # ears and ruff behind the head
    _ear(canvas, b, "near", rot_near, fold)
    if b.ruff and not p.get("collar", True):   # Maine coon ruff (hidden under a collar)
        ruff = smooth([(-50, 22), (-30, 52), (0, 60), (36, 48), (52, 24), (48, 58), (20, 78), (-16, 80), (-46, 62)])
        fill(canvas, ruff, b.light)
        fur(canvas, ruff, edge_fur(ruff, 60, 12, seed=b.seed + 3), shade(b.light, -0.3), 0.6, 0.8)
        fur(canvas, None, edge_fur(ruff, 40, 9, seed=b.seed + 4, inward=False, start=0.3, end=0.9),
            shade(b.light, -0.2), 0.55, 0.7)
        outline(canvas, ruff, 1.2, a=0.5)
    pts = _head_outline(b)
    head = smooth(pts)
    face_c = b.base
    fill(canvas, head, face_c)
    # coat pattern inside the head
    canvas.save()
    canvas.clipPath(head, doAntiAlias=True)
    if b.mask is not None:          # pointed coat: dark mask around the muzzle
        wash(canvas, head, ellipse(-18, 14, 34, 30), b.mask, 0.95, 9.0)
    if b.pattern == "tabby":
        for i, (x, y) in enumerate([(-18, -40), (-6, -42), (6, -40)]):
            tapered(canvas, [(x, y - 6), (x + 1, y + 10), (x + 3, y + 22)], 4.5, 0.6, b.dark, 0.85)
        for y in (0, 10):
            tapered(canvas, [(50, y - 6), (34, y), (24, y + 6)], 4.0, 0.5, b.dark, 0.8)
            tapered(canvas, [(-56, y - 2), (-46, y + 2), (-40, y + 8)], 3.5, 0.5, b.dark, 0.8)
    for c, x, y, r in b.patches:
        rr = np.random.default_rng(b.seed * 131 + abs(int(x)) * 7 + abs(int(y)))
        blob = smooth([(x + r * math.cos(a) * (0.8 + 0.35 * rr.random()), y + r * math.sin(a) * (0.8 + 0.35 * rr.random()))
                       for a in np.linspace(0, 2 * math.pi, 9)[:-1]])
        fill(canvas, blob, c)
        fur(canvas, blob, edge_fur(blob, 30, 6, seed=b.seed + 9), b.light, 0.5, 0.6)
    if b.pattern == "tuxedo":
        fill(canvas, smooth([(-40, 4), (-22, -6), (-4, 6), (4, 34), (-10, 52), (-38, 44)]), b.light)
    # light muzzle + chin
    muzzle_c = b.light if b.mask is None else mix(b.mask, b.light, 0.25)
    wash(canvas, head, ellipse(-18, 26, 26, 18), muzzle_c, 0.9, 6.0)
    # cheek shading
    wash(canvas, head, ellipse(36, 10, 22, 34), shade(face_c, -0.25), 0.35, 12.0)
    # interior hair strokes radiating from the muzzle (si mao)
    if not b.hairless:
        rr = np.random.default_rng(b.seed + 77)
        light_s, dark_s = [], []
        for i in range(int(110 * b.fluff)):
            a = rr.uniform(0, 2 * math.pi)
            rad = rr.uniform(16, 58)
            x, y = -20 + math.cos(a) * rad * 1.1, 14 + math.sin(a) * rad * 0.95
            (light_s if i % 3 else dark_s).append((x, y, a + rr.normal(0, 0.2), rr.uniform(5, 10)))
        fur(canvas, None, light_s, shade(face_c, 0.45), 0.35, 0.6)
        fur(canvas, None, dark_s, shade(face_c, -0.35), 0.3, 0.6)
    canvas.restore()
    # fur strokes along the silhouette
    if not b.hairless:
        fur(canvas, head, edge_fur(head, int(70 * b.fluff), 9 * b.fluff, seed=b.seed), shade(face_c, -0.35), 0.55, 0.7)
        fur(canvas, None, edge_fur(head, int(34 * b.fluff), 7 * b.fluff, seed=b.seed + 1, inward=False, start=0.35,
                                    end=0.95), shade(face_c, -0.2), 0.5, 0.7)
    else:                           # sphynx wrinkles
        for y in (-34, -28, -22):
            stroke_line(canvas, [(-26, y), (-12, y - 3), (4, y)], 1.0, INK, 0.45)
    outline(canvas, head, 1.8)
    if hat is not None:             # a hat sits on the skull, between the ears
        hat()
    # far ear in front of the skull line
    _ear(canvas, b, "far", rot_far, fold)
    # eyes, nose, mouth, whiskers
    _eye(canvas, b, -36, -2, 8.5, 8.5, p, near=False)
    _eye(canvas, b, -1, -4, 12, 11, p, near=True)
    nose = smooth([('c', -30, 12), ('c', -16, 11), (-22, 19)])
    shape(canvas, nose, b.nose, w=1.3)
    m = p["mouth"]
    if m < 0.15:
        stroke_line(canvas, [(-22, 19), (-22, 23), (-28, 27), (-33, 24)], 1.4)
        stroke_line(canvas, [(-22, 23), (-16, 27), (-11, 24)], 1.4)
    else:
        mouth = smooth([(-32, 24), (-22, 22), (-12, 24), (-16, 24 + 16 * m), (-22, 26 + 20 * m), (-28, 24 + 16 * m)])
        shape(canvas, mouth, (0.55, 0.16, 0.17), w=1.4)
        fill(canvas, ellipse(-22, 26 + 14 * m, 5, 3 + 3 * m), (0.9, 0.5, 0.52))
    wa = math.radians(p["whisker"])
    for i, (dy, ln) in enumerate(((-2, 62), (4, 66), (10, 58))):
        a0 = math.radians(-8 + i * 9) + wa
        x0, y0 = -40, 20 + dy * 0.4
        stroke_line(canvas, [(x0, y0), (x0 - ln * 0.5 * math.cos(a0), y0 + ln * 0.5 * math.sin(a0) - 3),
                             (x0 - ln * math.cos(a0), y0 + ln * math.sin(a0) + 2)], 0.9, INK, 0.75)
        stroke_line(canvas, [(-6, y0), (-6 + ln * 0.45 * math.cos(a0), y0 + ln * 0.45 * math.sin(a0) - 2),
                             (-6 + ln * 0.85 * math.cos(a0), y0 + ln * 0.85 * math.sin(a0) + 3)], 0.9, INK, 0.6)
    if p["blush"] > 0:
        fill(canvas, ellipse(-4, 20, 10, 5), (0.95, 0.5, 0.5), 0.35 * p["blush"])
