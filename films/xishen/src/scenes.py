"""Shot-specific staging, performance, camera movement and on-screen captions."""
import math
from functools import lru_cache

import skia

from codecinema import settings
from codecinema.audio.performance import activate, Performance
from pathlib import Path

from art import (TOP, BOTTOM, BLUE, GOLD, INK, IVORY, RED, aurora, background, barrel, character, col,
                 cup, curve, ellipse, glow, grade, lamp, line, paint, path, rain, rect, shape, smooth,
                 snow, spotlight, text, tricycle)


SCENES = {
    "title", "end", "rain_wide", "rain_face", "rain_fall", "memory", "memory_fall", "door",
    "door_open", "parents", "parents_close", "footprints", "water", "water_break", "water_echo",
    "lamp", "bedroom", "parents_leave", "stage", "stage_walk", "expectation", "audience",
    "stage_run", "curtain", "bedroom_wake", "water_debris", "water_message", "coat", "aurora",
    "grave", "grave_inquiry", "han", "device", "salt", "salt_throw", "salt_message", "clinic",
    "clinic_close", "tea", "gray", "paper", "domains", "letter", "thinking", "thinking_close",
    "breakfast", "breakfast_close", "soy", "rule", "coins", "chase", "recruit", "intervene", "director"
}


def bg_for(scene):
    if scene.startswith("rain") or scene in ("door", "parents_leave"):
        return "street"
    if scene.startswith("memory"):
        return "memory"
    if scene.startswith("bedroom"):
        return "bedroom"
    if scene.startswith("grave") or scene in ("han", "device"):
        return "grave"
    if scene in ("stage", "stage_walk", "stage_run", "expectation", "curtain", "title", "end"):
        return "stage"
    if scene == "audience":
        return "audience"
    if scene.startswith("clinic") or scene in ("tea", "paper", "letter"):
        return "clinic"
    if scene in ("gray", "domains"):
        return "abstract"
    if scene.startswith("breakfast") or scene in ("soy", "coins", "chase", "recruit", "intervene"):
        return "shop"
    if scene in ("aurora", "thinking", "thinking_close", "salt", "salt_throw", "salt_message", "rule", "director"):
        return "day"
    return "home"


def title(c, episode, shot, t, end=False):
    c.drawImage(background("stage"),0,0)
    glow(c,1460,590,560,RED,.14)
    # Quiet visual bookends; title, episode and credits live in player metadata.
    x=1200+math.sin(t*.17)*35 if not end else 960
    if not end:
        character(c,"chen_ling",x,941,1.7,t,shot.costume,
                  emotion="thinking" if episode["number"]==3 else "lost", injured=episode["number"]!=1)
    spotlight(c,x,935,t)


def monitor(c, value, u, warning=False):
    rect(c,762,393,814,343,"#060e17",radius=7)
    c.drawRoundRect(skia.Rect.MakeXYWH(762,393,814,343),7,7,paint("#61707b",.5,2))
    text(c,"观众期待值",811,465,35,RED)
    text(c,f"{value}%",1169,645,145,"#d44651",align="center",role="ui")
    line(c,814,686,1520,686,RED,.28,1)
    if warning:
        text(c,"低于 20% · 安全不再受保障",1169,790,34,IVORY,.9,align="center")


