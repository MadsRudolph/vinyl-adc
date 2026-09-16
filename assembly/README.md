# Local assembly bench

Public guide: **https://vinyl-adc.madsrudolph.dev/**. Current bench plan: [16 September 2026](sessions/2026-09-16/README.md) for the rev B digital board and both populated channels (no results recorded yet). Latest manual handoff: [6 September 2026](sessions/2026-09-06/README.md), rev A digital board with an external clock, with screenshots and a structured `session.json`. The public guide is static and never controls instruments. Browser progress is origin-specific: export a backup from localhost and restore it on the hosted domain. Local SDK captures are not automatically uploaded.

Start from the repository root:

```sh
python assembly/serve.py
```

## Publishing

`python assembly/build_site.py` produces `assembly/site-dist/`, excluding installers, extracted vendor packages, Python caches and local SDK captures. Published manual sessions are explicitly stored under `sessions/`. The Cloudflare Pages project is `vinyl-adc-assembly`; its deployment workflow lives in `MadsRudolph/madsrudolph.dev`, alongside the existing Cloudflare credentials. Dispatch `deploy-assembly.yml` there with the full pushed Vinyl ADC commit SHA. The portfolio site has its own independent deployment.

Open http://localhost:8080. The server listens only on 127.0.0.1 and serves this directory. No npm packages, internet connection, or external fonts are needed. Use the same browser and URL for the same saved progress. `--port 8081` selects another port.

The top of the page contains the **visual Korad KD3005D + AD3 BNC testing guide** at `/#visual-wiring`. Ten manual WaveForms steps show each wire, the actual PCB pad layout, and enlarged endpoints. Clock pairs and mux cases change the illustrated connections. All endpoint nets are checked against the PCB snapshot before diagrams are shown. Drawings use component-side orientation and include pin-1 markers and KiCad coordinates. They show pad/trace locations, not exact component housings or physical probe access.

The current fixture uses two 10× BNC probes (with matching WaveForms attenuation), DC coupling jumpers, W1 coax with 0 Ω adapter source impedance and a suitable board-end breakout, plus the remaining V+ flywire for +3.3 V. The Korad provides +5 V; the power board generates its negative rail from a 192 kHz pump input. The rev B digital board carries its own crystal Pierce oscillator, so W1 is only used for the power-board pump stimulus and the channel audio tone. The SDK scripts accept the same BNC fixture with `--probe 10`; the visual guide remains for manual WaveForms work. Do not mix fixtures within a run or run WaveForms alongside SDK tests.

Reference notes and troubleshooting remain below the visual guide. Link navigation opens the selected section, and printing temporarily expands the reference notes. Printing the visual guide captures the currently selected wiring step, not all ten steps. The guide is read-only and never enables instrument outputs or records a hardware PASS.

The guide provides separate checklists for all four physical boards, component sorting, PCB coordinates and pin/net tables, a zoomable component-side/underside reference, top-joint tracking, wire links, inspection, and initial powered checks. Select a part in the list or map. Drag the map to pan. Save backup exports all progress and bench notes; Restore replaces current progress after confirmation. Print prints the current stage and selected reference, not the entire guide.

## Source of truth

`generated/boards.json` is extracted read-only from the three current PCB files; channel L artwork is used twice, with independent progress and J21 selection. The guide includes all 114 schematic component positions, plus the board-only wire anchors and mounting holes. Existing PCB/project files are not edited.

Regenerate after PCB edits using a Python installation with KiCad's `pcbnew` module and `kicad-cli` on PATH:

```sh
python assembly/generate.py
python assembly/verify.py
```

Regeneration also runs KiCad DRC and stores its full reports. The generated data carries source SHA-256 hashes and a timestamp. Match the physical fabricated revision yourself; regenerating does not reset progress. Export progress before changing revisions and do not treat previous checkmarks as validation of changed artwork.

Component-side joint detection uses same-net F.Cu tracks touching pad geometry. Current boards have bottom-only pours. Vias are accepted only where they sit on a same-net wire-link anchor (the rev B digital board has two stacked GND vias at WL7a); the verifier rejects any other via or top pour so the extractor cannot silently omit required joints. The schematic's through-hole pads assume plated holes; DRC alone cannot validate unplated assembly.

The channel has 20 top-side pads per copy, including U20.1, U22.4, U23.1, U23.2, U23.10 and U24.4. Power/digital default to bottom-only copper as specified in fabrication notes, with a construction selector on Prepare for actual double-sided boards. On the rev B digital board, 16 wire-link anchors form the MCLK, CLK6M, DIN, +3V3, GND and PI_DIN links, with component-side socket joints at U4.10, U6.1, U6.4 and U8.11. On power, connect WL1A to WL1B.

The map renders track centerlines and schematic pad markers; copper pours, physical body outlines and exact pad shapes are intentionally omitted. Use the real KiCad board for physical clearance and solder access. The current rev B digital DRC reports no clearance or connectivity violations; it lists two silkscreen overlaps (WL1b/WL5a reference text over J4/U4 outlines), five co-located-hole warnings from the two GND vias stacked on the WL7a pad (one physical drill), and footprint-library warnings for the local WireLink library. The guide preserves those reports and calls for inspection rather than declaring them passed.

Initial power instructions are a bench checklist, not a validated commissioning specification. The repository does not establish current-limit settings, acceptance tolerances, or a complete audio capture/calibration procedure.

## AD3 testing and resistor markings

**Board tests · AD3** adds per-board fixture plans and interactive Python SDK tests. See [bench/README.md](bench/README.md). Reports and raw captures remain local; the page reads report history without controlling hardware. Official installers are in [downloads](downloads/README.md).

Resistors show five-band colour diagrams and written colour names in both sorting and component details. The final brown band assumes ±1% tolerance; actual component markings and multimeter readings take precedence. The 4R75 resistor uses a silver multiplier band.
