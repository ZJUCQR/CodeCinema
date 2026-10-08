"""Local HTTP transport and static assets for the Studio visual editor."""

import json
import mimetypes
import re
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from codecinema.workspace import projects
from codecinema.workspace import story as starters
from codecinema.workspace.paths import project_root

from .jobs import Studio

ASSETS = Path(__file__).with_name("assets")


class Handler(BaseHTTPRequestHandler):
    server_version = "CodeCinemaStudio/1.0"

    def log_message(self, *_):
        pass

    @property
    def studio(self):
        return self.server.studio

    def allowed_host(self):
        port = self.server.server_port
        return self.headers.get("Host") in (f"127.0.0.1:{port}", f"localhost:{port}")

    def json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        port = self.server.server_port
        origin = self.headers.get("Origin")
        if (not self.allowed_host() or self.headers.get("X-CodeCinema-Token") != self.studio.token or
                origin and origin not in (f"http://127.0.0.1:{port}", f"http://localhost:{port}")):
            return self.json({"error": "Open Studio at the local address printed in your terminal."}, 403)
        if urlsplit(self.path).path != "/api/render":
            return self.json({"error": "Unknown action"}, 404)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 262144:
                raise ValueError("The request is empty or too large.")
            payload = json.loads(self.rfile.read(length))
            self.studio.submit(payload)
            self.json({"ok": True}, 202)
        except (ValueError, OSError, TypeError) as exc:
            self.json({"error": str(exc)}, 400)

    def do_HEAD(self):
        self.do_GET(head=True)

    def do_GET(self, head=False):
        if not self.allowed_host():
            return self.json({"error": "Use localhost or 127.0.0.1."}, 403)
        route = unquote(urlsplit(self.path).path)
        if route == "/api/state":
            if head:
                self.send_response(200)
                self.end_headers()
                return
            try:
                return self.json(self.studio.snapshot())
            except (ValueError, OSError) as exc:
                return self.json({"error": str(exc)}, 400)
        path = None
        if route == "/":
            path = ASSETS / "index.html"
        elif route in ("/studio.css", "/studio.js"):
            path = ASSETS / route[1:]
        elif re.fullmatch(r"/presets/[a-z]+\.jpg", route) and Path(route).stem in starters.PRESETS:
            path = ASSETS / route[1:]
        else:
            match = re.fullmatch(r"/media/([a-z][a-z0-9_-]*)/([a-z][a-z0-9_-]*\.(?:mp4|jpg))", route)
            if match:
                folder = self.studio.project(match[1])
                try:
                    projects.read_starter(folder)
                    candidate = folder / "assets" / "film" / match[2]
                    if candidate.resolve().parent == (folder / "assets" / "film").resolve() and not candidate.is_symlink():
                        path = candidate
                except (ValueError, OSError):
                    pass
        if path is None or not path.is_file():
            return self.json({"error": "File not found"}, 404)
        self.send_file(path, head)

    def send_file(self, path, head=False):
        size = path.stat().st_size
        start, end, status = 0, size - 1, 200
        request = self.headers.get("Range")
        if request:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", request)
            if match and any(match.groups()):
                lo, hi = match.groups()
                if not lo:
                    start = max(0, size - int(hi))
                else:
                    start = int(lo)
                    end = min(size - 1, int(hi)) if hi else size - 1
                status = 206
            if not match or not any(match.groups()) or start > end or start >= size:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
        self.send_response(status)
        self.send_header("Content-Type", mimetypes.guess_type(str(path))[0] or "application/octet-stream")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'")
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if head:
            return
        try:
            with path.open("rb") as source:
                source.seek(start)
                left = end - start + 1
                while left:
                    chunk = source.read(min(65536, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass


def serve(port=8787, open_browser=True):
    if not 0 <= port <= 65535:
        raise ValueError("port must be between 0 and 65535")
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.studio = Studio(project_root())
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"CodeCinema Studio: {url}\nChoose a preset, edit your scenes, then press Render. Ctrl+C stops Studio.", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if server.studio.process and server.studio.process.poll() is None:
            server.studio.process.terminate()
        server.server_close()
    return 0
