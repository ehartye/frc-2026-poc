"""Identify native materials, mass, editability and assembly constraints of the issued robot."""

import hashlib, json, traceback
from pathlib import Path

import adsk.core as core
import adsk.fusion as fusion


def run(context):
    cfg = json.loads(Path("INPUT_MANIFEST_JSON").read_bytes())
    root = Path(cfg["project"])
    out = Path(cfg["output"])
    src = root / "cad/tower-lift/tower-l1.f3d"
    app = core.Application.get()
    previous = app.activeDocument
    before = app.documents.count
    own = None
    report = {
        "source": "cad/tower-lift/tower-l1.f3d",
        "sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
        "components": {},
    }
    try:
        manager = app.importManager
        own = manager.importToNewDocument(
            manager.createFusionArchiveImportOptions(str(src))
        )
        design = fusion.Design.cast(own.products.itemByProductType("DesignProductType"))
        r = design.rootComponent
        for occ in r.occurrences:
            c = occ.component
            b = c.bRepBodies.item(0)
            pp = b.physicalProperties
            material = b.material or c.material
            report["components"][c.name] = {
                "material": material.name if material else None,
                "massKg": pp.mass,
                "volumeCm3": pp.volume,
                "body": b.name,
                "grounded": occ.isGrounded,
                "features": c.features.count,
            }
        report["rigidGroups"] = {
            g.name: [o.component.name for o in g.occurrences] for g in r.rigidGroups
        }
        report["joints"] = [j.name for j in r.asBuiltJoints]
        report["libraries"] = {
            lib.name: [m.name for m in lib.materials]
            for lib in app.materialLibraries
            if lib.materials.count
        }
    except Exception:
        report["error"] = traceback.format_exc()
        raise
    finally:
        if own and own.isValid:
            own.close(False)
        if previous and previous.isValid:
            previous.activate()
        report["restored"] = before == app.documents.count
        (out / "baseline.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf8", newline="\n"
        )
