"""Matched passive 2026 tower study. Sum both hook reactions about the aft chassis foot."""

import sys, json, math, hashlib
from pathlib import Path

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / "experiments/tower-climb"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import run


def case(name, params):
    peak = {"foreN": -float("inf"), "aftCompressionN": -float("inf"), "horizontalN": 0}

    def witness(t, angle, center, contacts, brace_pos, brace_force):
        pitchMoment = 0
        vert = 0
        foreAft = 0
        for index, lx, lz, wx, wz, hx, hz in contacts:
            c, s = math.cos(angle), math.sin(angle)
            X = hx * c + hz * s
            Z = -hx * s + hz * c
            # x and z are body-frame coordinates of the actual force application.
            pitchMoment += (lx - (-0.280)) * Z - (lz - 0.1148) * X
            vert += Z
            foreAft += X
        fore = pitchMoment / 0.100
        if fore > peak["foreN"]:
            peak.update(foreN=fore, foreTimeS=t)
        peak["aftCompressionN"] = max(peak["aftCompressionN"], fore - vert)
        peak["horizontalN"] = max(peak["horizontalN"], abs(foreAft))

    data = run(name, **params, observe_contacts=witness)
    data.pop("rows")
    return {
        "case": name,
        "inputs": params,
        "maximums": peak,
        "factoredWorstWallMPa": 2 * peak["foreN"] / (12.53 * (1.95 - 0.035)),
        "observation": data,
    }


cases = [("baseline62", {}), ("loaded68", {"mass": 68, "cog_x": 0.035})]
for k in (32000, 96000, 128000):
    cases.append((f"loaded68-k{k}", {"mass": 68, "cog_x": 0.035, "bumper_k": k}))
cases += [
    ("loaded68-forward50", {"mass": 68, "cog_x": 0.050}),
    ("loaded68-forward50-double", {"mass": 68, "cog_x": 0.050, "bumper_k": 128000}),
    ("loaded68-roll", {"mass": 68, "cog_x": 0.035, "roll_deg": 1.5}),
]
cases += [
    ("soft50-coarse", {"mass": 68, "cog_x": 0.05, "bumper_k": 32000}),
    ("soft50-refined", {"mass": 68, "cog_x": 0.05, "bumper_k": 32000, "dt": 0.000125}),
    ("soft35-refined", {"mass": 68, "cog_x": 0.035, "bumper_k": 32000, "dt": 0.000125}),
    ("nominal-k-cg38", {"mass": 68, "cog_x": 0.038}),
    ("nominal-k-cg40", {"mass": 68, "cog_x": 0.040}),
]
rows = [case(*c) for c in cases]
out = Path(sys.argv[2])
out.write_text(
    json.dumps(
        {
            "supportSha256": hashlib.sha256(
                (root / "experiments/tower-climb/support.py").read_bytes()
            ).hexdigest(),
            "cases": rows,
        },
        indent=2,
    )
    + "\n",
    encoding="utf8",
    newline="\n",
)
for r in rows:
    print(
        r["case"],
        round(r["maximums"]["foreN"], 3),
        round(r["maximums"]["aftCompressionN"], 3),
        round(r["factoredWorstWallMPa"], 2),
        r["observation"].get("hangingAtAssessment"),
        list(r["observation"])[-6:],
    )
