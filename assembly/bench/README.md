# Analog Discovery 3 board tests

Use **Board tests · AD3** in the assembly page for the connections, expected values, and test results for the selected physical board. Tests run interactively in a terminal; the webpage never enables a hardware output.

From the project root:

```sh
python assembly/bench/run.py devices
python assembly/bench/run.py power
python assembly/bench/run.py digital --ad3-3v3
python assembly/bench/run.py left --ad3-3v3
python assembly/bench/run.py right --ad3-3v3
```

`--ad3-3v3` explicitly supplies **3.3 V from AD3 V+ to digital J2.3**. Omit it if a separate regulated bench output provides 3.3 V. **Never parallel these sources.** The bench supply always provides +5 V. Power alone does not use 3.3 V.

Python 3, NumPy, Digilent WaveForms Runtime/SDK and Adept Runtime are required. NumPy and Adept Runtime were already installed on this computer. Both official Linux installers have been saved in [downloads](../downloads/README.md). The normal Linux runner adds the installed Adept library directory to its own loader search path, without changing system configuration. WaveForms must be installed before the normal `python …` commands can find `libdwf.so`; `DWF_LIBRARY` can override the library path for diagnostics. Close the WaveForms GUI before running a hardware test. If multiple AD3 devices are connected, select `--serial SERIAL` using `devices` output.

The scripts refuse other instrument models. `devices` only enumerates devices, without opening one. Do not run a live board command until assembly, unpowered inspection and the wiring checklist are complete.

## Test order and scope

1. **Power standalone:** W1 loopback verifies the generated 192 kHz, 0–5 V pump clock before attaching it to J3.10. The power board receives bench +5 V at J3.2/GND at J3.1. The script checks +5 V, the generated negative rail, both references, ratiometric reference accuracy, and gross ripple. No digital board is attached to compete with W1.
2. **Digital standalone:** bench +5 V at J2.1, +3.3 V at J2.3, GND at J2.2. J1 shunt 1–2. Measure the oscillator/divider outputs, level-shifted clocks (including a sample-limited non-inversion/delay screen) and all four QL/QR mux truth-table cases. Temporary QL/QR ties are to board GND or +5 V, never to 3.3 V DIO outputs. The script checks actual input states before judging the outputs.
3. **Each channel:** use the tested power/digital boards and one channel at a time. Remove the digital-test input ties from the selected channel output. Check loaded supplies/references, quiet input density and switching, complementary flip-flop/DAC outputs, the selected bus output, and the response to two levels of 1 kHz input. Set J21 1–2 for left or 2–3 for right; physical reference numbers are identical on both copies.
4. **Complete stack:** with power off, remove all remaining test ties, connect both tested channels, and recheck the power rails/references under full load before enclosing the stack. Individual board results do not prove the full-stack power margin.

CLK6M is **6.144 MHz**; the net called MCLK is **1.536 MHz**. BCLK is 3.072 MHz, LRCLK is 48 kHz, and PUMP is 192 kHz. These values come from `clock_divider()` in `hardware/kicad/tools/vinyl_adc_layout.py`, with pin/net names checked against the PCB snapshot. The older README and design notes contain superseded architecture details.

`plans.json` is the shared website/terminal wiring plan. Its probe references and nets are validated against the extracted PCB data by the offline tests. `limits.json` contains the exact acceptance windows included in every report. Frequency targets and truth tables follow the schematic. Analog windows, ripple limits, duty/density windows and gain checks are **provisional engineering screening limits**, not a manufacturer specification or a measured production distribution. A charge pump is not a regulated −5 V source; the earlier SPICE work reports approximately −3.87 V under load, so the screening window is deliberately not centred tightly on −5.000 V.

## Connections and operation

