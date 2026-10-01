"""
score.py -- the ORIGINAL score of Duel in the Silver Grass, composed programmatically and rendered with instruments.py.

Material: ONLY the two leitmotifs in config.LEITMOTIFS (+ inversions / augmentations / diminutions / fragments /
scale-step sequences), in the in-scale on D (D Eb G A Bb); the epilogue turns them to the yo scale (D E G A B).
    tenko (Tenko, the elder)  D4 Bb3 A3 D4 Eb4 D4        grave, falling; it owns the half-step SIGHS (Eb->D, Bb->A)
    saku  (Saku, the shinobi)  his HOME form is the inversion D5 G5 Eb5 D5 Bb4 D5 G5 -- the G and the upward leaps;
                              the original D5 A4 Bb4 D5 Eb5 D5 A4 appears only in development
Harmony (the bass plan; drones, pedals and riffs are accompaniment, never new melody):
    prologue, Act I    D (open fifth D-A; the Eb rub for tension)
    Act II             G and A pedals, the bass sighing Bb->A (S16, S18); S19 G minor -> A-Eb; thunder / rain on A
    Act III            one scale step UP: Eb over Bb at the Raikiri, the storm sings tenko on Eb; bass Bb -> A (the
                       A-Eb tritone through S22b / S23) -> D only at the low point
    final pass         D.  Act III's Eb falling back to D is the film's large-scale sigh; the sigh itself (tenko
                       fragment Eb4 -> D4, solo shakuhachi) answers the sword break at 3412
    epilogue           D yo: tenko resolved, saku as a soft koto arpeggio, the end-card bell
Tuning: every drum and sub is pitched in the key -- odaiko D2 (partials A2 / D3), odaiko_lo G1 (D2 / G2), story hits
D1 (A1 / D2) or the bass of the moment; subs glide ONTO their pitch.  The temple bell is in the key (instruments).

Sync: every accent that answers an event (odaiko, odaiko_lo, sub, strings sfz, hyoshigi) is placed at the EXACT
event time; only the pattern that follows is quantised, starting on the first grid step >= 1 frame later.
render()['marks'] lists every event-driven accent with its event time (mix.py checks |music - event| <= 1 frame);
events more than 1 frame off their grid are listed in render()['warnings'].

Time: the metered sections follow timeline.tempo_sections (config.TEMPO_MAP; Act III split at the low point so it is
a downbeat wherever the picture puts it):
    act1      92 BPM from act1_bar1 (631)         -> act2_start
    act2     120 BPM (12 f per beat) from 1633    -> act3_start
    act3     140 BPM from 2497 (= the Raikiri)    -> low_point  (fitted);   act3_low  low_point -> 'silence' (HARD stop)
Free-time sections (prologue, pre-clash, final pass, epilogue) are placed on cue times.

Level design (the loudness map is finished in mix.py): continuous beds carry a `role` ('bed' shime 16ths / koto
ostinati, 'pad' tremolo and choir pads) trimmed per section (ROLE_TRIM_DB); the arrangement thins 1-2 bars before the
hat cut, the act II downbeat and the Raikiri; routine accents (shove, deflect, spear draw) are held below the story
hits (first clash, hat cut, act II downbeat, Raikiri, low point, final pass).

render(doc) -> dict(stem=(2,N), sections=[...], notes=int, counts, hits, marks, accents, warnings)
"""
import numpy as np

import config
import dsp
import instruments as I
import timeline as tl
from dsp import SR, n_of, TWO_PI

TONIC = config.TONIC_MIDI
SCALES = {"in": config.SCALE_IN, "yo": config.SCALE_YO}
MOTIFS = config.LEITMOTIFS

# pitches (Hz) of the tuned percussion / subs
D1, G1, A1, BB1, D2 = 36.71, 49.0, 55.0, 58.27, 73.42
# string / choir voicings of the bass plan (MIDI)
VOICING = {
    "D": [26, 38, 45, 50],            # D1 D2 A2 D3
    "G": [31, 38, 43, 50],            # G1 D2 G2 D3
    "A": [33, 38, 45],                # A1 D2 A2        (A with the D above: in-scale 'sus')
    "A_eb": [33, 39, 45],             # A1 Eb2 A2       (the tritone of the storm)
    "Bb": [34, 39, 46],               # Bb1 Eb2 Bb2
    "EbBb": [34, 39, 43, 46, 51],     # Eb major over Bb: the Raikiri
}
SUB_HZ = {"D": D1, "G": G1, "A": A1, "A_eb": A1, "Bb": BB1, "EbBb": BB1}
RIFF_SHIFT = {"D": 0, "G": 2, "A": 3, "A_eb": 3, "Bb": 4, "EbBb": 4}   # tenko riff sequenced onto the bass


