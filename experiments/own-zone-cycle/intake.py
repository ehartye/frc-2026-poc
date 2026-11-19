"""Planar ground acquisition in one moving robot frame; SI throughout the integration."""

import math


def simulate_intake(cad, h=0.0001, roller=True, drive=0.38, guides=True, wheels=None):
    by = {p["name"]: p for p in cad}
    part = by["ground intake roller"]
    radius = 0.150114 / 2
    mass = 0.215
    inertia = 0.4 * mass * radius**2
    arm = by["left intake bearing arm"]
    pivot = (arm["start"][0] / 1000, arm["start"][2] / 1000)
    lever = math.dist(arm["start"], arm["end"]) / 1000
    capture = math.radians(-39)
    cx = pivot[0] + lever * math.cos(capture)
    cz = pivot[1] + lever * math.sin(capture)
    wheelr = part["radius"] / 1000
    ramp = by["left intake ramp"]
    back, front = [(v[0] / 1000, v[2] / 1000) for v in [ramp["start"], ramp["end"]]]
    dy = (ramp["start"][1] - ramp["width"] / 2) / 1000
    rim = math.sqrt(radius**2 - dy**2)
    thickness = ramp["height"] / 2000
    wheelpart = by["left scoring wheel"]
    j, k = wheelpart["start"], wheelpart["end"]
    center_x = (j[0] + k[0]) / 2000
    center_z = (j[2] + k[2]) / 2000
    rotor_axis_x = (k[0] - j[0]) / math.dist(j, k)
    rotor_axis_z = (k[2] - j[2]) / math.dist(j, k)
    tangent_x, tangent_z = rotor_axis_z, -rotor_axis_x
    lateral = abs(j[1]) / 1000
    shot_r = wheelpart["radius"] / 1000
    width = math.dist(j, k) / 1000
    rotor_inertia = 0.5 * (math.pi * shot_r**2 * width * 1100) * shot_r**2
    rotor_speed = 0 if wheels is None else wheels["rimMps"] / shot_r
    release = None
    first_touch = None
    shot_work = 0.0
    chassis_x = 0.0
    x, z = 0.46, radius
    vx, vz = -drive, 0.0
    spin = 0.0
    bar = by["front deck crossmember"]
    bx = bar["start"][0] / 1000
    bz = bar["start"][2] / 1000
    hx = bar["width"] / 2000
    hz = bar["height"] / 2000
    cleat = by["left lift shelf 1"]
    pad = cleat["lower"][1] / 1000
    support_rad = math.sqrt(radius**2 - pad**2)
    rows = []
    contacts = set()
    crossing = None
    lifted = None
    contact_plane = 0.280
    parked = None
    brake_at = None
    for k in range(round(2.0 / h) + 1):
        t = k * h
        elapsed = 0 if parked is None else max(0, t - parked)
        if parked is not None and brake_at is None and z > 0.25:
            brake_at = t
        brake_time = 0 if brake_at is None else t - brake_at
        chassis_speed = (
            drive if brake_at is None else drive * max(0, 1 - brake_time / 0.35)
        )
        body_accel = -drive / 0.35 if brake_at is not None and brake_time < 0.35 else 0
        chassis_x += chassis_speed * h
        fx, fz, moment = -mass * body_accel, -mass * 9.80665, 0.0
        angle = capture + min(1, elapsed / 0.2) * math.radians(31)
        cx = pivot[0] + lever * math.cos(angle)
        cz = pivot[1] + lever * math.sin(angle)
        # Lower the shelf 33 mm at intake pickup. Each returning cleat remains
        # on the other branch until the indexed carrier advances.
        lift = min(0.490, max(0, elapsed - 0.23) * 0.65)
        lift_speed = 0.65 if 0 < lift < 0.49 else 0.0

        def force(nx, nz, depth, arm_radius, surface, mu, name, normal_speed=0):
            nonlocal fx, fz, moment
            if depth <= 0:
                return
            normal = max(
                0.0, 2500.0 * depth - 10.0 * (vx * nx + vz * nz - normal_speed)
            )
            tx, tz = -nz, nx
            relative = vx * tx + vz * tz - spin * arm_radius - surface
            tangent = -mu * normal * math.tanh(relative / 0.035)
            fx += normal * nx + tangent * tx
            fz += normal * nz + tangent * tz
            moment -= tangent * arm_radius
            if normal > 0.01:
                contacts.add(name)

        force(0, 1, radius - z, radius, chassis_speed, 0.55, "carpet")
        dx, dz = x - cx, z - cz
        d = math.hypot(dx, dz)
        force(
            dx / d,
            dz / d,
            radius + wheelr - d,
            radius,
            -1.25 if roller else 0.0,
            0.65,
            "intake roller",
        )
        sx, sz = back[0] - front[0], back[1] - front[1]
        along = min(
            1, max(0, ((x - front[0]) * sx + (z - front[1]) * sz) / (sx * sx + sz * sz))
        )
        dx = x - front[0] - along * sx
        dz = z - front[1] - along * sz
        d = math.hypot(dx, dz)
        force(dx / d, dz / d, rim + thickness - d, rim, 0, 0.28, "two ramp edges")

        def rectangle(x0, x1, z0, z1, effective_radius, normal_v, name, friction):
            dx = x - min(x1, max(x0, x))
            dz = z - min(z1, max(z0, z))
            d = math.hypot(dx, dz)
            if d > 1e-10:
                nx, nz = dx / d, dz / d
                force(
                    nx,
                    nz,
                    effective_radius - d,
                    effective_radius,
                    normal_v * nx,
                    friction,
                    name,
                    normal_v * nz,
                )

        rectangle(
            bx - hx,
            bx + hx,
            bz - hz,
            bz + hz,
            radius,
            0,
            "front deck crossmember",
            0.35,
        )
        rectangle(
            0.196,
            0.292,
            0.066 + lift,
            0.072 + lift,
            support_rad,
            lift_speed,
            "paired indexed shelves",
            0.6,
        )
        if guides:
            for name in [
                "rear lift custody gate",
                "front lift custody guide",
                "central fore-aft feed deck",
            ]:
                q = by[name]
                a, b = q["lower"], q["upper"]
                rectangle(
                    a[0] / 1000,
                    b[0] / 1000,
                    a[2] / 1000,
                    b[2] / 1000,
                    radius,
                    0,
                    name,
                    0.20,
                )
        if wheels is not None:
            u = (x - center_x) * tangent_x + (z - center_z) * tangent_z
            axial = (x - center_x) * rotor_axis_x + (z - center_z) * rotor_axis_z
            radial = math.hypot(u, lateral)
            # Symmetric opposing lateral cylinders. In this central slice their
            # lateral forces and piece spin moments cancel. Include stored roller
            # energy, finite footprint and slip. No motor torque during transit.
            depth = radius + shot_r - radial
            if depth > 0 and abs(axial) < width / 2:
                if first_touch is None:
                    first_touch = t
                speed = vx * tangent_x + vz * tangent_z
                normal = max(0, wheels["stiffness"] * depth - 4 * speed * u / radial)
                slip = shot_r * rotor_speed - speed * lateral / radial
                traction = wheels["mu"] * normal * math.tanh(slip / 0.08)
                net = 2 * (normal * u / radial + traction * lateral / radial)
                fx += net * tangent_x
                fz += net * tangent_z
                rotor_speed -= traction * shot_r / rotor_inertia * h
                shot_work += net * speed * h
                contacts.add("paired scoring wheels")
            elif (
                first_touch is not None
                and release is None
                and u > 0
                and vx * tangent_x + vz * tangent_z > 0
            ):
                release = {
                    "timeS": t,
                    "positionMm": [x * 1000, 0, z * 1000],
                    "velocityMps": [vx, 0, vz],
                    "relativeAxisOffsetMm": axial * 1000,
                    "rollerKineticEnergyJ": rotor_inertia * rotor_speed**2,
                    "workOnPieceJ": shot_work,
                    "chassisTravelM": chassis_x,
                    "chassisSpeedMps": chassis_speed,
                    "spinRadS": spin,
                }
                rows.append([round(t, 6), round(x * 1000, 4), 0, round(z * 1000, 4)])
                break
        if parked is None and x < contact_plane and abs(vx) < 0.10 and t > 0.25:
            parked = t
            crossing = {
                "timeS": t,
                "positionMm": [x * 1000, 0, z * 1000],
                "velocityMps": [vx, 0, vz],
                "spinRadS": spin,
            }
        if elapsed > 0.23 and z > 0.54 and lifted is None:
            lifted = {
                "timeS": t,
                "positionMm": [x * 1000, 0, z * 1000],
                "velocityMps": [vx, 0, vz],
            }
        if k % max(1, round(0.01 / h)) == 0:
            rows.append([round(t, 5), round(x * 1000, 4), 0, round(z * 1000, 4)])
        vx += fx / mass * h
        vz += fz / mass * h
        spin += moment / inertia * h
        x += vx * h
        z += vz * h
    return {
        "events": sorted(contacts),
        "crossing": crossing,
        "lifted": lifted,
        "trajectory": rows,
        "finalMm": [x * 1000, 0, z * 1000],
        "dt": h,
        "release": release,
        "wheelContactAtS": first_touch,
    }


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cad/own-zone-upper"))
    from prepare_upper import parts

    for h, roller, drive in [
        (0.0001, True, 0.38),
        (0.00005, True, 0.38),
        (0.0001, False, 0.38),
        (0.0001, False, 0),
    ]:
        r = simulate_intake(parts()[1], h, roller, drive)
        print(h, roller, drive, r["crossing"], r["finalMm"], r["lifted"], r["events"])
