"""Authored production packs, separate from film content and generated assets.

Packs run in isolated processes so Blender and their artistic modules can keep
independent dependencies. New declarative films use codecinema.engine.pipeline instead.
"""
import os
from pathlib import Path
from codecinema.workspace.paths import films_dir

BUILTINS = ("nightrevels", "silvergrass", "xishen")


def source_root(name):
    if name not in BUILTINS:
        raise ValueError(f"Unknown production pack: {name}")
    return Path(__file__).parent / name


def film_root(name):
    return Path(os.environ.get("CODECINEMA_FILM_DIR", Path(films_dir()) / name)).resolve()
