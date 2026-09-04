// =============================================================================
// Vinyl ADC - Parametric 3D-Printable Enclosure
// Compatible with OpenSCAD 2021.01+
// Generates: vinyl-adc-base.stl and vinyl-adc-lid.stl
// =============================================================================

/* [Part Selection] */
// Which part to render: "both", "base", "lid"
part = "both"; // [both, base, lid]

/* [General Dimensions] */
board_w = 100.0;          // PCB Width (X) in mm
board_d = 100.0;          // PCB Depth (Y) in mm
board_clearance = 0.5;    // 0.5 mm clearance on all sides as specified
wall_th = 3.0;            // 3.0 mm wall thickness as specified
floor_th = 3.0;           // 3.0 mm bottom floor thickness
lid_th = 3.0;             // 3.0 mm top lid thickness
corner_radius = 4.0;      // Outer corner filleting

/* [Internal Standoff & Stack Geometry] */
pcb_hole_offset = 44.0;   // Distance of M3 holes from PCB center (+/-44.0 mm)
boss_od = 8.0;            // PCB mounting boss outer diameter
boss_h = 6.0;             // Bottom standoff boss height
screw_hole_d = 2.9;       // Pilot diameter for M3 heat-set insert or direct thread
clearance_hole_d = 3.4;   // M3 clearance hole diameter
cavity_h = 59.0;          // Total inner cavity height (fits 4-board stack)

/* [Derived Dimensions] */
cavity_w = board_w + 2 * board_clearance; // 101.0 mm
cavity_d = board_d + 2 * board_clearance; // 101.0 mm
outer_w  = cavity_w + 2 * wall_th;         // 107.0 mm
outer_d  = cavity_d + 2 * wall_th;         // 107.0 mm
total_h  = floor_th + cavity_h;            // 62.0 mm

corner_boss_offset_x = cavity_w / 2 - 2.5; // Corner boss position
corner_boss_offset_y = cavity_d / 2 - 2.5;

$fn = 64; // High mesh resolution for clean arcs and manifold exports

// =============================================================================
// Helper Modules
// =============================================================================

module rounded_box(w, d, h, r) {
    translate([0, 0, h / 2])
    hull() {
        for (x = [-w/2 + r, w/2 - r]) {
            for (y = [-d/2 + r, d/2 - r]) {
                translate([x, y, 0])
                    cylinder(h = h, r = r, center = true);
            }
        }
    }
}

