"""Exercise Studio's local HTTP contract, media seeking and a real visual-editor render."""
import http.client
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from codecinema import cli, projects, starters
from codecinema.studio import Handler, Studio
from test_starters import HAS_MEDIA, ROOT


class StudioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="codecinema-studio-test-")
        self.root = Path(self.temp.name)
        (self.root / "films").mkdir()
        self.previous = Path.cwd()
        os.chdir(self.root)
        self.environment = patch.dict(os.environ, {"PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8"})
        self.environment.start()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.studio = Studio(self.root)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        os.chdir(self.previous)
        self.environment.stop()
        self.temp.cleanup()

    def request(self, method, path, data=None, token=True, extra=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-CodeCinema-Token"] = self.server.studio.token
        headers.update(extra or {})
        connection.request(method, path, json.dumps(data) if data is not None else None, headers)
        response = connection.getresponse()
        status, returned, body = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return status, returned, body

    def test_bootstrap_static_assets_and_invalid_requests(self):
        status, _, body = self.request("GET", "/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)["presets"]), 8)
        for route in ("/", "/studio.js", "/studio.css", "/presets/neon.jpg"):
            self.assertEqual(self.request("GET", route)[0], 200)
        payload = {"id": "valid", "story": starters.make_story("My Film"), "format": "landscape", "quality": "standard"}
        self.assertEqual(self.request("POST", "/api/render", payload, token=False)[0], 403)
        self.assertEqual(self.request("POST", "/api/render", payload, extra={"Origin": "https://example.com"})[0], 403)
        payload["id"] = "../escape"
        self.assertEqual(self.request("POST", "/api/render", payload)[0], 400)
        self.assertEqual(list((self.root / "films").iterdir()), [])
        self.assertEqual(self.request("GET", "/media/../../film.toml")[0], 404)

    def test_byte_range_requests_and_head(self):
        self.assertEqual(cli.main(["new", "ranges"]), 0)
        folder = self.root / "films" / "ranges" / "assets" / "film"
        folder.mkdir(parents=True)
        (folder / "ranges.mp4").write_bytes(bytes(range(256)) * 8)
        route = "/media/ranges/ranges.mp4"
        status, headers, body = self.request("GET", route, extra={"Range": "bytes=100-199"})
        self.assertEqual((status, len(body)), (206, 100))
        self.assertEqual(headers["Content-Range"], "bytes 100-199/2048")
        self.assertEqual(body, bytes(range(100, 200)))
        self.assertEqual(self.request("GET", route, extra={"Range": "bytes=-17"})[2], (bytes(range(256)) * 8)[-17:])
        self.assertEqual(self.request("GET", route, extra={"Range": "bytes=3000-"})[0], 416)
        self.assertEqual(self.request("GET", route, extra={"Range": "bytes=-0"})[0], 416)
        self.assertEqual(self.request("HEAD", route)[2], b"")

    @unittest.skipUnless(HAS_MEDIA, "FFmpeg and Skia are required for the Studio render")
    def test_render_mixed_scenes_and_edit_an_existing_project(self):
        story = starters.make_story('My "Mixed" Film', "ocean", 3)
        story["scenes"][1]["preset"] = "ink"
        payload = {"id": "visual-film", "story": story, "format": "square", "quality": "preview", "preview": True}
        self.assertEqual(self.request("POST", "/api/render", payload)[0], 202)
        job = self.wait_for_job()
        self.assertEqual(job["status"], "done", job["log"])
        self.assertEqual(self.request("GET", job["video"], extra={"Range": "bytes=0-127"})[0], 206)
        saved = projects.read_starter(self.root / "films" / "visual-film")
        self.assertEqual(saved["scenes"][1]["preset"], "ink")
        payload.update(existing=True, preview=False)
        payload["story"]["scenes"][0]["subtitle"] = "Edited in Studio"
        self.assertEqual(self.request("POST", "/api/render", payload)[0], 202)
        job = self.wait_for_job()
        self.assertEqual(job["status"], "done", job["log"])
        report = json.loads((self.root / "films/visual-film/out/master/qc.json").read_text())
        self.assertEqual((report["width"], report["height"], report["frames"]), (360, 360, 72))
        self.assertTrue((self.root / "films/visual-film/assets/film/visual-film_preview.mp4").is_file())

    def wait_for_job(self):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            job = json.loads(self.request("GET", "/api/state")[2])["job"]
            if job["status"] != "running":
                return job
            time.sleep(0.1)
        self.fail("Studio render did not complete in 30 seconds")


if __name__ == "__main__":
    unittest.main()
