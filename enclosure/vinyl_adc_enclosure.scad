// Vinyl ADC - parametric two-part enclosure (base + lid) for the 4-tier
// 100 x 100 mm PCB stack.  OpenSCAD 2021.01 compatible.
//
// Every dimension comes from vinyl_adc_params.scad, which make_params.py
// derives from the KiCad boards (outline, mounting holes, connector
// positions) and the kicad-cli GLB exports (component heights).
//
// Frame: origin at the outer bottom-left-FRONT corner of the base.
//        X right, Y toward the back, Z up.  KiCad "top of screen" is the back.
//
// Export:
//   openscad.com -o vinyl-adc-base.stl -D part="\"base\"" vinyl_adc_enclosure.scad
//   openscad.com -o vinyl-adc-lid.stl  -D part="\"lid\""  vinyl_adc_enclosure.scad
//
// Print orientation (no supports needed):
//   base : as modelled, floor on the bed.  Walls vertical, bosses vertical.
//          The two LINE IN windows are 12 mm bridges - normal FDM bridging.
//          The Pi ribbon notch is open to the top edge, so nothing to bridge.
//   lid  : flip 180 deg (top face on the bed, lip pointing up).  The screw
//          counterbores then face the bed and print as short 6.5 mm bridges.

include <vinyl_adc_params.scad>

part = "assembly";   // "base" | "lid" | "assembly" | "exploded"
$fn = 48;
eps = 0.01;

// ------------------------------------------------------------------ helpers
module rounded_box(size, r) {
    // box with rounded vertical edges, corner at origin
    hull()
        for (x = [r, size[0] - r], y = [r, size[1] - r])
            translate([x, y, 0]) cylinder(r = r, h = size[2]);
}

// ------------------------------------------------------------------ base
module base_solid() {
    difference() {
        rounded_box([OUTER, OUTER, Z_LID_UNDER], CORNER_R);
        // cavity
        translate([WALL, WALL, FLOOR]) cube([INNER, INNER, Z_LID_UNDER]);
    }
    // floor bosses for the tier-1 standoffs (M3 heat-set inserts)
    for (h = HOLES)
        translate([h[0], h[1], FLOOR - eps]) cylinder(d = BOSS_D, h = BOSS_H + eps);
}

module base_cutters() {
    // heat-set insert holes in the bosses
    for (h = HOLES)
        translate([h[0], h[1], FLOOR + BOSS_H - INSERT_DEPTH]) cylinder(d = INSERT_D, h = INSERT_DEPTH + 1);
    // LINE IN windows on the +X wall  [y0, y1, z0, z1]
    for (w = WINDOWS_PX)
        translate([OUTER - WALL - eps, w[0], w[2]]) cube([WALL + 2 * eps, w[1] - w[0], w[3] - w[2]]);
    // gain-trimmer screwdriver holes on the -Y wall  [x, z, d]
    for (t = HOLES_MY)
        translate([t[0], -eps, t[1]]) rotate([-90, 0, 0]) cylinder(d = t[2], h = WALL + 2 * eps);
    // Pi ribbon notch on the -Y wall, open to the top edge  [x0, x1, z0, z1]
    for (n = NOTCHES_MY)
        translate([n[0], -eps, n[2]]) cube([n[1] - n[0], WALL + 2 * eps, n[3] - n[2] + 1]);
}

module base() {
    difference() {
        base_solid();
        base_cutters();
    }
}

// ------------------------------------------------------------------ lid
lip_out = INNER - 2 * LID_LIP_CLR;   // outer size of the locating lip

module lid() {
    // modelled in place: plate from Z_LID_UNDER to Z_OUTER_TOP, lip below it
    difference() {
        union() {
            translate([0, 0, Z_LID_UNDER]) rounded_box([OUTER, OUTER, LID_T], CORNER_R);
            // locating lip, drops inside the wall
            translate([WALL + LID_LIP_CLR, WALL + LID_LIP_CLR, Z_LID_UNDER - LID_LIP_H])
                difference() {
                    cube([lip_out, lip_out, LID_LIP_H + eps]);
                    translate([LID_LIP_T, LID_LIP_T, -eps])
                        cube([lip_out - 2 * LID_LIP_T, lip_out - 2 * LID_LIP_T, LID_LIP_H + 3 * eps]);
                }
        }
        // M3 screws into the top standoffs: through hole + counterbore
        for (h = HOLES) {
            translate([h[0], h[1], Z_LID_UNDER - LID_LIP_H - 1]) cylinder(d = 3.4, h = LID_T + LID_LIP_H + 2);
            translate([h[0], h[1], Z_OUTER_TOP - 2]) cylinder(d = 6.5, h = 2 + eps);
        }
        // engraved label, 0.6 mm deep
        translate([OUTER / 2, OUTER / 2, Z_OUTER_TOP - 0.6])
            linear_extrude(0.6 + eps) {
                translate([0, 6]) text("VINYL ADC", size = 9, halign = "center", valign = "center", font = "Liberation Sans:style=Bold");
                translate([0, -7]) text("discrete 3rd-order delta-sigma", size = 4, halign = "center", valign = "center", font = "Liberation Sans");
            }
    }
}

// ------------------------------------------------------------------ preview
module standoff(len) { color("goldenrod") cylinder(d = 5.5, h = len, $fn = 6); }

module preview_stack(explode = 0) {
    for (i = [0 : len(TIER_Z_TOP) - 1]) {
        z = TIER_Z_TOP[i] + i * explode;
        color("darkgreen") translate([WALL + CLR, WALL + CLR, z - T_PCB]) cube([BOARD, BOARD, T_PCB]);
        for (h = HOLES) translate([h[0], h[1], z]) standoff(STANDOFF);
    }
}

if (part == "base") base();
else if (part == "lid") lid();
else if (part == "exploded") {
    base();
    preview_stack(12);
    translate([0, 0, 60]) lid();
} else {
    base();
    preview_stack(0);
    lid();
}
