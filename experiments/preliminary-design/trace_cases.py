"""Fit the tracked FUEL's package strokes to the solved traces of field_trials.py.

A package case moves a body by one stroke: a straight translation, a circular arc about a Y axis, or a translation
with a quadratic drop (a drag-free ballistic segment). fit() covers a trace window with the fewest such strokes that
stay within a stated distance of every traced sample, breaking at each named event. Every stroke starts and ends on
a traced sample, so consecutive strokes join exactly and the stroke path is the trial's path to within the tolerance.

Side-view traces are [t, x, z, ...] in metres; samples here are (t, x_mm, z_mm).
"""
import math


def _line_dev(p, a, b):
    ax, az = a; bx, bz = b
    dx, dz = bx - ax, bz - az
    L2 = dx * dx + dz * dz
    if L2 == 0:
        return math.hypot(p[0] - ax, p[1] - az)
    s = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - az) * dz) / L2))
    return math.hypot(p[0] - ax - s * dx, p[1] - az - s * dz)


def _circle(p, q, r):
    ax, az = p; bx, bz = q; cx, cz = r
    d = 2 * (ax * (bz - cz) + bx * (cz - az) + cx * (az - bz))
    if abs(d) < 1e-9:
        return None
    ux = ((ax * ax + az * az) * (bz - cz) + (bx * bx + bz * bz) * (cz - az) + (cx * cx + cz * cz) * (az - bz)) / d
    uz = ((ax * ax + az * az) * (cx - bx) + (bx * bx + bz * bz) * (ax - cx) + (cx * cx + cz * cz) * (bx - ax)) / d
    return ux, uz


def _candidates(pts):
    """Yield (deviation_mm, stroke) for each stroke kind that can join pts[0] to pts[-1]."""
    a, b = pts[0], pts[-1]
    yield max((_line_dev(p, a, b) for p in pts[1:-1]), default=0.0), dict(kind="line")
    if len(pts) < 3:
        return
    mid = pts[len(pts) // 2]
    centre = _circle(a, mid, b)
    if centre and math.hypot(*centre) < 1e7:
        ux, uz = centre
        r = math.hypot(a[0] - ux, a[1] - uz)
        phi = lambda p: math.atan2(p[0] - ux, p[1] - uz)       # a rotation about +Y increases this angle
        sweep, last, ok = 0.0, phi(a), True
        for p in pts[1:]:
            step = (phi(p) - last + math.pi) % (2 * math.pi) - math.pi
            sweep += step; last = phi(p)
        # the unwrapped sweep must keep one sense and stay under half a turn
        sense = 1 if sweep >= 0 else -1
        last = phi(a); run = 0.0
        for p in pts[1:]:
            step = (phi(p) - last + math.pi) % (2 * math.pi) - math.pi
            run += step; last = phi(p)
            if run * sense < -1e-4 or abs(run) > abs(sweep) + 1e-4:
                ok = False
                break
        if ok and 1e-9 < abs(sweep) < math.pi:
            dev = max(abs(math.hypot(p[0] - ux, p[1] - uz) - r) for p in pts)
            yield dev, dict(kind="arc", centre=(ux, uz), sweepRad=sweep)
    dx, dz = b[0] - a[0], b[1] - a[1]
    if abs(dx) > 1.0:  # a drop needs steady horizontal travel to parameterize it
        s = [(p[0] - a[0]) / dx for p in pts]
        if all(-1e-9 <= v <= 1 + 1e-9 for v in s) and all(s[i] <= s[i + 1] + 1e-9 for i in range(len(s) - 1)):
            # z(s) = az + (dz + h) s - h s^2 ; least squares for the fall h
            num = sum((p[1] - a[1] - dz * v) * (v - v * v) for p, v in zip(pts, s))
            den = sum((v - v * v) ** 2 for v in s)
            if den > 0:
                h = num / den
                if h > 1e-6:
                    dev = max(abs(p[1] - (a[1] + (dz + h) * v - h * v * v)) for p, v in zip(pts, s))
                    yield dev, dict(kind="drop", fallMm=h)


def _best(pts, tol):
    best = min(_candidates(pts), key=lambda c: c[0])
    return best if best[0] <= tol else None


def fit(samples, tol, breaks=()):
    """Cover samples [(t, x, z)] with strokes within tol mm. breaks are times a stroke may not span.
    Returns [dict(kind, fromS, toS, fromMm, toMm, deviationMm, ...)]."""
    cut = sorted({min(range(len(samples)), key=lambda i: abs(samples[i][0] - t)) for t in breaks} | {0, len(samples) - 1})
    out = []
    for lo, hi in zip(cut, cut[1:]):
        i = lo
        while i < hi:
            # longest stroke from i: grow geometrically, then bisect
            good, step = i + 1, 1
            j = i + 1
            while j <= hi and _best([s[1:3] for s in samples[i:j + 1]], tol):
                good = j
                step *= 2
                j = min(hi, i + step) if good < hi else hi + 1
                if j == good:
                    break
            lo_j, hi_j = good, min(hi, max(good, i + step))
            while lo_j < hi_j:
                m = (lo_j + hi_j + 1) // 2
                if _best([s[1:3] for s in samples[i:m + 1]], tol):
                    lo_j = m
                else:
                    hi_j = m - 1
            j = lo_j
            pts = [s[1:3] for s in samples[i:j + 1]]
            if math.dist(pts[0], pts[-1]) < 1e-6 and j < hi:   # no travel yet: wait for motion
                # absorb the rest: extend to the next sample that moved
                k = j
                while k < hi and math.dist(samples[k][1:3], pts[0]) < 1e-6:
                    k += 1
                j = max(j, k)
                pts = [s[1:3] for s in samples[i:j + 1]]
            found = _best(pts, tol)
            assert found, f"no stroke within {tol} mm from sample {i} to {j}"
            dev, stroke = found
            if math.dist(pts[0], pts[-1]) >= 1e-6:
                out.append(dict(stroke, fromS=samples[i][0], toS=samples[j][0], fromMm=list(pts[0]), toMm=list(pts[-1]), deviationMm=dev))
            i = j
    return out


def ops(stroke, y=0.0):
    """Mechanical-motion operations for one fitted stroke in the robot STEP frame (mm)."""
    (ax, az), (bx, bz) = stroke["fromMm"], stroke["toMm"]
    if stroke["kind"] == "line":
        return [dict(kind="translation", travelMm=[bx - ax, 0.0, bz - az])]
    if stroke["kind"] == "arc":
        ux, uz = stroke["centre"]
        return [dict(kind="rotation", originMm=[ux, y, uz], axis=[0.0, 1.0, 0.0], travelDeg=math.degrees(stroke["sweepRad"]))]
    h = stroke["fallMm"]
    return [dict(kind="translation", travelMm=[bx - ax, 0.0, bz - az + h]), dict(kind="gravity-drop", fallMm=h, quadraticFraction=1.0)]


def side(frames, ix=1, iz=2):
    return [(f[0], 1000 * f[ix], 1000 * f[iz]) for f in frames]
