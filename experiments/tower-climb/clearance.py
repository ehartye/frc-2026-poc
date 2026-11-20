"""Test native moving-vs-fixed geometry at working and excess travel using exact STEP solids."""

import json, sys
from pathlib import Path
import numpy as np
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.gp import gp_Trsf, gp_Vec

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "cad/tower-lift"))
from scene import records


def check():
    components = records()
    cases = []
    for deploy, lower in (
        (0, 0),
        (108, 0),
        (215, 0),
        (215, 50),
        (215, 100),
        (215, 115),
    ):
        moved = []
        for shape, info in components:
            d = np.array(
                [
                    -deploy if info["stage"] == "hooks" else 0,
                    0,
                    -lower if info["stage"] != "fixed" else 0,
                ]
            )
            if d.any():
                transform = gp_Trsf()
                transform.SetTranslation(gp_Vec(*d.astype(float)))
                shape = BRepBuilderAPI_Transform(shape, transform, False).Shape()
            moved.append((shape, info, np.array(info["boundsMm"]) + np.tile(d, 2)))
        collisions = []
        for i, (a, pa, ba) in enumerate(moved):
            for b, pb, bb in moved[i + 1 :]:
                if (
                    pa["stage"] == pb["stage"]
                    or (
                        np.minimum(ba[3:], bb[3:]) - np.maximum(ba[:3], bb[:3]) < 0.001
                    ).any()
                ):
                    continue
                common = BRepAlgoAPI_Common(a, b)
                props = GProp_GProps()
                BRepGProp.VolumeProperties_s(common.Shape(), props)
                if props.Mass() > 0.01:
                    collisions.append(
                        dict(
                            pair=[pa["id"], pb["id"]], volumeMm3=round(props.Mass(), 3)
                        )
                    )
        cases.append(dict(deployMm=deploy, lowerMm=lower, intersections=collisions))
    return cases


if __name__ == "__main__":
    results = check()
    (HERE / "clearance.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf8", newline="\n"
    )
    print(
        [
            (r["lowerMm"], [(v["pair"], v["volumeMm3"]) for v in r["intersections"]])
            for r in results
        ]
    )
