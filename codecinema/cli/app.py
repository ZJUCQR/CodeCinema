"""
CodeCinema command line.

    codecinema list                          list the registered films with their steps and requirements
    codecinema run <film> [step] [args ...]  run a film's step (default: all), e.g. `codecinema run nightrevels audio`
    codecinema new <id> [--render]           create a film from scene data; add --render to produce it immediately
    codecinema customize <film> [--render]   change a film's renderer, story and look without editing Python
    codecinema studio                        open the local visual editor: choose, customize and render
    codecinema presets                       list the starter looks and output options
    codecinema renderers                     list built-in and installed rendering backends
    codecinema check                         check the toolchain and Python packages

Run `codecinema <command> -h` to see a command's options.
`python -m codecinema ...` works the same without installing the console script.
"""
import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

from codecinema import __version__, renderers
from codecinema.runtime import diagnostics
from codecinema.workspace import films, projects, settings
from codecinema.workspace import story as starters
from codecinema.workspace.paths import films_dir


def cmd_list(a):
    fs = films.discover()
    if not fs:
        print("no films found in films/")
        return 1
    for f in fs.values():
        zh = f"  {f.title_zh}" if f.title_zh else ""
        print(f"{f.id:14s} {f.title}{zh}")
        if f.description:
            print(f"{'':14s} {f.description}")
        print(f"{'':14s} steps: {', '.join(f.steps)}" + (f"   needs: {', '.join(f.requires)}" if f.requires else ""))
    return 0


def cmd_run(a):
    fs = films.discover()
    if a.film not in fs:
        print(f"unknown film '{a.film}'. Films: {', '.join(fs) or '(none)'}")
        return 1
    return fs[a.film].run(a.step, a.args)


def cmd_new(a):
    if not re.fullmatch(r"[a-z][a-z0-9_-]*", a.id):
        print("film id: lower-case letters, digits, '-' or '_', starting with a letter")
        return 1
    dest = os.path.join(films_dir(), a.id)
    if os.path.exists(dest):
        print(f"{dest} already exists")
        return 1
    try:
        seconds = starters.duration(a.duration if a.duration is not None else 12.0)
        if a.accent is not None and not re.fullmatch(r"#[0-9a-fA-F]{6}", a.accent):
            raise ValueError("accent must be a hex color such as #c5e8db")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if a.open and not a.render:
        print("--open requires --render; use: codecinema new <id> --render --open", file=sys.stderr)
        return 1
    if a.render:
        problems = diagnostics.starter_problems(a.renderer or "skia")
        if problems:
            print("\n".join(problems), file=sys.stderr)
            return 1
    story = json.loads(Path(a.story).read_text(encoding="utf-8")) if a.story else None
    if story is not None:
        story = starters.revise_story(story, title=a.title, subtitle=a.subtitle,
                                      preset=a.preset, seconds=a.duration, accent=a.accent)
        seconds = starters.validate_story(story)
    preset = a.preset or "moonrise"
    title = a.title or a.id.replace("-", " ").replace("_", " ").title()
    w, h = projects.create(dest, title=title, preset=preset, seconds=seconds, subtitle=a.subtitle,
                            format_name=a.format, quality=a.quality, accent=a.accent, renderer=a.renderer,
                            story=story)
    looks = ", ".join(sorted({scene["preset"] for scene in story["scenes"]})) if story else preset
    print(f"Created {os.path.relpath(dest)} · {looks} · {seconds:g}s · {w}×{h}", flush=True)
    if a.render:
        args = ["--open"] if a.open else []
        result = films.Film(dest).run("all", args)
        if result:
            print(f"The project is saved. After fixing the error, retry: codecinema run {a.id} all", file=sys.stderr)
        return result
    print(f"Render: codecinema run {a.id} all\nCustomize: {os.path.relpath(dest)}/scenes.json")
    return 0


def cmd_renderers(a):
    for name, spec in renderers.available().items():
        print(f"{name:12s} {spec['description']}")
    return 0


def cmd_presets(a):
    for name, preset in starters.PRESETS.items():
        print(f"{name:12s} {preset['description']}")
    print('\nTry: codecinema new myfilm --preset aurora --title "My Film" --render')
    print("Formats: landscape, portrait, square. Quality: preview (360p), standard (720p), high (1080p).")
    return 0


def cmd_customize(a):
    found = films.discover()
    if a.film not in found:
        print(f"Unknown film '{a.film}'. Run: codecinema list", file=sys.stderr)
        return 1
    if a.open and not a.render:
        print("--open requires --render", file=sys.stderr)
        return 1
    if a.render:
        problems = diagnostics.starter_problems(a.renderer or found[a.film].renderer)
        if problems:
            print("\n".join(problems), file=sys.stderr)
            return 1
    film = found[a.film]
    projects.customize(film.dir, title=a.title, subtitle=a.subtitle, preset=a.preset, seconds=a.duration,
                       format_name=a.format, quality=a.quality, accent=a.accent, renderer=a.renderer,
                       story=json.loads(Path(a.story).read_text(encoding="utf-8")) if a.story else None)
    print(f"Updated {a.film}; the previous settings are saved in out/edits/.", flush=True)
    if a.render:
        return films.Film(film.dir).run("all", ["--open"] if a.open else [])
    print(f"Render: codecinema run {a.film} all")
    return 0


