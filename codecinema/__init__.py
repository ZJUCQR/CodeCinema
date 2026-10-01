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

__version__ = "1.0.0"
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FILMS_DIR = os.path.join(REPO, "films")
