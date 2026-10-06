"""Deterministic, code-drawn human puppets and cinematic environments (Skia)."""
from functools import lru_cache
import math

import numpy as np
import skia

from codecinema import settings
from story import CANON

INK = "#080f17"
IVORY = "#e9dfcd"
GOLD = "#c5a16f"
RED = "#b62b3c"
BLUE = "#689eb5"
TOP, BOTTOM = 132, 948


def smooth(x):
    x = max(0., min(1., x))
    return x * x * (3 - 2 * x)


def col(h, a=1):
    h = h.lstrip("#")
    return skia.Color4f(*(int(h[i:i+2], 16) / 255 for i in (0, 2, 4)), a)


def paint(h, a=1, width=0):
    p = skia.Paint(AntiAlias=True, Color4f=col(h, a))
    if width:
        p.setStyle(skia.Paint.kStroke_Style)
        p.setStrokeWidth(width)
        p.setStrokeCap(skia.Paint.kRound_Cap)
        p.setStrokeJoin(skia.Paint.kRound_Join)
    return p


def rect(c, x, y, w, h, color, a=1, radius=0):
    r = skia.Rect.MakeXYWH(x, y, w, h)
    if radius:
        c.drawRoundRect(r, radius, radius, paint(color, a))
    else:
        c.drawRect(r, paint(color, a))


def ellipse(c, x, y, rx, ry, color, a=1, width=0):
    c.drawOval(skia.Rect.MakeLTRB(x-rx, y-ry, x+rx, y+ry), paint(color, a, width))


def line(c, x, y, xx, yy, color, a=1, width=1):
    c.drawLine(x, y, xx, yy, paint(color, a, width))


def path(points, closed=True):
    p = skia.Path()
    p.moveTo(*points[0])
    for point in points[1:]:
        p.lineTo(*point)
    if closed:
        p.close()
    return p


def curve(points, closed=True):
    p = skia.Path()
    p.moveTo(*points[0])
    n = len(points)
    for i in range(n if closed else n-1):
        a, b = points[i], points[(i+1) % n]
        prev = points[(i-1) % n] if (closed or i) else a
        nxt = points[(i+2) % n] if (closed or i+2 < n) else b
        p.cubicTo(a[0]+(b[0]-prev[0])/6, a[1]+(b[1]-prev[1])/6,
                  b[0]-(nxt[0]-a[0])/6, b[1]-(nxt[1]-a[1])/6, *b)
    if closed:
        p.close()
    return p


def shape(c, points, color, outline=INK, width=1.5, a=1, rounded=True):
    p = curve(points) if rounded else path(points)
    c.drawPath(p, paint(color, a))
    if outline:
        c.drawPath(p, paint(outline, a, width))
    return p


def gradient(c, bounds, colors, a=1, horizontal=False):
    x, y, w, h = bounds
    shader = skia.GradientShader.MakeLinear([skia.Point(x, y), skia.Point(x+w if horizontal else x, y if horizontal else y+h)],
                                           [col(x, a) for x in colors])
    c.drawRect(skia.Rect.MakeXYWH(*bounds), skia.Paint(Shader=shader))


def glow(c, x, y, radius, color, a=.25, rx=1):
    c.save()
    c.translate(x, y)
    c.scale(rx, 1)
    shader = skia.GradientShader.MakeRadial(skia.Point(0, 0), radius, [col(color, a), col(color, 0)])
    c.drawCircle(0, 0, radius, skia.Paint(Shader=shader, AntiAlias=True))
    c.restore()


@lru_cache(maxsize=16)
def typeface(role):
    filename = settings.font(role)
    if filename:
        face = skia.Typeface.MakeFromFile(filename)
        if face:
            return face
    manager = skia.FontMgr.RefDefault()
    families = ("PingFang SC", "Noto Serif CJK SC", "Noto Sans CJK SC", "Microsoft YaHei")
    for family in families:
        face = manager.matchFamilyStyle(family, skia.FontStyle())
        if face and all(skia.Font(face).textToGlyphs("戏神")):
            return face
    raise RuntimeError("A CJK font is required; set XISHEN_FONTS_SONG to a Noto Serif CJK or Songti font.")


@lru_cache(maxsize=512)
def text_blob(s, size, role="song"):
    font = skia.Font(typeface(role), size)
    return skia.TextBlob.MakeFromText(s, font), font.measureText(s)


def text(c, s, x, y, size=32, color=IVORY, a=1, align="left", role="song"):
    if not s:
        return
    blob, w = text_blob(s, size, role)
    xx = x-w/2 if align == "center" else x-w if align == "right" else x
    c.drawTextBlob(blob, xx, y, paint(color, a))


# Each face has its own silhouette and body proportions, shared across all shots.
CAST = {
    "chen_ling": dict(cheek=25, jaw=15, chin=5, eye=11, shoulder=40, waist=26, hip=30, hair="fringe", age=0),
    "chen_tan": dict(cheek=26, jaw=20, chin=10, eye=11.5, shoulder=42, waist=30, hip=31, hair="receding", age=2),
    "li_xiuchun": dict(cheek=25, jaw=17, chin=5, eye=10.5, shoulder=36, waist=28, hip=35, hair="bun", age=1),
    "han_meng": dict(cheek=29, jaw=25, chin=13, eye=12, shoulder=54, waist=36, hip=37, hair="side", age=1),
    "jiang_qin": dict(cheek=25, jaw=20, chin=8, eye=11, shoulder=46, waist=30, hip=32, hair="crop", age=0),
    "doctor_lin": dict(cheek=24, jaw=16, chin=6, eye=10.5, shoulder=40, waist=27, hip=31, hair="part", age=1),
    "zhao_yi": dict(cheek=25, jaw=17, chin=7, eye=11, shoulder=40, waist=26, hip=29, hair="messy", age=0),
    "uncle_zhao": dict(cheek=31, jaw=26, chin=14, eye=13, shoulder=50, waist=43, hip=43, hair="balding", age=2),
    "xiao_liu": dict(cheek=24, jaw=17, chin=6, eye=10, shoulder=37, waist=25, hip=28, hair="soft", age=0),
}


