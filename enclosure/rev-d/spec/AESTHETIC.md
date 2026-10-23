# Rev D enclosure: design-language brief

The box will sit on the shelf beside a Schiit Saga (Saga+ or Saga S), a Schiit Modi DAC and a Fosi Audio amplifier. Nothing called "Fosi CA3" turned up anywhere; Fosi's current small stereo/mono amp is the **ZA3**, and its look matches what Mads described, so this brief assumes the ZA3. Confirm it. The other possibility is the older V3, which is visually close.

It should read as the fourth member of that stack: a premium object, not a project box. It must also do the things Mads asked for: show the PCB, use a laser-cut acrylic lid and the board's own mounting holes, put diffusers on the 8 LEDs, and let him press SW1/SW2 without a tool.

## 1. The neighbours

| | Schiit Saga+ | Schiit Saga S | Schiit Modi+ | Fosi ZA3 |
|---|---|---|---|---|
| Size W × D × H | 9 × 6 × 2″ (229 × 152 × 51 mm), tube +1.25″ above the top [1] | 230 × 150 × 50 mm [2] | 5 × 3.5 × 1.25″ (127 × 89 × 32 mm), 1 lb [3] | 154.9 × 183.9 × 50.8 mm (W/D order is ambiguous between listings), aluminium [4][5] |
| Body | Schiit "¾-width" chassis: a bent sheet-metal U top cover over a flat base | Same family chassis | Schiit small chassis, same idiom | Aluminium-alloy chassis, fine sandblasted / matte, bevelled edges [5] |
| Finish | Silver or black [1] | Silver or black | Silver or black | Matte black with orange accents [6][7] |
| Front | Big volume knob, input switch [1], small LEDs | Volume knob, input/mode, LEDs | One button + small LED row | **Symmetric:** big orange/copper knob dead centre, two toggles flanking it (XLR/RCA, stereo/mono), one orange power LED [6][7] |
| Sides/top | Flat, plain. The Saga+ tube pokes through the top [8]. | Flat | Flat | Aluminium side panels with orange mesh vent grilles [6] |

The Schiit construction details (folded U-shell, exposed side screws, thick flat faceplate) come from general product knowledge, not a cited spec page. Schiit's own product pages now return HTTP 410. The sizes are from the cited listings.

### What makes them read as premium

1. **Few, flat, uninterrupted faces.** Each part is a box made of large planes: one fold line, crisp edges and nothing decorative. Schiit's look is the bent-metal U: top and sides are one continuous skin with a single radius at each fold.
2. **Honest fasteners.** Schiit shows its screws, which are small, evenly spaced and matched in colour. Visible screws read as "serviceable instrument", not "cheap", *if* they line up on a grid.
3. **One strong control, everything else quiet.** One big knob carries the face. LEDs are tiny pinpricks, not spotlights. The ZA3 has a single orange LED, and Schiit uses small white LEDs.
4. **Consistent height lines.** Saga S, Saga+ (body) and ZA3 are all about **50 mm / 2″** tall; the Modi is 32 mm. On a shelf, a shared top line is what makes mixed brands look like a system.
5. **Material honesty and texture.** Fine bead-blast or brush, no gloss on the body. Gloss appears only where it means something: a knob face or a glass window.
6. **Proportion.** Low and wide, with the depth about equal to or greater than the width, so it never looks like a cube. Saga is 1.5 : 1 wide; ZA3 is about 1 : 1.2.

### How a printed + laser-cut box gets there

- **Height and width:** the 50.8 mm overall height line (SPEC §4) matches the Saga S and ZA3 exactly. The width is 155 mm, the same as the ZA3. Depth is 168 mm. The front face reads as a 155 × 51 mm faceplate, a sibling of the ZA3's.
- **Faces:** print large planar faces with no sculpting. Use a 1.0 mm × 45° chamfer on every horizontal outside edge (it also kills elephant foot) and a 3 mm radius on the four vertical corners. That is the bent-metal look.
- **Texture:** print the cosmetic faces **against a textured PEI sheet**. This gives a uniform fine "sandblasted" grain that matches the ZA3's bead-blast. Faces that print vertically get horizontal layer lines, which read as a brushed finish if they are 0.15 mm and seam-free; put the seam on the back edge. Matte black PETG (or ASA) for the body. Do not use fuzzy skin.
- **Fasteners:** use **exposed black (or stainless) ISO 7380 button-head screws** on a deliberate grid: four through the lid corners, equal insets, all the same length. That is Schiit's honesty in a form that can be printed.
- **Glass:** the acrylic is the "glass". Keep it clear, polish the edges with flame or fine abrasive, and set it **flush** into a rebate so the top reads as one plane, with a 1.2 mm frame of the body visible around it.
- **LEDs:** turn them into quiet, even dots, about 3 mm across, softly glowing, with colour preserved. No hot spots. LEDs are never seen bare.
- **Accent:** one accent colour, used once. Either a copper/orange button cap to rhyme with the ZA3 knob, or a white bezel inlay to rhyme with Schiit silver. Pick by which box sits next to it.

