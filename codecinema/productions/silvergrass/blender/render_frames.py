"""
render_frames.py - resumable per-frame renderer.

    Blender -b --factory-startup --python codecinema/productions/silvergrass/blender/render_frames.py -- --blend out/scene.blend \
        (--shots S12-S14 | --shots S12a,S13 | --start N --end M | --frames 5,9,12) [--step K]
        [--quality layout|preview|final] [--out DIR] [--percent P] [--no-mb] [--no-lock] [--force]
        [--no-skip] [--log PATH]

For every frame: skip it when <out>/<frame:05d>.png already exists and is a complete PNG (resume); otherwise
take a machine-wide render slot (lane_tools.render_lock), apply the per-shot overrides
(render_setup.apply_shot_overrides, config.SHOT_RENDER), render to <frame>.<pid>.tmp.png (per process: two
renderers on the same frame never touch each other's file), verify it and os.replace() it into place (a crash
never leaves a half-written frame under the final name; tmp files of dead processes are swept at start).
Frames in config.RENDER_SKIP (black frames generated in post) are skipped unless --no-skip.  --quality
re-applies the render preset when it differs from the one the scene was built with - LOUDLY: build-time content
(grass density ...) stays what the build made, so the summary + log carry 'quality_mismatch'.  One JSON line per
frame goes to <out>/render_log.jsonl, and a final 'RENDER_SUMMARY {...}' line is printed for the supervisor.
When started by the supervisor (env SILVERGRASS_SUPERVISOR_PID) it stops before the next frame once the supervisor
is gone.  Exit codes: 0 all frames present, 1 crashed (traceback), 3 some frames failed, 4 supervisor gone.
"""

from codecinema.productions import film_root, source_root
import argparse
import glob
import inspect
import json
import os
import re
import sys
import time
import traceback

