"""Elastic bolt-group reactions at the measured four M6 rail mounts, idealized rigid module/frame."""

import argparse
import itertools
import json
from pathlib import Path
import math

import numpy as np

from swerve import build


def run():
    _, parts, _, _ = build()
    sites = []
    for k, row in parts.items():
        if k.startswith("front left rail mount") and k.endswith("M6 cap screw"):
            s = row["features"][0]["shape"]
            t = np.array(s["b"]) - s["a"]
            t = t / np.linalg.norm(t)
            # Actual rail plane is 26.1 behind the underside of its screw head.
            point = np.array(s["b"]) - 26.1 * t
            sites.append((k, point, t))
    assert len(sites) == 4
    center = np.array([265.0, 265.0, 0.0])

    def skew(r):
        return np.array([[0, -r[2], r[1]], [r[2], 0, -r[0]], [-r[1], r[0], 0]])

    constraints = []
    for _, point, n in sites:
        a = np.column_stack((np.eye(3), -skew(point - center) / 100.0))
        constraints.append((a, n))
    samples = []
    weights = (("four even", 0.25), ("two on diagonal", 0.5), ("single corner", 1))
    for (name, fraction), lat, angle in itertools.product(
        weights, (0.5, 1.0, 2.0), (0, 45, 90, 135, 180, 225, 270, 315)
    ):
        mass = 62.0
        g = 9.80665
        f = mass * g * fraction
        rad = math.radians(angle)
        w = np.array([f * lat * math.cos(rad), f * lat * math.sin(rad), 2 * f, 0, 0, 0])
        cases = []
        for shear_ratio, contact_ratio in itertools.product(
            (0.1, 0.4, 1.0), (0, 1.0, 4.0)
        ):

            def reaction(q, details=False):
                eq = -w.copy()
                forces = []
                for a, n in constraints:
                    u = a @ q
                    un = n @ u
                    us = u - un * n
                    tensile = 10000 * un
                    # No preload or friction credit. A closed compressed joint can bear on its rail.
                    contact = 10000 * contact_ratio * min(un, 0)
                    shear = 10000 * shear_ratio * us
                    eq += a.T @ (shear + (tensile + contact) * n)
                    forces.append((max(0, tensile), np.linalg.norm(shear)))
                return forces if details else eq

            for flags in itertools.product((False, True), repeat=4):
                k = np.zeros((6, 6))
                for flag, (a, n) in zip(flags, constraints):
                    p = np.outer(n, n)
                    spring = 10000 * (
                        (1 + contact_ratio * flag) * p + shear_ratio * (np.eye(3) - p)
                    )
                    k += a.T @ spring @ a
                q = np.linalg.solve(k, w)
                if np.max(np.abs(reaction(q))) < 1e-4:
                    break
            else:
                raise ValueError("Force/moment closure")
            maxima = {
                "boltTensionN": 0.0,
                "boltShearN": 0.0,
                "boltCombinedMPa": 0.0,
                "threadDemandMPa": 0.0,
                "bossWeldMeanMPa": 0.0,
            }
            for tension, shear in reaction(q, True):
                # M6 ISO coarse tensile stress area 20.1 mm². Use thread-root area also for gross direct shear.
                equivalent = math.hypot(tension / 20.1, math.sqrt(3) * shear / 20.1)
                vals = (
                    tension,
                    shear,
                    equivalent,
                    tension / (0.5 * math.pi * 5 * 11.9),
                    math.hypot(tension, shear) / (math.pi * 13 * 1.5),
                )
                for key, val in zip(maxima, vals):
                    maxima[key] = max(maxima[key], val)
            cases.append(maxima)
        samples.append(
            dict(
                case=name,
                cornerFraction=fraction,
                verticalG=2.0,
                lateralG=lat,
                headingDeg=angle,
                worst={k: round(max(v[k] for v in cases), 3) for k in cases[0]},
            )
        )
    return dict(
        bodyMassKg=62.0,
        massBasis="Scenario gross supported mass, including any cargo; no measured weight.",
        model="Four M6 spring stations on exact saddle/rail planes, no friction or assembly preload. Rigid purchased module and rails, lateral headings in 45 degree steps. Force and moment closure checked. Vary shear/axial spring ratio 0.1 to 1 and compression bearing stiffness from zero to four times tensile. The tensile and shear peaks can belong to different screws.",
        limits="No thread/weld allowable or HAZ strength assigned. Mean circular attachment stress assumes 1.5 mm continuous throat. Thread screening subtracts two pitch-lengths from 13.9 mm geometry; avoids using gross engagement as fully formed. No prying, fatigue, stress concentration, under-head slip, motor torque, deck load or local rail shell yielding evaluated.",
        loads=samples,
    )


if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("out", type=Path)
    p = a.parse_args()
    p.out.write_text(json.dumps(run(), indent=2) + "\n", encoding="utf8")
