"""Compare identical registered contact histories with transverse sleeves and full-length tension ties."""

import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments/tower-climb"))
from support import run

CONDITIONS = {
    "nominal": {},
    "original heavy": {"mass": 68, "cog_x": 0.035},
    "soft upright bumper": {"mass": 68, "cog_x": 0.035, "bumper_k": 32000},
    "stiffer upright bumper": {"mass": 68, "cog_x": 0.035, "bumper_k": 128000},
    "forward CG": {"mass": 68, "cog_x": 0.050, "bumper_k": 64000},
    "forward stiff": {"mass": 68, "cog_x": 0.050, "bumper_k": 128000},
    "forward soft": {"mass": 68, "cog_x": 0.050, "bumper_k": 32000},
    "forward soft half step": {
        "mass": 68,
        "cog_x": 0.050,
        "bumper_k": 32000,
        "dt": 0.000125,
    },
    "missed two-hook set": {"mass": 68, "cog_x": 0.035, "lateral_error": 0.23},
    "thread release": {"mass": 68, "cog_x": 0.035, "thread_mu": 0.035},
    "power off early": {"mass": 68, "cog_x": 0.035, "powered_cut": 2},
    "lateral assembly tilt": {"mass": 68, "cog_x": 0.035, "roll_deg": 1.5},
}


def case(label, settings):
    peaks = dict(tensionN=0.0, compressionN=0.0, longitudinalN=0.0)

    def collect(t, theta, cg, contacts, brace, brace_force):
        c, s = math.cos(theta), math.sin(theta)
        forward = rear = horizontal = 0.0
        for _, x, z, wx, wz, fx, fz in contacts:
            xforce = c * fx + s * fz
            zforce = -s * fx + c * fz
            fore = ((x + 0.280) * zforce - (z - 0.1148) * xforce) / 0.100
            forward += fore
            rear += zforce - fore
            horizontal += xforce
        peaks["tensionN"] = max(peaks["tensionN"], forward, rear)
        peaks["compressionN"] = max(peaks["compressionN"], -forward, -rear)
        peaks["longitudinalN"] = max(peaks["longitudinalN"], abs(horizontal))

    observation = run(label, **settings, observe_contacts=collect)
    observation.pop("rows")
    # Assume all load feeds one side's fore/aft supports, and apply 2x to the resulting
    # modeled external reactions; these are explicit study choices, not measured extremes.
    preload = 750.0
    rod_area = 36.6
    steel_E = 200000.0
    al_E = 68900.0
    # Use the distance to the last engaged thread as an upper length bound.
    length = 745.0 - 61.5
    rodN = 2 * peaks["tensionN"] + preload
    mastN = 2 * peaks["compressionN"] + preload
    outer = 19.9
    wall = 2.85
    moment = (outer**4 - (outer - 2 * wall) ** 4) / 12
    # Subtract an upper bound for material removed at four outer corner radii.
    max_outer_radius = 2
    moment -= 4 * (1 - math.pi / 4) * max_outer_radius**2 * (outer / 2) ** 2
    unsupported = 744 - 114.8
    supports = {}
    for k in (1.0, 2.0):
        critical = math.pi**2 * al_E * moment / (k * unsupported) ** 2
        supports[str(k)] = {
            "elasticBucklingN": critical,
            "demandOverEuler": mastN / critical,
        }
    return {
        "settings": settings,
        "externalSingleSide": peaks,
        "historicalClimbObservation": observation,
        "previousSleeveOneWallStressMPa": 2
        * peaks["tensionN"]
        / (12.53 * (1.95 - 0.035)),
        "throughTie": {
            "assumedMaxPreloadN": preload,
            "tensionIncludingPreloadN": rodN,
            "threadAreaMm2": rod_area,
            "stressMPa": rodN / rod_area,
            "elasticExtensionFromZeroMm": rodN * length / (rod_area * steel_E),
            "topFlangePlateBearingMPa": rodN / 94.8437,
            "bottomWasherRailBearingMPa": rodN / 152.8071,
            "headFlangeShearMPa": rodN
            / ((4 * (13.8 - 4.5) + 4 * math.sqrt(2) * 2.25) * 4),
            "threadHalfPitchShearScreenMPa": rodN / (math.pi * 6.647 * 0.5 * 24.5),
            "threadScreenEngagementMm": 24.5,
            "mastCompressionN": mastN,
            "mastCompressionAtMeasuredFaceMPa": mastN / 202.07,
            "minimumWallMm": wall,
            "maxReceivedOuterCornerRadiusMm": max_outer_radius,
            "minimumSecondMomentMm4": moment,
            "mastEuler": supports,
            "lowerKeyShearProjectedPressureMPa": 2
            * peaks["longitudinalN"]
            / (3.175 * 12.60),
            "upperKeyShearProjectedPressureMPa": 2
            * peaks["longitudinalN"]
            / (6 * (13.8 - 4.5)),
        },
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    data = {name: case(name, parameters) for name, parameters in CONDITIONS.items()}
    args.output.write_text(
        json.dumps(
            {
                "cases": data,
                "scope": "Planar registered forces; the tension rod bypasses mast wall fastener bearing. Scenario mass, stiffness, friction, preload and CG are assumptions. Euler is elastic; end fixing, imperfections, fatigue and impact strength are unqualified. A single hook does not establish yaw closure.",
            },
            indent=2,
        )
        + "\n",
        encoding="utf8",
    )
