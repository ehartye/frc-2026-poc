"""Render only the issued foundation components from the whole reopened STEP to expose the connections."""

import argparse
import base64
import gzip
import hashlib
import importlib.util
import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from OCP.BRepMesh import BRepMesh_IncrementalMesh

from foundation_job import ROOT
from offline import machine
from reopened_geometry import read
from supplier import bounds


def render(output, still, orbit=None):
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
        backdrop = {"center": "#405F86", "edge": "#142F63"}
        limits, triangles = f.render(mesh, still, groups, backdrop)
        if orbit:
            orbit.mkdir(parents=True, exist_ok=True)
            packed = gzip.compress(mesh.read_bytes(), compresslevel=6, mtime=0)
            layout = {
                "bounds": list(limits),
                "groups": [[g["triangles"], g["color"], g["role"]] for g in groups],
                "backdrop": backdrop,
            }
            receipt = {
                "source": "cad/assembly-release/foundation-student.step",
                "sourceSha256": binding["sourceSha256"],
                "drawnArticles": list(solids),
                "scope": "109 revised foundation articles selected from the 235-product public robot",
                "triangles": triangles,
                "groups": groups,
                "stillSha256": hashlib.sha256(still.read_bytes()).hexdigest(),
                "packedMeshSha256": hashlib.sha256(packed).hexdigest(),
            }
            (orbit / "receipt.json").write_text(
                json.dumps(receipt, indent=2) + "\n", encoding="utf8"
            )
            fields = {
                "title": "Swerve foundation",
                "scope": "Inspect the frame, four student module assemblies and their fasteners. Open the Fusion download to see the 126 inherited robot components alongside this revised foundation.",
                "facts": f"{len(solids)} revised articles · {triangles:,} triangles",
                "bounds": json.dumps(layout),
                "mesh": base64.b64encode(packed).decode("ascii"),
            }
            template = (ROOT / "scripts/cad-orbit.html").read_text(encoding="utf8")
            (orbit / "index.html").write_text(
                re.sub(r"\{\{(\w+)\}\}", lambda m: fields[m[1]], template),
                encoding="utf8",
            )
    print(binding)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("artifacts", type=Path)
    p.add_argument("still", type=Path)
    p.add_argument("--orbit", type=Path)
    a = p.parse_args()
    render(a.artifacts, a.still, a.orbit)
