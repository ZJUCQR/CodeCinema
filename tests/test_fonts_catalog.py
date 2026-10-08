"""Font catalog integrity: ids, scripts, categories, licenses, pinned sources and the bundled files."""
import hashlib
import re
from collections import Counter

import pytest

from codecinema import typography
from codecinema.typography import catalog, index, resolve
from codecinema.workspace.paths import resource_dir

HEX40 = re.compile(r"[0-9a-f]{40}")


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("CODECINEMA_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("CODECINEMA_FONTS_DOWNLOAD", "off")
    monkeypatch.delenv("CODECINEMA_FONTS_MIRROR", raising=False)
    monkeypatch.setattr(index, "folders", lambda: [(resource_dir("fonts"), "bundled")])
    typography.clear()
    yield
    typography.clear()


def test_ids_names_and_aliases_are_unique():
    ids = [f.id for f in catalog.FAMILIES]
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", i) for i in ids)
    keys = Counter(k for f in catalog.FAMILIES for k in {catalog.key(n) for n in (f.id, f.name, *f.aliases)})
    assert [k for k, n in keys.items() if n > 1] == []


def test_fields_are_valid():
    for fam in catalog.FAMILIES:
        assert fam.category in catalog.CATEGORIES, fam.id
        assert fam.scripts and set(fam.scripts) <= set(catalog.SCRIPTS), fam.id
        assert len(set(fam.scripts)) == len(fam.scripts), fam.id
        assert fam.license in catalog.LICENSES, fam.id
        assert fam.designer.strip(), fam.id
        assert fam.source in catalog.SOURCES, fam.id
        assert fam.files, fam.id
        assert fam.license_file is not None or fam.notice.startswith("Copyright"), fam.id
        if fam.license_file:
            assert fam.license_file.name in ("OFL.txt", "LICENSE.txt")
            assert (fam.license_file.name == "OFL.txt") == (fam.license == "OFL-1.1")
        for file in (*fam.files, *([fam.license_file] if fam.license_file else [])):
            assert re.fullmatch(r"[0-9a-f]{64}", file.sha256), (fam.id, file.name)
            assert file.size > 0
        for file in fam.files:
            lo, hi = file.weights
            assert 100 <= lo <= hi <= 1000 and file.style in ("normal", "italic"), (fam.id, file.name)
            assert file.name.endswith((".ttf", ".otf"))


def test_download_addresses_are_https_and_pinned():
    for repo, commit, templates in catalog.SOURCES.values():
        assert HEX40.fullmatch(commit) and all(t.startswith("https://") for t in templates)
    for fam in catalog.FAMILIES:
        commit = catalog.SOURCES[fam.source][1]
        for file in (*fam.files, *([fam.license_file] if fam.license_file else [])):
            urls = fam.urls(file)
            assert len(urls) == len(catalog.SOURCES[fam.source][2]) - (fam.source == "lxgw" and file not in fam.files)
            assert all(u.startswith("https://") for u in urls)
            assert commit in urls[0] and "[" not in urls[0] and " " not in urls[0]
    assert catalog.family("inter").urls(catalog.family("inter").files[0])[0] == (
        f"https://raw.githubusercontent.com/google/fonts/{catalog.COMMIT}/ofl/inter/Inter%5Bopsz%2Cwght%5D.ttf")


def test_mirror_templates_come_first():
    fam = catalog.family("lilita-one")
    urls = fam.urls(fam.files[0], ("https://proxy.example/{url}", "file:///srv/google-fonts"))
    assert urls[0] == "https://proxy.example/" + fam.urls(fam.files[0])[0]
    assert urls[1] == "file:///srv/google-fonts/ofl/lilitaone/LilitaOne-Regular.ttf"
    assert urls[2:] == fam.urls(fam.files[0])


def test_coverage_of_writing_systems():
    main = Counter(f.script for f in catalog.FAMILIES)
    assert main["latin"] >= 20 and main["zh-Hans"] >= 8 and main["zh-Hant"] >= 3
    assert main["ja"] >= 8 and main["ko"] >= 8
    for system in ("arabic", "devanagari", "thai", "hebrew"):
        assert catalog.family(f"Noto Sans {system.title()}").script == system
    for name in ("Inter", "Nunito", "Baloo 2", "Lilita One", "Bangers", "Luckiest Guy", "Chewy", "Comic Neue",
                 "Patrick Hand", "Caveat", "Pacifico", "Lobster", "Permanent Marker", "Playfair Display", "Lora",
                 "EB Garamond", "Cinzel", "Oswald", "Press Start 2P", "JetBrains Mono", "ZCOOL XiaoWei",
                 "ZCOOL QingKe HuangYou", "Ma Shan Zheng", "Zhi Mang Xing", "Liu Jian Mao Cao", "Long Cang",
                 "Noto Sans SC", "Noto Serif SC", "LXGW WenKai", "Noto Sans TC", "Noto Serif TC", "LXGW WenKai TC",
                 "Noto Sans JP", "Noto Serif JP", "M PLUS Rounded 1c", "Zen Maru Gothic", "Kosugi Maru",
                 "Yusei Magic", "Dela Gothic One", "RocknRoll One", "Klee One", "Hachi Maru Pop", "Shippori Mincho",
                 "Yuji Syuku", "Noto Sans KR", "Noto Serif KR", "Jua", "Do Hyeon", "Black Han Sans", "Gaegu",
                 "Nanum Pen Script", "Gowun Dodum", "Gamja Flower", "Sunflower", "Dongle"):
        assert catalog.family(name), name


def test_bundled_fonts_match_the_catalog_bytes():
    for fid in ("fredoka", "zcool-kuaile"):
        fam = catalog.family(fid)
        assert resolve.status(fam) == "bundled"
        for shipped, original in fam.bundled:
            file = fam.license_file if original == fam.license_file.name else \
                next(f for f in fam.files if f.name == original)
            path = resolve.bundled_path(fam, original)
            assert path is not None and path.name == shipped
            data = path.read_bytes()
            if path.suffix == ".txt":           # a checkout may turn the license's line ends into CRLF
                data = data.replace(b"\r\n", b"\n")
            assert hashlib.sha256(data).hexdigest() == file.sha256 and len(data) == file.size


def test_lookup_is_case_and_space_insensitive_and_suggests():
    assert catalog.family("ZCOOL KuaiLe") is catalog.family("zcool-kuaile") is catalog.family("zcoolkuaile")
    assert catalog.family("rounded mplus 1c").id == "m-plus-rounded-1c"          # the name inside the font files
    assert catalog.family("Lilta One") is None
    assert catalog.suggestions("Lilta One")[0] == "Lilita One"
    with pytest.raises(typography.UnknownFont, match="Did you mean: Lilita One"):
        typography.find("Lilta One")


def test_roles_name_catalog_families_that_cover_their_system():
    for role, table in catalog.ROLES.items():
        for system, ids in table.items():
            for fid in ids:
                fam = catalog.family(fid)
                assert fam is not None and fam.id == fid, (role, fid)
                assert system in fam.scripts, (role, system, fid)
    assert catalog.role_families("title", "latin")[0] == "fredoka"
    assert catalog.role_families("title", "zh-Hans")[0] == "zcool-kuaile"
    assert catalog.role_families("credits", "cyrillic")[0] == "nunito"
    assert catalog.role_families("ui", "ja")[0] == catalog.SYSTEM["ja"][0]


def test_select_families_by_name_system_language_category():
    assert [f.id for f in typography.select("Lilita One")] == ["lilita-one"]
    assert {f.script for f in typography.select("ja")} == {"ja"}
    assert typography.select("Japanese") == typography.select("ja")
    assert {f.script for f in typography.select("traditional chinese")} == {"zh-Hant"}
    assert {f.category for f in typography.select("pixel")} == {"pixel"}
    assert len(typography.select("all")) == len(catalog.FAMILIES)
    with pytest.raises(typography.UnknownFont):
        typography.select("klingon-sans")
