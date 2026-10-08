"""
codecinema.audio.instruments -- one catalog of named instruments with a uniform note call.

    play(name, pitch, duration, velocity=0.8, articulation="normal", seed=0, **opts) -> (2, n) float64 at dsp.SR
        pitch      MIDI number (float allowed: fractions detune); ignored by unpitched percussion
        duration   gate in seconds (how long the note is held); the clip continues through the release / ring
        velocity   0..1 (values above 1 are read as MIDI 1..127)
        articulation  normal | staccato | staccatissimo | tenuto | legato | accent | marcato | swell | fp | sfz |
                   dim | scoop | fall | bend_up | trill | vibrato | slide, plus per-instrument ones (pizz, trem,
                   spiccato, mute, harmonic, gliss, gliss_down, press, grace, roll, choke, muted, rim, edge, flam)
        opts       bend (cents: scalar, array at dsp.SR or [(t, cents), ...]), vibrato (depth_cents, rate_hz, delay_s),
                   slide_from (MIDI pitch to glide from) + slide_time, scale (semitone offsets for glissandi),
                   source ('sampled' | 'synth' to force one)
    catalog() -> [{"name", "family", "description", "source", "range", "articulations"}]
    names(family=None), source(name), get(name)

A named instrument plays its General MIDI program from the sound bank (soundfont.default()) when one is available,
otherwise its synthesized model (codecinema.audio.synth / percussion).  The Chinese plucked and blown instruments are
always synthesized.  Every source is loudness-matched once (short-term RMS of a reference note), so velocity 0.8
sounds equally loud on every instrument; the velocity law is amplitude ~ velocity^2 for both sources.
Synthesized notes are rendered once per pitch / velocity layer and then shaped (damper, release, crossfade loop),
which makes long scores fast; notes with bends are rendered individually.
"""
from collections import OrderedDict
from dataclasses import dataclass

import numpy as np

from codecinema.audio import dsp, percussion as perc, soundfont, synth
from codecinema.audio.dsp import SR, n_of

REF_DB = -20.0                 # short-term RMS of a reference note at velocity 0.8
LONG_SUSTAIN = 4.0             # cached length of sustained synth notes (longer gates loop with crossfades)
LAYERS = (0.25, 0.45, 0.65, 0.82, 1.0)
LAYERS_SUSTAIN = (0.35, 0.65, 0.9)   # sustained synth timbres change little with velocity: fewer renders
CACHE_SAMPLES = 96_000_000     # synth note cache budget (float32 samples, ~380 MB)
COMMON_ARTS = ("normal", "staccato", "staccatissimo", "tenuto", "legato", "accent", "marcato", "swell", "fp", "sfz",
               "dim", "scoop", "fall", "bend_up", "trill", "vibrato", "slide")


@dataclass(frozen=True)
class Instrument:
    name: str
    family: str
    description: str
    synth: object                 # f(midi, gate, vel, r, art, cents) -> mono or stereo
    gm: tuple = None              # (bank, program) or (bank, program, key) for drum-kit sounds
    lo: int = 36
    hi: int = 96
    kind: str = "decay"           # decay (damped at the gate) | sustain | drum
    release: float = 0.25         # damper T60 (decay) or release time (sustain)
    arts: tuple = ()
    sampled: bool = True          # use the bank when it is available
    transpose: int = 0            # sampled path: semitones
    eq: tuple = ()                # sampled path: extra EQ bands (kind, fc, gain_db, q)
    vibrato: tuple = None         # sampled path: extra vibrato (depth, rate, delay)
    scoop: float = 0.0            # sampled path: cents scoop into every note
    trim_db: float = 0.0          # balance trim after loudness matching
    ref: int = None               # reference pitch for loudness matching

    @property
    def pitched(self):
        return self.kind != "drum" or self.name == "timpani"


# ------------------------------------------------------------------------------------------------ synth adapters
def _m(kind):
    return lambda m, g, v, r, a, c: synth.mallet(kind, m, g, v, r, cents=c)


def _p(kind):
    return lambda m, g, v, r, a, c: synth.plucked(kind, m, g, v, r, cents=c, let_ring=True)


def _w(kind):
    return lambda m, g, v, r, a, c: synth.wind(kind, m, g, v, r, cents=c)


def _b(kind, voices=1):
    def f(m, g, v, r, a, c):
        mode = {"swell": "swell", "sfz": "sfz", "fp": "sfz"}.get(a, "sustain")
        return synth.brass(kind, m, g, v, r, cents=c, voices=voices, mode=mode)
    return f


def _bow(voices, body="high", vib=14.0, release=0.35):
    def f(m, g, v, r, a, c):
        mode = {"trem": "tremolo", "spiccato": "spiccato", "swell": "swell", "sfz": "sfz", "fp": "sfz"}.get(a, "sustain")
        return synth.bowed(m, g, v, r, cents=c, voices=voices, body=body, vib_depth=vib, release=release, mode=mode)
    return f


def _drum(fn):
    return lambda m, g, v, r, a, c: fn(v, r)


def _pipa(m, g, v, r, a, c):
    return synth.pipa(m, g, v, r, cents=c, tremolo=(a == "trem"))


def _guzheng(m, g, v, r, a, c):
    press = [(0.12, 200.0, 0.12)] if a == "press" else None
    return synth.guzheng(m, g, v, r, cents=c, press=press)


def _guqin(m, g, v, r, a, c):
    return synth.guqin(m, g, v, r, cents=c, slide=(a == "slide_in"), harmonic=(a == "harmonic"))


