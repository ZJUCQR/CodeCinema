"""Music notation: pitches, durations, melodies, keys and modes, chord symbols, roman numerals, voicing."""
import pytest

from codecinema.audio import theory as T


def test_pitch_names_round_trip():
    for midi in range(128):
        assert T.parse_pitch(T.pitch_name(midi)) == midi
    assert T.parse_pitch("C4") == 60 and T.parse_pitch("F#5") == 78 and T.parse_pitch("Bb3") == 58
    assert T.parse_pitch("Cbb4") == 58 and T.parse_pitch("Ex4") == 66 and T.parse_pitch("B♭2") == 46


@pytest.mark.parametrize("bad", ["H4", "C", "4C", "C#", "Cq4", ""])
def test_bad_pitches_raise(bad):
    with pytest.raises(ValueError):
        T.parse_pitch(bad)


@pytest.mark.parametrize("text, beats", [("w", 4.0), ("h", 2.0), ("q", 1.0), ("e", 0.5), ("s", 0.25), ("t", 0.125),
                                         ("q.", 1.5), ("e..", 0.875), ("e3", 1 / 3), ("1.5", 1.5)])
def test_durations(text, beats):
    assert T.parse_duration(text) == pytest.approx(beats)


@pytest.mark.parametrize("bad", ["x", "q...", "qq", "e4"])
def test_bad_durations_raise(bad):
    with pytest.raises(ValueError):
        T.parse_duration(bad)


def test_melody_ties_slides_marks_and_rests():
    notes = T.parse_melody("C4/q D4/e' ~D4/e ~F4/q r/q G4^", 4)
    assert [(n.beat, n.dur, n.pitch) for n in notes] == [(0.0, 1.0, 60), (1.0, 1.0, 62), (2.0, 1.0, 65), (3.0, 1.0,
                                                                                                          None),
                                                         (4.0, 1.0, 67)]
    assert notes[1].art == "staccato" and notes[2].slide and notes[4].art == "marcato"


def test_pickup_bar_is_right_aligned():
    notes = T.parse_melody("G4/e A4/e | B4/h C5/h", 4)
    assert notes[0].beat == pytest.approx(3.0) and notes[2].beat == pytest.approx(4.0)


def test_bar_length_errors_name_the_bar():
    with pytest.raises(ValueError, match="bar 2 lasts 3 beats"):
        T.parse_melody("C4/w | D4/h E4/q | F4/w | G4/w", 4)


def test_meters():
    assert T.meter_beats(4) == (4.0, False)
    assert T.meter_beats("6/8") == (3.0, True)
    assert T.meter_beats("2/4") == (2.0, False)
    assert T.meter_beats("12/8") == (6.0, True)


@pytest.mark.parametrize("symbol, pcs", [("C", [0, 4, 7]), ("Cm7", [0, 3, 7, 10]), ("Fmaj7", [5, 9, 0, 4]),
                                         ("G7sus4", [7, 0, 2, 5]), ("Bdim7", [11, 2, 5, 8]), ("Ebaug", [3, 7, 11]),
                                         ("D5", [2, 9]), ("A/C#", [9, 1, 4]), ("Bbm9", [10, 1, 5, 8, 0])])
def test_chord_symbols(symbol, pcs):
    c = T.parse_chord(symbol)
    assert c.pcs == pcs
    assert T.parse_chord(T.chord_name(c)).pcs == pcs


def test_roman_numerals_follow_the_mode():
    major, minor = T.Key(0, "major"), T.Key(9, "minor")
    assert T.chord_name(T.parse_chord("ii7", major)) == "Dm7"
    assert T.chord_name(T.parse_chord("I7", major)) == "Cmaj7"
    assert T.chord_name(T.parse_chord("V7", major)) == "G7"
    assert T.chord_name(T.parse_chord("V/vi", major)) == "E"
    assert T.chord_name(T.parse_chord("bVI", minor)) == "E"         # b lowers the degree of the minor scale
    assert T.chord_name(T.parse_chord("iiø", minor)) == "Bm7b5"
    assert T.chord_name(T.parse_chord("IV/5", major)) == "F/G"


@pytest.mark.parametrize("bad", ["Hm", "Cblah", "", "%"])
def test_bad_chords_raise(bad):
    with pytest.raises(ValueError):
        T.parse_chord(bad, T.Key(0))


def test_chord_charts_hold_and_repeat():
    bars = T.parse_chords("C G | % | Am . F |", T.Key(0), 4)
    assert len(bars) == 3
    assert [(o, d) for o, d, _ in bars[0]] == [(0.0, 2.0), (2.0, 2.0)]
    assert bars[1][0][2].root == 7
    assert [(o, d, T.chord_name(c)) for o, d, c in bars[2]] == [(0.0, 8 / 3, "Am"), (8 / 3, 4 / 3, "F")]
    with pytest.raises(ValueError, match="nothing to repeat"):
        T.parse_chords("% | C", T.Key(0))


def test_keys_and_modes():
    assert T.parse_key("F#m") == T.Key(6, "minor")
    assert T.parse_key("Bb", "dorian") == T.Key(10, "dorian")
    with pytest.raises(ValueError):
        T.parse_key("Q")
    k = T.Key(4, "in")
    assert k.pcs() == [4, 5, 9, 11, 0] and k.harmony_mode == "phrygian" and k.minorish
    assert T.Key(4, "miyako_bushi").pcs() == k.pcs()
    assert T.Key(9, "hirajoshi").pcs() == [9, 11, 0, 4, 5]
    assert k.step(64, 1) == 65 and k.step(64, -1) == 60 and k.snap(66) in (65, 69)
    for mode, scale in T.MODES.items():
        assert scale[0] == 0 and list(scale) == sorted(scale), mode
        assert T.Key(0, mode).harmony_mode in T.MODES


def test_voicing_keeps_the_chord_under_a_ceiling():
    c = T.parse_chord("G7")
    v = T.voicing(c, 4, 48, 72)
    assert v == sorted(v) and all(48 <= m <= 72 for m in v)
    assert {m % 12 for m in v} >= {7, 11, 5}
    low = T.voicing(c, 4, 48, 72, top=60)
    assert max(low) <= max(v)
    assert T.bass_note(T.parse_chord("C/E"), 28, 48) % 12 == 4


def test_theme_parsing_splits_long_notes_over_bars():
    th = T.parse_theme({"key": "D", "mode": "major", "tempo": 90, "meter": "3/4",
                        "melody": "D5/h. | ~D5/q E5/q F#5/q", "chords": "D | A"})
    assert th.length == 2 and th.beats == 3.0
    assert th.bars[1]["melody"][0].art == "tie"
