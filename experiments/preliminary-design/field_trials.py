"""Physics trials for R3's mission-critical field interactions: acquisition up the intake chute, entry to the stage,
the hold-back, launch, the batch through the one flywheel, collecting, holding and feeding 24 FUEL in the hopper,
delivery into the HUB and the Level 1 hang.

Each trial integrates the free FUEL or the supported robot with penalty contact and regularized Coulomb
friction (explicit semi-implicit Euler). Actuator inputs are stated per trial: a belt or wheel surface speed is
imposed (transport at that speed, not proof the motor sustains it); the winch follows a DC motor line with
a current limit and bus voltage. Units are SI. The mechanism geometry comes from dimensions.py, the same module
the placed solids are built from, so the bumper, intake, floor lane and shooter surfaces have one definition.
The HUB, the TOWER and the hook are written here separately.

The tracked FUEL is one chain: acquire-nominal ends at capture, entry-nominal starts from that state and ends at
rest in the seat, launch-nominal starts from that seat and ends at release, and deliver-nominal starts from that
release state. build_package.py turns those four traces into the package's FUEL cases.

    python -I -B experiments/preliminary-design/field_trials.py

Writes experiments/preliminary-design/field-trials.json. build_package.py fits the tracked FUEL's package cases to
its traces and writes each trial's qualification record into the release.
"""
import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import dimensions as D

ROOT = HERE.parents[1]
RULES = json.loads((HERE / "construction-rules.json").read_text(encoding="utf-8"))
G = 9.81
R = RULES["fuel"]["diameterMm"] / 2000
assert abs(R - D.R_BALL / 1000) < 1e-12
RHO = 1.2
MM = 0.001


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Contacts:
    """Per-surface contact record: rows [t_on, t_off, mm] with the deepest indentation seen in each row.
    A continuous contact is cut into rows no longer than `window` seconds, so the depth is resolved in time."""
    def __init__(self, window=0.05):
        self.rows, self.open, self.window = {}, {}, window

    def step(self, t, touching):
        for label, pen in touching.items():
            row = self.open.get(label)
            if row is None or t - row[0] >= self.window:
                row = self.open[label] = [round(t, 4), round(t, 4), 0.0]
                self.rows.setdefault(label, []).append(row)
            row[1] = round(t, 4); row[2] = max(row[2], pen * 1000)
        for label in [k for k in self.open if k not in touching]:
            del self.open[label]

    def result(self):
        return {k: [[a, b, round(c, 3)] for a, b, c in v] for k, v in self.rows.items()}


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


# ------------------------------------------------------------------ brushless motor line
# A NEO-class brushless motor: 5676 rpm free, 2.6 N m stall, 105 A stall, 1.8 A free at 12 V (published motor curve
# figures; the selected motor's own curve replaces them at detailed design).
MOTOR = dict(freeRadps=5676 * 2 * math.pi / 60, stallNm=2.6, stallA=105.0, freeA=1.8)
MOTOR["ohm"] = 12.0 / MOTOR["stallA"]
MOTOR["kt"] = MOTOR["stallNm"] / (MOTOR["stallA"] - MOTOR["freeA"])
MOTOR["ke"] = (12.0 - MOTOR["freeA"] * MOTOR["ohm"]) / MOTOR["freeRadps"]


def motor_current(want_a, motor_radps, bus_v, stator_a, supply_a=None):
    """Winding current (A) one motor can carry at this speed: the request, limited by the stator limit, by the bus
    voltage left above the back-EMF, and by the supply limit on its electrical input. Returns (current, supply amps)."""
    e = MOTOR["ke"] * motor_radps
    i = max(0.0, min(want_a, stator_a, (bus_v - e) / MOTOR["ohm"]))
    if supply_a is not None:   # input power e i + i^2 R may not exceed bus_v * supply_a
        a, b, c = MOTOR["ohm"], e, -bus_v * supply_a
        i = min(i, (-b + math.sqrt(b * b - 4 * a * c)) / (2 * a))
    return i, i * (e + i * MOTOR["ohm"]) / bus_v


class WheelDrive:
    """The flywheel as a free body: inertia, two direct brushless motors and a speed loop. The loop asks for full
    current when the wheel is band (a fraction of the setpoint) slow and none at the setpoint."""
    def __init__(self, setpoint_mps=None, inertia=None, motors=None, gear=None, stator_a=None, supply_a=None, bus_v=12.0,
                 band=0.005, efficiency=0.9, drag_nm=0.02, start_mps=None, powered=True):
        S = D.SHOOTER
        self.set = S["wheel_surface_mps"] if setpoint_mps is None else setpoint_mps
        self.inertia = S["inertia_kgm2"] if inertia is None else inertia
        self.motors = S["motors"] if motors is None else motors
        self.gear = S["gear"] if gear is None else gear
        self.stator_a = S["stator_a"] if stator_a is None else stator_a
        supply_a = S["supply_a"] if supply_a is None else supply_a
        self.supply_a, self.bus_v, self.band, self.eff, self.drag, self.powered = supply_a, bus_v, band, efficiency, drag_nm, powered
        self.rw = D.FLYWHEEL_R * MM
        self.omega = (self.set if start_mps is None else start_mps) / self.rw
        self.peak_supply_a, self.motor_j, self.amps = 0.0, 0.0, 0.0

    @property
    def mps(self):
        return self.omega * self.rw

    def step(self, load_nm, dt):
        """Advance the wheel by dt under load_nm (the FUEL's friction torque on the wheel, negative when it slows it)."""
        want = self.stator_a * min(1.0, max(0.0, (self.set - self.mps) / (self.band * self.set))) if self.powered else 0.0
        i, supply = motor_current(want, self.omega * self.gear, self.bus_v, self.stator_a, self.supply_a)
        torque = self.motors * self.gear * MOTOR["kt"] * i * self.eff
        self.amps = self.motors * supply
        self.peak_supply_a = max(self.peak_supply_a, self.amps)
        self.motor_j += torque * self.omega * dt
        self.omega = max(0.0, self.omega + (load_nm + torque - self.drag) / self.inertia * dt)

    def record(self):
        return dict(setpointMps=self.set, inertiaKgM2=self.inertia, motors=self.motors, gear=self.gear, statorLimitA=self.stator_a,
                    supplyLimitA=self.supply_a, busV=self.bus_v, loopBand=self.band, efficiency=self.eff, dragNm=self.drag, powered=self.powered)


def spin_up(bus_v=12.0, dt=1e-3, **kw):
    """Time (s) and peak battery-side current (A) for the flywheel motors to bring the wheel from rest to its ready band."""
    d = WheelDrive(start_mps=0.0, bus_v=bus_v, **kw)
    t = 0.0
    while d.mps < d.set * (1 - D.SHOOTER["ready_band"]) and t < 20.0:
        d.step(0.0, dt); t += dt
    return dict(busV=bus_v, seconds=round(t, 3) if t < 20.0 else None, peakSupplyA=round(d.peak_supply_a, 1), motorJ=round(d.motor_j, 1),
                storedJ=round(0.5 * d.inertia * d.omega ** 2, 1))


# ------------------------------------------------------------------ acquisition (side view, robot frame)
def back_plate():
    """The chute back plate in the side view (metres): belt-side face, top edge and hopper-side face of the wedge."""
    I_, x1 = D.INTAKE, D.BUMPER["x1"]
    z0, z1 = I_["back_z0"], I_["back_top"]
    return [((x1 * MM, z0 * MM), (x1 * MM, z1 * MM)), (((x1 - I_["back_t"]) * MM, z1 * MM), (x1 * MM, z1 * MM)),
            (((x1 - I_["back_foot"]) * MM, z0 * MM), ((x1 - I_["back_t"]) * MM, z1 * MM)),
            (((x1 - I_["back_foot"]) * MM, z0 * MM), (x1 * MM, z0 * MM))]


