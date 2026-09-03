# Shopping list - discrete delta-sigma vinyl ADC

The list to take into the DTU component shop, for **one complete stereo
converter**: power board, digital board, and two copies of the channel board.

Verified 2026-09-02 against the three artworks actually being milled
(`power/`, `channel_l/`, `digital/`) and against the shop stock list
(`dtu_component_shop.csv`, 1464 lines). Every shop code below is present in
that list by exact part number and category. It agrees line for line
with the generated `bom.md`; this file adds what that one only mentions in
prose: sockets, headers, shunts, standoffs and the Pi cable, and it says which
shelf each item is on.

**Need** is what the boards take. **Grab** adds a small spare margin, because a
1 % resistor dropped on the floor or a logic chip zapped at bring-up should not
cost a second trip.

## Resistors - shelf "E96 Standard", 1/4 W through-hole

Ask for them by the shop's own code in the first column.

| Shop code | Value | Need | Grab | Where |
|---|---|---:|---:|---|
| 4R75 | 4.75 Ω | 1 | 2 | power R1 (pump post-filter) |
| 1K00 | 1.00 kΩ | 2 | 4 | channel R20 |
| 2K21 | 2.21 kΩ | 2 | 4 | channel R37 |
| 5K90 | 5.90 kΩ | 2 | 4 | channel R28 |
| 8K25 | 8.25 kΩ | 4 | 6 | channel R29, R30 |
| 10K0 | 10.0 kΩ | 8 | 10 | power R2-R5, channel R31, R32 |
| 10K5 | 10.5 kΩ | 2 | 4 | channel R24 |
| 13K0 | 13.0 kΩ | 4 | 6 | channel R25, R26 |
| 14K7 | 14.7 kΩ | 4 | 6 | channel R22, R23 |
| 20K5 | 20.5 kΩ | 2 | 4 | channel R21 |
| 22K1 | 22.1 kΩ | 6 | 8 | channel R33, R35, R36 |
| 165K | 165 kΩ | 2 | 4 | channel R34 |
| 255K | 255 kΩ | 2 | 4 | channel R27 |

13 values, 41 resistors.

## Trimmer - shelf "Trimmer"

| Shop code | Need | Grab | Where |
|---|---:|---:|---|
| 47K trimmer | 2 | 2 | channel RV20, input level |

The footprint on the board is a 3-pin 2.54 mm in-line row. Check the shop's
47K trimmer has that pin arrangement before leaving the counter.

## Capacitors

| Shop code | Shelf | Need | Grab | Where |
|---|---|---:|---:|---|
| 100n | Ceramic | 23 | 26 | decoupling on every IC, all boards |
| 220p | Ceramic | 6 | 8 | channel C22, C23, C24 (integrators) |
| 1n5 | Ceramic | 2 | 4 | channel C21 |
| 2u2 | **Film** | 2 | 2 | channel C20 (input coupling) - film, not electrolytic |
| 10µF | Electrolytic | 1 | 2 | power C4 |
| 220µF | Electrolytic | 2 | 3 | power C5, C6 (pump reservoir and filter) |
| 470µF | Electrolytic | 1 | 2 | power C1 (+5 V reservoir) |

Any voltage rating the shop has is fine: nothing here sees more than 5 V.
The 2u2 film footprint assumes a 10 mm lead pitch and an 11 x 6.3 mm body.
Measure the shop's part; if it differs the footprint changes, not the part.

## Diodes - shelf "Schottky"

| Shop code | Need | Grab | Where |
|---|---:|---:|---|
| 1N5817 | 2 | 4 | power D1, D2 (charge pump) |

## ICs

