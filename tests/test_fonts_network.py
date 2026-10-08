"""Live checks of the pinned font sources. Skipped unless CODECINEMA_NETWORK_TESTS is set:

    CODECINEMA_NETWORK_TESTS=1 pytest tests/test_fonts_network.py      # small downloads through every mirror
    CODECINEMA_NETWORK_TESTS=all pytest tests/test_fonts_network.py    # also every catalog file (about 500 MB)
"""
import os

import pytest

from codecinema import typography
from codecinema.runtime import downloads
from codecinema.typography import catalog

MODE = os.environ.get("CODECINEMA_NETWORK_TESTS", "").strip().lower()
pytestmark = pytest.mark.skipif(not MODE or MODE in ("0", "no", "off"), reason="set CODECINEMA_NETWORK_TESTS=1")


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("CODECINEMA_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("CODECINEMA_FONTS_DOWNLOAD", "auto")
    monkeypatch.delenv("CODECINEMA_FONTS_MIRROR", raising=False)
    monkeypatch.delenv("CODECINEMA_OFFLINE", raising=False)
    typography.clear()
    yield
    typography.clear()


@pytest.mark.parametrize("source", sorted(catalog.SOURCES))
def test_every_mirror_serves_the_pinned_bytes(source):
    fam = next(f for f in catalog.FAMILIES if f.source == source)
    file = fam.license_file                                  # small, and on every mirror of the repository
    for i, url in enumerate(fam.urls(file)):
        path = downloads.cached(f"probe/{source}-{i}-{file.name}", url, file.sha256, file.size, quiet=True)
        assert downloads.sha256_file(path) == file.sha256


def test_a_family_downloads_with_its_license_on_first_use():
    face = typography.find("Lilita One", 400)
    assert face.source == "cache" and typography.status(typography.family("lilita-one")) == "cached"
    assert typography.license_path(typography.family("lilita-one")).is_file()


@pytest.mark.skipif(MODE != "all", reason="set CODECINEMA_NETWORK_TESTS=all to verify every catalog file")
def test_every_catalog_file_matches_its_checksum():
    failed = []
    for fam in catalog.FAMILIES:
        try:
            typography.fetch(fam, quiet=True)
        except downloads.DownloadError as exc:
            failed.append(f"{fam.id}: {exc}")
    assert failed == []
