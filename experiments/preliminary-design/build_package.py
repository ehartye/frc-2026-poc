"""Build the R3 preliminary package: placed STEP, field fixtures, motion study, budgets, premises and review plan.

Run from anywhere with the project geometry environment, after field_trials.py:
    python -I -B experiments/preliminary-design/field_trials.py
    python -I -B experiments/preliminary-design/build_package.py [--check] [--fail-fast] [--previous RECEIPT]
    python -I -B experiments/preliminary-design/build_package.py --release cad/preliminary-design/releases/layout-001 [--check]

Without --release the package is written beside this file and its pins are relative to the repository root.
With --release the same package is written into that directory as self-contained review inputs: every pin is
relative to the release directory, and the files the package pins are copied in.

The tracked FUEL's cases are not drawn here. They are fitted to the solved traces in field-trials.json
(trace_cases.py), so the package animation is the trial motion within the stated tolerance.
"""
import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
REPO = HERE.parents[1]

from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
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
from OCP.gp import gp_Pnt

import ballistics
import dimensions as D
import geometry as G
import trace_cases as TC

ISSUE = "R3-PD2"
PLUGIN = Path(__import__("os").environ["AGENT_FRC"])  # the Agent FRC plugin checkout; required
CLI = PLUGIN / "scripts" / "design.mjs"
TOL_MM = 1.5          # every FUEL stroke stays within this distance of its traced samples
BALL = "FUEL tracked"
PAYLOAD = "tracked FUEL"

# Output target, set by main(): OUT is the directory written, ROOT the project root its pins are relative to.
OUT, ROOT, REL = HERE, REPO, HERE.relative_to(REPO).as_posix()


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


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rel(name):
    return f"{REL}/{name}" if REL else name


def pin(name):
    return {"file": rel(name), "sha256": sha(OUT / name)}


def write(name, obj):
    (OUT / name).parent.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return pin(name)


def carry(name, source=None):
    """Make a pinned input available in the output directory. A release gets a copy; a copied JSON file's pins are
    re-rooted from this experiment folder to the release directory."""
    src = HERE / name if source is None else source
    if (OUT / name).resolve() != src.resolve():
        (OUT / name).parent.mkdir(parents=True, exist_ok=True)
        if name.endswith(".json") and source is None:
            text = src.read_text(encoding="utf-8").replace('"' + HERE.relative_to(REPO).as_posix() + "/", '"')
            (OUT / name).write_text(text, encoding="utf-8", newline="\n")
        else:
            shutil.copyfile(src, OUT / name)
    return pin(name)


def write_step(name, solids, title):
    doc = TDocStd_Document(TCollection_ExtendedString("BinXCAF"))
    table = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    for n, s in solids.items():
        TDataStd_Name.Set_s(table.AddShape(s, False), TCollection_ExtendedString(n))
    w = STEPCAFControl_Writer()
    assert w.Transfer(doc, STEPControl_AsIs) and w.Write(str(OUT / name)) == IFSelect_RetDone
    text = (OUT / name).read_text(encoding="utf-8")
    text = re.sub(r"FILE_NAME\('Open CASCADE Shape Model','[^']*'", f"FILE_NAME('{title}','2026-11-22T00:00:00'", text, count=1)
    (OUT / name).write_text(text, encoding="utf-8", newline="\n")
    return pin(name)


def T(v):
    return dict(kind="translation", travelMm=[float(x) for x in v])


def ROT(origin, axis, deg):
    return dict(kind="rotation", originMm=[float(x) for x in origin], axis=[float(x) for x in axis], travelDeg=float(deg))


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
            region = BRepAlgoAPI_Cut(region, s_).Shape()
        total += volume(region)
    vball = 4 / 3 * math.pi * G.R_BALL ** 3
    return dict(freeVolumeMm3=round(total, 0), ballVolumeMm3=round(vball, 0),
                estimateAtPacking={str(f): round(f * total / vball, 1) for f in (0.45, 0.50, 0.55)})


# ---------------------------------------------------------------- tracked FUEL path, from the trial traces
# Trial contact surface -> placed solid it stands for. The carpet is not a placed solid.
SOLID_OF = {"bumper face": "bumper front", "bumper top": "bumper front", "belt back run": "intake belt module",
            "belt front run": "intake belt module", "bottom pulley": "intake belt module", "top pulley": "intake belt module",
            "top roller": "intake top roller"}
INTAKE_SURFACES = ("belt back run", "belt front run", "bottom pulley", "top pulley", "top roller")


def load_trials():
    path = HERE / "field-trials.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["dimensions"]["sha256"] == sha(HERE / "dimensions.py") and data["rules"]["sha256"] == sha(HERE / "construction-rules.json"), \
        "field-trials.json was solved for other dimensions or rules: run field_trials.py first"
    return data, {t["name"]: t for t in data["trials"]}


def first_contact(trial, labels):
    return min((rows[0][0] for label, rows in trial["contacts"].items() if label in labels), default=None)


def last_contact(trial, labels):
    return max((rows[-1][1] for label, rows in trial["contacts"].items() if label in labels), default=None)


def peak_contacts(trial, t0, t1, pad=0.005):
    """Placed solid -> deepest traced indentation (mm) inside [t0, t1], for every solid touched within pad s of it."""
    out = {}
    for label, rows in trial["contacts"].items():
        solid = SOLID_OF.get(label, label)
        if solid == "carpet":
            continue
        for a, b, depth in rows:
            if b >= t0 - pad and a <= t1 + pad:
                inside = b >= t0 and a <= t1
                out[solid] = max(out.get(solid, 0.0), depth if inside else 0.0)
    return out


def fuel_strokes(trials):
    """The tracked FUEL's ordered strokes: [(phase, trial name, stroke, y)] with strokes in robot millimetres."""
    acq, entry, lch, dlv = (trials[n] for n in ("acquire-nominal", "entry-nominal", "launch-nominal", "deliver-nominal"))
    t_intake = first_contact(acq, INTAKE_SURFACES)
    t_roller = first_contact(acq, ("top roller",))
    t_thrown = last_contact(acq, INTAKE_SURFACES)
    t_belt = first_contact(entry, ("floor belt front", "floor belt main"))
    sch = lch["schedule"]
    plan = [
        (acq, 1, 2, [("acquire-approach", t_intake), ("acquire-climb", t_roller), ("acquire-over", t_thrown), ("acquire-throw", None)]),
        (entry, 1, 2, [("hopper-drop", t_belt), ("hopper-roll", None)]),
        (lch, 1, 2, [("launch-back-off", sch["backOffEndS"]), ("launch-coast", sch["feedStartS"]), ("launch-feed", sch["flywheelTakesS"]),
                     ("launch-wrap", None)]),
        (dlv, 1, 3, [("flight", None)]),
    ]
    out = []
    for trial, ix, iz, phases in plan:
        ends = [t for _, t in phases if t is not None]
        breaks = ends + [e["t"] for e in trial["events"]]
        for stroke in TC.fit(TC.side(trial["frames"], ix, iz), TOL_MM, breaks):
            mid = (stroke["fromS"] + stroke["toS"]) / 2
            phase = next(name for name, t in phases if t is None or mid < t)
            out.append((phase, trial["name"], stroke))
    # consecutive trials join on the same traced sample (to the 0.01 mm the traces are stored at)
    for (_, _, a), (_, _, b) in zip(out, out[1:]):
        assert math.dist(a["toMm"], b["fromMm"]) < 0.02, (a, b)
        b["fromMm"] = list(a["toMm"])
    return out


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


FIXTURE_BASIS = {
    "hub body": "Field fixture, FRC 2026 V0 HUB: 1193.8 mm square body 1777 mm tall with a 1059.18 mm circumscribed hexagonal opening (experiments/preliminary-design/geometry.py field_bodies). Nominal planning solid, not the official field model. Placed in the robot datum with the HUB centre at (-3100, -2000) mm for the acquire pose (2.7 m shot offset less the acquire offset); cases move it with the robot-relative field motion.",
    "hub top": "Field fixture, FRC 2026 V0 HUB top plate: 1193.8 mm square from 1779 to 1828.8 mm with the same hexagonal opening (geometry.py field_bodies). Placed with the HUB body.",
    "tower base": "Field fixture, FRC 2026 V0 TOWER BASE: 39.0 x 45.18 in plate, 8 mm edges, front edge 4.6 mm ahead of the uprights (geometry.py field_bodies). Placed with the TOWER face at x = 625 mm, centre y = -3250 mm for the acquire pose; tower cases move it.",
    "tower low rung": "Field fixture, FRC 2026 V0 TOWER low rung: 42.164 mm tube at 685.8 mm centre height spanning the 819.15 mm upright gap (geometry.py field_bodies). Placed with the TOWER.",
    "tower upright left": "Field fixture, FRC 2026 V0 TOWER upright: 88.9 x 38.1 mm section, 9.5 to 1831.3 mm (geometry.py field_bodies). Placed with the TOWER.",
    "tower upright right": "Field fixture, FRC 2026 V0 TOWER upright: 88.9 x 38.1 mm section, 9.5 to 1831.3 mm (geometry.py field_bodies). Placed with the TOWER.",
}
ALLOWANCE = ("1 mm preliminary reserve between unrelated solids. Where a physics trial solved the tracked FUEL against a surface, that pair is "
             "declared as payload compression with the trial's indentation as its limit. Stored FUEL keep a 3 mm undeformed reserve; "
             "separately listed joints are drawn with at least 1.5 mm splits")
