"""The font catalog: open-licensed families pinned to exact files (standard library only).

Every downloadable file comes from github.com/google/fonts at COMMIT (LXGW WenKai from its designer's repository
at the commit of release v1.522), is tried through the mirrors in SOURCES and is verified by size and SHA-256, so a
font never changes under a film. Fredoka and ZCOOL KuaiLe also ship with CodeCinema and work offline.

    family("lilita one")         # -> Family by name, id or alias; case, spaces and hyphens are ignored
    families(script="ja")        # families whose main writing system is Japanese
    role_families("title", "ko") # default families of a role for a writing system, best first

Writing systems: latin, latin-ext, vietnamese, cyrillic, greek, zh-Hans, zh-Hant, ja, ko, arabic, devanagari,
thai, hebrew. A family's `scripts` lists the systems it covers (checked against its character map), main one first.
"""
import difflib
import re
from dataclasses import dataclass
from urllib.parse import quote

COMMIT = "2eb0b48d5f760f62e286216f0859a8c540dbc1bd"       # github.com/google/fonts, 2026-10-08
LXGW_COMMIT = "e8b5b48b79f19f29aa68b0a178eab3472ea9f7e8"  # github.com/lxgw/LxgwWenKai, release v1.522
# Download addresses per source, tried in order. {path} is the file's path in the repository (URL-encoded),
# {name} its file name. jsDelivr serves files up to 20 MB; larger ones fall through to the next address.
SOURCES = {
    "google": ("google/fonts", COMMIT, (
        "https://raw.githubusercontent.com/{repo}/{commit}/{path}",
        "https://cdn.jsdelivr.net/gh/{repo}@{commit}/{path}",
        "https://fastly.jsdelivr.net/gh/{repo}@{commit}/{path}")),
    "lxgw": ("lxgw/LxgwWenKai", LXGW_COMMIT, (
        "https://raw.githubusercontent.com/{repo}/{commit}/{path}",
        "https://github.com/{repo}/releases/download/v1.522/{name}",
        "https://cdn.jsdelivr.net/gh/{repo}@{commit}/{path}")),
}
SCRIPTS = {"latin": "Latin", "latin-ext": "Latin Extended", "vietnamese": "Vietnamese", "cyrillic": "Cyrillic",
           "greek": "Greek", "zh-Hans": "Simplified Chinese", "zh-Hant": "Traditional Chinese", "ja": "Japanese",
           "ko": "Korean", "arabic": "Arabic", "devanagari": "Devanagari", "thai": "Thai", "hebrew": "Hebrew"}
CATEGORIES = ("sans", "serif", "rounded", "display", "comic", "handwriting", "brush", "mono", "pixel")
LICENSES = {"OFL-1.1": "SIL Open Font License 1.1", "Apache-2.0": "Apache License 2.0"}
SAMPLES = {
    "latin": "Every film begins with a single frame.",
    "latin-ext": "Każdy film zaczyna się od jednej klatki.",
    "vietnamese": "Mỗi bộ phim bắt đầu từ một khung hình.",
    "cyrillic": "Каждый фильм начинается с одного кадра.",
    "greek": "Κάθε ταινία ξεκινά με ένα καρέ.",
    "zh-Hans": "每部电影都从一帧画面开始。",
    "zh-Hant": "每部電影都從一幀畫面開始。",
    "ja": "映画は一枚の絵から始まる。",
    "ko": "모든 영화는 한 장면에서 시작된다.",
    "arabic": "كل فيلم يبدأ بلقطة واحدة.",
    "devanagari": "हर फ़िल्म एक फ़्रेम से शुरू होती है।",
    "thai": "ภาพยนตร์ทุกเรื่องเริ่มต้นจากภาพเดียว",
    "hebrew": "כל סרט מתחיל בתמונה אחת.",
}


@dataclass(frozen=True)
class File:
    """One file of a family: a font (weight, or the range of a variable weight axis, and style) or a license."""
    name: str
    size: int
    sha256: str
    weight: int | tuple = 400
    style: str = "normal"

    @property
    def weights(self):
        """(lowest, highest) weight this file draws."""
        return tuple(self.weight) if isinstance(self.weight, tuple) else (self.weight, self.weight)


@dataclass(frozen=True)
class Family:
    id: str
    name: str
    category: str
    scripts: tuple
    folder: str                      # folder of the files in the source repository
    designer: str
    files: tuple = ()
    license: str = "OFL-1.1"         # SPDX identifier
    license_file: File | None = None
    notice: str = ""                 # copyright notice, for a folder without a license text
    source: str = "google"
    license_folder: str | None = None
    bundled: tuple = ()              # (file shipped with CodeCinema, catalog file) pairs
    aliases: tuple = ()              # other family names the font files carry

    @property
    def script(self):
        """The main writing system."""
        return self.scripts[0]

    @property
    def size(self):
        """Bytes to download for every file of the family."""
        return sum(f.size for f in self.files) + (self.license_file.size if self.license_file else 0)

    def weights(self):
        """Human-readable weights, e.g. '300-700' or '400, 700', with ' italic' when italics exist."""
        spans = sorted({f.weights for f in self.files})
        text = ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in spans)
        return text + (" + italic" if any(f.style == "italic" for f in self.files) else "")

    def path(self, file):
        """The file's path inside its source repository."""
        folder = self.folder if file is not self.license_file or self.license_folder is None else self.license_folder
        return f"{folder}/{file.name}" if folder else file.name

    def urls(self, file, mirrors=()):
        """Download addresses for one file: `mirrors` (templates or base URLs, tried first), then the built-ins."""
        repo, commit, templates = SOURCES[self.source]
        path, name = quote(self.path(file), safe="/"), quote(file.name, safe="")
        primary = templates[0].format(repo=repo, commit=commit, path=path, name=name)
        out = []
        for template in (*mirrors, *templates):
            if "{" not in template:
                template = template.rstrip("/") + "/{path}"
            if file not in self.files and "{path}" not in template and "{url}" not in template:
                continue        # release downloads carry the fonts only
            url = template.format(repo=repo, commit=commit, path=path, name=name, url=primary)
            if url not in out:
                out.append(url)
        return out


