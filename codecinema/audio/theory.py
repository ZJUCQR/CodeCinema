"""
codecinema.audio.theory -- music written as text: pitches, durations, modes, chord symbols and voice leading
(standard library only).

Melody notation (C4 = MIDI 60), tokens separated by spaces, '|' marks bar lines:
    D5/q  F#5/e.  Bb4/h  r/q  A4/1.5  ~A4/q
    pitch     letter + optional accidentals (# b x bb, also unicode sharps / flats) + octave; 'r' is a rest
    /dur      w h q e s t (whole .. 32nd, in quarter-note beats 4 2 1 .5 .25 .125), '.' dotted, '..' double
              dotted, a trailing '3' for a triplet value (e3 = 1/3 beat), or a number of beats (/1.5)
              the duration carries over when omitted (the first default is a quarter)
    ~         prefix: tie to the previous note (same pitch) or, with a new pitch, slide into it (portamento)
    marks     suffixes after the duration: ' staccato  > accent  _ tenuto  ^ marcato
    bars      every bar between the first and the last must fill the meter; a short first bar is a pickup
Chords: bars separated by '|'; chord slots inside a bar share it equally; '%' repeats the previous chord and '.'
or '-' holds it.  Symbols: C Cm C7 Cmaj7 Cm7 C6 Cm6 Csus2 Csus4 C7sus4 Cdim Cdim7 Cm7b5 Caug Cadd9 C9 Cmaj9 Cm9 C5
with an optional slash bass (A/C#), or roman numerals in the key (I ii iii IV V vi vii°, V7, ii7, bVII, IV/5 ...).
Modes: major minor harmonic_minor dorian mixolydian lydian phrygian, the Chinese pentatonic modes gong shang jue
zhi yu, and the Japanese scales in (= miyako_bushi) yo hirajoshi (the key names the tonic of the mode).
"""
import itertools
import re
from dataclasses import dataclass, field

NOTE_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
PC_NAME = ("C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")
DURATIONS = {"w": 4.0, "h": 2.0, "q": 1.0, "e": 0.5, "s": 0.25, "t": 0.125}

MODES = {
    "major": (0, 2, 4, 5, 7, 9, 11), "ionian": (0, 2, 4, 5, 7, 9, 11),
    "minor": (0, 2, 3, 5, 7, 8, 10), "aeolian": (0, 2, 3, 5, 7, 8, 10),
    "harmonic_minor": (0, 2, 3, 5, 7, 8, 11), "dorian": (0, 2, 3, 5, 7, 9, 10),
    "mixolydian": (0, 2, 4, 5, 7, 9, 10), "lydian": (0, 2, 4, 6, 7, 9, 11), "phrygian": (0, 1, 3, 5, 7, 8, 10),
    "gong": (0, 2, 4, 7, 9), "shang": (0, 2, 5, 7, 10), "jue": (0, 3, 5, 8, 10), "zhi": (0, 2, 5, 7, 9),
    "yu": (0, 3, 5, 7, 10), "pentatonic": (0, 2, 4, 7, 9), "minor_pentatonic": (0, 3, 5, 7, 10),
    "in": (0, 1, 5, 7, 8), "miyako_bushi": (0, 1, 5, 7, 8), "yo": (0, 2, 5, 7, 9), "hirajoshi": (0, 2, 3, 7, 8),
}
# heptatonic parent of each pentatonic mode (used for harmony)
PARENT = {"gong": "major", "pentatonic": "major", "shang": "dorian", "jue": "phrygian", "zhi": "mixolydian",
          "yu": "minor", "minor_pentatonic": "minor", "in": "phrygian", "miyako_bushi": "phrygian", "yo": "mixolydian",
          "hirajoshi": "minor"}
PENTATONIC = ("gong", "shang", "jue", "zhi", "yu", "pentatonic", "minor_pentatonic")
JAPANESE = ("in", "miyako_bushi", "yo", "hirajoshi")

