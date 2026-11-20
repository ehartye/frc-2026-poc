"""Reconstruct signed mast reactions from the registered project climb integrator (SI units)."""

import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments/tower-climb"))
from support import run

SCENARIOS = {
    "nominal": {},
    "finer": {"dt": 0.000125},
    "loaded": {"mass": 68, "cog_x": 0.035},
    "early-cut": {"powered_cut": 2},
    "stalled-drive": {"disable": True},
    "missed-rung": {"lateral_error": 0.23},
    "released-thread": {"thread_mu": 0.035},
    "roll-error": {"roll_deg": 1.5},
}


def compare(name, parameters, reference):
    maxima = {}
    at_assessment = {}

    def observe(time, pitch, cg, contacts, upright_position, upright_force):
        # The hook structure applies these external rung forces to the mast system.
        # The upright brace reaction travels by a different chassis path. Do not double count it.
        c, s = math.cos(pitch), math.sin(pitch)
        projections = []
        for hook, x, z, _, _, world_fx, world_fz in contacts:
            fx = c * world_fx + s * world_fz
            fz = -s * world_fx + c * world_fz
            fore_tension = ((x + 0.280) * fz - (z - 0.1148) * fx) / 0.100
            projections.append(
                ((-0.088, 0.088)[hook], fx, fore_tension, fz - fore_tension)
            )
        for model in ("simple crossbeam", "same-side direct", "all demand one side"):
            for side in (-1, 1) if model != "all demand one side" else (1,):
                fore, aft, side_force = 0.0, 0.0, 0.0
                for hook_y, fx, forward, rear in projections:
                    if model == "simple crossbeam":
                        share = (0.326 + side * hook_y) / 0.652
                    elif model == "same-side direct":
                        share = float(side * hook_y > 0)
                    else:
                        share = 1.0
                    fore += share * forward
                    aft += share * rear
                    side_force += share * fx
                key = model + "/" + ("left" if side == 1 else "right")
                at_assessment[key] = {
                    "foreNetUpN": fore,
                    "aftNetUpN": aft,
                    "horizontalN": side_force,
                }
                envelope = maxima.setdefault(key, {})
                for metric, value in (
                    ("foreTensionN", fore),
                    ("foreCompressionN", -fore),
                    ("aftTensionN", aft),
                    ("aftCompressionN", -aft),
                    ("longitudinalShearN", abs(side_force)),
                ):
                    if value > envelope.get(metric, {}).get("loadN", -math.inf):
                        envelope[metric] = {"loadN": value, "timeS": time}

    current = run(name, **parameters, observe_contacts=observe)
    current.pop("rows")
    if current != reference:
        raise ValueError("The baseline climb no longer reproduces: " + name)
    return {"timeStepS": current["dt"], "peak": maxima, "assessment": at_assessment}


def wall_screen(cases):
    demand = max(
        x["peak"]["all demand one side/left"]["foreTensionN"]["loadN"]
        for x in cases.values()
    )
    # Comparison gauges below are procurement/receiving minima, not asserted thread tolerances.
    rows = []
    for designation, assumed_root in (("M6", 4.65), ("M8", 6.2)):
        for loaded_fraction in (0.5, 0.6, 1.0):
            stress = 2 * demand * loaded_fraction / (2 * assumed_root)
            rows.append(
                dict(
                    fastener=designation,
                    minimumReceivedThreadRootMm=assumed_root,
                    singleBoltLoadFactor=2.0,
                    maximumWallShare=loaded_fraction,
                    projectedWallStressMPa=stress,
                    bulkProofComparisonMPa=150,
                    ratioToBulkProof=stress / 150,
                )
            )
    factored = 2 * demand
    sleeve_min = 12.53
    wall_min = 1.95
    end_recess_max = 0.035
    bearing_land = wall_min - end_recess_max
    hole_max = 12.60
    min_width = 19.90
    horizontal = max(
        v["peak"]["all demand one side/left"]["longitudinalShearN"]["loadN"]
        for v in cases.values()
    )
    paths = {
        "singleSleeveOneWallProjectedBearingMPa": factored
        / (sleeve_min * bearing_land),
        "bothWallsMastNetTensileMPa": factored
        / (2 * wall_min * (min_width - hole_max)),
        "oneSleevePlaneShearMPa": factored / (math.pi / 4 * (sleeve_min**2 - 8.55**2)),
        "drawPilotNetTensionMPa": factored / (math.pi / 4 * (12.6**2 - 8**2)),
        "drawScrewTensileStressMPa": factored / 36.6,
        "railBottomWasherBearingMPa": factored / 152.8071,
        "railPilotHorizontalBearingMPa": (2 * horizontal) / (12.6 * 3.175),
        "thinnedMastWall1_6mmMPa": factored / (sleeve_min * (1.60 - end_recess_max)),
    }
    return {
        "fittedSleeve": {
            "demandFactor": 2,
            "minimumTubeWallMm": wall_min,
            "minimumOuterTubeWidthMm": min_width,
            "maxSleeveEndRecessMm": end_recess_max,
            "maxInstalledBoreMm": hole_max,
            "minSleeveDiameterMm": sleeve_min,
            "maximumHorizontalN": horizontal,
            "stressMPa": paths,
            "scope": "One transverse sleeve or one of its two walls carries the full load in the indicated tensile/shear/bearing check. Two-wall mast net area is a separate section. Gross material proof comparisons are not working fatigue or joint ratings.",
        },
        "climbMaxN": demand,
        "scope": "One cross-bolt carries the full tension. Both shank-bearing planes conservatively use the gauge thread root. The near/far wall split is varied. Wall, fatigue, weld, compression and allowable joint ratings require separate evidence.",
        "rows": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    reference = {
        c["name"]: c
        for c in json.loads(
            (ROOT / "experiments/tower-climb/support.json").read_bytes()
        )
    }
    cases = {
        name: compare(name, params, reference[name])
        for name, params in SCENARIOS.items()
    }
    args.output.write_text(
        json.dumps({"cases": cases, "fastenerComparison": wall_screen(cases)}, indent=2)
        + "\n",
        encoding="utf8",
    )
