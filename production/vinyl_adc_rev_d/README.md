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
| Silkscreen | text 0.9-1.4 mm, every stroke >= 0.15 mm (PCBWay minimum); white on green (or any) |
| Drill files | Excellon, PTH and NPTH separate, absolute origin, mm |
| Gerber format | RS-274X, Protel extensions, no X2 attributes, silk subtracted from mask |
| Electrical test | yes, against `vinyl_adc_rev_d.d356` |

`vinyl_adc_rev_d-layers.pdf/` holds one PDF per layer for a visual check,
`vinyl_adc_rev_d-schematic.pdf` the sheet the board was built from, the
two PNGs are KiCad's 3D renders of each side, and `vinyl_adc_rev_d.step`
the mechanical model for the enclosure. The bill of materials is
`docs/bom-rev-d.md`; the design record is `docs/design-notes.md` §12 and
`hardware/kicad/rev_d/README.md`.

## Layer order for the order form

PCBWay asks for the copper stack of a 4-layer job (put it in the remark
field as well):

| # | File | Layer |
|---|---|---|
| L1 | `vinyl_adc_rev_d-F_Cu.gtl` | top, signals |
| L2 | `vinyl_adc_rev_d-In1_Cu.g1` | inner 1, solid GND plane |
| L3 | `vinyl_adc_rev_d-In2_Cu.g2` | inner 2, +5V / +5VA power planes (split) |
| L4 | `vinyl_adc_rev_d-B_Cu.gbl` | bottom, signals |

Vias are tented (covered by mask) on both sides. The Pi's 2x20 socket J2
goes on the BOTTOM (copper) side; its outline and pin-1 mark are on the
bottom silkscreen.

## Checked before ordering (25 September 2026)

DRC: 0 violations, 0 unconnected, 0 warnings, zones refilled. Every
silkscreen line and text stroke widened to 0.15 mm (the library
footprints draw 0.12 mm, below PCBWay's minimum), every reference on the
silkscreen except J20's (it carries the LINE IN L label), connector and
jumper legends (LINE IN L/R, TONEARM GND, TRIM L/R, BOND, J1 1-2 XTAL /
2-3 GPCLK, J6 WR), polarity marks on every electrolytic, diode and LED,
pin-1 notches on every DIP. Drills 0.40 mm (vias) and 0.75-1.52 mm
(components), all KiCad library sizes for the leads they take. Not yet
fitted to these footprints on any board so far: the two 10 uH chokes (15.24 mm
axial), the 6 mm buttons, the TO-92s, the 5 mm LEDs, the 1N4148s and the
2x20 / 2x5 headers.

