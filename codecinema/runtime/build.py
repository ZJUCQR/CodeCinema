"""Bundle shared editor, starter and font resources without packaging film media."""

from pathlib import Path
import shutil

from setuptools.command.build_py import build_py


class BuildPy(build_py):
    def run(self):
        super().run()
        source = Path(__file__).resolve().parents[2] / "assets" / "_shared"
        target = Path(self.build_lib) / "codecinema" / "_assets"
        for name in ("studio", "scaffold", "fonts"):
            shutil.copytree(source / name, target / name, dirs_exist_ok=True)

    def get_outputs(self, include_bytecode=1):
        outputs = super().get_outputs(include_bytecode)
        target = Path(self.build_lib) / "codecinema" / "_assets"
        return outputs + [str(p) for p in sorted(target.rglob("*")) if p.is_file()]
