# Production files: vinyl_adc_rev_c (one board, 4 layers)

Exported by `hardware/kicad/tools/export_rev_c.sh` from
`hardware/kicad/rev_c/vinyl_adc_rev_c.kicad_pcb`. Upload
`vinyl_adc_rev_c-gerbers.zip` as-is; the loose files in `gerbers/` are the
same set.

| Parameter | Value |
|---|---|
| Layers | 4: `F.Cu` signals, `In1.Cu` solid GND, `In2.Cu` solid +5V, `B.Cu` signals |
| Size | 170 x 120 mm, rectangular, no slots |
| Thickness | 1.6 mm FR-4, 1 oz copper outer and inner |
| Smallest track / clearance | 0.3 mm / 0.2 mm (supply nets 0.6 mm) |
| Vias | 0.7 mm pad, 0.35 mm drill, 3 of them |
| Holes | all through-hole parts, 0.8-1.3 mm PTH; 4 x 3.2 mm and 4 x 2.7 mm mounting holes NPTH |
| Surface finish | HASL lead-free is fine (everything is hand-soldered through-hole) |
| Mask / silk | any colour; silkscreen both sides (the back carries only the Pi socket's outline) |
| Drill files | Excellon, PTH and NPTH separate, absolute origin, mm |
| Gerber format | RS-274X, Protel extensions, no X2 attributes, silk subtracted from mask |

`vinyl_adc_rev_c-layers.pdf` is one page per layer for a visual check,
`vinyl_adc_rev_c-schematic.pdf` the sheet the board was built from, and the
two PNGs are KiCad's 3D renders of each side. The bill of materials is
`docs/bom-rev-c.md`.
