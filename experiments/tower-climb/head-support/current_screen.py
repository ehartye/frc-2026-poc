"""Predeclared matched alternatives for a jam-bounded prebuild lift drive."""

import json, sys
from pathlib import Path

here = Path(__file__).resolve().parent
sys.path.insert(0, str(here.parent))
from support import run

# A project screening fraction of C0 (0.5) is a comparison target, not an approved working load.
# Choose 4.5 A from the worst of the declared friction intervals before rerunning the climb.
profiles = {
    "nominal": {},
    "soft-forward": {"mass": 68.0, "cog_x": 0.050, "bumper_k": 32000},
    "tilt": {"mass": 68.0, "cog_x": 0.035, "roll_deg": 1.5},
    "low-thread-friction": {"mass": 68.0, "cog_x": 0.035, "thread_mu": 0.035},
    "high-thread-friction": {
        "mass": 68.0,
        "cog_x": 0.050,
        "bumper_k": 32000,
        "thread_mu": 0.21,
    },
    "tilt-high-friction": {
        "mass": 68.0,
        "cog_x": 0.035,
        "roll_deg": 1.5,
        "thread_mu": 0.21,
    },
}
out = {}
for label, settings in profiles.items():
    out[label] = {}
    for amps in (23.0, 4.5):
        r = run(label, motor_a=amps, **settings)
        out[label][str(amps)] = {
            "settings": settings,
            "cutS": r["cutS"],
            "firstClearS": r["firstClearS"],
            "lostAfterCutS": r["lostAfterCutS"],
            "pointsAt2sAfterCut": r["conditionalTeleopPoints"],
            "evaluatedGapMm": 1000 * r["minimumAssessedClearanceM"],
            "peakQuasistaticDemandA": r["peak"]["currentA"],
            "assessmentStrokeMm": 1000 * r["atAssessment"]["down"],
        }
    print(
        label,
        [
            (
                k,
                round(v["peakQuasistaticDemandA"], 3),
                v["pointsAt2sAfterCut"],
                round(v["assessmentStrokeMm"], 2),
            )
            for k, v in out[label].items()
        ],
        flush=True,
    )
(here / "current-screen.json").write_text(
    json.dumps(out, indent=2) + "\n", newline="\n"
)
