"""Floorplan of the rev E (SMD) HAT, for hat_board.py.

    118 x 88 mm, origin top-left, parts on top, the Pi 4 underneath.

      x 0..62                               x 62..118  (over the Pi)
      y  0..33   CHANNEL L  J20 RV20 -> U20 U22 U21     DIGITAL  Y1 U9 U3 U4
                            U24 U23  J22                          U6 U8 J1 J5 U11
      y 33..42   J3 + lift network | U12 clip windows  PUMP     L1 C1 U1 U10 ...
      y 42..75   CHANNEL R  (channel L, moved 42 down)  ISLAND   L2 C18 U2 ref
      y 75..88   LED drivers, then the front row: 8 LEDs ........ SW1 SW2

Same geography as the first rev D placement (inputs on the left edge, the
digital column over the Pi's header, power at the far end from the inputs)
but a quarter of the area, every passive next to the pin it serves, and
channel R a rigid copy of channel L.  The In2 split follows the right-hand
column: +5V over the digital and pump blocks (x >= 62, y < 60), +5VA
everywhere else; L2 stands across y = 60 with a pad in each plane.
"""
import re

import pcbnew

W, H = 118.0, 88.0
PI_HDR = (W - 52.5, 32.5)
BOARD_HOLES = [(3.5, 3.5), (3.5, H - 3.5), (W - 3.5, H - 3.5)]
SPLIT_X, SPLIT_Y = 62.0, 60.0

RULES = dict(track=0.25, clearance=0.2, via=0.6, via_drill=0.3,
             supply_track=0.4, clock_track=0.3, edge=0.3)
GAP, MARGIN, SNAP = 0.35, 0.6, 0.25
REF_SIZE = 0.8
ITERS = 250000
WEIGHTS = {"-5V": 0.3, "+3V3": 0.4, "VREF_P": 0.6, "VREF_N": 0.6,
           "CHASSIS": 0.5,
           # the charge pump's 192 kHz loop: drivers -> flying cap ->
           # rectifier -> reservoir, kept small
           "Net-(U1-1Y0)": 2.0, "Net-(D1-A)": 3.0, "Net-(D2-A)": 3.0}

DY = 42.0                              # channel R = channel L moved down
CH_L = (0.6, 0.6, 61.6, 33.0)
CLIP = (0.6, 33.2, 61.6, 41.8)
STRIP = (0.6, 75.4, W - 0.6, H - 0.6)
DIG = (62.3, 0.6, W - 0.6, 30.5)
PUMP = (62.3, 30.5, W - 0.6, SPLIT_Y - 0.3)
ISLAND = (62.3, SPLIT_Y + 0.3, W - 0.6, 75.2)

# the front row, left to right; each LED sits nearest the block that drives
# it: the clip pair under the clip detector, the rails, then the clock and
# the Pi's three towards the digital column
LED_Y = H - 4.2
LEDS = [("D6", "CLIP L"), ("D7", "CLIP R"), ("D3", "+5VA"), ("D4", "-5V"),
        ("D5", "CLK"), ("D8", "REC"), ("D9", "BUSY"), ("D10", "READY")]
LED_X0, LED_PITCH = 10.0, 7.5
BUTTONS = [("SW1", "SHUTDOWN", 86.0), ("SW2", "USER", 99.0)]
SW_Y = H - 4.4
TP_L = (57.4, 19.0)                   # J22 pad 1; J62 is DY below
TP_D = (W - 7.2, 22.0)                # J5 pad 1

# legends drawn after placement: nothing may be placed under them
KEEPOUTS = [(5.0, H - 3.0, 67.0, H - 0.6)]                    # LED names
KEEPOUTS += [(x - 5.1, SW_Y - 4.7, x + 5.1, SW_Y - 3.6) for _r, _c, x in BUTTONS]


def _tp_keepouts(x, y):
    """Pin names left of the ground column, a caption above the header."""
    return [(x - 5.0, y - 1.3, x - 1.95, y + 11.5),
            (x - 5.0, y - 3.4, x + 4.3, y - 1.95)]


for _dy in (0.0, DY):
    KEEPOUTS += _tp_keepouts(TP_L[0], TP_L[1] + _dy)
KEEPOUTS += _tp_keepouts(*TP_D)


def chan(n):
    r = [f"R{n + k}" for k in range(18)]
    c = [f"C{n + k}" for k in range(12)]
    return r + c + [f"U{n + k}" for k in range(5)] + [f"J{n}", f"RV{n}",
                                                        f"J{n + 2}"]


