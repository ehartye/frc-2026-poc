# R3-PD2 LAN review bundle

<!-- cad-still -->
[![Robot 1780 with red alliance bumpers](../../../cad/showcase-red/assembly.png)](https://ehartye.github.io/frc-2026-poc/#model)

**Project CAD · Robot 1780 with red alliance bumpers.** Parked Fusion assembly with four swerve modules, a rear lift and two floor intake ramps supported by gussets on both sides. Purchased components use public project-drawn representations. [Editable Fusion assembly](../../../cad/showcase-red/display.f3d) · [STEP](../../../cad/showcase-red/display.step) · [Rotate the model](https://ehartye.github.io/frc-2026-poc/#model)
<!-- /cad-still -->

The still above is the current published robot. This bundle reviews the preliminary R3 design, which is layout-checked but not yet detailed in Fusion.

This folder holds only the review pages for issue R3-PD2: `package-motion.html`, the geometric clearance player (about 31 MB, committed; its SHA-256 is pinned in `receipt.json`), and `field-interaction.html`, the physics trial player (committed; rebuild it with `python -I -B experiments/preliminary-design/field_trials.py`). Both pages are self-contained: they load no external scripts. Private CAD and supplier models are not in it.

## Build the page

From the project root, with the CAD Python environment selected:

```powershell
$env:PYTHON = '<cad python>'
node <agent-frc>/scripts/design.mjs preliminary-check . experiments/preliminary-design/layout.json --write-view --quiet > $null
```

The receipt records the page's SHA-256 (`view.sha256` in [receipt.json](../receipt.json)). A page earns credit only if its bytes match.

## Serve it on the LAN

```powershell
python -m http.server 8765 --bind <host LAN address> --directory experiments/preliminary-design/review
```

Open `http://<host LAN address>:8765/index.html` on the host and then on a second device. Stop the server with Ctrl+C. The folder stays usable as a static bundle after the host shuts down.

## What to check

1. Reset the view, orbit a full revolution and underneath, pan, zoom, and toggle the labels.
2. Play `intake-deploy` through `park-lower` in order. Then scrub `launch-wrap` and the four flight arcs into the HUB cavity.
3. Select a component and read its purpose and rationale.
4. Open the mass and power ledgers.
5. In `field-interaction.html`, play `hang-nominal` and the failing `hang-no-brake` control, then `deliver-6.55` (a rim miss) and `acquire-belt-locked`.
6. Open the displaced-hood control (`package-displacement-control`). It shows a known failing case.

Expected scope: the represented package, cases and reserves. The issue's status is `reopen`; read why in [the study](../study.md).
