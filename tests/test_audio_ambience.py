"""Ambience beds: exact length, -20 dBFS RMS, peaks under -3 dBFS, zero edges, deterministic."""
import os
import traceback
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pytest

from codecinema.audio import ambience, dsp, soundfont

soundfont.use("off")  # synthesized instruments: the fallback every machine has, and deterministic

NAMES = ambience.names()


def _measure(name):
    """worker: render a 4 s bed (bank off) and measure it -> a small dict (or the error)"""
    try:
        from codecinema.audio import ambience, dsp, soundfont
        soundfont.use("off")
        y = ambience.bed(name, 4.0, seed=1)
        return {"shape": y.shape, "finite": bool(np.all(np.isfinite(y))), "rms_db": float(dsp.lin2db(dsp.rms(y))),
                "peak": dsp.peak(y), "edges": float(np.max(np.abs(y[:, [0, -1]]))),
                "dc": float(np.max(np.abs(np.mean(y, axis=-1))))}
    except Exception:  # noqa: BLE001 -- report the failure for this item alone
        return {"error": traceback.format_exc()}


@pytest.fixture(scope="module")
def measured():
    with ProcessPoolExecutor(max_workers=max(1, min(8, (os.cpu_count() or 2) - 1))) as pool:
        return dict(zip(NAMES, pool.map(_measure, NAMES)))


@pytest.mark.parametrize("name", NAMES)
def test_every_bed_renders_clean(measured, name):
    s = measured[name]
    assert "error" not in s, s.get("error")
    assert s["shape"] == (2, dsp.n_of(4.0))
    assert s["finite"]
    assert s["rms_db"] == pytest.approx(ambience.REF_DB, abs=1.0)
    assert s["peak"] <= dsp.db2lin(-3.0) + 1e-6
    assert s["edges"] == 0.0
    assert s["dc"] < 2e-3


def test_catalog_and_errors():
    rows = ambience.catalog()
    assert len(rows) == len(NAMES) >= 30
    assert all(row["description"] for row in rows)
    with pytest.raises(KeyError, match="Known"):
        ambience.bed("no_such_bed", 1.0)


def test_beds_are_deterministic_and_vary_with_the_seed():
    a, b, c = (ambience.bed("harbor", 3.0, seed=s) for s in (7, 7, 8))
    assert np.array_equal(a, b) and not np.array_equal(a, c)


@pytest.mark.parametrize("intensity", [0.3, 1.6])
def test_intensity_scales_the_level(intensity):
    y = ambience.bed("city_street", 3.0, seed=2, intensity=intensity)
    expected = ambience.REF_DB + dsp.lin2db(0.6 + 0.4 * min(1.0, intensity))
    assert dsp.lin2db(dsp.rms(y)) == pytest.approx(expected, abs=1.0)
    assert dsp.peak(y) <= dsp.db2lin(-3.0) + 1e-6


def test_long_beds_do_not_loop():
    """two halves of a long bed are not copies of each other"""
    y = ambience.bed("river", 12.0, seed=3)[0]
    half = len(y) // 2
    assert abs(np.corrcoef(y[:half], y[half:2 * half])[0, 1]) < 0.2
