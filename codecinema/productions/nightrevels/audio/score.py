"""
score.py -- render out/notes.json into music stems for The Night Revels of Han Xizai, Cat Edition.

Every note is placed sample-accurately at t = (frame - 1) / fps (frames are fractional).  Humanisation is small and
deterministic (seeded by the note): timing jitter of a few ms, velocity +-5 %, grace ornaments shared by the flute
section.  Notes whose timing is a story beat (the sour note, the squeak, the long note, the final stroke, the bell,
chord hits) are never jittered.

Voices: pipa (+ strummed chords), jiegu + paiban (perc), three dizi + bili + a derived sheng pad (winds),
guqin (qin), bell.  A warm wooden-hall convolution reverb is fed from per-instrument sends.

    render(notes_doc, cue, n_total) -> dict(stems={name: (2,n)}, wet=(2,n), onsets=[...], stop=(t_stop, t_resume))
"""

import numpy as np

import dsp
import instruments as I
from dsp import SR, n_of, midi2hz

dsp.REVERB_PRESETS["woodhall"] = dict(rt60=1.75, length=3.4, predelay=0.017, n_er=16, er_span=0.07, er_gain=0.6,
                                      echoes=[], bands=(1.35, 1.0, 0.66, 0.36), tail_gain=1.0, build=0.025)

STEM = dict(pipa="pipa", drum="perc", clapper="perc", dizi_a="winds", dizi_b="winds", dizi_fold="winds",
            bili="winds", sheng="winds", guqin="qin", bell="bell")
PAN = dict(pipa=-0.15, drum=0.12, clapper=0.3, dizi_a=-0.4, dizi_b=-0.12, dizi_fold=0.2, bili=0.42, sheng=0.0,
           guqin=-0.06, bell=0.0)
GAIN_DB = dict(pipa=-2.5, drum=1.0, clapper=-4.5, dizi_a=-11.0, dizi_b=-12.0, dizi_fold=-11.0, bili=-9.0,
               sheng=-14.0, guqin=-3.5, bell=-4.0)
SEND = dict(pipa=0.3, drum=0.22, clapper=0.18, dizi_a=0.32, dizi_b=0.32, dizi_fold=0.32, bili=0.3, sheng=0.4,
            guqin=0.38, bell=0.3)
# per-section trims (dB): the Liuyao dance is the energetic climax, the flute ensemble sits a little back
SECTION_DB = {("dance", "pipa"): 3.0, ("dance", "drum"): 1.5, ("dance", "clapper"): 1.5, ("winds", "dizi_a"): -1.5,
              ("winds", "dizi_b"): -1.5, ("winds", "dizi_fold"): -1.5, ("winds", "bili"): -1.5,
              ("winds", "sheng"): -1.5, ("listen", "pipa"): -0.5, ("prologue", "guqin"): -4.0}
TECH_DB = {"sour": 4.0, "squeak": 9.0, "long": 2.5}   # the gags must read over the ensemble
EXACT = {"sour", "squeak", "long", "final", "chord"}
SCALE_PC = {2, 4, 6, 9, 11}                       # D gong: D E F# A B


def _t(frame, fps):
    return (float(frame) - 1.0) / fps


def _scale_above(m):
    k = int(m) + 1
    while k % 12 not in SCALE_PC:
        k += 1
    return k


def _grace_for(note):
    """flute ornaments are decided per musical event (frame), so the whole section plays the same one"""
    if note["tech"] or note["dur"] < 0.5:
        return None
    rr = dsp.rng("grace", round(float(note["frame"]), 2))
    u = rr.uniform()
    if u < 0.3:
        return [((_scale_above(note["midi"]) - note["midi"]) * 100.0, 0.045)]           # da yin (upper tap)
    if u < 0.42:
        up = (_scale_above(note["midi"]) - note["midi"]) * 100.0
        return [(0.0, 0.05), (up, 0.035)]                                              # die yin (tap after onset)
    return None


def _render_note(nt, idx, fps):
    """-> (clip mono/stereo, onset seconds, instr key)"""
    ins, tech = nt["instr"], nt["tech"]
    vel = float(nt["vel"])
    dur = float(nt["dur"])
    r = dsp.rng("note", ins, round(float(nt["frame"]), 3), nt["midi"], idx)
    t = _t(nt["frame"], fps)
    if tech not in EXACT and ins != "bell":
        sd = 0.002 if ins in ("drum", "clapper") else 0.003
        t += float(np.clip(r.normal(0.0, sd), -2.5 * sd, 2.5 * sd))
        vel *= float(np.exp(r.normal(0.0, 0.05)))
    f = float(midi2hz(nt["midi"]))
    if ins == "pipa":
        grace = None
        if tech in (None, "pluck") and dur >= 0.5 and r.uniform() < 0.2:
            grace = (-100.0 * r.choice([1, 2]), 0.07)                                   # tui: push up into the note
        y = I.pipa(f, dur, vel, r, tech=tech, grace=grace)
    elif ins == "drum":
        y = I.jiegu(vel, r, stroke=tech or "center", head=idx % 2)
    elif ins == "clapper":
        y = I.paiban(vel, r)
    elif ins.startswith("dizi"):
        y = I.dizi(f, dur, vel, r, tech=tech, grace=_grace_for(nt),
                   membrane={"dizi_a": 1.0, "dizi_b": 0.8, "dizi_fold": 1.1}[ins])
    elif ins == "bili":
        y = I.bili(f, dur, vel, r)
    elif ins == "guqin":
        y = I.guqin(f, dur, vel, r, tech=tech)
    elif ins == "bell":
        y = I.bell(f, dur, vel, r)
    else:
        return None
    return y, t


