"""CodeCinema's multi-episode pipeline: plan → acting audio → stills → picture → master → QC."""
from __future__ import annotations

from codecinema.productions import film_root

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
FILM = film_root("xishen")
REPO = FILM.parents[1]
os.environ["CODECINEMA_FILM_DIR"] = str(FILM)
sys.path.insert(0,str(REPO))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402
import skia  # noqa: E402

from codecinema.runtime import media
from codecinema.workspace import settings  # noqa: E402
from art import character, col, gradient, text, text_blob, typeface  # noqa: E402
from scenes import SCENES, draw_frame  # noqa: E402
from sound import synthesize  # noqa: E402
from story import CANON, STORY, digest, timeline, validate, write_plan  # noqa: E402

OUT = Path(settings.path("paths","out_dir"))
MASTER = Path(settings.path("paths","final_video"))
W = int(settings.get("video","width",1920))
H = int(settings.get("video","height",1080))
FPS = int(settings.get("video","fps",24))


def dump(path,value):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def signature(options):
    from codecinema.audio.speech import local_available
    engine=options.speech_engine
    if engine=="auto":
        engine="local" if local_available() else "system"
    return digest(json.dumps({"settings":settings.SETTINGS,"w":W,"h":H,"fps":FPS,"narration":options.narration,
                             "speech_engine": engine},
                             sort_keys=True,ensure_ascii=False))


def validate_all():
    report=validate()
    if W<320 or H<180 or W%2 or H%2 or abs(W/H-16/9)>.01 or not 1<=FPS<=60:
        raise ValueError("Use even 16:9 dimensions and a frame rate from 1 to 60")
    if int(settings.get("audio","sample_rate",48000))<8000:
        raise ValueError("Invalid audio sample rate")
    for episode in STORY["episodes"]:
        for shot in timeline(episode):
            if shot.data["scene"] not in SCENES:
                raise ValueError(f"Missing scene: {shot.id}")
            if abs(shot.duration*FPS-round(shot.duration*FPS))>1e-6:
                raise ValueError(f"Shot is not on a frame boundary: {shot.id}")
            if shot.text and text_blob(shot.text,33)[1]>3030:
                raise ValueError(f"Subtitle exceeds two lines: {shot.id}")
    if not all(skia.Font(typeface("song")).textToGlyphs("我不是戏神陈伶")):
        raise ValueError("The selected font has missing Chinese glyphs")
    return report


def plan(episodes,options):
    report=validate_all()
    write_plan(OUT)
    print(f"Story validated: {report['episodes']} episodes, {report['shots']} shots, {report['duration_s']} s",flush=True)


def frame(episode,shot,t,w=W,h=H):
    surface=skia.Surface(w,h)
    draw_frame(surface.getCanvas(),episode,shot,t,w,h)
    return surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)


