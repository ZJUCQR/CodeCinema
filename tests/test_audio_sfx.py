"""Sound effects: every catalog entry renders finite, bounded, zero-edged audio at the catalog level."""
import os
import traceback
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pytest

from codecinema.audio import dsp, sfx, soundfont

soundfont.use("off")  # synthesized instruments: the fallback every machine has, and deterministic

NAMES = sfx.names()


def _measure(name):
    """worker: render one sound (bank off) and measure it -> a small dict (or the error)"""
    try:
        from codecinema.audio import dsp, sfx, soundfont
        soundfont.use("off")
        y = sfx.render(name, seed=1)
        return {"ndim": y.ndim, "channels": y.shape[0] if y.ndim == 2 else 1, "n": y.shape[-1],
                "finite": bool(np.all(np.isfinite(y))), "peak": dsp.peak(y),
                "edges": float(np.max(np.abs(y[..., [0, -1]]))),
                "dc": float(np.max(np.abs(np.mean(dsp.as_stereo(y), axis=-1)))), "loudness": dsp.loudness_peak(y)}
    except Exception:  # noqa: BLE001 -- report the failure for this item alone
        return {"error": traceback.format_exc()}


@pytest.fixture(scope="module")
def measured():
    with ProcessPoolExecutor(max_workers=max(1, min(8, (os.cpu_count() or 2) - 1))) as pool:
        return dict(zip(NAMES, pool.map(_measure, NAMES, chunksize=4)))


@pytest.mark.parametrize("name", NAMES)
def test_every_sound_renders_clean(measured, name):
    s = measured[name]
    assert "error" not in s, s.get("error")
    entry = next(e for e in sfx.catalog() if e["name"] == name)
    assert s["ndim"] == (2 if entry["stereo"] else 1) and s["channels"] in (1, 2)
    assert s["finite"]
    assert 0.05 * dsp.SR <= s["n"] <= 15.0 * dsp.SR
    assert s["peak"] <= dsp.db2lin(-1.0) + 1e-9
    assert s["edges"] == 0.0
    assert s["dc"] < 2e-3
    # the loudest 100 ms sits at the anchor; very short clicks may stop below it at the peak ceiling
    assert -26.0 <= s["loudness"] <= sfx.REF_LU + 0.2


def test_catalog_entries_are_described():
    rows = sfx.catalog()
    assert len(rows) == len(NAMES) >= 160
    for row in rows:
        assert row["description"] and isinstance(row["params"], dict) and isinstance(row["stereo"], bool)


@pytest.mark.parametrize("name", ["dog_bark", "rain_on_roof", "applause", "teleport", "glass_break", "typing"])
def test_renders_are_deterministic_and_vary_with_the_seed(name):
    a, b, c = sfx.render(name, seed=4), sfx.render(name, seed=4), sfx.render(name, seed=5)
    assert np.array_equal(a, b)
    assert a.shape != c.shape or not np.array_equal(a, c)


def test_parameters_reach_the_generator():
    assert sfx.render("footsteps", seed=1, steps=8).shape[-1] > sfx.render("footsteps", seed=1, steps=2).shape[-1]
    assert sfx.render("car_pass", seed=3, speed=30.0).shape[-1] > sfx.render("car_pass", seed=3, speed=100.0).shape[-1]
    wood, mud = sfx.render("step_wood", seed=2), sfx.render("step_mud", seed=2)
    assert wood.shape == mud.shape and not np.allclose(wood, mud)


def test_errors_name_the_choices():
    with pytest.raises(KeyError, match="Known"):
        sfx.render("no_such_sound")
    with pytest.raises(ValueError, match="surface"):
        sfx.render("footsteps", surface="lava")


def test_doppler_pass_drops_in_pitch():
    """a tone carried past the listener: the received frequency falls by the Doppler ratio"""
    f0, v = 1000.0, 30.0
    y = dsp.mono(sfx._pass_by(lambda m: np.sin(2 * np.pi * f0 * np.arange(m) / dsp.SR), 4.0, v, 2.0, 3.0, absorb=False))
    k = dsp.n_of(0.25)

    def freq(seg):
        spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), 8 * len(seg)))
        return np.argmax(spec) * dsp.SR / (8 * len(seg))
    approach, recede = freq(y[dsp.n_of(0.3):dsp.n_of(0.3) + k]), freq(y[dsp.n_of(3.4):dsp.n_of(3.4) + k])
    assert approach == pytest.approx(f0 / (1 - v / sfx.C_AIR), rel=0.01)
    assert recede == pytest.approx(f0 / (1 + v / sfx.C_AIR), rel=0.01)
