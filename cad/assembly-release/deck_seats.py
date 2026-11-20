"""Retain the four electronics deck sections on the actual two crossmembers."""

from shop import stock, add, drill, article, rect, round_stock, hexagon


def build(existing):
    articles = {}
    rail_ops = {}
    for name in (
        "left electronics deck",
        "right electronics deck",
        "fore electronics deck bridge",
        "aft electronics deck bridge",
    ):
        if name in existing:
            row = existing[name]
            side = 1 if name.startswith("left") else -1
            seats = [
                (-151, 54 * side),
                (-151, 238 * side),
                (129, 110 * side),
                (129, 238 * side),
            ]
        else:
            aft = name.startswith("aft")
            lo, hi = (-178, -137) if aft else (54, 167)
            row = article(
                name,
                "structure",
                "Aluminum 6061",
                [stock(rect([lo, -44, 122], [hi, 47, 129]))],
                parent="rear deck crossmember" if aft else "front deck crossmember",
                connection="Two top-access counterbored screws and welded threaded bosses retain the bridge. Service the electrical articles above it first.",
            )
            existing[name] = row
            seats = [(-151 if aft else 129, y) for y in (-23, 24)]
        row["connection"] = (
            "Counterbored M5 button screws clamp the deck against the fully supported crossmember flat. Remove hardware above the target deck before changing it."
        )
        for i, (x, y) in enumerate(seats, 1):
            stem = name + " retainer " + str(i)
            rail = ("rear" if x < 0 else "front") + " deck crossmember"

            def pole(z, to, r, inner=0):
                return round_stock([x, y, z], [x, y, to], r, inner)

            row["features"].extend(
                [drill(pole(121, 130, 2.75)), drill(pole(126, 130, 5))]
            )
            rail_ops.setdefault(rail, []).append(drill(pole(118, 123, 5.05)))
            boss = stem + " welded boss"
            articles[boss] = article(
                boss,
                "structure",
                "Aluminum 6061",
                [stock(pole(110, 122, 5, 2.1))],
                parent=rail,
                connection="10mm OD, 12 mm long welded insert. Ø4.2 through pilot; tap M5x0.8-6H after weld and flush-face.",
                purchase="6061-T6 10 mm finished round boss",
            )
            articles[stem + " screw"] = article(
                stem + " screw",
                "fastener",
                "Steel, Carbon",
                [
                    stock(pole(110, 126, 2.5)),
                    add(pole(126, 128.75, 4.75)),
                    drill(hexagon([x, y, 128.76], [x, y, 127.1], 3)),
                ],
                parent=boss,
                connection="ISO 7380-1 M5x16. 3 mm deep head counterbore leaves 4 mm effective stock over the beam; nominal 12 mm threaded length.",
                purchase="ISO 7380-1 M5x16 button head",
            )
    return articles, rail_ops
