#!/usr/bin/env python3
"""
src/post/titles.py — calligraphic title cards for Duel in the Silver Grass (original work).

Renders every entry of config.TITLES as a straight-alpha RGBA PNG sequence at delivery
resolution (config.DELIVERY_X x DELIVERY_Y) into  out/titles/<id>/00001.png ...
(numbered relative to the title's first frame, one PNG per frame of its inclusive range).

Styles (config.TITLES[*]['style']):
  epigraph  centred Kaiti line, per-glyph staggered fade + slow upward drift; the small grey dateline
            arrives with the last glyph
  main      huge Xingkai calligraphy written glyph after glyph (each glyph's strokes follow an approximate
            writing order: left radical before right part, trailing dots last), ink feathering + warm glow,
            cinnabar seal (the glyph of 'Saku') that stamps in with a tiny scale bounce ON the music cue 'title' as the audio
            lane resolves it (out/events.json -> config), optional tracked subtitle, soft defocus fade-out
  name      lower-third character card: name slides in, tapered dry-brush stroke, small epithet (the stroke
            and the epithet arrive together)
  act       vertical act card in the upper right third: the 'Act One/Two/Three' column (read first), then the act glyph
            (Blade / Fire / Thunder) as a large IVORY calligraphic accent with a soft glow tinted to the act's light,
            a small cinnabar seal under the column; brush-revealed top -> bottom. (No red brush kanji:
            that is a game-UI motif on the IP deny-list — red appears only as a small seal.)
  end       the 'End' glyph written in, seal, small Kaiti credit line in the lower letterbox bar, fade out

Every text layer sits on a soft dark shadow + block backdrop for legibility over bright sunset frames; all
text stays inside the 2.35:1 picture (y PIC_Y0..PIC_Y1) except the end credit.

Rendering is atomic and locked: each card is rendered into out/titles/<id>.tmp/ and swapped into place only
when complete, under an exclusive lock (out/titles/.lock), so an assembler never reads a half-written card
(assemble.py hard-links its frames while holding the same lock). A card re-renders automatically when its
config entry, this file, the fonts or its resolved music cue change.

Usage (.venv python):
  python src/post/titles.py                     # render all titles (skips up-to-date ones)
  python src/post/titles.py --force             # re-render everything
  python src/post/titles.py --only main_title,act1
  python src/post/titles.py --check-fonts       # glyph coverage / tofu check only
  python src/post/titles.py --only act2 --frames 20,40 --out /tmp/x   # a few local frames (1-based)
Library:
  ensure_titles(ids=None, force=False, jobs=None) -> {id: dir}
  snapshot_titles(ids, dest_dir) -> {id: dir}     (lock + ensure + hard-link copy, used by assemble.py)
Outputs besides the PNGs: out/titles/timeline.json — per card the legible window, the seal impact frames and
the cue they follow, plus "sound_cues" (seal stamps) the audio lane can place a sound on.
"""
from __future__ import annotations

import argparse
import contextlib
import functools
import hashlib
import json
import math
import os
import shutil
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
for _p in (os.path.join(ROOT, "src", "common"), HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import config  # noqa: E402
import cues as CUES  # noqa: E402
import procutil  # noqa: E402

W, H = config.DELIVERY_X, config.DELIVERY_Y
PIC_H, PIC_Y0 = config.letterbox(W, H)                     # 816, 132
PIC_Y1 = PIC_Y0 + PIC_H                                    # 948
LAYOUT_REF = (1920, 1080)      # the delivery size the layout, type sizes and offsets below are authored in (px)
STAMP_NAME = ".stamp.json"
LOCK_NAME = ".lock"
RENDER_VERSION = 10


def warn(msg):
    print(f"[titles] WARNING {msg}", file=sys.stderr, flush=True)


# ============================================================================ palette (sRGB 0..1)
def _hex(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], np.float32)


IVORY = _hex("#F2EBDD")        # main text: warm paper white
IVORY_HOT = _hex("#FFF6E6")    # fresh-ink sheen at the writing front
SUB = _hex("#D9D1C3")          # subtitles
EPITHET = _hex("#E9E2D5")      # small epithets (a touch dimmer than the name, still legible on bright sky)
GREY = _hex("#A39D94")         # epigraph dateline / credits
SHADOW = _hex("#000000")       # legibility shadow (pure black: invisible over black frames)
GLOW_WARM = _hex("#FFCF96")
SEAL_RED = _hex("#B3261B")     # cinnabar seal paste (the only red in the titles)

ACT_GLOW = {                   # soft glow tint of the ivory act glyph (matches the env states)
    "act1": _hex("#FFC58A"),   # dusk gold
    "act2": _hex("#FF9E62"),   # fire amber
    "act3": _hex("#A9C8FF"),   # storm blue-white
}

# ============================================================================ fonts
FACES = {
    "xingkai": (config.FONT_CALLIGRAPHY, "Xingkai SC", "Bold"),
    "xingkai_light": (config.FONT_CALLIGRAPHY, "Xingkai SC", "Light"),
    "weibei": (config.FONT_WEIBEI, "Weibei SC", "Bold"),
    "kaiti": (config.FONT_KAITI, "Kaiti SC", "Regular"),
    "kaiti_bold": (config.FONT_KAITI, "Kaiti SC", "Bold"),
    "song": (config.FONT_SONG, "Songti SC", "Regular"),
    "song_light": (config.FONT_SONG, "Songti SC", "Light"),
}
# original seal glyphs: the name of our shinobi (config.TITLES 'name_shinobi', 朔) = the film's "signature"
SHINOBI_GLYPH = next((t["text"] for t in config.TITLES if t["id"] == "name_shinobi"), "朔")[:1]
SEAL_GLYPH = {"main": SHINOBI_GLYPH, "end": SHINOBI_GLYPH}
SEAL_FACE = "weibei"

_face_idx_cache: dict = {}
_font_cache: dict = {}


def _face_index(path, family, style):
    """Index of the face (family, style) in a font file (a .ttc holds several). Another font file (e.g. a Linux /
    Windows font set in [fonts]) falls back to its first face of the same style, then to face 0."""
    key = (path, family, style)
    if key not in _face_idx_cache:
        names = []
        for idx in range(32):
            try:
                f = ImageFont.truetype(path, 20, index=idx)
            except OSError:
                break
            names.append(f.getname())
        found = next((i for i, n in enumerate(names) if n == (family, style)), None)
        if found is None:
            found = next((i for i, n in enumerate(names) if n[1] == style), 0 if names else None)
        if found is None:
            raise RuntimeError(f"font face {family} {style}: no usable font file ({path!r}); set it in [fonts] "
                               f"(film.local.toml) or $SILVERGRASS_FONTS_<ROLE>")
        _face_idx_cache[key] = found
    return _face_idx_cache[key]


def get_font(face, size):
    key = (face, int(size))
    if key not in _font_cache:
        path, fam, sty = FACES[face]
        _font_cache[key] = ImageFont.truetype(path, int(size), index=_face_index(path, fam, sty),
                                              layout_engine=ImageFont.Layout.BASIC)
    return _font_cache[key]


def act_seal_glyph(spec):
    lay = LAYOUT.get(spec["id"], {})
    return lay.get("seal_glyph") or (spec.get("sub", "").replace(" ", "")[:1] or SEAL_GLYPH["main"])


def title_face_usage():
    """(face, text) pairs actually rendered, for the glyph-coverage check."""
    use = []
    for t in config.TITLES:
        st = t["style"]
        if st == "epigraph":
            use += [(EPI_FACE, t["text"]), (EPI_SUB_FACE, t["sub"])]
        elif st == "main":
            use += [(MAIN_FACE, t["text"]), (MAIN_SUB_FACE, t["sub"]), (SEAL_FACE, SEAL_GLYPH["main"])]
        elif st == "name":
            use += [(NAME_FACE, t["text"]), (NAME_SUB_FACE, t["sub"])]
        elif st == "act":
            use += [(ACT_FACE, t["text"]), (ACT_ACCENT_FACE, t["sub"])]
            if LAYOUT.get(t["id"], {}).get("seal", True):
                use += [(SEAL_FACE, act_seal_glyph(t))]
        elif st == "end":
            use += [(END_FACE, t["text"]), (END_CREDIT_FACE, t["sub"]), (SEAL_FACE, SEAL_GLYPH["end"])]
    return use


def verify_fonts(verbose=True):
    """Every glyph we draw must exist in the face (cmap) and must not rasterise as .notdef / empty."""
    from fontTools.ttLib import TTFont
    problems = []
    cmaps = {}
    for face, text in title_face_usage():
        path, fam, sty = FACES[face]
        idx = _face_index(path, fam, sty)
        if (path, idx) not in cmaps:
            tt = (TTFont(path, fontNumber=idx, lazy=True) if path.lower().endswith((".ttc", ".otc"))
                  else TTFont(path, lazy=True))
            cmaps[(path, idx)] = tt.getBestCmap()
        cmap = cmaps[(path, idx)]
        f = get_font(face, 96)
        notdef = np.asarray(f.getmask("\U0010FFFD"), np.uint8)
        for ch in sorted(set(text) - {" "}):
            if ord(ch) not in cmap:
                problems.append(f"{face}: U+{ord(ch):04X} {ch} missing from cmap")
                continue
            m = np.asarray(f.getmask(ch), np.uint8)
            if m.size == 0 or m.max() == 0:
                problems.append(f"{face}: {ch} renders empty")
            elif m.shape == notdef.shape and np.array_equal(m, notdef):
                problems.append(f"{face}: {ch} renders as .notdef (tofu)")
        if verbose:
            used = f.getname()
            note = "" if used == (fam, sty) else f"  (fallback face: {used[0]} {used[1]})"
            print(f"  font {face:14s} {fam} {sty:8s} idx={idx}  glyphs ok: {''.join(sorted(set(text) - {' '}))}{note}")
    if problems:
        raise RuntimeError("font check failed:\n  " + "\n  ".join(problems))
    return True


# ============================================================================ small math helpers
def clamp01(x):
    return min(1.0, max(0.0, float(x)))


def lin(t, a, b):
    return clamp01((t - a) / float(b - a)) if b != a else float(t >= b)


def ease_out_cubic(x):
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def ease_out_quart(x):
    x = clamp01(x)
    return 1 - (1 - x) ** 4


def ease_in_out_sine(x):
    x = clamp01(x)
    return 0.5 - 0.5 * math.cos(math.pi * x)


def ease_in_cubic(x):
    x = clamp01(x)
    return x ** 3


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def seed_of(s):
    return int(hashlib.sha1(s.encode()).hexdigest()[:8], 16)


def noise2(shape, cell, rng, aniso=(1.0, 1.0)):
    """Smooth band-limited noise (unit std): bicubic-upsampled Gaussian lattice.
    aniso=(ky, kx) stretches the cell per axis (e.g. (1, 8) -> horizontal fibres)."""
    h, w = shape
    cy, cx = max(cell * aniso[0], 1.0), max(cell * aniso[1], 1.0)
    gh, gw = int(math.ceil(h / cy)) + 4, int(math.ceil(w / cx)) + 4
    g = rng.standard_normal((gh, gw)).astype(np.float32)
    im = Image.fromarray(g).resize((int(round(gw * cx)), int(round(gh * cy))), Image.BICUBIC)
    a = np.asarray(im, np.float32)
    oy, ox = int(cy * 1.5), int(cx * 1.5)
    a = a[oy:oy + h, ox:ox + w]
    return (a - a.mean()) / (a.std() + 1e-6)


def fbm(shape, cell, rng, octaves=4, persistence=0.5, aniso=(1.0, 1.0)):
    acc = np.zeros(shape, np.float32)
    amp, tot = 1.0, 0.0
    for k in range(octaves):
        acc += amp * noise2(shape, max(cell / (2 ** k), 1.0), rng, aniso)
        tot += amp * amp
        amp *= persistence
    return acc / math.sqrt(tot)


