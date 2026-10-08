"""
codecinema.audio.composer -- music written as data: themes, styles and cues placed on a film timeline.

    render_score(music, duration, seed=0) -> {"melody", "harmony", "bass", "percussion", "fx": (2, n)} at dsp.SR
    plan(music, duration, seed=0)         -> [{cue summary: style, key, tempo, bars, statements ...}]
    music = {"themes": {name: theme}, "cues": [cue, ...]}

A theme is {"key", "mode", "tempo", "meter", "melody", "chords"} in the notation of codecinema.audio.theory.
A cue is {"start", "end", "style", and optionally "theme", "key", "mode", "tempo", "intensity" 0..1,
"variation" (light | full | sparse | minor | half_time | double_time, combinable with '+'), "end_with" (button |
ring | fade | cut), "fade_in" s, "hits": [{"t", "kind": stinger | crash | swell | pluck_rise | fall | sparkle}],
"lift" (semitones: the last statement modulates up), "modulate" (true: end on the dominant of the next cue's key),
"lead" (instrument name or list, replacing the style's melody instruments), "fade_out" (s, with end_with fade),
"reverb" (wet amount), "seed"}.  Without a theme the cue composes its own: a period of two four-bar phrases (motif, repetition, contour,
half and authentic cadences) over a progression drawn from the mode.  The tempo is nudged (at most about 6 %) so
whole bars land on the cue end; the plan intros, repeats and varies the theme (instrument, octave, countermelody,
density) and always ends on a cadence.  A style is an arrangement recipe: lead / doubling / countermelody
instruments, accompaniment and bass patterns, percussion grids, dynamics, humanisation and reverb.
"""
import math
from dataclasses import dataclass, field

import numpy as np

from codecinema.audio import dsp, instruments, theory as T
from codecinema.audio.dsp import SR, n_of

STEMS = ("melody", "harmony", "bass", "percussion", "fx")
BUTTON_LEAD = 0.12              # the button chord lands this long before the cue end
TAIL_S = 3.5                    # ring / reverb tail rendered past a cue end
SCORE_LUFS = -20.0              # integrated loudness of the whole score before the mix

# ------------------------------------------------------------------------------------------------ demo themes
THEMES = {
    "lullaby_of_stars": {
        "key": "F", "mode": "major", "tempo": 72, "meter": 3,
        "melody": "A4/q. G4/e F4/q | D5/h C5/q | A4/q. G4/e F4/q | G4/h. | A4/q. G4/e F4/q | D5/q F5/q D5/q | "
                  "C5/q. A4/e G4/q | F4/h. | A4/q D5/q E5/q | F5/h D5/q | Bb4/q. C5/e D5/q | C5/h. | "
                  "A4/q. G4/e F4/q | D5/q F5/q D5/q | C5/q A4/q G4/q | F4/h.",
        "chords": "F | Bb | F/C | C7 | F | Bb | F/C C7 | F | Dm | Bb | Gm7 | C7 | F | Bb | F/C C7 | F",
    },
    "little_adventure": {
        "key": "G", "mode": "major", "tempo": 116, "meter": 4,
        "melody": "G4/q. D4/e G4/e A4/e B4/q | E5/q. D5/e C5/q E5/q | D5/q B4/e G4/e B4/q D5/q | A4/q. B4/e A4/h | "
                  "G4/q. D4/e G4/e A4/e B4/q | E5/q. D5/e C5/q G5/q | F#5/q. E5/e D5/q C5/q | B4/q A4/q G4/h",
        "chords": "G | C | G/B | D | G | C | D7 | G",
    },
    "spring_festival": {
        "key": "D", "mode": "gong", "tempo": 132, "meter": "2/4",
        "melody": "A5/s B5/s A5/e F#5/e A5/e | D6/e. E6/s D6/e B5/e | A5/e B5/e A5/s F#5/s E5/e | E5/q. F#5/e | "
                  "A5/s B5/s A5/e F#5/e A5/e | D6/e. E6/s D6/e B5/e | B5/e A5/e E5/e F#5/e | D5/q. r/e | "
                  "B5/e. A5/s B5/e D6/e | A5/e F#5/e E5/e F#5/e | E5/s F#5/s E5/e B4/e E5/e | A4/e. B4/s A4/q | "
                  "D5/e E5/e F#5/e A5/e | B5/e. A5/s B5/e D6/e | E6/e. D6/s B5/e A5/e | D6/q. r/e",
        "chords": "D | D | Bm | A | D | D | A | D | G | D | Em | A | D | Bm | A | D",
    },
}

# preferred median pitch of a melody on each lead instrument
LEAD_CENTER = {"flute": 79, "piccolo": 88, "violin": 76, "clarinet": 70, "oboe": 74, "english_horn": 67, "piano": 74,
               "glockenspiel": 86, "celesta": 84, "music_box": 84, "whistle": 81, "trumpet": 72, "muted_trumpet": 72,
               "french_horn": 65, "brass_section": 70, "cello": 57, "viola": 64, "erhu": 72, "dizi": 84, "suona": 76,
               "guzheng": 72, "pizzicato_strings": 74, "xylophone": 84, "voice_oohs": 70, "choir_aahs": 70,
               "vibraphone": 74, "marimba": 74, "pipa": 72, "yangqin": 76, "strings": 76, "bassoon": 53, "harmonica": 74,
               "accordion": 72, "ocarina": 79, "recorder": 77, "kalimba": 78, "ukulele": 72, "steel_drums": 74,
               "trombone": 58, "tuba": 43, "harp": 74, "nylon_guitar": 66, "tin_whistle": 84, "sheng": 72,
               "warm_pad": 70, "slow_strings": 76, "tremolo_strings": 76, "tubular_bells": 72}

# ------------------------------------------------------------------------------------------------ percussion grids
# one bar per string, 4 steps per quarter note: X accent, x normal, o soft, . rest
GRIDS = {
    "shaker8": {4: "x.o.x.o.x.o.x.o.", 3: "x.o.x.o.x.o.", 2: "x.o.x.o.", "c": "x.oo.ox.oo.o"},
    "shaker16": {4: "xooox0ooxooox0oo".replace("0", "o"), 3: "xoooxoooxooo", 2: "xoooxooo", "c": "xooxooxooxoo"},
    "backbeat_clap": {4: "....X.......X...", 3: "....x...x...", 2: "....X...", "c": "......X....."},
    "tamb_backbeat": {4: "....x.......x...", 3: "....o...o...", 2: "....x...", "c": "......x....."},
    "kick_soft": {4: "x.......o.......", 3: "x...........", 2: "x.......", "c": "x.....o....."},
    "kick_drive": {4: "X.....x.x.......", 3: "X.......x...", 2: "X.....x.", "c": "X.....x....."},
    "woodblock_play": {4: "..x...o...x.o...", 3: "..x...x.....", 2: "..x...o.", "c": "..x.....x..."},
    "woodblock_tick": {4: "o.......o.......", 3: "o...........", 2: "o.......", "c": "o.....o....."},
    "hat8": {4: "x.o.x.o.x.o.x.o.", 3: "x.o.x.o.x.o.", 2: "x.o.x.o.", "c": "x.ox.ox.ox.o"},
    "snare_march": {4: "X..xX.x.X..xX.xx", 3: "X..xx.x.x.xx", 2: "X..xx.x.", "c": "X.xx.xX.xx.x"},
    "snare_train": {4: "XoxoXoxoXoxoXoxo", 3: "XoxoXoxoXoxo", 2: "XoxoXoxo", "c": "XooxooXooxoo"},
    "snare_back": {4: "....X.......X...", 3: "........x...", 2: "....X...", "c": "......X....."},
    "toms_adv": {4: "X..x..x...x.x...", 3: "X..x..x.x...", 2: "X..x..x.", "c": "X..x..X..x.."},
    "taiko_pulse": {4: "X.......x.x.....", 3: "X.....x.....", 2: "X.....x.", "c": "X.....x.x..."},
    "taiko_heart": {4: "X..x............", 3: "X..x........", 2: "X..x....", "c": "X..x........"},
    "bass_drum_1": {4: "X...............", 3: "X...........", 2: "X.......", "c": "X..........."},
    "bass_drum_13": {4: "X.......x.......", 3: "X...........", 2: "X.......", "c": "X.....x....."},
    "timp_13": {4: "X.......x.......", 3: "X.......x...", 2: "X...x...", "c": "X.....x....."},
    "triangle_1": {4: "x...............", 3: "x...........", 2: "x.......", "c": "x..........."},
    # luogu: gong-and-drum grids in 2/4 (repeated for longer bars)
    "tanggu": {2: "X.x.xxx.", 4: "X.x.xxx.X.x.x.xx", 3: "X.x.xxx.x.x.", "c": "X.xx.xX.xx.x"},
    "daluo": {2: "X.......", 4: "X.......x.......", 3: "X...........", "c": "X..........."},
    "bo": {2: "X.x.X.x.", 4: "X.x.X.x.X.x.X.x.", 3: "X.x.X.x.X.x.", "c": "X..x..X..x.."},
    "xiaoluo": {2: "..x...x.", 4: "..x...x...x...x.", 3: "..x...x...x.", "c": "...x.....x.."},
    "bangzi": {2: "x.x.x.x.", 4: "x.x.x.x.x.x.x.x.", 3: "x.x.x.x.x.x.", "c": "x..x..x..x.."},
    "muyu_tick": {2: "x...x...", 4: "x...x...x...x...", 3: "x...x...x...", "c": "x.....x....."},
}
FILLS = {
    "snare": {4: "........xxxxXXXX", 3: "....xxxxXXXX", 2: "xxxxXXXX", "c": "......xxxXXX"},
    "toms": {4: "........X.x.x.xx", 3: "....X.x.x.xx", 2: "X.x.x.xx", "c": "......X.x.xx"},
    "tanggu": {2: "XxXxX.X.", 4: "X.x.xxx.XxXxX.X.", 3: "X.x.XxXxX.X.", "c": "X.x.xxXxXxX."},
    "woodblock": {4: "............x.x.", 3: "........x.x.", 2: "....x.x.", "c": "........x.x."},
}

