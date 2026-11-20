"""Measure square-cut frame lands directly in the modeled stock, including the complete end annulus."""

import json
from pathlib import Path
import sys
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.gp import gp_Trsf, gp_Vec

from frame import build
from offline import machine
from drivetrain_fit import vol


def sample(part, other, direction):
    gap = BRepExtrema_DistShapeShape(part, other).Value()
    base = vol(BRepAlgoAPI_Common(part, other).Shape())
    land = []
    for delta in (0.005, 0.01, 0.02):
        x = gp_Trsf()
        x.SetTranslation(gp_Vec(*(d * delta for d in direction)))
        pressed = BRepBuilderAPI_Transform(part, x, False).Shape()
        area = (vol(BRepAlgoAPI_Common(pressed, other).Shape()) - base) / delta
        land.append(round(area, 4))
    return dict(
        gapMm=round(gap, 6),
        commonMm3=round(base, 6),
        perturbationMm=[0.005, 0.01, 0.02],
        areaMm2=land,
    )


def run():
    parts = {k: machine(v["features"]) for k, v in build().items()}
    out = {}

    def pair(a, b, vec):
        out[a + " / " + b] = sample(parts[a], parts[b], vec)

    for end in ("rear", "front"):
        cross = end + " deck crossmember"
        for side, sg in (("left", 1), ("right", -1)):
            plate = f"{end} {side} crossmember backing plate"
            post = f"{end} {side} hopper post"
            pair(cross, plate, [0, sg, 0])
            pair(plate, side + " perimeter tube", [0, sg, 0])
            pair(post, cross, [0, 0, -1])
            pair(post, side + " floor sill", [0, 0, 1])
    expected = 25.4**2 - (25.4 - 2 * 3.175) ** 2
    for k, v in out.items():
        if v["gapMm"] > 1e-5 or v["commonMm3"] > 1e-3:
            raise ValueError(k)
        if (
            "deck crossmember /" in k
            and max(abs(x - expected) for x in v["areaMm2"]) > 0.002
        ):
            raise ValueError(k)
    return out


if __name__ == "__main__":
    Path(sys.argv[1]).write_text(json.dumps(run(), indent=2) + "\n", encoding="utf8")
