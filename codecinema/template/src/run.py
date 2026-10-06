"""A configurable CodeCinema starter. Edit scenes.json, or replace draw_frame() and score()."""
import argparse
from functools import lru_cache
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

FILM = Path(__file__).resolve().parents[1]
os.environ["CODECINEMA_FILM_DIR"] = str(FILM)
for parent in FILM.parents:
    if (parent / "codecinema" / "__init__.py").is_file():
        sys.path.insert(0, str(parent))
        break

try:
    import numpy as np
    from PIL import Image, ImageDraw
    import skia
    from scipy.io import wavfile
except ImportError as exc:
    raise SystemExit(f"Missing Python dependency: {exc.name}. Run: python -m pip install .") from None

from codecinema import diagnostics, media, settings, starters
from codecinema.audio import dsp

PALETTES = {
    "moonrise": {"sky": ("#111c36", "#6a5975"), "hills": ("#38475c", "#25354b", "#152338"),
                 "accent": "#efe0b8", "water": "#17283c", "root": 110.0},
    "sunset": {"sky": ("#543f73", "#efa07d"), "hills": ("#9c6380", "#6c4d70", "#3d405d"),
               "accent": "#ffddb2", "water": "#645275", "root": 146.83},
    "aurora": {"sky": ("#071b30", "#264e61"), "hills": ("#304e62", "#1c3549", "#0b2132"),
               "accent": "#b1ead0", "water": "#122d40", "root": 130.81},
    "neon": {"sky": ("#100b2b", "#633263"), "hills": ("#342143", "#221c38", "#13192e"),
             "accent": "#ed9cd4", "water": "#191a35", "root": 123.47},
    "ocean": {"sky": ("#259bbd", "#a0ded7"), "hills": ("#68b0bb", "#418d9f", "#25788e"),
              "accent": "#fff0c7", "water": "#238da9", "root": 164.81},
    "ink": {"sky": ("#eee6d4", "#d9d3bf"), "hills": ("#b2b4a6", "#858f86", "#536b64"),
            "accent": "#b35850", "water": "#d6d4c1", "root": 98.0},
    "cosmos": {"sky": ("#090e29", "#362350"), "hills": ("#34234d", "#271f3a", "#17182e"),
               "accent": "#d4b2ef", "water": "#181b3c", "root": 82.41},
    "ember": {"sky": ("#151c2d", "#6b5054"), "hills": ("#41454d", "#2f3a3e", "#1b2a2d"),
              "accent": "#f8ce8e", "water": "#1b2a2d", "root": 116.54},
}


