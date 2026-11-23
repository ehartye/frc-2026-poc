"""Part lists, display meshes and the record for the trimmed official field fixtures in this folder.

For each fixture in selection.json this reads <id>.step (written by extract.py) and writes:

  <id>.parts.json    every placed leaf part OpenCascade reads with geometry: product path, colour, solid and face counts, and its bounds in the
                     official frame, the project field frame and each docked robot frame of the selection
  <id>.meshes.json   display tessellation in the project field frame, as review-replay fieldBodies
                     (agent-frc/review-replays@1: {name, category, color, mesh: {v, f}})

and official-field.json, the record of the source, hashes, products, official placements and frames.

Usage: python -I -B cad/field/official/tessellate.py [FOLDER]          (needs cadquery-ocp)
"""
import hashlib
import json
import re
import sys
from pathlib import Path

from OCP.Bnd import Bnd_Box
from OCP.BRep import BRep_Tool
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.gp import gp_Trsf
from OCP.IFSelect import IFSelect_RetDone
from OCP.OCP.collections import Sequence_TDF_Label
from OCP.Quantity import Quantity_Color
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDF import TDF_Label
from OCP.TDocStd import TDocStd_Document
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS
from OCP.XCAFDoc import XCAFDoc_ColorGen, XCAFDoc_ColorSurf, XCAFDoc_ColorTool, XCAFDoc_DocumentTool, XCAFDoc_ShapeTool

HERE = Path(__file__).resolve().parent
ST = XCAFDoc_ShapeTool
FACE = getattr(TopoDS, "Face_s", None) or TopoDS.Face


def label_name(label):
    attr = TDataStd_Name()
    return attr.Get().ToExtString() if label.FindAttribute(TDataStd_Name.GetID_s(), attr) else ""


def colour_of(label):
    c = Quantity_Color()
    for kind in (XCAFDoc_ColorSurf, XCAFDoc_ColorGen):
        if XCAFDoc_ColorTool.GetColor_s(label, kind, c):
            return "#%02x%02x%02x" % tuple(round(255 * (v * 12.92 if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055)) for v in (c.Red(), c.Green(), c.Blue()))
    return None


def bounds(shape):
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    return None if box.IsVoid() else [round(v, 3) for v in list(box.CornerMin().Coord()) + list(box.CornerMax().Coord())]


def moved(shape, m):
    """A placed shape taken through a rigid 3x4 matrix."""
    t = gp_Trsf()
    t.SetValues(*[v for row in m for v in row])
    return shape.Moved(TopLoc_Location(t))


def count(shape, what):
    n, explorer = 0, TopExp_Explorer(shape, what)
    while explorer.More():
        n += 1
        explorer.Next()
    return n


def triangles(shape, linear, angular):
    """Vertices and outward triangles of one placed shape."""
    BRepMesh_IncrementalMesh(shape, linear, False, angular, False)
    points, faces, explorer = [], [], TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        face = FACE(explorer.Current())
        location = TopLoc_Location()
        mesh = BRep_Tool.Triangulation_s(face, location)
        if mesh is not None:
            placement, base = location.Transformation(), len(points)
            for i in range(1, mesh.NbNodes() + 1):
                points.append(mesh.Node(i).Transformed(placement).Coord())
            for i in range(1, mesh.NbTriangles() + 1):
                a, b, c = (base + k - 1 for k in mesh.Triangle(i).Get())
                faces.append((a, c, b) if face.Orientation() == TopAbs_REVERSED else (a, b, c))
        explorer.Next()
    return points, faces


def merged(parts):
    """One indexed mesh from several, vertices rounded to 0.01 mm and shared."""
    index, vertices, faces = {}, [], []
    for points, tris in parts:
        local = []
        for p in points:
            key = tuple(round(v, 2) + 0.0 for v in p)
            if key not in index:
                index[key] = len(vertices)
                vertices.append(list(key))
            local.append(index[key])
        for a, b, c in tris:
            a, b, c = local[a], local[b], local[c]
            if a != b and b != c and a != c:
                faces.append([a, b, c])
    return dict(v=vertices, f=faces)


def read(path):
    doc = TDocStd_Document(TCollection_ExtendedString("XCAF"))
    reader = STEPCAFControl_Reader()
    reader.SetColorMode(True)
    reader.SetNameMode(True)
    assert reader.ReadFile(str(path)) == IFSelect_RetDone, f"Could not read {path.name}"
    assert reader.Transfer(doc), f"Could not transfer {path.name}"
    free = Sequence_TDF_Label()
    XCAFDoc_DocumentTool.ShapeTool_s(doc.Main()).GetFreeShapes(free)
    assert free.Length() == 1, f"{path.name}: expected one root product"
    return doc, free.Value(1)