# ------------------------------------------------------------------------------------------------ styles
# lead: [(instrument, octave shift, articulation)] rotated per statement; double: (instrument, octaves, min intensity)
# counter: (instrument, mode guide|fill|heterophony, (lo, hi), dB, min intensity, first statement)
# comp: [(instrument, pattern, (lo, hi), dB, min intensity)]; pad: [(instrument, (lo, hi), dB, min intensity)]
# bass: (instrument, pattern, (lo, hi), dB); drums: [(instrument, grid, dB, min intensity, articulation)]
STYLES = {
    "playful": dict(
        tempo=116, meter=4, mode="major", key="G", end_with="button",
        lead=[("pizzicato_strings", 0, "auto"), ("clarinet", 0, "auto"), ("whistle", 0, "auto"), ("marimba", 0, "auto")],
        double=("glockenspiel", 1, 0.62),
        double_db=-10.0,
        counter=("bassoon", "fill", (43, 62), -5.0, 0.35, 1),
        comp=[("ukulele", "strum", (60, 72), -7.0, 0.0), ("marimba", "ostinato", (60, 79), -11.0, 0.55)],
        pad=[("strings", (55, 72), -16.0, 0.85)],
        bass=("acoustic_bass", "oompah", (36, 52), -3.0),
        drums=[("shaker", "shaker8", -20.0, 0.25, None), ("clap", "backbeat_clap", -18.0, 0.6, None),
               ("woodblock", "woodblock_play", -17.0, 0.4, None), ("kick", "kick_soft", -14.0, 0.75, None)],
        fill="woodblock", crash=None, reverb=("hall", 0.13), vel=(0.55, 0.88), human=(0.007, 0.06),
        legato=0.9, rubato=0.0, rit=0.03, intro=1, staccato_short=True,
        gen=dict(cells="bouncy", center=7, span=(-5, 12), leap=0.35)),
    "adventure": dict(
        tempo=126, meter=4, mode="major", key="D", end_with="button",
        lead=[("french_horn", 0, "legato"), ("trumpet", 0, "auto"), ("strings", 1, "legato")],
        double=("strings", 1, 0.55),
        counter=("cello", "guide", (48, 66), -6.0, 0.45, 1),
        comp=[("strings", "pulse8", (55, 72), -9.0, 0.0), ("brass_section", "stabs", (55, 72), -8.0, 0.68)],
        pad=[("slow_strings", (48, 67), -14.0, 0.35)],
        bass=("contrabass", "drive8", (28, 47), -4.0),
        drums=[("tom_low", "toms_adv", -11.0, 0.3, None), ("snare", "snare_march", -16.0, 0.6, None),
               ("bass_drum", "bass_drum_13", -11.0, 0.45, None), ("timpani", "timp_13", -11.0, 0.55, "tonic")],
        fill="toms", crash="cymbals", reverb=("hall", 0.2), vel=(0.6, 0.95), human=(0.006, 0.05),
        legato=1.0, rubato=0.0, rit=0.04, intro=1,
        gen=dict(cells="heroic", center=7, span=(-5, 12), leap=0.4)),
    "tender": dict(
        tempo=72, meter=4, mode="major", key="F", end_with="ring",
        lead=[("piano", 0, "normal"), ("flute", 0, "legato"), ("violin", 0, "legato"), ("oboe", 0, "legato")],
        double=None,
        counter=("cello", "guide", (45, 62), -6.0, 0.3, 1),
        comp=[("piano", "broken", (41, 67), -7.0, 0.0)],
        pad=[("strings", (52, 72), -12.0, 0.3)],
        bass=("contrabass", "root_whole", (31, 48), -11.0),
        bass_min=0.5,
        drums=[],
        fill=None, crash=None, reverb=("hall", 0.3), vel=(0.4, 0.75), human=(0.012, 0.05),
        legato=1.02, rubato=0.05, rit=0.12, intro=1,
        gen=dict(cells="lyric", center=5, span=(-5, 12), leap=0.3)),
    "wonder": dict(
        tempo=84, meter=4, mode="lydian", key="C", end_with="ring",
        lead=[("celesta", 0, "normal"), ("flute", 0, "legato"), ("voice_oohs", 0, "legato"), ("violin", 0, "legato")],
        double=("glockenspiel", 1, 0.6),
        counter=("french_horn", "guide", (50, 65), -7.0, 0.5, 1),
        comp=[("harp", "arp16", (48, 84), -7.0, 0.0)],
        pad=[("strings", (55, 76), -11.0, 0.0), ("voice_oohs", (57, 76), -13.0, 0.45)],
        bass=("contrabass", "root_whole", (31, 48), -10.0),
        drums=[("triangle", "triangle_1", -17.0, 0.35, "phrase")],
        fill=None, crash="cymbal_swell", reverb=("hall", 0.38), vel=(0.45, 0.85), human=(0.01, 0.05),
        legato=1.02, rubato=0.03, rit=0.1, intro=1, gliss="harp", sparkle=True,
        gen=dict(cells="lyric", center=7, span=(-3, 12), leap=0.35)),
    "mystery": dict(
        tempo=76, meter=4, mode="minor", key="D", end_with="ring",
        lead=[("clarinet", -1, "legato"), ("flute", -1, "legato"), ("oboe", 0, "legato"), ("vibraphone", 0, "normal")],
        double=None,
        counter=("bassoon", "fill", (40, 58), -7.0, 0.45, 0),
        comp=[("pizzicato_strings", "tiptoe", (50, 67), -8.0, 0.0), ("celesta", "twinkle", (74, 91), -16.0, 0.5)],
        pad=[("tremolo_strings", (50, 69), -18.0, 0.4)],
        bass=("acoustic_bass", "tiptoe_bass", (31, 50), -6.0),
        drums=[("woodblock", "woodblock_tick", -19.0, 0.3, None)],
        fill=None, crash="cymbal_swell", reverb=("hall", 0.24), vel=(0.4, 0.7), human=(0.01, 0.05),
        legato=0.95, rubato=0.02, rit=0.06, intro=1,
        gen=dict(cells="sneaky", center=5, span=(-7, 9), leap=0.3, chromatic=0.15)),
    "tension": dict(
        tempo=104, meter=4, mode="minor", key="C", end_with="cut",
        lead=[("french_horn", -1, "legato"), ("cello", 0, "legato"), ("trombone", 0, "legato")],
        double=None,
        counter=None,
        comp=[("strings", "pulse8", (48, 67), -7.0, 0.0), ("tremolo_strings", "pad_high", (67, 84), -16.0, 0.5)],
        pad=[("slow_strings", (45, 64), -13.0, 0.3)],
        bass=("contrabass", "pedal8", (28, 43), -4.0),
        drums=[("taiko", "taiko_heart", -10.0, 0.25, None), ("timpani", "bass_drum_1", -12.0, 0.5, "tonic"),
               ("tom_low", "toms_adv", -16.0, 0.75, None)],
        fill="toms", crash="cymbal_swell", reverb=("hall", 0.2), vel=(0.5, 0.95), human=(0.005, 0.04),
        legato=1.0, rubato=0.0, rit=0.0, intro=2,
        progressions="tension",
        gen=dict(cells="sparse_motif", center=3, span=(-5, 8), leap=0.25)),
    "sad": dict(
        tempo=64, meter=4, mode="minor", key="A", end_with="ring",
        lead=[("cello", 0, "legato"), ("oboe", 0, "legato"), ("violin", 0, "legato"), ("piano", 0, "normal")],
        double=None,
        counter=("viola", "guide", (55, 69), -7.0, 0.35, 1),
        comp=[("piano", "broken_slow", (45, 67), -9.0, 0.0)],
        pad=[("slow_strings", (50, 72), -11.0, 0.0)],
        bass=("contrabass", "root_whole", (28, 45), -9.0),
        drums=[],
        fill=None, crash=None, reverb=("hall", 0.34), vel=(0.35, 0.7), human=(0.012, 0.05),
        legato=1.03, rubato=0.06, rit=0.15, intro=1,
        gen=dict(cells="lyric", center=3, span=(-5, 10), leap=0.25)),
    "triumph": dict(
        tempo=108, meter=4, mode="major", key="Bb", end_with="button",
        lead=[("brass_section", 0, "legato"), ("french_horn", 0, "legato"), ("trumpet", 0, "legato")],
        double=("strings", 1, 0.0),
        counter=("french_horn", "guide", (55, 69), -5.0, 0.4, 1),
        comp=[("strings", "block_quarters", (55, 76), -8.0, 0.0), ("brass_section", "fanfare", (53, 70), -8.0, 0.6)],
        pad=[("choir_aahs", (55, 76), -11.0, 0.55)],
        bass=("tuba", "root_half", (28, 46), -4.0),
        drums=[("timpani", "timp_13", -9.0, 0.3, "tonic"), ("snare", "snare_march", -15.0, 0.5, None),
               ("bass_drum", "bass_drum_1", -10.0, 0.5, None)],
        fill="snare", crash="cymbals", reverb=("hall", 0.24), vel=(0.65, 1.0), human=(0.005, 0.04),
        legato=1.0, rubato=0.0, rit=0.08, intro=1,
        gen=dict(cells="heroic", center=7, span=(-3, 12), leap=0.4)),
    "lullaby": dict(
        tempo=66, meter=3, mode="major", key="F", end_with="ring",
        lead=[("music_box", 0, "normal"), ("celesta", 0, "normal"), ("flute", 0, "legato")],
        double=None,
        counter=("clarinet", "guide", (53, 67), -9.0, 0.45, 1),
        comp=[("harp", "waltz_arp", (41, 72), -7.0, 0.0)],
        pad=[("strings", (53, 72), -15.0, 0.4)],
        bass=("cello", "root_bar", (36, 52), -11.0),
        bass_min=0.3,
        drums=[],
        fill=None, crash=None, reverb=("hall", 0.33), vel=(0.35, 0.65), human=(0.012, 0.04),
        legato=1.0, rubato=0.04, rit=0.15, intro=1,
        gen=dict(cells="lullaby", center=4, span=(-3, 10), leap=0.25)),
    "comic_chase": dict(
        tempo=160, meter="2/4", mode="major", key="C", end_with="button",
        lead=[("xylophone", 0, "normal"), ("piccolo", 0, "auto"), ("trumpet", 0, "auto"), ("clarinet", 0, "auto")],
        double=("pizzicato_strings", 0, 0.5),
        counter=("bassoon", "fill", (41, 58), -6.0, 0.4, 0),
        comp=[("pizzicato_strings", "offbeat", (55, 70), -8.0, 0.0), ("brass_section", "offbeat_stab", (55, 70), -11.0, 0.7)],
        pad=[],
        bass=("tuba", "oompah", (31, 48), -3.0),
        drums=[("snare", "snare_train", -16.0, 0.4, None), ("woodblock", "woodblock_play", -15.0, 0.3, None),
               ("kick", "kick_soft", -13.0, 0.5, None)],
        fill="snare", crash="crash", reverb=("hall", 0.11), vel=(0.65, 0.95), human=(0.004, 0.05),
        legato=0.85, rubato=0.0, rit=0.0, intro=1, staccato_short=True,
        gen=dict(cells="chase", center=7, span=(-5, 12), leap=0.3, chromatic=0.2)),
    "festive_chinese": dict(
        tempo=132, meter="2/4", mode="gong", key="D", end_with="button",
        lead=[("suona", 0, "normal"), ("dizi", 0, "normal"), ("suona", 0, "normal")],
        double=("dizi", 1, 0.45),
        counter=("yangqin", "heterophony", (62, 86), -9.0, 0.55, 0),
        comp=[("pipa", "pent_ostinato", (57, 76), -10.0, 0.0), ("guzheng", "pent_arp", (50, 74), -12.0, 0.5),
              ("sheng", "pad_fifths", (60, 76), -15.0, 0.4)],
        pad=[("strings", (52, 72), -16.0, 0.7)],
        bass=("acoustic_bass", "pent_bass", (33, 50), -5.0),
        drums=[("tanggu", "tanggu", -7.0, 0.0, None), ("bo", "bo", -15.0, 0.2, None),
               ("xiaoluo", "xiaoluo", -15.0, 0.3, None), ("daluo", "daluo", -12.0, 0.4, None),
               ("bangzi", "bangzi", -19.0, 0.55, None)],
        fill="tanggu", crash="daluo", reverb=("hall", 0.17), vel=(0.65, 0.95), human=(0.004, 0.05),
        legato=0.95, rubato=0.0, rit=0.04, intro=2, luogu=True,
        gen=dict(cells="festive", center=7, span=(-5, 12), leap=0.3)),
    "tender_chinese": dict(
        tempo=68, meter=4, mode="gong", key="G", end_with="ring",
        lead=[("erhu", 0, "legato"), ("dizi", 0, "legato"), ("erhu", 0, "legato"), ("guzheng", 0, "normal")],
        double=None,
        counter=("cello", "guide", (45, 62), -8.0, 0.45, 1),
        comp=[("guzheng", "pent_flow", (50, 79), -8.0, 0.0)],
        pad=[("strings", (52, 72), -13.0, 0.3), ("sheng", (60, 74), -17.0, 0.65)],
        bass=("contrabass", "root_whole", (31, 48), -11.0),
        bass_min=0.35,
        drums=[],
        fill=None, crash=None, reverb=("hall", 0.33), vel=(0.4, 0.75), human=(0.012, 0.05),
        legato=1.03, rubato=0.05, rit=0.13, intro=1, gliss="guzheng",
        gen=dict(cells="lyric", center=5, span=(-5, 12), leap=0.3)),
    "night": dict(
        tempo=66, meter=4, mode="dorian", key="D", end_with="ring",
        lead=[("flute", -1, "legato"), ("dizi", 0, "legato"), ("vibraphone", 0, "normal")],
        double=None,
        counter=("clarinet", "guide", (50, 65), -8.0, 0.5, 1),
        comp=[("harp", "arp_slow", (45, 74), -9.0, 0.0), ("celesta", "twinkle", (79, 96), -16.0, 0.3)],
        pad=[("strings", (50, 69), -13.0, 0.0), ("voice_oohs", (55, 72), -17.0, 0.6)],
        bass=("contrabass", "root_whole", (28, 45), -11.0),
        drums=[],
        fill=None, crash="cymbal_swell", reverb=("hall", 0.4), vel=(0.35, 0.65), human=(0.012, 0.04),
        legato=1.02, rubato=0.04, rit=0.1, intro=2,
        gen=dict(cells="lyric", center=5, span=(-5, 9), leap=0.3)),
    "flashback": dict(
        tempo=76, meter=3, mode="major", key="D", end_with="ring",
        lead=[("music_box", 0, "normal"), ("piano", 0, "normal")],
        double=None,
        counter=None,
        comp=[("piano", "waltz_broken", (45, 69), -9.0, 0.0)],
        pad=[("warm_pad", (52, 72), -17.0, 0.3)],
        bass=None,
        drums=[],
        fill=None, crash=None, reverb=("hall", 0.36), vel=(0.35, 0.6), human=(0.014, 0.05),
        legato=1.0, rubato=0.05, rit=0.15, intro=1, fx="memory",
        gen=dict(cells="lullaby", center=5, span=(-3, 10), leap=0.25)),
    "underwater": dict(
        tempo=66, meter=4, mode="lydian", key="E", end_with="ring",
        lead=[("voice_oohs", 0, "legato"), ("celesta", 0, "normal"), ("flute", 0, "legato")],
        double=None,
        counter=("french_horn", "guide", (48, 62), -10.0, 0.5, 1),
        comp=[("harp", "arp_slow", (48, 79), -9.0, 0.0)],
        pad=[("warm_pad", (48, 72), -10.0, 0.0), ("voice_oohs", (55, 74), -14.0, 0.3), ("strings", (50, 72), -14.0, 0.5)],
        bass=("contrabass", "root_whole", (28, 45), -11.0),
        drums=[],
        fill=None, crash="cymbal_swell", reverb=("hall", 0.42), vel=(0.4, 0.7), human=(0.012, 0.04),
        legato=1.03, rubato=0.03, rit=0.1, intro=1, fx="underwater",
        gen=dict(cells="lyric", center=7, span=(-3, 12), leap=0.3)),
}
STYLES["heroic"] = STYLES["adventure"]

# rhythm cells: one bar each; negative = rest.  'cad' cells close a phrase (last element is the cadence note)
CELLS = {
    "bouncy": {4: [[1, .5, .5, 1, 1], [.5, .5, .5, .5, 1, 1], [.75, .25, .5, .5, 1, 1], [1, .5, .5, .5, .5, 1],
                   [.5, .5, 1, .5, .5, 1]],
               "half": [[1, .5, .5, 2], [.5, .5, 1, 2]], "full": [[1, 1, 2], [.5, .5, 1, 2], [1, 1, 1, -1]]},
    "heroic": {4: [[1.5, .5, 1, 1], [.75, .25, 1, 2], [1, .5, .5, 1, 1], [1.5, .5, 2]],
               "half": [[1, 1, 2], [1.5, .5, 2]], "full": [[1, 1, 2], [2, 2], [3, -1]]},
    "lyric": {4: [[1.5, .5, 2], [1, 1, 1, 1], [2, 1, 1], [1.5, .5, 1, 1], [1, 1, 2]],
              "half": [[2, 2], [1, 1, 2], [1.5, .5, 2]], "full": [[2, 2], [3, -1], [4]]},
    "lullaby": {3: [[1, 1, 1], [2, 1], [1.5, .5, 1], [1, 2]], "half": [[2, 1], [3]], "full": [[3], [2, -1]]},
    "sneaky": {4: [[.5, .5, -.5, .5, 1, 1], [1, .5, .5, -1, 1], [.5, .5, .5, .5, 2], [-.5, .5, .5, .5, 1, 1]],
               "half": [[1, 1, 2], [.5, .5, 1, 2]], "full": [[1, 1, 2], [2, 2], [1, -1, 2]]},
    "sparse_motif": {4: [[1.5, .5, 2], [2, -2], [1, 1, 2], [-1, 1, 1, 1]], "half": [[2, 2], [4]], "full": [[4], [2, 2]]},
    "chase": {2: [[.25, .25, .25, .25, .5, .5], [.5, .25, .25, .5, .5], [.25, .25, .5, .25, .25, .5],
                  [.5, .5, .5, .5]], "half": [[.5, .5, 1], [1, 1]], "full": [[.5, .5, 1], [1, -1]]},
    "festive": {2: [[.25, .25, .5, .5, .5], [.75, .25, .5, .5], [.5, .5, .25, .25, .5], [.5, .25, .25, 1],
                    [.5, .5, .5, .5]], "half": [[1.5, .5], [1, 1]], "full": [[1.5, -.5], [1, 1]]},
}
# motif shapes in scale steps from the first note (extended by steps when a rhythm cell has more notes)
MOTIF_SHAPES = {
    "bouncy": [[0, 2, 4, 2, 1, 0], [0, -1, 0, 2, 4, 2], [0, 4, 3, 2, 1, 2], [0, 2, 1, 3, 2, 4], [0, 0, 2, 4, 2, 0]],
    "heroic": [[0, 3, 2, 3, 4, 2], [0, 4, 3, 2, 3, 1], [0, -3, 0, 1, 2, 4], [0, 2, 4, 3, 2, 1]],
    "lyric": [[0, 1, 2, 1, 0], [0, 2, 1, 0, -1], [0, -1, 1, 2, 1], [0, 3, 2, 1, 2], [0, 1, 3, 2, 1]],
    "lullaby": [[0, -1, -2, 0], [0, 2, 1, 0], [0, 1, 0, -1], [0, -2, -1, 0]],
    "sneaky": [[0, 1, 0, -1, 0, 1, 2], [0, -1, -2, -1, 0, 2], [0, 0, 1, 0, -1, -2]],
    "sparse_motif": [[0, 1, -1, 0], [0, -1, 1, 3], [0, 2, 1, 0]],
    "chase": [[0, 1, 2, 3, 4, 2], [0, 2, 1, 3, 2, 4], [0, -1, 0, 1, 2, 4]],
    "festive": [[0, 1, 0, -1, -2, 0], [0, 2, 3, 2, 1, 0], [0, -1, -2, 0, 1, 2], [0, 1, 2, 4, 2, 1]],
}
# progressions (roman numerals, one bar per item) for the two halves of a period
PROGRESSIONS = {
    "major": (["I | V | vi | IV V", "I | IV | V | V", "I | vi | IV | V", "I | iii | IV | V", "I | IV | I | V"],
              ["I | V | IV V | I", "vi | IV | V | I", "IV | I | ii V | I", "I | vi | ii V | I", "IV | V | vi | ii V"]),
    "minor": (["i | VI | iv | V", "i | iv | VII | III", "i | VII | VI | V", "i | III | iv | V"],
              ["i | VI | iv V | i", "VI | VII | V | i", "iv | i | V | i", "i | iv | V | i"]),
    "dorian": (["i | IV | i | IV", "i | VII | IV | i", "i | ii | IV | IV"],
               ["i | IV | VII | i", "VII | IV | v | i", "i | IV | i | i"]),
    "mixolydian": (["I | VII | IV | I", "I | v | IV | IV", "I | VII | I | V"], ["I | VII | IV | I", "IV | VII | I | I"]),
    "lydian": (["I | II | I | II", "I | II | vii | iii", "I | II | iii | II"], ["I | II | vi | V", "I | II | I | I"]),
    "phrygian": (["i | II | i | VII", "i | II | III | II"], ["i | II | VII | i", "iv | II | i | i"]),
    "tension": (["i | i | VI | V", "i | bII | i | V", "i | VI | iv | V"], ["i | VI | bII | V", "i | iv | V | V"]),
}


