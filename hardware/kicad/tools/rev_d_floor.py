"""Floorplan of the rev D (through-hole) HAT, for hat_board.py.

    140 x 136 mm, origin top-left, parts on top, the Pi 4 underneath.

      x 0..84                                x 84..140  (over the Pi)
      y   0..46  CHANNEL L  J20 RV20 -> U20 U22 U21     DIGITAL  Y1 U9 / U8 U4 /
                            U24 U23  J22                          U6 U3, J1
      y  46..58  J3 + lift network | U12 clip | J5      PUMP     C1 L1 U1 U10 (to y 88)
      y  58..104 CHANNEL R  (channel L, moved 58 down)  ISLAND   L2 C18 U2 ref U11
      y 104..136 LED drivers, then the front row: 8 LEDs ........ SW1 SW2

The second layout of rev D.  The first (176 x 146) put every passive in a
row of its own kind, first-fit, inside a band -- tidy from a distance and
the reason its traces ran diagonally across the board: a resistor sat
wherever its row had room, not next to the pin it serves.  This one is
placed by hat_place.py from the netlist, the same way as rev E: anchors on
the edges, ICs in schematic order, every passive pulled to its pins and
every decoupling cap to its supply pin, channel R a rigid copy of channel
L.  Same geography as rev E, scaled for DIPs and axial leads; 30 % less
board than the first layout.

The In2 split follows the right-hand column: +5V over the digital and pump
blocks (x >= 84, y < 88), +5VA everywhere else; L2 stands across y = 88
with a pad in each plane.
"""
import re

import pcbnew

W, H = 140.0, 136.0
PI_HDR = (W - 52.5, 32.5)
BOARD_HOLES = [(3.5, 3.5), (3.5, H - 3.5), (W - 3.5, H - 3.5)]
SPLIT_X, SPLIT_Y = 84.0, 88.0

# rev D's own rules: twice PCBWay's 4-layer minimums, every lead hand-soldered
RULES = dict(track=0.25, clearance=0.2, via=0.8, via_drill=0.4,
             supply_track=0.4, clock_track=0.3, edge=0.3)
GAP, MARGIN, SNAP = 0.4, 0.6, 0.25
REF_SIZE = 1.0
ITERS = 250000
WEIGHTS = {"-5V": 0.3, "+3V3": 0.4, "VREF_P": 0.6, "VREF_N": 0.6,
           "CHASSIS": 0.5,
           # the charge pump's 192 kHz loop: drivers -> flying cap ->
           # rectifier -> reservoir, kept small
           "Net-(U1-1Y0)": 2.0, "Net-(D1-A)": 3.0, "Net-(D2-A)": 3.0}

DY = 58.0                              # channel R = channel L moved down
CH_L = (0.6, 0.6, 83.6, 46.0)
CLIP = (0.6, 46.2, 83.6, 58.4)
STRIP = (0.6, 104.4, W - 0.6, H - 0.6)
DIG = (84.2, 0.6, W - 0.6, 57.0)
PUMP = (84.2, 57.0, W - 0.6, SPLIT_Y - 0.3)
ISLAND = (84.2, SPLIT_Y + 0.3, W - 0.6, 120.0)   # down to the buttons

# the front row, left to right, each LED nearest the block that drives it
LED_Y = H - 6.0
LEDS = [("D6", "CLIP L"), ("D7", "CLIP R"), ("D3", "+5VA"), ("D4", "-5V"),
        ("D5", "CLK"), ("D8", "REC"), ("D9", "BUSY"), ("D10", "READY")]
LED_X0, LED_PITCH = 11.0, 9.5          # pad 1; the body centre is +1.27
BUTTONS = [("SW1", "SHUTDOWN", 104.0), ("SW2", "USER", 118.0)]   # pad 1
SW_Y = H - 9.5
TP_L = (78.5, 22.0)                   # J22 pad 1; J62 is DY below
TP_D = (78.5, 47.5)                   # J5 pad 1: between J22 and J62

KEEPOUTS = [(6.0, H - 2.4, 84.0, H - 0.6)]                    # LED names
KEEPOUTS += [(x - 1.6, SW_Y - 3.3, x + 8.1, SW_Y - 1.65) for _r, _c, x in BUTTONS]


def _tp_keepouts(x, y):
    """Pin names left of the ground column, a caption above the header."""
    return [(x - 5.4, y - 1.3, x - 1.95, y + 11.5),
            (x - 5.4, y - 3.6, x + 4.3, y - 1.95)]


for _dy in (0.0, DY):
    KEEPOUTS += _tp_keepouts(TP_L[0], TP_L[1] + _dy)
