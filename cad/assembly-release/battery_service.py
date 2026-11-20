"""Check battery restraint and the continuous vertical extraction envelope against the parked source assembly."""

import argparse, json
import numpy as np
from pathlib import Path
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from battery import build
from passive_job import recipe
from verify_products import products
from offline import machine, shape
from hashlib import sha256
from drivetrain_fit import vol, broad
from shop import rect, round_stock
from supplier import bounds


def check():
    parts = build()
    job = recipe()
    source = Path(__file__).resolve().parents[2] / job["stepBase"]
    if sha256(source.read_bytes()).hexdigest() != job["stepSha256"]:
        raise ValueError("Incorrect source")
    fixed = products(source)
    fixed.update({k: machine(v["features"]) for k, v in job["parts"].items()})
    world = {k: (s, bounds(s)) for k, s in fixed.items()}
    pack = "battery secured envelope"

    def clashes(s, skip):
        bb = bounds(s)
        hits = {}
        for k, (other, ob) in world.items():
            if k not in skip and broad(bb, ob):
                v = vol(BRepAlgoAPI_Common(s, other).Shape())
                if v > 0.01:
                    hits[k] = round(v, 4)
        return hits

    # Conservative upper dimension extends 2 mm above nominal for all three dimensions.
    sweep = shape(rect([-133, -37, 48], [50, 41, 805]))
    keeper = {
        "battery center keeper",
        *(k for k in parts if "hold-down screw" in k or "hold-down washer" in k),
    }
    clash = clashes(sweep, {pack})
    open_hits = clashes(sweep, keeper | {pack})
    # Translate the entire mechanically locked but electrically disconnected cassette straight down.
    # Rectangular sweeps of moving article bounds enclose every intermediate translation, including curved hardware.
    held = {
        pack,
        "battery cradle floor",
        "battery center keeper",
        *(
            k
            for k in parts
            if "battery end stop" in k
            or "battery cradle wall" in k
            or "battery hold-down" in k
        ),
    }
    removal = {
        k
        for k in parts
        if "battery sled mount" in k and k.endswith((" screw", " washer"))
    }
    down = {}
    for k in held:
        bb = np.array(world[k][1], float)
        bb[2] -= 270
        trial = shape(rect(bb[:3].tolist(), bb[3:].tolist()))
        bad = clashes(trial, held | removal)
        if bad:
            down[k] = bad
    # Entire solid seated reaction requires the existing supplier case to remain inside this clearance.
    # Intentional thread engagement is recorded in the detailed parked-interference map.
    side_directions = {}
    for side, d in (("left", 1), ("right", -1)):
        envelope = shape(
            rect([-133, min(-37, -37 + 500 * d), 48], [50, max(41, 41 + 500 * d), 217])
        )
        # Give the drawer the best possible case by removing its own pickup/retention articles.
        bare_obstacles = clashes(
            envelope, set(parts) - {"right electronics deck", "left electronics deck"}
        )
        high = shape(
            rect([-133, min(-37, -37 + 500 * d), 116], [50, max(41, 41 + 500 * d), 285])
        )
        upper_obstacles = clashes(
            high, set(parts) - {"right electronics deck", "left electronics deck"}
        )
        side_directions[side] = {
            "existingHeight": bare_obstacles,
            "raise68mmToClearRail": upper_obstacles,
        }
    # Purpose-built practice pit cart. Structural runners contact bottom frame rails (Z64), while
    # an independent jack platform and four anti-slide lips capture the cassette before releasing fasteners.
    cart = {}
    for side, yy in (("right", -327.3), ("left", 327.3)):
        for end, x in (("fore", 74), ("aft", -77)):
            cart[f"{side} {end} chassis support pad"] = shape(
                rect([x - 32, yy - 9, 48], [x + 32, yy + 9, 64])
            )
    platform = shape(rect([-121, -43, 33.65], [38, 46, 41.65]))
    # Short ledges surround the tray on X with 2 mm location allowance. Four ground-side screws sit outboard.
    lips = [shape(rect([x, -34, 37.65], [x + 4, 39, 46.65])) for x in (-143, 56)]
    # Cart platform runners support the lips without occupying the washer/tool stations.
    supports = [
        shape(rect([-145, -30, 30], [62, -22, 37.65])),
        shape(rect([-145, 21, 30], [62, 29, 37.65])),
    ]
    cart["sled platform"] = platform
    total = 0
    for k, v in cart.items():
        if k != "sled platform":
            inside = shape(
                rect(
                    [bounds(v)[0], bounds(v)[1], 64],
                    [bounds(v)[3], bounds(v)[4], 64.01],
                )
            )
            total += (
                vol(
                    BRepAlgoAPI_Common(
                        inside, world[k.split()[0] + " perimeter tube"][0]
                    ).Shape()
                )
                / 0.01
            )
    cart_hits = {k: clashes(v, ()) for k, v in cart.items()}
    for i, pad in enumerate(lips + supports):
        cart_hits[f"sled lip or support {i + 1}"] = clashes(pad, ())
    surface = shape(rect([-121, -43, 41.65], [38, 46, 41.66]))
    sled_support = (
        vol(BRepAlgoAPI_Common(surface, world["battery cradle floor"][0]).Shape())
        / 0.01
    )
    cart_scope = {
        "staticRobotContactAreaMm2": round(total, 3),
        "cassetteRestBeforeScrewReleaseMm2": round(sled_support, 3),
        "nominalInitialInterferenceMm3": cart_hits,
        "floorDatumBelowCarpetPlaneMm": 380,
        "lowestCartPlatformAfter270mmLoweringMm": -240,
        "floorClearanceAtEndMm": 140,
        "purpose": "Chassis is seated first on four support pads. Raise the independent lift platform into positive contact under the loaded sled before removing four underside screws. Lower 270 mm with tray kept between fore and aft lips. The entire assembly is then outside the robot. Dolly lift, bracing, load rating, connector/routing and installed operator access still require project verification.",
    }
    gauges = {}
    for which, sy in (("right", -75), ("left", 78)):
        for idx, x in enumerate((-110, 26), 1):
            stem = f"{which} battery sled mount {idx}"
            held_screw = stem + " screw"
            excluded = {held_screw}
            key = shape(round_stock([x, sy, -45], [x, sy, 35.65], 3))
            # An 18 mm diam straight handle occupies a separate 55 mm length below the bit.
            grip = shape(round_stock([x, sy, -100], [x, sy, -45], 9))
            socket = shape(round_stock([x, sy, 10], [x, sy, 35.65], 4.35))
            station = {}
            for label, s in (
                ("4mm key", key),
                ("18mm grip", grip),
                ("head withdrawal", socket),
            ):
                site = clashes(s, excluded)
                for g, o in [
                    *cart.items(),
                    *((f"lip {i}", v) for i, v in enumerate(lips + supports)),
                ]:
                    if broad(bounds(s), bounds(o)):
                        v = vol(BRepAlgoAPI_Common(s, o).Shape())
                        if v > 0.01:
                            site["cart " + g] = round(v, 4)
                station[label] = site
            gauges[held_screw] = station
    # Representative SB50 pair aligned along Y in the side bay forward of the tray.
    # Envelope separation uses the catalog mated length; neither insulation nor cable slack is inferred.
    # 23 mm release = 14.7 mm interlock plus 8.3 mm projected clear before unplugged lowering.
    housing = shape(rect([65.45, -40.65, 75], [100.55, 40.65, 90.9]))
    disconnected = shape(rect([65.45, -63.65, 75], [100.55, 7.35, 90.9]))
    descent = shape(rect([65.45, -63.65, 75 - 270], [100.55, -15.65, 90.9]))
    handling = shape(rect([59.45, -74, 69], [106.55, -39, 97]))
    connector = {
        label: clashes(body, set())
        for label, body in (
            ("joined pair", housing),
            ("23mm separation", disconnected),
            ("unpinned housing lowered with tray", descent),
            ("side grip section", handling),
        )
    }
    connector.update(
        source="Anderson 992G1, DS-SB50 rev 9. Single body 48 x 35.1 x 15.9 mm; pair joined 81.3 mm. The named CAD volumes are clearance studies, and do not provide 6 AWG routing, connector mounts, cable strain relief or evidence of hand contact.",
        prematedPairCenterMm=[83, 0, 82.95],
        separationMm=23,
        projectedUnmatedGapMm=8.3,
    )
    # Different Anderson drawing and family editions give different widths. Surround
    # both values and add the drawing tolerance as a separate receiving gauge.
    lower = 82.95 - 16.4 / 2
    upper = 82.95 + 16.4 / 2
    tol_shapes = {
        "joined": rect([64.45, -40.9, lower], [101.55, 40.9, upper]),
        "23mm release sweep": rect([64.45, -63.9, lower], [101.55, 8.1, upper]),
        "pack-side 270mm drop": rect([64.45, -63.9, lower - 270], [101.55, -14.4, upper]),
    }
    connector["editionAndReceivingEnvelope"] = {
        "housingMaximumMm": [48.5, 37.1, 16.4],
        "matedPairLengthMm": [80.8, 81.8],
        "worstIndependentSeparationGapMm": round(23 - (2 * 48.5 - 80.8), 2),
        "contactsMm3": {name: clashes(shape(box), set()) for name, box in tol_shapes.items()},
        "basis": "Anderson drawing 111923S1 Rev 2 and DS-SB50 Rev 9. Take the larger nominal from both editions on each perpendicular axis plus 0.5 mm. The finished mated length, lug, strain relief and wiring require separate receiving checks."
    }
    transient = {}
    for name, s in ((n, world[n][0]) for n in parts if n != pack):
        hits = clashes(s, {name})
        if hits:
            transient[name] = hits
    return dict(
        purchase="MK ES17-12 F3",
        baseSha256=job["stepSha256"],
        cartToolAccess=gauges,
        disconnectedHousing=connector,
        sideDrawerSweeps=side_directions,
        cartAndSled=cart_scope,
        catalogMassKg=5.86,
        maxCaseAssumedMm=[183, 78, 169],
        centerDatumMm=[-41.5, 2, 48],
        translationAxis=[0, 0, 1],
        continuousExtractionTopZMm=805,
        installedKeeperObstaclesMm3=clash,
        removedKeeperObstaclesMm3=open_hits,
        parkedPartInterferencesMm3=transient,
        downwardSledWithdrawalHitsMm3=down,
        loweringDistanceMm=270,
        requiredCartClearanceBelowSledMm=270,
        nominalRoomMm={"foreAndAftEach": 1.825, "left": 3, "right": 4, "above": 3},
        dose={
            "caseInertialForceAt3gN": round(5.86 * 3 * 9.80665, 2),
            "keeperBendingMPaAt3gUsingMidpointPointLoad": round(
                1.5 * 5.86 * 3 * 9.80665 * 104.6 / (25 * 6.35**2), 2
            ),
        },
        restrictions="One bare battery. Compare electrical connector and cable removal separately. The terminal shroud and lead loop can extend beyond the supplied case dimensions. Conservative fully swept upper case does not establish mechanic hand access. The housing material is ABS, while mass is charged once using the complete manufacturer-quoted pack.",
    )


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("output", type=Path)
    a = cli.parse_args()
    a.output.write_text(json.dumps(check(), indent=2) + "\n", encoding="utf8", newline="\n")
