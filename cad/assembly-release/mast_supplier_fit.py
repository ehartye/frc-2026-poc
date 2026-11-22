"""Sweep the installed supplier module geometry against every anchor part and installation tool."""

import argparse
import hashlib
import json
import math
from pathlib import Path
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Common
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from drivetrain_fit import ROTATING, broad, cyl, moved, vol
from mast_ties import build
from offline import machine, shape
from supplier import content, bounds
from swerve import layout


def register(source):
    cfg, _, _, sites = layout()
    geometry = content(source, cfg["swerve"]["sha256"])
    sweep = {}
    for name, part in geometry.items():
        if int(name.split(":")[0]) in ROTATING:
            bb = bounds(part)
            r = (
                math.hypot(max(abs(bb[0]), abs(bb[3])), max(abs(bb[2]), abs(bb[5])))
                + 0.01
            )
            if r > 47.4:
                limit = cyl([0, bb[1] - 1, 0], [0, bb[4] + 1, 0], 47.4)
                if vol(BRepAlgoAPI_Cut(part, limit).Shape()) > 0.001:
                    raise ValueError("Rotation radius fails: " + name)
                r = 47.4
            part = cyl([0, bb[1], 0], [0, bb[4], 0], r)
        sweep[name] = part
    return cfg["swerve"]["sha256"], sites, sweep


def check(source):
    pin, sites, local = register(source)
    articles, _, tools, _ = build()
    items = {n: machine(v["features"]) for n, v in articles.items()}
    items.update({k: shape(v) for k, v in tools.items()})
    shape_bounds = {k: bounds(v) for k, v in items.items()}
    result = {}
    for site in sites:
        pairs = []
        mounted = {}
        hits = {}
        for k, part in local.items():
            body = moved(part, site)
            bb = bounds(body)
            mounted[k] = body
            for n, b in shape_bounds.items():
                gap = math.sqrt(
                    sum(
                        max(0.0, bb[i] - b[i + 3], b[i] - bb[i + 3]) ** 2
                        for i in range(3)
                    )
                )
                pairs.append((gap, n, k))
                if (
                    broad(b, bb)
                    and (v := vol(BRepAlgoAPI_Common(body, items[n]).Shape())) > 0.025
                ):
                    hits[n + "; " + k] = round(v, 5)
        closest = (math.inf, None, None)
        for gap, n, k in sorted(pairs):
            if gap > closest[0]:
                break
            closest = min(
                closest,
                (BRepExtrema_DistShapeShape(mounted[k], items[n]).Value(), n, k),
            )
        result[site["name"]] = {
            "pose": site,
            "minimumMm": closest[0],
            "anchorOrTool": closest[1],
            "supplierLeaf": closest[2],
            "collisionsMm3": hits,
        }
    return {
        "anchorSha256": hashlib.sha256(
            Path(__file__).with_name("mast_ties.py").read_bytes()
        ).hexdigest(),
        "supplierSha256": pin,
        "registeredLeavesPerModule": len(local),
        "sweptLeafIndices": sorted(ROTATING),
        "stages": result,
        "passed": all(not c["collisionsMm3"] for c in result.values()),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("supplier", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = check(args.supplier)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    if not report["passed"]:
        raise SystemExit(1)
