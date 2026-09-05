# Vinyl ADC showcase animations

Three seamless six-second loops, rendered from `enclosure/vinyl_adc_enclosure.blend`:

| Clip | View |
| --- | --- |
| `orbit` | Full 360° product orbit with the enclosure assembled |
| `assembly` | Explode and reassemble the original PCB stack and lid |
| `electronics` | Isolated four-board stack with a gently moving camera |

Each clip includes a 960 × 720, 24 fps H.264 MP4, a 560 × 420, 10 fps looping GIF, and a PNG poster. MP4 files have fast-start metadata and no audio. Use MP4 for the portfolio and GIF for GitHub README images. Exact sizes are in `manifest.json`.

Open `index.html` to preview all three clips. The gallery includes playback controls and respects reduced-motion preferences.

## GitHub README

```markdown
![Vinyl ADC exploded assembly](media/showcase/assembly.gif)
```

## Portfolio

Copy the chosen MP4 and poster to the website's public assets directory, then adjust these paths to match:

```html
<video controls muted loop playsinline preload="metadata"
       poster="/media/vinyl-adc/orbit-poster.png"
       aria-label="Vinyl ADC enclosure rotating through a full turn"
       style="width:100%;height:auto">
  <source src="/media/vinyl-adc/orbit.mp4" type="video/mp4">
</video>
```

For automatic playback, use the gallery's reduced-motion-aware script. Keep controls available so visitors can pause movement. Assets are prepared locally; this does not publish changes to madsrudolph.dev.

## Reproduce or edit

From the repository root, using Blender 5.2 and FFmpeg:

```sh
blender -b enclosure/vinyl_adc_enclosure.blend --python enclosure/animation/render_showcase.py
python enclosure/animation/encode_showcase.py
```

Pass `-- --preview` for two preview frames per clip or `-- --clip orbit` to render one clip. The render script generates editable `orbit.blend`, `assembly.blend`, and `electronics.blend` files under `enclosure/animation/`. Frame 145 matches frame 1; exports stop at frame 144 to avoid a duplicated loop endpoint. Generated blend files and intermediate PNG sequences are ignored by Git; the source scripts and final exports are tracked.

The original CAD file is preserved. The showcase copies use studio lighting, a slate floor, and a simplified transparent acrylic shader. The electronics shot hides enclosure and wiring for visibility; it is an illustrative exploded view, not an assembly instruction.
