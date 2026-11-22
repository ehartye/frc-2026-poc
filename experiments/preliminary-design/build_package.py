"""Build the R3 preliminary package: placed STEP, field fixtures, motion study, budgets, premises, trial records,
missions and review plan.

Run from anywhere with the project geometry environment, after field_trials.py:
    python -I -B experiments/preliminary-design/field_trials.py
    python -I -B experiments/preliminary-design/build_package.py --release cad/preliminary-design/releases/layout-002 [--check] [--fail-fast] [--previous RECEIPT]

The package is written into the release folder and checked with the repository as the project root: every pin is
a repository-relative path, and the files the package pins are copied into the release folder.

The tracked FUEL's cases are not drawn here. They are fitted to the solved traces in field-trials.json
(trace_cases.py), so the package animation is the trial motion within the stated tolerance. Each stroke pins a
record of the trial window it follows, with that trial's qualification: its result, a rejected control, brackets
and a timestep check.
"""
import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
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

ISSUE = "R3-PD3"
PLUGIN = Path(os.environ["AGENT_FRC"])  # the Agent FRC plugin checkout; required
CLI = PLUGIN / "scripts" / "design.mjs"
TOL_MM = 1.5          # every FUEL stroke stays within this distance of its traced samples
BALL = "FUEL tracked"
PAYLOAD = "tracked FUEL"
EXP = HERE.relative_to(REPO).as_posix()

# Output target, set by main(): OUT is the release folder written, REL its repository-relative path.
OUT, REL = None, None


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
    return f"{REL}/{name}"


def pin(name):
    return {"file": rel(name), "sha256": sha(OUT / name)}


def write(name, obj):
    (OUT / name).parent.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return pin(name)


def carry(name, source=None):
    """Copy a pinned input into the release folder. A copied JSON file's pins are re-rooted from this experiment
    folder to the release folder."""
    src = HERE / name if source is None else source
    (OUT / name).parent.mkdir(parents=True, exist_ok=True)
    if name.endswith(".json") and source is None:
        text = src.read_text(encoding="utf-8").replace('"' + EXP + "/", '"' + REL + "/")
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


# ---------------------------------------------------------------- start-fold stock
def supported_positions(stowed, extra_exclusions=(), avoid=(), limit=7):
    """Greedy bottom-up deposition on a 22 mm grid. An upper FUEL needs a FUEL below it and three contacts in all
    (FUEL within 2 mm, or solids within 6 mm). Used to place the preload, not to claim capacity."""
    bodies, k = G.robot_bodies("R3", intake_stowed=stowed)
    solids = [(n, s_, bounds(s_)) for n, (s_, g) in bodies.items()]
    r = G.R_BALL
    zs = [k["z0"] + 11 * i for i in range(60) if k["z0"] + 11 * i <= k["wall"] - r]
    cands = sorted(((x, y, z) for z in zs for x in range(-150, 237, 22) for y in range(-238, 239, 22)),
                   key=lambda q: (q[2], q[0], abs(q[1]), q[1]))
    placed = []
    for q in cands:
        if abs(q[1]) > 316 + G.DY - r - 1.5 or (q[2] > k["z0"] + 10 and q[0] < D.REAR_WALL_X[1] + r + 1.5):
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


def start_volume():
    """Hopper volume available to FUEL in the starting fold: the walled space behind the stowed back plate, up to the
    top of that plate, minus every robot solid inside it (exact booleans)."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    bodies, k = G.robot_bodies("R3", intake_stowed=True)
    foot = D.BUMPER["x1"] - D.INTAKE["back_foot"] - D.INTAKE["shift"][0]
    top = D.INTAKE["back_top"] - D.INTAKE["shift"][2]
    region = G.box((D.REAR_WALL_X[1], -316 - G.DY, k["belt_top"]), (foot, 316 + G.DY, top))
    for n, (s_, g) in bodies.items():
        region = BRepAlgoAPI_Cut(region, s_).Shape()
    total = volume(region)
    vball = 4 / 3 * math.pi * G.R_BALL ** 3
    return dict(freeVolumeMm3=round(total, 0), ballVolumeMm3=round(vball, 0), frontMm=foot, topMm=top,
                estimateAtPacking={str(f): round(f * total / vball, 1) for f in (0.45, 0.50, 0.55)})


# ---------------------------------------------------------------- tracked FUEL path, from the trial traces
# Trial contact surface -> placed solid it stands for. The carpet is not a placed solid.
SOLID_OF = {"bumper face": "bumper front", "bumper top": "bumper front", "belt back run": "intake belt module",
            "belt front run": "intake belt module", "bottom pulley": "intake belt module", "top pulley": "intake belt module",
            "top roller": "intake top roller", "chute back plate": "intake back plate", "feeder roller": "feeder roller left"}
INTAKE_SURFACES = ("belt back run", "belt front run", "bottom pulley", "top pulley", "top roller")
FLOOR_SURFACES = ("floor belt front", "floor belt main", "lane deck")


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
    """The tracked FUEL's ordered strokes: [(phase, trial name, stroke)] with strokes in robot millimetres."""
    acq, entry, lch, dlv = (trials[n] for n in ("acquire-nominal", "entry-nominal", "launch-nominal", "deliver-nominal"))
    t_intake = first_contact(acq, INTAKE_SURFACES)
    t_roller = first_contact(acq, ("top roller",))
    t_thrown = last_contact(acq, INTAKE_SURFACES + ("chute back plate",))
    t_floor = first_contact(entry, FLOOR_SURFACES)
    t_feeder = first_contact(entry, ("feeder roller",))
    sch = lch["schedule"]
    # The staged FUEL stands still until the feed command: the launch strokes start there.
    lch_frames = [f for f in lch["frames"] if f[0] >= sch["feedStartS"] - 1e-9]
    lch_frames[0] = [lch_frames[0][0]] + list(lch["frames"][0][1:])
    plan = [
        (acq, acq["frames"], 1, 2, [("acquire-approach", t_intake), ("acquire-climb", t_roller), ("acquire-over", t_thrown), ("acquire-throw", None)]),
        (entry, entry["frames"], 1, 2, [("hopper-drop", t_floor), ("hopper-roll", t_feeder), ("stage", None)]),
        (lch, lch_frames, 1, 2, [("launch-feed", sch["flywheelTakesS"]), ("launch-wrap", None)]),
        (dlv, dlv["frames"], 1, 3, [("flight", None)]),
    ]
    out = []
    for trial, frames, ix, iz, phases in plan:
        ends = [t for _, t in phases if t is not None]
        breaks = ends + [e["t"] for e in trial["events"]]
        for stroke in TC.fit(TC.side(frames, ix, iz), TOL_MM, breaks):
            mid = (stroke["fromS"] + stroke["toS"]) / 2
            phase = next(name for name, t in phases if t is None or mid < t)
            out.append((phase, trial["name"], stroke))
    # consecutive trials join on the same traced sample (to the 0.01 mm the traces are stored at)
    for (_, _, a), (_, _, b) in zip(out, out[1:]):
        assert math.dist(a["toMm"], b["fromMm"]) < 0.05, (a, b)
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
INTAKE_DRIVE = ("Belt and top roller driven by one brushless motor through {gear:g}:1, a speed loop to {u} m/s and {stator:g} A stator and {supply:g} A supply "
                "limits, solved in the trial; the carriage is deployed and stationary")
PHASE = {
    # phase: (what happens, electrical duty, transporting mechanisms and their drives, or None for a free path)
    "acquire-approach": ("The robot drives onto the floor FUEL; it rolls on the carpet toward the intake", "acquire", None),
    "acquire-climb": ("The bottom pulley draws the FUEL under the belt and the back run lifts it up the bumper face and the chute back plate", "acquire",
                      {"intake": INTAKE_DRIVE}),
    "acquire-over": ("The top roller pushes the FUEL aft over the top of the back plate", "acquire", {"intake": INTAKE_DRIVE}),
    "acquire-throw": ("Thrown by the top roller, the FUEL flies over the back plate and inside the frame", "acquire", None),
    "hopper-drop": ("The captured FUEL falls from the chute to the floor of the hopper", "acquire", None),
    "hopper-roll": ("The floor belt carries the FUEL aft to the feeder roller", "acquire",
                    {"floor belts": "Floor belt surface at {belt} m/s toward the feeders, imposed in the trial"}),
    "stage": ("The feeder roller draws the FUEL in to the stage beam and stops; the FUEL is clamped between the braked roller and the lane deck", "acquire",
              {"feeders": "Feeder roller surface at {stage} m/s until the FUEL centre crosses the stage beam, then stopped and braked; imposed in the trial",
               "floor belts": "Floor belt surface at {belt} m/s until the stage beam, then stopped; imposed in the trial"}),
    "launch-feed": ("On the feed command the feeder roller rolls the FUEL along the lane deck to the flywheel", "launch",
                    {"feeders": "Feeder roller surface at {feed} m/s from the feed command, given only with the wheel in its ready band; imposed in the trial"}),
    "launch-wrap": ("The flywheel takes the FUEL, rolls it up the hood and releases it", "launch",
                    {"shooter": "Flywheel a free {inertia} kg m2 body at a {wheel} m/s setpoint under two motors and a speed loop, solved in the trial"}),
    "flight": ("Free flight from the hood release into the HUB", "launch", None),
}
ENVELOPE = re.compile(r"envelope|sweep|reserve|loom|trunk|lead|housing|module body|module motors|electronics|"
                      r"battery tray|dressed battery|plug and bracket|steer|azimuth|cassettes|sills|trusses|perimeter|"
                      r"field|hub |tower |trough|bumper|SPARK MAX|radio|roboRIO|distribution|breaker|reducer|motor|winch|belt module|servo|switch|sensor", re.I)


# ---------------------------------------------------------------- trial qualification
def qualification(trials, base, control, brackets, fine):
    """The qualification record of a trial: its result, a control it rejects, brackets and a timestep check.

    control is (trial name, condition). brackets is [(input, unit, [(value, trial name), ...])]: the nominal value comes
    first; a bracket is recorded when the listed trials hold both a passing and a failing value. fine is the name of the
    same trial at a finer step."""
    t = trials
    assert t[base]["passed"], base
    assert not t[control[0]]["passed"], control[0]
    rows = []
    for name, unit, values in brackets:
        ok = [(v, n) for v, n in values if t[n]["passed"]]
        bad = [(v, n) for v, n in values if not t[n]["passed"]]
        if ok and bad:
            near = min(bad, key=lambda q: abs(q[0] - ok[0][0]))
            best = min(ok, key=lambda q: abs(q[0] - near[0]))
            rows.append(dict(input=name, unit=unit, passing=best[0], failing=near[0], passingTrial=best[1], failingTrial=near[1],
                             failingFirstUnmet=t[near[1]]["firstUnmet"]))
    assert rows, f"no bracket with a passing and a failing value for {base}"
    dt = lambda n: t[n]["params"].get("dt", 1e-4)
    return dict(result="pass", trial=base, metric=t[base]["metric"],
                control=dict(condition=control[1], trial=control[0], rejected=True, firstUnmet=t[control[0]]["firstUnmet"]),
                brackets=rows,
                timestep=dict(coarseS=dt(base), fineS=dt(fine), sameOutcome=bool(t[fine]["passed"]), fineTrial=fine,
                              coarseMetric=t[base]["metric"]["value"], fineMetric=t[fine]["metric"]["value"]))


def qualifications(trials, chain):
    N = lambda prefix, pairs: [(v, prefix + s) for v, s in pairs]
    return {
        "acquisition": qualification(trials, "acquire-nominal", ("acquire-belt-locked (cause isolation)", "Intake belt locked"), [
            ("belt and bumper squeeze", "mm", [(20.0, "acquire-nominal"), (25.0, "acquire-compression-25mm"), (17.5, "acquire-compression-17.5mm"),
                                               (15.0, "acquire-compression-15mm"), (10.0, "acquire-compression-10mm")]),
            ("intake belt speed", "m/s", [(3.0, "acquire-nominal"), (2.5, "acquire-belt-2.5mps"), (2.0, "acquire-belt-2.0mps"), (1.5, "acquire-belt-1.5mps")]),
            ("bumper cover friction", "coefficient", [(0.4, "acquire-nominal"), (0.3, "acquire-bumper-friction-0.3"), (0.2, "acquire-bumper-friction-0.2")]),
            ("back plate friction", "coefficient", [(0.4, "acquire-nominal"), (0.2, "acquire-back-plate-friction-0.2"), (0.1, "acquire-back-plate-friction-0.1")]),
        ], "acquire-nominal-half-step"),
        "entry": qualification(trials, "entry-nominal", ("entry-no-feeder (control)", "No feeder roller: nothing holds the FUEL off the spinning flywheel"), [
            ("stage beam and controller lag", "ms", [(5.0, "entry-nominal"), (20.0, "entry-stage-lag-20ms"), (80.0, "entry-stage-lag-80ms"), (150.0, "entry-stage-lag-150ms")]),
            ("feeder squeeze", "mm", [(D.FEEDER["squeeze"], "entry-nominal"), (8.0, "entry-feeder-squeeze-8mm"), (4.0, "entry-feeder-squeeze-4mm"), (1.0, "entry-feeder-squeeze-1mm")]),
        ], "entry-nominal-half-step"),
        "hold": qualification(trials, "hold-nominal", ("hold-no-feeder (control)", "No feeder roller"), [
            ("push from queued FUEL", "N", [(30.0, "hold-nominal"), (90.0, "hold-queue-push-90N"), (120.0, "hold-queue-push-120N"), (150.0, "hold-queue-push-150N")]),
            ("feeder and deck friction", "coefficient", [(0.9, "hold-nominal"), (0.5, "hold-feeder-friction-0.5-deck-0.3"), (0.2, "hold-feeder-friction-0.2-deck-0.2")]),
        ], "hold-nominal-half-step"),
        "launch": qualification(trials, "launch-nominal", ("launch-feeder-stopped (cause isolation)", "Feeder roller stopped: no feed"), [
            ("flywheel setpoint", "m/s", [(D.SHOOTER["wheel_surface_mps"], "launch-nominal")] + [
                (round(D.SHOOTER["wheel_surface_mps"] + d, 1), f"launch-setpoint-{D.SHOOTER['wheel_surface_mps'] + d:.1f}mps") for d in (-0.3, 0.3, -0.5, 0.5)]),
            ("wheel-to-hood squeeze", "mm", [(12.0, "launch-nominal"), (8.0, "launch-squeeze-8mm"), (16.0, "launch-squeeze-16mm"), (6.0, "launch-squeeze-6mm"), (20.0, "launch-squeeze-20mm")]),
            ("wheel friction", "coefficient", [(0.9, "launch-nominal"), (0.5, "launch-wheel-friction-0.5"), (0.3, "launch-wheel-friction-0.3")]),
            ("contact stiffness", "N/m", [(15000.0, "launch-nominal"), (10000.0, "launch-contact-stiffness-10k"), (30000.0, "launch-contact-stiffness-30k"), (7500.0, "launch-contact-stiffness-7.5k")]),
        ], "launch-nominal-half-step"),
        "batch": qualification(trials, "batch-nominal", ("batch-motors-off (cause isolation)", "Flywheel motors off through the batch"), [
            ("flywheel stator current limit at the weak-pack bus", "A", [(40.0, "batch-weak-pack-8.34V"), (20.0, "batch-stator-limit-20A-weak-pack"), (5.0, "batch-stator-limit-5A-weak-pack")]),
            ("stator current limit with the bare 0.0026 kg m2 roller at the weak-pack bus", "A", [(40.0, "batch-bare-roller-0.0026-wheel-weak-pack"), (20.0, "batch-bare-roller-weak-pack-stator-limit-20A")]),
        ], "batch-nominal-half-step"),
        "delivery": qualification(trials, "deliver-nominal", ("deliver-6.40", "Release 6.40 m/s, below the scoring band"), [
            ("release speed", "m/s", [(round(chain["release"]["speedMps"], 3), "deliver-nominal"), (6.9, "deliver-6.90"), (6.7, "deliver-6.70"), (7.1, "deliver-7.10"),
                                      (6.55, "deliver-6.55"), (7.25, "deliver-7.25"), (7.4, "deliver-7.40")]),
        ], "deliver-nominal-half-step"),
        "hang": qualification(trials, "hang-nominal", ("hang-no-brake (disabled control)", "No brake: the winch coasts with power removed"), [
            ("winch current limit", "A", [(40.0, "hang-nominal"), (30.0, "hang-current-limit-30A"), (20.0, "hang-current-limit-20A"), (15.0, "hang-current-limit-15A"),
                                          (10.0, "hang-current-limit-10A")]),
        ], "hang-nominal-half-step"),
        "hopper": qualification(trials, "hopper-cycle-nominal", ("hopper-collect-24-open-throat-low-entry (control: the earlier issue's fill)",
                                                                  "The earlier issue's intake: FUEL thrown in low through an open throat"), [
            ("floor belt speed", "m/s", [(1.2, "hopper-cycle-nominal"), (0.6, "hopper-cycle-belt-0.6mps"), (0.3, "hopper-cycle-belt-0.3mps")]),
            ("loaded stop, start and turn", "g", [(0.5, "hopper-cycle-pattern-3"), (0.75, "hopper-cycle-0.75g-pattern-3"), (1.0, "hopper-cycle-1g-pattern-3 (adverse)")]),
            ("FUEL collected", "FUEL", [(24.0, "hopper-collect-24-hold"), (27.0, "hopper-collect-27-hold"), (30.0, "hopper-collect-30-hold")]),
            ("carriage nudge in the unjam cycle after a 1 g transit", "mm", [(D.INTAKE["nudge"][0], "hopper-cycle-1g-pattern-2"), (0.0, "hopper-cycle-1g-pattern-2-no-nudge (cause isolation)")]),
        ], "hopper-cycle-nominal-half-step"),
    }


