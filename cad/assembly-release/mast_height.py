"""Bound the height of actual tied-head geometry under declared wheel-height disturbances."""

import argparse
import hashlib
from itertools import combinations, product
import json
from pathlib import Path

import numpy as np

from mast_ties import build
from offline import machine
from supplier import bounds
from swerve import layout


def run(head_receipt):
    parts, _, _, _ = build()
    head = json.loads(head_receipt.read_bytes())
    sites = layout()[3]
    supports = np.array(
        [[s["translation"][0], s["translation"][1], 1] for s in sites], dtype=float
    )
    features = {
        n: bounds(machine(p["features"]))
        for n, p in parts.items()
        if n.endswith(" upper plate key")
    }
    for suffix, sign in (("left", 1), ("right", -1)):
        # Include the full diameter of the proposed M5 shaft at its highest point.
        y = sign * 305
        features[suffix + " project head journal"] = [
            -242.5,
            y - 2.5,
            head[suffix]["highestJournalZ"],
            -237.5,
            y + 2.5,
            head[suffix]["highestJournalZ"],
        ]
    cases = {}
    for uncertainty in (0.0, 1.0, 2.0, 3.0):
        maxima = {n: {"heightMm": -np.inf} for n in features}
        for offsets in product((-uncertainty, uncertainty), repeat=4):
            for feet in combinations(range(4), 3):
                # Three touching wheels establish a plane. A fourth can unload but
                # must not pass through the floor. Leaving CG unconstrained covers
                # a superset of equilibria and conservatively bounds these heights.
                a, b, c = np.linalg.solve(
                    supports[list(feet)], np.array(offsets)[list(feet)]
                )
                if min(supports @ [a, b, c] - offsets) < -1e-9:
                    continue
                for name, box in features.items():
                    # Unit-normal rotation lowers the vertical projection of
                    # positive local Z. Keeping all of Z is an upper bound.
                    x = box[3] if a >= 0 else box[0]
                    y = box[4] if b >= 0 else box[1]
                    height = box[5] + a * x + b * y + c + 0.5
                    if height > maxima[name]["heightMm"]:
                        maxima[name] = dict(
                            heightMm=height,
                            marginMm=762 - height,
                            wheelDeltaMm=offsets,
                            supporting=[sites[i]["name"] for i in feet],
                        )
        cases[str(uncertainty)] = maxima
    return dict(
        headReceiptSha256=hashlib.sha256(head_receipt.read_bytes()).hexdigest(),
        legalHeightMm=762,
        verticalMachiningAllowanceMm=0.5,
        cases=cases,
        basis="Four wheel datums from the selected module layout. Wheel delta is an assumed effective change in each loaded wheel support height on a common flat floor. The three-point plane uses the vertex cases of a bounded four-wheel interval. Positive local body height is left unshortened for a conservative small-tilt bound. This does not measure actual wheel or assembly tolerances or certify field-floor conditions.",
    )


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("output", type=Path)
    cli.add_argument(
        "--head",
        type=Path,
        default=Path(__file__).resolve().parents[2]
        / "experiments/tower-climb/head-support/recessed-head-fit.json",
    )
    args = cli.parse_args()
    args.output.write_text(json.dumps(run(args.head), indent=2) + "\n", encoding="utf8")
