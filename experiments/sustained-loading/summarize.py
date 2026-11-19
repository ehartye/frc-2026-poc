"""Extract the closed-gate boundary and compact clock comparison from raw simulations."""

import argparse
import hashlib
import json
from pathlib import Path

CASES = {
    "previous-gate": "loading-coupled-wheel",
    "combined-adverse": "loading-coupled-wheel-stall",
    "coarse-timed": "loading-final500",
    "timed-250us": "loading-final250",
    "timed-125us": "loading-final125",
}


def save(path, value):
    path.write_bytes((json.dumps(value, indent=2) + "\n").encode())


def summarize(raw, output):
    result = {}
    output.mkdir(parents=True, exist_ok=True)
    for name, stem in CASES.items():
        path = raw / f"{stem}.json"
        data = json.loads(path.read_bytes())
        cartridge = data["cartridge"]
        rows = cartridge["rows"]
        wheel = data["wheel"]
        counts = {
            str(int(t)): len(ids) for t, ids in data["custody"] if t in (0, 5, 25, 30)
        }
        result[name] = {
            "mode": data["mode"],
            "stockStart": data["source"],
            "stepS": data["dt"],
            "initialConflictsAbove1mm": data["initialHits"],
            "onboardByCollectionSecond": counts,
            "gateClosedS": rows[-1]["closedS"] if len(rows) == 8 else None,
            "admissions": [
                {k: row[k] for k in ("sourceIds", "dockedLanes", "tier", "closedS")}
                for row in rows
            ],
            "rail": {
                k: wheel.get(k)
                for k in (
                    "mass",
                    "cogM",
                    "mu",
                    "currentA",
                    "stableS",
                    "endM",
                    "maximum",
                )
            },
            "closestTire": data.get("closestWheel"),
            "terminalStage": cartridge["stage"],
        }
        if name.startswith("timed-"):
            checkpoint = cartridge["checkpoint"]
            assert len(checkpoint["payload"]) == 24
            assert len(checkpoint["remainingField"]) == 8
            assert set(checkpoint["sourceIds"]) == {
                i for row in rows for i in row["sourceIds"]
            }
            filename = f"{name}-checkpoint.json"
            save(output / filename, checkpoint)
            result[name]["checkpoint"] = filename
            result[name]["checkpointSha256"] = hashlib.sha256(
                (output / filename).read_bytes()
            ).hexdigest()
    save(output / "results.json", result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    summarize(args.raw, args.output)