FAMILIES = (
    Family("fredoka", "Fredoka", "rounded", ("latin", "hebrew"), "ofl/fredoka", "Milena Brandão, Hafontia",
           files=(File("Fredoka[wdth,wght].ttf", 159184,
                       "2ba02e68b152868aef9ba28e24b3648c7d457fe6f25c761f2c2c53fb61a73fc8", (300, 700)),),
           license_file=File("OFL.txt", 4388, "5c9e7eee5c6b25f4b05b8d53b2e470ea4962f9ced742d044a98f7d95d1375bab"),
           bundled=(("Fredoka.ttf", "Fredoka[wdth,wght].ttf"), ("OFL-Fredoka.txt", "OFL.txt"))),
    Family("inter", "Inter", "sans", ("latin", "latin-ext", "vietnamese", "cyrillic", "greek"), "ofl/inter",
           "Rasmus Andersson",
           files=(File("Inter[opsz,wght].ttf", 876576,
                       "29160a80ff49ddcab2c97711247e08b1fab27a484a329ce8b813d820dc559031", (100, 900)),
                  File("Inter-Italic[opsz,wght].ttf", 906596,
                       "acd98e64795781b2058f07b18475e0ecee2a0fe2b42a49e2f9e37d0d6bf66ce6", (100, 900), "italic")),
           license_file=File("OFL.txt", 4377, "5b9321a4298cfeb6b34354164a1c3afc3db114569984c502b9b35d988fd58c57")),
    Family("nunito", "Nunito", "rounded", ("latin", "latin-ext", "vietnamese", "cyrillic"), "ofl/nunito",
           "Vernon Adams, Cyreal, Jacques Le Bailly",
           files=(File("Nunito[wght].ttf", 276932, "bb55a5ca5c2042335b3991af27c4d0705d0ef41cac6164ac737fd8f2a1e85207",
                       (200, 1000)),
                  File("Nunito-Italic[wght].ttf", 281832,
                       "b520cc871868b0acfca1beda875df7f4a44ebce914f8a89f83977fc9c09529c8", (200, 1000), "italic")),
           license_file=File("OFL.txt", 4385, "580df76c95a1ec5ab878ceb25bb3d85c6a076804e9c970c8c6972aea775fdf65")),
    Family("comfortaa", "Comfortaa", "rounded", ("latin", "latin-ext", "vietnamese", "cyrillic", "greek"),
           "ofl/comfortaa", "Johan Aakerlund",
           files=(File("Comfortaa[wght].ttf", 201756,
                       "0fc3f45dc48b614db9c39181502544b37217ecbf8bee2fb35886992bc96c5bd3", (300, 700)),),
           license_file=File("OFL.txt", 4519, "bc85bae0b512b799bbfb2b916e4d0a34cfd963d09778cd783e248b479e67760a")),
    Family("baloo-2", "Baloo 2", "rounded", ("latin", "latin-ext", "vietnamese", "devanagari"), "ofl/baloo2", "Ek Type",
           files=(File("Baloo2[wght].ttf", 683200, "d47a6852548059b1db49a1319d06d499d546c3fa2237cf9eee9c43c8abb025c2",
                       (400, 800)),),
           license_file=File("OFL.txt", 4384, "ad09b05dc8bc678c9daf7c4c5f7ef1f55e5726127f4330b2e98e40b9dffcb860")),
    Family("rubik", "Rubik", "sans", ("latin", "latin-ext", "cyrillic", "arabic", "hebrew"), "ofl/rubik",
           "Hubert and Fischer, Meir Sadan, Cyreal, Daniel Grumer, Omaima Dajani",
           files=(File("Rubik[wght].ttf", 359804, "1b3a7437ba2af80e465e773ed60c5036d1ba6ace492d89046dbcf18fb31e4e88",
                       (300, 900)),
                  File("Rubik-Italic[wght].ttf", 354984,
                       "08c6c4018a5ada8b517407b46897e46cf6ebb106853fbd3e89addb51d3b59c62", (300, 900), "italic")),
           license_file=File("OFL.txt", 4384, "472cbe7c25441df63e9c7864b43eb3c0f4b3df950c66a76224e6cfe1eae843fb")),
    Family("noto-sans", "Noto Sans", "sans", ("latin", "latin-ext", "vietnamese", "cyrillic", "greek", "devanagari"),
           "ofl/notosans", "Google",
           files=(File("NotoSans[wdth,wght].ttf", 2049096,
                       "bfb7bb691513f12e734dc346c03a03f784912432d7e3fa8e56efcf906fe86b3d", (100, 900)),
                  File("NotoSans-Italic[wdth,wght].ttf", 2322640,
                       "58e6e0ebd1931b29a365aa2d3e2ee9a9e831a3af7cf3ad1462d4e72154f0b291", (100, 900), "italic")),
           license_file=File("OFL.txt", 4396, "cee9892f9f0cc8fe882c9e9537ee6a89621d86ee7ceaf70b02e2b2b1c25c061a")),
    Family("oswald", "Oswald", "sans", ("latin", "latin-ext", "vietnamese", "cyrillic"), "ofl/oswald",
           "Vernon Adams, Kalapi Gajjar, Cyreal",
           files=(File("Oswald[wght].ttf", 172088, "5b38c246e255a12f5712d640d56bcced0472466fc68983d2d0410ec0457c2817",
                       (200, 700)),),
           license_file=File("OFL.txt", 4483, "0fd731a904b729a4e02eaf5e8ebd06783edd9abe400e8882760160230675b652")),
    Family("lilita-one", "Lilita One", "display", ("latin",), "ofl/lilitaone", "Juan Montoreano",
           files=(File("LilitaOne-Regular.ttf", 28092,
                       "f5b641c45c69d772ee4eda687bc9fda411d5cad6b0b45371491da4580cbc8d59", 400),),
           license_file=File("OFL.txt", 4392, "255d5debbb80eb2ea762644311f266a279e8778f00156655a516e2b7781a63e1")),
    Family("bebas-neue", "Bebas Neue", "display", ("latin", "latin-ext"), "ofl/bebasneue", "Ryoichi Tsunekawa",
           files=(File("BebasNeue-Regular.ttf", 61400,
                       "08e4623805102d819f58601e46e345648846075e363b2ceb23313c2d1c83ec73", 400),),
           license_file=File("OFL.txt", 4337, "72082f6cb4d04be2ecf7cc7d9e1e7d73787f0af8a5a278a47cade70c16b78341")),
    Family("lobster", "Lobster", "display", ("latin", "latin-ext", "vietnamese", "cyrillic"), "ofl/lobster",
           "Impallari Type",
           files=(File("Lobster-Regular.ttf", 406076,
                       "d6568e697fd50cedc0be04d8aae4127fe95add607e7bff954ca88604be80c205", 400),),
           license_file=File("OFL.txt", 4430, "88aece7d90f2bb7049719f11619a560af22af3451af141f12aa4f46bb157a99b")),
    Family("bangers", "Bangers", "comic", ("latin", "latin-ext", "vietnamese"), "ofl/bangers", "Vernon Adams",
           files=(File("Bangers-Regular.ttf", 93148, "4160a7311de9342674cce9160cde9fcbb30f48190397d86ff1b70b455af65824",
                       400),),
           license_file=File("OFL.txt", 4479, "630dd5a307c0657b094d324e069b390edf90182fe5003639e06c02a0e5769af7")),
    Family("luckiest-guy", "Luckiest Guy", "comic", ("latin", "latin-ext"), "apache/luckiestguy", "Astigmatic",
           files=(File("LuckiestGuy-Regular.ttf", 73320,
                       "cfbdd68a039f92df51cf3721506af6242e64594c6325fe0bedbeff3fe385d980", 400),),
           license="Apache-2.0",
           license_file=File("LICENSE.txt", 11358, "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30")),
    Family("chewy", "Chewy", "comic", ("latin",), "apache/chewy", "Sideshow",
           files=(File("Chewy-Regular.ttf", 41248, "7cf75ea288f82fd20badea8ab4da7a656a96a7277c170811e813b3d3d6294147",
                       400),),
           license="Apache-2.0",
           license_file=File("LICENSE.txt", 11358, "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30")),
    Family("comic-neue", "Comic Neue", "comic", ("latin",), "ofl/comicneue", "Craig Rozynski, Hrant Papazian",
           files=(File("ComicNeue-Light.ttf", 55816, "efb91c06dccc264f07f800c0691d40c94e8cfce6183daade0709268bec178f76",
                       300),
                  File("ComicNeue-Regular.ttf", 57248,
                       "a0ee5a37c8b27c4db0700137d928598b1e23b0089e1546a8961909176b779360", 400),
                  File("ComicNeue-Bold.ttf", 55716, "3e7e5fccfd7e0788f317b43312151c1bd5cf058c9697a8d83eac3939050bd61e",
                       700),
                  File("ComicNeue-LightItalic.ttf", 54120,
                       "a6d36baee09c7025916ddb517835458d15ef890291507197a54875ccc096b927", 300, "italic"),
                  File("ComicNeue-Italic.ttf", 54392,
                       "e06bfd1552f5c9464c5665733ffd69239b0593885dbb9e059688a5900f78cf98", 400, "italic"),
                  File("ComicNeue-BoldItalic.ttf", 55928,
                       "5c312c2a2fa64eee82f3b87fcfab8f3b12a5e59b043124401d322eb323cfbf16", 700, "italic")),
           license_file=File("OFL.txt", 4390, "7c38a22e5878e60fe423360553e63dd7be23d29f1f60336034935dbfc96e8320")),
    Family("patrick-hand", "Patrick Hand", "handwriting", ("latin", "latin-ext", "vietnamese"), "ofl/patrickhand",
           "Patrick Wagesreiter",
           files=(File("PatrickHand-Regular.ttf", 214772,
                       "0f173b3e6cb6d1af25babf7f0057c5ac4ee11f9992b0469bb817e967ef4ad0fc", 400),),
           license_file=File("OFL.txt", 4376, "377f4f9c19e935228552478eb68cc2ed82910988a60ba60e2ac73b09f32d02d1")),
    Family("caveat", "Caveat", "handwriting", ("latin", "latin-ext", "cyrillic"), "ofl/caveat", "Impallari Type",
           files=(File("Caveat[wght].ttf", 403648, "0bdb6b660482d31531b3945849fba5916b3ef8695da7024a9e6b9ee3c4157988",
                       (400, 700)),),
           license_file=File("OFL.txt", 4385, "1f9d81d094273d82f3898a1ee8b598a717d050ecbf5ff7bede105b704880157b")),
    Family("dancing-script", "Dancing Script", "handwriting", ("latin", "latin-ext", "vietnamese"), "ofl/dancingscript",
           "Impallari Type",
           files=(File("DancingScript[wght].ttf", 133636,
                       "21808625578fe8d8cd10cb684be546dca077b27cd03a53a2f1ec11dc743c924c", (400, 700)),),
           license_file=File("OFL.txt", 4443, "6f090277c00af96651ce6dbcc38ff1591047a3bffef486e80b6a32e8276a8201")),
    Family("permanent-marker", "Permanent Marker", "handwriting", ("latin",), "apache/permanentmarker", "Font Diner",
           files=(File("PermanentMarker-Regular.ttf", 74632,
                       "28f82c8a7943cb8e9d599f8554da1d4fc75dbcf69b9885ad6c0611d20c6946c5", 400),),
           license="Apache-2.0",
           license_file=File("LICENSE.txt", 11358, "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30")),
    Family("pacifico", "Pacifico", "brush", ("latin", "latin-ext", "vietnamese", "cyrillic"), "ofl/pacifico",
           "Vernon Adams, Jacques Le Bailly, Botjo Nikoltchev, Ani Petrova",
           files=(File("Pacifico-Regular.ttf", 329380,
                       "5b6c0d5334a7bf77dea52b975c5a0c408878c0f7115ed5b6fb151f634b7bf701", 400),),
           license_file=File("OFL.txt", 4389, "a47e5daeda73568969395c656823102678f2eefb0d7d7ecb47aac4cc17e42204")),
    Family("playfair-display", "Playfair Display", "serif", ("latin", "latin-ext", "vietnamese", "cyrillic"),
           "ofl/playfairdisplay", "Claus Eggers Sørensen",
           files=(File("PlayfairDisplay[wght].ttf", 300724,
                       "c40f2293766a503bc70cce9e512ef844a4ccb7cbcde792fe2ea31d191917d8d6", (400, 900)),
                  File("PlayfairDisplay-Italic[wght].ttf", 278688,
                       "a5e26dc5e2e77fb2803a0bf02fd4f81ee136ec8dea863ccdb0c59a263b21378b", (400, 900), "italic")),
           license_file=File("OFL.txt", 4449, "566be814f8e96e93dfa16101331557eb6b5467e9e03f627c0910fe93ca12300e")),
    Family("lora", "Lora", "serif", ("latin", "latin-ext", "vietnamese", "cyrillic"), "ofl/lora", "Cyreal",
           files=(File("Lora[wght].ttf", 212196, "822a6621ccbe8d97d20ac88c1c41f5615c9c2c202eaa75f272cd452aac6475a7",
                       (400, 700)),
                  File("Lora-Italic[wght].ttf", 221232,
                       "22d8d8854b53807aa664ca34f2031a9ed57a1d0dea296b8b96cdd3aad937a2b3", (400, 700), "italic")),
           license_file=File("OFL.txt", 4423, "1d9a970809ac804b582a6ce7f0ebc4e7fefcbfd7ff6299cad35ee656a21be716")),
    Family("eb-garamond", "EB Garamond", "serif", ("latin", "latin-ext", "vietnamese", "cyrillic", "greek"),
           "ofl/ebgaramond", "Georg Duffner, Octavio Pardo",
           files=(File("EBGaramond[wght].ttf", 851176,
                       "ef9512f92f6d579e5dc75af59a5a4b1b8b47d2eda89e00b954d44520e5369027", (400, 800)),
                  File("EBGaramond-Italic[wght].ttf", 754468,
                       "bba2c4499c93c9612b90b9825d32b07da52fce2fe57562a1eb6b833553f93c4e", (400, 800), "italic")),
           license_file=File("OFL.txt", 4398, "0985066662eb755ed3683ae5482a81a9195b49ce3f7e165cc2388b3dbece7dd7")),
    Family("cinzel", "Cinzel", "serif", ("latin", "latin-ext"), "ofl/cinzel", "Natanael Gama",
           files=(File("Cinzel[wght].ttf", 125468, "f4d83d34d1f6c741193e4acf4b3dff9531e5a67b6aa65228d00a7db72a4e0f34",
                       (400, 900)),),
           license_file=File("OFL.txt", 4383, "f2b3029aba64c378bf0963b62945eee15e564fe4330b934c8f2eb058282b5e83")),
    Family("noto-serif", "Noto Serif", "serif", ("latin", "latin-ext", "vietnamese", "cyrillic", "greek"),
           "ofl/notoserif", "Google",
           files=(File("NotoSerif[wdth,wght].ttf", 1887192,
                       "4d8e6761424656867019081a1a01336f3cb086982682698714054fc33f782713", (100, 900)),
                  File("NotoSerif-Italic[wdth,wght].ttf", 2448496,
                       "e87acbc6c0efd0d9a20d6a8cbbda2b266c14be3a3a6f5af8ec9d7b2460570ad1", (100, 900), "italic")),
           license_file=File("OFL.txt", 4396, "cee9892f9f0cc8fe882c9e9537ee6a89621d86ee7ceaf70b02e2b2b1c25c061a")),
    Family("jetbrains-mono", "JetBrains Mono", "mono", ("latin", "latin-ext", "vietnamese", "cyrillic", "greek"),
           "ofl/jetbrainsmono", "JetBrains, Philipp Nurullin, Konstantin Bulenkov",
           files=(File("JetBrainsMono[wght].ttf", 187208,
                       "48715a42ec242c21e9f02692891e147d022299a52e48d5e413e1a942193ffeda", (100, 800)),
                  File("JetBrainsMono-Italic[wght].ttf", 191556,
                       "85ae2a5cd3f56baf1ce1c21a851322c58e3d8fbe8e8ad4a4d090a820dd7fe558", (100, 800), "italic")),
           license_file=File("OFL.txt", 4399, "b2fe5e8987594e9ffd1d2ca52a2f5d73eb8335243893c5d6254b5ad69269591d")),
    Family("press-start-2p", "Press Start 2P", "pixel", ("latin", "latin-ext", "cyrillic", "greek"), "ofl/pressstart2p",
           "CodeMan38",
           files=(File("PressStart2P-Regular.ttf", 118204,
                       "034c77f1f05ec89421e4a63f0e3a4ca1ecf852cc6d2bf611f126f275728e017d", 400),),
           license_file=File("OFL.txt", 4413, "705960c3281a5765ecc0b59bd4ed7ca59eed165748076bc2fc3e8fdbfeb944b0")),
    Family("zcool-kuaile", "ZCOOL KuaiLe", "display", ("zh-Hans", "latin"), "ofl/zcoolkuaile",
           "Liu Bingke, Yang Kang, Wu Shaojie",
           files=(File("ZCOOLKuaiLe-Regular.ttf", 1514968,
                       "812a6fc1fe54b6d73a419245c32dfeba8aa33104d5be90d1cf6af082007cb71d", 400),),
           license_file=File("OFL.txt", 4398, "538078469839b4a2e7ad22bef4ebe41681a4e53749bb2a072144024f1d6d703d"),
           bundled=(("ZCOOLKuaiLe-Regular.ttf", "ZCOOLKuaiLe-Regular.ttf"), ("OFL-ZCOOLKuaiLe.txt", "OFL.txt"))),
    Family("zcool-xiaowei", "ZCOOL XiaoWei", "serif", ("zh-Hans", "latin"), "ofl/zcoolxiaowei", "Li Dawei",
           files=(File("ZCOOLXiaoWei-Regular.ttf", 6313808,
                       "a42b620140f493db42f741351dfbf343c0936d58588ee8004b8b2a218d997ff1", 400),),
           license_file=File("OFL.txt", 4400, "a094514ca57cf8f9c5e8d8d1adab5d8cd3a377297ff016f9df2c05b3ecd77f0a"),
           aliases=("站酷小薇体",)),
    Family("zcool-qingke-huangyou", "ZCOOL QingKe HuangYou", "display", ("zh-Hans", "latin"), "ofl/zcoolqingkehuangyou",
           "Zheng Qingke",
           files=(File("ZCOOLQingKeHuangYou-Regular.ttf", 8328684,
                       "54f0c0df4308cd74cd0f2fd3494ae054dbc4a1fd6fa7d71f4807eb4cdd8b4136", 400),),
           license_file=File("OFL.txt", 4419, "f1bce31b817dee01c1e4ef8bc45d8ecb95f01f4abbf0a985007cb3cd0fd8123d")),
    Family("ma-shan-zheng", "Ma Shan Zheng", "brush", ("zh-Hans", "latin"), "ofl/mashanzheng", "Ma ShanZheng",
           files=(File("MaShanZheng-Regular.ttf", 5857936,
                       "6d2546bb189c732a8ca29af9e22457b152387d158aa459e4ac2ce1e51788b7fb", 400),),
           license_file=File("OFL.txt", 4397, "d7bdb1cee215b689e23c2f95672a6084c790542170648267a55114103d756a08")),
    Family("zhi-mang-xing", "Zhi Mang Xing", "brush", ("zh-Hans", "latin"), "ofl/zhimangxing", "Wei Zhimang",
           files=(File("ZhiMangXing-Regular.ttf", 4063532,
                       "644e0cae9b40f0b10ab729a01bd32032e3973bac22be3dccae01bf6ae7fde969", 400),),
           license_file=File("OFL.txt", 4397, "10947328199e369a3e6b4a67e8e5507ed99d5bbb264a1f156415aa9b665e4d15")),
    Family("liu-jian-mao-cao", "Liu Jian Mao Cao", "brush", ("zh-Hans", "latin"), "ofl/liujianmaocao",
           "Liu Zhengjiang, Kimberly Geswein, ZhongQi",
           files=(File("LiuJianMaoCao-Regular.ttf", 4951804,
                       "cab396b91a5b7c0b4005a35891180d06e6751f5ac261fe680aec65c1ae209033", 400),),
           license_file=File("OFL.txt", 4406, "ff56684b0212481e7c3886c26d5a655de9b211c8119e5ccc756138a97b066acc")),
    Family("long-cang", "Long Cang", "handwriting", ("zh-Hans", "latin"), "ofl/longcang", "Chen Xiaomin",
           files=(File("LongCang-Regular.ttf", 5162508,
                       "e5bf2c3f24ef2327c6f136d8f73e2f9dfdf44896fdbeb35a9515f44777bb91bc", 400),),
           license_file=File("OFL.txt", 4390, "603546b7219a94bb59bf8294458194a5010119486354092b66a09a3fd61aeacc")),
    Family("noto-sans-sc", "Noto Sans SC", "sans", ("zh-Hans", "latin", "vietnamese", "cyrillic"), "ofl/notosanssc",
           "Google",
           files=(File("NotoSansSC[wght].ttf", 17772300,
                       "a3041811a78c361b1de50f953c805e0244951c21c5bd412f7232ef0d899af0da", (100, 900)),),
           license_file=File("OFL.txt", 4388, "1c05c68c34f9708415aada51f17e1b0092d2cea709bf4a94cd38114f9e73d7d9")),
    Family("noto-serif-sc", "Noto Serif SC", "serif", ("zh-Hans", "latin", "vietnamese", "cyrillic"), "ofl/notoserifsc",
           "Google",
           files=(File("NotoSerifSC[wght].ttf", 25125512,
                       "050080d9255a86808f2945bffac582b31ef32bc36411ce29563b4961670c66f9", (200, 900)),),
           license_file=File("OFL.txt", 4350, "5e0da210fb04058a8c0087985d2d456b931c2579811a49655721d3cf0c36b6d6")),
    Family("lxgw-wenkai", "LXGW WenKai", "handwriting",
           ("zh-Hans", "latin", "latin-ext", "vietnamese", "cyrillic", "greek"), "fonts/TTF", "LXGW",
           files=(File("LXGWWenKai-Light.ttf", 28267156,
                       "526ec70cbb0118e871d481f8179e03ff045f0e4d72d080dcca87950c4ab27cca", 300),
                  File("LXGWWenKai-Regular.ttf", 25575676,
                       "39ad71264b588165b469e35e6afb162a378dacd1f95348160240ba9038ac3009", 400),
                  File("LXGWWenKai-Medium.ttf", 25379848,
                       "d4bdeb38a39151d74d084cba5090f8cb7d20bf83eedb78c35939ae70b9f4e3f6", 500)),
           license_file=File("OFL.txt", 4448, "c38b1994a5e48ac30ac7d1da7d0409fd8fd8127dfe28a13d6e787d5b1ef34a5e"),
           source="lxgw",
           license_folder=""),
    Family("noto-sans-tc", "Noto Sans TC", "sans", ("zh-Hant", "latin", "vietnamese", "cyrillic"), "ofl/notosanstc",
           "Google",
           files=(File("NotoSansTC[wght].ttf", 11941968,
                       "864727d210d54f2537bbe23b3a839436c3992af72de9322af5270897246bd44f", (100, 900)),),
           license_file=File("OFL.txt", 4388, "1c05c68c34f9708415aada51f17e1b0092d2cea709bf4a94cd38114f9e73d7d9")),
    Family("noto-serif-tc", "Noto Serif TC", "serif", ("zh-Hant", "latin", "vietnamese", "cyrillic"), "ofl/notoseriftc",
           "Google",
           files=(File("NotoSerifTC[wght].ttf", 16851596,
                       "0077e18f57c6908f4a000969880940bdb0dad057c0e8d98b49dc364c3d1b09c6", (200, 900)),),
           license_file=File("OFL.txt", 4350, "5e0da210fb04058a8c0087985d2d456b931c2579811a49655721d3cf0c36b6d6")),
    Family("lxgw-wenkai-tc", "LXGW WenKai TC", "handwriting",
           ("zh-Hant", "latin", "latin-ext", "vietnamese", "cyrillic", "greek"), "ofl/lxgwwenkaitc", "LXGW",
           files=(File("LXGWWenKaiTC-Light.ttf", 13771744,
                       "48cabec60b908f145002192c366d805b674d6e890a98c24f8a39fd33542273fd", 300),
                  File("LXGWWenKaiTC-Regular.ttf", 13110528,
                       "4fcc5aec11cbbf737b0cfab7b63796f7f280087a7a656b2f13342cd5e5318d95", 400),
                  File("LXGWWenKaiTC-Bold.ttf", 12881104,
                       "5c9feadfd928f3ae3860e7d001ad3d0d0c55b0157fff08cd4d51b51aca677f23", 700)),
           license_file=File("OFL.txt", 4390, "4fff27d35db0e22cd81d58da6f20e09f415cf354a3338e3cf1fc0eb9222c7174")),
    Family("huninn", "Huninn", "rounded", ("zh-Hant", "latin", "latin-ext", "vietnamese", "cyrillic", "hebrew"),
           "ofl/huninn", "justfont",
           files=(File("Huninn-Regular.ttf", 4683972,
                       "1bd770a5ffc0c06723b567686f8b5db5abf9ab54227f3bbc4e6fd648f4698805", 400),),
           license_file=File("OFL.txt", 4382, "d71824aeb09afc4c2cac01acab5c3db79796e927ba37be40d69fb62a412639b6")),
    Family("iansui", "Iansui", "handwriting", ("zh-Hant", "latin", "cyrillic"), "ofl/iansui", "But Ko",
           files=(File("Iansui-Regular.ttf", 9420560,
                       "6e6340d80d618a42b48ade9370c34fa37a8210750c6fbc8efe65f23716538a2b", 400),),
           license_file=File("OFL.txt", 4388, "ba756a625db54032da8e4c8e58a19519964b93fac04267ec15e14ee8c5cc82a5")),
    Family("noto-sans-jp", "Noto Sans JP", "sans", ("ja", "latin", "vietnamese", "cyrillic"), "ofl/notosansjp",
           "Google",
           files=(File("NotoSansJP[wght].ttf", 9589900,
                       "c2f3b4d463500a2ddcd3849cded1fceeb9fd6d1c32e6cbecd568453ba50fc68f", (100, 900)),),
           license_file=File("OFL.txt", 4388, "1c05c68c34f9708415aada51f17e1b0092d2cea709bf4a94cd38114f9e73d7d9")),
    Family("noto-serif-jp", "Noto Serif JP", "serif", ("ja", "latin", "vietnamese", "cyrillic"), "ofl/notoserifjp",
           "Google",
           files=(File("NotoSerifJP[wght].ttf", 13574352,
                       "2fd527ba12b6a44ec30d796d633360da0aeba6c5d4af1304ce12bb4dc15a7dfc", (200, 900)),),
           license_file=File("OFL.txt", 4350, "5e0da210fb04058a8c0087985d2d456b931c2579811a49655721d3cf0c36b6d6")),
    Family("m-plus-rounded-1c", "M PLUS Rounded 1c", "rounded",
           ("ja", "latin", "latin-ext", "vietnamese", "cyrillic", "greek", "hebrew"), "ofl/mplusrounded1c",
           "Coji Morishita, M+ Fonts Project",
           files=(File("MPLUSRounded1c-Thin.ttf", 2907880,
                       "180c0959fff5af21637c3887c0ec47df8164877218ef7e866a7a227f2c1e1a9f", 100),
                  File("MPLUSRounded1c-Light.ttf", 3294556,
                       "ade5c673a5d097b59c7bc5b1a6c1e37d3dd63c3ac98468a647d8ab2392b98b49", 300),
                  File("MPLUSRounded1c-Regular.ttf", 3389792,
                       "b75708b53e45b06d17d470aeeca5b766e3d1b3999f03f13ec4eb863ca846c14c", 400),
                  File("MPLUSRounded1c-Medium.ttf", 3432624,
                       "adfde1b6bae58719c4e0144612a94232e72fc5ca655c4722165fe88d06521a70", 500),
                  File("MPLUSRounded1c-Bold.ttf", 3542592,
                       "c358630584e8e2d8fbd6121d0f4693255ffef6d1e6d4f3441fd6e5a963a11f9e", 700),
                  File("MPLUSRounded1c-ExtraBold.ttf", 3628512,
                       "8e7c15901dca87f1451b356dda594f7d092ba252a5dcc47da74523a242493c36", 800),
                  File("MPLUSRounded1c-Black.ttf", 3635504,
                       "d5981a59ccc5f00da1bd3ae46750fa95cd165b0e6b3a5fc7a1945f94c59449e3", 900)),
           notice="Copyright 2016 The Rounded M+ Project Authors.",
           aliases=("Rounded Mplus 1c",)),
    Family("zen-maru-gothic", "Zen Maru Gothic", "rounded", ("ja", "latin", "cyrillic", "greek"), "ofl/zenmarugothic",
           "Yoshimichi Ohira",
           files=(File("ZenMaruGothic-Light.ttf", 3723392,
                       "c4e6fa10ff517df37cb0c13038fe2813f3c47afe6577fa4a5573200e4508b2c1", 300),
                  File("ZenMaruGothic-Regular.ttf", 3832756,
                       "a0c0b53543e0993ae2225e629c833f3d51495ad31720694ff112ce4ce11111ef", 400),
                  File("ZenMaruGothic-Medium.ttf", 3810988,
                       "3cfdb98a13571ede17fcc769f5093a97c38b80a7b9b2ab754a26b4d822092b3b", 500),
                  File("ZenMaruGothic-Bold.ttf", 3779008,
                       "fe24426b9c8b5523a0146a8235c8674eccf0493af354a53ec895c3596d9eb745", 700),
                  File("ZenMaruGothic-Black.ttf", 3710324,
                       "6bd74fe76cd39ee0ec18775c3661d845343fb3f6f8fa09a3076638417baf741f", 900)),
           license_file=File("OFL.txt", 4402, "2a20cf7ce1909d8ee1e949095d340f7d7656705f7c810a2d6faf56800ad0cb3d")),
    Family("kosugi-maru", "Kosugi Maru", "rounded", ("ja", "latin", "cyrillic"), "apache/kosugimaru", "MOTOYA",
           files=(File("KosugiMaru-Regular.ttf", 3565716,
                       "4b8d0022c8dadd090ef67cd1f71f130714767af7806cba2eb4ebe4b0271c1d68", 400),),
           license="Apache-2.0",
           license_file=File("LICENSE.txt", 11358, "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30")),
    Family("yusei-magic", "Yusei Magic", "handwriting", ("ja", "latin"), "ofl/yuseimagic", "Tanukizamurai",
           files=(File("YuseiMagic-Regular.ttf", 3134968,
                       "82098615f39ed9da6a8ccc674b9006e49c70dd5b775a7a1697f6bedd22ce25a2", 400),),
           license_file=File("OFL.txt", 4393, "c74e8c47951ddd9c902f07097761cfa0457993e28d8e1e946e273c0250be77c9")),
    Family("dela-gothic-one", "Dela Gothic One", "display",
           ("ja", "latin", "latin-ext", "vietnamese", "cyrillic", "greek"), "ofl/delagothicone", "artakana",
           files=(File("DelaGothicOne-Regular.ttf", 2508848,
                       "4ff87a0965f1b0505e5a2c58424bc6ad3cff27e56a82f21c2fc9d6b0e3857ee2", 400),),
           license_file=File("OFL.txt", 4392, "c0014792d4f4abc0508c295b277f2b17ae44465c8dc88d12af9cea48279b5fda")),
    Family("rocknroll-one", "RocknRoll One", "display", ("ja", "latin", "cyrillic"), "ofl/rocknrollone",
           "Fontworks Inc.",
           files=(File("RocknRollOne-Regular.ttf", 2682824,
                       "dc0f5ff975851827f63f2c6bfed128ffbca14b6399a10fb5e1711215c0108526", 400),),
           license_file=File("OFL.txt", 4488, "b2f42a005a6a48ead81e369021e300184f0cbecb48aee6f831e46c7897f6055b")),
    Family("klee-one", "Klee One", "handwriting", ("ja", "latin", "cyrillic"), "ofl/kleeone", "Fontworks Inc.",
           files=(File("KleeOne-Regular.ttf", 8724204,
                       "bf4063f030cc2ae6adf0a11424a1888e5c0eb4438f1f6d02f52294af868e9b3a", 400),
                  File("KleeOne-SemiBold.ttf", 8905128,
                       "b031ec426c23ca1143ef1f7d58bee7a79efe119ed654152f121c922202b303fd", 600)),
           license_file=File("OFL.txt", 4479, "e376b0df8e8a2345a9533db6f0a5333a1107975569ad9d1973a7ee557161ca38")),
    Family("hachi-maru-pop", "Hachi Maru Pop", "comic", ("ja", "latin", "cyrillic"), "ofl/hachimarupop", "Nonty",
           files=(File("HachiMaruPop-Regular.ttf", 4385624,
                       "78408910c8f1a2f174a279cbc1484b48b71780039eba3fe1be2bfcc5d4df3f98", 400),),
           license_file=File("OFL.txt", 4494, "8d3c434650e84f42ddb33e9b5929089ea51c39b231b798dacb33087d5f05d9f1")),
    Family("shippori-mincho", "Shippori Mincho", "serif", ("ja", "latin"), "ofl/shipporimincho", "FONTDASU",
           files=(File("ShipporiMincho-Regular.ttf", 8677284,
                       "769b5269f0f9bc6534b352c0e6bd856a566e03ff788f107191c2d835863570b2", 400),
                  File("ShipporiMincho-Medium.ttf", 8678848,
                       "700e505afc4cded2338eba29478a041e04c1c2ea5114fbb3e0b04e76c302c5d8", 500),
                  File("ShipporiMincho-SemiBold.ttf", 8650032,
                       "bc7925544894a91466449adb73c6d943f50c3e53eb1c74d0673fe2dbafcd4d2d", 600),
                  File("ShipporiMincho-Bold.ttf", 8563788,
                       "63bc4eddc74793f671c3ab827c5175e773ffbe569d0bf50ee65375ea9e3bc286", 700),
                  File("ShipporiMincho-ExtraBold.ttf", 8563208,
                       "bdb787644b4b347e9a7efdd576f0d16ee4528cc9b5c86d23e06fa1a14ae0444c", 800)),
           license_file=File("OFL.txt", 4399, "41fba056279be5f45ff9a99e44b7b53897b42732f5806d8e666e0ab49ac6bd38")),
    Family("yuji-syuku", "Yuji Syuku", "brush", ("ja", "latin", "cyrillic"), "ofl/yujisyuku", "Kinuta Font Factory",
           files=(File("YujiSyuku-Regular.ttf", 8430348,
                       "82728ebafc8c97391e2dab633414a806f344b8e4e2227d307179f07b548fca61", 400),),
           license_file=File("OFL.txt", 4386, "ef7c85c72ae94381c8bc4832ae4e6fbabdeafa2bb8a31313cd75dce95a690256")),
    Family("dotgothic16", "DotGothic16", "pixel", ("ja", "latin", "cyrillic"), "ofl/dotgothic16", "Fontworks Inc.",
           files=(File("DotGothic16-Regular.ttf", 2069236,
                       "3ad9af88726d42b40f7f365f0dcac785af73cf20ea6f1d5b44e57cc21150b8f1", 400),),
           license_file=File("OFL.txt", 4492, "b6630c61ea078cacd7fabe37d14ffe557a0b45b06683374a9aa9e24262993e33")),
    Family("noto-sans-kr", "Noto Sans KR", "sans", ("ko", "latin", "vietnamese", "cyrillic"), "ofl/notosanskr",
           "Google",
           files=(File("NotoSansKR[wght].ttf", 10414588,
                       "194018e6b2b293a7964f037b25c0249ce1418bc9ab3c971060a03aa57861e252", (100, 900)),),
           license_file=File("OFL.txt", 4388, "1c05c68c34f9708415aada51f17e1b0092d2cea709bf4a94cd38114f9e73d7d9")),
    Family("noto-serif-kr", "Noto Serif KR", "serif", ("ko", "latin", "vietnamese", "cyrillic"), "ofl/notoserifkr",
           "Google",
           files=(File("NotoSerifKR[wght].ttf", 23795420,
                       "11f8d5de6f1b79195efba3828aaa2ec95c1178f5ae976fb23c8d53250a9938f3", (200, 900)),),
           license_file=File("OFL.txt", 4350, "5e0da210fb04058a8c0087985d2d456b931c2579811a49655721d3cf0c36b6d6")),
    Family("jua", "Jua", "rounded", ("ko", "latin"), "ofl/jua", "Woowahan Brothers",
           files=(File("Jua-Regular.ttf", 2119352, "769677aef240bfc3b9965f2b50748075bff885e6c6992fc591a3fb268279f898",
                       400),),
           license_file=File("OFL.txt", 4342, "44a7c6e4c5572392ae122d3b1d8c6ba6fd640a7797e675384585d947f2773e3c")),
    Family("do-hyeon", "Do Hyeon", "display", ("ko", "latin"), "ofl/dohyeon", "Woowahan Brothers",
           files=(File("DoHyeon-Regular.ttf", 879764,
                       "35644be7f28e0a68a447b1f7af351dcde5674b870f24f7b5f43e26d00b4ab653", 400),),
           license_file=File("OFL.txt", 4347, "de5ff32211a4340b01477af39ee339d639438955e409f79b666d4b9207f3c92c")),
    Family("black-han-sans", "Black Han Sans", "display", ("ko", "latin"), "ofl/blackhansans", "Zess Type",
           files=(File("BlackHanSans-Regular.ttf", 998424,
                       "31960809284026681774a8e52dc19ebcad26cf69b0ad9d560f288296fbb52739", 400),),
           license_file=File("OFL.txt", 4399, "c324192c8b3a988bae45a9a7e4ac1258b684739003bda114e0523423440457c9")),
    Family("gaegu", "Gaegu", "handwriting", ("ko", "latin"), "ofl/gaegu", "JIKJI SOFT",
           files=(File("Gaegu-Light.ttf", 3213004, "da44ad6e5823819599ec42e1a516f23002cc0e72f968f93bd49e793360cd77ca",
                       300),
                  File("Gaegu-Regular.ttf", 3165816, "aa52c98336f7c62e2896fc8b12b56a75d5b476d88a2f104b0980f4f7ce0adfc3",
                       400),
                  File("Gaegu-Bold.ttf", 2962664, "cc38a4af9506a45254d1ce07c589ec473d9e5f0be319e5a77b17c214903f8c1c",
                       700)),
           license_file=File("OFL.txt", 4344, "53a9ce47085d9fef613c7ecb3730dc80d25962510bbea231b89564f58240f251")),
    Family("nanum-pen-script", "Nanum Pen Script", "handwriting", ("ko", "latin"), "ofl/nanumpenscript",
           "Sandoll Communication",
           files=(File("NanumPenScript-Regular.ttf", 3201664,
                       "6f0d1ab29c7894010dc88831fb7a0a51edb79136e450344183de5b1a8b52bd43", 400),),
           license_file=File("OFL.txt", 4534, "eeacf16032901d0ed0456876ec77b8f0fda6b3fecec7d972f8543eb602e6c30f"),
           aliases=("Nanum Pen",)),
    Family("gowun-dodum", "Gowun Dodum", "sans", ("ko", "latin", "latin-ext", "vietnamese"), "ofl/gowundodum",
           "Yanghee Ryu",
           files=(File("GowunDodum-Regular.ttf", 7229088,
                       "a6e457933227483a11758fd0947bc74422a106d46f0bf057fdaa5af94a30067d", 400),),
           license_file=File("OFL.txt", 4395, "a7c73f9521cd646bbdfb6684c99a62311bbd7bce11898dc11ef0b3c69eda1aca")),
    Family("gamja-flower", "Gamja Flower", "handwriting", ("ko", "latin"), "ofl/gamjaflower", "YoonDesign Inc",
           files=(File("GamjaFlower-Regular.ttf", 12615444,
                       "ece32819ed58536355a49a095b0cdfdd3b8ef9081c5ed9ca1cef8f5d999ae1ac", 400),),
           license_file=File("OFL.txt", 4354, "39de3de5f1873f89bca4af37823ab22e28e88d0d8f7fe2f07e82e9e6e9bf7b70")),
    Family("sunflower", "Sunflower", "sans", ("ko", "latin"), "ofl/sunflower", "JIKJISOFT",
           files=(File("Sunflower-Light.ttf", 758332,
                       "dd9fb97aa9ec1fdb65e0328513d9c54c114fba41decca1d32a1e1ed992e255c5", 300),
                  File("Sunflower-Medium.ttf", 770536,
                       "6e216d6b2f77a850f6b73be25633d09e03385dfa63a3a632f9e7d83a90ea7f79", 500),
                  File("Sunflower-Bold.ttf", 746300, "6b033627817f6619433afe82028013dc45a78ff82406b1dbe5b16e1bbc370e0a",
                       700)),
           license_file=File("OFL.txt", 4348, "a9b40759b5821a0c2ad07cbd2c2a61dca4b3e222e6370a7d5bfb6b373bf4fb10")),
    Family("dongle", "Dongle", "rounded", ("ko", "latin", "latin-ext", "vietnamese"), "ofl/dongle", "Yanghee Ryu",
           files=(File("Dongle-Light.ttf", 4389060, "bb04e03dbe44fb0c619434f31565e62b5bac67229d5ed72eeac69c2e74e9a45c",
                       300),
                  File("Dongle-Regular.ttf", 4458600,
                       "2966e7a9d312a868e2b5477bf9a3e59b8ce16beb76e7e52305ab5897d1ce9741", 400),
                  File("Dongle-Bold.ttf", 4476536, "944c498c0d1a1832ab36f173b1b3aa5ae77b2a914e00c4d79e05338fae36472d",
                       700)),
           license_file=File("OFL.txt", 4386, "f9e59049e824264bffd626d0901cfcaac9d5ba756988b904d3e3e0e233493607")),
    Family("nanum-brush-script", "Nanum Brush Script", "brush", ("ko", "latin"), "ofl/nanumbrushscript",
           "Sandoll Communication",
           files=(File("NanumBrushScript-Regular.ttf", 3564804,
                       "27ceaf578c96f594cdf07fe0181b251790acbb746a164e45c1f6473f89911a31", 400),),
           license_file=File("OFL.txt", 4534, "eeacf16032901d0ed0456876ec77b8f0fda6b3fecec7d972f8543eb602e6c30f")),
    Family("noto-sans-arabic", "Noto Sans Arabic", "sans", ("arabic", "latin", "latin-ext"), "ofl/notosansarabic",
           "Google",
           files=(File("NotoSansArabic[wdth,wght].ttf", 844676,
                       "63111b5b2e074dd48cc67692e0a2726d86ee94c1c37fe8598257b7b4e87e869e", (100, 900)),),
           license_file=File("OFL.txt", 4382, "07fc70bfeb985cc1a87a8587d0a0c80bab11c86c9dc3fd95b6f0cb332f983e96")),
    Family("baloo-bhaijaan-2", "Baloo Bhaijaan 2", "rounded", ("arabic", "latin", "latin-ext", "vietnamese"),
           "ofl/baloobhaijaan2", "Ek Type",
           files=(File("BalooBhaijaan2[wght].ttf", 285508,
                       "3e9f07fbc796c0ddcb3e6e0aa26f9c86741d9f5b7f5cb72f4ed3c06e55a19336", (400, 800)),),
           license_file=File("OFL.txt", 4384, "ad09b05dc8bc678c9daf7c4c5f7ef1f55e5726127f4330b2e98e40b9dffcb860")),
    Family("noto-sans-devanagari", "Noto Sans Devanagari", "sans", ("devanagari", "latin", "latin-ext"),
           "ofl/notosansdevanagari", "Google",
           files=(File("NotoSansDevanagari[wdth,wght].ttf", 641944,
                       "14ec4af41f27482216d1c2229f417ff9b1425e1babb014e57d1d40d03229853e", (100, 900)),),
           license_file=File("OFL.txt", 4386, "a216f6f8d85c7228093e0ee5e258d9d377e6671f68acb4db1930b29583d0f331")),
    Family("noto-sans-thai", "Noto Sans Thai", "sans", ("thai", "latin", "latin-ext"), "ofl/notosansthai", "Google",
           files=(File("NotoSansThai[wdth,wght].ttf", 218652,
                       "5a1c559bb539583c8a1fd99d1c5b9491e5e14478c9cd2bd0970d5c3096cc9ef8", (100, 900)),),
           license_file=File("OFL.txt", 4380, "2e98fd23a52d253db8612cd5942c8f2ff4111b21d2367050fdca91d8ccc374a0")),
    Family("mitr", "Mitr", "sans", ("thai", "latin", "latin-ext", "vietnamese"), "ofl/mitr", "Cadson Demak",
           files=(File("Mitr-ExtraLight.ttf", 200760,
                       "dc3e6a03603bb0db3dc6833042e218a917d211d52d93bca426aa606f129d4488", 200),
                  File("Mitr-Light.ttf", 211080, "0ddb2f43bc071cd1546d1abdb0447c4a411e06450e69d97c838c2725fc8064a6",
                       300),
                  File("Mitr-Regular.ttf", 222416, "3763923ca8d860f9c06f483f663cd3d8d94e9ed8c2f35a7ce35bb6b13e1219fd",
                       400),
                  File("Mitr-Medium.ttf", 222116, "847340933424d473bff6d011bc08543a2a2d2a670985a93e3431e3ac8926068f",
                       500),
                  File("Mitr-SemiBold.ttf", 225796, "257e8612923ed13838b2f0a0f9b25527aa83513c657df049a5ee608e6d4a059d",
                       600),
                  File("Mitr-Bold.ttf", 224432, "92349c05cd6a35549d0fb3e9b0d7d73059717e212cbda182ee28e5917150bc34",
                       700)),
           license_file=File("OFL.txt", 4382, "427ae4ac208b3cb1930bc2398141bed5880f0c057af4d2fc91b2f7ba8dcffb7d")),
    Family("noto-sans-hebrew", "Noto Sans Hebrew", "sans", ("hebrew", "latin", "latin-ext"), "ofl/notosanshebrew",
           "Google",
           files=(File("NotoSansHebrew[wdth,wght].ttf", 112640,
                       "7ef36a2c3593758cdb622e1bdef4f84523e92fbc3ccc667438dd80ff54c2de88", (100, 900)),),
           license_file=File("OFL.txt", 4382, "9b9fe028b5ba74d231659a1bbaf0ed09b11e759d1ca6a070999e16d151616b47")),
)

