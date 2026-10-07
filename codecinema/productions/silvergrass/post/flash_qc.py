#!/usr/bin/env python3
"""
codecinema/productions/silvergrass/post/flash_qc.py — photosensitivity QC for Duel in the Silver Grass.

Measures the mean relative luminance of every frame — sRGB/BT.709 code values -> linear light ->
Y = 0.2126 R + 0.7152 G + 0.0722 B, averaged over the PICTURE only (letterbox bars excluded) — of a
rendered PNG sequence or of a decoded video, then applies the general-flash rule of ITU-R BT.1702 /
WCAG 2.x as specified ("> 3 opposing >= 10 % luminance flips per 24 f outside FULL_WHITE = FAIL"):

  transition  a monotonic luminance change of >= 0.10 (10 % of full white). Hysteresis: a new transition
              starts only once the signal has moved >= 0.10 back from the previous extreme. It counts only
              when its darker state is below 0.80 (two very bright states are not a flash) and when it completes
              within 24 frames (slower changes — fades, dusk falling — are not flash components).
  flash       a pair of opposing transitions (up + down).
  FAIL        more than 3 flashes, i.e. >= 7 counted transitions, ending inside any 24-frame window.
              Transitions touching config.FULL_WHITE (+-1 f) — the film's one designed white-out — are ignored.
              (Counting single transitions instead would forbid the 2-flashes-per-second budget that
              DIRECTION §5 explicitly allows, so a "flip" is read as a flash, as in BT.1702.)
  FAIL        any frame outside FULL_WHITE whose mean luminance exceeds 0.92 (config: "only FULL_WHITE frames
              may exceed ~90 % full-frame white").
  WARN        more than 2 flashes (>= 5 transitions) per 24 f: over the DIRECTION budget (<= 2 per second).
  WARN        a flash whose bright state exceeds 0.70 (DIRECTION: other flashes <= 70 %).
  WARN        red flashes: the same counting applied to the saturated-red area fraction
              (pixels with R/(R+G+B) >= 0.8 and R >= 0.2; transition = >= 25 % of the picture).

Usage (.venv python):
  python codecinema/productions/silvergrass/post/flash_qc.py out/frames                 # rendered PNGs (absolute frame numbers from names)
  python codecinema/productions/silvergrass/post/flash_qc.py out/previews/preview_full.mp4 [--start 1]   # decoded output (letterbox cropped)
  options: --json PATH  --plot PATH.png  --start F (film frame of the first video frame)  --width 640
Exit code: 0 = PASS or WARN, 1 = FAIL, 2 = nothing to analyse.
Library: analyze_video(path, frame0, blackdetect=False) / analyze_frames(dir) -> report dict (see analyze()).
"""
from __future__ import annotations

from codecinema.productions import film_root, source_root

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = str(film_root("silvergrass"))
if os.path.join(str(source_root("silvergrass")), "common") not in sys.path:
    sys.path.insert(0, os.path.join(str(source_root("silvergrass")), "common"))
import config  # noqa: E402

FFMPEG, FFPROBE = config.FFMPEG, config.FFPROBE
THR = 0.10                  # transition size (fraction of full white)
DARK_MAX = 0.80             # the darker state of a counted transition must be below this
WINDOW = config.FPS         # frames (1 s)
FAIL_FLASHES = 3            # > 3 flashes per window -> FAIL
WARN_FLASHES = config.PHOTOSENSITIVITY["flashes_per_s"]   # > 2 flashes per window -> WARN (DIRECTION budget)
WHITE_MAX = 0.92            # mean luminance allowed outside FULL_WHITE (the QC gate; the design budget
                            # config.PHOTOSENSITIVITY['full_white_max'] is ~0.90)
PEAK_WARN = config.PHOTOSENSITIVITY["flash_max"]          # flash peak budget (0.70)
RED_THR = 0.25              # red-area transition size
FRAME_RE = re.compile(r"^(\d+)\.png$", re.IGNORECASE)

_lut = None


