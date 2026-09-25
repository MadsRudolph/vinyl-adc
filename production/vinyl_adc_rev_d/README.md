# Production files: vinyl_adc_rev_d (Raspberry Pi HAT, one board, 4 layers)

Exported by `hardware/kicad/tools/export_rev_d.sh` from
`hardware/kicad/rev_d/vinyl_adc_rev_d.kicad_pcb`. Upload
`vinyl_adc_rev_d-gerbers.zip` as-is; the loose files in `gerbers/` are the
same set. `vinyl_adc_rev_d.d356` is the IPC-D-356 netlist for the fab's
electrical test.

| Parameter | Value |
|---|---|
| Layers | 4: `F.Cu` signals, `In1.Cu` solid GND, `In2.Cu` +5V / +5VA planes (split), `B.Cu` signals |
| Size | 140 x 136 mm, rectangular, no slots |
| Thickness | 1.6 mm FR-4, 1 oz copper outer and inner (PCBWay 4-layer standard stackup) |
| Smallest track / clearance | 0.25 mm / 0.2 mm (supply nets 0.4 mm, clocks 0.3 mm) |
| Vias | 0.8 mm pad, 0.4 mm drill |
| Holes | all through-hole parts, 0.8-1.3 mm PTH; 3 x 3.2 mm (M3, board) and 4 x 2.7 mm (M2.5, Pi) mounting holes NPTH |
| Surface finish | HASL lead-free is fine (everything is hand-soldered through-hole); ENIG if offered |
| Mask / silk | any colour; silkscreen both sides (the back carries the Pi socket's outline and orientation legend) |
| Min silk text | 0.8 mm |
| Drill files | Excellon, PTH and NPTH separate, absolute origin, mm |
| Gerber format | RS-274X, Protel extensions, no X2 attributes, silk subtracted from mask |
| Electrical test | yes, against `vinyl_adc_rev_d.d356` |

`vinyl_adc_rev_d-layers.pdf/` holds one PDF per layer for a visual check,
`vinyl_adc_rev_d-schematic.pdf` the sheet the board was built from, the
two PNGs are KiCad's 3D renders of each side, and `vinyl_adc_rev_d.step`
the mechanical model for the enclosure. The bill of materials is
`docs/bom-rev-d.md`; the design record is `docs/design-notes.md` §12 and
`hardware/kicad/rev_d/README.md`.
