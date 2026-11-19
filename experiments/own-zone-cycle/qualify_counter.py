"""Bind field drive, same-piece release, traffic, zone and active-clock evidence."""

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def read(path):
    return json.loads(path.read_bytes())


def write(path, data):
    path.write_text(
        json.dumps(data, indent=2, allow_nan=False) + "\n",
        encoding="utf8",
        newline="\n",
    )


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def qualify(cache):
    profile = read(ROOT / "kickoff/rules-model.json")
    strategy = read(ROOT / "kickoff/selected-strategy.json")["case"]
    study = read(HERE / "single-piece.json")
    comparison = read(HERE / "approach-comparison.json")
    nominal = study["refinements"][-1]
    shift_start = (
        strategy["stockReadyAtSource"] + strategy["loadedTravel"] + strategy["settle"]
    )
    baseline = next(r for r in comparison["configs"] if r["offsetM"] == 0.25)
    if (
        baseline["contactTicks"]
        or min(
            baseline["minimumStaticClearanceIn"],
            baseline["minimumPeerProjectionGapIn"],
            baseline["wholeBumperZoneClearanceIn"],
        )
        <= 0
    ):
        raise ValueError("Unavailable scoring pose")
    flight, release = nominal["flight"], nominal["mechanism"]["release"]
    start, finish = flight["firstSpherePassS"], flight["lastSpherePassS"]
    normals = np.array(
        [
            [
                math.cos(math.pi / 6 + i * math.pi / 3),
                math.sin(math.pi / 6 + i * math.pi / 3),
            ]
            for i in range(6)
        ]
    )
    center = np.array(study["registeredHub"]["centerM"])
    data = []
    representative = None

    def activity(leader, t):
        station = next(
            s
            for s in profile["rehearsal"]["stations"]
            if s["id"] == comparison["station"]
        )
        return any(
            w["phase"] == "Shift 1"
            and w["fromS"] <= t < w["toS"]
            and w.get("firstPeriodLeader", leader) == leader
            for w in station["activeWindows"]
        )

    game = next(
        m
        for m in read(ROOT / "kickoff/match-series.json")["matches"]
        if m["id"] == comparison["scenario"]
    )["game"]
    if game["firstPeriodCount"]["red"] <= game["firstPeriodCount"]["blue"]:
        raise ValueError("Scenario needs red AUTO lead")
    for filename in [
        "r2c-clear-corridor-coarse.json",
        "r2c-clear-corridor.json",
        "r2c-clear-corridor-refined.json",
        "r2c-qualified-fine.json",
    ]:
        for trial in read(cache / filename):
            offset = trial["towardHubOffsetM"]
            if abs(offset) < 0.001 and (trial["wheelMps"], trial["tubeMps"]) in [
                (1, 1),
                (2, 2),
            ]:
                continue
            first = min(c["t"] for c in trial["contacts"].values())
            if first <= finish:
                raise ValueError(
                    "Full-ball aperture test is interrupted by field contact"
                )
            margins = [
                profile["fieldFeatures"]["hubOpening"] * 0.0254 / 2
                - profile["fieldFeatures"]["fuelDiameter"] * 0.0254 / 2
                - normals
                @ (
                    np.array(trial["releaseFieldM"][:2])
                    + np.array(flight["velocityFieldMps"][:2]) * t
                    - center[:2]
                )
                for t in [start, finish]
            ]
            margin = float(np.min(margins))
            crossings = [
                h
                for h in trial["channels"]
                if h["upstreamClear"]
                and h["downstreamClear"]
                and h["enterS"] is not None
                and h["leaveS"] > h["enterS"]
                and h["downstreamClearS"] >= h["leaveS"]
                and h["transitions"] == 1
            ]
            if len(crossings) > 1:
                raise ValueError("Same piece interrupted multiple lanes")
            hit = crossings[0] if crossings else None
            shift_t = (
                shift_start + release["timeS"] + hit["downstreamClearS"]
                if hit
                else None
            )
            physical = bool(margin > 0 and hit)
            selected_pose = offset == baseline["offsetM"]
            active = bool(selected_pose and physical and activity("red", shift_t))
            inactive = bool(selected_pose and physical and activity("blue", shift_t))
            row = {
                k: v for k, v in trial.items() if k not in ("trajectory", "channels")
            }
            row.update(
                channel=hit,
                apertureMarginM=margin,
                fullApertureS=finish,
                firstFieldContactS=first,
                clearAtShiftS=shift_t,
                selectedTrafficPose=selected_pose,
                physicalPassage=physical,
                pointsActiveScenario=int(active),
                pointsSameTrialInactive=int(inactive),
            )
            if physical and selected_pose and trial["dt"] == 0.000125:
                representative = (trial, row)
            data.append(row)
    assert representative is not None
    trial, selected = representative
    replay = read(HERE / "replay.json")
    replay["flightRows"] = trial["trajectory"]
    replay["robotFieldM"] = (
        np.array(flight["robotFieldM"])
        + 0.25
        * np.array([math.cos(flight["headingRad"]), math.sin(flight["headingRad"])])
    ).tolist()
    bounds = study["registeredHub"]["markerBoundsByType"]
    order = lambda b: (b[1] + b[4]) / 2
    channel = selected["channel"]["channel"] - 1
    replay["counterMarkerBoundsMm"] = [
        sorted(bounds[key], key=order)[channel]
        for key in ["Counting Sensor", "Sensor Reflector"]
    ]
    events = {
        "Carpet pickup": replay["atPickup"],
        "Guided handoff": replay["atLift"],
        "Release": replay["atRelease"],
        "Full HUB opening": replay["atRelease"] + finish,
        "Counter beam blocked": replay["atRelease"] + selected["channel"]["enterS"],
        "FUEL clear downstream": replay["atRelease"]
        + selected["channel"]["downstreamClearS"],
    }
    replay["eventsRunS"] = events
    chain = {
        "schema": "frc-2026/registered-counter@1",
        "piece": "R2C-FUEL-01",
        "basis": "100% prebuild, contact-only field transport",
        "rules": "Kickoff V0 + TU00, G407, §§6.4.1 and 6.5.1, Table 6-3",
        "source": {
            "cad": study["cadSha256"],
            "field": study["supplierFieldSha256"],
            "ruleRegister": digest(ROOT / "kickoff/rule-register.json"),
            "samePieceInput": digest(HERE / "single-piece.json"),
            "release": release,
            "nominalContactNperM": 30000,
            "noLoadSpeedFraction": 0.7,
        },
        "shiftClockOriginS": shift_start,
        "phase": "Shift 1",
        "scenario": comparison["scenario"],
        "selectedPose": baseline,
        "eventsRunS": events,
        "rows": data,
    }
    write(HERE / "counter-result.json", chain)
    write(HERE / "counter-replay.json", replay)
    return selected


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("cache", type=Path)
    row = qualify(p.parse_args().cache)
    print(
        row["pointsActiveScenario"],
        row["pointsSameTrialInactive"],
        row["clearAtShiftS"],
    )
