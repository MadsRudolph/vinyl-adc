#!/usr/bin/env bash
# Export the rev D board (and a Raspberry Pi 4) to GLB for render_rev_d.py.
#
#   hardware/kicad/rev_d/render/export_model.sh
#
# Writes build/board.glb and build/pi4.glb next to this script. The board is
# exported from a scratch copy of the .kicad_pcb in which the one 3D model path
# that does not resolve under KiCad 10 (the vendored bornier-2 terminal block,
# whose STEP KiCad 10 dropped) points at the stock Phoenix MKDS 1,5/2-5.08
# model of the same pitch. The design file itself is not touched.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
build="$here/build"
pcb="$here/../vinyl_adc_rev_d.kicad_pcb"
mkdir -p "$build"

sed 's#${KICAD9_3DMODEL_DIR}/TerminalBlock.3dshapes/TerminalBlock_bornier-2_P5.08mm.step#${KICAD10_3DMODEL_DIR}/TerminalBlock_Phoenix.3dshapes/TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal.step#' \
    "$pcb" > "$build/board.kicad_pcb"
cp "$here/../vinyl_adc_rev_d.kicad_pro" "$build/board.kicad_pro"
kicad-cli pcb export glb -f -o "$build/board.glb" --subst-models \
    --include-tracks --include-pads --include-zones \
    --include-silkscreen --include-soldermask "$build/board.kicad_pcb" 2>&1 | grep -v 'image handler' || true

# Raspberry Pi 4B model from the FreeCAD parts library (CC BY 3.0).
pi_url='https://raw.githubusercontent.com/FreeCAD/FreeCAD-library/master/Computing/SingleBoardComputers/Raspberry/Raspberry%20Pi%204B/Raspberry%20Pi%204B.step'
pi_sha='82c055acbed781e623d8c32acfdec2254400104f2cfa21ddbc2ba0e8b80797da'
mkdir -p "$build/pi4"
if [ ! -f "$build/pi4/pi4b.step" ]; then
    curl -fL -o "$build/pi4/pi4b.step" "$pi_url"
fi
echo "$pi_sha  $build/pi4/pi4b.step" | sha256sum -c -
# KiCad does the STEP -> GLB tessellation: a one-footprint board carrying it.
cat > "$build/pi4/pi4.kicad_pcb" <<PCB
(kicad_pcb (version 20240108) (generator "pcbnew")
  (general (thickness 1.6))
  (paper "A4")
  (layers (0 "F.Cu" signal) (31 "B.Cu" signal) (44 "Edge.Cuts" user))
  (footprint "PI4" (layer "F.Cu") (at 0 0)
    (property "Reference" "PI4" (at 0 0) (layer "F.Fab"))
    (attr through_hole)
    (model "$build/pi4/pi4b.step" (offset (xyz 0 0 0)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0)))
  )
)
PCB
kicad-cli pcb export glb -f -o "$build/pi4.glb" --no-board-body "$build/pi4/pi4.kicad_pcb" 2>&1 | grep -v 'image handler\|outline is malformed' || true
ls -l "$build"/*.glb
