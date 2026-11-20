"""Issue the display derivative in Autodesk Fusion and inspect the saved archive in a fresh document."""

import hashlib
import importlib.util
import json
from pathlib import Path
import traceback
import time
import adsk
import adsk.core as core
import adsk.fusion as fusion


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_glyph(root, row):
    occurrence = root.occurrences.addNewComponent(core.Matrix3D.create())
    component = occurrence.component
    component.name = row["name"]
    normal = core.Vector3D.create(*row["normal"])
    datum = row["loops"][0][0]
    origin = core.Point3D.create(*(x / 10 for x in datum))
    base = component.yZConstructionPlane if normal.x else component.xZConstructionPlane
    offset = base.geometry.origin.vectorTo(origin).dotProduct(base.geometry.normal)
    plane_input = component.constructionPlanes.createInput()
    plane_input.setByOffset(base, core.ValueInput.createByReal(offset))
    plane = component.constructionPlanes.add(plane_input)
    plane.isLightBulbOn = False
    sketch = component.sketches.addWithoutEdges(plane)
    sketch.name = "1780 ink outline " + row["digit"]
    sketch.isComputeDeferred = True
    for ring in row["loops"]:
        pts = [
            sketch.modelToSketchSpace(core.Point3D.create(*(v / 10 for v in p)))
            for p in ring
        ]
        for i, pt in enumerate(pts):
            sketch.sketchCurves.sketchLines.addByTwoPoints(pt, pts[(i + 1) % len(pts)])
    sketch.isComputeDeferred = False
    selected = [p for p in sketch.profiles if p.profileLoops.count == len(row["loops"])]
    if len(selected) != 1:
        raise ValueError("Ambiguous ink outline " + row["name"])
    extrudes = component.features.extrudeFeatures
    ext = extrudes.createInput(
        selected[0], fusion.FeatureOperations.NewBodyFeatureOperation
    )
    forward = sketch.xDirection.crossProduct(sketch.yDirection).dotProduct(normal) > 0
    ext.setOneSideExtent(
        fusion.DistanceExtentDefinition.create(
            core.ValueInput.createByReal(row["depthMm"] / 10)
        ),
        fusion.ExtentDirections.PositiveExtentDirection
        if forward
        else fusion.ExtentDirections.NegativeExtentDirection,
    )
    extrudes.add(ext).name = "White print relief"
    sketch.isVisible = False
    body = component.bRepBodies.item(0)
    body.name = row["name"]
    body.attributes.add("R26-showcase", "artwork", "original vector 1780")
    return occurrence, body


def capture(app, path):
    view = app.activeViewport
    camera = view.camera
    camera.isSmoothTransition = False
    camera.cameraType = core.CameraTypes.OrthographicCameraType
    camera.eye = core.Point3D.create(148, 128, 100)
    camera.target = core.Point3D.create(0, 0, 29)
    camera.upVector = core.Vector3D.create(0, 0, 1)
    view.camera = camera
    view.fit()
    adsk.doEvents()
    for _ in range(12):
        adsk.doEvents()
        view.refresh()
        time.sleep(0.05)
    outcome = view.saveAsImageFile(str(path), 1500, 1050)
    if not outcome:
        raise ValueError("Fusion viewport capture failed")
    current = view.camera
    return {
        "eyeCm": current.eye.asArray(),
        "targetCm": current.target.asArray(),
        "up": current.upVector.asArray(),
        "viewExtents": current.viewExtents,
        "image": [1500, 1050],
    }


def appearance(body):
    ap = body.appearance
    rgb = None
    for key in ("opaque_albedo", "surface_albedo", "generic_diffuse", "metal_f0"):
        prop = core.ColorProperty.cast(ap.appearanceProperties.itemById(key))
        if prop:
            color = prop.value
            rgb = f"#{color.red:02X}{color.green:02X}{color.blue:02X}"
            break
    return ap.name, rgb


def reveal(design, root, occs):
    design.activateRootComponent()
    root.isBodiesFolderLightBulbOn = True
    counts = {
        "isolated": 0,
        "hiddenOccurrence": 0,
        "disabledBodyFolder": 0,
        "hiddenBody": 0,
    }
    for occ in occs.values():
        if occ.isIsolated:
            occ.isIsolated = False
            counts["isolated"] += 1
    for occ in occs.values():
        comp = occ.component
        if not occ.isLightBulbOn:
            occ.isLightBulbOn = True
            counts["hiddenOccurrence"] += 1
        if not comp.isBodiesFolderLightBulbOn:
            comp.isBodiesFolderLightBulbOn = True
            counts["disabledBodyFolder"] += 1
        for body in comp.bRepBodies:
            if not body.isLightBulbOn:
                body.isLightBulbOn = True
                counts["hiddenBody"] += 1
    for occ in occs.values():
        occ.isLightBulbOn = False
    adsk.doEvents()
    core.Application.get().activeViewport.refresh()
    for occ in occs.values():
        comp = occ.component
        occ.isLightBulbOn = True
        comp.isBodiesFolderLightBulbOn = True
        comp.opacity = 1.0
        for body in comp.bRepBodies:
            body.opacity = 1.0
            body.isLightBulbOn = True
            body.isVisible = True
            proxy = body.createForAssemblyContext(occ)
            proxy.isVisible = True
            proxy.isLightBulbOn = True
    adsk.doEvents()
    return counts