def _dizi(m, g, v, r, a, c):
    return synth.dizi(m, g, v, r, cents=c, grace=[(200.0, 0.055)] if a == "grace" else None)


def _sheng(m, g, v, r, a, c):
    return synth.sheng(m, g, v, r, cents=c, chord=(0, 7) if a == "fifth" else (0,))


def _erhu(m, g, v, r, a, c):
    return synth.erhu(m, g, v, r, cents=c)


def _timpani(m, g, v, r, a, c):
    return perc.timpani(m, v, r, roll=g if a == "roll" else 0.0)


def _hit(fn, **kw):
    return lambda m, g, v, r, a, c: fn(v, r, **kw)


def _tom(pitch):
    return lambda m, g, v, r, a, c: perc.tom(v, r, pitch=pitch)


def _tanggu(m, g, v, r, a, c):
    return perc.tanggu(v, r, stroke=a if a in ("rim", "edge") else "center")


def _taiko(m, g, v, r, a, c):
    return perc.taiko(v, r, rim=(a == "rim"))


def _bo(m, g, v, r, a, c):
    return perc.bo(v, r, muted=(a in ("muted", "choke")))


def _crash(m, g, v, r, a, c):
    return perc.crash(v, r, choke=0.15 if a == "choke" else None)


def _cymbals(m, g, v, r, a, c):
    return perc.cymbals(v, r, choke=0.15 if a == "choke" else None)


def _swell(m, g, v, r, a, c):
    return perc.cymbal_swell(max(g, 0.5), v, r)


def _sleigh(m, g, v, r, a, c):
    return perc.sleigh_bells(v, r, dur=max(0.2, min(g, 2.0)))


