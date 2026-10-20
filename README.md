# Vinyl ADC

[Assembly guide & bench log](https://vinyl-adc.madsrudolph.dev/) · [Rev D bring-up, 20 October](docs/bringup-log-2026-10-rev-d.md) · [Bring-up log, 16–18 September](docs/bringup-log-2026-09.md) · [16 September bench plan](assembly/sessions/2026-09-16/README.md) · [6 September test handoff](assembly/sessions/2026-09-06/README.md)

**Rev D (20 October): built, made by PCBWay, and running.** The converter now lives on one four-layer Raspberry Pi HAT, [fabricated by PCBWay](#rev-d-the-pcbway-board), in place of the four hand-milled boards it was born on. Both channels modulated correctly from the first capture, and with the turntable connected the whole chain records about **8 dB more A-weighted range** than the milled stack did, while running on the Pi's own 5 V and the Pi's noisier clock. Record: [rev D bring-up log](docs/bringup-log-2026-10-rev-d.md).

**The milled stack (September):** all four boards are assembled and bench-screened with the AD3 (16–17 September): power, rev B digital with the on-board crystal Pierce, both channels and the full stack pass, after resoldering a crystal leg and swapping the reference op-amp U2 to an LM358 for output headroom on the charge-pump rail (design-notes §10b′). A Raspberry Pi 4 captures the stream, and a ripper service on it records sides automatically, splits and tags the tracks and hands finished albums to the Jellyfin server; setup in [pi/README.md](pi/README.md) and [server/README.md](server/README.md). No complete-system audio performance is claimed by these assembly tests.

**Rev C (22 September):** with a fab available, the four milled boards are redrawn as [one 4-layer board](hardware/kicad/rev_c/README.md), 170 × 120 mm, all through-hole, with the Raspberry Pi 4 plugged into its underside on its own 40-pin header and the bench fixes (LM358 reference, filtered 5 V inlet, series resistors on the I2S clocks) built in. It passes the same intent gate as the milled boards against the reference sheet; [production files](production/vinyl_adc_rev_c/) and a [bill of materials](docs/bom-rev-c.md) are exported. It was never built: rev D superseded it.

**Rev D (designed 22–25 September):** with PCBWay sponsoring the fabrication, the one-board converter is redrawn as a proper [Raspberry Pi HAT](hardware/kicad/rev_d/README.md) — 140 × 136 mm (its layout redone on 24 September: every passive beside the pin it serves, channel R a copy of channel L), four layers, still every part through-hole from the DTU shop — and given the things the bench asked for: an analog supply island behind its own choke (the DAC reference rail, kept away from the Pi's and the charge pump's switching), a second 74HC244 to stiffen the −5 V pump, a damped MCLK, eight front-edge status LEDs (rail, pump, clock-alive, clip L/R from LM339 window comparators, and three under the Pi's control), shutdown and user buttons, a HAT ID EEPROM, test-point headers with ground pins, and a tonearm ground terminal with a lift network. `tools/check_rev_d.py` proves it is the reference circuit plus exactly those additions; [production files](production/vinyl_adc_rev_d/) and the [bill of materials](docs/bom-rev-d.md) are exported. Design record: [design-notes §12](docs/design-notes.md#12-rev-d-the-converter-as-a-raspberry-pi-hat-22-september-2026).

**Rev E (24 September):** the same circuit in common [surface-mount parts](hardware/kicad/rev_e/README.md) on a 118 × 88 mm four-layer HAT — 0805 C0G/X7R and thin-film parts, SOIC logic and op-amps, SOT-23 transistors, shielded SMD chokes — checked by the same gate as rev D, placed and routed by the same tools, DRC clean. [Production files](production/vinyl_adc_rev_e/) include the pick-and-place file for PCBWay assembly; [bill of materials](docs/bom-rev-e.md); design record [design-notes §13](docs/design-notes.md).

<p align="center">
  <a href="https://madsrudolph.github.io/vinyl-adc/"><img src="https://img.shields.io/badge/🚀_Interactive_3D-Live_Web_Viewer-38bdf8?style=for-the-badge&logo=webgl&logoColor=white" alt="Live 3D Web Viewer"></a>
  <a href="https://github.com/MadsRudolph/srm-cam"><img src="https://img.shields.io/badge/CNC_Milled_With-SRM--CAM-10b981?style=for-the-badge&logo=cmake&logoColor=white" alt="Milled with SRM-CAM"></a>
  <img src="https://img.shields.io/badge/Hardware-KiCad_10-0077c2?style=for-the-badge&logo=kicad&logoColor=white" alt="KiCad 10">
  <img src="https://img.shields.io/badge/Architecture-Discrete_3rd--Order_ΔΣ-f59e0b?style=for-the-badge" alt="Architecture">
  <img src="https://img.shields.io/badge/Audio-24--bit_%2F_48_kHz-8b5cf6?style=for-the-badge" alt="Audio">
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" alt="License">
</p>

<p align="center">
  <strong>A Discrete 3rd-Order Continuous-Time Delta-Sigma Stereo Audio ADC</strong><br>
  Engineered from standard analog op-amps &amp; 74HC CMOS logic — <em>zero dedicated ADC ICs anywhere in the signal chain</em>.<br>
  All circuit boards isolation-milled on a <strong>Roland SRM-20</strong> CNC mill using <a href="https://github.com/MadsRudolph/srm-cam"><strong>SRM-CAM</strong></a>.
</p>

<p align="center">
  <img src="media/showcase/electronics.gif" alt="The four milled Vinyl ADC boards: power, right channel, left channel and digital" width="720">
</p>

<p align="center">
  <a href="media/showcase/README.md">Download GIF animations &amp; print files</a>
</p>

<details>
<summary><strong>More views: the enclosure orbit and exploded assembly</strong></summary>

### Product orbit

![Vinyl ADC enclosure rotating through a full turn](media/showcase/orbit.gif)

### Exploded assembly

![Vinyl ADC 3D exploded assembly animation](media/showcase/assembly.gif)

</details>

<p align="center">
  👉 <strong><a href="https://madsrudolph.github.io/vinyl-adc/">Launch Live Interactive 3D Web Viewer &amp; Explosion Slider</a></strong> 👈
</p>

---

## Rev D: the PCBWay board

<p align="center">
  <img src="media/showcase/rev-d/hero.png" alt="Rev D: the Vinyl ADC as one four-layer Raspberry Pi HAT" width="820">
</p>

Every board before this one was isolation-milled single-sided at the university workshop. That is why the converter had four stacked boards, a 16-pin bus and dozens of hand-soldered wire links, and why the September bring-up spent a day finding a −5 V rail that reached one board only through solder wicked up an unplated hole. **PCBWay offered to sponsor fabrication**, so the converter was redrawn as what it should have been from the start: one board, a solid ground plane, the Raspberry Pi plugged in underneath.

| | Milled stack (Sept 2026) | Rev D (Oct 2026) |
|---|---|---|
| Boards | 4 × 100 × 100 mm, stacked on a bus | **1 × 140 × 136 mm** Raspberry Pi HAT |
| Copper | 1 layer, milled, bare copper | **4 layers**: signals / solid GND / split +5V·+5VA / signals |
| Links | dozens of wire jumpers | **none**: plated through-holes and vias |
| Finish | none | solder mask both sides, silkscreen, HASL lead-free |
| Supply for best figures | bench supply (the Pi's 5 V cost 6–11 dB) | **the Pi's 5 V**, analog island behind its own choke |
| Bring-up | two days, two hidden faults in one channel | both channels healthy from the first capture |

**Measured, with the turntable connected** (stylus up, same phono stage, same method, music peaks set to −6 dBFS on both builds):

| 20 Hz–20 kHz | Milled stack, bench supply, crystal clock | **Rev D, Pi 5 V, Pi clock** |
|---|---|---|
| Idle floor, A-weighted | −61.1 / −62.1 dBFS | **−69.7 / −68.2 dBFS** |
| Idle floor, 2–20 kHz | −59.6 / −60.6 dBFS | **−76.5 / −70.5 dBFS** |
| Music peak to floor, A-weighted | 54.2 / 55.2 dB | **63.7 / 62.2 dB** |
| Music peak to floor, unweighted | 48.9 / 49.2 dB | **51.4 / 51.3 dB** |

Rev D gets there on the supply that hurt the milled stack most and on the Pi's fractional-divider clock (about 1 ns of jitter) while its own crystal oscillator is debugged, so these are a floor for what it can do, not its final figures. What remains in the unweighted number is 50 Hz hum common to both channels, i.e. the turntable's grounding rather than the converter; the board's tonearm terminal is there for that next experiment. The converter-only floor and the full AD3 audio plan (dynamic range, THD, response) on rev D are next, against the milled stack's 67.9 dB.

**What the fab board changed, honestly:** the whole class of fault that cost the most time in September (unplated holes, component-side joints no iron can reach, wire links) does not exist on it, and the first capture from both channels was already healthy. The one rev D fault found so far is my own: the clip-LED comparators' inputs are swapped in the schematic, documented as an [erratum](docs/bringup-log-2026-10-rev-d.md#7-erratum-the-clip-leds-are-lit-all-the-time) with a rework that stays on the underside. Five boards, 4 layers, 1.6 mm FR-4, 1 oz copper, HASL lead-free; the [Gerbers and production files](production/vinyl_adc_rev_d/) are in the repo.

Thanks to **[PCBWay](https://www.pcbway.com)** for sponsoring the boards.

<p align="center">
  <img src="media/showcase/rev-d/orbit.gif" alt="Rev D board turning through a full orbit" width="720"><br>
  <sub>CAD renders (<a href="media/showcase/rev-d/README.md">all views and how they are made</a>); Raspberry Pi 4 model from the FreeCAD parts library, CC BY 3.0.</sub>
</p>

---

## Audiophile Engineering Specifications

| Specification | Target / Measured Performance | Design Rationale & Implementation |
|---|---|---|
| **Modulator Topology** | Continuous-Time CIFB (Cascade of Integrators, Feedback) | 3rd-order active RC loop with local resonator feedback (`G = 0.03`) |
| **Dynamic Range / SNR** | **68.3 dB measured in 20 kHz band** | Purposefully matched to the physical vinyl surface noise floor (~60–65 dB) |
| **Audio Output** | **24-bit / 48 kHz Linear PCM FLAC** | Decimated in software on Raspberry Pi CPU (CIC filter + compensation FIR) |
| **Modulator Sampling Rate ($F_s$)** | **1.536 MHz** ($32\times$ OverSampling Ratio) | Matches bandwidth constraints of DTU-stocked op-amps (`TL072` 3 MHz GBW) |
| **Master Clock ($F_{clk}$)** | **6.144 MHz crystal Pierce oscillator** (74HCU04 + HC-49 crystal) | Direct low-jitter clock ($<50\text{ ps}$ jitter vs. Pi PLL phase noise); also available as a plug-in module for the rev A board |
| **Digital Stream Format** | Bit-Interleaved PDM on standard I2S bus | 3.072 Mbps data stream, read as 32-bit stereo audio frames at 48 kHz |
| **Analog Inputs** | Gold RCA Phono Jacks &amp; 5.08 mm Screw Terminals | Switchable input gain via front-panel multi-turn trim potentiometer |
| **Analog Grounding** | Star-ground topology with tonearm binding post | Eliminates 50 Hz turntable motor hum and ground-loop switching transients |
| **PCB Manufacturing** | Rev D: 4-layer 1.6 mm FR-4, HASL lead-free, by **[PCBWay](https://www.pcbway.com)**. First build: isolation-milled single-sided FR4 | Milled toolpaths generated via [**SRM-CAM**](https://github.com/MadsRudolph/srm-cam) on a **Roland SRM-20** mill |
| **Enclosure Dimensions** | $144.0\text{ mm} \times 144.0\text{ mm} \times 105.0\text{ mm}$ | Open organic lattice, reinforced connector islands and M3 lid inserts; recessed $3.0\text{ mm}$ acrylic lid |

---

## Printable enclosure

The enclosure has an open, rounded lattice on all four sides and 40 mm more height for the PCB stack and cable routing. Solid connector islands and reinforced lid-insert bosses carry the mounting loads. **Print upright with supports**; the revised mesh and supported slice pass validation, but physical print/fit testing is still pending.

[STL, 3MF, insert-fit coupon and printing instructions](enclosure/README.md) · [Three looping GIFs](media/showcase/README.md)

## Signal Processing Flow

```
   ┌─────────────────────────────────────────────────────────────────────────────┐
   │                          ANALOG SIGNAL CHAIN (HARDWARE)                     │
   │                                                                             │
   │  Turntable (Debut Carbon)                                                  │
   │         │                                                                   │
   │         ▼                                                                   │
   │  Phono Preamplifier                                                         │
   │         │                                                                   │
   │         ▼                                                                   │
   │  [ VINYL ADC ] ──> 3rd-Order CT-ΔΣ ──> 1.536 MHz PDM ──> 74HC157 Mux       │
   │   Gold RCA In      TL072 + LM311       74HC74 Retimed    Stereo Interleave  │
   └─────────────────────────────────────────────────────────────────┬───────────┘
                                                                     │ 3.072 Mbps
                                                                     ▼
   ┌─────────────────────────────────────────────────────────────────────────────┐
   │                         DIGITAL DSP CHAIN (RASPBERRY PI)                    │
   │                                                                             │
   │  ALSA I2S Interface (48 kHz / 32-bit Frame Capture)                         │
   │         │                                                                   │
   │         ▼                                                                   │
   │  Software De-interleaver (Separates Left & Right Bitstreams)                │
   │         │                                                                   │
   │         ▼                                                                   │
   │  4th-Order CIC Decimator (Downsamples 32x to 48 kHz Nyquist)                │
   │         │                                                                   │
   │         ▼                                                                   │
   │  FIR Droop & Phase Compensation Filter                                      │
   │         │                                                                   │
   │         ▼                                                                   │
   │  24-bit / 48 kHz Bit-Perfect FLAC Encoder ──> Jellyfin Media Server         │
   └─────────────────────────────────────────────────────────────────────────────┘
```

---

## Noise-Shaping & SPICE Verification

The defining characteristic of delta-sigma conversion is **noise shaping**: pushing quantization noise out of the audible spectrum into ultrasonic frequencies where digital decimation filters remove it completely.

<p align="center">
  <img src="media/noise_shaping_spectrum.png" alt="Noise-Shaping Spectrum & PDM Waveform" width="850">
</p>

- **Time-Domain (Top):** Shows the incoming 1 kHz analog test sine wave alongside the discrete 1.536 MHz 1-bit decision stream. The pulse density cleanly mirrors the instantaneous input amplitude.
- **Frequency-Domain (Bottom):** Measured FFT spectrum with Hann windowing. The audible passband (20 Hz – 20 kHz, shaded green) exhibits a **68.3 dB SNR** with clean third-order $+60\text{ dB/decade}$ noise shaping that drives quantization noise above 30 kHz.

---

## The original 4-board milled stack (rev A/B)

To overcome the routing limitations of single-layer CNC isolation milling (0.84 mm clearance between DIP pins), the system is split into four 100 × 100 mm boards interconnected by a 16-pin ribbon bus and M3 brass standoffs:

| Tier & Board | 3D Raytraced Board Render | Function & Key Components |
|---|:---:|---|
| **Tier 4 (Top)**<br>[`vinyl_adc_digital`](hardware/kicad/digital/) | <img src="media/pcb_renders/pcb_digital_3d.png" width="340" alt="Digital Board 3D Render"> | **Clock, Interleaving & Pi Interface:**<br>• 6.144 MHz crystal Pierce oscillator (`Y1` + `74HCU04`)<br>• `74HCT132` Schmitt-trigger clock buffer<br>• `74HC4040` binary clock divider ($F_s = 1.536\text{ MHz}$, $\text{BCLK} = 3.072\text{ MHz}$, $\text{LRCLK} = 48\text{ kHz}$)<br>• `74HC157` stereo bit-interleaving MUX<br>• `74HC4049` 5 V $\rightarrow$ 3.3 V level shifter to Raspberry Pi |
| **Tier 3**<br>[`vinyl_adc_channel_l`](hardware/kicad/channel_l/) | <img src="media/pcb_renders/pcb_channel_3d.png" width="340" alt="Left Channel Modulator 3D Render"> | **Left Channel Modulator:**<br>• 3rd-order active RC integrators (`TL072`)<br>• `LM311` high-speed comparator<br>• `74HC74` retiming flip-flop &amp; 1-bit DAC network<br>• Multi-turn input gain trim potentiometer<br>• Jumper set to Left (`pins 1-2`) |
| **Tier 2**<br>[`vinyl_adc_channel_r`](hardware/kicad/channel_r/) | <img src="media/pcb_renders/pcb_channel_3d.png" width="340" alt="Right Channel Modulator 3D Render"> | **Right Channel Modulator:**<br>• Identical artwork to Tier 3 (milled twice)<br>• Jumper set to Right (`pins 2-3`)<br>• Independent ground plane &amp; analog reference |
| **Tier 1 (Base)**<br>[`vinyl_adc_power`](hardware/kicad/power/) | <img src="media/pcb_renders/pcb_power_3d.png" width="340" alt="Power Supply Board 3D Render"> | **Power & Reference Generation:**<br>• `74HC244` + `1N5817` charge-pump negative rail<br>• Low-noise precision virtual ground reference (`TL072`)<br>• High-capacity bulk reservoir &amp; post-filter network<br>• 4× M3 mounting holes seated onto enclosure floor bosses |

---

## PCB Fabrication with SRM-CAM & Roland SRM-20

The four boards of the first build were designed for single-sided isolation milling on the **Roland SRM-20** desktop CNC mill at the DTU FabLab. That constraint is why the converter was split into four boards with dozens of wire links; [rev D](#rev-d-the-pcbway-board) is the same circuit on a fabricated four-layer board.

<p align="center">
  <a href="https://github.com/MadsRudolph/srm-cam"><img src="https://img.shields.io/badge/Toolpaths_Generated_By-SRM--CAM-10b981?style=for-the-badge&logo=cmake&logoColor=white" alt="SRM-CAM"></a>
</p>

The RML-1 milling toolpaths and G-code were generated directly using [**SRM-CAM**](https://github.com/MadsRudolph/srm-cam) (`gerber2rml`):
- **Isolation Routing:** Traces isolation-milled on `B.Cu` using 0.2 mm / 0.4 mm V-bits with wide rubout for ground separation.
- **Excellon Drilling:** Automatic hole-center extraction from KiCad `*.drl` files for all DIP sockets, film caps, resistors, and headers.
- **Edge Routing:** Clean board profiling with 1.0 mm end mill for the 100 × 100 mm PCB footprint and M3 mounting holes.
- **Workpiece Fixturing:** Copper-clad FR4 secured using the double-sided tape &amp; CA glue method documented in the [SRM-CAM User Guide: Holding the copper](https://madsrudolph.github.io/srm-cam/holding-the-copper.html).

All production Gerbers and Excellon drill files ready for SRM-CAM are located in [`production/`](production/).

---

## Raspberry Pi Wiring & Star-Grounding Architecture

Turntable systems are exceptionally sensitive to 50/60 Hz hum and digital switching noise. The Vinyl ADC implements an isolated star-grounding architecture:

```mermaid
graph TD
    subgraph Analog Front-End
        TT["Turntable Ground Spade"] --- Post["Chassis Ground Binding Post"]
        RCA["RCA Input Outer Shield"] --- Post
        Post --- Star(("★ STAR GROUND"))
        Star --- Tier1["Tier 1 Analog Virtual Ground"]
    end

    subgraph Raspberry Pi Connection
        Star -.->|Isolated Digital Return| Pi_GND["Pin 6 / 9 (GND)"]
        Tier4["Tier 4 Logic Bus"] -->|Pin 12 / GPIO 18| Pi_BCLK["PCM_CLK (3.072 MHz)"]
        Tier4 -->|Pin 35 / GPIO 19| Pi_LRCLK["PCM_FS (48 kHz)"]
        Tier4 -->|Pin 38 / GPIO 20| Pi_DIN["PCM_DIN (3.072 Mbps)"]
        Pi_Power["Pin 2 / 4 (+5V)"] -->|Filtered DC Rail| Tier1_Pwr["Tier 1 Power In"]
    end
```

### Raspberry Pi 40-Pin GPIO Pinout:

This is the milled stack's wiring. Rev D plugs onto the Pi as a HAT and also uses GPIO3/4/17/22/23/27 and the ID EEPROM pins: see [pi/README.md §7](pi/README.md#7-rev-d-hat-what-the-board-puts-on-the-gpio-header).

| Raspberry Pi Pin | Signal Name | Vinyl ADC Connection | Function |
|---|---|---|---|
| **Pin 2 or 4** | `+5V Power` | Tier 1 DC Input | Supplies digital and analog converter power |
| **Pin 6 or 9** | `GND` | Tier 4 Logic Ground | Digital switching current return |
| **Pin 12 (GPIO 18)** | `PCM_CLK` | Tier 4 Clock Out | 3.072 MHz bit clock for I2S capture |
| **Pin 35 (GPIO 19)** | `PCM_FS` | Tier 4 Frame Sync | 48 kHz word clock (L/R frame framing) |
| **Pin 38 (GPIO 20)** | `PCM_DIN` | Tier 4 Interleaved PDM | Serial stream carrying alternating Left/Right bits |

---

## Repository Structure

```
├── docs/                           # Documentation & Interactive Web App
│   ├── index.html                 # Interactive 3D Web Viewer for GitHub Pages
│   ├── vinyl_adc_assembled.glb    # Complete 3D CAD model with explosion timeline
│   ├── shopping-list.md           # Component shop procurement list
│   ├── bom.md                     # Bill of materials
│   └── design-notes.md            # Circuit design decisions and SPICE findings
├── enclosure/                      # 3D print and laser cutting files
│   ├── vinyl_adc_enclosure.blend  # Complete Blender 3D CAD scene
│   ├── vinyl_adc_enclosure_base.3mf # Millimetre print mesh
│   ├── vinyl_adc_enclosure_base.stl # Watertight binary STL
│   ├── vinyl_adc_plexiglass_top.svg # 1:1 Spirit laser cutter SVG
│   ├── vinyl_adc_plexiglass_top.dxf # 1:1 AutoCAD R12 DXF
│   └── *.glb                      # 3D board exports from KiCad
├── hardware/kicad/                 # KiCad 10 schematics, boards & routing
│   ├── power/                     # Tier 1: Power & voltage reference board
│   ├── channel_l/                 # Tier 2 & 3: Modulator channel (milled twice)
│   ├── digital/                   # Tier 4: Digital clock & Pi interface
│   ├── sim/                       # 8x SPICE testbenches for loop validation
│   └── tools/                     # Python layout and netlist verification scripts
├── production/                     # Production-ready Gerbers and Excellon drill files for SRM-CAM
├── media/                          # Visuals, renders, and animations
│   ├── vinyl_adc_assembly.gif     # Looping 3D exploded view animation
│   ├── vinyl_adc_assembly.mp4     # 720p 24fps H.264 animation video
│   ├── noise_shaping_spectrum.png # Continuous-time 3rd-order FFT plot
│   ├── laser_engraved_lid.png     # Clear acrylic lid technical artwork
│   └── pcb_renders/               # Raytraced KiCad 3D renders of each PCB tier
└── sim/                            # Modulator numerical simulation models
```

---

## Interactive 3D Web Viewer

Test the 3D model and scrub the exploded assembly timeline directly in your browser:  
🔗 **[https://madsrudolph.github.io/vinyl-adc/](https://madsrudolph.github.io/vinyl-adc/)**

---

## Related Projects

- [**SRM-CAM (`gerber2rml`)**](https://github.com/MadsRudolph/srm-cam): Desktop CAM for the Roland SRM-20 CNC mill used to isolation-mill the PCBs for this project.

---

## License

MIT License — free for personal and educational use.
