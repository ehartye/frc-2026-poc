"""Bind the intended public Fusion component recipe to its separately measured student-archive receipt."""

import hashlib
import json
from pathlib import Path

from prepare_upper import parts

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def file_record(path):
    return {
        "file": path.relative_to(ROOT).as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def inventory():
    _, stock, proxies, _ = parts()
    rows = []
    for component in stock + proxies:
        name = component["name"]
        is_vendor = component in proxies
        is_reserve = component["role"] == "electrical"
        if is_vendor:
            role = "mechanism" if "scoring" in name else "drive"
            basis = "Project-drawn public purchased-part envelope. The registered supplier master is described in cad/own-zone-upper/design.md."
        elif is_reserve:
            role = "other"
            basis = "Project-drawn electronics or battery packaging reservation. No supplier solid is redistributed."
        elif any(
            s in name
            for s in ("perimeter tube", "front return", "deck crossmember", "bumper")
        ):
            role = "frame"
            basis = "Project-authored frame and bumper component in the R2C Fusion assembly recipe."
        elif "module tab" in name:
            role = "drive"
            basis = "Project-authored drivetrain interface in the R2C Fusion assembly recipe."
        else:
            role = "mechanism"
            basis = "Project-authored solid in the R2C mechanism and support recipe."
        rows.append(
            {
                "id": name,
                "role": role,
                "representation": "project-proxy"
                if is_vendor or is_reserve
                else "project-original",
                "provenance": basis,
                "editMetric": "extrusions",
            }
        )
    return rows


if __name__ == "__main__":
    revision = json.loads((ROOT / "highlights.json").read_bytes())["revision"]
    source = {
        "schema": "agent-frc/public-fusion-handoff@1",
        "revision": revision,
        "shareable": True,
        "archive": file_record(HERE / "own-zone-public.f3d"),
        "reopen": file_record(HERE / "student-reopen.json"),
        "components": inventory(),
        "joints": [],
    }
    (HERE / "public-handoff.json").write_text(
        json.dumps(source, indent=2, ensure_ascii=False) + "\n",
        encoding="utf8",
        newline="\n",
    )