# ------------------------------------------------------------------------------------------------ the catalog
_STRINGS_ARTS = ("pizz", "trem", "spiccato")
_GLISS = ("gliss", "gliss_down")
_DRUM_ARTS = ("roll", "flam")
_LIST = [
    # keys and mallets
    Instrument("piano", "keys", "concert grand piano", lambda m, g, v, r, a, c: synth.piano(m, g, v, r, cents=c),
               (0, 0), 21, 108, "decay", 0.25, ref=64),
    Instrument("celesta", "mallets", "celesta: soft struck steel plates", _m("celesta"), (0, 8), 60, 108, "decay", 0.3),
    Instrument("glockenspiel", "mallets", "glockenspiel: bright steel bars", _m("glockenspiel"), (0, 9), 72, 108, "decay",
               0.5, trim_db=-3.0),
    Instrument("music_box", "mallets", "music box comb", _m("music_box"), (0, 10), 60, 108, "decay", 0.6),
    Instrument("vibraphone", "mallets", "vibraphone with motor tremolo", _m("vibraphone"), (0, 11), 53, 89, "decay", 0.4),
    Instrument("marimba", "mallets", "rosewood marimba", _m("marimba"), (0, 12), 45, 96, "decay", 0.3),
    Instrument("xylophone", "mallets", "xylophone", _m("xylophone"), (0, 13), 65, 108, "decay", 0.15),
    Instrument("tubular_bells", "mallets", "tubular bells (chimes)", _m("tubular_bells"), (0, 14), 60, 77, "decay", 0.8),
    Instrument("kalimba", "mallets", "kalimba thumb piano", _m("kalimba"), (0, 108), 60, 96, "decay", 0.3),
    Instrument("steel_drums", "mallets", "steel pan", _m("steel_drums"), (0, 114), 55, 88, "decay", 0.3),
    Instrument("church_bells", "mallets", "church bells", lambda m, g, v, r, a, c: synth.bells(m, g, v, r), (8, 14),
               48, 84, "decay", 1.5),
    # plucked
    Instrument("harp", "plucked", "orchestral harp", _p("harp"), (0, 46), 24, 103, "decay", 0.6, ("harmonic",) + _GLISS),
    Instrument("nylon_guitar", "plucked", "classical (nylon) guitar", _p("nylon_guitar"), (0, 24), 40, 84, "decay", 0.2,
               ("harmonic",)),
    Instrument("steel_guitar", "plucked", "acoustic steel-string guitar", _p("steel_guitar"), (0, 25), 40, 86, "decay",
               0.18, ("harmonic",)),
    Instrument("ukulele", "plucked", "ukulele (re-entrant, bright and short)", _p("ukulele"), (8, 24), 60, 88, "decay",
               0.12),
    Instrument("mandolin", "plucked", "mandolin", _p("steel_guitar"), (16, 25), 55, 91, "decay", 0.15),
    Instrument("banjo", "plucked", "five-string banjo", _p("banjo"), (0, 105), 48, 86, "decay", 0.1),
    Instrument("acoustic_bass", "plucked", "upright bass, plucked", _p("acoustic_bass"), (0, 32), 28, 60, "decay", 0.15,
               ref=40, trim_db=1.5),
    Instrument("fingered_bass", "plucked", "electric bass, fingered", _p("fingered_bass"), (0, 33), 28, 64, "decay",
               0.12, ref=40, trim_db=1.0),
    # bowed strings
    Instrument("violin", "strings", "solo violin", _bow(1), (0, 40), 55, 100, "sustain", 0.3, _STRINGS_ARTS),
    Instrument("viola", "strings", "solo viola", _bow(1), (0, 41), 48, 88, "sustain", 0.3, _STRINGS_ARTS),
    Instrument("cello", "strings", "solo cello", _bow(1, vib=16.0), (0, 42), 36, 76, "sustain", 0.35, _STRINGS_ARTS,
               ref=50),
    Instrument("contrabass", "strings", "double bass, bowed", _bow(1, vib=10.0), (0, 43), 28, 60, "sustain", 0.35,
               _STRINGS_ARTS, ref=40, trim_db=1.0),
    Instrument("strings", "strings", "string ensemble, sustained", _bow(6, release=0.5), (0, 48), 28, 100, "sustain",
               0.5, _STRINGS_ARTS),
    Instrument("slow_strings", "strings", "string ensemble, slow attack", _bow(6, release=0.8), (0, 49), 28, 100,
               "sustain", 0.8, _STRINGS_ARTS),
    Instrument("tremolo_strings", "strings", "string ensemble, bowed tremolo",
               lambda m, g, v, r, a, c: synth.bowed(m, g, v, r, cents=c, voices=6, mode="tremolo"), (0, 44), 28, 100,
               "sustain", 0.4),
    Instrument("pizzicato_strings", "strings", "string ensemble, pizzicato",
               lambda m, g, v, r, a, c: synth.pizz_section(m, g, v, r, cents=c), (0, 45), 28, 96, "decay", 0.2),
    # woodwinds
    Instrument("flute", "woodwinds", "concert flute", _w("flute"), (0, 73), 60, 96, "sustain", 0.1),
    Instrument("piccolo", "woodwinds", "piccolo", _w("piccolo"), (0, 72), 74, 108, "sustain", 0.08, trim_db=-2.0),
    Instrument("recorder", "woodwinds", "alto recorder", _w("recorder"), (0, 74), 65, 96, "sustain", 0.07),
    Instrument("pan_flute", "woodwinds", "pan flute", _w("ocarina"), (0, 75), 60, 96, "sustain", 0.1),
    Instrument("tin_whistle", "woodwinds", "tin whistle", _w("recorder"), (24, 75), 74, 98, "sustain", 0.06),
    Instrument("clarinet", "woodwinds", "B-flat clarinet", _w("clarinet"), (0, 71), 50, 91, "sustain", 0.09),
    Instrument("oboe", "woodwinds", "oboe", _w("oboe"), (0, 68), 58, 91, "sustain", 0.09),
    Instrument("english_horn", "woodwinds", "english horn (cor anglais)", _w("oboe"), (0, 69), 52, 81, "sustain", 0.1),
    Instrument("bassoon", "woodwinds", "bassoon", _w("bassoon"), (0, 70), 34, 75, "sustain", 0.1, ref=50),
    Instrument("whistle", "woodwinds", "human whistling", _w("whistle"), (11, 78), 67, 98, "sustain", 0.08),
    Instrument("ocarina", "woodwinds", "ocarina", _w("ocarina"), (0, 79), 60, 91, "sustain", 0.1),
    Instrument("harmonica", "woodwinds", "diatonic harmonica", _w("harmonica"), (0, 22), 60, 96, "sustain", 0.08),
    Instrument("accordion", "woodwinds", "accordion (musette)",
               lambda m, g, v, r, a, c: synth.accordion(m, g, v, r, cents=c), (8, 21), 48, 89, "sustain", 0.1),
    # brass
    Instrument("french_horn", "brass", "french horns", _b("french_horn"), (0, 60), 34, 77, "sustain", 0.2, ref=58),
    Instrument("trumpet", "brass", "trumpet", _b("trumpet"), (0, 56), 54, 86, "sustain", 0.1, ("mute",)),
    Instrument("muted_trumpet", "brass", "trumpet with a straight mute", _b("muted_trumpet"), (0, 59), 54, 84, "sustain",
               0.08),
    Instrument("trombone", "brass", "tenor trombone", _b("trombone"), (0, 57), 34, 72, "sustain", 0.12, ref=53),
    Instrument("tuba", "brass", "tuba", _b("tuba"), (0, 58), 26, 58, "sustain", 0.14, ref=40, trim_db=1.0),
    Instrument("brass_section", "brass", "brass section (trumpets and trombones)", _b("trumpet", voices=3), (0, 61), 40,
               84, "sustain", 0.12),
    # voices and pads
    Instrument("choir_aahs", "voices", "mixed choir on 'aah'",
               lambda m, g, v, r, a, c: synth.choir(m, g, v, r, cents=c, vowel="a"), (0, 52), 40, 84, "sustain", 0.6),
    Instrument("voice_oohs", "voices", "soft voices on 'ooh'",
               lambda m, g, v, r, a, c: synth.choir(m, g, v, r, cents=c, vowel="u", breath=0.06), (0, 53), 45, 84,
               "sustain", 0.6),
    Instrument("warm_pad", "pads", "warm analogue pad", lambda m, g, v, r, a, c: synth.pad(m, g, v, r, cents=c), (0, 89),
               36, 96, "sustain", 1.2),
    # Chinese instruments
    Instrument("pipa", "chinese", "pipa: plucked lute (articulations: trem = lunzhi tremolo)", _pipa, None, 45, 93,
               "decay", 0.25, ("trem",), sampled=False),
    Instrument("guzheng", "chinese", "guzheng zither: bright plucks, press-bends, vibrato, glissandi", _guzheng, (0, 107),
               38, 96, "decay", 0.5, ("press",) + _GLISS, sampled=False),
    Instrument("dizi", "chinese", "dizi bamboo flute with membrane buzz", _dizi, None, 67, 98, "sustain", 0.1,
               ("grace",), sampled=False),
    Instrument("erhu", "chinese", "erhu two-string fiddle: nasal, singing, sliding", _erhu, (0, 40), 62, 93, "sustain",
               0.25, eq=(("hp", 250, 0, 0.7), ("peak", 600, -2.0, 1.0), ("peak", 1100, 3.0, 1.2), ("peak", 2300, 1.5, 1.4),
                         ("peak", 3500, -2.0, 1.0), ("highshelf", 6500, -6.0, 0.7)), vibrato=(22.0, 6.0, 0.18),
               scoop=-40.0),
    Instrument("suona", "chinese", "suona: bright, nasal festive shawm", _w("suona"), (0, 111), 64, 93, "sustain", 0.08,
               eq=(("peak", 1400, 3.0, 1.2), ("peak", 3000, 2.5, 1.4)), vibrato=(18.0, 6.2, 0.2), scoop=-70.0,
               trim_db=-1.0),
    Instrument("sheng", "chinese", "sheng mouth organ (articulation fifth: add the fifth)", _sheng, None, 55, 88,
               "sustain", 0.45, ("fifth",), sampled=False),
    Instrument("guqin", "chinese", "guqin silk zither (slide_in, harmonic)", _guqin, None, 36, 79, "decay", 1.0,
               ("slide_in", "harmonic"), sampled=False),
    Instrument("yangqin", "chinese", "yangqin hammered dulcimer", _m("yangqin"), (0, 15), 48, 96, "decay", 0.5),
    # Japanese instruments
    Instrument("koto", "japanese", "koto: thirteen-string zither", _p("guzheng"), (0, 107), 45, 93, "decay", 0.5),
    Instrument("shamisen", "japanese", "shamisen: three-string lute with a snapping plectrum attack", _p("banjo"),
               (0, 106), 48, 88, "decay", 0.15),
    Instrument("shakuhachi", "japanese", "shakuhachi: breathy end-blown bamboo flute", _w("shakuhachi"), (0, 77),
               60, 88, "sustain", 0.12, vibrato=(16.0, 4.6, 0.4), scoop=-50.0),
    # drum kit
    Instrument("kick", "drums", "kick drum", _drum(perc.kick), (128, 0, 36), kind="drum", arts=_DRUM_ARTS),
    Instrument("snare", "drums", "snare drum", _drum(perc.snare), (128, 0, 38), kind="drum", arts=_DRUM_ARTS),
    Instrument("brush_snare", "drums", "snare with brushes", _hit(perc.snare, brush=True), (128, 40, 38), kind="drum"),
    Instrument("side_stick", "drums", "snare side stick", _drum(perc.side_stick), (128, 0, 37), kind="drum"),
    Instrument("clap", "drums", "hand claps", _hit(perc.clap, people=3), (128, 0, 39), kind="drum"),
    Instrument("hihat_closed", "drums", "closed hi-hat", _hit(perc.hihat, kind="closed"), (128, 0, 42), kind="drum",
               trim_db=-4.0),
    Instrument("hihat_pedal", "drums", "pedal hi-hat", _hit(perc.hihat, kind="pedal"), (128, 0, 44), kind="drum",
               trim_db=-4.0),
    Instrument("hihat_open", "drums", "open hi-hat", _hit(perc.hihat, kind="open"), (128, 0, 46), kind="drum",
               trim_db=-4.0),
    Instrument("tom_low", "drums", "floor tom", _tom(0.15), (128, 0, 43), kind="drum", arts=_DRUM_ARTS),
    Instrument("tom_mid", "drums", "mid tom", _tom(0.5), (128, 0, 47), kind="drum", arts=_DRUM_ARTS),
    Instrument("tom_high", "drums", "high tom", _tom(0.85), (128, 0, 50), kind="drum", arts=_DRUM_ARTS),
    Instrument("ride", "drums", "ride cymbal", _drum(perc.ride), (128, 0, 51), kind="drum", trim_db=-4.0),
    Instrument("ride_bell", "drums", "ride cymbal bell", _hit(perc.ride, bell=True), (128, 0, 53), kind="drum",
               trim_db=-4.0),
    Instrument("crash", "drums", "crash cymbal (choke)", _crash, (128, 0, 49), kind="drum", arts=("choke",),
               trim_db=-3.0),
    Instrument("tambourine", "drums", "tambourine", _drum(perc.tambourine), (128, 0, 54), kind="drum", trim_db=-3.0),
    Instrument("shaker", "drums", "shaker", _drum(perc.shaker), (128, 0, 82), kind="drum", trim_db=-5.0),
    Instrument("cowbell", "drums", "cowbell", _drum(perc.cowbell), (128, 0, 56), kind="drum", trim_db=-4.0),
    Instrument("woodblock", "drums", "wood block, high", _drum(perc.woodblock), (128, 0, 76), kind="drum", trim_db=-3.0),
    Instrument("woodblock_low", "drums", "wood block, low", _hit(perc.woodblock, high=False), (128, 0, 77), kind="drum",
               trim_db=-3.0),
    Instrument("triangle", "drums", "triangle (articulation muted)", _drum(perc.triangle), (128, 0, 81), kind="drum",
               arts=("muted", "roll"), trim_db=-6.0),
    Instrument("castanets", "drums", "castanets", _drum(perc.castanets), (128, 0, 85), kind="drum", trim_db=-3.0),
    # orchestral percussion
    Instrument("timpani", "percussion", "timpani (pitched; articulation roll)", _timpani, (0, 47), 38, 57, "drum",
               arts=("roll",), ref=45),
    Instrument("bass_drum", "percussion", "concert bass drum", _drum(perc.bass_drum), (128, 48, 36), kind="drum",
               arts=("roll",)),
    Instrument("cymbals", "percussion", "orchestral clash cymbals (choke)", _cymbals, (128, 48, 59), kind="drum",
               arts=("choke",), trim_db=-3.0),
    Instrument("cymbal_swell", "percussion", "suspended-cymbal roll swelling to its peak at the end of the gate",
               _swell, None, kind="drum", sampled=False, trim_db=-3.0),
    Instrument("sleigh_bells", "percussion", "sleigh bells, shaken for the gate", _sleigh, (128, 0, 83), kind="drum",
               trim_db=-4.0),
    Instrument("taiko", "percussion", "taiko drum (articulation rim)", _taiko, None, kind="drum", arts=("rim", "roll"),
               sampled=False),
    # Chinese percussion
    Instrument("daluo", "chinese_percussion", "big gong: pitch falls after the strike", _hit(perc.daluo), None,
               kind="drum", sampled=False, trim_db=-2.0),
    Instrument("xiaoluo", "chinese_percussion", "small opera gong: pitch rises after the strike", _hit(perc.xiaoluo), None,
               kind="drum", sampled=False, trim_db=-3.0),
    Instrument("bo", "chinese_percussion", "Chinese cymbals (articulation muted)", _bo, None, kind="drum",
               arts=("muted",), sampled=False, trim_db=-3.0),
    Instrument("tanggu", "chinese_percussion", "hall drum (articulations edge, rim, roll)", _tanggu, None, kind="drum",
               arts=("edge", "rim", "roll"), sampled=False),
    Instrument("bangzi", "chinese_percussion", "hardwood clapper", _hit(perc.bangzi), None, kind="drum", sampled=False,
               trim_db=-4.0),
    Instrument("muyu", "chinese_percussion", "wooden fish", _hit(perc.muyu), None, kind="drum", sampled=False,
               trim_db=-3.0),
]
INSTRUMENTS = {i.name: i for i in _LIST}
ALIASES = {"string_ensemble": "strings", "strings_ensemble": "strings", "contra_bass": "contrabass",
           "double_bass": "contrabass", "upright_bass": "acoustic_bass", "bass": "fingered_bass", "horn": "french_horn",
           "horns": "french_horn", "choir": "choir_aahs", "oohs": "voice_oohs", "pad": "warm_pad", "pizz": "pizzicato_strings",
           "gong": "daluo", "big_gong": "daluo", "small_gong": "xiaoluo", "chinese_cymbals": "bo", "nao": "bo",
           "dulcimer": "yangqin", "music box": "music_box", "hihat": "hihat_closed", "concert_bass_drum": "bass_drum"}


