# PCB — four CNC-milled, single-sided boards from three designs

Copper is isolation-milled on **B.Cu** with an 0.8 mm flat end mill; the
silkscreen is laser-etched on top. Everything is through-hole and every IC is
socketed.

| Design | Outline | Parts | Built | What it holds |
|---|---|---:|---:|---|
| `vinyl_adc_common` | 160 × 120 mm | 24 | ×1 | power in, charge pump, ±2.5 V reference, the quantiser and 1-bit DAC |
| `vinyl_adc_channel_l` | 190 × 145 mm | 31 | **×2** | one modulator channel: line in, three integrators, resonator, comparator |
| `vinyl_adc_digital` | 140 × 100 mm | 13 | ×1 | 6.144 MHz clock, divider, interleave mux, level shift, Pi header |

`vinyl_adc.kicad_sch` is the whole converter on one page. **It has no board and
is not meant to have one** — it is the sheet the SPICE benches link back to and
the one `check_intent.py` reads. `vinyl_adc_channel_r.kicad_sch` has no board
either: it is the same drawing as channel L with every refdes forty higher, and
exists so the split can be checked. **One channel artwork is milled twice.**

## Why four boards

The one-board version was built and routed. Measured, single-sided: **45 wire
bridges**, 17 vias and 25 ground pads the pour could not reach. Splitting it in
two — analog and digital — fixed the digital half (6 bridges) and not the
analog one, which stayed at 39–43 however it was arranged. 82 parts on the
machine's largest blank is 0.37 parts/cm²; the digital half that routes well is
0.09.

So the two channels came off onto their own board. They are identical, so it is
one more *design*, not two, and the stereo pair is two copies of one artwork.

```
        common board                                  digital board
   +5V in <--------------------- J3 --- J4 ------------ from the Pi, 12-way
   charge pump -> -5V              MCLK ->
   reference   -> +/-2.5V          <- QL, QR
   U5 quantiser, U7 DAC gates      PUMP ->
        |          |
        J5         J6      14-way each
        |          |
   channel L    channel R      J7 on each: both supplies, both references,
   (one artwork, built twice)   CMP out, DACP and DACN back
```

**The modulator loop now crosses a ribbon** — comparator out on the channel
board, flip-flop and DAC gates on the common board, DAC drive back. That is
worth being explicit about, because an earlier revision of these notes argued
it must never happen. The delay the loop's `k0` coefficient compensates is the
LM311's **200 ns**; 10 cm of ribbon adds about **0.5 ns**, a quarter of one
percent of it. What does not cross is anything that would matter: the DAC's
own reference is the 74HC04's supply, and that supply and its reservoir sit
with the gates.

`tools/check_split.py` is the gate that keeps the split honest. It welds each
link's pin *n* to its partner's pin *n*, drops the connectors, and requires the
resulting partition of every (ref, pin) node to be **identical** to the
reference sheet's. It also proves the two channel boards are one artwork:
channel R's netlist must be channel L's with every refdes number raised by
forty. Move a block to the wrong board and every other check still passes;
this one does not.

## The links

Three ribbons, all shrouded IDC box headers on 2.54 mm pitch:

```
  J3 / J4  2x6, 12-way            J5 / J7 and J6 / J7  2x7, 14-way
   1 GND    2 +5V                  1 GND    2 +5V
   3 GND    4 MCLK                 3 GND    4 VREF_P
   5 GND    6 QL                   5 GND    6 VREF_N
   7 GND    8 QR                   7 GND    8 CMP_x
   9 GND   10 PUMP                 9 GND   10 DACP_x
  11 GND   12 +5V                 11 GND   12 DACN_x
                                  13 GND   14 -5V
```

On a 2×N Odd_Even symbol the odd pins are the left column, so putting every
ground on an odd pin gives a solid ground column down one side of the drawing —
and, because an IDC ribbon takes conductor *n* to pin *n*, a grounded conductor
either side of every signal in the cable. MCLK is why that matters: its jitter
is what sets this converter's noise floor, 20 ps buying a 102 dB floor where
1 ns leaves 68.

**Shrouded, not bare pin strips.** These rows carry supplies against grounds;
reversed, a bare strip puts +5 V straight across the ground column. The
shroud's key makes that impossible. The shop carries neither the headers nor
the sockets, so they go on the same order as the oscillator can — see
`docs/bom.md`.

## Regenerating a board from its schematic

