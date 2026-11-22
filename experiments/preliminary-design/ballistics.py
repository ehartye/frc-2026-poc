"""Speed windows for a FUEL launched into the HUB opening, with quadratic drag and a spin-lift band.

Season facts come from the project rules addendum (construction-rules.json). The drag and lift bands, the
opening interpretation and the release geometry are labeled assumptions.

A floor-fed hood shooter rolls the FUEL between the moving wheel and the fixed hood, so the FUEL leaves
with spin whose Magnus force points away from the wheel side: below the trajectory for this layout.
Lift coefficient 0 to 0.30 bounds that effect for spin ratios up to about 1 (assumed, not measured).
"""
import json, math
from pathlib import Path

HERE = Path(__file__).resolve().parent
RULES = json.loads((HERE / "construction-rules.json").read_text(encoding="utf-8"))
G = 9.81
RHO = 1.2
D = RULES["fuel"]["diameterMm"] / 1000
R = D / 2
AREA = math.pi * R * R
RIM_Z = RULES["hub"]["openingFrontEdgeMm"] / 1000
# Conservative reading: 41.7 in is the across-corners span, so the inscribed radius is smaller.
INSCRIBED = RULES["hub"]["openingSpanMm"] / 2 * math.cos(math.pi / 6) / 1000


def fly(v, deg, h0, mass, cd, cl=0.0, dt=0.001):
    kd = 0.5 * RHO * cd * AREA / mass
    kl = 0.5 * RHO * cl * AREA / mass
    x, z = 0.0, h0
    vx, vz = v * math.cos(math.radians(deg)), v * math.sin(math.radians(deg))
    path = [(0.0, x, z)]
    t = 0
    while z > -0.1 and t < 4:
        s = math.hypot(vx, vz)
        # drag opposes velocity; spin lift is perpendicular, toward the lower side of the trajectory
        ax = -kd * s * vx + kl * s * vz
        az = -G - kd * s * vz - kl * s * vx
        vx += ax * dt; vz += az * dt; x += vx * dt; z += vz * dt; t += dt
        path.append((t, x, z))
    return path


def edges(d):
    return [(d - INSCRIBED, RIM_Z), (d + INSCRIBED, RIM_Z)]


def score(path, d):
    """Return (enters, edge clearance in m, landing offset from the HUB centre at 1.70 m) for one path."""
    apex = max(range(len(path)), key=lambda j: path[j][2])
    if path[apex][2] < RIM_Z + R:
        return False, -1.0, None
    end = next((j for j in range(apex, len(path)) if path[j][2] <= 1.70), None)
    if end is None:
        return False, -1.0, None
    pts = [(q[1], q[2]) for q in path[:end + 1]]
    clearance = min([math.dist(p, e) for e in edges(d) for p in pts if abs(p[0] - e[0]) < 0.4] or [9.0]) - R
    landing = pts[-1][0] - d
    inside = abs(landing) <= INSCRIBED - R - 0.010
    # descending through the rim plane must happen between the edges with the whole ball inside
    cross = next(((x1) for (x0, z0), (x1, z1) in zip(pts, pts[1:]) if z0 >= RIM_Z > z1), None)
    ok = inside and clearance >= 0.003 and cross is not None and d - INSCRIBED + R <= cross <= d + INSCRIBED - R
    return ok, clearance, landing


def window(deg, h0, d, mass, cd, cl=0.0):
    """Coarse 0.05 m/s scan, then 0.01 m/s refinement at each end of the passing band."""
    ok = lambda v: score(fly(v, deg, h0, mass, cd, cl), d)[0]
    coarse = [round(4 + 0.05 * i, 2) for i in range(141) if ok(round(4 + 0.05 * i, 2))]
    if not coarse:
        return None
    lo, hi = coarse[0], coarse[-1]
    lo = min([round(lo - 0.01 * i, 2) for i in range(1, 5) if ok(round(lo - 0.01 * i, 2))] + [lo])
    hi = max([round(hi + 0.01 * i, 2) for i in range(1, 5) if ok(round(hi + 0.01 * i, 2))] + [hi])
    return [lo, hi]


def robust(deg, h0, d, conditions):
    ws = [window(deg, h0, d, *c) for c in conditions]
    if None in ws:
        return None, ws
    lo, hi = max(w[0] for w in ws), min(w[1] for w in ws)
    return ([lo, hi] if lo <= hi else None), ws


CONDITIONS = [(0.215, cd, cl) for cd in (0.35, 0.6) for cl in (0.0, 0.3)]
R3_RELEASE_M = 0.267  # release height of the launch trial (field-trials.json chain.release.z); build_package.py checks it


def study():
    rows = []
    cases = [(f"R3 floor-fed hood (release {R3_RELEASE_M:.3f} m)", R3_RELEASE_M, deg) for deg in (60, 62)]
    cases += [(f"release {h:.2f} m", h, 60) for h in (0.43, 0.60, 0.70)]
    for label, h0, deg in cases:
        for d in (1.6, 2.0, 2.2, 2.4, 2.8, 3.6):
            band, per = robust(deg, h0, d, CONDITIONS)
            rows.append(dict(release=label, exitHeightM=h0, elevationDeg=deg, distanceM=d,
                             nominalWindowMps=window(deg, h0, d, 0.215, 0.47, 0.15), robustWindowMps=band,
                             conditionWindowsMps={f"cd{c[1]}-cl{c[2]}": w for c, w in zip(CONDITIONS, per)}))
    return dict(basis="Point-mass flight with quadratic drag (Cd 0.35-0.60) and a downward spin-lift band (CL 0-0.30) at 0.215 kg. "
                      "A shot enters when it clears both rim edges by 3 mm, descends through the rim plane with the whole ball inside the inscribed opening, "
                      "and is within the opening at 1.70 m. Nominal: Cd 0.47, CL 0.15. robustWindowMps is the speed band that enters under all four drag/lift corners, or null.",
                inscribedRadiusM=INSCRIBED, rimHeightM=RIM_Z, rows=rows)


if __name__ == "__main__":
    out = study()
    (HERE / "ballistics.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    for r in out["rows"]:
        if r["release"].startswith("R3"):
            print(r["elevationDeg"], r["distanceM"], r["nominalWindowMps"], r["robustWindowMps"], r["conditionWindowsMps"])
