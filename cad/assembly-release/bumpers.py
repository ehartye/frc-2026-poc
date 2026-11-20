"""Four-corner, five-segment passive bumper. Soft corners remain full depth around the frame corner."""

from shop import article, stock, add, drill, rect, round_stock, hexagon
import numpy as np


def build():
    candidates = [
        ("left blue side bumper", (0, 1), (1, 0), -340, 340, (-231.5, -95, 90, 265)),
        ("right blue side bumper", (0, -1), (1, 0), -340, 340, (-231.5, -95, 90, 265)),
        ("rear blue bumper", (-1, 0), (0, 1), -340, 340, (-150, 0, 150)),
        ("left blue front bumper", (1, 0), (0, 1), 150, 340, (178, 274)),
        ("right blue front bumper", (1, 0), (0, 1), -340, -150, (-274, -178)),
    ]
    added = {}
    revised = {}
    rail_cuts = {}
    bills = []
    for panel, n, t, s0, s1, sites in candidates:
        side = panel.startswith(("left", "right")) and "side" in panel
        anchor_u = -12.7
        rail = (
            panel.split()[0] + " perimeter tube"
            if side
            else "rear perimeter tube"
            if panel.startswith("rear")
            else panel.split()[0] + " front return"
        )

        def pt(u, s, z):
            return [n[0] * (340 + u) + t[0] * s, n[1] * (340 + u) + t[1] * s, z]

        def box(u0, u1, s0, s1, z0, z1):
            vertices = np.array(
                [pt(u, s, z) for u in (u0, u1) for s in (s0, s1) for z in (z0, z1)]
            )
            return rect(vertices.min(0), vertices.max(0))

        def cyl(u0, u1, s, z, r, inner=0):
            return round_stock(pt(u0, s, z), pt(u1, s, z), r, inner)

        back = panel.replace("blue ", "") + " backer"
        foam = panel.replace("blue ", "") + " padding"
        f0 = s0 - 75.5 if side else s0
        f1 = s1 + 75.5 if side else s1
        wood = [stock(box(0, 12, s0, s1, 48.5, 167.5))]
        fill = [stock(box(12, 75.5, f0, f1, 48.5, 167.5))]
        if side:
            fill.append(add(box(0, 12, f0, s0, 48.5, 167.5)))
            fill.append(add(box(0, 12, s1, f1, 48.5, 167.5)))
        fabric = [
            stock(box(75.5, 76, f0, f1, 48, 168)),
            add(box(0, 75.5, f0, f1, 167.5, 168)),
            add(box(0, 75.5, f0, f1, 48, 48.5)),
        ]
        # Soft corner returns on the two side assemblies close the cloth over the two exposed ends.
        if side:
            fabric.append(add(box(0, 76, f0 - 0.5, f0, 48, 168)))
            fabric.append(add(box(0, 76, f1, f1 + 0.5, 48, 168)))
        elif "front" in panel:
            # Only the central loading opening exposes cloth ends on the short returns.
            if s0 == 150:
                fabric.append(add(box(0, 76, s0 - 0.5, s0, 48, 168)))
            else:
                fabric.append(add(box(0, 76, s1, s1 + 0.5, 48, 168)))
        revised[panel] = article(
            panel,
            "bumper-blue",
            "CORDURA 1000D coated nylon 6,6 cloth",
            fabric,
            parent=back,
            connection="Blue 1000D nylon wraps outer/top/bottom and exposed end surfaces. Fold and staple to backer's inward face, flush in relief before mounting. Duplicate the replaceable skin in red for the other alliance.",
            purchase="Rockywoods 1000 Denier Coated CORDURA Nylon Fabric, Royal Blue or Red, 10.8 oz/sq yd, nominal 0.5 mm. The AndyMark kit cloth remains an alternate pending areal mass.",
        )
        revised[panel]["engineeringMaterial"] = {
            "name": "CORDURA 1000D coated nylon 6,6 cloth",
            "base": "Nylon 6/6",
            "densityKgM3": 10.8 * 0.028349523125 / (0.9144**2 * 0.0005),
            "source": "Rockywoods 1000 Denier Coated CORDURA Nylon Fabric; catalog areal mass over nominal 0.5 mm cloth envelope",
        }
        added[foam] = article(
            foam,
            "guide",
            "Ethafoam 220 polyethylene foam",
            fill,
            parent=back,
            connection="Contiguous 63.5 mm solid closed-cell PE face bonded against 119 mm continuous backing; side units have uncompressed 75.5 mm full-depth corner stock. Generic foam appearance is not a density measurement.",
            purchase="Ethafoam 220 polyethylene closed-cell stock cut from 3 inch billet, nominal 37 kg/m3",
        )
        added[foam]["engineeringMaterial"] = {
            "name": "Ethafoam 220 polyethylene foam",
            "base": "Polyethylene, Low Density",
            "densityKgM3": 37,
            "source": "Sealed Air grade 220",
        }
        added[back] = article(
            back,
            "structure",
            "Metsa Wood 12 mm 9-ply birch plywood",
            wood,
            parent=rail,
            connection="12 mm structural birch backer sits at frame face. Recessed M5 fasteners attach machined angles to the removable panel; accessible vertical M6 screws secure the angles to the frame.",
            purchase="Metsa Wood birch plywood, nominal 12 mm, 9 plies. Select panel and verify section height and flatness on receipt.",
        )
        added[back]["engineeringMaterial"] = {
            "name": "Metsa Wood 12 mm 9-ply birch plywood",
            "base": "Plywood, Finish",
            "densityKgM3": 680,
            "source": "Metsa Wood birch plywood data sheet, 680 kg/m3 at 65% relative humidity",
        }
        for i, s in enumerate(sites, 1):
            corner = panel.replace(" blue", "") + " mounting " + str(i)
            bracket = corner + " angle"

            def vc(u, t, z0, z1, r, inner=0):
                return round_stock(pt(u, t, z0), pt(u, t, z1), r, inner)

            # Bar-stock angle machined from a 36 mm long, 25.4 x 31.75 billet. Machine the
            # foot and the vertical mounting face in one setup to keep the pad directly above the tube.
            fl = [
                stock(box(-25.4, 0, s - 18, s + 18, 114.8, 121.15)),
                add(box(-6.35, 0, s - 18, s + 18, 121.15, 146.55)),
                drill(vc(anchor_u, s, 114, 122, 3.3)),
            ]
            added[bracket] = article(
                bracket,
                "structure",
                "Aluminum 6061",
                fl,
                parent=rail,
                connection="6.35 mm L-section seats on rail top. An M6 socket screw clamps the foot into the frame-mounted welded boss; two M5 button screws clamp the wood to the vertical face.",
                purchase="6061-T6511 angle milled from 31.75 mm square stock, Online Metals 1117, cut 36 mm.",
            )
            for side, q in (("a", s - 10), ("b", s + 10)):
                z = 135
                wood.extend(
                    [
                        drill(cyl(-0.1, 12.2, q, z, 2.75)),
                        drill(cyl(7.5, 12.1, q, z, 8.25)),
                    ]
                )
                fl.append(drill(cyl(-6.5, 0.1, q, z, 2.1)))
                added[corner + " " + side + " panel washer"] = article(
                    corner + " " + side + " panel washer",
                    "fastener",
                    "Steel, Carbon",
                    [stock(cyl(7.5, 8.5, q, z, 7.5, 2.65))],
                    parent=back,
                    connection="15 mm large-face washer spreads screw load into plywood. 1.0 mm thickness and countersunk margin to be received.",
                    purchase="M5 15 mm OD x 1 mm wide washer",
                )
                added[corner + " " + side + " panel screw"] = article(
                    corner + " " + side + " panel screw",
                    "fastener",
                    "Steel, Carbon",
                    [
                        stock(cyl(-7.5, 8.5, q, z, 2.5)),
                        add(cyl(8.5, 11.25, q, z, 4.75)),
                        drill(hexagon(pt(11.26, q, z), pt(9.65, q, z), 3)),
                    ],
                    parent=bracket,
                    connection="ISO 7380-1 M5x16 through washer and wood into six-mm tapped aluminum flange. Head remains beneath padding after shop installation.",
                    purchase="ISO 7380-1 M5x16",
                )
            boss = corner + " frame boss"
            added[boss] = article(
                boss,
                "structure",
                "Aluminum 6061",
                [stock(vc(anchor_u, s, 98.8, 114.8, 6.35, 2.5))],
                parent=rail,
                connection="12.70 OD 6061 threaded weld boss, length 16 mm. diameter 5 mm pilot, thread M6x1-6H after welding, face flush with rail.",
            )
            rail_cuts.setdefault(rail, []).append(
                drill(vc(anchor_u, s, 111, 115.5, 6.40))
            )
            screw = corner + " top screw"
            added[screw] = article(
                screw,
                "fastener",
                "Steel, Carbon",
                [
                    stock(vc(anchor_u, s, 101.15, 121.15, 3)),
                    add(vc(anchor_u, s, 121.15, 127.15, 5)),
                    drill(hexagon(pt(anchor_u, s, 127.16), pt(anchor_u, s, 124.15), 5)),
                ],
                parent=boss,
                connection="Standard M6x20 top-access socket screw. Nominal gross threaded length 13.65 mm. Seat on 6.35 mm flange; after removal the bracket and panel travel straight out.",
                purchase="ISO 4762 M6x20 class 8.8",
            )
        bills.append(
            dict(
                panel=panel,
                backerMm=[s1 - s0, 119, 12],
                foamDepthMm=63.5,
                hardExtensionMm=12,
                outerExtensionMm=76,
                cutouts=len(sites),
                installedFrameStationsMm=list(sites),
                topScrewAxisMm=[pt(anchor_u, s, 121.15) for s in sites],
            )
        )
    return revised, added, rail_cuts, bills
