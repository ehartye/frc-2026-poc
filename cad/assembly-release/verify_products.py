"""Check every named STEP product against the shop design or unchanged native predecessor."""

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDF import TDF_Label
from OCP.collections import Sequence_TDF_Label as TDF_LabelSequence
from OCP.TDocStd import TDocStd_Document
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from OCP.gp import gp_Trsf, gp_Vec
from offline import machine, shape
from reopened_geometry import mass_geometry
from supplier import bounds


def products(path):
    doc = TDocStd_Document(TCollection_ExtendedString("BinXCAF"))
    table = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    reader = STEPCAFControl_Reader()
    if reader.ReadFile(str(path)) != IFSelect_RetDone or not reader.Transfer(doc):
        raise ValueError("STEP import failed")
    labels = TDF_LabelSequence()
    table.GetFreeShapes(labels)
    items = {}

    def visit(label, loc):
        nodes = TDF_LabelSequence()
        table.GetComponents_s(label, nodes)
        if nodes.Length():
            for i in range(1, nodes.Length() + 1):
                occ = nodes.Value(i)
                ref = TDF_Label()
                if not table.GetReferredShape_s(occ, ref):
                    raise ValueError("Missing definition")
                visit(ref, loc.Multiplied(table.GetLocation_s(occ)))
            return
        a = TDataStd_Name()
        if not label.FindAttribute(TDataStd_Name.GetID_s(), a):
            raise ValueError("Unnamed product")
        name = a.Get().ToExtString()
        if name in items:
            raise ValueError("Ambiguous identity " + name)
        items[name] = table.GetShape_s(label).Moved(loc)

    for i in range(1, labels.Length() + 1):
        visit(labels.Value(i), TopLoc_Location())
    return items


def measure(shape_):
    vol, cg = mass_geometry(shape_)
    it = TopExp_Explorer(shape_, TopAbs_SOLID)
    count = 0
    while it.More():
        it.Next()
        count += 1
    return vol, cg, np.array(bounds(shape_)), count


def check(prior, current, recipe):
    issued = products(current)
    expected = products(prior)
    plan = json.loads(recipe.read_bytes())["parts"]
    expected.update({k: machine(v["features"]) for k, v in plan.items()})
    if set(issued) != set(expected):
        raise ValueError(("changed product set", sorted(set(issued) ^ set(expected))))
    rows = {}
    for name, ref in expected.items():
        actual = issued[name]
        v, cg, box, solids = measure(actual)
        refV, refCG, refBox, _ = measure(ref)
        row = dict(
            basis="recipe" if name in plan else "predecessor",
            solids=solids,
            volumeDeltaMm3=float(v - refV),
            centroidDeltaMm=float(np.linalg.norm(cg - refCG)),
            boxDeltaMm=float(np.abs(box - refBox).max()),
        )
        row["pass"] = (
            solids == 1
            and abs(v - refV) <= max(0.02, refV * 1e-5)
            and row["centroidDeltaMm"] <= 0.002
            and row["boxDeltaMm"] <= 0.003
        )
        if name.endswith(" socket screw"):
            shank = plan[name]["features"][0]["shape"]
            x, y, z = shank["a"]
            areas = []
            interference = []
            housing = issued[name.split(" tab ")[0] + " public drive housing"]
            for h in (z + 2.14, z + 56.92):
                sample = shape(
                    {
                        "kind": "box",
                        "lo": [x - 3, y - 3, h - 0.05],
                        "hi": [x + 3, y + 3, h + 0.05],
                    }
                )
                section = BRepAlgoAPI_Common(actual, sample).Shape()
                area = mass_geometry(section)[0] / 0.1
                areas.append(area)
                trial = {}
                for offset in (0.0, 0.04, 0.15):
                    tr = gp_Trsf()
                    tr.SetTranslation(gp_Vec(offset, 0, 0))
                    placed = BRepBuilderAPI_Transform(section, tr, True).Shape()
                    trial[str(offset)] = mass_geometry(
                        BRepAlgoAPI_Common(placed, housing).Shape()
                    )[0]
                interference.append(trial)
            row["tabShankAreaMm2"] = areas
            row["tabToShankOverlapMm3Per0p1mmSlice"] = interference
            row["pass"] &= all(
                abs(a - math.pi * shank["r"] ** 2) < 0.001 for a in areas
            )
            row["pass"] &= all(
                t["0.0"] < 1e-6 and t["0.04"] < 1e-6 and t["0.15"] > 1e-4
                for t in interference
            )
        rows[name] = row
    failed = [k for k, v in rows.items() if not v["pass"]]
    return {
        "basisSha256": hashlib.sha256(prior.read_bytes()).hexdigest(),
        "recipeSha256": hashlib.sha256(recipe.read_bytes()).hexdigest(),
        "stepSha256": hashlib.sha256(current.read_bytes()).hexdigest(),
        "planned": len(plan),
        "inherited": len(rows) - len(plan),
        "failed": failed,
        "products": rows,
    }


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    for arg in ("prior", "current", "recipe", "out"):
        cli.add_argument(arg, type=Path)
    a = cli.parse_args()
    report = check(a.prior, a.current, a.recipe)
    a.out.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf8"
    )
    print(len(report["products"]), "named products,", len(report["failed"]), "failed")
    raise SystemExit(bool(report["failed"]))
