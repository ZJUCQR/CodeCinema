"""
stress_test.py -- robustness tests of the audio pipeline against the shapes the real Blender export will have
(run it before the final mix; every variant is derived from out/audio/draft_events.json).

    .venv/bin/python src/audio/stress_test.py            # fast checks (timeline + score + sfx placement) ~1 min
    .venv/bin/python src/audio/stress_test.py --full     # + render and master every variant through mix.render
                                                         #   and require its QC gates (checks.qc_pass); ~2 min each

Variants
  A  act1a lane doc: slowmo@595 (36 f) + blade_lock@599 duration=31 tags=[grind, slowmo]
     -> the slowed lock covers exactly 599..630 and its release 'shing' lands within 1.5 f of 630
  B  only the S07 lane emits a slowmo event -> the config windows S13 / S19 / S25-S26 survive (union), the S26
     sheathe at 3412 is still the slow one and the ambience muffle windows are all there
  C  story beats off the half-beat grid: grass_shear 1098, overhead clash_heavy 1128, low point 2958
     -> every music accent sits on its event (<= 1 frame), grid warnings are raised, the act-III grid is re-fitted
  D  lookups: the overhead block is a plain `clash` (0.9); no S12 blade_lock but a stray one in S18;
     sheathe 3406 + tsuba_click 3412; a stinger event on the hat cut
     -> the overhead tutti uses the clash, the stray lock is ignored, ONE click at 3412, the stinger is merged
  E  messy Blender export: missing pan/dist, numeric strings, fractional frames, aliases, unknown types, garbage,
     340 extra footsteps, cuts[] with telephoto lenses
  F  empty events file (config cues only)
Reports: out/audio/stress/<variant>_report.json (+ stress_summary.json); audio renders go to a temp dir.
"""
import argparse
import copy
import json
import os
import random
import shutil
import sys
import tempfile
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(HERE, "..", "common"), HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import config  # noqa: E402
import dsp  # noqa: E402
import analysis as an  # noqa: E402
import timeline as tl  # noqa: E402
import score  # noqa: E402
import sfx  # noqa: E402
from dsp import SR, n_of  # noqa: E402

DRAFT = config.DRAFT_EVENTS_JSON
OUT = os.path.join(config.AUDIO_DIR, "stress")


def _f(fr):
    return (fr - config.FRAME_START) / config.FPS


def variant_A(base):
    d = copy.deepcopy(base)
    d["events"] = [e for e in d["events"] if not (e["type"] == "slowmo" and e["frame"] == 595)]
    d["events"] += [dict(frame=595, type="slowmo", duration=36),
                    dict(frame=599, type="blade_lock", duration=31, strength=0.35, tags=["grind", "slowmo"], pan=0.0, dist=4.0)]
    return d


def variant_B(base):
    d = copy.deepcopy(base)
    d["events"] = [e for e in d["events"] if not (e["type"] == "slowmo" and e["frame"] != 595)]
    return d


def variant_C(base):
    d = copy.deepcopy(base)
    for e in d["events"]:
        if e["type"] == "grass_shear":
            e["frame"] = 1098
        if e["type"] == "clash_heavy" and e["frame"] == 1132:
            e["frame"] = 1128
        if e["type"] == "rain_split":
            e["frame"] = 2958
            e["tags"] = ["low_point"]
        if e["type"] == "shockwave" and e["frame"] == 2952:
            e["frame"] = 2960
        if e["type"] == "music_cue" and e.get("cue") == "low_point":
            e["frame"] = 2958
    return d


def variant_D(base):
    d = copy.deepcopy(base)
    ev = []
    for e in d["events"]:
        if e["type"] == "clash_heavy" and e["frame"] == 1132:
            e = dict(e, type="clash", strength=0.9)
        if e["type"] == "blade_lock":
            continue
        if e["type"] == "sheathe" and e["frame"] == 3412:
            e = dict(e, frame=3406)
        ev.append(e)
    ev.append(dict(frame=2150, type="blade_lock", duration=16, pan=0.1, dist=3.0))
    ev.append(dict(frame=1420, type="stinger", strength=0.8))
    d["events"] = ev
    return d


