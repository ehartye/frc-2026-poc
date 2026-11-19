"""Recreate the single-piece counter trials from a registered project-local field mesh."""

import argparse
from pathlib import Path
from counter_witness import run
from qualify_counter import qualify, write

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("cache", type=Path)
    cache = p.parse_args().cache
    cases = [
        ("r2c-clear-corridor-coarse.json", 0.25, 0.0005, [(1, 1)]),
        ("r2c-clear-corridor.json", 0.25, 0.00025, [(1, 1), (0, 0)]),
        ("r2c-clear-corridor-refined.json", 0.25, 0.000125, [(1, 1)]),
        ("r2c-qualified-fine.json", 0.0, 0.00025, [(0, 0), (1, 0), (0, 1)]),
    ]
    for filename, offset, step, speeds in cases:
        write(cache / filename, run(cache, 1, step, speeds, 4.0, offset))
    qualify(cache)
