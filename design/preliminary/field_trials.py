"""Physics trials for R3's mission-critical field interactions: acquisition, delivery into the HUB and the Level 1 hang.

Each trial integrates the free FUEL or the supported robot with penalty contact and regularized Coulomb
friction (explicit semi-implicit Euler). Actuator inputs are stated per trial: a belt surface speed is
imposed (transport at that speed, not proof the motor sustains it); the winch follows a DC motor line with
a current limit and bus voltage. Units are SI. Run from the project root:

    python -I -B design/preliminary/field_trials.py

Writes design/preliminary/field-trials.json and design/preliminary/review/field-interaction.html.
"""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RULES = json.loads((HERE / "construction-rules.json").read_text(encoding="utf-8"))
FACTS = json.loads((HERE / "package-facts.json").read_text(encoding="utf-8"))
G = 9.81
R = RULES["fuel"]["diameterMm"] / 2000
RHO = 1.2


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ------------------------------------------------------------------ 2D contact helpers (XZ plane)
def seg_contact(px, pz, a, b):
    """Closest point on segment ab to p; returns (distance, nx, nz, qx, qz)."""
    ax, az = a; bx, bz = b
    dx, dz = bx - ax, bz - az
    L2 = dx * dx + dz * dz
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / L2))
    qx, qz = ax + t * dx, az + t * dz
    d = math.hypot(px - qx, pz - qz)
    if d == 0:
        return 0.0, 0.0, 1.0, qx, qz
    return d, (px - qx) / d, (pz - qz) / d, qx, qz


def friction(Fn, vt, mu, eps=0.01):
    return -mu * Fn * vt / math.sqrt(vt * vt + eps * eps)


