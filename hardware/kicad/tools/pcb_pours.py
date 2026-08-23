#!/usr/bin/env python
r"""Copper pours: a GND plane, and a +5V network in the corridors. Idempotent.

    & "C:\Program Files\KiCad\10.0\bin\python.exe" tools\pcb_pours.py ..\vinyl_adc.kicad_pcb

These are a routing prerequisite, not decoration. FreeRouting only treats a net
as a plane if there is a filled pour on it; without one it routes that net as
ordinary traces. Measured on this board: with a GND pour, GND needs **zero**
track segments. Without one it would need more than any other net.

+5V is the next worst, and it is worth its own pour for the same reason. Routed
as traces it took 102 segments on the copper side plus 33 more on top -- and on
a single-sided board "on top" means a wire you solder by hand. It reaches
roughly twenty pads spread over the whole board, so there is no arrangement of
parts that makes it local.

The +5V pour is a spine, not a plane: one horizontal bar in the empty corridor
between the power band and channel L, and one vertical bar in the corridor
between the analog half and the digital column. They cross, so they fill as one
region, and every IC is then a short hop from the rail.

**This does cut the ground plane**, and that is a real cost paid deliberately:
on one copper layer any connected +5V network is a slot in the ground, and the
only choice is where to put it. It runs along the corridors BETWEEN the
functional bands, so each band -- both analog channels, the power section, the
digital column -- keeps unbroken ground underneath it, and only the crossings
between bands see the discontinuity.

Which is why every bar STOPS SHORT OF THE BOARD EDGE. Carried out to the edge
it cuts the ground in two outright: the only ground copper joining the halves
is then the sliver between the bar's end and the outline, and one signal track
crossing that sliver strands every ground pad on the far side. Ending each bar
about 12 mm in leaves a ground bridge at both ends too wide for the router to
sever by accident.
"""
import os
import sys

import pcbnew
from pcbnew import VECTOR2I, FromMM, ToMM

INSET_MM = 0.85          # the cnc profile's clearance

# board -> net -> (priority, [rectangles in mm]). Higher priority wins the
# overlap, so GND retreats from the +5V bars rather than the two fighting over
# the copper. None = the whole board, inset.
POURS = {
    "common": {
        "GND": (0, None),
        # Two spines in the corridor between the power band and everything
        # else. Only PUMP and -5V's own feed cross it, so neither spine gets
        # severed -- see the floorplan's note on why that is the whole game.
        "+5V": (1, [(32.0, 54.0, 168.0, 60.0)]),
        "-5V": (1, [(32.0, 64.0, 168.0, 70.0)]),
    },
    "channel": {
        "GND": (0, None),
        # The chain occupies the top half; these live in the empty bottom
        # half, so the ground under the analog signal path is never cut and
        # nothing has to cross a spine to get anywhere. VREF_N earns one
        # because it feeds all three integrators: as traces it was the third
        # worst net on the board.
        "+5V":    (1, [(34.0, 92.0, 200.0, 100.0)]),
        "-5V":    (1, [(34.0, 106.0, 200.0, 114.0)]),
        # VREF_N had a spine here too and it wedged FreeRouting: four planes
        # on one board and it never got past reading the DSN -- twenty-four
        # minutes, no progress, no error. Three is fine. If VREF_N turns out
        # to need one, give it the spine and route it as a fourth pass rather
        # than handing the router four planes at once.
    },
    "digital": {
        "GND": (0, None),
        # one bar is enough here: both rows of logic sit against it.
        "+5V": (1, [(32.0, 58.0, 148.0, 66.0)]),
        # +3V3 reaches three pads that are already next to each other, so it
        # is two tracks, not a plane. A pour for it would only cut the ground.
    },
}

