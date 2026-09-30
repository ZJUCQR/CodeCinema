"""
render_supervisor.py - final render orchestration. Runs with the .venv Python.

    .venv/bin/python src/render_supervisor.py [--blend out/scene.blend] [--shots all | S05-S09 | S12,S13]
        [--quality final] [--out out/frames] [--slots N] [--mem-gb GB] [--spf S] [--retries N]
        [--grace S] [--dry-run] [--no-verify] [--allow-quality-mismatch] [--allow-unverified-build]
    (numeric defaults: settings [render] -> config.RENDER_*)

* One supervisor per output dir (exclusive procutil.lock_file on <out>/.supervisor.lock).  Children (Blender
  processes, own process groups) are recorded in <out>/logs/children.json and killed on SIGTERM / SIGINT / SIGHUP /
  exit; leftovers of a killed supervisor are killed at the next start.  Children also exit on their own when the
  supervisor dies (render_frames checks SILVERGRASS_SUPERVISOR_PID before every frame).
* The build is SNAPSHOTTED at start: <blend dir>/.render_snapshot_<sha16>.blend (+ its build report); every chunk
  renders from the snapshot, so rebuilding out/scene.blend during a long render never mixes versions (start a new
  run for a new build).  Every supervisor using a snapshot holds a lock on its own <snapshot>.<pid>.inuse file;
  a snapshot without a held .inuse lock is unused and deleted.
* Guards: the build report must belong to the blend (sha1), have status 'ok', and its quality must equal
  --quality (a preview build rendered at final quality keeps preview grass / content) - otherwise refuse
  (--allow-quality-mismatch / --allow-unverified-build override).
* Work unit = one shot (a chunk): `Blender -b --factory-startup <snapshot> --python-exit-code 1 --python
  src/blender/render_frames.py -- --start a --end b`; render_frames resumes (skips complete frames), writes
  <frame>.<pid>.tmp.png -> os.replace and takes a machine-wide render_lock slot per frame.
* Up to --slots chunks in parallel, a second one only when procutil.free_memory_gb() reports >= --mem-gb.
* Watchdog: a chunk is killed after config.RENDER_WATCHDOG_FACTOR (3) x expected + --grace s (expected = frames x
  seconds-per-frame, median of the frames already rendered, else --spf); time spent waiting for a render slot does
  not count.
* --retries (default 2) retries per chunk; if a shot still stalls, its first missing frame is rendered alone with
  motion blur OFF (poison-frame fallback, listed in the final summary + manifest) and the rest of the shot
  continues normally.
* Logs (<out>/logs/<shot>_try<n>.log) are written live, line by line, and grepped for 'Traceback' /
  'Shadow buffer full' (-> warnings in the manifest).
* Every frame of a finished chunk is verified with PIL (decode + expected size); broken frames are deleted and
  re-queued.
* manifest.json keeps per-shot fingerprints = sha1(the shot's CONTENT digest from the build report
  (build_scene.shot_digests: static data of everything visible in the shot + the animation key slices acting on
  it) + quality + render-time code (render_setup.py, render_frames.py) + render-time config (SHOT_RENDER,
  resolution, RENDER_SKIP)).  Builds without digests fall back to hashing ALL sources (whole config.py, every
  acts/*.py, every blender module): over-invalidates, never under-invalidates.  A changed fingerprint deletes
  that shot's frames before rendering.
* Progress (frames on disk) + ETA every config.RENDER_PROGRESS_S (30 s) to stdout and <out>/logs/supervisor.log; a
  final summary lists failed and motion-blur-off frames.  --dry-run prints the plan and changes nothing.
"""
import argparse
import atexit
import glob
import hashlib
import json
import os
import shutil
import signal
import statistics
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src", "common"))
import config  # noqa: E402
import procutil  # noqa: E402

RENDER_FRAMES = os.path.join(ROOT, "src", "blender", "render_frames.py")
RENDER_TIME_SOURCES = ("src/blender/render_setup.py", "src/blender/render_frames.py")
LOG_ALERTS = ("Traceback", "Shadow buffer full")
SNAPSHOT_PREFIX = ".render_snapshot_"
PROGRESS_EVERY = config.RENDER_PROGRESS_S


