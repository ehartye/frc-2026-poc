"""Reconstruct purchased modules and the two existing scoring motors with exact article hashes.

Keep this native output in the project's ignored artifacts. Start from the issued student archive;
each public package occurrence is removed before inserting authorized supplier geometry.
"""

import hashlib
import json
import math
import traceback
from pathlib import Path
import adsk.core as core
import adsk.fusion as fusion


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def placement(rows, origin):
    mat = core.Matrix3D.create()
    for r in range(3):
        for c in range(3):
            mat.setCell(r, c, rows[r][c])
        mat.setCell(r, 3, origin[r] / 10)
    return mat


def run(context):
    cfg = json.loads(Path("INPUT_MANIFEST_JSON").read_bytes())
    out = Path(cfg["output"])
    src = Path(cfg["supplierDirectory"])
    public = out / "foundation-student.f3d"
    issued = json.loads((out / "foundation-issue-reopen.json").read_bytes())
    if sha(public) != issued["archiveSha256"] or issued["stage"] != "verified":
        raise ValueError("Issue the public archive first")
    geo = json.loads((out / "foundation-products.json").read_bytes())
    if (
        geo["stepSha256"] != issued["stepSha256"]
        or geo["failed"]
        or geo["planned"] + geo["inherited"] != issued["count"]
    ):
        raise ValueError(
            "Verify the geometry of every issued and inherited article before supplier relink."
        )
    job = json.loads((out / "foundation-job.json").read_bytes())
    a = math.radians(60)
    nx = -math.sin(a)
    nz = math.cos(a)
    motors = []
    for side, sg in (("left", 1), ("right", -1)):
        motors.append(
            dict(
                name=side + " scoring motor",
                rotation=[[0, nx, nz], [1, 0, 0], [0, nz, -nx]],
                translation=[238 + (28 - 40.1) * nx, sg * 104, 601 + (28 - 40.1) * nz],
            )
        )
    bundles = [
        (
            "REV-21-3005",
            "REV-21-3005.STEP",
            "11f8381810846a2e52a23dbbe07f8271b314967624eee53f56e59a3ece05c75e",
            job["sites"],
        ),
        (
            "REV-21-1650",
            "REV-21-1650-extracted.step",
            "204eabe42f40b49a117ef9027e18448a8046b4bf985c518eb2bdf57bb4be2a0d",
            motors,
        ),
    ]
    for _, f, d, _sites in bundles:
        if sha(src / f) != d:
            raise ValueError("Supplier geometry mismatch: " + f)
    wanted = {
        s["name"]: (sku, d, placement(s["rotation"], s["translation"]).asArray())
        for sku, f, d, sites in bundles
        for s in sites
    }
    app = core.Application.get()
    prior = app.activeDocument
    before = app.documents.count
    doc = None
    manager = app.importManager
    report = dict(publicSha256=sha(public), sites={}, removed=[])

    def openfile(p):
        return manager.importToNewDocument(
            manager.createFusionArchiveImportOptions(str(p))
        )

    try:
        doc = openfile(public)
        design = fusion.Design.cast(doc.products.itemByProductType("DesignProductType"))
        r = design.rootComponent
        for j in list(r.asBuiltJoints):
            if not j.name.startswith("Tower "):
                j.deleteMe()
        for group in list(r.rigidGroups):
            if not group.name.startswith("Tower "):
                group.deleteMe()
        for o in list(r.occurrences):
            name = o.component.name
            if " public " in name:
                if not o.deleteMe():
                    raise RuntimeError("Proxy removal failed " + name)
                report["removed"].append(name)
        if len(report["removed"]) != 22:
            raise ValueError(report["removed"])
        for sku, f, d, sites in bundles:
            comp = None
            for site in sites:
                mat = placement(site["rotation"], site["translation"])
                if comp is None:
                    occ = r.occurrences.addNewComponent(mat)
                    comp = occ.component
                    comp.name = sku + " authorized supplier shape"
                    if not manager.importToTarget(
                        manager.createSTEPImportOptions(str(src / f)), comp
                    ):
                        raise RuntimeError(sku)
                    comp.attributes.add("R26-supplier", "sourceSha256", d)
                else:
                    occ = r.occurrences.addExistingComponent(comp, mat)
                occ.attributes.add("R26-supplier", "site", site["name"])
        # Registered exact module housings share the welded and bolted chassis datum.
        # Locked purchased internals are an installed-geometry configuration; the public model carries student motion.
        frozen = core.ObjectCollection.create()
        for o in r.occurrences:
            name = o.component.name
            a = o.attributes.itemByName("R26-supplier", "site")
            if (a and wanted[a.value][0] == "REV-21-3005") or (
                name in job["parts"] and job["parts"][name]["stage"] == "fixed"
            ):
                frozen.add(o)
        r.rigidGroups.add(frozen, False).name = "Installed supplier modules and frame"
        output = out / "foundation-supplier.f3d"
        ex = design.exportManager
        if not ex.execute(ex.createFusionArchiveExportOptions(str(output))):
            raise RuntimeError("Private export")
        doc.close(False)
        doc = None
        doc = openfile(output)
        design = fusion.Design.cast(doc.products.itemByProductType("DesignProductType"))
        r = design.rootComponent
        for o in r.occurrences:
            site = o.attributes.itemByName("R26-supplier", "site")
            if not site:
                continue
            sku, pin, expected = wanted[site.value]
            actual = o.transform2.asArray()
            if max(abs(x - y) for x, y in zip(actual, expected)) > 1e-6:
                raise ValueError("Installed transform " + site.value)
            if (
                o.component.attributes.itemByName("R26-supplier", "sourceSha256").value
                != pin
            ):
                raise ValueError(sku)
            if sku == "REV-21-3005" and o.component.allOccurrences.count != 74:
                raise ValueError("Supplier component count")
            box = o.preciseBoundingBox
            report["sites"][site.value] = dict(
                article=sku,
                sourceSha256=pin,
                transform=actual,
                descendants=o.component.allOccurrences.count,
                boundsMm=[
                    round(x * 10, 5)
                    for pt in (box.minPoint, box.maxPoint)
                    for x in pt.asArray()
                ],
            )
        if set(report["sites"]) != set(wanted):
            raise ValueError("Missing purchased articles")
        report["archiveSha256"] = sha(output)
    except:
        report["error"] = traceback.format_exc()
        raise
    finally:
        if doc and doc.isValid:
            doc.close(False)
        if prior and prior.isValid:
            prior.activate()
        report["restored"] = app.documents.count == before
        (out / "foundation-supplier-reopen.json").write_text(
            json.dumps(report, indent=2), encoding="utf8"
        )
