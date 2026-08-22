# Discrete delta-sigma vinyl ADC — design record

Session of 2026-08-22. Supersedes the architecture sketch in `HANDOFF.md` where
the two disagree; every change is justified below with the number that forced it.

Everything here is reproducible: `sim/` contains the simulator and the scripts
that produced each result, and every quoted figure is the output of one of them.

---

## 1. What the DTU shop actually stocks — and what it costs us

Checked against `C:\Users\Mads2\KiCad\DTU-EKB-components\Components\parts\dtu_component_shop.csv`
(1464 lines, the same list the KiCad symbol/footprint libraries are built from).

**The handoff's candidate parts are mostly not there.** No NE5532. No OPA2134.
No crystal oscillators of any kind. No ICL7660/MAX1044 charge pump. No TL431 or
any precision voltage reference.

The complete set of op-amps in the shop, by gain-bandwidth:

| Part | GBW | Note |
|---|---|---|
| LF356 | 5 MHz | the fastest thing on the shelf |
| TL071/072/074, TL081/082/084 | 3 MHz | JFET input |
| LM301 | 1 MHz | externally compensated |
| MCP6002 | 1 MHz | rail-to-rail |
| LM358/324, LM741, OP07, LH0042 | ≤1 MHz | |

Comparators: **LM311** (200 ns) and LM339 (300 ns). Nothing faster.

That single table is what reshaped the design. **6.144 MHz as the modulator
clock is not reachable** — it would need ~25 MHz op-amps and a ~50 ns
comparator.

