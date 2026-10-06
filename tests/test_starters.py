"""User-facing creation, editing and media regressions; all projects live in temporary workspaces."""
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import importlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

from codecinema import cli, projects, starters

ROOT = Path(__file__).resolve().parents[1]
HAS_MEDIA = bool(shutil.which("ffmpeg") and shutil.which("ffprobe") and importlib.util.find_spec("skia"))


class Workspace(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="codecinema-test-")
        self.root = Path(self.temp.name)
        (self.root / "films").mkdir()
        self.previous = Path.cwd()
        os.chdir(self.root)
        self.environment = patch.dict(os.environ, {"PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8"})
        self.environment.start()

    def tearDown(self):
        os.chdir(self.previous)
        self.environment.stop()
        self.temp.cleanup()

    def command(self, *args):
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            result = cli.main(list(args))
        return result, output.getvalue()

    def child(self, *args):
        return subprocess.run([sys.executable, "-m", "codecinema", *args], cwd=self.root, env=os.environ,
                              capture_output=True, text=True, encoding="utf-8")


class CreationTests(Workspace):
    def test_title_is_data_and_survives_quotes_newlines_and_tokens(self):
        title = 'A "quoted" \\ title\n__FILM_ID__ __ENV_PREFIX__ $(not-a-command)'
        code, _ = self.command("new", "quoted-title", "--title", title)
        self.assertEqual(code, 0)
        path = self.root / "films" / "quoted-title"
        meta = tomllib.loads((path / "film.toml").read_text())
        self.assertEqual(meta["film"]["title"], title)
        self.assertEqual(json.loads((path / "scenes.json").read_text())["title"], title)
        compile((path / "src/run.py").read_text(), str(path / "src/run.py"), "exec")
        self.assertNotIn(title, (path / "src/run.py").read_text())

    def test_eight_presets_create_editable_valid_stories(self):
        self.assertEqual(len(starters.PRESETS), 8)
        for preset in starters.PRESETS:
            code, _ = self.command("new", preset, "--preset", preset, "--duration", "15")
            self.assertEqual(code, 0)
            data = projects.read_starter(self.root / "films" / preset)
            self.assertAlmostEqual(starters.validate_story(data), 15)
            self.assertTrue(all(s["preset"] == preset for s in data["scenes"]))

    def test_invalid_id_duration_color_and_missing_tools_leave_no_project(self):
        for args in (("../escape",), ("bad", "--duration", "nan"), ("bad", "--duration", "0"),
                     ("bad", "--accent", "red"), ("bad", "--open")):
            self.assertEqual(self.command("new", *args)[0], 1)
        with patch("codecinema.diagnostics.starter_problems", return_value=["Install FFmpeg first"]):
            self.assertEqual(self.command("new", "bad", "--render")[0], 1)
        self.assertEqual(list((self.root / "films").iterdir()), [])

    def test_new_never_overwrites_existing_film(self):
        self.assertEqual(self.command("new", "keep-me")[0], 0)
        story = self.root / "films" / "keep-me" / "scenes.json"
        before = story.read_bytes()
        self.assertEqual(self.command("new", "keep-me", "--preset", "neon")[0], 1)
        self.assertEqual(story.read_bytes(), before)

    def test_native_loader_error_is_reported_before_creation(self):
        original = importlib.import_module
        def unavailable(name):
            if name == "skia":
                raise ImportError("libGL.so.1: cannot open shared object file")
            return original(name)
        with patch("codecinema.diagnostics.importlib.import_module", side_effect=unavailable):
            result, output = self.command("new", "missing-runtime", "--render")
        self.assertEqual(result, 1)
        self.assertIn("libGL.so.1", output)
        self.assertFalse((self.root / "films" / "missing-runtime").exists())

    def test_customization_preserves_scene_order_and_saves_previous_version(self):
        self.command("new", "editable", "--title", "Original")
        path = self.root / "films" / "editable"
        original = (path / "scenes.json").read_bytes()
        code, _ = self.command("customize", "editable", "--title", 'A "New" Title', "--preset", "neon",
                               "--duration", "24", "--format", "portrait", "--quality", "high", "--accent", "#bada55")
        self.assertEqual(code, 0)
        data = projects.read_starter(path)
        self.assertEqual([s["camera"] for s in data["scenes"]], ["wide", "drift", "close"])
        self.assertAlmostEqual(starters.validate_story(data), 24)
        self.assertEqual(data["scenes"][0]["title"], 'A "New" Title')
        video = tomllib.loads((path / "film.toml").read_text())["settings"]["video"]
        self.assertEqual((video["width"], video["height"]), (1080, 1920))
        backups = list((path / "out" / "edits").glob("*/scenes.json"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(json.loads(backups[0].read_bytes()), json.loads(original))

    def test_invalid_edit_does_not_change_saved_story_or_manifest(self):
        self.command("new", "editable")
        path = self.root / "films" / "editable"
        before = {name: (path / name).read_bytes() for name in ("scenes.json", "film.toml")}
        self.assertEqual(self.command("customize", "editable", "--accent", "not-a-color")[0], 1)
        self.assertEqual({name: (path / name).read_bytes() for name in before}, before)
        self.assertFalse((path / "out" / "edits").exists())


@unittest.skipUnless(HAS_MEDIA, "FFmpeg and Skia are required for the media integration test")
class MediaTests(Workspace):
    def test_create_customize_preview_and_stale_assembly(self):
        result = self.child("new", "sample", "--preset", "cosmos", "--duration", "3", "--quality", "preview", "--render")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        path = self.root / "films" / "sample"
        master = path / "assets" / "film" / "sample.mp4"
        self.assertTrue(master.is_file())
        result = self.child("customize", "sample", "--preset", "neon", "--format", "portrait", "--render")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads((path / "out" / "master" / "qc.json").read_text())
        self.assertEqual((report["width"], report["height"], report["frames"]), (360, 640, 72))
        before = hashlib.sha256(master.read_bytes()).hexdigest()
        result = self.child("run", "sample", "all", "--quality", "preview")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(hashlib.sha256(master.read_bytes()).hexdigest(), before)
        self.assertTrue((path / "assets" / "film" / "sample_preview.mp4").is_file())
        data = projects.read_starter(path)
        data["scenes"][0]["subtitle"] = "A changed caption"
        (path / "scenes.json").write_text(json.dumps(data))
        result = self.child("run", "sample", "assemble")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("different settings", result.stderr)
        self.assertEqual(hashlib.sha256(master.read_bytes()).hexdigest(), before)


if __name__ == "__main__":
    unittest.main()
