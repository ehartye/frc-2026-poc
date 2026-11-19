"""Build the student service ledger from both complete numerical refinements."""

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REFINEMENTS = [("500us", "0.09"), ("250us", "125us")]


def load(path):
    return json.loads(path.read_bytes())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unpack(raw, label, mechanism, model, record_frames):
    states = load(raw / f"tiered-receiver-{mechanism}.json")
    field = load(raw / f"{model}-{label}.json")
    release = {p["id"]: p for p in states["releases"]}
    if len(release) != 24 or set(release) != {row["id"] for row in field["pieces"]}:
        raise ValueError("The field and receiver must account for the same 24 IDs")
    rows = []
    for i, row in enumerate(field["pieces"]):
        ident = row["id"]
        wheel = release[ident]
        if wheel["timeS"] != row["releaseS"]:
            raise ValueError("Field and receiver release clocks disagree")
        cleared = row["sharedClearS"]
        aperture = row["apertureS"]
        time = row["releaseS"]
        item = {
            key: row[key]
            for key in (
                "id",
                "releaseS",
                "apertureS",
                "sharedClearS",
                "channel",
                "countWithin",
                "processingOnly",
            )
        }
        item.update(
            slot=1 + i % 6,
            wheelRecoveryRadS=wheel["firstContact"]["rotorSpeedRadS"],
            previousReleaseGapS=None if i == 0 else time - rows[-1]["releaseS"],
            latestStrictReleaseShiftS=None
            if cleared is None
            else 25 - (cleared - time),
            latestProcessingReleaseShiftS=None
            if cleared is None
            else min(25 - (aperture - time), 28 - (cleared - time)),
            lastPossibleRimMarginsM=[
                r["marginM"]
                for r in row["nativeRimPassages"]
                if r.get("marginM") is not None
            ],
            nativeRimTouches=[
                name for name in row["nativeContacts"] if "Funnel Side" in name
            ],
            sensorInterruptions=[
                s["channel"] for s in field["sensorIntervals"] if ident in s["definite"]
            ],
            freeFlightTopM=wheel["positionM"][2]
            + wheel["velocityMps"][2] ** 2 / (2 * 9.80665)
            + 0.150114 / 2,
        )
        rows.append(item)
    result = {
        "fieldDtS": field["dt"],
        "mechanismDtS": states["dt"],
        "pieceContacts": field.get("pieceContactsEnabled", True),
        "inputWheelSha256": digest(raw / f"tiered-receiver-{mechanism}.json"),
        "fieldRawSha256": digest(raw / f"{model}-{label}.json"),
        "sphereInteractions": len(field["sphereInteractions"]),
        "rows": rows,
        "schedule": [
            {
                "startShiftS": start,
                "inside": sum(
                    r["sharedClearS"] is not None and start + r["sharedClearS"] < 25
                    for r in rows
                ),
                "processing": sum(
                    r["sharedClearS"] is not None
                    and start + r["apertureS"] < 25 <= start + r["sharedClearS"] <= 28
                    for r in rows
                ),
            }
            for start in (13, 11, 8)
        ],
        "aperturesBySlot": [
            sum(r["apertureS"] is not None and r["slot"] == s for r in rows)
            for s in range(1, 7)
        ],
    }
    if record_frames:
        result["frames"] = field["trajectory"]
    return result


def build(raw):
    trials = [
        unpack(raw, label, mechanic, "batch-rim", True)
        for label, mechanic in REFINEMENTS
    ]

    def common(key):
        return sorted(
            set.intersection(*[{r["id"] for r in t["rows"] if r[key]} for t in trials])
        )

    field = load(HERE.parent / "own-zone-cycle/single-piece.json")
    return {
        "schema": "rebuilt-packed-service/1",
        "studentCadSha256": field["cadSha256"],
        "fieldSourceSha256": field["supplierFieldSha256"],
        "openingM": field["registeredHub"]["centerM"],
        "fixedCases": {
            name: load(raw / f"finite-{name}.json")["count"]
            for name in ("fixed", "belts-off", "split", "bridge", "diagonal", "sweep")
        },
        "withoutWheelRecovery": len(load(raw / "tiered-receiver-0.json")["releases"]),
        "trials": trials,
        "bothInside": common("countWithin"),
        "bothComplete": common("sharedClearS"),
        "control": unpack(raw, "250us", "125us", "independent-field", False),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw", type=Path)
    parser.add_argument("--out", type=Path, default=HERE / "results.json")
    args = parser.parse_args()
    args.out.write_text(
        json.dumps(build(args.raw), allow_nan=False, separators=(",", ":")) + "\n",
        encoding="utf8",
    )