PHASE = {
    # phase: (what happens, electrical duty, transporting mechanisms and their imposed drives, or None)
    "acquire-approach": ("The robot drives onto the floor FUEL; it rolls on the carpet toward the intake", "acquire", None),
    "acquire-climb": ("The bottom pulley draws the FUEL under the belt and the back run lifts it up the bumper face", "acquire",
                      {"intake": "Belt and top roller surfaces at {u} m/s, imposed in the trial; the carriage is deployed and stationary"}),
    "acquire-over": ("The top roller pushes the FUEL aft off the top of the climb", "acquire",
                     {"intake": "Belt and top roller surfaces at {u} m/s, imposed in the trial; the carriage is deployed and stationary"}),
    "acquire-throw": ("Thrown by the top roller, the FUEL flies over the bumper top and inside the frame", "acquire", None),
    "hopper-drop": ("The captured FUEL leaves the top roller and falls past the front lip toward the floor belts", "acquire", None),
    "hopper-roll": ("The FUEL lands on the stopped floor belts and rolls aft on its capture momentum to the stopped flywheel", "acquire", None),
    "launch-back-off": ("The floor belt backs the seated FUEL off the stopped flywheel", "launch",
                        {"floor belts": "Floor belt surface reversed at {back} m/s for {back_s} s, imposed in the trial"}),
    "launch-coast": ("The belt is stopped while the flywheel spins up; the FUEL coasts on clear of the wheel", "launch", None),
    "launch-feed": ("The floor belt feeds the FUEL to the spinning flywheel", "launch",
                    {"floor belts": "Floor belt surface at {feed} m/s toward the flywheel, imposed in the trial"}),
    "launch-wrap": ("The flywheel takes the FUEL, rolls it up the hood and releases it", "launch",
                    {"floor belts": "Floor belt surface at {feed} m/s toward the flywheel, imposed in the trial",
                     "shooter": "Flywheel surface held at {wheel} m/s, imposed in the trial; the model does not slow the wheel under load"}),
    "flight": ("Free flight from the hood release into the HUB", "launch", None),
}
ENVELOPE = re.compile(r"envelope|sweep|reserve|loom|trunk|lead|housing|module body|module motors|electronics panel|"
                      r"battery tray|dressed battery|plug and bracket|steer|azimuth|cassettes|sills|trusses|perimeter|"
                      r"field|hub |tower |trough|bumper|SPARK MAX|radio|roboRIO|distribution|breaker|reducer|motor|winch|belt module|servo|switch|sensor", re.I)


