"""Build the R3 preliminary package: placed STEP, motion study, budgets, premises and review plan.

Run from anywhere with the project geometry environment:
    python -I -B experiments/preliminary-design/build_package.py [--check] [--fail-fast]
Paths written into the plan are relative to the project root (the repository root).
"""
import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ROOT = HERE.parents[1]
REL = HERE.relative_to(ROOT).as_posix()

from OCP.BRepBndLib import BRepBndLib
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.Bnd import Bnd_Box
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPCAFControl import STEPCAFControl_Writer
from OCP.STEPControl import STEPControl_AsIs
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDocStd import TDocStd_Document
from OCP.XCAFDoc import XCAFDoc_DocumentTool

import geometry as G
import ballistics

ISSUE = "R3-PD2"
PLUGIN = Path(__import__("os").environ["AGENT_FRC"])  # the Agent FRC plugin checkout; required
CLI = PLUGIN / "scripts" / "design.mjs"


def bounds(shape):
    b = Bnd_Box(); BRepBndLib.AddOptimal_s(shape, b, False, False)
    return [*b.CornerMin().Coord(), *b.CornerMax().Coord()]


def volume(shape):
    p = GProp_GProps(); BRepGProp.VolumeProperties_s(shape, p, True)
    return p.Mass()


def dist(a, b):
    q = BRepExtrema_DistShapeShape(a, b)
    assert q.IsDone()
    return q.Value()


def box_point_gap(box, p):
    return math.sqrt(sum(max(box[i] - p[i], 0, p[i] - box[i + 3]) ** 2 for i in range(3)))


def rel(name):
    return f"{REL}/{name}"


def pin(name):
    return {"file": rel(name), "sha256": hashlib.sha256((HERE / name).read_bytes()).hexdigest()}


def write(name, obj):
    (HERE / name).write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8", newline="\n")
    return pin(name)


def T(v):
    return dict(kind="translation", travelMm=[float(x) for x in v])


def ROT(origin, axis, deg):
    return dict(kind="rotation", originMm=[float(x) for x in origin], axis=[float(x) for x in axis], travelDeg=float(deg))


def sub(a, b):
    return [x - y for x, y in zip(a, b)]


# ---------------------------------------------------------------- capacity screen
PITCH = 2 * G.R_BALL + 4.0
LAYER_DZ = PITCH / math.sqrt(2)


def capacity(variant, stowed, extra_exclusions=(), limit=None, avoid=(), xmax=236, phases=5):
    """Supported stacked packing: square layers offset into the hollows below. An upper FUEL needs at least one FUEL
    below and three supports in all, counting walls and solids within 6 mm.

    Every position clears every fixed robot solid by 1.5 mm, stays inside the side walls, behind the rear wall
    above the floor lane, and out of the open intake throat between the lip and the front upper wall.
    The best of phases x phases lattice offsets is kept. It is a geometric stacking screen, not a dynamic fill.
    """
    bodies, k = G.robot_bodies(variant, intake_stowed=stowed)
    solids = [(n, s_, bounds(s_)) for n, (s_, g) in bodies.items()]
    r, clear = G.R_BALL, 1.5
    zmax = k["wall"] - r
    best = []
    for ix in range(phases):
        for iy in range(phases):
            ox, oy = -150 + ix * PITCH / phases, iy * PITCH / phases
            placed, layers = [], []
            for L in range(12):
                z = k["z0"] + L * LAYER_DZ
                if z > zmax:
                    break
                sh = PITCH / 2 if L % 2 else 0.0
                row = []
                for i in range(-1, 6):
                    x = ox + sh + i * PITCH
                    if x < -150 or x > xmax:
                        continue
                    for j in range(-4, 5):
                        y = oy + sh + j * PITCH
                        q = (x, y, z)
                        if abs(y) > 316 + G.DY - r - clear:
                            continue
                        if L > 0 and x < -93 + r + clear:
                            continue  # behind the rear wall only the floor lane feeds the pinch
                        if 170 + r < z < 482 - r and x > 160:
                            continue  # the open intake throat does not retain a FUEL
                        below = sum(1 for b in layers[L - 1] if math.dist(q, b) <= PITCH + 1) if L > 0 else 0
                        if L > 0 and below == 0:
                            continue
                        if any(box_point_gap(b, q) < r + clear for b in extra_exclusions):
                            continue
                        if avoid and min(math.dist(q, a) for a in avoid) < 2 * r + 2:
                            continue
                        near = [sh_ for n, sh_, b in solids if box_point_gap(b, q) < r + 6]
                        touching = 0
                        if near:
                            ball = G.sphere(q)
                            gaps = [dist(ball, o) for o in near]
                            if any(g < clear for g in gaps):
                                continue
                            touching = sum(1 for g in gaps if g <= 6)
                        if L > 0 and below + touching < 3:
                            continue  # an upper FUEL needs three supports: FUEL below or walls and solids within 6 mm
                        row.append(q)
                layers.append(row)
                placed += row
            if len(placed) > len(best):
                best = placed
    return (best[:limit] if limit else best), k


def supported_positions(variant, stowed, extra_exclusions=(), avoid=(), limit=7):
    """Greedy bottom-up deposition on a 22 mm grid. An upper FUEL needs a FUEL below it and three contacts in all
    (FUEL within 2 mm, or solids within 6 mm). Used to place the preload, not to claim capacity."""
    bodies, k = G.robot_bodies(variant, intake_stowed=stowed)
    solids = [(n, s_, bounds(s_)) for n, (s_, g) in bodies.items()]
    r = G.R_BALL
    zs = [k["z0"] + 11 * i for i in range(60) if k["z0"] + 11 * i <= k["wall"] - r]
    cands = sorted(((x, y, z) for z in zs for x in range(-150, 237, 22) for y in range(-238, 239, 22)),
                   key=lambda q: (q[2], q[0], abs(q[1]), q[1]))
    placed = []
    for q in cands:
        if abs(q[1]) > 316 + G.DY - r - 1.5 or (q[2] > k["z0"] + 10 and q[0] < -93 + r + 1.5):
            continue
        if 170 + r < q[2] < 482 - r and q[0] > 160:
            continue
        if any(math.dist(q, o) < 2 * r + 1.5 for o in placed):
            continue
        if any(box_point_gap(b, q) < r + 1.5 for b in extra_exclusions):
            continue
        if avoid and min(math.dist(q, a) for a in avoid) < 2 * r + 2:
            continue
        ball = G.sphere(q)
        gaps = [dist(ball, o) for n, o, b in solids if box_point_gap(b, q) < r + 6]
        if any(g < 1.5 for g in gaps):
            continue
        if q[2] > k["z0"] + 1:
            below = [o for o in placed if o[2] < q[2] - 40 and math.dist(q, o) <= 2 * r + 3.5]
            contacts = len([o for o in placed if math.dist(q, o) <= 2 * r + 3.5]) + sum(1 for g in gaps if g <= 6)
            if not below or contacts < 3:
                continue
        placed.append(q)
        if len(placed) >= limit:
            break
    return placed


