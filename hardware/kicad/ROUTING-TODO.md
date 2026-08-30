# What is left before these boards can be cut

State on 2026-08-30. The **channel artwork is now DOUBLE-SIDED** (cut twice from
the two pieces of double-sided stock); power and digital stay single-sided.
**No board has met its full acceptance bar yet, so nothing has been exported to
`production/`.**

Re-measure before trusting any of this:

```
py -3.13 tools/remaining_links.py                       # the links, one by one
"C:/Program Files/KiCad/10.0/bin/python.exe" \
    ~/.claude/skills/kicad-place/scripts/place_route.py check <board>.kicad_pcb
py -3.13 ~/.claude/skills/kicad-place/scripts/place_score.py <board>.kicad_pcb
```

## Where the three artworks stand

| | sides | links left | wire bridges | vias | GND pour | DRC beyond the `.kicad_dru` exception | placement |
|---|---|---:|---:|---:|---|---|---|
| power | single | **0** | 1 | 0 | 1 piece, 0 stranded | 1 silk_overlap | 4/4 |
| channel | **double** | **1** | 0 | **0** | whole, 0 stranded, 9 fragments | 8 isolated_copper, 13 silk_overlap | 4/4 |
| digital | single | 13 | 0 | 0 | 2 pieces, 1 stranded, 19 fragments | none | 3/4 |

The channel board went from **13 links to 1** by using the top layer. The one
left is `VREF_N`: an F.Cu track at (68.88, 70.30) to **J7 pin 6** at
(73.81, 32.54) — the reference coming off the stacking bus, a ~38 mm run.
FreeRouting will not close it at 30 or 100 passes, with the whole top layer free.

## Two gates now read "wrong" on the channel board, on purpose

`place_route.py check` and `place_score.py` are single-sided tools. On the
channel artwork they report:

```
FAIL  single_sided  10 F.Cu bridge runs (52 segments)
FAIL  onelayer      52 F.Cu segments are wire bridges to hand-solder, not copper
```

**Both are wrong about this board.** Those 52 F.Cu segments are *milled copper
on the top side*, not wire. The metric that still means something on a
double-sided milled board is **vias**, because the holes are drilled and never
plated — a via is a wire pushed through and soldered both sides. That check
reads `ok 0 vias`, and it is the one to watch. Everything else those tools
report — connectivity, oracles_agree, netclass, track width, pour islands —
is layer-aware and still valid.

## Why "leftovers on top" and not a full re-route

Four architectures measured on the same placement, same clearance, every output
refilled by KiCad before judging:

| | links left | vias | GND pour | pads needing a TOP joint | of those, on DIP sockets |
|---|---:|---:|---|---:|---:|
| single-sided (what it was) | 13 | 0 | whole, 6 fragments | 0 | 0 |
| signals on top, GND plane on bottom | 6 | 0 | **whole, 1 piece** | 91 | 28 |
| both layers, GND poured | 2 | 1 | **split in 3**, 12 fragments | 55 | 15 |
| **leftovers on top (shipped)** | **1** | **0** | whole, 9 fragments | **20** | **6** |

The reasoning that picked the last one: **a link left open is a wire, and a wire
is soldered at both ends** — exactly the two joints a milled top-side trace
between the same two pads needs. So converting leftovers to top copper costs
nothing in soldering and removes the wire. The other two modes re-route from
scratch and move joints that were already fine, buying a better plane (or two
fewer links) for 35–71 extra top-side joints.

"Signals on top" is the electrically prettiest board — an uncut ground plane
under every trace — and if the noise floor ever needs it, it is one command
away. It costs 28 socket-pin joints on the top side instead of 6.

## Milling it double-sided

- **Stock:** 110 × 110 mm against a 100.1 × 100.1 mm outline — about 5 mm of
  margin all round.
- **Registration is already solved.** The four M3 mounting holes sit at exactly
  **±44.00 mm from the board centre in both axes** — a perfect square,
  symmetric about the centre in X and in Y. Flipping the board about either
  axis maps the hole pattern onto itself, so two dowel pins through a diagonal
  pair register the second side with no extra tooling holes and no error to
  measure. Drill those four first, on the first side.