QUALITIES = {
    "": (0, 4, 7), "maj": (0, 4, 7), "M": (0, 4, 7), "m": (0, 3, 7), "min": (0, 3, 7), "-": (0, 3, 7),
    "7": (0, 4, 7, 10), "maj7": (0, 4, 7, 11), "M7": (0, 4, 7, 11), "Δ7": (0, 4, 7, 11), "Δ": (0, 4, 7, 11),
    "m7": (0, 3, 7, 10), "min7": (0, 3, 7, 10), "-7": (0, 3, 7, 10), "mmaj7": (0, 3, 7, 11),
    "6": (0, 4, 7, 9), "m6": (0, 3, 7, 9), "sus2": (0, 2, 7), "sus4": (0, 5, 7), "sus": (0, 5, 7),
    "7sus4": (0, 5, 7, 10), "7sus": (0, 5, 7, 10), "dim": (0, 3, 6), "°": (0, 3, 6), "o": (0, 3, 6),
    "dim7": (0, 3, 6, 9), "°7": (0, 3, 6, 9), "o7": (0, 3, 6, 9), "m7b5": (0, 3, 6, 10), "ø": (0, 3, 6, 10),
    "ø7": (0, 3, 6, 10), "aug": (0, 4, 8), "+": (0, 4, 8), "add9": (0, 4, 7, 14), "add2": (0, 2, 4, 7),
    "madd9": (0, 3, 7, 14), "9": (0, 4, 7, 10, 14), "maj9": (0, 4, 7, 11, 14), "m9": (0, 3, 7, 10, 14),
    "5": (0, 7), "6/9": (0, 4, 7, 9, 14), "69": (0, 4, 7, 9, 14),
}
ROMAN = {"i": 0, "ii": 1, "iii": 2, "iv": 3, "v": 4, "vi": 5, "vii": 6}


def _acc(s):
    return s.count("#") + s.count("♯") + 2 * s.count("x") - s.count("b") - s.count("♭")


def pitch_class(name):
    """'F#' -> 6, 'Bb' -> 10"""
    m = re.fullmatch(r"([A-Ga-g])([#b♯♭x]*)", name.strip())
    if not m:
        raise ValueError(f"Not a note name: {name!r}")
    return (NOTE_PC[m.group(1).upper()] + _acc(m.group(2))) % 12


def parse_pitch(tok):
    """'F#5' -> 78 (C4 = 60)"""
    m = re.fullmatch(r"([A-Ga-g])([#b♯♭x]*)(-?\d)", tok.strip())
    if not m:
        raise ValueError(f"Not a pitch: {tok!r} (use a letter, accidentals and an octave, e.g. F#5)")
    return 12 * (int(m.group(3)) + 1) + NOTE_PC[m.group(1).upper()] + _acc(m.group(2))


def pitch_name(midi):
    midi = int(round(midi))
    return f"{PC_NAME[midi % 12]}{midi // 12 - 1}"


def parse_duration(s):
    """'q' -> 1.0, 'e.' -> 0.75, 'e3' -> 1/3, '1.5' -> 1.5 (quarter-note beats)"""
    s = s.strip()
    try:
        return float(s)
    except ValueError:
        pass
    m = re.fullmatch(r"([whqest])(\.{0,2})(3?)", s)
    if not m:
        raise ValueError(f"Not a duration: {s!r} (w h q e s t, dotted, triplet '3', or beats)")
    d = DURATIONS[m.group(1)]
    d *= {0: 1.0, 1: 1.5, 2: 1.75}[len(m.group(2))]
    if m.group(3):
        d *= 2.0 / 3.0
    return d


def meter_beats(meter):
    """beats (quarter notes) per bar and the compound flag: 4 -> (4, False), '6/8' -> (3, True)"""
    if isinstance(meter, (int, float)):
        return float(meter), False
    m = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", str(meter))
    if not m:
        return float(meter), False
    num, den = int(m.group(1)), int(m.group(2))
    beats = num * 4.0 / den
    return beats, den == 8 and num % 3 == 0


