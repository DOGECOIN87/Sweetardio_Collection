# Weather distinctness — blue_dusk, 6 plates

Mean CIE76 dE over the exposed plate, averaged across 6 different plates.
Seed 4444. Plates: RIP_Gorbagana, Sweetardio_116 (20), UAP_Taskforce, Legendary_Opengotchi, Winning, Emblem.

Closest ALREADY-APPROVED pair: `clear` / `overcast` at dE 2.7 — context, not the bar.
DISTINCT_DE is 6.0, set deliberately above it: a new state entering a table
whose ceiling is six has to separate harder than a pair that has been in the set
from the start and is distinguished elsewhere in the matrix.

| new state | vs | dE | vs whole table (min) | verdict |
|---|---|---|---|---|
| `blizzard` | `snow` | 44.8 | 21.6 (`fog`) | distinct |
| `tornado` | `storm` | 19.5 | 16.5 (`snow`) | distinct |

Full matrix (dE):

| | clear | overcast | fog | rain | snow | storm | blizzard | tornado |
|---|---|---|---|---|---|---|---|---|
| **clear** | — | 2.7 | 29.1 | 3.7 | 6.2 | 11.9 | 50.6 | 17.7 |
| **overcast** | 2.7 | — | 27.8 | 3.3 | 4.8 | 12.4 | 49.4 | 16.6 |
| **fog** | 29.1 | 27.8 | — | 30.3 | 23.5 | 38.8 | 21.6 | 28.3 |
| **rain** | 3.7 | 3.3 | 30.3 | — | 7.3 | 9.4 | 51.9 | 16.5 |
| **snow** | 6.2 | 4.8 | 23.5 | 7.3 | — | 16.1 | 44.8 | 16.5 |
| **storm** | 11.9 | 12.4 | 38.8 | 9.4 | 16.1 | — | 60.3 | 19.5 |
| **blizzard** | 50.6 | 49.4 | 21.6 | 51.9 | 44.8 | 60.3 | — | 47.5 |
| **tornado** | 17.7 | 16.6 | 28.3 | 16.5 | 16.5 | 19.5 | 47.5 | — |
