"""Resolve font names and roles to font files, with offline fallback.

    find("Lilita One", weight=700)            # -> Face: bundled, installed (user, then system), cached or downloaded
    find("assets/nian/fonts/Seal.otf")        # a font file; relative paths start at the film (assets/ at the workspace)
    stack(["Lilita One"], role="title", text="Nian · 年")    # -> [Face, ...] that together cover the text
    fetch(family)                             # download a family and its license for offline use

A catalog family that is neither installed nor cached is downloaded on first use, with one line on stderr, unless
downloads are off (CODECINEMA_OFFLINE=1, CODECINEMA_FONTS_DOWNLOAD=off or [fonts] download = "off"). Text then falls
back to a font for its writing system: the role's defaults, the system's fonts, and finally the bundled fonts.
Mirrors ([fonts] mirror or CODECINEMA_FONTS_MIRROR) are URL templates with {url}, {repo}, {commit}, {path} and
{name}, or base URLs of a copy of the repository, tried before the built-in addresses; separate several with spaces.
"""
import os
import re
import sys
import unicodedata
from collections import namedtuple
from dataclasses import dataclass
from pathlib import Path

from codecinema.runtime import downloads
from codecinema.typography import catalog, index, scripts

FONT_SUFFIXES = (".ttf", ".otf", ".ttc", ".otc", ".woff", ".woff2")
_Option = namedtuple("_Option", "weights style path index kind")
_FOUND = {}
_NOTES = set()


class FontError(ValueError):
    """A font name, file or download problem, with a message that says what to do."""


class UnknownFont(FontError):
    """A family name that is neither in the catalog nor installed."""

    def __init__(self, name):
        super().__init__(name)
        self.name = name

    def __str__(self):              # suggestions are computed only when the message is shown
        close = catalog.suggestions(self.name, index.families())
        hint = f" Did you mean: {', '.join(close)}?" if close else ""
        return (f"Unknown font family '{self.name}'.{hint} List the families with: codecinema library fonts "
                f"(or give the path of a .ttf/.otf file)")


class FontUnavailable(FontError):
    """A catalog family that is not on this machine and cannot be downloaded now."""


@dataclass(frozen=True)
class Face:
    """One font face in a file: what PIL, skia and Blender load. `weight` is the weight to draw (the wght
    coordinate of a variable font)."""
    path: str
    index: int = 0
    family: str = ""
    weight: int = 400
    style: str = "normal"
    source: str = "file"            # bundled | user | system | cache | file
    id: str = ""                    # catalog id

    def charset(self):
        """Code points the face covers, or None when unknown."""
        return index.charset(self.path, self.index)

    def covers(self, text):
        chars = self.charset()
        return chars is None or all(ord(ch) in chars for ch in text if needs_glyph(ch))

    def axes(self):
        return index.axes(self.path, self.index)

    def coordinates(self, size=None):
        """Design coordinates for every variation axis (weight, italic, optical size at `size`), or None."""
        axes = self.axes()
        if not axes:
            return None
        values = []
        for tag, lo, default, hi in axes:
            value = {"wght": self.weight, "ital": 1.0 if self.style == "italic" else 0.0,
                     "opsz": size or default}.get(tag, default)
            values.append(min(max(float(value), lo), hi))
        return values


def needs_glyph(ch):
    """False for control and format characters (joiners, direction marks, variation selectors)."""
    return unicodedata.category(ch) not in ("Cc", "Cf") and not 0xFE00 <= ord(ch) <= 0xFE0F


def _setting(name, default):
    try:
        from codecinema.workspace import settings
    except (ImportError, OSError, ValueError):      # outside a readable workspace the defaults apply
        return default
    return settings.get("fonts", name, default)


def downloads_enabled():
    """Whether missing catalog fonts may be downloaded now."""
    if downloads.offline():
        return False
    value = os.environ.get("CODECINEMA_FONTS_DOWNLOAD")
    if value is None:
        value = _setting("download", "auto")
    return str(value).strip().lower() not in ("off", "0", "false", "no", "never")


