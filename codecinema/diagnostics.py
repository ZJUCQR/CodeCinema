"""Small, actionable dependency checks for first-time film makers."""
import importlib.util
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


def starter_problems():
    missing = [name for name in STARTER_MODULES if importlib.util.find_spec(name) is None]
    problems = []
    if missing:
        problems.append(f"Missing Python packages: {', '.join(missing)}. Run: python -m pip install .")
    tools = [name for name in ("ffmpeg", "ffprobe") if not tool_available(settings.tool(name))]
    if tools:
        problems.append(f"Missing tools: {', '.join(tools)}. {ffmpeg_help()}")
    return problems
