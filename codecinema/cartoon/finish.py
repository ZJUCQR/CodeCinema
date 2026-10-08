"""Finishing: title cards, subtitles, color grades and transitions for the master.

Titles are painted once as transparent PNGs and laid over the picture by
FFmpeg with soft fades; grades (such as the warm, grainy "memory" look) and
fades between shots are FFmpeg filters enabled only during their shots, so the
rendered frames stay untouched and the finishing pass is quick to redo.

Title fonts, first match wins: the title's own "font", the screenplay's "fonts" table ({"title", "subtitle",
"credits"}; subtitle and credits default to title), the film's [fonts] title / subtitle / credits settings, then
the defaults (Fredoka for Latin text, ZCOOL KuaiLe for Chinese, catalog fonts for other writing systems).
A value is a family from `codecinema library fonts`, a font file, or a list of them; characters a font lacks
fall back per run, and Han-only text follows the screenplay's "language" (or a title's "lang").
"""
from __future__ import annotations

import functools
import json
from pathlib import Path

from PIL import Image, ImageFilter

from codecinema import typography
from codecinema.typography import draw as typeset
from codecinema.workspace import settings

KINDS = ("title", "subtitle", "credits")

GRADES = {
    # Warm sepia memory: 45 % toward sepia, vignette and moving grain.
    "memory": ["colorchannelmixer=rr=0.72:rg=0.35:rb=0.09:gr=0.16:gg=0.79:gb=0.08:br=0.12:bg=0.24:bb=0.56",
               "vignette=angle=PI/4.2", "noise=alls=6:allf=t"],
    "dream": ["gblur=sigma=1.2", "eq=saturation=1.15:brightness=0.03"],
    "cold": ["colorbalance=bs=0.06:bm=0.03:rs=-0.03"],
    "warm": ["colorbalance=rs=0.05:rm=0.03:bs=-0.04"],
    "night": ["eq=saturation=0.92"],
}


def _cjk(text):
    return any("\u3000" <= ch <= "鿿" or "＀" <= ch <= "￯" for ch in text)


@functools.lru_cache(maxsize=8)
def _screenplay(path, stamp):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data.get("fonts") or {}, data.get("language")


def film_fonts():
    """The active film's screenplay "fonts" table and "language" (({}, None) when it has none)."""
    path = Path(settings.ROOT) / "screenplay.json"
    try:
        return _screenplay(str(path), path.stat().st_mtime_ns)
    except (OSError, ValueError):
        return {}, None


def choose(kind, title=None, fonts=None):
    """The font for one kind of title text ("title", "subtitle" or "credits"), or None for the defaults."""
    title, fonts = title or {}, fonts or {}
    for pick in (title.get("font"), fonts.get(kind), fonts.get("title"), settings.get("fonts", kind, ""),
                 settings.get("fonts", "title", "")):
        if pick:
            return pick
    return None


def check_fonts(screenplay):
    """Problems with a screenplay's font choices (its "fonts" table and each title's "font"), for the plan step."""
    fonts = screenplay.get("fonts") or {}
    if not isinstance(fonts, dict):
        return ['"fonts" must be an object, e.g. {"title": "Lilita One", "credits": "Nunito"}']
    problems = [f'fonts.{k}: unknown text kind (use {", ".join(KINDS)})' for k in fonts if k not in KINDS]
    names = [fonts[k] for k in KINDS if fonts.get(k)]
    for scene in screenplay.get("scenes", []):
        for shot in scene.get("shots", []):
            if isinstance(shot.get("title"), dict) and shot["title"].get("font"):
                names.append(shot["title"]["font"])
    flat = [n for name in names for n in ([name] if isinstance(name, str) else name)]
    return problems + typography.check(flat)


def lettering_for(text, size, weight=600, fonts=None, lang=None):
    """The fonts for one piece of title text at `size` pixels: `fonts` (names, ids or files), else the [fonts]
    display / display_cjk settings when set, then the title defaults for each writing system in the text."""
    if not fonts:
        legacy = settings.get("fonts", "display_cjk" if _cjk(text) else "display", "")
        fonts = [legacy] if legacy else None
    return typeset.Lettering(typography.stack(fonts, role="title", text=text, lang=lang, weight=weight), size)


def font_for(text, size, weight=600, fonts=None, lang=None):
    """The PIL font that leads `text` (see lettering_for)."""
    return lettering_for(text, size, weight, fonts, lang).font()


def _draw_text(image, xy, text, letters, fill, anchor="mm", spacing=8):
    typeset.text(image, xy, text, letters, fill, anchor=anchor, align="center", spacing=spacing)


def title_card(title, width, height, path, fonts=None, language=None):
    """A transparent overlay for one title: main, lower, card or end. `fonts` and `language` default to the active
    film's screenplay."""
    if fonts is None or language is None:
        film, film_language = film_fonts()
        fonts = film if fonts is None else fonts
        language = film_language if language is None else language
    try:
        return _title_card(title, width, height, path, fonts, title.get("lang") or language)
    except typography.UnknownFont as exc:
        from codecinema.cartoon.screenplay import ScreenplayError
        raise ScreenplayError(f"title '{title.get('text', '')}': {exc}") from None