# ------------------------------------------------------------------ acquisition (side view, robot frame)
def acquisition(name, u=3.0, comp_back=0.020, comp_pulley=0.020, mu_belt=0.9, mu_bumper=0.4, mu_carpet=0.6,
                k=15000.0, zeta=0.3, mass=0.215, v_robot=0.5, dt=1e-4, t_end=1.5, locked=False):
    """FUEL on the carpet; the robot drives at v_robot; the bottom pulley pulls it under, the back run lifts it
    against the bumper face and the top roller pushes it over the bumper. Compression is the detailed setting
    the layout leaves undrawn (it draws a 3 mm undeformed reserve)."""
    c = 2 * zeta * math.sqrt(k * mass)
    inertia = 0.4 * mass * R * R
    rp = 0.0185
    xk = 0.4175 + 2 * R - comp_back            # belt back run, pressing the FUEL into the bumper cover
    xp = xk + rp
    zb = 2 * R - comp_pulley + rp              # bottom pulley centre: its underside compresses the FUEL top
    zt = 0.300 - rp
    roller = (0.4175 + R + 0.003, 0.270 + R + 0.003 + 0.0381 - 0.020)  # top roller lowered 20 mm into the FUEL path
    belt_u = 0.0 if locked else u
    omega_p = -belt_u / rp
    omega_r = -belt_u / 0.0381
    prims = [  # (kind, geometry, surface velocity function or angular speed, mu, label)
        ("seg", ((-1.0, 0.0), (2.0, 0.0)), (-v_robot, 0.0), mu_carpet, "carpet"),
        ("seg", ((0.4175, 0.048), (0.4175, 0.168)), (0.0, 0.0), mu_bumper, "bumper face"),
        ("seg", ((0.3415, 0.168), (0.4175, 0.168)), (0.0, 0.0), mu_bumper, "bumper top"),
        ("seg", ((xk, zb), (xk, zt)), (0.0, belt_u), mu_belt, "belt back run"),
        ("seg", ((xp + rp, zb), (xp + rp, zt)), (0.0, -belt_u), mu_belt, "belt front run"),
        ("circ", ((xp, zb), rp), omega_p, mu_belt, "bottom pulley"),
        ("circ", ((xp, zt), rp), omega_p, mu_belt, "top pulley"),
        ("circ", (roller, 0.0381), omega_r, mu_belt, "top roller"),
    ]
    x, z, vx, vz, w = 0.72, R, -v_robot, 0.0, 0.0
    t, frames, events, first = 0.0, [], [], {}
    max_belt_force, belt_power = 0.0, 0.0
    captured = None
    step = 0
    while t < t_end:
        fx, fz, tq = 0.0, -mass * G, 0.0
        belt_now = 0.0
        for kind, geom, sv, mu, label in prims:
            if kind == "seg":
                d, nx, nz, qx, qz = seg_contact(x, z, *geom)
                rad = R
                svx, svz = sv
            else:
                (cx, cz), rr = geom
                d0 = math.hypot(x - cx, z - cz)
                nx, nz = (x - cx) / d0, (z - cz) / d0
                d = d0 - rr
                qx, qz = cx + nx * rr, cz + nz * rr
                svx, svz = -sv * (qz - cz), sv * (qx - cx)
                rad = R
            pen = rad - d
            if pen <= 0:
                continue
            if label not in first:
                first[label] = round(t, 4)
                events.append(dict(t=round(t, 4), event=f"first contact: {label}"))
            # relative velocity of the FUEL surface at the contact point
            rx, rz = -nx * R, -nz * R
            pvx, pvz = vx - w * rz, vz + w * rx
            rvx, rvz = pvx - svx, pvz - svz
            vn = rvx * nx + rvz * nz
            Fn = max(0.0, k * pen - c * vn)
            tx, tz = -nz, nx
            vt = rvx * tx + rvz * tz
            Ft = friction(Fn, vt, mu)
            Fx, Fz = Fn * nx + Ft * tx, Fn * nz + Ft * tz
            fx += Fx; fz += Fz
            tq += rx * Fz - rz * Fx
            if label.startswith(("belt", "bottom", "top")):
                belt_now += abs(Ft) * u
                max_belt_force = max(max_belt_force, Fn)
        belt_power = max(belt_power, belt_now)
        vx += fx / mass * dt; vz += fz / mass * dt; w += tq / inertia * dt
        x += vx * dt; z += vz * dt; t += dt; step += 1
        if step % 20 == 0:
            frames.append([round(t, 4), round(x, 5), round(z, 5), round(w, 2)])
        if captured is None and x < 0.340 and z > 0.168 + R * 0.5:
            captured = round(t, 4)
            events.append(dict(t=captured, event="FUEL over the bumper and inside the frame: captured"))
            break
        if z < -0.05 or x > 1.2:
            events.append(dict(t=round(t, 4), event="FUEL lost"))
            break
    ok = captured is not None and captured <= 1.0
    return dict(name=name, kind="acquisition", passed=ok,
                metric=dict(name="capture time (s)", value=captured, requirement="captured within 1.0 s of first contact"),
                firstUnmet=None if ok else ("not captured within 1.5 s" if captured is None else "capture slower than 1.0 s"),
                imposed=f"belt and roller surface speed {belt_u} m/s imposed; robot approach {v_robot} m/s imposed",
                solved="FUEL translation and spin with penalty contact and Coulomb friction",
                beltDemand=dict(maxNormalN=round(max_belt_force, 1), maxFrictionPowerW=round(belt_power, 1),
                                note="Power the belt must supply at the imposed speed; compare with the selected motor before claiming it sustains the speed"),
                params=dict(u=u, compBack=comp_back, compPulley=comp_pulley, muBelt=mu_belt, muBumper=mu_bumper, muCarpet=mu_carpet,
                            k=k, zeta=zeta, mass=mass, vRobot=v_robot, dt=dt, locked=locked),
                geometry=dict(beltBackX=xk, pulley=[xp, zb, rp], topPulley=[xp, zt, rp], roller=[roller[0], roller[1], 0.0381],
                              bumper=[0.3415, 0.048, 0.4175, 0.168]),
                events=events, frames=frames)


# ------------------------------------------------------------------ delivery (3D, shot pose)
HUB = (-2.700, 0.0)
HALF = 1193.8 / 2000
CIRC = RULES["hub"]["openingSpanMm"] / 2000
HEX = [(HUB[0] + CIRC * math.cos(math.radians(90 + 60 * i)), HUB[1] + CIRC * math.sin(math.radians(90 + 60 * i))) for i in range(6)]


def in_hex(x, y):
    s = None
    for (ax, ay), (bx, by) in zip(HEX, HEX[1:] + HEX[:1]):
        cr = (bx - ax) * (y - ay) - (by - ay) * (x - ax)
        if s is None:
            s = cr > 0
        elif (cr > 0) != s:
            return False
    return True


