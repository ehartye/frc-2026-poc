"""Render or verify the README still of a published preliminary design release.

The still is drawn from the release's public review scene, the same block-level solids and colors the
interactive review shows, with the offscreen renderer the detailed CAD still uses. It needs no STEP.
"""
import argparse
import gzip
import hashlib
import importlib.util
import json
import struct
from pathlib import Path
from tempfile import TemporaryDirectory

SCHEMA = "frc-2026-poc/preliminary-still@1"
# Clearance gauges are tools, not robot material; field fixtures are not the robot. In a park case the
# payload has been delivered, so it is hidden with the field.
HIDDEN_CATEGORIES = ("reserved-space",)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def paths(root, release):
    served = root / "docs/preliminary-design/releases" / release
    return served, root / "docs/robot" / f"preliminary-{release}.png", root / "docs/robot" / f"preliminary-{release}.json"


def facets(scene, case, pose):
    """Group the shown bodies' triangles by display color, placed by the selected pose of the case."""
    grouped, shown, hidden = {}, [], []
    for name in sorted(case["bodies"]):
        body, placed = scene["bodies"][name], case["bodies"][name]
        if (body["fixture"] or body["category"] in HIDDEN_CATEGORIES or name in case["removed"]
                or case["stage"] == "park" and body["role"] == "payload"):
            hidden.append(name)
            continue
        shown.append(name)
        m = placed["matrices"][min(pose, len(placed["matrices"]) - 1) if pose >= 0 else -1]
        mesh = scene["meshes"][placed["mesh"]]
        points = [tuple(m[r * 4] * x + m[r * 4 + 1] * y + m[r * 4 + 2] * z + m[r * 4 + 3] for r in range(3))
                  for x, y, z in mesh["v"]]
        rows = grouped.setdefault(body["color"].lower(), [])
        for a, b, c in mesh["f"]:
            rows.append((points[a], points[b], points[c]))
    return grouped, shown, hidden


def write_stl(grouped, file):
    """One binary STL with the triangles of each color contiguous, in the order the renderer colors them."""
    groups = []
    with file.open("wb") as out:
        out.write(bytes(80) + struct.pack("<I", sum(len(rows) for rows in grouped.values())))
        for color in sorted(grouped):
            for a, b, c in grouped[color]:
                u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
                n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
                size = sum(x * x for x in n) ** .5 or 1
                out.write(struct.pack("<12fH", *(x / size for x in n), *a, *b, *c, 0))
            groups.append(dict(color=color, triangles=len(grouped[color])))
    return groups


def expected(root, release, case_id, pose):
    served, image, record = paths(root, release)
    packed = (served / "review-scene.json.gz").read_bytes()
    scene = json.loads(gzip.decompress(packed))
    issued = json.loads((served / "release.json").read_bytes())
    if issued["release"] != release or issued["phase"] != "preliminary-design" or issued["status"] != "layout-checked":
        raise ValueError("The still needs a layout-checked preliminary design release")
    if sha((served / "receipt.json").read_bytes()) != issued["receipt"]["sha256"]:
        raise ValueError("The published receipt differs from the release record")
    case = next((c for c in scene["cases"] if c["id"] == case_id), None)
    if case is None or case["kind"] != "nominal" or case["status"] != "pass":
        raise ValueError("Pose the still in a passing nominal case of the release")
    grouped, shown, hidden = facets(scene, case, pose)
    receipt = dict(schema=SCHEMA, release=release, issue=issued["issue"], phase=issued["phase"],
                   releaseRecordSha256=sha((served / "release.json").read_bytes()),
                   receiptSha256=issued["receipt"]["sha256"], sceneSha256=sha(packed),
                   scene=f"docs/preliminary-design/releases/{release}/review-scene.json.gz",
                   case=case_id, pose=pose, shownBodies=len(shown), hiddenBodies=hidden,
                   triangles=sum(len(rows) for rows in grouped.values()),
                   renderer="scripts/export-showcase-cad.py render, offscreen VTK, parallel projection")
    return grouped, receipt, image, record


def run(root, release, case_id, pose, update):
    grouped, receipt, image, record = expected(root, release, case_id, pose)
    # The caption (title, alt text, pose and scope sentences) is authored in the record and kept across renders.
    caption = json.loads(record.read_bytes()).get("caption") if record.exists() else None
    if not caption or sorted(caption) != ["alt", "pose", "scope", "title"]:
        raise ValueError(f"Author the caption (title, alt, pose, scope) in {record.name} first")
    receipt["caption"] = caption
    if update:
        spec = importlib.util.spec_from_file_location("showcase_cad", Path(__file__).with_name("export-showcase-cad.py"))
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        backdrop = json.loads((root / "cad-showcase.json").read_text(encoding="utf-8-sig")).get("backdrop")
        with TemporaryDirectory() as tmp:
            mesh = Path(tmp) / "layout.stl"
            groups = write_stl(grouped, mesh)
            _, triangles = tool.render(mesh, image, groups, backdrop)
        if triangles != receipt["triangles"]:
            raise ValueError("The rendered still lost triangles")
        receipt["imageSha256"] = sha(image.read_bytes())
        record.write_bytes((json.dumps(receipt, indent=2, ensure_ascii=False) + "\n").encode())
    saved = json.loads(record.read_bytes())
    receipt["imageSha256"] = sha(image.read_bytes())
    if saved != receipt:
        raise ValueError("The preliminary still or its record is stale. Rerun with --update.")
    print(f"Verified the {release} still against its review scene, release record and receipt.")
    return saved


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("release", nargs="?", help="defaults to the current release in the published index")
    parser.add_argument("--case", default="park-lower")
    parser.add_argument("--pose", type=int, default=-1, help="pose index in the case; -1 is its final pose")
    parser.add_argument("--update", action="store_true", help="render the still; needs the CAD Python environment")
    args = parser.parse_args()
    root = args.root.resolve()
    current = json.loads((root / "docs/preliminary-design/releases.json").read_bytes())["current"]
    run(root, args.release or current, args.case, args.pose, args.update)