# =============================================================================================
# plan
# =============================================================================================
def load_build_report(blend):
    """build_report.json next to the blend (a snapshot has its own copy <snapshot>.build_report.json)."""
    own = os.path.splitext(os.path.abspath(blend))[0] + ".build_report.json"
    p = own if os.path.exists(own) else os.path.join(os.path.dirname(os.path.abspath(blend)), config.BUILD_REPORT_NAME)
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def all_shots(report):
    """Shots of the built blend (build report) or config.SHOTS."""
    shots = report.get("shots") or [dict(id=s["id"], start=s["start"], end=s["end"], lane=s["lane"])
                                    for s in config.SHOTS]
    return shots


def select_shots(shots, spec):
    if spec in (None, "", "all"):
        return list(shots)
    ids = [s["id"] for s in shots]
    out = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            out += shots[ids.index(a):ids.index(b) + 1]
        else:
            out.append(shots[ids.index(part)])
    return out


def shot_frames(shot):
    return [f for f in range(shot["start"], shot["end"] + 1)
            if not any(a <= f <= b for a, b in config.RENDER_SKIP)]


def config_digest(shot):
    """The render-time parts of config for `shot` (kept for build reports; the content digest covers the rest)."""
    keys = ("FPS", "RES_X", "RES_Y", "PREVIEW_SCALE", "TIME_WARP", "SLOWMO", "FULL_WHITE", "RENDER_SKIP",
            "PALETTE", "HANDOFF", "ACTS", "SCREEN_DIRECTION")
    d = {k: getattr(config, k, None) for k in keys}
    d["shot"] = next((s for s in config.SHOTS if s["id"] == shot["id"]), shot)
    d["shot_render"] = config.SHOT_RENDER.get(shot["id"])
    return json.dumps(d, sort_keys=True, default=str)


def config_hash(shot):
    """sha1 of config_digest(shot) (build_scene stores it per shot in build_report['shot_config'])."""
    return hashlib.sha1(config_digest(shot).encode()).hexdigest()[:20]


