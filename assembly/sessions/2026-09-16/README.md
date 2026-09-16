# Bench plan — 16 September 2026 (rev B digital board, both channels populated)

This is a plan, not a record. No measurement has been taken on the rev B digital board or on either channel yet; the results section at the end stays empty until the runs happen. The 6 September readings were taken on the rev A digital board with an external W1 clock and do not transfer.

## What changed since 6 September

- The digital board is now **rev B**: U9 (74HCU04) + Y1 form a 6.144 MHz Pierce oscillator on the board itself. The X1 socket is gone. **J1 goes across pins 1–2** (crystal); J2.7 stays open. W1 is never connected to the digital board.
- Both channel boards have their seven 100 nF decoupling capacitors and can be powered.
- The SDK scripts now accept the BNC fixture: add `--probe 10,1` for the current probes (scope 1 at 10×, scope 2 at 1×). The DIO flywires and V+ still come off the adapter's pass-through header.
- The PCB snapshot behind the guide and the scripts was regenerated for the current boards (`python assembly/verify.py` passes), so reports will not be marked stale.

## Fixture that stays the same

Korad KD3005D at +5.00 V. AD3 with BNC adapter: both coupling jumpers DC, W1 jumper 0 Ω, scope 1 probe at 10× and scope 2 probe at 1×, declared to the scripts as `--probe 10,1`. AD3 GND, both probe clips and Korad black all on board GND; never a clip on the −5 V rail. AD3 V+ at 3.30 V is the only +3.3 V source (`--ad3-3v3`). Every wiring change: Korad off → script stops AD3 outputs → rewire → script prompts the power-on.

Close WaveForms before any script; only one application may own the AD3.

## Run order

Preferred: `python assembly/bench/gui.py` and open http://127.0.0.1:8090. Same tests as the commands below, with the wiring table and one big READY / ON / OFF button per prompt, and a "continue from an earlier run" option that carries passed steps instead of repeating them. The terminal commands remain equivalent.

Type READY / ON / OFF only after doing what the prompt says. Each run writes `assembly/bench/results/<id>/report.json` plus raw captures; the assembly page's **Board tests · AD3 → Refresh results** shows them.

### 1. Power board again, this time with a saved report

```sh
python assembly/bench/run.py power --probe 10,1
```

Standalone power board. W1 → J3.10 (192 kHz, 0–5 V, the script sets it), Korad red → J3.2, black → J3.1. Limit 0.10 A. The script checks the W1 stimulus with nothing attached first, then +5 V, the negative rail, both references and gross ripple. This replaces the "approximately −4.3 V / references work" notes from 6 September with exact numbers.

### 2. Rev B digital board standalone (two probe checks)

```sh
python assembly/bench/run.py digital --ad3-3v3 --probe 10,1
```

Digital only: Korad red → J2.1, black → J2.2, V+ → J2.3, J1 1–2. Limit 0.10 A. After the rails step, two probe moves on header pins, no DIO wires, no ties: scope 1 → J2.4 PI_BCLK with scope 2 → J2.5 PI_LRCLK (3.3 V logic, 3.072 MHz / 48 kHz), then scope 1 → J4.8 MCLK with scope 2 → J4.10 PUMP (5 V logic, 1.536 MHz / 192 kHz). If nothing runs, probe J1.1 (raw Pierce output, 6.144 MHz) and U4.10.

### 3. Full stack without the Pi

```sh
python assembly/bench/run.py stack --ad3-3v3 --probe 10,1
```

Power + digital + both channels on the bus, J21 = 1–2 left and 2–3 right, nothing on the channel inputs, W1 disconnected, V+ → J2.3, limit 0.30 A. Rails (power J3.2 / J3.16) and references (J3.4 / J3.6) under full load, then PI_BCLK / PI_LRCLK (J2.4 / J2.5), then PI_DIN / PI_BCLK (J2.6 / J2.4): PI_DIN must toggle at 3.3 V logic.

### 4. Connect the Raspberry Pi

Power off. Remove AD3 V+ and all probes. Pi I²S header → J2 pin for pin; the Pi supplies +3.3 V from then on. Korad on first, then boot the Pi and capture. The per-channel `left` / `right` scripts stay available for debugging a channel.

## What to record for each run

Korad current at each ON prompt (the script asks), the report id, and anything the script did not measure: heating, CC events, wrong-looking waveforms. Screenshots only if you go the manual WaveForms route.

## Results (evening session, SDK reports in `assembly/bench/results/`)

**Power board — PASS** (`20260916T193608Z-power-95a4ffad`, pump-check and rails carried from the 21:16 run):

| Measurement | Value | Window |
|---|---|---|
| W1 pump stimulus | 192.00 kHz, duty 0.497, 0.014 / 4.92 V | 188–196 kHz, 35–65 %, ≤0.45 / 4.0–5.3 V |
| +5 V | 4.901 V, 28 mVpp | 4.75–5.25 V, ≤150 mVpp |
| Negative rail | −4.425 V, 20 mVpp | −5.25…−3.50 V |
| Korad current, power board alone | 0 mA shown (below display resolution) | |

References passed in the same run; exact values are in the report.

**Digital board — rails PASS, clocks FAIL** (`20260916T193845Z` failed because the V+ wire was not on J2.3; `20260916T200514Z` rails PASS: +5 V 4.888 V, +3.3 V 3.318 V, 32 mA; `20260916T201434Z` clocks):

| Pin | Expected | Measured |
|---|---|---|
| J2.4 PI_BCLK | 3.072 MHz | stuck at 3.25 V |
| J2.5 PI_LRCLK | 48 kHz | 500.9 kHz, later 491 kHz (drifting) |
| J4.8 MCLK | 1.536 MHz | 15.90 MHz |
| J4.10 PUMP | 192 kHz | 1.987 MHz |

Every divider output was 10.35× too fast and drifting, so the Pierce stage was free-running at about 63.6 MHz instead of locking to the crystal. **Cause: one leg of Y1 was not soldered**, leaving the inverter with only its 1 M feedback path. After resoldering it, three consecutive captures on the bus header gave MCLK 1536.30 kHz (duty 0.51) and PUMP 192.04 kHz (duty 0.50), stable to the last digit and within the AD3's own timebase tolerance. The divider, the 74HCT132 buffer, the 74HC4049 shifter and the rails were healthy throughout; the stuck PI_BCLK was just the 4049 unable to pass a 31 MHz BCLK at 3.3 V.

Note for later: U9 is a buffered **74HC04N** (marking D6683PS), not the unbuffered 74HCU04 the design specifies. It locks to the crystal now that the crystal is connected, but a buffered gate in a Pierce is marginal (design-notes §5), so the HCU04 stays on the order list and should replace it when it arrives.

**Next:** rerun `digital` continuing from the 22:05 run (rails carried), then `stack`, then the Pi.
