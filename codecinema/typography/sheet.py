"""A font specimen sheet: one row per family with a sample line in its main writing system.

    specimen("fonts.png")                       # every catalog family (downloads what is missing, if allowed)
    specimen("ja.png", ["ja", "Lilita One"])    # families, writing systems, languages or categories
"""
from pathlib import Path

from PIL import Image

from codecinema.typography import catalog, resolve
from codecinema.typography import draw as typeset

BACKGROUND, INK, MUTED, ACCENT = "#14161d", "#f2efe8", "#9aa3b2", "#f0b75e"
MARGIN, LABEL, ROW, HEADING = 48, 470, 88, 76


def _letters(text, size, weight=500):
    """The bundled UI lettering for names and notes (no downloads)."""
    return typeset.Lettering(resolve.stack(["fredoka"], role="ui", text=text, weight=weight, download=False), size)


def _write(image, xy, text, size, fill, weight=500):
    typeset.text(image, xy, text, _letters(text, size, weight), fill, anchor="ls", align="left")


def specimen(path, names=None, width=1800, download=None):
    """Render the sheet to `path` (PNG) and return its path. Families that cannot be had are listed as such."""
    chosen = resolve.select(",".join(names)) if names else list(catalog.FAMILIES)
    order = list(catalog.SCRIPTS)
    chosen.sort(key=lambda f: (order.index(f.script), catalog.FAMILIES.index(f)))
    groups = list(dict.fromkeys(f.script for f in chosen))
    rows = []
    for fam in chosen:
        try:
            face = resolve.find(fam.id, 400, download=download)
            rows.append((fam, face, f"{fam.category} · {fam.license} · {resolve.status(fam)}"))
        except resolve.FontError:
            rows.append((fam, None, f"{fam.category} · {fam.license} · not downloaded"))
    height = MARGIN * 2 + 70 + HEADING * len(groups) + ROW * len(rows)
    image = Image.new("RGBA", (width, height), BACKGROUND)
    _write(image, (MARGIN, MARGIN + 34), f"CodeCinema fonts · {len(rows)} families", 38, INK, 600)
    _write(image, (MARGIN + 640, MARGIN + 34), f"google/fonts @ {catalog.COMMIT[:7]} · SHA-256 verified", 22, MUTED)
    y = MARGIN + 70
    for group in groups:
        y += HEADING
        _write(image, (MARGIN, y - 18), catalog.SCRIPTS[group], 30, ACCENT, 600)
        for fam, face, note in (row for row in rows if row[0].script == group):
            y += ROW
            _write(image, (MARGIN, y - 38), fam.name, 26, INK, 600)
            _write(image, (MARGIN, y - 10), note, 18, MUTED)
            sample = catalog.SAMPLES[fam.script]
            if face is None:
                _write(image, (MARGIN + LABEL, y - 22), "Download: codecinema library fonts --download " + fam.id,
                       22, MUTED)
                continue
            size, room = 46, width - MARGIN * 2 - LABEL
            letters = typeset.Lettering(resolve.stack([face], role="ui", text=sample, download=False), size)
            used = letters.width(sample)
            if used > room:
                letters = typeset.Lettering(letters.faces, max(12, int(size * room / used)))
            typeset.text(image, (MARGIN + LABEL, y - 20), sample, letters, INK, anchor="ls", align="left")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(path)
    return path
