"""Read a cartoon screenplay and compile it into a frame-accurate production plan.

A screenplay is JSON (`films/<id>/screenplay.json`) written like a shooting
script: cast and sets chosen from the libraries, then scenes made of shots,
each shot with a duration, a camera direction and a list of timed beats.

    {"t": 1.0, "who": "mei", "walk": "gate"}                    # move to a mark (walk, run, waddle, hop, fly, ...)
    {"t": 1.5, "who": "mei", "act": "wave", "dur": 1.2}         # an action from the motion library
    {"t": 2.0, "who": "mei", "face": "joy"}                     # an expression
    {"t": 2.2, "who": "mei", "look": "grandma"}                 # a gaze target: a character, a mark, a point or "camera"
    {"t": 2.4, "who": "mei", "say": "Grandma!", "en": "Grandma!", "mood": "excited"}
    {"t": 3.0, "sfx": "pop", "at": "gate"}                      # a sound effect, optionally placed in the stereo field
    {"t": 3.2, "fx": "sparkles", "at": "gate", "dur": 1.5}      # a visual effect
    {"t": 0.0, "prop": "lantern", "hold": "mei", "hand": "r"}   # props can be placed, carried, moved or shown

Times inside a shot are relative to the shot's start. Characters keep their
positions from shot to shot within a scene, as in continuity editing.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

from codecinema.cartoon import cast as library
from codecinema.cartoon import faces, motion, sets

VERSION = 1
MOVES = ("walk", "run", "sneak", "tiptoe", "waddle", "hop", "skip", "trudge", "fly", "swim", "float", "slide")
TRANSITIONS = ("cut", "fade", "dissolve", "fade_white", "fade_in")
SIZES = ("extreme_wide", "wide", "full", "medium", "medium_close", "close", "extreme_close")


class ScreenplayError(ValueError):
    pass


def load(path):
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ScreenplayError(f"{path.name}: invalid JSON at line {exc.lineno}: {exc.msg}") from exc
    return data


def _where(scene, shot=None, beat=None):
    out = f"scene '{scene.get('id', '?')}'"
    if shot is not None:
        out += f", shot '{shot.get('id', '?')}'"
    if beat is not None:
        out += f", beat at {beat.get('t', 0)}s"
    return out


class Compiler:
    def __init__(self, data, film_dir=None):
        self.data = data
        self.film_dir = Path(film_dir) if film_dir else None
        if data.get("version", VERSION) != VERSION:
            raise ScreenplayError(f"Unsupported screenplay version {data.get('version')}; use {VERSION}")
        self.fps = int(data.get("fps", 24))
        self.seed = int(data.get("seed", 1))
        self.cast = {}
        for cid, entry in data.get("cast", {}).items():
            spec = library.resolve(entry, cid)
            self.cast[cid] = {"spec": spec, "metrics": library.metrics(spec)}
        if not self.cast:
            raise ScreenplayError("The screenplay has no cast")
        self.sets = {}
        for sid, entry in data.get("sets", {}).items():
            self.sets[sid] = sets.resolve(entry, sid)
        self.props = {}
        for pid, entry in data.get("props", {}).items():
            self.props[pid] = sets.resolve_prop(entry, pid)
        self.events = {cid: [] for cid in self.cast}
        self.prop_events = {pid: [] for pid in self.props}
        self.shots, self.scenes = [], []
        self.sfx, self.fx, self.lines, self.titles, self.ambience, self.spaces = [], [], [], [], [], []
        self.music_cues = []

    # ------------------------------------------------------------------ resolving places
    def point(self, value, scene, z=False, who=None, t=None):
        """A mark name, a character id, or coordinates -> (x, y[, z])."""
        if isinstance(value, str):
            marks = dict(self.sets[scene["set"]]["marks"])
            marks.update(scene.get("marks", {}))
            if value in marks:
                p = tuple(float(v) for v in marks[value])
            elif value in self.cast and t is not None:
                p = self._position_of(value, t)
            elif value in self.cast:
                raise ScreenplayError(f"{_where(scene)}: '{value}' needs a time to be used as a place")
            else:
                raise ScreenplayError(f"{_where(scene)}: unknown mark '{value}'. Marks: {', '.join(sorted(marks))}")
        else:
            p = tuple(float(v) for v in value)
        if len(p) not in (2, 3):
            raise ScreenplayError(f"{_where(scene)}: a place needs 2 or 3 coordinates, got {value}")
        if z and len(p) == 2:
            # Props, effects and sounds need a height: rest them on the set's ground.
            p = p + (sets.ground_function(self.sets[scene["set"]])(p[0], p[1]),)
        return p

    def _position_of(self, cid, t):
        track = motion.Track(cid, self.cast[cid]["spec"], self.cast[cid]["metrics"], self.events[cid])
        p, _ = track.position(t)
        return tuple(p)

    def _ground_point(self, p, scene):
        if len(p) > 2:
            return list(p)
        return [p[0], p[1], sets.ground_function(self.sets[scene["set"]])(p[0], p[1])]

    def angle(self, value, cid, scene, t):
        """Facing from degrees, a compass word, 'camera' (resolved later), or a target to face."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return math.radians(value)
        named = {"front": 0.0, "south": 0.0, "back": 180.0, "north": 180.0, "left": -90.0, "west": -90.0,
                 "right": 90.0, "east": 90.0}
        if value in named:
            return math.radians(named[value])
        target = self.point(value, scene, t=t)
        here = self._position_of(cid, t)
        return motion.heading_of(target[0] - here[0], target[1] - here[1])

    # ------------------------------------------------------------------ compile
    def compile(self):
        t = 0.0
        scenes = self.data.get("scenes", [])
        if not scenes:
            raise ScreenplayError("The screenplay has no scenes")
        for si, scene in enumerate(scenes):
            scene.setdefault("id", f"scene{si + 1}")
            if scene.get("set") not in self.sets:
                raise ScreenplayError(f"{_where(scene)}: unknown set '{scene.get('set')}'. Sets: {', '.join(self.sets)}")
            start = t
            present = set()
            for cid in self.cast:
                self.events[cid].append({"t": t, "type": "hide", "order": -2})
            for pid in self.props:
                self.prop_events[pid].append({"t": t, "type": "hide", "order": -2})
            starts = scene.get("start", {})
            for cid, state in starts.items():
                self._state(cid, state, scene, t, present, phase="place")
            for cid, state in starts.items():
                self._state(cid, state, scene, t, present, phase="pose")
            for pid, state in scene.get("props", {}).items():
                self._prop(pid, dict(state), scene, t)
            for shi, shot in enumerate(scene.get("shots", [])):
                shot.setdefault("id", f"{scene['id']}.{shi + 1}")
                dur = float(shot.get("dur", 0))
                if dur < 0.3:
                    raise ScreenplayError(f"{_where(scene, shot)}: every shot needs dur >= 0.3 seconds")
                for phase in ("place", "pose"):
                    for cid, state in shot.get("cast", {}).items():
                        self._state(cid, state, scene, t, present, phase=phase)
                for beat in sorted(shot.get("do", []), key=lambda b: float(b.get("t", 0))):
                    local = float(beat.get("t", 0))
                    if not 0 <= local <= dur + 1e-6:
                        raise ScreenplayError(f"{_where(scene, shot, beat)}: beat time outside the shot (0..{dur})")
                    self._beat(beat, scene, shot, t + local, present)
                cam = dict(shot.get("camera", {}))
                if cam.get("size", "medium") not in SIZES:
                    raise ScreenplayError(f"{_where(scene, shot)}: camera size must be one of {', '.join(SIZES)}")
                transition = shot.get("transition", "cut")
                if transition not in TRANSITIONS:
                    raise ScreenplayError(f"{_where(scene, shot)}: transition must be one of {', '.join(TRANSITIONS)}")
                self.shots.append({"id": shot["id"], "scene": scene["id"], "start": t, "end": t + dur, "camera": cam,
                                   "transition": transition, "grade": shot.get("grade", scene.get("grade")),
                                   "set": scene["set"]})
                if shot.get("title"):
                    title = shot["title"]
                    title = {"text": title} if isinstance(title, str) else dict(title)
                    title.setdefault("start", 0.0)
                    title.setdefault("dur", min(dur, 4.0))
                    title["start"] = t + float(title["start"])
                    self.titles.append(title)
                t += dur
            setspec = self.sets[scene["set"]]
            light = scene.get("time", setspec["time"])
            if light not in sets.TIMES:
                raise ScreenplayError(f"{_where(scene)}: unknown time '{light}'. Times: {', '.join(sets.TIMES)}")
            self.scenes.append({"id": scene["id"], "start": start, "end": t, "set": scene["set"], "time": light,
                                "weather": scene.get("weather", setspec.get("weather")),
                                "grade": scene.get("grade"), "present": sorted(present)})
            amb = scene.get("ambience", setspec.get("ambience"))
            if amb:
                self.ambience.append({"start": start, "end": t, "bed": amb,
                                      "gain_db": float(scene.get("ambience_db", -20.0)), "fade": 1.5})
            self.spaces.append({"start": start, "end": t, "space": scene.get("space", setspec.get("space", "outdoor"))})
            if scene.get("music"):
                cue = dict(scene["music"])
                cue.setdefault("start", start + float(cue.pop("offset", 0.0)))
                cue.setdefault("end", t)
                self.music_cues.append(cue)
        self.duration = t
        for cue in self.data.get("music", {}).get("cues", []):
            self.music_cues.append(dict(cue))
        self.music_cues.sort(key=lambda c: c["start"])
        return self.plan()

    def _state(self, cid, state, scene, t, present, phase="place"):
        """A character's state at the start of a scene or shot: placed first, then posed and turned."""
        if cid not in self.cast:
            raise ScreenplayError(f"{_where(scene)}: '{cid}' is not in the cast")
        state = {"at": state} if isinstance(state, (list, str)) else dict(state)
        ev = self.events[cid]
        if phase == "place":
            present.add(cid)
            ev.append({"t": t, "type": "show", "order": -1})
            if "at" in state:
                p = self.point(state["at"], scene)
                ev.append({"t": t, "type": "place", "at": list(p), "order": 0})
            return
        if "facing" in state:
            facing = state["facing"]
            if facing == "camera":
                facing = "front"
            ev.append({"t": t, "type": "turn", "angle": self.angle(facing, cid, scene, t), "dur": 0.0, "order": 1})
        if "face" in state:
            faces.expression(state["face"])
            ev.append({"t": t, "type": "face", "expr": state["face"], "order": 1})
        if "look" in state:
            ev.append({"t": t, "type": "look", "at": self._look_target(state["look"], scene, t), "dur": 0.01,
                       "order": 1})
        if "act" in state:
            ev.append({"t": t, "type": "act", "name": state["act"], "dur": float(state.get("dur", 3600)),
                       "params": state.get("params", {}), "fade": 0.01, "order": 1})
        if "blush" in state:
            ev.append({"t": t, "type": "blush", "value": float(state["blush"]), "order": 1})
        if "scale" in state:
            ev.append({"t": t, "type": "scale", "value": float(state["scale"]), "dur": 0.0, "order": 1})

    def _look_target(self, value, scene, t):
        if value in (None, "none", False):
            return None
        if value == "camera" or (isinstance(value, str) and value in self.cast):
            return value
        if isinstance(value, str) and value in self.props:
            return list(self._prop_point(value, t, scene))
        p = self.point(value, scene, z=False)
        return list(p)

    def _prop_point(self, pid, t, scene):
        for e in reversed(self.prop_events[pid]):
            if e["t"] <= t and e["type"] == "place":
                return tuple(e["at"])
        return (0.0, 0.0, 0.0)

    def _beat(self, beat, scene, shot, t, present):
        who = beat.get("who")
        if who is not None and who not in self.cast:
            raise ScreenplayError(f"{_where(scene, shot, beat)}: '{who}' is not in the cast")
        if who is not None and who not in present:
            if not beat.get("show"):
                raise ScreenplayError(f"{_where(scene, shot, beat)}: '{who}' is not on set; add it to the scene's "
                                      f"start or give the beat \"show\": true")
            present.add(who)
        ev = self.events.get(who)
        if who and beat.get("show"):
            ev.append({"t": t, "type": "show", "order": -1})
        verb = next((k for k in MOVES if k in beat), None)
        if who and verb:
            target = beat[verb]
            pts = target if (isinstance(target, list) and target and isinstance(target[0], (list, str))) else [target]
            path = [list(self.point(p, scene, t=t)) for p in pts]
            move = {"t": t, "type": "move", "path": path, "gait": verb}
            if "dur" in beat:
                move["end"] = t + float(beat["dur"])
            if "speed" in beat:
                move["speed"] = float(beat["speed"])
            if "facing" in beat:
                move["facing"] = self.angle(beat["facing"], who, scene, t)
            if "ease" in beat:
                move["ease"] = float(beat["ease"])
            ev.append(move)
        if who and "at" in beat and not verb and "say" not in beat and "act" not in beat:
            ev.append({"t": t, "type": "place", "at": list(self.point(beat["at"], scene))})
        if who and "turn" in beat:
            ev.append({"t": t, "type": "turn", "angle": self.angle(beat["turn"], who, scene, t),
                       "dur": float(beat.get("turn_dur", 0.4))})
        if who and "act" in beat:
            params = dict(beat.get("params", {}))
            for key in ("at", "target"):
                if key in params and not isinstance(params[key], (int, float)):
                    p = self.point(params[key], scene, z=True, t=t) if not (isinstance(params[key], str) and
                                                                            params[key] in self.cast) else None
                    if p is None:
                        other = params[key]
                        hp = self._position_of(other, t)
                        m = self.cast[other]["metrics"]
                        p = (hp[0], hp[1], sets.ground_function(self.sets[scene["set"]])(*hp[:2]) + m["neck"])
                    params["at"] = list(p)
            for key in ("hand", "height", "turns", "rate", "lift", "seat", "depth", "amount", "side", "pitch",
                        "roll", "count"):
                if key in beat and key not in params:
                    params[key] = beat[key]
            if beat["act"] not in motion.ACTIONS:
                raise ScreenplayError(f"{_where(scene, shot, beat)}: unknown action '{beat['act']}'. "
                                      f"Actions: {', '.join(sorted(motion.ACTIONS))}")
            ev.append({"t": t, "type": "act", "name": beat["act"], "dur": float(beat.get("dur", 1.5)),
                       "params": params, "fade": float(beat.get("fade", 0.22))})
        if who and "face" in beat:
            faces.expression(beat["face"])
            ev.append({"t": t, "type": "face", "expr": beat["face"]})
        if who and "look" in beat:
            ev.append({"t": t, "type": "look", "at": self._look_target(beat["look"], scene, t),
                       "dur": float(beat.get("look_dur", 0.35))})
        if who and "blush" in beat:
            ev.append({"t": t, "type": "blush", "value": float(beat["blush"])})
        if who and "scale" in beat:
            ev.append({"t": t, "type": "scale", "value": float(beat["scale"]), "dur": float(beat.get("dur", 0.5))})
        if who and ("wear" in beat or "unwear" in beat):
            item = beat.get("wear", beat.get("unwear"))
            ev.append({"t": t, "type": "wear", "item": item, "on": "wear" in beat})
        if who and beat.get("hide"):
            ev.append({"t": t, "type": "hide"})
            present.discard(who)
        if who and ("say" in beat or "vocal" in beat):
            line_id = f"{shot['id']}.{len([l for l in self.lines if l['shot'] == shot['id']]) + 1}"
            line = {"id": line_id, "shot": shot["id"], "t": t, "who": who,
                    "text": beat.get("say", ""), "vocal": beat.get("vocal"), "mood": beat.get("mood", "neutral"),
                    "direction": beat.get("direction", ""), "subtitles": {}}
            for lang in ("en", "zh"):
                if lang in beat:
                    line["subtitles"][lang] = beat[lang]
            if beat.get("say"):
                line["subtitles"].setdefault(self.data.get("subtitle", "en"), beat["say"])
            self.lines.append(line)
            ev.append({"t": t, "type": "say", "line": line_id, "dur": 1.0})
        if "sfx" in beat:
            at = beat.get("at")
            pos = None
            if at is not None:
                pos = list(self.point(at, scene, z=True, t=t)) if not (isinstance(at, str) and at in self.cast) \
                    else self._ground_point(self._position_of(at, t), scene)
            elif who:
                pos = self._ground_point(self._position_of(who, t), scene)
            self.sfx.append({"t": t, "name": beat["sfx"], "gain_db": float(beat.get("gain_db", 0.0)),
                             "params": beat.get("params", {}), "pos": pos})
        if "fx" in beat:
            at = beat.get("at", who)
            pos = None
            if at is not None:
                pos = list(self.point(at, scene, z=True, t=t)) if not (isinstance(at, str) and at in self.cast) \
                    else self._ground_point(self._position_of(at, t), scene)
            self.fx.append({"t": t, "name": beat["fx"], "dur": float(beat.get("dur", 1.5)), "pos": pos,
                            "params": beat.get("params", {}), "scene": scene["id"]})
        if "prop" in beat:
            self._prop(beat["prop"], beat, scene, t)

    def _prop(self, pid, beat, scene, t):
        if pid not in self.props:
            raise ScreenplayError(f"{_where(scene)}: unknown prop '{pid}'. Props: {', '.join(self.props) or 'none'}")
        ev = self.prop_events[pid]
        if beat.get("hold"):
            ev.append({"t": t, "type": "hold", "who": beat["hold"], "hand": beat.get("hand", "r"),
                       "offset": beat.get("offset", [0, 0, 0])})
        if "place" in beat or ("at" in beat and not beat.get("hold")):
            p = self.point(beat.get("place", beat.get("at")), scene, z=True, t=t)
            ev.append({"t": t, "type": "place", "at": list(p), "rot": beat.get("rot", [0, 0, 0])})
        if "move" in beat:
            pts = beat["move"]
            pts = pts if isinstance(pts[0], (list, str)) else [pts]
            ev.append({"t": t, "type": "move", "path": [list(self.point(p, scene, z=True, t=t)) for p in pts],
                       "dur": float(beat.get("dur", 1.0)), "spin": beat.get("spin", 0.0)})
            ev.append({"t": t + float(beat.get("dur", 1.0)), "type": "place",
                       "at": list(self.point(pts[-1], scene, z=True, t=t)), "rot": beat.get("rot", [0, 0, 0])})
        if "glow" in beat:
            ev.append({"t": t, "type": "glow", "value": float(beat["glow"]), "dur": float(beat.get("dur", 0.5))})
        if beat.get("show"):
            ev.append({"t": t, "type": "show"})
        if beat.get("hide") is True:
            ev.append({"t": t, "type": "hide"})
        if "scale" in beat:
            ev.append({"t": t, "type": "scale", "value": float(beat["scale"]), "dur": float(beat.get("dur", 0.4))})
        if not any(k in beat for k in ("hide",)):
            if not any(e["type"] == "show" and e["t"] == t for e in ev):
                ev.append({"t": t, "type": "show"})

    # ------------------------------------------------------------------ the plan
    def plan(self):
        frames = round(self.duration * self.fps)
        foley = []
        for cid, info in self.cast.items():
            track = motion.Track(cid, info["spec"], info["metrics"], self.events[cid], seed=hash_seed(cid))
            plan, height = info["spec"]["plan"], info["metrics"]["height"]
            # Footsteps follow the body: penguins pat, birds tick, big creatures thump.
            kind = "waddle" if plan == "penguin" else "creature_step" if height > 1.8 else "step"
            scale = 0.4 if plan == "bird" else 1.0

            def surface_at(t):
                scene = next((s for s in self.scenes if s["start"] <= t < s["end"]), None)
                return self.sets[scene["set"]]["surface"] if scene else "ground"

            for step in track.footsteps():
                surface = surface_at(step["t"])
                if surface == "none":
                    continue
                foley.append({**step, "kind": kind, "weight": step["weight"] * scale, "surface": surface,
                              "plan": plan, "gain_db": -5.0})
            # Landings, falls and sitting down get their own Foley from the action timeline.
            for start, end, name, params, _fade in track.acts:
                hits = {"jump": [("land", 0.78)], "fall": [("land", 0.25)], "hop": [], "sit": [("sit", 0.35)],
                        "cheer": [], "stomp": []}.get(name)
                if not hits:
                    continue
                for kind_hit, at in hits:
                    t = start + (end - start) * at if name == "jump" else start + at
                    p, _ = track.position(t)
                    surface = surface_at(t)
                    if surface == "none":
                        continue
                    foley.append({"t": round(t, 4), "who": cid, "kind": kind_hit, "x": p[0], "y": p[1],
                                  "surface": surface, "weight": min(1.0, (height / 1.1) ** 1.2) * scale,
                                  "plan": plan, "gain_db": -2.0})
        foley.sort(key=lambda row: row["t"])
        language = self.data.get("language", "English")
        return {
            "version": VERSION,
            "title": self.data.get("title", "Untitled"),
            "title_local": self.data.get("title_local", ""),
            "language": language,
            "subtitle": self.data.get("subtitle", "en"),
            "fps": self.fps, "seed": self.seed, "duration": self.duration, "frames": frames,
            "look": self.data.get("look", {}),
            "cast": self.cast,
            "tracks": self.events,
            "sets": self.sets,
            "props": {pid: {"spec": spec, "events": self.prop_events[pid]} for pid, spec in self.props.items()},
            "scenes": self.scenes,
            "shots": self.shots,
            "lines": self.lines,
            "fx": self.fx,
            "titles": self.titles,
            "credits": self.data.get("credits", []),
            "audio": {"duration": self.duration, "seed": self.seed,
                      "music": {"themes": self.data.get("music", {}).get("themes", {}), "cues": self.music_cues},
                      "sfx": self.sfx, "foley": foley, "ambience": self.ambience, "spaces": self.spaces,
                      "master": self.data.get("master", {"target_lufs": -16.0, "true_peak_db": -1.0})},
        }