def _file_hash(rel):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return None
    with open(p, "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()[:16]


def file_sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def render_time_inputs(shot):
    """What render_frames adds on top of the blend: per-shot overrides + output format + render-time code."""
    return dict(shot_render=config.SHOT_RENDER.get(shot["id"]), res=[config.RES_X, config.RES_Y],
                preview_scale=config.PREVIEW_SCALE, code={k: _file_hash(k) for k in RENDER_TIME_SOURCES})


def fingerprint(shot, report, quality):
    """Render fingerprint of one shot: the shot's content digest (build_report['shot_digest']) + quality + the
    render-time inputs.  Without a digest (old / --no-digest builds) every source the build recorded is hashed
    (the whole config.py, every act module, every blender module) - over-invalidating but safe."""
    dig = (report.get("shot_digest") or {}).get(shot["id"])
    if dig:
        blob = dict(kind="content", digest=dig, quality=quality, build_quality=report.get("quality"),
                    render=render_time_inputs(shot))
    else:
        src = {k: v for k, v in (report.get("sources") or {}).items() if "/tests/" not in k}
        blob = dict(kind="sources", sources=src, config=(report.get("shot_config") or {}).get(shot["id"]),
                    quality=quality, build_quality=report.get("quality"), lanes=report.get("lanes"),
                    render=render_time_inputs(shot))
    return hashlib.sha1(json.dumps(blob, sort_keys=True, default=str).encode()).hexdigest()[:20]


# =============================================================================================
# frames
# =============================================================================================
def frame_path(out, f):
    return os.path.join(out, config.frame_name(f))


def verify_frame(path, size=None):
    """PIL decode check (+ expected size). Returns None if fine, else an error string."""
    from PIL import Image
    try:
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            im.load()
            if size is not None and tuple(im.size) != tuple(size):
                return f"size {im.size} != {size}"
            if im.mode not in ("RGB", "RGBA"):
                return f"mode {im.mode}"
    except Exception as e:                         # noqa: BLE001 - any decode failure = broken frame
        return f"{type(e).__name__}: {e}"
    return None


def missing_frames(out, frames):
    return [f for f in frames if not (os.path.exists(frame_path(out, f)) and os.path.getsize(frame_path(out, f)) > 64)]


def measured_spf(out):
    """Median seconds/frame from render_log.jsonl (None if no data)."""
    p = os.path.join(out, config.RENDER_LOG_NAME)
    if not os.path.exists(p):
        return None
    vals = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("ok") and r.get("seconds"):
                vals.append(float(r["seconds"]))
    return statistics.median(vals[-200:]) if vals else None


def mem_available_gb():
    """Free + reclaimable memory in GB (procutil: vm_stat / /proc/meminfo / GlobalMemoryStatusEx); None if unknown."""
    return procutil.free_memory_gb()


# =============================================================================================
# processes
# =============================================================================================
class _Pid:
    """Popen stand-in for procutil.terminate_tree on a child we did not start (a killed supervisor's leftover)."""

    def __init__(self, pid):
        self.pid = int(pid)

    def poll(self):
        return None if procutil.pid_alive(self.pid) else 0

    def kill(self):
        pass                                        # terminate_tree's fallback: the group is already gone


class Interrupted(Exception):
    pass


# =============================================================================================
# supervisor
# =============================================================================================
class Supervisor:
    def __init__(self, a):
        self.a = a
        self.src_blend = os.path.abspath(a.blend)
        self.blend = self.src_blend                   # -> the snapshot once acquired
        self.out = os.path.abspath(a.out)
        self.logs = os.path.join(self.out, "logs")
        self.report = load_build_report(self.src_blend)
        self.quality = a.quality
        self.manifest_path = os.path.join(self.out, "manifest.json")
        self.manifest = self._load_manifest()
        self.shots = select_shots(all_shots(self.report), a.shots)
        self.lock = threading.RLock()                 # re-entrant: the signal handler may run under it
        self.t0 = time.time()
        self.children = {}                            # pid -> dict(pgid, shot, started, cmd)
        self._procs = {}                              # pid -> Popen of the running children
        self.stopping = False
        self.running_items = {}
        self.fallback_frames = []
        self._out_lock = None
        self._snap_fh = None
        res = self.report.get("resolution") if self.report.get("quality") == self.quality else None
        self.size = None if (a.no_verify or not res) else tuple(res)     # decode-only check otherwise

    # ---- bookkeeping
    def _load_manifest(self):
        if os.path.exists(self.manifest_path):
            with open(self.manifest_path, encoding="utf-8") as f:
                return json.load(f)
        return dict(version=2, shots={})

    def save_manifest(self):
        if self.a.dry_run:
            return
        with self.lock:
            self._save_manifest()

    def _save_manifest(self):
        self.manifest.update(blend=self.src_blend, snapshot=self.blend, quality=self.quality,
                             build_sha1=self.report.get("blend_sha1") or getattr(self, "blend_sha1", None),
                             updated=time.strftime("%Y-%m-%d %H:%M:%S"))
        tmp = self.manifest_path + f".{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.manifest, f, indent=1)
        os.replace(tmp, self.manifest_path)

    def log(self, msg):
        line = f"[supervisor {time.strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        if not self.a.dry_run:
            os.makedirs(self.logs, exist_ok=True)
            with open(os.path.join(self.logs, "supervisor.log"), "a", encoding="utf-8") as f:
                f.write(line + "\n")

    # ---- guards
    def check_build(self):
        """Problems with the build for this render: (untrusted build problems, quality problem or None)."""
        rep, probs = self.report, []
        if not rep:
            probs.append("no build_report.json next to the blend")
            return probs, None
        st = rep.get("status")
        if st is not None and st != "ok":
            probs.append(f"build status is {st!r} (error: {str(rep.get('error', ''))[:200]})")
        sha = rep.get("blend_sha1")
        self.blend_sha1 = file_sha1(self.src_blend)
        if sha and sha != self.blend_sha1:
            probs.append("build_report.json does not belong to this blend (sha1 mismatch: rebuilt or copied?)")
        if not sha:
            self.log("note: build report without blend_sha1 (old build) - cannot verify it matches the blend")
        bq, qp = rep.get("quality"), None
        if bq and bq != self.quality:
            qp = (f"the blend was built at quality {bq!r} but --quality {self.quality!r} was asked: build-time "
                  f"content (grass density, ...) would not match; rebuild with --quality {self.quality} or pass "
                  f"--allow-quality-mismatch")
        return probs, qp

    # ---- locks / snapshot / children
    def acquire_out_lock(self):
        os.makedirs(self.out, exist_ok=True)
        p = os.path.join(self.out, ".supervisor.lock")
        fh = open(p, "a+")
        if not procutil.lock_file(fh):
            try:
                fh.seek(0)
                holder = fh.read().strip()
            except OSError:                            # Windows: the holder's byte-range lock also blocks reads
                holder = "?"
            fh.close()
            raise SystemExit(f"render_supervisor: another supervisor is rendering into {self.out} ({holder})")
        fh.seek(0)
        fh.truncate()
        fh.write(json.dumps(dict(pid=os.getpid(), since=time.strftime("%Y-%m-%d %H:%M:%S"), blend=self.src_blend)))
        fh.flush()
        self._out_lock = fh

    def snapshot(self):
        """Copy the blend (+ report) to <blend dir>/.render_snapshot_<sha16>.blend once and render from it."""
        sha = getattr(self, "blend_sha1", None) or file_sha1(self.src_blend)
        d = os.path.dirname(self.src_blend)
        snap = os.path.join(d, f"{SNAPSHOT_PREFIX}{sha[:16]}.blend")
        self._snap_fh = open(f"{snap}.{os.getpid()}.inuse", "a+")     # in use by this supervisor (before the copy)
        procutil.lock_file(self._snap_fh, blocking=True)
        if not os.path.exists(snap):
            tmp = snap + f".{os.getpid()}.tmp"
            shutil.copy2(self.src_blend, tmp)
            if file_sha1(tmp) != sha:
                os.remove(tmp)
                raise SystemExit("render_supervisor: the blend changed while it was being snapshotted - retry")
            os.replace(tmp, snap)
            self.log(f"snapshot {os.path.basename(snap)} ({os.path.getsize(snap) / 1e6:.0f} MB)")
        rep_copy = os.path.splitext(snap)[0] + ".build_report.json"
        if not os.path.exists(rep_copy):
            with open(rep_copy + ".tmp", "w", encoding="utf-8") as f:
                json.dump(self.report, f, indent=1)
            os.replace(rep_copy + ".tmp", rep_copy)
        self.blend = snap
        self.manifest["snapshot_sha1"] = sha
        self._cleanup_snapshots(keep=snap)
        return snap

    def _cleanup_snapshots(self, keep=None):
        """Delete unused snapshots (no supervisor holds one of their .inuse locks) next to the source blend."""
        for p in glob.glob(os.path.join(os.path.dirname(self.src_blend), SNAPSHOT_PREFIX + "*.blend")):
            if keep and os.path.abspath(p) == os.path.abspath(keep):
                continue
            try:
                if not self._snapshot_unused(p):
                    continue
                os.remove(p)
                rp = os.path.splitext(p)[0] + ".build_report.json"
                if os.path.exists(rp):
                    os.remove(rp)
                self.log(f"removed unused snapshot {os.path.basename(p)}")
            except OSError:
                pass

    @staticmethod
    def _snapshot_unused(snap):
        """True when no live supervisor holds a <snap>.<pid>.inuse lock (stale .inuse files are removed)."""
        for u in glob.glob(glob.escape(snap) + ".*.inuse"):
            with open(u, "a+") as fh:
                if not procutil.lock_file(fh):
                    return False
                procutil.unlock_file(fh)
            if procutil.pid_alive(u.rsplit(".", 2)[-2]):
                return False                           # just created, its owner has not locked it yet
            os.remove(u)
        return True

    def _children_path(self):
        return os.path.join(self.logs, "children.json")

    def _save_children(self):
        os.makedirs(self.logs, exist_ok=True)
        tmp = self._children_path() + f".{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(dict(supervisor=os.getpid(), children=self.children), f, indent=1)
        os.replace(tmp, self._children_path())

    def reap_leftovers(self):
        """Kill Blender children that a previous (killed) supervisor left rendering into this out dir."""
        p = self._children_path()
        if not os.path.exists(p):
            return 0
        try:
            with open(p, encoding="utf-8") as f:
                old = json.load(f)
        except (OSError, ValueError):
            return 0
        n = 0
        for pid, info in (old.get("children") or {}).items():
            if not procutil.pid_alive(pid):
                continue
            cmd = procutil.process_command(pid) or ""
            if "render_frames.py" not in cmd or self.out not in cmd:
                continue                               # pid reused by something else
            self.log(f"killing leftover child {pid} ({info.get('shot')}) of supervisor {old.get('supervisor')}")
            procutil.terminate_tree(_Pid(info.get("pgid", pid)), grace=5.0)
            n += 1
        os.remove(p)
        return n

    def kill_children(self, reason=""):
        with self.lock:
            kids = dict(self.children)
        for pid, info in kids.items():
            proc = self._procs.get(pid) or _Pid(info["pgid"])
            if proc.poll() is None:
                self.log(f"killing child {pid} ({info.get('shot')}) {reason}")
                procutil.terminate_tree(proc, grace=3.0)
        with self.lock:
            self.children.clear()
            if not self.a.dry_run:
                self._save_children()

    def install_handlers(self):
        def handler(signum, frame):
            if self.stopping:
                return
            self.stopping = True
            self.log(f"signal {signal.Signals(signum).name}: stopping, killing children")
            self.kill_children("(supervisor interrupted)")
            raise Interrupted(signum)
        for s in (signal.SIGTERM, signal.SIGINT, getattr(signal, "SIGHUP", None)):    # no SIGHUP on Windows
            if s is not None:
                signal.signal(s, handler)
        atexit.register(lambda: self.kill_children("(supervisor exit)") if self.children else None)

    # ---- plan
    def plan(self):
        items = []
        for s in self.shots:
            frames = shot_frames(s)
            if not frames:
                continue
            fp = fingerprint(s, self.report, self.quality)
            old = self.manifest.get("shots", {}).get(s["id"], {})
            invalid = bool(old) and old.get("fingerprint") != fp
            todo = frames if invalid else missing_frames(self.out, frames)
            items.append(dict(shot=s, frames=frames, fingerprint=fp, invalidate=invalid, todo=todo))
        return items

    def cmd(self, shot_id=None, frames=None, no_mb=False):
        c = config.blender_cmd(RENDER_FRAMES, "--quality", self.quality, "--out", self.out, blend=self.blend)
        if frames:
            c += ["--frames", ",".join(str(f) for f in frames)]
        else:
            s = next(x for x in self.shots if x["id"] == shot_id)
            c += ["--start", str(s["start"]), "--end", str(s["end"])]
        if no_mb:
            c.append("--no-mb")
        return c

    # ---- one chunk
    def run_chunk(self, it, attempt, frames=None, no_mb=False):
        sid = it["shot"]["id"]
        n = len(frames or it["todo"])
        spf = measured_spf(self.out) or self.a.spf
        budget = config.RENDER_WATCHDOG_FACTOR * n * spf + self.a.grace
        os.makedirs(self.logs, exist_ok=True)
        logp = os.path.join(self.logs, f"{sid}_try{attempt}{'_nomb' if no_mb else ''}.log")
        c = self.cmd(sid, frames, no_mb)
        self.log(f"start {sid} attempt {attempt} ({n} frames, budget {budget:.0f}s{', no motion blur' if no_mb else ''})")
        t0 = time.time()
        state = dict(waiting_since=None, waited=0.0, alerts=set(), summary=None)
        env = dict(os.environ, SILVERGRASS_SUPERVISOR_PID=str(os.getpid()))
        with open(logp, "w", encoding="utf-8", buffering=1) as lf:       # line-buffered: live + survives a kill
            lf.write(f"# {' '.join(c)}\n")
            with self.lock:
                if self.stopping:
                    raise Interrupted()
                p = subprocess.Popen(c, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
                                     env=env, **procutil.popen_group_kwargs())
                self.children[str(p.pid)] = dict(pgid=p.pid, shot=sid, attempt=str(attempt),
                                                 started=time.strftime("%H:%M:%S"), out=self.out)
                self._procs[str(p.pid)] = p
                self._save_children()

            def reader():
                for line in p.stdout:
                    lf.write(line)
                    if "[render_lock] waiting" in line:
                        state["waiting_since"] = time.time()
                    elif state["waiting_since"] is not None and ("[render_lock] got slot" in line
                                                                 or "[render_frames] frame" in line):
                        state["waited"] += time.time() - state["waiting_since"]
                        state["waiting_since"] = None
                    for a in LOG_ALERTS:
                        if a in line:
                            state["alerts"].add(a)
                    if line.startswith("RENDER_SUMMARY "):
                        try:
                            state["summary"] = json.loads(line[len("RENDER_SUMMARY "):])
                        except ValueError:
                            pass
            th = threading.Thread(target=reader, daemon=True)
            th.start()
            killed = False
            while True:
                if p.poll() is not None:
                    th.join(timeout=10)
                    break
                ws = state["waiting_since"]
                cur_wait = state["waited"] + ((time.time() - ws) if ws else 0.0)
                if not killed and time.time() - t0 - cur_wait > budget:
                    self.log(f"WATCHDOG: {sid} exceeded {budget:.0f}s -> kill")
                    procutil.terminate_tree(p, grace=2.0)
                    killed = True
                time.sleep(0.5)
            with self.lock:
                self.children.pop(str(p.pid), None)
                self._procs.pop(str(p.pid), None)
                if not self.a.dry_run:
                    self._save_children()
        if self.stopping:
            raise Interrupted()
        return dict(returncode=p.returncode, killed=killed, alerts=sorted(state["alerts"]), summary=state["summary"],
                    log=logp, seconds=round(time.time() - t0, 1), waited=round(state["waited"], 1))

    def verify(self, frames):
        bad = []
        for f in frames:
            p = frame_path(self.out, f)
            if not os.path.exists(p):
                continue
            err = verify_frame(p, self.size)
            if err:
                bad.append((f, err))
                os.remove(p)
        return bad

    def process(self, it):
        """Render one shot: normal chunk attempts (1 + retries); when they stall, the first missing frame gets
        the poison-frame fallback (alone, motion blur off) and the rest of the shot continues normally."""
        sid = it["shot"]["id"]
        with self.lock:
            rec = self.manifest.setdefault("shots", {}).setdefault(sid, {})
        if it["invalidate"]:
            n = 0
            for f in it["frames"]:
                if os.path.exists(frame_path(self.out, f)):
                    os.remove(frame_path(self.out, f))
                    n += 1
            self.log(f"{sid}: fingerprint changed -> deleted {n} old frames")
        rec.update(fingerprint=it["fingerprint"], frames=[it["frames"][0], it["frames"][-1]], status="running",
                   warnings=rec.get("warnings", []) if not it["invalidate"] else [],
                   motion_blur_off=rec.get("motion_blur_off", []) if not it["invalidate"] else [])
        attempts, dead = [], []
        tries = 0
        try:
            while not self.stopping:
                todo = [f for f in missing_frames(self.out, it["frames"]) if f not in dead]
                if not todo:
                    break
                if tries <= self.a.retries:
                    it["todo"] = todo
                    explicit = todo if dead else None           # skip frames that already proved poisonous
                    r = self.run_chunk(it, tries, frames=explicit)
                    tries += 1
                else:
                    f = todo[0]
                    r = self.run_chunk(it, f"poison{f}", frames=[f], no_mb=True)
                    if missing_frames(self.out, [f]) or (not self.a.no_verify and self.verify([f])):
                        dead.append(f)
                        rec["warnings"].append(f"frame {f} failed even with motion blur off")
                    else:
                        rec["warnings"].append(f"frame {f} rendered only with motion blur OFF (poison-frame fallback)")
                        rec["motion_blur_off"].append(f)
                        with self.lock:
                            self.fallback_frames.append(f)
                    tries = self.a.retries                      # one more normal attempt for the remaining frames
                attempts.append(r)
                bad = [] if self.a.no_verify else self.verify(it["frames"])
                for a in r["alerts"]:
                    rec["warnings"].append(f"'{a}' in {os.path.basename(r['log'])}")
                if bad:
                    rec["warnings"].append(f"{len(bad)} broken frames deleted + re-queued: {bad[:5]}")
        except Interrupted:
            rec.update(status="interrupted")
            with self.lock:
                self.save_manifest()
            return rec
        left = missing_frames(self.out, it["frames"])
        rec.update(status="done" if not left else ("interrupted" if self.stopping else "failed"), failed_frames=left,
                   attempts=[dict(returncode=a["returncode"], killed=a["killed"], seconds=a["seconds"],
                                  waited=a["waited"], alerts=a["alerts"], log=a["log"],
                                  rendered=(a["summary"] or {}).get("rendered"),
                                  quality_mismatch=(a["summary"] or {}).get("quality_mismatch")) for a in attempts],
                   finished=time.strftime("%Y-%m-%d %H:%M:%S"))
        with self.lock:
            self.save_manifest()
        self.log(f"{sid}: {rec['status']} ({len(attempts)} run(s), {len(left)} missing)")
        return rec

    # ---- main loop
    def run(self):
        try:
            return self._run()
        except Interrupted:
            self.log("interrupted")
            return 130

    def _run(self):
        if not self.a.dry_run:
            self.acquire_out_lock()
            self.install_handlers()
            self.reap_leftovers()
        probs, qp = self.check_build()
        refused = ([] if self.a.allow_unverified_build else probs) + \
            ([qp] if qp and not self.a.allow_quality_mismatch else [])
        for p in refused:
            self.log(f"REFUSED: {p}")
        if refused and not self.a.dry_run:
            return 2
        for p in probs + ([qp] if qp else []):
            if p not in refused:
                self.log(f"WARNING: {p}")
        items = self.plan()
        total = sum(len(i["frames"]) for i in items)
        todo = sum(len(i["todo"]) for i in items)
        self.log(f"blend {self.src_blend} quality {self.quality} -> {self.out}")
        self.log(f"{len(items)} shots, {total} frames, {todo} to render, "
                 f"{sum(i['invalidate'] for i in items)} invalidated")
        if self.a.dry_run:
            spf = measured_spf(self.out) or self.a.spf
            plan = [dict(shot=i["shot"]["id"], lane=i["shot"].get("lane"), frames=[i["frames"][0], i["frames"][-1]],
                         todo=len(i["todo"]), invalidate=i["invalidate"], fingerprint=i["fingerprint"],
                         content_digest=bool((self.report.get("shot_digest") or {}).get(i["shot"]["id"])),
                         cmd=" ".join(self.cmd(i["shot"]["id"]))) for i in items]
            print("PLAN " + json.dumps(dict(shots=plan, frames_todo=todo, est_seconds=round(todo * spf, 1),
                                            slots=self.a.slots, mem_available_gb=mem_available_gb(),
                                            refused=refused, warnings=[p for p in probs + ([qp] if qp else [])
                                                                       if p not in refused])), flush=True)
            return 2 if refused else 0
        try:
            if any(i["todo"] or i["invalidate"] for i in items):
                self.snapshot()                        # only when something will be rendered (full blends are big)
            return self._run_items(items, total)
        except Interrupted:
            self.log("interrupted")
            return 130
        finally:
            self.kill_children("(cleanup)")
            self.save_manifest()
            if self._snap_fh is not None:
                try:
                    procutil.unlock_file(self._snap_fh)
                    self._snap_fh.close()
                    os.remove(self._snap_fh.name)
                except OSError:
                    pass
                self._snap_fh = None

    def _run_items(self, items, total):
        queue = [i for i in items if i["todo"] or i["invalidate"]]
        for i in items:
            if not (i["todo"] or i["invalidate"]):
                rec = self.manifest.setdefault("shots", {}).setdefault(i["shot"]["id"], {})
                rec.update(fingerprint=i["fingerprint"], status="done", frames=[i["frames"][0], i["frames"][-1]])
        self.save_manifest()
        self.all_frames = [f for i in items for f in i["frames"]]
        running = []
        self._last_prog = 0.0
        self._mem_unknown_logged = False
        self._t_first = time.time()
        self._done0 = total - len(missing_frames(self.out, self.all_frames))
        while (queue or running) and not self.stopping:
            running = [t for t in running if t.is_alive()]
            can_start = len(running) < self.a.slots and queue
            if can_start and running:
                mem = mem_available_gb()
                if mem is None and not self._mem_unknown_logged:
                    self._mem_unknown_logged = True
                    self.log("note: free memory cannot be measured on this system - --mem-gb gate disabled")
                if mem is not None and mem < self.a.mem_gb:
                    can_start = False
            if can_start:
                it = queue.pop(0)
                t = threading.Thread(target=self.process, args=(it,), daemon=True)
                t.start()
                running.append(t)
                time.sleep(1.0)
                continue
            time.sleep(1.0)
            self._progress(total, len(running))
        for t in running:
            t.join(timeout=5)
        self._progress(total, 0, final=True)
        shots = self.manifest.get("shots", {})
        failed = {k: v for k, v in shots.items() if v.get("status") == "failed"}
        nomb = sorted({f for v in shots.values() for f in v.get("motion_blur_off", [])})
        self.manifest["summary"] = dict(failed_shots=sorted(failed),
                                        failed_frames=sorted({f for v in failed.values() for f in v.get("failed_frames", [])}),
                                        motion_blur_off_frames=nomb, seconds=round(time.time() - self.t0, 1))
        self.save_manifest()
        self.log(f"SUMMARY: {len(shots)} shots, failed {sorted(failed) or 'none'}; motion blur OFF frames "
                 f"(poison fallback): {nomb or 'none'}")
        return 1 if failed else 0

    def _progress(self, total, n_running, final=False):
        now = time.time()
        if not final and now - self._last_prog < PROGRESS_EVERY:
            return
        self._last_prog = now
        done = total - len(missing_frames(self.out, self.all_frames))
        spf = measured_spf(self.out)
        left = total - done
        rate_done = done - self._done0
        el = now - self._t_first
        if rate_done > 0 and el > 0:
            eta_s = left * el / rate_done                  # observed throughput (includes slot waits)
        elif spf:
            eta_s = left * spf / max(1, n_running or 1)
        else:
            eta_s = None
        eta = f"{eta_s / 60:.0f} min" if eta_s is not None else "?"
        self.log(f"progress {done}/{total} frames on disk, {n_running} chunk(s) running, median {spf or 0:.2f} s/f, "
                 f"ETA {eta}")


def main():
    ap = argparse.ArgumentParser(prog="render_supervisor.py")
    ap.add_argument("--blend", default=config.SCENE_BLEND)
    ap.add_argument("--shots", default="all")
    ap.add_argument("--quality", default="final", choices=["layout", "preview", "final"])
    ap.add_argument("--out", default=config.FRAMES_DIR)
    ap.add_argument("--slots", type=int, default=config.RENDER_SLOTS)
    ap.add_argument("--mem-gb", type=float, default=config.RENDER_MIN_FREE_MEM_GB,
                    help="free memory needed to start a 2nd parallel chunk")
    ap.add_argument("--spf", type=float, default=config.RENDER_EXPECTED_SPF,
                    help="expected seconds/frame before measurements exist")
    ap.add_argument("--retries", type=int, default=config.RENDER_RETRIES)
    ap.add_argument("--grace", type=float, default=config.RENDER_WATCHDOG_GRACE_S,
                    help=f"watchdog: {config.RENDER_WATCHDOG_FACTOR:g} x expected + grace seconds")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-verify", action="store_true")
    ap.add_argument("--allow-quality-mismatch", action="store_true",
                    help="render although the blend was built at another quality")
    ap.add_argument("--allow-unverified-build", action="store_true",
                    help="render although the build report is failed/missing/for another blend")
    a = ap.parse_args()
    if not os.path.exists(a.blend):
        raise SystemExit(f"render_supervisor: {a.blend} not found (run build_scene first)")
    sys.exit(Supervisor(a).run())


if __name__ == "__main__":
    main()