def acquisition(name, u=None, comp_back=None, comp_pulley=None, mu_belt=0.9, mu_bumper=0.4, mu_carpet=0.6,
                k=15000.0, zeta=0.3, mass=0.215, v_robot=0.5, dt=1e-4, t_end=2.0, locked=False, every=40, mu_back=0.4,
                imposed=False, abreast=1, bus_v=12.0, gear=None, supply_a=None, stator_a=None, moving_kg=None, roller_ratio=None,
                back=True):
    """FUEL on the carpet; the robot drives at v_robot; the bottom pulley pulls it under, the back run lifts it
    against the bumper face and on up the chute back plate, and the top roller throws it over the top of the back
    plate into the hopper. The belt, pulleys, roller and back plate stand where dimensions.py puts them (the layout
    draws the same squeeze); comp_back and comp_pulley bracket that setting. The top roller turns roller_ratio times
    as fast as the belt. back=False removes the back plate (the control: the belt then has nothing to lift against
    above the bumper).

    The belt is a free body driven by its motor: an equivalent moving mass at the belt surface, one brushless motor
    through gear:1 to the 18.5 mm pulley, a speed loop to u, and the stator and supply current limits. abreast FUEL
    enter side by side and load the one belt together (each follows the same side-view path). imposed=True holds the
    belt speed instead, as the earlier issue did."""
    I_ = D.INTAKE
    u = I_["belt_mps"] if u is None else u
    gear = I_["gear"] if gear is None else gear
    supply_a = I_["supply_a"] if supply_a is None else supply_a
    stator_a = I_["stator_a"] if stator_a is None else stator_a
    moving_kg = I_["moving_kg"] if moving_kg is None else moving_kg
    comp_back = I_["pinch_squeeze"] * MM if comp_back is None else comp_back
    comp_pulley = I_["pulley_squeeze"] * MM if comp_pulley is None else comp_pulley
    roller_ratio = I_["roller_ratio"] if roller_ratio is None else roller_ratio
    ip = D.intake_points(comp_back * 1000, comp_pulley * 1000)
    B = D.BUMPER
    c = 2 * zeta * math.sqrt(k * mass)
    inertia = 0.4 * mass * R * R
    rp = ip["pulley_r"] * MM
    xk = ip["belt_x"] * MM                     # belt back run, pressing the FUEL into the bumper cover
    xp = ip["pulley_x"] * MM
    zb = ip["bottom_z"] * MM                   # bottom pulley centre: its underside compresses the FUEL top
    zt = ip["top_z"] * MM
    rr_ = ip["roller_r"] * MM
    roller = (ip["roller"][0] * MM, ip["roller"][1] * MM)
    belt_u = 0.0 if locked else u
    prims = [  # (kind, geometry, belt-driven surface direction or None, mu, label)
        ("seg", ((-1.0, 0.0), (2.0, 0.0)), None, mu_carpet, "carpet"),
        ("seg", ((B["x1"] * MM, B["z0"] * MM), (B["x1"] * MM, B["z1"] * MM)), None, mu_bumper, "bumper face"),
        ("seg", ((B["x0"] * MM, B["z1"] * MM), (B["x1"] * MM, B["z1"] * MM)), None, mu_bumper, "bumper top"),
        *([("seg", seg, None, mu_back, "chute back plate") for seg in back_plate()] if back else []),
        ("seg", ((xk, zb), (xk, zt)), (0.0, 1.0), mu_belt, "belt back run"),
        ("seg", ((xp + rp, zb), (xp + rp, zt)), (0.0, -1.0), mu_belt, "belt front run"),
        ("circ", ((xp, zb), rp), True, mu_belt, "bottom pulley"),
        ("circ", ((xp, zt), rp), True, mu_belt, "top pulley"),
        ("circ", (roller, rr_), True, mu_belt, "top roller"),
    ]
    edge = I_["back_top"] * MM if back else B["z1"] * MM
    x, z, vx, vz, w = 0.72, R, -v_robot, 0.0, 0.0
    t, frames, events, first = 0.0, [[0.0, round(x, 5), round(z, 5), 0.0]], [], {}
    max_belt_force, belt_power, belt_j, min_u, peak_supply = 0.0, 0.0, 0.0, belt_u, 0.0
    speed = [[0.0, round(belt_u, 3)]]
    captured = None
    step = 0
    contacts = Contacts(0.001 if every <= 10 else 0.05)
    while t < t_end:
        fx, fz, tq = 0.0, -mass * G, 0.0
        belt_now, belt_load = 0.0, 0.0
        touching = {}
        for kind, geom, driven, mu, label in prims:
            if kind == "seg":
                d, nx, nz, qx, qz = seg_contact(x, z, *geom)
                sx, sz = driven if driven else (0.0, 0.0)
            else:
                (cx, cz), rr = geom
                d0 = math.hypot(x - cx, z - cz)
                nx, nz = (x - cx) / d0, (z - cz) / d0
                d = d0 - rr
                sx, sz = nz, -nx                # the surface of a belt-driven pulley or roller moves along this unit direction
            pen = R - d
            if pen <= 0:
                continue
            ratio = roller_ratio if label == "top roller" else 1.0
            svx, svz = (-v_robot, 0.0) if label == "carpet" else (ratio * belt_u * sx, ratio * belt_u * sz)
            touching[label] = max(touching.get(label, 0.0), pen)
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
            if driven:
                along = ratio * Ft * (tx * sx + tz * sz)   # friction on the FUEL along the belt motion, reflected to the belt; the belt feels the opposite
                belt_load += along
                belt_now += along * belt_u
                max_belt_force = max(max_belt_force, Fn)
        contacts.step(t, touching)
        belt_power = max(belt_power, abreast * belt_now)
        belt_j += abreast * belt_now * dt
        if not locked and not imposed:
            motor_radps = belt_u / rp * gear
            want = stator_a * min(1.0, max(0.0, (u - belt_u) / (0.02 * u)))
            amps, supply = motor_current(want, motor_radps, bus_v, stator_a, supply_a)
            peak_supply = max(peak_supply, supply)
            force = gear * MOTOR["kt"] * amps * 0.85 / rp
            belt_u = max(0.0, belt_u + (force - abreast * belt_load) / moving_kg * dt)
            min_u = min(min_u, belt_u)
        vx += fx / mass * dt; vz += fz / mass * dt; w += tq / inertia * dt
        x += vx * dt; z += vz * dt; t += dt; step += 1
        if step % round(every * 1e-4 / dt) == 0:
            frames.append([round(t, 4), round(x, 5), round(z, 5), round(w, 2)])
        if step % round(100 * 1e-4 / dt) == 0:
            speed.append([round(t, 4), round(belt_u, 3)])
        if captured is None and x < D.FRONT_RAIL["x1"] * MM and z > edge + R * 0.5:
            captured = round(t, 4)
            events.append(dict(t=captured, event="FUEL over the back plate and inside the frame: captured"))
            break
        if z < -0.05 or x > 1.2:
            events.append(dict(t=round(t, 4), event="FUEL lost"))
            break
    if frames[-1][0] != round(t, 4):
        frames.append([round(t, 4), round(x, 5), round(z, 5), round(w, 2)])
    ok = captured is not None and captured <= 1.2
    driven_text = (f"belt and roller surface speed {belt_u if locked else u} m/s imposed" if locked or imposed else
                   f"belt and roller driven by one brushless motor through {gear:g}:1 to the pulley, speed loop to {u} m/s, {stator_a:g} A stator and "
                   f"{supply_a:g} A supply limits at a {bus_v:g} V bus, {moving_kg} kg equivalent moving mass; {abreast} FUEL abreast load the belt")
    return dict(name=name, kind="acquisition", passed=ok,
                metric=dict(name="capture time (s)", value=captured, requirement="over the back plate and inside the frame within 1.2 s of the start"),
                firstUnmet=None if ok else (f"not captured within {t_end:g} s" if captured is None else "capture slower than 1.2 s"),
                imposed=f"{driven_text}; robot approach {v_robot} m/s imposed",
                solved="FUEL translation and spin with penalty contact and Coulomb friction" + ("" if locked or imposed else "; belt speed under the contact load"),
                beltDemand=dict(maxNormalN=round(max_belt_force, 1), maxFrictionPowerW=round(belt_power, 1), energyJ=round(belt_j, 2),
                                minBeltMps=round(min_u, 3), peakSupplyA=round(peak_supply, 1), driven=not (locked or imposed), abreast=abreast,
                                note="Work and peak power the belt gives the FUEL, the lowest belt speed under that load and the peak battery-side "
                                     "current of its motor. With an imposed belt the speed is held and no current is computed"),
                params=dict(u=u, compBack=comp_back, compPulley=comp_pulley, muBelt=mu_belt, muBumper=mu_bumper, muCarpet=mu_carpet,
                            k=k, zeta=zeta, mass=mass, vRobot=v_robot, dt=dt, locked=locked, imposed=imposed, abreast=abreast, busV=bus_v,
                            gear=gear, supplyA=supply_a, statorA=stator_a, movingKg=moving_kg, rollerRatio=roller_ratio, muBack=mu_back, backPlate=back),
                geometry=dict(beltBackX=xk, pulley=[xp, zb, rp], topPulley=[xp, zt, rp], roller=[roller[0], roller[1], rr_],
                              bumper=[B["x0"] * MM, B["z0"] * MM, B["x1"] * MM, B["z1"] * MM],
                              backPlate=[[a[0], a[1], b[0], b[1]] for a, b in back_plate()] if back else []),
                beltSpeed=speed, contacts=contacts.result(), final=dict(t=t, x=x, z=z, vx=vx, vz=vz, w=w),
                events=events, frames=frames)


# ------------------------------------------------------------------ hopper lane (side view, robot frame)
STICK = True                                             # stick-slip friction in the lane trials


