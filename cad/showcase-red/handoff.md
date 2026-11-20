# Red 1780 robot assembly

![Fusion preview of the assembled robot with red 1780 bumpers](assembly.png)

Open [display.f3d](display.f3d) in Fusion to inspect the four swerve corners, upper assembly and tower in their parked positions. The 235-component public foundation is the basis for this display. Five bumper bodies use the red alliance finish. Sixteen editable white ink extrusions spell **1780** on the left side, right side, rear and left front return. A full number fits the 190 mm front return alongside the intake opening. Each group spans 165 × 100 mm with 13 mm primary strokes.

The still above is the preview Fusion wrote inside the downloadable archive. The [orbitable GLB](display.glb) was tessellated from [the STEP](display.step) exported after the exact F3D reopened. The [provenance record](provenance.json) binds all four files to their digests and records the public model scope. [The fresh Fusion inspection](native-reopen.json) records component appearances and graphics visibility.

Bumper bodies in this revision represent the installed envelope. Their inherited Steel material assignment and the 0.12 mm ink relief are excluded from bumper mass estimates. Construction and service evidence for the layered bumper belongs to its own revision. Public module and motor envelopes retain their positions from the [qualified foundation](../assembly-release/engineering.md). Purchased models are registered separately for local engineering use.

## Reproduce the display

1. Run [display_fusion.py](display_fusion.py) through Fusion with a manifest pointing to the repository root in `project` and a local output directory in `evidenceDirectory`. The authoring pass opens the pinned foundation, creates the print from [numbering.py](numbering.py), and reopens the exported F3D to inspect its components and export the STEP.
2. Run `python3.14 cad/showcase-red/extract_preview.py` with Python 3.14 or newer to copy the embedded Fusion PNG. The archive uses Zstandard ZIP entries.
3. With the project CAD Python environment, run `python cad/showcase-red/build_orbit.py`. It compares all 235 predecessor shapes by volume, centroid and extents, checks the sixteen new marking bodies, and writes the GLB and byte-level provenance.

The graphics inspection refreshes Fusion’s occurrence visibility after import. This addresses a cold graphics state observed in which only the tower and artwork drew although all bodies reported visible.
