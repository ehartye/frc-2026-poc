# Preliminary design: Chute-fed hood shooter

<!-- cad-still -->
[![Chute-fed hood shooter 1.0, preliminary design](../../docs/robot/preliminary-design.png)](https://ehartye.github.io/frc-2026-poc/preliminary-design/)

**Project CAD · Chute-fed hood shooter 1.0, preliminary design · in-progress.** Whole-robot blockout, parked at the end of the park-lower case: back on the carpet after the low-rung hang, with the intake stowed. Field parts and FUEL are hidden. It is not detailed CAD. [Open the design review](https://ehartye.github.io/frc-2026-poc/preliminary-design/)
<!-- /cad-still -->

This folder holds the preliminary design as data. The coding agent checks, stages and publishes the design with its own design tool, Agent FRC; `PLUGIN` below stands for wherever the agent keeps that tool. The project's CI runs none of it and the repository holds no pin to it. The solids are built and measured by the design library, [`frc-design-kernel`](https://github.com/ehartye/frc-design-kernel), which has no pinned version: its main branch is the release.

| Version | Design | Status |
| --- | --- | --- |
| `releases/1.0/` | Chute-fed hood shooter: FUEL enter the hopper over the intake's own back plate, a braked feeder roller per lane holds and meters them, and one hooded flywheel with an inertia ring launches them. Level 1 hang on two telescoping hooks. | in progress |

One design has one version folder. An edit to an in-progress design is the next draft of the same version: edit the data, regenerate, check and stage `1.0` again.

## Source, judgement and generated files

| Kind | Files | Who writes them |
| --- | --- | --- |
| Source | `design.json`: every solid, group, fixture, mount, contact, pose and motion, with sizes worked out from its `parameters`. `field/*.step`: the field parts it places | The designer or the agent, by hand. This is where geometry changes |
| Judgement | `judgement.json`: the stage of each motion with its allowance and basis, the cycle, the displaced control, attachment labels, premises, the narrative list and the review text. `budgets.json`, `package-limits.json`, `missions.json`, `narrative.md`, `premise-*.json`, `measurements.json` | The designer or the agent, by hand. This is where reasons, allowances and budgets change |
| Generated | `generated/design.step`, `generated/fixtures.step`, `generated/manifest.json` | The design library, from `design.json`. Never edited |
| Checked | `receipt.json`, `package-motion.html` and its scene | The agent's layout check |
| Recorded trials | `field-trials.json`, `transport/`, `trial-*.json`, `replays.json.gz` | The trial solver in `experiments/preliminary-design/`. Kept as recorded until trials are written as data |

A finding from a trial or a later stage is fixed in `design.json`, never in a generated file. No program in this repository draws the robot.

## Regenerate, check and publish

The agent runs these from the repository root with the geometry Python environment.

```sh
python -m frc_design_kernel build cad/preliminary-design/releases/1.0/design.json --out cad/preliminary-design/releases/1.0/generated
node PLUGIN/scripts/design.mjs preliminary-check . cad/preliminary-design/releases/1.0/judgement.json --write-view --output cad/preliminary-design/releases/1.0/receipt.json --workers 4
python -I -B experiments/preliminary-design/handoff.py cad/preliminary-design/releases/1.0
python PLUGIN/scripts/stage_preliminary_review.py 1.0
python scripts/preliminary-still.py .
python scripts/cad-readmes.py . --update
node PLUGIN/scripts/design-publication.mjs check .
```

- Regenerate after every edit to `design.json`. The layout check stops when the generated solids are of an earlier source.
- The full check takes under a minute. While changing one or two motions, add `--cases A,B`; while only geometry or motion changes, use `--physics-only` in place of `--write-view`.
- After an edit to names, colours, explanations or grouping only, run the check with `--view-only` in place of `--write-view`.
- Readiness to be marked effective: `node PLUGIN/scripts/design.mjs effective-readiness . --release cad/preliminary-design/releases/1.0 --design "Chute-fed hood shooter 1.0"`. The owner marks a design effective in a reviewed pull request.
- Review locally: `python PLUGIN/scripts/serve_preliminary_review.py`, then open `http://127.0.0.1:8000/`.
- After the status or draft number changes, edit the status line and caption of `docs/index.html` by hand. Nothing writes the entry page.

The physics trials are solved separately by `experiments/preliminary-design/field_trials.py` (about twenty minutes on eight cores) into `experiments/preliminary-design/field-trials.json`. The tracked FUEL's motions in `design.json` are fitted to those traces, and each `transport/` record repeats the exact start and travel of the motion it stands behind. Rerun the trials after changing `dimensions.py`, then refit those motions and records by hand.

The review is one page with one motion list: the checked cases first, then the replays. A replay is playback of the recorded frames. The layout check neither runs nor credits it.
