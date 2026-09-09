%
O0001
( gerber2rml - SRM-20 NC )
( vinyl_adc_osc - step 0 of 4: DRY RUN )
( spindle OFF, bit held 5 mm up - this file cannot cut )
( watch it trace the outline, then run the traces file )
G90 G17
G21
G91
G28 Z0.
G90
G54
( DRY RUN - spindle stays OFF, nothing is cut )
G0 Z5.
G0 X103.719 Y69.787
G1 X61.819 Y69.787 Z5. F900.
G1 X61.819 Y25.787 Z5.
G1 X103.719 Y25.787 Z5.
G1 X103.719 Y69.787 Z5.
G0 Z2.
G91
G28 Z0.
G90
M5
G91
G28 X0. Y0.
G90
M30
%
