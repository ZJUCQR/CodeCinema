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


def hair(c, kind, t):
    if kind == "bun":
        ellipse(c, 23, -369, 25, 24, "#1a2024")
        shape(c, [(-39,-333),(-38,-358),(-18,-378),(20,-375),(39,-350),(37,-322),(29,-341),
                  (0,-353),(-22,-348),(-33,-319)], "#171f25")
        line(c, -20, -359, 18, -365, "#607078", .35, 1.2)
    elif kind in ("receding", "balding"):
        shape(c, [(-39,-320),(-40,-348),(-31,-360),(-24,-338),(-28,-316)], "#262d31")
        shape(c, [(37,-320),(39,-350),(29,-358),(26,-337),(29,-314)], "#262d31")
        if kind == "receding":
            c.drawPath(curve([(-26,-363),(-3,-373),(25,-363)], False), paint("#4a4744", .8, 3))
    else:
        points = [(-41,-308),(-47,-342),(-39,-368),(-21,-383),(2,-382),(20,-388),(42,-365),
                  (46,-337),(38,-305),(31,-339),(20,-326),(16,-352),(4,-329),(-2,-348),
                  (-17,-327),(-18,-349),(-30,-330),(-35,-314)]
        if kind in ("short", "neat"):
            points = [(-39,-316),(-44,-346),(-32,-371),(2,-379),(33,-368),(44,-344),(35,-317),
                      (28,-344),(10,-346),(-16,-344),(-30,-339)]
        shape(c, points, "#101921", "#060b10", 2)
        for i in range(6):
            x = -29 + i*11
            c.drawPath(curve([(x-7,-367),(x,-354),(x+2,-335)], False), paint("#526374", .27, 1.2))


