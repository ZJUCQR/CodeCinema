"""One isolated process per film, including its audio settings and Blender jobs."""

import os
from pathlib import Path
import runpy
import sys


def main():
    if len(sys.argv) < 3:
        raise SystemExit("Use: codecinema run <film> <step>")
    path = Path(sys.argv[1]).resolve()
    os.environ["CODECINEMA_FILM_DIR"] = str(path)
    os.chdir(path)
    from codecinema.films import Film
    from codecinema.productions import source_root

    film = Film(path)
    args = sys.argv[2:]
    film.command(args[0])  # validate before importing production dependencies
    if film.legacy_entry:
        # Previously created, possibly customized projects remain runnable.
        entry = path / film.legacy_entry
    elif film.production == "story":
        from codecinema.pipeline import main as produce

        return produce(args)
    else:
        entry = source_root(film.production) / "run.py"
    sys.path.insert(0, str(entry.parent))
    sys.argv = [str(entry), *args]
    runpy.run_path(str(entry), run_name="__main__")
    return 0


if __name__ == "__main__":
    sys.exit(main())
