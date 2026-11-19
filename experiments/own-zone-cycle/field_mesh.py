"""Extract the selected blue HUB's contact surfaces to a private cache from the pinned FIRST STEP."""

import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from OCP.BRep import BRep_Tool
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDF import TDF_Label
from OCP.TDocStd import TDocStd_Document
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from OCP.collections import Sequence_TDF_Label
from field_register import PIN, name


def triangles(shape, chord=1.0):
    BRepMesh_IncrementalMesh(shape, chord, False, 0.22, False).Perform()
    faces = TopExp_Explorer(shape, TopAbs_FACE)
    while faces.More():
        face = TopoDS.Face(faces.Current())
        loc = TopLoc_Location()
        surface = BRep_Tool.Triangulation_s(face, loc)
        if surface:
            pose = loc.Transformation()
            points = np.array(
                [
                    surface.Node(i).Transformed(pose).Coord()
                    for i in range(1, surface.NbNodes() + 1)
                ]
            )
            indices = (
                np.array(
                    [
                        surface.Triangle(i).Get()
                        for i in range(1, surface.NbTriangles() + 1)
                    ]
                )
                - 1
            )
            if face.Orientation() == TopAbs_REVERSED:
                indices = indices[:, [0, 2, 1]]
            if len(indices):
                yield points[indices]
        faces.Next()


def generate(source, dest):
    if hashlib.sha256(source.read_bytes()).hexdigest() != PIN:
        raise ValueError("Field revision mismatch")
    doc = TDocStd_Document(TCollection_ExtendedString("Field mesh"))
    table = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    reader = STEPCAFControl_Reader()
    reader.SetColorMode(False)
    reader.SetLayerMode(False)
    if reader.ReadFile(str(source)) != IFSelect_RetDone or not reader.Transfer(doc):
        raise ValueError("STEP failed")
    roots = Sequence_TDF_Label()
    table.GetFreeShapes(roots)
    data = {}
    labels = {}

    def visit(label, placement, level, inside=False):
        ident = name(label)
        children = Sequence_TDF_Label()
        table.GetComponents_s(label, children)
        if level == 1 and ident != "GE-26300: Hub <1>":
            return
        inside = inside or "GE-26400:" in ident
        if not len(children):
            selected = (
                ident.startswith(("GE-263", "GE-264"))
                or inside
                and any(
                    n in ident.lower()
                    for n in ["wheel", "sensor", "reflector", "shaft", "roller"]
                )
            )
            if selected:
                shape = table.GetShape_s(label).Moved(placement)
                chunks = list(triangles(shape))
                if chunks:
                    key = str(len(data))
                    data[key] = np.concatenate(chunks).astype("float32")
                    labels[key] = ident
            return
        for c in children:
            ref = TDF_Label()
            if not table.GetReferredShape_s(c, ref):
                ref = c
            visit(ref, placement.Multiplied(table.GetLocation_s(c)), level + 1, inside)

    for root in roots:
        visit(root, TopLoc_Location(), 0)
    if not any("Funnel Side" in v for v in labels.values()):
        raise ValueError("Missing HUB funnel")
    np.savez_compressed(dest, **data, labels=json.dumps(labels))
    print(
        len(data),
        "registered geometries;",
        sum(len(v) for v in data.values()),
        "triangles",
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    generate(a.source, a.output)
