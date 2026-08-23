#!/usr/bin/env python
r"""Deterministic floorplan: every part where the CIRCUIT wants it, then locked.

    & "C:\Program Files\KiCad\10.0\bin\python.exe" tools\pcb_floorplan.py ..\vinyl_adc.kicad_pcb

KiCad-Autoplace optimises half-perimeter wire length. It has no idea this is a
delta-sigma ADC, and on this board that goes wrong twice over.

Left to itself it interleaved everything: the two analog channels overlapped by
59 x 70 mm, the 6.144 MHz divider sat inside both of them, and the charge pump
-- 32 mA switching at 192 kHz -- was spread across the whole board among the
integrators. For a converter whose design target is a 68 dB noise floor that is
close to the worst arrangement available. It also routed badly: 66 % of nets on
the first single-sided pass.

Locking the ICs into bands fixed the ICs and not the passives, for a reason
worth writing down: **a decoupling capacitor's nets are +5V and GND, and both
of those are everywhere**, so wire length gives the placer no reason at all to
put it next to the chip it decouples. It scattered them across the board, which
is exactly the one thing a decoupling cap must not be.

So the placement is done here instead:

It does both halves; which one is chosen by the file name.

    COMMON, 160 x 120                   CHANNEL, 190 x 145 (built twice)
    y  38  C1  U1 charge pump            y  56  J20 -> RV20 -> U20 -> U21
    y  56  ------ +5V bar ------                with the passives packed
    y  66  ------ -5V bar ------                round them in one band
    y  90  J3 | U5 U7 U2 | J5 J6         y  92  +5V and -5V spines
                                         y 138                        J7

    DIGITAL, 140 x 100
    y  42  X1 J1 U3 U4        (the clock, made once)
    y  58  ------- +5V bar -------
    y  84  J4 U6 U8 J2

U5 (the retiming flip-flops) and U7 (the DAC drive gates) are 74HC parts on
the ANALOG board, because they are inside the modulator's feedback loop and
its delay is compensated by a coefficient that a ribbon cable would falsify.
They sit in the right-hand column between the two channel bands, equidistant
from both, since each package serves L and R.

Three rules behind it:

  * all digital in one column on the right, so the 6.144 MHz clock edges and
    the 3 Mbps DIN never cross an analog band;
  * the two channels in separate horizontal bands, each flowing left to right
    exactly as the schematic reads;
  * every input on the left edge, the Pi header on the right.

The charge pump sits along the top rather than between the channels. Its
192 kHz ripple is deliberately 4x the output rate so it lands on a CIC null,
and the reference is ratiometric so rail noise cancels -- but there is still no
reason to put a switching current next to integrator 1 when the top edge is
free.
"""
import os
import sys

import pcbnew
from pcbnew import VECTOR2I, FromMM, ToMM

# ---------------------------------------------------------------- anchors --
# The parts whose position is a circuit decision rather than a packing one.
# ref -> (x mm, y mm, rotation deg)
PLANS = {}

# COMMON, 160 x 120.
#
# Laid out from the connectivity, not from the schematic's reading order. The
# two channel ribbons talk to the quantiser, the DAC gates and the reference,
# so those four sit in one band together; the digital ribbon talks to the
# quantiser and the charge pump, so it goes at the other end of the same band.
# The power section is the only thing on its own, along the top.
#
# That leaves the corridor between the two bands carrying just TWO nets --
# PUMP and -5V -- which is what makes it usable as supply spine. Every net
# that crosses a spine severs it, and a severed spine is worse than no spine:
# the supply then needs more hand-soldered links than it saved.
PLANS["common"] = dict(gap=2.0, anchors={
    "C1":  (30, 34, 0),          # 470u reservoir at the +5V entry
    "U1":  (62, 38, 90),         # 74HC244 charge pump, lying down
    "C4":  (84, 38, 90),         # 10u flying cap, hard against the driver
    "D1":  (95, 30, 90),
    "D2":  (95, 46, 90),
    "C5":  (106, 38, 0),
    "R1":  (114, 38, 90),
    "C6":  (122, 38, 0),
    # The lower band is ordered by COUNTING CROSSINGS, which is the only thing
    # that decides a single-sided board. Each net that has to get past a
    # package costs a detour round it, and often a wire bridge. Three orders
    # were built and measured, everything else the same:
    #
    #   J5/J6 U5 U7 U2 J3   14 crossings   15 wire bridges
    #   U2 J5/J6 U7 U5 J3   ~10            25   (the ribbons in the middle,
    #                                            which looked obviously right)
    #   J3 U5 U7 U2 J5/J6    8             see below
    #
    # The winner puts the digital ribbon next to the flip-flops it clocks and
    # next to the charge pump above it, and the two channel ribbons next to
    # the reference they carry -- so MCLK, QL, QR, PUMP and both VREFs are all
    # short, and only CMP and the DAC drives have to travel.
    "J3":  (32, 90, 0),          # ribbon to the digital board, left edge
    "U5":  (68, 90, 0),          # 74HC74 retiming flip-flops
    "U7":  (105, 90, 0),         # 74HC04 DAC drive gates
    "U2":  (140, 90, 0),         # TL072 reference buffer + inverter
    "J5":  (170, 82, 0),         # ribbon to channel L, right edge
    "J6":  (170, 120, 0),        # ribbon to channel R, right edge
},
decouple={
    "C2":  ("C1", "right"),      # 100n beside the bulk reservoir
    "C3":  ("U1", "above"),      # 74HC244, lying down
    "C7":  ("U2", "above"),      # TL072: one cap per rail
    "C8":  ("U2", "below"),
    "C12": ("U5", "above"),
    "C14": ("U7", "above"),
},
bands={
    "reference": (124, 108, 158, 136, ["R2", "R3", "R4", "R5"]),
})