def configure(P):
    P.dec_w = 8.0                     # a decoupling cap is worth 8 mm of wire
    # -- fixed: connectors on the edges, the front row ------------------------
    for i, (ref, _cap) in enumerate(LEDS):
        P.fix(ref, LED_X0 + i * LED_PITCH, LED_Y, 0)
    for ref, _cap, x in BUTTONS:
        P.fix(ref, x, SW_Y, 0)
    for n, dy in ((20, 0.0), (60, DY)):
        P.fix(f"J{n}", 4.7, 10.0 + dy, 270)       # wire entry on the left edge
        P.fix(f"RV{n}", 11.2, 26.0 + dy, 180)     # trim header, pins to the edge
        P.fix(f"J{n + 2}", TP_L[0], TP_L[1] + dy, 0)   # TPs, by the Pi header
    P.fix("J3", 4.7, 31.0, 270)                   # tonearm ground, between
    P.fix("J5", *TP_D, 0)                         # digital TPs, right edge
    # L2 across the In2 split, +5V pad up in the +5V plane
    p = P.parts["L2"]
    rot = next(r for r in (90, 270) if
               dict((net, dy) for _n, _dx, dy, net in p.geo[r][1])["+5V"] < 0)
    P.fix("L2", 76.0, SPLIT_Y, rot)

    # -- channel L; channel R follows as a rigid copy ---------------------------
    refs_l = chan(20)
    for ref in refs_l:
        if not P.parts[ref].fixed:
            P.twin(ref, re.sub(r"\d+", lambda m: str(int(m.group()) + 40), ref),
                   0.0, DY)
    P.region([r for r in refs_l if not P.parts[r].fixed], CH_L)
    P.hint("U20", 20.0, 9.0, 0)          # TL072 integrators 1, 2
    P.hint("U22", 33.0, 9.0, 0)          # TL072 integrator 3, inverter
    P.hint("U21", 46.0, 9.0, 0)          # LM311 quantiser
    P.hint("U24", 28.0, 24.0, 0)         # 74HC04 DAC gates
    P.hint("U23", 42.0, 24.0, 0)         # 74HC74 retime
    P.hint("C20", 16.0, 26.0, 0)         # film coupling cap, by the input

    # -- between the channels: tonearm lift network, clip windows -------------
    P.region(["U12", "C44", "C50", "R44", "R45", "R46", "R47",
              "J4", "R17", "C48", "D15", "D16"], CLIP)
    P.hint("U12", 36.0, 37.5, 90)

    # -- front strip: LED drivers ------------------------------------------------
    P.region(["R48", "D13", "C42", "R49", "R50", "Q2", "R52",
              "R53", "D14", "C43", "R59", "R51", "Q3", "R16",
              "C40", "D11", "D12", "C41", "R43", "Q1", "R42",
              "R40", "R41", "R54", "R55", "R56",
              "R57", "R58", "C46", "C47"], STRIP)

    # -- digital, over the Pi -----------------------------------------------------
    P.region(["Y1", "U9", "J1", "R10", "R11", "C16", "C17", "C9",
              "U3", "U4", "U6", "U8", "C10", "C11", "C13", "C15",
              "R12", "R13", "R14", "U11", "C45", "R15", "J6"], DIG)
    P.hint("U8", 73.0, 11.0, 0)          # level shift, by the I2S pins
    P.hint("U6", 76.0, 26.0, 0)          # interleave mux
    P.hint("U4", 88.0, 20.0, 0)          # divider
    P.hint("U3", 100.0, 20.0, 0)         # oscillator buffer, Schmitt
    P.hint("U9", 108.0, 10.0, 0)         # Pierce inverter
    P.hint("Y1", 92.0, 6.0, 0)
    P.hint("U11", 75.0, 27.0, 0)         # HAT EEPROM, by ID_SD / ID_SC

    # -- power: pump on +5V, island and reference on +5VA ----------------------
    P.region(["L1", "C1", "C2", "U1", "U10", "C3", "C49", "C4", "D1",
              "D2", "C5", "R1"], PUMP)
    P.hint("L1", 76.0, 44.0, 0)
    P.hint("C1", 90.0, 50.0, 0)
    P.hint("U1", 100.0, 40.0, 0)
    P.hint("U10", 111.0, 40.0, 0)
    # C6, the -5V reservoir, sits with the reference that draws on it
    P.region(["C18", "C19", "U2", "C7", "C8", "R2", "R3", "R4", "R5", "C6"],
             ISLAND)
    P.hint("C18", 84.0, 67.0, 0)
    P.hint("U2", 102.0, 67.0, 0)

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
        x = pcbnew.ToMM(fps[ref].GetPosition().x)
        T(board, cap, x, H - 1.9, size=0.8)
    for ref, cap, x in BUTTONS:
        T(board, cap, x, SW_Y - 4.0, size=0.8)
    tps = (("J22", "TP L  odd = GND", ("INT1", "INT2", "INT3", "CMP", "DACP")),
           ("J62", "TP R  odd = GND", ("INT1", "INT2", "INT3", "CMP", "DACP")),
           ("J5", "TP DIG", ("MCLK", "LRCK", "DIN", "VR+", "VR-")))
    for ref, cap, names in tps:
        for i, nm in enumerate(names):
            px, py = pad_mm(fps[ref], str(2 * i + 1))
            T(board, nm, px - 3.4, py, size=0.8)
        px, py = pad_mm(fps[ref], "1")
        T(board, cap, px + 0.2, py - 2.6, size=0.8)
    # on the copper side, where the Pi sits: the first pad-free spot
    from hat_board import text_block
    text_block(board, fps, ("VINYL ADC  rev E", "SMD Raspberry Pi HAT, 4 layers",
                            "Pi 4 plugs in on this side",
                            "USB / Ethernet over the top edge"),
               (1.4, 1.0, 1.0, 1.0), pcbnew.B_SilkS, (2.0, 2.0, W - 2.0, H - 2.0), mirror=True)
