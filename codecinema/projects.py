"""Safe, reversible customization of the editable starter projects."""
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import tomlkit

from codecinema import registry, settings, starters

# Released starter renderer before spoken scenes. Match its full source so a
# user-modified renderer is never replaced by an automatic template update.
LEGACY_SILENT_RENDERERS = {"7c7c775432227b06a7e10a727cabc097af9c10fb32b72a63977cefdef6068915"}


def create(path, *, title, preset, seconds, format_name, quality, accent=None, subtitle=None):
    """Create a film folder and register its settings in the workspace configuration."""
    path = Path(path).absolute()
    if path.parent.name != "films" or not re.fullmatch(r"[a-z][a-z0-9_-]*", path.name):
        raise ValueError("Create films under films/<id>, using lower-case letters, digits, '-' or '_'")
    if os.path.lexists(path):
        raise ValueError(f"{path} already exists")
    data = starters.make_story(title, preset, seconds, subtitle)
    if accent is not None:
        for scene in data["scenes"]:
            scene["accent"] = accent
    starters.validate_story(data)
    width, height = starters.dimensions(format_name, quality)
    created = False
    try:
        with registry.edit(path) as document:
            config = document.get("tool", {}).get("codecinema", {})
            if "starter" not in config:
                raise ValueError("pyproject.toml needs [tool.codecinema.starter] defaults to create a film")
            if path.name in config.get("films", {}) or os.path.lexists(path):
                raise ValueError(f"{path.name} already exists; choose a new ID")
            meta = copy.deepcopy(config["starter"].unwrap())
            meta["title"] = title
            meta["env_prefix"] = re.sub(r"[^A-Z0-9]", "_", path.name.upper())
            meta.setdefault("settings", {}).setdefault("paths", {})["final_video"] = f"assets/film/{path.name}.mp4"
            meta["settings"].setdefault("video", {}).update(
                width=width, height=height, crf=starters.QUALITIES[quality]["crf"],
                preset=starters.QUALITIES[quality]["preset"],
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=".codecinema-", dir=path.parent) as temporary:
                staged = Path(temporary) / path.name
                source = Path(__file__).with_name("template")
                shutil.copytree(source, staged, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                for file in staged.rglob("*.md"):
                    content = file.read_text(encoding="utf-8")
                    content = content.replace("__FILM_ID__", path.name).replace("__FILM_TITLE__", title)
                    file.write_text(content, encoding="utf-8", newline="\n")
                (staged / "scenes.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                if os.path.lexists(path):
                    raise ValueError(f"{path} already exists")
                staged.rename(path)
                created = True
            config.setdefault("films", {})[path.name] = meta
    except Exception:
        if created:
            shutil.rmtree(path)
        raise
    return width, height


def read_starter(path):
    path = Path(path)
    if settings.film_meta(str(path)).get("template") != "starter-v1":
        raise ValueError("This film has its own production pipeline. Use its README; customize supports starter films.")
    data = json.loads((path / "scenes.json").read_text(encoding="utf-8"))
    starters.validate_story(data)
    return data


def customize(path, **changes):
    """Update one film under the workspace lock, retaining a reversible snapshot."""
    undo = []
    def rollback():
        for target, content in reversed(undo):
            registry.atomic_write(target, content)
    with registry.edit(path, rollback=rollback) as document:
        return _customize(path, document, undo, **changes)


def _customize(path, document, undo, *, title=None, subtitle=None, preset=None, seconds=None, format_name=None,
              quality=None, accent=None, story=None):
    """Validate all changes first, save a previous version, then update JSON and TOML."""
    path = Path(path)
    original = read_starter(path)
    data = copy.deepcopy(story if story is not None else original)
    before = starters.validate_story(data)
    if title is not None:
        old_title = data["title"]
        data["title"] = title
        for scene in data["scenes"]:
            if scene.get("title") == old_title:
                scene["title"] = title
    if subtitle is not None:
        data["scenes"][0]["subtitle"] = subtitle
    if preset is not None:
        if preset not in starters.PRESETS:
            raise ValueError("Unknown preset")
        for scene in data["scenes"]:
            scene["preset"] = preset
    if accent is not None:
        for scene in data["scenes"]:
            scene["accent"] = accent
    if seconds is not None:
        ratio = starters.duration(seconds) / before
        for scene in data["scenes"]:
            scene["duration_s"] *= ratio
    starters.validate_story(data)
    renderer = path / "src/run.py"
    replacement = None
    old_renderer = None
    if any(scene.get("narration", {}).get("text") for scene in data["scenes"]):
        old_renderer = renderer.read_text(encoding="utf-8")
        source_hash = hashlib.sha256(old_renderer.encode()).hexdigest()
        if source_hash in LEGACY_SILENT_RENDERERS:
            replacement = Path(__file__).with_name("template").joinpath("src/run.py").read_text(encoding="utf-8")
        elif '"narration"' not in old_renderer and "'narration'" not in old_renderer:
            raise ValueError("This customized renderer does not support spoken scenes. Your code has been preserved. "
                             "Create a new starter and copy its scene data, or merge the narration support from "
                             "codecinema/template/src/run.py. See README.md#speech.")
    previous = tomlkit.dumps(document)
    meta = document["tool"]["codecinema"]["films"][path.name]
    meta["title"] = data["title"]
    video = meta.setdefault("settings", {}).setdefault("video", {})
    current = settings.load(str(path))["video"]
    shape = format_name or ("square" if current["width"] == current["height"] else
                            "landscape" if current["width"] > current["height"] else "portrait")
    if quality is not None:
        width, height = starters.dimensions(shape, quality)
        video["crf"] = starters.QUALITIES[quality]["crf"]
        video["preset"] = starters.QUALITIES[quality]["preset"]
    elif format_name is not None:
        x, y = starters.FORMATS[shape]
        short = min(current["width"], current["height"])
        width, height = (round(short * part / min(x, y) / 2) * 2 for part in (x, y))
    else:
        width, height = current["width"], current["height"]
    video["width"] = width
    video["height"] = height
    backup = path / "out" / "edits" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup.mkdir(parents=True, exist_ok=True)
    (backup / "pyproject.toml").write_text(previous, encoding="utf-8")
    (backup / "scenes.json").write_text(json.dumps(original, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    updates = [(path / "scenes.json", json.dumps(data, ensure_ascii=False, indent=2) + "\n")]
    if replacement is not None:
        (backup / "run.py").write_text(old_renderer, encoding="utf-8")
        updates.insert(0, (renderer, replacement))
    for target, content in updates:
        undo.append((target, target.read_text(encoding="utf-8")))
        registry.atomic_write(target, content)
    return data