def stroke(c, points, color, a=1, width=1):
    c.drawPath(curve(points, False), paint(color, a, width))


def hair(c, kind, t=0):
    dark, sheen = "#101923", "#566578"
    if kind == "bun":
        ellipse(c, 25, -349, 13, 14, dark)
        shape(c, [(-27,-323),(-29,-345),(-19,-361),(4,-367),(25,-357),(29,-337),(25,-316),
                  (22,-342),(9,-349),(-5,-347),(-20,-338),(-24,-316)], dark, "#090f19", .8)
        for j in range(4):
            stroke(c, [(-20+j*6,-352),(-3+j*4,-359),(17,-352)], sheen, .27, .65)
    elif kind in ("receding", "balding"):
        for side in (-1, 1):
            shape(c, [(side*24,-318),(side*29,-328),(side*28,-346),(side*22,-352),
                      (side*20,-339),(side*22,-326)], "#302f30", None)
            for j in range(3):
                stroke(c, [(side*(23+j),-345),(side*(25+j),-332),(side*25,-325)], "#aaa89e", .5, .6)
        if kind == "receding":
            stroke(c, [(-17,-357),(-3,-361),(15,-355)], "#514945", .9, 1.3)
    elif kind == "fringe":
        shape(c, [(-26,-316),(-32,-337),(-30,-355),(-17,-365),(2,-370),(20,-367),
                  (30,-355),(31,-333),(25,-310),(21,-337),(16,-325),(10,-348),(6,-327),
                  (-2,-345),(-8,-329),(-12,-346),(-20,-328),(-24,-311)], dark, "#080e18", .9)
        for j, x in enumerate((-23,-15,-6,4,13,22)):
            stroke(c, [(x-5,-358),(x,-349),(x+3,-332+j%2*5)], sheen, .35, .75)
            stroke(c, [(x-3,-349),(x,-337),(x+1,-329+j%2*4)], "#839198", .18, .45)
    elif kind in ("side", "part"):
        shape(c, [(-26,-316),(-29,-345),(-22,-359),(0,-366),(23,-359),(31,-347),(28,-319),
                  (23,-323),(23,-342),(7,-348),(-1,-354),(-13,-342),(-21,-344),(-22,-318)], dark, "#080e18", .9)
        if kind == "part":
            stroke(c, [(1,-364),(-1,-355),(-4,-347)], "#9b9389", .7, 1.1)
        for j in range(4):
            stroke(c, [(-18+j*8,-358),(-12+j*7,-353),(12+j*3,-345)], sheen, .34, .8)
        if kind == "side":
            for j in range(3):
                line(c,-25,-338+j*5,-22,-338+j*5,"#879098",.28,.65)
    else:
        messy = kind == "messy"
        points = [(-25,-316),(-31,-341),(-26,-357),(-15,-360),(-10,-371 if messy else -365),
                  (0,-365),(8,-372 if messy else -366),(14,-361),(24,-365 if messy else -358),
                  (30,-346),(28,-320),(23,-316),(22,-342),(13,-340),(6,-344),(-4,-340),(-18,-341),(-22,-316)]
        shape(c, points, dark, "#080e18", .9)
        for j in range(5):
            x = -20+j*9
            stroke(c, [(x,-359),(x+4,-352),(x+3,-342)], sheen, .3, .65)


def hand(c, x, y, skin, side=1, gesture=False):
    c.save(); c.translate(x,y); c.scale(side,1)
    if gesture:
        shape(c,[(-6,-1),(1,-5),(8,-12),(10,-11),(5,-1),(11,3),(14,10),(10,15),
                 (3,13),(-2,7),(-6,6)],skin,"#765b55",.65)
        stroke(c,[(5,3),(10,5),(10,10)],"#927067",.65,.55)
    else:
        shape(c,[(-5,-3),(5,-3),(7,5),(6,17),(3,19),(-1,17),(-4,9),(-6,3)],skin,"#765b55",.6)
        for x0 in (0,3):
            stroke(c,[(x0,6),(x0+1,13),(x0,16)],"#8c6e64",.65,.45)
        stroke(c,[(-5,2),(-1,3),(1,8)],"#8c6e64",.65,.55)
    c.restore()