# ------------------------------------------------------------------------------------------------ melody
@dataclass
class Note:
    beat: float                    # onset in beats from the start of the melody
    dur: float                     # beats
    pitch: float = None            # MIDI, None = rest
    art: str = "normal"
    slide: bool = False            # slide (portamento) from the previous note

    @property
    def end(self):
        return self.beat + self.dur


def parse_melody(text, beats_per_bar=None):
    """notation -> [Note] (ties merged).  With beats_per_bar, bar lines are checked: every bar between the first
    and the last must fill the meter; a short first bar is a pickup (it ends where bar 1 begins)."""
    notes = []
    dur = 1.0
    pos = 0.0
    marks = {"'": "staccato", ">": "accent", "_": "tenuto", "^": "marcato"}
    text = str(text).replace("\n", " ")
    if beats_per_bar:
        bars = [b for b in text.split("|")]
        sums = []
        d = 1.0
        for b in bars:
            total = 0.0
            for tok in b.split():
                tok = tok.lstrip("~").rstrip("'>_^")
                if "/" in tok:
                    d = parse_duration(tok.split("/", 1)[1])
                total += d
            sums.append(total)
        for i, total in enumerate(sums):
            if 0 < i < len(sums) - 1 and abs(total - beats_per_bar) > 1e-6:
                raise ValueError(f"melody bar {i + 1} lasts {total:g} beats; the meter has {beats_per_bar:g}")
        if len(sums) > 1 and 0 < sums[0] < beats_per_bar - 1e-6:
            pos = beats_per_bar - sums[0]            # pickup: right-align the first bar
    for tok in text.split():
        if tok == "|":
            continue
        tok = tok.strip("|")
        if not tok:
            continue
        tie = tok.startswith("~")
        tok = tok.lstrip("~")
        art = "normal"
        while tok and tok[-1] in marks:
            art = marks[tok[-1]]
            tok = tok[:-1]
        if "/" in tok:
            p, d = tok.split("/", 1)
            dur = parse_duration(d)
        else:
            p = tok
        pitch = None if p.lower() in ("r", "rest", "-") else parse_pitch(p)
        if tie and notes and notes[-1].pitch is not None and pitch == notes[-1].pitch and abs(notes[-1].end - pos) < 1e-6:
            notes[-1].dur += dur
        else:
            notes.append(Note(pos, dur, pitch, art, slide=tie and pitch is not None))
        pos += dur
    return notes


# ------------------------------------------------------------------------------------------------ keys and modes
@dataclass(frozen=True)
class Key:
    tonic: int                     # pitch class
    mode: str = "major"

    @property
    def scale(self):
        return MODES[self.mode]

    @property
    def harmony_mode(self):
        return PARENT.get(self.mode, self.mode)

    @property
    def harmony_scale(self):
        return MODES[self.harmony_mode]

    @property
    def minorish(self):
        sc = self.harmony_scale
        return sc[2] == 3

    def pcs(self, harmony=False):
        sc = self.harmony_scale if harmony else self.scale
        return [(self.tonic + s) % 12 for s in sc]

    def degree_pc(self, degree, harmony=True):
        sc = self.harmony_scale if harmony else self.scale
        return (self.tonic + sc[degree % len(sc)]) % 12

    def contains(self, midi):
        return (int(round(midi)) - self.tonic) % 12 in self.scale

    def snap(self, midi, direction=0):
        """nearest scale pitch (direction -1 / +1 to search only down / up)"""
        m = int(round(midi))
        for d in range(0, 12):
            for s in ((0,) if d == 0 else ((d, -d) if direction == 0 else ((d,) if direction > 0 else (-d,)))):
                if self.contains(m + s):
                    return m + s
        return m

    def step(self, midi, steps):
        """move `steps` scale degrees from a scale pitch"""
        m = self.snap(midi)
        k = 0
        direction = 1 if steps > 0 else -1
        while k < abs(steps):
            m += direction
            if self.contains(m):
                k += 1
        return m

    def degree_of(self, midi):
        """(scale index, alteration in semitones) of a pitch"""
        rel = (int(round(midi)) - self.tonic) % 12
        sc = self.scale
        best = min(range(len(sc)), key=lambda i: (abs(rel - sc[i]), sc[i] > rel))
        return best, rel - sc[best]