# all three probe headers in one column beside the socket: the channels'
# two and, between them, the digital one (MCLK and both references run
# past here into the channels anyway)
KEEPOUTS += _tp_keepouts(*TP_D)


def chan(n):
    r = [f"R{n + k}" for k in range(18)]
    c = [f"C{n + k}" for k in range(12)]
    return r + c + [f"U{n + k}" for k in range(5)] + [f"J{n}", f"RV{n}",
                                                        f"J{n + 2}"]


DIPS = (90, 270)                      # DIPs lie along the signal flow


def configure(P):
    P.dec_w = 8.0                     # a decoupling cap is worth 8 mm of wire
    for i, (ref, _cap) in enumerate(LEDS):
        P.fix(ref, LED_X0 + i * LED_PITCH, LED_Y, 0)
    for ref, _cap, x in BUTTONS:
        P.fix(ref, x, SW_Y, 0)
    for n, dy in ((20, 0.0), (60, DY)):
        P.fix(f"J{n}", 4.7, 10.0 + dy, 270)       # wire entry on the left edge
        P.fix(f"RV{n}", 11.2, 26.0 + dy, 180)     # trim header, pins to the edge
        P.fix(f"J{n + 2}", TP_L[0], TP_L[1] + dy, 0)
    P.fix("J3", 4.7, 48.5, 270)                   # tonearm ground, between
    P.fix("J5", *TP_D, 0)
    p = P.parts["L2"]                             # across the In2 split
    rot = next(r for r in (90, 270) if
               dict((net, dy) for _n, _dx, dy, net in p.geo[r][1])["+5V"] <
               dict((net, dy) for _n, _dx, dy, net in p.geo[r][1])["+5VA"])
    d = abs(p.geo[rot][1][1][2] - p.geo[rot][1][0][2]) / 2
    top = min(dy for _n, _dx, dy, _net in p.geo[rot][1])
    P.fix("L2", W - 3.7, SPLIT_Y - d - top, rot)   # right edge, below the hole

    refs_l = chan(20)
    for ref in refs_l:
        if not P.parts[ref].fixed:
            P.twin(ref, re.sub(r"\d+", lambda m: str(int(m.group()) + 40), ref),
                   0.0, DY)
    P.region([r for r in refs_l if not P.parts[r].fixed], CH_L)
    P.hint("U20", 28.0, 12.0, 90, rots=DIPS)     # TL072 integrators 1, 2
    P.hint("U22", 46.0, 12.0, 90, rots=DIPS)     # TL072 integrator 3, inverter
    P.hint("U21", 64.0, 12.0, 90, rots=DIPS)     # LM311 quantiser
    P.hint("U24", 40.0, 35.0, 90, rots=DIPS)     # 74HC04 DAC gates
    P.hint("U23", 62.0, 35.0, 90, rots=DIPS)     # 74HC74 retime
    P.hint("C20", 24.0, 34.0, 0)

    P.region(["U12", "C44", "C50", "R44", "R45", "R46", "R47"], CLIP)
    # the tonearm lift network round J3, on the left edge between the inputs
    P.region(["J4", "R17", "C48", "D15", "D16"], (0.6, 36.0, 36.0, 68.0))
    P.hint("U12", 44.0, 52.3, 90, rots=DIPS)

    P.region(["R48", "D13", "C42", "R49", "R50", "Q2", "R52",
              "R53", "D14", "C43", "R59", "R51", "Q3", "R16",
              "C40", "D11", "D12", "C41", "R43", "Q1", "R42",
              "R40", "R41", "R54", "R55", "R56",
              "R57", "R58", "C46", "C47"], STRIP)

    P.region(["Y1", "U9", "J1", "R10", "R11", "C16", "C17", "C9",
              "U3", "U4", "U6", "U8", "C10", "C11", "C13", "C15",
              "R12", "R13", "R14"], DIG)
    # the HAT EEPROM is read once, at boot, at 100 kHz: it gives its place
    # by the header to the clock chain and lives below the reference
    P.region(["U11", "C45", "R15", "J6"], ISLAND)
    P.hint("U11", 124.0, 112.0, 90, rots=DIPS)
    # three rows of two under J5: level shift and mux by the socket's I2S
    # pins, the clock chain (Pierce, divider, Schmitt) on the outside
    # three rows of two, a row of passives between each: level shift and
    # mux by the socket's I2S pins, the clock chain on the outside
    P.hint("Y1", 103.0, 9.0, 0)
    P.hint("U9", 127.0, 9.0, 90, rots=DIPS)
    P.hint("U8", 102.0, 27.0, 90, rots=DIPS)
    P.hint("U4", 127.0, 27.0, 90, rots=DIPS)
    P.hint("U6", 102.0, 45.0, 90, rots=DIPS)
    P.hint("U3", 127.0, 45.0, 90, rots=DIPS)

    P.region(["L1", "C1", "C2", "U1", "U10", "C3", "C49"], PUMP)
    # the flying cap, rectifier and -5V filter touch neither plane: they sit
    # just under the split, straight below the drivers, loop small
    P.region(["C4", "D1", "D2", "C5", "R1"],
             (PUMP[0], PUMP[1], W - 0.6, ISLAND[3]))
    P.hint("C4", 110.0, 88.5, 0)
    P.hint("D1", 122.0, 88.0, 0)
    P.hint("D2", 122.0, 92.0, 0)
    P.hint("C5", 110.0, 95.0, 0)
    # inlet choke upright under the socket's 5 V pins, the reservoir beside
    # it, then the pump pair standing side by side, L2 at the edge
    P.hint("C1", 96.8, 62.8, 0)
    P.hint("L1", 93.8, 78.4, 90)
    P.hint("U1", 112.3, 72.5, 0, rots=(0, 180))
    P.hint("U10", 125.8, 72.5, 0, rots=(0, 180))
    P.region(["C18", "C19", "U2", "C7", "C8", "R2", "R3", "R4", "R5", "C6"],
             ISLAND)
    P.hint("C18", 98.0, 104.0, 0)
    P.hint("U2", 116.0, 104.0, 90, rots=DIPS)

    # routing channels: every DIP keeps 0.5 mm more round it, and the pump
    # pair 1.0 mm -- their sixteen outputs and eight inputs are two 17-pad
    # nets that must escape between the packages
    P.halo([r for r in P.parts if r.startswith("U")], 0.5)
    P.halo(["U1", "U10"], 1.0)

    for cap, host in (("C3", "U1"), ("C49", "U10"), ("C7", "U2"),
                      ("C8", "U2"), ("C45", "U11"), ("C44", "U12"),
                      ("C50", "U12"), ("C25", "U20"), ("C26", "U20"),
                      ("C28", "U22"), ("C29", "U22"), ("C27", "U21"),
                      ("C30", "U23"), ("C31", "U24"), ("C9", "U9"),
                      ("C10", "U3"), ("C11", "U4"), ("C13", "U6"),
                      ("C15", "U8"), ("C2", "C1"), ("C19", "C18")):
        P.decouple(cap, host)


