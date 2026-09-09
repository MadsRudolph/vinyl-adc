# 6.144 MHz oscillator module

A coaster-sized single-sided board that **fills the X1 DIP-8 socket** on the
already-built digital board, standing in for the unobtainable oscillator can.
Electrically it *is* the can: a Pierce oscillator (74HCU04 + the found 2-pin
6.144 MHz crystal) whose buffered output leaves on the socket's OUT pin.
The same `blk_pierce` block draws this module, the rev B digital board and
the `sim_i_pierce` testbench, so the three cannot drift apart.
Design rationale, and the two values that are load-bearing (R_s = 2k2, and
*unbuffered* 74HCU04): `docs/design-notes.md` §5.

## Parts

| Ref | Value | Package | Shop? |
|---|---|---|---|
| U9 | **74HCU04** (unbuffered!) | DIP-14 + socket | order (pin-identical to 74HC04) |
| Y1 | 6.144 MHz crystal | HC-49 | in hand |
| R10 | 1M | axial | shop |
| R11 | 2k2 | axial | shop (2k21 E96 fine) |
| C16, C17 | 27p | ceramic disc | shop (22p/33p also fine) |
| C9 | 100n | ceramic disc | shop |
| J1 | 4 machined pins | at DIP-8 positions 1/4/5/8 | shop pin strip |

A buffered 74HC04 in U9's socket is an emergency substitute only — verify
with a scope that the output is 6.144 MHz and not ~30 MHz before trusting it
(the buffered gate can oscillate through the crystal's holder capacitance).

## Build order

1. Solder the four **J1 pins first**, from the component side, pointing
   **down**: machined round pins (cut from a strip) at pad positions
   1, 4, 5 and 8 — the corners of the pad field. Pads 2/3/6/7 stay empty.
   Seat them in a spare DIP-8 socket while soldering so they cure straight.
2. Low parts next (R10, R11, C16, C17, C9), then the DIP-14 socket, then Y1.
3. Plug in the 74HCU04 last.

## Fitting it to the digital board

- **Pad 1 of the module goes over pin 1 of the X1 socket** (the socket's
  notch end). Both are marked; a 180° misfit puts +5 V on the clock output.
- The module body extends **east and south** from the socket, over the
  board's emptiest quarter. Its north edge sits just clear of the CLK-SEL
  jumper — J1 on the digital board must be jumpered **1-2** (crystal) with
  the module in place, so fit that jumper first.
- Height: the module rides ~8 mm above the digital board on the socket +
  pin stack. Its far east edge passes close over U3's socket; if it touches,
  stack a second machined-pin socket under the module as a spacer.
- The enclosure lid was drawn for a bare digital board — check the module
  clears the acrylic before closing it, and bench-test with the lid off
  until then.

## Bench check

Power the digital board, jumper J1 1-2, and scope the socket's pin 5 (or
U3 pin 1): a 5 V square wave at **6.144 MHz ±0.01 %**. The 74HC4040 then
gives BCLK 3.072 MHz on Q0 and LRCLK 48 kHz on Q6 as in the testing guide.

## Files

- `vinyl_adc_osc.kicad_sch` — drawn by `hardware/kicad/tools/osc_module_layout.py`
- `vinyl_adc_osc.kicad_pcb` — placed by `vinyl_adc_osc.place.py`, routed
  single-sided: 19/19 connections, zero wire bridges, zero vias, DRC clean
- `production/vinyl_adc_osc/` — mill Gerbers + Excellon drill, laser silk DXF
