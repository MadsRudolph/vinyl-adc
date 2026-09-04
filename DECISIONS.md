# DECISIONS — Vinyl ADC product rendering, enclosure and site

Branch `agent/claude`. Everything below was derived from the repository on
2026-09-04; nothing in `hardware/kicad/` was modified.

> **Shared working tree.** While this ran, another agent was working in the
> same checkout (`C:\Users\Mads2\vinyl-adc`): it switched the checkout to
> `agent/antigravity`, re-exported the per-board GLBs over mine at 23:29
> (without copper/silk), added its own `render/render.py`,
> `render/vinyl_adc_render.blend`, `render/vinyl-adc-*.png`,
> `site/images/` and `hardware/export/vinyl-adc-board.{glb,step}`, and
> committed copies of my files onto *its* branch (commits `997fba8`,
> `1fa38e4`, author "Mads"). To keep `agent/claude` clean and self-consistent
> I re-ran the whole pipeline in a separate `git worktree` of `agent/claude`
> and committed from there; every number below was reproduced identically in
> that clean run. Files on `agent/antigravity` are not mine and are not
> referenced here.

## 1. What was found in the repo (and what the task text assumed)

- The task says "the .kicad_pcb". There are **three** board designs and
  **four** physical boards: `power` (tier 1), `channel_l` milled twice (tiers
  2 and 3, the R copy jumpered as R), `digital` (tier 4). All three are
  **100.0 × 100.0 mm**, outline from KiCad (20, 20) to (120, 120), with four
  **Ø3.2 mm** mounting holes at (26, 26), (114, 26), (26, 114), (114, 114) —
  identical on every board, so the stack shares one set of standoffs.
- `hardware/kicad/PCB-NOTES.md` describes an older split (160 × 120 common
  board, 190 × 145 channel, 140 × 100 digital, IDC headers J3–J7). **It is
  stale**: the boards in the repo are the 100 × 100 four-tier set with a
  2×8 pin header (`J3`/`J4`/`J7`, value "2x8 BUS") at the same position on
  every board. The `.kicad_pcb` files were used as the source of truth.
- The README claims "Gold RCA phono jacks". **No RCA, USB, LED, switch or
  barrel-jack footprint exists on any board.** The externally reachable parts
  are exactly:
  - `J20` "LINE IN L" — `TerminalBlock_bornier-2_P5.08mm` on the channel
    board at (115.80, 100.75) rot 90°, body flush with the +X board edge;
  - `RV20` "47k" — gain trimmer on the channel board at (92.14, 108.42)
    rot −90°, body flush with the −Y (front) board edge;
  - `J2` "TO PI GPIO" — `PinHeader_1x08_P2.54mm_Vertical` on the digital
    board at (60.22, 115.60) rot 90°, at the front edge.
  The enclosure therefore has 2 LINE IN windows, 2 trimmer access holes and
  one Pi-ribbon notch, and nothing else. RCA/USB are listed as **TBD** on the
  site rather than invented.
- Power: there is no power connector on the power board. +5 V arrives from
  the Pi over the 8-way `J2` header (README pinout, pins 2/4), the −5 V rail
  is made on-board by the 74HC244 charge pump. So the Pi ribbon is the only
  cable leaving the box.
- Specs used on the site come from README + `docs/design-notes.md`:
  3rd-order CT CIFB ΔΣ, 1.536 MHz modulator clock (OSR 32), 6.144 MHz
  oscillator can, 24-bit / 48 kHz output after CIC + FIR on the Pi,
  ≈68 dB SNR (simulated), full scale 2.47 Vrms. Nothing else was asserted.

## 2. Tools actually found

| Tool | Location | Used for |
|---|---|---|
| kicad-cli 10.0.4 | `C:\Program Files\KiCad\10.0\bin\kicad-cli.exe` (not on PATH) | GLB + STEP export of the three boards |
| KiCad python 3.11.5 | `C:\Program Files\KiCad\10.0\bin\python.exe` | not needed (own s-expression parser instead) |
| Blender 4.4.3 | `C:\Program Files\Blender Foundation\Blender 4.4\blender.exe` (not on PATH) | scene build, renders, .blend, assembly GLB |
| Blender 5.1.1 | `C:\Program Files\Blender Foundation\Blender 5.1\blender.exe` | only to read the old `enclosure/vinyl_adc_enclosure.blend` (saved by 5.2.x; 4.4 cannot open it) |
| OpenSCAD 2021.01 | `C:\Program Files\OpenSCAD\openscad.com` (not on PATH) | parametric enclosure → STL |
| Python 3.11.9 | `python` (Windows Store launcher, on PATH) | all scripts; **no third-party modules** (numpy/trimesh not installed, none needed) |
| GPU | NVIDIA GeForce RTX 3060 | Cycles via OptiX, ~11 s / frame at 24 samples |

