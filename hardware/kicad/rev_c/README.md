# Rev C: the whole converter on one fabricated 4-layer board

The four CNC-milled boards exist because of one number: 0.84 mm between two
DIP pads, which nothing could pass on the single-sided mill (see
`../PCB-NOTES.md`). A fab removes that constraint, and with it the reason to
split, so rev C is the reference sheet built as it was drawn -- one board,
170 x 120 mm, four layers, every part through-hole and socketed exactly as
before, with the Raspberry Pi 4 plugged into the underside on its own 40-pin
header. The measured rev B stack (docs/bringup-log-2026-09.md 13a) is the
baseline this board will be compared against.

## What changed against the reference sheet, and nothing else

`tools/check_rev_c.py` welds three two-pin parts through, drops the Pi
connector on both sides, and requires the remaining node partition to be
identical to `../reference/vinyl_adc.kicad_sch`. It passes with 99 nets each
side. The three parts, and the fourth change it cannot see:

| Change | Why | Where it came from |
|---|---|---|
| U2 is an LM358, not a TL072 | VREF_N must reach -2.5 V from a pump rail that sags to -3.8 V; a TL07x stops 2 V above V- | bench 16 Sept, design-notes 10b' |
| FB1 ferrite bead on the 5 V inlet | the board is now powered from the Pi's 5 V pins and the Pi's switching noise was measurably worse than the bench supply | bringup log, open item 4 |
| R12, R13 = 475 R in BCLK and LRCLK | the Pi's I2S pins are outputs until a stream is opened, so two drivers meet on those lines at boot | bringup log 6.3 |
| J2 is the Pi's 2x20 header | no pigtail, no stacking bus, one box | this revision |

Everything else -- the modulator, the quantiser, the clock tree, the
values, the Pierce oscillator from rev B -- is the same drawing, called from
the same block functions in `../tools/vinyl_adc_layout.py` (`board_rev_c`).

## Stackup and rules

`F.Cu` signals, `In1.Cu` solid GND, `In2.Cu` solid +5V, `B.Cu` signals.
Through-hole pads reach both planes on their own, so GND and +5V need no
tracks at all: the router only ever sees the 66 other nets. Tracks 0.3 mm,
supplies (-5V, +3V3, PUMP, VREF_P, VREF_N) 0.6 mm, clearance 0.2 mm, vias
0.7/0.35 mm -- twice PCBWay's 4-layer minimums throughout. Thermal reliefs
on the planes, because every lead is hand-soldered and a lead into a solid
inner plane sinks the iron.

## Floorplan

```
  x 0..112                              x 114..170
  y   4..56   CHANNEL L  J20 RV20 -> U20 U22 U21 / U23 U24     DIGITAL  Y1 U9 J1
                                                                         U3 U4
  y  60..112  CHANNEL R  J60 RV60 -> U60 U62 U61 / U63 U64              U6 U8
                                                               inlet     FB1 C1 C2
                                                               POWER     U1 C4 D1 D2
                                                                         U2 R2-R5 C5 R1 C6
```

Each channel reads left to right like its schematic band; the integrator
resistor clusters sit between the packages they feed, the DAC gates and the
retiming flip-flop below, next to the summing resistors they drive. The
digital column is beside the Pi socket so MCLK, the I2S trio and the level
shifter are short, and the power section is at the far end of the board from
the inputs. `tools/rev_c_board.py` holds the numbers.

## The Pi, and the one fact about it worth writing down

The Pi sits UNDER the board, HAT-style, on a 2x20 female header soldered to
the copper side at (117.5, 32.5); its four holes are at (117.5, 3.5),
(166.5, 3.5), (117.5, 61.5), (166.5, 61.5). Its USB-C/HDMI edge is flush
with the board's right edge and its USB/Ethernet end overhangs the TOP edge
by 20 mm -- the same 65 mm reach the HAT specification uses, because those
connectors stand 16 mm proud and would hit the board.

Handedness: seen from above, pin 1 (3V3) is the row NEARER the Pi's centre,
pin 2 (5V) the row along the Pi's edge, both at the SD-card end. The first
attempt put the Pi's SD end at the bottom and its header edge on the left,
which reads naturally and is a mirror image -- no rotation of a back-side
socket could land pins 1, 2 and 39 on it. `place_pi_socket()` searches the
four rotations and refuses the placement rather than guessing, which is what
caught it. Verified against KiCad's own `Raspberry_Pi_Zero_Socketed`
footprint: header centre on the hole line, holes 29 mm either side.

The Pi's PoE header (8.5 mm, near its Ethernet jack) lands under about
(117-122, 4-8), which is exactly the top end of the socket; nothing else is
there. A plain 8.5 mm HAT socket touches it; an 11 mm extended-height socket
does not. Use the taller one if in doubt.

The Pi powers the board: 73 mA at 5 V through FB1 (bringup log 13). The
board is the I2S master, as before.

## Regenerating it

```bash
cd hardware/kicad
PYTHONPATH=<dir holding the pcbnew sitecustomize shim> REV_C_SCRATCH=/tmp/rev_c \
    tools/rev_c_pipeline.sh
```

That runs, in order: `vinyl_adc_layout.py vinyl_adc_rev_c` (the sheet),
`kicad-cli sch export netlist`, `check_rev_c.py` (the gate),
`pcb_netlist_json.py` (from the kicad-laser-pcb skill), `rev_c_board.py`
(placement, planes, rules), `route_rev_c.py` (FreeRouting on four layers,
retried with different via and direction costs until DRC shows zero
unconnected), `export_rev_c.sh` (Gerbers, drills, PDFs, renders into
`production/vinyl_adc_rev_c/`) and `make_bom.py rev_c` (`docs/bom-rev-c.md`).

Two things about the router. FreeRouting 1.9.0 has no headless mode and
2.3.0 needs Java 25; on Hyprland the script installs a session-only window
rule (`hyprctl eval 'hl.window_rule(...)'`) that sends its window to a
silent special workspace, and reads `hyprctl clients` afterwards to confirm
it went there. And it is deterministic for identical input: a run that
leaves a net open is not retried with the same costs but with the next pair
in the list. On this board the first two pairs left VREF_P open by one
segment; the third (against 2.5, via 40) closed everything with 3 vias.

## Where it stands (22 September 2026)

| | |
|---|---|
| parts | 111 + 8 mounting holes, all through-hole, every IC socketed |
| nets | 68 on the board (99 on the sheet before the planes swallow GND and +5V and the Pi's NC pins) |
| copper | F.Cu 1597 mm, B.Cu 1955 mm, 3 vias, GND and +5V as planes |
| gates | ERC clean (42 lib-symbol-mismatch warnings, same as every sheet here); `check_rev_c.py` OK; `sch_score` passes except the 55 deliberately NC pins it counts as floating; DRC 0 unconnected, 2 silk-over-copper warnings (references clipped by the mask, cosmetic) |
| production | `production/vinyl_adc_rev_c/`, see its README for the order parameters |

Not done: the enclosure. `enclosure/build_enclosure.py` models the
100 x 100 mm stack and must be rebuilt for a 170 x 120 board with the Pi
underneath and 20 mm of Pi beyond the top edge. Not done either: building
and measuring it, which is the point of the exercise -- the milled stack's
67.9 dB dynamic range is the number to beat, and whether a ground plane
moves it is the question.
