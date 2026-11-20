"""Gauge a detachable rear-facing bit ratchet throughout its side entry and operation."""

import argparse
import json
from pathlib import Path

from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from drivetrain_fit import vol, broad
from offline import shape, machine
from passive_job import recipe
from shop import rect, round_stock
from supplier import bounds
from verify_products import products


def run():
    plan = recipe()
    world = products(Path(__file__).resolve().parents[2] / plan["stepBase"])
    world.update({k: machine(row["features"]) for k, row in plan["parts"].items()})
    fixed = {k: (s, bounds(s)) for k, s in world.items()}

    def check(s, skip):
        bb = bounds(s)
        return {
            k: round(v, 4)
            for k, (obs, ob) in fixed.items()
            if k != skip
            and broad(bb, ob)
            and (v := vol(BRepAlgoAPI_Common(s, obs).Shape())) > 0.025
        }

    report = {}
    panel = next(p for p in plan["panels"] if p["panel"] == "rear blue bumper")
    for i, (x, y, z) in enumerate(panel["topScrewAxisMm"], 1):
        # The head projects 12 mm behind the stud; the 87 mm handle points forward into the bay.
        # 24-mm max width + 10 mm extra on each side encloses the entire 6° ratchet sector.
        skip = f"rear bumper mounting {i} top screw"

        def hull(x0, x1, y0, y1, z0, z1):
            return shape(rect([x0, y0, z0], [x1, y1, z1]))

        # Insert the loose bit above the top of the fabric, then lower it into the socket.
        # The head is brought in separately at a higher plane and lowered onto the bit.
        gauges = {
            "loose bit enters from behind": hull(
                -465, x + 3.75, y - 3.75, y + 3.75, 170, 220
            ),
            "bit lowered and extracted": shape(
                round_stock([x, y, z + 6], [x, y, 220], 3.75)
            ),
            "head and lever approach horizontally": hull(
                -475, x + 87, y - 22, y + 22, 186, 204
            ),
            "head seated through screw rise": hull(
                x - 12, x + 12, y - 12, y + 12, 158, 204
            ),
            "lever work and tool lift": hull(x, x + 87, y - 22, y + 22, 158, 204),
            "magnetic screw pickup": shape(round_stock([x, y, z], [x, y, 169], 5.15)),
            "outside hand corridor": hull(x + 24, x + 96, y - 28, y + 28, 175, 214),
        }
        report[skip] = {n: check(s, skip) for n, s in gauges.items()}
    return {
        "sourceSha256": plan["stepSha256"],
        "frame": "parked public assembly with passive revision in place, millimetres",
        "tool": "Wera 05073230001 with a 5 x 50 mm bit from pack 05073060001, installed bit separately",
        "receiving": "Accept the actual head within 24 mm width, 18 mm thickness and 12 mm behind the axis. Complete tool must fit at the declared seated height and face a 6 degree free return stroke. Maintain hand clearance to all wiring installed later.",
        "cases": report,
        "passed": all(not hits for site in report.values() for hits in site.values()),
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    d = run()
    a.output.write_text(json.dumps(d, indent=2) + "\n", encoding="utf8")
    print(d["passed"], {k: v for s in d["cases"].values() for k, v in s.items() if v})
