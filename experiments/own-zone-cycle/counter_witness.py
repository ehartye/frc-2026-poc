"""Read the outgoing FUEL against all physically possible rays between each registered housing pair."""

import argparse
import itertools
import json
from pathlib import Path

import numpy as np
from counter_drive import CounterDrive
from hub_contact import Hub
from target import R


def corners(bounds):
    lo, hi = np.array(bounds).reshape(2, 3) / 1000
    return np.array(list(itertools.product(*zip(lo, hi))))


class BeamWitness:
    def __init__(self, registered):
        bounds = registered["markerBoundsByType"]
        order = lambda b: (b[1] + b[4]) / 2
        sensors = sorted(bounds["Counting Sensor"], key=order)
        reflectors = sorted(bounds["Sensor Reflector"], key=order)
        self.channels = []
        self.profiles = []
        for sensor, reflector in zip(sensors, reflectors, strict=True):
            a = np.repeat(corners(sensor), 8, axis=0)
            b = np.tile(corners(reflector), (8, 1))
            gap = (max(min(a[:, 1]), min(b[:, 1])), min(max(a[:, 1]), max(b[:, 1])))
            # Open Y span strictly between the two physical housings.
            inner = tuple(sorted((gap[0], gap[1])))
            self.channels.append((a, b - a, inner))
            self.profiles.append(
                {
                    "enterS": None,
                    "leaveS": None,
                    "maxMarginM": None,
                    "firstCenterM": None,
                    "upstreamClear": False,
                    "downstreamClear": False,
                    "downstreamClearS": None,
                    "transitions": 0,
                }
            )
        self.interrupted = [False] * len(self.channels)

    def observe(self, time, center, velocity):
        for i, (a, delta, lane) in enumerate(self.channels):
            row = self.profiles[i]
            if center[0] + R < min(a[:, 0].min(), (a + delta)[:, 0].min()):
                if row["enterS"] is None:
                    row["upstreamClear"] = True
                continue
            if row["enterS"] is not None and center[0] - R > max(
                a[:, 0].max(), (a + delta)[:, 0].max()
            ):
                row["downstreamClear"] = True
                if row["downstreamClearS"] is None:
                    row["downstreamClearS"] = time
            margin = None
            if lane[0] < center[1] < lane[1]:
                frac = (center[1] - a[:, 1]) / delta[:, 1]
                # At the plane of the ball center, enclose the full possible optical bundle.
                intersections = a + frac[:, None] * delta
                margin = R - float(np.linalg.norm(intersections - center, axis=1).max())
                if row["maxMarginM"] is None or row["maxMarginM"] < margin:
                    row["maxMarginM"] = margin
            blocked = margin is not None and margin > 0
            if blocked and not self.interrupted[i]:
                row["transitions"] += 1
                if row["enterS"] is None:
                    row["enterS"] = time
                    row["firstCenterM"] = center.tolist()
            if not blocked and self.interrupted[i]:
                row["leaveS"] = time
            self.interrupted[i] = blocked

    def result(self):
        return [dict(channel=i + 1, **r) for i, r in enumerate(self.profiles)]


def run(cache, example, dt, speeds, duration, offset=0.0):
    study = json.loads(Path(__file__).with_name("single-piece.json").read_bytes())
    sample = study["refinements"][example]
    candidate = dict(sample["flight"])
    direction = np.array(
        [np.cos(candidate["headingRad"]), np.sin(candidate["headingRad"])]
    )
    candidate["releaseFieldM"] = (
        np.array(candidate["releaseFieldM"]) + np.r_[offset * direction, 0.0]
    ).tolist()
    candidate["robotFieldM"] = (
        np.array(candidate["robotFieldM"]) + offset * direction
    ).tolist()
    hub = Hub(cache / "blue-hub-private.npz")
    results = []
    for wheel, tube in speeds:
        sensor = BeamWitness(study["registeredHub"])
        case = hub.carry(
            candidate,
            dt,
            sample["mechanism"]["release"]["spinRadS"],
            seconds=duration,
            counter=CounterDrive(hub.part, wheel, tube),
            observe=sensor.observe,
        )
        results.append(
            {
                "wheelMps": wheel,
                "tubeMps": tube,
                "dt": dt,
                "seconds": duration,
                "towardHubOffsetM": offset,
                "releaseFieldM": candidate["releaseFieldM"],
                "channels": sensor.result(),
                **case,
            }
        )
    return results


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("cache", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--dt", type=float, default=0.0005)
    p.add_argument("--example", type=int, default=1)
    p.add_argument("--seconds", type=float, default=6.0)
    p.add_argument("--drive", nargs=2, type=float, action="append", required=True)
    p.add_argument("--offset", type=float, default=0.0)
    args = p.parse_args()
    rows = run(args.cache, args.example, args.dt, args.drive, args.seconds, args.offset)
    args.output.write_text(
        json.dumps(rows, indent=2, allow_nan=False) + "\n", encoding="utf8"
    )
    for row in rows:
        print(
            row["wheelMps"],
            row["tubeMps"],
            row["finalPositionM"],
            len(row["counterWheelsTouched"]),
            [
                (r["channel"], r["maxMarginM"], r["enterS"], r["downstreamClear"])
                for r in row["channels"]
            ],
        )
