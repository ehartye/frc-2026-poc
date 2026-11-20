"""Verify wheel-axis transport by steering, with measured transforms in the grounded chassis."""

import math
import adsk
import adsk.core as core


def check(root, sites, anchor):
    occs = {o.component.name: o for o in root.occurrences}
    joints = {j.name: j.jointMotion for j in root.asBuiltJoints}

    def relative(now, home):
        inverse = home.copy()
        inverse.invert()
        inverse.transformBy(now)
        return inverse

    results = {}
    for site in sites:
        tag = site["name"]
        steerer = joints[tag + " steering"]
        drive = joints[tag + " wheel rotation"]
        wheel = occs[tag + " public wheel"]
        fork = occs[tag + " public turning fork"]
        try:
            steerer.rotationValue = 0
            drive.rotationValue = 0
            adsk.doEvents()
            origin = anchor.transform2.asArray()
            center = core.Point3D.create(*(v / 10 for v in site["translation"]))
            axle = core.Vector3D.create(*(r[0] for r in site["rotation"]))
            wf0 = wheel.transform2.copy()
            ff0 = fork.transform2.copy()
            steerer.rotationValue = 0.63
            adsk.doEvents()
            rotFork = relative(fork.transform2, ff0)
            axle.transformBy(rotFork)
            w0 = wheel.transform2.copy()
            drive.rotationValue = 0.80
            adsk.doEvents()
            after = wheel.transform2.copy()
            spin = relative(after, w0)
            axis = core.Vector3D.create(
                spin.getCell(2, 1) - spin.getCell(1, 2),
                spin.getCell(0, 2) - spin.getCell(2, 0),
                spin.getCell(1, 0) - spin.getCell(0, 1),
            )
            axis.normalize()
            direction = abs(axis.dotProduct(axle))
            cp = center.copy()
            cp.transformBy(relative(after, wf0))
            radius = center.distanceTo(cp) * 10
            frameError = max(
                abs(a - b) for a, b in zip(origin, anchor.transform2.asArray())
            )
            if (
                abs(steerer.rotationValue - 0.63) > math.radians(0.05) + 1e-10
                or abs(drive.rotationValue - 0.80) > math.radians(0.05) + 1e-10
                or direction < 0.99999
                or radius > 0.01
                or frameError > 1e-7
            ):
                raise ValueError(
                    (
                        tag,
                        steerer.rotationValue,
                        drive.rotationValue,
                        direction,
                        radius,
                        frameError,
                        axle.asArray(),
                        axis.asArray(),
                    )
                )
            results[tag] = {
                "steeringRad": steerer.rotationValue,
                "wheelRad": drive.rotationValue,
                "expectedAxis": axle.asArray(),
                "measuredAxis": axis.asArray(),
                "signedDot": axis.dotProduct(axle),
                "absoluteDot": direction,
                "centerShiftMm": radius,
                "groundTransformError": frameError,
            }
        finally:
            drive.rotationValue = 0
            steerer.rotationValue = 0
            adsk.doEvents()
    return results
