"""Conservative parked-to-hung obstacle screen at the recorded poses, in source millimetres."""

import json, math, sys
from itertools import product
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "cad/tower-lift"))
from recipe import parts


def check(components=None):
    rows = json.loads((HERE / "motion.json").read_bytes())
    nominal = json.loads((HERE / "support.json").read_bytes())[0]
    all_parts = (
        components
        or json.loads((ROOT / "cad/tower-lift/appearances.json").read_bytes())["solids"]
    )
    stage = {p["name"]: p["stage"] for p in parts()}
    field = json.loads((HERE / "field.json").read_bytes())["sides"]["blue"]
    field_bounds = []
    for obj in field:
        name = obj["name"]
        q = [
            v - (nominal["startDatumX"] * 1000, nominal["startDatumY"] * 1000, 0)[i % 3]
            for i, v in enumerate(obj["boundsMm"])
        ]
        if "Base Bottom" in name:
            q[5] = obj["fieldward145mmTopMm"]
        field_bounds.append((name, q))
    exceptions = {}
    # Back straight into the registered pose, stowed and at zero yaw. The broader field
    # rehearsal supplies navigation/traffic; this last 350 mm tests the actual dock volume.
    entry = [
        dict(rows[0], t=-i / 20, x=rows[0]["x"] + i * 0.0175) for i in range(20, 0, -1)
    ]
    for row in entry + rows:
        co, si = math.cos(row["pitch"]), math.sin(row["pitch"])
        for part in all_parts:
            name = part["id"]
            st = stage.get(name, "fixed")
            bb = part["boundsMm"][:]
            for i in (0, 3):
                bb[i] -= 1000 * row["deploy"] if st == "hooks" else 0
            for i in (2, 5):
                bb[i] -= 1000 * row["down"] if st in ("hooks", "elevator") else 0
            corners = [
                (
                    1000 * row["x"] + co * x - si * (z - 320),
                    1000 * row["z"] + 320 + si * x + co * (z - 320),
                )
                for x, z in product((bb[0], bb[3]), (bb[2], bb[5]))
            ]
            xs, zs = zip(*corners)
            a = [min(xs), bb[1], min(zs), max(xs), bb[4], max(zs)]
            for fname, q in field_bounds:
                if min(a[4], q[4]) - max(a[1], q[1]) < 0.01:
                    continue
                if "Tower Rung" in fname:
                    cx = (q[0] + q[3]) / 2 - 1000 * row["x"]
                    cz = (q[2] + q[5]) / 2 - 320 - 1000 * row["z"]
                    rx = co * cx + si * cz
                    rz = -si * cx + co * cz + 320
                    depth = (q[5] - q[2]) / 2 - math.hypot(
                        rx - min(bb[3], max(bb[0], rx)), rz - min(bb[5], max(bb[2], rz))
                    )
                    if name.endswith("crown hook"):
                        continue  # Actual three-face throat contact is in support.py.
                else:
                    depth = min(
                        min(a[i + 3], q[i + 3]) - max(a[i], q[i]) for i in range(3)
                    )
                    if name == "rear blue bumper" and "Upright" in fname:
                        continue
                if depth > 0.03:
                    key = name + " / " + fname
                    old = exceptions.get(key)
                    if old is None or depth > old["overlapMm"]:
                        exceptions[key] = dict(
                            timeS=row["t"], overlapMm=round(depth, 5)
                        )
    return dict(
        samples=len(rows),
        entrySamples=len(entry),
        entryTravelMm=350,
        stepS=rows[1]["t"],
        role="Conservative occupied component boxes against registered field boxes and finite rung cylinders; explicit compliant hook-rung and rear-bumper-upright contacts are solved separately.",
        unexpected=exceptions,
    )


if __name__ == "__main__":
    result = check()
    (HERE / "field-clearance.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf8", newline="\n"
    )
    print(result)
