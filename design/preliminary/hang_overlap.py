"""Plan-view check of the front bumper bearing on both TOWER uprights during the hang.

For each lateral offset and yaw of the robot at the berth, report the bearing width on each upright face
(the overlap of the bumper's front face with the upright's 38.1 mm face, measured along the face). Both
uprights must bear so the hang moment is reacted without roll. Run: python -I -B design/preliminary/hang_overlap.py
Writes hang-overlap.json. Dimensions: V0 uprights 819.15 mm apart, 38.1 mm thick; bumper outer half-width
from geometry.HALF_W plus the 76.5 mm bumper section.
"""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
GAP_HALF = 819.15 / 2
THICK = 38.1


def bearing(offset, yaw_deg, half_w):
    """Bearing width (mm) on the left and right upright faces. Yaw rotates the bumper face about its centre;
    the robot is pushed forward until the first corner touches, so a yawed face bears only at the leading upright
    unless the trailing gap closes by compliance (reported as the trailing gap)."""
    y0, y1 = -half_w + offset, half_w + offset
    left = max(0.0, min(y1, GAP_HALF + THICK) - max(y0, GAP_HALF))
    right = max(0.0, min(-GAP_HALF, y1) - max(y0, -GAP_HALF - THICK))
    gap = abs(math.tan(math.radians(yaw_deg))) * (2 * GAP_HALF + THICK)
    return round(left, 2), round(right, 2), round(gap, 2)


def table(half_w):
    rows = []
    for off in (0, 5, 10, 15, 20, 23, 25, 30):
        l, r, _ = bearing(off, 0, half_w)
        rows.append(dict(offsetMm=off, leftMm=l, rightMm=r, bothBear=l > 0 and r > 0))
    yaw = [dict(yawDeg=y, trailingGapMm=bearing(0, y, half_w)[2]) for y in (0.25, 0.5, 1.0, 2.0)]
    tol = half_w - GAP_HALF
    return dict(bumperHalfWidthMm=half_w, lateralToleranceMm=round(tol, 2), offsets=rows, yaw=yaw)


if __name__ == "__main__":
    out = dict(schema="frc-2026-poc/hang-overlap@1",
               basis="Plan view at the berth. Both uprights must bear on the front bumper so the hang moment (about 610 N horizontal at 67.6 kg) is shared; a yawed robot closes its trailing gap only by bumper compliance or a further yaw correction.",
               r3pd1_680mm=table(340 + 76.5), r3pd2_714mm=table(357 + 76.5))
    (HERE / "hang-overlap.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    for k in ("r3pd1_680mm", "r3pd2_714mm"):
        t = out[k]
        print(k, "tolerance", t["lateralToleranceMm"], [(r["offsetMm"], r["bothBear"]) for r in t["offsets"]], t["yaw"])
