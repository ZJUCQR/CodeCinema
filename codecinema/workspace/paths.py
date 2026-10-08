"""Resolve workspace and package locations without importing production dependencies."""

import glob
import os
import sys
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


def font_dirs(film=None):
    """Font folders as (path, kind) pairs, kind "user" (the film's assets/<id>/fonts and the workspace's
    assets/_shared/fonts first), "bundled", "user" (the per-user font folder) or "system". Missing folders included."""
    home = Path.home()
    out = []
    if film:
        out.append((film_assets(film) / "fonts", "user"))
    out.append((Path(project_root(film)) / "assets" / "_shared" / "fonts", "user"))
    out += [(PACKAGE_ROOT / "_assets" / "fonts", "bundled"), (IMPORT_ROOT / "assets" / "_shared" / "fonts", "bundled")]
    if sys.platform == "darwin":
        out += [(home / "Library" / "Fonts", "user"), (Path("/Library/Fonts"), "system"),
                (Path("/System/Library/Fonts"), "system"), (Path("/Network/Library/Fonts"), "system")]
        out += [(Path(p), "system") for p in sorted(glob.glob(
            "/System/Library/AssetsV2/com_apple_MobileAsset_Font*/*/AssetData"))]
    elif sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA") or str(home / "AppData" / "Local")
        out += [(Path(local) / "Microsoft" / "Windows" / "Fonts", "user"),
                (Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts", "system")]
    else:
        data = os.environ.get("XDG_DATA_HOME") or str(home / ".local" / "share")
        out += [(Path(data) / "fonts", "user"), (home / ".fonts", "user")]
        for base in (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(os.pathsep):
            if base:
                out.append((Path(base) / "fonts", "system"))
        out += [(Path("/usr/share/fonts"), "system"), (Path("/usr/local/share/fonts"), "system")]
    def same(path):
        return os.path.normcase(os.path.realpath(path))

    # In a source checkout the workspace's shared fonts are the bundled ones.
    bundled = {same(PACKAGE_ROOT / "_assets" / "fonts"), same(IMPORT_ROOT / "assets" / "_shared" / "fonts")}
    seen, unique = set(), []
    for path, kind in out:
        resolved = same(path)
        if resolved not in seen:
            seen.add(resolved)
            unique.append((path, "bundled" if resolved in bundled else kind))
    return unique
