"""A frame-accurate story and the paths shared by every production stage."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from codecinema.workspace import settings
from codecinema.workspace import story as starters
from codecinema.workspace.paths import PACKAGE_ROOT


@dataclass(frozen=True)
class RenderContext:
    film: Path
    story: dict
    scenes: tuple
    title: str
    renderer: str
    width: int
    height: int
    fps: int
    frames: int
    duration: float
    out: Path
    picture: Path
    sound: Path
    final: Path
    signature: str
    options: Any

    @classmethod
    def load(cls, options):
        film = Path(settings.ROOT)
        story = json.loads((film / "scenes.json").read_text(encoding="utf-8"))
        seconds = starters.validate_story(story)
        width, height = int(settings.get("video", "width")), int(settings.get("video", "height"))
        shape = options.format or ("square" if width == height else "landscape" if width > height else "portrait")
        if options.quality:
            width, height = starters.dimensions(shape, options.quality)
        elif options.format:
            x, y = starters.FORMATS[shape]
            short = min(width, height)
            width, height = (round(short * part / min(x, y) / 2) * 2 for part in (x, y))
        fps = options.fps if options.fps is not None else int(settings.get("video", "fps", 24))
        if not (64 <= width <= 7680 and 64 <= height <= 7680 and width % 2 == height % 2 == 0):
            raise ValueError("Video dimensions must be even integers between 64 and 7680")
        if not 1 <= fps <= 120:
            raise ValueError("fps must be between 1 and 120")
        if not 8000 <= int(settings.get("audio", "sample_rate", 48000)) <= 192000:
            raise ValueError("audio.sample_rate must be between 8000 and 192000")
        if not 0 <= int(settings.get("video", "crf", 16)) <= 51:
            raise ValueError("video.crf must be between 0 and 51")
        frames = round((starters.duration(options.duration) if options.duration is not None else seconds) * fps)
        scenes, elapsed = [], 0.0
        for spec in story["scenes"]:
            start = round(elapsed / seconds * frames)
            elapsed += spec["duration_s"]
            end = round(elapsed / seconds * frames)
            if end <= start:
                raise ValueError("A scene has no frames. Increase duration or fps")
            scenes.append((spec, start, end))
        preview = options.quality == "preview"
        out = Path(settings.path("paths", "out_dir")) / ("preview" if preview else "master")
        final = Path(settings.path("paths", "final_video"))
        if preview:
            final = final.with_name(final.stem + "_preview.mp4")
        renderer = settings.film_meta(str(film)).get("renderer", "skia")
        from codecinema.renderers import renderer_fingerprint

        data = {
            "story": story,
            "width": width,
            "height": height,
            "fps": fps,
            "frames": frames,
            "settings": settings.SETTINGS,
            "quality": options.quality,
            "renderer": renderer_fingerprint(renderer),
        }
        if any(s.get("narration", {}).get("text") for s in story["scenes"]):
            from codecinema.audio import speech

            data["speech_engine"] = (
                ("local" if speech.local_available() else "system")
                if options.speech_engine == "auto"
                else options.speech_engine
            )
        digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode())
        package = PACKAGE_ROOT
        sources = [
            package / "engine/context.py",
            package / "engine/pipeline.py",
            package / "workspace/story.py",
            *sorted((package / "renderers").glob("*.py")),
            *sorted((package / "audio").glob("*.py")),
        ]
        # Imported Blender scenes can also use local textures or models.
        assets = film / "assets"
        if assets.exists():
            sources += sorted(p for p in assets.rglob("*") if p.is_file() and p.relative_to(assets).parts[0] != "film")
        for path in sources:
            digest.update(
                str(path.relative_to(film) if path.is_relative_to(film) else path.relative_to(package)).encode()
            )
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
        return cls(
            film,
            story,
            tuple(scenes),
            story["title"],
            renderer,
            width,
            height,
            fps,
            frames,
            frames / fps,
            out,
            out / "picture.mp4",
            out / "sound.wav",
            final,
            digest.hexdigest(),
            options,
        )
