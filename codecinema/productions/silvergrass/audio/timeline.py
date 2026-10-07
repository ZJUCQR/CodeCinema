"""
timeline.py -- load + normalise events.json, derive music cues and environment windows.

Everything downstream (score, sfx, ambience, mix) reads a `Doc`, never the raw JSON, so that the
final run simply re-reads the real out/events.json.

Contract notes:
  * event time      t = (frame - frame_start) / fps          (sample-exact: round(t * SR))
  * `duration`      frames (the events.json timeline unit). `duration_s` (seconds) or
                    `end_frame` override it.  A non-integer float < 12 is treated as seconds (warning).
  * `strength`      0..1 (clamped to 0..1.5), default per type
  * `pan`           -1..1 (default 0);  `dist` metres from camera (default 6); `lens` (mm) looked up from cuts[] by the
                    event's `cut` id (else by frame) -> sfx uses the apparent distance dist * 35 / lens
  * slow motion     config.SLOWMO united with `slowmo` events (an event replaces the config window it overlaps)
  * tempo           config.TEMPO_MAP; act3 is split at the low point (two fitted grids: the cue is a downbeat)
  * `thunder.distance`  'near' | 'mid' | 'far'  or a number (<=1: normalised 0 near..1 far, else metres)
  * cues            config.MUSIC_CUES  <-  doc.music_cues  <-  type-derived (first hat_cut / thunder / raikiri
                    event)  <-  tags (e.g. tags:["first_clash"])  <-  explicit music_cue events (highest)
"""

import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(HERE, "..", "common"), HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import config  # noqa: E402

SR = config.AUDIO_SR          # same value as dsp.SR (numpy-only here: no scipy import for post/cues.py)

KNOWN_TYPES = {
    "whoosh", "clash", "raikiri", "tree_split", "haori_shed", "spear_draw", "sheath_drop", "clash_heavy",
    "perfect_deflect", "blade_lock", "hit", "kick", "step", "dash", "jump", "land", "roll", "skid", "kneel",
    "body_fall", "draw", "sheathe", "tsuba_click", "spear_pull", "spear_spin", "kunai_throw", "kunai_deflect",
    "hat_cut", "sword_break", "cord_cut", "wind_gust", "grass_shear", "fire_ignite", "fire_burst", "thunder",
    "lightning_strike", "electric_crackle", "rain_split", "rain_start", "rain_stop", "steam_hiss", "shockwave",
    "bell", "heartbeat", "stinger", "slowmo", "music_cue",
    "drip",          # extension: a single water drop into a puddle (S24e 3256)
}
ALIASES = {"wind_blade": "grass_shear", "grass_cut": "grass_shear", "footstep": "step", "flash": None,
           "water_drop": "drip", "drop": "drip"}
CONTROL_TYPES = {"music_cue", "rain_start", "rain_stop", "wind_gust"}   # drive score / ambience (no own clip)
DURATION_TYPES = {"blade_lock", "skid", "spear_spin", "electric_crackle", "heartbeat", "slowmo"}
CUE_ORDER = list(config.MUSIC_CUES.keys())          # config order is chronological
ANCHOR_CUES = {"act1": "act1_bar1", "act2": "act2_start", "act3": "act3_start"}   # TEMPO_MAP section -> cue


class Doc:
    def __init__(self):
        self.path = None
        self.fps = config.FPS
        self.frame_start = config.FRAME_START
        self.frame_end = config.FRAME_END
        self.events = []
        self.cues = {}
        self.acts = []
        self.shots = []
        self.warnings = []
        self.unknown = {}
        self.aliased = {}
        self.draft = False
        self.cuts = []                # [{id, start, end, lens}] from the Blender export (camera sub-cuts)

    def lens_at(self, e):
        """focal length (mm) of the camera that shows event e: its `cut` id, else the cut containing its frame"""
        cid = e.get("cut")
        if cid:
            for c in self.cuts:
                if c["id"] == cid and c["lens"]:
                    return c["lens"]
        fr = e.get("frame")
        if fr is not None:
            for c in self.cuts:
                if c["start"] <= fr <= c["end"] and c["lens"]:
                    return c["lens"]
        return None

    # ------------------------------------------------------------------ time helpers
    @property
    def duration(self):
        return (self.frame_end - self.frame_start + 1) / self.fps

    @property
    def n_samples(self):
        return int(round(self.duration * SR))

    def f2t(self, frame):
        return (frame - self.frame_start) / self.fps

    def cue(self, name, default=None):
        c = self.cues.get(name)
        return c["t"] if c else default

    def act_at(self, t):
        for a in self.acts:
            if a["t0"] <= t < a["t1"]:
                return a
        return self.acts[-1] if self.acts else None

    def shot_at(self, t):
        for s in self.shots:
            if s["t0"] <= t < s["t1"]:
                return s
        return self.shots[-1] if self.shots else None

    def of_type(self, *types):
        return [e for e in self.events if e["type"] in types]

    def summary(self):
        by = {}
        for e in self.events:
            by[e["type"]] = by.get(e["type"], 0) + 1
        return dict(sorted(by.items()))


