"""
lane_preview.py - one command from a lane module to a reviewable preview.

    .venv/bin/python src/tools/lane_preview.py act1b [--quality layout|preview] [--step 2] [--every 12]
        [--stubs environment,...] [--skip-build] [--skip-render] [--no-video] [--auto-boost]

1. build   Blender build_scene.py --lanes <lane> --quality <q>      -> out/lanes/<lane>/scene.blend (+ events.json,
                                                                       build_report.json, qa/)
2. render  Blender render_frames.py --start s --end e --step <step>  -> out/previews/<lane>/<q>/#####.png (resumes)
3. sheet   contact sheet of every <every>th frame                    -> out/previews/<lane>/<lane>_<q>_sheet.png
4. video   frames labelled 'frame / cut' (burned in with PIL - this ffmpeg build has no drawtext), each held
           <step> frames at 24 fps, + a click track synthesised from the lane's events (pitch per event family,
           panned with the event pan)                               -> out/previews/<lane>/<lane>_<q>.mp4
Prints the paths and the build QA summary.  Timings are printed per stage.  A failed build (non-zero exit,
build_report status != 'ok', or no fresh scene.blend) aborts before anything is rendered or deleted, so a stale
preview can never pass for a new one.
"""
import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import time
import wave

import numpy as np
from PIL import Image, ImageDraw

ROOT = (__import__("os").environ.get("SILVERGRASS_ROOT") or str(next(p for p in __import__("pathlib").Path(__file__).resolve().parents if (p / "src" / "common" / "config.py").is_file())))   # repo root (portable)
sys.path.insert(0, os.path.join(ROOT, "src", "common"))
sys.path.insert(0, os.path.join(ROOT, "src", "tools"))
import config  # noqa: E402
import contact_sheet as CS  # noqa: E402

FFMPEG = config.FFMPEG
SR = config.AUDIO_SR
CLICK = {   # event family -> (frequency Hz, length s, gain)
    "clash": (2600.0, 0.05, 0.9), "clash_heavy": (1800.0, 0.09, 1.0), "perfect_deflect": (3200.0, 0.12, 1.0),
    "whoosh": (0.0, 0.10, 0.35), "step": (140.0, 0.03, 0.5), "land": (110.0, 0.06, 0.7), "skid": (0.0, 0.2, 0.3),
    "music_cue": (440.0, 0.08, 0.6), "thunder": (60.0, 0.4, 0.8), "lightning_strike": (90.0, 0.25, 0.9),
}
DEFAULT_CLICK = (900.0, 0.02, 0.45)


def run(cmd, log_path=None):
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True)
    if log_path:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(r.stdout + "\n" + r.stderr)
    if r.returncode != 0:
        tail = "\n".join((r.stdout + r.stderr).strip().splitlines()[-25:])
        raise SystemExit(f"lane_preview: command failed ({r.returncode}): {' '.join(cmd[:6])} ...\n{tail}")
    return r.stdout, time.time() - t0


def check_build(lane_dir, blend, t_build=None):
    """Abort unless the lane build succeeded: report status 'ok' (no 'error'), and scene.blend exists and is not
    older than this build (t_build = the time the build command started)."""
    rp = os.path.join(lane_dir, config.BUILD_REPORT_NAME)
    if not os.path.exists(rp):
        raise SystemExit(f"lane_preview: no build report {rp} - build first")
    rep = json.load(open(rp, encoding="utf-8"))
    if rep.get("error") or rep.get("status", "ok") != "ok":
        raise SystemExit(f"lane_preview: the build FAILED (status {rep.get('status')!r}) - nothing rendered:\n"
                         f"{str(rep.get('error', ''))[-1500:]}")
    if not os.path.exists(blend):
        raise SystemExit(f"lane_preview: {blend} missing although the report says ok")
    if t_build is not None and os.path.getmtime(blend) < t_build - 1.0:
        raise SystemExit(f"lane_preview: {blend} is older than this build - stale scene, nothing rendered")
    return rep


def click_track(events, f0, n_frames, path):
    """Stereo WAV with one synthetic click per event (video time 0 = frame f0)."""
    n = int(math.ceil(n_frames / config.FPS * SR)) + SR // 2
    out = np.zeros((n, 2), dtype=np.float32)
    rng = np.random.default_rng(7)
    for e in events:
        t = (float(e["frame"]) - f0) / config.FPS
        if t < 0 or t * SR >= n:
            continue
        freq, length, gain = CLICK.get(e["type"], DEFAULT_CLICK)
        if e.get("tags"):
            gain = min(1.0, gain * 1.3)
        m = int(length * SR)
        tt = np.arange(m) / SR
        env = np.exp(-tt / (length * 0.35))
        sig = np.sin(2 * np.pi * freq * tt) if freq > 0 else rng.standard_normal(m) * 0.6
        sig = (sig * env * gain * 0.5).astype(np.float32)
        pan = float(e.get("pan", 0.0) or 0.0)
        lr = np.array([math.cos((pan + 1) * math.pi / 4), math.sin((pan + 1) * math.pi / 4)], dtype=np.float32)
        i0 = int(t * SR)
        i1 = min(n, i0 + m)
        out[i0:i1] += sig[: i1 - i0, None] * lr[None, :]
    peak = float(np.abs(out).max()) or 1.0
    out = (out / max(1.0, peak) * 32000).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(out.tobytes())
    return path


