"""Screenplay cartoons without Blender: the character library, the compiler, motion quality and the camera."""
import copy
import json
import math
from pathlib import Path

import pytest

from codecinema.cartoon import camera, cast, motion, screenplay
from codecinema.cartoon.screenplay import ScreenplayError, hash_seed

ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT / "assets" / "_shared" / "scaffold" / "cartoon" / "screenplay.json"
FILMS = [ROOT / "films" / name / "screenplay.json" for name in ("pebble", "nian")]


def compile_data(data):
    return screenplay.Compiler(copy.deepcopy(data), None).compile()


def tracks_of(plan):
    return {cid: motion.Track(cid, info["spec"], info["metrics"], plan["tracks"][cid], seed=hash_seed(cid))
            for cid, info in plan["cast"].items()}


@pytest.fixture(scope="module")
def starter():
    return json.loads(STARTER.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------- library
@pytest.mark.parametrize("name", sorted(cast.ARCHETYPES))
def test_every_archetype_resolves_to_sane_proportions(name):
    spec = cast.resolve({"from": name}, name)
    m = cast.metrics(spec)
    assert 0 < m["hip"] < m["chest"] < m["head_z"] < m["height"]
    assert m["stride"] > 0 and m["arm"] > 0 and m["head_r"] > 0
    assert spec.get("sheet", {}).get("act") in (None, *motion.ACTIONS)


def test_library_rejects_unknown_parts():
    with pytest.raises(ValueError, match="archetype"):
        cast.resolve({"from": "dragon"}, "x")
    with pytest.raises(ValueError, match="body shape"):
        cast.resolve({"from": "girl", "shape": "cube"}, "x")
    with pytest.raises(ValueError, match="hat"):
        cast.resolve({"from": "girl", "accessories": [{"kind": "hat", "style": "crown"}]}, "x")


def test_body_shapes_change_proportions():
    slim = cast.metrics(cast.resolve({"from": "man", "shape": "slim"}, "a"))
    broad = cast.metrics(cast.resolve({"from": "man", "shape": "broad"}, "b"))
    assert broad["shoulder"][0] > slim["shoulder"][0]


# ---------------------------------------------------------------------------- compiler
def test_starter_compiles(starter):
    plan = compile_data(starter)
    assert plan["shots"] and plan["lines"] and set(plan["tracks"]) == {"mei", "pip"}
    assert abs(plan["duration"] - sum(s["dur"] for sc in starter["scenes"] for s in sc["shots"])) < 1e-6


@pytest.mark.parametrize("path", FILMS, ids=lambda p: p.parent.name)
def test_example_films_compile_without_motion_warnings(path):
    plan = screenplay.compile_file(path, path.parent)
    assert motion.motion_warnings(plan) == []


def test_screenplay_errors_name_the_place(starter):
    bad = copy.deepcopy(starter)
    bad["scenes"][0]["shots"][0]["do"].append({"t": 1.0, "who": "nobody", "face": "happy"})
    with pytest.raises(ScreenplayError, match="'nobody' is not in the cast"):
        compile_data(bad)
    late = copy.deepcopy(starter)
    late["scenes"][0]["shots"][0]["do"].append({"t": 99.0, "who": "mei", "face": "happy"})
    with pytest.raises(ScreenplayError, match="outside the shot"):
        compile_data(late)


def test_held_poses_end_at_the_next_starting_state(starter):
    data = copy.deepcopy(starter)
    shots = data["scenes"][0]["shots"]
    shots[0]["cast"] = {"pip": {"act": "sit"}}
    shots[1]["cast"] = {"pip": {"face": "happy"}}
    plan = compile_data(data)
    sit = next(e for e in plan["tracks"]["pip"] if e["type"] == "act" and e["name"] == "sit")
    assert abs(sit["t"] + sit["dur"] - shots[0]["dur"]) < 1e-6


# ---------------------------------------------------------------------------- motion
def test_envelope_springs_in_holds_and_releases():
    assert motion.envelope(0.0, 1.0, 3.0, 0.22, "wave") == 0.0
    assert motion.envelope(0.95, 1.0, 3.0, 0.22, "wave") < 0          # wind-up before a lively action
    assert abs(motion.envelope(2.0, 1.0, 3.0, 0.22, "wave") - 1.0) < 0.01
    assert max(motion.envelope(1.0 + k * 0.01, 1.0, 3.0, 0.22, "wave") for k in range(40)) > 1.05   # overshoot
    assert abs(motion.envelope(4.2, 1.0, 3.0, 0.22, "wave")) < 0.01
    assert motion.envelope(2.0, 1.0, 3.0, 0.01, "sit") == 1.0          # held from a cut: no fade


def test_round_corners_keeps_the_ends_and_softens_turns():
    pts = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0)]
    smooth = motion.round_corners(pts)
    assert smooth[0] == pts[0] and smooth[-1] == pts[-1]
    turns = []
    for a, b, c in zip(smooth, smooth[1:], smooth[2:]):
        h1 = math.atan2(b[1] - a[1], b[0] - a[0])
        h2 = math.atan2(c[1] - b[1], c[0] - b[0])
        turns.append(abs(motion.wrap_angle(h2 - h1)))
    assert max(turns) < math.radians(10)


