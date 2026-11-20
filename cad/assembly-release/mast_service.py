"""Bound the existing battery cart and independently removable bumper paths against every proposed mast fastener."""

import argparse
import json
from pathlib import Path
import numpy as np
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from drivetrain_fit import vol, broad
from mast_ties import build
from passive_job import recipe
from offline import machine, shape
from rear_bumper_tool import run as rear_ratchet
from shop import rect, round_stock
from supplier import bounds


def check():
    plan = recipe()
    parts, _, tool_rows, _ = build()
    solids = {n: machine(row["features"]) for n, row in parts.items()}
    obstacles = {n: (s, bounds(s)) for n, s in solids.items()}
    tools = {n: shape(v) for n, v in tool_rows.items()}
    gauges = {}
    for panel in plan["panels"]:
        name = panel["panel"]
        axis = 0 if "front" in name or name.startswith("rear") else 1
        sign = -1 if name.startswith(("rear", "right")) else 1
        moving = [
            m
            for m in plan["groups"]["Installed " + name][1:]
            if not m.endswith((" top screw", " frame boss"))
        ]
        for item in moving:
            for i, feature in enumerate(plan["parts"][item]["features"]):
                if feature["op"] == "cut":
                    continue
                box = np.array(bounds(shape(feature["shape"])), dtype=float)
                box[:3] += 1e-7
                box[3:] -= 1e-7
                box[axis + 3 if sign > 0 else axis] += 60 * sign
                gauges[f"{item} stock {i} 60mm withdrawal"] = shape(
                    rect(box[:3], box[3:])
                )
        for i, (x, y, z) in enumerate(panel["topScrewAxisMm"]):
            gauges[f"{name} cap {i} withdrawal"] = shape(
                round_stock([x, y, z], [x, y, z + 38], 5.05)
            )
            if not name.startswith("rear"):
                gauges[f"{name} cap {i} driver"] = shape(
                    round_stock([x, y, z + 5.99], [x, y, 201], 3.1)
                )
                gauges[f"{name} cap {i} handle"] = shape(
                    round_stock([x, y, 201], [x, y, 245], 8)
                )
    for n, row in plan["parts"].items():
        if not (
            n.startswith(("battery cradle", "battery secured", "battery center"))
            or "battery end stop" in n
            or "battery hold-down" in n
        ):
            continue
        box = list(bounds(machine(row["features"])))
        box[2] -= 270
        gauges[n + " 270mm sled drop"] = shape(rect(box[:3], box[3:]))
    for side, y in (("left", 327.3), ("right", -327.3)):
        for end, x in (("fore", 74), ("aft", -77)):
            pad = shape(rect([x - 32, y - 9, 48], [x + 32, y + 9, 64]))
            gauges[side + " " + end + " cart pad"] = pad
            for name, tool in tools.items():
                if (
                    broad(bounds(pad), bounds(tool))
                    and vol(BRepAlgoAPI_Common(tool, pad).Shape()) > 0.025
                ):
                    raise ValueError("Service cart blocks " + name)
    checks = {}
    for name, body in gauges.items():
        box = bounds(body)
        checks[name] = {
            n: round(v, 4)
            for n, (s, b) in obstacles.items()
            if broad(box, b) and (v := vol(BRepAlgoAPI_Common(s, body).Shape())) > 0.025
        }
    rear = rear_ratchet(solids)
    return {
        "gauges": len(gauges),
        "newArticles": len(solids),
        "collisionsMm3": checks,
        "rearRatchet": rear,
        "passed": all(not h for h in checks.values()) and rear["passed"],
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    report = check()
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    print(report["gauges"], report["newArticles"], report["passed"], flush=True)
    if not report["passed"]:
        raise SystemExit(1)
