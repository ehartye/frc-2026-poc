"""Serviceable MK ES17-12 cradle supported by both deck crossmembers, project coordinates in mm."""

from frame import tube
from shop import article, rect, round_stock, stock, drill, hexagon, add


def build():
    parts = {}

    def put(
        name,
        features,
        material,
        parent,
        connection,
        role="structure",
        purchase="6061-T6 fabricated stock",
    ):
        parts[name] = article(
            name,
            role,
            material,
            features,
            parent=parent,
            connection=connection,
            purchase=purchase,
        )

    body = "battery secured envelope"
    floor = "battery cradle floor"
    put(
        body,
        [stock(rect([-132, -36, 48], [49, 40, 215]))],
        "ABS Plastic",
        floor,
        "MK ES17-12 purchased article. Drawn overall envelope. Its 5.86 kg catalog mass includes the sealed contents once.",
        "electrical",
        "MK ES17-12 F3 (one battery from AndyMark am-0844)",
    )
    parts[body]["catalogMassKg"] = 5.86
    floor_features = [stock(rect([-137, -84, 41.65], [54, 87, 48]))]
    put(
        floor,
        floor_features,
        "Aluminum 6061",
        "four battery sled mounts",
        "Weld the 6.35 mm floor to the 4 mm side walls along their lower outside corners. Square and tack before final weld.",
    )
    for xlo, hi, which in ((-137, -133.825, "aft"), (50.825, 54, "fore")):
        put(
            which + " battery end stop",
            [stock(rect([xlo, -40, 48], [hi, 43, 95]))],
            "Aluminum 6061",
            floor,
            "3.175 mm end plate bears at the ends of the case, weld both outer corners and bottom to cradle.",
        )
    for y, outer, center, side in ((-44, -44, -50.8, "right"), (43, 47, 53.8, "left")):
        label = "battery cradle wall " + str(y)
        beam = side + " battery well bearer"
        sy = -75 if side == "right" else 78
        put(
            beam,
            tube([-138.3, sy, 109.3], [116.3, sy, 109.3], 19.05, 19.05, 1.5748),
            "Aluminum 6061",
            "rear deck crossmember; front deck crossmember",
            "254.60 mm Online Metals 18011 square tube butt-welded to full-height crossmember faces before upper assembly.",
            "structure",
            "Online Metals 18011 6061-T6 square tube",
        )
        for idx, x in enumerate((-110, 26), 1):
            stem = side + " battery sled mount " + str(idx)
            floor_features.append(drill(round_stock([x, sy, 41], [x, sy, 49], 2.75)))
            put(
                stem,
                [
                    stock(round_stock([x, sy, 48], [x, sy, 99.775], 6.35)),
                    drill(round_stock([x, sy, 47], [x, sy, 63], 2.1)),
                ],
                "Aluminum 6061",
                beam,
                "12.7 mm diameter welded drop post. Tap M5x0.8 from underside, 4.2 mm pilot. Flat lower face seats on sled rim.",
            )
            put(
                stem + " screw",
                [
                    stock(round_stock([x, sy, 40.65], [x, sy, 60.65], 2.5)),
                    add(round_stock([x, sy, 35.65], [x, sy, 40.65], 4.25)),
                    drill(hexagon([x, sy, 35.64], [x, sy, 38.15], 4)),
                ],
                "Steel, Carbon",
                stem,
                "M5x20 socket screw installed from underside through sled flange and flat washer; remove with sled supported on pit cart.",
                "fastener",
                "ISO 4762 M5x20",
            )
            put(
                stem + " washer",
                [stock(round_stock([x, sy, 40.65], [x, sy, 41.65], 5, 2.7))],
                "Steel, Carbon",
                stem,
                "M5 small flat washer under tray flange.",
                "fastener",
                "ISO 7089 M5",
            )
        put(
            label,
            [stock(rect([-137, y, 48], [54, y + 4, 129]))],
            "Aluminum 6061",
            floor,
            "Weld the long wall to sled floor along its exterior bottom edge; it moves with the removable cassette.",
        )
        name = side + " battery hold-down post"
        put(
            name,
            [
                stock(round_stock([-41.5, center, 48], [-41.5, center, 218], 6.35)),
                drill(round_stock([-41.5, center, 204], [-41.5, center, 219], 2.1)),
            ],
            "Aluminum 6061",
            floor,
            "Machine 12.7 mm round stock and tap top M5x0.8 (4.2 mm pilot), weld post to sled floor; tighten against post hard stop.",
        )
        put(
            side + " battery hold-down screw",
            [
                stock(
                    round_stock([-41.5, center, 209.35], [-41.5, center, 225.35], 2.5)
                ),
                add(round_stock([-41.5, center, 225.35], [-41.5, center, 228.1], 4.75)),
                drill(hexagon([-41.5, center, 228.11], [-41.5, center, 226.5], 3)),
            ],
            "Steel, Carbon",
            name,
            "M5x16 button-head screw through washer and nonconductive bar into tapped post. Central location keeps metal away from terminal ends.",
            "fastener",
            "ISO 7380-1 M5x16",
        )
        put(
            side + " battery hold-down washer",
            [
                stock(
                    round_stock(
                        [-41.5, center, 224.35], [-41.5, center, 225.35], 5, 2.7
                    )
                )
            ],
            "Steel, Carbon",
            name,
            "Spreads clamp load over nonconductive bar. Select and verify an M5 washer matching the 10 mm outer diameter and 1 mm thickness.",
            "fastener",
            "ISO 7089 M5",
        )
    f = [stock(rect([-54, -60, 218], [-29, 60.5, 224.35]))]
    for y in (-50.8, 53.8):
        f.append(drill(round_stock([-41.5, y, 217], [-41.5, y, 225], 2.75)))
    put(
        "battery center keeper",
        f,
        "Polycarbonate, Clear",
        "left battery hold-down post; right battery hold-down post",
        "25 mm wide, 6.35 mm polycarbonate bridge at center of pack spans both bolted hard stops. Lower the complete retained and disconnected sled to a supported pit service cart before removing the two keeper screws and washers. Hard stop leaves 3 mm shell travel at nominal size; an insulating conforming pad can be fitted to the actual center lid, separately from protected terminal ends.",
        "guide",
        "6.35 mm polycarbonate sheet",
    )
    # Reproduce and locally relieve the existing two electronics deck blanks for the keeper bar.
    for side, lo, hi in (("right", -251, -44), ("left", 47, 251)):
        deck = side + " electronics deck"
        parts[deck] = article(
            deck,
            "structure",
            "Aluminum 6061",
            [
                stock(rect([-178, lo, 122], [167, hi, 129])),
                drill(rect([-55, max(lo, -61), 121], [-28, min(hi, 64), 130])),
            ],
            parent="rear deck crossmember; front deck crossmember",
            connection="Machine a local 27 mm wide opening for the removable top keeper. The deck requires its own structural retention.",
        )
    return parts
