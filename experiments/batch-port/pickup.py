"""Replay single floor pickup with the split port positively closed and the tongue stowed."""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "cad/own-zone-upper"))
sys.path.insert(0, str(HERE.parent / "own-zone-cycle"))
from prepare_upper import parts
from intake import simulate_intake


def check():
    parts_list = parts()[1]
    original = next(p for p in parts_list if p["name"] == "rear lift custody gate")
    lo, hi = original["lower"], original["upper"]
    assert lo == [167, -65, 134] and hi == [171, 65, 550]
    # These tiled rectangles have the same rectangular outer contact boundary.
    # Testing all elementary cells also detects internal holes and overlap.
    tiles = [
        (-65, 65, 134, 226),
        (-65, 0, 226, 400),
        (0, 65, 226, 400),
        (-65, 65, 400, 550),
    ]
    for y in (-32.5, 32.5):
        for z in (180, 313, 475):
            assert sum(y0 < y < y1 and z0 < z < z1 for y0, y1, z0, z1 in tiles) == 1
    cases = {}
    for name, flags in (
        ("closed", {}),
        ("stalled roller", {"roller": False}),
        ("missing guides", {"guides": False}),
    ):
        trial = simulate_intake(parts_list, **flags)
        cases[name] = {k: trial[k] for k in ("crossing", "lifted", "events", "finalMm")}
    if not cases["closed"]["lifted"] or any(
        cases[name]["lifted"] for name in ("stalled roller", "missing guides")
    ):
        raise ValueError("Pickup comparison changed")
    return {
        "reference": "R2C rear guide in millimetres; tongue fully withdrawn from the pickup corridor",
        "closedTilesYZMm": tiles,
        "xMm": [lo[0], hi[0]],
        "cases": cases,
    }


if __name__ == "__main__":
    (HERE / "pickup.json").write_text(
        json.dumps(check(), indent=2) + "\n", encoding="utf8"
    )
