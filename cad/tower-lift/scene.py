"""Build role-matched Fusion still inventory and a timed GLB from the reopened whole robot."""

import json, hashlib, sys, math
from pathlib import Path
import numpy as np
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box
from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax2, gp_Pnt, gp_Dir

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "cad/own-zone-upper"), str(ROOT / "scripts")]
from animated import Scene, world, triangles
from component_palette import resolve_palette
from verify_upper import bounds
from recipe import parts


def records():
    data = json.loads((ROOT / "cad/own-zone-upper/appearances.json").read_bytes())
    intended = {
        p["id"]: dict(role=p["role"], bounds=p["boundsMm"], stage="fixed")
        for p in data["solids"]
    }
    for p in parts():
        if p["shape"] == "hook":
            xs, zs = zip(*p["profile"])
            bb = [min(xs), p["y"], min(zs), max(xs), p["y"] + p["thickness"], max(zs)]
        else:
            bb = bounds(p)
        intended[p["name"]] = dict(role=p["role"], bounds=bb, stage=p["stage"])
    reader = STEPControl_Reader()
    if (
        reader.ReadFile(str(HERE / "tower-l1.step")) != IFSelect_RetDone
        or not reader.TransferRoots()
    ):
        raise ValueError("STEP failed")
    exp = TopExp_Explorer(reader.OneShape(), TopAbs_SOLID)
    out = []
    while exp.More():
        shp = exp.Current()
        bbox = Bnd_Box()
        BRepBndLib.AddOptimal_s(shp, bbox, False, False)
        bb = np.array([*bbox.CornerMin().Coord(), *bbox.CornerMax().Coord()])
        matches = [
            n
            for n, p in intended.items()
            if abs(bb - np.array(p["bounds"])).max() < 0.001
        ]
        if len(matches) != 1:
            raise ValueError(f"Unidentified or duplicate solid at {bb}: {matches}")
        name = matches[0]
        part = intended.pop(name)
        out.append(
            (
                shp,
                dict(
                    id=name,
                    stage=part["stage"],
                    role=part["role"],
                    boundsMm=bb.round(5).tolist(),
                ),
            )
        )
        exp.Next()
    if intended:
        raise ValueError(f"Missing components {list(intended)}")
    return out


def make():
    physical = records()
    receipt = dict(
        schema="agent-frc/assembly-appearances@1",
        sourceSha256=hashlib.sha256((HERE / "tower-l1.step").read_bytes()).hexdigest(),
        solids=[{k: v for k, v in p.items() if k != "stage"} for _, p in physical],
    )
    (HERE / "appearances.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf8", newline="\n"
    )
    evidence = ROOT / "experiments/tower-climb"
    source = json.loads((evidence / "support.json").read_bytes())[0]
    rows = json.loads((evidence / "motion.json").read_bytes())
    colors = resolve_palette(ROOT)
    scene = Scene()
    robot = scene.node("Hung R2C robot", world([0, 0, 320]))
    offset = scene.node("Chassis datum", world([0, 0, -320]), robot)
    lift = scene.node("Lift carriage", parent=offset)
    rail = scene.node("Deploying hooks", parent=lift)
    for shape, part in physical:
        node = scene.node(
            part["id"],
            parent={"fixed": offset, "elevator": lift, "hooks": rail}[part["stage"]],
        )
        scene.geometry(
            node,
            world(np.concatenate(list(triangles(shape, 0.45)))),
            colors[part["role"]],
        )
    # Team-drawn teaching geometry at official measured datums; does not redistribute FIRST triangles.
    data = json.loads((evidence / "field.json").read_bytes())["sides"]["blue"]
    origin = np.r_[source["startDatumX"], source["startDatumY"], 0] * 1000
    for i, row in enumerate(data):
        q = np.array(row["boundsMm"]) - np.tile(origin, 2)
        if "Tower Rung" in row["name"]:
            sh = BRepPrimAPI_MakeCylinder(
                gp_Ax2(
                    gp_Pnt((q[0] + q[3]) / 2, q[1], (q[2] + q[5]) / 2), gp_Dir(0, 1, 0)
                ),
                (q[5] - q[2]) / 2,
                q[4] - q[1],
            ).Shape()
        elif any(
            tag in row["name"] for tag in ("Upright Outer", "Base Bottom", "Base Angle")
        ):
            if "Base Bottom" in row["name"]:
                q[5] = row["fieldward145mmTopMm"]
            sh = BRepPrimAPI_MakeBox(gp_Pnt(*q[:3]), gp_Pnt(*q[3:])).Shape()
        else:
            continue
        node = scene.node("Registered TOWER guide " + str(i))
        scene.geometry(node, world(np.concatenate(list(triangles(sh)))), "#527DB6")
    clip = {"name": "Park, capture, lift and hold", "channels": [], "samplers": []}
    times = [r["t"] for r in rows]
    scene.track(
        clip, robot, "translation", times, [[r["x"], 0.320 + r["z"], 0] for r in rows]
    )
    # Positive pitch raises +X into viewer +Y: rotate around viewer +Z.
    scene.track(
        clip,
        robot,
        "rotation",
        times,
        [[0, 0, math.sin(r["pitch"] / 2), math.cos(r["pitch"] / 2)] for r in rows],
    )
    scene.track(clip, lift, "translation", times, [[0, -r["down"], 0] for r in rows])
    scene.track(clip, rail, "translation", times, [[-r["deploy"], 0, 0] for r in rows])
    scene.g["animations"] = [clip]
    output = ROOT / "docs/robot/cad/tower-climb.glb"
    scene.save(output)


if __name__ == "__main__":
    make()
