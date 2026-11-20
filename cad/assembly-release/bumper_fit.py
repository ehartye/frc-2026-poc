"""Verify proposed removable bumper mounts against the complete registered chassis and module envelopes."""

import argparse, json
from pathlib import Path
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.gp import gp_Trsf, gp_Vec
import numpy as np

from bumpers import build as panels
from frame import build as frame
from drivetrain_fit import run as module_fit, vol, broad, moved
from offline import machine, shape
from shop import round_stock, rect
from supplier import bounds, content
from swerve import layout
from verify_products import products
from passive_job import recipe
from battery import build as battery
from deck_seats import build as decks


def revised():
    stock = frame()
    wrap, fittings, holes, bill = panels()
    for n, ops in holes.items():
        stock[n]["features"].extend(ops)
    electrics = battery()
    retainers, beam_cuts = decks(electrics)
    for n, ops in beam_cuts.items():
        stock[n]["features"].extend(ops)
    stock.update(electrics)
    stock.update(retainers)
    stock.update(wrap)
    stock.update(fittings)
    return stock


def run(source):
    wrapped, fittings, holes, bill = panels()
    plan = recipe()
    path = Path(__file__).resolve().parents[2] / plan["stepBase"]
    stationary = products(path)
    stationary = {k: s for k, s in stationary.items() if " public " not in k}
    for name, p in plan["parts"].items():
        stationary[name] = machine(p["features"])
    cfg, _, _, sites = layout()
    vendor = content(source, cfg["swerve"]["sha256"])
    for site in sites:
        for k, v in vendor.items():
            stationary[site["name"] + " supplier " + k] = moved(v, site)
    space = {k: (s, bounds(s)) for k, s in stationary.items()}

    def overlaps(s, skip):
        bb = bounds(s)
        bad = {}
        for key, (other, b) in space.items():
            if key in skip or not broad(bb, b):
                continue
            v = vol(BRepAlgoAPI_Common(s, other).Shape())
            if v > 0.025:
                bad[key] = round(v, 4)
        return bad

    paths = {}
    pulls = {}
    continuous = {}
    for b in bill:
        cover = b["panel"]
        prefix = cover.replace(" blue", "")
        if cover.startswith("rear"):
            normal = np.array([-1, 0, 0])
        elif "front" in cover:
            normal = np.array([1, 0, 0])
        else:
            normal = np.array([0, 1 if cover.startswith("left") else -1, 0])
        items = {cover, prefix + " padding", prefix + " backer"}
        detached = set(items)
        for i, (s, axis) in enumerate(
            zip(b["installedFrameStationsMm"], b["topScrewAxisMm"]), 1
        ):
            tag = prefix + " mounting " + str(i)
            screw = tag + " top screw"
            accomp = {
                n
                for n in fittings
                if n.startswith(tag + " ")
                and not n.endswith((" top screw", " frame boss"))
            }
            items.update(accomp)
            detached.update(accomp | {screw})
            x, y, z = axis

            # Entire screw extraction from its head seat and the longer bit up to a hand plane.
            # The test separately checks a 16 mm OD straight handle after it clears the bumper top.
            def axial(a, b, r):
                return shape(round_stock([x, y, a], [x, y, b], r))

            pos = {}
            for key, envelope in (
                ("cap withdrawal", axial(z, z + 38, 5.05)),
                ("long driver", axial(z + 5.99, 201, 3.1)),
                ("driver handle", axial(201, 245, 8)),
            ):
                pos[key] = overlaps(envelope, {screw})
            paths[tag] = pos
        negative = {}
        for step in (0.5, 3, 10, 25, 42, 60):
            xyz = normal * step
            tr = gp_Trsf()
            tr.SetTranslation(gp_Vec(*xyz))
            for n in items:
                moving = BRepBuilderAPI_Transform(stationary[n], tr, False).Shape()
                for k, v in overlaps(moving, detached).items():
                    negative[f"{n} / {k} @ {step}"] = v
        pulls[cover] = negative
        # Each uncut additive feature is enclosed for its entire 60 mm translation.
        # A vacant enclosure proves clearance including intermediate positions.
        # An overlap needs an exact swept shape or a new station.
        blocked = {}
        for part_name in sorted(items):
            for i, feat in enumerate(plan["parts"][part_name]["features"]):
                if feat["op"] == "cut":
                    continue
                bb = np.array(bounds(shape(feat["shape"])))
                # Remove only the OCCT bounding-box tolerance, below 1 micrometre.
                bb[:3] += 1e-7
                bb[3:] -= 1e-7
                shift = 60 * normal
                low = bb[:3] + np.minimum(0, shift)
                high = bb[3:] + np.maximum(0, shift)
                conflicts = overlaps(shape(rect(low, high)), detached)
                if conflicts:
                    blocked[f"{part_name} additive stock {i + 1}"] = conflicts
        continuous[cover] = blocked
    return {
        "source": module_fit(source, frame_recipe=revised),
        "toolHits": paths,
        "steppedWithdrawalHits": pulls,
        "continuousConservativeWithdrawalHits": continuous,
        "precedingStepSha256": plan["stepSha256"],
        "cutList": bill,
        "period": "Kickoff V0 + TU00; R401-R412",
        "scope": "15 proposed mount stations. A top-access M6 screw, 5 mm driver and 16 mm handle are screened against the parked project shapes. All uncompressed foam is idealized. Tool hand/ratchet arc and installed wire clearance remain separate. No clock claim for changing covers.",
    }


if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("module", type=Path)
    a.add_argument("out", type=Path)
    x = a.parse_args()
    x.out.write_text(json.dumps(run(x.module), indent=2) + "\n", encoding="utf8")
