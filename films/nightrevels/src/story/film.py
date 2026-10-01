"""
film.py - the whole film as actors, keys, camera moves and sound events.

build() -> (stage, events). Sections read right to left along the scroll; see docs/FILM_PLAN.md for the story.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "paint"), os.path.join(os.path.dirname(HERE), "common")]
import config as C  # noqa: E402
import music  # noqa: E402
import props as P  # noqa: E402
import anim  # noqa: E402
from anim import Actor, Camera, Events, Track  # noqa: E402
import cat as _cat  # noqa: E402
anim.DEFAULTS.update(_cat.POSE0)
from body import GROUND, HEAD_AT  # noqa: E402
from cast import make_cast  # noqa: E402
from ink import Xf  # noqa: E402
from stage import EN_SERIF, Stage, seal_image, text_image  # noqa: E402

SS = C.SS
CUE = C.CUE
FL = C.FLOOR


# ------------------------------------------------------------------------------------------------ helpers
def head_pos(a, f):
    ch = a.char
    face = a.at(f).get("facing", ch.facing)
    s = ch.scale
    d = 1 if face < 0 else -1
    return a.value("x", f) + HEAD_AT[0] * s * d, a.value("y", f) + (-GROUND[ch.posture] + HEAD_AT[1]) * s


def look_at(a, f0, f1, target, step=3, gain=1.0, turn=True):
    """Key look / look_y / head_rot so actor `a` follows target(f) -> (x, y) between f0 and f1."""
    for f in range(int(f0), int(f1) + 1, step):
        tx, ty = target(f)
        hx, hy = head_pos(a, f)
        face = a.at(f).get("facing", a.char.facing)
        dxl = (tx - hx) * (1 if face < 0 else -1)          # + = behind the cat (to its right)
        look = max(-1.0, min(1.0, -dxl / 260.0 * gain))
        a.key("look", f, look, "lin")
        a.key("look_y", f, max(-1.0, min(1.0, (ty - hy) / 260.0)), "lin")
        if turn:
            rot = max(-18.0, min(18.0, math.degrees(math.atan2(ty - hy, abs(tx - hx) + 60)) * 0.5))
            a.key("head_rot", f, -rot if dxl < 0 else rot * 0.4, "lin")


def meow(ev, a, f, dur=12, size=0.8, kind="meow"):
    a.key("mouth", f - 3, 0.0).key("mouth", f + 2, size, "out").key("mouth", f + dur, size * 0.6)
    a.key("mouth", f + dur + 5, 0.0)
    ev.emit(f, kind, who=a.name, x=a.value("x", f), size=size, dur=dur / C.FPS)


def happy(a, f0, f1, ramp=4):
    a.track("happy").hold(f0, f1, 1.0, "inout", ramp)


def blink_hold(a, f0, f1, v=1.0, ramp=4):
    a.track("blink").hold(f0, f1, v, "inout", ramp)
    a.track("blink_lock").hold(f0 - ramp, f1 + ramp, 1.0, "step", 0)


def prop(name, draw, x, y, z=0.0, **base):
    a = Actor(name, None, x, y, z, idle=False, **base)
    a.draw_fn = draw
    return a


def static(name, fn, x, y, z=0.0, scale=SS, **kw):
    def draw(c, a, f):
        with Xf(c, a.value("x", f), a.value("y", f), a.value("rot", f), scale):
            fn(c, **kw)
    return prop(name, draw, x, y, z)


def walk(a, f0, f1, x0, x1):
    a.key("x", f0, x0, "lin").key("x", f1, x1, "lin")
    a.track("walk").key(f0 - 4, 0.0).key(f0, 1.0).key(f1, 1.0).key(f1 + 5, 0.0)


# ------------------------------------------------------------------------------------------------ build
def build():
    CH = make_cast()
    A, T = [], []
    ev = Events()
    cam = Camera(12900, 500, C.Z_SCROLL)
    t_of = lambda f: f / C.FPS                                          # noqa: E731

    # ============================================================================ prologue
    slip = text_image("韩熙载夜宴图", 70, True)
    T.append(dict(image=slip, x=13420, y=150, scale=1.0, alpha=Track(1.0)))
    T.append(dict(image=seal_image("猫", 64), x=13420, y=150 + slip.height() + 20, scale=1.0, alpha=Track(1.0)))
    cap = text_image("南唐·韩府·夜", 58, True, color=(40, 30, 26))
    T.append(dict(image=cap, x=12760, y=190, scale=1.0,
                  alpha=Track(0.0).key(CUE["caption"], 0.0).key(CUE["caption"] + 30, 0.9)))
    cam.key(70, x=12900).key(CUE["caption"] + 10, x=12760).key(CUE["kitten_enter"] + 20, x=12700)
    cam.key(CUE["kitten_hide"] + 10, x=12420).key(264, x=12150)

    kitten = Actor("kitten", CH["kitten"], 13000, FL - 10, 5, facing=-1)
    kitten.key("visible", 0, 0.0, "step").key("visible", CUE["kitten_enter"] - 2, 1.0, "step")
    walk(kitten, CUE["kitten_enter"], CUE["kitten_hide"], 12980, 12300)
    kitten.key("tail_off", CUE["kitten_enter"], 0.0)
    kitten.base.update(paw_l=(10, -40), paw_r=(0, -30), tail_amp=0.6)
    kitten.key("look", CUE["kitten_enter"] + 20, 0.6).key("look", CUE["kitten_enter"] + 40, -0.6)
    kitten.key("look", CUE["kitten_enter"] + 60, 0.4).key("look", CUE["kitten_hide"] - 10, -0.8)
    kitten.key("x", 1500, 12300, "step")
    A.append(kitten)
    ev.emit(CUE["kitten_enter"] + 10, "tiptoe", x=12900, n=10, dur=(CUE["kitten_hide"] - CUE["kitten_enter"]) / C.FPS)

    def kitten_hold(c, f, p):              # sketchbook + brush
        with Xf(c, -46, 70, -8):
            P.shape(c, P._rect(-26, -36, 26, 30), (0.93, 0.9, 0.82), w=1.1)
            P.stroke_line(c, [(-14, -10), (0, -20), (12, -6)], 1.2, P.INK, 0.6)
        P.tapered(c, [(-10, 70), (-24, 40)], 3.5, 2.0, (0.45, 0.3, 0.18))
    kitten.hold = kitten_hold

    A.append(static("screen0", P.screen, 12150, FL, 20, w=360, h=560, seed=3))

    # the moth (one actor for the whole film, keyed path + flutter)
    moth = prop("moth", lambda c, a, f: P.moth(c, a.value("x", f) + 14 * math.sin(f * 0.23),
                                               a.value("y", f) + 10 * math.sin(f * 0.31 + 1), t_of(f), 1.8,
                                               a.value("rot", f)), 13200, 380, 60)
    moth.keys("x", [(170, 12900), (250, 12050), (262, 11900)], "lin").keys("y", [(170, 420), (250, 300)], "lin")
    moth.key("visible", 168, 0.0, "step").key("visible", 170, 1.0, "step").key("visible", 262, 0.0, "step")
    A.append(moth)

    # ============================================================================ scene 1: listening
    x_couch, x_han, x_lang = 11480, 11390, 11640
    y_seat = FL - 110 * SS
    A.append(static("couch1", P.couch, x_couch, FL, 1, w=460, canopy=True, seed=5))
    han1 = Actor("han1", CH["han"], x_han, y_seat, 10, facing=-1)
    han1.base.update(blink=0.0, paw_l=(0, 0), paw_r=(0, 0))
    A.append(han1)
    A.append(static("quilt1", P.quilt, x_lang - 40, y_seat + 2, 11, w=220))
    lang1 = Actor("lang1", CH["lang"], x_lang, y_seat, 12, facing=-1)
    A.append(lang1)
    x_tab = 11700
    A.append(static("table1", P.table, x_tab, FL + 30, 30, w=170, h=100, items=[("fruit", 10), ("ewer", 52)]))
    cup_y = FL + 30 - 100 * SS
    cup = prop("cup", lambda c, a, f: _draw_cup(c, a, f), x_tab - 40 * SS, cup_y, 31)
    A.append(cup)
    A.append(static("table1b", P.table, 10980, FL + 10, 25, w=240, h=100,
                    items=[("cakes", -70), ("ewer", 0), ("cup", 60), ("cup", 90)]))
    guest_g = Actor("guest_g", CH["guest_green"], 10760, FL + 5, 26, facing=-1)
    guest_b = Actor("guest_b", CH["guest_blue"], 10560, FL - 40, 15, facing=-1)
    A += [static("stool_g", P.stool, 10760, FL + 5, 25.5), static("stool_b", P.stool, 10560, FL - 40, 14.5),
          guest_g, guest_b]
    li1 = Actor("li1", CH["li"], 10060, FL + 10, 26, facing=1)
    jia1 = Actor("jia1", CH["jiaming"], 10330, FL + 20, 27, facing=-1)
    A += [static("stool_li", P.stool, 10060, FL + 10, 25.8), static("stool_jia", P.stool, 10330, FL + 20, 26.5),
          li1, jia1]
    att1 = Actor("att1", CH["attendant"], 10230, FL - 90, 8, facing=-1)
    att1.base.update(paw_l=(10, -10), paw_r=(0, -8))
    A.append(att1)
    A.append(prop("candle1", lambda c, a, f: _candle(c, a, f), 9905, FL - 20, 6))
    A.append(static("screen1", P.screen, 9700, FL, 40, w=360, h=560, seed=11))

    # pipa playing, synced to the notes
    pipa_notes = [n for n in music.NOTES if n["instr"] == "pipa" and n["section"] in ("listen",)]

    def pluck_at(f, notes):
        amt, last = 0.0, None
        for n in notes:
            d = f - n["frame"]
            if d < -1:
                break
            if n.get("tech") == "tremolo" and 0 <= d <= n["dur"] * C.FPS:
                amt = max(amt, 0.6 + 0.4 * abs(math.sin(d * 2.1)))
                last = n
            elif 0 <= d < 8:
                amt = max(amt, 1.0 - d / 8)
                last = n
        return amt, last

    def li_hold(c, f, p):
        amt, last = pluck_at(f, pipa_notes)
        P.pipa(c, -20, 118, ang=48, scale=1.0, pluck=amt)
    li1.hold = li_hold
    li1.base.update(paw_l=(-40, -50), paw_r=(40, 10), blink=0.0)
    for n in pipa_notes:            # near paw flicks on every pluck; far paw slides with pitch
        f = n["frame"]
        li1.key("paw_r", f - 2, (40, 10)).key("paw_r", f + 1, (48, 22), "out").key("paw_r", f + 6, (40, 10))
        slide = (n["midi"] - 62) * 1.6
        li1.key("paw_l", f, (-40 + slide, -50 + slide * 0.6), "inout")
        if n.get("tech") == "sour":
            li1.key("pupil", f, 1.0, "snap").key("pupil", f + 40, 0.35)
    blink_hold(li1, CUE["pipa_start"] + 10, CUE["cup_fall"] - 2, 0.75)
    blink_hold(li1, CUE["pipa_resume"] + 6, CUE["pipa_end"], 0.75)
    li1.key("head_rot", CUE["pipa_start"], -6).key("head_rot", CUE["pipa_end"], -6)

    # ears of every listener turn to the music; Han half-closes his eyes
    for a in (han1, lang1, guest_g, guest_b, jia1, att1):
        for n in pipa_notes[::3]:
            a.key("ear_l", n["frame"], -8.0).key("ear_l", n["frame"] + 8, 4.0)
    blink_hold(han1, CUE["pipa_start"] + 30, CUE["cup_fall"] - 4, 0.55)
    han1.key("look", 300, -0.9)
    jia1.key("look", 300, -0.7).key("tail_speed", 300, 2.0)
    guest_g.key("look", 300, -0.9)
    guest_b.key("look", 300, -1.0).key("head_rot", 300, 4)

    # the cup gag
    f_push, f_fall = CUE["cup_push"], CUE["cup_fall"]
    lang1.key("look", f_push - 30, 0.0).key("look", f_push - 10, -0.1)
    lang1.key("look_y", f_push - 10, 0.5)
    # he stares at the camera (look ~ 0, head toward viewer) while the paw pushes the cup
    lang1.key("look", f_push, 0.05).key("look_y", f_push, 0.1).key("head_rot", f_push, 6)
    blink_hold(lang1, f_push + 6, f_fall - 4, 0.35)
    # the paw rests on the cup, then nudges it (in little stops) to the table edge while he stares at us
    cx0, cx1 = x_tab - 40 * SS, x_tab - 92 * SS
    lang1.key("paw_r", f_push - 10, (0, 0)).key("paw_r", f_push, (26, 52), "inout")
    lang1.key("reach_r", f_push - 12, 1.0).key("reach_r", f_push - 2, 1.45).key("reach_r", f_fall + 18, 1.45)
    lang1.key("reach_r", f_fall + 26, 1.0)
    for i in range(4):
        fr = f_push + 12 + i * 14
        k = (i + 1) / 4.0
        cxk = cx0 + (cx1 - cx0) * k
        lang1.key("paw_r", fr, (26 - 40 * k, 52), "inout").key("paw_r", fr + 7, (26 - 40 * k + 3, 50), "inout")
        cup.key("x", fr, cxk, "inout").key("x", fr + 7, cxk, "lin")
        ev.emit(fr - 4, "cup_nudge", x=cxk)
    lang1.key("paw_r", f_fall - 6, (-20, 50), "inout").key("paw_r", f_fall + 20, (0, 0), "inout")
    cup.key("x", f_fall - 2, cx1 - 14, "in").key("x", f_fall + 8, cx1 - 34, "lin")
    cup.key("y", f_fall - 2, cup_y, "lin").key("y", f_fall + 8, FL + 30, "in")
    cup.key("rot", f_fall - 2, 0.0).key("rot", f_fall + 8, -110.0, "in")
    ev.emit(f_fall + 8, "cup_clink", x=x_tab)
    # everyone turns to Lang; he licks his paw
    for a, dl in ((han1, 0.6), (li1, 0.8), (jia1, 1.0), (guest_g, 1.0), (guest_b, 1.0), (att1, 1.0)):
        face = a.base.get("facing", -1)
        a.key("look", f_fall + 6, 0.0).key("look", f_fall + 12, -face * dl, "snap")
        a.key("pupil", f_fall + 8, 0.9, "snap").key("pupil", f_fall + 60, 0.35)
        a.key("look", CUE["pipa_resume"] - 8, a.value("look", f_fall - 20)).key("look", CUE["pipa_resume"],
                                                                                 a.value("look", f_fall - 20))
    blink_hold(han1, f_fall + 30, CUE["pipa_resume"] - 4, 1.0)
    ev.emit(f_fall + 36, "sigh", who="han", x=x_han)
    lang1.key("look", CUE["lick"] - 6, 0.6).key("head_rot", CUE["lick"], 16)
    lang1.key("paw_r", CUE["lick"], (-30, -80), "inout").key("paw_r", CUE["lick"] + 36, (-30, -80))
    for i in range(3):
        lang1.key("mouth", CUE["lick"] + 4 + i * 10, 0.35).key("mouth", CUE["lick"] + 9 + i * 10, 0.0)
        ev.emit(CUE["lick"] + 4 + i * 10, "lick", x=x_lang)
    blink_hold(lang1, CUE["lick"], CUE["lick"] + 34, 1.0)
    lang1.key("paw_r", CUE["lick"] + 46, (0, 0)).key("head_rot", CUE["lick"] + 46, 0)

    # camera, scene 1
    cam.key(300, x=11420, z=C.Z_SCROLL)
    cam.key(372, x=11300).key(460, x=10560).key(520, x=10620)
    cam.key(548, x=11560, y=700, z=2.0).key(646, x=11560, y=710, z=2.05)
    cam.key(664, x=10820, y=500, z=C.Z_SCROLL, ease="out").key(700, x=10760)
    cam.key(790, x=10200).key(840, x=9820)

    # kitten peeks from screen1 at the end of the scene
    kit1 = Actor("kit1", CH["kitten"], 9985, FL - 10, 35, facing=-1)
    kit1.key("visible", 0, 0.0, "step").key("visible", 700, 1.0, "step").key("visible", 1000, 0.0, "step")
    kit1.base.update(paw_l=(10, -40), paw_r=(0, -30))
    kit1.key("look", 700, 0.8)
    kit1.hold = kitten_hold
    kit1.keys("paw_r", [(720 + i * 8, (0, -30) if i % 2 else (-8, -24)) for i in range(18)])
    A.append(kit1)

    # ============================================================================ scene 2: the dance
    x_drum, x_han2, x_monk = 9010, 9170, 9430
    han2 = Actor("han2", CH["han_stand"], x_han2, FL, 20, facing=-1)
    A.append(han2)
    drum_hits = [n for n in music.NOTES if n["instr"] == "drum"]
    drum_act = prop("drum2", lambda c, a, f: _drum(c, a, f, drum_hits), x_drum, FL + 10, 21)
    A.append(drum_act)

    def han_sticks(c, f, p):
        for key, off in (("paw_l", (-44, 96)), ("paw_r", (-10, 104))):
            px, py = p.get(key, (0, 0))
            P.drumstick(c, off[0] + px + 6, off[1] + py, -35 if key == "paw_l" else -20)
    han2.hold = han_sticks
    han2.base.update(paw_l=(-40, -20), paw_r=(-60, -26))
    # strike: paws move to the drum head (local ~(-110, 130)) on each hit, alternating
    for i, n in enumerate(drum_hits):
        f = n["frame"]
        k = "paw_l" if i % 2 == 0 else "paw_r"
        up = (-40, -20) if k == "paw_l" else (-60, -26)
        hit = (-70, 36) if k == "paw_l" else (-86, 30)
        if n.get("tech") == "final":
            up = (-30, -110)
        han2.key(k, f - 5, up).key(k, f, hit, "in").key(k, f + 5, up, "out")
    han2.key("look", 880, -0.7).key("look_y", 880, 0.3)
    # the stick frozen mid-air when the music stops
    han2.key("paw_l", CUE["music_stop"], (-40, -60)).key("paw_l", CUE["land"] - 6, (-30, -110))

    monk = Actor("monk", CH["monk"], x_monk, FL - 30, 15, facing=-1)
    monk.base.update(paw_l=(20, -30), paw_r=(-10, -36), ear_l=26, ear_r=26)
    monk.key("look", 880, 0.9).key("look_y", 880, 0.8).key("head_rot", 880, 10)
    A.append(monk)

    x_wang = 8250
    wang = Actor("wang", CH["wang"], x_wang, FL - 10, 30, facing=1)
    A.append(wang)
    x_jia2 = 8700
    jia2 = Actor("jia2", CH["jiaming_stand"], x_jia2, FL - 50, 18, facing=-1)
    claps = [n for n in music.NOTES if n["instr"] == "clapper" and n["section"] == "dance"]

    def jia_clap(c, f, p):
        o = 0.0
        for n in claps:
            d = f - n["frame"]
            if -4 <= d < 0:
                o = max(o, 1 + d / 4)
            elif 0 <= d < 6:
                o = max(o, 0.0)
        P.clappers(c, -40, 60, -10, o)
    jia2.hold = jia_clap
    jia2.base.update(paw_l=(0, -40), paw_r=(-10, -44))
    A.append(jia2)
    lang2 = Actor("lang2", CH["lang_stand"], 7760, FL - 20, 17, facing=1)
    att2 = Actor("att2", CH["attendant2"], 7560, FL + 10, 22, facing=1)
    gst2 = Actor("gst2", CH["guest_green_stand"], 7960, FL - 70, 12, facing=1)
    A += [lang2, att2, gst2]
    A.append(prop("candle2", lambda c, a, f: _candle(c, a, f), 7400, FL - 30, 6))
    A.append(static("screen2", P.screen, 7200, FL, 40, w=360, h=560, seed=21))

    # dance: turns, sleeve arcs on the beat (the Liuyao), speeding up with the music
    beat_frames = [n["frame"] for n in drum_hits if n["section"] == "dance" and n.get("tech") != "final"]
    for i, f in enumerate(beat_frames):
        side = 1 if (i // 2) % 2 == 0 else -1
        wang.key("paw_l", f, (-70 * side, -90 + 30 * (i % 2)), "inout")
        wang.key("paw_r", f, (60 * side, -70 - 30 * (i % 2)), "inout")
        wang.key("head_rot", f, 8 * side, "inout")
        wang.key("water_l", f, (200 + 40 * side, i * 0.37), "inout")
        wang.key("water_r", f, (-20 - 40 * side, i * 0.41 + 0.3), "inout")
        wang.key("body_y", f, -6 if i % 2 else 0, "inout")
        if i % 8 == 4:
            wang.key("facing", f, -1, "step").key("facing", f + 12, 1, "step")
    happy(wang, CUE["drum_start"] + 20, CUE["moth_enter"] + 10)
    wang.key("cloth", 0, 0.0).key("cloth", CUE["land"] + 200, 18.0, "lin")

    # the moth arrives: every head snaps to it
    mf0, mf1 = CUE["moth_enter"], CUE["land"] + 20
    moth.key("visible", mf0 - 1, 0.0, "step").key("visible", mf0, 1.0, "step")
    moth.keys("x", [(mf0, 7650), (CUE["heads_snap"], 7980), (CUE["music_stop"], 8150), (CUE["pounce"], 8210),
                    (CUE["pounce"] + 14, 8300), (CUE["land"], 8520), (mf1, 8900)], "inout")
    moth.keys("y", [(mf0, 250), (CUE["heads_snap"], 330), (CUE["music_stop"], 300), (CUE["pounce"], 320),
                    (CUE["pounce"] + 14, 220), (CUE["land"], 160), (mf1, 120)], "inout")
    moth.key("visible", mf1 + 1, 0.0, "step")
    moth_pos = lambda f: (moth.value("x", f), moth.value("y", f))     # noqa: E731
    ev.emit(mf0, "moth_flutter", x=7650, dur=(mf1 - mf0) / C.FPS)
    for a in (han2, monk, jia2, lang2, att2, gst2):
        look_at(a, CUE["heads_snap"], CUE["land"] - 2, moth_pos, step=3)
        a.key("pupil", CUE["heads_snap"], 1.0, "snap").key("pupil", CUE["land"] + 20, 0.35)
        a.key("look", CUE["land"] + 12, 0.0)
    wang.key("happy", CUE["heads_snap"], 0.0, "step")
    look_at(wang, CUE["heads_snap"], CUE["land"] - 4, moth_pos, step=3)
    wang.key("pupil", CUE["heads_snap"], 1.0, "snap")
    # freeze, wiggle, pounce
    wang.key("paw_l", CUE["music_stop"], (-30, -20)).key("paw_r", CUE["music_stop"], (20, -10))
    for i in range(6):
        fr = CUE["wiggle"] + i * 4
        wang.key("body_x", fr, 6 if i % 2 else -6, "inout")
    wang.key("body_x", CUE["pounce"] - 2, 0.0)
    wang.key("y", CUE["pounce"] - 4, FL - 10).key("y", CUE["pounce"] + 12, FL - 240, "out")
    wang.key("y", CUE["land"] - 10, FL - 200, "inout").key("y", CUE["land"], FL - 10, "in")
    wang.key("x", CUE["pounce"], x_wang).key("x", CUE["pounce"] + 14, x_wang + 60).key("x", CUE["land"], x_wang + 40)
    wang.key("paw_l", CUE["pounce"] + 6, (-20, -170), "out").key("paw_r", CUE["pounce"] + 6, (-40, -160), "out")
    wang.key("water_l", CUE["pounce"] + 6, (260, 3.0)).key("water_r", CUE["pounce"] + 6, (250, 3.4))
    wang.key("ear_l", CUE["pounce"], -10).key("mouth", CUE["pounce"] + 4, 0.5).key("mouth", CUE["pounce"] + 14, 0.0)
    ev.emit(CUE["pounce"], "pounce", x=x_wang)
    ev.emit(CUE["pounce"] + 4, "sleeve_whoosh", x=x_wang)
    ev.emit(CUE["wiggle"], "chirp", who="wang", x=x_wang)
    # landing in a perfect pose, on the final drum stroke
    wang.key("paw_l", CUE["land"], (-80, -130), "back").key("paw_r", CUE["land"], (70, -60), "back")
    wang.key("water_l", CUE["land"], (150, 5.0)).key("water_r", CUE["land"], (30, 5.4))
    wang.key("head_rot", CUE["land"], -10, "back")
    happy(wang, CUE["land"] + 4, CUE["land"] + 110)
    ev.emit(CUE["land"], "land_soft", x=x_wang)
    # applause, the monk's relief
    for a in (lang2, att2, gst2, jia2):
        happy(a, CUE["applause"] + 4, CUE["applause"] + 60)
        for i in range(7):
            fr = CUE["applause"] + i * 7
            a.key("paw_l", fr, (-10, -60)).key("paw_r", fr, (-30, -64))
            a.key("paw_l", fr + 3, (-24, -60)).key("paw_r", fr + 3, (-18, -62))
    ev.emit(CUE["applause"], "applause", x=7900, dur=2.2)
    blink_hold(monk, CUE["monk_sigh"], CUE["monk_sigh"] + 30, 1.0)
    monk.key("ear_l", CUE["monk_sigh"], 0).key("ear_r", CUE["monk_sigh"], 0)
    ev.emit(CUE["monk_sigh"], "sigh", who="monk", x=x_monk)

    cam.key(880, x=9150, z=C.Z_SCROLL).key(960, x=9000, z=1.2, y=520)
    cam.key(1030, x=8560, z=C.Z_SCROLL, y=500).key(1160, x=8420)
    cam.key(CUE["heads_snap"], x=8300, y=520, z=1.25).key(CUE["music_stop"], x=8240, y=560, z=1.6)
    cam.key(CUE["pounce"] + 12, x=8300, y=430, z=1.5).key(CUE["land"], x=8560, y=500, z=C.Z_SCROLL, ease="out")
    cam.key(1400, x=8420).key(1464, x=7300)

    # ============================================================================ scene 3: intermission
    x_bed3, x_han3 = 6560, 6470
    A.append(static("couch3", P.couch, x_bed3, FL, 1, w=460, canopy=True, seed=31, panels=True))
    han3 = Actor("han3", CH["han"], x_han3, y_seat, 10, facing=-1)
    A.append(han3)
    lady3 = Actor("lady3", CH["lady_cross"], x_bed3 + 150, y_seat, 11, facing=-1)
    A.append(static("quilt3", P.quilt, x_bed3 + 120, y_seat + 2, 10.5, w=240, color=(0.3, 0.42, 0.5)))
    A.append(lady3)
    basin3 = prop("basin3", lambda c, a, f: _basin(c, a, f), 6200, FL + 20, 30)
    A.append(basin3)
    att3 = Actor("att3", CH["attendant"], 6060, FL + 20, 31, facing=1)
    att3.base.update(paw_l=(-20, -20), paw_r=(-30, -10))
    A.append(att3)
    yawn3 = Actor("yawn3", CH["attendant2"], 5850, FL - 60, 14, facing=-1)
    A.append(yawn3)
    A.append(prop("candle3", lambda c, a, f: _candle(c, a, f), 5620, FL - 20, 6))
    A.append(static("screen3", P.screen, 5100, FL, 40, w=360, h=560, seed=41))
    kit3 = Actor("kit3", CH["kitten"], 5410, FL - 10, 41, facing=-1)
    kit3.key("visible", 0, 0.0, "step").key("visible", 1600, 1.0, "step").key("visible", 1900, 0.0, "step")
    kit3.base.update(paw_l=(10, -40), paw_r=(0, -30))
    kit3.hold = kitten_hold
    kit3.key("look", 1600, 0.8)
    for i in range(16):
        kit3.key("paw_r", 1690 + i * 3, (0, -30) if i % 2 else (-10, -22), "lin")
    A.append(kit3)

    # the basin: a toe dip, recoil, shake, then a lick bath instead
    han3.key("look", 1490, -0.6).key("look_y", 1490, 0.5)
    han3.key("paw_r", CUE["basin_offer"], (0, 0)).key("paw_r", CUE["toe_dip"] - 6, (-110, 70), "inout")
    han3.key("reach_r", CUE["basin_offer"], 1.0).key("reach_r", CUE["toe_dip"] - 8, 1.7).key("reach_r", CUE["recoil"] + 6, 1.0)
    han3.key("paw_r", CUE["toe_dip"], (-120, 96), "in")
    han3.key("paw_r", CUE["recoil"], (-40, -20), "snap")
    han3.key("pupil", CUE["toe_dip"], 1.0, "snap").key("ear_l", CUE["toe_dip"] + 2, 40, "snap")
    han3.key("ear_r", CUE["toe_dip"] + 2, 40, "snap").key("ear_l", CUE["lick_face"] + 30, 0).key("ear_r", CUE["lick_face"] + 30, 0)
    for i in range(8):
        fr = CUE["shake"] + i * 3
        han3.key("paw_r", fr, (-40 + (10 if i % 2 else -10), -20 + (6 if i % 2 else -6)), "lin")
    ev.emit(CUE["toe_dip"], "water_dip", x=6200)
    ev.emit(CUE["recoil"], "meow_offended", who="han", x=x_han3)
    han3.key("mouth", CUE["recoil"], 0.5, "snap").key("mouth", CUE["recoil"] + 10, 0.0)
    ev.emit(CUE["shake"], "paw_shake", x=x_han3)
    basin3.key("splash", CUE["toe_dip"] - 1, 0.0).key("splash", CUE["toe_dip"] + 2, 1.0).key("splash", CUE["toe_dip"] + 20, 0.0)
    han3.key("paw_r", CUE["lick_face"], (-40, -90), "inout")
    for i in range(5):
        fr = CUE["lick_face"] + 6 + i * 9
        han3.key("paw_r", fr, (-44, -110), "inout").key("paw_r", fr + 4, (-40, -84), "inout")
        han3.key("mouth", fr, 0.3).key("mouth", fr + 4, 0.0)
        ev.emit(fr, "lick", x=x_han3)
    blink_hold(han3, CUE["lick_face"], CUE["lick_face"] + 50, 1.0)
    han3.key("paw_r", CUE["lick_face"] + 60, (0, 0)).key("pupil", CUE["lick_face"] + 60, 0.35)
    att3.key("look", CUE["toe_dip"], -0.8).key("blush", CUE["recoil"], 0.8).key("blush", CUE["recoil"] + 40, 0.0)
    # kneading and purring
    for i in range(22):
        fr = CUE["knead"] + i * 8
        side = i % 2
        lady3.key("paw_l", fr, (-10, 20 if side else 30), "inout").key("paw_r", fr, (0, 30 if side else 20), "inout")
    happy(lady3, CUE["knead"], CUE["knead"] + 190)
    ev.emit(CUE["knead"], "purr", who="lady", x=x_bed3 + 150, dur=8.0)
    # the yawn
    yawn3.key("mouth", CUE["yawn"], 0.0).key("mouth", CUE["yawn"] + 10, 1.0, "out").key("mouth", CUE["yawn"] + 34, 1.0)
    yawn3.key("mouth", CUE["yawn"] + 44, 0.0)
    blink_hold(yawn3, CUE["yawn"] + 4, CUE["yawn"] + 40, 1.0)
    yawn3.key("ear_l", CUE["yawn"] + 6, 24).key("ear_r", CUE["yawn"] + 6, 24).key("ear_l", CUE["yawn"] + 44, 0)
    yawn3.key("ear_r", CUE["yawn"] + 44, 0)
    ev.emit(CUE["yawn"] + 8, "yawn", who="yawn3", x=5850)
    # Han notices the kitten ... and lets him be
    han3.key("ear_l", CUE["ear_turn"], -6).key("ear_r", CUE["ear_turn"], 34, "snap")
    han3.key("look", CUE["ear_turn"] + 4, 0.9, "inout")
    kit3.key("pupil", CUE["kitten_freeze"], 1.0, "snap").key("idle", CUE["kitten_freeze"], 0.0, "step")
    kit3.key("ear_l", CUE["kitten_freeze"], 30, "snap").key("ear_r", CUE["kitten_freeze"], 30, "snap")
    kit3.key("idle", CUE["han_away"] + 6, 1.0, "step").key("pupil", CUE["han_away"] + 10, 0.35)
    kit3.key("ear_l", CUE["han_away"] + 8, 0).key("ear_r", CUE["han_away"] + 8, 0)
    han3.key("blink", CUE["kitten_freeze"] + 10, 0.0).key("blink", CUE["kitten_freeze"] + 20, 0.45)
    happy(han3, CUE["han_smile"], CUE["han_away"])
    han3.key("look", CUE["han_away"], -0.6).key("ear_r", CUE["han_away"], 0)
    ev.emit(CUE["han_smile"], "purr", who="han", x=x_han3, dur=1.5)

    cam.key(1500, x=6380, z=C.Z_SCROLL).key(1530, x=6300, y=620, z=1.8).key(1620, x=6300, y=620, z=1.8)
    cam.key(1660, x=6150, y=500, z=C.Z_SCROLL).key(1700, x=6080)
    cam.key(1736, x=5920, z=1.1).key(1810, x=5900, z=1.1).key(1848, x=5150, z=C.Z_SCROLL)

    # ============================================================================ scene 4: the wind ensemble
    x_chair = 4700
    A.append(static("chair4", P.chair, x_chair + 20, FL, 9, facing=-1))
    han4 = Actor("han4", CH["han_open"], x_chair, FL - 124 * SS, 10, facing=-1)

    def han_fan(c, f, p):
        px, py = p.get("paw_r", (0, 0))
        P.fan(c, -10 + px + 4, 104 + py - 4, -20 + 18 * math.sin(f * 0.25))
    han4.hold = han_fan
    for fr in range(1849, 2376, 6):
        han4.key("paw_r", fr, (-20 + 16 * math.sin(fr * 0.25), -40 + 6 * math.cos(fr * 0.25)), "lin")
    blink_hold(han4, 1880, 2140, 0.6)
    ev.emit(1860, "fan", x=x_chair, dur=20.0)
    A.append(han4)
    players = []
    for k, (key, x, y) in enumerate((("flute_calico", 4150, FL - 30), ("flute_blue", 3910, FL - 10),
                                     ("flute_fold", 3670, FL - 30), ("bili", 3430, FL - 10))):
        a = Actor(key, CH[key], x, y, 20 + k * 0.1, facing=1)
        a.base.update(paw_l=(-60, -150), paw_r=(-20, -150))
        instr = {"flute_calico": "dizi_a", "flute_blue": "dizi_b", "flute_fold": "dizi_fold", "bili": "bili"}[key]
        notes = [n for n in music.NOTES if n["instr"] == instr and n["section"] in ("winds",)]

        def hold(c, f, p, instr=instr, notes=notes):
            if instr == "bili":
                P.flute(c, -34, -26, 58, kind="bili")
            else:
                P.flute(c, -120, -36, 8, 150)
        a.hold = hold
        for n in notes:
            f = n["frame"]
            a.key("paw_l", f, (-60 + (4 if n["midi"] % 2 else -4), -150), "lin")
            a.key("body_y", f, -3, "inout").key("body_y", f + 8, 0, "inout")
        blink_hold(a, 1880, CUE["long_note"], 0.5)
        players.append(a)
        A.append(a)
    fold = players[2]
    # the long note: cheeks puff, eyes widen, the squeak
    fold.key("head_rot", CUE["long_note"], -4).key("head_rot", CUE["squeak"] - 4, -14)
    fold.key("pupil", CUE["long_note"] + 30, 0.8).key("blush", CUE["long_note"], 0.0).key("blush", CUE["squeak"], 1.0)
    fold.key("ear_l", CUE["squeak"] - 20, 20).key("ear_r", CUE["squeak"] - 20, 20)
    fold.key("pupil", CUE["squeak"], 1.0, "snap").key("mouth", CUE["squeak"] + 2, 0.5, "snap").key("mouth", CUE["squeak"] + 16, 0.0)
    for a in players + []:
        a.key("look", CUE["squeak"] + 4, -0.2 if a is not fold else 0.0)
        if a is not fold:
            a.key("look", CUE["squeak"] + 6, 1.0 if a.value("x", 0) > fold.value("x", 0) else -1.0)
        happy(a, CUE["giggle"], CUE["giggle"] + 36)
    fold.key("blush", CUE["giggle"] + 50, 0.0)
    ev.emit(CUE["giggle"], "giggle", x=3800, dur=1.4)
    jia4 = Actor("jia4", CH["jiaming_stand"], 3190, FL - 20, 18, facing=1)
    claps4 = [n for n in music.NOTES if n["instr"] == "clapper" and n["section"] == "winds"]
    jia4.hold = lambda c, f, p: P.clappers(c, -40, 60, -10, max([0.0] + [1 + (f - n["frame"]) / 4 for n in claps4
                                                                         if -4 <= f - n["frame"] < 0]))
    jia4.base.update(paw_l=(0, -40), paw_r=(-10, -44))
    A.append(jia4)
    A.append(prop("candle4", lambda c, a, f: _candle(c, a, f), 4420, FL - 40, 6))
    # the nose boop at the screen
    x_sc4 = 2800
    lang4 = Actor("lang4", CH["lang_stand"], x_sc4 - 180, FL - 10, 41, facing=1)
    lady4 = Actor("lady4", CH["attendant2"], x_sc4 - 40, FL - 10, 41.5, facing=-1)
    A += [lang4, lady4, static("screen4", P.screen, x_sc4, FL, 40, w=360, h=560, seed=51)]
    lang4.key("x", CUE["boop"] - 40, x_sc4 - 180).key("x", CUE["boop"], x_sc4 - 140, "inout")
    lady4.key("x", CUE["boop"] - 40, x_sc4 - 40).key("x", CUE["boop"], x_sc4 - 78, "inout")
    for a in (lang4, lady4):
        blink_hold(a, CUE["boop"] - 6, CUE["boop"] + 30, 1.0)
        a.key("head_rot", CUE["boop"], -6)
        a.key("blush", CUE["boop"], 1.0).key("blush", CUE["boop"] + 50, 0.3)
    ev.emit(CUE["boop"], "boop", x=x_sc4 - 110)

    cam.key(1890, x=4400, z=C.Z_SCROLL).key(2010, x=3900).key(2140, x=3850)
    cam.key(2160, x=3690, y=540, z=2.0).key(CUE["squeak"] + 2, x=3690, y=540, z=2.1)
    cam.key(CUE["giggle"] + 10, x=3850, y=500, z=1.15).key(2270, x=3800)
    cam.key(2300, x=2690, y=560, z=2.1).key(2350, x=2690, y=560, z=2.1).key(2376, x=2300, y=500, z=C.Z_SCROLL)

    # ============================================================================ scene 5: farewell
    x_han5 = 2130
    han5 = Actor("han5", CH["han_yellow"], x_han5, FL, 20, facing=-1)
    han5.base.update(paw_l=(-20, -150), paw_r=(0, 0))
    han5.hold = lambda c, f, p: P.drumstick(c, -44 + p.get("paw_l", (0, 0))[0] + 6, 96 + p.get("paw_l", (0, 0))[1],
                                            -80)
    A.append(han5)
    x_tab5 = 1650
    A.append(static("table5", P.table, x_tab5, FL + 20, 30, w=220, h=100, items=[("cakes", 50)]))
    fish = prop("fish", lambda c, a, f: _fish(c, a, f), x_tab5 - 40, FL + 20 - 100 * SS, 31)
    A.append(fish)
    lang5 = Actor("lang5", CH["lang_stand"], x_tab5 + 250, FL, 29, facing=-1)
    att5 = Actor("att5", CH["attendant2"], x_tab5 - 200, FL + 10, 32, facing=1)
    A += [lang5, att5]
    lang5.key("look", CUE["fish_grab"] - 40, -0.3).key("look_y", CUE["fish_grab"] - 40, 0.6)
    lang5.key("paw_r", CUE["fish_grab"] - 20, (0, 0)).key("paw_r", CUE["fish_grab"], (-150, 70), "inout")
    lang5.key("reach_r", CUE["fish_grab"] - 22, 1.0).key("reach_r", CUE["fish_grab"] - 4, 1.8)
    lang5.key("reach_r", CUE["fish_caught"] + 14, 1.8).key("reach_r", CUE["fish_caught"] + 24, 1.0)
    lang5.key("paw_r", CUE["fish_grab"] + 16, (-60, 20), "inout")
    fish.key("x", CUE["fish_grab"], x_tab5 - 40).key("x", CUE["fish_grab"] + 16, x_tab5 + 150, "inout")
    fish.key("y", CUE["fish_grab"], FL + 20 - 100 * SS).key("y", CUE["fish_grab"] + 16, FL - 250, "inout")
    lang5.key("pupil", CUE["fish_grab"], 1.0)
    att5.key("x", CUE["fish_caught"] - 20, x_tab5 - 200).key("x", CUE["fish_caught"], x_tab5 - 110, "inout")
    att5.key("paw_l", CUE["fish_caught"], (-60, -60), "snap").key("paw_l", CUE["fish_caught"] + 20, (0, 0))
    ev.emit(CUE["fish_caught"], "paw_tap", x=x_tab5)
    lang5.key("ear_l", CUE["fish_caught"] + 2, 40, "snap").key("ear_r", CUE["fish_caught"] + 2, 40, "snap")
    lang5.key("paw_r", CUE["fish_caught"] + 10, (0, 0), "snap")
    fish.key("x", CUE["fish_caught"] + 10, x_tab5 - 40, "inout").key("y", CUE["fish_caught"] + 10, FL + 20 - 100 * SS, "in")
    meow(ev, lang5, CUE["fish_caught"] + 12, 14, 0.7, "meow_sheepish")
    lang5.key("look", CUE["fish_caught"] + 30, 1.0).key("ear_l", CUE["fish_caught"] + 60, 0).key("ear_r", CUE["fish_caught"] + 60, 0)
    # a cat that fits (almost) in a basket
    x_bask = 1300
    A.append(static("basket", P.basket, x_bask, FL + 20, 30, w=90, h=60))
    bcat = Actor("bcat", CH["attendant"], x_bask + 200, FL + 20, 29, facing=-1)
    A.append(bcat)
    walk(bcat, CUE["basket"] - 40, CUE["basket"], x_bask + 200, x_bask + 10)
    bcat.key("y", CUE["basket"] + 2, FL + 20).key("y", CUE["basket"] + 14, FL + 20 + 34 * SS, "inout")
    bcat.key("body_y", CUE["basket"] + 14, 0)
    happy(bcat, CUE["basket"] + 16, CUE["basket"] + 120)
    A.append(static("basket_front", P.basket, x_bask, FL + 20, 30.5, w=90, h=60))
    ev.emit(CUE["basket"] + 12, "basket_creak", x=x_bask)
    ev.emit(CUE["basket"] + 30, "purr", who="bcat", x=x_bask, dur=3.0)
    # the moth lands on Han's nose
    moth.key("visible", 2580, 1.0, "step").key("visible", 2579, 0.0, "step")
    nose = lambda f: (x_han5 - 22 * han5.char.scale - 6 * han5.char.scale,                     # noqa: E731
                      FL + (-GROUND["stand"] - 50 + 16) * han5.char.scale)
    nx, ny = nose(2632)
    moth.keys("x", [(2580, 1500), (2610, 1900), (CUE["moth_nose"], nx), (CUE["blow"], nx), (CUE["blow"] + 20, nx - 300)])
    moth.keys("y", [(2580, 300), (2610, 360), (CUE["moth_nose"], ny - 14), (CUE["blow"], ny - 14),
                    (CUE["blow"] + 20, ny - 260)])
    moth.key("visible", CUE["blow"] + 22, 0.0, "step")
    look_at(han5, 2590, CUE["moth_nose"] - 2, moth_pos, step=3)
    han5.key("look", CUE["moth_nose"], 0.0).key("look_y", CUE["moth_nose"], 0.9)
    han5.key("crosseyed", CUE["moth_nose"] + 2, 1.0).key("crosseyed", CUE["blow"] + 6, 0.0)
    han5.key("mouth", CUE["blow"] - 2, 0.0).key("mouth", CUE["blow"] + 2, 0.25).key("mouth", CUE["blow"] + 14, 0.0)
    ev.emit(CUE["blow"], "blow", x=x_han5)
    happy(han5, CUE["blow"] + 16, 2712)

    cam.key(2410, x=1950, z=C.Z_SCROLL).key(2450, x=1720, y=600, z=1.5).key(2525, x=1700, y=600, z=1.5)
    cam.key(2560, x=1360, y=640, z=1.4).key(2600, x=1360, y=640, z=1.4)
    cam.key(2630, x=nx + 60, y=ny + 40, z=2.6).key(CUE["blow"] + 10, x=nx + 60, y=ny + 40, z=2.6)
    cam.key(2712, x=950, y=500, z=C.Z_SCROLL)

    # ============================================================================ epilogue
    x_kit = 640
    A.append(static("screen5", P.screen, 1000, FL, 20, w=320, h=520, seed=61))
    A.append(static("desk", P.table, x_kit - 110, FL + 20, 25, w=150, h=70, items=[]))
    kitE = Actor("kitE", CH["kitten"], x_kit, FL + 20, 26, facing=-1)
    kitE.hold = kitten_hold
    kitE.base.update(paw_l=(10, -40), paw_r=(0, -30))
    for i in range(20):
        kitE.key("paw_r", 2713 + i * 3, (0, -30) if i % 2 else (-10, -22), "lin")
    happy(kitE, CUE["sketch_done"], CUE["sketch_done"] + 20)
    A.append(kitE)
    hanE = Actor("hanE", CH["han_stand"], 1060, FL - 20, 24, facing=-1)
    A.append(hanE)
    hanE.key("visible", 0, 0.0, "step").key("visible", CUE["han_behind"] - 30, 1.0, "step")
    walk(hanE, CUE["han_behind"] - 30, CUE["han_behind"] + 10, 1060, x_kit + 100)
    hanE.key("look", CUE["han_behind"] + 10, -0.6).key("look_y", CUE["han_behind"] + 10, 0.7)
    kitE.key("pupil", CUE["han_behind"] + 16, 1.0, "snap").key("ear_l", CUE["han_behind"] + 16, 30, "snap")
    kitE.key("ear_r", CUE["han_behind"] + 16, 30, "snap").key("look", CUE["han_behind"] + 16, 1.0)
    hanE.key("paw_l", CUE["pat"] - 10, (0, 0)).key("paw_l", CUE["pat"], (-28, -8), "inout")
    for i in range(3):
        hanE.key("paw_l", CUE["pat"] + 4 + i * 8, (-28, 2)).key("paw_l", CUE["pat"] + 8 + i * 8, (-28, -8))
    hanE.key("paw_l", CUE["pat"] + 34, (0, 0))
    happy(kitE, CUE["pat"], CUE["pull_back"] + 60)
    kitE.key("ear_l", CUE["pat"], 0).key("ear_r", CUE["pat"], 0).key("pupil", CUE["pat"], 0.35)
    ev.emit(CUE["pat"], "purr", who="kitten", x=x_kit, dur=4.0)
    happy(hanE, CUE["pat"] + 10, CUE["pull_back"] + 60)
    tea = prop("tea", lambda c, a, f: _tea(c, a, f), x_kit + 60, FL - 200, 27)
    tea.key("visible", 0, 0.0, "step").key("visible", CUE["tea"], 1.0, "step")
    tea.key("x", CUE["tea"], x_kit + 120).key("x", CUE["tea"] + 20, x_kit - 60)
    tea.key("y", CUE["tea"], FL - 210).key("y", CUE["tea"] + 20, FL - 150)
    A.append(tea)
    ev.emit(CUE["tea"] + 20, "tea_set", x=x_kit)
    seal = prop("seal", lambda c, a, f: _seal(c, a, f), 470, 600, 80)
    seal.key("visible", 0, 0.0, "step").key("visible", CUE["seal"] - 1, 1.0, "step")
    seal.key("s", CUE["seal"] - 1, 1.6).key("s", CUE["seal"] + 3, 1.0, "in")
    A.append(seal)
    ev.emit(CUE["seal"], "seal_thump", x=470)
    cam.key(2730, x=780, y=560, z=1.35).key(CUE["pull_back"], x=780, y=560, z=1.35)
    cam.key(2990, x=C.SCROLL_L / 2, y=500, z=C.W / (C.SCROLL_L + 400), ease="inout")
    cam.key(C.FRAME_END, x=C.SCROLL_L / 2, y=500, z=C.W / (C.SCROLL_L + 400))

    # light through the night: warm dim candlelight deepening to midnight, cool at dawn
    tint = Track((1.0, 1.0, 1.0))
    tint.key(1, (1.0, 0.97, 0.9)).key(840, (0.98, 0.9, 0.78)).key(1464, (0.95, 0.86, 0.72))
    tint.key(1848, (0.9, 0.8, 0.66)).key(2376, (0.94, 0.86, 0.74)).key(2712, (0.96, 0.95, 0.94))
    tint.key(3072, (0.98, 0.98, 1.0))
    stage = Stage(cam, A, T, light=lambda f: (tint(f), 1.0))
    t0 = CUE["title_card"]
    title = text_image("韩熙载夜宴图 · 猫", 104, False, color=(236, 224, 200))
    sub = text_image("The Night Revels of Han Xizai  ·  Cat Edition", 40, False, font=EN_SERIF, color=(214, 200, 176))
    cred = text_image("Every stroke, note and meow is generated by code", 30, False, font=EN_SERIF,
                      color=(170, 158, 140))
    fade_in = Track(0.0).key(t0, 0.0).key(t0 + 24, 1.0).key(C.FRAME_END - 18, 1.0).key(C.FRAME_END, 0.0)
    stage.overlays = [dict(image=title, cx=C.W / 2, cy=300, scale=1.0, alpha=fade_in),
                      dict(image=sub, cx=C.W / 2, cy=760, scale=1.0, alpha=fade_in),
                      dict(image=cred, cx=C.W / 2, cy=830, scale=1.0, alpha=fade_in)]
    stage.black = Track(1.0).key(1, 1.0).key(30, 0.0, "out").key(C.FRAME_END - 18, 0.0).key(C.FRAME_END, 1.0)
    return stage, ev


# ------------------------------------------------------------------------------------------------ prop draws
def _draw_cup(c, a, f):
    with Xf(c, a.value("x", f), a.value("y", f), a.value("rot", f), SS * 1.8):
        P.dish(c, "celadon")


def _candle(c, a, f):
    with Xf(c, a.value("x", f), a.value("y", f), 0, SS):
        P.candle(c, f / C.FPS, 380, flicker_seed=hash(a.name) % 7)


def _drum(c, a, f, hits):
    last = min([f - n["frame"] for n in hits if n["frame"] <= f] or [99]) / C.FPS
    with Xf(c, a.value("x", f), a.value("y", f), 0, SS):
        P.drum(c, last)


def _basin(c, a, f):
    with Xf(c, a.value("x", f), a.value("y", f), 0, SS):
        P.basin(c, True, a.value("splash", f))


def _fish(c, a, f):
    with Xf(c, a.value("x", f), a.value("y", f), 0, SS):
        P.dish(c, "fish")


def _tea(c, a, f):
    with Xf(c, a.value("x", f), a.value("y", f), 0, SS):
        P.dish(c, "teabowl")


_SEAL = None


def _seal(c, a, f):
    global _SEAL
    if _SEAL is None:
        _SEAL = seal_image("顾氏", 120)
    s = a.value("s", f) * 2.6
    import skia
    c.drawImageRect(_SEAL, skia.Rect.MakeXYWH(a.value("x", f) - 60 * s, a.value("y", f) - 60 * s, 120 * s, 120 * s),
                    skia.SamplingOptions(skia.FilterMode.kLinear), None)
