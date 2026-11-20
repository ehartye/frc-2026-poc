"""Reject any unsound shop feature, disconnected article, or mismatched public SKU ownership."""

import argparse
import json
from pathlib import Path

from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer

from offline import machine


def run(recipe):
    job = json.loads(recipe.read_bytes())
    errors = []
    for name, article in job["parts"].items():
        body = None
        for index, feature in enumerate(article["features"], 1):
            body = machine([feature], body)
            it = TopExp_Explorer(body, TopAbs_SOLID)
            count = 0
            while it.More():
                count += 1
                it.Next()
            if count != 1 or not BRepCheck_Analyzer(body).IsValid():
                errors.append((name, index, count))
        if article["role"] not in job["palette"]:
            errors.append((name, "unknown role"))
    if errors:
        raise ValueError(errors)
    return len(job["parts"])


if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("recipe", type=Path)
    print(f"{run(a.parse_args().recipe)} material-assigned articles validated")
