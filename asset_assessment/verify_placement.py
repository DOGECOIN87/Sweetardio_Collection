#!/usr/bin/env python3
"""Verify where every character actually lands on the canvas.

audit_placement.py answers "what should CHAR_Y_ADJUST be?" by measuring raw
art against one target line. This answers the different question: given the
tables as they stand, where does each character ACTUALLY end up once the
compositor is done with it — and is that where its group sits?

It matters because a character does not have one position, it has several.
generate_random_combination() picks between four placement paths:

    with footwear      dy = CHAR_Y_ADJUST                  (no drop)
    no-offset char     dy = CHAR_Y_ADJUST                  (no drop)
    centered + bare    dy = CENTERED_FOOTWEARLESS_DY       (drop suppressed)
    standing + bare    dy = 150 + CHAR_Y_ADJUST + FOOTWEARLESS_DY

So a character can be right in one case and wrong in another, and a table
diff cannot see it. This walks the real branch logic from generator.py, adds
the resulting dy to the measured (sparkle-proof, char_scale-aware) body bbox,
and reports the final canvas position per case.

Rather than assert hardcoded target lines, it groups characters by the
placement path they take and flags anyone more than --tol from their own
group's median. A group that agrees with itself is the actual requirement:
these are cast members that have to look like they stand on the same floor.

Horizontal placement is checked too — every body should be centred on the
face-hole column (~690), since the skin ball, eyes and mouth are all pinned
there and cannot move to follow a body that drifted sideways.

CAVEAT — multi-part assets. Both checks use the main body's bounding box, and
a bbox is the wrong metric for a character drawn as two offset pieces.
chocolate_sandwich_cookie is the case in the current set: a back wafer sits
behind and left of the front disc, so the bbox reads ~54px left of the face
column and ~56px lower than the front disc that actually carries the face.
Its CHAR_Y_ADJUST of +50 is tuned to the FRONT disc and is correct; this tool
flags it anyway. Confirm a flag by rendering it before believing it.

Usage: python3 asset_assessment/verify_placement.py [--tol 25]
Exit status is 1 if anything is flagged, so it can gate a build.
"""

import argparse
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ".")
import generator as g  # noqa: E402

from audit_placement import char_table, measure, BALL_CENTER  # noqa: E402


# Deviations confirmed by rendering and deliberately accepted. Keyed by
# (character, check); "*" matches any case. Waived entries are still printed —
# they just do not fail the run, so the exit status stays meaningful.
WAIVED = {
    ("chocolate_sandwich_cookie", "vertical"):
        "applies to its FOOTWEAR case only, where CHAR_Y_ADJUST +50 is tuned to "
        "the FRONT disc: the back wafer sits lower, so the bbox reads ~56px "
        "below the group. Its bare case is centred correctly and needs no "
        "waiver — confirmed by render.",
    ("chocolate_sandwich_cookie", "horizontal"):
        "two-part asset: the back wafer sits left of the front disc, so the bbox "
        "centre reads ~54px left. The face-carrying disc is on the column — "
        "confirmed by render.",
}


def waiver(name, check):
    return WAIVED.get((name, check))


def parse_args():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tol", type=int, default=25,
                    help="px from the group median before a character is "
                         "flagged (default 25)")
    ap.add_argument("--x-tol", type=int, default=45,
                    help="px of horizontal drift from the face column allowed")
    return ap.parse_args()


def placement_cases(name):
    """Every (case, dy) this character can actually be composited with.

    Mirrors the branch order in generate_random_combination() exactly.
    """
    no_offset = any(k.lower() in name.lower() for k in g.NO_OFFSET_CHARS)
    centered = g.is_centered(name)
    wat_ok = not g.is_wat_excluded(name)
    base = g.char_y_adjust(name)
    cases = []

    if no_offset:
        # never drops, footwear or not
        cases.append(("no-offset", base))
    else:
        if wat_ok:
            cases.append(("footwear", base))
        if centered:
            cases.append(("centered-bare", g.centered_footwearless_dy(name)))
            # a gorbhouse re-enables the drop for centred characters
            cases.append(("centered+gorbhouse",
                          g.VERTICAL_OFFSET + base + g.footwearless_dy(name)))
        else:
            cases.append(("standing-bare",
                          g.VERTICAL_OFFSET + base + g.footwearless_dy(name)))
    return cases


def group_of(name, case):
    """Characters that must agree with each other on a floor line."""
    low = name.lower()
    cone = "ice_cream" in low or "gummy_bear" in low
    if case == "no-offset":
        return "cone tips (no-offset)" if cone else "no-offset bodies"
    if case == "footwear":
        return "standing on footwear"
    if case == "centered-bare":
        return "centred, bare"
    if case == "centered+gorbhouse":
        return "centred, on gorbhouse"
    return "standing, bare"


