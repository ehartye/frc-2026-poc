"""Publish a checked preliminary design release into the season site, set a release's design status, copy a release's
inputs to a new release folder, or remove a release.

A new release takes a version as its ID, MAJOR.MINOR. The major number is the architecture and carries its name, given
once with --design-name. The minor number counts the effective baselines of that architecture. A draft is a publish
of an in-progress version and takes no number: staging the same ID again counts it.

This script only copies files and edits the release index. The project's Design publication workflow decides
whether the result may merge: it reruns the layout check from the committed inputs and compares the receipt.
Withdrawing a release is a status change: the index keeps the reason and the last commit that held its published
files, and the files leave the site."""
import argparse
import datetime
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zlib

STATUSES = ("in-progress", "effective", "superseded", "withdrawn")
SCENE = "review-scene.json.gz"
FIELD = re.compile(r"field/[a-z0-9][a-z0-9._-]{0,110}\.html")
VERSION = re.compile(r"([1-9][0-9]{0,3})\.(0|[1-9][0-9]{0,3})")
# An ID issued before versions: lowercase letters, digits and hyphens. It keeps working and carries no design name.
EARLIER_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
PER_RELEASE = ("designStatus", "revision", "accepted", "reason", "lastCommit")


def read(path):
    return json.loads(path.read_bytes())


