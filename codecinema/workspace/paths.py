"""Resolve workspace and package locations without importing production dependencies."""

import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
IMPORT_ROOT = PACKAGE_ROOT.parent
REPO = str(IMPORT_ROOT)


def project_root(start=None):
    """Nearest workspace with pyproject.toml, otherwise the package's parent."""
    cur = os.path.abspath(start or os.getcwd())
    while True:
        if os.path.isfile(os.path.join(cur, "pyproject.toml")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return REPO
        cur = parent


def films_dir(start=None):
    return os.path.join(project_root(start), "films")


def film_assets(film):
    """The workspace's asset directory for a film, independent of its code."""
    film = Path(film).absolute()
    return Path(project_root(film)) / "assets" / film.name


def resolve_path(value, film):
    """Resolve assets/ paths from the workspace, other relative paths from the film."""
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    base = Path(project_root(film)) if path.parts and path.parts[0] == "assets" else Path(film)
    return base / path


def resource_dir(name):
    """Shared source resources, or their bundled copies in an installed wheel."""
    if name not in ("studio", "scaffold", "fonts"):
        raise ValueError(f"Unknown framework resource: {name}")
    for base in (PACKAGE_ROOT / "_assets", IMPORT_ROOT / "assets" / "_shared"):
        path = base / name
        if path.is_dir():
            return path
    raise FileNotFoundError(f"Missing CodeCinema {name} resources. Reinstall the framework.")
