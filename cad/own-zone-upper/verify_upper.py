"""Match one Fusion-reopened solid per project role and check the registered mechanism space."""

import hashlib
import itertools
import json
import math
import sys
from pathlib import Path
import numpy as np
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS
from prepare_upper import HERE, parts


def bounds(part):
    if part["shape"] == "box":
        return np.array(part["lower"] + part["upper"])
    a, b = np.array(part["start"]), np.array(part["end"])
    n = (b - a) / np.linalg.norm(b - a)
    if part["shape"] == "cylinder":
        r = part["radius"] * np.sqrt(np.maximum(0, 1 - n * n))
    else:
        up = [0, 1, 0] if abs(n[2]) > 0.98 else [0, 0, 1]
        u = np.cross(up, n)
        u = u / np.linalg.norm(u)
        v = np.cross(n, u)
        r = (abs(u) * part["width"] + abs(v) * part["height"]) / 2
    return np.r_[np.minimum(a, b) - r, np.maximum(a, b) + r]


def reopened():
    cfg, items, proxies, sites = parts()
    reader = STEPControl_Reader()
    source = HERE / "own-zone-public.step"
    if reader.ReadFile(str(source)) != IFSelect_RetDone or not reader.TransferRoots():
        raise ValueError("Fusion STEP reopen failed")
    explore = TopExp_Explorer(reader.OneShape(), TopAbs_SOLID)
    pending = items + proxies
    records = []
    while explore.More():
        shape = explore.Current()
        b = Bnd_Box()
        BRepBndLib.AddOptimal_s(shape, b, False, False)
        actual = np.array([*b.CornerMin().Coord(), *b.CornerMax().Coord()])
        matches = [p for p in pending if max(abs(actual - bounds(p))) < 0.001]
        if len(matches) != 1:
            raise ValueError(f"{len(matches)} recipes for source solid {actual}")
        part = matches[0]
        pending.remove(part)
        records.append((shape, part, actual))
        explore.Next()
    if pending:
        raise ValueError("Missing source shapes")
    return records


def main():
    cfg, items, proxies, sites = parts()
    records = reopened()
    solids = [
        {"id": p["name"], "role": p["role"], "boundsMm": np.round(ext, 5).tolist()}
        for _, p, ext in records
    ]
    source = HERE / "own-zone-public.step"
    out = {
        "schema": "agent-frc/assembly-appearances@1",
        "sourceSha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "solids": solids,
    }
    (HERE / "appearances.json").write_text(json.dumps(out, indent=2) + "\n")
    native = json.loads((HERE / "fusion-progress.json").read_bytes())
    assert native["stage"] == "complete" and not native["errors"]
    assert len(native["projectParts"]) == len(items)
    assert len(native["supplierSites"]) == 4 and len(native["extraSupplierSites"]) == 2
    stowed = [ext for _, p, ext in records if p["role"] != "bumper-blue"]
    ext = np.array(stowed)
    assert abs(ext[:, :2].min() + 340) < 0.001 and abs(ext[:, 3:5].max() - 340) < 0.001
    assert ext[:, 5].max() < 740
    r = 150.114 / 2
    # Nominal grid remains inside the CAD hopper; two per layer clear the center deck seam.
    cells = np.array(
        [
            [x, y, z]
            for x, y, z in itertools.product(
                [-251, -97, 57], [-232, -78, 76, 230], [235 + r, 239 + 3 * r]
            )
        ]
    )
    assert (
        len(cells) == 24
        and min(math.dist(a, b) for i, a in enumerate(cells) for b in cells[i + 1 :])
        >= 2 * r
    )
    assert np.all(cells.min(axis=0) - r >= [-330, -311, 235]) and np.all(
        cells.max(axis=0) + r <= [148, 311, 552]
    )
    print(
        f"{len(records)} independently matched solids; {len(items)} native editable parts; {ext[:, 5].max():.2f} mm stowed height; 24 nominal storage slots"
    )


if __name__ == "__main__":
    main()