def main():
    global OUT, ROOT, REL
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", help="write self-contained review inputs into this directory (repository-relative)")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--fail-fast", action="store_true")
    ap.add_argument("--previous", help="held checkpoint receipt, project-relative")
    ap.add_argument("--receipt", help="with --release --check: where to save the scratch receipt")
    args = ap.parse_args()
    release = bool(args.release)
    if release:
        OUT = (REPO / args.release).resolve()
        ROOT, REL = OUT, ""
        OUT.mkdir(parents=True, exist_ok=True)

    bodies, k = G.robot_bodies("R3")
    groups_of = {n: g for n, (s, g) in bodies.items()}
    shapes = {n: s for n, (s, g) in bodies.items()}

    # Shot pose: HUB centre 2700 mm aft of the robot centre. Acquire pose is (400, 2000) in shot coordinates.
    hub_shot = (-2700.0, 0.0); tower_face_shot, tower_y_shot = 1025.0, -1250.0
    acq = (400.0, 2000.0)
    field = G.field_bodies(k, (hub_shot[0] - acq[0], hub_shot[1] - acq[1]), tower_face_shot - acq[0], tower_y_shot - acq[1])
    for n, s in field.items():
        shapes[n] = s; groups_of[n] = "field"

    # ---------------------------------------------------------- the tracked FUEL, from the solved traces
    trial_data, trials = load_trials()
    trials_pin = carry("field-trials.json")
    for stale in (OUT / "transport").glob("*.json"):   # every record is rewritten below
        stale.unlink()
    strokes = fuel_strokes(trials)
    Y = D.TRACK_Y
    xz = lambda p: (p[0], Y, p[1])
    start = xz(strokes[0][2]["fromMm"])
    seat = xz(next(s for ph, _, s in reversed(strokes) if ph == "hopper-roll")["toMm"])   # at rest against the stopped flywheel
    release_mm = next(s for ph, _, s in strokes if ph == "flight")["fromMm"]
    rel_state = trial_data["chain"]["release"]
    # Installed (STEP) pose: where the mission finds it, on the carpet ahead of the intake. The service cases start from
    # the installed scene, so they are checked with the floor lane empty.
    shapes[BALL] = G.sphere(start); groups_of[BALL] = PAYLOAD

    # Capacity, with the tracked piece's lane kept clear of the stored set.
    vol = {v: {st: free_volume(v, st == "stowed") for st in ("deployed", "stowed")} for v in ("R3", "R3L")}
    dep, _ = capacity("R3", False)
    stow, _ = capacity("R3", True)
    low_dep, kl = capacity("R3L", False)
    low_stow, _ = capacity("R3L", True)

    # Stored AUTO preload: stable positions in the starting fold, clear of the slide sweep and every traced FUEL position.
    path_samples = []
    for name in ("acquire-nominal", "entry-nominal", "launch-nominal"):
        for f in trials[name]["frames"]:
            q = (1000 * f[1], Y, 1000 * f[2])
            if not path_samples or math.dist(q, path_samples[-1]) >= 10.0:
                path_samples.append(q)
    columns = [(-90, 236 + G.DY, 83, 77, 312 + G.DY, 4000), (-342, -263, 80, -99, 190, 4000), (170, -275, 150, 620, 275, 500)]
    stored = supported_positions("R3", True, extra_exclusions=columns, avoid=path_samples, limit=7)
    assert len(stored) >= 2, f"only {len(stored)} supported stored positions"
    for i, p in enumerate(stored, 1):
        shapes[f"FUEL stored {i}"] = G.sphere(p); groups_of[f"FUEL stored {i}"] = "stored FUEL"

    # ---------------------------------------------------------- STEP: the robot package and the field fixtures
    field_m = sorted(field)
    step = write_step("package.step", {n: shapes[n] for n in sorted(shapes) if n not in field}, "R3-PD2 package")
    fixture_pin = write_step("field-fixtures.step", {n: shapes[n] for n in field_m}, "R3-PD2 field fixtures")
    fixtures = [dict(id=n, file=fixture_pin, solid=n, basis=FIXTURE_BASIS[n]) for n in field_m]

    design_path = OUT / "design.json"
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
    roles = {"frame": "structure", "hopper": "structure", "climber tubes": "structure", "battery retention": "structure", "bumpers": "bumper",
             "drivetrain": "drive", "battery": "battery", "electrical": "other", "floor belts": "mechanism",
             "shooter": "mechanism", "intake": "mechanism", "climber hooks": "mechanism", "climber inner tubes": "mechanism",
             "tracked FUEL": "payload", "stored FUEL": "payload", "field": "other"}
    groups = {g: dict(role=r, members=sorted(n for n, gg in groups_of.items() if gg == g)) for g, r in roles.items()}
    assert set(groups_of.values()) == set(roles), set(groups_of.values()) ^ set(roles)
    G_ = lambda g: groups[g]["members"]

    # ---------------------------------------------------------- cases
    history = {n: [] for n in shapes}
    cases, stages, fuel_index = [], {}, []

    def case(cid, stage, basis, moves, moving_groups, carried=None, initial=None, extra=None, transported=None):
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
        c["fixtures"] = fixtures
        cases.append(c)
        stages[cid] = dict(purpose=stage, movingGroups=moving_groups, carriedWith=carried or {}, allowanceBasis=ALLOWANCE)
        if transported:
            stages[cid]["transportedBy"] = transported
        for n, ops in moves.items():
            history[n] = (initial.get(n) if initial and n in initial else history[n]) + ops
        if initial:
            for n, v in initial.items():
                if n not in moves:
                    history[n] = v
        return c

    def vertex(p):
        return BRepBuilderAPI_MakeVertex(gp_Pnt(*p)).Vertex()

    def resting_rules(centre, solids, where):
        """Compression rules for a FUEL standing still against placed solids in their installed pose."""
        rules = []
        q = vertex(centre)
        for n in solids:
            depth = G.R_BALL - dist(q, shapes[n])
            if depth > -1.5:   # closer than the reserve a moving case would need
                assert depth < 1.0, (n, depth)
                rules.append(dict(payload=BALL, contact=n, maxDepthMm=round(max(depth, 0.0) + 0.5, 3),
                                  basis=f"The FUEL rests against this surface {where}: {max(depth, 0.0):.3f} mm indentation in the trial's penalty "
                                        "contact (15 kN/m estimate, not a measured force-deflection curve), plus 0.5 mm"))
        return rules

    intake = G_("intake")
    shift = list(G.INTAKE["shift"])
    history.update({n: [T([-v for v in shift])] for n in intake})

    case("intake-deploy", "operating", f"Slide the intake carriage {shift[0]:g} mm forward and {-shift[2]:g} mm down from the legal start fold, over the bumper",
         {n: [T(shift)] for n in intake}, ["intake"])
    for n in intake:
        history[n] = []  # the translations cancel; continue from the installed deployed pose

    acq_p, lch_p = trials["acquire-nominal"]["params"], trials["launch-nominal"]["params"]
    drive_values = dict(u=acq_p["u"], back=lch_p["backMps"], back_s=lch_p["backS"], feed=lch_p["feedMps"], wheel=lch_p["wheelMps"])
    counts, phase_cases, duty_of = {}, {}, {}
    for index, (phase, trial_name, stroke) in enumerate(strokes):
        what, duty, transporters = PHASE[phase]
        counts[phase] = counts.get(phase, 0) + 1
        cid = f"{phase}-{counts[phase]}"
        phase_cases.setdefault(phase, []).append(cid)
        duty_of[cid] = duty
        trial = trials[trial_name]
        window = f"{trial_name} {stroke['fromS']:.4f}-{stroke['toS']:.4f} s"
        shape_word = dict(line="straight stroke", arc="circular arc", drop="translation with a quadratic drop")[stroke["kind"]]
        support = ("moved by contact with " + " and ".join(sorted(transporters)) if transporters else
                   "no mechanism moves it here, so the stroke has no transportedBy and stands on the pinned trace alone")
        basis = (f"{what}. A {shape_word} fitted to the solved trace {window} of field-trials.json, within {stroke['deviationMm']:.2f} mm of every "
                 f"traced sample (limit {TOL_MM} mm); {support}")
        ops = TC.ops(stroke, Y)
        peaks = peak_contacts(trial, stroke["fromS"], stroke["toS"])
        if index and strokes[index - 1][1] != trial_name:   # the surfaces the previous trial ended on are still beside the FUEL
            before = trials[strokes[index - 1][1]]
            for solid in peak_contacts(before, before["frames"][-1][0], before["frames"][-1][0]):
                peaks.setdefault(solid, 0.0)
        chord = math.dist(stroke["fromMm"], stroke["toMm"])
        travel = (abs(stroke["sweepRad"]) * math.dist(stroke["fromMm"], stroke["centre"]) if stroke["kind"] == "arc" else
                  chord + 2 * stroke["fallMm"] if stroke["kind"] == "drop" else chord)
        margin = 0.2 + travel / 30000          # the sweep certifies intervals of travel / 2^16
        rules = [dict(payload=BALL, contact=solid, maxDepthMm=math.ceil((depth + stroke["deviationMm"] + margin) * 100) / 100,
                      basis=f"{window}: {depth:.2f} mm deepest indentation into this surface in that window of the trial's penalty contact (15 kN/m "
                            f"estimate, not a measured force-deflection curve), plus the {stroke['deviationMm']:.2f} mm stroke fit and a "
                            f"{margin:.2f} mm sweep margin")
                 for solid, depth in sorted(peaks.items())]
        init_before = list(history[BALL])
        transported = None
        if transporters:
            record = dict(schema="frc-2026-poc/contact-transport-trial@1", issue=ISSUE,
                          transport=dict(case=cid, payload=PAYLOAD, mechanisms=sorted(transporters), moves={BALL: ops}, initialPose={BALL: init_before}),
                          fieldTrials=trials_pin,
                          trial=dict(name=trial_name, fromS=stroke["fromS"], toS=stroke["toS"], fromPoseMm=list(xz(stroke["fromMm"])),
                                     toPoseMm=list(xz(stroke["toMm"])), stroke=stroke["kind"], maxDeviationMm=round(stroke["deviationMm"], 4),
                                     toleranceMm=TOL_MM, peakIndentationMm={s_: round(v, 3) for s_, v in sorted(peaks.items())}),
                          basis=basis)
            evidence = write(f"transport/{cid}.json", record)
            transported = {PAYLOAD: dict(mechanisms=sorted(transporters), drive={m: t.format(**drive_values) for m, t in transporters.items()},
                                         evidence=evidence, basis=what)}
        case(cid, "operating", basis, {BALL: ops}, [PAYLOAD], extra=dict(payloadCompression=rules, maxDepth=16) if rules else None,
             transported=transported)
        fuel_index.append(dict(case=cid, phase=phase, trial=trial_name, fromS=stroke["fromS"], toS=stroke["toS"], stroke=stroke["kind"],
                               maxDeviationMm=round(stroke["deviationMm"], 4), transportedBy=sorted(transporters) if transporters else None,
                               compression={r["contact"]: r["maxDepthMm"] for r in rules}))
        if phase.startswith("hopper") and strokes[index + 1][0].startswith("launch"):
            seat_rules = resting_rules(seat, ["floor belt main", "flywheel"], "in the seat")
            transit = (acq[0], acq[1], 0)
            case("loaded-transit", "operating", "Drive loaded from the DEPOT side of the alliance zone to the shot pose (robot frame: the field moves)",
                 {n: [T(transit)] for n in field_m}, ["field"], extra=dict(payloadCompression=seat_rules))
    last_flight = phase_cases["flight"][-1]
    seated_case = phase_cases["hopper-roll"][-1]
    world = field_m + [BALL]
    case("tower-lateral", "operating", "Drive sideways to the TOWER line",
         {n: [T((0, -tower_y_shot, 0))] for n in world}, ["field", PAYLOAD])
    approach = -(tower_face_shot - 417.5 - 5.0)
    case("tower-forward", "operating", "Close to 5 mm from the uprights with the deployed intake between them",
         {n: [T((approach, 0, 0))] for n in world}, ["field", PAYLOAD])
    hooks = G_("climber hooks")
    hz = k["hook"] - 6
    yc = 299 + G.DY
    reach = {"climber hook left": [ROT((300, yc, hz), (0, 0, 1), 180)], "climber hook right": [ROT((300, -yc, hz), (0, 0, 1), -180)]}
    case("climb-reach", "operating", "Swing both hooks 180 degrees inboard above the rung so the jaws pass beyond it", reach, ["climber hooks"])
    rung_top = 685.8 + 42.164 / 2
    seat_drop = -(k["hook"] - 12 - (rung_top + 1.5))
    case("climb-seat", "operating", "Lower the hooks onto the low rung; a 2 mm seat contact is required at the end of the stroke",
         {n: [T((0, 0, seat_drop))] for n in hooks + G_("climber inner tubes")}, ["climber hooks", "climber inner tubes"],
         extra={"requiredContacts": [dict(id=f"{side} hook seats on low rung", pair=[f"climber hook {side}", "tower low rung"],
                                          criterion="Hook arm underside within 2 mm of the rung top", maxGapMm=2.0, window=[0.9, 1.0])
                                     for side in ("left", "right")]})
    lift = 70.0
    case("climb-lift", "operating", "Retract the hooks 70 mm; in the robot frame the field and hooks move down together (Level 1 clears carpet and base)",
         {n: [T((0, 0, -lift))] for n in hooks + G_("climber inner tubes") + world}, ["climber hooks", "climber inner tubes", "field", PAYLOAD])
    case("park-lower", "park", "After the match, lower the robot back to the carpet",
         {n: [T((0, 0, lift))] for n in hooks + G_("climber inner tubes") + world}, ["climber hooks", "climber inner tubes", "field", PAYLOAD])
    cycle = [c["id"] for c in cases]

    def service(cid, group, basis):
        mv = {n: [T((0, 0, 2000))] for n in G_(group)}
        c = dict(id=cid, stage="service", basis=basis, moves=mv, minGapMm=1.0, extract=sorted(mv), checkLinearEnvelope=True, fixtures=fixtures)
        cases.append(c)
        stages[cid] = dict(purpose="service", movingGroups=[group], carriedWith={},
                           allowanceBasis="1 mm preliminary reserve during withdrawal")
    service("battery-withdraw", "battery", "Lift the battery straight out through the open hopper with the intake deployed and hooks stowed; the 2 m stroke passes the field fixtures' envelope used by the checker")
    service("shooter-withdraw", "shooter", "Lift the flywheel, hood, side plates and both motors out as one module, with the floor lane empty: a FUEL seated against the flywheel stands over the hood's lower lip and blocks the lift")

    motion = write("paths.json", dict(schema="agent-frc/mechanical-motion@1", step=step, layoutDesignSha256=design["sha256"],
                                      layoutDatum=datum, cases=cases))

    mounts = [dict(group="floor belts", on="floor pan", pointMm=[0, 0, k["floor"]], basis="Belt bed rests on the floor pan"),
              dict(group="shooter", on="frame rail rear", pointMm=[-327, 0, 120.65], basis="Shooter side plates bolt to the rear rail top"),
              dict(group="intake", on="intake slide rail left", pointMm=[300, 278, 400], basis="Carriage plates run on the two-stage slide; the fixed stage is drawn"),
              dict(group="climber inner tubes", on="climber tube left", pointMm=[300, 299 + G.DY, 500], basis="Inner tube runs in bushings in the fixed outer tube"),
              dict(group="climber hooks", on="climber inner tube left", pointMm=[300, 299 + G.DY, k["hook"] - 14], basis="Swing joint on the inner tube top"),
              dict(group="battery", on="battery retention cleat aft", pointMm=[-95.0, 291.0, 150.0],
                   basis="Battery end face captured between the aft and fore cleats; hold-down strap over the top is undesigned"),
              dict(group="battery retention", on="floor pan", pointMm=[-95.0, 291.0, 100.0],
                   basis="Cleat feet riveted to the floor pan top, which rests on the frame rails")]

    # ---------------------------------------------------------- budgets
    requirements_cases = {}
    loads = {
        # battery-side ampere ranges per source in each stage (conservative bounds, see study)
        "intake-deploy": dict(drive=[10, 60], steer=[2, 8], intake=[5, 25], indexer=[0, 5], flywheel=[0, 5], climber=[0, 0], controls=[3, 6]),
        "acquire": dict(drive=[20, 90], steer=[2, 10], intake=[10, 30], indexer=[2, 10], flywheel=[0, 5], climber=[0, 0], controls=[3, 6]),
        "loaded-transit": dict(drive=[50, 100], steer=[3, 12], intake=[0, 10], indexer=[0, 5], flywheel=[5, 30], climber=[0, 0], controls=[3, 6]),
        "launch": dict(drive=[0, 40], steer=[0, 6], intake=[0, 10], indexer=[5, 15], flywheel=[20, 60], climber=[0, 0], controls=[3, 6]),
        "tower": dict(drive=[20, 90], steer=[2, 10], intake=[0, 2], indexer=[0, 2], flywheel=[0, 5], climber=[0, 2], controls=[3, 6]),
        "climb": dict(drive=[0, 10], steer=[0, 4], intake=[0, 2], indexer=[0, 2], flywheel=[0, 2], climber=[10, 45], controls=[3, 6]),
        "park": dict(drive=[0, 5], steer=[0, 2], intake=[0, 2], indexer=[0, 2], flywheel=[0, 2], climber=[5, 20], controls=[3, 6]),
    }
    stage_load = {"intake-deploy": "intake-deploy", "loaded-transit": "loaded-transit", "tower-lateral": "tower", "tower-forward": "tower",
                  "climb-reach": "climb", "climb-seat": "climb", "climb-lift": "climb", "park-lower": "park", **duty_of}
    need = {"launch": 8.0, "loaded-transit": 7.5, "tower": 7.5, "climb": 7.5, "acquire": 7.5, "intake-deploy": 7.5, "park": 7.0}
    sources = ["drive", "steer", "intake", "indexer", "flywheel", "climber", "controls"]
    lch_demand = trials["launch-nominal"]["wheelDemand"]
    belt_w = trials["acquire-nominal"]["beltDemand"]["maxFrictionPowerW"]
    duty_note = {
        "acquire": f". The intake's 30 A is its supply limit; the acquisition trial's contacts dissipate up to {belt_w:.0f} W at the imposed belt speed, "
                   "so the belt slows under that peak unless the limit rises (gate G4)",
        "launch": f". The flywheel row covers the imposed {lch_p['spinS']:g} s spin-up: {lch_demand['spinUpPeakW']:.0f} W peak for the 0.006 kg m2 wheel, "
                  f"which is {lch_demand['spinUpPeakW'] / 0.85 / 8.338:.0f} A at the 8.34 V weak-pack launch bus with 85% drive efficiency (the efficiency is an assumption). "
                  f"The {lch_demand['peakFrictionPowerW']:.0f} W friction peak during a shot is drawn from the wheel's inertia",
    }
    elec = {}
    for cid in cycle:
        key = stage_load[cid]
        for cond, voc, res in (("nominal", [12.4, 12.8], [0.012, 0.016]), ("weak", [11.9, 12.2], [0.020, 0.026])):
            requirements_cases[f"{cid}-{cond}"] = dict(stage=cid, batteryCondition=cond, sources=sources,
                                                       duty=f"{key} duty during {cid}", requiredMotionMinV=need[key])
            elec[f"{cid}-{cond}"] = dict(basis=f"Simultaneous battery-side bounds for the {key} duty with supply current limits (drive 25 A per module battery-side)" + duty_note.get(key, ""),
                                         loadedKg=None, batterySideA=loads[key], openCircuitV=voc, resistanceOhm=res)
    # Shooter: a wheel with the stated inertia cannot weigh less than I / r^2; the plates and hood are the drawn aluminum.
    inertia, r_wheel = D.SHOOTER["inertia_kgm2"], D.FLYWHEEL_R / 1000
    wheel_kg = [inertia / (r_wheel ** 2 * 0.85), inertia / (r_wheel ** 2 * 0.65)]   # rim-heavy tube to thick-walled tube
    plates_kg = sum(volume(shapes[n]) for n in G_("shooter") if "side plate" in n) / 1e6 * 2.70
    hood_kg = volume(shapes["hood"]) / 1e6 * 2.70
    shooter_kg = [math.floor((wheel_kg[0] + 0.6 * plates_kg + hood_kg + 0.9 + 0.3) * 10) / 10,
                  math.ceil((wheel_kg[1] + plates_kg + hood_kg + 1.2 + 0.6) * 10) / 10]
    shooter_basis = (f"Flywheel with {inertia} kg m2 on a {D.FLYWHEEL_R} mm radius: {wheel_kg[0]:.2f}-{wheel_kg[1]:.2f} kg (a tube with 85% to 65% of its "
                     f"mass at the rim; I / r2 is the floor). Two 6 mm aluminum side plates {plates_kg:.2f} kg as drawn, 60% of that if lightened. "
                     f"Hood {hood_kg:.2f} kg. Two flywheel motors 0.9-1.2 kg. Shaft, bearings and fasteners 0.3-0.6 kg")
    cleat_cm3 = sum(volume(shapes[n]) for n in G_("battery retention")) / 1000
    cleat_hi = round(cleat_cm3 * 2.70 / 1000, 3)   # solid 6061 at 2.70 g/cm3
    cleat_lo = round(cleat_hi * 0.5, 3)            # formed-angle cleats occupy about half the drawn block
    mass_rows = [
        ("frame and floor", G_("frame"), [5.2, 6.6], "Four 2x1x0.125 in 6061 rails (2.72 m at 1.20 kg/m), 3 mm polycarbonate floor (about 0.4 m2), lip, slide rails, tube mounts, gussets"),
        ("hopper walls", G_("hopper"), [2.4, 3.4], "Four 2 mm polycarbonate panels (about 2.5 kg at 1.2 g/cm3) plus edge stiffeners"),
        ("drivetrain", G_("drivetrain"), [8.5, 10.5], "Four MAXSwerve corners: 1.720 kg purchased assembly each (foundation reconciliation) plus drive and steering motors"),
        ("floor indexer", G_("floor belts"), [1.5, 2.3], "Two flat belt runs, rollers, one reversible motor and gearbox. The belt cleat of the earlier issue is removed; its mass was inside this range and the range is kept"),
        ("shooter", G_("shooter"), shooter_kg, shooter_basis),
        ("intake", G_("intake"), [2.8, 3.8], "Vertical belt module with internal motor, top roller, carriage plates and slide moving stage"),
        ("climber", G_("climber tubes") + G_("climber inner tubes") + G_("climber hooks"), [3.0, 4.0], "Two telescoping tube pairs, hooks with swing actuators inside the inner tubes, winch and cables"),
        ("electrical and controls", G_("electrical"), [4.2, 5.4], "Power distribution, controller, radio, 15 motor controllers, breaker, sensors, wiring on two side panels"),
        ("bumpers (excluded by R103)", G_("bumpers"), [0.0, 0.0], "R103 excludes bumpers; 6.0-7.5 kg carried in the running payload and in the R408 check"),
        ("battery (excluded by R103)", G_("battery"), [0.0, 0.0], "R103 excludes the battery and its connector half; 5.0-6.9 kg (V0 battery 4.99-6.57 kg plus leads) carried in the running payload"),
        ("field fixtures (not robot)", field_m, [0.0, 0.0], "HUB and TOWER references are field equipment"),
        ("unmodeled robot hardware", [], [3.0, 5.0], "Fasteners, brackets, cable chain, camera and spares not yet drawn"),
        ("battery retention", G_("battery retention"), [cleat_lo, cleat_hi], f"Two cleat envelopes, {cleat_cm3:.1f} cm3: high as solid 6061 at 2.70 g/cm3, low at half fill for formed angle; rivets inside"),
    ]
    payload = [6.0 + 5.0 + 24 * 0.203, 7.5 + 6.9 + 24 * 0.227]
    inspection = [sum(r[2][0] for r in mass_rows), sum(r[2][1] for r in mass_rows)]
    running = [inspection[0] + payload[0], inspection[1] + payload[1]]
    assert running[1] <= D.HANG_MASS_KG, f"the hang trial's {D.HANG_MASS_KG} kg is below the running mass upper bound {running[1]:.2f} kg"
    assert abs(ballistics.R3_RELEASE_M - release_mm[1] / 1000) < 0.003, "ballistics.py R3_RELEASE_M differs from the launch trial's release height"
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
    release_distance = (release_mm[0] - hub_shot[0]) / 1000
    measured = dict(issue=ISSUE, designSha256=design["sha256"], stepSha256=step["sha256"],
                    startOverhangMm=round(sweep["startOverhang"], 3), sweptTopMm=round(sweep["top"], 3),
                    sweptFrontExtensionMm=round(sweep["front"], 3), sweptOtherExtensionMm=round(max(sweep["rear"], sweep["side"]), 3),
                    sidesExtendedMax=float(sweep["maxSides"]), sweptWorst=sweep["worst"], deployedReachMm=round(deployed_reach, 3),
                    capacityDeployed=float(len(dep)), capacityStowed=float(len(stow)),
                    volumeEstimateDeployedLow=vol["R3"]["deployed"]["estimateAtPacking"]["0.45"], volumeEstimateStowedLow=vol["R3"]["stowed"]["estimateAtPacking"]["0.45"], lowCapacityDeployed=float(len(low_dep)), lowCapacityStowed=float(len(low_stow)),
                    releaseDistanceM=round(release_distance, 4), deliveryPoseM=round(-hub_shot[0] / 1000, 4),
                    withBumpersUpperKg=round(inspection[1] + 7.5, 3), bellyClearanceMm=k["floor"] - 6.0,
                    bumpCrossingClearanceMm=bump["minClearanceMm"], bumpCrossingLimit=bump["limitingFeature"],
                    bumperUprightOverlapMm=round(G.HALF_W + 76.5 - 819.15 / 2, 2),
                    basis="Measured by build_package.py from the solids it writes to package.step and the cases it writes to paths.json. Extensions sample every robot member except bumpers at 49 fractions of each operating and park case. Capacity premises use free_volume() at a 0.45 packing fraction; capacity() is a rigid stacked-lattice lower bound. The release distance is the launch trial's release point to the HUB centre.")
    for old in OUT.glob(f"premise-{ISSUE}-*.json"):  # earlier issues keep their pinned premise files
        old.unlink()
    rules = carry("construction-rules.json")
    strategy = carry("kickoff/selected-strategy.json", REPO / "kickoff/selected-strategy.json") if release else \
        {"file": "kickoff/selected-strategy.json", "sha256": sha(REPO / "kickoff/selected-strategy.json")}
    # Replay input for the held delivery-pose premise: the named depot-shift step of slot 2 in the re-run series.
    held = HERE / "receipt-R3-PD1-held.json"
    # The repeat keeps the held premise's scenario identity; its own unit is inches from the blue-hub station centre.
    HELD_SCENARIO = "Robot-centre distance from the HUB centre at delivery in the field rehearsal (2.16 m at its delivery steps)"
    held_plan = json.loads(held.read_text(encoding="utf-8"))["planSha256"] if held.exists() else None
    rprof = HERE / "rehearsal" / "r3-2p7m-profile.json"
    hub_in = (182.1, 158.85)
    for name in sorted(p.name for p in (HERE / "rehearsal").glob("*.json") if p.name != "delivery-pose-evidence.json" and "wait-cycles" not in p.name):
        carry(f"rehearsal/{name}")
    carry("receipt-R3-PD1-held.json"); carry("ballistics.json"); carry("bump_crossing.py")

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
        fieldReplay=dict(field_input, profile=pin("rehearsal/r3-2p7m-profile.json"), result=pin("rehearsal/r3-2p7m-series.json")),
        resolvedSteps=[depot_pose, auto_pose],
        frame="Blue field inches. The stand-off is measured to the blue-hub station centre (its chassis action datum at 108, 158.85); the HUB centre is (182.1, 158.85), so both steps stand 2.70 m from the HUB centre.",
        comparison=pin("rehearsal/comparison.json"),
        outcome="With waitCycles yield and the shared partner deconfliction (0 permanent cycles), slot 2 credits 124 FUEL in both the baseline and the 2.70 m series, so the pose costs nothing; R3L credits 124 on the depot route and 40 on the TRENCH route (0 permanent cycles when it has the corridor alone). Pre-0.84 results were understated by permanent wait cycles.",
        heldReceipt=pin("receipt-R3-PD1-held.json") if held.exists() else None))
    specs = [
        ("start-overhang", "mm", [-500.0, 0.5], "startOverhangMm", "Starting fold: nothing but bumpers outside the frame projection", "preliminary-design", ["intake", "climber hooks"], rules, "R102 no overhang in the starting configuration"),
        ("swept-height", "mm", [0.0, 762.0], "sweptTopMm", "Robot height in every operating and park pose", "preliminary-design", ["climber hooks", "intake", "hopper"], rules, "R104/R107 30 in, measured as if on a flat floor"),
        ("swept-front-extension", "mm", [-500.0, 304.8], "sweptFrontExtensionMm", "Front extension through every operating and park pose", "preliminary-design", ["intake", "climber hooks"], rules, "R105 12 in"),
        ("swept-other-extension", "mm", [-500.0, 0.5], "sweptOtherExtensionMm", "Rear and side extension through every operating and park pose", "preliminary-design", ["shooter", "climber hooks"], rules, "R106 one side at a time; only the front extends"),
        ("sides-extended", "sides", [0.0, 1.0], "sidesExtendedMax", "Sides extended at once in any sampled pose", "preliminary-design", ["intake", "climber hooks"], rules, "R106"),
        ("with-bumpers-mass", "kg", [0.0, 61.23], "withBumpersUpperKg", "Upper R103 estimate plus 7.5 kg bumpers", "preliminary-design", ["bumpers", "frame"], rules, "R408 135 lb"),
        ("hopper-capacity", "FUEL", [24.0, 200.0], "volumeEstimateDeployedLow", "Selected own-zone batch of 24 with the intake deployed, at a loose 0.45 packing fraction", "conceptual-design", ["hopper", "intake", "floor belts"], strategy, "24-piece serial batch"),
        ("start-capacity", "FUEL", [8.0, 200.0], "volumeEstimateStowedLow", "AUTO preload of eight in the starting fold, at a loose 0.45 packing fraction", "conceptual-design", ["hopper", "intake"], strategy, "Begin legally preloaded with at most eight"),
        ("shot-window", "m", [2.4, 3.6], "releaseDistanceM", "Release-to-HUB distance with an entry band under all drag and spin corners", "preliminary-design", ["shooter"], pin("ballistics.json"), "ballistics.json at the launch trial's 0.267 m release: every drag and spin corner enters from 2.4 m with a 0.15 m/s band (0.03 m/s at 2.2 m)"),
        ("delivery-pose", "in", [32.0, 49.0], "deliveryStandoffIn", HELD_SCENARIO, "conceptual-design", ["shooter", "drivetrain"], delivery_evidence, "Every B2 blue-hub attempt in the re-run series r3-2p7m stands 32.2004-48.6491 in from the station centre (AUTO step 32.2004, depot step 48.6491), inside 49 in (3 in within the 52 in release radius); the scenario text is the held R3-PD1 identity, whose 2.16 m refers to the original rehearsal; the step stands 2.70 m from the HUB centre and costs no FUEL against the deconflicted baseline (124 vs 124)"),
        ("delivery-hub-distance", "m", [2.6, 2.8], "deliveryPoseM", "Robot-centre distance from the HUB centre at every slot 2 delivery step in the re-run rehearsal", "conceptual-design", ["shooter", "drivetrain"], pin("rehearsal/comparison.json"), "The robust shot band at 62 degrees is 0.15 m/s wide from 2.4 m release distance"),
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

    if release:
        shutil.copyfile(REPO / "kickoff/selected-strategy.md", OUT / "narrative.md")
        narrative = pin("narrative.md")
    else:
        narrative = {"file": "kickoff/selected-strategy.md", "sha256": sha(REPO / "kickoff/selected-strategy.md")}

    # ---------------------------------------------------------- narrative coverage, from the trial results
    tr = trials
    cap_s = tr["acquire-nominal"]["metric"]["value"]
    seat_s = tr["entry-nominal"]["metric"]["value"]
    band = trial_data["chain"]["scoringBandMps"]
    feed = [s for ph, _, s in strokes if ph == "launch-feed"]
    feed_mps = abs(feed[-1]["toMm"][0] - feed[0]["fromMm"][0]) / 1000 / (feed[-1]["toS"] - feed[0]["fromS"])
    lane_rate = feed_mps / (k["pitch"] / 1000)
    belt_rate = D.FLOOR_BELT_MPS / (k["pitch"] / 1000)
    lip_mm = D.FRONT_LIP["z1"] - k["belt_top"]
    lip_g = math.sqrt(2 * G.R_BALL * lip_mm - lip_mm ** 2) / (G.R_BALL - lip_mm)
    wheel = tr["launch-nominal"]["wheelDemand"]
    near, far = tr["launch-no-back-off-seat-0.5mm-aft"], tr["launch-no-back-off-seat-1.0mm-aft"]
    assert near["passed"] and not far["passed"]
    seat_text = (f"Nothing restrains the seated FUEL forward. Without the belt's back-off, a FUEL at rest {near['startFlywheelIndentationMm']:.2f} mm into the "
                 f"stopped wheel still launches at speed and one {far['startFlywheelIndentationMm']:.2f} mm in is fed early at spin-up; that threshold comes from "
                 "the penalty contact springing a lightly pressed FUEL clear and is not a measured limit. With the back-off a FUEL pressed "
                 f"{tr['launch-from-pressed-seat']['startFlywheelIndentationMm']:.1f} mm in launches at speed; one wedged "
                 f"{tr['launch-from-wedged-seat (adverse)']['startFlywheelIndentationMm']:.1f} mm in by a running belt does not. No hold-back is designed")
    half_band = 100 * (band[1] - band[0]) / (band[1] + band[0])
    wheel_text = (f"The launch trial's wheel does {wheel['energyJ']:.0f} J of work per FUEL at the imposed speed. A free 0.006 kg m2 wheel would lose "
                  f"{wheel['speedDropPercent']:.1f}% of its speed supplying it, against a scoring band of plus or minus {half_band:.1f}%, so the wheel's inertia "
                  "or its speed control has to carry the shot (gate G5)")
    gates = "Verification gates are in verification-gates.json; the contract assigns physical performance, retention and actuator dynamics to their own commissioned evidence (docs/preliminary-design.md)."
    objectives = [
        ("AUTO: start with up to eight supported FUEL and score from a legal launch pose while the HUB is active", "represented",
         f"The starting fold holds {measured['volumeEstimateStowedLow']:.0f} or more FUEL by free volume (start-capacity premise); the launch and flight cases carry a FUEL into the HUB opening from the 2.7 m pose that the re-run rehearsal credits in AUTO (delivery-pose premise). With Agent FRC 0.84 wait-cycle yield and the shared partner deconfliction, delivering from 2.70 m costs no FUEL: slot 2 credits 124 in both the baseline and R3 series (alliance totals 366 and 382). Pre-0.84 results (96 against 104) were understated by permanent wait cycles."),
        ("Inactive shift: collect and hold the next allocated stock from the DEPOT, OUTPOST or a partner", "represented",
         f"The acquire cases take a floor FUEL up the bumper face and over the bumper along the acquisition trial's trace (captured in {cap_s:.2f} s); the hopper cases follow the entry trial from capture to rest against the stopped flywheel ({seat_s:.1f} s, floor belts stopped). hopper-capacity is {measured['volumeEstimateDeployedLow']:.0f} or more by free volume. The entry trial is one FUEL in an empty lane: a batch of 24 collected onto stopped belts is not evaluated, and a running belt wedges the FUEL into the stopped pinch (entry-floor-belt-running trials)."),
        ("Active shift: carry each FUEL from storage through one transfer into the HUB", "represented",
         f"loaded-transit, the launch cases and the flight cases carry the tracked FUEL from its seat into the HUB cavity along the launch and delivery trials' traces. The launch trial backs the FUEL off the stopped wheel, spins the wheel up and feeds it; it releases at {rel_state['speedMps']:.2f} m/s and {rel_state['elevationDeg']:.1f} degrees, and the delivery trials score from {band[0]:.2f} to {band[1]:.2f} m/s."),
        ("Active shift: sustain 2.00 FUEL/s to score 24 with stock ready by second 5", "represented",
         f"Two pinch lanes. If every FUEL moved at the {D.FLOOR_BELT_MPS} m/s belt speed with {k['pitch']:.0f} mm spacing, each lane would feed {belt_rate:.1f} FUEL/s. The launch trial's single free FUEL rolls on that belt at {feed_mps:.2f} m/s from rest (mean over the feed), which is {lane_rate:.1f} FUEL/s per lane and {2 * lane_rate:.1f} for two lanes against 2.00, so the margin depends on how a stacked batch rides the belt. {wheel_text}. The first FUEL of a batch takes {rel_state['t']:.1f} s from its seat to release (back-off, spin-up, feed). Bulk convergence and the sustained rate are gate G1. " + gates),
        ("Fallback: score the available batch when supply or traffic consumes the window and return to collecting", "represented",
         "The cycle is piece-count independent; the intake stays deployed in every operating case; the re-run rehearsal keeps the depot loop."),
        ("Traffic: remain in the own zone, keep possession through loaded driving and contact, and yield", "represented",
         f"By geometry the front lip stands {lip_mm:.0f} mm above the floor belts, so by statics a floor FUEL needs about {lip_g:.1f} g of horizontal deceleration to roll over it; side and rear walls rise above the top layer; the open throat holds no counted FUEL. The seated FUEL is held only by the stopped flywheel behind it and friction: nothing restrains it forward during the loaded transit. Loaded 0.5 g stops are gate G2. " + gates),
        ("Neutral collector alternative with two field crossings", "out-of-scope",
         f"The coordinator selected the own-zone role. R3 keeps a BUMP crossing option (bump-crossing premise, {measured['bumpCrossingClearanceMm']:.1f} mm least clearance) with the intake retracted; the re-run TRENCH variant (R3L) credits fewer FUEL than the depot loop."),
        ("End game: Level 1 low-rung hang when its expected 10 points exceed the remaining FUEL service", "represented",
         f"Cases reach, seat (2 mm required contact) and lift 70 mm; the 714 mm frame gives 23.9 mm of bumper overlap with each upright (hang-bumper-overlap premise); the hang physics trial at {D.HANG_MASS_KG} kg holds {1000 * tr['hang-nominal']['metric']['value']:.1f} mm with the brake and fails without it; its cable load peaks at {tr['hang-nominal']['cable']['liftPeakN']:.0f} N in the lift and settles at {tr['hang-nominal']['cable']['holdN'][1]:.0f} N. Jaw capture under lateral offset and the brake hold are gate G3. " + gates),
        ("AUTO Level 1 TOWER (15 points, two-robot cap)", "out-of-scope",
         "The strategy keeps the eight-FUEL AUTO objective; no joined AUTO climb evidence is sought in this layout."),
        ("Reserve the depot entrance and partner lane", "out-of-scope",
         "Alliance routing decision owned by the field rehearsal, independent of the robot layout."),
        ("Measurement: observe intake crossing, retained identity, release and downstream crossing on one timebase", "represented",
         "entry sensor at the front lip and pinch sensor at the flywheel lane are placed; the HUB counter is field equipment."),
    ]
    explain = component_explanations(shapes, groups_of, roles, k, trials, wheel_text)
    view = "package-motion.html" if release else f"{REL}/review/package-motion.html"
    wrap_hood = [(row["compression"].get("hood", 0), row["case"]) for row in fuel_index if row["phase"] == "launch-wrap" and "hood" in row["compression"]]
    control_case = max(wrap_hood)[1]
    mission_objective = "Active shift: carry each FUEL from storage through one transfer into the HUB"
    plan = dict(schema="agent-frc/preliminary-layout@1", issue=ISSUE, design=design, step=step, motion=motion, datum=datum,
                groups=groups, mounts=mounts, stages=stages, missingInputs=[],
                control=dict(case=control_case, displaced="hood", moving=BALL, offsetMm=[0, 0, 8],
                             basis="Raise the hood 8 mm, as a mislocated hood mount would, so it squeezes the FUEL beyond the launch trial's indentation in the wrap"),
                cycle=cycle, view=view, budgets=budgets, premises=premises,
                narrativeReview=dict(source=narrative, objectives=[dict(objective=o, disposition=s, basis=b) for o, s, b in objectives]),
                presentation=dict(components=explain,
                                  required={"wheels": [n for n in shapes if "wheel azimuth" in n], "drive and steering actuators": [n for n in shapes if "module motors" in n],
                                            "control computer, power distribution, main disconnect and radio": ["electronics panel", "electronics panel left"],
                                            "supply": ["battery"], "game piece": [BALL] + [n for n in shapes if n.startswith("FUEL stored")]},
                                  loadMembers={"drive": [n for n in shapes if "module body" in n or "module motors" in n], "steer": [n for n in shapes if "module motors" in n],
                                               "intake": ["intake belt module", "intake top roller", "intake slide rail left", "intake slide rail right"], "indexer": ["floor belt main", "floor belt front"],
                                               "flywheel": ["flywheel motor left", "flywheel motor right", "flywheel"], "climber": hooks + G_("climber inner tubes") + ["climber winch"], "controls": ["electronics panel", "electronics panel left"]},
                                  architecture="R3 · tall floor-fed hooded-flywheel shooter on a 680 × 714 mm four-module swerve base",
                                  caseKinds={c["id"]: "nominal" for c in cases},
                                  uncoveredCases=[
                                      dict(id="bump-crossing-dynamic", condition="Driving over the BUMP at speed with stored FUEL", reason="Only the static two-wheel rest check (bump_crossing.py) is evaluated; dynamic loads and FUEL retention are not."),
                                      dict(id="loaded-robot-contact", condition="Robot-to-robot contact while carrying FUEL", reason="No contact or pushing case is commissioned in this layout."),
                                      dict(id="hopper-capacity-physical", condition=f"Seating {measured['volumeEstimateStowedLow']:.0f} or more FUEL in the starting fold", reason="Capacity is a free-volume premise; packing is not simulated."),
                                      dict(id="batch-collection", condition="Collecting a batch of 24 FUEL onto stopped floor belts", reason="The entry trial follows one FUEL in an empty lane; how a batch distributes, and how it is conveyed without wedging the first FUEL into the stopped pinch, is not evaluated."),
                                      dict(id="seat-retention-in-transit", condition="Holding the seated FUEL off the flywheel through the loaded transit and the spin-up", reason=seat_text),
                                      dict(id="intake-belt-load", condition="Intake belt speed under the acquisition load", reason=f"The acquisition trial imposes the belt speed; its contacts dissipate up to {belt_w:.0f} W at peak, above what the intake's 30 A supply limit delivers, and the trial fails at 2.0 m/s."),
                                      dict(id="flywheel-load", condition="Flywheel speed under the launch load", reason="The launch trial imposes the wheel surface speed. " + wheel_text + "."),
                                  ],
                                  fieldInteractions=[dict(title="R3 field interactions: acquisition, hopper entry, launch, delivery and hang trials",
                                                          href="field/r3-field-trials.html" if release else "field-interaction.html",
                                                          objective=mission_objective, evidence=trials_pin)]))
    if not release:
        # Agent FRC 0.85.0: the held R3-PD1 premise moved, byte-identical, out of the disallowed design/ root.
        plan["relocations"] = {"design/preliminary/premise-delivery-pose-accepted.json": f"{REL}/premise-R3-PD1-delivery-pose-accepted.json"}
    write("layout.json", plan)
    shot = dict(speedMps=rel_state["speedMps"], elevationDeg=rel_state["elevationDeg"], spinRatio=rel_state["spinRatio"],
                releaseMm=list(xz(release_mm)), distanceM=release_distance, scoringBandMps=band, flightS=tr["deliver-nominal"]["metric"]["value"],
                source="launch-nominal release state and deliver-nominal trace in field-trials.json",
                pointMassBands=dict(zip(("robustBandMps", "conditionBandsMps"),
                                        ballistics.robust(G.EXIT_DEG, release_mm[1] / 1000, release_distance, ballistics.CONDITIONS)),
                                    nominalBandMps=ballistics.window(G.EXIT_DEG, release_mm[1] / 1000, release_distance, 0.215, 0.47, 0.15),
                                    note="ballistics.py point-mass screen at the trial's release height and distance, for comparison only"))
    extras = dict(freeVolume=vol, capacity=dict(R3=dict(deployed=dep, stowed=stow), R3L=dict(deployed=low_dep, stowed=low_stow, constants={k_: kl[k_] for k_ in ("floor", "wall", "hook")})),
                  stored=stored, trackedFuel=dict(installedMm=list(start), seatMm=list(seat), toleranceMm=TOL_MM, fieldTrials=trials_pin, cases=fuel_index,
                                                  feedSpeedMps=feed_mps, laneRateFuelPerS=lane_rate),
                  shot=shot, inspectionKg=inspection, runningKg=running, sweep=sweep,
                  volumesMm3={n: round(volume(s), 1) for n, s in shapes.items()})
    if not release:
        write("package-facts.json", extras)
    missions = dict(missionCases=[
        dict(case=last_flight, kind="operating-case", accomplishes="delivered", objective=mission_objective),
        dict(case=seated_case, kind="operating-case", accomplishes="acquired", objective=mission_objective),
        dict(case="climb-lift", kind="operating-case", accomplishes="climb-held",
             objective="End game: Level 1 low-rung hang when its expected 10 points exceed the remaining FUEL service")])
    if release:
        write("missions.json", missions)
        import field_trials
        field_trials.render_player(field_trials.player_data(OUT / "field-trials.json", "field-trials.json"), OUT / "field" / "r3-field-trials.html", release=True)
        import review_data
        review_data.write(OUT, plan, trial_data, fuel_index, measured)
    print(json.dumps(dict(target=str(OUT), volume={v: {s_: x["estimateAtPacking"] for s_, x in y.items()} for v, y in vol.items()},
                          capacity={"R3": [len(dep), len(stow)], "R3L": [len(low_dep), len(low_stow)]}, stored=len(stored),
                          fuelCases=len(fuel_index), cycle=len(cycle), control=control_case, shot={q: shot[q] for q in ("speedMps", "elevationDeg", "distanceM", "scoringBandMps")},
                          feedMps=feed_mps, sweep=sweep, reach=deployed_reach, inspection=inspection, running=running,
                          maxFitDeviationMm=max(r["maxDeviationMm"] for r in fuel_index)), indent=1))
    if args.check:
        check(args, view)


def check(args, view):
    """Run the layout check. A release is checked in a scratch copy, so its committed receipt and player are left for
    the release staging pass; the experiment tree keeps its own receipt and player."""
    env = dict(__import__("os").environ)
    env.setdefault("PYTHON", sys.executable)
    if args.release:
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp) / "inputs"
            shutil.copytree(OUT, scratch, ignore=shutil.ignore_patterns("package-motion*", "receipt.json"))
            flags = ["--fail-fast"] if args.fail_fast else ["--require-checked", "--write-view"]
            out = subprocess.run(["node", str(CLI), "preliminary-check", str(scratch), "layout.json", *flags], capture_output=True, text=True, env=env)
            sys.stderr.write(out.stderr)
            if args.receipt:
                Path(args.receipt).write_text(out.stdout, encoding="utf-8", newline="\n")
            try:
                r = json.loads(out.stdout)
                print("exit", out.returncode, "status", r.get("status"), "missing", r.get("missingInputs"), "reopen", r.get("reopen"),
                      "control", ((r.get("control") or {}).get("witness") or {}).get("status"))
            except ValueError:
                print("exit", out.returncode, out.stdout[:400])
        return
    flags = ["--fail-fast"] if args.fail_fast else ["--require-checked", "--write-view"]
    if args.previous:
        flags += ["--previous", args.previous]
    view_path = ROOT / view
    if not args.fail_fast:
        for stale in (view_path, view_path.with_name("package-motion.geometry.json.gz")):
            if stale.exists():
                stale.unlink()
    view_path.parent.mkdir(exist_ok=True)
    out = subprocess.run(["node", str(CLI), "preliminary-check", str(ROOT), rel("layout.json"), *flags], capture_output=True, text=True, env=env)
    sys.stderr.write(out.stderr)
    (OUT / ("receipt-partial.json" if args.fail_fast else "receipt.json")).write_text(out.stdout, encoding="utf-8", newline="\n")
    print("exit", out.returncode)


