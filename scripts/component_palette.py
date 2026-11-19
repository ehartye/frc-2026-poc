"""Resolve the CAD viewing palette for one robot project using only the standard library."""
import argparse
import hashlib
import json
import re
from pathlib import Path


DEFAULT = Path(__file__).with_name("cad-color-convention.json")
OVERRIDE = Path("cad/component-palette.json")
SCHEMA = "agent-frc/component-palette@1"


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Repeated palette field: {key}")
        result[key] = value
    return result


def resolve_palette(project_root):
    root = Path(project_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Expected a project directory")
    default = json.loads(DEFAULT.read_text(encoding="utf-8"))
    colors = {role["id"]: role["color"] for role in default["roles"]}
    override = root / OVERRIDE
    if override.exists() or override.is_symlink():
        override = override.resolve(strict=True)
        override.relative_to(root)
        spec = json.loads(override.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_keys)
        if not isinstance(spec, dict) or spec.get("schema") != SCHEMA or set(spec) != {"schema", "colors"}:
            raise ValueError(f"Expected schema {SCHEMA} and colors in {OVERRIDE}")
        if not isinstance(spec["colors"], dict):
            raise ValueError("Expected a mapping from component roles to sRGB colors")
        colors.update(spec["colors"])
    for key, value in colors.items():
        if not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", key):
            raise ValueError(f"Invalid component role: {key}")
        if not isinstance(value, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
            raise ValueError(f"Expected a six-digit sRGB color for {key}")
    return {key: value.upper() for key, value in sorted(colors.items())}


def palette_digest(colors):
    canonical = json.dumps(colors, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    args = parser.parse_args()
    try:
        resolved = resolve_palette(args.project)
        print(json.dumps({"schema": SCHEMA, "colors": resolved}, indent=2))
    except (ValueError, OSError) as error:
        parser.exit(1, f"{error}\n")