# ------------------------------------------------------------------------------------------------ data
@dataclass
class Event:
    t: float                    # seconds from the start of the score
    inst: str
    pitch: float
    dur: float                  # gate (s)
    vel: float
    stem: str
    art: str = "normal"
    pan: float = 0.0
    gain_db: float = 0.0
    opts: dict = field(default_factory=dict)


@dataclass
class Bar:
    chords: list                # [(offset_beats, dur_beats, Chord)]
    melody: list                # [theory.Note] (beats relative to the bar)
    statement: int = -1         # -1 intro / coda
    theme_bar: int = -1
    phrase_end: bool = False
    final: bool = False
    shift: int = 0              # semitones (modulation) applied to this bar


@dataclass
class CuePlan:
    index: int
    cue: dict
    style: dict
    style_name: str
    key: T.Key
    tempo: float
    beats: float
    compound: bool
    bars: list
    start: float
    grid_end: float
    end: float
    intensity: float
    variation: set
    end_with: str
    theme_name: str
    statements: int
    seed: int
    beat_times: np.ndarray = None   # seconds at quarter-beat resolution (absolute)
    lead_shift: dict = field(default_factory=dict)

    def time(self, beat):
        """absolute seconds of a beat position (beats from the cue's first bar)"""
        q = np.asarray(beat, dtype=np.float64) * 4.0
        return np.interp(q, np.arange(len(self.beat_times)), self.beat_times)


def _rng(*keys):
    return dsp.rng("composer", *keys)


def _lerp(a, b, u):
    return a + (b - a) * float(np.clip(u, 0.0, 1.0))


# ------------------------------------------------------------------------------------------------ generated themes
def _prog_family(key, style):
    fam = style.get("progressions")
    if fam:
        return fam
    hm = key.harmony_mode
    if hm in PROGRESSIONS:
        return hm
    return "minor" if key.minorish else "major"


def _choose_cells(style, beats, compound):
    kind = style.get("gen", {}).get("cells", "lyric")
    table = CELLS.get(kind, CELLS["lyric"])
    b = int(round(beats))
    if b in table:
        return table[b], table["half"], table["full"]
    # adapt a 4/4 table by scaling the cells to the bar length
    src = next((table[k] for k in (4, 3, 2) if k in table), CELLS["lyric"][4])
    src_len = sum(abs(x) for x in src[0])
    s = beats / src_len
    scale = lambda cells: [[x * s for x in c] for c in cells]
    return scale(src), scale(table["half"]), scale(table["full"])


