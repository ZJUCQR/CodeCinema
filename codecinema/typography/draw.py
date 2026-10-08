"""Draw text on PIL images with per-run fonts.

    lettering = Lettering(typography.stack(fonts, role="title", text=text, weight=650), size)
    draw.text(image, (x, y), text, lettering, "#fffaf0", anchor="mm", align="center", spacing=8)

Text one font covers is drawn by ImageDraw.multiline_text itself, so it looks exactly as before. Mixed text is laid
out like multiline_text lays out lines, each line's runs sharing the first font's baseline; lines in complex scripts
are shaped by skia (typography.shaping) so Arabic, Hebrew, Indic and Thai titles are right on every platform.
"""
import functools

from PIL import ImageDraw, ImageFont

from codecinema.typography import scripts, shaping
from codecinema.typography.text import runs as split_runs


@functools.lru_cache(maxsize=96)
def pil_font(face, size):
    """A PIL font for a Face at `size` pixels, set to the face's weight when the font is variable."""
    font = ImageFont.truetype(face.path, size, index=face.index)
    values = face.coordinates(size)
    if values:
        try:
            font.set_variation_by_axes(values)
        except (OSError, ValueError, AttributeError):
            pass                # FreeType without variation support draws the default instance
    return font


class Lettering:
    """A font stack (faces, best first) at one pixel size."""

    def __init__(self, faces, size):
        self.faces = [face for face in faces if face is not None]
        self.size = size

    @property
    def primary(self):
        return self.faces[0] if self.faces else None

    def font(self, face=None):
        face = face or self.primary
        return pil_font(face, self.size) if face else ImageFont.load_default(self.size)

    def runs(self, line):
        return split_runs(line, self.faces)

    def single(self, text):
        """The one face that draws all of `text` without shaping help, or None when it needs several."""
        lines = text.split("\n")
        used = {face for line in lines for _, face in self.runs(line)}
        if len(used) > 1 or any(scripts.complex_text(line) for line in lines):
            return None
        return next(iter(used), None) or self.primary

    def width(self, line):
        parts = self.runs(line)
        if _shaped(line, parts):
            return shaping.line(tuple(parts), self.size)[1]
        return sum(self.font(face).getlength(segment) for segment, face in parts)


def _shaped(line, parts):
    return bool(parts) and all(face is not None for _, face in parts) and scripts.complex_text(line) \
        and shaping.available()


def text(image, xy, text, lettering, fill, anchor="mm", align="center", spacing=8):
    """Draw like ImageDraw.multiline_text, switching fonts per run where the first font lacks glyphs."""
    draw = ImageDraw.Draw(image)
    face = lettering.single(text)
    if face is not None or not lettering.faces:
        draw.multiline_text(xy, text, font=lettering.font(face), fill=fill, anchor=anchor, align=align,
                            spacing=spacing)
        return
    primary = lettering.font()
    lines = text.split("\n")
    line_spacing = primary.getbbox("A")[3] + spacing
    widths = [lettering.width(line) for line in lines]
    widest = max(widths)
    top = xy[1] - {"m": (len(lines) - 1) * line_spacing / 2, "d": (len(lines) - 1) * line_spacing}.get(anchor[1], 0)
    # The anchor's vertical position relative to the baseline, from the first font (as PIL anchors a line).
    lift = primary.getbbox("A", anchor="l" + anchor[1])[1] - primary.getbbox("A", anchor="ls")[1]
    for line, width in zip(lines, widths):
        left = xy[0] + {"center": (widest - width) / 2, "right": widest - width}.get(align, 0) \
            - {"m": widest / 2, "r": widest}.get(anchor[0], 0)
        baseline = top + lift
        parts = lettering.runs(line)
        if _shaped(line, parts):
            coverage, position = shaping.mask(parts, lettering.size, left, baseline)
            draw.bitmap(position, coverage, fill=fill)
        else:
            x = left
            for segment, run_face in (reversed(parts) if scripts.rtl(line) else parts):
                font = lettering.font(run_face)
                draw.text((x, baseline), segment, font=font, fill=fill, anchor="ls")
                x += font.getlength(segment)
        top += line_spacing