def main():
    global OUT, REL
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", required=True, help="release folder to write (repository-relative)")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--fail-fast", action="store_true")
    ap.add_argument("--previous", help="held checkpoint receipt, repository-relative")
    args = ap.parse_args()
    REL = Path(args.release).as_posix().strip("/")
    OUT = (REPO / REL).resolve()
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
    chain = trial_data["chain"]
    trials_pin = carry("field-trials.json")
    for stale in list((OUT / "transport").glob("*.json")) + list(OUT.glob("trial-*.json")):   # every record is rewritten below
        stale.unlink()
    quals = qualifications(trials, chain)
    strokes = fuel_strokes(trials)
    Y = D.TRACK_Y
    xz = lambda p: (p[0], Y, p[1])
    start = xz(strokes[0][2]["fromMm"])
    seat = xz(next(s for ph, _, s in reversed(strokes) if ph == "stage")["toMm"])   # clamped at the stage
    release_mm = next(s for ph, _, s in strokes if ph == "flight")["fromMm"]
    rel_state = chain["release"]
    # Installed (STEP) pose: where the mission finds it, on the carpet ahead of the intake. The service cases start from
    # the installed scene, so they are checked with the floor lane empty.
    shapes[BALL] = G.sphere(start); groups_of[BALL] = PAYLOAD

    # Stored AUTO preload: stable positions in the starting fold, behind the stowed carriage and clear of every traced
    # position of the tracked FUEL.
    vol = start_volume()
    path_samples = []
    for name in ("entry-nominal", "launch-nominal"):
        for f in trials[name]["frames"]:
            q = (1000 * f[1], Y, 1000 * f[2])
            if not path_samples or math.dist(q, path_samples[-1]) >= 10.0:
                path_samples.append(q)
    columns = [(-342, -263, 80, D.REAR_WALL_X[0] - 3, 190, 4000), (vol["frontMm"] - 2, -275, 100, 620, 275, 800)]   # shooter; the stowed carriage and its travel
    stored = supported_positions(True, extra_exclusions=columns, avoid=path_samples, limit=7)
    assert stored, "no supported stored position"
    for i, p in enumerate(stored, 1):
        shapes[f"FUEL stored {i}"] = G.sphere(p); groups_of[f"FUEL stored {i}"] = "stored FUEL"

    # ---------------------------------------------------------- STEP: the robot package and the field fixtures
    field_m = sorted(field)
    step = write_step("package.step", {n: shapes[n] for n in sorted(shapes) if n not in field}, f"{ISSUE} package")
    fixture_pin = write_step("field-fixtures.step", {n: shapes[n] for n in field_m}, f"{ISSUE} field fixtures")
    fixtures = [dict(id=n, file=fixture_pin, solid=n, basis=FIXTURE_BASIS[n]) for n in field_m]

    design_path = OUT / "design.json"
    if design_path.exists():
        design_path.unlink()
    subprocess.run(["node", str(CLI), "new", str(design_path)], check=True, stdout=subprocess.DEVNULL)
    d = json.loads(design_path.read_text(encoding="utf-8"))
    d["design"]["frameProfile"] = {"kind": "square"}
    d["design"]["parameters"].update(frameLengthM=0.68, frameWidthM=0.714, trackM=0.564, bumperBottomM=0.048,
                                     bumperHeightM=0.12, bumperDepthM=0.0775, height=0.75, reach=0.245,
                                     toolHeight=0.25, opening=0.512, phase="deployed")
    design_path.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8", newline="\n")
    chk = subprocess.run(["node", str(CLI), "validate", str(design_path)], capture_output=True, text=True)
    assert chk.returncode == 0, chk.stderr + chk.stdout
    design = pin("design.json")
    datum = dict(name="R3 robot datum: carpet plane at the frame centre, +X toward the intake, +Y left, millimetres",
                 robotToStepMm=[1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1])

    # ---------------------------------------------------------- groups
    roles = {"frame": "structure", "hopper": "structure", "hopper shelf": "structure", "climber tubes": "structure", "battery retention": "structure",
             "battery strap": "structure", "bumpers": "bumper", "drivetrain": "drive", "battery": "battery", "electrical": "other",
             "floor belts": "mechanism", "feeders": "mechanism", "shooter": "mechanism", "intake": "mechanism", "climber hooks": "mechanism",
             "climber inner tubes": "mechanism", "tracked FUEL": "payload", "stored FUEL": "payload", "field": "other"}
    groups = {g: dict(role=r, members=sorted(n for n, gg in groups_of.items() if gg == g)) for g, r in roles.items()}
    assert set(groups_of.values()) == set(roles), set(groups_of.values()) ^ set(roles)
    G_ = lambda g: groups[g]["members"]

    # ---------------------------------------------------------- cases
    history = {n: [] for n in shapes}
    cases, stages, fuel_index = [], {}, []

    def case(cid, stage, basis, moves, moving_groups, carried=None, initial=None, extra=None, transported=None, free=None):
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
        if free:
            stages[cid]["freePath"] = free
        for n, ops in moves.items():
            history[n] = (initial.get(n) if initial and n in initial else history[n]) + ops
        if initial:
            for n, v in initial.items():
                if n not in moves:
                    history[n] = v
        return c

    def vertex(p):
        return BRepBuilderAPI_MakeVertex(gp_Pnt(*p)).Vertex()

    def resting_rules(centre, solids, where, trial):
        """Compression rules for the staged FUEL standing still, from the entry trial's contacts at rest."""
        rules = []
        peaks = peak_contacts(trial, trial["frames"][-1][0], trial["frames"][-1][0])
        q = vertex(centre)
        for n in solids:
            depth = max(G.R_BALL - dist(q, shapes[n]), peaks.get(n, 0.0))
            if depth > -1.5:   # closer than the reserve a moving case would need
                rules.append(dict(payload=BALL, contact=n, maxDepthMm=round(max(depth, 0.0) + 0.5, 3),
                                  basis=f"The FUEL is clamped against this surface {where}: {max(depth, 0.0):.3f} mm indentation in the trial's penalty "
                                        "contact (15 kN/m estimate, not a measured force-deflection curve), plus 0.5 mm"))
        return rules

    intake = G_("intake")
    shift = list(D.INTAKE["shift"])
    history.update({n: [T([-v for v in shift])] for n in intake})

    case("intake-deploy", "operating", f"Slide the intake carriage {shift[0]:g} mm forward and {-shift[2]:g} mm down from the legal start fold, over the bumper",
         {n: [T(shift)] for n in intake}, ["intake"])
    for n in intake:
        history[n] = []  # the translations cancel; continue from the installed deployed pose

    acq_p, ent_p, lch_p = (trials[n]["params"] for n in ("acquire-nominal", "entry-nominal", "launch-nominal"))
    drive_values = dict(u=acq_p["u"], gear=acq_p["gear"], stator=acq_p["statorA"], supply=acq_p["supplyA"], belt=ent_p["belt"], stage=ent_p["stageMps"],
                        feed=lch_p["feederMps"], wheel=lch_p["wheelMps"], inertia=D.SHOOTER["inertia_kgm2"])
    qual_of = {"acquire-nominal": "acquisition", "entry-nominal": "entry", "launch-nominal": "launch", "deliver-nominal": "delivery"}
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
        support = ("moved by contact with " + " and ".join(sorted(transporters)) if transporters else "no mechanism moves it here: a free path")
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
                 for solid, depth in sorted(peaks.items()) if solid in shapes]
        init_before = list(history[BALL])
        path = dict(case=cid, payload=PAYLOAD, moves={BALL: ops}, initialPose={BALL: init_before})
        if transporters:
            path = dict(case=cid, payload=PAYLOAD, mechanisms=sorted(transporters), moves={BALL: ops}, initialPose={BALL: init_before})
        record = dict(schema="frc-2026-poc/trial-window@1", issue=ISSUE, **{"transport" if transporters else "freePath": path},
                      fieldTrials=trials_pin,
                      trial=dict(name=trial_name, fromS=stroke["fromS"], toS=stroke["toS"], fromPoseMm=list(xz(stroke["fromMm"])),
                                 toPoseMm=list(xz(stroke["toMm"])), stroke=stroke["kind"], maxDeviationMm=round(stroke["deviationMm"], 4),
                                 toleranceMm=TOL_MM, peakIndentationMm={s_: round(v, 3) for s_, v in sorted(peaks.items())}),
                      qualification=quals[qual_of[trial_name]], basis=basis)
        evidence = write(f"transport/{cid}.json", record)
        transported = free = None
        if transporters:
            transported = {PAYLOAD: dict(mechanisms=sorted(transporters), drive={m: t.format(**drive_values) for m, t in transporters.items()},
                                         evidence=evidence, basis=what)}
        else:
            free = {PAYLOAD: dict(evidence=evidence, basis=what)}
        case(cid, "operating", basis, {BALL: ops}, [PAYLOAD], extra=dict(payloadCompression=rules, maxDepth=16) if rules else None,
             transported=transported, free=free)
        fuel_index.append(dict(case=cid, phase=phase, trial=trial_name, fromS=stroke["fromS"], toS=stroke["toS"], stroke=stroke["kind"],
                               maxDeviationMm=round(stroke["deviationMm"], 4), transportedBy=sorted(transporters) if transporters else None,
                               compression={r["contact"]: r["maxDepthMm"] for r in rules}, record=evidence["file"]))
        if phase == "stage" and strokes[index + 1][0].startswith("launch"):
            seat_rules = resting_rules(seat, ["lane deck", "feeder roller left"], "at the stage", trials["entry-nominal"])
            transit = (acq[0], acq[1], 0)
            case("loaded-transit", "operating", "Drive loaded from the DEPOT side of the alliance zone to the shot pose (robot frame: the field moves); "
                 "the staged FUEL stays clamped between the braked feeder roller and the lane deck",
                 {n: [T(transit)] for n in field_m}, ["field"], extra=dict(payloadCompression=seat_rules))
    last = lambda phase: phase_cases[phase][-1]
    world = field_m + [BALL]
    hooks = G_("climber hooks")
    hz = k["hook"] - 6
    yc = 299 + G.DY
    reach = {"climber hook left": [ROT((300, yc, hz), (0, 0, 1), 180)], "climber hook right": [ROT((300, -yc, hz), (0, 0, 1), -180)]}
    case("climb-reach", "operating", "With the hopper empty and the intake still deployed below them, swing both hooks 180 degrees inboard to point forward",
         reach, ["climber hooks"])
    case("intake-stow", "operating", "Slide the empty intake carriage back into the frame between the forward hooks, so nothing stands under the rung",
         {n: [T([-v for v in shift])] for n in intake}, ["intake"])
    case("tower-lateral", "operating", "Drive sideways to the TOWER line",
         {n: [T((0, -tower_y_shot, 0))] for n in world}, ["field", PAYLOAD])
    approach = -(tower_face_shot - 417.5 - 5.0)
    case("tower-forward", "operating", "Close to 5 mm from the uprights; the hook jaws pass over the low rung",
         {n: [T((approach, 0, 0))] for n in world}, ["field", PAYLOAD])
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

    def service(cid, members, group_names, basis, move=(0, 0, 2000), removed=None):
        mv = {n: [T(move)] for n in members}
        c = dict(id=cid, stage="service", basis=basis, moves=mv, minGapMm=1.0, extract=sorted(mv), checkLinearEnvelope=True, fixtures=fixtures)
        if removed:
            c["removed"] = removed
        cases.append(c)
        stages[cid] = dict(purpose="service", movingGroups=group_names, carriedWith={},
                           allowanceBasis="1 mm preliminary reserve during withdrawal")
    cover = G_("hopper shelf") + G_("battery strap")
    service("battery-cover-remove", cover, ["hopper shelf", "battery strap"],
            "Release the battery strap and lift the left shelf panel straight out with it, beside the feeder roller and aft of the stowed hook arm; the 2 m stroke passes the field fixtures' envelope used by the checker")
    service("battery-withdraw", G_("battery"), ["battery"], "With the shelf panel and strap out, lift the battery straight up",
            removed={n: "battery-cover-remove" for n in cover})
    service("shooter-withdraw", G_("shooter"), ["shooter"],
            "Lift the flywheel, inertia ring, hood, side plates and both motors out as one module, with the floor lane empty")

    motion = write("paths.json", dict(schema="agent-frc/mechanical-motion@1", step=step, layoutDesignSha256=design["sha256"],
                                      layoutDatum=datum, cases=cases))

    fxc, fzc = k["feeder"]
    cz = k["c"][1]
    lane = D.HOPPER["lane_half"]
    M = lambda group, on, point, basis, member=None: dict(group=group, on=on, pointMm=[float(v) for v in point], basis=basis, **({"member": member} if member else {}))
    mounts = [
        M("floor belts", "floor pan", (0, 0, k["floor"]), "Belt bed rests on the floor pan"),
        M("feeders", "hopper liner left", (fxc, lane + 1, fzc - 20), "Left roller shaft runs in a bearing block on the channel wall of the left liner; its gearmotor hangs from the same block", "feeder roller left"),
        M("feeders", "hopper liner left", (fxc, lane + 1, fzc - 22), "Gearmotor flange on the bearing block outboard of the channel wall", "feeder motor left"),
        M("feeders", "hopper liner right", (fxc, -lane - 1, fzc - 20), "Right roller shaft runs in a bearing block on the channel wall of the right liner", "feeder roller right"),
        M("feeders", "hopper liner right", (fxc, -lane - 1, fzc - 22), "Gearmotor flange on the bearing block outboard of the channel wall", "feeder motor right"),
        M("shooter", "frame rail rear", (-327, 0, 120.65), "Shooter side plates bolt to the rear rail top"),
        M("intake", "intake slide rail left", (300, 266, 400), "Left carriage plate runs on the two-stage slide; the fixed stage is drawn", "intake carriage plate left"),
        M("intake", "intake slide rail right", (300, -266, 400), "Right carriage plate runs on the two-stage slide; the fixed stage is drawn", "intake carriage plate right"),
        M("intake", "intake carriage plate left", (560, 255, 300), "Belt module frame spans the two carriage plates", "intake belt module"),
        M("intake", "intake carriage plate left", (495.5, 255, 565), "Top roller shaft runs in bearings in the two carriage plates", "intake top roller"),
        M("intake", "intake carriage plate left", (400, 255, 300), "Back plate flanges bolt to the two carriage plates", "intake back plate"),
        M("intake", "intake carriage plate left", (434, 255, 569), "Sensor bracket on the top edge of the left carriage plate", "entry sensor"),
        M("climber inner tubes", "climber tube left", (300, yc, 500), "Inner tube runs in bushings in the fixed outer tube", "climber inner tube left"),
        M("climber inner tubes", "climber tube right", (300, -yc, 500), "Inner tube runs in bushings in the fixed outer tube", "climber inner tube right"),
        M("climber hooks", "climber inner tube left", (300, yc, k["hook"] - 14), "Swing joint on the inner tube top", "climber hook left"),
        M("climber hooks", "climber inner tube right", (300, -yc, k["hook"] - 14), "Swing joint on the inner tube top", "climber hook right"),
        M("battery", "battery retention cleat aft", (-95.0, 291.0, 150.0), "Battery end face captured between the aft and fore cleats, with the strap over its top"),
        M("battery retention", "floor pan", (-95.0, 291.0, 100.0), "Cleat feet riveted to the floor pan top, which rests on the frame rails"),
        M("battery strap", "battery retention cleat aft", (-95.0, 291.0, 199.0), "Strap anchored to the aft cleat and buckled to the fore cleat over the battery top"),
        M("hopper shelf", "hopper liner left", (0.0, lane + 1, D.HOPPER["shelf_z"] - 3), "Shelf panel rests on the channel wall of the left liner and on the side wall, held by two quarter-turn fasteners"),
        M("hopper", "frame rail left", (0.0, 334.0, 120.65), "Side wall foot on the left rail top", "hopper wall left"),
        M("hopper", "frame rail right", (0.0, -334.0, 120.65), "Side wall foot on the right rail top", "hopper wall right"),
        M("hopper", "floor pan", (0.0, lane + 1, k["floor"]), "Channel wall foot on the floor pan", "hopper liner left"),
        M("hopper", "floor pan", (0.0, -lane - 1, k["floor"]), "Channel wall foot on the floor pan", "hopper liner right"),
        M("hopper", "hopper wall left", (D.REAR_WALL_X[1] - 1.5, 334.0, 500.0), "Rear wall flange on the left side wall; its right edge is carried by the right liner's pocket wall", "hopper rear wall"),
        M("climber tubes", "climber tube mount left", (300, yc, 222), "Outer tube socket in the tube mount", "climber tube left"),
        M("climber tubes", "climber tube mount right", (300, -yc, 222), "Outer tube socket in the tube mount", "climber tube right"),
        M("climber tubes", "intake slide rail left", (200, 266.0, 345.0), "Winch plate bolts to the underside of the fixed slide rail, in the bay outboard of the carriage plate; the right cable crosses inside the front rail", "climber winch"),
    ]

    # ---------------------------------------------------------- budgets
    requirements_cases = {}
    loads = {
        # battery-side ampere ranges per source in each stage (conservative bounds, see study)
        "intake-deploy": dict(drive=[10, 60], steer=[2, 8], intake=[5, 25], indexer=[0, 5], flywheel=[0, 5], climber=[0, 0], controls=[3, 6]),
        "acquire": dict(drive=[20, 90], steer=[2, 10], intake=[10, 30], indexer=[2, 12], flywheel=[2, 10], climber=[0, 0], controls=[3, 6]),
        "loaded-transit": dict(drive=[50, 100], steer=[3, 12], intake=[0, 10], indexer=[0, 5], flywheel=[5, 30], climber=[0, 0], controls=[3, 6]),
        "launch": dict(drive=[0, 40], steer=[0, 6], intake=[0, 10], indexer=[5, 15], flywheel=[10, 60], climber=[0, 0], controls=[3, 6]),
        "tower": dict(drive=[20, 90], steer=[2, 10], intake=[0, 2], indexer=[0, 2], flywheel=[0, 5], climber=[0, 2], controls=[3, 6]),
        "climb": dict(drive=[0, 10], steer=[0, 4], intake=[0, 2], indexer=[0, 2], flywheel=[0, 2], climber=[10, 45], controls=[3, 6]),
        "park": dict(drive=[0, 5], steer=[0, 2], intake=[0, 2], indexer=[0, 2], flywheel=[0, 2], climber=[5, 20], controls=[3, 6]),
    }
    stage_load = {"intake-deploy": "intake-deploy", "intake-stow": "intake-deploy", "loaded-transit": "loaded-transit", "tower-lateral": "tower",
                  "tower-forward": "tower", "climb-reach": "climb", "climb-seat": "climb", "climb-lift": "climb", "park-lower": "park", **duty_of}
    need = {"launch": 8.0, "loaded-transit": 7.5, "tower": 7.5, "climb": 7.5, "acquire": 7.5, "intake-deploy": 7.5, "park": 7.0}
    sources = ["drive", "steer", "intake", "indexer", "flywheel", "climber", "controls"]
    lch_demand = trials["launch-nominal"]["wheelDemand"]
    belt = trials["acquire-three-abreast-9V-bus (adverse)"]["beltDemand"]
    spin = chain["spinUp"]
    batch_peak = trials["batch-weak-pack-8.34V"]["batch"]["peakSupplyA"]
    duty_note = {
        "acquire": f". The intake row is its 30 A supply limit: with three FUEL abreast on a 9 V bus the driven belt draws {belt['peakSupplyA']:.0f} A and "
                   f"its speed dips to {belt['minBeltMps']:.2f} m/s, and all three are captured. The flywheel row holds the wheel at speed while FUEL is aboard",
        "loaded-transit": f". The flywheel row covers a spin-up from rest during the transit at 15 A per motor: {spin['transitLimit15A']['seconds']:.1f} s on the weak pack "
                          f"({spin['transitLimit15A']['peakSupplyA']:.0f} A battery-side peak)",
        "launch": f". The flywheel row is two motors at their 30 A supply limit: the weak-pack batch trial peaks at {batch_peak:.0f} A battery-side. One shot takes "
                  f"{lch_demand['energyJ']:.0f} J from the wheel, a {lch_demand['speedDropPercent']:.1f}% speed fall that the motors return before the next feed. "
                  "The indexer row is the floor belt and both feeder gearmotors",
    }
    elec = {}
    for cid in cycle:
        key = stage_load[cid]
        for cond, voc, res in (("nominal", [12.4, 12.8], [0.012, 0.016]), ("weak", [11.9, 12.2], [0.020, 0.026])):
            requirements_cases[f"{cid}-{cond}"] = dict(stage=cid, batteryCondition=cond, sources=sources,
                                                       duty=f"{key} duty during {cid}", requiredMotionMinV=need[key])
            elec[f"{cid}-{cond}"] = dict(basis=f"Simultaneous battery-side bounds for the {key} duty with supply current limits (drive 25 A per module battery-side)" + duty_note.get(key, ""),
                                         loadedKg=None, batterySideA=loads[key], openCircuitV=voc, resistanceOhm=res)
    # Mass. Drawn sheet parts are weighed from their solids; purchased and undrawn items are allocations with a stated basis.
    kg = lambda names, density: sum(volume(shapes[n]) for n in names) / 1e6 * density
    fb = D.flywheel_build()
    plates_kg = kg([n for n in G_("shooter") if "side plate" in n], 2.70)
    hood_kg = kg(["hood"], 2.70)
    # Side plates are drawn as 8 mm envelopes and allocated as 4.76 mm (3/16 in) plate with 30 to 50% pocketed out.
    side_kg = [round(plates_kg * 4.76 / 8 * 0.5, 2), round(plates_kg * 4.76 / 8 * 0.7, 2)]
    shooter_kg = [round(fb["kg"] + side_kg[0] + hood_kg + 0.9 + 0.3, 2), round(fb["kg"] * 1.05 + side_kg[1] + hood_kg + 1.2 + 0.6, 2)]
    shooter_basis = (f"Flywheel as built in dimensions.py: {fb['kg']:.2f} kg for {fb['inertia']:.4f} kg m2 (aluminum tube roller {fb['tubeKg']:.2f} kg, tread "
                     f"{fb['treadKg']:.2f} kg, one steel inertia ring {fb['ringKg']:.2f} kg on a {fb['webKg']:.2f} kg web, hubs {fb['hubKg']:.2f} kg), plus 5% high. "
                     f"Two side plates allocated as 4.76 mm aluminum with 30 to 50% pocketed out, {side_kg[0]:.2f}-{side_kg[1]:.2f} kg (the drawn 8 mm envelopes would weigh {plates_kg:.2f} kg solid). "
                     f"Hood {hood_kg:.2f} kg. Two flywheel motors 0.9-1.2 kg. Shaft, bearings and fasteners 0.3-0.6 kg")
    hopper_names = G_("hopper") + G_("hopper shelf")
    # Walls are drawn 3 mm thick and liners 2 mm; both are allocated as 1.5 mm polycarbonate with folded edges.
    walls_pc = kg(["hopper wall left", "hopper wall right", "hopper rear wall"], 1.20) * 1.5 / 3
    liners_pc = kg(["hopper liner left", "hopper liner right", "hopper shelf left"], 1.20) * 1.5 / 2
    hopper_pc = walls_pc + liners_pc
    hopper_kg = [round(hopper_pc + 0.3, 2), round(hopper_pc * 1.1 + 0.6, 2)]
    plate_kg = kg([n for n in G_("intake") if "carriage plate" in n], 2.70)
    # Carriage plates are drawn as 10 mm envelopes and allocated as 3 mm plate with 25 to 40% pocketed out.
    carriage_kg = [round(plate_kg * 0.3 * 0.6, 2), round(plate_kg * 0.3 * 0.75, 2)]
    intake_kg = [round(2.8 + 0.25 + 0.4 + carriage_kg[0], 2), round(3.6 + 0.4 + 0.6 + carriage_kg[1], 2)]
    cleat_cm3 = sum(volume(shapes[n]) for n in G_("battery retention")) / 1000
    cleat_hi = round(cleat_cm3 * 2.70 / 1000, 3)   # solid 6061 at 2.70 g/cm3
    cleat_lo = round(cleat_hi * 0.5, 3)            # formed-angle cleats occupy about half the drawn block
    deck_kg = kg(["lane deck"], 2.70)
    mass_rows = [
        ("frame and floor", G_("frame"), [round(5.2 + deck_kg, 2), round(6.4 + deck_kg, 2)], f"Four 2x1x0.125 in 6061 rails (2.72 m at 1.20 kg/m), 3 mm polycarbonate floor (about 0.4 m2), slide rails, tube mounts, gussets, and the 3 mm aluminum lane deck ({deck_kg:.2f} kg as drawn). The front lip of the earlier issue is removed"),
        ("hopper walls and liners", hopper_names, hopper_kg, f"Two side walls and the rear wall (drawn 3 mm) and two formed liners and the battery shelf panel (drawn 2 mm), all allocated as 1.5 mm polycarbonate: {walls_pc:.2f} kg of walls and {liners_pc:.2f} kg of liners at 1.2 g/cm3, plus 0.3-0.6 kg of edge stiffeners and fasteners and 10% high. The front upper wall of the earlier issue is removed"),
        ("drivetrain", G_("drivetrain"), [8.9, 9.7], "Four MAXSwerve corners: 1.720 kg purchased assembly each (foundation reconciliation), 6.88 kg, plus four drive motors at 0.43 kg and four steering motors at 0.14 kg, 2.28 kg; 0.25 kg low for the lighter wheel option and 0.5 kg high for fasteners and encoders cables"),
        ("floor indexer", G_("floor belts"), [1.2, 1.9], "Two flat belt runs 332 mm wide in the channel, rollers, one motor and gearbox"),
        ("feeders", G_("feeders"), [1.2, 1.7], "Two 2 in compliant rollers on 12 mm shafts (0.30-0.40 kg each), two planetary gearmotors with brakes (0.25-0.40 kg each), bearing blocks 0.1 kg"),
        ("shooter", G_("shooter"), shooter_kg, shooter_basis),
        ("intake", G_("intake"), intake_kg, f"Vertical belt module with internal motor and top roller as in the earlier issue (2.8-3.6 kg), 130 mm more belt and frame (0.25-0.4 kg), the back plate as a folded 1 mm aluminum wedge (0.4-0.6 kg), and two carriage plates allocated as 3 mm aluminum with 25 to 40% pocketed out, {carriage_kg[0]:.2f}-{carriage_kg[1]:.2f} kg (the drawn 10 mm envelopes would weigh {plate_kg:.2f} kg solid)"),
        ("climber", G_("climber tubes") + G_("climber inner tubes") + G_("climber hooks"), [3.0, 3.9], "Two telescoping tube pairs, hooks with swing actuators inside the inner tubes, winch and cables"),
        ("electrical and controls", G_("electrical"), [4.3, 5.4], "Power distribution, controller, radio, 17 motor controllers, breaker, three beam sensors, wiring on the panels under the right shelf and in the right bay"),
        ("bumpers (excluded by R103)", G_("bumpers"), [0.0, 0.0], "R103 excludes bumpers; 6.0-7.5 kg carried in the running payload and in the R408 check"),
        ("battery (excluded by R103)", G_("battery"), [0.0, 0.0], "R103 excludes the battery and its connector half; 5.0-6.9 kg (V0 battery 4.99-6.57 kg plus leads) carried in the running payload"),
        ("field fixtures (not robot)", field_m, [0.0, 0.0], "HUB and TOWER references are field equipment"),
        ("unmodeled robot hardware", [], [3.0, 4.5], "Fasteners, brackets, cable chain, camera and spares not yet drawn. The upper bound falls 0.5 kg from the earlier issue: the feeder mounts, battery strap, lane deck and liner joints it covered are now drawn and weighed in their own lines"),
        ("battery retention", G_("battery retention") + G_("battery strap"), [round(cleat_lo + 0.05, 3), round(cleat_hi + 0.10, 3)], f"Two cleat envelopes, {cleat_cm3:.1f} cm3: high as solid 6061 at 2.70 g/cm3, low at half fill for formed angle; rivets inside. Webbing strap and buckle 0.05-0.10 kg"),
    ]
    payload = [6.0 + 5.0 + 24 * 0.203, 7.5 + 6.9 + 24 * 0.227]
    inspection = [sum(r[2][0] for r in mass_rows), sum(r[2][1] for r in mass_rows)]
    running = [inspection[0] + payload[0], inspection[1] + payload[1]]
    assert inspection[1] < 52.16, f"inspection upper bound {inspection[1]:.2f} kg"
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
        masses=[dict(id=i, members=m, kg=kg_, basis=b) for i, m, kg_, b in mass_rows], electricalCases=elec))

    # ---------------------------------------------------------- premises and measurements
    import bump_crossing
    bump = bump_crossing.screen(k["floor"])
    robot_members = [n for n, g in groups_of.items() if roles[g] not in ("payload", "other", "bumper")] + G_("electrical")
    sweep = swept_envelope(cases, shapes, robot_members)
    deployed_reach = max(bounds(s_)[3] for n, (s_, g) in bodies.items() if g != "bumpers") - 340.0
    release_distance = (release_mm[0] - hub_shot[0]) / 1000
    patterns = [t for n, t in trials.items() if n == "hopper-cycle-nominal" or n.startswith("hopper-cycle-pattern-")]
    collect = trials["hopper-collect-24-hold"]["feed"]
    carried = collect["inHopper"] + min(collect["heldInChute"], 4)
    measured = dict(issue=ISSUE, designSha256=design["sha256"], stepSha256=step["sha256"],
                    startOverhangMm=round(sweep["startOverhang"], 3), sweptTopMm=round(sweep["top"], 3),
                    sweptFrontExtensionMm=round(sweep["front"], 3), sweptOtherExtensionMm=round(max(sweep["rear"], sweep["side"]), 3),
                    sidesExtendedMax=float(sweep["maxSides"]), sweptWorst=sweep["worst"], deployedReachMm=round(deployed_reach, 3),
                    carriedInCollectTrial=float(carried), cyclePatternsFed24=float(sum(1 for t in patterns if t["passed"])), cyclePatterns=float(len(patterns)),
                    volumeEstimateStowedLow=vol["estimateAtPacking"]["0.45"],
                    releaseDistanceM=round(release_distance, 4), deliveryPoseM=round(-hub_shot[0] / 1000, 4),
                    withBumpersUpperKg=round(inspection[1] + 7.5, 3), bellyClearanceMm=k["floor"] - 6.0,
                    bumpCrossingClearanceMm=bump["minClearanceMm"], bumpCrossingLimit=bump["limitingFeature"],
                    bumperUprightOverlapMm=round(G.HALF_W + 76.5 - 819.15 / 2, 2),
                    basis="Measured by build_package.py from the solids it writes to package.step and the cases it writes to paths.json. Extensions sample every robot member except bumpers at 49 fractions of each operating and park case. The carried count is the hopper-collect-24-hold trial's FUEL in the hopper plus at most four waiting in the chute; the start capacity is the free volume behind the stowed back plate at a 0.45 packing fraction. The release distance is the launch trial's release point to the HUB centre.")
    rules = carry("construction-rules.json")
    strategy = carry("kickoff/selected-strategy.json", REPO / "kickoff/selected-strategy.json")
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
        ("hopper-capacity", "FUEL", [24.0, 200.0], "carriedInCollectTrial", "Selected own-zone batch of 24 collected through the intake chute and held: FUEL in the hopper plus at most four waiting in the chute", "conceptual-design", ["hopper", "intake", "floor belts", "feeders"], strategy, "24-piece serial batch"),
        ("start-capacity", "FUEL", [8.0, 200.0], "volumeEstimateStowedLow", "AUTO preload of eight in the starting fold behind the stowed intake, at a loose 0.45 packing fraction", "conceptual-design", ["hopper", "intake"], strategy, "Begin legally preloaded with at most eight"),
        ("shot-window", "m", [2.4, 3.6], "releaseDistanceM", "Release-to-HUB distance with an entry band under all drag and spin corners", "preliminary-design", ["shooter"], pin("ballistics.json"), "ballistics.json at the launch trial's 0.267 m release: every drag and spin corner enters from 2.4 m with a 0.15 m/s band (0.03 m/s at 2.2 m)"),
        ("delivery-pose", "in", [32.0, 49.0], "deliveryStandoffIn", HELD_SCENARIO, "conceptual-design", ["shooter", "drivetrain"], delivery_evidence, "Every B2 blue-hub attempt in the re-run series r3-2p7m stands 32.2004-48.6491 in from the station centre (AUTO step 32.2004, depot step 48.6491), inside 49 in (3 in within the 52 in release radius); the scenario text is the held R3-PD1 identity, whose 2.16 m refers to the original rehearsal; the step stands 2.70 m from the HUB centre and costs no FUEL against the deconflicted baseline (124 vs 124)"),
        ("delivery-hub-distance", "m", [2.6, 2.8], "deliveryPoseM", "Robot-centre distance from the HUB centre at every slot 2 delivery step in the re-run rehearsal", "conceptual-design", ["shooter", "drivetrain"], pin("rehearsal/comparison.json"), "The robust shot band at 62 degrees is 0.15 m/s wide from 2.4 m release distance"),
        ("bump-crossing", "mm", [5.0, 500.0], "bumpCrossingClearanceMm", "Side-view BUMP crossing with the intake retracted: least clearance of any underside feature over the sharp 15 degree crest", "conceptual-design", ["frame", "drivetrain", "bumpers"], pin("bump_crossing.py"), "Accepted margin 5 mm over a conservative sharp crest; bump_crossing.py"),
        ("hang-bumper-overlap", "mm", [20.0, 200.0], "bumperUprightOverlapMm", "Lateral overlap of the bumper with each TOWER upright face while hanging", "preliminary-design", ["bumpers", "frame", "climber hooks"], rules, "Uprights 819.15 mm apart; a 20 mm overlap tolerates driver alignment error"),
    ]
    for old in OUT.glob("premise-*.json"):
        old.unlink()
    premises = []
    for pid, unit, rng, field_name, scen, phase, ifaces, src, basis in specs:
        identity = dict(id=pid, unit=unit, scenario=scen)
        extra = dict(fieldInput=field_input, repeat=dict(previousPlanSha256=held_plan)) if pid == "delivery-pose" else {}
        acc = write(f"premise-{ISSUE}-{pid}-accepted.json", dict(**identity, criterion={"range": rng}, phase=phase, interfaces=ifaces, source=src, basis=basis, **extra))
        cur = write(f"premise-{ISSUE}-{pid}-current.json", dict(**identity, value=measured[field_name], issue=ISSUE, designSha256=design["sha256"],
                                                          stepSha256=step["sha256"], source=current_src, valueField=field_name))
        premises.append(dict(accepted=acc, current=cur))

    shutil.copyfile(REPO / "kickoff/selected-strategy.md", OUT / "narrative.md")
    narrative = pin("narrative.md")

    # ---------------------------------------------------------- trial records for interactions no single stroke carries
    tr = trials
    band = chain["scoringBandMps"]
    def trial_record(name, cid, kind, what, names, summary):
        return write(name, dict(schema="frc-2026-poc/trial-record@1", issue=ISSUE, case=cid, interaction=what, fieldTrials=trials_pin,
                                trials=names, summary=summary, qualification=quals[kind]))
    cyc_times = sorted(t["feed"]["lastFedS"] for t in patterns)
    cyc_push = max(t["feed"]["peakPushOnStagedN"] for t in patterns)
    hold_q, hop_q = quals["hold"], quals["hopper"]
    bnb = tr["batch-nominal"]["batch"]; bwk = tr["batch-weak-pack-8.34V"]["batch"]
    hang = tr["hang-nominal"]
    records = dict(
        hold=trial_record("trial-hold.json", "loaded-transit", "hold", "Hold the staged FUEL clear of the spinning flywheel through the loaded transit",
                          [n for n in tr if n.startswith("hold-")],
                          dict(leastClearanceMm=tr["hold-nominal"]["metric"]["value"], creepMm=tr["hold-nominal"]["creepMm"],
                               condition=tr["hold-nominal"]["imposed"])),
        hopper=trial_record("trial-hopper-cycle.json", last("launch-feed"), "hopper",
                            "Collect 24 FUEL through the chute, hold them through a 0.5 g stop, start and turn, and feed them all to the flywheel",
                            [n for n in tr if n.startswith("hopper-")],
                            dict(patterns=len(patterns), patternsPassing=sum(1 for t in patterns if t["passed"]), seconds24Fed=[cyc_times[0], cyc_times[-1]],
                                 ratePerS=[round(24 / cyc_times[-1], 2), round(24 / cyc_times[0], 2)], peakPushOnStagedN=cyc_push,
                                 unjamCycles=[min(t["feed"]["unjamCycles"] for t in patterns), max(t["feed"]["unjamCycles"] for t in patterns)],
                                 collect24=dict(inHopper=collect["inHopper"], inChute=collect["heldInChute"]),
                                 condition=tr["hopper-cycle-nominal"]["imposed"])),
        batch=trial_record("trial-batch.json", last("launch-wrap"), "batch", "Launch 24 FUEL through the one flywheel at 4 FUEL/s inside the scoring band",
                           [n for n in tr if n.startswith("batch-")],
                           dict(scoringBandMps=band, releaseSpeedMps=bnb["releaseSpeedMps"], weakPackReleaseSpeedMps=bwk["releaseSpeedMps"],
                                ratePerS=tr["batch-nominal"]["metric"]["value"], peakSupplyA=bnb["peakSupplyA"], flywheel=chain["flywheel"], spinUp=chain["spinUp"])),
        hang=trial_record("trial-hang.json", "climb-lift", "hang", "Lift the robot 70 mm on the low rung and hold it for 3 s with power removed",
                          [n for n in tr if n.startswith("hang-")],
                          dict(massKg=D.HANG_MASS_KG, minClearanceM=hang["metric"]["value"], cableLiftPeakN=hang["cable"]["liftPeakN"], cableHoldN=hang["cable"]["holdN"],
                               limits=hang["limits"])),
    )

    # ---------------------------------------------------------- risk register and bench tests
    acq_q, ent_q, lch_q = quals["acquisition"], quals["entry"], quals["launch"]
    B_ = lambda q, name: next(b for b in q["brackets"] if b["input"] == name)
    wheel = tr["launch-nominal"]["wheelDemand"]
    reserve = 52.16 - inspection[1]
    weak = None  # filled from the receipt after the check; the ledger margin is quoted in the gates text below
    hard = {g: [n for n in tr if n.startswith(f"hopper-cycle-{g}-pattern") and "no-nudge" not in n] for g in ("0.75g", "1g")}
    g_text = "; ".join(f"at {g[:-1]} g {sum(1 for n in names if tr[n]['passed'])} of {len(names)} tested patterns keep and feed all 24" for g, names in hard.items())
    g_text = "Harder stops are tested on single patterns only: " + g_text
    no_nudge = tr["hopper-cycle-1g-pattern-2-no-nudge (cause isolation)"]
    risks = [
        dict(id="flywheel-droop", risk="The flywheel slows under each shot and through a batch, and the release leaves the scoring band",
             closedBy=f"Flywheel a free {fb['inertia']:.4f} kg m2 body (roller plus one inertia ring, {fb['kg']:.2f} kg) under two motors and a speed loop, fed only inside a 1% ready band: "
                      f"one shot takes {wheel['energyJ']:.0f} J and drops the wheel {wheel['speedDropPercent']:.1f}%; 24 FUEL at 4 FUEL/s release at {bnb['releaseSpeedMps'][0]:.2f}-{bnb['releaseSpeedMps'][1]:.2f} m/s on a 12 V bus and "
                      f"{bwk['releaseSpeedMps'][0]:.2f}-{bwk['releaseSpeedMps'][1]:.2f} m/s on the 8.34 V weak-pack bus, inside the {band[0]:.3f}-{band[1]:.3f} m/s band (batch trials)"),
        dict(id="shot-calibration", risk="The model's wheel-to-FUEL speed transfer, drag and spin lift are estimates, so the setpoint that centres the release in the band is not known",
             benchTest=dict(measure="FUEL scored of 20 launched from the 2.7 m pose, with every measured release speed of a 24 FUEL batch inside the band found on the bench", **{"pass": 19, "fail": 18}, unit="FUEL")),
        dict(id="hold-back", risk="A staged FUEL is pushed into the spinning flywheel with no feed commanded",
             closedBy=f"One braked feeder roller per lane over a fixed lane deck, {D.FEEDER['squeeze']:g} mm squeeze, floor belt ending ahead of the staged FUEL and stopped while both lanes are staged: "
                      f"the hold trial keeps the FUEL {tr['hold-nominal']['metric']['value']:.1f} mm clear under a {B_(hold_q, 'push from queued FUEL')['passing']:g} N push at 1.5 g and fails at "
                      f"{B_(hold_q, 'push from queued FUEL')['failing']:g} N. In the {len(patterns)} collect-hold-feed patterns the push on a staged FUEL peaks at {cyc_push:.0f} N (20 ms mean), "
                      + ("above" if cyc_push > B_(hold_q, 'push from queued FUEL')['passing'] else "inside") + " the steady push the hold trial passes, as FUEL land on the heap, and no pattern feeds uncommanded; "
                      "the bench tests hold-back-force and uncommanded-feed-bench measure the margin"),
        dict(id="hold-back-force", risk="The hold rests on foam friction and stiffness that are estimates (0.9 and 0.6, 15 kN/m)",
             benchTest=dict(measure="Steady push on a staged FUEL that the braked feeder holds without the FUEL reaching the wheel", **{"pass": 90, "fail": 60}, unit="N")),
        dict(id="intake-power", risk="The intake belt cannot hold its speed under the acquisition load at its current limit",
             closedBy=f"Belt driven in the trial by one motor at 2:1 with a 30 A supply limit: three FUEL abreast on a 9 V bus dip it to {belt['minBeltMps']:.2f} m/s and are captured; "
                      f"the trial captures down to {B_(acq_q, 'intake belt speed')['passing']:g} m/s and fails at {B_(acq_q, 'intake belt speed')['failing']:g} m/s"),
        dict(id="acquisition-pinch", risk="Capture depends on the belt squeeze and on cover and back plate friction, which are estimates",
             benchTest=dict(measure="Floor FUEL thrown over the back plate within 1.2 s, of 20, at 17.5, 20 and 25 mm squeeze with the belt at or above 2.5 m/s", **{"pass": 20, "fail": 19}, unit="FUEL")),
        dict(id="batch-collection", risk="A batch of 24 cannot be collected: thrown in low through an open throat, the hopper stalls with FUEL backing out into the intake",
             closedBy=f"The intake is a chute that lifts each FUEL up its own back plate to {D.INTAKE['back_top']:g} mm and throws it in over the top; the back plate closes the hopper front. "
                      f"Collect trial: {collect['inHopper']} in the hopper and {collect['heldInChute']} in the chute of 24; collecting {B_(hop_q, 'FUEL collected')['failing']:g} leaves more than four in the chute (bracket). "
                      "The earlier issue's low entry fails the same trial (control)"),
        dict(id="batch-feed", risk="The collected heap bridges or strands FUEL and the feed falls below 2.00 FUEL/s",
             closedBy=f"Two-lane channel with the belt running to the front rail, sloped shelves, feeder rollers standing in the hopper and meeting at the centre line, one stage beam per lane, a belt reversal and a "
                      f"{D.INTAKE['nudge'][0]:g} mm carriage nudge in the unjam cycle: {sum(1 for t in patterns if t['passed'])} of {len(patterns)} collect-hold-feed patterns feed all 24 in {cyc_times[0]:.1f}-{cyc_times[-1]:.1f} s "
                      f"({24 / cyc_times[-1]:.1f}-{24 / cyc_times[0]:.1f} FUEL/s)"),
        dict(id="feed-rate-bench", risk="Heap behaviour varies from run to run and rests on FUEL-to-FUEL and wall friction estimates; the slowest pattern feeds 24 in "
                                        f"{cyc_times[-1]:.1f} s against 12 s",
             benchTest=dict(measure="FUEL fed to the flywheel within 12 s of the first feed command, 24 collected through the chute, in each of 5 runs", **{"pass": 22, "fail": 21}, unit="FUEL")),
        dict(id="loaded-driving", risk="A hard stop can throw FUEL forward over the chute, which is open above the top roller. " + g_text,
             benchTest=dict(measure="FUEL leaving the robot across ten stops from 3 m/s and five turns at the loaded acceleration limit of 0.5 g with 24 aboard", **{"pass": 0, "fail": 1}, unit="FUEL")),
        dict(id="uncommanded-feed-bench", risk="A FUEL reaches the flywheel while collecting or driving",
             benchTest=dict(measure="Uncommanded feeds in 20 collect-and-drive cycles of 24 FUEL", **{"pass": 0, "fail": 1}, unit="feeds")),
        dict(id="mass-reserve", risk=f"The inspection weight estimate tops out {reserve:.2f} kg under the 52.16 kg limit",
             benchTest=dict(measure="Weighed inspection weight of the robot without bumpers and battery", **{"pass": 52.16, "fail": 52.17}, unit="kg")),
        dict(id="hang-squaring", risk="The robot hangs yawed or offset and a bumper misses an upright",
             benchTest=dict(measure="Least clearance to the carpet and TOWER BASE through the 3 s hold, at 70.3 kg, seated at 0 and at 20 mm lateral offset each way", **{"pass": 5, "fail": 0}, unit="mm")),
        dict(id="hang-with-fuel", risk="The intake cannot stow with FUEL in the front of the hopper, and deployed it stands under the rung",
             closedBy="The hang sequence swings the hooks forward first, then stows the empty intake between them, then closes on the TOWER (cases climb-reach, intake-stow, tower-forward, checked). "
                      "The stow is commanded only with the chute and both stage beams clear; with FUEL aboard the robot keeps shooting and does not hang, which is the strategy's own rule"),
        dict(id="bump-clearance", risk=f"The front bumper corner clears the BUMP crest by {bump['minClearanceMm']:.1f} mm in the static screen",
             benchTest=dict(measure="Least clearance of any part other than wheels and bumpers over the BUMP in ten crossings each way, intake retracted", **{"pass": 5, "fail": 0}, unit="mm")),
        dict(id="battery-strap", risk="The battery has no hold-down",
             closedBy="A strap over the battery top between the two cleats is drawn and mounted, and the shelf panel above it covers it; the service cases remove the panel and strap, then lift the battery (checked)"),
        dict(id="unregistered-joints", risk="Members carried no registered joint to the frame",
             closedBy="Each separately mounted member has its own mount entry: both feeder rollers and motors, both carriage plates, both inner tubes, both hooks, both climber tubes, the winch, the side walls, liners, rear wall, shelf panel and strap"),
        dict(id="weak-battery-margin", risk="The loaded-transit duty leaves the smallest voltage margin on a weak battery",
             benchTest=dict(measure="Minimum bus voltage through a loaded transit with the flywheel spinning up, on a battery at 0.026 ohm", **{"pass": 7.5, "fail": 7.0}, unit="V")),
        dict(id="carriage-nudge", risk="The unjam cycle's carriage nudge has to push the back plate into the FUEL at the hopper front. In the recorded trials the pattern run without the nudge "
                                       + ("also feeds all 24, so the trials do not show the nudge is needed" if no_nudge["passed"] else "strands FUEL at the front and the same pattern with the nudge feeds all 24"),
             benchTest=dict(measure="Arches at the hopper front cleared by one 40 mm nudge, of 10 set by hand with 24 FUEL aboard", **{"pass": 10, "fail": 9}, unit="arches")),
        dict(id="bump-crossing-dynamic", risk="Driving over the BUMP at speed with stored FUEL is not evaluated",
             benchTest=dict(measure="FUEL leaving the robot in ten BUMP crossings each way at 1.5 m/s with 24 aboard and the intake retracted", **{"pass": 0, "fail": 1}, unit="FUEL")),
        dict(id="loaded-robot-contact", risk="Robot-to-robot contact while carrying FUEL is not evaluated",
             benchTest=dict(measure="FUEL leaving the robot in five 1 m/s bumper-to-bumper contacts on each side with 24 aboard", **{"pass": 1, "fail": 2}, unit="FUEL")),
    ]
    write("verification-gates.json", dict(schema="frc-2026-poc/verification-gates@2", issue=ISSUE,
          basis="Each open risk of the preliminary design is closed by a design change that a trial or a checked case shows, or carried as a bench test with a pass and a fail value. Bench results are not required to accept the preliminary design; a failed bench test reopens it.",
          risks=risks))

    # ---------------------------------------------------------- narrative coverage, from the trial results
    cap_s = tr["acquire-nominal"]["metric"]["value"]
    seat_s = tr["entry-nominal"]["metric"]["value"]
    gates = "Bench tests are listed in verification-gates.json and in the risk register of missions.json."
    obj_auto = "AUTO: start with up to eight supported FUEL and score from a legal launch pose while the HUB is active"
    obj_collect = "Inactive shift: collect and hold the next allocated stock from the DEPOT, OUTPOST or a partner"
    obj_carry = "Active shift: carry each FUEL from storage through one transfer into the HUB"
    obj_rate = "Active shift: sustain 2.00 FUEL/s to score 24 with stock ready by second 5"
    obj_traffic = "Traffic: remain in the own zone, keep possession through loaded driving and contact, and yield"
    obj_hang = "End game: Level 1 low-rung hang when its expected 10 points exceed the remaining FUEL service"
    objectives = [
        (obj_auto, "represented",
         f"The starting fold holds {measured['volumeEstimateStowedLow']:.0f} or more FUEL by free volume behind the stowed intake (start-capacity premise), and the hopper-cycle-8-preload trial feeds eight from the hopper; the launch and flight cases carry a FUEL into the HUB opening from the 2.7 m pose that the re-run rehearsal credits in AUTO (delivery-pose premise). Delivering from 2.70 m costs no FUEL: slot 2 credits 124 in both the baseline and R3 series."),
        (obj_collect, "represented",
         f"The acquire cases take a floor FUEL up the bumper face and the chute back plate and over its top along the acquisition trial's trace (inside the frame in {cap_s:.2f} s); the hopper and stage cases follow the entry trial to the stage, clamped under the feeder roller {seat_s:.2f} s later. The hopper-collect-24-hold trial collects 24 through the chute: {collect['inHopper']} in the hopper and {collect['heldInChute']} in the chute, none lost and none at the flywheel (hopper-capacity premise)."),
        (obj_carry, "represented",
         f"loaded-transit, the launch cases and the flight cases carry the tracked FUEL from the stage into the HUB cavity along the launch and delivery trials' traces. The feeder advances it only with the wheel in its ready band; it releases at {rel_state['speedMps']:.2f} m/s and {rel_state['elevationDeg']:.1f} degrees, and the delivery trials score from {band[0]:.3f} to {band[1]:.3f} m/s at the nominal drag and spin lift and at all four corners."),
        (obj_rate, "represented",
         f"The batch trial launches 24 FUEL through the one flywheel at {tr['batch-nominal']['metric']['value']:.1f} FUEL/s, every release inside the scoring band, on a 12 V and on the 8.34 V weak-pack bus. The hopper cycle trial feeds 24 collected FUEL to the flywheel in {cyc_times[0]:.1f}-{cyc_times[-1]:.1f} s over {len(patterns)} arrival patterns ({24 / cyc_times[-1]:.1f}-{24 / cyc_times[0]:.1f} FUEL/s against 2.00), so the hopper, not the flywheel, sets the rate. The wheel spins up in {spin['nominal']['seconds']:.1f} s ({spin['weakPack']['seconds']:.1f} s on the weak pack) and is held at speed while FUEL is aboard. " + gates),
        ("Fallback: score the available batch when supply or traffic consumes the window and return to collecting", "represented",
         "The cycle is piece-count independent: the hopper-cycle-8-preload trial feeds a part batch; the intake stays deployed in every scoring case; the re-run rehearsal keeps the depot loop."),
        (obj_traffic, "represented",
         f"The hopper front is closed by the deployed intake's back plate to {D.INTAKE['back_top']:g} mm and the walls rise to 715 mm. Every collect-hold-feed pattern carries its 24 FUEL through a 0.5 g stop, start and turn with none lost. {g_text}. Loaded acceleration is limited to 0.5 g. The staged FUEL is clamped under a braked feeder roller: the hold trial keeps it {tr['hold-nominal']['metric']['value']:.1f} mm clear of the spinning wheel at 1.5 g with a {B_(hold_q, 'push from queued FUEL')['passing']:g} N push. " + gates),
        ("Neutral collector alternative with two field crossings", "out-of-scope",
         f"The coordinator selected the own-zone role. R3 keeps a BUMP crossing option (bump-crossing premise, {measured['bumpCrossingClearanceMm']:.1f} mm least clearance) with the intake retracted."),
        (obj_hang, "represented",
         f"With the hopper empty the hooks swing forward, the intake stows between them, the robot closes on the TOWER, seats (2 mm required contact) and lifts 70 mm; the 714 mm frame gives 23.9 mm of bumper overlap with each upright (hang-bumper-overlap premise); the hang physics trial at {D.HANG_MASS_KG} kg holds {1000 * hang['metric']['value']:.1f} mm with the brake and fails without it; its cable load peaks at {hang['cable']['liftPeakN']:.0f} N in the lift and settles at {hang['cable']['holdN'][1]:.0f} N. " + gates),
        ("AUTO Level 1 TOWER (15 points, two-robot cap)", "out-of-scope",
         "The strategy keeps the eight-FUEL AUTO objective; no joined AUTO climb evidence is sought in this layout."),
        ("Reserve the depot entrance and partner lane", "out-of-scope",
         "Alliance routing decision owned by the field rehearsal, independent of the robot layout."),
        ("Measurement: observe intake crossing, retained identity, release and downstream crossing on one timebase", "represented",
         "An entry sensor on the carriage watches the top of the chute and a stage beam watches each lane at the feeder; the HUB counter is field equipment."),
    ]
    explain = component_explanations(shapes, groups_of, roles, k, trials, quals, fb)
    view = rel("package-motion.html")
    wrap_hood = [(row["compression"].get("hood", 0), row["case"]) for row in fuel_index if row["phase"] == "launch-wrap" and "hood" in row["compression"]]
    control_case = max(wrap_hood)[1]
    uncovered = [dict(id=r["id"], condition=r["benchTest"]["measure"], reason=r["risk"]) for r in risks if r["id"] in ("bump-crossing-dynamic", "loaded-robot-contact")]
    plan = dict(schema="agent-frc/preliminary-layout@1", issue=ISSUE, design=design, step=step, motion=motion, datum=datum,
                groups=groups, mounts=mounts, stages=stages, missingInputs=[],
                control=dict(case=control_case, displaced="hood", moving=BALL, offsetMm=[0, 0, 8],
                             basis="Raise the hood 8 mm, as a mislocated hood mount would, so it squeezes the FUEL beyond the launch trial's indentation in the wrap"),
                cycle=cycle, view=view, budgets=budgets, premises=premises,
                narrativeReview=dict(source=narrative, objectives=[dict(objective=o, disposition=s, basis=b) for o, s, b in objectives]),
                presentation=dict(components=explain,
                                  required={"wheels": [n for n in shapes if "wheel azimuth" in n], "drive and steering actuators": [n for n in shapes if "module motors" in n],
                                            "control computer, power distribution, main disconnect and radio": ["electronics panel", "electronics panel left", "electronics bay right"],
                                            "supply": ["battery"], "game piece": [BALL] + [n for n in shapes if n.startswith("FUEL stored")]},
                                  loadMembers={"drive": [n for n in shapes if "module body" in n or "module motors" in n], "steer": [n for n in shapes if "module motors" in n],
                                               "intake": ["intake belt module", "intake top roller", "intake slide rail left", "intake slide rail right"],
                                               "indexer": ["floor belt main", "floor belt front"] + G_("feeders"),
                                               "flywheel": ["flywheel motor left", "flywheel motor right", "flywheel", "flywheel inertia ring"],
                                               "climber": hooks + G_("climber inner tubes") + ["climber winch"],
                                               "controls": ["electronics panel", "electronics panel left", "electronics bay right"]},
                                  architecture="R3 · tall floor-fed hooded-flywheel shooter with a chute intake on a 680 × 714 mm four-module swerve base",
                                  caseKinds={c["id"]: "nominal" for c in cases},
                                  uncoveredCases=uncovered))
    import review_data
    scene_data = review_data.build(OUT, REPO, plan, trial_data, fuel_index, measured, risks, records)
    plan["presentation"].update(review_data.presentation(scene_data))
    review_data.save(OUT, scene_data)
    write("layout.json", plan)

    # ---------------------------------------------------------- missions: mission cases, cycle map and risk register
    FIT = lambda cid, what, objective: dict(case=cid, kind="field-interaction-trial", accomplishes=what, objective=objective,
                                           trial=next(dict(file=r["record"], sha256=sha(REPO / r["record"])) for r in fuel_index if r["case"] == cid))
    OPC = lambda cid, what, objective, key: dict(case=cid, kind="operating-case", accomplishes=what, objective=objective, trial=records[key])
    of = lambda *phases: [c for ph in phases for c in phase_cases.get(ph, [])]
    missions = dict(
        missionCases=[
            FIT(last("acquire-climb"), "acquired", obj_collect),
            FIT(last("stage"), "acquired", obj_collect),
            OPC("loaded-transit", "acquired", obj_traffic, "hold"),
            FIT(last("launch-feed"), "delivered", obj_carry),
            OPC(last("launch-feed"), "delivered", obj_rate, "hopper"),
            FIT(last("launch-wrap"), "delivered", obj_carry),
            OPC(last("launch-wrap"), "delivered", obj_rate, "batch"),
            FIT(last("flight"), "scored", obj_carry),
            OPC("climb-lift", "climb-held", obj_hang, "hang")],
        cycle=dict(
            acquire=dict(cases=["intake-deploy"] + of("acquire-approach", "acquire-climb", "acquire-over", "acquire-throw")),
            retain=dict(cases=of("hopper-drop", "hopper-roll", "stage") + ["loaded-transit"]),
            transfer=dict(cases=of("launch-feed", "launch-wrap")),
            deliver=dict(cases=of("flight")),
            reset=dict(notApplicable="No reset motion: the intake stays deployed and each lane's feeder stages the next FUEL as the last one leaves, which the hopper cycle trial covers"),
            endgame=dict(cases=["climb-reach", "intake-stow", "tower-lateral", "tower-forward", "climb-seat", "climb-lift"]),
            park=dict(cases=["park-lower"]),
            service=dict(cases=["battery-cover-remove", "battery-withdraw", "shooter-withdraw"])),
        risks=risks)
    write("missions.json", missions)
    extras = dict(startVolume=vol, stored=stored,
                  trackedFuel=dict(installedMm=list(start), seatMm=list(seat), toleranceMm=TOL_MM, fieldTrials=trials_pin, cases=fuel_index),
                  shot=dict(speedMps=rel_state["speedMps"], elevationDeg=rel_state["elevationDeg"], spinRatio=rel_state["spinRatio"],
                            releaseMm=list(xz(release_mm)), distanceM=release_distance, scoringBandMps=band, flightS=tr["deliver-nominal"]["metric"]["value"],
                            source="launch-nominal release state and deliver-nominal trace in field-trials.json"),
                  inspectionKg=inspection, runningKg=running, reserveKg=reserve, sweep=sweep,
                  volumesMm3={n: round(volume(s), 1) for n, s in shapes.items()})
    write("package-facts.json", extras)
    print(json.dumps(dict(target=str(REL), stored=len(stored), startVolume=vol["estimateAtPacking"], fuelCases=len(fuel_index), cycle=len(cycle), control=control_case,
                          shot=dict(speedMps=rel_state["speedMps"], elevationDeg=rel_state["elevationDeg"], band=band), sweep=sweep, reach=deployed_reach,
                          inspection=inspection, running=running, reserveKg=reserve, carried=carried,
                          maxFitDeviationMm=max(r["maxDeviationMm"] for r in fuel_index)), indent=1))
    if args.check:
        check(args, view)


