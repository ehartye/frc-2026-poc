"""Trim FIRST's official field STEP to the fixtures this project's missions interact with.

Reads the official whole-field STEP (not kept in this repository), checks its SHA-256 against selection.json and,
for each fixture listed there, writes <id>.step: the official root product, the selected top-level occurrences and
everything below them. The records are copied from the official file as written, so product names, part geometry,
colours and each occurrence's official field placement are unchanged. Only two list records are new: the
presentation list and the product category that name the kept items.

Usage: python -I -B cad/field/official/extract.py PATH/TO/OFFICIAL.step [OUTPUT_DIR]

The source is downloaded data: keep it in its own folder outside the checkout and run Python with -I.
Standard library only. Run tessellate.py afterwards to refresh the part lists, display meshes and the record.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RECORD = re.compile(r"#(\d+)\s*=\s*((?:'(?:[^']|'')*'|[^;'])*);")
STRING = re.compile(r"'((?:[^']|'')*)'")
REF = re.compile(r"#(\d+)")
STYLE_KINDS = ("STYLED_ITEM", "OVER_RIDING_STYLED_ITEM", "CONTEXT_DEPENDENT_OVER_RIDING_STYLED_ITEM")
STYLE_LISTS = ("MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION", "DRAUGHTING_MODEL")


def kind_of(body):
    body = body.lstrip()
    if body.startswith("("):
        return "(" + " ".join(re.findall(r"([A-Z][A-Z0-9_]+)\s*\(", STRING.sub("''", body)))
    return re.match(r"[A-Z0-9_]+", body).group(0)


def trim(source_text, selection):
    """Yield (fixture, STEP text, counts) for each fixture of the selection."""
    start = source_text.index("DATA;") + 5
    header, data = source_text[:start], source_text[start:source_text.rindex("ENDSEC;")]
    data = re.sub(r"/\*.*?\*/", "", data, flags=re.S) if "/*" in data else data
    body, kind, refs = {}, {}, {}
    for m in RECORD.finditer(data):
        n = int(m.group(1))
        body[n] = m.group(2)
        kind[n] = kind_of(m.group(2))
        refs[n] = [int(r) for r in REF.findall(STRING.sub("''", m.group(2)))]
    by_kind = {}
    for n, k in kind.items():
        for word in (k[1:].split() if k.startswith("(") else [k]):
            by_kind.setdefault(word, []).append(n)
    strings = lambda n: [s.replace("''", "'") for s in STRING.findall(body[n])]

    def product_name(definition):
        s = strings(refs[refs[definition][0]][0])
        return s[1] if len(s) > 1 and s[1].strip() else s[0]

    children, is_child = {}, set()
    for n in by_kind["NEXT_ASSEMBLY_USAGE_OCCURRENCE"]:
        parent, child = refs[n][:2]
        children.setdefault(parent, []).append((n, child))
        is_child.add(child)
    roots = [d for d in children if d not in is_child]
    assert len(roots) == 1, "Expected one root product"
    root = roots[0]
    shape_of, used_by = {}, {}                      # definition or occurrence -> its PRODUCT_DEFINITION_SHAPE records -> their users
    for n in by_kind["PRODUCT_DEFINITION_SHAPE"]:
        shape_of.setdefault(refs[n][0], []).append(n)
    for word in ("SHAPE_DEFINITION_REPRESENTATION", "CONTEXT_DEPENDENT_SHAPE_REPRESENTATION"):
        for n in by_kind.get(word, []):
            for r in refs[n]:
                used_by.setdefault(r, []).append(n)
    rep_links = {}                                  # representation -> plain SHAPE_REPRESENTATION_RELATIONSHIP records naming it
    for n in by_kind.get("SHAPE_REPRESENTATION_RELATIONSHIP", []):
        if "REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION" not in kind[n]:
            for r in refs[n][:2]:
                rep_links.setdefault(r, []).append(n)
    root_rep = next(refs[u][1] for s in shape_of[root] for u in used_by.get(s, []) if kind[u] == "SHAPE_DEFINITION_REPRESENTATION")
    context = refs[root_rep][-1]
    next_free = max(body) + 1

    for fixture in selection["fixtures"]:
        seeds, kept_definitions = set(), [root]
        for want in fixture["products"]:
            found = [(n, c) for n, c in children[root] if product_name(c) == want["product"]
                     and ("instance" not in want or want["instance"] in strings(n))]
            assert len(found) == 1, f"{want} matches {len(found)} top-level occurrences"
            stack = [found[0]]
            while stack:
                occurrence, definition = stack.pop()
                seeds.add(occurrence)
                for s in shape_of.get(occurrence, []):
                    seeds.update([s] + used_by.get(s, []))
                if definition not in kept_definitions:
                    kept_definitions.append(definition)
                    stack.extend(children.get(definition, []))
        for definition in kept_definitions:
            for s in shape_of.get(definition, []):
                seeds.update([s] + [u for u in used_by.get(s, []) if kind[u] == "SHAPE_DEFINITION_REPRESENTATION"])
        seeds.update(by_kind.get("APPLICATION_PROTOCOL_DEFINITION", []))
        keep = set()

        def close(stack):
            while stack:
                n = stack.pop()
                if n in keep:
                    continue
                keep.add(n)
                if n == root_rep:
                    continue        # the root's placements arrive through the kept occurrences, not through its item list
                stack.extend(r for r in refs[n] if r not in keep)
                stack.extend(link for link in rep_links.get(n, []) if link not in keep)

        close(list(seeds))
        close([context])
        # colours: keep each style whose styled item is kept, then list them
        styled = [n for word in STYLE_KINDS for n in by_kind.get(word, [])]
        changed, kept_styles = True, []
        while changed:
            changed = False
            for n in styled:
                if n not in keep and all(r in keep for r in refs[n] if not kind[r].startswith("PRESENTATION_STYLE")):
                    close([n])
                    kept_styles.append(n)
                    changed = True
        extra, listed = [], set()
        for word in STYLE_LISTS:
            for n in by_kind.get(word, []):
                if n not in keep and all(r in keep for r in refs[n]):
                    close([n])
                    listed.update(refs[n])
        unlisted = sorted(n for n in kept_styles if n not in listed)
        number = next_free
        if unlisted:
            extra.append(f"#{number} = MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION('',({','.join('#%d' % n for n in unlisted)}),#{context});")
            number += 1
        products = sorted({refs[refs[d][0]][0] for d in kept_definitions})
        extra.append(f"#{number} = PRODUCT_RELATED_PRODUCT_CATEGORY('part',$,({','.join('#%d' % n for n in products)}));")
        # the root representation keeps only the placements the kept records use
        items = [r for r in refs[root_rep][:-1] if r in keep]
        name = STRING.search(body[root_rep]).group(0)
        root_text = f"{kind[root_rep]}({name},({','.join('#%d' % r for r in items)}),#{context})"
        assert not kind[root_rep].startswith("("), "Unexpected complex root representation"
        lines = [header] + [f"#{n} = {root_text if n == root_rep else body[n]};" for n in sorted(keep)] + extra + ["ENDSEC;", "END-ISO-10303-21;", ""]
        yield fixture, "\n".join(lines), dict(records=len(keep), products=len(products), styles=len(kept_styles))


def main():
    source = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE
    out.mkdir(parents=True, exist_ok=True)
    selection = json.loads((HERE / "selection.json").read_text(encoding="utf-8"))
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == selection["source"]["stepSha256"], f"Not the pinned official field STEP: {digest}"
    for fixture, text, counts in trim(raw.decode("latin-1"), selection):
        path = out / f"{fixture['id']}.step"
        path.write_bytes(text.encode("latin-1"))
        print(path.name, path.stat().st_size, "bytes", counts, flush=True)


if __name__ == "__main__":
    main()
