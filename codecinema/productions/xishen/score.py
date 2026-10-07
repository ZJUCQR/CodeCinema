"""Original scene-led chamber score, sharing the film clock and DSP toolkit."""

from functools import lru_cache
import math

import numpy as np

from codecinema.audio import dsp

SR = int(dsp.SR)

# The protagonist's motif recurs with different harmony, rhythm and orchestration.
MOTIF = (62, 69, 65, 64, 60, 62, 57, 60)
FAMILIES = {
    "theatre": {"stage", "stage_walk", "stage_run", "audience", "expectation", "curtain", "water_message"},
    "investigation": {"grave", "grave_inquiry", "han", "device", "clinic", "clinic_close", "tea", "paper", "letter"},
    "wonder": {"aurora", "gray", "domains", "memory", "memory_fall", "thinking", "thinking_close"},
    "comedy": {"breakfast", "breakfast_close", "soy", "coins", "chase", "recruit", "intervene", "director", "rule"},
}


def family(scene):
    return next((name for name, scenes in FAMILIES.items() if scene in scenes), "rain")


def pan(y, position=0):
    angle=(position+1)*math.pi/4
    return np.column_stack((y*math.cos(angle), y*math.sin(angle))).astype(np.float32)


@lru_cache(maxsize=192)
def note(kind, midi, duration_ms, seed):
    duration=duration_ms/1000
    n=round(duration*SR)
    freq=440*2**((midi-69)/12)
    t=np.arange(n,dtype=np.float32)/SR
    rng=np.random.default_rng(seed)
    if kind in ("piano", "celesta", "marimba"):
        ratios=(1,2,3.004,4.012,5.02,6.032) if kind=="piano" else (1,2.76,5.4,8.93)
        amps=(1,.36,.18,.11,.05,.03) if kind=="piano" else (1,.18,.07,.025)
        decays=[max(.18,(2.8 if kind=="piano" else 2.1)/(j+1)**.6) for j in range(len(ratios))]
        y=dsp.modal([freq*r for r in ratios],amps,decays,n,attack=.004 if kind=="piano" else .002)
        if kind=="piano":
            y+=rng.standard_normal(n)*np.exp(-t/.006)*.016
    else:
        y=np.zeros(n,np.float32)
        harmonics=range(1,12) if kind=="strings" else range(1,12,2)
        for harmonic in harmonics:
            for detune in (-.0021,.0026):
                vibrato=.002*np.sin(math.tau*5.1*t+rng.uniform(0,math.tau))
                phase=math.tau*freq*harmonic*(t*(1+detune)+np.cumsum(vibrato,dtype=np.float32)/SR)
                y+=np.sin(phase+rng.uniform(0,math.tau))/harmonic**(1.5 if kind=="strings" else 1.7)
        y*=np.minimum(1,t/(.48 if kind=="strings" else .06))*np.minimum(1,(duration-t)/.35)
    peak=max(float(np.max(np.abs(y))),.001)
    return np.asarray(y/peak,dtype=np.float32)


def music(episode, shot):
    n=round(shot.duration*SR)
    mix=np.zeros((n,2),np.float32)
    theme=family(shot.data['scene'])
    beat={"rain":.92,"theatre":.72,"investigation":.83,"wonder":1.12,"comedy":.48}[theme]
    instruments={"rain":("piano","strings"),"theatre":("celesta","strings"),
                 "investigation":("piano","strings"),"wonder":("celesta","strings"),
                 "comedy":("marimba","clarinet")}[theme]

    def add(kind, midi, at, duration, gain, position=0, seed=0):
        y=note(kind,midi,round(duration*1000),seed)
        source=max(0,round((shot.start-at)*SR));destination=max(0,round((at-shot.start)*SR))
        count=min(len(y)-source,n-destination)
        if count>0:
            mix[destination:destination+count]+=pan(y[source:source+count]*gain,position)

    bar=beat*4
    chords=([50,57,62,65],[46,53,58,62],[43,50,55,58],[45,52,57,64])
    if theme=="comedy":
        chords=([50,57,62,66],[47,54,59,62],[43,50,55,59],[45,52,57,61])
    # Overlapping string/woodwind phrases sustain across cuts on the story clock.
    for index in range(math.floor((shot.start-bar*1.5)/bar),math.ceil(shot.end/bar)):
        at=index*bar
        if at<0:continue
        chord=chords[(index//2)%4]
        for j,midi in enumerate(chord):
            if theme=="comedy" and j%2:continue
            add(instruments[1],midi,at,bar*1.3,.009 if theme!="comedy" else .012,
                -.45+j*.3,810+index*7+j)
        if theme in ("theatre","investigation"):
            add("piano",chord[0]-12,at,2.6,.025,-.18,900+index)
    # Sparse rain phrases leave room for foley; comic passages use shorter answers.
    step=beat*(2 if theme in ("rain","wonder") else 1)
    for index in range(math.floor((shot.start-3.2)/step),math.ceil(shot.end/step)):
        at=index*step
        if at<0 or (theme=="rain" and index%8 in (3,4,7)):continue
        midi=MOTIF[index%8]+(12 if theme=="wonder" else 0)
        if theme=="comedy" and midi%12==5:midi+=1
        if theme=="investigation" and index%4==3:continue
        gain=.037 if index%4==0 else .024
        add(instruments[0],midi,at,3.2 if theme!="comedy" else .8,gain,
            -.25 if index%2 else .3,500+index)
    # Deliberate near-silence at discoveries gives the cue a dramatic shape.
    if shot.data['scene'] in ("tea","device","audience"):
        t=np.arange(n,dtype=np.float32)/SR
        dip=1-.75*np.exp(-((t-shot.duration*.63)/.65)**2)
        mix*=dip[:,None]
    return mix