def character(c, who, x, y, scale=1.5, t=0, costume=None, emotion="neutral", pose="stand", facing=1,
              rotation=0, injured=True, silhouette=False):
    """A consistent graphic-novel cast; dialogue drives the face on its real clock."""
    from codecinema.audio.performance import current_mouth
    spec, model = CANON["characters"][who], CAST[who]
    costume = costume or spec["costumes"][0]
    skin = spec["skin"]
    seed = sum(map(ord, who))
    breath = math.sin(t*1.45+seed)*.7
    walk = math.sin(t*(6.0 if pose=="run" else 3.5))*13 if pose in ("walk","run") else 0
    shoulder, waist, hip = model["shoulder"], model["waist"], model["hip"]
    robe = costume == "red_robe"
    c.save(); c.translate(x,y+breath*scale); c.rotate(rotation); c.scale(scale*facing,scale)
    if silhouette:
        ellipse(c,0,-331,24,31,"#101a23")
        shape(c,[(-37,-291),(-42,-174),(-26,-5),(21,-5),(37,-174),(35,-291)],"#101a23",None)
        c.restore(); return
    colors = {
        "red_robe": ("#922b40","#451c2d","#d1525a"),
        "black_coat": ("#243640","#101d28","#637681"),
        "memory_shirt": ("#b9b5a4","#696c68","#ece4cc"),
        "father_home": ("#595450","#2c3034","#978a76"),
        "mother_home": ("#78656a","#40353e","#b08d8b"),
        "raincoat": ("#1f2d39","#101a25","#566b76"),
        "officer_coat": ("#172a37","#09151f","#607583"),
        "uniform": ("#293b48","#101e2b","#647889"),
        "white_coat": ("#d1d2c6","#788b8e","#f3ecd8"),
        "work_jacket": ("#856153","#422d30","#b08766"),
        "apron": ("#947854","#514331","#c5a979"),
        "green_jacket": ("#536d5c","#293f3a","#8b9d7b"),
    }
    base, dark, light = colors[costume]
    # Long, articulated legs and individual body silhouettes replace the old dolls.
    ellipse(c,0,-2,62,8,"#060e16",.33)
    for side in (-1,1):
        swing=walk*side
        xx=side*16+swing*.4
        shape(c,[(side*hip*.65,-168),(side*7,-165),(xx-7,-86),(xx-7,-10),
                 (xx+8,-9),(xx+10,-81),(side*(hip+2),-157)],"#26343c","#0f1923",.8)
        stroke(c,[(side*20,-146),(xx+2,-86),(xx+2,-25)],"#657078",.33,.9)
        if robe:
            shape(c,[(xx-7,-14),(xx+7,-14),(xx+12,-5),(xx+20,-2),(xx+18,2),
                     (xx-9,2)],skin,"#705d5b",.6)
            for j in range(3): line(c,xx+8+j*3,-2,xx+8+j*3,1,"#856861",.6,.5)
        else:
            shape(c,[(xx-8,-18),(xx+8,-17),(xx+12,-5),(xx+22,-2),(xx+21,3),(xx-10,3)],"#101b24","#070e18",.8)
            line(c,xx-6,-12,xx+8,-11,"#7c8787",.55,.8)
            line(c,xx-8,1,xx+20,1,"#52616b",.65,1)
    hem=-40 if robe else -61 if costume in ("black_coat","officer_coat","white_coat","raincoat") else -147
    drift=math.sin(t*.85)*2.0 if robe else .4
    body=[(-12,-297),(-shoulder,-289),(-shoulder-3,-244),(-waist-2,-172),
          (-hip-9+drift,hem),(-10+drift,hem+4),(hip+8+drift,hem),(waist+4,-174),
          (shoulder+2,-244),(shoulder,-289),(12,-297)]
    shape(c,body,base,"#0d1722",1)
    shape(c,[(-shoulder,-277),(-waist,-177),(-hip-8,hem),(-10,hem+1),(-12,-187),(-6,-283)],dark,None,a=.48)
    shape(c,[(shoulder-5,-279),(waist+1,-176),(hip+4,hem),(hip-5,hem+1),(waist-5,-181)],light,None,a=.16)
    if robe:
        shape(c,[(-12,-295),(-28,-279),(-17,-245),(23,-201),(28,-210),(2,-263)],light,None,a=.72)
        shape(c,[(12,-295),(27,-278),(19,-253),(-16,-219),(-23,-224),(2,-265)],dark,None)
        # Subtle woven trim and asymmetrical fabric folds.
        stroke(c,[(-25,-279),(-12,-249),(21,-208)],"#e5a08c",.54,1.1)
        stroke(c,[(-13,-181),(-23,-105),(-25,hem+3)],light,.36,1.2)
        stroke(c,[(21,-198),(9,-124),(3,hem+3)],dark,.9,2.2)
        for j in range(4):
            xx=-24+j*16
            stroke(c,[(xx,-167),(xx+math.sin(j)*6,-98),(xx+drift*1.4,hem+3)],light,.20,.8)
        rect(c,-waist-4,-186,(waist+4)*2,9,dark)
    else:
        shape(c,[(-9,-297),(8,-297),(13,-230),(-14,-230)],"#bbc0b5" if costume=="white_coat" else dark,None)
        shape(c,[(-12,-295),(-shoulder+8,-277),(-20,-257),(-9,-243),(-4,-260)],light,None,a=.54)
        shape(c,[(12,-295),(shoulder-8,-277),(21,-257),(9,-243),(4,-260)],light,None,a=.41)
        stroke(c,[(-12,-295),(-21,-270),(-9,-244)],dark,.65,.8)
        stroke(c,[(12,-295),(22,-269),(9,-244)],dark,.65,.8)
        line(c,3,-237,3,hem+1,dark,.9,1)
        for yy in range(-224,int(hem),30):
            ellipse(c,5,yy,1.8,1.8,light,.85)
            ellipse(c,5.3,yy-.4,.45,.45,IVORY,.6)
        for side in (-1,1):
            stroke(c,[(side*(waist-7),-212),(side*waist,-191),(side*(hip+3),hem+1)],dark,.55,1)
            if hem < -100:
                line(c,side*(waist-13),-193,side*(waist-1),-197,light,.65,1.2)
        if costume in ("black_coat","officer_coat"):
            for side in (-1,1):
                line(c,side*(waist-18),-204,side*(waist-2),-201,dark,1,2)
                line(c,side*(waist-18),-203,side*(waist-2),-200,light,.38,.7)
        if costume=="uniform":
            rect(c,-shoulder+4,-278,17,4,RED)
            rect(c,shoulder-21,-278,17,4,RED)
            rect(c,-waist-3,-182,(waist+3)*2,6,"#17212b")
            rect(c,-4,-182,9,6,"#bda479",radius=1)
        if costume=="white_coat":
            rect(c,14,-250,17,18,"#bcc6bc",radius=1)
            line(c,19,-256,19,-238,"#345369",1,1.7)
            line(c,22,-255,22,-239,"#6e5146",1,1.2)
        if costume=="apron":
            shape(c,[(-29,-265),(28,-265),(39,-153),(43,-92),(-42,-92),(-37,-153)],"#c5b389",dark,.7)
            rect(c,-23,-179,44,24,"#b59a73",radius=2)
            line(c,-23,-154,21,-154,light,.7,.8)
    # Sleeves use elbow bends; hands have slender individual fingers.
    for side in (-1,1):
        raised=pose in ("hold","offer","point") and side==1
        hx=side*(57 if raised else shoulder+11)
        hy=(-223 if pose=="point" else -203) if raised else -144+walk*side*.28
        elbowx=side*(shoulder+16)
        elbowy=-199 if raised else -215
        cuff=15 if robe else 9
        shape(c,[(side*(shoulder-4),-286),(side*(shoulder+10),-280),
                 (elbowx+side*9,elbowy),(hx+side*cuff,hy-3),(hx-side*cuff,hy+5),
                 (elbowx-side*8,elbowy+7),(side*(shoulder-10),-249)],base,"#12202b",.8)
        stroke(c,[(side*(shoulder+4),-269),(elbowx,elbowy),(hx,hy-8)],light,.46,1.0)
        line(c,hx-cuff,hy-1,hx+cuff,hy-2,dark,.8,2 if robe else 1.3)
        hand(c,hx,hy+2,skin,side,gesture=pose=="point" and raised)
    # A smaller head, defined jaw and sculpted planes keep human proportions.
    shape(c,[(-9,-311),(-9,-287),(0,-277),(10,-288),(9,-311)],skin,"#695f5b",.65)
    shape(c,[(-9,-307),(9,-307),(7,-288),(-6,-286)],"#8a6e65",None,a=.47)
    cheek,jaw,chin=model["cheek"],model["jaw"],model["chin"]
    face=[(-cheek+3,-346),(-cheek,-331),(-cheek+2,-317),(-jaw,-307),(-chin,-301),
          (chin,-301),(jaw,-307),(cheek-1,-319),(cheek,-335),(cheek-4,-349),(1,-357)]
    face_path=shape(c,face,skin,"#3a3033",.55)
    c.save(); c.clipPath(face_path,doAntiAlias=True)
    gradient(c,(-cheek,-358,cheek*2,58),["#f0d6c6",skin,"#a98779"],a=.56,horizontal=True)
    glow(c,-11,-337,23,"#f7deca",.16,rx=.7)
    glow(c,cheek+4,-326,28,"#664750",.18,rx=.65)
    glow(c,0,-352,17,"#7c6061",.22,rx=1.6)
    c.restore()
    shape(c,[(cheek-5,-346),(cheek,-333),(cheek-2,-318),(jaw,-307),(chin,-302),
             (10,-307),(15,-323),(14,-345)],"#96766c",None,a=.36)
    shape(c,[(-15,-344),(-21,-331),(-18,-319),(-8,-316),(-4,-330),(-6,-345)],"#f4daca",None,a=.14)
    for side in (-1,1):
        ellipse(c,side*(cheek+1),-328,3.2,6.5,skin)
        stroke(c,[(side*(cheek+1),-332),(side*(cheek+2),-328),(side*cheek,-324)],"#936b62",.7,.6)
    blink=((t+seed*.017)%5.4)>5.27
    tense=emotion in ("afraid","lost")
    gaze=math.sin(t*.31+seed)*.6
    for side in (-1,1):
        ex=side*model["eye"]; ey=-330
        outer=ey-(.7 if who in ("chen_ling","zhao_yi") else 0)
        height=1.9 if tense else 1.05 if who=="han_meng" else 1.4
        if blink:
            stroke(c,[(ex-5.6,ey),(ex,ey+1.0),(ex+5.4,outer)],"#30272e",1,1.05)
        else:
            shape(c,[(ex-5.6,ey),(ex-2.5,ey-height),(ex+3.0,ey-height+.4),(ex+5.4,outer),
                     (ex+2.8,ey+height-.3),(ex-2.7,ey+height)],"#e8ded3","#675453",.45)
            ellipse(c,ex+gaze,ey+.15,1.55,height+.2,spec["eyes"])
            ellipse(c,ex+gaze+.65,ey-.9,.55,.65,"#dfe9df",.9)
            stroke(c,[(ex-5.6,ey),(ex-2.5,ey-height),(ex+3,ey-height+.4),(ex+5.4,outer)],"#27242d",1,0.8)
            stroke(c,[(ex-5.3,ey+4.4),(ex+1,ey+4.7),(ex+5,ey+2.9)],"#a17d73",.45,.6)
        brow=ey-7.2
        tilt=side*-1.9 if tense else side*-1.0 if who=="han_meng" else side*.5
        if who=="zhao_yi" and side==1: brow-=2.0
        stroke(c,[(ex-6.7,brow-tilt),(ex-1,brow-.3),(ex+6.0,brow+tilt)],
               "#362d32",1,1.5 if who in ("han_meng","uncle_zhao","chen_tan") else 1.1)
        if model["age"]:
            stroke(c,[(ex-6,ey+5.6),(ex+1,ey+6.7),(ex+5,ey+5)],"#8b6c63",.5,.65)
    # Nose drawn with light planes rather than a cartoon hook.
    stroke(c,[(1,-330),(-1,-321),(-.5,-318),(4,-317)],"#977469",.82,.65)
    line(c,-2,-316,1,-315,"#78584f",.8,.55)
    line(c,1,-325,2,-320,"#efd9ca",.7,.7)
    mouth=current_mouth(who)
    my=-310
    if mouth.opening>.035:
        width={"a":4.3,"o":2.8,"i":5.1,"e":4.0,"f":4.5}.get(mouth.shape,4)
        height={"a":3.1,"o":3.2,"i":.8,"e":1.7,"f":.6}.get(mouth.shape,2)*mouth.opening+.3
        ellipse(c,.4,my,width,height,"#593238")
        if height>1.3:
            ellipse(c,.4,my-height*.48,width*.75,.5,"#e2d1bd",.75)
            ellipse(c,.5,my+height*.44,width*.57,height*.3,"#ae6d71",.65)
        stroke(c,[(-width,my),(.3,my-height-.4),(width,my)],"#885654",.6,.5)
    else:
        stroke(c,[(-5.7,my),(-.8,my-.6),(2.2,my),(5.7,my-.4 if emotion=="thinking" else my+.2)],"#815858",.96,.6)
        stroke(c,[(-3,my+1.7),(.5,my+2),(3.5,my+1.2)],"#f0d2c4",.7,.6)
    if model["age"]:
        for side in (-1,1):
            stroke(c,[(side*15,-318),(side*12,-311),(side*12,-307)],"#8d6d62",.38,.65)
        if model["age"]==2:
            stroke(c,[(-10,-348),(0,-349),(9,-347)],"#9b7c70",.4,.6)
            stroke(c,[(-12,-343),(-2,-344),(9,-342)],"#9b7c70",.38,.55)
    hair(c,model["hair"],t)
    if who=="chen_ling" and injured and costume!="memory_shirt":
        stroke(c,[(22,-341),(21,-336),(23,-333)],"#972936",.9,1.0)
        if robe:
            for j in range(4): ellipse(c,-28+j*18,hem+3-j*3,7,3,"#382432",.5)
    if who=="doctor_lin":
        for side in (-1,1):
            ex=side*model["eye"]
            c.drawRoundRect(skia.Rect.MakeXYWH(ex-8,-335,16,11),2,2,paint("#172732",1,1.2))
            line(c,ex-5,-333,ex+2,-333,"#c1d7d0",.15,.5)
        line(c,-3,-332,3,-332,"#172732",1,.9)
        line(c,-26,-332,-19,-332,"#172732",1,1)
        line(c,19,-332,26,-332,"#172732",1,1)
    if who=="uncle_zhao":
        shape(c,[(-31,-347),(-29,-360),(-2,-367),(28,-358),(31,-344),(0,-350)],"#d4cfb6","#70796c",.7)
        stroke(c,[(-25,-357),(-4,-359),(23,-353)],"#8c9581",.7,.8)
        stroke(c,[(-21,-353),(-3,-355),(24,-349)],"#f6efd7",.6,.7)
    if who=="han_meng":
        line(c,4,my,26,my+1,"#c8b393",1,3.2)
        line(c,24,my+1,27,my+1,"#b85c40",1,2.6)
        for j in range(5):
            glow(c,29+math.sin(t*.7+j)*5,-327-j*10-(t*4)%12,10,"#c1cad0",.065)
        if injured: line(c,22,-322,27,-318,RED,.92,.8)
    if costume=="raincoat":
        stroke(c,[(-31,-308),(-40,-339),(-29,-372),(0,-382),(31,-365),(38,-336),(30,-308)],"#101e29",1,8)
        stroke(c,[(-33,-321),(-35,-345),(-23,-365),(0,-375),(23,-361)],light,.26,1.2)
    if pose=="hold" and robe: barrel(c,5,-244,.8,t,broken=False)
    c.restore()


