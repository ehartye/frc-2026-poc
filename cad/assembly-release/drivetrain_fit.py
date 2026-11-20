"""Check removal tools and an entire turn of each module in the registered robot, in mm."""

import argparse
import json
import math
from pathlib import Path

import numpy as np
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.gp import gp_Trsf

from offline import machine, shape
from shop import round_stock
from supplier import bounds, content
from swerve import build, layout
from frame import build as build_frame
from contact_audit import records

ROTATING = {
    11,
    12,
    13,
    14,
    15,
    16,
    17,
    18,
    23,
    *range(32, 46),
    *range(48, 54),
    *range(57, 62),
}


def moved(body, site):
    matrix = np.column_stack((site["rotation"], site["translation"]))
    placement = gp_Trsf()
    placement.SetValues(*matrix.flatten())
    return BRepBuilderAPI_Transform(body, placement, False).Shape()


def vol(body):
    p = GProp_GProps()
    BRepGProp.VolumeProperties_s(body, p)
    return abs(p.Mass())


def broad(a, b):
    return np.all(np.minimum(a[3:], b[3:]) - np.maximum(a[:3], b[:3]) > 0.00001)


def cyl(a, b, r):
    return shape(round_stock(a, b, r))


def run(source, issued_step=None):
    cfg, _, _, sites = layout()
    native = content(source, cfg["swerve"]["sha256"])
    leaves = {}
    for name, part in native.items():
        i = int(name.split(":")[0])
        if i in ROTATING:
            bb = bounds(part)
            r = (
                math.hypot(max(abs(bb[0]), abs(bb[3])), max(abs(bb[2]), abs(bb[5])))
                + 0.01
            )
            if r > 47.4:
                limit = cyl([0, bb[1] - 1, 0], [0, bb[4] + 1, 0], 47.4)
                if vol(BRepAlgoAPI_Cut(part, limit).Shape()) > 0.001:
                    raise ValueError(f"Moving part outside analytic revolution: {name}")
                r = 47.4
            leaves[name] = cyl([0, bb[1], 0], [0, bb[4], 0], r)
        else:
            leaves[name] = part
    new, hardware, rail_ops, stacks = build()
    new.update(build_frame())
    scene = {
        m["id"]: body
        for body, m in records()
        if " public " not in m["id"] and m["id"] not in new
    }
    for name, ops in rail_ops.items():
        new[name]["features"].extend(ops)
    scene.update(
        {name: machine(row["features"]) for name, row in {**new, **hardware}.items()}
    )
    native_binding = None
    if issued_step:
        from reopened_geometry import read

        scene, native_binding = read(issued_step, scene)
    fixed = {name: (body, bounds(body)) for name, body in scene.items()}
    report = {}
    for site in sites:

        def world(body):
            return moved(body, site)

        def hits(tool, obstacles, skip=()):
            bb = bounds(tool)
            result = {}
            for name, (obs, ob) in obstacles.items():
                if name in skip or not broad(bb, ob):
                    continue
                v = vol(BRepAlgoAPI_Common(tool, obs).Shape())
                if v > 0.02:
                    result[name] = round(v, 4)
            return result

        tag = site["name"]
        module = {k: world(v) for k, v in leaves.items()}
        registered = {k: (v, bounds(v)) for k, v in module.items()}
        contacts = {}
        for leaf, part in module.items():
            conflict = hits(part, fixed)
            if conflict:
                contacts[leaf] = conflict
        tools = {}
        for index in range(2):

            def project(u, h, v):
                return [u, h, v] if index == 0 else [v, h, u]

            for k, h in enumerate((46, 67), 1):
                prefix = tag + " rail mount " + str(index + 1) + "-" + str(k)
                key = world(cyl(project(-17.49, h, 69.85), project(44.5, h, 69.85), 3))
                pull = world(
                    cyl(project(-23.49, h, 69.85), project(22.5, h, 69.85), 5.05)
                )
                for op, tool in (("key", key), ("headWithdrawal", pull)):
                    tools[prefix + " " + op] = hits(
                        tool, {**registered, **fixed}, (prefix + " M6 cap screw",)
                    )
            # Install vertical hardware before raising module to the frame. No chassis access claimed at this step.
            for k, v in enumerate((57.15, 82.55), 1):
                key = world(
                    cyl(project(-31.75, 22.625, v), project(-31.75, -38, v), 2.35)
                )
                socket = world(
                    cyl(project(-31.75, 86.23, v), project(-31.75, 115, v), 7)
                )
                for op, tool in (("bottomKey", key), ("topSocket", socket)):
                    tools[f"{tag} tab {index + 1}-{k} {op}"] = hits(tool, registered)
        report[tag] = {
            "supplierRobotIntersectionsMm3": contacts,
            "serviceContactsMm3": tools,
        }
    return dict(
        supplierSha256=cfg["swerve"]["sha256"],
        supplierBodies=len(leaves),
        sites=report,
        nativeBinding=native_binding,
        interpretation="Volume over 0.02 cubic mm. Moving leaves use enclosing cylinders over their full axial intervals. Positive cylinder overlap requires exact angular investigation. Bottom key and top socket checks are against its non-chassis module before installation. The side driver and cap head are checked with the complete parked T1 robot.",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("supplier", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--step",
        type=Path,
        help="Independently reopened issued Fusion STEP, used in place of generated robot stock",
    )
    arg = parser.parse_args()
    arg.output.write_text(
        json.dumps(run(arg.supplier, arg.step), indent=2) + "\n", encoding="utf8"
    )
