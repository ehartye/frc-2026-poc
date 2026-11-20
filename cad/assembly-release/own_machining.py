"""Repair an existing foundation timeline, restricting every machining cut to its own stock."""

import hashlib
import json
import traceback
from pathlib import Path

import adsk.core as core
import adsk.fusion as fusion


def run(context):
    cfg = json.loads(Path("INPUT_MANIFEST_JSON").read_bytes())
    out = Path(cfg["output"])
    job = json.loads((out / "foundation-job.json").read_bytes())
    src = out / "withdrawn-3b8cf0e4/foundation-student.f3d"
    pin = hashlib.sha256(src.read_bytes()).hexdigest()
    if pin != "3b8cf0e48cd8df83811ff1b87ab938a20006eaf48b7ecdb921362226b83525aa":
        raise ValueError("Expected the withdrawn demonstration")
    app = core.Application.get()
    prior, count, doc = app.activeDocument, app.documents.count, None
    report = {"sourceSha256": pin, "cuts": [], "stage": "import"}

    def checkpoint():
        (out / "owner-machining.json").write_text(
            json.dumps(report, indent=2), encoding="utf8"
        )

    try:
        manager = app.importManager
        doc = manager.importToNewDocument(
            manager.createFusionArchiveImportOptions(str(src))
        )
        d = fusion.Design.cast(doc.products.itemByProductType("DesignProductType"))
        root = d.rootComponent
        plan = job["parts"]
        import re, sys

        sys.path.insert(0, str(Path(cfg["project"]) / "cad/assembly-release"))
        import native_stock
        import importlib

        importlib.reload(native_stock)
        occs = {o.component.name: o for o in root.occurrences}
        boundaries = []
        timeline = {}
        for name, occ in occs.items():
            for feat in occ.component.features.extrudeFeatures:
                i = feat.timelineObject.index
                timeline.setdefault(i, []).append((name, feat.name))
                if name in plan and feat.name == "New 1":
                    boundaries.append((i, name))
        boundaries.sort()
        if len(boundaries) != len(plan):
            raise ValueError("Expected one stock start per article")
        cuts, missing = [], []
        for ix, (first, name) in enumerate(boundaries):
            last = (
                boundaries[ix + 1][0] if ix + 1 < len(boundaries) else d.timeline.count
            )
            got = set()
            for index, group in timeline.items():
                if not first <= index < last:
                    continue
                feature = next(
                    (
                        m
                        for _, n in group
                        if (m := re.match(r"(?:New|Join|Cut) (\d+)", n))
                    ),
                    None,
                )
                if not feature:
                    raise ValueError((index, name, group))
                seq = int(feature[1]) - 1
                got.add(seq)
                if len(group) > 1:
                    if plan[name]["features"][seq]["op"] != "cut":
                        raise ValueError((index, "multi-component join", name))
                    cuts.append((index, name, group))
            for i, f in enumerate(plan[name]["features"]):
                if i not in got:
                    if f["op"] != "cut":
                        raise ValueError((name, i, f))
                    missing.append((name, i, f))
        report["expectedScopeRepairs"] = len(cuts)
        report["expectedRestoredCuts"] = len(missing)
        report["stage"] = "restricting cut participants"
        checkpoint()
        for index, name, group in sorted(cuts):
            feat = d.timeline.item(index).entity
            report["active"] = [index, name]
            if not feat.timelineObject.rollTo(True):
                raise RuntimeError("Timeline failed at " + name)
            comp = occs[name].component
            if comp.bRepBodies.count != 1:
                raise RuntimeError(
                    (name, "stock bodies before cut", comp.bRepBodies.count)
                )
            before = [b.parentComponent.name for b in feat.participantBodies or []]
            feat.participantBodies = [comp.bRepBodies.item(0)]
            report["cuts"].append(dict(index=index, component=name, before=before))
            if len(report["cuts"]) % 5 == 0:
                checkpoint()
        d.timeline.moveToEnd()
        report["stage"] = "restoring omitted shop machining"
        report["restoredCuts"] = []
        checkpoint()
        for name, i, feat in missing:
            native_stock.build(occs[name], [feat])
            report["restoredCuts"].append([name, i])
            if len(report["restoredCuts"]) % 5 == 0:
                checkpoint()
        d.computeAll()
        non_single = {
            o.component.name: o.component.bRepBodies.count
            for o in root.occurrences
            if o.component.bRepBodies.count != 1
        }
        if non_single:
            raise ValueError(("disconnected stock", non_single))
        filename = out / "owner-foundation.f3d"
        export = d.exportManager
        if not export.execute(export.createFusionArchiveExportOptions(str(filename))):
            raise RuntimeError("Corrected F3D export failed")
        doc.close(False)
        doc = manager.importToNewDocument(
            manager.createFusionArchiveImportOptions(str(filename))
        )
        d = fusion.Design.cast(doc.products.itemByProductType("DesignProductType"))
        export = d.exportManager
        step = out / "owner-foundation.step"
        if not export.execute(export.createSTEPExportOptions(str(step))):
            raise RuntimeError("Corrected STEP export failed")
        report["archiveSha256"] = hashlib.sha256(filename.read_bytes()).hexdigest()
        report["stepSha256"] = hashlib.sha256(step.read_bytes()).hexdigest()
        report["stage"] = "exported for independent checks"
    except:
        report["error"] = traceback.format_exc()
        raise
    finally:
        if doc and doc.isValid:
            doc.close(False)
        if prior and prior.isValid:
            prior.activate()
        report["restored"] = app.documents.count == count
        checkpoint()
