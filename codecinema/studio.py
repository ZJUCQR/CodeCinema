"""A local visual editor for starter films. No account, API key or web dependencies."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import threading
import time
from urllib.parse import unquote, urlsplit
import webbrowser

from codecinema import diagnostics, films, project_root, projects, settings, starters, renderers

ASSETS = Path(__file__).with_name("studio_assets")
FILM_ID = re.compile(r"[a-z][a-z0-9_-]*")


class Studio:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.Lock()
        self.job = None
        self.process = None

    def project(self, film_id):
        if not isinstance(film_id, str) or not FILM_ID.fullmatch(film_id):
            raise ValueError("Use a film ID starting with a lowercase letter, followed by letters, digits, - or _.")
        path = self.root / "films" / film_id
        if path.is_symlink() or (path.exists() and path.resolve().parent != (self.root / "films").resolve()):
            raise ValueError("The project must be inside this workspace's films folder.")
        return path

    def existing(self):
        result = []
        for film in films.discover(str(self.root / "films")).values():
            if settings.film_meta(film.dir).get("production") == "story":
                path = self.project(film.id)
                story = projects.read_starter(path)
                video = settings.load(str(path))["video"]
                short = min(video["width"], video["height"])
                name = Path(settings.load(str(path))["paths"]["final_video"]).name
                result.append({"id": film.id, "story": story, "renderer": film.renderer,
                               "video": f"/media/{film.id}/{name}?v={time.time_ns()}" if (path / "assets" / "film" / name).is_file() else None,
                               "format": "square" if video["width"] == video["height"] else
                                         "landscape" if video["width"] > video["height"] else "portrait",
                               "quality": "high" if short >= 1080 else "standard" if short >= 720 else "preview"})
        return result

    def snapshot(self):
        with self.lock:
            job = json.loads(json.dumps(self.job))
        return {"token": self.token, "presets": starters.PRESETS, "projects": self.existing(),
                "problems": diagnostics.starter_problems(), "renderers": renderers.available(), "job": job}

    def submit(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("The request must be a JSON object.")
        path = self.project(payload.get("id"))
        story = payload.get("story")
        starters.validate_story(story)
        for name, choices in (("format", starters.FORMATS), ("quality", starters.QUALITIES)):
            if not isinstance(payload.get(name), str) or payload[name] not in choices:
                raise ValueError(f"Choose a valid {name}.")
        renderer = renderers.require(payload.get("renderer", "skia"))
        preview = payload.get("preview", False)
        if type(preview) is not bool:
            raise ValueError("preview must be true or false.")
        if path.exists():
            projects.read_starter(path)
            if payload.get("existing") is not True:
                raise ValueError("This ID already exists. Select it from My films to edit it, or choose a new ID.")
        elif payload.get("existing"):
            raise ValueError("This project no longer exists. Create a new film instead.")
        problems = diagnostics.starter_problems(renderer)
        if problems:
            raise ValueError("\n".join(problems))
        with self.lock:
            if self.job and self.job["status"] == "running":
                raise ValueError("A film is already rendering. Wait for it to finish.")
            self.job = {"id": path.name, "status": "running", "log": [], "video": None, "preview": preview}
        threading.Thread(target=self.render, args=(path, payload), daemon=True).start()

    def log(self, line):
        with self.lock:
            self.job["log"].append(line)
            self.job["log"] = self.job["log"][-100:]

    def command(self, args, cwd):
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        package_root = str(Path(__file__).resolve().parent.parent)
        env["PYTHONPATH"] = os.pathsep.join(filter(None, (package_root, env.get("PYTHONPATH"))))
        process = subprocess.Popen([sys.executable, *args], cwd=cwd, env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        self.process = process
        for line in process.stdout:
            self.log(line.rstrip())
        result = process.wait()
        process.stdout.close()
        self.process = None
        if result:
            raise ValueError("Rendering stopped. The details below explain what to fix; your project is saved.")

    def render(self, path, payload):
        try:
            if not path.exists():
                story = payload["story"]
                self.command(["-m", "codecinema", "new", path.name, "--title", story["title"],
                              "--preset", story["scenes"][0]["preset"], "--duration", str(starters.validate_story(story)),
                              "--format", payload["format"], "--quality", payload["quality"], "--renderer", payload.get("renderer", "skia")], self.root)
            projects.customize(path, story=payload["story"], format_name=payload["format"], quality=payload["quality"], renderer=payload.get("renderer", "skia"))
            film = films.Film(str(path))
            args = film.command("all")[1:]
            if payload.get("preview"):
                args += ["--quality", "preview"]
            self.command(args, path)
            name = Path(settings.load(str(path))["paths"]["final_video"]).name
            if payload.get("preview"):
                name = Path(name).stem + "_preview.mp4"
            with self.lock:
                self.job.update(status="done", video=f"/media/{path.name}/{name}?v={time.time_ns()}")
        except Exception as exc:
            self.log(str(exc))
            with self.lock:
                self.job["status"] = "error"


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
