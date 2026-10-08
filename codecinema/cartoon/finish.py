"""Finishing: title cards, subtitles, color grades and transitions for the master.

Titles are painted once as transparent PNGs and laid over the picture by
FFmpeg with soft fades; grades (such as the warm, grainy "memory" look) and
fades between shots are FFmpeg filters enabled only during their shots, so the
rendered frames stay untouched and the finishing pass is quick to redo.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from codecinema.workspace import settings

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
    return any("　" <= ch <= "鿿" or "＀" <= ch <= "￯" for ch in text)


def font_for(text, size, weight=600):
    role = "display_cjk" if _cjk(text) else "display"
    path = settings.font(role) or settings.font("ui")
    if not path:
        return ImageFont.load_default(size)
    font = ImageFont.truetype(path, size)
    try:
        font.set_variation_by_axes([weight])
    except (OSError, ValueError, AttributeError):
        pass
    return font


def _draw_text(draw, xy, text, font, fill, anchor="mm", spacing=8):
    draw.multiline_text(xy, text, font=font, fill=fill, anchor=anchor, align="center", spacing=spacing)


def title_card(title, width, height, path):
    """A transparent overlay for one title: main, lower, card or end."""
    scale = 2
    W, H = width * scale, height * scale
    style = title.get("style", "main")
    text = title.get("text", "")
    sub = title.get("sub", "")
    color = title.get("color", "#fffaf0")
    image = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw, sdraw = ImageDraw.Draw(image), ImageDraw.Draw(shadow)
    if style in ("card", "end"):
        band = Image.new("RGBA", (W, H), (8, 10, 22, int(255 * title.get("dim", 0.55))))
        image = Image.alpha_composite(image, band)
        draw = ImageDraw.Draw(image)
    if style == "lower":
        size, pos, sub_size = int(H * 0.05), (W * 0.5, H * 0.84), int(H * 0.03)
    elif style == "main":
        size, pos, sub_size = int(H * title.get("size", 0.13)), (W * 0.5, H * title.get("y", 0.44)), int(H * 0.045)
    else:
        size, pos, sub_size = int(H * 0.1), (W * 0.5, H * 0.42), int(H * 0.04)
    font = font_for(text, size, 650)
    for dx, dy in ((0, 6), (0, 3)):
        _draw_text(sdraw, (pos[0] + dx, pos[1] + dy * scale), text, font, (20, 16, 40, 200))
    if sub:
        sfont = font_for(sub, sub_size, 500)
        sub_pos = (pos[0], pos[1] + size * 0.62 + sub_size * 0.9)
        _draw_text(sdraw, (sub_pos[0], sub_pos[1] + 4 * scale), sub, sfont, (20, 16, 40, 190))
    shadow = shadow.filter(ImageFilter.GaussianBlur(10 * scale))
    image = Image.alpha_composite(image, shadow)
    draw = ImageDraw.Draw(image)
    _draw_text(draw, pos, text, font, color)
    if sub:
        _draw_text(draw, sub_pos, sub, sfont, title.get("sub_color", "#f4e9d2"))
    lines = title.get("credits", [])
    if lines:
        cfont = font_for(" ".join(lines), int(H * 0.028), 450)
        y = pos[1] + size * 0.9 + (sub_size * 2.2 if sub else 0)
        for line in lines:
            _draw_text(draw, (W * 0.5, y), line, cfont, "#e9e3d6")
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
