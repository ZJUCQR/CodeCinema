#!/usr/bin/env python3
"""
src/post/assemble.py — finishing / final assembly for Duel in the Silver Grass.

  picture PNGs (any size, 2.35:1)  ─ frame plan (RENDER_SKIP black, holds, slates) ─ S29 fade to black (picture)
      ─ scale to 1920 wide (lanczos, RGB -> BT.709 limited 4:4:4) ─ [--grain] ─ pad to 1920x1080 letterbox
      ─ overlay title PNG sequences (straight alpha, private hard-linked snapshot) at their exact frame ranges
      ─ [--preview: downscale to 960x540] ─ yuv420p ─ libx264
  audio WAV ─ 48 kHz stereo ─ sample-exact slice of the range ─ [final: AAC true-peak conditioning] ─ AAC
      (encoded first, then stream-copied into the MP4)
  verify ─ ffprobe (frames, fps, size, duration, AAC 48 kHz stereo) ─ [final: flash QC, blackdetect, EBU R128]

Frame plan (per output frame f):
  * f inside config.RENDER_SKIP              -> black (designed black: S01, the tail of S29), never "missing"
  * rendered                                 -> itself
  * missing, a rendered frame of the SAME shot within the hold cap (previews: max(step, 12) frames)
                                             -> held (the newest earlier one, else the next one: cuts stay exact)
  * otherwise, preview                       -> a 'NOT RENDERED · <shot>' slate (--missing black: black)
  * --final                                  -> FAILS if any frame outside RENDER_SKIP is missing or is not
                                                config.RES_X x RES_Y, unless --allow-holds (then: held, else black)
S29 fade: post owns the picture fade to black from FADE_START (3770) to the RENDER_SKIP tail (3811); it is applied
to the picture only (before the title overlay) so the 'End' card stays crisp. --fade auto skips it if the renders already fade.

Audio rules (final mode):
  * --audio auto = out/audio/final_mix.wav; missing -> error (unless --allow-silent). Previews fall back to
    out/audio/demo_mix.wav (logged).
  * the WAV must be the film length within 1 frame (never padded/trimmed by more than that);
  * a FULL final also requires out/audio/mix_report.json to describe this WAV, built from config.EVENTS_JSON
    (not a draft), no older than out/events.json, length_s == expected_length_s (within 1 sample);
  * AAC headroom: the encoder overshoots true peak; if the decoded AAC exceeds -1 dBTP, a 4x-oversampled lookahead
    limiter (ceiling -2.5 dBTP, lowered as needed) conditions the peaks before encoding (loudness ~unchanged).
QC in the final verify (hard gates unless --allow-qc-fail): src/post/flash_qc.py on the decoded output,
blackdetect outside S01 / FADE_START..end, EBU R128 on the delivered AAC (-14 LUFS +-1 LU on a full final,
true peak <= -1 dBTP). A JSON QC report is written next to the output (full final: out/final_qc.json).

Usage (.venv python):
  python src/post/assemble.py --preview                              # whole film, 960x540, demo/final audio
  python src/post/assemble.py --final                                # delivery master -> config.FINAL_VIDEO
  python src/post/assemble.py --final --range 433 1632               # one act at full quality (out/previews/)
Options: --frames DIR (default out/frames) --audio auto|none|PATH --out PATH --no-titles --grain N (0=off)
         --step K --missing slate|black --allow-holds --allow-silent --allow-qc-fail --fade auto|on|off --qc
         --crf N --mac-copy --mix-report PATH --events PATH --keep-temp --dry-run --titles-force --jobs N
"""
from __future__ import annotations

import argparse
import bisect
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
for _p in (os.path.join(ROOT, "src", "common"), HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import config  # noqa: E402
import procutil  # noqa: E402

FFMPEG, FFPROBE = config.FFMPEG, config.FFPROBE
FPS = config.FPS
W, H = config.DELIVERY_X, config.DELIVERY_Y
SR = config.AUDIO_SR
if SR % FPS:
    raise ValueError(f"audio sample rate {SR} Hz is not a whole number of samples per frame at {FPS} fps "
                     f"(the sample-exact audio slicing needs it)")
SAMPLES_PER_FRAME = SR // FPS            # 2000 at 48 kHz / 24 fps
FILM_FRAMES = config.FRAME_END - config.FRAME_START + 1
FILM_SECONDS = FILM_FRAMES / FPS
FRAME_RE = re.compile(r"^(\d+)\.png$", re.IGNORECASE)
HOLD_CAP = 12                            # previews: longest hold (frames) before a slate appears

VIDEO = config.VIDEO
MODES = {
    "preview": dict(size=(int(VIDEO["preview_width"]), int(VIDEO["preview_height"])),
                    vcodec=["-c:v", VIDEO["codec"], "-preset", VIDEO["preview_preset"], "-crf",
                            str(int(VIDEO["preview_crf"])), "-pix_fmt", VIDEO["pix_fmt"]],
                    acodec=["-c:a", "aac", "-b:a", VIDEO["preview_audio_bitrate"], "-ar", str(SR), "-ac", "2"]),
    # Level 4.1 High: max 62.5 Mbit/s, CPB 62.5 Mbit — enforced so dense grass/rain/grain frames stay decodable
    "final": dict(size=(W, H), vcodec=["-c:v", VIDEO["codec"], "-preset", VIDEO["preset"], "-crf",
                                       str(int(VIDEO["crf"])), "-tune", "film", "-profile:v", "high", "-level:v", "4.1",
                                       "-maxrate", "50M", "-bufsize", "62.5M", "-pix_fmt", VIDEO["pix_fmt"]],
                  acodec=["-c:a", "aac", "-b:a", VIDEO["audio_bitrate"], "-ar", str(SR), "-ac", "2"]),
}
COLOR_TAGS = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]

# S29: the picture fades to black from FADE_START; the frames from FADE_BLACK (the RENDER_SKIP tail) on are black.
FADE_START, FADE_BLACK = config.FADE_TO_BLACK
TP_CEILING = config.AUDIO_TRUE_PEAK_DB   # dBTP of the delivered (decoded) AAC
PRE_CEILING = config.AUDIO_AAC_PRE_LIMITER_DB   # first limiter ceiling (dBTP) before the AAC encoder
LUFS_TARGET, LUFS_TOL = config.AUDIO_TARGET_LUFS, config.AUDIO_LOUDNESS_TOL_LU


