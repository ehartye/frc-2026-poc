"""Original public article representations, constrained by the registered supplier interfaces.

The exact private assembly supplies collision and service evidence. These independently shaped solids
expose student azimuth and wheel axes and the tab seats without publishing supplier CAD.
"""

import numpy as np

from shop import add, article, drill, rect, round_stock, stock
from swerve import layout


def build():
    revised = {}
    _, _, _, sites = layout()
    for site in sites:
        name = site["name"]
        rot = np.asarray(site["rotation"])
        center = np.asarray(site["translation"])

        def pt(x, y, z):
            return (rot @ np.asarray([x, y, z]) + center).tolist()

        def cylinder(a, b, r, inside=0):
            return round_stock(pt(*a), pt(*b), r, inside)

        def box(lo, hi):
            pts = np.array(
                [
                    pt(x, y, z)
                    for x in (lo[0], hi[0])
                    for y in (lo[1], hi[1])
                    for z in (lo[2], hi[2])
                ]
            )
            return rect(pts.min(0), pts.max(0))

        housing = name + " public drive housing"
        wheel = name + " public wheel"
        motor = name + " public motor reserve"
        azimuth = name + " public turning fork"
        axle = name + " public wheel axle"
        parent = name + " module tab spacer 1; " + name + " module tab spacer 2"
        fab = [
            "A simplified public view of the selected REV-21-3005 assembly. Generic native material is for illustration.",
        ]

        def part(label, role, material, features, parent, method, stage):
            row = article(
                label,
                role,
                material,
                features,
                parent=parent,
                connection=method,
                stage=stage,
                source=fab[0],
                purchase="REV-21-3005 installed assembly with selected drive and steering motors",
            )
            row["instance"] = "MAXSwerve " + name
            revised[label] = row

        # Annular azimuth collar and a single wall joining the two first-party mounting feet.
        pieces = [
            stock(cylinder([0, 35, 0], [0, 83, 0], 30, 20)),
            add(box([12, 30, 12], [26, 83, 26])),
        ]
        for bottom, top in ((27.46375, 31.75), (82.55, 86.2125)):
            pieces.extend(
                [
                    add(box([-36, bottom, 19], [25, top, 26])),
                    add(box([-37, bottom, 22], [-26, top, 87.7])),
                    add(box([19, bottom, -36], [26, top, 25])),
                    add(box([22, bottom, -37], [87.7, top, -26])),
                ]
            )
            for x, z in (
                (-31.75, 57.15),
                (-31.75, 82.55),
                (57.15, -31.75),
                (82.55, -31.75),
            ):
                pieces.append(
                    drill(cylinder([x, bottom - 0.01, z], [x, top + 0.01, z], 2.5))
                )
        part(
            housing,
            "drive",
            "Aluminum 6061",
            pieces,
            parent,
            "Article represented by original paired feet around its four measured finite mounting stations.",
            "fixed",
        )
        part(
            motor,
            "drive",
            "Aluminum 6061",
            [stock(cylinder([16, 83, 16], [16, 133.36, 16], 19))],
            housing,
            "Motor reserve belongs to the package; no additional purchased mass.",
            "fixed",
        )
        # Fork pivot sleeve OD40 fits the housing collar. Lower thrust shoulder establishes axial support.
        pieces = [
            stock(cylinder([0, 30, 0], [0, 53, 0], 19.95)),
            add(cylinder([0, 30, 0], [0, 35, 0], 25.5)),
        ]
        for sx in (-1, 1):
            x0, x1 = sorted([sx * 14, sx * 21])
            pieces.append(add(box([x0, -5, -7], [x1, 34, 7])))
        pieces.append(drill(cylinder([-22, 0, 0], [22, 0, 0], 5)))
        part(
            azimuth,
            "drive",
            "Aluminum 6061",
            pieces,
            housing,
            "Public steering sleeve turns around supplier vertical axis in housing.",
            "azimuth",
        )
        part(
            axle,
            "shaft",
            "Steel, Carbon",
            [stock(cylinder([-21, 0, 0], [21, 0, 0], 5))],
            azimuth,
            "Package axle follows the fork and spans its two support cheeks.",
            "azimuth",
        )
        part(
            wheel,
            "wheel",
            "Rubber, Black",
            [stock(cylinder([-13, 0, 0], [13, 0, 0], 38.1, 5.0))],
            axle,
            "Public wheel spins around the registered +X supplier axis on its axle.",
            "wheel",
        )
    return revised
