"""Drawing with fonts: the example films' titles stay identical, mixed scripts share a baseline, skia captions, the
specimen sheet and the `library fonts` command. No network: downloads are off."""
import json
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from codecinema import cli, typography
from codecinema.cartoon import finish
from codecinema.renderers import skia as skia_renderer
from codecinema.typography import draw as typeset
from codecinema.typography import index, shaping
from codecinema.workspace import settings
from codecinema.workspace.paths import resource_dir

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("CODECINEMA_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("CODECINEMA_FONTS_DOWNLOAD", "off")
    monkeypatch.delenv("CODECINEMA_FONTS_MIRROR", raising=False)
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(urllib.error.URLError("off")))
    monkeypatch.setattr(index, "folders", lambda: [(resource_dir("fonts"), "bundled")])
    typography.clear()
    yield
    typography.clear()


def legacy_title_card(title, width, height):
    """The title card as drawn before codecinema.typography (one font per text, ImageDraw.multiline_text)."""
    def font_for(text, size, weight=600):
        cjk = any("\u3000" <= ch <= "鿿" or "＀" <= ch <= "￯" for ch in text)
        font = ImageFont.truetype(settings.font("display_cjk" if cjk else "display") or settings.font("ui"), size)
        try:
            font.set_variation_by_axes([weight])
        except (OSError, ValueError, AttributeError):
            pass
        return font

    def draw_text(draw, xy, text, font, fill):
        draw.multiline_text(xy, text, font=font, fill=fill, anchor="mm", align="center", spacing=8)

    scale = 2
    W, H = width * scale, height * scale
    style, text, sub = title.get("style", "main"), title.get("text", ""), title.get("sub", "")
    image, shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0)), Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    if style in ("card", "end"):
        image = Image.alpha_composite(image, Image.new("RGBA", (W, H), (8, 10, 22, int(255 * title.get("dim", 0.55)))))
    if style == "lower":
        size, pos, sub_size = int(H * 0.05), (W * 0.5, H * 0.84), int(H * 0.03)
    elif style == "main":
        size, pos, sub_size = int(H * title.get("size", 0.13)), (W * 0.5, H * title.get("y", 0.44)), int(H * 0.045)
    else:
        size, pos, sub_size = int(H * 0.1), (W * 0.5, H * 0.42), int(H * 0.04)
    font = font_for(text, size, 650)
    for dx, dy in ((0, 6), (0, 3)):
        draw_text(sdraw, (pos[0] + dx, pos[1] + dy * scale), text, font, (20, 16, 40, 200))
    if sub:
        sfont = font_for(sub, sub_size, 500)
        sub_pos = (pos[0], pos[1] + size * 0.62 + sub_size * 0.9)
        draw_text(sdraw, (sub_pos[0], sub_pos[1] + 4 * scale), sub, sfont, (20, 16, 40, 190))
    image = Image.alpha_composite(image, shadow.filter(ImageFilter.GaussianBlur(10 * scale)))
    draw = ImageDraw.Draw(image)
    draw_text(draw, pos, text, font, title.get("color", "#fffaf0"))
    if sub:
        draw_text(draw, sub_pos, sub, sfont, title.get("sub_color", "#f4e9d2"))
    lines = title.get("credits", [])
    if lines:
        cfont = font_for(" ".join(lines), int(H * 0.028), 450)
        y = pos[1] + size * 0.9 + (sub_size * 2.2 if sub else 0)
        for line in lines:
            draw_text(draw, (W * 0.5, y), line, cfont, "#e9e3d6")
            y += H * 0.045
    return image.resize((width, height), Image.LANCZOS)


def screenplay_titles(film):
    data = json.loads((ROOT / "films" / film / "screenplay.json").read_text(encoding="utf-8"))
    titles = [s["title"] for scene in data["scenes"] for s in scene.get("shots", []) if s.get("title")]
    return data, [{"text": t} if isinstance(t, str) else dict(t) for t in titles]


@pytest.mark.parametrize("film, family", [("pebble", "Fredoka"), ("nian", "ZCOOL KuaiLe")])
def test_example_film_titles_are_unchanged(film, family, tmp_path):
    data, titles = screenplay_titles(film)
    assert titles and "fonts" not in data
    for k, title in enumerate(titles):
        assert finish.lettering_for(title["text"], 100, 650, None, data.get("language")).primary.family == family
        path = finish.title_card(title, 480, 270, tmp_path / f"{film}{k}.png", fonts={}, language=data["language"])
        assert np.array_equal(np.asarray(Image.open(path)), np.asarray(legacy_title_card(title, 480, 270))), title


