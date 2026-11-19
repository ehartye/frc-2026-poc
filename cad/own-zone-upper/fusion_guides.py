"""Reopen each prior archive and add the two custody guides as native extrusions."""

import importlib.util
import json
from pathlib import Path
import traceback
import adsk.core as core
import adsk.fusion as fusion


def run(context):
    cfg = json.loads(Path("INPUT_MANIFEST_JSON").read_bytes())
    out = Path(cfg["output"])
    base = Path(cfg["baseline"])
    job = json.loads((out / "native-job.json").read_bytes())
    spec = importlib.util.spec_from_file_location("own_zone_native", cfg["author"])
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    app = core.Application.get()
    prior = app.activeDocument
    own = None
    receipt = json.loads((base / "fusion-progress.json").read_bytes())
    receipt["stage"] = "guides in progress"
    receipt["guideReopens"] = {}
    try:
        for name in ["own-zone-public", "own-zone-supplier"]:
            manager = app.importManager
            own = manager.importToNewDocument(
                manager.createFusionArchiveImportOptions(str(base / (name + ".f3d")))
            )
            design = fusion.Design.cast(
                own.products.itemByProductType("DesignProductType")
            )
            root = design.rootComponent
            colors = {"guide": design.appearances.itemByName("FRC guide")}
            for item in job["items"]:
                if item["name"] in (
                    "rear lift custody gate",
                    "front lift custody guide",
                ):
                    native.build_part(root, design, item, colors, job)
            exporter = design.exportManager
            if name.endswith("public") and not exporter.execute(
                exporter.createSTEPExportOptions(str(out / (name + ".step")))
            ):
                raise RuntimeError("STEP export failed")
            if not exporter.execute(
                exporter.createFusionArchiveExportOptions(str(out / (name + ".f3d")))
            ):
                raise RuntimeError("F3D export failed")
            own.close(False)
            own = None
            own = manager.importToNewDocument(
                manager.createFusionArchiveImportOptions(str(out / (name + ".f3d")))
            )
            design = fusion.Design.cast(
                own.products.itemByProductType("DesignProductType")
            )
            root = design.rootComponent
            parts = {
                c.name: {
                    "bodies": c.bRepBodies.count,
                    "extrusions": c.features.extrudeFeatures.count,
                }
                for c in design.allComponents
                if c.attributes.itemByName("FRC", "source")
            }
            expected = {
                item["name"]
                for item in job["items"]
                + (job["proxies"] if name.endswith("public") else [])
            }
            if set(parts) != expected:
                raise ValueError(
                    "Wrong reopened component set: " + repr(set(parts) ^ expected)
                )
            if name.endswith("supplier"):
                for o in root.occurrences:
                    site = o.attributes.itemByName("FRC", "site")
                    if site:
                        recorded = receipt["supplierSites"][site.value]
                        if (
                            o.component.allOccurrences.count != recorded["descendants"]
                            or max(
                                abs(a - b)
                                for a, b in zip(
                                    o.transform2.asArray(), recorded["transform"]
                                )
                            )
                            > 1e-6
                        ):
                            raise ValueError("Restricted module placement changed")
                receipt["projectParts"] = parts
            receipt["guideReopens"][name] = {
                "projectParts": len(parts),
                "gate": parts["rear lift custody gate"],
                "guide": parts["front lift custody guide"],
            }
            own.close(False)
            own = None
        receipt["stage"] = "complete"
    except:
        receipt["stage"] = "failed"
        receipt["errors"].append(traceback.format_exc())
        raise
    finally:
        (out / "fusion-progress.json").write_text(
            json.dumps(receipt, indent=2), encoding="utf8"
        )
        if own and own.isValid:
            own.close(False)
        if prior and prior.isValid:
            prior.activate()
