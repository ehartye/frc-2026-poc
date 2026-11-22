# R3 preliminary design: a floor-fed hood shooter on the 680 mm swerve base

**Issue R3-PD1 · status `reopen` (conceptual-design: delivery pose) · three narrative objectives open · robot datum: carpet plane at the frame centre, +X toward the intake, +Y left, millimetres.**

Selected architecture: **R3, the tall floor-fed hooded-flywheel robot**. It replaces the R2C upper and the R2C-T1 screw lift for detailing. The swerve foundation carries forward provisionally.

All 18 cycle cases, both service withdrawals, the displaced control and both budgets pass. The issue is held by two things:

- A conceptual premise: R3 must deliver from 2.7 m, not from the rehearsed 2.16 m.
- Three narrative objectives whose evidence is a bench test or a load check, not layout geometry.

[Checker receipt](receipt.json) · [Layout plan](layout.json) · [Placed STEP](package.step) · [Motion study](paths.json) · [Budgets](budgets.json) · [Measurements](measurements.json) · [Architecture comparison](architecture-comparison.json) · [Retention review](retention.json) · [Ballistics](ballistics.json) · [Rules addendum](construction-rules.json)

## What the robot has to do

The pinned narrative is the [own-zone scorer strategy](../../kickoff/selected-strategy.md). Its AUTO preloads eight FUEL. During the inactive shift the robot collects up to 24 from the DEPOT, OUTPOST or a partner. It then scores 24 in 12 s while its HUB is active. The fallback is to score what it holds and return to collecting. In the end game it can take a Level 1 hang on the low rung.

The plan's narrative review gives each objective one of three dispositions:

- **Represented (six).** AUTO, collection, single-transfer delivery, fallback, measurement, plus the carry from storage into the HUB.
- **Open (three).**
  - Sustaining 2 FUEL/s (F1).
  - Keeping possession through loaded driving (F6).
  - The hang (F4).
- **Out of scope (three).** The neutral-collector route, the AUTO climb and the depot-lane reservation.

The V0 robot limits that the kickoff register left unmodeled now sit in [construction-rules.json](construction-rules.json). They come from the manual file whose SHA-256 the register already pins:

- R103 weight: 52.16 kg, excluding bumpers and battery.
- R408 weight with bumpers: 61.23 kg.
- R102 start configuration: no overhang outside the frame projection.
- R105/R106 extension: 304.8 mm, one side at a time.
- R107 height: 762 mm, measured as if the robot rests on a flat floor.
- FUEL: 0.203–0.227 kg.
- HUB opening: front edge at 1828.8 mm.
- TRENCH clear height: 565.15 mm.
- Low rung: centre at 685.8 mm, centred in the 819 mm-spaced uprights.
- TOWER BASE plate: 8 mm thick.

## Why R3

**The incumbent fails twice, and both failures are measured.** Its wheel pair cannot reach the opening: 7 of 9 cases peak between 0.97 m and 1.39 m. Its five-handoff path released 24 FUEL in 12 s, but only 3 scored.

**R3's allocation.** Floor belts feed the bottom FUEL layer straight into a 4 in flywheel pinch. A fixed hood wraps the piece 62° and releases it at 62° elevation. A diagonal slide carries a vertical belt over the bumper; the belt lifts a floor FUEL against the bumper face. A straight slide never sweeps beyond the R105 reach. The first issue's folding intake swept 360 mm past the perimeter mid-motion.

**Release height and pose.** [ballistics.py](ballistics.py) includes drag (Cd 0.35–0.60) and the downward spin lift a hood shot produces (CL 0–0.30). R3 releases at 0.236 m, so it needs about 2.4 m to the HUB centre before every drag-and-spin corner enters. A 0.60–0.70 m release enters from 2.0 m. R3 therefore trades the rehearsed delivery pose for one fewer transfer, and the rehearsal must be re-run with R3 delivering at 2.7 m (robot centre).

**The low variant (R3L) does not lose on capacity.** By exact free volume at 0.45–0.55 packing:

- R3 holds 36.9–45.1 FUEL.
- R3L holds 28.0–34.2 FUEL. It meets 24 with less margin.

A rigid stacked-lattice screen finds only 10 in both. It is kept as a lower bound, not a decision measure. R3L buys certain TRENCH passage but needs one more climber motion and gives up the BUMP option. **If the BUMP crossing premise (F5) fails, select R3L.**

