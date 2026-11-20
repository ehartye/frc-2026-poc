"""Proposed through-rail draw screws and cross-bolted mast spigots. Project millimetres."""

from shop import add, article, contour, drill, hexagon, rect, round_stock, stock


def build(sleeved=True, spigot_flats=15.80):
    parts, append, tools, seats = {}, {}, {}, []
    for side, y in (("left", 326), ("right", -326)):
        rail = side + " perimeter tube"
        append[rail] = []
        for name, x in ((side + " mast", -180), (side + " aft mast", -280)):
            axis_sign = -1 if name.endswith("aft mast") else 1
            plug = name + " anchor spigot"
            sleeve = name + " through-rail sleeve"
            longitudinal = name + " draw screw"
            lock = name + " draw locking washer pair"

            def vertical(low, high, r, inner=0):
                return round_stock([x, y, low], [x, y, high], r, inner)

            def transverse(start, end, z, r, inner=0):
                return round_stock(
                    [x + axis_sign * start, y, z], [x + axis_sign * end, y, z], r, inner
                )

            def define(n, features, parent, connection, material, sku, role):
                parts[n] = article(
                    n,
                    role,
                    material,
                    features,
                    parent=parent,
                    connection=connection,
                    purchase=sku,
                )

            append[name] = []
            # Install the sleeve through the top clearance, onto the intact lower wall.
            # The top and bottom holes intentionally have different diameters.
            append[rail] += [
                drill(vertical(111, 115, 6.45)),
                drill(vertical(63.5, 67.5, 4.50)),
            ]
            define(
                sleeve,
                [stock(vertical(67.175, 110.8, 6.35, 4.30))],
                rail,
                "Machine ends square. Match the compressible stack from the bottom inside face to the spigot pilot underside.",
                "Aluminum 6061",
                "6061-T6 12.7 mm round, bored 8.60 mm",
                "structure",
            )
            a, relief = spigot_flats / 2, 2.25
            outline = [
                (-a, -a + relief),
                (-a + relief, -a),
                (a - relief, -a),
                (a, -a + relief),
                (a, a - relief),
                (a - relief, a),
                (-a + relief, a),
                (-a, a - relief),
            ]
            body = [
                stock(contour([[x + u, y + v, 114.8] for u, v in outline], [0, 0, 76])),
                add(vertical(110.8, 114.8, 6.30)),
                drill(vertical(110.7, 137.3, 3.40)),
            ]
            for j, z in enumerate((153.8, 174.8), 1):
                cross = name + f" cross fastener {j}"
                bore_radius = 6.29 if sleeved else 4.25
                append[name].append(drill(transverse(-10.2, 10.2, z, bore_radius)))
                body.append(drill(transverse(-8.1, 8.1, z, bore_radius)))
                if sleeved:
                    pin = cross + " fitted sleeve"
                    define(
                        pin,
                        [stock(transverse(-9.99, 9.99, z, 6.275, 4.25))],
                        plug,
                        "Match-ream both walls and the installed spigot. A full-span 12.55 OD by 8.50 ID sleeve bears the vertical load directly. Each external washer retains it axially; the M8 bolt closes the stack.",
                        "Aluminum 6061",
                        "6061-T6 12.7 mm round bar, turned to fit",
                        "structure",
                    )

                for suffix, start, end in (
                    ("head washer", -11.6, -10),
                    ("nut washer", 10, 11.6),
                ):
                    define(
                        cross + " " + suffix,
                        [stock(transverse(start, end, z, 8, 4.20))],
                        name,
                        "Deburred M8 plain bearing washer against the external mast face.",
                        "Steel, Carbon",
                        "ISO 7089 M8 plain washer",
                        "fastener",
                    )
                define(
                    cross + " screw",
                    [
                        stock(transverse(-11.6, 28.4, z, 4)),
                        add(transverse(-19.6, -11.6, z, 6.5)),
                        drill(
                            hexagon(
                                [x + axis_sign * (-19.7), y, z],
                                [x + axis_sign * (-15.6), y, z],
                                6,
                            )
                        ),
                    ],
                    plug,
                    "Through both mast walls, close-fitting insert and both washers. Capture with the M8 locknut.",
                    "Steel, Carbon",
                    "Accu SSC-M8-40-12.9 DIN 912",
                    "fastener",
                )
                define(
                    cross + " locknut",
                    [
                        stock(
                            hexagon(
                                [x + axis_sign * (+11.6), y, z],
                                [x + axis_sign * (+19.6), y, z],
                                13,
                                4.05,
                            )
                        )
                    ],
                    cross + " screw",
                    "M8 nylon insert locknut. Verify insert engagement, clamp seating, thread runout and replacement interval.",
                    "Steel, Carbon",
                    "DIN 985 M8 low nylon-insert nut, 13 mm AF",
                    "fastener",
                )
                tools[cross + " screw withdrawal"] = transverse(-62, -19.6, z, 6.7)
                tools[cross + " driver"] = transverse(-60, -19.6, z, 3.65)
                tools[cross + " nut socket"] = transverse(19.62, 60, z, 9.5, 4.25)
                seats.extend(
                    [
                        (name, cross + " head washer", [-axis_sign, 0, 0]),
                        (name, cross + " nut washer", [axis_sign, 0, 0]),
                    ]
                )
            define(
                plug,
                body,
                name,
                "Machine the eight flats to the measured minimum tube bore less 0.20 mm; preserve the 2.25 mm corner relief. Tap bottom M8x1.25. Fixture on the rail pilot and match-ream mast and spigot for the fitted cross sleeves.",
                "Aluminum 6061",
                "6061-T6 spigot milled from solid stock",
                "structure",
            )
            define(
                lock,
                [stock(vertical(61.5, 64, 8.30, 4.35))],
                rail,
                "Wedge-lock pair directly under bolt head on the prepared rail. Inspect supported teeth and seating.",
                "Steel, Carbon",
                "Nord-Lock NL8sp, assembled pair",
                "fastener",
            )
            define(
                longitudinal,
                [
                    stock(vertical(61.5, 131.5, 4)),
                    add(vertical(53.5, 61.5, 6.5)),
                    drill(hexagon([x, y, 53.4], [x, y, 57.6], 6)),
                ],
                plug,
                "M8x70 underhead, 20.7 mm gross thread engagement, 18.2 mm after two pitches; positive tension path through the lower rail face. The integral 12.6 mm pilot enters the rail crown for positive horizontal bearing.",
                "Steel, Carbon",
                "Accu SSC-M8-70-12.9",
                "fastener",
            )
            tools[longitudinal + " withdrawal"] = vertical(-19, 53.5, 6.7)
            tools[longitudinal + " driver"] = vertical(-23, 53.5, 3.65)
            seats.extend(
                [
                    (lock, rail, [0, 0, 1]),
                    (longitudinal, lock, [0, 0, 1]),
                    (sleeve, rail, [0, 0, -1]),
                    (plug, sleeve, [0, 0, -1]),
                ]
            )
    return parts, append, tools, seats
