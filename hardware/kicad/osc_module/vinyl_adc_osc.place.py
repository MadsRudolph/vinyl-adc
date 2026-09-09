# Placement intent for the plug-in oscillator module (40x44 mm).
# The DIP-8 plug mates with the X1 socket (pad 1 NW); the 74HCU04 lies along
# the flow with its Pierce pins on the south row, and the crystal network
# sits in two rows directly beneath: node B's three parts adjacent in one
# row, node A's two beneath them.  Wide gaps: on a single-sided board the
# 1.27 mm packing this DSL defaults to leaves no corridor for a 1.0 mm
# track at 0.85 mm clearance, and FreeRouting left 4 links open until the
# gaps grew.
board(flow="y", grid=1.27, gap=2.54, block_gap=2.54, band_gap=2.54,
      margin=2.5)

# The plug must present pad 1 at its NW corner, exactly like the socket it
# mates with -- the class vote turned it 180 and that flips the module's
# overhang onto the CLK-SEL jumper.
rotate_class("DIP-8_W7.62mm_LongPads", 0)

anchor("J1", edge="left", at=0.1)

block("osc", core="U9", axis="x", dress=[cap("C9", at="+5V")])
row("nodeb", parts=["R11", "C17", "Y1"], axis="x")
row("nodea", parts=["C16", "R10"], axis="x")

band("main", blocks=["osc"])
band("s1", blocks=["nodeb"])
band("s2", blocks=["nodea"])
