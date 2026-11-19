"""Contact-surface velocities of the registered field counter; signs discharge toward midfield."""

from collections import defaultdict
import numpy as np

WHEEL = "2in Wheel Intergrated 0500 HEX Hub"
TUBE = "GE-26408: Counter Roller Tube"


def register_rotors(parts):
    centers = {i: (lo + hi) / 2 for i, (_, _, lo, hi) in enumerate(parts)}
    wheels = defaultdict(list)
    tubes = {}
    for i, (name, _, lo, hi) in enumerate(parts):
        if name == WHEEL:
            wheels[round(centers[i][1], 3)].append(i)
        elif name == TUBE:
            # Horizontal shaft. A contact on its underside is carried outward.
            tubes[i] = (centers[i], np.array([0.0, -1.0, 0.0]), (hi[2] - lo[2]) / 2)
    if len(tubes) != 1 or sorted(map(len, wheels.values())) != [2] * 8:
        raise ValueError("Expected one counter tube and eight pairs of stacked rollers")
    rotors = {}
    for rank, (_, ids) in enumerate(sorted(wheels.items())):
        low, high = sorted(ids, key=lambda i: centers[i][2])
        axis = centers[high] - centers[low]
        axis /= np.linalg.norm(axis)
        if not (0.33 < axis[0] < 0.39 and 0.91 < axis[2] < 0.95):
            raise ValueError(
                "Inclined counter shaft did not match its registered geometry"
            )
        # Each pair straddles its discharge lane. The two facing surfaces travel outward.
        handedness = -1 if rank % 2 == 0 else 1
        for i in ids:
            rotors[i] = (centers[i], axis * handedness, 0.0254)
    return rotors, tubes


class CounterDrive:
    def __init__(self, parts, roller_surface_mps=0.0, tube_surface_mps=0.0):
        self.moving = {}
        rollers, tubes = register_rotors(parts)
        for group, speed in [(rollers, roller_surface_mps), (tubes, tube_surface_mps)]:
            for index, (center, axis, radius) in group.items():
                self.moving[index] = (center, axis * speed / radius)

    def surface(self, index, location):
        if index not in self.moving:
            return 0.0
        center, omega = self.moving[index]
        return np.cross(omega, location - center)
