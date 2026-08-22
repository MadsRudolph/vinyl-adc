# Handoff — Discrete Delta-Sigma Vinyl ADC (from-scratch build)

Written 2026-08-22 by a previous session. The goal of YOUR session: **design the
schematic** (and later the PCB + software). Mads is a DTU EE student; treat him
as technically strong, lead with actions, keep explanations brief unless asked.

## What this is

A **from-scratch stereo audio ADC** for digitizing vinyl — no dedicated ADC IC
allowed. Everything must be buildable from the **DTU component shop** stock
(jelly-bean op-amps, comparators, 74-series logic, passives, regulators).
It permanently replaces a borrowed Focusrite Scarlett Solo in this chain:

```
Pro-Ject Debut Carbon → Pro-Ject Phono Box (line out, RCA stereo)
    → [THIS PROJECT] → Raspberry Pi "mediaplayer" → FLAC → Jellyfin/Music Assistant
```

## Decided architecture (agreed with Mads — don't relitigate, refine)

**Second-order discrete delta-sigma modulator per channel**, 1-bit PDM output,
digital decimation done in SOFTWARE on the Pi (CIC + FIR — deliberately: this is
Mads's DSP curriculum, DTU 34315).

- Clock ~**6.144 MHz**, OSR **128**, output rate **48 kHz**
- Analog: 2 cascaded op-amp integrators → comparator → D-flip-flop (retimed
  1-bit out) → 1-bit DAC feedback (analog switch or transistor pair to ±ref)
- Expected performance: **11–13 ENOB, ~65–75 dB SNR** — deliberately matched to
  vinyl's own ~60–70 dB medium noise floor. Mads knows and accepts this.
- Stereo = two modulator channels sharing clock + reference.

## Candidate parts (verify against actual shop stock — this is step 1)

- Op-amps: NE5532 (preferred, audio) or TL072
- Comparator: LM311 (or LM393); design in hysteresis
- Logic: 74HC74 (D-FF), 74HC4053 (feedback switch), 74HC4040 (clock divider for
  LRCLK generation — see Pi interface note), possibly 74LVC-series if 3.3 V
  logic levels demand it (Pi GPIO is 3.3 V — NOT 5 V tolerant! Level discipline
  is a hard requirement.)
- Clock: crystal oscillator module 6.144 MHz (or 12.288 ÷ 2). **OPEN QUESTION:
  Mads was asked whether the shop stocks audio-frequency crystal modules or
  whether to use the Pi's GPCLK0 (GPIO4) as clock source (fewer parts, more
  jitter). Get his answer before fixing the clock design.**
- Supply: Pi 5 V → LDO(s); decide single-supply (bias at mid-rail ~1.65/2.5 V)
  vs charge-pump ±rail for the analog front end. Clean analog rail matters.
- Input: RC anti-alias per channel (line level in, ~2 Vrms max), film caps.

## Raspberry Pi interface (the clever bit — design for it)

Target Pi: **mediaplayer, 192.168.50.165** (`ssh mads@192.168.50.165`, key auth,
passwordless sudo; Debian 13, PipeWire). It already runs librespot + squeezelite
user services (audio OUT via USB Schiit Modi) — GPIO/I2S is free.

- Pi I2S capture pins: **BCLK = GPIO18 (pin 12), LRCLK = GPIO19 (pin 35),
  DIN = GPIO20 (pin 38)**. GPCLK0 = GPIO4 (pin 7) if Pi provides master clock.
- The Pi's I2S controller expects framed audio, not raw PDM. Plan used by prior
  session: the board divides the 6.144 MHz bit clock by 128 (74HC4040) to make a
  48 kHz "LRCLK", so the Pi captures the raw PDM bitstream as if it were 64-bit
  stereo frames; software then reinterprets the bits. Validate this scheme
  during schematic design (it constrains BCLK/LRCLK phase).
- A device-tree overlay for I2S slave capture is needed later (software phase,
  not schematic phase).

## Deliverables, in order

1. **Schematic** — KiCad. Two invocable skills exist and MUST be used:
   `kicad-schematic` (readable schematic discipline) and later
   `kicad-laser-pcb` (DTU 62768 single-sided fiber-laser PCB process,
   104×104 mm jig format, its own footprint library and gotchas).
   Calculate real component values (integrator RC for stability at OSR 128,
   comparator hysteresis, feedback DAC levels, input filter corner).
2. **BOM** with DTU-shop-plausible parts; flag anything that may need ordering.
3. **PCB** via kicad-laser-pcb process. Analog/digital ground split, short
   input traces, single-sided constraints.
4. **Software** (separate phase): CIC decimator (order ≥3 for 2nd-order mod) +
   FIR compensation + DC-block highpass, running on the Pi; then integration
   into the proven vinyl pipeline below.

## Already-proven infrastructure (don't rebuild)

- Vinyl capture pipeline works end-to-end (proven with the Scarlett, mono):
  `pw-record` on the Pi → sox → FLAC → copied to Proxmox host
  `root@192.168.50.200:/srv/media/music/...` (chown 100000:100000) → Jellyfin
  library scan → Music Assistant → playback on "Audio Chain" (squeezelite on
  the same Pi). Level calibration method: record test, `sox ... -n stats`,
  target ≈ −6 dB peaks.
- Planned UX (software phase): Home Assistant "Record Vinyl" button.
- Sox silence-splitting of vinyl tracks FAILED at 0.7% threshold (surface
  noise) — track splitting needs a smarter approach eventually.

## Context that saves you time

- Homelab: Proxmox host `root@192.168.50.200` (guests incl. Jellyfin CT 106 at
  .212:8096); watchtower Pi .136 (monitoring/bench, Deskflow KVM, serial tools).
  Mads's memory files cover these ([[jellyfin-autorip]], [[watchtower-pi]],
  [[proxmox-migration]]).
- Mads does the physical work (shop run, soldering, scoping) — guide him.
- Bench: watchtower Pi has tio/ser2net/PulseView-ready USB, plus a monitor;
  Deskflow gives him mouse/keyboard on it from his desk.

## First actions for your session

1. Ask Mads for the shop-stock answers: which op-amps/comparators/logic
   families are on the shelf, and the **clock question** above.
2. Load `kicad-schematic`, start the schematic: block diagram → per-block
   values → full sheet. One channel first, then mirror for stereo.
3. Sanity-check modulator stability (2nd-order needs proper coefficient
   scaling — integrator gains ~0.5/0.5 or similar; simulate if tools allow,
   or design conservatively).
