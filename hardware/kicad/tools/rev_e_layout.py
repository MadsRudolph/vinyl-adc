#!/usr/bin/env python3
"""REV E: rev D's circuit in surface-mount parts, on one 4-layer HAT.

    python3 tools/rev_e_layout.py   ->  rev_e/vinyl_adc_rev_e.kicad_sch

Rev D is the through-hole HAT built from the DTU shop's drawers.  Rev E is
the same circuit, drawn by the SAME block functions (rev_d_layout.py, which
calls vinyl_adc_layout.py), with every part that has a common SMD
equivalent swapped for it.  The netlist is therefore rev D's plus nothing,
and `check_rev_d.py vinyl_adc_rev_e` proves it with the same gate.

What changes is packages and three part numbers, never a value inside the
loop:

  * resistors and small capacitors in 0805 (hand-solder pads): 1 % thin
    film for every resistor, C0G for 27 p / 220 p / 1n5 (the integrator
    and filter caps, where X7R's voltage coefficient would be distortion),
    X7R for the 100 n decoupling;
  * every IC in SOIC (74HC244 in SOIC-20W), same pinout as the DIPs;
  * BC547/BC557 -> BC847/BC857 in SOT-23.  The TO-92 and SOT-23 pinouts
    differ, so the SYMBOL changes too (the pin names B/E/C do not, and the
    blocks connect by name);
  * 1N4148 -> 1N4148W (SOD-123), 1N5817 -> SS14 (SMA), 1N4003 -> S1M (SMA);
  * the four 10 u electrolytics -> 10 u X5R 25 V ceramic in 1206.  The
    flying cap gains from the lower ESR; the three timing caps lose ~40 %
    to DC bias, which moves the clip-stretch and clock-alive decay from
    ~1 s to ~0.6 s -- still long enough to see;
  * 220 u / 470 u -> SMD aluminium electrolytics, 220 u 16 V in 6.3 x 7.7
    and 470 u 10 V in 8 x 10 (both rails are 5 V; the stock sizes);
  * both 10 uH chokes -> Bourns SRR1260-100M (4.4 A, 27 mOhm), the island
    corner unchanged;
  * the crystal -> HC-49/SMD, 6x6 mm SMD tact switches, 0805 LEDs.

What stays through-hole, on purpose: the connectors (screw terminals, pin
headers, the Pi socket -- they take mechanical load) and C20/C60, the 2u2
input coupling capacitors.  2.2 uF does not exist in C0G, and an X7R in
series with the audio is the one place on this board a ceramic's voltage
coefficient would be audible; the MKT film part is the same as rev D's.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import vinyl_adc_layout as L                                  # noqa: E402
import rev_d_layout as D                                      # noqa: E402
from vinyl_adc_layout import emit_board, TITLE                # noqa: E402

NAME = "vinyl_adc_rev_e"

# SOT-23 transistors: different pin numbers from TO-92, same pin names
D.NPN, D.PNP = "Transistor_BJT:BC847", "Transistor_BJT:BC857"

HS = "_HandSolder"
R0805 = "Resistor_SMD:R_0805_2012Metric_Pad1.20x1.40mm" + HS
C0805 = "Capacitor_SMD:C_0805_2012Metric_Pad1.18x1.45mm" + HS
C1206 = "Capacitor_SMD:C_1206_3216Metric_Pad1.33x1.80mm" + HS
SO = "Package_SO:SOIC-{}_3.9x{}mm_P1.27mm"
SO8, SO14, SO16 = SO.format(8, 4.9), SO.format(14, 8.7), SO.format(16, 9.9)
SO20W = "Package_SO:SOIC-20W_7.5x12.8mm_P1.27mm"

# the value each part is ordered as, where the SMD part number differs
VALUES = {"BC547": "BC847", "BC557": "BC857", "1N4148": "1N4148W",
          "1N5817": "SS14", "1N4003": "S1M"}

# sheet notes that name a through-hole package or the shop's part
NOTES = (("24LC32 DIP-8, ORDER", "24LC32 SOIC-8"),
         ("the shop's 10u 3A part", "SRR1260 10 uH SMD"),
         ("(the shop's \"10u 3A\" choke, low DCR)", "(SRR1260-100M)"))


def footprints():
    D.footprints()                      # rev D's additions first, then SMD
    L.FOOTPRINTS.update({
        "Device:R": R0805,
        "Device:D_Schottky": "Diode_SMD:D_SMA",
        "Device:L": "Inductor_SMD:L_Bourns_SRR1260",
        "Device:LED": "LED_SMD:LED_0805_2012Metric_Pad1.15x1.40mm" + HS,
        "Device:Crystal": "Crystal:Crystal_SMD_HC49-SD_HandSoldering",
        D.NPN: "Package_TO_SOT_SMD:SOT-23",
        D.PNP: "Package_TO_SOT_SMD:SOT-23",
        D.SW: "Button_Switch_SMD:SW_SPST_PTS645Sx43SMTR92",
        "Memory_EEPROM:24LC32": SO8,
        "Comparator:LM339": SO14,
        "Comparator:LM311": SO8,
        "Amplifier_Operational:TL072": SO8,
        "Amplifier_Operational:LM358": SO8,
        "74xx:74HC04": SO14,
        "74xx:74HC74": SO14,
        "74xx:74LS132": SO14,
        "74xx:74LS157": SO16,
        "4xxx:4040": SO16,
        "4xxx:4049": SO16,
        "74xx:74HC244": SO20W,
    })
    # keyed by the ORDERED value: board_rev_e() renames before footprints
    # are assigned
    L.FOOTPRINTS_V.update({
        "1N4148W": "Diode_SMD:D_SOD-123",
        "S1M": "Diode_SMD:D_SMA",
    })
    L.FOOTPRINTS_C.clear()
    L.FOOTPRINTS_C.update({
        "2u2": "Capacitor_THT:C_Rect_L11.0mm_W6.3mm_P10.00mm_MKT",
        "470u": "Capacitor_SMD:CP_Elec_8x10",       # 470 u 10 V
        "220u": "Capacitor_SMD:CP_Elec_6.3x7.7",    # 220 u 16 V
        "10u": C1206,
    })
    L.FP_DISC = C0805              # footprint_for() reads it at call time


def board_rev_e(sh):
    links = D.board_rev_d(sh)
    for part in sh.parts:
        part.value = VALUES.get(part.value, part.value)
    texts = []
    for (t, x, y, size) in sh.texts:
        for old, new in NOTES:
            t = t.replace(old, new)
        texts.append((t, x, y, size))
    sh.texts[:] = texts
    return links


def main():
    footprints()
    return emit_board(NAME, board_rev_e, "A0",
                      TITLE + "  -  REV E, SMD RASPBERRY PI HAT, ONE 4-LAYER BOARD")


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
