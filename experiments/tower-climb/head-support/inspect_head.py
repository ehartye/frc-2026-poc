from pathlib import Path
import sys, json, hashlib, math
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.gp import gp_Vec, gp_Trsf
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / "cad/assembly-release"))
from verify_products import products
from shop import round_stock
from offline import shape


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def prop(sh, kind):
    g = GProp_GProps()
    (BRepGProp.SurfaceProperties_s if kind == "area" else BRepGProp.VolumeProperties_s)(
        sh, g
    )
    return abs(g.Mass())


def box(sh):
    b = Bnd_Box()
    BRepBndLib.AddOptimal_s(sh, b, False, False)
    return (*b.CornerMin().Coord(), *b.CornerMax().Coord())


def face_z(sh, z):
    exp = TopExp_Explorer(sh, TopAbs_FACE)
    while exp.More():
        bb = box(exp.Current())
        if abs(bb[2] - z) < 0.001 and abs(bb[5] - z) < 0.001:
            yield exp.Current()
        exp.Next()


def moved(sh, z):
    t = gp_Trsf()
    t.SetTranslation(gp_Vec(0, 0, z))
    return BRepBuilderAPI_Transform(sh, t, False).Shape()


p = root / "cad/assembly-release/foundation-student.step"
parts = products(p)


def overlap(a, b):
    return prop(BRepAlgoAPI_Common(a, b).Shape(), "volume")


def interface(a, b, z):
    return sum(
        prop(BRepAlgoAPI_Common(f, g).Shape(), "area")
        for f in face_z(a, z)
        for g in face_z(b, z)
    )


res = {}
for side, sgn in [("left", 1), ("right", -1)]:
    screw = parts[side + " lead screw envelope"]
    plate = parts[side + " upper bearing plate"]
    x = -240
    y = sgn * 305
    top = 744
    near = {}
    for n, q in parts.items():
        if n == side + " lead screw envelope":
            continue
        bb = box(q)
        if (
            min(
                bb[3] - x + 6,
                x + 6 - bb[0],
                bb[4] - y + 6,
                y + 6 - bb[1],
                bb[5] - 555,
                746 - bb[2],
            )
            < 0
        ):
            continue
        near[n] = {
            "gapMm": round(BRepExtrema_DistShapeShape(screw, q).Value(), 5),
            "overlapMm3": round(overlap(screw, q), 5),
        }
    # 24 mm washer OD is an illustrative shop envelope for testing the plate support.
    gauges = []
    for outer in (14, 18, 24):
        gauge = shape(round_stock([x, y, top - 0.01], [x, y, top], outer / 2, 5))
        supported = interface(gauge, plate, top)
        full = math.pi * ((outer / 2) ** 2 - 25)
        extend = max(0, (outer / 2) - min(y - box(plate)[1], box(plate)[4] - y))
        gauges.append(
            dict(
                outerDiameterMm=outer,
                innerDiameterMm=10,
                idealAreaMm2=full,
                supportedAreaMm2=supported,
                unsupportedAreaMm2=full - supported,
                overhangMm=extend,
            )
        )
    res[side] = {
        "upperPlateBoxMm": box(plate),
        "screwBoxMm": box(screw),
        "nearScrew": near,
        "flatEndContactMm2": interface(screw, plate, top),
        "probeUp025OverlapMm3": overlap(moved(screw, 0.25), plate),
        "probeDown025GapMm": BRepExtrema_DistShapeShape(
            moved(screw, -0.25), plate
        ).Value(),
        "sizingScreens": gauges,
    }
out = {
    "sourceStepSha256": digest(p),
    "solidCount": len(parts),
    "sides": res,
    "scope": "Parked geometry only. Gauges are ideal annuli, not a selected or load-rated bearing. Positive thickness overlap counterchecks whether the observed end faces are merely touching.",
}
target = Path(sys.argv[2])
target.write_text(json.dumps(out, indent=2) + "\n", newline="\n")
print(json.dumps(res["left"], indent=2))