| Shop code | Shelf | Package | Need | Grab | Where |
|---|---|---|---:|---:|---|
| TL072 | Linear | DIP-8 | 5 | 6 | power U2 (reference), channel U20, U22 (integrators) |
| LM311 | Linear | DIP-8 | 2 | 3 | channel U21 (comparator) |
| 74HC04 | 74HC CMOS Logic | DIP-14 | 2 | 3 | channel U24 (1-bit DAC gates) |
| 74HC74 | 74HC CMOS Logic | DIP-14 | 2 | 3 | channel U23 (retiming flip-flop) |
| 74HCT132 | 74HCT Logic | DIP-14 | 1 | 2 | digital U3 (clock input buffer) - **HCT, not HC** |
| 74HC157 | 74HC CMOS Logic | DIP-16 | 1 | 2 | digital U6 (L/R interleave mux) |
| 74HC4040 | 74HC CMOS Logic | DIP-16 | 1 | 2 | digital U4 (clock divider) |
| 74HC4049 | 74HC CMOS Logic | DIP-16 | 1 | 2 | digital U8 (5 V to 3.3 V level shift) |
| 74HC244 | 74HC CMOS Logic | DIP-20 | 1 | 2 | power U1 (charge pump driver) |

U3 must be the **74HCT132**: its TTL-level input threshold is what lets the
board accept a 3.3 V oscillator or the Pi's 3.3 V GPCLK0. A 74HC132 will not
do. The shop stocks both, so read the label.

## DIP sockets - shelf "IC Socket"

Every IC is socketed, and so is the oscillator can.

| Shop code | Need | Grab | For |
|---|---:|---:|---|
| DIP8 Socket | 8 | 9 | 5 x TL072, 2 x LM311, 1 x oscillator can |
| DIP14 Socket | 5 | 6 | 2 x 74HC04, 2 x 74HC74, 74HCT132 |
| DIP16 Socket | 3 | 4 | 74HC157, 74HC4040, 74HC4049 |
| DIP20 Socket | 1 | 1 | 74HC244 |

## Connectors - shelves "Header" and "Terminal"

| Shop code | Need | Where |
|---|---:|---|
| 2 pol skrueterminal | 2 | channel J20, line in (one per channel) |
| Header Male (straight strip) | 1 strip | cut into: 3 x 1x3 (J1 clock select, J21 Q select on each channel) and 1 x 1x8 (J2 to the Pi) |
| Jumper (shunt) | 3 | J1, and J21 on each channel board |

The Q-select shunt on J21 is the only thing that makes a channel board left or
right: pins 1-2 is LEFT, pins 2-3 is RIGHT.

## Not in the shop - order these

The shop's list has none of the following. They go on one order together.

| Item | Qty | Notes |
|---|---:|---|
| **6.144 MHz crystal oscillator can**, DIP-8 footprint, 5 V or 3.3 V | 1 (+1 spare) | X1. The one part the whole design depends on: the Pi's GPCLK0 as a substitute costs about 3 dB of SNR. Full-size or half-size can both drop into the DIP-8 socket. |
| **2x8 stacking headers, 2.54 mm** | 4 sets | The board-to-board bus (J3, J4, J7 x2). One plain female socket for the top board, one long-pin male for the bottom, two pass-through stacking headers for the middle. The shop's "Double Male" and "Female Header" strips can stand in for top and bottom, but nothing it stocks does the pass-through middle pair. |
| **M3 x 11 mm standoffs** | 16 | Four per board gap and mount. Confirm the length against the stacking header you actually order. |
| **M3 screws and nuts** | 16 + 16 | For the standoffs. |
| **Female-to-female jumper wires, 8 way** | 1 set | J2 to the Pi's GPIO header. Any 20 cm Dupont set does it. |
| RCA phono sockets | 2 | Optional. The board has screw terminals; fit RCA only if the phono stage's cable ends that way. |

## Consumables to have on the bench

- Hookup wire for the wire links the single-sided boards need. `PCB-NOTES.md`
  counts roughly fifty hand-soldered joints across the set.
- Solder. Ground pads join the pour solid with no thermal relief, so plan on
  a 40 W+ iron and give each ground joint a couple of extra seconds.

## Totals

| | Lines | Pieces |
|---|---:|---:|
| Components on the boards | 37 | 109 |
| Sockets, shunts, header strip, terminals | 8 | 24 + 1 strip |
| To order | 5 to 6 | see above |
