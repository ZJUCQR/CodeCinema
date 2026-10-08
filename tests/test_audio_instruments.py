"""Instruments, synthesized (sound bank off): every note renders clean at the matched level."""
import os
import traceback
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pytest

from codecinema.audio import dsp, instruments, soundfont

soundfont.use("off")  # synthesized instruments: the fallback every machine has, and deterministic

NAMES = instruments.names()


def _problems(y):
    """what is wrong with a note (empty when it is clean)"""
    bad = []
    if y.ndim != 2 or y.shape[0] != 2:
        bad.append(f"shape {y.shape}")
    if not np.all(np.isfinite(y)):
        bad.append("not finite")
    if dsp.peak(y) >= 1.0:
        bad.append(f"peak {dsp.peak(y):.3f}")
    if np.any(y[:, 0] != 0.0) or np.any(y[:, -1] != 0.0):
        bad.append("edges not at zero")
    if y.shape[-1] > 20 * dsp.SR:
        bad.append("too long")
    return bad


def _measure(name):
    """worker: a reference note, every instrument-specific articulation and both ends of the range (bank off)"""
    try:
        from codecinema.audio import instruments, soundfont
        soundfont.use("off")
        inst = instruments.get(name)
        pitch = inst.ref or (inst.lo + inst.hi) // 2
        y = instruments.play(name, pitch, 1.0, 0.8, seed=0)
        out = {"source": instruments.source(name), "level": instruments._short_term_db(y), "problems": {}}
        notes = {"reference": y}
        for art in inst.arts:
            notes[art] = instruments.play(name, pitch, 0.4, 0.7, art, seed=1)
        if inst.pitched:
            notes["lowest"] = instruments.play(name, inst.lo, 0.3, 0.6, seed=2)
            notes["highest"] = instruments.play(name, inst.hi, 0.3, 0.6, seed=2)
        for label, note in notes.items():
            if _problems(note):
                out["problems"][label] = _problems(note)
        return out
    except Exception:  # noqa: BLE001 -- report the failure for this item alone
        return {"error": traceback.format_exc()}


@pytest.fixture(scope="module")
def measured():
    with ProcessPoolExecutor(max_workers=max(1, min(8, (os.cpu_count() or 2) - 1))) as pool:
        return dict(zip(NAMES, pool.map(_measure, NAMES, chunksize=2)))


@pytest.mark.parametrize("name", NAMES)
def test_every_instrument_plays_clean_and_matched(measured, name):
    s = measured[name]
    assert "error" not in s, s.get("error")
    assert s["source"] == "synthesized"
    assert not s["problems"], s["problems"]
    # loudness matching: the loudest 50 ms of a reference note sits at REF_DB (plus the instrument's trim)
    trim = instruments.get(name).trim_db
    assert trim + instruments.REF_DB - 6.0 <= s["level"] <= trim + instruments.REF_DB + 3.0


def test_velocity_law_and_determinism():
    soft = instruments.play("electric_piano", 60, 0.5, 0.4, seed=3)
    loud = instruments.play("electric_piano", 60, 0.5, 0.8, seed=3)
    assert dsp.rms(loud) > dsp.rms(soft) * 2.5
    assert np.array_equal(loud, instruments.play("electric_piano", 60, 0.5, 0.8, seed=3))


def test_chip_voices_differ_by_duty_and_carry_no_dc():
    a = instruments.play("chip_square", 72, 0.3, 0.8, "duty12", seed=0)
    b = instruments.play("chip_square", 72, 0.3, 0.8, "duty50", seed=0)
    assert a.shape == b.shape and not np.allclose(a, b)
    assert abs(float(np.mean(a))) < 1e-3 * dsp.peak(a)


def test_catalog():
    rows = instruments.catalog()
    assert len(rows) == len(NAMES) >= 110
    for row in rows:
        assert row["description"] and row["family"] and row["source"] in ("sampled", "synthesized")
        assert row["range"] is None or row["range"][0] < row["range"][1]
    with pytest.raises(KeyError, match="Known"):
        instruments.get("no_such_instrument")
    assert instruments.get("double_bass").name == "contrabass"
