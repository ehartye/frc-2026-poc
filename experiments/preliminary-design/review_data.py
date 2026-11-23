"""Project-authored inputs for the standardized preliminary review scene of a release (review-data-RELEASE.json).

build_package.py --release calls build() with the package it is about to write, copies the scene fields that the
stock review page reads into the layout's presentation (presentation()), and saves the data with save(). Every
value cites its source; anything without a source is recorded as not supplied.
"""
import hashlib
import json
import math
from pathlib import Path

NOTE = ("Project-authored inputs for the standardized preliminary review scene. Values cite their source; "
        "anything without a source is recorded as not supplied.")


def support_paths(plan, motion, fixture_groups=("field",)):
    """Per-member support paths from the registered mount datums and contact transports (no invented joints)."""
    groups = plan["groups"]
    group_of = {m: g for g, s in groups.items() for m in s["members"]}
    mounts = {}
    for m in plan.get("mounts", []):
        mounts.setdefault(m["group"], []).append(m)
    fixtures = {f["id"] for c in motion["cases"] for f in c.get("fixtures", [])}
    moved = {n for c in motion["cases"] for n in c["moves"]} - fixtures
    wanted = sorted(n for n, g in group_of.items() if g not in fixture_groups and (groups[g]["role"] == "mechanism" or n in moved))
    transport = {}
    for sid, st in plan["stages"].items():
        for payload, spec in (st.get("transportedBy") or {}).items():
            transport.setdefault(payload, []).append((sid, spec))

    def chain(group, seen=()):
        rows = mounts.get(group)
        if not rows:
            return None
        m = rows[0]
        step = (f"{group} mounts on {m['on']} at ({', '.join(f'{v:g}' for v in m['pointMm'])}) mm: {m['basis']}"
                + (f" (+{len(rows) - 1} more mount datum{'s' if len(rows) > 2 else ''})" if len(rows) > 1 else ""))
        host = group_of.get(m["on"])
        if host is None or host in seen:
            return [step]
        if groups[host]["role"] == "structure" and not mounts.get(host):
            return [step, f"{m['on']} is a {host} structure member"]
        rest = chain(host, seen + (group,))
        return [step] + (rest if rest else [f"{m['on']} ({host}): no registered mount datum onward (not supplied)"])

    out = {}
    for n in wanted:
        g = group_of[n]
        if groups[g]["role"] == "payload":
            rows = transport.get(g, [])
            moving = [c["id"] for c in motion["cases"] if n in c["moves"] and c["stage"] != "service"]
            carried = sorted(sid for sid, _ in rows)
            free = [c for c in moving if c not in carried]
            mech = sorted({m for _, spec in rows for m in spec.get("mechanisms", [])})
            out[n] = dict(path=[f"Moved by contact transport ({', '.join(mech)}) in {len(carried)} cases, each bound to its trial window by a pinned transport record: {', '.join(carried)}",
                                f"No mechanism moves it in {len(free)} cases (carpet approach, flight over the back plate, the fall to the floor, free flight to the HUB, and riding with the field): {', '.join(free)}. The free-path strokes pin their trial window through freePath"],
                          supplied=bool(rows), source="layout.json stages[].transportedBy and freePath, and paths.json case bases")
            continue
        c = chain(g)
        if c:
            c[0] = "Group datum: " + c[0]
        out[n] = (dict(path=c, supplied=True, source="layout.json mounts") if c else
                  dict(path=[], supplied=False, reason=f"The layout registers no mount datum for group '{g}'"))
    return out


