"""Voiceover for the short: one Kokoro clip per line, joined with set pauses, plus word timings for the captions.

    .venv/bin/python voice.py [--voice am_michael] [--speed 1.08]

Writes audio/vo.wav (24 kHz mono) and public/vo.json: lines with start/end and words with start/end (seconds).
The ElevenLabs swap: elevenlabs_voice.py writes the same two files from the same LINES.
"""
import argparse,json
from pathlib import Path
import numpy as np,soundfile as sf

HERE=Path(__file__).resolve().parent
# (key, text, pause after in seconds). Keys are what the Remotion scenes hang off.
SCRIPTS={}
LINES=[
 ('hook',   "This audio converter has no converter chip.",0.25),
 ('bits',   "Just op-amps, comparators and logic, turning a record into one and a half million bits every second.",0.35),
 ('milled', "Version one was four boards I milled myself, held together with jumper wires.",0.15),
 ('barely', "It worked. Barely.",0.35),
 ('pcbway', "So PCBWay built it properly.",0.3),
 ('layers', "Four copper layers, with a solid ground plane in the middle.",0.2),
 ('holes',  "Six hundred and forty-nine plated holes.",0.15),
 ('silk',   "And silkscreen this sharp.",0.35),
 ('pi',     "It drops straight onto a Raspberry Pi,",0.1),
 ('rip',    "and rips my records to lossless files, all by itself.",0.4),
 ('result', "The result? Seventy-eight point seven decibels of dynamic range.",0.15),
 ('eleven', "Eleven more than my homemade boards.",0.4),
 ('end',    "Boards by PCBWay.",0.6),
]

SCRIPTS['short']=(LINES,1.05)
SCRIPTS['story']=([
 ('hook',   "I built an audio converter with no converter chip.",0.2),
 ('sep',    "In September, I milled the boards myself.",0.15),
 ('mess',   "Four boards, a pile of jumper wires, and two days of debugging.",0.35),
 ('oct',    "In October, PCBWay sent me these.",0.3),
 ('look',   "Look at this.",0.25),
 ('detail', "Every hole plated. Four layers, with a ground plane I could never mill.",0.3),
 ('solder', "A lot of soldering later,",0.1),
 ('pi',     "it plugs straight into a Raspberry Pi and rips my records by itself.",0.3),
 ('better', "And it measures eleven decibels better than the old one.",0.35),
 ('thanks', "Thanks, PCBWay.",0.6),
],1.07)
SCRIPTS['cine']=([
 ('groove', "Every record is a groove.",0.9),
 ('nochip', "This board reads it without a converter chip.",0.7),
 ('parts',  "Op-amps. Comparators. Logic.",1.0),
 ('layers', "Four copper layers, made by PCBWay.",1.1),
 ('dr',     "Seventy-eight point seven decibels of dynamic range.",1.0),
 ('kept',   "Your records, kept the way they sound.",0.9),
 ('name',   "Vinyl ADC. Boards by PCBWay.",0.8),
],0.92)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--voice',default='am_puck');ap.add_argument('--speed',type=float);ap.add_argument('--edit',default='short')
    a=ap.parse_args();LINES_,sp=SCRIPTS[a.edit];speed=a.speed or sp;tag='' if a.edit=='short' else '-'+a.edit
    from kokoro import KPipeline
    from faster_whisper import WhisperModel
    pipe=KPipeline(lang_code='a');sr=24000
    asr=WhisperModel('small.en',device='cpu',compute_type='int8')
    out=[];t=0.;lines=[];lead=0.2
    out.append(np.zeros(int(lead*sr),np.float32));t=lead
    (HERE/'audio').mkdir(exist_ok=True)
    for key,text,pause in LINES_:
        chunks=[np.asarray(audio,np.float32) for _,_,audio in pipe(text,voice=a.voice,speed=speed)]
        y=np.concatenate(chunks)
        # trim leading/trailing silence so the pauses are ours
        env=np.abs(y)>0.01;i0=max(0,np.argmax(env)-int(.02*sr));i1=len(y)-max(0,np.argmax(env[::-1])-int(.05*sr));y=y[i0:i1]
        p=HERE/'audio'/f'line{tag}-{key}.wav';sf.write(p,y,sr)
        y16=np.interp(np.arange(0,len(y),1.5),np.arange(len(y)),y).astype(np.float32)
        segs,_=asr.transcribe(y16,word_timestamps=True,language='en',initial_prompt=text)
        words=[]
        for w in (w for s in segs for w in s.words):
            tok=w.word.strip()
            if tok.startswith('-') and words:words[-1]['w']+=tok;words[-1]['e']=round(t+w.end,3)
            else:words.append({'w':tok,'s':round(t+w.start,3),'e':round(t+w.end,3)})
        script=text.split()
        if len(script)==len(words):                      # the captions say what the script says, at whisper's timing
            for w,sw in zip(words,script):w['w']=sw
        d=len(y)/sr;lines.append({'key':key,'text':text,'start':round(t,3),'end':round(t+d,3),'words':words})
        out.append(y);out.append(np.zeros(int(pause*sr),np.float32));t+=d+pause
        print(f'{key:7s} {t-d-pause:6.2f}-{t-pause:6.2f}  {text}')
    sf.write(HERE/f'audio/vo{tag}.wav',np.concatenate(out),sr)
    (HERE/'public').mkdir(exist_ok=True)
    (HERE/f'public/vo{tag}.json').write_text(json.dumps({'duration':round(t,3),'lines':lines},indent=1))
    print('total',round(t,2),'s')

if __name__=='__main__':main()
