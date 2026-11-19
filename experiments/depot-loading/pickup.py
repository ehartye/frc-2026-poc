"""Register release-day depot stock and compare a parked reach-over intake with the fixed robot."""

import argparse
import copy
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "cad/own-zone-upper"))
sys.path.insert(0, str(HERE.parent / "own-zone-cycle"))
from prepare_upper import parts
from intake import simulate_intake
from field_register import PIN


def register(raw):
    inventory = json.loads((raw / "depot-registration.json").read_bytes())
    (front,) = [
        r["boundsMm"]
        for r in inventory
        if "GE-26601-01" in r["name"] and r["boundsMm"][3] < 0
    ]
    centers = []
    for r in inventory:
        bounds = r["boundsMm"]
        if (
            r["name"] == "GE-26900: Fuel"
            and bounds[3] < front[3]
            and bounds[5] < 155
            and front[1] < bounds[1] < front[4]
        ):
            centers.append([(a + b) / 2 for a, b in zip(bounds[:3], bounds[3:])])
    centers.sort(key=lambda p: (-p[0], p[1]))
    if len(centers) != 24:
        raise ValueError("Expected the 24 registered pieces in the blue depot")
    sides = [
        r["boundsMm"]
        for r in inventory
        if "GE-26601-02" in r["name"] and r["boundsMm"][3] < 0
    ]
    if len(sides) != 2:
        raise ValueError("Expected two blue DEPOT side tubes")
    return (
        front,
        sides,
        [
            {"id": f"blue-depot-{i + 1:02}", "centerMm": p}
            for i, p in enumerate(centers)
        ],
    )


class Approach:
    duration = 3.0

    def __init__(self, initial, barrier, candidate):
        self.initial = initial
        self.barrier = barrier
        self.candidate = candidate
        self.tip = min(0.605, self.initial[0] + 0.060)

    def roller(self, t, parked):
        if not self.candidate:
            return (
                0.275 + 0.103 * math.cos(math.radians(-39)),
                0.240 + 0.103 * math.sin(math.radians(-39)),
                0,
                0,
            )
        # Start overhead, lower, then sweep toward the receiver. Smoothstep avoids instantaneous velocity changes.
        poses = [
            (0.0, self.tip, 0.233),
            (0.25, self.tip, 0.155),
            (0.92, 0.336, 0.159),
            (1.12, 0.336, 0.159),
            (1.40, 0.330, 0.302),
        ]
        for (ta, xa, za), (tb, xb, zb) in zip(poses, poses[1:]):
            if t <= tb:
                u = (t - ta) / (tb - ta)
                blend = u * u * (3 - 2 * u)
                rate = 6 * u * (1 - u) / (tb - ta)
                return (
                    xa + (xb - xa) * blend,
                    za + (zb - za) * blend,
                    (xb - xa) * rate,
                    (zb - za) * rate,
                )
        return poses[-1][1], poses[-1][2], 0, 0


def run(raw):
    front, sides, centers = register(raw)
    base = parts()[1]
    near = 0.345
    rail = (near, near + (front[3] - front[0]) / 1000, front[5] / 1000)
    robot_x = front[3] / 1000 + near
    result = {
        "sourceFieldSha256": PIN,
        "frontTubeBoundsMm": front,
        "sideTubeBoundsMm": sides,
        "centerXM": robot_x,
        "fieldHeadingDeg": 180,
        "floorStock": centers,
        "rows": [],
    }
    for rank in range(4):
        fuel = centers[6 * rank + 2]
        gx, gy, gz = fuel["centerMm"]
        initial = (robot_x - gx / 1000, gz / 1000)
        for name, candidate, power in (
            ("original floor intake", False, True),
            ("over-rail stroke", True, True),
            ("stalled roller during stroke", True, False),
        ):
            stock = copy.deepcopy(base)
            if candidate:
                for part in stock:
                    if part["name"] in ("left intake ramp", "right intake ramp"):
                        part["end"] = [402, part["end"][1], 35]
            approach = Approach(initial, rail, candidate)
            r = simulate_intake(stock, drive=0, roller=power, source=approach)
            result["rows"].append(
                {
                    "sourceId": fuel["id"],
                    "rank": rank + 1,
                    "case": name,
                    "startM": initial,
                    "rollerForwardExtentM": approach.tip + 0.038
                    if candidate
                    else 0.393,
                    "trajectory": r["trajectory"],
                    "contacts": r["events"],
                    "settled": r["crossing"],
                    "head": r["lifted"],
                    "finalMm": r["finalMm"],
                }
            )
    return result


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("cache", type=Path)
    cli.add_argument("output", type=Path)
    args = cli.parse_args()
    data = run(args.cache)
    args.output.write_text(json.dumps(data, allow_nan=False) + "\n", encoding="utf8")
    for r in data["rows"]:
        print(
            r["sourceId"],
            r["case"],
            r["finalMm"],
            r["settled"] and r["settled"]["timeS"],
            r["head"] and r["head"]["timeS"],
        )