def run(context):
    cfg = json.loads(Path("INPUT_MANIFEST_JSON").read_bytes())
    root_dir = Path(cfg["project"])
    out = root_dir / "cad/showcase-red"
    base = root_dir / "cad/assembly-release/foundation-student.f3d"
    source_sha = "3e11e4f83ad035d1999aae2b6509fbeef82c5b6d410ce6f5c60b6229d819c6c0"
    if digest(base) != source_sha:
        raise ValueError("The issued public foundation source differs")
    numbering = load("r26_numbering", out / "numbering.py")
    colors = load("r26_print_colors", root_dir / "cad/own-zone/fusion.py")
    app = core.Application.get()
    owned = None
    report = {
        "basisSha256": source_sha,
        "documentsBefore": app.documents.count,
        "stage": "opening",
    }
    result = out / "native-reopen.json"

    def save():
        result.write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")

    def open_file(path):
        return app.importManager.importToNewDocument(
            app.importManager.createFusionArchiveImportOptions(str(path))
        )

    def tree(doc):
        design = fusion.Design.cast(doc.products.itemByProductType("DesignProductType"))
        occs = {o.component.name: o for o in design.rootComponent.occurrences}
        return design, design.rootComponent, occs

    try:
        if cfg.get("mode", "issue") == "issue":
            owned = open_file(base)
            design, root, occs = tree(owned)
            if len(occs) != 235:
                raise ValueError("Unexpected public source occurrence inventory")
            palette = {"palette": {"bumper-red": "#C5273D", "bumper-number": "#FFFFFF"}}
            cache = {}
            red = colors.finish(design, palette, "bumper-red", cache)
            white = colors.finish(design, palette, "bumper-number", cache)
            groups = {face: core.ObjectCollection.create() for face in numbering.FACES}
            for name in numbering.COVERS:
                occ = occs[name]
                body = occ.component.bRepBodies.item(0)
                new_name = name.replace(" blue ", " red ")
                occ.component.name = new_name
                body.name = new_name
                body.appearance = red
                for face in body.faces:
                    face.appearance = red
                body.attributes.add("R26-showcase", "foundationSource", name)
            for row in numbering.glyphs():
                report["stage"] = "authoring " + row["name"]
                save()
                mark, body = make_glyph(root, row)
                body.appearance = white
                group = groups[row["face"]]
                if not group.count:
                    group.add(occs[row["sourcePanel"]])
                group.add(mark)
                adsk.doEvents()
            for name, group in groups.items():
                root.rigidGroups.add(group, False).name = (
                    "Attached " + name + " 1780 print"
                )
            reveal(design, root, {o.component.name: o for o in root.occurrences})
            design.computeAll()
            report["stage"] = "exporting"
            save()
            if not design.exportManager.execute(
                design.exportManager.createFusionArchiveExportOptions(
                    str(out / "display.f3d")
                )
            ):
                raise ValueError("Archive export failed")
            owned.close(False)
            owned = None
        if cfg.get("mode") == "reveal":
            owned = open_file(Path(cfg["inputArchive"]))
            design, root, occs = tree(owned)
            report["visibilityRepair"] = reveal(design, root, occs)
            report["stage"] = "exporting visible assembly"
            save()
            adsk.doEvents()
            design.computeAll()
            if not design.exportManager.execute(
                design.exportManager.createFusionArchiveExportOptions(
                    str(out / "display.f3d")
                )
            ):
                raise ValueError("Visible assembly archive export failed")
            owned.close(False)
            owned = None
        report["stage"] = "cold reopening"
        save()
        owned = open_file(out / "display.f3d")
        owned.activate()
        design, root, occs = tree(owned)
        report["coldViewRefresh"] = reveal(design, root, occs)
        if len(occs) != 251:
            raise ValueError("Expected 235 previous components and 16 new digit bodies")
        rows = {}
        for name, occ in sorted(occs.items()):
            comp = occ.component
            if comp.bRepBodies.count != 1:
                raise ValueError("Unexpected body count: " + name)
            body = comp.bRepBodies.item(0)
            ap, rgb = appearance(body)
            rendered = (
                occ.isVisible
                and occ.isLightBulbOn
                and comp.isBodiesFolderLightBulbOn
                and body.isLightBulbOn
            )
            rows[name] = {
                "body": body.name,
                "appearance": ap,
                "rgb": rgb,
                "graphicsVisible": rendered,
            }
            if not rendered:
                raise ValueError("Cold archive still hides " + name)
        for row in numbering.glyphs():
            if rows[row["name"]]["rgb"] != "#FFFFFF":
                raise ValueError("Wrong digit appearance")
        for name in numbering.COVERS:
            if rows[name.replace(" blue ", " red ")]["rgb"] != "#C5273D":
                raise ValueError("Wrong alliance appearance")
        if not design.exportManager.execute(
            design.exportManager.createSTEPExportOptions(str(out / "display.step"))
        ):
            raise ValueError("Cold STEP export failed")
        viewport = Path(cfg["evidenceDirectory"]) / "red-cold-viewport.png"
        report["diagnosticCamera"] = capture(app, viewport)
        report.update(
            stage="verified",
            archiveSha256=digest(out / "display.f3d"),
            stepSha256=digest(out / "display.step"),
            diagnosticViewportSha256=digest(viewport),
            inventory=rows,
            joints=root.joints.count,
            rigidGroups=root.rigidGroups.count,
        )
    except Exception:
        report["failure"] = traceback.format_exc()
    finally:
        if owned:
            owned.close(False)
        report["documentsAfter"] = app.documents.count
        report["restored"] = report["documentsBefore"] == report["documentsAfter"]
        save()
