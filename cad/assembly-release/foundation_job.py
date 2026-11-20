"""Prepare the versioned shop recipe separately from permission-sensitive supplier files."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

from swerve import build as saddle_stack, layout
from frame import build as frame
from module_views import build as public_modules

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from component_palette import resolve_palette


def recipe():
    saddle, hardware, rail_holes, stacks = saddle_stack()
    parts = {**frame(), **saddle, **hardware, **public_modules()}
    for name, operations in rail_holes.items():
        parts[name]["features"].extend(operations)
    for name, row in parts.items():
        # Part identity persists across native documents; each independently procured physical item has a separate owner.
        row["identity"] = (
            "R26-FDN-" + hashlib.sha256(("part/" + name).encode()).hexdigest()[:16]
        )
        row.setdefault("instance", row["identity"])
    return dict(
        schema="rebuilt-foundation/v1",
        archiveBase="cad/tower-lift/tower-l1.f3d",
        archiveBaseSha256="7c4a6210bcd23540999d3412107e6a8cf72f30596250f113314b35cbf66eb941",
        parts=parts,
        stacks=stacks,
        sites=layout()[3],
        palette=resolve_palette(ROOT),
    )


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("output", type=Path)
    args = cli.parse_args()
    args.output.write_text(json.dumps(recipe(), indent=2) + "\n", encoding="utf8")
