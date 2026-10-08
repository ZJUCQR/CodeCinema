"""Shape lines with skia's paragraph layout (HarfBuzz and ICU, shipped with skia-python): Arabic joining, Indic
clusters, Thai marks and right-to-left order come out the same on every platform.

    picture, width, baseline, height = line((("مرحبا", face),), 48)    # white glyphs, origin at the top left
    image, (left, top) = mask(runs, 48, x, y)                          # coverage for PIL, baseline at (x, y)
"""
import functools
import math

from codecinema.typography import scripts


@functools.lru_cache(maxsize=1)
def available():
    """True when skia's paragraph layout works here (checked once with a tiny paragraph)."""
    try:
        import skia
        layout = skia.textlayout
        collection = layout.FontCollection()
        collection.setDefaultFontManager(layout.TypefaceFontProvider())
        builder = layout.ParagraphBuilder.make(layout.ParagraphStyle(), collection, skia.Unicode.ICU_Make())
        builder.addText("a")
        builder.Build().layout(100)
        return True
    except Exception:           # noqa: BLE001 - no skia, no text layout or no ICU data: PIL draws instead
        return False


@functools.lru_cache(maxsize=64)
def typeface(face):
    """A skia typeface for a Face, at its weight when the font is variable."""
    import skia
    loaded = skia.Typeface.MakeFromFile(face.path, face.index)
    if loaded is None:
        raise OSError(f"skia cannot read the font {face.path}")
    values = face.coordinates()
    if values:
        position = skia.FontArguments.VariationPosition
        # FontArguments only points at the coordinates: keep every object alive until the clone exists.
        coordinates = position.Coordinates([position.Coordinate(int.from_bytes(tag.encode("ascii"), "big"), value)
                                            for (tag, *_), value in zip(face.axes(), values)])
        design = position(coordinates)
        arguments = skia.FontArguments()
        arguments.setVariationDesignPosition(design)
        loaded = loaded.makeClone(arguments) or loaded
    return loaded


@functools.lru_cache(maxsize=256)
def line(runs, size):
    """Shape one line of (segment, face) runs. Returns (skia.Picture of white glyphs with the line's top left at the
    origin, advance width, baseline below the top, height)."""
    import skia
    layout = skia.textlayout
    provider = layout.TypefaceFontProvider()
    names = {}
    for _segment, face in runs:
        if face not in names:
            names[face] = f"codecinema-{len(names)}"
            provider.registerTypeface(typeface(face), names[face])
    collection = layout.FontCollection()
    collection.setDefaultFontManager(provider)
    builder = layout.ParagraphBuilder.make(layout.ParagraphStyle(), collection, skia.Unicode.ICU_Make())
    rtl = scripts.rtl("".join(segment for segment, _ in runs))
    for i, (segment, face) in enumerate(runs):
        style = layout.TextStyle()
        style.setFontSize(size)
        style.setFontFamilies([names[face]])
        style.setForegroundPaint(skia.Paint(AntiAlias=True, Color=skia.ColorWHITE))
        builder.pushStyle(style)
        # A right-to-left line is isolated as such: the paragraph's own direction is left-to-right.
        builder.addText(("\u2067" if rtl and i == 0 else "") + segment + ("\u2069" if rtl and i == len(runs) - 1
                                                                            else ""))
        builder.pop()
    paragraph = builder.Build()
    paragraph.layout(1e6)
    width, height = paragraph.LongestLine, paragraph.Height
    recorder = skia.PictureRecorder()
    canvas = recorder.beginRecording(skia.Rect.MakeLTRB(-size, -size, width + size, height + size))
    paragraph.paint(canvas, 0, 0)
    return recorder.finishRecordingAsPicture(), width, paragraph.AlphabeticBaseline, height


def mask(runs, size, x, y):
    """A grayscale PIL coverage image of a shaped line and the integer (left, top) to draw it at, so that the line
    starts at x on the baseline y."""
    import numpy as np
    import skia
    from PIL import Image
    picture, width, baseline, height = line(tuple(runs), size)
    pad = math.ceil(size * 0.6)
    top_edge = y - baseline
    left, top = math.floor(x) - pad, math.floor(top_edge) - pad
    surface = skia.Surface(math.ceil(width) + 2 * pad + 1, math.ceil(height) + 2 * pad + 1)
    canvas = surface.getCanvas()
    canvas.clear(skia.ColorTRANSPARENT)
    canvas.translate(pad + x - math.floor(x), pad + top_edge - math.floor(top_edge))
    canvas.drawPicture(picture)
    alpha = surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)[:, :, 3]
    return Image.fromarray(np.ascontiguousarray(alpha), "L"), (left, top)