def test_steps_never_blur_and_fast_moves_are_flagged(starter):
    data = copy.deepcopy(starter)
    data["scenes"][0]["shots"][0]["do"][0]["dur"] = 0.8      # mei rushes 3 m in under a second
    plan = compile_data(data)
    mei = tracks_of(plan)["mei"]
    mv = mei.moves[0]
    assert mv.steps <= motion.MAX_CADENCE["walk"] * (mv.end - mv.start) + 1
    assert any(w.startswith("mei covers") for w in motion.motion_warnings(plan))


def test_flapping_never_beats_faster_than_the_frame_rate_can_show():
    track = motion.Track("p", cast.resolve({"from": "penguin"}, "p"), cast.metrics(cast.resolve({"from": "penguin"},
                                                                                                "p")),
                         [{"t": 0, "type": "place", "at": [0, 0]},
                          {"t": 0, "type": "act", "name": "flap", "dur": 3.0, "params": {"rate": 13}}])
    flaps = [track.pose(1.0 + f / 24)["wings"]["l"]["flap"] for f in range(48)]
    crossings = sum(1 for a, b in zip(flaps, flaps[1:]) if (a - 0.9) * (b - 0.9) < 0)
    assert crossings / 2 / 2.0 <= motion.MAX_BEAT + 0.5


def test_facing_stays_continuous_along_a_u_turn():
    spec = cast.resolve({"from": "boy"}, "b")
    track = motion.Track("b", spec, cast.metrics(spec), [
        {"t": 0, "type": "place", "at": [0, 0], "facing": 0.0},
        {"t": 0.5, "type": "move", "path": [[3, 0], [3, 3], [0, 3]], "gait": "run", "end": 5.0}])
    angles = [track.facing(f / 24) for f in range(0, 24 * 6)]
    assert max(abs(b - a) for a, b in zip(angles, angles[1:])) < 0.5      # a quick turn, never a full-turn jump
    assert abs(motion.wrap_angle(angles[-1] - motion.heading_of(-1, 0))) < 0.05


@pytest.mark.parametrize("path", FILMS, ids=lambda p: p.parent.name)
def test_no_large_motion_pops_inside_shots(path):
    """Frame-to-frame accelerations stay bounded inside every shot (cuts and teleports may jump)."""
    plan = screenplay.compile_file(path, path.parent)
    tracks = tracks_of(plan)
    fps = plan["fps"]
    for cid in ("pebble", "skye", "xiaoman", "nainai", "nian"):
        if cid not in tracks:
            continue
        tr = tracks[cid]
        prev = []
        for f in range(0, plan["frames"], 2):
            t = f / fps
            shot = next(s["id"] for s in plan["shots"] if s["start"] <= t < s["end"] or s is plan["shots"][-1])
            q = tr.pose(t)
            if not q.get("visible") or (prev and prev[-1][0] != shot):
                prev = []
                if not q.get("visible"):
                    continue
            prev.append((shot, q["head"]["yaw"], q["facing"]))
            if len(prev) >= 3:
                (_, a, fa), (_, b, fb), (_, c, fc) = prev[-3:]
                assert abs(c - 2 * b + a) < 1.0, (cid, t, "head yaw")
                turn = motion.wrap_angle(fc - fb) - motion.wrap_angle(fb - fa)   # whole turns look the same
                assert abs(turn) < 1.0, (cid, t, "facing")


# ---------------------------------------------------------------------------- camera
def test_close_shots_keep_the_whole_head_in_frame(starter):
    data = copy.deepcopy(starter)
    shot = data["scenes"][0]["shots"][2]          # pip jumps
    shot["camera"] = {"size": "close", "on": ["pip"], "side": "front"}
    plan = compile_data(data)
    tracks = tracks_of(plan)
    director = camera.Director(tracks, {}, 16 / 9)
    sh = next(s for s in plan["shots"] if s["id"] == shot["id"])
    pip = tracks["pip"]
    for k in range(9):
        t = sh["start"] + (sh["end"] - sh["start"]) * k / 8
        view = director.solve(sh, t)
        head = pip.head_position(t)
        top = (head[0], head[1], head[2] + pip.m["head_r"])
        d = [top[i] - view["pos"][i] for i in range(3)]
        axis = [view["target"][i] - view["pos"][i] for i in range(3)]
        up_angle = math.atan2(d[2], math.hypot(d[0], d[1])) - math.atan2(axis[2], math.hypot(axis[0], axis[1]))
        half = math.atan(36.0 / (16 / 9) / 2 / view["lens"])
        assert up_angle < half, t
