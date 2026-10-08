"""DSP building blocks the whole library leans on."""
import numpy as np
import pytest

from codecinema.audio import dsp


def test_place_clips_at_both_ends():
    buf = np.zeros((2, 10))
    dsp.place(buf, np.ones(4), -2)
    dsp.place(buf, np.ones((2, 4)) * 2.0, 8, gain=0.5)
    assert buf[0].tolist() == [1, 1, 0, 0, 0, 0, 0, 0, 1, 1]


def test_fades_reach_zero():
    y = dsp.fade(np.ones((2, 1000)), 0.005, 0.005)
    assert np.all(y[:, 0] == 0.0) and np.all(y[:, -1] == 0.0) and y[0, 500] == 1.0


def test_limiter_holds_its_true_peak_ceiling():
    r = dsp.rng("test-limiter")
    x = r.standard_normal((2, dsp.SR)) * 0.5
    y, _ = dsp.limiter(x, -1.0)
    assert dsp.true_peak_dbtp(y) <= -1.0 + 0.1


def test_loudness_anchor_of_a_reference_tone():
    """a 1 kHz full-scale sine reads about -3 LUFS on the K-weighted scale (mono, panned to the centre)"""
    t = dsp.t_axis(dsp.SR)
    assert dsp.loudness_peak(np.sin(2 * np.pi * 1000 * t)) == pytest.approx(-3.0, abs=0.7)


def test_band_limited_oscillators_do_not_alias():
    """PolyBLEP saw and pulse at A4: everything between the harmonics (DC aside) at least 40 dB down"""
    n = dsp.SR
    f = np.fft.rfftfreq(n, 1.0 / dsp.SR)
    harmonics = np.abs(f - 440.0 * np.round(f / 440.0)) < 20
    for wave in (dsp.osc_saw(440.0, n), dsp.osc_square(440.0, n, 0.0, 0.25)):
        spec = np.abs(np.fft.rfft(wave * np.blackman(n)))
        assert spec[~harmonics & (f > 20)].max() < spec[f > 20].max() * dsp.db2lin(-40.0)


def test_rng_is_deterministic_per_key():
    assert dsp.rng("a", 1).random() == dsp.rng("a", 1).random()
    assert dsp.rng("a", 1).random() != dsp.rng("a", 2).random()