def plane_at(x, y):
    return "+5V" if (x >= SPLIT_X and y < SPLIT_Y) else "+5VA"


def zones(W, H):
    e = 0.5
    return [
        ("GND", pcbnew.In1_Cu, [(e, e), (W - e, e), (W - e, H - e), (e, H - e)]),
        ("+5V", pcbnew.In2_Cu, [(SPLIT_X + 0.3, e), (W - e, e),
                                (W - e, SPLIT_Y - 0.3),
                                (SPLIT_X + 0.3, SPLIT_Y - 0.3)]),
        ("+5VA", pcbnew.In2_Cu, [(e, e), (SPLIT_X - 0.3, e),
                                 (SPLIT_X - 0.3, SPLIT_Y + 0.3),
                                 (W - e, SPLIT_Y + 0.3), (W - e, H - e),
                                 (e, H - e)]),
    ]


def silkscreen(board, fps):
    from hat_board import add_board_text as T
    from hat_board import pad_mm
    for ref, cap in LEDS:
        x = pcbnew.ToMM(fps[ref].GetPosition().x) + 1.27
        T(board, cap, x, H - 1.5, size=0.9)
    for ref, cap, x in BUTTONS:
        T(board, cap, x + 3.25, SW_Y - 2.5, size=0.9)
    tps = (("J22", "TP L  odd = GND", ("INT1", "INT2", "INT3", "CMP", "DACP")),
           ("J62", "TP R  odd = GND", ("INT1", "INT2", "INT3", "CMP", "DACP")),
           ("J5", "TP DIG odd = GND", ("MCLK", "LRCK", "DIN", "VR+", "VR-")))
    for ref, cap, names in tps:
        for i, nm in enumerate(names):
            px, py = pad_mm(fps[ref], str(2 * i + 1))
            T(board, nm, px - 3.6, py, size=0.9)
        px, py = pad_mm(fps[ref], "1")
        T(board, cap, px + 0.2, py - 2.8, size=0.9)
    # on the copper side, where the Pi sits: the first pad-free spot
    from hat_board import text_block
    text_block(board, fps, ("VINYL ADC  rev D", "through-hole Raspberry Pi HAT, 4 layers",
                            "Pi 4 plugs in on this side",
                            "USB / Ethernet over the top edge"),
               (1.4, 1.0, 1.0, 1.0), pcbnew.B_SilkS, (2.0, 2.0, W - 2.0, H - 2.0), mirror=True)
