# Weather distinctness — blue_dusk, 6 plates

Mean CIE76 dE over the exposed plate, averaged across 6 different plates.
Seed 4444. Plates: RIP_Gorbagana, Sweetardio_116 (20), UAP_Taskforce, Legendary_Opengotchi, Winning, Emblem.

Closest ALREADY-APPROVED pair: `overcast` / `rain` at dE 3.3 — context, not the bar.
DISTINCT_DE is 6.0, set deliberately above it: a new state entering a table
whose ceiling is six has to separate harder than a pair that has been in the set
from the start and is distinguished elsewhere in the matrix.

| state | plate detail kept | plate chroma kept |
|---|---|---|
| `overcast` | 70% | 82% |
| `fog` | 29% | 86% |
| `rain` | 79% | 71% |
| `snow` | 81% | 66% |
| `storm` | 97% | 53% |
| `blizzard` | 26% | 55% |
| `tornado` | 44% | 19% |

Worst of the 6 plates, against the SAME PHASE WITH NO WEATHER — so the number is
what the weather costs, not what the hour of day costs. The per-state floors live in
`verify_sky.py`'s `PLATE_DETAIL_FLOOR`, which fails the build if a state drifts past its own.

| new state | vs | dE | vs whole table (min) | verdict |
|---|---|---|---|---|
| `blizzard` | `snow` | 32.2 | 18.4 (`fog`) | distinct |
| `tornado` | `storm` | 19.0 | 13.7 (`snow`) | distinct |

Full matrix (dE):

| | overcast | fog | rain | snow | storm | blizzard | tornado |
|---|---|---|---|---|---|---|---|
| **overcast** | — | 18.2 | 3.3 | 4.8 | 12.4 | 36.5 | 13.9 |
| **fog** | 18.2 | — | 20.9 | 14.4 | 29.7 | 18.4 | 22.5 |
| **rain** | 3.3 | 20.9 | — | 7.3 | 9.4 | 39.1 | 14.3 |
| **snow** | 4.8 | 14.4 | 7.3 | — | 16.1 | 32.2 | 13.7 |
| **storm** | 12.4 | 29.7 | 9.4 | 16.1 | — | 47.6 | 19.0 |
| **blizzard** | 36.5 | 18.4 | 39.1 | 32.2 | 47.6 | — | 34.6 |
| **tornado** | 13.9 | 22.5 | 14.3 | 13.7 | 19.0 | 34.6 | — |
