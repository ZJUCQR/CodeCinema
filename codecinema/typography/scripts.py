"""Unicode scripts and writing systems for choosing fonts (standard library only).

    script_of("年")                        # "Han"; "Common" for spaces, digits and punctuation, "Inherited" for marks
    itemize("Nian · 年")                   # [("Nian · ", "Latin"), ("年", "Han")]
    writing_systems("Nian · 年")           # ["zh-Hans", "latin"]: what a font stack needs, most specific first
    writing_systems("年", lang="ja")       # ["ja"]: Han-only text follows the film or line language
    language_system("Japanese")            # "ja"

Han characters belong to Japanese text when kana appear, otherwise to the given language (Chinese, Japanese,
Korean, Traditional Chinese), defaulting to Simplified Chinese.
"""
import bisect
import unicodedata

_RANGES = sorted([
    (0x0041, 0x005A, "Latin"), (0x0061, 0x007A, "Latin"), (0x00AA, 0x00AA, "Latin"), (0x00BA, 0x00BA, "Latin"),
    (0x00C0, 0x00D6, "Latin"), (0x00D8, 0x00F6, "Latin"), (0x00F8, 0x02AF, "Latin"), (0x0300, 0x036F, "Inherited"),
    (0x0370, 0x03FF, "Greek"), (0x0400, 0x052F, "Cyrillic"), (0x0530, 0x058F, "Armenian"), (0x0590, 0x05FF, "Hebrew"),
    (0x0600, 0x06FF, "Arabic"), (0x0700, 0x074F, "Syriac"), (0x0750, 0x077F, "Arabic"), (0x0780, 0x07BF, "Thaana"),
    (0x0870, 0x08FF, "Arabic"), (0x0900, 0x097F, "Devanagari"), (0x0980, 0x09FF, "Bengali"),
    (0x0A00, 0x0A7F, "Gurmukhi"), (0x0A80, 0x0AFF, "Gujarati"), (0x0B00, 0x0B7F, "Oriya"), (0x0B80, 0x0BFF, "Tamil"),
    (0x0C00, 0x0C7F, "Telugu"), (0x0C80, 0x0CFF, "Kannada"), (0x0D00, 0x0D7F, "Malayalam"),
    (0x0D80, 0x0DFF, "Sinhala"), (0x0E00, 0x0E7F, "Thai"), (0x0E80, 0x0EFF, "Lao"), (0x0F00, 0x0FFF, "Tibetan"),
    (0x1000, 0x109F, "Myanmar"), (0x10A0, 0x10FF, "Georgian"), (0x1100, 0x11FF, "Hangul"),
    (0x1200, 0x139F, "Ethiopic"), (0x1780, 0x17FF, "Khmer"), (0x1800, 0x18AF, "Mongolian"),
    (0x1AB0, 0x1AFF, "Inherited"), (0x1C80, 0x1C8F, "Cyrillic"), (0x1D00, 0x1D7F, "Latin"),
    (0x1DC0, 0x1DFF, "Inherited"), (0x1E00, 0x1EFF, "Latin"), (0x1F00, 0x1FFF, "Greek"), (0x200C, 0x200D, "Inherited"),
    (0x20D0, 0x20FF, "Inherited"), (0x2C60, 0x2C7F, "Latin"), (0x2D00, 0x2D2F, "Georgian"),
    (0x2DE0, 0x2DFF, "Cyrillic"), (0x2E80, 0x2FDF, "Han"), (0x3005, 0x3005, "Han"), (0x3007, 0x3007, "Han"),
    (0x3021, 0x3029, "Han"), (0x3038, 0x303B, "Han"), (0x3041, 0x3096, "Hiragana"), (0x3099, 0x309A, "Inherited"),
    (0x309D, 0x309F, "Hiragana"), (0x30A1, 0x30FA, "Katakana"), (0x30FD, 0x30FF, "Katakana"),
    (0x3105, 0x312F, "Bopomofo"), (0x3131, 0x318E, "Hangul"), (0x31A0, 0x31BF, "Bopomofo"),
    (0x31F0, 0x31FF, "Katakana"), (0x32D0, 0x32FE, "Katakana"), (0x3400, 0x4DBF, "Han"), (0x4E00, 0x9FFF, "Han"),
    (0xA640, 0xA69F, "Cyrillic"), (0xA720, 0xA7FF, "Latin"), (0xA8E0, 0xA8FF, "Devanagari"),
    (0xA960, 0xA97F, "Hangul"), (0xAB30, 0xAB6F, "Latin"), (0xAC00, 0xD7FF, "Hangul"), (0xF900, 0xFAFF, "Han"),
    (0xFB00, 0xFB06, "Latin"), (0xFB13, 0xFB17, "Armenian"), (0xFB1D, 0xFB4F, "Hebrew"), (0xFB50, 0xFDFF, "Arabic"),
    (0xFE00, 0xFE0F, "Inherited"), (0xFE20, 0xFE2F, "Inherited"), (0xFE70, 0xFEFF, "Arabic"),
    (0xFF21, 0xFF3A, "Latin"), (0xFF41, 0xFF5A, "Latin"), (0xFF66, 0xFF6F, "Katakana"), (0xFF71, 0xFF9D, "Katakana"),
    (0xFFA0, 0xFFDC, "Hangul"), (0x1B000, 0x1B16F, "Hiragana"), (0x20000, 0x323AF, "Han"),
    (0xE0100, 0xE01EF, "Inherited"),
])
_STARTS = [start for start, _, _ in _RANGES]
# CJK punctuation, symbols and full-width forms: script Common, but drawn by CJK fonts.
_CJK_COMMON = ((0x3000, 0x303F), (0x30FB, 0x30FC), (0x3200, 0x33FF), (0xFE30, 0xFE4F), (0xFF01, 0xFF20),
               (0xFF3B, 0xFF40), (0xFF5B, 0xFF65))
