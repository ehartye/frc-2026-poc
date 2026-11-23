"""Publish a checked preliminary design release into the season site, or set a release's design status.

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


def current_for(record):
    """The release the stable URL opens: the effective one, else the newest in-progress one, else the newest not withdrawn."""
    names = record["releases"]
    return (next((n for n in names if status_of(record, n) == "effective"), None)
            or next((n for n in reversed(names) if status_of(record, n) == "in-progress"), None)
            or next((n for n in reversed(names) if status_of(record, n) != "withdrawn"), None)
            or (names[-1] if names else None))


def save_index(record, site):
    record["current"] = current_for(record)
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


def stage(season, inputs, release):
    """Copy one release's checked files into the site and list it in the index as in progress.

    An in-progress release is revised in place: staging its ID again replaces its published files and counts a
    revision in the index. A release stops changing when it is marked effective, and stays so afterwards."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", release):
        raise ValueError("Use a lowercase release ID with letters, digits and hyphens")
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
        if release in index["releases"] and status_of(index, release) != "in-progress":
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
            print("Preliminary release " + release + " is unchanged (revision " + str(revision_of(index, release)) + ")")
            return
        if replaced:
            # Git holds the earlier bytes; the pull request shows what changed.
            shutil.rmtree(destination)
        staged.rename(destination)
        # One design keeps one ID: an edit counts a revision here and adds no entry to the picker.
        number = revision_of(index, release) + 1 if replaced or release in index["releases"] else 1
        commit = head_commit(season)
        index.setdefault("revision", {})[release] = dict(number=number, date=datetime.date.today().isoformat(),
                                                         **(dict(commit=commit) if commit else {}))
        if release not in index["releases"]:
            index["releases"].append(release)
            index.setdefault("designStatus", {})[release] = "in-progress"
        save_index(index, site)
    print(("Revised preliminary release " + release + " in place" if number > 1 else "Staged preliminary release " + release)
          + " (" + status_of(index, release) + ", revision " + str(number) + ")")


def readiness_report(inputs, reporter=None, season=None):
    """Show the reviewer the plugin's effective-readiness report for a release's inputs. It never stops a status change."""
    where = [inputs.as_posix()]
    try:
        # A release checked from the repository root resolves its trial pins from there.
        if season is not None and project_root(season, inputs, read(inputs / "layout.json").get("view")) == season.resolve():
            where = [season.as_posix(), "--release", inputs.resolve().relative_to(season.resolve()).as_posix()]
    except (OSError, ValueError):
        pass
    command = "node PLUGIN/scripts/design.mjs effective-readiness " + " ".join(where)
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
    """How many times a release has been staged with changed files. One published before revisions were counted is at 1."""
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
    print("Preliminary release " + release + " is " + status + "; the site opens " + str(record["current"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("release", nargs="?")
    mode.add_argument("--set-status", nargs=2, metavar=("RELEASE", "STATUS"), help="Set a release " + ", ".join(STATUSES))
    parser.add_argument("--reason", help="Why the release is withdrawn, with --set-status RELEASE withdrawn")
    parser.add_argument("--readiness", type=Path, help="Plugin scripts/effective-readiness.mjs, to print its report with --set-status RELEASE effective")
    args = parser.parse_args()
    base = Path(__file__).resolve().parent
    try:
        if args.set_status:
            set_status(base.parents[1] / "docs/preliminary-design", *args.set_status, reason=args.reason)
            if args.set_status[1] == "effective":
                # Informational: the index is already updated, and the reviewer of the pull request judges the report.
                readiness_report(base / "releases" / args.set_status[0], args.readiness, base.parents[1])
        else:
            stage(base.parents[1], base / "releases" / args.release, args.release)
    except (KeyError, ValueError, OSError) as error:
        sys.exit(str(error))
