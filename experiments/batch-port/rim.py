"""Bound the actual sphere cross-section through the six native top lips during one solver step."""

import json
import math
import numpy as np


class Rim:
    def __init__(self, cache, center, radius):
        self.center = np.array(center)
        self.radius = radius
        bounds = []
        normals = []
        tops = []
        bottoms = []
        thickness = []
        with np.load(cache) as data:
            for key, name in json.loads(str(data["labels"])).items():
                if name != "GE-26329: Hub Funnel Side":
                    continue
                tri = data[key].astype(float) / 1000
                top = tri[:, :, 2].max()
                points = tri.reshape(-1, 3)
                tips = points[points[:, 2] > top - 2e-7]
                inward = tips[:, :2].mean(axis=0) - self.center[:2]
                theta = (
                    math.pi / 6
                    + round(
                        (math.atan2(inward[1], inward[0]) - math.pi / 6) / (math.pi / 3)
                    )
                    * math.pi
                    / 3
                )
                n = np.array([math.cos(theta), math.sin(theta)])
                # Two long parallel upper edges are connected across the sheet thickness.
                crest = tri[tri[:, :, 2].max(axis=1) > top - 2e-7]
                projected = (crest[:, :, :2] - self.center[:2]) @ n
                top_radius = float(np.mean((tips[:, :2] - self.center[:2]) @ n))
                outer = crest[
                    (projected > top_radius + 0.001) & (crest[:, :, 2] < top - 0.0005)
                ]
                if len(outer) == 0:
                    raise ValueError("No paired outer edge")
                bottom = outer[:, 2].max()
                lip_width = float(
                    np.max(
                        (outer[outer[:, 2] > bottom - 2e-7, :2] - self.center[:2]) @ n
                    )
                    - top_radius
                )
                section = []
                # The tightest opening over the lip comes from clipped native triangles,
                # including intersections with the lower face of this finite band.
                for ta, tb in [(0, 1), (1, 2), (2, 0)]:
                    a, b = tri[:, ta], tri[:, tb]
                    mask = (a[:, 2] >= bottom) & (b[:, 2] < bottom)
                    if np.any(mask):
                        aa, bb = a[mask], b[mask]
                        ratio = (bottom - aa[:, 2]) / (bb[:, 2] - aa[:, 2])
                        section.append(aa + ratio[:, None] * (bb - aa))
                    mask = (a[:, 2] < bottom) & (b[:, 2] >= bottom)
                    if np.any(mask):
                        aa, bb = a[mask], b[mask]
                        ratio = (bottom - aa[:, 2]) / (bb[:, 2] - aa[:, 2])
                        section.append(aa + ratio[:, None] * (bb - aa))
                section.append(points[points[:, 2] >= bottom])
                ap = float(np.min((np.vstack(section)[:, :2] - self.center[:2]) @ n))
                bounds.append(ap)
                normals.append(n)
                tops.append(top)
                bottoms.append(bottom)
                thickness.append(float(np.hypot(top - bottom, lip_width)))
        if len(bounds) != 6:
            raise ValueError("Expected six independent native opening faces")
        self.ap = np.array(bounds)
        self.n = np.array(normals)
        self.top = max(tops)
        self.bottom = min(bottoms)
        self.receipt = {
            "topM": self.top,
            "bottomM": self.bottom,
            "sheetThicknessM": thickness,
            "minimumApothemsM": bounds,
            "normalsXY": [n.tolist() for n in normals],
        }

    def margin(self, a, b):
        # Every interpolated sphere slice on every plane in the finite slab is
        # enclosed by this per-step radius and the two endpoint horizontal projections.
        dz = max(0.0, min(a[2], b[2]) - self.top, self.bottom - max(a[2], b[2]))
        rho = math.sqrt(max(0.0, self.radius**2 - dz**2))
        aa = self.n @ (a[:2] - self.center[:2])
        bb = self.n @ (b[:2] - self.center[:2])
        return float(np.min(self.ap - np.maximum(aa, bb) - rho))

    def observe(self, body, old, t, step):
        p = body["p"]
        hi = self.top + self.radius
        lo = self.bottom - self.radius
        start = old
        if old[2] >= hi and p[2] < hi:
            f = (hi - old[2]) / (p[2] - old[2])
            start = old + f * (p - old)
            body["rimWatch"] = {"startS": t + f * step, "marginM": float("inf")}
        w = body.get("rimWatch")
        if w is None:
            return
        if p[2] > hi:
            body["rimWatch"] = None
            return
        f = (lo - old[2]) / (p[2] - old[2]) if p[2] < lo <= old[2] else 1.0
        end = old + f * (p - old)
        w["marginM"] = min(w["marginM"], self.margin(start, end))
        if p[2] <= lo:
            w["endS"] = t + f * step
            body["rimAttempts"].append(w)
            if w["marginM"] > 0 and body.get("rimS") is None:
                body["rimS"] = w["endS"]
                body["rimMarginM"] = w["marginM"]
            body["rimWatch"] = None