def render(doc, cue, n_total):
    fps = float(doc.get("fps", 24))
    notes = doc["notes"]
    stems = {}
    sends = np.zeros((2, n_total))
    onsets = []

    def add(ins, clip, t, extra_send=0.0, section=None, tech=None):
        g = dsp.db2lin(GAIN_DB[ins] + SECTION_DB.get((section, ins), 0.0) + TECH_DB.get(tech, 0.0))
        st = dsp.pan_mono(clip, PAN[ins]) if clip.ndim == 1 else dsp.pan_stereo(clip, PAN[ins])
        st = st * g
        key = STEM[ins]
        if key not in stems:
            stems[key] = np.zeros((2, n_total))
        s = int(round(t * SR))
        dsp.place(stems[key], st, s)
        dsp.place(sends, st, s, SEND[ins] + extra_send)

    # ---------------------------------------------------------------- chords -> strums
    chords = {}
    for i, nt in enumerate(notes):
        if nt["instr"] == "pipa" and nt["tech"] == "chord":
            chords.setdefault(round(float(nt["frame"]), 3), []).append(nt)
    for fr, grp in sorted(chords.items()):
        vel = max(float(g["vel"]) for g in grp)
        dur = max(float(g["dur"]) for g in grp)
        spread = 0.011 if vel >= 0.7 else 0.035
        y = I.pipa_strum(midi2hz(np.array([g["midi"] for g in grp])), dur, vel, dsp.rng("strum", fr),
                         spread=spread)
        t = _t(fr, fps)
        add("pipa", y, t, extra_send=0.15, section=grp[0].get("section"))
        onsets.append(dict(instr="pipa", tech="chord", t=t))

    # ---------------------------------------------------------------- single notes
    drum_i = 0
    for i, nt in enumerate(notes):
        if nt["instr"] == "pipa" and nt["tech"] == "chord":
            continue
        idx = drum_i if nt["instr"] == "drum" else i
        if nt["instr"] == "drum":
            drum_i += 1
        res = _render_note(nt, idx, fps)
        if res is None:
            print(f"score: unknown instrument {nt['instr']!r} -- skipped")
            continue
        y, t = res
        add(nt["instr"], y, t, extra_send=0.25 if nt["tech"] == "final" else 0.0, section=nt.get("section"),
            tech=nt["tech"])
        onsets.append(dict(instr=nt["instr"], tech=nt["tech"], t=_t(nt["frame"], fps)))

    # ---------------------------------------------------------------- sheng pad under the bili bass (winds)
    lim = _t(cue.get("long_note", 1e9), fps) + 0.08
    for nt in notes:
        if nt["instr"] != "bili":
            continue
        m = int(nt["midi"]) + 12
        top = m + 7 if (m + 7) % 12 in SCALE_PC else m + 5
        t = _t(nt["frame"], fps)
        dur = float(nt["dur"]) + 0.15
        if t < lim < t + dur:
            dur = max(0.3, lim - t)
        y = I.sheng(midi2hz(np.array([m, top])), dur, 0.3, dsp.rng("sheng", round(t, 3)), attack=0.3, release=0.45)
        add("sheng", y, t, section=nt.get("section"))

    # ---------------------------------------------------------------- the dead stop before the pounce
    t_stop = _t(cue.get("music_stop", 1e9), fps)
    later = [o["t"] for o in onsets if o["t"] > t_stop + 0.01]
    t_resume = min(later) - 0.004 if later else n_total / SR
    gate = np.ones(n_total)
    a, b = n_of(t_stop), n_of(t_resume)
    if a < n_total:
        m = n_of(0.025)
        gate[a:a + m] = np.linspace(1.0, 0.0, m)
        gate[a + m:b] = 0.0
    for k in stems:
        stems[k] *= gate
    sends *= gate

    # ---------------------------------------------------------------- warm wooden hall
    wet = dsp.convolve_reverb(sends, "woodhall", seed=11)
    wet = dsp.eq_chain(wet, [("peak", 260, 1.5, 0.8), ("highshelf", 5500, -4.0, 0.7), ("hp", 60, 0.0, 0.7)])
    # the hall itself holds its breath at the stop (shorter tail than the natural decay)
    if a < n_total:
        tt = (np.arange(b - a)) / SR
        wet[:, a:b] *= np.exp(-tt / 0.35)
    wet *= 0.55
    onsets.sort(key=lambda o: o["t"])
    return dict(stems=stems, wet=wet, onsets=onsets, stop=(t_stop, t_resume))