```bash
cd "hardware/kicad"
B=vinyl_adc_common        # or vinyl_adc_channel_l, vinyl_adc_digital
"/c/Program Files/KiCad/10.0/bin/kicad-cli.exe" sch export netlist --format kicadsexpr -o $B.net $B.kicad_sch
py -3.13 "$SKILL/scripts/pcb_netlist_json.py" $B.net /tmp/$B.json
KICAD_PCB_SIZE_MM=160x120 KICAD_PCB_FAB=cnc KICAD_LASER_EXTRA_LIBS="$PWD/lib" \
  "/c/Program Files/KiCad/10.0/bin/python.exe" "$SKILL/scripts/pcb_build.py" /tmp/$B.json $B.kicad_pcb
"/c/Program Files/KiCad/10.0/bin/python.exe" tools/pcb_floorplan.py $B.kicad_pcb
"/c/Program Files/KiCad/10.0/bin/python.exe" tools/pcb_pours.py     $B.kicad_pcb
```

`$SKILL` is the `kicad-laser-pcb` skill directory. Sizes: `160x120` common,
`190x145` channel, `140x100` digital. `pcb_build.py` **ceils** the outline, so
a size must be asked for as whole millimetres or it comes out a millimetre
larger than requested.

Both scripts pick their plan from the file name, so there is one floorplan
script and one pour script, not six.

## The floorplans are hand-written, and that is the point

```
  COMMON, 160 x 120                   CHANNEL, 190 x 145 (built twice)
  y  38  C1  U1 charge pump           y  56  J20 -> RV20 -> U20 -> U21
  y  56  ------ +5V bar ------               with the passives packed
  y  66  ------ -5V bar ------               round them in one band
  y  90  J3 | U5 U7 U2 | J5 J6        y  92  +5V and -5V spines
                                      y 138                        J7
  DIGITAL, 140 x 100
  y  42  X1 J1 U3 U4        (the clock, made once)
  y  58  ------- +5V bar -------
  y  84  J4 U6 U8 J2
```

The auto-placer was tried first and is wrong for this design in two separate
ways.

**It interleaves the blocks.** Optimising half-perimeter wire length, it put
the two analog channels on top of each other (59 × 70 mm of overlap), the
6.144 MHz divider inside both, and the charge pump — 32 mA switching at
192 kHz — spread across the whole board among the integrators. For a converter
whose whole design target is a 68 dB noise floor, that is close to the worst
arrangement available. It also routed badly: **66 %** of nets on the first
single-sided pass.

**Locking the ICs fixes the ICs and not the passives.** A decoupling
capacitor's two nets are +5V and GND, and both of those span the entire board,
so wire length gives the placer no reason whatsoever to put the cap next to the
chip it decouples — and it did not. Decoupling caps are therefore pinned to
their host IC explicitly, at a distance derived from the two real outlines so
it is right for a DIP-8 and a DIP-20 alike.

Two things the hand floorplans do that are worth copying:

- **The common board's lower band is ordered by counting crossings.** Every
  net that has to get past a package costs a detour round it and often a wire
  bridge, so the order of the five things in that band is worth measuring
  rather than reasoning about. Three were built, everything else identical:

  | order | crossings | wire bridges |
  |---|---:|---:|
  | `J5/J6  U5 U7 U2  J3` | 14 | 15 |
  | `U2  J5/J6  U7 U5  J3` | ~10 | **25** |
  | `J3  U5 U7 U2  J5/J6` | 8 | 16 |

  The middle one is the arrangement that looks obviously right — the ribbons
  next to everything they talk to — and it is the worst of the three. The
  shipped order is the last: the digital ribbon beside the flip-flops it
  clocks and the charge pump above it, the channel ribbons beside the
  reference they carry. Counting crossings predicted the *direction* and not
  the size; only building all three told the truth.
- **The channel board keeps its whole lower half empty for the supply
  spines.** The modulator is one signal chain and reads best as one row; the
  spines then live below it, so the ground under the analog path is never cut
  and nothing has to cross a spine to get anywhere.

`tools/pcb_blocks.py` reports where each functional block landed and which
blocks overlap. On all three floorplans every block occupies its own rectangle.

## Nothing passes between two adjacent DIP pins

This is the single fact that shapes the layout. 2.54 mm pitch with 1.7 mm pads
leaves **0.84 mm** between neighbouring pads. A 1.0 mm track needs 0.85 mm of
clearance either side — 2.7 mm of corridor. It does not fit, and no narrower
track helps either: even a zero-width track would need 1.7 mm.

So **every track has to go round the outside of a package**, and so does the
copper pour. A board packed to look neat leaves the router nowhere to do that,
and it gives up on the last few nets rather than routing them the long way
round. The `GAP` between neighbouring parts is therefore a measured number per
board rather than a principle — and it is **not monotonic**. On the digital
half, same placement otherwise: at 2.0 mm the router finished every signal net
and left six wire bridges; at 3.5 it left none, and abandoned seven nets
instead, because the extra air had pushed the decoupling caps out into the
channels it wanted.