def stills(episodes,options):
    image_dir=FILM/"assets/images"; image_dir.mkdir(parents=True,exist_ok=True)
    tiles=[]
    for episode in episodes:
        shots=list(timeline(episode))
        for shot in shots:
            at=shot.duration*.5
            rgba=frame(episode,shot,at,960,540)
            rgb=Image.fromarray(rgba).convert("RGB")
            if shot.data["scene"]=="title":
                poster=Image.fromarray(frame(episode,shot,shot.duration*.52)).convert("RGB")
                poster.save(image_dir/f"{episode['id']}.jpg",quality=94)
            tile=rgb.resize((384,216),Image.Resampling.LANCZOS)
            tile_canvas=Image.new("RGB",(384,246),"#0b131c")
            tile_canvas.paste(tile,(0,0))
            d=ImageDraw.Draw(tile_canvas)
            d.text((12,223),f"{shot.id}  {shot.start:.0f}s",fill="#c8ac80")
            tiles.append(tile_canvas)
    contact=Image.new("RGB",(1920,math.ceil(len(tiles)/5)*246),"#0b131c")
    for index,tile in enumerate(tiles):
        contact.paste(tile,((index%5)*384,(index//5)*246))
    review_dir=OUT/"stills"; review_dir.mkdir(parents=True,exist_ok=True)
    contact.save(review_dir/"storyboard.jpg",quality=90)
    # Cast sheet uses exactly the same model functions as the actual footage.
    cast_surface=skia.Surface(1500,1620); c=cast_surface.getCanvas(); c.clear(col("#101e2b"))
    for index,(key,spec) in enumerate(CANON["characters"].items()):
        x=(index%3)*500; y=(index//3)*540
        c.save(); c.clipRect(skia.Rect.MakeXYWH(x,y,500,540))
        gradient(c,(x,y,500,540),["#263a48","#0f1d2a"])
        character(c,key,x+250,y+475,1.03,1.2,injured=key!="han_meng")
        text(c,spec["name"],x+250,y+518,30,"#d9c4a1",align="center")
        c.restore()
    cast_surface.makeImageSnapshot().save(str(review_dir/"cast.png"),skia.kPNG)
    print(f"Posters: {image_dir}; cast sheet and {len(tiles)} storyboard panels: {review_dir}",flush=True)


def render_shot(episode,shot,key):
    segments=OUT/"segments"/key; segments.mkdir(parents=True,exist_ok=True)
    target=segments/f"{shot.id}.mp4"
    expected=round(shot.duration*FPS)
    if target.exists():
        try:
            info=media.probe(str(target))
            if info.get("frames")==expected and info.get("width")==W and info.get("height")==H and abs(info["fps"]-FPS)<.01:
                return str(target),True
        except (OSError,ValueError,subprocess.SubprocessError):
            pass
    tmp=segments/f"{shot.id}.partial.mp4"
    surface=skia.Surface(W,H)
    encoder=media.encoder(str(tmp),W,H,FPS,crf=int(settings.get("video","crf",18)),
                          preset=str(settings.get("video","preset","fast")),tune="animation")
    try:
        for index in range(expected):
            draw_frame(surface.getCanvas(),episode,shot,index/FPS,W,H)
            pixels=surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)
            encoder.stdin.write(pixels.tobytes())
        encoder.stdin.close()
        if encoder.wait()!=0:
            raise RuntimeError(f"Encoder failed: {shot.id}")
        tmp.replace(target)
    except BaseException:
        if encoder.stdin and not encoder.stdin.closed:
            encoder.stdin.close()
        if encoder.poll() is None:
            encoder.terminate(); encoder.wait()
        tmp.unlink(missing_ok=True)
        raise
    return str(target),False


def render(episodes,options):
    audio(episodes,options)
    key=signature(options); shots=[(e,s) for e in episodes for s in timeline(e)]
    jobs=options.jobs or int(settings.get("render","jobs",3))
    if not 1<=jobs<=16:
        raise ValueError("Use between 1 and 16 render jobs")
    print(f"Rendering {len(shots)} shots at {W}×{H}, {FPS} fps, {jobs} workers",flush=True)
    start=time.monotonic()
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        tasks={pool.submit(render_shot,e,s,key):s.id for e,s in shots}
        for count,task in enumerate(as_completed(tasks),1):
            _,reused=task.result()
            if count%3==0 or count==len(shots):
                print(f"{count}/{len(shots)} · {tasks[task]} · {'cached' if reused else 'encoded'} · "
                      f"{time.monotonic()-start:.0f}s elapsed",flush=True)
    for episode in episodes:
        folder=OUT/episode["id"]; folder.mkdir(parents=True,exist_ok=True)
        paths=[OUT/"segments"/key/f"{s.id}.mp4" for s in timeline(episode)]
        media.concat([str(p) for p in paths],str(folder/"picture.mp4"))
        dump(folder/"picture.json",{"signature":key,"frames":episode["duration_s"]*FPS})
    print("Picture complete",flush=True)


def audio(episodes,options):
    key=signature(options)
    for episode in episodes:
        path=OUT/"audio"/f"{episode['id']}.wav"
        marker=path.with_suffix(".json")
        performance_files = [OUT/"audio/performance"/f"{s.id}.json" for s in timeline(episode)]
        if (path.exists() and marker.exists() and json.loads(marker.read_text())["signature"]==key
                and all(p.is_file() for p in performance_files)):
            print(f"{episode['id']} audio cached",flush=True)
            continue
        synthesize(episode,OUT/"audio",options.narration,options.speech_engine)
        dump(marker,{"signature":key})


def meta_escape(value):
    return str(value).replace("\\","\\\\").replace("=","\\=").replace(";","\\;").replace("#","\\#").replace("\n"," ")


def metadata(path,title,chapters):
    rows=[";FFMETADATA1",f"title={meta_escape(title)}","artist=CodeCinema","comment=Adaptation of chapters 1–6; original screenplay and procedural artwork"]
    for start,end,label in chapters:
        rows.extend(["[CHAPTER]","TIMEBASE=1/1000",f"START={round(start*1000)}",f"END={round(end*1000)}",
                     f"title={meta_escape(label)}"])
    Path(path).write_text("\n".join(rows)+"\n",encoding="utf-8")


def mux(picture,sound,subtitles,meta,target):
    target=Path(target); target.parent.mkdir(parents=True,exist_ok=True)
    temp=target.with_name(target.stem+".partial.mp4")
    subprocess.run([settings.tool("ffmpeg"),"-v","error","-y","-i",str(picture),"-i",str(sound),
                    "-i",str(subtitles),"-i",str(meta),"-map","0:v:0","-map","1:a:0","-map","2:0",
                    "-map_metadata","3","-map_chapters","3","-c:v","copy","-c:a","aac",
                    "-b:a",str(settings.get("video","audio_bitrate","256k")),"-c:s","mov_text",
                    "-metadata:s:s:0","language=zho","-metadata:s:s:0","title=中文",
                    "-disposition:s:0","0","-movie_timescale","1000","-movflags","+faststart",str(temp)],check=True)
    temp.replace(target)


def episode_output(episode):
    return MASTER.parent/f"{episode['id']}.mp4"


def assemble(episodes,options):
    key=signature(options)
    for episode in episodes:
        folder=OUT/episode["id"]; picture=folder/"picture.mp4"; sound=OUT/"audio"/f"{episode['id']}.wav"
        for marker in (folder/"picture.json",OUT/"audio"/f"{episode['id']}.json"):
            if not marker.exists() or json.loads(marker.read_text())["signature"]!=key:
                raise RuntimeError(f"{episode['id']}: stale or missing inputs; run render and audio with the same settings")
        chapters=[]
        for shot in timeline(episode):
            label=shot.data.get("label") or shot.text[:17] or episode["title"]
            chapters.append((shot.start,shot.end,label))
        meta=folder/"chapters.ffmeta"
        metadata(meta,f"我不是戏神 · 第{episode['number']}集 · {episode['title']}",chapters)
        mux(picture,sound,OUT/f"{episode['id']}.srt",meta,episode_output(episode))
        print(f"Episode master: {episode_output(episode)}",flush=True)
    if len(episodes)==len(STORY["episodes"]):
        joined=OUT/"joined.mp4"
        media.concat([str(episode_output(e)) for e in episodes],str(joined))
        cursor=0; chapters=[]
        for e in episodes:
            chapters.append((cursor,cursor+e["duration_s"],f"第{e['number']}集 · {e['title']}"))
            cursor+=e["duration_s"]
        meta=OUT/"complete.ffmeta"; metadata(meta,"我不是戏神 · 开篇三集",chapters)
        MASTER.parent.mkdir(parents=True,exist_ok=True)
        temp=MASTER.with_name(MASTER.stem+".partial.mp4")
        subprocess.run([settings.tool("ffmpeg"),"-v","error","-y","-i",str(joined),"-i",str(OUT/"complete.srt"),
                        "-i",str(meta),"-map","0:v:0","-map","0:a:0","-map","1:0","-map_metadata","2",
                        "-map_chapters","2","-c:v","copy","-c:a","copy","-c:s","mov_text",
                        "-metadata:s:s:0","language=zho","-disposition:s:0","0","-movie_timescale","1000",
                        "-movflags","+faststart",str(temp)],check=True)
        temp.replace(MASTER); joined.unlink(missing_ok=True)
        print(f"Complete trilogy: {MASTER}",flush=True)


def inspect_master(path,seconds,options):
    raw=subprocess.run([settings.tool("ffprobe"),"-v","error","-show_streams","-show_format","-show_chapters",
                        "-of","json",str(path)],capture_output=True,text=True,check=True)
    info=json.loads(raw.stdout)
    video=next(s for s in info["streams"] if s["codec_type"]=="video")
    sound=next(s for s in info["streams"] if s["codec_type"]=="audio")
    if (video["width"],video["height"])!=(W,H) or int(video["nb_frames"])!=seconds*FPS:
        raise ValueError(f"Wrong picture dimensions or frame count: {path}")
    if abs(float(info["format"]["duration"])-seconds)>.1:
        raise ValueError(f"Wrong master duration: {path}")
    if int(sound["sample_rate"])!=int(settings.get("audio","sample_rate",48000)) or sound["channels"]!=2:
        raise ValueError(f"Wrong audio format: {path}")
    if abs(float(sound["duration"])-seconds)>.08:
        raise ValueError(f"Audio/video duration mismatch: {path}")
    if not any(s["codec_type"]=="subtitle" for s in info["streams"]) or not info["chapters"]:
        raise ValueError(f"Missing subtitle track or chapters: {path}")
    cursor=0.0
    for chapter in info["chapters"]:
        start=float(chapter["start_time"]); end=float(chapter["end_time"])
        if abs(start-cursor)>.05 or end<=start or end>seconds+.05:
            raise ValueError(f"Invalid chapter timestamps: {path}")
        cursor=end
    if abs(cursor-seconds)>.05:
        raise ValueError(f"Chapters do not span the complete film: {path}")
    if not options.skip_decode:
        subprocess.run([settings.tool("ffmpeg"),"-v","error","-xerror","-i",str(path),"-map","0:v:0",
                        "-map","0:a:0","-f","null","-"],check=True,capture_output=True)
    measurement=subprocess.run([settings.tool("ffmpeg"),"-hide_banner","-nostats","-i",str(path),"-map","0:a:0",
                                "-af","ebur128=peak=true","-f","null","-"],capture_output=True,text=True,check=True)
    summary=measurement.stderr.rsplit("Summary:",1)[-1]
    lufs=float(re.search(r"I:\s+(-?[\d.]+) LUFS",summary).group(1))
    peak=float(re.search(r"Peak:\s+(-?[\d.]+) dBFS",summary).group(1))
    target=float(settings.get("audio","target_lufs",-16))
    if abs(lufs-target)>2 or peak>-.2:
        raise ValueError(f"Loudness outside limits: {path}: {lufs} LUFS, {peak} dBTP")
    return {"path":str(path),"duration_s":float(info["format"]["duration"]),"frames":int(video["nb_frames"]),
            "width":W,"height":H,"fps":FPS,"audio_rate":int(sound["sample_rate"]),"channels":2,
            "chapters":len(info["chapters"]),"lufs":lufs,"true_peak_db":peak,"decode_checked":not options.skip_decode}


def qc(episodes,options):
    from codecinema.audio.performance import Performance
    report={"story":validate_all(),"signature":signature(options),
            "shots":[],"masters":[]}
    for episode in episodes:
        for shot in timeline(episode):
            a=frame(episode,shot,shot.duration*.45,480,270)
            b=frame(episode,shot,shot.duration*.45,480,270)
            if not np.array_equal(a,b):
                raise ValueError(f"Nondeterministic frame: {shot.id}")
            content=a[33:237,:,:3]
            if int(np.max(content))-int(np.min(content))<35:
                raise ValueError(f"Blank shot: {shot.id}")
            moving=frame(episode,shot,shot.duration*.68,480,270)
            delta=float(np.mean(np.abs(a.astype(np.float32)-moving.astype(np.float32))))
            if shot.data["scene"] not in ("end",) and delta<.01:
                raise ValueError(f"Static shot: {shot.id}")
            report["shots"].append({"id":shot.id,"deterministic":True,"motion_delta":round(delta,3)})
        speech_file=OUT/"audio"/f"{episode['id']}_speech.json"
        if not speech_file.exists():
            raise ValueError(f"Missing speech report: {episode['id']}")
        speech=json.loads(speech_file.read_text())
        if options.narration=="required" and any(c["status"] not in ("synthesized","recording") for c in speech["cues"]):
            raise ValueError(f"Missing required narration: {episode['id']}")
        for shot in timeline(episode):
            performance=Performance.load(OUT/"audio/performance"/f"{shot.id}.json")
            data=performance.data
            if data.get("speaker"):
                if speech["engine"]=="local" and data.get("method")!="forced-aligned":
                    raise ValueError(f"Missing dialogue alignment: {shot.id}")
                if data["duration"]+.65>shot.duration-.25:
                    raise ValueError(f"Dialogue escapes its shot: {shot.id}")
                for at in (-.1,.1,shot.duration):
                    if performance.mouth(at,data["speaker"]).opening:
                        raise ValueError(f"Mouth moves outside dialogue: {shot.id}")
                if performance.mouth(1,"not_the_speaker").opening:
                    raise ValueError(f"The wrong character is speaking: {shot.id}")
        report.setdefault("speech",[]).append({"episode":episode["id"],"engine":speech["engine"],
                                                "cues":len(speech["cues"]),"timing_checked":True})
        print(f"Checking decoded master and sound: {episode['id']}",flush=True)
        report["masters"].append(inspect_master(episode_output(episode),episode["duration_s"],options))
    if len(episodes)==len(STORY["episodes"]):
        report["masters"].append(inspect_master(MASTER,sum(e["duration_s"] for e in episodes),options))
    dump(OUT/"qc.json",report)
    print(f"QC passed: {len(report['shots'])} deterministic shots, {len(report['masters'])} playable masters",flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step",choices=("plan","stills","render","audio","assemble","qc","all"),nargs="?",default="all")
    parser.add_argument("--episode",choices=("all","ep01","ep02","ep03"),default="all")
    parser.add_argument("--jobs",type=int,default=0)
    parser.add_argument("--narration",choices=("auto","off","required"),default=str(settings.get("audio","narration","auto")))
    parser.add_argument("--speech-engine",choices=("auto","local","system","recording"),default="auto",
                        help="local: emotional voices and forced alignment on Apple Silicon; recording: supplied WAVs")
    parser.add_argument("--skip-decode",action="store_true",help="Skip full master decoding when repeating an inspection")
    options=parser.parse_args()
    episodes=[e for e in STORY["episodes"] if options.episode in ("all",e["id"])]
    validate_all(); OUT.mkdir(parents=True,exist_ok=True)
    if options.step!="plan":
        write_plan(OUT)
    functions={"plan":plan,"stills":stills,"render":render,"audio":audio,"assemble":assemble,"qc":qc}
    sequence=("plan","audio","stills","render","assemble","qc") if options.step=="all" else (options.step,)
    for step in sequence:
        functions[step](episodes,options)
    return 0


if __name__=="__main__":
    sys.exit(main())
