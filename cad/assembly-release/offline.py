"""Independently reconstruct the shop features with OCCT for interference and finite section checks."""

import numpy as np
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeFace
from OCP.BRepPrimAPI import (
    BRepPrimAPI_MakeBox,
    BRepPrimAPI_MakeCylinder,
    BRepPrimAPI_MakePrism,
)
from OCP.gp import gp_Pnt, gp_Vec, gp_Ax2, gp_Dir


def shape(f):
    kind = f["kind"]
    if kind == "box":
        return BRepPrimAPI_MakeBox(gp_Pnt(*f["lo"]), gp_Pnt(*f["hi"])).Shape()
    if kind == "round":
        a, b = np.array(f["a"], float), np.array(f["b"], float)
        axis = gp_Ax2(gp_Pnt(*a), gp_Dir(*(b - a)))
        result = BRepPrimAPI_MakeCylinder(axis, f["r"], np.linalg.norm(b - a)).Shape()
        if f.get("inner", 0):
            result = BRepAlgoAPI_Cut(
                result,
                BRepPrimAPI_MakeCylinder(
                    axis, f["inner"], np.linalg.norm(b - a)
                ).Shape(),
            ).Shape()
        return result
    wire = BRepBuilderAPI_MakePolygon()
    for p in f["points"]:
        wire.Add(gp_Pnt(*p))
    wire.Close()
    result = BRepPrimAPI_MakePrism(
        BRepBuilderAPI_MakeFace(wire.Wire()).Face(), gp_Vec(*f["delta"])
    ).Shape()
    for hole in f.get("holes", []):
        a = np.array(hole["center"])
        b = a + f["delta"]
        result = BRepAlgoAPI_Cut(
            result, shape(dict(kind="round", a=a, b=b, r=hole["r"]))
        ).Shape()
    return result


def machine(features, existing=None):
    part = existing
    for f in features:
        tool = shape(f["shape"])
        if f["op"] == "new":
            part = tool
        elif f["op"] == "join":
            part = BRepAlgoAPI_Fuse(part, tool).Shape()
        else:
            part = BRepAlgoAPI_Cut(part, tool).Shape()
    return part
