"""One clock for staging, camera cuts, score and synchronized effects."""

from codecinema.productions import film_root
import json

_story = json.loads((film_root("beacon") / "story.json").read_text(encoding="utf-8"))

FPS = 24
SECONDS = 48
FRAMES = FPS * SECONDS
WIDTH, HEIGHT = 1920, 1080
SHOTS = _story["shots"]
CUES = _story["cues"]


def smooth(a, b, t):
    x = max(0.0, min(1.0, (t - a) / (b - a)))
    return x * x * x * (x * (x * 6 - 15) + 10)
