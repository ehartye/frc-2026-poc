"""Project-authored inputs for the standardized preliminary review scene of a release (review-data-RELEASE.json).

build_package.py --release calls write() with the package it just built. Every value cites its source; anything
without a source is recorded as not supplied.
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
                                f"No mechanism moves it in {len(free)} cases (carpet approach, free flight, rolling on stopped belts, and riding with the field): {', '.join(free)}. Those strokes carry no transportedBy and rest on the pinned field-trials.json trace named in each case basis"],
                          supplied=bool(rows), source="layout.json stages[].transportedBy and paths.json case bases")
            continue
        c = chain(g)
        if c:
            c[0] = "Group datum: " + c[0]
        out[n] = (dict(path=c, supplied=True, source="layout.json mounts") if c else
                  dict(path=[], supplied=False, reason=f"The layout registers no mount datum for group '{g}'"))
    return out


def write(release_dir, plan, trial_data, fuel_index, measured):
    release_dir = Path(release_dir)
    sha = lambda f: hashlib.sha256((release_dir / f).read_bytes()).hexdigest()
    pin = lambda f: dict(file=f, sha256=sha(f))
    motion = json.loads((release_dir / plan["motion"]["file"]).read_text(encoding="utf-8"))
    budgets = json.loads((release_dir / plan["budgets"]["file"]).read_text(encoding="utf-8"))
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
    lch = trials["launch-nominal"]
    data = dict(
        schema="frc-2026-poc/preliminary-review-data@1", release=release_dir.name, note=NOTE,
        runningAdditions=dict(
            source=pin(plan["budgets"]["file"]),
            basis=f"budgets.json runningPayloadBasis: '{budgets['runningPayloadBasis']}'",
            items=[dict(name="bumpers", kg=[6.0, 7.5], members=g["bumpers"]["members"], basis="R103 excludes bumpers; 6.0-7.5 kg per budgets.json"),
                   dict(name="battery and leads", kg=[5.0, 6.9], members=g["battery"]["members"], basis="R103 excludes the battery and its connector half; 5.0-6.9 kg per budgets.json"),
                   dict(name="24 FUEL", kg=fuel, members=stored,
                        basis=f"24 FUEL at 0.203-0.227 kg each (budgets.json); the {len(stored)} placed FUEL represent the carried stock")],
            totalKg=[round(v, 3) for v in payload]),
        support=dict(source="layout.json mounts (group-level datums) and stages[].transportedBy; structure-to-frame joints beyond these datums are not registered",
                     members=support_paths(plan, motion)),
        modelNotes=[
            "What it is: the R3-PD2 whole-robot preliminary blockout (tall floor-fed hooded-flywheel shooter on a 680 x 714 mm four-module swerve base). Solids are planning envelopes and simplified material blocks, not a Fusion robot.",
            "Simplified: swerve modules are body, motor and azimuth envelopes; electronics are two panel blocks; belts and rollers are rigid outlines; the HUB and TOWER are V0-dimension fixtures, not the official field model. The intake belt, top roller, flywheel and hood are drawn at the squeeze the physics trials use (dimensions.py), so the tracked FUEL overlaps them by the trial's indentation; each such pair is declared as payload compression in its case.",
            f"Tracked FUEL motion: every one of its {len(fuel_index)} cases is a stroke fitted within {max(r['maxDeviationMm'] for r in fuel_index):.2f} mm (limit 1.5 mm) to the solved acquire, entry, launch and deliver trials in field-trials.json. Each stroke is uniform in its own parameter, so playback timing inside a case is not the trial's; the trial window is in caseTimes. Contact stiffness, damping, friction and rolling resistance are estimates, not measurements, and no FUEL force-deflection curve is available.",
            f"Imposed in the trials: robot approach speed, intake belt speed ({trials['acquire-nominal']['params']['u']} m/s), the floor belt schedule (stopped during entry; {lch['params']['backMps']} m/s back-off, then {lch['params']['feedMps']} m/s feed) and the flywheel surface speed ({lch['params']['wheelMps']} m/s). Whether the motors sustain them under load is not solved.",
            "Prescribed, not simulated, in the package: the intake slide, the field moving in the robot frame (transit and TOWER approach), and the climb strokes.",
            "Unverified: verification gates G1-G7 (verification-gates.json) carry the physical tests; hopper capacity is a free-volume premise; dynamic BUMP crossing and robot-to-robot contact are not evaluated.",
            "Sources and cutoff: FRC REBUILT kickoff manual V0 with Team Update 00, cutoff 2026-01-10 23:59:59 America/New_York (construction-rules.json); field dimensions from the V0 description (geometry.py field_bodies).",
            "Open items: see openItems."],
        focus=dict(component="FUEL tracked", basis="The mission cases follow this FUEL from the carpet into the HUB"),
        caseTimes=dict(source=pin("field-trials.json"),
                       note="Trial seconds are on each trial's own clock (acquire, entry, launch and deliver each start at 0). A FUEL case plays its fitted stroke uniformly.",
                       chain=dict(captureS=trials["acquire-nominal"]["metric"]["value"], seatS=trials["entry-nominal"]["metric"]["value"],
                                  releaseS=round(chain["release"]["t"], 4), scoredS=trials["deliver-nominal"]["metric"]["value"]),
                       cases=times),
        targetAperture=dict(
            name="HUB opening (top)",
            source=dict(rule="construction-rules.json hub: 'Section 5.4; front edge 72 in, 41.7 in hexagonal opening, 47 in footprint'",
                        geometry="geometry.py hexagon_prism: corners on +/-Y, flats facing +/-X", file=pin("construction-rules.json")),
            interpretation="41.7 in (1059.18 mm) treated as across-corners, the smaller conservative inscribed opening (construction-rules.json)",
            frame="HUB-local millimetres: origin at the HUB centre on the carpet, +X/+Y parallel to the robot datum axes",
            cornersMm=hexc,
            placement=dict(shotPoseHubCentreMm=[-2700.0, 0.0], basis="build_package.py hub_shot: HUB centre 2700 mm aft of the robot centre at the delivery pose")),
        openItems=[
            "No hold-back for the seated FUEL. " + next(c["reason"] for c in plan["presentation"]["uncoveredCases"] if c["id"] == "seat-retention-in-transit") + ".",
            "Batch collection is not evaluated: the entry trial is one FUEL in an empty lane with the floor belts stopped; a running belt wedges the FUEL into the stopped pinch (entry-floor-belt-running trials).",
            f"Feed rate: a free FUEL rolls at about a third of the belt speed in the launch trial, so the sustained 2.00 FUEL/s objective rests on gate G1, not on the belt-speed calculation.",
            f"Launch inputs are imposed: flywheel surface speed, belt schedule and the squeeze. The wheel does {lch['wheelDemand']['energyJ']:.0f} J of work per FUEL in the trial, a {lch['wheelDemand']['speedDropPercent']:.1f}% speed drop for a free 0.006 kg m2 wheel, which the trial does not apply. Motor sizing and the FUEL's force-deflection curve are not measured.",
            f"The seat position depends on contact damping, which is an estimate: at damping ratio 0.3 the FUEL rests against the wheel; at 0.20 and 0.10 it rebounds and rests {trials['entry-contact-damping-0.20']['seat']['clearOfFlywheelMm']:.0f} and {trials['entry-contact-damping-0.10']['seat']['clearOfFlywheelMm']:.0f} mm clear of it (still seated, and the launch from there still scores, later). Rest time is {trials['entry-nominal']['metric']['value']:.1f} s; it needed a 0.05 ms timestep to converge.",
            f"Contact stiffness is an estimate and decides the launch: 10 and 30 kN/m score, 7.5 kN/m releases too slowly. The 8 to 16 mm squeeze bracket is a force bracket at 15 kN/m.",
            f"Scoring band: only {chain['scoringBandMps'][0]:.2f} to {chain['scoringBandMps'][1]:.2f} m/s scores at the nominal drag and spin lift and at all four corners. 6.55 m/s misses at the high-drag, high-spin corner and 7.15 m/s at both low-drag corners. The band's ends score off the HUB top plate or cavity wall; the point-mass screen's clean band at this release is narrower (package-facts.json shot.pointMassBands in the experiment folder).",
            f"Intake belt load: the acquisition trial's contacts dissipate up to {trials['acquire-nominal']['beltDemand']['maxFrictionPowerW']:.0f} W at the imposed 3 m/s, above the intake's 30 A supply limit; the trial fails at 2.0 m/s.",
            "A carrier-free FUEL stroke (carpet approach, free flight, rolling on stopped belts) has no evidence slot in the layout schema; its trial window is recorded in the case basis and in caseTimes.",
            "No registered structure-to-frame joint: hopper walls (hopper front upper wall, hopper rear wall, hopper wall left, hopper wall right).",
            "No registered structure-to-frame joint: climber tubes and winch (climber tube left, climber tube right, climber winch) to the climber tube mounts.",
            "Frame-internal joints are not registered: frame rails, floor pan, floor pan front tongue, front lip, climber tube mounts and intake slide rails.",
            "Battery hold-down strap over the battery top is undesigned; the cleats capture it in X only.",
            "Group-level mount datums: right-hand members (climber hook right, climber inner tube right, intake carriage plate right, shooter side plate right) cite the left-hand datum."])
    target = release_dir.parent.parent / f"review-data-{release_dir.name}.json"
    target.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return target