def lamp(c, x, y, s=1, t=0):
    c.save(); c.translate(x,y); c.scale(s,s)
    glow(c,0,-55,300,"#d99b54",.37)
    ellipse(c,0,0,34,8,"#1d2023")
    shape(c,[(-18,-9),(-15,-42),(15,-42),(20,-9)],"#8f7c59")
    shape(c,[(-16,-43),(-20,-76),(-13,-125),(13,-125),(20,-76),(16,-43)],"#749895",None,a=.15)
    c.drawPath(curve([(-16,-43),(-20,-76),(-13,-125),(13,-125),(20,-76),(16,-43)]),paint("#b5b4a0",.5,1.2))
    flame = math.sin(t*2.4)*2
    shape(c,[(-5,-46),(-7,-58),(flame,-78),(5,-56),(5,-46)],"#e6af68",None)
    shape(c,[(-2,-47),(0,-61),(3,-49)],"#fff0bd",None)
    ellipse(c,0,-126,14,4,"#444d4d")
    c.restore()


def barrel(c, x, y, s=1, t=0, broken=False):
    c.save(); c.translate(x,y); c.scale(s,s)
    shape(c,[(-31,-44),(-42,-23),(-45,30),(-35,45),(34,45),(44,29),(42,-23),(29,-44)],
          "#6f8c93","#183741",1.4,a=.85)
    for yy in (-17,16,31):
        c.drawPath(curve([(-42,yy),(-9,yy+5),(28,yy+3),(43,yy)],False),paint("#aac0bf",.5,2))
    line(c,-22,-24,-24,25,"#bfcecd",.45,3)
    if not broken:
        rect(c,-18,-62,36,20,"#567c85",radius=3)
        ellipse(c,0,-61,18,4,"#9db4b1")
    else:
        shape(c,[(-20,-45),(-15,-56),(-5,-42),(3,-53),(15,-40),(23,-49),(29,-44)],"#a2b9b7",None)
    c.restore()