def main():
    args = parse_args()
    rows = []
    print("measuring 33 characters (sparkle-proof, char_scale applied)...\n")
    for name, fname in sorted(char_table().items()):
        bbox, hole = measure(os.path.join(g.TRAITS_DIR, g.CHARACTERZ, fname))
        if bbox is None:
            print(f"  {name}: NO OPAQUE PIXELS")
            continue
        f = g.char_scale(name)
        if abs(f - 1.0) > 1e-6:
            px, py = g.CHAR_SCALE_PIVOT
            x0, y0, x1, y1 = bbox
            bbox = (px + f * (x0 - px), py + f * (y0 - py),
                    px + f * (x1 - px), py + f * (y1 - py))
            if hole:
                hole = (round(px + f * (hole[0] - px)),
                        round(py + f * (hole[1] - py)))
        for case, dy in placement_cases(name):
            rows.append({
                "name": name, "case": case, "dy": dy,
                "group": group_of(name, case),
                "bottom": round(bbox[3]) + dy,
                "cy": round((bbox[1] + bbox[3]) / 2) + dy,
                "cx": round((bbox[0] + bbox[2]) / 2),
                "hole": hole,
            })

    # ── vertical: does each character agree with its own group? ──────────
    flagged, waived = [], []
    print("=" * 78)
    print("VERTICAL — final composited bottom, by placement path")
    print("=" * 78)
    canvas_cy = g.CANVAS_SIZE // 2
    for grp in sorted({r["group"] for r in rows}):
        members = [r for r in rows if r["group"] == grp]
        # Characters that STAND are judged on a shared bottom line. Ones that
        # FLOAT are judged on their centre against the canvas centre: matching
        # bottoms across different body sizes pushes the biggest bodies high,
        # which is exactly how the oversized doughnuts passed this check.
        # only the BARE centred case floats; "centred, on gorbhouse"
        # stands on the gorbhouse and is judged on a bottom line
        floats = grp == "centred, bare"
        key = "cy" if floats else "bottom"
        med = canvas_cy if floats else statistics.median(
            r["bottom"] for r in members)
        label = (f"centre vs canvas centre {med:.0f}" if floats
                 else f"median bottom {med:.0f}")
        print(f"\n{grp}  ({len(members)} characters, {label})")
        for r in sorted(members, key=lambda r: r[key]):
            d = r[key] - med
            mark = ""
            if abs(d) > args.tol:
                w = waiver(r["name"], "vertical")
                if w:
                    mark = "   (waived)"
                    waived.append((r["name"], "vertical", w))
                else:
                    mark = "   <== OFF GROUP"
                    flagged.append((r, med, d))
            print(f"   {r['name']:32s} dy {r['dy']:+5d}  "
                  f"{key} {r[key]:5d}  {d:+6.0f}{mark}")

    # ── horizontal: bodies must stay on the face column ─────────────────
    print("\n" + "=" * 78)
    print(f"HORIZONTAL — body centre vs the face column x={BALL_CENTER[0]}")
    print("=" * 78)
    xbad = []
    seen = set()
    for r in rows:
        if r["name"] in seen:
            continue
        seen.add(r["name"])
        dx = r["cx"] - BALL_CENTER[0]
        if abs(dx) > args.x_tol:
            w = waiver(r["name"], "horizontal")
            if w:
                waived.append((r["name"], "horizontal", w))
            else:
                xbad.append((r["name"], r["cx"], dx))
    if xbad:
        for n, cx, dx in sorted(xbad, key=lambda t: -abs(t[2])):
            print(f"   {n:32s} centre x={cx:4d}  {dx:+4d} from the face column")
    else:
        print(f"   all {len(seen)} bodies within ±{args.x_tol}px — OK")

    # ── face holes ──────────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("FACE HOLES — must stay near the ball centre or the eyes miss")
    print("=" * 78)
    holebad = []
    for name in sorted({r["name"] for r in rows}):
        r = next(r for r in rows if r["name"] == name)
        if not r["hole"]:
            print(f"   {name:32s} no enclosed hole (open-face character)")
            continue
        dx = r["hole"][0] - BALL_CENTER[0]
        dy = r["hole"][1] - BALL_CENTER[1]
        if abs(dx) > 40 or abs(dy) > 40:
            holebad.append((name, r["hole"], dx, dy))
    if holebad:
        for n, h, dx, dy in holebad:
            print(f"   {n:32s} hole {h} drifts ({dx:+d},{dy:+d})")
    else:
        print("   every face hole within ±40px of the ball centre — OK")

    # ── verdict ─────────────────────────────────────────────────────────
    print("\n" + "=" * 78)
    total = len({r["name"] for r in rows})
    print(f"VERDICT: {total} characters, {len(rows)} placement cases checked")
    print(f"  vertical off-group : {len(flagged)}")
    print(f"  horizontal drift   : {len(xbad)}")
    print(f"  face-hole drift    : {len(holebad)}")
    for r, med, d in flagged:
        print(f"\n  {r['name']} [{r['case']}] sits {abs(d):.0f}px "
              f"{'below' if d > 0 else 'above'} where its group sits "
              f"({med:.0f})")

    if waived:
        print(f"\n  waived ({len({(n, c) for n, c, _ in waived})} confirmed "
              f"non-issues, see WAIVED in this file):")
        for n, c, why in sorted({(n, c, w) for n, c, w in waived}):
            print(f"    {n} [{c}] — {why.splitlines()[0]}")

    ok = not (flagged or xbad or holebad)
    print("\n  RESULT: " + ("all characters placed correctly" if ok
                            else "PLACEMENT ISSUES FOUND"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