def lane_scene(squeeze=None, cleat=None, feeder_squeeze=None, feeder=True):
    """Static side-view surfaces of the floor lane behind the bumper, from dimensions.py (metres)."""
    K = D.frame_constants("R3", squeeze)
    B, RL = D.BUMPER, D.FRONT_RAIL
    bt = K["belt_top"] * MM
    pan = K["floor"] * MM
    cx, cz = K["c"][0] * MM, K["c"][1] * MM
    a0, a1 = (math.radians(v) for v in K["hood_span_deg"])
    wall = D.REAR_WALL_X
    wall_z = (K["z0"] + D.R_BALL + 7) * MM
    segs = [
        ((B["x0"] * MM, B["z1"] * MM), (B["x1"] * MM, B["z1"] * MM), "hard", "bumper front"),
        ((B["x0"] * MM, B["z0"] * MM), (B["x0"] * MM, B["z1"] * MM), "hard", "bumper front"),
        ((RL["x0"] * MM, RL["z1"] * MM), (RL["x1"] * MM, RL["z1"] * MM), "hard", "frame rail front"),
        ((RL["x1"] * MM, RL["z1"] * MM), (RL["x1"] * MM, B["z1"] * MM), "hard", "bumper front"),
        ((RL["x1"] * MM, B["z1"] * MM), (B["x0"] * MM, B["z1"] * MM), "hard", "bumper front"),
        *[(a, b, "hard", "chute back plate") for a, b in back_plate()],
        ((D.FLOOR_BELT_FRONT["x0"] * MM, bt), (D.FLOOR_BELT_FRONT["x1"] * MM, bt), "belt", "floor belt front"),
        ((D.FLOOR_BELT_MAIN["x0"] * MM, bt), (D.FLOOR_BELT_MAIN["x1"] * MM, bt), "belt", "floor belt main"),
        ((D.LANE_DECK["x0"] * MM, bt), (D.LANE_DECK["x1"] * MM, bt), "deck", "lane deck"),
        ((D.FLOOR_PAN["x0"] * MM, pan), (D.FLOOR_PAN["x1"] * MM, pan), "hard", "floor pan"),
        ((D.FLOOR_TONGUE["x0"] * MM, pan), (D.FLOOR_TONGUE["x1"] * MM, pan), "hard", "floor pan front tongue"),
        ((wall[0] * MM, wall_z), (wall[1] * MM, wall_z), "hard", "hopper rear wall"),
        ((wall[1] * MM, wall_z), (wall[1] * MM, wall_z + 0.3), "hard", "hopper rear wall"),
    ]
    if cleat:  # the superseded belt cleat, kept as a control
        x0, x1, z0, z1 = cleat
        segs += [((x1, z0), (x1, z1), "hard", "indexer cleat"), ((x0, z1), (x1, z1), "hard", "indexer cleat"),
                 ((x0, z0), (x0, z1), "hard", "indexer cleat")]
    F_ = D.FEEDER
    fsq = F_["squeeze"] if feeder_squeeze is None else feeder_squeeze
    roller = ((F_["x"] * MM, (K["belt_top"] + 2 * D.R_BALL - fsq + F_["r"]) * MM), F_["r"] * MM) if feeder else None
    return dict(segs=segs, wheel=((cx, cz), D.FLYWHEEL_R * MM), hood=((cx, cz), K["hood_in"] * MM, a0, a1), feeder=roller,
                feederSqueezeMm=fsq if feeder else None, beltTop=bt, K=K)


def scene_record(scene):
    """The lane surfaces for the player (metres)."""
    (cx, cz), rw = scene["wheel"]
    (_, _), rin, a0, a1 = scene["hood"]
    circles = [[cx, cz, rw, "flywheel"]]
    if scene["feeder"]:
        (fx, fz), rf = scene["feeder"]
        circles.append([fx, fz, rf, "feeder roller"])
    return dict(segs=[[a[0], a[1], b[0], b[1], label] for a, b, _, label in scene["segs"]], circles=circles, arcs=[[cx, cz, rin, a0, a1, "hood"]])


def lane(state, control, scene, drive=None, crr=0.03, mu_belt=0.9, mu_wheel=0.9, mu_hard=0.4, mu_hood=0.6, mu_feeder=0.9, k=15000.0,
         zeta=0.3, mass=0.215, dt=1e-4, t_end=4.0, every=50, settle=False, release=False, accel_x=0.0, push_n=0.0, t0=0.0, abreast=1, stick=STICK):
    """Integrate one free FUEL in the floor lane.

    control(t, x, wheel_mps) returns (belt, feeder, wheel): the floor belt and feeder roller surface speeds toward the
    flywheel, which are imposed, and the flywheel surface speed when it is imposed. With drive (a WheelDrive) the
    flywheel is a free body instead: its speed follows the FUEL's friction torque and its motors, and the third
    value is ignored. Rolling resistance is a couple crr * N * R opposing rolling on each surface (regularized at
    0.2 rad/s). accel_x is the robot's acceleration (m/s2, +X forward), felt by the FUEL as a body force; push_n is
    a steady force toward the flywheel from FUEL queued behind. t0 offsets the reported times.

    Friction in the lane is stick-slip: each contact carries a tangential spring (stiffness k, the contact's own
    damping) that holds up to mu * N and slides at mu * N beyond it, so a clamped FUEL stays where it is until the
    load exceeds its friction. stick=False falls back to the regularized Coulomb law of the other trials, under
    which a clamped FUEL creeps at any load."""
    (cx, cz), rw = scene["wheel"]
    (_, _), rin, a0, a1 = scene["hood"]
    c = 2 * zeta * math.sqrt(k * mass)
    inertia = 0.4 * mass * R * R
    mus = dict(hard=mu_hard, belt=mu_belt, deck=mu_hood)
    x, z, vx, vz, w = (state[q] for q in ("x", "z", "vx", "vz", "w"))
    t, step = 0.0, 0
    frames, events, first = [[round(t0, 4), round(x, 5), round(z, 5), round(w, 2)]], [], {}
    contacts = Contacts(0.001 if every <= 10 else 0.05)
    recent, outcome, released, springs = [], None, None, {}
    peak_wheel_power, wheel_energy = 0.0, 0.0
    uw = drive.mps if drive else 0.0
    wheel_trace = [[round(t0, 4), round(uw, 4)]]
    wheel_low, wheel_touch = None, None
    while t < t_end:
        vb, uf, imposed_w = control(t, x, uw)
        if not drive:
            uw = imposed_w
        fx, fz, tq = -mass * accel_x - push_n, -mass * G, 0.0
        touching = {}
        rows = []
        for a, b, kind, label in scene["segs"]:
            d, nx, nz, _, _ = seg_contact(x, z, a, b)
            if R - d > 0:
                rows.append((R - d, nx, nz, (-vb, 0.0) if kind == "belt" else (0.0, 0.0), mus[kind], label))
        d0 = math.hypot(x - cx, z - cz)
        if R - (d0 - rw) > 0:
            nx, nz = (x - cx) / d0, (z - cz) / d0
            rows.append((R - (d0 - rw), nx, nz, (uw * nz, -uw * nx), mu_wheel, "flywheel"))
        if scene["feeder"]:
            (qx, qz), rf = scene["feeder"]
            df = math.hypot(x - qx, z - qz)
            if R - (df - rf) > 0:
                nx, nz = (x - qx) / df, (z - qz) / df
                rows.append((R - (df - rf), nx, nz, (uf * nz, -uf * nx), mu_feeder, "feeder roller"))
        ang = math.atan2(z - cz, x - cx)
        if a0 <= ang <= a1:
            if d0 + R - rin > 0:
                rows.append((d0 + R - rin, -(x - cx) / d0, -(z - cz) / d0, (0.0, 0.0), mu_hood, "hood"))
        else:  # past either end the hood acts through its end edge
            e = a0 if ang < a0 else a1
            ex, ez = cx + rin * math.cos(e), cz + rin * math.sin(e)
            d = math.hypot(x - ex, z - ez)
            if 0 < d < R:
                rows.append((R - d, (x - ex) / d, (z - ez) / d, (0.0, 0.0), mu_hood, "hood"))
        wheel_now, wheel_load, live = 0.0, 0.0, {}
        for pen, nx, nz, (svx, svz), mu, label in rows:
            touching[label] = max(touching.get(label, 0.0), pen)
            if label not in first:
                first[label] = round(t0 + t, 4)
                events.append(dict(t=round(t0 + t, 4), event=f"first contact: {label}"))
            rx, rz = -nx * R, -nz * R
            rvx, rvz = vx - w * rz - svx, vz + w * rx - svz
            vn = rvx * nx + rvz * nz
            Fn = max(0.0, k * pen - c * vn)
            tx, tz = -nz, nx
            vt = rvx * tx + rvz * tz
            if stick:
                xi = springs.get(label, 0.0) + vt * dt
                Ft = -k * xi - c * vt
                if abs(Ft) > mu * Fn:                      # sliding: the spring keeps only what the friction limit holds
                    Ft = math.copysign(mu * Fn, Ft)
                    xi = -Ft / k
                live[label] = xi
            else:
                Ft = friction(Fn, vt, mu)
            Fx, Fz = Fn * nx + Ft * tx, Fn * nz + Ft * tz
            fx += Fx; fz += Fz
            tq += rx * Fz - rz * Fx
            roll = (nx * (vz - svz) - nz * (vx - svx)) / R
            tq -= crr * Fn * R * roll / math.sqrt(roll * roll + 0.2 ** 2)
            if label == "flywheel":
                wheel_now += -Ft * uw       # the wheel surface moves along -t: power it gives the FUEL
                wheel_load += Ft * rw       # and the torque the FUEL returns to the wheel
        springs = live
        peak_wheel_power = max(peak_wheel_power, wheel_now)
        wheel_energy += wheel_now * dt
        if "flywheel" in touching and uw > 0:
            wheel_touch = t0 + t if wheel_touch is None else wheel_touch
            wheel_low = uw if wheel_low is None else min(wheel_low, uw)
        if drive:
            drive.step(abreast * wheel_load, dt)   # abreast FUEL meet the wheel together, each on this path
            uw = drive.mps
        contacts.step(t0 + t, touching)
        vx += fx / mass * dt; vz += fz / mass * dt; w += tq / inertia * dt
        x += vx * dt; z += vz * dt; t += dt; step += 1
        if step % round(every * 1e-4 / dt) == 0:
            frames.append([round(t0 + t, 4), round(x, 5), round(z, 5), round(w, 2)])
        if step % round(20 * 1e-4 / dt) == 0:
            wheel_trace.append([round(t0 + t, 4), round(uw, 4)])
        if step % round(1e-3 / dt) == 0:
            recent.append((x, z))
            if len(recent) > 300:
                recent.pop(0)
        # Past the hood end and touching neither the wheel nor the end edge, the FUEL has left the shooter. The hood
        # is a surface without thickness in this model, so the run ends here.
        d0 = math.hypot(x - cx, z - cz)
        ang = math.atan2(z - cz, x - cx)
        ex, ez = cx + rin * math.cos(a0), cz + rin * math.sin(a0)
        if ang < a0 and x < cx and d0 - rw - R > 0 and math.hypot(x - ex, z - ez) > R:
            speed = math.hypot(vx, vz)
            if release:
                outcome = "released"
                released = dict(t=t0 + t, x=x, z=z, vx=vx, vz=vz, w=w, speedMps=speed, elevationDeg=math.degrees(math.atan2(vz, -vx)),
                                spinRatio=w * R / speed)
                events.append(dict(t=round(t0 + t, 4), event=f"FUEL clear of the flywheel and the hood end: released at {speed:.2f} m/s"))
            else:
                outcome = "through the shooter"
                events.append(dict(t=round(t0 + t, 4), event=f"FUEL rolls up the hood and out of its end at {speed:.2f} m/s"))
            break
        if settle and len(recent) == 300 and max(math.hypot(x - p, z - q) for p, q in recent) < 0.0005:
            outcome = "at rest"
            events.append(dict(t=round(t0 + t, 4), event="FUEL at rest (under 0.5 mm of travel in 0.3 s)"))
            break
        if z < 0 or x > 1.2 or x < -0.6:
            outcome = "lost"
            events.append(dict(t=round(t0 + t, 4), event="FUEL left the lane"))
            break
    if frames[-1][0] != round(t0 + t, 4):
        frames.append([round(t0 + t, 4), round(x, 5), round(z, 5), round(w, 2)])
    wheel_trace.append([round(t0 + t, 4), round(uw, 4)])
    return dict(outcome=outcome, final=dict(t=t, x=x, z=z, vx=vx, vz=vz, w=w), released=released, events=events, frames=frames,
                contacts=contacts.result(), first=first, peakWheelFrictionPowerW=round(peak_wheel_power, 1), wheelEnergyJ=wheel_energy,
                wheelTrace=wheel_trace, wheelLowMps=wheel_low, wheelTouchS=wheel_touch, wheelEndMps=uw)