def tricycle(c, x, y, t=0, s=1):
    c.save(); c.translate(x,y); c.scale(s,s)
    for xx in (-160,190):
        ellipse(c,xx,0,55,55,"#0e1c25",1,6)
        ellipse(c,xx,0,45,45,"#53616a",.6,2)
        for j in range(9):
            ang=j*math.tau/9-t*2
            line(c,xx,0,xx+44*math.cos(ang),44*math.sin(ang),"#88908a",.7,1.1)
    for a,b in [((-160,0),(-90,-106)),((-160,0),(20,0)),((20,0),(-90,-106)),((20,0),(190,0))]:
        line(c,*a,*b,"#8e8d75",1,5)
    rect(c,40,-114,240,60,"#55615f")
    for xx in range(55,281,30):
        line(c,xx,-111,xx,-55,"#273940",1,2)
    line(c,-90,-108,-94,-140,"#aab0a1",1,4)
    line(c,-126,-141,-66,-141,"#25373e",1,7)
    rect(c,-31,-97,57,9,"#242e33",radius=4)
    c.restore()


def architecture(c, day=False, shop=False):
    gradient(c,(0,0,1920,1080),["#182c3a" if day else "#0b1725","#45616b" if day else "#183341","#0b1b25"])
    rng=np.random.default_rng(39)
    # Layered roofs: independent shapes, all converging on the same street.
    for depth in range(3):
        for j in range(9):
            xx=j*255-80+depth*39
            yy=470+depth*55+int(rng.integers(-65,65))
            color=["#203340","#1a2f3b","#10212c"][depth]
            shape(c,[(xx,yy),(xx+113,yy-83),(xx+239,yy),(xx+236,790),(xx+4,790)],color,None,rounded=False)
    for side in (-1,1):
        for j in range(4):
            xx=0+j*178 if side==-1 else 1490+j*155
            yy=250+j*42 if side==-1 else 266-j*27
            ww=197
            color="#20313a" if side==-1 else "#192a34"
            shape(c,[(xx,yy),(xx+ww,yy+40),(xx+ww,826),(xx,924)],color,"#0b1b27",3,rounded=False)
            shape(c,[(xx-12,yy),(xx+ww+9,yy+39),(xx+ww+13,yy+58),(xx-15,yy+18)],"#0c1a25",None,rounded=False)
            for row in range(3):
                wy=yy+91+row*137
                rect(c,xx+45,wy,67,85,"#09151e")
                rect(c,xx+50,wy+7,57,69,"#9a815b" if (j+row)%3==0 else "#38494d",.58)
                line(c,xx+78,wy+6,xx+78,wy+77,"#12232c",1,3)
                line(c,xx+49,wy+41,xx+109,wy+41,"#12232c",1,3)
            for yy2 in range(int(yy+38),840,21):
                line(c,xx+5,yy2,xx+ww-8,yy2+5,"#607078",.1,1)
    shape(c,[(765,631),(1260,631),(1900,1080),(0,1080)],"#2c4048",None,rounded=False)
    for j in range(20):
        yy=636+(.07+j/20)**2*456
        line(c,0,yy,1920,yy,"#839697",.12,1.2)
    for xx in range(-800,2800,155):
        line(c,1020,626,xx,1080,"#859394",.10,1)
    for j in range(15):
        xx=float(rng.integers(200,1710)); yy=float(rng.integers(730,1030))
        ellipse(c,xx,yy,float(rng.integers(30,160)),5+j%5,"#83a4ac",.12)
    for xx in (230,1630):
        line(c,xx,315,xx,907,"#09131c",1,11)
        line(c,xx,340,xx+60,340,"#09131c",1,7)
        rect(c,xx+30,336,43,66,"#433b2e",radius=6)
        rect(c,xx+36,344,30,44,"#af9a62",.5,radius=4)
        glow(c,xx+51,365,150,"#d3a55f",.10)
    if shop:
        rect(c,1100,285,686,492,"#423c33")
        rect(c,1122,320,630,382,"#171f22")
        shape(c,[(1050,290),(1801,290),(1760,336),(1090,336)],"#5b6256",None,rounded=False)
        rect(c,1170,354,76,284,"#ab9b79")
        for j,ch in enumerate("豆浆油条"):
            text(c,ch,1208,406+j*57,36,"#393b33",align="center")
        rect(c,1270,678,474,124,"#77674d")
        for j in range(10):
            line(c,1279+j*44,685,1279+j*44,799,"#292d29",.25,2)


