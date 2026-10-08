"""Produce a cartoon film from films/<id>/screenplay.json.

    codecinema run <film> plan        compile the screenplay, paint face atlases, print the timeline
    codecinema run <film> voices      speak every line (recordings, neural or system voice, or babble)
    codecinema run <film> stills      one frame per shot -> out/storyboard.jpg
    codecinema run <film> render      every frame with Blender (resumable; --preview for a fast low-res pass)
    codecinema run <film> audio       score, dialogue, Foley, effects and ambience -> out/audio/mix.wav
    codecinema run <film> assemble    grade, titles, subtitles and the final MP4
    codecinema run <film> qc          verify the master
    codecinema run <film> all         everything above in order
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from codecinema.workspace import settings
from codecinema.workspace.paths import IMPORT_ROOT, film_assets

STEPS = ("plan", "voices", "stills", "render", "audio", "assemble", "qc")


class Production:
    def __init__(self, options):
        self.options = options
        self.film = Path(settings.ROOT)
        self.out = Path(settings.path("paths", "out_dir") or self.film / "out")
        self.assets = film_assets(self.film)
        final = settings.path("paths", "final_video")
        meta = settings.film_meta(str(self.film))
        self.final = Path(final) if final else self.assets / "film" / f"{meta.get('id', self.film.name)}.mp4"
        self.preview = bool(getattr(options, "preview", False))
        width, height = int(settings.get("video", "width", 1920)), int(settings.get("video", "height", 1080))
        if self.preview:
            scale = float(settings.get("render", "preview_scale", 0.5))
            width, height = int(width * scale) // 2 * 2, int(height * scale) // 2 * 2
            self.final = self.final.with_name(self.final.stem + "_preview.mp4")
        self.width, self.height = width, height
        self.frames_dir = self.out / ("preview_frames" if self.preview else "frames")

    # ------------------------------------------------------------------ helpers
    @property
    def plan_path(self):
        return self.out / "plan.json"

    def load_plan(self):
        if not self.plan_path.is_file():
            raise SystemExit("No plan yet. Run: codecinema run <film> plan")
        return json.loads(self.plan_path.read_text(encoding="utf-8"))

    def voices(self):
        path = self.out / "voices" / "voices.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}

    def engine(self):
        engine = str(settings.get("render", "engine", "eevee")).lower()
        return "CYCLES" if engine == "cycles" else "BLENDER_EEVEE"

    def font(self):
        return settings.font("display_cjk") or settings.font("kaiti") or ""

    def blender(self, frames, folder, samples, force=False, label="render"):
        job = {"import_root": str(IMPORT_ROOT), "plan": str(self.plan_path),
               "voices": str(self.out / "voices" / "voices.json"), "folder": str(folder), "frames": list(frames),
               "width": self.width, "height": self.height, "samples": samples, "engine": self.engine(),
               "font": self.font(), "force": force}
        jobs_dir = self.out / "jobs"
        jobs_dir.mkdir(parents=True, exist_ok=True)
        path = jobs_dir / f"{label}-{frames[0]:05d}-{frames[-1]:05d}.json"
        path.write_text(json.dumps(job), encoding="utf-8")
        script = Path(__file__).parent / "blender" / "render.py"
        cmd = [settings.tool("blender"), "-b", "--factory-startup", "--python-exit-code", "1", "--python", str(script),
               "--", str(path)]
        env = dict(os.environ, CODECINEMA_FILM_DIR=str(self.film), PYTHONIOENCODING="utf-8")
        log = jobs_dir / f"{label}-{frames[0]:05d}.log"
        with log.open("w", encoding="utf-8") as fh:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env,
                                    encoding="utf-8", errors="replace")
            for line in proc.stdout:
                fh.write(line)
                if line.startswith("CARTOON") or "Error" in line or "Traceback" in line:
                    yield line.rstrip()
            if proc.wait() != 0:
                raise RuntimeError(f"Blender failed; see {log}")

    # ------------------------------------------------------------------ steps
    def cmd_plan(self):
        from codecinema.cartoon import faces, screenplay
        source = self.film / "screenplay.json"
        if not source.is_file():
            raise SystemExit(f"Missing {source}")
        plan = screenplay.compile_file(source, self.film)
        for cid, info in plan["cast"].items():
            info["atlas"] = faces.paint(info["spec"]["face"], self.out / "faces")
        data = json.loads(source.read_text(encoding="utf-8"))
        plan["scene_marks"] = {s.get("id"): s.get("marks", {}) for s in data["scenes"]}
        self.out.mkdir(parents=True, exist_ok=True)
        partial = self.plan_path.with_suffix(".partial.json")
        partial.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        partial.replace(self.plan_path)
        print(screenplay.summary(plan), flush=True)
        for warning in screenplay.timing_warnings(plan, self.voices()):
            print(f"  ! {warning}", flush=True)
        from codecinema.audio import sfx
        known = set(sfx.names())
        unknown = sorted({e["name"] for e in plan["audio"]["sfx"]} - known)
        if unknown:
            raise SystemExit(f"Unknown sound effects: {', '.join(unknown)}. Library: {', '.join(sorted(known))}")

    def cmd_voices(self):
        from codecinema.cartoon.voices import Casting
        plan = self.load_plan()
        engine = getattr(self.options, "speech_engine", "auto")
        Casting(plan, self.out / "voices", self.assets, engine).run(keep=getattr(self.options, "keep_voices", False))

    def cmd_stills(self):
        plan = self.load_plan()
        frames = []
        for shot in plan["shots"]:
            mid = (shot["start"] + shot["end"]) / 2
            frames.append(max(1, min(plan["frames"], int(mid * plan["fps"]) + 1)))
        frames = sorted(set(frames))
        folder = self.out / "stills"
        keep = (self.width, self.height)
        self.width, self.height = 960, 540
        try:
            for line in self.blender(frames, folder, 8, force=True, label="stills"):
                print(line, flush=True)
        finally:
            self.width, self.height = keep
        self._contact(plan, folder, frames)

    def _contact(self, plan, folder, frames):
        from PIL import Image, ImageDraw
        tiles = []
        for f in frames:
            path = folder / f"{f:05d}.png"
            if path.is_file():
                im = Image.open(path).convert("RGB")
                im.thumbnail((480, 270))
                shot = next(s for s in plan["shots"] if s["start"] <= (f - 1) / plan["fps"] < s["end"] + 1e-6)
                tiles.append((im, f"{shot['id']}  {shot['start']:.1f}s"))
        if not tiles:
            return
        cols = 5
        w, h = tiles[0][0].size
        sheet = Image.new("RGB", (cols * w, math.ceil(len(tiles) / cols) * (h + 26)), "#14161d")
        draw = ImageDraw.Draw(sheet)
        for i, (im, label) in enumerate(tiles):
            x, y = (i % cols) * w, (i // cols) * (h + 26)
            sheet.paste(im, (x, y))
            draw.text((x + 8, y + h + 6), label, fill="#dfe3ea")
        sheet.save(self.out / "storyboard.jpg", quality=88)
        print(f"Storyboard: {self.out / 'storyboard.jpg'}", flush=True)

    def frame_list(self, plan):
        spec = getattr(self.options, "frames", None)
        total = plan["frames"]
        if not spec:
            return list(range(1, total + 1))
        out = []
        for part in spec.split(","):
            if "-" in part:
                a, b = part.split("-")
                out += range(int(a), int(b) + 1)
            elif part.endswith("s"):
                out.append(int(float(part[:-1]) * plan["fps"]) + 1)
            else:
                out.append(int(part))
        return sorted(f for f in set(out) if 1 <= f <= total)

    def cmd_render(self):
        plan = self.load_plan()
        frames = self.frame_list(plan)
        todo = [f for f in frames if not (self.frames_dir / f"{f:05d}.png").exists()]
        if getattr(self.options, "force", False):
            todo = frames
        if not todo:
            print(f"All {len(frames)} frames are rendered.", flush=True)
            return
        jobs = max(1, int(getattr(self.options, "jobs", 0) or settings.get("render", "jobs", 2)))
        samples = int(settings.get("render", "samples_preview" if self.preview else "samples", 8 if self.preview
                                   else 16))
        chunks = [todo[i::jobs] for i in range(jobs)] if jobs > 1 else [todo]
        # Contiguous ranges keep each process inside few scenes (fewer sets to build).
        if jobs > 1:
            size = math.ceil(len(todo) / jobs)
            chunks = [todo[i:i + size] for i in range(0, len(todo), size)]
        begin = time.monotonic()
        print(f"Rendering {len(todo)} frames at {self.width}×{self.height} with {len(chunks)} Blender process(es)",
              flush=True)
        done = [0]

        def run(chunk):
            for line in self.blender(chunk, self.frames_dir, samples, force=getattr(self.options, "force", False)):
                if line.startswith("CARTOON"):
                    done[0] += 1
                    if done[0] % 24 == 0 or done[0] == len(todo):
                        rate = (time.monotonic() - begin) / done[0]
                        left = rate * (len(todo) - done[0])
                        print(f"  {done[0]}/{len(todo)} frames · {rate:.2f}s/frame · ~{left / 60:.1f} min left",
                              flush=True)
                else:
                    print(line, flush=True)

        with ThreadPoolExecutor(max_workers=len(chunks)) as pool:
            list(pool.map(run, chunks))

    def cmd_audio(self):
        from codecinema.audio import mixer
        from codecinema.cartoon import camera as directing
        from codecinema.cartoon import motion, sets
        from codecinema.cartoon.screenplay import hash_seed
        plan = self.load_plan()
        voices = self.voices()
        audio = dict(plan["audio"])
        tracks = {cid: motion.Track(cid, info["spec"], info["metrics"], plan["tracks"][cid], seed=hash_seed(cid))
                  for cid, info in plan["cast"].items()}
        director = directing.Director(tracks, {}, self.width / self.height)

        def pan_of(x, y, t):
            """Stereo position of a point as seen by the shot's camera at time t."""
            shot = next((s for s in plan["shots"] if s["start"] <= t < s["end"]), plan["shots"][-1])
            scene = next(s for s in plan["scenes"] if s["id"] == shot["scene"])
            spec = plan["sets"][scene["set"]]
            ground = sets.ground_function(spec)
            for tr in tracks.values():
                tr.ground = ground
            director.ground = ground
            director.marks = dict(spec["marks"])
            try:
                view = director.solve(shot, t)
            except ValueError:
                return 0.0, 5.0
            cx, cy, _ = view["pos"]
            tx, ty, _ = view["target"]
            fx, fy = tx - cx, ty - cy
            norm = math.hypot(fx, fy) or 1.0
            rx, ry = fy / norm, -fx / norm
            dx, dy = x - cx, y - cy
            depth = max(0.5, (dx * fx + dy * fy) / norm)
            side = (dx * rx + dy * ry) / depth
            return max(-0.8, min(0.8, side * 0.9)), math.hypot(dx, dy)

        dialogue = []
        for line in plan.get("lines", []):
            take = voices.get(line["id"])
            if not take:
                continue
            p, _ = tracks[line["who"]].position(line["t"])
            pan, dist = pan_of(p[0], p[1], line["t"])
            dialogue.append({"t": line["t"], "file": take["file"], "who": line["who"], "pan": pan * 0.5,
                             "gain_db": float(line.get("gain_db", 0.0)), "distance": dist})
        audio["dialogue"] = dialogue
        for row in audio.get("foley", []):
            pan, dist = pan_of(row["x"], row["y"], row["t"])
            row["pan"], row["distance"] = pan, dist
        for row in audio.get("sfx", []):
            if row.get("pos"):
                pan, dist = pan_of(row["pos"][0], row["pos"][1], row["t"])
                row.setdefault("pan", pan)
                row.setdefault("distance", dist)
        audio["master"] = {"target_lufs": float(settings.get("audio", "target_lufs", -16.0)),
                           "true_peak_db": float(settings.get("audio", "true_peak_db", -1.0)),
                           **plan["audio"].get("master", {})}
        report = mixer.mix(audio, self.out / "audio")
        print(json.dumps(report, indent=1)[:1200], flush=True)

    def cmd_assemble(self):
        from codecinema.cartoon import finish
        plan = self.load_plan()
        voices = self.voices()
        missing = [f for f in range(1, plan["frames"] + 1) if not (self.frames_dir / f"{f:05d}.png").exists()]
        if missing:
            raise SystemExit(f"{len(missing)} frames are missing (first: {missing[0]}). Run the render step.")
        mix = self.out / "audio" / "mix.wav"
        if not mix.is_file():
            raise SystemExit("No mix yet. Run the audio step.")
        titles = []
        for k, title in enumerate(plan.get("titles", [])):
            path = finish.title_card(title, self.width, self.height, self.out / "titles" / f"title{k}.png")
            titles.append((title, path))
        subs = []
        for lang in ("en", "zh"):
            text = finish.subtitles(plan, voices, lang)
            if text.strip():
                path = self.out / f"subtitles.{lang}.srt"
                path.write_text(text, encoding="utf-8")
                (self.out / f"subtitles.{lang}.vtt").write_text(finish.subtitles(plan, voices, lang, "vtt"),
                                                                 encoding="utf-8")
                subs.append((lang, path))
        graph, label = finish.video_filters(plan, titles, first_input=2)
        fps = plan["fps"]
        cmd = [settings.tool("ffmpeg"), "-v", "error", "-stats", "-y", "-framerate", str(fps), "-i",
               str(self.frames_dir / "%05d.png"), "-i", str(mix)]
        for title, path in titles:
            cmd += ["-loop", "1", "-framerate", str(fps), "-t", f"{title['dur']:.3f}", "-i", str(path)]
        first_sub = 2 + len(titles)
        for lang, path in subs:
            cmd += ["-i", str(path)]
        cmd += ["-filter_complex", graph, "-map", f"[{label}]", "-map", "1:a"]
        for k in range(len(subs)):
            cmd += ["-map", f"{first_sub + k}:0"]
        crf = int(settings.get("video", "crf", 18)) + (5 if self.preview else 0)
        cmd += ["-c:v", "libx264", "-crf", str(crf), "-preset", "veryfast" if self.preview else
                str(settings.get("video", "preset", "slow")), "-tune", "animation", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", str(settings.get("video", "audio_bitrate", "256k")),
                # An explicit length: -shortest would stop at the last subtitle cue.
                "-movflags", "+faststart", "-t", f"{plan['frames'] / fps:.3f}"]
        if subs:
            cmd += ["-c:s", "mov_text"]
            for k, (lang, _) in enumerate(subs):
                cmd += [f"-metadata:s:s:{k}", f"language={'eng' if lang == 'en' else 'chi'}",
                        f"-metadata:s:s:{k}", f"title={'English' if lang == 'en' else '中文'}"]
        cmd += ["-metadata", f"title={plan['title']}"]
        self.final.parent.mkdir(parents=True, exist_ok=True)
        partial = self.final.with_name(self.final.stem + ".partial.mp4")
        cmd.append(str(partial))
        subprocess.run(cmd, check=True)
        partial.replace(self.final)
        for lang, path in subs:
            shutil.copy(path.with_suffix(".vtt"), self.final.with_name(f"{self.final.stem}.{lang}.vtt"))
        print(f"Master: {self.final}", flush=True)

    def cmd_qc(self):
        from codecinema.runtime import media
        plan = self.load_plan()
        if not self.final.is_file():
            raise SystemExit("No finished film yet. Run assemble.")
        info = media.probe(str(self.final))
        problems = []
        if abs(info["duration"] - plan["duration"]) > 0.15:
            problems.append(f"duration {info['duration']:.2f}s, expected {plan['duration']:.2f}s")
        if info.get("width") != self.width or info.get("height") != self.height:
            problems.append(f"size {info.get('width')}×{info.get('height')}")
        if not info.get("audio_rate"):
            problems.append("no audio")
        report = self.out / "audio" / "report.json"
        if report.is_file():
            loud = json.loads(report.read_text(encoding="utf-8"))
            lufs = loud.get("integrated_lufs", loud.get("lufs"))
            if lufs is not None and abs(lufs - float(settings.get("audio", "target_lufs", -16.0))) > 1.5:
                problems.append(f"loudness {lufs:.1f} LUFS")
        (self.out / "qc.json").write_text(json.dumps({"passed": not problems, "problems": problems, **info}, indent=1),
                                          encoding="utf-8")
        if problems:
            raise SystemExit("QC failed: " + "; ".join(problems))
        print(f"Verified: {self.final} ({info['duration']:.2f}s, {info['width']}×{info['height']}, picture + sound)",
              flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="codecinema run <film>", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step", nargs="?", default="all", choices=STEPS + ("all",))
    parser.add_argument("--preview", action="store_true", help="Half-size, low-sample frames for a quick full pass")
    parser.add_argument("--frames", help="Render only these frames, e.g. 1-48,120 or 12.5s")
    parser.add_argument("--jobs", type=int, help="Parallel Blender processes (default: render.jobs)")
    parser.add_argument("--force", action="store_true", help="Re-render frames that already exist")
    parser.add_argument("--speech-engine", choices=("auto", "local", "system", "babble", "recording"), default="auto")
    parser.add_argument("--keep-voices", action="store_true",
                        help="Store takes as recordings in assets/<film>/voices so every platform reproduces them")
    parser.add_argument("--open", action="store_true", help="Open the finished film")
    options = parser.parse_args(argv)
    from codecinema.cartoon.screenplay import ScreenplayError
    production = Production(options)
    steps = STEPS if options.step == "all" else (options.step,)
    for step in steps:
        print(f"== {step}", flush=True)
        try:
            getattr(production, f"cmd_{step}")()
        except ScreenplayError as exc:        # a mistake in screenplay.json: the message names the scene, shot and beat
            print(f"error: {exc}", file=sys.stderr, flush=True)
            return 1
    if options.open and production.final.is_file():
        if sys.platform == "darwin":
            subprocess.run(["open", str(production.final)])
        elif sys.platform == "win32":
            os.startfile(str(production.final))
        else:
            subprocess.run(["xdg-open", str(production.final)])
    return 0


if __name__ == "__main__":
    sys.exit(main())