# Default families of each role per writing system, best first. Other roles use "body"; systems a role leaves out
# use its "latin" entry for Latin variants, then "body".
ROLES = {
    "title": {"latin": ("fredoka",), "latin-ext": ("nunito",), "vietnamese": ("nunito",), "cyrillic": ("nunito",),
              "greek": ("comfortaa",), "zh-Hans": ("zcool-kuaile",), "zh-Hant": ("huninn",),
              "ja": ("zen-maru-gothic",), "ko": ("jua",), "arabic": ("baloo-bhaijaan-2",), "devanagari": ("baloo-2",),
              "thai": ("mitr",), "hebrew": ("fredoka",)},
    "body": {"latin": ("inter",), "latin-ext": ("inter",), "vietnamese": ("inter",), "cyrillic": ("inter",),
             "greek": ("inter",), "zh-Hans": ("noto-sans-sc",), "zh-Hant": ("noto-sans-tc",), "ja": ("noto-sans-jp",),
             "ko": ("noto-sans-kr",), "arabic": ("noto-sans-arabic",), "devanagari": ("noto-sans-devanagari",),
             "thai": ("noto-sans-thai",), "hebrew": ("noto-sans-hebrew",)},
    "serif": {"latin": ("lora",), "greek": ("noto-serif",), "zh-Hans": ("noto-serif-sc",),
              "zh-Hant": ("noto-serif-tc",), "ja": ("noto-serif-jp",), "ko": ("noto-serif-kr",)},
    "handwriting": {"latin": ("caveat",), "vietnamese": ("patrick-hand",), "zh-Hans": ("lxgw-wenkai",),
                    "zh-Hant": ("lxgw-wenkai-tc",), "ja": ("klee-one",), "ko": ("gaegu",)},
    "brush": {"latin": ("pacifico",), "zh-Hans": ("ma-shan-zheng",), "zh-Hant": ("lxgw-wenkai-tc",),
              "ja": ("yuji-syuku",), "ko": ("nanum-brush-script",)},
    "comic": {"latin": ("bangers",), "cyrillic": ("nunito",), "zh-Hans": ("zcool-kuaile",), "zh-Hant": ("huninn",),
              "ja": ("hachi-maru-pop",), "ko": ("jua",)},
    "mono": {"latin": ("jetbrains-mono",)},
    "pixel": {"latin": ("press-start-2p",), "ja": ("dotgothic16",)},
}
ROLE_ALIASES = {"display": "title", "subtitle": "title", "credits": "title", "rounded": "title", "caption": "body",
                "text": "body", "sans": "body", "calligraphy": "brush", "script": "handwriting"}
