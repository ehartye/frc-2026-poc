"""Rebuild or summarize the field-source pickup, legal stock and bumper-opening trials."""

import argparse
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = [
    ("original", "fixed", 0.00025),
    ("stalled", "stalled", 0.00025),
    ("raised", "reach", 0.00025),
    ("single-fine", "load", 0.000125),
    ("single-coarse", "load", 0.00025),
    ("single-unpowered-storage", "load-stalled-belt", 0.00025),
    ("single-locked", "load-locked-gate", 0.00025),
    ("pair-fine", "paired", 0.000125),
    ("pair-coarse", "paired", 0.00025),
    ("pair-locked", "paired-locked-gate", 0.00025),
]


def emit(path, data):
    path.write_text(
        json.dumps(data, allow_nan=False, separators=(",", ":")) + "\n", encoding="utf8"
    )


def run(raw, execute):
    summary = {}
    frames = None
    for name, mode, dt in CASES:
        output = raw / ("loading-" + name + ".json")
        if execute:
            subprocess.run(
                [
                    "node",
                    HERE / "stock.mjs",
                    HERE / "stock-register.json",
                    output,
                    "blue-depot-03",
                    mode,
                    str(dt),
                ],
                check=True,
            )
        d = json.loads(output.read_bytes())
        if d["initialHits"] or len({x["id"] for x in d["initial"]}) != len(
            d["initial"]
        ):
            raise ValueError("Source starts overlapped or reused an identity")
        dock = d.get("cartridge", {})
        ids = dock.get(
            "retainedSourceIds",
            [dock["retainedSourceId"]] if dock.get("retainedSourceId") else [],
        )
        retained = ids + dock.get("retainedPreloads", [])
        summary[name] = {
            "dtS": dt,
            "mode": mode,
            "initialIds": [p["id"] for p in d["initial"]],
            "firstRollerTouch": d["firstRollerTouch"],
            "atShelf": d["settled"],
            "atHead": d["handoffs"],
            "laneEvents": dock.get("events", []),
            "retainedSourceIds": ids,
            "retainedPreloads": dock.get("retainedPreloads", []),
            "finalRetained": [p for p in d["final"] if p["id"] in retained],
        }
        if name == "pair-fine":
            frames = [
                [row[0], *[piece for piece in row[1:] if piece[0] in ids]]
                for row in d["coords"]
            ]
    if (
        summary["pair-fine"]["retainedSourceIds"]
        != summary["pair-coarse"]["retainedSourceIds"]
        or len(summary["pair-fine"]["retainedSourceIds"]) != 2
    ):
        raise ValueError("Paired result did not repeat")
    clocks = []
    for spent in (0, 1, 8):
        kept = 8 - spent
        for time in (5, 30):
            clocks.append(
                {
                    "availabilityS": time,
                    "autoPreloadsSpent": spent,
                    "stillOnboard": kept,
                    "sourcePiecesNeeded": 24 - kept,
                    "sourcePiecesPerS": (24 - kept) / time,
                    "maxSecondsPerPairOnAverage": time / ((24 - kept + 1) // 2),
                }
            )
    return {
        "schema": "rebuilt-depot-loading/1",
        "simulationScope": "Prebuild contact simulation, parked chassis, one collection operation at the first blue depot approach",
        "trials": summary,
        "clocks": clocks,
        "pairedFrames": frames,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scratch", type=Path)
    parser.add_argument("--summarize-only", action="store_true")
    args = parser.parse_args()
    args.scratch.mkdir(parents=True, exist_ok=True)
    emit(HERE / "results.json", run(args.scratch, not args.summarize_only))
