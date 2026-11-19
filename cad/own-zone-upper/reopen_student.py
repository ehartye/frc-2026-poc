"""Open the exact published F3D and inventory its editable solids in Autodesk Fusion."""

import hashlib
import json
from pathlib import Path
import adsk.core
import adsk.fusion


def run(context):
    cfg = json.loads(Path("INPUT_MANIFEST_JSON").read_bytes())
    source = Path(cfg["source"])
    data = source.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if (
        digest != "5bed444ce5dc99caa94e38164be3c5cbfbefa6ed7106d2bb0370cbe1abf16dd3"
        or len(data) != 964297
    ):
        raise ValueError("Unexpected student archive")
    app = adsk.core.Application.get()
    prior = app.activeDocument
    own = None
    before = app.documents.count
    result = {
        "source": "cad/own-zone-upper/own-zone-public.f3d",
        "sha256": digest,
        "bytes": len(data),
        "opened": False,
    }
    try:
        own = app.importManager.importToNewDocument(
            app.importManager.createFusionArchiveImportOptions(str(source))
        )
        design = adsk.fusion.Design.cast(
            own.products.itemByProductType("DesignProductType")
        )
        features = {}
        for occ in design.rootComponent.occurrences:
            comp = occ.component
            features[comp.name] = {
                "bodies": comp.bRepBodies.count,
                "sketches": comp.sketches.count,
                "extrusions": comp.features.extrudeFeatures.count,
            }
        result["components"] = features
        result["opened"] = True
        if len(features) != 117 or any(
            row["bodies"] != 1 or row["extrusions"] != 1 for row in features.values()
        ):
            raise ValueError("Student geometry or editable feature inventory changed")
        exp = design.exportManager
        if not exp.execute(exp.createSTEPExportOptions(cfg["step"])):
            raise ValueError("Independent student STEP export failed")
    finally:
        if own and own.isValid:
            own.close(False)
        if prior and prior.isValid:
            prior.activate()
        result["documentCountRestored"] = app.documents.count == before
        Path(cfg["result"]).write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf8"
        )
