"""
contact_sheet.py - tile rendered frames into one labelled sheet (frame number + cut id) for review.

    .venv/bin/python codecinema/productions/silvergrass/tools/contact_sheet.py out/previews/act1b/preview --every 12 \
        [--events out/lanes/act1b/events.json] [--start N --end M] [--cols 8] [--width 320]
        [--boost EV | --auto-boost] [--title TEXT] [--out sheet.png]

Cut ids come from the 'cuts' list of an events.json (build output); without it the config shot id is used.
--boost EV brightens every tile by EV stops (linear light); --auto-boost lifts only dark tiles (storm frames:
mean luminance < 0.08) towards 0.18 (<= +3 EV) and prints the applied boost on the tile so nobody mistakes it
for the real exposure.  Importable: make_sheet(paths_or_dir, out, ...) -> out path.
"""

from codecinema.productions import film_root, source_root
import argparse
import json
import math
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = str(film_root("silvergrass"))
sys.path.insert(0, os.path.join(str(source_root("silvergrass")), "common"))
import config  # noqa: E402

FRAME_RE = re.compile(r"(?<![\d.])(\d{4,6})\.png$")
FONT_PATHS = (config.FONT_MONO, config.FONT_UI)     # settings [fonts] mono / ui (auto-detected; "" if none)


def font(size):
    for p in FONT_PATHS:
        if p and os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                pass
    try:
        return ImageFont.load_default(size=size)       # Pillow >= 10.1: scalable bundled font
    except TypeError:
        return ImageFont.load_default()


def list_frames(d):
    """{frame: path} of '<frame>.png' files in d (tmp files ignored)."""
    out = {}
    for f in os.listdir(d):
        if f.endswith(".tmp.png"):
            continue
        m = FRAME_RE.search(f)
        if m:
            out[int(m.group(1))] = os.path.join(d, f)
    return dict(sorted(out.items()))


def cut_lookup(events_path=None):
    """frame -> cut id function from an events.json 'cuts' list (fallback: config shots)."""
    cuts = []
    if events_path and os.path.exists(events_path):
        with open(events_path, encoding="utf-8") as f:
            doc = json.load(f)
        cuts = [(c["start"], c["end"], c["id"]) for c in doc.get("cuts", [])]

    def lookup(fr):
        for a, b, cid in cuts:
            if a <= fr <= b:
                return cid
        s = config.shot_at(fr)
        return s["id"] if s else ""
    return lookup


def _to_lin(a):
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def _to_srgb(a):
    a = np.clip(a, 0.0, 1.0)
    return np.where(a <= 0.0031308, a * 12.92, 1.055 * a ** (1 / 2.4) - 0.055)


def luminance(img):
    """Mean relative luminance (0..1, linear) of a PIL image."""
    a = _to_lin(np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0)
    return float((a[..., 0] * 0.2126 + a[..., 1] * 0.7152 + a[..., 2] * 0.0722).mean())


def boost(img, ev):
    """Brighten by ev stops in linear light."""
    if not ev:
        return img
    a = _to_lin(np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0) * (2.0 ** ev)
    return Image.fromarray((_to_srgb(a) * 255.0 + 0.5).astype(np.uint8))


def make_sheet(src, out, every=1, start=None, end=None, frames=None, cols=6, width=320, ev=0.0, auto=False,
               events=None, title=None):
    """Build the sheet from a frame directory (or {frame: path}); returns out path."""
    fmap = list_frames(src) if isinstance(src, str) else dict(src)
    sel = [f for f in fmap if (start is None or f >= start) and (end is None or f <= end)]
    if frames:
        sel = [f for f in sel if f in set(frames)]
    elif every > 1 and sel:
        base = sel[0]
        sel = [f for f in sel if (f - base) % every == 0] or sel[:1]
    if not sel:
        raise SystemExit(f"contact_sheet: no frames in {src}")
    cut_of = cut_lookup(events)
    first = Image.open(fmap[sel[0]])
    h = max(1, round(width * first.height / first.width))
    lab_h = max(14, width // 16)
    fnt, fnt_t = font(lab_h - 3), font(22)
    rows = math.ceil(len(sel) / cols)
    top = 34 if title else 0
    sheet = Image.new("RGB", (cols * width + (cols + 1) * 4, top + rows * (h + lab_h + 4) + 4), (18, 18, 20))
    d = ImageDraw.Draw(sheet)
    if title:
        d.text((8, 6), title, fill=(235, 235, 235), font=fnt_t)
    for i, fr in enumerate(sel):
        im = Image.open(fmap[fr]).convert("RGB").resize((width, h), Image.LANCZOS)
        applied = ev
        if auto:
            lum = luminance(im)
            if lum < 0.08:
                applied = ev + min(3.0, math.log2(0.18 / max(lum, 1e-4)))
        im = boost(im, applied)
        x = 4 + (i % cols) * (width + 4)
        y = top + 4 + (i // cols) * (h + lab_h + 4)
        sheet.paste(im, (x, y))
        d.rectangle([x, y + h, x + width - 1, y + h + lab_h - 1], fill=(0, 0, 0))
        label = f"{fr:05d}  {cut_of(fr)}" + (f"  +{applied:.1f}EV" if applied else "")
        d.text((x + 4, y + h + 1), label, fill=(255, 220, 120) if applied else (230, 230, 230), font=fnt)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    sheet.save(out)
    print(f"[contact_sheet] {len(sel)} frames -> {out} ({sheet.width}x{sheet.height})")
    return out


def main():
    ap = argparse.ArgumentParser(prog="contact_sheet.py")
    ap.add_argument("dir")
    ap.add_argument("--out", default=None)
    ap.add_argument("--every", type=int, default=1)
    ap.add_argument("--start", type=int, default=None)
    ap.add_argument("--end", type=int, default=None)
    ap.add_argument("--frames", default=None)
    ap.add_argument("--cols", type=int, default=6)
    ap.add_argument("--width", type=int, default=320)
    ap.add_argument("--boost", type=float, default=0.0, help="exposure boost in stops (all tiles)")
    ap.add_argument("--auto-boost", action="store_true", help="boost only dark tiles (storm)")
    ap.add_argument("--events", default=None, help="events.json with the cut list")
    ap.add_argument("--title", default=None)
    a = ap.parse_args()
    out = a.out or os.path.join(a.dir, "contact_sheet.png")
    frames = [int(x) for x in a.frames.split(",")] if a.frames else None
    make_sheet(a.dir, out, a.every, a.start, a.end, frames, a.cols, a.width, a.boost, a.auto_boost, a.events,
               a.title)


if __name__ == "__main__":
    main()
