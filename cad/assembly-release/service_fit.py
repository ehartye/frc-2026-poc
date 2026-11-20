from pathlib import Path
import json
from passive_job import recipe
from offline import machine
from verify_products import products, measure
from drivetrain_fit import broad, vol
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from supplier import bounds
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.gp import gp_Trsf, gp_Vec
from hashlib import sha256
import argparse


def audit(folder):
    plan = recipe()
    source = Path(__file__).parents[2] / plan["stepBase"]
    if sha256(source.read_bytes()).hexdigest() != plan["stepSha256"]:
        raise ValueError("Wrong source")
    old = products(source)
    rows = plan["parts"]
    merged = {**old, **{k: machine(v["features"]) for k, v in rows.items()}}
    measured = {}
    for k in rows:
        volume, _, _, solids = measure(merged[k])
        measured[k] = dict(volumeMm3=round(float(volume), 5), solids=solids)
    boxes = {k: bounds(s) for k, s in merged.items()}
    pairs = {}
    for a, sa in merged.items():
        for b, sb in merged.items():
            if (
                b <= a
                or (a not in rows and b not in rows)
                or not broad(boxes[a], boxes[b])
            ):
                continue
            v = vol(BRepAlgoAPI_Common(sa, sb).Shape())
            if v > 0.025:
                pairs[a + " / " + b] = round(v, 4)
    expected = {}
    for name, row in rows.items():
        if name.endswith(
            (
                " panel screw",
                " top screw",
                " retainer screw",
                "hold-down screw",
                "sled mount 1 screw",
                "sled mount 2 screw",
            )
        ) or (" retainer " in name and name.endswith(" screw")):
            expected[" / ".join(sorted((name, row["parent"])))] = row["connection"]
    unaccounted = set(pairs) - set(expected)
    absent = set(expected) - set(pairs)
    seats = {}

    def seat(a, b, axis):
        av, bv = merged[a], merged[b]
        tr = gp_Trsf()
        tr.SetTranslation(gp_Vec(*(x * 0.01 for x in axis)))
        pushed = BRepBuilderAPI_Transform(av, tr, False).Shape()
        key = a + " to " + b
        seats[key] = dict(
            nominalVolumeMm3=round(vol(BRepAlgoAPI_Common(av, bv).Shape()), 5),
            normal=list(axis),
            contactAreaMm2=round(vol(BRepAlgoAPI_Common(pushed, bv).Shape()) / 0.01, 4),
        )

    for panel in plan["panels"]:
        part = panel["panel"]
        stem = part.replace(" blue", "")
        side = "side" in part
        outward = (
            (0, 1 if part.startswith("left") else -1, 0)
            if side
            else (-1 if part.startswith("rear") else 1, 0, 0)
        )
        for i, _ in enumerate(panel["topScrewAxisMm"], 1):
            bracket = f"{stem} mounting {i} angle"
            seat(bracket, rows[bracket]["parent"], [0, 0, -1])
            seat(bracket, stem + " backer", outward)
    for name, row in rows.items():
        if name.endswith(("sled mount 1", "sled mount 2")):
            seat(name, row["parent"], [0, 0, 1])
            seat(name, "battery cradle floor", [0, 0, -1])
        elif name.endswith(" well bearer"):
            seat(name, "rear deck crossmember", [-1, 0, 0])
            seat(name, "front deck crossmember", [1, 0, 0])
        elif name.endswith(" hold-down post"):
            seat(name, "battery cradle floor", [0, 0, -1])
            seat(name, "battery center keeper", [0, 0, 1])
    for deck in (
        "left electronics deck",
        "right electronics deck",
        "fore electronics deck bridge",
        "aft electronics deck bridge",
    ):
        for end in (
            ("front", "rear")
            if deck.startswith(("left", "right"))
            else (("front",) if deck.startswith("fore") else ("rear",))
        ):
            seat(deck, end + " deck crossmember", [0, 0, -1])
    seat("battery secured envelope", "battery cradle floor", [0, 0, -1])
    return dict(
        sourceSha256=plan["stepSha256"],
        count=len(merged),
        products=measured,
        modeledThreadContacts=pairs,
        unexpectedCommonMm3={k: pairs[k] for k in sorted(unaccounted)},
        absentThreadEngagement=sorted(absent),
        seats=seats,
        passParked=not unaccounted
        and not absent
        and all(r["solids"] == 1 for r in measured.values())
        and all(
            r["nominalVolumeMm3"] <= 0.025 and r["contactAreaMm2"] > 1
            for r in seats.values()
        ),
    )


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("output", type=Path)
    args = a.parse_args()
    data = audit(args.output.parent)
    args.output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf8")
