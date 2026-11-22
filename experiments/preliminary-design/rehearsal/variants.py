"""Re-run the kickoff match series with R3 delivering from 2.7 m, and compare R3L on the TRENCH route.

Run from the project root (needs Node and the Agent FRC checkout in AGENT_FRC):
    python -I -B experiments/preliminary-design/rehearsal/variants.py
Writes one profile and one series result per variant into this folder, plus comparison.json.
"""
import copy
import hashlib
import json
import math
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUNNER = Path(os.environ["AGENT_FRC"]) / "scripts" / "rehearsal-series.mjs"
HUB = (182.1, 158.85)          # blue HUB centre, field inches (kickoff/match-series.md)
POSE_IN = 2700 / 25.4          # R3 delivery: robot centre 2.7 m from the HUB centre


ACTION = (108.0, 158.85)       # blue-hub chassis action datum; legal-pose screen radius 52 in (field profile)
SCREEN_IN = 52.0 - 3.0


def moved(at):
    """Same side of the HUB axis, 2.7 m from the HUB centre, bearing turned toward the axis only as far as
    needed to stay 3 in inside the profile's legal-pose screen."""
    bearing = math.atan2(at[1] - HUB[1], HUB[0] - at[0])
    sign = 1 if bearing >= 0 else -1
    b = abs(bearing)
    while True:
        x, y = HUB[0] - POSE_IN * math.cos(b), HUB[1] + sign * POSE_IN * math.sin(b)
        if math.hypot(x - ACTION[0], y - ACTION[1]) <= SCREEN_IN or b <= 0:
            return [round(x, 2), round(y, 2)]
        b -= math.radians(0.5)


def relocate(program):
    for step in program["steps"]:
        if step.get("operation") == "attempt":
            step["at"] = moved(step["at"])
    return program


def deconflict(progs):
    """Alliance partner routes that leave slot 2's depot loop open, applied identically to every variant.
    Slot 3's reserve uses the deep reserve the role-and-support study selected; the neutral runner joins and
    leaves its trench corridor east of the depot lane and delivers south of the HUB axis (inside the
    52 in legal-pose screen)."""
    progs["shift-reserve"]["steps"][0]["at"] = [109, 268]
    for st in progs["shift-neutral"]["steps"]:
        if st["label"] == "Join the high trench corridor":
            st["at"] = [140, 214]
        elif st["label"] == "Yield the depot lane":
            st["at"] = [140, 214]
        elif st.get("operation") == "attempt":
            st["at"] = [95, 121]


def variant(base, name, height_mm=None, shift_program=None, move=True, width_mm=None, slot3_reserve=False):
    p = copy.deepcopy(base)
    p["rehearsal"]["waitCycles"] = "yield"   # Agent FRC 0.84.0: resolve robot-to-robot wait cycles
    deconflict(p["rehearsal"]["programs"])
    progs = p["rehearsal"]["programs"]
    for key in ([k for k in progs if k.startswith("auto-2-")] + ["shift-depot"]) if move else []:
        relocate(progs[key])
    if shift_program:
        progs[shift_program + "-slot2"] = relocate(copy.deepcopy(progs[shift_program]))
    for match in p["rehearsal"]["series"]["matches"]:
        for robot in match["roster"]:
            if robot["slot"] == 2 and height_mm is not None:
                robot["height"] = round(height_mm / 25.4, 3)
            if robot["slot"] == 2 and width_mm is not None:
                robot["width"] = round(width_mm / 25.4, 3)
            if robot["slot"] == 2 and shift_program:
                for period, prog in robot["plans"].items():
                    if prog == "shift-depot":
                        robot["plans"][period] = shift_program + "-slot2"
            if robot["slot"] == 3 and slot3_reserve:
                for period, prog in robot["plans"].items():
                    if prog == "shift-neutral":
                        robot["plans"][period] = "shift-reserve"   # R3L takes the neutral runner's TRENCH job
    path = HERE / f"{name}-profile.json"
    path.write_text(json.dumps(p, indent=1) + "\n", encoding="utf-8", newline="\n")
    return path


def run(profile, name):
    out = HERE / f"{name}-series.json"
    r = subprocess.run(["node", str(RUNNER), str(profile), str(out), "--report-deadlocks"], capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise SystemExit(r.stderr)
    cycles = json.loads(r.stdout)
    (HERE / f"{name}-wait-cycles.json").write_text(json.dumps(cycles, indent=1) + "\n", encoding="utf-8", newline="\n")
    d = json.loads(out.read_text(encoding="utf-8"))
    rows = []
    for m in d["matches"]:
        g = m["game"]
        slot2 = {}
        for e in g["events"]:
            if e.get("operation") == "attempt" and e.get("robot") in ("B2", "R2"):
                slot2.setdefault(e["robot"], 0)
                if e.get("outcome") == "credited":
                    slot2[e["robot"]] += len(e.get("pieces", []))
        rows.append(dict(match=m["id"], score=g["score"], slot2Credited=slot2,
                         slot2Terminal=g["endgame"].get("decisions") if isinstance(g.get("endgame"), dict) else None))
    return dict(variant=name, waitCycles=dict(mode=cycles["waitCycles"], count=cycles["cycleCount"], permanent=cycles["permanentCount"],
                                         report=f"{name}-wait-cycles.json"), profile={"file": str(profile.relative_to(ROOT)).replace("\\", "/"), "sha256": hashlib.sha256(profile.read_bytes()).hexdigest()},
                result={"file": str(out.relative_to(ROOT)).replace("\\", "/"), "sha256": hashlib.sha256(out.read_bytes()).hexdigest()}, matches=rows)


def main():
    base_path = ROOT / "kickoff" / "field-profile.json"
    base = json.loads(base_path.read_text(encoding="utf-8"))
    results = [run(variant(base, "kickoff-baseline-yield", move=False), "kickoff-baseline-yield"),
               run(variant(base, "r3-2p7m", 750.0, width_mm=714.0), "r3-2p7m"),
               run(variant(base, "r3l-2p7m-depot", 534.0, width_mm=714.0), "r3l-2p7m-depot"),
               run(variant(base, "r3l-2p7m-trench", 534.0, "shift-neutral", width_mm=714.0), "r3l-2p7m-trench"),
               run(variant(base, "r3l-2p7m-trench-solo", 534.0, "shift-neutral", width_mm=714.0, slot3_reserve=True), "r3l-2p7m-trench-solo")]
    out = dict(schema="frc-2026-poc/rehearsal-comparison@1", runner="agent-frc scripts/rehearsal-series.mjs",
               deliveryPoseM=2.7, hubCentreIn=HUB,
               basis="All profiles opt into rehearsal.waitCycles = yield (Agent FRC 0.84.0) and share one partner deconfliction (deep reserve; neutral runner east of the depot lane, delivering south of the HUB axis); runs before 0.84 held permanent robot-to-robot wait cycles that froze slot 2. Slot 2 (B2/R2) is the robot under design. Its AUTO and depot-shift delivery steps move to 2.7 m from the HUB centre, keeping their bearing unless the point would leave the profile's 52 in legal-pose screen (then the bearing turns toward the HUB axis); R3L variants also lower its height to 534 mm. The trench variant gives slot 2 a copy of the low-trench neutral program with the same 2.7 m delivery.",
               variants=results)
    (HERE / "comparison.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    for v in results:
        print(v["variant"], "waitCycles", v["waitCycles"])
        for m in v["matches"]:
            print("   ", m["match"], m["score"], m["slot2Credited"])


if __name__ == "__main__":
    main()