def get(name):
    key = ALIASES.get(name, name)
    if key not in INSTRUMENTS:
        raise KeyError(f"Unknown instrument {name!r}. Known: {', '.join(sorted(INSTRUMENTS))}")
    return INSTRUMENTS[key]


def names(family=None):
    return [i.name for i in _LIST if family is None or i.family == family]


def _use_bank(inst, force=None):
    if force == "synth" or inst.gm is None or not inst.sampled:
        return None
    sf = soundfont.default()
    if sf is None:
        if force == "sampled":
            raise RuntimeError("No sound bank is available for sampled playback")
        return None
    return sf if sf._resolve(*inst.gm[:2]) is not None else None


def source(name):
    """'sampled' or 'synthesized' for this process"""
    return "sampled" if _use_bank(get(name)) is not None else "synthesized"


def catalog():
    out = []
    for i in _LIST:
        arts = list(COMMON_ARTS if i.kind != "drum" else ("normal", "accent")) + list(i.arts)
        out.append({"name": i.name, "family": i.family, "description": i.description, "source": source(i.name),
                    "range": [i.lo, i.hi] if i.pitched else None, "articulations": arts})
    return out


# ------------------------------------------------------------------------------------------------ rendering helpers
_CACHE = OrderedDict()
_CACHED = [0]
_LEVELS = {}


