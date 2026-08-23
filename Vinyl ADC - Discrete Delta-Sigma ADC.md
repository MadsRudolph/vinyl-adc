# Vinyl ADC

A stereo audio ADC built from jelly-bean parts with **no ADC chip anywhere in
it**, to digitise vinyl. It permanently replaces the borrowed Focusrite
Scarlett Solo in the record-ripping chain.

**Status:** 🟡 Schematic complete, and now simulated block by block —
next is the PCB, then the decimator on the Pi

```
Pro-Ject Debut Carbon --> Phono Box --> [THIS BOARD] --> Pi "mediaplayer" --> FLAC --> Jellyfin
                                         analog -> PDM      CIC + FIR in software
```

## How it works

Each channel is a **third-order continuous-time delta-sigma modulator**: three
op-amp integrators, a comparator, a flip-flop that retimes the decision, and a
1-bit DAC made of resistors feeding back into all three integrators. The output
is a 1-bit stream at 1.536 MHz. Nothing turns that stream into samples on the
board — the decimation is done in software on the Pi, deliberately, because
that half is the DSP coursework.

```
in --> [ INT1 ]-->[ INT2 ]-->[ INT3 ]--> comparator --> D-FF --> 1-bit out
          ^          ^  ^       ^                          |
          |          |  +-------+ resonator                |
          +----------+------------------ 1-bit DAC --------+
```

Both channels are **bit-interleaved onto a single data line**, which makes the
Pi see an entirely ordinary 48 kHz / 32-bit stereo I2S stream — the most
boring, best-supported mode it has. Each 64-bit frame happens to carry exactly
32 left bits and 32 right bits, which is exactly one output sample per channel.
Software treats the capture as a raw 3.072 Mbps bit river and de-interleaves it.

**Expected performance: 68–70 dB SNR**, matched on purpose to vinyl's own
noise floor. There is no point chasing 100 dB for a source that has 60.

## Why third order

The design is constrained to what the DTU component shop stocks, and the shop's
fastest op-amp is an **LF356 at 5 MHz** with an **LM311** as the only decent
comparator. That caps the clock at 1.536 MHz, where a second-order loop manages
only 53 dB — well short of the target. The third integrator is the price of the
parts list. `docs/design-notes.md` has the numbers behind every such decision.

## Layout

| Path | What |
|---|---|
| `hardware/kicad/vinyl_adc.kicad_sch` | the whole converter on one page — **open this to read the circuit** |
| `hardware/kicad/vinyl_adc_common.kicad_sch` | board 1: power, reference, quantiser |
| `hardware/kicad/vinyl_adc_channel_l.kicad_sch` | board 2, **milled twice**: one modulator channel |
| `hardware/kicad/vinyl_adc_digital.kicad_sch` | board 3: clock, interleave, level shift, Pi header |
| `hardware/kicad/PCB-NOTES.md` | the boards: floorplans, pours, and what the mill dictates |
| `hardware/kicad/vinyl_adc.pdf` | rendered, for reading away from KiCad |
| `hardware/kicad/tools/vinyl_adc_layout.py` | draws all five sheets; re-run to regenerate |
| `hardware/kicad/tools/check_intent.py` | asserts the netlist is the intended circuit |
| `hardware/kicad/tools/check_split.py` | asserts the four boards, welded at their ribbons, ARE that circuit |
| `hardware/kicad/tools/make_bom.py` | BOM, checked against the shop stock list |
| `hardware/kicad/sim/` | eight SPICE testbenches — open a `.kicad_pro` and press Run |
| `hardware/kicad/sim/README.md` | what the simulations found, and the traps they hit |
| `sim/` | the modulator simulator and the scripts that chose every value |
| `docs/design-notes.md` | the decision record — read this before changing anything |
| `docs/bom.md` | bill of materials |
| `docs/HANDOFF-original.md` | the brief this was built from |

Regenerate everything:

```bash
cd "hardware/kicad" && py -3.13 tools/vinyl_adc_layout.py && py -3.13 tools/check_intent.py && py -3.13 tools/check_split.py && py -3.13 sim/tools/sim_layout.py
```

### It is four boards, from three designs

One copper layer with a ground plane on it has no room left for a second net
that has to reach everywhere, and 2.54 mm DIP pitch leaves 0.84 mm between
pads — too narrow for any track this process can cut, so everything routes
*round* its package rather than between the pins. As one board it needed 45
hand-soldered wire links. Split, it needs a fraction of that:

```
   common  ---12-way---  digital          the two channel boards are ONE
     |  |                                 artwork, milled twice
   14-way 14-way
     |  |
  channel L, channel R
```

`docs/design-notes.md` §11 has the measurements and the argument, including
the one thing that changed as a result: the modulator's feedback loop now
crosses a ribbon, which costs 0.5 ns against a 200 ns delay the loop already
compensates for.

## What the simulations say

`hardware/kicad/sim/` is eight KiCad testbenches — one per block plus the whole
loop — generated from the board's *own* layout functions, so each bench is the
same drawing as the board rather than a re-creation of it. 51 design checks and
34 model checks, all passing. The full account is in
[`sim/README.md`](hardware/kicad/sim/README.md) and `docs/design-notes.md` §10;
the short version:

- **The charge pump was wired backwards.** Both Schottkys had anode and cathode
  swapped, which made it a voltage doubler: the net called `-5V` simulated at
  **+3.4 V**. Every other check on this board passed it, because a diode wired
  the wrong way round is still a connected diode. Fixed.
- **The loop survives a vinyl click** — 40 µs at three times full scale, and it
  comes back. That is the thing the whole design leans on.
- **The negative rail is −3.87 V, not −4.1 V**, which leaves the TL074's
  *guaranteed* input common-mode floor at +0.13 V while every virtual earth
  sits at 0 V. It works typically; the margin the design assumed is not there.
  This is the one finding worth acting on at bring-up.
- **The I2S setup margin is 145 ns**, not the 163 ns on paper — ripple-counter
  skew eats the difference. Still four times what the Pi needs.

## Before changing a resistor

Two values in here are load-bearing in non-obvious ways:

- **The integrator state scaling** is chosen so the op-amps saturate at the
  right level. A 1-bit third-order loop that overloads never recovers on its
  own — one vinyl click would latch it at a rail until power-cycled — and that
  saturation is the only thing that rescues it. Re-run `sim/verify.py` if you
  touch the rails or the scaling. (SPICE says the window is wider than it
  looks: recovery is insensitive to where the clamp lands over 2.0–4.5 V.)
- **`Rk0`** (DAC to comparator) is excess-loop-delay compensation. Without it
  the LM311's 200 ns costs 8 dB and most of the overload margin. Measured on
  `sim_e_quantiser` at |k0| = 0.228 against the design's 0.225.

`Rin` is the safe one: it sets full scale only, is not in the feedback path,
and is the right knob if the phono stage turns out louder or quieter than the
~1 Vrms peaks assumed here.

## Still to do

- **Cut the boards.** Gerbers and drill files come out of
  `export_production.ps1`; `hardware/kicad/PCB-NOTES.md` has the commands and
  the two footprint assumptions to check against the real parts first (the
  2u2 film cap's lead pitch and the trimmer body).
- **Order the parts the shop does not stock**: a 6.144 MHz oscillator can, and
  the IDC box headers, sockets and ribbon for the three board-to-board links.
  Everything else is in the shop. The can is worth ordering rather than
  substituting the Pi's GPCLK0, whose jitter would become the dominant noise
  source.
- **Software**: CIC decimator (order ≥4) + FIR compensation + DC block on the
  Pi, then into the existing `pw-record` → sox → FLAC pipeline.
