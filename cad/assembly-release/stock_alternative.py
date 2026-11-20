"""Solid machined crossmember option for tube lots whose crown cannot carry the post fillet."""

from frame import build as original
from shop import rect, stock


def parts():
    base = original()
    for x, end in ((-151, "rear"), (129, "front")):
        row = base[end + " deck crossmember"]
        row["features"] = [
            stock(rect([x - 12.7, -308.25, 96.6], [x + 12.7, 308.25, 122]))
        ]
        row["stock"] = {
            "source": "Online Metals 1117",
            "grade": "6061-T6511",
            "incomingSquareMm": 31.75,
            "finishedSquareMm": 25.4,
            "edgeRadiusMaxMm": 0.25,
            "cutLengthMm": 616.5,
        }
        row["purchase"] = "Online Metals 1117, machined 6061-T6511 square bar"
    return base


def test(source):
    from drivetrain_fit import run, vol
    from frame_bearing import sample
    from offline import machine

    result = run(source, frame_recipe=parts)
    frame = parts()
    prior = original()
    result["alternate"] = {}
    result["massChangeKg"] = 0.0
    for end in ("front", "rear"):
        key = end + " deck crossmember"
        cross = machine(frame[key]["features"])
        result["massChangeKg"] += (
            vol(cross) - vol(machine(prior[key]["features"]))
        ) * 2.7e-6
        for sg, side in ((1, "left"), (-1, "right")):
            plate = machine(
                frame[end + " " + side + " crossmember backing plate"]["features"]
            )
            post = machine(frame[end + " " + side + " hopper post"]["features"])
            result["alternate"][end + " " + side] = dict(
                end=sample(cross, plate, [0, sg, 0]),
                post=sample(post, cross, [0, 0, -1]),
            )
    return result


if __name__ == "__main__":
    import argparse, json
    from pathlib import Path

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("supplier", type=Path)
    p.add_argument("out", type=Path)
    a = p.parse_args()
    a.out.write_text(json.dumps(test(a.supplier), indent=2) + "\n", encoding="utf8")
