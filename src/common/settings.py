"""
settings.py - project settings for SilverGrass (pure standard library; Python 3.11+ incl. Blender's Python).

Precedence (later wins):
    DEFAULTS  <  [tool.silvergrass] in pyproject.toml  <  silvergrass.local.toml (optional, git-ignored)
    <  environment (SILVERGRASS_<SECTION>_<KEY>)

Usage:
    import settings
    settings.get("render", "slots")          # -> 2
    settings.tool("ffmpeg")                  # -> absolute path or the bare name (let the OS resolve it)
    settings.font("calligraphy")             # -> absolute path of a matching font file, or "" if none found
"""
import glob
import os
import shutil
import sys

try:
    import tomllib
except ModuleNotFoundError:          # Python < 3.11
    tomllib = None

ROOT = os.environ.get("SILVERGRASS_ROOT") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

DEFAULTS = {
    "paths": {"out_dir": "out", "final_video": "assets/film/芒原决战_Final.mp4", "lock_dir": ""},
    "tools": {"blender": "", "ffmpeg": "", "ffprobe": "", "python": ""},
    "fonts": {"calligraphy": "", "weibei": "", "kaiti": "", "song": "", "ui": "", "mono": ""},
    "render": {"width": 1920, "height": 816, "preview_scale": 0.3333, "samples_final": 16, "samples_preview": 8,
               "motion_blur": True, "mb_shutter": 0.5, "mb_steps": 1, "mb_steps_sparks": 2, "mb_max_px": 40,
               "filter_size": 1.5, "shadow_pool_mb": 1024, "volumetric_tile": 8, "volumetric_samples": 64,
               "png_depth": "8", "png_compression": 15,
               "grass_density_final": 1.0, "grass_density_preview": 0.25, "grass_density_layout": 0.12,
               "slots": 2, "lock": True, "min_free_mem_gb": 4.5, "expected_seconds_per_frame": 12.0, "retries": 2,
               "watchdog_factor": 3.0, "watchdog_grace_s": 120.0, "progress_interval_s": 30.0,
               "tmp_max_age_s": 600.0},
    "video": {"delivery_width": 1920, "delivery_height": 1080, "codec": "libx264", "crf": 16, "preset": "slow",
              "pix_fmt": "yuv420p", "audio_bitrate": "320k", "preview_width": 960, "preview_height": 540,
              "preview_crf": 23, "preview_preset": "veryfast", "preview_audio_bitrate": "192k",
              "review_crf": 20, "review_audio_bitrate": "128k"},
    "audio": {"sample_rate": 48000, "target_lufs": -14.0, "true_peak_db": -1.0, "loudness_tolerance_lu": 1.0,
              "aac_pre_limiter_db": -2.5},
    "post": {"title_jobs": 0, "titles_lock_timeout_s": 900.0},
    "dev": {"demo_raise": False},
}

# conventional aliases that are honoured in addition to SILVERGRASS_<SECTION>_<KEY>
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
    if tomllib is None or not os.path.isfile(path):
        return {}
    with open(path, "rb") as fh:
        return tomllib.load(fh)


def _merge(base, extra):
    for sec, vals in (extra or {}).items():
        if isinstance(vals, dict):
            base.setdefault(sec, {}).update(vals)
    return base


def load(root=ROOT):
    data = {sec: dict(vals) for sec, vals in DEFAULTS.items()}
    _merge(data, _load_toml(os.path.join(root, "pyproject.toml")).get("tool", {}).get("silvergrass", {}))
    _merge(data, _load_toml(os.path.join(root, "silvergrass.local.toml")))
    for sec, vals in data.items():
        for key, val in list(vals.items()):
            env = os.environ.get(f"SILVERGRASS_{sec}_{key}".upper())
            if env is None and (sec, key) in ENV_ALIASES:
                env = os.environ.get(ENV_ALIASES[(sec, key)])
            if env is not None and env != "":
                vals[key] = _coerce(env, DEFAULTS.get(sec, {}).get(key, val))
    return data


SETTINGS = load()


def get(section, key, default=None):
    return SETTINGS.get(section, {}).get(key, default)


def path(section, key):
    """A settings path resolved against the repository root."""
    p = os.path.expanduser(str(get(section, key, "")))
    return p if (not p or os.path.isabs(p)) else os.path.join(ROOT, p)


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
        for cand in (os.path.join(ROOT, ".venv", "Scripts", "python.exe"), os.path.join(ROOT, ".venv", "bin", "python")):
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
}


def _font_dirs():
    home = os.path.expanduser("~")
    dirs = [os.path.join(ROOT, "assets", "fonts")]
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
    """Font file for a role ('calligraphy' | 'weibei' | 'kaiti' | 'song' | 'ui' | 'mono'): the settings/env value if set,
    else the first known candidate found on this machine, else ''."""
    explicit = get("fonts", role, "")
    if explicit:
        return os.path.expanduser(explicit)
    idx = _font_index()
    for name in FONT_CANDIDATES.get(role, []):
        hit = idx.get(name.lower())
        if hit:
            return hit
    return ""
