"""Tessellate the exact public Fusion STEP into a pickable, animated student GLB."""

import json
import math
import struct
import sys
from pathlib import Path
import numpy as np
from OCP.BRepPrimAPI import BRepPrimAPI_MakeSphere

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "experiments/own-zone-cycle"))
sys.path.insert(0, str(ROOT / "scripts"))
from field_mesh import triangles
from verify_upper import reopened
from component_palette import resolve_palette


def world(p):
    a = np.asarray(p, dtype=float)
    return a[..., [0, 2, 1]] * [1, 1, -1] / 1000


class Scene:
    def __init__(self):
        self.g = {
            "asset": {
                "version": "2.0",
                "generator": "2026 project Fusion STEP evidence renderer",
            },
            "scenes": [{"nodes": []}],
            "scene": 0,
            "nodes": [],
            "meshes": [],
            "materials": [],
            "bufferViews": [],
            "accessors": [],
            "animations": [],
        }
        self.bin = bytearray()
        self.colors = {}

    def buf(self, values, kind):
        a = np.ascontiguousarray(values, dtype="<f4")
        self.bin += bytes((-len(self.bin)) % 4)
        off = len(self.bin)
        self.bin += a.tobytes()
        views = self.g["bufferViews"]
        views.append({"buffer": 0, "byteOffset": off, "byteLength": a.nbytes})
        ac = {
            "bufferView": len(views) - 1,
            "componentType": 5126,
            "count": len(a),
            "type": kind,
            "min": a.reshape(len(a), -1).min(axis=0).tolist(),
            "max": a.reshape(len(a), -1).max(axis=0).tolist(),
        }
        self.g["accessors"].append(ac)
        return len(self.g["accessors"]) - 1

    def node(self, name, xyz=(0, 0, 0), parent=None):
        node = {"name": name, "translation": list(xyz)}
        self.g["nodes"].append(node)
        n = len(self.g["nodes"]) - 1
        roots = (
            self.g["scenes"][0]["nodes"]
            if parent is None
            else self.g["nodes"][parent].setdefault("children", [])
        )
        roots.append(n)
        return n

    def geometry(self, node, tri, color):
        t = np.asarray(tri)
        normal = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
        lengths = np.linalg.norm(normal, axis=1)
        mask = lengths > 1e-13
        n = normal[mask] / lengths[mask, None]
        coords = t[mask].reshape(-1, 3)
        if color not in self.colors:
            srgb = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
            lin = [
                c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
                for c in srgb
            ]
            self.colors[color] = len(self.g["materials"])
            self.g["materials"].append(
                {
                    "doubleSided": True,
                    "pbrMetallicRoughness": {
                        "baseColorFactor": [*lin, 1],
                        "metallicFactor": 0.1,
                        "roughnessFactor": 0.68,
                    },
                }
            )
        primitive = {
            "attributes": {
                "POSITION": self.buf(coords, "VEC3"),
                "NORMAL": self.buf(np.repeat(n, 3, axis=0), "VEC3"),
            },
            "material": self.colors[color],
        }
        self.g["meshes"].append({"primitives": [primitive]})
        self.g["nodes"][node]["mesh"] = len(self.g["meshes"]) - 1

    def track(self, clip, node, path, times, values):
        clip["samplers"].append(
            {
                "input": self.buf(times, "SCALAR"),
                "output": self.buf(values, "VEC4" if path == "rotation" else "VEC3"),
                "interpolation": "LINEAR",
            }
        )
        clip["channels"].append(
            {
                "sampler": len(clip["samplers"]) - 1,
                "target": {"node": node, "path": path},
            }
        )

    def save(self, path):
        self.bin += bytes((-len(self.bin)) % 4)
        self.g["buffers"] = [{"byteLength": len(self.bin)}]
        j = json.dumps(self.g, separators=(",", ":"), ensure_ascii=True).encode()
        j += b" " * ((-len(j)) % 4)
        path.write_bytes(
            struct.pack("<4sII", b"glTF", 2, 28 + len(j) + len(self.bin))
            + struct.pack("<I4s", len(j), b"JSON")
            + j
            + struct.pack("<I4s", len(self.bin), b"BIN\x00")
            + self.bin
        )


