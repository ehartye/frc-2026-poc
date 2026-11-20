"""Passive mast spigot fit, fresh import of the actual four project mast products. Units are mm."""

import hashlib, json, sys, math, copy
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "cad/assembly-release"))
from verify_products import products
from mast_anchors import build
from offline import machine, shape
from shop import rect
from OCP.gp import gp_Trsf, gp_Ax1, gp_Pnt, gp_Dir, gp_Vec
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp

file = root / "cad/assembly-release/foundation-student.step"
scene = products(file)
parts, cuts, _, _ = build()


def volume(sh):
    a = GProp_GProps()
    BRepGProp.VolumeProperties_s(sh, a)
    return abs(a.Mass())


def transform(sh, t):
    return BRepBuilderAPI_Transform(sh, t, False).Shape()


def sample(name, x, y):
    mast = machine(cuts[name], scene[name])
    # Isolate the rectangular working shank; exclude the projecting round rail pilot.
    crop = shape(rect([x - 12, y - 12, 114.81], [x + 12, y + 12, 190.8]))
    rows = []
    for size in (15.98, 15.80):
        variant, _, _, _ = build(spigot_flats=size)
        feats = variant[name + " anchor spigot"]["features"]
        shank = BRepAlgoAPI_Common(machine(feats), crop).Shape()
        for dx, yaw, tilt in [
            (0, 0, 0),
            (0.025, 0, 0),
            (0, 0.15, 0),
            (0, 0, 0.03),
            (0.025, 0.15, 0.03),
        ]:
            t = gp_Trsf()
            t.SetRotation(
                gp_Ax1(gp_Pnt(x, y, 114.8), gp_Dir(0, 0, 1)), math.radians(yaw)
            )
            a = transform(shank, t)
            t.SetRotation(
                gp_Ax1(gp_Pnt(x, y, 114.8), gp_Dir(0, 1, 0)), math.radians(tilt)
            )
            a = transform(a, t)
            t.SetTranslation(gp_Vec(dx, 0, 0))
            a = transform(a, t)
            rows.append(
                dict(
                    spanMm=size,
                    translationMm=dx,
                    yawDeg=yaw,
                    tiltDeg=tilt,
                    overlapMm3=round(volume(BRepAlgoAPI_Common(a, mast).Shape()), 6),
                    gapMm=round(BRepExtrema_DistShapeShape(a, mast).Value(), 7),
                )
            )
    return rows


out = {}
for side, y in [("left", 326), ("right", -326)]:
    for ab, x in [(" mast", -180), (" aft mast", -280)]:
        name = side + ab
        out[name] = sample(name, x, y)
assert len(out) == 4
r = dict(
    sourceStepSha256=hashlib.sha256(file.read_bytes()).hexdigest(),
    recipeSha256=hashlib.sha256(
        (root / "cad/assembly-release/mast_anchors.py").read_bytes()
    ).hexdigest(),
    cases=out,
    scope="Shop-drawing sensitivity. Changes to actual stock cavity, corner radii, coatings, shaft sizing and bore alignment require a receiving/assembly study. This comparison does not establish load capacity.",
)
Path(sys.argv[1]).write_text(json.dumps(r, indent=2) + "\n", encoding="utf8")
for i, a in enumerate(out["left mast"]):
    print(
        a["spanMm"],
        a["translationMm"],
        a["yawDeg"],
        a["tiltDeg"],
        [(v[i]["overlapMm3"], v[i]["gapMm"]) for v in out.values()],
    )