def character(c, who, x, y, scale=1.5, t=0, costume=None, emotion="neutral", pose="stand", facing=1,
              rotation=0, injured=True, speaking=False, silhouette=False):
    """One cast asset, shared across every shot; local coordinates are in puppet units."""
    spec = CANON["characters"][who]
    costume = costume or spec["costumes"][0]
    skin = spec["skin"]
    seed = sum(map(ord, who))
    breath = math.sin(t*1.55 + seed)*1.4
    walk = math.sin(t*4.3)*13 if pose in ("walk", "run") else 0
    c.save()
    c.translate(x, y+breath*scale)
    c.rotate(rotation)
    c.scale(scale*facing, scale)
    if silhouette:
        ellipse(c, 0, -325, 35, 48, "#101a23")
        shape(c, [(-42,-268),(-56,-60),(-22,-6),(26,-6),(52,-64),(41,-267)], "#101a23", None)
        c.restore()
        return
    robe = costume == "red_robe"
    colors = {"red_robe": ("#8f2234", "#511929", "#b13546"),
              "black_coat": ("#202f3a", "#101a25", "#53606a"),
              "memory_shirt": ("#9d9f9d", "#54606a", "#c3c2b5"),
              "father_home": ("#4f4e4b", "#303337", "#777268"),
              "mother_home": ("#70625e", "#403a40", "#92807a"),
              "raincoat": ("#192630", "#0c151f", "#344651"),
              "officer_coat": ("#162733", "#0a1520", "#334654"),
              "uniform": ("#273744", "#13222e", "#842b39"),
              "white_coat": ("#cdcac0", "#858e91", "#e5e0d0"),
              "work_jacket": ("#69534b", "#372d2e", "#8c6d57"),
              "apron": ("#ad8e62", "#50483d", "#c6ad84"),
              "green_jacket": ("#526963", "#283f3d", "#7e9184")}
    base, dark, light = colors[costume]
    # Feet and trousers remain anatomically anchored to the same pelvis.
    for side in (-1, 1):
        leg_x = side*22
        swing = walk*side
        shape(c, [(leg_x-12,-109),(leg_x+13,-110),(leg_x+14+swing,-13),(leg_x-9+swing,-11)], dark)
        if robe:
            shape(c, [(leg_x-10+swing,-15),(leg_x+13+swing,-13),(leg_x+23+swing,-3),
                      (leg_x+20+swing,1),(leg_x-12+swing,1)], skin)
            for j in range(3):
                line(c, leg_x+12+swing+j*3, -5, leg_x+12+swing+j*3, -1, "#897269", .65, .7)
        else:
            shape(c, [(leg_x-14+swing,-15),(leg_x+14+swing,-12),(leg_x+28+swing,-3),
                      (leg_x+24+swing,2),(leg_x-14+swing,2)], "#121b23")
    hem = -22 if robe else (-47 if costume in ("black_coat", "officer_coat", "raincoat") else -105)
    drift = math.sin(t*1.8+seed)*8 if robe else 2
    shape(c, [(-17,-287),(-42,-274),(-52,-218),(-43,-148),(-63+drift,hem),(-26,hem+10),
              (5,hem+5),(53+drift,hem+6),(48,-143),(47,-219),(38,-274),(15,-287)], base)
    if robe:
        shape(c, [(-18,-281),(-37,-271),(-26,-233),(20,-192),(27,-199),(-5,-251)], light, None, a=.46)
        shape(c, [(15,-280),(37,-270),(21,-231),(-18,-197),(-28,-201),(-1,-248)], dark, None)
    else:
        shape(c, [(-13,-282),(13,-282),(18,-220),(-17,-220)], dark, None)
        shape(c, [(-15,-283),(-32,-273),(-24,-247),(-8,-237),(-6,-252)], light, None, a=.68)
        shape(c, [(15,-283),(31,-273),(25,-247),(9,-236),(7,-252)], light, None, a=.59)
        line(c, 5, -234, 5, hem+6, dark, .85, 1.4)
        for yy in range(-216,int(hem),27):
            ellipse(c, 7, yy, 2.2, 2.2, light, .65)
    for j in range(6):
        xx = -38+j*14
        c.drawPath(curve([(xx,-179),(xx+math.sin(j)*8,-100),(xx+drift*.4,hem+2)], False),
                   paint(dark, .55, 1.6))
    rect(c, -43, -193, 87, 11, dark)
    if costume == "uniform":
        rect(c, -38, -194, 77, 7, RED)
        rect(c, -35, -269, 15, 6, RED)
    if costume == "apron":
        shape(c, [(-27,-250),(27,-250),(40,-72),(-39,-72)], "#dbc6a1", dark, 1.4)
        rect(c, -20, -157, 40, 32, "#b49b76", .8)
    if costume == "white_coat":
        for yy in (-202,-178,-154):
            ellipse(c, 3, yy, 2, 2, "#57636a")
        rect(c, 20, -230, 21, 24, "#aab1ac")
        line(c, 23, -243, 23, -224, "#3b5365", 1, 2)
    # Two sleeves: wide stage sleeves in red, weighted coat sleeves in daylight.
    for side in (-1, 1):
        sy = -180 + (walk*side*.35)
        reach = 25 if pose in ("hold", "offer", "point") else 0
        hand_x = side*(70-reach)
        hand_y = sy-40 if pose in ("hold", "offer") else sy+34
        width = 29 if robe else 17
        shape(c, [(side*35,-269),(side*53,-263),(side*(75-reach),sy-20),
                  (hand_x+side*width,hand_y-6),(hand_x-side*width,hand_y+8),(side*40,-219)], base)
        c.drawPath(curve([(side*45,-257),(side*57,sy-20),(hand_x,hand_y-8)], False), paint(light,.5,1.4))
        if robe:
            line(c, hand_x-side*width, hand_y+6, hand_x+side*width, hand_y-5, dark, 1, 3)
        shape(c, [(hand_x-8,hand_y),(hand_x+8,hand_y-3),(hand_x+11,hand_y+11),
                  (hand_x+3,hand_y+21),(hand_x-8,hand_y+14)], skin, "#6f6866", .7)
        for j in range(3):
            line(c, hand_x+j*3-2, hand_y+7, hand_x+j*3, hand_y+16, "#8e7970", .6, .7)
    # Neck, cheek contour, subtle face-plane shading.
    shape(c, [(-13,-305),(-14,-276),(0,-262),(14,-279),(13,-306)], skin)
    shape(c, [(-12,-303),(13,-303),(10,-282),(-7,-286)], "#988982", None, a=.52)
    jaw = 32 if spec["face"] in ("square", "angular") else 22
    shape(c, [(-35,-350),(-40,-325),(-33,-302),(-jaw,-285),(0,-275),(jaw,-285),(34,-305),
              (39,-329),(29,-359),(0,-370)], skin, "#19232b", 1.4)
    shape(c, [(23,-359),(35,-345),(37,-321),(27,-298),(9,-277),(22,-284),(33,-303),
              (39,-330)], "#a3928e", None, a=.62)
    ellipse(c, -37, -323, 6, 12, skin)
    ellipse(c, 36, -323, 5, 12, skin)
    line(c, -39, -325, -35, -318, "#8b7772", .8, 1)
    # Expression keeps features fixed while changing only brows, lids and mouth.
    blink = ((t+seed*.017) % 4.9) > 4.73
    wide = emotion in ("afraid", "lost")
    for side in (-1, 1):
        ex = side*17
        ey = -327
        if blink:
            c.drawPath(curve([(ex-10,ey),(ex,ey+2),(ex+10,ey-1)],False),paint("#222a31",1,1.6))
        else:
            shape(c, [(ex-11,ey),(ex-3,ey-5 if wide else ey-3),(ex+9,ey-1),
                      (ex+6,ey+5),(ex-5,ey+5)], "#ece2d5", "#3c3537", .8)
            ellipse(c, ex+1, ey+1, 3.6, 5.0 if wide else 4, spec["eyes"])
            ellipse(c, ex+2, ey-1, 1, 1.5, "#d1ddd9", .85)
            c.drawPath(curve([(ex-11,ey),(ex-3,ey-5),(ex+10,ey-1)],False),paint("#16232b",1,1.5))
        by = ey-15
        tilt = -4*side if emotion in ("afraid", "lost", "tired") else 1*side
        line(c, ex-10, by-tilt, ex+10, by+tilt, "#263139", 1, 2)
        c.drawPath(curve([(ex-9,ey+12),(ex,ey+14),(ex+7,ey+11)],False),paint("#958582",.5,.8))
    c.drawPath(curve([(1,-325),(-2,-311),(3,-307)],False),paint("#8b7470",.9,1.1))
    line(c, 2,-306,7,-307,"#8b7470",.75,.9)
    my = -294
    if speaking:
        ellipse(c, 1, my, 5.5, 2+2.8*(.5+.5*math.sin(t*13)), "#694b4c")
    else:
        c.drawPath(curve([(-8,my),(0,my+1),(8,my-1 if emotion=="thinking" else my+1)],False),paint("#624d4d",.9,1.1))
    line(c, -3,-290,4,-290,"#e1cec0",.7,.9)
    if spec["face"] in ("angular", "square", "soft"):
        for side in (-1,1):
            line(c, side*29,-310,side*26,-296,"#8a7973",.55,.7)
    hair(c, spec["hair"], t)
    if who == "chen_ling" and injured and costume != "memory_shirt":
        c.drawPath(curve([(29,-347),(27,-337),(31,-330)],False),paint("#942c3a",.85,1.5))
        if robe:
            for j in range(5):
                ellipse(c, -43+j*19, hem+17-j*9, 12, 7, "#34272d", .65)
    if who == "doctor_lin":
        for ex in (-17,17):
            c.drawRoundRect(skia.Rect.MakeXYWH(ex-13,-335,26,17),3,3,paint("#121e28",1,2))
        line(c, -4,-329,4,-329,INK,1,1.6)
        line(c, -40,-332,-30,-331,INK,1,1.6)
        line(c, 30,-331,39,-332,INK,1,1.6)
    if who == "uncle_zhao":
        shape(c,[(-40,-363),(-37,-377),(0,-386),(38,-375),(40,-361),(1,-365)],"#ceccc0",dark,1)
        line(c,-24,-376,27,-370,"#8b948c",.55,1.2)
    if who == "han_meng":
        line(c, 6,-294,33,-291,"#bfa889",1,5)
        ellipse(c,34,-291,2.5,2.5,"#b76246")
        for j in range(6):
            glow(c, 37+math.sin(t+j)*9, -312-j*14-(t*7)%20, 17, "#c1cad0", .07)
        if injured:
            line(c,25,-315,32,-310,RED,1,1.3)
    if costume == "raincoat":
        c.drawPath(curve([(-45,-314),(-56,-348),(-44,-388),(0,-409),(43,-385),(53,-347),(42,-311)],False),
                   paint("#101c27",1,14))
    if pose == "hold" and robe:
        barrel(c,0,-246,.8,t,broken=False)
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
