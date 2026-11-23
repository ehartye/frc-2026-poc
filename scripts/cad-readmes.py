"""Check or refresh the CAD still at the top of every project README.

Without options this is the README check: each project-owned README shows the still block directly below its title,
the image it shows exists, and its caption names the current design and its status. It compares no bytes: git records
what the image and its source were. --update rewrites every block.

The still links to the one viewer of the design: its design review page. cad-showcase.json names the shown design:
title, scope and status (in-progress, effective, superseded or withdrawn), and optionally design (its name, version or
release ID), still (the image, docs/robot/cad/assembly.png by default), source, and review (the project-relative folder
or page of the design review) or viewerUrl (its address). Without either, the still links to the review of the current
detailed design, else of the current preliminary design."""
import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from urllib.parse import quote, unquote

from atomic_file import write_atomic

START = "<!-- cad-still -->"
END = "<!-- /cad-still -->"
STATUSES = ("in-progress", "effective", "superseded", "withdrawn")


def output(file, data, update):
    previous = file.read_bytes() if file.exists() else None
    if previous == data:
        return
    if not update:
        raise ValueError(f"Stale or missing: {file}")
    write_atomic(file, data)


def selection(root):
    """The selected design as the caption names it: the configuration, and the design name, version or release ID."""
    config = json.loads((root / "cad-showcase.json").read_text(encoding="utf-8-sig"))
    design = config.get("design") or config.get("title")
    if not (isinstance(design, str) and design.strip()):
        raise ValueError("Name the shown design in cad-showcase.json: set title, or design to its name, version or release ID")
    if config.get("status") not in STATUSES:
        raise ValueError("Set status in cad-showcase.json to the shown design's status: " + ", ".join(STATUSES))
    return config, design.strip()


def current_of(index_file, key):
    """The design a status index opens, when the index lists it."""
    try:
        index = json.loads(index_file.read_text(encoding="utf-8-sig"))
        current = index.get("current")
        return current if isinstance(current, str) and current in index.get(key, []) else None
    except (OSError, ValueError, AttributeError, TypeError):
        return None


def review_of(root, config):
    """Where the still links: the one viewer of the shown design. Returns (target, words); target is a URL, a file or None.

    An explicit review or viewerUrl wins. Otherwise the review of the current detailed design, then of the current
    preliminary design. A project that still holds a page built by the retired orbit viewer keeps linking to it."""
    words = "Open the design review"
    if config.get("viewerUrl"):
        return config["viewerUrl"], words
    if config.get("review"):
        page = (root / config["review"]).resolve()
        if not page.is_relative_to(root):
            raise ValueError("Name the design review in cad-showcase.json as a project-relative folder or page")
        return (page / "index.html" if page.is_dir() or not page.suffix else page), words
    detailed, preliminary = root / "docs/detailed-design", root / "docs/preliminary-design"
    design, release = current_of(detailed / "designs.json", "designs"), current_of(preliminary / "releases.json", "releases")
    for page in ([detailed / "designs" / design / "index.html"] if design else []) + ([preliminary / "releases" / release / "index.html"] if release else []):
        if page.is_file():
            return page, words
    earlier = root / "docs/robot/cad/index.html"
    return (earlier, "Rotate the model") if earlier.is_file() else (None, words)