# CHANNEL, 190 x 145, built twice.
#
# One band, because the modulator is one signal chain and reads best as one:
# line in, three integrators, the resonator inverter, the comparator. The
# whole lower half of the board is then empty, and that is where the supply
# and reference spines go -- so the ground under the analog chain stays
# unbroken and nothing has to cross a spine to get anywhere.
PLANS["channel"] = dict(gap=2.0, anchors={
    "J20": (30, 56, 0),          # LINE IN, left edge
    "RV20": (62, 56, 0),         # level trimmer, screwdriver-reachable
    "U20": (108, 56, 0),         # TL074: all four sections
    "U21": (170, 56, 0),         # LM311 quantiser
    "J7":  (190, 138, 0),        # ribbon to the common board
},
decouple={
    "C25": ("U20", "above"),     # TL074: +5V above, -5V below
    "C26": ("U20", "below"),
    "C27": ("U21", "above"),
},
bands={
    "channel": (28, 28, 205, 84, [
        # front end, then integrator 1, 2, 3, the resonator inverter and the
        # quantiser's summing node -- the same left-to-right the sheet has
        "C20", "R20", "C21",
        "R21", "R22", "R23", "C22",
        "R24", "R25", "R26", "R27", "C23",
        "R28", "R29", "R30", "C24",
        "R31", "R32",
        "R33", "R34", "R35", "R36", "R37"]),
})

PLANS["digital"] = dict(anchors={
    "X1":  (36, 42, 0),          # 6.144 MHz can, in a DIP-8 socket
    "J1":  (58, 42, 0),          # clock-select jumper, beside the can
    "U3":  (88, 42, 0),          # 74HCT132 buffer
    "U4":  (130, 42, 0),         # 74HC4040 divider
    "J4":  (36, 84, 0),          # ribbon to the analog board, left edge
    "U6":  (80, 84, 0),          # 74HC157 interleave mux
    "U8":  (122, 84, 0),         # 74HC4049 level shift to 3.3 V
    "J2":  (152, 84, 0),         # TO PI GPIO, right edge, pins in a column
},
gap=2.0,
decouple={
    "C9":  ("X1", "above"),
    "C10": ("U3", "above"),
    "C11": ("U4", "above"),
    "C13": ("U6", "above"),
    "C15": ("U8", "above"),
},
bands={})

# Millimetres of air between neighbouring parts -- not the netclass clearance,
# which is what makes a board legal rather than routable. On a single-sided
# board with 1 mm tracks nothing passes between two adjacent DIP pins, so every
# connection goes round the outside of a package, and parts packed shoulder to
# shoulder leave the router nowhere to do that.
#
# It is NOT monotonic, which is worth knowing before you turn it up. Measured
# on the digital half, same placement otherwise: at 2.0 mm the router finished
# every signal net and left six wire bridges; at 3.5 it left none, and gave up
# on seven nets instead -- the extra air had pushed the decoupling caps out
# into the channels the router wanted. So it is per board, and it is a measured
# number rather than a principle.
GAP = 2.0
AXIAL_VERTICAL = True     # stand resistors on end: a row of summing resistors
                          # packs three times tighter and their top pads line
                          # up on the node they share


def size_mm(fp, rot=None):
    """Outline size in mm at rotation `rot` (current rotation if None)."""
    if rot is not None:
        fp.SetOrientationDegrees(rot)
    bb = fp.GetBoundingBox(False, False)
    return ToMM(bb.GetWidth()), ToMM(bb.GetHeight())


def place(fp, cx, cy, rot=0):
    """Put the footprint's OUTLINE CENTRE at (cx, cy), and lock it.

    A footprint's position is not its centre -- it is wherever the library
    author put the origin, which for every DIP here is up at pin 1. Placing a
    DIP-14 "at (104, 88)" actually lands its body centred on (107.8, 95.6),
    7.6 mm south-east of the intended spot, and everything computed from that
    assumption -- decoupling offsets, band packing, collision tests -- is
    wrong by a different amount for every package. So place provisionally,
    measure where the outline actually went, and correct.
    """
    fp.SetOrientationDegrees(rot)
    fp.SetPosition(VECTOR2I(0, 0))
    bb = fp.GetBoundingBox(False, False)
    ox = ToMM(bb.GetLeft()) + ToMM(bb.GetWidth()) / 2.0
    oy = ToMM(bb.GetTop()) + ToMM(bb.GetHeight()) / 2.0
    fp.SetPosition(VECTOR2I(FromMM(cx - ox), FromMM(cy - oy)))
    fp.SetLocked(True)


