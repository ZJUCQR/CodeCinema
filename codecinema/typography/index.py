"""Installed fonts: the bundled, workspace, per-user and system font folders, indexed by family name.

Names, weights, styles and the writing systems a font declares are read with fontTools once per file and kept in
the download cache (fonts/installed.json), so later runs only list the folders. Character maps (coverage) are read
on demand. Without fontTools (e.g. inside Blender) the index is empty and coverage is not checked.
"""
import functools
import json
import logging
import os
import tempfile
from pathlib import Path

from codecinema.typography.catalog import key

SUFFIXES = (".ttf", ".otf", ".ttc", ".otc")
VERSION = 1
KINDS = {"bundled": 0, "user": 1, "system": 2}
# OS/2 ulUnicodeRange bits per writing system, and code-page bits for CJK regions.
_RANGE_BITS = {"latin": 0, "latin-ext": 2, "greek": 7, "cyrillic": 9, "armenian": 10, "hebrew": 11, "arabic": 13,
               "devanagari": 15, "bengali": 16, "gurmukhi": 17, "gujarati": 18, "oriya": 19, "tamil": 20,
               "telugu": 21, "kannada": 22, "malayalam": 23, "thai": 24, "lao": 25, "georgian": 26,
               "vietnamese": 29, "tibetan": 70, "syriac": 71, "thaana": 72, "sinhala": 73, "myanmar": 74,
               "ethiopic": 75, "khmer": 80, "mongolian": 81}
_CODEPAGES = {17: "ja", 18: "zh-Hans", 19: "ko", 20: "zh-Hant", 21: "ko"}
_STATE = {}


def folders():
    """(folder, kind) pairs searched for installed fonts, for the active film."""
    from codecinema.workspace import paths
    try:
        from codecinema.workspace import settings
        film = settings.ROOT
    except (ImportError, OSError, ValueError):      # no readable workspace: only the standard folders count
        film = None
    return paths.font_dirs(film)


def _systems(os2):
    if os2 is None:
        return []
    bits = 0
    for i in range(4):
        bits |= (getattr(os2, f"ulUnicodeRange{i + 1}", 0) or 0) << (32 * i)
    found = [name for name, bit in _RANGE_BITS.items() if bits >> bit & 1]
    pages = getattr(os2, "ulCodePageRange1", 0) or 0
    cjk = {system for bit, system in _CODEPAGES.items() if pages >> bit & 1}
    if not cjk:
        if bits >> 49 & 1 or bits >> 50 & 1:
            cjk.add("ja")
        if bits >> 56 & 1:
            cjk.add("ko")
        if bits >> 59 & 1 and not cjk:
            cjk.add("zh-Hans")
    return found + sorted(cjk)


def _decoded(record):
    try:
        return record.toUnicode().strip()
    except Exception:           # noqa: BLE001 - undecodable legacy name records are skipped
        return ""


def _describe(font, index, path):
    names = {_decoded(r) for r in font["name"].names if r.nameID in (1, 16, 21)} - {""}
    family = font["name"].getBestFamilyName() or (min(names) if names else Path(path).stem)
    os2 = font.get("OS/2")
    weight = int(os2.usWeightClass) if os2 else 400
    weight = weight * 100 if 0 < weight < 10 else weight
    italic = bool(os2.fsSelection & 1) if os2 else bool(font["head"].macStyle & 2)
    weights = None
    if "fvar" in font:
        for axis in font["fvar"].axes:
            if axis.axisTag == "wght":
                weights = [int(axis.minValue), int(axis.maxValue)]
    return {"index": index, "family": family, "names": sorted({key(n) for n in names | {family}}),
            "weight": weight, "weights": weights, "italic": italic, "systems": _systems(os2)}


@functools.lru_cache(maxsize=256)
def read(path):
    """Face descriptions of one font file (several for a collection); [] when unreadable."""
    try:
        from fontTools.ttLib import TTCollection, TTFont
    except ImportError:
        return []
    logging.getLogger("fontTools").setLevel(logging.ERROR)     # odd timestamps and tables in system fonts are fine
    source = None
    try:
        if str(path).lower().endswith((".ttc", ".otc")):
            source = TTCollection(path, lazy=True)
            fonts = source.fonts
        else:
            source = TTFont(path, lazy=True)
            fonts = [source]
        return [_describe(font, i, path) for i, font in enumerate(fonts)]
    except Exception:           # noqa: BLE001 - a damaged or unsupported font file is ignored, as font managers do
        return []
    finally:
        _close(source)


