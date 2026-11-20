"""Generous upper bound on yaw recovery from one remaining hook at the existing settled pose.
Preserve each rung contact's in-plane load, assign both hooks' reactions to one surviving hook,
and allow the load center anywhere across its full width. Inputs are a comparison, not a new trajectory.
"""

from pathlib import Path
import json, math

d = Path(__file__).resolve().parent
r = json.loads((d / "settled-contacts.json").read_bytes())
field = json.loads((d.parent / "field.json").read_bytes())
upright = max(
    (p for p in field["sides"]["blue"] if "Upright Outer" in p["name"]),
    key=lambda p: p["boundsMm"][1],
)
ybmax = (upright["boundsMm"][4] - upright["boundsMm"][1]) / 2000
mu = 0.14
half_hook = 0.006
Xb = r["braceXZ"][0]
FxB = r["braceForceXZ"][0]


# Hook normals lie in XZ, so |N| <= norm(Fxz). Giving all friction to Y exaggerates achievable yaw.
def lower(ycenters):
    vals = []
    lat = 0.0
    Fsum = 0.0
    for i, _, __, x, z, fx, fz in r["contacts"]:
        center = ycenters[i]
        vals.append(sorted([-(center - half_hook) * fx, -(center + half_hook) * fx]))
        lat += abs(x - Xb) * math.hypot(fx, fz)
        Fsum += fx
    vals.append(sorted([-(-ybmax) * FxB, -ybmax * FxB]))
    lo, hi = sum(v[0] for v in vals), sum(v[1] for v in vals)
    demand = max(0, lo, -hi)
    return dict(
        longitudinalReactionResidualN=Fsum + FxB,
        longitudinalYawIntervalNm=[lo, hi],
        minimumYawFromForeAftNm=demand,
        generousLateralFrictionYawBoundNm=mu * lat,
        remainingLowerBoundNm=max(0, demand - mu * lat),
        minimumHookMuNecessary=demand / lat,
    )


out = dict(
    assumedRungMu=mu,
    postHalfWidthM=ybmax,
    hookWidthM=2 * half_hook,
    bracePositionM=r["braceXZ"],
    cases={},
)
for key, ys in [
    ("two hooks", [-0.088, 0.088]),
    ("left only", [0.088, 0.088]),
    ("right only", [-0.088, -0.088]),
]:
    out["cases"][key] = lower(ys)
# Alternative geometric requirement: if rung slips freely along Y, move bumper pressure center out to the hook.
out["scope"] = (
    "Frozen pose and observed XZ reactions on a vertical flat contact face, centered parking, complete unloading of the other hook. Unilateral contacts with fixed YZ/XZ geometry and no other restraint. A different settled pose, external side capture or shifted upright contact requires its own history."
)
(d / "one-hook-yaw.json").write_text(
    json.dumps(out, indent=2) + "\n", encoding="utf8", newline="\n"
)
print(json.dumps(out, indent=2))
