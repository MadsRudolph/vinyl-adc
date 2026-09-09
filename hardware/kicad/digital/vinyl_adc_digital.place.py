# vinyl_adc_digital rev B -- the crystal Pierce replaces the oscillator can.
#
#   Y1 6.144 MHz crystal + U9 74HCU04 Pierce -> J1 clock select
#     -> U3 74HCT132 schmitt buffer -> U4 74HC4040 divider
#        MCLK + PUMP    -> J4, the 2x8 stacking bus, up to the analogue boards
#        QL, QR         <- J4, into U6 74HC157, muxed by MCLK into DIN
#        BCLK/LRCLK/DIN -> U8 74HC4049 on +3V3 -> J2, down to the Pi
#
# Derived from the 4/4 placement in the kicad-place worked example; bands 1-2
# are unchanged in structure (supply caps by NEW refs: C13=U6, C11=U4,
# C10=U3, C15=U8).  Band 3's can-plus-jumper became the Pierce: U9 with its
# decoupling and the select header, then the crystal network in two rows
# directly beneath -- node B's three parts adjacent (R11-C17-Y1), node A's
# two below them, the row structure that took the plug-in module from four
# open links to a clean single-sided route.
#
# J4 and H1-H4 are LOCKED IN THE FILE at the stack's coordinates.
#
# FLOOR: >= 2 bridges bare on the old netlist; +3V3 + +5V + GND poured takes
# it to 0, and those pours also carry every supply pin, so the crystal rows
# only have their four local nets to route.

# cross_order="declared", and the level band names schmitt first: barycentre
# puts the buffer west, which sends BCLK, LRCLK and DIN the full board width
# from the divider -- FreeRouting left all three split.  Declared order puts
# U8 under U4: three short nets for one long CLK6M.
board(flow="y", grid=1.27, gap=2.54, block_gap=5.08, band_gap=3.81,
      margin=8.0, cross_order="declared")

lock("H1", "H2", "H3", "H4")

# --- band 1: the two chips that talk to the bus, directly under the bus ----
block("mux",     core="U6", axis="x", dress=[cap("C13", at="w")])
block("divider", core="U4", axis="y", dress=[cap("C11", at="e")])

# --- band 2: the level shifter with the Pi header, and the schmitt gate ----
block("schmitt", core="U3", axis="x", dress=[cap("C10", at="e")])
block("buffer",  core="U8", axis="y", dress=[cap("C15", at="w")], ring=["J2"])

# --- band 3: the Pierce oscillator, at the far end of the chain ------------
# J1 rings U9 for the same reason it ringed the can: the select header IS the
# oscillator's output connector (J1.1 = buffer out, J1.2 = gate, J1.3 = Pi's
# GPCLK0).
block("pierce", core="U9", axis="x", dress=[cap("C9", at="w")], ring=["J1"])

# --- bands 4-5: the crystal network, in net order ---------------------------
row("nodeb", parts=["R11", "C17", "Y1"], axis="x")
row("nodea", parts=["C16", "R10"], axis="x")

band("bus",   blocks=["mux", "divider"])
band("level", blocks=["schmitt", "buffer"])
band("clock", blocks=["pierce"])
band("xtalb", blocks=["nodeb"])
band("xtala", blocks=["nodea"])
