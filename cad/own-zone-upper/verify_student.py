"""Compare the exact downloadable Fusion archive's fresh native derivative to the selected public STEP."""

import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from verify_upper import HERE, reopened


def sha(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def geometry(source):
    rows = {}
    for body, role, bounds in reopened(source):
        volume, area = GProp_GProps(), GProp_GProps()
        BRepGProp.VolumeProperties_s(body, volume)
        BRepGProp.SurfaceProperties_s(body, area)
        faces = TopExp_Explorer(body, TopAbs_FACE)
        count = 0
        while faces.More():
            count += 1
            faces.Next()
        rows[role["name"]] = (
            bounds,
            volume.Mass(),
            area.Mass(),
            np.array(volume.CentreOfMass().Coord()),
            count,
        )
    return rows


def verify(folder):
    student = HERE / "own-zone-public.f3d"
    source = HERE / "own-zone-public.step"
    fresh = folder / "verified-student-download.step"
    audit = json.loads((folder / "verified-student-download.json").read_bytes())
    assert (
        audit["sha256"] == sha(student)
        and audit["bytes"] == student.stat().st_size
        and audit["documentCountRestored"]
    )
    previous, current = geometry(source), geometry(fresh)
    assert previous.keys() == current.keys() == audit["components"].keys()
    delta = np.zeros(4)
    for key, (a, v, s, c, faces) in previous.items():
        aa, vv, ss, cc, ff = current[key]
        assert faces == ff
        delta = np.maximum(
            delta,
            [np.abs(a - aa).max(), abs(v - vv), abs(s - ss), np.abs(c - cc).max()],
        )
    assert np.all(delta < np.array([0.00001, 0.01, 0.0001, 0.00001]))
    audit["stepComparison"] = {
        "originalStepSha256": sha(source),
        "independentExportSha256": sha(fresh),
        "matchedNamedSolids": len(current),
        "identicalFaceCounts": True,
        "maximumDelta": {
            "boundsMm": delta[0],
            "volumeMm3": delta[1],
            "areaMm2": delta[2],
            "centroidMm": delta[3],
        },
    }
    (HERE / "student-reopen.json").write_text(
        json.dumps(audit, indent=2) + "\n", encoding="utf8", newline="\n"
    )
    print(len(current), "named solids", delta)


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("folder", type=Path)
    verify(cli.parse_args().folder)
