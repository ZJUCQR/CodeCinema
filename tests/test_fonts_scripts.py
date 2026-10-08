"""Script detection, writing systems and mixed-script run segmentation."""
import pytest

from codecinema import typography
from codecinema.typography import index, scripts
from codecinema.typography.text import runs, tokens
from codecinema.workspace.paths import resource_dir


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("CODECINEMA_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("CODECINEMA_FONTS_DOWNLOAD", "off")
    monkeypatch.setattr(index, "folders", lambda: [(resource_dir("fonts"), "bundled")])
    typography.clear()
    yield
    typography.clear()


@pytest.mark.parametrize("ch, script", [
    ("A", "Latin"), ("é", "Latin"), ("Ł", "Latin"), ("ạ", "Latin"), ("Ж", "Cyrillic"), ("Ω", "Greek"),
    ("年", "Han"), ("𠀋", "Han"), ("々", "Han"), ("あ", "Hiragana"), ("カ", "Katakana"), ("ｶ", "Katakana"),
    ("ㄅ", "Bopomofo"), ("한", "Hangul"), ("ㄱ", "Hangul"), ("م", "Arabic"), ("ﻣ", "Arabic"), ("ש", "Hebrew"),
    ("क", "Devanagari"), ("ก", "Thai"), ("ক", "Bengali"), ("ა", "Georgian"), (" ", "Common"), ("7", "Common"),
    ("·", "Common"), ("、", "Common"), ("ー", "Common"), ("\u0301", "Inherited"), ("\u200d", "Inherited"),
    ("\u3099", "Inherited"), ("\ufe0f", "Inherited"),
])
def test_script_of(ch, script):
    assert scripts.script_of(ch) == script


def test_itemize_joins_neutral_characters_to_their_neighbours():
    assert scripts.itemize("Nian · 年") == [("Nian · ", "Latin"), ("年", "Han")]
    assert scripts.itemize("«Привет», Pebble!") == [("«Привет», ", "Cyrillic"), ("Pebble!", "Latin")]
    assert scripts.itemize("") == []


@pytest.mark.parametrize("text, lang, systems", [
    ("Pebble", None, ["latin"]),
    ("Nian · 年", None, ["zh-Hans", "latin"]),
    ("年", "Japanese", ["ja"]),
    ("年", "zh-TW", ["zh-Hant"]),
    ("年", "ko", ["ko"]),
    ("映画 Pebble", None, ["zh-Hans", "latin"]),
    ("映画 Pebble", "ja", ["ja", "latin"]),
    ("ペンギンのPebble", None, ["ja", "latin"]),
    ("映画はペンギン", "Chinese", ["ja"]),                 # kana make Han Japanese whatever the film language
    ("한국어 漢字", None, ["ko"]),
    ("注音 ㄅㄆㄇ", None, ["zh-Hant"]),
    ("Łódź, Kraków", None, ["latin-ext", "latin"]),
    ("Tiếng Việt", None, ["vietnamese", "latin"]),
    ("Привет, Pebble", None, ["cyrillic", "latin"]),
    ("مرحبا Pebble", None, ["arabic", "latin"]),
    ("「」", None, ["zh-Hans"]),                          # CJK punctuation is drawn by CJK fonts
    ("2024!", None, []),
])
def test_writing_systems(text, lang, systems):
    assert scripts.writing_systems(text, lang) == systems


@pytest.mark.parametrize("lang, system", [
    ("ja", "ja"), ("Japanese", "ja"), ("日本語", "ja"), ("ko-KR", "ko"), ("Korean", "ko"), ("zh", "zh-Hans"),
    ("zh-CN", "zh-Hans"), ("Mandarin", "zh-Hans"), ("Chinese", "zh-Hans"), ("zh_TW", "zh-Hant"),
    ("zh-Hant-HK", "zh-Hant"), ("Cantonese", "zh-Hant"), ("ar", "arabic"), ("he", "hebrew"), ("hi", "devanagari"),
    ("th", "thai"), ("ru", "cyrillic"), ("English", "latin"), ("fr-CA", "latin"), ("vi", "vietnamese"),
    (None, None), ("", None), ("Klingon", None),
])
def test_language_system(lang, system):
    assert scripts.language_system(lang) == system


def test_complex_and_right_to_left_detection():
    assert scripts.complex_text("مرحبا") and scripts.complex_text("नमस\u094dत\u0947") and scripts.complex_text("สว\u0e31สด\u0e35")
    assert not scripts.complex_text("Pebble 年 한국어")
    assert scripts.rtl("  «שלום» Pebble") and scripts.rtl("123 مرحبا")
    assert not scripts.rtl("Pebble مرحبا") and not scripts.rtl("")


class Fake:
    """A face covering a fixed set of characters (runs() only asks faces whether they cover text)."""

    def __init__(self, name, chars):
        self.name, self.chars = name, set(chars)

    def covers(self, text):
        return all(ch in self.chars or ch in "\u200d\ufe0f" for ch in text)

    def __repr__(self):
        return self.name


LATIN = Fake("latin", "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,!?·'éó\u0301")
WIDE = Fake("wide", LATIN.chars | set("ŁłŹź"))
CJK = Fake("cjk", "年完的故事映画はのペンギン一 ·、。「」" + "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")


def test_runs_switch_fonts_where_the_first_lacks_glyphs():
    assert runs("Nian · 年", [LATIN, CJK]) == [("Nian · ", LATIN), ("年", CJK)]
    assert runs("年 · 完", [LATIN, CJK]) == [("年 · 完", CJK)]          # punctuation stays with the text around it
    assert runs("Nian · 年", [CJK, LATIN]) == [("Nian · 年", CJK)]       # a CJK font that covers Latin draws all
    assert runs("「年」Nian", [LATIN, CJK]) == [("「年」", CJK), ("Nian", LATIN)]
    assert runs("ペンギンのPebble", [LATIN, CJK]) == [("ペンギンの", CJK), ("Pebble", LATIN)]


def test_words_keep_one_font_and_marks_stay_with_their_letter():
    assert runs("Łódź is far", [LATIN, WIDE]) == [("Łódź ", WIDE), ("is far", LATIN)]
    assert runs("Cafe\u0301 ok", [LATIN, CJK]) == [("Cafe\u0301 ok", LATIN)]
    assert [t[0] for t in tokens("e\u0301a 年年")] == ["e\u0301a", " ", "年", "年"]


def test_characters_no_font_covers_use_the_first_font():
    assert runs("Hi ☃", [LATIN, CJK]) == [("Hi ☃", LATIN)]
    assert runs("☃年", [LATIN, CJK]) == [("☃", LATIN), ("年", CJK)]
    assert runs("", [LATIN]) == [] and runs("abc", []) == [("abc", None)]


def test_runs_with_the_bundled_fonts():
    fredoka, zcool = typography.find("Fredoka", 650), typography.find("ZCOOL KuaiLe")
    assert fredoka.covers("Pebble · The End") and not fredoka.covers("年")
    assert zcool.covers("年 · 完") and zcool.covers("用 CodeCinema 编写、搭景、配乐与配音")
    assert typography.runs("Nian · 年", [fredoka, zcool]) == [("Nian · ", fredoka), ("年", zcool)]
