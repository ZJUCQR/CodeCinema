"""Insert the two rendered Blender opening shots on the existing story clock.

The untouched Skia picture remains available for later refreshes. Blender
dialogue is mixed by the episode pipeline, so a preview's music is never
layered over the finished episode soundtrack.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import skia

from codecinema import media, settings
from art import TOP, BOTTOM, col, rect
from scenes import captions
from story import timeline

OPENING = ("ep01_lost", "ep01_face")


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def check_picture(path, frames, fps, size=None):
    info = media.probe(str(path))
    if (info.get("frames") != frames or abs(info["fps"] - fps) > .001
            or abs(info["duration"] - frames / fps) > .08):
        raise ValueError(f"Picture does not match the story clock: {path}")
    if size and (info["width"], info["height"]) != size:
        raise ValueError(f"Picture does not match the episode dimensions: {path}")
    return info


def captioned(source, shot, target, width, height, fps):
    frames = round(shot.duration * fps)
    if target.is_file():
        check_picture(target, frames, fps, (width, height))
        return
    partial = target.with_name(target.stem + ".partial.mp4")
    decoder = subprocess.Popen(
        [settings.tool("ffmpeg"), "-v", "error", "-i", str(source), "-map", "0:v:0",
         "-vf", f"scale={width}:{height}:flags=lanczos", "-frames:v", str(frames),
         "-f", "rawvideo", "-pix_fmt", "rgba", "-"], stdout=subprocess.PIPE,
    )
    encoder = media.encoder(str(partial), width, height, fps,
                            crf=int(settings.get("video", "crf", 18)),
                            preset=str(settings.get("video", "preset", "fast")))
    surface = skia.Surface(width, height)
    canvas = surface.getCanvas()
    try:
        for index in range(frames):
            data = decoder.stdout.read(width * height * 4)
            if len(data) != width * height * 4:
                raise ValueError(f"Incomplete Blender picture: {source}, frame {index}")
            image = skia.Image.fromarray(np.frombuffer(data, np.uint8).reshape(height, width, 4),
                                        colorType=skia.kRGBA_8888_ColorType)
            canvas.clear(col("#050a10"))
            canvas.drawImage(image, 0, 0)
            canvas.save()
            canvas.scale(width / 1920, height / 1080)
            rect(canvas, 0, 0, 1920, TOP, "#050a10")
            rect(canvas, 0, BOTTOM, 1920, 1080 - BOTTOM, "#050a10")
            captions(canvas, shot, index / fps)
            canvas.restore()
            encoder.stdin.write(surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType).tobytes())
        decoder.stdout.close()
        if decoder.wait() != 0:
            raise RuntimeError(f"Blender decode failed: {source}")
        encoder.stdin.close()
        if encoder.wait() != 0:
            raise RuntimeError(f"Caption encoding failed: {shot.id}")
        check_picture(partial, frames, fps, (width, height))
        partial.replace(target)
    finally:
        for process, stream in ((decoder, decoder.stdout), (encoder, encoder.stdin)):
            if stream and not stream.closed:
                stream.close()
            if process.poll() is None:
                process.terminate()
                process.wait()
        partial.unlink(missing_ok=True)


def prepare(episodes, out, width, height, fps, signature):
    """Return picture paths and provenance without modifying the base renders."""
    result = {}
    for episode in episodes:
        base = out / episode["id"] / "picture.mp4"
        check_picture(base, round(episode["duration_s"] * fps), fps, (width, height))
        selected = [s for s in timeline(episode) if s.id in OPENING]
        if not selected:
            result[episode["id"]] = {"path": str(base), "renderer": "Skia"}
            continue
        sources = {s.id: out / "blender" / f"{s.id}.mp4" for s in selected}
        for shot in selected:
            source = sources[shot.id]
            if not source.is_file():
                raise ValueError(f"Missing Blender shot. Run: codecinema run xishen blender --shot {shot.id}")
            check_picture(source, round(shot.duration * fps), fps)
        provenance = {"base_sha256": sha256(base),
                      "blender_shots": {key: sha256(path) for key, path in sources.items()}}
        key = hashlib.sha256((signature + json.dumps(provenance, sort_keys=True)).encode()).hexdigest()[:20]
        directory = out / "editions" / key
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{episode['id']}_picture.mp4"
        if not target.is_file():
            for shot in selected:
                captioned(sources[shot.id], shot, directory / f"{shot.id}.mp4", width, height, fps)
            inputs = ["-i", str(base)]
            for shot in selected:
                inputs.extend(["-i", str(directory / f"{shot.id}.mp4")])
            filters, parts, cursor = [], [], 0
            for index, shot in enumerate(selected, 1):
                begin, end = round(shot.start * fps), round(shot.end * fps)
                if begin > cursor:
                    name = f"base{index}"
                    filters.append(f"[0:v]trim=start_frame={cursor}:end_frame={begin},setpts=PTS-STARTPTS[{name}]")
                    parts.append(f"[{name}]")
                filters.append(f"[{index}:v]setsar=1,setpts=PTS-STARTPTS[shot{index}]")
                parts.append(f"[shot{index}]")
                cursor = end
            total = round(episode["duration_s"] * fps)
            if cursor < total:
                filters.append(f"[0:v]trim=start_frame={cursor}:end_frame={total},setpts=PTS-STARTPTS[tail]")
                parts.append("[tail]")
            filters.append("".join(parts) + f"concat=n={len(parts)}:v=1:a=0[picture]")
            partial = target.with_name(target.stem + ".partial.mp4")
            try:
                subprocess.run(
                    [settings.tool("ffmpeg"), "-v", "error", "-y", *inputs,
                     "-filter_complex", ";".join(filters), "-map", "[picture]",
                     "-an", "-c:v", "libx264", "-preset", str(settings.get("video", "preset", "fast")),
                     "-crf", str(settings.get("video", "crf", 18)), "-pix_fmt", "yuv420p", str(partial)], check=True,
                )
                check_picture(partial, total, fps, (width, height))
                partial.replace(target)
            finally:
                partial.unlink(missing_ok=True)
        check_picture(target, round(episode["duration_s"] * fps), fps, (width, height))
        result[episode["id"]] = {"path": str(target), "renderer": "Skia + Blender opening", **provenance}
        print(f"{episode['id']}: inserted {sum(s.duration for s in selected):g}s of Blender on the original shot boundaries", flush=True)
    return result