def inside(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("Missing release input: " + str(name))
    return path


def replace_index(temporary, site):
    """Rename the complete new index over the old one, so a reader finds one or the other.

    Windows refuses the rename while a reader holds the index open; the reader finishes shortly."""
    for attempt in range(500):
        try:
            Path(temporary).replace(site / "releases.json")
            return
        except PermissionError:
            if attempt == 499:
                raise
            time.sleep(0.02)


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


def load_index(site):
    listing = site / "releases.json"
    record = read(listing) if listing.exists() else {"releases": []}
    names = record["releases"]
    if len(names) != len(set(names)):
        raise ValueError("The release index lists a release twice")
    return record


def status_of(record, release):
    """A listed release without a designStatus entry is in progress."""
    return (record.get("designStatus") or {}).get(release, "in-progress")


def version_of(release):
    """(major, minor) of a version ID such as 1.0, else None."""
    match = VERSION.fullmatch(release or "")
    return (int(match[1]), int(match[2])) if match else None


def major_of(release):
    version = version_of(release)
    return version[0] if version else None


def design_name(record, major):
    """The name of the architecture a major number stands for, from the index."""
    name = ((record.get("designs") or {}).get(str(major)) or {}).get("name")
    return name if isinstance(name, str) and name.strip() else None


def title_of(record, release):
    """A version reads NAME MAJOR.MINOR; an earlier ID reads as the ID."""
    name = design_name(record, major_of(release)) if version_of(release) else None
    return name + " " + release if name else release


def described(record, release):
    return ("preliminary design " if version_of(release) else "preliminary release ") + title_of(record, release)


def state_of(record, release):
    """What a reader sees after the name: the draft count while in progress, then the status."""
    status = status_of(record, release)
    return ("draft " + str(revision_of(record, release)) + ", in progress") if status == "in-progress" else status


def in_progress_of(record, major, besides=None):
    """The in-progress version of an architecture, if it has one."""
    return next((r for r in record["releases"] if r != besides and major_of(r) == major and status_of(record, r) == "in-progress"), None)


def place_version(record, release, name):
    """Name the architecture of a version being staged and check where the version falls among those listed.

    Returns notes for the person staging. It refuses only what the index cannot hold: an unnamed architecture, a second
    name for one architecture, a second in-progress version of one architecture and a version behind one already listed."""
    major, minor = version_of(release)
    known, notes = design_name(record, major), []
    if name is not None:
        name = " ".join(name.split())
        if not 0 < len(name) <= 60:
            raise ValueError("Give the design a short name in words with --design-name, 60 characters at most")
    if known is None:
        if not name:
            raise ValueError("Name design " + str(major) + " with --design-name \"NAME\": a short name in words for the architecture. "
                             "Give it once, the first time a major number is staged; every version of that architecture keeps it")
        other = next((m for m in (record.get("designs") or {}) if (design_name(record, m) or "").lower() == name.lower()), None)
        if other:
            notes.append("design " + other + " is also named \"" + name + "\". A different architecture takes its own name.")
        record.setdefault("designs", {})[str(major)] = dict(name=name)
    elif name and name != known:
        raise ValueError("Design " + str(major) + " is named \"" + known + "\". A name stays with its architecture: a different architecture "
                         "takes the next major number with its own name. Correct a spelling by editing designs in releases.json in a pull request")
    if release in record["releases"]:
        return notes
    drafting = in_progress_of(record, major)
    if drafting:
        raise ValueError(title_of(record, drafting) + " is already in progress (draft " + str(revision_of(record, drafting)) + "). Revise it in "
                         "place: stage " + drafting + " again. A draft takes no number; a new number is for a new effective baseline or a new architecture")
    minors = [version_of(r)[1] for r in record["releases"] if major_of(r) == major]
    majors = sorted({major_of(r) for r in record["releases"] if version_of(r)})
    if minors:
        following = str(major) + "." + str(max(minors) + 1)
        if minor < max(minors):
            raise ValueError("Version " + release + " comes before " + str(major) + "." + str(max(minors)) + ", which is already listed. The next version of "
                             + design_name(record, major) + " is " + following)
        if release != following:
            notes.append("the version after " + str(major) + "." + str(max(minors)) + " is " + following + "; " + release + " skips a number.")
        return notes
    if minor:
        notes.append("the first version of an architecture is " + str(major) + ".0; everything before its first effective baseline is a draft of " + str(major) + ".0.")
    if major != (majors[-1] + 1 if majors else 1):
        notes.append("the next architecture " + ("after design " + str(majors[-1]) + " is " + str(majors[-1] + 1) + ".0" if majors else "is 1.0") + "; " + release + " skips a number.")
    for earlier in majors:
        left = in_progress_of(record, earlier)
        if left:
            notes.append(title_of(record, left) + " is still in progress. If the team has left that architecture, mark it superseded or withdraw it.")
    return notes


def current_for(record):
    """The release the stable URL opens: the effective one, else the newest in-progress one, else the newest not withdrawn."""
    names = record["releases"]
    return (next((n for n in names if status_of(record, n) == "effective"), None)
            or next((n for n in reversed(names) if status_of(record, n) == "in-progress"), None)
            or next((n for n in reversed(names) if status_of(record, n) != "withdrawn"), None)
            or (names[-1] if names else None))


def save_index(record, site):
    record["current"] = current_for(record)
    if record["current"] is None:
        del record["current"]
    with tempfile.NamedTemporaryFile("w", dir=site, delete=False, encoding="utf-8", suffix=".json") as out:
        out.write(json.dumps(record, indent=2) + "\n")
    replace_index(out.name, site)


def project_root(season, inputs, view):
    """The folder a release's pins are written from: the season repository when its view names the release folder
    from there, else the release folder itself, for a package that was checked in its own folder."""
    season, inputs = season.resolve(), inputs.resolve()
    if isinstance(view, str) and view and (season / view).resolve().parent == inputs != season:
        return season
    return inputs


def checked_id(release):
    if not version_of(release) and not EARLIER_ID.fullmatch(release or ""):
        raise ValueError("Use a version as the release ID: MAJOR.MINOR, such as 1.0")
    return release


def stage(season, inputs, release, design=None):
    """Copy one release's checked files into the site and list it in the index as in progress.

    An in-progress release is revised in place: staging its ID again replaces its published files and counts a
    draft in the index, under `revision`. A release stops changing when it is marked effective, and stays so afterwards."""
    checked_id(release)
    if design is not None and not version_of(release):
        raise ValueError("--design-name names the architecture of a version ID, MAJOR.MINOR. Release " + release + " keeps its earlier ID and has no name")
    site = season / "docs/preliminary-design"
    inputs = inputs.resolve()
    plan_file = inside(inputs, "layout.json")
    plan, result = read(plan_file), read(inside(inputs, "receipt.json"))
    if result.get("planSha256") != hashlib.sha256(plan_file.read_bytes()).hexdigest():
        raise ValueError("The receipt belongs to a different layout. Rerun the preliminary check and save its receipt")
    if result.get("status") != "layout-checked" or result.get("partial") or result.get("physicsOnly"):
        raise ValueError("A preliminary release needs the layout-checked receipt of a full check")
    if not plan.get("view") or not plan.get("budgets"):
        raise ValueError("A preliminary release needs the review view and the checked weight and loaded-voltage budgets")
    missions = read(inputs / "missions.json").get("missionCases") if (inputs / "missions.json").exists() else None
    if not missions:
        raise ValueError("Declare a passing mission-task case for a represented objective in missions.json")
    root = project_root(season, inputs, plan["view"])
    viewer = inside(root, plan["view"])
    if viewer.parent != inputs:
        raise ValueError("Keep the review view in the release folder beside its layout plan")
    scene_file = viewer.with_name(SCENE)
    if not scene_file.is_file():
        raise ValueError("Generate the review with --write-view: a release publishes the review page and its scene")
    ledger = inside(root, plan["budgets"]["file"])
    files = {"index.html": viewer, SCENE: scene_file, "receipt.json": inputs / "receipt.json",
             "motion.json": inside(root, plan["motion"]["file"]), "budgets.json": ledger,
             "limits.json": inside(root, read(ledger)["requirements"]["file"])}

    def publish(name, source):
        if files.setdefault(name, source) != source:
            raise ValueError("Two different release files share a name: " + name)

    # Field-interaction players the review links, each with the trial behind it.
    scene = json.loads(zlib.decompress(scene_file.read_bytes(), 16 + zlib.MAX_WBITS))
    players = []
    for row in scene.get("fieldInteractions") or []:
        href = row.get("href") if isinstance(row.get("href"), str) else ""
        name = href[2:] if href.startswith("./") else href
        if not FIELD.fullmatch(name) or not isinstance(row.get("evidence"), dict):
            raise ValueError("Link each field interaction to a page at field/NAME.html beside the view, with its trial evidence: " + str(href))
        trial = inside(root, row["evidence"]["file"])
        publish(name, inside(viewer.parent, name))
        publish(trial.name, trial)
        if all(p["file"] != name for p in players):
            players.append(dict(file=name, trial=dict(file=trial.name), objective=row.get("objective")))
    published = []
    for mission in missions:
        mission = dict(mission)
        if mission.get("trial"):
            trial = inside(root, mission["trial"]["file"])
            publish(trial.name, trial)
            mission["trial"] = dict(file=trial.name)
        published.append(mission)
    record = dict(schema="agent-frc/preliminary-release@1", release=release, issue=result["issue"], phase="preliminary-design",
                  # Where the project's CI finds the committed inputs to rerun the layout check.
                  check=dict(project=inputs.relative_to(season.resolve()).as_posix(), plan="layout.json"),
                  missionCases=published, **(dict(fieldPlayers=players) if players else {}))
    site.mkdir(parents=True, exist_ok=True)
    with update_index(site), tempfile.TemporaryDirectory(dir=site.parent, prefix=".stage-") as tmp:
        index = load_index(site)
        notes = place_version(index, release, design) if version_of(release) else []
        if release in index["releases"] and status_of(index, release) != "in-progress":
            if version_of(release):
                major, minor = version_of(release)
                raise ValueError(title_of(index, release) + " is " + status_of(index, release) + " and no longer changes. Work toward its next baseline is "
                                 + str(major) + "." + str(minor + 1) + ", staged as a draft; a different architecture takes the next major number with its own name")
            raise ValueError("Release " + release + " is " + status_of(index, release) + " and no longer changes. Only an in-progress "
                             "release is revised in place; publish the design that follows it under a new release ID")
        staged = Path(tmp) / release
        for name, source in files.items():
            (staged / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, staged / name)
        (staged / "release.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        destination = site / "releases" / release
        destination.parent.mkdir(parents=True, exist_ok=True)
        replaced = destination.exists()
        if replaced and tree(destination) == tree(staged) and release in index["releases"]:
            print(sentence(described(index, release)) + " is unchanged (draft " + str(revision_of(index, release)) + ")")
            return
        if replaced:
            # Git holds the earlier bytes; the pull request shows what changed.
            shutil.rmtree(destination)
        staged.rename(destination)
        # One version keeps one ID: an edit counts a draft here, in the field named revision, and adds no entry to the picker.
        number = revision_of(index, release) + 1 if replaced or release in index["releases"] else 1
        commit = head_commit(season)
        index.setdefault("revision", {})[release] = dict(number=number, date=datetime.date.today().isoformat(),
                                                         **(dict(commit=commit) if commit else {}))
        if release not in index["releases"]:
            index["releases"].append(release)
            index.setdefault("designStatus", {})[release] = "in-progress"
        save_index(index, site)
    print(("Revised " + described(index, release) + " in place" if number > 1 else "Staged " + described(index, release))
          + " (" + state_of(index, release) + ")")
    for note in notes:
        print("Note: " + note)


def sentence(text):
    return text[:1].upper() + text[1:]


def readiness_report(inputs, reporter=None, season=None, design=None):
    """Show the reviewer the plugin's effective-readiness report for a release's inputs. It never stops a status change."""
    where = [inputs.as_posix()]
    try:
        # A release checked from the repository root resolves its trial pins from there.
        if season is not None and project_root(season, inputs, read(inputs / "layout.json").get("view")) == season.resolve():
            where = [season.as_posix(), "--release", inputs.resolve().relative_to(season.resolve()).as_posix()]
    except (OSError, ValueError):
        pass
    if design:
        where += ["--design", design]
    command = "node PLUGIN/scripts/design.mjs effective-readiness " + " ".join('"' + w + '"' if " " in w else w for w in where)
    if reporter is None:
        print("Exit criteria for an effective preliminary design: run `" + command + "`, or pass --readiness "
              "PLUGIN/scripts/effective-readiness.mjs to print the report here.")
        return
    try:
        run = subprocess.run(["node", str(reporter), *where], capture_output=True)
        report = run.stdout.decode("utf-8", errors="replace").rstrip()
        if run.returncode != 0 or not report:
            raise ValueError("no report")
        # The console may not hold every character of the report; the status change is already made.
        encoding = sys.stdout.encoding or "utf-8"
        print(report.encode(encoding, errors="replace").decode(encoding))
    except Exception:
        print("Effective-readiness report unavailable for " + inputs.as_posix() + "; run `" + command + "`.")


def tree(folder):
    """Every file under a folder with its digest."""
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob("*") if p.is_file()}


def revision_of(index, release):
    """The draft count: how many times a release has been staged with changed files. One published before drafts were counted is at 1."""
    number = ((index.get("revision") or {}).get(release) or {}).get("number")
    return number if isinstance(number, int) and number > 0 else 1


def head_commit(folder):
    """The commit the checkout is at, which the revision was staged from. None outside Git or before a first commit."""
    try:
        run = subprocess.run(["git", "-C", str(folder), "rev-parse", "--verify", "-q", "HEAD"], capture_output=True, text=True)
        return run.stdout.strip() or None if run.returncode == 0 else None
    except OSError:
        return None


def last_commit(folder):
    """The last commit that changed a folder, where its files can still be read. None outside Git."""
    try:
        run = subprocess.run(["git", "-C", str(folder), "log", "-1", "--format=%H", "--", "."], capture_output=True, text=True)
        return run.stdout.strip() or None if run.returncode == 0 else None
    except OSError:
        return None


def set_status(site, release, status, reason=None):
    """Set a release's design status in the index. Making a release effective supersedes the one that was.

    Withdrawing needs a reason. The index keeps it with the last commit that held the release's published files,
    and the files leave the site. Git keeps them; the checked inputs under cad/ stay."""
    if status not in STATUSES:
        raise ValueError("Set a release to one of " + ", ".join(STATUSES))
    if status == "withdrawn" and not (reason or "").strip():
        raise ValueError("Give the reason for a withdrawal with --reason")
    if status != "withdrawn" and reason:
        raise ValueError("--reason applies to a withdrawal")
    with update_index(site):
        record = load_index(site)
        if release not in record["releases"]:
            raise ValueError("Unknown release: " + release)
        statuses = record.setdefault("designStatus", {})
        version = version_of(release)
        drafting = in_progress_of(record, version[0], besides=release) if version and status == "in-progress" else None
        if drafting:
            raise ValueError(title_of(record, drafting) + " is already in progress. One architecture has one in-progress version: revise " + drafting + " in place")
        if status == "effective":
            # The date it was accepted stays with the release, so it remains listed as a design once it is superseded.
            record.setdefault("accepted", {}).setdefault(release, datetime.date.today().isoformat())
            for other in record["releases"]:
                if other != release and status_of(record, other) == "effective":
                    statuses[other] = "superseded"
        for field in ("reason", "lastCommit"):
            # A release that returns from withdrawn is staged again; its withdrawal note goes with the old status.
            (record.get(field) or {}).pop(release, None)
            if field in record and not record[field]:
                del record[field]
        if status == "withdrawn":
            published = site / "releases" / release
            commit = last_commit(published) if published.is_dir() else None
            record.setdefault("reason", {})[release] = reason.strip()
            if commit:
                record.setdefault("lastCommit", {})[release] = commit
            if published.is_dir():
                shutil.rmtree(published)
        statuses[release] = status
        save_index(record, site)
    print(sentence(described(record, release)) + " is " + status + "; the site opens " + str(record["current"]))
    if version and status == "effective" and design_name(record, version[0]):
        latest = max(major_of(r) for r in record["releases"] if version_of(r))
        print("Work toward the next baseline of " + design_name(record, version[0]) + " is " + str(version[0]) + "." + str(version[1] + 1)
              + ", staged as drafts until it is accepted. A different architecture is " + str(latest + 1) + ".0 with its own name.")


def step_digest(site, release):
    """The SHA-256 of the STEP a published release was checked on, from its receipt."""
    try:
        digest = (read(site / "releases" / release / "receipt.json").get("step") or {}).get("sha256")
        return digest if isinstance(digest, str) and digest else None
    except (OSError, ValueError, AttributeError):
        return None


RECEIPT = "agent-frc/preliminary-layout-result@1"


def copy_inputs(season, base, old, new):
    """Copy a release's check inputs to a new release folder and write its pins for the new paths.

    A record pins a file by path and SHA-256, and a release checked from the repository root names its own folder in
    those paths. Each such pin is verified against the source, written with the new path and given the digest of the
    copied file. The STEP and every other file that is not a pinning record keep their bytes. The review page, scene
    and receipt are not copied: the layout check writes them for the new folder. A held receipt is copied unchanged."""
    source, target = base / "releases" / checked_id(old), base / "releases" / checked_id(new)
    if not (source / "layout.json").is_file():
        raise ValueError("No layout plan at " + (source / "layout.json").relative_to(season).as_posix())
    if target.exists():
        raise ValueError(target.relative_to(season).as_posix() + " already exists. Choose a new release ID, or remove that folder first")
    before, after = source.relative_to(season).as_posix() + "/", target.relative_to(season).as_posix() + "/"
    digest = lambda file: hashlib.sha256(file.read_bytes()).hexdigest()
    view = read(source / "layout.json").get("view")
    left = {"receipt.json", SCENE, Path(view).name if isinstance(view, str) else SCENE, "__pycache__"}
    done, rewritten = set(), []

    def repin(name):
        """Rewrite the pins in one copied record, after the records it pins."""
        if name in done or not name.endswith(".json"):
            return
        done.add(name)
        try:
            data = json.loads((target / name).read_bytes())
        except (OSError, ValueError):
            return
        if isinstance(data, dict) and data.get("schema") == RECEIPT:
            return
        was = json.dumps(data)

        def walk(node):
            if isinstance(node, dict):
                file, pinned = node.get("file"), node.get("sha256")
                if isinstance(file, str) and file.startswith(before):
                    inner = file[len(before):]
                    if isinstance(pinned, str) and (not (source / inner).is_file() or digest(source / inner) != pinned):
                        raise ValueError(before + name + " pins " + file + ", which is missing or differs from its pinned SHA-256. Resolve it in release "
                                         + old + " before copying")
                    repin(inner)
                    node["file"] = after + inner
                    if isinstance(pinned, str) and (target / inner).is_file():
                        node["sha256"] = digest(target / inner)
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(data)
        if isinstance(data, dict) and isinstance(data.get("view"), str) and data["view"].startswith(before):
            data["view"] = after + data["view"][len(before):]
        if json.dumps(data) != was:
            (target / name).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            rewritten.append(name)

    try:
        shutil.copytree(source, target, ignore=lambda folder, names: [n for n in names if Path(folder) == source and n in left or n == "__pycache__"])
        for file in sorted(target.rglob("*.json")):
            repin(file.relative_to(target).as_posix())
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise
    plan = after + "layout.json"
    print("Copied the inputs of release " + old + " to " + after.rstrip("/") + " and wrote " + str(len(rewritten)) + " pinning record"
          + ("" if len(rewritten) == 1 else "s") + " for the new paths. The STEP is unchanged. Now run the layout check there, then stage " + new + ":\n"
          "  node PLUGIN/scripts/design.mjs preliminary-check . " + plan + " --write-view --require-checked --output " + after + "receipt.json")


def remove(season, base, release, replaced_by=None):
    """Take a release out of the index and delete its published folder and its inputs folder. No redirect is left.

    This is the last step of renaming a release: the same design is first rebuilt, checked and staged under its new ID.
    A release that is or was effective is removed only when --replaced-by names the effective release of the same STEP."""
    checked_id(release)
    site = season / "docs/preliminary-design"
    with update_index(site):
        record = load_index(site)
        if release not in record["releases"]:
            raise ValueError("Unknown release: " + release)
        if replaced_by is not None and (replaced_by == release or replaced_by not in record["releases"]):
            raise ValueError("--replaced-by names a listed release other than the one removed")
        gone, accepted = described(record, release), (record.get("accepted") or {}).get(release)
        if status_of(record, release) == "effective" or accepted:
            if replaced_by is None:
                raise ValueError(sentence(gone) + " is or was the effective design. Remove it only to rename it: stage the same design under its "
                                 "new ID, mark that release effective, then run --remove " + release + " --replaced-by NEW")
            if status_of(record, replaced_by) != "effective":
                raise ValueError("Release " + replaced_by + " is " + status_of(record, replaced_by) + ". Mark it effective before it replaces " + release)
            old, new = step_digest(site, release), step_digest(site, replaced_by)
            if not old or old != new:
                raise ValueError("Releases " + release + " and " + replaced_by + " were checked on different STEP files, or a receipt is missing. "
                                 "A rename keeps the design; a changed design is a new version and the earlier one stays as superseded")
            if accepted:
                # The design was accepted on the earlier date; the rename does not move it.
                record["accepted"][replaced_by] = min(accepted, record["accepted"].get(replaced_by, accepted))
        folders = [site / "releases" / release, base / "releases" / release]
        for folder in folders:
            if folder.is_dir():
                shutil.rmtree(folder)
        record["releases"].remove(release)
        for field in PER_RELEASE:
            (record.get(field) or {}).pop(release, None)
            if field in record and not record[field]:
                del record[field]
        version = version_of(release)
        if version and not any(major_of(r) == version[0] for r in record["releases"]):
            # A major number with no version left is free again, with its name.
            (record.get("designs") or {}).pop(str(version[0]), None)
        if "designs" in record and not record["designs"]:
            del record["designs"]
        save_index(record, site)
    print("Removed " + gone + (", replaced by " + described(record, replaced_by) if replaced_by else "") + ". Its folders "
          + " and ".join(f.resolve().relative_to(season.resolve()).as_posix() for f in folders) + " are deleted and no redirect is left: a link to ?release="
          + release + " now reports an unknown release. The site opens " + str(record.get("current")))
    try:
        links = read(season / "docs/detailed-design/designs.json").get("preliminary") or {}
    except (OSError, ValueError, AttributeError):
        links = {}
    for design in sorted(d for d, link in links.items() if link == release):
        print("Note: detailed design " + design + " names preliminary release " + release + ". Stage it again with --preliminary " + (replaced_by or "NEW") + ".")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("release", nargs="?")
    mode.add_argument("--set-status", nargs=2, metavar=("RELEASE", "STATUS"), help="Set a release " + ", ".join(STATUSES))
    mode.add_argument("--remove", metavar="RELEASE", help="Delete a release's folders and index entry after it was staged again under a new ID; no redirect is left")
    mode.add_argument("--copy-inputs", nargs=2, metavar=("FROM", "TO"),
                      help="Copy a release's check inputs to a new release folder with their pins written for the new paths, to start the next version or rename a release")
    parser.add_argument("--design-name", help="The architecture's name in words, given the first time a major number is staged, as in 1.0")
    parser.add_argument("--replaced-by", metavar="RELEASE", help="With --remove of a release that is or was effective: the effective release of the same STEP")
    parser.add_argument("--reason", help="Why the release is withdrawn, with --set-status RELEASE withdrawn")
    parser.add_argument("--readiness", type=Path, help="Plugin scripts/effective-readiness.mjs, to print its report with --set-status RELEASE effective")
    args = parser.parse_args()
    base = Path(__file__).resolve().parent
    try:
        if args.design_name is not None and not args.release:
            raise ValueError("--design-name goes with staging a version, as in stage.py 1.0 --design-name \"NAME\"")
        if args.replaced_by is not None and not args.remove:
            raise ValueError("--replaced-by goes with --remove")
        if args.set_status:
            site = base.parents[1] / "docs/preliminary-design"
            set_status(site, *args.set_status, reason=args.reason)
            if args.set_status[1] == "effective":
                # Informational: the index is already updated, and the reviewer of the pull request judges the report.
                release = args.set_status[0]
                readiness_report(base / "releases" / release, args.readiness, base.parents[1],
                                 design=title_of(load_index(site), release) if version_of(release) else None)
        elif args.copy_inputs:
            copy_inputs(base.parents[1].resolve(), base, *args.copy_inputs)
        elif args.remove:
            remove(base.parents[1], base, args.remove, args.replaced_by)
        else:
            stage(base.parents[1], base / "releases" / args.release, args.release, args.design_name)
    except (KeyError, ValueError, OSError) as error:
        sys.exit(str(error))
