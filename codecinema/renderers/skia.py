"""Skia artwork and common title compositing, owned by the framework."""

from functools import lru_cache
import math
import os
import numpy as np
import skia
from codecinema import settings
from codecinema.renderers.palettes import PALETTES


def smooth(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def color(hex_value, alpha=1.0):
    return skia.Color4f(*(int(hex_value[i : i + 2], 16) / 255 for i in (1, 3, 5)), alpha)


def paint(hex_value, alpha=1.0):
    return skia.Paint(AntiAlias=True, Color4f=color(hex_value, alpha))


def glow(canvas, x, y, radius, hex_value, alpha):
    shader = skia.GradientShader.MakeRadial(skia.Point(x, y), radius, [color(hex_value, alpha), color(hex_value, 0)])
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
        for family in (
            "Arial",
            "DejaVu Sans",
            "Liberation Sans",
            "Noto Sans",
            "PingFang SC",
            "Noto Sans CJK SC",
            "Microsoft YaHei",
            "WenQuanYi Zen Hei",
        ):
            candidates.append(manager.matchFamilyStyle(family, skia.FontStyle()))
    for face in candidates:
        if face and all(skia.Font(face, 20).textToGlyphs(chars)):
            return face
    raise ValueError(
        "The title or captions contain unsupported characters. Install a suitable font "
        "(e.g. Noto Sans CJK for Chinese) or set [fonts] ui in film.local.toml."
    )


class Renderer:
    """Yield packed RGBA frames, in the exact order requested by the pipeline."""

    version = "1"

    def __init__(self):
        self.context = None

    def prepare(self, context):
        if self.context is context:
            return
        self.context = context
        self.text_lines.cache_clear()
        self.face = find_typeface(
            context.title + "".join(s[0].get("title", "") + s[0].get("subtitle", "") for s in context.scenes)
        )
        self.stars = np.random.default_rng(context.story.get("seed", 7)).random((90, 3))
        self.layer = skia.Surface(context.width, context.height)

    def render(self, context, frames):
        self.prepare(context)
        surface = skia.Surface(context.width, context.height)
        for frame in frames:
            self.draw_frame(surface.getCanvas(), frame)
            yield surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType).tobytes()

    def composite(self, context, frame, image):
        """Apply the same captions and head/tail fades to a rendered 3D plate."""
        self.prepare(context)
        surface = skia.Surface(context.width, context.height)
        canvas = surface.getCanvas()
        canvas.drawImage(
            skia.Image.fromarray(np.asarray(image.convert("RGBA")), colorType=skia.kRGBA_8888_ColorType), 0, 0
        )
        spec, start, end = next(s for s in context.scenes if s[1] <= frame < s[2])
        self.captions(canvas, spec, (frame - start) / context.fps, (end - start) / context.fps)
        time = frame / context.fps
        fade = 1 - smooth(time / 0.3) * smooth((context.duration - time) / 0.5)
        canvas.drawRect(skia.Rect.MakeWH(context.width, context.height), paint("#050c17", fade))
        return surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType).tobytes()

    def background(self, canvas, spec, local, story_time, scene_duration):
        palette = PALETTES[spec["preset"]]
        accent = spec.get("accent", palette["accent"])
        progress = story_time / self.context.duration
        camera = spec.get("camera", "wide")
        zoom = {"wide": 1.0, "drift": 1.035, "close": 1.13}[camera] + 0.02 * smooth(local / scene_duration)
        canvas.save()
        canvas.translate(self.context.width * 0.5, self.context.height * 0.5)
        canvas.scale(zoom, zoom)
        canvas.translate(
            -self.context.width * 0.5
            + (math.sin(local * 0.15) * self.context.width * 0.008 if camera == "drift" else 0),
            -self.context.height * 0.5,
        )
        shader = skia.GradientShader.MakeLinear(
            [skia.Point(0, 0), skia.Point(0, self.context.height)], [color(c) for c in palette["sky"]]
        )
        canvas.drawRect(skia.Rect.MakeWH(self.context.width, self.context.height), skia.Paint(Shader=shader))
        scale = min(self.context.width, self.context.height) / 1080
        if spec["preset"] not in ("sunset", "ocean", "ink"):
            for index, (x, y, size) in enumerate(self.stars):
                alpha = 0.25 + 0.35 * (0.5 + 0.5 * math.sin(story_time * 0.5 + index))
                canvas.drawCircle(
                    x * self.context.width,
                    y * self.context.height * 0.57,
                    (0.7 + size * 1.3) * scale,
                    paint("#dfebf4", alpha),
                )
        if spec["preset"] == "aurora":
            for band, hue in enumerate(("#68d9b2", "#7ee9c5", "#779cda", "#ae91d4")):
                path = skia.Path()

                def ribbon_y(x):
                    return self.context.height * (
                        0.23 + band * 0.045 + 0.06 * math.sin(x * 4.8 + story_time * 0.17 + band * 0.8)
                    )

                for j in range(81):
                    x = j / 80
                    (path.moveTo if j == 0 else path.lineTo)(x * self.context.width, ribbon_y(x))
                for j in range(80, -1, -1):
                    x = j / 80
                    path.lineTo(
                        x * self.context.width,
                        ribbon_y(x) + self.context.height * (0.13 + 0.05 * math.sin(x * 6 + band)),
                    )
                path.close()
                ribbon = skia.GradientShader.MakeLinear(
                    [skia.Point(0, self.context.height * 0.15), skia.Point(0, self.context.height * 0.57)],
                    [color(hue, 0), color(hue, 0.32), color(hue, 0)],
                )
                canvas.drawPath(path, skia.Paint(Shader=ribbon, AntiAlias=True))
            glow(canvas, self.context.width * 0.64, self.context.height * 0.43, self.context.height * 0.3, accent, 0.11)
        elif spec["preset"] == "cosmos":
            x, y, radius = (
                self.context.width * 0.65,
                self.context.height * 0.56,
                min(self.context.width, self.context.height) * 0.19,
            )
            glow(canvas, x, y, radius * 2.2, accent, 0.18)
            ring = paint("#c0acd7", 0.45)
            ring.setStyle(skia.Paint.kStroke_Style)
            ring.setStrokeWidth(radius * 0.08)
            canvas.save()
            canvas.translate(x, y)
            canvas.rotate(-22)
            canvas.drawOval(skia.Rect.MakeLTRB(-radius * 1.7, -radius * 0.38, radius * 1.7, radius * 0.38), ring)
            planet = skia.GradientShader.MakeLinear(
                [skia.Point(-radius, -radius), skia.Point(radius, radius)],
                [color("#cab5d9"), color("#6d658f"), color("#3c3a62")],
            )
            canvas.drawCircle(0, 0, radius, skia.Paint(Shader=planet, AntiAlias=True))
            canvas.restore()
            angle = story_time * 0.15
            mx, my = x + math.cos(angle) * radius * 1.95, y + math.sin(angle) * radius * 0.7
            canvas.drawCircle(mx, my, radius * 0.16, paint("#e4d6ee"))
        elif spec["preset"] == "neon":
            glow(
                canvas, self.context.width * 0.65, self.context.height * 0.58, self.context.height * 0.4, "#e076ba", 0.3
            )
        elif spec["preset"] == "ember":
            glow(canvas, self.context.width * 0.64, self.context.height * 0.52, self.context.height * 0.36, accent, 0.2)
        else:
            x = self.context.width * 0.64
            y = self.context.height * (
                0.42 + progress * 0.18
                if spec["preset"] == "sunset"
                else 0.7 - 0.37 * smooth(progress / 0.8)
                if spec["preset"] == "moonrise"
                else 0.43
            )
            glow(canvas, x, y, self.context.height * 0.28, accent, 0.35)
            canvas.drawCircle(x, y, self.context.height * 0.067, paint(accent, 0.98))
            if spec["preset"] == "moonrise":
                canvas.drawCircle(
                    x - self.context.height * 0.018,
                    y - self.context.height * 0.011,
                    self.context.height * 0.047,
                    paint("#fff8dc", 0.2),
                )
        hills = palette["hills"] if spec["preset"] not in ("neon", "cosmos") else ()
        for layer, hue in enumerate(hills):
            path = skia.Path()
            path.moveTo(0, self.context.height)
            for j in range(101):
                x = j / 100
                y = self.context.height * (
                    0.67 + layer * 0.095 - 0.075 * math.sin(x * (6 + layer * 2) + layer * 1.6 + story_time * 0.025)
                )
                path.lineTo(x * self.context.width, y)
            path.lineTo(self.context.width, self.context.height)
            path.close()
            canvas.drawPath(path, paint(hue))
        if spec["preset"] == "neon":
            for i in range(30):
                x = i / 30 * self.context.width
                width = self.context.width / 30 * 0.85
                top = self.context.height * (0.34 + self.stars[i, 2] * 0.28)
                canvas.drawRect(
                    skia.Rect.MakeLTRB(x, top, x + width, self.context.height * 0.8),
                    paint(("#19203a", "#241b3c")[i % 2]),
                )
                for row in range(12):
                    for column in range(3):
                        if (i * 7 + row * 3 + column) % 5 == 0:
                            continue
                        left = x + width * (0.12 + column * 0.28)
                        y = top + self.context.height * 0.012 + row * self.context.height * 0.029
                        if y > self.context.height * 0.77:
                            break
                        hue = ("#e98ac8", "#89dde3")[(i + row) % 2]
                        alpha = 0.3 + 0.25 * math.sin(story_time * 0.3 + i + row) ** 2
                        canvas.drawRect(
                            skia.Rect.MakeXYWH(left, y, width * 0.12, self.context.height * 0.011), paint(hue, alpha)
                        )
        if spec["preset"] in ("sunset", "aurora", "ocean", "neon"):
            water_top = self.context.height * (0.72 if spec["preset"] in ("sunset", "ocean") else 0.81)
            canvas.drawRect(
                skia.Rect.MakeLTRB(0, water_top, self.context.width, self.context.height), paint(palette["water"])
            )
            for j in range(35):
                y = water_top + (self.context.height - water_top) * (j / 35) ** 1.35
                x = self.context.width * (0.64 + 0.027 * math.sin(j * 1.7 + story_time * 0.7))
                half = self.context.width * (0.013 + j * 0.004) * (0.75 + 0.25 * math.sin(j + story_time))
                stroke = paint(accent, 0.10 + 0.07 * math.sin(j * 0.9 + story_time * 0.4) ** 2)
                stroke.setStrokeWidth(max(1, self.context.height * 0.0018))
                canvas.drawLine(x - half, y, x + half, y, stroke)
            if spec["preset"] == "ocean":
                for band in range(5):
                    path = skia.Path()
                    for j in range(101):
                        x = j / 100
                        y = self.context.height * (
                            0.77 + band * 0.05 + 0.018 * math.sin(x * 13 - story_time * 0.8 + band)
                        )
                        (path.moveTo if j == 0 else path.lineTo)(x * self.context.width, y)
                    stroke = paint("#d4f0e2", 0.23)
                    stroke.setStyle(skia.Paint.kStroke_Style)
                    stroke.setStrokeWidth(self.context.height * 0.004)
                    canvas.drawPath(path, stroke)
        if spec["preset"] in ("aurora", "ember"):
            forest_base = self.context.height * (0.84 if spec["preset"] == "aurora" else 0.96)
            for x, y, height in self.stars[:40]:
                x *= self.context.width
                base = forest_base + self.context.height * y * 0.025
                tall = self.context.height * (0.045 + height * (0.07 if spec["preset"] == "aurora" else 0.28))
                path = skia.Path()
                path.moveTo(x, base - tall)
                path.lineTo(x - tall * 0.24, base)
                path.lineTo(x + tall * 0.24, base)
                path.close()
                canvas.drawPath(path, paint("#091f2d"))
        if spec["preset"] == "ember":
            for i, (x, y, size) in enumerate(self.stars[:35]):
                x = (x + 0.009 * math.sin(story_time * 0.6 + i)) * self.context.width
                y = (0.46 + y * 0.38 + 0.012 * math.cos(story_time * 0.5 + i)) * self.context.height
                alpha = 0.18 + 0.6 * math.sin(story_time * 0.8 + i) ** 2
                glow(canvas, x, y, (8 + size * 9) * scale, accent, alpha * 0.3)
                canvas.drawCircle(x, y, (0.8 + size * 1.4) * scale, paint(accent, alpha))
        if spec["preset"] == "ink":
            for i in range(7):
                x = (0.2 + i * 0.027 + story_time * 0.003) * self.context.width
                y = (0.43 + math.sin(i * 0.7) * 0.022) * self.context.height
                wing = self.context.height * 0.008
                stroke = paint("#405550", 0.65)
                stroke.setStrokeWidth(max(1, self.context.height * 0.001))
                canvas.drawLine(x - wing, y - wing * 0.4, x, y, stroke)
                canvas.drawLine(x, y, x + wing, y - wing * 0.5, stroke)
        if spec["preset"] == "ocean":
            for i in range(4):
                x = ((i * 0.29 + story_time * 0.004) % 1.3 - 0.1) * self.context.width
                y = self.context.height * (0.33 + 0.08 * (i % 2))
                glow(canvas, x, y, self.context.height * 0.13, "#e7f4e7", 0.35)
        canvas.restore()
        vignette = skia.GradientShader.MakeRadial(
            skia.Point(self.context.width * 0.5, self.context.height * 0.45),
            max(self.context.width, self.context.height) * 0.7,
            [color("#020b16", 0), color("#020b16", 0.5)],
        )
        canvas.drawRect(skia.Rect.MakeWH(self.context.width, self.context.height), skia.Paint(Shader=vignette))

    @lru_cache(maxsize=256)
    def text_lines(self, text, initial_size, max_lines):
        size = initial_size
        while size >= 6:
            font = skia.Font(self.face, size)
            lines = []
            for paragraph in text.splitlines():
                line = ""
                for char in paragraph:
                    if line and font.measureText(line + char) > self.context.width * 0.82:
                        split = line.rfind(" ")
                        if split > len(line) // 2:
                            lines.append(line[:split].strip())
                            line = line[split + 1 :] + char
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

    def captions(self, canvas, spec, local, scene_duration):
        fade = min(0.55, scene_duration * 0.25)
        alpha = smooth(local / fade) * smooth((scene_duration - local) / fade)
        y = self.context.height * 0.23
        for field, size, limit, hue in (
            (
                "title",
                min(self.context.width * 0.058, self.context.height * 0.072),
                3,
                "#253b37" if spec["preset"] == "ink" else "#f4ece0",
            ),
            (
                "subtitle",
                min(self.context.width * 0.023, self.context.height * 0.032),
                4,
                spec.get("accent", PALETTES[spec["preset"]]["accent"]),
            ),
        ):
            value = spec.get(field, "")
            if not value:
                continue
            lines, actual = self.text_lines(value, size, limit)
            for blob, width in lines:
                canvas.drawTextBlob(
                    blob, (self.context.width - width) / 2, y + actual * 0.035, paint("#0a1521", alpha * 0.65)
                )
                canvas.drawTextBlob(blob, (self.context.width - width) / 2, y, paint(hue, alpha))
                y += actual * 1.28
            y += self.context.height * 0.025

    def draw_frame(self, canvas, frame):
        """Draw one frame. All animation and scene boundaries use the same film clock."""
        index = next(i for i, (_, start, end) in enumerate(self.context.scenes) if start <= frame < end)
        spec, start, end = self.context.scenes[index]
        local, story_time, scene_duration = (
            (frame - start) / self.context.fps,
            frame / self.context.fps,
            (end - start) / self.context.fps,
        )
        self.background(canvas, spec, local, story_time, scene_duration)
        dissolve = min(0.35, scene_duration * 0.2)
        if index and local < dissolve:
            previous, prev_start, prev_end = self.context.scenes[index - 1]
            self.background(
                self.layer.getCanvas(),
                previous,
                (frame - prev_start) / self.context.fps,
                story_time,
                (prev_end - prev_start) / self.context.fps,
            )
            overlay = skia.Paint()
            overlay.setAlphaf(1 - smooth(local / dissolve))
            canvas.drawImage(self.layer.makeImageSnapshot(), 0, 0, paint=overlay)
        self.captions(canvas, spec, local, scene_duration)
        fade = 1 - smooth(story_time / 0.3) * smooth((self.context.duration - story_time) / 0.5)
        canvas.drawRect(skia.Rect.MakeWH(self.context.width, self.context.height), paint("#050c17", fade))