def smooth(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def color(hex_value, alpha=1.0):
    return skia.Color4f(*(int(hex_value[i:i + 2], 16) / 255 for i in (1, 3, 5)), alpha)


def paint(hex_value, alpha=1.0):
    return skia.Paint(AntiAlias=True, Color4f=color(hex_value, alpha))


def glow(canvas, x, y, radius, hex_value, alpha):
    shader = skia.GradientShader.MakeRadial(skia.Point(x, y), radius,
                                          [color(hex_value, alpha), color(hex_value, 0)])
    canvas.drawCircle(x, y, radius, skia.Paint(Shader=shader, AntiAlias=True))


def find_typeface(text):
    chars = "".join(sorted(set(text) - set("\n\r\t")))
    explicit = settings.get("fonts", "ui", "")
    paths = [os.path.expanduser(explicit)] if explicit else [settings.font("ui"), settings.font("song")]
    candidates = [skia.Typeface.MakeFromFile(p) for p in paths if p and os.path.isfile(p)]
    if explicit and not candidates:
        raise ValueError("fonts.ui does not point to a readable font file")
    if not explicit:
        manager = skia.FontMgr.RefDefault()
        for family in ("Arial", "DejaVu Sans", "Liberation Sans", "Noto Sans", "PingFang SC",
                       "Noto Sans CJK SC", "Microsoft YaHei", "WenQuanYi Zen Hei"):
            candidates.append(manager.matchFamilyStyle(family, skia.FontStyle()))
    for face in candidates:
        if face and all(skia.Font(face, 20).textToGlyphs(chars)):
            return face
    raise ValueError("The title or captions contain unsupported characters. Install a suitable font "
                     "(e.g. Noto Sans CJK for Chinese) or set [fonts] ui in film.local.toml.")


def configure(options):
    global W, H, FPS, DUR, N_FRAMES, TITLE, STORY, SCENES, OUT, PICTURE, SOUND, FINAL, KEY, FACE, STARS, LAYER
    STORY = json.loads((FILM / "scenes.json").read_text(encoding="utf-8"))
    seconds = starters.validate_story(STORY)
    TITLE = STORY["title"]
    W, H = int(settings.get("video", "width")), int(settings.get("video", "height"))
    shape = options.format or ("square" if W == H else "landscape" if W > H else "portrait")
    if options.quality:
        W, H = starters.dimensions(shape, options.quality)
    elif options.format:
        x, y = starters.FORMATS[shape]
        short = min(W, H)
        W, H = (round(short * part / min(x, y) / 2) * 2 for part in (x, y))
    FPS = options.fps if options.fps is not None else int(settings.get("video", "fps", 24))
    if not (64 <= W <= 7680 and 64 <= H <= 7680 and W % 2 == H % 2 == 0):
        raise ValueError("video width and height must be even integers between 64 and 7680")
    if not 1 <= FPS <= 120:
        raise ValueError("fps must be between 1 and 120")
    if not 8000 <= dsp.SR <= 192000:
        raise ValueError("audio.sample_rate must be between 8000 and 192000")
    if not 0 <= int(settings.get("video", "crf", 16)) <= 51:
        raise ValueError("video.crf must be between 0 and 51")
    total = starters.duration(options.duration) if options.duration is not None else seconds
    N_FRAMES = round(total * FPS)
    DUR = N_FRAMES / FPS
    SCENES = []
    elapsed = 0.0
    for spec in STORY["scenes"]:
        start = round(elapsed / seconds * N_FRAMES)
        elapsed += spec["duration_s"]
        end = round(elapsed / seconds * N_FRAMES)
        if end <= start:
            raise ValueError("A scene has no frames; increase --duration or --fps")
        SCENES.append((spec, start, end))
    preview = options.quality == "preview"
    OUT = Path(settings.path("paths", "out_dir")) / ("preview" if preview else "master")
    PICTURE, SOUND = OUT / "picture.mp4", OUT / "sound.wav"
    FINAL = Path(settings.path("paths", "final_video"))
    if preview:
        FINAL = FINAL.with_name(FINAL.stem + "_preview.mp4")
    data = {"story": STORY, "width": W, "height": H, "fps": FPS, "duration": DUR,
            "settings": settings.SETTINGS, "quality": options.quality}
    KEY = hashlib.sha256(Path(__file__).read_bytes() + json.dumps(data, sort_keys=True).encode()).hexdigest()
    FACE = find_typeface(TITLE + "".join(s[0].get("title", "") + s[0].get("subtitle", "") for s in SCENES))
    STARS = np.random.default_rng(STORY.get("seed", 7)).random((90, 3))
    LAYER = skia.Surface(W, H)


def background(canvas, spec, local, story_time, scene_duration):
    palette = PALETTES[spec["preset"]]
    accent = spec.get("accent", palette["accent"])
    progress = story_time / DUR
    camera = spec.get("camera", "wide")
    zoom = {"wide": 1.0, "drift": 1.035, "close": 1.13}[camera] + 0.02 * smooth(local / scene_duration)
    canvas.save()
    canvas.translate(W * 0.5, H * 0.5)
    canvas.scale(zoom, zoom)
    canvas.translate(-W * 0.5 + (math.sin(local * 0.15) * W * 0.008 if camera == "drift" else 0), -H * 0.5)
    shader = skia.GradientShader.MakeLinear([skia.Point(0, 0), skia.Point(0, H)],
                                          [color(c) for c in palette["sky"]])
    canvas.drawRect(skia.Rect.MakeWH(W, H), skia.Paint(Shader=shader))
    scale = min(W, H) / 1080
    if spec["preset"] not in ("sunset", "ocean", "ink"):
        for index, (x, y, size) in enumerate(STARS):
            alpha = 0.25 + 0.35 * (0.5 + 0.5 * math.sin(story_time * 0.5 + index))
            canvas.drawCircle(x * W, y * H * 0.57, (0.7 + size * 1.3) * scale, paint("#dfebf4", alpha))
    if spec["preset"] == "aurora":
        for band, hue in enumerate(("#68d9b2", "#7ee9c5", "#779cda", "#ae91d4")):
            path = skia.Path()
            def ribbon_y(x):
                return H * (0.23 + band * 0.045 + 0.06 * math.sin(x * 4.8 + story_time * 0.17 + band * 0.8))
            for j in range(81):
                x = j / 80
                (path.moveTo if j == 0 else path.lineTo)(x * W, ribbon_y(x))
            for j in range(80, -1, -1):
                x = j / 80
                path.lineTo(x * W, ribbon_y(x) + H * (0.13 + 0.05 * math.sin(x * 6 + band)))
            path.close()
            ribbon = skia.GradientShader.MakeLinear([skia.Point(0, H * 0.15), skia.Point(0, H * 0.57)],
                                                    [color(hue, 0), color(hue, 0.32), color(hue, 0)])
            canvas.drawPath(path, skia.Paint(Shader=ribbon, AntiAlias=True))
        glow(canvas, W * 0.64, H * 0.43, H * 0.3, accent, 0.11)
    elif spec["preset"] == "cosmos":
        x, y, radius = W * 0.65, H * 0.56, min(W, H) * 0.19
        glow(canvas, x, y, radius * 2.2, accent, 0.18)
        ring = paint("#c0acd7", 0.45)
        ring.setStyle(skia.Paint.kStroke_Style)
        ring.setStrokeWidth(radius * 0.08)
        canvas.save()
        canvas.translate(x, y)
        canvas.rotate(-22)
        canvas.drawOval(skia.Rect.MakeLTRB(-radius * 1.7, -radius * 0.38, radius * 1.7, radius * 0.38), ring)
        planet = skia.GradientShader.MakeLinear([skia.Point(-radius, -radius), skia.Point(radius, radius)],
                                                [color("#cab5d9"), color("#6d658f"), color("#3c3a62")])
        canvas.drawCircle(0, 0, radius, skia.Paint(Shader=planet, AntiAlias=True))
        canvas.restore()
        angle = story_time * 0.15
        mx, my = x + math.cos(angle) * radius * 1.95, y + math.sin(angle) * radius * 0.7
        canvas.drawCircle(mx, my, radius * 0.16, paint("#e4d6ee"))
    elif spec["preset"] == "neon":
        glow(canvas, W * 0.65, H * 0.58, H * 0.4, "#e076ba", 0.3)
    elif spec["preset"] == "ember":
        glow(canvas, W * 0.64, H * 0.52, H * 0.36, accent, 0.2)
    else:
        x = W * 0.64
        y = H * (0.42 + progress * 0.18 if spec["preset"] == "sunset" else
                 0.7 - 0.37 * smooth(progress / 0.8) if spec["preset"] == "moonrise" else 0.43)
        glow(canvas, x, y, H * 0.28, accent, 0.35)
        canvas.drawCircle(x, y, H * 0.067, paint(accent, 0.98))
        if spec["preset"] == "moonrise":
            canvas.drawCircle(x - H * 0.018, y - H * 0.011, H * 0.047, paint("#fff8dc", 0.2))
    hills = palette["hills"] if spec["preset"] not in ("neon", "cosmos") else ()
    for layer, hue in enumerate(hills):
        path = skia.Path()
        path.moveTo(0, H)
        for j in range(101):
            x = j / 100
            y = H * (0.67 + layer * 0.095 - 0.075 * math.sin(x * (6 + layer * 2) + layer * 1.6
                                                                             + story_time * 0.025))
            path.lineTo(x * W, y)
        path.lineTo(W, H)
        path.close()
        canvas.drawPath(path, paint(hue))
    if spec["preset"] == "neon":
        for i in range(30):
            x = i / 30 * W
            width = W / 30 * 0.85
            top = H * (0.34 + STARS[i, 2] * 0.28)
            canvas.drawRect(skia.Rect.MakeLTRB(x, top, x + width, H * 0.8), paint(("#19203a", "#241b3c")[i % 2]))
            for row in range(12):
                for column in range(3):
                    if (i * 7 + row * 3 + column) % 5 == 0:
                        continue
                    left = x + width * (0.12 + column * 0.28)
                    y = top + H * 0.012 + row * H * 0.029
                    if y > H * 0.77:
                        break
                    hue = ("#e98ac8", "#89dde3")[(i + row) % 2]
                    alpha = 0.3 + 0.25 * math.sin(story_time * 0.3 + i + row) ** 2
                    canvas.drawRect(skia.Rect.MakeXYWH(left, y, width * 0.12, H * 0.011), paint(hue, alpha))
    if spec["preset"] in ("sunset", "aurora", "ocean", "neon"):
        water_top = H * (0.72 if spec["preset"] in ("sunset", "ocean") else 0.81)
        canvas.drawRect(skia.Rect.MakeLTRB(0, water_top, W, H), paint(palette["water"]))
        for j in range(35):
            y = water_top + (H - water_top) * (j / 35) ** 1.35
            x = W * (0.64 + 0.027 * math.sin(j * 1.7 + story_time * 0.7))
            half = W * (0.013 + j * 0.004) * (0.75 + 0.25 * math.sin(j + story_time))
            stroke = paint(accent, 0.10 + 0.07 * math.sin(j * 0.9 + story_time * 0.4) ** 2)
            stroke.setStrokeWidth(max(1, H * 0.0018))
            canvas.drawLine(x - half, y, x + half, y, stroke)
        if spec["preset"] == "ocean":
            for band in range(5):
                path = skia.Path()
                for j in range(101):
                    x = j / 100
                    y = H * (0.77 + band * 0.05 + 0.018 * math.sin(x * 13 - story_time * 0.8 + band))
                    (path.moveTo if j == 0 else path.lineTo)(x * W, y)
                stroke = paint("#d4f0e2", 0.23)
                stroke.setStyle(skia.Paint.kStroke_Style)
                stroke.setStrokeWidth(H * 0.004)
                canvas.drawPath(path, stroke)
    if spec["preset"] in ("aurora", "ember"):
            forest_base = H * (0.84 if spec["preset"] == "aurora" else 0.96)
            for x, y, height in STARS[:40]:
                x *= W
                base = forest_base + H * y * 0.025
                tall = H * (0.045 + height * (0.07 if spec["preset"] == "aurora" else 0.28))
                path = skia.Path()
                path.moveTo(x, base - tall)
                path.lineTo(x - tall * 0.24, base)
                path.lineTo(x + tall * 0.24, base)
                path.close()
                canvas.drawPath(path, paint("#091f2d"))
    if spec["preset"] == "ember":
        for i, (x, y, size) in enumerate(STARS[:35]):
            x = (x + 0.009 * math.sin(story_time * 0.6 + i)) * W
            y = (0.46 + y * 0.38 + 0.012 * math.cos(story_time * 0.5 + i)) * H
            alpha = 0.18 + 0.6 * math.sin(story_time * 0.8 + i) ** 2
            glow(canvas, x, y, (8 + size * 9) * scale, accent, alpha * 0.3)
            canvas.drawCircle(x, y, (0.8 + size * 1.4) * scale, paint(accent, alpha))
    if spec["preset"] == "ink":
        for i in range(7):
            x = (0.2 + i * 0.027 + story_time * 0.003) * W
            y = (0.43 + math.sin(i * 0.7) * 0.022) * H
            wing = H * 0.008
            stroke = paint("#405550", 0.65)
            stroke.setStrokeWidth(max(1, H * 0.001))
            canvas.drawLine(x - wing, y - wing * 0.4, x, y, stroke)
            canvas.drawLine(x, y, x + wing, y - wing * 0.5, stroke)
    if spec["preset"] == "ocean":
        for i in range(4):
            x = ((i * 0.29 + story_time * 0.004) % 1.3 - 0.1) * W
            y = H * (0.33 + 0.08 * (i % 2))
            glow(canvas, x, y, H * 0.13, "#e7f4e7", 0.35)
    canvas.restore()
    vignette = skia.GradientShader.MakeRadial(skia.Point(W * 0.5, H * 0.45), max(W, H) * 0.7,
                                             [color("#020b16", 0), color("#020b16", 0.5)])
    canvas.drawRect(skia.Rect.MakeWH(W, H), skia.Paint(Shader=vignette))


@lru_cache(maxsize=256)
def text_lines(text, initial_size, max_lines):
    size = initial_size
    while size >= 6:
        font = skia.Font(FACE, size)
        lines = []
        for paragraph in text.splitlines():
            line = ""
            for char in paragraph:
                if line and font.measureText(line + char) > W * 0.82:
                    split = line.rfind(" ")
                    if split > len(line) // 2:
                        lines.append(line[:split].strip())
                        line = line[split + 1:] + char
                    else:
                        lines.append(line.strip())
                        line = char
                else:
                    line += char
            if line:
                lines.append(line.strip())
        if len(lines) <= max_lines:
            return [(skia.TextBlob.MakeFromText(s, font), font.measureText(s)) for s in lines], size
        size *= 0.9
    raise ValueError("A title or caption is too long to fit; shorten it in scenes.json")


def captions(canvas, spec, local, scene_duration):
    fade = min(0.55, scene_duration * 0.25)
    alpha = smooth(local / fade) * smooth((scene_duration - local) / fade)
    y = H * 0.23
    for field, size, limit, hue in (("title", min(W * 0.058, H * 0.072), 3,
                                     "#253b37" if spec["preset"] == "ink" else "#f4ece0"),
                                    ("subtitle", min(W * 0.023, H * 0.032), 4,
                                     spec.get("accent", PALETTES[spec["preset"]]["accent"]))):
        value = spec.get(field, "")
        if not value:
            continue
        lines, actual = text_lines(value, size, limit)
        for blob, width in lines:
            canvas.drawTextBlob(blob, (W - width) / 2, y + actual * 0.035, paint("#0a1521", alpha * 0.65))
            canvas.drawTextBlob(blob, (W - width) / 2, y, paint(hue, alpha))
            y += actual * 1.28
        y += H * 0.025


def draw_frame(canvas, frame):
    """Draw one frame. All animation and scene boundaries use the same film clock."""
    index = next(i for i, (_, start, end) in enumerate(SCENES) if start <= frame < end)
    spec, start, end = SCENES[index]
    local, story_time, scene_duration = (frame - start) / FPS, frame / FPS, (end - start) / FPS
    background(canvas, spec, local, story_time, scene_duration)
    dissolve = min(0.35, scene_duration * 0.2)
    if index and local < dissolve:
        previous, prev_start, prev_end = SCENES[index - 1]
        background(LAYER.getCanvas(), previous, (frame - prev_start) / FPS, story_time, (prev_end - prev_start) / FPS)
        overlay = skia.Paint()
        overlay.setAlphaf(1 - smooth(local / dissolve))
        canvas.drawImage(LAYER.makeImageSnapshot(), 0, 0, paint=overlay)
    captions(canvas, spec, local, scene_duration)
    fade = 1 - smooth(story_time / 0.3) * smooth((DUR - story_time) / 0.5)
    canvas.drawRect(skia.Rect.MakeWH(W, H), paint("#050c17", fade))


def cmd_plan():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = [{"name": spec.get("name", f"Scene {i + 1}"), "preset": spec["preset"],
             "start_s": start / FPS, "end_s": end / FPS} for i, (spec, start, end) in enumerate(SCENES)]
    (OUT / "plan.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(f"{TITLE} · {DUR:g}s · {len(SCENES)} scenes · {W}×{H} · {FPS} fps", flush=True)


def cmd_stills():
    OUT.mkdir(parents=True, exist_ok=True)
    surface = skia.Surface(W, H)
    tiles = []
    for spec, start, end in SCENES:
        draw_frame(surface.getCanvas(), (start + end) // 2)
        pixels = surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)
        image = Image.fromarray(pixels).convert("RGB")
        if not tiles:
            FINAL.parent.mkdir(parents=True, exist_ok=True)
            image.save(FINAL.with_suffix(".jpg"), quality=92)
        image.thumbnail((480, 480))
        tiles.append(image)
    cols = min(3, len(tiles))
    tw, th = tiles[0].size
    contact = Image.new("RGB", (cols * tw, math.ceil(len(tiles) / cols) * (th + 30)), "#101c2c")
    draw = ImageDraw.Draw(contact)
    for i, image in enumerate(tiles):
        x, y = i % cols * tw, i // cols * (th + 30)
        contact.paste(image, (x, y))
        draw.text((x + 12, y + th + 8), f"Scene {i + 1} / {SCENES[i][0]['preset']}", fill="#c7dddf")
    contact.save(OUT / "storyboard.jpg", quality=90)
    print(f"Storyboard: {OUT / 'storyboard.jpg'}", flush=True)


def marker(stage):
    return OUT / f"{stage}.json"


def cmd_render():
    OUT.mkdir(parents=True, exist_ok=True)
    surface = skia.Surface(W, H)
    temporary = PICTURE.with_name("picture.partial.mp4")
    quality = starters.QUALITIES.get(OPTIONS.quality, {})
    encoder = media.encoder(str(temporary), W, H, FPS,
                            crf=int(quality.get("crf", settings.get("video", "crf", 16))),
                            preset=quality.get("preset", settings.get("video", "preset", "medium")), tune="animation")
    begin = time.monotonic()
    try:
        for frame in range(N_FRAMES):
            draw_frame(surface.getCanvas(), frame)
            encoder.stdin.write(surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType).tobytes())
            if (frame + 1) % max(1, N_FRAMES // 4) == 0:
                print(f"Picture {100 * (frame + 1) // N_FRAMES}% · {time.monotonic() - begin:.1f}s", flush=True)
        encoder.stdin.close()
        if encoder.wait() != 0:
            raise ValueError("FFmpeg could not encode the picture; check the message above")
        temporary.replace(PICTURE)
        marker("picture").write_text(json.dumps({"signature": KEY}), encoding="utf-8")
    finally:
        if encoder.poll() is None:
            encoder.terminate()
            encoder.wait()
        if encoder.stdin and not encoder.stdin.closed:
            encoder.stdin.close()
        temporary.unlink(missing_ok=True)


def score():
    """A stereo pad and scene-timed bells, synthesized locally with the shared DSP toolkit."""
    n = dsp.n_of(DUR)
    t = dsp.t_axis(n)
    root = PALETTES[SCENES[0][0]["preset"]]["root"]
    drone = sum(dsp.osc_sine(root * ratio, n) * amplitude for ratio, amplitude in ((1, 0.5), (1.5, 0.3), (2, 0.2)))
    drone *= dsp.env_points([(0, 0), (min(0.5, DUR * 0.2), 0.35), (DUR - min(0.8, DUR * 0.25), 0.35),
                             (DUR, 0)], n)
    drone *= 1 + 0.12 * np.sin(2 * np.pi * 0.25 * t)
    mix = dsp.pan_mono(drone * 0.6, -0.15)
    for i, (spec, start, end) in enumerate(SCENES):
        at = dsp.n_of(start / FPS + min(0.7, (end - start) / FPS * 0.2))
        m = min(dsp.n_of(3.5), n - at)
        note = PALETTES[spec["preset"]]["root"] * (4, 6, 5)[i % 3]
        bell = dsp.additive(note, m, [(1, 1.0, 3.0), (2.76, 0.35, 1.6), (5.4, 0.12, 0.8)])
        bell *= dsp.env_decay(m, 3.0)
        mix[:, at:at + m] += dsp.pan_mono(dsp.fade(bell, 0.006, 0.2) * 0.4, (-0.25, 0.2, 0)[i % 3])
    mix += 0.3 * dsp.convolve_reverb(mix, "hall")
    mix = dsp.fade(dsp.normalize(mix, 0.78), 0.03, min(0.8, DUR * 0.25))
    limited = dsp.limiter(mix, float(settings.get("audio", "true_peak_db", -1.0)))
    return limited[0] if isinstance(limited, tuple) else limited


def cmd_audio():
    OUT.mkdir(parents=True, exist_ok=True)
    temporary = SOUND.with_name("sound.partial.wav")
    wavfile.write(temporary, dsp.SR, (np.clip(score().T, -1, 1) * 32767).astype(np.int16))
    temporary.replace(SOUND)
    marker("sound").write_text(json.dumps({"signature": KEY}), encoding="utf-8")
    print(f"Sound: {SOUND}", flush=True)


def cmd_assemble():
    for stage, path in (("picture", PICTURE), ("sound", SOUND)):
        stamp = marker(stage)
        if not path.is_file() or not stamp.is_file() or json.loads(stamp.read_text())["signature"] != KEY:
            raise ValueError(f"The {stage} is missing or was made with different settings. "
                             "Run all, or rerun render and audio with the same options.")
    temporary = FINAL.with_name(FINAL.stem + ".partial.mp4")
    try:
        media.mux(str(PICTURE), str(SOUND), str(temporary), metadata={"title": TITLE})
        temporary.replace(FINAL)
    finally:
        temporary.unlink(missing_ok=True)
    marker("master").write_text(json.dumps({"signature": KEY}), encoding="utf-8")


def cmd_qc():
    if not FINAL.is_file() or not marker("master").is_file():
        raise ValueError("No finished film found. Run all first.")
    if json.loads(marker("master").read_text())["signature"] != KEY:
        raise ValueError("The finished film uses different settings. Run all with the same options.")
    info = media.probe(str(FINAL))
    expected = {"width": W, "height": H, "frames": N_FRAMES, "audio_rate": dsp.SR, "fps": FPS}
    if any(info.get(key) != val for key, val in expected.items()) or abs(info["duration"] - DUR) > 0.05 + 1 / FPS:
        raise ValueError(f"Film verification failed: {info}")
    subprocess.run([media.ffmpeg(), "-v", "error", "-xerror", "-i", str(FINAL), "-f", "null", "-"], check=True)
    (OUT / "qc.json").write_text(json.dumps({"passed": True, **info}, indent=2) + "\n", encoding="utf-8")
    print(f"Verified: {FINAL} ({info['duration']:.2f}s, picture + stereo sound)", flush=True)


def open_film():
    if sys.platform == "darwin":
        subprocess.run(["open", str(FINAL)], check=True)
    elif sys.platform == "win32":
        os.startfile(str(FINAL))
    else:
        import webbrowser
        webbrowser.open(FINAL.as_uri())


def main():
    global OPTIONS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", nargs="?", default="all",
                        choices=("plan", "stills", "render", "audio", "assemble", "qc", "all"))
    parser.add_argument("--quality", choices=starters.QUALITIES, help="preview writes a separate 360p MP4")
    parser.add_argument("--format", choices=starters.FORMATS)
    parser.add_argument("--duration", type=float, help="Scale the whole timeline to this number of seconds")
    parser.add_argument("--fps", type=int)
    parser.add_argument("--open", action="store_true", help="Open the finished film in the default player")
    OPTIONS = parser.parse_args()
    try:
        if OPTIONS.open and OPTIONS.step not in ("all", "assemble", "qc"):
            raise ValueError("--open is available with all, assemble or qc")
        configure(OPTIONS)
        if OPTIONS.step in ("render", "assemble", "qc", "all"):
            missing = [name for name in ("ffmpeg", "ffprobe") if not diagnostics.tool_available(settings.tool(name))]
            if missing:
                raise ValueError(f"Missing {', '.join(missing)}. {diagnostics.ffmpeg_help()}")
        stages = {"plan": cmd_plan, "stills": cmd_stills, "render": cmd_render, "audio": cmd_audio,
                  "assemble": cmd_assemble, "qc": cmd_qc}
        selected = list(stages.values()) if OPTIONS.step == "all" else [stages[OPTIONS.step]]
        for function in selected:
            function()
        if OPTIONS.open:
            open_film()
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"Film could not be completed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
