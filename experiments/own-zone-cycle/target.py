"""Resolve the participating HUB opening and test full-sphere passage on a legal trial pose."""

import hashlib
import json
import math
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
R = 0.150114 / 2
G = 9.80665


def register(entries):
    sides = np.array(
        [
            row["boundsMm"]
            for row in entries
            if row["name"] == "GE-26329: Hub Funnel Side" and row["boundsMm"][0] < 0
        ]
    )
    if len(sides) != 6:
        raise ValueError("Could not identify all six blue-frame funnel faces")
    center = (
        np.r_[
            (sides[:, :2].min(axis=0) + sides[:, 3:5].max(axis=0)) / 2,
            sides[:, 5].max(),
        ]
        / 1000
    )
    bodies = {
        kind: [r for r in entries if r["name"] == kind and r["boundsMm"][0] < 0]
        for kind in ["Counting Sensor", "Sensor Reflector"]
    }
    centers = lambda rows: [
        (np.array(r["boundsMm"][:3]) + r["boundsMm"][3:]) / 2000 for r in rows
    ]
    sensor = centers(bodies["Counting Sensor"])
    reflect = centers(bodies["Sensor Reflector"])
    if len(sensor) != 4 or len(reflect) != 4:
        raise ValueError("Expected four counter channels")
    # The functional face, optical axis and event response are not supplied by a
    # body bounding box. Retain the registered housings separately from later witnesses.
    return {
        "centerM": center.tolist(),
        "markerBoundsByType": {
            k: [r["boundsMm"] for r in v] for k, v in bodies.items()
        },
        "registeredSensorHousingCentersM": [v.tolist() for v in sensor],
        "registeredReflectorCentersM": [v.tolist() for v in reflect],
    }


def projectile(registered, run):
    if not run["release"]:
        return {"outcome": "no-release", "trajectory": []}
    model = json.loads((ROOT / "kickoff/rules-model.json").read_bytes())
    # Use the depot program's already declared alliance-zone scoring station.
    station = model["rehearsal"]["programs"]["shift-depot"]["steps"][-1]["at"]
    center = np.array(registered["centerM"])
    dimensions = np.array([model["field"]["length"], model["field"]["width"]])
    robot = (np.array(station) - dimensions / 2) * 0.0254
    direction = center[:2] - robot
    direction /= np.linalg.norm(direction)
    yaxis = np.array([-direction[1], direction[0]])
    r = run["release"]
    position = np.array(r["positionMm"]) / 1000
    vel = r["velocityMps"]
    w0 = np.r_[robot + position[0] * direction + position[1] * yaxis, position[2]]
    velocity = np.r_[vel[0] * direction + vel[1] * yaxis, vel[2]]

    def at(t):
        return w0 + velocity * t + [0, 0, -G * t * t / 2]

    def descend(height):
        disc = velocity[2] ** 2 - 2 * G * (height - w0[2])
        if disc < 0:
            return None
        return (velocity[2] + math.sqrt(disc)) / G

    begin = descend(center[2] + R)
    end = descend(center[2] - R)
    apex = at(velocity[2] / G)
    duration = descend(R)
    points = [
        [round(t, 6), *[round(v, 7) for v in at(t)]]
        for t in np.linspace(0, duration, round(duration * 60) + 1)
    ]
    result = {
        "outcome": "short-of-full-aperture",
        "apexM": apex.tolist(),
        "releaseFieldM": w0.tolist(),
        "velocityFieldMps": velocity.tolist(),
        "headingRad": math.atan2(direction[1], direction[0]),
        "robotFieldM": robot.tolist(),
        "trajectory": points,
        "gravity": G,
    }
    if begin is not None and end is not None:
        normals = np.array(
            [
                [
                    math.cos(math.pi / 6 + i * math.pi / 3),
                    math.sin(math.pi / 6 + i * math.pi / 3),
                ]
                for i in range(6)
            ]
        )
        distances = [
            0.5 * 0.0254 * model["fieldFeatures"]["hubOpening"]
            - R
            - normals @ (at(t)[:2] - center[:2])
            for t in [begin, end]
        ]
        margin = float(np.min(distances))
        result.update(
            outcome="clear" if margin > 0 else "rim-intersection",
            apertureMarginM=margin,
            firstSpherePassS=begin,
            lastSpherePassS=end,
        )
    return result
