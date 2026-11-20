"""Introduce a finite brake torque at screw outputs in the registered planar contact solver."""

import math, json, hashlib, sys
from pathlib import Path

here = Path(__file__).resolve().parent
d = here.parent
sys.path.insert(0, str(d))
from support import run as legacy

native = (d / "support.py").read_text(encoding="utf8")
sig = "    observe_contacts=None,"
update = "            dv = max(-0.16, dv - backwards * dt / equiv)"
assert native.count(sig) == native.count(update) == 1
calc = """            fraction = max(0.,min(1.,(t-powered_cut-brake_delay)/brake_ramp))
            resisting = brake_count * brake_nm * fraction * 2 * math.pi / lead
            previous = dv
            if dv <= 0.0:
                dv = min(0.0,max(-0.16,dv + (resisting - backwards) * dt / equiv))
            else:
                dv = max(-0.16,dv - backwards * dt / equiv)
            if brake_sample:
                brake_sample(t, previous, dv, backwards, resisting, down, equiv)"""
solver = native.replace(
    sig,
    sig
    + "\n    brake_nm=0.0, brake_count=2, brake_delay=0.25, brake_ramp=0.15, brake_sample=None,",
).replace(update, calc)
# Resolve field.json from exactly the evidence study used to capture the rung contacts.
space = {"__file__": str(d / "support.py"), "__name__": "passive_brake_variant"}
exec(compile(solver, "passive-brake-model", "exec"), space)


def evaluate(name, mu, torque, count, delay, dt=0.00025):
    kw = dict(mass=68, cog_x=0.035, thread_mu=mu, read_after=12, dt=dt)
    max_speed = 0.0
    max_thrust = 0.0
    energy = 0.0
    peak_energy = 0.0

    def measure(t, v0, v1, back, resisting, stroke, equiv):
        nonlocal max_speed, max_thrust, energy, peak_energy
        max_speed = max(max_speed, -v1)
        max_thrust = max(max_thrust, back)
        peak_energy = max(peak_energy, 0.5 * equiv * v1 * v1)
        energy += resisting * 0.5 * (max(0, -v0) + max(0, -v1)) * dt

    r = space["run"](
        name,
        **kw,
        brake_nm=torque,
        brake_count=count,
        brake_delay=delay,
        brake_sample=measure,
    )
    if count == 0:
        control = legacy(name, **kw)
        assert r == control, "disabled derivative changed native baseline"
    cut = next(row["down"] for row in r["rows"] if row["t"] == 9)
    return dict(
        friction=mu,
        brakes=count,
        brakeTorqueNmEach=torque,
        engageDelayS=delay,
        rampS=0.15,
        dt=dt,
        readAfterCutS=12,
        initialStrokeMm=1000 * cut,
        finalStrokeMm=1000 * r["atAssessment"]["down"],
        clearanceMm=1000 * r["minimumAssessedClearanceM"],
        points=r["conditionalTeleopPoints"],
        lostAtS=r["lostAfterCutS"],
        peakBackdriveSpeedMmS=1000 * max_speed,
        peakBackdriveEquivalentOutputTorqueNm=max_thrust * 0.002 / (2 * math.pi),
        brakeWorkModelJ=energy,
        peakReflectedKineticJ=peak_energy,
    )


out = {}
for name, mu, trq, n, delay, dt in [
    ("original-low", 0.035, 0, 0, 0.25, 0.00025),
    ("normal-pair", 0.035, 0.15, 2, 0.25, 0.00025),
    ("delayed-pair", 0.035, 0.15, 2, 1.0, 0.00025),
    ("one-survivor", 0.035, 0.15, 1, 0.25, 0.00025),
    ("lossless-zero-brakes", 0, 0, 0, 0.25, 0.00025),
    ("lossless-both", 0, 0.15, 2, 0.25, 0.00025),
    ("lossless-one", 0, 0.15, 1, 0.25, 0.00025),
    ("lossless-both-halfstep", 0, 0.15, 2, 0.25, 0.000125),
    ("lossless-one-stronger", 0, 0.30, 1, 0.25, 0.00025),
    ("lossless-one-stronger-halfstep", 0, 0.30, 1, 0.25, 0.000125),
]:
    r = evaluate(name, mu, trq, n, delay, dt)
    out[name] = r
    print(
        name,
        r["points"],
        round(r["finalStrokeMm"], 3),
        round(r["clearanceMm"], 2),
        round(r["peakBackdriveEquivalentOutputTorqueNm"], 3),
        flush=True,
    )
(here / "passive-brake-control.json").write_text(
    json.dumps(
        {
            "parentSourceSha256": hashlib.sha256(
                (d / "support.py").read_bytes()
            ).hexdigest(),
            "virtualVariantSha256": hashlib.sha256(solver.encode()).hexdigest(),
            "cases": out,
            "interpretation": "Screw-output passive braking torque acts only in the reverse moving/holding direction after a delay and ramp. No credit for active current. Zero brakes must exactly reproduce the original solver. All motion is constrained to one common axis. A single brake holding a rigid shared coordinate does not establish safe independent holding of two physical screws; racking, differential motion, mounting, real torque and duty rating remain open. Energy integral covers braking at modeled contact speed; end stop impact is not modeled.",
        },
        indent=2,
    )
    + "\n",
    newline="\n",
)