| | A: R2C-T1 incumbent | **B: R3 selected** | C: R3L trench-runner |
|---|---|---|---|
| Custody | 5 handoffs; 3 of 24 scored | 3 handoffs; tracked piece checked carpet to HUB | 3 handoffs |
| Shot | 7 of 9 short | 6.88 m/s, robust band 6.82–6.96, 87 mm rim-edge clearance, from 2.4 m | as B, 49 mm lower |
| Mass (R103 52.16 kg) | no ledger | 35.6–47.8 kg, 4.36 kg reserve; ≤55.3 kg with bumpers | about 1 kg less |
| Weak-pack bus | not commissioned | 7.66 V minimum, needs 7.5 V | as B |
| Capacity (free volume) | 24 (box screen) | 36.9–45.1 | 28.0–34.2 |
| Swept envelope | 754 mm stowed | 750 mm; front 270.6 mm; one side; no start overhang | 534 mm, passes TRENCH |
| Field access | own zone | own zone, BUMP premise (4 mm margin) | own zone and TRENCH |
| Gives up | — | TRENCH, high release (delivery pose moves to 2.7 m) | capacity margin, BUMP, one climber motion |

| Rank (1 best) | Time | Risk | Complexity | Best practice | Maintainability |
|---|---|---|---|---|---|
| B: R3 | 1 | 1 | 1 | 1 | 1 |
| C: R3L | 2 | 2 | 2 | 1 (tie) | 2 |
| A: R2C-T1 | 3 | 3 | 3 | 3 | 3 |

- **Time:** B and C share mechanisms; C adds a telescoping raise before the hook swing. A must replace its shooter and feeder anyway, and its screw-lift findings stay open.
- **Risk:** B carries more capacity margin and fewer climber motions. C's TRENCH access is certain geometry, and this ranking flips if F5 fails.
- **Complexity:** B has one fewer climber motion. A has five handoffs and a screw-and-brake lift.
- **Best practice:** B and C use the same simple floor-fed allocation. A's serial elevator into a wheel pair is the furthest from it.
- **Maintainability:** B's battery and shooter both lift straight out (checked), and B has more packaging room than C.

**This invalidates detailed CAD and one field-rehearsal input:**

- The R2C upper (cad/own-zone-upper).
- The R2C-T1 tower lift, with its head-support, brake and mast studies.
- The foundation's battery cradle and electronics deck positions.
- The rehearsal's 2.16 m delivery steps.

The 680 mm frame, the module saddles at ±265 mm and the bumper section carry forward. Their supplier-fit evidence holds only until the R3 mounts are drawn.

## One FUEL through the cycle

| Case | What happens | Time (estimate) | Shared resource |
|---|---|---|---|
| intake-deploy | Carriage slides 280 mm forward and 62 mm down over the bumper | 0.4 s | slide actuator |
| acquire-approach, -climb, -over, -drop | Under the belt module; up the bumper face in the belt pinch; under the top roller over the bumper; onto the floor belts (3 mm undeformed reserve) | 0.5 s per piece | belt, drive |
| loaded-transit | Robot drives loaded to the shot pose (in the robot frame the field moves) | 3–5 s | drive current |
| index | Floor-belt cleat carries the piece 290 mm to the pinch (`carriedWith`) | 0.2 s | indexer |
| launch-wrap, flight-1…4 | 62° wrap, then four fitted ballistic arcs into the HUB cavity | 0.84 s flight | flywheel speed |
| tower-lateral, tower-forward | Indexer resets; bumper stops 5 mm from the uprights with the intake between them | 3 s | drive |
| climb-reach, climb-seat, climb-lift | Hooks swing 180° inboard, then seat within 2 mm of the rung (required contact, passed), then lift the robot 70 mm | 3 s | winch |
| park-lower | Robot returns to the carpet | 1 s | winch |

Intake, indexer and flywheel can run together while driving. The climb cannot overlap scoring.

## Check status

`node scripts/design.mjs preliminary-check <project> design/preliminary/layout.json --require-checked --write-view` returns **reopen** on Agent FRC 0.81.2, with the same receipt content as on 0.80.0. With `--require-checked` it exits 1:

- **Cases:** all 18 cycle cases and both service withdrawals pass in 10.4 s. climb-reach takes 4.4 s; every other case takes under 1 s.
- **Control:** raising the hood 8 mm makes it overlap the piece by 4,595 mm³, and the check rejects it.
- **Required contact:** both hooks seat within 1.5 mm of the rung.
- **Budgets:** mass passes (4.36 kg reserve). Every electrical case passes; the smallest margin is 0.16 V in weak-pack loaded transit.
- **Premises:** ten of eleven are within range. [build_package.py](build_package.py) measures each one from the solids and cases it writes.
  - `start-overhang` 0 mm.
  - `swept-height` 750 mm.
  - `swept-front-extension` 270.6 mm.
  - `swept-other-extension` 0 mm.
  - `sides-extended` 1.
  - `with-bumpers-mass` 55.3 kg.
  - `hopper-capacity` 36.9 and `start-capacity` 36.4.
  - `shot-window` 2.436 m.
  - `bump-breakover` 75 mm.
  - **`delivery-pose` 2.70 m is outside the rehearsed 1.9–2.4 m and reopens conceptual design.**

The smallest certified clearance lower bounds are 1.07–1.5 mm against the 1 mm reserve, on the guided FUEL paths and the hook sweep. Read them as nominal geometry, not tolerance-qualified fits.