def variant_E(base):
    rnd = random.Random(7)
    evs = []
    for e in base["events"]:
        e = dict(e)
        e["lane"] = "act1a"
        e["onscreen"] = rnd.random() < 0.7
        r = rnd.random()
        if r < 0.15:
            e.pop("pan", None)
            e.pop("dist", None)
        elif r < 0.25:
            e["strength"] = str(e.get("strength", 0.6))
        elif r < 0.3 and e["type"] not in ("music_cue", "rain_start", "rain_stop"):
            e["frame"] = e["frame"] + 0.5
        if e["type"] == "music_cue" and e.get("cue") in ("first_clash", "act1_bar1", "act2_start", "act3_start"):
            e["frame"] += 2
        evs.append(e)
    evs += [
        dict(frame=2600, type="thunder", distance=0.1, pan=0.3, dist=400.0),
        dict(frame=2650, type="thunder", distance=3500),
        dict(frame=2700, type="thunder", distance="overhead"),
        dict(frame=1900, type="skid", duration=0.75),
        dict(frame=2100, type="spear_spin", end_frame=2130),
        dict(frame=2750, type="electric_crackle", duration_s=1.2),
        dict(frame=1000, type="heartbeat", bpm=70, duration=48),
        dict(frame=1100, type="wind_blade", strength=0.9),
        dict(frame=900, type="footstep", who="Tenkosai"),
        dict(frame=950, type="foo_bar"), dict(frame=955, type="foo_bar"),
        dict(frame=None, type="clash"), dict(frame=6000, type="clash"), dict(frame=-100, type="clash"),
        dict(frame=config.FRAME_END, type="step", who="shinobi"),
        dict(frame=1, type="clash", strength=2.5, pan=4, dist=-3),
        dict(frame=700, type="whoosh", weapon="naginata", who="elder"),
        dict(frame=701, type="whoosh", weapon="yari"), dict(frame=702, type="whoosh", weapon="shuriken"),
        dict(frame=703, type="whoosh", weapon="fist"),
        dict(frame=1500, type="body_fall", who="saint"), dict(frame=1580, type="spear_pull"),
        dict(frame=800, type="clash", tags="first_clash"),
        "not a dict",
    ]
    for f in range(700, 2400, 5):
        evs.append(dict(frame=f, type="step", who=rnd.choice(["shinobi", "saint"]), strength=rnd.uniform(0.2, 0.6),
                        pos=[0, 0, 0.05], pan=rnd.uniform(-1, 1), dist=rnd.uniform(3, 30)))
    d = dict(fps=config.FPS, frame_start=config.FRAME_START, frame_end=config.FRAME_END, acts=config.ACTS,
             shots=[dict(id=s["id"], start=s["start"], end=s["end"], lane=s["lane"]) for s in config.SHOTS],
             cuts=base.get("cuts", []), events=evs, music_cues=dict(config.MUSIC_CUES), partial=False, warnings=[])
    return d


def variant_F(base):
    return dict(fps=config.FPS, frame_start=config.FRAME_START, frame_end=config.FRAME_END, events=[])


VARIANTS = dict(A=variant_A, B=variant_B, C=variant_C, D=variant_D, E=variant_E, F=variant_F)


# ============================================================================================ fast checks
def _render_score(doc):
    """arrangement only (no audio): marks + warnings"""
    C = {k: v["t"] for k, v in doc.cues.items()}
    secs = {s["section"]: s for s in tl.tempo_sections(doc)}
    G = {n: score.Grid(s["t_anchor"], s["bpm"], s["t_end"], nbars=s.get("bars"), name=n) for n, s in secs.items()}
    S = score.Score(fps=doc.fps)
    score.arr_prologue(S, doc, C)
    score.arr_act1_pre(S, doc, C, G["act1"])
    m1 = score.arr_act1(S, doc, C, G["act1"])
    m2 = score.arr_act2(S, doc, C, G["act2"])
    m3 = score.arr_act3(S, doc, C, G["act3"], G.get("act3_low"))
    score.arr_final_pass(S, doc, C)
    score.arr_epilogue(S, doc, C)
    return S, dict(act1=m1, act2=m2, act3=m3), secs


