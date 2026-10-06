"""Offline Mandarin speech, a shared musical clock, timed foley and ducked mixing."""
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import wave

import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import butter, sosfilt

from codecinema import settings
from codecinema.audio import dsp
from story import ROOT, timeline

SR = int(settings.get("audio", "sample_rate", 48000))


def stereo(y, pan=0):
    return np.asarray(dsp.pan_mono(y, pan).T, dtype=np.float32)


def read_voice(path):
    with wave.open(str(path),"rb") as fh:
        if fh.getsampwidth()!=2 or fh.getnchannels()!=1 or fh.getframerate()!=SR:
            raise ValueError(f"Voice cache must be mono PCM16 at {SR} Hz: {path}")
        return np.frombuffer(fh.readframes(fh.getnframes()),np.int16).astype(np.float32)/32768


def voice_for(shot, fallback):
    if not shot.data.get("speaker"):
        return fallback
    if shot.data["speaker"] == "李秀春":
        return fallback
    return "Reed (中文（中国大陆）)"


def prepare_voices(episode, out, mode="auto"):
    out=Path(out); cache=out/"voices"; cache.mkdir(parents=True,exist_ok=True)
    say=shutil.which("say")
    fallback=str(settings.get("audio","voice","Tingting"))
    rate=int(settings.get("audio","speech_rate",185))
    available=set()
    if say and mode!="off":
        listing=subprocess.run([say,"-v","?"],capture_output=True,text=True,check=True).stdout
        for row in listing.splitlines():
            available.add(row.split("#")[0].rsplit(None,1)[0].strip())
    report={"episode":episode["id"],"mode":mode,"engine":"macOS say" if say else None,"cues":[]}
    result={}
    for shot in timeline(episode):
        if not shot.text:
            continue
        provided=ROOT/"assets/voices"/f"{shot.id}.wav"
        voice=voice_for(shot,fallback)
        if voice not in available and fallback in available:
            voice=fallback
        if mode=="off":
            report["cues"].append({"shot":shot.id,"status":"disabled"})
            continue
        if not provided.exists() and (not say or voice not in available):
            message=f"No Mandarin speech engine or recording available for {shot.id}"
            if mode=="required":
                raise RuntimeError(message)
            report["cues"].append({"shot":shot.id,"status":"unavailable","message":message})
            continue
        payload=provided.read_bytes() if provided.exists() else f"{shot.text}|{voice}|{rate}|{SR}".encode()
        key=hashlib.sha256(payload).hexdigest()[:18]
        wav=cache/f"{shot.id}_{key}.wav"
        if not wav.exists():
            raw=cache/f"{shot.id}_{key}.aiff"
            script=cache/f"{shot.id}_{key}.txt"
            try:
                if provided.exists():
                    source=provided
                else:
                    script.write_text(shot.text,encoding="utf-8")
                    subprocess.run([say,"-v",voice,"-r",str(rate),"-f",str(script),"-o",str(raw)],check=True)
                    source=raw
                subprocess.run([settings.tool("ffmpeg"),"-v","error","-y","-i",str(source),"-ar",str(SR),
                                "-ac","1","-c:a","pcm_s16le",str(wav)],check=True)
            finally:
                raw.unlink(missing_ok=True); script.unlink(missing_ok=True)
        y=read_voice(wav)
        # Trim TTS lead/tail silence, then preserve every word without overlapping the next shot.
        indices=np.flatnonzero(np.abs(y)>.003)
        if len(indices):
            y=y[max(0,int(indices[0])-round(SR*.04)):min(len(y),int(indices[-1])+round(SR*.13))]
        duration=len(y)/SR
        slot=shot.duration-1.25
        if duration>slot:
            ratio=duration/slot
            if ratio>1.25:
                raise ValueError(f"{shot.id}: speech needs {duration:.2f}s, only {slot:.2f}s available; shorten the line")
            adjusted=cache/f"{shot.id}_{key}_fit{round(slot*1000)}.wav"
            if not adjusted.exists():
                subprocess.run([settings.tool("ffmpeg"),"-v","error","-y","-i",str(wav),
                                "-af",f"atempo={ratio:.6f}","-ar",str(SR),"-ac","1",str(adjusted)],check=True)
            y=read_voice(adjusted)
            indices=np.flatnonzero(np.abs(y)>.003)
            if len(indices):
                y=y[max(0,int(indices[0])-round(SR*.02)):int(indices[-1])+round(SR*.04)]
            if len(y)/SR>slot+.05:
                raise ValueError(f"{shot.id}: fitted speech still exceeds the available slot")
        peak=float(np.max(np.abs(y))) if len(y) else 0
        if peak<.001:
            raise ValueError(f"Empty narration for {shot.id}")
        y=y*(.44/peak)
        result[shot.id]=y
        report["cues"].append({"shot":shot.id,"status":"recording" if provided.exists() else "synthesized",
                               "voice":voice,"seconds":round(len(y)/SR,3),"start":shot.start+.65})
    (out/f"{episode['id']}_speech.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return result,report


def pluck(freq, seconds, gain=.1):
    n=round(seconds*SR)
    signal=dsp.additive(freq,n,[(1,1,2.8),(2,.32,1.2),(3,.14,.7),(4,.065,.3)])
    return np.asarray(signal*dsp.env_decay(n,2.3)*gain,dtype=np.float32)


def event(kind, duration, seed):
    n=round(duration*SR); t=np.arange(n,dtype=np.float32)/SR
    rng=np.random.default_rng(seed); white=rng.standard_normal(n).astype(np.float32)
    if kind in ("thunder","impact","device_break","fall"):
        y=sosfilt(butter(2,450 if kind=="device_break" else 130,fs=SR,output="sos"),white)
        y=y/ max(float(np.max(np.abs(y))),.01)
        y+=(np.sin(math.tau*(39 if kind=="thunder" else 75)*t)*.3)
        y*=np.exp(-t/(1.2 if kind=="thunder" else .23))
        if kind=="device_break":
            y+=sosfilt(butter(2,2100,"high",fs=SR,output="sos"),white)*np.exp(-t/.13)*.17
        return stereo(y*.22,-.1)
    if kind in ("bell","key","cup","spotlight"):
        freq={"bell":659.25,"key":2100.,"cup":1060.,"spotlight":340.}[kind]
        y=dsp.modal([freq,freq*2.71,freq*4.93],[1,.32,.12],[2.3,1.2,.5],n)
        return stereo(np.asarray(y,dtype=np.float32)*.10,.22)
    if kind in ("door","crack","salt","paper"):
        y=sosfilt(butter(2,[190,3800],"bandpass",fs=SR,output="sos"),white)
        y*=np.exp(-t/.16)
        y+=np.sin(math.tau*122*t)*np.exp(-t/.065)*.4
        return stereo(y*.14,-.2)
    if kind=="steps":
        y=np.zeros(n,np.float32)
        for at in np.arange(0,duration,.36):
            index=round(at*SR); m=min(round(.12*SR),n-index)
            tt=np.arange(m)/SR
            y[index:index+m]+=np.sin(math.tau*90*tt)*np.exp(-tt/.03)*.12
        return stereo(y,.1)
    if kind=="water":
        y=sosfilt(butter(2,[450,3200],"bandpass",fs=SR,output="sos"),white)
        y*=np.sin(math.pi*np.minimum(1,t/duration))*.10
        return stereo(y,.15)
    if kind=="whisper":
        y=sosfilt(butter(2,[700,2400],"bandpass",fs=SR,output="sos"),white)
        y*=(.5+.5*np.sin(t*3.2))*np.sin(np.minimum(1,t/duration)*math.pi)*.047
        return stereo(y,-.4)
    return np.zeros((n,2),np.float32)


def music(episode, shot):
    n=round(shot.duration*SR)
    t=shot.start+np.arange(n,dtype=np.float32)/SR
    base=np.sin(math.tau*55*t)*.027+np.sin(math.tau*82.4069*t)*.017+np.sin(math.tau*110.1*t)*.012
    base*=.68+.21*np.sin(math.tau*.075*t)
    mix=stereo(base,-.16)
    # A recurring D-minor pentatonic phrase; all notes use the episode clock.
    notes=[62,69,65,64,60,62,57,60]
    beat=3.1 if episode["number"]<3 else 2.7
    for index in range(math.floor((shot.start-3.8)/beat),math.ceil(shot.end/beat)):
        at=index*beat
        if at<0:
            continue
        midi=notes[index%len(notes)]
        freq=440*2**((midi-69)/12)
        y=pluck(freq,3.8,.073 if index%4==0 else .052)
        source=max(0,round((shot.start-at)*SR)); destination=max(0,round((at-shot.start)*SR))
        m=min(len(y)-source,n-destination)
        if m>0:
            mix[destination:destination+m]+=stereo(y[source:source+m],-.3 if index%2 else .3)
    if shot.data["scene"] in ("audience","expectation","curtain","device","water_message"):
        mix+=stereo(np.sin(math.tau*58.27*t)*.017+np.sin(math.tau*116.8*t)*.006,.2)
    if shot.data["scene"] in ("soy","rule","coins","chase","recruit","intervene","director"):
        mix+=stereo(np.sin(math.tau*146.832*t)*.009*(.5+.5*np.sin(t*1.9)),.24)
    return mix


def synthesize(episode, out, mode="auto"):
    out=Path(out); out.mkdir(parents=True,exist_ok=True)
    voices,report=prepare_voices(episode,out,mode)
    raw=out/f"{episode['id']}_mix.wav"; final=out/f"{episode['id']}.wav"
    with wave.open(str(raw),"wb") as fh:
        fh.setnchannels(2); fh.setsampwidth(2); fh.setframerate(SR)
        for shot in timeline(episode):
            n=round(shot.duration*SR); tt=np.arange(n,dtype=np.float32)/SR
            y=music(episode,shot)
            rng=np.random.default_rng(1000*episode["number"]+shot.index)
            noise=rng.standard_normal(n).astype(np.float32)
            wet=episode["number"]==1 or (episode["number"]==2 and shot.start<31)
            ambiance=sosfilt(butter(2,3200 if wet else 530,fs=SR,output="sos"),noise)
            ambiance*=.017 if wet else .010
            y+=stereo(ambiance,.08)
            spoken=np.zeros(n,np.float32)
            if shot.id in voices:
                at=round(.65*SR); voice=voices[shot.id]
                if at+len(voice)>n-round(.3*SR):
                    raise ValueError(f"Narration overlaps next shot: {shot.id}")
                spoken[at:at+len(voice)]=voice
                activity=uniform_filter1d(np.abs(spoken),size=round(.12*SR))
                duck=np.clip(activity/.024,0,1)
                y*=1-.65*duck[:,None]
            kind=shot.data.get("sfx")
            if kind:
                at=2.15 if kind=="thunder" else shot.duration*.79 if kind=="device_break" else 1.0
                length=min(3.8,shot.duration-at-.2)
                sfx=event(kind,length,602+shot.index)
                begin=round(at*SR); end=min(n,begin+len(sfx))
                y[begin:end]+=sfx[:end-begin]
            y+=stereo(spoken)
            # Short room reflections on the voice, avoiding convolution of an entire episode.
            for delay,gain in ((.048,.07),(.089,.034)):
                shift=round(delay*SR)
                y[shift:]+=stereo(spoken[:-shift]*gain,.26)
            envelope=np.minimum(1,tt/.06)*np.minimum(1,(shot.duration-tt)/.12)
            if shot.data["scene"]=="title":
                envelope*=np.minimum(1,tt/.9)
            elif shot.data["scene"]=="end":
                envelope*=np.minimum(1,(shot.duration-tt)/1.3)
            y*=envelope[:,None]
            if not np.all(np.isfinite(y)):
                raise ValueError(f"Nonfinite audio: {shot.id}")
            fh.writeframes((np.clip(y,-.94,.94)*32767).astype(np.int16).tobytes())
    norm=subprocess.run([settings.tool("ffmpeg"),"-hide_banner","-y","-i",str(raw),"-af",
                         f"loudnorm=I={settings.get('audio','target_lufs',-16)}:TP=-1:LRA=11:print_format=json",
                         "-ar",str(SR),"-c:a","pcm_s16le",str(final)],capture_output=True,text=True,check=True)
    (out/f"{episode['id']}_loudness.txt").write_text(norm.stderr,encoding="utf-8")
    raw.unlink(missing_ok=True)
    count=sum(cue["status"] in ("recording","synthesized") for cue in report["cues"])
    print(f"{episode['id']} audio: {count}/{len(report['cues'])} spoken cues",flush=True)
    return final
