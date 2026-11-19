"""One free FUEL against the local official HUB surfaces; no external game counter override."""

import json
from pathlib import Path
import numpy as np
import vtk
from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray
from target import R, G


class Hub:
    def __init__(self, cache):
        data = np.load(cache)
        self.part = []
        for key, name in json.loads(str(data["labels"])).items():
            tri = data[key].astype("float64") / 1000
            pts = tri.reshape(-1, 3)
            xyz = vtk.vtkPoints()
            xyz.SetData(numpy_to_vtk(pts, deep=True))
            cells = vtk.vtkCellArray()
            cells.SetData(
                numpy_to_vtkIdTypeArray(
                    np.arange(0, len(pts) + 1, 3, dtype="int64"), deep=True
                ),
                numpy_to_vtkIdTypeArray(np.arange(len(pts), dtype="int64"), deep=True),
            )
            pd = vtk.vtkPolyData()
            pd.SetPoints(xyz)
            pd.SetPolys(cells)
            loc = vtk.vtkStaticCellLocator()
            loc.SetDataSet(pd)
            loc.BuildLocator()
            self.part.append((name, loc, pts.min(axis=0), pts.max(axis=0)))
        self.lower = np.array([row[2] for row in self.part])
        self.upper = np.array([row[3] for row in self.part])

    def carry(self, candidate, dt, spin, seconds=2.6, counter=None, observe=None):
        p = np.array(candidate["releaseFieldM"], dtype=float)
        v = np.array(candidate["velocityFieldMps"], dtype=float)
        heading = candidate["headingRad"]
        omega = np.array([np.sin(heading) * spin, -np.cos(heading) * spin, 0.0])
        m = 0.215
        inertia = 0.4 * m * R**2
        frames = []
        contacts = {}
        low = 100.0
        max_depth = 0.0
        work = {}
        counter_wheels = {}
        for k in range(round(seconds / dt) + 1):
            t = k * dt
            low = min(low, p[2])
            force = np.array([0.0, 0.0, -m * G])
            torque = np.zeros(3)
            dist = np.maximum(np.maximum(self.lower - p, p - self.upper), 0)
            for i in np.flatnonzero(np.einsum("ij,ij->i", dist, dist) <= R * R):
                name, loc, _, _ = self.part[i]
                point = [0.0, 0.0, 0.0]
                cell = vtk.reference(0)
                sub = vtk.reference(0)
                d2 = vtk.reference(0.0)
                loc.FindClosestPoint(p, point, cell, sub, d2)
                d = max(1e-10, float(d2) ** 0.5)
                if d >= R:
                    continue
                depth = R - d
                n = (p - np.array(point)) / d
                max_depth = max(depth, max_depth)
                f = max(0, 9500 * depth - 22 * np.dot(v, n))
                relative = v + np.cross(omega, -R * n)
                surface = counter.surface(i, np.array(point)) if counter is not None else 0.0
                relative -= surface
                slip = relative - n * np.dot(relative, n)
                sl = np.linalg.norm(slip)
                ft = -0.25 * f * np.tanh(sl / 0.035) * slip / max(sl, 1e-12)
                if np.ndim(surface) and f > .02:
                    work[name] = work.get(name, 0.) + float(np.dot(ft, surface)) * dt
                force += f * n + ft
                torque += np.cross(-R * n, ft)
                if f > 0.02:
                    if name not in contacts:
                        contacts[name] = {"t": t, "centerM": p.tolist()}
                    if "Wheel Intergrated" in name and i not in counter_wheels:
                        counter_wheels[i] = {"t": t, "centerM": p.tolist()}
            if observe is not None:
                observe(t, p, v)
            if k % max(1, round((1 / 80) / dt)) == 0:
                frames.append([round(t, 6), *[round(x, 6) for x in p]])
            v += force / m * dt
            omega += torque / inertia * dt
            p += v * dt
            if p[2] < R and t > 0.3:
                break
        return {
            "contacts": contacts,
            "fieldDriveWorkJ": work,
            "finalVelocityMps": v.tolist(),
            "counterWheelsTouched": list(counter_wheels.values()),
            "minimumZM": float(low),
            "finalPositionM": p.tolist(),
            "maxModeledPenetrationM": float(max_depth),
            "dt": dt,
            "trajectory": frames,
        }
