# R3 preliminary design: a floor-fed hood shooter on the 680 mm swerve base

**Issue R3-PD1 · status `layout-checked` · robot datum: carpet plane at the frame centre, +X toward the intake, +Y left, millimetres.**
Selected architecture: **R3, the tall floor-fed hooded-flywheel robot**. It replaces the R2C upper and the R2C-T1 screw lift for detailing. The swerve foundation carries forward provisionally.

[Checker receipt](receipt.json) · [Layout plan](layout.json) · [Placed STEP](package.step) · [Motion study](paths.json) · [Budgets](budgets.json) · [Architecture comparison](architecture-comparison.json) · [Retention review](retention.json) · [Rules addendum](construction-rules.json)

## What the robot has to do

The pinned narrative is the [own-zone scorer strategy](../../kickoff/selected-strategy.md). Its AUTO preloads eight FUEL. During the inactive shift the robot collects up to 24 from the DEPOT, OUTPOST or a partner. It then scores 24 in 12 s while its HUB is active. The fallback is to score what it holds and return to collecting. In the end game it can take a Level 1 hang on the low rung. The narrative review in the plan marks each objective. Seven are represented by cases or premises. Three are out of scope for this layout: the neutral-collector route, the AUTO climb and the depot-lane reservation. The basis is recorded beside each one.

The V0 robot limits that the kickoff register left unmodeled now sit in [construction-rules.json](construction-rules.json). They come from the manual file whose SHA-256 the register already pins:

- R103 weight: 52.16 kg, excluding bumpers and battery.
- R408 weight with bumpers: 61.23 kg.
- R105 extension: 304.8 mm, one side at a time.
- R107 height: 762 mm at all times.
- FUEL: 0.203–0.227 kg.
- HUB opening: front edge at 1828.8 mm, 41.7 in hexagon.
- TRENCH clear height: 565.15 mm.
- Low rung: centre at 685.8 mm, 819 mm between the uprights.

## Why R3

The incumbent fails at two points, and both are measured. Its wheel pair cannot reach the opening: 7 of 9 cases peak between 0.97 m and 1.39 m. Its five-handoff path released 24 FUEL in 12 s, but only 3 scored. [ballistics.py](ballistics.py) shows that release height hardly matters. Every exit between 0.23 m and 0.70 m needs 5.6–8.3 m/s over 1.6–3.6 m. Removing the elevator therefore costs only about 0.3 m/s of exit speed.

R3 feeds the bottom FUEL layer on floor belts straight into a 4 in flywheel pinch. A fixed hood wraps the piece 60° and releases it at 60° elevation. The architecture comparison tested two other options:

- **Lowering the same arrangement under the TRENCH (R3L).** The capacity screen runs on the same solids and gives 20 deployed and 18 in the starting fold. That fails the 24-piece batch.
- **Direct deposit.** R107 rules it out.

| | A: R2C-T1 incumbent | **B: R3 selected** | C: R3L trench-runner |
|---|---|---|---|
| Custody | 5 handoffs; 3 of 24 scored | 3 handoffs; tracked piece checked carpet to HUB | 3 handoffs |
| Shot | 7 of 9 short | 6.91 m/s, 57 mm rim-edge clearance | as B |
| Mass (R103 52.16 kg) | no ledger | 32.6–44.6 kg, 7.56 kg reserve | about 1 kg less |
| Weak-pack bus | not commissioned | 7.66 V minimum, needs 7.5 V | as B |
| Capacity, deployed / start fold | 24 (box screen) | 30 / 23 | **20 / 18** |
| Height | 754 mm | 750 mm | 534 mm, passes TRENCH |
| Field access | own zone | own zone, BUMP premise | own zone and TRENCH |
| Gives up | — | TRENCH, high release | capacity, BUMP |

| Rank (1 best) | Time | Risk | Complexity | Best practice | Maintainability |
|---|---|---|---|---|---|
| B: R3 | 1 | 1 | 1 | 1 | 1 |
| C: R3L | 2 | 2 | 2 | 2 | 2 |
| A: R2C-T1 | 3 | 3 | 3 | 3 | 3 |

- **Time:** B reuses the foundation and needs no new mechanism class. C needs an expanding hopper to reach 24. A must replace its shooter and feeder anyway, and its screw lift findings stay open.
- **Risk:** A's failures are measured. C fails capacity by calculation. B's largest risk is bulk feeding (F1).
- **Complexity:** B and C share one allocation, but C's fix adds a mechanism. A has five handoffs and a screw-and-brake lift.
- **Best practice:** a floor-fed hood shooter is a common, simple allocation. A's serial elevator into a wheel pair is the furthest from it.
- **Maintainability:** B's battery and shooter both lift straight out (checked). C packs the same parts under 535 mm.

