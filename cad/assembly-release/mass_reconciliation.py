"""Separate body-property verification, vendor package masses and unresolved project scope."""

import argparse
import hashlib
import json
from pathlib import Path

from offline import machine
from reopened_geometry import read, mass_geometry


def investigate(output):
    job = json.loads((output / "foundation-job.json").read_bytes())
    cold = json.loads((output / "foundation-cold-mass.json").read_bytes())
    issued = json.loads((output / "foundation-issue-reopen.json").read_bytes())
    if cold["archiveSha256"] != issued["archiveSha256"] or not cold["restored"]:
        raise ValueError("No corresponding cold native evidence")
    by_id = {k: machine(row["features"]) for k, row in job["parts"].items()}
    step = output / "foundation-student.step"
    native, binding = read(step, by_id)
    if binding["sourceSha256"] != issued["stepSha256"]:
        raise ValueError("STEP view differs from the issued reopened model")
    checks = []
    modules = {}
    made = 0
    fasteners = 0
    unresolved = []
    prior = {r["occurrence"]: r for r in issued["rows"]}
    for row in cold["rows"]:
        name = row["occurrence"]
        if name not in native:
            unresolved.append(name)
            continue
        article = job["parts"][name]
        v = mass_geometry(native[name])[0] / 1000
        w = mass_geometry(by_id[name])[0] / 1000
        mass = row["massKg"]
        density = mass / max(row["volumeCm3"], 1e-10) * 1e6
        rel = abs(row["volumeCm3"] - v) / v
        checks.append(
            dict(
                part=name,
                identity=row["identity"],
                material=row["material"],
                nativeKg=mass,
                nativeCm3=row["volumeCm3"],
                reopenedStepCm3=v,
                originalStockCm3=w,
                nativeDensityKgM3=density,
                previousDefaultAccuracyCm3=prior[name]["volumeCm3"],
                relativeDifference=rel,
            )
        )
        if (
            row["identity"] != article["identity"]
            or row["instance"] != article["instance"]
            or row["material"] != article["material"]
        ):
            raise ValueError("Lost actual body identity or material on " + name)
        if row["instance"].startswith("MAXSwerve "):
            modules.setdefault(row["instance"], []).append(name)
        elif article["role"] == "fastener":
            fasteners += mass
        else:
            made += mass
    discrepancies = [r["part"] for r in checks if r["relativeDifference"] > 0.001]
    if set(modules) != {"MAXSwerve " + s["name"] for s in job["sites"]}:
        raise ValueError("Module purchase unit mismatch")
    return dict(
        archiveSha256=cold["archiveSha256"],
        stepSha256=binding["sourceSha256"],
        receiptSha256=hashlib.sha256(
            (output / "foundation-cold-mass.json").read_bytes()
        ).hexdigest(),
        coldNativeTotalKg=sum(s["massKg"] for s in cold["rows"]),
        legacyUnreconciled=unresolved,
        physicalCompleteRobotKg=None,
        madeFoundationKg=made,
        fastenerSurrogateKg=fasteners,
        moduleRepresentation=modules,
        modulePurchaseCount=len(modules),
        moduleCatalogKgEach=1.720,
        moduleCatalogSource="https://www.revrobotics.com/rev-21-3005/",
        moduleCondition="Supplier assembled-with-NEO catalog value. Physical historic configuration and measured dressed units remain unweighed. Four module representations are replaced once by four purchase units.",
        representedFoundationKg=made + fasteners + len(modules) * 1.720,
        unresolvedLimits="Threads, drive recesses, nut inserts, weld filler and supplier configuration make a physical as-built mass different from ideal first-party stock. Legacy upper, battery, bumper, electrical, harness, operating payload, tools and inspection exclusions are not resolved by this subsystem estimate.",
        discrepancies=discrepancies,
        checks=checks,
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("artifacts", type=Path)
    ap.add_argument("out", type=Path)
    a = ap.parse_args()
    report = investigate(a.artifacts)
    a.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    print(
        len(report["checks"]),
        "bodies checked;",
        len(report["discrepancies"]),
        "differ by more than 0.1 percent",
    )