def _num(v, default):
    try:
        if v is None:
            return default
        f = float(v)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default


def _thunder_distance(v):
    """-> 'near' | 'mid' | 'far'"""
    if isinstance(v, str):
        v = v.lower().strip()
        if v in ("near", "close", "overhead"):
            return "near"
        if v in ("mid", "medium", "middle"):
            return "mid"
        return "far"
    x = _num(v, None)
    if x is None:
        return "far"
    if x <= 1.0:
        return "near" if x < 0.33 else ("mid" if x < 0.66 else "far")
    return "near" if x < 400 else ("mid" if x < 2000 else "far")


def _norm_event(raw, idx, doc):
    e = dict(raw)
    typ = str(raw.get("type", "")).strip()
    if typ in ALIASES:
        tgt = ALIASES[typ]
        doc.aliased[typ] = doc.aliased.get(typ, 0) + 1
        if tgt is None:
            return None
        typ = tgt
    e["type"] = typ
    e["idx"] = idx
    frame = _num(raw.get("frame"), None)
    if frame is None:
        doc.warnings.append(f"event #{idx} ({typ}) has no frame -> skipped")
        return None
    e["frame"] = frame
    e["t"] = doc.f2t(frame)
    e["pan"] = float(max(-1.0, min(1.0, _num(raw.get("pan"), 0.0))))
    e["dist"] = float(max(0.2, _num(raw.get("dist"), 6.0)))
    e["strength"] = float(max(0.0, min(1.5, _num(raw.get("strength"), 1.0 if typ in (
        "clash_heavy", "perfect_deflect", "lightning_strike", "raikiri", "shockwave", "sword_break") else 0.7))))
    tags = raw.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    e["tags"] = [str(x) for x in tags]
    # duration
    dur_s = None
    if "duration_s" in raw:
        dur_s = _num(raw.get("duration_s"), None)
    elif "end_frame" in raw or "frame_end" in raw:
        ef = _num(raw.get("end_frame", raw.get("frame_end")), None)
        if ef is not None:
            dur_s = max(0.0, (ef - frame) / doc.fps)
    elif "duration" in raw:
        d = raw.get("duration")
        dv = _num(d, None)
        if dv is not None:
            if isinstance(d, float) and not float(d).is_integer() and dv < 12:
                dur_s = dv
                doc.warnings.append(f"event #{idx} {typ}: duration={d} looks like seconds (non-integer < 12) -> used as seconds")
            else:
                dur_s = dv / doc.fps
    e["duration_s"] = dur_s
    if typ == "thunder":
        e["distance"] = _thunder_distance(raw.get("distance", "far"))
    if typ in ("step", "draw", "sheathe", "dash", "jump", "land", "roll", "skid", "kneel", "whoosh"):
        e["who"] = str(raw.get("who", raw.get("char", "shinobi"))).lower()
        if "saint" in e["who"] or "elder" in e["who"] or "tenko" in e["who"]:
            e["who"] = "saint"
        elif e["who"] not in ("shinobi", "saint"):
            e["who"] = "shinobi"
    if typ == "whoosh":
        e["weapon"] = str(raw.get("weapon", "katana")).lower()
    return e


