#!/usr/bin/env bash
# A HAT board, end to end: schematic -> gate -> placed, routed, checked
# board -> production files -> BOM.
#
#   tools/hat_pipeline.sh rev_d      the through-hole HAT (DTU shop parts)
#   tools/hat_pipeline.sh rev_e      the same circuit in SMD parts
#
# (from hardware/kicad).  Routing is retried with different FreeRouting
# costs until DRC reports nothing unconnected and no errors (hat_route.py);
# the placed board is rebuilt before every attempt, and the placement is
# seeded, so it is the same each time.  pcbnew imports straight into the
# system python3 on this machine.
set -e
REV="${1:?usage: hat_pipeline.sh rev_d|rev_e}"
HERE="$(cd "$(dirname "$0")" && pwd)"
K="$HERE/.."
N="vinyl_adc_$REV"
SP="${HAT_SCRATCH:-/tmp/hat_pipeline_$REV}"; mkdir -p "$SP"
SKILL="$HOME/.claude/skills/kicad-laser-pcb/scripts"
cd "$HERE" && python3 "${REV}_layout.py" | tail -1
cd "$K"
kicad-cli sch export netlist --format kicadsexpr -o "$REV/$N.net" "$REV/$N.kicad_sch" >/dev/null 2>&1
python3 tools/check_rev_d.py "$N" | tail -1
python3 "$SKILL/pcb_netlist_json.py" "$REV/$N.net" "$SP/$REV.json" >/dev/null
python3 tools/hat_route.py "$REV" "$SP/$REV.json" --scratch "$SP/route"
"$HERE/export_rev_d.sh" "$REV"
if [ "$REV" = rev_e ]; then
  python3 tools/make_bom_smd.py > "$K/../../docs/bom-rev-e.md"
else
  python3 tools/make_bom.py rev_d > "$K/../../docs/bom-rev-d.md"
fi
echo "pipeline done: $REV"
