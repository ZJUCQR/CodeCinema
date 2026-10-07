"""Offline Mandarin speech, a shared musical clock, timed foley and ducked mixing."""

import json
import math
from pathlib import Path
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


def direction_for(shot, profile):
    scene = shot.data["scene"]
    emotion = shot.data.get("emotion", "neutral")
    directions = {
        "afraid": "害怕但努力克制，语尾稍发紧，在标点处自然换气。",
        "lost": "困惑、记忆混乱，关键词稍停顿，像努力辨认自己的处境。",
        "tired": "疲惫、气息较轻，语句仍清楚，不夸张呻吟。",
        "thinking": "边观察边推理，后半句逐渐坚定，克制地流露好奇。",
        "neutral": "自然、有变化的日常说话语气，不机械匀速。",
    }
    if not shot.data.get("speaker"):
        tone = ("紧张而有悬念，句尾稍收，关键变化前短暂停顿。" if scene in
                ("rain_fall", "memory_fall", "water_echo", "audience", "curtain", "water_message", "device", "tea")
                else "清晰自然地讲故事，随情节变化重音，画面留有呼吸感。")
        return "女性故事讲述者，标准普通话。" + tone + "约每秒五个汉字，完整读出文本，不增添话语。"
    return profile.get("direction", "标准普通话。") + directions[emotion] + "自然中等语速，完整读出文本，不增添话语。"


def prepare_voices(episode, out, mode="auto", engine="auto"):
    from codecinema.audio.speech import SpeechEngine, ForcedAligner, read_wave, write_wave
    from codecinema.audio.performance import describe
    from scipy.signal import resample_poly
    from story import CANON

    out = Path(out)
    cache = out / "voices"
    performance_dir = out / "performance"
    performance_dir.mkdir(parents=True, exist_ok=True)
    speech = SpeechEngine(cache, engine=engine) if mode != "off" else None
    report = {"episode": episode["id"], "mode": mode, "engine": speech.engine if speech else None, "cues": []}
    result, pending = {}, []
    names = {spec["name"]: key for key, spec in CANON["characters"].items()}
    try:
        for shot in timeline(episode):
            performance_path = performance_dir / f"{shot.id}.json"
            if not shot.text or mode == "off":
                performance_path.write_text("{}\n")
                if shot.text:
                    report["cues"].append({"shot": shot.id, "status": "disabled"})
                continue
            who = names.get(shot.data.get("speaker"))
            profile = CANON["characters"][who].get("speech", {}) if who else {"voice": "Serena"}
            voice = profile.get("voice", "Dylan")
            provided = ROOT / "assets/voices" / f"{shot.id}.wav"
            try:
                take_direction = direction_for(shot, profile)
                source, key = speech.take(shot.text, voice=voice, direction=take_direction,
                                         recording=provided, seed=43+shot.index,
                                         system_voice="Tingting" if who in (None, "li_xiuchun") else "Reed (中文（中国大陆）)",
                                         rate=int(settings.get("audio", "speech_rate", 185)))
            except RuntimeError as exc:
                if mode == "required" or speech.engine == "local":
                    raise RuntimeError(f"{shot.id}: {exc}") from exc
                report["cues"].append({"shot": shot.id, "status": "unavailable", "message": str(exc)})
                performance_path.write_text("{}\n")
                continue
            slot = shot.duration - 1.25
            final = cache / f"{key}_slot{round(slot*1000)}_{SR}.wav"
            if not final.exists():
                y, rate = read_wave(source)
                y = resample_poly(y, SR, rate).astype(np.float32) if rate != SR else y
                indices = np.flatnonzero(np.abs(y) > .0025)
                if len(indices):
                    y = y[max(0, int(indices[0])-round(SR*.045)):min(len(y), int(indices[-1])+round(SR*.12))]
                seconds = len(y) / SR
                if seconds > slot * 1.25 and speech.engine == "local" and not provided.exists():
                    # A slow or repeated take is auditioned again before changing a shot's clock.
                    retry_direction = take_direction + "语速稍快，停顿简洁，每句只读一遍。"
                    source, _ = speech.take(shot.text, voice=voice, direction=retry_direction, seed=103+shot.index)
                    y, rate = read_wave(source)
                    y = resample_poly(y, SR, rate).astype(np.float32) if rate != SR else y
                    indices = np.flatnonzero(np.abs(y) > .0025)
                    if len(indices):
                        y = y[max(0, int(indices[0])-round(SR*.045)):min(len(y), int(indices[-1])+round(SR*.12))]
                    seconds = len(y)/SR
                    # Keep the first-take cache key for the selected final waveform.
                if seconds > slot:
                    ratio = seconds / slot
                    if ratio > 1.25:
                        raise ValueError(f"{shot.id}: emotional take is {seconds:.2f}s for a {slot:.2f}s slot; extend the shot")
                    trimmed = cache / f"{key}_trim.wav"
                    write_wave(trimmed, y, SR)
                    subprocess.run([settings.tool("ffmpeg"), "-v", "error", "-y", "-i", str(trimmed),
                                    "-af", f"atempo={ratio:.8f}", "-ar", str(SR), "-ac", "1", str(final)], check=True)
                    trimmed.unlink(missing_ok=True)
                    y, _ = read_wave(final)
                    if len(y)/SR > slot + .05:
                        raise ValueError(f"{shot.id}: speech still exceeds its slot")
                peak = float(np.max(np.abs(y))) if len(y) else 0
                if peak < .001:
                    raise ValueError(f"Empty voice: {shot.id}")
                write_wave(final, y * (.44/peak), SR)
            y, _ = read_wave(final)
            result[shot.id] = y
            # Thoughts and narration are audible without animating the on-screen mouth.
            visible_speaker = who if shot.data.get("delivery") != "thought" else None
            pending.append((shot, y, visible_speaker, key, performance_path))
            report["cues"].append({"shot": shot.id, "status": "recording" if provided.exists() else "synthesized",
                                   "voice": voice, "character": who, "seconds": round(len(y)/SR, 3),
                                   "start": shot.start+.65, "file": str(final.relative_to(ROOT)),
                                   "direction": direction_for(shot, profile)})
            print(f"{shot.id}: {voice}, {len(y)/SR:.2f}s", flush=True)
    finally:
        if speech:
            speech.close()
    # Free the TTS model before loading the aligner or any frame workers.
    aligner = ForcedAligner() if speech and speech.engine == "local" else None
    try:
        for shot, y, who, key, performance_path in pending:
            alignment = []
            if who and aligner:
                aligned_cache = cache / f"{key}_aligned{round(shot.duration*1000)}.json"
                if aligned_cache.exists():
                    alignment = json.loads(aligned_cache.read_text())
                else:
                    alignment = aligner.align(y, SR, shot.text)
                    aligned_cache.write_text(json.dumps(alignment, ensure_ascii=False))
            data = describe(y, SR, text=shot.text, speaker=who, alignment=alignment,
                            method="forced-aligned" if alignment else "envelope")
            performance_path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    finally:
        if aligner:
            aligner.close()
    (out/f"{episode['id']}_speech.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return result, report


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
    from score import music as scene_score
    return scene_score(episode, shot)


def synthesize(episode, out, mode="auto", engine="auto"):
    out=Path(out); out.mkdir(parents=True,exist_ok=True)
    voices,report=prepare_voices(episode,out,mode,engine)
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
