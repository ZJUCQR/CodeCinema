"""
secondary.py - secondary motion of the costume chains, documented entry points.

The spring solver itself lives in characters.apply_secondary_motion (rig lane): per
chain follow-the-leader (verlet-style) particle springs pinned to the EVALUATED parent bones, gravity-aware hang,
air drag towards the wind + fx_time flutter, head/chest collision spheres, wet mode, reset at every hard cut with a
one-second (config.FPS frames) pre-roll that carries the cut's entry velocity, dt = fxclock.fx_time_at(f) -
fx_time_at(f-1), keys into '<rig>_secondary' pushed as the TOP NLA track. build_scene calls it directly. This module is the thin, documented
facade with stable names, so callers do not depend on the rig module's argument conventions, plus track hygiene:

  apply_secondary(rigs, frame_ranges, cuts=None, wind_fn=None, wet_fn=None, preroll=None, substeps=4) -> dict
        rigs: rig | name | list | {'SHINOBI': rig, ...}; frame_ranges: (f0, f1) or [(f0, f1), ...] (merged);
        cuts: None = timeline markers + config shot starts; wind_fn: None = environment.wind_at when the env is
        built (else 1.0) | float | callable(frame) -> float | (strength, (dx, dy)); wet_fn: None = the env's keyed
        wetness (world['env_wet']) | float | callable(frame). Sampling runs inside bl_util.muted_modifiers.
        Chains: SHINOBI hachimaki tails (tail1.*, tail2.*), SAINT beard.1-3 (SAINT_beard_cord rides beard.3),
        sleeve.L/R pouches and hem.L/R/B of the haori. Wind lifts / streams the tails (strength 1 = breeze ->
        about 0.3-0.5 m downwind, 2 = gale -> ~60 deg from vertical), wet makes them heavy and hanging.
  push_secondary_tracks(rigs) -> list[str]
        Makes '<rig>_secondary' the TOP NLA track of each rig (re-creating it at the top if a later track was
        added above it) and strips any channel that is not a secondary-chain bone rotation.
  chain_bones(rig) -> list[str]   the secondary bones of that rig (characters.SECONDARY_BONES)
  settle(rig, wind=0.0, wet=0.0)  static previews: let the chains hang for the current pose (no keys)
"""
import os
import sys

import bpy

ROOT = (__import__("os").environ.get("SILVERGRASS_ROOT") or str(next(p for p in __import__("pathlib").Path(__file__).resolve().parents if (p / "src" / "common" / "config.py").is_file())))   # repo root (portable)
for _p in (os.path.join(ROOT, "src", "common"), os.path.join(ROOT, "src", "blender")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import bl_util as U  # noqa: E402


def _C():
    import characters
    return characters


def _rig_list(rigs):
    C = _C()
    if isinstance(rigs, dict):
        rigs = list(rigs.values())
    if not isinstance(rigs, (list, tuple)):
        rigs = [rigs]
    return [C.get_rig(r) for r in rigs]


def chain_bones(rig):
    """Secondary-chain bone names of `rig` (present on the rig)."""
    C = _C()
    rig = C.get_rig(rig)
    return [b for b in C.SECONDARY_BONES[rig["char"]] if b in rig.pose.bones]


def _merge(ranges):
    if isinstance(ranges, tuple) and len(ranges) == 2 and not isinstance(ranges[0], (list, tuple)):
        ranges = [ranges]
    out = []
    for a, b in sorted((int(a), int(b)) for a, b in ranges):
        if out and a <= out[-1][1] + 1:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def _default_wind():
    try:
        import environment
        w = bpy.data.worlds.get("ENV_world")
        if w is not None and "env_wind" in w.keys():
            cache = {}

            def wind(frame):
                k = round(float(frame), 4)
                if k not in cache:
                    cache[k] = environment.wind_at(frame)
                return cache[k]
            return wind
    except Exception:  # noqa: BLE001
        pass
    return 1.0


def apply_secondary(rigs, frame_ranges, cuts=None, wind_fn=None, wet_fn=None, preroll=None, substeps=4):
    """Simulate + key the secondary chains of `rigs` over `frame_ranges` (see module doc). Returns
    {rig name: [per-range report dicts]} and pushes the '<rig>_secondary' tracks to the top."""
    C = _C()
    rl = _rig_list(rigs)
    wind = _default_wind() if wind_fn is None else wind_fn
    report = {r.name: [] for r in rl}
    with U.muted_modifiers():
        for f0, f1 in _merge(frame_ranges):
            res = C.apply_secondary_motion(rl, f0, f1, wind=wind, cuts=cuts, preroll=preroll, substeps=substeps,
                                           wetness=wet_fn)
            for r, rep in zip(rl, res):
                report[r.name].append(dict(rep, span=(f0, f1)))
    push_secondary_tracks(rl)
    return report


def push_secondary_tracks(rigs):
    """Ensure '<rig>_secondary' is the TOP NLA track (REPLACE, influence 1, HOLD) of every rig and that its action
    only animates secondary-chain bone rotations. Returns the track names handled."""
    names = []
    for rig in _rig_list(rigs):
        name = f"{rig.name}_secondary"
        act = bpy.data.actions.get(name)
        ad = rig.animation_data
        if act is None or ad is None:
            continue
        allowed = {f'pose.bones["{b}"].rotation_euler' for b in chain_bones(rig)}
        for layer in act.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    for fc in list(cb.fcurves):
                        if fc.data_path not in allowed:
                            cb.fcurves.remove(fc)
        tracks = list(ad.nla_tracks)
        tr = next((t for t in tracks if t.name == name), None)
        if tr is None or not tr.strips:
            continue
        if tracks[-1] != tr:                          # something was stacked above it: rebuild at the top
            st = tr.strips[0]
            spec = dict(start=st.frame_start, end=st.frame_end, a0=st.action_frame_start, a1=st.action_frame_end,
                        slot=st.action_slot)
            ad.nla_tracks.remove(tr)
            tr = ad.nla_tracks.new()
            tr.name = name
            st = tr.strips.new(name, int(spec["start"]), act)
            if spec["slot"] is not None:
                st.action_slot = spec["slot"]
            st.use_sync_length = False
            st.action_frame_start, st.action_frame_end = spec["a0"], spec["a1"]
            st.frame_start, st.frame_end = spec["start"], spec["end"]
        st = tr.strips[0]
        st.extrapolation = 'HOLD'
        st.blend_type = 'REPLACE'
        st.influence = 1.0
        tr.mute = False
        names.append(name)
    return names


def settle(rig, wind=0.0, wet=0.0):
    """Static preview: chains hang for the current pose (characters.settle_secondary, no keys)."""
    _C().settle_secondary(rig, wind=wind, wetness=wet)
