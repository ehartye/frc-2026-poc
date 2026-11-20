"""Reconcile editable material, native/STEP volume and single-charge purchase units for this subsystem."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
from passive_job import recipe
from foundation_job import recipe as foundation
from verify_products import products
from reopened_geometry import mass_geometry


def reconcile(folder, csv_path):
    job = recipe()
    allparts = {**foundation()["parts"], **job["parts"]}
    receipt = json.loads((folder / "service-native.json").read_bytes())
    step = folder / "service-student.step"
    pin = hashlib.sha256(step.read_bytes()).hexdigest()
    if not (
        receipt["restored"]
        and receipt["stage"] == "verified"
        and receipt["stepSha256"] == pin
    ):
        raise ValueError(
            "The input must be an independently reopened and restored service archive"
        )
    source = products(step)
    if set(source) != set(receipt["rows"]):
        raise ValueError("Incomplete archive inventory")
    charged = {}
    rows = []
    missing = []
    discrepant = []
    for name, body in source.items():
        props = receipt["rows"][name]
        vol_mm3 = mass_geometry(body)[0]
        if abs(vol_mm3 / 1000 - props["volumeCm3"]) > max(
            0.0001, vol_mm3 / 1000 * 0.001
        ):
            discrepant.append(name)
        row = allparts.get(name)
        if not row:
            missing.append(name)
            continue
        if (
            props["identity"] != row["identity"]
            or props["instance"] != row["instance"]
            or props["material"] != row["material"]
        ):
            raise ValueError("Material or article mismatch " + name)
        spec = row.get("engineeringMaterial")
        if spec and abs(spec["densityKgM3"] - props["densityKgM3"]) > 0.1:
            raise ValueError("Material density changed " + name)
        unit = row["instance"]
        if unit.startswith("MAXSwerve "):
            kg = 1.720
            basis = "REV assembled module catalog mass, one purchase unit"
            code = "REV-21-3005"
        elif "catalogMassKg" in row:
            kg = row["catalogMassKg"]
            basis = "MK complete sealed battery catalog mass, one purchase unit"
            code = "MK ES17-12"
        else:
            kg = vol_mm3 * props["densityKgM3"] / 1e9
            basis = "Reopened STEP volume times observed native material density"
            code = row.get("purchase") or row.get("source")
        if unit in charged and not unit.startswith("MAXSwerve "):
            raise ValueError("Duplicate purchase ownership: " + unit)
        charged[unit] = dict(massKg=kg, basis=basis, article=code)
        rows.append(
            dict(
                article=name,
                owner=unit,
                stock_or_purchase=code,
                material=props["material"],
                native_material_ID=props["materialId"],
                density_kg_m3=props["densityKgM3"],
                STEP_volume_mm3=round(vol_mm3, 4),
                native_mass_kg=props["massKg"],
                mass_basis=basis,
                installed_parent=row["parent"],
                method=row["connection"],
            )
        )
    with csv_path.open("w", newline="", encoding="utf8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return dict(
        archiveSha256=receipt["archiveSha256"],
        stepSha256=pin,
        nativeTotalKg=sum(p["massKg"] for p in receipt["rows"].values()),
        nativeVolumeDiscrepancies=discrepant,
        reconciledShapes=len(rows),
        purchaseOwners=len(charged),
        representedInstalledKg=sum(r["massKg"] for r in charged.values()),
        unresolvedArticles=sorted(missing),
        wholeInspectionMassKg=None,
        charged=charged,
        limits="Includes the installed blue cover set, ideal rigid fasteners, four catalog module units and one nominal 5.86 kg battery. Includes the purchased battery's casing and contents once. Does not book wire/boots, sewn overlap, mounting staples, adhesive, weld filler, the remaining historical upper or a pit cart. No inspection scale reading.",
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for n in ("folder", "out", "csv"):
        p.add_argument(n, type=Path)
    a = p.parse_args()
    r = reconcile(a.folder, a.csv)
    a.out.write_text(json.dumps(r, indent=2) + "\n", encoding="utf8")
    print(
        r["representedInstalledKg"],
        "kg; native discrepancies",
        r["nativeVolumeDiscrepancies"],
    )