SEAT_CLEAR_MM = 15.0                                     # a staged FUEL stands at least this far clear of the flywheel surface
STAGE_LAG_S = 0.005                                      # stage beam and controller latency before the feeder and belt stop


def wheel_gap_mm(scene, x, z):
    (cx, cz), rw = scene["wheel"]
    return (math.hypot(x - cx, z - cz) - rw - R) * 1000


def feeder_depth_mm(scene, x, z):
    (qx, qz), rf = scene["feeder"]
    return max(0.0, R - (math.hypot(x - qx, z - qz) - rf)) * 1000


def hopper_entry(name, start, belt=None, stage_mps=None, crr=0.03, mu_belt=0.9, mu_hard=0.4, mu_feeder=0.9, squeeze=None, cleat=None,
                 feeder_squeeze=None, feeder=True, wheel_mps=None, lag_s=STAGE_LAG_S, k=15000.0, zeta=0.3, mass=0.215, dt=1e-4, t_end=6.0,
                 every=50, start_note="the acquire-nominal capture state"):
    """Captured FUEL to its stage. It leaves the intake top roller with the capture state of the acquisition trial,
    crosses the bumper top and front lip, lands on the running floor belts and is carried aft to the feeder roller,
    which turns at its staging speed and draws the FUEL in. When the FUEL centre crosses the stage beam the feeder
    and the belt stop (after the sensing lag), and the FUEL is clamped between the stopped roller and the stopped
    belt. The flywheel spins at its setpoint throughout: the stage has to hold the FUEL clear of it."""
    F_ = D.FEEDER
    belt = D.FLOOR_BELT_MPS if belt is None else belt
    stage_mps = F_["stage_mps"] if stage_mps is None else stage_mps
    wheel_mps = D.SHOOTER["wheel_surface_mps"] if wheel_mps is None else wheel_mps
    scene = lane_scene(squeeze, cleat, feeder_squeeze, feeder)
    seen = []

    def control(t, x, uw):
        if not seen and x * 1000 <= F_["sensor_x"]:
            seen.append(t)
        staged = bool(seen) and t >= seen[0] + lag_s
        return (0.0 if staged else belt, 0.0 if staged else stage_mps, wheel_mps)

    run = lane(start, control, scene, crr=crr, mu_belt=mu_belt, mu_hard=mu_hard, mu_feeder=mu_feeder, k=k, zeta=zeta, mass=mass,
               dt=dt, t_end=t_end, every=every, settle=True)
    f = run["final"]
    on_belt = abs(f["z"] - (scene["beltTop"] + R)) < 0.002 + (scene["feederSqueezeMm"] or 0.0) * MM   # on the deck, pressed no deeper than the squeeze
    gap = wheel_gap_mm(scene, f["x"], f["z"])
    clamp = feeder_depth_mm(scene, f["x"], f["z"]) if feeder else 0.0
    events = sorted(run["events"] + ([dict(t=round(seen[0], 4), event="FUEL centre crosses the stage beam"),
                                       dict(t=round(seen[0] + lag_s, 4), event="feeder and floor belt stopped")] if seen else []), key=lambda e: e["t"])
    unmet = None
    if run["outcome"] == "through the shooter":
        unmet = "not held: the FUEL reaches the spinning flywheel and leaves the shooter before any feed is commanded"
    elif "flywheel" in run["contacts"]:
        unmet = "not held clear: the FUEL touches the spinning flywheel while staging"
    elif run["outcome"] != "at rest":
        unmet = "not at rest within %.1f s" % t_end if run["outcome"] is None else "FUEL left the lane"
    elif not seen:
        unmet = "at rest short of the stage beam: the feeder never drew it in"
    elif gap < SEAT_CLEAR_MM:
        unmet = f"staged {gap:.1f} mm from the spinning flywheel, inside the {SEAT_CLEAR_MM:.0f} mm reserve"
    elif not on_belt:
        unmet = "at rest off the lane deck"
    elif clamp < 1.0:
        unmet = f"staged with {clamp:.1f} mm of feeder squeeze: not clamped"
    elif f["t"] > 5.0:
        unmet = "at rest later than 5.0 s after capture"
    ok = unmet is None
    return dict(name=name, kind="entry", passed=ok,
                metric=dict(name="stage time after capture (s)", value=round(f["t"], 4) if run["outcome"] == "at rest" else None,
                            requirement=f"at rest on the lane deck within 5.0 s, past the stage beam, clamped at least 1 mm by the feeder roller and "
                                        f"at least {SEAT_CLEAR_MM:.0f} mm clear of the spinning flywheel, which it never touches"),
                firstUnmet=unmet,
                imposed=(f"start from {start_note}; floor belt surface {belt} m/s toward the flywheel and feeder roller surface {stage_mps} m/s until the "
                         f"FUEL centre crosses the stage beam at x = {F_['sensor_x']} mm, both stopped {1000 * lag_s:.0f} ms later; flywheel surface held at {wheel_mps} m/s"
                         if feeder else f"start from {start_note}; floor belt surface {belt} m/s; no feeder roller; flywheel surface held at {wheel_mps} m/s"),
                solved="FUEL translation and spin with penalty contact, Coulomb friction, gravity and rolling resistance",
                seat=dict(xM=round(f["x"], 5), zM=round(f["z"], 5), clearOfFlywheelMm=round(gap, 2), feederSqueezeMm=round(clamp, 2),
                          beamCrossedS=round(seen[0], 4) if seen else None),
                params=dict(belt=belt, stageMps=stage_mps, crr=crr, muBelt=mu_belt, muHard=mu_hard, muFeeder=mu_feeder, squeezeMm=scene["K"]["squeeze"],
                            feederSqueezeMm=scene["feederSqueezeMm"], wheelMps=wheel_mps, lagS=lag_s, k=k, zeta=zeta, mass=mass, dt=dt,
                            start={q: round(start[q], 5) for q in ("x", "z", "vx", "vz", "w")}, cleat=list(cleat) if cleat else None),
                scene=scene_record(scene), contacts=run["contacts"], final=f, events=events, frames=run["frames"])