def blur(a, sigma):
    """Gaussian blur; large radii are computed on a decimated copy (fast, visually identical)."""
    if sigma <= 0.05:
        return a
    if sigma < 5.0:
        return ndimage.gaussian_filter(a, sigma, mode="constant", truncate=3.5)
    f = max(2, int(sigma // 2.5))
    h, w = a.shape
    hs, ws = max(1, (h + f - 1) // f), max(1, (w + f - 1) // f)
    small = np.asarray(Image.fromarray(np.ascontiguousarray(a, np.float32)).resize((ws, hs), Image.BOX), np.float32)
    small = ndimage.gaussian_filter(small, sigma / f, mode="constant", truncate=3.5)
    return np.asarray(Image.fromarray(small).resize((w, h), Image.BICUBIC), np.float32)


def resize_f(a, w, h, resample=Image.BILINEAR):
    return np.asarray(Image.fromarray(np.ascontiguousarray(a, np.float32)).resize((int(w), int(h)), resample), np.float32)


def shift_sub(a, dy, dx):
    """Sub-pixel translate a float image (cubic spline, zero outside)."""
    if abs(dy) < 1e-3 and abs(dx) < 1e-3:
        return a
    out = ndimage.shift(a, (dy, dx), order=3, mode="constant", cval=0.0, prefilter=True)
    return np.clip(out, 0.0, None)


# ============================================================================ compositing
class Canvas:
    """Premultiplied float RGBA canvas covering a crop of the delivery frame."""

    def __init__(self, x0, y0, w, h):
        self.x0, self.y0, self.w, self.h = int(x0), int(y0), int(w), int(h)
        self.rgb = np.zeros((self.h, self.w, 3), np.float32)
        self.a = np.zeros((self.h, self.w), np.float32)

    def over(self, color, alpha):
        """Straight colour (3,) or (h,w,3) with coverage alpha (h,w) OVER the canvas."""
        alpha = np.clip(alpha, 0.0, 1.0).astype(np.float32)
        col = np.asarray(color, np.float32)
        inv = 1.0 - alpha
        if col.ndim == 1:
            self.rgb = col[None, None, :] * alpha[..., None] + self.rgb * inv[..., None]
        else:
            self.rgb = col * alpha[..., None] + self.rgb * inv[..., None]
        self.a = alpha + self.a * inv

    def over_premult(self, prgb, alpha, x, y):
        """Composite a small premultiplied patch whose top-left is at canvas pixel (x, y)."""
        h, w = alpha.shape
        cx0, cy0 = max(0, x), max(0, y)
        cx1, cy1 = min(self.w, x + w), min(self.h, y + h)
        if cx1 <= cx0 or cy1 <= cy0:
            return
        sx0, sy0 = cx0 - x, cy0 - y
        pa = alpha[sy0:sy0 + (cy1 - cy0), sx0:sx0 + (cx1 - cx0)]
        pc = prgb[sy0:sy0 + (cy1 - cy0), sx0:sx0 + (cx1 - cx0)]
        inv = 1.0 - pa
        self.rgb[cy0:cy1, cx0:cx1] = pc + self.rgb[cy0:cy1, cx0:cx1] * inv[..., None]
        self.a[cy0:cy1, cx0:cx1] = pa + self.a[cy0:cy1, cx0:cx1] * inv

    def multiply_alpha(self, k):
        self.rgb *= k
        self.a *= k

    def transform(self, dy=0.0, dx=0.0, sigma=0.0):
        """Whole-canvas sub-pixel drift and/or defocus (done on premultiplied data)."""
        if sigma > 0.05:
            self.rgb = np.stack([blur(self.rgb[..., c], sigma) for c in range(3)], -1)
            self.a = blur(self.a, sigma)
        if abs(dy) > 1e-3 or abs(dx) > 1e-3:
            self.rgb = np.stack([shift_sub(self.rgb[..., c], dy, dx) for c in range(3)], -1)
            self.a = shift_sub(self.a, dy, dx)
        self.a = np.clip(self.a, 0.0, 1.0)
        self.rgb = np.minimum(self.rgb, self.a[..., None])

    def to_frame(self, clip_y=(0, H)):
        """Full delivery-size straight-alpha RGBA uint8 frame."""
        a = np.clip(self.a, 0.0, 1.0)
        rgb = np.where(a[..., None] > 1e-5, self.rgb / np.maximum(a[..., None], 1e-5), 0.0)
        rgba = np.concatenate([np.clip(rgb, 0, 1), a[..., None]], -1)
        out = np.zeros((H, W, 4), np.float32)
        fx0, fy0 = max(0, self.x0), max(0, self.y0)
        fx1, fy1 = min(W, self.x0 + self.w), min(H, self.y0 + self.h)
        out[fy0:fy1, fx0:fx1] = rgba[fy0 - self.y0:fy1 - self.y0, fx0 - self.x0:fx1 - self.x0]
        y0c, y1c = clip_y
        out[:y0c] = 0.0
        out[y1c:] = 0.0
        q = np.round(out * 255.0).astype(np.uint8)
        q[..., :3][q[..., 3] == 0] = 0
        return q


# ============================================================================ typesetting
PUNCT_HALF = set("，。、；：！？）」』》")


def is_cjk(ch):
    o = ord(ch)
    return (0x2E80 <= o <= 0x9FFF) or (0xF900 <= o <= 0xFAFF) or (0x3000 <= o <= 0x303F) or (0xFF00 <= o <= 0xFFEF)


def glyph_ink(font, ch):
    """Rasterise one glyph -> (mask float32 0..1, ox, oy): top-left of mask relative to the pen on the baseline."""
    l, t, r, b = font.getbbox(ch, anchor="ls")
    pad = 3
    w, h = max(1, r - l + 2 * pad), max(1, b - t + 2 * pad)
    im = Image.new("L", (w, h), 0)
    ImageDraw.Draw(im).text((pad - l, pad - t), ch, font=font, fill=255, anchor="ls")
    return np.asarray(im, np.float32) / 255.0, l - pad, t - pad


class Glyph:
    __slots__ = ("ch", "mask", "x", "y", "index")

    def __init__(self, ch, mask, x, y, index=0):
        self.ch, self.mask, self.x, self.y, self.index = ch, mask, float(x), float(y), index

    @property
    def w(self):
        return self.mask.shape[1]

    @property
    def h(self):
        return self.mask.shape[0]


def cjk_axis(face, size):
    """y of the ideographic em-box centre relative to the baseline (negative = above)."""
    f = get_font(face, size)
    l, t, r, b = f.getbbox("国", anchor="ls")
    return (t + b) / 2.0


def _kind(ch):
    if ch == " ":
        return "space"
    if ch in "·・":
        return "dot"
    if ch in PUNCT_HALF:
        return "punct"
    return "cjk" if is_cjk(ch) else "latin"


def set_line(text, face, size, tracking=0.0, space=None, latin_face=None, latin_tracking=0.03,
             dot_cell=0.9, punct_tracking=0.05, dot_space=0.35):
    """Horizontal setting on a baseline at y=0, pen starting at x=0. Returns (glyphs, advance_width).
    Spacing model: `tracking` (em) is inserted only *between* two adjacent visible glyphs; closing
    punctuation is squeezed to a half em and hugs the glyph before it (punct_tracking) while carrying
    the full tracking after it; spaces and the centred interpunct cell have fixed widths, so ' · ' is
    exactly symmetric (spaces touching a dot use `dot_space`); a word space defaults to tracking + 0.5 em
    so it still reads as a break in widely tracked lines; Latin runs keep natural advances."""
    if space is None:
        space = tracking + 0.5
    font = get_font(face, size)
    lfont = get_font(latin_face, size) if latin_face else font
    axis = cjk_axis(face, size)
    kinds = [_kind(c) for c in text]
    glyphs, pen = [], 0.0
    for i, ch in enumerate(text):
        k = kinds[i]
        nxt = kinds[i + 1] if i + 1 < len(text) else None
        if k == "space":
            j0, j1 = i - 1, i + 1
            while j0 >= 0 and kinds[j0] == "space":
                j0 -= 1
            while j1 < len(text) and kinds[j1] == "space":
                j1 += 1
            near_dot = (j0 >= 0 and kinds[j0] == "dot") or (j1 < len(text) and kinds[j1] == "dot")
            pen += (dot_space if (near_dot and dot_space is not None) else space) * size
            continue
        if k == "dot":
            m, _, _ = glyph_ink(font, "·")
            cell = dot_cell * size
            glyphs.append(Glyph(ch, m, pen + cell / 2 - m.shape[1] / 2, axis - m.shape[0] / 2, len(glyphs)))
            pen += cell
            continue
        if k in ("cjk", "punct"):
            m, ox, oy = glyph_ink(font, ch)
            glyphs.append(Glyph(ch, m, pen + ox, oy, len(glyphs)))
            pen += font.getlength(ch) * (0.5 if k == "punct" else 1.0)
        else:
            m, ox, oy = glyph_ink(lfont, ch)
            glyphs.append(Glyph(ch, m, pen + ox, oy, len(glyphs)))
            pen += lfont.getlength(ch)
        if nxt is None or nxt in ("space", "dot"):
            continue
        if nxt == "punct":
            pen += punct_tracking * size
        elif k == "latin" and nxt == "latin":
            pen += latin_tracking * size
        else:
            pen += tracking * size
    return glyphs, pen


def set_optical(text, face, size, gap=0.06, scales=None, yoffs=None):
    """Display setting for calligraphy: glyphs placed by their ink boxes with a constant optical gap
    (em), ink-centred on a common horizontal axis at y=0. Returns glyph list (pen origin x=0)."""
    glyphs, x = [], 0.0
    for k, ch in enumerate(text):
        sc = scales[k % len(scales)] if scales else 1.0
        m = trim_mask(glyph_ink(get_font(face, round(size * sc)), ch)[0])
        dy = yoffs[k % len(yoffs)] if yoffs else 0.0
        glyphs.append(Glyph(ch, m, x, -m.shape[0] / 2.0 + dy, k))
        x += m.shape[1] + gap * size
    return glyphs


def set_column(text, face, size, tracking=0.0):
    """Vertical setting: each glyph ink-centred in a square cell of (1+tracking) em, column axis x=0,
    top of first cell at y=0. Returns (glyphs, height)."""
    font = get_font(face, size)
    cell = size * (1.0 + tracking)
    glyphs = []
    for i, ch in enumerate(text):
        m, _, _ = glyph_ink(font, ch)
        glyphs.append(Glyph(ch, m, -m.shape[1] / 2.0, i * cell + size / 2.0 - m.shape[0] / 2.0, i))
    return glyphs, (len(text) - 1) * cell + size


def translate(glyphs, dx, dy):
    for g in glyphs:
        g.x += dx
        g.y += dy
    return glyphs


def ink_box(glyphs):
    if not glyphs:
        raise ValueError("ink_box of an empty glyph list")
    x0 = min(g.x for g in glyphs)
    y0 = min(g.y for g in glyphs)
    x1 = max(g.x + g.w for g in glyphs)
    y1 = max(g.y + g.h for g in glyphs)
    return x0, y0, x1, y1


def paste_max(dst, src, x, y):
    """Max-composite src into dst at (fractional) position; sub-pixel via cubic spline."""
    ix, iy = int(math.floor(x)), int(math.floor(y))
    fx, fy = x - ix, y - iy
    if fx > 1e-3 or fy > 1e-3:
        src = np.pad(src, 2)
        src = np.clip(ndimage.shift(src, (fy, fx), order=3, mode="constant", prefilter=True), 0.0, 1.0)
        ix -= 2
        iy -= 2
    h, w = src.shape
    X0, Y0 = max(0, ix), max(0, iy)
    X1, Y1 = min(dst.shape[1], ix + w), min(dst.shape[0], iy + h)
    if X1 <= X0 or Y1 <= Y0:
        return
    sub = src[Y0 - iy:Y1 - iy, X0 - ix:X1 - ix]
    np.maximum(dst[Y0:Y1, X0:X1], sub, out=dst[Y0:Y1, X0:X1])


def raster(glyphs, canvas, labels=False):
    """Integer-position raster of glyphs (delivery coords) into a canvas-sized mask (+ label map)."""
    M = np.zeros((canvas.h, canvas.w), np.float32)
    L = -np.ones((canvas.h, canvas.w), np.int16) if labels else None
    for g in glyphs:
        ix, iy = int(round(g.x)) - canvas.x0, int(round(g.y)) - canvas.y0
        h, w = g.mask.shape
        X0, Y0 = max(0, ix), max(0, iy)
        X1, Y1 = min(canvas.w, ix + w), min(canvas.h, iy + h)
        if X1 <= X0 or Y1 <= Y0:
            continue
        sub = g.mask[Y0 - iy:Y1 - iy, X0 - ix:X1 - ix]
        if labels:
            sel = (sub > 0.01) & (sub > M[Y0:Y1, X0:X1])
            L[Y0:Y1, X0:X1][sel] = g.index
        np.maximum(M[Y0:Y1, X0:X1], sub, out=M[Y0:Y1, X0:X1])
    return (M, L) if labels else M


# ============================================================================ ink reveal maps
_SQ2 = math.sqrt(2.0)


def _overlap(a0, a1, b0, b1):
    return max(0, min(a1, b1) - max(a0, b0))


def component_order(lab, n, override=None):
    """Writing order of a glyph's connected ink components (0-based label indices).
    Chinese stroke-order heuristics that survive calligraphic joins:
      * side-by-side parts (vertical overlap > 50 %, horizontal overlap < 35 %) go left -> right
        (e.g. a glyph's left component before its right-hand radical), everything else top -> bottom, then left -> right;
      * small trailing marks — a component under 20 % of the largest one, on the right half of the glyph
        and nested inside a bigger component's box (e.g. the final dot of a halberd radical, or a hooked tail) — come last.
    `override` (list of label indices, from LAYOUT[...]['comp_order'][char]) wins when given."""
    if n <= 1:
        return list(range(n))
    if override:
        order = [k for k in override if 0 <= k < n]
        return order + [k for k in range(n) if k not in order]
    hs, ws = lab.shape
    objs = ndimage.find_objects(lab)
    areas = ndimage.sum(np.ones(lab.shape, np.float32), lab, index=np.arange(1, n + 1))
    cms = ndimage.center_of_mass(np.ones(lab.shape, np.float32), lab, index=np.arange(1, n + 1))
    info = []
    for k, sl in enumerate(objs):
        info.append(dict(k=k, y0=sl[0].start, y1=sl[0].stop, x0=sl[1].start, x1=sl[1].stop,
                         cy=cms[k][0], cx=cms[k][1], area=float(areas[k])))
    amax = max(c["area"] for c in info)

    def nested(a, b):
        return (_overlap(a["x0"], a["x1"], b["x0"], b["x1"]) * _overlap(a["y0"], a["y1"], b["y0"], b["y1"])
                >= 0.8 * (a["x1"] - a["x0"]) * (a["y1"] - a["y0"]))

    late = [a for a in info if a["area"] < 0.2 * amax and a["cx"] > 0.55 * ws
            and any(nested(a, b) for b in info if b is not a and b["area"] > a["area"])]
    main = [a for a in info if a not in late]

    def cmp(a, b):
        ha, hb = a["y1"] - a["y0"], b["y1"] - b["y0"]
        wa, wb = a["x1"] - a["x0"], b["x1"] - b["x0"]
        vo = _overlap(a["y0"], a["y1"], b["y0"], b["y1"]) / max(1, min(ha, hb))
        ho = _overlap(a["x0"], a["x1"], b["x0"], b["x1"]) / max(1, min(wa, wb))
        if vo > 0.5 and ho < 0.35:
            return -1 if a["cx"] < b["cx"] else 1
        ka, kb = (a["y0"], a["x0"]), (b["y0"], b["x0"])
        return -1 if ka < kb else (1 if ka > kb else 0)

    main.sort(key=functools.cmp_to_key(cmp))
    late.sort(key=lambda c: (c["y0"], c["x0"]))
    return [c["k"] for c in main + late]


def stroke_analysis(mask, overlap=0.32, ds=2, comp_order=None):
    """Writing-order analysis of one glyph mask (independent of timing): ink flows along each connected
    stroke by geodesic distance from its upper-left end, strokes taken in component_order().
    Returns dict(Ts=full-res map in path units 0..total, total=path length, ds, n_components, order)."""
    h, w = mask.shape
    hs, ws = max(1, h // ds), max(1, w // ds)
    small = resize_f(mask, ws, hs, Image.BOX)
    b = small > 0.42
    lab, n = ndimage.label(b, structure=np.ones((3, 3), bool))
    if n == 0:
        return dict(Ts=np.zeros(mask.shape, np.float32), total=1.0, ds=ds, n_components=0, order=[])
    ys, xs = np.nonzero(b)
    idx = -np.ones(b.shape, np.int64)
    idx[ys, xs] = np.arange(len(ys))
    rows, cols, wts = [], [], []
    for dy, dx, wt in ((0, 1, 1.0), (1, 0, 1.0), (1, 1, _SQ2), (1, -1, _SQ2)):
        xa0, xa1 = max(0, -dx), ws - max(0, dx)          # p=(y,x) and q=(y+dy,x+dx) both inside
        a = idx[0:hs - dy, xa0:xa1]
        c = idx[dy:hs, xa0 + dx:xa1 + dx]
        sel = (a >= 0) & (c >= 0)
        rows.append(a[sel])
        cols.append(c[sel])
        wts.append(np.full(sel.sum(), wt))
    N = len(ys)
    G = coo_matrix((np.concatenate(wts), (np.concatenate(rows), np.concatenate(cols))), shape=(N, N)).tocsr()
    objs = ndimage.find_objects(lab)
    starts = []
    for k, sl in enumerate(objs, 1):
        cy, cx = np.nonzero(lab[sl] == k)
        cy = cy + sl[0].start
        cx = cx + sl[1].start
        j = int(np.argmin(cx * 1.0 + cy * 1.3))          # upper-left end of the stroke
        starts.append(idx[cy[j], cx[j]])
    dist = dijkstra(G, directed=False, indices=starts, min_only=True)
    D = np.zeros(b.shape, np.float32)
    D[ys, xs] = dist
    comp_len = np.asarray(ndimage.maximum(D, lab, index=np.arange(1, n + 1)), np.float32)
    ref = float(max(hs, ws))
    order = component_order(lab, n, comp_order)
    t, start_t = 0.0, np.zeros(n, np.float32)
    ends = []
    for k in order:
        L = max(float(comp_len[k]), 0.12 * ref)
        start_t[k] = t
        t += L * (1.0 - overlap)
        ends.append(start_t[k] + L)
    total = max(ends)
    Ts = np.zeros(b.shape, np.float32)
    Ts[ys, xs] = start_t[lab[ys, xs] - 1] + D[ys, xs]
    _, (iy, ix) = ndimage.distance_transform_edt(~b, return_indices=True)
    Ts = Ts[iy, ix]
    return dict(Ts=resize_f(Ts, w, h, Image.BILINEAR), total=float(total), ds=ds, n_components=int(n),
                order=[int(k) for k in order])


def stroke_times(an, t0, t1, rng, jitter=0.45, front_px=5.0, shutter=0.55):
    """Timed reveal map (frames) for a glyph analysed by stroke_analysis(): T and the front softness."""
    scale = (t1 - t0) / an["total"]
    T = t0 + an["Ts"] * scale
    shape = an["Ts"].shape
    T = T + (0.65 * noise2(shape, 7.0, rng) + 0.35 * noise2(shape, 2.2, rng)) * jitter
    soft = max(shutter, front_px / an["ds"] * scale)
    return T.astype(np.float32), float(soft)


def sequential_timings(lengths, t_start, t_end, next_at=0.85, weight=0.5):
    """Glyph after glyph: glyph k+1 starts when glyph k is `next_at` written; each glyph's duration grows with
    its ink-path length (weight 0 = equal durations). The whole run spans exactly [t_start, t_end]."""
    L = np.asarray(lengths, np.float64)
    if len(L) == 0:
        return []
    rel = (1.0 - weight) + weight * L / max(L.mean(), 1e-6)
    tot = next_at * rel[:-1].sum() + rel[-1]
    D = (t_end - t_start) / tot
    out, t = [], t_start
    for r in rel:
        out.append((t, t + r * D))
        t += next_at * r * D
    return out


def stroke_flow(M, sigma_t):
    """Local stroke direction from the mask's structure tensor (the along-stroke eigenvector), with its
    coherence (0 = isotropic blob / junction, 1 = clean straight stroke). Returns (flow (2,h,w) [dy,dx], coh)."""
    gy = ndimage.gaussian_filter(M, 1.0, order=(1, 0))
    gx = ndimage.gaussian_filter(M, 1.0, order=(0, 1))
    jxx = blur(gx * gx, sigma_t)
    jyy = blur(gy * gy, sigma_t)
    jxy = blur(gx * gy, sigma_t)
    phi = 0.5 * np.arctan2(2.0 * jxy, jxx - jyy)          # angle of the dominant gradient (stroke normal)
    flow = np.stack([np.cos(phi), -np.sin(phi)], 0).astype(np.float32)      # tangent = normal rotated 90 deg
    coh = np.sqrt((jxx - jyy) ** 2 + 4.0 * jxy ** 2) / (jxx + jyy + 1e-6)
    return flow, np.clip(coh, 0, 1).astype(np.float32)


def flow_streaks(flow, rng, length=9, cell=1.2):
    """Brush-fibre noise streaked along a direction field (short straight-line LIC), unit std."""
    _, h, w = flow.shape
    base = noise2((h, w), cell, rng)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    acc = np.zeros((h, w), np.float32)
    for k in range(-length, length + 1):
        acc += ndimage.map_coordinates(base, [yy + k * flow[0], xx + k * flow[1]], order=1, mode="reflect")
    acc -= acc.mean()
    return (acc / (acc.std() + 1e-6)).astype(np.float32)


def wipe_reveal_map(shape, box, t0, t1, rng, direction="down", jitter=0.03, fibre=0.015):
    """Directional brush wipe over box=(x0,y0,x1,y1) (canvas px) with a gently irregular, fibrous front.
    (Low jitter/fibre: at small sizes larger values break the front into specks.)"""
    h, w = shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    x0, y0, x1, y1 = box
    if direction == "down":
        d = (yy - y0) / max(1.0, y1 - y0)
        fib = noise2(shape, 2.5, rng, aniso=(6.0, 1.0))
    elif direction == "right":
        d = (xx - x0) / max(1.0, x1 - x0)
        fib = noise2(shape, 2.5, rng, aniso=(1.0, 6.0))
    else:
        raise ValueError(direction)
    d = d + jitter * fbm(shape, 24.0, rng, octaves=3) + fibre * fib
    return (t0 + (t1 - t0) * np.clip(d, -0.2, 1.2)).astype(np.float32)


def reveal(T, t, soft):
    return np.clip((t - T) / soft + 0.5, 0.0, 1.0)


# ============================================================================ procedural props
def make_seal(glyph, size, rng, ss=4, color=SEAL_RED):
    """Cinnabar intaglio (baiwen, "white text") seal: rough-edged square with the glyph carved out (transparent).
    Returns premultiplied (rgb, alpha) at supersampled resolution (size*ss)."""
    S = int(size * ss)
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    c = (S - 1) / 2.0
    half = S * 0.46
    r = S * 0.07
    qx, qy = np.abs(xx - c) - (half - r), np.abs(yy - c) - (half - r)
    d = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r
    d += fbm((S, S), S / 6.0, rng, octaves=3) * S * 0.010 + noise2((S, S), S / 40.0, rng) * S * 0.006
    square = smoothstep(ss * 0.9, -ss * 0.9, d)
    # carved glyph, stretched to fill the field like a seal carving
    f = get_font(SEAL_FACE, S)
    gm, _, _ = glyph_ink(f, glyph)
    ys, xs = np.nonzero(gm > 0.02)
    gm = gm[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    inner = int(S * 0.70)
    gm = resize_f(gm, inner, inner, Image.LANCZOS)
    gm = np.clip(gm, 0, 1)
    gm = ndimage.grey_dilation(gm, size=(max(1, ss * 2), max(1, ss * 2)))       # carved lines are bold
    gm = smoothstep(0.30, 0.70, blur(gm, ss * 0.6) + noise2(gm.shape, ss * 3.0, rng) * 0.10)
    G = np.zeros((S, S), np.float32)
    o = (S - inner) // 2
    G[o:o + inner, o:o + inner] = gm
    alpha = square * (1.0 - G)
    # paste texture: density variation + tiny voids where the paste did not transfer
    dens = 0.90 + 0.10 * fbm((S, S), S / 5.0, rng, octaves=4)
    voids = smoothstep(1.9, 2.6, fbm((S, S), ss * 3.5, rng, octaves=2)) * 0.85
    alpha = alpha * np.clip(dens, 0, 1) * (1.0 - voids)
    tone = 0.93 + 0.07 * noise2((S, S), S / 8.0, rng)
    rgb = np.clip(color[None, None, :] * tone[..., None], 0, 1) * alpha[..., None]
    return rgb.astype(np.float32), alpha.astype(np.float32)


def seal_patch(seal, scale, angle_deg, ss=4):
    """Scale/rotate the supersampled seal and reduce to screen resolution -> (prgb, alpha)."""
    rgb, a = seal
    S = a.shape[0]
    chans = [rgb[..., 0], rgb[..., 1], rgb[..., 2], a]
    out = []
    target = max(4, int(round(S / ss * scale * 1.25)))       # generous box for the rotated square
    for ch in chans:
        im = Image.fromarray(np.ascontiguousarray(ch))
        im = im.rotate(angle_deg, resample=Image.BICUBIC, expand=True)
        big = int(round(im.size[0] * scale / ss))
        big = max(2, big)
        im = im.resize((big, big), Image.LANCZOS)
        arr = np.zeros((target, target), np.float32)
        o = (target - big) // 2
        src = np.asarray(im, np.float32)
        if o >= 0:
            arr[o:o + big, o:o + big] = src
        else:
            arr = src[-o:-o + target, -o:-o + target]
        out.append(arr)
    a2 = np.clip(out[3], 0, 1)
    prgb = np.clip(np.stack(out[:3], -1), 0, None)
    prgb = np.minimum(prgb, a2[..., None])
    return prgb, a2


SEAL_SETTLE = 5.0          # frames after impact until the bounce has settled


def seal_anim(u):
    """Stamp motion for local frame u since the seal's move started (impact = u 2): (scale, alpha)."""
    keys = [(0.0, 1.55, 0.0), (1.0, 1.22, 0.75), (2.0, 0.955, 1.0), (3.5, 1.022, 1.0), (5.0, 0.994, 1.0),
            (7.0, 1.0, 1.0)]
    if u <= 0:
        return keys[0][1], 0.0
    for (u0, s0, a0), (u1, s1, a1) in zip(keys, keys[1:]):
        if u <= u1:
            k = ease_in_out_sine((u - u0) / (u1 - u0)) if u0 >= 2.0 else (u - u0) / (u1 - u0)
            return s0 + (s1 - s0) * k, a0 + (a1 - a0) * k
    return 1.0, 1.0


def draw_seal(cv, seal, seal_c, u, angle, shadow=0.35, spread=True):
    """Composite the stamping seal (u = frames since its move started; impact at u = 2)."""
    if u <= 0:
        return
    sc, sa = seal_anim(u)
    prgb, pa = seal_patch(seal, sc, angle)
    cx, cy = seal_c
    ph, pw = pa.shape
    px, py = int(round(cx - pw / 2)) - cv.x0, int(round(cy - ph / 2)) - cv.y0
    hit = clamp01(1.0 - (u - 2.0) / 7.0) if u >= 2.0 else 0.0
    if spread and hit > 0:                        # faint paste spread on impact
        sp = Canvas(0, 0, pw, ph)
        sp.over(SEAL_RED, blur(pa, 3.0) * 0.28 * hit)
        cv.over_premult(sp.rgb, sp.a, px, py)
    if shadow > 0:                                # contact shadow so the red reads on bright sky
        sh = blur(pa, 6.0) * shadow * sa
        cv.over_premult(np.zeros(pa.shape + (3,), np.float32), sh, px + 2, py + 3)
    cv.over_premult(prgb * sa, pa * sa, px, py)


def make_brush_stroke(length, thick, rng, ss=3):
    """Thin tapered horizontal dry-brush stroke (press at the left, fibrous tail to the right).
    Returns alpha mask (float32) at screen resolution, origin = left end of the centre line;
    also returns the centre-line y offset inside the mask."""
    L, T = length * ss, thick * ss
    pad = int(T * 3)
    h, w = int(T * 6), int(L + 2 * pad)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    u = (xx - pad) / L
    uc = np.clip(u, 0, 1)
    yc = h / 2.0 - np.sin(np.pi * uc) * T * 0.55 + (uc - 0.5) * T * 0.35
    prof = (0.62 + 0.38 * smoothstep(0.0, 0.05, uc)) * (1.0 - 0.9 * smoothstep(0.30, 1.0, uc) ** 1.15)
    prof *= 1.0 + 0.10 * np.exp(-((uc - 0.035) / 0.03) ** 2)        # small press nub at the entry
    half = 0.5 * T * prof
    d = np.abs(yy - yc) - half
    d = np.where(u < 0, np.hypot(xx - pad, yy - (h / 2.0 + T * -0.175)) - 0.5 * T * 0.62, d)
    d = np.where(u > 1, np.hypot(xx - pad - L, yy - yc) - 0.2 * ss, d)
    d += noise2((h, w), ss * 2.5, rng, aniso=(1.0, 5.0)) * ss * 0.35
    m = smoothstep(ss * 0.8, -ss * 0.8, d)
    fib = noise2((h, w), ss * 1.4, rng, aniso=(1.0, 26.0))
    dry = smoothstep(0.40, 1.0, uc) * 0.9
    m *= np.clip(1.0 - dry * smoothstep(-0.3, 0.5, fib), 0, 1)
    m *= 0.88 + 0.12 * noise2((h, w), ss * 1.2, rng, aniso=(1.0, 18.0)).clip(-1, 1)
    small = resize_f(np.clip(m, 0, 1), w // ss, h // ss, Image.BOX)
    return small, (h / 2.0) / ss, pad / ss


BACKDROP_REACH = 1.75     # super-gaussian exp(-(r^2)^1.5) is < 0.5/255 beyond this radius


def backdrop(canvas, cx, cy, rx, ry, power=1.5):
    """Soft super-gaussian ellipse (0..1) centred at delivery coords (cx, cy)."""
    yy, xx = np.mgrid[0:canvas.h, 0:canvas.w].astype(np.float32)
    xx += canvas.x0
    yy += canvas.y0
    r2 = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2
    return np.exp(-np.power(r2, power)).astype(np.float32)


def canvas_geom(content_box, margin, ellipses=(), clip=(0, 0, W, H)):
    """Crop rectangle (x0, y0, w, h) covering content+margin and the full reach of each backdrop
    ellipse (cx, cy, rx, ry), so no soft layer is ever cut by the crop edge."""
    x0, y0, x1, y1 = content_box
    x0, y0, x1, y1 = x0 - margin, y0 - margin, x1 + margin, y1 + margin
    for cx, cy, rx, ry in ellipses:
        x0, x1 = min(x0, cx - BACKDROP_REACH * rx), max(x1, cx + BACKDROP_REACH * rx)
        y0, y1 = min(y0, cy - BACKDROP_REACH * ry), max(y1, cy + BACKDROP_REACH * ry)
    X0, Y0 = int(math.floor(max(clip[0], x0))), int(math.floor(max(clip[1], y0)))
    X1, Y1 = int(math.ceil(min(clip[2], x1))), int(math.ceil(min(clip[3], y1)))
    return (X0, Y0, X1 - X0, Y1 - Y0)


def text_shadow(M, near_sigma, far_sigma, near_amt, far_amt, near_gain=2.2, far_gain=2.6):
    """Two-scale soft shadow alpha from a coverage mask (dilated-looking via gain)."""
    n = np.clip(blur(M, near_sigma) * near_gain, 0, 1) * near_amt
    f = np.clip(blur(M, far_sigma) * far_gain, 0, 1) * far_amt
    return 1.0 - (1.0 - n) * (1.0 - f)


# ============================================================================ title styles
EPI_FACE, EPI_SUB_FACE = "kaiti", "kaiti"
MAIN_FACE, MAIN_SUB_FACE = "xingkai", "kaiti"
NAME_FACE, NAME_SUB_FACE = "xingkai", "kaiti"
ACT_FACE, ACT_ACCENT_FACE = "kaiti", "xingkai"
END_FACE, END_CREDIT_FACE = "xingkai", "kaiti"

# Per-title layout overrides (delivery px) — tweak here after seeing the real renders.
#   act cards: cx = horizontal centre of the card group, cy = vertical centre of the accent glyph (sky band:
#   the glyph bottom stays above ~52 % of the picture height), accent_h = max accent ink height,
#   seal = small cinnabar seal under the column (seal_glyph defaults to the accent glyph), rule = hairline
#   under the column instead of the seal.
#   comp_order = {char: [component label indices]} overrides the automatic stroke order of a glyph.
LAYOUT = {
    "epigraph": dict(cy=518),
    "main_title": dict(cy=462),
    "name_shinobi": dict(x=178, base=792),
    "name_saint": dict(x=178, base=792),
    "act1": dict(cx=1532, cy=420, accent_h=236, seal=True),
    "act2": dict(cx=1532, cy=420, accent_h=236, seal=True),
    "act3": dict(cx=1532, cy=420, accent_h=236, seal=True),
    "end": dict(cy=506, credit_y=1014),
}

# Music cues a style follows (resolved like the audio lane does; missing cues fall back to the design timing).
STYLE_CUES = {"main": ["title"], "end": ["end_seal"]}


def trim_mask(m, pad=2):
    ys, xs = np.nonzero(m > 0.004)
    if len(ys) == 0:
        return m
    y0, y1 = max(0, ys.min() - pad), min(m.shape[0], ys.max() + 1 + pad)
    x0, x1 = max(0, xs.min() - pad), min(m.shape[1], xs.max() + 1 + pad)
    return m[y0:y1, x0:x1]


class Ink:
    """Precomputed 'written' calligraphy layer and its per-frame look (reveal, dry-brush front, fibres).
    timings: [(t0, t1)] per glyph, or window=(t_start, t_end) to write the glyphs one after another."""

    def __init__(self, glyphs, cv, rng, timings=None, window=None, next_at=0.85, overlap=0.32, bias_down=0.0,
                 comp_orders=None, jitter=0.45):
        comp_orders = comp_orders or {}
        ans = [stroke_analysis(g.mask, overlap, comp_order=comp_orders.get(g.ch)) for g in glyphs]
        if timings is None:
            timings = sequential_timings([a["total"] for a in ans], window[0], window[1], next_at)
        self.timings = [(float(a), float(b)) for a, b in timings]
        self.orders = {g.ch: a["order"] for g, a in zip(glyphs, ans)}
        M, L = raster(glyphs, cv, labels=True)
        T = np.full(M.shape, 1e6, np.float32)
        S = np.ones(M.shape, np.float32)
        for g, an, (t0, t1) in zip(glyphs, ans, self.timings):
            ix, iy = int(round(g.x)) - cv.x0, int(round(g.y)) - cv.y0
            Tk, sk = stroke_times(an, t0, t1, rng, jitter=jitter)
            if bias_down > 0:
                yy = np.linspace(0.0, 1.0, g.h, dtype=np.float32)[:, None]
                Tk = (1.0 - bias_down) * Tk + bias_down * (t0 + (t1 - t0) * yy)
            sel = L[iy:iy + g.h, ix:ix + g.w] == g.index
            T[iy:iy + g.h, ix:ix + g.w][sel] = Tk[sel]
            S[iy:iy + g.h, ix:ix + g.w][sel] = sk
        own = L >= 0
        if (~own).any() and own.any():
            _, (jy, jx) = ndimage.distance_transform_edt(~own, return_indices=True)
            T, S = T[jy, jx], S[jy, jx]
        self.M, self.T, self.S = M, T, S
        gh = max((g.h for g in glyphs), default=100)
        flow, coh = stroke_flow(M, max(2.0, gh / 36.0))
        # bristle fibres run along the stroke; where the direction is ambiguous (junctions) they fade out
        self.fib = flow_streaks(flow, rng) * smoothstep(0.15, 0.55, coh)
        self.tex = (0.985 + 0.015 * fbm(M.shape, 60.0, rng, octaves=3)).astype(np.float32)

    @property
    def end(self):
        return max(b for _, b in self.timings) if self.timings else 0.0

    def shade(self):
        """Ink body shading: faint paper/ink density variation + bristle marks (about +-1.5 % luma)."""
        return self.tex * (1.0 + 0.0075 * np.clip(self.fib, -1.5, 1.5))

    def at(self, t, front_tau=1.4, dry=0.55):
        R = reveal(self.T, t, self.S)
        front = np.exp(-np.maximum(t - self.T, 0.0) / front_tau) * (R > 0)
        MR = self.M * R * np.clip(1.0 - dry * front * smoothstep(-0.2, 1.1, self.fib), 0.0, 1.0)
        return MR, front


def has_text(s):
    return bool(s and s.strip())


def center_line(glyphs, cx, axis_y, face, size, hang=True):
    """Centre a set line on cx (ideographs only: trailing punctuation hangs) with its CJK axis at axis_y."""
    core = [g for g in glyphs if g.ch not in PUNCT_HALF] if hang else glyphs
    x0, _, x1, _ = ink_box(core or glyphs)
    translate(glyphs, cx - (x0 + x1) / 2, axis_y - cjk_axis(face, size))
    return glyphs


NOMINAL_FRAMES = {"epigraph": 78, "main": 105, "name": 65, "act": 80, "end": 83}
SHORT_CARD = 70            # cards shorter than this cap their fade-out at SHORT_FADE frames
SHORT_FADE = 11.0


class Title:
    """Base: a title spans spec['start']..spec['end'] (inclusive). Intro/outro timings are authored for
    NOMINAL_FRAMES[style] and scale down (ts) for shorter cards so the fully-legible hold keeps its share.
    Subclasses register every fade-in ramp in self.ramps (name -> local frame where it is complete) and the
    start of the fade-out in self.out_start; the legible window is derived from them."""
    clip_y = (PIC_Y0, PIC_Y1)

    def __init__(self, spec):
        self.spec = spec
        self.id = spec["id"]
        self.n = spec["end"] - spec["start"] + 1
        self.ts = min(1.0, max(0.5, self.n / float(NOMINAL_FRAMES.get(spec["style"], self.n))))
        self.rng = np.random.default_rng(seed_of(self.id))
        self.lay = LAYOUT.get(self.id, {})
        self.ramps = {}
        self.out_start = self.n - 1.0
        self.warnings = []
        self.cue_info = {}
        self.empty = not has_text(spec.get("text", "")) and not has_text(spec.get("sub", ""))
        if self.empty:
            self.cv = (0, 0, 1, 1)
        else:
            self.setup()

    def setup(self):
        raise NotImplementedError

    def render(self, i):
        raise NotImplementedError

    def warn(self, msg):
        self.warnings.append(msg)
        warn(f"{self.id}: {msg}")

    def out_len(self, nominal):
        """Fade-out length: nominal * ts, capped for short cards so the text holds longer."""
        L = nominal * self.ts
        if self.n < SHORT_CARD:
            L = min(L, SHORT_FADE)
        return max(6.0, L)

    def cue_local(self, name):
        """Resolved cue (absolute frame) for this card, from spec['_cues'] (set by effective_spec)."""
        c = (self.spec.get("_cues") or {}).get(name)
        return None if c is None else c.get("frame")

    def frame(self, i):
        if self.empty:
            return np.zeros((H, W, 4), np.uint8)
        return self.render(i).to_frame(self.clip_y)

    def _local_moments(self):
        """(fully legible from, legible until) as local 0-based frame indices."""
        return (max(self.ramps.values()) if self.ramps else 0.0), self.out_start

    def moments(self):
        """Key absolute frames of this card (for the editor / composer)."""
        a, b = self._local_moments()
        s = self.spec["start"]
        lf, lt = s + int(math.ceil(a - 1e-6)), s + int(math.floor(b + 1e-6))
        out = dict(start=s, end=self.spec["end"], legible_from=lf, legible_to=lt, legible_frames=max(0, lt - lf + 1),
                   time_scale=round(self.ts, 3), ramps={k: round(s + v, 1) for k, v in self.ramps.items()})
        if getattr(self, "seal_impact", None) is not None:
            out["seal_impact"] = s + int(round(self.seal_impact))
        if self.cue_info:
            out["cues"] = self.cue_info
        if self.warnings:
            out["warnings"] = self.warnings
        return out


class EpigraphTitle(Title):
    """The epigraph ("For a swordsman, a whole life goes to meet a single instant.") — per-glyph staggered fade with a slow upward drift; the small grey dateline
    arrives together with the last glyph."""

    FADE = 12.0     # per-glyph fade-in (frames, x ts)
    RISE = 14.0     # per-glyph settle (px rise easing out)

    def setup(self):
        s = self.spec
        self.size = 62
        cy = self.lay.get("cy", 518)
        gl = []
        if has_text(s["text"]):
            gl, _ = set_line(s["text"].strip(), EPI_FACE, self.size, tracking=0.30)
            center_line(gl, W / 2, cy, EPI_FACE, self.size)
        sg = []
        if has_text(s.get("sub")):
            sg, _ = set_line(s["sub"].strip(), EPI_SUB_FACE, 27, tracking=0.60)
            center_line(sg, W / 2, cy + (86 if gl else 0), EPI_SUB_FACE, 27, hang=False)
        self.glyphs, self.sub = gl, sg
        bx0, by0, bx1, by1 = ink_box(gl + sg)
        self.bd = ((bx0 + bx1) / 2, (by0 + by1) / 2, (bx1 - bx0) * 0.70, (by1 - by0) * 1.3 + 40)
        self.cv = canvas_geom((bx0, by0 - 20, bx1, by1), 80, [self.bd])
        ts = self.ts
        self.t_in = [ts * (3.0 + 1.3 * k) for k in range(len(gl))]
        self.t_sub = self.t_in[-1] if gl else ts * 6.0          # the dateline arrives with the last glyph
        if gl:
            self.ramps["line"] = self.t_in[-1] + ts * max(self.FADE, self.RISE)
        if sg:
            self.ramps["dateline"] = self.t_sub + ts * self.FADE
        self.fade_len = self.out_len(14)
        self.out_start = self.n - 1 - self.fade_len

    def render(self, i):
        n, ts = self.n, self.ts
        cv = Canvas(*self.cv)
        fade_out = 1.0 - ease_in_out_sine(lin(i, self.out_start, n - 1))
        drift = -11.0 * (i / (n - 1))
        M = np.zeros((cv.h, cv.w), np.float32)
        for g, t0 in zip(self.glyphs, self.t_in):
            a = ease_in_out_sine(lin(i, t0, t0 + self.FADE * ts))
            if a <= 0:
                continue
            rise = 7.0 * (1.0 - ease_out_cubic(lin(i, t0, t0 + self.RISE * ts)))
            paste_max(M, g.mask * a, g.x - cv.x0, g.y - cv.y0 + rise + drift)
        S = np.zeros_like(M)
        sa = ease_in_out_sine(lin(i, self.t_sub, self.t_sub + self.FADE * ts))
        if sa > 0:
            for g in self.sub:
                paste_max(S, g.mask * sa, g.x - cv.x0, g.y - cv.y0 + drift + 4.0 * (1 - sa))
        allm = np.maximum(M, S)
        cx, cy, rx, ry = self.bd
        cv.over(SHADOW, backdrop(cv, cx, cy + drift, rx, ry) * 0.22 * ease_in_out_sine(lin(i, 0, 20 * ts)))
        cv.over(SHADOW, text_shadow(allm, 3.0, 16.0, 0.55, 0.35))
        cv.over(IVORY, blur(M, 2.2) * 0.22)
        cv.over(IVORY, M)
        cv.over(GREY, S)
        cv.multiply_alpha(fade_out)
        return cv


class MainTitle(Title):
    """The main title — calligraphy written glyph after glyph, ink feathering + warm glow, seal stamp on the music
    cue 'title', optional tracked subtitle with hairlines, soft defocus fade-out."""

    MAX_W = 1300
    WRITE = 34.0          # nominal writing time of the whole title (frames, x ts)
    MIN_WRITE = 16.0      # never write faster than this (frames)

    def setup(self):
        s = self.spec
        text = s["text"].replace(" ", "")
        size = 240
        kw = dict(gap=0.05, scales=[1.0, 0.95, 1.0, 1.08], yoffs=[0.0, 8.0, -5.0, 3.0])
        glyphs = set_optical(text, MAIN_FACE, size, **kw)
        x0, y0, x1, y1 = ink_box(glyphs)
        if x1 - x0 > self.MAX_W:                          # long titles scale down to stay elegant
            size = int(size * self.MAX_W / (x1 - x0))
            kw["yoffs"] = [v * size / 240 for v in kw["yoffs"]]
            glyphs = set_optical(text, MAIN_FACE, size, **kw)
            x0, y0, x1, y1 = ink_box(glyphs)
        self.has_sub = has_text(s.get("sub"))
        cy = self.lay.get("cy", 462 if self.has_sub else 472)
        translate(glyphs, W / 2 - (x0 + x1) / 2, cy - (y0 + y1) / 2)
        self.glyphs = glyphs
        x0, y0, x1, y1 = ink_box(glyphs)
        self.sub = []
        bot = y1
        if self.has_sub:
            ss = 38
            sg, _ = set_line(s["sub"].strip(), MAIN_SUB_FACE, ss, tracking=0.30, dot_cell=0.95)
            self.sub_axis_y = y1 + 70
            center_line(sg, W / 2, self.sub_axis_y, MAIN_SUB_FACE, ss, hang=False)
            self.sub = sg
            self.sub_box = ink_box(sg)
            bot = self.sub_box[3]
        # seal: at the end of the line, sitting low beside the last glyph
        g = glyphs[-1]
        self.seal_size = int(round(92 * size / 240))
        self.seal_c = (x1 + 24 * size / 240 + self.seal_size / 2, g.y + g.h - self.seal_size / 2 - 18 * size / 240)
        ts = self.ts
        self.fade_len = self.out_len(19)
        self.out_start = self.n - 1 - self.fade_len
        w0 = 2.0 * ts
        write_end = w0 + self.WRITE * ts
        # --- the seal hits the paper (scale bottoms out, u = 2) on the music cue 'title' as the audio lane resolves it
        default_impact = write_end + 3.0
        latest = self.out_start - 12.0                    # the stamp must settle and hold before the fade-out
        earliest = w0 + self.MIN_WRITE + 3.0
        impact, src = default_impact, "design (no cue)"
        cue = (s.get("_cues") or {}).get("title")
        if cue and cue.get("frame") is not None:
            local = float(cue["frame"] - s["start"])
            src = f"cue 'title' = {cue['frame']} ({cue.get('source')})"
            if not (0 <= local <= self.n - 1):
                self.warn(f"music cue 'title' at frame {cue['frame']} lies outside the card "
                          f"{s['start']}-{s['end']}: seal keeps its design timing (local {default_impact:.1f})")
                src += " -> ignored (outside card)"
            else:
                impact = local
        if impact < earliest:
            self.warn(f"seal impact local {impact:.1f} is too early for the writing (min {earliest:.1f}); clamped")
            impact = earliest
            src += " -> clamped early"
        if impact > latest:
            self.warn(f"seal impact local {impact:.1f} is too late for the fade-out (max {latest:.1f}); clamped")
            impact = latest
            src += " -> clamped late"
        write_end = min(write_end, impact - 3.0)          # a quicker hand when the cue comes early
        self.seal_impact = impact
        self.seal_t = impact - 2.0
        self.cue_info = dict(seal=dict(frame=s["start"] + int(round(impact)), source=src))
        self.sub_t = self.seal_t + 5.0 * ts
        top = y0
        self.bd = (W / 2, (top + bot) / 2, (x1 - x0) * 0.62, (bot - top) * 0.62 + (0 if self.has_sub else 30))
        content = (x0, y0, max(x1, self.seal_c[0] + self.seal_size), bot)
        self.cv = canvas_geom(content, 150, [self.bd])
        cv = Canvas(*self.cv)
        self.ink = Ink(glyphs, cv, self.rng, window=(w0, write_end), next_at=0.85,
                       comp_orders=self.lay.get("comp_order"))
        self.seal = make_seal(SEAL_GLYPH["main"], self.seal_size, self.rng)
        self.bdm = backdrop(cv, *self.bd)
        self.ramps.update(written=self.ink.end + 1.0, seal=impact + SEAL_SETTLE)
        if self.has_sub:
            self.ramps.update(subtitle=self.sub_t + 18 * ts, hairlines=self.sub_t + 28 * ts)

    def render(self, i):
        n = self.n
        cv = Canvas(*self.cv)
        MR, front = self.ink.at(i)
        ts = self.ts
        fade_out = ease_in_out_sine(lin(i, self.out_start, n - 1))
        cv.over(SHADOW, self.bdm * 0.24 * ease_in_out_sine(lin(i, 0, 24 * ts)))
        cv.over(SHADOW, text_shadow(MR, 7.0, 34.0, 0.42, 0.40))
        cv.over(GLOW_WARM, np.clip(blur(MR, 14.0) * 1.1, 0, 1) * 0.20)
        bleed_sigma = 1.5 + 1.3 * clamp01((i - 3) / (40.0 * ts))
        cv.over(IVORY, np.clip(blur(MR, bleed_sigma) - MR, 0, 1) * 0.55)          # ink feathering
        shade = self.ink.shade()
        col = IVORY[None, None, :] * shade[..., None] + (IVORY_HOT - IVORY)[None, None, :] * (0.8 * front)[..., None]
        cv.over(np.clip(col, 0, 1), MR)
        draw_seal(cv, self.seal, self.seal_c, i - self.seal_t, -2.5)
        if self.has_sub:
            self._subtitle(cv, i)
        if fade_out > 0:
            cv.transform(dy=-7.0 * ease_in_cubic(fade_out), sigma=2.6 * fade_out)
            cv.multiply_alpha(1.0 - fade_out)
        return cv

    def _subtitle(self, cv, i):
        t0, ts = self.sub_t, self.ts
        sa = ease_in_out_sine(lin(i, t0, t0 + 18 * ts))
        if sa <= 0:
            return
        S = np.zeros((cv.h, cv.w), np.float32)
        spread = 1.0 + 0.10 * (1.0 - ease_out_cubic(lin(i, t0, t0 + 26 * ts)))
        cx = W / 2
        for g in self.sub:
            gx = cx + (g.x + g.w / 2 - cx) * spread - g.w / 2
            paste_max(S, g.mask * sa, gx - cv.x0, g.y - cv.y0)
        hl = ease_out_cubic(lin(i, t0 + 4 * ts, t0 + 28 * ts))
        if hl > 0:
            sx0, _, sx1, _ = self.sub_box
            y = self.sub_axis_y - cv.y0
            L = 120.0 * hl
            xs = np.arange(cv.w, dtype=np.float32)
            ys = np.arange(cv.h, dtype=np.float32)
            cov_y = np.clip(1.3 - np.abs(ys - y), 0, 1)
            for side in (-1, 1):
                xa = (sx0 - 36 if side < 0 else sx1 + 36) - cv.x0
                lo, hi = sorted((xa, xa + side * L))
                cov_x = np.clip(np.minimum(xs + 1 - lo, hi - xs), 0, 1)
                taper = np.clip(1.0 - np.abs(xs - xa) / 128.0, 0, 1) ** 0.8
                S = np.maximum(S, (cov_y[:, None] * (cov_x * taper)[None, :]) * 0.6 * sa)
        cv.over(SHADOW, text_shadow(S, 2.5, 12.0, 0.55, 0.40))
        cv.over(SUB, S)


class NameTitle(Title):
    """Lower-third character card: name / tapered dry-brush stroke / epithet (stroke and epithet together)."""

    NAME_SHADOW = (4.0, 22.0, 0.5, 0.38, 2.2, 2.6)
    EPI_SHADOW = (2.5, 10.0, 0.85, 0.5, 3.0, 2.6)

    def setup(self):
        s = self.spec
        name = s["text"].replace(" ", "")
        n_glyph = max(1, len(name))
        self.size = {1: 150, 2: 138, 3: 128, 4: 124}.get(n_glyph, int(124 * 4 / n_glyph))
        x = self.lay.get("x", 178)
        base = self.lay.get("base", 792)
        gl = set_optical(name, NAME_FACE, self.size, gap=0.07) if name else []
        if gl:
            x0, y0, x1, y1 = ink_box(gl)
            translate(gl, x - x0, base - y1)                 # the ink sits on the stroke line
            nx0, ny0, nx1, ny1 = ink_box(gl)
        else:
            nx0, ny0, nx1, ny1 = x, base - 10, x + 200, base
        self.glyphs = gl
        stroke_len = max(300.0, (nx1 - nx0) + 170.0)
        self.stroke, self.stroke_cy, self.stroke_pad = make_brush_stroke(stroke_len, 6.5, self.rng)
        self.stroke_xy = (nx0 - 12 - self.stroke_pad, ny1 + 22 - self.stroke_cy)
        self.stroke_len = stroke_len
        sg = []
        if has_text(s.get("sub")):
            sg, _ = set_line(s["sub"].strip(), NAME_SUB_FACE, 31, tracking=0.55)
            sx0, sy0, _, _ = ink_box(sg)
            translate(sg, nx0 + 4 - sx0, ny1 + 44 - sy0)
        self.sub = sg
        bx0, by0, bx1, by1 = ink_box(gl + sg) if (gl or sg) else (nx0, ny0, nx1, ny1)
        bx1 = max(bx1, nx0 + stroke_len)
        by1 = max(by1, ny1 + 30)
        self.bd = ((bx0 + bx1) / 2 - 30, (by0 + by1) / 2 + 10, (bx1 - bx0) * 0.80 + 80, (by1 - by0) * 0.80 + 30)
        self.cv = canvas_geom((bx0 - 60, by0, bx1 + 60, by1), 100, [self.bd])
        self.bdm = backdrop(Canvas(*self.cv), *self.bd)
        ts = self.ts
        self.t_name_a, self.t_name_slide, self.t_name_blur = 13 * ts, 16 * ts, 11 * ts
        self.t_stroke = (5 * ts, 16 * ts)
        self.t_epi = (5 * ts, 16 * ts)
        self.t_epi_slide = 18 * ts
        self.fade_len = self.out_len(14)
        self.out_start = self.n - 1 - self.fade_len
        self.ramps.update(name=max(self.t_name_a, self.t_name_slide), stroke=self.t_stroke[1] + 1.5)
        if sg:
            self.ramps.update(epithet=max(self.t_epi[1], self.t_epi_slide))

    def render(self, i):
        n, ts = self.n, self.ts
        cv = Canvas(*self.cv)
        fade = 1.0 - ease_in_out_sine(lin(i, self.out_start, n - 1))
        exit_dx = 14.0 * ease_in_cubic(lin(i, self.out_start, n - 1))
        a = ease_out_cubic(lin(i, 0, self.t_name_a))
        dx = -38.0 * (1.0 - ease_out_quart(lin(i, 0, self.t_name_slide))) + exit_dx
        N = np.zeros((cv.h, cv.w), np.float32)
        for g in self.glyphs:
            paste_max(N, g.mask, g.x - cv.x0 + dx, g.y - cv.y0)
        bl = 3.2 * (1.0 - ease_out_cubic(lin(i, 0, self.t_name_blur)))
        if bl > 0.05:
            N = blur(N, bl)
        N *= a
        sp = ease_out_cubic(lin(i, *self.t_stroke))
        Sk = np.zeros_like(N)
        if sp > 0:
            st = self.stroke
            sx, sy = self.stroke_xy
            xs = np.arange(st.shape[1], dtype=np.float32) - self.stroke_pad
            head = sp * (self.stroke_len + 40.0)
            wipe = np.clip((head - xs) / 26.0, 0, 1)
            paste_max(Sk, st * wipe[None, :] * 0.92, sx - cv.x0 + exit_dx * 0.7, sy - cv.y0)
        ea = ease_in_out_sine(lin(i, *self.t_epi))
        E = np.zeros_like(N)
        if ea > 0:
            edx = 12.0 * (1.0 - ease_out_cubic(lin(i, self.t_epi[0], self.t_epi_slide))) + exit_dx * 0.5
            for g in self.sub:
                paste_max(E, g.mask * ea, g.x - cv.x0 + edx, g.y - cv.y0)
        allm = np.maximum(N, Sk * 0.8)
        cv.over(SHADOW, self.bdm * 0.30 * ease_in_out_sine(lin(i, 0, 16 * ts)))
        cv.over(SHADOW, text_shadow(allm, *self.NAME_SHADOW))
        cv.over(SHADOW, text_shadow(E, *self.EPI_SHADOW))                         # epithet: its own tight shadow
        cv.over(GLOW_WARM, np.clip(blur(N, 9.0) * 1.2, 0, 1) * 0.16)
        cv.over(IVORY, np.clip(blur(N, 1.4) - N, 0, 1) * 0.4)
        cv.over(IVORY, N)
        cv.over(IVORY * 0.96, Sk)
        cv.over(EPITHET, E)
        cv.multiply_alpha(fade)
        return cv


class ActTitle(Title):
    """Vertical act card, upper right third: the act-number column (read first — vertical text runs right -> left),
    then the act glyph as a large IVORY calligraphic accent with a soft glow tinted to the act's light; a small
    cinnabar seal (the act glyph carved in intaglio) under the column. Column wipes top -> bottom, the accent is
    written stroke by stroke. No outline rim, no red brush glyph."""

    COL_SIZE = 54
    SEAL_SIZE = 56
    COL_SHADOW = (3.0, 12.0, 0.9, 0.55, 3.0, 2.6)       # near sigma, far sigma, near amt, far amt, gains
    ACC_SHADOW = (5.0, 30.0, 0.46, 0.40, 2.2, 2.6)

    def setup(self):
        s = self.spec
        lay = self.lay
        cx, cy = lay.get("cx", 1532), lay.get("cy", 420)
        acc = s.get("sub", "").replace(" ", "")
        colt = s.get("text", "").replace(" ", "")
        cap = float(lay.get("accent_h", 236))
        big = None
        if acc:
            if len(acc) == 1:
                probe = trim_mask(glyph_ink(get_font(ACT_ACCENT_FACE, 300), acc)[0])
                fs = int(300 * min(cap / probe.shape[0], cap * 1.05 / probe.shape[1]))
                m = trim_mask(glyph_ink(get_font(ACT_ACCENT_FACE, fs), acc)[0])
                big = Glyph(acc, m, 0.0, 0.0, 0)
            else:
                col_acc, _ = set_column(acc, ACT_ACCENT_FACE, int(min(300, 1.25 * cap / len(acc))), 0.02)
                x0, y0, x1, y1 = ink_box(col_acc)
                cvt = Canvas(int(math.floor(x0)) - 2, int(math.floor(y0)) - 2, int(x1 - x0) + 6, int(y1 - y0) + 6)
                big = Glyph(acc, trim_mask(raster(col_acc, cvt)), 0.0, 0.0, 0)
        cs = self.COL_SIZE
        col = []
        if colt:
            col, col_h = set_column(colt, ACT_FACE, cs, tracking=0.38)
        # group layout: [accent] gap [column]; the group is centred on cx, the accent glyph on cy
        gap = 50.0
        col_w = cs
        grp_w = (big.w if big is not None else 0.0) + (gap + col_w if col else 0.0)
        left = cx - grp_w / 2.0
        if big is not None:
            big.x, big.y = left, cy - big.h / 2.0
            top = big.y
        else:
            top = cy - (len(colt) * cs * 1.38) / 2.0
        if col:
            col_cx = (big.x + big.w + gap + col_w / 2.0) if big is not None else cx
            translate(col, col_cx, top + 10)
        self.big, self.col = big, col
        parts = ([big] if big is not None else []) + col
        bx0, by0, bx1, by1 = ink_box(parts)
        self.use_seal = bool(lay.get("seal", True)) and bool(col)
        self.rule = None
        self.seal = None
        ts = self.ts
        if col:
            cb = ink_box(col)
            col_axis = col[0].x + col[0].w / 2.0
            if self.use_seal:
                self.seal_size = self.SEAL_SIZE
                self.seal_c = (col_axis, cb[3] + 30 + self.seal_size / 2.0)
                self.seal = make_seal(act_seal_glyph(s), self.seal_size, self.rng)
                by1 = max(by1, self.seal_c[1] + self.seal_size / 2.0 + 8)
            elif lay.get("rule", True):
                self.rule = (col_axis, cb[3] + 26, 64.0)
                by1 = max(by1, cb[3] + 90)
        self.bd = ((bx0 + bx1) / 2, (by0 + by1) / 2, (bx1 - bx0) * 0.72, (by1 - by0) * 0.66)
        self.cv = canvas_geom((bx0, by0, bx1, by1), 120, [self.bd])
        cv = Canvas(*self.cv)
        self.bdm = backdrop(cv, *self.bd)
        # --- column: gentle top -> bottom wipe per glyph
        self.Mc = raster(col, cv) if col else np.zeros((cv.h, cv.w), np.float32)
        self.Tc = np.full(self.Mc.shape, 1e6, np.float32)
        colx = np.arange(cv.w)[None, :]
        rowy = np.arange(cv.h)[:, None]
        self.col_t = [(ts * (2.0 + 2.6 * k), ts * (10.0 + 2.6 * k)) for k in range(len(col))]
        for g, (c0, c1) in zip(col, self.col_t):
            gx0, gy0 = g.x - cv.x0, g.y - cv.y0
            Tk = wipe_reveal_map(self.Mc.shape, (gx0, gy0, gx0 + g.w, gy0 + g.h), c0, c1, self.rng, "down")
            sel = (colx >= gx0 - 4) & (colx <= gx0 + g.w + 4) & (rowy >= gy0 - 4) & (rowy <= gy0 + g.h + 4)
            self.Tc = np.where(sel, np.minimum(self.Tc, Tk), self.Tc)
        if col:
            self.ramps["column"] = self.col_t[-1][1] + 1.0
        # --- accent: written stroke by stroke (with a mild top -> bottom bias), overlapping the column's end
        if big is not None:
            a0, a1 = ts * 8.0, ts * 26.0
            self.ink = Ink([big], cv, self.rng, timings=[(a0, a1)], overlap=0.30, bias_down=0.2,
                           comp_orders=lay.get("comp_order"))
            self.ramps["accent"] = self.ink.end + 1.0
        else:
            self.ink = None
        if self.seal is not None:
            self.seal_impact = (self.ink.end if self.ink is not None else self.ramps.get("column", 10.0)) + 2.0
            self.seal_t = self.seal_impact - 2.0
            self.ramps["seal"] = self.seal_impact + SEAL_SETTLE
        if self.rule is not None:
            self.t_rule = (10 * ts, 22 * ts)
            self.ramps["rule"] = self.t_rule[1]
        self.glow = ACT_GLOW.get(self.id, GLOW_WARM)
        self.fade_len = self.out_len(15)
        self.out_start = self.n - 1 - self.fade_len

    def render(self, i):
        n, ts = self.n, self.ts
        cv = Canvas(*self.cv)
        fade = ease_in_out_sine(lin(i, self.out_start, n - 1))
        C = self.Mc * reveal(self.Tc, i, 1.4)
        if self.ink is not None:
            B, front = self.ink.at(i, front_tau=1.6, dry=0.5)
        else:
            B, front = np.zeros_like(C), np.zeros_like(C)
        Rl = np.zeros_like(C)
        if self.rule is not None:
            rl = ease_out_cubic(lin(i, *self.t_rule))
            if rl > 0:
                x, y, L = self.rule
                ys = np.arange(cv.h, dtype=np.float32) + cv.y0
                xs = np.arange(cv.w, dtype=np.float32) + cv.x0
                cov_y = np.clip(np.minimum(ys + 1 - y, y + L * rl - ys), 0, 1)
                cov_x = np.clip(1.5 - np.abs(xs - x), 0, 1)                    # a crisp 2 px rule
                Rl = cov_y[:, None] * cov_x[None, :] * 0.85
        cv.over(SHADOW, self.bdm * 0.30 * ease_in_out_sine(lin(i, 0, 20 * ts)))
        if self.ink is not None:
            cv.over(SHADOW, text_shadow(B, *self.ACC_SHADOW))                   # accent: soft two-scale shadow
            cv.over(self.glow, np.clip(blur(B, 12.0) * 1.15, 0, 1) * 0.24)       # act-tinted glow, no outline
            bleed = 1.4 + 1.1 * clamp01((i - 8 * ts) / (30.0 * ts))
            cv.over(IVORY, np.clip(blur(B, bleed) - B, 0, 1) * 0.5)             # ink feathering
            col = IVORY[None, None, :] * self.ink.shade()[..., None] + \
                (IVORY_HOT - IVORY)[None, None, :] * (0.8 * front)[..., None]
            cv.over(np.clip(col, 0, 1), B)
        small = np.maximum(C, Rl)
        cv.over(SHADOW, text_shadow(small, *self.COL_SHADOW))                     # column: its own tight shadow
        cv.over(IVORY, np.clip(blur(C, 1.2) - C, 0, 1) * 0.3)
        cv.over(IVORY, C)
        cv.over(SUB, Rl)
        if self.seal is not None:
            draw_seal(cv, self.seal, self.seal_c, i - self.seal_t, 1.5, shadow=0.45)
        if fade > 0:
            cv.transform(dy=-9.0 * ease_in_cubic(fade), sigma=2.0 * fade)
            cv.multiply_alpha(1.0 - fade)
        return cv


class EndTitle(Title):
    """The 'End' card — written in, seal, small Kaiti credit line in the lower letterbox; fades out with the film."""

    clip_y = (PIC_Y0, H)       # the small credit may sit in the lower letterbox bar
    CREDIT_SIZE = 27

    def setup(self):
        s = self.spec
        cy = self.lay.get("cy", 506)
        txt = s.get("text", "").replace(" ", "")
        gl = []
        if txt:
            gl = set_optical(txt, END_FACE, 230 if len(txt) == 1 else int(230 * min(1.0, 3.2 / len(txt))), gap=0.06)
            x0, y0, x1, y1 = ink_box(gl)
            translate(gl, W / 2 - (x0 + x1) / 2, cy - (y0 + y1) / 2)
        self.glyphs = gl
        cg = []
        cs = self.CREDIT_SIZE
        if has_text(s.get("sub")):
            cg, _ = set_line(s["sub"].strip(), END_CREDIT_FACE, cs, tracking=0.22, latin_tracking=0.04)
            center_line(cg, W / 2, self.lay.get("credit_y", 1014), END_CREDIT_FACE, cs, hang=False)
        self.credit = cg
        ts = self.ts
        boxes = []
        self.seal_impact = None
        if gl:
            gx0, gy0, gx1, gy1 = ink_box(gl)
            g = gl[-1]
            self.seal_size = 66
            self.seal_c = (gx1 + 12 + self.seal_size / 2, g.y + g.h - self.seal_size / 2 - 22)
            self.bd = (W / 2, cy, (gx1 - gx0) * 1.3, (gy1 - gy0) * 0.95)
            boxes.append((gx0, gy0, self.seal_c[0] + self.seal_size, gy1))
        else:
            self.bd = (W / 2, cy, 200.0, 150.0)
        if cg:
            boxes.append(ink_box(cg))
        content = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes),
                   max(b[3] for b in boxes))
        self.cv = canvas_geom(content, 110, [self.bd])
        cv = Canvas(*self.cv)
        self.fade_len = self.out_len(16)
        self.out_start = self.n - 1 - self.fade_len
        if gl:
            self.ink = Ink(gl, cv, self.rng, window=(3.0 * ts, 26.0 * ts), next_at=0.85, overlap=0.28,
                           comp_orders=self.lay.get("comp_order"))
            impact, src = self.ink.end + 4.0, "design (no cue)"
            cue = (s.get("_cues") or {}).get("end_seal")
            if cue and cue.get("frame") is not None:
                local = float(cue["frame"] - s["start"])
                src = f"cue 'end_seal' = {cue['frame']} ({cue.get('source')})"
                if self.ink.end + 2.0 <= local <= self.out_start - 8.0:
                    impact = local
                else:
                    self.warn(f"cue 'end_seal' local {local:.1f} does not fit the card; design timing kept")
                    src += " -> ignored"
            self.seal_impact = impact
            self.seal_t = impact - 2.0
            self.cue_info = dict(seal=dict(frame=s["start"] + int(round(impact)), source=src))
            self.seal = make_seal(SEAL_GLYPH["end"], 66, self.rng)
            self.ramps.update(written=self.ink.end + 1.0, seal=impact + SEAL_SETTLE)
        else:
            self.ink = self.seal = None
        self.t_credit = (22.0 * ts, 34.0 * ts)
        if cg:
            self.ramps["credit"] = self.t_credit[1]
        self.bdm = backdrop(cv, *self.bd)

    def render(self, i):
        n, ts = self.n, self.ts
        cv = Canvas(*self.cv)
        fade = ease_in_out_sine(lin(i, self.out_start, n - 1))
        if self.ink is not None:
            MR, front = self.ink.at(i)
            cv.over(SHADOW, self.bdm * 0.22 * ease_in_out_sine(lin(i, 0, 20 * ts)))
            cv.over(SHADOW, text_shadow(MR, 7.0, 30.0, 0.4, 0.35))
            cv.over(GLOW_WARM, np.clip(blur(MR, 13.0) * 1.1, 0, 1) * 0.10)
            cv.over(IVORY, np.clip(blur(MR, 2.4) - MR, 0, 1) * 0.5)
            col = IVORY[None, None, :] * self.ink.shade()[..., None] + \
                (IVORY_HOT - IVORY)[None, None, :] * (0.8 * front)[..., None]
            cv.over(np.clip(col, 0, 1), MR)
            draw_seal(cv, self.seal, self.seal_c, i - self.seal_t, 2.0, shadow=0.0, spread=False)
        ca = ease_in_out_sine(lin(i, *self.t_credit))
        if ca > 0 and self.credit:
            C = np.zeros((cv.h, cv.w), np.float32)
            for g in self.credit:
                paste_max(C, g.mask * ca, g.x - cv.x0, g.y - cv.y0 + 3.0 * (1.0 - ca))
            cv.over(GREY, C)
        if fade > 0:
            cv.transform(sigma=1.6 * fade)
            cv.multiply_alpha(1.0 - fade)
        return cv


STYLES = {"epigraph": EpigraphTitle, "main": MainTitle, "name": NameTitle, "act": ActTitle, "end": EndTitle}


def build(spec):
    return STYLES[spec["style"]](spec)


# ============================================================================ rendering / caching
def title_dir(tid):
    return os.path.join(config.TITLES_DIR, tid)


def spec_by_id(tid):
    for t in config.TITLES:
        if t["id"] == tid:
            return t
    raise KeyError(tid)


def effective_spec(spec_or_id):
    """config.TITLES entry + the music cues it follows, resolved like the audio lane does (out/events.json ->
    config). Resolving once here (not in the render workers) keeps the stamp, the PNGs and timeline.json
    consistent even if events.json changes mid-render."""
    spec = spec_by_id(spec_or_id) if isinstance(spec_or_id, str) else spec_or_id
    spec = {k: v for k, v in spec.items() if k != "_cues"}
    names = STYLE_CUES.get(spec["style"], [])
    if names:
        res = CUES.resolve_many(names)
        spec["_cues"] = {n: (dict(frame=int(f), source=src) if f is not None else None) for n, (f, src) in res.items()}
    return spec


def stamp_for(spec):
    """Hash of everything a card's pixels depend on: this file, the (effective) spec incl. the resolved cue
    FRAMES (not their source labels), fonts and geometry."""
    with open(os.path.abspath(__file__), "rb") as fh:
        src = fh.read()
    spec = spec if "_cues" in spec else effective_spec(spec)
    frames = {k: (v or {}).get("frame") for k, v in (spec.get("_cues") or {}).items()}
    base = {k: v for k, v in spec.items() if k != "_cues"}
    h = hashlib.sha1(src)
    h.update(json.dumps(base, sort_keys=True, ensure_ascii=False).encode())
    h.update(json.dumps(frames, sort_keys=True).encode())
    fonts = []
    for face in sorted(FACES):
        p = FACES[face][0]
        fonts.append([face, p, os.path.getsize(p) if os.path.exists(p) else None])
    h.update(json.dumps([fonts, W, H, PIC_Y0, PIC_Y1, SEAL_GLYPH, RENDER_VERSION]).encode())
    return h.hexdigest()


def is_current(spec):
    spec = spec if "_cues" in spec else effective_spec(spec)
    d = title_dir(spec["id"])
    n = spec["end"] - spec["start"] + 1
    try:
        with open(os.path.join(d, STAMP_NAME)) as fh:
            st = json.load(fh)
    except (OSError, ValueError):
        return False
    if st.get("hash") != stamp_for(spec) or st.get("frames") != n:
        return False
    return all(os.path.exists(os.path.join(d, f"{k:05d}.png")) for k in range(1, n + 1))


_lock_state = dict(depth=0, fh=None)


@contextlib.contextmanager
def titles_lock(timeout=config.TITLES_LOCK_TIMEOUT_S):
    """Exclusive, process-re-entrant lock on out/titles (renders and assembler snapshots never overlap)."""
    st = _lock_state
    if st["depth"] == 0:
        os.makedirs(config.TITLES_DIR, exist_ok=True)
        fh = os.fdopen(os.open(os.path.join(config.TITLES_DIR, LOCK_NAME), os.O_RDWR | os.O_CREAT, 0o644), "r+b")
        t0, said = time.time(), False
        while not procutil.lock_file(fh):
            if not said:
                print("[titles] waiting for the titles lock (another render/assembly is running) ...", flush=True)
                said = True
            if time.time() - t0 > timeout:
                fh.close()
                raise RuntimeError(f"timed out after {timeout:.0f}s waiting for {config.TITLES_DIR}/{LOCK_NAME}")
            time.sleep(0.25)
        st["fh"] = fh
    st["depth"] += 1
    try:
        yield
    finally:
        st["depth"] -= 1
        if st["depth"] == 0:
            procutil.unlock_file(st["fh"])
            st["fh"].close()
            st["fh"] = None


def _render_chunk(spec, local_frames, out_dir):
    t = build(spec)
    os.makedirs(out_dir, exist_ok=True)
    for k in local_frames:                        # k is 1-based
        fr = t.frame(k - 1)
        Image.fromarray(fr, "RGBA").save(os.path.join(out_dir, f"{k:05d}.png"), compress_level=4)
    return spec["id"], len(local_frames)


def _swap_in(tmp_dir, final_dir):
    """Replace final_dir by the completed tmp_dir (two renames; the old tree is deleted afterwards)."""
    old = None
    if os.path.exists(final_dir):
        old = f"{final_dir}.old{os.getpid()}"
        shutil.rmtree(old, ignore_errors=True)
        os.replace(final_dir, old)
    os.replace(tmp_dir, final_dir)
    if old:
        shutil.rmtree(old, ignore_errors=True)


def render_titles(ids, jobs=None, chunk=24, verbose=True):
    """Render full sequences for the given ids in parallel into <id>.tmp/, stamp them, and swap each into
    place only when complete (call under titles_lock)."""
    specs = [effective_spec(t) for t in ids]
    tasks = []
    for s in specs:
        n = s["end"] - s["start"] + 1
        tmp = title_dir(s["id"]) + ".tmp"
        shutil.rmtree(tmp, ignore_errors=True)
        os.makedirs(tmp)
        frames = list(range(1, n + 1))
        for c in range(0, n, chunk):
            tasks.append((s, frames[c:c + chunk], tmp))
    jobs = jobs or config.TITLE_JOBS
    if (W, H) != LAYOUT_REF:
        warn(f"delivery size {W}x{H}: the title layout is authored in {LAYOUT_REF[0]}x{LAYOUT_REF[1]} px and is not "
             f"rescaled (check the cards)")
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        futs = [ex.submit(_render_chunk, *tk) for tk in tasks]
        for fu in as_completed(futs):
            fu.result()
    for s in specs:
        n = s["end"] - s["start"] + 1
        tmp = title_dir(s["id"]) + ".tmp"
        missing = [k for k in range(1, n + 1) if not os.path.exists(os.path.join(tmp, f"{k:05d}.png"))]
        if missing:
            raise RuntimeError(f"title {s['id']}: {len(missing)} frame(s) missing after render: {missing[:5]}")
        with open(os.path.join(tmp, STAMP_NAME), "w") as fh:
            json.dump(dict(hash=stamp_for(s), frames=n, start=s["start"], end=s["end"], style=s["style"],
                           cues=s.get("_cues"), rendered=time.strftime("%Y-%m-%d %H:%M:%S")),
                      fh, ensure_ascii=False, indent=1)
        _swap_in(tmp, title_dir(s["id"]))
        if verbose:
            print(f"  title {s['id']:13s} frames {s['start']}-{s['end']} ({n}) -> {title_dir(s['id'])}")
    if verbose:
        print(f"  rendered {len(specs)} title(s) in {time.time() - t0:.1f}s with {jobs} workers")


def write_timeline(path=None):
    """out/titles/timeline.json: key absolute frames of every card (start/end, legible window, seal impact and
    the cue it follows) + 'sound_cues' — seal stamps the audio lane can put a sound on."""
    path = path or os.path.join(config.TITLES_DIR, "timeline.json")
    cards, sound = {}, []
    for t in config.TITLES:
        b = build(effective_spec(t))
        m = b.moments()
        cards[t["id"]] = m
        if m.get("seal_impact") is not None:
            sound.append(dict(frame=m["seal_impact"], kind="seal_stamp", card=t["id"],
                              follows=(m.get("cues") or {}).get("seal", {}).get("source")))
    data = dict(cards=cards, sound_cues=sorted(sound, key=lambda x: x["frame"]),
                events=dict(path=config.EVENTS_JSON, sha1=CUES.events_fingerprint()),
                generated=time.strftime("%Y-%m-%d %H:%M:%S"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
    return data


def _cleanup_stale():
    if not os.path.isdir(config.TITLES_DIR):
        return
    for name in os.listdir(config.TITLES_DIR):
        if name.endswith(".tmp") or ".old" in name:
            p = os.path.join(config.TITLES_DIR, name)
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)


def ensure_titles(ids=None, force=False, jobs=None, verbose=True):
    """Make sure the PNG sequences exist and match this generator + config + cues; returns {id: dir}."""
    ids = ids or [t["id"] for t in config.TITLES]
    with titles_lock():
        todo = [t for t in ids if force or not is_current(effective_spec(t))]
        tl = os.path.join(config.TITLES_DIR, "timeline.json")
        if todo:
            _cleanup_stale()
            verify_fonts(verbose=verbose)
            render_titles(todo, jobs=jobs, verbose=verbose)
            write_timeline()
        else:
            if not os.path.exists(tl):
                write_timeline()
            if verbose:
                print("  titles up to date")
    return {t: title_dir(t) for t in ids}


def _link_or_copy(src, dst):
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def snapshot_titles(ids, dest_dir, force=False, jobs=None, verbose=True):
    """Under the lock: ensure the cards are current, then hard-link (or copy) their PNGs into
    dest_dir/<id>/ so an encoder reads a private, immutable snapshot even if titles re-render meanwhile."""
    out = {}
    with titles_lock():
        ensure_titles(ids, force=force, jobs=jobs, verbose=verbose)
        for tid in ids:
            src = title_dir(tid)
            dst = os.path.join(dest_dir, tid)
            os.makedirs(dst, exist_ok=True)
            for name in os.listdir(src):
                if name.endswith(".png"):
                    _link_or_copy(os.path.join(src, name), os.path.join(dst, name))
            out[tid] = dst
    return out


def check_bounds(ids=None):
    """Every frame of every title: nothing but the end credit may put alpha > 2/255 into the letterbox
    bars, and every PNG must be DELIVERY-sized RGBA. Returns a list of offending (id, frame, top, bottom)."""
    bad = []
    for tid in ids or [t["id"] for t in config.TITLES]:
        spec = spec_by_id(tid)
        d = title_dir(tid)
        n = spec["end"] - spec["start"] + 1
        for k in range(1, n + 1):
            with Image.open(os.path.join(d, f"{k:05d}.png")) as im:
                if im.size != (W, H) or im.mode != "RGBA":
                    bad.append((tid, k, f"{im.size} {im.mode}", ""))
                    continue
                a = np.asarray(im.getchannel("A"))
            top, bot = int(a[:PIC_Y0].max()), int(a[PIC_Y1:].max())
            if top > 2 or (bot > 2 and spec["style"] != "end"):
                bad.append((tid, k, top, bot))
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="comma-separated title ids")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--jobs", type=int, default=None)
    ap.add_argument("--check-fonts", action="store_true")
    ap.add_argument("--frames", help="render only these 1-based local frames of the --only titles")
    ap.add_argument("--out", help="output dir for --frames (default: out/titles/_frames)")
    a = ap.parse_args(argv)
    if a.check_fonts:
        verify_fonts(verbose=True)
        print("font check OK")
        return 0
    ids = a.only.split(",") if a.only else None
    if a.frames:
        verify_fonts(verbose=False)
        frames = [int(x) for x in a.frames.split(",")]
        for tid in ids or [t["id"] for t in config.TITLES]:
            # never write into the stamped card dirs: debug frames go to --out or out/titles/_frames/<id>
            d = os.path.join(a.out or os.path.join(config.TITLES_DIR, "_frames"), tid)
            _render_chunk(effective_spec(tid), frames, d)
            print(f"  {tid}: frames {frames} -> {d}")
        return 0
    ensure_titles(ids, force=a.force, jobs=a.jobs)
    with titles_lock():                       # never read a card while another process swaps it in
        bad = check_bounds(ids)
    if bad:
        print("WARNING: title alpha inside letterbox bars:", bad)
    else:
        print("  letterbox check OK (no title alpha in the bars except the end credit)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
