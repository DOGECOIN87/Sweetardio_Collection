# Weather distinctness — blue_dusk, 6 plates

Mean CIE76 dE over the exposed plate, averaged across 6 different plates.
Seed 4444. Plates: RIP_Gorbagana, Sweetardio_116 (20), UAP_Taskforce, Legendary_Opengotchi, Winning, Emblem.

Closest ALREADY-APPROVED pair: `rain` / `snow` at dE 7.3 — context, not the bar.
DISTINCT_DE is 6.0, set deliberately above it: a new state entering a capped
table has to separate harder than a pair that has been in the set from the start and
is distinguished elsewhere in the matrix.

| state | plate detail kept | plate chroma kept |
|---|---|---|
| `fog` | 29% | 86% |
| `rain` | 79% | 71% |
| `snow` | 81% | 66% |
| `storm` | 97% | 53% |
| `blizzard` | 26% | 55% |
| `tornado` | 45% | 19% |
| `flooded` | 38% | 112% |

Worst of the 6 plates, against the SAME PHASE WITH NO WEATHER — so the number is
what the weather costs, not what the hour of day costs. The per-state floors live in
`verify_sky.py`'s `PLATE_DETAIL_FLOOR`, which fails the build if a state drifts past its own.

| new state | vs | dE | vs whole table (min) | verdict |
|---|---|---|---|---|
| `blizzard` | `snow` | 32.2 | 18.4 (`fog`) | distinct |
| `tornado` | `storm` | 18.8 | 13.7 (`flooded`) | distinct |
| `flooded` | `rain` | 11.7 | 8.0 (`snow`) | distinct |

Full matrix (dE):

| | fog | rain | snow | storm | blizzard | tornado | flooded |
|---|---|---|---|---|---|---|---|
| **fog** | — | 20.9 | 14.4 | 29.7 | 18.4 | 22.6 | 13.8 |
| **rain** | 20.9 | — | 7.3 | 9.4 | 39.1 | 14.2 | 11.7 |
| **snow** | 14.4 | 7.3 | — | 16.1 | 32.2 | 13.7 | 8.0 |
| **storm** | 29.7 | 9.4 | 16.1 | — | 47.6 | 18.8 | 19.4 |
| **blizzard** | 18.4 | 39.1 | 32.2 | 47.6 | — | 34.7 | 29.7 |
| **tornado** | 22.6 | 14.2 | 13.7 | 18.8 | 34.7 | — | 13.7 |
| **flooded** | 13.8 | 11.7 | 8.0 | 19.4 | 29.7 | 13.7 | — |
