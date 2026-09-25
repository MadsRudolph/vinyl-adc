# Rev E: rev D's circuit in SMD parts, one 4-layer HAT

Rev D is the through-hole HAT built from the DTU shop's drawers. Rev E is
the same circuit in surface-mount parts from any distributor (or PCBWay's
assembly service), on a board a fifth the size of rev D's first layout.
The sheet is drawn by `tools/rev_e_layout.py`, which calls rev D's block
functions unchanged and only swaps footprints and four part numbers, and
`tools/check_rev_d.py vinyl_adc_rev_e` runs rev D's own gate on it: the
netlist is the reference sheet plus exactly rev D's additions, nothing
inside the modulator loop moved.

## What changed from rev D, part by part

| Rev D (THT) | Rev E (SMD) | Why this part |
|---|---|---|
| axial resistors | 0805, 1 % thin film | hand-solderable, every value in stock everywhere |
| disc ceramics | 0805: C0G for 27 p / 220 p / 1n5, X7R for 100 n | the integrator and filter caps must not change value with voltage |
| 2u2 MKT film (C20, C60) | **same MKT film, through-hole** | 2.2 µF does not exist in C0G, and an X7R in series with the audio is where a ceramic's voltage coefficient would be heard |
| 10 µ electrolytics | 10 µ X5R 25 V, 1206 | lower ESR for the flying cap; the stretch timers run ~0.6 s instead of ~1 s |
| 220 µ / 470 µ radial | 220 µ 16 V 6.3 × 7.7, 470 µ 10 V 8 × 10 SMD cans | the smallest stock cans at those values |
| DIP ICs | SOIC (74HC244 in SOIC-20W) | same pinouts |
| BC547 / BC557 TO-92 | BC847 / BC857 SOT-23 | pinouts differ, so the SYMBOL changes too; the blocks connect by pin name |
| 1N4148 / 1N5817 / 1N4003 | 1N4148W SOD-123 / SS14 SMA / S1M SMA | |
| shop 10 µH 3 A axial chokes | Bourns SRR1260-100M | shielded, 27 mΩ; the island's 2.3 kHz corner unchanged |
| HC-49 crystal | HC-49/SMD | same 6.144 MHz, same load caps |
| 5 mm LEDs, 6 mm THT buttons | 0805 LEDs, 6 × 6 SMD tact switches | |

Connectors stay through-hole: the screw terminals, the pin headers and the
Pi socket take the mechanical load. BOM: `docs/bom-rev-e.md`.

## Floorplan

```
      x 0..62                               x 62..118  (over the Pi)
      y  0..33   CHANNEL L  J20 RV20 -> U20 U22 U21     DIGITAL  Y1 U9 U3 U4
                            U24 U23  J22                          U6 U8 J1 J5 U11
      y 33..42   J3 + lift network | U12 clip windows  PUMP     L1 C1 U1 U10 ...
      y 42..75   CHANNEL R  (channel L, moved 42 down)  ISLAND   L2 C18 U2 ref
      y 75..88   LED drivers, then the front row: 8 LEDs ........ SW1 SW2
```

118 × 88 mm. The same geography as rev D: inputs on the left edge, the
digital column over the Pi's header, power at the far end from the inputs,
the eight LEDs and two buttons along the front edge, the Pi's USB/Ethernet
over the top (back) edge. Channel R is a rigid copy of channel L, 42 mm
lower: the same circuit gets the same copper.

## How it was placed and routed

Not by hand coordinates and not by a wire-length auto-placer.
`tools/hat_place.py` takes anchors from `tools/rev_e_floor.py` (connectors,
the LED row, the Pi socket, starting points for the ICs), puts every other
part where its nets want it, and anneals: weighted wire length, plus a
strong pull of every decoupling cap to the supply pin it serves, plus a
prohibitive cost on any +5V/+5VA pad landing in the other In2 plane. No
courtyards may overlap. `tools/hat_board.py` builds the board around it
(outline, holes, Pi socket, planes, netclasses, references, legends).

`tools/hat_route.py rev_e` then routes with FreeRouting on F.Cu/B.Cu,
gives every SMD plane pad its own stub and via where the routed copper
leaves room (`tools/fanout.py`, outward from the part), and drops a via
onto any plane "island" DRC still reports — pads FreeRouting joined with
a track but never took to the plane (`tools/fanout.py --islands`). It
retries FreeRouting costs until DRC is clean. The order matters:
FreeRouting 2.4.1 connects most SMD plane pads itself, but on a board that
already carries any copper it throws a NullPointerException in its router
and never returns, so the fan-out cannot go in first.

## Stackup and rules

`F.Cu` signals, `In1.Cu` solid GND, `In2.Cu` split (+5V under the digital
and pump blocks, x ≥ 62 and y < 60; +5VA everywhere else), `B.Cu` signals.
L2 stands across the split with a pad in each plane. Tracks 0.25 mm,
supplies 0.4 mm, clocks 0.3 mm, clearance 0.2 mm, vias 0.6/0.3 mm, all
comfortably inside PCBWay's standard 4-layer process.

## Regenerating it

```bash
cd hardware/kicad
tools/hat_pipeline.sh rev_e
```

## Where it stands (25 September 2026)

| | |
|---|---|
| parts | 177 + 7 mounting holes; all SMD on the top side except the connectors, C20/C60 and the Pi socket (copper side) |
| gates | ERC clean; `check_rev_d.py vinyl_adc_rev_e` OK; placement with no courtyard overlaps and every +5V/+5VA pad in its own plane; DRC schematic parity: the same 234 cosmetic items as rev D |
| copper | 1726 segments, 4.3 m of track (2.9 m top, 1.5 m bottom), 277 vias (about 100 FreeRouting's, the rest the plane fan-out); DRC: 0 violations, 0 unconnected, 0 warnings |
| production | `production/vinyl_adc_rev_e/`: Gerbers, drills, IPC-D-356, layer and schematic PDFs, renders, STEP and `vinyl_adc_rev_e-pos.csv` (pick-and-place, top side) |

Not built. Everything rev D's README lists as not done applies here too.

