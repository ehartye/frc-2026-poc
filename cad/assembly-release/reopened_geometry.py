"""Map native STEP BReps to the portable shop article inventory without trusting file names."""

import hashlib
import numpy as np
from OCP.STEPControl import STEPControl_Reader
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID
from OCP.IFSelect import IFSelect_RetDone
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

from supplier import bounds


def mass_geometry(s):
    prop = GProp_GProps()
    BRepGProp.VolumeProperties_s(s, prop)
    return prop.Mass(), np.array(prop.CentreOfMass().Coord())


def read(path, expected):
    reader = STEPControl_Reader()
    if reader.ReadFile(str(path)) != IFSelect_RetDone or not reader.TransferRoots():
        raise ValueError("Native STEP read failed")
    x = TopExp_Explorer(reader.OneShape(), TopAbs_SOLID)
    dims = {k: np.array(bounds(s)) for k, s in expected.items()}
    picked = {}
    unclaimed = []
    while x.More():
        s = x.Current()
        bb = np.array(bounds(s))
        candidates = [k for k, b in dims.items() if np.max(np.abs(b - bb)) < 0.003]
        if candidates:
            actual, m = mass_geometry(s)
            ranked = []
            for n in candidates:
                v, c = mass_geometry(expected[n])
                ranked.append(
                    (abs(v - actual) / max(v, 1) + np.linalg.norm(m - c), n, v, c)
                )
            _, n, v, c = min(ranked, key=lambda row: row[0])
            if (
                abs(v - actual) > max(0.02, abs(v) * 1e-5)
                or np.linalg.norm(m - c) > 0.002
            ):
                raise ValueError(
                    (
                        n,
                        "native stock dimensions agree but volume or centroid differs",
                        actual,
                        v,
                        m.tolist(),
                        c.tolist(),
                    )
                )
            picked[n] = s
            dims.pop(n)
        else:
            unclaimed.append(bb.round(4).tolist())
        x.Next()
    if dims:
        raise ValueError("Missing expected native geometry: " + ", ".join(dims))
    return picked, dict(
        registered=len(picked),
        unclaimed=len(unclaimed),
        sourceSha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )
