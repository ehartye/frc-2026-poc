"""Replay the release-day field study and the source-linked design and load checks."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PROFILE = ROOT / "kickoff/rules-model.json"
CAPTURE = ROOT / "experiments/depot-loading/results.json"


def read(path):
    return json.loads(path.read_bytes())


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf8", newline="\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cli(plugin, script, *args):
    result = subprocess.run(["node", plugin / "scripts" / script, *args],
                            check=True, capture_output=True, encoding="utf8")
    return json.loads(result.stdout)


def receipt(file, pointer=None):
    source = {"path": file.name, "sha256": digest(file)}
    if pointer is not None:
        source["pointer"] = pointer
    return source


def cargo_comparison(plugin, output):
    trials = read(CAPTURE)["trials"]
    cases = [
        {"id": "fine", "condition": "Parked at the registered depot, 0.125 ms integration."},
        {"id": "coarse", "condition": "Same geometry and commands, 0.250 ms integration."},
        {"id": "locked", "condition": "Transfer gate locked. The front roller is available."},
    ]
    descriptions = {
        "single": "One moving carriage translates each supported piece 79 mm across the chassis before admission.",
        "pair": "Two fixed admission lanes and a split center shelf align the two neighboring pieces directly with storage.",
    }
    metrics = {}
    for concept in descriptions:
        for case in cases:
            run_id = concept + "-" + case["id"]
            trial = trials[run_id]
            source = set(trial["retainedSourceIds"])
            preloads = set(trial["retainedPreloads"])
            final = {piece["id"] for piece in trial["finalRetained"] if piece["timeS"] == 8}
            if source & preloads or source | preloads != final:
                raise ValueError("Invalid eight-second cargo register for " + run_id)
            metrics[run_id] = {
                "concept": concept, "case": case["id"], "runId": run_id,
                "admitted": len(source), "preloads": len(preloads),
                "sourceIds": sorted(source), "preloadIds": sorted(preloads),
                "inputPointer": "/trials/" + run_id, "stepS": trial["dtS"],
            }
    source_file = output / "capture-observations.json"
    save(source_file, {"source": {"path": CAPTURE.relative_to(ROOT).as_posix(), "sha256": digest(CAPTURE)},
                       "runs": metrics})
    concepts = []
    for name, architecture in descriptions.items():
        runs = []
        for case in cases:
            base = "/runs/" + name + "-" + case["id"]
            runs.append({"case": case["id"], "source": receipt(source_file), "execution": base,
                         "values": {key: base + "/" + key for key in ("admitted", "preloads")}})
        concepts.append({"id": name, "architecture": architecture, "runs": runs,
                         "interfaces": [
                             {"from": "bumper and capture roller", "to": "supported carriage or lanes",
                              "exchange": "two neighboring depot pieces within the common front opening"},
                             {"from": "transfer gate", "to": "storage pockets",
                              "exchange": "admit new identities while retaining the eight separate preloads"},
                         ]})
    manifest = output / "design.json"
    save(manifest, {"schema": "agent-frc/design-review@1", "cases": cases, "concepts": concepts,
                    "objectives": [{"id": "admitted", "unit": "distinct source pieces at 8 s", "min": 2},
                                   {"id": "preloads", "unit": "original supported preloads at 8 s", "min": 8}]})
    return cli(plugin, "design-review.mjs", manifest, output)


def transport_throughput(plugin, output, study):
    rehearsal = read(PROFILE)["rehearsal"]
    matches = {match["id"]: match for match in rehearsal["series"]["matches"]}
    starts = {}
    cursor = 0
    for period in rehearsal["periods"]:
        starts[period["name"]] = cursor
        cursor += period["seconds"]
    station = next(s for s in rehearsal["stations"] if s["id"] == "blue-depot")
    common = {
        "criterionId": "blue-depot-to-b2-cargo",
        "criterion": "A distinct depot piece enters B2 cargo in a successful registered station transfer.",
        "focalRobot": "B2",
        "windowScope": "The first complete inactive shift plus the first five seconds of its next active shift.",
    }
    demand = {**common, "requiredPieces": 24, "windowS": 30,
              "basis": "After spending eight preloads in AUTO the project needs 24 fresh pieces onboard by active second five."}
    episodes = []
    for cell in study["cells"]:
        if cell["role"] != "alliance-depot":
            continue
        match = matches[cell["match"]]
        team = {r["slot"]: r for r in match["roster"] if r["side"] == "blue"}
        first = {"red": 0, "blue": 0}
        for event in cell["events"]:
            if event["phase"] == "AUTO" and event["operation"] == "attempt" and event["outcome"] == "credited":
                first["blue" if event["robot"].startswith("B") else "red"] += len(event["pieces"])
        leader = match["tieWinner"] if first["red"] == first["blue"] else max(first, key=first.get)
        start = starts["Shift 1" if leader == "blue" else "Shift 2"]
        end = start + 30
        inventory = {f"blue-depot/{n}" for n in range(1, station["stock"] + 1)}
        admissions = []
        for event in cell["events"]:
            if (event.get("station") != station["id"] or event["operation"] != "acquire"
                    or event["outcome"] != "acquired"):
                continue
            t = starts[event["phase"]] + event["timeS"]
            if t < start:
                inventory.difference_update(event["pieces"])
            if event["robot"] != "B2" or not start <= t < end:
                continue
            for pid in event["pieces"]:
                # The station enters custody and confirms cargo in one atomic model event.
                witness = f"{cell['context']} B2 {event['phase']} second {event['timeS']:.2f} blue-depot {pid}"
                admissions.extend([{"timeS": t, "piece": pid, "kind": "acquire"},
                                   {"timeS": t, "piece": pid, "kind": "accept", "witness": witness}])
        episodes.append({**common, "runId": cell["context"], "revision": study["profileSha256"],
                         "condition": match["id"], "evidence": "field-rehearsal",
                         "variation": {"peerProgram": team[3]["plans"]["Shift 1"],
                                       "ourOpening": team[2]["plans"]["AUTO"], "autoLeadingSide": leader},
                         "windowS": [start, end], "initialPieces": sorted(inventory), "events": admissions})
    source = output / "replenishment-observations.json"
    save(source, {"rulesProfileSha256": digest(PROFILE), "roleStudySha256": digest(HERE / "study.json"),
                  "demand": demand, "episodes": episodes})
    manifest = output / "throughput.json"
    save(manifest, {"schema": "agent-frc/throughput-study@1", "demand": receipt(source, "/demand"),
                    "episodes": [{"id": row["runId"], "source": receipt(source, f"/episodes/{i}")}
                                 for i, row in enumerate(episodes)]})
    return cli(plugin, "hardening.mjs", "throughput", manifest, output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plugin", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    study = cli(args.plugin, "strategy-lab.mjs", PROFILE, HERE / "study.json")
    save(args.output / "alliance-results.json", study)
    design = cargo_comparison(args.plugin, args.output)
    elevation = cli(args.plugin, "hardening.mjs", "elevation", HERE / "elevation.json", ROOT)
    throughput = transport_throughput(args.plugin, args.output, study)
    for name, report in (("design", design), ("elevation", elevation), ("throughput", throughput)):
        save(args.output / (name + "-results.json"), report)
    observations = {
        "roleMargins": {cell["context"] + "/" + cell["role"]: cell["margin"] for cell in study["cells"]},
        "cargo": {concept["id"]: {case["id"]: case["status"] for case in concept["cases"]}
                  for concept in design["concepts"]},
        "elevation": {mechanism["id"]: mechanism["status"] for mechanism in elevation["mechanisms"]},
        "freshAdmissions": {episode["id"]: episode["accepted"] for episode in throughput["episodes"]},
    }
    if observations != read(HERE / "expected.json"):
        raise ValueError("The reproduced results differ from the student evidence: " + str(observations))
