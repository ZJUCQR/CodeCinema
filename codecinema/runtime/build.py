"""Bundle shared editor, starter and font resources without packaging film media."""

from fnmatch import fnmatch
from pathlib import Path
import shutil

from setuptools.command.build_py import build_py
from setuptools.command.sdist import sdist

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "assets" / "_shared"
BUNDLED = ("studio", "scaffold", "fonts")
SKIP = ("__pycache__", "*.py[cod]", ".DS_Store")


class BuildPy(build_py):
    def run(self):
        super().run()
        target = Path(self.build_lib) / "codecinema" / "_assets"
        for name in BUNDLED:
            shutil.copytree(SHARED / name, target / name, dirs_exist_ok=True, ignore=shutil.ignore_patterns(*SKIP))

    def get_outputs(self, include_bytecode=1):
        outputs = super().get_outputs(include_bytecode)
        target = Path(self.build_lib) / "codecinema" / "_assets"
        return outputs + [str(p) for p in sorted(target.rglob("*")) if p.is_file()]


class Sdist(sdist):
    """Source archives carry the same folders, so a wheel built from one is complete."""

    def make_release_tree(self, base_dir, files):
        extra = [path.relative_to(ROOT).as_posix()
                 for name in BUNDLED for path in sorted((SHARED / name).rglob("*"))
                 if path.is_file() and not any(fnmatch(part, skip) for part in path.parts for skip in SKIP)]
        super().make_release_tree(base_dir, [*files, *extra])