The [package player](review/package-motion.html) is 31 MB, so it is not committed. To regenerate it from the committed files, run `node scripts/design.mjs preliminary-check <project> design/preliminary/layout.json --write-view` with `PYTHON` set to the CAD environment.

## Field interactions (Agent FRC 0.81.2)

[field_trials.py](field_trials.py) integrates each mission-critical interaction on this revision. It writes the [trace](field-trials.json) and a [player](review/field-interaction.html): pick a trial, scrub its run timestamps, and read the outcome, events, imposed and solved quantities, and solver settings. All trials use penalty contact with Coulomb friction, and their stiffness and friction values are estimates. Every trial gives the same result at half the timestep.

| Interaction | Nominal result | Control | Bracket (pass / fail), other inputs held |
|---|---|---|---|
| Acquisition: belt pulls the FUEL under its bottom pulley, lifts it against the bumper face, top roller pushes it over | Captured in 0.50 s | Belt and roller locked: not captured, so the belt does the transfer | Compression: 17.5 mm passes, 15 mm fails. Belt speed: 2.5 m/s passes, 2.0 m/s fails. Belt friction: 0.5 passes. |
| Delivery: free FUEL from the designed hood exit (6.88 m/s, 62°, spin ratio 1) through HUB contact to an assumed sensor plane at 1.50 m | Scored at 0.93 s, after one contact with the far cavity wall | Spin lift CL 0.30 and 30 kN/m contact: both still score | 6.70 and 7.10 m/s score. 6.55 and 7.30 m/s strike the rim and miss. |
| Hang: robot with wheel, bumper-upright and hook contacts; winch on a DC motor line, then 3 s with power removed | 37.8 mm minimum clearance through assessment; 2.2° pitch | No brake: the robot settles onto the carpet, so the hold depends on the brake | Winch current limit: 20 A passes, 15 A stalls before the stroke ends. An 8 V bus with 0.2 upright friction passes. |

What these results change:

- **Acquisition window (F2).** The window is narrow, and the belt speed is imposed. At 3 m/s the contacts dissipate up to 786 W at peak. Predicting whether a motor holds that speed under load needs a loaded drive model or a bench measurement. These belong to the F2 compression and drive-sizing work.
- **Delivery release (F2).** The release state is designed, not measured. The sensor location is an assumption.
- **Hang plane (F4).** The hang trial is a side view, so it cannot show the 6.4 mm lateral bumper overlap or roll.

## Open findings

1. **F1, bulk feed (the premise most likely to invalidate the role).** Twenty-four FUEL must converge into two pinch lanes at 2 FUEL/s or faster. The bench plan, stop conditions and fallback are in the [comparison](architecture-comparison.json).
2. **F2, contact settings and drives.** The acquisition trials need at least 17.5 mm of compression and 2.5 m/s of belt speed. Size the belt motor for its loaded speed. Belt-to-bumper pinch, top roller and hood/flywheel compression are not drawn; the layout reserves the undeformed path.
   - The robust speed band at 2.44 m is 6.82–6.96 m/s, so the flywheel must hold speed within about ±0.9%.
   - Flywheel inertia of at least 0.006 kg m² limits the speed drop per shot to about 1.6–2%, which is more than that band.
   - Recovery between shots is part of F1.
3. **F3, weak-pack margin.** Loaded transit keeps 0.16 V. The drive supply limit of 25 A per module (battery side) is required.
4. **F4, hang.**
   - The winch needs a current limit of at least 20 A (the trial stalls at 15 A).
   - At 67.6 kg the hang puts about 610 N of horizontal reaction on 6.4 mm of bumper overlap per upright.
   - The jaw reaches only 5.4 mm below the rung centre.
   - Options: a 714 mm wide frame within the 2794 mm perimeter, or lateral guidance, plus a longer jaw.
   - The winch must hold 663 N without power.
5. **F5, BUMP crossing.** The belly has 4 mm of breakover margin and no motion case, and the intake must retract to cross. If this fails, select R3L.
6. **F6, retention.** Run loaded 0.5 g stops (R-4). The capacity figure is a volume estimate, not a settled fill.
7. **F7, field rehearsal.** Re-run the delivery steps at 2.7 m and compare cycle time against a 0.6 m-release variant.
8. **F8, native CAD.** Building the R3 skeleton in Fusion is a follow-up for the single-writer Fusion session.

## Reproduce

Run from the project root:

```powershell
$env:PYTHON = '<cad python>'; $env:AGENT_FRC = '<agent-frc checkout>'
python -I -B design/preliminary/ballistics.py
python -I -B design/preliminary/build_package.py --check --fail-fast   # quick revision loop
python -I -B design/preliminary/build_package.py --check               # issued receipt and player
python -I -B design/preliminary/field_trials.py                        # field-interaction trials and player
```

The STEP header carries a fixed timestamp, so an unchanged rebuild reproduces every pinned hash.