def build(release_dir, repo, plan, trial_data, fuel_index, measured, risks, records):
    """release_dir is the release folder; every pin in plan is a path from repo, the project root."""
    release_dir, repo = Path(release_dir), Path(repo)
    pin = lambda f: dict(file=f, sha256=hashlib.sha256((repo / f).read_bytes()).hexdigest())
    here = lambda name: (release_dir / name).relative_to(repo).as_posix()
    motion = json.loads((repo / plan["motion"]["file"]).read_text(encoding="utf-8"))
    budgets = json.loads((repo / plan["budgets"]["file"]).read_text(encoding="utf-8"))
    trials = {t["name"]: t for t in trial_data["trials"]}
    g = plan["groups"]
    circ = 1059.18 / 2
    hexc = [[round(circ * math.cos(math.radians(90 + 60 * k)), 2), round(circ * math.sin(math.radians(90 + 60 * k)), 2), 1828.8] for k in range(6)]
    times = {row["case"]: dict(seconds=[row["fromS"], row["toS"]], trial=row["trial"],
                               basis=f"{row['stroke']} stroke fitted to this window of the solved trace, within {row['maxDeviationMm']:.2f} mm")
             for row in fuel_index}
    hang = next(e["t"] for e in trials["hang-nominal"]["events"] if e["event"].startswith("stroke complete"))
    times["climb-lift"] = dict(seconds=[0.0, hang], trial="hang-nominal", basis=f"lift stroke complete; then a 3 s brake hold to {hang + 3:.4f} s")
    for cid in list(plan["stages"]) + ["package-displacement-control"]:
        times.setdefault(cid, dict(supplied=False, reason="No trial or rehearsal times this prescribed case"))
    payload = budgets["runningPayloadKg"]
    fuel = [round(24 * 0.203, 3), round(24 * 0.227, 3)]
    stored = g["stored FUEL"]["members"] + g["tracked FUEL"]["members"]
    chain = trial_data["chain"]
    lch, acq, ent = trials["launch-nominal"], trials["acquire-nominal"], trials["entry-nominal"]
    patterns = [t for n, t in trials.items() if n == "hopper-cycle-nominal" or n.startswith("hopper-cycle-pattern-")]
    secs = sorted(t["feed"]["lastFedS"] for t in patterns)
    closed = [r for r in risks if r.get("closedBy")]
    bench = [r for r in risks if r.get("benchTest")]
    prescribed = sorted(c for c, t in times.items() if t.get("supplied") is False and c != "package-displacement-control")
    data = dict(
        schema="frc-2026-poc/preliminary-review-data@2", release=release_dir.name, note=NOTE,
        runningAdditions=dict(
            source=pin(plan["budgets"]["file"]),
            basis=f"budgets.json runningPayloadBasis: '{budgets['runningPayloadBasis']}'",
            items=[dict(name="bumpers", kg=[6.0, 7.5], members=g["bumpers"]["members"], basis="R103 excludes bumpers; 6.0-7.5 kg per budgets.json"),
                   dict(name="battery and leads", kg=[5.0, 6.9], members=g["battery"]["members"], basis="R103 excludes the battery and its connector half; 5.0-6.9 kg per budgets.json"),
                   dict(name="24 FUEL", kg=fuel, members=stored,
                        basis=f"24 FUEL at 0.203-0.227 kg each (budgets.json); the {len(stored)} placed FUEL represent the carried stock")],
            totalKg=[round(v, 3) for v in payload]),
        support=dict(source="layout.json mounts (one entry per separately mounted member) and the stages' transportedBy and freePath records",
                     members=support_paths(plan, motion)),
        modelNotes=[
            "What it is: the R3-PD3 whole-robot preliminary blockout (tall floor-fed hooded-flywheel shooter with a chute intake on a 680 x 714 mm four-module swerve base). Solids are planning envelopes and simplified material blocks, not a Fusion robot.",
            "Changed from layout-001: the intake is a chute that lifts each FUEL up its own back plate and throws it into the hopper from above; the hopper floor is a two-lane channel under sloped shelves; a braked feeder roller per lane over a fixed deck holds and meters the FUEL; the flywheel carries an inertia ring and runs whenever FUEL is aboard; the battery has a strap under a lift-out shelf panel; the hang swings the hooks first and stows the intake between them.",
            "Simplified: swerve modules are body, motor and azimuth envelopes; electronics are panel blocks; belts and rollers are rigid outlines; the back plate is drawn solid; the HUB and TOWER are V0-dimension fixtures, not the official field model. The intake belt, top roller, back plate, feeder roller, flywheel and hood are drawn at the squeeze the physics trials use (dimensions.py), so the tracked FUEL overlaps them by the trial's indentation; each such pair is declared as payload compression in its case.",
            f"Tracked FUEL motion: every one of its {len(fuel_index)} cases is a stroke fitted within {max(r['maxDeviationMm'] for r in fuel_index):.2f} mm (limit 1.5 mm) to the solved acquire, entry, launch and deliver trials in field-trials.json, and pins a record of its trial window with that trial's qualification. Each stroke is uniform in its own parameter, so playback timing inside a case is not the trial's; the trial window is in caseTimes.",
            f"Solved in the trials: the FUEL against every surface; the intake belt speed under its motor and current limits; the flywheel speed under the FUEL's load and its motors. Imposed: robot approach speed ({acq['params']['vRobot']} m/s), floor belt speed ({ent['params']['belt']} m/s) and feeder roller speeds ({ent['params']['stageMps']} and {lch['params']['feederMps']} m/s).",
            f"Not shown as motion: the 24-FUEL hopper cycle (collect through the chute, hold through a 0.5 g stop, start and turn, feed), the hold-back, the 24-shot batch and the hang are physics trials in field-trials.json, summarised in trial-hopper-cycle.json, trial-hold.json, trial-batch.json and trial-hang.json beside this plan. Their cases here ({', '.join(c for c in ('loaded-transit', 'climb-lift') if c in plan['stages'])}) play prescribed strokes. The hopper cycle fed all 24 in {secs[0]:.1f}-{secs[-1]:.1f} s over {len(patterns)} arrival patterns.",
            "Prescribed, not simulated, in the package: the intake slide, the field moving in the robot frame (transit and TOWER approach), the hook swing and the climb strokes: " + ", ".join(prescribed) + ".",
            "Contact stiffness, damping, friction and rolling resistance are estimates, not measurements, and no FUEL force-deflection curve is available. Motor figures are a published brushless curve.",
            "Sources and cutoff: FRC REBUILT kickoff manual V0 with Team Update 00, cutoff 2026-01-10 23:59:59 America/New_York (construction-rules.json); field dimensions from the V0 description (geometry.py field_bodies).",
            "Risks closed by design and bench tests still to run: see openItems."],
        focus=dict(component="FUEL tracked", basis="The mission cases follow this FUEL from the carpet into the HUB"),
        caseTimes=dict(source=pin(here("field-trials.json")),
                       note="Trial seconds are on each trial's own clock (acquire, entry, launch and deliver each start at 0). A FUEL case plays its fitted stroke uniformly.",
                       chain=dict(captureS=trials["acquire-nominal"]["metric"]["value"], stagedS=trials["entry-nominal"]["metric"]["value"],
                                  releaseS=round(chain["release"]["t"], 4), scoredS=trials["deliver-nominal"]["metric"]["value"]),
                       cases=times),
        trialRecords=records,
        targetAperture=dict(
            name="HUB opening (top)",
            source=dict(rule="construction-rules.json hub: 'Section 5.4; front edge 72 in, 41.7 in hexagonal opening, 47 in footprint'",
                        geometry="geometry.py hexagon_prism: corners on +/-Y, flats facing +/-X", file=pin(here("construction-rules.json"))),
            interpretation="41.7 in (1059.18 mm) treated as across-corners, the smaller conservative inscribed opening (construction-rules.json)",
            frame="HUB-local millimetres: origin at the HUB centre on the carpet, +X/+Y parallel to the robot datum axes",
            cornersMm=hexc,
            placement=dict(shotPoseHubCentreMm=[-2700.0, 0.0], basis="build_package.py hub_shot: HUB centre 2700 mm aft of the robot centre at the delivery pose")),
        openItems=[f"Closed by design ({r['id']}): {r['risk']}. {r['closedBy']}." for r in closed]
                  + [f"Bench test ({r['id']}): {r['risk']}. Measure: {r['benchTest']['measure']}; pass {r['benchTest']['pass']}, fail {r['benchTest']['fail']} {r['benchTest'].get('unit', '')}." for r in bench]
                  + ["The loaded acceleration limit of 0.5 g is not in the field rehearsal: its cycle times were credited without it and are not re-run here.",
                     "The feeder shafts through the channel walls, the right climber cable across the front rail and the hood's thickness are not drawn.",
                     "The stowed carriage stands in the front half of the hopper, so the intake cannot stow while FUEL is forward of the stage; the hang is taken with the hopper empty."])
    return data


def presentation(data):
    """The review-scene fields of layout.json presentation, taken from the review data."""
    def path(row):
        return " -> ".join(row["path"]) if row.get("supplied") else "Not supplied: " + row["reason"]
    return dict(title="Floor-fed hooded flywheel shooter with a chute intake", context="R3 \u00b7 Issue R3-PD3 \u00b7 preliminary layout",
                focus=f"{data['focus']['component']}: {data['focus']['basis']}.",
                notes=data["modelNotes"] + data["openItems"],
                runningAdditions=[dict(name=i["name"], kg=i["kg"], members=i["members"]) for i in data["runningAdditions"]["items"]],
                runningBasis=data["runningAdditions"]["basis"],
                loadPaths={member: path(row) for member, row in data["support"]["members"].items()})


def save(release_dir, data):
    release_dir = Path(release_dir)
    target = release_dir / "review-data.json"
    target.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return target
