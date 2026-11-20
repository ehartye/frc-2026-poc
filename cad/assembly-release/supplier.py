"""Survey the exact selected module assembly in the installed world frame without redistributing STEP."""

import hashlib, json, sys
from pathlib import Path
import numpy as np
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box
from OCP.GeomAbs import GeomAbs_Cylinder
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE
from OCP.TopoDS import TopoDS

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "experiments/own-zone-cycle"))
sys.path.insert(0, str(ROOT / "cad/own-zone"))
import field_mesh as fm
from prepare import layout


def content(path, expected):
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError("Supplier archive differs")
    doc = fm.TDocStd_Document(fm.TCollection_ExtendedString("Module geometry"))
    table = fm.XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    reader = fm.STEPCAFControl_Reader()
    reader.SetColorMode(False)
    if reader.ReadFile(str(path)) != fm.IFSelect_RetDone or not reader.Transfer(doc):
        raise ValueError("Cannot read STEP")
    roots = fm.Sequence_TDF_Label()
    table.GetFreeShapes(roots)
    parts = {}

    def visit(label, placement, prefix):
        children = fm.Sequence_TDF_Label()
        table.GetComponents_s(label, children)
        if not len(children):
            parts[prefix] = table.GetShape_s(label).Moved(placement)
            return
        for index, child in enumerate(children):
            ref = fm.TDF_Label()
            if not table.GetReferredShape_s(child, ref):
                ref = child
            visit(
                ref,
                placement.Multiplied(table.GetLocation_s(child)),
                prefix + str(index) + ":" + fm.name(ref) + "/",
            )

    for root in roots:
        visit(root, fm.TopLoc_Location(), "")
    return parts


def bounds(shape):
    bb = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, bb, False, False)
    return [*bb.CornerMin().Coord(), *bb.CornerMax().Coord()]


def faces(shape):
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        face = TopoDS.Face(exp.Current())
        surface = BRepAdaptor_Surface(face)
        exp.Next()
        if surface.GetType() != GeomAbs_Cylinder:
            continue
        cyl = surface.Cylinder()
        p = cyl.Location().Coord()
        axis = cyl.Axis().Direction().Coord()
        if abs(axis[1]) < 0.999 or abs(cyl.Radius() - 2.5) > 0.01:
            continue
        yield dict(
            xzMm=[round(p[0], 4), round(p[2], 4)],
            diaMm=round(2 * cyl.Radius(), 4),
            finiteYmm=[round(bounds(face)[i], 6) for i in [1, 4]],
        )


def build(source):
    cfg, items, _, sites = layout()
    occ = content(source, cfg["swerve"]["sha256"])
    plates = {
        k: sorted(
            (
                f
                for f in faces(s)
                if any(abs(v + 31.75) < 0.01 for v in f["xzMm"])
                and any(abs(v - t) < 0.01 for v in f["xzMm"] for t in (57.15, 82.55))
            ),
            key=lambda f: f["xzMm"],
        )
        for k, s in occ.items()
        if k.startswith(("9:", "10:"))
    }
    # A cylinder can be represented as two half-faces. Count a physical bore once.
    for name, rows in plates.items():
        plates[name] = list(
            {(tuple(f["xzMm"]), tuple(f["finiteYmm"])): f for f in rows}.values()
        )
        if len(plates[name]) != 4:
            raise ValueError("Expected the four selected outer stations per plate")
    if len(plates) != 2:
        raise ValueError("Both physical tab plates must be present")
    data = {}
    for site in sites:
        rot = np.asarray(site["rotation"])
        t = np.asarray(site["translation"])
        out = []
        for name, axes in plates.items():
            for f in axes:
                x, z = f["xzMm"]
                start, end = [
                    (rot @ np.array([x, y, z]) + t).round(6).tolist()
                    for y in f["finiteYmm"]
                ]
                out.append(
                    dict(plate=name, startMm=start, endMm=end, diameterMm=f["diaMm"])
                )
        data[site["name"]] = out
    return dict(
        sourceSha256=cfg["swerve"]["sha256"],
        sourceLeafOccurrences=len(occ),
        sourcePlates=plates,
        registered=data,
    )


if __name__ == "__main__":
    result = build(Path(sys.argv[1]))
    Path(sys.argv[2]).write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf8", newline="\n"
    )
    print(result["sourcePlates"])
