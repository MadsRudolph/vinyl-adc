# Rev D: the converter as a Raspberry Pi HAT, one 4-layer board

Rev C showed that a fab removes the reason the converter was ever split
into four milled boards. Rev D is the board designed *for* a fab — PCBWay
offered to make it — rather than merely allowed by one: 140 × 136 mm, four
layers, every part through-hole and (with one optional exception) from the
DTU shop, the Raspberry Pi 4 plugged into a 2×20 socket on the copper side
HAT-style. Rev C's placement was discarded; the circuit was not. Its SMD
twin, the same circuit in distributor parts on 118 × 88 mm, is rev E
(`../rev_e/`). The sheet
is drawn by the same block functions as the reference sheet and every
milled board, and `tools/check_rev_d.py` proves the netlist is the
reference partition plus exactly the additions listed here.

## What it adds, and why each thing is on the board

| Addition | Parts | Reason |
|---|---|---|
| **+5VA analog island** | L2 10 µH, C18 470 µ, C19 100 n | The DAC gates' supply *is* the reference (design-notes §6). The bench measured the Pi's 5 V costing 6–11 dB of idle noise (bringup log §8.5) and the charge pump's 30 mA at 192 kHz shared that rail. 10 µH into 470 µ is a 2.3 kHz corner, ~35 dB down at 192 kHz, with tens of milliohms of DCR — the rail stays stiff and ratiometric. Everything in the loop is on it: the TL072s, the LM311s' bias and pull-up, the retiming 74HC74s, the DAC 74HC04s, the LM358 reference. |
| **Second charge-pump driver** | U10 74HC244, C49 | The pump's 16 Ω output resistance is the drivers' on-resistance (§10b); sixteen buffers halve it and lift the negative rail ~0.5 V under load — the TL072 common-mode margin §10b called the one thing worth acting on. |
| **MCLK damper** | R14 33R2 | One driver, three loads over 100 mm; that edge's jitter sets the noise floor (§5). |
| **Stocked inlet choke** | L1 10 µH | Same part as L2, replacing rev C's ordered ferrite bead. |
| **Status LEDs** (front edge, left to right) | D6 CLIP L, D7 CLIP R, D5 CLK, D4 −5V, D3 +5VA, D8 REC, D9 BUSY, D10 READY | +5VA and −5V say the rails are up (the pump was a real bring-up fault). CLK is a diode pump off a spare 74HCT132 gate (U3B, C40, D11, D12, C41, R43, Q1): it lights only while LRCLK *toggles*. CLIP L/R are LM339 (U12) window comparators on the first integrators against ±2.0 V derived from the references (R44–R47), wired-OR, stretched to ~1 s (D13/D14, C42/C43, R49/R59) and switched by BC557s (Q2/Q3): the loop is about to latch (§4a) — back the trim off. REC/BUSY/READY are GPIO17/27/22 through 330 R, because the Pi's own LEDs are under the board. |
| **Buttons** | SW1 GPIO3, SW2 GPIO23 (R57/R58, C46/C47) | GPIO3 wakes a halted Pi, so SW1 is the power button with `dtoverlay=gpio-shutdown`; SW2 is for the ripper. |
| **HAT ID EEPROM** | U11 24LC32, R15, J6, C45 | On ID_SD/ID_SC, socketed, write-protected unless J6 is shorted. The one part the shop does not carry, and the one the board works without. |
| **Test points** | J22, J62 (INT1, INT2, INT3, CMP, DACP per channel), J5 (MCLK, LRCLK, DIN, VREF_P, VREF_N) | 2×5 headers with the odd column all ground: two probes on header pins, never DIP legs. |
| **Tonearm / chassis ground** | J3, R17 10R, C48 100 n, D15/D16 1N4003, J4 | Beside the line inputs. J4 shorted is the milled stack's hard bond; open, the lift network breaks the 50 Hz loop (bringup log open item 3). |

Design record with the numbers: `docs/design-notes.md` §12. Bill of
materials against the shop list: `docs/bom-rev-d.md` (four ORDER lines:
the crystal, the 74HCU04, the 2×20 HAT socket, and the optional EEPROM).

## Stackup and rules

`F.Cu` signals, `In1.Cu` solid GND, `In2.Cu` split — `+5V` under the
digital and pump blocks (x ≥ 84, y < 84), `+5VA` under everything else —
`B.Cu` signals. L2 stands across the split at the right edge so each of
its pads sits in its own plane; the ground plane is unbroken, so no
signal's return path crosses it. Tracks 0.25 mm, supplies (−5V, +3V3,
PUMP, VREF_P, VREF_N, PI_5V, TH_P, TH_N) 0.4 mm, clocks (CLK6M, MCLK,
BCLK, LRCLK, DIN and the PI_ trio) 0.3 mm, clearance 0.2 mm, vias
0.8/0.4 mm, 0.3 mm to the edge — at least twice PCBWay's 4-layer minimums
throughout, because every lead is hand-soldered. Thermal reliefs on both
planes for the same reason.

## Floorplan: the second layout