def test_titles_choose_fonts_from_the_card_the_screenplay_then_settings(monkeypatch):
    title = {"text": "The End", "font": "Lilita One"}
    assert finish.choose("credits", title, {"title": "Bangers", "credits": "Nunito"}) == "Lilita One"
    assert finish.choose("credits", {}, {"title": "Bangers", "credits": "Nunito"}) == "Nunito"
    assert finish.choose("subtitle", {}, {"title": "Bangers"}) == "Bangers"
    assert finish.choose("title", {}, {}) is None
    monkeypatch.setitem(settings.SETTINGS["fonts"], "title", "Caveat")
    assert finish.choose("subtitle", {}, {}) == "Caveat"


def test_screenplay_font_names_are_checked():
    script = {"fonts": {"title": "Lilta One", "credit": "Nunito"},
              "scenes": [{"shots": [{"title": {"text": "x", "font": ["Fredoka", "Noto Sans JQ"]}}]}]}
    problems = finish.check_fonts(script)
    assert len(problems) == 3
    assert "fonts.credit" in problems[0] and "Lilita One" in problems[1] and "Noto Sans JP" in problems[2]
    assert finish.check_fonts({"fonts": {"title": "Fredoka", "credits": "zcool-kuaile"}}) == []


def test_unknown_title_fonts_fail_as_screenplay_errors(tmp_path):
    from codecinema.cartoon.screenplay import ScreenplayError
    with pytest.raises(ScreenplayError, match="Did you mean: Lilita One"):
        finish.title_card({"text": "Pebble"}, 320, 180, tmp_path / "t.png", fonts={"title": "Lilta One"})


def test_mixed_script_runs_share_one_baseline():
    faces = typography.stack(["Fredoka"], role="title", text="Nian · 年", weight=650)
    assert [f.family for f in faces] == ["Fredoka", "ZCOOL KuaiLe"]
    letters = typeset.Lettering(faces, 96)
    mixed = Image.new("RGBA", (700, 220), (0, 0, 0, 0))
    typeset.text(mixed, (24, 150), "Nian · 年", letters, "#ffffff", anchor="ls", align="left")
    expected = Image.new("RGBA", (700, 220), (0, 0, 0, 0))
    draw = ImageDraw.Draw(expected)
    latin, han = letters.font(faces[0]), letters.font(faces[1])
    draw.text((24, 150), "Nian · ", font=latin, fill="#ffffff", anchor="ls")
    draw.text((24 + latin.getlength("Nian · "), 150), "年", font=han, fill="#ffffff", anchor="ls")
    assert np.array_equal(np.asarray(mixed), np.asarray(expected))
    alone = Image.new("RGBA", (700, 220), (0, 0, 0, 0))
    ImageDraw.Draw(alone).text((24, 150), "Nian · 年", font=latin, fill="#ffffff", anchor="ls")
    assert not np.array_equal(np.asarray(mixed), np.asarray(alone))         # Fredoka alone has no 年


def test_mixed_title_card_renders(tmp_path):
    title = {"text": "Nian · 年", "sub": "a New Year tale · 年的故事", "style": "main", "credits": ["CodeCinema · 年"]}
    path = finish.title_card(title, 480, 270, tmp_path / "mixed.png", fonts={"title": "Fredoka"}, language="Chinese")
    alpha = np.asarray(Image.open(path))[:, :, 3]
    assert alpha.max() == 255 and (alpha > 0).mean() > 0.01


@pytest.mark.skipif(not shaping.available(), reason="skia-python without text layout")
def test_right_to_left_lines_are_shaped():
    face = typography.find("Fredoka", 500)                  # Fredoka also draws Hebrew
    letters = typeset.Lettering([face], 64)
    assert letters.single("שלום") is None                  # complex text goes through the shaper
    image = Image.new("RGBA", (400, 120), (0, 0, 0, 0))
    typeset.text(image, (200, 60), "שלום", letters, "#ffffff")
    alpha = np.asarray(image)[:, :, 3]
    columns = np.nonzero(alpha.max(axis=0))[0]
    assert alpha.max() == 255 and abs((columns[0] + columns[-1]) / 2 - 200) < 8      # centred like other text


def story_context(title, scenes, width=640, height=360, fps=12):
    specs, start = [], 0
    for scene in scenes:
        frames = int(scene["duration_s"] * fps)
        specs.append((scene, start, start + frames))
        start += frames
    return SimpleNamespace(title=title, scenes=tuple(specs), story={"seed": 7, "scenes": scenes}, width=width,
                           height=height, fps=fps, duration=start / fps)