def main():
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE
    sel = json.loads((HERE / "selection.json").read_text(encoding="utf-8"))
    frame, tess = sel["fieldFrame"], sel["tessellation"]
    record = dict(schema=sel["schema"], source=sel["source"], units="mm", officialFrame=sel["officialFrame"], fieldFrame=frame,
                  tessellation=tess, fixtures=[])
    for fx in sel["fixtures"]:
        step_path = folder / f"{fx['id']}.step"
        doc, root = read(step_path)
        root_name = label_name(root)
        skip = re.compile(fx.get("displaySkip", sel.get("displaySkip", "$^")), re.I)
        least = fx.get("displayMinMm", tess.get("displayMinMm", 0.0))
        groups = [(g["id"], g["name"], re.compile(g["match"], re.I), g.get("color"), g.get("minMm", least)) for g in fx["displayGroups"]]
        parts, meshes, tints, placed_products, empty = [], {g[0]: [] for g in groups}, {g[0]: {} for g in groups}, [], {}

        def walk(label, loc, path, inherited):
            own = colour_of(label) or inherited
            kids = Sequence_TDF_Label()
            ST.GetComponents_s(label, kids)
            if kids.Length():
                for i in range(1, kids.Length() + 1):
                    child, ref = kids.Value(i), TDF_Label()
                    if ST.GetReferredShape_s(child, ref):
                        if label == root:
                            placed_products.append(dict(product=label_name(ref), officialTransform=[
                                [round(ST.GetLocation_s(child).Transformation().Value(r, c), 9) for c in range(1, 5)] for r in range(1, 4)]))
                        walk(ref, loc.Multiplied(ST.GetLocation_s(child)), path + [label_name(ref)], colour_of(child) or own)
                return
            placed = ST.GetShape_s(label).Moved(loc)
            b = bounds(placed)
            if b is None:        # a part whose B-rep OpenCascade reads as empty; it stays in the STEP
                empty[path[-1]] = empty.get(path[-1], 0) + 1
                return
            size = max(b[3] - b[0], b[4] - b[1], b[5] - b[2])
            text = " / ".join(path[1:])
            group = None if skip.search(path[-1]) else next((g for g in groups if g[2].search(text)), None)
            group = group if group and size >= group[4] else None
            in_field = moved(placed, frame["matrix"])
            parts.append(dict(path=path, color=own, solids=count(placed, TopAbs_SOLID), faces=count(placed, TopAbs_FACE), boundsOfficialMm=b,
                              boundsFieldMm=bounds(in_field),
                              **({"boundsDockMm": {d["id"]: bounds(moved(placed, d["matrix"])) for d in fx["dockFrames"]}} if fx.get("dockFrames") else {}),
                              display=group[0] if group else None))
            if group:
                meshes[group[0]].append(triangles(in_field, tess["linearDeflectionMm"], tess["angularDeflectionRad"]))
                tints[group[0]][own] = tints[group[0]].get(own, 0) + len(meshes[group[0]][-1][1])

        walk(root, TopLoc_Location(), [root_name], None)
        bodies = {}
        for gid, gname, _, gcolor, _ in groups:
            mesh = merged(meshes[gid])
            assert mesh["f"], f"No geometry for display group {gid}"
            tint = gcolor or max(((k, n) for k, n in tints[gid].items() if k), key=lambda kn: kn[1], default=("#9aa3ad", 0))[0]
            bodies[f"{fx['id']}-{gid}"] = dict(name=gname, category="field", color=tint, mesh=mesh, purpose=fx["purpose"],
                                               rationale=f"FIRST official field model: {', '.join(p['product'] for p in placed_products)}. {sel['source']['edition']}")
        (folder / f"{fx['id']}.meshes.json").write_bytes((json.dumps(dict(
            schema=sel["schema"] + "/meshes", frame=frame["name"], units="mm", fieldBodies=bodies), separators=(",", ":")) + "\n").encode("utf-8"))
        (folder / f"{fx['id']}.parts.json").write_text(json.dumps(dict(
            schema=sel["schema"] + "/parts", fixture=fx["id"], units="mm", parts=parts), separators=(",", ":")).replace('},{"path"', '},\n{"path"') + "\n", encoding="utf-8")
        span = lambda key: [min(p[key][a] for p in parts) for a in range(3)] + [max(p[key][a] for p in parts) for a in range(3, 6)]
        record["fixtures"].append(dict(
            id=fx["id"], purpose=fx["purpose"], step=step_path.name, stepSha256=hashlib.sha256(step_path.read_bytes()).hexdigest(),
            stepBytes=step_path.stat().st_size, rootProduct=root_name, products=placed_products, parts=f"{fx['id']}.parts.json",
            meshes=f"{fx['id']}.meshes.json", leafParts=len(parts), solids=sum(p["solids"] for p in parts), faces=sum(p["faces"] for p in parts),
            displayedParts=sum(1 for p in parts if p["display"]), partsReadEmpty=empty,
            displayBodies={k: dict(color=v["color"], vertices=len(v["mesh"]["v"]), triangles=len(v["mesh"]["f"])) for k, v in bodies.items()},
            boundsOfficialMm=span("boundsOfficialMm"), boundsFieldMm=span("boundsFieldMm"), dockFrames=fx.get("dockFrames", []), notes=fx.get("notes", [])))
        print(fx["id"], len(parts), "leaf parts;", {k: len(v["mesh"]["f"]) for k, v in bodies.items()}, flush=True)
    (folder / "official-field.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
