"""Frozen-contact sensitivity for independent backdriving screw axes up to first guide contact."""

from pathlib import Path
import math, json, sys, hashlib

here = Path(__file__).resolve().parent
record = here / "settled-contacts.json"
fit = Path(sys.argv[1])
cad = json.loads(fit.read_bytes())
snapshot = json.loads(record.read_bytes())
theta = snapshot["angle"]
hz = [0.0, 0.0]
for j, _, _, _, _, fx, fz in snapshot["contacts"]:
    hz[j] += fz * math.cos(theta) - fx * math.sin(theta)
F = sum(hz)
r = (hz[1] - hz[0]) * 88 / 305
loads = [(F - r) / 2, (F + r) / 2]
threshold = (
    max(v["firstAboveFiveThousandthsMm3BracketMm"][1] for v in cad["heldSide"].values())
    / 1000
)
pitch = 0.002
k = 2 * math.pi / pitch
jmotor = 0.00005
ratio = 6
mass = jmotor * (k * ratio) ** 2


def replay(mu, torques, delay, ramp, dt, limits=loads):
    p = [0.0, 0.0]
    v = [0.0, 0.0]
    maxdiff = 0
    hit = None
    tau = [
        max(
            0.0,
            f
            * 0.0045
            * math.tan(
                math.atan(0.002 / (math.pi * 0.009))
                - math.atan(mu / math.cos(math.radians(14.5)))
            ),
        )
        for f in limits
    ]
    for i in range(round(12 / dt) + 1):
        t = i * dt
        if abs(p[0] - p[1]) >= threshold:
            hit = t
            break
        if max(p) >= 0.100:
            break
        if i == round(12 / dt):
            break
        fraction = max(0, min(1, (t - delay) / ramp))
        for j in range(2):
            v[j] = max(0.0, v[j] + (tau[j] - torques[j] * fraction) * k / mass * dt)
            p[j] += v[j] * dt
        maxdiff = max(maxdiff, abs(p[0] - p[1]))
    return dict(
        friction=mu,
        outputBrakeTorquesNm=torques,
        engageDelayS=delay,
        rampS=ramp,
        dt=dt,
        screwAxialN=limits,
        driveBackTorqueNm=tau,
        hitRegisteredInterferenceS=hit,
        assessedUntilS=t,
        terminalTravelMm=[1000 * x for x in p],
        terminalSpeedMmS=[1000 * x for x in v],
        maxDifferentialMm=maxdiff * 1000,
    )


out = {}
for mu in (0.0, 0.035, 0.14):
    for torques, name in [
        ([0.15, 0.15], "both"),
        ([0.30, 0], "left-only"),
        ([0, 0.30], "right-only"),
        ([0, 0], "both-open"),
    ]:
        out[f"{name}-{mu}"] = replay(mu, torques, 0.25, 0.15, 0.00025)
out["left-lossless-refined"] = replay(0.0, [0.30, 0], 0.25, 0.15, 0.000125)
out["both-different-delays-control"] = (
    None  # Filled by mirrored runs for distinct delays below.
)
# A fully held side against a released side has an analytic interference time at constant load.
tau = loads[1] * pitch / (2 * math.pi)
a = tau * k / mass
analytic = math.sqrt(2 * threshold / a)
# Gravity plus reflected rotor energy converted into a lossless direct catch load. No motion is propagated past guide contact.
catch = {}
for travel in (0.002, 0.004, 0.006):
    speed = math.sqrt(2 * a * travel)
    energy = 0.5 * mass * speed**2
    catch[str(travel)] = {
        "energyJ": energy,
        "speedMmS": speed * 1000,
        "minimumMeanCatchLoadFor05mmStopN": loads[1] + energy / 0.0005,
        "minimumMeanCatchLoadFor1mmStopN": loads[1] + energy / 0.001,
    }
del out["both-different-delays-control"]
assert (
    abs(
        out["left-only-0.0"]["hitRegisteredInterferenceS"]
        - out["left-lossless-refined"]["hitRegisteredInterferenceS"]
    )
    < 0.001
)
assert (
    abs(
        out["left-only-0.0"]["hitRegisteredInterferenceS"]
        - out["right-only-0.0"]["hitRegisteredInterferenceS"]
    )
    < 0.0005
)
assert (
    out["both-0.0"]["maxDifferentialMm"] == 0
    and out["both-open-0.0"]["terminalTravelMm"][0] >= 100
)
res = {
    "contactSampleHash": hashlib.sha256(record.read_bytes()).hexdigest(),
    "rackingReceiptHash": hashlib.sha256(fit.read_bytes()).hexdigest(),
    "sourceContactTimeS": snapshot["t"],
    "measuredRungProjectionN": hz,
    "perScrewLoadsN": loads,
    "reflectedMassEachKg": mass,
    "guideInterferenceDifferenceMm": threshold * 1000,
    "instantaneouslyHeldSideAnalyticLosslessTimeS": analytic,
    "cases": out,
    "losslessCatchWork": catch,
    "scope": "Two independent screw coordinates under the frozen 68 kg rung contact and a rigid bridge force split. The model stops at significant initial guide overlap or full mechanical travel; impact, varying contact, chassis roll and structural binding after that boundary are unresolved. Brake torque is an assumed dynamic capacity, not a supplier working allowance. Direct-catch work is a necessary mean in an ideal lossless fixed-load stop; peak, socket, frame load sharing and damping are unknown.",
}
(here / "differential-time.json").write_text(json.dumps(res, indent=2) + "\n")
print("loads", loads, "threshold", threshold, "analytic", analytic)
for n, r in out.items():
    print(
        n, r["hitRegisteredInterferenceS"], [round(d, 3) for d in r["terminalTravelMm"]]
    )
print(catch)
