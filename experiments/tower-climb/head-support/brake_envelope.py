"""Size two vendor brake envelopes against the season's parked assembly and height datum."""

import json, sys, hashlib
from pathlib import Path
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.BRepExtrema import BRepExtrema_DistShapeShape

here = Path(__file__).resolve().parent
root = here.parents[2]
sys.path.insert(0, str(root / "cad/assembly-release"))
from verify_products import products
from offline import shape
from shop import round_stock

source = root / "cad/assembly-release/foundation-student.step"
ps = products(source)


def bounds(q):
    b = Bnd_Box()
    BRepBndLib.AddOptimal_s(q, b, False, False)
    return list(b.CornerMin().Coord() + b.CornerMax().Coord())


boxes = {n: bounds(s) for n, s in ps.items()}
wheel = {
    n: b[2] for n, b in boxes.items() if any(k in n.lower() for k in ["tread", "wheel"])
}
floor = min(wheel.values())
reg = root / "kickoff/rule-register.json"


def entries(v):
    if isinstance(v, dict):
        if v.get("id") == "height" and "value" in v:
            yield v
        for value in v.values():
            yield from entries(value)
    elif isinstance(v, list):
        for value in v:
            yield from entries(value)


height = next(entries(json.loads(reg.read_bytes())))
limit = floor + 25.4 * height["value"]
report = {
    "sourceStep": hashlib.sha256(source.read_bytes()).hexdigest(),
    "registeredTireBottomMm": floor,
    "wheelCandidates": wheel,
    "startingHeightRule": height,
    "highestPermittedZMm": limit,
    "originalHighest": max(boxes, key=lambda k: boxes[k][5]),
    "originalHighestZMm": max(b[5] for b in boxes.values()),
    "headControlOverHeightMm": 765 - limit,
    "proposedTieAt763OverHeightMm": 763 - limit,
    "candidates": {},
}
for side, y in [("left", 305), ("right", -305)]:
    for name, diam, length in [("SA-35", 35, 27), ("SA-40", 40, 30.5)]:
        for loc, z in [
            ("above-current-plate", 750),
            ("above-lock-stack", 765),
            ("below-existing-reduction", 551 - length),
        ]:
            q = shape(round_stock((-240, y, z), (-240, y, z + length), diam / 2))
            bb = bounds(q)
            hit = []
            for n, pp in ps.items():
                b = boxes[n]
                if any(
                    min(bb[i + 3], b[i + 3]) - max(bb[i], b[i]) < 0.0001
                    for i in range(3)
                ):
                    continue
                g = GProp_GProps()
                BRepGProp.VolumeProperties_s(BRepAlgoAPI_Common(q, pp).Shape(), g)
                if g.Mass() > 0.001:
                    hit.append([n, round(g.Mass(), 3)])
            report["candidates"][" ".join((side, name, loc))] = {
                "minimumZ": z,
                "maximumZ": z + length,
                "ownTopMarginMm": limit - (z + length),
                "nativeEnvelopeOverlapsMm3": hit,
            }
(here / "brake-envelope.json").write_text(json.dumps(report, indent=2) + "\n")
print(
    "wheel refs:",
    wheel,
    "floor:",
    floor,
    "allowable top:",
    limit,
    "original:",
    report["originalHighestZMm"],
)
for n, r in report["candidates"].items():
    if n.startswith("left"):
        print(n, r["ownTopMarginMm"], r["nativeEnvelopeOverlapsMm3"])
