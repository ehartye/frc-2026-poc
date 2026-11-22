"""Append a checked season release, or audit the index before deploying the season site."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile


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
    dirs = {p.name for p in (site / "releases").iterdir() if p.is_dir() and not p.name.startswith(".")}
    if set(names) - dirs or dirs - set(names) - {recovering}:
        raise ValueError("Release index and immutable directories disagree. Reconcile every release before publishing.")
    for name in names:
        release = site / "releases" / name
        expected = read(release / "receipt.json")["view"]["sha256"]
        if hashlib.sha256((release / "index.html").read_bytes()).hexdigest() != expected:
            raise ValueError("Indexed view differs from receipt: " + name)
    return record


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
    with update_index(site), tempfile.TemporaryDirectory(dir=site.parent, prefix=".stage-") as tmp:
        record = index(site, recovering=release)
        if release in record["releases"]:
            raise FileExistsError("Release already exists: " + release)
        files = {"index.html": viewer, "receipt.json": receipt_file, "motion.json": pinned(inputs, plan["motion"])}
        if plan.get("budgets"):
            ledger = pinned(inputs, plan["budgets"])
            files.update({"budgets.json": ledger, "limits.json": pinned(inputs, read(ledger)["requirements"])})
        staged = Path(tmp) / release
        staged.mkdir()
        for name, src in files.items():
            shutil.copyfile(src, staged / name)
        if destination.exists():
            if {p.name for p in destination.iterdir()} != set(files) or any(
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