**This invalidates detailed CAD.** The R2C upper (cad/own-zone-upper) is superseded, and so is the R2C-T1 tower lift with its head-support, brake and mast studies. The foundation's battery cradle and electronics deck positions are also superseded. The 680 mm frame, the module saddles at ±265 mm and the bumper section carry forward. Their supplier-fit evidence holds only until the R3 mounts are drawn.

## One FUEL through the cycle

| Case | What happens | Time (estimate) | Shared resource |
|---|---|---|---|
| intake-deploy | Intake unfolds 135° from its legal start fold | 0.4 s | intake gearmotor |
| acquire-approach … acquire-drop | Ramp, roller, crest over the bumper and drop onto the floor belts, with a 3 mm undeformed reserve | 0.5 s per piece | roller, drive |
| loaded-transit | Robot drives loaded from the DEPOT side to the shot pose (in the robot frame the field moves) | 3–5 s | drive current |
| index | Floor-belt cleat carries the piece 290 mm to the pinch (`carriedWith`) | 0.2 s | indexer |
| launch-wrap, flight-1…4 | 60° wrap, then four fitted ballistic arcs into the HUB cavity | 0.79 s flight | flywheel speed |
| tower-lateral, tower-forward | Indexer resets; bumper stops 5 mm from the uprights with the intake between them | 3 s | drive |
| climb-reach, climb-seat, climb-lift | Hooks swing 180° inboard, then seat within 2 mm of the rung (required contact, passed), then lift the robot 70 mm | 3 s | winch |
| park-lower | Robot returns to the carpet | 1 s | winch |

Intake, indexer and flywheel can run together while driving. The climb cannot overlap scoring, because the drive is parked and the winch takes the current.

## Check status

`node scripts/design.mjs preliminary-check <project> design/preliminary/layout.json --require-checked --write-view` returns **layout-checked** with no missing inputs:

- **Cases:** all 20 cycle cases and both service withdrawals (battery and shooter module) pass. The full run takes 18 s. The slowest case is climb-reach at 4.8 s. Every other case takes under 1 s.
- **Control:** raising the hood 8 mm makes it overlap the piece by 4,595 mm³ at the pinch, and the check rejects it.
- **Required contact:** both hooks seat within 1.5 mm of the rung.
- **Premises:** all seven observations fall inside their accepted ranges.
  - Start-fold height 750 mm (limit 762).
  - Deployed height 750 mm.
  - Intake reach 266.9 mm (limit 304.8).
  - Capacity 30 deployed (need 24) and 23 in the start fold (need 8).
  - Shot distance 2.338 m (range 1.6–3.6).
  - Belly clearance 75 mm (BUMP breakover needs 71).

The clearances are close to the reserve. The smallest certified lower bounds are 1.04–1.6 mm against the 1 mm reserve, on the guided FUEL paths and the hook sweep. Read them as nominal geometry, not tolerance-qualified fits.

The [package player](review/package-motion.html) is 81 MB, so it is not committed. To regenerate it, run `python -I -B design/preliminary/build_package.py --check` from the project root. Set the `PYTHON` environment variable to the CAD environment and `AGENT_FRC` to the plugin checkout. The receipt records its SHA-256.

## Open findings

1. **F1, bulk feed (the premise most likely to invalidate the role).** 24 FUEL must converge into two pinch lanes at 2 FUEL/s or faster. The bench plan, stop conditions and fallback are in the [comparison](architecture-comparison.json).
2. **F2, contact settings.** Hood/flywheel and roller compression are not drawn; the layout reserves the undeformed path. The accepted speed band at 2.34 m is only 6.79–6.91 m/s at Cd 0.47. Measure Cd and hold the flywheel speed within about ±1%. Flywheel inertia of 0.006 kg m² or more limits the speed drop per shot to about 2%.
3. **F3, weak-pack margin.** Loaded transit keeps only 0.16 V. The drive supply limit of 25 A per module (battery side) is a requirement, not an option.
4. **F4, hang.** The rung position within the upright depth is assumed. The jaw reaches 5.4 mm below the rung centre against a horizontal reaction of about 575 N. Select the winch brake and the swing actuator.
5. **F5, BUMP crossing.** The belly has 4 mm of breakover margin and no motion case.
6. **F6, retention.** Run loaded 0.5 g stops. The capacity figure is a non-overlap screen, not a settled heap.
7. **F7, native CAD.** Building the R3 skeleton in Fusion is a follow-up for the single-writer Fusion session.

## Reproduce

Run from the project root with the CAD Python environment selected:

```powershell
$env:PYTHON = '<cad python>'; $env:AGENT_FRC = '<agent-frc checkout>'
python -I -B design/preliminary/ballistics.py
python -I -B design/preliminary/build_package.py --check --fail-fast   # quick revision loop
python -I -B design/preliminary/build_package.py --check               # issued receipt and player
```