def log(*a):
    print("[assemble]", *a, flush=True)


class AssemblyError(SystemExit):
    """A refused assembly (bad inputs for the requested mode). Exit code 1 with the message."""


def in_skip(f):
    return any(a <= f <= b for a, b in config.RENDER_SKIP)


def ranges_str(frames):
    """Compact '1-4, 9, 12-40' string for a sorted list of ints."""
    frames = sorted(frames)
    if not frames:
        return "-"
    out, a, b = [], frames[0], frames[0]
    for x in frames[1:]:
        if x == b + 1:
            b = x
            continue
        out.append(f"{a}-{b}" if b > a else f"{a}")
        a = b = x
    out.append(f"{a}-{b}" if b > a else f"{a}")
    s = ", ".join(out)
    return s if len(s) < 300 else s[:300] + " ..."


def shot_of(f):
    s = config.shot_at(f)
    return s["id"] if s else None


# ============================================================================ frame sourcing
def scan_frames(frames_dir):
    """{frame_number: path} for every NNNNN.png in the directory (numbering is absolute film frames)."""
    found = {}
    if not frames_dir or not os.path.isdir(frames_dir):
        return found
    for name in os.listdir(frames_dir):
        m = FRAME_RE.match(name)
        if m:
            found[int(m.group(1))] = os.path.join(frames_dir, name)
    return found


def frame_info(found, frames):
    """{frame: (size, mode)} read from the PNG headers (cheap)."""
    info = {}
    for f in frames:
        with Image.open(found[f]) as im:
            info[f] = (im.size, im.mode)
    return info


def infer_step(found):
    fr = sorted(found)
    if len(fr) < 3:
        return 1
    d = Counter(b - a for a, b in zip(fr, fr[1:]))
    return max(1, d.most_common(1)[0][0])


def plan_frames(found, start, end, mode="preview", step=None, allow_holds=False, missing=None):
    """Per output frame: ('src', n) | ('black', reason) | ('slate', shot_id). See the module docstring.
    Returns (plan, stats) where stats lists the rendered / held / unfilled / skip (designed black) frames."""
    usable = sorted(f for f in found if not in_skip(f))
    have = set(usable)
    step = step or infer_step(found)
    if mode == "final":
        cap = None if allow_holds else 0
        missing = "black"
    else:
        cap = max(step, HOLD_CAP)
        missing = missing or "slate"
    plan = []
    st = dict(rendered=[], held=[], unfilled=[], skip=[], step=step, cap=cap)
    for f in range(start, end + 1):
        if in_skip(f):
            plan.append(("black", "skip"))
            st["skip"].append(f)
            continue
        if f in have:
            plan.append(("src", f))
            st["rendered"].append(f)
            continue
        sh = shot_of(f)
        j = bisect.bisect_right(usable, f)
        prev = usable[j - 1] if j > 0 else None
        nxt = usable[j] if j < len(usable) else None
        ok = lambda n, gap: n is not None and shot_of(n) == sh and (cap is None or gap <= cap)  # noqa: E731
        choice = None
        if ok(prev, f - (prev or 0)):
            choice = prev
        elif ok(nxt, (nxt or 0) - f):
            choice = nxt
        elif mode == "final" and allow_holds and prev is not None:
            choice = prev                                   # draft final: hold across a cut rather than black
        if choice is not None:
            plan.append(("src", choice))
            st["held"].append(f)
        else:
            plan.append(("slate", sh) if missing == "slate" else ("black", "missing"))
            st["unfilled"].append(f)
    return plan, st


def fade_factor(f):
    """Picture multiplier of the S29 fade to black: 1 before FADE_START, eased to 0 at FADE_BLACK."""
    if f < FADE_START:
        return 1.0
    if f >= FADE_BLACK:
        return 0.0
    u = (f - FADE_START) / float(FADE_BLACK - FADE_START)
    return 1.0 - u * u * (3.0 - 2.0 * u)


def _mean_luma(path):
    with Image.open(path) as im:
        a = np.asarray(im.convert("L").reduce(4), np.float32) / 255.0
    return float(a.mean())


def renders_already_fade(found):
    """True if the rendered frames themselves fade to black toward FADE_BLACK (then post must not fade again),
    False if they do not, None if it cannot be judged (no frames near the fade)."""
    usable = sorted(f for f in found if not in_skip(f))
    a = [f for f in usable if FADE_START - 12 <= f <= FADE_START + 2]
    b = [f for f in usable if FADE_BLACK - 8 <= f < FADE_BLACK]
    if not a or not b:
        return None
    la, lb = _mean_luma(found[a[-1]]), _mean_luma(found[b[-1]])
    return bool(lb < 0.03 and (la < 0.02 or lb < 0.25 * la))


# ============================================================================ picture sources
def _has_alpha(mode, info=None):
    return mode in ("RGBA", "LA", "PA") or (mode == "P" and bool(info and "transparency" in info))


def _to_layout(im, layout):
    """Any PIL image -> 'RGB' (transparent pixels composited over black) or 'RGBA'."""
    if layout == "RGBA":
        return im.convert("RGBA")
    if _has_alpha(im.mode, im.info):
        rgba = im.convert("RGBA")
        out = Image.new("RGB", rgba.size, (0, 0, 0))
        out.paste(rgba, mask=rgba.getchannel("A"))
        return out
    return im.convert("RGB")


