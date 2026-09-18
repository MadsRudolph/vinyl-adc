# Vinyl ADC: bring-up log, 16–18 September 2026

From four freshly assembled boards to a Raspberry Pi that records a playing record, splits it into tagged FLAC tracks and hands the album to Jellyfin. This is the complete work log: every measurement, every fault with its symptoms and its real cause, the wrong hypotheses along the way, and the software that was written to get there.

Companion documents: the measured results per step are in [`assembly/sessions/2026-09-16/README.md`](../assembly/sessions/2026-09-16/README.md); the design rationale is in [`design-notes.md`](design-notes.md) (the reference-headroom finding from this bring-up is §10b′); the Pi setup is in [`pi/README.md`](../pi/README.md); the media-server side is in [`server/README.md`](../server/README.md). Raw bench reports and captures live in `assembly/bench/results/` (not in git).

## 1. Overview

### 1.1 Starting point

| Item | State on 16 September, 20:00 |
|---|---|
| Power board | Assembled. Tested loosely on 6 September: "about −4.3 V", references "work", no exact values recorded |
| Digital board | **New rev B**, just assembled: the unobtainable DIP-8 oscillator can is replaced by an on-board crystal Pierce oscillator (74HCU04 + 6.144 MHz HC-49 crystal). Never powered |
| Channel boards L/R | Assembled including the seven 100 nF decoupling capacitors that were missing on 6 September. Never powered |
| Bench tooling | Written for the rev A digital board with an external clock from the AD3; refused to run |
| Raspberry Pi | None set up. No capture or decimation software existed |

Instruments: Digilent Analog Discovery 3 (AD3) with the BNC adapter, one 10× probe on scope 1 and one 1× probe on scope 2, Korad KD3005D bench supply at 5.00 V, a multimeter.

### 1.2 Outcome