def hex_closest(x, y):
    best = None
    for a, b in zip(HEX, HEX[1:] + HEX[:1]):
        d, nx, ny, qx, qy = seg_contact(x, y, a, b)
        if best is None or d < best[0]:
            best = (d, qx, qy)
    return best[1], best[2]


def ring_closest_xy(x, y):
    """Closest point of the square-minus-hexagon region to (x, y)."""
    if in_hex(x, y):
        return hex_closest(x, y)
    return min(max(x, HUB[0] - HALF), HUB[0] + HALF), min(max(y, HUB[1] - HALF), HUB[1] + HALF)


def hub_contacts(p):
    """Penalty contacts of a FUEL centre p against the HUB body, top plate and cavity floor."""
    out = []
    for z0, z1, region in ((0.0, 1.777, "ring"), (1.779, 1.8288, "ring"), (0.990, 1.000, "floor")):
        if region == "ring":
            qx, qy = ring_closest_xy(p[0], p[1])
        else:
            qx, qy = (p[0], p[1]) if in_hex(p[0], p[1]) else hex_closest(p[0], p[1])
        qz = min(max(p[2], z0), z1)
        d = math.dist(p, (qx, qy, qz))
        if d < R and d > 0:
            out.append(((p[0] - qx) / d, (p[1] - qy) / d, (p[2] - qz) / d, R - d))
    return out


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def delivery(name, v=None, cd=0.47, cl=0.15, k=15000.0, zeta=0.3, mu=0.6, mass=0.215, dt=1e-4, t_end=1.6, elevation=62.0):
    v = FACTS["flight"]["speedMps"] if v is None else v
    ex, ez = FACTS["flight"]["arcs"][0]["start"]
    p = [ex / 1000, 0.0825, ez / 1000]
    e = math.radians(elevation)
    vel = [-v * math.cos(e), 0.0, v * math.sin(e)]
    omega = [0.0, -v / R, 0.0]  # rolling off the fixed hood: spin ratio 1, Magnus toward the lower side of the path
    area = math.pi * R * R
    kd = 0.5 * RHO * cd * area
    kl = 0.5 * RHO * cl * area
    inertia = 0.4 * mass * R * R
    c = 2 * zeta * math.sqrt(k * mass)
    t, frames, events, scored, touched = 0.0, [], [], None, False
    step = 0
    sensor = 1.50
    while t < t_end:
        sp = math.sqrt(sum(q * q for q in vel)) or 1e-9
        F = [-kd * sp * vel[0], -kd * sp * vel[1], -kd * sp * vel[2] - mass * G]
        wn = math.sqrt(sum(q * q for q in omega)) or 1e-9
        mg = cross([q / wn for q in omega], vel)
        F = [F[i] + kl * sp * mg[i] for i in range(3)]
        Tq = [0.0, 0.0, 0.0]
        for nx, ny, nz, pen in hub_contacts(p):
            n = (nx, ny, nz)
            r = (-nx * R, -ny * R, -nz * R)
            vc = [vel[i] + cross(omega, r)[i] for i in range(3)]
            vn = sum(vc[i] * n[i] for i in range(3))
            Fn = max(0.0, k * pen - c * vn)
            vt = [vc[i] - vn * n[i] for i in range(3)]
            vtm = math.sqrt(sum(q * q for q in vt))
            Ft = [friction(Fn, vtm, mu) * (vt[i] / vtm if vtm else 0) for i in range(3)]
            f = [Fn * n[i] + Ft[i] for i in range(3)]
            F = [F[i] + f[i] for i in range(3)]
            tq = cross(r, f)
            Tq = [Tq[i] + tq[i] for i in range(3)]
            if not touched:
                touched = True
                events.append(dict(t=round(t, 4), event="first HUB contact", at=[round(q, 3) for q in p]))
        vel = [vel[i] + F[i] / mass * dt for i in range(3)]
        omega = [omega[i] + Tq[i] / inertia * dt for i in range(3)]
        prev = p[2]
        p = [p[i] + vel[i] * dt for i in range(3)]
        t += dt; step += 1
        if step % 20 == 0:
            frames.append([round(t, 4), round(p[0], 4), round(p[1], 4), round(p[2], 4)])
        if prev >= sensor > p[2] and in_hex(p[0], p[1]) and scored is None:
            scored = round(t, 4)
            events.append(dict(t=scored, event="FUEL crosses the HUB sensor plane inside the opening: scored"))
            break
        if p[2] < 0.2 and not in_hex(p[0], p[1]):
            events.append(dict(t=round(t, 4), event="FUEL on the carpet outside the HUB: missed"))
            break
    ok = scored is not None
    return dict(name=name, kind="delivery", passed=ok,
                metric=dict(name="scored at sensor (s)", value=scored, requirement="cross the sensor plane inside the opening"),
                firstUnmet=None if ok else "did not reach the sensor plane inside the opening",
                imposed=f"release state from the layout hood exit: {v} m/s at {elevation} deg with spin ratio 1 (designed, not measured)",
                solved="free FUEL translation and spin under drag, spin lift and penalty contact with the HUB",
                params=dict(v=v, cd=cd, cl=cl, k=k, zeta=zeta, mu=mu, mass=mass, dt=dt, elevationDeg=elevation, sensorZ=sensor),
                hub=dict(center=HUB, half=HALF, hex=HEX), events=events, frames=frames)