def fast_checks(name, doc):
    res = dict(variant=name, checks={}, info={})
    ck, info = res["checks"], res["info"]
    S, marks, secs = _render_score(doc)
    ev_marks = [m for m in S.marks if m.get("t_event") is not None]
    ck["music_marks_within_1_frame"] = all(abs(m["t"] - m["t_event"]) <= 1.0 / doc.fps + 1e-6 for m in ev_marks)
    f0 = doc.frame_start
    info["marks"] = {m["name"]: (round(f0 + m["t"] * doc.fps, 2),
                                 None if m["t_event"] is None else round(f0 + m["t_event"] * doc.fps, 2))
                     for m in S.marks}
    info["grid_warnings"] = S.warnings
    info["tempo"] = {k: (round(v["bpm"], 2), v["bars"], v.get("fitted")) for k, v in secs.items()}
    info["doc_warnings"] = doc.warnings[:12]
    slow = tl.slowmo_windows(doc)
    info["slowmo_frames"] = [(round(f0 + a * doc.fps, 1), round(f0 + b * doc.fps, 1), e is not None)
                             for a, b, e in slow]
    ck["slowmo_config_windows_kept"] = all(any(a <= _f(fa) + 0.05 and b >= _f(fb + 1) - 0.05 for a, b, _ in slow)
                                           or any(e is not None and a < _f(fb + 1) and _f(fa) < b for a, b, e in slow)
                                           for fa, fb in config.SLOWMO)
    X = sfx.render_all(doc, merged_bells=[doc.cue("title"), doc.cue("end_card")],
                       merged_stingers=[marks["act1"]["hat_cut"]],
                       breath=(doc.cue("raikiri") - 0.5, doc.cue("raikiri")) if doc.cue("raikiri") else None)
    ck["sfx_finite"] = bool(np.all(np.isfinite(X["dry"])) and np.all(np.isfinite(X["exempt"])))
    info["sfx_notes"] = X["notes"]
    info["placed"] = len(X["placed"])
    if name == "A":
        e = next(x for x in doc.events if x["type"] == "blade_lock" and abs(x["frame"] - 599) < 0.5)
        ctx = sfx.event_ctx(doc, e, slow)
        clip = sfx.render_event(e, ctx)
        a = dsp.mono(dsp.as_stereo(clip.audio))
        pad = np.concatenate([np.zeros(n_of(0.2)), a, np.zeros(n_of(0.3))])
        t_exp = e["duration_s"]
        t_on, _ = an.guided_onset(pad, 0.2 + t_exp - 0.05, search=0.12)
        rel_f = 599 + ((t_on - 0.2) if t_on is not None else 0.0) * doc.fps
        end_f = 599 + (a.shape[-1] / SR) * doc.fps
        info["blade_lock"] = dict(slow=ctx["slow"], release_frame=round(rel_f, 2), clip_end_frame=round(end_f, 1))
        ck["blade_lock_release_on_630"] = t_on is not None and abs(rel_f - 630) <= 1.5
    if name == "B":
        ck["slowmo_windows_4"] = len(slow) >= 4
        e = next((x for x in doc.events if x["type"] == "sheathe" and abs(x["frame"] - 3412) < 1), None)
        if e:
            ck["s26_sheathe_in_slowmo"] = sfx.event_ctx(doc, e, slow)["in_slowmo"]
    if name == "C":
        mk = {m["name"]: m for m in S.marks}
        ck["grass_shear_on_event"] = abs(mk["grass_shear"]["t"] - _f(1098)) < 1e-3
        ck["overhead_on_event"] = abs(mk["overhead"]["t"] - _f(1128)) < 1e-3
        ck["low_point_on_event"] = abs(mk["low_point"]["t"] - _f(2958)) < 1e-3
        ck["grid_warnings_raised"] = any("grass_shear" in w for w in S.warnings)
        ck["act3_split_fitted"] = "act3_low" in secs and bool(secs["act3"].get("fitted"))
    if name == "D":
        mk = {m["name"]: m for m in S.marks}
        ck["overhead_uses_plain_clash"] = mk["overhead"]["src"] == "clash event" and abs(mk["overhead"]["t"] - _f(1132)) < 1e-3
        ck["stray_blade_lock_ignored"] = mk["blade_lock"]["t_event"] is None
        pl = [p for p in X["placed"] if p["type"] in ("sheathe", "tsuba_click") and p["t"] > _f(3380)]
        ck["one_click_at_3412"] = len(pl) >= 1 and all(abs(p["t"] - _f(3412)) < 1e-3 for p in pl)
        ck["stinger_merged"] = any(s["type"] == "stinger" for s in X["skipped"])
    if name == "E":
        ck["unknown_types_reported"] = "foo_bar" in doc.unknown
        ck["aliases_mapped"] = doc.aliased.get("wind_blade", 0) == 1 and doc.aliased.get("footstep", 0) == 1
    res["pass"] = all(ck.values())
    return res


