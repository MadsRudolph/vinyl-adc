"""Encode rendered PNG sequences with FFmpeg; run using Python 3."""
from pathlib import Path
import hashlib
import subprocess, shutil, json, argparse
root=Path(__file__).resolve().parents[2]; out=root/'media/showcase'
p=argparse.ArgumentParser(); p.add_argument('--clip', choices=['orbit','assembly','electronics']); a=p.parse_args()
manifest=[]
for clip in ([a.clip] if a.clip else ('orbit','assembly','electronics')):
 frames=out/'frames'/clip
 stamp=json.loads((frames/'render.json').read_text())
 assert stamp['source_sha256']==hashlib.sha256((root/'enclosure/vinyl_adc_enclosure.blend').read_bytes()).hexdigest(), 'Frames are from another enclosure revision'
 assert stamp['frames']==72
 missing=[i for i in range(1,73) if not (frames/f'{i:04}.png').exists()]
 if missing: raise SystemExit(f'{clip}: missing {len(missing)} frames')
 source=['ffmpeg','-hide_banner','-loglevel','error','-y','-framerate','12','-i',str(frames/'%04d.png'),'-frames:v','72']
 subprocess.run(source+['-c:v','libx264','-preset','slow','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(out/f'{clip}.mp4')],check=True)
 subprocess.run(source+['-filter_complex','fps=12,scale=720:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=256[p];[b][p]paletteuse=dither=sierra2_4a','-loop','0',str(out/f'{clip}.gif')],check=True)
 gif_probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_streams','-of','json',str(out/f'{clip}.gif')]))['streams'][0]
 assert gif_probe['nb_read_frames']=='72' and gif_probe['width']==720 and gif_probe['height']==540
 assert abs(float(gif_probe['duration'])-6)<0.02
 shutil.copy2(frames/('0037.png' if clip=='assembly' else '0001.png'),out/f'{clip}-poster.png')
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(out/f'{clip}.mp4')]))
 stream=probe['streams'][0]
 assert stream['nb_frames']=='72' and stream['width']==960 and stream['height']==720
 manifest.append({'name':clip,'seconds':6,'width':960,'height':720,'fps':12,'mp4_bytes':(out/f'{clip}.mp4').stat().st_size,'gif_width':720,'gif_height':540,'gif_bytes':(out/f'{clip}.gif').stat().st_size})
if a.clip:
 existing=json.loads((out/'manifest.json').read_text()) if (out/'manifest.json').exists() else []
 manifest=[v for v in existing if v['name']!=a.clip]+manifest
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest,indent=2))