def _title_card(title, width, height, path, fonts, lang):
    scale = 2
    W, H = width * scale, height * scale
    style = title.get("style", "main")
    text = title.get("text", "")
    sub = title.get("sub", "")
    color = title.get("color", "#fffaf0")
    image = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if style in ("card", "end"):
        band = Image.new("RGBA", (W, H), (8, 10, 22, int(255 * title.get("dim", 0.55))))
        image = Image.alpha_composite(image, band)
    if style == "lower":
        size, pos, sub_size = int(H * 0.05), (W * 0.5, H * 0.84), int(H * 0.03)
    elif style == "main":
        size, pos, sub_size = int(H * title.get("size", 0.13)), (W * 0.5, H * title.get("y", 0.44)), int(H * 0.045)
    else:
        size, pos, sub_size = int(H * 0.1), (W * 0.5, H * 0.42), int(H * 0.04)
    font = lettering_for(text, size, 650, choose("title", title, fonts), lang)
    for dx, dy in ((0, 6), (0, 3)):
        _draw_text(shadow, (pos[0] + dx, pos[1] + dy * scale), text, font, (20, 16, 40, 200))
    if sub:
        sfont = lettering_for(sub, sub_size, 500, choose("subtitle", title, fonts), lang)
        sub_pos = (pos[0], pos[1] + size * 0.62 + sub_size * 0.9)
        _draw_text(shadow, (sub_pos[0], sub_pos[1] + 4 * scale), sub, sfont, (20, 16, 40, 190))
    shadow = shadow.filter(ImageFilter.GaussianBlur(10 * scale))
    image = Image.alpha_composite(image, shadow)
    _draw_text(image, pos, text, font, color)
    if sub:
        _draw_text(image, sub_pos, sub, sfont, title.get("sub_color", "#f4e9d2"))
    lines = title.get("credits", [])
    if lines:
        cfont = lettering_for(" ".join(lines), int(H * 0.028), 450, choose("credits", title, fonts), lang)
        y = pos[1] + size * 0.9 + (sub_size * 2.2 if sub else 0)
        for line in lines:
            _draw_text(image, (W * 0.5, y), line, cfont, "#e9e3d6")
            y += H * 0.045
    image = image.resize((width, height), Image.LANCZOS)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return path


def _stamp(seconds):
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return h, m, s, ms


def subtitles(plan, voices, lang, kind="srt"):
    """Subtitle text for one language from the spoken lines and their take lengths."""
    cues = []
    for line in plan.get("lines", []):
        text = line.get("subtitles", {}).get(lang)
        if not text:
            continue
        take = voices.get(line["id"], {})
        start = line["t"]
        end = start + max(1.2, take.get("duration", 1.5) + 0.35)
        cues.append((start, min(end, plan["duration"]), text))
    for i in range(len(cues) - 1):
        if cues[i][1] > cues[i + 1][0] - 0.05:
            cues[i] = (cues[i][0], max(cues[i][0] + 0.5, cues[i + 1][0] - 0.05), cues[i][2])
    out = ["WEBVTT", ""] if kind == "vtt" else []
    for i, (a, b, text) in enumerate(cues, 1):
        ha, ma, sa, msa = _stamp(a)
        hb, mb, sb, msb = _stamp(b)
        if kind == "vtt":
            out += [f"{ha:02d}:{ma:02d}:{sa:02d}.{msa:03d} --> {hb:02d}:{mb:02d}:{sb:02d}.{msb:03d}", text, ""]
        else:
            out += [str(i), f"{ha:02d}:{ma:02d}:{sa:02d},{msa:03d} --> {hb:02d}:{mb:02d}:{sb:02d},{msb:03d}", text, ""]
    return "\n".join(out)


def video_filters(plan, title_inputs, first_input=2):
    """An FFmpeg filter graph: grades and fades on the picture, then title overlays."""
    steps = []
    shots = plan["shots"]
    for shot in shots:
        grade = shot.get("grade")
        if grade:
            for f in GRADES.get(grade, []):
                steps.append(f"{f}:enable='between(t,{shot['start']:.3f},{shot['end']:.3f})'")
    for i, shot in enumerate(shots):
        kind = shot.get("transition", "cut")
        color = "white" if kind == "fade_white" else "black"
        if kind in ("fade", "fade_white", "dissolve") and i > 0:
            d = 0.3 if kind == "dissolve" else 0.55
            a = shot["start"]
            steps.append(f"fade=t=out:st={a - d:.3f}:d={d:.3f}:color={color}:enable='between(t,{a - d:.3f},{a:.3f})'")
            steps.append(f"fade=t=in:st={a:.3f}:d={d:.3f}:color={color}:enable='between(t,{a:.3f},{a + d:.3f})'")
        if kind == "fade_in":
            a = shot["start"]
            steps.append(f"fade=t=in:st={a:.3f}:d=1.0:enable='between(t,{a:.3f},{a + 1.0:.3f})'")
    end = plan["duration"]
    steps.append(f"fade=t=out:st={end - 1.6:.3f}:d=1.6:enable='between(t,{end - 1.6:.3f},{end:.3f})'")
    graph = [f"[0:v]{','.join(steps) or 'null'}[base]"]
    last = "base"
    for k, (title, path) in enumerate(title_inputs):
        idx = first_input + k
        start, dur = title["start"], title["dur"]
        fade_in, fade_out = min(0.8, dur / 3), min(0.9, dur / 3)
        graph.append(f"[{idx}:v]format=rgba,fade=t=in:st=0:d={fade_in:.2f}:alpha=1,"
                     f"fade=t=out:st={dur - fade_out:.2f}:d={fade_out:.2f}:alpha=1,setpts=PTS+{start:.3f}/TB[t{k}]")
        graph.append(f"[{last}][t{k}]overlay=0:0:eof_action=pass:enable='between(t,{start:.3f},{start + dur:.3f})'"
                     f"[v{k}]")
        last = f"v{k}"
    graph.append(f"[{last}]format=yuv420p[out]")
    return ";".join(graph), "out"
