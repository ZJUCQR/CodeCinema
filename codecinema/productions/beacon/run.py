"""Reproduce The Last Beacon with CodeCinema and Blender 5.2+."""

from codecinema.productions import film_root, source_root

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = film_root("beacon")
os.environ["CODECINEMA_FILM_DIR"] = str(ROOT)
sys.path.insert(0, str(ROOT.parents[1]))
from story import FPS, FRAMES, HEIGHT, SECONDS, WIDTH

from codecinema import blender, procutil, settings

OUT = ROOT / "out"
MASTER = ROOT / "assets/film/TheLastBeacon.mp4"


def execute(args, **kwargs):
    return subprocess.run(list(map(str, args)), check=True, **kwargs)


def check():
    for name in ("blender", "ffmpeg", "ffprobe"):
        path = settings.tool(name)
        if not shutil.which(path):
            raise RuntimeError(f"{name} is missing; install it or set its tool override.")
    result = execute([settings.tool("blender"), "--version"], capture_output=True, text=True)
    import re

    version = re.search(r"Blender (\d+)\.(\d+)", result.stdout)
    if not version or tuple(map(int, version.groups())) < (5, 2):
        raise RuntimeError("This film requires Blender 5.2 or later.")
    print("Blender, FFmpeg and FFprobe are available.")


def render(force=False, jobs=1):
    folder = OUT / "frames"
    folder.mkdir(parents=True, exist_ok=True)
    source = (ROOT / "story.json").read_bytes() + b"".join((source_root("beacon") / p).read_bytes() for p in ("scene.py", "story.py"))
    options = {
        section: {key: settings.get(section, key, default) for key, default in values.items()}
        for section, values in {
            "render": {"samples_final": 48, "exposure": -0.4},
            "art": {"porcelain": [0.72, 0.79, 0.75], "brass": [0.52, 0.28, 0.085], "scarf": [0.38, 0.035, 0.027]},
        }.items()
    }
    digest = hashlib.sha256(source + json.dumps(options, sort_keys=True).encode()).hexdigest()
    manifest = folder / "edition.json"
    try:
        previous = json.loads(manifest.read_text()) if manifest.exists() else {}
    except json.JSONDecodeError:
        previous = {}
    if previous.get("source") != digest or force:
        for frame in folder.glob("*.png"):
            frame.unlink()
    temporary = manifest.with_suffix(".part.json")
    temporary.write_text(json.dumps({"source": digest, "frames": FRAMES, "width": WIDTH, "height": HEIGHT}))
    temporary.replace(manifest)
    chunk = (FRAMES + jobs - 1) // jobs

    def render_range(start):
        blender.run(str(source_root("beacon") / 'scene.py'), "--start", start, "--end", min(start + chunk - 1, FRAMES))

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        list(pool.map(render_range, range(1, FRAMES + 1, chunk)))


