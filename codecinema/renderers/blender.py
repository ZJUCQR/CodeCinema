"""Blender plates with the same text, timing, audio and delivery as Skia."""

import json
from pathlib import Path
from PIL import Image
from codecinema.runtime import blender
from codecinema.workspace import settings
from codecinema.renderers.skia import Renderer as Compositor


def validate(story, film):
    for scene in story["scenes"]:
        spec = scene.get("blender", {})
        if not isinstance(spec, dict):
            raise ValueError("scene.blender must be an object")
        if spec.get("file"):
            if not isinstance(spec["file"], str):
                raise ValueError("scene.blender.file must be a relative .blend path")
            path = (film / spec["file"]).resolve()
            if not path.is_relative_to(film.resolve()) or path.suffix != ".blend" or not path.is_file():
                raise ValueError("Blender scene files must be existing .blend files inside this film folder")
        for key in ("camera", "scene"):
            if key in spec and not isinstance(spec[key], str):
                raise ValueError(f"scene.blender.{key} must be text")
        if type(spec.get("frame_start", 1)) is not int:
            raise ValueError("scene.blender.frame_start must be an integer")


class Renderer:
    version = "1"

    def validate(self, context):
        validate(context.story, context.film)

    def render(self, context, frames):
        validate(context.story, context.film)
        frames = list(frames)
        folder = context.out / "blender" / context.signature
        folder.mkdir(parents=True, exist_ok=True)
        missing = []
        for frame in frames:
            path = folder / f"{frame:06d}.png"
            try:
                with Image.open(path) as image:
                    if image.size != (context.width, context.height):
                        raise ValueError("Wrong frame size")
                    image.verify()
            except (OSError, ValueError):
                missing.append(frame)
        if missing:
            samples = int(
                settings.get(
                    "render", "samples_preview" if context.options.quality == "preview" else "samples_final", 16
                )
            )
            if not 1 <= samples <= 4096:
                raise ValueError("Blender samples must be between 1 and 4096")
            job = {
                "film": str(context.film),
                "folder": str(folder),
                "frames": missing,
                "width": context.width,
                "height": context.height,
                "fps": context.fps,
                "scenes": context.scenes,
                "seed": context.story.get("seed", 7),
                "samples": samples,
            }
            path = folder / "job.json"
            path.write_text(json.dumps(job), encoding="utf-8")
            blender.run(Path(__file__).with_name("blender_scene.py"), path)
        compositor = Compositor()
        for frame in frames:
            with Image.open(folder / f"{frame:06d}.png") as image:
                yield compositor.composite(context, frame, image)
