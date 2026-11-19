"""Verify project-owned STEP appearance assignments and the viewer's triangle ranges."""

import argparse
from collections import Counter
import hashlib
import gzip
import struct
import json
import math
import re
from pathlib import Path

from component_palette import palette_digest, resolve_palette


def backdrop_colors(config):
    if "backdrop" not in config:
        return None
    backdrop = config["backdrop"]
    if (not isinstance(backdrop, dict) or set(backdrop) != {"center", "edge"}
            or not all(isinstance(color, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", color)
                       for color in backdrop.values())):
        raise ValueError("CAD backdrop needs center and edge sRGB colors")
    return {key: backdrop[key].upper() for key in ("center", "edge")}


def load_assignments(root, relative, source_hash):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("Expected a project-relative appearance manifest")
    path = (root / relative).resolve()
    path.relative_to(root.resolve())
    raw = path.read_bytes()
    config = json.loads(raw.decode("utf-8-sig"))
    if (
        config.get("schema") != "agent-frc/assembly-appearances@1"
        or config.get("sourceSha256") != source_hash
    ):
        raise ValueError("Appearance assignments require the same source STEP")
    colors = resolve_palette(root)
    rows = config.get("solids")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Expected one appearance assignment per source solid")
    ids = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid solid appearance assignment")
        ident, role = row.get("id"), row.get("role")
        if not isinstance(ident, str) or not ident.strip() or ident in ids:
            raise ValueError(
                "Missing or repeated solid identity in appearance assignments"
            )
        ids.add(ident)
        if not isinstance(role, str) or role not in colors:
            raise ValueError(f"Unknown appearance role for {ident}: {role}")
        if "boundsMm" in row:
            bounds = row["boundsMm"]
            if (
                not isinstance(bounds, list)
                or len(bounds) != 6
                or not all(type(x) in (int, float) and math.isfinite(x) for x in bounds)
                or any(bounds[i] > bounds[i + 3] for i in range(3))
            ):
                raise ValueError(f"Invalid solid bounds for {ident}")
    binding = dict(
        file=relative,
        sha256=hashlib.sha256(raw).hexdigest(),
        paletteSha256=palette_digest(colors),
    )
    return rows, colors, binding


def validated_groups(root, record, packed):
    appearance = record.get("appearances")
    if record.get("schema") != "agent-frc/cad-still@2" or not isinstance(
        appearance, dict
    ):
        raise ValueError("Missing appearance receipt")
    rows, colors, binding = load_assignments(
        root, appearance.get("file"), record["sourceSha256"]
    )
    if any(appearance.get(key) != value for key, value in binding.items()):
        raise ValueError(
            "Appearance manifest or resolved palette changed; regenerate CAD"
        )
    counts = Counter(row["role"] for row in rows)
    groups = appearance.get("groups")
    if not isinstance(groups, list) or len(groups) != len(counts):
        raise ValueError("Incomplete CAD appearance groups")
    for group, (role, count) in zip(groups, counts.items()):
        if (
            not isinstance(group, dict)
            or group.get("role") != role
            or group.get("color") != colors[role]
            or group.get("solids") != count
            or type(group.get("triangles")) is not int
            or group["triangles"] <= 0
        ):
            raise ValueError("CAD appearance group disagrees with its assignment")
    if len(rows) != record.get("solids") or sum(
        group["triangles"] for group in groups
    ) != record.get("triangles"):
        raise ValueError("CAD appearance ranges do not cover the exported assembly")
    with gzip.open(packed, "rb") as facets:
        header = facets.read(84)
        if (
            len(header) != 84
            or struct.unpack_from("<I", header, 80)[0] != record["triangles"]
        ):
            raise ValueError("CAD mesh header does not cover the appearance groups")
        for group in groups:
            remaining = group["triangles"] * 50
            digest = hashlib.sha256()
            while remaining:
                chunk = facets.read(min(remaining, 1 << 20))
                if not chunk:
                    raise ValueError("Incomplete CAD appearance group")
                remaining -= len(chunk)
                digest.update(chunk)
            if digest.hexdigest() != group.get("facetsSha256"):
                raise ValueError("CAD color range does not match the exported facets")
        if facets.read(1):
            raise ValueError("Unassigned CAD facets")
    solid_roles = {row["role"] for row in rows if row.get("representation") != "appearance-overlay"}
    ranges = []
    for group in groups:
        entry = [group["triangles"], group["color"], group["role"]]
        if group["role"] not in solid_roles:
            entry.append("appearance-overlay")
        ranges.append(entry)
    return ranges


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            validated_groups(
                args.project.resolve(),
                json.loads(args.receipt.read_bytes()),
                args.receipt.with_name("assembly.stl.gz"),
            )
        )
    )
