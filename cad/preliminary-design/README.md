# R3 preliminary design review inputs

<!-- cad-still -->
[![Robot 1780 with red alliance bumpers](../showcase-red/assembly.png)](https://ehartye.github.io/frc-2026-poc/#model)

**Project CAD · Robot 1780 with red alliance bumpers.** Parked Fusion assembly with four swerve modules, a rear lift and two floor intake ramps supported by gussets on both sides. Purchased components use public project-drawn representations. [Editable Fusion assembly](../showcase-red/display.f3d) · [STEP](../showcase-red/display.step) · [Rotate the model](https://ehartye.github.io/frc-2026-poc/#model)
<!-- /cad-still -->

This folder holds the checked inputs of each R3 preliminary design release and the scripts that publish them. It follows the Agent FRC 0.117.0 publication workflow: one release folder per issue, checked with the repository as the project root, and staged into `docs/preliminary-design/`.

| Release | Issue | Design | Status |
| --- | --- | --- | --- |
| `releases/layout-002/` | R3-PD3 | Floor-fed hooded flywheel shooter with a chute intake: FUEL enter the hopper over the intake's own back plate, a braked feeder roller per lane holds and meters them, and one flywheel with an inertia ring launches them | in progress |
| `releases/layout-001/` | R3-PD2 | Floor-fed hooded flywheel shooter with a low open throat | superseded by layout-002 |

`releases/layout-002/` is written by `experiments/preliminary-design/build_package.py --release cad/preliminary-design/releases/layout-002 --check` after `field_trials.py` has solved the physics trials. Every pin in it is a path from the repository root. It holds the layout plan, the placed STEP and field fixtures, the motion study, budgets and limits, premises, the narrative, `field-trials.json`, one trial-window record per tracked-FUEL case under `transport/`, the four trial records for the hold-back, the hopper cycle, the batch and the hang, `missions.json` (mission cases, the cycle map and the risk register), `verification-gates.json` (the same risk register with its bench tests), the review page and the `layout-checked` receipt.

- Check a release: `node PLUGIN/scripts/design.mjs preliminary-check . cad/preliminary-design/releases/layout-002/layout.json --require-checked --write-view --output cad/preliminary-design/releases/layout-002/receipt.json`.
- Report readiness to be marked effective: `node PLUGIN/scripts/design.mjs effective-readiness . --release cad/preliminary-design/releases/layout-002`.
- Stage a release: `python cad/preliminary-design/stage.py layout-002`, then `node PLUGIN/scripts/design-publication.mjs check .`.
- Change a status: `python cad/preliminary-design/stage.py --set-status layout-002 effective --readiness PLUGIN/scripts/effective-readiness.mjs`. The owner marks a release effective in a reviewed pull request.
- Review locally: `python cad/preliminary-design/serve.py`, then open `http://127.0.0.1:8000/`. For a LAN review, add `--bind LAN_ADDRESS --port PORT`.

The review is one page with one list of cases. The tracked FUEL's cases play strokes fitted to the solved trial traces. The hopper cycle, hold-back, batch and hang trials are recorded as trial records on their mission cases and do not play as animations in this release.

The interacting field parts are motion-study fixtures (`field-fixtures.step`, registered under each case's `fixtures` with their source, dimensions and placement). They stay in the clearance checks but carry no robot mass, and **Fit field interaction** frames them.
