# Weather distinctness — blue_dusk, 6 plates

Mean CIE76 dE over the exposed plate, averaged across 6 different plates.
Seed 4444. Plates: RIP_Gorbagana, Sweetardio_116 (20), UAP_Taskforce, Legendary_Opengotchi, Winning, Emblem.

Closest ALREADY-APPROVED pair: `clear` / `overcast` at dE 2.7. That is the bar a new
state has to clear to be as distinct as something the collection already ships;
DISTINCT_DE is set at 6.0.

| new state | vs | dE | vs whole table (min) | verdict |
|---|---|---|---|---|
| `blizzard` | `snow` | 44.8 | 21.6 (`fog`) | distinct |
| `tornado` | `storm` | 19.3 | 16.4 (`snow`) | distinct |

Full matrix (dE):

| | clear | overcast | fog | rain | snow | storm | blizzard | tornado |
|---|---|---|---|---|---|---|---|---|
| **clear** | — | 2.7 | 29.1 | 3.7 | 6.2 | 11.9 | 50.6 | 17.6 |
| **overcast** | 2.7 | — | 27.8 | 3.3 | 4.8 | 12.4 | 49.4 | 16.5 |
| **fog** | 29.1 | 27.8 | — | 30.3 | 23.5 | 38.8 | 21.6 | 28.5 |
| **rain** | 3.7 | 3.3 | 30.3 | — | 7.3 | 9.4 | 51.9 | 16.4 |
| **snow** | 6.2 | 4.8 | 23.5 | 7.3 | — | 16.1 | 44.8 | 16.4 |
| **storm** | 11.9 | 12.4 | 38.8 | 9.4 | 16.1 | — | 60.3 | 19.3 |
| **blizzard** | 50.6 | 49.4 | 21.6 | 51.9 | 44.8 | 60.3 | — | 47.7 |
| **tornado** | 17.6 | 16.5 | 28.5 | 16.4 | 16.4 | 19.3 | 47.7 | — |