def _close(font):
    """Release the file now: fontTools objects hold it open until garbage collection, and Windows cannot replace or
    delete an open file."""
    try:
        if font is not None:
            font.close()
    except Exception:           # noqa: BLE001 - closing is best effort
        pass


def _index_file():
    from codecinema.runtime import downloads
    return downloads.cache_root() / "fonts" / "installed.json"


def faces():
    """Every installed face: dicts with path, index, family, names, weight, weights, italic, systems and kind."""
    if "faces" in _STATE:
        return _STATE["faces"]
    try:
        import fontTools  # noqa: F401
    except ImportError:
        _STATE["faces"] = []
        return []
    store = _index_file()
    try:
        saved = json.loads(store.read_text(encoding="utf-8"))
        known = saved["files"] if saved.get("version") == VERSION else {}
    except (OSError, ValueError, KeyError, TypeError):
        known = {}
    files, result, changed = {}, [], False
    for folder, kind in folders():
        if not folder.is_dir():
            continue
        for dirpath, _dirs, names in os.walk(folder):
            for name in sorted(names):
                if not name.lower().endswith(SUFFIXES):
                    continue
                path = os.path.join(dirpath, name)
                try:
                    st = os.stat(path)
                except OSError:
                    continue
                stamp = [st.st_size, st.st_mtime_ns]
                entry = known.get(path)
                if not entry or entry.get("stamp") != stamp:
                    entry, changed = {"stamp": stamp, "faces": read(path)}, True
                files[path] = entry
                result += [{**face, "path": path, "kind": kind} for face in entry["faces"]]
    if changed or set(files) != set(known):
        try:
            store.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix="installed.", suffix=".part", dir=store.parent)
            with os.fdopen(fd, "w", encoding="utf-8") as out:
                json.dump({"version": VERSION, "files": files}, out, ensure_ascii=False)
            os.replace(temporary, store)
        except OSError:
            pass                # a read-only cache only costs a rescan next time
    _STATE["faces"] = result
    return result


def lookup(*names):
    """Installed faces whose family name matches one of `names` (bundled, then user, then system folders)."""
    wanted = {key(n) for n in names if n}
    hits = [face for face in faces() if wanted & set(face["names"])]
    return sorted(hits, key=lambda face: KINDS.get(face["kind"], 3))


def with_system(system):
    """Installed faces that declare a writing system, regular upright faces first."""
    hits = [face for face in faces() if system in face["systems"]]
    return sorted(hits, key=lambda face: (KINDS.get(face["kind"], 3), face["italic"], abs(face["weight"] - 400),
                                          face["family"]))


def families():
    """Installed family names (for suggestions)."""
    return sorted({face["family"] for face in faces()})


@functools.lru_cache(maxsize=128)
def charset(path, index=0):
    """The code points a face maps to glyphs, or None when fontTools cannot tell (then every character counts)."""
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        return None
    font = None
    try:
        font = TTFont(path, lazy=True, fontNumber=index)
        return frozenset(font.getBestCmap() or {})
    except Exception:           # noqa: BLE001 - unreadable character map: let the renderer try
        return None
    finally:
        _close(font)


@functools.lru_cache(maxsize=128)
def axes(path, index=0):
    """Variation axes as ((tag, minimum, default, maximum), ...) in the font's order; () for static fonts."""
    font = None
    try:
        from fontTools.ttLib import TTFont
        font = TTFont(path, lazy=True, fontNumber=index)
        if "fvar" not in font:
            return ()
        return tuple((a.axisTag, a.minValue, a.defaultValue, a.maxValue) for a in font["fvar"].axes)
    except Exception:           # noqa: BLE001 - no fontTools or an unreadable table: draw the default instance
        return ()
    finally:
        _close(font)


def clear():
    """Forget indexed folders and cached character maps (after installing fonts, and in tests)."""
    _STATE.clear()
    read.cache_clear()
    charset.cache_clear()
    axes.cache_clear()
