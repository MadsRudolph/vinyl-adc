# Vinyl ADC rev D: bring-up log, 20 October 2026

Rev D is the converter redrawn as one four-layer Raspberry Pi HAT and made by
PCBWay, who sponsored the boards. It replaces the four isolation-milled,
single-sided boards that were brought up in September
([bring-up log, 16–18 September](bringup-log-2026-09.md)); those boards and
their measurements are the baseline every figure here is compared with. Design
record: [design-notes §12](design-notes.md), board files:
[`hardware/kicad/rev_d/`](../hardware/kicad/rev_d/README.md).

## 1. The board

| | Milled stack (rev A/B, Sept 2026) | Rev D (PCBWay, Oct 2026) |
|---|---|---|
| Boards | 4 (power, channel L, channel R, digital), stacked on a bus | 1 |
| Layers | 1, isolation-milled on a Roland SRM-20 | 4: signal / solid GND / split +5V·+5VA / signal |
| Size | four × 100 × 100 mm | 140 × 136 mm, Pi 4 underneath as a HAT |
| Links | dozens of wire jumpers, component-side joints no iron reaches | none: plated through-holes and vias |
| Material, finish | FR-4 copper-clad, bare copper | 1.6 mm FR-4, 1 oz copper, HASL lead-free, solder mask both sides, silkscreen |
| Pi connection | flying leads to the header | 2×20 socket on the copper side |
| Power | bench supply for the best figures; the Pi's 5 V cost 6–11 dB | the Pi's 5 V, with an analog island (+5VA) behind its own choke |

Five boards were ordered on 25 September; one is assembled. Every part is
through-hole and socketed, as on the milled boards.

## 2. The Pi side

Capture needed no change: rev D uses the same I²S pins (GPIO18/19/20) with the
Pi as clock consumer, so the overlay, the consumer-mode service and the ripper
ran as they were. What rev D adds on the header is new software:

- **`pi/panel.py`**, started by the ripper: REC (GPIO17) while a side records,
  BUSY (GPIO27) while identifying, cutting or encoding, READY (GPIO22) when idle
  with the card open, blinking while the ADC sends no clocks. SW2 (GPIO23) is
  the dashboard's Record / Stop on a button, for what the needle detector cannot
  judge: a very quiet lead-in, or a side to end now rather than after 60 s of
  silence. It is ignored while there are no clocks, so a press cannot start a
  side the moment the clocks appear.
- **SW1** is the power button: `dtoverlay=gpio-shutdown` in `config.txt`, and
  GPIO3 wakes a halted Pi by itself.
- **`pi/gpclk.py`** starts the Pi's GPCLK0 on GPIO4 (§3).

## 3. First power-up: no clocks from the crystal

The Pi booted, the I²S pins went to consumer mode, and no undervoltage was
flagged, but the ripper reported no clocks. Sampled 200 times each, PI_BCLK sat
high, PI_LRCLK and PI_DIN low: nothing toggled. The fault was on the board's
master clock (the 6.144 MHz crystal oscillator), upstream of the divider chain.
It is not yet diagnosed.

The board was designed for this: J1 (CLK SEL) can feed the clock buffer from the
Pi's GPCLK0 instead, a fallback that had never been needed. `pi/gpclk.py`
programs GPCLK0 from PLLD (750 MHz ÷ 122.0703 = 6.144000 MHz, MASH 1) and puts
GPIO4 on ALT0. With J1 moved, all three I²S lines toggled and the ripper went
straight to idle in stereo.

**Every figure below was taken on the Pi's clock.** GPCLK0's fractional divider
carries about 1 ns of jitter, which design-notes §5 puts at a ~68 dB ceiling for
the converter; the crystal is specified below 50 ps. They are therefore a
conservative view of rev D, not its final numbers.

## 4. Both channels, first time

| At the bitstream, no music | Milled stack (Sept) | Rev D, left | Rev D, right |
|---|---|---|---|
| Verdict | third-order shaping | Healthy | Healthy |
| One-density | 0.4957 | 0.4983 | 0.4960 |
| Mean run of identical bits | 1.35 / 1.36 | 1.40 | 1.37 |
| Noise shaping, 30→80 kHz | +68.1 / +68.6 dB/dec | +66 dB/dec | +68 dB/dec |

The milled stack took two days and two hidden faults before its right channel
modulated (the −5 V supply reaching the board only through solder wicked up an
unplated hole, then a short on the feedback DAC). Rev D's two channels were
healthy, and matched, from the first capture.

The first look showed the left channel 14 dB noisier than the right. Its input
trimmer RV20 was simply at the end of its travel; once set with a record
playing (`pi/levels.py`), both channels peak at **−6.0 dBFS** (95th percentile
of the 100 ms peaks over 45 s, the September method; September's setting was
−6.9 dBFS) with 17 dB crest factor and no sign of clamping.

## 5. Milled against fabricated: the idle floor with the turntable connected

The same measurement as [test-and-verification §5b](test-and-verification.md):
stylus up, platter stopped, the whole chain powered (turntable → Pro-Ject phono
stage → converter), trimmers set for music peaks near −6 dBFS, ten seconds of the
ripper's own 48 kHz output. The turntable's ground wire goes to the phono stage
only, as in September; rev D's J3 tonearm terminal is unused (J4 fitted).

