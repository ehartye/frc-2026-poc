"""Whole-robot STEP contact audit. A touching pair still needs a real attachment or bearing."""

import argparse
import itertools
import json
import sys
from pathlib import Path

import numpy as np
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "tower-lift"))
from scene import records


def audit(solids):
    seen = {s["id"]: set() for _, s in solids}
    pairs = []
    for (sa, a), (sb, b) in itertools.combinations(solids, 2):
        x, y = np.asarray(a["boundsMm"]), np.asarray(b["boundsMm"])
        overlap = np.minimum(x[3:], y[3:]) - np.maximum(x[:3], y[:3])
        if np.linalg.norm(np.minimum(overlap, 0)) > 0.051:
            continue
        query = BRepExtrema_DistShapeShape(sa, sb)
        if not query.IsDone():
            raise ValueError((a["id"], b["id"]))
        gap = query.Value()
        if gap > 0.05:
            continue
        volume = 0.0
        if (overlap > 0.001).all():
            op = BRepAlgoAPI_Common(sa, sb)
            prop = GProp_GProps()
            BRepGProp.VolumeProperties_s(op.Shape(), prop)
            volume = prop.Mass()
        key = [a["id"], b["id"]]
        pairs.append(
            dict(parts=key, gapMm=round(gap, 5), commonVolumeMm3=round(volume, 4))
        )
        for k, v in (key, key[::-1]):
            seen[k].add(v)
    groups = []
    pending = set(seen)
    while pending:
        start = min(pending)
        stack = [start]
        group = set()
        while stack:
            n = stack.pop()
            if n in group:
                continue
            group.add(n)
            stack.extend(seen[n] - group)
        groups.append(sorted(group))
        pending -= group
    return dict(
        criterion="Native STEP shape distance <= 0.05 mm at parked pose. Geometric contact alone does not retain or transmit rated loads.",
        groups=sorted(groups, key=len, reverse=True),
        pairs=pairs,
    )


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("output", type=Path)
    args = a.parse_args()
    result = audit(records())
    args.output.write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf8", newline="\n"
    )
    print([len(g) for g in result["groups"]], len(result["pairs"]))
