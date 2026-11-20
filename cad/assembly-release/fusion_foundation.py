"""Author the retained drivetrain on the exact issued T1 and independently reopen the result in Fusion."""

import hashlib
import importlib.util
import json
import sys
import traceback
from pathlib import Path

import adsk
import adsk.core as core
import adsk.fusion as fusion


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run(context):
    cfg = json.loads(Path("INPUT_MANIFEST_JSON").read_bytes())
    project = Path(cfg["project"])
    out = Path(cfg["output"])
    jobfile = out / "foundation-job.json"
    job = json.loads(jobfile.read_bytes())
    sys.path.insert(0, str(project / "cad/assembly-release"))
    import native_stock

    spec = importlib.util.spec_from_file_location(
        "frc_cad_colors", project / "cad/own-zone/fusion.py"
    )
    colors = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(colors)
    plan = job["parts"]
    src = project / job["archiveBase"]
    if digest(src) != job["archiveBaseSha256"]:
        raise ValueError("Archive source mismatch")
    app = core.Application.get()
    prior = app.activeDocument
    count = app.documents.count
    doc = None
    result = {
        "stage": "starting",
        "sourceSha256": digest(src),
        "recipeSha256": digest(jobfile),
        "rows": [],
    }
    filename = out / "foundation-student.f3d"

    def save_status():
        (out / "foundation-issue-reopen.json").write_text(
            json.dumps(result, indent=2), encoding="utf8"
        )

    def openfile(path):
        return app.importManager.importToNewDocument(
            app.importManager.createFusionArchiveImportOptions(str(path))
        )

    def tree(document):
        design = fusion.Design.cast(
            document.products.itemByProductType("DesignProductType")
        )
        return (
            design,
            design.rootComponent,
            {o.component.name: o for o in design.rootComponent.occurrences},
        )

    def rigid(r, groupname, parts):
        m = core.ObjectCollection.create()
        for part in parts:
            m.add(part)
        r.rigidGroups.add(m, False).name = groupname

    def axis_point(r, p):
        setup = r.constructionPlanes.createInput()
        setup.setByOffset(
            r.xYConstructionPlane, core.ValueInput.createByReal(p[2] / 10)
        )
        plane = r.constructionPlanes.add(setup)
        plane.isLightBulbOn = False
        sk = r.sketches.add(plane)
        sk.name = "Module joint datum"
        local = sk.modelToSketchSpace(core.Point3D.create(*(x / 10 for x in p)))
        point = sk.sketchPoints.add(local)
        sk.isVisible = False
        return fusion.JointGeometry.createByPoint(point)

    try:
        doc = openfile(src)
        design, r, old = tree(doc)
        appearances = {
            k: design.appearances.itemByName("FRC " + k)
            for k in job["palette"]
            if design.appearances.itemByName("FRC " + k)
        }
        lib = app.materialLibraries.itemByName("Fusion Material Library")
        for i, (name, row) in enumerate(plan.items()):
            result["stage"] = (
                "machining " + str(i + 1) + " / " + str(len(plan)) + " " + name
            )
            if i % 5 == 0:
                save_status()
            if name in old:
                o = old[name]
                comp = o.component
                stock = comp.features.extrudeFeatures
                while stock.count:
                    if not stock.item(stock.count - 1).deleteMe():
                        raise RuntimeError("Prior stock removal " + name)
            else:
                o = r.occurrences.addNewComponent(core.Matrix3D.create())
                o.component.name = name
            body = native_stock.build(o, row["features"])
            body.name = name
            mat = lib.materials.itemByName(row["material"])
            if mat is None:
                raise RuntimeError("Material unavailable " + row["material"])
            body.material = mat
            body.appearance = colors.finish(design, job, row["role"], appearances)
            for key in ("identity", "instance"):
                body.attributes.add("R26-foundation", key, row[key])
            old[name] = o
        # Bolted and welded frame paths only, both unmodified upper and older tower groups retain their historical qualification.
        installed = [old[k] for k, row in plan.items() if row["stage"] == "fixed"]
        rigid(r, "Installed chassis weldments and module mounts", installed)
        for site in job["sites"]:
            tag = site["name"]
            rigid(
                r,
                tag + " moving axle",
                [old[tag + " public wheel axle"], old[tag + " public turning fork"]],
            )
            p = axis_point(r, site["translation"])
            rot = site["rotation"]
            first = (
                "XAxisJointDirection" if abs(rot[0][0]) > 0.5 else "YAxisJointDirection"
            )
            for label, body, base, axis in (
                (
                    "steering",
                    " public turning fork",
                    " public drive housing",
                    "ZAxisJointDirection",
                ),
                ("wheel rotation", " public wheel", " public wheel axle", first),
            ):
                inp = r.asBuiltJoints.createInput(old[tag + body], old[tag + base], p)
                inp.setAsRevoluteJointMotion(getattr(fusion.JointDirections, axis))
                r.asBuiltJoints.add(inp).name = tag + " " + label
        design.computeAll()
        result["stage"] = "exporting"
        save_status()
        export = design.exportManager
        if not export.execute(export.createFusionArchiveExportOptions(str(filename))):
            raise RuntimeError("F3D export")
        doc.close(False)
        doc = None
        doc = openfile(filename)
        design, r, occs = tree(doc)
        result["stage"] = "qualifying"
        save_status()
        result["archiveSha256"] = digest(filename)
        export = design.exportManager
        step = out / "foundation-student.step"
        if not export.execute(export.createSTEPExportOptions(str(step))):
            raise RuntimeError("STEP export")
        result["stepSha256"] = digest(step)
        for n, o in occs.items():
            b = o.component.bRepBodies.item(0)
            p = b.physicalProperties
            wanted = plan.get(n)
            attr = b.attributes.itemByName("R26-foundation", "identity")
            owner = b.attributes.itemByName("R26-foundation", "instance")
            if wanted and (
                not attr
                or attr.value != wanted["identity"]
                or b.material.name != wanted["material"]
            ):
                raise RuntimeError(n)
            result["rows"].append(
                dict(
                    occurrence=n,
                    body=b.name,
                    identity=attr.value if attr else None,
                    instance=owner.value if owner else None,
                    material=b.material.name,
                    materialId=b.material.id,
                    massKg=p.mass,
                    volumeCm3=p.volume,
                    extrusions=o.component.features.extrudeFeatures.count,
                )
            )
        joints = {j.name: j for j in r.asBuiltJoints}
        result["joints"] = list(joints)
        result["motion"] = {}
        for site in job["sites"]:
            tag = site["name"]
            for label, suffix in (
                ("steering", " public turning fork"),
                ("wheel rotation", " public wheel"),
            ):
                joint = joints[tag + " " + label].jointMotion
                body = occs[tag + suffix]
                values = []
                for angle in (0, 0.63, 1.57, 0):
                    joint.rotationValue = angle
                    adsk.doEvents()
                    values.append(
                        dict(
                            angleRad=joint.rotationValue,
                            transform=body.transform2.asArray(),
                        )
                    )
                if (
                    max(
                        abs(a - b)
                        for a, b in zip(values[0]["transform"], values[1]["transform"])
                    )
                    < 0.02
                ):
                    raise ValueError("Unmoved joint " + tag + label)
                result["motion"][tag + " " + label] = values
        result["count"] = len(occs)
        result["stage"] = "verified"
    except:
        result["error"] = traceback.format_exc()
        raise
    finally:
        if doc and doc.isValid:
            doc.close(False)
        if prior and prior.isValid:
            prior.activate()
        result["restored"] = app.documents.count == count
        save_status()
