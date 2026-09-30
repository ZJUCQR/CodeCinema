#!/usr/bin/env python3
"""
src/post/cues.py — music-cue frames exactly as the audio lane resolves them.

Picture events that are locked to the score (the main-title seal lands on the 'title' cue, where the
score places its temple bell + deep drum) must use the SAME frame the audio lane used, or the seal and
its sound drift apart. The audio lane resolves cues in src/audio/timeline.py:

    config.MUSIC_CUES  <-  events.json "music_cues"  <-  first-of-type events  <-  tags  <-  music_cue events

(+ a monotonic-order sanity fix). This module reuses that code (loaded read-only by file path, so the
audio lane's modules never shadow ours on sys.path) and falls back to a local re-implementation of the
same priority order if it cannot be imported. Only the real out/events.json is consulted — never the
audio lane's draft — so the final picture follows the real animation.

  resolve(name)          -> (frame:int|None, source:str)
  resolve_many(names)    -> {name: (frame, source)}
  events_fingerprint()   -> short sha1 of out/events.json ("none" when absent)
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
if os.path.join(ROOT, "src", "common") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src", "common"))
import config  # noqa: E402

AUDIO_TIMELINE = os.path.join(ROOT, "src", "audio", "timeline.py")
_cache: dict = {}


def _events_path(events_path=None):
    return os.path.abspath(events_path or config.EVENTS_JSON)


def events_fingerprint(events_path=None):
    p = _events_path(events_path)
    if not os.path.exists(p):
        return "none"
    with open(p, "rb") as fh:
        return hashlib.sha1(fh.read()).hexdigest()[:12]


def _load_audio_timeline():
    """Import src/audio/timeline.py under a private module name (read-only reuse)."""
    if "mod" in _cache:
        return _cache["mod"]
    mod = None
    try:
        spec = importlib.util.spec_from_file_location("_post_audio_timeline", AUDIO_TIMELINE)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if not hasattr(mod, "load"):
            mod = None
    except Exception as e:  # the audio lane's module is not ours: never let it break the titles
        print(f"[cues] note: could not import {AUDIO_TIMELINE} ({e!r}); using the local resolver", file=sys.stderr)
        mod = None
    _cache["mod"] = mod
    return mod


def _local_resolve(raw):
    """Same priority order as src/audio/timeline._derive_cues (subset: no type-derived defaults needed here
    except the ones that exist there)."""
    cues = {k: (int(v), "config") for k, v in config.MUSIC_CUES.items()}
    for k, v in (raw.get("music_cues") or {}).items():
        try:
            cues[k] = (int(round(float(v))), "events.music_cues")
        except (TypeError, ValueError):
            pass
    evs = [e for e in raw.get("events", []) or [] if isinstance(e, dict) and "frame" in e]
    evs.sort(key=lambda e: float(e["frame"]))
    first = {}
    for e in evs:
        first.setdefault(e.get("type"), e)
    for typ, cue in (("hat_cut", "hat_cut"), ("perfect_deflect", "perfect_deflect"), ("raikiri", "raikiri"),
                     ("rain_start", "rain_start"), ("thunder", "thunder_first")):
        if typ in first:
            cues[cue] = (int(round(float(first[typ]["frame"]))), f"first '{typ}' event")
    for e in evs:
        tags = e.get("tags") or []
        for tg in ([tags] if isinstance(tags, str) else tags):
            if tg in config.MUSIC_CUES and not cues.get(tg, (0, ""))[1].startswith("tag"):
                cues[tg] = (int(round(float(e["frame"]))), f"tag on '{e.get('type')}' event")
    for e in evs:
        if e.get("type") == "music_cue" and str(e.get("cue", "")).strip():
            cues[str(e["cue"]).strip()] = (int(round(float(e["frame"]))), "music_cue event")
    return cues


def _resolve_all(events_path=None):
    p = _events_path(events_path)
    key = (p, os.path.getmtime(p) if os.path.exists(p) else None)
    if _cache.get("key") == key:
        return _cache["cues"]
    if not os.path.exists(p):
        cues = {k: (int(v), "config (no events.json)") for k, v in config.MUSIC_CUES.items()}
    else:
        mod = _load_audio_timeline()
        cues = None
        if mod is not None:
            try:
                doc = mod.load(p)
                cues = {k: (int(round(float(v["frame"]))), str(v.get("source", "?"))) for k, v in doc.cues.items()}
            except Exception as e:
                print(f"[cues] note: audio timeline failed on {p} ({e!r}); using the local resolver", file=sys.stderr)
                cues = None
        if cues is None:
            with open(p, encoding="utf-8") as fh:
                cues = _local_resolve(json.load(fh))
    _cache.update(key=key, cues=cues)
    return cues


def resolve(name, events_path=None):
    """(frame, source) for a cue name; (None, 'unknown') when neither the events nor config define it."""
    return _resolve_all(events_path).get(name, (None, "unknown"))


def resolve_many(names, events_path=None):
    allc = _resolve_all(events_path)
    return {n: allc.get(n, (None, "unknown")) for n in names}


if __name__ == "__main__":
    for k, (f, src) in _resolve_all().items():
        print(f"  {k:16s} {f!s:>6}  {src}")
    print("  events:", _events_path(), events_fingerprint())
