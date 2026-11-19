"""Render a still and a browser mesh from one project-owned STEP assembly."""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory

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


def render(mesh, image):
    reader = vtk.vtkSTLReader()
    reader.SetFileName(str(mesh))
    reader.Update()
    data = reader.GetOutput()
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(data)
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
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
    count = 0
    while solids.More():
        count += 1
        solids.Next()
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
        writer = StlAPI_Writer()
        writer.ASCIIMode = False
        if not writer.Write(shape, str(mesh)):
            raise ValueError("STL export failed")
        png = folder / "assembly.png"
        mesh_bounds, triangles = render(mesh, png)
        if triangles < 1 or not all(math.isclose(a, b, abs_tol=chord + .001) for a, b in zip(bounds, mesh_bounds)):
            raise ValueError("Mesh bounds disagree with source assembly")
        packed = folder / "assembly.stl.gz"
        packed.write_bytes(gzip.compress(mesh.read_bytes(), compresslevel=6, mtime=0))
        receipt = dict(schema="agent-frc/cad-still@1", source=config["source"],
                       sourceSha256=source_hash, imageSha256=digest(png), meshSha256=digest(packed),
                       solids=count, triangles=triangles, units="mm", nativeBounds=bounds,
                       meshBounds=mesh_bounds, chordMm=chord, angleRad=angle)
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