**Blender MCP server: not reachable** (`Cannot connect to Blender at
localhost:9876`) — Blender was not running with the add-on. Fell back to
headless `blender.exe -b -P render\build_scene.py` as the task allows. That is
also the better choice for reproducibility: the whole scene is rebuilt from
the exports on every run.

## 3. Board export — placeholders

`kicad-cli pcb export glb --subst-models --include-tracks --include-pads
--include-zones --include-silkscreen --include-soldermask` resolved every
stock 3D model except one:

| Footprint | Refs | Why no model | Placeholder used in the render |
|---|---|---|---|
| `TerminalBlock_bornier-2_P5.08mm` (vendored in `hardware/kicad/lib/`) | `J20` on both channel tiers | The `.kicad_mod` references `${KICAD9_3DMODEL_DIR}/TerminalBlock.3dshapes/…step`; that folder was removed from KiCad 10's library and the variable is undefined | Box 7.5 × 10.0 × 10.6 mm from the footprint's F.Fab outline (local x −2.46…7.54, y ±3.75) at KiCad body centre (115.80, 98.21), green, two Ø3 screw heads on top, two Ø2.6 wire-entry recesses on the +X face |
| `WireLink_TH` | `WL1A/B` (power), `WL1A/B`…`WL9A/B` (digital) | Single-pad footprints for hand-soldered jumper wires; no model by design | Ø0.8 mm red insulated wire from pad A to pad B, 1.2 mm above the board, with vertical legs |
| `MountingHole_3.2mm_M3` | `H1–H4` on every board | No body — correct | none (hole is cut in the board body by the export) |

Hardware that is not in KiCad at all but is required for the assembly to
exist, all modelled as simple bodies and stated here:

- 16 × **M3 × 18 mm male–female brass hex standoffs** (5.5 mm A/F), four per
  tier; the male thread of each passes through the board into the female top
  of the one below (tier 1 into the base inserts). 18 mm was chosen from the
  measured heights, see §4.
- 4 × M3 heat-set inserts in the floor bosses (Ø4.0 × 7 mm hole).
- 4 × M3 × 6 socket-head screws through the lid into the top standoffs.
- 4 × **16-way IDC sockets** on the 2×8 bus headers + one 16-way ribbon
  daisy-chained up the back (README: "16-pin ribbon bus"). Socket body
  24.3 × 8.6 × 9 mm seated 2.5 mm above the board → 11.5 mm top.
- 8-way Dupont housings (14 mm tall) on `J2` and a flat 8-way ribbon leaving
  through the front notch.

Board thickness 1.6 mm (KiCad default; the GLB body spans y = −1.6…0). Lead
protrusion on the solder side 1.7 mm (GLB bbox min).

## 4. Stack and enclosure geometry (derived, not chosen)

All numbers are produced by `enclosure/make_params.py` from
`hardware/export/board_geometry.json` (own parser over the `.kicad_pcb`) and
`hardware/export/board_heights.json` (glTF POSITION accessor extents of the
kicad-cli GLBs). Enclosure frame: origin at the outer bottom-left-front
corner, X right, Y toward the back, Z up;
`X = kx − 20 + 0.5 + 3`, `Y = (120 − ky) + 0.5 + 3`.

| Quantity | Value | Where it comes from |
|---|---|---|
| Tallest part, power board | 11.6 mm | 470 µF radial cap (GLB node bbox) |
| Tallest part, channel board | 11.6 mm | 2.2 µF film cap `C_Rect_L11.0mm_W6.3mm` |
| Tallest part, digital board | 10.13 mm | 2.54 mm pin headers |
| Tallest thing on any tier | 15.5 mm | IDC socket (11.5) + ribbon fold (4) |
| Required standoff | ≥ 17.2 mm | 15.5 + 1.7 mm leads of the board above |
| **Standoff** | **18 mm** (stock length) | → tier pitch 19.6 mm |
| Board tops Z | 10.6 / 30.2 / 49.8 / 69.4 | floor 3 + boss 6 + 1.6 + n·19.6 |
| Lid underside | 87.4 | 69.4 + 18 |
| **Outer size** | **107.0 × 107.0 × 90.4 mm** | 100 + 2·0.5 + 2·3; 87.4 + 3 |
| Cavity | 101.0 × 101.0 mm, 84.4 mm deep | spec: 0.5 mm clearance, 3 mm walls |