def interior(c, bedroom=False, clinic=False):
    gradient(c,(0,0,1920,1080),["#202930","#3d3935","#181f26"])
    rect(c,120,168,1670,582,"#3a3c3b")
    for xx in (115,560,1160,1790):
        rect(c,xx,160,23,693,"#14212a")
    for yy in (187,740):
        rect(c,108,yy,1702,22,"#13212a")
    shape(c,[(108,761),(1810,761),(1920,1080),(0,1080)],"#293238",None,rounded=False)
    for xx in range(-300,2500,98):
        line(c,960,603,xx,1080,"#9c937e",.16,1)
    for j in range(12):
        yy=760+j*j*3.3
        line(c,0,yy,1920,yy,"#a39176",.12,1)
    rect(c,210,270,282,334,"#142d3b")
    gradient(c,(227,287,245,296),["#254954","#142a37"])
    for xx in (235,350,465):
        rect(c,xx,278,10,318,"#0e1b24")
    rect(c,225,435,249,11,"#0e1b24")
    if bedroom:
        rect(c,601,685,1040,153,"#171f26")
        shape(c,[(587,648),(1584,648),(1660,736),(606,736)],"#727d7b",None,rounded=False)
        rect(c,580,587,23,265,"#1b252b")
        rect(c,1630,672,19,188,"#1b252b")
        ellipse(c,746,665,103,25,"#b0b3a1",.78)
        shape(c,[(852,657),(1527,657),(1605,728),(866,729)],"#344955",None,rounded=False)
        rect(c,1210,266,218,180,"#283036")
        line(c,1224,280,1412,280,"#807568",.4,2)
    elif clinic:
        rect(c,1240,231,370,264,"#29383f")
        for yy in (302,397,487):
            rect(c,1238,yy,375,10,"#5f5d50")
        for j in range(15):
            xx=1261+(j%5)*66; yy=297+(j//5)*94
            rect(c,xx,yy-42,34,41,"#9caaa0",.55,radius=4)
            rect(c,xx+5,yy-49,24,9,"#394a48")
            rect(c,xx+3,yy-23,28,12,"#c4c1a5",.7)
        rect(c,710,717,823,38,"#8e8066")
        shape(c,[(711,755),(1530,755),(1491,949),(744,949)],"#3b403a",None,rounded=False)
        text(c,"诊",626,378,85,"#91a599",.6)
    else:
        rect(c,681,704,873,28,"#665d4c")
        rect(c,722,732,22,200,"#252d30")
        rect(c,1480,732,22,200,"#252d30")
        for xx in (933,1374):
            rect(c,xx-63,623,126,173,"#243139")
            rect(c,xx-76,791,154,18,"#3e4847")
        rect(c,100,180,410,611,"#101b25")
        rect(c,137,204,332,583,"#1d2b35")
        line(c,302,207,302,783,"#0d1720",1,5)
        ellipse(c,430,556,5,5,"#8f8060")
    glow(c,1090,558,540,"#b98f59",.17)


def stage(c, memory=False, audience=False):
    gradient(c,(0,0,1920,1080),["#070c15","#121c28","#26313b"])
    curtain_color="#271d25" if memory else "#09111c"
    for j in range(43):
        xx=j*46
        rect(c,xx,150,39,520,curtain_color)
        gradient(c,(xx,151,35,519),["#39404a" if memory else "#25303d",curtain_color],.27,True)
    rect(c,120,174,1680,13,"#33404b")
    for xx in (530,950,1370):
        rect(c,xx,187,47,24,"#4b5053",radius=5)
        ellipse(c,xx+22,212,17,6,"#cfbca0",.7)
    shape(c,[(0,673),(1920,673),(1920,1030),(0,1030)],"#4b4542",None,rounded=False)
    for j in range(23):
        yy=675+(.01+j/23)**1.8*360
        line(c,0,yy,1920,yy,"#a48c74",.19,1.5)
    for xx in range(-1800,3900,210):
        line(c,960,511,xx,1080,"#111d28",.65,1.5)
    if audience:
        gradient(c,(0,0,1920,1080),["#070e18","#122434","#101b25"])
        for row in range(7):
            y=260+row*85
            scale=.52+row*.125
            count=18-row
            spacing=1920/(count+1)
            for j in range(count):
                x=(j+1)*spacing+(row%2)*spacing*.17
                rect(c,x-40*scale,y,80*scale,94*scale,"#343333",radius=12*scale)
                rect(c,x-34*scale,y+8*scale,68*scale,75*scale,"#15212b",radius=8*scale)
                ellipse(c,x,y-18*scale,21*scale,30*scale,"#070c13")
                shape(c,[(x-21*scale,y+9*scale),(x-34*scale,y+67*scale),(x+34*scale,y+67*scale),
                         (x+21*scale,y+9*scale)],"#080f18",None)


def graveyard(c):
    gradient(c,(0,0,1920,1080),["#253d4a","#55676a","#1f343e"])
    for layer in range(3):
        color=["#3b525b","#29434e","#162c38"][layer]
        for j in range(15):
            x=j*140+layer*26; y=760+layer*39; h=240+j%4*67
            line(c,x,y,x+13,y-h,color,1,5+layer*3)
            for k in range(4):
                by=y-h*.4-k*35
                line(c,x+9,by,x-42-k*6,by-56,color,1,3)
                line(c,x+9,by-22,x+72,by-66,color,1,2)
    shape(c,[(0,816),(240,767),(650,793),(1030,733),(1500,762),(1920,832),(1920,1080),(0,1080)],
          "#435258",None)
    for j in range(15):
        x=116+(j%6)*300+(j//6)*58; y=781+(j//6)*76
        ellipse(c,x,y,75,23,"#273c45")
        line(c,x-5,y-9,x+1,y-59,"#8b8b76",1,6)
        line(c,x-17,y-53,x+23,y-52,"#7e8374",1,4)
    shape(c,[(0,853),(1920,728),(1920,747),(0,872)],"#b8a768",None,rounded=False)
    for j in range(30):
        x=j*68
        line(c,x,851-x*.064,x+11,865-x*.064,"#393d38",1,6)
    glow(c,1050,466,570,"#9abbbe",.10)


@lru_cache(maxsize=12)
def background(kind):
    s=skia.Surface(1920,1080); c=s.getCanvas()
    if kind in ("street", "day", "shop"):
        architecture(c,kind!="street",kind=="shop")
    elif kind in ("home", "bedroom", "clinic"):
        interior(c,kind=="bedroom",kind=="clinic")
    elif kind in ("stage", "memory", "audience"):
        stage(c,kind=="memory",kind=="audience")
    elif kind=="grave":
        graveyard(c)
    else:
        gradient(c,(0,0,1920,1080),["#0a1622","#253e4b","#172531"])
    return s.makeImageSnapshot()


def aurora(c,t):
    for j in range(11):
        p=skia.Path(); p.moveTo(-100,267+j*9)
        p.cubicTo(320,80+math.sin(t*.08)*38,695,495-j*9,1120,295+j*8)
        p.cubicTo(1490,103+j*5,1710,259,2010,116+j*6)
        c.drawPath(p,paint("#70bad0",.035+(5-abs(j-5))*.009,14))
    for j in range(6):
        p=skia.Path(); p.moveTo(-120,359+j*5)
        p.cubicTo(510,221,781,317+math.sin(t*.11)*15,1250,196+j*9)
        p.cubicTo(1470,139,1700,277,1980,160+j*4)
        c.drawPath(p,paint("#aacbd1",.035,9))


def rain(c,t,density=1):
    for j in range(int(110*density)):
        x=(j*157.19 + math.sin(j*5.2)*81-t*97)%2110-100
        y=(j*213.63+t*(690+(j%7)*37))%960+80
        length=17+j%6*4
        line(c,x,y,x-8,y+length,"#a8bac7",.14+(j%4)*.025,1.1)
    for j in range(14):
        phase=(t*.85+j*.391)%1
        ellipse(c,(j*193.7)%1820+40,797+j%4*35,phase*40,phase*6,"#a2c2c9",(1-phase)*.18,1)


def snow(c,t):
    for j in range(40):
        x=(j*319.7+t*8)%2000-40; y=(j*189.1+t*11)%860+90
        ellipse(c,x,y,1.2,1.2,"#d1dfdb",.25)


def spotlight(c,x,y,t):
    p=path([(945,205),(x-350,y),(x+350,y)])
    shader=skia.GradientShader.MakeLinear([skia.Point(945,205),skia.Point(x,y)],
                                         [col("#d8d3bb",.035),col("#d8d3bb",.16)])
    c.drawPath(p,skia.Paint(Shader=shader,AntiAlias=True))
    ellipse(c,x,y,351,41,"#bdc3b1",.19)
    for j in range(20):
        xx=x-250+(j*47.9+t*5)%500; yy=260+(j*113.8+t*3)%510
        ellipse(c,xx,yy,1,1,"#dbcdb1",.25)


def cup(c,x,y,s=1,liquid="#793943"):
    c.save(); c.translate(x,y); c.scale(s,s)
    ellipse(c,0,34,69,11,INK,.6)
    shape(c,[(-50,-34),(-45,20),(-25,37),(24,37),(45,20),(51,-34)],"#b7c3b9","#273840",1.8)
    ellipse(c,0,-33,51,15,"#273840")
    ellipse(c,0,-33,44,12,liquid)
    c.drawPath(curve([(48,-26),(76,-24),(78,5),(47,17)],False),paint("#b4c1b5",1,9))
    line(c,-34,-19,-30,13,"#eff0da",.45,2)
    c.restore()


@lru_cache(maxsize=1)
def grain():
    rng=np.random.default_rng(842)
    rgba=np.zeros((1080,1920,4),dtype=np.uint8)
    rgba[:,:,:3]=220
    rgba[:,:,3]=rng.integers(0,10,size=(1080,1920),dtype=np.uint8)
    return skia.Image.fromarray(rgba,colorType=skia.kRGBA_8888_ColorType)


def grade(c):
    c.drawImage(grain(),0,0)
    # Vignette and edge shading avoid crushed faces while framing every scene.
    gradient(c,(0,132,360,816),["#040b13","#040b13"],.10)
    gradient(c,(1560,132,360,816),["#040b13","#040b13"],.12)
    gradient(c,(0,790,1920,158),["#07111b","#07111b"],.22)
