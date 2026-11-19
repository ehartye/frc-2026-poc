"""Run every attained magazine exit, native HUB surface, ball contact and optical channel on one clock."""

import argparse
import itertools
import json
import math
import sys
from pathlib import Path

import numpy as np
import vtk

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "own-zone-cycle"))
from counter_drive import CounterDrive
from counter_witness import BeamWitness
from hub_contact import Hub
from target import R, G
from rim import Rim

M = 0.215
J = 0.4 * M * R * R
ZERO = np.zeros(3)


def cross(a, b):
    return np.array(
        [
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0],
        ]
    )


def load(path):
    return json.loads(path.read_bytes())


class Counter:
    def __init__(self, source):
        witness = BeamWitness(source)
        self.lines = []
        for a, d, span in witness.channels:
            tips = a + d
            self.lines.append(
                (
                    a,
                    d,
                    span,
                    np.minimum(a.min(0), tips.min(0)),
                    np.maximum(a.max(0), tips.max(0)),
                )
            )
        self.open = [None] * 4
        self.intervals = []

    def advance(self, t, balls):
        for i, (a, d, span, lo, hi) in enumerate(self.lines):
            near = []
            for b in balls:
                p = b["p"]
                if (
                    p[0] < lo[0] - R
                    or p[0] > hi[0] + R
                    or p[1] < lo[1] - R
                    or p[1] > hi[1] + R
                    or p[2] < lo[2] - R
                    or p[2] > hi[2] + R
                ):
                    continue
                g = np.maximum(np.maximum(lo - p, p - hi), 0)
                if g @ g <= R * R:
                    near.append(b)
            row = self.open[i]
            if not near:
                if row is not None:
                    row.update(clearS=t, possible=sorted(row["possible"]))
                    self.intervals.append(row)
                    self.open[i] = None
                continue
            if row is None:
                row = {
                    "channel": i + 1,
                    "firstPossibleS": t,
                    "possible": set(),
                    "definite": {},
                }
                self.open[i] = row
            for b in near:
                p = b["p"]
                ident = b["id"]
                row["possible"].add(ident)
                if not span[0] < p[1] < span[1]:
                    continue
                ratio = (p[1] - a[:, 1]) / d[:, 1]
                g = a + ratio[:, None] * d - p
                margin = R - math.sqrt(float(np.max(np.sum(g * g, axis=1))))
                if margin > 0:
                    h = row["definite"].setdefault(
                        ident, {"firstS": t, "lastS": t, "marginM": margin}
                    )
                    h["lastS"] = t
                    h["marginM"] = max(h["marginM"], margin)


def force(v, n, depth, stiffness, damping, mu):
    vn = float(v @ n)
    normal = max(0, stiffness * depth - damping * vn)
    slip = v - n * vn
    speed = math.sqrt(float(slip @ slip))
    tang = -mu * normal * math.tanh(speed / 0.035) * slip / max(speed, 1e-12)
    return normal * n + tang, tang


def field(hub, drive, b, t):
    p, v, w = b["p"], b["v"], b["w"]
    gap = np.maximum(np.maximum(hub.lower - p, p - hub.upper), 0.0)
    for i in np.flatnonzero(np.einsum("ij,ij->i", gap, gap) <= R * R):
        name, locator, _, _ = hub.part[i]
        point = [0.0, 0.0, 0.0]
        cell = vtk.reference(0)
        sub = vtk.reference(0)
        dist = vtk.reference(0.0)
        locator.FindClosestPoint(p, point, cell, sub, dist)
        length = max(1e-10, float(dist) ** 0.5)
        if length >= R:
            continue
        n = (p - np.array(point)) / length
        rel = v + cross(w, -R * n) - drive.surface(i, np.array(point))
        f, tan = force(rel, n, R - length, 9500, 22, 0.25)
        b["f"] += f
        b["m"] += cross(-R * n, tan)
        if float(f @ f) > 0.001:
            b["geometry"].add(name)
            log = b["contacts"].setdefault(
                name, {"firstS": t, "lastS": t, "firstCenterM": p.tolist()}
            )
            log["lastS"] = t


