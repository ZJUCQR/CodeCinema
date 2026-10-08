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