```
      x 0..84                                x 84..140  (over the Pi)
      y   0..46  CHANNEL L  J20 RV20 -> U20 U22 U21     DIGITAL  Y1 U9 / U8 U4 /
                            U24 U23  J22                          U6 U3, J1
      y  46..58  J3 + lift network | U12 clip | J5      PUMP     L1 C1 U1 U10
      y  58..104 CHANNEL R  (channel L, moved 58 down)  ISLAND   L2 C18 U2 ref
      y 104..136 LED drivers, then the front row: 8 LEDs ........ SW1 SW2
```

The first layout (176 × 146 mm, 23 September) put every passive in a row
of its own kind, first-fit, inside a band. It read tidily from across the
room and badly up close: a resistor sat wherever its row had room, not
next to the pin it serves, so its traces ran diagonally across the board,
and most of the board was empty. It was discarded on 24 September.

The second keeps the geography — inputs on the left edge, each channel
reading left to right as its schematic band does, the digital column over
the Pi's header, power at the far end from the inputs, LEDs and buttons on
the front edge — and places everything else from the netlist
(`tools/hat_place.py`, driven by `tools/rev_d_floor.py`): anchors for the
connectors and the front row, starting points for the ICs, then every
passive pulled to the pins it connects to and every decoupling cap to the
supply pin it serves, annealed with no courtyard overlaps and a
prohibitive cost on any +5V/+5VA pad in the wrong half of In2. Channel R
is a rigid copy of channel L, 58 mm lower: the same circuit on the same
copper. The three probe headers (J22, J5, J62) stand in one column beside
the socket. The charge pump's AC loop — drivers, flying cap C4, D1/D2, C5
— is weighted three times, so it stays in one tight group under the two
74HC244s. 26 % less board than the first layout.

## The Pi

Under the right-hand 56 mm on a 2×20 female header soldered to the copper
side at (87.5, 32.5); its holes are at (87.5, 3.5), (136.5, 3.5),
(87.5, 61.5), (136.5, 61.5). USB-C/HDMI edge flush with the board's right
edge, USB/Ethernet end 20 mm over the TOP edge — the back panel, where the
line inputs also are. The handedness (pin 1 is the inboard row at the SD
end, seen from above) is the one rev C verified against KiCad's own
`Raspberry_Pi_Zero_Socketed` footprint and its HAT template;
`place_pi_socket()` searches the four rotations and refuses the placement
rather than guessing. Use an 11 mm extended-height socket if the Pi's PoE
header touches the socket's top end.

The Pi powers the board through L1 (~100 mA at 5 V with the LEDs). The
board is the I2S master, as before. The GPIO map, including the buttons,
LEDs and EEPROM, is in `pi/README.md` §7.

## Regenerating it

```bash
cd hardware/kicad
tools/hat_pipeline.sh rev_d        # rev_e for the SMD twin
```

That runs, in order: `rev_d_layout.py` (the sheet), `kicad-cli sch export
netlist`, `check_rev_d.py` (the gate), `pcb_netlist_json.py` (from the
kicad-laser-pcb skill), then `hat_route.py` — `hat_board.py` (placement by
`hat_place.py` from `rev_d_floor.py`, planes, rules, legends) and
`route_4layer.py` (FreeRouting 2.4.1 on four layers, headless enough)
retried over cost pairs until DRC shows zero unconnected and no errors —
then `export_rev_d.sh` (Gerbers, drills, IPC-D-356, PDFs, renders, STEP
into `production/vinyl_adc_rev_d/`) and `make_bom.py rev_d`
(`docs/bom-rev-d.md`).

Legends only, on an already routed board (no reroute):
`python3 tools/hat_board.py rev_d --silk rev_d/vinyl_adc_rev_d.kicad_pcb`,
then `tools/export_rev_d.sh`.

pcbnew imports straight into this machine's `python3` (3.14); the one
thing missing there is `SwigPyIterator.next`, which the tools alias before
touching `GetTracks()`.

## Where it stands (25 September 2026)

| | |
|---|---|
| parts | 177 + 7 mounting holes, all through-hole, every IC socketed |
| nets | 104 on the board (98 on the sheet match the reference after the gate's welding and dropping; the rest are the additions') |
| gates | ERC clean; `check_rev_d.py` OK; placement with no courtyard overlaps and every +5V/+5VA pad in its own plane; DRC schematic parity has no wiring disagreement (its 234 items are 177 footprint names without the library prefix, 7 mounting holes with no symbol, and 50 NC pins the board leaves netless) |
| copper | second layout, routed by FreeRouting on F.Cu/B.Cu: 1020 segments, 5.0 m of track (2.2 m top, 2.8 m bottom), 13 vias; GND, +5V, +5VA as planes. DRC: 0 violations, 0 unconnected, 0 warnings |
| production | `production/vinyl_adc_rev_d/`, see its README for the order parameters |

Not done: the enclosure (`enclosure/build_enclosure.py` models the milled
stack and needs redrawing for the HAT with the Pi's ports on two edges);
SPICE benches for the clock-alive pump and the clip stretcher (diode-RC
circuits whose numbers are in the block docstrings — the TP headers make
them a two-probe bench check); software for the three GPIO LEDs and SW2 in
`ripper.py`. And building it, which is the point: the milled stack's
67.9 dB dynamic range (bringup log §13a) is the number to beat, and
whether the island and the stiffer pump move it is the experiment.