# Widely installed system families per writing system: the offline fallback, and the "ui" role's first choice.
SYSTEM = {
    "latin": ("Helvetica Neue", "Helvetica", "Arial", "Segoe UI", "Roboto", "Noto Sans", "DejaVu Sans",
              "Liberation Sans", "Cantarell", "Ubuntu"),
    "zh-Hans": ("PingFang SC", "Hiragino Sans GB", "Heiti SC", "STHeiti", "Microsoft YaHei", "Microsoft YaHei UI",
                "DengXian", "SimHei", "Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Zen Hei",
                "WenQuanYi Micro Hei", "Droid Sans Fallback"),
    "zh-Hant": ("PingFang TC", "PingFang HK", "Heiti TC", "Microsoft JhengHei", "Microsoft JhengHei UI",
                "Noto Sans CJK TC", "Source Han Sans TC", "AR PL UMing TW", "WenQuanYi Zen Hei"),
    "ja": ("Hiragino Sans", "Hiragino Kaku Gothic ProN", "Yu Gothic", "Yu Gothic UI", "Meiryo", "MS Gothic",
           "Noto Sans CJK JP", "Source Han Sans JP", "IPAexGothic", "IPAGothic", "TakaoGothic", "VL Gothic"),
    "ko": ("Apple SD Gothic Neo", "AppleGothic", "Malgun Gothic", "Gulim", "Noto Sans CJK KR", "Source Han Sans KR",
           "NanumGothic", "UnDotum"),
    "arabic": ("Geeza Pro", "SF Arabic", "Segoe UI", "Arial", "Tahoma", "Noto Sans Arabic", "Noto Naskh Arabic",
               "DejaVu Sans"),
    "hebrew": ("Arial Hebrew", "SF Hebrew", "Segoe UI", "Arial", "Noto Sans Hebrew", "DejaVu Sans"),
    "devanagari": ("Kohinoor Devanagari", "Devanagari Sangam MN", "Nirmala UI", "Mangal", "Noto Sans Devanagari",
                   "Lohit Devanagari", "FreeSans"),
    "thai": ("Thonburi", "Sukhumvit Set", "Leelawadee UI", "Leelawadee", "Tahoma", "Noto Sans Thai",
             "Noto Sans Thai Looped", "Loma", "Garuda", "Waree"),
}
for _system in ("latin-ext", "vietnamese", "cyrillic", "greek"):
    SYSTEM[_system] = SYSTEM["latin"]
