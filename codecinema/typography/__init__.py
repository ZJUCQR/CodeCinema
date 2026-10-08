"""Fonts for titles, captions and credits: a curated catalog of open-licensed families, resolution with offline
fallback, script detection and mixed-script text.

    from codecinema import typography
    typography.find("Lilita One")                                  # -> Face (a file, a face index, a weight)
    faces = typography.stack(["Lilita One"], role="title", text="Nian · 年", lang="Chinese")
    typography.runs("Nian · 年", faces)                            # -> [("Nian · ", Lilita One), ("年", ZCOOL KuaiLe)]
    typography.writing_systems("映画 Pebble")                       # -> ["zh-Hans", "latin"] ("ja" with lang="ja")

Families are found bundled, then in the user's and the system's font folders, then in the download cache, and are
downloaded on first use (pinned files, SHA-256 checked); see codecinema library fonts. Drawing helpers live in
typography.draw (PIL) and typography.shaping (skia); the specimen sheet in typography.sheet.
"""
from codecinema.typography.catalog import (CATEGORIES, COMMIT, FAMILIES, LICENSES, ROLES, SAMPLES, SCRIPTS, Family,
                                           File, families, family, role_families)
from codecinema.typography.resolve import (Face, FontError, FontUnavailable, UnknownFont, check, clear,
                                           downloads_enabled, fetch, find, license_path, mirrors, select, stack, status)
from codecinema.typography.scripts import itemize, language_system, script_of, writing_systems
from codecinema.typography.text import runs

__all__ = ["CATEGORIES", "COMMIT", "FAMILIES", "LICENSES", "ROLES", "SAMPLES", "SCRIPTS", "Face", "Family", "File",
           "FontError", "FontUnavailable", "UnknownFont", "check", "clear", "downloads_enabled", "families", "family",
           "fetch", "find", "itemize", "language_system", "license_path", "mirrors", "role_families", "runs",
           "script_of", "select", "stack", "status", "writing_systems"]