def readmes(root, update):
    """Check the still block of every project README, or rewrite it. Returns the number of README files.

    The check reads the block only: where it sits, that its image exists and what its caption names. It never
    compares the image, its source or a palette with a recorded digest."""
    config, design = selection(root)
    review, words = review_of(root, config) if update else (None, "")
    still = (root / config.get("still", "docs/robot/cad/assembly.png")).resolve()
    if update and not (still.is_relative_to(root) and still.is_file()):
        raise ValueError("No CAD still image at " + str(config.get("still", "docs/robot/cad/assembly.png")) + ". Render it, or name it as still in cad-showcase.json")
    paths = subprocess.check_output(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=root)
    names = sorted(set(n.decode() for n in paths.split(b"\0") if n and Path(n.decode()).name.lower() in ("readme.md", "readme")))
    for name in names:
        file = root / name
        if not file.exists():
            continue
        original = file.read_bytes()
        text = original.decode("utf-8-sig", errors="surrogateescape").replace("\r\n", "\n")
        if not update:
            check_block(file, name, text, design, config["status"])
            continue
        text = re.sub(r"\n*" + START + ".*?" + END + r"\n*", "\n\n", text, flags=re.S)
        lines = text.splitlines(keepends=True)
        heading = next((i for i, line in enumerate(lines) if line.startswith("# ")), None)
        if heading is None:
            raise ValueError(f"README needs a title: {name}")
        def link(target):
            return quote(Path(os.path.relpath(target, file.parent)).as_posix(), safe="/.-_")
        title = config["title"]
        image = link(still)
        target = review if isinstance(review, str) else link(review) if review else None
        source = f' [Source STEP]({link(root / config["source"])})' if config.get("source") else ""
        shown = title if design == title else f"{title} · {design}"
        picture = f'![{title}]({image})'
        # Without a published review the still stands alone; the next --update links it.
        block = (f'{START}\n{f"[{picture}]({target})" if target else picture}\n\n'
                 f'**Project CAD · {shown} · {config["status"]}.** {config["scope"]}'
                 f'{" ·".join(part for part in (source, f" [{words}]({target})" if target else "") if part)}\n{END}')
        merged = "".join(lines[:heading+1]).rstrip("\n") + "\n\n" + block + "\n\n" + "".join(lines[heading+1:]).lstrip("\n")
        if b"\r\n" in original:
            merged = merged.replace("\n", "\r\n")
        bom = b"\xef\xbb\xbf" if original.startswith(b"\xef\xbb\xbf") else b""
        output(file, bom + merged.encode(errors="surrogateescape"), update)
    return len(names)


def check_block(file, name, text, design, status):
    """One README: the still block sits directly below the title, shows an image that exists and names the design and status."""
    lines = text.splitlines()
    heading = next((i for i, line in enumerate(lines) if line.startswith("# ")), None)
    if heading is None:
        raise ValueError(f"README needs a title: {name}")
    below = next((line for line in lines[heading + 1:] if line.strip()), "")
    found = re.search(START + "(.*?)" + END, text, flags=re.S)
    fix = "Run cad-readmes.py --update"
    if not found or below.strip() != START:
        raise ValueError(f"No CAD still block directly below the title of {name}. {fix}")
    image = re.search(r"!\[[^\]]*\]\(([^)\s]+)\)", found[1])
    if not image or not (file.parent / unquote(image[1])).is_file():
        raise ValueError(f"The CAD still of {name} shows no image file that exists" + (": " + image[1] if image else "") + f". {fix}")
    caption = found[1][image.end():]
    if design not in caption or status not in caption:
        raise ValueError(f"The CAD still caption of {name} does not name the current design ({design}) and its status ({status}). {fix}")


def run(root, update, verify_export=False):
    count = readmes(root, update)
    if verify_export:
        print("Note: --verify-export does nothing now. The orbit view it compared is retired; the design review page is the one viewer. Remove the option.")
    if update:
        review, _ = review_of(root, selection(root)[0])
        print(f"Rewrote the still of {count} README files. " + ("The still links to the design review." if review else
              "No design review is published yet, so the still links nowhere: stage the design, or set review in cad-showcase.json, and run --update again."))
    else:
        print(f"Checked the still of {count} README files: block below the title, image present, design and status named. No bytes compared.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--update", action="store_true", help="Rewrite every README still block")
    parser.add_argument("--verify-export", action="store_true", help="Retired with the orbit view; accepted and ignored")
    parser.add_argument("--template", type=Path, help="Retired with the orbit view; accepted and ignored")
    args = parser.parse_args()
    run(args.root.resolve(), args.update, args.verify_export)
