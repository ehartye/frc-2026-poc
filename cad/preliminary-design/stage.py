"""Append a checked work-in-progress release, or audit the index before deploying the season site."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import zlib


def read(path):
    return json.loads(path.read_bytes())


def pinned(root, row):
    path = (root / row["file"]).resolve()
    if not path.is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
        raise ValueError("Missing or changed release input: " + row["file"])
    return path


@contextmanager
def update_index(site):
    # The OS releases this advisory lock on process exit, even after a crash.
    key = hashlib.sha256(os.path.normcase(str(site.resolve())).encode()).hexdigest()
    lock = Path(tempfile.gettempdir()) / ("preliminary-review-" + key + ".lock")
    with lock.open("a+b") as handle:
        if os.name == "nt":
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def index(site, recovering=None):
    listing = site / "releases.json"
    record = read(listing) if listing.exists() else {"releases": []}
    names = record["releases"]
    if len(names) != len(set(names)) or (names and record.get("current") not in names):
        raise ValueError("Release index has a duplicate ID or an unknown current release")
    legacy = record.get("legacy", [])
    if names[:len(legacy)] != legacy:
        raise ValueError("Legacy releases must be the earliest entries in the release index, in order")
    dirs = {p.name for p in (site / "releases").iterdir() if p.is_dir() and not p.name.startswith(".")}
    if set(names) - dirs or dirs - set(names) - {recovering}:
        raise ValueError("Release index and immutable directories disagree. Reconcile every release before publishing.")
    for name in names:
        release = site / "releases" / name
        view = read(release / "receipt.json")["view"]
        if hashlib.sha256((release / "index.html").read_bytes()).hexdigest() != view["sha256"]:
            raise ValueError("Indexed view differs from receipt: " + name)
        if view.get("geometry") and not geometry_matches(release, view):
            raise ValueError("Indexed geometry differs from receipt: " + name)
        # A release deployed before release records existed stays as published; list it once under "legacy".
        if name not in record.get("legacy", []) or (release / "release.json").exists():
            check_release(release)
    return record


LABEL = "Work-in-progress preliminary design"
RESERVED = {"index.html", "receipt.json", "motion.json", "release.json", "budgets.json", "limits.json"}
TRIAL = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}\.json")
GEOMETRY = re.compile(r"[a-z0-9][a-z0-9._-]{0,110}\.geometry\.json\.gz")


def geometry_matches(release, view):
    """The page, the receipt and the served compressed geometry name and pin the same content."""
    pin = view.get("geometry") or {}
    name = pin.get("file") or ""
    path = release / Path(name).name
    if not GEOMETRY.fullmatch(Path(name).name) or Path(name).name in RESERVED or not path.is_file():
        return False
    page = (release / "index.html").read_text(encoding="utf-8")
    try:
        shown = json.loads(page.split('id="data">', 1)[1].split("</script>", 1)[0])["geometry"]
    except (IndexError, KeyError, ValueError):
        return False
    served = path.read_bytes()
    if (shown.get("file") != path.name or shown.get("contentSha256") != pin.get("contentSha256")
            or hashlib.sha256(served).hexdigest() != pin.get("sha256")):
        return False
    try:
        stream = zlib.decompressobj(16 + zlib.MAX_WBITS)
        content = stream.decompress(served, shown["bytes"] + 1)
    except (zlib.error, KeyError, TypeError):
        return False
    return (len(content) == shown["bytes"] and stream.eof
            and hashlib.sha256(content).hexdigest() == pin["contentSha256"])
KINDS = {"operating-case", "field-interaction-trial"}
OUTCOMES = {"acquired", "delivered", "scored", "climb-held"}


FIELD = re.compile(r"field/[a-z0-9][a-z0-9._-]{0,110}\.html")
FIELD_PLAYER_POLICY = ("default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; "
                       "font-src data:; media-src data: blob:; base-uri 'none'; form-action 'none'")
RAW_TEXT = {"script", "style", "textarea", "title", "xmp", "iframe", "noembed", "noframes", "noscript", "plaintext"}
BANNED_TAGS = {"iframe", "frame", "frameset", "object", "embed", "portal", "base", "link", "applet", "form", "area"}
RESOURCE_ATTRS = {"src", "srcset", "poster", "background", "data", "action", "formaction", "ping", "xlink:href"}
HEAD = re.compile(r'(?:<!doctype html>[ \t\n\r\f]*)?(?:<html(?: lang="[A-Za-z-]{1,16}")?>[ \t\n\r\f]*)?<head>[ \t\n\r\f]*', re.I)
URL_SPACE = "".join(map(chr, range(33)))  # a browser strips C0 controls and spaces around a URL
NETWORK = re.compile(r"\b(?:fetch|importScripts|sendBeacon)\s*\(|\b(?:XMLHttpRequest|WebSocket|EventSource|RTCPeerConnection)\b")


def start_tags(html):
    """Mirror the gate's tokenizer: start tags and attributes as a browser reads them."""
    tags, i, n = [], 0, len(html)
    space = lambda c: c in " \t\n\f\r"
    letter = lambda c: c.isascii() and c.isalpha()
    while i < n:
        if html[i] != "<":
            i += 1
            continue
        if html.startswith("<!--", i):
            e = html.find("-->", i + 4)
            i = n if e < 0 else e + 3
            continue
        nxt = html[i + 1] if i + 1 < n else ""
        if nxt in ("!", "?", "/"):
            e = html.find(">", i + 1)
            i = n if e < 0 else e + 1
            continue
        if not letter(nxt):
            i += 1
            continue
        j = i + 1
        while j < n and not space(html[j]) and html[j] not in "/>":
            j += 1
        name, attrs = html[i + 1:j].lower(), []
        while j < n and html[j] != ">":
            if space(html[j]) or html[j] == "/":
                j += 1
                continue
            k = j + 1
            while k < n and not space(html[k]) and html[k] not in "/>=":
                k += 1
            attr = html[j:k].lower()
            while k < n and space(html[k]):
                k += 1
            value = ""
            if k < n and html[k] == "=":
                k += 1
                while k < n and space(html[k]):
                    k += 1
                if k < n and html[k] in "\"'":
                    e = html.find(html[k], k + 1)
                    value, k = (html[k + 1:], n) if e < 0 else (html[k + 1:e], e + 1)
                else:
                    e = k
                    while e < n and not space(html[e]) and html[e] != ">":
                        e += 1
                    value, k = html[k:e], e
            attrs.append((attr, value))
            j = k
        tags.append((name, attrs))
        i = j + 1
        if name in RAW_TEXT:
            close = html.lower().find("</" + name, i)
            i = n if close < 0 else close
    return tags