def parse_key(key, mode="major"):
    if isinstance(key, Key):
        return key
    text = str(key).strip()
    m = re.fullmatch(r"([A-Ga-g][#b♯♭x]*)\s*(m|min|minor|maj|major)?\s*", text)
    if m:
        md = mode
        if m.group(2) in ("m", "min", "minor"):
            md = "minor"
        elif m.group(2) in ("maj", "major"):
            md = "major"
        return Key(pitch_class(m.group(1)), md)
    raise ValueError(f"Not a key: {key!r}")


# ------------------------------------------------------------------------------------------------ chords
@dataclass(frozen=True)
class Chord:
    root: int                      # pitch class
    intervals: tuple = (0, 4, 7)
    bass: int = None               # pitch class of a slash bass (None = root)
    symbol: str = ""

    @property
    def pcs(self):
        return [(self.root + i) % 12 for i in self.intervals]

    @property
    def bass_pc(self):
        return self.root if self.bass is None else self.bass

    @property
    def third(self):
        for i in self.intervals:
            if i % 12 in (3, 4):
                return (self.root + i) % 12
        return None

    @property
    def fifth(self):
        for i in self.intervals:
            if i % 12 in (6, 7, 8):
                return (self.root + i) % 12
        return None

    @property
    def seventh(self):
        for i in self.intervals:
            if i % 12 in (9, 10, 11) and i < 12:
                return (self.root + i) % 12
        return None

    @property
    def is_minor(self):
        return 3 in self.intervals and 4 not in self.intervals

    def transpose(self, semis):
        return Chord((self.root + semis) % 12, self.intervals, None if self.bass is None else (self.bass + semis) % 12,
                     self.symbol)

    def contains(self, midi):
        return int(round(midi)) % 12 in self.pcs


_NAMES = {(0, 4, 7): "", (0, 3, 7): "m", (0, 4, 7, 10): "7", (0, 4, 7, 11): "maj7", (0, 3, 7, 10): "m7",
          (0, 4, 7, 9): "6", (0, 3, 7, 9): "m6", (0, 2, 7): "sus2", (0, 5, 7): "sus4", (0, 5, 7, 10): "7sus4",
          (0, 3, 6): "dim", (0, 3, 6, 9): "dim7", (0, 3, 6, 10): "m7b5", (0, 4, 8): "aug", (0, 4, 7, 14): "add9",
          (0, 3, 7, 14): "madd9", (0, 4, 7, 10, 14): "9", (0, 4, 7, 11, 14): "maj9", (0, 3, 7, 10, 14): "m9",
          (0, 7): "5", (0, 2, 4, 7): "add2"}


def chord_name(c):
    """Chord -> symbol such as 'F#m7/C#'"""
    name = PC_NAME[c.root] + _NAMES.get(tuple(c.intervals), "(" + ",".join(str(i) for i in c.intervals) + ")")
    return name + (f"/{PC_NAME[c.bass]}" if c.bass is not None and c.bass != c.root else "")


