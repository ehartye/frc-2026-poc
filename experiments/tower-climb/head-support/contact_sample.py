from pathlib import Path
import json, sys

d = Path(__file__).resolve().parent
sys.path.insert(0, str(d.parent))
from support import run


def record(t, a, cg, contacts, bracepos, braceforce):
    if abs(t - 11) < 0.000001:
        print(
            "cg",
            cg,
            "pitch",
            a,
            "bracepos",
            bracepos,
            "braceforce",
            braceforce,
            "hooks",
            contacts,
        )
        (d / "settled-contacts.json").write_text(
            json.dumps(
                dict(
                    t=t,
                    angle=a,
                    cgXZ=cg,
                    contacts=contacts,
                    braceXZ=bracepos,
                    braceForceXZ=braceforce,
                ),
                indent=2,
            ),
            encoding="utf8",
            newline="\n",
        )


r = run("loaded68", mass=68, cog_x=0.035, observe_contacts=record)
field = json.loads((d.parent / "field.json").read_bytes())
print(
    [
        (p["name"], p["boundsMm"])
        for p in field["sides"]["blue"]
        if "Upright Outer" in p["name"]
    ]
)
