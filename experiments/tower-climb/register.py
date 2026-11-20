"""Measure the two TOWERs from the project-local, kickoff-day FIRST source."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments/own-zone-cycle"))
import field_mesh as fm
import numpy as np


def measure(path):
    if hashlib.sha256(path.read_bytes()).hexdigest() != fm.PIN:
        raise ValueError("Unregistered field edition")
    doc = fm.TDocStd_Document(fm.TCollection_ExtendedString("TOWER bounds"))
    table = fm.XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    reader = fm.STEPCAFControl_Reader()
    reader.SetColorMode(False)
    reader.SetLayerMode(False)
    if reader.ReadFile(str(path)) != fm.IFSelect_RetDone or not reader.Transfer(doc):
        raise ValueError("STEP failed")
    roots = fm.Sequence_TDF_Label()
    table.GetFreeShapes(roots)
    catalog = {"blue": [], "red": []}

    def visit(label, placement, depth):
        name = fm.name(label)
        if depth == 1 and not name.startswith("GE-26500: Tower"):
            return
        children = fm.Sequence_TDF_Label()
        table.GetComponents_s(label, children)
        if not len(children):
            groups = list(fm.triangles(table.GetShape_s(label).Moved(placement)))
            if not groups:
                return
            points = np.concatenate(groups)
            lo, hi = points.min(axis=(0, 1)), points.max(axis=(0, 1))
            side = "blue" if hi[0] < 0 else "red"
            row = {"name": name, "boundsMm": np.r_[lo, hi].round(4).tolist()}
            if "Tower Base Bottom" in name:
                # Include the highest triangle intersecting the outermost 145 mm of the base,
                # over the full lateral span. Conservative with sloping or crossing triangles.
                outward = points[:, :, 0] * (1 if side == "blue" else -1)
                mask = outward.max(axis=1) >= outward.max() - 145
                row["fieldward145mmTopMm"] = float(points[mask, :, 2].max())
            catalog[side].append(row)
        for child in children:
            ref = fm.TDF_Label()
            if not table.GetReferredShape_s(child, ref):
                ref = child
            visit(ref, placement.Multiplied(table.GetLocation_s(child)), depth + 1)

    for root in roots:
        visit(root, fm.TopLoc_Location(), 0)
    result = {"sourceSha256": fm.PIN, "units": "mm", "sides": {}}
    for side, entries in catalog.items():
        parts = [
            r
            for r in entries
            if any(
                tag in r["name"]
                for tag in (
                    "Tower Rung",
                    "Tower Base Bottom",
                    "Tower Upright Outer",
                    "Tower Upright Inner",
                    "Tower Base Angle",
                    "Tower Upright Gusset",
                    "Tower Brace",
                    "Tower Lower Plastic",
                )
            )
        ]
        if sum("Tower Rung" in r["name"] for r in parts) != 3:
            raise ValueError("Expected three rungs")
        result["sides"][side] = parts
    return result


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("field", type=Path)
    cli.add_argument("out", type=Path)
    args = cli.parse_args()
    args.out.write_text(
        json.dumps(measure(args.field), indent=2) + "\n", encoding="utf8", newline="\n"
    )