## Footprints

Assigned in `tools/vinyl_adc_layout.py`, not in the GUI — that script owns the
schematics, so anything set by hand would be wiped the next time it runs.

| Part | Footprint |
|---|---|
| resistors | `R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal`, stood on end |
| ceramics (100n, 1n5, 220p) | `C_Disc_D5.0mm_W2.5mm_P5.00mm` |
| 2u2 film | `C_Rect_L11.0mm_W6.3mm_P10.00mm_MKT` — **measure the real part** |
| 10u, 220u | `CP_Radial_D8.0mm_P3.50mm` |
| 470u | `CP_Radial_D10.0mm_P5.00mm` |
| 1N5817 | `D_DO-41_SOD81_P10.16mm_Horizontal` |
| every IC | `Package_DIP:DIP-<n>_W7.62mm_LongPads` |
| X1 oscillator | DIP-8 **socket**, not `Oscillator_DIP-8`: the can is socketed like everything else, and a socket wants all eight pads |
| trimmers | `Potentiometer_Bourns_3296W_Vertical` — **measure the real part** |
| screw terminals | `TerminalBlock_bornier-2_P5.08mm`, vendored into `lib/` |
| J3, J4 | `Connector_IDC:IDC-Header_2x06_P2.54mm_Vertical` |
| J5, J6, J7 | `Connector_IDC:IDC-Header_2x07_P2.54mm_Vertical` |

Two of those are assumptions, flagged above: the 2u2 film cap's lead pitch and
the trimmer body. Both are cheap to fix before cutting and expensive after.

The bornier terminal blocks were **deleted from KiCad 10's stock library**.
They live in `lib/TerminalBlock.pretty` and are registered in the project's own
`fp-lib-table`, which KiCad reads at *project* load — so reopen the project,
not just the board, after touching it. One `fp-lib-table` in this directory
serves every project here.

## Pad gaps against the 0.8 mm end mill

The mill cannot enter a gap narrower than its own diameter, and a gap it cannot
enter ships as a short. Every footprint was measured:

| Part | Min pad gap | |
|---|---|---|
| axial passives | 3.4 mm and up | fine |
| radial electrolytics | 1.90 mm | fine |
| bornier terminals | 2.08 mm | fine |
| trimmer | 1.10 mm | fine |
| DIP-8/14/16/20 LongPads | 0.94 mm | fine |
| **2.54 mm headers (J1–J7)** | **0.84 mm** | needs a DRC exception |

Each board has a `.kicad_dru` relaxing the clearance to 0.8 mm *only* between
two pads of the same header footprint. The full 0.85 mm stays in force
everywhere else. That gap is set by the header's own pin pitch, not by anything
we cut, and it still clears the tool.

## Pours

`tools/pcb_pours.py`: a GND plane over the whole board, and supply spines in
the corridors between the functional bands.

These are a routing prerequisite, not decoration. FreeRouting only treats a net
as a plane if there is a filled pour on it. Measured both ways on the digital
board, same placement:

| | B.Cu | F.Cu (wire bridges) | vias |
|---|---:|---:|---:|
| GND as a **plane** | 98 segments | **0** | 0 |
| GND as an ordinary **net** | 193 segments | 60 segments = 14 bridges | 2 |

Four details in that script are load-bearing and none is obvious:

- **A net that crosses a spine severs it.** A track plus its 0.85 mm clearance
  either side is 2.7 mm of no-copper; run one across a 6 mm bar and the bar is
  in two pieces, which then need hand-soldered links of their own. So the
  spines go where almost nothing crosses them, and the floorplans are arranged
  to make that true rather than the other way round.
- **Every spine stops ~12 mm short of the board edge.** Carried out to the edge
  it cuts the ground plane in two outright: the only ground copper joining the
  halves is the sliver between the bar's end and the outline, and one signal
  track crossing that sliver strands every ground pad on the far side.
- **Pads connect to the pour solidly, not through thermal reliefs.** A relief
  needs the pour to surround the pad enough to grow spokes, and on this process
  the pour cannot enter between adjacent DIP pins at all — so it reaches most
  ground pins from one side only. Measured on the digital board: with reliefs,
  four pads starved and eight came out unconnected; solid, every ground pad
  connects and both counts go to zero. (KiCad's default 0.5 mm relief gap would
  have been unmillable anyway — narrower than the tool.) **The cost is real and
  belongs in the build notes: use a 40 W+ iron and give each ground joint a
  couple of extra seconds.**
