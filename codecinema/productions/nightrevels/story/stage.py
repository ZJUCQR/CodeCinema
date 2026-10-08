"""
stage.py - renders one frame of the living scroll: silk + mounting, actors sorted by depth, light, grain.

A Stage holds actors (anim.Actor), a Camera and text images (captions / title slips) and draws frame f into a
skia.Surface. Scene content is built by film.py.
"""

import os
import sys

import numpy as np
import skia

from codecinema.workspace.paths import film_assets, project_root

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(os.path.dirname(HERE), "paint"), os.path.join(os.path.dirname(HERE), "common")]
import config as C  # noqa: E402
from ink import ellipse, fill, stroke_line  # noqa: E402
from silk import make_grain, make_silk  # noqa: E402


# ------------------------------------------------------------------------------------------------ text images
def _font(names, size):
    from PIL import ImageFont
    dirs = ["/System/Library/Fonts", "/System/Library/Fonts/Supplemental", "/Library/Fonts",
            os.path.expanduser("~/Library/Fonts"), "/usr/share/fonts", str(film_assets(C.ROOT) / "fonts"),
            os.path.join(project_root(C.ROOT), "assets", "_shared", "fonts")]
    import glob
    dirs += glob.glob("/System/Library/AssetsV2/com_apple_MobileAsset_Font*/*/AssetData")
    for n in names:
        for d in dirs:
            for root, _, files in os.walk(d):
                for f in files:
                    if f.lower() == n.lower():
                        return ImageFont.truetype(os.path.join(root, f), size)
    return ImageFont.load_default()


CALLI = ["Xingkai.ttc", "STXINGKA.TTF", "ZhiMangXing-Regular.ttf", "MaShanZheng-Regular.ttf", "LXGWWenKai-Regular.ttf"]
KAI = ["Kaiti.ttc", "STKAITI.TTF", "simkai.ttf", "LXGWWenKai-Regular.ttf"]
EN_SERIF = ["Baskerville.ttc", "Didot.ttc", "Georgia.ttf", "DejaVuSerif.ttf", "LiberationSerif-Regular.ttf"]


def text_image(text, size=64, vertical=True, font=CALLI, color=(34, 26, 22), spacing=1.08):
    """Calligraphy as a transparent skia.Image (vertical columns read top-down)."""
    from PIL import Image, ImageDraw
    f = _font(font, size)
    chars = list(text)
    if vertical:
        w, h = int(size * 1.3), int(size * spacing * len(chars) + size * 0.4)
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        for i, ch in enumerate(chars):
            d.text((w / 2, size * 0.2 + i * size * spacing + size / 2), ch, font=f, fill=color + (235,), anchor="mm")
    else:
        bbox = f.getbbox(text)
        w, h = bbox[2] - bbox[0] + int(size * 0.4), int(size * 1.5)
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.text((w / 2, h / 2), text, font=f, fill=color + (240,), anchor="mm")
    arr = np.array(im)
    return skia.Image.fromarray(arr, colorType=skia.kRGBA_8888_ColorType)


