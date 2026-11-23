"""Field fixtures for the layout check, taken from FIRST's official field model in cad/field/official/.

Each fixture is one official part: its geometry is the published solid, copied rigidly into the robot datum at the
shot pose (robot centre 2700 mm on the alliance-wall side of the HUB centre, on its centreline, +X toward the blue
alliance wall). The HUB and the TOWER keep their official positions relative to each other. Fasteners, tags, lights,
the fuel counter and other small parts are left out of the check; cad/field/official/ holds the whole assemblies.
"""
import importlib.util
import json
import re
from pathlib import Path

from OCP.OCP.collections import Sequence_TDF_Label
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.TDF import TDF_Label
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.gp import gp_Trsf, gp_Vec

REPO = Path(__file__).resolve().parents[2]
FOLDER = REPO / "cad/field/official"
SHOT_POSE = (-6345.0, 0.0, 0.0)   # official millimetres -> robot datum at the shot pose (official-field.json, blue-hub dockFrames)

# fixture name stem -> (file, official product name pattern, what it is for the mission)
SELECTION = [
    ("hub funnel side", "blue-hub", r"^GE-26329: Hub Funnel Side$", "One of the six sloping walls of the HUB funnel. A FUEL that enters the opening lands on them"),
    ("hub funnel base", "blue-hub", r"^GE-26315-01: Hub Funnel Base$", "Bottom of the HUB funnel, where scored FUEL drop to the counter"),
    ("hub roof panel", "blue-hub", r"^GE-26304: Hub Roof Panel$", "Roof of the HUB body around the funnel"),
    ("hub side panel", "blue-hub", r"^GE-26305: Hub Side Panel$", "Side panel of the HUB body"),
    ("hub front panel top", "blue-hub", r"^GE-26308: Hub Front Panel, Top$", "Upper panel of the HUB face"),
    ("hub front panel bottom", "blue-hub", r"^GE-26328: Hub Front Panel, Bottom$", "Lower panel of the HUB face"),
    ("hub rear panel", "blue-hub", r"^GE-26306: Hub Rear Panel, Bottom$", "Neutral-zone panel of the HUB body"),
    ("hub net", "blue-hub", r"^GE-26318: Hub Net \(Aesthetic\)$", "Net behind the opening. A shot that carries past the opening meets it"),
    ("tower base", "blue-tower", r"^GE-26501-01: Tower Base Bottom$", "TOWER BASE plate. A Level 1 hang has to clear it"),
    ("tower upright outer", "blue-tower", r"^GE-26502-01: Tower Upright Outer$", "TOWER upright. The bumper berths against the pair"),
    ("tower upright inner", "blue-tower", r"^GE-26502-02: Tower Upright Inner$", "TOWER upright. The bumper berths against the pair"),
    ("tower rung", "blue-tower", r"^GE-26503: Tower Rung$", "TOWER rung. The hooks seat on the low one at 685.8 mm"),
    ("tower lower plastic", "blue-tower", r"^GE-26505: Tower Lower Plastic$", "Panel between the uprights below the low rung"),
]


def _tool():
    spec = importlib.util.spec_from_file_location("official_tessellate", FOLDER / "tessellate.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


def _solids(shape):
    out, explorer = [], TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        out.append(explorer.Current())
        explorer.Next()
    return out


def fixtures():
    """name -> (placed solid, basis). Names are numbered in the order of the part centres (x, then y, then z)."""
    tool = _tool()
    record = json.loads((FOLDER / "official-field.json").read_text(encoding="utf-8"))
    move = gp_Trsf()
    move.SetTranslation(gp_Vec(*SHOT_POSE))
    found = {stem: [] for stem, *_ in SELECTION}
    for file in sorted({f for _, f, _, _ in SELECTION}):
        doc, root = tool.read(FOLDER / f"{file}.step")
        wanted = [(stem, re.compile(pattern), what) for stem, f, pattern, what in SELECTION if f == file]

        def walk(label, loc, name):
            kids = Sequence_TDF_Label()
            tool.ST.GetComponents_s(label, kids)
            if kids.Length():
                for i in range(1, kids.Length() + 1):
                    child, ref = kids.Value(i), TDF_Label()
                    if tool.ST.GetReferredShape_s(child, ref):
                        walk(ref, loc.Multiplied(tool.ST.GetLocation_s(child)), tool.label_name(ref))
                return
            for stem, pattern, what in wanted:
                if pattern.search(name):
                    placed = tool.ST.GetShape_s(label).Moved(loc).Moved(TopLoc_Location(move))
                    for solid in _solids(placed):
                        # Bake the placement into the solid's own coordinates (a rigid copy), so the STEP writer stores one named solid.
                        baked = BRepBuilderAPI_Transform(solid.Located(TopLoc_Location()), solid.Location().Transformation(), True).Shape()
                        found[stem].append((tool.bounds(baked), baked, name, what, file))
        walk(root, TopLoc_Location(), tool.label_name(root))
    out = {}
    source = record["source"]
    for stem, rows in found.items():
        assert rows, f"No official part for {stem}"
        rows.sort(key=lambda r: [round((r[0][a] + r[0][a + 3]) / 2, 1) for a in range(3)])
        for i, (b, solid, product, what, file) in enumerate(rows, 1):
            name = stem if len(rows) == 1 else f"{stem} {i}"
            out[name] = (solid, f"{what}. FIRST official field model, part '{product}' from cad/field/official/{file}.step ({source['file']}, "
                                f"{source['edition']}), geometry as published, placed in the robot datum at the shot pose: official millimetres "
                                f"shifted by ({SHOT_POSE[0]:g}, {SHOT_POSE[1]:g}, {SHOT_POSE[2]:g})")
    return out


if __name__ == "__main__":
    for name, (solid, basis) in fixtures().items():
        print(name, _tool().bounds(solid))
