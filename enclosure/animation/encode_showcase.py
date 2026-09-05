"""Encode rendered PNG sequences with FFmpeg; run using Python 3."""
from pathlib import Path
import subprocess, shutil, json, argparse
root=Path(__file__).resolve().parents[2]; out=root/'media/showcase'
p=argparse.ArgumentParser(); p.add_argument('--clip', choices=['orbit','assembly','electronics']); a=p.parse_args()
manifest=[]
for clip in ([a.clip] if a.clip else ('orbit','assembly','electronics')):
 frames=out/'frames'/clip
 missing=[i for i in range(1,145) if not (frames/f'{i:04}.png').exists()]
 if missing: raise SystemExit(f'{clip}: missing {len(missing)} frames')
 source=['ffmpeg','-hide_banner','-loglevel','error','-y','-framerate','24','-i',str(frames/'%04d.png')]
 subprocess.run(source+['-frames:v','144','-c:v','libx264','-preset','slow','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(out/f'{clip}.mp4')],check=True)
 subprocess.run(source+['-filter_complex','fps=10,scale=560:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=sierra2_4a','-loop','0',str(out/f'{clip}.gif')],check=True)
 shutil.copy2(frames/('0073.png' if clip=='assembly' else '0001.png'),out/f'{clip}-poster.png')
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(out/f'{clip}.mp4')]))
 stream=probe['streams'][0]
 assert stream['nb_frames']=='144' and stream['width']==960 and stream['height']==720
 manifest.append({'name':clip,'seconds':6,'width':960,'height':720,'fps':24,'mp4_bytes':(out/f'{clip}.mp4').stat().st_size,'gif_bytes':(out/f'{clip}.gif').stat().st_size})
if a.clip:
 existing=json.loads((out/'manifest.json').read_text()) if (out/'manifest.json').exists() else []
 manifest=[v for v in existing if v['name']!=a.clip]+manifest
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest,indent=2))
