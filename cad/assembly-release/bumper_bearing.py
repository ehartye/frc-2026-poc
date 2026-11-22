"""Measure each bumper's inward rail seat and the individual outward retention surfaces."""
import argparse
import hashlib
import json
from pathlib import Path

from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.gp import gp_Trsf, gp_Vec

from drivetrain_fit import vol
from offline import machine
from passive_job import recipe
from verify_products import products


def seat(panel, support, direction, depth=0.01):
    def volume_at(distance):
        transform = gp_Trsf()
        transform.SetTranslation(gp_Vec(*(distance * v for v in direction)))
        shifted = BRepBuilderAPI_Transform(panel, transform, False).Shape()
        return vol(BRepAlgoAPI_Common(shifted, support).Shape())

    return {
        "parkedCommonMm3": round(volume_at(0), 5),
        "compressedAreaMm2": round(volume_at(depth) / depth, 4),
        "reversedCommonMm3": round(volume_at(-depth), 5),
    }


def measure(issued=None):
    job = recipe()
    raw = job["parts"]
    if issued:
        solids = products(issued)
    else:
        solids = {name: machine(row["features"]) for name, row in raw.items()}
    results = {}
    for panel in job["panels"]:
        name = panel["panel"]
        stem = name.replace(" blue", "")
        backing = stem + " backer"
        rail = raw[backing]["parent"]
        if "side" in name:
            inward = (0, -1 if name.startswith("left") else 1, 0)
        else:
            inward = (1 if name.startswith("rear") else -1, 0, 0)
        contacts = {"inward backer to rail": seat(solids[backing], solids[rail], inward)}
        for i, _ in enumerate(panel["installedFrameStationsMm"], 1):
            loc = f"{stem} mounting {i}"
            contacts[f"{i} M6 head to bracket"] = seat(solids[loc + " top screw"], solids[loc + " angle"], (0, 0, -1))
            for pair in ("a", "b"):
                key = f"{loc} {pair} panel"
                contacts[f"{i}{pair} washer to wood"] = seat(solids[key + " washer"], solids[backing], inward)
                contacts[f"{i}{pair} head to washer"] = seat(solids[key + " screw"], solids[key + " washer"], inward)
        results[name] = contacts
    checks = [entry for panel in results.values() for entry in panel.values()]
    return {
        "predecessorStepSha256": job["stepSha256"],
        "inspectedStepSha256": hashlib.sha256(issued.read_bytes()).hexdigest() if issued else None,
        "perturbationMm": 0.01,
        "panels": results,
        "surfaceCount": len(checks),
        "passed": all(entry["parkedCommonMm3"] < 0.001 and entry["compressedAreaMm2"] > 1 and entry["reversedCommonMm3"] < 0.001 for entry in checks),
        "scope": "Continuous wood-to-frame faces carry inward compression. Each panel screw bears through its individual washer into the plywood; each removable top screw bears on the bracket. The opposite perturbation must unload every seat. These static contact areas exclude clamp preload, fastener cooldown, impact pressure, wood pull-through, weld strength and fabric/foam adhesion.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--issued-step", type=Path)
    args = parser.parse_args()
    result = measure(args.issued_step)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf8", newline="\n")
    print(result["surfaceCount"], "surfaces, passed", result["passed"])
    raise SystemExit(not result["passed"])