def hold(name, start, belt=None, accel_g=0.0, push_n=0.0, seconds=2.0, feeder_squeeze=None, mu_feeder=0.9, mu_belt=0.9, mu_deck=0.6, k=15000.0,
         zeta=0.3, mass=0.215, dt=1e-4, stick=True, feeder=True, start_note="the entry-nominal stage"):
    """Staged FUEL under load, with the feeder roller stopped and the flywheel at speed: the floor belt left
    running, the robot accelerating, or queued FUEL pressing from behind. The hold-back passes when the FUEL
    stays clear of the flywheel for the whole run.

    stick=False is the control for the friction law: with regularized Coulomb friction, which has no stiction, the
    same clamped FUEL creeps through under a load its friction would hold."""
    belt = 0.0 if belt is None else belt
    wheel_mps = D.SHOOTER["wheel_surface_mps"]
    scene = lane_scene(feeder_squeeze=feeder_squeeze, feeder=feeder)
    run = lane(start, lambda t, x, uw: (belt, 0.0, wheel_mps), scene, mu_feeder=mu_feeder, mu_belt=mu_belt, mu_hood=mu_deck, k=k, zeta=zeta, mass=mass,
               dt=dt, t_end=seconds, accel_x=accel_g * G, push_n=push_n, stick=stick, every=round(0.005 / dt), release=True)
    gaps = [wheel_gap_mm(scene, f[1], f[2]) for f in run["frames"]]
    travel = (start["x"] - min(f[1] for f in run["frames"])) * 1000
    unmet = None
    if "flywheel" in run["contacts"] or run["outcome"] == "through the shooter":
        unmet = "the FUEL reaches the spinning flywheel with no feed commanded"
    elif min(gaps) < SEAT_CLEAR_MM - 5.0:
        unmet = f"the FUEL creeps to {min(gaps):.1f} mm from the flywheel"
    ok = unmet is None
    return dict(name=name, kind="hold", passed=ok,
                metric=dict(name="least clearance to the spinning flywheel (mm)", value=round(min(gaps), 2),
                            requirement=f"stays at least {SEAT_CLEAR_MM - 5.0:.0f} mm clear of the flywheel for {seconds:g} s with the feeder stopped"),
                firstUnmet=unmet,
                imposed=(f"start from {start_note}; feeder roller stopped and braked; floor belt surface {belt} m/s toward the flywheel; robot "
                         f"acceleration {accel_g:g} g forward; {push_n:g} N from queued FUEL behind; flywheel surface held at {wheel_mps} m/s"),
                solved="FUEL translation and spin with penalty contact, Coulomb friction, gravity and rolling resistance",
                creepMm=round(travel, 2),
                params=dict(belt=belt, accelG=accel_g, pushN=push_n, feederSqueezeMm=scene["feederSqueezeMm"], muFeeder=mu_feeder, muBelt=mu_belt, muDeck=mu_deck, k=k,
                            zeta=zeta, mass=mass, dt=dt, stick=stick, feeder=feeder, start={q: round(start[q], 5) for q in ("x", "z", "vx", "vz", "w")}),
                scene=scene_record(scene), contacts=run["contacts"], final=run["final"], events=run["events"], frames=run["frames"])


def launch(name, start, feed_mps=None, feeder_mps=None, feed_at=0.1, squeeze=None, feeder_squeeze=None, crr=0.03, mu_wheel=0.9, mu_belt=0.9,
           mu_hood=0.6, mu_feeder=0.9, k=15000.0, zeta=0.3, mass=0.215, dt=1e-4, t_end=3.0, every=50, band=None, imposed_wheel=False,
           drive=None, start_note="the entry-nominal stage", t0=0.0, abreast=1, **drive_kw):
    """Staged FUEL to release. The flywheel is at its setpoint, a free body under its motors and speed loop. Once
    the measured wheel speed is inside the ready band the feeder roller and floor belt advance the FUEL; the wheel
    takes it, slows under its load, rolls it up the hood and releases it. imposed_wheel=True holds the wheel
    speed instead. drive continues an earlier shot's wheel."""
    S, F_ = D.SHOOTER, D.FEEDER
    feed_mps = D.FLOOR_BELT_MPS if feed_mps is None else feed_mps
    feeder_mps = F_["mps"] if feeder_mps is None else feeder_mps
    scene = lane_scene(squeeze, feeder_squeeze=feeder_squeeze)
    drive = (drive or WheelDrive(**drive_kw)) if not imposed_wheel else None
    setpoint = drive.set if drive else drive_kw.get("setpoint_mps", S["wheel_surface_mps"])
    fed = []

    def control(t, x, uw):
        if not fed and t >= feed_at and (drive is None or abs(uw - setpoint) <= S["ready_band"] * setpoint):
            fed.append(t)
        return ((feed_mps, feeder_mps, setpoint) if fed else (0.0, 0.0, setpoint))

    before = drive.motor_j if drive else 0.0
    run = lane(start, control, scene, drive=drive, crr=crr, mu_belt=mu_belt, mu_wheel=mu_wheel, mu_hood=mu_hood, mu_feeder=mu_feeder, k=k,
               zeta=zeta, mass=mass, dt=dt, t_end=t_end, every=every, release=True, t0=t0, abreast=abreast)
    rel = run["released"]
    events = sorted(run["events"] + ([dict(t=round(t0 + fed[0], 4), event=f"wheel ready at {setpoint} m/s: feeder {feeder_mps} m/s and belt {feed_mps} m/s advance the FUEL")]
                                     if fed else []), key=lambda e: e["t"])
    unmet = None
    if rel is None:
        unmet = "not released within %.1f s" % t_end if fed else "never fed: the wheel did not reach its ready band"
    elif run["wheelTouchS"] is not None and (not fed or run["wheelTouchS"] < t0 + fed[0]):
        unmet = "the flywheel takes the FUEL before the feed is commanded"
    elif band and not (band[0] <= rel["speedMps"] <= band[1]):
        unmet = f"release {rel['speedMps']:.2f} m/s is outside the delivery trials' scoring band {band[0]:.2f}-{band[1]:.2f} m/s"
    ok = unmet is None
    low = run["wheelLowMps"]
    return dict(name=name, kind="launch", passed=ok,
                metric=dict(name="release speed (m/s)", value=None if rel is None else round(rel["speedMps"], 3),
                            requirement="fed only with the wheel in its ready band and released inside the delivery trials' scoring band"
                                        + (f" ({band[0]:.2f}-{band[1]:.2f} m/s)" if band else "")),
                firstUnmet=unmet,
                imposed=(f"start from {start_note}; feeder roller and floor belt stopped until the wheel is within {100 * S['ready_band']:g}% of its setpoint "
                         f"and {feed_at} s have passed, then feeder {feeder_mps} m/s and belt {feed_mps} m/s; "
                         + (f"flywheel surface held at {setpoint} m/s" if drive is None else
                            f"flywheel a free {drive.inertia} kg m2 body from {setpoint} m/s with {drive.motors} motors at {drive.gear:g}:1, {drive.stator_a:g} A stator "
                            f"and {drive.supply_a:g} A supply limit each, {drive.bus_v:g} V bus" + ("" if drive.powered else ", motors off"))),
                solved="FUEL translation and spin with penalty contact, Coulomb friction, gravity and rolling resistance"
                       + ("" if drive is None else "; flywheel speed under the FUEL's friction torque and the motor torque"),
                release=None if rel is None else {q: round(v, 5) for q, v in rel.items()},
                wheelDemand=dict(peakFrictionPowerW=run["peakWheelFrictionPowerW"], energyJ=round(run["wheelEnergyJ"], 2),
                                 lowestMps=None if low is None else round(low, 3),
                                 speedDropPercent=None if low is None else round(100 * (1 - low / setpoint), 2),
                                 atReleaseMps=round(run["wheelEndMps"], 3), motorJ=None if drive is None else round(drive.motor_j - before, 2),
                                 peakSupplyA=None if drive is None else round(drive.peak_supply_a, 1), drive=None if drive is None else drive.record(),
                                 note="Work done by the wheel surface on the FUEL, the lowest wheel speed while it touches the FUEL and its fall below "
                                      "the setpoint, the wheel speed at release, the work the motors returned during the shot and their peak "
                                      "battery-side current"),
                schedule=dict(feedStartS=round(t0 + fed[0], 4) if fed else None, flywheelTakesS=None if run["wheelTouchS"] is None else round(run["wheelTouchS"], 4)),
                params=dict(feedMps=feed_mps, feederMps=feeder_mps, feedAtS=feed_at, squeezeMm=scene["K"]["squeeze"], feederSqueezeMm=scene["feederSqueezeMm"],
                            crr=crr, muWheel=mu_wheel, muBelt=mu_belt, muHood=mu_hood, muFeeder=mu_feeder, k=k, zeta=zeta, mass=mass, dt=dt,
                            wheelMps=setpoint, imposedWheel=imposed_wheel, start={q: round(start[q], 5) for q in ("x", "z", "vx", "vz", "w")}),
                scene=scene_record(scene), contacts=run["contacts"], final=run["final"], released=rel, events=events, frames=run["frames"],
                wheelTrace=run["wheelTrace"])


