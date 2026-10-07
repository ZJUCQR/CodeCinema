"""One clock for staging, camera cuts, score and synchronized effects."""

FPS = 24
SECONDS = 48
FRAMES = FPS * SECONDS
WIDTH, HEIGHT = 1920, 1080
SHOTS = (
    (0, 8, "An island in the clouds"),
    (8, 16, "The keeper listens"),
    (16, 24, "A small act of care"),
    (24, 32, "The instrument remembers"),
    (32, 40, "A signal crosses the sky"),
    (40, 48, "An answer"),
)
CUES = {"touch": 20.0, "ignition": 24.0, "signal": 32.0, "answer": 40.0}


def smooth(a, b, t):
    x = max(0.0, min(1.0, (t - a) / (b - a)))
    return x * x * x * (x * (x * 6 - 15) + 10)
