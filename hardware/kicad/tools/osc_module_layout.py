#!/usr/bin/env python3
"""Layout script for the plug-in oscillator module.

Run:  py -3.13 osc_module_layout.py  ->  ../osc_module/vinyl_adc_osc.kicad_sch

The digital board that is ALREADY BUILT expects a 6.144 MHz oscillator can
in X1's DIP-8 socket, and that can is unobtainable.  This module is the same
Pierce oscillator the board revision bakes in -- blk_pierce, the identical
function, so the two can never drift apart -- on a coaster-sized single-sided
board with four pins underneath at the can's corner positions:

    pin 1  EN   (socket wires it to +5 V; the module leaves the pad empty)
    pin 4  GND
    pin 5  OUT  -> the 74HCT132 clock buffer on the digital board
    pin 8  VDD  <- +5 V from the socket

It is NOT part of the reference-sheet split -- check_split.py models X1 as
the can, and electrically this module IS that can.  Unplug it and drop in a
real can any day one turns up.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vinyl_adc_layout import (G, STUB, SKILL, blk_pierce, new_sheet,  # noqa: E402,F401
                              note_block, power_flags, assign_footprints,
                              write_project, FP_DIP)

OUT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "..", "osc_module"))
NAME = "vinyl_adc_osc"
TITLE = "Vinyl ADC  -  6.144 MHz oscillator module (plugs into X1)"


def compose(sh):
    note_block(sh, (G(24), G(13)),
               "OSCILLATOR MODULE  (Pierce, 74HCU04 + 6.144 MHz crystal -- "
               "fills the X1 DIP-8 socket on the digital board)", size=2.0)
    power_flags(sh, G(160), G(18), ("+5V", "GND"))

    # G(24), not G(14): the first spare gate's tie-low bus reaches
    # G(10) left of the block and lands on the sheet frame otherwise
    out = blk_pierce(sh, G(24), G(20))

    # The DIP-8 plug, drawn as an 8-pin connector so the pin NUMBERS land on
    # the socket's pads.  The symbol's pin rows sit at even-grid offsets from
    # its origin (pin 4 ON it, pin 5 one step below): origin at G(26) puts
    # pin 5 exactly on the buffer's output row.
    j1 = sh.place("Connector_Generic:Conn_01x08", "J1",
                  at=(G(76), G(26)), value="DIP-8 PLUG")
    sh.seg(out, j1.pin(5))
    # pin 4 above the output row, ground dog-legged UP so gnd's 2.54 mm
    # symbol drop cannot land on the output wire
    p4 = j1.pin(4)
    sh.seg(p4, (G(56), p4.y))
    sh.seg((G(56), p4.y), (G(56), G(22)))
    sh.seg((G(56), G(22)), (G(50), G(22)))
    sh.gnd((G(50), G(22)))
    # pin 8 below, the rail attached with rise=0 for the mirror-image reason
    p8 = j1.pin(8)
    sh.seg(p8, (G(64), p8.y))
    sh.seg((G(64), p8.y), (G(64), G(38)))
    sh.seg((G(64), G(38)), (G(58), G(38)))
    sh.rail((G(58), G(38)), net="+5V", rise=0)
    sh.nc(j1.pin(1), j1.pin(2), j1.pin(3), j1.pin(6), j1.pin(7))

    note_block(sh, (G(96), G(22)),
               "Fit machined pins at positions 1/4/5/8 only --\n"
               "the can's corners.  Pads 2/3/6/7 stay empty.\n"
               "Pin 1 is the socket's EN pull-up; the module\n"
               "does not need it and leaves the pad unwired.",
               size=1.27)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    sh = new_sheet(title=TITLE, project=NAME, paper="A4")
    compose(sh)
    missing = assign_footprints(sh)
    for part in sh.parts:
        if part.ref == "J1":
            part.footprint = FP_DIP.format(8)   # the socket's own pad field
    problems = sh.check()
    out = os.path.join(OUT_DIR, f"{NAME}.kicad_sch")
    sh.emit(out)
    write_project(out, sh.uuid)
    print(f"{NAME}: {len(sh.parts)} symbols, "
          + ("footprints OK" if not missing else f"{len(missing)} missing")
          + ", "
          + ("geometry OK" if not problems else f"{len(problems)} faults"))
    for p in problems[:20]:
        print("    ", p)
    return 1 if (problems or missing) else 0


if __name__ == "__main__":
    sys.exit(main())