## 2. Concepts (ranked)

### ★ 1. "Faceplate + glass": printed tray, bezel faceplate, flush clear lid (recommended)

| Part | What it is |
|---|---|
| **Tray** | One PETG print: floor, left/right/back walls, the three M3 HAT posts, four Pi bosses, vents and port cut-outs. Outer 155 × 168 mm, body height 47.6 mm, 3 mm walls. The back wall is a clean **rear panel**: the Pi's Ethernet and USB on the right, and on the left 2 panel RCA jacks (L/R) and a 4 mm ground binding post. Short shielded pigtails run along the left-wall gutter to J20/J60/J3. Then every cable on the shelf leaves from the back, as on the Schiit units. USB-C power stays on the right side, or goes to the back with the optional right-angle extension. |
| **Bezel faceplate** | A separate printed part (y −5.4 to ≈ 14, full width, top flush at z 25). It covers the LED/switch strip and is the "face" of the product. **Front face:** plain, textured, with a debossed `VINYL ADC` wordmark at the left (0.4 mm deep, filled or left shadowed). **Top surface:** a row of 8 light windows and 2 buttons. **Front-top edge:** a 45° × 4 mm chamfer that the light windows break through, so the LEDs are visible both from the listening position (front) and from above. Fixed by two M3 screws from inside and keyed into the tray. |
| **LED diffusers** | A one-piece opaque "comb" printed into the underside of the bezel: one cell per LED on the **9.50 mm pitch**, centres from SPEC §5. Each cell holds a **light pipe** printed separately in **natural (unpigmented) PETG**, Ø 4.6, from just above the LED dome (cup ID 5.3, 2 mm deep) up to the window. The pipe is frosted at its tip; a single 0.6 mm layer of white PLA over it is an even stronger diffuser. The cup sits on a **compliant (sprung) foot or a 1 mm foam ring**, so the 8.6–11.6 mm LED height uncertainty never preloads the LEDs. Expected attenuation is about 3–5×, set by tip thickness. Opaque cell walls stop the always-on CLIP reds bleeding into their neighbours. |
| **Buttons** | Two printed buttons through the bezel top at (107.25, 7.25) and (121.25, 7.25). Cap Ø 10, standing 0.8 mm proud, with a 0.5 mm chamfer. Engrave ⏻ on SW1 and a dot on SW2. The cap colour is the single accent. Each stem is guided in a 6 mm bore (0.2 mm clearance per side) and ends 0.3 mm above the plunger; a stem shoulder takes the overtravel against the bezel. The tact switch is the return spring. Stem length is set from the measured plunger height, so leave a 1 mm sanding allowance on the tip. |
| **Lid** | 3 mm clear cast acrylic, about 152.6 (x) × 147 (y) mm: x −10.2…142.4, y ≈ 14…161.4, leaving a 1.2 mm body frame on the sides and back. The exact front edge is set by the bezel depth. It drops into a 3.0 mm rebate in the tray and bezel tops (0.3 mm gap all round) and is held by 4 × M3×8 button heads into heat-set inserts. Insert bosses hang from the wall tops at the four corners: the back-right one stays above the USB jacks (above z +5). Optionally laser-etch fine legends on the acrylic underside: `LINE IN L / GND / R` over the terminal blocks, `TP L / DIG / R` over the headers, a 140 × 136 hairline frame. Etched underneath, they read through the glass without collecting dust. |
| **Feet** | Four 12 mm rubber feet in 0.5 mm recesses, 20 mm in from each corner. |

**Why it wins:**
- It shows ~90 % of the board through one flat pane.
- It gives the box a real *face* in the Schiit/Fosi idiom.
- It solves LED glare and button pressing in one part, and that part is the one that most needs to look good, so it can be printed face-down on textured PEI and reprinted alone.
- It uses H1/H2/H3 plus the four Pi columns, and has the cleanest cable story (all at the back).