def main():
    ap = argparse.ArgumentParser(description="stress-test the audio pipeline against real-lane event shapes")
    ap.add_argument("--full", action="store_true", help="also render + master every variant (mix.render)")
    ap.add_argument("--only", default="A,B,C,D,E,F")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    base = json.load(open(DRAFT, encoding="utf-8"))
    tmp = tempfile.mkdtemp(prefix="silvergrass_stress_")
    summary = {}
    T0 = time.time()
    try:
        for name in a.only.split(","):
            d = VARIANTS[name](base)
            d["draft"] = False
            path = os.path.join(tmp, f"events_{name}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False)
            doc = tl.load(path)
            r = fast_checks(name, doc)
            if a.full:
                import mix
                rep = mix.render(path, os.path.join(tmp, f"mix_{name}.wav"),
                                 report_path=os.path.join(a.out, f"{name}_report.json"),
                                 stems_dir=os.path.join(tmp, f"stems_{name}"), spec_dir=os.path.join(tmp, "spec"),
                                 spectrograms=False, log=lambda *x: None)
                r["mix_checks"] = rep["checks"]
                r["mix"] = dict(lufs=rep["integrated_lufs"], tp=rep["true_peak_dbtp"], music_sync=rep["music_sync"]["max_abs_ms"],
                                onsets=f"{rep['onset_check']['within_10ms']}/{rep['onset_check']['checked']}",
                                story_hits={h["cue"]: (h["hit_max_momentary"], h["contrast_3s"]) for h in rep["story_hits"]["hits"]},
                                film_max=rep["story_hits"]["film_max"], total_s=rep["timings"]["total_s"])
                r["pass"] = r["pass"] and rep["checks"]["qc_pass"]
            summary[name] = r
            bad = [k for k, v in r["checks"].items() if not v] + \
                ([k for k, v in r.get("mix_checks", {}).items() if not v and k not in ("events_real", "all_pass", "qc_pass")])
            print(f"[{name}] {'PASS' if r['pass'] else 'FAIL'}  {('failed: ' + str(bad)) if bad else ''}")
            for k in ("blade_lock", "tempo"):
                if k in r["info"]:
                    print(f"      {k}: {r['info'][k]}")
            if name in ("B", "A"):
                print(f"      slowmo windows (frames): {r['info']['slowmo_frames']}")
            if name in ("C", "D"):
                keep = ("grass_shear", "overhead", "blade_lock", "shove", "low_point")
                print(f"      marks (music frame, event frame): { {k: v for k, v in r['info']['marks'].items() if k in keep} }")
                print(f"      grid warnings: {len(r['info']['grid_warnings'])}")
            if "mix" in r:
                print(f"      mix: {r['mix']}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    summary["_meta"] = dict(full=a.full, seconds=round(time.time() - T0, 1),
                            all_pass=all(v["pass"] for k, v in summary.items() if not k.startswith("_")))
    with open(os.path.join(a.out, "stress_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1, default=str)
    print(f"stress: {'ALL PASS' if summary['_meta']['all_pass'] else 'FAILURES'} in {summary['_meta']['seconds']} s "
          f"-> {os.path.join(a.out, 'stress_summary.json')}")
    sys.exit(0 if summary["_meta"]["all_pass"] else 1)


if __name__ == "__main__":
    main()
