"""Film-side alias of codecinema.procutil (import procutil)."""

from codecinema.productions import film_root
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("CODECINEMA_FILM_DIR", str(film_root("silvergrass")))
_d = _HERE
while not os.path.isfile(os.path.join(_d, "codecinema", "__init__.py")) and os.path.dirname(_d) != _d:
    _d = os.path.dirname(_d)
if _d not in sys.path:
    sys.path.insert(0, _d)
from codecinema import procutil as _m  # noqa: E402

sys.modules[__name__] = _m
