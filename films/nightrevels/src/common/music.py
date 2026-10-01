"""
music.py - the score as data: note events shared by the choreography (playing paws) and the audio engine.

Each note: dict(frame, t, instr, midi, dur, vel, section, tech). Frames are fractional film frames.
Instruments: pipa, drum, clapper, dizi_a / dizi_b / dizi_fold, bili, guqin, bell.
Modes: gong pentatonic on D (D E F# A B); the night pieces use the same notes centred on B (yu mode).
"""
import config as C

G = C.SCALE_GONG


def pitch(deg, octv=0, base=C.TONIC_MIDI):
    o, d = divmod(deg, 5)
    return base + 12 * (octv + o) + G[d]


class Line:
    """Places notes on a beat grid starting at frame f0 with a (possibly accelerating) tempo."""

    def __init__(self, f0, bpm0, bpm1=None, beats_total=None):
        self.f0, self.bpm0, self.bpm1 = f0, bpm0, (bpm1 or bpm0)
        self.total = beats_total

    def frame(self, beat):
        if self.bpm1 == self.bpm0 or not self.total:
            return self.f0 + beat * C.FPS * 60.0 / self.bpm0
        # linear tempo ramp over `total` beats: t(b) = integral of 60/bpm(b) db
        import math
        k = (self.bpm1 - self.bpm0) / self.total
        b = min(beat, self.total)
        t = 60.0 / k * math.log((self.bpm0 + k * b) / self.bpm0)
        if beat > self.total:
            t += (beat - self.total) * 60.0 / self.bpm1
        return self.f0 + t * C.FPS


def melody(line, notes, instr, section, start_beat=0.0, octv=0, vel=0.7, tech=None, base=C.TONIC_MIDI):
    """notes: [(deg | None, beats)] or [(deg, octave_offset, beats)]."""
    out, b = [], start_beat
    for n in notes:
        if len(n) == 2:
            deg, beats = n
            oo = 0
        else:
            deg, oo, beats = n
        if deg is not None:
            f = line.frame(b)
            dur = (line.frame(b + beats) - f) / C.FPS
            out.append(dict(frame=f, instr=instr, midi=pitch(deg, octv + oo, base), dur=dur, vel=vel, section=section,
                            tech=(tech or ("tremolo" if instr == "pipa" and beats >= 1.0 else None))))
        b += beats
    return out, b