- Common reference: AD3 GND, 1−, 2−, board GND, and bench negative. A negative-rail measurement uses **2+ on the negative rail**, never a ground clip on that rail. Confirm any earth-referenced bench connections before adding the USB-connected instrument.
- Use direct 1× AD3 flywire scope connections, DC coupled, with short grounds. The driver sets a 20 V total input range and measures actual sample rates. A passive attenuating probe requires a scaling change; do not silently substitute a 10× probe.
- DIO pins are always inputs, with internal pulls and pattern outputs disabled. They observe 0–5 V logic only. AD3 outputs are 3.3 V logic, which is why they are not used to drive 5 V HC test inputs. AD3 W1 is used for the pump stimulus and audio sine; W2 and V− are disabled and unused.
- Bench starting point: +5.00 V, 0.10 A current limit for a standalone power/digital board; 0.20 A for power + digital + one channel. These are starting protection settings, not expected current consumption. Persistent CC, abnormal current or heating requires stopping and diagnosis, not automatically raising the limit. The script records your manual +5 V current readings.
- AD3 V+ (when selected) is 3.30 V. It is disabled between rewiring steps and at shutdown. Its default instrument protection is not a substitute for the bench +5 V current limit.
- Every wiring change requires an OFF → READY → ON sequence. Turn the bench supply off first, then let the script stop AD3 outputs, rewire, and follow the next power-on prompt. Do not change ICs, shunts or jumpers while powered.
- Ctrl+C and ordinary errors attempt W1/W2, digital-output and AD3-supply shutdown and close the device with SDK `OnClose=shutdown`. USB disconnect or process kill can prevent software cleanup; turn the bench supply off yourself. W1 disabled is not guaranteed high impedance, so disconnect it before using that node with another source.

The power pump test can run before digital assembly. Channel tests require the digital board to supply MCLK and PUMP, and the power board to supply the references/negative rail. No test energizes the Pi.

## Measurements and result files

Each run writes a new folder under `assembly/bench/results/` containing:

- `report.json`: PASS / FAIL / ERROR / ABORTED, exact measured values, limits, raw-capture filenames, device serial/SDK version, supply readings, source PCB hashes and limit-file hash.
- `.npz` files: scope voltages or 16-bit digital sample words plus actual sample rate, and the recovered density waveform for tone tests. Read with `numpy.load(path)` using keys `samples` and `sample_rate_hz`.

The page's **Refresh results** reads the generated index and shows history for that physical board. A report from a different PCB snapshot is marked stale; a simulation is never displayed as a board PASS. Tests stop at the first failed bound or invalid acquisition. Unrun steps are not assumed successful. Exit codes are 0 for a completed passing sequence, 1 for an out-of-window measurement, and 2 for setup/instrument errors or an aborted sequence.

Scope records use a single hardware buffer. Fast digital checks use up to 32768 samples at approximately 50 MS/s. The channel's longer record uses approximately 4 MS/s for 120 ms; it samples Q at falling MCLK edges and averages 256 modulator bits per recovered point. Actual rates are read back. High-speed captures separately check settled feedback relationships; the slower long record is not used for propagation-delay conclusions. Lost/corrupted record data, missing clocks, short captures and acquisition timeouts invalidate a test rather than creating a false PASS.

The two audio inputs are 0.10 and 0.25 Vpeak (0.20 and 0.50 Vpp), 1 kHz, zero offset. Keep RV20 fixed. The scope verifies the input amplitude; the recovered bit-density trace must fit 1 kHz and increase consistently with the input. This tests basic signal conversion and gross gain response, **not** a calibrated audio frequency response, decimator implementation, SNR, THD, jitter, crosstalk or 24-bit accuracy. The gross 150 mVpp ripple check is not a claim of measuring microvolt ripple.

## Offline verification

These commands never open an instrument:

```sh
python assembly/bench/run.py left --plan
python assembly/bench/run.py left --simulate
python assembly/bench/run.py digital --simulate --simulate-fault wrong-clock
python -m unittest discover -s assembly/bench -p 'test_*.py' -v
```

Simulated reports use `status: SIMULATED` and a separate `simulation_outcome`; they cannot qualify a board. Regression tests exercise healthy fixtures and deliberately inject a bad supply, wrong clock, reversed mux, stuck channel and missing tone. They also cover missing clocks, record loss, shutdown failures and output-range guards.

No AD3 was attached when these scripts were created. SDK loading/enumeration and software tests can be checked here, but real acquisition, wiring, analog acceptance limits and board behaviour still need the first physical run.

## Primary references

- [Digilent AD3 datasheet](https://files.digilent.com/datasheets/Analog-Discovery-3-Datasheet.pdf): scope, waveform output and 5 V tolerant digital-input electrical limits.
- [Digilent WaveForms download listing](https://digilent.com/reference/software/waveforms/waveforms-3/previous-versions): official installers.
- [Digilent SDK examples](https://github.com/Digilent/WaveForms-SDK-Getting-Started-PY): API use and instrument lifecycle.
- The downloaded WaveForms 3.25.1 package includes `usr/include/digilent/waveforms/dwf.h`, the SDK reference manual, and `usr/share/digilent/waveforms/samples/py/`. Function signatures and acquisition/record conventions were checked against that header and the official `AnalogIn_Record.py`, `DigitalIn_Record.py`, and `AnalogIO_AnalogDiscovery3_Power.py` examples.
