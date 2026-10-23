#!/usr/bin/env bash
# Export the rev D HAT to STEP in the enclosure's board frame (SPEC section 1):
# origin at the board's front-left corner (KiCad page 51.06, 157.5). KiCad puts the
# board bottom at z = 0; build_assembly.json moves it down 1.6 so z = 0 is the top face.
# Same terminal-block model swap as hardware/kicad/rev_d/render/export_model.sh.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../../../.." && pwd)"
tmp="$(mktemp -d)"
sed 's#${KICAD9_3DMODEL_DIR}/TerminalBlock.3dshapes/TerminalBlock_bornier-2_P5.08mm.step#${KICAD10_3DMODEL_DIR}/TerminalBlock_Phoenix.3dshapes/TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal.step#' \
    "$repo/hardware/kicad/rev_d/vinyl_adc_rev_d.kicad_pcb" > "$tmp/hat.kicad_pcb"
cp "$repo/hardware/kicad/rev_d/vinyl_adc_rev_d.kicad_pro" "$tmp/hat.kicad_pro"
"$repo/tools/capped" -m 3G kicad-cli pcb export step -f --subst-models --user-origin 51.06x157.5mm \
    -o "$here/../parts/hat_rev_d.step" "$tmp/hat.kicad_pcb"
rm -rf "$tmp"
