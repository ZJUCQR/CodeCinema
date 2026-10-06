"""
CodeCinema - a framework for making complete short films with code.

    codecinema.settings   per-film settings (film.toml + local overrides + environment), tool and font discovery
    codecinema.procutil   cross-platform process / lock / memory helpers
    codecinema.audio.dsp  audio DSP toolkit (oscillators, filters, physical models, reverb, loudness, limiter)
    codecinema.media      ffmpeg helpers (probe, concat, mux)
    codecinema.films      film discovery and step running
    codecinema.cli        the `codecinema` / `python -m codecinema` command line
"""
import os

__version__ = "1.1.0"
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def project_root(start=None):
    """The project folder: the nearest folder at or above `start` (default: the working directory) that has a
    films/ folder, so an installed `codecinema` command works inside any clone; else the package's parent."""
    cur = os.path.abspath(start or os.getcwd())
    while True:
        if os.path.isdir(os.path.join(cur, "films")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return REPO
        cur = parent


def films_dir(start=None):
    return os.path.join(project_root(start), "films")