def audio():
    from sound import generate

    OUT.mkdir(exist_ok=True)
    report = generate(OUT / "audio")
    (OUT / "audio/report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report)


def assemble():
    from PIL import Image

    for frame in range(1, FRAMES + 1):
        path = OUT / "frames" / f"{frame:05d}.png"
        with Image.open(path) as image:
            if image.size != (WIDTH, HEIGHT):
                raise ValueError(f"Wrong frame size: {path}")
            image.verify()
    from scipy.io import wavfile

    sample_rate, samples = wavfile.read(OUT / "audio/mix.wav", mmap=True)
    if sample_rate != 48000 or samples.shape != (SECONDS * 48000, 2):
        raise ValueError("The mix must be exactly 48 seconds of 48 kHz stereo audio; run the audio step again.")
    MASTER.parent.mkdir(parents=True, exist_ok=True)
    temporary = MASTER.with_suffix(".part.mp4")
    execute(
        [
            settings.tool("ffmpeg"),
            "-v",
            "error",
            "-y",
            "-framerate",
            FPS,
            "-start_number",
            1,
            "-i",
            OUT / "frames/%05d.png",
            "-i",
            OUT / "audio/mix.wav",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-vf",
            "fade=t=in:st=0:d=1,fade=t=out:st=46:d=2,scale=out_color_matrix=bt709:out_range=tv",
            "-c:v",
            "libx264",
            "-crf",
            "17",
            "-preset",
            "slow",
            "-pix_fmt",
            "yuv420p",
            "-color_primaries",
            "bt709",
            "-colorspace",
            "bt709",
            "-color_trc",
            "iec61966-2-1",
            "-color_range",
            "tv",
            "-c:a",
            "aac",
            "-b:a",
            "320k",
            "-ar",
            "48000",
            "-t",
            SECONDS,
            "-movflags",
            "+faststart",
            "-metadata",
            "title=The Last Beacon",
            "-metadata",
            "artist=ZJUCQR",
            temporary,
        ]
    )
    execute([settings.tool("ffmpeg"), "-v", "error", "-xerror", "-i", temporary, "-f", "null", "-"])
    probe = execute(
        [
            settings.tool("ffprobe"),
            "-v",
            "error",
            "-count_frames",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            temporary,
        ],
        capture_output=True,
        text=True,
    )
    info = json.loads(probe.stdout)
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    sound = next(s for s in info["streams"] if s["codec_type"] == "audio")
    if int(video["nb_read_frames"]) != FRAMES:
        raise ValueError("Incomplete picture")
    if sound["channels"] != 2 or int(sound["sample_rate"]) != 48000:
        raise ValueError("Wrong audio format")
    if any(abs(float(stream["duration"]) - SECONDS) >= 0.05 for stream in (video, sound)):
        raise ValueError("Picture and audio must both span the complete film")
    measurement = execute(
        [
            settings.tool("ffmpeg"),
            "-hide_banner",
            "-i",
            temporary,
            "-af",
            "loudnorm=I=-16:TP=-1:LRA=11:print_format=json",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    data = measurement.stderr
    loudness = json.loads(data[data.rfind("{") : data.rfind("}") + 1])
    if float(loudness["input_tp"]) > -1:
        raise ValueError("Encoded true peak exceeds -1 dBTP")
    if not -19 <= float(loudness["input_i"]) <= -13:
        raise ValueError("Master loudness outside intended range")
    temporary.replace(MASTER)
    (OUT / "qc.json").write_text(json.dumps({"probe": info, "loudness": loudness, "decoded": True}, indent=2) + "\n")
    print(f"Verified master: {MASTER}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="step", required=True)
    sub.add_parser("check")
    still = sub.add_parser("still")
    still.add_argument("frames", nargs="?", default="96,288,481,672,864,1056")
    still.add_argument("--full", action="store_true")
    for name in ("render", "all"):
        p = sub.add_parser(name)
        p.add_argument("--force", action="store_true", help="Re-render all frames")
        p.add_argument(
            "--jobs", type=int, choices=(1, 2, 3, 4), default=1, help="Concurrent Blender processes (default: 1)"
        )
    sub.add_parser("audio")
    sub.add_parser("assemble")
    args = parser.parse_args()
    if args.step == "check":
        check()
        return
    OUT.mkdir(exist_ok=True)
    with (OUT / ".production.lock").open("a+b") as lock:
        if not procutil.lock_file(lock):
            parser.error("Another beacon production step is running. Let it finish first.")
        try:
            dispatch(args)
        finally:
            procutil.unlock_file(lock)


def dispatch(args):
    if args.step == "check":
        check()
    elif args.step == "still":
        frames = [int(frame) for frame in args.frames.split(",")]
        if not frames or any(frame < 1 or frame > FRAMES for frame in frames):
            raise ValueError(f"Choose frame numbers in 1..{FRAMES}.")
        blender.run(str(source_root("beacon") / 'scene.py'), "--frames", args.frames, *([] if args.full else ["--preview"]))
    elif args.step == "render":
        check()
        render(args.force, args.jobs)
    elif args.step == "audio":
        audio()
    elif args.step == "assemble":
        assemble()
    else:
        check()
        render(args.force, args.jobs)
        audio()
        assemble()


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"beacon: {exc}", file=sys.stderr)
        sys.exit(1)
