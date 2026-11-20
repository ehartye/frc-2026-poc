"""Package the passive brake downstream of reduction, using a belt and an offset shaft.
All dimensions are examples in mm unless taken from the item named in the receipt."""

import sys, math, json, hashlib
from pathlib import Path
import numpy as np
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Fuse, BRepAlgoAPI_Cut
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.gp import gp_Trsf, gp_Vec
from OCP.BRep import BRep_Builder
from OCP.TopoDS import TopoDS_Compound
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

here = Path(__file__).resolve().parent
root = here.parents[2]
sys.path.insert(0, str(root / "cad/assembly-release"))
sys.path.insert(0, str(root / "cad/tower-lift"))
from verify_products import products
from offline import shape
from shop import rect, round_stock, contour, hexagon
from recipe import parts as tower_parts


def cylinder(x, y, z0, z1, r, inner=0):
    return shape(round_stock((x, y, z0), (x, y, z1), r, inner))


def box(x0, y0, z0, x1, y1, z1):
    return shape(rect((min(x0, x1), min(y0, y1), z0), (max(x0, x1), max(y0, y1), z1)))


def cut(a, b):
    return BRepAlgoAPI_Cut(a, b).Shape()


def fuse(a, b):
    return BRepAlgoAPI_Fuse(a, b).Shape()


def volume(a):
    g = GProp_GProps()
    BRepGProp.VolumeProperties_s(a, g)
    return abs(g.Mass())


def common(a, b):
    return volume(BRepAlgoAPI_Common(a, b).Shape())


def bounds(a):
    b = Bnd_Box()
    BRepBndLib.AddOptimal_s(a, b, False, False)
    return np.array(b.CornerMin().Coord() + b.CornerMax().Coord())


def gap(a, b):
    return np.linalg.norm(
        np.maximum.reduce([np.zeros(3), a[:3] - b[3:], b[:3] - a[3:]])
    )


def move(s, v):
    t = gp_Trsf()
    t.SetTranslation(gp_Vec(*v))
    return BRepBuilderAPI_Transform(s, t, False).Shape()


def distance(a, b):
    return BRepExtrema_DistShapeShape(a, b).Value()


def sweep(a, b, ba, bb, start, end):
    lower = gap(
        np.r_[ba[:3] + np.minimum(start, end), ba[3:] + np.maximum(start, end)], bb
    )
    if lower > 2.5:
        return lower
    mid = (start + end) / 2
    half = np.linalg.norm(end - start) / 2
    sep = distance(move(a, mid), b)
    if sep < 0.0001:
        return 0.0
    if sep - half > 0.15 or half < 0.01:
        return max(0.0, sep - half)
    return min(sweep(a, b, ba, bb, start, mid), sweep(a, b, ba, bb, mid, end))


def capsule(x1, y1, x2, y2, r, z0, z1):
    dx, dy = x2 - x1, y2 - y1
    k = r / math.hypot(dx, dy)
    ox, oy = -k * dy, k * dx
    points = [
        (x1 + ox, y1 + oy, z0),
        (x2 + ox, y2 + oy, z0),
        (x2 - ox, y2 - oy, z0),
        (x1 - ox, y1 - oy, z0),
    ]
    core = shape(contour(points, [0, 0, z1 - z0]))
    return fuse(fuse(core, cylinder(x1, y1, z0, z1, r)), cylinder(x2, y2, z0, z1, r))


