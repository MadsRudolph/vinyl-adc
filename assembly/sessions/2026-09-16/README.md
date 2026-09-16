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

Type READY / ON / OFF only after doing what the prompt says. Each run writes `assembly/bench/results/<id>/report.json` plus raw captures; the assembly page's **Board tests · AD3 → Refresh results** shows them.

### 1. Power board again, this time with a saved report

```sh
python assembly/bench/run.py power --probe 10,1
```

Standalone power board. W1 → J3.10 (192 kHz, 0–5 V, the script sets it), Korad red → J3.2, black → J3.1. Limit 0.10 A. The script checks the W1 stimulus with nothing attached first, then +5 V, the negative rail, both references and gross ripple. This replaces the "approximately −4.3 V / references work" notes from 6 September with exact numbers.

### 2. Rev B digital board standalone

```sh
python assembly/bench/run.py digital --ad3-3v3 --probe 10,1
```

Remove W1 from the power board. Digital only: Korad red → J2.1, black → J2.2, V+ → J2.3, J1 1–2, QL (J4.12) and QR (J4.14) tied to GND for the rails and clocks steps. Limit 0.10 A.

Before trusting the divider: if the clocks step fails with no CLK6M, put a probe on **J1.1**. That is the raw Pierce output (U9.4). 6.144 MHz there but nothing at U4.10 is a J1/U3 problem; nothing at J1.1 is the oscillator itself (U9 must be the unbuffered 74HCU04; R11 = 2k2; C16/C17 = 27 pF). An oscillator running at tens of MHz means a buffered 74HC04 was fitted.

DIO wiring for the clocks step (all inputs): DIO0 U4.10 CLK6M, DIO1 J4.8 MCLK, DIO2 U4.9 BCLK, DIO3 U4.4 LRCLK, DIO4 J2.4 PI_BCLK, DIO5 J2.5 PI_LRCLK, DIO6 U6.4 DIN, DIO7 J4.12 QL, DIO8 J4.14 QR, DIO9 J2.6 PI_DIN, DIO10 J4.10 PUMP. Scope 1 → J2.4, scope 2 → J2.5 for the Pi levels; the mux step moves them to U6.4 and J2.6.

The four mux cases each need a power-off change of the QL/QR ties (0 = GND, 1 = board +5 V, never a 3.3 V DIO output). After the run, power off and **remove both ties** before any channel goes on the bus.

### 3. Left channel with the tested power and digital boards

```sh
python assembly/bench/run.py left --ad3-3v3 --probe 10,1
```

Power + digital + left channel on the bus, correctly aligned pin for pin. J21 = 1–2 on this board. Korad red → digital J2.1, black → J2.2, V+ → J2.3. Limit 0.20 A. W1 is disconnected for the rails, references and quiet steps; J20.1 is shorted to J20.2 for the quiet step. Then W1 → J20.1 (with scope 1 on it) for the two 1 kHz tone levels, 0.10 and 0.25 Vpeak, RV20 unchanged.

DIO for the channel steps: DIO0 U23.3 MCLK, DIO1 U23.5 Q_OUT, DIO2 U23.6 QN_OUT, DIO3 U24.4 DACP_L, DIO4 U24.2 DACN_L, DIO5 J7.12 QL (left). Scope 2 → J7.2 (+5 V) during the tone steps.

### 4. Right channel

```sh
python assembly/bench/run.py right --ad3-3v3 --probe 10,1
```

Same as the left run with the right board only, J21 = 2–3, DIO5 → J7.14 (QR).

### 5. Full stack rail check

Power off, remove every remaining tie and the J20 short, fit both channels with opposite J21 settings, then repeat the rails and references readings under full load (the `left` run's first two steps with both channels on the bus, or manually with the visual guide's power steps). Record the Korad current. Only then close the enclosure.

## What to record for each run

Korad current at each ON prompt (the script asks), the report id, and anything the script did not measure: heating, CC events, wrong-looking waveforms. Screenshots only if you go the manual WaveForms route.

## Results

*(empty — nothing measured yet on the rev B digital board or the channels)*
