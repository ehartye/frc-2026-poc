"""Assemble the passive service revision from the public foundation, in robot coordinates."""

import argparse, hashlib, json
from pathlib import Path

from bumpers import build as wraps
from battery import build as cradle
from deck_seats import build as decks
from foundation_job import recipe as foundation


def recipe():
    prior = foundation()
    changed, hardware, rail_cuts, panels = wraps()
    power = cradle()
    extra, seats = decks(power)
    revised = {**changed, **hardware, **power, **extra}
    for name, ops in seats.items():
        rail_cuts.setdefault(name, []).extend(ops)
    for name, ops in rail_cuts.items():
        old = prior["parts"][name]
        revised[name] = {
            **old,
            "appendFeatures": ops,
            "features": [*old["features"], *ops],
        }
    existing = set(prior["parts"])
    groups = {}
    for panel in panels:
        name = panel["panel"]
        key = name.replace(" blue", "")
        base = (
            name.split()[0] + " perimeter tube"
            if "side" in name
            else "rear perimeter tube"
            if name.startswith("rear")
            else name.split()[0] + " front return"
        )
        groups["Installed " + name] = [
            base,
            name,
            key + " padding",
            key + " backer",
            *(k for k in hardware if k.startswith(key + " mounting ")),
        ]
    groups["Installed battery well and removable sled"] = [
        "rear deck crossmember",
        *(k for k in power if "electronics deck" not in k),
    ]
    for name in power:
        if "electronics deck" in name:
            # The two real attachment rows anchor each deck. The grounding field
            # takes one structural member; the physical BOM carries all the seats.
            groups["Retained " + name] = [
                ("front" if name.startswith("fore") else "rear") + " deck crossmember",
                name,
                *(k for k in extra if k.startswith(name + " retainer ")),
            ]
    for name, row in revised.items():
        if name not in existing:
            row["identity"] = (
                "R26-SVC-"
                + hashlib.sha256(("article/" + name).encode()).hexdigest()[:16]
            )
            row.setdefault("instance", row["identity"])
    return {
        "schema": "rebuilt-service-cad/v1",
        "archiveBase": "cad/assembly-release/foundation-student.f3d",
        "archiveSha256": "3e11e4f83ad035d1999aae2b6509fbeef82c5b6d410ce6f5c60b6229d819c6c0",
        "stepBase": "cad/assembly-release/foundation-student.step",
        "stepSha256": "6b5bc9ee326ba83b2db1885ae0a4033d1a74a7efc35911fc44af69d24421e79e",
        "parts": revised,
        "groups": groups,
        "sites": prior["sites"],
        "panels": panels,
        "palette": prior["palette"],
        "teamNumber": None,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out", type=Path)
    a = ap.parse_args()
    data = recipe()
    a.out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf8")
    print(
        len(data["parts"]),
        "machined or purchased articles",
        len(data["groups"]),
        "physically registered assemblies",
    )
