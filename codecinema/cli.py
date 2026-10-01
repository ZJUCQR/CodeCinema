"""
CodeCinema command line.

    codecinema list                          the films in films/ and their steps
    codecinema run <film> <step> [args ...]  run one step of a film (e.g. `codecinema run nightrevels all`)
    codecinema new <id> [--title "..."]      start a new film from the template (films/<id>/)
    codecinema check                         toolchain and Python packages

`python -m codecinema ...` works the same without installing the console script.
"""
import argparse
import os
import re
import shutil
import sys

from codecinema import FILMS_DIR, __version__, films, settings


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
    dest = os.path.join(FILMS_DIR, a.id)
    if os.path.exists(dest):
        print(f"{dest} already exists")
        return 1
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "template")
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__"))
    title = a.title or a.id.replace("-", " ").replace("_", " ").title()
    for root, _, files in os.walk(dest):
        for fn in files:
            p = os.path.join(root, fn)
            with open(p, encoding="utf-8") as fh:
                s = fh.read()
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(s.replace("__FILM_ID__", a.id).replace("__FILM_TITLE__", title)
                         .replace("__ENV_PREFIX__", re.sub(r"[^A-Z0-9]", "_", a.id.upper())))
    print(f"created {os.path.relpath(dest)}  ->  codecinema run {a.id} all")
    return 0


def cmd_check(a):
    ok = True
    for mod in ("numpy", "scipy", "PIL", "matplotlib", "pyloudnorm", "skia"):
        try:
            __import__(mod)
            print(f"  [ok] py:{mod}")
        except ImportError:
            ok = False
            print(f"  [!!] py:{mod}  missing - run: pip install .")
    for tool in ("ffmpeg", "ffprobe", "blender"):
        p = settings.tool(tool)
        found = os.path.isabs(p) and os.path.exists(p) or shutil.which(p)
        need = tool != "blender"
        ok &= bool(found) or not need
        print(f"  [{'ok' if found else ('!!' if need else '--')}] {tool:8s} {p if found else 'not found'}"
              + ("" if need else "   (only needed by Blender films)"))
    print("\nall good" if ok else "\nsome checks failed")
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="codecinema", description=f"CodeCinema {__version__}: films made with code.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    r = sub.add_parser("run")
    r.add_argument("film")
    r.add_argument("step")
    r.add_argument("args", nargs=argparse.REMAINDER)
    n = sub.add_parser("new")
    n.add_argument("id")
    n.add_argument("--title", default="")
    sub.add_parser("check")
    a = ap.parse_args(argv)
    return {"list": cmd_list, "run": cmd_run, "new": cmd_new, "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