| Item | State on 18 September, 00:30 |
|---|---|
| Power, digital, full stack | Pass the AD3 screening (reports `20260916T193608Z-power`, `20260916T203340Z-digital`, `20260917T152701Z-stack`) |
| Left channel | Healthy third-order modulator. Idle noise **−79.6 dBFS** (20 Hz–20 kHz), about 77 dB below a full-scale sine. The design simulation predicted 70 dB |
| Right channel | Modulator loop unstable. Root cause located (the board's −5 V enters through one fragile component-side joint on the bus connector), permanent fix not yet applied |
| Raspberry Pi 4 | Captures the I²S stream as clock consumer, runs the ripper and dashboard as a boot service |
| First real recording | 30 s of a playing record through the left channel, −26 dBFS RMS |
| Jellyfin | Host-side puller installed and tested; albums land in `/srv/media/music/Vinyl/` |

### 1.3 Timeline

| When | What |
|---|---|
| 16 Sep 20:30–21:10 | Bench tooling brought up to the rev B board; hosted guide redeployed |
| 16 Sep 21:10–21:40 | Per-channel probe option, browser GUI for the bench tests, resume support |
| 16 Sep 21:36 | Power board PASS |
| 16 Sep 21:38–22:35 | Digital board: missing 3.3 V wire, then the oscillator running at 63.6 MHz, fixed by resoldering a crystal leg. PASS at 22:33 |
| 16 Sep 22:40–23:30 | Stack test: left board loads MCLK, J21 orientation, both channel outputs pass |
| 16 Sep 23:59 | References fail under full load: VREF_N −1.77 V. TL072 cannot swing that far on the loaded pump rail |
| 17 Sep 17:20 | U2 swapped to LM358: VREF_N −2.43 V. Full stack PASS at 17:27 |
| 17 Sep 17:30–20:15 | Pi: OS, SSH, overlay, the "I²S pins are outputs at boot" finding, migration from USB stick to SD card |
| 17 Sep 20:24 | First capture from the Pi. Left healthy, right first-order-like |
| 17 Sep 20:30–23:30 | Right channel: shorted op-amp output, limit cycle, open joint at R33, finally the single-joint −5 V feed |
| 17 Sep 23:00 | Live browser view of both modulator streams |
| 17 Sep 23:50 | Listening simulation through the modulator model |
| 18 Sep 00:05 | First real music recorded and declicked |
| 18 Sep 00:30 | Ripper, dashboard and Jellyfin delivery running |

## 2. Bench tooling for the rev B digital board

### 2.1 Why nothing ran

`assembly/bench/run.py` refuses to test against a stale PCB snapshot (`assembly/generated/boards.json` carries a SHA-256 per board). The rev B commit had changed all three PCB files, so every hash mismatched. Regenerating failed too:

| Check in `assembly/generate.py` / `verify.py` | Rev A assumption | Rev B reality | Change |
|---|---|---|---|
| No vias | 0 | 2, stacked, GND, on the WL7a wire-link pad | Vias accepted only where they sit on a same-net wire-link anchor |
| Digital part count | 13 | 18 (U9, Y1, R10, R11, C16, C17 added, X1 gone) | Updated; component positions 109 → 114 |
| Wire-link anchors | 18, paired as `WLnA`/`WLnB` | 16, lowercase `WLna`/`WLnb`, one (WL4b) with no drawn route | Pairing by name replaced by "each anchor net has at least two anchors" |
| Part kinds | no crystal | Y1 | `crystal` kind added, shown in the assembly app |

The assembly app's wire-link page paired anchors by the uppercase suffix, so it showed **no links at all** for rev B. It now derives links from the drawn top-side routes (`boards.json` → `runs`): anchors on a route are chained by nearest neighbour, component pads join the nearest anchor on their route, and an anchor with no route is paired with the nearest same-net endpoint and flagged "verify in KiCad". Result: 16 links.

The guide still described the rev A procedure (X1 empty, J1 on 2–3, W1 injecting 6.144 MHz at 0–3.3 V into J2.7). All of it was rewritten for the crystal: **J1 on 1–2, nothing on J2.7, W1 never connected to the digital board**, with a new first probe pair J1.1 (raw Pierce output) against U4.10 (buffered CLK6M).

### 2.2 Clock tree (for reference)

$$
f_{\mathrm{CLK6M}} = 6.144\ \text{MHz},\quad
f_{\mathrm{BCLK}} = \frac{f_{\mathrm{CLK6M}}}{2} = 3.072\ \text{MHz},\quad
f_{\mathrm{MCLK}} = \frac{f_{\mathrm{CLK6M}}}{4} = 1.536\ \text{MHz},\quad
f_{\mathrm{PUMP}} = \frac{f_{\mathrm{CLK6M}}}{32} = 192\ \text{kHz},\quad
f_{\mathrm{LRCLK}} = \frac{f_{\mathrm{CLK6M}}}{128} = 48\ \text{kHz}
$$

All from one 74HC4040 ripple counter, so their phase relationship is fixed. That matters later (§6.3, §7.2).

### 2.3 Probe attenuation per channel

The scripts assumed 1× flywires; the fixture is a 10× probe on scope 1 and a 1× probe on scope 2. `--probe` now takes one value per channel (`--probe 10,1`) and calls `FDwfAnalogInChannelAttenuationSet` per channel (`assembly/bench/dwf_device.py:AD3.scope`). Verified on the instrument by reading the range back after requesting a 20 V probe-tip range:

| Setting | Range read back | Meaning |
|---|---|---|
| 1× | 59.8 V | the AD3's ±25 V input range |
| 10× | 52.2 V | the ±2.5 V input range, scaled by 10 |

So the SDK scales both the range and the returned samples, and every limit is still checked in probe-tip volts.

### 2.4 Browser GUI and resume

A typed `ready` instead of `READY` aborted a run after two passed steps. Three changes followed:

- **Operator layer** (`assembly/bench/run.py`): all prompts go through an operator object. `TerminalOperator` accepts confirmation words case-insensitively; `gui.py:WebOperator` blocks the test thread until the browser answers.
- **Resume** (`--resume RUN_ID`): the leading PASS steps of an earlier run of the same board are copied into the new report (`carried_from`) and skipped. It refuses if the PCB snapshot, the limits file, the probe setting or the 3.3 V source differ. The measured +5 V is restored from the carried step because the reference check needs it.
- **GUI** (`assembly/bench/gui.py`, `http://127.0.0.1:8090`): board, probes and "continue from" selection, the wiring table per step, one large button labelled with the word the step needs, a field for the Korad current, a log with pass/fail colouring, abort. It only relays answers; it never enables an AD3 output itself and never touches the supply.

One bug shipped and was fixed within minutes: the prompt event was emitted as `emit(kind='prompt', **pending)` while `pending` itself carried a `kind` key. My offline test had used a simulated run, which has no prompts.

### 2.5 The test route was cut down twice

The original digital test wanted eleven DIO grabbers on DIP pins plus two probes. That was rejected at the bench, rightly. The final minimum route uses **only the two scope probes on header pins**:

| Test | Steps |
|---|---|
| `power` | W1 self-check, rails, references |
| `digital` | rails, Pi-side clocks (J2.4, J2.5), bus clocks (J4.8, J4.10) |
| `stack` | rails with the left channel only, left modulator output QL (J4.12 against MCLK), rails with both channels, QR (J4.14), references (J4.4, J4.6), Pi clocks, Pi data (J2.6 against J2.4) |

The stack test adds the channel boards one at a time so that a faulty board is caught alone. All probe points moved to the digital board's header at the top of the stack when the power board's pins turned out to be unreachable once stacked. The mux truth table is not screened separately; "Pi data toggles with both channels present" covers it. The detailed per-channel tests (`left`, `right`, DIO harness, 1 kHz tone) remain for debugging.

## 3. Power board

Report `20260916T193608Z-power-95a4ffad`, PASS. Power board alone, W1 driving PUMP at J3.10, Korad 5.00 V.

| Measurement | Value | Window |
|---|---|---|
| W1 pump stimulus | 192.002 kHz, duty 0.497, low 0.014 V, high 4.920 V | ±2 %, 35–65 %, ≤0.45 V, 4.0–5.3 V |
| +5 V | 4.901 V, ripple 28 mVpp | 4.75–5.25 V, ≤150 mVpp |
| Negative rail | −4.425 V, ripple 20 mVpp | −5.25…−3.50 V |
| VREF_P | +2.466 V | 2.35–2.65 V |
| VREF_N | −2.490 V | −2.65…−2.35 V |

## 4. Digital board

### 4.1 Fault 1: no 3.3 V (operator)

`20260916T193845Z`: +5 V 4.884 V, **+3.3 V 0.026 V**, 31 mA. The capture of J2.3 was perfectly flat at 26 mV for 8 ms, no noise, no drift: a pin nothing is driving, not a rail under load. The script's enable sequence matched Digilent's own `AnalogIO_AnalogDiscovery3_Power.py`. The V+ flywire was not on J2.3.

Added afterwards: the test reads back what the AD3 itself measures on V+. A first version hinted "almost no current, check the wire" at 0.0 mA; that was wrong, because the 3.3 V side is a single 74HC4049 and draws microamps. The hint was removed.

Rails then passed: +5 V 4.888 V, +3.3 V 3.318 V, 32 mA.

### 4.2 Fault 2: the oscillator ran at 63.6 MHz

Symptoms at the Pi header:

| Pin | Expected | Measured |
|---|---|---|
| J2.4 PI_BCLK | 3.072 MHz | stuck at 3.25 V |
| J2.5 PI_LRCLK | 48 kHz | clean 3.3 V square at **500.9 kHz**, later **491 kHz** |

A ripple counter cannot produce a toggling LRCLK from a dead BCLK, so the counter was running, only far too fast:

$$
f_{\mathrm{CLK}} = 128 \times 500.9\ \text{kHz} \approx 64\ \text{MHz}
$$

BCLK was then about 32 MHz, which a 74HC4049 running from 3.3 V cannot pass, hence the stuck output. The 2 % drift between two readings a quarter of an hour apart ruled out the crystal, which holds 0.01 %. Confirmed on the 5 V bus pins:

| Pin | Expected | Measured | Ratio |
|---|---|---|---|
| J4.8 MCLK | 1.536 MHz | 15.90 MHz | 10.35 |
| J4.10 PUMP | 192 kHz | 1.987 MHz | 10.35 |

An inverter with only resistive feedback oscillates near $1/(2 t_{pd})$, about 60–70 MHz for HC logic. The chip in U9 reads **74HC04N D6683PS**, a buffered part, where the design calls for the unbuffered 74HCU04 (design-notes §5; the BOM still says "ORDER"). That looked like the answer, and it was written down as the cause.

**It was not the cause.** One leg of the crystal Y1 was not soldered. With the crystal open, only the 1 MΩ feedback R10 closes the loop, which gives exactly this free-running mode. After resoldering, three consecutive captures:

| Pin | Expected | Measured | Duty |
|---|---|---|---|
| MCLK | 1536.000 kHz | 1536.296 kHz, identical each time | 0.51 |
| PUMP | 192.000 kHz | 192.03–192.05 kHz | 0.50 |

The +0.02 % offset is within the AD3's timebase tolerance. The buffered 74HC04 stays in the socket for now; it locks, but a buffered gate in a Pierce is marginal, and the 74HCU04 remains on the order list.

### 4.3 Digital PASS

Report `20260916T203340Z-digital-897c4fcc`.

| Signal | Frequency | Low / high |
|---|---|---|
| PI_BCLK | 3.0726 MHz, duty 0.59 | −0.03 / 3.36 V |
| PI_LRCLK | 48.009 kHz, duty 0.51 | −0.01 / 3.35 V |
| MCLK | 1.5363 MHz, duty 0.51 | −0.07 / 5.01 V |
| PUMP | 192.04 kHz, duty 0.50 | −0.01 / 5.05 V |

The 0.59 duty on PI_BCLK is the 1× probe's capacitance slowing a 3 MHz edge from a 3.3 V 74HC4049, not the board. Later the same probe on the same signal read only 0.75–2.6 V. Rule that came out of it: **3 MHz Pi-side signals get the 10× probe.**

## 5. The stack

### 5.1 Left channel on the bus: MCLK dragged to 2 V

Rails with power + digital + left: +5 V 4.867 V, −5 V **−4.036 V**, 67 mA. Then:

| | With the left board | Board unplugged |
|---|---|---|
| MCLK high | 4.94 V | 4.98 V |
| MCLK low | **2.06 V** | 0.21 V |
| QL | flat 3.3 V with 192 kHz pump crosstalk, 0 edges | (open input) |

A low level of 2.06 V means the divider output was sinking roughly 50 mA against something sourcing 5 V through about 60 Ω:

$$
I \approx \frac{2.06\ \text{V}}{40\ \Omega} \approx 50\ \text{mA},\qquad R_{\text{source}} \approx \frac{5 - 2.06}{0.05} \approx 59\ \Omega
$$

which is one HC output fighting another, not a resistor. MCLK reaches exactly one pin on the channel board, U23 pin 3, next to pin 4 (+5 V).

Wrong turns here, in order:

1. *A solder bridge U23.3–U23.4.* The meter read 813 Ω one way and 1000 Ω the other between MCLK and +5 V, on **both** boards: that is just what the unpowered chip shows, not a bridge.
2. *A 0.07 mm clearance between MCLK and −5 V tracks.* My distance script ignored layers. MCLK runs on the bottom, that −5 V track on the top; the channel board is double-sided and the DRC is clean.
3. *U23 inserted backwards.* It explained every symptom (floating chip ground clamps MCLK's low through the input diode; the Q pin position carries an input). The chip has a notch at one end and a moulding circle at the other; the notch pointed at the bus, which is correct, since U23 pin 1 is the bus end. Hypothesis dead.

What remained was the same mechanism without the rotation: **U23's ground pin not making contact**. After the board and chip were reseated:

| | Before | After |
|---|---|---|
| MCLK low | 2.06 V | 0.21 V |
| QL | flat 3.3 V | 0–5 V, 366 edges in the record, one-density 0.497, changing only on MCLK edges |

### 5.2 J21 orientation

"J21 = 1–2" was ambiguous on the bench. From the PCB data: **pin 1 (square pad, QL) is the pin farthest from the bus connector; pin 3 (QR) is nearest.** Left board: shunt on the far pair. Right board: on the near pair. The right board first read 0 edges at QR for this reason, then passed with density 0.532.

### 5.3 VREF_N runs out of rail

| Load on the charge pump | −5 V rail | VREF_N |
|---|---|---|
| Power board alone | −4.425 V | −2.490 V |
| + left channel | −4.036 V | not measured |
| + both channels (83 mA total) | −3.788 V | **−1.767 V** (VREF_P +2.466 V) |

VREF_N is U2B, a TL072 inverting VREF_P (R4 = R5 = 10 kΩ). A TL07x output stops about 2 V above its negative supply:

$$
V_{\text{out,min}} \approx V_{-} + 2\ \text{V} = -3.79 + 2.0 \approx -1.8\ \text{V}
$$

Design-notes §10b had already measured the pump at −3.87 V under 30 mA and priced that against the integrators' common-mode range, but not against the reference inverter's output swing. The modulators keep toggling around 50 % with a skewed DAC, so this fails silently.

Fix: **U2 → LM358**, same DIP-8 pinout, output sinks to within a few hundred millivolts of V− at the 1.3 mA both channels draw from VREF_N (14k7 ∥ 13k0 ∥ 8k25 per channel into virtual earths). Rejected alternatives: MCP6002 and MCP601 (rail-to-rail but 6 V maximum total supply, U2 spans 8.8 V; the MCP601 is also a single), LM386 (an audio power amplifier, different pinout).

Result on 17 September: stack current 83 → 73 mA, **VREF_N −2.430 V**, ratio error 0.1 %. Report `20260917T152701Z-stack-94703bd8`, PASS on all seven steps; PI_DIN one-density 0.516 (it was 0.615 with the skewed reference).

An intermediate failure that day read "PI_BCLK = 48.009 kHz": both probes were one pin low on J2. Scope 1 was on LRCLK and scope 2 read about 791 kHz, the rising-edge rate of a random-looking 3.072 Mb/s stream (one rising edge per four bits).

### 5.4 What the Pi will see (manual AD3 capture)

PI_DIN transitions sit **10 ns after the BCLK falling edge and 150 ns before the rising edge** the Pi samples on (bit period 326 ns): textbook I²S timing. My first analysis sampled on the falling edge, where the data changes, and got a nonsense density of 0.87.

## 6. Raspberry Pi

### 6.1 Bringing the Pi up

Pi 4 Model B rev 1.2, Raspberry Pi OS Lite 64-bit (Debian 13 "trixie", kernel 6.18.50). No SD card reader was available, so the image went onto a USB stick; the Pi 4 boots from USB with no card inserted.

- Found on the LAN by mDNS (`vinyladc.local`) and by the Raspberry Pi MAC prefix `dc:a6:32`. Key login after one `ssh-copy-id`; a sudoers drop-in gave the user passwordless sudo.
- **Incident:** after a reboot my SSH client refused to connect: "REMOTE HOST IDENTIFICATION HAS CHANGED". An SD card had been inserted, the Pi 4 tries SD before USB, and it had booted another project ("vintedbot") from the card. Nothing was touched; the host-key check did its job.
- **Migration to the card** with `rpi-clone -f -U --exclude='/home/mads/backups/*' mmcblk0` (rsync-based, rewrites the partition IDs in `cmdline.txt` and `fstab`): 4 min 43 s. The clone lacked the empty `/boot/firmware` mount-point directory on its root filesystem; created by hand. Verified: root on `mmcblk0p2`, 435 boot files on both, overlay and config line present.

### 6.2 The overlay

The stock `i2s-master-dac` overlay is exactly this clocking arrangement (the Pi as I²S clock consumer, a dummy codec, two 32-bit slots) but playback-only. `pi/vinyl-adc-overlay.dts` is its capture twin with the S/PDIF receiver stub `linux,spdif-dir`. The kernel has `snd-soc-bcm2835-i2s`, `snd-soc-simple-card` and `snd-soc-spdif-rx`; the live device tree exposes `i2s_clk_consumer` and `sound`. After a reboot: `card 1: vinyladc [vinyl-adc]`.

### 6.3 Finding: the Pi's I²S clock pins are outputs until a stream is first opened

Read from the PCM block's `MODE_A` register (BCM2711, `0xFE203000 + 0x08`) with `pi/pcm_pins.py`:

| When | `MODE_A` | CLKM / FSM | GPIO18 / GPIO19 |
|---|---|---|---|
| After boot, before any capture | `0x00000000` | 0 / 0 | **outputs** (clock master) |
| After a capture device was opened once | `0x00f0fc20` | 1 / 1 | inputs (consumer), FLEN 64, FSLEN 32 |

The driver programs consumer mode in `hw_params`, not at probe. With the ADC powered during the Pi's boot, the Pi and the ADC's level shifter would drive BCLK and LRCLK against each other. `vinyl-adc-consumer.service` opens the device once at boot and logs the pin state before and after; it finishes about 22 s after kernel start.

Consequences: **boot the Pi first, then switch the ADC's 5 V on.** For the final build, where the Pi's 5 V powers the stack and the ADC therefore clocks during boot, about 470 Ω in series with PI_BCLK and PI_LRCLK limits the overlap to a few milliamps.

### 6.3a The capture card can come up wedged, and only a re-probe clears it

On one boot the card registered normally — `card 1: vinyladc`, `pcm0c` present, one free subdevice, `snd_soc_spdif_rx` and `snd_soc_bcm2835_i2s` loaded, DMA channel `dma0chan2 | fe203000.i2s:rx` allocated — but **every open of `/dev/snd/pcmC1D0c` failed with `EINVAL`**, for any format, including a bare `dd` on the node. `strace` put it at the `openat` itself, not at `hw_params`, and the kernel logged nothing at all. Headphone playback on card 0 worked, so ALSA at large was fine.

It is not the missing clock: the same `EINVAL` appeared with the ADC powered and unpowered, and the honest "no clocks" failure looks different — the open succeeds and the *read* returns `EIO`, which is what `vinyl-adc-consumer.service` means by ending in an I/O error. `live.py` reports any failure as "No clocks from the ADC", which is what sent me looking at the hardware first.

Re-probing the ASoC card clears it, no reboot needed:

```
echo soc:sound | sudo tee /sys/bus/platform/drivers/asoc-simple-card/unbind
echo soc:sound | sudo tee /sys/bus/platform/drivers/asoc-simple-card/bind
```

After that the open succeeds and consumer mode is programmed as usual (`MODE_A=0x00f0fc20`, CLKM/FSM = 1). Later boots came up healthy, so it is intermittent rather than a configuration error. **Check `MODE_A` before blaming the hardware:** if it still reads `0x00000000` after something has opened the device, the card is wedged, not silent.

### 6.4 Wiring

| J2 pin | Signal | Pi header |
|---|---|---|
| 1 | +5 V | pin 2, or the bench supply, never both |
| 2, 8 | GND | pins 6, 39 |
| 3 | +3.3 V | pin 1 (powers only the 74HC4049) |
| 4 | PI_BCLK | pin 12, GPIO18 |
| 5 | PI_LRCLK | pin 35, GPIO19 |
| 6 | PI_DIN | pin 38, GPIO20 |
| 7 | GPCLK0 | open. Only for clocking the ADC from the Pi, with J1 on 2–3 |

## 7. From bits to audio

### 7.1 Stream format

64 BCLK per 48 kHz frame, captured as `S32_LE` stereo. The 32-bit words are **not PCM**. The 74HC157 sends the left modulator's bit while MCLK is high and the right one while it is low, so the data line alternates L, R, L, R at 3.072 Mb/s and each frame carries 32 bits of each 1.536 MHz stream. Because LRCLK and MCLK come from the same ripple counter, the first bit after the frame edge is always a left bit.

### 7.2 The decimator (`pi/decimate.py`, NumPy only)

| Stage | Detail |
|---|---|
| De-interleave | `np.unpackbits` on big-endian words, even positions = left, odd = right |
| CIC | order 4, ÷8, to 192 kHz; Hogenauer structure with state so captures can be streamed; int64 wrap-around is harmless |
| FIR | 161 taps, ÷4, to 48 kHz; windowed frequency-sampling design (Kaiser β = 10) whose passband is the inverse of the CIC droop to 20 kHz, stopband from 28 kHz so aliases fold above 20 kHz |
| Start-up | the first 20 ms are discarded (the filters start from zero state; this was the "−10 dBFS peak" in the first capture) |

Self-test `pi/test_decimate.py`: a synthetic interleaved stream from a second-order modulator, 1 kHz at 0.5 FS and 18 kHz at 0.25 FS plus 0.1 FS DC, recovered within **0.03 dB** and DC to 0.1000.

### 7.3 Judging a modulator from its own bits (`pi/analyze_bitstream.py`)

PSD of each 1-bit stream at the full rate (65 536-point Hann segments, averaged):

- **In-band floor** in dBFS/Hz at 1, 5 and 20 kHz.
- **Noise-shaping slope** between 30 and 80 kHz. A healthy third-order loop climbs about +60 dB/decade just above the audio band; first-order gives +20.
- **Idle tone.** With a DC input the loop whistles at

$$
f_{\text{idle}} = \lvert 2d - 1 \rvert \cdot f_{\text{clk}}
$$

where $d$ is the one-density. Left: $d = 0.4959 \Rightarrow 12.6$ kHz, measured 12.59 kHz. Right: $d = 0.4982 \Rightarrow 5.5$ kHz, measured 5.51 kHz.

The small DC offset itself is explained by the reference asymmetry, $(2.467 - 2.430)/(2.467 + 2.430) \approx 0.0076$, so every healthy board lands near $d = 0.4957$.

### 7.4 First capture (17 September 20:24)

10 s, exactly 3 840 000 bytes, so BCLK/LRCLK are locked.

| | Left | Right |
|---|---|---|
| One-density | 0.4959 | 0.4982 |
| In-band floor at 1 / 5 / 20 kHz | −118 / −118 / −117 dBFS/Hz | −123 / −104 / −100 dBFS/Hz |
| Shaping 30→80 kHz | **+68 dB/decade** | **+13 dB/decade** |
| Noise 20 Hz–20 kHz | −74.3 dBFS | −41.4 dBFS |
| Strongest line | 12.59 kHz, −85 dBFS | 5.51 kHz, **−46 dBFS** |

## 8. The right channel

Four separate faults, each hiding the next.

### 8.1 Integrator 2's output shorted to ground

U20 pin 7 (output of the second integrator) was shorted to ground. The third integrator received nothing from the second, the loop was effectively first-order, and a first-order loop is unconditionally stable, so it "worked": toggling at 50 %, passing every bench screen, shaping noise at +13 dB/decade with a loud idle tone. **None of the AD3 tests could see this; only the spectrum of the bitstream did.**

Removing the short improved the *left* channel from −74.3 to **−79.6 dBFS**: the fault had been loading the shared rails.

### 8.2 Limit cycle

With integrator 2 back, the right loop became truly third-order and, being wrong somewhere else, unstable:

| | Left | Right |
|---|---|---|
| Mean run of identical bits | 1.35 (max 3) | **18.5–19.5 (max 22)** |
| Spectrum | shaped | flat around −90 dBFS/Hz |
| One-density | 0.496 | 0.56–0.57 |

About 17 ones, 17 zeros, repeating: a rail-to-rail oscillation near 41–45 kHz.

**It couples into the left channel.** Left-channel clicks appeared, up to 0.37 FS. The raw bits show why:

```
 L: ...0011001100110011 1111111111111 0101010110010110...
 R: ...0000000000000000 1111101100101100110110 00000000000000...
```

Whenever the right loop momentarily leaves its limit cycle, the jolt through the shared supply and reference rails makes the left modulator hold one level for up to 13–22 clocks.

Exonerated on the way: U20 (swapped with a spare TL072, no change) and the integrator capacitors (all marked 221 on both boards).

### 8.3 In-circuit resistance as a diagnostic, and what I got wrong about it

With the boards unplugged, resistance between IC pins across each loop connection, right board against left:

| Between | Nominal | Left | Right |
|---|---|---|---|
| U24.4 ↔ U20.6 (R25, DAC → integrator 2) | 13 k | 12.7 k | 11.3 k |
| U22.7 ↔ U20.6 (R27, resonator) | 255 k | 118 k | 118 k |
| U20.6 ↔ U20.7 (across C23) | — | 26 k | 26 k |
| U20.1 ↔ U20.2 (across C22) | — | 33 k | 28 k |
| U22.1 ↔ U22.2 (across C24) | — | 130 k | 130 k |
| **U21.3 ↔ U22.1 (R33, integrator 3 → comparator)** | **22 k** | **22 k** | **115 k** |

I predicted "255 k" and "open across the capacitors" and both predictions were naive. The 118 k is R27 in parallel with the path through R32, R31, R33, R34 and R25:

$$
255\ \text{k}\Omega \parallel (10 + 10 + 22.1 + 165 + 13)\ \text{k}\Omega = 255 \parallel 220 \approx 118\ \text{k}\Omega
$$

and the unpowered ICs conduct too. **The method only works as a comparison between two boards of the same design**, and as that it found an open connection: R33's path read 115 kΩ instead of 22 kΩ. (I first guessed R33 and R34, a 165 kΩ neighbour, had been swapped; the colour bands were right.) Reflowing R33's joints brought it to 22 kΩ.

The limit cycle remained.

### 8.4 Root cause: the −5 V supply enters through one component-side joint

Pressing the stack together moved the fault from the right board to the left board. So the loops were fine and a *contact* was not. From the PCB data (`boards.json`, bottom-copper connectivity per net):

| Net | Bottom-copper islands | Bridged only by top copper |
|---|---|---|
| −5 V | {U20.4, U22.4, C26.2, C29.2} and **{J7.16} alone** | J7.16 → U22.4 |
| +5 V | {U23.*, U24.14, C30, C31}, {J7.2, U21.8, C27, R37}, {U22.8, C28, R36}, {U20.8, C25} | J7.2 → U23.1, R36.1 → U23.10, C25.1 → C31.1 |

The holes are not plated. **Bus pin J7.16 has no bottom-copper connection to anything; the whole board's negative rail depends on that header pin being soldered on the component side** — and that is a joint no iron can reach. The `PinHeader_2x08_P2.54mm_Vertical` body outline runs −1.27 to 3.81 mm across rows whose pads sit at 0 and 2.54 mm, so both rows are *under* the plastic, clearing the pad edge by 0.42 mm. With the header seated, the only thing that can connect the pin to the top ring is solder that wicked 1.6 mm up the ~0.1 mm annulus between pin and hole wall, and that column of solder is compressed every time the stack is pushed together. It also explains why reflowing pin 16 from below never held: the joint being reflowed cannot be seen, and whether enough solder climbs back up is chance. When it opens, both op-amps lose V−, the loop overloads (density near 0.6, no shaping). Static bench continuity read fine, because an unflexed marginal joint conducts.

Planned fix, both channel boards, underside: a wire from the J7.16 pad to U22 pin 4, and one from J7.2 to U23 pin 14. Reflowing pin 16 alone did not hold. **Open as of this log.**

#### 8.4a Every joint on the board that carries current through the component side

The same snapshot answers the general question, not just the one about −5 V. `boards.json` already stores each connected top-layer route with the pads that terminate it (`runs`), and a pad flagged `top` is one whose leg has to be soldered on the component side for that route to conduct. There are **ten such routes and twenty such joints**:

| Net | Terminals | Reachable on the component side? |
|---|---|---|
| **−5 V** | **J7.16 ↔ U22.4** | J7.16 beside the header body — the fault in §8.4 |
| **+5 V** | **J7.2 ↔ U23.1** | J7.2, same header, same problem |
| +5 V | R36.1 ↔ U23.10 | resistor leg fine; U23.10 under the socket |
| +5 V | C25.1 ↔ C31.1 | capacitor legs, both accessible |
| VREF_N | R26.1 ↔ R30.1 | resistor legs |
| CMP_L | R37.2 ↔ U23.2 | U23.2 under the socket |
| DACP_L | R25.1 ↔ U24.4 | U24.4 under the socket |
| C22 net | R24.1 ↔ U20.1 | U20.1 under the socket |
| C24 net | C24.2 ↔ R31.1 | accessible |
| R27 net | R27.1 ↔ R32.2 | resistor legs |

Only the two header pins are both hard to solder *and* mechanically worked every time the stack is assembled, which is why they are the two to wire and the rest can stay as they are. The four socket pins are worth remembering if a signal fault ever appears at U23, U24 or U20 — the joint is under the socket body, so it cannot be reflowed without lifting the socket.

The card that goes to the bench with this — the board drawn from the solder side, so the mirrored pin order is not something to work out with an iron in hand — is `docs/underside-wires.html`, generated by `assembly/underside_wires.py` from the same snapshot.

### 8.6 The second fault: DACP_L shorted to ground (18 September, fixed)

The §8.4 wires went on both boards and the right channel did not change: mean run 19.0, density 0.579, slope +3 dB/decade. So §8.4 was a real fault — and not the only one. Worth being clear about that, because the −5 V root cause was never actually tested until the fix was done.

Ruling out the class first. Today's joint inventory (§8.4a) lists ten runs that exist only as component-side copper, and the right board had since been desoldered, resoldered and had the Pi's 5 V fed into a shorted stack. Each of those runs is a direct trace between two pads, so each **must** read ~0 Ω and no comparison with the left board is needed to judge it. All ten read 0 Ω. Both TL072s had V− (−3.87 V and −3.99 V; the difference and the hum on the first were probe contact, not a fault — the noise was mains harmonics, not the 42 kHz limit cycle or the 192 kHz pump). So every passive path was sound.

That left the active side, and the AD3 comparing **the same node on the two boards** found it in three moves:

| Node | Left | Right |
|---|---|---|
| U20.1, integrator 1 out | 1.63 V p-p | **6.83 V p-p** (−2.51…+4.32) |
| U20.7, integrator 2 out | 1.89 V p-p | **6.79 V p-p** (−2.57…+4.22) |
| **U24.4, DAC gate out (DACP_L)** | **0 → +4.63 V, 569 kHz** | **flat, 0.234 V swing, 41.5 kHz** |

Integrator 1 railing meant the loop was open, not that one stage was sick, so walking downstream was pointless; the DAC output was the thing to look at. And the *level* named the failure mode: a 74HC04 driving into a dead short sources tens of milliamps and sits a couple of hundred millivolts above ground, which is exactly the 236 mV "high" measured. A dead chip floats or sits at a rail instead.

U24 is socketed, so pulling it separated the two cases in one move: socket pin 4 still read short to ground, so the fault was the board's copper, not the chip. DACP_L is three pads (U24.4, R25.1, R34.1), 33 mm of component-side copper and ~45 mm of solder-side trace that the ground pour flanks at 0.5 mm with no mask anywhere. The short was found and cleared there.

**Result, both channels on the bench, inputs live:**

| | Left | Right |
|---|---|---|
| Mean run (max) | 1.35 (3) | 1.36 (3) |
| One-density | 0.4957 | 0.4957 |
| Shaping 30→80 kHz | +69.5 dB/dec | +68.5 dB/dec |
| In-band noise | −74.8 dBFS | −75.7 dBFS |
| Floor at 1 kHz | −124.5 dBFS/Hz | −125.5 dBFS/Hz |

Both verdicts read *third-order shaping*, the two spectra lie on top of each other, and the right channel is marginally the quieter of the two. **That is stereo working for the first time**, and it closes open item 1.

Two process notes. The 42.7 kHz the left channel showed throughout was the right channel's limit cycle coupling through the shared rails, exactly as §8.2 described — so a "fault" visible on the good board was really the bad one bleeding in. And the load argument I tried on the way (rail at −4.00 V against the −3.79 V of §13, therefore one channel not drawing) was worthless: a limit-cycling channel does not draw what a working one draws, so the comparison cannot separate the two cases.

### 8.5 Supply noise goes straight into the signal

| Supply for the stack | Left idle noise, 20 Hz–20 kHz |
|---|---|
| Korad bench supply | −79.6 dBFS |
| The Pi's 5 V pin | −68…−73 dBFS |

The 1-bit DAC gates (74HC04) run directly from +5 V, so that rail *is* the DAC reference.

## 9. Live view (`pi/live.py`)

A diagnostic page for the PC browser, twice a second per channel: verdict (third-order shaping / weak / none / limit cycle / stuck), in-band noise, shaping slope, one-density, mean run length; the noise spectrum of both streams from 20 Hz to 768 kHz on one log axis; the last 20 ms of decimated audio; the first 192 modulator bits drawn as cells, where a limit cycle shows as long solid bars. On a Pi 4 it costs about 0.35 s of one core per 0.5 s of signal. It is what made "press on the stack and watch the right channel" possible, which is how §8.4 was found. Two validated series colours on a dark surface, status shown with icon and label, crosshair tooltips, a table view.

## 10. Listening simulation (`sim/listen.py`)

Question: what will music sound like through this ADC? The repo already had a continuous-time model of the loop (`sim/modulator.py`: CIFB, finite GBW, excess loop delay, resonator, ELD path) with the real E96 values from `sim/components.py`. Its `run()` steps one clock at a time in pure Python, about ten minutes for a few seconds of stereo.

- **Batched engine**: the same state update vectorised over hundreds of time slices. Verified **bit-exact** against `Modulator.run` on 6000 clocks. 13 s of stereo (40 M clocks) in 7 s.
- **A mistake worth recording**: concatenating independently simulated bit slices gave 33 dB SNR instead of about 70. The loop is chaotic; two slices encode the same audio with unrelated noise trajectories, and a seam between them breaks the noise shaping. Fix: decimate every slice on its own, with a lead-in for the loop and the filters, and crossfade the *audio*, where a seam is only one noise realisation handing over to another.
- Input interpolation: spectral zero-padding to 192 kHz, then linear ×8.
- Analog noise added at the bench-measured density, −125 dBFS/Hz.

| Check | Model | Hardware / design |
|---|---|---|
| Idle noise, 20 Hz–20 kHz | −79.9 dBFS | −79.6 dBFS (left channel, measured) |
| SNR, −6 dBFS 997 Hz tone, with analog noise | 69.7 dB | 70.0 dB (design-notes, simulated) |
| Same, quantisation only | 72.4 dB | — |

On a synthesised plucked-string clip: residual −62.4 dBFS unweighted, of which 98 % is shaped noise between 20 and 24 kHz that the decimator's transition band lets through; the audible part (20 Hz–20 kHz) is **−78.1 dBFS**. A steeper final filter stage would remove the rest.

## 11. First real recording

The turntable's line output into the left channel's J20.

- First attempt: no music. After removing the clicks the channel was at −77 dBFS with a white spectrum (spectral flatness 0.55; music is below 0.2). The J20 shorting wire from the tests was the prime suspect.
- Second attempt: **−26.7 dBFS RMS, peaks about −9 dBFS**, flatness 0.00, spectrum falling from −31 dBFS (20–100 Hz) to −64 dBFS (8–20 kHz): properly equalised line-level music, about 12 dB of headroom unused. Mains hum: 50 Hz band −39 dBFS, 100 Hz −48 dBFS (open stack on a bench, no turntable ground wire).

**Declicking, first try, rejected.** A loudness-based detector on the content above 10 kHz flagged 196 "clicks" and wanted to interpolate over 24 % of the samples. It was mistaking cymbals for clicks.

**Declicking, second try, from the hardware's own evidence:**

| Evidence | Found in 30 s |
|---|---|
| Runs of 7+ identical bits in the left stream (music never produces them at this level) | 9 runs, 101 of 46 080 000 bits |
| Moments where the right stream's steady 17-bit run pattern breaks | 19 events |
| Left treble envelope within 2 ms of those events | median 0.040 FS, against 0.001 FS at random moments |

Stuck runs are replaced by a neutral 1010… pattern *in the bitstream, before decimation*; 15 of the 19 events that stood out were patched over 2 ms. **0.10 % of the samples touched**, peak −6.8 → −12.2 dBFS.

## 12. The ripper

### 12.1 Signal path and detection (`pi/ripper.py`)

Capture thread (`arecord` → queue) → DSP thread: de-interleave, stuck-run repair, decimation, DC removal, channel-fault handling → recorder state machine → worker thread for splitting and encoding → HTTP API and dashboard on port 8091.

The detector level is the power of the first difference of the audio per 100 ms, which is treble-weighted and therefore blind to mains hum. Calibration from real captures:

| Condition | Detector level, 5 / 50 / 95 percentile |
|---|---|
| Music playing | −65 / −48 / −42 dB |
| Input connected, nothing playing | −74 / −73 / −52 dB (the 95th percentile is the right board's clicks) |
| Input shorted | −74 / −74 / −73 dB |

| Parameter | Default |
|---|---|
| Start | above −62 dB for 70 % of 2 s, with 2.5 s of pre-roll |
| Stop | below −67 dB for 85 % of a 15 s **window** |
| Track gap | below −63 dB for at least 1.2 s |
| Discard | sides shorter than 90 s |

The window matters: the first version used a run of quiet chunks, and the right board's clicks reset it forever, so a finished side never closed.

A channel whose run lengths say "stuck" or "oscillating" is replaced by the healthy one (mono), and the dashboard says so.

### 12.2 Tracks

The record is identified by a MusicBrainz release search in the dashboard (no API key; a descriptive User-Agent). A recorded side of music duration $T$ is matched to the album's next tracks by choosing $k$ to minimise

$$
\Bigl\lvert \sum_{i=n}^{n+k-1} \ell_i - T \Bigr\rvert
$$

so no side letters are needed and multi-disc albums just continue. Expected boundaries are the cumulative lengths scaled by $T/\sum \ell_i$; each is snapped to the longest detected gap within ±15 s, else placed at the expected time. Without track lengths the gaps alone decide.

### 12.3 Encoding and delivery

One common gain per album (album peak to −1 dBFS, capped at +24 dB) so relative levels between tracks survive; 10 ms fades at the cuts; `flac --best`, 24-bit 48 kHz; tags via mutagen (title, artist, album artist, album, track and disc numbers, date, MusicBrainz ids, `MEDIA=Vinyl`, a comment with the rip date and gain); the Cover Art Archive front cover embedded and as `cover.jpg`. Finished albums appear at `/outbox.json` with sizes and SHA-256.

`server/vinyl-pull.py` runs on the Proxmox host from a two-minute timer, in the style of the host's existing autorip service. **It pulls**, so no server credentials live on the Pi. It validates every name, downloads next to the final place, verifies size and hash, moves in, applies the library's ownership (100000:100000, read from the library root) and acknowledges to the Pi. It never deletes; a file the Pi re-encoded (a later side, a new common gain) replaces the old one, which is moved to `/srv/media/.vinyl-replaced/`. Jellyfin's Music library already includes `/media/music` with real-time monitoring, so albums in `/srv/media/music/Vinyl/Artist/Album (Year) [Vinyl]/` appear by themselves.

### 12.4 Tests

| Test | Result |
|---|---|
| Synthetic side: silence, 4 × 30 s of real captured music with 3 s gaps, silence; fake four-track album | Started on the music, closed after 15 s of silence, cuts at **31.0, 64.0, 97.0 s** (the gap centres), four FLAC files of 30.4 s, correct tags, album gain +11.2 dB |
| Puller dry run into a temp folder on the host (through an SSH reverse tunnel, since the PC's firewall blocked the direct route) | 4 files fetched and verified, ownership correct, album acknowledged; second run a no-op |
| On the Pi | 0.24 s of one core per 0.5 s of signal, no backlog. It started recording by itself the moment it was launched, because a record was playing |

### 12.5 Dashboard

State pill (idle / recording with time / not clocking), per-channel health, mono notice; the record on the platter with cover, current track and progress; stereo RMS meters with peak hold and clip flag on a −60…0 dBFS scale; the needle detector with its two thresholds and the silence countdown; the whole side as a waveform (left up, right down, detected gaps shaded, expected track changes dashed, hover for time and levels); records and sides with status, "Finish and send"; log; detection settings.

## 12b. The first real rip, and what the cut got wrong (18 September, 00:44–01:10)

The first side recorded with the ripper was side A of Radiohead's *KID A MNESIA* (2021, 3 LP), stopped after the third track to test the delivery path.

**What worked.** Detection started the side at the needle drop, the dashboard showed the album and track, "Finish and send" encoded three FLACs with tags, and the server's timer fetched them, verified their checksums and filed them under `/srv/media/music/Vinyl/Radiohead/KID A MNESIA (2021) [Vinyl]/` with the library's owner; Jellyfin's monitor rescanned by itself. The Pi kept up (backlog 0, about 250 ms of CPU per 500 ms block).

**What went wrong.**

1. *The side did not close by itself.* With the needle lifted, the level sat at −73 dB but the right channel board's clicks pushed 28 % of the 100 ms frames above the −67 dB stop threshold, so the "85 % of a 15 s window quiet" rule never fired; the side was stopped by hand 85 s later. The envelope also showed why a longer rule is needed rather than a lower threshold: the gap after *Everything in Its Right Place* is 17 s of −71 dB, as quiet as a lifted needle. Over 30 s the two are separable: a 30 s window at −65 dB is at most 65 % quiet anywhere in the music and at least 84 % quiet after the lift. That is the new rule (`stop_db −65`, `stop_seconds 30`, 80 %); it would have closed this side about 30 s after the lift.
2. *The cut was 30 s off.* The music extent was taken from single frames above −62 dB, so a click in the silent tail made the side 16.4 min long instead of 14.8, the track list was stretched to fit, and the cuts fell at 279 s, 595 s and 985 s against real boundaries near 251, 537 and 895 s; the first "track" ended half a minute into *Kid A*. The fix computes the extent from 3 s windows (≥ 50 % of frames above the threshold), extends both ends to where a 3 s window is 80 % below the stop threshold so fade-outs are kept, recomputes the gaps from the finished envelope and merges fragments closer than 2.5 s (the clicks had split the 241–261 s gap into three), and where no gap exists near an expected boundary (*Kid A* runs into *The National Anthem*) cuts at the quietest second within ±15 s instead of at a scaled guess. Re-run on the same envelope: 251.2, 535.0, 882 s.
3. *No cover.* This pressing has no scan on the Cover Art Archive; the release group's front cover is fetched as a fallback (it exists for this album).

The delivered files were re-encoded and replaced. The puller, until then strictly additive, now replaces a file whose checksum changed and moves the old one to `/srv/media/.vinyl-replaced/`, because the common album gain changes whenever a side is added, and the zero-touch flow below re-sends albums.

## 12c. Zero-touch: the record identifies itself

The intended use is to put a record on and never open the dashboard. The ripper fingerprints the first two minutes of a side (Chromaprint `fpcalc` on the raw 24-bit side file, about 0.7 s on the Pi) and queries AcoustID with `meta=recordings releases tracks`.

The first live attempt returned nothing, with a valid key, from five different points of the side. The cause was the `duration` parameter: AcoustID only returns a recording whose length is within about ±10 s of the declared duration, and I had been declaring the 120 s excerpt length. With 251 s declared, the vinyl audio of *Everything in Its Right Place* (mono, −39 dBFS hum, clicks) scored 0.83; 245–260 s worked, 235 and 275 s did not. So the lookup now waits until the first track's length is known: while recording, the end of the first gap; for a closed side, the quiet fragments around the first gap from the envelope (a fade-out leaves several short ones, and the true length ends at the next track's start, so the gap's centre, end and start are tried, then ±10 s, at most eight requests); for sides whose tracks run into each other, a scan of plausible lengths after eight minutes. Chromaprint itself is unbothered by the vinyl artefacts; the whole difficulty was the metadata. Every (release, medium, track) an answer could be is ranked: the album already in use first (+100, so a chosen pressing is never abandoned because AcoustID lists the recording under other editions), then vinyl formats (+2), then the match score, with a small penalty for long track lists so compilations lose to the album. If one of the current album's recordings matched, the side is attached to it at that track; otherwise the best release becomes the current album (its tracklist from MusicBrainz), and an album that was in progress is finalised with what it has. The side then carries its own starting track (`first`), so side B before side A, or a needle dropped mid-side, cuts correctly. A side whose tracks are already recorded goes to the trash instead of being assigned twice; an album untouched for three hours is sent as it is; below 3 GB free the ripper removes trash and the raw audio of delivered albums, oldest first. The lookup needs a free AcoustID application key in `~/vinyl/acoustid.key`; without it the dashboard says so and manual selection still works. Tests: `pi/test_ripper.py` (ranking, current-album stickiness, album switching, no-key path, cutting from a given track, repeat-play rejection).

### 12c′. The first zero-touch record, and the anchor (18 September, 01:50–05:40)

The first record played without touching the dashboard was Lord Finesse's *The Awakening* (1996). What the run taught, in order:

1. *Intros are not fingerprinted.* The first side stopped after the intro track; AcoustID had nothing for it. The lookup now retries at each following track gap (up to four) and, for a closed side, tries the first four tracks in turn. When the side was played again, the second track was found.
2. *Which pressing.* AcoustID did not list the vinyl release for the matched recording, so the ripper used the 1996 CD edition (same sixteen tracks). The dashboard says so.
3. *The identified track is not necessarily the first on the side.* On the next side the needle went down a minute into track 5; the second track fingerprinted, at 226 s, was *Taking It Lyte* (track 6, score 0.86). The ripper took it for the side's first track, labelled the side tracks 6–7, and three hours later the idle timer delivered a wrong album to Jellyfin. Now the identification is stored as an *anchor* (track index, time on the side): tracks before it are counted back from that time by their lengths, tracks after it forward. The re-cut gave 225 s of track 5, track 6 whole (63 s against 66), 74 s of track 7.
4. *Partial tracks.* A side that starts mid-track or ends with a lifted needle used to encode those fragments as if whole. The fitter now flags them (`partial`): they are not counted toward the album and not encoded, so nothing incomplete reaches the library. The dashboard lists them as "incomplete, not kept".
5. *Activity.* A re-cut or a reset now counts as activity for the three-hour idle send, which otherwise re-fires immediately after any correction.

The wrong delivery was moved to `/srv/media/.vinyl-replaced/` on the server (nothing deleted). As of 05:40 the album stands at two whole tracks (1 and 6) and nothing sent; the clean test that remains is one whole side played from lead-in to run-out. Tests for all of this: `pi/test_ripper.py`.

## 12d. Audio performance plan (`assembly/bench/run.py audio`)

"Is the rip better than streaming?" cannot be answered yes: a lossless stream is the digital master, and vinyl is a lossy analogue copy of it (60–70 dB SNR, 25–35 dB separation, 0.5–3 % distortion; *KID A MNESIA* was cut from digital files). What can be proved is that the ADC is transparent to the medium. The `audio` bench plan measures the finished converter as used: stack powered from the Pi, ripper running, only W1 and AD3 GND on the channel input J20. The ripper gained `/api/hold` (do not record test tones) and `/api/audio` (the last 60 s of decimated audio), so the measurement uses the exact signal path that ends in the FLAC. Steps: full-scale calibration from a 0.5 Vpk tone; idle noise (unweighted, A-weighted, hum lines, SNR); 1 kHz at −3/−6/−20/−40/−60 dBFS (THD, THD+N, harmonics, AES17 dynamic range); crosstalk; third-octave response at −20 dBFS; CCIF 19+20 kHz and SMPTE 60 Hz + 7 kHz IMD from custom W1 waveforms. Spectra and the response are plotted, `summary.md` tabulates everything, and dBFS follows AES17 (rms relative to a full-scale sine; the Hann-window scaling was checked against synthetic sines and noise). The AD3's 14-bit generator bounds distortion and noise figures near −80 dB. The plan is verified in simulation (`SimulatedPi`) and not yet run on the hardware; the "before" baseline is the next bench session.

## 13. Measured performance so far

**Conditions:** left channel, input shorted at J20, Korad 5.00 V, full stack, U2 = LM358, 10 s captures on the Pi, analysis at 1.536 MHz.

| Quantity | Value |
|---|---|
| Idle noise, 20 Hz–20 kHz | −79.6 dBFS (≈77 dB below a full-scale sine) |
| In-band noise density at 1 / 5 / 20 kHz | −126 / −124 / −122 dBFS/Hz |
| Noise shaping 30→80 kHz | +69 dB/decade |
| Idle tone | 13.4 kHz, −86 dBFS |
| One-density with zero input | 0.4957 |
| Stack current | 73 mA at 5.00 V |
| Rails under full load | +4.867 V, −3.79 V |
| References | +2.467 V, −2.430 V |
| Crystal-derived MCLK | 1536.296 kHz |

Not yet measured: THD and SNR with a calibrated tone, frequency response, crosstalk, anything on the right channel.

## 13a. Audio performance, measured (18 September)

First run of the `audio` plan on hardware, left channel, W1 into J20, stack on the Korad, capture from the ripper's decimated 48 kHz output. Run `20260918T093339Z-audio-a485477f`.

| Quantity | Value |
|---|---|
| Full-scale input | 10.41 Vpk (7.362 Vrms) |
| Frequency response, 20 Hz–20 kHz | **0.119 dB peak-to-peak** over 31 third-octave points (−0.047 dB at 20 Hz, +0.072 dB at 16.3 kHz) |
| Dynamic range (AES17, −60 dBFS tone, A-weighted) | 67.9 dB |
| SNR (0 dBFS re idle noise, A-weighted) | 67.7 dB |
| Idle noise, generator connected | −66.2 dBFS, −67.7 dBFS(A) |
| Crosstalk into the right channel | −92.4 dB |
| THD at −6 / −20 dBFS | 0.028 % / 0.032 % (2nd −75.8 dBc, 3rd −83.7 dBc) |
| IMD CCIF 19+20 kHz | −82 dB |
| IMD SMPTE 60 Hz + 7 kHz (4:1) | 0.139 % |
| Hum, 50 Hz | −99.5 dBFS |

Four things to read carefully. **−82 dB CCIF is the AD3's generator, not the converter** — the plan says as much, and anything near −80 dB is the instrument. **THD at −40 and −60 dBFS (1.6 %, 2.3 %) is noise, not distortion**, the tone being near the floor. **−3 dBFS was never reached**: full scale is 10.41 Vpk, so it needs 7.4 Vpk and W1 stops near ±5 V, which is why the −3 and −6 requests both landed at −6.37 dBFS. And the idle-noise figure is **not** comparable with the −76.8 dBFS the live view reports for a shorted input, because here the generator is wired to the input and contributing.

Against the plan's own reference points, 67.9 dB of dynamic range sits inside the 60–70 dB a good pressing delivers, which is the benchmark that matters here.

## 14. What I got wrong, and what caught it

| Claim | Reality | Caught by |
|---|---|---|
| The buffered 74HC04 is why the oscillator runs at 63 MHz | An unsoldered crystal leg | The builder looking at the joint |
| 0.0 mA from AD3 V+ means the wire is off | One CMOS buffer draws microamps | The rails step passing with 0.0 mA |
| MCLK–(−5 V) clearance is 0.07 mm | Different copper layers | Printing the layer of each segment |
| U23 is inserted backwards | Notch toward the bus is correct | Checking pin 1's position in the PCB data |
| R33 and R34 are swapped | Colour bands correct; an open joint | The builder reading the bands |
| Expect 255 kΩ / open across a capacitor | Parallel paths and unpowered ICs | Both boards reading the same |
| Sliced bitstreams can be concatenated | Seams break the noise shaping (33 dB) | A tone SNR check before trusting the audio |
| Treble spikes are clicks | Mostly cymbals (24 % flagged) | The patch percentage |
| A run of quiet chunks detects silence | Clicks reset it forever | The offline fake-side test |
| A ±4-bin window finds the test tone | The ADC clocks itself: LRCLK is 48009 Hz, so a tone lands ~190 ppm low and walks out of the window in proportion to frequency — 35 dB lost at 8 kHz, 70 dB at 19 kHz | A "frequency response" far too steep for any analogue filter (−51 dB at 8 kHz), then reading where the peak really was |
| An 8 s capture after a 5 s settle is clean | The ripper serves the *last* 8 s, so 3 s of the window predates the change and still holds the previous step's tone | A-weighted and unweighted "idle noise" agreeing to four figures — which only happens if the noise *is* a 1 kHz tone |
| Sampling PI_DIN on the falling BCLK edge | That is where the data changes | Transition timing relative to both edges |

Process lessons: compare two boards rather than reasoning about one; let the hardware's own bitstream say what is wrong; every new analysis gets a synthetic test with a known answer before it is believed; and twice my wait loops never ended because `pgrep`/`pkill` patterns matched their own command line.

## 15. Open items

1. ~~**Channel boards:** underside wires J7.16 → U22.4 and J7.2 → U23.14 on both boards.~~ **Done 18 September**, along with the DACP_L short that was the second fault (§8.6). Both channels now read third-order shaping and match to within 1 dB. Bench card: `docs/underside-wires.html`. Still to do: re-measure the right channel with the input shorted at J20, for a figure comparable to §13's −79.6 dBFS.
2. **Order and fit the 74HCU04** in the digital board's U9.
3. **Hum:** turntable ground to the chassis post, enclosure, shielded input leads. Currently −39 dBFS at 50 Hz.
4. **Supply noise:** filter the 5 V feeding the DAC gates before running the stack from the Pi (6–11 dB worse than the bench supply today); fit 470 Ω in PI_BCLK and PI_LRCLK for that configuration.
5. **Decimator:** steeper final stage to remove the 20–24 kHz shaped noise (−62 dBFS unweighted).
6. **Ripper:** tune thresholds on full sides with real groove noise; register an AcoustID application key and put it in `~/vinyl/acoustid.key`; a DHCP reservation for the Pi, whose address is configured on the server.
7. ~~**Performance measurements:** run `assembly/bench/run.py audio` on the hardware for the baseline.~~ **Done 18 September for the left channel** (§13a), after fixing two bugs the run itself exposed (§14). Still to do: the right channel, and a Pi-powered run to quantify what the unfiltered 5 V costs (open item 4). Note the bench GUI holds the AD3 until its process exits, so a second run needs it restarted; and it imports `run.py`/`audio.py` at start, so edits need a restart to take effect.
8. The hosted guide (`vinyl-adc.madsrudolph.dev`) was last deployed from commit `c99fa82`; the `gh` CLI on the PC hangs behind a mise shim, so later deploy dispatches did not go out.

## 16. Software written in these three days

| Path | Purpose |
|---|---|
| `assembly/generate.py`, `verify.py`, `app.js`, `index.html`, `visual-wiring.js` | Guide and PCB snapshot for the rev B board |
| `assembly/bench/run.py`, `dwf_device.py`, `plans.json` | Operator layer, `--probe a,b`, `--resume`, V+ readback, minimal `digital`, incremental `stack` |
| `assembly/bench/gui.py` | Browser front end for the bench tests (port 8090) |
| `pi/vinyl-adc-overlay.dts`, `install-overlay.sh` | I²S clock-consumer capture card |
| `pi/pcm_pins.py`, `vinyl-adc-consumer.service` | Reads the I²S pin direction; sets consumer mode at boot |
| `pi/decimate.py`, `test_decimate.py` | Bit de-interleaving and ÷32 decimation, with self-test |
| `pi/analyze_bitstream.py` | Modulator health from the raw bits |
| `pi/live.py`, `vinyl-adc-live.service` | Diagnostic live view |
| `pi/ripper.py`, `ripper.html`, `vinyl-adc-ripper.service`, `test_ripper.py` | Automatic recording, identification, splitting, encoding, dashboard |
| `assembly/bench/audio.py` | Audio performance analysis (THD+N, SNR, DR, response, IMD) for the `audio` plan |
| `server/vinyl-pull.py`, `.service`, `.timer` | Delivery into the Jellyfin library |
| `sim/listen.py` | Audio through the modulator model and the real decimator |
| `assembly/underside_wires.py` | Solder-side bench card for the two supply wires, drawn from `boards.json` |
