"""
flash_qc.py - photosensitivity check of a rendered frame directory using the limits below.

    .venv/bin/python src/tools/flash_qc.py out/frames [--start N --end M] [--json report.json] [--plot lum.png]
        [--strict]

ONE implementation of the hard rules: they are delegated to src/post/flash_qc.py (post lane: sRGB -> linear
luminance of the picture, BT.1702 / WCAG general-flash counting, letterbox handling, video input):
    FAIL  > 3 flashes (>= 7 counted >= 10 % transitions whose darker side < 0.80) within any 24 frames
    FAIL  any frame outside config.FULL_WHITE with mean luminance > 0.92 (only the S25 white-out may be white)
    WARN  > 2 flashes per 24 f (the <= 2 per second budget), flash peaks > 70 %, red flashes, sparse sequences
This wrapper adds the pipeline's extra checks on top, using the same counting code:
    FAIL  the general-flash rule on each screen QUADRANT (25 % of the screen = WCAG's area threshold: a bolt that
          strobes one corner can pass the whole-frame mean)
    WARN  (FAIL with --strict) director's budget: flash onsets < config.FLASH_MIN_GAP (12) frames apart,
          saturated-red area rising faster than RED_RAMP_MIN (6) frames (the S15 fire-ramp rule)
config.FULL_WHITE frames (and +-1 f around them) are ignored.  With sparse frames (preview step 2) missing
frames hold the previous one (1-frame flashes can be missed; the report says so).  Exit code 1 on FAIL,
2 when there is nothing to analyse.
"""
import argparse
import importlib.util
import json
import os
import re
import sys

import numpy as np
from PIL import Image

ROOT = (__import__("os").environ.get("SILVERGRASS_ROOT") or str(next(p for p in __import__("pathlib").Path(__file__).resolve().parents if (p / "src" / "common" / "config.py").is_file())))   # repo root (portable)
sys.path.insert(0, os.path.join(ROOT, "src", "common"))
import config  # noqa: E402

POST_PATH = os.path.join(ROOT, "src", "post", "flash_qc.py")
FRAME_RE = re.compile(r"^(\d{4,6})\.png$")
RED_RAMP_MIN = config.PHOTOSENSITIVITY["fire_ramp_min_frames"]     # S15 fire-ramp rule (6 f)