The old `enclosure/vinyl_adc_enclosure.blend` in the repo stacks the boards
on a 12.6 mm pitch inside a 144 × 144 × 65 box. Measured against the exports
that is physically impossible: an 11.6 mm capacitor under an 11 mm gap, and
no room at all for a socket on the bus header. The new stack is taller
(90.4 mm) because the parts are.

### Cutouts (each checked twice — see §6)

| Cutout | Wall | Driven by | Position (enclosure mm) | Size |
|---|---|---|---|---|
| LINE IN R window | +X | `J20` tier 2 | Y 19.295–31.295, Z 30.5–41.5 | 12 × 11 |
| LINE IN L window | +X | `J20` tier 3 | Y 19.295–31.295, Z 50.1–61.1 | 12 × 11 |
| GAIN R hole | −Y | `RV20` tier 2 | X 75.64, Z 35.2 | Ø 5 |
| GAIN L hole | −Y | `RV20` tier 3 | X 75.64, Z 54.8 | Ø 5 |
| Pi ribbon notch | −Y | `J2` tier 4 | X 40.45–64.77, Z 72.4–87.4 (open to top) | 24.3 × 15 |

Assumptions behind them:

- **Terminal block wire entry faces +X.** The bornier footprint's F.Fab
  outline has its extra line on the local +y face; with rot 90° that face
  points at the +X board edge (courtyard reaches x = 119.8 of 120), which is
  the only reading consistent with the designer putting it flush with the
  edge. Window = courtyard span (10.5 mm) + 0.75 mm each side, 11 mm tall
  from 0.3 mm above the board (bornier body ≈ 10.6 mm).
- **Trimmer is treated as side-adjust** (Bourns 3296X/Y style) with the
  screw on the face toward the front wall, axis 5 mm above the board, on the
  pin-row x (92.14). The board uses a `PinHeader_1x03_Horizontal` footprint
  for it, PCB-NOTES says 3296W (top-adjust) — **TBD on the real part**. If it
  is top-adjust, the two Ø5 holes are harmless and adjustment is done with
  the lid off.
- The Pi notch is open to the top edge (no bridge to print) and 1.5 mm wider
  than `J2`'s courtyard each side; the ribbon leaves at Z ≈ 83–85.
- Screw terminals are tightened **before** stacking the next tier (7.4 mm
  between the block top and the board above is not screwdriver room).

### Two-part design and printability

- **Base**: tray with 3 mm floor and walls, outer vertical edges R3, four
  Ø8 × 6 mm bosses with Ø4 insert holes. Prints floor-down with no supports:
  every wall is vertical, the notch is open-topped, and the two LINE IN
  windows are 12 mm bridges — ordinary FDM bridging, no support needed.
- **Lid**: 3 mm plate with a 2 mm × 4 mm locating lip that drops 0.25 mm
  inside the wall, four Ø3.4 through-holes with Ø6.5 × 2 counterbores, and
  the label engraved 0.6 mm. Print **upside down** (top face on the bed, lip
  up): no overhangs; the counterbores become 6.5 mm circular bridges.
- Material chosen for the renders: **matte charcoal PLA** (also printable in
  PETG as the README suggests); brass standoffs, black-oxide screws.

## 5. Rendering

- Blender 4.4.3 headless, **Cycles** (OptiX on the RTX 3060), 1920 × 1080,
  256 samples adaptive + OpenImageDenoise, AgX "Medium High Contrast".
- Neutral studio: 4 area lights (key/fill/rim/top), 12 m light-grey ground,
  world split with a Light Path node so the camera sees a seamless light
  cove while the lighting world stays dim.
- Cameras are placed by an exact frustum fit of the assembly bounding box
  (not a bounding sphere), so framing is reproducible.
- Shots: `hero.png` (3/4, f/8 DoF), `front_panel.png` (front + right walls,
  ribbon included), `line_in_side.png` (right wall), `exploded.png` (lid +45,
  tiers lifted 62/96/130/164 mm, cables hidden).
- `render/vinyl-adc-assembly.blend` is saved in the assembled state with all
  four cameras. Two GLBs are exported from the scene:
  `hardware/export/vinyl-adc-assembly.glb` (full product incl. enclosure and
  cables) and `hardware/export/vinyl-adc-board.glb` — the literal name the
  task asks for — which is the four-tier board stack with its standoffs and
  the placeholders of §3, no enclosure. The per-board KiCad exports are
  `vinyl-adc-{power,channel_l,digital}.{glb,step}`.

## 6. Verification performed

