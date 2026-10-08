"""The mixer: a short scene with every bus is mastered to its loudness target under the true-peak ceiling."""
import json

import numpy as np
import pytest

from codecinema.audio import dsp, mixer, sfx, soundfont

soundfont.use("off")  # synthesized instruments: the fallback every machine has, and deterministic


def test_short_mix_hits_its_targets(tmp_path):
    audio = {
        "duration": 10.0, "seed": 3,
        "music": {"cues": [{"start": 0.0, "end": 9.5, "style": "bossa_nova", "intensity": 0.6}]},
        "babble": [{"t": 1.0, "profile": "girl", "text": "Look, the rain has stopped!", "mood": "happy"}],
        "vocals": [{"t": 4.5, "profile": "puppy", "kind": "yip"}],
        "sfx": [{"t": 2.5, "name": "door_open", "pan": -0.3}, {"t": 6.0, "name": "car_pass", "distance": 12.0}],
        "foley": [{"t": 3.0 + 0.5 * k, "kind": "step", "surface": "gravel", "weight": 0.6} for k in range(4)],
        "ambience": [{"start": 0.0, "end": 10.0, "bed": "city_street", "gain_db": -20.0}],
        "spaces": [{"start": 0.0, "end": 10.0, "space": "outdoor"}],
        "master": {"target_lufs": -16.0, "true_peak_db": -1.0, "bits": 16},
    }
    report = mixer.mix(audio, tmp_path)
    assert report["lufs"] == pytest.approx(-16.0, abs=1.0)
    assert report["true_peak_dbtp"] <= -0.7
    assert report["counts"]["sfx"] == 2 and report["counts"]["foley"] == 4
    assert report["music"][0]["style"] == "bossa_nova" and report["music"][0]["chords"]
    x = mixer.read_wav(tmp_path / "mix.wav")
    assert len(x) == dsp.n_of(10.0) and np.all(np.isfinite(x))
    for bus in mixer.BUSES:
        assert (tmp_path / "stems" / f"{bus}.wav").is_file()
        assert report["buses"][bus]["peak_db"] < 0.0
    assert json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))["lufs"] == report["lufs"]


def test_new_surfaces_reach_the_foley():
    for surface in ("carpet", "metal", "tile", "gravel", "leaves", "mud", "marble", "rug"):
        y = mixer._foley(sfx, {"kind": "step", "surface": surface}, 1)
        assert np.all(np.isfinite(y)) and dsp.peak(y) > 0
