"""Produce the student evidence rows from the modeled R2C intake and real registered field."""

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "cad/own-zone-upper"))
from prepare_upper import parts
from intake import simulate_intake
from target import register, projectile
from hub_contact import Hub


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("local_field_folder", type=Path)
    a = p.parse_args()
    cache = a.local_field_folder
    reg = register(json.loads((cache / "field-registration.json").read_bytes()))
    stock = parts()[1]
    result = {
        "edition": "Kickoff V0 and TU00. Physical field STEP created January 7 and published January 10.",
        "supplierFieldSha256": "2ad90e42f2c2db0fab5b22bb65aa0851089e414d568d4ebd127624fa230c7671",
        "cadSha256": hashlib.sha256(
            (ROOT / "cad/own-zone-upper/own-zone-public.step").read_bytes()
        ).hexdigest(),
        "registeredHub": reg,
        "grid": [],
        "controls": {},
    }

    def simple(r):
        return {k: v for k, v in r.items() if k != "trajectory"}

    for label, kwargs in [
        ("stopped roller", {"roller": False}),
        ("prior missing guides", {"guides": False}),
        ("no approach or roller", {"drive": 0, "roller": False}),
    ]:
        result["controls"][label] = simple(simulate_intake(stock, **kwargs))
    for stiffness in [7500, 15000, 30000]:
        for speed in [0.5, 0.7, 0.9]:
            config = {
                "stiffness": stiffness,
                "rimMps": 0.032 * 5676 * math.tau / 60 * speed,
                "mu": 0.65,
            }
            r = simulate_intake(stock, wheels=config)
            a = projectile(reg, r)
            result["grid"].append(
                {
                    "contactNperM": stiffness,
                    "initialNoLoadFraction": speed,
                    "case": simple(r),
                    "flight": simple(a),
                }
            )
    h = Hub(cache / "blue-hub-private.npz")
    reference = {}
    for step in [0.0001, 0.00005]:
        r = simulate_intake(
            stock,
            h=step,
            wheels={
                "stiffness": 30000,
                "rimMps": 0.032 * 5676 * math.tau / 60 * 0.7,
                "mu": 0.65,
            },
        )
        a = projectile(reg, r)
        c = h.carry(a, step * 5, r["release"]["spinRadS"])
        result.setdefault("refinements", []).append(
            {"mechanism": simple(r), "flight": simple(a), "field": simple(c)}
        )
        reference = {
            "mechanismRows": r["trajectory"],
            "flightRows": c["trajectory"],
            "atPickup": r["crossing"]["timeS"],
            "atLift": r["lifted"]["timeS"],
            "atRelease": r["release"]["timeS"],
            "headingRad": a["headingRad"],
            "robotFieldM": a["robotFieldM"],
            "centerM": reg["centerM"],
        }
    for name, data in [("single-piece.json", result), ("replay.json", reference)]:
        (HERE / name).write_text(
            json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf8"
        )
    print(
        "Nine contact conditions, three controls and two continuous refinements recorded"
    )


if __name__ == "__main__":
    main()
