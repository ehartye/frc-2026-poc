"""Check the limiting dressed-cable side corridor between the maximum battery and retained deck."""

import argparse
import json
from pathlib import Path
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from passive_job import recipe
from offline import machine, shape
from shop import round_stock, rect
from drivetrain_fit import vol


def compare():
    job = recipe()
    case = shape(rect([-133, -37, 48], [50, 41, 217]))
    deck = machine(job["parts"]["right electronics deck"]["features"])
    other = machine(job["parts"]["left electronics deck"]["features"])
    rows = []
    for side, fixed, center in (("right", deck, -40.5), ("left", other, 44)):
        for outer in (5, 6, 7, 8, 9.525):
            test = shape(
                round_stock([-105, center, 125], [-75, center, 125], outer / 2)
            )
            intersections = [
                vol(BRepAlgoAPI_Common(test, part).Shape()) for part in (case, fixed)
            ]
            gaps = [
                BRepExtrema_DistShapeShape(test, part).Value() for part in (case, fixed)
            ]
            rows.append(
                dict(
                    side=side,
                    outerDiameterMm=outer,
                    gapToCaseAndDeckMm=[round(n, 5) for n in gaps],
                    commonWithCaseAndDeckMm3=[round(n, 4) for n in intersections],
                    passesHalfMmRadialAllowance=all(v < 0.01 for v in intersections)
                    and min(gaps) >= 0.49999,
                )
            )
    return dict(
        predecessorStepSha256=job["stepSha256"],
        maxCaseMm=[183, 78, 169],
        sampleAxisXmm=[-105, -75],
        rightSideWidthMm=7,
        leftSideWidthMm=6,
        rows=rows,
        scope="30 mm straight-gauge cross section through the actual side-deck thickness. A wire carried beside the maximum-size case must pass the deck here during lowering if routed along that side. A matched terminal or continuous routed cable has not been registered. The 9.525 mm trial is a sample gauge, not the installed am-4483 insulation diameter. No positive result establishes bend or branch slack.",
    )


if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("out", type=Path)
    d = a.parse_args()
    r = compare()
    d.out.write_text(json.dumps(r, indent=2) + "\n", encoding="utf8")
