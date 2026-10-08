"""Font resolution order (bundled, user, system, cache, download), offline fallback, mirrors and verified downloads.

The network is disabled for every test here: only file:// addresses (local mirrors) can be fetched.
"""
import json
import shutil
import urllib.error
import urllib.request

import pytest
from fontTools.ttLib import TTFont

from codecinema import typography
from codecinema.runtime import downloads
from codecinema.typography import catalog, index
from codecinema.workspace import settings
from codecinema.workspace.paths import resource_dir

BUNDLED = resource_dir("fonts")


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("CODECINEMA_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("CODECINEMA_FONTS_DOWNLOAD", "off")
    for name in ("CODECINEMA_FONTS_MIRROR", "CODECINEMA_OFFLINE"):
        monkeypatch.delenv(name, raising=False)
    real = urllib.request.urlopen

    def local_only(request, *args, **kwargs):
        url = getattr(request, "full_url", request)
        if not str(url).startswith("file:"):
            raise urllib.error.URLError("network disabled in tests")
        return real(request, *args, **kwargs)

    monkeypatch.setattr(urllib.request, "urlopen", local_only)
    user, system = tmp_path / "user-fonts", tmp_path / "system-fonts"
    user.mkdir()
    system.mkdir()
    monkeypatch.setattr(index, "folders", lambda: [(BUNDLED, "bundled"), (user, "user"), (system, "system")])
    typography.clear()
    yield user, system
    typography.clear()


def renamed(source, target, family, codepages=None, kana=False):
    """Copy a bundled font under another family name: an offline stand-in for an installed or catalog font.
    `kana` maps hiragana and katakana to an existing glyph, so the copy covers Japanese text."""
    font = TTFont(source)
    if kana:
        for table in font["cmap"].tables:
            if table.isUnicode():
                glyph = table.cmap[ord("人")]
                table.cmap.update({cp: glyph for cp in range(0x3041, 0x30FF)})
    names = font["name"]
    for name_id in (1, 4, 6, 16, 17, 21):
        names.removeNames(nameID=name_id)
    names.setName(family, 1, 3, 1, 0x409)
    names.setName(family, 16, 3, 1, 0x409)
    names.setName(family + " Regular", 4, 3, 1, 0x409)
    names.setName(family.replace(" ", "") + "-Regular", 6, 3, 1, 0x409)
    if codepages is not None:
        font["OS/2"].ulCodePageRange1 = codepages
    target.parent.mkdir(parents=True, exist_ok=True)
    font.save(target)
    return target


@pytest.fixture
def testa(tmp_path, monkeypatch):
    """A catalog family "Testa Sans" (a renamed Fredoka) and a local mirror that serves it."""
    mirror = tmp_path / "mirror"
    folder = mirror / "ofl" / "testasans"
    font = renamed(BUNDLED / "Fredoka.ttf", folder / "TestaSans[wdth,wght].ttf", "Testa Sans")
    license_text = folder / "OFL.txt"
    shutil.copy(BUNDLED / "OFL-Fredoka.txt", license_text)
    fam = catalog.Family(
        "testa-sans", "Testa Sans", "rounded", ("latin",), "ofl/testasans", "Tests",
        files=(catalog.File(font.name, font.stat().st_size, downloads.sha256_file(font), (300, 700)),),
        license_file=catalog.File("OFL.txt", license_text.stat().st_size, downloads.sha256_file(license_text)))
    monkeypatch.setattr(catalog, "FAMILIES", catalog.FAMILIES + (fam,))
    monkeypatch.setitem(catalog._BY_KEY, "testasans", fam)
    return fam, mirror


def online(monkeypatch, *mirrors):
    monkeypatch.setenv("CODECINEMA_FONTS_DOWNLOAD", "auto")
    monkeypatch.setenv("CODECINEMA_FONTS_MIRROR", " ".join(m.as_uri() for m in mirrors))
    typography.clear()


def test_bundled_fonts_come_before_installed_copies(isolated):
    user, _system = isolated
    shutil.copy(BUNDLED / "Fredoka.ttf", user / "MyFredoka.ttf")
    face = typography.find("fredoka", 650)
    assert face.source == "bundled" and face.path.endswith("Fredoka.ttf") and face.coordinates() == [650.0, 100.0]
    assert typography.find("ZCOOL KuaiLe").source == "bundled"


def test_user_fonts_come_before_system_fonts(isolated):
    user, system = isolated
    renamed(BUNDLED / "Fredoka.ttf", system / "Testa.ttf", "Testa Sans")
    renamed(BUNDLED / "Fredoka.ttf", user / "Testa.ttf", "Testa Sans")
    face = typography.find("testa sans", 500)
    assert face.source == "user" and face.path == str(user / "Testa.ttf") and face.weight == 500
    assert [f["kind"] for f in index.lookup("Testa Sans")] == ["user", "system"]
    store = json.loads((downloads.cache_root() / "fonts" / "installed.json").read_text(encoding="utf-8"))
    assert store["version"] == index.VERSION and str(user / "Testa.ttf") in store["files"]


def test_catalog_family_order_installed_cache_download(isolated, testa, monkeypatch, capsys):
    user, _system = isolated
    fam, mirror = testa
    assert typography.status(fam) == "downloadable"
    with pytest.raises(typography.FontUnavailable, match="--download testa-sans"):
        typography.find("Testa Sans")
    online(monkeypatch, mirror)
    face = typography.find("Testa Sans", 650)
    cached = downloads.cache_root() / "fonts" / "testa-sans"
    assert face.source == "cache" and face.path == str(cached / fam.files[0].name) and face.weight == 650
    assert (cached / "OFL.txt").read_text(encoding="utf-8").startswith("Copyright")
    assert typography.license_path(fam) == cached / "OFL.txt"
    assert "Downloading font Testa Sans (OFL-1.1)" in capsys.readouterr().err
    assert typography.status(fam) == "cached"
    shutil.rmtree(mirror)
    typography.clear()
    assert typography.find("Testa Sans").source == "cache"                # no mirror needed any more
    renamed(BUNDLED / "Fredoka.ttf", user / "Testa.ttf", "Testa Sans")
    typography.clear()
    assert typography.find("Testa Sans").source == "user"                 # installed fonts win over the cache
    assert typography.status(fam) == "installed"


def test_a_bad_mirror_falls_through_to_the_next(testa, tmp_path, monkeypatch, capsys):
    fam, mirror = testa
    bad = tmp_path / "bad"
    shutil.copytree(mirror, bad)
    damaged = bad / "ofl" / "testasans" / fam.files[0].name
    data = bytearray(damaged.read_bytes())
    data[1000] ^= 0xFF                                  # same size, different bytes
    damaged.write_bytes(bytes(data))
    online(monkeypatch, bad, mirror)
    path = typography.fetch(fam)[0]
    assert downloads.sha256_file(path) == fam.files[0].sha256
    assert "failed its SHA-256 check" in capsys.readouterr().err


def test_without_network_every_address_is_reported(testa, monkeypatch):
    fam, _mirror = testa
    monkeypatch.setenv("CODECINEMA_FONTS_DOWNLOAD", "auto")
    with pytest.raises(downloads.DownloadError) as error:
        typography.fetch(fam)
    message = str(error.value)
    assert "any of 3 addresses" in message
    assert all(host in message for host in ("raw.githubusercontent.com", "cdn.jsdelivr.net", "fastly.jsdelivr.net"))


def test_offline_switch_blocks_downloads(testa, monkeypatch):
    fam, mirror = testa
    online(monkeypatch, mirror)
    monkeypatch.setenv("CODECINEMA_OFFLINE", "1")
    assert not typography.downloads_enabled()
    with pytest.raises(typography.FontUnavailable, match="downloads are off"):
        typography.find(fam.id)
    with pytest.raises(downloads.DownloadError, match="CODECINEMA_OFFLINE"):
        typography.fetch(fam)


def test_a_real_catalog_family_downloads_from_a_local_mirror(tmp_path, monkeypatch):
    fam = catalog.family("fredoka")
    folder = tmp_path / "google-fonts" / "ofl" / "fredoka"
    folder.mkdir(parents=True)
    shutil.copy(BUNDLED / "Fredoka.ttf", folder / "Fredoka[wdth,wght].ttf")
    (folder / "OFL.txt").write_bytes((BUNDLED / "OFL-Fredoka.txt").read_bytes().replace(b"\r\n", b"\n"))
    online(monkeypatch, tmp_path / "google-fonts")
    path = typography.fetch(fam)[0]
    assert path.name == "Fredoka[wdth,wght].ttf"
    assert downloads.is_cached("fonts/fredoka/" + path.name, fam.files[0].sha256)


def test_missing_fonts_fall_back_offline_with_a_note(capsys):
    faces = typography.stack(["Lilita One"], role="title", text="Hello 年", weight=650)
    assert [f.family for f in faces] == ["ZCOOL KuaiLe"]
    assert all(f.covers("Hello 年") for f in faces)
    assert "Lilita One is not installed or downloaded" in capsys.readouterr().err


def test_offline_script_fallback_uses_a_system_font_for_the_script(isolated):
    _user, system = isolated
    japan = 1 << 17                                     # OS/2 code page bit: JIS/Japan
    renamed(BUNDLED / "ZCOOLKuaiLe-Regular.ttf", system / "Gothic.ttf", "Test Gothic", codepages=japan, kana=True)
    typography.clear()
    faces = typography.stack(None, role="title", text="ペンギンのPebble", lang="ja", weight=650)
    assert [(f.family, f.source) for f in faces] == [("Test Gothic", "system")]     # it covers the Latin too
    typography.clear()
    (system / "Gothic.ttf").unlink()
    faces = typography.stack(None, role="title", text="ペンギンのPebble", lang="ja")
    assert [f.family for f in faces] == ["Fredoka"]          # nothing here draws kana: the Latin default leads


def test_defaults_follow_the_text_and_language():
    def first(text, lang=None):
        return typography.stack(None, role="title", text=text, lang=lang, weight=650)[0].family

    assert first("Pebble") == "Fredoka"
    assert first("年 · 完") == first("Nian · 年") == first("用 CodeCinema 编写") == "ZCOOL KuaiLe"
    assert first("") == "Fredoka"
    assert first("", lang="Chinese") == "ZCOOL KuaiLe"
    explicit = typography.stack(["Fredoka"], role="title", text="Nian · 年")
    assert [f.family for f in explicit] == ["Fredoka", "ZCOOL KuaiLe"]


def test_check_reports_unknown_names_and_missing_files():
    problems = typography.check(["Lilta One", "Fredoka", "fonts/missing.ttf", "zcool kuaile"])
    assert len(problems) == 2
    assert "Did you mean: Lilita One" in problems[0] and "missing.ttf" in problems[1]


def test_font_files_and_settings_accept_family_names(monkeypatch):
    face = typography.find(str(BUNDLED / "Fredoka.ttf"), 700)
    assert face.source == "file" and face.weight == 700 and face.coordinates() == [700.0, 100.0]
    monkeypatch.setitem(settings.SETTINGS["fonts"], "display_cjk", "ZCOOL KuaiLe")
    assert settings.font("display_cjk") == typography.find("zcool-kuaile").path
    monkeypatch.setitem(settings.SETTINGS["fonts"], "display", "Lilta One")
    with pytest.raises(typography.UnknownFont):
        settings.font("display")


def test_variable_weights_reach_pil_and_skia():
    from codecinema.typography import draw, shaping
    light, bold = typography.find("Fredoka", 100), typography.find("Fredoka", 900)
    assert light.weight == 300 and bold.weight == 700                     # clamped to the font's range
    assert draw.pil_font(light, 80).getlength("Pebble") != draw.pil_font(bold, 80).getlength("Pebble")
    if shaping.available():
        assert [c.value for c in shaping.typeface(bold).getVariationDesignPosition()] == [700.0, 100.0]


def test_cached_keeps_its_old_signature(tmp_path):
    source = tmp_path / "blob.bin"
    source.write_bytes(b"codecinema" * 1000)
    sha, size = downloads.sha256_file(source), source.stat().st_size
    path = downloads.cached("misc/blob.bin", source.as_uri(), sha, size)
    assert path.read_bytes() == source.read_bytes() and downloads.is_cached("misc/blob.bin", sha, size)
    source.unlink()
    assert downloads.cached("misc/blob.bin", source.as_uri(), sha, size) == path   # served from the cache
    with pytest.raises(downloads.DownloadError, match="place the file at"):
        downloads.cached("misc/other.bin", source.as_uri(), sha)
