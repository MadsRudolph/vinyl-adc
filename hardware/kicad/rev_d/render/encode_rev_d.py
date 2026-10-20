"""Encode the rev D clip frames into GIF, MP4 and poster; run with Python 3.

    python3 hardware/kicad/rev_d/render/encode_rev_d.py [--clip orbit|explode]

Reads build/frames/<clip>/0001..0072.png (from render_rev_d.py) and writes
media/showcase/rev-d/<clip>.gif (720x540), <clip>.mp4 (960x720, H.264),
<clip>-poster.png (960x720) and manifest.json. Same format as the enclosure
clips in media/showcase/: 12 fps, 6 s seamless loops.
"""
from pathlib import Path
import argparse, hashlib, json, shutil, subprocess

here = Path(__file__).resolve().parent
root = here.parents[3]
out = root / 'media/showcase/rev-d'
CLIPS = ('orbit', 'explode')
POSTER = {'orbit': '0001.png', 'explode': '0037.png'}

p = argparse.ArgumentParser()
p.add_argument('--clip', choices=CLIPS)
a = p.parse_args()
out.mkdir(parents=True, exist_ok=True)

manifest = []
for clip in ([a.clip] if a.clip else CLIPS):
    frames = here / 'build/frames' / clip
    stamp = json.loads((frames / 'render.json').read_text())
    assert stamp['board_glb_sha256'] == hashlib.sha256((here / 'build/board.glb').read_bytes()).hexdigest(), \
        'frames are from another board export'
    assert stamp['frames'] == 72
    missing = [i for i in range(1, 73) if not (frames / f'{i:04}.png').exists()]
    if missing:
        raise SystemExit(f'{clip}: missing {len(missing)} frames')
    src = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-framerate', '12',
           '-i', str(frames / '%04d.png'), '-frames:v', '72']
    subprocess.run(src + ['-c:v', 'libx264', '-preset', 'slow', '-crf', '20', '-pix_fmt', 'yuv420p',
                          '-movflags', '+faststart', str(out / f'{clip}.mp4')], check=True)
    # One palette for the whole loop; Bayer dither keeps frame-to-frame noise
    # (and so the file size) down on the dark gradient backdrop.
    subprocess.run(src + ['-filter_complex',
                          'fps=12,scale=720:-1:flags=lanczos,split[a][b];'
                          '[a]palettegen=max_colors=128:stats_mode=full[p];'
                          '[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle',
                          '-loop', '0', str(out / f'{clip}.gif')], check=True)
    g = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-count_frames', '-show_streams',
                                            '-of', 'json', str(out / f'{clip}.gif')]))['streams'][0]
    assert g['nb_read_frames'] == '72' and g['width'] == 720 and g['height'] == 540
    assert abs(float(g['duration']) - 6) < 0.02
    shutil.copy2(frames / POSTER[clip], out / f'{clip}-poster.png')
    m = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json',
                                            str(out / f'{clip}.mp4')]))['streams'][0]
    assert m['nb_frames'] == '72' and m['width'] == 960 and m['height'] == 720
    manifest.append({'name': clip, 'seconds': 6, 'width': 960, 'height': 720, 'fps': 12,
                     'mp4_bytes': (out / f'{clip}.mp4').stat().st_size,
                     'gif_width': 720, 'gif_height': 540,
                     'gif_bytes': (out / f'{clip}.gif').stat().st_size})

mf = out / 'manifest.json'
old = json.loads(mf.read_text()) if mf.exists() else {}
clips = {c['name']: c for c in old.get('clips', [])}
clips.update({c['name']: c for c in manifest})
stills = []
for name in ('hero', 'top', 'detail'):
    f = out / f'{name}.png'
    if f.exists():
        s =json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json',
                                                str(f)]))['streams'][0]
        stills.append({'name': name, 'width': s['width'], 'height': s['height'], 'png_bytes': f.stat().st_size})
data = {'clips': [clips[c] for c in CLIPS if c in clips], 'stills': stills}
mf.write_text(json.dumps(data, indent=2) + '\n')
print(json.dumps(data, indent=2))
