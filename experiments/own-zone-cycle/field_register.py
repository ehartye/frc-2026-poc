"""Read named purchased or FIRST field assemblies locally. Do not distribute their geometry."""

import argparse
import hashlib
import json
from pathlib import Path
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDF import TDF_Label
from OCP.TDocStd import TDocStd_Document
from OCP.TopLoc import TopLoc_Location
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from OCP.collections import Sequence_TDF_Label

PIN = "2ad90e42f2c2db0fab5b22bb65aa0851089e414d568d4ebd127624fa230c7671"


def name(label):
    attribute = TDataStd_Name()
    return (
        attribute.Get().ToExtString()
        if label.FindAttribute(TDataStd_Name.GetID_s(), attribute)
        else ""
    )


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("source", type=Path)
    cli.add_argument("output", type=Path)
    cli.add_argument(
        "--include-name",
        action="append",
        default=[],
        help="Also register matching named assembly or leaf occurrences",
    )
    args = cli.parse_args()
    if hashlib.sha256(args.source.read_bytes()).hexdigest() != PIN:
        raise ValueError("Field STEP revision differs")
    doc = TDocStd_Document(TCollection_ExtendedString("FRC field"))
    table = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    reader = STEPCAFControl_Reader()
    reader.SetColorMode(False)
    reader.SetLayerMode(False)
    if reader.ReadFile(str(args.source)) != IFSelect_RetDone or not reader.Transfer(
        doc
    ):
        raise ValueError("Field source did not open")
    roots = Sequence_TDF_Label()
    table.GetFreeShapes(roots)
    inventory = []

    def visit(label, placement, stack):
        children = Sequence_TDF_Label()
        table.GetComponents_s(label, children)
        ident = name(label)
        chain = stack + [ident]
        wanted = (
            "GE-26300: Hub",
            "Fuel Counter",
            "Counting Sensor",
            "Sensor Reflector",
            "GE-26329: Hub Funnel Side",
            "GE-26407: Inlet Funnel",
            "GE-26900: Fuel",
            "Carpet",
        )
        if any(k.lower() in ident.lower() for k in (*wanted, *args.include_name)):
            shape = table.GetShape_s(label).Moved(placement)
            bounds = Bnd_Box()
            BRepBndLib.AddOptimal_s(shape, bounds, False, False)
            t = placement.Transformation()
            inventory.append(
                {
                    "name": ident,
                    "path": chain,
                    "boundsMm": [
                        round(v, 3)
                        for v in (
                            *bounds.CornerMin().Coord(),
                            *bounds.CornerMax().Coord(),
                        )
                    ],
                    "transform": [
                        [round(t.Value(i, j), 9) for j in (1, 2, 3, 4)]
                        for i in (1, 2, 3)
                    ],
                }
            )
        for child in children:
            target = TDF_Label()
            if not table.GetReferredShape_s(child, target):
                target = child
            loc = placement.Multiplied(table.GetLocation_s(child))
            visit(target, loc, chain)

    for root in roots:
        visit(root, TopLoc_Location(), [])
    args.output.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf8")
    from collections import Counter

    print(Counter(row["name"] for row in inventory))


if __name__ == "__main__":
    main()