def batch(name, start, shots=24, period=None, band=None, masses=None, every=50, t_limit=20.0, **kw):
    """A batch through the one flywheel: shots FUEL, each from the stage, fed no sooner than period apart and only
    with the wheel in its ready band. The wheel is one free body through the whole batch, so each shot starts from
    what the last one left. masses cycles the FUEL mass through the legal range. Reports every release."""
    period = D.FEEDER["period_s"] if period is None else period
    drive_keys = ("setpoint_mps", "inertia", "motors", "gear", "stator_a", "supply_a", "bus_v", "band", "efficiency", "drag_nm", "powered")
    drive = WheelDrive(**{q: kw.pop(q) for q in drive_keys if q in kw})
    masses = masses or [0.215]
    t, rows, traces, frames, feeds = 0.0, [], [], [], []
    for i in range(shots):
        one = launch(f"{name}-{i + 1}", start, feed_at=max(0.0, (feeds[-1] + period - t) if feeds else 0.1), drive=drive, band=band,
                     mass=masses[i % len(masses)], every=every, t0=t, **kw)
        if one["schedule"]["feedStartS"] is None or one["release"] is None:
            rows.append(dict(shot=i + 1, passed=False, firstUnmet=one["firstUnmet"]))
            break
        feeds.append(one["schedule"]["feedStartS"])
        rel = one["release"]
        rows.append(dict(shot=i + 1, massKg=masses[i % len(masses)], feedS=one["schedule"]["feedStartS"], releaseS=round(rel["t"], 4),
                         speedMps=round(rel["speedMps"], 3), elevationDeg=round(rel["elevationDeg"], 2), wheelLowMps=one["wheelDemand"]["lowestMps"],
                         wheelAtFeedMps=round(next(u for tt, u in one["wheelTrace"] if tt >= one["schedule"]["feedStartS"] - 1e-9), 3),
                         passed=one["passed"], firstUnmet=one["firstUnmet"]))
        traces += one["wheelTrace"]
        frames.append(one["frames"])
        t = rel["t"]
        if t > t_limit:
            break
    good = [r for r in rows if r.get("speedMps") is not None]
    done = len(good) == shots and all(r["passed"] for r in rows)
    span = good[-1]["releaseS"] - good[0]["feedS"] if good else None
    rate = (len(good) / (good[-1]["releaseS"])) if good else 0.0
    speeds = [r["speedMps"] for r in good]
    unmet = None
    if not done:
        bad = next(r for r in rows if not r["passed"])
        unmet = f"shot {bad['shot']}: {bad['firstUnmet']}"
    elif good[-1]["releaseS"] > 12.0 * shots / 24:
        unmet = f"{shots} FUEL take {good[-1]['releaseS']:.2f} s, slower than 2.00 FUEL/s"
    ok = unmet is None
    return dict(name=name, kind="batch", passed=ok,
                metric=dict(name="FUEL released per second", value=round(rate, 3),
                            requirement=f"all {shots} released inside the scoring band" + (f" ({band[0]:.2f}-{band[1]:.2f} m/s)" if band else "")
                                        + ", each fed with the wheel in its ready band, at 2.00 FUEL/s or faster from the first feed command"),
                firstUnmet=unmet,
                imposed=(f"each FUEL starts from {kw.get('start_note', 'the entry-nominal stage')}; feeds at least {period} s apart; feeder and belt speeds imposed; "
                         f"flywheel one free {drive.inertia} kg m2 body with {drive.motors} motors at {drive.gear:g}:1, {drive.stator_a:g} A stator limit each, "
                         f"{drive.bus_v:g} V bus" + ("" if drive.powered else ", motors off") + f"; FUEL mass cycles through {masses} kg"),
                solved="every FUEL's translation and spin, and the flywheel speed through the whole batch",
                batch=dict(shots=rows, releaseSpeedMps=[min(speeds), max(speeds)] if speeds else None, lastReleaseS=good[-1]["releaseS"] if good else None,
                           spanS=None if span is None else round(span, 3), peakSupplyA=round(drive.peak_supply_a, 1), motorJ=round(drive.motor_j, 1),
                           drive=drive.record()),
                params=dict(shots=shots, periodS=period, masses=masses, **{q: v for q, v in kw.items() if isinstance(v, (int, float))}),
                wheelTrace=traces[::5], frames=frames[0] if frames else [], scene=scene_record(lane_scene(kw.get("squeeze"), feeder_squeeze=kw.get("feeder_squeeze"))),
                contacts={}, events=[dict(t=r["releaseS"], event=f"shot {r['shot']} released at {r['speedMps']} m/s; wheel fell to {r['wheelLowMps']} m/s")
                                     for r in good])


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
    for z0, z1, region, label in ((0.0, 1.777, "ring", "hub body"), (1.779, 1.8288, "ring", "hub top"), (0.990, 1.000, "floor", "hub body")):
        if region == "ring":
            qx, qy = ring_closest_xy(p[0], p[1])
        else:
            qx, qy = (p[0], p[1]) if in_hex(p[0], p[1]) else hex_closest(p[0], p[1])
        qz = min(max(p[2], z0), z1)
        d = math.dist(p, (qx, qy, qz))
        if d < R and d > 0:
            out.append(((p[0] - qx) / d, (p[1] - qy) / d, (p[2] - qz) / d, R - d, label))
    return out


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def delivery(name, release, speed=None, cd=0.47, cl=0.15, k=15000.0, zeta=0.3, mu=0.6, mass=0.215, dt=1e-4, t_end=1.6, every=40,
             release_note="the launch-nominal release state"):
    """Released FUEL to the HUB sensor plane. The start is the release state of a launch trial: position, velocity
    and spin. speed rescales that velocity and spin together, holding the release point and direction."""
    v0 = math.hypot(release["vx"], release["vz"])
    scale = 1.0 if speed is None else speed / v0
    p = [release["x"], D.TRACK_Y * MM, release["z"]]
    vel = [release["vx"] * scale, 0.0, release["vz"] * scale]
    omega = [0.0, -release["w"] * scale, 0.0]  # the side view's positive spin is about -Y: Magnus toward the lower side of the path
    v = v0 * scale
    area = math.pi * R * R
    kd = 0.5 * RHO * cd * area
    kl = 0.5 * RHO * cl * area
    inertia = 0.4 * mass * R * R
    c = 2 * zeta * math.sqrt(k * mass)
    t, events, scored, touched = 0.0, [], None, False
    frames = [[0.0, round(p[0], 5), round(p[1], 5), round(p[2], 5)]]
    step = 0
    sensor = 1.50
    contacts = Contacts(0.001 if every <= 10 else 0.05)
    while t < t_end:
        sp = math.sqrt(sum(q * q for q in vel)) or 1e-9
        F = [-kd * sp * vel[0], -kd * sp * vel[1], -kd * sp * vel[2] - mass * G]
        wn = math.sqrt(sum(q * q for q in omega)) or 1e-9
        mg = cross([q / wn for q in omega], vel)
        F = [F[i] + kl * sp * mg[i] for i in range(3)]
        Tq = [0.0, 0.0, 0.0]
        touching = {}
        for nx, ny, nz, pen, label in hub_contacts(p):
            touching[label] = max(touching.get(label, 0.0), pen)
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
                events.append(dict(t=round(t, 4), event=f"first HUB contact: {label}", at=[round(q, 3) for q in p]))
        contacts.step(t, touching)
        vel = [vel[i] + F[i] / mass * dt for i in range(3)]
        omega = [omega[i] + Tq[i] / inertia * dt for i in range(3)]
        prev = p[2]
        p = [p[i] + vel[i] * dt for i in range(3)]
        t += dt; step += 1
        if step % round(every * 1e-4 / dt) == 0:
            frames.append([round(t, 4), round(p[0], 5), round(p[1], 5), round(p[2], 5)])
        if prev >= sensor > p[2] and in_hex(p[0], p[1]) and scored is None:
            scored = round(t, 4)
            events.append(dict(t=scored, event="FUEL crosses the HUB sensor plane inside the opening: scored"))
            break
        if p[2] < 0.2 and not in_hex(p[0], p[1]):
            events.append(dict(t=round(t, 4), event="FUEL on the carpet outside the HUB: missed"))
            break
    if frames[-1][0] != round(t, 4):
        frames.append([round(t, 4), round(p[0], 5), round(p[1], 5), round(p[2], 5)])
    ok = scored is not None
    elev = math.degrees(math.atan2(release["vz"], -release["vx"]))
    return dict(name=name, kind="delivery", passed=ok,
                metric=dict(name="scored at sensor (s)", value=scored, requirement="cross the sensor plane inside the opening"),
                firstUnmet=None if ok else "did not reach the sensor plane inside the opening",
                imposed=f"start from {release_note}: {v:.3f} m/s at {elev:.2f} deg, spin ratio {release['w'] * R / v0:.3f}"
                        + ("" if speed is None else " (speed and spin rescaled together; point and direction held)"),
                solved="free FUEL translation and spin under drag, spin lift and penalty contact with the HUB",
                params=dict(v=round(v, 4), cd=cd, cl=cl, k=k, zeta=zeta, mu=mu, mass=mass, dt=dt, elevationDeg=round(elev, 3), sensorZ=sensor,
                            release=[round(q, 5) for q in (release["x"], D.TRACK_Y * MM, release["z"])]),
                hub=dict(center=HUB, half=HALF, hex=HEX), contacts=contacts.result(), events=events, frames=frames)


# ------------------------------------------------------------------ elevation (side view, berth)
def elevation(name, mass=D.HANG_MASS_KG, cg=(-0.01, 0.28), bus_v=10.0, brake=True, mu_up=0.4, dt=1e-4, t_end=8.0,
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
        if step % round(100 * 1e-4 / dt) == 0:
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
                limits="Side view: both hooks and both uprights act in one plane. The 23.9 mm lateral bumper-to-upright overlap and any roll are not represented (gate G3).",
                cable=dict(liftPeakN=max((f[5] for f in frames if t_hold is None or f[0] <= t_hold), default=None),
                           holdN=None if t_hold is None else [min(f[5] for f in frames if f[0] > t_hold + 0.2), max(f[5] for f in frames if f[0] > t_hold + 0.2)],
                           note="Cable load summed over both hooks: the peak while the winch lifts, and the range once the brake holds"),
                params=dict(mass=mass, cg=cg, busV=bus_v, brake=brake, muUpright=mu_up, dt=dt, stroke=stroke, currentLimitA=i_limit,
                            stallForceN=f_stall12, freeSpeedMps=v_free12, wheelK=kw, hookK=kh),
                rung=rung, uprightX=upright_x, events=events, frames=frames)