def post():
    """The post lane's flash_qc module (loaded under another name: this file is called flash_qc too)."""
    spec = importlib.util.spec_from_file_location("post_flash_qc", POST_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def series(frame_dir, P, start=None, end=None, width=640):
    """Per-frame (held over gaps) full-frame luminance, red fraction and the 4 quadrant luminances, measured
    with the post module's frame_stats (same sampling + EOTF as the hard rules)."""
    found = {}
    for name in os.listdir(frame_dir):
        m = FRAME_RE.match(name)
        if m:
            found[int(m.group(1))] = os.path.join(frame_dir, name)
    if start is not None or end is not None:
        found = {f: p for f, p in found.items() if (start is None or f >= start) and (end is None or f <= end)}
    if not found:
        return None
    frames = sorted(found)
    f0, f1 = frames[0], frames[-1]
    L, R, Q = [], [], [[], [], [], []]
    last = (0.0, 0.0, [0.0] * 4)
    for f in range(f0, f1 + 1):
        if f in found:
            with Image.open(found[f]) as im:
                im = im.convert("RGB")
                k = max(1, im.width // width)
                a = np.ascontiguousarray(np.asarray(im)[::k, ::k])
            cx, cy, cw, ch = P.picture_crop(a.shape[1], a.shape[0])
            a = np.ascontiguousarray(a[cy:cy + ch, cx:cx + cw])
            h, w = a.shape[:2]
            y, r = P.frame_stats(a)
            quads = [P.frame_stats(np.ascontiguousarray(q))[0] for q in
                     (a[:h // 2, :w // 2], a[:h // 2, w // 2:], a[h // 2:, :w // 2], a[h // 2:, w // 2:])]
            last = (y, r, quads)
        L.append(last[0])
        R.append(last[1])
        for i in range(4):
            Q[i].append(last[2][i])
    return dict(frame0=f0, L=np.asarray(L), R=np.asarray(R), Q=[np.asarray(q) for q in Q], present=frames)


def analyse(frame_dir, start=None, end=None, strict=False):
    """Hard rules (post module) + quadrants + director's budget. Returns the report dict (JSON-able)."""
    P = post()
    s = series(frame_dir, P, start, end)
    if s is None:
        return None
    rep = P.public(P.analyze(s["L"], s["R"], frame0=s["frame0"], source=os.path.abspath(frame_dir)))
    rep["tool"] = "src/tools/flash_qc.py (hard rules: src/post/flash_qc.py)"
    n = len(s["L"])
    rep["present"] = len(s["present"])
    steps = np.diff(s["present"]) if len(s["present"]) > 1 else np.array([1])
    rep["sampling_step"] = int(np.median(steps))
    if len(s["present"]) < n:
        rep["warnings"].append(f"sparse sequence: {len(s['present'])}/{n} frames present (gaps held) - 1-frame "
                               f"flashes may be missed")
    quads = []
    for i, q in enumerate(s["Q"]):
        qr = P.analyze(q, None, frame0=s["frame0"])
        quads.append(dict(quadrant=i, max_flashes_per_24f=qr["max_flashes_per_24f"], fail_windows=qr["fail_windows"]))
        if qr["fail_windows"]:
            rep["problems"].append(f"quadrant {i} (25 % of the screen): > {P.FAIL_FLASHES} flashes per "
                                   f"{P.WINDOW} f in {qr['fail_windows'][:6]}")
    rep["quadrants"] = quads
    art = []
    onsets = [t["f1"] for t in rep.get("transitions", []) if t["dir"] > 0]
    for a, b in zip(onsets, onsets[1:]):
        if b - a < config.FLASH_MIN_GAP:
            art.append(dict(rule="flash_gap", frames=[a, b], gap=b - a, min_gap=config.FLASH_MIN_GAP))
    fw = config.FULL_WHITE
    for i0, i1, d in P.transitions(s["R"], P.RED_THR):
        fa, fb = s["frame0"] + i0, s["frame0"] + i1
        if d > 0 and fb - fa < RED_RAMP_MIN and not (fw[0] - 1 <= fb and fa <= fw[1] + 1):
            art.append(dict(rule="red_ramp", frame=int(fb), frames=int(fb - fa), min_frames=RED_RAMP_MIN))
    rep["art_direction"] = art
    fails = list(rep["problems"]) + ([f"director's budget (--strict): {a}" for a in art] if strict else [])
    rep["fails"] = fails
    rep["status"] = "FAIL" if fails else ("WARN" if (rep["warnings"] or art) else "PASS")
    rep["series"] = dict(frame0=s["frame0"], lum=[round(float(v), 4) for v in s["L"]])
    rep["_L"] = s["L"]
    return rep, P


def main():
    ap = argparse.ArgumentParser(prog="flash_qc.py")
    ap.add_argument("dir")
    ap.add_argument("--start", type=int, default=None)
    ap.add_argument("--end", type=int, default=None)
    ap.add_argument("--json", default=None)
    ap.add_argument("--plot", default=None)
    ap.add_argument("--strict", action="store_true", help="director's budget violations fail too")
    a = ap.parse_args()
    res = analyse(a.dir, a.start, a.end, strict=a.strict)
    if res is None:
        print(f"flash_qc: no #####.png frames in {a.dir}")
        sys.exit(2)
    rep, P = res
    out = a.json or os.path.join(a.dir, "flash_qc.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in rep.items() if not k.startswith("_")}, f, indent=1, default=str)
    if a.plot:
        P.plot(rep, a.plot, rep["_L"])
    for x in rep["fails"]:
        print("FAIL", x)
    for x in rep["art_direction"]:
        if not a.strict:
            print("WARN", x)
    for w in rep["warnings"]:
        print("warn:", w)
    print(f"flash_qc {rep['status']}: frames {rep['frame0']}-{rep['frame1']} ({rep['present']} present), max "
          f"{rep['max_flashes_per_24f']:.1f} flashes/24f -> {out}")
    sys.exit(1 if rep["status"] == "FAIL" else 0)


if __name__ == "__main__":
    main()