def cmd_studio(a):
    from codecinema.studio import serve
    return serve(port=a.port, open_browser=not a.no_open)


def cmd_check(a):
    ok = True
    missing_tools = False
    for mod in ("numpy", "scipy", "PIL", "matplotlib", "pyloudnorm", "skia"):
        try:
            __import__(mod)
            print(f"  [ok] py:{mod}")
        except (ImportError, OSError) as exc:
            ok = False
            print(f"  [!!] py:{mod}  {exc}")
            print("       " + (diagnostics.graphics_help() if mod == "skia" else "Run: python -m pip install ."))
    for tool in ("ffmpeg", "ffprobe", "blender"):
        p = settings.tool(tool)
        found = os.path.isabs(p) and os.path.exists(p) or shutil.which(p)
        need = tool != "blender"
        missing_tools |= bool(need and not found)
        ok &= bool(found) or not need
        print(f"  [{'ok' if found else ('!!' if need else '--')}] {tool:8s} {p if found else 'not found'}"
              + ("" if need else "   (only needed by Blender films)"))
    print("\nall good" if ok else "\nsome checks failed")
    if missing_tools:
        print(diagnostics.ffmpeg_help())
    if not ok:
        print("Setup guide: README.md#quick-start")
    return 0 if ok else 1


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):        # film titles may be non-Latin (Windows consoles default to cp1252)
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(prog="codecinema", description=f"CodeCinema {__version__}: films made with code.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="List the registered films with their steps and requirements")
    sub.add_parser("renderers", help="List built-in and installed rendering backends")
    r = sub.add_parser("run", help="Run one production step of a film (default: all)")
    r.add_argument("film", help="Film ID (see codecinema list)")
    r.add_argument("step", nargs="?", default="all", help="Production step (default: all)")
    r.add_argument("args", nargs=argparse.REMAINDER, help="Options passed to the step, e.g. --quality preview")
    n = sub.add_parser("new", help="Create a film from scene data; add --render to produce it immediately")
    n.add_argument("id")
    n.add_argument("--renderer", default="skia", help="Rendering backend (see codecinema renderers)")
    n.add_argument("--story", help="Import scene JSON, then apply any explicitly supplied story options")
    n.add_argument("--title")
    n.add_argument("--subtitle", help="Opening caption (edit all captions later in scenes.json)")
    n.add_argument("--accent", help="Accent color, e.g. '#c5e8db'")
    n.add_argument("--preset", choices=starters.PRESETS, help="Look (default: moonrise, or imported story looks)")
    n.add_argument("--duration", type=float, metavar="SECONDS", help="Total runtime (default: 12, or imported story duration)")
    n.add_argument("--format", choices=starters.FORMATS, default="landscape")
    n.add_argument("--quality", choices=starters.QUALITIES, default="standard", help="default: standard (720p)")
    n.add_argument("--render", action="store_true", help="Create, render, synthesize sound, assemble and verify")
    n.add_argument("--open", action="store_true", help="Open the finished MP4 with your default player (requires --render)")
    sub.add_parser("presets", help="List the starter looks and output options")
    c = sub.add_parser("customize", help="Change a film's renderer, story and look without editing Python")
    c.add_argument("film")
    c.add_argument("--renderer", help="Switch the rendering backend")
    c.add_argument("--story", help="Replace the story with a scene JSON file")
    c.add_argument("--title")
    c.add_argument("--subtitle")
    c.add_argument("--preset", choices=starters.PRESETS)
    c.add_argument("--duration", type=float, metavar="SECONDS")
    c.add_argument("--format", choices=starters.FORMATS)
    c.add_argument("--quality", choices=starters.QUALITIES)
    c.add_argument("--accent")
    c.add_argument("--render", action="store_true")
    c.add_argument("--open", action="store_true")
    studio = sub.add_parser("studio", help="Open the local visual editor: choose, customize and render")
    studio.add_argument("--port", type=int, default=8787)
    studio.add_argument("--no-open", action="store_true", help="Print the address without opening a browser")
    sub.add_parser("check", help="Check the toolchain and Python packages")
    a = ap.parse_args(argv)
    try:
        return {"list": cmd_list, "run": cmd_run, "new": cmd_new, "check": cmd_check,
                "presets": cmd_presets, "renderers": cmd_renderers, "customize": cmd_customize, "studio": cmd_studio}[a.cmd](a)
    except (OSError, ValueError) as exc:
        print(f"codecinema: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