def mirrors():
    """User mirror templates, tried before the built-in download addresses."""
    value = os.environ.get("CODECINEMA_FONTS_MIRROR")
    if value is None:
        value = _setting("mirror", "")
    return tuple(part for part in re.split(r"[\s;]+", str(value or "")) if part)


def note(message):
    """Print a font notice once per process."""
    if message not in _NOTES:
        _NOTES.add(message)
        print(f"fonts: {message}", file=sys.stderr, flush=True)


def clear():
    """Forget resolved fonts and indexed folders (after installing fonts, and in tests)."""
    _FOUND.clear()
    _NOTES.clear()
    index.clear()
    # Cached PIL fonts and skia typefaces keep their files open (Windows cannot replace or delete those).
    for name, caches in (("draw", ("pil_font",)), ("shaping", ("typeface", "line"))):
        module = sys.modules.get(f"codecinema.typography.{name}")
        for cache in caches if module is not None else ():
            getattr(module, cache).cache_clear()


# ------------------------------------------------------------------------------------------------ finding one face
def _weight_rank(want, lo, hi):
    """CSS font matching: exact or inside a variable range first, then the documented search direction."""
    if lo <= want <= hi:
        return (0, 0)
    near = lo if want < lo else hi
    if 400 <= want <= 500:
        order = 1 if want < near <= 500 else 2 if near < want else 3
    elif want < 400:
        order = 1 if near < want else 2
    else:
        order = 1 if near > want else 2
    return (order, abs(near - want))


def _pick(options, weight, style):
    return min(options, key=lambda o: (o.style != style, _weight_rank(weight, *o.weights), o.kind != "bundled"))


def _face(option, weight, family, fid=""):
    lo, hi = option.weights
    return Face(str(option.path), option.index, family, int(min(max(weight, lo), hi)), option.style, option.kind, fid)


def _installed(faces):
    return [_Option(tuple(f["weights"]) if f["weights"] else (f["weight"], f["weight"]),
                    "italic" if f["italic"] else "normal", f["path"], f["index"], f["kind"]) for f in faces]


def _cache_name(fam, file):
    return f"fonts/{fam.id}/{file.name}"


def _bundled_dirs():
    from codecinema.workspace.paths import font_dirs
    return [path for path, kind in font_dirs() if kind == "bundled" and path.is_dir()]


def bundled_path(fam, name):
    """Where a catalog file ships with CodeCinema, or None."""
    for shipped, original in fam.bundled:
        if original == name:
            for folder in _bundled_dirs():
                if (folder / shipped).is_file():
                    return folder / shipped
    return None


def _is_path(text):
    return "/" in text or "\\" in text or text.startswith("~") or text.lower().endswith(FONT_SUFFIXES)


def _file_face(text, weight, style):
    try:
        from codecinema.workspace import settings
        from codecinema.workspace.paths import resolve_path
        path = Path(resolve_path(text, settings.ROOT))
    except (ImportError, OSError, ValueError):      # no workspace: relative to the working directory
        path = Path(text).expanduser()
    if not path.is_file():
        raise FontError(f"No font file at {path}")
    described = index.read(str(path))
    if not described:
        return Face(str(path), 0, path.stem, weight, style, "file")
    option = _installed([{**described[0], "path": str(path), "kind": "file"}])[0]
    return _face(option, weight, described[0]["family"])


def _catalog_face(fam, weight, style, allow):
    options = []
    for file in fam.files:
        path = bundled_path(fam, file.name)
        if path:
            options.append(_Option(file.weights, file.style, path, 0, "bundled"))
    if options:
        return _face(_pick(options, weight, style), weight, fam.name, fam.id)
    installed = [f for f in index.lookup(fam.name, *fam.aliases) if f["kind"] != "bundled"]
    if installed:
        return _face(_pick(_installed(installed), weight, style), weight, fam.name, fam.id)
    root = downloads.cache_root()
    every = [_Option(f.weights, f.style, root / _cache_name(fam, f), 0, "cache") for f in fam.files]
    best = _pick(every, weight, style)
    file = fam.files[every.index(best)]
    cached = [o for o, f in zip(every, fam.files) if downloads.is_cached(_cache_name(fam, f), f.sha256, f.size)]
    if best in cached:
        return _face(best, weight, fam.name, fam.id)
    reason = " and downloads are off"
    if allow:
        try:
            fetch(fam, [file])
            return _face(best, weight, fam.name, fam.id)
        except downloads.DownloadError as exc:
            reason = f" ({str(exc).splitlines()[0]})"
    if cached:
        return _face(_pick(cached, weight, style), weight, fam.name, fam.id)
    raise FontUnavailable(f"{fam.name} is not installed or downloaded{reason}. Download it for offline use with: "
                          f"codecinema library fonts --download {fam.id}")