def load(path=None):
    """Load events.json (default: out/events.json, fallback out/audio/draft_events.json)."""
    doc = Doc()
    if path is None:
        path = config.EVENTS_JSON if os.path.exists(config.EVENTS_JSON) else config.DRAFT_EVENTS_JSON
    doc.path = path
    raw = {}
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    else:
        doc.warnings.append(f"events file {path} not found -> timeline from config only")
    doc.fps = int(raw.get("fps", config.FPS))
    doc.frame_start = int(raw.get("frame_start", config.FRAME_START))
    doc.frame_end = int(raw.get("frame_end", config.FRAME_END))
    doc.draft = bool(raw.get("draft", False))
    if (doc.fps, doc.frame_start, doc.frame_end) != (config.FPS, config.FRAME_START, config.FRAME_END):
        doc.warnings.append(f"events timeline {doc.fps}fps {doc.frame_start}-{doc.frame_end} differs from config "
                            f"({config.FPS}fps {config.FRAME_START}-{config.FRAME_END}); using the events file values")
    acts = raw.get("acts") or config.ACTS
    doc.acts = [dict(id=a["id"], name=a.get("name", a["id"]), env=a.get("env"),
                     t0=doc.f2t(a["start"]), t1=doc.f2t(a["end"] + 1)) for a in acts]
    shots = raw.get("shots") or config.SHOTS
    doc.shots = [dict(id=s["id"], t0=doc.f2t(s["start"]), t1=doc.f2t(s["end"] + 1)) for s in shots]
    for c in raw.get("cuts") or []:
        if not isinstance(c, dict):
            continue
        a, b = _num(c.get("start"), None), _num(c.get("end"), None)
        if c.get("id") is None or a is None or b is None:
            continue
        lens = _num(c.get("lens"), None)
        doc.cuts.append(dict(id=str(c["id"]), start=a, end=b, lens=lens if (lens and lens > 1.0) else None))
    evs = []
    for i, r in enumerate(raw.get("events", []) or []):
        if not isinstance(r, dict):
            continue
        e = _norm_event(r, i, doc)
        if e is None:
            continue
        if e["type"] not in KNOWN_TYPES:
            doc.unknown[e["type"]] = doc.unknown.get(e["type"], 0) + 1
            continue
        if not (doc.frame_start - 48 <= e["frame"] <= doc.frame_end + 48):
            doc.warnings.append(f"event #{i} {e['type']} frame {e['frame']} outside the film -> skipped")
            continue
        e["lens"] = doc.lens_at(e)
        evs.append(e)
    evs.sort(key=lambda e: (e["frame"], e["idx"]))
    doc.events = evs
    for k, v in doc.unknown.items():
        doc.warnings.append(f"unknown event type '{k}' x{v} -> skipped")
    _derive_cues(doc, raw)
    return doc


