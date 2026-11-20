"""Feature definitions for drawing-driven native parts. Dimensions millimetres in robot coordinates."""

import math


def rect(lo, hi):
    return {"kind": "box", "lo": list(lo), "hi": list(hi)}


def round_stock(a, b, r, inner=0):
    return {"kind": "round", "a": list(a), "b": list(b), "r": r, "inner": inner}


def contour(points, delta, holes=()):
    return {
        "kind": "profile",
        "points": [list(p) for p in points],
        "delta": list(delta),
        "holes": list(holes),
    }


def ring(a, b, outer, inner):
    return round_stock(a, b, outer, inner)


def article(
    name,
    role,
    material,
    features,
    *,
    parent,
    connection,
    stage="fixed",
    source="Project stock",
    purchase=None,
):
    return dict(
        name=name,
        role=role,
        material=material,
        features=features,
        parent=parent,
        connection=connection,
        stage=stage,
        source=source,
        purchase=purchase,
    )


def stock(f):
    return dict(op="new", shape=f)


def add(f):
    return dict(op="join", shape=f)


def drill(f):
    return dict(op="cut", shape=f)


def normalized(a):
    n = math.sqrt(sum(x * x for x in a))
    return [v / n for v in a]


def hexagon(a, b, af, bore=0):
    direction = normalized([v - u for u, v in zip(a, b)])
    up = [0, 0, 1] if abs(direction[2]) < 0.95 else [0, 1, 0]

    def cross(u, v):
        return [
            u[1] * v[2] - u[2] * v[1],
            u[2] * v[0] - u[0] * v[2],
            u[0] * v[1] - u[1] * v[0],
        ]

    x = normalized(cross(up, direction))
    y = cross(direction, x)
    points = []
    for j in range(6):
        angle = math.pi * j / 3
        points.append(
            [
                a[i]
                + af / math.sqrt(3) * (math.cos(angle) * x[i] + math.sin(angle) * y[i])
                for i in range(3)
            ]
        )
    return contour(
        points, [v - u for u, v in zip(a, b)], [dict(center=a, r=bore)] if bore else []
    )