def make_slate(path, size, shot_id, layout="RGB"):
    """Dark 'NOT RENDERED' slate for previews (clearly not a designed black)."""
    import titles as T
    w, h = size
    im = Image.new("RGB", size, (24, 24, 27))
    d = ImageDraw.Draw(im)
    s = next((x for x in config.SHOTS if x["id"] == shot_id), None)
    try:
        big = T.get_font("kaiti", max(12, h // 9))
        small = T.get_font("kaiti", max(9, h // 20))
    except (RuntimeError, OSError):              # no Kaiti font configured: Pillow's default face (preview slates only)
        big, small = ImageFont.load_default(max(12, h // 9)), ImageFont.load_default(max(9, h // 20))
    t1 = "NOT RENDERED"
    t2 = f"{shot_id}  ·  {s['start']}–{s['end']}" if s else "no shot"
    for txt, font, y, col in ((t1, big, 0.42, (150, 148, 142)), (t2, small, 0.60, (110, 108, 104))):
        tw = d.textlength(txt, font=font)
        d.text(((w - tw) / 2, h * y), txt, font=font, fill=col, anchor="ls")
    d.rectangle([2, 2, w - 3, h - 3], outline=(60, 60, 64), width=max(1, h // 200))
    _to_layout(im, layout).save(path)
    return path


def build_picture(plan, found, start, tmp, fade_on):
    """Resolve the plan into one image path per output frame (all the same size/layout).
    Returns (seq, size, derived_counts)."""
    used = sorted({v for k, v in plan if k == "src"})
    info = frame_info(found, used)
    if info:
        size = Counter(sz for sz, _ in info.values()).most_common(1)[0][0]
        n_alpha = sum(1 for _, md in info.values() if _has_alpha(md))
        layout = "RGBA" if n_alpha * 2 > len(info) else "RGB"     # majority pixel layout; RGBA -> premultiplied
    else:                                                          # over black in ffmpeg (no per-frame rewrite)
        size, layout = (config.RES_X, config.RES_Y), "RGB"
    norm_dir = os.path.join(tmp, "norm")
    os.makedirs(norm_dir, exist_ok=True)
    norm = {}
    fixed = []
    for f in used:
        sz, md = info[f]
        if sz == size and md == layout:
            norm[f] = found[f]
            continue
        with Image.open(found[f]) as im:
            im = _to_layout(im, layout)
            if im.size != size:
                im = im.resize(size, Image.LANCZOS)
            p = os.path.join(norm_dir, f"{f:05d}.png")
            im.save(p, compress_level=1)
        norm[f] = p
        fixed.append(f)
    if fixed:
        log(f"normalised {len(fixed)} source frame(s) of other size/mode to {size[0]}x{size[1]} {layout}: "
            f"{ranges_str(fixed)}")
    sizes = Counter(sz for sz, _ in info.values())
    if len(sizes) > 1:
        log(f"WARNING mixed input sizes {dict(sizes)}")
    black = os.path.join(tmp, "black.png")
    Image.new(layout, size, (0, 0, 0, 255) if layout == "RGBA" else (0, 0, 0)).save(black)
    slates = {}
    fade_dir = os.path.join(tmp, "fade")
    n_fade = 0
    seq = []
    for i, (kind, val) in enumerate(plan):
        f = start + i
        if kind == "black":
            seq.append(black)
            continue
        if kind == "slate":
            if val not in slates:
                slates[val] = make_slate(os.path.join(tmp, f"slate_{val}.png"), size, val, layout)
            seq.append(slates[val])
            continue
        p = norm[val]
        k = fade_factor(f) if fade_on else 1.0
        if k < 0.9999:
            os.makedirs(fade_dir, exist_ok=True)
            q = os.path.join(fade_dir, f"{f:05d}.png")
            with Image.open(p) as im:
                a = np.asarray(im.convert(layout), np.float32)
            a[..., :3] *= k
            Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8), layout).save(q, compress_level=1)
            p = q
            n_fade += 1
        seq.append(p)
    return seq, size, layout, dict(normalised=len(fixed), faded=n_fade, slates=sorted(s for s in slates if s))


def picture_geometry(size):
    """Scaled picture size (1920 wide, even height) and letterbox offset for an input frame size."""
    iw, ih = size
    ph = int(round(W * ih / iw / 2.0)) * 2
    if ph > H:
        raise AssemblyError(f"input aspect {iw}x{ih} is taller than 16:9 — not a scope frame")
    return ph, (H - ph) // 2


def link_sequence(dirpath, sources):
    """Link sources[i] -> dirpath/%05d.png (i+1): symlink, else hard link, else copy (procutil.link_or_copy)."""
    os.makedirs(dirpath, exist_ok=True)
    for i, src in enumerate(sources, 1):
        procutil.link_or_copy(src, os.path.join(dirpath, f"{i:05d}.png"))


# ============================================================================ titles
def title_sequence(start, end, tmp, force=False, jobs=None):
    """Snapshot (hard-link, under the titles lock) the cards overlapping [start, end] and build the per-frame
    title sequence in tmp/t. Returns the ids used (empty -> no title input)."""
    import titles as T
    ids = [t["id"] for t in config.TITLES if not (t["end"] < start or t["start"] > end)]
    if not ids:
        return []
    dirs = T.snapshot_titles(ids, os.path.join(tmp, "titles"), force=force, jobs=jobs)
    per = [[] for _ in range(end - start + 1)]
    for t in config.TITLES:
        if t["id"] not in dirs:
            continue
        for f in range(max(start, t["start"]), min(end, t["end"]) + 1):
            per[f - start].append(os.path.join(dirs[t["id"]], f"{f - t['start'] + 1:05d}.png"))
    blank = os.path.join(tmp, "blank_rgba.png")
    Image.new("RGBA", (W, H), (0, 0, 0, 0)).save(blank)
    seq = []
    for k, paths in enumerate(per):
        if not paths:
            seq.append(blank)
        elif len(paths) == 1:
            seq.append(paths[0])
        else:                                   # overlapping titles: composite once, in list order
            im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            for p in paths:
                im = Image.alpha_composite(im, Image.open(p).convert("RGBA"))
            p = os.path.join(tmp, "tover", f"{k + 1:05d}.png")
            os.makedirs(os.path.dirname(p), exist_ok=True)
            im.save(p)
            seq.append(p)
    link_sequence(os.path.join(tmp, "t"), seq)
    return ids


# ============================================================================ audio
def probe_audio(path):
    out = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "a:0", "-show_entries",
                          "stream=sample_rate,channels,duration,duration_ts,codec_name:format=duration", "-of", "json",
                          path], capture_output=True, text=True, check=True).stdout
    j = json.loads(out)
    st = (j.get("streams") or [{}])[0]
    dur = float(st.get("duration") or j.get("format", {}).get("duration") or 0.0)
    return dict(sr=int(st.get("sample_rate", 0) or 0), ch=int(st.get("channels", 0) or 0), dur=dur,
                codec=st.get("codec_name"))


def resolve_audio(arg, mode, allow_silent=False, audio_dir=None):
    """--audio auto|none|PATH -> path or None, applying the mode's rules."""
    audio_dir = audio_dir or config.AUDIO_DIR
    if arg in (None, "", "auto"):
        final_mix = os.path.join(audio_dir, os.path.basename(config.FINAL_MIX_WAV))
        demo = os.path.join(audio_dir, os.path.basename(config.DEMO_MIX_WAV))
        if os.path.exists(final_mix):
            log(f"--audio auto -> {final_mix}")
            return final_mix
        if mode == "final":
            if allow_silent:
                log(f"WARNING --audio auto: {final_mix} not found; --allow-silent -> SILENT master")
                return None
            raise AssemblyError(f"final master needs the real mix, but {final_mix} does not exist. Run src/audio/mix.py "
                                f"after the Blender build has written {config.EVENTS_JSON} (or pass --audio PATH, or "
                                f"--allow-silent for a picture-only master).")
        if os.path.exists(demo):
            log(f"--audio auto: {os.path.basename(final_mix)} not found -> DEMO mix {demo} "
                f"(draft events; preview only)")
            return demo
        log("--audio auto: no mix found -> video only")
        return None
    if arg == "none":
        if mode == "final" and not allow_silent:
            raise AssemblyError("--audio none in final mode needs --allow-silent")
        return None
    if not os.path.exists(arg):
        raise AssemblyError(f"audio file not found: {arg}")
    return os.path.abspath(arg)


def audio_provenance(audio, report_path=None, events_path=None):
    """Problems (list of str) that make `audio` unfit for the delivery master, from out/audio/mix_report.json."""
    report_path = report_path or config.MIX_REPORT_JSON
    events_path = os.path.realpath(events_path or config.EVENTS_JSON)
    rp = os.path.realpath
    probs, info = [], dict(report=report_path, events=events_path)
    if not os.path.exists(events_path):
        probs.append(f"{events_path} does not exist (the real animation events the mix must be built from)")
    try:
        with open(report_path, encoding="utf-8") as fh:
            rep = json.load(fh)
    except (OSError, ValueError) as e:
        probs.append(f"mix report {report_path} missing or unreadable ({e.__class__.__name__})")
        return probs, info
    out = rep.get("output")
    if not out or rp(out) != rp(audio):
        probs.append(f"mix report describes {out!r}, not {audio!r} (stale or foreign report)")
    src = rep.get("events_source")
    if not src or rp(src) != events_path:
        probs.append(f"mix was built from events {src!r}, not {events_path!r}")
    if rep.get("events_draft"):
        probs.append("mix report says events_draft = true (draft events)")
    if os.path.exists(events_path) and os.path.exists(audio) and os.path.getmtime(audio) < os.path.getmtime(events_path):
        probs.append(f"{os.path.basename(audio)} is older than {os.path.basename(events_path)} (re-run src/audio/mix.py)")
    ls, es = rep.get("length_s"), rep.get("expected_length_s")
    if ls is None or es is None or abs(float(ls) - float(es)) > 1.0 / SR + 1e-9:
        probs.append(f"mix length_s {ls} != expected_length_s {es} (tolerance 1 sample)")
    if es is not None and abs(float(es) - FILM_SECONDS) > 1e-6:
        probs.append(f"mix expected_length_s {es} != film length {FILM_SECONDS}")
    info.update(lufs=rep.get("integrated_lufs"), true_peak=rep.get("true_peak_dbtp"), events_source=src,
                length_s=ls, draft=rep.get("events_draft"))
    return probs, info


R128_I = re.compile(r"I:\s+(-?[\d.]+|-inf) LUFS")
R128_TP = re.compile(r"Peak:\s+(-?[\d.]+|-inf) dBFS")


def r128(path, pre_chain=None):
    """(integrated LUFS, true peak dBTP) of the first audio stream (optionally through a filter chain)."""
    chain = (pre_chain + "," if pre_chain else "") + "ebur128=peak=true:framelog=quiet"
    r = subprocess.run([FFMPEG, "-hide_banner", "-nostats", "-i", path, "-filter_complex", f"[0:a:0]{chain}[o]",
                        "-map", "[o]", "-f", "null", "-"], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ebur128 failed on {path}: {r.stderr[-500:]}")
    i, p = R128_I.findall(r.stderr), R128_TP.findall(r.stderr)
    conv = lambda v: float("-inf") if v == "-inf" else float(v)   # noqa: E731
    return (conv(i[-1]) if i else None), (conv(p[-1]) if p else None)


def encode_audio(audio, a0, a1, n_samp, mode, tmp, condition=True, dry_run=False):
    """Encode the sample-exact slice [a0, a1) of the WAV (film timeline) to AAC in tmp. Final mode: if the decoded
    AAC would exceed TP_CEILING, condition the peaks with a 4x-oversampled lookahead limiter (ceiling PRE_CEILING,
    lowered by the measured excess, at most 4 passes). Returns dict(path, cmd, lufs, tp, ...)."""
    spec = MODES[mode]
    base = (f"[0:a]aresample={SR},aformat=sample_fmts=fltp:sample_rates={SR}:channel_layouts=stereo,"
            f"atrim=start_sample={a0}:end_sample={a1},asetpts=PTS-STARTPTS")
    tail = f"apad=whole_len={n_samp},atrim=end_sample={n_samp}"
    out = os.path.join(tmp, "audio.m4a")

    def run(lim_db):
        lim = ""
        if lim_db is not None:
            lim = (f",aresample={SR * 4},alimiter=limit={10 ** (lim_db / 20.0):.6f}:attack=0.5:release=40:"
                   f"level=disabled:latency=1,aresample={SR}")
        cmd = [FFMPEG, "-hide_banner", "-y", "-loglevel", "error", "-i", os.path.abspath(audio), "-filter_complex",
               f"{base}{lim},{tail}[a]", "-map", "[a]", *spec["acodec"], out]
        if not dry_run:
            subprocess.run(cmd, check=True)
        return cmd

    res = dict(path=out, attempts=[])
    if mode != "final" or not condition:
        res["cmd"] = run(None)
        return res
    src_i, src_tp = (None, None) if dry_run else r128(os.path.abspath(audio), base[len("[0:a]"):])
    res.update(source_lufs=src_i, source_tp=src_tp)
    ceiling = None
    for k in range(4):
        cmd = run(ceiling)
        res["cmd"] = cmd
        if dry_run:
            break
        i, tp = r128(out)
        res["attempts"].append(dict(limiter_ceiling=ceiling, lufs=i, tp=tp))
        log(f"audio pass {k + 1}: limiter {'off' if ceiling is None else f'{ceiling:.2f} dBTP'} -> AAC {i} LUFS, "
            f"true peak {tp} dBTP")
        res.update(lufs=i, tp=tp, limiter_ceiling=ceiling)
        if tp is None or tp <= TP_CEILING:
            break
        ceiling = PRE_CEILING if ceiling is None else ceiling - (tp - TP_CEILING) - 0.2
    return res


# ============================================================================ graph
def build_graph(pic_h, pad_y, use_titles, grain, out_size, has_alpha=False):
    v = []
    pre = "format=gbrap,premultiply=inplace=1," if has_alpha else "format=rgb24,"    # RGBA renders: over black
    v.append(f"[0:v]{pre}scale={W}:{pic_h}:flags=lanczos+accurate_rnd+full_chroma_int:"
             f"out_color_matrix=bt709:out_range=tv,format=yuv444p,setsar=1[pic0]")
    pic = "pic0"
    if grain and grain > 0:
        gw, gh = W // 2, pic_h // 2 // 2 * 2
        v.append(f"nullsrc=s={gw}x{gh}:r={FPS},format=yuv444p,lutyuv=y=128:u=128:v=128,"
                 f"noise=c0s={int(grain)}:c0f=t:all_seed=20251029,"
                 f"scale={W}:{pic_h}:flags=bicubic,format=yuv444p[grn]")
        v.append(f"[{pic}][grn]blend=c0_mode=overlay:shortest=1[pic1]")   # luma only, weighted to mid-tones
        pic = "pic1"
    v.append(f"[{pic}]pad={W}:{H}:0:{pad_y}:color=black[bg]")
    cur = "bg"
    if use_titles:
        v.append("[1:v]format=rgba,scale=out_color_matrix=bt709:out_range=tv,format=yuva444p[ttl]")
        v.append(f"[{cur}][ttl]overlay=x=0:y=0:format=yuv444:alpha=straight:eof_action=pass[comp]")
        cur = "comp"
    tail = ""
    if out_size != (W, H):
        tail = f"scale={out_size[0]}:{out_size[1]}:flags=bicubic+accurate_rnd+full_chroma_int,"
    # tag the frames themselves (ffmpeg >= 7 takes VUI colour info from frame metadata)
    v.append(f"[{cur}]{tail}format=yuv420p,setsar=1,"
             f"setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709[v]")
    return v


# ============================================================================ QC helpers
def allowed_black_windows():
    s01 = next((s for s in config.SHOTS if s["id"] == "S01"), None)
    wins = sorted(set(list(config.RENDER_SKIP) + ([(s01["start"], s01["end"])] if s01 else [])
                      + [(FADE_START, config.FRAME_END)]))
    merged = []
    for a, b in wins:                           # merge overlapping / touching windows
        if merged and a <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def mac_copy(src, dst):
    """Stream copy re-tagged with the sRGB transfer (13): QuickTime/Safari then show the picture like the PNGs
    instead of applying their BT.709 '1.96 gamma' lift."""
    cmd = [FFMPEG, "-hide_banner", "-y", "-loglevel", "error", "-i", src, "-map", "0", "-c", "copy",
           "-bsf:v", "h264_metadata=transfer_characteristics=13", "-color_trc", "iec61966-2-1",
           "-movflags", "+faststart", dst]
    subprocess.run(cmd, check=True)
    return cmd


# ============================================================================ main entry
def assemble(frames_dir=None, audio=None, out=None, mode="preview", start=None, end=None, titles=True,
             grain=0, step=None, keep_temp=False, dry_run=False, titles_force=False, jobs=None, extra_meta=None,
             allow_silent=False, allow_holds=False, allow_qc_fail=False, missing=None, fade="auto", qc=None,
             crf=None, mac=False, mix_report=None, events_json=None, condition_audio=True, report=None):
    if dry_run:
        keep_temp = True                            # keep the symlink sequences so the printed command runs
    start = config.FRAME_START if start is None else int(start)
    end = config.FRAME_END if end is None else int(end)
    if not (config.FRAME_START <= start <= end <= config.FRAME_END):
        raise AssemblyError(f"--range must satisfy {config.FRAME_START} <= START <= END <= {config.FRAME_END}")
    full = (start, end) == (config.FRAME_START, config.FRAME_END)
    n = end - start + 1
    dur = n / FPS
    frames_dir = frames_dir or config.FRAMES_DIR
    spec = dict(MODES[mode])
    if crf is not None:
        vc = list(spec["vcodec"])
        vc[vc.index("-crf") + 1] = str(int(crf))
        spec["vcodec"] = vc
    qc = (mode == "final") if qc is None else bool(qc)
    if out is None:
        if mode == "final":
            out = config.FINAL_VIDEO if full else os.path.join(config.PREVIEW_DIR, f"final_{start:04d}-{end:04d}.mp4")
        else:
            tag = "full" if full else f"{start:04d}-{end:04d}"
            out = os.path.join(config.PREVIEW_DIR, f"preview_{tag}.mp4")
    out = os.path.abspath(out)
    if report is None:
        report = config.FINAL_QC_JSON if out == os.path.abspath(config.FINAL_VIDEO) \
            else os.path.splitext(out)[0] + ".qc.json"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    t_all = time.time()
    log(f"mode={mode} range={start}-{end} ({n} frames = {dur:.3f} s) frames={frames_dir}")

    # ---- audio decision first (cheap refusals before any work)
    if audio is None and mode == "final" and not allow_silent:
        raise AssemblyError("final master without audio: pass --audio (default auto = out/audio/final_mix.wav) "
                            "or --allow-silent for a picture-only master")
    prov = None
    if audio:
        ai = probe_audio(audio)
        log(f"audio {audio}: {ai['codec']} {ai['sr']} Hz x{ai['ch']}, {ai['dur']:.4f} s (film {FILM_SECONDS:.3f} s)")
        off = ai["dur"] - FILM_SECONDS
        if mode == "final" and abs(off) > 1.0 / FPS + 1e-6:
            raise AssemblyError(f"final: audio is {abs(off):.3f} s {'short' if off < 0 else 'long'} "
                                f"({ai['dur']:.3f} s vs {FILM_SECONDS:.3f} s); refusing to pad/trim more than 1 frame")
        if off < -1e-3:
            log(f"WARNING audio is {-off:.3f} s short -> padded with silence")
        elif off > 1e-3:
            log(f"note: audio {off:.3f} s longer than the film -> trimmed")
        if mode == "final":
            probs, pinfo = audio_provenance(audio, mix_report, events_json)
            prov = dict(problems=probs, **pinfo)
            if probs and full:
                raise AssemblyError("final master refused — the audio is not the real mix of the real events:\n  - "
                                    + "\n  - ".join(probs))
            for p in probs:
                log(f"WARNING (range final, not fatal) audio provenance: {p}")

    # ---- picture plan
    found = scan_frames(frames_dir)
    rng_found = [f for f in found if start <= f <= end and not in_skip(f)]
    if mode == "final" and not allow_holds:
        miss = [f for f in range(start, end + 1) if not in_skip(f) and f not in found]
        info = frame_info(found, rng_found)
        wrong = [f for f in rng_found if info[f][0] != (config.RES_X, config.RES_Y)]
        if miss or wrong:
            msg = []
            if miss:
                msg.append(f"{len(miss)} frame(s) missing: {ranges_str(miss)}")
            if wrong:
                sz = Counter(info[f][0] for f in wrong)
                msg.append(f"{len(wrong)} frame(s) not {config.RES_X}x{config.RES_Y} ({dict(sz)}): {ranges_str(wrong)}")
            raise AssemblyError("final refused (pass --allow-holds for a draft final):\n  - " + "\n  - ".join(msg))
    plan, st = plan_frames(found, start, end, mode, step, allow_holds, missing)
    n_pic = n - len(st["skip"])
    log(f"picture: rendered {len(st['rendered'])}/{n_pic} frames outside RENDER_SKIP (step ~{st['step']}, "
        f"hold cap {st['cap'] if st['cap'] is not None else 'none'})")
    if st["skip"]:
        log(f"designed black (config.RENDER_SKIP): {ranges_str(st['skip'])}")
    if st["held"]:
        log(f"held/borrowed within their shot: {len(st['held'])} frame(s)")
    if st["unfilled"]:
        what = "slates" if (mode == "preview" and (missing or "slate") == "slate") else "black"
        shots = sorted({shot_of(f) for f in st["unfilled"]}, key=lambda s: [x["id"] for x in config.SHOTS].index(s)
                       if s in [x["id"] for x in config.SHOTS] else 99)
        log(f"NOT RENDERED -> {what}: {len(st['unfilled'])} frame(s) in {', '.join(map(str, shots))}: "
            f"{ranges_str(st['unfilled'])}")
    fade_on = False
    fade_note = "not in range"
    if end >= FADE_START and start < FADE_BLACK:
        if fade == "off":
            fade_note = "off (--fade off)"
        elif fade == "on":
            fade_on, fade_note = True, "on (--fade on)"
        else:
            pre = renders_already_fade(found)
            fade_on = not pre
            fade_note = ("skipped: the renders already fade to black" if pre else
                         f"post fade {FADE_START}->{FADE_BLACK} (renders {'do not fade' if pre is False else 'n/a'})")
        log(f"S29 fade: {fade_note}")

    tmp = tempfile.mkdtemp(prefix="silvergrass_assemble_")
    try:
        seq, size, layout, dstats = build_picture(plan, found, start, tmp, fade_on)
        pic_h, pad_y = picture_geometry(size)
        aspect = size[0] / size[1]
        if abs(aspect - config.RES_X / config.RES_Y) > 0.02:
            log(f"WARNING input aspect {aspect:.3f} != {config.RES_X / config.RES_Y:.3f}; fitted to width")
        link_sequence(os.path.join(tmp, "v"), seq)
        log(f"input {size[0]}x{size[1]} {layout} -> picture {W}x{pic_h} at y={pad_y}..{pad_y + pic_h}"
            + (f"; faded {dstats['faded']} frame(s)" if dstats["faded"] else ""))

        # ---- titles (private snapshot, taken under the titles lock)
        ids = title_sequence(start, end, tmp, force=titles_force, jobs=jobs) if titles else []
        use_titles = bool(ids)
        if use_titles:
            log("titles in range: " + ", ".join(f"{t['id']}[{t['start']}-{t['end']}]" for t in config.TITLES
                                              if t["id"] in ids))

        # ---- audio encode (sample-exact slice; final: true-peak conditioning)
        ares = None
        if audio:
            a0 = (start - config.FRAME_START) * SAMPLES_PER_FRAME
            a1 = (end - config.FRAME_START + 1) * SAMPLES_PER_FRAME
            ares = encode_audio(audio, a0, a1, n * SAMPLES_PER_FRAME, mode, tmp, condition=condition_audio,
                                dry_run=dry_run)
            print("\n[assemble] audio command:\n  " + shlex.join(ares["cmd"]), flush=True)

        chains = build_graph(pic_h, pad_y, use_titles, grain, spec["size"], layout == "RGBA")
        graph = ";".join(chains)
        meta = ["-metadata", f"title={config.FILM_TITLE}", "-metadata", f"comment={config.FILM_COMMENT}"]
        for k, v in (extra_meta or {}).items():
            meta += ["-metadata", f"{k}={v}"]
        inputs = ["-framerate", str(FPS), "-start_number", "1", "-i", os.path.join(tmp, "v", "%05d.png")]
        if use_titles:
            inputs += ["-framerate", str(FPS), "-start_number", "1", "-i", os.path.join(tmp, "t", "%05d.png")]
        a_idx = None
        if ares:
            a_idx = 2 if use_titles else 1
            inputs += ["-i", ares["path"]]
        cmd = [FFMPEG, "-hide_banner", "-y", "-loglevel", "warning", "-stats", *inputs,
               "-filter_complex", graph, "-map", "[v]"]
        if a_idx is not None:
            cmd += ["-map", f"{a_idx}:a:0", "-c:a", "copy"]
        cmd += ["-frames:v", str(n), "-r", str(FPS), "-fps_mode", "cfr", *spec["vcodec"], *COLOR_TAGS,
                "-t", f"{dur:.6f}", "-movflags", "+faststart", *meta, out]
        print("\n[assemble] ffmpeg command:\n  " + shlex.join(cmd), flush=True)
        print("[assemble] filter graph, one chain per line:\n    " + "\n    ".join(chains), flush=True)
        if dry_run:
            return dict(out=out, cmd=cmd, graph=graph, dry_run=True, audio_cmd=(ares or {}).get("cmd"))
        t0 = time.time()
        r = subprocess.run(cmd)
        if r.returncode != 0:
            raise AssemblyError(f"ffmpeg failed with exit code {r.returncode}")
        log(f"encoded in {time.time() - t0:.1f}s -> {out}")
        rep = verify(out, n, spec["size"], mode, want_audio=bool(audio), start=start, full=full, qc=qc,
                     allow_qc_fail=allow_qc_fail, plot_path=os.path.splitext(report)[0] + ".flash.png")
        rep.update(out=out, cmd=cmd, graph=graph, seconds=round(time.time() - t_all, 1), mode=mode,
                   range=[start, end], frames_dir=os.path.abspath(frames_dir),
                   picture=dict(rendered=len(st["rendered"]), held=len(st["held"]), unfilled=len(st["unfilled"]),
                                skip_black=len(st["skip"]), step=st["step"], hold_cap=st["cap"],
                                unfilled_ranges=ranges_str(st["unfilled"]), fade=fade_note, **dstats),
                   titles=ids, audio_source=audio, audio_provenance=prov,
                   audio_encode={k: v for k, v in (ares or {}).items() if k not in ("path",)} if ares else None)
        if mac and rep.get("ok"):
            mo = os.path.splitext(out)[0] + "_mac.mp4"
            rep["mac_copy"] = dict(out=mo, cmd=mac_copy(out, mo))
            log(f"Mac copy (sRGB transfer tag) -> {mo}")
        try:
            with open(report, "w") as fh:
                json.dump(rep, fh, ensure_ascii=False, indent=1, default=str)
            rep["report"] = report
            log(f"QC report -> {report}")
        except OSError as e:
            log(f"WARNING could not write the QC report {report}: {e}")
        return rep
    finally:
        if keep_temp:
            log(f"temp kept: {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)


def verify(path, n_expected, size, mode="preview", want_audio=False, start=config.FRAME_START, full=False, qc=False,
           allow_qc_fail=False, plot_path=None):
    j = json.loads(subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries",
         "stream=codec_type,codec_name,profile,level,width,height,r_frame_rate,nb_frames,duration,sample_rate,channels,"
         "pix_fmt,color_space,color_transfer,color_primaries,color_range,bit_rate:format=duration,size,bit_rate",
         "-of", "json", path], capture_output=True, text=True, check=True).stdout)
    vs = [s for s in j["streams"] if s["codec_type"] == "video"]
    as_ = [s for s in j["streams"] if s["codec_type"] == "audio"]
    v = vs[0]
    rep = dict(video=dict(codec=v["codec_name"], profile=v.get("profile"), level=v.get("level"),
                          size=f"{v['width']}x{v['height']}", fps=v["r_frame_rate"], frames=int(v.get("nb_frames", 0)),
                          duration=float(v.get("duration", 0)), pix_fmt=v.get("pix_fmt"),
                          colorspace=v.get("color_space"), transfer=v.get("color_transfer"),
                          bit_rate=int(v.get("bit_rate", 0) or 0)),
               format_duration=float(j["format"]["duration"]), size_mb=round(int(j["format"]["size"]) / 1e6, 2))
    problems = []
    if rep["video"]["frames"] != n_expected:
        problems.append(f"video frames {rep['video']['frames']} != {n_expected}")
    if v["r_frame_rate"] != f"{FPS}/1":
        problems.append(f"fps {v['r_frame_rate']}")
    if (v["width"], v["height"]) != tuple(size):
        problems.append(f"size {v['width']}x{v['height']} != {size[0]}x{size[1]}")
    if abs(rep["video"]["duration"] - n_expected / FPS) >= 0.5 / FPS:
        problems.append(f"video duration {rep['video']['duration']}")
    if as_:
        a = as_[0]
        rep["audio"] = dict(codec=a["codec_name"], sr=int(a["sample_rate"]), ch=int(a["channels"]),
                            duration=float(a.get("duration", 0)), bit_rate=int(a.get("bit_rate", 0) or 0))
    if want_audio:
        if not as_:
            problems.append("no audio stream")
        else:
            ad = rep["audio"]
            if abs(ad["duration"] - n_expected / FPS) >= 1.0 / FPS:
                problems.append(f"audio duration {ad['duration']}")
            if mode == "final" and (ad["codec"], ad["sr"], ad["ch"]) != ("aac", SR, 2):
                problems.append(f"final audio must be AAC {SR} Hz stereo, got {ad['codec']} {ad['sr']} x{ad['ch']}")
    elif as_ and mode == "final":
        problems.append("unexpected audio stream")
    basics_ok = not problems
    qc_problems, qc_warn = [], []
    if qc:
        import flash_qc
        t0 = time.time()
        bd = config.QC_BLACKDETECT
        fq = flash_qc.analyze_video(path, frame0=start, blackdetect=dict(d=bd["black_min_s"], pix_th=bd["black_pix_th"],
                                                                         pic_th=bd["black_pic_th"]))
        Lser = fq.pop("_L")
        if fq["frames"] != n_expected:
            qc_problems.append(f"decoded {fq['frames']} frames, expected {n_expected}")
        if fq["status"] == "FAIL":
            qc_problems += [f"flash QC: {p}" for p in fq["problems"]]
        qc_warn += [f"flash QC: {w}" for w in fq["warnings"]]
        wins = allowed_black_windows()
        bad_black = [(a, b) for a, b in fq.get("black", [])
                     if not any(wa - 2 <= a and b <= wb + 2 for wa, wb in wins)]
        if bad_black:
            qc_problems.append(f"black frames outside S01 / RENDER_SKIP / {FADE_START}-end: "
                               + ", ".join(f"{a}-{b}" for a, b in bad_black))
        loud = None
        if as_:
            li, tp = r128(path)
            loud = dict(integrated_lufs=li, true_peak_dbtp=tp, target_lufs=LUFS_TARGET if full else None,
                        tp_ceiling=TP_CEILING)
            if tp is not None and tp > TP_CEILING:
                qc_problems.append(f"true peak {tp} dBTP > {TP_CEILING} dBTP after AAC")
            if full and li is not None and abs(li - LUFS_TARGET) > LUFS_TOL:
                qc_problems.append(f"integrated loudness {li} LUFS outside {LUFS_TARGET} +- {LUFS_TOL} LU")
        try:
            plot = plot_path or (os.path.splitext(path)[0] + ".flash.png")
            flash_qc.plot(fq, plot, Lser)
        except Exception as e:  # plotting is a review aid only
            plot = f"plot failed: {e!r}"
        rep["qc"] = dict(ok=not qc_problems, problems=qc_problems, warnings=qc_warn, seconds=round(time.time() - t0, 1),
                         flash=dict(status=fq["status"], max_flashes_per_24f=fq["max_flashes_per_24f"],
                                    transitions=fq["transitions_counted"], worst_window=fq["worst_window"],
                                    luminance=fq["luminance"], frames_over_white=fq["frames_over_white"][:20],
                                    red=fq.get("red"), plot=plot),
                         black=dict(intervals=fq.get("black", []), allowed=wins, outside=bad_black),
                         loudness=loud)
        for p in qc_problems:
            log(f"QC {'FAIL' if mode == 'final' else 'note (preview, informational)'}: {p}")
        for w in qc_warn:
            log(f"QC warn: {w}")
        state = "OK" if not qc_problems else ("FAILED" if mode == "final" else "notes (informational)")
        log(f"QC {state} in {rep['qc']['seconds']} s: flash {fq['status']} "
            f"(max {fq['max_flashes_per_24f']:.1f}/24 f), black {len(fq.get('black', []))} interval(s)"
            + (f", {loud['integrated_lufs']} LUFS / {loud['true_peak_dbtp']} dBTP" if loud else ""))
    gate = mode == "final"                   # previews: QC is informational (no AAC conditioning, sparse frames)
    if qc and not gate and qc_problems:
        rep["qc"]["informational"] = True
    ok = basics_ok and (not qc_problems or allow_qc_fail or not gate)
    rep["problems"] = problems
    rep["ok"] = bool(ok)
    log("verify: " + json.dumps({k: rep[k] for k in ("video", "format_duration", "size_mb") if k in rep} |
                                ({"audio": rep["audio"]} if "audio" in rep else {}), ensure_ascii=False))
    for p in problems:
        log(f"verify problem: {p}")
    log("verify " + ("OK" if ok else "FAILED") + f": expected {n_expected} frames = {n_expected / FPS:.3f} s"
        + (" (QC failures allowed by --allow-qc-fail)" if (qc_problems and allow_qc_fail) else ""))
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--preview", action="store_true",
                   help=f"fast {MODES['preview']['size'][0]}x{MODES['preview']['size'][1]} ({VIDEO['codec']} "
                        f"{VIDEO['preview_preset']} crf {VIDEO['preview_crf']}) [default]")
    g.add_argument("--final", action="store_true",
                   help=f"delivery master {W}x{H} (crf {VIDEO['crf']} {VIDEO['preset']}, AAC {VIDEO['audio_bitrate']})")
    ap.add_argument("--frames", default=config.FRAMES_DIR, help="PNG sequence dir (#####.png, absolute frames)")
    ap.add_argument("--audio", default="auto",
                    help="auto (default: out/audio/final_mix.wav; previews fall back to demo_mix.wav) | none | PATH")
    ap.add_argument("--allow-silent", action="store_true", help="final: allow a master without audio")
    ap.add_argument("--allow-holds", action="store_true",
                    help="final: allow missing / off-size frames (draft final; held, else black)")
    ap.add_argument("--allow-qc-fail", action="store_true", help="record QC failures but still exit 0")
    ap.add_argument("--missing", choices=["slate", "black"], default=None,
                    help="preview: what unrendered frames beyond the hold cap show (default slate)")
    ap.add_argument("--fade", choices=["auto", "on", "off"], default="auto", help="S29 picture fade to black")
    ap.add_argument("--qc", action="store_true", help="preview: also run flash QC / blackdetect / loudness")
    ap.add_argument("--out", default=None)
    ap.add_argument("--range", nargs=2, type=int, metavar=("START", "END"))
    ap.add_argument("--step", type=int, default=None, help="sparse-render step (default: inferred)")
    ap.add_argument("--no-titles", action="store_true")
    ap.add_argument("--titles-force", action="store_true", help="re-render title PNGs first")
    ap.add_argument("--grain", type=float, default=0.0, help="film grain strength (0=off, ~4 subtle)")
    ap.add_argument("--crf", type=int, default=None, help="override the x264 CRF (e.g. 18 for a sharing copy)")
    ap.add_argument("--mac-copy", action="store_true", help="also write <out>_mac.mp4 tagged sRGB transfer")
    ap.add_argument("--mix-report", default=None, help="default out/audio/mix_report.json")
    ap.add_argument("--events", default=None, help="default config.EVENTS_JSON")
    ap.add_argument("--jobs", type=int, default=None, help="title render workers")
    ap.add_argument("--keep-temp", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    mode = "final" if a.final else "preview"
    s, e = (a.range if a.range else (None, None))
    try:
        audio = resolve_audio(a.audio, mode, a.allow_silent)
        rep = assemble(frames_dir=a.frames, audio=audio, out=a.out, mode=mode, start=s, end=e,
                       titles=not a.no_titles, grain=a.grain, step=a.step, keep_temp=a.keep_temp, dry_run=a.dry_run,
                       titles_force=a.titles_force, jobs=a.jobs, allow_silent=a.allow_silent,
                       allow_holds=a.allow_holds, allow_qc_fail=a.allow_qc_fail, missing=a.missing, fade=a.fade,
                       qc=True if (a.qc or mode == "final") else False, crf=a.crf, mac=a.mac_copy,
                       mix_report=a.mix_report, events_json=a.events)
    except AssemblyError as ex:
        print(f"[assemble] ERROR: {ex}", file=sys.stderr, flush=True)
        return 1
    return 0 if rep.get("dry_run") or rep.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
