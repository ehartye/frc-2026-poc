"""Bound full deployment and lift travel against the fitted stationary through-ties."""

import argparse
import itertools
import json
from pathlib import Path
import sys
import numpy as np
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.gp import gp_Trsf, gp_Vec
from mast_ties import build
from offline import machine
from supplier import bounds
from verify_products import products
from foundation_job import ROOT


def bbox_gap(a, b):
    return float(
        np.linalg.norm(np.maximum.reduce([np.zeros(3), a[:3] - b[3:], b[:3] - a[3:]]))
    )


def move(body, offset):
    t = gp_Trsf()
    t.SetTranslation(gp_Vec(*offset.tolist()))
    return BRepBuilderAPI_Transform(body, t, False).Shape()


def bound_segment(moving, fixed, start, end):
    b = np.array(bounds(moving))
    bf = np.array(bounds(fixed))
    lo = b[:3] + np.minimum(start, end)
    hi = b[3:] + np.maximum(start, end)
    box_bound = bbox_gap(np.r_[lo, hi], bf)
    if box_bound > 1:
        return box_bound
    mid = (start + end) / 2
    distance = BRepExtrema_DistShapeShape(move(moving, mid), fixed).Value()
    below = distance - np.linalg.norm(end - start) / 2
    if below > 0.05:
        return below
    if np.linalg.norm(end - start) < 0.02:
        return max(0.0, below)
    return min(
        bound_segment(moving, fixed, start, mid), bound_segment(moving, fixed, mid, end)
    )


def run():
    sys.path.insert(0, str(ROOT / "cad/tower-lift"))
    from recipe import parts as moving_parts

    project = products(ROOT / "cad/assembly-release/foundation-student.step")
    parts, _, _, _ = build()
    ties = {n: machine(row["features"]) for n, row in parts.items()}
    markers = {}
    for row in moving_parts():
        if row["stage"] == "fixed":
            continue
        name = row["name"]
        positions = (
            np.zeros(3),
            np.array([-215.0, 0.0, 0.0]) if row["stage"] == "hooks" else np.zeros(3),
        )
        positions = (*positions, positions[-1] + np.array([0.0, 0.0, -100.0]))
        limits = []
        for n, fixed in ties.items():
            for start, end in itertools.pairwise(positions):
                gap = bound_segment(project[name], fixed, start, end)
                limits.append((gap, n))
        gap, n = min(limits)
        markers[name] = {"conservativeClearanceMm": gap, "limitingTieArticle": n}
    return {
        "operatingPathMm": [[0, 0], [215, 0], [215, 100]],
        "basis": "Exact parked STEP for each moving item. Swept bounding-box separation or recursive rigid-translation distance bound covers every point on each commanded segment.",
        "moving": markers,
        "passed": all(v["conservativeClearanceMm"] > 0 for v in markers.values()),
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    result = run()
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
    if not result["passed"]:
        raise SystemExit(1)
