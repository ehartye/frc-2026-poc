# R3 preliminary design review inputs

<!-- cad-still -->
[![Robot 1780 with red alliance bumpers](../showcase-red/assembly.png)](https://ehartye.github.io/frc-2026-poc/#model)

**Project CAD · Robot 1780 with red alliance bumpers.** Parked Fusion assembly with four swerve modules, a rear lift and two floor intake ramps supported by gussets on both sides. Purchased components use public project-drawn representations. [Editable Fusion assembly](../showcase-red/display.f3d) · [STEP](../showcase-red/display.step) · [Rotate the model](https://ehartye.github.io/frc-2026-poc/#model)
<!-- /cad-still -->

This folder follows the Agent FRC 0.93.0 whole-robot review layout template. `releases/layout-001/` holds the editable inputs for the R3 floor-fed hood shooter: design, layout, package STEP, paths, limits, budgets, narrative, premises, checker receipt and the checked package player. It is the R3-PD2 package written by `python -I -B experiments/preliminary-design/build_package.py --release cad/preliminary-design/releases/layout-001`, so every pin resolves inside the release directory. The tracked FUEL's cases are fitted to the physics trials in `field-trials.json`. The receipt and player are regenerated with `preliminary-check --write-view --require-checked` when the release is staged.

- Stage a release: `python cad/preliminary-design/stage.py layout-001`.
- Audit the index: `python cad/preliminary-design/stage.py --check-index`.
- Review locally: `python cad/preliminary-design/serve.py`, then open `http://127.0.0.1:8000/`. For a LAN review, add `--bind LAN_ADDRESS --port PORT`.

The free-piece acquisition, hopper entry, launch, delivery and hang trials play in the [field-interaction player](releases/layout-001/field/r3-field-trials.html), which ships inside the release. `pages-workflow.yml` is the template's starter workflow. It is not installed, because the season showcase already deploys Pages.

The interacting field parts are motion-study fixtures (`field-fixtures.step`, registered under each case's `fixtures` with their source, dimensions and placement). They stay in the clearance checks but carry no robot mass, and **Fit field interaction** frames them.

The stable index's "main robot page" link (`../`) is part of the plugin's gated viewer. It resolves on the deployed GitHub Pages site, where `preliminary-design/` sits under the season showcase. A local server rooted at `docs/` has no season index there, so the link returns to this review.