def seal_image(text, size=90, color=(178, 34, 28), style="relief"):
    """A red square seal (white characters cut into red = intaglio 'relief' negative)."""
    from PIL import Image, ImageDraw, ImageFilter
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((3, 3, size - 3, size - 3), radius=size // 12, fill=color + (235,))
    chars = list(text)
    n = len(chars)
    f = _font(["Kaiti.ttc", "STKAITI.TTF", "LXGWWenKai-Regular.ttf"], int(size * (0.7 if n == 1 else 0.42)))
    if n == 1:
        d.text((size / 2, size / 2), text, font=f, fill=(245, 232, 215, 255), anchor="mm")
    else:
        pos = [(0.72, 0.28), (0.72, 0.72), (0.28, 0.28), (0.28, 0.72)]
        for ch, (px, py) in zip(chars, pos):
            d.text((size * px, size * py), ch, font=f, fill=(245, 232, 215, 255), anchor="mm")
    arr = np.array(im.filter(ImageFilter.GaussianBlur(0.4)))
    rng = np.random.default_rng(len(text))
    worn = rng.random(arr.shape[:2]) < 0.04
    arr[worn, 3] = (arr[worn, 3] * 0.5).astype(np.uint8)
    return skia.Image.fromarray(arr, colorType=skia.kRGBA_8888_ColorType)


# ------------------------------------------------------------------------------------------------ stage
class Stage:
    def __init__(self, camera, actors, texts=None, light=None):
        self.cam, self.actors = camera, actors
        self.texts = texts or []            # (actor-like dict: image, x, y, scale, alpha track)
        self.light = light                   # light(f) -> (tint rgb, strength)
        self._silk = None
        self._grain = None
        self.overlays = []                   # screen-space images: dict(image, cx, cy, scale, alpha)
        self.black = None                    # fade-to-black track

    # silk is created lazily per process and cached on disk
    def silk(self):
        if self._silk is None:
            if os.path.exists(C.SILK_NPY):
                arr = np.load(C.SILK_NPY)
            else:
                arr = make_silk(C.SCROLL_L, C.SCROLL_H)
                os.makedirs(os.path.dirname(C.SILK_NPY), exist_ok=True)
                np.save(C.SILK_NPY, arr)
            self._silk = skia.Image.fromarray(arr, colorType=skia.kRGBA_8888_ColorType)
            self._grain = skia.Image.fromarray(make_grain(C.W, C.H), colorType=skia.kRGBA_8888_ColorType)
        return self._silk

    def draw_mount(self, c):
        """Brocade mounting at both ends and the thin binding along the edges."""
        for x0, x1 in ((C.MOUNT_R, C.SCROLL_L), (0, C.MOUNT_L)):
            r = skia.Rect.MakeLTRB(x0, 0, x1, C.SCROLL_H)
            c.drawRect(r, skia.Paint(Color4f=skia.Color4f(0.22, 0.32, 0.36, 1)))
            c.save()
            c.clipRect(r)
            for yy in range(20, C.SCROLL_H, 70):
                for xx in range(int(x0) + ((yy // 70) % 2) * 35, int(x1), 70):
                    fill(c, ellipse(xx, yy, 12, 7), (0.72, 0.6, 0.32), 0.55)
                    stroke_line(c, [(xx - 16, yy + 4), (xx - 4, yy - 6), (xx + 8, yy + 4), (xx + 18, yy - 4)], 1.2,
                                (0.8, 0.68, 0.38), 0.5)
            c.restore()
            edge = C.MOUNT_R if x0 == C.MOUNT_R else C.MOUNT_L
            c.drawRect(skia.Rect.MakeLTRB(edge - 6, 0, edge + 6, C.SCROLL_H),
                       skia.Paint(Color4f=skia.Color4f(0.62, 0.5, 0.28, 1)))
        # rollers at the very ends
        for xr in (-18, C.SCROLL_L + 18):
            c.drawRect(skia.Rect.MakeLTRB(xr - 18, -40, xr + 18, C.SCROLL_H + 40),
                       skia.Paint(Color4f=skia.Color4f(0.32, 0.2, 0.12, 1)))
            for yy in (-40, C.SCROLL_H + 40):
                fill(c, ellipse(xr, yy, 26, 12), (0.85, 0.8, 0.7))

    def render(self, f, surface):
        cx, cy, z = self.cam.at(f)
        hh = C.H / 2 / z
        if hh <= C.SCROLL_H / 2:            # keep close-ups inside the silk (no band below / above the scroll)
            cy = min(max(cy, hh), C.SCROLL_H - hh)
        c = surface.getCanvas()
        c.clear(skia.Color4f(0.07, 0.06, 0.06, 1))
        c.save()
        c.translate(C.W / 2, C.H / 2)
        c.scale(z, z)
        c.translate(-cx, -cy)
        half_w = C.W / 2 / z
        view = (cx - half_w - 400, cx + half_w + 400)
        # silk ground (only the visible slice is sampled)
        silk = self.silk()
        src = skia.Rect.MakeLTRB(max(0, view[0]), 0, min(C.SCROLL_L, view[1]), C.SCROLL_H)
        if src.width() > 0:
            c.drawImageRect(silk, src, src, skia.SamplingOptions(skia.FilterMode.kLinear), None)
        if view[1] > C.MOUNT_R or view[0] < C.MOUNT_L:
            self.draw_mount(c)
        # texts on the silk
        for t in self.texts:
            a = t["alpha"](f)
            if a <= 0.01 or not (view[0] - 500 < t["x"] < view[1] + 500):
                continue
            img = t["image"]
            s = t.get("scale", 1.0)
            p = skia.Paint(Color4f=skia.Color4f(1, 1, 1, a))
            c.drawImageRect(img, skia.Rect.MakeXYWH(t["x"] - img.width() * s / 2, t["y"], img.width() * s,
                                                    img.height() * s), skia.SamplingOptions(skia.FilterMode.kLinear),
                            p)
        # actors by depth
        live = []
        for a in self.actors:
            x = a.value("x", f)
            if a.value("visible", f) < 0.5:
                continue
            if not (view[0] - 600 < x < view[1] + 600):
                continue
            live.append((a.z + a.value("zoff", f), a.value("y", f), a))
        for _, _, a in sorted(live, key=lambda t: (t[0], t[1])):
            if a.draw_fn is not None:
                a.draw_fn(c, a, f)
            else:
                pose = a.at(f)
                hold = (lambda cv, a=a, pose=pose: a.hold(cv, f, pose)) if a.hold else None
                extra = (lambda cv, anc, a=a, pose=pose: a.extra(cv, f, pose, anc)) if a.extra else None
                a.char.facing = pose.get("facing", a.char.facing)
                a.char.draw(c, a.value("x", f), a.value("y", f), pose, hold=hold, extra=extra)
        c.restore()
        # night light: a warm, dimming multiply that cools at dawn + vignette
        if self.light is not None:
            tint, k = self.light(f)
            p = skia.Paint(Color4f=skia.Color4f(tint[0], tint[1], tint[2], k), BlendMode=skia.BlendMode.kMultiply)
            c.drawRect(skia.Rect.MakeWH(C.W, C.H), p)
        vg = skia.GradientShader.MakeRadial(skia.Point(C.W / 2, C.H / 2), C.W * 0.72,
                                            [skia.Color4f(0, 0, 0, 0), skia.Color4f(0, 0, 0, 0.0),
                                             skia.Color4f(0.05, 0.03, 0.02, 0.38)], [0.0, 0.55, 1.0])
        c.drawRect(skia.Rect.MakeWH(C.W, C.H), skia.Paint(Shader=vg))
        # fibre grain overlay
        c.drawImage(self._grain, 0, 0, skia.SamplingOptions(),
                    skia.Paint(BlendMode=skia.BlendMode.kOverlay, Color4f=skia.Color4f(1, 1, 1, 0.35)))
        for o in self.overlays:
            a = o["alpha"](f)
            if a > 0.01:
                img, s = o["image"], o.get("scale", 1.0)
                c.drawImageRect(img, skia.Rect.MakeXYWH(o["cx"] - img.width() * s / 2, o["cy"] - img.height() * s / 2,
                                                        img.width() * s, img.height() * s),
                                skia.SamplingOptions(skia.FilterMode.kLinear), skia.Paint(Color4f=skia.Color4f(1, 1, 1, a)))
        if self.black is not None:
            k = self.black(f)
            if k > 0.001:
                c.drawRect(skia.Rect.MakeWH(C.W, C.H), skia.Paint(Color4f=skia.Color4f(0, 0, 0, min(1.0, k))))
