"""
run.py - NightRevels command line.

    codecinema run nightrevels build        write out/events.json and out/notes.json (sound cues + score)
    codecinema run nightrevels still F[,F]  render single frames to out/stills/
    codecinema run nightrevels render       render the film picture to out/video/picture.mp4 (parallel, resumable chunks)
    codecinema run nightrevels audio        synthesize score + SFX + ambience -> out/audio/final_mix.wav
    codecinema run nightrevels assemble     mux picture + audio -> assets/film/NightRevels.mp4
    codecinema run nightrevels all
"""

from codecinema.productions import film_root, source_root
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

ROOT = str(film_root("nightrevels"))
sys.path[:0] = [os.path.join(str(source_root("nightrevels")), "common"), os.path.join(str(source_root("nightrevels")), "story")]
import config as C  # noqa: E402

CHUNK = C.CHUNK
VIDEO_DIR = os.path.join(C.OUT, "video")


def cmd_build(a=None):
    import film
    import music
    stage, ev = film.build()
    os.makedirs(C.OUT, exist_ok=True)
    doc = dict(fps=C.FPS, frame_start=C.FRAME_START, frame_end=C.FRAME_END, cue=C.CUE,
               sections=C.SECTIONS, events=ev.sorted())
    with open(C.EVENTS_JSON, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
    with open(C.NOTES_JSON, "w", encoding="utf-8") as fh:
        json.dump(dict(fps=C.FPS, notes=music.NOTES), fh, ensure_ascii=False, indent=1)
    print(f"events: {len(ev.items)}  notes: {len(music.NOTES)}")
    return 0


def cmd_still(a):
    import skia
    import film
    stage, _ = film.build()
    os.makedirs(os.path.join(C.OUT, "stills"), exist_ok=True)
    surf = skia.Surface(C.W, C.H)
    for f in [int(x) for x in a.frames.split(",")]:
        stage.render(f, surf)
        p = os.path.join(C.OUT, "stills", f"{f:05d}.png")
        surf.makeImageSnapshot().save(p)
        print(p)
    return 0


_STAGE = None


def _init():
    global _STAGE
    import film
    _STAGE, _ = film.build()


def _render_chunk(args):
    """Render frames [f0, f1] and pipe them straight into an x264 segment."""
    f0, f1, path = args
    import skia
    surf = skia.Surface(C.W, C.H)
    tmp = path + ".part.mp4"
    cmd = [C.FFMPEG, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{C.W}x{C.H}", "-r", str(C.FPS),
           "-i", "-", "-c:v", "libx264", "-preset", C.RENDER_PRESET, "-crf", str(C.RENDER_CRF), "-tune", "animation",
           "-pix_fmt", "yuv420p",
           tmp]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for f in range(f0, f1 + 1):
        _STAGE.render(f, surf)
        arr = surf.makeImageSnapshot().toarray()
        p.stdin.write(arr.tobytes())
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError(f"ffmpeg failed for chunk {f0}-{f1}")
    os.replace(tmp, path)
    return f0, f1, time.time() - t0


def cmd_render(a):
    os.makedirs(VIDEO_DIR, exist_ok=True)
    # Content is now editable independently of this production pack. Never reuse
    # chunks from a previous story, set of settings or implementation.
    digest = hashlib.sha256(json.dumps(C._settings.SETTINGS, sort_keys=True).encode())
    for source in [Path(ROOT) / "story.json", *sorted(source_root("nightrevels").rglob("*.py"))]:
        digest.update(source.read_bytes())
    signature = digest.hexdigest()
    edition = Path(VIDEO_DIR) / "edition.json"
    try:
        previous = json.loads(edition.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = {}
    if previous.get("signature") != signature:
        for chunk in Path(VIDEO_DIR).glob("chunk_*.mp4"):
            chunk.unlink()
    from codecinema.registry import atomic_write
    atomic_write(edition, json.dumps({"signature": signature}))
    jobs = []
    for f0 in range(C.FRAME_START, C.FRAME_END + 1, CHUNK):
        f1 = min(C.FRAME_END, f0 + CHUNK - 1)
        path = os.path.join(VIDEO_DIR, f"chunk_{f0:05d}.mp4")
        if a.force or not os.path.exists(path):
            jobs.append((f0, f1, path))
    print(f"{len(jobs)} chunk(s) to render")
    workers = a.jobs or C.RENDER_JOBS
    t0 = time.time()
    if jobs:
        with ProcessPoolExecutor(max_workers=workers, initializer=_init) as ex:
            for f0, f1, dt in ex.map(_render_chunk, jobs):
                print(f"  frames {f0}-{f1}: {dt:.1f}s", flush=True)
    lst = os.path.join(VIDEO_DIR, "chunks.txt")
    with open(lst, "w") as fh:
        for f0 in range(C.FRAME_START, C.FRAME_END + 1, CHUNK):
            fh.write(f"file 'chunk_{f0:05d}.mp4'\n")
    out = os.path.join(VIDEO_DIR, "picture.mp4")
    subprocess.check_call([C.FFMPEG, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out])
    print(f"picture: {out}  ({time.time() - t0:.0f}s)")
    return 0


def cmd_audio(a):
    return subprocess.call([sys.executable, os.path.join(str(source_root("nightrevels")), "audio", "mix.py")])


def cmd_assemble(a):
    pic = os.path.join(VIDEO_DIR, "picture.mp4")
    wav = os.path.join(C.AUDIO_DIR, "final_mix.wav")
    os.makedirs(os.path.dirname(C.FINAL_VIDEO), exist_ok=True)
    cmd = [C.FFMPEG, "-v", "error", "-y", "-i", pic, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
           "-c:a", "aac", "-b:a", C.AUDIO_BITRATE, "-shortest", "-movflags", "+faststart",
           "-metadata", "title=韩熙载夜宴图 · 猫", C.FINAL_VIDEO]
    r = subprocess.call(cmd)
    print(C.FINAL_VIDEO if r == 0 else "assemble failed")
    return r


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    s = sub.add_parser("still")
    s.add_argument("frames")
    r = sub.add_parser("render")
    r.add_argument("--force", action="store_true")
    r.add_argument("--jobs", type=int, default=0)
    sub.add_parser("audio")
    sub.add_parser("assemble")
    al = sub.add_parser("all")
    al.add_argument("--force", action="store_true")
    al.add_argument("--jobs", type=int, default=0)
    a = ap.parse_args()
    if a.cmd == "all":
        for step in (cmd_build, cmd_render, cmd_audio, cmd_assemble):
            if step(a):
                return 1
        return 0
    return {"build": cmd_build, "still": cmd_still, "render": cmd_render, "audio": cmd_audio,
            "assemble": cmd_assemble}[a.cmd](a) or 0


if __name__ == "__main__":
    sys.exit(main())