def state(final):
    return {q: final[q] for q in ("x", "z", "vx", "vz", "w")}


def at_rest(final, dx=0.0):
    s = state(final)
    s.update(x=s["x"] + dx, vx=0.0, vz=0.0, w=0.0)
    return s


CORNERS = [(0.35, 0.0), (0.35, 0.30), (0.60, 0.0), (0.60, 0.30)]  # the drag and spin-lift corners of ballistics.py
SPEEDS = [6.40, 6.55, 6.70, 6.90, 7.10, 7.25, 7.40]         # delivery trials recorded with their traces
SCAN = [round(6.50 + 0.025 * i, 3) for i in range(33)]    # the scoring scan: 6.500 to 7.300 m/s in 0.025 m/s steps
BARE_WHEEL = 0.0026                                      # the roller without its inertia ring, kept as a control
WEAK_V = 8.34                                            # weak-pack bus under the launch duty (budgets.json)


def run_trials():
    fine = dict(every=10)  # 1 ms frames and contact rows for the four traces the layout's FUEL cases are fitted to
    acq = acquisition("acquire-nominal", **fine)
    capture = state(acq["final"])
    slow = acquisition("acquire-belt-2.5mps", u=2.5)
    # The entry runs at half the others' timestep, as in the earlier issue.
    entry = hopper_entry("entry-nominal", capture, dt=5e-5, **fine)
    seat = at_rest(entry["final"])  # the FUEL waits clamped at the stage through the loaded transit
    rel = launch("launch-nominal", seat)["released"]
    assert acq["passed"] and entry["passed"] and rel, "the nominal chain must reach a release"
    # A release speed scores only if it scores at the nominal drag and spin lift and at all four corners.
    scan = {v: delivery(f"deliver-{v:.2f}", rel, speed=v) for v in SPEEDS}
    rows = []
    for v in SCAN:
        nominal = delivery("scan", rel, speed=v)["passed"]
        corners = {f"cd{cd}-cl{cl}": delivery("corner", rel, speed=v, cd=cd, cl=cl)["passed"] for cd, cl in CORNERS}
        rows.append(dict(speedMps=v, nominal=nominal, corners=corners, scores=nominal and all(corners.values())))
    near = min(range(len(rows)), key=lambda i: abs(rows[i]["speedMps"] - rel["speedMps"]))
    assert rows[near]["scores"], "the nominal release speed does not score at every drag and spin corner"
    lo = hi = near
    while lo > 0 and rows[lo - 1]["scores"]:
        lo -= 1
    while hi < len(rows) - 1 and rows[hi + 1]["scores"]:
        hi += 1
    band = [rows[lo]["speedMps"], rows[hi]["speedMps"]]
    lch = launch("launch-nominal", seat, band=band, **fine)
    rel = lch["released"]
    legal = [0.203, 0.215, 0.227]
    set_mps = D.SHOOTER["wheel_surface_mps"]
    trials = [
        acq,
        acquisition("acquire-belt-locked (cause isolation)", locked=True),
        acquisition("acquire-belt-speed-imposed (earlier issue's drive)", imposed=True),
        acquisition("acquire-low-friction-light-compression (adverse)", mu_belt=0.5, comp_back=0.010, comp_pulley=0.010),
        acquisition("acquire-roller-at-belt-speed", roller_ratio=1.0),
        acquisition("acquire-back-plate-friction-0.2", mu_back=0.2),
        acquisition("acquire-back-plate-friction-0.1", mu_back=0.1),
        acquisition("acquire-nominal-half-step", dt=5e-5),
        acquisition("acquire-three-abreast", abreast=3),
        acquisition("acquire-three-abreast-9V-bus (adverse)", abreast=3, bus_v=9.0),
        acquisition("acquire-three-abreast-7V-bus", abreast=3, bus_v=7.0),
        acquisition("acquire-three-abreast-9V-supply-limit-20A", abreast=3, bus_v=9.0, supply_a=20.0),
        acquisition("acquire-three-abreast-9V-supply-limit-10A", abreast=3, bus_v=9.0, supply_a=10.0),
        acquisition("acquire-belt-friction-0.7", mu_belt=0.7),
        acquisition("acquire-belt-friction-0.5", mu_belt=0.5),
        acquisition("acquire-bumper-friction-0.3", mu_bumper=0.3),
        acquisition("acquire-bumper-friction-0.2", mu_bumper=0.2),
        acquisition("acquire-compression-15mm", comp_back=0.015, comp_pulley=0.015),
        acquisition("acquire-compression-10mm", comp_back=0.010, comp_pulley=0.010),
        acquisition("acquire-compression-17.5mm", comp_back=0.0175, comp_pulley=0.0175),
        acquisition("acquire-compression-25mm", comp_back=0.025, comp_pulley=0.025),
        slow,
        acquisition("acquire-belt-2.0mps", u=2.0),
        acquisition("acquire-belt-1.5mps", u=1.5),
        acquisition("acquire-approach-1.0mps", v_robot=1.0),
        entry,
        hopper_entry("entry-nominal-half-step", capture, dt=2.5e-5),
        hopper_entry("entry-nominal-double-step", capture, dt=1e-4),
        hopper_entry("entry-no-feeder (control)", capture, feeder=False),
        hopper_entry("entry-feeder-not-turning (cause isolation)", capture, stage_mps=0.0),
        hopper_entry("entry-floor-belt-stopped", capture, belt=0.0),
        hopper_entry("entry-floor-belt-0.6mps", capture, belt=0.6),
        hopper_entry("entry-stage-lag-20ms", capture, lag_s=0.020),
        hopper_entry("entry-stage-lag-80ms", capture, lag_s=0.080),
        hopper_entry("entry-stage-lag-150ms", capture, lag_s=0.150),
        hopper_entry("entry-from-2.5mps-intake-belt", state(slow["final"]), start_note="the acquire-belt-2.5mps capture state"),
        hopper_entry("entry-rolling-resistance-0.01", capture, crr=0.01),
        hopper_entry("entry-rolling-resistance-0.20", capture, crr=0.20),
        hopper_entry("entry-belt-friction-0.5", capture, mu_belt=0.5),
        hopper_entry("entry-feeder-friction-0.5", capture, mu_feeder=0.5),
        hopper_entry("entry-feeder-squeeze-8mm", capture, feeder_squeeze=8.0),
        hopper_entry("entry-feeder-squeeze-4mm", capture, feeder_squeeze=4.0),
        hopper_entry("entry-feeder-squeeze-1mm", capture, feeder_squeeze=1.0),
        hopper_entry("entry-contact-damping-0.20", capture, zeta=0.20),
        hopper_entry("entry-contact-damping-0.10", capture, zeta=0.10),
        hold("hold-nominal", seat, belt=D.FLOOR_BELT_MPS, accel_g=1.5, push_n=30.0),
        hold("hold-nominal-half-step", seat, belt=D.FLOOR_BELT_MPS, accel_g=1.5, push_n=30.0, dt=5e-5),
        hold("hold-no-feeder (control)", seat, belt=D.FLOOR_BELT_MPS, accel_g=1.5, push_n=30.0, feeder=False),
        hold("hold-regularized-friction-law (control for the law)", seat, belt=D.FLOOR_BELT_MPS, accel_g=1.5, push_n=30.0, stick=False),
        hold("hold-braking-1.5g", seat, belt=D.FLOOR_BELT_MPS, accel_g=-1.5),
        hold("hold-queue-push-90N", seat, belt=D.FLOOR_BELT_MPS, accel_g=1.5, push_n=90.0),
        hold("hold-queue-push-120N", seat, belt=D.FLOOR_BELT_MPS, accel_g=1.5, push_n=120.0),
        hold("hold-queue-push-150N", seat, belt=D.FLOOR_BELT_MPS, accel_g=1.5, push_n=150.0),
        hold("hold-feeder-friction-0.5-deck-0.3", seat, belt=D.FLOOR_BELT_MPS, accel_g=1.5, push_n=30.0, mu_feeder=0.5, mu_deck=0.3),
        hold("hold-feeder-friction-0.2-deck-0.2", seat, belt=D.FLOOR_BELT_MPS, accel_g=1.5, push_n=30.0, mu_feeder=0.2, mu_deck=0.2),
        lch,
        launch("launch-nominal-half-step", seat, band=band, dt=5e-5),
        launch("launch-feeder-stopped (cause isolation)", seat, band=band, feeder_mps=0.0, t_end=2.0),
        launch("launch-wheel-speed-imposed (earlier issue's drive)", seat, band=band, imposed_wheel=True),
        launch("launch-motors-off", seat, band=band, powered=False),
        launch("launch-bare-roller-motors-off (control)", seat, band=band, inertia=BARE_WHEEL, powered=False),
        launch("launch-bare-roller-0.0026-wheel", seat, band=band, inertia=BARE_WHEEL),
        launch("launch-layout-001-0.006-wheel", seat, band=band, inertia=0.006),
        launch("launch-weak-pack-8.34V", seat, band=band, bus_v=WEAK_V),
        launch("launch-two-abreast", seat, band=band, abreast=2),
        launch("launch-two-abreast-weak-pack-heavy-FUEL (adverse)", seat, band=band, abreast=2, bus_v=WEAK_V, mass=legal[2]),
        launch("launch-three-abreast", seat, band=band, abreast=3),
        launch("launch-fuel-0.203kg", seat, band=band, mass=legal[0]),
        launch("launch-fuel-0.227kg", seat, band=band, mass=legal[2]),
        launch("launch-stator-limit-20A", seat, band=band, stator_a=20.0),
        launch("launch-squeeze-6mm", seat, band=band, squeeze=6.0),
        launch("launch-squeeze-8mm", seat, band=band, squeeze=8.0),
        launch("launch-squeeze-16mm", seat, band=band, squeeze=16.0),
        launch("launch-squeeze-20mm", seat, band=band, squeeze=20.0),
        launch("launch-wheel-friction-0.5", seat, band=band, mu_wheel=0.5),
        launch("launch-wheel-friction-0.3", seat, band=band, mu_wheel=0.3),
        launch("launch-contact-stiffness-7.5k", seat, band=band, k=7500.0),
        launch("launch-contact-stiffness-10k", seat, band=band, k=10000.0),
        launch("launch-contact-stiffness-30k", seat, band=band, k=30000.0),
        *[launch(f"launch-setpoint-{set_mps + d:.1f}mps", seat, band=band, setpoint_mps=set_mps + d) for d in (-0.5, -0.3, 0.3, 0.5)],
        batch("batch-nominal", seat, band=band, masses=legal),
        batch("batch-nominal-half-step", seat, band=band, masses=legal, dt=5e-5),
        batch("batch-weak-pack-8.34V", seat, band=band, masses=legal, bus_v=WEAK_V),
        batch("batch-motors-off (cause isolation)", seat, band=band, masses=legal, powered=False),
        batch("batch-bare-roller-0.0026-wheel-weak-pack", seat, band=band, masses=legal, inertia=BARE_WHEEL, bus_v=WEAK_V),
        batch("batch-bare-roller-weak-pack-stator-limit-20A", seat, band=band, masses=legal, inertia=BARE_WHEEL, bus_v=WEAK_V, stator_a=20.0),
        batch("batch-stator-limit-20A-weak-pack", seat, band=band, masses=legal, stator_a=20.0, bus_v=WEAK_V),
        batch("batch-stator-limit-5A-weak-pack", seat, band=band, masses=legal, stator_a=5.0, bus_v=WEAK_V),
        batch("batch-required-rate-0.5s-period", seat, band=band, masses=legal, period=0.5),
        delivery("deliver-nominal", rel, **fine),
        delivery("deliver-nominal-half-step", rel, dt=5e-5),
        *[delivery(f"deliver-corner-cd{cd}-cl{cl}", rel, cd=cd, cl=cl) for cd, cl in CORNERS],
        delivery("deliver-stiff-contact-30k (sensitivity)", rel, k=30000.0),
        *[scan[v] for v in SPEEDS],
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
    import hopper_flow
    trials += hopper_flow.run_trials(throw=tuple(round(capture[q], 4) for q in ("x", "z", "vx", "vz", "w")))
    for tr in trials:
        tr.pop("released", None)
    spin = dict(nominal=spin_up(supply_a=D.SHOOTER["supply_a"]), weakPack=spin_up(bus_v=WEAK_V, supply_a=D.SHOOTER["supply_a"]),
                transitLimit15A=spin_up(bus_v=WEAK_V, supply_a=15.0),
                note="The flywheel motors bring the wheel from rest to its ready band during the loaded transit: at the launch duty's 30 A "
                     "per-motor supply limit, and at the 15 A per motor the loaded-transit budget row allows")
    chain = dict(capture={q: round(v, 6) for q, v in capture.items()}, seat={q: round(v, 6) for q, v in seat.items()},
                 release={q: round(v, 6) for q, v in rel.items()}, scoringBandMps=band, scoringScan=rows, spinUp=spin,
                 flywheel=dict(D.flywheel_build(), setpointMps=set_mps, readyBand=D.SHOOTER["ready_band"]),
                 note="acquire-nominal ends at capture; entry-nominal starts there and ends clamped at the stage; launch-nominal starts at the stage "
                      "(at rest) and ends at release; deliver-nominal starts at that release. A release speed counts as scoring only if the "
                      "delivery scores at the nominal drag and spin lift (Cd 0.47, CL 0.15) and at all four corners (Cd 0.35 and 0.60, CL 0 and "
                      "0.30). The scoring band is the contiguous run of such speeds in the 0.025 m/s scan around the nominal release.")
    return trials, chain


SOLVER = ("Semi-implicit Euler; penalty normal contact k with damping ratio zeta. Lane trials (entry, hold, launch, batch): stick-slip "
          "friction with a tangential spring, and a rolling resistance couple crr N R. Acquisition, delivery, hang and the 3-D hopper trial: "
          "Coulomb friction regularized at 0.01 m/s")
NOTES = [
    "Acquisition: side view at the front bumper. The belt back run, bottom pulley, top roller and chute back plate stand at the squeeze the layout draws (dimensions.py); variants bracket it. The belt is a free body under its motor and current limits; the FUEL climbs the bumper face and the back plate and is thrown over the top of the back plate.",
    "Hopper entry: side view of the floor lane from the capture state to the stage. The FUEL falls from the chute to the floor belt, which carries it to the feeder roller; the roller turns at its staging speed until the FUEL centre crosses the stage beam, then both stop. The flywheel spins at its setpoint throughout. One FUEL in an empty lane.",
    "Hold: the staged FUEL with the feeder stopped, the floor belt running, the robot accelerating and queued FUEL pushing. Under the roller the floor is the fixed lane deck.",
    "Launch: the same lane. The flywheel is a free body: its inertia, two direct brushless motors with current limits and a speed loop. The feeder advances the FUEL only while the wheel is inside its ready band. The hood is a surface without thickness, and a run ends when the FUEL passes its end.",
    "Batch: 24 FUEL through the one flywheel, each launched from the stage, the wheel carried from shot to shot. Each lane's next FUEL is assumed staged in time; the hopper trials test that.",
    "Hopper: 24 free FUEL in three dimensions. They arrive through the chute at 4 FUEL/s, each thrown in with the acquisition trial's capture state at a random lane position; the feeders stage and hold through a 0.5 g stop, start and turn; from 10 s the lanes feed in turn. A FUEL advanced to the flywheel is counted and removed. A FUEL that comes forward over the back plate, or arrives while the place it would be thrown to is taken, waits in the chute and is thrown in when there is room. Outcomes vary with the arrival pattern, so sixteen are run.",
    "Scoring band: a release speed counts only if the delivery scores at the nominal drag and spin lift and at all four drag and spin corners (chain.scoringScan).",
    "Delivery: starts from the launch trial's release state at the 2.7 m shot pose; HUB body, top plate and cavity from V0 dimensions; the sensor plane at 1.50 m inside the opening is an assumption (V0 does not locate it).",
    "Elevation: rung centred in the upright depth (V0), uprights 5 mm ahead of the bumper, TOWER BASE edge 0.4 mm ahead of the bumper face.",
    "Motor figures are a NEO-class brushless curve (5676 rpm free, 2.6 N m stall, 105 A stall at 12 V); drive efficiency 0.85 to 0.9 is an assumption.",
    "Contact stiffness, damping, friction and rolling resistance are estimates, not measured. No FUEL force-deflection curve is available, so every indentation here is a model result, not a material limit."]


def main():
    trials, chain = run_trials()
    out = dict(schema="frc-2026-poc/field-trials@3", issue="R3-PD3",
               dimensions={"file": "dimensions.py", "sha256": sha(HERE / "dimensions.py")},
               rules={"file": "construction-rules.json", "sha256": sha(HERE / "construction-rules.json")},
               solver=SOLVER, scenarioNotes=NOTES, chain=chain, trials=trials)
    text = json.dumps(out, separators=(",", ":"))
    (HERE / "field-trials.json").write_text(text + "\n", encoding="utf-8", newline="\n")
    for tr in trials:
        print(f"{tr['name']:58s} {'PASS' if tr['passed'] else 'FAIL'}  {tr['metric']['name']}={tr['metric']['value']}  {tr.get('firstUnmet') or ''}")
        if tr["kind"] == "acquisition":
            print("   ", tr["beltDemand"])
        if tr["kind"] in ("entry", "launch", "acquisition", "delivery", "hold"):
            print("    peak indentation mm", {k: max(r[2] for r in v) for k, v in tr["contacts"].items()})
        if tr["kind"] == "entry":
            print("   ", tr["seat"], [e["event"] for e in tr["events"]])
        if tr["kind"] == "launch":
            print("   ", tr["release"], tr["schedule"], {q: v for q, v in tr["wheelDemand"].items() if q not in ("note", "drive")})
        if tr["kind"] == "batch":
            print("   ", {q: v for q, v in tr["batch"].items() if q not in ("shots", "drive")})
        if tr["kind"] == "hopper":
            print("   ", {q: v for q, v in tr["feed"].items() if q not in ("times", "remainingAtMm")})
        if tr["kind"] == "hold":
            print("    creep mm", tr["creepMm"])
        if tr["kind"] == "delivery":
            print("   ", [e["event"] + " " + str(e.get("at", "")) for e in tr["events"]])
        if tr["kind"] == "elevation":
            print("    max pitch deg", round(max(abs(f[3]) for f in tr["frames"]) * 57.3, 2), "peak cable N", max(f[5] for f in tr["frames"]), [e["event"] for e in tr["events"]])
    print("chain", json.dumps(chain))


if __name__ == "__main__":
    main()