def generate_theme(key, beats, compound, nbars, style, rng):
    """compose a singable period: motif (bar 1), answer (bar 2), continuation, half cadence; then the motif returns
    and the second phrase closes on the tonic.  Strong beats take chord tones, weak beats move by step."""
    fam = _prog_family(key, style)
    a_opts, b_opts = PROGRESSIONS[fam]
    halves = [a_opts[rng.integers(len(a_opts))], b_opts[rng.integers(len(b_opts))]]
    hk = T.Key(key.tonic, key.harmony_mode)
    chord_bars = []
    for h in halves:
        chord_bars += T.parse_chords(h, hk, beats)
    while len(chord_bars) < nbars:
        chord_bars += chord_bars[: nbars - len(chord_bars)]
    chord_bars = chord_bars[:nbars]
    if nbars < 8:
        chord_bars[-1] = [(0.0, beats, T.parse_chord("I" if not key.minorish else "i", hk))]
        if nbars >= 2:
            v = T.parse_chord("V", T.Key(key.tonic, "harmonic_minor" if key.minorish else "major"))
            chord_bars[-2] = chord_bars[-2][:1] if chord_bars[-2][0][1] < beats else chord_bars[-2]
            o, d, c = chord_bars[-2][-1]
            chord_bars[-2][-1] = (o, d, c)
            if key.harmony_mode not in ("dorian", "mixolydian", "lydian"):
                chord_bars[-2] = [(0.0, beats / 2, chord_bars[-2][0][2]), (beats / 2, beats / 2, v)] \
                    if chord_bars[-2][0][2].root != v.root else [(0.0, beats, v)]
    if key.minorish and key.harmony_mode in ("minor",):
        # raise the dominant (harmonic minor) wherever V appears
        hm = T.Key(key.tonic, "harmonic_minor")
        for bar in chord_bars:
            for i, (o, d, c) in enumerate(bar):
                if c.root == hm.degree_pc(4) and c.intervals[:3] == (0, 3, 7):
                    bar[i] = (o, d, T.Chord(c.root, (0, 4, 7) + c.intervals[3:], c.bass, c.symbol))
    cells, half_cells, full_cells = _choose_cells(style, beats, compound)
    pick = lambda opts: list(opts[rng.integers(len(opts))])
    order = rng.permutation(len(cells))
    ra, rb, rc = (list(cells[order[k % len(cells)]]) for k in range(3))
    gen = style.get("gen", {})
    kind = gen.get("cells", "lyric")
    shapes = MOTIF_SHAPES.get(kind, MOTIF_SHAPES["lyric"])
    motif = list(shapes[rng.integers(len(shapes))])
    centre = 60 + key.tonic + gen.get("center", 5)
    if centre > 74:
        centre -= 12
    lo = centre + gen.get("span", (-5, 12))[0] - 2
    hi = centre + gen.get("span", (-5, 12))[1]
    if nbars >= 8:
        roles = ["motif", "sequence", "rise", "half", "motif", "sequence_up", "climax", "final"]
        rhythms = [ra, rb, rc, pick(half_cells), ra, rb, rc, pick(full_cells)]
        roles = (roles * (nbars // 8 + 1))[:nbars]
        rhythms = (rhythms * (nbars // 8 + 1))[:nbars]
        roles[-1], rhythms[-1] = "final", pick(full_cells)
    else:
        roles = (["motif", "sequence", "climax", "final"] if nbars >= 4 else ["motif", "final"][-nbars:])[:nbars]
        rhythms = ([ra, rb, rc, pick(full_cells)] if nbars >= 4 else [ra, pick(full_cells)][-nbars:])[:nbars]
        roles[-1] = "final"
        rhythms[-1] = pick(full_cells)
    dom_pcs = {key.degree_pc(4), key.degree_pc(1), key.degree_pc(6)}
    bars, last = [], None
    first_start = None
    for b in range(nbars):
        chords, rh, role = chord_bars[b], rhythms[b], roles[b]
        ch0 = chords[0][2]
        if role == "motif":
            if first_start is None:
                cands = [m for m in range(lo + 2, hi - 4) if ch0.contains(m) and m % 12 != ch0.root] or \
                    [m for m in range(lo, hi) if ch0.contains(m)]
                first_start = min(cands, key=lambda m: (abs(m - (centre + 2)), m))
            pitches = _realize(key, first_start, motif, rh, chords, beats, compound, lo, hi)
        elif role in ("sequence", "sequence_up"):
            base = first_start if first_start is not None else centre
            move = (ch0.root - chord_bars[0][0][2].root) % 12
            move = move - 12 if move > 6 else move
            ref = base + move + (2 if role == "sequence_up" else 0)
            near = [m for m in range(lo, hi + 1) if ch0.contains(m) and min(abs(m - ref), abs(m - ref - 12),
                                                                            abs(m - ref + 12)) <= 2]
            prev_note = last if last is not None else ref
            st = min(near, key=lambda m: (abs(m - prev_note), m)) if near else \
                min((m for m in range(lo, hi + 1) if ch0.contains(m)), key=lambda m: (abs(m - ref), m), default=ref)
            pitches = _realize(key, st, motif, rh, chords, beats, compound, lo, hi)
        elif role == "rise":
            st = key.step(key.snap(last if last is not None else centre), -1)
            pitches = _realize(key, st, [0, 1, 2, 3, 2, 4, 3, 5], rh, chords, beats, compound, lo, hi + 2)
        elif role == "climax":
            peak = min((m for m in range(centre + 5, hi + 1) if ch0.contains(m)), key=lambda m: abs(m - (centre + 7)),
                       default=hi)
            pitches = _realize(key, peak, [0, 1, 0, -1, -2, -3, -4, -5], rh, chords, beats, compound, lo, hi + 2)
        elif role == "half":
            ref = last if last is not None else centre
            goal = min((m for m in range(lo, hi + 1) if m % 12 in dom_pcs), key=lambda m: (abs(m - ref - 1), m))
            pitches = _approach(key, goal, ref, rh, lo, hi + 2)
        else:
            ref = last if last is not None else centre
            tonics = [m for m in range(lo - 2, hi + 1) if (m - key.tonic) % 12 == 0]
            goal = min(tonics, key=lambda m: abs(m - ref) + 0.6 * abs(m - centre) + (1.5 if m > ref else 0.0))
            pitches = _approach(key, goal, ref, rh, lo, hi + 2)
        notes, pos, k = [], 0.0, 0
        for d in rh:
            if d < 0:
                notes.append(T.Note(pos, -d, None))
                pos += -d
                continue
            notes.append(T.Note(pos, d, pitches[k]))
            last = pitches[k]
            k += 1
            pos += d
        bars.append(notes)
    return T.Theme(key, float(style.get("tempo", 100)), beats, compound,
                   [{"melody": m, "chords": c} for m, c in zip(bars, chord_bars)], "generated")


def _realize(key, start, shape, rhythm, chords, beats, compound, lo, hi):
    """pitches of a bar: a scale-step shape from `start` (moved to a chord tone that lets the whole shape fit
    inside [lo, hi]), extended by steps; notes on strong beats and long notes move to the nearest chord tone in the
    direction of the line, without turning a moving line into repeated notes"""
    durs = [d for d in rhythm if d > 0]
    pos_list, pos = [], 0.0
    for d in rhythm:
        if d > 0:
            pos_list.append(pos)
        pos += abs(d)
    shape = list(shape)
    while len(shape) < len(durs):
        shape.append(shape[-1] + (1 if len(shape) < 2 or shape[-1] >= shape[-2] else -1))
    shape = shape[:max(1, len(durs))]
    top, bottom = max(shape), min(shape)
    ch0 = _chord_at(chords, 0.0)

    def fits(m):
        return key.step(m, top) <= hi and key.step(m, bottom) >= lo

    if not fits(start):
        cands = [m for m in range(lo, hi + 1) if ch0.contains(m) and key.contains(m) and fits(m)] or \
            [m for m in range(lo, hi + 1) if key.contains(m) and fits(m)]
        if cands:
            start = min(cands, key=lambda m: abs(m - start))
    out = []
    for k, (d, ps) in enumerate(zip(durs, pos_list)):
        m = key.step(start, shape[k]) if shape[k] else key.snap(start)
        ch = _chord_at(chords, ps)
        if (_strong(ps, beats, compound) or d >= max(1.5, beats / 2)) and not _consonant(ch, m, key):
            move = shape[k] - (shape[k - 1] if k else 0)
            prev = out[-1] if out else None
            opts = [m + j for j in range(-4, 5) if _consonant(ch, m + j, key) and key.contains(m + j) and
                    lo <= m + j <= hi + 2]
            if move and prev is not None:
                opts = [x for x in opts if x != prev] or opts
            if opts:
                m = min(opts, key=lambda x: (abs(x - m) + (0.4 if move > 0 and x < m or move < 0 and x > m else 0.0)))
        out.append(m)
    return out


def _consonant(ch, m, key):
    """a chord tone -- or, in a pentatonic melody, the chord's added sixth or ninth (both idiomatic there)"""
    if ch.contains(m):
        return True
    return key.mode in T.PENTATONIC and (int(round(m)) - ch.root) % 12 in (2, 9) and key.contains(m)


def _approach(key, goal, ref, rhythm, lo=0, hi=127):
    """a stepwise line through the bar that lands on `goal` with its last note (approached from the side of `ref`,
    or from the other side when that would leave the range)"""
    n = sum(1 for d in rhythm if d > 0)
    direction = 1 if ref > goal else -1
    if abs(ref - goal) <= 1:
        direction = 1
    line = [key.step(goal, direction * (n - 1 - k)) if n - 1 - k else goal for k in range(n)]
    if any(m > hi or m < lo for m in line):
        line = [key.step(goal, -direction * (n - 1 - k)) if n - 1 - k else goal for k in range(n)]
    return line


def _chord_at(chords, pos):
    for o, d, c in chords:
        if o - 1e-6 <= pos < o + d - 1e-6:
            return c
    return chords[-1][2]


def _strong(pos, beats, compound):
    if compound:
        return abs(pos % 1.5) < 1e-6
    if beats >= 4:
        return abs(pos % 2.0) < 1e-6
    return abs(pos % 1.0) < 1e-6 and pos < 1e-6 or (beats == 3 and abs(pos) < 1e-6)


# ------------------------------------------------------------------------------------------------ adapting themes
def _map_pitch(p, src, dst):
    """move a pitch from one key/mode to another, keeping scale degree and chromatic alteration"""
    if p is None:
        return None
    rel_oct = (int(round(p)) - src.tonic) // 12
    deg, alt = src.degree_of(p)
    n_src, n_dst = len(src.scale), len(dst.scale)
    if n_src == n_dst:
        tgt = dst.scale[deg]
    else:
        ratio = deg * n_dst / n_src
        tgt = dst.scale[int(round(ratio)) % n_dst]
    base = dst.tonic + 12 * rel_oct + tgt + alt
    shift = (dst.tonic - src.tonic) % 12
    shift = shift - 12 if shift > 6 else shift
    return base if abs(base - (p + shift)) <= 6 else base + 12 * round(((p + shift) - base) / 12)


def _map_chord(c, src, dst):
    """chord in src key -> same function in dst key (quality from the destination mode; V stays major in minor)"""
    if src.tonic == dst.tonic and src.harmony_mode == dst.harmony_mode:
        return c
    hs, hd = T.Key(src.tonic, src.harmony_mode), T.Key(dst.tonic, dst.harmony_mode)
    rel = (c.root - hs.tonic) % 12
    if rel in hs.harmony_scale:
        deg = hs.harmony_scale.index(rel)
        diat = T.roman(hd, deg, seventh=len(c.intervals) >= 4)
        if c.intervals[:3] in ((0, 5, 7), (0, 2, 7)):
            diat = T.Chord(diat.root, c.intervals, None)
        if deg == 4 and hd.minorish and 4 in c.intervals:
            diat = T.Chord(diat.root, (0, 4, 7) + ((10,) if len(c.intervals) >= 4 else ()), None)
        bass = None
        if c.bass is not None:
            bass = _map_pitch(60 + c.bass, T.Key(hs.tonic, hs.harmony_mode), T.Key(hd.tonic, hd.harmony_mode)) % 12
        return T.Chord(diat.root, diat.intervals, bass, "")
    t = c.transpose((dst.tonic - src.tonic) % 12)
    return T.Chord(t.root, t.intervals, t.bass, "")


def adapt_theme(theme, key):
    """transpose / re-mode a theme into the cue key (nearest octave)"""
    src = theme.key
    if src.tonic == key.tonic and src.mode == key.mode:
        return theme
    bars = []
    for b in theme.bars:
        mel = [T.Note(n.beat, n.dur, _map_pitch(n.pitch, src, key), n.art, n.slide) for n in b["melody"]]
        chords = [(o, d, _map_chord(c, src, key)) for o, d, c in b["chords"]]
        bars.append({"melody": mel, "chords": chords})
    return T.Theme(key, theme.tempo, theme.beats, theme.compound, bars, theme.name)


# ------------------------------------------------------------------------------------------------ planning
def _variation(cue):
    v = cue.get("variation") or ""
    if isinstance(v, (list, tuple)):
        return {str(x) for x in v}
    return {x.strip() for x in str(v).replace(",", "+").replace("|", "+").split("+") if x.strip()}


def _fit_bars(span, tempo, beats, phrase, min_bars=1):
    """number of bars and the adjusted tempo so whole bars fill `span` seconds (tempo change <= ~6 %)"""
    bar_s = beats * 60.0 / tempo
    exact = span / bar_s
    best = None
    lo = max(min_bars, int(math.floor(exact / 1.065)))
    hi = max(lo, int(math.ceil(exact / 0.94)))
    for n in range(lo, hi + 1):
        new_t = n * beats * 60.0 / span
        change = abs(new_t / tempo - 1.0)
        if change > 0.065:
            continue
        score = change * 12.0 + (0.0 if n % phrase == 0 else (0.35 if n % 4 == 0 else (0.7 if n % 2 == 0 else 1.1)))
        if best is None or score < best[0]:
            best = (score, n, new_t)
    if best is None:
        n = max(min_bars, int(round(exact)))
        return n, n * beats * 60.0 / span
    return best[1], best[2]


def _theme_for(cue, themes):
    name = cue.get("theme")
    if not name:
        return None, ""
    spec = themes.get(name) if isinstance(name, str) else name
    if spec is None:
        raise ValueError(f"Cue at {cue.get('start')}s uses an unknown theme {name!r}")
    if isinstance(spec, T.Theme):
        return spec, getattr(spec, "name", str(name))
    return T.parse_theme(spec, name if isinstance(name, str) else "theme"), name if isinstance(name, str) else "theme"


def _cadence(bars, key, beats):
    """make the final bar a tonic arrival with the melody on the tonic, approached through the dominant"""
    hk = T.Key(key.tonic, key.harmony_mode)
    tonic = T.parse_chord("i" if key.minorish else "I", hk)
    dom_key = T.Key(key.tonic, "harmonic_minor" if key.harmony_mode == "minor" else key.harmony_mode)
    dom = T.parse_chord("V" if key.harmony_mode in ("major", "minor", "harmonic_minor") else
                        ("v" if key.harmony_mode in ("dorian", "mixolydian") else "V"), dom_key)
    last = bars[-1]
    already = last.chords[-1][2].root == tonic.root and last.chords[0][2].root == tonic.root
    last.chords = [(0.0, beats, tonic)]
    mel = [n for n in last.melody if n.pitch is not None]
    prev_pitch = None
    for b in reversed(bars[:-1]):
        ps = [n.pitch for n in b.melody if n.pitch is not None]
        if ps:
            prev_pitch = ps[-1]
            break
    ends_on_tonic = bool(mel) and (mel[-1].pitch - key.tonic) % 12 == 0
    if (mel or prev_pitch is not None) and not (already and ends_on_tonic):
        keep = [n for n in last.melody if n.end <= beats / 2 + 1e-6]
        kept = [n.pitch for n in keep if n.pitch is not None]
        ref = kept[-1] if kept else (mel[0].pitch if mel else prev_pitch)
        target = min((ref + d for d in range(-7, 8) if (ref + d - key.tonic) % 12 == 0), key=lambda m: abs(m - ref))
        first = last.melody[0] if last.melody else None
        if first is not None and first.pitch is not None and first.beat < 1e-6 and len(mel) <= 2:
            last.melody = [T.Note(0.0, beats, target)]
        else:
            start = keep[-1].end if keep else 0.0
            last.melody = keep + [T.Note(start, beats - start, target)]
    if len(bars) >= 2:
        pen = bars[-2]
        o, d, c = pen.chords[-1]
        if c.root not in (dom.root, (key.tonic + 5) % 12, tonic.root) and key.harmony_mode not in ("lydian",):
            if d >= beats - 1e-6 and beats >= 2:
                pen.chords = pen.chords[:-1] + [(o, d / 2, c), (o + d / 2, d / 2, dom)]
                o = o + d / 2
            else:
                pen.chords = pen.chords[:-1] + [(o, d, dom)]
            for nt in pen.melody:
                if nt.pitch is not None and nt.beat >= o - 1e-6 and not dom.contains(nt.pitch) and \
                        (nt.dur >= 0.75 or abs(nt.beat - o) < 1e-6):
                    nt.pitch = min((nt.pitch + k for k in range(-3, 4) if dom.contains(nt.pitch + k)),
                                   key=lambda m: (abs(m - nt.pitch), m), default=nt.pitch)


def plan_cue(cue, index, themes, seed, usage, next_cue=None):
    style_name = cue.get("style", "tender")
    if style_name not in STYLES:
        raise ValueError(f"Unknown music style {style_name!r}. Styles: {', '.join(sorted(STYLES))}")
    style = STYLES[style_name]
    variation = _variation(cue)
    theme, theme_name = _theme_for(cue, themes)
    base_key = theme.key if theme else T.parse_key(style["key"], style["mode"])
    key = T.parse_key(cue["key"], cue.get("mode") or base_key.mode) if cue.get("key") else base_key
    if cue.get("mode"):
        key = T.Key(key.tonic, cue["mode"])
    if "minor" in variation:
        key = T.Key(key.tonic, "yu" if key.mode in T.PENTATONIC else "minor")
    beats, compound = T.meter_beats(theme.beats if theme else style.get("meter", 4))
    if theme and theme.beats:
        beats, compound = theme.beats, theme.compound
    tempo = float(cue.get("tempo") or (theme.tempo if theme else style["tempo"]))
    start, end = float(cue["start"]), float(cue["end"])
    if end <= start:
        raise ValueError(f"Cue at {start}s ends before it starts")
    end_with = cue.get("end_with") or style.get("end_with", "ring")
    span = end - start - (BUTTON_LEAD if end_with == "button" else 0.0)
    cue_seed = int(cue.get("seed", seed)) * 1009 + index
    rng = _rng("plan", cue_seed, style_name)
    if theme is None:
        nb = 8 if span >= 7.5 * beats * 60.0 / tempo else 4
        theme = generate_theme(key, beats, compound, nb, style, rng)
        theme_name = f"generated:{style_name}"
    else:
        theme = adapt_theme(theme, key)
    L = theme.length
    phrase = L if L <= 8 else 4
    n, tempo = _fit_bars(span, tempo, beats, phrase)
    n = max(1, n)
    intro = 0
    if n >= L + style.get("intro", 1) + 1 and n >= 6:
        intro = style.get("intro", 1)
        if (n - intro) % L and (n - (intro - 1)) % L == 0 and intro > 0:
            intro -= 1
    bars = []
    first = theme.bars[0]["chords"]
    for i in range(intro):
        bars.append(Bar(chords=[(0.0, beats, first[0][2])], melody=[], statement=-1))
    rem = n - intro
    s = 0
    used = usage.get(theme_name, 0)
    while rem > 0:
        take = min(L, rem)
        if take < L and take < max(2, L // 2) and bars:
            # a short remainder becomes a coda: the theme's closing bars once more
            for b in range(L - take, L):
                src = theme.bars[b]
                bars.append(Bar(chords=list(src["chords"]), melody=[T.Note(x.beat, x.dur, x.pitch, x.art, x.slide)
                                                                     for x in src["melody"]],
                                statement=-2, theme_bar=b, phrase_end=b == L - 1))
            rem = 0
            break
        order = list(range(take))
        if take < L:
            # keep the theme's own closing bars (its cadence) at the end of a shortened statement
            close = 2 if take >= 4 else 1
            order = list(range(take - close)) + list(range(L - close, L))
        for k, b in enumerate(order):
            src = theme.bars[b]
            bars.append(Bar(chords=list(src["chords"]), melody=[T.Note(x.beat, x.dur, x.pitch, x.art, x.slide)
                                                                 for x in src["melody"]],
                            statement=used + s, theme_bar=b, phrase_end=(b + 1) % 4 == 0 or k == take - 1))
        rem -= take
        s += 1
    lift = cue.get("lift")
    if lift and s >= 2:
        semis = 2 if lift is True else int(lift)
        last_stmt = max(b.statement for b in bars)
        idx = [i for i, b in enumerate(bars) if b.statement == last_stmt]
        for i in idx:
            bars[i].shift = semis
        if idx and idx[0] > 0:
            pivot = bars[idx[0] - 1]
            new_dom = T.Chord((key.tonic + semis + 7) % 12, (0, 4, 7, 10))
            o, d, c = pivot.chords[-1]
            pivot.chords = pivot.chords[:-1] + ([(o, d / 2, c), (o + d / 2, d / 2, new_dom)] if d >= 2 else [(o, d, new_dom)])
    final_key = T.Key((key.tonic + (bars[-1].shift if bars else 0)) % 12, key.mode)
    if end_with != "cut" and n >= 1:
        _cadence_shifted(bars, final_key, beats, key)
    if cue.get("modulate") and next_cue is not None and next_cue.get("key"):
        nk = T.parse_key(next_cue["key"], next_cue.get("mode", "major"))
        if nk.tonic != final_key.tonic and end_with in ("ring", "fade"):
            bars[-1].chords = [(0.0, beats, T.Chord((nk.tonic + 7) % 12, (0, 4, 7, 10)))]
            for nt in bars[-1].melody:
                if nt.pitch is not None and not bars[-1].chords[0][2].contains(nt.pitch + bars[-1].shift):
                    nt.pitch = min((nt.pitch + d for d in range(-2, 3)
                                    if bars[-1].chords[0][2].contains(nt.pitch + d + bars[-1].shift)),
                                   key=lambda m: abs(m - nt.pitch), default=nt.pitch)
    if bars:
        bars[-1].final = True
        bars[-1].phrase_end = True
    usage[theme_name] = used + max(1, s)
    intensity = float(np.clip(cue.get("intensity", 0.6), 0.0, 1.0))
    plan = CuePlan(index, cue, style, style_name, key, tempo, beats, compound, bars, start, start + span, end,
                   intensity, variation, end_with, theme_name, s, cue_seed)
    plan.beat_times = _tempo_map(plan)
    return plan


def _cadence_shifted(bars, key, beats, base_key):
    """cadence in the key of the final bars (after a lift the bars carry a shift; notes stay unshifted)"""
    sh = bars[-1].shift
    if not sh:
        _cadence(bars, key, beats)
        return
    for b in bars[-2:]:
        for nt in b.melody:
            if nt.pitch is not None:
                nt.pitch += sh
        b.chords = [(o, d, c.transpose(sh)) for o, d, c in b.chords]
    _cadence(bars, key, beats)
    for b in bars[-2:]:
        for nt in b.melody:
            if nt.pitch is not None:
                nt.pitch -= sh
        b.chords = [(o, d, c.transpose(-sh)) for o, d, c in b.chords]


def _tempo_map(plan):
    """absolute times at quarter-beat resolution: steady tempo, a breath at phrase ends (expressive styles) and a
    ritardando into the last bar, all scaled so the bars end exactly at the grid end"""
    n_q = int(round(len(plan.bars) * plan.beats * 4)) + 1
    step = np.full(n_q - 1, 60.0 / plan.tempo / 4.0)
    rub = plan.style.get("rubato", 0.0)
    rit = plan.style.get("rit", 0.0) if plan.end_with in ("ring", "button") else 0.0
    q_per_bar = plan.beats * 4
    for i, b in enumerate(plan.bars):
        a = int(round(i * q_per_bar))
        e = int(round((i + 1) * q_per_bar))
        if b.phrase_end and rub > 0 and not b.final:
            k = max(1, int(q_per_bar // 2))
            step[e - k:e] *= 1.0 + rub * np.linspace(0.3, 1.0, k)
        if b.final and rit > 0:
            step[a:e] *= 1.0 + rit * np.linspace(0.2, 1.0, e - a) ** 1.5
        if i == len(plan.bars) - 2 and rit > 0:
            step[a:e] *= 1.0 + 0.35 * rit * np.linspace(0.0, 1.0, e - a)
    times = np.concatenate([[0.0], np.cumsum(step)])
    total = plan.grid_end - plan.start
    return plan.start + times * (total / max(times[-1], 1e-9))


# ------------------------------------------------------------------------------------------------ arrangement
class Arranger:
    """turns a CuePlan into note events, part by part"""

    def __init__(self, plan, seed):
        self.p = plan
        self.s = plan.style
        self.seed = seed
        self.events = []
        self.beats = plan.beats
        v = plan.variation
        self.intensity = plan.intensity
        if "full" in v:
            self.intensity = max(self.intensity, 0.85)
        if "light" in v:
            self.intensity = min(self.intensity, 0.4)
        self.sparse = "sparse" in v
        self.light = "light" in v
        self.sub = 2.0 if "half_time" in v else (0.5 if "double_time" in v else 1.0)
        self.key = plan.key
        self.n_stmt = max(1, plan.statements)

    # ------------------------------------------------------------------ helpers
    def rng(self, *k):
        return _rng(self.p.seed, self.p.style_name, *k)

    def level(self, bar):
        """intensity of a bar: statements build up gently through a cue"""
        st = max(0, bar.statement) if bar.statement >= 0 else 0
        if self.n_stmt > 1 and not self.sparse:
            first = min(b.statement for b in self.p.bars if b.statement >= 0) if any(
                b.statement >= 0 for b in self.p.bars) else 0
            k = (st - first) / max(1, self.n_stmt - 1)
            return float(np.clip(self.intensity - 0.15 + 0.3 * k, 0.0, 1.0))
        return self.intensity

    def vel(self, base, beat_in_bar, rng, accent=0.0):
        lo, hi = self.s["vel"]
        v = _lerp(lo, hi, base)
        if abs(beat_in_bar) < 1e-6:
            v *= 1.06
        elif self.beats >= 4 and abs(beat_in_bar - self.beats / 2) < 1e-6:
            v *= 1.03
        elif abs(beat_in_bar % 1.0) > 1e-6:
            v *= 0.94
        v *= 1.0 + accent
        v *= 1.0 + rng.normal(0.0, self.s["human"][1])
        return float(np.clip(v, 0.05, 1.0))

    def t(self, bar_i, beat, rng=None, sd=None):
        tt = float(self.p.time(bar_i * self.beats + beat))
        if rng is not None:
            sd = self.s["human"][0] if sd is None else sd
            tt += float(np.clip(rng.normal(0.0, sd), -2.5 * sd, 2.5 * sd))
        return tt

    def dur(self, bar_i, beat, length):
        return max(0.03, float(self.p.time(bar_i * self.beats + beat + length) - self.p.time(bar_i * self.beats + beat)))

    def add(self, *a, **k):
        self.events.append(Event(*a, **k))

    def chord_at(self, bar, beat):
        return _chord_at(bar.chords, beat).transpose(bar.shift) if bar.shift else _chord_at(bar.chords, beat)

    def slots(self, bar):
        return [(o, d, c.transpose(bar.shift) if bar.shift else c) for o, d, c in bar.chords]

    def melody_floor(self, bar):
        ps = [n.pitch + bar.shift + self.p.lead_shift.get(bar.statement, 0) for n in bar.melody if n.pitch is not None]
        return min(ps) if ps else None

    # ------------------------------------------------------------------ melody
    def lead_for(self, statement):
        leads = self.s["lead"]
        custom = self.p.cue.get("lead")
        if custom:
            custom = [custom] if isinstance(custom, str) else list(custom)
            leads = [(instruments.get(x).name, 0, "auto") for x in custom]
        st = max(0, statement)
        if self.light:
            light = [x for x in leads if x[0] in ("glockenspiel", "celesta", "flute", "music_box", "whistle", "dizi",
                                                  "pizzicato_strings", "clarinet", "harp", "marimba", "piano")]
            leads = light or leads
        return leads[st % len(leads)]

    def octave_fit(self, inst, notes, extra):
        ps = [n.pitch for n in notes if n.pitch is not None]
        if not ps:
            return 0
        med = float(np.median(ps))
        centre = LEAD_CENTER.get(inst, 72)
        lo, hi = instruments.get(inst).lo, instruments.get(inst).hi
        best, best_c = 0, 1e9
        for k in range(-4, 5):
            sh = 12 * k
            c = abs(med + sh - centre) + 3.0 * sum(1 for p in ps if p + sh < lo or p + sh > hi)
            if c < best_c:
                best, best_c = sh, c
        return best + 12 * extra

    def melody(self):
        stmts = {}
        for i, b in enumerate(self.p.bars):
            if b.statement >= 0:
                stmts.setdefault(b.statement, []).append(i)
        for st, idx in stmts.items():
            inst, extra, art_mode = self.lead_for(st)
            notes = [n for i in idx for n in self.p.bars[i].melody]
            sh = self.octave_fit(inst, notes, extra)
            self.p.lead_shift[st] = sh
            lvl = self.level(self.p.bars[idx[0]])
            rng = self.rng("melody", st)
            self._line(idx, inst, sh, art_mode, lvl, rng, "melody", 0.0, pan=0.0)
            dbl = self.s.get("double")
            if dbl and not self.sparse and lvl >= dbl[2] and dbl[0] != inst:
                sh2 = self.octave_fit(dbl[0], notes, dbl[1] - 1) if dbl[1] else self.octave_fit(dbl[0], notes, 0)
                if dbl[0] in ("strings", "slow_strings") and sh2 < sh:
                    sh2 += 12
                self._line(idx, dbl[0], sh2, "auto", lvl * 0.92, self.rng("double", st), "melody",
                           self.s.get("double_db", -5.0), pan=0.25)
            if self.p.style_name in ("festive_chinese",) and lvl >= 0.75 and inst != "pipa":
                self._line(idx, "pipa", self.octave_fit("pipa", notes, 0), "trem_long", lvl * 0.8,
                           self.rng("pipa", st), "melody", -10.0, pan=-0.3)

    def _line(self, idx, inst, shift, art_mode, lvl, rng, stem, gain_db, pan=0.0):
        legato = self.s.get("legato", 1.0)
        spec = instruments.get(inst)
        prev_pitch = None
        items = []
        for i in idx:
            bar = self.p.bars[i]
            for n in bar.melody:
                if n.pitch is None:
                    prev_pitch = None
                    continue
                if n.art == "tie" and items and items[-1][2] == n.pitch + bar.shift + shift:
                    items[-1][3] += n.dur
                    continue
                items.append([i, n.beat, n.pitch + bar.shift + shift, n.dur, n.art, n.slide])
        for j, (i, beat, pitch, d, art, slide) in enumerate(items):
            bar = self.p.bars[i]
            nxt = items[j + 1] if j + 1 < len(items) else None
            gap_to_next = None
            if nxt is not None:
                gap_to_next = (nxt[0] * self.beats + nxt[1]) - (i * self.beats + beat + d)
            a = "normal"
            if art in ("staccato", "accent", "marcato", "tenuto"):
                a = art
            elif art_mode == "auto" and self.s.get("staccato_short") and d <= 0.5 and spec.kind == "sustain":
                a = "staccato"
            elif art_mode == "legato" and spec.kind == "sustain":
                a = "legato" if gap_to_next is not None and gap_to_next < 1e-6 else "normal"
            gate_beats = d * (legato if spec.kind == "sustain" else 1.0)
            if spec.kind == "decay":
                gate_beats = d if art_mode != "staccato" else min(d, 0.5)
                if inst in ("piano", "harp", "guzheng", "music_box", "celesta", "vibraphone") and gap_to_next is not None:
                    gate_beats = d + min(gap_to_next, 1.0) * 0.5
            opts = {}
            if slide and prev_pitch is not None and spec.kind == "sustain":
                opts = {"slide_from": prev_pitch, "slide_time": 0.12}
            elif inst in ("erhu", "violin", "cello") and prev_pitch is not None and d >= 1.0 and \
                    3 <= abs(pitch - prev_pitch) <= 7 and rng.uniform() < 0.35:
                opts = {"slide_from": prev_pitch, "slide_time": 0.1}
            if inst == "dizi" and d >= 1.0 and rng.uniform() < 0.3 and not opts:
                a = "grace"
            if inst == "guzheng" and d >= 2.0 and rng.uniform() < 0.25:
                a = "press" if rng.uniform() < 0.4 else a
            if art_mode == "trem_long":
                if d < 1.0:
                    continue
                a = "trem"
            accent = 0.05 * (pitch - 72) / 12.0
            if bar.final and j == len(items) - 1:
                accent -= 0.06
            v = self.vel(lvl, beat, rng, accent)
            tt = self.t(i, beat, rng)
            self.add(tt, inst, pitch, self.dur(i, beat, gate_beats), v, stem, a, pan, gain_db, opts)
            prev_pitch = pitch

    # ------------------------------------------------------------------ countermelody
    def counter(self):
        c = self.s.get("counter")
        if not c or self.sparse or self.light:
            return
        inst, mode, (lo, hi), gdb, min_i, from_st = c
        rng = self.rng("counter")
        prev = None
        for i, bar in enumerate(self.p.bars):
            lvl = self.level(bar)
            if bar.statement < 0 and not bar.final or lvl < min_i:
                continue
            if bar.statement >= 0:
                first = min(b.statement for b in self.p.bars if b.statement >= 0)
                if bar.statement - first < from_st:
                    continue
            if mode == "guide":
                prev = self._guide(i, bar, inst, lo, hi, gdb, lvl, rng, prev)
            elif mode == "fill":
                self._fill(i, bar, inst, lo, hi, gdb, lvl, rng)
            elif mode == "heterophony":
                self._heterophony(i, bar, inst, gdb, lvl, rng)

    def _guide(self, i, bar, inst, lo, hi, gdb, lvl, rng, prev):
        mf = self.melody_floor(bar)
        for o, d, ch in self.slots(bar):
            tones = [ch.third, ch.seventh, ch.root, ch.fifth]
            tones = [t for t in tones if t is not None]
            opts = [m for m in range(lo, hi + 1) if m % 12 in tones[:2]] or \
                [m for m in range(lo, hi + 1) if m % 12 in tones]
            if mf is not None:
                opts = [m for m in opts if m <= mf - 3] or opts
            if not opts:
                continue
            ref = prev if prev is not None else (lo + hi) / 2
            m = min(opts, key=lambda x: (abs(x - ref), x))
            if d >= 4 - 1e-6 and rng.uniform() < 0.55:
                nxt_ch = self.chord_at(bar, o + d - 1e-3)
                self.add(self.t(i, o, rng), inst, m, self.dur(i, o, d * 0.5 + 0.05), self.vel(lvl * 0.85, o, rng),
                         "harmony", "legato", -0.35, gdb)
                step = self.key.step(m, -1 if rng.uniform() < 0.6 else 1)
                self.add(self.t(i, o + d * 0.5, rng), inst, step, self.dur(i, o + d * 0.5, d * 0.5),
                         self.vel(lvl * 0.8, o + d * 0.5, rng), "harmony", "normal", -0.35, gdb)
                m = step if nxt_ch.contains(step) else m
            else:
                self.add(self.t(i, o, rng), inst, m, self.dur(i, o, d + 0.02), self.vel(lvl * 0.85, o, rng), "harmony",
                         "legato", -0.35, gdb)
            prev = m
        return prev

    def _fill(self, i, bar, inst, lo, hi, gdb, lvl, rng):
        """answer the melody where it holds a long note or rests"""
        gaps = []
        mel = sorted(bar.melody, key=lambda n: n.beat)
        for n in mel:
            if n.pitch is None and n.dur >= 1.0:
                gaps.append((n.beat, n.dur))
            elif n.pitch is not None and n.dur >= 2.0:
                gaps.append((n.beat + 1.0, n.dur - 1.0))
        if not mel and bar.statement != -1:
            gaps.append((0.0, self.beats))
        for g0, gd in gaps[:1]:
            ch = self.chord_at(bar, g0)
            tones = sorted([m for m in range(lo, hi + 1) if ch.contains(m)])
            if not tones:
                continue
            k = int(min(4, gd / 0.5))
            start = tones[min(len(tones) - 1, int(rng.integers(len(tones) // 2, len(tones))))]
            seq = [start]
            for _ in range(k - 1):
                cands = [x for x in tones if x < seq[-1]] or tones
                seq.append(cands[-1])
            for j, p in enumerate(seq):
                b = g0 + 0.5 * j
                self.add(self.t(i, b, rng), inst, p, self.dur(i, b, 0.4), self.vel(lvl * 0.8, b, rng), "harmony",
                         "staccato", -0.4, gdb)

    def _heterophony(self, i, bar, inst, gdb, lvl, rng):
        """the melody again, simplified to its strong-beat notes and ornamented with neighbour notes"""
        sh = self.p.lead_shift.get(bar.statement, 0)
        for n in bar.melody:
            if n.pitch is None or n.art == "tie":
                continue
            p = n.pitch + bar.shift + sh
            spec = instruments.get(inst)
            while p < spec.lo:
                p += 12
            while p > spec.hi:
                p -= 12
            if n.dur >= 1.0 and rng.uniform() < 0.5:
                up = self.key.step(p, 1)
                self.add(self.t(i, n.beat, rng), inst, up, self.dur(i, n.beat, 0.12), self.vel(lvl * 0.7, n.beat, rng),
                         "harmony", "normal", 0.35, gdb - 2)
                self.add(self.t(i, n.beat + 0.125, rng), inst, p, self.dur(i, n.beat + 0.125, n.dur - 0.125),
                         self.vel(lvl * 0.8, n.beat, rng), "harmony", "normal", 0.35, gdb)
            elif abs(n.beat % 1.0) < 1e-6:
                self.add(self.t(i, n.beat, rng), inst, p, self.dur(i, n.beat, n.dur), self.vel(lvl * 0.8, n.beat, rng),
                         "harmony", "normal", 0.35, gdb)

    # ------------------------------------------------------------------ accompaniment
    def comp(self):
        for layer in self.s.get("comp", []):
            inst, pattern, (lo, hi), gdb, min_i = layer
            rng = self.rng("comp", inst, pattern)
            prev = None
            for i, bar in enumerate(self.p.bars):
                lvl = self.level(bar)
                if lvl < min_i or (self.sparse and min_i > 0.0) or (self.light and min_i > 0.3):
                    continue
                fn = getattr(self, "pat_" + pattern, None)
                if fn is None:
                    raise ValueError(f"Unknown accompaniment pattern {pattern!r}")
                prev = fn(i, bar, inst, lo, hi, gdb, lvl, rng, prev)

    def pads(self):
        for inst, (lo, hi), gdb, min_i in self.s.get("pad", []):
            rng = self.rng("pad", inst)
            prev = None
            run = None
            for i, bar in enumerate(self.p.bars):
                lvl = self.level(bar)
                if lvl < min_i:
                    run = None
                    continue
                mf = self.melody_floor(bar)
                for o, d, ch in self.slots(bar):
                    top = None if mf is None else mf - 2
                    v = T.voicing(ch, 4 if inst not in ("voice_oohs", "choir_aahs") else 3, lo, hi, prev, top)
                    if not v:
                        continue
                    same = run is not None and run[2] == tuple(v) and run[4] < 2
                    if same:
                        run[1] += d
                        run[4] += 1 if o == 0 else 0
                    else:
                        self._flush_pad(run, inst, gdb, rng)
                        run = [(i, o), d, tuple(v), lvl, 0]
                    prev = v
            self._flush_pad(run, inst, gdb, rng)

    def _flush_pad(self, run, inst, gdb, rng):
        if not run:
            return
        (i, o), d, v, lvl, _ = run
        art = "swell" if d >= 4 and rng.uniform() < 0.25 and inst not in ("warm_pad",) else "legato"
        for k, p in enumerate(v):
            self.add(self.t(i, o, rng, 0.004), inst, p, self.dur(i, o, d + 0.08), self.vel(lvl * 0.75, 0.5, rng),
                     "harmony", art, (-0.5, -0.15, 0.15, 0.5)[k % 4], gdb)

    def _tones(self, ch, lo, hi):
        return sorted(m for m in range(lo, hi + 1) if ch.contains(m))

    def _bass_tone(self, ch, lo):
        b = ch.bass_pc
        return lo + (b - lo) % 12

    def _sub(self, step):
        return max(0.25, step * self.sub)

    def pat_arp16(self, i, bar, inst, lo, hi, gdb, lvl, rng, prev):
        return self._arp(i, bar, inst, lo, hi, gdb, lvl, rng, self._sub(0.25), "updown", ring=1.5)

    def pat_arp8(self, i, bar, inst, lo, hi, gdb, lvl, rng, prev):
        return self._arp(i, bar, inst, lo, hi, gdb, lvl, rng, self._sub(0.5), "updown", ring=1.5)

    def pat_arp_slow(self, i, bar, inst, lo, hi, gdb, lvl, rng, prev):
        return self._arp(i, bar, inst, lo, hi, gdb, lvl, rng, self._sub(1.0 if self.beats != 3 else 1.0), "up", ring=2.0)

    def _arp(self, i, bar, inst, lo, hi, gdb, lvl, rng, step, shape, ring=1.0):
        mf = self.melody_floor(bar)
        for o, d, ch in self.slots(bar):
            base = self._bass_tone(ch, lo)
            tones = [m for m in self._tones(ch, base, min(hi, base + 19))]
            if mf is not None and inst not in ("harp",):
                tones = [m for m in tones if m <= mf - 1] or tones
            if not tones:
                continue
            seq = tones + tones[-2:0:-1] if shape == "updown" else tones
            k = 0
            b = o
            while b < o + d - 1e-6:
                p = seq[k % len(seq)]
                g = min(o + d - b, step * ring * 2) if inst in ("harp", "piano", "guzheng", "celesta") else step * ring
                self.add(self.t(i, b, rng), inst, p, self.dur(i, b, g), self.vel(lvl * 0.8, b, rng, -0.04 * (k % 2)),
                         "harmony", "normal", -0.3 + 0.6 * (p - lo) / max(1, hi - lo), gdb)
                k += 1
                b += step
        return None

    def pat_broken(self, i, bar, inst, lo, hi, gdb, lvl, rng, prev):
        """piano left hand: root - fifth - octave - tenth ... in eighths, held with the pedal until the chord changes"""
        step = self._sub(0.5)
        for o, d, ch in self.slots(bar):
            root = lo + (ch.bass_pc - lo) % 12
            third = ch.third if ch.third is not None else ch.root
            fifth = ch.fifth if ch.fifth is not None else ch.root
            r_pc = ch.root
            figure = [root, root + (fifth - ch.bass_pc) % 12, root + 12 + (r_pc - ch.bass_pc) % 12,
                      root + 12 + (third - ch.bass_pc) % 12 + (12 if (third - ch.bass_pc) % 12 < 5 else 0)]
            figure = [p if p <= hi else p - 12 for p in figure]
            seq = figure + [figure[2], figure[1]] if self.beats != 3 else [figure[0], figure[1], figure[3], figure[1],
                                                                           figure[2], figure[1]]
            k, b = 0, o
            while b < o + d - 1e-6:
                p = seq[k % len(seq)]
                self.add(self.t(i, b, rng), inst, p, self.dur(i, b, o + d - b + 0.1), self.vel(lvl * 0.75, b, rng,
                         -0.06 * (k % 2)), "harmony", "normal", -0.2, gdb)
                k += 1
                b += step
        return prev

    def pat_broken_slow(self, i, bar, inst, lo, hi, gdb, lvl, rng, prev):
        old = self.sub
        self.sub = old * 2.0
        try:
            return self.pat_broken(i, bar, inst, lo, hi, gdb, lvl, rng, prev)
        finally:
            self.sub = old

    def pat_waltz_broken(self, i, bar, inst, lo, hi, gdb, lvl, rng, prev):
        return self.pat_broken(i, bar, inst, lo, hi, gdb, lvl * 0.9, rng, prev)

    def pat_waltz_arp(self, i, bar, inst, lo, hi, gdb, lvl, rng, prev):
        return self.pat_broken(i, bar, inst, lo, hi, gdb, lvl, rng, prev)

    def pat_block_quarters(self, i, bar, inst, lo, hi, gdb, lvl, rng, prev):
        mf = self.melody_floor(bar)
        for o, d, ch in self.slots(bar):
            v = T.voicing(ch, 4, lo, hi, prev, None if mf is None else mf - 2)
            prev = v
            b = o
            while b < o + d - 1e-6:
                accent = 0.08 if abs(b) < 1e-6 else 0.0
                for k, p in enumerate(v):
                    self.add(self.t(i, b, rng, 0.003), inst, p, self.dur(i, b, 0.8 * self.sub), self.vel(
                        lvl * 0.8, b, rng, accent), "harmony", "marcato" if accent else "normal", (-0.4, -0.1, 0.1, 0.4)[k % 4], gdb)
                b += self.sub
        return prev

    def pat_pulse8(self, i, bar, inst, lo, hi, gdb, lvl, rng, prev):
        """driving string ostinato: the low chord tones in eighths, accents 3+3+2"""
        step = self._sub(0.5)
        accents = [1, 0, 0, 1, 0, 0, 1, 0]
        for o, d, ch in self.slots(bar):
            v = T.voicing(ch, 3, lo, hi, prev)
            prev = v
            k, b = 0, o
            while b < o + d - 1e-6:
                acc = accents[int(round(b / step)) % 8] if step == 0.5 else (1 if abs(b % 1.0) < 1e-6 else 0)
                for j, p in enumerate(v[:2] if not acc else v):
                    self.add(self.t(i, b, rng, 0.003), inst, p, self.dur(i, b, step * 0.7), self.vel(
                        lvl * (0.9 if acc else 0.7), b, rng), "harmony", "spiccato" if inst in (
                        "strings", "violin", "viola", "cello") else "staccato", (-0.35, 0.0, 0.35)[j % 3], gdb)
                k += 1
                b += step
        return prev

    def pat_stabs(self, i, bar, inst, lo, hi, gdb, lvl, rng, prev):
        if not (bar.theme_bar % 2 == 0 or bar.final):
            return prev
        o, d, ch = self.slots(bar)[0]
        v = T.voicing(ch, 4, lo, hi, prev)
        for k, p in enumerate(v):
            self.add(self.t(i, 0.0, rng, 0.003), inst, p, self.dur(i, 0.0, 0.45), self.vel(lvl, 0.0, rng, 0.1),
                     "harmony", "marcato", (-0.3, -0.1, 0.1, 0.3)[k % 4], gdb)
        if self.beats >= 4:
            for k, p in enumerate(v):
                self.add(self.t(i, 1.5, rng, 0.003), inst, p, self.dur(i, 1.5, 0.35), self.vel(lvl * 0.85, 1.5, rng),
                         "harmony", "staccato", (-0.3, -0.1, 0.1, 0.3)[k % 4], gdb - 2)
        return v

    def pat_fanfare(self, i, bar, inst, lo, hi, gdb, lvl, rng, prev):
        """triumphant brass: quarter, triplet eighths, two quarters on chord tones (every other bar)"""
        if bar.theme_bar % 2 == 1 and not bar.final:
            return prev
        o, d, ch = self.slots(bar)[0]
        v = T.voicing(ch, 3, lo, hi, prev)
        rhythm = [(0.0, 1.0), (1.0, 1 / 3), (4 / 3, 1 / 3), (5 / 3, 1 / 3), (2.0, 1.0), (3.0, 1.0)] if self.beats >= 4 \
            else [(0.0, 1.0), (1.0, 0.5), (1.5, 0.5)]
        for b, L in rhythm:
            if b >= self.beats:
                continue
            for k, p in enumerate(v):
                self.add(self.t(i, b, rng, 0.003), inst, p, self.dur(i, b, L * 0.85), self.vel(
                    lvl, b, rng, 0.06 if b == 0 else 0.0), "harmony", "accent" if b == 0 else "normal",
                    (-0.3, 0.0, 0.3)[k % 3], gdb)
        return v

    def pat_strum(self, i, bar, inst, lo, hi, gdb, lvl, rng, prev):
        """down / up strums in eighths (D . D U . U D U), strings spread by a few ms"""
        pattern = {4: "D.DU.UDU", 3: "D.DUDU", 2: "D.DU"}.get(int(round(self.beats)), "D.DU" * int(self.beats / 2))
        step = self._sub(0.5)
        for o, d, ch in self.slots(bar):
            v = T.voicing(ch, 4, lo, hi, prev)
            prev = v
            b = o
            while b < o + d - 1e-6:
                c = pattern[int(round(b / step)) % len(pattern)]
                if c in "DU":
                    notes = v if c == "D" else v[::-1][:3]
                    spread = 0.012 if c == "D" else 0.008
                    for k, p in enumerate(notes):
                        self.add(self.t(i, b, rng, 0.003) + k * spread, inst, p, self.dur(i, b, step * 1.8),
                                 self.vel(lvl * (0.85 if c == "D" else 0.65), b, rng), "harmony", "normal",
                                 -0.2 + 0.4 * k / max(1, len(notes) - 1), gdb)
                b += step
        return prev

    def pat_ostinato(self, i, bar, inst, lo, hi, gdb, lvl, rng, prev):
        """mallet ostinato on root - fifth - octave - fifth"""
        step = self._sub(0.5)
        for o, d, ch in self.slots(bar):
            tones = self._tones(ch, lo, hi)
            if not tones:
                continue
            r = min((m for m in tones if m % 12 == ch.root), default=tones[0])
            fifth = min((m for m in tones if ch.fifth is not None and m % 12 == ch.fifth and m > r), default=r + 7)
            fig = [r, fifth, r + 12 if r + 12 <= hi else fifth, fifth]
            k, b = 0, o
            while b < o + d - 1e-6:
                p = fig[k % 4]
                self.add(self.t(i, b, rng), inst, p, self.dur(i, b, step), self.vel(lvl * 0.7, b, rng), "harmony",
                         "normal", 0.35, gdb)
                k += 1
                b += step
        return prev

    def pat_offbeat(self, i, bar, inst, lo, hi, gdb, lvl, rng, prev):
        """the 'pah' of oom-pah: short chords on the off-beats"""
        for o, d, ch in self.slots(bar):
            v = T.voicing(ch, 3, lo, hi, prev)
            prev = v
            b = o + 0.5 * self.sub if self.beats <= 2 else o + 1.0
            while b < o + d - 1e-6:
                for k, p in enumerate(v):
                    self.add(self.t(i, b, rng, 0.003), inst, p, self.dur(i, b, 0.3), self.vel(lvl * 0.75, b, rng),
                             "harmony", "staccato", (-0.3, 0.0, 0.3)[k % 3], gdb)
                b += (1.0 if self.beats <= 2 else 2.0) * self.sub
        return prev

    def pat_offbeat_stab(self, i, bar, inst, lo, hi, gdb, lvl, rng, prev):
        if bar.theme_bar % 2:
            return prev
        return self.pat_offbeat(i, bar, inst, lo, hi, gdb, lvl * 0.9, rng, prev)

    def pat_tiptoe(self, i, bar, inst, lo, hi, gdb, lvl, rng, prev):
        """sneaky staccato chord tones on the beats, a grace of chromatic approach now and then"""
        for o, d, ch in self.slots(bar):
            tones = self._tones(ch, lo, hi)
            if not tones:
                continue
            b = o
            k = 0
            while b < o + d - 1e-6:
                p = tones[(k * 2) % len(tones)] if k % 2 == 0 else tones[min(len(tones) - 1, (k * 2 + 1) % len(tones))]
                self.add(self.t(i, b, rng), inst, p, self.dur(i, b, 0.3), self.vel(lvl * 0.7, b, rng), "harmony",
                         "normal", 0.25, gdb)
                k += 1
                b += 1.0 * self.sub
        return prev

    def pat_twinkle(self, i, bar, inst, lo, hi, gdb, lvl, rng, prev):
        """a few soft high chord tones scattered on the eighth grid"""
        for o, d, ch in self.slots(bar):
            tones = self._tones(ch, lo, hi)
            if not tones:
                continue
            for b in np.arange(o, o + d - 1e-6, 0.5):
                if rng.uniform() < 0.22:
                    p = tones[int(rng.integers(len(tones)))]
                    self.add(self.t(i, b, rng), inst, p, self.dur(i, b, 1.0), self.vel(lvl * 0.55, b, rng), "harmony",
                             "normal", float(rng.uniform(-0.6, 0.6)), gdb)
        return prev

    def pat_pad_high(self, i, bar, inst, lo, hi, gdb, lvl, rng, prev):
        for o, d, ch in self.slots(bar):
            v = T.voicing(ch, 3, lo, hi, prev)
            prev = v
            for k, p in enumerate(v):
                self.add(self.t(i, o, rng, 0.004), inst, p, self.dur(i, o, d + 0.05), self.vel(lvl * 0.6, 0.5, rng),
                         "harmony", "normal", (-0.5, 0.0, 0.5)[k % 3], gdb)
        return prev

    def pat_pad_fifths(self, i, bar, inst, lo, hi, gdb, lvl, rng, prev):
        """sheng: root and fifth (and octave) held through the chord"""
        for o, d, ch in self.slots(bar):
            r = lo + (ch.root - lo) % 12
            if r + 7 > hi:
                r -= 12
            self.add(self.t(i, o, rng, 0.004), inst, r, self.dur(i, o, d + 0.05), self.vel(lvl * 0.65, 0.5, rng),
                     "harmony", "fifth", 0.2, gdb)
        return prev

    def _pent_tones(self, ch, lo, hi):
        pcs = set(self.key.pcs())
        ct = [m for m in range(lo, hi + 1) if m % 12 in pcs and (ch.contains(m) or m % 12 == (ch.root + 2) % 12)]
        return ct or self._tones(ch, lo, hi)

    def pat_pent_ostinato(self, i, bar, inst, lo, hi, gdb, lvl, rng, prev):
        """pipa: pentatonic figure in sixteenths (2/4) around the chord, accents on the beats"""
        step = self._sub(0.25)
        fig = [0, 2, 1, 2, 3, 2, 1, 2]
        for o, d, ch in self.slots(bar):
            tones = self._pent_tones(ch, lo, hi)
            base = min(range(len(tones)), key=lambda j: abs(tones[j] - (lo + hi) / 2))
            k, b = 0, o
            while b < o + d - 1e-6:
                p = tones[min(len(tones) - 1, max(0, base - 1 + fig[k % 8]))]
                self.add(self.t(i, b, rng), inst, p, self.dur(i, b, step * 1.5), self.vel(
                    lvl * (0.8 if abs(b % 1.0) < 1e-6 else 0.6), b, rng), "harmony", "normal", -0.35, gdb)
                k += 1
                b += step
        return prev

    def pat_pent_arp(self, i, bar, inst, lo, hi, gdb, lvl, rng, prev):
        """guzheng: rising pentatonic arpeggio in eighths, ringing"""
        step = self._sub(0.5)
        for o, d, ch in self.slots(bar):
            tones = self._pent_tones(ch, lo, hi)
            k, b = 0, o
            while b < o + d - 1e-6:
                p = tones[k % len(tones)]
                self.add(self.t(i, b, rng), inst, p, self.dur(i, b, 1.5), self.vel(lvl * 0.65, b, rng), "harmony",
                         "normal", 0.35, gdb)
                k += 1
                b += step
        return prev

    def pat_pent_flow(self, i, bar, inst, lo, hi, gdb, lvl, rng, prev):
        """guzheng accompaniment for tender pieces: up-and-down pentatonic eighths, left-hand bass on the beat"""
        step = self._sub(0.5)
        for o, d, ch in self.slots(bar):
            tones = self._pent_tones(ch, lo + 7, hi)
            seq = tones[: 6] + tones[4:0:-1] if len(tones) > 6 else tones + tones[-2:0:-1]
            bass = lo + (ch.bass_pc - lo) % 12
            self.add(self.t(i, o, rng), inst, bass, self.dur(i, o, d), self.vel(lvl * 0.75, o, rng), "harmony",
                     "normal", -0.3, gdb)
            k, b = 1, o + step
            while b < o + d - 1e-6:
                p = seq[k % len(seq)]
                self.add(self.t(i, b, rng), inst, p, self.dur(i, b, 2.0), self.vel(lvl * 0.6, b, rng, -0.04 * (k % 2)),
                         "harmony", "normal", 0.25, gdb)
                k += 1
                b += step
        return prev

    # ------------------------------------------------------------------ bass
    def bass(self):
        b = self.s.get("bass")
        if not b:
            return
        inst, pattern, (lo, hi), gdb = b
        min_i = self.s.get("bass_min", 0.0)
        rng = self.rng("bass")
        prev = None
        for i, bar in enumerate(self.p.bars):
            lvl = self.level(bar)
            if lvl < min_i:
                continue
            for o, d, ch in self.slots(bar):
                root = T.bass_note(ch, lo, hi, prev)
                fifth = root + 7 if root + 7 <= hi else root - 5
                prev = root
                v = lambda b, a=0.0: self.vel(lvl * 0.85, b, rng, a)
                art = "staccato" if pattern in ("oompah", "drive8", "pedal8", "tiptoe_bass") else "normal"
                if pattern == "root_whole":
                    self.add(self.t(i, o, rng), inst, root, self.dur(i, o, d + 0.05), v(o), "bass", "legato", 0.0, gdb)
                elif pattern == "root_bar":
                    if o < 1e-6:
                        self.add(self.t(i, o, rng), inst, root, self.dur(i, o, self.beats), v(o), "bass", "normal",
                                 0.0, gdb)
                elif pattern == "root_half":
                    half = min(d, 2.0 * self.sub)
                    b2 = o
                    k = 0
                    while b2 < o + d - 1e-6:
                        self.add(self.t(i, b2, rng), inst, root if k % 2 == 0 else fifth, self.dur(i, b2, half * 0.95),
                                 v(b2), "bass", "normal", 0.0, gdb)
                        b2 += half
                        k += 1
                elif pattern in ("oompah", "pent_bass"):
                    step = (1.0 if self.beats <= 2 else 2.0) * self.sub
                    if pattern == "pent_bass":
                        step = 1.0 * self.sub
                    b2, k = o, 0
                    while b2 < o + d - 1e-6:
                        p = root if k % 2 == 0 else fifth
                        if pattern == "pent_bass" and k % 4 == 2 and root + 12 <= hi:
                            p = root + 12
                        self.add(self.t(i, b2, rng), inst, p, self.dur(i, b2, step * 0.55), v(b2), "bass", art, 0.0, gdb)
                        b2 += step
                        k += 1
                elif pattern in ("drive8", "pedal8"):
                    step = 0.5 * self.sub
                    tonic = T.bass_note(T.Chord(self.key.tonic), lo, hi, root) if pattern == "pedal8" else root
                    b2, k = o, 0
                    while b2 < o + d - 1e-6:
                        p = tonic
                        if pattern == "drive8" and abs(b2 - (o + d - step)) < 1e-6 and tonic + 12 <= hi + 5:
                            p = tonic + 12
                        self.add(self.t(i, b2, rng, 0.003), inst, p, self.dur(i, b2, step * 0.7), v(b2, 0.06 if k % 2 == 0
                                 else -0.05), "bass", "staccato", 0.0, gdb)
                        b2 += step
                        k += 1
                elif pattern in ("walking", "tiptoe_bass"):
                    nxt = self._next_root(i, o + d, lo, hi, root)
                    line = [root, root + (ch.third - ch.root) % 12 if ch.third is not None else fifth, fifth,
                            nxt + (1 if nxt < fifth else -1)]
                    b2, k = o, 0
                    while b2 < o + d - 1e-6:
                        self.add(self.t(i, b2, rng), inst, line[k % 4], self.dur(i, b2, 0.45 if pattern ==
                                 "tiptoe_bass" else 0.9), v(b2), "bass", art, 0.0, gdb)
                        b2 += 1.0 * self.sub
                        k += 1
                else:
                    raise ValueError(f"Unknown bass pattern {pattern!r}")

    def _next_root(self, i, beat, lo, hi, prev):
        bar_i = i + int(beat // self.beats)
        if bar_i >= len(self.p.bars):
            return prev
        ch = self.chord_at(self.p.bars[bar_i], beat % self.beats)
        return T.bass_note(ch, lo, hi, prev)

    # ------------------------------------------------------------------ percussion
    def _grid(self, name, table=GRIDS):
        g = table.get(name)
        if g is None:
            raise ValueError(f"Unknown percussion grid {name!r}")
        if self.p.compound and "c" in g:
            return g["c"], self.beats / len(g["c"])
        b = int(round(self.beats))
        if b in g:
            return g[b], 0.25
        src = g.get(4) or next(iter(g.values()))
        steps = int(round(self.beats * 4))
        return (src * (steps // len(src) + 1))[:steps], 0.25

    def drums(self):
        if self.sparse:
            return
        layers = list(self.s.get("drums", []))
        for inst, grid, gdb, min_i, mode in layers:
            if self.light and min_i > 0.3:
                continue
            rng = self.rng("drum", inst, grid)
            pattern, step = self._grid(grid)
            for i, bar in enumerate(self.p.bars):
                lvl = self.level(bar)
                if lvl < min_i or bar.final and self.p.end_with in ("ring", "button"):
                    continue
                if mode == "phrase" and not (bar.theme_bar % 4 == 0 and bar.theme_bar >= 0):
                    continue
                fill = self.s.get("fill")
                fill_bar = fill is not None and bar.phrase_end and (bar.theme_bar + 1) % 4 == 0 and not bar.final \
                    and lvl >= 0.45
                pat = pattern
                if fill_bar and fill in FILLS and inst in ("snare", "tom_low", "tanggu", "woodblock") and (
                        fill == "toms" and inst == "tom_low" or fill == inst or fill == "snare" and inst == "snare"):
                    pat, step = self._grid(fill, FILLS)
                for k, c in enumerate(pat):
                    if c == ".":
                        continue
                    b = k * step * self.sub
                    if b >= self.beats - 1e-6:
                        break
                    if self.sub > 1 and abs((k * step) % (step * 2)) > 1e-6 and c != "X":
                        continue
                    acc = {"X": 1.0, "x": 0.8, "o": 0.55}.get(c, 0.7)
                    pitch = 60
                    if inst == "timpani":
                        ch = self.chord_at(bar, b)
                        pitch = T.bass_note(T.Chord(ch.root if mode != "tonic" or b > 0 else self.key.tonic), 40, 52)
                    art = "normal"
                    if inst == "bo" and c == "o":
                        art = "muted"
                    if inst == "tanggu" and c == "o":
                        art = "edge"
                    self.add(self.t(i, b, rng, 0.004), inst, pitch, self.dur(i, b, 0.25), self.vel(lvl * acc, b, rng),
                             "percussion", art, _DRUM_PAN.get(inst, 0.0), gdb)
        self._crashes()
        if self.s.get("luogu"):
            self._luogu_breaks()

    def _crashes(self):
        c = self.s.get("crash")
        if not c or self.sparse or self.light:
            return
        rng = self.rng("crash")
        seen = set()
        for i, bar in enumerate(self.p.bars):
            if bar.statement < 0 or bar.theme_bar != 0 or bar.statement in seen or self.level(bar) < 0.45:
                continue
            seen.add(bar.statement)
            if c == "cymbal_swell":
                if i == 0:
                    continue
                t_hit = self.t(i, 0.0)
                L = min(2.0, self.dur(i - 1, 0.0, self.beats))
                self.add(t_hit - L, "cymbal_swell", 60, L, 0.55, "percussion", "normal", 0.0, -16.0)
            else:
                self.add(self.t(i, 0.0, rng, 0.003), c, 60, 1.0, self.vel(self.level(bar), 0.0, rng, 0.1),
                         "percussion", "normal", 0.25 if c != "daluo" else -0.2, -8.0)
                if c == "daluo":
                    self.add(self.t(i, 0.0, rng, 0.003), "bo", 60, 1.0, self.vel(self.level(bar), 0.0, rng),
                             "percussion", "normal", 0.3, -11.0)

    def _luogu_breaks(self):
        """at the end of every statement: 'cang - cai - cang' -- gong, cymbals and drum together"""
        rng = self.rng("luogu")
        for i, bar in enumerate(self.p.bars):
            if bar.statement < 0 or not bar.phrase_end or (bar.theme_bar + 1) % 8 != 0 or bar.final:
                continue
            lvl = self.level(bar)
            last = self.beats - 1.0
            for b, kind in ((last, "cang"), (last + 0.5, "cai")):
                if kind == "cang":
                    self.add(self.t(i, b, rng, 0.003), "daluo", 60, 1.0, self.vel(lvl, 0.0, rng), "percussion",
                             "normal", -0.2, -11.0)
                self.add(self.t(i, b, rng, 0.003), "bo", 60, 1.0, self.vel(lvl * 0.9, 0.0, rng), "percussion",
                         "normal" if kind == "cang" else "muted", 0.3, -13.0)
                self.add(self.t(i, b, rng, 0.003), "tanggu", 60, 0.3, self.vel(lvl, 0.0, rng), "percussion",
                         "normal", 0.0, -9.0)

    # ------------------------------------------------------------------ endings, embellishments, hits
    def ending(self):
        p = self.p
        if not p.bars:
            return
        i = len(p.bars) - 1
        bar = p.bars[-1]
        ch = self.chord_at(bar, 0.0)
        lvl = self.level(bar)
        if p.end_with == "button":
            t_b = p.grid_end
            lead = self.lead_for(max(0, bar.statement))[0]
            v = min(1.0, _lerp(*self.s["vel"], lvl) * 1.1)
            spec = instruments.get(lead)
            top = T.voicing(ch, 3, spec.lo + 7, min(spec.hi, spec.lo + 26))
            for k, m in enumerate(top):
                self.add(t_b, lead, m, 0.18, v, "melody", "staccato" if spec.kind == "sustain" else "normal",
                         (-0.2, 0.0, 0.2)[k % 3], 1.0)
            for inst, _, (lo, hi), gdb, _mi in self.s.get("comp", [])[:1]:
                for m in T.voicing(ch, 3, lo, hi):
                    self.add(t_b, inst, m, 0.2, v * 0.9, "harmony", "staccato", 0.0, gdb)
            b = self.s.get("bass")
            if b:
                self.add(t_b, b[0], T.bass_note(ch, b[2][0], b[2][1]), 0.25, v, "bass", "staccato", 0.0, b[3])
            hits = {"playful": [("woodblock", -6.0), ("glockenspiel", -5.0), ("kick", -9.0)],
                    "comic_chase": [("crash", -9.0), ("kick", -8.0)],
                    "festive_chinese": [("daluo", -8.0), ("bo", -10.0), ("tanggu", -6.0)],
                    "adventure": [("cymbals", -9.0), ("timpani", -6.0)], "triumph": [("cymbals", -7.0), ("timpani", -5.0)]}
            for inst, gdb in hits.get(p.style_name, [("timpani", -8.0)] if self.s.get("drums") else []):
                pitch = T.bass_note(T.Chord(self.key.tonic), 40, 52) if inst == "timpani" else (
                    T.voicing(ch, 1, 84, 96)[0] if inst == "glockenspiel" else 60)
                self.add(t_b, inst, pitch, 0.3, v, "percussion", "normal", 0.0, gdb)
        elif p.end_with == "ring":
            if p.style_name in ("festive_chinese",):
                self.add(self.t(i, 0.0), "daluo", 60, 1.0, 0.75, "percussion", "normal", -0.2, -10.0)
            elif self.s.get("crash") == "cymbal_swell" or p.style_name in ("tender", "wonder", "sad", "lullaby"):
                if self.s.get("gliss") or p.style_name in ("wonder",):
                    pass

    def embellish(self):
        p = self.p
        rng = self.rng("embellish")
        g = self.s.get("gliss")
        if g:
            for i, bar in enumerate(p.bars):
                if bar.statement >= 0 and bar.theme_bar == 0 and self.level(bar) >= 0.3:
                    ch = self.chord_at(bar, 0.0)
                    target = T.voicing(ch, 1, 74, 86)
                    if not target:
                        continue
                    L = 0.45
                    t0 = self.t(i, 0.0) - L
                    if t0 < p.start:
                        continue
                    self.add(t0, g, target[0], 1.5, 0.55, "fx", "gliss", 0.2, -8.0,
                             {"scale": tuple(sorted({(pc - target[0]) % 12 for pc in self.key.pcs()})), "sweep": L,
                              "span": 14})
        if self.s.get("sparkle"):
            for i, bar in enumerate(p.bars):
                if bar.phrase_end and not bar.final and bar.statement >= 0 and rng.uniform() < 0.6:
                    ch = self.chord_at(bar, self.beats - 1.0)
                    tones = [m for m in range(84, 101) if ch.contains(m)][:4]
                    for k, m in enumerate(tones):
                        self.add(self.t(i, self.beats - 1.0) + 0.07 * k, "glockenspiel", m, 0.6, 0.45, "fx", "normal",
                                 0.4, -14.0)

    def hits(self):
        p = self.p
        chinese = p.style_name in ("festive_chinese", "tender_chinese")
        for h in p.cue.get("hits", []) or []:
            t_hit = float(h["t"])
            kind = h.get("kind", "stinger")
            gain = float(h.get("gain_db", 0.0))
            bar_i = int(np.clip(np.searchsorted(p.beat_times, t_hit) / 4.0 // self.beats, 0, len(p.bars) - 1))
            bar = p.bars[bar_i]
            ch = self.chord_at(bar, 0.0)
            v = float(h.get("velocity", 0.85))
            if kind == "stinger":
                if chinese:
                    for inst, gdb in (("daluo", -6.0), ("bo", -8.0), ("tanggu", -4.0)):
                        self.add(t_hit, inst, 60, 0.5, v, "fx", "normal", 0.0, gdb + gain)
                    for m in T.voicing(ch, 2, 72, 88):
                        self.add(t_hit, "suona", m, 0.35, v, "fx", "accent", 0.0, -6.0 + gain)
                else:
                    for m in T.voicing(ch, 4, 55, 76):
                        self.add(t_hit, "brass_section", m, 0.3, v, "fx", "marcato", 0.0, -6.0 + gain)
                        self.add(t_hit, "strings", m + 12, 0.25, v, "fx", "marcato", 0.0, -9.0 + gain)
                    self.add(t_hit, "timpani", T.bass_note(ch, 40, 52), 0.5, v, "fx", "normal", 0.0, -5.0 + gain)
                    self.add(t_hit, "cymbals", 60, 1.0, v * 0.9, "fx", "normal", 0.3, -9.0 + gain)
            elif kind == "crash":
                if chinese:
                    self.add(t_hit, "daluo", 60, 1.0, v, "fx", "normal", -0.2, -6.0 + gain)
                    self.add(t_hit, "bo", 60, 1.0, v, "fx", "normal", 0.3, -8.0 + gain)
                else:
                    self.add(t_hit, "crash", 60, 1.0, v, "fx", "normal", 0.35, -6.0 + gain)
                    self.add(t_hit, "bass_drum", 60, 1.0, v, "fx", "normal", 0.0, -7.0 + gain)
            elif kind == "swell":
                L = float(h.get("length", 2.0))
                self.add(t_hit - L, "cymbal_swell", 60, L, v, "fx", "normal", 0.0, -6.0 + gain)
                for m in T.voicing(ch, 3, 55, 74):
                    self.add(t_hit - L, "strings", m, L, v * 0.8, "fx", "swell", 0.0, -12.0 + gain)
            elif kind in ("pluck_rise", "fall"):
                inst = "guzheng" if chinese else "harp"
                tones = [m for m in range(55, 91) if ch.contains(m) or (chinese and self.key.contains(m))]
                tones = tones[::2] if len(tones) > 12 else tones
                n = min(10, len(tones))
                seq = tones[:n] if kind == "pluck_rise" else tones[::-1][:n]
                span = float(h.get("length", 0.6))
                for k, m in enumerate(seq):
                    tt = (t_hit - span + span * k / max(1, n - 1)) if kind == "pluck_rise" else t_hit + span * k / max(1, n - 1)
                    self.add(tt, inst, m, 0.8, v * (0.55 + 0.45 * (k / max(1, n - 1) if kind == "pluck_rise" else
                                                              1 - k / max(1, n - 1))), "fx", "normal",
                             -0.4 + 0.8 * k / max(1, n - 1), -6.0 + gain)
                    if not chinese:
                        self.add(tt, "pizzicato_strings", m, 0.3, v * 0.7, "fx", "normal", 0.0, -10.0 + gain)
            elif kind == "sparkle":
                tones = [m for m in range(79, 100) if ch.contains(m)][:6]
                for k, m in enumerate(tones):
                    self.add(t_hit + 0.055 * k, "celesta" if k % 2 else "glockenspiel", m, 0.8, v * 0.7, "fx", "normal",
                             -0.4 + 0.16 * k, -9.0 + gain)
                self.add(t_hit, "triangle", 60, 1.0, v * 0.6, "fx", "normal", 0.5, -12.0 + gain)
            else:
                raise ValueError(f"Unknown hit kind {kind!r}")

    def build(self):
        self.melody()
        self.counter()
        self.comp()
        self.pads()
        self.bass()
        self.drums()
        self.ending()
        self.embellish()
        self.hits()
        return self.events


_DRUM_PAN = {"hihat_closed": 0.3, "hihat_open": 0.3, "shaker": 0.35, "tambourine": -0.3, "woodblock": -0.25,
             "woodblock_low": -0.2, "clap": 0.0, "ride": 0.35, "tom_low": -0.25, "tom_mid": 0.1, "tom_high": 0.3,
             "xiaoluo": 0.35, "bo": 0.25, "daluo": -0.25, "bangzi": 0.45, "muyu": -0.4, "triangle": 0.45,
             "timpani": -0.15, "taiko": 0.0, "tanggu": 0.0}


# ------------------------------------------------------------------------------------------------ rendering
def _render_events(events, n, offset, seed):
    """{stem: (2, n)} buffers; event times are relative to `offset` seconds"""
    out = {s: np.zeros((2, n)) for s in STEMS}
    for k, e in enumerate(sorted(events, key=lambda e: (e.inst, e.t))):
        s = int(round((e.t - offset) * SR))
        if s >= n:
            continue
        clip = instruments.play(e.inst, e.pitch, e.dur, e.vel, e.art, seed=seed + k, **(e.opts or {}))
        if e.pan:
            clip = dsp.pan_stereo(clip, e.pan, 1.0)
        dsp.place(out[e.stem], clip, s, dsp.db2lin(e.gain_db))
    return out


def _memory_fx(x, rng):
    """a remembered sound: tape wow and flutter, narrow band, warm saturation, faint hiss, narrower image"""
    n = x.shape[-1]
    wow = 0.0018 * np.sin(2 * np.pi * 0.55 * np.arange(n) / SR) + 0.0006 * dsp.ctrl_noise(n, rng, 7.0)
    y = dsp.varispeed(x, 1.0 + wow, n_out=n)
    y = dsp.highpass(y, 160, 2)
    y = dsp.lowpass(y, 4800, 2)
    y = dsp.saturate(y * 1.6, 0.25) / 1.6
    m = 0.5 * (y[0] + y[1])
    s = 0.5 * (y[0] - y[1]) * 0.6
    y = np.vstack([m + s, m - s])
    hiss = dsp.bandpass(rng.standard_normal((2, n)), 1500, 6000, 2)
    return y + hiss * (dsp.rms(y) / (dsp.rms(hiss) + 1e-12) * dsp.db2lin(-34.0))


def _underwater_fx(x, rng):
    n = x.shape[-1]
    t = np.arange(n) / SR
    fc = 2200.0 * (1.0 + 0.35 * np.sin(2 * np.pi * 0.07 * t + 1.0))
    y = dsp.lp_varying(x, fc, 0.9, spacing=0.5)
    wob = 0.0012 * np.sin(2 * np.pi * 0.23 * t)
    return dsp.varispeed(y, 1.0 + wob, n_out=n)


def render_cue(plan, seed=0):
    """render one planned cue -> ({stem: (2, m)}, start_sample) with fades and reverb applied"""
    events = Arranger(plan, seed).build()
    pre = 0.6 if any(e.t < plan.start for e in events) else 0.05
    pre = max(pre, plan.start - min((e.t for e in events), default=plan.start) + 0.05)
    t0 = plan.start - pre
    tail = 0.03 if plan.end_with == "cut" else TAIL_S
    n = n_of(plan.end - t0 + tail)
    stems = _render_events(events, n, t0, seed * 7919 + plan.index * 104729)
    rng = _rng("cuefx", plan.seed)
    fx = plan.style.get("fx")
    preset, wet = plan.style.get("reverb", ("hall", 0.25))
    wet = float(plan.cue.get("reverb", wet))
    for s in STEMS:
        x = stems[s]
        if not np.any(x):
            continue
        if fx == "memory":
            x = _memory_fx(x, rng)
        elif fx == "underwater":
            x = _underwater_fx(x, rng)
        w = wet * (0.6 if s == "bass" else (0.85 if s == "percussion" else 1.0))
        if w > 0:
            x = x + w * dsp.convolve_reverb(x, preset)
        stems[s] = x
    # cue envelope: fade in, and the ending
    env = np.ones(n)
    fi = float(plan.cue.get("fade_in", 0.0) or 0.0)
    a = n_of(pre)
    if fi > 0:
        k = n_of(fi)
        env[:a] = 0.0
        env[a:a + k] = 0.5 - 0.5 * np.cos(np.pi * np.linspace(0, 1, len(env[a:a + k])))
    else:
        env[:a] = np.clip(np.linspace(-3.0, 1.0, a), 0.0, 1.0) if a > 0 else env[:a]
    e_i = n_of(plan.end - t0)
    if plan.end_with == "fade":
        fl = float(plan.cue.get("fade_out", min(4.0, 0.3 * (plan.end - plan.start))))
        k = n_of(fl)
        env[e_i - k:e_i] *= 0.5 + 0.5 * np.cos(np.pi * np.linspace(0, 1, k))
        env[e_i:] = 0.0
    elif plan.end_with == "cut":
        k = n_of(0.03)
        env[e_i - k:e_i] *= np.linspace(1, 0, k)
        env[e_i:] = 0.0
    else:
        k = n - e_i
        env[e_i:] *= np.clip(1.0 - np.linspace(0, 1, k) ** 2, 0, 1) if k > 0 else 1.0
    for s in STEMS:
        stems[s] *= env
    return stems, int(round(t0 * SR))           # may be negative: the pre-roll before the film starts is dropped


def plan(music, duration, seed=0):
    """plan every cue (no audio): keys, tempi, bars and statements -- useful for picture sync"""
    themes = {**THEMES, **(music.get("themes") or {})}
    cues = sorted(music.get("cues") or [], key=lambda c: float(c["start"]))
    usage = {}
    out = []
    for i, cue in enumerate(cues):
        if float(cue["start"]) >= duration:
            continue
        p = plan_cue(cue, i, themes, seed, usage, cues[i + 1] if i + 1 < len(cues) else None)
        out.append(p)
    return out


def summary(plans):
    rows = []
    for p in plans:
        rows.append({"start": p.start, "end": p.end, "style": p.style_name, "theme": p.theme_name,
                     "key": f"{T.PC_NAME[p.key.tonic]} {p.key.mode}", "tempo": round(p.tempo, 2), "bars": len(p.bars),
                     "statements": p.statements, "end_with": p.end_with,
                     "downbeats": [round(float(p.time(i * p.beats)), 3) for i in range(len(p.bars))]})
    return rows


def render_score(music, duration, seed=0):
    """Render the cues of `music` into stems over `duration` seconds."""
    n = n_of(duration)
    stems = {s: np.zeros((2, n)) for s in STEMS}
    for p in plan(music, duration, seed):
        cue_stems, at = render_cue(p, seed)
        for s in STEMS:
            dsp.place(stems[s], cue_stems[s], at)
    total = sum(stems.values())
    if np.any(total):
        try:
            import pyloudnorm as pyln
            lufs = pyln.Meter(SR).integrated_loudness(total.T) if total.shape[-1] > SR // 2 else -70.0
        except Exception:
            lufs = -70.0
        if not np.isfinite(lufs) or lufs < -70:
            lufs = float(dsp.lin2db(dsp.rms(total) + 1e-12)) - 3.0
        g = dsp.db2lin(SCORE_LUFS - lufs)
        pk = dsp.peak(total) * g
        if pk > dsp.db2lin(-1.0):
            g *= dsp.db2lin(-1.0) / pk
        for s in STEMS:
            stems[s] *= g
    return stems
