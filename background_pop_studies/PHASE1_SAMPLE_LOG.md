# ULTIMATE GRADE LOG - Sweetardio background pop

Engine: `background_pop_studies/grade.py` · source `traits/backgroundz` -> output `traits/backgroundz_pop` · 4 plates

Targets derived from Phase 1 measurements: mid-key anchor L* = 130 (midpoint of darkest body 54 / brightest body 206), stage saturation 0.30 (body mean 0.629), split-tone COOL (bodies measure +62.3 warm). Every parameter below is a continuous function of the plate's measured L/S/busyness/temperature.

| plate | L | Lstd | S | temp | edge | op% | p_midkey | c_scurve | f_sat | warm_n | a_sh | a_hl | busy_n | blur_px | lc_cut | vignette | bloom | overlay | L_out | S_out | temp_out |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Sweetardio_11317.png | 144.4 | 34.4 | 0.319 | -47.6 | 9.2 | 100 | 1.097 | 0.320 | 0.955 | 0.038 | 0.006 | 0.004 | 0.000 | 0.00 | 0.000 | 0.179 | 0.100 |  | 135.9 | 0.309 | -42.1 |
| Sweetardio_11325.png | 109.8 | 43.5 | 0.319 | +43.5 | 16.7 | 100 | 0.884 | 0.199 | 0.955 | 0.999 | 0.160 | 0.100 | 0.690 | 4.81 | 0.242 | 0.155 | 0.100 |  | 114.9 | 0.241 | +31.4 |
| Sweetardio_114 (10).png | 13.3 | 23.7 | 0.772 | -12.5 | 7.1 | 100 | 0.550 | 0.320 | 0.492 | 0.428 | 0.069 | 0.043 | 0.000 | 0.00 | 0.000 | 0.100 | 0.100 |  | 33.4 | 0.615 | -26.7 |
| Sweetardio_114.png | 60.8 | 51.5 | 0.739 | -57.9 | 18.0 | 100 | 0.660 | 0.150 | 0.509 | 0.001 | 0.000 | 0.000 | 0.874 | 6.09 | 0.306 | 0.108 | 0.100 |  | 88.4 | 0.462 | -50.9 |

## Cohesion summary (opaque-pixel means)

| metric | before (min / mean / max) | after (min / mean / max) |
|---|---|---|
| L | 13 / 82 / 144 | 33 / 93 / 136 |
| S | 0.32 / 0.54 / 0.77 | 0.24 / 0.41 / 0.61 |
| temp R-B | -58 / -19 / +44 | -51 / -22 / +31 |

L spread (std) 49.6 -> 38.4; S spread 0.22 -> 0.14; temp spread 39.6 -> 32.1.