ROOT = str(film_root("silvergrass"))
for _p in (os.path.join(str(source_root("silvergrass")), "common"), os.path.join(str(source_root("silvergrass")), "blender")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bpy  # noqa: E402
import config  # noqa: E402
import procutil  # noqa: E402
import bl_util as U  # noqa: E402
import lane_tools as LT  # noqa: E402

PNG_SIG = b"\x89PNG\r\n\x1a\n"
TMP_RE = re.compile(rf"^\d{{{config.FRAME_DIGITS},}}\.(\d+)\.tmp\.png$")     # config.frame_name(f, ".<pid>.tmp.png")
SUPERVISOR_PID = os.environ.get("SILVERGRASS_SUPERVISOR_PID")
# fault injection for tests/test_pipeline.py only: this frame hangs unless motion blur is disabled (--no-mb)
TEST_POISON_FRAME = os.environ.get("SILVERGRASS_TEST_POISON_FRAME")


def png_complete(path):
    """True if path is a non-trivial PNG with its IEND chunk (cheap check, no decoding)."""
    try:
        size = os.path.getsize(path)
        if size < 64:
            return False
        with open(path, "rb") as f:
            if f.read(8) != PNG_SIG:
                return False
            f.seek(size - 12)
            return b"IEND" in f.read(12)
    except OSError:
        return False


def _units(scene):
    """Ordered selectable units: config shots, then the blend's cuts (markers), then dev-lane shots.
    [(id, f0, f1)]"""
    units = [(s["id"], s["start"], s["end"]) for s in config.SHOTS]
    try:                                            # dev-lane shots stored by build_scene
        units += [(s["id"], s["start"], s["end"]) for s in json.loads(scene.get("build_shots", "[]"))
                  if s["id"] not in {u[0] for u in units}]
    except ValueError:
        pass
    ms = sorted((m for m in scene.timeline_markers if m.camera is not None), key=lambda m: m.frame)
    for i, m in enumerate(ms):
        nxt = ms[i + 1].frame - 1 if i + 1 < len(ms) else scene.frame_end
        units.append((m.name, m.frame, int(m.camera.get("cut_f1", nxt))))
    return units


def select_frames(scene, shots=None, start=None, end=None, frames=None, step=1, no_skip=False):
    """Frames to render from --shots / --start --end / --frames (+ step), minus config.RENDER_SKIP."""
    out = []
    if frames:
        out = [int(x) for x in str(frames).split(",") if x.strip()]
    elif shots:
        units = _units(scene)
        ids = [u[0] for u in units]
        for part in str(shots).split(","):
            part = part.strip()
            if "-" in part:
                a, b = part.split("-", 1)
                ia, ib = ids.index(a), ids.index(b)
                sel = units[ia:ib + 1]
            else:
                sel = [units[ids.index(part)]]
            for _, f0, f1 in sel:
                out.extend(range(f0, f1 + 1))
    else:
        s = scene.frame_start if start is None else int(start)
        e = scene.frame_end if end is None else int(end)
        out = list(range(s, e + 1))
    out = sorted(set(out))
    if step > 1:
        base = out[0] if out else 0
        out = [f for f in out if (f - base) % step == 0]
    if not no_skip:
        out = [f for f in out if not any(a <= f <= b for a, b in config.RENDER_SKIP)]
    return out


def _call(fn, **kw):
    params = inspect.signature(fn).parameters
    if any(p.kind == p.VAR_KEYWORD for p in params.values()):
        return fn(**kw)
    return fn(**{k: v for k, v in kw.items() if k in params})


def _render_setup():
    try:
        import render_setup
        return render_setup
    except ImportError as e:
        if getattr(e, "name", None) != "render_setup":
            raise
        return None


def configure(scene, quality):
    """Apply a render preset (render_setup.configure or the build_scene placeholder)."""
    rs = _render_setup()
    if rs is not None and hasattr(rs, "configure"):
        try:
            return _call(rs.configure, quality=quality, scene=scene)
        except (ValueError, KeyError, TypeError):
            if quality != "layout":
                raise
    import build_scene
    return build_scene._local_configure(quality, scene)


def apply_overrides(scene, frame, quality):
    rs = _render_setup()
    if rs is not None and hasattr(rs, "apply_shot_overrides"):
        return _call(rs.apply_shot_overrides, scene=scene, frame=frame, quality=quality)
    import build_scene
    return build_scene._local_apply_shot_overrides(scene, frame, quality)


def sweep_tmp(out_dir, max_age=None):
    """Remove tmp frames of dead renderers (<frame>.<pid>.tmp.png) and old legacy <frame>.tmp.png files."""
    max_age = config.RENDER_TMP_MAX_AGE if max_age is None else max_age
    n = 0
    now = time.time()
    for p in glob.glob(os.path.join(out_dir, "*.tmp.png")):
        m = TMP_RE.match(os.path.basename(p))
        try:
            if (m and not procutil.pid_alive(m.group(1))) or (not m and now - os.path.getmtime(p) > max_age):
                os.remove(p)
                n += 1
        except OSError:
            pass
    return n


def _cut_at(scene, frame):
    best = None
    for m in sorted(scene.timeline_markers, key=lambda m: m.frame):
        if m.frame <= frame and m.camera is not None:
            best = m.name
    return best


def render(frames, out_dir, quality=None, percent=None, motion_blur=True, lock=True, force=False,
           log_path=None, label=None):
    """Render `frames` of the open scene into out_dir/<frame:05d>.png (resumable). Returns a summary dict."""
    sc = bpy.context.scene
    os.makedirs(out_dir, exist_ok=True)
    sweep_tmp(out_dir)
    built_q = sc.get("build_quality")
    mismatch = None
    if quality and built_q and quality != built_q:
        mismatch = dict(built=built_q, requested=quality)
        print(f"[render_frames] WARNING *** QUALITY MISMATCH: the blend was built at {built_q!r}, rendering at "
              f"{quality!r}: only the render preset changes, build-time content (grass density, ...) stays "
              f"{built_q!r} - rebuild with --quality {quality} for real {quality} frames ***", flush=True)
    if quality and quality != built_q:
        configure(sc, quality)
    quality = quality or built_q or "preview"
    if percent:
        sc.render.resolution_percentage = int(percent)
    if not motion_blur:
        sc.render.use_motion_blur = False
    U.configure_png(sc)
    log_path = log_path or os.path.join(out_dir, config.RENDER_LOG_NAME)
    summ = dict(requested=len(frames), rendered=0, skipped=0, failed=[], seconds=0.0, quality=quality,
                out=out_dir, blend=bpy.data.filepath, quality_mismatch=mismatch)
    t_all = time.time()
    for f in frames:
        if SUPERVISOR_PID and not procutil.pid_alive(SUPERVISOR_PID):
            print(f"[render_frames] supervisor {SUPERVISOR_PID} is gone -> stopping before frame {f}", flush=True)
            summ["stopped"] = "supervisor gone"
            break
        final = os.path.join(out_dir, config.frame_name(f))
        tmp = os.path.join(out_dir, config.frame_name(f, f".{os.getpid()}.tmp.png"))
        if not force and png_complete(final):
            summ["skipped"] += 1
            continue
        if os.path.exists(tmp):
            os.remove(tmp)
        t_wait = time.time()
        try:
            ctx = LT.render_lock(label=label or f"render_frames {os.path.basename(bpy.data.filepath)} f{f}") \
                if lock else _nolock()
            with ctx as slot:
                waited = time.time() - t_wait
                ov = apply_overrides(sc, f, quality)
                if TEST_POISON_FRAME and int(TEST_POISON_FRAME) == f and motion_blur:
                    print(f"[render_frames] TEST poison frame {f}: hanging", flush=True)
                    time.sleep(3600)
                dt = U.render_still(tmp, f, sc)
            if not png_complete(tmp):
                raise RuntimeError(f"incomplete PNG written for frame {f}")
            os.replace(tmp, final)
        except Exception as e:                         # keep going; the supervisor retries
            traceback.print_exc()
            summ["failed"].append(f)
            _log(log_path, dict(frame=f, ok=False, error=f"{type(e).__name__}: {e}"))
            continue
        summ["rendered"] += 1
        rec = dict(frame=f, ok=True, seconds=round(dt, 3), waited=round(waited, 2), slot=slot, cut=_cut_at(sc, f),
                   shot=(config.shot_at(f) or {}).get("id"), quality=quality, bytes=os.path.getsize(final),
                   motion_blur=bool(sc.render.use_motion_blur) and motion_blur,
                   overrides=ov if isinstance(ov, dict) else None, t=time.strftime("%H:%M:%S"))
        if mismatch:
            rec["quality_mismatch"] = mismatch
        _log(log_path, rec)
        print(f"[render_frames] frame {f}: {dt:.2f}s (wait {waited:.1f}s, {rec['cut'] or '-'}) -> {final}", flush=True)
    summ["seconds"] = round(time.time() - t_all, 2)
    print("RENDER_SUMMARY " + json.dumps(summ), flush=True)
    return summ


class _nolock:
    def __enter__(self):
        return None

    def __exit__(self, *a):
        return False


def _log(path, rec):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def main():
    """CLI entry (see the module doc); any exception -> traceback + exit code 1 (Blender itself would exit 0)."""
    try:
        _main()
    except SystemExit:
        raise
    except BaseException:                               # noqa: BLE001
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        sys.exit(1)


def _main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="render_frames.py")
    ap.add_argument("--blend", default=None)
    ap.add_argument("--shots", default=None)
    ap.add_argument("--start", type=int, default=None)
    ap.add_argument("--end", type=int, default=None)
    ap.add_argument("--frames", default=None)
    ap.add_argument("--step", type=int, default=1)
    ap.add_argument("--quality", default=None, choices=[None, "layout", "preview", "final"])
    ap.add_argument("--out", default=None)
    ap.add_argument("--percent", type=int, default=None)
    ap.add_argument("--no-mb", action="store_true", help="motion blur off (poison-frame fallback)")
    ap.add_argument("--no-lock", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-skip", action="store_true", help="ignore config.RENDER_SKIP")
    ap.add_argument("--log", default=None)
    a = ap.parse_args(argv)
    if a.blend and os.path.abspath(a.blend) != os.path.abspath(bpy.data.filepath or ""):
        bpy.ops.wm.open_mainfile(filepath=os.path.abspath(a.blend))
    sc = bpy.context.scene
    frames = select_frames(sc, a.shots, a.start, a.end, a.frames, a.step, a.no_skip)
    out = a.out or config.FRAMES_DIR
    print(f"[render_frames] {len(frames)} frames ({frames[:1]}..{frames[-1:]}) -> {out}", flush=True)
    s = render(frames, out, a.quality, a.percent, motion_blur=not a.no_mb, lock=not a.no_lock, force=a.force,
               log_path=a.log)
    sys.exit(4 if s.get("stopped") else (3 if s["failed"] else 0))


if __name__ == "__main__":
    main()
