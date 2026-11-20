"""Project-owned R2C rear, single-upright, two-hook L1 design. All geometry is in millimetres."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def parts():
    items = []

    def add(name, stage, role, shape, **params):
        items.append(dict(name=name, stage=stage, role=role, shape=shape, **params))

    def block(name, stage, role, a, b):
        add(name, stage, role, "box", lower=a, upper=b)

    def tube(name, stage, role, start, end, width, height, wall):
        add(
            name,
            stage,
            role,
            "tube",
            start=start,
            end=end,
            width=width,
            height=height,
            wall=wall,
        )

    def cylinder(name, stage, role, start, end, radius):
        add(name, stage, role, "cylinder", start=start, end=end, radius=radius)

    for side, s in (("left", 1), ("right", -1)):
        outer = 326 * s
        tube(
            side + " mast",
            "fixed",
            "structure",
            [-180, outer, 114.8],
            [-180, outer, 744],
            20,
            20,
            2,
        )
        # A second attached post resists the fore-aft cantilever moment.
        tube(
            side + " aft mast",
            "fixed",
            "structure",
            [-280, outer, 114.8],
            [-280, outer, 744],
            20,
            20,
            2,
        )
        block(
            side + " upper bearing plate",
            "fixed",
            "guide",
            [-294, min(s * 336, s * 298), 744],
            [-166, max(s * 336, s * 298), 750],
        )
        block(
            side + " lower bearing plate",
            "fixed",
            "guide",
            [-267, min(s * 335, s * 292), 551],
            [-213, max(s * 335, s * 292), 557],
        )
        cylinder(
            side + " lead screw envelope",
            "fixed",
            "shaft",
            [-240, s * 305, 557],
            [-240, s * 305, 744],
            5,
        )
        # The NEO envelope is below the rear bridge, clear of the upper cargo roof.
        cylinder(
            side + " lift motor envelope",
            "fixed",
            "drive",
            [-240, s * 258, 577],
            [-240, s * 258, 638],
            30,
        )
        block(
            side + " reduction envelope",
            "fixed",
            "drive",
            [-259, min(s * 248, s * 312), 557],
            [-221, max(s * 248, s * 312), 577],
        )
        block(
            side + " driven nut",
            "elevator",
            "mechanism",
            [-249, min(s * 315, s * 296), 711],
            [-231, max(s * 315, s * 296), 725],
        )
        block(
            side + " nut link",
            "elevator",
            "mechanism",
            [-248, min(s * 314, s * 298), 701],
            [-232, max(s * 314, s * 298), 711],
        )
        # Nut and outer guide attach to the bridge upper crossmember through this plate.
        block(
            side + " crosshead cheek",
            "elevator",
            "mechanism",
            [-292, min(s * 315, s * 292), 687],
            [-117, max(s * 315, s * 292), 701],
        )
        # Clearance through both mounting plates; the captive nut uses a nominal thread bore.
        for item in items[-3:]:
            item["holes"] = [
                [-240, s * 305, 5.0 if item["name"].endswith("driven nut") else 5.8]
            ]
        for x, n in ((-180, "forward"), (-280, "aft")):
            tube(
                side + " " + n + " carriage sleeve",
                "elevator",
                "guide",
                [x, outer, 682],
                [x, outer, 722],
                26,
                25,
                2,
            )
        y = s * 72
        tube(
            side + " extension sleeve",
            "elevator",
            "guide",
            [-173, y, 739],
            [-86, y, 739],
            28,
            30,
            2,
        )
        block(
            side + " sleeve pedestal",
            "elevator",
            "mechanism",
            [-164, min(y - 11, y + 11), 701],
            [-142, max(y - 11, y + 11), 724],
        )
        tube(
            side + " extending rail",
            "hooks",
            "structure",
            [-220, y, 739],
            [175, y, 739],
            20,
            22,
            2,
        )
        # Single cut hook in a native sketch. Two plate faces closely flank the rails.
        add(
            side + " crown hook",
            "hooks",
            "guide",
            "hook",
            y=min(s * 82, s * 94),
            thickness=12,
            profile=[
                [-283, 710],
                [-271, 710],
                [-271, 737],
                [-223, 737],
                [-223, 710],
                [-211, 710],
                [-211, 736],
                [-176, 736],
                [-176, 753],
                [-283, 753],
            ],
        )
    tube(
        "crosshead lift bridge",
        "elevator",
        "structure",
        [-151, -315, 691],
        [-151, 315, 691],
        20,
        20,
        2,
    )
    block(
        "rail synchronizing tie", "hooks", "mechanism", [153, -82, 750], [173, 82, 754]
    )
    # A carriage-mounted, 4 mm lead screw deploys the guide rails. The travelling nut
    # seats against the rear bearing block; the bearing beam carries that axial reaction.
    block(
        "extension bearing beam",
        "elevator",
        "structure",
        [-161, -14, 701],
        [225, 14, 716],
    )

    def bored(name, stage, x0, x1, width, height, radius):
        add(
            name,
            stage,
            "guide",
            "axial-block",
            start=[x0, 0, 733],
            end=[x1, 0, 733],
            width=width,
            height=height,
            holes=[[x0, 0, radius]],
        )

    bored("extension rear bearing and stop", "elevator", -74, -62, 28, 34, 5.2)
    bored("extension forward bearing", "elevator", 193, 205, 28, 34, 5.2)
    cylinder(
        "extension screw envelope", "elevator", "shaft", [-74, 0, 733], [205, 0, 733], 5
    )
    bored("extension deployment nut", "hooks", 153, 173, 20, 26, 5)
    block("extension nut hanger", "hooks", "mechanism", [153, -8, 746], [173, 8, 750])
    cylinder(
        "extension motor envelope",
        "elevator",
        "drive",
        [205, 0, 733],
        [254, 0, 733],
        18,
    )
    block(
        "extension motor foot", "elevator", "structure", [207, -9, 716], [223, 9, 718]
    )
    return items


if __name__ == "__main__":
    (HERE / "parts.json").write_text(
        json.dumps(parts(), indent=2) + "\n", encoding="utf-8", newline="\n"
    )