- **Fill islands that reach no pad are dropped**, so there is no floating
  copper to mill round or to lift off the laminate later.

**Three planes is the limit.** With four -- the channel board briefly had
+5V, -5V, VREF_N and GND -- FreeRouting never got past reading the DSN:
twenty-four minutes, no progress, no error, no CPU pattern that looked like
work. Three is fine and routes in minutes. If a fourth net ever needs a spine,
give it one and route it as a separate pass rather than handing the router four
planes at once.

There is also a pcbnew trap in there worth knowing about anywhere else you
script zones: **`board.Remove()` on a ZONE leaves the SWIG runtime unable to
wrap anything the board hands back afterwards.** Every later call returns a
bare `SwigPyObject` and dies on its first attribute access, on a board that is
perfectly readable — "no destructor found" in the noise is the tell. It only
bites on the *second* run, when there are zones to remove, which is exactly
when you have stopped expecting it. `pcb_pours.py` drops the stale zones, saves,
and re-loads from the file.

## What it actually came out at

Measured with `tools/pcb_report.py` and KiCad's own DRC, after routing,
pouring and filling:

| Design | B.Cu | wire bridges | vias | pads off the pour |
|---|---|---:|---:|---:|
| common | 243 seg, 1327 mm | 16 | 11 | 0 |
| channel (each of two) | 151 seg, 1419 mm | 10 | 4 | 3 |
| digital | 101 seg, 841 mm | 6 | 1 | 0 |
| **a stereo ADC** | | **42** | **20** | **6** |

plus six places where a supply *track* comes out in two pieces (three on the
common board, three on the digital one) and wants a link across the gap. Call
it **fifty hand-soldered joints for the set**, against 45 wire bridges, 17 vias
and 25 stranded ground pads for the one-board version.

**Be clear about what the split did and did not buy.** It did not halve the
wire count. What it bought is that every ground pad now reaches the plane
(25 stranded became 6), the boards are small enough to build and debug one at
a time, and two of the four are the same board. The bridge count barely moved.

Two levers are left, both untried, and they are the ones worth pulling before
cutting copper:

- **Narrower tracks.** The `cnc` profile's 1.0 mm track is a robustness choice,
  not a constraint from the mill: what the mill dictates is the 0.8 mm *gap*.
  At 0.6 mm the corridor a track needs between two obstacles falls from 2.7 mm
  to 2.3 — about 15 % more usable width everywhere on the board, applied to the
  exact quantity that is short. 0.6 mm of 35 µm copper carries something like
  1.8 A; the largest current here is the charge pump's 32 mA.
- **Two TL072s per channel instead of one TL074.** Seventeen of the channel
  board's resistors have to cluster round a single 19 mm package, because all
  four integrator sections live inside it — and nothing passes between DIP
  pins, so they all compete for the same few approaches. Two duals let the
  integrator pairs sit 40 mm apart, each with its own resistor cluster and its
  own summing node. It costs one more socket and one more 100 n per channel,
  and both parts are stocked.

## Routing

Single-sided: all copper on B.Cu, components on top. Any F.Cu track is a wire
bridge to solder, so `tools/pcb_report.py` counts them and never rolls them
into a "routed %".

```bash
"$SKILL/scripts/route_board.ps1" -Pcb vinyl_adc_common.kicad_pcb -KeepPlacement
```

`-KeepPlacement` is required: the floorplan is deliberate and every part is
locked.

**The script sometimes stops after `lockdsn`,** on a `PCB_VIA::GetWidth called
without a layer argument` assertion, and never imports stage 2 — the board is
then left with stage 1 only, which looks like a beautifully bridge-free route
and is really a board with thirty unrouted nets. Check `pcb_report.py` against
DRC's unconnected count every time; if stage 2 is missing, import it by hand:

```bash
"/c/Program Files/KiCad/10.0/bin/python.exe" "$SKILL/scripts/pcb_route.py"     ses <board>.kicad_pcb "$TEMP/kicad-laser/<board>2.ses"
```

Then, either way:

```bash
"/c/Program Files/KiCad/10.0/bin/python.exe" tools/pcb_pours.py <board>.kicad_pcb
py -3.13 tools/pcb_report.py <board>.kicad_pcb
```

`tools/pcb_stitch.py` will reconnect pour islands the routing cuts off, by
maze-routing from each stranded pad back to the main body of the pour on a
0.25 mm grid. It is a maze router and not a stub search because a stub cannot
get round the end of a track, and that is exactly the move required. It reports
what it cannot solve rather than leaving it quiet — and on these boards it
usually has nothing to do, because the spine placement above stops the islands
forming in the first place.
