"""Create the public orbit from the STEP exported by the independently reopened Fusion archive."""

import hashlib
import json
from pathlib import Path
import sys
import numpy as np

HERE = Path(__file__).resolve().parent
CAD = HERE.parent
sys.path[:0] = [str(CAD / "assembly-release"), str(CAD / "own-zone-upper")]
from verify_products import products, measure
from animated import Scene, world, triangles
from numbering import COVERS, glyphs
from ramp_support import parts as ramp_parts
from offline import shape


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    native = json.loads((HERE / "native-reopen.json").read_bytes())
    if native["stage"] != "verified" or not native["restored"]:
        raise ValueError("The cold Fusion inspection has not completed")
    archive, step, still = (
        HERE / name for name in ("display.f3d", "display.step", "assembly.png")
    )
    for file, key in ((archive, "archiveSha256"), (step, "stepSha256")):
        if digest(file) != native[key]:
            raise ValueError(f"Different bytes: {file.name}")
    original = products(CAD / "assembly-release/foundation-student.step")
    originals = {
        name.replace(" blue ", " red ") if name in COVERS else name: body
        for name, body in original.items()
    }
    solids = products(step)
    artwork = {row["name"]: row for row in glyphs()}
    support = ramp_parts()
    if set(solids) != (set(originals) | set(artwork) | set(support)) or set(solids) != set(
        native["inventory"]
    ):
        raise ValueError("Fusion, STEP, foundation and artwork product lists differ")
    scene = Scene()
    scene.g.pop("animations", None)
    scene.g["asset"].update(
        generator="FRC 2026 public Foundation red 1780, cold-reopened Fusion STEP"
    )
    maxima = {"volumeMm3": 0.0, "centroidMm": 0.0, "extentMm": 0.0}
    count = 0
    for name, solid in solids.items():
        volume, cg, bb, ns = measure(solid)
        if ns != 1 or volume <= 0:
            raise ValueError("Expected one solid: " + name)
        if name in originals:
            v0, c0, b0, n0 = measure(originals[name])
            deviations = (
                abs(volume - v0),
                float(np.linalg.norm(cg - c0)),
                float(np.abs(bb - b0).max()),
            )
            if (
                deviations[0] > max(0.025, v0 * 1e-5)
                or deviations[1] > 0.001
                or deviations[2] > 0.001
            ):
                raise ValueError(("Changed foundation geometry", name, deviations))
            for key, d in zip(maxima, deviations):
                maxima[key] = max(maxima[key], d)
        elif name in artwork:
            row = artwork[name]
            axis = 0 if row["normal"][0] else 1
            if (
                abs(bb[axis + 3] - bb[axis] - 0.12) > 0.002
                or abs(bb[5] - bb[2] - 100) > 0.002
            ):
                raise ValueError(
                    "Print relief dimensions differ from the issue " + name
                )
        else:
            row=support[name]
            planned=shape({"kind":"profile","points":row["points"],"delta":row["delta"],"holes":[]})
            v0,c0,b0,_=measure(planned)
            if abs(v0-volume)>0.025 or np.linalg.norm(c0-cg)>0.001 or np.abs(b0-bb).max()>0.001:
                raise ValueError("Intake fabrication geometry differs: "+name)
            if native["inventory"][name]["material"] != row["material"]:
                raise ValueError("Intake support has a different physical material: "+name)
        color = native["inventory"][name]["rgb"]
        if color is None:
            raise ValueError(
                ("No source appearance", name, native["inventory"][name]["appearance"])
            )
        mesh = np.concatenate(list(triangles(solid, 0.16)))
        count += len(mesh)
        scene.geometry(scene.node(name), world(mesh), color)
    output = HERE / "display.glb"
    scene.save(output)
    result = {
        "revision": "Robot 1780 with chassis-connected intake ramps, derived from the issued red Fusion assembly",
        "sha256": {p.name: digest(p) for p in (archive, step, output, still)},
        "source": {
            "immediatePredecessor": {"commit": "25df8858ffa118469e9fefdbc5ff392de6e3a1ae", "path": "cad/showcase-red/display.f3d", "sha256": native["rampPredecessorSha256"]},
            "archive": "../assembly-release/foundation-student.f3d",
            "sha256": native["basisSha256"],
            "step": "../assembly-release/foundation-student.step",
            "stepSha256": digest(CAD / "assembly-release/foundation-student.step"),
        },
        "pipeline": [
            "Fusion opens the issued red 1780 predecessor, adds four editable ramp bridges and two frame cheeks, and assigns the six supports and two existing ramps their aluminum physical material.",
            "A separate Fusion document opens the saved derivative, reads all component appearances and exports the entire STEP. The cold viewport is independently checked after native graphics refresh.",
            "The public GLB tessellates those same 257 named STEP products with the colors read from the reopened archive.",
        ],
        "appearance": "Project red-alliance finish #C5273D; native white numerals #FFFFFF. Four 165 by 100 mm print groups use 13 mm primary strokes on the two sides, rear, and left front return. The print is represented by 0.12 mm relief.",
        "nativeStill": {
            "method": "Embedded assembly preview written by Autodesk Fusion into the issued archive",
            "archiveEntry": "FusionAssetName[Active]/Previews/big.png",
            "pixels": [1024, 1024],
            "pose": "Fusion-authored default saved assembly preview; blue studio background is a site presentation choice.",
        },
        "coldDiagnosticCamera": native["diagnosticCamera"],
        "fusionCounts": {
            "components": len(solids),
            "oneSolidPerProduct": True,
            "sourceComponents": len(originals),
            "whiteDigits": len(artwork),
            "rampSupportArticles": len(support),
            "redPredecessorSha256":native["rampPredecessorSha256"],
            "regularJointCollectionOnly": native["joints"],
            "asBuiltJoints": "Source swerve and tower motion have separate evidence. The display inspection did not remeasure the AsBuiltJoints collection.",
            "nativeRigidGroups": native["rigidGroups"],
        },
        "mesh": {
            "triangles": count,
            "nodes": len(scene.g["nodes"]),
            "chordToleranceMm": 0.16,
            "angularToleranceRad": 0.22,
            "coordinateMapping": "(robot X, robot Z, -robot Y) / 1000 to glTF metres",
        },
        "unchangedFoundationMaxDifference": maxima,
        "rights": "Public first-party robot geometry only. Purchased module and motor geometry is represented by the issued editable project envelopes. Exact supplier CAD remains in the private local relink; its geometry is not republished.",
        "engineeringScope": "The five colored bumpers in this display revision are solid packaging envelopes. Their inherited Fusion Steel assignment and the artwork are excluded from bumper mass or inspection claims. Sectioned foam, cloth, plywood and physical mounts belong to the separate passive service revision. This derivative does not qualify those mounts, tower support or match performance.",
        "motion": "Static assembled display. The pre-existing tower/joint and scoring motion studies have their own revision-bound viewers.",
    }
    (HERE / "provenance.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf8"
    )
    print("Verified", len(solids), "products and", count, "GLB triangles", flush=True)


if __name__ == "__main__":
    main()
