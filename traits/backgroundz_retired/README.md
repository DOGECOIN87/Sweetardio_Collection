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
