"""Where each project's files live.  One directory per .kicad_pro.

KiCad treats a DIRECTORY as a project's home: `fp-lib-table`, the `.kicad_prl`
session state and the project-local settings are all resolved from it, and
`${KIPRJMOD}` means it.  Five projects sharing one folder makes them fight
over that state, and makes it far too easy to open the one-page reference
sheet beside a board and wonder why cross-probing does nothing -- the boards
link to their OWN board-level sheets, whose symbols are different objects
with different UUIDs entirely.

`lib/`, `tools/` and `sim/` stay shared at the top.  Each project's
fp-lib-table reaches the shared footprints with ${KIPRJMOD}/../lib.
"""
import os

ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

DIRS = {
    "vinyl_adc": "reference",
    "vinyl_adc_power": "power",
    "vinyl_adc_channel_l": "channel_l",
    "vinyl_adc_channel_r": "channel_r",
    "vinyl_adc_digital": "digital",
}

# The three that actually become copper.  vinyl_adc is the one-page reference
# and has no board by design; vinyl_adc_channel_r is bookkeeping, so the split
# can be checked -- one channel artwork is milled twice.
BOARDS = ("vinyl_adc_power", "vinyl_adc_channel_l", "vinyl_adc_digital")

BUS_REF = {
    "vinyl_adc_power": "J3",
    "vinyl_adc_channel_l": "J7",
    "vinyl_adc_channel_r": "J7",
    "vinyl_adc_digital": "J4",
}


def home(name):
    if name not in DIRS:
        raise SystemExit(f"unknown project {name!r}")
    return os.path.join(ROOT, DIRS[name])


def path(name, ext):
    return os.path.join(home(name), f"{name}.{ext}")


def sch(name):
    return path(name, "kicad_sch")


def net(name):
    return path(name, "net")


def pcb(name):
    return path(name, "kicad_pcb")
