"""Speed windows for a FUEL launched into the HUB opening, with quadratic drag.

Season facts come from the project rules decomposition (construction-rules.json). The drag band,
the opening interpretation and the release geometry are labeled assumptions.
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


def fly(v, deg, h0, mass, cd, dt=0.0005):
    k = 0.5 * RHO * cd * AREA / mass
    x, z = 0.0, h0
    vx, vz = v * math.cos(math.radians(deg)), v * math.sin(math.radians(deg))
    path = [(0.0, x, z)]
    t = 0
    while z > -0.1 and t < 4:
        s = math.hypot(vx, vz)
        ax, az = -k * s * vx, -G - k * s * vz
        vx += ax * dt; vz += az * dt; x += vx * dt; z += vz * dt; t += dt
        path.append((t, x, z))
    return path


def enters(path, d):
    """Pass above the near rim with the whole ball, then descend through the rim plane inside the inscribed opening."""
    near = d - INSCRIBED
    far = d + INSCRIBED
    for (t0, x0, z0), (t1, x1, z1) in zip(path, path[1:]):
        if x0 < near + R <= x1 or x0 < near - R <= x1:
            pass
        # whole ball must be above the rim while its centre is within one radius of the near edge
        if near - R <= x1 <= near + R and z1 < RIM_Z + R and z1 >= z0 - 1:
            return False
        if z0 >= RIM_Z > z1:  # descending through the rim plane
            return near + R <= x1 <= far - R
    return False


def window(deg, h0, d, mass, cd):
    good = [v / 20 for v in range(60, 400) if enters(fly(v / 20, deg, h0, mass, cd), d)]
    return [min(good), max(good)] if good else None


def study():
    m_lo, m_hi = RULES["fuel"]["massKg"]
    exits = {
        "incumbent R2C scoring wheels (measured handoff 540 mm, wheel top 641 mm)": 0.60,
        "tall hooded flywheel above the 3-layer hopper": 0.70,
        "low trench-runner hooded flywheel": 0.43,
    }
    rows = []
    for label, h0 in exits.items():
        for deg in (55, 60, 65, 70):
            for d in (1.6, 2.4, 3.6):
                for cd in (0.35, 0.6):
                    worst = [window(deg, h0, d, m, cd) for m in (m_lo, m_hi)]
                    both = None if None in worst else [max(w[0] for w in worst), min(w[1] for w in worst)]
                    rows.append(dict(exit=label, exitHeightM=h0, elevationDeg=deg, distanceM=d, cd=cd,
                                     speedWindowMps=both if both and both[0] <= both[1] else None))
    return dict(basis="Point-mass flight with quadratic drag, no lift from spin. The ball must clear the near rim with its whole diameter and descend through the rim plane at least one radius inside the inscribed opening. Mass and diameter follow the V0 FUEL description; drag coefficients 0.35 and 0.60 bound a smooth-to-rough foam sphere near Re 1e5 (assumed, not measured).",
                inscribedRadiusM=INSCRIBED, rimHeightM=RIM_Z, rows=rows)


if __name__ == "__main__":
    out = study()
    (HERE / "ballistics.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    for r in out["rows"]:
        if r["cd"] == 0.6 and r["elevationDeg"] in (60, 65):
            print(r["exit"][:28], r["elevationDeg"], r["distanceM"], r["speedWindowMps"])
