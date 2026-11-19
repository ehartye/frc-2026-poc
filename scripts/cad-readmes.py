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


def run(root, update, template):
    config = json.loads((root / "cad-showcase.json").read_text(encoding="utf-8-sig"))
    folder = root / "docs/robot/cad"
    receipt = json.loads((folder / "receipt.json").read_text(encoding="utf-8"))
    if receipt["source"] != config["source"]:
        raise ValueError("Selected CAD differs from export. Regenerate the still and mesh.")
    checked(root / config["source"], receipt["sourceSha256"])
    checked(folder / "assembly.png", receipt["imageSha256"])
    mesh = checked(folder / "assembly.stl.gz", receipt["meshSha256"])
    fields = dict(title=html.escape(config["title"]), scope=html.escape(config["scope"]),
                  facts=f'{receipt["solids"]:,} solids · {receipt["triangles"]:,} triangles · {receipt["chordMm"]} mm chord setting',
                  bounds=json.dumps(receipt["nativeBounds"]), mesh=base64.b64encode(mesh).decode("ascii"))
    viewer = re.sub(r"\{\{(\w+)\}\}", lambda match: fields[match[1]], template.read_text(encoding="utf-8"))
    output(folder / "index.html", viewer.encode(), update)
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
        title = config["title"]
        image = link(folder / "assembly.png")
        target = config.get("viewerUrl") or link(folder / "index.html")
        source = link(root / config["source"])
        block = (f'{START}\n[![{title}]({image})]({target})\n\n'
                 f'**Project CAD · {title}.** {config["scope"]} '
                 f'[Source STEP · {receipt["sourceSha256"][:10]}]({source}) · [Rotate the model]({target})\n{END}')
        merged = "".join(lines[:heading+1]).rstrip("\n") + "\n\n" + block + "\n\n" + "".join(lines[heading+1:]).lstrip("\n")
        if b"\r\n" in original:
            merged = merged.replace("\n", "\r\n")
        bom = b"\xef\xbb\xbf" if original.startswith(b"\xef\xbb\xbf") else b""
        output(file, bom + merged.encode(errors="surrogateescape"), update)
    print(f"Verified CAD source, mesh, still, viewer and {len(names)} README files.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--template", type=Path, default=Path(__file__).resolve().parents[1] / "templates/cad-orbit.html")
    args = parser.parse_args()
    run(args.root.resolve(), args.update, args.template)

