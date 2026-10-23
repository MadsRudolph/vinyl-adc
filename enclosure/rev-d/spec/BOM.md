# Rev D enclosure: hardware BOM (concept 1)

Every line was checked against Parts Bin (`partsbin.py search` and `check`, 2026-10-21). **Parts Bin has no mechanical hardware.** Home stock lists only electronic parts, and the DTU shop's "Mounting" category is solder lugs, TO-220/TO-3 bushings and pot hardware. So every fastener, standoff, foot, sheet and panel connector below comes out as **buy**.

Two caveats:
- Mads may still have M3 hardware from the rev C stack: `docs/shopping-list.md` ordered 16 × M3×11 standoffs plus screws and nuts. Parts Bin does not track it, so check the drawer first.
- Filament is not tracked in Parts Bin either.

| # | Item | Qty | Spec | Used for | Source |
|---|---|---|---|---|---|
| 1 | M3 brass heat-set insert | 7 (+3 spare) | M3 × 5.7 mm, OD ≈ 4.6 (e.g. Ruthex RX-M3x5.7). Pilot 4.2 × 6.5 deep, checked with `enclosure/m3_insert_fit_coupon.stl`. | 3 HAT posts (H1/H2/H3), 4 lid corners | **buy** |
| 2 | M3 × 8 button head, ISO 7380 | 4 | Black oxide or A2 stainless; all external screws the same finish | Lid corners | **buy** |
| 3 | M3 × 6 button head, ISO 7380 | 3 | Same finish | HAT → posts | **buy** |
| 4 | M3 × 8 socket or pan head | 2 | Internal, finish irrelevant | Bezel → tray, from inside | **buy** |
| 5 | M3 nylon washer | 3 | ID 3.2, OD ≤ 7 (the NPTH holes have no ring; H1 allows Ø 9.6 max) | Under the HAT screws | **buy** |
| 6 | M2.5 × 11 mm F-F standoff (brass or nylon) | 4 | Rev D BOM item. The Pi hangs on these. | HAT ↔ Pi | **buy** (unless already fitted on the stack) |
| 7 | M2.5 × 5 pan or button head | 4 | | HAT top → standoff | **buy** |
| 8 | M2.5 × 10 socket or pan head | 4 | Head ≤ Ø 5, in a 3 mm counterbore under the floor | Floor → Pi → standoff | **buy** |
| 9 | Self-adhesive rubber feet | 4 | Ø 12 × 3.2 mm (e.g. 3M Bumpon SJ5382 class). Height sets the 50.8 overall line. | Feet | **buy** |
| 10 | Cast acrylic sheet, clear | 1 | 3.0 mm, ≥ 160 × 160 mm (plus an offcut for test cuts) | Lid (Mads laser-cuts) | **buy** |
| 11 | Filament: matte black PETG (or ASA) | ≈ 250 g | | Tray, bezel, diffuser comb | **buy** (unless on the shelf) |
| 12 | Filament: natural / clear PETG | ≈ 10 g | Unpigmented | 8 light pipes | **buy** (unless on the shelf) |
| 13 | Filament: accent PLA/PETG (copper-orange or white) | ≈ 5 g | | 2 button caps | **buy** (unless on the shelf) |
| 14 | RCA panel jack, insulated, red + white | 2 | Ø 9.5–10 mm panel hole (rev C used 9.5 mm bores), ≤ 5 mm panel thickness | Rear-panel LINE IN L/R | **buy** (rev C hardware may be reusable) |
| 15 | 4 mm binding post, black | 1 | Ø 6 mm panel hole (as rev C) | Rear-panel tonearm ground → J3 | **buy** |
| 16 | Shielded audio hookup wire + ring/fork for the ground | ≈ 0.5 m | | RCA → J20/J60, post → J3 pigtails | **buy** (or home offcuts) |
| 17 | Raspberry Pi 4 heatsink, optional | 1 | ≤ 15 × 15 × 5 mm, thermal tape | SoC, under the HAT (6.2 mm clearance) | **buy** |
| 18 | USB-C right-angle male → panel female extension, optional | 1 | 90° plug, panel-mount female, ≤ 15 cm | Brings power to the rear panel | **buy** |

**Nothing from the DTU shop.** The shop carries no mechanical hardware, RCA jacks or binding posts. Its "Mounting Hardware" item is potentiometer hardware and does not apply here.

**Electrical alternative for the LED glare (not part of this BOM).** The cleaner fix is a larger series resistor per LED, from the DTU shop's E96 range (**shop**), alongside the diffusers. That is a board change, so it is left to Mads.