- `enclosure/check_stl.py`: both STLs are closed 2-manifolds —
  base 2204 tris, 0 open / 0 non-manifold edges, 137.84 cm³, bbox
  0…107 × 0…107 × 0…87.4; lid 14156 tris, 0 / 0, 36.99 cm³, Z 83.4…90.4.
  (OpenSCAD's own CGAL report also said "Simple: yes".)
- `enclosure/check_cutouts.py` re-reads the `.kicad_pcb` files with the
  parser, maps each connector courtyard into the enclosure frame and checks
  the cutout contains it; then evaluates a generalised winding number on the
  base STL at sample points inside each opening (must be open) and 1 mm
  outside it (must be solid), and at the boss rings / insert holes.
  Result: **ALL CUTOUTS VERIFIED** — coordinates checked:
  `J20` (115.80, 100.75) → X 95.3–103.3, Y 20.045–30.545 on tiers 2 & 3;
  `RV20` (92.14, 108.42) → X 75.64; `J2` (60.22, 115.60) → X 41.95–63.27;
  holes (26|114, 26|114) → (9.5|97.5, 9.5|97.5).
- `site/check_site.py`: all referenced files exist under `site/`, no
  external URLs, no `<script>`, all images 1920 × 1080 PNG. The page was also
  served with `python -m http.server` and fetched: `index.html` 200, all four
  `img/*.png` 200 `image/png` at their full sizes.

## 7. Things that failed on the way, and what was done instead

- Blender MCP unreachable → headless Blender (§2).
- `bpy.ops.object.shade_smooth()` fails headless ("context is incorrect") →
  `Mesh.shade_smooth()` + `Mesh.set_sharp_from_angle()` on the data.
- First lighting pass was ~3 stops over (Blender light watts are not physical
  at 0.1 m scale) and AgX turned everything pastel → lights cut to
  9/3.5/8/2.5 W, world 0.12, exposure 0.
- Children of a moved Empty report stale `matrix_world` until
  `view_layer.update()` → the exploded-view framing was wrong the first time.
- OpenSCAD 2021 writes ASCII STL by default; the cutout checker assumed
  binary → shared reader that accepts both; final STLs exported as binary
  (`--export-format binstl`).
- The KiCad 9 model variable for the terminal block cannot be pointed at a
  substitute: KiCad 10 ships no bornier model at all → placeholder (§3).
- The old `vinyl_adc_enclosure.blend` is a Blender 5.2 file; 4.4 cannot read
  it. It was inspected with 5.1 only to learn the previous tier pitch, and is
  not used by anything new.

## 8. Reproduce from a clean checkout (PowerShell)

```powershell
Set-Location <path-to>\vinyl-adc
$cli     = "C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"
$blender = "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"
$scad    = "C:\Program Files\OpenSCAD\openscad.com"

# 1. geometry from the boards + 3D exports (deliverable 1)
python hardware\export\extract_geometry.py
foreach ($b in 'power','channel_l','digital') {
  & $cli pcb export glb  --subst-models --include-tracks --include-pads --include-zones `
        --include-silkscreen --include-soldermask -f -o "hardware\export\vinyl-adc-$b.glb" "hardware\kicad\$b\vinyl_adc_$b.kicad_pcb"
  & $cli pcb export step --subst-models -f -o "hardware\export\vinyl-adc-$b.step" "hardware\kicad\$b\vinyl_adc_$b.kicad_pcb"
}
python hardware\export\glb_heights.py

# 2. enclosure (deliverable 2)
python enclosure\make_params.py
& $scad -o enclosure\vinyl-adc-base.stl --export-format binstl -D 'part="base"' enclosure\vinyl_adc_enclosure.scad
& $scad -o enclosure\vinyl-adc-lid.stl  --export-format binstl -D 'part="lid"'  enclosure\vinyl_adc_enclosure.scad
python enclosure\check_stl.py enclosure\vinyl-adc-base.stl enclosure\vinyl-adc-lid.stl
python enclosure\check_cutouts.py

# 3. renders, .blend and assembly GLB (deliverable 3) — ~1-2 min per frame on an RTX 3060
& $blender -b -P render\build_scene.py -- --samples 256
#    quick preview instead:  -- --engine BLENDER_EEVEE_NEXT --samples 16

# 4. site (deliverable 4)
New-Item -ItemType Directory -Force site\img | Out-Null
Copy-Item render\renders\*.png site\img\
python site\check_site.py
Start-Process site\index.html
```

`hardware/export/vinyl-adc-assembly.glb` and `vinyl-adc-board.glb` are
written by step 3. To view the site locally:
`python -m http.server 8765 --bind 127.0.0.1 --directory site` then open
<http://127.0.0.1:8765/>.
