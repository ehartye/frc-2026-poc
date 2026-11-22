"""Side-view BUMP crossing screen: rest both wheels on the V0 BUMP profile at every position and measure the
clearance of every underside feature. Run: python -I -B experiments/preliminary-design/bump_crossing.py [floor_top_mm]

BUMP (V0 5.5): 6.513 in tall, 44.4 in deep, two 15 degree ramps meeting at the crest (conservative sharp
crest; a flat top would only add clearance). Wheels 76.2 mm at +/-265 mm. Underside features are the bottoms
of the R3 solids with the intake retracted (start fold).
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
H = 6.513 * 25.4
TAN = math.tan(math.radians(15))
R_W, A = 38.1, 265.0


def terrain(x):
    return max(0.0, H - TAN * abs(x))


def wheel_centre_z(xw):
    """Lowest centre height of a wheel at xw that does not penetrate the profile."""
    best = 0.0
    for i in range(-40, 41):
        x = xw + R_W * i / 40
        best = max(best, terrain(x) + math.sqrt(max(0.0, R_W * R_W - (x - xw) ** 2)))
    return best


def features(floor_top):
    pan = floor_top - 6
    return [("floor pan", -176, 176, pan), ("front tongue", 177.5, 312, pan), ("module bodies", 185, 312, 80.0),
            ("module bodies", -312, -185, 80.0), ("frame rail front", 314.6, 340, 69.85), ("frame rail rear", -340, -314.6, 69.85),
            ("bumper front", 341.5, 417.5, 48.0), ("bumper rear", -417.5, -341.5, 48.0)]


def screen(floor_top=81.0, step=5.0):
    feats = features(floor_top)
    worst = (1e9, None, None)
    x = -1200.0
    while x <= 1200.0:
        # wheels are at robot-frame x = +/-A; the robot centre is at field x; solve the rigid pose from both wheels
        zf, zr = wheel_centre_z(x + A), wheel_centre_z(x - A)
        for _ in range(3):  # small pitch: wheel field positions shift by A(1-cos); refine
            th = math.atan2(zf - zr, 2 * A)
            xf, xr = x + A * math.cos(th), x - A * math.cos(th)
            zf, zr = wheel_centre_z(xf), wheel_centre_z(xr)
        th = math.atan2(zf - zr, 2 * A)
        zc = (zf + zr) / 2 - R_W * math.cos(th)  # robot-frame z = 0 at the wheel contact line midpoint
        for name, x0, x1, zb in feats:
            for k in range(11):
                lx = x0 + (x1 - x0) * k / 10
                fx = x + lx * math.cos(th) - zb * math.sin(th)
                fz = zc + lx * math.sin(th) + zb * math.cos(th)
                gap = fz - terrain(fx)
                if gap < worst[0]:
                    worst = (gap, name, round(x, 1))
        x += step
    return dict(floorTopMm=floor_top, minClearanceMm=round(worst[0], 2), limitingFeature=worst[1], robotCentreFromCrestMm=worst[2])


if __name__ == "__main__":
    floors = [float(a) for a in sys.argv[1:]] or [81.0]
    out = [screen(f) for f in floors]
    print(json.dumps(out, indent=1))
