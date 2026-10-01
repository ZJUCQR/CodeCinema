"""
acts - one choreography module per lane.

Lane contract
    src/blender/acts/<lane>.py exposes build(ctx) where
        ctx = dict(chars=<characters.build() result>, env=<environment.build() result>, config=config,
                   lane=<lane>, span=(f0, f1), shots=[shot dicts], quality='layout'|'preview'|'final',
                   stubs={module: True if a placeholder was used})
    It keys ONLY inside its span (lane_tools audits: keys up to 6 f beyond [s-0.3, e+0.7] are kept, anything
    further is deleted with a warning), creates its cameras through cameras.shot (sub-cut ids 'S12a' ...),
    emits events through events.emit, and names its objects '<shot>_...'. build_scene wraps the call in
    lane_tools.begin_lane / end_lane, so the lane's keys end up in its own NLA strips.
    Objects the lane creates (in its LANE_<lane> collection, renderable, without visibility keys) are keyed
    hidden outside its span automatically; set ob['persist'] = True for one that must stay in later lanes
    (QA fails a lane object that renders outside its span otherwise).  To art-direct secondary-motion bones
    (hachimaki tails, beard) over a range, call lane_tools.secondary_override(rig, f0, f1, bones) and key those
    bones in the lane; the '<rig>_secondary' springs are muted there.
    Real lanes take their span/shots from config (config.lane_span / shots_for_lane). Dev lanes (name starting
    with '_', e.g. acts/_demo.py) live on a private frame range and define module-level SPAN = (f0, f1) and
    SHOTS = [dict(id=..., start=..., end=..., desc=...)].
"""
import importlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# repo root, resolved like settings.ROOT; the single sys.path bootstrap for every lane module (acts.<lane>)
ROOT = os.environ.get("SILVERGRASS_ROOT") or os.path.abspath(os.path.join(HERE, "..", "..", ".."))
for _p in (os.path.join(ROOT, "src", "common"), os.path.join(ROOT, "src", "blender")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import config  # noqa: E402


def available_lanes():
    """Lane modules present on disk (real lanes in config.LANES order, then dev lanes)."""
    names = [f[:-3] for f in os.listdir(HERE) if f.endswith(".py") and f != "__init__.py"]
    real = [ln for ln in config.LANES if ln in names]
    return real + sorted(n for n in names if n not in real)


def lane_module(lane):
    """Import acts.<lane> (fresh import each build process)."""
    return importlib.import_module(f"acts.{lane}")


def lane_span(lane, module=None):
    """(f0, f1) of a lane: module SPAN for dev lanes, else config.lane_span."""
    if lane in config.LANES:
        return tuple(config.lane_span(lane))
    mod = module or lane_module(lane)
    return tuple(getattr(mod, "SPAN"))


def lane_shots(lane, module=None):
    """Shot dicts of a lane (config for real lanes, module SHOTS for dev lanes)."""
    if lane in config.LANES:
        return config.shots_for_lane(lane)
    mod = module or lane_module(lane)
    return list(getattr(mod, "SHOTS", []))


def sub_cuts(lane, splits=None):
    """[(cut id, f0, f1)] of a real lane: its config shots, each split at the sub-cut start frames given in
    splits[shot id] (sub-cuts get the suffixes a, b, c ...; a shot without splits keeps its own id)."""
    splits = splits or {}
    shots = config.shots_for_lane(lane)
    unknown = set(splits) - {s["id"] for s in shots}
    if unknown:
        raise ValueError(f"sub_cuts({lane!r}): not shots of this lane: {sorted(unknown)}")
    out = []
    for s in shots:
        starts = [s["start"], *splits.get(s["id"], ())]
        if any(a >= b for a, b in zip(starts, starts[1:])) or starts[-1] > s["end"]:
            raise ValueError(f"sub_cuts({lane!r}): {s['id']} splits must rise inside {s['start']}-{s['end']}: "
                             f"{starts[1:]}")
        if len(starts) == 1:
            out.append((s["id"], s["start"], s["end"]))
            continue
        ends = [f - 1 for f in starts[1:]] + [s["end"]]
        out += [(s["id"] + chr(ord("a") + i), a, b) for i, (a, b) in enumerate(zip(starts, ends))]
    return out