# ------------------------------------------------------------------ elevation (side view, berth)
def elevation(name, mass=67.6, cg=(-0.01, 0.28), bus_v=10.0, brake=True, mu_up=0.4, dt=1e-4, t_end=8.0,
              stroke=0.070, i_limit=40.0):
    """Robot rigid body (x, z, pitch) on unilateral wheel and bumper contacts; hooks seated on the low rung pull
    down by a winch with a DC motor line (NEO, 25:1, 12.5 mm spool, both cables), then a brake holds with power
    removed through the 3 s assessment. The bumper bears on the upright faces."""
    inertia = mass * (0.68 ** 2 + 0.60 ** 2) / 12
    f_stall12, v_free12, i_stall = 2.6 * 25 / 0.0125, 5676 * 2 * math.pi / 60 / 25 * 0.0125, 105.0
    f_lim = i_limit / i_stall * f_stall12
    rung = (0.46695, 0.6858, 0.02108)
    upright_x = 0.4225
    wheels = [(0.265, 0.0381), (-0.265, 0.0381)]
    bumper_pts = [(0.4175, 0.048), (0.4175, 0.168), (-0.4175, 0.048), (0.3415, 0.048)]
    kw, cw = 2.0e5, 3000.0
    kh, ch = 5.0e5, 3000.0
    x, z, th, vx, vz, w = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    s, t = 0.0, 0.0
    frames, events = [], []
    phase, t_hold = "lift", None
    # settle on the wheels first
    z = -mass * G / (2 * kw)
    min_clear, step = None, 0

    def world(px, pz):
        cx, cz = px - cg[0], pz - cg[1]
        return (x + cg[0] + cx * math.cos(th) - cz * math.sin(th), z + cg[1] + cx * math.sin(th) + cz * math.cos(th))

    def vel_at(qx, qz):
        ox, oz = x + cg[0], z + cg[1]
        return vx - w * (qz - oz), vz + w * (qx - ox)

    while t < t_end:
        fx, fz, tq = 0.0, -mass * G, 0.0
        ox, oz = x + cg[0], z + cg[1]

        def apply(Fx, Fz, qx, qz):
            nonlocal fx, fz, tq
            fx += Fx; fz += Fz; tq += (qx - ox) * Fz - (qz - oz) * Fx

        for px, pz in wheels:
            qx, qz = world(px, pz - 0.0381)
            pen = -qz
            if pen > 0:
                pvx, pvz = vel_at(qx, qz)
                Fn = max(0.0, kw * pen - cw * pvz)
                apply(friction(Fn, pvx, 0.9), Fn, qx, qz)
        for px, pz in bumper_pts:
            qx, qz = world(px, pz)
            floor = 0.008 if qx >= 0.4179 else 0.0
            if qz < floor:
                pvx, pvz = vel_at(qx, qz)
                Fn = max(0.0, kw * (floor - qz) - cw * pvz)
                apply(friction(Fn, pvx, 0.5), Fn, qx, qz)
            if px > 0.4 and qx > upright_x:
                pvx, pvz = vel_at(qx, qz)
                Fn = max(0.0, kw * (qx - upright_x) + cw * pvx)
                apply(-Fn, friction(Fn, pvz, mu_up), qx, qz)
        # hook: arm underside at local z 0.7084 - s over x 0.289-0.513, jaw inner face at local x 0.501
        arm_a, arm_b = world(0.289, 0.7084 - s), world(0.513, 0.7084 - s)
        jaw_a, jaw_b = world(0.501, 0.7084 - s), world(0.501, 0.6804 - s)
        T = 0.0
        for a, b, label in ((arm_a, arm_b, "arm"), (jaw_a, jaw_b, "jaw")):
            d, nx, nz, qx, qz = seg_contact(rung[0], rung[1], a, b)
            pen = rung[2] - d
            if pen > 0:
                pvx, pvz = vel_at(qx, qz)
                vn = -(pvx * nx + pvz * nz)
                Fn = max(0.0, kh * pen - ch * vn)
                Fx, Fz = -Fn * nx, -Fn * nz          # force of the rung on the hook
                apply(Fx, Fz, qx, qz)
                T += max(0.0, Fz)
        # winch: cable tension equals the vertical hook load
        if phase == "lift":
            avail = min(f_stall12 * bus_v / 12, f_lim)   # voltage or current limit, whichever binds
            vs = v_free12 * bus_v / 12 * (1 - T / avail)  # negative when the load exceeds it: the hook backdrives
            s = max(0.0, min(stroke, s + vs * dt))
            if s >= stroke:
                phase, t_hold = "hold", t
                events.append(dict(t=round(t, 4), event=f"stroke complete; power removed, {'brake holds' if brake else 'no brake: winch coasts'}"))
        elif not brake:
            s = max(0.0, s - T / 400.0 * dt)       # coasting gearbox backdrives under load
        vx += fx / mass * dt; vz += fz / mass * dt; w += tq / inertia * dt
        x += vx * dt; z += vz * dt; th += w * dt; t += dt; step += 1
        lowest = min(world(px, pz - 0.0381)[1] for px, pz in wheels)
        bumper_low = min(world(px, pz)[1] - (0.008 if world(px, pz)[0] >= 0.4179 else 0.0) for px, pz in bumper_pts)
        clear = min(lowest, bumper_low)
        if step % 50 == 0:
            frames.append([round(t, 4), round(x, 5), round(z, 5), round(th, 5), round(s, 5), round(T, 1)])
        if t_hold is not None and t >= t_hold:
            min_clear = clear if min_clear is None else min(min_clear, clear)
            if t >= t_hold + 3.0:
                events.append(dict(t=round(t, 4), event="3 s assessment window complete"))
                break
    ok = t_hold is not None and min_clear is not None and min_clear > 0.005
    return dict(name=name, kind="elevation", passed=ok,
                metric=dict(name="minimum clearance to carpet or TOWER BASE during the 3 s assessment (m)",
                            value=None if min_clear is None else round(min_clear, 4), requirement="greater than 5 mm throughout"),
                firstUnmet=None if ok else ("stroke never completed" if t_hold is None else "robot touches the carpet or TOWER BASE during assessment"),
                imposed="winch follows a DC motor line (NEO, 25:1, 12.5 mm spool) at the stated bus voltage and current limit",
                solved="robot translation and pitch with unilateral wheel, bumper, upright and hook contacts",
                limits="Side view: both hooks and both uprights act in one plane. The 6.4 mm lateral bumper-to-upright overlap and any roll are not represented (open F4).",
                params=dict(mass=mass, cg=cg, busV=bus_v, brake=brake, muUpright=mu_up, dt=dt, stroke=stroke, currentLimitA=i_limit,
                            stallForceN=f_stall12, freeSpeedMps=v_free12, wheelK=kw, hookK=kh),
                rung=rung, uprightX=upright_x, events=events, frames=frames)