def srgb_lut():
    """uint8 code value -> linear light (sRGB / BT.709 display EOTF, WCAG 2.x formula)."""
    global _lut
    if _lut is None:
        c = np.arange(256, dtype=np.float64) / 255.0
        _lut = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4).astype(np.float32)
    return _lut


def frame_stats(rgb):
    """(mean relative luminance, saturated-red area fraction) of an HxWx3 uint8 frame."""
    lut = srgb_lut()
    lin = lut[rgb]
    y = lin[..., 0] * 0.2126 + lin[..., 1] * 0.7152 + lin[..., 2] * 0.0722
    f = rgb.astype(np.float32)
    s = f.sum(-1) + 1e-6
    red = (f[..., 0] / s >= 0.8) & (f[..., 0] >= 51.0)
    return float(y.mean()), float(red.mean())


# ============================================================================ sources
def picture_crop(w, h):
    """(x, y, w, h) of the scope picture inside a letterboxed frame (or the whole frame)."""
    ph, y0 = config.letterbox(w, h)
    if h > ph + 4:
        return 0, y0, w, ph
    return 0, 0, w, h


def probe_size(path):
    out = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                          "-of", "json", path], capture_output=True, text=True, check=True).stdout
    st = json.loads(out)["streams"][0]
    return int(st["width"]), int(st["height"])


BLACK_RE = re.compile(r"black_start:\s*([\d.]+)\s+black_end:\s*([\d.]+)")


def series_from_video(path, width=640, blackdetect=None):
    """Decode every frame of the video's picture area (letterbox cropped), point-sampled to `width`
    (point sampling keeps the linear-light mean unbiased). blackdetect = None or dict(d=, pix_th=, pic_th=)
    runs ffmpeg's blackdetect on the full-resolution picture in the same decode pass.
    Returns dict(L, R, crop, black=[(t0, t1)] seconds)."""
    w, h = probe_size(path)
    cx, cy, cw, ch = picture_crop(w, h)
    ow = min(width, cw)
    oh = int(round(ch * ow / cw / 2.0)) * 2
    chain = f"crop={cw}:{ch}:{cx}:{cy}"
    if blackdetect:
        bd = config.QC_BLACKDETECT
        chain += (f",blackdetect=d={blackdetect.get('d', bd['black_min_s'])}:"
                  f"pix_th={blackdetect.get('pix_th', bd['black_pix_th'])}:"
                  f"pic_th={blackdetect.get('pic_th', bd['black_pic_th'])}")
    chain += (f",scale={ow}:{oh}:flags=neighbor+accurate_rnd+full_chroma_int:in_color_matrix=bt709:in_range=tv,"
              f"format=rgb24")
    fd, errpath = tempfile.mkstemp(prefix="flashqc_", suffix=".log")
    os.close(fd)
    L, R = [], []
    try:
        with open(errpath, "w") as errf:
            p = subprocess.Popen([FFMPEG, "-hide_banner", "-nostats", "-loglevel", "info", "-i", path, "-map", "0:v:0",
                                  "-vf", chain, "-f", "rawvideo", "-"], stdout=subprocess.PIPE, stderr=errf)
            fb = ow * oh * 3
            while True:
                buf = p.stdout.read(fb)
                if not buf or len(buf) < fb:
                    break
                y, r = frame_stats(np.frombuffer(buf, np.uint8).reshape(oh, ow, 3))
                L.append(y)
                R.append(r)
            p.wait()
        with open(errpath) as fh:
            log = fh.read()
        if p.returncode != 0:
            raise RuntimeError(f"ffmpeg decode failed ({p.returncode}): {log[-800:]}")
    finally:
        os.remove(errpath)
    black = [(float(a), float(b)) for a, b in BLACK_RE.findall(log)] if blackdetect else []
    return dict(L=np.asarray(L, np.float64), R=np.asarray(R, np.float64), crop=(cx, cy, cw, ch), size=(w, h),
                black=black)