# =====================================================================================  motif tools
def motif(name, scale=None, shift=0, octave=0, aug=1.0, inv=False, retro=False, frag=None):
    """-> [(beat_offset, beats, midi)] ; shift = scale steps (diatonic sequence), inv = mirror around the
    first note in scale-step space, aug = rhythmic augmentation (<1 diminution), frag = slice of notes"""
    m = MOTIFS[name]
    sc = SCALES[scale or m["scale"]]
    notes = list(m["notes"])
    if frag is not None:
        notes = notes[frag]
    flat = [d + 5 * o for (d, o, b) in notes]
    beats = [b * aug for (_, _, b) in notes]
    if inv:
        p = flat[0]
        flat = [2 * p - f for f in flat]
    if retro:
        flat, beats = flat[::-1], beats[::-1]
    out = []
    pos = 0.0
    for f, b in zip(flat, beats):
        f = f + shift + 5 * octave
        out.append((pos, b, TONIC + 12 * (f // 5) + sc[f % 5]))
        pos += b
    return out


def saku_home(**kw):
    """the shinobi's own figure: the saku inversion (D G Eb D Bb D G)"""
    return motif("saku", inv=True, **kw)


def total_beats(mot):
    return sum(b for (_, b, _) in mot)


class Grid:
    def __init__(self, t_anchor, bpm, t_end, bpb=4, nbars=None, name=""):
        self.t0 = t_anchor
        self.beat = 60.0 / bpm
        self.bpb = bpb
        self.t_end = t_end
        self.bar_len = bpb * self.beat
        self.nbars = int(nbars) if nbars else max(1, int(round((t_end - t_anchor) / self.bar_len)))
        self.bpm = bpm
        self.name = name

    def t(self, bar, beat=0.0):
        return self.t0 + (bar * self.bpb + beat) * self.beat

    def beats_at(self, t):
        return (t - self.t0) / self.beat

    def bar_at(self, t):
        return int(np.floor(self.beats_at(t) / self.bpb + 1e-9))

    def bar_near(self, t):
        return int(round(self.beats_at(t) / self.bpb))

    def q(self, t, div=2):
        """quantise a time to the nearest 1/div beat"""
        b = round(self.beats_at(t) * div) / div
        return self.t0 + b * self.beat

    def next_step(self, t, div=2, gap=1.0 / config.FPS):
        """first 1/div-beat grid step at least `gap` s after t (patterns that FOLLOW an exact-time accent)"""
        b = np.ceil((self.beats_at(t + gap) - 1e-9) * div) / div
        return self.t0 + b * self.beat

    def off_frames(self, t, div=2, fps=config.FPS):
        return abs(t - self.q(t, div)) * fps


# =====================================================================================  note list
class Score:
    def __init__(self, seed=11, fps=config.FPS):
        self.notes = []
        self.marks = []
        self.warnings = []
        self.fps = fps
        self.r = dsp.rng("score", seed)

    def add(self, inst, t, dur=0.0, midi=None, vel=0.7, role=None, **kw):
        if t is None or not np.isfinite(t):
            return
        self.notes.append(dict(inst=inst, t=float(t), dur=float(dur), midi=midi, vel=float(vel), kw=kw, role=role))

    def mark(self, name, t_music, t_event=None, src="default", G=None):
        """record an event-driven accent (t_event None: no event -> the default time was used)"""
        d = dict(name=name, t=round(float(t_music), 4), t_event=None if t_event is None else round(float(t_event), 4),
                 src=src)
        if t_event is not None:
            d["err_ms"] = round((t_music - t_event) * 1000.0, 2)
            if G is not None:
                off = G.off_frames(t_event, 2, self.fps)
                d["grid_off_frames"] = round(off, 2)
                if off > 1.0:
                    self.warnings.append(f"'{name}' event at {t_event:.3f} s is {off:.1f} frames off the {G.name} "
                                         f"8th-note grid: the accent follows the event, the pattern re-enters on the grid")
        self.marks.append(d)
        return t_music

    def hum(self, t, amt=0.005):
        return t + self.r.normal(0.0, amt)

    def vj(self, v, amt=0.06):
        return float(np.clip(v * (1.0 + self.r.normal(0.0, amt)), 0.02, 1.2))

    def pattern(self, inst, G, bar, pat, vel=0.8, t_from=None, t_to=None, humanize=0.004, role=None, **kw):
        """16-step (or any length) drum pattern for one bar: X accent, x normal, o ghost, f flam"""
        steps = len(pat)
        sb = G.bpb / steps
        for i, ch in enumerate(pat):
            if ch == ".":
                continue
            t = G.t(bar, i * sb)
            if (t_from is not None and t < t_from - 1e-6) or (t_to is not None and t >= t_to - 1e-6):
                continue
            v = {"X": 1.0, "x": 0.72, "o": 0.42, "f": 0.95}.get(ch, 0.7) * vel
            tt = t if (i * sb) % 1.0 == 0 else self.hum(t, humanize)
            self.add(inst, tt, 0.0, None, self.vj(v), role=role, **kw)
            if ch == "f":
                self.add(inst, tt - 0.028, 0.0, None, self.vj(v * 0.45), role=role, **kw)

    def line(self, inst, t0, beat, mot, vel=0.6, ring=None, legato=1.0, vel_shape=None, t_to=None, role=None, **kw):
        """play a motif list starting at t0 with the given beat length (s)"""
        for i, (b, nb, m) in enumerate(mot):
            t = t0 + b * beat
            if t_to is not None and t >= t_to - 0.02:
                break
            d = nb * beat * legato if ring is None else max(ring, nb * beat)
            v = vel * (vel_shape[i % len(vel_shape)] if vel_shape else 1.0)
            self.add(inst, self.hum(t, 0.004) if i else t, d, m, self.vj(v, 0.05), role=role, **kw)
        return t0 + total_beats(mot) * beat

    def hit(self, t, level=1.0, bass="D", big=False, strings=True, hyoshigi=False, sub=True, send_big=None,
            str_dur=0.9, str_vel=None, swell_to=None):
        """a unified accent at EXACT time t: drums (+ big low drum on the bass pitch), sub, strings sfz"""
        v = level
        self.add("odaiko", t, 0, None, min(1.1, 1.0 * v), role="accent")
        if big:
            f0 = {"D": D1, "G": G1, "A": A1, "A_eb": A1, "Bb": G1, "EbBb": G1}[bass]
            self.add("odaiko_lo", t, 0, None, min(1.15, 1.08 * v), role="accent", size=1.5, tone=0.42, f0=f0,
                     send=send_big or {"huge": 0.35, "hall": 0.1})
        else:
            self.add("odaiko_lo", t, 0, None, min(1.1, 0.95 * v), role="accent")
        if sub:
            self.add("sub", t, 1.8 if big else 1.4, None, min(1.0, 0.8 * v), role="accent", f0=SUB_HZ[bass])
        if hyoshigi:
            self.add("hyoshigi", t, 0, None, 0.8 * v, role="accent")
        if strings:
            self.add("strings", t, str_dur, VOICING[bass], str_vel if str_vel is not None else 0.7 * v, mode="sfz",
                     swell_to=swell_to, release=0.4, role="accent")


# =====================================================================================  instrument renderers
def _hz(m):
    return float(dsp.midi2hz(m))


def _sub(vel, r, dur=1.6, f0=D1):
    """pitched sub boom that glides ONTO f0 (in the key) and stays there; a quiet octave for small speakers"""
    n = n_of(dur)
    t = dsp.t_axis(n)
    f = f0 * (1.0 + 0.9 * np.exp(-t / 0.035) + 0.02 * np.exp(-t / 0.15))
    ph = dsp.phase_cycles(f, n)
    y = (np.sin(TWO_PI * ph) + 0.22 * np.sin(2 * TWO_PI * ph + 0.4)) * np.exp(-t / (dur * 0.3)) * np.clip(t / 0.004, 0, 1)
    y = dsp.saturate(y * 1.2, 0.25)
    return dsp.fade(dsp.normalize(y, 1.0) * vel, 0.0, dur * 0.25)


def _noise_hit(vel, r, dur=1.2, tau=0.22):
    n = n_of(dur)
    t = dsp.t_axis(n)
    out = np.zeros((2, n))
    for ch in range(2):
        x = r.standard_normal(n)
        x = dsp.tv_biquad(x, "lp", 900 + 13000 * np.exp(-t / 0.09), 0.7, block=128)
        out[ch] = x * np.exp(-t / tau) * np.clip(t / 0.006, 0, 1)
    return dsp.normalize(dsp.fade(out, 0.0, dur * 0.3), 1.0) * vel


def render_note(n, r):
    """-> (audio mono|stereo, anchor_samples)"""
    inst, v, kw = n["inst"], n["vel"], dict(n["kw"])
    for k in ("pan", "send", "gain", "width", "eq"):
        kw.pop(k, None)
    if inst in ("odaiko", "odaiko_lo"):
        size = kw.pop("size", 1.2 if inst == "odaiko_lo" else 0.9)
        tone = kw.pop("tone", 0.35 if inst == "odaiko_lo" else 0.55)
        f0 = kw.pop("f0", G1 if inst == "odaiko_lo" else D2)
        return I.odaiko(v, r, size=size, tone=tone, f0=f0), 0
    if inst == "shime":
        return I.shime(v, r, rim=kw.pop("rim", False)), 0
    if inst == "hyoshigi":
        return I.hyoshigi(v, r), 0
    if inst == "shakuhachi":
        return I.shakuhachi(_hz(n["midi"]), max(n["dur"], 0.15), v, r, **kw), 0
    if inst in ("koto", "koto2"):
        return I.koto(_hz(n["midi"]), max(n["dur"], 0.5), v, r, **kw), 0
    if inst == "shamisen":
        return I.shamisen(_hz(n["midi"]), max(n["dur"], 0.25), v, r, **kw), 0
    if inst in ("strings", "strings_hi"):
        ms = n["midi"] if isinstance(n["midi"], (list, tuple)) else [n["midi"]]
        return I.strings([_hz(m) for m in ms], max(n["dur"], 0.1), v, r, **kw), 0
    if inst == "choir":
        ms = n["midi"] if isinstance(n["midi"], (list, tuple)) else [n["midi"]]
        return I.choir([_hz(m) for m in ms], max(n["dur"], 0.3), v, r, **kw), 0
    if inst == "bell":
        return I.temple_bell(_hz(n["midi"]), v, r, dur=max(n["dur"], 4.0), **kw), 0
    if inst == "heart":
        return I.heartbeat(v, r), 0
    if inst == "swell":
        a, anc = I.metal_swell(max(n["dur"], 0.4), v, r, **kw)
        return a, anc
    if inst == "sub":
        return _sub(v, r, dur=n["dur"] if n["dur"] > 0 else 1.6, **kw), 0
    if inst == "noise_hit":
        return _noise_hit(v, r, dur=n["dur"] if n["dur"] > 0 else 1.2, **kw), 0
    raise KeyError(inst)


# track defaults: pan, stereo width, reverb sends, gain
TRACKS = {
    "odaiko":     dict(pan=0.05, width=1.0, send={"hall": 0.26}, gain=0.5),
    "odaiko_lo":  dict(pan=-0.05, width=1.0, send={"hall": 0.30}, gain=0.5),
    "shime":      dict(pan=0.3, width=1.0, send={"hall": 0.14}, gain=0.4),
    "hyoshigi":   dict(pan=-0.15, width=1.0, send={"temple": 0.32}, gain=0.4),
    "shakuhachi": dict(pan=-0.08, width=1.0, send={"temple": 0.40}, gain=0.72),
    "koto":       dict(pan=-0.4, width=1.0, send={"hall": 0.22}, gain=0.8),
    "koto2":      dict(pan=0.42, width=1.0, send={"hall": 0.22}, gain=0.7),
    "shamisen":   dict(pan=0.32, width=1.0, send={"hall": 0.14}, gain=0.85),
    "strings":    dict(pan=0.0, width=1.0, send={"hall": 0.30}, gain=0.42),
    "strings_hi": dict(pan=0.1, width=0.8, send={"hall": 0.36}, gain=0.34),
    "choir":      dict(pan=0.0, width=1.0, send={"hall": 0.44}, gain=0.6),
    "bell":       dict(pan=0.0, width=1.0, send={"temple": 0.45}, gain=0.55),
    "heart":      dict(pan=0.0, width=1.0, send={"hall": 0.04}, gain=0.55),
    "swell":      dict(pan=0.0, width=1.0, send={"hall": 0.22}, gain=0.35),
    "sub":        dict(pan=0.0, width=1.0, send={}, gain=0.24),
    "noise_hit":  dict(pan=0.0, width=1.0, send={"huge": 0.6}, gain=0.4),
}


# mix automation of the music stem per section (dB)
SECTION_GAIN_DB = dict(prologue=-5.0, act1_pre=-1.5, final_pass=0.0, epilogue=-4.5)
# per-section trims of the continuous beds / pads (dB): the fight must breathe, not be a wall of 16ths and tremolo
ROLE_TRIM_DB = {
    "act1": dict(bed=-3.0, pad=-2.0),
    "act2": dict(bed=-2.5, pad=-2.0),
    "act3": dict(bed=-1.5, pad=-1.5),
    "act3_low": dict(bed=-1.5, pad=-1.5),
}
BREATH = 0.42        # s of (almost) nothing before the Raikiri cut
A2_BREATH = 0.3      # s of nothing before the act II downbeat (only the reversed swell sucks in)
# low-mid clean-up (the 250 Hz octave was +8 dB over 1 kHz in the groove, +13 dB in the epilogue): pedals + flute
EPI_EQ = [("peak", 250.0, -3.0, 0.8)]
GROOVE_EQ = [("peak", 260.0, -2.5, 0.8)]
OST_EQ = [("highshelf", 1500.0, -3.0, 0.7)]      # the koto ostinato is a bed: its 2nd/3rd harmonics recede

# re-struck drums / re-plucked strings damp the previous vibration: (fade s, same_pitch_only)
CHOKE = {"odaiko": (0.10, False), "odaiko_lo": (0.14, False), "shime": (0.035, False), "hyoshigi": (0.02, False),
         "koto": (0.06, True), "koto2": (0.06, True), "shamisen": (0.03, False)}


def _choke_times(notes):
    """for every note: seconds after its onset at which the next note of the same voice cuts it (or None)"""
    out = [None] * len(notes)
    last = {}
    for i, n in enumerate(notes):
        c = CHOKE.get(n["inst"])
        if c is None:
            continue
        key = (n["inst"], str(n["midi"])) if c[1] else n["inst"]
        j = last.get(key)
        if j is not None:
            dt = n["t"] - notes[j]["t"]
            if dt > 0.012:
                out[j] = dt if out[j] is None else min(out[j], dt)
        last[key] = i
    return out


def _choke(a, idx, fade):
    """cosine fade-out starting at sample idx over `fade` seconds, silence after"""
    n = a.shape[-1]
    if idx >= n:
        return a
    f = n_of(fade)
    a = a.copy()
    m = min(f, n - idx)
    w = 0.5 + 0.5 * np.cos(np.linspace(0, np.pi, m))
    a[..., idx:idx + m] *= w
    a[..., idx + m:] = 0.0
    return a[..., :idx + m]


# =====================================================================================  helpers on the Doc
def shot_t(doc, sid, default=None):
    for s in doc.shots:
        if s["id"] == sid:
            return s["t0"]
    return default


def shot_id_at(doc, t):
    s = doc.shot_at(t)
    return s["id"] if s else None


def first_event(doc, typ, t0=-1e9, t1=1e9, tag=None):
    for e in doc.events:
        if e["type"] == typ and t0 <= e["t"] <= t1 and (tag is None or tag in e["tags"]):
            return e
    return None


def strongest_event(doc, types, t0, t1, min_strength=0.8):
    """the strongest event of `types` in [t0, t1] with strength >= min_strength (earliest on ties), else None"""
    c = [e for e in doc.events if e["type"] in types and t0 <= e["t"] <= t1 and e["strength"] >= min_strength]
    if not c:
        return None
    return max(c, key=lambda e: (e["strength"] + (0.2 if e["type"] == "clash_heavy" else 0.0), -e["t"]))


def events_in(doc, types, t0, t1):
    return [e for e in doc.events if e["type"] in types and t0 <= e["t"] < t1]


def cue_src(doc, name):
    c = doc.cues.get(name)
    return c["source"] if c else "default"


def _title(tid):
    for t in config.TITLES:
        if t["id"] == tid:
            return t
    return None


# =====================================================================================  sections
def arr_prologue(S, doc, C):
    fps = doc.fps
    t_title = C["title"]
    t_a1 = C["act1_start"]
    # the low D under the wind, then the title: temple bell + a soft deep drum (D1) + the drone opening up
    S.add("strings", 1.8, max(0.5, t_title - 1.8) + 0.4, [38, 45], 0.22, mode="swell", release=1.6, role="pad")
    S.add("strings", t_title - 0.15, t_a1 - t_title + 0.3, [38, 45, 50], 0.28, mode="sustain", attack=1.4, release=1.0,
          role="pad")
    S.add("bell", t_title, 13.0, 50, 0.55)
    S.add("odaiko_lo", t_title, 0, None, 0.42, size=1.4, tone=0.35, f0=D1)
    S.mark("title", t_title, t_title if cue_src(doc, "title") != "config" else None, cue_src(doc, "title"))
    # sparse shakuhachi: one call from the field after the bell (ro = A3), gone before the shinobi's walk (S03)
    t03 = shot_t(doc, "S03", t_title + 2.6)
    t = t_title + 1.3
    d = max(0.6, min(1.6, t03 - 0.35 - t))
    S.add("shakuhachi", t, d, 57, 0.26, attack="meri", bend=-120, bend_time=0.22, vib_delay=0.6, swell=0.5, fall=90,
          release=0.3, bright=0.3)
    # S03, his name card: the shinobi's own figure (saku inversion, augmented x2) softly on the koto
    nc = _title("name_shinobi")
    t_nc = doc.f2t(nc["start"]) if nc else shot_t(doc, "S03", t_title + 4.5) + 2.0
    for (b, nb, m) in saku_home(aug=2.0):
        S.add("koto", t_nc + b * 0.36, 2.2, m, S.vj(0.22), bright=0.45)
    # S04, the elder's reveal: tenko on the shakuhachi (rubato), the last D rings into the stand-off
    t04 = shot_t(doc, "S04")
    if t04 is not None:
        S.add("odaiko", t04 + 0.1, 0, None, 0.28)
        t = t04 + 3.0 / fps
        beat = 0.55
        stretch = [1.1, 0.95, 1.15, 0.85, 1.1, 1.0]
        gaps = [0.12, 0.0, 0.18, 0.0, 0.0, 0.0]
        arts = [dict(attack="meri", bend=-120, bend_time=0.2, vib_delay=0.5, swell=0.4),
                dict(attack="plain", vib_depth=10, vib_delay=0.3),
                dict(attack="meri", bend=-60, yuri=0.6),
                dict(attack="plain", atari=200, vib_depth=6),
                dict(attack="kari", vib_depth=22, vib_delay=0.35, swell=0.3),
                dict(attack="plain", fall=160, vib_depth=18, swell=0.6, release=0.45)]
        vels = [0.32, 0.27, 0.3, 0.26, 0.35, 0.33]
        for (b0, nb, m), st, gap, art, v in zip(motif("tenko"), stretch, gaps, arts, vels):
            d = nb * beat * st
            S.add("shakuhachi", t, d, m, v, bright=0.35, **art)
            t += d + gap
        S.add("koto", t04 + 55.0 / fps, 2.5, 86, 0.14, bright=0.8)       # the eye glint (~392)


def arr_act1_pre(S, doc, C, G1):
    t0 = C["act1_start"]
    tc = C["first_clash"]
    tb1 = G1.t0
    S.add("hyoshigi", t0, 0, None, 0.62)
    S.add("hyoshigi", t0 + 0.42, 0, None, 0.82)
    S.add("strings", t0 - 0.2, max(1.0, (tc - 0.85) - t0), [38, 45], 0.28, mode="sustain", attack=0.6, release=0.6,
          role="pad")
    S.add("strings", t0 + 1.8, max(0.8, min(3.4, tc - t0 - 3.2)), [39], 0.16, mode="swell", release=0.6, role="pad")
    t = t0 + 1.15
    for (b, nb, m) in saku_home(frag=slice(0, 3)):                  # D5 G5 Eb5: his leap
        S.add("koto", t, 2.2, m, 0.28, bright=0.45)
        t += 0.62
    t = t0 + 3.3
    for (b, nb, m) in motif("tenko", frag=slice(0, 3), octave=1):    # D5 Bb4 A4: the elder's fall answers
        S.add("koto2", t, 2.2, m, 0.2, bright=0.4)
        t += 0.7
    t06 = shot_t(doc, "S06")
    if t06 is not None and t06 < tc - 1.0:
        S.add("odaiko_lo", t06 + 0.15, 0, None, 0.2)
        S.add("odaiko_lo", t06 + 0.8, 0, None, 0.24)
    # the clang itself: the music drops in HARD (D1 drum + sub + low-string stab blooming through the slow motion)
    S.mark("first_clash", tc, tc if cue_src(doc, "first_clash") != "config" else None, cue_src(doc, "first_clash"))
    S.add("odaiko_lo", tc, 0, None, 1.08, size=1.55, tone=0.45, f0=D1, send={"huge": 0.4, "hall": 0.1}, role="accent")
    S.add("odaiko", tc, 0, None, 0.9, role="accent")
    S.add("sub", tc, 2.2, None, 0.8, f0=D1, role="accent")
    S.add("strings", tc, 0.7, [38, 45, 50], 0.72, mode="sfz", swell_to=0.3, release=0.6, role="accent")
    # after the clang: the slow-motion bloom into bar 1 (the groove starts at act1_bar1)
    if tb1 - tc > 0.3:
        S.add("strings", tc + 0.12, tb1 - tc - 0.1, [38, 45, 50], 0.42, mode="swell", release=0.12)
        S.add("swell", tb1, tb1 - tc - 0.05, None, 0.42)


def arr_act1(S, doc, C, G):
    """92-BPM grid from act1_bar1 to act2_start"""
    nb = G.nbars
    t_end = G.t(nb)
    beat = G.beat
    fr = 1.0 / doc.fps
    # ---------------------------------------------------------------- event lookups (exact times)
    gs = first_event(doc, "grass_shear", G.t0, t_end)
    t_gs = gs["t"] if gs else G.t(7, 2)
    t_pd = C.get("perfect_deflect", G.t(11, 3))
    t_hc = C.get("hat_cut", G.t(12, 2.4))
    ov = strongest_event(doc, ("clash", "clash_heavy"), t_gs + 0.2, t_gs + 4.0, 0.8)
    t_ov = ov["t"] if ov else G.t(G.bar_near(t_gs) + 1)
    bl = first_event(doc, "blade_lock", t_ov, t_pd)
    t_bl = bl["t"] if bl else G.t(10, 1.25)
    t_shove = (t_bl + (bl["duration_s"] or 1.8)) if bl else G.t(11)
    t_shove = min(t_shove, t_pd - 0.5)
    sd = first_event(doc, "spear_draw", t_hc, t_end)
    t_sd = sd["t"] if sd else G.t(15, 1)
    S.mark("grass_shear", t_gs, gs["t"] if gs else None, "grass_shear event" if gs else "default", G)
    S.mark("overhead", t_ov, ov["t"] if ov else None, f"{ov['type']} event" if ov else "default", G)
    S.mark("blade_lock", t_bl, bl["t"] if bl else None, "blade_lock event" if bl else "default")   # a pad onset
    S.mark("shove", t_shove, t_shove if bl else None, "blade_lock end" if bl else "default", G)
    S.mark("spear_draw", t_sd, sd["t"] if sd else None, "spear_draw event" if sd else "default", G)
    b_ov = G.bar_near(t_ov)
    b_shove = G.bar_near(t_shove)
    b_hc = G.bar_at(t_hc)
    t10 = shot_t(doc, "S10")
    s_hide0 = (G.bar_at(t10 - 0.4) + 1) if t10 is not None else 5          # first bar starting inside S10
    s_hide0 = int(np.clip(s_hide0, 2, max(2, G.bar_at(t_gs))))
    # ---------------------------------------------------------------- bar 0: the music drops in (the anchor)
    S.mark("act1_bar1", G.t0, G.t0 if cue_src(doc, "act1_bar1") != "config" else None, cue_src(doc, "act1_bar1"))
    S.add("odaiko", G.t(0), 0, None, 0.95, role="accent")
    S.add("odaiko_lo", G.t(0), 0, None, 0.95, role="accent")
    S.add("sub", G.t(0), 0, None, 0.7, f0=D1, role="accent")
    S.add("strings", G.t(0), G.bar_len * 2, [38, 45, 50], 0.62, mode="sfz", swell_to=0.45, release=0.8)
    S.pattern("odaiko", G, 0, "X.......x...x...", 0.62, t_from=G.t(0, 0.1))
    S.pattern("shime", G, 0, "........xoxoxxxx", 0.55, role="bed")
    S.line("koto", G.t(0, 2), beat, saku_home(), 0.5, ring=1.4, bright=0.45)
    S.add("hyoshigi", G.t(0), 0, None, 0.55)
    # ---------------------------------------------------------------- A / A2 (S08, S09): the groove on D
    ost = saku_home()             # the ostinato: his figure in even eighths, 7 notes + a rest
    for k in range(1, min(s_hide0, nb)):
        mode = "A" if k <= 2 else "A2"
        S.pattern("odaiko", G, k, "X.....x.X...x..." if mode == "A" else "X.....x.X...x.xo", 0.66)
        S.pattern("odaiko_lo", G, k, "X.......X.......", 0.56)
        S.pattern("shime", G, k, "x.o.x.o.x.oox.o." if mode == "A" else "xoxoxoxoXoxoxoxo", 0.5, role="bed")
        inst = "koto" if mode == "A" else "koto2"
        for i, (_, _, m) in enumerate(ost):
            S.add(inst, S.hum(G.t(k, 0.5 * i)), 1.2, m, S.vj(0.32 if i else 0.4), role="bed", bright=0.25, eq=OST_EQ)
        if mode == "A2":
            sh = (k - 3) * 2
            S.line("koto", G.t(k, 0), beat, saku_home(shift=sh), 0.5, ring=1.0, bright=0.45)
            S.line("koto", G.t(k, 2.5), beat, motif("saku", shift=sh + 1, frag=slice(0, 5)), 0.45, ring=1.0, bright=0.45)
    if s_hide0 > 1:
        S.add("strings", G.t(1), G.bar_len * min(3, s_hide0 - 1) - 0.1, [38, 45], 0.36, mode="sustain", attack=0.5,
              release=0.7, role="pad", eq=GROOVE_EQ)
        # the elder's theme over the groove (quieter than before, a flatter, more reedy tone instead of level)
        t_sh = G.t(1)
        for (b, nbt, m), art in zip(motif("tenko"), [dict(attack="meri", bend=-90), {}, dict(yuri=0.3), dict(atari=200),
                                                   dict(attack="kari"), dict(fall=120, swell=0.5)]):
            S.add("shakuhachi", t_sh + b * beat, nbt * beat * 0.97, m, 0.4, vib_delay=0.3, bright=0.8, eq=GROOVE_EQ, **art)
    # ---------------------------------------------------------------- hide (S10: the elder listens) .. the cut
    t_hide0 = G.t(s_hide0)
    if t_gs - t_hide0 > 1.0:
        S.add("strings", t_hide0, t_gs - t_hide0 - 0.05, [38, 45], 0.2, mode="sustain", attack=1.2, release=0.3,
              role="pad")
        hide_m = motif("tenko", frag=slice(3, 6), aug=1.5)          # D4 Eb4 D4 -- the sigh, very slow
        tt = t_hide0 + 0.8
        for (b, nbt, m) in hide_m:
            if tt + nbt * beat > t_gs - 0.3:
                break
            S.add("shakuhachi", tt, nbt * beat, m, 0.24, attack="meri", bend=-70, yuri=0.5, breath=1.4, vib_depth=8,
                  bright=0.4)
            tt += nbt * beat + 0.15
    # ---------------------------------------------------------------- the draw-cut shears the grass (exact time)
    S.add("odaiko", t_gs, 0, None, 0.9, role="accent")
    S.add("odaiko_lo", t_gs, 0, None, 0.85, role="accent")
    S.add("sub", t_gs, 0, None, 0.6, f0=D1, role="accent")
    S.add("strings", t_gs, max(0.6, t_ov - t_gs), [38, 45, 50], 0.55, mode="sfz", swell_to=0.75, release=0.1,
          role="accent")
    tt = G.next_step(t_gs, 2, fr)
    i = 0
    while tt < t_ov - 0.05:
        u = (tt - t_gs) / max(t_ov - t_gs, 1e-3)
        S.add("shime", tt, 0, None, S.vj(0.28 + 0.5 * u), role="bed")
        S.add("shime", tt + beat / 4, 0, None, S.vj(0.2 + 0.4 * u), role="bed")
        if i % 2 == 0:
            S.add("odaiko", tt, 0, None, S.vj(0.28 + 0.45 * u))
        tt += beat / 2
        i += 1
    # ---------------------------------------------------------------- overhead block -> the flurry (S11 end, S12)
    S.add("odaiko", t_ov, 0, None, 0.95, role="accent")
    S.add("odaiko_lo", t_ov, 0, None, 0.95, role="accent")
    S.add("hyoshigi", t_ov, 0, None, 0.72, role="accent")
    S.add("sub", t_ov, 0, None, 0.65, f0=D1, role="accent")
    S.add("strings", t_ov, 0.9, [38, 45, 50, 57], 0.62, mode="sfz", release=0.3, role="accent")
    # the elder's theme in the low strings, from the block (first note on the accent) to the blade lock
    t_ten = G.t(b_ov)
    for j, (b, nbt, m) in enumerate(motif("tenko", octave=-1)):
        ts = t_ov if j == 0 else t_ten + b * beat
        te = t_ten + (b + nbt) * beat
        if ts >= t_bl - 0.05:
            break
        S.add("strings", ts, max(0.1, min(te, t_bl) - ts) * 0.98, [m, m - 12], 0.5, mode="sustain", attack=0.06,
              release=0.25)
    t_flurry0 = G.next_step(t_ov, 2, fr)
    for k in range(b_ov, b_shove + 1):
        tb, te = G.t(k), G.t(k + 1)
        if tb >= t_pd:
            break
        pat_end = min(te, t_bl)
        if tb < pat_end:
            S.pattern("odaiko", G, k, "X.x.X.x.X.x.X.xx", 0.72, t_from=max(tb, t_flurry0), t_to=pat_end)
            S.pattern("odaiko_lo", G, k, "X...X...X...X...", 0.66, t_from=max(tb, t_flurry0), t_to=pat_end)
            S.pattern("shime", G, k, "XxxxXxxxXxxxXxxx", 0.5, t_from=max(tb, t_flurry0), t_to=pat_end, role="bed")
            for i, (_, _, m) in enumerate(ost):
                t = G.t(k, 0.5 * i)
                if max(tb, t_flurry0) - 1e-6 <= t < pat_end:
                    S.add("koto", S.hum(t), 1.0, m, S.vj(0.34 if i else 0.42), role="bed", bright=0.25, eq=OST_EQ)
            if k > b_ov and G.t(k, 2.5) < pat_end:
                S.line("koto2", G.t(k, 0), beat, saku_home(shift=k - b_ov), 0.48, ring=1.0, t_to=pat_end, bright=0.45)
                S.line("koto2", G.t(k, 2.5), beat, motif("saku", shift=k - b_ov, frag=slice(0, 5)), 0.42, ring=1.0,
                       t_to=pat_end, bright=0.45)
            if tb >= t_ov + fr:
                S.add("shakuhachi", tb, 0.32, 74, 0.55, muraiki=0.9, attack="plain", release=0.08, bright=0.4)
    # blade lock: the half-step grinding (D-Eb), everything tightening into the shove
    if t_shove - t_bl > 0.3:
        S.add("strings", t_bl, t_shove - t_bl, [50, 51], 0.5, mode="tremolo", attack=0.3, release=0.05, role="pad")
        tt = G.next_step(t_bl, 4, fr)
        while tt < t_shove - 0.02:
            u = (tt - t_bl) / (t_shove - t_bl)
            S.add("shime", tt, 0, None, S.vj(0.22 + 0.5 * u), role="bed")
            tt += beat / 4
        S.add("swell", t_shove, min(2.0, t_shove - t_bl), None, 0.3)
    # the shove (a routine beat: below the story hits), the elder's first two-handed overhead, the perfect deflect
    S.add("odaiko", t_shove, 0, None, 0.8, role="accent")
    S.add("odaiko_lo", t_shove, 0, None, 0.72, role="accent")
    S.add("strings", t_shove, 0.6, [38, 45], 0.5, mode="sfz", release=0.3, role="accent")
    ovh = first_event(doc, "whoosh", t_shove + 0.3, t_pd - 0.05)
    t_h = ovh["t"] if ovh else G.t(b_shove, 2)
    S.mark("overhead_2h", t_h, ovh["t"] if ovh else None, "whoosh event" if ovh else "default", G)
    tt = G.next_step(t_shove, 2, fr)
    while tt < min(t_h, t_pd) - 0.05:
        u = (tt - t_shove) / max(t_pd - t_shove, 1e-3)
        S.add("shime", tt, 0, None, S.vj(0.24 + 0.36 * u), role="bed")
        tt += beat / 4
    if t_h < t_pd - 0.1:
        S.add("odaiko", t_h, 0, None, 0.7, role="accent")
        S.add("strings", t_h, t_pd - t_h, [57, 58], 0.4, mode="tremolo", attack=0.1, release=0.05, role="pad")
        S.add("shakuhachi", t_h, t_pd - t_h, 69, 0.4, attack="meri", bend=-150, muraiki=0.5, glide_to=(0.25, _hz(70)))
    # suspended through the slow motion, pianissimo: glassy high tremolo, the sigh on the shakuhachi (flutter)
    S.mark("perfect_deflect", t_pd, t_pd if cue_src(doc, "perfect_deflect") != "config" else None,
           cue_src(doc, "perfect_deflect"), G)
    S.add("strings_hi", t_pd + 0.15, max(0.5, t_hc - t_pd - 0.15), [69, 70, 74], 0.12, mode="tremolo", attack=0.5,
          release=0.1, tone="ponticello")
    S.add("shakuhachi", t_pd + 0.45, max(0.4, (t_hc - t_pd) * 0.42), 75, 0.17, flutter=0.6, attack="kari", bright=0.3)
    S.add("shakuhachi", t_pd + 0.45 + (t_hc - t_pd) * 0.48, max(0.3, (t_hc - t_pd) * 0.38), 74, 0.15, flutter=0.3,
          fall=90, bright=0.3)
    S.add("swell", t_hc, min(1.4, t_hc - t_pd), None, 0.3)
    # ---------------------------------------------------------------- the hat cut: the stinger (exact)
    S.mark("hat_cut", t_hc, t_hc if cue_src(doc, "hat_cut") != "config" else None, cue_src(doc, "hat_cut"))  # off-grid by design
    S.hit(t_hc, 1.0, "D", big=True, hyoshigi=True, str_dur=1.3, swell_to=0.15, send_big={"hall": 0.2, "huge": 0.3})
    S.add("strings", t_hc, 1.3, [51], 0.5, mode="sfz", swell_to=0.15, release=1.0, role="accent")   # the Eb rub
    S.add("strings_hi", t_hc, 0.9, [74, 75, 81], 0.26, mode="tremolo", attack=0.01, release=0.9)
    # ---------------------------------------------------------------- S13 tail / S14: tension -- drone + heartbeat
    t_ten0, t_ten1 = t_hc + 0.9, t_sd - 0.05
    if t_ten1 - t_ten0 > 2.0:
        S.add("strings", t_ten0 - 0.3, t_ten1 - t_ten0 + 0.3, [26, 38], 0.38, mode="swell", release=0.25, role="pad")
        S.add("strings", t_ten0, t_ten1 - t_ten0, [38, 45], 0.18, mode="sustain", attack=1.5, release=0.3, role="pad")
        S.add("strings_hi", t_ten0 + 0.8, t_ten1 - t_ten0 - 0.8, [74, 75], 0.13, mode="tremolo", attack=1.2,
              release=0.2, trem_rate=9.0, tone="ponticello", role="pad")
        if not events_in(doc, ("heartbeat",), t_ten0 - 1.0, t_ten1):
            tt = t_ten0 + 0.35
            while tt < t_ten1 - 0.3:
                u = (tt - t_ten0) / (t_ten1 - t_ten0)
                S.add("heart", tt, 0, None, S.vj(0.5 + 0.3 * u, 0.03))
                tt += 60.0 / (60.0 + 22.0 * u)
        b0 = G.bar_at(t_ten0) + 1
        for k in range(b0, nb):
            if G.t(k) < t_ten1 - 0.4:
                S.add("odaiko_lo", G.t(k), 0, None, S.vj(0.36 + 0.04 * (k - b0)))
        # the sigh (Eb -> D), breathed on the shakuhachi as the haori falls
        hs = first_event(doc, "haori_shed", t_ten0, t_ten1)
        t_sig = (hs["t"] + 0.25) if hs else (t_ten0 + 0.45 * (t_ten1 - t_ten0))
        if t_sig + 2.2 < t_ten1:
            S.add("shakuhachi", t_sig, 1.1, 75, 0.32, attack="meri", bend=-80, muraiki=0.35, yuri=0.4, breath=1.4,
                  bright=0.4)
            S.add("shakuhachi", t_sig + 1.1, 1.2, 74, 0.28, attack="plain", fall=110, breath=1.4, release=0.3, bright=0.4)
    else:
        tt = G.next_step(t_hc, 2, fr)
        while tt < min(t_sd, G.t(b_hc + 1)) - 0.02:
            S.add("shime", tt, 0, None, S.vj(0.45), role="bed")
            tt += beat / 2
    # ---------------------------------------------------------------- the spear draw: the build into act II
    # (a routine accent, then a crescendo that STOPS a breath before the downbeat -- the downbeat is the story hit)
    t_br = t_end - A2_BREATH
    S.add("shakuhachi", t_sd, 0.9, 74, 0.55, muraiki=1.0, attack="meri", bend=-200, fall=250, bright=0.3)
    S.add("odaiko", t_sd, 0, None, 0.75, role="accent")
    S.add("odaiko_lo", t_sd, 0, None, 0.7, role="accent")
    S.add("strings", t_sd, max(0.5, t_br - t_sd), [38, 45, 50], 0.46, mode="swell", release=0.05)
    tt = G.next_step(t_sd, 2, fr)
    while tt < t_br - 0.03:
        u = (tt - t_sd) / max(t_br - t_sd, 1e-3)
        S.add("odaiko", tt, 0, None, S.vj(0.32 + 0.38 * u))
        S.add("shime", tt, 0, None, S.vj(0.28 + 0.36 * u), role="bed")
        S.add("shime", tt + beat / 8, 0, None, S.vj(0.2 + 0.3 * u), role="bed")
        tt += beat / 2 if u < 0.45 else beat / 4
    S.add("swell", t_end, min(2.0, t_end - t_sd), None, 0.4)
    return dict(grass_shear=t_gs, overhead=t_ov, blade_lock=t_bl, shove=t_shove, perfect_deflect=t_pd,
                hat_cut=t_hc, spear_draw=t_sd, tension=(round(t_ten0, 3), round(t_ten1, 3)), breath=round(t_br, 3))


def arr_act2(S, doc, C, G):
    """120 BPM, 18 bars: eruption / onslaught / kunai / close quarters / javelin / thunder / rain.
    Bass plan: G and A pedals, the bass sighing Bb -> A."""
    nb = G.nbars
    beat = G.beat
    fr = 1.0 / doc.fps
    t_end = G.t(nb)
    t_th = C.get("thunder_first", G.t(15))
    t_rain = C.get("rain_start", G.t(16))
    b_th = G.bar_at(t_th + 0.01)
    b_rain = G.bar_at(t_rain + 0.01)

    def shamisen_riff(k, bass, vel=0.6):
        mot = motif("tenko", octave=-1, aug=0.5, shift=RIFF_SHIFT[bass])
        for i, (b, nbt, m) in enumerate(mot):
            if b >= 4.0:
                break
            t = G.t(k, b)
            if nbt >= 1.0:           # tsugaru-style: long notes as repeated 16ths
                for j in range(int(round(min(nbt, 4.0 - b) * 4))):
                    S.add("shamisen", S.hum(t + j * beat / 4), 0.3, m, S.vj(vel * (1.0 if j == 0 else 0.6)), role="bed")
            else:
                S.add("shamisen", S.hum(t), max(0.25, nbt * beat * 1.4), m, S.vj(vel * 0.9))

    def pedal(k, bass, vel=0.4, mode="spiccato"):
        v = VOICING[bass][:3]
        if mode == "spiccato":
            for i in range(8):
                acc = 1.0 if i in (0, 3, 6) else 0.6
                S.add("strings", S.hum(G.t(k, 0.5 * i)), beat * 0.45, v[1:], S.vj(vel * acc), mode="spiccato")
            S.add("strings", G.t(k), G.bar_len - 0.05, v[:1], vel * 0.8, mode="sustain", attack=0.08, release=0.2,
                  role="pad")
        else:
            S.add("strings", G.t(k), G.bar_len - 0.05, v, vel, mode=mode, attack=0.08, release=0.15, role="pad")

    # bar 0-1: eruption (fire ring) on G -- the downbeat is a story hit (exact: it is the grid anchor)
    S.mark("act2_start", G.t0, G.t0 if cue_src(doc, "act2_start") != "config" else None, cue_src(doc, "act2_start"))
    S.hit(G.t(0), 1.0, "G", big=True, hyoshigi=True, str_dur=G.bar_len * 2 - 0.1, swell_to=0.8,
          send_big={"huge": 0.3, "hall": 0.12})
    for i, m in enumerate((43, 50, 55)):
        S.add("shamisen", G.t(0) + 0.018 * i, 0.9, m, 0.75, role="accent")
    tt = G.t(0, 1)
    while tt < G.t(2) - 0.01:
        u = (tt - G.t(0, 1)) / (G.t(2) - G.t(0, 1))
        S.add("shamisen", S.hum(tt, 0.003), 0.28, 43, S.vj(0.3 + 0.35 * u), sawari=0.6, role="bed")
        tt += beat / 4
    S.pattern("odaiko", G, 0, "X.......X..x.X..", 0.72, t_from=G.t(0, 0.1))
    S.pattern("odaiko", G, 1, "X..x..X.X..x.xxx", 0.78)
    S.pattern("odaiko_lo", G, 1, "X.......X.......", 0.72)
    S.pattern("shime", G, 1, "........XxxxXxxx", 0.55, role="bed")
    # bars 2..: onslaught (S16) / kunai (S17) / close quarters (S18) / javelin (S19)
    ten_aug = motif("tenko", octave=-1, aug=2.0)        # 18 beats in the low strings (S18)
    s16_0 = s18_0 = None
    for k in range(2, nb):
        tb = G.t(k)
        sid = shot_id_at(doc, tb + G.bar_len / 2)
        if k >= b_th:
            break
        if sid in ("S16", "S15"):
            s16_0 = k if s16_0 is None else s16_0
            j = k - s16_0
            bass = ["G", "G", "Bb", "A"][min(j, 3)] if j < 4 else ("G" if j % 2 == 0 else "A")
            S.pattern("odaiko", G, k, "X..x..X.X..x..X.", 0.72)
            S.pattern("odaiko_lo", G, k, "X.......X.......", 0.7)
            S.pattern("shime", G, k, "XxoxXxoxXxoxXxox", 0.46, role="bed")
            shamisen_riff(k, bass)
            pedal(k, bass, 0.38)
            if bass in ("Bb", "A") and j in (2, 3):                 # the bass sigh Bb -> A, doubled by the cellos
                S.add("strings", tb, G.bar_len - 0.05, [VOICING[bass][0] + 12], 0.34, mode="sustain", attack=0.1,
                      release=0.2)
        elif sid == "S17":
            S.pattern("odaiko", G, k, "X..x..x.X.x.x.X.", 0.72)
            S.pattern("odaiko_lo", G, k, "X.......X.......", 0.66)
            S.pattern("shime", G, k, "XxxxXxoxXxxxXxox", 0.46, role="bed")
            shamisen_riff(k, "A", 0.5)
            pedal(k, "A", 0.34, mode="sustain")
            S.line("koto", G.t(k, 0), beat, saku_home(shift=(k % 3)), 0.55, ring=0.9, bright=0.45)
            S.line("koto2", G.t(k, 2.0), beat, motif("saku", shift=(k % 3)), 0.45, ring=0.9, bright=0.4)
        elif sid == "S18":
            s18_0 = k if s18_0 is None else s18_0
            j = k - s18_0
            bass = ["G", "G", "Bb", "A"][min(j, 3)]
            S.pattern("odaiko", G, k, "X.x.X.x.X.x.X.x.", 0.76)
            S.pattern("odaiko_lo", G, k, "X...X...X...X...", 0.7)
            S.pattern("shime", G, k, "XxxxXxxxXxxxXxxx", 0.5, role="bed")
            shamisen_riff(k, bass, 0.58)
            S.add("strings", tb, G.bar_len - 0.05, [VOICING[bass][0], VOICING[bass][0] + 12], 0.36, mode="sustain",
                  attack=0.1, release=0.2, role="pad")
            S.line("koto", G.t(k, 3.0), beat, saku_home(frag=slice(3, 7)), 0.45, ring=0.8, bright=0.4)
            if j == 0:
                t_stop = shot_t(doc, "S19", t_th)
                t_stop = G.t(G.bar_at(t_stop - 0.4) + 1) if t_stop is not None else t_th
                for (b, nbt, m) in ten_aug:
                    ts = tb + b * beat
                    if ts >= t_stop - 0.1:
                        break
                    S.add("strings", ts, min(nbt * beat, t_stop - ts) * 0.97, [m + 12], 0.46, mode="sustain",
                          attack=0.12, release=0.3)
            if shot_id_at(doc, G.t(k + 1) + 0.5) != "S18":
                S.add("hyoshigi", G.t(k, 3), 0, None, 0.62)
        else:   # S19: the javelin, the deflect (speed ramp), into the flames
            first = shot_id_at(doc, G.t(k - 1) + 0.5) != sid
            if first:
                S.add("odaiko_lo", tb, 0, None, 0.8)
                S.add("strings", tb, G.bar_len - 0.05, [43, 50, 58], 0.46, mode="sustain", attack=0.1, release=0.3)
                dfl = strongest_event(doc, ("clash", "clash_heavy"), tb, tb + G.bar_len * 2, 0.8)
                t_d = dfl["t"] if dfl else G.t(k, 2)
                S.mark("javelin_deflect", t_d, dfl["t"] if dfl else None, f"{dfl['type']} event" if dfl else "default", G)
                S.add("odaiko", t_d, 0, None, 0.85, role="accent")
                S.add("shakuhachi", t_d + 0.05, 0.5, 74, 0.6, muraiki=0.9, attack="meri", bend=-180, bright=0.3)
                S.add("shakuhachi", t_d + 0.6, 0.7, 75, 0.54, attack="kari", muraiki=0.4, bright=0.3)
                S.add("shakuhachi", t_d + 1.35, 1.1, 74, 0.5, fall=150, bright=0.3)
            else:
                S.add("strings", tb, G.bar_len - 0.05, [45, 51, 57], 0.42, mode="tremolo", attack=0.3, release=0.1,
                      role="pad")
                tt = G.t(k, 2)
                while tt < G.t(k + 1) - 0.02:
                    u = (tt - G.t(k, 2)) / (2 * beat)
                    S.add("shime", tt, 0, None, S.vj(0.22 + 0.45 * u), role="bed")
                    tt += beat / 4
    # thunder: the storm arrives (A, the tritone Eb above)
    S.mark("thunder_first", t_th, t_th if cue_src(doc, "thunder_first") != "config" else None,
           cue_src(doc, "thunder_first"), G)
    S.add("odaiko", t_th, 0, None, 0.9, role="accent")
    S.add("odaiko_lo", t_th, 0, None, 0.9, role="accent")
    S.add("sub", t_th, 0, None, 0.6, f0=A1, role="accent")
    S.add("strings", t_th, max(0.5, t_rain - t_th), VOICING["A_eb"], 0.4, mode="tremolo", attack=0.05, release=0.2,
          role="pad")
    # the downpour hits on the cut; then the act THINS towards the Raikiri: two bars of rain, low drum, the storm
    # tremolo growing, the oroshi strokes, then the breath -- everything stops, only the inhale remains
    S.mark("rain_start", t_rain, t_rain if cue_src(doc, "rain_start") != "config" else None, cue_src(doc, "rain_start"), G)
    S.add("odaiko", t_rain, 0, None, 0.85, role="accent")
    S.add("odaiko_lo", t_rain, 0, None, 0.85, role="accent")
    t_br = t_end - BREATH
    S.add("strings", t_rain, max(0.5, t_br - t_rain), [33, 45, 46], 0.42, mode="tremolo", attack=0.05, release=0.04,
          role="pad")
    S.add("strings_hi", t_rain + 0.5, max(0.5, t_br - t_rain - 0.5), [69, 70], 0.14, mode="tremolo", attack=1.5,
          release=0.04, tone="ponticello", role="pad")
    k = b_rain
    while G.t(k) < t_end - 0.05:
        last = G.t(k + 1) >= t_end - 0.05
        if not last:
            S.pattern("odaiko_lo", G, k, "X.......X.......", 0.6, t_from=G.next_step(t_rain, 2, fr))
        else:
            # oroshi: accelerating strokes into the raikiri ... then the breath
            tt = G.t(k)
            gap = beat * 0.9
            while tt < t_br - 0.03:
                u = (tt - G.t(k)) / G.bar_len
                S.add("odaiko", tt, 0, None, S.vj(0.3 + 0.4 * u))
                tt += gap
                gap = max(0.06, gap * 0.8)
        k += 1
    S.add("swell", t_end, 1.3, None, 0.36)
    return dict(thunder_first=t_th, rain_start=t_rain, breath=round(t_br, 3))


def arr_act3(S, doc, C, G, G2=None):
    """140 BPM from the Raikiri to the low point (grid G) and from the low point to the hard stop (grid G2).
    One scale step up (Eb over Bb) -> A -> D at the low point."""
    beat = G.beat
    fr = 1.0 / doc.fps
    lp = first_event(doc, "rain_split", G.t0, G.t_end + 4.0, tag="low_point") or \
        first_event(doc, "clash_heavy", G.t0, G.t_end + 4.0, tag="low_point")
    t_low = C.get("low_point", G.t(11))
    if G2 is not None:
        t_low = G2.t0
    b_low = G.nbars if G2 is not None else G.bar_near(t_low)
    t_end = G2.t(G2.nbars) if G2 is not None else G.t(G.nbars)
    t_end = min(t_end, C.get("silence", t_end))
    S.mark("low_point", t_low, t_low if cue_src(doc, "low_point") != "config" else (lp["t"] if lp else None),
           cue_src(doc, "low_point"), G)
    # bar 0: the Raikiri -- Eb major over Bb (one step above the home key), choir, the big drum on G1
    S.mark("raikiri", G.t0, G.t0 if cue_src(doc, "raikiri") != "config" else None, cue_src(doc, "raikiri"))
    S.hit(G.t(0), 1.05, "EbBb", big=True, hyoshigi=True, str_dur=G.bar_len * 2 - 0.1, str_vel=0.72, swell_to=0.6,
          send_big={"huge": 0.4, "hall": 0.1})
    S.add("odaiko_lo", G.t(0) + 0.03, 0, None, 0.55, role="accent")
    S.add("choir", G.t(0), G.bar_len * 2 - 0.2, [51, 55, 58, 63], 0.66, vowel="a", vowel_to="o", attack=0.08,
          release=0.4, morph=(0.2, 0.9))
    S.pattern("odaiko", G, 1, "X.......X.......", 0.66)
    S.add("strings", G.t(1), G.bar_len, VOICING["Bb"], 0.44, mode="tremolo", attack=0.1, release=0.1, role="pad")
    ten2 = motif("tenko", aug=2.0, shift=1)             # the storm sings the elder's theme, a step up (18 beats)
    b_strobe = b_22b = None
    for k in range(2, b_low):
        tb = G.t(k)
        sid = shot_id_at(doc, tb + G.bar_len / 2)
        if sid == "S22":
            if b_strobe is None:
                b_strobe = k
                for (b, nbt, m) in ten2:
                    ts = tb + b * beat
                    if ts < G.t(k + 5) - 0.1:
                        S.add("choir", ts, min(nbt * beat, G.t(k + 5) - ts) * 0.98, [m, m - 12], 0.44, vowel="a",
                              vowel_to="o", attack=0.12, release=0.3)
            j = k - b_strobe
            bass = "Bb" if j < 3 else "A_eb"
            S.pattern("odaiko", G, k, "X.x.X.x.X.x.X.x.", 0.76)
            S.pattern("odaiko_lo", G, k, "X...X...X...X...", 0.7)
            S.pattern("shime", G, k, "XxxxXxxxXxxxXxxx", 0.5, role="bed")
            S.add("strings", tb, G.bar_len - 0.03, VOICING[bass], 0.52, mode="tremolo", attack=0.05, release=0.08,
                  role="pad")
            S.add("strings_hi", tb, G.bar_len - 0.03, [75, 82] if bass == "Bb" else [75, 81], 0.16, mode="tremolo",
                  attack=0.05, release=0.08, tone="ponticello", role="pad")
            S.line("koto", G.t(k, 0), beat, saku_home(shift=(j % 3) + 1), 0.52, ring=0.8, bright=0.45)
            S.line("koto2", G.t(k, 2.5), beat, saku_home(shift=(j % 3), frag=slice(0, 5), octave=-1), 0.42, ring=0.8,
                   bright=0.4)
            # the storm's shamisen: the tenko riff on the bass of the moment, long notes as tsugaru 16ths
            for i, (b, nbt, m) in enumerate(motif("tenko", octave=-1, aug=0.5, shift=RIFF_SHIFT[bass])):
                if b >= 4.0:
                    break
                if nbt >= 1.0:
                    for q in range(int(round(min(nbt, 4.0 - b) * 4))):
                        S.add("shamisen", S.hum(G.t(k, b + q / 4)), 0.28, m, S.vj(0.5 if q == 0 else 0.32), role="bed")
                else:
                    S.add("shamisen", S.hum(G.t(k, b)), max(0.25, nbt * beat * 1.4), m, S.vj(0.46))
        elif sid == "S22b":
            # the shinobi's counter-attack: FULL TUTTI on A (the A-Eb tritone) -- the arrangement peak of the film
            b_22b = k if b_22b is None else b_22b
            j = k - b_22b
            S.pattern("odaiko", G, k, "X.x.X.xxX.x.X.xx", 0.8)
            S.pattern("odaiko_lo", G, k, "X...X...X...X...", 0.74)
            S.pattern("shime", G, k, "XxxxXxxxXxxxXxxx", 0.54, role="bed")
            S.add("strings", tb, G.bar_len - 0.03, VOICING["A_eb"], 0.55, mode="tremolo", attack=0.05, release=0.08,
                  role="pad")
            S.add("strings_hi", tb, G.bar_len - 0.03, [75, 81], 0.2, mode="tremolo", attack=0.05, release=0.08,
                  tone="ponticello", role="pad")
            S.add("choir", tb, G.bar_len - 0.05, [57, 63, 69], 0.42, vowel="a", vowel_to="o", attack=0.1, release=0.15,
                  role="pad")
            for i, (b, nbt, m) in enumerate(motif("tenko", octave=-1, aug=0.5, shift=3)):
                if b >= 4.0:
                    break
                if nbt >= 1.0:
                    for q in range(int(round(min(nbt, 4.0 - b) * 4))):
                        S.add("shamisen", S.hum(G.t(k, b + q / 4)), 0.28, m, S.vj(0.58 if q == 0 else 0.36), role="bed")
                else:
                    S.add("shamisen", S.hum(G.t(k, b)), max(0.25, nbt * beat * 1.4), m, S.vj(0.52))
            S.line("koto", G.t(k, 0), beat, saku_home(shift=2 + j % 2), 0.62, ring=0.8, bright=0.5)
            S.line("koto2", G.t(k, 0), beat, saku_home(shift=2 + j % 2, octave=-1), 0.46, ring=0.8, bright=0.45)
            S.line("koto", G.t(k, 2.5), beat, saku_home(shift=3 + j % 2, frag=slice(0, 5)), 0.56, ring=0.8, bright=0.5)
        else:
            # S23 up to the low point: the elder gathers into jodan -- SUBITO piano after the tutti, then a
            # crescendo of the whole storm (A under a Bb rub), cut off a breath before the blow
            u0 = (k - (b_low - 2)) / 2.0
            t_stop = t_low - 0.18
            tt = tb
            while tt < min(G.t(k + 1), t_stop) - 0.01:
                u = u0 + (tt - tb) / G.bar_len / 2.0
                S.add("odaiko_lo", tt, 0, None, S.vj(0.3 + 0.45 * u))
                tt += beat
            tt = tb if k == b_low - 1 else G.t(k, 2)
            while tt < min(G.t(k + 1), t_stop) - 0.01:
                u = (tt - tb) / G.bar_len
                S.add("shime", tt, 0, None, S.vj(0.18 + 0.45 * (u0 + u / 2)), role="bed")
                tt += beat / 4
            if k == b_low - 2 or (k == b_low - 1 and b_low - 2 < 2):
                dur = t_stop - tb
                S.add("strings", tb, dur, [33, 45, 46], 0.5, mode="tremolo", attack=dur * 0.7, release=0.05, role="pad")
                S.add("choir", tb, dur, [57, 58, 63], 0.4, vowel="o", vowel_to="a", attack=dur * 0.75, release=0.05,
                      swell=1.0, morph=(0.3, 0.95), role="pad")
    S.add("swell", t_low, 2.0, None, 0.42)
    # the low point: D -- the arrival (the only D bass of Act III)
    S.hit(t_low, 1.05, "D", big=True, str_dur=G.bar_len, str_vel=0.78, swell_to=0.4,
          send_big={"huge": 0.35, "hall": 0.1})
    S.add("choir", t_low, G.bar_len * 1.1, [50, 57, 62], 0.6, vowel="a", vowel_to="o", attack=0.05, release=0.7,
          morph=(0.2, 1.0))
    # the shinobi down on one knee; the elder's two unhurried steps (exact); the elder's theme, low and grave
    tt = (G2.t(0, 2) if G2 is not None else G.t(b_low, 2))
    for (b, nbt, m) in motif("tenko", octave=-1):
        ts = tt + b * beat
        if ts >= t_end - 0.1:
            break
        S.add("strings", ts, min(nbt * beat, t_end - ts - 0.02), [m, m - 12], 0.5, mode="sustain", attack=0.1,
              release=0.1)
    S.add("strings", t_low + beat * 2, max(0.5, t_end - t_low - beat * 2 - 0.02), [38, 45], 0.2, mode="sustain",
          attack=1.0, release=0.02, role="pad")
    steps = [e for e in events_in(doc, ("step",), t_low + 1.0, t_end) if e.get("who") == "saint"][:2]
    if steps:
        for i, e in enumerate(steps):
            S.mark(f"saint_step_{i + 1}", e["t"], e["t"], "step event")            # free time: no grid
            S.add("odaiko_lo", e["t"], 0, None, 0.72, role="accent")
    else:
        for ts in ((G2 or G).t(1, 2), (G2 or G).t(2, 1)) if G2 is not None else (G.t(b_low + 1, 2), G.t(b_low + 2, 1)):
            if ts < t_end - 0.1:
                S.add("odaiko_lo", ts, 0, None, 0.72)
    return dict(low_point=t_low)


def arr_final_pass(S, doc, C):
    t = C["final_pass"]
    S.mark("final_pass", t, t if cue_src(doc, "final_pass") != "config" else None, cue_src(doc, "final_pass"))
    # the one unified hit: D1 drum, D2 drum, sub, noise burst, D-A-D-A strings -- into the 'huge' tail.  No bell
    # under the killing blow (a sustained bell hum after the hit would be a gong-like kill sting).
    S.add("odaiko_lo", t, 0, None, 1.15, size=1.65, tone=0.42, f0=D1, send={"huge": 0.45, "hall": 0.1}, role="accent")
    S.add("odaiko", t, 0, None, 1.0, send={"huge": 0.4}, role="accent")
    S.add("sub", t, 2.4, None, 1.0, f0=D1, role="accent")
    S.add("noise_hit", t, 2.0, None, 0.9, tau=0.45, role="accent")
    S.add("strings", t, 5.5, [26, 38, 45, 50, 57], 0.9, mode="sfz", sfz_drop=0.6, swell_to=0.25, release=2.6,
          send={"huge": 0.4}, role="accent")
    ep = C.get("epilogue", t + 8.0)
    S.add("strings", t + 3.2, max(1.0, ep - t - 2.0), [38], 0.16, mode="swell", release=1.5, eq=EPI_EQ)
    # the payoff: the blade snaps with the third click -- solo shakuhachi answers with the elder's sigh
    # (tenko fragment D4 Eb4 D4) over the low D, before the moonlit yo epilogue
    sb = first_event(doc, "sword_break", t, ep)
    t_sb = sb["t"] if sb else t + 112.0 / doc.fps
    S.mark("sword_break_answer", t_sb + 0.35, None, "sword_break event (+0.35 s, free)" if sb else "default")
    S.add("strings", t_sb, max(1.0, ep - t_sb + 0.5), [50], 0.12, mode="swell", release=1.2, eq=EPI_EQ)
    beat = 0.72
    tt = t_sb + 0.35
    arts = [dict(attack="plain", vib_depth=6), dict(attack="meri", bend=-110, bend_time=0.25, vib_delay=0.5, swell=0.35),
            dict(attack="plain", fall=130, vib_depth=16, vib_delay=0.6, swell=0.3, release=0.6)]
    for (b, nb, m), art, st in zip(motif("tenko", frag=slice(3, 6)), arts, [1.2, 1.1, 1.0]):
        d = nb * beat * st
        S.add("shakuhachi", tt, d, m, 0.26, bright=0.35, eq=EPI_EQ, **art)
        tt += d + 0.05
    S.add("strings", ep - 3.0, 3.8, [50, 57], 0.14, mode="swell", release=1.6, eq=EPI_EQ)


def arr_epilogue(S, doc, C):
    ep = C["epilogue"]
    ec = C.get("end_card", ep + 10.5)
    S.add("strings", ep, max(3.0, ec - ep + 0.8), [50, 57, 64], 0.24, mode="swell", release=2.4, eq=EPI_EQ)
    beat = 0.85
    t = ep + 1.2
    arts = [dict(attack="meri", bend=-100, bend_time=0.22, vib_delay=0.6), dict(vib_depth=9), dict(yuri=0.5),
            dict(atari=200), dict(attack="kari", vib_depth=16), dict(vib_depth=14, swell=0.2, release=0.9)]
    for (b, nb, m), art, st, gap in zip(motif("tenko", scale="yo"), arts, [1.1, 0.95, 1.15, 0.9, 1.1, 1.05],
                                        [0.22, 0.0, 0.3, 0.0, 0.0, 0.0]):
        d = nb * beat * st
        S.add("shakuhachi", t, d, m, 0.27, bright=0.4, eq=EPI_EQ, **art)
        t += d + gap
    t_k = ep + 3.4
    for (b, nb, m) in saku_home(scale="yo", aug=2.0):
        S.add("koto", t_k + b * beat, 2.4, m, S.vj(0.2), bright=0.4)
    t_k2 = ep + 6.3
    for (b, nb, m) in motif("saku", scale="yo", aug=2.0, octave=-1):
        S.add("koto2", t_k2 + b * beat, 2.4, m, S.vj(0.17), bright=0.35)
    S.add("koto", ec - 1.0, 3.2, 50, 0.22, bright=0.4)
    S.add("koto2", ec - 0.98, 3.2, 57, 0.18, bright=0.4)
    S.mark("end_card", ec, ec if cue_src(doc, "end_card") != "config" else None, cue_src(doc, "end_card"))
    S.add("bell", ec, 10.0, 50, 0.5)


# =====================================================================================  hit points
def add_hit_points(S, doc, grids, drums_out=()):
    """let the drums catch on-grid impacts from the events -- at the EXACT event time (the SFX lands there), only
    if the event is within 45 ms of a 16th (it belongs to the groove) and no odaiko is already within 60 ms"""
    types = ("clash", "clash_heavy", "kunai_deflect", "kick")
    od = sorted(n["t"] for n in S.notes if n["inst"] in ("odaiko", "odaiko_lo"))
    od = np.array(od) if od else np.array([-1e9])
    added = []
    for G in grids:
        for e in events_in(doc, types, G.t0, G.t(G.nbars)):
            if any(a <= e["t"] < b for (a, b) in drums_out):
                continue
            if abs(G.q(e["t"], 4) - e["t"]) > 0.045:
                continue
            if np.min(np.abs(od - e["t"])) < 0.06:
                continue
            v = 0.5 + 0.22 * min(1.0, e["strength"])
            S.add("odaiko", e["t"], 0, None, v, role="accent")
            od = np.append(od, e["t"])
            added.append(round(e["t"], 4))
    return added


# =====================================================================================  render
def _sections(C, grids):
    g1, g2, g3 = grids["act1"], grids["act2"], grids["act3"]
    g3b = grids.get("act3_low")
    rows = [("prologue", 0.0, C["act1_start"]), ("act1_pre", C["act1_start"], g1.t0), ("act1", g1.t0, g1.t(g1.nbars)),
            ("act2", g2.t0, g2.t(g2.nbars)), ("act3", g3.t0, g3.t(g3.nbars))]
    if g3b is not None:
        rows.append(("act3_low", g3b.t0, min(g3b.t(g3b.nbars), C.get("silence", 1e9))))
    rows += [("silence", C["silence"], C["final_pass"]), ("final_pass", C["final_pass"], C["epilogue"]),
             ("epilogue", C["epilogue"], 1e9)]
    return rows


def render(doc, verbose=False, workers=None):
    N = doc.n_samples
    C = {k: v["t"] for k, v in doc.cues.items()}
    secs = {s["section"]: s for s in tl.tempo_sections(doc)}
    grids = {}
    for name in ("act1", "act2", "act3", "act3_low"):
        s = secs.get(name)
        if s:
            grids[name] = Grid(s["t_anchor"], s["bpm"], s["t_end"], nbars=s.get("bars"), name=name)
    S = Score(fps=doc.fps)
    arr_prologue(S, doc, C)
    arr_act1_pre(S, doc, C, grids["act1"])
    marks1 = arr_act1(S, doc, C, grids["act1"])
    marks2 = arr_act2(S, doc, C, grids["act2"])
    marks3 = arr_act3(S, doc, C, grids["act3"], grids.get("act3_low"))
    arr_final_pass(S, doc, C)
    arr_epilogue(S, doc, C)
    thin = [(marks1["perfect_deflect"], marks1["hat_cut"]), (marks1["breath"], grids["act1"].t(grids["act1"].nbars)),
            (marks2["breath"] - 1.2, grids["act2"].t(grids["act2"].nbars)), (marks3["low_point"] - 0.5, marks3["low_point"])]
    hits = add_hit_points(S, doc, list(grids.values()), drums_out=thin)
    sec_rows = _sections(C, grids)

    def sec_of(t):
        for name, a, b in sec_rows:
            if a <= t < b:
                return name
        return None
    # ---------------------------------------------------------------- render notes
    dry = np.zeros((2, N))
    sends = {k: np.zeros((2, N), dtype=np.float32) for k in ("hall", "temple", "huge")}
    counts = {}
    notes = sorted(S.notes, key=lambda x: x["t"])
    choke_at = _choke_times(notes)
    for i, n in enumerate(notes):
        tr = TRACKS[n["inst"]]
        r = dsp.rng("note", n["inst"], round(n["t"], 4), str(n["midi"]), i)
        a, anc = render_note(n, r)
        if choke_at[i] is not None:
            a = _choke(a, anc + n_of(choke_at[i]), CHOKE[n["inst"]][0])
        if n["kw"].get("eq"):
            a = dsp.eq_chain(a, n["kw"]["eq"])
        pan = n["kw"].get("pan", tr["pan"])
        gain = n["kw"].get("gain", tr["gain"])
        if n["role"]:
            gain *= float(dsp.db2lin(ROLE_TRIM_DB.get(sec_of(n["t"]), {}).get(n["role"], 0.0)))
        if a.ndim == 1:
            st = dsp.pan_mono(a, pan)
        else:
            st = dsp.pan_stereo(a, pan, n["kw"].get("width", tr["width"]))
        st *= gain
        start = int(round(n["t"] * SR)) - anc
        dsp.place(dry, st, start)
        for k, lv in (n["kw"].get("send") or tr["send"]).items():
            dsp.place(sends[k], st, start, lv)
        counts[n["inst"]] = counts.get(n["inst"], 0) + 1
    for k in list(sends):
        buf = sends.pop(k)
        if np.any(buf):
            dry += dsp.convolve_reverb(buf, k, seed=3)
        del buf
    stem = dsp.highpass(dry, 30.0, 2)
    del dry
    # the music bus: low shelf (the drums' sub lives in the sub), a slight presence dip, a little air on top
    stem = dsp.eq_chain(stem, [("lowshelf", 110.0, -3.5, 0.7), ("peak", 2500.0, -1.0, 0.8), ("highshelf", 6000.0, 2.0, 0.7)])
    # ---------------------------------------------------------------- section automation (dB), 0.6 s ramps
    auto = [(0.0, SECTION_GAIN_DB["prologue"]), (C["act1_start"], SECTION_GAIN_DB["act1_pre"]),
            (grids["act1"].t0, 0.0), (C["final_pass"], SECTION_GAIN_DB["final_pass"]),
            (C["epilogue"], SECTION_GAIN_DB["epilogue"])]
    tt = np.arange(0, N, 480) / SR
    gdb = np.zeros_like(tt)
    for (ta, g) in auto:
        gdb = np.where(tt >= ta, g, gdb)
    k = int(0.6 * SR / 480)
    gdb = np.convolve(np.pad(gdb, (k, k), mode="edge"), np.ones(k) / k, mode="same")[k:-k]
    stem *= dsp.db2lin(np.interp(np.arange(N) / SR, tt, gdb))
    # ---------------------------------------------------------------- hard silences + end
    sw = tl.silence_windows(doc)
    if "music" in sw:
        a, b = sw["music"]
        ia, ib = int(round(a * SR)), int(round(b * SR))
        fo = n_of(0.012)
        stem[:, max(0, ia - fo):ia] *= np.linspace(1.0, 0.0, min(fo, ia))
        stem[:, ia:ib] = 0.0
    sections = []
    for name, a, b in sec_rows:
        g = grids.get(name)
        sections.append(dict(name=name, t0=round(a, 3), t1=round(min(b, doc.duration), 3),
                             bpm=(round(g.bpm, 2) if g else None), bars=(g.nbars if g else None)))
    accents = sorted({round(n["t"], 4) for n in S.notes if n["role"] == "accent"})
    return dict(stem=stem, sections=sections, notes=len(S.notes), counts=counts, hits=hits,
                marks=dict(act1=marks1, act2=marks2, act3=marks3), event_marks=S.marks, accents=accents,
                warnings=S.warnings, pitched=[(n["t"], n["midi"], n["inst"]) for n in S.notes if n["midi"] is not None])
