"""CodeCinema: content in workspace, production in engine, pictures in renderers.

Import implementation modules from their responsibility-based packages.
The former ``from codecinema import settings, media, ...`` convenience imports
remain available for existing film entry scripts and extensions.
"""

from importlib import import_module

from codecinema.workspace.paths import REPO, films_dir, project_root

__version__ = "2.0.0"
__all__ = ["__version__", "REPO", "films_dir", "project_root"]

_ALIASES = {
    "settings": "workspace.settings",
    "registry": "workspace.registry",
    "films": "workspace.films",
    "projects": "workspace.projects",
    "starters": "workspace.story",
    "context": "engine.context",
    "pipeline": "engine.pipeline",
    "worker": "engine.worker",
    "blender": "runtime.blender",
    "media": "runtime.media",
    "procutil": "runtime.process",
    "diagnostics": "runtime.diagnostics",
}


def __getattr__(name):
    if name not in _ALIASES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(f".{_ALIASES[name]}", __name__)
    globals()[name] = module
    return module
