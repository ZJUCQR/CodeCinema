"""Film-side alias of the shared DSP toolkit codecinema.audio.dsp (import dsp)."""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
os.environ["CODECINEMA_FILM_DIR"] = os.path.abspath(os.path.join(_HERE, "..", ".."))
_d = _HERE
while not os.path.isfile(os.path.join(_d, "codecinema", "__init__.py")) and os.path.dirname(_d) != _d:
    _d = os.path.dirname(_d)
if _d not in sys.path:
    sys.path.insert(0, _d)
_COMMON = os.path.join(_HERE, "..", "common")     # the film's config, importable by the audio modules
if _COMMON not in sys.path:
    sys.path.insert(0, _COMMON)
from codecinema.audio import dsp as _m  # noqa: E402

sys.modules[__name__] = _m