def box(fp):
    bb = fp.GetBoundingBox(False, False)
    return (ToMM(bb.GetLeft()), ToMM(bb.GetTop()),
            ToMM(bb.GetRight()), ToMM(bb.GetBottom()))


def hits(cand, taken):
    ax0, ay0, ax1, ay1 = cand
    for bx0, by0, bx1, by1 in taken:
        if ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1:
            return True
    return False


def pack(board, name, rect, refs, placed, taken):
    """Lay `refs` out left to right inside `rect`, stepping over what is there.

    The anchors live INSIDE these rectangles -- U20 sits in the middle of
    channel L's band, and its two decoupling caps directly above and below it
    -- so a packer that only wraps at the right edge drops parts straight on
    top of them. First fit on a 1 mm grid, skipping anything occupied.
    """
    x0, y0, x1, y1 = rect
    step = 1.0
    for ref in refs:
        fp = board.FindFootprintByReference(ref)
        if fp is None:
            print(f"   {name}: {ref} not on the board")
            continue
        rot = 90 if (AXIAL_VERTICAL and ref.startswith("R")) else 0
        fp.SetOrientationDegrees(rot)
        w, h = size_mm(fp)
        spot = None
        y = y0
        while y + h <= y1 and spot is None:
            x = x0
            while x + w <= x1:
                cand = (x - GAP / 2, y - GAP / 2, x + w + GAP / 2, y + h + GAP / 2)
                if not hits(cand, taken):
                    spot = (x, y)
                    break
                x += step
            y += step
        if spot is None:
            print(f"   {name}: no room left for {ref}")
            continue
        x, y = spot
        place(fp, x + w / 2, y + h / 2, rot)
        taken.append((x - GAP / 2, y - GAP / 2,
                      x + w + GAP / 2, y + h + GAP / 2))
        placed.append(ref)


def main(path):
    global GAP
    base = os.path.basename(path)
    which = next(k for k in ("digital", "channel", "common") if k in base)
    GAP = PLANS[which].get("gap", GAP)
    anchors = PLANS[which]["anchors"]
    decouple = PLANS[which]["decouple"]
    bands = PLANS[which]["bands"]
    print(f"{which} floorplan")
    board = pcbnew.LoadBoard(path)
    placed, missing, taken = [], [], []

    def claim(fp):
        x0, y0, x1, y1 = box(fp)
        taken.append((x0 - GAP / 2, y0 - GAP / 2,
                      x1 + GAP / 2, y1 + GAP / 2))

    for ref, (x, y, rot) in anchors.items():
        fp = board.FindFootprintByReference(ref)
        if fp is None:
            missing.append(ref)
            continue
        place(fp, x, y, rot)
        claim(fp)
        placed.append(ref)

    for cap, (host, side) in decouple.items():
        fp = board.FindFootprintByReference(cap)
        hostfp = board.FindFootprintByReference(host)
        if fp is None or hostfp is None:
            missing.append(cap)
            continue
        # derive the offset from the two real outlines rather than guessing:
        # a DIP-16 is 2.5 mm taller than a DIP-14 and a radial electrolytic is
        # three times the height of a disc
        rot = 90 if side in ("left", "right") else 0
        cw, ch = size_mm(fp, rot)
        hx0, hy0, hx1, hy1 = box(hostfp)
        hcx, hcy = (hx0 + hx1) / 2, (hy0 + hy1) / 2
        dy = (hy1 - hy0 + ch) / 2 + GAP
        dx = (hx1 - hx0 + cw) / 2 + GAP
        pos = {"above": (hcx, hcy - dy), "below": (hcx, hcy + dy),
               "left": (hcx - dx, hcy), "right": (hcx + dx, hcy)}[side]
        place(fp, pos[0], pos[1], rot)
        claim(fp)
        placed.append(cap)

    for name, (x0, y0, x1, y1, refs) in bands.items():
        pack(board, name, (x0, y0, x1, y1), refs, placed, taken)

    left = [fp.GetReference() for fp in board.GetFootprints()
            if fp.GetReference() not in placed]
    for fp in board.GetFootprints():
        fp.SetLocked(fp.GetReference() in placed)

    pcbnew.SaveBoard(path, board)
    print(f"{len(placed)} parts placed and locked")
    if left:
        print(f"{len(left)} left to the placer: {' '.join(sorted(left))}")
    if missing:
        print("NOT FOUND:", " ".join(missing))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1
                  else "vinyl_adc_common.kicad_pcb"))