def _cache_get(key):
    hit = _CACHE.get(key)
    if hit is not None:
        _CACHE.move_to_end(key)
    return hit


def _cache_put(key, y):
    y = y.astype(np.float32)
    _CACHE[key] = y
    _CACHED[0] += y.size
    while _CACHED[0] > CACHE_SAMPLES and len(_CACHE) > 1:
        _, old = _CACHE.popitem(last=False)
        _CACHED[0] -= old.size
    return y


def _vel01(v):
    v = float(v)
    return float(np.clip(v / 127.0 if v > 1.0 else v, 0.0, 1.0))


def _midi_vel(v):
    return int(np.clip(round(1 + 126 * v), 1, 127))


def _bend_curve(bend, n):
    """scalar | array | [(t, cents), ...] -> array(n) or None"""
    if bend is None:
        return None
    if np.ndim(bend) == 0:
        return np.full(n, float(bend))
    b = np.asarray(bend, dtype=np.float64)
    if b.ndim == 2 and b.shape[1] == 2:
        return np.interp(np.arange(n) / SR, b[:, 0], b[:, 1])
    return synth._cents(b, n)


def _gesture(art, gate, n, opts, pitch):
    """pitch gesture of an articulation in cents (array(n)) or None"""
    t = np.arange(n) / SR
    c = None
    if art == "scoop":
        c = -150.0 * (1.0 - dsp.smoothstep(t / 0.12))
    elif art == "fall":
        c = -600.0 * dsp.smoothstep((t - gate * 0.55) / max(gate * 0.45, 0.05)) ** 1.5
    elif art == "bend_up":
        c = 200.0 * dsp.smoothstep((t - gate * 0.3) / max(gate * 0.5, 0.05))
    elif art == "trill":
        step = float(opts.get("trill_step", 2.0)) * 100.0
        sq = (np.floor(t * 2.0 * float(opts.get("trill_rate", 7.5))) % 2.0)
        c = step * dsp.onepole(sq, 60.0)
    elif art == "slide" or opts.get("slide_from") is not None:
        src = opts.get("slide_from", pitch - 2.0)
        st = float(opts.get("slide_time", 0.12))
        c = 100.0 * (float(src) - float(pitch)) * (1.0 - dsp.smoothstep(t / max(st, 1e-3)))
    extra = _bend_curve(opts.get("bend"), n)
    if extra is not None:
        c = extra if c is None else c + extra
    return c


