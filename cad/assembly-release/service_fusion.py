"""Add the installed service hardware to an exact foundation archive and inspect a cold reopen."""

import hashlib
import importlib
import importlib.util
import json
import os
from zipfile import ZipFile
import sys
import traceback
from pathlib import Path

import adsk
import adsk.core as core
import adsk.fusion as fusion


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path, data):
    staged = path.with_suffix(path.suffix + ".tmp")
    with staged.open("w", encoding="utf8", newline="\n") as stream:
        json.dump(data, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    staged.replace(path)


def service_checkpoints(folder, pins):
    for register in sorted(folder.glob("completed-*.json"), reverse=True):
        record = json.loads(register.read_bytes())
        if any(record.get(k) != v for k, v in pins.items()):
            continue
        archive = folder / (register.stem + ".f3d")
        if archive.is_file() and digest(archive) == record["archiveSha256"]:
            return archive, record["completedArticles"]
    return None, 0


def checkpoint(design, root, folder, pins, completed):
    # Distinct filenames retain the last confirmed checkpoint through interruption of
    # a later export. Commit the small register only after flushing the archive.
    stem = f"completed-{completed:03d}"
    temporary = folder / (stem + ".partial.f3d")
    archive = folder / (stem + ".f3d")
    for name, value in {**pins, "completedArticles": completed}.items():
        root.attributes.add("R26-service-checkpoint", name, str(value))
    if not design.exportManager.execute(design.exportManager.createFusionArchiveExportOptions(str(temporary))):
        raise RuntimeError("Checkpoint export failed at " + stem)
    with ZipFile(temporary) as package:
        if not package.namelist() or package.testzip() is not None:
            raise ValueError("Incomplete archive at " + stem)
    with temporary.open("rb+") as stream:
        os.fsync(stream.fileno())
    temporary.replace(archive)
    atomic_json(folder / (stem + ".json"), {**pins, "completedArticles": completed, "archiveSha256": digest(archive)})


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
        atomic_json(out / "service-native.json", report)

    def open_doc(file):
        return app.importManager.importToNewDocument(
            app.importManager.createFusionArchiveImportOptions(str(file))
        )

    try:
        if cfg.get("verifyExisting"):
            if digest(archive) != cfg["verifyExisting"]:
                raise ValueError("Archive to reopen differs")
        else:
            pins = {"sourceSha256": digest(src), "recipeSha256": digest(jobfile)}
            checkpoint_dir = out / "service-checkpoints" / pins["recipeSha256"]
            checkpoint_dir.mkdir(parents=True, exist_ok=True)
            path, completed = service_checkpoints(checkpoint_dir, pins)
            doc = open_doc(path or src)
            design, r, occs = design_tree(doc)
            original = json.loads((folder / "reopened-native.json").read_bytes())
            source_names = {row["occurrence"] for row in original["rows"]}
            processed = list(job["parts"])[:completed]
            if set(occs) != source_names | set(processed) or not occs["rear perimeter tube"].isGrounded:
                raise ValueError("Stored checkpoint articles or foundation ground differ")
            if path:
                for key, val in {**pins, "completedArticles": completed}.items():
                    attr = r.attributes.itemByName("R26-service-checkpoint", key)
                    if not attr or attr.value != str(val):
                        raise ValueError("Cold checkpoint identity " + key)
                for name in processed:
                    comp = occs[name].component
                    if comp.bRepBodies.count != 1:
                        raise ValueError("Cold checkpoint solids " + name)
                    body = comp.bRepBodies.item(0)
                    for key in ("identity", "instance"):
                        attr = body.attributes.itemByName("R26-service", key)
                        if not attr or attr.value != job["parts"][name][key]:
                            raise ValueError("Cold checkpoint " + key + " " + name)
                    if body.material.name != job["parts"][name]["material"]:
                        raise ValueError("Cold checkpoint material " + name)
            report["resumedFromArticle"] = completed
            interval = int(cfg.get("checkpointEvery", 18))
            if interval <= 0:
                raise ValueError("checkpointEvery must be positive")
            close_every = int(cfg.get("closeEveryArticles", 0))
            if close_every < 0 or close_every % interval:
                raise ValueError("closeEveryArticles must be a nonnegative multiple of checkpointEvery")
            pause_file = out / "pause-service-after-checkpoint"
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
                if i <= completed:
                    continue
                report.update(stage="machining", index=i, article=name)
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
                body = machining.build(occ, operations, after_feature=adsk.doEvents)
                body.name = name
                body.material = physical(materials, design, row)
                body.appearance = colors.finish(design, job, row["role"], cache)
                body.attributes.add("R26-service", "identity", row["identity"])
                body.attributes.add("R26-service", "instance", row["instance"])
                if i == 4 or i % interval == 0 or i == len(job["parts"]):
                    checkpoint(design, r, checkpoint_dir, pins, i)
                    report["completedArticles"] = i
                    if (cfg.get("closeAtCheckpoint") or pause_file.exists()
                            or (close_every and i % close_every == 0)):
                        report["stage"] = "checkpointed"
                        return
                    save()
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
