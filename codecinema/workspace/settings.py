"""
codecinema.workspace.settings - per-film settings (pure standard library; Python 3.11+, including Blender's Python).

Every film lives in films/<id>/ and is registered under [tool.codecinema.films.<id>] in pyproject.toml.
Settings precedence (later wins):
    framework DEFAULTS  <  the film's .settings tables  <  film.local.toml (optional, git-ignored)
    <  environment: <ENV_PREFIX>_<SECTION>_<KEY> (prefix from env_prefix), CODECINEMA_<SECTION>_<KEY>
       and the aliases BLENDER_BIN / FFMPEG / FFPROBE

The active film is $CODECINEMA_FILM_DIR (set by the CLI and by each film's own entry point) or, failing that, the
registered film directory containing the working directory.

Usage:
    from codecinema.workspace import settings
    settings.get("render", "slots")          # -> 2
    settings.tool("ffmpeg")                  # -> absolute path or the bare name (let the OS resolve it)
    settings.font("calligraphy")             # -> absolute path of a matching font file, or "" if none found
"""
import copy
import glob
import os
import shutil
import sys
import tomllib
from pathlib import Path

from codecinema.workspace import registry
from codecinema.workspace.paths import film_assets, project_root, resolve_path

REPO = project_root(os.environ.get("CODECINEMA_FILM_DIR"))


def _find_film_dir():
    d = os.environ.get("CODECINEMA_FILM_DIR")
    if d:
        return os.path.abspath(d)
    cur = os.path.abspath(os.getcwd())
    while True:
        if registry.film_config(cur):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return REPO
        cur = parent


ROOT = _find_film_dir()               # the active film's content directory

DEFAULTS = {
    "paths": {"out_dir": "out"},
    "tools": {"blender": "", "ffmpeg": "", "ffprobe": "", "python": ""},
    "fonts": {"calligraphy": "", "weibei": "", "kaiti": "", "song": "", "ui": "", "mono": "", "display": "",
              "display_cjk": ""},
    "video": {"width": 1920, "height": 1080, "fps": 24, "codec": "libx264", "crf": 16, "preset": "slow",
              "pix_fmt": "yuv420p", "audio_bitrate": "320k"},
    "audio": {"sample_rate": 48000, "target_lufs": -14.0, "true_peak_db": -1.0,
              "soundbank": "auto"},   # "auto" (download GeneralUser GS once, else synthesize) | "off" | path to an .sf2
}

# conventional aliases honoured in addition to the prefixed variables
ENV_ALIASES = {("tools", "blender"): "BLENDER_BIN", ("tools", "ffmpeg"): "FFMPEG", ("tools", "ffprobe"): "FFPROBE"}


def _coerce(value, like):
    if isinstance(like, bool):
        return str(value).strip().lower() in ("1", "true", "yes", "on")
    if isinstance(like, int):
        return int(float(value))
    if isinstance(like, float):
        return float(value)
    return str(value)


def _load_toml(path):
    if not os.path.isfile(path):
        return {}
    with open(path, "rb") as fh:
        return tomllib.load(fh)


def _merge(base, extra):
    for sec, vals in (extra or {}).items():
        if isinstance(vals, dict):
            base.setdefault(sec, {}).update(vals)
    return base


def film_meta(film_dir=None):
    """Metadata from [tool.codecinema.films.<id>] in the workspace pyproject.toml."""
    film_dir = film_dir or ROOT
    config = registry.film_config(film_dir)
    if not config:
        return {}
    return {**{key: value for key, value in config.items() if key != "settings"}, "id": Path(film_dir).name}


def load(film_dir=None):
    film_dir = film_dir or ROOT
    data = copy.deepcopy(DEFAULTS)
    _merge(data, registry.film_config(film_dir).get("settings", {}))
    _merge(data, _load_toml(os.path.join(film_dir, "film.local.toml")))
    prefix = str(film_meta(film_dir).get("env_prefix", "")).upper()
    for sec, vals in data.items():
        for key, val in list(vals.items()):
            env = None
            for pre in ([prefix] if prefix else []) + ["CODECINEMA"]:
                env = os.environ.get(f"{pre}_{sec}_{key}".upper())
                if env is not None:
                    break
            if env is None and (sec, key) in ENV_ALIASES:
                env = os.environ.get(ENV_ALIASES[(sec, key)])
            if env is not None and env != "":
                vals[key] = _coerce(env, val)
    return data


SETTINGS = load()


def get(section, key, default=None):
    return SETTINGS.get(section, {}).get(key, default)


def path(section, key):
    """Resolve assets/ from the workspace and other relative paths from the film."""
    p = str(get(section, key, ""))
    return str(resolve_path(p, ROOT)) if p else ""


# ------------------------------------------------------------------------------------------------ tools
_BLENDER_CANDIDATES = {
    "darwin": ["/Applications/Blender.app/Contents/MacOS/Blender",
               os.path.expanduser("~/Applications/Blender.app/Contents/MacOS/Blender")],
    "win32": sorted(glob.glob(r"C:\Program Files\Blender Foundation\Blender*\blender.exe"), reverse=True),
    "linux": ["/usr/bin/blender", "/snap/bin/blender", "/opt/blender/blender"],
}