def free_volume(variant, stowed):
    """Hopper volume available to FUEL material: the walled envelope minus every robot solid inside it (exact booleans)."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    bodies, k = G.robot_bodies(variant, intake_stowed=stowed)
    env = G.box((-93, -316 - G.DY, k["belt_top"]), (311, 316 + G.DY, k["wall"]))
    env = BRepAlgoAPI_Cut(env, G.box((236, -340 - G.DY, 170), (320, 340 + G.DY, 482))).Shape()  # the open throat holds nothing
    pinch = G.box((-150 - G.R_BALL, -173, k["belt_top"]), (-93, 173, k["z0"] + G.R_BALL))
    total = 0.0
    for region in (env, pinch):
        for n, (s_, g) in bodies.items():
            b = bounds(s_)
            region = BRepAlgoAPI_Cut(region, s_).Shape()
        total += volume(region)
    vball = 4 / 3 * math.pi * G.R_BALL ** 3
    return dict(freeVolumeMm3=round(total, 0), ballVolumeMm3=round(vball, 0),
                estimateAtPacking={str(f): round(f * total / vball, 1) for f in (0.45, 0.50, 0.55)})


# ---------------------------------------------------------------- tracked FUEL path
def tracked_path(k):
    """Approach under the belt, climb the bumper face in the belt pinch, pass under the top roller, drop to the floor."""
    ip = G.intake_points()
    y = 82.5
    zf = G.R_BALL + G.GAP
    bx = ip["ball_x"]
    top = G.INTAKE["climb_top"]
    pts = dict(S0=(700.0, y, zf), S1=(bx, y, zf), S2=(bx, y, top), S3=(140.0, y, top), D=(140.0, y, k["z0"]))
    return pts, ip


def circle(p, q, r):
    """Centre of the XZ circle through three points."""
    ax, az = p; bx, bz = q; cx, cz = r
    d = 2 * (ax * (bz - cz) + bx * (cz - az) + cx * (az - bz))
    ux = ((ax * ax + az * az) * (bz - cz) + (bx * bx + bz * bz) * (cz - az) + (cx * cx + cz * cz) * (az - bz)) / d
    uz = ((ax * ax + az * az) * (cx - bx) + (bx * bx + bz * bz) * (ax - cx) + (cx * cx + cz * cz) * (bx - ax)) / d
    return ux, uz


def flight(k, hub_x, segments=4, cd=0.47, cl=0.15, mass=0.215):
    """Choose the centre of the speed band that enters at the nominal drag and spin lift; fit circular arcs to the path."""
    ex, ez = k["exit_point"]
    d = (ex - hub_x) / 1000
    scan = []
    for i in range(400):
        v = round(5.0 + 0.01 * i, 2)
        if ballistics.score(ballistics.fly(v, G.EXIT_DEG, ez / 1000, mass, cd, cl), d)[0]:
            scan.append(v)
    assert scan, "no entry window"
    band = [min(scan), max(scan)]
    v = round((band[0] + band[1]) / 2, 2)
    path = ballistics.fly(v, G.EXIT_DEG, ez / 1000, mass, cd, cl)
    ok, edge, landing = ballistics.score(path, d)
    assert ok
    apex = max(range(len(path)), key=lambda j: path[j][2])
    end = next(j for j in range(apex, len(path)) if path[j][2] <= 1.70)
    robust, per = ballistics.robust(G.EXIT_DEG, ez / 1000, d, ballistics.CONDITIONS)
    xz = lambda j: (ex - 1000 * path[j][1], 1000 * path[j][2])
    cuts = [round(end * i / segments) for i in range(segments + 1)]
    arcs, err = [], 0.0
    for a_, b_ in zip(cuts, cuts[1:]):
        m = (a_ + b_) // 2
        c = circle(xz(a_), xz(m), xz(b_))
        r = math.dist(c, xz(a_))
        ang = lambda p: math.atan2(p[1] - c[1], p[0] - c[0])
        phi = math.degrees(ang(xz(a_)) - ang(xz(b_)))
        phi = (phi + 180) % 360 - 180
        err = max(err, max(abs(math.dist(c, xz(j)) - r) for j in range(a_, b_ + 1)))
        arcs.append(dict(centreMm=list(c), deg=phi, start=list(xz(a_)), end=list(xz(b_))))
    return dict(speedMps=v, nominalBandMps=band, robustBandMps=robust, conditionBandsMps=per, distanceM=d, exitHeightM=ez / 1000,
                elevationDeg=G.EXIT_DEG, cd=cd, cl=cl, massKg=mass, flightS=path[end][0], landingOffsetFromHubCentreMm=1000 * landing,
                rimEdgeClearanceMm=1000 * edge, arcs=arcs, maxArcDeviationMm=err)


def swept_envelope(cases, shapes, robot_members):
    """Extremes of every robot member (bumpers excluded) at 49 fractions of each operating and park case.

    R105 front/rear/side extension beyond the 340 mm frame half-width, R106 sides extended at once,
    R107 height (the robot's own height as if on a flat floor), and the starting-fold overhang.
    """
    sys.path.insert(0, str(PLUGIN / "scripts"))
    from mechanical_motion import transform
    out = dict(front=-1e9, rear=-1e9, side=-1e9, top=-1e9, maxSides=0, startOverhang=None, worst={})
    static = {n: bounds(shapes[n]) for n in robot_members}
    for c in cases:
        if c["stage"] == "service":
            continue
        moving = [n for n in robot_members if n in c["moves"] or n in c.get("initialPose", {})]
        for i in range(49):
            t = i / 48
            boxes = dict(static)
            for n in moving:
                placed = transform(shapes[n], c.get("initialPose", {}).get(n, []), 1)
                boxes[n] = bounds(transform(placed, c["moves"].get(n, []), t))
            ext = dict(front=max(b[3] for b in boxes.values()) - 340, rear=-340 - min(b[0] for b in boxes.values()),
                       left=max(b[4] for b in boxes.values()) - G.HALF_W, right=-G.HALF_W - min(b[1] for b in boxes.values()),
                       top=max(b[5] for b in boxes.values()))
            ext["side"] = max(ext["left"], ext["right"])
            sides = sum(1 for key in ("front", "rear", "left", "right") if ext[key] > 0.5)
            for key in ("front", "rear", "side", "top"):
                if ext[key] > out[key]:
                    out[key] = ext[key]; out["worst"][key] = dict(case=c["id"], t=t)
            out["maxSides"] = max(out["maxSides"], sides)
            if out["startOverhang"] is None:
                out["startOverhang"] = max(ext["front"], ext["rear"], ext["side"])
            if not moving:
                break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--fail-fast", action="store_true")
    ap.add_argument("--previous", help="held checkpoint receipt, project-relative")
    args = ap.parse_args()

    bodies, k = G.robot_bodies("R3")
    groups_of = {n: g for n, (s, g) in bodies.items()}
    shapes = {n: s for n, (s, g) in bodies.items()}

    # Shot pose: HUB centre 2700 mm aft of the robot centre. Acquire pose is (400, 2000) in shot coordinates.
    hub_shot = (-2700.0, 0.0); tower_face_shot, tower_y_shot = 1025.0, -1250.0
    acq = (400.0, 2000.0)
    field = G.field_bodies(k, (hub_shot[0] - acq[0], hub_shot[1] - acq[1]), tower_face_shot - acq[0], tower_y_shot - acq[1])
    for n, s in field.items():
        shapes[n] = s; groups_of[n] = "field"

    pts, ip = tracked_path(k)
    D = pts["D"]
    shapes["FUEL tracked"] = G.sphere(D); groups_of["FUEL tracked"] = "tracked FUEL"
    cleat_x0 = D[0] + G.R_BALL + G.GAP
    shapes["indexer cleat"] = G.box((cleat_x0, D[1] - 60, k["belt_top"] + 1.5), (cleat_x0 + 8, D[1] + 60, k["z0"]))
    groups_of["indexer cleat"] = "floor indexer"

    # Capacity, with the cleat present and the tracked piece's pocket excluded from the stored set.
    vol = {v: {st: free_volume(v, st == "stowed") for st in ("deployed", "stowed")} for v in ("R3", "R3L")}
    dep, _ = capacity("R3", False)
    stow, _ = capacity("R3", True)
    low_dep, kl = capacity("R3L", False)
    low_stow, _ = capacity("R3L", True)

    # Stored AUTO preload: stable positions in the starting fold, clear of the slide sweep and every commissioned path.
    path_samples = []
    seq = [pts[x] for x in ("S0", "S1", "S2", "S3", "D")]
    for a, b in zip(seq, seq[1:]):
        for i in range(21):
            path_samples.append(tuple(a[j] + (b[j] - a[j]) * i / 20 for j in range(3)))
    cx, cz = k["c"]
    for i in range(41):
        path_samples.append((D[0] + (cx - D[0]) * i / 40, D[1], D[2]))
    columns = [(-90, 236 + G.DY, 83, 77, 312 + G.DY, 4000), (-342, -263, 80, -99, 190, 4000), (-73, 22.5, 91.5, 227, 142.5, 168.1),
               (170, -275, 150, 620, 275, 480)]
    stored = supported_positions("R3", True, extra_exclusions=columns, avoid=path_samples, limit=7)
    assert len(stored) >= 2, f"only {len(stored)} supported stored positions"
    for i, p in enumerate(stored, 1):
        shapes[f"FUEL stored {i}"] = G.sphere(p); groups_of[f"FUEL stored {i}"] = "stored FUEL"

    # ---------------------------------------------------------- STEP
    doc = TDocStd_Document(TCollection_ExtendedString("BinXCAF"))
    table = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    for name, s in shapes.items():
        TDataStd_Name.Set_s(table.AddShape(s, False), TCollection_ExtendedString(name))
    w = STEPCAFControl_Writer()
    assert w.Transfer(doc, STEPControl_AsIs) and w.Write(str(HERE / "package.step")) == IFSelect_RetDone
    import re
    text = (HERE / "package.step").read_text(encoding="utf-8")
    text = re.sub(r"FILE_NAME\('Open CASCADE Shape Model','[^']*'", "FILE_NAME('R3-PD1 package','2026-11-22T00:00:00'", text, count=1)
    (HERE / "package.step").write_text(text, encoding="utf-8", newline="\n")
    step = pin("package.step")

    design_path = HERE / "design.json"
    if design_path.exists():
        design_path.unlink()
    subprocess.run(["node", str(CLI), "new", str(design_path)], check=True, stdout=subprocess.DEVNULL)
    d = json.loads(design_path.read_text(encoding="utf-8"))
    d["design"]["frameProfile"] = {"kind": "square"}
    d["design"]["parameters"].update(frameLengthM=0.68, frameWidthM=0.714, trackM=0.564, bumperBottomM=0.048,
                                     bumperHeightM=0.12, bumperDepthM=0.0775, height=0.75, reach=0.274,
                                     toolHeight=0.25, opening=0.516, phase="deployed")
    design_path.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8", newline="\n")
    chk = subprocess.run(["node", str(CLI), "validate", str(design_path)], capture_output=True, text=True)
    assert chk.returncode == 0, chk.stderr + chk.stdout
    design = pin("design.json")
    datum = dict(name="R3 robot datum: carpet plane at the frame centre, +X toward the intake, +Y left, millimetres",
                 robotToStepMm=[1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1])

    # ---------------------------------------------------------- groups
    roles = {"frame": "structure", "hopper": "structure", "climber tubes": "structure", "bumpers": "bumper",
             "drivetrain": "drive", "battery": "battery", "electrical": "other", "floor belts": "mechanism",
             "floor indexer": "mechanism", "shooter": "mechanism", "intake": "mechanism", "climber hooks": "mechanism", "climber inner tubes": "mechanism",
             "tracked FUEL": "payload", "stored FUEL": "payload", "field": "other"}
    groups = {g: dict(role=r, members=sorted(n for n, gg in groups_of.items() if gg == g)) for g, r in roles.items()}
    G_ = lambda g: groups[g]["members"]
    field_m = G_("field")

    # ---------------------------------------------------------- cases
    history = {n: [] for n in shapes}
    cases, stages = [], {}
    fly = flight(k, hub_shot[0])

    def case(cid, stage, basis, moves, moving_groups, carried=None, initial=None, extra=None):
        init = {n: list(v) for n, v in history.items() if v}
        if initial:
            for n, v in initial.items():
                if v:
                    init[n] = v
                else:
                    init.pop(n, None)
        c = dict(id=cid, stage=stage, basis=basis, moves=moves, minGapMm=1.0)
        if init:
            c["initialPose"] = init
        if extra:
            c.update(extra)
        if all(op["kind"] == "translation" for ops in moves.values() for op in ops):
            c["checkLinearEnvelope"] = True
        cases.append(c)
        stages[cid] = dict(purpose=stage, movingGroups=moving_groups, carriedWith=carried or {},
                           allowanceBasis="1 mm preliminary reserve between unrelated solids; guided FUEL paths keep a 3 mm undeformed reserve; separately listed joints are drawn with at least 1.5 mm splits")
        for n, ops in moves.items():
            history[n] = (initial.get(n) if initial and n in initial else history[n]) + ops
        if initial:
            for n, v in initial.items():
                if n not in moves:
                    history[n] = v

    intake = G_("intake")
    shift = list(G.INTAKE["shift"])
    history.update({n: [T([-v for v in shift])] for n in intake})
    ball = "FUEL tracked"
    P = lambda key: list(pts[key])
    off = lambda key: sub(P(key), list(D))
    history[ball] = [T(off("S0"))]

    case("intake-deploy", "operating", "Slide the intake carriage 280 mm forward and 62 mm down from the legal start fold, over the bumper",
         {n: [T(shift)] for n in intake}, ["intake"])
    for n in intake:
        history[n] = []  # the translations cancel; continue from the installed deployed pose
    legs = [("acquire-approach", "S0", "S1", "Drive onto the FUEL; it passes under the belt module to the bumper face with 3 mm undeformed reserve"),
            ("acquire-climb", "S1", "S2", "The vertical belt lifts the FUEL against the bumper face (pinch compression is a detailed-design setting)"),
            ("acquire-over", "S2", "S3", "The top roller pushes the FUEL aft over the bumper, front rail and lip into the hopper")]
    for cid, a, b, basis in legs:
        case(cid, "operating", basis, {ball: [T(sub(P(b), P(a)))]}, ["tracked FUEL"], initial={ball: [T(off(a))]})
    fall = pts["S3"][2] - D[2]
    case("acquire-drop", "operating", "Release onto the floor belts at the front of the indexer lane",
         {ball: [dict(kind="gravity-drop", fallMm=fall, quadraticFraction=1.0)]}, ["tracked FUEL"],
         initial={ball: [T((0, 0, fall))]})
    history[ball] = []
    transit = (acq[0], acq[1], 0)
    case("loaded-transit", "operating", "Drive loaded from the DEPOT side of the alliance zone to the shot pose (robot frame: the field moves)",
         {n: [T(transit)] for n in field_m}, ["field"])
    run = cx - D[0]
    case("index", "operating", "A floor-belt cleat carries the tracked FUEL 290 mm aft to the flywheel pinch",
         {ball: [T((run, 0, 0))], "indexer cleat": [T((run, 0, 0))]}, ["tracked FUEL", "floor indexer"],
         carried={"tracked FUEL": "floor indexer"})
    wrap = ROT((cx, 0, cz), (0, 1, 0), G.EXIT_DEG)
    case("launch-wrap", "operating", f"The FUEL rolls {G.EXIT_DEG} degrees around the flywheel against the hood and releases at {G.EXIT_DEG} degrees elevation",
         {ball: [wrap]}, ["tracked FUEL"])
    hub_now = hub_shot
    ex, ez = k["exit_point"]
    for i, arc in enumerate(fly["arcs"], 1):
        c = arc["centreMm"]
        case(f"flight-{i}", "operating", f"Ballistic arc {i} of {len(fly['arcs'])} at {fly['speedMps']} m/s toward the HUB opening (prescribed; drag Cd {fly['cd']}, spin lift CL {fly['cl']}; circular fit within {fly['maxArcDeviationMm']:.1f} mm)",
             {ball: [ROT((c[0], 0, c[1]), (0, 1, 0), arc["deg"])]}, ["tracked FUEL"])
    world = field_m + [ball]
    case("tower-lateral", "operating", "Drive sideways to the TOWER line and reset the indexer cleat",
         {**{n: [T((0, -tower_y_shot, 0))] for n in world}, "indexer cleat": [T((-run, 0, 0))]},
         ["field", "tracked FUEL", "floor indexer"])
    approach = -(tower_face_shot - 417.5 - 5.0)
    case("tower-forward", "operating", "Close to 5 mm from the uprights with the deployed intake between them",
         {n: [T((approach, 0, 0))] for n in world}, ["field", "tracked FUEL"])
    hooks = G_("climber hooks")
    hz = k["hook"] - 6
    yc = 299 + G.DY
    reach = {"climber hook left": [ROT((300, yc, hz), (0, 0, 1), 180)], "climber hook right": [ROT((300, -yc, hz), (0, 0, 1), -180)]}
    case("climb-reach", "operating", "Swing both hooks 180 degrees inboard above the rung so the jaws pass beyond it", reach, ["climber hooks"])
    rung_top = 685.8 + 42.164 / 2
    seat = -(k["hook"] - 12 - (rung_top + 1.5))
    case("climb-seat", "operating", "Lower the hooks onto the low rung; a 2 mm seat contact is required at the end of the stroke",
         {n: [T((0, 0, seat))] for n in hooks + G_("climber inner tubes")}, ["climber hooks", "climber inner tubes"],
         extra={"requiredContacts": [dict(id=f"{side} hook seats on low rung", pair=[f"climber hook {side}", "tower low rung"],
                                          criterion="Hook arm underside within 2 mm of the rung top", maxGapMm=2.0, window=[0.9, 1.0])
                                     for side in ("left", "right")]})
    lift = 70.0
    case("climb-lift", "operating", "Retract the hooks 70 mm; in the robot frame the field and hooks move down together (Level 1 clears carpet and base)",
         {n: [T((0, 0, -lift))] for n in hooks + G_("climber inner tubes") + world}, ["climber hooks", "climber inner tubes", "field", "tracked FUEL"])
    case("park-lower", "park", "After the match, lower the robot back to the carpet",
         {n: [T((0, 0, lift))] for n in hooks + G_("climber inner tubes") + world}, ["climber hooks", "climber inner tubes", "field", "tracked FUEL"])
    cycle = [c["id"] for c in cases]

    def service(cid, group, basis):
        mv = {n: [T((0, 0, 2000))] for n in G_(group)}
        c = dict(id=cid, stage="service", basis=basis, moves=mv, minGapMm=1.0, extract=sorted(mv), checkLinearEnvelope=True)
        cases.append(c)
        stages[cid] = dict(purpose="service", movingGroups=[group], carriedWith={},
                           allowanceBasis="1 mm preliminary reserve during withdrawal")
    service("battery-withdraw", "battery", "Lift the battery straight out through the open hopper with the intake deployed and hooks stowed; the 2 m stroke passes the field fixtures' envelope used by the checker")
    service("shooter-withdraw", "shooter", "Lift the flywheel, hood, side plates and both motors out as one module")

    motion = write("paths.json", dict(schema="agent-frc/mechanical-motion@1", step=step, layoutDesignSha256=design["sha256"],
                                      layoutDatum=datum, cases=cases))

    mounts = [dict(group="floor belts", on="floor pan", pointMm=[0, 0, k["floor"]], basis="Belt bed rests on the floor pan"),
              dict(group="floor indexer", on="floor belt main", pointMm=[0, 82.5, k["belt_top"]], basis="Cleat rides the main belt"),
              dict(group="shooter", on="frame rail rear", pointMm=[-327, 0, 120.65], basis="Shooter side plates bolt to the rear rail top"),
              dict(group="intake", on="intake slide rail left", pointMm=[300, 278, 400], basis="Carriage plates run on the two-stage slide; the fixed stage is drawn"),
              dict(group="climber inner tubes", on="climber tube left", pointMm=[300, 299 + G.DY, 500], basis="Inner tube runs in bushings in the fixed outer tube"),
              dict(group="climber hooks", on="climber inner tube left", pointMm=[300, 299 + G.DY, k["hook"] - 14], basis="Swing joint on the inner tube top")]

    # ---------------------------------------------------------- budgets
    requirements_cases = {}
    loads = {
        # battery-side ampere ranges per source in each stage (conservative bounds, see study)
        "intake-deploy": dict(drive=[10, 60], steer=[2, 8], intake=[5, 25], indexer=[0, 5], flywheel=[0, 5], climber=[0, 0], controls=[3, 6]),
        "acquire": dict(drive=[20, 90], steer=[2, 10], intake=[10, 30], indexer=[2, 10], flywheel=[0, 5], climber=[0, 0], controls=[3, 6]),
        "loaded-transit": dict(drive=[50, 100], steer=[3, 12], intake=[0, 10], indexer=[0, 5], flywheel=[5, 30], climber=[0, 0], controls=[3, 6]),
        "index": dict(drive=[0, 40], steer=[0, 6], intake=[0, 10], indexer=[5, 15], flywheel=[10, 30], climber=[0, 0], controls=[3, 6]),
        "launch": dict(drive=[0, 40], steer=[0, 6], intake=[0, 10], indexer=[5, 15], flywheel=[20, 60], climber=[0, 0], controls=[3, 6]),
        "tower": dict(drive=[20, 90], steer=[2, 10], intake=[0, 2], indexer=[0, 2], flywheel=[0, 5], climber=[0, 2], controls=[3, 6]),
        "climb": dict(drive=[0, 10], steer=[0, 4], intake=[0, 2], indexer=[0, 2], flywheel=[0, 2], climber=[10, 45], controls=[3, 6]),
        "park": dict(drive=[0, 5], steer=[0, 2], intake=[0, 2], indexer=[0, 2], flywheel=[0, 2], climber=[5, 20], controls=[3, 6]),
    }
    stage_load = {"intake-deploy": "intake-deploy", "loaded-transit": "loaded-transit", "index": "index",
                  "launch-wrap": "launch", "flight-1": "launch", "flight-2": "launch", "flight-3": "launch", "flight-4": "launch",
                  "tower-lateral": "tower", "tower-forward": "tower", "climb-reach": "climb", "climb-seat": "climb",
                  "climb-lift": "climb", "park-lower": "park"}
    need = {"launch": 8.0, "index": 7.5, "loaded-transit": 7.5, "tower": 7.5, "climb": 7.5, "acquire": 7.5, "intake-deploy": 7.5, "park": 7.0}
    sources = ["drive", "steer", "intake", "indexer", "flywheel", "climber", "controls"]
    elec = {}
    for cid in cycle:
        key = stage_load.get(cid, "acquire")
        for cond, voc, res in (("nominal", [12.4, 12.8], [0.012, 0.016]), ("weak", [11.9, 12.2], [0.020, 0.026])):
            requirements_cases[f"{cid}-{cond}"] = dict(stage=cid, batteryCondition=cond, sources=sources,
                                                       duty=f"{key} duty during {cid}", requiredMotionMinV=need[key])
            elec[f"{cid}-{cond}"] = dict(basis=f"Simultaneous battery-side bounds for the {key} duty with supply current limits (drive 25 A per module battery-side)",
                                         loadedKg=None, batterySideA=loads[key], openCircuitV=voc, resistanceOhm=res)
    mass_rows = [
        ("frame and floor", G_("frame"), [5.2, 6.6], "Four 2x1x0.125 in 6061 rails (2.72 m at 1.20 kg/m), 3 mm polycarbonate floor (about 0.4 m2), lip, slide rails, tube mounts, gussets"),
        ("hopper walls", G_("hopper"), [2.4, 3.4], "Four 2 mm polycarbonate panels (about 2.5 kg at 1.2 g/cm3) plus edge stiffeners"),
        ("drivetrain", G_("drivetrain"), [8.5, 10.5], "Four MAXSwerve corners: 1.720 kg purchased assembly each (foundation reconciliation) plus drive and steering motors"),
        ("floor indexer", G_("floor belts") + G_("floor indexer"), [1.5, 2.3], "Two belt runs, rollers, cleats, one motor and gearbox"),
        ("shooter", G_("shooter"), [5.0, 6.8], "Flywheel shaft with 0.006 kg m2 inertia, hood, two side plates, two flywheel motors, bearings"),
        ("intake", G_("intake"), [2.8, 3.8], "Vertical belt module with internal motor, top roller, carriage plates and slide moving stage"),
        ("climber", G_("climber tubes") + G_("climber inner tubes") + G_("climber hooks"), [3.0, 4.0], "Two telescoping tube pairs, hooks with swing actuators inside the inner tubes, winch and cables"),
        ("electrical and controls", G_("electrical"), [4.2, 5.4], "Power distribution, controller, radio, 15 motor controllers, breaker, sensors, wiring on two side panels"),
        ("bumpers (excluded by R103)", G_("bumpers"), [0.0, 0.0], "R103 excludes bumpers; 6.0-7.5 kg carried in the running payload and in the R408 check"),
        ("battery (excluded by R103)", G_("battery"), [0.0, 0.0], "R103 excludes the battery and its connector half; 5.0-6.9 kg (V0 battery 4.99-6.57 kg plus leads) carried in the running payload"),
        ("field fixtures (not robot)", field_m, [0.0, 0.0], "HUB and TOWER references are field equipment"),
        ("unmodeled robot hardware", [], [3.0, 5.0], "Fasteners, brackets, cable chain, camera and spares not yet drawn"),
    ]
    payload = [6.0 + 5.0 + 24 * 0.203, 7.5 + 6.9 + 24 * 0.227]
    inspection = [sum(r[2][0] for r in mass_rows), sum(r[2][1] for r in mass_rows)]
    running = [inspection[0] + payload[0], inspection[1] + payload[1]]
    for row in elec.values():
        row["loadedKg"] = running
    req = write("package-limits.json", dict(
        basis="V0 R103 inspection limit from construction-rules.json; roboRIO brownout near 6.75 V plus margin; per-duty minimums in the study",
        inspectionLimitKg=52.16, operatingMinV=7.0, massLines=[r[0] for r in mass_rows], electricalCases=requirements_cases))
    budgets = write("budgets.json", dict(issue=ISSUE, step=step, motion=motion, design=design, requirements=req,
        runningPayloadKg=payload,
        runningPayloadBasis="Bumpers 6.0-7.5 kg, battery and leads 5.0-6.9 kg and 24 FUEL at 0.203-0.227 kg: all carried in the match but outside the R103 weighing",
        masses=[dict(id=i, members=m, kg=kg, basis=b) for i, m, kg, b in mass_rows], electricalCases=elec))

    # ---------------------------------------------------------- premises and measurements
    import bump_crossing
    bump = bump_crossing.screen(k["floor"])
    robot_members = [n for n, g in groups_of.items() if roles[g] not in ("payload", "other", "bumper")] + G_("electrical")
    sweep = swept_envelope(cases, shapes, robot_members)
    deployed_reach = max(bounds(s_)[3] for n, (s_, g) in bodies.items() if g != "bumpers") - 340.0
    measured = dict(issue=ISSUE, designSha256=design["sha256"], stepSha256=step["sha256"],
                    startOverhangMm=round(sweep["startOverhang"], 3), sweptTopMm=round(sweep["top"], 3),
                    sweptFrontExtensionMm=round(sweep["front"], 3), sweptOtherExtensionMm=round(max(sweep["rear"], sweep["side"]), 3),
                    sidesExtendedMax=float(sweep["maxSides"]), sweptWorst=sweep["worst"], deployedReachMm=round(deployed_reach, 3),
                    capacityDeployed=float(len(dep)), capacityStowed=float(len(stow)),
                    volumeEstimateDeployedLow=vol["R3"]["deployed"]["estimateAtPacking"]["0.45"], volumeEstimateStowedLow=vol["R3"]["stowed"]["estimateAtPacking"]["0.45"], lowCapacityDeployed=float(len(low_dep)), lowCapacityStowed=float(len(low_stow)),
                    releaseDistanceM=round(fly["distanceM"], 4), deliveryPoseM=round(-hub_shot[0] / 1000, 4),
                    withBumpersUpperKg=round(inspection[1] + 7.5, 3), bellyClearanceMm=k["floor"] - 6.0,
                    bumpCrossingClearanceMm=bump["minClearanceMm"], bumpCrossingLimit=bump["limitingFeature"],
                    bumperUprightOverlapMm=round(G.HALF_W + 76.5 - 819.15 / 2, 2),
                    basis="Measured by build_package.py from the solids it writes to package.step and the cases it writes to paths.json. Extensions sample every robot member except bumpers at 49 fractions of each operating and park case. Capacity premises use free_volume() at a 0.45 packing fraction; capacity() is a rigid stacked-lattice lower bound.")
    for old in HERE.glob(f"premise-{ISSUE}-*.json"):  # earlier issues keep their pinned premise files
        old.unlink()
    write("measurements.json", measured)
    current_src = pin("measurements.json")
    rules = pin("construction-rules.json")
    strategy = {"file": "kickoff/selected-strategy.json", "sha256": hashlib.sha256((ROOT / "kickoff/selected-strategy.json").read_bytes()).hexdigest()}
    profile = {"file": "kickoff/field-profile.json", "sha256": hashlib.sha256((ROOT / "kickoff/field-profile.json").read_bytes()).hexdigest()}
    # Replay input for the held delivery-pose premise: the named depot-shift step of slot 2 in the re-run series.
    held = HERE / "receipt-R3-PD1-held.json"
    # The repeat keeps the held premise's scenario identity; its own unit is inches from the blue-hub station centre.
    HELD_SCENARIO = "Robot-centre distance from the HUB centre at delivery in the field rehearsal (2.16 m at its delivery steps)"
    held_plan = json.loads(held.read_text(encoding="utf-8"))["planSha256"] if held.exists() else None
    rprof = HERE / "rehearsal" / "r3-2p7m-profile.json"
    rsteps = json.loads(rprof.read_text(encoding="utf-8"))["rehearsal"]["programs"]
    hub_in = (182.1, 158.85)

    def step_pose(match, actor, period, index):
        out = subprocess.run(["node", str(PLUGIN / "scripts" / "rehearsal-step-pose.mjs"), str(rprof), match, actor, period, str(index)],
                             capture_output=True, text=True, encoding="utf-8")
        assert out.returncode == 0, out.stderr
        return json.loads(out.stdout)
    depot_pose = step_pose("Neutral return", "B2", "Shift 1", 3)
    auto_pose = step_pose("Neutral return", "B2", "AUTO", 1)
    for pose in (depot_pose, auto_pose):
        dx, dy = pose["pointIn"][0] - hub_in[0], pose["pointIn"][1] - hub_in[1]
        pose["hubCentreDistanceM"] = round(math.hypot(dx, dy) * 0.0254, 4)
        pose["bearingFromHubAxisDeg"] = round(math.degrees(math.atan2(dy, -dx)), 2)
    field_input = dict(input="stationPosition", actor="B2", station="blue-hub")  # every B2 attempt at the station, series-wide
    measured["deliveryStandoffIn"] = depot_pose["standoffIn"]
    write("measurements.json", measured)
    current_src = pin("measurements.json")
    delivery_evidence = write("rehearsal/delivery-pose-evidence.json", dict(
        premise="delivery-pose", phase="conceptual-design",
        scenario=HELD_SCENARIO,
        issue=ISSUE, designSha256=design["sha256"], stepSha256=step["sha256"],
        fieldReplay=dict(field_input,
                         profile={"file": f"{REL}/rehearsal/r3-2p7m-profile.json", "sha256": hashlib.sha256(rprof.read_bytes()).hexdigest()},
                         result={"file": f"{REL}/rehearsal/r3-2p7m-series.json", "sha256": hashlib.sha256((HERE / "rehearsal" / "r3-2p7m-series.json").read_bytes()).hexdigest()}),
        resolvedSteps=[depot_pose, auto_pose],
        frame="Blue field inches. The stand-off is measured to the blue-hub station centre (its chassis action datum at 108, 158.85); the HUB centre is (182.1, 158.85), so both steps stand 2.70 m from the HUB centre.",
        comparison=pin("rehearsal/comparison.json"),
        outcome="With waitCycles yield and the shared partner deconfliction (0 permanent cycles), slot 2 credits 124 FUEL in both the baseline and the 2.70 m series, so the pose costs nothing; R3L credits 124 on the depot route and 40 on the TRENCH route (0 permanent cycles when it has the corridor alone). Pre-0.84 results were understated by permanent wait cycles.",
        heldReceipt={"file": f"{REL}/receipt-R3-PD1-held.json", "sha256": hashlib.sha256(held.read_bytes()).hexdigest()} if held.exists() else None))
    specs = [
        ("start-overhang", "mm", [-500.0, 0.5], "startOverhangMm", "Starting fold: nothing but bumpers outside the frame projection", "preliminary-design", ["intake", "climber hooks"], rules, "R102 no overhang in the starting configuration"),
        ("swept-height", "mm", [0.0, 762.0], "sweptTopMm", "Robot height in every operating and park pose", "preliminary-design", ["climber hooks", "intake", "hopper"], rules, "R104/R107 30 in, measured as if on a flat floor"),
        ("swept-front-extension", "mm", [-500.0, 304.8], "sweptFrontExtensionMm", "Front extension through every operating and park pose", "preliminary-design", ["intake", "climber hooks"], rules, "R105 12 in"),
        ("swept-other-extension", "mm", [-500.0, 0.5], "sweptOtherExtensionMm", "Rear and side extension through every operating and park pose", "preliminary-design", ["shooter", "climber hooks"], rules, "R106 one side at a time; only the front extends"),
        ("sides-extended", "sides", [0.0, 1.0], "sidesExtendedMax", "Sides extended at once in any sampled pose", "preliminary-design", ["intake", "climber hooks"], rules, "R106"),
        ("with-bumpers-mass", "kg", [0.0, 61.23], "withBumpersUpperKg", "Upper R103 estimate plus 7.5 kg bumpers", "preliminary-design", ["bumpers", "frame"], rules, "R408 135 lb"),
        ("hopper-capacity", "FUEL", [24.0, 200.0], "volumeEstimateDeployedLow", "Selected own-zone batch of 24 with the intake deployed, at a loose 0.45 packing fraction", "conceptual-design", ["hopper", "intake", "floor belts"], strategy, "24-piece serial batch"),
        ("start-capacity", "FUEL", [8.0, 200.0], "volumeEstimateStowedLow", "AUTO preload of eight in the starting fold, at a loose 0.45 packing fraction", "conceptual-design", ["hopper", "intake"], strategy, "Begin legally preloaded with at most eight"),
        ("shot-window", "m", [2.4, 3.6], "releaseDistanceM", "Release-to-HUB distance with an entry band under all drag and spin corners", "preliminary-design", ["shooter"], pin("ballistics.json"), "ballistics.json robust bands at 62 degrees start at 2.4 m"),
        ("delivery-pose", "in", [32.0, 49.0], "deliveryStandoffIn", HELD_SCENARIO, "conceptual-design", ["shooter", "drivetrain"], delivery_evidence, "Every B2 blue-hub attempt in the re-run series r3-2p7m stands 32.2004-48.6491 in from the station centre (AUTO step 32.2004, depot step 48.6491), inside 49 in (3 in within the 52 in release radius); the scenario text is the held R3-PD1 identity, whose 2.16 m refers to the original rehearsal; the step stands 2.70 m from the HUB centre and costs no FUEL against the deconflicted baseline (124 vs 124)"),
        ("delivery-hub-distance", "m", [2.6, 2.8], "deliveryPoseM", "Robot-centre distance from the HUB centre at every slot 2 delivery step in the re-run rehearsal", "conceptual-design", ["shooter", "drivetrain"], pin("rehearsal/comparison.json"), "The robust shot band at 62 degrees starts at 2.4 m release distance"),
        ("bump-crossing", "mm", [5.0, 500.0], "bumpCrossingClearanceMm", "Side-view BUMP crossing with the intake retracted: least clearance of any underside feature over the sharp 15 degree crest", "conceptual-design", ["frame", "drivetrain", "bumpers"], pin("bump_crossing.py"), "Accepted margin 5 mm over a conservative sharp crest; bump_crossing.py"),
        ("hang-bumper-overlap", "mm", [20.0, 200.0], "bumperUprightOverlapMm", "Lateral overlap of the bumper with each TOWER upright face while hanging", "preliminary-design", ["bumpers", "frame", "climber hooks"], rules, "Uprights 819.15 mm apart; a 20 mm overlap tolerates driver alignment error"),
    ]
    premises = []
    for pid, unit, rng, field_name, scen, phase, ifaces, src, basis in specs:
        identity = dict(id=pid, unit=unit, scenario=scen)
        extra = dict(fieldInput=field_input, repeat=dict(previousPlanSha256=held_plan)) if pid == "delivery-pose" else {}
        acc = write(f"premise-{ISSUE}-{pid}-accepted.json", dict(**identity, criterion={"range": rng}, phase=phase, interfaces=ifaces, source=src, basis=basis, **extra))
        cur = write(f"premise-{ISSUE}-{pid}-current.json", dict(**identity, value=measured[field_name], issue=ISSUE, designSha256=design["sha256"],
                                                          stepSha256=step["sha256"], source=current_src, valueField=field_name))
        premises.append(dict(accepted=acc, current=cur))

    narrative = {"file": "kickoff/selected-strategy.md", "sha256": hashlib.sha256((ROOT / "kickoff/selected-strategy.md").read_bytes()).hexdigest()}
    gates = "Verification gates are in verification-gates.json; the contract assigns physical performance, retention and actuator dynamics to their own commissioned evidence (docs/preliminary-design.md)."
    objectives = [
        ("AUTO: start with up to eight supported FUEL and score from a legal launch pose while the HUB is active", "represented",
         "The starting fold holds 36 or more FUEL by free volume (start-capacity premise); launch-wrap and flight cases carry a FUEL into the HUB opening from the 2.7 m pose that the re-run rehearsal credits in AUTO (delivery-pose premise). With Agent FRC 0.84 wait-cycle yield and the shared partner deconfliction, delivering from 2.70 m costs no FUEL: slot 2 credits 124 in both the baseline and R3 series (alliance totals 366 and 382). Pre-0.84 results (96 against 104) were understated by permanent wait cycles."),
        ("Inactive shift: collect and hold the next allocated stock from the DEPOT, OUTPOST or a partner", "represented",
         "acquire-* cases take a floor FUEL up the bumper face into the hopper; the acquisition physics trial captures it in 0.50 s; hopper-capacity is 36 or more by free volume."),
        ("Active shift: carry each FUEL from storage through one transfer into the HUB", "represented",
         "loaded-transit, index, launch-wrap and flight cases carry the tracked FUEL into the HUB cavity; the delivery physics trial scores from 6.70 to 7.10 m/s."),
        ("Active shift: sustain 2.00 FUEL/s to score 24 with stock ready by second 5", "represented",
         "Two pinch lanes; by calculation each lane feeds 3.9 FUEL/s at 0.6 m/s belt speed and 154 mm spacing, and the flywheel recovers a 2% speed drop in about 0.03 s on two motors, so the layout supplies 7.8 FUEL/s against 2.00. Bulk convergence without jams is gate G1. " + gates),
        ("Fallback: score the available batch when supply or traffic consumes the window and return to collecting", "represented",
         "The cycle is piece-count independent; the intake stays deployed in every operating case; the re-run rehearsal keeps the depot loop."),
        ("Traffic: remain in the own zone, keep possession through loaded driving and contact, and yield", "represented",
         "By geometry the front lip stands 77 mm above a floor FUEL's base, more than its 75 mm radius, so horizontal deceleration alone cannot roll it out; side and rear walls rise above the top layer; the open throat holds no counted FUEL. Loaded 0.5 g stops are gate G2. " + gates),
        ("Neutral collector alternative with two field crossings", "out-of-scope",
         "The coordinator selected the own-zone role. R3 keeps a BUMP crossing option (bump-crossing premise, 8.7 mm least clearance) with the intake retracted; the re-run TRENCH variant (R3L) credits fewer FUEL than the depot loop."),
        ("End game: Level 1 low-rung hang when its expected 10 points exceed the remaining FUEL service", "represented",
         "Cases reach, seat (2 mm required contact) and lift 70 mm; the 714 mm frame gives 23.9 mm of bumper overlap with each upright (hang-bumper-overlap premise); the hang physics trial holds 37.8 mm with the brake and fails without it. Jaw capture under lateral offset and the brake hold are gate G3. " + gates),
        ("AUTO Level 1 TOWER (15 points, two-robot cap)", "out-of-scope",
         "The strategy keeps the eight-FUEL AUTO objective; no joined AUTO climb evidence is sought in this layout."),
        ("Reserve the depot entrance and partner lane", "out-of-scope",
         "Alliance routing decision owned by the field rehearsal, independent of the robot layout."),
        ("Measurement: observe intake crossing, retained identity, release and downstream crossing on one timebase", "represented",
         "entry sensor at the front lip and pinch sensor at the flywheel lane are placed; the HUB counter is field equipment."),
    ]
    explain = component_explanations(shapes, groups_of)
    view = f"{REL}/review/package-motion.html"
    plan = dict(schema="agent-frc/preliminary-layout@1", issue=ISSUE, design=design, step=step, motion=motion, datum=datum,
                groups=groups, mounts=mounts, stages=stages, missingInputs=[],
                control=dict(case="launch-wrap", displaced="hood", moving=ball, offsetMm=[0, 0, 8],
                             basis="Raise the hood 8 mm, inside a plausible fabrication error, so its lip enters the undeformed FUEL path at the pinch"),
                cycle=cycle, view=view, budgets=budgets, premises=premises,
                narrativeReview=dict(source=narrative, objectives=[dict(objective=o, disposition=s, basis=b) for o, s, b in objectives]),
                presentation=dict(components=explain,
                                  required={"wheels": [n for n in shapes if "wheel azimuth" in n], "drive and steering actuators": [n for n in shapes if "module motors" in n],
                                            "control computer, power distribution, main disconnect and radio": ["electronics panel", "electronics panel left"],
                                            "supply": ["battery"], "game piece": [ball] + [n for n in shapes if n.startswith("FUEL stored")]},
                                  loadMembers={"drive": [n for n in shapes if "module" in n], "steer": [n for n in shapes if "module motors" in n],
                                               "intake": ["intake belt module", "intake top roller", "intake slide rail left", "intake slide rail right"], "indexer": ["floor belt main", "floor belt front", "indexer cleat"],
                                               "flywheel": ["flywheel motor left", "flywheel motor right", "flywheel"], "climber": hooks + G_("climber inner tubes") + ["climber winch"], "controls": ["electronics panel", "electronics panel left"]}))
    write("layout.json", plan)
    extras = dict(freeVolume=vol, capacity=dict(R3=dict(deployed=dep, stowed=stow), R3L=dict(deployed=low_dep, stowed=low_stow, constants={k_: kl[k_] for k_ in ("floor", "wall", "hook")})),
                  stored=stored, trackedPath=pts, flight=fly, inspectionKg=inspection, runningKg=running, sweep=sweep,
                  volumesMm3={n: round(volume(s), 1) for n, s in shapes.items()})
    write("package-facts.json", extras)
    print(json.dumps(dict(volume=vol, capacity={"R3": [len(dep), len(stow)], "R3L": [len(low_dep), len(low_stow)]}, flight=fly,
                          sweep=sweep, reach=deployed_reach, inspection=inspection, running=running), indent=1))
    if args.check:
        flags = ["--fail-fast"] if args.fail_fast else ["--require-checked", "--write-view"]
        if args.previous:
            flags += ["--previous", args.previous]
        view_path = ROOT / view
        if not args.fail_fast and view_path.exists():
            view_path.unlink()
        view_path.parent.mkdir(exist_ok=True)
        out = subprocess.run(["node", str(CLI), "preliminary-check", str(ROOT), rel("layout.json"), *flags], capture_output=True, text=True)
        sys.stderr.write(out.stderr)
        (HERE / ("receipt-partial.json" if args.fail_fast else "receipt.json")).write_text(out.stdout, encoding="utf-8", newline="\n")
        print("exit", out.returncode)


def component_explanations(shapes, groups_of):
    E = {}
    def put(names, purpose, rationale, category, material):
        for n in names:
            E[n] = dict(purpose=purpose, rationale=rationale, category=category, material=material)
    S = list(shapes)
    put([n for n in S if n.startswith("frame rail")], "Carry the drive corners, bumpers and every mechanism mount.",
        "The foundation's 680 mm length and module saddles carry forward; the frame widens to 714 mm (2788 mm perimeter) for hang overlap, so the side-rail saddle fits must be redrawn.", "structure", "6061-T6 2x1x0.125 in tube")
    put(["floor pan", "floor pan front tongue"], "Support the floor belts, battery tray and electronics.",
        "Sits 94 mm above the carpet; the BUMP crossing screen then leaves 24 mm at the belly and 8.7 mm at the front bumper corner.", "structure", "3 mm polycarbonate over aluminum stiffeners")
    put(["front lip"], "Keep floor-level FUEL from rolling out over the front rail.", "Its 170 mm top stands 2 mm above the floor-layer centres and 5 mm below the entering FUEL.", "structure", "3 mm aluminum")
    put([n for n in S if n.startswith("intake slide rail")], "Guide the intake carriage between the start fold and the pickup pose.",
        "A straight slide never sweeps beyond the 304.8 mm R105 reach; the fixed stage of the two-stage slide is drawn.", "structure", "Aluminum drawer-slide stage")
    put([n for n in S if n.startswith("climber tube mount")], "Carry the climber tubes and the hang load into the front rail.", "The hang reaction enters the frame next to the front modules.", "structure", "6 mm aluminum bracket")
    put([n for n in S if "wheel azimuth" in n], "Reserve the full steering sweep of each swerve wheel.",
        "A revolved envelope avoids animating an axisymmetric sweep and still bounds the wheel at any heading.", "drivetrain", "Supplier wheel; envelope only")
    put([n for n in S if "module body" in n], "Represent the swerve module plates and gearing.", "Four-module swerve is the project default and the foundation already fits the supplier tabs.", "drivetrain", "Supplier module")
    put([n for n in S if "module motors" in n], "Reserve the drive and steering motors above each module.", "Their height limits the lowest hopper layer at the corners.", "drivetrain", "Supplier motors")
    put([n for n in S if n.startswith("bumper")], "Protect the frame perimeter and back the intake pinch.", "The 48-168 mm zone and 76 mm section follow the foundation release; the front bumper face is the pinch backing, and its 866.15 mm width overlaps each TOWER upright by 23.9 mm.", "bumper", "Plywood backing, foam, fabric")
    put(["hopper wall left", "hopper wall right"], "Contain stacked FUEL up to 715 mm.", "Walls rise 85 mm above the top-layer centres so a stable stack stays inside.", "structure", "2 mm polycarbonate")
    put(["hopper front upper wall"], "Close the hopper front above the intake throat.", "It starts at 482 mm, above the slide's swept path and the stowed carriage.", "structure", "2 mm polycarbonate")
    put(["hopper rear wall"], "Separate stored FUEL from the spinning flywheel.", "Only the floor-level lane may reach the pinch; upper layers would double-feed or jam on the wheel top.", "structure", "2 mm polycarbonate")
    put(["floor belt main", "floor belt front"], "Move the bottom FUEL layer aft toward the flywheel pinch.", "Feeding straight from the floor removes the incumbent's vertical elevator transfer.", "mechanism", "Belt envelope; belt and rollers")
    put(["indexer cleat"], "Push one tracked FUEL along the floor lane into the pinch.", "A cleated belt gives a positive drive path that a free-piece test can meter.", "mechanism", "Urethane cleat on belt")
    put(["flywheel"], "Accelerate the FUEL against the hood.", "A 4 in floor-fed flywheel at 62 degrees enters from 2.4 to 3.6 m under every drag and spin corner; 0.006 kg m2 limits the speed drop per shot to about 1.6-2%.", "mechanism", "Aluminum hub, compliant tread")
    put(["hood"], "Guide the FUEL 62 degrees around the flywheel and release it at 62 degrees elevation.", "Its end stops 2 mm inside the rear perimeter, so the shooter never extends a second side.", "mechanism", "Formed aluminum with friction liner")
    put([n for n in S if "shooter side plate" in n], "Carry the flywheel bearings and hood.", "Plates stop 4 mm short of the rear modules and bound the two pinch lanes.", "structure", "6 mm aluminum plate")
    put(["flywheel motor left", "flywheel motor right"], "Drive the flywheel from both ends.", "Outboard of each side plate, clear of the battery, the panels and the rear modules.", "mechanism", "Brushless motor")
    put(["battery"], "Supply the robot bus.", "Standing on its end at the left side lets it lift straight out between the hook arm and rear wall.", "battery", "Sealed lead acid 12 V")
    put(["electronics panel", "electronics panel left"], "Hold power distribution, controller, radio, breaker and 15 motor controllers on both faces.", "The side strips are outside the floor lanes and reachable from above.", "electrical", "Polycarbonate panel")
    put(["entry sensor"], "Observe each FUEL crossing the intake lip.", "The strategy requires per-piece intake crossings on the match timebase.", "electrical", "Beam-break sensor")
    put(["pinch sensor"], "Observe each FUEL entering the flywheel lane.", "Separates retained identity from release for the counting requirement.", "electrical", "Beam-break sensor")
    put([n for n in S if n.startswith("climber tube ") and "mount" not in n], "Guide the telescoping hooks.", "Front corners above the modules give a straight load path into the frame for the hang.", "structure", "30 mm round aluminum tube")
    put(["climber winch"], "Retract both inner tubes by cable to lift the robot.", "One motor at the front top keeps both hooks synchronized; it must hold 625 N with power removed (F4).", "mechanism", "Gearmotor and spool envelope")
    put([n for n in S if n.startswith("climber inner tube")], "Telescope inside the outer tube to seat the hook and lift the robot 70 mm.",
        "A round tube lets the hook swing on top without the tube rotating in its guide; the swing actuator sits inside it.", "mechanism", "22 mm round aluminum tube")
    put([n for n in S if n.startswith("climber hook")], "Swing over the low rung, seat and lift the robot 70 mm.", "Stowed inside the perimeter for R106; a 180 degree inboard swing avoids a second-side extension.", "mechanism", "Aluminum tube and hook plate")
    put(["intake belt module"], "Lift a floor FUEL up the bumper face.", "A vertical belt 3 mm off the undeformed FUEL pinches it against the bumper inside the 304.8 mm reach; compression is a detailed-design setting.", "mechanism", "Belt module with internal motor")
    put(["intake top roller"], "Push the lifted FUEL aft over the bumper.", "Placed 3 mm above the FUEL at the top of the climb.", "mechanism", "2 in compliant wheels on hex shaft")
    put([n for n in S if n.startswith("intake carriage plate")], "Join the belt module and top roller to the slide.", "Plates at 262-272 mm pass between the 819 mm TOWER uprights so the intake can stay deployed during the climb.", "mechanism", "6 mm aluminum plate")
    put(["FUEL tracked"], "Follow one identifiable FUEL from the carpet into the HUB.", "Its undeformed path carries the custody, clearance and ballistic checks.", "game-piece", "Foam FUEL 150.114 mm, 0.203-0.227 kg")
    put([n for n in S if n.startswith("FUEL stored")], "Represent stored stock in the starting fold.", "Supported pockets from the deposition screen that stay clear of every commissioned path; capacity itself is the free-volume premise.", "game-piece", "Foam FUEL")
    put(["hub body", "hub top"], "Locate the HUB and its hexagonal opening.", "The flight cases must clear the near flat at 1828.8 mm and descend inside the conservative inscribed opening.", "field", "Field fixture (V0 dimensions)")
    put([n for n in S if n.startswith("tower upright")], "Locate the TOWER uprights.", "Their 819 mm gap bounds the intake and the bumper approach.", "field", "Field fixture (V0 dimensions)")
    put(["tower low rung"], "Locate the low rung at 685.8 mm.", "The hooks must seat on it; the V0 text centres it in the upright depth.", "field", "Field fixture (V0 dimensions)")
    put(["tower base"], "Locate the TOWER BASE plate.", "Level 1 requires clearing it; its 8 mm edge stands under the front bumper at the berth.", "field", "Field fixture (V0 dimensions)")
    missing = [n for n in shapes if n not in E]
    assert not missing, missing
    return E


if __name__ == "__main__":
    main()