| 20 Hz–20 kHz | Milled stack, **bench supply**, crystal | Rev D, **Pi 5 V**, **Pi clock** |
|---|---|---|
| Total | −55.8 / −56.1 dBFS | **−57.5 / −57.3 dBFS** |
| A-weighted | −61.1 / −62.1 dBFS | **−69.7 / −68.2 dBFS** |
| 20–200 Hz | −58.6 / −58.4 | −57.6 / −57.6 |
| 200 Hz–2 kHz | −68.6 / −69.4 | **−73.7 / −73.6** |
| 2–20 kHz | −59.6 / −60.6 | **−76.5 / −70.5** |
| 50 Hz line | — | −57.9 / −57.9 dBFS |
| Music peak to floor, unweighted | 48.9 / 49.2 dB | **51.4 / 51.3 dB** |
| Music peak to floor, A-weighted | 54.2 / 55.2 dB | **63.7 / 62.2 dB** |

Rev D runs on the supply that cost the milled stack 6–11 dB, and on a clock with
about twenty times the crystal's jitter, and still delivers **about 8 dB more
A-weighted range** from the record to the file. Everything above 200 Hz is
5–17 dB lower.

**What is left is mains hum.** L/R coherence is 1.00 at 50 Hz and falls to
0.29, 0.18 and 0.06 in the three bands above it: the 50 Hz line is the same
voltage on both channels, so it comes in through a shared ground, while the rest
of the floor is independent per channel. The 50 Hz line alone (−57.9 dBFS) is
now essentially the whole unweighted total. That is the source chain's ground,
not the converter; the J3 terminal and its lift network exist for exactly this
experiment (§8).

## 6. The needle detector, re-derived

The ripper's start and stop thresholds are absolute dBFS, so they belong to one
noise floor and one trimmer setting. On rev D the detector's treble-weighted level
reads **−69.5 dBFS** with the stylus up (p10–p90 within 0.2 dB), against −57.6 in
September. With the same margins above the floor as before, `start_db` moved
from −55 to **−67** and `stop_db` from −54 to **−66** (`stop_seconds` stays 60).
`gap_db` (−63, used to find the gaps between tracks) is still the September value
and must be re-checked on a full side.

## 7. Erratum: the clip LEDs are lit all the time

Both red CLIP LEDs stayed on regardless of level. This is a design error in rev D,
not an assembly fault, and it follows from the schematic:

| U12 (LM339) pin | Function | Net on the board |
|---|---|---|
| 5 / 4 | comparator 1 + / − | INT1_L / TH_P (+2.02 V) |
| 7 / 6 | comparator 2 + / − | TH_N (−1.99 V) / INT1_L |

An LM339 output sinks when + < −, and sinking lights the LED. As wired,
comparator 1 sinks whenever INT1 < +2.02 V and comparator 2 whenever
INT1 > −1.99 V, i.e. both sink *inside* the window, which is always. The right
channel's pair (pins 8–11) is the same. The netlist gate `check_rev_d.py` had
been written to the same wrong wiring, which is why it passed.

Confirmed on the board: with U12 pulled from its socket, the 10 k pull-ups and
the 100 k recharge the stretch capacitors and both LEDs go dark, which also
proves the BC557s and the stretchers are sound.

- **Now:** U12 stays out. The Pi stands in: REC flashes for a second whenever a
  peak passes −0.3 dBFS, the threshold at which the dashboard already shows
  "■ CLIP" (`pi/panel.py`).
- **Rework, when wanted:** swap the two thresholds rather than the comparator
  inputs. With TH_P at −2 V and TH_N at +2 V the same pins form the correct
  window. R44 (VREF_P→TH_P) and R46 (VREF_N→TH_N) stand 12 mm apart; removing
  them and fitting two 22k1 resistors diagonally across their holes *from the
  solder side*, VREF_P→TH_N and VREF_N→TH_P, is invisible from the top.
- **Source:** `tools/rev_d_layout.py` now wires each section to sink outside the
  window, and the gate checks the corrected wiring; regenerated in a scratch copy,
  rev D and rev E both pass, and the as-built rev D fails on exactly these pins.
  The rev D files are left as built. **Rev E's production files still carry the
  error** and must be regenerated before it is ordered.

## 8. Open items

1. **The crystal oscillator.** Find why it did not start (Y1, the 74HCU04 at U9,
   J1), and repeat §5 on it: the GPCLK0 jitter is the largest known handicap in
   the numbers above.
2. **Converter-only floor:** inputs shorted, raw bitstream at 1.536 MHz, for the
   number that compares the boards directly (milled stack: −76.75 / −77.49 dBFS,
   test-and-verification §3).
3. **The AD3 audio plan** (`assembly/bench/run.py audio`) on rev D: dynamic
   range, THD, response, crosstalk, against the milled stack's 67.9 dB.
4. **Hum:** the turntable ground on J3, J4 fitted and lifted.
5. **`gap_db`** on a full side (§6).
6. **GPCLK0 at boot** while J1 stays on the Pi clock (`pi/gpclk.py` does not
   survive a reboot).
7. **U12:** the threshold swap (§7), then refit it. **Rev E:** regenerate.
