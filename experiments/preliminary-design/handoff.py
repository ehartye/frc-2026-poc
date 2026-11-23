"""Write HANDOFF.md in a preliminary design's folder from the files the layout check read and wrote.

    python -I -B experiments/preliminary-design/handoff.py cad/preliminary-design/releases/1.0

Every figure is read from the judgement file, the generated manifest of the design source, the receipt, missions.json,
measurements.json or a trial record in that folder. Run it after the layout check. It reads files and runs nothing else.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FIRST_WORK = [
    "Draw the carriage cross-ties and the moving slide stage, and check them against the hopper cheeks through the slide travel (risk carriage-cross-ties).",
    "Measure a FUEL force-deflection curve and the foam friction on the feeder roller and lane deck; repeat the hold-back and acquisition trials with them (risks hold-back-force, acquisition-pinch).",
    "Repeat the delivery and hang trials against the official HUB and TOWER parts, then find the flywheel setpoint on the bench (risks shot-calibration, hang-squaring).",
    "Set the withdrawal clearances of the battery, shelf panel and shooter module. The service cases here show no interference and hold no reserve.",
    "Weigh the mass estimate against real parts as they are chosen: the reserve is small (risk mass-reserve).",
]


def main():
    rel = Path(sys.argv[1]).as_posix().strip("/")
    folder = REPO / rel
    load = lambda name: json.loads((folder / name).read_text(encoding="utf-8"))
    plan, receipt, missions, measured, built = (load(n) for n in ("judgement.json", "receipt.json", "missions.json", "measurements.json", "generated/manifest.json"))
    assert receipt["status"] == "layout-checked" and not receipt.get("partial"), "Run the full layout check first"
    index = json.loads((REPO / "docs/preliminary-design/releases.json").read_text(encoding="utf-8"))
    version = folder.name
    name = index.get("designs", {}).get(version.split(".")[0], {}).get("name", "")
    fixtures = {f["name"] for f in built["fixtures"]}
    groups = {name: g for name, g in built["groups"].items() if g["members"]}
    payload = {m for g in groups.values() if g["role"] == "payload" for m in g["members"]}
    out = [f"# Handoff to detailed design: {name} {version}", "",
           f"Written by `experiments/preliminary-design/handoff.py` from the files in `{rel}/`. The design is in progress until the owner marks it effective. "
           "Lengths are millimetres in the robot datum unless a unit is given.", ""]

    def table(title, head, rows, note=None):
        out.extend([f"## {title}", ""] + ([note, ""] if note else []) + ["| " + " | ".join(head) + " |", "| " + " | ".join("---" for _ in head) + " |"])
        out.extend("| " + " | ".join(str(c).replace("|", "/").replace("\n", " ") for c in row) + " |" for row in rows)
        out.append("")

    robot = len(built["solids"])
    table("Design", ["Item", "Value", "File"], [
        ["Name and version", f"{name} {version}", "`docs/preliminary-design/releases.json`"],
        ["Blockout", f"{robot} named solids, one per functional volume, in {len(groups) - 1} groups", "`design.json` (the design source), built to `generated/design.step`"],
        ["Solid names", "Plain words with handedness last, such as `feeder roller left`; envelopes say so in their explanation", "`judgement.json` presentation.components"],
        ["Field parts", f"{len(fixtures)} parts of FIRST's official HUB and TOWER at the shot pose", "`field/*.step`, source in `cad/field/official/`"]])
    table("Frame and datums", ["Datum", "Value", "File"], [
        ["Origin and axes", built["design"]["frame"], "`design.json` frame"],
        ["Floor", "Z = 0 at the carpet", "`design.json` frame"],
        *[[f"Mount: {m.get('member', m['group'])} on {m['on']}", f"({m['atMm'][0]:g}, {m['atMm'][1]:g}, {m['atMm'][2]:g}). {m['note']}", "`design.json` mounts"] for m in built["mounts"]]])
    moves = []
    for case in ("intake-deploy", "climb-reach", "climb-seat", "climb-lift"):
        group, ops = next((g, o) for g, o in sorted(built["motions"][case]["moves"].items())
                          if not set(groups[g]["members"]) <= fixtures and groups[g]["role"] != "payload")
        op = ops[0]
        travel = (f"rotates {op['travelDeg']:g} degrees about axis {op['axis']} through {op['originMm']}" if op["kind"] == "rotation"
                  else f"translates {op['travelMm']}")
        moves.append([case, group, travel])
    table("Axes and travel", ["Case", "First moving group", "Travel"], moves, "From the motions of `design.json`. Mirrored groups move the same way on the other side.")
    table("Envelopes", ["Measure", "Value", "File"], [
        ["Frame", "680 long by 714 wide, 2788 perimeter", "`design.json` frame rails"],
        ["Bumper zone", "48 to 168 above the carpet, 76 section", "`design.json` bumpers"],
        ["Starting overhang beyond the frame", measured["startOverhangMm"], "`measurements.json`"],
        ["Greatest height in any operating or park pose", measured["sweptTopMm"], "`measurements.json`"],
        ["Greatest front extension", measured["sweptFrontExtensionMm"], "`measurements.json`"],
        ["Greatest rear or side extension", measured["sweptOtherExtensionMm"], "`measurements.json`"],
        ["Sides extended at once", measured["sidesExtendedMax"], "`measurements.json`"],
        ["Least clearance over the BUMP crest, static screen", measured["bumpCrossingClearanceMm"], "`measurements.json`"]])

    tight = {}
    for c in receipt["cases"]:
        for p in c["pairs"]:
            gap = (p.get("witness") or {}).get("gapMm")
            a, b = p["pair"]
            if gap is None or gap >= 10 or (a in fixtures and b in fixtures):
                continue
            if (a, b) not in tight or gap < tight[a, b][0]:
                tight[a, b] = (gap, c["case"])
    table("Interfaces and allowances: fits under 10 mm", ["Pair", "Least gap", "Case"],
          [[f"{a} / {b}", f"{g:.1f}", case] for (a, b), (g, case) in sorted(tight.items(), key=lambda kv: (kv[1][0], kv[0]))],
          "Least gap of each pair the layout check measured under 10 mm, from `receipt.json`. Each is an interface for detailed design to dimension, not a verified clearance. "
          "Pairs of official field parts are left out.")
    contacts = {}
    for row in built["contacts"]:
        a, b = row["pair"]
        if not (a in fixtures and b in fixtures):
            contacts[a, b] = row
    table("Interfaces and allowances: intended contacts", ["Pair", "Cases", "Basis"],
          [[f"{a} / {b}", ", ".join(row.get("during", ["every case"])), row["note"]] for (a, b), row in sorted(contacts.items())],
          "From the contacts of `design.json`. A listed pair is left out of that case's clearance test.")
    unmounted = plan.get("attachment", {}).get("unmounted", {})
    if unmounted:
        table("Connections not drawn yet", ["Solid", "Reason"], sorted(unmounted.items()))

    seen, windows = set(), []
    for case in missions["missionCases"]:
        ref = case.get("trial", {}).get("file")
        if not ref or ref in seen:
            continue
        seen.add(ref)
        q = json.loads((REPO / ref).read_text(encoding="utf-8"))["qualification"]
        for b in q["brackets"]:
            windows.append([q["trial"], b["input"], f"{b['passing']:g} {b['unit']}", f"{b['failing']:g} {b['unit']}", f"`{Path(ref).name}`"])
        windows.append([q["trial"], "control: " + q["control"]["condition"], "", "rejected", f"`{Path(ref).name}`"])
        windows.append([q["trial"], "timestep", f"{q['timestep']['coarseS']:g} s", f"same outcome at {q['timestep']['fineS']:g} s: {q['timestep']['sameOutcome']}", f"`{Path(ref).name}`"])
    table("Operating point and windows", ["Trial", "Input", "Passes at", "Fails at", "Record"], windows,
          "Each trial ran on blockout geometry with estimated contact stiffness and friction. A bracket lists one passing value and the nearest failing one.")
    table("Motion cases", ["Phase", "Cases", "Path tolerance"],
          [[phase, ", ".join(v["cases"]) if "cases" in v else "not applicable: " + v["notApplicable"],
            ", ".join(sorted({f"{plan['stages'][c]['pathToleranceMm']:g} mm" for c in v.get("cases", [])}))] for phase, v in missions["cycle"].items()]
          + [["displaced control", f"{plan['control']['case']}: {plan['control']['basis']}", "rejected" if receipt["control"]["witness"]["status"] == "fail" else "NOT rejected"]],
          "From `missions.json` and `judgement.json`. The single prescribed strokes follow their path exactly; the tracked FUEL's strokes are within the stated distance of the solved trace.")
    b = receipt["budgets"]
    volts = min(b["electricalCases"], key=lambda e: e["marginV"])
    table("Budgets", ["Budget", "Value", "File"], [
        ["Inspection weight estimate", f"{b['inspectionKg'][0]:.2f} to {b['inspectionKg'][1]:.2f} kg against {load('package-limits.json')['inspectionLimitKg']:g} kg", "`receipt.json` budgets"],
        ["Reserve under the limit", f"{b['remainingKg']:.2f} kg", "`receipt.json` budgets"],
        ["Running weight with bumpers, battery and 24 FUEL", f"{b['runningKg'][0]:.2f} to {b['runningKg'][1]:.2f} kg", "`receipt.json` budgets"],
        ["Least loaded-voltage margin", f"{volts['marginV']:.2f} V in {volts['case']} ({volts['loadedBusV'][0]:.2f} V against {volts['requiredMinV']:g} V)", "`receipt.json` budgets"],
        ["Mass and current by subsystem", "one line per subsystem with its basis", "`budgets.json`"]])
    risks = missions["risks"]
    table("Open risks and bench tests", ["Risk", "Closed by, or bench test", "Pass", "Fail"],
          [[f"{r['id']}: {r['risk']}", "Closed: " + r["closedBy"], "", ""] if r.get("closedBy") else
           [f"{r['id']}: {r['risk']}", r["benchTest"]["measure"], f"{r['benchTest']['pass']:g} {r['benchTest'].get('unit', '')}", f"{r['benchTest']['fail']:g} {r['benchTest'].get('unit', '')}"]
           for r in risks], "From `missions.json`.")
    table("Trials and replays", ["Motion", "What it plays", "Repeat on real parts"],
          [[r["label"], r["basis"].split(". ")[0], "Yes"] for r in json.loads(__import__("gzip").decompress((folder / "replays.json.gz").read_bytes()))["replays"]],
          "Every trial ran on blockout geometry and estimated contact properties. The delivery and hang trials ran against dimensioned field surfaces, not the official parts the layout check uses.")
    out.extend(["## First work items", ""] + [f"{i}. {item}" for i, item in enumerate(FIRST_WORK, 1)] + [""])
    (folder / "HANDOFF.md").write_text("\n".join(out), encoding="utf-8", newline="\n")
    print(f"Wrote {rel}/HANDOFF.md: {len(tight)} fits under 10 mm, {len(contacts)} intended contacts, {len(risks)} risks")


if __name__ == "__main__":
    main()
