"""Renderer API: render(context, frame_indices) yields one packed RGBA byte frame per index.

Register a class with the `codecinema.renderers` Python entry-point group.
The class must construct without arguments, expose a version string, and may
provide validate(context) for backend-specific fields. Third-party plugins are
installed Python code and carry the same trust requirements as any dependency.
"""

from importlib import import_module, metadata
import inspect
import hashlib
from pathlib import Path
from typing import Iterable, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from codecinema.engine.context import RenderContext


class FrameRenderer(Protocol):
    version: str

    def render(self, context: "RenderContext", frames: Iterable[int]) -> Iterable[bytes]: ...


BUILTINS = {
    "skia": {
        "title": "Skia · 2D",
        "description": "Fast illustrated landscapes and motion graphics",
        "factory": "codecinema.renderers.skia:Renderer",
    },
    "blender": {
        "title": "Blender · 3D",
        "description": "Lit 3D worlds, animated cameras or your own .blend scene",
        "factory": "codecinema.renderers.blender:Renderer",
    },
}


def plugins():
    result = {}
    for entry in metadata.entry_points(group="codecinema.renderers"):
        if entry.name in BUILTINS or entry.name in result:
            raise ValueError(f"Duplicate renderer name: {entry.name}")
        result[entry.name] = entry
    return result


def available():
    return {
        **{name: {k: v for k, v in spec.items() if k != "factory"} for name, spec in BUILTINS.items()},
        **{name: {"title": name, "description": "Installed renderer plugin"} for name in plugins()},
    }


def require(name):
    if not isinstance(name, str) or name not in available():
        raise ValueError(f"Unknown renderer {name!r}. Run: codecinema renderers")
    return name


def get_renderer(name):
    require(name)
    if name in BUILTINS:
        module, factory = BUILTINS[name]["factory"].split(":")
        renderer = getattr(import_module(module), factory)()
    else:
        renderer = plugins()[name].load()()
    if not callable(getattr(renderer, "render", None)) or not isinstance(getattr(renderer, "version", None), str):
        raise ValueError(f"Renderer {name!r} needs render(context, frames) and a version string")
    return renderer


def renderer_fingerprint(name):
    renderer = get_renderer(name)
    source = inspect.getfile(type(renderer))
    digest = hashlib.sha256(Path(source).read_bytes()).hexdigest()
    distribution = plugins().get(name)
    return {
        "name": name,
        "version": renderer.version,
        "source": digest,
        "distribution": distribution.dist.version if distribution and distribution.dist else "builtin",
    }