del _system


def key(name):
    """Comparable form of a family name: case-folded, without spaces, hyphens and underscores."""
    return re.sub(r"[\s_\-]+", "", str(name)).casefold()


_BY_KEY = {key(n): fam for fam in FAMILIES for n in (fam.id, fam.name, *fam.aliases)}


def family(name):
    """The catalog family called `name` (id, family name or alias), or None."""
    return _BY_KEY.get(key(name))


def families(script=None, category=None):
    """Families in catalog order, optionally only those whose main writing system or category matches."""
    return [f for f in FAMILIES
            if (script is None or f.script == script) and (category is None or f.category == category)]


def suggestions(name, extra=(), limit=4):
    """Family names from the catalog (and `extra`, such as installed families) that look like `name`, closest
    first."""
    wanted = key(name)
    scored = {}
    for pool, cutoff, bonus in (({key(n): f.name for f in FAMILIES for n in (f.id, f.name, *f.aliases)}, 0.6, 0.01),
                                ({key(n): n for n in extra if not n.startswith(".")}, 0.75, 0)):
        for k, shown in pool.items():
            score = difflib.SequenceMatcher(None, wanted, k).ratio()
            score = max(score, 0.9 if len(wanted) >= 3 and wanted in k else 0) + bonus
            if score >= cutoff and score > scored.get(shown, 0):
                scored[shown] = score
    return sorted(scored, key=lambda shown: (-scored[shown], shown))[:limit]


def role_families(role, system):
    """Catalog ids (or system family names for the "ui" role) to try for a role and writing system, best first."""
    role = ROLE_ALIASES.get(role, role)
    if role == "ui":
        return SYSTEM.get(system, ()) + ROLES["body"].get(system, ())
    table = ROLES.get(role, ROLES["body"])
    latin = table.get("latin", ()) if system in ("latin-ext", "vietnamese", "cyrillic", "greek") else ()
    out = []
    for fid in table.get(system, ()) + latin + ROLES["body"].get(system, ()):
        if fid not in out:
            out.append(fid)
    return tuple(out)