def check(args, view):
    """Run the layout check from the repository root and save its receipt beside the plan."""
    env = dict(os.environ)
    env.setdefault("PYTHON", sys.executable)
    plan, receipt = rel("layout.json"), rel("receipt-partial.json" if args.fail_fast else "receipt.json")
    flags = ["--fail-fast"] if args.fail_fast else ["--require-checked", "--write-view"]
    if args.previous:
        flags += ["--previous", args.previous]
    out = subprocess.run(["node", str(CLI), "preliminary-check", str(REPO), plan, *flags, "--output", receipt], capture_output=True, text=True, env=env)
    sys.stderr.write(out.stderr)
    print("exit", out.returncode, out.stdout[-400:])


def component_explanations(shapes, groups_of, roles, k, trials, quals, fb):
    E = {}
    def put(names, purpose, rationale, category, material, **more):
        for n in names:
            assert n in shapes, n
            E[n] = dict(purpose=purpose, rationale=rationale, category=category, material=material, **more)
    S = list(shapes)
    acq, ent, lch = trials["acquire-nominal"], trials["entry-nominal"], trials["launch-nominal"]
    hang = trials["hang-nominal"]["cable"]
    peak = lambda t, labels: max(r[2] for label in labels for r in t["contacts"].get(label, [[0, 0, 0.0]]))
    B_ = lambda q, name: next(b for b in q["brackets"] if b["input"] == name)
    I_, F_, H = D.INTAKE, D.FEEDER, D.HOPPER
    sq = B_(quals["acquisition"], "belt and bumper squeeze")
    put([n for n in S if n.startswith("frame rail")], "Carry the drive corners, bumpers and every mechanism mount.",
        "The foundation's 680 mm length and module saddles carry forward; the frame is 714 mm wide (2788 mm perimeter) for hang overlap. The front rail top closes the front of the hopper channel below the bumper top.", "structure", "6061-T6 2x1x0.125 in tube")
    put(["floor pan", "floor pan front tongue"], "Support the floor belts, battery and electronics.",
        "Sits 94 mm above the carpet; the BUMP crossing screen then leaves 24 mm at the belly and 8.7 mm at the front bumper corner.", "structure", "3 mm polycarbonate over aluminum stiffeners")
    put(["lane deck"], "Carry the staged FUEL and the FUEL being fed, under the feeder rollers and on to the flywheel.",
        "A fixed surface, not the belt: a FUEL clamped between a braked roller and a fixed deck stays put whatever the belt behind it does. The floor belt ends ahead of it so the staged FUEL does not touch the belt.", "structure", "3 mm aluminum with a friction surface")
    put([n for n in S if n.startswith("intake slide rail")], "Guide the intake carriage between the start fold and the pickup pose.",
        f"A straight slide of {I_['shift'][0]:g} mm aft and {-I_['shift'][2]:g} mm up never sweeps beyond the 304.8 mm R105 reach; the fixed stage of the two-stage slide is drawn. The same slide makes the 40 mm unjam nudge.", "structure", "Aluminum drawer-slide stage")
    put([n for n in S if n.startswith("climber tube mount")], "Carry the climber tubes and the hang load into the front rail.", "The hang reaction enters the frame next to the front modules.", "structure", "6 mm aluminum bracket")
    put([n for n in S if "wheel azimuth" in n], "Reserve the full steering sweep of each swerve wheel.",
        "A revolved envelope avoids animating an axisymmetric sweep and still bounds the wheel at any heading.", "drivetrain", "Supplier wheel; envelope only")
    put([n for n in S if "module body" in n], "Represent the swerve module plates and gearing.", "Four-module swerve is the project default and the foundation already fits the supplier tabs.", "drivetrain", "Supplier module")
    put([n for n in S if "module motors" in n], "Reserve the drive and steering motors above each module.", "Their height sets the low front shelves of the hopper liners above the front corners.", "drivetrain", "Supplier motors")
    put([n for n in S if n.startswith("bumper")], "Protect the frame perimeter and back the intake pinch.",
        f"The 48-168 mm zone and 76 mm section follow the foundation release; the front bumper face is the pinch backing for the first of the climb: the acquisition trial presses the FUEL {peak(acq, ['bumper face', 'bumper top']):.1f} mm into it. Its 866.15 mm width overlaps each TOWER upright by 23.9 mm.", "bumper", "Plywood backing, foam, fabric")
    put(["hopper wall left", "hopper wall right"], "Contain stacked FUEL up to 715 mm.", "The walls stand above the heap the collect trial builds.", "structure", "2 mm polycarbonate")
    put(["hopper rear wall"], "Separate stored FUEL from the spinning flywheel above the floor lanes.",
        "Only the floor layer may pass under it. It stands behind the feeder rollers, so the rollers pull the floor FUEL out from under the heap. It stops at the right liner's pocket, clear of the inertia ring.", "structure", "2 mm polycarbonate")
    put(["hopper liner left", "hopper liner right"], "Shape the hopper floor: a two-lane channel with shelves sloping in to it, and the cheeks beside the stowed intake.",
        f"The channel is two lanes ({2 * H['lane_half']:g} mm) wide for its whole length, so the floor layer never has to converge; the batch trial stalls on the earlier issue's flat full-width floor. The {H['shelf_deg']:g} degree shelves cover the battery and electronics; the low front shelves pass under the stowed carriage. The right liner starts ahead of the flywheel's inertia ring behind a pocket wall.", "structure", "2 mm formed polycarbonate")
    put(["hopper shelf left"], "Cover the battery and slope stored FUEL in to the channel; lift out for battery service.",
        "A separate panel on two quarter-turn fasteners: the service cases lift it out with the strap, then the battery.", "structure", "2 mm polycarbonate panel")
    put(["floor belt main", "floor belt front"], "Carry the floor layer of FUEL aft to the feeder rollers.",
        f"Flat belts in the channel at {D.FLOOR_BELT_MPS} m/s, running to the front rail so a FUEL at the front of the floor stands on a driven surface. They stop while both lanes are staged and held, and reverse for 0.3 s in an unjam cycle. At 0.6 and 0.3 m/s the hopper cycle trial feeds all 24 in {trials['hopper-cycle-belt-0.6mps']['feed']['lastFedS']:.1f} and {trials['hopper-cycle-belt-0.3mps']['feed']['lastFedS']:.1f} s, against {trials['hopper-cycle-nominal']['feed']['lastFedS']:.1f} s at this speed.", "mechanism", "Belt envelope; flat belt and rollers")
    put(["feeder roller left", "feeder roller right"], "Hold a staged FUEL clear of the spinning flywheel, and feed it on command.",
        f"One compliant 2 in roller per lane, {F_['squeeze']:g} mm into the FUEL over the fixed lane deck. Braked, it is the hold-back: the hold trial keeps the FUEL {trials['hold-nominal']['metric']['value']:.1f} mm clear of the wheel at 1.5 g with a {B_(quals['hold'], 'push from queued FUEL')['passing']:g} N push and fails at {B_(quals['hold'], 'push from queued FUEL')['failing']:g} N. Turning, it meters: the lanes feed the one flywheel in turn, each feed given only with the wheel in its ready band. The two rollers meet at the centre line so a FUEL between the lanes is still under a roller.", "mechanism", "2 in compliant roller on a 12 mm shaft")
    put(["feeder motor left", "feeder motor right"], "Turn and brake one feeder roller.", "A small planetary gearmotor with a brake outboard of the channel wall, under the shelf on the left and in the pocket on the right. Unmounted allowance: the 12 mm shaft through the channel wall and the bearing block that carries it are not drawn, so the motor appears to float.", "mechanism", "Planetary gearmotor with brake; envelope", name=None)
    put(["flywheel"], "Accelerate each FUEL against the hood.",
        f"A 4 in floor-fed flywheel at a {lch['params']['wheelMps']} m/s setpoint, held at speed whenever FUEL is aboard. The wheel-to-hood gap is the FUEL diameter less {k['squeeze']:.0f} mm: the launch trial releases at {lch['release']['speedMps']:.2f} m/s. It is a free body in the trial: one shot takes {lch['wheelDemand']['energyJ']:.0f} J and drops it {lch['wheelDemand']['speedDropPercent']:.1f}%.", "mechanism", "Aluminum tube roller, compliant tread")
    put(["flywheel inertia ring"], "Store the energy of a shot so the wheel speed falls little.",
        f"One steel ring ({fb['ringKg']:.2f} kg) outboard of the right side plate brings the wheel to {fb['inertia']:.4f} kg m2 for {fb['kg']:.2f} kg. The batch trial holds the scoring band with it on the weak-pack bus; the bare roller holds it there only at the full 40 A stator limit.", "mechanism", "Steel ring on an aluminum web; drawn as its disc envelope", volumeType="envelope")
    put(["hood"], "Guide the FUEL around the flywheel and release it at about 62 degrees elevation.",
        f"Concentric with the wheel and tangent to the lane deck. It ends at {k['hood_span_deg'][0]:.1f} degrees about the wheel axis, where the launch trial releases the FUEL at {lch['release']['elevationDeg']:.1f} degrees; the end stays inside the rear perimeter, so the shooter never extends a second side.", "mechanism", "Formed aluminum with friction liner")
    put([n for n in S if "shooter side plate" in n], "Carry the flywheel bearings and hood.", "Plates stop 4 mm short of the rear modules and bound the two lanes behind the rear wall.", "structure", "6 mm aluminum plate")
    put(["flywheel motor left", "flywheel motor right"], "Drive the flywheel from both ends and hold its speed.", "Direct drive, 40 A stator and 30 A supply limit each. Outboard of each side plate, clear of the battery, the ring and the rear modules.", "mechanism", "Brushless motor")
    put(["battery"], "Supply the robot bus.", "Standing on its end under the left shelf, between two cleats and under a strap; it lifts straight out once the shelf panel and strap are off.", "battery", "Sealed lead acid 12 V")
    put(["battery retention cleat aft"], "Stop the battery sliding aft and carry its end load into the floor pan.",
        "Paired with the fore cleat so the battery is captured in X.", "structure", "6061 aluminium formed cleat", volumeType="envelope")
    put(["battery retention cleat fore"], "Stop the battery sliding forward.",
        "Paired with the aft cleat so the battery is captured in X while it still lifts straight out for service.", "structure", "6061 aluminium formed cleat", volumeType="envelope")
    put(["battery strap"], "Hold the battery down on the floor pan.", "The earlier issue had no hold-down. The strap runs over the battery top between the cleats, under the shelf panel.", "structure", "25 mm webbing and buckle")
    put(["electronics panel", "electronics panel left", "electronics bay right"], "Hold power distribution, controller, radio, breaker and 17 motor controllers.", "Under the right shelf, beside the battery and under the right slide rail: outside the FUEL space and reachable from above or from the side. The panel under the shelf stands on the floor pan.", "electrical", "Polycarbonate panel")
    put(["entry sensor"], "Observe each FUEL passing the top of the chute, and that the chute is clear before the intake stows.", "The strategy requires per-piece intake crossings on the match timebase.", "electrical", "Beam-break sensor")
    put(["stage sensor left", "stage sensor right"], "Observe the FUEL staged under each feeder roller.", "One beam per lane: a FUEL on the centre line breaks both, and both rollers then hold or feed it together. Separates retained identity from release for the counting requirement.", "electrical", "Beam-break sensor")
    put([n for n in S if n.startswith("climber tube ") and "mount" not in n], "Guide the telescoping hooks.", "Front corners above the modules give a straight load path into the frame for the hang.", "structure", "30 mm round aluminum tube")
    put(["climber winch"], "Retract both inner tubes by cable to lift the robot.", f"Under the left slide rail, outboard of the carriage plate. In the hang trial at {D.HANG_MASS_KG} kg its cable load peaks at {hang['liftPeakN']:.0f} N during the lift, and the brake must hold {hang['holdN'][1]:.0f} N with power removed.", "mechanism", "Gearmotor and spool envelope")
    put([n for n in S if n.startswith("climber inner tube")], "Telescope inside the outer tube to seat the hook and lift the robot 70 mm.",
        "A round tube lets the hook swing on top without the tube rotating in its guide; the swing actuator sits inside it.", "mechanism", "22 mm round aluminum tube")
    put([n for n in S if n.startswith("climber hook")], "Swing forward, pass over the low rung, seat and lift the robot 70 mm.", "Stowed inside the perimeter for R106. They swing while the intake is still deployed below them; the intake then stows between them.", "mechanism", "Aluminum tube and hook plate")
    put(["intake belt module"], "Draw a floor FUEL under its bottom pulley and lift it up the bumper face and the back plate.",
        f"Drawn at the acquisition trial's setting: the back run stands {I_['pinch_squeeze']:.0f} mm inside one FUEL diameter from the bumper face and the back plate, and the bottom pulley {I_['pulley_squeeze']:.0f} mm into a floor FUEL. The trial captures at {sq['passing']:g} mm and fails at {sq['failing']:g} mm, so the squeeze is a layout dimension. It stays inside the 304.8 mm reach.", "mechanism", "Belt module with internal motor")
    put(["intake top roller"], "Throw the lifted FUEL aft over the top of the back plate.",
        f"Lowered {I_['roller_drop']:.0f} mm into the path of the FUEL at the top of the climb and turning at {I_['roller_ratio']:g} times the belt speed; the FUEL enters the hopper at {math.hypot(acq['final']['vx'], acq['final']['vz']):.1f} m/s, {1000 * acq['final']['z']:.0f} mm up, above the stored FUEL.", "mechanism", "2 in compliant wheels on hex shaft")
    put(["intake back plate"], "Back the belt above the bumper, and close the front of the hopper while the intake is deployed.",
        f"It continues the bumper face plane up to {I_['back_top']:g} mm, so a FUEL enters the hopper from above the heap: thrown in low through an open throat, the collect trial stalls with FUEL backing out. Its hopper-side face leans forward from a {I_['back_foot']:g} mm foot, so a FUEL touching it stands over the driven belt. In an unjam cycle the slide nudges it {I_['nudge'][0]:g} mm into the FUEL at the front.", "mechanism", "Folded 1 mm aluminum wedge with a friction face; drawn solid", volumeType="envelope")
    put([n for n in S if n.startswith("intake carriage plate")], "Join the belt module, top roller and back plate to the slide, and close the sides of the chute.", "Plates at 250-260 mm run outboard of the hopper cheeks and inboard of the slide rails, and pass over the front module motors as the carriage deploys.", "mechanism", "Aluminum plate, lightened")
    put([BALL], "Follow one identifiable FUEL from the carpet into the HUB.",
        f"Its cases are strokes fitted within {TOL_MM} mm to the solved acquisition, entry, launch and delivery traces; it is drawn where the mission finds it, on the carpet ahead of the intake.", "game-piece", "Foam FUEL 150.114 mm, 0.203-0.227 kg")
    put([n for n in S if n.startswith("FUEL stored")], "Represent stored stock in the starting fold.", "Supported places from the deposition screen, behind the stowed carriage and clear of every traced position of the tracked FUEL; capacity itself is the collect trial and the start-capacity premise.", "game-piece", "Foam FUEL")
    put(["hub body", "hub top"], "Locate the HUB and its hexagonal opening.", "The flight cases follow the delivery trial over the near flat at 1828.8 mm, into the conservative inscribed opening and against the cavity wall.", "reserved-space", "Field fixture (V0 dimensions)")
    put([n for n in S if n.startswith("tower upright")], "Locate the TOWER uprights.", "Their 819 mm gap bounds the bumper approach and the forward hooks.", "reserved-space", "Field fixture (V0 dimensions)")
    put(["tower low rung"], "Locate the low rung at 685.8 mm.", "The hooks must seat on it; the V0 text centres it in the upright depth.", "reserved-space", "Field fixture (V0 dimensions)")
    put(["tower base"], "Locate the TOWER BASE plate.", "Level 1 requires clearing it; its 8 mm edge stands under the front bumper at the berth.", "reserved-space", "Field fixture (V0 dimensions)")
    missing = [n for n in shapes if n not in E]
    assert not missing, missing
    for n, c in E.items():   # inspector fields: display name, owning group and what the drawn volume stands for
        g = groups_of[n]
        if c.get("name") is None:
            c["name"] = n[0].upper() + n[1:] + (" (unmounted allowance)" if "name" in c else "")
        c.setdefault("subsystem", g)
        c.setdefault("volumeType", "envelope" if ENVELOPE.search(n) or roles[g] == "drive" else "material")
    return E


if __name__ == "__main__":
    main()
