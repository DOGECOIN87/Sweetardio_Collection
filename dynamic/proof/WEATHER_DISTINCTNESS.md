# Weather distinctness — day, 6 plates

Mean CIE76 dE over the exposed plate, averaged across 6 different plates.
Seed 4444. Plates: RIP_Gorbagana, Sweetardio_116 (20), UAP_Taskforce, Legendary_Opengotchi, Winning, Emblem.

Closest ALREADY-APPROVED pair: `rain` / `snow` at dE 9.8 — context, not the bar.
DISTINCT_DE is 6.0, set deliberately above it: a new state entering a capped
table has to separate harder than a pair that has been in the set from the start and
is distinguished elsewhere in the matrix.

| state | plate detail kept | plate chroma kept |
|---|---|---|
| `fog` | 35% | 57% |
| `rain` | 82% | 55% |
| `snow` | 76% | 54% |
| `storm` | 99% | 25% |
| `blizzard` | 38% | 42% |
| `tornado` | 57% | 31% |
| `flooded` | 50% | 93% |

Worst of the 6 plates, against the SAME PHASE WITH NO WEATHER — so the number is
what the weather costs, not what the hour of day costs. The per-state floors live in
`verify_sky.py`'s `PLATE_DETAIL_FLOOR`, which fails the build if a state drifts past its own.

| new state | vs | dE | vs whole table (min) | verdict |
|---|---|---|---|---|
| `blizzard` | `snow` | 20.7 | 9.9 (`fog`) | distinct |
| `tornado` | `storm` | 15.9 | 7.1 (`rain`) | distinct |
| `flooded` | `rain` | 10.3 | 8.6 (`snow`) | distinct |

Full matrix (dE):

| | fog | rain | snow | storm | blizzard | tornado | flooded |
|---|---|---|---|---|---|---|---|
| **fog** | — | 21.0 | 12.4 | 33.9 | 9.9 | 22.5 | 14.9 |
| **rain** | 21.0 | — | 9.8 | 13.5 | 30.1 | 7.1 | 10.3 |
| **snow** | 12.4 | 9.8 | — | 22.9 | 20.7 | 12.3 | 8.6 |
| **storm** | 33.9 | 13.5 | 22.9 | — | 42.8 | 15.9 | 20.9 |
| **blizzard** | 9.9 | 30.1 | 20.7 | 42.8 | — | 30.3 | 24.0 |
| **tornado** | 22.5 | 7.1 | 12.3 | 15.9 | 30.3 | — | 13.1 |
| **flooded** | 14.9 | 10.3 | 8.6 | 20.9 | 24.0 | 13.1 | — |
