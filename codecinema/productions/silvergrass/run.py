#!/usr/bin/env python3
"""
run.py — one entry point for the whole Duel in the Silver Grass (SilverGrass) pipeline.

    codecinema run silvergrass check                         # toolchain + fonts + deps
    codecinema run silvergrass build   [--lanes all] [--quality final|preview|layout]
    codecinema run silvergrass preview <lane> [--quality layout|preview] [--step 2]
    codecinema run silvergrass render  [--shots S02-S05] [--slots 2]
    codecinema run silvergrass audio                         # score + SFX + mix from out/events.json
    codecinema run silvergrass titles                        # calligraphy title cards
    codecinema run silvergrass assemble [--preview] [--range START END]
    codecinema run silvergrass all     [--slots 2]           # build -> render -> audio -> titles -> assemble

Lanes: prologue, act1a, act1b, act2, act3, finale (see codecinema/productions/silvergrass/common/config.py).
Run it with the project's Python environment (e.g. `codecinema run silvergrass ...`). Tools, fonts, render and
encoding settings come from the film settings in pyproject.toml (+ film.local.toml, SILVERGRASS_*
environment variables).
"""

from codecinema.productions import film_root, source_root
import argparse
import os
import re
import shutil
import subprocess
import sys

ROOT = str(film_root("silvergrass"))
sys.path.insert(0, os.path.join(str(source_root("silvergrass")), "common"))
import config  # noqa: E402

PY = sys.executable
BLENDER = config.BLENDER_BIN


def _run(cmd, **kw):
    print("\n$ " + " ".join(str(c) for c in cmd), flush=True)
    return subprocess.call([str(c) for c in cmd], cwd=ROOT, **kw)


def _blender(script, *args):
    return _run(config.blender_cmd(script, *args))


def cmd_check(a):
    ok = True
    def row(name, good, info, required=True):
        nonlocal ok
        ok &= bool(good) or not required
        print(f"  [{'ok' if good else ('!!' if required else '--')}] {name:14s} {info}")
    print("toolchain")
    need = "Blender " + ".".join(str(v) for v in config.MIN_BLENDER_VERSION) + "+"
    has_b = os.path.exists(BLENDER) or shutil.which(BLENDER) is not None
    ver, ver_ok = "", False
    if has_b:
        try:
            ver = subprocess.run([BLENDER, "--version"], capture_output=True, text=True, timeout=60).stdout.splitlines()[0]
        except Exception as exc:   # noqa: BLE001
            ver = f"(could not run: {exc})"
        m = re.search(r"Blender\s+(\d+)\.(\d+)", ver)
        ver_ok = bool(m) and (int(m.group(1)), int(m.group(2))) >= tuple(config.MIN_BLENDER_VERSION)
    row("blender", has_b and ver_ok, (ver if ver_ok else f"{ver} (needs {need})") if ver else
        f"not found at {BLENDER} (set [tools] blender or $BLENDER_BIN; needs {need})")
    for tool, path in (("ffmpeg", config.FFMPEG), ("ffprobe", config.FFPROBE)):
        ok_path = os.path.isabs(path) and os.path.exists(path) or shutil.which(path)
        row(tool, ok_path, path if ok_path else f"not found (install ffmpeg or set [tools] {tool})")
    py_ok = os.path.exists(config.PYTHON) or shutil.which(config.PYTHON) is not None
    py_info = config.PYTHON if os.path.abspath(config.PYTHON) == os.path.abspath(PY) else \
        f"{config.PYTHON}  (running: {PY})"
    row("python", py_ok, py_info if py_ok else f"not found: {config.PYTHON} (set [tools] python)")
    for mod in ("numpy", "scipy", "PIL", "matplotlib", "pyloudnorm"):
        try:
            __import__(mod)
            row(f"py:{mod}", True, "")
        except ImportError:
            row(f"py:{mod}", False, "missing - run: pip install .")
    print("fonts (titles; set [fonts] in film.local.toml or $SILVERGRASS_FONTS_<ROLE>)")
    for k in ("FONT_CALLIGRAPHY", "FONT_WEIBEI", "FONT_KAITI", "FONT_SONG"):
        p = getattr(config, k)
        row(k, bool(p) and os.path.exists(p), p or "not found - set it in film.local.toml")
    print("optional fonts (diagnostic + contact sheets; a default font is used when missing)")
    for k in ("FONT_UI", "FONT_MONO"):
        p = getattr(config, k)
        row(k, bool(p) and os.path.exists(p), p or "not found (optional)", required=False)
    print("\nall good" if ok else "\nsome checks failed (see above)")
    return 0 if ok else 1