def component_explanations(shapes, groups_of, roles, k, trials, wheel_text):
    E = {}
    def put(names, purpose, rationale, category, material, **more):
        for n in names:
            E[n] = dict(purpose=purpose, rationale=rationale, category=category, material=material, **more)
    S = list(shapes)
    acq, lch = trials["acquire-nominal"], trials["launch-nominal"]
    hang = trials["hang-nominal"]["cable"]
    peak = lambda t, labels: max(r[2] for label in labels for r in t["contacts"].get(label, [[0, 0, 0.0]]))
    I_ = G.INTAKE
    put([n for n in S if n.startswith("frame rail")], "Carry the drive corners, bumpers and every mechanism mount.",
        "The foundation's 680 mm length and module saddles carry forward; the frame widens to 714 mm (2788 mm perimeter) for hang overlap, so the side-rail saddle fits must be redrawn.", "structure", "6061-T6 2x1x0.125 in tube")
    put(["floor pan", "floor pan front tongue"], "Support the floor belts, battery tray and electronics.",
        "Sits 94 mm above the carpet; the BUMP crossing screen then leaves 24 mm at the belly and 8.7 mm at the front bumper corner.", "structure", "3 mm polycarbonate over aluminum stiffeners")
    put(["front lip"], "Keep floor-level FUEL from rolling out over the front rail.",
        f"Its 170 mm top stands {D.FRONT_LIP['z1'] - k['belt_top']:.0f} mm above the floor belts. The entry trial's captured FUEL grazes it by {peak(trials['entry-nominal'], ['front lip']):.1f} mm on the way in.", "structure", "3 mm aluminum")
    put([n for n in S if n.startswith("intake slide rail")], "Guide the intake carriage between the start fold and the pickup pose.",
        "A straight slide never sweeps beyond the 304.8 mm R105 reach; the fixed stage of the two-stage slide is drawn.", "structure", "Aluminum drawer-slide stage")
    put([n for n in S if n.startswith("climber tube mount")], "Carry the climber tubes and the hang load into the front rail.", "The hang reaction enters the frame next to the front modules.", "structure", "6 mm aluminum bracket")
    put([n for n in S if "wheel azimuth" in n], "Reserve the full steering sweep of each swerve wheel.",
        "A revolved envelope avoids animating an axisymmetric sweep and still bounds the wheel at any heading.", "drivetrain", "Supplier wheel; envelope only")
    put([n for n in S if "module body" in n], "Represent the swerve module plates and gearing.", "Four-module swerve is the project default and the foundation already fits the supplier tabs.", "drivetrain", "Supplier module")
    put([n for n in S if "module motors" in n], "Reserve the drive and steering motors above each module.", "Their height limits the lowest hopper layer at the corners.", "drivetrain", "Supplier motors")
    put([n for n in S if n.startswith("bumper")], "Protect the frame perimeter and back the intake pinch.",
        f"The 48-168 mm zone and 76 mm section follow the foundation release; the front bumper face is the pinch backing: the acquisition trial presses the FUEL {peak(acq, ['bumper face', 'bumper top']):.1f} mm into it. Its 866.15 mm width overlaps each TOWER upright by 23.9 mm.", "bumper", "Plywood backing, foam, fabric")
    put(["hopper wall left", "hopper wall right"], "Contain stacked FUEL up to 715 mm.", "Walls rise 85 mm above the top-layer centres so a stable stack stays inside.", "structure", "2 mm polycarbonate")
    put(["hopper front upper wall"], "Close the hopper front above the intake throat.", "It starts at 482 mm, above the slide's swept path and the stowed carriage.", "structure", "2 mm polycarbonate")
    put(["hopper rear wall"], "Separate stored FUEL from the spinning flywheel.", "Only the floor-level lane may reach the pinch; upper layers would double-feed or jam on the wheel top.", "structure", "2 mm polycarbonate")
    put(["floor belt main", "floor belt front"], "Hold the bottom FUEL layer, back the seated FUEL off the flywheel and feed it to the pinch.",
        f"Flat reversible belts replace the cleated belt. They stay stopped while a FUEL enters, because a running belt wedges it into the stopped pinch (entry trials); the launch trial reverses them at {lch['params']['backMps']} m/s to back the FUEL off, then feeds at {lch['params']['feedMps']} m/s.", "mechanism", "Belt envelope; flat belt and rollers")
    put(["flywheel"], "Stop the entering FUEL while it is at rest, then accelerate the FUEL against the hood.",
        f"A 4 in floor-fed flywheel. The wheel-to-hood gap is the FUEL diameter less {k['squeeze']:.0f} mm, so the stopped wheel is the seat stop and the spinning wheel grips: the launch trial releases at {lch['release']['speedMps']:.2f} m/s from a {lch['params']['wheelMps']} m/s surface. {wheel_text}.", "mechanism", "Aluminum hub, compliant tread")
    put(["hood"], "Guide the FUEL around the flywheel and release it at about 62 degrees elevation.",
        f"Concentric with the wheel and tangent to the floor belt top. It ends at {k['hood_span_deg'][0]:.1f} degrees about the wheel axis, where the launch trial releases the FUEL at {lch['release']['elevationDeg']:.1f} degrees; the end stays inside the rear perimeter, so the shooter never extends a second side.", "mechanism", "Formed aluminum with friction liner")
    put([n for n in S if "shooter side plate" in n], "Carry the flywheel bearings and hood.", "Plates stop 4 mm short of the rear modules and bound the two pinch lanes.", "structure", "6 mm aluminum plate")
    put(["flywheel motor left", "flywheel motor right"], "Drive the flywheel from both ends.", "Outboard of each side plate, clear of the battery, the panels and the rear modules.", "mechanism", "Brushless motor")
    put(["battery"], "Supply the robot bus.", "Standing on its end at the left side lets it lift straight out between the hook arm and rear wall.", "battery", "Sealed lead acid 12 V")
    put(["battery retention cleat aft"], "Stop the battery sliding aft and carry its end load into the floor pan.",
        "The battery stands on the floor pan with no retention article; the R3 layout check found no mount for it.", "structure", "6061 aluminium formed cleat", volumeType="envelope")
    put(["battery retention cleat fore"], "Stop the battery sliding forward toward the electronics panel.",
        "Paired with the aft cleat so the battery is captured in X while it still lifts straight out for service.", "structure", "6061 aluminium formed cleat", volumeType="envelope")
    put(["electronics panel", "electronics panel left"], "Hold power distribution, controller, radio, breaker and 15 motor controllers on both faces.", "The side strips are outside the floor lanes and reachable from above.", "electrical", "Polycarbonate panel")
    put(["entry sensor"], "Observe each FUEL crossing the intake lip.", "The strategy requires per-piece intake crossings on the match timebase.", "electrical", "Beam-break sensor")
    put(["pinch sensor"], "Observe each FUEL entering the flywheel lane.", "Separates retained identity from release for the counting requirement.", "electrical", "Beam-break sensor")
    put([n for n in S if n.startswith("climber tube ") and "mount" not in n], "Guide the telescoping hooks.", "Front corners above the modules give a straight load path into the frame for the hang.", "structure", "30 mm round aluminum tube")
    put(["climber winch"], "Retract both inner tubes by cable to lift the robot.", f"One motor at the front top keeps both hooks synchronized. In the hang trial at {D.HANG_MASS_KG} kg its cable load peaks at {hang['liftPeakN']:.0f} N during the lift, and the brake must hold {hang['holdN'][1]:.0f} N with power removed (gate G3).", "mechanism", "Gearmotor and spool envelope")
    put([n for n in S if n.startswith("climber inner tube")], "Telescope inside the outer tube to seat the hook and lift the robot 70 mm.",
        "A round tube lets the hook swing on top without the tube rotating in its guide; the swing actuator sits inside it.", "mechanism", "22 mm round aluminum tube")
    put([n for n in S if n.startswith("climber hook")], "Swing over the low rung, seat and lift the robot 70 mm.", "Stowed inside the perimeter for R106; a 180 degree inboard swing avoids a second-side extension.", "mechanism", "Aluminum tube and hook plate")
    put(["intake belt module"], "Draw a floor FUEL under its bottom pulley and lift it up the bumper face.",
        f"Drawn at the acquisition trial's setting: the back run stands {I_['pinch_squeeze']:.0f} mm inside one FUEL diameter from the bumper face and the bottom pulley {I_['pulley_squeeze']:.0f} mm into a floor FUEL. The trial captures at 17.5 mm and fails at 15 mm, so the squeeze is a layout dimension, not a detailing choice. It stays inside the 304.8 mm reach.", "mechanism", "Belt module with internal motor")
    put(["intake top roller"], "Push the lifted FUEL aft over the bumper.",
        f"Lowered {I_['roller_drop']:.0f} mm into the path of the FUEL at the top of the climb, as in the acquisition trial; it throws the FUEL into the hopper at the capture velocity the entry trial starts from.", "mechanism", "2 in compliant wheels on hex shaft")
    put([n for n in S if n.startswith("intake carriage plate")], "Join the belt module and top roller to the slide.", "Plates at 262-272 mm pass between the 819 mm TOWER uprights so the intake can stay deployed during the climb.", "mechanism", "6 mm aluminum plate")
    put([BALL], "Follow one identifiable FUEL from the carpet into the HUB.",
        f"Its cases are strokes fitted within {TOL_MM} mm to the solved acquisition, entry, launch and delivery traces; it is drawn where the mission finds it, on the carpet ahead of the intake.", "game-piece", "Foam FUEL 150.114 mm, 0.203-0.227 kg")
    put([n for n in S if n.startswith("FUEL stored")], "Represent stored stock in the starting fold.", "Supported pockets from the deposition screen that stay clear of every traced position of the tracked FUEL; capacity itself is the free-volume premise.", "game-piece", "Foam FUEL")
    put(["hub body", "hub top"], "Locate the HUB and its hexagonal opening.", "The flight cases follow the delivery trial over the near flat at 1828.8 mm, into the conservative inscribed opening and against the cavity wall.", "field", "Field fixture (V0 dimensions)")
    put([n for n in S if n.startswith("tower upright")], "Locate the TOWER uprights.", "Their 819 mm gap bounds the intake and the bumper approach.", "field", "Field fixture (V0 dimensions)")
    put(["tower low rung"], "Locate the low rung at 685.8 mm.", "The hooks must seat on it; the V0 text centres it in the upright depth.", "field", "Field fixture (V0 dimensions)")
    put(["tower base"], "Locate the TOWER BASE plate.", "Level 1 requires clearing it; its 8 mm edge stands under the front bumper at the berth.", "field", "Field fixture (V0 dimensions)")
    missing = [n for n in shapes if n not in E]
    assert not missing, missing
    for n, c in E.items():   # inspector fields: display name, owning group and what the drawn volume stands for
        g = groups_of[n]
        c.setdefault("name", n[0].upper() + n[1:])
        c.setdefault("subsystem", g)
        c.setdefault("volumeType", "envelope" if ENVELOPE.search(n) or roles[g] == "drive" else "material")
    return E


if __name__ == "__main__":
    main()