The lid comes off with four screws for probing.

### 2. "Open sandwich": acrylic top and bottom on a printed perimeter frame

A printed rectangular frame, about 25 mm tall, carries the walls and port cut-outs. Clear acrylic plates close it top and bottom, so the Pi and the HAT's underside show through a glass floor, and the whole stack hangs on the frame from the M3 holes. LED diffusers are individual natural-PETG thimbles on each LED, seen through the top. Buttons are acrylic-guided plungers through the lid.

- **Pros:** shows the most electronics and is very "maker premium".
- **Cons:** two acrylic sheets plus a tall frame look more like a display case than hi-fi. There is no real faceplate, so it won't sit with the Saga/ZA3. A glass floor puts the Pi's microSD and solder side on show and needs standoff feet. The front LEDs are only visible from above.

### 3. "Plinth": low printed base, board floats, acrylic hood

A low printed plinth (about 18 mm tall) holds the Pi and the posts. A folded or bonded 5-sided acrylic hood drops over the HAT, so there are no opaque walls above the board. The LEDs get thimble diffusers and the buttons go through the hood.

- **Pros:** maximum visibility from every angle.
- **Cons:** bent or bonded acrylic is a much harder cut and fabrication job. Port cut-outs land in acrylic, which is brittle at USB/HDMI plug loads. Dust gets in. It reads as a showcase, not a component, and the height line is lost.

**Recommendation: concept 1.** If Mads wants even more board on show, concept 1 accepts one upgrade without redesign: a second 3 mm acrylic window in the left wall (x −11.4, between y 20 and 140). It sits at the analogue input side, where the MKT boxes and terminal blocks are the most photogenic parts.

## 3. Colour and material callout

| Element | Material | Finish |
|---|---|---|
| Tray, bezel | PETG or ASA, matte black (to sit with the ZA3), or light grey/silver (to sit with a silver Saga) | Textured PEI on the bezel face; 0.15 mm layers on the walls |
| Light pipes | Natural / clear PETG | Frosted tip, 0.6 mm white cap layer optional |
| Diffuser comb | Same black as the bezel | Opaque, 1.2 mm walls between cells |
| Buttons | PLA or PETG in the accent: copper/orange (ZA3 rhyme) or white (Schiit rhyme) | Top face printed on textured PEI |
| Lid | 3 mm cast acrylic, clear (smoke grey is an option, but it hides the green PCB) | Flame-polished edges, legends etched underneath |
| Screws | ISO 7380 button head, black oxide or A2 stainless, all M3×8 on the outside | All heads on the same grid |

## References

1. Saga+ spec: 9″ W × 6″ D × 2″ H, +1.25″ tube, 6 lb, silver/black, knob + input switch. https://addictedtoaudio.com.au/products/schiit-audio-saga-stereo-pre-amplifier-1 — manual: https://www.schiit.com/public/upload/PDF/saga%20plus%20manual.pdf
2. Saga S, 230 × 150 × 50 mm (StereoNet review). https://stereonet.com/reviews/schiit-audio-saga-s-preamp-aegir-power-amplifier-review
3. Modi+, 5 × 3.5 × 1.25″, 1 lb (Schiit page via search; the page now returns 410). https://www.schiit.com/products/modi-plus
4. Fosi ZA3, 154.9 × 183.9 × 50.8 mm (Cowcotland spec sheet; Kirstein lists D × W × H in the same numbers). https://www.cowcotland.com/articles/4297/test-fosi-audio-za3-pour-les-geeks.html
5. ZA3 aluminium chassis, fine sandblasted, bevelled edges. https://www.kirstein.de/en/HiFi/HiFi-amplifiers-and-AV-receivers/Fosi-Audio-ZA3-Mono-Stereo-HiFi-Amplifier.html
6. ZA3 front layout, orange knob/LED, side grilles. https://www.audioreviews.org/fosi-audio-za3-review-dw/ · https://www.soundphilereview.com/reviews/fosi-audio-za3-review-51805/
7. ZA3 "solid orange-finished volume knob", XLR/RCA and stereo/mono switches. https://www.shuttergroove.com/reviews/hi-fi/fosi-audio-za3-review-compact-power-amplifier/
8. Saga+ ¾-width chassis shared with the Modius/Magnius; the tube sits above the top plane. https://futureaudiophile.com/schiit-saga-preamplifier-reviewed/