COMPLEX = {"Arabic", "Hebrew", "Syriac", "Thaana", "Devanagari", "Bengali", "Gurmukhi", "Gujarati", "Oriya", "Tamil",
           "Telugu", "Kannada", "Malayalam", "Sinhala", "Thai", "Lao", "Tibetan", "Myanmar", "Khmer", "Mongolian"}
RTL = {"Arabic", "Hebrew", "Syriac", "Thaana"}
_HAN = {"Han", "Hiragana", "Katakana", "Bopomofo"}
_PRIORITY = {"zh-Hans": 0, "zh-Hant": 0, "ja": 0, "ko": 0, "arabic": 1, "hebrew": 1, "devanagari": 1, "thai": 1,
             "greek": 3, "cyrillic": 3, "vietnamese": 4, "latin-ext": 5, "latin": 6}
_LANGUAGES = {
    "ja": ("ja", "jp", "jpn", "japanese", "日本語"),
    "ko": ("ko", "kr", "kor", "korean", "한국어", "조선어"),
    "zh-Hant": ("zh-hant", "zh-tw", "zh-hk", "zh-mo", "yue", "cantonese", "traditional chinese", "繁體中文", "粵語"),
    "zh-Hans": ("zh", "zh-hans", "zh-cn", "zh-sg", "cmn", "chinese", "mandarin", "simplified chinese", "中文", "汉语",
                "普通话"),
    "arabic": ("ar", "fa", "ur", "arabic", "persian", "farsi", "urdu"),
    "hebrew": ("he", "iw", "yi", "hebrew", "yiddish"),
    "devanagari": ("hi", "mr", "ne", "sa", "hindi", "marathi", "nepali", "sanskrit"),
    "thai": ("th", "thai"),
    "cyrillic": ("ru", "uk", "be", "bg", "sr", "mk", "kk", "mn", "russian", "ukrainian", "belarusian", "bulgarian",
                 "serbian", "macedonian", "kazakh"),
    "greek": ("el", "greek"),
    "vietnamese": ("vi", "vietnamese"),
    "latin": ("en", "fr", "de", "es", "it", "pt", "nl", "sv", "da", "no", "nb", "fi", "pl", "cs", "tr", "id", "ms",
              "english", "french", "german", "spanish", "italian", "portuguese", "dutch", "polish", "turkish"),
}
_BY_LANGUAGE = {name: system for system, names in _LANGUAGES.items() for name in names}


