# Vinyl ADC lattice enclosure GIFs

Three seamless six-second loops show the revised 105 mm tall enclosure:

| GIF | View |
| --- | --- |
| [orbit.gif](orbit.gif) | Full 360° product orbit with the assembly closed |
| [assembly.gif](assembly.gif) | Explode and reassemble the PCB stack and acrylic lid |
| [electronics.gif](electronics.gif) | Isolated four-board stack with a gently moving camera |

GIFs are 720 × 540 at 12 fps. Each also has a 960 × 720 PNG poster and a 12 fps H.264 MP4 fallback. The gallery and portfolio display the GIFs, with a still-image toggle and reduced-motion handling. Sizes are recorded in [manifest.json](manifest.json).

[Print files and instructions](../../enclosure/README.md) · [Interactive 3D model](https://madsrudolph.github.io/vinyl-adc/)

These are CAD visualizations, not photographs of a finished print. The taller stack uses illustrative 23 mm inter-board spacers. The electronics view hides the enclosure and wiring for clarity.

## Reproduce

```sh
blender --factory-startup -b enclosure/vinyl_adc_enclosure.blend -noaudio --gpu-backend opengl --python enclosure/animation/render_showcase.py
python enclosure/animation/encode_showcase.py
```

Use `-- --preview` for frames 1 and 37 of each clip, or `-- --clip orbit` for one clip. Editable animation scenes are generated under `enclosure/animation/`; intermediate frames and scenes are ignored by Git. Frame 73 matches frame 1; export stops at frame 72 to avoid a duplicate endpoint. The encoder verifies the source scene hash, frame count, GIF dimensions and duration so mixed or stale frame sequences cannot be published accidentally.