- **Mill B.Cu, flip, mill F.Cu.** The CAM does the mirroring for whichever side
  you cut second — do not pre-mirror the Gerbers. `export_production.ps1`
  already writes both `F.Cu` and `B.Cu`.
- **Top-side soldering: 20 pads.** Fourteen are on headers or axial/radial parts
  where the whole pad is reachable. **Six are DIP socket pins** — U20.1, U22.4,
  U23.1, U23.10, U23.2, U24.4 — and those have **1.78 mm of pad outside the IC
  body** (roughly 1.1 mm outside a typical socket). That margin is exactly why
  this process mandates the `_LongPads` DIP footprints. It is tight but it is
  reachable with a fine tip; solder those six before seating anything that
  covers them.
- The 8 `isolated_copper` are stray pour fragments with no pad on them. Not a
  connectivity fault, and they will move when the pour is refilled after the
  last link goes in, so they are not worth chasing yet.

## power — 0 links, 1 bridge, and a long way round for the return current

Fully connected, ground pour whole, no stranded pads. The one bridge is a single
**-5V** wire, J3.16 (61.11, 32.54) to U2.4 (85.19, 56.81) — 35 mm diagonally.

**The direction-cost theory did not hold.** The ladder already defaults to
`against_preferred_direction_trace_costs 1.0`, and re-routing traded that 1
bridge for **3 missing links** — a worse board. It does cost the return path:
`cutspan` **fails at 1.551 board diagonals** (219 mm further than straight).
The fresh route fixes that (0.483) at the price of those 3 links, and is kept at
`scratchpad/rt_power_1/run1/Tiso/`. That trade is yours; the connected board is
what is on disk.

If you have a third piece of double-sided stock later, `route_2layer.py
--mode leftovers-top` would almost certainly absorb this bridge into top copper
the same way it did on the channel board.

## digital — 13 links, and the real problem is the placement

Routed from nothing (3/20 nets, zone unfilled, 60 unconnected) down to 13 links,
0 DRC violations, 0 bridges. Reproducible: two independent ladder runs both
landed on 13, rung for rung.

**But 13 against a floor of 2 is a placement problem, not a router problem:**

| | power | channel | digital |
|---|---:|---:|---:|
| `nbr_rank` (want <= 0.25) | 0.227 | 0.177 | **0.512** |
| ratsnest crossings / part | 0.0 | 0.36 | **1.85** |
| HPWL / part / diagonal | 0.080 | 0.127 | **0.495** |

Digital is the only board failing the cohesion gate, and by more than 2x, while
carrying five times the channel board's crossings on a third of the parts. More
router passes will not fix that.

The unpulled lever is **pouring**: `place_floor.py --pours` says GND alone
leaves digital at floor 2, but **`+3V3 + +5V + GND` takes it to 0** — three
pours, exactly at the budget before FreeRouting wedges. That means partitioning
B.Cu into three plane regions, a real design change carrying gotcha 25 (two
same-priority zones over one outline can invert their fill once there are
tracks). Highest-value thing left on this board, and not attempted.

## Tooling added

- `tools/remaining_links.py` — the unrouted links, pad by pad with coordinates.
- `tools/route_2layer.py` — double-sided routing (`signals-top`, `both-layers`,
  `leftovers-top`). Two traps are handled in there and written up in the source:
  FreeRouting does not echo `(type fix)` wires back into the `.ses`, so a
  locked-copper run must **merge** rather than let `ImportSpecctraSES` replace;
  and 1.9.0 headless can sit forever after writing a complete `.ses`, so the
  wait is bounded and the file on disk decides.

## Also stale, not touched

`PCB-NOTES.md` still documents the superseded four-board build — a 160×120 mm
`vinyl_adc_common` and three IDC ribbons — and now also predates the channel
board going double-sided.

`production/` was already empty apart from its `.gitignore`.
