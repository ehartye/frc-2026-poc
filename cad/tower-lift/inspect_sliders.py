"""Capture occurrence one in occurrence two after driving the reopened public Fusion archive."""

import adsk


def capture(joints, commands, inventory, digest):
    observed = {}
    for name, positions in commands.items():
        joint = joints[name]
        one, two = joint.occurrenceOne, joint.occurrenceTwo
        motion = joint.jointMotion
        initial = motion.slideValue
        samples = []
        try:
            for mm in positions:
                motion.slideValue = mm / 10
                adsk.doEvents()
                matrix = two.transform2.copy()
                matrix.invert()
                # Matrix3D.transformBy pre-multiplies: relative = inverse(two) * one.
                relative = one.transform2.copy()
                relative.transformBy(matrix)
                samples.append(
                    dict(
                        position=motion.slideValue * 10,
                        relativeTransform=relative.asArray(),
                    )
                )
        finally:
            motion.slideValue = initial
            adsk.doEvents()
        observed[name] = dict(
            type="slider",
            occurrenceOne=one.component.name,
            occurrenceTwo=two.component.name,
            positionUnit="mm",
            limitMm=[
                motion.slideLimits.minimumValue * 10,
                motion.slideLimits.maximumValue * 10,
            ],
            samples=samples,
        )
    return dict(
        source="cad/tower-lift/tower-l1.f3d",
        sha256=digest,
        opened=True,
        components=inventory,
        joints=observed,
        relativeTransformFrame="occurrenceTwo",
        transformTranslationUnit="cm",
    )
