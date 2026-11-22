"""Build a versioned preliminary design review release from a checked Agent FRC package.

Season-neutral. The release reads only the package player that the layout check verified
(`receipt.view`), so its meshes and rigid motion are the plugin's own tessellation and motion
sampling of the reviewed STEP. Every input is pinned by SHA-256 in release.json.

Usage: python -I -B scripts/preliminary_review.py RELEASE_CONFIG.json [--check]
"""
import argparse
import gzip
import hashlib
import io
import json
import math
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRAMES = 25
IDENTITY = [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0]


def fail(message):
    raise SystemExit("preliminary review: " + message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def project_file(name):
    path = (ROOT / name).resolve()
    if Path(name).is_absolute() or not path.is_relative_to(ROOT) or not path.is_file():
        fail("expected a project-relative input file: " + str(name))
    return path


RELOCATE = []  # (prefix recorded in the package, prefix in this repository)


def located(name):
    """Map a path recorded by the package to its copy in this repository (byte-identical)."""
    for old, new in RELOCATE:
        if name.startswith(old):
            return new + name[len(old):]
    return name


def payload(name):
    """Exact package bytes. A `.gz` copy stands for the uncompressed file the receipt pins."""
    data = project_file(name).read_bytes()
    return gzip.decompress(data) if name.endswith(".gz") else data


def read_json(name):
    return json.loads(payload(located(name)).decode("utf-8-sig"))


def pin(name):
    return {"file": name, "sha256": digest(project_file(name).read_bytes())}


def player_data(name):
    text = payload(name).decode("utf-8")
    tag = '<script type="application/json" id="data">'
    start = text.find(tag)
    if start < 0:
        fail("the package player has no embedded data: " + name)
    start += len(tag)
    return json.loads(text[start:text.index("</script>", start)])


# ---------------------------------------------------------------- mesh measures
def closed_and_volume(vertices, faces):
    edges = Counter()
    volume = 0.0
    for a, b, c in faces:
        for e in ((a, b), (b, c), (c, a)):
            edges[e] += 1
        p, q, r = vertices[a], vertices[b], vertices[c]
        volume += (p[0] * (q[1] * r[2] - q[2] * r[1]) - p[1] * (q[0] * r[2] - q[2] * r[0])
                   + p[2] * (q[0] * r[1] - q[1] * r[0])) / 6.0
    closed = all(n == 1 and edges.get((b, a)) == 1 for (a, b), n in edges.items())
    return closed, volume


def compose(m, n):
    """Row-major 3x4 product m * n."""
    out = []
    for r in range(3):
        row = m[4 * r:4 * r + 4]
        for c in range(4):
            v = sum(row[k] * n[4 * k + c] for k in range(3))
            out.append(v + (row[3] if c == 3 else 0.0))
    return out


def rigid_fit(source, target):
    """Rigid transform mapping source vertices onto target (same order), or None."""
    import numpy as np
    a, b = np.asarray(source, float), np.asarray(target, float)
    if a.shape != b.shape:
        return None
    ca, cb = a.mean(0), b.mean(0)
    u, _, vt = np.linalg.svd((a - ca).T @ (b - cb))
    d = np.sign(np.linalg.det(vt.T @ u.T))
    rot = vt.T @ np.diag([1, 1, d]) @ u.T
    t = cb - rot @ ca
    if np.abs(a @ rot.T + t - b).max() > 1e-4:
        return None
    return [float(rot[r, c]) if c < 3 else float(t[r]) for r in range(3) for c in range(4)]


def tidy(m):
    return [round(v, 9) if i % 4 != 3 else round(v, 4) for i, v in enumerate(m)]


# ---------------------------------------------------------------- sanitizer
def scrub(value, rules):
    if isinstance(value, str):
        for pattern, replacement in rules:
            value = re.sub(pattern, replacement, value)
        return value
    if isinstance(value, list):
        return [scrub(v, rules) for v in value]
    if isinstance(value, dict):
        return {scrub(k, rules): scrub(v, rules) for k, v in value.items()}
    return value


def build(config_name):
    config = read_json(config_name)
    if config.get("schema") != "agent-frc/preliminary-review-release@1":
        fail("unknown release configuration schema")
    package = config["package"]
    RELOCATE[:] = [tuple(r) for r in config.get("relocate", [])]
    layout, receipt, budgets = (read_json(package[k]) for k in ("layout", "receipt", "budgets"))
    if receipt.get("status") != "layout-checked":
        fail("the receipt is not layout-checked")
    view_pin = {"file": package["view"], "sha256": digest(payload(package["view"]))}
    if located(receipt["view"]["file"]).removesuffix(".gz") != package["view"].removesuffix(".gz")             or receipt["view"]["sha256"] != view_pin["sha256"] or not receipt["view"]["verified"]:
        fail("the package player differs from the verified receipt view")
    for key in ("step", "motion"):
        if layout[key] != receipt[key]:
            fail("layout and receipt name different " + key)
    data = player_data(package["view"])
    if data["step"] != receipt["step"] or data["motion"] != receipt["motion"] or data["issue"] != receipt["issue"]:
        fail("the package player is bound to different geometry")
    requirements = read_json(budgets["requirements"]["file"])
    rules = [tuple(r) for r in config.get("scrub", [])]

    groups = data["groups"]
    member_group = {n: g for g, spec in groups.items() for n in spec["members"]}
    fixture_groups = set(config.get("fixtureGroups", []))
    components = data.get("components", {})
    palette = data["palette"]
    mass_basis = {n: row for row in budgets["masses"] for n in row["members"]}

    # One mesh per body; per-case placement differences become a rigid offset on that case's frames.
    cases_in = data["cases"]
    names = sorted(set().union(*(c["bodies"] for c in cases_in)))
    receipt_removed = {c["case"]: set(c.get("removed") or []) for c in receipt["cases"]}
    for c in cases_in:
        absent = set(names) - set(c["bodies"])
        if absent != receipt_removed.get(c["id"], set()):
            fail("case roster differs from the receipt's removed bodies: " + c["id"])
    base, offsets = {}, {}
    for name in names:
        holders = [c for c in cases_in if name in c["bodies"]]
        variants = Counter(json.dumps(c["bodies"][name]["vertices"]) for c in holders)
        key = variants.most_common(1)[0][0]
        base[name] = next(c["bodies"][name] for c in holders if json.dumps(c["bodies"][name]["vertices"]) == key)
        for c in holders:
            mesh = c["bodies"][name]
            if mesh["vertices"] is base[name]["vertices"] or mesh["vertices"] == base[name]["vertices"]:
                continue
            if mesh["triangles"] != base[name]["triangles"]:
                fail("non-rigid mesh variant for " + name + " in " + c["id"])
            fit = rigid_fit(base[name]["vertices"], mesh["vertices"])
            if fit is None:
                fail("no rigid placement for " + name + " in " + c["id"])
            offsets[(c["id"], name)] = fit

    bodies, fixtures = {}, []
    for name in names:
        mesh = base[name]
        v = [[round(x, 4) for x in p] for p in mesh["vertices"]]
        faces = [f for f in mesh["triangles"] if len(set(f)) == 3]  # pole slivers of a sphere carry no area
        closed, volume = closed_and_volume(v, faces)
        group = member_group.get(name)
        if group is None:
            fail("unregistered body " + name)
        info = components.get(name, {})
        aliases = config.get("categoryAliases", {})
        candidates = [info.get("category"), config.get("groupCategories", {}).get(group), groups[group]["role"]]
        candidates = [c for c in candidates if c]
        category = next((k for c in candidates for k in (c, aliases.get(c)) if k in palette), "reference")
        if category not in palette:
            fail("no palette color for category " + category)
        row = mass_basis.get(name)
        basis = info.get("basis") or (("Mass line “" + row["id"] + "” " + "–".join(f"{k:g}" for k in row["kg"]) + " kg: " + row["basis"])
                                      if row else "Placed planning envelope; carried outside the inspection mass ledger")
        body = dict(v=v, f=faces, volume=abs(volume), closed=closed,
                    error=abs(abs(volume) - mesh["volumeMm3"]), category=category, group=group,
                    material=info.get("material", "Preliminary planning envelope"),
                    purpose=info.get("purpose"), rationale=info.get("rationale"), basis=basis)
        if group in fixture_groups:
            body["fixture"] = True
            fixtures.append(name)
        bodies[name] = body

    receipt_cases = {c["case"]: c for c in receipt["cases"]}

    def frames_for(case_id, name, matrices):
        offset = offsets.get((case_id, name))
        seq = [compose(m, offset) if offset else m for m in matrices]
        if len(seq) == 1:
            seq = seq * FRAMES
        return [tidy(m) for m in seq]

    def series_of(case_id, frame_map):
        series, rig = {}, {}
        for name, seq in frame_map.items():
            if all(m == tidy(IDENTITY) for m in seq):
                continue
            key = json.dumps(seq)
            label = series.setdefault(key, ("s" + str(len(series)), seq))[0]
            rig[name] = label
        return {label: seq for label, seq in series.values()}, rig

    def stage_text(case_id, i, n):
        spec = layout["stages"][case_id]
        moving = ", ".join(spec.get("movingGroups", []))
        return f"{case_id} · {spec['purpose']} · {round(100 * i / (n - 1))}% of the prescribed path · moving: {moving or 'none'}"

    def gap_of(pairs):
        gaps = [p["witness"]["gapMm"] for p in pairs if isinstance(p.get("witness"), dict) and p["witness"].get("gapMm") is not None]
        return f"{min(gaps):.2f}" if gaps else None

    def results_of(pairs):
        out = []
        for p in pairs:
            w = dict(p["witness"]) if isinstance(p.get("witness"), dict) else {"reason": p.get("method", "recorded")}
            if p.get("method"):
                w.setdefault("reason", p["method"])
            out.append(dict(pair=p["pair"], status=p["status"], witness=w))
        return out

    duty_of = {}
    for row in data["power"]:
        if row["batteryCondition"] == "weak":
            duty_of.setdefault(row["stage"], row["case"])

    cases = []
    case_frames = {}
    for c in cases_in:
        cid = c["id"]
        frame_map = {n: frames_for(cid, n, c["bodies"][n]["matrices"]) for n in names if n in c["bodies"]}
        case_frames[cid] = frame_map
        rc = receipt_cases[cid]
        spec = layout["stages"][cid]
        series, rig = series_of(cid, frame_map)
        cases.append(dict(id=f"{cid} · {spec['purpose']}", key=cid, stage=spec["purpose"],
                          positions=[[0, 0]] * FRAMES, frames={}, series=series, rig=rig,
                          removed=sorted(rc.get("removed") or []), status=rc["status"], gap=gap_of(rc["pairs"]),
                          results=results_of(rc["pairs"]), duty=duty_of.get(cid),
                          measure=[stage_text(cid, i, FRAMES) for i in range(FRAMES)],
                          basis=f"{cid}: {spec['purpose']} case. Moving groups: {', '.join(spec.get('movingGroups', [])) or 'none'}. "
                                f"{spec.get('allowanceBasis', '')} Receipt status {rc['status']}; "
                                f"{rc['counts'].get('broadPhase', 0)} broad-phase pairs, {rc['counts'].get('bounded', 0)} bounded."))

    # The main operating cycle: the receipt's registered cycle, played stage by stage from the installed pose.
    cycle = receipt["cycle"]
    if config.get("cycleCase"):
        cc = config["cycleCase"]
        if any(receipt_removed.get(s) for s in cycle):
            fail("a cycle stage removes bodies; the cycle playback needs a full roster")
        frame_map = {n: [m for s in cycle for m in case_frames[s][n]] for n in names}
        series, rig = series_of(cc["key"], frame_map)
        total = FRAMES * len(cycle)
        results = []
        for k, s in enumerate(cycle):
            for r in results_of(receipt_cases[s]["pairs"]):
                w = dict(r["witness"])
                if isinstance(w.get("t"), (int, float)):
                    w["t"] = (k * FRAMES + w["t"] * (FRAMES - 1)) / (total - 1)
                results.append(dict(pair=r["pair"], status=r["status"], witness=w, stage=s))
        weak = [r for r in data["power"] if r["batteryCondition"] == "weak" and r["stage"] in cycle]
        governing = min(weak, key=lambda r: r["marginV"])["case"] if weak else None
        measure = [f"Stage {k + 1}/{len(cycle)} · " + stage_text(s, i, FRAMES) for k, s in enumerate(cycle) for i in range(FRAMES)]
        status = "pass" if all(receipt_cases[s]["status"] == "pass" for s in cycle) else "fail"
        gaps = [gap_of(receipt_cases[s]["pairs"]) for s in cycle]
        gaps = [float(g) for g in gaps if g is not None]
        cases.insert(0, dict(id=cc["label"], key=cc["key"], stage="operating cycle", positions=[[0, 0]] * total, frames={},
                             series=series, rig=rig, removed=[], status=status, gap=f"{min(gaps):.2f}" if gaps else None,
                             results=results, duty=cc.get("duty") or governing, measure=measure,
                             basis=cc["basis"] + " Stages in order: " + ", ".join(cycle) + ". Each stage starts from the installed pose, as the "
                                   "layout check prescribes it, so the playback steps between stages rather than blending them."))

    # The displaced control: the same case with the displaced member offset, which the check must reject.
    control = receipt.get("control")
    if control and config.get("controlCase", True):
        cid = control["case"]
        frame_map = {n: list(seq) for n, seq in case_frames[cid].items()}
        off = control["offsetMm"]
        frame_map[control["displaced"]] = [tidy(m[:3] + [m[3] + off[0]] + m[4:7] + [m[7] + off[1]] + m[8:11] + [m[11] + off[2]])
                                           for m in frame_map[control["displaced"]]]
        series, rig = series_of("control", frame_map)
        w = control["witness"]
        cases.append(dict(id=f"control · {control['displaced']} displaced {off} mm (expected fail)", key="package-displacement-control",
                          stage="control", positions=[[0, 0]] * FRAMES, frames={}, series=series, rig=rig, removed=[],
                          status=w["status"], gap=None, duty=duty_of.get(cid),
                          results=[dict(pair=w["pair"], status=w["status"], witness=w["witness"])],
                          measure=[f"Displaced control of {cid} · {round(100 * i / (FRAMES - 1))}%" for i in range(FRAMES)],
                          basis=f"Known failing control: {control['displaced']} is offset by {off} mm in {cid}. The same check rejects it "
                                f"({' / '.join(w['pair'])}, {w['witness'].get('volumeMm3', 0):.1f} mm³ overlap)."))

    power = []
    load_members = data.get("loadMembers", {})
    for row in data["power"]:
        power.append(dict(case=row["case"], stage=row["stage"], batteryCondition=row["batteryCondition"], duty=row["duty"],
                          openCircuitV=row["openCircuit"][0], resistance=row["resistance"][1], requiredMinV=row["requiredMinV"],
                          loadedBusV=row["loadedBusV"], batterySideA=row["batterySideA"], marginV=row["marginV"], status=row["status"],
                          lines=[dict(name=k, amps=v, members=load_members.get(k, [])) for k, v in sorted(row["loads"].items())]))
    power.sort(key=lambda e: (e["batteryCondition"] != "weak", e["marginV"]))

    robot = [n for n in names if n not in fixtures]
    floor_points = [p for n in names for p in bodies[n]["v"]]
    pad = 750.0
    floor = dict(min=[math.floor((min(p[0] for p in floor_points) - pad) / 250) * 250, math.floor((min(p[1] for p in floor_points) - pad) / 250) * 250],
                 max=[math.ceil((max(p[0] for p in floor_points) + pad) / 250) * 250, math.ceil((max(p[1] for p in floor_points) + pad) / 250) * 250],
                 z=0.0, step=250)

    premises = [f"Premise {p['id']} ({p['phase']}): {p['scenario']} · {p['status']} at {p['value'] if isinstance(p['value'], str) else format(p['value'], 'g')} {p['unit']}" for p in receipt.get("premises", [])]
    narrative = receipt.get("narrativeReview") or data.get("narrativeReview")
    scene = dict(
        schema="agent-frc/preliminary-review-scene@1",
        season=config["season"], release=config["id"], issue=config["title"], status=config["status"],
        step=receipt["step"]["sha256"], receipt=digest(project_file(package["receipt"]).read_bytes()),
        motion=receipt["motion"]["sha256"], view=view_pin["sha256"],
        bodies=bodies, palette=palette, floor=floor,
        mass=[dict(id=r["id"], kg=r["kg"], members=r["members"]) for r in budgets["masses"]],
        details=[dict(name=item["name"], kg=item["kg"], members=item.get("members", []), running=True) for item in config.get("runningItems", [])]
        or [dict(name="Running payload", kg=budgets["runningPayloadKg"], members=[], running=True)],
        runningBasis=budgets.get("runningPayloadBasis"),
        power=power, inspection=receipt["budgets"]["inspectionKg"], running=receipt["budgets"]["runningKg"],
        limits=dict(inspectionKg=requirements["inspectionLimitKg"], operatingMinV=requirements.get("operatingMinV")),
        cases=cases, static=[], unresolved=[],
        narrow=sum(receipt_cases[c["id"]]["counts"].get("broadPhase", 0) for c in cases_in[:1]),
        required=[[role, members] for role, members in data.get("required", {}).items()],
        narrativeReview=dict(source=narrative["source"], objectives=narrative["objectives"]) if narrative else None,
        support=config.get("support", {}), fixtureMeshes={}, fixtures=fixtures,
        notes=config.get("notes", []) + premises, focus=config.get("focus", ""),
        validationText=None, defaultCase=config["defaultCase"],
        links=config.get("links", []),
    )
    scene = scrub(scene, rules)
    if config["defaultCase"] not in [c["key"] for c in cases]:
        fail("default case is not in the release")
    for rule in config.get("forbid", []):
        text = json.dumps(scene, ensure_ascii=False)
        if re.search(rule, text):
            fail("forbidden content remains in the scene: " + rule)
    raw = json.dumps(scene, allow_nan=False, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0, compresslevel=9) as stream:
        stream.write(raw)
    packed = buffer.getvalue()

    copies = {}
    for target, source in config.get("copy", {}).items():
        copies[target] = project_file(source).read_bytes()
    release = dict(
        id=config["id"], title=config["title"], defaultCase=config["defaultCase"],
        sceneSha256=digest(packed), sceneJsonSha256=digest(raw),
        geometry=receipt["step"]["sha256"],
        cases=[c["key"] for c in cases], scope=config["scope"],
        fixtureRepresentation=config.get("fixtureRepresentation"),
        disposition=config.get("disposition"),
        issue=receipt["issue"], receiptStatus=receipt["status"],
        inputs=dict(config=pin(config_name), layout=pin(package["layout"]), receipt=pin(package["receipt"]),
                    budgets=pin(package["budgets"]), view=view_pin, step=receipt["step"], motion=receipt["motion"],
                    **{k: pin(v) for k, v in package.get("evidence", {}).items()}),
        copied={k: dict(source=v, sha256=digest(copies[k])) for k, v in config.get("copy", {}).items()},
        generator=pin("scripts/preliminary_review.py"),
    )
    release.update(config.get("releaseExtra", {}))
    return config, packed, release, copies, scene


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config")
    parser.add_argument("--check", action="store_true", help="verify the committed release instead of writing it")
    args = parser.parse_args()
    config, packed, release, copies, scene = build(args.config)
    out = (ROOT / config["output"]).resolve()
    if not out.is_relative_to(ROOT):
        fail("output leaves the project")
    files = {"scene.json.gz": packed,
             "release.json": (json.dumps(release, indent=2, ensure_ascii=False) + "\n").encode("utf-8"), **copies}
    if args.check:
        stale = [n for n, b in files.items() if not (out / n).is_file() or (out / n).read_bytes() != b]
        if stale:
            fail("stale release files: " + ", ".join(stale))
        print(f"Verified release {config['id']}: {len(scene['bodies'])} bodies, {len(scene['cases'])} cases")
        return
    out.mkdir(parents=True, exist_ok=True)
    for n, b in files.items():
        (out / n).write_bytes(b)
    print(f"Wrote release {config['id']}: {len(scene['bodies'])} bodies, {len(scene['cases'])} cases, scene {len(packed):,} bytes")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