source = root / "cad/assembly-release/foundation-student.step"
native = products(source)
stage = {p["name"]: p["stage"] for p in tower_parts() if p["stage"] != "fixed"}
writer = STEPControl_Writer()
builder = BRep_Builder()
assembly = TopoDS_Compound()
builder.MakeCompound(assembly)
out = {
    "sourceHash": hashlib.sha256(source.read_bytes()).hexdigest(),
    "stageCount": len(stage),
    "sides": {},
}
for sign, side in [(1, "left"), (-1, "right")]:
    sx, sy = -240, 305 * sign
    center = (213 - 16 * 3) / 2
    bx, by = sx - math.sqrt(center**2 - 28**2), sign * 277
    rPitch = 16 * 3 / (2 * math.pi)
    c0, c1 = 577.5, 587.3

    def cy(x, y, z0, z1, r, inner=0):
        return cylinder(x, y, z0, z1, r, inner)

    def pulley(x, y):
        # Maximal flange envelope over the entire toothed interval; actual tooth profile and thin flanges are inside.
        return fuse(cy(x, y, c0, c1, 9, 3), cy(x, y, c1, c0 + 17.5, 5, 3))

    belt = cut(
        capsule(sx, sy, bx, by, rPitch + 2.5, 579.4, 585.4),
        capsule(sx, sy, bx, by, rPitch - 2.5, 578, 587),
    )
    brake = cy(bx, by, 602, 632, 19.5)
    # A single machined lower plate with a wing supporting the auxiliary shaft. Retain original plate as its datum.
    lp = side + " lower bearing plate"
    wing = box(bx - 19, sign * 248, 553, -253, sign * 308, 557)
    plate = fuse(native[lp], wing)
    plate = cut(plate, cy(bx, by, 550, 558, 6))
    mount = box(bx - 19, sign * 248, 597.5, bx + 23, sign * 306, 602)
    mount = cut(mount, cy(bx, by, 596, 603, 6))
    design = {
        "belt outer envelope": belt,
        "screw-side pulley": pulley(sx, sy),
        "brake-side pulley": pulley(bx, by),
        "SAB039-30 housing gauge": brake,
        "machined lower plate": plate,
        "brake registration plate blank": mount,
        "auxiliary 6mm shaft gauge": cy(bx, by, 552, 602, 3),
    }
    # Platen spanning brake and lower plate. Bolt pattern on supplier brake still unresolved.
    for idx, (ox, oy) in enumerate([(-12, -22), (16, -21), (-12, 22)]):
        design["bracket pillar " + str(idx)] = cy(
            bx + ox, by + sign * oy, 557, 597.5, 3
        )
    # Relieve the original lower plate where its underside crossed the hopper wall.
    design["machined lower plate"] = cut(
        plate, box(-269, sign * 310, 550, -211, sign * 316, 553.5)
    )
    support = design["machined lower plate"]
    support = fuse(support, box(-301, sign * 312, 554, -159, sign * 322, 557))
    extra_tools = {}
    for mast in (-280, -180):
        aperture = box(mast - 10, sign * 316, 550, mast + 10, sign * 336, 574)
        saddle = cut(
            box(mast - 22, sign * 309, 554, mast + 22, sign * 325.85, 572), aperture
        )
        cap = cut(
            box(mast - 22, sign * 326.15, 554, mast + 22, sign * 339.7, 572), aperture
        )
        support = cut(fuse(support, saddle), aperture)
        for xx in (mast - 16, mast + 16):

            def along(ya, yb, r, inner=0):
                return shape(
                    round_stock((xx, sign * ya, 564), (xx, sign * yb, 564), r, inner)
                )

            support = cut(support, along(308, 326, 2.25))
            cap = cut(cap, along(326, 340, 2))  # major-diameter thread envelope
            design[f"M4 clamp fastener at {xx}"] = fuse(
                along(305, 309, 3.5), along(309, 339, 2)
            )
            extra_tools[f"clamp driver at {xx}"] = along(265, 308, 2)
        support = cut(
            support, box(mast - 22.1, sign * 325.85, 550, mast + 22.1, sign * 341, 573)
        )
        design[f"split external saddle cap {mast}"] = cap
    support = cut(support, box(-260, sign * 247, 557, -220, sign * 313, 578))
    design["machined lower plate"] = support
    for idx, (ox, oy) in enumerate([(-12, -22), (16, -21), (-12, 22)]):
        xpost, ypost = bx + ox, by + sign * oy
        design["machined lower plate"] = cut(
            fuse(design["machined lower plate"], cy(xpost, ypost, 553, 561, 5)),
            cy(xpost, ypost, 554, 562, 2),
        )
        design["brake registration plate blank"] = cut(
            design["brake registration plate blank"], cy(xpost, ypost, 597, 603, 2.25)
        )
        design["bracket pillar " + str(idx)] = cut(
            fuse(
                shape(hexagon((xpost, ypost, 561), (xpost, ypost, 597.5), 8)),
                cy(xpost, ypost, 555, 561, 2),
            ),
            cy(xpost, ypost, 587.5, 598, 2),
        )
        design["upper pillar screw " + str(idx)] = fuse(
            cy(xpost, ypost, 602, 606, 3.5), cy(xpost, ypost, 590, 602, 2)
        )

    design["lower radial bush envelope"] = cy(bx, by, 553, 557, 6, 3.05)
    design["upper radial bush envelope"] = cy(bx, by, 597.5, 602, 6, 3.05)
    for name in ["machined lower plate", "brake registration plate blank"]:
        design[name] = cut(design[name], cy(bx, by, 550, 604, 6))
    # A cross pin ties each catalog pilot-bored pulley to its own machined 6 mm journal.
    keyedShaft = "lower lead screw journal"
    design[keyedShaft] = fuse(cy(sx, sy, 557, 595.2, 3), cy(sx, sy, 595.2, 727, 5))
    for nm, xpin, ypin, shkey in [
        ("screw-side pulley", sx, sy, keyedShaft),
        ("brake-side pulley", bx, by, "auxiliary 6mm shaft gauge"),
    ]:
        pin = shape(round_stock((xpin - 5, ypin, 591), (xpin + 5, ypin, 591), 1))
        cutter = shape(round_stock((xpin - 6, ypin, 591), (xpin + 6, ypin, 591), 1))
        design[nm] = cut(design[nm], cutter)
        design[shkey] = cut(design[shkey], cutter)
        design["transverse drive pin " + nm] = pin
        extra_tools["pin service punch " + nm] = shape(
            round_stock((xpin - 35, ypin, 591), (xpin - 4.99, ypin, 591), 0.85)
        )
    # Check unrelated installed articles as well as the historical native robot.
    internal = []
    names = list(design)
    for ii, aa in enumerate(names):
        for ab in names[ii + 1 :]:
            if aa == "belt outer envelope" and ab in (
                "screw-side pulley",
                "brake-side pulley",
            ):
                continue
            if gap(bounds(design[aa]), bounds(design[ab])) > 0.001:
                continue
            ov = common(design[aa], design[ab])
            if ov > 0.001:
                internal.append([aa, ab, round(ov, 3)])
    oldcheek = native[side + " crosshead cheek"]
    cheek = cut(cut(oldcheek, cy(sx, sy, 686, 690, 11)), cy(sx, sy, 686, 702, 6.5))
    controls = {}
    # At the end of the registered travel the old cheek intrudes into the pulley flange.
    controls["oldCheekAtEndPulleyOverlapMm3"] = common(
        move(oldcheek, (0, 0, -100)), design["screw-side pulley"]
    )
    controls["relievedCheekAtEndPulleyGapMm"] = distance(
        move(cheek, (0, 0, -100)), design["screw-side pulley"]
    )
    controls["beltMotorGapMm"] = distance(belt, native[side + " lift motor envelope"])
    controls["motorToBrakeGapMm"] = distance(
        brake, native[side + " lift motor envelope"]
    )
    controls["motorToShaftPulleyGapMm"] = distance(
        design["brake-side pulley"], native[side + " lift motor envelope"]
    )
    assert len(stage) == 28
    static = []
    near = []
    worst = []
    ex = {lp, side + " lead screw envelope"}
    for nm, body in design.items():
        solids = TopExp_Explorer(body, TopAbs_SOLID)
        count = 0
        while solids.More():
            assert BRepCheck_Analyzer(solids.Current()).IsValid(), nm
            count += 1
            solids.Next()
        assert count == 1, (nm, count)
        bb = bounds(body)
        builder.Add(assembly, body)
        sweepmin = []
        for n, old in native.items():
            if n in ex:
                continue
            q = cheek if n == side + " crosshead cheek" else old
            a = bounds(q)
            dg = gap(a, bb)
            if n not in stage:
                if dg >= 3:
                    continue
                v = common(body, q)
                if v > 0.001:
                    static.append([nm, n, round(v, 4)])
                else:
                    near.append([nm, n, round(distance(body, q), 3)])
            else:
                v0 = np.zeros(3)
                v1 = np.array([-215.0, 0.0, 0.0]) if stage[n] == "hooks" else v0
                v2 = v1 + np.array([0.0, 0.0, -100.0])
                if nm == keyedShaft and n == side + " driven nut":
                    # Nominal intended thread interface. The upper and lower limits both keep full threaded length in the nut.
                    continue
                val = min(sweep(q, body, a, bb, v0, v1), sweep(q, body, a, bb, v1, v2))
                sweepmin.append((val, n))
        worst.append([nm, *min(sweepmin)])
    # Service access for housing withdrawal and three provisional post drivers, throughout straight pull.
    tools = {"brake withdrawal +65mm": cy(bx, by, 602, 697, 19.5)}
    for idx, (ox, oy) in enumerate([(-12, -22), (16, -21), (-12, 22)]):
        tools["8mm OD pillar driver " + str(idx)] = cy(
            bx + ox, by + sign * oy, 602, 664, 4
        )
    tools.update(extra_tools)
    service = {}
    for n, tool in tools.items():
        collided = []
        closest = (1e8, "")
        b = bounds(tool)
        for nn, old in native.items():
            if nn in ex:
                continue
            d = gap(b, bounds(old))
            if d >= closest[0]:
                continue
            dd = distance(tool, old)
            closest = min(closest, (dd, nn))
            if dd < 0.001 and common(tool, old) > 0.001:
                collided.append(nn)
        keep = []
        for newname, newpart in design.items():
            if n.startswith("brake withdrawal") and newname in (
                "SAB039-30 housing gauge",
                "brake registration plate blank",
                "auxiliary 6mm shaft gauge",
            ):
                continue
            if (
                n.startswith("8mm OD pillar driver")
                and newname == "upper pillar screw " + n.split()[-1]
            ):
                continue
            if (
                n.startswith("clamp driver")
                and newname == "M4 clamp fastener at " + n.split()[-1]
            ):
                continue
            if n.startswith("pin service punch") and newname in (
                "transverse drive pin " + n[len("pin service punch ") :],
            ):
                continue
            if gap(b, bounds(newpart)) > 0.001:
                continue
            ov = common(tool, newpart)
            if ov > 0.001:
                keep.append([newname, round(ov, 4)])
        service[n] = {
            "parkedMinimumMm": closest[0],
            "nearest": closest[1],
            "interference": collided,
            "fixtureObstructions": keep,
        }
    rootContacts = {}
    for mast, label in [(-280, " aft mast"), (-180, " mast")]:
        old = native[side + label]
        rootContacts[str(mast)] = {
            "originalLowerPlateGapMm": distance(native[lp], old),
            "newLowerSaddleGapMm": distance(support, old),
            "newExternalCapGapMm": distance(
                design[f"split external saddle cap {mast}"], old
            ),
        }
    builder.Add(assembly, cheek)
    out["sides"][side] = {
        "brakeAxisXYmm": [bx, by],
        "axisDistanceMm": center,
        "controls": controls,
        "parkedOverlaps": static,
        "internalOverlaps": internal,
        "rootContacts": rootContacts,
        "nearFixedContacts": near,
        "continuousLiftBoundByArticle": worst,
        "service": service,
        "baseWingRootOverlapWithOriginalMm3": common(wing, native[lp]),
    }
out["scope"] = (
    "Registered park, deploy, 100 mm lift, straight brake removal and provisional post-driver sweeps. Exact native fixed and moving robot products, conservative project-drawn vendor envelopes. Planned lower-plate and screw replacement excluded from old collision roster. Stock pulley has 4 mm pilot, project 6 mm bore. A short keyed or pinned shaft and positively secured pulley joints, the redesigned reducer, brake mounting pattern, bearing fits, fasteners, belt static rating/tensioner/guard, full height, dual-side racking and installed stop rating remain to establish."
)
writer.Transfer(assembly, STEPControl_AsIs)
writer.Write(str(here / "offset-brake-fit.step"))
(here / "offset-brake-fit.json").write_text(json.dumps(out, indent=2) + "\n")
for side, r in out["sides"].items():
    print(
        side,
        r["brakeAxisXYmm"],
        r["controls"],
        r["parkedOverlaps"],
        r["internalOverlaps"],
        r["rootContacts"],
        min(x[1] for x in r["continuousLiftBoundByArticle"]),
        r["service"],
    )
