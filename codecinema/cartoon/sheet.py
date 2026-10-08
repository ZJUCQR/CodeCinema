"""Render the character library as one labelled picture (a "model sheet") with Blender."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

from codecinema.cartoon import cast, faces
from codecinema.workspace import settings
from codecinema.workspace.paths import IMPORT_ROOT


def character_sheet(path, names=None, width=2400, height=760, per_row=12):
    """Render the characters (default: the whole library) in rows of `per_row`, labelled, as one picture."""
    from PIL import Image, ImageDraw
    from codecinema.cartoon.finish import font_for
    names = names or list(cast.ARCHETYPES)
    path = Path(path).absolute()
    rows = [names[i:i + per_row] for i in range(0, len(names), per_row)]
    images = []
    with tempfile.TemporaryDirectory(prefix="codecinema-sheet-") as work:
        work = Path(work)
        for k, row in enumerate(rows):
            out = work / f"row{k}.png"
            chars = []
            for name in row:
                spec = cast.resolve({"from": name}, name)
                chars.append({"id": name, "spec": spec, "metrics": cast.metrics(spec),
                              "atlas": faces.paint(spec["face"], work / "faces")})
            job = work / f"row{k}.json"
            job.write_text(json.dumps({"import_root": str(IMPORT_ROOT), "characters": chars, "out": str(out),
                                       "width": width, "height": height}), encoding="utf-8")
            script = Path(__file__).parent / "blender" / "sheet.py"
            subprocess.run([settings.tool("blender"), "-b", "--factory-startup", "--python-exit-code", "1",
                            "--python", str(script), "--", str(job)], check=True, stdout=subprocess.DEVNULL,
                           env=dict(os.environ, PYTHONIOENCODING="utf-8"))
            labels = json.loads(Path(str(out) + ".labels.json").read_text(encoding="utf-8"))
            image = Image.open(out).convert("RGB")
            draw = ImageDraw.Draw(image)
            font = font_for("Aa", int(height * 0.034), 500)
            for label in labels:
                draw.text((label["x"] * width, (1 - label["y"]) * height + height * 0.045),
                          label["name"].replace("_", " "), font=font, fill="#3a3f4b", anchor="mm")
            images.append(image)
    sheet = Image.new("RGB", (width, height * len(images)))
    for k, image in enumerate(images):
        sheet.paste(image, (0, k * height))
    sheet.save(path)
    return path