def self_contained(html):
    """Mirror the gate: the plugin's exact policy first in <head>, and no external resource, link or network API."""
    html = html.replace("\r\n", "\n")
    html = html[1:] if html.startswith("﻿") else html
    head = HEAD.match(html)
    meta = '<meta http-equiv="Content-Security-Policy" content="' + FIELD_PLAYER_POLICY + '">'
    if not head or not html.startswith(meta, head.end()):
        return "make " + meta + " the first element in <head>"
    policies = 0
    for name, attrs in start_tags(html):
        if name in BANNED_TAGS:
            return "an embedded, linked or submitted resource (<" + name + ">)"
        for attr, value in attrs:
            v = value.strip(URL_SPACE).lower()
            policies += attr == "http-equiv"
            if name == "script" and attr == "src":
                return "an external script"
            if attr == "href" and not v.startswith("#"):
                return "a link away from the page"
            if attr in RESOURCE_ATTRS and not re.match(r"(?:data:|blob:|#)", v):
                return "a resource URL (" + attr + ")"
    if policies != 1:
        return "declare exactly one http-equiv element, the policy"
    if NETWORK.search(html):
        return "a network API"
    if LABEL not in html:
        return 'label the page "' + LABEL + '"'
    return None


def view_data(page):
    """The checked player's embedded data; the plugin gate separately proves the page is its own player."""
    if 'id="data">' not in page:
        return {}
    return json.loads(page.split('id="data">', 1)[1].split("</script>", 1)[0])


def player_target(href):
    """The served page a view link names: field/NAME.html, optionally after ./."""
    if not isinstance(href, str):
        return None
    name = href[2:] if href.startswith("./") else href
    return name if FIELD.fullmatch(name) else None


