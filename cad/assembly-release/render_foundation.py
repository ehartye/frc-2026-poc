"""Render only the issued foundation components from the whole reopened STEP to expose the connections."""

import argparse
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from OCP.BRepMesh import BRepMesh_IncrementalMesh

from foundation_job import ROOT
from offline import machine
from reopened_geometry import read
from supplier import bounds


def render(output, still):
    src = output / "foundation-student.step"
    job = json.loads((output / "foundation-job.json").read_bytes())
    solids, binding = read(
        src, {n: machine(row["features"]) for n, row in job["parts"].items()}
    )
    toolkit = ROOT / "scripts/export-showcase-cad.py"
    loader = importlib.util.spec_from_file_location("render_project_step", toolkit)
    f = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(f)
    bodies = []
    rows = []
    for name, solid in solids.items():
        if not BRepMesh_IncrementalMesh(solid, 0.18, False, 0.18, True).IsDone():
            raise ValueError(name)
        bodies.append(solid)
        rows.append(dict(role=job["parts"][name]["role"], boundsMm=bounds(solid)))
    with TemporaryDirectory() as temp:
        mesh = Path(temp) / "foundation.stl"
        groups = f.write_colored_stl(bodies, rows, job["palette"], mesh)
        f.render(mesh, still, groups, {"center": "#405F86", "edge": "#142F63"})
    print(binding)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("artifacts", type=Path)
    p.add_argument("still", type=Path)
    a = p.parse_args()
    render(a.artifacts, a.still)
