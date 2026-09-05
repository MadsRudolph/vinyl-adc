# Vinyl ADC

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
  <img src="media/showcase/assembly.gif" alt="Vinyl ADC 3D Exploded Assembly Animation" width="720">
</p>

<p align="center">
  <a href="media/showcase/README.md">Download MP4 videos &amp; website embeds</a>
</p>

<details>
<summary><strong>More views: product orbit and four-board close-up</strong></summary>

### Product orbit

![Vinyl ADC enclosure rotating through a full turn](media/showcase/orbit.gif)

### Four-board close-up

![Vinyl ADC power, right-channel, left-channel, and digital boards](media/showcase/electronics.gif)

</details>

<p align="center">
  👉 <strong><a href="https://madsrudolph.github.io/vinyl-adc/">Launch Live Interactive 3D Web Viewer &amp; Explosion Slider</a></strong> 👈
</p>

---

## Audiophile Engineering Specifications

| Specification | Target / Measured Performance | Design Rationale & Implementation |
|---|---|---|
| **Modulator Topology** | Continuous-Time CIFB (Cascade of Integrators, Feedback) | 3rd-order active RC loop with local resonator feedback (`G = 0.03`) |
| **Dynamic Range / SNR** | **68.3 dB measured in 20 kHz band** | Purposefully matched to the physical vinyl surface noise floor (~60–65 dB) |
| **Audio Output** | **24-bit / 48 kHz Linear PCM FLAC** | Decimated in software on Raspberry Pi CPU (CIC filter + compensation FIR) |
| **Modulator Sampling Rate ($F_s$)** | **1.536 MHz** ($32\times$ OverSampling Ratio) | Matches bandwidth constraints of DTU-stocked op-amps (`TL072` 3 MHz GBW) |
| **Master Clock ($F_{clk}$)** | **6.144 MHz Crystal Oscillator** (DIP-8) | Direct low-jitter oscillator ($<50\text{ ps}$ jitter vs. Pi PLL phase noise) |
| **Digital Stream Format** | Bit-Interleaved PDM on standard I2S bus | 3.072 Mbps data stream, read as 32-bit stereo audio frames at 48 kHz |
| **Analog Inputs** | Gold RCA Phono Jacks &amp; 5.08 mm Screw Terminals | Switchable input gain via front-panel multi-turn trim potentiometer |
| **Analog Grounding** | Star-ground topology with tonearm binding post | Eliminates 50 Hz turntable motor hum and ground-loop switching transients |
| **PCB Manufacturing** | Isolation-milled single-sided copper FR4 | Toolpaths generated via [**SRM-CAM**](https://github.com/MadsRudolph/srm-cam) on a **Roland SRM-20** mill |
| **Enclosure Dimensions** | $144.0\text{ mm} \times 144.0\text{ mm} \times 65.0\text{ mm}$ | 3D-printed PETG base with recessed laser-engraved $3.0\text{ mm}$ acrylic lid |

---

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

## The 4-Board PCB Stack

To overcome the routing limitations of single-layer CNC isolation milling (0.84 mm clearance between DIP pins), the system is split into four 100 × 100 mm boards interconnected by a 16-pin ribbon bus and M3 brass standoffs:

| Tier & Board | 3D Raytraced Board Render | Function & Key Components |
|---|:---:|---|
| **Tier 4 (Top)**<br>[`vinyl_adc_digital`](hardware/kicad/digital/) | <img src="media/pcb_renders/pcb_digital_3d.png" width="340" alt="Digital Board 3D Render"> | **Clock, Interleaving & Pi Interface:**<br>• 6.144 MHz crystal oscillator can (`X1`)<br>• `74HCT132` Schmitt-trigger clock buffer<br>• `74HC4040` binary clock divider ($F_s = 1.536\text{ MHz}$, $\text{BCLK} = 3.072\text{ MHz}$, $\text{LRCLK} = 48\text{ kHz}$)<br>• `74HC157` stereo bit-interleaving MUX<br>• `74HC4049` 5 V $\rightarrow$ 3.3 V level shifter to Raspberry Pi |
| **Tier 3**<br>[`vinyl_adc_channel_l`](hardware/kicad/channel_l/) | <img src="media/pcb_renders/pcb_channel_3d.png" width="340" alt="Left Channel Modulator 3D Render"> | **Left Channel Modulator:**<br>• 3rd-order active RC integrators (`TL072`)<br>• `LM311` high-speed comparator<br>• `74HC74` retiming flip-flop &amp; 1-bit DAC network<br>• Multi-turn input gain trim potentiometer<br>• Jumper set to Left (`pins 1-2`) |
| **Tier 2**<br>[`vinyl_adc_channel_r`](hardware/kicad/channel_r/) | <img src="media/pcb_renders/pcb_channel_3d.png" width="340" alt="Right Channel Modulator 3D Render"> | **Right Channel Modulator:**<br>• Identical artwork to Tier 3 (milled twice)<br>• Jumper set to Right (`pins 2-3`)<br>• Independent ground plane &amp; analog reference |
| **Tier 1 (Base)**<br>[`vinyl_adc_power`](hardware/kicad/power/) | <img src="media/pcb_renders/pcb_power_3d.png" width="340" alt="Power Supply Board 3D Render"> | **Power & Reference Generation:**<br>• `74HC244` + `1N5817` charge-pump negative rail<br>• Low-noise precision virtual ground reference (`TL072`)<br>• High-capacity bulk reservoir &amp; post-filter network<br>• 4× M3 mounting holes seated onto enclosure floor bosses |

---

## PCB Fabrication with SRM-CAM & Roland SRM-20

All boards in this project are physical hardware designed for single-sided isolation milling on the **Roland SRM-20** desktop CNC mill at the DTU FabLab.

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
│   ├── vinyl_adc_enclosure_base.3mf # PrusaSlicer print file
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
