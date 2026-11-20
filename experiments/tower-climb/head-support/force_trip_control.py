"""Ideal axial-force trip and longer power-loss assessment as mechanism design controls."""

from pathlib import Path
import sys, json, math

p = Path(__file__).resolve().parent
sys.path.insert(0, str(p.parent))
from support import run

profiles = json.loads((p / "current-screen.json").read_bytes())
out = {}
for name, baseline in profiles.items():
    kw = baseline["23.0"]["settings"]
    mu = kw.get("thread_mu", 0.14)
    thrustPerAmp = (2.6 / 105 * 6 * 0.82) / (
        0.0045
        * math.tan(
            math.atan(0.002 / (math.pi * 0.009))
            + math.atan(mu / math.cos(math.radians(14.5)))
        )
    )
    # Test the low end of the proposed trip tolerance during lifting and the high end at obstruction.
    # The planar solver's historical per-hook friction/current relationship is retained.
    cap = 900 / thrustPerAmp
    r = run(name + "-900N", motor_a=cap, read_after=12, **kw)
    out[name] = {
        "settings": kw,
        "idealTripLowN": 900,
        "hypotheticalBlockedUpperNAtZeroOvershoot": 1100,
        "equivalentCurrentAInThisFrictionScenario": cap,
        "peakDemandA": r["peak"]["currentA"],
        "firstClearS": r["firstClearS"],
        "firstLostAfterCutS": r["lostAfterCutS"],
        "strokeAtCutMm": next(rr["down"] * 1000 for rr in r["rows"] if rr["t"] == 9),
        "stroke12sAfterCutMm": r["atAssessment"]["down"] * 1000,
        "modeledPoints12sAfterCut": r["conditionalTeleopPoints"],
        "minimumClearanceAfterCutMm": 1000 * r["minimumAssessedClearanceM"],
    }
    print(
        name,
        round(cap, 3),
        r["firstClearS"],
        r["lostAfterCutS"],
        round(1000 * r["atAssessment"]["down"], 2),
        r["conditionalTeleopPoints"],
        flush=True,
    )
(p / "force-trip-control.json").write_text(
    json.dumps(
        {
            "cases": out,
            "scope": "Ideal 1.0 kN axial demand trip, +/-10% variation; lifting tested at 900 N, hard-stop sensitivity capped at 1100 N only for an instantaneous ideal axial limiter. Not installed hardware or a sensor/control design. Claim excludes response delay, impact and guide binding. Historical solver uses per-hook lumping for screw current and has a quasi-static friction law. No active control after 9 s.",
        },
        indent=2,
    )
    + "\n",
    newline="\n",
)
