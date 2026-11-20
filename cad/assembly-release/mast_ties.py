"""Four full-height tower ties with upper and lower locating pilots. All dimensions are project mm."""

from shop import add, article, contour, drill, hexagon, rect, round_stock, stock


def build(wall_mm=3.0):
    parts, cuts, tools, seats = {}, {}, {}, []

    def put(n, role, mat, fs, parent, method, sku):
        parts[n] = article(
            n, role, mat, fs, parent=parent, connection=method, purchase=sku
        )

    for side, y in (("left", 326), ("right", -326)):
        rail = side + " perimeter tube"
        beam = side + " upper bearing plate"
        cuts[rail] = []
        cuts[beam] = []
        for suffix, x in ((" mast", -180), (" aft mast", -280)):
            mast = side + suffix
            inner = 10 - wall_mm
            put(
                mast,
                "structure",
                "EN AW-6060 T66 mast tube",
                [
                    stock(rect([x - 10, y - 10, 114.8], [x + 10, y + 10, 744])),
                    drill(
                        rect(
                            [x - inner, y - inner, 114.7], [x + inner, y + inner, 744.1]
                        )
                    ),
                ],
                rail,
                "Full mast appears at its original outer dimensions. Face the two ends square and gauge wall, flatness, corner radii and finished inside span before matching the removable keys.",
                "AMCO 3170300001, 20 x 20 x 3 mm EN AW-6060 T66, stock length 6 m",
            )
            parts[mast]["engineeringMaterial"] = {
                "name": "EN AW-6060 T66 mast tube",
                "base": "Aluminum 6061",
                "densityKgM3": 2700,
                "source": "AMCO 3170300001, temper T66, engineering density cross-checked against catalog length and mass",
            }

            def cyl(z0, z1, r, inner=0):
                return round_stock([x, y, z0], [x, y, z1], r, inner)

            def octagon(z, h, allowance=-0.10, bore=0):
                a, k = inner + allowance, 2.25
                pts = [
                    (-a, -a + k),
                    (-a + k, -a),
                    (a - k, -a),
                    (a, -a + k),
                    (a, a - k),
                    (a - k, a),
                    (-a + k, a),
                    (-a, a - k),
                ]
                return contour(
                    [[x + u, y + v, z] for u, v in pts],
                    [0, 0, h],
                    [{"center": [x, y, z], "r": bore}] if bore else [],
                )

            tie = mast + " full length M8 tie"
            lower = mast + " lower rail key"
            upper = mast + " upper plate key"
            crush = mast + " lower rail crush sleeve"
            bottom = mast + " bottom locking washer"
            bottom_nut = mast + " bottom tie nut"
            # The keys position the tube and transmit shear through four flats and a
            # cylindrical pilot. The axial tension tie passes straight through their bores.
            cuts[rail].extend([drill(cyl(111, 115, 6.45)), drill(cyl(63.5, 67.5, 4.5))])
            cuts[beam].append(drill(octagon(743.7, 6.6, allowance=0.05)))
            put(
                lower,
                "structure",
                "Aluminum 6061",
                [
                    stock(octagon(114.8, 26, bore=4.30)),
                    add(cyl(110.8, 114.8, 6.30, 4.30)),
                ],
                mast,
                "Gauge and seat integral cylindrical pilot in rail; slide the mast over the relieved flats before installing the tie.",
                "6061-T6 solid stock",
            )
            put(
                upper,
                "structure",
                "Aluminum 6061",
                [
                    stock(octagon(718, 32)),
                    add(cyl(750, 754, 9.5)),
                    drill(cyl(717.9, 750.75, 3.4)),
                ],
                beam,
                "Insert relieved flats through the keyed plate into the mast from above. Face the 4 mm flange square and turn its diameter to 19 mm. Drill a diameter 6.80 tap pilot to the registered depth, bottom-tap M8 x 1.25 and gauge at least 27 mm of usable thread. No stack above the flange.",
                "6061-T6 solid round bar, minimum blank diameter 20 mm",
            )
            put(
                crush,
                "structure",
                "Aluminum 6061",
                [stock(cyl(67.175, 110.8, 6.35, 4.30))],
                rail,
                "Match sleeve to measured rail inside face and lower key. No end clearance under tie preload.",
                "6061-T6 12.7 mm rod, bore 8.60 mm",
            )
            put(
                tie,
                "fastener",
                "Steel, Carbon",
                [stock(cyl(51, 745, 4))],
                rail,
                "Cut to 694 mm, finish threads and install 27 mm into the captive tapped head. Set from below before installing the lower washer and nut. Keep 2.50 mm of stud below the lower nut. Verify assembly preload against the structural study.",
                "Wurth 0959 008 DIN 976-1 A M8x1000 class 8.8 right-hand rod",
            )
            put(
                bottom,
                "fastener",
                "Steel, Carbon",
                [stock(cyl(61.5, 64, 8.30, 4.35))],
                rail,
                "Registered NL8sp locking pair below the rail.",
                "Nord-Lock NL8sp M8 wide wedge-lock pair",
            )
            put(
                bottom_nut,
                "fastener",
                "Steel, Carbon",
                [stock(hexagon([x, y, 53.5], [x, y, 61.5], 13, 4.05))],
                tie,
                "Inspect usable thread through the prevailing-torque insert and check received nut height.",
                "DIN 985 M8 property class 8 low locking nut",
            )
            tools[mast + " head insertion above plate"] = cyl(754.01, 794, 9.5)
            tools[mast + " lower socket"] = cyl(25, 61.49, 9.75, 7.55)
            tools[mast + " rod insertion before head"] = cyl(754.01, 1448.1, 4.1)
            seats.extend(
                [
                    (upper, beam, [0, 0, -1]),
                    (bottom_nut, bottom, [0, 0, 1]),
                    (bottom, rail, [0, 0, 1]),
                    (crush, rail, [0, 0, -1]),
                    (lower, crush, [0, 0, -1]),
                    (mast, rail, [0, 0, -1]),
                    (beam, mast, [0, 0, -1]),
                ]
            )
    return parts, cuts, tools, seats
