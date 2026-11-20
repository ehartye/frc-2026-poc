"""Cold-reopen the issued F3D and read very high-accuracy native BRep body material/mass by identity."""

import hashlib, json, traceback
from pathlib import Path
import adsk.core as core
import adsk.fusion as fusion


def run(context):
    cfg = json.loads(Path("INPUT_MANIFEST_JSON").read_bytes())
    out = Path(cfg["output"])
    src = out / "foundation-student.f3d"
    issued = json.loads((out / "foundation-issue-reopen.json").read_bytes())
    pin = hashlib.sha256(src.read_bytes()).hexdigest()
    if issued.get("stage") != "verified" or issued.get("archiveSha256") != pin:
        raise ValueError("Unverified archive")
    app = core.Application.get()
    prior = app.activeDocument
    count = app.documents.count
    doc = None
    report = dict(archiveSha256=pin, rows=[])
    try:
        manager = app.importManager
        doc = manager.importToNewDocument(
            manager.createFusionArchiveImportOptions(str(src))
        )
        design = fusion.Design.cast(doc.products.itemByProductType("DesignProductType"))
        root = design.rootComponent
        occs = {o.component.name: o for o in root.occurrences}
        fixed = root.rigidGroups.itemByName(
            "Installed chassis weldments and module mounts"
        )
        actual = {o.component.name for o in fixed.occurrences}
        recipe = json.loads((out / "foundation-job.json").read_bytes())
        expected = {n for n, row in recipe["parts"].items() if row["stage"] == "fixed"}
        if not occs["rear perimeter tube"].isGrounded or actual != expected:
            raise ValueError(
                "Issued frame has no ground anchor or changed installed members."
            )
        anchor = occs["rear perimeter tube"]
        report["frameGround"] = {
            "grounded": anchor.isGrounded,
            "fixedMembers": sorted(actual),
            "relativeMotion": {},
        }

        def relative(part):
            ground = anchor.transform2.copy()
            ground.invert()
            transform = part.transform2.copy()
            transform.transformBy(ground)
            return transform.asArray()

        joints = {j.name: j for j in root.asBuiltJoints}
        import adsk

        for site in recipe["sites"]:
            tag = site["name"]
            for label, part in (
                ("steering", " public turning fork"),
                ("wheel rotation", " public wheel"),
            ):
                joint = joints[tag + " " + label].jointMotion
                values = []
                base = anchor.transform2.asArray()
                for angle in (0, 0.63, 1.57, 0):
                    joint.rotationValue = angle
                    adsk.doEvents()
                    if (
                        max(
                            abs(a - b)
                            for a, b in zip(base, anchor.transform2.asArray())
                        )
                        > 1e-7
                    ):
                        raise ValueError("Chassis moved")
                    values.append(
                        {
                            "commandRad": angle,
                            "measuredRad": joint.rotationValue,
                            "relativeToFrame": relative(occs[tag + part]),
                        }
                    )
                if (
                    max(
                        abs(a - b)
                        for a, b in zip(
                            values[0]["relativeToFrame"], values[1]["relativeToFrame"]
                        )
                    )
                    < 0.02
                ):
                    raise ValueError("Joint did not articulate relative to frame")
                report["frameGround"]["relativeMotion"][tag + " " + label] = values
        import sys

        sys.path.insert(0, str(Path(cfg["project"]) / "cad/assembly-release"))
        import coupled_motion, importlib

        check = importlib.reload(coupled_motion).check
        report["compoundMotion"] = check(root, recipe["sites"], anchor)
        for o in root.occurrences:
            if o.component.bRepBodies.count != 1:
                raise ValueError(o.component.name)
            b = o.component.bRepBodies.item(0)
            p = b.getPhysicalProperties(
                fusion.CalculationAccuracy.VeryHighCalculationAccuracy
            )
            identity = b.attributes.itemByName("R26-foundation", "identity")
            owner = b.attributes.itemByName("R26-foundation", "instance")
            report["rows"].append(
                dict(
                    occurrence=o.component.name,
                    body=b.name,
                    identity=identity.value if identity else None,
                    instance=owner.value if owner else None,
                    materialId=b.material.id,
                    material=b.material.name,
                    volumeCm3=p.volume,
                    massKg=p.mass,
                    accuracy=p.accuracy,
                )
            )
        report["count"] = len(report["rows"])
    except:
        report["error"] = traceback.format_exc()
        raise
    finally:
        if doc and doc.isValid:
            doc.close(False)
        if prior and prior.isValid:
            prior.activate()
        report["restored"] = app.documents.count == count
        (out / "foundation-cold-mass.json").write_text(
            json.dumps(report, indent=2), encoding="utf8"
        )
