"""Create dimensioned native stock sketches and machining features in the owning occurrence."""

import math
import adsk.core as core
import adsk.fusion as fusion


def dot(a, b):
    return sum(u * v for u, v in zip(a, b))


def cross(a, b):
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def unit(a):
    return [v / math.sqrt(dot(a, a)) for v in a]


def section(s):
    if s["kind"] == "profile":
        return s["points"], s["holes"], s["delta"]
    if s["kind"] == "round":
        delta = [z - y for y, z in zip(s["a"], s["b"])]
        circles = [dict(center=s["a"], r=s["r"])]
        if s.get("inner", 0):
            circles.append(dict(center=s["a"], r=s["inner"]))
        return [], circles, delta
    x, y, z = s["lo"]
    u, v, w = s["hi"]
    return [[x, y, z], [u, y, z], [u, v, z], [x, v, z]], [], [0, 0, w - z]


def build(occ, features, after_feature=None):
    comp = occ.component
    inverse = occ.transform2.copy()
    inverse.invert()

    def local(p):
        pt = core.Point3D.create(*(x / 10 for x in p))
        pt.transformBy(inverse)
        return pt

    for i, feat in enumerate(features):
        points, circles, delta = section(feat["shape"])
        p0 = points[0] if points else circles[0]["center"]
        localorigin = local(p0)
        normal = core.Vector3D.create(*delta)
        normal.transformBy(inverse)
        normal.normalize()
        planes = [
            comp.xYConstructionPlane,
            comp.yZConstructionPlane,
            comp.xZConstructionPlane,
        ]
        base = next(
            (
                p
                for p in planes
                if abs(p.geometry.normal.dotProduct(normal)) > 0.9999999
            ),
            None,
        )
        if base is None:
            # Intersection of the desired plane and the component XY plane defines the rotation line.
            n = normal.asArray()
            q = localorigin.asArray()
            den = n[0] ** 2 + n[1] ** 2
            d = dot(n, q)
            c = [d * n[0] / den, d * n[1] / den, 0]
            axis = unit(cross([0, 0, 1], n))
            assist = comp.sketches.add(comp.xYConstructionPlane)
            assist.name = "Machining plane axis"
            line = assist.sketchCurves.sketchLines.addByTwoPoints(
                core.Point3D.create(*c),
                core.Point3D.create(*(v + z for v, z in zip(c, axis))),
            )
            angle = math.acos(max(-1, min(1, n[2])))
            inp = comp.constructionPlanes.createInput()
            inp.setByAngle(
                line, core.ValueInput.createByReal(angle), comp.xYConstructionPlane
            )
            base = comp.constructionPlanes.add(inp)
            if abs(base.geometry.normal.dotProduct(normal)) < 0.9999999:
                base.deleteMe()
                inp = comp.constructionPlanes.createInput()
                inp.setByAngle(
                    line, core.ValueInput.createByReal(-angle), comp.xYConstructionPlane
                )
                base = comp.constructionPlanes.add(inp)
            assist.isVisible = False
            base.isLightBulbOn = False
        off = base.geometry.origin.vectorTo(localorigin).dotProduct(
            base.geometry.normal
        )
        if abs(off) > 1e-7:
            inp = comp.constructionPlanes.createInput()
            inp.setByOffset(base, core.ValueInput.createByReal(off))
            plane = comp.constructionPlanes.add(inp)
            plane.isLightBulbOn = False
        else:
            plane = base
        sk = comp.sketches.addWithoutEdges(plane)
        sk.name = feat.get("label", feat["op"].title() + " stock profile")
        if points:
            pts = [sk.modelToSketchSpace(local(p)) for p in points]
            for j, pt in enumerate(pts):
                sk.sketchCurves.sketchLines.addByTwoPoints(pt, pts[(j + 1) % len(pts)])
        for c in circles:
            sk.sketchCurves.sketchCircles.addByCenterRadius(
                sk.modelToSketchSpace(local(c["center"])), c["r"] / 10
            )
        profile = max(list(sk.profiles), key=lambda p: p.profileLoops.count)
        # A construction plane may use the reverse normal to the requested extrusion.
        world_normal = sk.xDirection.crossProduct(sk.yDirection)
        sign = 1 if world_normal.dotProduct(normal) > 0 else -1
        length = math.sqrt(dot(delta, delta)) / 10 * sign
        operation = {
            "new": fusion.FeatureOperations.NewBodyFeatureOperation,
            "cut": fusion.FeatureOperations.CutFeatureOperation,
            "join": fusion.FeatureOperations.JoinFeatureOperation,
        }[feat["op"]]
        extrudes = comp.features.extrudeFeatures
        setup = extrudes.createInput(profile, operation)
        magnitude = core.ValueInput.createByReal(abs(length))
        setup.setOneSideExtent(
            fusion.DistanceExtentDefinition.create(magnitude),
            fusion.ExtentDirections.PositiveExtentDirection
            if length > 0
            else fusion.ExtentDirections.NegativeExtentDirection,
        )
        if feat["op"] == "cut":
            if comp.bRepBodies.count != 1:
                raise ValueError("Machining requires one target in " + comp.name)
            setup.participantBodies = [comp.bRepBodies.item(0)]
        ext = extrudes.add(setup)
        ext.name = feat.get("label", feat["op"].title() + " " + str(i + 1))
        sk.isVisible = False
        if after_feature is not None:
            after_feature()
    if comp.bRepBodies.count != 1:
        raise RuntimeError("Expected one physical body for " + comp.name)
    return comp.bRepBodies.item(0)