def build():
    N = []
    cue = C.CUE
    # ------------------------------------------------ prologue: guqin harmonics over silence
    L = Line(40, 60)
    for b, deg, o in ((0, 3, 0), (2, 0, 1), (3.5, 4, 0), (6, 3, 0), (8, 0, 0)):
        N.append(dict(frame=L.frame(b), instr="guqin", midi=pitch(deg, o - 1), dur=3.0, vel=0.55, section="prologue",
                      tech="harmonic" if b in (0, 6) else None))
    # ------------------------------------------------ scene 1: pipa solo, 76 bpm (the cup interrupts it)
    L = Line(cue["pipa_start"], C.TEMPO["listen"])
    a1 = [(4, -1, 0.5), (0, 0, 0.5), (1, 0, 1), (2, 0, 0.5), (1, 0, 0.5), (0, 0, 1),
          (3, 0, 1.5), (2, 0, 0.5), (1, 0, 1), (0, 0, 1)]
    a2 = [(2, 0, 0.5), (3, 0, 0.5), (4, 0, 1), (3, 0, 0.5), (2, 0, 0.5), (1, 0, 1),
          (0, 0, 0.5), (1, 0, 0.5), (2, 0, 0.5), (1, 0, 0.5), (0, 0, 2)]
    for part in (a1, a2):
        notes, _ = melody(L, part, "pipa", "listen", start_beat=0 if part is a1 else 8)
        N += notes
    b_in = [(4, 0, 0.75), (3, 0, 0.5)]
    notes, _ = melody(L, b_in, "pipa", "listen", start_beat=16)
    N += notes
    N.append(dict(frame=cue["sour_note"], instr="pipa", midi=pitch(2) + 1, dur=0.9, vel=0.85, section="listen",
                  tech="sour"))
    L2 = Line(cue["pipa_resume"], C.TEMPO["listen"])
    b_full = [(4, 0, 1), (3, 0, 0.5), (4, 0, 0.5), (0, 1, 1), (4, 0, 1),
              (3, 0, 0.5), (2, 0, 0.5), (1, 0, 1), (0, 0, 1.6)]
    notes, _ = melody(L2, b_full, "pipa", "listen")
    N += notes
    # ------------------------------------------------ scene 2: the Liuyao dance, accelerating 96 -> 132 bpm
    beats = 28.0
    L = Line(cue["drum_start"], C.TEMPO["dance"][0], C.TEMPO["dance"][1], beats)
    tune = [(0, 0.5), (1, 0.5), (2, 1), (4, 0.5), (3, 0.5), (2, 1),
            (1, 0.5), (2, 0.5), (3, 0.5), (2, 0.5), (1, 1), (0, 1)]
    b = 0.0
    while b < beats - 0.01:
        notes, b = melody(L, tune, "pipa", "dance", start_beat=b, octv=0, vel=0.62, tech="pluck")
        N += [n for n in notes if n["frame"] < cue["music_stop"] - 2]
    for i in range(int(beats)):
        f = L.frame(i)
        if f >= cue["music_stop"] - 2:
            break
        N.append(dict(frame=f, instr="drum", midi=0, dur=0.3, vel=0.95 if i % 4 == 0 else 0.7, section="dance",
                      tech="center" if i % 2 == 0 else "rim"))
        if i % 4 == 3:          # an off-beat fill
            N.append(dict(frame=L.frame(i + 0.5), instr="drum", midi=0, dur=0.2, vel=0.55, section="dance",
                          tech="rim"))
        if i % 2 == 0:
            N.append(dict(frame=f, instr="clapper", midi=0, dur=0.2, vel=0.8, section="dance", tech=None))
    # the landing: one great stroke + chord
    N.append(dict(frame=cue["land"], instr="drum", midi=0, dur=1.2, vel=1.0, section="dance", tech="final"))
    N.append(dict(frame=cue["land"], instr="clapper", midi=0, dur=0.3, vel=1.0, section="dance", tech=None))
    for m in (pitch(0, -1), pitch(3, -1), pitch(0), pitch(2)):
        N.append(dict(frame=cue["land"] + 1, instr="pipa", midi=m, dur=2.5, vel=0.85, section="dance", tech="chord"))
    # ------------------------------------------------ scene 3: sparse guqin (yu colour), 60 bpm
    L = Line(C.SECTIONS[3]["f0"] + 10, C.TEMPO["rest"])
    for b, deg, o, t in ((0, 4, -1, None), (2, 3, -1, None), (3, 1, -1, "slide"), (6, 4, -1, "harmonic"),
                         (9, 2, -1, None), (10, 1, -1, None), (11, 0, -1, None), (14, 4, -2, "harmonic")):
        N.append(dict(frame=L.frame(b), instr="guqin", midi=pitch(deg, o), dur=3.5, vel=0.5, section="rest", tech=t))
    # ------------------------------------------------ scene 4: the wind ensemble, 84 bpm
    L = Line(cue["flutes_start"], C.TEMPO["winds"])
    fl = [(2, 1), (3, 0.5), (4, 0.5), (0, 1, 1.5), (4, 0.5), (3, 1), (2, 1),
          (1, 0.5), (2, 0.5), (3, 1), (2, 0.5), (1, 0.5), (0, 2),
          (4, -1, 1), (0, 0.5), (1, 0.5), (2, 1.5), (3, 0.5), (2, 1), (1, 1)]
    bili = [(0, -1, 2), (4, -2, 2), (2, -1, 2), (3, -1, 2), (0, -1, 2), (4, -2, 2), (1, -1, 2), (0, -1, 2)]
    for who, dv in (("dizi_a", 0.6), ("dizi_b", 0.5), ("dizi_fold", 0.5)):
        notes, _ = melody(L, fl, who, "winds", octv=1, vel=dv)
        N += [n for n in notes if n["frame"] < cue["long_note"]]
    notes, _ = melody(L, bili, "bili", "winds", octv=0, vel=0.45)
    N += [n for n in notes if n["frame"] < cue["long_note"]]
    # the Scottish Fold's long note, then the squeak
    N.append(dict(frame=cue["long_note"], instr="dizi_fold", midi=pitch(4, 1), dur=(cue["squeak"] - cue["long_note"]) / C.FPS,
                  vel=0.6, section="winds", tech="long"))
    N.append(dict(frame=cue["squeak"], instr="dizi_fold", midi=pitch(1, 2) + 1, dur=0.35, vel=0.7, section="winds",
                  tech="squeak"))
    L = Line(cue["flutes_resume"], C.TEMPO["winds"])
    end = [(2, 0.5), (1, 0.5), (0, 1), (4, -1, 0.5), (0, 1.5)]
    for who, dv in (("dizi_a", 0.6), ("dizi_b", 0.5), ("dizi_fold", 0.5)):
        notes, _ = melody(L, end, who, "winds", octv=1, vel=dv)
        N += notes
    for i in range(0, 20, 2):
        f = Line(cue["flutes_start"], C.TEMPO["winds"]).frame(i)
        if f < cue["long_note"]:
            N.append(dict(frame=f, instr="clapper", midi=0, dur=0.2, vel=0.55, section="winds", tech=None))
    # ------------------------------------------------ scene 5: farewell coda, 72 bpm
    L = Line(cue["coda_start"], C.TEMPO["farewell"])
    coda = [(0, 1, 1), (4, 0.5), (3, 0.5), (2, 1), (1, 1), (2, 0.5), (1, 0.5), (0, 2),
            (3, 1), (2, 0.5), (1, 0.5), (0, 1), (4, -1, 1), (0, 3)]
    notes, _ = melody(L, coda, "pipa", "farewell", vel=0.5)
    N += [n for n in notes if n["frame"] < cue["coda_end"] + 30]
    notes, _ = melody(L, [(n[0], n[1], n[2]) if len(n) == 3 else (n[0], 0, n[1]) for n in coda], "dizi_a",
                      "farewell", octv=1, vel=0.32)
    N += [n for n in notes if n["frame"] < cue["coda_end"] + 30 and n["frame"] > L.frame(8)]
    # ------------------------------------------------ epilogue: guqin, the seal's bell, a last chord
    L = Line(C.SECTIONS[6]["f0"] + 20, 56)
    for b, deg, o, t in ((0, 0, -1, None), (1.5, 4, -1, None), (3, 3, -1, "slide"), (5, 2, -1, None),
                         (6, 1, -1, None), (8, 0, -1, "harmonic")):
        N.append(dict(frame=L.frame(b), instr="guqin", midi=pitch(deg, o), dur=3.5, vel=0.5, section="epilogue",
                      tech=t))
    N.append(dict(frame=cue["seal"], instr="bell", midi=pitch(0, -2), dur=8.0, vel=0.8, section="epilogue", tech=None))
    for m in (pitch(0, -1), pitch(3, -1), pitch(0), pitch(4)):
        N.append(dict(frame=cue["seal"] + 2, instr="pipa", midi=m, dur=4.0, vel=0.55, section="epilogue",
                      tech="chord"))
    for n in N:
        n["t"] = C.f2s(n["frame"])
    return sorted(N, key=lambda n: n["frame"])


NOTES = build()


def onsets(instr, f0=-1e9, f1=1e9, section=None):
    return [n for n in NOTES if n["instr"] == instr and f0 <= n["frame"] < f1 and (section is None or
                                                                                   n["section"] == section)]
