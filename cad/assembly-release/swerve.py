"""Derive the four rail saddles from this robot's eight measured tab seats and stock faces."""

import sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "own-zone"))
from prepare import layout as prior_layout
from shop import article, rect, round_stock, hexagon, stock, add, drill

AL = "Aluminum 6061"
CARBON = "Steel, Carbon"
STEEL = "Steel, Mild"


def layout():
    cfg, items, proxies, sites = prior_layout()
    cfg = dict(cfg, wheelAxisFromRobotCenterMm=[265.0, 265.0])
    for site in sites:
        x, y, z = site["translation"]
        site["translation"] = [float(np.sign(x) * 265), float(np.sign(y) * 265), z]
    return cfg, items, proxies, sites


def build():
    cfg, prior, _, sites = layout()
    replaced = {}
    added = {}
    rail_ops = {}
    stacks = []
    for site in sites:
        site_name = site["name"]
        rot = np.array(site["rotation"])
        origin = np.array(site["translation"])
        for index in range(2):

            def world(u, h, v):
                return (
                    (rot @ np.array((u, h, v) if index == 0 else (v, h, u)) + origin)
                    .round(6)
                    .tolist()
                )

            def box(u0, u1, h0, h1, v0, v1):
                corners = np.array(
                    [
                        world(u, h, v)
                        for u in (u0, u1)
                        for h in (h0, h1)
                        for v in (v0, v1)
                    ]
                )
                return rect(corners.min(0), corners.max(0))

            def cyl(u0, h0, v0, u1, h1, v1, r, inner=0):
                return round_stock(world(u0, h0, v0), world(u1, h1, v1), r, inner)

            tag = site_name + " module tab spacer " + str(index + 1)
            rail_axis = np.subtract(world(1, 0, 0), world(0, 0, 0))
            along_x = abs(rail_axis[0]) > 0.5
            if along_x:
                rail = (
                    "rear perimeter tube"
                    if site_name.startswith("rear")
                    else site_name.split()[-1] + " front return"
                )
            else:
                rail = site_name.split()[-1] + " perimeter tube"
            inner_face = -(
                cfg["frameOutsideMm"] / 2
                - cfg["railWidthMm"]
                - cfg["wheelAxisFromRobotCenterMm"][0]
            )
            # Both supplier tab seats are 50.8 apart. The vertical saddle is fitted to
            # them without pulling the plates together. Integral through holes follow each finite 5 mm throat.
            ops = [stock(box(inner_face, -23.5, 31.75, 82.55, 52, 87.7))]
            for v in (57.15, 82.55):
                ops.append(drill(cyl(-31.75, 30, v, -31.75, 84, v, 2.65)))
            for h in (46, 67):
                ops.append(drill(cyl(inner_face - 1, h, 69.85, -22.5, h, 69.85, 3.25)))
            for v in (57.8, 81.9):
                ops.append(drill(cyl(inner_face - 1, 57.15, v, -22.5, 57.15, v, 5.35)))
            replaced[tag] = article(
                tag,
                "structure",
                AL,
                ops,
                parent=rail,
                connection="Clamped against the rail by two socket screws into welded threaded bosses.",
            )
            for k, h in enumerate((46, 67), 1):
                prefix = site_name + " rail mount " + str(index + 1) + "-" + str(k)
                boss = prefix + " weld boss"
                bolt = prefix + " M6 cap screw"
                # 16 mm deep blind-side boss is flange welded to the aluminum rail inner wall.
                weld_end = inner_face - 16
                rail_ops.setdefault(rail, []).append(
                    drill(
                        cyl(inner_face - 3.5, h, 69.85, inner_face + 1, h, 69.85, 6.55)
                    )
                )
                added[boss] = article(
                    boss,
                    "structure",
                    AL,
                    [stock(cyl(weld_end, h, 69.85, inner_face, h, 69.85, 6.5, 2.50))],
                    parent=rail,
                    connection="Circumferential plug boss weld to one rail wall. M6x1 threaded after welding, 5.00 mm through tap drill; finish M6x1-6H. Thread flank geometry is suppressed.",
                )
                added[bolt] = article(
                    bolt,
                    "fastener",
                    CARBON,
                    [
                        stock(cyl(-23.5 - 40, h, 69.85, -23.5, h, 69.85, 3)),
                        add(cyl(-23.5, h, 69.85, -17.5, h, 69.85, 5)),
                        drill(
                            hexagon(world(-17.49, h, 69.85), world(-20.5, h, 69.85), 5)
                        ),
                    ],
                    parent=boss,
                    connection="ISO 4762 M6x40. Head bears on inboard saddle face, threads engage rail boss.",
                    purchase="pgb-Europe 20659, ISO 4762 M6x1x40 class 8.8",
                )
            for k, v in enumerate((57.15, 82.55), 1):
                prefix = site_name + " tab " + str(index + 1) + "-" + str(k)
                screw = prefix + " socket screw"
                nut = prefix + " locknut"
                length = 69.85
                seat = 27.46375
                top = 86.2125
                nut_h = 6.3246
                added[screw] = article(
                    screw,
                    "fastener",
                    CARBON,
                    [
                        stock(cyl(-31.75, seat, v, -31.75, seat + length, v, 2.413)),
                        add(cyl(-31.75, seat - 4.826, v, -31.75, seat, v, 3.9624)),
                        drill(
                            hexagon(
                                world(-31.75, seat - 4.836, v),
                                world(-31.75, seat - 2.54, v),
                                3.96875,
                            )
                        ),
                    ],
                    parent=tag,
                    connection="Head bears against lower module tab, shank crosses both finite bores and saddle.",
                    purchase="Bolt Depot 8232, ASTM A574 socket cap #10-32 x 2-3/4 in",
                )
                added[nut] = article(
                    nut,
                    "fastener",
                    CARBON,
                    [
                        stock(
                            hexagon(
                                world(-31.75, top, v),
                                world(-31.75, top + nut_h, v),
                                9.5504,
                                2.43,
                            )
                        )
                    ],
                    parent=screw,
                    connection="Nylon insert locknut bears on upper mounting tab.",
                    purchase="Bolt Depot 2623, #10-32 zinc steel nylon insert locknut",
                )
                stacks.append(
                    dict(
                        site=site_name,
                        saddle=tag,
                        rail=rail,
                        axisLower=world(-31.75, seat, v),
                        axisUpper=world(-31.75, top, v),
                        lowerSeatZMm=seat + origin[2],
                        upperSeatZMm=top + origin[2],
                        tabThroatMm=5.0,
                        saddleThroughMm=5.30,
                        clearStackMm=round(top - seat, 4),
                        boltLengthMm=length,
                        lockNutHeightMm=nut_h,
                        tipPastNutMm=round(length - (top - seat) - nut_h, 4),
                        railBossThreadMm=round(40 - (abs(inner_face) - 23.5), 4),
                    )
                )
    return replaced, added, rail_ops, stacks
