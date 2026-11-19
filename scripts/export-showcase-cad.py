"""Render a still and a browser mesh from one project-owned STEP assembly."""
import argparse
import gzip
import hashlib
import json
import math
import struct
from pathlib import Path
from tempfile import TemporaryDirectory

from OCP.BRep import BRep_Builder
from OCP.TopoDS import TopoDS_Compound
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader
from OCP.StlAPI import StlAPI_Writer
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
import vtk


def digest(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def write_stl(shape, path):
    writer = StlAPI_Writer()
    writer.ASCIIMode = False
    if not writer.Write(shape, str(path)):
        raise ValueError("STL export failed")


def write_colored_stl(solids, rows, colors, mesh):
    if len(solids) != len(rows):
        raise ValueError("Solid count differs from the appearance manifest")
    grouped = {}
    builder = BRep_Builder()
    for shape, row in zip(solids, rows):
        if "boundsMm" in row:
            box = Bnd_Box()
            BRepBndLib.AddOptimal_s(shape, box, False, False)
            actual = (*box.CornerMin().Coord(), *box.CornerMax().Coord())
            if any(abs(a - b) > .001 for a, b in zip(actual, row["boundsMm"])):
                raise ValueError(f"Solid bounds disagree with the assignment for {row['id']}")
        group = grouped.get(row["role"])
        if group is None:
            compound = TopoDS_Compound()
            builder.MakeCompound(compound)
            group = grouped[row["role"]] = [compound, 0]
        builder.Add(group[0], shape)
        group[1] += 1
    groups = []
    temp = mesh.with_name("role.stl")
    with mesh.open("wb") as output:
        output.write(bytes(84))
        for role, (compound, count) in grouped.items():
            write_stl(compound, temp)
            part = temp.read_bytes()
            n = struct.unpack_from("<I", part, 80)[0]
            if not n or len(part) != 84 + 50 * n:
                raise ValueError(f"Incomplete role mesh: {role}")
            output.write(memoryview(part)[84:])
            groups.append(dict(role=role, color=colors[role], solids=count, triangles=n,
                               facetsSha256=hashlib.sha256(memoryview(part)[84:]).hexdigest()))
        output.seek(80)
        output.write(struct.pack("<I", sum(g["triangles"] for g in groups)))
    return groups


def set_backdrop(renderer, width, height, colors):
    import numpy as np
    from vtk.util.numpy_support import numpy_to_vtk

    # Match the CSS farthest-corner ellipse in the orbit viewer. VTK starts at bottom left.
    yy, xx = np.ogrid[:height, :width]
    dx = ((xx + .5) / width - .5) / (.5 * math.sqrt(2))
    dy = ((yy + .5) / height - .52) / (.52 * math.sqrt(2))
    blend = np.minimum(1, np.hypot(dx, dy) / .72)[..., None]
    center, edge = [np.array(list(bytes.fromhex(colors[key][1:]))) for key in ("center", "edge")]
    pixels = np.rint(center + blend * (edge - center)).astype(np.uint8)
    background = vtk.vtkImageData()
    background.SetDimensions(width, height, 1)
    background.GetPointData().SetScalars(numpy_to_vtk(pixels.reshape(-1, 3), deep=True))
    texture = vtk.vtkTexture()
    texture.SetInputData(background)
    texture.InterpolateOn()
    renderer.SetBackgroundTexture(texture)
    renderer.TexturedBackgroundOn()


def render(mesh, image, groups=None, backdrop=None):
    reader = vtk.vtkSTLReader()
    reader.SetFileName(str(mesh))
    if groups:
        reader.MergingOff()
    reader.Update()
    data = reader.GetOutput()
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(data)
    if groups:
        import numpy as np
        from vtk.util.numpy_support import numpy_to_vtk

        if data.GetNumberOfCells() != sum(g["triangles"] for g in groups):
            raise ValueError("Rendered mesh lost assigned triangles")
        palette = [list(bytes.fromhex(group["color"][1:])) for group in groups]
        rgb = np.repeat(np.asarray(palette, dtype=np.uint8), [g["triangles"] for g in groups], axis=0)
        data.GetCellData().SetScalars(numpy_to_vtk(rgb, deep=True))
        mapper.SetScalarModeToUseCellData()
        mapper.SetColorModeToDirectScalars()
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    if not groups:
        actor.GetProperty().SetColor(.64, .79, .86)
    actor.GetProperty().SetAmbient(.2)
    actor.GetProperty().SetSpecular(.22)
    renderer = vtk.vtkRenderer()
    renderer.SetBackground(.055, .085, .115)
    renderer.AddActor(actor)
    camera = renderer.GetActiveCamera()
    camera.SetPosition(1.45, -1.8, 1.12)
    camera.SetViewUp(0, 0, 1)
    camera.ParallelProjectionOn()
    window = vtk.vtkRenderWindow()
    window.SetOffScreenRendering(1)
    window.AddRenderer(renderer)
    window.SetSize(1100, 720)
    if backdrop:
        set_backdrop(renderer, 1100, 720, backdrop)
    renderer.ResetCamera()
    # Frame the actual projected geometry including tall and very flat mechanisms.
    camera.OrthogonalizeViewUp()
    renderer.ResetCameraClippingRange()
    window.Render()
    capture = vtk.vtkWindowToImageFilter()
    capture.SetInput(window)
    capture.Update()
    writer = vtk.vtkPNGWriter()
    writer.SetFileName(str(image))
    writer.SetInputConnection(capture.GetOutputPort())
    writer.Write()
    window.Finalize()
    return data.GetBounds(), data.GetNumberOfCells()


def export(root, config, output):
    source = (root / config["source"]).resolve()
    source.relative_to(root)
    source_hash = digest(source)
    reader = STEPControl_Reader()
    if reader.ReadFile(str(source)) != IFSelect_RetDone:
        raise ValueError("Cannot open source STEP")
    if reader.TransferRoots() != reader.NbRootsForTransfer():
        raise ValueError("Incomplete STEP transfer")
    shape = reader.OneShape()
    solids = TopExp_Explorer(shape, TopAbs_SOLID)
    bodies = []
    while solids.More():
        bodies.append(solids.Current())
        solids.Next()
    count = len(bodies)
    if not count:
        raise ValueError("Expected solid geometry")
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    x, y, z = box.CornerMin().Coord()
    xx, yy, zz = box.CornerMax().Coord()
    bounds = [x, xx, y, yy, z, zz]
    chord = 0.18
    angle = 0.18
    if not BRepMesh_IncrementalMesh(shape, chord, False, angle, True).IsDone():
        raise ValueError("Tessellation did not finish")
    output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output) as tmp:
        folder = Path(tmp)
        mesh = folder / "assembly.stl"
        groups = None
        if "appearances" in config:
            from cad_appearances import load_assignments, validated_groups
            rows, colors, appearance = load_assignments(root, config["appearances"], source_hash)
            groups = write_colored_stl(bodies, rows, colors, mesh)
        else:
            write_stl(shape, mesh)
        png = folder / "assembly.png"
        backdrop = None
        if "backdrop" in config:
            from cad_appearances import backdrop_colors
            backdrop = backdrop_colors(config)
        mesh_bounds, triangles = render(mesh, png, groups, backdrop)
        if triangles < 1 or not all(math.isclose(a, b, abs_tol=chord + .001) for a, b in zip(bounds, mesh_bounds)):
            raise ValueError("Mesh bounds disagree with source assembly")
        packed = folder / "assembly.stl.gz"
        packed.write_bytes(gzip.compress(mesh.read_bytes(), compresslevel=6, mtime=0))
        receipt = dict(schema="agent-frc/cad-still@1", source=config["source"],
                       sourceSha256=source_hash, imageSha256=digest(png), meshSha256=digest(packed),
                       solids=count, triangles=triangles, units="mm", nativeBounds=bounds,
                       meshBounds=mesh_bounds, chordMm=chord, angleRad=angle)
        if groups:
            receipt["schema"] = "agent-frc/cad-still@2"
            receipt["appearances"] = {**appearance, "groups": groups}
            validated_groups(root, receipt, packed)
        if backdrop:
            receipt["backdrop"] = backdrop
        if digest(source) != source_hash:
            raise ValueError("Source changed during export")
        for artifact in (packed, png):
            artifact.replace(output / artifact.name)
        record = folder / "receipt.json"
        record.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        record.replace(output / record.name)
        print(f"{count} solids, {triangles} triangles: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    project = args.root.resolve()
    manifest = json.loads((project / "cad-showcase.json").read_text(encoding="utf-8-sig"))
    export(project, manifest, project / "docs" / "robot" / "cad")
