#!/usr/bin/env bash
# Production files for the rev C board -> production/vinyl_adc_rev_c/
# Gerbers in Protel naming without X2 attributes (what PCBWay's importer
# reads without complaint), silk clipped by the mask, drills split PTH/NPTH.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
PCB="$HERE/../rev_c/vinyl_adc_rev_c.kicad_pcb"
SCH="$HERE/../rev_c/vinyl_adc_rev_c.kicad_sch"
OUT="$HERE/../../../production/vinyl_adc_rev_c"
rm -rf "$OUT"; mkdir -p "$OUT/gerbers"
kicad-cli pcb export gerbers -o "$OUT/gerbers/" \
  -l F.Cu,In1.Cu,In2.Cu,B.Cu,F.Mask,B.Mask,F.SilkS,B.SilkS,Edge.Cuts \
  --no-x2 --no-netlist --subtract-soldermask --check-zones "$PCB" >/dev/null
kicad-cli pcb export drill -o "$OUT/gerbers/" --format excellon \
  --excellon-separate-th --generate-map --map-format pdf "$PCB" >/dev/null
kicad-cli pcb export pdf -o "$OUT/vinyl_adc_rev_c-layers.pdf" \
  -l F.Cu,In1.Cu,In2.Cu,B.Cu,F.SilkS,B.SilkS,Edge.Cuts --mode-separate "$PCB" >/dev/null
kicad-cli sch export pdf -o "$OUT/vinyl_adc_rev_c-schematic.pdf" "$SCH" >/dev/null
kicad-cli pcb render --side top -w 1600 -h 1130 -o "$OUT/vinyl_adc_rev_c-top.png" "$PCB" >/dev/null
kicad-cli pcb render --side bottom -w 1600 -h 1130 -o "$OUT/vinyl_adc_rev_c-bottom.png" "$PCB" >/dev/null
(cd "$OUT/gerbers" && zip -q ../vinyl_adc_rev_c-gerbers.zip ./*)
echo "exported to $OUT"
