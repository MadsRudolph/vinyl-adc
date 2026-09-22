#!/usr/bin/env bash
# Schematic -> gate -> placed board -> routed board -> DRC -> production files.
#
#   PYTHONPATH=<pcbnew shim dir> tools/rev_c_pipeline.sh
#
# Routing is retried with different FreeRouting costs until DRC reports no
# unconnected items; the placed board is rebuilt before every attempt.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
K="$HERE/.."
SP="${REV_C_SCRATCH:-/tmp/rev_c_pipeline}"; mkdir -p "$SP"
SKILL="$HOME/.claude/skills/kicad-laser-pcb/scripts"
cd "$HERE" && python3 vinyl_adc_layout.py vinyl_adc_rev_c | tail -1
cd "$K"
kicad-cli sch export netlist --format kicadsexpr -o rev_c/vinyl_adc_rev_c.net rev_c/vinyl_adc_rev_c.kicad_sch >/dev/null 2>&1
python3 tools/check_rev_c.py | tail -1
python3 "$SKILL/pcb_netlist_json.py" rev_c/vinyl_adc_rev_c.net "$SP/rev_c.json" >/dev/null
ok=0
for costs in "1.9 25" "1.5 15" "2.5 40" "1.2 10" "3.0 60"; do
  set -- $costs
  python3 tools/rev_c_board.py "$SP/rev_c.json" rev_c/vinyl_adc_rev_c.kicad_pcb 2>&1 | grep -v 'm_choices' | tail -1
  if python3 tools/route_rev_c.py rev_c/vinyl_adc_rev_c.kicad_pcb --passes 40 --out "$SP" \
       --against-cost "$1" --via-cost "$2" 2>&1 | grep -v 'm_choices\|Debug:\|memory leak' | tee "$SP/route.log" \
     && grep -q 'DRC: 0 unconnected' "$SP/route.log"; then ok=1; break; fi
done
[ "$ok" = 1 ] || { echo "no clean route"; exit 1; }
"$HERE/export_rev_c.sh"
python3 tools/make_bom.py rev_c > "$K/../../docs/bom-rev-c.md"
echo "pipeline done"
