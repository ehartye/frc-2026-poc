"""Add an editable lift to the exact issued R2C archive and verify both native sliders on reopen."""

import hashlib
import importlib.util
import json
import traceback
from pathlib import Path

import adsk
import adsk.core as core
import adsk.fusion as fusion


def load_module(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bounds(occ):
    box = occ.preciseBoundingBox
    return [10 * v for v in (*box.minPoint.asArray(), *box.maxPoint.asArray())]


def run(context):
    cfg = json.loads(Path("INPUT_MANIFEST_JSON").read_bytes())
    project, out = Path(cfg["project"]), Path(cfg["output"])
    base = project / "cad/own-zone-upper/own-zone-public.f3d"
    pin = hashlib.sha256(base.read_bytes()).hexdigest()
    if pin != "5bed444ce5dc99caa94e38164be3c5cbfbefa6ed7106d2bb0370cbe1abf16dd3":
        raise RuntimeError("Unexpected base geometry")
    author = load_module("r2c_parts", project / "cad/own-zone/fusion.py")
    colors = load_module(
        "r2c_colors", project / "scripts/component_palette.py"
    ).resolve_palette(project)
    items = json.loads((project / "cad/tower-lift/parts.json").read_bytes())
    stages = {p["name"]: p["stage"] for p in items}
    app = core.Application.get()
    prior, initial = app.activeDocument, app.documents.count
    progress = {"baseSha256": pin, "stage": "open", "rows": []}
    own = None
    archive = out / "tower-l1.f3d"

    def open_file(path):
        m = app.importManager
        return m.importToNewDocument(m.createFusionArchiveImportOptions(str(path)))

    def handles(doc):
        design = fusion.Design.cast(doc.products.itemByProductType("DesignProductType"))
        return design, design.rootComponent

    try:
        own = open_file(base)
        design, root = handles(own)
        if root.occurrences.count != 117:
            raise ValueError("Base inventory differs")
        progress["stage"] = "features"
        palette = {
            name: design.appearances.itemByName("FRC " + name) for name in colors
        }
        palette = {k: v for k, v in palette.items() if v}
        added = {}
        for p in items:
            if p["shape"] != "hook":
                occ = author.build_part(root, design, p, palette, {"palette": colors})
            else:
                occ = root.occurrences.addNewComponent(
                    author.transform(
                        [[1, 0, 0], [0, 0, 1], [0, -1, 0]],
                        [0, p["y"] + p["thickness"], 0],
                    )
                )
                comp = occ.component
                comp.name = p["name"]
                sk = comp.sketches.add(comp.xYConstructionPlane)
                sk.name = "Low-rung crown and capture slot"
                points = [
                    core.Point3D.create(x / 10, z / 10, 0) for x, z in p["profile"]
                ]
                for i, pt in enumerate(points):
                    sk.sketchCurves.sketchLines.addByTwoPoints(
                        pt, points[(i + 1) % len(points)]
                    )
                ext = comp.features.extrudeFeatures.addSimple(
                    sk.profiles.item(0),
                    core.ValueInput.createByString("12 mm"),
                    fusion.FeatureOperations.NewBodyFeatureOperation,
                )
                ext.name = "Hook plate thickness"
                ext.bodies.item(0).name = p["name"]
                ext.bodies.item(0).appearance = author.finish(
                    design, {"palette": colors}, p["role"], palette
                )
            added[p["name"]] = occ
        anchor = next(
            o for o in root.occurrences if o.component.name == "rear perimeter tube"
        )
        anchor.isGrounded = True
        for stage in ("fixed", "elevator", "hooks"):
            members = core.ObjectCollection.create()
            for name, occ in added.items():
                if stages[name] == stage:
                    members.add(occ)
            if stage == "fixed":
                members.add(anchor)
            root.rigidGroups.add(members, False).name = "Tower " + stage
        extension, lift = "Tower rear deployment", "Tower load stroke"
        ori = fusion.JointGeometry.createByPoint(root.originConstructionPoint)
        groups = [
            (
                extension,
                "left extending rail",
                "crosshead lift bridge",
                "XAxisJointDirection",
                0,
                215.0,
            ),
            (
                lift,
                "crosshead lift bridge",
                "left mast",
                "ZAxisJointDirection",
                2,
                115.0,
            ),
        ]
        progress["stage"] = "slider setup"
        signs = {}
        for name, moving, seat, axis, index, stroke in groups:
            params = root.asBuiltJoints.createInput(added[moving], added[seat], ori)
            params.setAsSliderJointMotion(getattr(fusion.JointDirections, axis))
            joint = root.asBuiltJoints.add(params)
            joint.name = name
            member = added[moving]
            old = bounds(member)[index]
            motion = joint.jointMotion
            motion.slideValue = 0.1
            adsk.doEvents()
            delta = bounds(member)[index] - old
            if abs(abs(delta) - 1) > 0.025:
                raise ValueError(f"Unexpected {name} axis change {delta}")
            sign = -1 if delta > 0 else 1
            signs[name] = sign
            motion.slideValue = 0
            adsk.doEvents()
            limits = motion.slideLimits
            limits.minimumValue = min(0, sign * stroke / 10)
            limits.maximumValue = max(0, sign * stroke / 10)
            limits.isMinimumValueEnabled = limits.isMaximumValueEnabled = True
        design.computeAll()
        progress["stage"] = "export"
        exporter = design.exportManager
        if not exporter.execute(
            exporter.createFusionArchiveExportOptions(str(archive))
        ):
            raise RuntimeError("Archive failed")
        own.close(False)
        own = None
        own = open_file(archive)
        design, root = handles(own)
        occs = {o.component.name: o for o in root.occurrences}
        joints = {j.name: j for j in root.asBuiltJoints}
        baseline = {name: bounds(o) for name, o in occs.items()}
        progress["nativeInventory"] = {
            n: {
                "bodies": o.component.bRepBodies.count,
                "extrusions": o.component.features.extrudeFeatures.count,
            }
            for n, o in occs.items()
        }
        for x, z in ((0, 0), (215, 0), (215, 60), (215, 100), (215, 115), (0, 0)):
            joints[extension].jointMotion.slideValue = signs[extension] * x / 10
            joints[lift].jointMotion.slideValue = signs[lift] * z / 10
            adsk.doEvents()
            max_error = 0
            for n, o in occs.items():
                stage = stages.get(n)
                shift = [
                    -x if stage == "hooks" else 0,
                    0,
                    -z if stage in ("hooks", "elevator") else 0,
                ]
                observed = bounds(o)
                max_error = max(
                    max_error,
                    max(
                        abs(v - (baseline[n][i] + shift[i % 3]))
                        for i, v in enumerate(observed)
                    ),
                )
            if max_error > 0.05:
                raise ValueError(f"Motion at {x},{z} differs by {max_error} mm")
            progress["rows"].append(
                dict(
                    deployMm=x,
                    lowerMm=z,
                    maximumBoundsErrorMm=max_error,
                    rightCrownBoundsMm=bounds(occs["right crown hook"]),
                    fixedDatumBoundsMm=bounds(occs["rear perimeter tube"]),
                )
            )
        progress["stage"] = "reopened"
        progress["archiveSha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
        progress["joints"] = {
            name: {"controlSign": signs[name], "travelMm": stroke}
            for name, _, _, _, _, stroke in groups
        }
        inspector = load_module(
            "tower_inspect", project / "cad/tower-lift/inspect_sliders.py"
        )
        verification = inspector.capture(
            joints,
            {extension: [0, -100, -215, 0], lift: [0, -60, -100, -115, 0]},
            progress["nativeInventory"],
            progress["archiveSha256"],
        )
        (out / "student-reopen.json").write_text(
            json.dumps(verification, indent=2) + chr(10),
            encoding="utf8",
            newline=chr(10),
        )
        exp = design.exportManager
        step = out / "tower-l1.step"
        if not exp.execute(exp.createSTEPExportOptions(str(step))):
            raise RuntimeError("Reopened STEP export failed")
        progress["stepSha256"] = hashlib.sha256(step.read_bytes()).hexdigest()
        progress["stage"] = "complete"
    except BaseException:
        progress["error"] = traceback.format_exc()
        raise
    finally:
        if own and own.isValid:
            own.close(False)
        if prior and prior.isValid:
            prior.activate()
        progress["documentsRestored"] = app.documents.count == initial
        (out / "native-reopen.json").write_text(
            json.dumps(progress, indent=2) + "\n", encoding="utf8", newline="\n"
        )
