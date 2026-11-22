# R3 preliminary design review inputs

<!-- cad-still -->
[![Robot 1780 with red alliance bumpers](../showcase-red/assembly.png)](https://ehartye.github.io/frc-2026-poc/#model)

**Project CAD · Robot 1780 with red alliance bumpers.** Parked Fusion assembly with four swerve modules, a rear lift and two floor intake ramps supported by gussets on both sides. Purchased components use public project-drawn representations. [Editable Fusion assembly](../showcase-red/display.f3d) · [STEP](../showcase-red/display.step) · [Rotate the model](https://ehartye.github.io/frc-2026-poc/#model)
<!-- /cad-still -->

This folder follows the Agent FRC 0.86.0 whole-robot review layout template. `releases/layout-001/` holds the editable inputs for the R3 floor-fed hood shooter: design, layout, package STEP, paths, limits, budgets, narrative, premises, checker receipt and the checked package player. It is the R3-PD2 package from `experiments/preliminary-design/`, re-rooted so that every pin resolves inside the release directory, then re-checked with `preliminary-check --write-view --require-checked` (status `layout-checked`).

- Stage a release: `python cad/preliminary-design/stage.py layout-001`.
- Audit the index: `python cad/preliminary-design/stage.py --check-index`.
- Review locally: `python cad/preliminary-design/serve.py`, then open `http://127.0.0.1:8000/`. For a LAN review, add `--bind LAN_ADDRESS --port PORT`.

The free-piece acquisition, delivery and hang trials play in the [field-interaction player](../../docs/preliminary-design/field-interaction-layout-001.html). `pages-workflow.yml` is the template's starter workflow. It is not installed, because the season showcase already deploys Pages.