def run(cache, inputs, dt, clock_start, piece_contacts=True):
    local = load(inputs)
    registered = load(HERE.parent / "own-zone-cycle/single-piece.json")["registeredHub"]
    basis = load(HERE.parent / "own-zone-cycle/counter-replay.json")
    center = np.array(registered["centerM"])
    heading = basis["headingRad"]
    co, si = math.cos(heading), math.sin(heading)
    orient = np.array([[co, -si, 0], [si, co, 0], [0, 0, 1.0]])
    offset = np.r_[basis["robotFieldM"], 0.0]
    rays = np.array(
        [
            [
                math.cos(math.pi / 6 + i * math.pi / 3),
                math.sin(math.pi / 6 + i * math.pi / 3),
            ]
            for i in range(6)
        ]
    )
    field_width = (
        load(PROJECT / "kickoff/rules-model.json")["fieldFeatures"]["hubOpening"]
        * 0.0254
    )
    hub = Hub(cache / "blue-hub-private.npz")
    drive = CounterDrive(hub.part, 1.0, 1.0)
    sensors = Counter(registered)
    rim = Rim(cache / "blue-hub-private.npz", center, R)
    active = []
    states = []
    history = []
    interactions = {}
    events = sorted(local["releases"], key=lambda r: r["timeS"])
    cursor = 0
    t = 0.0
    latest = local["duration"] + 5.0
    while t < latest:
        while cursor < len(events) and events[cursor]["timeS"] <= t + 1e-9:
            event = events[cursor]
            cursor += 1
            b = {
                "id": event["id"],
                "releaseS": event["timeS"],
                "p": offset + orient @ event["positionM"],
                "v": orient @ event["velocityMps"],
                "w": orient @ event["spinRadS"],
                "geometry": set(),
                "crossing": None,
                "apertureS": None,
                "apertureMarginM": None,
                "landedS": None,
                "rimAttempts": [],
                "contacts": {},
                "passedDownstream": {},
                "clearUpstream": {},
            }
            active.append(b)
            states.append(b)
        step = min(dt, latest - t)
        if cursor < len(events):
            step = min(step, events[cursor]["timeS"] - t)
        if step < 1e-12:
            break
        for b in active:
            b["f"] = np.array([0.0, 0.0, -M * G])
            b["m"] = np.zeros(3)
            field(hub, drive, b, t)
        for a, b in itertools.combinations(active, 2) if piece_contacts else ():
            diff = a["p"] - b["p"]
            d2 = float(diff @ diff)
            if d2 >= (2 * R) ** 2:
                continue
            distance = max(1e-10, d2**0.5)
            n = diff / distance
            rel = a["v"] + cross(a["w"], -R * n) - b["v"] - cross(b["w"], R * n)
            f, ft = force(rel, n, 2 * R - distance, 9000, 16, 0.35)
            a["f"] += f
            b["f"] -= f
            a["m"] += cross(-R * n, ft)
            b["m"] += cross(R * n, -ft)
            key = tuple(sorted([a["id"], b["id"]]))
            log = interactions.setdefault(
                key, {"ids": key, "firstS": t, "lastS": t, "impulseNs": 0.0}
            )
            log["lastS"] = t
            log["impulseNs"] += float(np.linalg.norm(f)) * step
        for b in active:
            old = b["p"].copy()
            b["v"] += b["f"] * (step / M)
            b["w"] += b["m"] * (step / J)
            b["p"] += b["v"] * step
            p = b["p"]
            rim.observe(b, old, t, step)
            upper, lower = center[2] + R, center[2] - R
            if old[2] >= upper and p[2] < upper:
                alpha = (upper - old[2]) / (p[2] - old[2])
                entry = old + alpha * (p - old)
                b["crossing"] = float(
                    np.min(field_width / 2 - R - rays @ (entry[:2] - center[:2]))
                )
            if b["crossing"] is not None:
                if p[2] > upper:
                    b["crossing"] = None
                    continue
                alpha = (
                    (lower - old[2]) / (p[2] - old[2])
                    if p[2] < lower <= old[2]
                    else 1.0
                )
                end = old + alpha * (p - old)
                gap = float(np.min(field_width / 2 - R - rays @ (end[:2] - center[:2])))
                b["crossing"] = min(b["crossing"], gap)
                if p[2] <= lower:
                    if b["crossing"] > 0 and b["apertureS"] is None:
                        b["apertureS"] = t + alpha * step
                        b["apertureMarginM"] = b["crossing"]
                    b["crossing"] = None
            if p[2] < R and b["v"][2] < 0:
                b["landedS"] = t + step
        t += step
        sensors.advance(t, active)
        for b in active:
            for i, (_, _, _, lo, hi) in enumerate(sensors.lines):
                if b["p"][0] + R < lo[0]:
                    b["clearUpstream"].setdefault(i + 1, t)
                if b["p"][0] - R > hi[0] and i + 1 in b["clearUpstream"]:
                    b["passedDownstream"].setdefault(i + 1, t)
        active = [b for b in active if b["landedS"] is None]
        if round(t / dt) % max(1, round(0.05 / dt)) == 0 and (
            not history or t > history[-1][0] + 0.02
        ):
            history.append(
                [
                    round(t, 4),
                    *[[b["id"], *[round(i, 4) for i in b["p"]]] for b in active],
                ]
            )
        if cursor == len(events) and not active:
            break
    results = []
    for b in states:
        ident = b["id"]
        matches = [e for e in sensors.intervals if ident in e["definite"]]
        clean = [
            e
            for e in matches
            if len(e["possible"]) == 1
            and b.get("rimS") is not None
            and e["firstPossibleS"] >= b["rimS"]
            and b["passedDownstream"].get(e["channel"], -1)
            > e["definite"][ident]["firstS"]
        ]
        e = clean[0] if len(clean) == 1 else None
        # Any matching active-window score must be source-bound and followed by a clear interval shared by all balls.
        when = max(e["clearS"], b["passedDownstream"][e["channel"]]) if e else None
        within = bool(when is not None and clock_start + when < 25)
        processing = bool(
            when is not None
            and clock_start + b["rimS"] < 25 <= clock_start + when <= 28
        )
        results.append(
            {
                "id": ident,
                "releaseS": b["releaseS"],
                "apertureS": b.get("rimS"),
                "marginM": b.get("rimMarginM"),
                "legacyApertureS": b["apertureS"],
                "legacyMarginM": b["apertureMarginM"],
                "nativeRimPassages": b["rimAttempts"],
                "nativeContacts": b["contacts"],
                "sharedClearS": when,
                "channel": e["channel"] if e else None,
                "countWithin": within,
                "processingOnly": processing,
                "landedS": b["landedS"],
            }
        )
    return {
        "dt": dt,
        "pieceContactsEnabled": piece_contacts,
        "startShiftS": clock_start,
        "idsReleased": len(events),
        "apertures": sum(r["apertureS"] is not None for r in results),
        "unambiguousPassages": sum(r["sharedClearS"] is not None for r in results),
        "activeWindow": sum(r["countWithin"] for r in results),
        "processingOnly": sum(r["processingOnly"] for r in results),
        "nativeRim": rim.receipt,
        "sphereInteractions": list(interactions.values()),
        "pieces": results,
        "sensorIntervals": sensors.intervals,
        "trajectory": history,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("cache", type=Path)
    p.add_argument("input", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--dt", type=float, default=0.0005)
    p.add_argument("--clock-start", type=float, default=13.0)
    p.add_argument(
        "--independent-paths",
        action="store_true",
        help="Diagnostic control: disable inter-piece contact only",
    )
    a = p.parse_args()
    r = run(a.cache, a.input, a.dt, a.clock_start, not a.independent_paths)
    a.output.write_text(json.dumps(r, allow_nan=False) + "\n", encoding="utf8")
    print(
        {
            k: r[k]
            for k in [
                "idsReleased",
                "apertures",
                "unambiguousPassages",
                "activeWindow",
                "processingOnly",
            ]
        },
        "ball contacts",
        len(r["sphereInteractions"]),
    )