def labelled_frames(frame_map, cut_of, tmp, label):
    """Copy frames into tmp as 000000.png ... with 'frame / cut' burned in. Returns the count."""
    os.makedirs(tmp, exist_ok=True)
    fnt = None
    for i, (fr, p) in enumerate(sorted(frame_map.items())):
        im = Image.open(p).convert("RGB")
        if im.width % 2 or im.height % 2:                       # x264 wants even sizes
            im = im.crop((0, 0, im.width - im.width % 2, im.height - im.height % 2))
        if fnt is None:
            fnt = CS.font(max(12, im.height // 18))
        d = ImageDraw.Draw(im)
        txt = f"{fr:05d}  {cut_of(fr)}  {label}"
        d.rectangle([0, 0, len(txt) * fnt.size * 0.62 + 10, fnt.size + 8], fill=(0, 0, 0))
        d.text((5, 3), txt, fill=(255, 230, 150), font=fnt)
        im.save(os.path.join(tmp, f"{i:06d}.png"))
    return len(frame_map)


def main():
    ap = argparse.ArgumentParser(prog="lane_preview.py")
    ap.add_argument("lane")
    ap.add_argument("--quality", default="layout", choices=["layout", "preview", "final"])
    ap.add_argument("--step", type=int, default=2)
    ap.add_argument("--every", type=int, default=12)
    ap.add_argument("--stubs", default="")
    ap.add_argument("--fallback", action="store_true", help="placeholders when env/characters build fails")
    ap.add_argument("--skip-build", action="store_true")
    ap.add_argument("--skip-render", action="store_true")
    ap.add_argument("--no-video", action="store_true")
    ap.add_argument("--auto-boost", action="store_true")
    a = ap.parse_args()
    lane, q = a.lane, a.quality
    lane_dir = config.lane_dir(lane)
    prev_dir = os.path.join(config.PREVIEW_DIR, lane)
    frame_dir = os.path.join(prev_dir, q)
    os.makedirs(frame_dir, exist_ok=True)
    blend = os.path.join(lane_dir, "scene.blend")
    times = {}
    if not a.skip_build:
        t_build = time.time()
        cmd = config.blender_cmd("src/blender/build_scene.py", "--lanes", lane, "--quality", q)
        if a.stubs:
            cmd += ["--stubs", a.stubs]
        if a.fallback:
            cmd.append("--fallback")
        _, times["build"] = run(cmd, os.path.join(prev_dir, "build.log"))
        check_build(lane_dir, blend, t_build)
        if os.path.isdir(frame_dir):                      # a new build invalidates old preview frames
            for f in os.listdir(frame_dir):
                if f.endswith(".png"):
                    os.remove(os.path.join(frame_dir, f))
    else:
        check_build(lane_dir, blend, None)
    rep = json.load(open(os.path.join(lane_dir, config.BUILD_REPORT_NAME), encoding="utf-8"))
    s, e = rep["lane_spans"][lane]
    if not a.skip_render:
        cmd = config.blender_cmd("src/blender/render_frames.py", "--blend", blend, "--start", s, "--end", e,
                                 "--step", a.step, "--quality", q, "--out", frame_dir)
        _, times["render"] = run(cmd, os.path.join(prev_dir, "render.log"))
    events_path = os.path.join(lane_dir, "events.json")
    t0 = time.time()
    sheet = os.path.join(prev_dir, f"{lane}_{q}_sheet.png")
    CS.make_sheet(frame_dir, sheet, every=a.every, cols=6, width=300, auto=a.auto_boost or lane == "act3",
                  events=events_path, title=f"{lane}  {q}  frames {s}-{e}  every {a.every}")
    times["sheet"] = time.time() - t0
    video = None
    if not a.no_video:
        t0 = time.time()
        fmap = CS.list_frames(frame_dir)
        fmap = {f: p for f, p in fmap.items() if s <= f <= e}
        tmp = os.path.join(prev_dir, "_video_tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        cut_of = CS.cut_lookup(events_path)
        n = labelled_frames(fmap, cut_of, tmp, f"{lane} {q}")
        f0 = min(fmap)
        doc = json.load(open(events_path, encoding="utf-8")) if os.path.exists(events_path) else {"events": []}
        wav = click_track(doc["events"], f0, n * a.step, os.path.join(prev_dir, f"{lane}_clicks.wav"))
        video = os.path.join(prev_dir, f"{lane}_{q}.mp4")
        vid = config.VIDEO
        cmd = [FFMPEG, "-y", "-loglevel", "error", "-framerate", f"{config.FPS}/{a.step}", "-i",
               os.path.join(tmp, "%06d.png"), "-i", wav, "-r", str(config.FPS), "-c:v", vid["codec"],
               "-crf", str(vid["review_crf"]), "-pix_fmt", vid["pix_fmt"], "-c:a", "aac",
               "-b:a", vid["review_audio_bitrate"], "-shortest", video]
        run(cmd)
        shutil.rmtree(tmp, ignore_errors=True)
        times["video"] = time.time() - t0
    qa = rep.get("qa", {})
    print(json.dumps(dict(lane=lane, quality=q, span=[s, e], blend=blend, frames=frame_dir, sheet=sheet,
                          video=video, qa_fail_count=qa.get("fail_count"), stubs=[k for k, v in rep["stubs"].items() if v],
                          warnings=len(rep.get("warnings", [])), seconds={k: round(v, 1) for k, v in times.items()}),
                     indent=1))


if __name__ == "__main__":
    main()