def _derive_cues(doc, raw):
    cues = {k: dict(frame=v, t=doc.f2t(v), source="config") for k, v in config.MUSIC_CUES.items()}
    for k, v in (raw.get("music_cues") or {}).items():
        fv = _num(v, None)
        if fv is not None:
            cues[k] = dict(frame=fv, t=doc.f2t(fv), source="events.music_cues")
    # type-derived (story beats that are not grid anchors).  The film's first `thunder` event is the prologue's
    # far omen roll (frame 70, tags distant/omen): the 'thunder_first' story cue is the first thunder from the act II
    # start on that is not an omen.
    first = {}
    t_a2 = cues.get("act2_start", {}).get("t", doc.f2t(config.MUSIC_CUES["act2_start"]))
    for e in doc.events:
        if e["type"] == "thunder" and (e["t"] < t_a2 - 1.0 or "omen" in e["tags"] or "distant" in e["tags"]):
            continue
        first.setdefault(e["type"], e)
    for typ, cue in (("hat_cut", "hat_cut"), ("perfect_deflect", "perfect_deflect"), ("raikiri", "raikiri"),
                     ("rain_start", "rain_start"), ("thunder", "thunder_first")):
        if typ in first:
            cues[cue] = dict(frame=first[typ]["frame"], t=first[typ]["t"], source=f"first '{typ}' event")
    # tags
    tagged = {}
    for e in doc.events:
        for tg in e["tags"]:
            if tg in config.MUSIC_CUES or tg in CUE_ORDER:
                tagged.setdefault(tg, e)
    for tg, e in tagged.items():
        cues[tg] = dict(frame=e["frame"], t=e["t"], source=f"tag on '{e['type']}' event")
    # explicit music_cue events (highest priority).  Like codecinema/productions/silvergrass/blender/events.py, the first (earliest) event of a
    # cue name wins; duplicates are reported.
    explicit = {}
    for e in doc.events:
        if e["type"] == "music_cue":
            name = str(e.get("cue", "")).strip()
            if not name:
                doc.warnings.append(f"music_cue event at frame {e['frame']} without cue= -> ignored")
                continue
            if name in explicit:
                doc.warnings.append(f"music_cue '{name}' emitted twice ({explicit[name]['frame']}, {e['frame']}) "
                                    f"-> keeping the first")
                continue
            explicit[name] = e
            cues[name] = dict(frame=e["frame"], t=e["t"], source="music_cue event")
    # sanity: keep cue order monotonic.  A cue may not precede any cue whose CONFIG frame is strictly earlier
    # (cues that share a config frame, e.g. act3_start == raikiri, may land in either order).  Violators fall
    # back to their config frame, or are clamped to the earliest legal time if even that breaks the order.
    done = []
    for name in CUE_ORDER:
        if name not in cues:
            continue
        c = cues[name]
        cfg = config.MUSIC_CUES[name]
        lim = max([cues[k]["t"] for k in done if config.MUSIC_CUES[k] < cfg], default=-1.0)
        if c["t"] < lim - 1e-9:
            t_new = doc.f2t(cfg)
            src = "config (order fix)"
            if t_new < lim - 1e-9:
                t_new, src = lim, "clamped (order fix)"
            f_new = round(doc.frame_start + t_new * doc.fps, 3)
            doc.warnings.append(f"cue '{name}' at frame {c['frame']} ({c['source']}) precedes an earlier cue -> "
                                f"frame {f_new} ({src})")
            cues[name] = dict(frame=f_new, t=t_new, source=src)
        done.append(name)
    doc.cues = cues


# ------------------------------------------------------------------ derived environment windows
def rain_window(doc):
    """(t_on, t_off) of the rain; defaults: act3 start-6 s .. epilogue start + 1 s"""
    on = [e["t"] for e in doc.events if e["type"] == "rain_start"]
    off = [e["t"] for e in doc.events if e["type"] == "rain_stop"]
    a3 = next((a for a in doc.acts if a["id"] == "act3"), None)
    t_on = on[0] if on else ((a3["t0"] - 6.0) if a3 else None)
    t_off = None
    if off:
        cand = [t for t in off if t_on is None or t > t_on]
        t_off = cand[0] if cand else off[-1]
    elif a3:
        t_off = a3["t1"] + 1.0
    return t_on, t_off


def fire_window(doc):
    """(t_on, t_out): from fire_ignite until the rain has put it out (rain_start + 7 s)"""
    ig = [e["t"] for e in doc.events if e["type"] == "fire_ignite"]
    a2 = next((a for a in doc.acts if a["id"] == "act2"), None)
    t_on = ig[0] if ig else (a2["t0"] + 0.25 if a2 else None)
    r_on, _ = rain_window(doc)
    t_out = (r_on + 7.0) if r_on is not None else (a2["t1"] if a2 else None)
    return t_on, t_out


def slowmo_windows(doc):
    """[(t0, t1, event_or_None)]: the union of config.SLOWMO and the `slowmo` events.  An event window replaces
    every config window it overlaps (the lane knows the real timing); config windows that no event overlaps are
    kept, so a lane that forgets its slowmo event does not lose the S13 / S19 / S25-S26 treatment."""
    ev = []
    for e in doc.events:
        if e["type"] == "slowmo":
            d = e["duration_s"] if e["duration_s"] else 1.5
            ev.append((e["t"], e["t"] + d, e))
    out = list(ev)
    for (a, b) in getattr(config, "SLOWMO", []):
        ta, tb = doc.f2t(a), doc.f2t(b + 1)
        if not any(ea < tb and ta < eb for (ea, eb, _) in ev):
            out.append((ta, tb, None))
    out.sort(key=lambda w: w[0])
    return out


# story cues inside a metered section that must fall on a bar line: the section is split there and each part is
# fitted separately (the grid bends a little instead of the music hitting early / late)
SPLIT_CUES = {"act3": ("low_point", "act3_low")}


