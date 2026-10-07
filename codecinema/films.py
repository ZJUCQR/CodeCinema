"""Discover data-only film projects and run isolated production workers."""

import os
import subprocess
import sys
from pathlib import Path

from codecinema import films_dir, registry
from codecinema.settings import film_meta


class Film:
    def __init__(self, path):
        self.dir = os.path.abspath(path)
        meta = film_meta(self.dir)
        if not meta:
            raise ValueError(f"Film is not registered in pyproject.toml: {self.dir}")
        self.id = meta.get("id", os.path.basename(self.dir))
        self.title = meta.get("title", self.id)
        self.title_zh = meta.get("title_zh", "")
        self.description = meta.get("description", "")
        self.production = meta.get("production", "story")
        self.renderer = meta.get("renderer", "skia")
        self.legacy_entry = meta.get("entry")
        self.steps = list(meta.get("steps", ["all"]))
        self.requires = list(meta.get("requires", []))

    def command(self, step, args=()):
        if self.steps and step not in self.steps:
            raise SystemExit(f"{self.id}: unknown step '{step}' (steps: {', '.join(self.steps)})")
        return [sys.executable, "-m", "codecinema.worker", self.dir, step, *args]

    def run(self, step, args=()):
        env = dict(os.environ, CODECINEMA_FILM_DIR=self.dir)
        env.setdefault("PYTHONIOENCODING", "utf-8")
        env["PYTHONPATH"] = os.pathsep.join(
            filter(None, (str(Path(__file__).resolve().parent.parent), env.get("PYTHONPATH")))
        )
        return subprocess.call(self.command(step, args), cwd=self.dir, env=env)


def discover(root=None):
    root = root or films_dir()
    out = {}
    if os.path.isdir(root):
        for name in sorted(registry.definitions(os.path.dirname(os.path.abspath(root)))):
            d = os.path.join(root, name)
            if os.path.isdir(d):
                f = Film(d)
                out[f.id] = f
    return out
