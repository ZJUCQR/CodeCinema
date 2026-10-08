"""
codecinema.runtime.media - small ffmpeg helpers shared by the films.

    probe(path)                         -> dict(duration, width, height, fps, frames, audio_rate)
    encoder(path, w, h, fps, crf=...)   -> a Popen that takes raw RGBA frames on stdin and writes an H.264 file
    concat(paths, out)                  -> joins same-codec segments without re-encoding
    mux(video, audio, out, ...)         -> picture + sound -> final .mp4 (AAC, faststart, optional metadata)
"""
import json
import os
import subprocess
import tempfile

from codecinema.workspace import settings


def ffmpeg():
    return settings.tool("ffmpeg")


def ffprobe():
    return settings.tool("ffprobe")


def probe(path):
    out = subprocess.run([ffprobe(), "-v", "error", "-show_entries",
                          "stream=codec_type,width,height,r_frame_rate,nb_frames,sample_rate:format=duration",
                          "-of", "json", path], capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    info = dict(duration=float(d.get("format", {}).get("duration", 0.0)))
    for s in d.get("streams", []):
        if s.get("codec_type") == "video":
            num, den = (s.get("r_frame_rate") or "0/1").split("/")
            info.update(width=s.get("width"), height=s.get("height"), fps=float(num) / float(den or 1),
                        frames=int(s.get("nb_frames") or 0))
        elif s.get("codec_type") == "audio":
            info["audio_rate"] = int(s.get("sample_rate") or 0)
    return info


def encoder(path, width, height, fps, crf=16, preset="medium", tune=None, pix_fmt="yuv420p"):
    """Start an x264 encoder reading raw RGBA frames from stdin: p.stdin.write(frame.tobytes()); close(); wait()."""
    cmd = [ffmpeg(), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{width}x{height}",
           "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", preset, "-crf", str(crf)]
    if tune:
        cmd += ["-tune", tune]
    cmd += ["-pix_fmt", pix_fmt, path]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def concat(paths, out):
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
        for p in paths:
            fh.write(f"file '{os.path.abspath(p)}'\n")
        lst = fh.name
    try:
        subprocess.check_call([ffmpeg(), "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy",
                               out])
    finally:
        os.remove(lst)
    return out


def mux(video, audio, out, bitrate="320k", metadata=None):
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    cmd = [ffmpeg(), "-v", "error", "-y", "-i", video, "-i", audio, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
           "-c:a", "aac", "-b:a", bitrate, "-shortest", "-movflags", "+faststart"]
    for k, v in (metadata or {}).items():
        cmd += ["-metadata", f"{k}={v}"]
    subprocess.check_call(cmd + [out])
    return out