def cmd_build(a):
    return _blender(str(source_root("silvergrass") / 'blender/build_scene.py'), "--lanes", a.lanes, "--quality", a.quality)


def cmd_preview(a):
    return _run([PY, str(source_root("silvergrass") / 'tools/lane_preview.py'), a.lane, "--quality", a.quality, "--step", str(a.step)])


def cmd_render(a):
    args = [PY, str(source_root("silvergrass") / 'render_supervisor.py'), "--blend", config.SCENE_BLEND, "--quality", "final",
            "--out", config.FRAMES_DIR, "--slots", str(a.slots)]
    if a.shots:
        args += ["--shots", a.shots]
    env = dict(os.environ, SILVERGRASS_RENDER_SLOTS=str(a.slots))
    return _run(args, env=env)


def cmd_audio(a):
    return _run([PY, str(source_root("silvergrass") / 'audio/mix.py'), "--strict"])


def cmd_titles(a):
    return _run([PY, str(source_root("silvergrass") / 'post/titles.py')])


def cmd_assemble(a):
    args = [PY, str(source_root("silvergrass") / 'post/assemble.py'), "--preview" if a.preview else "--final", "--frames", config.FRAMES_DIR,
            "--audio", "auto"]
    if a.range:
        args += ["--range", str(a.range[0]), str(a.range[1])]
    return _run(args)


def cmd_all(a):
    steps = [
        ("build", lambda: cmd_build(argparse.Namespace(lanes="all", quality="final"))),
        ("render", lambda: cmd_render(argparse.Namespace(shots=None, slots=a.slots))),
        ("audio", lambda: cmd_audio(a)),
        ("titles", lambda: cmd_titles(a)),
        ("assemble", lambda: cmd_assemble(argparse.Namespace(preview=False, range=None))),
    ]
    for name, fn in steps:
        print(f"\n===== {name} =====", flush=True)
        rc = fn()
        if rc != 0:
            print(f"step '{name}' failed (exit {rc}); fix it and re-run - finished work is kept and resumed")
            return rc
    print(f"\ndone -> {config.FINAL_VIDEO}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check").set_defaults(fn=cmd_check)
    p = sub.add_parser("build"); p.add_argument("--lanes", default="all")
    p.add_argument("--quality", default="final", choices=["layout", "preview", "final"]); p.set_defaults(fn=cmd_build)
    p = sub.add_parser("preview"); p.add_argument("lane", choices=config.LANES)
    p.add_argument("--quality", default="layout", choices=["layout", "preview"])
    p.add_argument("--step", type=int, default=2); p.set_defaults(fn=cmd_preview)
    p = sub.add_parser("render"); p.add_argument("--shots", default=None, help="e.g. S02-S05 (default: all)")
    p.add_argument("--slots", type=int, default=config.RENDER_SLOTS); p.set_defaults(fn=cmd_render)
    sub.add_parser("audio").set_defaults(fn=cmd_audio)
    sub.add_parser("titles").set_defaults(fn=cmd_titles)
    p = sub.add_parser("assemble"); p.add_argument("--preview", action="store_true")
    p.add_argument("--range", nargs=2, type=int, metavar=("START", "END")); p.set_defaults(fn=cmd_assemble)
    p = sub.add_parser("all"); p.add_argument("--slots", type=int, default=config.RENDER_SLOTS); p.set_defaults(fn=cmd_all)
    a = ap.parse_args()
    sys.exit(a.fn(a))


if __name__ == "__main__":
    main()
