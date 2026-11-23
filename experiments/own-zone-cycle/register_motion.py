"""Generate the project-owned checked chapter register from the independent contact trace."""

import math
import numpy as np
from qualify_counter import HERE, ROOT, digest, read, write


def ref(p):
    return {"file": p.relative_to(ROOT).as_posix(), "sha256": digest(p)}


def main():
    report = HERE / "counter-result.json"
    replay = HERE / "counter-replay.json"
    clip = ROOT / "cad/archived-views/robot/cad/own-zone.glb"
    data, summary = read(replay), read(report)
    core = {
        "revision": "R2C",
        "attempt": "Neutral return Shift 1, forward corridor",
        "piece": summary["piece"],
        "clock": "local contact trial",
        "frame": "glTF scene",
        "unit": "m",
    }
    path = np.array(data["mechanismRows"])

    def local_at(t):
        xyz = np.array([np.interp(t, path[:, 0], path[:, j]) for j in [1, 2, 3]]) / 1000
        return [xyz[0], xyz[2], -xyz[1]]

    t, x, y, z = data["flightRows"][-1]
    x -= data["robotFieldM"][0]
    y -= data["robotFieldM"][1]
    h = data["headingRad"]
    last = [x * math.cos(h) + y * math.sin(h), z, x * math.sin(h) - y * math.cos(h)]
    cut = data["atLift"]
    end = data["atRelease"] + t
    states = [
        {**core, "timeS": t, "position": loc}
        for t, loc in [
            (-0.7, local_at(-0.7)),
            (cut, local_at(cut)),
            (cut, local_at(cut)),
            (end, last),
        ]
    ]
    selected = next(
        r
        for r in summary["rows"]
        if r["selectedTrafficPose"] and r["dt"] == 0.000125 and r["wheelMps"] == 1
    )
    assert (
        selected["pointsActiveScenario"] == 1
        and selected["pointsSameTrialInactive"] == 0
    )
    events = []
    annotations = [
        (
            "Carpet pickup",
            "capture",
            "target",
            "reached",
            "The moving intake brought this same ball across the modeled capture threshold.",
        ),
        (
            "Guided handoff",
            "handoff",
            "target",
            "reached",
            "The ball center rose through the 540 mm handoff plane.",
        ),
        (
            "Release",
            "release",
            "target",
            "reached",
            "The ball left the paired wheels with the recorded contact velocity.",
        ),
        (
            "Full HUB opening",
            "full-aperture",
            "target",
            "reached",
            "The full sphere passed all six boundaries before its first field contact.",
        ),
        (
            "Counter beam blocked",
            "counter-blocked",
            "target",
            "reached",
            "The sphere intercepted all rays between sensor and reflector housing bounds.",
        ),
        (
            "FUEL clear downstream",
            "modeled-active-score",
            "score",
            "scored",
            "Channel 3 had one interruption then cleared downstream in the active blue HUB, at 16.987 s in Shift 1.",
        ),
    ]
    for label, kind, category, outcome, criterion in annotations:
        row = {
            **core,
            "type": kind,
            "kind": category,
            "qualified": True,
            "target": label,
            "criterion": criterion,
            "timeS": summary["eventsRunS"][label],
        }
        if category == "score":
            row["rule"] = "Kickoff V0 §6.5.1 and Table 6-3. One modeled point."
        events.append(row)
    source_refs = [ref(report), ref(replay)]
    trace, obs = HERE / "motion-checkpoints.json", HERE / "motion-observations.json"
    write(trace, {"sources": source_refs, "rows": states})
    write(obs, {"sources": source_refs, "events": events})
    chapters = []
    for i, (name, start, stop) in enumerate(
        [("Pickup and lift", -0.7, cut), ("Release and HUB entry", cut, end)]
    ):
        entry = {
            "id": str(i),
            "label": name,
            "animation": name,
            "node": "One nominal FUEL",
            "start": "/rows/" + str(i * 2),
            "end": "/rows/" + str(i * 2 + 1),
            "sync": [
                {"runS": start, "clipS": 0},
                {"runS": stop, "clipS": float(np.float32(stop - start))},
            ],
            "events": [
                {
                    "id": r["type"],
                    "timeS": r["timeS"],
                    "type": r["type"],
                    "outcome": annotations[j][3],
                    "pointer": "/events/" + str(j),
                }
                for j, r in enumerate(events)
                if (i == 0 and j < 2) or (i == 1 and j >= 2)
            ],
        }
        if i:
            entry["join"] = {"kind": "position", "tolerance": 0}
        chapters.append(entry)
    write(
        HERE / "motion-chapters.json",
        {
            "schema": "agent-frc/replay-chapters@1",
            "revision": "R2C",
            "media": ref(clip),
            "trace": ref(trace),
            "observations": ref(obs),
            "chapters": chapters,
        },
    )


if __name__ == "__main__":
    main()