def tool(name):
    """Absolute path of an external tool: settings/env override, then PATH, then standard install locations.
    Falls back to the bare name so a missing tool fails with a clear 'not found' at call time."""
    explicit = get("tools", name, "")
    if explicit:
        return os.path.expanduser(explicit)
    if name == "python":            # the project's interpreter (numpy/scipy/matplotlib), also when called from Blender
        for cand in [os.path.join(d, ".venv", sub) for d in (ROOT, REPO)
                     for sub in (os.path.join("Scripts", "python.exe"), os.path.join("bin", "python"))]:
            if os.path.exists(cand):
                return cand
        return shutil.which("python3") or shutil.which("python") or sys.executable
    found = shutil.which(name)
    if found:
        return found
    if name == "blender":
        for cand in _BLENDER_CANDIDATES.get(sys.platform if sys.platform in _BLENDER_CANDIDATES else "linux", []):
            if os.path.exists(cand):
                return cand
    return name


# ------------------------------------------------------------------------------------------------ fonts
FONT_CANDIDATES = {
    "calligraphy": ["Xingkai.ttc", "STXINGKA.TTF", "ZhiMangXing-Regular.ttf", "MaShanZheng-Regular.ttf",
                    "LiuJianMaoCao-Regular.ttf", "LXGWWenKai-Regular.ttf"],
    "weibei": ["WeibeiSC-Bold.otf", "WeibeiTC-Bold.otf", "STXINWEI.TTF", "MaShanZheng-Regular.ttf",
               "LXGWWenKai-Bold.ttf", "LXGWWenKai-Regular.ttf"],
    "kaiti": ["Kaiti.ttc", "STKAITI.TTF", "simkai.ttf", "LXGWWenKai-Regular.ttf", "NotoSerifCJK-Regular.ttc",
              "NotoSerifSC-Regular.otf"],
    "song": ["Songti.ttc", "STSONG.TTF", "simsun.ttc", "NotoSerifCJK-Regular.ttc", "NotoSerifSC-Regular.otf",
             "LXGWWenKai-Regular.ttf"],
    "ui": ["Arial.ttf", "arial.ttf", "Helvetica.ttc", "DejaVuSans.ttf", "LiberationSans-Regular.ttf",
           "NotoSans-Regular.ttf"],
    "mono": ["Menlo.ttc", "consola.ttf", "DejaVuSansMono.ttf", "LiberationMono-Regular.ttf",
             "NotoSansMono-Regular.ttf"],
    # Bundled in assets/_shared/fonts (SIL Open Font License), so titles look the same on every platform.
    "display": ["Fredoka.ttf", "Arial Rounded Bold.ttf", "DejaVuSans-Bold.ttf", "Arial.ttf"],
    "display_cjk": ["ZCOOLKuaiLe-Regular.ttf", "LXGWWenKai-Regular.ttf", "NotoSansCJK-Regular.ttc", "PingFang.ttc",
                    "msyh.ttc", "Songti.ttc"],
}


def _font_dirs():
    home = os.path.expanduser("~")
    package = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # The workspace's shared fonts, then the copies bundled with the package (wheel or source checkout).
    dirs = [str(film_assets(ROOT) / "fonts"), os.path.join(REPO, "assets", "_shared", "fonts"),
            os.path.join(package, "_assets", "fonts"), os.path.join(os.path.dirname(package), "assets", "_shared", "fonts")]
    if sys.platform == "darwin":
        dirs += ["/System/Library/Fonts", "/System/Library/Fonts/Supplemental", "/Library/Fonts",
                 os.path.join(home, "Library", "Fonts")]
        dirs += glob.glob("/System/Library/AssetsV2/com_apple_MobileAsset_Font*/*/AssetData")
    elif sys.platform == "win32":
        dirs += [os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
                 os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts")]
    else:
        dirs += ["/usr/share/fonts", "/usr/local/share/fonts", os.path.join(home, ".fonts"),
                 os.path.join(home, ".local", "share", "fonts")]
    return [d for d in dirs if d and os.path.isdir(d)]


_FONT_INDEX = None


def _font_index():
    global _FONT_INDEX
    if _FONT_INDEX is None:
        _FONT_INDEX = {}
        for d in _font_dirs():
            for dirpath, _dirs, files in os.walk(d):
                for fn in files:
                    _FONT_INDEX.setdefault(fn.lower(), os.path.join(dirpath, fn))
    return _FONT_INDEX


def font(role):
    """Font file for a role ('calligraphy' | 'weibei' | 'kaiti' | 'song' | 'ui' | 'mono' | 'display' | 'display_cjk'):
    the settings/env value if set,
    else the first known candidate found on this machine, else ''."""
    explicit = get("fonts", role, "")
    if explicit:
        return str(resolve_path(explicit, ROOT))
    idx = _font_index()
    for name in FONT_CANDIDATES.get(role, []):
        hit = idx.get(name.lower())
        if hit:
            return hit
    return ""
