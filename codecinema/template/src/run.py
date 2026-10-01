"""
__FILM_TITLE__ - a CodeCinema film, started from the template.

    python src/run.py render     draw every frame (skia) and encode the picture
    python src/run.py audio      synthesize the sound track (codecinema.audio.dsp)
    python src/run.py assemble   mux picture + sound into the final film
    python src/run.py all

Replace draw_frame() and score() with your own film; keep the timing in frames and seconds from the settings.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FILM = os.path.dirname(HERE)
os.environ["CODECINEMA_FILM_DIR"] = FILM
_d = HERE
while not os.path.isfile(os.path.join(_d, "codecinema", "__init__.py")) and os.path.dirname(_d) != _d:
    _d = os.path.dirname(_d)
sys.path.insert(0, _d)

import numpy as np  # noqa: E402
import skia  # noqa: E402
from scipy.io import wavfile  # noqa: E402

from codecinema import media, settings  # noqa: E402
from codecinema.audio import dsp  # noqa: E402

W, H = int(settings.get("video", "width")), int(settings.get("video", "height"))
FPS = int(settings.get("video", "fps"))
DUR = float(settings.get("video", "duration_s", 6.0))
N_FRAMES = int(round(DUR * FPS))
OUT = settings.path("paths", "out_dir")
PICTURE = os.path.join(OUT, "picture.mp4")
SOUND = os.path.join(OUT, "sound.wav")
FINAL = settings.path("paths", "final_video")
TITLE = "__FILM_TITLE__"


def smooth(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def draw_frame(c, f):
    """One frame: a moon rises over layered hills while the title fades in."""
    t = f / FPS
    k = W / 1920.0
    c.clear(skia.Color4f(0.06, 0.07, 0.11, 1))
    sky = skia.GradientShader.MakeLinear([skia.Point(0, 0), skia.Point(0, H)],
                                         [skia.Color4f(0.10, 0.13, 0.24, 1), skia.Color4f(0.32, 0.26, 0.30, 1)])
    c.drawRect(skia.Rect.MakeWH(W, H), skia.Paint(Shader=sky))
    my = H * (0.78 - 0.42 * smooth(t / (DUR * 0.8)))
    glow = skia.GradientShader.MakeRadial(skia.Point(W * 0.62, my), 260 * k,
                                          [skia.Color4f(1, 0.95, 0.8, 0.35), skia.Color4f(1, 0.95, 0.8, 0)])
    c.drawCircle(W * 0.62, my, 260 * k, skia.Paint(Shader=glow, AntiAlias=True))
    c.drawCircle(W * 0.62, my, 70 * k, skia.Paint(Color4f=skia.Color4f(0.98, 0.95, 0.86, 1), AntiAlias=True))
    for i, (base, amp, col) in enumerate(((0.70, 0.10, 0.20), (0.80, 0.08, 0.13), (0.90, 0.06, 0.07))):
        p = skia.Path()
        p.moveTo(0, H)
        for x in range(0, W + 40, 40):
            y = H * (base - amp * (0.5 + 0.5 * math.sin(x / W * (5 + i * 2) + i * 1.7 + t * 0.05 * (i + 1))))
            p.lineTo(x, y)
        p.lineTo(W, H)
        p.close()
        c.drawPath(p, skia.Paint(Color4f=skia.Color4f(col, col * 1.05, col * 1.2, 1), AntiAlias=True))
    a = smooth((t - 1.0) / 1.5) * (1 - smooth((t - DUR + 0.8) / 0.8))
    if a > 0:
        font = skia.Font(skia.Typeface(""), 84 * k)
        blob = skia.TextBlob(TITLE, font)
        w = font.measureText(TITLE)
        c.drawTextBlob(blob, (W - w) / 2, H * 0.3, skia.Paint(Color4f=skia.Color4f(0.96, 0.92, 0.84, a),
                                                              AntiAlias=True))


def cmd_render():
    os.makedirs(OUT, exist_ok=True)
    surf = skia.Surface(W, H)
    enc = media.encoder(PICTURE, W, H, FPS, crf=int(settings.get("video", "crf", 16)), tune="animation")
    for f in range(N_FRAMES):
        draw_frame(surf.getCanvas(), f)
        enc.stdin.write(surf.makeImageSnapshot().toarray().tobytes())
    enc.stdin.close()
    if enc.wait() != 0:
        raise SystemExit("encoder failed")
    print(f"picture: {PICTURE} ({N_FRAMES} frames)")


def score():
    """A soft drone that swells with the moon, and a bell when the title appears."""
    n = dsp.n_of(DUR)
    t = dsp.t_axis(n)
    drone = sum(dsp.osc_sine(f, n) * a for f, a in ((110.0, 0.5), (165.0, 0.3), (220.5, 0.2)))
    drone *= dsp.env_points([(0, 0.0), (1.5, 0.35), (DUR - 1.0, 0.35), (DUR, 0.0)], n)
    drone *= 1 + 0.15 * np.sin(2 * np.pi * 0.25 * t)
    bell = np.zeros(n)
    at = dsp.n_of(1.0)
    m = n - at
    bell[at:] = dsp.additive(523.25, m, [(1, 1.0, 4.0), (2.76, 0.5, 2.5), (5.4, 0.25, 1.2), (8.9, 0.12, 0.7)])
    bell[at:] *= dsp.env_decay(m, 4.0)
    mix = dsp.pan_mono(drone * 0.6, -0.15) + dsp.pan_mono(bell * 0.5, 0.2)
    mix = mix + 0.35 * dsp.convolve_reverb(mix, "hall")
    mix = dsp.fade(dsp.normalize(mix, 0.8), 0.02, 0.8)
    out = dsp.limiter(mix, float(settings.get("audio", "true_peak_db", -1.0)))
    return out[0] if isinstance(out, tuple) else out


def cmd_audio():
    os.makedirs(OUT, exist_ok=True)
    y = score()
    wavfile.write(SOUND, dsp.SR, (np.clip(y.T, -1, 1) * 32767).astype(np.int16))
    print(f"sound: {SOUND}")


def cmd_assemble():
    media.mux(PICTURE, SOUND, FINAL, metadata={"title": TITLE})
    print(f"film: {FINAL}")


def main():
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    steps = {"render": [cmd_render], "audio": [cmd_audio], "assemble": [cmd_assemble],
             "all": [cmd_render, cmd_audio, cmd_assemble]}
    if step not in steps:
        raise SystemExit(__doc__)
    for fn in steps[step]:
        fn()
    return 0


if __name__ == "__main__":
    sys.exit(main())
