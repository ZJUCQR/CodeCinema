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


def character_sheet(path, names=None, width=2400, height=760):
    names = names or list(cast.ARCHETYPES)
    path = Path(path).absolute()
    with tempfile.TemporaryDirectory(prefix="codecinema-sheet-") as work:
        work = Path(work)
        rows = []
        for name in names:
            spec = cast.resolve({"from": name}, name)
            rows.append({"id": name, "spec": spec, "metrics": cast.metrics(spec),
                         "atlas": faces.paint(spec["face"], work / "faces")})
        job = work / "sheet.json"
        job.write_text(json.dumps({"import_root": str(IMPORT_ROOT), "characters": rows, "out": str(path),
                                   "width": width, "height": height}), encoding="utf-8")
        script = Path(__file__).parent / "blender" / "sheet.py"
        subprocess.run([settings.tool("blender"), "-b", "--factory-startup", "--python-exit-code", "1", "--python",
                        str(script), "--", str(job)], check=True, stdout=subprocess.DEVNULL,
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        labels = json.loads((work / "labels.json").read_text(encoding="utf-8")) if (work / "labels.json").is_file() \
            else json.loads(Path(str(path) + ".labels.json").read_text(encoding="utf-8"))
    from PIL import Image, ImageDraw
    from codecinema.cartoon.finish import font_for
    image = Image.open(path).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = font_for("Aa", int(height * 0.034), 500)
    for row in labels:
        label = row["name"].replace("_", " ")
        draw.text((row["x"] * width, (1 - row["y"]) * height + height * 0.045), label, font=font,
                  fill="#3a3f4b", anchor="mm")
    image.save(path)
    Path(str(path) + ".labels.json").unlink(missing_ok=True)
    return path
