# 2026 REBUILT proof of concept

<!-- cad-still -->
[![R2C-T1 own-zone scorer and TOWER lift](docs/robot/cad/assembly.png)](https://ehartye.github.io/frc-2026-poc/robot/tower.html)

**Project CAD · R2C-T1 own-zone scorer and TOWER lift.** Parked 159-solid Fusion assembly with four swerve modules, blue bumpers and two editable rear low-rung sliders. Public purchased parts use project-drawn representations. [Source STEP · 973dd45e1f](cad/tower-lift/tower-l1.step) · [Rotate the model](https://ehartye.github.io/frc-2026-poc/robot/tower.html)
<!-- /cad-still -->

[Project workflow and student-owned outputs](docs/workflow.md) · [Current R2C-T1 Fusion handoff and climb](experiments/tower-climb/study.md) · [Play both mechanism animations](https://ehartye.github.io/frc-2026-poc/robot/)

## Kickoff field lab

[Open the live 2026 showcase](https://ehartye.github.io/frc-2026-poc/) or [launch the student field lab](https://ehartye.github.io/frc-2026-poc/field-lab.html) to compare starting volume, trench access and scoring windows. [Read the kickoff study and student decision record](kickoff/study.md) or inspect the [reviewed rules model](kickoff/rules-model.json). The lab uses the January 10 release and same-day Team Update 00. The [selected own-zone strategy](kickoff/selected-strategy.md) records the coordinator decision, serial service clock and first capacity screen.

Choose B2 or R2 in the student rehearsal to operate the Level 1 low-rung robot. B1/R1 can compare hypothetical higher-level hardware. [Play the physical climb](https://ehartye.github.io/frc-2026-poc/robot/tower.html).

[Play three matches at 10×](https://ehartye.github.io/frc-2026-poc/field-lab.html#rehearsal) or inspect the [student match-series results](kickoff/match-series.md).

## Archived subsystem experiment

The [historical case input manifest](experiments/legacy/historical-fixtures/agent-frc/manifest.json) identifies source-pinned simulation parameters, original geometry and prior analysis from the earlier plugin case. Inputs labeled as excerpts have a new schema and retain their source hash. The manifest records identical existing files and the original revision of the shared producers.

![Interim mechanism layout, not a complete robot](cad/interim-layout.svg)

**Interim subsystem concept, not a complete assembled robot.** Both views show the nominal mechanism fixture. It is not a picture of a complete robot. Chassis, motors, rails, supports and transmission are not assembled.

## Design highlights

- **Fixed-angle HUB approach and launch** with one preloaded FUEL.
- 60 degree guide, 0.3 m powered travel, 0.0005 kg m2 inertia per roller, refined duty 0.6.
- Ideal differential-drive approach, 200 ms stopped handoff, virtual pregrip/gate interlocks and powered roller model using WPILib DCMotor/shared supply.
- 12 V gives about 252 mm whole-sphere thin-plane margin; 9 V fails.
- **No official scoring or hardware safety acceptance is claimed.**

## Run on Windows

Requires existing Python 3, PowerShell, Git, JDK 17 and populated Gradle/WPILib cache. No installation or robot deployment is performed.

```powershell
./run.ps1 -JavaHome '<existing JDK17 directory>' -GradleHome '<existing populated Gradle cache>'
```

Open the printed results directory: `SUMMARY.md`, `season-results.json` and `robot-run/receipt.json`. Each invocation executes the unchanged shared three-season regression, then selects this season's results. The extra regressions are deliberate shared-model checks, not other season projects owned by this repository. Fresh output directories and run IDs prevent reusing old passing XML.

## What lives here

- `cad/`: original fixture STEP, editable OCP generator and dimensions, overview SVG, and earlier sideplate SVG/DXF. R1 adds the editable four-module Fusion chassis. R2C adds the intake, lift, hopper and scoring upper. The exact supplier archive stays project-local.
- `experiments/legacy/shared/examples/java-2026-sim/src/`: actual Java controller/plant and integration tests, not a link to unavailable code.
- `experiments/legacy/shared/scripts/`: actual execution, finite-body target and evidence checks.
- `config.json`: season design description checked against pinned runtime duty/inertia. It is not yet a general tuning interface.
- `docs/DESIGN.md`: design scope, assumptions and remaining work.
- `PROVENANCE.json`: exact source commit and file hashes; no Git history or private vault included.

The shared source snapshot is derived from agent-frc commit `21d785397cd08ca9dc5bf5f9849996ab508c9a49`. That development commit need not be accessible remotely to run this checkout. Gradle 8.11, GradleRIO/WPILib 2026.2.1 and JUnit 5.10.1 are pinned; 2024/2025 are game models using the 2026 desktop toolchain, not historical toolchain builds. See [dependency notices](experiments/legacy/shared/examples/java-2026-sim/THIRD_PARTY.md).

## Open and edit CAD

Open `cad/2026-original-fixture.step` in a STEP-capable CAD tool. Eight exported shapes describe the original floor/gate/guides, simplified rollers and nominal piece. The companion JSON records parameters and limitations. Export and STEP reopen were checked, not fit, loads or fabrication readiness. With an existing OCP 8.0.1 Python environment, regenerate using:

```powershell
python cad/build_original_fixture.py --season 2026 --output artifacts/cad
```

The top view is illustrative and omits guide-slot detail; STEP is the geometric artifact. CAD is not yet coupled automatically to the plant.

Only the documented run entry is supported by this minimal snapshot. Legacy tasks named in the retained upstream build file may have intentionally omitted sources. The configuration is a pinned description: edits are rejected, not silently treated as plant tuning. Shared source and CAD bytes are preserved by .gitattributes; other text uses LF.

## Public contribution checks

Run `python -m unittest discover -s tests` and `python scripts/check_public_content.py` after committing changes. The guard checks committed bytes, private paths/network addresses, unexplained machine aliases and binary additions. Reports identify file/category only. Manually review images/CAD metadata and novel formats before publishing; pattern checks are not a complete privacy guarantee.

[Follow the 24-piece packed service comparison in the student showcase](https://ehartye.github.io/frc-2026-poc/robot/batch.html).
