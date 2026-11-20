"""Check the deployer throughout its stroke and the loaded stroke on the same carriage."""

import json, math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def audit():
    parts = {
        r["id"]: r["boundsMm"]
        for r in json.loads((ROOT / "cad/tower-lift/appearances.json").read_bytes())[
            "solids"
        ]
    }
    screw = parts["extension screw envelope"]
    nut = parts["extension deployment nut"]
    stop = parts["extension rear bearing and stop"]
    sleeve = parts["right extension sleeve"]
    rail = parts["right extending rail"]
    shaft_axis = [(a + b) / 2 for a, b in zip(screw[1:3], screw[4:6])]
    nut_axis = [(a + b) / 2 for a, b in zip(nut[1:3], nut[4:6])]
    states = json.loads((HERE / "motion.json").read_bytes())
    min_overlap = min_rail = float("inf")
    min_stop = float("inf")
    for row in states:
        x = 1000 * row["deploy"]
        overlap = min(screw[3], nut[3] - x) - max(screw[0], nut[0] - x)
        engagement = min(sleeve[3], rail[3] - x) - max(sleeve[0], rail[0] - x)
        stop_gap = nut[0] - x - stop[3]
        min_overlap = min(min_overlap, overlap)
        min_rail = min(min_rail, engagement)
        min_stop = min(min_stop, stop_gap)
    if (
        min_overlap < 19.99
        or min_rail < 86.99
        or min_stop < -0.01
        or math.dist(shaft_axis, nut_axis) > 0.01
    ):
        raise ValueError("Incomplete deployment, stop or guide engagement")
    run = json.loads((HERE / "support.json").read_bytes())[0]
    reactions = run["atAssessment"]["hookXZ"]
    rpm = 1.5 * 0.215 / 1.24 / 0.004 * 60
    return dict(
        schema="r2c-t1/axial-deployment@1",
        workingDeployMm=215,
        workingLiftMm=100,
        nativeLiftMm=115,
        minimumEngagementMm=min_overlap,
        leadMm=4,
        minimumEngagedTurns=min_overlap / 4,
        radialCenterErrorMm=math.dist(shaft_axis, nut_axis),
        minimumGuideOverlapMm=min_rail,
        minimumStopClearanceMm=min_stop,
        nominalAtStopAxialLoadN=-sum(q[0] for q in reactions),
        peakUnloadedCommandRpm=rpm,
        assumedNoLoadRpm=5500,
        scope="Smooth motion requires the indicated shaft speed; screw, nut and motor are packaging envelopes. Powered friction, bearings, thread stripping, installed retention and motor selection need independent qualification.",
    )


if __name__ == "__main__":
    result = audit()
    (HERE / "extension.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf8", newline="\n"
    )
    print(result)