def main():
    palette = resolve_palette(ROOT)
    scene = Scene()
    data = json.loads((ROOT / "experiments/own-zone-cycle/counter-replay.json").read_bytes())
    pivot = np.array([275, 0, 240])
    arm = scene.node("Ground intake pivot", world(pivot))
    cleats = []
    for shape, part, extent in reopened():
        name = part["name"]
        parent = (
            arm
            if name == "ground intake roller"
            or name.endswith(("intake bearing arm", "intake journal"))
            else None
        )
        center = (extent[:3] + extent[3:]) / 2
        n = scene.node(
            name, world(center - (pivot if parent is not None else 0)), parent
        )
        scene.geometry(
            n,
            world(np.concatenate(list(triangles(shape, 0.18))) - center),
            palette[part["role"]],
        )
        if "lift shelf " in name:
            cleats.append((n, center))
    fuel = scene.node("One nominal FUEL")
    scene.g["nodes"][fuel]["scale"] = [0, 0, 0]
    geom = np.concatenate(list(triangles(BRepPrimAPI_MakeSphere(75.057).Shape(), 0.8)))
    scene.geometry(fuel, world(geom), "#E6B72A")
    goal = scene.node("HUB aperture reference ring")
    scene.g["nodes"][goal]["scale"] = [0, 0, 0]
    center = np.array(data["centerM"])
    robot = np.array(data["robotFieldM"])
    h = data["headingRad"]
    forward = np.array([math.cos(h), math.sin(h)])
    left = np.array([-forward[1], forward[0]])

    def local(p):
        xy = np.array(p[:2]) - robot
        return world([1000 * np.dot(xy, forward), 1000 * np.dot(xy, left), 1000 * p[2]])

    vertices = []
    rho = 0.0417 * 25.4 / 2 / math.cos(math.pi / 6)
    for i in range(6):
        a = i * math.pi / 3
        b = (i + 1) * math.pi / 3
        quad = [
            local(
                [center[0] + r * math.cos(an), center[1] + r * math.sin(an), center[2]]
            )
            for r, an in [(rho, a), (rho, b), (rho + 0.025, b), (rho + 0.025, a)]
        ]
        vertices += [[quad[0], quad[1], quad[2]], [quad[0], quad[2], quad[3]]]
    scene.geometry(goal, vertices, "#DAA84A")
    witness = scene.node("Registered field counter channel 3")
    scene.g["nodes"][witness]["scale"] = [0, 0, 0]
    ends = [np.array(box).reshape(2,3).mean(axis=0)/1000 for box in data["counterMarkerBoundsMm"]]
    a, b = [local(p) for p in ends]
    # Display a reference line between housing centers; the numerical check bounds every ray.
    up = np.array([0, .009, 0])
    scene.geometry(witness, [[a-up,b-up,b+up],[a-up,b+up,a+up]], "#61e6de")
    contacts = data["mechanismRows"]
    flying = data["flightRows"]
    parked = data["atPickup"]
    handoff = data["atLift"]
    release = data["atRelease"]
    for label, begin, end in [
        ("Pickup and lift", -0.7, handoff),
        ("Release and HUB entry", handoff, release + flying[-1][0]),
    ]:
        times = np.linspace(begin, end, max(3, round((end - begin) * 60)))
        ticks = times - begin
        clip = {"name": label, "samplers": [], "channels": []}
        scene.g["animations"].append(clip)
        q = []
        positions = []
        outline = []
        cargo = []
        shelves = {n: [] for n, _ in cleats}
        shelfq = {n: [] for n, _ in cleats}
        feed = np.array(contacts)
        fly = np.array(flying)
        for t in times:
            angle = (
                (84 + (-39 - 84) * min(1, max(0, (t + 0.7) / 0.7)))
                if t < 0
                else -39 + 31 * min(1, max(0, (t - parked) / 0.2))
            )
            z = math.radians(angle - 84) / 2
            q.append([0, 0, math.sin(z), math.cos(z)])
            if t <= release:
                positions.append(
                    world([np.interp(t, feed[:, 0], feed[:, i]) for i in [1, 2, 3]])
                )
            else:
                positions.append(
                    local(
                        [
                            np.interp(t - release, fly[:, 0], fly[:, i])
                            for i in [1, 2, 3]
                        ]
                    )
                )
            cargo.append([1, 1, 1])
            outline.append([int(begin > 0)] * 3)
            for n, c in cleats:
                # Side-mounted ledges fold onto their return run after rounding the upper pulley.
                delta = -33 * min(1, max(0, (t + 0.7) / 0.7)) + min(
                    490, max(0, (t - parked - 0.23) * 650)
                )
                top = 622.0
                travel = c[2] + delta
                if travel <= top:
                    xyz = [c[0], c[1], travel]
                    rot = 0.0
                else:
                    sweep = min(math.pi, (travel - top) / 52.5)
                    xyz = [
                        c[0] + 52.5 * (1 - math.cos(sweep)),
                        c[1],
                        top
                        + 52.5 * math.sin(sweep)
                        - max(0, travel - top - 52.5 * math.pi),
                    ]
                    rot = -sweep
                shelves[n].append(world(xyz))
                shelfq[n].append([0, 0, math.sin(rot / 2), math.cos(rot / 2)])
        scene.track(clip, arm, "rotation", ticks, q)
        scene.track(clip, fuel, "translation", ticks, positions)
        scene.track(clip, fuel, "scale", ticks, cargo)
        scene.track(clip, goal, "scale", ticks, outline)
        scene.track(clip, witness, "scale", ticks, outline)
        for n, _ in cleats:
            scene.track(clip, n, "translation", ticks, shelves[n])
            scene.track(clip, n, "rotation", ticks, shelfq[n])
    output = ROOT / "cad/archived-views/robot/cad/own-zone.glb"
    output.parent.mkdir(parents=True, exist_ok=True)
    scene.save(output)
    print(
        output.name,
        len(scene.g["nodes"]),
        "nodes;",
        [c["name"] for c in scene.g["animations"]],
    )


if __name__ == "__main__":
    main()