def script_of(ch):
    """The Unicode script of one character (by block): "Latin", "Han", "Hangul", ..., "Common" or "Inherited"."""
    cp = ord(ch)
    i = bisect.bisect_right(_STARTS, cp) - 1
    if i >= 0 and cp <= _RANGES[i][1]:
        return _RANGES[i][2]
    return "Inherited" if unicodedata.category(ch) in ("Mn", "Me") else "Common"


def cjk_common(ch):
    """True for CJK punctuation, symbols and full-width forms."""
    cp = ord(ch)
    return any(a <= cp <= b for a, b in _CJK_COMMON)


def itemize(text):
    """Split text into (segment, script) runs; spaces, punctuation and marks join the surrounding script."""
    scripts = [script_of(ch) for ch in text]
    strong = [s if s not in ("Common", "Inherited") else None for s in scripts]
    last = next((s for s in strong if s), "Common")
    resolved = []
    for s in strong:
        last = s or last
        resolved.append(last)
    out = []
    for ch, s in zip(text, resolved):
        if out and out[-1][1] == s:
            out[-1][0] += ch
        else:
            out.append([ch, s])
    return [(segment, s) for segment, s in out]


def language_system(lang):
    """The writing system of a language name or tag ("ja", "Japanese", "zh-TW", "Chinese" ...), or None."""
    if not lang:
        return None
    text = str(lang).strip().lower().replace("_", "-")
    if text in _BY_LANGUAGE:
        return _BY_LANGUAGE[text]
    if text.startswith(("zh-hant", "zh-tw", "zh-hk", "zh-mo")):
        return "zh-Hant"
    return _BY_LANGUAGE.get(text.split("-")[0])


def han_system(text, lang=None):
    """The writing system of Han characters in `text`: ja with kana, else the language's, else zh-Hans."""
    scripts = {script_of(ch) for ch in text}
    if scripts & {"Hiragana", "Katakana"}:
        return "ja"
    system = language_system(lang)
    if system in ("ja", "ko", "zh-Hans", "zh-Hant"):
        return system
    if "Hangul" in scripts:
        return "ko"
    if "Bopomofo" in scripts:
        return "zh-Hant"
    return "zh-Hans"


def system_of(ch, han="zh-Hans"):
    """The writing system one character needs from a font, or None for spaces, digits, punctuation and marks."""
    script = script_of(ch)
    cp = ord(ch)
    if script == "Latin":
        if 0xFF21 <= cp <= 0xFF5A:
            return han
        if cp < 0x100:
            return "latin"
        if 0x1EA0 <= cp <= 0x1EF9 or cp in (0x01A0, 0x01A1, 0x01AF, 0x01B0):
            return "vietnamese"
        return "latin-ext"
    if script in ("Han", "Bopomofo"):
        return "zh-Hant" if script == "Bopomofo" else han
    if script in ("Hiragana", "Katakana"):
        return "ja"
    if script == "Hangul":
        return "ko"
    if script in ("Common", "Inherited"):
        return han if cjk_common(ch) else None
    return script.lower()


def assign(text, lang=None, context=None):
    """{character: writing system} for the characters of `text` that need one."""
    han = han_system(context or text, lang)
    out = {}
    for ch in text:
        if ch not in out:
            system = system_of(ch, han)
            if system:
                out[ch] = system
    return out


def writing_systems(text, lang=None, context=None):
    """Writing systems in `text`, most specific first (CJK, other scripts, then Latin variants)."""
    found = list(dict.fromkeys(assign(text, lang, context).values()))
    return sorted(found, key=lambda s: _PRIORITY.get(s, 2))


def complex_text(text):
    """True when text needs shaping or right-to-left layout (Arabic, Hebrew, Indic, Thai ...)."""
    return any(script_of(ch) in COMPLEX for ch in text)


def rtl(text):
    """True when the first strongly directional character is right-to-left."""
    for ch in text:
        script = script_of(ch)
        if script in RTL:
            return True
        if script not in ("Common", "Inherited") or unicodedata.bidirectional(ch) == "L":
            return False
    return False
