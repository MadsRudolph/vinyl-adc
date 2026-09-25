#!/usr/bin/env bash
# Production files for a HAT board -> production/vinyl_adc_<rev>/
#
#   tools/export_rev_d.sh            rev D, the through-hole HAT
#   tools/export_rev_d.sh rev_e      rev E, the SMD HAT (adds the pick-and-
#                                    place file PCBWay's assembly wants)
#
# Gerbers in Protel naming without X2 attributes (what PCBWay's importer
# reads without complaint), silk clipped by the mask, drills split PTH/NPTH,
# plus the layer PDF, the schematic PDF, both 3D renders and an IPC-D-356
# netlist for the fab's electrical test.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
REV="${1:-rev_d}"
N="vinyl_adc_$REV"
PCB="$HERE/../$REV/$N.kicad_pcb"
SCH="$HERE/../$REV/$N.kicad_sch"
OUT="$HERE/../../../production/$N"
# regenerate everything but keep the hand-written README beside it
mkdir -p "$OUT"; find "$OUT" -mindepth 1 ! -name README.md -delete; mkdir -p "$OUT/gerbers"
kicad-cli pcb export gerbers -o "$OUT/gerbers/" \
  -l F.Cu,In1.Cu,In2.Cu,B.Cu,F.Mask,B.Mask,F.SilkS,B.SilkS,Edge.Cuts \
  --no-x2 --no-netlist --subtract-soldermask --check-zones "$PCB" >/dev/null
kicad-cli pcb export drill -o "$OUT/gerbers/" --format excellon \
  --excellon-separate-th --generate-map --map-format pdf "$PCB" >/dev/null
kicad-cli pcb export ipcd356 -o "$OUT/$N.d356" "$PCB" >/dev/null
kicad-cli pcb export pdf -o "$OUT/$N-layers.pdf" \
  -l F.Cu,In1.Cu,In2.Cu,B.Cu,F.SilkS,B.SilkS,Edge.Cuts --mode-separate "$PCB" >/dev/null
kicad-cli sch export pdf -o "$OUT/$N-schematic.pdf" "$SCH" >/dev/null
kicad-cli pcb render --side top -w 1800 -h 1400 -o "$OUT/$N-top.png" "$PCB" >/dev/null
kicad-cli pcb render --side bottom -w 1800 -h 1400 -o "$OUT/$N-bottom.png" "$PCB" >/dev/null
kicad-cli pcb export step -o "$OUT/$N.step" --subst-models "$PCB" >/dev/null 2>&1 || true
if [ "$REV" = rev_e ]; then
  kicad-cli pcb export pos -o "$OUT/$N-pos.csv" --format csv --units mm \
    --side front --exclude-dnp "$PCB" >/dev/null
fi
(cd "$OUT/gerbers" && rm -f ../$N-gerbers.zip && zip -q ../$N-gerbers.zip ./*)
echo "exported to $OUT"
