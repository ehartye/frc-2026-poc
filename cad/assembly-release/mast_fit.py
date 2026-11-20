"""Check the mast attachments and the onset of positive bearing in each registered load direction."""

import argparse
import hashlib
import json
from pathlib import Path

from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.gp import gp_Trsf, gp_Vec
from bumper_bearing import seat
from drivetrain_fit import broad, vol
from mast_anchors import build
from offline import machine, shape
from passive_job import recipe
from supplier import bounds
from verify_products import products


def projected_contact(moving, fixed, direction, distance):
    t = gp_Trsf()
    t.SetTranslation(gp_Vec(*(x * distance for x in direction)))
    moved = BRepBuilderAPI_Transform(moving, t, False).Shape()
    return vol(BRepAlgoAPI_Common(moved, fixed).Shape())


def transitions(moving, fixed, axes, samples):
    rows = {}
    for label, direction in axes.items():
        readings = [projected_contact(moving, fixed, direction, d) for d in samples]
        if readings[0] > 1e-6 or readings[-1] < 1e-6:
            raise ValueError(f"Bearing transition missing on {label}: {readings}")
        rows[label] = dict(
            translationMm=list(samples), materialIntersectionsMm3=readings
        )
    return rows


def inspect():
    job = recipe()
    path = Path(__file__).resolve().parents[2] / job["stepBase"]
    scene = products(path)
    scene.update({n: machine(row["features"]) for n, row in job["parts"].items()})
    parts, cuts, tools, seats = build()
    for name, operations in cuts.items():
        for f in operations:
            scene[name] = BRepAlgoAPI_Cut(scene[name], shape(f["shape"])).Shape()
    scene.update({n: machine(row["features"]) for n, row in parts.items()})
    boxes = {n: bounds(s) for n, s in scene.items()}
    checks = {}
    for name, solid in [
        *((n, scene[n]) for n in parts),
        *((n, shape(s)) for n, s in tools.items()),
    ]:
        bb = bounds(solid)
        overlap = {}
        for other, obs in scene.items():
            if other == name or not broad(bb, boxes[other]):
                continue
            common = vol(BRepAlgoAPI_Common(solid, obs).Shape())
            if common > 0.025:
                overlap[other] = round(common, 5)
        checks[name] = overlap
        # Only the smooth bolt envelope against modeled M8 tap-pilot stock is intentionally common.
        for other in overlap:
            if not (
                (
                    name.endswith("draw screw")
                    and other == name.replace(" draw screw", " anchor spigot")
                )
                or (
                    name.endswith("anchor spigot")
                    and other == name.replace(" anchor spigot", " draw screw")
                )
            ):
                raise ValueError((name, overlap))
    bearings = {}
    lateral = {
        "forward": (1, 0, 0),
        "backward": (-1, 0, 0),
        "left": (0, 1, 0),
        "right": (0, -1, 0),
    }
    vertical = {
        "up": (0, 0, 1),
        "down": (0, 0, -1),
        "left": (0, 1, 0),
        "right": (0, -1, 0),
    }
    from shop import round_stock

    for side, y in (("left", 326), ("right", -326)):
        for suffix, x in ((" mast", -180), (" aft mast", -280)):
            mast = side + suffix
            spigot = mast + " anchor spigot"
            rail = side + " perimeter tube"
            # Isolate the certified cylindrical pilot span; the extended insert also contacts its mast.
            probe = shape(round_stock([x, y, 111.625], [x, y, 114.8], 6.30))
            bearings[spigot + " on rail"] = transitions(
                probe, scene[rail], lateral, (0.14, 0.16)
            )
            for j in (1, 2):
                name = mast + f" cross fastener {j} fitted sleeve"
                bearings[name + " on mast"] = transitions(
                    scene[name], scene[mast], vertical, (0.014, 0.020)
                )
                bearings[name + " on insert"] = transitions(
                    scene[name], scene[spigot], vertical, (0.014, 0.020)
                )
    return {
        "projectStepSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "recipeSha256": hashlib.sha256(
            Path(__file__).with_name("mast_anchors.py").read_bytes()
        ).hexdigest(),
        "installedArticles": len(parts),
        "toolSweeps": len(tools),
        "clearanceScreen": checks,
        "bearing": bearings,
        "seats": [
            {"moving": a, "fixed": b, "direction": v, **seat(scene[a], scene[b], v)}
            for a, b, v in seats
        ],
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("output", type=Path)
    f = ap.parse_args()
    f.output.write_text(json.dumps(inspect(), indent=2) + "\n", encoding="utf8")
