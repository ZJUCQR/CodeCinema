"""Shared plan → picture + sound → assembly → QC for declarative films."""

import argparse
import json
import math
import os
import subprocess
import sys
import time
from PIL import Image, ImageDraw
from codecinema import diagnostics, media, settings, starters, procutil
from codecinema.audio import dsp, soundtrack
from codecinema.context import RenderContext
from codecinema.renderers import get_renderer


class Pipeline:
    def __init__(self, context):
        self.context = context
        self.renderer = get_renderer(context.renderer)
        if callable(getattr(self.renderer, "validate", None)):
            self.renderer.validate(context)

    def cmd_audio(self):
        soundtrack.generate(self.context)

    def cmd_stills(self):
        c = self.context
        c.out.mkdir(parents=True, exist_ok=True)
        frames = [(start + end) // 2 for _, start, end in c.scenes]
        tiles = []
        for pixels in self.renderer.render(c, frames):
            image = Image.frombytes("RGBA", (c.width, c.height), pixels).convert("RGB")
            if not tiles:
                c.final.parent.mkdir(parents=True, exist_ok=True)
                image.save(c.final.with_suffix(".jpg"), quality=92)
            image.thumbnail((480, 480))
            tiles.append(image)
        if len(tiles) != len(frames):
            raise ValueError("Renderer did not return all requested storyboard frames")
        columns = min(3, len(tiles))
        w, h = tiles[0].size
        sheet = Image.new("RGB", (columns * w, math.ceil(len(tiles) / columns) * (h + 30)), "#101c2c")
        draw = ImageDraw.Draw(sheet)
        for i, tile in enumerate(tiles):
            x, y = i % columns * w, i // columns * (h + 30)
            sheet.paste(tile, (x, y))
            draw.text((x + 12, y + h + 8), f"Scene {i + 1}", fill="#c7dddf")
        sheet.save(c.out / "storyboard.jpg", quality=90)
        print(f"Storyboard: {c.out / 'storyboard.jpg'}", flush=True)

    def cmd_plan(self):
        self.context.out.mkdir(parents=True, exist_ok=True)
        rows = [
            {
                "name": spec.get("name", f"Scene {i + 1}"),
                "preset": spec["preset"],
                "start_s": start / self.context.fps,
                "end_s": end / self.context.fps,
            }
            for i, (spec, start, end) in enumerate(self.context.scenes)
        ]
        (self.context.out / "plan.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
        print(
            f"{self.context.title} · {self.context.duration:g}s · {len(self.context.scenes)} scenes · {self.context.width}×{self.context.height} · {self.context.fps} fps",
            flush=True,
        )

    def marker(self, stage):
        return self.context.out / f"{stage}.json"

    def cmd_render(self):
        self.context.out.mkdir(parents=True, exist_ok=True)
        temporary = self.context.picture.with_name("picture.partial.mp4")
        quality = starters.QUALITIES.get(self.context.options.quality, {})
        encoder = media.encoder(
            str(temporary),
            self.context.width,
            self.context.height,
            self.context.fps,
            crf=int(quality.get("crf", settings.get("video", "crf", 16))),
            preset=quality.get("preset", settings.get("video", "preset", "medium")),
            tune="animation",
        )
        begin = time.monotonic()
        frame = -1
        try:
            for frame, pixels in enumerate(self.renderer.render(self.context, range(self.context.frames))):
                if frame >= self.context.frames or len(pixels) != self.context.width * self.context.height * 4:
                    raise ValueError("Renderer returned an unexpected frame or invalid RGBA size")
                encoder.stdin.write(pixels)
                if (frame + 1) % max(1, self.context.frames // 4) == 0:
                    print(
                        f"Picture {100 * (frame + 1) // self.context.frames}% · {time.monotonic() - begin:.1f}s",
                        flush=True,
                    )
            if frame + 1 != self.context.frames:
                raise ValueError("Renderer did not produce every requested frame")
            encoder.stdin.close()
            if encoder.wait() != 0:
                raise ValueError("FFmpeg could not encode the picture; check the message above")
            temporary.replace(self.context.picture)
            self.marker("picture").write_text(json.dumps({"signature": self.context.signature}), encoding="utf-8")
        finally:
            if encoder.poll() is None:
                encoder.terminate()
                encoder.wait()
            if encoder.stdin and not encoder.stdin.closed:
                encoder.stdin.close()
            temporary.unlink(missing_ok=True)

    def cmd_assemble(self):
        for stage, path in (("picture", self.context.picture), ("sound", self.context.sound)):
            stamp = self.marker(stage)
            if (
                not path.is_file()
                or not stamp.is_file()
                or json.loads(stamp.read_text())["signature"] != self.context.signature
            ):
                raise ValueError(
                    f"The {stage} is missing or was made with different settings. "
                    "Run all, or rerun render and audio with the same options."
                )
        self.context.final.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.context.final.with_name(self.context.final.stem + ".partial.mp4")
        try:
            media.mux(
                str(self.context.picture),
                str(self.context.sound),
                str(temporary),
                metadata={"title": self.context.title},
            )
            temporary.replace(self.context.final)
        finally:
            temporary.unlink(missing_ok=True)
        self.marker("master").write_text(json.dumps({"signature": self.context.signature}), encoding="utf-8")

    def cmd_qc(self):
        if not self.context.final.is_file() or not self.marker("master").is_file():
            raise ValueError("No finished film found. Run all first.")
        if json.loads(self.marker("master").read_text())["signature"] != self.context.signature:
            raise ValueError("The finished film uses different settings. Run all with the same options.")
        info = media.probe(str(self.context.final))
        expected = {
            "width": self.context.width,
            "height": self.context.height,
            "frames": self.context.frames,
            "audio_rate": dsp.SR,
            "fps": self.context.fps,
        }
        if (
            any(info.get(key) != val for key, val in expected.items())
            or abs(info["duration"] - self.context.duration) > 0.05 + 1 / self.context.fps
        ):
            raise ValueError(f"Film verification failed: {info}")
        subprocess.run(
            [media.ffmpeg(), "-v", "error", "-xerror", "-i", str(self.context.final), "-f", "null", "-"], check=True
        )
        (self.context.out / "qc.json").write_text(
            json.dumps({"passed": True, **info}, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Verified: {self.context.final} ({info['duration']:.2f}s, picture + stereo sound)", flush=True)

    def open_film(self):
        if sys.platform == "darwin":
            subprocess.run(["open", str(self.context.final)], check=True)
        elif sys.platform == "win32":
            os.startfile(str(self.context.final))
        else:
            import webbrowser

            webbrowser.open(self.context.final.as_uri())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "step", nargs="?", default="all", choices=("plan", "stills", "render", "audio", "assemble", "qc", "all")
    )
    parser.add_argument("--quality", choices=starters.QUALITIES)
    parser.add_argument("--format", choices=starters.FORMATS)
    parser.add_argument("--duration", type=float)
    parser.add_argument("--fps", type=int)
    parser.add_argument("--speech-engine", choices=("auto", "local", "system", "recording"), default="auto")
    parser.add_argument("--open", action="store_true")
    options = parser.parse_args(argv)
    try:
        if options.open and options.step not in ("all", "assemble", "qc"):
            raise ValueError("--open is available with all, assemble or qc")
        context = RenderContext.load(options)
        if options.step in ("render", "stills", "all"):
            problems = diagnostics.starter_problems(context.renderer)
            if problems:
                raise ValueError("\n".join(problems))
        pipeline = Pipeline(context)
        steps = ("plan", "stills", "render", "audio", "assemble", "qc") if options.step == "all" else (options.step,)
        context.out.parent.mkdir(parents=True, exist_ok=True)
        with (context.out.parent / ".production.lock").open("a+b") as lock:
            if not procutil.lock_file(lock, blocking=False):
                raise ValueError("This film is already rendering in another process")
            try:
                for step in steps:
                    getattr(pipeline, "cmd_" + step)()
            finally:
                procutil.unlock_file(lock)
        if options.open:
            pipeline.open_film()
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print(f"Film could not be completed: {exc}", file=sys.stderr)
        return 1
    return 0
