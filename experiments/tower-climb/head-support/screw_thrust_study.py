"""Separate contact-derived screw thrust from a hypothetical powered hard-stop load."""

from pathlib import Path
import sys, json, hashlib, math

here = Path(__file__).resolve().parent
root = here.parents[2]
study = here.parent
sys.path.insert(0, str(study))
from support import run


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


support = study / "support.py"
cases = json.loads((here / "bumper-sensitivity.json").read_text())["cases"]
inputs = {r["case"]: r["inputs"] for r in cases}
inputs.update(
    {
        "left-only": dict(mass=68, cog_x=0.035, lateral_error=0.23),
        "opposite-offset-two-contact": dict(mass=68, cog_x=0.035, lateral_error=-0.23),
        "right-only": dict(mass=68, cog_x=0.035, lateral_error=0.070),
        "released-thread": dict(mass=68, cog_x=0.035, thread_mu=0.035),
        "disabled": dict(disable=True),
        "early-stop": dict(powered_cut=2.0),
    }
)


def evaluate(name, params):
    peaks = {}
    seen = 0

    def record(k, val, t):
        if k not in peaks or val > peaks[k]["forceN"]:
            peaks[k] = {"forceN": val, "timeS": t}

    def sample(t, pitch, center, contacts, *unused):
        nonlocal seen
        seen += 1
        c, s = math.cos(pitch), math.sin(pitch)
        hz = [0.0, 0.0]
        for j, x, z, wx, wz, fx, fz in contacts:
            hz[j] += c * fz - s * fx
        total = sum(hz)
        # On the robot the hook centers stay at -/+88 mm when the field datum is shifted.
        # Assumes a rigid bridge, two purely axial screw reactions, no other roll couples.
        d = (hz[1] - hz[0]) * 88 / 305
        r0, r1 = (total - d) / 2, (total + d) / 2
        assert (
            abs(total - r0 - r1) < 1e-8
            and abs(305 * (r1 - r0) - 88 * (hz[1] - hz[0])) < 1e-7
        )
        for k, v in [
            ("hookMinus", hz[0]),
            ("hookPlus", hz[1]),
            ("eitherHook", max(hz)),
            ("bridgeMinus", r0),
            ("bridgePlus", r1),
            ("singleDriveProjection", total),
            ("reverseProjection", -total),
        ]:
            record(k, v, t)

    res = run(name, observe_contacts=sample, **params)
    return dict(
        inputs=params,
        hooksLandingOnRung=res["hasTwoContacts"],
        sampleCount=seen,
        peaks=peaks,
        conditionalPoints=res["conditionalTeleopPoints"],
        peakCurrentReportedA=res["peak"]["currentA"],
    )


rows = {name: evaluate(name, p) for name, p in inputs.items()}
# Machine assumptions from the historical contact solver, plus explicit torque-thrust conversion.
mD = 0.009
lead = 0.002
gear = 6.0
efficiency = 0.82
kt = 2.6 / 105.0
ceiling = 23.0


def motor_force(mu):
    lam = math.atan(lead / (math.pi * mD))
    phi = math.atan(mu / math.cos(math.radians(14.5)))
    return kt * gear * efficiency / (0.5 * mD * math.tan(lam + phi))


jam = {}
for mu in [0.035, 0.07, 0.14, 0.21]:
    f = motor_force(mu)
    jam[str(mu)] = {
        "thrustPerAmpN": f,
        "hypothetical23AAtStopN": ceiling * f,
        "ampsAtEzoBasicStatic": 2440 / f,
        "ampsAtAstBasicStatic": 1701 / f,
        "ampsAtHalfEzoBasicStatic": 1220 / f,
    }
res = {
    "provenance": {
        str(p.relative_to(root)): sha(p)
        for p in [
            support,
            study / "field.json",
            here / "bumper-sensitivity.json",
            root / "cad/tower-lift/recipe.py",
            root / "cad/assembly-release/foundation-student.step",
        ]
    },
    "cases": rows,
    "quasistaticHardStop": jam,
    "assumptions": {
        "rungContactUnit": "Newtons in world XZ transformed by same-step chassis pitch into chassis Z",
        "bridge": "Two axial screw supports at robot Y +/-305 mm. Rung hooks at +/-88 mm. Unmodeled guide moments or carriage mass, friction, inertia, lopsided stiffness, jams or real three-axis dynamics can alter screw reactions. One-drive routing is a load allocation sensitivity, not a rigorous bound for a binding joint. Single-hook planar observations do not prove a stable hang.",
        "hardStop": "Alternative quasi-static torque equilibrium at a blocked nut with 6:1 gear, constant efficiency 0.82, motor torque constant 2.6/105 Nm/A, 2 mm lead and 9 mm mean diameter. No mechanical stop compliance, torque limiter, driver current regulation, ramp, losses beyond model, thermal derating, impact or backlash modeled. The historical solver clamps speed when demand exceeds 23 A; it does not generate this force. Static catalog rating is a comparison point only, not an allowable service load. The opposed pair has one loaded thrust race for each direction.",
    },
}
(here / "screw-thrust-study.json").write_text(
    json.dumps(res, indent=2) + "\n", newline="\n"
)
for n, r in rows.items():
    print(
        n,
        *[
            round(r["peaks"][k]["forceN"], 2)
            for k in [
                "eitherHook",
                "bridgeMinus",
                "bridgePlus",
                "singleDriveProjection",
                "reverseProjection",
            ]
        ],
    )
for m, r in jam.items():
    print("jam", m, r)