def _dynamics(art, gate, n):
    """amplitude shape of an articulation over the gate (array(n)) or None"""
    if art not in ("swell", "fp", "sfz", "dim"):
        return None
    t = np.arange(n) / SR
    g = max(gate, 0.05)
    if art == "swell":
        return 0.25 + 0.75 * dsp.smoothstep(t / (g * 0.9))
    if art == "dim":
        return 1.0 - 0.65 * dsp.smoothstep(t / g)
    lo = 0.3 if art == "fp" else 0.2
    return np.where(t < 0.08, 1.0, lo + (1.0 - lo) * np.exp(-(t - 0.08) / 0.12)) * (1.0 + 0.4 * dsp.smoothstep((t - g * 0.5) / g))


def _short_term_db(y):
    m = dsp.as_stereo(y)
    w = n_of(0.05)
    k = m.shape[-1] // w
    if k < 1:
        return float(dsp.lin2db(dsp.rms(m) + 1e-12))
    e = np.mean(m[:, :k * w].reshape(2, k, w) ** 2, axis=(0, 2))
    return float(10.0 * np.log10(np.max(e) + 1e-20))


def _shape_decay(y, gate, t60):
    """damper at the gate, truncated once it has died away"""
    n = y.shape[-1]
    k = n_of(gate)
    if k >= n:
        return y
    end = min(n, k + n_of(t60 * 1.05) + 8)
    y = y[..., :end].astype(np.float64)
    tt = np.arange(end - k) / SR
    y[..., k:] *= np.exp(-dsp.LN1000 * tt / max(t60, 1e-3))
    return y


