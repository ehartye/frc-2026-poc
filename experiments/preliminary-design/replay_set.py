"""Write the replay set of an R3 release: the recorded hopper cycle, hold-back, batch and hang trials as entries of
the review's one motion list.

Every frame comes from the traces already recorded in field-trials.json. Nothing is solved here. A replay is
playback: the layout check neither runs nor credits it. The robot's members stand at the starting pose of a checked
case; what moves is what the trial recorded.
"""
import gzip
import json
import math

import dimensions as D

NAME = "replays.json.gz"
R = D.R_BALL
FUEL_COLOUR = "#e6b450"
I4 = [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0]


def icosphere(radius, level=2):
    """A closed triangle mesh of a sphere about the origin."""
    t = (1 + 5 ** .5) / 2
    v = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t), (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    f = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
         (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    for _ in range(level):
        mid, out = {}, []

        def m(a, b):
            key = (min(a, b), max(a, b))
            if key not in mid:
                mid[key] = len(v)
                v.append(tuple((v[a][i] + v[b][i]) / 2 for i in range(3)))
            return mid[key]
        for a, b, c in f:
            ab, bc, ca = m(a, b), m(b, c), m(c, a)
            out += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        f = out
    unit = [[x / math.sqrt(sum(q * q for q in p)) * radius for x in p] for p in v]
    return dict(v=[[round(x, 3) for x in p] for p in unit], f=[list(tri) for tri in f])


def mul(a, b):
    """a after b, both row-major 3x4."""
    out = []
    for r in range(3):
        row = [sum(a[r * 4 + k] * b[k * 4 + c] for k in range(3)) for c in range(3)]
        row.append(sum(a[r * 4 + k] * b[k * 4 + 3] for k in range(3)) + a[r * 4 + 3])
        out += row
    return out


def op_matrix(op):
    if op["kind"] == "translation":
        x, y, z = op["travelMm"]
        return [1.0, 0, 0, x, 0, 1.0, 0, y, 0, 0, 1.0, z]
    if op["kind"] == "gravity-drop":
        return [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, -op["fallMm"]]
    ax, ay, az = op["axis"]
    n = math.sqrt(ax * ax + ay * ay + az * az)
    ax, ay, az = ax / n, ay / n, az / n
    c, s = math.cos(math.radians(op["travelDeg"])), math.sin(math.radians(op["travelDeg"]))
    rot = [[c + ax * ax * (1 - c), ax * ay * (1 - c) - az * s, ax * az * (1 - c) + ay * s],
           [ay * ax * (1 - c) + az * s, c + ay * ay * (1 - c), ay * az * (1 - c) - ax * s],
           [az * ax * (1 - c) - ay * s, az * ay * (1 - c) + ax * s, c + az * az * (1 - c)]]
    o = op["originMm"]
    out = []
    for r in range(3):
        out += rot[r] + [o[r] - sum(rot[r][k] * o[k] for k in range(3))]
    return out


def start_pose(case):
    """Member -> the transform from its drawn position to where the checked case starts it."""
    out = {}
    for member, ops in case.get("initialPose", {}).items():
        m = I4
        for op in ops:
            m = mul(op_matrix(op), m)
        out[member] = m
    return out


def shift(x, y, z):
    return [1.0, 0, 0, round(x, 2), 0, 1.0, 0, round(y, 2), 0, 0, 1.0, round(z, 2)]


def static_groups(members, pose, frames, prefix):
    """Members that do not move: one group per distinct starting transform."""
    bodies, groups, seen = {}, {}, {}
    for member in members:
        m = pose.get(member, I4)
        key = tuple(round(x, 6) for x in m)
        if key not in seen:
            seen[key] = f"{prefix}-{len(seen)}"
            groups[seen[key]] = [list(key)] * frames
        bodies[member] = seen[key]
    return bodies, groups


def fuel_body(i, what):
    return dict(name=f"FUEL {i} of the recorded trial", category="game-piece", color=FUEL_COLOUR, subsystem="Game piece",
                material="FUEL: 150.1 mm foam ball", mesh=icosphere(R),
                purpose=what, rationale="Drawn as a rigid sphere at the centre the trial recorded. Its spin and its indentation into the rollers are not drawn.")


def build(out, repo, rel, trial_data, cases, robot_members, field_members, objectives):
    """Write replays.json.gz into the release folder and return its plan pin fields (file is repository-relative)."""
    trials = {t["name"]: t for t in trial_data["trials"]}
    case = {c["id"]: c for c in cases}
    evidence = lambda name: [dict(file=f"{rel}/field-trials.json", role=f"Recorded trial {name}: the frames this replay plays")]
    first = lambda prefix: next(c for c in cases if c["id"].startswith(prefix))
    final = lambda prefix: [c for c in cases if c["id"].startswith(prefix)][-1]
    field, replays = {}, []

    # ------------------------------------------------------------ one FUEL from the carpet into the HUB
    acq, ent, lch, dlv = (trials[k] for k in ("acquire-nominal", "entry-nominal", "launch-nominal", "deliver-nominal"))
    feed = lch["schedule"]["feedStartS"]
    parts = [("collecting", acq["frames"], 2, None, True), ("to the stage", ent["frames"], 2, None, True),
             ("launching", [f for f in lch["frames"] if f[0] >= feed - 1e-9], 2, None, False), ("in flight", dlv["frames"], 3, 2, False)]
    time, rows, measure, events, at_shot, clock = [], [], [], [], [], 0.0
    for word, frames, iz, iy, away in parts:
        events.append(dict(frame=len(time), label=word[0].upper() + word[1:]))
        t0 = frames[0][0]
        for f in frames:
            time.append(round(clock + f[0] - t0, 4))
            rows.append(shift(1000 * f[1], D.TRACK_Y if iy is None else 1000 * f[iy], 1000 * f[iz]))
            measure.append(f"{word} · trial second {f[0]:.2f} · FUEL centre {1000 * f[iz]:.0f} mm above the carpet")
            at_shot.append(not away)
        clock = time[-1] + 0.02
    n = len(time)
    events.append(dict(frame=n - 1, label="In the HUB"))
    start = start_pose(first("acquire-"))
    bodies, groups = static_groups(robot_members, start, n, "robot")
    away_pose = start.get(field_members[0], I4)
    for member in field_members:
        bodies[member] = "field"
    groups["field"] = [list(I4) if here else list(away_pose) for here in at_shot]
    field["replay FUEL tracked"] = fuel_body(1, "The one FUEL the four chained trials follow")
    bodies["replay FUEL tracked"] = "fuel"
    groups["fuel"] = rows
    replays.append(dict(
        id="replay-one-fuel", label="One FUEL from the carpet into the HUB (recorded trials)",
        basis="Recorded trials acquire-nominal, entry-nominal, launch-nominal and deliver-nominal of field-trials.json, played one after another. "
              "Each starts where the one before ended. The checked acquire, hopper, launch and flight cases follow the same path in coarse strokes.",
        objective=objectives["carry"],
        evidence=[dict(file=f"{rel}/field-trials.json", role="Recorded trials acquire-nominal, entry-nominal, launch-nominal and deliver-nominal: the frames this replay plays")],
        recorded=["Centre of the FUEL through the intake, the hopper, the feeder, the flywheel and the flight",
                  "The delivery trial solved the flight and the scoring against a dimensioned HUB opening"],
        display=["The official HUB and TOWER parts are drawn for scale. The trials did not run against them, so where the FUEL meets the funnel is not a trial result",
                 "The loaded drive between collecting and shooting is not in these trials: the field jumps to the shot pose",
                 "The clock restarts with each trial and the waits between them are left out",
                 "Belts, rollers and the flywheel do not turn in the picture"],
        time=time, measure=measure, events=events, follow=bodies["floor pan"], bodies=bodies, groups=groups))

    # ------------------------------------------------------------ collect, hold and feed 24 FUEL
    tr = trials["hopper-cycle-nominal"]
    frames = tr["frames"]
    n = len(frames)
    time = [max(0.0, f[0]) for f in frames]
    pose = start_pose(first("hopper-"))
    bodies, groups = static_groups(robot_members, pose, n, "robot")
    follow = bodies["floor pan"]
    count = len(frames[0]) - 1
    for i in range(1, count + 1):
        key = f"replay FUEL {i:02d}"
        field[key] = fuel_body(i, "One of the 24 FUEL of a recorded trial")
        bodies[key] = f"fuel-{i:02d}"
        groups[f"fuel-{i:02d}"] = [None if f[i] is None else shift(*(1000 * q for q in f[i])) for f in frames]
    fed_at = tr["feed"]["times"]
    accel = tr["params"]["accel"]
    feed_from = tr["params"]["feedFrom"]
    words = {(-0.5, 0.0): "0.5 g stop", (0.5, 0.0): "0.5 g start", (0.0, 0.5): "0.5 g turn"}

    def phase(t):
        for a, b, gx, gy in accel:
            if a <= t <= b:
                return words.get((gx, gy), "accelerating")
        if t < tr["feed"]["lastArrivalS"] + 0.3:
            return "collecting through the chute"
        return "feeding on command" if t >= feed_from else "holding"
    measure = []
    for f in frames:
        aboard = sum(1 for p in f[1:] if p is not None)
        fed = sum(1 for t in fed_at if t <= f[0])
        measure.append(f"{phase(f[0])} · {aboard} FUEL in the robot · {fed} of {count} fed to the flywheel")
    at = lambda t: min(range(n), key=lambda i: abs(time[i] - t))
    events = [dict(frame=0, label="First FUEL thrown in"), dict(frame=at(tr["feed"]["lastArrivalS"]), label="24 collected")]
    events += [dict(frame=at(a), label=words.get((gx, gy), "accelerate")) for a, b, gx, gy in accel]
    events += [dict(frame=at(feed_from), label="Feed command"), dict(frame=n - 1, label="24 fed")]
    replays.append(dict(
        id="replay-hopper-cycle", label="Collect, hold and feed 24 FUEL (recorded trial)",
        basis=f"Recorded trial hopper-cycle-nominal of field-trials.json: {tr['solved']}. Imposed: {tr['imposed']}. "
              f"Result: {tr['feed']['fed']} of {count} fed, {tr['feed']['lost']} lost, {tr['feed']['uncommanded']} uncommanded, "
              f"{tr['feed']['ratePerS']:.2f} FUEL/s. It is one of 16 arrival patterns; all 16 pass.",
        objective=objectives["rate"], evidence=evidence("hopper-cycle-nominal"),
        recorded=[f"Centre of each of the {count} FUEL every 0.04 s, from its throw over the chute back plate to the flywheel",
                  "Times of the stop, start, turn and each feed"],
        display=["The robot is drawn standing still. The trial applies the stop, start and turn as accelerations of the FUEL in the robot's frame",
                 "FUEL are rigid spheres. Spin and indentation are not drawn",
                 "Belts, feeder rollers and the flywheel do not turn in the picture",
                 "A FUEL disappears when the flywheel takes it. The batch replay shows the launch"],
        time=time, measure=measure, events=events, follow=follow, bodies=bodies, groups=groups))

    # ------------------------------------------------------------ hold the staged FUEL off the flywheel
    tr = trials["hold-nominal"]
    frames = tr["frames"]
    n = len(frames)
    pose = start_pose(case["loaded-transit"])
    bodies, groups = static_groups(robot_members, pose, n, "robot")
    field["replay FUEL staged"] = fuel_body(1, "The staged FUEL of the hold-back trial")
    bodies["replay FUEL staged"] = "fuel"
    groups["fuel"] = [shift(1000 * f[1], D.TRACK_Y, 1000 * f[2]) for f in frames]
    x0 = frames[0][1]
    p = tr["params"]
    replays.append(dict(
        id="replay-hold-back", label="Hold the staged FUEL off the flywheel (recorded trial)",
        basis=f"Recorded trial hold-nominal of field-trials.json: {tr['solved']}. Imposed: {tr['imposed']}. "
              f"Result: creep {tr['creepMm']:.2f} mm, least clearance to the flywheel {tr['metric']['value']:.1f} mm against 10 mm. "
              "The motion is about a millimetre, so the picture barely changes: read the creep in the readout. "
              "The limit cases (90 N holds, 120 N fails) are in the trial record trial-hold.json and are not replayed.",
        objective=objectives["traffic"], evidence=evidence("hold-nominal"),
        recorded=["Centre and spin of the staged FUEL every 5 ms for 2 s"],
        display=["The robot is drawn standing still. The 1.5 g acceleration and the 30 N queue push act on the FUEL in the trial",
                 "The feeder roller, belt and flywheel do not turn in the picture"],
        time=[f[0] for f in frames],
        measure=[f"feeder braked · {p['accelG']:g} g · {p['pushN']:g} N push from the queue · creep {abs(f[1] - x0) * 1000:.2f} mm toward the flywheel" for f in frames],
        events=[dict(frame=0, label="Staged, feeder braked"), dict(frame=n - 1, label="Held for 2 s")],
        follow=bodies["floor pan"], bodies=bodies, groups=groups))

    # ------------------------------------------------------------ launch 24 FUEL through the one flywheel
    tr = trials["batch-nominal"]
    one = tr["frames"]                                   # the first shot, from the stage to release
    shots = tr["batch"]["shots"]
    wheel = tr["wheelTrace"]
    lead = shots[0]["feedS"]
    end = shots[-1]["releaseS"]
    step = 0.01
    n = int(math.ceil(end / step)) + 2
    time = [round(i * step, 3) for i in range(n)]
    pose = start_pose(first("launch-"))
    bodies, groups = static_groups(robot_members + field_members, pose, n, "still")

    def along(t):
        """The first shot's recorded centre at t seconds after its own start."""
        if t <= one[0][0]:
            return one[0][1], one[0][2]
        for a, b in zip(one, one[1:]):
            if a[0] <= t <= b[0]:
                u = (t - a[0]) / (b[0] - a[0]) if b[0] > a[0] else 0.0
                return a[1] + u * (b[1] - a[1]), a[2] + u * (b[2] - a[2])
        return None
    for i, shot in enumerate(shots, 1):
        key = f"replay FUEL {i:02d}"
        field.setdefault(key, fuel_body(i, "One of the 24 FUEL of a recorded trial"))
        bodies[key] = f"fuel-{i:02d}"
        staged_from = shots[i - 2]["releaseS"] if i > 1 else 0.0
        rows = []
        for t in time:
            centre = along(t - (shot["feedS"] - lead)) if staged_from <= t <= shot["releaseS"] + step else None
            rows.append(None if centre is None else shift(1000 * centre[0], D.TRACK_Y, 1000 * centre[1]))
        groups[f"fuel-{i:02d}"] = rows

    def wheel_at(t):
        best = wheel[0][1]
        for tt, u in wheel:
            if tt > t:
                break
            best = u
        return best
    measure = []
    for t in time:
        done = [s for s in shots if s["releaseS"] <= t]
        last = f" · last release {done[-1]['speedMps']:.2f} m/s" if done else ""
        measure.append(f"{len(done)} of {len(shots)} released · flywheel surface {wheel_at(t):.2f} m/s{last}")
    band = trial_data["chain"]["scoringBandMps"]
    speeds = [s["speedMps"] for s in shots]
    replays.append(dict(
        id="replay-batch", label="Launch 24 FUEL through the one flywheel (recorded trial)",
        basis=f"Recorded trial batch-nominal of field-trials.json: {tr['solved']}. Imposed: {tr['imposed']}. "
              f"Result: {tr['metric']['value']:.2f} FUEL/s, releases {min(speeds):.2f}-{max(speeds):.2f} m/s inside the {band[0]:g}-{band[1]:g} m/s scoring band.",
        objective=objectives["rate"], evidence=evidence("batch-nominal"),
        recorded=["Feed time, release time and release speed of each of the 24 FUEL", "Flywheel surface speed through the whole batch",
                  "Path of the first FUEL from the stage to release"],
        display=["Every FUEL is drawn on the first FUEL's recorded path, started at its own recorded feed time. The trial kept one path",
                 "A FUEL disappears at release. The flight cases show the path to the HUB",
                 "All 24 are drawn in the tracked lane. The robot feeds its two lanes in turn",
                 "The flywheel and feeder do not turn in the picture"],
        time=time, measure=measure,
        events=[dict(frame=min(n - 1, int(round(s["releaseS"] / step))), label=f"FUEL {s['shot']} released") for s in shots if s["shot"] in (1, 8, 16, 24)],
        follow=bodies["floor pan"], bodies=bodies, groups=groups))

    # ------------------------------------------------------------ lift on the low rung and hold with power removed
    tr = trials["hang-nominal"]
    frames = tr["frames"]
    n = len(frames)
    pose = start_pose(case["climb-lift"])
    cgx, cgz = (1000 * q for q in tr["params"]["cg"])
    lifted = ("climber hook left", "climber hook right", "climber inner tube left", "climber inner tube right")
    bodies, groups = static_groups(field_members, pose, n, "field")
    rigid, moving = {}, {}
    for member in robot_members:
        m = pose.get(member, I4)
        key = (tuple(round(x, 6) for x in m), member in lifted)
        if key not in rigid:
            rigid[key] = f"robot-{len(rigid)}"
            moving[rigid[key]] = (list(key[0]), key[1])
        bodies[member] = rigid[key]
    for name, (m, on_line) in moving.items():
        rows = []
        for t, x, z, th, s, load in frames:
            c, si = math.cos(th), math.sin(th)
            # The trial's rigid body: rotation by th in the side view about the centre of gravity, then its travel.
            body = [c, 0, -si, 1000 * x + cgx - (c * cgx - si * cgz), 0, 1.0, 0, 0, si, 0, c, 1000 * z + cgz - (si * cgx + c * cgz)]
            line = shift(0, 0, -1000 * s) if on_line else I4
            rows.append([round(q, 6) for q in mul(body, mul(line, m))])
        groups[name] = rows
    hold_at = tr["events"][0]["t"]
    hold = tr["cable"]["holdN"]
    replays.append(dict(
        id="replay-hang", label="Lift on the low rung and hold with power removed (recorded trial)",
        basis=f"Recorded trial hang-nominal of field-trials.json: {tr['solved']}. Imposed: {tr['imposed']}. "
              f"Result: least clearance to the carpet or TOWER BASE {1000 * tr['metric']['value']:.1f} mm against 5 mm through the 3 s hold; "
              f"cable load {tr['cable']['liftPeakN']:.0f} N peak, {hold[0]:.0f}-{hold[1]:.0f} N held. {tr['limits']}",
        objective=objectives["hang"], evidence=evidence("hang-nominal"),
        recorded=["Robot travel and pitch every 10 ms", "Winch stroke and cable load"],
        display=["The hooks and inner tubes are drawn retracting by the recorded stroke. The trial holds them on the rung by a contact spring, so they can be drawn a few millimetres off it",
                 "The TOWER stands still. The checked climb-lift case shows the same lift in the robot's frame"],
        time=[f[0] for f in frames],
        measure=[("winch lifting" if f[0] < hold_at else "power removed, brake holding") + f" · robot raised {1000 * f[2]:.0f} mm · pitch {math.degrees(f[3]):.1f}° · cable {f[5]:.0f} N" for f in frames],
        events=[dict(frame=0, label="Hooks seated"), dict(frame=min(range(n), key=lambda i: abs(frames[i][0] - hold_at)), label="Stroke complete, power removed"),
                dict(frame=n - 1, label="Held 3 s")],
        follow=bodies["floor pan"], bodies=bodies, groups=groups))

    data = json.dumps(dict(schema="agent-frc/review-replays@1", fieldBodies=field, replays=replays), separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    (out / NAME).write_bytes(gzip.compress(data, 9, mtime=0))
    return [dict(id=r["id"], frames=len(r["time"]), bodies=len(r["bodies"])) for r in replays]
