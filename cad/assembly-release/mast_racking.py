"""Sweep an independently slipped side of the held crosshead against four actual sleeve/mast pairs."""

import argparse
import hashlib
import json
import math
from pathlib import Path

from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec

from drivetrain_fit import vol
from mast_ties import build
from offline import machine
from supplier import bounds
from verify_products import products


def transform(s, t):
    return BRepBuilderAPI_Transform(s, t, False).Shape()


def run():
    root = Path(__file__).resolve().parents[2]
    path = root / "cad/assembly-release/foundation-student.step"
    parked = products(path)
    parts, _, _, _ = build()
    move = gp_Trsf()
    move.SetTranslation(gp_Vec(0, 0, -100))
    sleeves = {}
    for side in ("left", "right"):
        for rank, mast in (("forward", " mast"), ("aft", " aft mast")):
            name = f"{side} {rank} carriage sleeve"
            sleeves[name] = (
                transform(parked[name], move),
                machine(parts[side + mast]["features"]),
            )
    results = {}
    for held, sign in (("left", 1), ("right", -1)):
        nut = bounds(parked[held + " driven nut"])
        screw = bounds(parked[held + " lead screw envelope"])
        pivot = [(screw[i] + screw[i + 3]) / 2 for i in (0, 1)]
        pivot.append((nut[2] + nut[5]) / 2 - 100)
        axis = gp_Ax1(gp_Pnt(*pivot), gp_Dir(1, 0, 0))
        spacing = 2 * abs(pivot[1])

        def contacts(delta):
            rotation = gp_Trsf()
            rotation.SetRotation(axis, -sign * math.asin(delta / spacing))
            return {
                n: abs(vol(BRepAlgoAPI_Common(transform(s, rotation), mast).Shape()))
                for n, (s, mast) in sleeves.items()
            }

        rows = {str(d): contacts(d) for d in (0, 1, 2, 4, 8, 12, 16, 24, 32, 48)}
        previous = 0
        for text, values in rows.items():
            following = float(text)
            if max(values.values()) > 0.005:
                break
            previous = following
        else:
            raise ValueError("No failed sleeve control")
        for _ in range(14):
            middle = (previous + following) / 2
            if max(contacts(middle).values()) > 0.005:
                following = middle
            else:
                previous = middle
        results[held] = {
            "heldNutPivotMm": pivot,
            "screwSpacingMm": spacing,
            "firstAboveFiveThousandthsMm3BracketMm": [previous, following],
            "rolledDegrees": math.degrees(math.asin(following / spacing)),
            "observedAtUpperBracketMm3": contacts(following),
            "slipStatesMm": rows,
        }
    return {
        "sourceStepSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "mastRecipeSha256": hashlib.sha256(
            Path(__file__).with_name("mast_ties.py").read_bytes()
        ).hexdigest(),
        "symmetricAt100mmGapMm": {
            n: BRepExtrema_DistShapeShape(s, mast).Value()
            for n, (s, mast) in sleeves.items()
        },
        "heldSide": results,
        "scope": "One screw axis stays at full working stroke. The other screw backdrives while a hypothetical rigid carriage remains free to roll about the held nut center. This favorable articulation measures sleeve/mast interference from differential displacement. Actual screw nuts, bearings, alignment, frame stiffness, brake loading, elastic contact, time to slip and posture after binding require additional evidence.",
    }


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("output", type=Path)
    args = cli.parse_args()
    args.output.write_text(json.dumps(run(), indent=2) + "\n", encoding="utf8")