def parse_chord(sym, key=None):
    """chord symbol or roman numeral -> Chord"""
    s = sym.strip()
    bass = None
    if "/" in s and not s.endswith("6/9"):
        s, b = s.rsplit("/", 1)
        if re.fullmatch(r"[A-Ga-g][#b♯♭]*", b):
            bass = pitch_class(b)
        elif re.fullmatch(r"[b#]?\d", b) and key is not None:
            acc = _acc(b[:-1])
            bass = (key.degree_pc(int(b[-1]) - 1) + acc) % 12
        elif key is not None and re.fullmatch(r"[b#]?(?:i|ii|iii|iv|v|vi|vii|I|II|III|IV|V|VI|VII)", b):
            target = parse_chord(b, key)               # secondary chord: V/vi = V of vi
            inner = parse_chord(s, Key(target.root, "minor" if target.is_minor else "major"))
            return Chord(inner.root, inner.intervals, None, sym)
    m = re.fullmatch(r"([A-G][#b♯♭]*)(.*)", s)
    if m:
        root = pitch_class(m.group(1))
        q = m.group(2)
        if q not in QUALITIES:
            raise ValueError(f"Unknown chord quality in {sym!r}")
        return Chord(root, QUALITIES[q], bass, sym)
    m = re.fullmatch(r"([b#♭♯]?)(vii|iii|ii|iv|vi|v|i|VII|III|II|IV|VI|V|I)(.*)", s)
    if not m or key is None:
        raise ValueError(f"Not a chord: {sym!r}")
    acc, numeral, q = _acc(m.group(1)), m.group(2), m.group(3)
    deg = ROMAN[numeral.lower()]
    sc = key.harmony_scale
    root = (key.tonic + sc[deg] + acc) % 12
    upper = numeral.isupper()
    if q in ("°", "o", "dim"):
        iv = (0, 3, 6)
    elif q in ("°7", "o7", "dim7"):
        iv = (0, 3, 6, 9)
    elif q in ("ø", "ø7", "m7b5"):
        iv = (0, 3, 6, 10)
    elif q in ("+", "aug"):
        iv = (0, 4, 8)
    elif q == "7":
        iv = (0, 4, 7, 10) if upper else (0, 3, 7, 10)
        if upper and numeral == "I" and key.harmony_mode in ("major", "lydian"):
            iv = (0, 4, 7, 11)
        if upper and numeral == "IV" and key.harmony_mode in ("major",):
            iv = (0, 4, 7, 11)
    elif q in ("maj7", "M7"):
        iv = (0, 4, 7, 11)
    elif q in QUALITIES and q:
        iv = QUALITIES[q]
        if not upper and q in ("6", "add9", "9"):
            iv = tuple(3 if x == 4 else x for x in iv)
    else:
        iv = (0, 4, 7) if upper else (0, 3, 7)
    return Chord(root, iv, bass, sym)


def parse_chords(text, key=None, beats_per_bar=4.0):
    """'D | A/C# | Bm G' -> [[(offset_beats, dur_beats, Chord), ...] per bar]"""
    bars = []
    prev = None
    for bar_txt in str(text).split("|"):
        toks = bar_txt.split()
        if not toks:
            continue
        slot = beats_per_bar / len(toks)
        out = []
        for i, tok in enumerate(toks):
            if tok in ("%",):
                ch = prev
            elif tok in (".", "-"):
                if out:
                    o, d, c = out[-1]
                    out[-1] = (o, d + slot, c)
                    continue
                ch = prev
            else:
                ch = parse_chord(tok, key)
            if ch is None:
                raise ValueError(f"Chord bar {bar_txt!r}: nothing to repeat")
            out.append((i * slot, slot, ch))
            prev = ch
        bars.append(out)
    return bars


def roman(key, degree, seventh=False):
    """diatonic chord on a scale degree (0-based) of the key's harmony scale"""
    sc = key.harmony_scale
    pcs = [(key.tonic + sc[(degree + k) % 7] + (12 if degree + k >= 7 else 0)) for k in (0, 2, 4, 6)]
    iv = tuple(p - pcs[0] for p in pcs[: 4 if seventh else 3])
    return Chord(pcs[0] % 12, iv)