// =============================================================================
// Base Enclosure Module
// =============================================================================
module enclosure_base() {
    difference() {
        union() {
            // Main outer body
            rounded_box(outer_w, outer_d, total_h, corner_radius);
            
            // 4x Corner screw boss columns for lid retention
            for (x = [-corner_boss_offset_x, corner_boss_offset_x]) {
                for (y = [-corner_boss_offset_y, corner_boss_offset_y]) {
                    translate([x, y, floor_th])
                        cylinder(h = cavity_h, d = 9.0);
                }
            }
            
            // 4x PCB floor mounting bosses (M3, at +/-44.0 mm)
            for (x = [-pcb_hole_offset, pcb_hole_offset]) {
                for (y = [-pcb_hole_offset, pcb_hole_offset]) {
                    translate([x, y, floor_th])
                        cylinder(h = boss_h, d = boss_od);
                }
            }
        }
        
        // Subtract main inner cavity (leaving 3 mm walls and 3 mm floor)
        translate([0, 0, floor_th + cavity_h / 2 + 0.1])
            cube([cavity_w, cavity_d, cavity_h + 0.2], center = true);
            
        // 4x PCB mounting boss screw holes (M3 pilot / insert bore)
        for (x = [-pcb_hole_offset, pcb_hole_offset]) {
            for (y = [-pcb_hole_offset, pcb_hole_offset]) {
                // Blind hole into floor for heat-set or underside screw
                translate([x, y, -0.5])
                    cylinder(h = floor_th + boss_h + 1.0, d = screw_hole_d);
                // Underside M3 screw head counterbore
                translate([x, y, -0.5])
                    cylinder(h = 1.8, d = 6.0);
            }
        }
        
        // 4x Corner lid screw holes (M3 heat-set insert holes at top)
        for (x = [-corner_boss_offset_x, corner_boss_offset_x]) {
            for (y = [-corner_boss_offset_y, corner_boss_offset_y]) {
                translate([x, y, total_h - 10.0])
                    cylinder(h = 10.5, d = screw_hole_d);
            }
        }
        
        // =====================================================================
        // Connector Cutouts (Exact PCB Coordinates)
        // =====================================================================
        
        // --- RIGHT WALL (X = +outer_w / 2): Analog Inputs & Ground ---
        // 1. Right Channel RCA Input (Tier 2): Center Y = 25.0 mm, Z = 26.0 mm
        translate([outer_w / 2 - wall_th - 1.0, 25.0, 26.0])
            rotate([0, 90, 0])
                cylinder(h = wall_th + 2.0, d = 10.0);
                
        // 2. Left Channel RCA Input (Tier 3): Center Y = 40.0 mm, Z = 38.0 mm
        translate([outer_w / 2 - wall_th - 1.0, 40.0, 38.0])
            rotate([0, 90, 0])
                cylinder(h = wall_th + 2.0, d = 10.0);
                
        // 3. Chassis Ground Binding Post: Center Y = 8.0 mm, Z = 32.0 mm
        translate([outer_w / 2 - wall_th - 1.0, 8.0, 32.0])
            rotate([0, 90, 0])
                cylinder(h = wall_th + 2.0, d = 6.5);
                
        // --- REAR WALL (Y = +outer_d / 2): Digital & Power Interfaces ---
        // 4. Raspberry Pi GPIO / Interleaved PDM Egress Slot (Tier 4, J2 at X = -9.78 mm)
        // Center X = -9.78 mm, Z = 48.0 mm, Slot 34 x 10 mm
        translate([-9.78, outer_d / 2 - wall_th - 1.0, 48.0])
            rotate([-90, 0, 0])
                hull() {
                    translate([-12.0, 0, 0]) cylinder(h = wall_th + 2.0, d = 10.0);
                    translate([ 12.0, 0, 0]) cylinder(h = wall_th + 2.0, d = 10.0);
                }
                
        // 5. 5V DC Power Input Port (Tier 1 Power Board): Center X = 25.0 mm, Z = 12.0 mm
        translate([25.0, outer_d / 2 - wall_th - 1.0, 12.0])
            rotate([-90, 0, 0])
                cylinder(h = wall_th + 2.0, d = 8.5);
                
        // --- FRONT WALL (Y = -outer_d / 2): Controls & Indicators ---
        // 6. Input Level Gain Trim Potentiometer Aperture (RV20): Center X = -25.0 mm, Z = 32.0 mm
        translate([-25.0, -outer_d / 2 - 1.0, 32.0])
            rotate([-90, 0, 0])
                cylinder(h = wall_th + 2.0, d = 7.5);
                
        // 7. Power / Clip Indicator LED: Center X = 25.0 mm, Z = 32.0 mm
        translate([25.0, -outer_d / 2 - 1.0, 32.0])
            rotate([-90, 0, 0])
                cylinder(h = wall_th + 2.0, d = 3.5);
    }
}

// =============================================================================
// Lid Module (Printable Flat, Zero Supports)
// =============================================================================
module enclosure_lid() {
    difference() {
        union() {
            // Main lid plate (107.0 x 107.0 x 3.0 mm)
            rounded_box(outer_w, outer_d, lid_th, corner_radius);
            
            // Alignment / friction-fit locating lip (2.0 mm step into cavity)
            translate([0, 0, -1.0])
                rounded_box(cavity_w - 0.4, cavity_d - 0.4, 2.0, corner_radius - 1.0);
        }
        
        // 4x M3 mounting screw counterbored holes
        for (x = [-corner_boss_offset_x, corner_boss_offset_x]) {
            for (y = [-corner_boss_offset_y, corner_boss_offset_y]) {
                // Through clearance hole
                translate([x, y, -2.5])
                    cylinder(h = lid_th + 5.0, d = clearance_hole_d);
                // Counterbore for M3 socket / button head screw
                translate([x, y, lid_th - 1.6])
                    cylinder(h = 2.0, d = 6.2);
            }
        }
    }
}

// =============================================================================
// Output Rendering Dispatch
// =============================================================================
if (part == "base") {
    enclosure_base();
} else if (part == "lid") {
    // Oriented flat on build bed for 100% support-free FDM printing
    translate([0, 0, 0])
        enclosure_lid();
} else {
    // Both assembled preview
    color([0.2, 0.2, 0.22, 1.0])
        enclosure_base();
    color([0.9, 0.9, 0.95, 0.7])
        translate([0, 0, total_h + 1.5])
            enclosure_lid();
}
