"""Rebuild the contact runs and public summary against a registered project-local field."""

import argparse
import subprocess
import sys
from pathlib import Path

from report import HERE, REFINEMENTS, build
import json


def run(raw):
    if not (raw / "blue-hub-private.npz").is_file():
        raise FileNotFoundError(
            "Reconstruct blue-hub-private.npz from the pinned field source first"
        )
    for mode in ("fixed", "belts-off", "split", "bridge", "diagonal", "sweep"):
        subprocess.run(
            ["node", HERE / "port.mjs", mode, raw / f"finite-{mode}.json"], check=True
        )
    for label, step, torque in (
        ("0", "0.00025", "0"),
        ("0.09", "0.00025", "0.09"),
        ("125us", "0.000125", "0.09"),
    ):
        subprocess.run(
            [
                "node",
                HERE / "magazine.mjs",
                raw / f"tiered-receiver-{label}.json",
                "12",
                step,
                "1.4",
                ".9",
                "12",
                "7",
                "1",
                torque,
            ],
            check=True,
        )
    for label, mechanic in REFINEMENTS:
        step = ".0005" if label == "500us" else ".00025"
        for model in (
            ["batch-rim", "independent-field"] if label == "250us" else ["batch-rim"]
        ):
            args = [
                sys.executable,
                HERE / "shared_field.py",
                raw,
                raw / f"tiered-receiver-{mechanic}.json",
                raw / f"{model}-{label}.json",
                "--dt",
                step,
            ]
            if model == "independent-field":
                args.append("--independent-paths")
            subprocess.run(args, check=True)
    return build(raw)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw", type=Path)
    result = run(parser.parse_args().raw.resolve())
    (HERE / "results.json").write_text(
        json.dumps(result, allow_nan=False, separators=(",", ":")) + "\n",
        encoding="utf8",
    )