# ------------------------------------------------------------------------------------------------ voice leading
def voicing(chord, n=4, lo=48, hi=72, prev=None, top=None):
    """choose MIDI pitches for a chord: every essential tone present (root, third, seventh; fifth if room),
    no crossing, gentle spacing, minimum total movement from `prev` (or centred when there is no previous voicing).
    `top` (the melody's lowest note nearby) is a soft ceiling: voices above it cost, so the harmony stays under
    the tune without jumping about whenever the tune dips."""
    pcs = chord.pcs
    essential = [chord.root]
    if chord.third is not None:
        essential.append(chord.third)
    if chord.seventh is not None:
        essential.append(chord.seventh)
    extra = [p for p in pcs if p not in essential]
    want = list(dict.fromkeys(essential + extra))
    options = [m for m in range(lo, hi + 1) if m % 12 in pcs]
    if not options:
        return []
    n = max(1, min(n, len(options)))
    centre = (lo + hi) / 2.0 if prev is None or not len(prev) else sum(prev) / len(prev)
    if prev is None and top is not None:
        centre = min(centre, top - 5.0)
    best, best_cost = None, None
    prev_sorted = sorted(prev) if prev else None
    if prev_sorted and len(prev_sorted) == n:
        pool = itertools.product(*[sorted(options, key=lambda m: abs(m - p))[:4] for p in prev_sorted])
    else:
        mid = sorted(options, key=lambda m: abs(m - centre))[: n + 5]
        pool = itertools.combinations(sorted(mid), n)
    for combo in pool:
        v = sorted(combo)
        if len(set(v)) < n:
            continue
        have = {m % 12 for m in v}
        if any(p not in have for p in want[: min(len(want), n)]):
            continue
        if any(b - a > 12 for a, b in zip(v[1:], v[2:])) or (n >= 2 and v[-1] - v[0] > 24):
            continue
        if prev_sorted and len(prev_sorted) == n:
            steps = [abs(a - b) for a, b in zip(v, prev_sorted)]
            cost = sum(steps) + sum(4.0 + 0.6 * (s - 5) for s in steps if s > 5)
        else:
            cost = abs(sum(v) / n - centre) + 0.3 * (v[-1] - v[0])
        if top is not None and v[-1] > top:
            cost += 1.5 * (v[-1] - top)
        if chord.third is not None and sum(1 for m in v if m % 12 == chord.third) > 1:
            cost += 4
        if v[0] % 12 != chord.bass_pc and n >= 3:
            cost += 0.5
        if best_cost is None or cost < best_cost:
            best, best_cost = v, cost
    if best is None:
        best = sorted(sorted(options, key=lambda m: abs(m - centre))[:n])
    return list(best)


def bass_note(chord, lo=28, hi=48, prev=None):
    """the bass pitch of a chord (slash bass honoured) near the previous bass note"""
    pc = chord.bass_pc
    opts = [m for m in range(lo, hi + 1) if m % 12 == pc]
    if not opts:
        return lo + (pc - lo) % 12
    ref = prev if prev is not None else (lo + hi) / 2.0 - 3
    return min(opts, key=lambda m: (abs(m - ref), m))


@dataclass
class Theme:
    """a parsed theme: melody notes and chord slots per bar, in its own key"""
    key: Key
    tempo: float = 100.0
    beats: float = 4.0
    compound: bool = False
    bars: list = field(default_factory=list)     # [{"melody": [Note (beat relative to the bar)], "chords": [...]}]
    name: str = ""

    @property
    def length(self):
        return len(self.bars)


def parse_theme(spec, name=""):
    """theme dict -> Theme"""
    key = parse_key(spec.get("key", "C"), spec.get("mode", "major"))
    if spec.get("mode"):
        key = Key(key.tonic, spec["mode"])
    beats, compound = meter_beats(spec.get("meter", 4))
    notes = parse_melody(spec.get("melody", ""), beats)
    chords = parse_chords(spec.get("chords", "I"), key, beats) if spec.get("chords") else []
    total = max([n.end for n in notes] + [0.0])
    nbars = max(int(-(-total // beats)) if total > 0 else 0, len(chords), 1)
    bars = [{"melody": [], "chords": chords[i % len(chords)] if chords else [(0.0, beats, roman(key, 0))]}
            for i in range(nbars)]
    for nt in notes:
        b = int(nt.beat // beats + 1e-9)
        start, remaining, first = nt.beat, nt.dur, True
        while remaining > 1e-9 and b < nbars:
            bar_end = (b + 1) * beats
            d = min(remaining, bar_end - start)
            part = Note(start - b * beats, d, nt.pitch, nt.art if first else "normal", nt.slide if first else False)
            if not first:
                part.art = "tie"
            bars[b]["melody"].append(part)
            remaining -= d
            start = bar_end
            b += 1
            first = False
    return Theme(key, float(spec.get("tempo", 100)), beats, compound, bars, name)