def hash_seed(text):
    return int(hashlib.sha256(text.encode()).hexdigest()[:6], 16) % 997 / 97.0


def compile_file(path, film_dir=None):
    data = load(path)
    return Compiler(copy.deepcopy(data), film_dir).compile()


def timing_warnings(plan, voices):
    """Spoken lines that run into the next line or far past their shot (once takes exist)."""
    out = []
    lines = sorted(plan.get("lines", []), key=lambda l: l["t"])
    for i, line in enumerate(lines):
        take = voices.get(line["id"])
        if not take:
            continue
        end = line["t"] + take["duration"]
        if i + 1 < len(lines) and end > lines[i + 1]["t"] + 0.05:
            out.append(f"{line['id']} ({line['who']}) runs {end - lines[i + 1]['t']:.1f}s into {lines[i + 1]['id']}")
        shot = next((s for s in plan["shots"] if s["id"] == line["shot"]), None)
        if shot and end > shot["end"] + 1.5:
            out.append(f"{line['id']} ends {end - shot['end']:.1f}s after its shot; lengthen the shot or the cut")
    return out


def summary(plan):
    lines = [f"{plan['title']} · {plan['duration']:.1f}s · {len(plan['scenes'])} scenes · {len(plan['shots'])} shots · "
             f"{len(plan['cast'])} characters · {len(plan['lines'])} lines"]
    for scene in plan["scenes"]:
        n = sum(1 for s in plan["shots"] if s["scene"] == scene["id"])
        lines.append(f"  {scene['start']:6.1f}–{scene['end']:6.1f}s  {scene['id']:18s} {scene['set']} · {scene['time']}"
                     f" · {n} shots · {', '.join(scene['present'])}")
    return "\n".join(lines)
