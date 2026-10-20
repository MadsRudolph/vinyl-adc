# Vinyl ADC rev D renders

Renders of rev D, the converter as one 4-layer, through-hole Raspberry Pi HAT
(140 × 136 mm, fabricated by PCBWay):

| File | View |
| --- | --- |
| [hero.png](hero.png) | Three-quarter view from the front-left: line inputs, the front LED row and the two buttons |
| [top.png](top.png) | Straight top-down view with the legend readable; the Pi's USB/Ethernet end shows over the back edge |
| [detail.png](detail.png) | Close-up of the front edge: the REC, BUSY and READY LEDs and the SHUTDOWN button |
| [orbit.gif](orbit.gif) | Full 360° turntable of the HAT with the Pi 4 plugged in underneath |
| [explode.gif](explode.gif) | The HAT lifting off the Pi's 40-pin header and seating again |

GIFs are 720 × 540 at 12 fps, seamless six-second loops. Each also has a 960 × 720 PNG poster and a 12 fps H.264 MP4. Sizes are recorded in [manifest.json](manifest.json).

These are CAD renders made in Blender (Cycles) from the KiCad board file. They are not photographs of the assembled board. What differs from the real board:

- Soldermask and legend colours are PCBWay's default green and white. The order left the colour open. The pads are HASL lead-free, as ordered.
- Every LED is lit in the colour its Value field gives (CLIP L/R and REC red, CLK, +5VA and READY green, −5V and BUSY yellow).
- The resistors are drawn as blue metal-film bodies with no colour bands. The terminal blocks are drawn blue. The ICs are drawn without their sockets.
- KiCad 10 has no 3D model for the vendored bornier-2 footprint (J3, J20, J60), so the stock Phoenix MKDS 1,5/2-5.08 model stands in for it. Pitch and position are the same.
- The Raspberry Pi 4 model is "Raspberry Pi 4B" from the [FreeCAD parts library](https://github.com/FreeCAD/FreeCAD-library/tree/master/Computing/SingleBoardComputers/Raspberry/Raspberry%20Pi%204B), licensed [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/) and attributed there to its contributors (commit 71fae7e, Charles Fox). The model has no surface detail, so its materials are approximate. It sits 11 mm below the HAT (8.5 mm socket plus the 2.5 mm header body).

## Reproduce

```sh
hardware/kicad/rev_d/render/export_model.sh
blender -b --factory-startup --python hardware/kicad/rev_d/render/render_rev_d.py
python3 hardware/kicad/rev_d/render/encode_rev_d.py
```

`export_model.sh` exports the board to GLB with `kicad-cli` (tracks, pads, silkscreen, soldermask and component models). It works from a scratch copy of the board file that has the terminal-block model substituted. It also downloads the Pi STEP once, checks its SHA-256, and tessellates it through `kicad-cli`. `render_rev_d.py` writes the three stills straight into this folder. It renders the orbit and explode frames into `hardware/kicad/rev_d/render/build/frames/`. The encoder turns those frames into the GIFs, MP4s, posters and `manifest.json`. Use `-- --shot hero` (repeatable) to render one shot, or `-- --preview` for half-size stills and frames 1 and 37 of each clip. Cycles uses OptiX, CUDA or HIP when a GPU is present and falls back to the CPU with fewer samples. The full set takes about 18 minutes on an RTX 3060. Frame 73 matches frame 1, so export stops at frame 72 to avoid a duplicate endpoint. Scenes (`build/<shot>.blend`), frames and the downloaded model are ignored by Git.
