"""Planar compliant rung, bumper and floor contacts for the project-owned twin hook assembly."""

import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
G = 9.80665
R = 0.021082
TRAVEL = 0.100
CAPTURE = 0.215


def smooth(t, distance, duration):
    u = max(0, min(1, t / duration))
    return distance * u * u * (3 - 2 * u), distance * 6 * u * (1 - u) / duration


def run(
    name,
    *,
    dt=0.00025,
    mass=62.0,
    cog_x=0.0,
    axial_error=0.0,
    lateral_error=0.0,
    roll_deg=0.0,
    motor_a=23.0,
    thread_mu=0.14,
    powered_cut=9.0,
    read_after=2.0,
    disable=False,
    bumper_k=64000,
    observe_contacts=None,
):
    tower = json.loads((HERE / "field.json").read_bytes())["sides"]["blue"]
    low = min(
        (p for p in tower if "Tower Rung" in p["name"]), key=lambda p: p["boundsMm"][2]
    )["boundsMm"]
    upright = max(
        (p for p in tower if "Upright Outer" in p["name"]),
        key=lambda p: p["boundsMm"][1],
    )["boundsMm"]
    # Datum chosen at the nearest wallward face of the selected upright exterior sheet.
    face = upright[3] / 1000
    rung_x = (low[0] + low[3]) / 2000 - face - 0.416 + axial_error
    rung_z = (low[2] + low[5]) / 2000
    # The compression pad is the existing rear bumper. The low rung supports both offset hooks.
    base = next(p for p in tower if "Base Bottom" in p["name"])
    plate_front = base["boundsMm"][3] / 1000 - face - 0.416
    plate_top = (
        max(
            base["fieldward145mmTopMm"],
            *(p["boundsMm"][5] for p in tower if "Tower Base Angle" in p["name"]),
        )
        / 1000
    )
    half_width = (upright[4] - upright[1]) / 2000
    low_half_y = [(v - (upright[1] + upright[4]) / 2) / 1000 for v in (low[1], low[4])]
    hook_y = [-0.088 + lateral_error, 0.088 + lateral_error]
    lands = [
        low_half_y[0] + 0.006 < y < low_half_y[1] - 0.006
        and abs(y) > 0.006 + half_width
        for y in hook_y
    ]
    if abs(lateral_error) > 0.340:
        raise ValueError("Offset loses upright under the rear bumper")
    # World is local to the parked robot, X away from the alliance wall, Z upward.
    # A single longitudinal plane assumes symmetric loading. A static roll offset changes each contact gap.
    com_h = 0.320
    x, z, a = cog_x, com_h - mass * G / (2 * 220000), 0.0
    vx = vz = omega = down = dv = 0.0
    lead = 0.002
    ratio = 6.0
    mean_diameter = 0.009
    helix = math.atan(lead / (math.pi * mean_diameter))
    phi = math.atan(thread_mu / math.cos(math.radians(14.5)))
    equiv = 2 * 0.000050 * (2 * math.pi * ratio / lead) ** 2
    inertia = mass * (0.68**2 + 0.64**2) / 12
    peak = {
        "eachHookN": [0.0, 0.0],
        "uprightN": 0.0,
        "currentA": 0.0,
        "wheelN": 0.0,
        "pitchDeg": 0.0,
    }
    rows = []
    first = None
    worst_clear = 1.0
    lost = None
    for i in range(math.ceil((powered_cut + read_after) / dt) + 1):
        t = i * dt
        ext, ve = smooth(min(t, powered_cut), CAPTURE, 1.24)
        # Closed-loop screw position target slows before the end of its stroke.
        commanded, vr = smooth(t - 1.30, 0 if disable else TRAVEL, 7.35)
        c = math.cos(a)
        s = math.sin(a)
        fx = 0.0
        fz = -mass * G
        tau = 0.0
        hook = [[0.0, 0.0], [0.0, 0.0]]
        hook_contacts = [] if observe_contacts is not None else None
        wheel = 0.0
        brace = 0.0

        def point(lx, lz):
            u = lx - cog_x
            v = lz - com_h
            return x + c * u - s * v, z + s * u + c * v

        def apply(lx, lz, nx, nz, k, damping, depth, friction, ldx=0.0, ldz=0.0):
            nonlocal fx, fz, tau
            if depth <= 0:
                return 0.0, 0.0
            wx, wz = point(lx, lz)
            rx = wx - x
            rz = wz - z
            ux = vx - omega * rz + c * ldx - s * ldz
            uz = vz + omega * rx + s * ldx + c * ldz
            normal = max(0.0, k * depth - damping * (ux * nx + uz * nz))
            slip = ux * nz - uz * nx
            tangent = -friction * normal * math.tanh(slip / 0.008)
            qx = nx * normal + nz * tangent
            qz = nz * normal - nx * tangent
            fx += qx
            fz += qz
            tau += rx * qz - rz * qx
            return qx, qz

        tire_gap = []
        for lx in (-0.268, 0.268):
            wx, wz = point(lx, 0.0381)
            tire_gap.append(wz - 0.0381)
            force = apply(lx, 0.0, 0, 1, 220000, 1100, -tire_gap[-1], 0.62)
            wheel += force[1]
        # Normal at the nearest rear cover edge under pitch; friction at the upright face.
        lx, lz = min(((-0.416, 0.048), (-0.416, 0.168)), key=lambda p: point(*p)[0])
        wx, wz = point(lx, lz)
        brace_force = apply(lx, lz, 1, 0, bumper_k, 260, -0.416 - wx, 0.18)
        brace = brace_force[0]
        brace_position = (wx, wz)
        # Transform the stationary rung center to the current chassis frame.
        cx = c * (rung_x - x) + s * (rung_z - z) + cog_x
        cz = -s * (rung_x - x) + c * (rung_z - z) + com_h
        for j, ly in enumerate(hook_y):
            if not lands[j]:
                continue
            offset_z = math.tan(math.radians(roll_deg)) * ly
            for xmin, xmax, zmin, zmax in (
                (-0.283, -0.211, 0.737, 0.753),
                (-0.283, -0.271, 0.710, 0.737),
                (-0.223, -0.211, 0.710, 0.737),
            ):
                xmin -= ext
                xmax -= ext
                zmin += offset_z - down
                zmax += offset_z - down
                px = max(xmin, min(xmax, cx))
                pz = max(zmin, min(zmax, cz))
                dx = px - cx
                dz = pz - cz
                dist = math.hypot(dx, dz)
                if dist >= R or dist < 1e-9:
                    continue
                nx = (c * dx - s * dz) / dist
                nz = (s * dx + c * dz) / dist
                qx, qz = apply(px, pz, nx, nz, 180000, 115, R - dist, 0.14, -ve, -dv)
                if hook_contacts is not None:
                    hook_contacts.append((j, px, pz, *point(px, pz), qx, qz))
                hook[j][0] += qx
                hook[j][1] += qz
        if observe_contacts is not None:
            observe_contacts(t, a, (x, z), hook_contacts, brace_position, brace_force)
        resistance = max(0.0, sum((-s * h[0] + c * h[1]) for h in hook))
        # Two independent NEO envelopes; track the per-screw worst nominal shared torque.
        demand = 0.0
        for hx, hz in hook:
            axial = max(0, -s * hx + c * hz)
            demand = max(
                demand,
                (axial * mean_diameter * 0.5 * math.tan(helix + phi))
                / (ratio * 0.82 * (2.6 / 105)),
            )
        speed_cap = 5676 / 60 * lead / ratio * max(0.0, (11.0 - demand * 12 / 105) / 12)
        if t < powered_cut:
            if demand > motor_a:
                speed_cap = 0
            speed_target = min(speed_cap, max(0, vr + 5 * (commanded - down)))
            dv += max(-0.20 * dt, min(0.20 * dt, speed_target - dv))
        elif phi >= helix:
            dv = 0.0
        else:
            backwards = (
                resistance
                * mean_diameter
                * 0.5
                * math.tan(helix - phi)
                * 2
                * math.pi
                / lead
            )
            dv = max(-0.16, dv - backwards * dt / equiv)
        down = max(0.0, min(TRAVEL, down + dv * dt))
        if down == 0 or down == TRAVEL:
            dv = 0.0
        vx += fx / mass * dt
        vz += fz / mass * dt
        omega += tau / inertia * dt
        x += vx * dt
        z += vz * dt
        a += omega * dt
        # Only the bumper overlaps the fieldward lip; conservative including the highest
        # measured lip face and all four base angle tops. Wheels remain fieldward.
        foot = [
            point(lx, lz)
            for lx, lz in (
                (-0.416, 0.048),
                (-0.340, 0.048),
                (0.340, 0.048),
                (0.416, 0.048),
            )
        ]
        over = [pz - plate_top for px, pz in foot if px < plate_front]
        base_gap = min(over, default=1.0)
        low_tire = min(tire_gap)
        loaded = sum(h[1] for h in hook) > mass * G * 0.65
        seen = loaded and low_tire > 0.001 and base_gap > 0.001 and all(lands)
        if seen and first is None:
            first = t
        if t >= powered_cut and first is not None and not seen and lost is None:
            lost = t
        if t >= powered_cut:
            worst_clear = min(worst_clear, low_tire, base_gap)
        for j, h in enumerate(hook):
            peak["eachHookN"][j] = max(peak["eachHookN"][j], math.hypot(*h))
        peak["uprightN"] = max(peak["uprightN"], brace)
        peak["currentA"] = max(peak["currentA"], demand)
        peak["pitchDeg"] = max(peak["pitchDeg"], abs(math.degrees(a)))
        peak["wheelN"] = max(peak["wheelN"], wheel)
        if i % round(0.025 / dt) == 0 or i == math.ceil(
            (powered_cut + read_after) / dt
        ):
            rows.append(
                dict(
                    t=round(t, 6),
                    x=x - cog_x,
                    z=z - com_h,
                    pitch=a,
                    deploy=ext,
                    down=down,
                    hookXZ=hook,
                    uprightN=brace,
                    wheelN=wheel,
                    tireGapM=low_tire,
                    baseGapM=base_gap,
                    qualified=seen,
                )
            )
    last = rows[-1]
    return dict(
        name=name,
        dt=dt,
        massKg=mass,
        startDatumX=face + 0.416 - axial_error,
        startDatumY=(upright[1] + upright[4]) / 2000 + lateral_error,
        rungX=rung_x,
        rungZ=rung_z,
        cutS=powered_cut,
        assessedS=powered_cut + read_after,
        hasTwoContacts=lands,
        threadSelfLocks=phi >= helix,
        firstClearS=first,
        lostAfterCutS=lost,
        minimumAssessedClearanceM=worst_clear,
        peak=peak,
        atAssessment=last,
        conditionalTeleopPoints=10 if last["qualified"] else 0,
        rows=rows,
    )


if __name__ == "__main__":
    trials = []
    for name, kw in (
        ("nominal", {}),
        ("finer", {"dt": 0.000125}),
        ("loaded", {"mass": 68.0, "cog_x": 0.035}),
        ("early-cut", {"powered_cut": 2.0}),
        ("stalled-drive", {"disable": True}),
        ("missed-rung", {"lateral_error": 0.23}),
        ("released-thread", {"thread_mu": 0.035}),
        ("roll-error", {"roll_deg": 1.5}),
    ):
        r = run(name, **kw)
        rows = r.pop("rows")
        if name == "nominal":
            (HERE / "motion.json").write_text(
                json.dumps(rows, separators=(",", ":")) + "\n",
                encoding="utf8",
                newline="\n",
            )
        trials.append(r)
    (HERE / "support.json").write_text(
        json.dumps(trials, indent=2) + "\n", encoding="utf8", newline="\n"
    )
    for t in trials:
        print(
            t["name"],
            t["conditionalTeleopPoints"],
            t["firstClearS"],
            t["atAssessment"]["tireGapM"],
            t["peak"]["currentA"],
        )