def series_from_frames(frames_dir, start=None, end=None, width=640):
    """Luminance of a PNG sequence named by absolute film frame. Missing frames hold the previous one
    (exactly what the assembler shows), and the report says how sparse the sequence was."""
    found = {}
    for name in os.listdir(frames_dir):
        m = FRAME_RE.match(name)
        if m:
            found[int(m.group(1))] = os.path.join(frames_dir, name)
    if not found:
        return None
    fr = sorted(found)
    start = fr[0] if start is None else start
    end = fr[-1] if end is None else end
    L, R, have = [], [], []
    last = (0.0, 0.0)
    for f in range(start, end + 1):
        if f in found:
            with Image.open(found[f]) as im:
                im = im.convert("RGB")
                k = max(1, im.width // width)
                a = np.asarray(im)[::k, ::k]
            last = frame_stats(np.ascontiguousarray(a))
            have.append(f)
        L.append(last[0])
        R.append(last[1])
    return dict(L=np.asarray(L), R=np.asarray(R), frame0=start, present=have)


# ============================================================================ analysis
def transitions(L, thr=THR):
    """Hysteresis transition finder -> list of [i0, i1, direction] (indices into L)."""
    out = []
    n = len(L)
    if n < 2:
        return out
    lo_i = hi_i = 0
    d = 0
    ext = 0
    for i in range(1, n):
        x = L[i]
        if d == 0:
            if x < L[lo_i]:
                lo_i = i
            if x > L[hi_i]:
                hi_i = i
            if L[hi_i] - L[lo_i] >= thr:
                if hi_i > lo_i:
                    out.append([lo_i, hi_i, 1])
                    d, ext = 1, hi_i
                else:
                    out.append([hi_i, lo_i, -1])
                    d, ext = -1, lo_i
        elif d == 1:
            if x >= L[ext]:
                ext = i
                out[-1][1] = i
            elif L[ext] - x >= thr:
                out.append([ext, i, -1])
                d, ext = -1, i
        else:
            if x <= L[ext]:
                ext = i
                out[-1][1] = i
            elif x - L[ext] >= thr:
                out.append([ext, i, 1])
                d, ext = 1, i
    return out


def _windows_over(ends, limit, window=WINDOW):
    """[(first_end, last_end, count)] of maximal groups where >= limit transitions end within `window` frames."""
    ends = np.asarray(sorted(ends))
    bad = []
    for j in range(len(ends)):
        k = np.searchsorted(ends, ends[j] - window + 1)
        c = j - k + 1
        if c >= limit:
            a, b = int(ends[k]), int(ends[j])
            if bad and a <= bad[-1][1]:
                bad[-1] = (bad[-1][0], b, max(bad[-1][2], c))
            else:
                bad.append((a, b, c))
    return bad


def _max_in_window(ends, window=WINDOW):
    ends = np.asarray(sorted(ends))
    best, at = 0, None
    for j in range(len(ends)):
        k = np.searchsorted(ends, ends[j] - window + 1)
        if j - k + 1 > best:
            best, at = j - k + 1, (int(ends[k]), int(ends[j]))
    return best, at


def analyze(L, R=None, frame0=config.FRAME_START, exclude=(config.FULL_WHITE,), source=None):
    """Apply the rules to a luminance series (index 0 = film frame `frame0`). Returns a JSON-able report."""
    L = np.asarray(L, np.float64)
    n = len(L)
    fr = lambda i: int(frame0 + i)                                        # noqa: E731
    near_ex = lambda f: any(a - 1 <= f <= b + 1 for a, b in exclude)       # noqa: E731
    spans_ex = lambda f0, f1: any(f0 < a and f1 > b for a, b in exclude)   # noqa: E731
    counted, ignored_white, ignored_bright, ignored_slow = [], 0, 0, 0
    for i0, i1, d in transitions(L):
        f0, f1 = fr(i0), fr(i1)
        if near_ex(f0) or near_ex(f1) or spans_ex(f0, f1):
            ignored_white += 1
            continue
        if f1 - f0 > WINDOW:                   # a change slower than 1 s is not a flash component
            ignored_slow += 1
            continue
        lo, hi = min(L[i0], L[i1]), max(L[i0], L[i1])
        if lo >= DARK_MAX:
            ignored_bright += 1
            continue
        counted.append(dict(f0=f0, f1=f1, dir=int(d), lo=round(float(lo), 4), hi=round(float(hi), 4)))
    ends = [t["f1"] for t in counted]
    fail_w = _windows_over(ends, 2 * FAIL_FLASHES + 1)
    warn_w = _windows_over(ends, 2 * WARN_FLASHES + 1)
    mx, mx_at = _max_in_window(ends)
    white = [fr(i) for i in np.flatnonzero(L > WHITE_MAX) if not any(a <= fr(i) <= b for a, b in exclude)]
    peaks = sorted({t["f1"] if t["dir"] > 0 else t["f0"] for t in counted if t["hi"] > PEAK_WARN})
    problems, warnings = [], []
    if fail_w:
        problems.append(f"{len(fail_w)} window(s) with > {FAIL_FLASHES} flashes per {WINDOW} f: " +
                        ", ".join(f"{a}-{b} ({c} transitions)" for a, b, c in fail_w[:12]))
    if white:
        problems.append(f"{len(white)} frame(s) above {WHITE_MAX:.2f} mean luminance outside FULL_WHITE {exclude}: "
                        f"{white[:12]}")
    if warn_w and not fail_w:
        warnings.append(f"> {WARN_FLASHES} flashes per second (DIRECTION budget) in: " +
                        ", ".join(f"{a}-{b}" for a, b, _ in warn_w[:12]))
    if peaks:
        warnings.append(f"{len(peaks)} flash peak(s) above {PEAK_WARN:.0%} luminance: {peaks[:12]}")
    red = None
    if R is not None and len(R) == n:
        rt = [t for t in transitions(np.asarray(R, np.float64), RED_THR)
              if not (near_ex(fr(t[0])) or near_ex(fr(t[1])))]
        rmx, rat = _max_in_window([fr(t[1]) for t in rt])
        red = dict(transitions=len(rt), max_per_window=rmx, worst=rat, max_fraction=round(float(np.max(R)), 4))
        if rmx >= 2 * FAIL_FLASHES + 1:
            warnings.append(f"red flashes: {rmx} saturated-red transitions within {WINDOW} f at {rat}")
    status = "FAIL" if problems else ("WARN" if warnings else "PASS")
    return dict(source=source, frames=n, frame0=int(frame0), frame1=int(frame0 + n - 1), status=status,
                problems=problems, warnings=warnings,
                luminance=dict(min=round(float(L.min()), 4) if n else None, max=round(float(L.max()), 4) if n else None,
                               mean=round(float(L.mean()), 4) if n else None),
                transitions_counted=len(counted), transitions_ignored_full_white=ignored_white,
                transitions_ignored_bright=ignored_bright, transitions_ignored_slow=ignored_slow,
                max_transitions_per_24f=int(mx),
                max_flashes_per_24f=mx / 2.0, worst_window=mx_at, fail_windows=fail_w, warn_windows=warn_w,
                frames_over_white=white, transitions=counted[:400], red=red,
                rule=dict(threshold=THR, dark_max=DARK_MAX, window=WINDOW, fail_flashes_gt=FAIL_FLASHES,
                          warn_flashes_gt=WARN_FLASHES, white_max=WHITE_MAX, exclude=[list(e) for e in exclude]))


def analyze_video(path, frame0=config.FRAME_START, blackdetect=None, width=640):
    s = series_from_video(path, width=width, blackdetect=blackdetect)
    rep = analyze(s["L"], s["R"], frame0=frame0, source=os.path.abspath(path))
    rep["crop"] = list(s["crop"])
    rep["_L"] = s["L"]
    if blackdetect is not None:
        rep["black"] = [(frame0 + int(round(a * config.FPS)), frame0 + int(round(b * config.FPS)) - 1)
                        for a, b in s["black"]]
    return rep


def analyze_frames(frames_dir, start=None, end=None, width=640):
    s = series_from_frames(frames_dir, start, end, width)
    if s is None:
        return None
    rep = analyze(s["L"], s["R"], frame0=s["frame0"], source=os.path.abspath(frames_dir))
    n = len(s["L"])
    rep["present"] = len(s["present"])
    if len(s["present"]) < n:
        rep["warnings"].append(f"sparse sequence: {len(s['present'])}/{n} frames present (gaps held) — flash timing "
                               f"is only exact on consecutive frames")
        if rep["status"] == "PASS":
            rep["status"] = "WARN"
    rep["_L"] = s["L"]
    return rep


def plot(rep, path, L=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    L = rep.get("_L") if L is None else L
    f0 = rep["frame0"]
    x = np.arange(f0, f0 + len(L))
    fig, ax = plt.subplots(figsize=(18, 3.6))
    for a, b in rep["rule"]["exclude"]:
        ax.axvspan(a - 0.5, b + 0.5, color="gold", alpha=0.35, lw=0)
    for a, b, _ in rep["warn_windows"]:
        ax.axvspan(a - WINDOW + 1, b, color="orange", alpha=0.2, lw=0)
    for a, b, _ in rep["fail_windows"]:
        ax.axvspan(a - WINDOW + 1, b, color="red", alpha=0.3, lw=0)
    ax.plot(x, L, lw=0.8, color="k")
    for t in rep["transitions"]:
        ax.plot([t["f0"], t["f1"]], [t["lo"] if t["dir"] > 0 else t["hi"], t["hi"] if t["dir"] > 0 else t["lo"]],
                color="tab:red" if t["dir"] > 0 else "tab:blue", lw=1.2)
    for s in config.SHOTS:
        if f0 <= s["start"] <= x[-1]:
            ax.axvline(s["start"], color="0.7", lw=0.5)
            ax.text(s["start"] + 2, 0.97, s["id"], fontsize=6, va="top", color="0.4")
    ax.set_ylim(0, 1)
    ax.set_xlim(x[0], x[-1])
    ax.set_ylabel("mean rel. luminance")
    ax.set_title(f"flash QC {rep['status']}: max {rep['max_flashes_per_24f']:.1f} flashes / 24 f  "
                 f"({rep['transitions_counted']} transitions)  {os.path.basename(str(rep['source']))}", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=80)
    plt.close(fig)
    return path


def public(rep):
    """Report without the private numpy series (JSON-able)."""
    return {k: v for k, v in rep.items() if not k.startswith("_")}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="frames dir (#####.png) or a video file")
    ap.add_argument("--start", type=int, default=None, help="film frame of the first video frame (default 1)")
    ap.add_argument("--end", type=int, default=None, help="frames dir only: last frame")
    ap.add_argument("--json", default=None)
    ap.add_argument("--plot", default=None)
    ap.add_argument("--width", type=int, default=640)
    a = ap.parse_args(argv)
    if os.path.isdir(a.source):
        rep = analyze_frames(a.source, a.start, a.end, a.width)
        if rep is None:
            print(f"[flash_qc] no #####.png frames in {a.source}")
            return 2
    else:
        rep = analyze_video(a.source, a.start or config.FRAME_START, width=a.width)
    if a.plot:
        plot(rep, a.plot)
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(public(rep), fh, indent=1)
    print(f"[flash_qc] {rep['status']}  frames {rep['frame0']}-{rep['frame1']}  max {rep['max_flashes_per_24f']:.1f} "
          f"flashes/24f  transitions {rep['transitions_counted']} (+{rep['transitions_ignored_full_white']} in FULL_WHITE)"
          f"  lum {rep['luminance']}")
    for p in rep["problems"]:
        print("  FAIL:", p)
    for w in rep["warnings"]:
        print("  warn:", w)
    return 1 if rep["status"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
