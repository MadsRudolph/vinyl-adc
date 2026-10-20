"""Cut the rev D YouTube short (1080x1920, 30 fps, silent) from the phone footage, the photos and the Blender renders.

    python3 media/rev-d-photos/build_short.py [--only N] [--preview]

Every segment is rendered to build/seg-NN.mp4 (photos as subpixel Ken Burns frames from PIL, phone clips through
ffmpeg, renders from their PNG frames), its title overlaid as a PIL-drawn PNG with an alpha fade, then all are joined
into short/vinyl-adc-rev-d-short.mp4. The phone originals stay in raw/ (not in git).
"""
import argparse,subprocess,shutil
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageFilter,ImageOps

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
RAW=HERE/'raw';BUILD=HERE/'build';OUT=HERE/'short'
FRAMES=ROOT/'hardware/kicad/rev_d/render/build/frames'
FONTS=HERE/'fonts'   # Poppins and IBM Plex Mono (OFL), the madsrudolph.dev typefaces
W,H,FPS=1080,1920,30
GRADE='eq=contrast=1.04:saturation=0.92:gamma=1.02,unsharp=5:5:0.4'   # phone footage: tame the red mat a little

ap=argparse.ArgumentParser();ap.add_argument('--only',type=int);ap.add_argument('--preview',action='store_true');args=ap.parse_args()

def run(cmd):subprocess.run(cmd,check=True)
def enc(): return ['-c:v','libx264','-preset','slow','-crf','16','-pix_fmt','yuv420p','-r',str(FPS),'-an','-movflags','+faststart']

# ---------------------------------------------------------------- titles
def title_png(path,big,small=None,y=250):
    im=Image.new('RGBA',(W,H),(0,0,0,0));d=ImageDraw.Draw(im)
    fb=ImageFont.truetype(str(FONTS/'Poppins-Bold.ttf'),76);fs=ImageFont.truetype(str(FONTS/'PlexMono-Medium.ttf'),38)
    lines=big.split('\n');yy=y;boxes=[]
    for ln in lines:
        w=d.textlength(ln,font=fb);boxes.append((ln,(W-w)/2,yy,fb));yy+=94
    if small:
        yy+=14
        for ln in small.split('\n'):
            w=d.textlength(ln,font=fs);boxes.append((ln,(W-w)/2,yy,fs));yy+=52
    sh=Image.new('RGBA',(W,H),(0,0,0,0));ds=ImageDraw.Draw(sh)
    for ln,x,yv,f in boxes:ds.text((x,yv+3),ln,font=f,fill=(0,0,0,230))
    sh=sh.filter(ImageFilter.GaussianBlur(9))
    for ln,x,yv,f in boxes:d.text((x,yv),ln,font=f,fill=(255,255,255,255) if f is fb else (150,240,170,255))
    # a soft dark band behind the titles, so they read over silkscreen and keyboards alike
    top=max(0,y-170);bot=yy+150;a=np.zeros((H,1),np.float32)
    for r in range(top,bot):
        u=min(1,(r-top)/120,(bot-r)/150);a[r]=.62*u*u*(3-2*u)
    scrim=Image.fromarray(np.dstack([np.zeros((H,W,3),np.uint8),np.repeat((a*255).astype(np.uint8),W,1)]),'RGBA')
    Image.alpha_composite(Image.alpha_composite(scrim,sh),im).save(path)

def with_title(src,dst,dur,big,small=None,y=250,fade_in=0.25,start=0.15):
    png=BUILD/(dst.stem+'-title.png');title_png(png,big,small,y)
    fo=max(start+fade_in,dur-.35)
    run(['ffmpeg','-v','error','-y','-i',str(src),'-loop','1','-t',f'{dur}','-i',str(png),'-filter_complex',
         f'[1:v]format=rgba,fade=in:st={start}:d={fade_in}:alpha=1,fade=out:st={fo}:d=0.3:alpha=1[t];[0:v][t]overlay=0:0:shortest=1,format=yuv420p',
         '-t',f'{dur}',*enc(),str(dst)])

# ---------------------------------------------------------------- sources
def photo(name,dur,start,end,out):
    """Ken Burns over a photo. start/end are (cx, cy, height) in fractions of the photo: the window centre and its height."""
    im=ImageOps.exif_transpose(Image.open(RAW/name)).convert('RGB');iw,ih=im.size
    tmp=BUILD/(out.stem+'-kb');shutil.rmtree(tmp,ignore_errors=True);tmp.mkdir(parents=True)
    n=int(round(dur*FPS))
    for i in range(n):
        u=i/(n-1);u=u*u*(3-2*u)
        cx,cy,hh=[a+(b-a)*u for a,b in zip(start,end)]
        h=hh*ih;w=h*W/H;x0=cx*iw-w/2;y0=cy*ih-h/2
        fr=im.transform((W,H),Image.Transform.EXTENT,(x0,y0,x0+w,y0+h),Image.Resampling.BICUBIC)
        fr.save(tmp/f'{i:04}.png')
    run(['ffmpeg','-v','error','-y','-framerate',str(FPS),'-i',str(tmp/'%04d.png'),'-vf',GRADE,*enc(),str(out)])

