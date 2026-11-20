"""Bind the intended student design inventory to the independently reopened deliverable."""

import hashlib, json
from pathlib import Path
from recipe import parts

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def reference(file):
    return dict(
        file=file, sha256=hashlib.sha256((ROOT / file).read_bytes()).hexdigest()
    )


if __name__ == "__main__":
    base = json.loads((ROOT / "cad/own-zone-upper/public-handoff.json").read_bytes())
    old = base["components"]
    planned = []
    for p in parts():
        ident = p["name"]
        proxy = "envelope" in ident or any(
            word in ident
            for word in (
                "driven nut",
                "deployment nut",
                "bearing and stop",
                "forward bearing",
            )
        )
        planned.append(
            dict(
                id=ident,
                role="mechanism",
                representation="project-proxy" if proxy else "project-original",
                provenance="Project-authored packaging and interface sketch; no manufacturer geometry redistributed."
                if proxy
                else "Original dimensioned low-rung assembly part in cad/tower-lift/recipe.py.",
                editMetric="extrusions",
            )
        )
    direction = reference("cad/tower-lift/directions.json")
    joints = [
        dict(
            id=key, type="slider", occurrenceOne=a, occurrenceTwo=b, direction=direction
        )
        for key, a, b in (
            ("Tower rear deployment", "left extending rail", "crosshead lift bridge"),
            ("Tower load stroke", "crosshead lift bridge", "left mast"),
        )
    ]
    revision = json.loads((ROOT / "highlights.json").read_bytes())["revision"]
    manifest = dict(
        schema=base["schema"],
        revision=revision,
        shareable=True,
        archive=reference("cad/tower-lift/tower-l1.f3d"),
        reopen=reference("cad/tower-lift/student-reopen.json"),
        components=old + planned,
        joints=joints,
    )
    (HERE / "public-handoff.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf8",
        newline="\n",
    )
