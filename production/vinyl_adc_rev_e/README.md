# Production files: vinyl_adc_rev_e (SMD Raspberry Pi HAT, one board, 4 layers)

Exported by `hardware/kicad/tools/export_rev_d.sh rev_e` from
`hardware/kicad/rev_e/vinyl_adc_rev_e.kicad_pcb`. Upload
`vinyl_adc_rev_e-gerbers.zip` as-is; the loose files in `gerbers/` are the
same set. `vinyl_adc_rev_e.d356` is the IPC-D-356 netlist for the fab's
electrical test.

| Parameter | Value |
|---|---|
| Layers | 4: `F.Cu` signals, `In1.Cu` solid GND, `In2.Cu` +5V / +5VA planes (split), `B.Cu` signals |
| Size | 118 x 88 mm, rectangular, no slots |
| Thickness | 1.6 mm FR-4, 1 oz copper outer and inner (PCBWay 4-layer standard stackup) |
| Smallest track / clearance | 0.25 mm / 0.2 mm (supply nets 0.4 mm, clocks 0.3 mm) |
| Vias | 0.6 mm pad, 0.3 mm drill (tented) |
| Holes | connectors and C20/C60 0.8-1.3 mm PTH, vias 0.3 mm; 3 x 3.2 mm (M3, board) and 4 x 2.7 mm (M2.5, Pi) mounting holes NPTH |
| Surface finish | ENIG (flat pads for the SOICs and 0805s); HASL lead-free works for hand assembly |
| Mask / silk | any colour; silkscreen both sides (the back carries the Pi socket's outline and orientation legend) |
| Min silk text | 0.8 mm |
| Drill files | Excellon, PTH and NPTH separate, absolute origin, mm |
| Gerber format | RS-274X, Protel extensions, no X2 attributes, silk subtracted from mask |
| Electrical test | yes, against `vinyl_adc_rev_e.d356` |

`vinyl_adc_rev_e-layers.pdf/` holds one PDF per layer for a visual check,
`vinyl_adc_rev_e-schematic.pdf` the sheet the board was built from, the
two PNGs are KiCad's 3D renders of each side, and `vinyl_adc_rev_e.step`
the mechanical model for the enclosure. The bill of materials is
`docs/bom-rev-e.md`; the design record is `docs/design-notes.md` §13 and
`hardware/kicad/rev_e/README.md`.

## Assembly

Parts are on the top side only (plus the Pi's 2x20 socket on the copper
side, through-hole). For PCBWay assembly send `docs/bom-rev-e.md` and
`vinyl_adc_rev_e-pos.csv` (top side, mm, origin at the board's top-left
corner as drawn); mark J2 (the Pi socket) as hand-fitted on the bottom.
The through-hole parts (J3, J20, J60, RV20/RV60 headers, J1, J4, J5, J6,
J22, J62, C20, C60) can be fitted by them or by hand afterwards.