def find(name, weight=400, style="normal", *, download=None):
    """The face for a family name, catalog id or font file. Raises UnknownFont (with suggestions) for a name that
    is neither in the catalog nor installed, and FontUnavailable when a catalog family cannot be had now."""
    if isinstance(name, Face):
        return name
    text = str(name or "").strip()
    if not text:
        raise FontError("A font name is empty")
    allow = downloads_enabled() if download is None else bool(download)
    memo = (text, int(weight), style, allow)
    if memo in _FOUND:
        found = _FOUND[memo]
        if isinstance(found, FontError):
            raise found
        return found
    try:
        if _is_path(text):
            found = _file_face(text, int(weight), style)
        elif catalog.family(text):
            found = _catalog_face(catalog.family(text), int(weight), style, allow)
        else:
            installed = index.lookup(text)
            if not installed:
                raise UnknownFont(text)
            found = _face(_pick(_installed(installed), int(weight), style), int(weight), installed[0]["family"])
    except FontError as exc:
        _FOUND[memo] = exc
        raise
    _FOUND[memo] = found
    return found


def check(names):
    """Problems with font names, without downloading: unknown families and missing files."""
    problems = []
    for name in _names(names):
        if _is_path(name):
            try:
                _file_face(name, 400, "normal")
            except FontError as exc:
                problems.append(str(exc))
        elif not catalog.family(name) and not index.lookup(name):
            problems.append(str(UnknownFont(name)))
    return problems


# ------------------------------------------------------------------------------------------------ stacks
def _names(fonts):
    if not fonts:
        return []
    if isinstance(fonts, (str, Face)):
        return [fonts]
    return [f for f in fonts if f]


def _missing(chars, faces):
    out = set(chars)
    for face in faces:
        covered = face.charset()
        if covered is None:
            return set()
        out = {ch for ch in out if ord(ch) not in covered}
    return out


def _try(name, weight, style, download):
    try:
        return find(name, weight, style, download=download)
    except FontUnavailable as exc:
        note(str(exc))
    except FontError:
        pass                    # a system family that is not installed here
    return None


def _system_faces(system, weight, style):
    for name in catalog.SYSTEM.get(system, ()):
        installed = index.lookup(name)
        if installed:
            yield _face(_pick(_installed(installed), weight, style), weight, installed[0]["family"])
    for found in index.with_system(system)[:40]:
        yield _face(_installed([found])[0], weight, found["family"])


def stack(fonts=None, *, role="title", text="", lang=None, weight=400, style="normal", download=None):
    """Faces for drawing `text`, best first: the requested fonts (names, ids, files or Faces), then the role's
    defaults for each writing system the text needs (see catalog.ROLES), then installed system fonts, then the
    bundled fonts. A face is added only when it covers characters the earlier ones lack. Han-only text follows
    `lang` (a language name or tag) to choose Chinese, Japanese or Korean fonts."""
    faces = []
    for name in _names(fonts):
        try:
            face = find(name, weight, style, download=download)
        except FontUnavailable as exc:
            note(f"{exc} Using a fallback font.")
            continue
        if face not in faces:
            faces.append(face)
    chars = {ch for ch in text if needs_glyph(ch)}
    missing = _missing(chars, faces) if faces else chars
    han = scripts.han_system(text, lang)
    systems = scripts.writing_systems("".join(sorted(missing)), lang, context=text)
    if not faces and not systems:
        systems = [scripts.language_system(lang) or "latin"]

    def add(face, pending, strict=False):
        """Append a face that covers some pending characters; a role default may lead an empty stack anyway."""
        nonlocal missing
        covered = face.charset()
        useful = covered is None or not pending or any(ord(ch) in covered for ch in pending)
        if face in faces or (not useful and (faces or strict)):
            return pending
        faces.append(face)
        missing = _missing(missing, [face])
        return _missing(pending, [face])

    # Writing systems in priority order; each tries the role's families, then the fonts installed for it.
    for system in systems:
        pending = {ch for ch in missing if scripts.system_of(ch, han) == system}
        if faces and not pending:
            continue
        for name in catalog.role_families(role, system):
            face = _try(name, weight, style, download)
            if face is not None:
                pending = add(face, pending)
                if not pending:
                    break
        if pending:
            for face in _system_faces(system, weight, style):
                pending = add(face, pending, strict=True)
                if not pending:
                    break
    if missing or not faces:
        for fam in catalog.FAMILIES:
            if fam.bundled and (missing or not faces):
                face = _try(fam.id, weight, style, False)
                if face is not None:
                    add(face, missing, strict=bool(faces))
    return faces


