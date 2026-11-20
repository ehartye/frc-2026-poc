"""Measure actual bearing contact at both tab seats and both hardware seats of every bolted stack."""

import argparse
import json
from pathlib import Path

import numpy as np
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepGProp import BRepGProp
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
from OCP.GProp import GProp_GProps
from OCP.gp import gp_Pnt

from supplier import content
from swerve import layout


def seat(part, axis_u, v, height, fabric):
    def point(u, z):
        return [u, height, z] if axis_u else [z, height, u]

    if fabric == "saddle":
        # Cut the seating patch at the midplane between bolts for a distinct observation per station.
        lo, hi = (52, 69.85) if v < 69.85 else (69.85, 87.7)
        outer = [
            point(u, t) for u, t in [(-46.6, lo), (-23.5, lo), (-23.5, hi), (-46.6, hi)]
        ]
        wire = BRepBuilderAPI_MakePolygon()
        for p in outer:
            wire.Add(gp_Pnt(*p))
        wire.Close()
        patch = BRepBuilderAPI_MakeFace(wire.Wire()).Face()
    else:
        # A 9.2 mm washer-face diameter is conservative inside the 9.525 AF nut.
        from OCP.gp import gp_Ax2, gp_Dir, gp_Circ
        from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire

        circle = gp_Circ(
            gp_Ax2(gp_Pnt(*point(-31.75, v)), gp_Dir(0, 1, 0)),
            3.7846 if fabric == "head" else 4.6,
        )
        patch = BRepBuilderAPI_MakeFace(
            BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(circle).Edge()).Wire()
        ).Face()
    result = BRepAlgoAPI_Common(patch, part).Shape()
    prop = GProp_GProps()
    BRepGProp.SurfaceProperties_s(result, prop)
    # Supplier throat is already void; saddle's hole is slightly bigger.
    area = prop.Mass()
    if fabric == "head":
        area -= np.pi * (2.75**2 - 2.5**2)
    if fabric == "saddle":
        area -= np.pi * (2.65**2 - 2.5**2)
    return round(float(area), 4)


def measure(path):
    cfg, _, _, sites = layout()
    supplier = content(path, cfg["swerve"]["sha256"])
    by_height = {}
    from supplier import faces

    for name, part in supplier.items():
        if name.startswith(("9:", "10:")):
            throat = next(
                f for f in faces(part) if any(abs(n + 31.75) < 0.01 for n in f["xzMm"])
            )
            by_height[round(throat["finiteYmm"][0])] = part
    measured = []
    for axis_u in (True, False):
        for v in (57.15, 82.55):
            row = dict(saddle=1 if axis_u else 2, supplierStation=v)
            for label, part, y, fabric in (
                ("lowerSaddle", 27, 31.75, "saddle"),
                ("upperSaddle", 83, 82.55, "saddle"),
                ("head", 27, 27.46375, "head"),
                ("nut", 83, 86.2125, "nut"),
            ):
                row[label + "AreaMm2"] = seat(by_height[part], axis_u, v, y, fabric)
                if row[label + "AreaMm2"] <= 1:
                    raise ValueError((row, label))
            measured.append(row)
    result = []
    for site in sites:
        for row in measured:
            v = row["supplierStation"]
            p = [-31.75, 31.75, v] if row["saddle"] == 1 else [v, 31.75, -31.75]
            pos = np.asarray(site["rotation"]) @ np.asarray(p) + site["translation"]
            result.append(
                dict(site=site["name"], centerMm=pos.round(4).tolist(), **row)
            )
    return dict(
        sourceSha256=cfg["swerve"]["sha256"],
        method="Finite coplanar surface intersections on the unmodified supplier plates. Saddle area partitioned at bolt midplane; minimum 7.5692 mm socket cap diameter, measured between r2.75 mm and the outside edge; nut seat uses an inscribed 9.2 mm circle.",
        stacks=result,
    )


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("supplier", type=Path)
    cli.add_argument("out", type=Path)
    args = cli.parse_args()
    args.out.write_text(
        json.dumps(measure(args.supplier), indent=2) + "\n", encoding="utf8"
    )
