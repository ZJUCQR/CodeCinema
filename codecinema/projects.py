"""Safe, reversible customization of the editable starter projects."""
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import tomllib

from codecinema import settings, starters


def create(path, *, title, preset, seconds, format_name, quality, accent=None, subtitle=None):
    """Prepare the complete starter privately, then make it visible in one rename."""
    path = Path(path)
    if os.path.lexists(path):
        raise ValueError(f"{path} already exists")
    data = starters.make_story(title, preset, seconds, subtitle)
    if accent is not None:
        for scene in data["scenes"]:
            scene["accent"] = accent
    starters.validate_story(data)
    width, height = starters.dimensions(format_name, quality)
    values = {"__FILM_ID__": path.name, "__ENV_PREFIX__": re.sub(r"[^A-Z0-9]", "_", path.name.upper())}
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".codecinema-", dir=path.parent) as temporary:
        staged = Path(temporary) / path.name
        source = Path(__file__).with_name("template")
        shutil.copytree(source, staged, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for file in staged.rglob("*"):
            if not file.is_file() or file.name == "scenes.json":
                continue
            content = file.read_text(encoding="utf-8")
            pattern = "|".join(values)
            if file.suffix != ".py":
                content = re.sub(pattern, lambda match: values[match.group()], content)
            if file.name == "film.toml":
                content = replace_value(content, "film", "title", title)
                for key, value in (("width", width), ("height", height), ("crf", starters.QUALITIES[quality]["crf"]),
                                   ("preset", starters.QUALITIES[quality]["preset"])):
                    content = replace_value(content, "settings.video", key, value)
                tomllib.loads(content)
            else:
                content = content.replace("__FILM_TITLE__", title)
            file.write_text(content, encoding="utf-8", newline="\n")
        (staged / "scenes.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if os.path.lexists(path):
            raise ValueError(f"{path} already exists")
        staged.rename(path)
    return width, height


def replace_value(text, section, key, value):
    header = re.search(rf"(?m)^\[{re.escape(section)}\]\s*$", text)
    if not header:
        return text.rstrip() + f"\n\n[{section}]\n{key} = {json.dumps(value, ensure_ascii=False)}\n"
    next_header = re.search(r"(?m)^\[", text[header.end():])
    end = header.end() + next_header.start() if next_header else len(text)
    block = text[header.end():end]
    line = f"{key} = {json.dumps(value, ensure_ascii=False)}"
    pattern = rf"(?m)^{re.escape(key)}\s*=.*$"
    if re.search(pattern, block):
        block = re.sub(pattern, lambda _: line, block)
    else:
        block = block.rstrip() + "\n" + line + "\n\n"
    return text[:header.end()] + block + text[end:]


def read_starter(path):
    path = Path(path)
    if settings.film_meta(str(path)).get("template") != "starter-v1":
        raise ValueError("This film has its own production pipeline. Use its README; customize supports starter films.")
    data = json.loads((path / "scenes.json").read_text(encoding="utf-8"))
    starters.validate_story(data)
    return data


def customize(path, *, title=None, subtitle=None, preset=None, seconds=None, format_name=None,
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
    manifest = path / "film.toml"
    previous = manifest.read_text(encoding="utf-8")
    text = replace_value(previous, "film", "title", data["title"])
    current = settings.load(str(path))["video"]
    shape = format_name or ("square" if current["width"] == current["height"] else
                            "landscape" if current["width"] > current["height"] else "portrait")
    if quality is not None:
        width, height = starters.dimensions(shape, quality)
        text = replace_value(text, "settings.video", "crf", starters.QUALITIES[quality]["crf"])
        text = replace_value(text, "settings.video", "preset", starters.QUALITIES[quality]["preset"])
    elif format_name is not None:
        x, y = starters.FORMATS[shape]
        short = min(current["width"], current["height"])
        width, height = (round(short * part / min(x, y) / 2) * 2 for part in (x, y))
    else:
        width, height = current["width"], current["height"]
    text = replace_value(text, "settings.video", "width", width)
    text = replace_value(text, "settings.video", "height", height)
    tomllib.loads(text)
    backup = path / "out" / "edits" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup.mkdir(parents=True, exist_ok=True)
    (backup / "film.toml").write_text(previous, encoding="utf-8")
    (backup / "scenes.json").write_text(json.dumps(original, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for target, content in ((path / "scenes.json", json.dumps(data, ensure_ascii=False, indent=2) + "\n"),
                            (manifest, text)):
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(content, encoding="utf-8", newline="\n")
        temporary.replace(target)
    return data
