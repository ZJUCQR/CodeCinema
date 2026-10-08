"""Composer: every style renders a cue, cues keep the harmony rules, plans report errors clearly."""
import os
import traceback
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pytest

from codecinema.audio import composer as C
from codecinema.audio import dsp, instruments, soundfont
from codecinema.audio import theory as T

soundfont.use("off")  # synthesized instruments: the fallback every machine has, and deterministic

STYLES = [row["name"] for row in C.catalog() if not row["alias_of"]]


def _render_style(style):
    """worker: render a 4.5 s cue of one style (bank off), with room for its pre-roll and tail -> stats (or the error).
    Sustained notes are cached 1.5 s long instead of 4 s: no note in the cue is held longer (longer gates would loop
    through the library's own crossfade), and the sweep runs in a fraction of the time."""
    try:
        from codecinema.audio import composer, dsp, instruments, soundfont
        soundfont.use("off")
        instruments.LONG_SUSTAIN = 1.5
        stems = composer.render_score({"cues": [{"start": 0.8, "end": 5.3, "style": style, "intensity": 0.8,
                                                 "seed": 2}]}, 9.0, seed=2)
        total = sum(stems.values())
        return {"shape": total.shape, "finite": bool(all(np.all(np.isfinite(x)) for x in stems.values())),
                "peak": dsp.peak(total), "rms": {k: dsp.rms(x) for k, x in stems.items()},
                "edges": float(np.max(np.abs(total[:, [0, -1]])))}
    except Exception:  # noqa: BLE001 -- report the failure for this item alone
        return {"error": traceback.format_exc()}


@pytest.fixture(scope="module")
def rendered():
    """all styles rendered in parallel worker processes (real rendering, a fraction of the wall time)"""
    heavy = ("festive_chinese", "jazz_swing", "adventure", "march", "celtic", "comic_chase", "triumph", "waltz")
    order = sorted(STYLES, key=lambda s: (s not in heavy, heavy.index(s) if s in heavy else 0))
    with ProcessPoolExecutor(max_workers=max(1, min(8, (os.cpu_count() or 2) - 1))) as pool:
        return dict(zip(order, pool.map(_render_style, order)))


@pytest.mark.parametrize("style", STYLES)
def test_every_style_renders_a_cue(rendered, style):
    s = rendered[style]
    assert "error" not in s, s.get("error")
    assert s["shape"] == (2, dsp.n_of(9.0))
    assert s["finite"]
    assert 0.0 < s["peak"] <= dsp.db2lin(-1.0) + 1e-9
    assert s["edges"] == 0.0
    assert s["rms"]["melody"] > 1e-4 and s["rms"]["harmony"] > 1e-4


def _arrange(style, dur=16.0, seed=3, **cue):
    p = C.plan({"cues": [{"start": 0.0, "end": dur, "style": style, "intensity": 0.8, "seed": seed, **cue}]}, dur + 1,
               seed)[0]
    return p, C.Arranger(p, seed).build()


@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("theme", [None] + sorted(C.THEMES))
def test_any_theme_in_any_style_keeps_the_cadence_rules(style, theme):
    """the cue closes on the tonic chord with the melody on the tonic, approached from the dominant (bII in the
    phrygian family), the subdominant or the tonic; every event is playable"""
    p, events = _arrange(style, 14.0, **({"theme": theme} if theme else {}))
    last = p.bars[-1]
    assert last.chords[-1][2].root == p.key.tonic, T.chord_name(last.chords[-1][2])
    tail = [n.pitch for n in last.melody if n.pitch is not None]
    assert not tail or (tail[-1] - p.key.tonic) % 12 == 0
    if len(p.bars) >= 2 and p.key.harmony_mode != "lydian":
        pen = p.bars[-2].chords[-1][2]
        assert pen.root in (C._dominant(p.key).root, (p.key.tonic + 5) % 12, p.key.tonic), T.chord_name(pen)
    for e in events:
        assert e.dur > 0 and 0.0 <= e.vel <= 1.0 and e.stem in C.STEMS
        assert instruments.get(e.inst)


def test_swing_delays_the_offbeats():
    p, events = _arrange("jazz_swing")
    beat = 60.0 / p.tempo
    ride = [((e.t - p.start) / beat) % 1.0 for e in events if e.inst == "ride"]
    offbeats = [f for f in ride if 0.3 < f < 0.9]
    assert offbeats and abs(np.median(offbeats) - p.swing) < 0.06
    straight, _ = _arrange("playful")
    assert straight.swing == 0.5 and straight.time(0.5) == pytest.approx(straight.time(0.0) + 0.5 * 60 / straight.tempo,
                                                                         rel=0.05)


def test_japanese_style_stays_in_the_in_scale_and_cadences_from_bii():
    p, events = _arrange("japanese", 30.0)
    assert p.key.mode == "in"
    assert all(p.key.contains(e.pitch) for e in events if e.stem == "melody")
    final = p.bars[-1].chords[-1][2]
    assert final.root == p.key.tonic and final.third is None
    pen = p.bars[-2].chords[-1][2]
    assert pen.root in ((p.key.tonic + 1) % 12, (p.key.tonic + 5) % 12, p.key.tonic)


def test_jazz_family_cadences_with_sevenths():
    p, _ = _arrange("bossa_nova", 12.0)
    assert len(p.bars[-1].chords[-1][2].intervals) == 4
    p, _ = _arrange("tender", 12.0)
    assert len(p.bars[-1].chords[-1][2].intervals) == 3


def test_compound_meter_and_drum_articulations():
    p, events = _arrange("celtic")
    assert p.beats == 3.0 and p.compound
    p, events = _arrange("chiptune")
    assert {e.art for e in events if e.inst == "chip_noise"} >= {"kick", "hat", "normal"}


def test_plan_errors_are_clear():
    with pytest.raises(ValueError, match="Unknown music style"):
        C.plan({"cues": [{"start": 0, "end": 4, "style": "polka"}]}, 5)
    with pytest.raises(ValueError, match="unknown theme"):
        C.plan({"cues": [{"start": 0, "end": 4, "style": "tender", "theme": "nope"}]}, 5)
    with pytest.raises(ValueError, match="ends before it starts"):
        C.plan({"cues": [{"start": 4, "end": 2, "style": "tender"}]}, 5)
    p = C.plan({"cues": [{"start": 0, "end": 6, "style": "tender", "hits": [{"t": 2, "kind": "kaboom"}]}]}, 7)[0]
    with pytest.raises(ValueError, match="Unknown hit kind"):
        C.Arranger(p, 0).build()


def test_summary_and_catalog():
    plans = C.plan({"cues": [{"start": 0, "end": 10, "style": "lofi", "seed": 1}]}, 11)
    row = C.summary(plans)[0]
    assert len(row["chords"]) == len(row["downbeats"]) == row["bars"]
    rows = C.catalog()
    assert len(rows) == len(C.STYLES) >= 28
    assert all(r["description"] and r["lead"] for r in rows)
    assert next(r for r in rows if r["name"] == "heroic")["alias_of"] == "adventure"