def _loop_extend(y, n_need, start, xfade):
    """lengthen a sustained tone by crossfade-looping its tail from `start` (samples) on"""
    seg = y[..., start:]
    out = y
    xf = min(xfade, seg.shape[-1] // 3)
    w = np.sin(0.5 * np.pi * np.linspace(0.0, 1.0, xf))
    while out.shape[-1] < n_need:
        head = out[..., :-xf]
        tail = out[..., -xf:] * w[::-1] + seg[..., :xf] * w
        out = np.concatenate([head, tail, seg[..., xf:]], axis=-1)
    return out


def _shape_sustain(y, gate, release, body_end):
    """take the first `gate` seconds of a long sustained render and release it with a cosine fade"""
    k = n_of(gate)
    r = max(8, n_of(release))
    need = k + r
    if need > body_end:
        y = _loop_extend(y[..., :body_end], need, int(body_end * 0.45), n_of(0.25))
    y = np.array(y[..., :need], dtype=np.float64)
    if y.shape[-1] < need:
        y = dsp.pad_to(y, need)
    y[..., k:need] *= 0.5 + 0.5 * np.cos(np.pi * np.linspace(0.0, 1.0, need - k))
    return y


# ------------------------------------------------------------------------------------------------ sources
def _norm_layer(y, layer):
    """normalise a render to REF_DB short-term RMS at velocity 0.8 (velocity law: amplitude ~ velocity^2)"""
    return y * dsp.db2lin(REF_DB - _short_term_db(y)) * (layer / 0.8) ** 2


def _synth_raw(inst, midi, gate, vel, art, seed, cents):
    """synthesized note (stereo), velocity law vel^2 applied; cached by pitch / velocity layer when possible"""
    if inst.kind == "drum":
        layer = min(LAYERS, key=lambda v: abs(v - vel))
        rr = int(seed) % 2
        key = (inst.name, round(float(midi), 2) if inst.pitched else None, layer, art, rr,
               round(gate, 2) if art in ("roll",) or inst.name in ("cymbal_swell", "sleigh_bells") else None)
        y = _cache_get(key)
        if y is None:
            y = _cache_put(key, _norm_layer(dsp.as_stereo(inst.synth(midi, gate, layer, dsp.rng(inst.name, key), art,
                                                                     None)), layer))
        return y.astype(np.float64) * (vel / layer) ** 2
    if art == "spiccato" and cents is None:
        layer = min(LAYERS_SUSTAIN, key=lambda v: abs(v - vel))
        key = (inst.name, round(float(midi), 2), layer, "spiccato")
        y = _cache_get(key)
        if y is None:
            y = inst.synth(midi, 0.12, layer, dsp.rng(inst.name, key), "spiccato", None)
            y = _cache_put(key, _norm_layer(dsp.as_stereo(y) if y.ndim == 2 else dsp.pan_mono(y, 0.0), layer))
        return y.astype(np.float64) * (vel / layer) ** 2
    if cents is not None or art in ("trem", "press", "grace", "slide_in", "harmonic", "fifth"):
        decay = inst.kind == "decay" and art != "trem"
        y = inst.synth(midi, 60.0 if decay else gate, vel, dsp.rng(inst.name, round(float(midi), 3), seed, art), art,
                       cents)
        y = _norm_layer(dsp.as_stereo(y) if y.ndim == 2 else dsp.pan_mono(y, 0.0), vel)
        if decay:
            y = _shape_decay(y, gate, inst.release)
        return y
    layer = min(LAYERS if inst.kind == "decay" else LAYERS_SUSTAIN, key=lambda v: abs(v - vel))
    rr = int(seed) % (2 if inst.kind == "decay" else 1)
    key = (inst.name, round(float(midi), 2), layer, rr)
    y = _cache_get(key)
    if y is None:
        long_gate = 60.0 if inst.kind == "decay" else LONG_SUSTAIN
        y = inst.synth(midi, long_gate, layer, dsp.rng(inst.name, key), "normal", None)
        y = _cache_put(key, _norm_layer(dsp.as_stereo(y) if y.ndim == 2 else dsp.pan_mono(y, 0.0), layer))
    if inst.kind == "decay":
        out = _shape_decay(y, gate, inst.release if art not in ("staccato", "staccatissimo") else min(inst.release, 0.12))
    else:
        out = _shape_sustain(y, gate, inst.release, min(y.shape[-1], n_of(LONG_SUSTAIN)))
    return out * (vel / layer) ** 2


def _sampled_raw(inst, sf, midi, gate, vel, art, seed, cents, opts):
    if inst.kind == "drum" and len(inst.gm) > 2:
        bank, prog, key = inst.gm
        y = sf.render_note(bank, prog, key, _midi_vel(vel), max(gate, 0.3))
        return y
    bank, prog = inst.gm[:2]
    if art == "pizz" and inst.family == "strings":
        prog, bank = 45, 0
    elif art == "trem" and inst.family == "strings":
        prog, bank = 44, 0
    elif art == "mute" and inst.name == "trumpet":
        prog = 59
    elif art == "harmonic" and inst.name in ("nylon_guitar", "steel_guitar"):
        prog, bank = 31, 0
    key = float(midi) + inst.transpose
    release = None
    if art in ("staccato", "staccatissimo", "spiccato"):
        release = 0.06 if inst.kind == "sustain" else None
    c = cents
    if inst.scoop and inst.kind == "sustain" and art not in ("staccato", "staccatissimo"):
        t = np.arange(len(c) if c is not None else n_of(gate + 2.0)) / SR
        sc = inst.scoop * np.exp(-t / 0.05)
        c = sc if c is None else c + sc
    vib = opts.get("vibrato", inst.vibrato if inst.kind == "sustain" else None)
    y = sf.render_note(bank, prog, key, _midi_vel(vel), gate, release, bend=c, vibrato=vib)
    if inst.eq:
        y = dsp.eq_chain(y, list(inst.eq))
    return y


def _sampled_gain_db(inst, sf, vel):
    """dB correction for a sampled note: the bank's level at each velocity layer of a reference note is measured once,
    and notes are brought to REF_DB at velocity 0.8 with amplitude ~ velocity^2 (timbre still follows the bank)"""
    key = (inst.name, id(sf))
    if key not in _LEVELS:
        ref = inst.ref if inst.ref is not None else int(round((inst.lo + inst.hi) / 2))
        measured = np.array([_short_term_db(_sampled_raw(inst, sf, ref, 1.0, v, "normal", 0, None, {})) for v in LAYERS])
        law = REF_DB + 40.0 * np.log10(np.array(LAYERS) / 0.8)
        _LEVELS[key] = law - measured
    return float(np.interp(vel, LAYERS, _LEVELS[key]))


def _gliss(inst, pitch, duration, velocity, seed, opts, up=True):
    offsets = opts.get("scale", (0, 2, 4, 7, 9))
    sweep = float(opts.get("sweep", 0.4))
    span = int(opts.get("span", 12))
    notes = [pitch + 12 * o + s for o in range(-3, 1) for s in offsets]
    notes = sorted({m for m in notes if pitch - span <= m < pitch})
    seq = notes + [pitch] if up else [pitch] + notes[::-1]
    step = sweep / max(1, len(seq) - 1)
    clips = []
    for i, m in enumerate(seq):
        target = (i == len(seq) - 1) if up else (i == 0)
        v = velocity if target else velocity * (0.5 + 0.4 * (i / len(seq) if up else 1 - i / len(seq)))
        d = duration if target else max(0.3, sweep)
        clips.append((n_of(i * step), play(inst.name, m, d, v, "normal", seed + i, source=opts.get("source"))))
    n = max(s + c.shape[-1] for s, c in clips)
    out = np.zeros((2, n))
    for s, c in clips:
        out[:, s:s + c.shape[-1]] += c
    return out


def _roll(inst, pitch, duration, velocity, seed, opts):
    """single-stroke roll over the gate, swelling into its last stroke"""
    rate = float(opts.get("roll_rate", 16.0))
    times = np.arange(0.0, max(duration, 1.0 / rate), 1.0 / rate)
    r = dsp.rng("roll", inst.name, seed)
    clips = []
    for i, ts in enumerate(times):
        u = ts / max(duration, 1e-3)
        v = velocity * (0.4 + 0.6 * u ** 1.2) * r.uniform(0.85, 1.05)
        clips.append((n_of(ts + r.normal(0, 0.003) if i else 0.0), play(inst.name, pitch, 0.2, v, "normal", seed + i,
                                                                      source=opts.get("source"))))
    n = max(s + c.shape[-1] for s, c in clips)
    out = np.zeros((2, n))
    for s, c in clips:
        out[:, max(0, s):max(0, s) + c.shape[-1]] += c
    return out


# ------------------------------------------------------------------------------------------------ the note call
def play(name, pitch=60, duration=0.5, velocity=0.8, articulation="normal", seed=0, **opts):
    """Render one note of a named instrument (stereo, onset at sample 0, loudness-matched)."""
    inst = get(name)
    art = articulation or "normal"
    vel = _vel01(velocity)
    duration = max(0.02, float(duration))
    pitch = float(pitch if pitch is not None else (inst.ref or 60))
    if inst.kind != "drum" and inst.pitched:
        while pitch < inst.lo - 12:
            pitch += 12
        while pitch > inst.hi + 12:
            pitch -= 12
    if art in ("gliss", "gliss_down") and inst.kind != "drum":
        return _gliss(inst, pitch, duration, vel, seed, opts, up=(art == "gliss"))
    if art == "roll" and inst.name not in ("timpani",) and inst.kind == "drum" and inst.name != "cymbal_swell":
        return _roll(inst, pitch, duration, vel, seed, opts)
    if art == "flam" and inst.kind == "drum":
        grace = play(name, pitch, 0.1, vel * 0.55, "normal", seed + 1, source=opts.get("source"))
        main = play(name, pitch, duration, vel, "normal", seed, source=opts.get("source"))
        s = n_of(0.022)
        out = np.zeros((2, max(grace.shape[-1], s + main.shape[-1])))
        out[:, :grace.shape[-1]] += grace
        out[:, s:s + main.shape[-1]] += main
        return out
    if art == "pizz" and inst.family == "strings" and inst.name != "pizzicato_strings":
        return play("pizzicato_strings", pitch, duration, velocity, "normal", seed, **opts)
    if art == "trem" and inst.family == "strings" and _use_bank(inst, opts.get("source")) is None and \
            inst.name not in ("tremolo_strings",):
        return play("tremolo_strings", pitch, duration, velocity, "normal", seed, **opts)
    if art == "mute" and inst.name == "trumpet" and _use_bank(inst, opts.get("source")) is None:
        return play("muted_trumpet", pitch, duration, velocity, "normal", seed, **opts)
    gate = duration
    if art == "staccato":
        gate = min(duration * 0.5, 0.2)
    elif art == "staccatissimo":
        gate = min(duration * 0.3, 0.09)
    elif art == "legato":
        gate = duration + 0.04
    elif art == "marcato":
        gate = duration * 0.75
    if art in ("accent", "sfz"):
        vel = min(1.0, vel * 1.15)
    elif art == "marcato":
        vel = min(1.0, vel * 1.22)
    if art == "harmonic" and inst.family == "plucked":
        pitch += 12.0
        vel *= 0.6
    n_guess = n_of(gate + 2.0)
    cents = _gesture(art, gate, n_guess, opts, pitch) if inst.pitched else None
    vib = opts.get("vibrato")
    if art == "vibrato" and vib is None:
        vib = (32.0, 5.6, 0.12)
    if vib is not None and inst.pitched:
        t = np.arange(n_guess) / SR
        depth, rate, delay = (list(vib) + [0.2])[:3]
        v_c = depth * dsp.smoothstep((t - delay) / 0.3) * np.sin(2 * np.pi * rate * t)
        cents = v_c if cents is None else cents + v_c
    sf = _use_bank(inst, opts.get("source"))
    if sf is not None:
        y = _sampled_raw(inst, sf, pitch, gate, vel, art, seed, cents, {k: v for k, v in opts.items() if k != "vibrato"})
    else:
        y = _synth_raw(inst, pitch, gate, vel, art, seed, cents)
    y = y * dsp.db2lin((_sampled_gain_db(inst, sf, vel) if sf is not None else 0.0) + inst.trim_db)
    shape = _dynamics(art, gate, y.shape[-1])
    if shape is not None:
        y = y * shape
    a = min(y.shape[-1] // 4, n_of(0.001 if inst.kind != "drum" else 0.0004))
    if a > 1:
        y[:, :a] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(a) / a)       # a struck or plucked onset still takes ~1 ms
    k = min(y.shape[-1], n_of(0.004))
    if k > 1:
        y[:, -k:] *= np.linspace(1.0, 0.0, k)
    return y


def chord(name, pitches, duration, velocity=0.7, articulation="normal", seed=0, spread=0.0, **opts):
    """several notes of one instrument summed; spread = seconds between successive notes (strum / roll)"""
    clips = []
    for i, p in enumerate(pitches):
        clips.append((n_of(i * spread), play(name, p, max(0.02, duration - i * spread), velocity, articulation, seed + i,
                                             **opts)))
    n = max(s + c.shape[-1] for s, c in clips)
    out = np.zeros((2, n))
    for s, c in clips:
        out[:, s:s + c.shape[-1]] += c
    return out
