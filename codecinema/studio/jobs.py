"""Studio project state and background production jobs."""

import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
from pathlib import Path

from codecinema import renderers
from codecinema.runtime import diagnostics
from codecinema.workspace import films, projects, settings
from codecinema.workspace import story as starters
from codecinema.workspace.paths import IMPORT_ROOT

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
        package_root = str(IMPORT_ROOT)
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