def edge_bbox(board):
    """The Edge.Cuts extent.

    Straight from the board rather than by walking GetDrawings(): pcbnew's
    SWIG container typemaps are not reliably registered in every interpreter
    this runs under, and when they are missing the walk fails with
    "'SwigPyObject' object is not iterable" on a board that is otherwise
    perfectly readable.
    """
    bb = board.GetBoardEdgesBoundingBox()
    if bb.GetWidth() <= 0:
        raise SystemExit("no Edge.Cuts outline -- draw one before placement")
    return (ToMM(bb.GetLeft()), ToMM(bb.GetTop()),
            ToMM(bb.GetRight()), ToMM(bb.GetBottom()))


def add_zone(board, net, shape, priority):
    """`shape` is either (x0, y0, x1, y1) or a list of (x, y) outline points."""
    pts = (shape if not isinstance(shape, tuple)
           else [(shape[0], shape[1]), (shape[2], shape[1]),
                 (shape[2], shape[3]), (shape[0], shape[3])])
    zone = pcbnew.ZONE(board)
    zone.SetLayer(pcbnew.B_Cu)
    zone.SetNet(net)
    zone.SetAssignedPriority(priority)
    zone.SetIsFilled(True)
    zone.SetLocalClearance(FromMM(INSET_MM))
    zone.SetMinThickness(FromMM(0.25))
    # SOLID pad connections, not thermal reliefs, and that is forced rather
    # than chosen. A relief needs the pour to surround the pad enough to grow
    # two spokes; on this process the pour cannot enter between adjacent DIP
    # pins at all (0.84 mm gap, and it needs 0.85 either side), so it reaches
    # most ground pins from one side only. Measured on the digital half: with
    # reliefs, four pads starved and eight came out unconnected; solid, every
    # ground pad connects and both counts go to zero. KiCad's default 0.5 mm
    # relief gap would have been unmillable anyway -- narrower than the tool.
    #
    # The cost is real and belongs in the build notes: a lead soldered into a
    # filled plane sinks the iron's heat. Use a 40 W+ iron and give each joint
    # a couple of extra seconds.
    zone.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    # Drop fill islands that reach no pad: floating copper is nothing but
    # extra milling and something to lift off the laminate later.
    zone.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    outline = zone.Outline()
    outline.NewOutline()
    for x, y in pts:
        outline.Append(FromMM(x), FromMM(y))
    board.Add(zone)
    return zone


def main(path):
    base = os.path.basename(path)
    which = next(k for k in ("digital", "channel", "common") if k in base)
    pours = POURS[which]
    print(f"{which} pours")
    board = pcbnew.LoadBoard(path)
    bx0, by0, bx1, by1 = edge_bbox(board)

    # Idempotency, and the trap in it: board.Remove() on a ZONE leaves the SWIG
    # runtime unable to wrap anything the board hands back afterwards -- every
    # later call returns a bare SwigPyObject and dies on its first attribute,
    # on a board that is perfectly readable ("no destructor found" in the
    # noise is the tell). It only bites on the SECOND run, when there are
    # zones to remove, which is exactly when you have stopped expecting it.
    # So: drop them, write, and start again from the file.
    stale = [z for z in board.Zones() if z.GetNetname() in pours]
    if stale:
        for z in stale:
            board.Remove(z)
        pcbnew.SaveBoard(path, board)
        board = pcbnew.LoadBoard(path)
    ins = INSET_MM
    made = []
    for name, (priority, rects) in pours.items():
        net = board.FindNet(name)
        if net is None:
            print(f"no {name} net on this board -- skipped")
            continue
        if rects is None:
            rects = [(bx0 + ins, by0 + ins, bx1 - ins, by1 - ins)]
        for shape in rects:
            add_zone(board, net, shape, priority)
            xs = [q[0] for q in shape] if not isinstance(shape, tuple) else shape[0::2]
            ys = [q[1] for q in shape] if not isinstance(shape, tuple) else shape[1::2]
            made.append((name, (min(xs), min(ys), max(xs), max(ys))))

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(path, board)
    for name, (x0, y0, x1, y1) in made:
        print(f"  {name:5s} pour on B.Cu  {x1 - x0:6.1f} x {y1 - y0:6.1f} mm "
              f"at ({x0:.1f}, {y0:.1f})")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "vinyl_adc_common.kicad_pcb")
