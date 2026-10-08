"""Cartoon voices: every profile speaks, every vocalization renders, timing follows the plan exactly."""
import itertools
import os
import traceback
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pytest

from codecinema.audio import babble, dsp

LINES = ("Hello there, my little friend! Shall we go and see the sea?", "奶奶说，年兽其实很温柔，对吧？")
PROFILES = list(babble.PROFILES)
VOCALS = list(babble.VOCALIZATIONS)


def _problems(y):
    """what is wrong with a voice clip (empty when clean): bounds, edges, DC, the -14 LU anchor"""
    bad = []
    if y.ndim != 1 or not np.all(np.isfinite(y)):
        bad.append("not a finite mono clip")
    if dsp.peak(y) > dsp.db2lin(-1.0) + 1e-9:
        bad.append(f"peak {dsp.peak(y):.3f}")
    if y[0] != 0.0 or y[-1] != 0.0:
        bad.append("edges not at zero")
    if abs(float(np.mean(y))) >= 2e-3:
        bad.append("DC offset")
    # anchored at -14 LU; a line with sharp consonants may stop a little lower at the -1 dBFS ceiling
    if not -18.0 <= dsp.loudness_peak(y) <= -13.8:
        bad.append(f"loudness {dsp.loudness_peak(y):.1f}")
    return bad


def _speak(profile):
    """worker: both lines in one profile -> problems and timing checks (or the error)"""
    try:
        from codecinema.audio import babble, dsp
        out = []
        for line, mood in zip(LINES, ("happy", "tender")):
            plan = babble.plan(line, profile, mood, seed=2)
            y = babble.render(line, profile, mood, seed=2)
            rows = plan["syllables"]
            out.append({"problems": _problems(y), "length_ok": y.shape[0] == dsp.n_of(plan["duration"]),
                        "ordered": bool(rows) and all(a["t1"] <= b["t0"] + 1e-9 for a, b in itertools.pairwise(rows))})
        return out
    except Exception:  # noqa: BLE001 -- report the failure for this item alone
        return {"error": traceback.format_exc()}


def _vocal(kind):
    """worker: one vocalization in five kinds of voice -> problems per profile (or the error)"""
    try:
        from codecinema.audio import babble, dsp
        out = {}
        for profile in ("girl", "man", "monster", "alien", "puppy"):
            y = babble.vocalize(kind, profile, seed=1)
            bad = _problems(y) + ([] if 0.1 * dsp.SR <= len(y) <= 6.0 * dsp.SR else [f"length {len(y)}"])
            if bad:
                out[profile] = bad
        return out
    except Exception:  # noqa: BLE001 -- report the failure for this item alone
        return {"error": traceback.format_exc()}


@pytest.fixture(scope="module")
def results():
    with ProcessPoolExecutor(max_workers=max(1, min(8, (os.cpu_count() or 2) - 1))) as pool:
        spoken = dict(zip(PROFILES, pool.map(_speak, PROFILES)))
        vocals = dict(zip(VOCALS, pool.map(_vocal, VOCALS, chunksize=2)))
    return spoken, vocals


@pytest.mark.parametrize("profile", PROFILES)
def test_every_profile_speaks_on_the_plan_clock(results, profile):
    s = results[0][profile]
    assert "error" not in s, s
    for line in s:
        assert not line["problems"], line["problems"]
        assert line["length_ok"] and line["ordered"]


@pytest.mark.parametrize("kind", VOCALS)
def test_every_vocalization_renders(results, kind):
    s = results[1][kind]
    assert not s, s


def test_moods_change_the_delivery():
    calm = babble.plan("We should go home now.", "woman", "sleepy", 1)
    quick = babble.plan("We should go home now.", "woman", "excited", 1)
    assert quick["duration"] < calm["duration"]
    assert np.mean([r["f0"] for r in quick["syllables"]]) > np.mean([r["f0"] for r in calm["syllables"]])


def test_determinism_and_errors():
    assert np.array_equal(babble.vocalize("hum", "girl", 3), babble.vocalize("hum", "girl", 3))
    assert not np.array_equal(babble.vocalize("hum", "girl", 3), babble.vocalize("hum", "girl", 4))
    with pytest.raises(KeyError, match="Known"):
        babble.vocalize("yodel", "girl")
    with pytest.raises(KeyError):
        babble.render("hi", "dragon")


def test_catalog():
    rows = babble.catalog()
    profiles = [r for r in rows if r["kind"] == "profile"]
    vocals = [r for r in rows if r["kind"] == "vocalization"]
    assert len(profiles) == len(PROFILES) >= 20 and len(vocals) == len(VOCALS) >= 39
    assert all(r["description"] for r in rows)
