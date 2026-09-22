# Standalone characters

Two transparent renders of each of the 27 characters: 54 PNGs at the full
1393 × 1393 canvas, so every file shares the collection's registration (the face
sits at ~(690, 601) in all of them).

Each file has the minimum kit: **character, skin, eyes and mouth**. It has no
background plate, arm, footwear or sticker. The renders come from the
production compositor, with the plate-side `GROUND_SHADOW` and
`SUBJECT_SEPARATION` turned off because there is no plate to seat the figure
into. Every shadow on the figure itself (skin, eyes, mouth, face inset) is kept.

The traits are dealt round-robin from a seeded shuffle. Every skin, eye and
mouth appears about equally often, and a character's two variants never share
a skin, an eye or a mouth. `manifest.json` lists each file's traits.
`_contact_sheet.jpg` shows the whole set over grey.

Regenerate: `python3 asset_assessment/export_standalone_characters.py`
(`--variants N`, `--seed N`, `--only <character>`).