def device(c, t, u):
    x,y,r=1205,587,203
    ellipse(c,x,y,r+15,r+15,"#131f29")
    ellipse(c,x,y,r,r,"#a3a795")
    ellipse(c,x,y,r-13,r-13,"#273d46")
    ellipse(c,x,y,r-26,r-26,"#142532")
    for j in range(48):
        ang=j*math.tau/48
        inner=r-35 if j%4==0 else r-27
        cc=["#82947d",GOLD,RED][min(2,j//16)]
        line(c,x+inner*math.sin(ang),y-inner*math.cos(ang),x+(r-20)*math.sin(ang),y-(r-20)*math.cos(ang),cc,.85,2)
    shake=smooth((u-.4)/.35)
    angle=-.35+math.sin(t*19)*shake*3.8
    if u < .79:
        shape(c,[(x-5*math.cos(angle),y-5*math.sin(angle)),
                 (x+158*math.sin(angle),y-158*math.cos(angle)),
                 (x+5*math.cos(angle),y+5*math.sin(angle))],"#c5bdaa",None,rounded=False)
        ellipse(c,x,y,13,13,"#748c88")
    else:
        for j in range(16):
            ang=j*2.398; dist=70+smooth((u-.79)/.21)*(80+j*17)
            xx=x+math.cos(ang)*dist; yy=y+math.sin(ang)*dist
            shape(c,[(xx,yy),(xx+18,yy+9),(xx+8,yy+29),(xx-10,yy+16)],"#82948f",None,rounded=False)
        line(c,x-170,y-85,x+165,y+117,"#050b12",1,12)
        line(c,x-58,y+167,x+48,y-185,"#050b12",1,7)


def food(c,x,y,t):
    ellipse(c,x,y,126,30,"#a0a994")
    ellipse(c,x,y-5,117,24,"#c3c4a7")
    for j in range(3):
        c.save(); c.translate(x-56+j*52,y-5); c.rotate(-17+j*13)
        shape(c,[(-17,-65),(-16,47),(-8,60),(7,53),(12,-54),(7,-71)],"#c59450","#775539",1.4)
        line(c,-3,-55,-2,46,"#ead097",.7,3)
        for k in range(7):
            ellipse(c,-7,-45+k*14,2,3,"#9b713d",.6)
        c.restore()
    cup(c,x-153,y-3,.9,"#ded5ad")
    for j in range(9):
        glow(c,x-150+math.sin(t*.4+j)*19,y-82-j*13-(t*9)%16,42,"#dce2d6",.06)


def layout(c, episode, shot, t):
    scene=shot.data["scene"]; u=t/shot.duration
    costume=shot.costume
    emotion=shot.data.get("emotion","neutral")
    talking=.65<t<shot.duration-1 and shot.data.get("speaker")=="陈伶"
    def hero(x=985,y=921,s=1.7,**kwargs):
        injured=not (episode["number"]==1 and (shot.index<3 or (scene=="rain_fall" and u<.45)))
        character(c,"chen_ling",x,y,s,t,costume=costume,emotion=emotion,speaking=talking,injured=injured,**kwargs)
    c.drawImage(background(bg_for(scene)),0,0)

    if scene.startswith("rain"):
        if scene=="rain_wide":
            hero(1080+smooth(u)*95,915,1.55,pose="walk",rotation=math.sin(t*1.3)*2)
            glow(c,1120,815,420,RED,.05,rx=1.5)
        elif scene=="rain_face":
            hero(1180,2090,4.65)
            glow(c,730,445,520,BLUE,.13)
        else:
            hero(1110,892,1.55,rotation=-83*smooth((u-.08)/.38),pose="walk")
        rain(c,t,1.45)
        if shot.data.get("sfx")=="thunder":
            a=math.exp(-((t-2.15)/.42)**2)*.14
            rect(c,0,TOP,1920,BOTTOM-TOP,"#b8ccdc",a)
    elif scene in ("memory","memory_fall"):
        spotlight(c,1020,919,t)
        character(c,"chen_ling",1070,924,1.6,t,costume="memory_shirt",pose="point",injured=False)
        for j in range(4):
            line(c,670+j*200,840,722+j*200,874,"#c5b58e",.55,3)
            line(c,701+j*200,835,682+j*200,879,"#c5b58e",.55,3)
        if scene=="memory_fall":
            yy=214+smooth((u-.25)/.45)*500
            c.save(); c.translate(1110,yy); c.rotate(u*165)
            rect(c,-47,-25,94,50,"#5a6972",radius=6)
            ellipse(c,42,0,13,22,"#cfc1a4")
            c.restore()
            rect(c,0,TOP,1920,BOTTOM-TOP,INK,smooth((u-.7)/.18)*.94)
    elif scene=="door":
        rect(c,486,168,682,789,"#25323b")
        rect(c,562,217,472,725,"#17232b")
        for xx in range(575,1030,58):
            line(c,xx,222,xx,938,"#39454a",.5,2)
        rect(c,1110,602,113,108,"#474e49",radius=3)
        rect(c,1122,619,90,10,INK)
        text(c,"报刊",1166,672,26,GOLD,align="center")
        hero(1330,930,1.72,pose="offer",facing=-1)
        line(c,1114,716,1153,716,GOLD,1,5)
        ellipse(c,1159,716,9,9,GOLD,1,3)
        rain(c,t)
    elif scene=="door_open":
        shape(c,[(450,188),(760,259),(760,947),(450,947)],"#b5986e",None,rounded=False)
        glow(c,730,687,440,GOLD,.25)
        hero(694+u*140,922,1.75,pose="walk")
        rect(c,350,152,39,813,"#111e2a")
        rect(c,447,202,26,744,"#4d4b42")
    elif scene in ("parents","parents_close"):
        close=scene=="parents_close"
        if close:
            character(c,"chen_tan",554,1690,3.6,t,emotion="afraid",speaking=shot.data.get("speaker")=="陈坛")
            character(c,"li_xiuchun",1320,1662,3.5,t,emotion="afraid",speaking=shot.data.get("speaker")=="李秀春")
            lamp(c,940,916,.95,t)
        else:
            character(c,"chen_tan",928,965,1.63,t,emotion="afraid",speaking=shot.data.get("speaker")=="陈坛")
            character(c,"li_xiuchun",1440,965,1.52,t,emotion="afraid")
            rect(c,719,738,840,67,"#625a48")
            lamp(c,1145,742,.86,t)
            ellipse(c,815,742,46,9,"#918975",.65)
    elif scene=="footprints":
        for j in range(7):
            a=smooth((u-j*.08)/.17)
            x=433+j*96; y=850-j*19
            ellipse(c,x+(j%2)*36,y,16,30,"#111d23",a*.8)
            ellipse(c,x+(j%2)*36-3,y-29,20,14,"#111d23",a*.8)
            for k in range(4):
                ellipse(c,x-14+k*9+(j%2)*36,y-42,3,4,"#111d23",a*.8)
        lamp(c,1423,741,.83,t)
    elif scene in ("water","water_break","water_echo"):
        hero(1080,958,1.83,pose="hold",rotation=-3)
        if scene!="water":
            barrel(c,1080,501,1.7,t,True)
            for j in range(8):
                yy=635+(j*67+t*112)%219
                ellipse(c,1090+math.sin(j)*46,yy,3,7,"#a8c0bd",.68)
        if scene=="water_echo":
            c.saveLayer(skia.Rect.MakeWH(1920,1080),paint(IVORY,.13))
            hero(1380,940,1.66,pose="offer")
            c.restore()
        ellipse(c,1050,909,260,21,"#739795",.2)
    elif scene=="lamp":
        lamp(c,955,841,3.5,t)
        character(c,"chen_tan",1510,921,1.3,t,emotion="afraid")
    elif scene in ("bedroom","bedroom_wake"):
        if scene=="bedroom":
            hero(1300,664,1.6,rotation=-89)
            shape(c,[(845,677),(1480,690),(1554,731),(827,731)],"#344953",None)
        else:
            hero(1130,1078,1.66,pose="hold",rotation=-4*(1-smooth(u)))
            shape(c,[(812,726),(1480,732),(1541,778),(781,778)],"#344953",None)
        glow(c,336,420,408,BLUE,.14)
    elif scene=="parents_leave":
        character(c,"chen_tan",852+u*180,899,1.4,t,costume="raincoat",pose="walk",emotion="afraid")
        character(c,"li_xiuchun",1130+u*140,887,1.31,t,costume="raincoat",pose="walk",emotion="afraid")
        rain(c,t,1.5)
    elif scene in ("stage","stage_walk","stage_run"):
        x=960
        if scene=="stage_walk":
            x=846+u*225
        elif scene=="stage_run":
            x=960+math.sin(u*math.tau)*530
        spotlight(c,x,922,t)
        hero(x,924,1.75,pose="run" if scene=="stage_run" else "walk" if scene=="stage_walk" else "stand")
        if scene=="stage_run":
            rect(c,47,200,109,763,"#3a4044")
            rect(c,1765,200,109,763,"#3a4044")
    elif scene=="expectation":
        spotlight(c,460,904,t)
        hero(430,922,1.35)
        monitor(c,shot.data["expectation"],u,shot.data.get("motif") is not None)
    elif scene=="audience":
        for row in range(7):
            y=260+row*85; s=.52+row*.125; count=18-row; spacing=1920/(count+1)
            for j in range(count):
                x=(j+1)*spacing+(row%2)*spacing*.17
                a=smooth((u-row*.042-j*.008)/.28)
                for side in (-1,1):
                    ellipse(c,x+side*8*s,y-20*s,3.4*s,1.6*s,"#c94550",a*.9)
                    glow(c,x+side*8*s,y-20*s,10*s,RED,a*.14)
        rect(c,0,TOP,1920,BOTTOM-TOP,INK,.1)
    elif scene=="curtain":
        gap=smooth((u-.15)/.8)*280
        rect(c,960-gap,148,gap*2,518,"#00030a")
        for side in (-1,1):
            for j in range(14):
                xx=960+side*(gap+8+j*48)
                line(c,xx,150,xx+side*23,652,"#485568",.15,17)
        spotlight(c,960,908,t)
        hero(960,923,1.7)
    elif scene in ("water_debris","water_message"):
        hero(1322,1075,1.45,rotation=-16,pose="hold")
        barrel(c,489,814,2.05,t,True)
        for j in range(6):
            xx=637+j*73
            shape(c,[(xx,820),(xx+19,816),(xx+35,831),(xx+7,837)],"#8ba6aa",None)
        ellipse(c,970,833,337,68,"#8fa9a8",.19)
        if scene=="water_message":
            a=smooth((u-.13)/.45)
            text(c,"我们在看着你",970,837,67,RED,a,align="center",role="kaiti")
            for j in range(11):
                ellipse(c,720+j*47,856+math.sin(j)*7,3,9,RED,a*.6)
    elif scene=="coat":
        hero(1060,930,1.93,pose="hold")
    elif scene=="aurora":
        aurora(c,t)
        hero(1070,939,1.54,rotation=-4)
        glow(c,900,500,540,BLUE,.08)
        snow(c,t)
    elif scene in ("grave","grave_inquiry"):
        if scene=="grave":
            for j in range(8):
                character(c,"jiang_qin",460+j*153,809+(j%2)*25,.67,t+j,costume="uniform",injured=False)
            character(c,"chen_tan",480,956,1.59,t,costume="raincoat",emotion="afraid")
            character(c,"li_xiuchun",781,952,1.48,t,costume="raincoat",emotion="afraid")
        else:
            character(c,"chen_tan",579,940,1.7,t,costume="raincoat",emotion="afraid")
            character(c,"li_xiuchun",928,930,1.51,t,costume="raincoat",emotion="afraid")
            character(c,"jiang_qin",1410,936,1.74,t,costume="uniform",pose="offer",injured=False)
            rect(c,1268,638,130,77,"#c1ba9e")
        snow(c,t)
    elif scene=="han":
        character(c,"han_meng",1140,1685,3.42,t,costume="officer_coat",emotion="thinking",injured=False,
                  speaking=shot.data.get("speaker")=="韩蒙")
        line(c,349,537,647,537,GOLD,.4,1)
        snow(c,t)
    elif scene=="device":
        character(c,"han_meng",522,1010,1.92,t,costume="officer_coat",pose="hold",injured=u>.79,emotion="afraid" if u>.79 else "neutral")
        device(c,t,u)
        snow(c,t)
    elif scene in ("salt","salt_throw","salt_message"):
        aurora(c,t)
        if scene!="salt_message":
            x=1060+u*160
            tricycle(c,x,879,t,.95)
            character(c,"xiao_liu",x-114,829,1.0,t,costume="green_jacket",pose="hold",rotation=-10)
            character(c,"zhao_yi",x+180,825,.94,t,costume="work_jacket",pose="point")
            for dx in (20,225):
                rect(c,x+dx,730,70,93,"#8c9587",radius=9)
                ellipse(c,x+dx+35,731,35,9,"#d2d2b8")
            hero(486,935,1.58)
            if scene=="salt_throw":
                for j in range(35):
                    ph=(u*1.7+j*.013)%1
                    xx=x+145-(x-330)*ph; yy=588-160*math.sin(ph*math.pi)+ph*130
                    ellipse(c,xx+j%5*9,yy+j%7*7,2,2,"#e1dfc9",.9)
        else:
            hero(1385,1168,1.66,rotation=-13)
            ellipse(c,858,822,450,65,"#819da5",.15)
            text(c,"观众期待值",831,779,35,IVORY,.8,align="center")
            text(c,"27%",831,866,88,IVORY,smooth(u/.35)*(1-smooth((u-.8)/.2)),align="center",role="ui")
        snow(c,t)
    elif scene in ("clinic","clinic_close"):
        close=scene=="clinic_close"
        if close and shot.data.get("speaker")=="陈伶":
            hero(720,1670,3.42)
            character(c,"doctor_lin",1550,1510,2.8,t,costume="white_coat",facing=-1)
        elif close:
            hero(464,1340,2.3)
            character(c,"doctor_lin",1230,1690,3.48,t,costume="white_coat",speaking=True)
        else:
            hero(601,1010,1.71,pose="hold")
            character(c,"doctor_lin",1327,982,1.79,t,costume="white_coat",pose="hold")
            rect(c,723,736,822,53,"#8b7f66")
            cup(c,1260,716,.7,"#6b5938")
        glow(c,700,561,460,BLUE,.07)
    elif scene=="tea":
        character(c,"doctor_lin",606,1500,3.0,t,costume="white_coat",emotion="afraid",pose="hold")
        cup(c,1280,659,4.0,"#682531" if u>.26 else "#65533a")
        if u>.3:
            ellipse(c,1300,861,191,17,RED,.5)
    elif scene in ("gray","domains"):
        # These images are explicitly an illustration of the doctor's explanation.
        if scene=="gray":
            for j in range(6):
                xx=230+j*256
                p=shape(c,[(xx,290),(xx+110,230),(xx+218,337),(xx+130,816),(xx-41,641)],
                        "#61717a",None,a=.4,rounded=False)
                c.save(); c.clipPath(p,doAntiAlias=True)
                for k in range(5):
                    rect(c,xx-37+k*53,473+k%3*31,37,337,"#132732",.65)
                c.restore()
                c.drawPath(p,paint("#c3c8bd",.45,1.3))
            line(c,349,292,1320,175,RED,.7,3)
            glow(c,1322,175,122,RED,.2)
        else:
            for j in range(9):
                angle=j*math.tau/9-.5
                x=960+math.cos(angle)*610; y=544+math.sin(angle)*266
                ellipse(c,x,y,36,13,"#36515b",1,2)
                glow(c,x,y-12,110,GOLD,.22)
                shape(c,[(x-8,y),(x-11,y-14),(x+math.sin(t+j)*4,y-40),(x+9,y-11),(x+8,y)],GOLD,None)
                line(c,x,y,960,544,"#80959a",.13,1)
    elif scene=="paper":
        cup(c,951,671,3.8,"#748f90")
        shape(c,[(676,463),(1196,452),(1220,563),(700,572)],"#d9d1b7",None,rounded=False)
        for j in range(11):
            x=728+j*42; y=530+math.sin(j*2+t)*10
            ellipse(c,x,y,21+u*12,12+u*10,"#738b8b",smooth((u-j*.025)/.7)*.5)
    elif scene=="letter":
        character(c,"doctor_lin",1460,977,1.8,t,costume="white_coat",pose="offer",speaking=True)
        rect(c,391,465,699,334,"#cbc2a6",radius=3)
        shape(c,[(392,465),(741,663),(1090,465)],"#b4ac93",None,rounded=False)
        line(c,392,798,641,653,"#8d8b79",.6,2)
        line(c,1090,798,841,653,"#8d8b79",.6,2)
        text(c,"极光城",740,727,64,"#3b4b4c",align="center")
        text(c,"转介信",740,773,29,"#5c6255",align="center")
    elif scene in ("thinking","thinking_close"):
        aurora(c,t)
        if scene=="thinking":
            hero(1370,941,1.85,pose="walk")
        else:
            hero(1208,1760,3.7)
            line(c,374,580,716,580,GOLD,.5,1)
    elif scene in ("breakfast","breakfast_close"):
        if scene=="breakfast_close":
            hero(615,1470,2.87,pose="hold")
            character(c,"uncle_zhao",1400,1492,2.95,t,costume="apron",emotion="afraid" if u>.6 else "neutral")
            rect(c,740,803,926,102,"#78694f")
            food(c,979,803,t)
        else:
            hero(678,1013,1.72,pose="hold")
            character(c,"uncle_zhao",1410,941,1.65,t,costume="apron",pose="offer")
            rect(c,814,763,700,83,"#807157")
            food(c,1070,762,t)
        snow(c,t)
    elif scene=="soy":
        rect(c,340,487,1239,467,"#695c48")
        ellipse(c,960,751,440,143,"#7a8477")
        ellipse(c,960,722,440,141,"#c4c1a3")
        ellipse(c,960,717,400,114,"#dcd3ae")
        for j in range(6):
            ellipse(c,960,717,80+j*53+(t*5)%30,24+j*15,"#9b9e89",.13,1)
        text(c,"观众期待值 +3",960,674,37,RED,smooth(u/.35),align="center")
        text(c,"32%",960,771,96,RED,smooth(u/.4),align="center",role="ui")
        for j in range(8):
            glow(c,665+j*82,554-math.sin(t*.3+j)*25,73,IVORY,.045)
    elif scene=="rule":
        aurora(c,t)
        rect(c,0,TOP,1920,BOTTOM-TOP,INK,.6)
        hero(1525,961,1.89)
        line(c,191,493,1067,493,GOLD,.35,1)
    elif scene=="coins":
        tricycle(c,822,874,t,1)
        character(c,"xiao_liu",596,894,1.21,t,costume="green_jacket",emotion="tired",pose="hold")
        character(c,"zhao_yi",1031,922,1.54,t,costume="work_jacket",pose="offer")
        for j in range(18):
            x=1360+(j%6)*54; y=519+(j//6)*64
            ellipse(c,x,y,20,20,"#b39160")
            ellipse(c,x,y,15,15,"#6d674e",1,1)
            rect(c,x-4,y-4,8,8,"#39463f")
    elif scene=="chase":
        movement=math.sin(u*math.pi)*260
        character(c,"zhao_yi",990+movement,925,1.5,t,costume="work_jacket",pose="run",emotion="afraid",rotation=8)
        character(c,"uncle_zhao",669+movement,935,1.7,t,costume="apron",pose="run",emotion="afraid",rotation=6)
        line(c,646+movement,684,774+movement,477,"#857661",1,14)
        for j in range(6):
            character(c,"jiang_qin",120+j*325,924,.9,t+j,silhouette=True)
    elif scene=="recruit":
        hero(730,1226,2.3,pose="point")
        character(c,"xiao_liu",1300,1240,2.35,t,costume="green_jacket",emotion="thinking")
        tricycle(c,1510,908,0,.67)
    elif scene=="intervene":
        character(c,"uncle_zhao",507,942,1.69,t,costume="apron",pose="point",emotion="afraid")
        line(c,653,574,819,770,"#857661",1,13)
        character(c,"zhao_yi",1030,937,1.72,t,costume="work_jacket",emotion="afraid")
        character(c,"xiao_liu",1240-smooth(u)*71,955,1.78,t,costume="green_jacket",pose="hold",rotation=-16)
        for j in range(4):
            character(c,"jiang_qin",1540+j*86,943,.8,t+j,silhouette=True)
    elif scene=="director":
        aurora(c,t)
        hero(1250,1738,3.7)
        line(c,208,552,707,552,GOLD,.35,1)
    else:
        raise ValueError(f"Unimplemented scene: {scene}")


def captions(c, shot, t):
    if not shot.text or t < .65 or t >= shot.duration-.5:
        return
    # Native CJK text, with wrapping based on measured glyph width.
    from art import text_blob
    lines=[]; current=""
    for char in shot.text:
        if text_blob(current+char,33)[1] > 1515:
            lines.append(current); current=char
        else:
            current+=char
    if current:
        lines.append(current)
    if len(lines)>2:
        raise ValueError(f"Subtitle exceeds two lines: {shot.id}")
    speaker=shot.data.get("speaker")
    if speaker:
        text(c,speaker,960,981 if len(lines)==2 else 998,23,GOLD,align="center")
    y=1018 if len(lines)==2 else 1040
    for i,s in enumerate(lines):
        text(c,s,960,y+i*42,33,IVORY,align="center")


def draw_frame(c, episode, shot, t, width=1920, height=1080):
    c.clear(col("#050a10"))
    c.save(); c.scale(width/1920,height/1080)
    c.save(); c.clipRect(skia.Rect.MakeLTRB(0,TOP,1920,BOTTOM))
    scene=shot.data["scene"]
    with activate(performance(shot.id), t):
        if scene in ("title","end"):
            title(c,episode,shot,t,scene=="end")
        else:
            # Subtle shot-specific pans and dolly movement preserve the cast sheets.
            u=t/shot.duration
            z=1.01+.035*smooth(u)
            direction=-1 if shot.index%2 else 1
            c.translate(960+direction*(u-.5)*17,552)
            c.scale(z,z); c.translate(-960,-552)
            layout(c,episode,shot,t)
    grade(c)
    c.restore()
    if scene not in ("title","end"):
        captions(c,shot,t)
    fade=0
    if scene=="title":
        fade=1-smooth(t/1.0)
    elif scene=="end":
        fade=smooth((t-shot.duration+1.3)/1.3)
    if fade:
        rect(c,0,0,1920,1080,"#050a10",fade)
    c.restore()


@lru_cache(maxsize=128)
def performance(shot_id):
    return Performance.load(Path(settings.path("paths","out_dir"))/"audio/performance"/f"{shot_id}.json")
