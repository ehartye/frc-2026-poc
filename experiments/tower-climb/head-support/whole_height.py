"""Parked whole-robot conservative height including source solids and both candidate head/tie sets."""

import sys, json, hashlib, itertools
from pathlib import Path
import numpy as np
from OCP.STEPControl import STEPControl_Reader
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID
from OCP.BRepCheck import BRepCheck_Analyzer

p = Path(__file__).parent
root = p.parents[2]
tie = Path(sys.argv[1]).resolve() / "cad/assembly-release"
sys.path.insert(0, str(tie))
from verify_products import products
from mast_ties import build
from swerve import layout
from offline import machine


def bounds(sh):
    b = Bnd_Box()
    BRepBndLib.AddOptimal_s(sh, b, False, False)
    return list(b.CornerMin().Coord() + b.CornerMax().Coord())


parts = products(root / "cad/assembly-release/foundation-student.step")
for side in ("left", "right"):
    del parts[side + " upper bearing plate"]
    del parts[side + " lead screw envelope"]
boxes = {k: bounds(sh) for k, sh in parts.items()}
ties = build()[0]
boxes.update({name: bounds(machine(r["features"])) for name, r in ties.items()})
reader = STEPControl_Reader()
source = p / "retained-head-fit.step"
assert int(reader.ReadFile(str(source))) == 1
reader.TransferRoots()
e = TopExp_Explorer(reader.OneShape(), TopAbs_SOLID)
i = 0
while e.More():
    sh = e.Current()
    assert BRepCheck_Analyzer(sh).IsValid()
    i += 1
    boxes["retained head solid " + str(i)] = bounds(sh)
    e.Next()
assert i == 20
sites = np.array([[a["translation"][0], a["translation"][1], 1] for a in layout()[3]])
out = {}
for u in [0, 1, 2, 3]:
    top = (-1, None)
    candidates = []
    for dz in itertools.product((-u, u), repeat=4):
        for three in itertools.combinations(range(4), 3):
            a, b, c = np.linalg.solve(sites[list(three)], np.array(dz)[list(three)])
            if min(sites @ np.array([a, b, c]) - dz) < -1e-9:
                continue
            for n, v in boxes.items():
                h = (
                    v[5]
                    + (v[3] if a >= 0 else v[0]) * a
                    + (v[4] if b >= 0 else v[1]) * b
                    + c
                    + 0.5
                )
                if h > top[0]:
                    top = (
                        h,
                        {
                            "part": n,
                            "partBoundsMm": v,
                            "wheelDeltaMm": dz,
                            "supports": three,
                        },
                    )
    out[u] = {"maximumHeightMm": top[0], "remainingTo762Mm": 762 - top[0], **top[1]}
print(json.dumps(out, indent=2))
(p / "retained-head-whole-height.json").write_text(
    json.dumps(
        {
            "source": hashlib.sha256(source.read_bytes()).hexdigest(),
            "loadedProductBounds": len(boxes),
            "candidateHeadsSolidCount": i,
            "cases": out,
            "scope": "Conservative individual solid bounding boxes evaluated over three-point support planes, fourth wheel may unload. Machining +0.5 mm. No tire stiffness calibration. Upper plates in separate tied-head recipe require integrating both sets of cuts. Lower brake candidate sits below 700 mm.",
        },
        indent=2,
    )
)