# ------------------------------------------------------------------------------------------------ downloads
def license_text(fam):
    """The license text for a family whose folder has none: its notice and the OFL, taken from a bundled copy."""
    for folder in _bundled_dirs():
        for path in sorted(folder.glob("OFL*.txt")):
            body = path.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n\n", 1)[1]
            return f"{fam.notice}\n\n{body}"
    raise FontError(f"Missing the bundled OFL text needed for {fam.name}. Reinstall CodeCinema.")


def license_path(fam):
    """The local copy of a family's license text, or None before it is downloaded."""
    if fam.license_file:
        shipped = bundled_path(fam, fam.license_file.name)
        if shipped:
            return shipped
        name = _cache_name(fam, fam.license_file)
        return downloads.cache_root() / name if downloads.is_cached(name, fam.license_file.sha256) else None
    path = downloads.cache_root() / "fonts" / fam.id / "OFL.txt"
    return path if path.is_file() else None


def fetch(family, files=None, quiet=False):
    """Download a catalog family's files (default: all) with its license into the cache; returns the font paths."""
    fam = family if isinstance(family, catalog.Family) else catalog.family(family)
    if fam is None:
        raise UnknownFont(family)
    if fam.license_file:
        downloads.cached(_cache_name(fam, fam.license_file), fam.urls(fam.license_file, mirrors()),
                         fam.license_file.sha256, fam.license_file.size, quiet=True)
    else:
        target = downloads.cache_root() / "fonts" / fam.id / "OFL.txt"
        if not target.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(license_text(fam), encoding="utf-8")
    return [downloads.cached(_cache_name(fam, f), fam.urls(f, mirrors()), f.sha256, f.size,
                             label=f"font {fam.name} ({fam.license}): {f.name}", quiet=quiet)
            for f in (fam.files if files is None else files)]


def status(fam):
    """'bundled', 'installed' (user or system folders), 'cached', 'partial' (some weights cached) or 'downloadable'."""
    if any(bundled_path(fam, f.name) for f in fam.files):
        return "bundled"
    if any(f["kind"] != "bundled" for f in index.lookup(fam.name, *fam.aliases)):
        return "installed"
    cached = sum(downloads.is_cached(_cache_name(fam, f), f.sha256, f.size) for f in fam.files)
    return "cached" if cached == len(fam.files) else "partial" if cached else "downloadable"


def select(target):
    """Families named by a comma-separated list of families, writing systems or languages, categories, or 'all'."""
    out = []
    for item in (part.strip() for part in str(target).split(",")):
        if not item:
            continue
        lowered = {k.lower(): k for k in catalog.SCRIPTS} | {v.lower(): k for k, v in catalog.SCRIPTS.items()}
        system = lowered.get(item.lower()) or scripts.language_system(item)
        if item.lower() == "all":
            found = list(catalog.FAMILIES)
        elif catalog.family(item):
            found = [catalog.family(item)]
        elif system:
            found = catalog.families(script=system)
        elif item.lower() in catalog.CATEGORIES:
            found = catalog.families(category=item.lower())
        else:
            raise UnknownFont(item)
        out += [f for f in found if f not in out]
    return out
