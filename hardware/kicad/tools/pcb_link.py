#!/usr/bin/env python
r"""Link each footprint back to the schematic symbol it came from.

    & "C:\Program Files\KiCad\10.0\bin\python.exe" tools\pcb_link.py

KiCad cross-probes between Eeschema and pcbnew through the footprint's PATH
-- the schematic symbol's UUID, stamped on the footprint as `/<uuid>`.  Click
a part on the board and KiCad looks that path up to find the symbol.

`pcb_build.py` builds the board from a netlist JSON and never writes it, so a
scripted board arrives with no paths at all: selecting a component highlights
nothing in the schematic, the cross-probe buttons do nothing, and "Update PCB
from Schematic" treats every footprint as new because it cannot match them.
Nothing warns about it -- the board is otherwise completely valid, DRC is
clean, the netlist is right.  Only the link is missing.

The UUIDs are in the netlist already, as `(tstamps ...)` on each component,
so this reads them straight back out and stamps them on.

RUN IT AFTER EVERY `vinyl_adc_layout.py`, not just after `pcb_build.py`.  The
generator re-rolls every symbol UUID each time it draws a sheet, so any
regeneration silently orphans every path on the board.  Re-export the
netlists first, then run this.

It verifies its own work, because every way this fails is quiet: it re-reads
what it wrote and checks each footprint resolves to the symbol with the same
reference.  Reporting "linked 18" while writing garbage is exactly the bug
this script has already had twice.
"""
import io
import os
import re
import sys
import paths

import pcbnew

BOARDS = ("vinyl_adc_power", "vinyl_adc_channel_l", "vinyl_adc_digital")


def uuids(net_path):
    """ref -> symbol UUID, read out of the netlist's components block.

    Two traps in here, both of which fail silently rather than loudly.

    Only the COMPONENTS block: `(ref "C1")` also appears on every node of the
    nets block, where it means something else entirely.

    And each `(comp ...)` carries TWO `(tstamps ...)` -- the sheetpath's,
    which is just "/", and the symbol's own UUID.  Taking the first one after
    the ref picks the sheetpath, so every footprint gets a path of "/", which
    pcbnew accepts, stores, and then serialises as nothing at all.  The board
    saves clean, the script reports every footprint linked, and not one of
    them is.  So match on the UUID's own shape.
    """
    s = io.open(net_path, encoding="utf-8").read()
    a = s.find("(components")
    if a < 0:
        raise SystemExit(f"no components block in {net_path}")
    b = s.find("(nets", a)
    block = s[a:b if b > 0 else len(s)]

    uuid = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    out = {}
    for chunk in block.split("(comp")[1:]:
        m = re.search(r'\(ref "([^"]+)"\)', chunk)
        # No closing paren in the pattern: a MULTI-UNIT symbol writes
        # `(tstamps "uuid-a" "uuid-b" ...)`, one per unit, so requiring `")`
        # right after silently skips every TL072, 74HC74 and 74HC04 on the
        # board.  The first unit's UUID is the one to cross-probe to.
        t = re.search(r'\(tstamps "(' + uuid + r')"', chunk)
        if m and t:
            out[m.group(1)] = t.group(1)
    return out


def link(board_path, net_path):
    want = uuids(net_path)
    b = pcbnew.LoadBoard(board_path)
    done, missing = 0, []
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        # The M3 holes are board features, not schematic symbols -- they have
        # no path to stamp and are not a fault.
        if ref.startswith("H") and ref[1:].isdigit():
            continue
        u = want.get(ref)
        if not u:
            missing.append(ref)
            continue
        fp.SetPath(pcbnew.KIID_PATH("/" + u))
        done += 1
    # pcbnew.SaveBoard, NOT board.Save: the latter returns cleanly and
    # writes a file with no paths in it at all.
    pcbnew.SaveBoard(board_path, b)
    return done, missing


def verify(board_path, sch_path):
    """Re-read what we wrote: does each footprint resolve to its own symbol?"""
    pcb = io.open(board_path, encoding="utf-8").read()
    sch = io.open(sch_path, encoding="utf-8").read()
    tab, nl = chr(9), chr(10)
    sym = {}
    # Instance blocks are `(symbol` at ONE tab followed by end-of-line; the
    # `(symbol "Device:C"` forms two tabs in are library definitions.
    for chunk in sch.split(nl + tab + "(symbol" + nl)[1:]:
        u = re.search(r'\(uuid "([0-9a-f-]{36})"\)', chunk)
        r = re.search(r'\(property "Reference" "([^"]+)"', chunk)
        if u and r:
            sym[u.group(1)] = r.group(1)
    wrong = []
    for chunk in pcb.split(nl + tab + "(footprint ")[1:]:
        fr = re.search(r'\(property "Reference" "([^"]+)"', chunk)
        fp = re.search(r'\(path "/([0-9a-f-]{36})"', chunk)
        if not fr:
            continue
        ref = fr.group(1)
        if ref.startswith("H") and ref[1:].isdigit():
            continue
        if not fp or sym.get(fp.group(1)) != ref:
            wrong.append(ref)
    return wrong


if __name__ == "__main__":
    bad = 0
    for name in (sys.argv[1:] or paths.BOARDS):
        pcb, net = paths.pcb(name), paths.net(name)
        if not (os.path.exists(pcb) and os.path.exists(net)):
            print(f"{name}: no board or no netlist, skipped")
            continue
        done, missing = link(pcb, net)
        wrong = verify(pcb, paths.sch(name))
        print(f"{name}: linked {done} footprint(s), verified "
              f"{done - len(wrong)} resolve to the right symbol"
              + (f", {len(missing)} WITHOUT a symbol: {missing}" if missing
                 else "")
              + (f", {len(wrong)} MISLINKED: {wrong[:6]}" if wrong else ""))
        bad += len(missing) + len(wrong)
    sys.exit(1 if bad else 0)
