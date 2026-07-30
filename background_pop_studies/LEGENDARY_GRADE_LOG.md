# ULTIMATE GRADE LOG - Sweetardio background pop

Engine: `background_pop_studies/grade.py` · source `traits/backgrounds_pop_originals` -> output `traits/backgrounds_pop` · 4 plates

Targets derived from Phase 1 measurements: mid-key anchor L* = 130 (midpoint of darkest body 54 / brightest body 206), stage saturation 0.30 (body mean 0.629), split-tone COOL (bodies measure +62.3 warm). Every parameter below is a continuous function of the plate's measured L/S/busyness/temperature.

| plate | L | Lstd | S | temp | edge | op% | p_midkey | c_scurve | f_sat | warm_n | a_sh | a_hl | busy_n | blur_px | lc_cut | vignette | bloom | overlay | L_out | S_out | temp_out |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Legendary_Just_Aliens.png | 44.1 | 34.8 | 0.333 | -8.6 | 5.6 | 100 | 0.591 | 0.320 | 0.926 | 0.485 | 0.078 | 0.048 | 0.000 | 0.00 | 0.000 | 0.101 | 0.100 |  | 76.5 | 0.336 | -20.5 |
| Legendary_Opengotchi.png | 30.6 | 27.6 | 0.605 | -22.6 | 9.1 | 100 | 0.550 | 0.320 | 0.591 | 0.290 | 0.046 | 0.029 | 0.000 | 0.00 | 0.000 | 0.100 | 0.100 |  | 66.0 | 0.464 | -36.8 |
| Legendary_Simplex.png | 28.0 | 27.3 | 0.642 | -22.4 | 7.0 | 100 | 0.550 | 0.320 | 0.565 | 0.292 | 0.047 | 0.029 | 0.000 | 0.00 | 0.000 | 0.100 | 0.100 |  | 61.1 | 0.497 | -37.2 |
| Legendary_Tenders.png | 28.7 | 31.2 | 0.444 | -8.9 | 11.2 | 100 | 0.550 | 0.320 | 0.746 | 0.480 | 0.077 | 0.048 | 0.002 | 0.01 | 0.001 | 0.100 | 0.100 |  | 61.3 | 0.390 | -23.4 |

## Cohesion summary (opaque-pixel means)

| metric | before (min / mean / max) | after (min / mean / max) |
|---|---|---|
| L | 28 / 33 / 44 | 61 / 66 / 76 |
| S | 0.33 / 0.51 / 0.64 | 0.34 / 0.42 / 0.50 |
| temp R-B | -23 / -16 / -9 | -37 / -29 / -20 |

L spread (std) 6.6 -> 6.2; S spread 0.12 -> 0.06; temp spread 6.9 -> 7.6.

Note: the run graded 13 plates; 9 were later retired from the collection.
Their rows are dropped above and the cohesion summary is recomputed over
the 4 surviving plates. `Legendary_Sarv.png` was renamed
`Legendary_Opengotchi.png` at the same time.
