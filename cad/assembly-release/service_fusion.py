"""Add the installed service hardware to an exact foundation archive and inspect a cold reopen."""

import hashlib
import importlib
import importlib.util
import json
import sys
import traceback
from pathlib import Path

import adsk.core as core
import adsk.fusion as fusion


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def design_tree(doc):
    d = fusion.Design.cast(doc.products.itemByProductType("DesignProductType"))
    root = d.rootComponent
    return d, root, {o.component.name: o for o in root.occurrences}


def physical(materials, design, row):
    spec = row.get("engineeringMaterial")
    if not spec:
        mat = materials.itemByName(row["material"])
        if mat is None:
            raise ValueError("Missing physical stock " + row["material"])
        return mat
    m = design.materials.itemByName(spec["name"])
    if not m:
        base = materials.itemByName(spec["base"])
        if base is None:
            raise ValueError(spec["base"])
        m = design.materials.addByCopy(base, spec["name"])
        for key in ("structural_Density", "thermal_Density"):
            prop = m.materialProperties.itemById(key)
            if prop:
                prop.value = spec["densityKgM3"]
    if (
        abs(
            m.materialProperties.itemById("structural_Density").value
            - spec["densityKgM3"]
        )
        > 0.01
    ):
        raise ValueError("Unregistered density " + spec["name"])
    return m


def run(context):
    cfg = json.loads(Path("INPUT_MANIFEST_JSON").read_bytes())
    project, out = Path(cfg["project"]), Path(cfg["output"])
    jobfile = out / "passive-job.json"
    job = json.loads(jobfile.read_bytes())
    src = project / job["archiveBase"]
    if digest(src) != job["archiveSha256"]:
        raise ValueError("Changed predecessor")
    folder = project / "cad" / "assembly-release"
    sys.path.insert(0, str(folder))
    import native_stock, coupled_motion

    machining = importlib.reload(native_stock)
    motion = importlib.reload(coupled_motion)
    colorspec = importlib.util.spec_from_file_location(
        "service_colors", project / "cad/own-zone/fusion.py"
    )
    colors = importlib.util.module_from_spec(colorspec)
    colorspec.loader.exec_module(colors)
    app = core.Application.get()
    before = app.documents.count
    previous = app.activeDocument
    doc = None
    archive = out / "service-student.f3d"
    step = out / "service-student.step"
    report = dict(
        sourceSha256=digest(src),
        recipeSha256=digest(jobfile),
        stage="starting",
        documentsBefore=before,
    )

    def save():
        (out / "service-native.json").write_text(
            json.dumps(report, indent=2), encoding="utf8"
        )

    def open_doc(file):
        return app.importManager.importToNewDocument(
            app.importManager.createFusionArchiveImportOptions(str(file))
        )

    try:
        if cfg.get("verifyExisting"):
            if digest(archive) != cfg["verifyExisting"]:
                raise ValueError("Archive to reopen differs")
        else:
            doc = open_doc(src)
            design, r, occs = design_tree(doc)
            if len(occs) != 235 or not occs["rear perimeter tube"].isGrounded:
                raise ValueError("Foundation shape or ground changed")
            materials = app.materialLibraries.itemByName(
                "Fusion Material Library"
            ).materials
            cache = {
                k: design.appearances.itemByName("FRC " + k)
                for k in job["palette"]
                if design.appearances.itemByName("FRC " + k)
            }
            for n, row in job["parts"].items():
                # Resolve the entire material inventory before processing any timeline features.
                physical(materials, design, row)
            for i, (name, row) in enumerate(job["parts"].items(), 1):
                report.update(stage="machining", index=i, article=name)
                if i % 3 == 1:
                    save()
                occ = occs.get(name)
                if occ is None:
                    occ = r.occurrences.addNewComponent(core.Matrix3D.create())
                    occ.component.name = name
                    occs[name] = occ
                elif "appendFeatures" not in row:
                    # Preserve earlier corrective timelines. Suppress only the final issued
                    # body of this named occurrence, then author editable replacement stock.
                    comp = occ.component
                    if comp.bRepBodies.count != 1:
                        raise ValueError("Unexpected envelope body count " + name)
                    remove = comp.features.removeFeatures.add(comp.bRepBodies.item(0))
                    remove.name = "Retire predecessor envelope"
                    if comp.bRepBodies.count:
                        raise RuntimeError("Predecessor envelope still present " + name)
                operations = row.get("appendFeatures", row["features"])
                body = machining.build(occ, operations)
                body.name = name
                body.material = physical(materials, design, row)
                body.appearance = colors.finish(design, job, row["role"], cache)
                body.attributes.add("R26-service", "identity", row["identity"])
                body.attributes.add("R26-service", "instance", row["instance"])
            for key, names in job["groups"].items():
                objects = core.ObjectCollection.create()
                for name in names:
                    objects.add(occs[name])
                r.rigidGroups.add(objects, False).name = key
            design.computeAll()
            report["stage"] = "exporting"
            save()
            if not design.exportManager.execute(
                design.exportManager.createFusionArchiveExportOptions(str(archive))
            ):
                raise RuntimeError("Export")
            doc.close(False)
            doc = None
        doc = open_doc(archive)
        design, r, occs = design_tree(doc)
        report.update(
            stage="qualifying", archiveSha256=digest(archive), count=len(occs)
        )
        save()
        groups = {
            g.name: sorted(o.component.name for o in g.occurrences)
            for g in r.rigidGroups
        }
        for key, names in job["groups"].items():
            if groups.get(key) != sorted(names):
                raise ValueError("Native group " + key)
        anchor = occs["rear perimeter tube"]
        if not anchor.isGrounded:
            raise ValueError("Ground lost")
        report["groups"] = groups
        report["joints"] = [j.name for j in r.asBuiltJoints]
        report["coupledWheelMotion"] = motion.check(r, job["sites"], anchor)
        if not design.exportManager.execute(
            design.exportManager.createSTEPExportOptions(str(step))
        ):
            raise RuntimeError("Cold STEP export failed")
        report["stepSha256"] = digest(step)
        rows = {}
        for n, o in occs.items():
            if o.component.bRepBodies.count != 1:
                raise ValueError("Multiple bodies " + n)
            body = o.component.bRepBodies.item(0)
            p = body.getPhysicalProperties(
                fusion.CalculationAccuracy.VeryHighCalculationAccuracy
            )
            m = body.material
            ident = body.attributes.itemByName(
                "R26-service", "identity"
            ) or body.attributes.itemByName("R26-foundation", "identity")
            owner = body.attributes.itemByName(
                "R26-service", "instance"
            ) or body.attributes.itemByName("R26-foundation", "instance")
            wanted = job["parts"].get(n)
            if wanted and (
                not ident
                or ident.value != wanted["identity"]
                or m.name != wanted["material"]
            ):
                raise ValueError("Archive attribute " + n)
            rows[n] = dict(
                identity=ident.value if ident else None,
                instance=owner.value if owner else None,
                material=m.name,
                materialId=m.id,
                volumeCm3=p.volume,
                massKg=p.mass,
                densityKgM3=m.materialProperties.itemById("structural_Density").value,
            )
        report.update(rows=rows, stage="verified", ground=anchor.component.name)
    except:
        report["failure"] = traceback.format_exc()
        raise
    finally:
        if doc and doc.isValid:
            doc.close(False)
        if previous and previous.isValid:
            previous.activate()
        report.update(
            documentsAfter=app.documents.count, restored=app.documents.count == before
        )
        save()