def check_release(release):
    """Mirror the plugin's preliminary release gate: physics receipt, digests and a mission-task case."""
    def fail(message):
        raise ValueError(message + ": " + release.name)
    if not (release / "release.json").is_file():
        fail("Release has no release record (release.json); stage it with this script")
    present = set()
    for p in release.iterdir():
        if p.name == "field" and p.is_dir() and not p.is_symlink():
            present |= {"field/" + q.name + ("/" if q.is_dir() else "") for q in p.iterdir()}
        else:
            present.add(p.name)
    if RESERVED - present:
        fail("Release is missing " + ", ".join(sorted(RESERVED - present)))
    record, receipt = read(release / "release.json"), read(release / "receipt.json")
    sha = lambda name: hashlib.sha256((release / name).read_bytes()).hexdigest()
    if (record.get("schema") != "agent-frc/preliminary-release@1" or record.get("release") != release.name
            or record.get("label") != LABEL or record.get("issue") != receipt.get("issue")):
        fail("Release record names a different schema, release, label or issue")
    pins = [(record.get("receipt") or {}, "receipt.json"), (record.get("view") or {}, "index.html"),
            (record.get("scene") or {}, "motion.json")]
    if (any(pin.get("file") != name or pin.get("sha256") != sha(name) for pin, name in pins)
            or (receipt.get("view") or {}).get("sha256") != sha("index.html") or not receipt["view"].get("verified")
            or (receipt.get("motion") or {}).get("sha256") != sha("motion.json")
            or record["scene"].get("stepSha256") != (receipt.get("step") or {}).get("sha256")):
        fail("Published receipt, view or scene differs from its pins")
    budgets = receipt.get("budgets") or {}
    if ((budgets.get("source") or {}).get("sha256") != sha("budgets.json")
            or (budgets.get("limits") or {}).get("sha256") != sha("limits.json")):
        fail("Published budgets differ from the receipt")
    witness = (receipt.get("control") or {}).get("witness") or {}
    cases, power = receipt.get("cases") or [], budgets.get("electricalCases") or []
    if (receipt.get("status") != "layout-checked" or record.get("status") != "layout-checked" or receipt.get("partial")
            or receipt.get("missingInputs") or receipt.get("reopen") or not cases
            or any(c.get("status") != "pass" for c in cases) or witness.get("status") != "fail"
            or budgets.get("massStatus") != "pass" or not power or any(r.get("status") != "pass" for r in power)):
        fail("A preliminary release needs a layout-checked receipt: clearance, mass and voltage pass, "
             "the displaced control is rejected and no inputs are missing")
    objectives = (receipt.get("narrativeReview") or {}).get("objectives") or []
    represented = {o.get("objective") for o in objectives if o.get("disposition") == "represented"}
    passed = {c.get("case") for c in cases if c.get("status") == "pass"}
    missions, trials = record.get("missionCases") or [], set()
    players = record.get("fieldPlayers") or []
    files = [q.get("file") for q in players if isinstance(q, dict)]
    if len(files) != len(players) or len(set(files)) != len(files) or not all(FIELD.fullmatch(f or "") for f in files):
        fail("Each field player needs a unique field/NAME.html file")
    rows = view_data((release / "index.html").read_text(encoding="utf-8")).get("fieldInteractions") or []
    linked = {}
    for row in rows:
        name = player_target(row.get("href"))
        if name not in files:
            fail("A field interaction must link a listed field player (" + str(row.get("href")) + ")")
        linked.setdefault(name, []).append(row)
    stage_pins = {(s.get("evidence") or {}).get("sha256") for st in (receipt.get("stages") or {}).values()
                  for s in (st.get("transportedBy") or {}).values()}
    for q in players:
        t, name = q.get("trial") or {}, q["file"]
        trial = t.get("file") or ""
        if not (release / name).is_file() or sha(name) != q.get("sha256"):
            fail("Published field player differs from its pin: " + name)
        if not TRIAL.fullmatch(trial) or trial in RESERVED or not (release / trial).is_file() or sha(trial) != t.get("sha256"):
            fail("Publish the pinned trial for field player " + name)
        trials.add(trial)
        if not isinstance(q.get("objective"), str) or not q["objective"].strip() or q["objective"] not in represented:
            fail("Field player " + name + " must show a represented narrative objective")
        links = linked.get(name)
        if not links:
            fail("Each listed field player must be linked from the checked view: " + name)
        if any(r.get("objective") != q["objective"] for r in links):
            fail("Field player " + name + " objective differs from the checked view")
        if not (any(isinstance(r.get("evidence"), dict) and r["evidence"].get("sha256") == t["sha256"] for r in links)
                or t["sha256"] in stage_pins):
            fail("The trial for field player " + name + " is not one the receipt pins")
        why = self_contained((release / name).read_text(encoding="utf-8"))
        if why:
            fail("Field player " + name + " is not self-contained: " + why)
    if not missions:
        fail("Declare a mission-task case in missions.json")
    for m in missions:
        stage_ = (receipt.get("stages") or {}).get(m.get("case")) or {}
        ok = (m.get("kind") in KINDS and m.get("accomplishes") in OUTCOMES and m.get("objective") in represented
              and m.get("case") in passed and stage_.get("purpose") == "operating"
              and m.get("case") in (receipt.get("cycle") or []))
        if m.get("kind") == "field-interaction-trial" and "player" in m:
            q = next((q for q in players if q.get("file") == m["player"]), None)
            ok = ok and "trial" not in m and q is not None and q.get("objective") == m.get("objective")
            if ok:
                trial = read(release / q["trial"]["file"])
                ok = (trial.get("case") if "case" in trial else (trial.get("transport") or {}).get("case")) == m.get("case")
        elif m.get("kind") == "field-interaction-trial":
            t = m.get("trial") or {}
            name = t.get("file") or ""
            ok = (ok and bool(TRIAL.fullmatch(name)) and name not in RESERVED and (release / name).is_file()
                  and sha(name) == t.get("sha256") and any((s.get("evidence") or {}).get("sha256") == t.get("sha256")
                                                          for s in (stage_.get("transportedBy") or {}).values()))
            trials.add(name)
        elif "trial" in m:
            ok = False
        if not ok:
            fail("Mission case " + str(m.get("case")) + " must be a passing operating case in the checked cycle, "
                 "with a known accomplishment, for a represented narrative objective")
    geometry = set()
    if (receipt.get("view") or {}).get("geometry"):
        if not geometry_matches(release, receipt["view"]):
            fail("Published geometry differs from the page and receipt")
        geometry.add(Path(receipt["view"]["geometry"]["file"]).name)
    extra = present - RESERVED - trials - geometry - set(files)
    if extra:
        fail("Unrecognized release files " + ", ".join(sorted(extra)))


