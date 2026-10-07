"""Small, actionable dependency checks for first-time film makers."""
import importlib
import os
import shutil
import sys

from codecinema import settings

STARTER_MODULES = ("numpy", "scipy", "PIL", "skia")


def tool_available(path):
    return bool(shutil.which(path) or (os.path.isfile(path) and os.access(path, os.X_OK)))


def ffmpeg_help():
    if sys.platform == "darwin":
        return "Install FFmpeg: brew install ffmpeg"
    if sys.platform == "win32":
        return "Install FFmpeg: winget install Gyan.FFmpeg (then reopen your terminal)"
    return "Install FFmpeg: sudo apt-get install ffmpeg (or use your distribution's package manager)"


def graphics_help():
    if sys.platform.startswith("linux"):
        return "Skia's Linux runtime needs: sudo apt-get install libgl1 libegl1 libfontconfig1"
    return "Install the Python dependencies in this environment: python -m pip install ."


def starter_problems(renderer="skia"):
    from codecinema.renderers import require
    require(renderer)
    problems = []
    for name in STARTER_MODULES:
        try:
            importlib.import_module(name)
        except (ImportError, OSError) as exc:
            problems.append(f"Could not load {name}: {exc}. " +
                            (graphics_help() if name == "skia" else "Run: python -m pip install ."))
    tools = [name for name in ("ffmpeg", "ffprobe") if not tool_available(settings.tool(name))]
    if tools:
        problems.append(f"Missing tools: {', '.join(tools)}. {ffmpeg_help()}")
    if renderer == "blender" and not tool_available(settings.tool("blender")):
        problems.append("Install Blender 5.2 or later, or set BLENDER_BIN to its executable.")
    return problems
