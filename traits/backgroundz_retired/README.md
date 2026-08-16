# Retired background plates

Plates taken out of the collection. **Nothing here mints** — the generator
reads `traits/backgroundz`, and these are not in it.

They live here rather than being deleted for one specific reason:
`grade.py` grades *everything* in `traits/backgroundz_originals` into
`traits/backgroundz`, with no skip list. A retired plate whose ungraded source
stayed in that folder would silently reappear in the collection on the next
full regrade. Moving the source here is what makes the retirement stick.

Each `.png` in this folder is the **ungraded original**, which is what you
need to bring a plate back:

```bash
git mv traits/backgroundz_retired/<plate>.png traits/backgroundz_originals/
python3 background_pop_studies/grade.py --only <plate>
```

then re-add its `TRAIT_NAMES[BACKGROUNDZ]` entry in `generator.py`, rebuild the
three compat maps (`build_char_compat.py`, `build_eyez_compat.py`,
`build_wat_compat.py`), and re-run `calibrate_rarity.py` — a plate joining or
leaving re-randomises every downstream draw. `background_pop_studies/ULTIMATE_GRADE_LOG.md`
still holds each retired plate's grade row on purpose, since the engine is not
bit-identical across numpy/Pillow versions and the row is the only record of
what it was graded with.

`graded/` holds the graded copy of two plates whose deletion was blocked in the
environment this retirement was done in. They are derived artifacts —
regenerable from the original by the command above — and are kept only so the
mint folder could be left correct. Deleting that subfolder loses nothing.

## Retired 2026-08

| plate | why |
|---|---|
| `Celestial.png` | owner's cull |
| `Cookboy_Black_Enamel.png` | owner's cull — three of the four Cookboy foil colourways went, leaving Cookboy and Cookboy Chocolate |
| `Cookboy_Gold.png` | owner's cull |
| `Cookboy_Silver.png` | owner's cull |
| `Gummy_Bears.png` | owner's cull |
| `M&Ms.png` | owner's cull |
| `Pixie_Stix.png` | owner's cull |
| `Sweetardio (16).png` | never shipped — see below |

`Sweetardio (16).png` is the one entry here that was **never in the collection**
to begin with, so it is the only one with no graded copy to delete, no
`TRAIT_NAMES` entry to drop and no effect on the draw. It sat in
`backgroundz_originals` with no counterpart in `traits/backgroundz`, which is
precisely the state this folder exists to prevent: the next full `grade.py` run
would have minted it as an extra plate under a fallback display name and voided
the calibration, with nothing gating it.

It is a finished, on-brand plate — the Sweetardio storefront interior, a
companion shot to the `Sweetardio` conveyor plate — not a broken asset. It is
retired because it was never graded in, not because anything is wrong with it.
Bringing it back is the standard restore at the top of this file, plus a
re-render, since a new plate re-randomises every downstream draw. Note it would
also need a display name that is not `Store`, which `Store.png` already holds.