def main():
    trials = [
        acquisition("acquire-nominal"),
        acquisition("acquire-belt-locked (cause isolation)", locked=True),
        acquisition("acquire-low-friction-light-compression (adverse)", mu_belt=0.5, comp_back=0.010, comp_pulley=0.010),
        acquisition("acquire-nominal-half-step", dt=5e-5),
        acquisition("acquire-belt-friction-0.7", mu_belt=0.7),
        acquisition("acquire-belt-friction-0.5", mu_belt=0.5),
        acquisition("acquire-compression-15mm", comp_back=0.015, comp_pulley=0.015),
        acquisition("acquire-compression-10mm", comp_back=0.010, comp_pulley=0.010),
        acquisition("acquire-compression-17.5mm", comp_back=0.0175, comp_pulley=0.0175),
        acquisition("acquire-compression-25mm", comp_back=0.025, comp_pulley=0.025),
        acquisition("acquire-belt-2.5mps", u=2.5),
        acquisition("acquire-belt-2.0mps", u=2.0),
        acquisition("acquire-belt-1.5mps", u=1.5),
        acquisition("acquire-approach-1.0mps", v_robot=1.0),
        delivery("deliver-nominal"),
        delivery("deliver-slow-6.70 (adverse)", v=6.70),
        delivery("deliver-strong-spin-CL0.30 (adverse)", cl=0.30),
        delivery("deliver-stiff-contact-30k (sensitivity)", k=30000.0),
        delivery("deliver-nominal-half-step", dt=5e-5),
        delivery("deliver-6.40", v=6.40),
        delivery("deliver-6.55", v=6.55),
        delivery("deliver-7.10", v=7.10),
        delivery("deliver-7.30", v=7.30),
        elevation("hang-nominal"),
        elevation("hang-no-brake (disabled control)", brake=False),
        elevation("hang-weak-battery-8V-low-upright-friction (adverse)", bus_v=8.0, mu_up=0.2),
        elevation("hang-nominal-half-step", dt=5e-5),
        elevation("hang-current-limit-30A", i_limit=30.0),
        elevation("hang-current-limit-20A", i_limit=20.0),
        elevation("hang-current-limit-15A", i_limit=15.0),
        elevation("hang-current-limit-10A", i_limit=10.0),
        elevation("hang-current-limit-8A", i_limit=8.0),
    ]
    layout = HERE / "layout.json"
    out = dict(schema="frc-2026-poc/field-trials@1", issue="R3-PD2",
               layout={"file": "design/preliminary/layout.json", "sha256": sha(layout)},
               rules={"file": "design/preliminary/construction-rules.json", "sha256": sha(HERE / "construction-rules.json")},
               solver="Semi-implicit Euler; penalty normal contact k with damping ratio zeta; Coulomb friction regularized at 0.01 m/s",
               scenarioNotes=[
                   "Acquisition: side view at the front bumper; compression of the belt and pulley is the detailed setting the layout reserves as 3 mm undeformed.",
                   "Delivery: release state from the layout's hood exit at the 2.7 m shot pose; HUB body, top plate and cavity from V0 dimensions; the sensor plane at 1.50 m inside the opening is an assumption (V0 does not locate it).",
                   "Elevation: rung centred in the upright depth (V0), uprights 5 mm ahead of the bumper, TOWER BASE edge 0.4 mm ahead of the bumper face.",
                   "Contact stiffness, damping and friction are estimates, not measured; the FUEL release speed and spin are designed, not measured."],
               trials=trials)
    text = json.dumps(out, separators=(",", ":"))
    (HERE / "field-trials.json").write_text(text + "\n", encoding="utf-8", newline="\n")
    out["trace"] = {"file": "design/preliminary/field-trials.json", "sha256": sha(HERE / "field-trials.json")}
    template = (HERE / "field-interaction-template.html").read_text(encoding="utf-8")
    page = template.replace("TRIAL_DATA", json.dumps(out, separators=(",", ":")).replace("<", "\\u003c"))
    (HERE / "review" / "field-interaction.html").write_text(page, encoding="utf-8", newline="\n")
    for tr in trials:
        print(f"{tr['name']:58s} {'PASS' if tr['passed'] else 'FAIL'}  {tr['metric']['name']}={tr['metric']['value']}  {tr.get('firstUnmet') or ''}")
        if tr["kind"] == "acquisition":
            print("   ", tr["beltDemand"])
        if tr["kind"] == "delivery":
            print("   ", [e["event"] + " " + str(e.get("at", "")) for e in tr["events"]])
        if tr["kind"] == "elevation":
            print("    max pitch deg", round(max(abs(f[3]) for f in tr["frames"]) * 57.3, 2), "peak cable N", max(f[5] for f in tr["frames"]), [e["event"] for e in tr["events"]])


if __name__ == "__main__":
    main()
