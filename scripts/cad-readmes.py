"""Refresh or verify the shared CAD view and every project README using only Python and Git."""
import argparse
import base64
import hashlib
import html
import json
import os
import re
import subprocess
from pathlib import Path
from urllib.parse import quote

START = "<!-- cad-still -->"
END = "<!-- /cad-still -->"


def checked(path, expected):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f"Changed CAD evidence: {path}")
    return data


def output(file, data, update):
    previous = file.read_bytes() if file.exists() else None
    if previous == data:
        return
    if not update:
        raise ValueError(f"Stale or missing: {file}")
    file.write_bytes(data)


STATUS_WORDS = {"in-progress": "in progress", "effective": "effective"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def preliminary_feature(root, config, update):
    """Return the README feature when the detailed design index shows no current detailed design.

    A current detailed design keeps the README still. Otherwise each README features the current preliminary
    design release, with the still preliminary-still.py rendered from that release's published review scene.
    """
    listing = root / "docs/detailed-design/designs.json"
    if not listing.exists():
        return None
    try:
        index = json.loads(listing.read_bytes())
        statuses, designs = index["designStatus"], index["designs"]
        if not isinstance(statuses, dict) or not isinstance(designs, list):
            raise TypeError
    except (ValueError, KeyError, TypeError):
        raise ValueError("Unreadable detailed design index: docs/detailed-design/designs.json") from None
    if index.get("current") is not None or any(statuses.get(name) in ("in-progress", "effective") for name in designs):
        return None
    served = root / "docs/preliminary-design"
    releases = json.loads((served / "releases.json").read_bytes())
    release = releases.get("current")
    status = releases.get("designStatus", {}).get(release, "in-progress")
    if release not in releases["releases"] or status not in STATUS_WORDS:
        raise ValueError("The README needs a current in-progress or effective preliminary design release")
    image = root / "docs/robot" / f"preliminary-{release}.png"
    if not image.exists() or not image.with_suffix(".json").exists():
        raise ValueError("Render the README still of " + release + " with preliminary-still.py.")
    record = json.loads(image.with_suffix(".json").read_bytes())
    folder = served / "releases" / release
    if (record["release"] != release or record["imageSha256"] != digest(image)
            or record["releaseRecordSha256"] != digest(folder / "release.json")
            or record["receiptSha256"] != digest(folder / "receipt.json")
            or record["sceneSha256"] != digest(folder / "review-scene.json.gz")):
        raise ValueError("The preliminary still differs from the current release. Regenerate it with preliminary-still.py.")
    caption = record["caption"]
    return dict(image=image, heading=f"Preliminary design · {STATUS_WORDS[status]} · {release}",
                review=config["siteUrl"] + "preliminary-design/", receipt=folder / "receipt.json",
                receiptSha256=record["receiptSha256"],
                text=f'{caption["title"]}. {caption["pose"]} {caption["scope"]}')


def run(root, update, template):
    config = json.loads((root / "cad-showcase.json").read_text(encoding="utf-8-sig"))
    folder = root / "docs/robot/cad"
    receipt = json.loads((folder / "receipt.json").read_text(encoding="utf-8"))
    if receipt["source"] != config["source"]:
        raise ValueError("Selected CAD differs from export. Regenerate the still and mesh.")
    checked(root / config["source"], receipt["sourceSha256"])
    checked(folder / "assembly.png", receipt["imageSha256"])
    mesh = checked(folder / "assembly.stl.gz", receipt["meshSha256"])
    layout = receipt["nativeBounds"]
    if "appearances" in config or receipt.get("schema") == "agent-frc/cad-still@2":
        from cad_appearances import validated_groups
        if not config.get("appearances") or config["appearances"] != receipt.get("appearances", {}).get("file"):
            raise ValueError("Selected appearance manifest differs from the export")
        layout = dict(bounds=layout, groups=validated_groups(root, receipt, folder / "assembly.stl.gz"))
    elif receipt.get("schema") != "agent-frc/cad-still@1":
        raise ValueError("Unknown CAD receipt schema")
    if "backdrop" in config or "backdrop" in receipt:
        from cad_appearances import backdrop_colors
        backdrop = backdrop_colors(config)
        if not backdrop or backdrop != backdrop_colors(receipt):
            raise ValueError("CAD backdrop changed. Regenerate the still and mesh.")
        if isinstance(layout, list):
            layout = {"bounds": layout}
        layout["backdrop"] = backdrop
    fields = dict(title=html.escape(config["title"]), scope=html.escape(config["scope"]),
                  facts=f'{receipt["solids"]:,} solids · {receipt["triangles"]:,} triangles · {receipt["chordMm"]} mm chord setting',
                  bounds=json.dumps(layout), mesh=base64.b64encode(mesh).decode("ascii"))
    viewer = re.sub(r"\{\{(\w+)\}\}", lambda match: fields[match[1]], template.read_text(encoding="utf-8"))
    output(folder / "index.html", viewer.encode(), update)
    featured = config["featuredAssembly"]
    hashes = json.loads((root / featured["receipt"]).read_text(encoding="utf-8"))["sha256"]
    for role in ("archive", "mesh", "source", "still"):
        asset = root / featured[role]
        checked(asset, hashes[asset.name])
    feature = preliminary_feature(root, config, update)
    paths = subprocess.check_output(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=root)
    names = sorted(set(n.decode() for n in paths.split(b"\0") if n and Path(n.decode()).name.lower() in ("readme.md", "readme")))
    for name in names:
        file = root / name
        if not file.exists():
            continue
        original = file.read_bytes()
        text = original.decode("utf-8-sig", errors="surrogateescape").replace("\r\n", "\n")
        text = re.sub(r"\n*" + START + ".*?" + END + r"\n*", "\n\n", text, flags=re.S)
        lines = text.splitlines(keepends=True)
        heading = next((i for i, line in enumerate(lines) if line.startswith("# ")), None)
        if heading is None:
            raise ValueError(f"README needs a title: {name}")
        def link(target):
            return quote(Path(os.path.relpath(target, file.parent)).as_posix(), safe="/.-_")
        title = featured["title"]
        image = link(root / featured["still"])
        target = featured["viewerUrl"]
        step = link(root / featured["source"])
        archive = link(root / featured["archive"])
        block = (f'{START}\n[![{title}]({image})]({target})\n\n'
                 f'**Project CAD · {title}.** {featured["scope"]} '
                 f'[Editable Fusion assembly]({archive}) · [STEP]({step}) · [Rotate the model]({target})\n{END}')
        if feature:
            block = (f'{START}\n[![{feature["heading"]}]({link(feature["image"])})]({feature["review"]})\n\n'
                     f'**{feature["heading"]}.** {feature["text"]} [Open the review]({feature["review"]}) · '
                     f'[Layout-checked receipt · {feature["receiptSha256"][:10]}]({link(feature["receipt"])})\n{END}')
        merged = "".join(lines[:heading+1]).rstrip("\n") + "\n\n" + block + "\n\n" + "".join(lines[heading+1:]).lstrip("\n")
        if b"\r\n" in original:
            merged = merged.replace("\n", "\r\n")
        bom = b"\xef\xbb\xbf" if original.startswith(b"\xef\xbb\xbf") else b""
        output(file, bom + merged.encode(errors="surrogateescape"), update)
    shown = feature["heading"] if feature else featured["title"]
    print(f"Verified CAD source, mesh, still, viewer and {len(names)} README files featuring {shown}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--template", type=Path, default=Path(__file__).resolve().parents[1] / "templates/cad-orbit.html")
    args = parser.parse_args()
    run(args.root.resolve(), args.update, args.template)
