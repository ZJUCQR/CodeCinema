"""Film definitions in the workspace's pyproject.toml.

Reads use only the standard library, including inside Blender. Editing imports
tomlkit lazily to preserve comments and unrelated packaging configuration.
"""
from contextlib import contextmanager
import os
from pathlib import Path
import re
import tempfile
import threading
import tomllib

from codecinema import project_root

_EDIT_LOCK = threading.RLock()


def manifest(film_dir=None):
    return Path(project_root(film_dir)) / "pyproject.toml"


def config(root=None):
    path = Path(root) / "pyproject.toml" if root is not None else manifest()
    if not path.is_file():
        return {}
    with path.open("rb") as stream:
        return tomllib.load(stream).get("tool", {}).get("codecinema", {})


def definitions(root=None):
    films = config(root).get("films", {})
    if not isinstance(films, dict):
        raise ValueError("[tool.codecinema.films] must contain named film tables")
    for name, data in films.items():
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", name) or not isinstance(data, dict):
            raise ValueError(f"Invalid film entry in pyproject.toml: {name}")
    return films


def film_config(film_dir):
    path = Path(film_dir).resolve()
    root = manifest(path).parent
    if path.parent != root / "films":
        return {}
    return definitions(root).get(path.name, {})


def atomic_write(path, content):
    """Replace one text file only after the complete new content is on disk."""
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=path.parent, prefix="." + path.name + "-",
                                         suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            temporary.chmod(path.stat().st_mode)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@contextmanager
def edit(film_dir, rollback=None):
    """Serialize workspace edits across Studio threads and CLI processes."""
    import tomlkit
    from codecinema import procutil

    path = manifest(film_dir)
    if not path.is_file():
        raise ValueError("Run inside a CodeCinema workspace with a root pyproject.toml")
    lock_path = path.parent / "out" / ".config.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with _EDIT_LOCK, lock_path.open("a+b") as lock:
        if not procutil.lock_file(lock, blocking=True):
            raise OSError("Could not lock pyproject.toml; retry after the other edit finishes")
        try:
            previous = path.read_text(encoding="utf-8")
            document = tomlkit.parse(previous)
            yield document
            content = tomlkit.dumps(document)
            tomllib.loads(content)
            if content != previous:
                atomic_write(path, content)
        except Exception:
            if rollback is not None:
                rollback()
            raise
        finally:
            procutil.unlock_file(lock)
