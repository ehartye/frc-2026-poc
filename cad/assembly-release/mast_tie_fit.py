"""Cold geometric checks for the two-ended shear pilots and the four full-height mast ties."""

import argparse
import hashlib
import json
import math
from pathlib import Path

from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut

from bumper_bearing import seat
from drivetrain_fit import broad, vol
from mast_fit import transitions
from mast_ties import build
from offline import machine, shape
from passive_job import recipe
from shop import round_stock
from supplier import bounds
from verify_products import products


def run():
    job = recipe()
    path = Path(__file__).resolve().parents[2] / job["stepBase"]
    parts, cuts, tools, seats = build()
    scene = products(path)
    scene.update({name: machine(row["features"]) for name, row in job["parts"].items()})
    for name, operations in cuts.items():
        for op in operations:
            scene[name] = BRepAlgoAPI_Cut(scene[name], shape(op["shape"])).Shape()
    scene.update({name: machine(row["features"]) for name, row in parts.items()})
    boxes = {n: bounds(body) for n, body in scene.items()}
    evidence = {}
    candidates = {name: scene[name] for name in parts}
    candidates.update({name: shape(row) for name, row in tools.items()})
    for name, body in candidates.items():
        limits = bounds(body)
        evidence[name] = {
            other: round(volume, 5)
            for other, item in scene.items()
            if other != name
            and broad(limits, boxes[other])
            and (volume := abs(vol(BRepAlgoAPI_Common(body, item).Shape()))) > 0.025
        }
    directions = {
        "forward": [1, 0, 0],
        "aft": [-1, 0, 0],
        "left": [0, 1, 0],
        "right": [0, -1, 0],
    }
    bearings = {}
    thread_pairs = {}
    for side, y in (("left", 326), ("right", -326)):
        for mast, x in ((side + " mast", -180), (side + " aft mast", -280)):
            for label, z0, z1, owner in (
                ("lower", 111.625, 114.8, side + " perimeter tube"),
                ("upper", 744, 749.5, side + " upper bearing plate"),
            ):
                # Isolate the respective pilot's engagement in the machined parent.
                key = mast + (
                    " lower rail key" if label == "lower" else " upper plate key"
                )
                probe = (
                    scene[key]
                    if label == "upper"
                    else shape(round_stock([x, y, z0], [x, y, z1], 6.3, 4.3))
                )
                bearings[mast + " " + label + " pilot against " + owner] = transitions(
                    probe, scene[owner], directions, (0.14, 0.16)
                )
                bearings[key + " against mast"] = transitions(
                    scene[key], scene[mast], directions, (0.09, 0.11)
                )
            head = mast + " upper plate key"
            rod = mast + " full length M8 tie"
            observed = evidence[head].pop(rod, 0)
            reverse = evidence[rod].pop(head, 0)
            target = math.pi * (4**2 - 3.4**2) * 27
            if max(abs(observed - target), abs(reverse - target)) > 0.002:
                raise ValueError((head, observed, reverse, target))
            thread_pairs[head] = {
                "rod": rod,
                "modeledMajorVsTapPilotMm3": observed,
                "grossEngagementMm": 27,
            }
    result = {
        "foundationStepSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "tieRecipeSha256": hashlib.sha256(
            Path(__file__).with_name("mast_ties.py").read_bytes()
        ).hexdigest(),
        "articlesAndSweeps": evidence,
        "threads": thread_pairs,
        "maximumRobotZmm": max(v[5] for v in boxes.values()),
        "seats": [
            {"moving": a, "fixed": b, "direction": v, **seat(scene[a], scene[b], v)}
            for a, b, v in seats
        ],
        "lateralBearingTransitions": bearings,
        "scope": "Parked project recipe with idealized stock. Incipient lateral bearing under signed displacement is checked independently of clamp friction. Static geometric seating does not establish joint preload or stock strength.",
    }
    result["passed"] = all(not hits for hits in evidence.values()) and all(
        row["parkedCommonMm3"] < 0.001
        and row["reversedCommonMm3"] < 0.001
        and row["compressedAreaMm2"] > 0.1
        for row in result["seats"]
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = run()
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    if not report["passed"]:
        raise SystemExit(1)
