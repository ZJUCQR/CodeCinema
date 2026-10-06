"""
codecinema.films - discover the films in films/*/film.toml and run their steps.

A film is any directory with a film.toml whose [film] table names an `entry` script (relative to the film) and the
`steps` it accepts; `run(film, step, args)` executes `python <entry> <step> <args...>` inside the film directory with
CODECINEMA_FILM_DIR set, so every module of the film (and the framework) reads that film's settings.
"""
import os
import subprocess
import sys

from codecinema import films_dir
from codecinema.settings import film_meta


class Film:
    def __init__(self, path):
        self.dir = os.path.abspath(path)
        meta = film_meta(self.dir)
        self.id = meta.get("id", os.path.basename(self.dir))
        self.title = meta.get("title", self.id)
        self.title_zh = meta.get("title_zh", "")
        self.description = meta.get("description", "")
        self.entry = os.path.join(self.dir, meta.get("entry", "src/run.py"))
        self.steps = list(meta.get("steps", ["all"]))
        self.requires = list(meta.get("requires", []))

    def run(self, step, args=()):
        if self.steps and step not in self.steps:
            raise SystemExit(f"{self.id}: unknown step '{step}' (steps: {', '.join(self.steps)})")
        env = dict(os.environ, CODECINEMA_FILM_DIR=self.dir)
        env.setdefault("PYTHONIOENCODING", "utf-8")
        return subprocess.call([sys.executable, self.entry, step, *args], cwd=self.dir, env=env)


def discover(root=None):
    root = root or films_dir()
    out = {}
    if os.path.isdir(root):
        for name in sorted(os.listdir(root)):
            if name.startswith("."):
                continue
            d = os.path.join(root, name)
            if os.path.isfile(os.path.join(d, "film.toml")):
                f = Film(d)
                out[f.id] = f
    return out
