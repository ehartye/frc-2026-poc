"""Build the R3 preliminary package: placed STEP, motion study, budgets, premises and review plan.

Run from anywhere with the project geometry environment:
    python -I -B design/preliminary/build_package.py [--check] [--fail-fast]
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

ISSUE = "R3-PD1"
PLUGIN = Path(__import__("os").environ.get("AGENT_FRC", str(ROOT.parents[1] / "agent-frc")))
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
def capacity(variant, stowed, extra_exclusions=(), limit=None, avoid=(), xmax=236):
    """Greedy bottom-up placement of undeformed FUEL inside the hopper walls against every fixed robot solid."""
    bodies, k = G.robot_bodies(variant, intake_stowed=stowed)
    solids = [(n, s, bounds(s)) for n, (s, g) in bodies.items()]
    r, clear = G.R_BALL, 1.5
    zmax = k["wall"] - r
    xs = [x for x in range(-150, 237, 22)]
    ys = [y for y in range(-238, 239, 22)]
    zs = [k["z0"] + 22 * i for i in range(0, 40) if k["z0"] + 22 * i <= zmax]
    cands = sorted(((x, y, z) for z in zs for x in xs for y in ys), key=lambda p: (p[2], p[0], abs(p[1]), p[1]))
    placed = []
    for p in cands:
        if p[2] > k["z0"] + 10 and p[0] < -93 + r + clear:
            continue  # behind the rear wall only the floor-level pinch lane is hopper volume
        if abs(p[1]) > 316 - r - clear:
            continue
        if any(math.dist(p, q) < 2 * r + clear for q in placed):
            continue
        if p[0] > xmax or any(box_point_gap(b, p) < r + clear for b in extra_exclusions):
            continue
        if avoid and min(math.dist(p, q) for q in avoid) < 2 * r + 2:
            continue
        near = [s for n, s, b in solids if box_point_gap(b, p) < r + clear]
        if near:
            ball = G.sphere(p)
            if any(dist(ball, s) < clear for s in near):
                continue
        placed.append(p)
        if limit and len(placed) >= limit:
            break
    return placed, k


# ---------------------------------------------------------------- tracked FUEL path
def tracked_path(k):
    ip = G.intake_points()
    f, b = G.INTAKE["ramp_front"], G.INTAKE["ramp_back"]
    u, n, L, co = ip["u"], ip["n"], ip["length"], ip["centre_off"]
    y = 82.5
    zf = G.R_BALL + G.GAP
    s1 = (zf - f[1] - co * n[1]) / u[1]
    p = lambda s: (f[0] + s * u[0] + co * n[0], f[1] + s * u[1] + co * n[1])
    S0 = (770.0, zf); S1 = p(s1); S2 = p(L)
    crest = 82.0
    S3 = (b[0] + crest * math.cos(math.radians(67.5)), b[1] + crest * math.sin(math.radians(67.5)))
    S4 = (b[0], b[1] + crest)
    S5 = (140.0, S4[1])
    D = (140.0, k["z0"])
    pts = {k_: (x, y, z) for k_, (x, z) in dict(S0=S0, S1=S1, S2=S2, S3=S3, S4=S4, S5=S5, D=D).items()}
    return pts, ip


def circle(p, q, r):
    """Centre of the XZ circle through three points."""
    ax, az = p; bx, bz = q; cx, cz = r
    d = 2 * (ax * (bz - cz) + bx * (cz - az) + cx * (az - bz))
    ux = ((ax * ax + az * az) * (bz - cz) + (bx * bx + bz * bz) * (cz - az) + (cx * cx + cz * cz) * (az - bz)) / d
    uz = ((ax * ax + az * az) * (cx - bx) + (bx * bx + bz * bz) * (ax - cx) + (cx * cx + cz * cz) * (bx - ax)) / d
    return ux, uz


def flight(k, hub_x, segments=4, end_z=1.70):
    """Pick the speed in the entry window that lands nearest the HUB centre; approximate the path by circular arcs."""
    ex, ez = k["exit_point"]
    d = (ex - hub_x) / 1000
    mass, cd = 0.215, 0.47
    win = ballistics.window(G.EXIT_DEG, ez / 1000, d, mass, cd)
    assert win, "no entry window"
    best = None
    edges = [(hub_x + 1059.18 / 2 * math.cos(math.pi / 6), 1828.8), (hub_x - 1059.18 / 2 * math.cos(math.pi / 6), 1828.8)]
    scan = []
    for i in range(int(round((win[1] - win[0] + 0.4) / 0.01)) + 1):
        v = round(win[0] - 0.2 + 0.01 * i, 2)
        path = ballistics.fly(v, G.EXIT_DEG, ez / 1000, mass, cd)
        apex = max(range(len(path)), key=lambda j: path[j][2])
        if 1000 * path[apex][2] < 1828.8 + G.R_BALL:
            continue
        end = next(j for j in range(apex, len(path)) if path[j][2] <= end_z)
        xs = [(ex - 1000 * q[1], 1000 * q[2]) for q in path[:end + 1]]
        edge = min(math.dist(p, e) for p in xs for e in edges) - G.R_BALL
        miss = abs(xs[-1][0] - hub_x)
        inside = miss <= 1059.18 / 2 * math.cos(math.pi / 6) - G.R_BALL - 10
        scan.append(dict(speedMps=v, edgeClearanceMm=round(edge, 1), endOffsetMm=round(miss, 1), inside=inside))
        if inside and (best is None or edge > best[0]):
            best = (edge, v, path, end, miss)
    edge, v, path, end, miss = best
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
    return dict(speedMps=v, windowMps=win, distanceM=d, exitHeightM=ez / 1000, cd=cd, massKg=mass,
                flightS=path[end][0], endOffsetFromHubCentreMm=miss, rimEdgeClearanceMm=edge, speedScan=scan,
                acceptedSpeedBandMps=[min(r["speedMps"] for r in scan if r["inside"] and r["edgeClearanceMm"] >= 3),
                                      max(r["speedMps"] for r in scan if r["inside"] and r["edgeClearanceMm"] >= 3)],
                arcs=arcs, maxArcDeviationMm=err)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--fail-fast", action="store_true")
    args = ap.parse_args()

    bodies, k = G.robot_bodies("R3")
    groups_of = {n: g for n, (s, g) in bodies.items()}
    shapes = {n: s for n, (s, g) in bodies.items()}

    # Shot pose: HUB centre 2600 mm aft of the robot centre. Acquire pose is (400, 2000) in shot coordinates.
    hub_shot = (-2600.0, 0.0); tower_face_shot, tower_y_shot = 1025.0, -1250.0
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
    dep, _ = capacity("R3", False)
    stow, _ = capacity("R3", True)
    low_dep, kl = capacity("R3L", False)
    low_stow, _ = capacity("R3L", True)

    # Stored AUTO preload: positions valid in both intake poses and clear of every commissioned path.
    path_samples = []
    seq = [pts[x] for x in ("S0", "S1", "S2", "S3", "S4", "S5", "D")]
    for a, b in zip(seq, seq[1:]):
        for i in range(21):
            path_samples.append(tuple(a[j] + (b[j] - a[j]) * i / 20 for j in range(3)))
    cx, cz = k["c"]
    for i in range(41):
        path_samples.append((D[0] + (cx - D[0]) * i / 40, D[1], D[2]))
    columns = [(-90, 236, 83, 77, 312, 4000), (-342, -263, 80, -99, 190, 4000), (-73, 22.5, 91.5, 227, 142.5, 168.1)]
    stored, _ = capacity("R3", True, extra_exclusions=columns, avoid=path_samples, xmax=40, limit=7)
    assert len(stored) == 7, f"only {len(stored)} stored preload positions"
    for i, p in enumerate(stored, 1):
        shapes[f"FUEL stored {i}"] = G.sphere(p); groups_of[f"FUEL stored {i}"] = "stored FUEL"

    # ---------------------------------------------------------- STEP
    doc = TDocStd_Document(TCollection_ExtendedString("BinXCAF"))
    table = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    for name, s in shapes.items():
        TDataStd_Name.Set_s(table.AddShape(s, False), TCollection_ExtendedString(name))
    w = STEPCAFControl_Writer()
    assert w.Transfer(doc, STEPControl_AsIs) and w.Write(str(HERE / "package.step")) == IFSelect_RetDone
    step = pin("package.step")

    design_path = HERE / "design.json"
    if design_path.exists():
        design_path.unlink()
    subprocess.run(["node", str(CLI), "new", str(design_path)], check=True, stdout=subprocess.DEVNULL)
    d = json.loads(design_path.read_text(encoding="utf-8"))
    d["design"]["frameProfile"] = {"kind": "square"}
    d["design"]["parameters"].update(frameLengthM=0.68, frameWidthM=0.68, trackM=0.53, bumperBottomM=0.048,
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
             "floor indexer": "mechanism", "shooter": "mechanism", "intake": "mechanism", "intake pivot drive": "mechanism", "climber hooks": "mechanism", "climber inner tubes": "mechanism",
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

    pivot = (G.INTAKE["pivot"][0], 0, G.INTAKE["pivot"][1])
    intake = G_("intake")
    history.update({n: [ROT(pivot, (0, -1, 0), G.INTAKE_STOW_DEG)] for n in intake})
    ball = "FUEL tracked"
    P = lambda key: list(pts[key])
    off = lambda key: sub(P(key), list(D))
    history[ball] = [T(off("S0"))]

    case("intake-deploy", "operating", "Unfold the intake from its legal starting fold through 135 degrees to the floor pickup pose",
         {n: [ROT(pivot, (0, -1, 0), -G.INTAKE_STOW_DEG)] for n in intake}, ["intake"])
    for n in intake:
        history[n] = []  # the rotations cancel; continue from the installed deployed pose
    legs = [("acquire-approach", "S0", "S1", "Drive onto the FUEL; it reaches the ramp toe 3 mm clear of the carpet plane"),
            ("acquire-ramp", "S1", "S2", "The roller drives the FUEL up the 45 degree ramp with 3 mm undeformed reserve to ramp and roller"),
            ("acquire-crest-1", "S2", "S3", "First chord over the ramp's rear edge at 82 mm centre radius"),
            ("acquire-crest-2", "S3", "S4", "Second chord to the crest above the ramp's rear edge"),
            ("acquire-over", "S4", "S5", "Carry the FUEL over the bumper, front rail and lip into the hopper")]
    for cid, a, b, basis in legs:
        case(cid, "operating", basis, {ball: [T(sub(P(b), P(a)))]}, ["tracked FUEL"], initial={ball: [T(off(a))]})
    fall = pts["S5"][2] - D[2]
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
    case("launch-wrap", "operating", "The FUEL rolls 60 degrees around the flywheel against the hood and releases at 60 degrees elevation",
         {ball: [wrap]}, ["tracked FUEL"])
    hub_now = hub_shot
    ex, ez = k["exit_point"]
    for i, arc in enumerate(fly["arcs"], 1):
        c = arc["centreMm"]
        case(f"flight-{i}", "operating", f"Ballistic arc {i} of {len(fly['arcs'])} at {fly['speedMps']} m/s toward the HUB opening (prescribed; drag Cd {fly['cd']}; circular fit within {fly['maxArcDeviationMm']:.1f} mm)",
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
    reach = {"climber hook left": [ROT((300, 299, hz), (0, 0, 1), 180)], "climber hook right": [ROT((300, -299, hz), (0, 0, 1), -180)]}
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
    service("shooter-withdraw", "shooter", "Lift the flywheel, hood, side plates and motor out as one module")

    motion = write("paths.json", dict(schema="agent-frc/mechanical-motion@1", step=step, layoutDesignSha256=design["sha256"],
                                      layoutDatum=datum, cases=cases))

    mounts = [dict(group="floor belts", on="floor pan", pointMm=[0, 0, k["floor"]], basis="Belt bed rests on the floor pan"),
              dict(group="floor indexer", on="floor belt main", pointMm=[0, 82.5, k["belt_top"]], basis="Cleat rides the main belt"),
              dict(group="shooter", on="frame rail rear", pointMm=[-327, 0, 120.65], basis="Shooter side plates bolt to the rear rail top"),
              dict(group="intake", on="intake pivot mount left", pointMm=[322, 278, 279], basis="Pivot axle bearing on the mount top"),
              dict(group="intake pivot drive", on="intake pivot mount left", pointMm=[322, 274, 279], basis="Gearmotor flange on the inboard face of the pivot mount"),
              dict(group="climber inner tubes", on="climber tube left", pointMm=[300, 299, 500], basis="Inner tube runs in bushings in the fixed outer tube"),
              dict(group="climber hooks", on="climber inner tube left", pointMm=[300, 299, k["hook"] - 14], basis="Swing joint on the inner tube top")]

    # ---------------------------------------------------------- budgets
    requirements_cases = {}
    loads = {
        # battery-side ampere ranges per source in each stage (conservative bounds, see study)
        "intake-deploy": dict(drive=[10, 60], steer=[2, 8], intake=[5, 20], indexer=[0, 5], flywheel=[0, 5], climber=[0, 0], controls=[3, 6]),
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
        ("frame and floor", G_("frame"), [4.2, 5.4], "Four 2x1x0.125 in 6061 rails (2.72 m at 0.79 kg/m), 3 mm polycarbonate floor and lip, pivot mounts, gussets"),
        ("hopper walls", G_("hopper"), [1.6, 2.6], "Three 2 mm polycarbonate panels about 1.05 m2 at 1.2 g/cm3 plus edge stiffeners"),
        ("drivetrain", G_("drivetrain"), [8.5, 10.5], "Four MAXSwerve corners: 1.720 kg purchased assembly each (foundation reconciliation) plus drive and steering motors"),
        ("floor indexer", G_("floor belts") + G_("floor indexer"), [1.5, 2.3], "Two belt runs, rollers, cleats, one motor and gearbox"),
        ("shooter", G_("shooter"), [5.0, 6.8], "Flywheel shaft with 0.006 kg m2 inertia, hood, two side plates, two flywheel motors, bearings"),
        ("intake", G_("intake") + G_("intake pivot drive"), [2.4, 3.4], "Roller with internal motor, ramp, two arms and the coaxial pivot gearmotor"),
        ("climber", G_("climber tubes") + G_("climber inner tubes") + G_("climber hooks"), [2.6, 3.6], "Two telescoping tube pairs, hooks, winch motor, swing actuator"),
        ("electrical and controls", G_("electrical"), [3.8, 5.0], "Power distribution, controller, radio, 11 motor controllers, breaker, sensors, wiring"),
        ("bumpers (excluded by R103)", G_("bumpers"), [0.0, 0.0], "R103 excludes bumpers; 6.0-7.5 kg carried in the running payload and in the R408 check"),
        ("battery (excluded by R103)", G_("battery"), [0.0, 0.0], "R103 excludes the battery and its connector half; 5.6-6.2 kg carried in the running payload"),
        ("field fixtures (not robot)", field_m, [0.0, 0.0], "HUB and TOWER references are field equipment"),
        ("unmodeled robot hardware", [], [3.0, 5.0], "Fasteners, brackets, cable chain, camera and spares not yet drawn"),
    ]
    payload = [6.0 + 5.6 + 24 * 0.203, 7.5 + 6.2 + 24 * 0.227]
    inspection = [sum(r[2][0] for r in mass_rows), sum(r[2][1] for r in mass_rows)]
    running = [inspection[0] + payload[0], inspection[1] + payload[1]]
    for row in elec.values():
        row["loadedKg"] = running
    req = write("package-limits.json", dict(
        basis="V0 R103 inspection limit from construction-rules.json; roboRIO brownout near 6.75 V plus margin; per-duty minimums in the study",
        inspectionLimitKg=52.16, operatingMinV=7.0, massLines=[r[0] for r in mass_rows], electricalCases=requirements_cases))
    budgets = write("budgets.json", dict(issue=ISSUE, step=step, motion=motion, design=design, requirements=req,
        runningPayloadKg=payload,
        runningPayloadBasis="Bumpers 6.0-7.5 kg, battery 5.6-6.2 kg and 24 FUEL at 0.203-0.227 kg: all carried in the match but outside the R103 weighing",
        masses=[dict(id=i, members=m, kg=kg, basis=b) for i, m, kg, b in mass_rows], electricalCases=elec))

    # ---------------------------------------------------------- premises and measurements
    stowed_bodies, _ = G.robot_bodies("R3", intake_stowed=True)
    stowed_top = max(bounds(s)[5] for s, g in stowed_bodies.values())
    deployed_top = max(bounds(s)[5] for s, g in bodies.values())
    deployed_reach = max(bounds(s)[3] for s, g in bodies.values()) - 340.0
    measured = dict(issue=ISSUE, designSha256=design["sha256"], stepSha256=step["sha256"],
                    stowedTopMm=round(stowed_top, 3), deployedTopMm=round(deployed_top, 3), deployedReachMm=round(deployed_reach, 3),
                    capacityDeployed=len(dep), capacityStowed=len(stow), lowCapacityDeployed=len(low_dep), lowCapacityStowed=len(low_stow),
                    shotDistanceM=round(fly["distanceM"], 4), bellyClearanceMm=k["floor"] - 6.0,
                    basis="Measured from the solids written to package.step by build_package.py; capacity is a greedy 22 mm lattice placement of undeformed FUEL with 1.5 mm clearance")
    write("measurements.json", measured)
    current_src = pin("measurements.json")
    rules = pin("construction-rules.json")
    strategy = {"file": "kickoff/selected-strategy.json", "sha256": hashlib.sha256((ROOT / "kickoff/selected-strategy.json").read_bytes()).hexdigest()}
    premises = []
    specs = [
        ("stowed-start-height", "mm", [0.0, 762.0], "stowedTopMm", "Starting configuration with the intake folded", "preliminary-design", ["intake", "climber hooks"], rules, "R104/R107 30 in limit"),
        ("deployed-height", "mm", [0.0, 762.0], "deployedTopMm", "Operating configuration with hooks stowed", "preliminary-design", ["climber hooks", "hopper"], rules, "R107 30 in at all times"),
        ("intake-reach", "mm", [0.0, 304.8], "deployedReachMm", "Deployed intake beyond the front frame perimeter", "preliminary-design", ["intake"], rules, "R105 12 in extension"),
        ("hopper-capacity", "FUEL", [24.0, 200.0], "capacityDeployed", "Selected own-zone batch of 24 with the intake deployed", "conceptual-design", ["hopper", "intake", "floor belts"], strategy, "24-piece serial batch"),
        ("start-capacity", "FUEL", [8.0, 200.0], "capacityStowed", "AUTO preload of eight in the starting fold", "conceptual-design", ["hopper", "intake"], strategy, "Begin legally preloaded with at most eight"),
        ("shot-distance", "m", [1.6, 3.6], "shotDistanceM", "Delivery pose used by the field rehearsal (about 2.2 m from the HUB centre)", "conceptual-design", ["shooter"], strategy, "Ballistic study covers 1.6 to 3.6 m"),
        ("bump-breakover", "mm", [71.0, 500.0], "bellyClearanceMm", "BUMP crest crossing at 530 mm wheelbase needs 71 mm under the belly", "conceptual-design", ["frame", "drivetrain"], rules, "15 degree BUMP ramps meeting at the crest"),
    ]
    for pid, unit, rng, field_name, scen, phase, ifaces, src, basis in specs:
        identity = dict(id=pid, unit=unit, scenario=scen)
        val = measured[field_name]
        acc = write(f"premise-{pid}-accepted.json", dict(**identity, criterion={"range": rng}, phase=phase, interfaces=ifaces, source=src, basis=basis))
        cur = write(f"premise-{pid}-current.json", dict(**identity, value=float(val), issue=ISSUE, designSha256=design["sha256"],
                                                          stepSha256=step["sha256"], source=current_src, valueField=field_name))
        premises.append(dict(accepted=acc, current=cur))
    # the current observation must equal its source field exactly
    meas = json.loads((HERE / "measurements.json").read_text(encoding="utf-8"))
    for name in [p for p in meas if isinstance(meas[p], int) and not isinstance(meas[p], bool)]:
        meas[name] = float(meas[name])
    write("measurements.json", meas)
    current_src = pin("measurements.json")
    premises = []
    for pid, unit, rng, field_name, scen, phase, ifaces, src, basis in specs:
        identity = dict(id=pid, unit=unit, scenario=scen)
        acc = write(f"premise-{pid}-accepted.json", dict(**identity, criterion={"range": rng}, phase=phase, interfaces=ifaces, source=src, basis=basis))
        cur = write(f"premise-{pid}-current.json", dict(**identity, value=meas[field_name], issue=ISSUE, designSha256=design["sha256"],
                                                          stepSha256=step["sha256"], source=current_src, valueField=field_name))
        premises.append(dict(accepted=acc, current=cur))

    narrative = {"file": "kickoff/selected-strategy.md", "sha256": hashlib.sha256((ROOT / "kickoff/selected-strategy.md").read_bytes()).hexdigest()}
    objectives = [
        ("AUTO: start with up to eight supported FUEL and score from a legal launch pose while the HUB is active", "represented",
         "Seven stored preloads plus the tracked pocket fit the starting fold (start-capacity premise); launch-wrap and flight cases carry a FUEL into the HUB opening. AUTO route timing stays with the field rehearsal."),
        ("Inactive shift: collect and hold the next allocated stock from the DEPOT, OUTPOST or a partner", "represented",
         "acquire-* cases take a floor FUEL over the bumper into the hopper; hopper-capacity premise checks 24 with the intake deployed."),
        ("Active shift: move loaded and score 24 by the end of the shift (2.00 FUEL/s with stock ready by second 5)", "represented",
         "loaded-transit, index, launch-wrap and flight cases carry one FUEL through the single floor-to-flywheel transfer. The 24-piece rate depends on bulk feeding into two pinch lanes, recorded as open finding F1 with its bench test."),
        ("Fallback: score the available batch when supply or traffic consumes the window and return to collecting", "represented",
         "The cycle is piece-count independent; the intake stays deployed in every operating case."),
        ("Traffic: remain in the own zone, preserve possession during an interrupted crossing and yield", "represented",
         "Loaded-transit keeps stored FUEL inside walls that rise 85 mm above the top-layer centres; retention review R-6."),
        ("Neutral collector alternative with two field crossings", "out-of-scope",
         "The coordinator selected the own-zone role. R3 keeps a BUMP crossing option (bump-breakover premise) but its route is not commissioned here."),
        ("End game: Level 1 low-rung hang when its expected 10 points exceed the remaining FUEL service", "represented",
         "tower-lateral, tower-forward, climb-reach, climb-seat (required 2 mm seat contact) and climb-lift raise the robot 70 mm."),
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
                                            "control computer, power distribution, main disconnect and radio": ["electronics panel"],
                                            "supply": ["battery"], "game piece": [ball] + [n for n in shapes if n.startswith("FUEL stored")]},
                                  loadMembers={"drive": [n for n in shapes if "module" in n], "steer": [n for n in shapes if "module motors" in n],
                                               "intake": ["intake pivot drive", "intake roller"], "indexer": ["floor belt main", "floor belt front", "indexer cleat"],
                                               "flywheel": ["flywheel motor", "flywheel"], "climber": hooks + G_("climber inner tubes"), "controls": ["electronics panel"]}))
    write("layout.json", plan)
    extras = dict(capacity=dict(R3=dict(deployed=dep, stowed=stow), R3L=dict(deployed=low_dep, stowed=low_stow, constants={k_: kl[k_] for k_ in ("floor", "wall", "hook")})),
                  stored=stored, trackedPath=pts, flight=fly, inspectionKg=inspection, runningKg=running,
                  volumesMm3={n: round(volume(s), 1) for n, s in shapes.items()})
    write("package-facts.json", extras)
    print(json.dumps(dict(capacity={"R3": [len(dep), len(stow)], "R3L": [len(low_dep), len(low_stow)]}, flight=fly,
                          stowedTop=stowed_top, deployedTop=deployed_top, reach=deployed_reach, inspection=inspection, running=running), indent=1))
    if args.check:
        flags = ["--fail-fast"] if args.fail_fast else ["--require-checked", "--write-view"]
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
        "The verified 680 mm foundation outline is carried forward; its supplier-fit checks remain valid only at these rail positions.", "structure", "6061-T6 2x1x0.125 in tube")
    put(["floor pan", "floor pan front tongue"], "Support the floor belts, battery tray and electronics.",
        "Sits 75 mm above the carpet so the belly clears the 71 mm BUMP breakover requirement.", "structure", "3 mm polycarbonate over aluminum stiffeners")
    put(["front lip"], "Keep floor-level FUEL from rolling out over the front rail.", "It stays 14 mm below the entering FUEL path so the intake can feed over it.", "structure", "3 mm aluminum")
    put([n for n in S if "pivot mount" in n], "Carry the intake pivot axle above the front rail.", "A raised pivot lets the arms pass over the bumper and the intake fold within the start envelope.", "structure", "6 mm aluminum plate")
    put([n for n in S if "wheel azimuth" in n], "Reserve the full steering sweep of each swerve wheel.",
        "A revolved envelope avoids animating an axisymmetric sweep and still bounds the wheel at any heading.", "drivetrain", "Supplier wheel; envelope only")
    put([n for n in S if "module body" in n], "Represent the swerve module plates and gearing.", "Four-module swerve is the project default and the foundation already fits the supplier tabs.", "drivetrain", "Supplier module")
    put([n for n in S if "module motors" in n], "Reserve the drive and steering motors above each module.", "Their height limits the lowest hopper layer at the corners.", "drivetrain", "Supplier motors")
    put([n for n in S if n.startswith("bumper")], "Protect the frame perimeter.", "The bumper zone and 76 mm section follow the foundation release; covers use the alliance colors.", "bumper", "Plywood backing, foam, fabric")
    put(["hopper wall left", "hopper wall right"], "Contain four layers of FUEL up to 715 mm.", "Walls rise 85 mm above the top-layer centres so the load survives turning and contact.", "structure", "2 mm polycarbonate")
    put(["hopper rear wall"], "Separate stored FUEL from the spinning flywheel.", "Only the floor-level lane may reach the pinch; upper layers would double-feed or jam on the wheel top.", "structure", "2 mm polycarbonate")
    put(["floor belt main", "floor belt front"], "Move the bottom FUEL layer aft toward the flywheel pinch.", "Feeding straight from the floor removes the incumbent's vertical elevator transfer.", "mechanism", "Belt envelope; belt and rollers")
    put(["indexer cleat"], "Push one tracked FUEL along the floor lane into the pinch.", "A cleated belt gives a positive drive path that a free-piece test can meter.", "mechanism", "Urethane cleat on belt")
    put(["flywheel"], "Accelerate the FUEL against the hood.", "A 4 in floor-fed flywheel needs about 6.5-8.3 m/s exit speed from 1.6-3.6 m; inertia 0.006 kg m2 limits speed drop per shot to about 2%.", "mechanism", "Aluminum hub, compliant tread")
    put(["hood"], "Guide the FUEL 60 degrees around the flywheel and release it at 60 degrees elevation.", "A fixed hood with speed control covers the 1.6-3.6 m shot band without an adjustable hood joint.", "mechanism", "Formed aluminum with friction liner")
    put([n for n in S if "shooter side plate" in n], "Carry the flywheel bearings and hood.", "Plates stop 4 mm short of the rear modules and bound the two pinch lanes.", "structure", "6 mm aluminum plate")
    put(["flywheel motor"], "Drive the flywheel.", "Outboard of the right plate, clear of the battery and the rear module.", "mechanism", "Two brushless motors, one envelope")
    put(["battery"], "Supply the robot bus.", "Standing on its end at the left side lets it lift straight out between the hook arm and rear wall.", "battery", "Sealed lead acid 12 V")
    put(["electronics panel"], "Hold power distribution, controller, radio and motor controllers.", "The right side strip is outside the floor lanes and reachable from above.", "electrical", "Polycarbonate panel")
    put(["entry sensor"], "Observe each FUEL crossing the intake lip.", "The strategy requires per-piece intake crossings on the match timebase.", "electrical", "Beam-break sensor")
    put(["pinch sensor"], "Observe each FUEL entering the flywheel lane.", "Separates retained identity from release for the counting requirement.", "electrical", "Beam-break sensor")
    put([n for n in S if n.startswith("climber tube")], "Guide the telescoping hooks.", "Front corners above the modules give a straight load path into the frame for the hang.", "structure", "30 mm round aluminum tube")
    put([n for n in S if n.startswith("climber inner tube")], "Telescope inside the outer tube to seat the hook and lift the robot 70 mm.",
        "A round tube lets the hook swing on top without the tube rotating in its guide.", "mechanism", "22 mm round aluminum tube")
    put([n for n in S if n.startswith("climber hook")], "Swing over the low rung, seat and lift the robot 70 mm.", "Stowed inside the perimeter for R106; a 180 degree inboard swing avoids a second-side extension.", "mechanism", "Aluminum tube and hook plate")
    put(["intake ramp"], "Carry a floor FUEL up and over the bumper.", "A 45 degree ramp meets a floor FUEL at its centre height.", "mechanism", "3 mm polycarbonate")
    put(["intake roller"], "Drive the FUEL up the ramp.", "Placed 3 mm off the undeformed FUEL; compression is a detailed-design setting.", "mechanism", "3 in compliant wheels on hex shaft")
    put([n for n in S if n.startswith("intake arm")], "Carry the roller and ramp from the pivot.", "Arms pass between the 819 mm TOWER uprights so the intake can stay deployed during the climb.", "mechanism", "6 mm aluminum plate")
    put(["intake pivot drive"], "Rotate the intake between its starting fold and the floor pose.", "Coaxial with the pivot so it occupies no swept volume; the roller motor runs inside the roller. The outer 34 mm at each roller end is not a FUEL path.", "mechanism", "Gearmotor envelope")
    put(["FUEL tracked"], "Follow one identifiable FUEL from the carpet into the HUB.", "Its undeformed path carries the custody, clearance and ballistic checks.", "game-piece", "Foam FUEL 150.114 mm, 0.203-0.227 kg")
    put([n for n in S if n.startswith("FUEL stored")], "Hold the AUTO preload in the starting fold.", "Positions come from the capacity screen and stay clear of every commissioned path.", "game-piece", "Foam FUEL")
    put(["hub body", "hub top"], "Locate the HUB and its hexagonal opening.", "The flight cases must clear the near flat at 1828.8 mm and descend inside the conservative inscribed opening.", "field", "Field fixture (V0 dimensions)")
    put([n for n in S if n.startswith("tower upright")], "Locate the TOWER uprights.", "Their 819 mm gap bounds the intake and the bumper approach.", "field", "Field fixture (V0 dimensions)")
    put(["tower low rung"], "Locate the low rung at 685.8 mm.", "The hooks must seat on it; its position within the upright depth is an assumption.", "field", "Field fixture (V0 dimensions)")
    missing = [n for n in shapes if n not in E]
    assert not missing, missing
    return E


if __name__ == "__main__":
    main()