class LegacyCaptions(skia_renderer.Renderer):
    """Captions as drawn before codecinema.typography: one typeface, one TextBlob per line."""

    def prepare(self, context):
        fresh = self.context is not context
        super().prepare(context)
        if fresh:
            self.face = skia_renderer.find_typeface(context.title + "".join(
                s[0].get("title", "") + s[0].get("subtitle", "") for s in context.scenes))
            self.legacy = {}

    def legacy_lines(self, text, size, max_lines):
        import skia
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

    def captions(self, canvas, spec, local, scene_duration):
        smooth, paint = skia_renderer.smooth, skia_renderer.paint
        fade = min(0.55, scene_duration * 0.25)
        alpha = smooth(local / fade) * smooth((scene_duration - local) / fade)
        y = self.context.height * 0.23
        for field, size, limit, hue in (
                ("title", min(self.context.width * 0.058, self.context.height * 0.072), 3,
                 "#253b37" if spec["preset"] == "ink" else "#f4ece0"),
                ("subtitle", min(self.context.width * 0.023, self.context.height * 0.032), 4,
                 spec.get("accent", skia_renderer.PALETTES[spec["preset"]]["accent"]))):
            if not spec.get(field, ""):
                continue
            lines, actual = self.legacy_lines(spec[field], size, limit)
            for blob, width in lines:
                canvas.drawTextBlob(blob, (self.context.width - width) / 2, y + actual * 0.035,
                                    paint("#0a1521", alpha * 0.65))
                canvas.drawTextBlob(blob, (self.context.width - width) / 2, y, paint(hue, alpha))
                y += actual * 1.28
            y += self.context.height * 0.025


STORY = [{"preset": "moonrise", "duration_s": 2, "camera": "wide", "title": "My Film",
          "subtitle": "A little light in the quiet, and a much longer caption that has to wrap onto a second line."},
         {"preset": "ink", "duration_s": 2, "camera": "drift", "title": "", "subtitle": "Let the empty space breathe."}]


def test_story_captions_are_unchanged_by_default():
    context = story_context("My Film", STORY)
    frames = [6, 12, 30]
    new, old = skia_renderer.Renderer(), LegacyCaptions()
    assert list(new.render(context, frames)) == list(old.render(context, frames))
    assert new.letters["title"].typeface is not None                 # one system typeface, as before


def test_story_caption_fonts_come_from_settings(monkeypatch):
    monkeypatch.setitem(settings.SETTINGS["fonts"], "title", "Fredoka")
    context = story_context("Nian · 年", [{"preset": "sunset", "duration_s": 2, "title": "Nian · 年",
                                           "subtitle": "Every film begins with a single frame · 年"}])
    renderer = skia_renderer.Renderer()
    renderer.validate(context)
    frame = next(renderer.render(context, [12]))
    assert len(frame) == 640 * 360 * 4
    assert [f.family for f in renderer.letters["title"].faces] == ["Fredoka", "ZCOOL KuaiLe"]
    pieces, width = renderer.letters["title"].line("Nian · 年", 40)
    assert len(pieces) == 2 and pieces[1][1] > 0 and width > pieces[1][1]
    monkeypatch.setitem(settings.SETTINGS["fonts"], "subtitle", "Lilta One")
    with pytest.raises(ValueError, match="Lilita One"):
        renderer.validate(context)


@pytest.mark.skipif(not shaping.available(), reason="skia-python without text layout")
def test_story_captions_shape_complex_scripts(monkeypatch):
    monkeypatch.setitem(settings.SETTINGS["fonts"], "subtitle", "Fredoka")
    letters = skia_renderer.letters_for("", "שלום Pebble")["subtitle"]
    pieces, width = letters.line("שלום Pebble", 32)
    assert len(pieces) == 1 and isinstance(pieces[0][0], tuple) and width > 0


def test_specimen_sheet_offline(tmp_path):
    from codecinema.typography import sheet
    path = sheet.specimen(tmp_path / "fonts.png", ["fredoka", "zcool-kuaile", "lilita-one"])
    image = Image.open(path)
    assert image.size == (1800, sheet.MARGIN * 2 + 70 + sheet.HEADING * 2 + sheet.ROW * 3)


def test_library_fonts_command(capsys):
    assert cli.main(["library", "fonts"]) == 0
    out = capsys.readouterr().out
    assert "Latin (27)" in out and "Simplified Chinese (10)" in out and "Japanese (13)" in out
    assert "Fredoka" in out and "bundled" in out and "downloadable" in out and "73 families" in out
    assert cli.main(["library", "fonts", "--names", "zcool kuaile"]) == 0
    out = capsys.readouterr().out
    assert "OFL-ZCOOLKuaiLe.txt" in out and "status           bundled" in out
    assert cli.main(["library", "fonts", "--names", "Lilta One"]) == 1
    assert "Did you mean: Lilita One" in capsys.readouterr().err
    assert cli.main(["library", "fonts", "--download", "fredoka,zcool-kuaile"]) == 0
    assert "2 families: 2 already available" in capsys.readouterr().out
    assert cli.main(["library", "sounds", "--download", "ja"]) == 1


def test_check_reports_fonts(capsys):
    assert cli.app._check_fonts()
    out = capsys.readouterr().out
    assert "Fredoka, ZCOOL KuaiLe bundled" in out and "downloads off" in out