**Must be ordered** (flagged per the handoff's instruction):

- 6.144 MHz oscillator can — the only genuinely unavailable part, and §5 shows
  it is worth ordering rather than substituting.
- RCA phono sockets — the shop has screw terminals and Molex only.

---

## 2. Clock rate and modulator order

`sim/design_search.py`, `sim/clock_choice.py`.

With a 5 MHz op-amp and a 200 ns comparator the clock lands at **1.536 MHz**,
so **OSR = 32** for 48 kHz output. At that OSR:

| | peak SNR at −6 dBFS |
|---|---|
| 2nd order | 53 dB |
| **3rd order** | **70 dB** |

A 2nd-order loop misses the 65–75 dB target by a wide margin at OSR 32, so the
handoff's second-order plan does not survive the parts list. **Third order it
is.** The third integrator is the price of the shop's op-amp selection.

### What actually limits the clock

Not gain-bandwidth, as expected — **excess loop delay**:

| op-amp GBW | SNR | | loop delay | SNR | overload |
|---|---|---|---|---|---|
| ideal | 69.7 dB | | 0 ns | 69.3 dB | −3 dBFS |
| 10 MHz | 69.3 dB | | 65 ns | 69.7 dB | −3 dBFS |
| LF356 5 MHz | 70.0 dB | | 130 ns | 65.4 dB | −3 dBFS |
| **TL07x 3 MHz** | **70.6 dB** | | **202 ns** | **61.9 dB** | **−4.4 dBFS** |
| 1 MHz | 70.7 dB | | 326 ns | unstable | −12 dBFS |

GBW is a non-issue down to 1 MHz. The LM311's 200 ns costs 7 dB and most of the
overload margin — **and it is why the clock cannot go faster**: at 3.072 MHz
that same 200 ns is 61% of a clock period, which is unconditionally unstable.

**Consequence: the integrators are TL074, not LF356.** The fastest part in the
shop buys nothing, and the TL074's fourth section is needed anyway (§3).

### Excess-loop-delay compensation — one resistor, 8 dB

Adding a direct path from the DAC to the comparator input (weight `k0`)
recovers almost all of it:

| k0 | SNR at −6 dBFS | stable to |
|---|---|---|
| 0 (none) | 61.9 dB | 0.50 FS |
| −0.10 | 68.2 dB | 0.70 FS |
| **−0.225** | **69.8 dB** | **0.70 FS** |
| −0.50 | 65.7 dB | 0.50 FS |
| +0.20 | unstable | — |

---

## 3. Final loop

Third-order CIFB, continuous-time, 1-bit, with a resonator and ELD compensation:

```
a = [0.250, 0.320, 0.610]     integrator gains, normalised to fs
g = 0.0300                    resonator: int3 -> int2, spreads the NTF zeros
k0 = -0.225                   DAC -> comparator, ELD compensation
||NTF||inf = 1.48             Lee's rule for a 1-bit quantiser
```

**The resonator is worth 6.9 dB** (70.0 vs 63.1 dB re-optimised without it), so
it pays for the op-amp section it needs — and a TL074 quad supplies that section
free once the three integrators are in the same package.

Performance with real parts (TL074, 200 ns delay, E96 values — `sim/components.py`):

| input level | input volts | SNR | integrator swings |
|---|---|---|---|
| −14 dBFS | 0.49 Vrms | 61.3 dB | 1.05 / 1.11 / 1.22 V |
| −10.5 dBFS | 0.74 Vrms | 65.3 dB | 1.24 / 1.37 / 1.40 V |
| **−8 dBFS** | **0.98 Vrms** | **68.0 dB** | 1.43 / 1.47 / 1.45 V |
| −6 dBFS | 1.24 Vrms | 69.8 dB | 1.61 / 1.70 / 1.66 V |
| −4.4 dBFS | 1.48 Vrms | 71.6 dB | 1.94 / 1.92 / 1.86 V |
| −3.1 dBFS | 1.73 Vrms | **overload** | — |

Target was 65–75 dB. **Sits at 68–70 dB across the normal operating range.**

Input volts assume the level trimmer at maximum, where full scale is 3.49 Vpk
(2.47 Vrms) — set by `Rin = 20k5` against `Rd1 = 14k7`, since full scale is
just `2.5 V × Rin/Rd1`. The trimmer only ever attenuates, so **the fixed
resistor sets the most sensitive setting the board can reach**. That is chosen
for a phono stage delivering roughly 1 Vrms peaks; a hotter 2 Vrms source is
handled by turning the trimmer down, and a much quieter one wants a smaller
`Rin`. `Rin` is not in the feedback path, so changing it moves full scale
without touching the loop at all.

---

## 4. Two findings that change the circuit

### 4a. Without clamping, one vinyl click kills the recording

`sim/verify.py`. A 40 µs transient at 3× full scale, then back to a normal
signal:

| | after the click |
|---|---|
| ideal op-amps, no clamp | **LATCHED** — output stuck at one rail, permanently |
| clamped at 1.4× Vref | recovered, 68.4 dB (unchanged) |

A 1-bit third-order loop that overloads does not come back on its own. On a
vinyl source that is not a corner case — it is Tuesday.

**The fix is free**: the integrator state scales (S1..S3 in `sim/components.py`)
are chosen so the op-amps' own output saturation is the clamp. Normal peaks are
1.4–1.9 V; the TL074 on the ±5 V rails saturates around ±2.7 V, which is
1.3–1.8× Vref — exactly the range simulated as recovering. **No extra parts, but
the rail voltages and the scaling are now load-bearing, not arbitrary.** Do not
"tidy up" the resistor values without re-running `verify.py`.

### 4b. The handoff's Pi interface cannot work as described

The plan was: divide the 6.144 MHz bit clock by 128 for a 48 kHz LRCLK, and let
the Pi capture "64-bit stereo frames". Two independent problems:

1. **One DIN cannot carry two full-rate PDM streams.** Two modulators at the bit
   clock need 2× the bit clock on the single data line. Stereo was never going
   to fit.
2. **The BCM2835 PCM block caps a channel at 32 bits.** A 128-bit-per-channel
   frame is not expressible — most of each frame would simply not be captured.

**The fix — and it comes out unreasonably clean:**

```
6.144 MHz can ──► 74HC4040 ──┬── Q0 (pin 9) = 3.072 MHz = BCLK
                             ├── Q1 (pin 7) = 1.536 MHz = modulator clock
                             │                            + interleave select
                             ├── Q4 (pin 3) = 192 kHz   = charge-pump drive
                             └── Q6 (pin 4) = 48 kHz    = LRCLK
```

(The 4040's outputs are numbered from Q0 = ÷2, so these are pins 9, 7, 3 and 4 —
worth stating in pin numbers because the ÷2 stage being called "Q0" rather than
"Q1" is an easy off-by-one when wiring it.)

- Both modulators run at 1.536 MHz; a 74HC157 interleaves them onto DIN at
  3.072 MHz, `R L R L …`
- BCLK 3.072 MHz, LRCLK 48 kHz, 64 bits/frame is **exactly standard 48 kHz
  32-bit stereo I2S** — the most boring, best-supported mode the Pi has.
- Each 64-bit frame carries **32 L bits + 32 R bits = precisely one OSR-32
  output sample per channel**. The decimator gets whole, frame-aligned words.
- Software treats the "32-bit stereo" capture as a raw 3.072 Mbps bit river and
  de-interleaves even/odd bits. The L/R phase is fixed by construction (one
  counter drives everything) and identified once at bring-up.

Timing: every 4040 output changes on a master-clock falling edge, so DIN changes
on BCLK falling and the Pi samples it on BCLK rising — **163 ns of setup
margin**, textbook I2S source behaviour, with no retiming flip-flop needed.

---

## 5. Why the oscillator can is worth ordering

`sim/components.py` computes the NRZ-DAC jitter floor:

| clock source | jitter | jitter noise floor |
|---|---|---|
| crystal oscillator can | 20 ps | **102 dB** |
| Pi GPCLK0 (fractional divider) | ~1 ns | **68 dB** |

GPCLK0 would become the dominant noise source and drag the total to ~65 dB —
it would eat the entire margin the third integrator was added to buy. Order the
can.

A 3-pin header lets GPIO4 be strapped in as a bring-up fallback. The clock input
is buffered by a **74HCT** gate (VIH 2.0 V) so it accepts a 3.3 V oscillator or
the Pi's 3.3 V GPCLK0 without fuss.

---

## 6. Supply and reference

±5 V, Pi-powered, as agreed.

- **+5 V** from the Pi, LC filtered.
- **−5 V** by charge pump — no charge-pump IC in the shop, so it is built from a
  **74HC244 with all eight outputs paralleled** (~32 mA) plus 1N5817 Schottkys.

  That ~32 mA is the real constraint, and it is why **the LM311s run on a single
  +5 V/GND supply** rather than ±5 V: leaving them on the negative rail costs
  ~8 mA, which drops the pump output far enough that the TL074s no longer clear
  their 1.94 V peak swing. Running the comparator single-supply needs the
  quantiser summing node biased to +2.5 V, which is free: a resistor equal to
  `Rs` up to +5 V does it, and `VREF_P` is already exactly 5 V/2, so the
  threshold lands where it should with no extra reference.
  Driven from 4040 **Q4 = 192 kHz (pin 3)**, deliberately: 192 kHz is 4× the
  output rate, so any surviving ripple lands **exactly on a null of the CIC
  decimator**. (§4b and the schematic both have this right; an earlier draft
  of this paragraph said Q5, which is 96 kHz.)
  Post-filtered 4.7 Ω + 220 µF → **−3.87 V measured at 29.8 mA**, ripple
  0.24 µV. The −4.1 V estimated here is optimistic — see §10.
- **Reference.** The 1-bit DAC is a 74HC04 gate swinging 0/5 V into R_d, with an
  equal resistor to a −2.5 V reference recentring it: net feedback ±2.5 V.

  **The reference tracks the rail on purpose.** If ±2.5 V is derived by a plain
  divider from the same rail the gate runs on, rail noise becomes a common-mode
  *gain* modulation (−98 dB) instead of additive noise. Filtering the reference
  instead of tracking it would break that cancellation and inject the rail noise
  at full weight. The rail therefore needs **low impedance, not a series RC** —
  the DAC's average supply current is proportional to the signal, so a series
  resistor there would put a signal-dependent droop straight onto the reference.

Thermal noise is a non-issue: 12 µVrms input-referred, **104 dB** below 2 Vrms.
Quantisation noise dominates at ~70 dB, which is the intended design.

---

## 7. Tolerance

Monte Carlo, 120 builds, 1% resistors (`sim/verify.py`):

| caps | median | worst | 5th pct |
|---|---|---|---|
| 5% | 69.9 dB | 68.0 dB | 68.6 dB |
| 10% | 69.7 dB | 66.9 dB | 67.6 dB |

SNR is robust. **Overload margin is not** — about 30% of builds overload nearer
−6 dBFS than −3 dBFS. Hence the nominal operating point is set at **−8 dBFS
(2 Vrms)**, not −6, and there is a front-panel level trimmer. §4a's saturation
clamp is what makes the remaining risk survivable rather than fatal.

E96 snapping costs nothing: realised a = [0.2467, 0.3212, 0.6108] against a
target of [0.250, 0.320, 0.610].

---

## 8. The schematic, and how it was verified

`hardware/kicad/vinyl_adc.kicad_sch`, drawn by
`hardware/kicad/tools/vinyl_adc_layout.py` (A2, 121 parts, four bands: power,
clock/digital, channel L, channel R). Re-run the script to regenerate the sheet
and the `.kicad_pro` together.

Four gates, all passing:

| gate | result |
|---|---|
| `sch_score.py` | PASS, 13/13 — 79% of pins wired part-to-part, 15% stub+label |
| KiCad ERC `--severity-all` | 23 `lib_symbol_mismatch` only (benign cache drift) |
| `tools/check_intent.py` | PASS — drawn netlist matches the intended circuit |
| exported PDF | read, twice; band spacing set from measured extents |

**`check_intent.py` is the one that earned its keep.** The other three all passed
on a sheet that had `MCLK` shorted to ground and `+5V` shorted to `+3V3` — it
asserts the actual topology (each summing node's membership, DAC polarity per
integrator, that int3 reaches both the resonator and the quantiser, that the
rails are separate) and caught every one of them. Re-run it after any edit.

Three bugs it found, all the same shape and all worth knowing for the PCB phase:

- A **ground drop landing on a neighbouring pin's stub.** On a 2.54 mm pin
  pitch a 5.08 mm drop ends exactly one row down, KiCad puts a junction there,
  and two pins short. This shorted the whole 74HC157 and, through it, MCLK to
  ground. Unused inputs now go to one shared bus with a single ground symbol.
- A **vertical run down a header's pin column**, which shorted all three pins of
  the clock-select jumper — the exact trap the `kicad-schematic` skill warns
  about. Every header is now approached horizontally, one run per pin.
- **Two blocks whose decoupling columns landed on the same x**, tying a
  comparator output to a supply.

Also worth recording: **`schdraw.note()` writes a multi-line string into the
s-expression verbatim**, producing a raw newline inside a quoted token, and
KiCad 10 then refuses to load the file entirely — while `sch_score` and the
in-process checks all still pass. `vinyl_adc_layout.py` works around it with a
local `note_block()` that emits one note per line. Fixing `schdraw` to escape
newlines would be a one-line change and would stop this recurring.

## 9. Known limitations

- **DAC inter-symbol interference.** The "a 1-bit DAC cannot be non-linear"
  argument fails if the rise and fall edges are not symmetric, because then the
  charge delivered depends on the transition pattern. This is the classic
  limiter of continuous-time modulators and is not modelled here. Keep the DAC
  node lightly loaded and the two gate edges as symmetric as possible; expect it
  to be the reason the built board measures nearer 65 dB than 70.
- The finite-GBW model is a single lag per integrator. Real op-amps are worse
  near GBW — but since GBW proved irrelevant down to 1 MHz against a 3 MHz part,
  there is a lot of margin absorbing that error.
- 13 ICs plus ~60 resistors will not fit the 62768 process's 104×104 mm
  single-sided jig comfortably. Expect to split across two boards or negotiate a
  larger format. **A PCB-phase problem, flagged now because it may affect the
  connector and block placement chosen during layout.**

---

## 10. What SPICE found

`hardware/kicad/sim/` — eight KiCad testbenches, one per block plus the whole
loop, generated by `sim/tools/sim_layout.py`, which imports this board's own
layout script and calls the same block functions, so every bench is the same
drawing as the board. `sim/tools/run_sims.py` exports each sheet through
`kicad-cli` and asserts the numbers in this document: **51 checks, all
passing**. `sim/tools/test_models.py` checks the behavioural models against
their datasheets separately: 34 more.

SPICE was not asked for the SNR figure. Reaching 68 dB over a 20 kHz band at
OSR 32 needs about a second of transient at nanosecond steps; `sim/verify.py`
computes it properly in minutes. SPICE was asked about the analog reality
that model idealises, and it found five things.

### 10a. The charge pump was drawn backwards

**Both Schottkys had their anodes and cathodes swapped**, which makes the
circuit a voltage doubler rather than an inverter. The net called `-5V`
simulated at **+3.4 V** — which would have arrived on the V− pin of every
op-amp on the board.

Nothing else caught it. `sch_score` passed, ERC passed, the exported netlist
read back correctly and `check_intent.py` passed, because a diode wired the
wrong way round is still a connected diode and every one of those checks is
about connectivity. The cause was a comment asserting that
`Device:D_Schottky` numbers its pins anode-first; **it numbers them
cathode-first**, and at `rot=90` pin 1 lands at the bottom.

Fixed in `charge_pump()`, and `sim_a_pump` now asserts the pump node's
polarity explicitly, which is a check that could only ever have come from a
simulation.

### 10b. The pump is weaker than §6 assumed, and that costs input headroom

| | §6 estimate | measured |
|---|---|---|
| rail | −4.1 V | **−3.87 V** |
| current | 32 mA | 29.8 mA |
| ripple | < 1 µV | **0.24 µV** ✓ |
| time to come up | — | **~40 ms** |

The pump's output resistance is about 16 Ω and it is set by the **74HC244's
own on-resistance**, not by 1/fC: 10 µF through 4 Ω is a 40 µs time constant
against a 2.6 µs half period, so the flying cap never finishes charging. A
bigger C4 or a faster PUMP will not change that; only more paralleled buffers
would, and there are none left.

**The consequence is the one thing on this list worth acting on.** The TL07x's
input common-mode range is specified as ±11 V minimum on ±15 V rails — V− + 4 V
guaranteed, V− + 3 V typical. On a −3.87 V rail the *guaranteed* floor is
**+0.13 V**, and every virtual earth on this board sits at 0 V. Simulation says
it works: the summing nodes never go below −0.27 V, comfortably inside the
typical −0.87 V floor. But the ~1 V of margin §6 implied by writing "±5 V" is
not there, and a part at its guaranteed limit would phase-invert. Anything
that lightens the negative rail — the LM311s are already on a single supply
for this reason — buys margin directly.

### 10c. The loop survives the click, and the clamp is not knife-edge

40 µs at three times full scale at t = 1.5 ms. By 2.2 ms all three
integrators are back to their normal swing and the output is still toggling
at 50 % density. This is what §4a promised and it is the single most valuable
thing SPICE could say about this design.

The saturation doing the rescuing is **asymmetric**, because the rails are:

| | positive | negative |
|---|---|---|
| integrator 1 | +3.19 V | −2.35 V |
| integrator 2 | +3.43 V | −2.33 V |
| integrator 3 | +3.35 V | −2.32 V |

§4a assumed a symmetric ±2.7 V. It recovers anyway — and sweeping the clamp
level in the Python model shows recovery is insensitive over at least
2.0–4.5 V, so the "1.3–1.8 × Vref window" in §4a reads far more precarious
than it is. What matters is that the states are bounded at all: unclamped,
they run away by six orders of magnitude.

Integrator swings at −8 dBFS measure **1.42 / 1.46 / 1.31 V** against the
1.43 / 1.47 / 1.45 V predicted in §3.

### 10d. Every coefficient is 3.5 % low, and it is the TL074's 3 MHz

The settled integrator ramp is **96 %** of 2.5 V / (Rd × C). An ideal
amplifier gives 100.0 % and a 30 MHz one 99.7 %, so this is the part and not
the measurement. `a1` reads 0.236 against the design's 0.247.

It is a systematic 3.5 % on every `ai`, well inside the ±10 % Monte Carlo of
§7, and §2's GBW sweep already shows the loop does not care — the Python
model carries the same lag. Worth knowing only so nobody chases it: the
triangle's peak-to-peak reads 6 % low for the same reason, the corners being
rounded, and no charge is lost.

Two more numbers confirmed rather than corrected: **|k0| = 0.228** read
straight off the comparator's threshold shift (design −0.225, E96 −0.2278),
and the LM311's propagation delay at **195 ns** against the 200 ns budgeted.

### 10e. The I2S setup margin is 145 ns, not 163

§4b's 163 ns is half a BCLK period, which assumes DIN and BCLK arrive
together. They do not: the ripple counter puts **31 ns** between Q0 and Q6,
and the mux and the two 74HC4049 stages take their share. What survives is
**145 ns**, still more than four times what the Pi needs, and 64 BCLK per
LRCLK frame with a clean 1.536 MHz DIN confirms the two channels land in
alternate bit slots.

The DAC's two levels come out **0.09 %** apart at integrator 1 and **1.3 %**
at integrator 2, from the 74HC04's 50 Ω against 14k7 and 13k0. That is a gain
error and a DC offset in the feedback, never distortion.

### 10f. A toolchain trap that would have wasted a day

**ngspice cannot read this board's component values.** They are written the
IEC 60062 way, which is correct for a BOM and unreadable to SPICE: it takes
the leading number, looks for a scale suffix and discards the rest.

| on the sheet | ngspice reads | intended |
|---|---|---|
| `14k7` | 14 kΩ | 14.7 kΩ |
| `5k90` | 5 kΩ | 5.9 kΩ |
| `4R75` | 4 Ω | 4.75 Ω |
| `1M0` | **1 mΩ** | 1 MΩ |

Nothing warns; the deck exports and the simulation runs a different circuit.
`sim_layout.py` gives every passive a `Sim.Params` override carrying the same
value spelled the way ngspice reads it, while the Value field keeps the
notation the board and the BOM use. `hardware/kicad/sim/README.md` records
the other traps — multi-unit symbols not exporting at all, power symbols
landing on each other, and three ways a behavioural logic model can look
like it works while producing noise.