def stage(season, inputs, release):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", release):
        raise ValueError("Use a lowercase release ID with letters, digits and hyphens")
    site = season / "docs/preliminary-design"
    releases = site / "releases"
    releases.mkdir(parents=True, exist_ok=True)
    destination = releases / release
    inputs = inputs.resolve()
    plan = read(inputs / "layout.json")
    receipt_file = inputs / "receipt.json"
    result = read(receipt_file)
    if result["planSha256"] != hashlib.sha256((inputs / "layout.json").read_bytes()).hexdigest():
        raise ValueError("Review receipt belongs to a different layout")
    if not result.get("view", {}).get("verified"):
        raise ValueError("Review needs a verified display artifact")
    viewer = pinned(inputs, result["view"])
    if viewer != (inputs / plan["view"]).resolve():
        raise ValueError("The checked view differs from the layout's selected view")
    if result.get("status") != "layout-checked" or result.get("missingInputs"):
        raise ValueError("A preliminary release needs a layout-checked receipt with no missing inputs")
    if not plan.get("budgets"):
        raise ValueError("A preliminary release needs the checked weight and loaded-voltage budgets")
    missions = read(inputs / "missions.json")["missionCases"] if (inputs / "missions.json").exists() else []
    if not missions:
        raise ValueError("Declare a passing mission-task case for a represented objective in missions.json")
    with update_index(site), tempfile.TemporaryDirectory(dir=site.parent, prefix=".stage-") as tmp:
        record = index(site, recovering=release)
        if release in record["releases"]:
            raise FileExistsError("Release already exists: " + release)
        files = {"index.html": viewer, "receipt.json": receipt_file, "motion.json": pinned(inputs, plan["motion"])}
        if result["view"].get("geometry"):
            try:
                geometry = pinned(inputs, result["view"]["geometry"])
            except ValueError as error:
                # Another zlib can compress the same content differently; the receipt pins the bytes it checked.
                raise ValueError(str(error) + ". Regenerate it with --write-view and save that run's receipt") from None
            if geometry.parent != viewer.parent or not GEOMETRY.fullmatch(geometry.name):
                raise ValueError("Keep the compressed geometry beside its view, named VIEW.geometry.json.gz")
            files[geometry.name] = geometry
        ledger = pinned(inputs, plan["budgets"])
        files.update({"budgets.json": ledger, "limits.json": pinned(inputs, read(ledger)["requirements"])})
        players = []
        for row in view_data(viewer.read_text(encoding="utf-8")).get("fieldInteractions") or []:
            name = player_target(row.get("href"))
            if not name or not FIELD.fullmatch(name):
                raise ValueError("Link each field interaction to a season player at field/NAME.html beside the view: "
                                 + str(row.get("href")))
            if not isinstance(row.get("evidence"), dict):
                raise ValueError("Pin the trial evidence for field player " + name + " in the layout")
            page, trial = viewer.parent / name, pinned(inputs, row["evidence"])
            if not page.is_file():
                raise ValueError("Missing field player beside the view: " + name)
            if not TRIAL.fullmatch(trial.name) or trial.name in RESERVED or files.get(trial.name, trial) != trial:
                raise ValueError("Name each trial file in lowercase JSON, distinct from the release files: " + trial.name)
            files[name], files[trial.name] = page, trial
            if all(p["file"] != name for p in players):
                players.append(dict(file=name, sha256=hashlib.sha256(page.read_bytes()).hexdigest(),
                                    trial=dict(file=trial.name, sha256=row["evidence"]["sha256"]),
                                    objective=row.get("objective")))
        published = []
        for mission in missions:
            mission = dict(mission)
            if mission.get("trial"):
                trial = pinned(inputs, mission["trial"])
                if not TRIAL.fullmatch(trial.name) or trial.name in RESERVED:
                    raise ValueError("Name a trial file in lowercase JSON that differs from the release files: " + trial.name)
                if files.get(trial.name, trial) != trial:
                    raise ValueError("Two different trial files share a name: " + trial.name)
                files[trial.name] = trial
                mission["trial"] = dict(file=trial.name, sha256=mission["trial"]["sha256"])
            published.append(mission)
        digest = lambda name: hashlib.sha256(files[name].read_bytes()).hexdigest()
        files["release.json"] = Path(tmp) / "release.json"
        files["release.json"].write_text(json.dumps(dict(
            schema="agent-frc/preliminary-release@1", release=release, issue=result["issue"],
            label="Work-in-progress preliminary design", status=result["status"],
            receipt=dict(file="receipt.json", sha256=digest("receipt.json")),
            view=dict(file="index.html", sha256=digest("index.html")),
            scene=dict(file="motion.json", sha256=digest("motion.json"), stepSha256=result["step"]["sha256"]),
            missionCases=published, **(dict(fieldPlayers=players) if players else {})), indent=2) + "\n", encoding="utf-8")
        staged = Path(tmp) / release
        staged.mkdir()
        for name, src in files.items():
            (staged / name).parent.mkdir(exist_ok=True)
            shutil.copyfile(src, staged / name)
        check_release(staged)
        if destination.exists():
            existing = {str(p.relative_to(destination)).replace(os.sep, "/") for p in destination.rglob("*") if p.is_file()}
            if existing != set(files) or any(
                    (destination / n).read_bytes() != (staged / n).read_bytes() for n in files):
                raise ValueError("Existing release bytes differ: " + release)
        else:
            staged.rename(destination)
        record["current"] = release
        record["releases"].append(release)
        new_index = Path(tmp) / "releases.json"
        new_index.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        new_index.replace(site / "releases.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("release", nargs="?")
    mode.add_argument("--check-index", action="store_true")
    args = parser.parse_args()
    base = Path(__file__).resolve().parent
    if args.check_index:
        index(base.parents[1] / "docs/preliminary-design")
    else:
        stage(base.parents[1], base / "releases" / args.release, args.release)
