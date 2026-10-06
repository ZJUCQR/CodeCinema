"""Make a Blender character/acting study using an existing story shot.

    codecinema run xishen blender --still
    codecinema run xishen blender --shot ep01_face
    codecinema run xishen blender --shot ep01_lost

This is look development for the opening rain sequence, not a trilogy master.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
import json
import re
import ssl
import subprocess
from urllib.request import urlopen
import wave

import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import butter, sosfilt

from codecinema import blender, media, settings
from codecinema.audio.performance import Performance
from story import ROOT, STORY, digest, timeline, validate
from score import music

REVISION = '063bff04e60f3e7c651fda628c30f5d83f3f3078'
SOURCE = 'https://raw.githubusercontent.com/animate1978/MB-Lab/'+REVISION+'/'
# Pin the database separately from the MIT framework. Downloads stay in out/.
ASSETS = {
    'license.txt': '021a9f55e1d9938486e39c566445c4363c40366ac2aa47d81738f22126e16cf9',
    'data/humanoid_library.blend': 'ae2a03430be1ef0f74a9bfa01136579e88beb521c9db7d496b5921bec6d1cd4e',
    'data/vertices/m_as01_verts.json': '8db331995089a681b3b893b39d9ac0b82ea02c4d84d7a246b0cb7dafe868835e',
    'data/morphs/m_as01_morphs.json': '75e6e2b9688dd5b2a4b012e5c9327bda4bff8c544a9f85ace99883cf323866b2',
    'data/joints/human_male_joints.json': 'b4444a0324338859846ed0b214a97ea762689600958e29a846ea4e61cb7a5b8a',
    'data/joints/human_male_joints_offset.json': '9d91e64db260c96f41486d2f22c65256b37783142c5b3fe1df91d0e87e528ce9',
    'data/vgroups/human_male_vgroups_base.json': 'ab75e638d3caf4875c36b9e38d0f379b86bc1ac1c29859bb4af1f38783a4a42f',
    'data/expressions_morphs/m_as01_exprs.json': '1c07088c5eafe66f7de139e3b5b2721b79e418d1d777bd793d8754096680b14a',
    'data/textures/hum_m_asian_albedo.png': '682336a0b0b7a1bbdb6ba8e0ade1aa3ce45f18516d300bc3d6905804b3394851',
    'data/textures/human_male_bump.png': 'c5a7b8f691e24c24504b139d9b87e076be3f1058147691e341d426c33c79d350',
    'data/textures/eyes_albedo.png': '25427e1375ddbab14a37d7fbe3da832680f8c7696508f7470bd2c3d43ef912c1',
    'data/textures/human_male_teeth.png': '58ea9eb2cac6027526fec404eb3440ef2789a7c00b9f42bb2665fee9af99169e',
    'data/textures/human_male_eyelash.png': '88aa8d523321d52c4444837a6abed965c955ce8dbb9077a396a6867060cfb74d',
}


def prepare_assets(folder):
    folder.mkdir(parents=True, exist_ok=True)
    context=ssl.create_default_context()
    try:
        import certifi
        context=ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass

    def download(item):
        name, expected=item
        target=folder/name
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest()==expected:
            return
        print('Preparing actor asset: '+name, flush=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload=urlopen(SOURCE+name, timeout=60, context=context).read()
        if hashlib.sha256(payload).hexdigest()!=expected:
            raise RuntimeError('Actor asset integrity check failed: '+name)
        temporary=target.with_name(target.name+'.partial')
        temporary.write_bytes(payload)
        temporary.replace(target)

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(download, ASSETS.items()))
    (folder/'source.json').write_text(json.dumps({
        'project':'MB-Lab','revision':REVISION,'source':SOURCE,
        'database_license':'AGPL-3.0-or-later',
        'render_license':'Rendered images and videos are original works under the upstream render exception.',
        'files':ASSETS}, indent=2)+'\n', encoding='utf-8')


def recorded_take(episode, shot, out, options):
    if options.narration=='off':
        return None, None
    performance=out/'audio/performance'/f'{shot.id}.json'
    report_path=out/'audio'/f"{episode['id']}_speech.json"
    profile=Performance.load(performance).data
    report=json.loads(report_path.read_text()) if report_path.is_file() else {}
    cue=next((row for row in report.get('cues',[]) if row['shot']==shot.id), {})
    filename=ROOT/cue['file'] if cue.get('file') else None
    provided=ROOT/'assets/voices'/f'{shot.id}.wav'
    stale=(profile.get('text')!=shot.text or not filename or not filename.is_file())
    if options.speech_engine!='auto' and report.get('engine')!=options.speech_engine:
        stale=True
    if provided.is_file() and (cue.get('status')!='recording' or not filename or not filename.is_file() or
                              provided.stat().st_mtime>filename.stat().st_mtime):
        stale=True
    if stale:
        from sound import prepare_voices
        prepare_voices(episode, out/'audio', options.narration, options.speech_engine)
    report=json.loads(report_path.read_text())
    cue=next((row for row in report['cues'] if row['shot']==shot.id), {})
    filename=ROOT/cue['file'] if cue.get('file') else None
    if filename and filename.is_file():
        return performance, filename
    if options.narration=='required':
        raise RuntimeError('Missing dialogue for '+shot.id)
    return None, None


def soundtrack(episode, shot, voice, target, gait_period):
    from codecinema.audio import dsp
    from sound import event, foot_splashes
    rate=int(dsp.SR)
    n=round(shot.duration*rate)
    y=music(episode, shot)
    rng=np.random.default_rng(720+shot.index)
    noise=sosfilt(butter(2,3300,fs=rate,output='sos'),rng.standard_normal(n))
    y+=np.column_stack((noise,noise))*.012
    if shot.data.get('sfx'):
        at=2.15 if shot.data['sfx']=='thunder' else 1.0
        effect=event(shot.data['sfx'],min(3.8,shot.duration-at-.2),602+shot.index)
        begin=round(at*rate);count=min(len(effect),n-begin)
        y[begin:begin+count]+=effect[:count]
    if shot.data['scene']=='rain_wide':
        # Barefoot splashes land on the same alternating contact clock as IK.
        y+=foot_splashes(shot.duration,gait_period,rng)
    if voice:
        with wave.open(str(voice),'rb') as source:
            if source.getsampwidth()!=2 or source.getframerate()!=rate or source.getnchannels()!=1:
                raise ValueError('Expected the pipeline\'s mono PCM16 dialogue at '+str(rate)+' Hz')
            spoken=np.frombuffer(source.readframes(source.getnframes()),dtype=np.int16).astype(np.float32)/32768
        start=round(.65*rate)
        if start+len(spoken)>n:
            raise ValueError('Dialogue exceeds the selected shot; extend its timeline duration')
        dialogue=np.zeros(n,np.float32);dialogue[start:start+len(spoken)]=spoken
        activity=np.clip(uniform_filter1d(np.abs(dialogue),size=round(.12*rate))/.024,0,1)
        y*=1-.65*activity[:,None]
        y+=np.column_stack((dialogue,dialogue))*.7071
    t=np.arange(n)/rate
    y*=np.minimum(1,t/.06)[:,None]*np.minimum(1,(shot.duration-t)/.12)[:,None]
    if not np.all(np.isfinite(y)):
        raise ValueError('Nonfinite preview sound')
    with wave.open(str(target),'wb') as fh:
        fh.setnchannels(2);fh.setsampwidth(2);fh.setframerate(rate)
        fh.writeframes((np.clip(y,-.97,.97)*32767).astype(np.int16).tobytes())


def main(args=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shot',default='ep01_face',help='Opening rain shot, e.g. ep01_face or ep01_lost')
    parser.add_argument('--still',action='store_true',help='Render one character review frame')
    parser.add_argument('--at',type=float,default=2.4,help='Time in seconds for a still')
    parser.add_argument('--engine',choices=('eevee','cycles'),default='eevee')
    parser.add_argument('--width',type=int,default=1280)
    parser.add_argument('--samples',type=int,default=32)
    parser.add_argument('--narration',choices=('auto','off','required'),default='auto')
    parser.add_argument('--speech-engine',choices=('auto','local','system','recording'),default='auto')
    options=parser.parse_args(args)
    validate()
    found=[(e,s) for e in STORY['episodes'] for s in timeline(e) if s.id==options.shot]
    if not found:
        parser.error('Unknown story shot: '+options.shot)
    episode,shot=found[0]
    if shot.data['scene'] not in ('rain_face','rain_wide') or shot.costume!='red_robe':
        parser.error('This Blender study currently supports the opening red-robe rain close-ups and walk')
    height=round(options.width*9/16)
    if options.width<320 or options.width>3840 or options.width%2 or height%2 or abs(options.width/height-16/9)>.002:
        parser.error('Use an even 16:9 size, e.g. --width 1280 or --width 1920')
    if not 1<=options.samples<=1024 or not 0<=options.at<shot.duration:
        parser.error('Invalid sample count or still time')
    fps=int(settings.get('video','fps',24))
    if not 1<=fps<=60 or abs(shot.duration*fps-round(shot.duration*fps))>1e-6:
        parser.error('Use a frame rate from 1 to 60 with whole-frame shot durations')
    try:
        result=subprocess.run([settings.tool('blender'),'--version'],capture_output=True,text=True,check=True)
    except (FileNotFoundError,subprocess.CalledProcessError) as exc:
        raise RuntimeError('Install Blender 5.2+ or set BLENDER_BIN to its executable.') from exc
    version=result.stdout.splitlines()[0]
    match=re.search(r'Blender (\d+)\.(\d+)',version)
    if not match or tuple(map(int,match.groups()))<(5,2):
        raise RuntimeError('This scene requires Blender 5.2 or later; found '+version)
    out=Path(settings.path('paths','out_dir'))
    study=out/'blender';study.mkdir(parents=True,exist_ok=True)
    assets=study/'assets/mblab';prepare_assets(assets)
    performance,voice=recorded_take(episode,shot,out,options)
    manifest={'assets':str(assets),'performance':str(performance) if performance else '',
              'scene':shot.data['scene'],'shot':shot.id,'fps':fps,'frames':round(shot.duration*fps),
              'width':options.width,'height':height,'engine':'CYCLES' if options.engine=='cycles' else 'BLENDER_EEVEE',
              'samples':options.samples,'at':options.at,'blender_version':version,
              'walk_speed':.28,'gait_period':1.35}
    extra=json.dumps(manifest,sort_keys=True)+Path(blender.__file__).read_text()
    if performance:extra+=performance.read_text()
    signature=digest(extra)
    directory=study/'cache'/signature;directory.mkdir(parents=True,exist_ok=True)
    manifest.update(directory=str(directory),still=options.still)
    manifest_path=directory/'manifest.json'
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(f'Blender study: {shot.id}, {options.width} × {height}, {fps} fps, {options.engine}',flush=True)
    blender.run(Path(__file__).with_name('blender_scene.py'), '--manifest', manifest_path)
    if options.still:
        from PIL import Image
        frame=min(manifest['frames'],round(options.at*fps)+1)
        target=study/f'{shot.id}.jpg'
        Image.open(directory/f'{frame:05d}.png').convert('RGB').save(target,quality=95,subsampling=0)
    else:
        picture=directory/'picture.mp4'
        subprocess.run([media.ffmpeg(),'-v','error','-y','-framerate',str(fps),'-start_number','1',
                        '-i',str(directory/'%05d.png'),'-frames:v',str(manifest['frames']),
                        '-c:v','libx264','-crf','17','-preset','fast','-pix_fmt','yuv420p',str(picture)],check=True)
        audio=directory/'sound.wav';soundtrack(episode,shot,voice,audio,manifest['gait_period'])
        target=study/f'{shot.id}.mp4';partial=study/f'{shot.id}.partial.mp4'
        media.mux(str(picture),str(audio),str(partial),metadata={'title':shot.id+' • Blender acting study','artist':'ZJUCQR'})
        info=media.probe(str(partial))
        if info['frames']!=manifest['frames'] or abs(info['duration']-shot.duration)>.1:
            raise RuntimeError('The Blender study has an incorrect duration or frame count')
        partial.replace(target)
    print('Blender study complete: '+str(target),flush=True)
    return 0
