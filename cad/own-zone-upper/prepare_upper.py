"""Upper layout in the native robot frame. Dimensions and trajectories are in millimetres."""

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "own-zone"))
from prepare import box, cylinder, layout, sha


def beam(name, role, start, end, width, height):
    return {
        "name": name,
        "role": role,
        "shape": "beam",
        "start": start,
        "end": end,
        "width": width,
        "height": height,
    }


def parts():
    cfg, stock, proxies, sites = layout()
    add = stock.append
    for y, side in [(-306, "right"), (306, "left")]:
        for x, end in [(-188, "rear"), (176, "front")]:
            add(
                box(
                    f"{end} {side} hopper post",
                    "structure",
                    [x - 10, y - 8, 115],
                    [x + 10, y + 8, 229],
                )
            )
        add(
            beam(
                side + " floor sill", "structure", [-330, y, 227], [150, y, 227], 18, 12
            )
        )
    for x, end in [(-188, "rear"), (176, "front")]:
        add(
            beam(
                end + " deck crossmember",
                "structure",
                [x, -315, 113],
                [x, 315, 113],
                20,
                25,
            )
        )
    for side, y0, y1 in [("left", 47, 251), ("right", -251, -44)]:
        add(
            box(
                side + " electronics deck", "structure", [-178, y0, 122], [167, y1, 129]
            )
        )
    add(
        box("fore electronics deck bridge", "structure", [54, -44, 122], [167, 47, 129])
    )
    add(
        box(
            "aft electronics deck bridge",
            "structure",
            [-178, -44, 122],
            [-137, 47, 129],
        )
    )
    add(box("battery cradle floor", "structure", [-137, -44, 44], [54, 47, 48]))
    for y in (-44, 43):
        add(
            box(
                "battery cradle wall " + str(y),
                "structure",
                [-137, y, 48],
                [54, y + 4, 129],
            )
        )
    # Supplier-independent packaging reserves; the project has not acquired exact
    # supplier CAD for these electrical components.
    add(box("battery secured envelope", "electrical", [-132, -36, 48], [49, 40, 215]))
    add(
        box(
            "distribution enclosure reserve",
            "electrical",
            [55, -80, 129],
            [155, 74, 178],
        )
    )
    add(box("robot controller reserve", "electrical", [-163, 62, 129], [4, 154, 171]))
    add(box("field radio reserve", "electrical", [-153, -155, 129], [-24, -82, 168]))
    for i in range(8):
        x = -150 + (i // 2) * 78
        y = 182 if i % 2 else -226
        add(
            box(
                "drive controller reserve " + str(i + 1),
                "electrical",
                [x, y, 129],
                [x + 59, y + 44, 162],
            )
        )
    # A four-column reservoir leads into a reversible transverse floor and central
    # elevator; the open forward center is the common inlet and outlet.
    add(box("hopper back panel", "structure", [-334, -315, 232], [-330, 315, 552]))
    for s, side in [(-1, "right"), (1, "left")]:
        y = min(311 * s, 315 * s)
        add(box(side + " hopper wall", "guide", [-330, y, 232], [148, y + 4, 552]))
        lo, hi = sorted([87 * s, 311 * s])
        add(box(side + " hopper front wing", "guide", [148, lo, 232], [152, hi, 552]))
        add(
            box(side + " cross feed deck", "mechanism", [-330, lo, 230], [148, hi, 235])
        )
        add(
            box(
                side + " front elevator upright",
                "structure",
                [176, s * 105 - 7, 111],
                [190, s * 105 + 7, 648],
            )
        )
        add(
            box(
                side + " rear elevator upright",
                "structure",
                [312, s * 105 - 7, 113],
                [326, s * 105 + 7, 648],
            )
        )
        add(
            beam(
                side + " elevator upper tie",
                "structure",
                [181, s * 105, 637],
                [319, s * 105, 637],
                14,
                14,
            )
        )
        for x, label in [(196, "inside"), (301, "outside")]:
            add(
                box(
                    f"{side} {label} lift belt",
                    "belt",
                    [x - 3, s * 91 - 5, 86],
                    [x + 3, s * 91 + 5, 621],
                )
            )
        for i, z in enumerate([99, 258, 417, 576], 1):
            add(
                box(
                    f"{side} lift shelf {i}",
                    "mechanism",
                    [196, s * 81 - 9, z],
                    [292, s * 81 + 9, z + 6],
                )
            )
        add(
            beam(
                side + " intake ramp",
                "guide",
                [213, s * 60, 48],
                [337, s * 60, 15],
                28,
                5,
            )
        )
    add(box("rear lift custody gate", "guide", [167, -65, 134], [171, 65, 550]))
    add(box("front lift custody guide", "guide", [327, -65, 221], [331, 65, 582]))
    add(box("central fore-aft feed deck", "belt", [-330, -87, 230], [149, 87, 235]))
    for z, end in [(84, "lower"), (622, "upper")]:
        for side, span in [("left", (88, 116)), ("right", (-116, -88))]:
            add(
                cylinder(
                    side + " " + end + " lift stub shaft",
                    "shaft",
                    [248, span[0], z],
                    [248, span[1], z],
                    7.5,
                )
            )
    pivot = [275, 240]
    stow = [
        pivot[0] + 103 * math.cos(math.radians(84)),
        pivot[1] + 103 * math.sin(math.radians(84)),
    ]
    add(
        cylinder(
            "ground intake roller",
            "mechanism",
            [stow[0], -126, stow[1]],
            [stow[0], 126, stow[1]],
            38,
        )
    )
    for y, side in [(-150, "right"), (150, "left")]:
        add(
            beam(
                side + " intake bearing arm",
                "structure",
                [pivot[0], y, pivot[1]],
                [stow[0], y, stow[1]],
                12,
                15,
            )
        )
        add(
            beam(
                side + " intake pivot plate",
                "structure",
                [315, y, 247],
                [pivot[0], y, pivot[1]],
                12,
                22,
            )
        )
        yr = sorted([y, float(1 if y > 0 else -1) * 100])
        add(
            cylinder(
                side + " intake pivot axle",
                "shaft",
                [pivot[0], yr[0], pivot[1]],
                [pivot[0], yr[1], pivot[1]],
                6,
            )
        )
        journal = sorted([y, 126 if y > 0 else -126])
        add(
            cylinder(
                side + " intake journal",
                "shaft",
                [stow[0], journal[0], stow[1]],
                [stow[0], journal[1], stow[1]],
                7,
            )
        )
        add(
            box(
                side + " upper head cheek",
                "structure",
                [151, y - 4, 562],
                [321, y + 4, 706],
            )
        )
    # Both roller axes are perpendicular to travel and lateral contact.
    angle = math.radians(60)
    normal = (-math.sin(angle), math.cos(angle))
    for sign, side in [(-1, "right"), (1, "left")]:

        def axis(s):
            return [238 + s * normal[0], sign * 104, 601 + s * normal[1]]

        add(cylinder(side + " scoring wheel", "mechanism", axis(-25), axis(25), 32))
        add(cylinder(side + " scoring spindle", "shaft", axis(-36), axis(36), 6))
        add(
            beam(
                side + " upper guide",
                "guide",
                [190, sign * 80, 548],
                [300, sign * 80, 719],
                6,
                10,
            )
        )
        for pos in [-33, 33]:
            q = axis(pos)
            add(
                beam(
                    side + " scoring bearing bridge " + str(pos),
                    "structure",
                    [q[0], min(sign * 104, sign * 146), q[2]],
                    [q[0], max(sign * 104, sign * 146), q[2]],
                    15,
                    10,
                )
            )
    for side, span in [("left", (76, 100)), ("right", (-100, -76))]:
        add(
            cylinder(
                side + " feed diverter pivot",
                "shaft",
                [156, span[0], 548],
                [156, span[1], 548],
                7,
            )
        )
    add(box("feed diverter vane", "mechanism", [154, -75, 548], [158, 75, 594]))
    for s, side in [(-1, "right"), (1, "left")]:
        center = [238, 104 * s, 601]
        start = [center[0] + 28 * normal[0], center[1], center[2] + 28 * normal[1]]
        end = [start[0] + 93.26 * normal[0], start[1], start[2] + 93.26 * normal[1]]
        proxies.append(
            cylinder(side + " public scoring motor envelope", "drive", start, end, 30)
        )
    return cfg, stock, proxies, sites


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plugin", type=Path)
    parser.add_argument("supplier_step", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    cfg, stock, proxies, sites = parts()
    if sha(args.supplier_step) != cfg["swerve"]["sha256"]:
        raise ValueError("Unexpected module source")
    sys.path.insert(0, str(args.plugin.resolve() / "scripts"))
    from component_palette import resolve_palette

    palette = resolve_palette(ROOT)
    if any(s["role"] not in palette for s in stock + proxies):
        raise ValueError("Missing palette role")
    args.output.mkdir(exist_ok=True, parents=True)
    vendor = args.supplier_step.resolve().parent / "REV-21-1650-extracted.step"
    if not vendor.is_file():
        raise ValueError(
            "Provide the privately extracted and verified REV-21-1650 STEP"
        )
    motors = []
    a = math.radians(60)
    n = [-math.sin(a), 0, math.cos(a)]
    basis = [[0, n[0], n[2]], [1, 0, 0], [0, n[2], -n[0]]]
    for sign, side in [(-1, "right"), (1, "left")]:
        motors.append(
            {
                "name": side + " scoring motor",
                "rotation": basis,
                "translation": [
                    238 + (28 - 40.1) * n[0],
                    sign * 104,
                    601 + (28 - 40.1) * n[2],
                ],
            }
        )
    job = {
        "title": "REBUILT own-zone R2",
        "items": stock,
        "proxies": proxies,
        "sites": sites,
        "palette": palette,
        "layout": cfg,
        "supplier": str(args.supplier_step.resolve()),
        "output": str(args.output.resolve()),
        "extraSources": [
            {
                "file": str(vendor),
                "sha256": sha(vendor),
                "source": "REV-21-1650",
                "placements": motors,
            }
        ],
    }
    (args.output / "native-job.json").write_text(
        json.dumps(job, indent=2) + "\n", encoding="utf8"
    )
    print(len(stock), "project parts;", len(proxies), "public supplier representations")


if __name__ == "__main__":
    main()