def _fit(s, doc, tol=0.02):
    span = s["t_end"] - s["t_anchor"]
    bar = 4 * 60.0 / s["bpm"]
    nb = max(1, int(round(span / bar)))
    fit = nb * 4 * 60.0 / span if span > 0 else s["bpm"]
    s.setdefault("bpm_nominal", s["bpm"])
    s["bars"] = nb
    s["fitted"] = abs(fit / s["bpm"] - 1.0) <= tol
    if s["fitted"]:
        s["bpm"] = fit
    else:
        s["bars"] = max(1, int(np.ceil(span / bar - 1e-6)))
        doc.warnings.append(f"tempo section {s['section']}: span {span:.3f} s is not ~{nb} bars at "
                            f"{s['bpm']:.1f} BPM (fit {fit:.2f} > {tol * 100:.0f} % off) -> nominal tempo kept, "
                            f"last bar partial")


def tempo_sections(doc):
    """config.TEMPO_MAP with anchors (t) possibly overridden by explicit music_cue events / tags for the anchor
    cues (act1_bar1 / act2_start / act3_start), within +-12 frames.  A section containing a SPLIT_CUES story cue
    (act3: the low point) is split there into two fitted grids, so the cue is a downbeat wherever it lands."""
    secs = []
    for tm in getattr(config, "TEMPO_MAP", []):
        anchor_f = tm["anchor"]
        cue = ANCHOR_CUES.get(tm["section"])
        src = "config.TEMPO_MAP"
        c = doc.cues.get(cue) if cue else None
        if c and c["source"] not in ("config", "config (order fix)", "clamped (order fix)", "events.music_cues") \
                and abs(c["frame"] - anchor_f) <= 12:
            if abs(c["frame"] - anchor_f) > 0.01:
                doc.warnings.append(f"tempo anchor {tm['section']} moved {anchor_f} -> {c['frame']} ({c['source']})")
            anchor_f = c["frame"]
            src = c["source"]
        secs.append(dict(section=tm["section"], bpm=float(tm["bpm"]), anchor_frame=anchor_f, t_anchor=doc.f2t(anchor_f),
                         t_end=doc.f2t(tm["end"] + 1), source=src))
    # a section ends where the next begins; act3 ends at the music 'silence'
    for a, b in zip(secs, secs[1:]):
        a["t_end"] = b["t_anchor"]
    if secs:
        sil = doc.cue("silence")
        if sil is not None and sil > secs[-1]["t_anchor"]:
            secs[-1]["t_end"] = sil
    out = []
    for s in secs:
        split = SPLIT_CUES.get(s["section"])
        tc = doc.cue(split[0]) if split else None
        bar = 4 * 60.0 / s["bpm"]
        if tc is not None and s["t_anchor"] + 2 * bar <= tc <= s["t_end"] - 1.0 * bar:
            s2 = dict(section=split[1], bpm=s["bpm"], anchor_frame=round(doc.frame_start + tc * doc.fps, 3), t_anchor=tc,
                      t_end=s["t_end"], source=f"split at '{split[0]}'")
            s["t_end"] = tc
            _fit(s, doc, 0.025)
            s2["bpm"] = s["bpm"]                     # continue at the (fitted) tempo of the first part
            _fit(s2, doc, 0.03)
            out += [s, s2]
        else:
            _fit(s, doc)
            out.append(s)
    return out


def silence_windows(doc):
    """hard silences: music off [silence, final_pass); every stem off [white_silence, blade_ring);
    ambience off [white_silence, final_pass)"""
    w = {}
    s, fp = doc.cue("silence"), doc.cue("final_pass")
    if s is not None and fp is not None and fp > s:
        w["music"] = (s, fp)
    ws, br = doc.cue("white_silence"), doc.cue("blade_ring")
    if ws is not None:
        w["all"] = (ws, br if (br is not None and br > ws) else ws + 0.5)
        if fp is not None and fp > ws:
            w["ambience"] = (ws, fp)
    return w


def wetness_at(doc, t):
    on, off = rain_window(doc)
    if on is None or t < on + 1.0:
        return 0.0
    if off is not None and t > off + 8.0:
        return 0.3            # still damp after the rain
    return 1.0


def fire_at(doc, t):
    on, out = fire_window(doc)
    if on is None or t < on or (out is not None and t > out):
        return 0.0
    return 1.0