def clip(name,ss,dur,out,speed=1.,crop_x=None):
    """A phone clip. Portrait clips are scaled; landscape ones are cropped to 9:16 around crop_x (fraction of width)."""
    vf=[]
    if crop_x is not None:
        vf.append(f"crop=ih*9/16:ih:(iw-ih*9/16)*{crop_x}:0")
    vf+= [f'setpts=PTS/{speed}',f'scale={W}:{H}:flags=lanczos',GRADE,f'fps={FPS}']
    run(['ffmpeg','-v','error','-y','-ss',f'{ss}','-t',f'{dur*speed}','-i',str(RAW/name),'-vf',','.join(vf),'-t',f'{dur}',*enc(),str(out)])

def render(shot,out,first=1,last=None,dur=None):
    fr=sorted(p for p in (FRAMES/shot).glob('[0-9]*.png'));last=last or len(fr)
    n=last-first+1
    run(['ffmpeg','-v','error','-y','-framerate',str(FPS),'-start_number',str(first),'-i',str(FRAMES/shot/'%04d.png'),
         '-frames:v',str(n),*enc(),str(out)])

# ---------------------------------------------------------------- the edit
SEGMENTS=[
 # (builder, duration, title, subtitle)
 (lambda o:photo('20261021_001723.jpg',3.4,(.30,.52,.98),(.62,.55,.80),o),3.4,
  'Four boards.\nMilled at home.','the old Vinyl ADC'),
 (lambda o:photo('20261021_001723.jpg',2.6,(.70,.56,.78),(.74,.60,.62),o),2.6,
  'One board.\nMade by PCBWay.','rev D · 4 layers'),
 (lambda o:clip('20261021_001916.mp4',0.4,3.4,o,speed=1.0),3.4,
  '649 plated holes','0.25 mm tracks · HASL lead-free'),
 (lambda o:photo('20261021_001028.jpg',3.0,(.50,.50,1.0),(.46,.47,.86),o),3.0,
  'Silkscreen\nthis sharp','0.8 mm legends'),
 (lambda o:photo('20261021_001213.jpg',2.8,(.42,.46,.70),(.56,.58,.52),o),2.8,
  'Every via tented','solder mask both sides'),
 (lambda o:render('v_fly',o,first=21,last=140),4.0,
  '184 parts','every one through-hole'),
 (lambda o:clip('20261021_001846.mp4',0.5,4.0,o,speed=1.6),4.0,
  'No ADC chip.','op-amps, comparators\nand 74HC logic'),
 (lambda o:render('v_led',o),4.0,
  'A delta-sigma ADC,\nbuilt from parts',None),
 (lambda o:clip('20261021_002125.mp4',1.6,3.0,o,speed=1.4,crop_x=.42),3.0,
  'Onto the Pi','a Raspberry Pi 4 HAT'),
 (lambda o:clip('20261021_002125.mp4',13.0,2.6,o,speed=1.0,crop_x=.40),2.6,
  'Powered up',None),
 (lambda o:render('v_explode',o),4.0,
  '78.7 dB','dynamic range, measured\n+11 dB over the milled boards'),
 (lambda o:clip('20261021_002515.mp4',0.5,4.2,o,speed=1.0,crop_x=.12),4.2,
  'Ripping my records','straight to FLAC'),
 (lambda o:render('v_orbit',o),4.0,
  'PCBs by PCBWay','thank you for the boards\nvinyl-adc.madsrudolph.dev'),
]

BUILD.mkdir(exist_ok=True);OUT.mkdir(exist_ok=True)
parts=[]
for i,(build,dur,big,small) in enumerate(SEGMENTS):
    base=BUILD/f'base-{i:02}.mp4';seg=BUILD/f'seg-{i:02}.mp4';parts.append(seg)
    if args.only is not None and i!=args.only:continue
    if not base.exists():build(base)
    with_title(base,seg,dur,big,small,y=250)
    print('segment',i,'done')
lst=BUILD/'list.txt';lst.write_text(''.join(f"file '{p}'\n" for p in parts))
final=OUT/'vinyl-adc-rev-d-short.mp4'
run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',str(lst),*enc(),str(final)])
print(final)
