"""Evaluate axial abutment and radial journal envelopes against the registered native export."""

import json
import math
import sys
from pathlib import Path

from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
from OCP.BRep import BRep_Builder
from OCP.TopoDS import TopoDS_Compound
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / "cad/assembly-release"))
from offline import shape
from shop import rect, round_stock, hexagon
from verify_products import products

parts = products(root / "cad/assembly-release/foundation-student.step")
folder = Path(__file__).parent
low = "--retained" in sys.argv
recessed = low or "--recessed" in sys.argv
drop = 9 if low else 7 if recessed else 0
shaft_top = 754.7 if low else 765 - drop
stem = (
    "retained-head-fit"
    if low
    else "recessed-head-fit"
    if recessed
    else "opposed-head-fit"
)
out = {}
builder = BRep_Builder()
assembly = TopoDS_Compound()
builder.MakeCompound(assembly)


def vol(sh):
    p = GProp_GProps()
    BRepGProp.VolumeProperties_s(sh, p)
    return abs(p.Mass())


def bounds(sh):
    b = Bnd_Box()
    BRepBndLib.AddOptimal_s(sh, b, False, False)
    return (*b.CornerMin().Coord(), *b.CornerMax().Coord())


def solid_common(a, b):
    return vol(BRepAlgoAPI_Common(a, b).Shape())


for side, sign in [("left", 1), ("right", -1)]:
    x, y = -240, sign * 305

    def tube(lo, hi, outer, inner=0):
        return shape(round_stock((x, y, lo), (x, y, hi), outer / 2, inner / 2))

    orig = parts[side + " upper bearing plate"]
    extra = shape(
        rect(
            (x - 10, min(sign * 295, sign * 302), 744),
            (x + 10, max(sign * 295, sign * 302), 750),
        )
    )
    plate = BRepAlgoAPI_Cut(
        BRepAlgoAPI_Fuse(orig, extra).Shape(), tube(743, 751, 8)
    ).Shape()
    if recessed:
        # The central pocket and pad are machined in one piece from thicker plate.
        extra = shape(
            rect(
                (x - 14, min(sign * 295, sign * 319), 744 - drop),
                (x + 14, max(sign * 295, sign * 319), 750),
            )
        )
        plate = BRepAlgoAPI_Fuse(orig, extra).Shape()
        plate = BRepAlgoAPI_Cut(plate, tube(750 - drop, 751, 19)).Shape()
        plate = BRepAlgoAPI_Cut(plate, tube(743 - drop, 751, 8)).Shape()

    def headtube(lo, hi, outer, inner=0):
        return tube(lo - drop, hi - drop, outer, inner)

    # Entries are checked gauge volumes, not a manufacturer's race CAD or fabricated spindle drawing.
    hardware = {
        "plate": plate,
        "spindle threaded major envelope": tube(557, 736 - drop, 10),
        "integral lower shaft abutment": headtube(736, 739, 12),
        "ground journal": headtube(739, 755, 6),
        "thread for upper lock hardware": tube(755 - drop, shaft_top, 5),
        "lower bearing boundary": headtube(739, 744, 14, 6),
        "upper bearing boundary": headtube(750, 755, 14, 6),
        "plain radial bush boundary": headtube(744, 750, 8, 6.1),
        "upper rotating washer": headtube(755, 757, 12, 5.3),
    }
    if low:
        nut_bottom = 757 - drop
        hardware["DIN980V M5 upper lock nut gauge"] = shape(
            hexagon((x, y, nut_bottom), (x, y, nut_bottom + 5.1), 8, 2.5)
        )
        socket = tube(nut_bottom, nut_bottom + 35, 12, 9.3)
        if solid_common(socket, plate) > 0.001:
            raise ValueError("Socket intersects head plate")
    for sh in hardware.values():
        builder.Add(assembly, sh)
    excluded = {side + " upper bearing plate", side + " lead screw envelope"}
    collisions = []
    for name, article in hardware.items():
        aa = bounds(article)
        for n, part in parts.items():
            if n in excluded:
                continue
            bb = bounds(part)
            if any(
                min(aa[i + 3], bb[i + 3]) - max(aa[i], bb[i]) < 0.0001 for i in range(3)
            ):
                continue
            v = solid_common(article, part)
            if v > 0.01:
                collisions.append([name, n, round(v, 4)])
    contacts = {}
    for z, lo in [(744, 744), (750, 749.99)]:
        gauge = headtube(lo, lo + 0.01, 14, 8)
        contacts[str(z - drop)] = round(solid_common(gauge, plate) / 0.01, 5)
    ideal = math.pi * (7**2 - 4**2)
    assert all(abs(a - ideal) < 0.002 for a in contacts.values())
    assert solid_common(plate, hardware["ground journal"]) < 0.001
    assert (
        abs(BRepExtrema_DistShapeShape(plate, hardware["ground journal"]).Value() - 1)
        < 1e-4
    )
    out[side] = {
        "fullHousingBackingAreaMm2": contacts,
        "highestJournalZ": shaft_top,
        "nominalHeadToHeightLimitMm": 762 - shaft_top,
        "shaftShoulderDiameterMm": 12,
        "requiredMinimumMm": 10.8,
        "journalToPlateRadialClearanceMm": 1,
        "nearestPlateEdgeBeyond14mmRaceMm": 3,
        "collisionsWithOriginalParkedAssemblyMm3": collisions,
    }
    if low:
        out[side]["nutTopZMm"] = nut_bottom + 5.1
        out[side]["threadAboveNutMm"] = shaft_top - nut_bottom - 5.1
        out[side]["carriageNutToLowerShoulderParkedMm"] = BRepExtrema_DistShapeShape(
            parts[side + " driven nut"], hardware["integral lower shaft abutment"]
        ).Value()
        out[side]["socketToHousingMm"] = BRepExtrema_DistShapeShape(
            socket, plate
        ).Value()
writer = STEPControl_Writer()
writer.Transfer(assembly, STEPControl_AsIs)
writer.Write(str(folder / (stem + ".step")))
out["scope"] = (
    "Nominal parked fit only. Bearing envelopes are gauges for EZO F6-14M. Reopen exported STEP before design use. Unverified elements include reverse locknut, race pilots and tolerances, selected radial bush, lubrication, life and working load, alignment, tool and motion sweeps. Lower gearbox remains an undrilled envelope."
)
(folder / (stem + ".json")).write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))
