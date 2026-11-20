"""Extract the bounded collection handoff, then bind the loaded transit to those exact bytes."""

import argparse
import hashlib
import json
from pathlib import Path


def save(path, obj):
    data = (json.dumps(obj, indent=2) + "\n").encode()
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def process(raw, output, include_transit):
    output.mkdir(parents=True, exist_ok=True)
    for step in (125, 250):
        run = json.loads((raw / f"loaded-field-{step}.json").read_bytes())
        dock = run["cartridge"]
        checkpoint = dock["checkpoint"]
        boundary = output / f"depot-{step}us.json"
        digest = save(boundary, checkpoint)
        end_wall = run["fieldBoundary"]
        centers = [
            checkpoint["robotFieldXYM"][0] - p["positionM"][0]
            for p in checkpoint["remainingField"]
        ]
        result = {
            "dt": run["dt"],
            "mode": run["mode"],
            "gateClosedS": checkpoint["timeS"],
            "onboardAt5": len(dict(run["custody"])[5]),
            "admissions": [
                {"ids": row["sourceIds"], "closeS": row["closedS"]}
                for row in dock["rows"]
            ],
            "sourceBound": {"file": boundary.name, "sha256": digest},
            "closestLooseCenterToWallAtHandoffM": min(centers) - end_wall["wallX"],
            "fieldBoundary": end_wall,
            "closestTire": run["closestWheel"],
        }
        if include_transit:
            carry = json.loads(
                (raw / f"loaded-bounded-transfer-{step}.json").read_bytes()
            )
            if carry["sourceSha256"] != digest:
                raise ValueError("Travel used a different loading boundary.")
            end = output / f"arrived-{step}us.json"
            result["end"] = {"file": end.name, "sha256": save(end, carry["end"])}
            result["travel"] = {
                k: carry[k]
                for k in (
                    "sourceSha256",
                    "departS",
                    "arriveS",
                    "readyS",
                    "wheel",
                    "minimumDoorM",
                    "minimumWallM",
                    "firstEnvelopeEscape",
                    "closestLooseTire",
                    "firstBodyStockContact",
                )
            }
            result["travel"]["retainedAtReady"] = carry["samples"][-1]["retained"]
            result["travel"]["initialPayloadIds"] = carry["initial"]
        save(output / f"study-{step}us.json", result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--transit", action="store_true")
    args = parser.parse_args()
    process(args.raw, args.output, args.transit)
