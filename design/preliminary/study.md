# R3 preliminary design: a floor-fed hood shooter on a 680 × 714 mm swerve base

**Issue R3-PD2 · robot datum: carpet plane at the frame centre, +X toward the intake, +Y left, millimetres.**

Selected architecture: **R3, the tall floor-fed hooded-flywheel robot**. It replaces the R2C upper and the R2C-T1 screw lift for detailing.

**Status.** The issue is `layout-checked` on its own: every case, premise, control and budget passes, and no input is missing. Resubmitted against the held [R3-PD1 receipt](receipt-R3-PD1-held.json), as the contract requires, it stays `reopen`. The checker cannot verify a repeated *delivery position*; it replays only a step's dwell, speed, height, heading or pickup face. See [Why the held issue stays reopened](#why-the-held-issue-stays-reopened).

[Checker receipt](receipt.json) · [Layout plan](layout.json) · [Placed STEP](package.step) · [Motion study](paths.json) · [Budgets](budgets.json) · [Measurements](measurements.json) · [Verification gates](verification-gates.json) · [Re-run rehearsal](rehearsal/comparison.json) · [Architecture comparison](architecture-comparison.json) · [Retention review](retention.json) · [Ballistics](ballistics.json) · [Rules addendum](construction-rules.json) · [Review index](review/index.html)

## What changed from R3-PD1

- **Field rehearsal re-run at the 2.7 m delivery pose** (the plugin's `rehearsal-series.mjs` on project variants of the kickoff profile).
  - Slot 2's AUTO and depot-shift deliveries move to 2.70 m from the HUB centre. They stay inside the profile's 52 in legal-pose screen; the depot delivery bearing turns from 30° to 24°.
  - Over the three matches, slot 2 credits 96 FUEL against the baseline's 104, so the 2.70 m pose costs 8 FUEL. Two matches each lose one 4-piece delivery, and the cycle legs barely change (2.85 s against 3.1 s).
  - R3L on the depot route matches R3 (96). On the TRENCH route it credits only 40. R3 stays selected.
- **Frame widened to 714 mm.** The perimeter becomes 2788 mm of the 2794 mm allowed. The bumper overlaps each TOWER upright by 23.9 mm instead of 6.4 mm. [hang_overlap.py](hang_overlap.py) checks this in plan view: both uprights bear for lateral offsets up to ±23.9 mm (±6.9 mm at 680 mm), and a 0.5° yaw opens a 7.5 mm trailing gap, so the robot squares against both uprights before it lifts. Module centres move to ±282 mm across; the foundation's side-rail saddles must be redrawn.
- **Floor raised to 100 mm.** [bump_crossing.py](bump_crossing.py) rests both wheels on the BUMP profile across a sharp 15° crest. The least clearance is 8.7 mm, at the front bumper corner, which the bumper zone fixes; the belly keeps 24.3 mm.
- **Narrative.** Every objective is represented or explicitly scoped out. The performance that geometry cannot show is carried by [verification gates](verification-gates.json) with pass/fail numbers, which the contract assigns to separate evidence: "Detailed seat geometry, loads, tolerances, retention, actuator dynamics and physical performance require their own commissioned evidence."

## What the robot has to do

The pinned narrative is the [own-zone scorer strategy](../../kickoff/selected-strategy.md). Its AUTO preloads eight FUEL. During the inactive shift the robot collects up to 24 from the DEPOT, OUTPOST or a partner. It then scores 24 in 12 s while its HUB is active. The fallback is to score what it holds and return to collecting. In the end game it can take a Level 1 hang on the low rung.

The plan's narrative review gives each objective one of three dispositions:

- **Represented (eight).** AUTO, collection, single-transfer delivery, the 2 FUEL/s rate (gate G1), fallback, possession under traffic (gate G2), the hang (gate G3) and measurement.
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

The 680 mm frame length, the four MAXSwerve corners and the bumper section carry forward. The frame widens to 714 mm, so the side-rail module saddles must be redrawn before the supplier-fit evidence applies again.

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

`node scripts/design.mjs preliminary-check <project> design/preliminary/layout.json --require-checked --write-view` on Agent FRC 0.81.2:

- **Without `--previous`:** `layout-checked`, exit 0.
- **With `--previous design/preliminary/receipt-R3-PD1-held.json`:** `reopen`, exit 1. This is the issued [receipt](receipt.json). Its only missing item is "Repeat conceptual-design on this issue before resuming delivery-pose".

What passes in both runs:

- **Cases:** all 18 cycle cases and both service withdrawals pass in about 10 s.
- **Control:** raising the hood 8 mm overlaps the FUEL by 4,595 mm³, and the check rejects it.
- **Required contact:** both hooks seat within 1.5 mm of the rung.
- **Budgets:** R103 mass is 35.6–47.8 kg (4.36 kg reserve). The weak-pack minimum is 7.66 V against 7.5 V.
- **Premises:** all twelve are within range.
  - `start-overhang` 0 mm.
  - `swept-height` 750 mm.
  - `swept-front-extension` 270.6 mm.
  - `swept-other-extension` 0 mm.
  - `sides-extended` 1.
  - `with-bumpers-mass` 55.3 kg.
  - `hopper-capacity` 37.7 and `start-capacity` 37.2.
  - `shot-window` 2.436 m.
  - `delivery-pose` 2.70 m against the re-run rehearsal's 2.6–2.8 m.
  - `bump-crossing` 8.7 mm.
  - `hang-bumper-overlap` 23.9 mm.

### Why the held issue stays reopened

The contract requires passing the held receipt: "Keep the held receipt in project custody and pass it separately on resubmission." It then limits what can clear a held field premise: "Supported replay inputs include a named program step’s dwell, robot speed, height and heading, and a modeled front pickup mouth. … An unsupported repeat stays open." It also states that "An initial review without a supplied prior receipt cannot clear a historical hold."

The held premise is a delivery *position*, which is none of the supported inputs. R3-PD2 records it as a replay input for the forthcoming position replay. [rehearsal/delivery-pose-evidence.json](rehearsal/delivery-pose-evidence.json) names actor B2, match "Own-zone supply", Shift 1, program `shift-depot` step 3 "Attempt HUB delivery; credited". It gives the 2.70 m stand-off at a 23.7° bearing and the AUTO step at 2.70 m and 0.1°, pins the re-run profile, result and held receipt, and is referenced by the premise's `fieldInput` and `repeat`. The R3-PD1 premise files keep their original bytes; R3-PD2's premises are prefixed with the issue name. So `verify_reopens()` in `scripts/preliminary_design.py` reports `repeatVerified: false` however the rehearsal turns out. Clearing it needs either a plugin replay input for a program step's position, or an owner decision to accept the re-run rehearsal as the conceptual repeat.

The [package player](review/package-motion.html) is 31 MB, so it is not committed; regenerate it with `--write-view`. The plugin's player has no field-interaction view, so the [review index](review/index.html) links it with the committed [field-interaction player](review/field-interaction.html).

## Field interactions (Agent FRC 0.81.2)

[field_trials.py](field_trials.py) integrates each mission-critical interaction on this revision. It writes the [trace](field-trials.json) and a [player](review/field-interaction.html): pick a trial, scrub its run timestamps, and read the outcome, events, imposed and solved quantities, and solver settings. All trials use penalty contact with Coulomb friction, and their stiffness and friction values are estimates. Every trial gives the same result at half the timestep.

| Interaction | Nominal result | Control | Bracket (pass / fail), other inputs held |
|---|---|---|---|
| Acquisition: belt pulls the FUEL under its bottom pulley, lifts it against the bumper face, top roller pushes it over | Captured in 0.53 s | Belt and roller locked: not captured, so the belt does the transfer | Compression: 17.5 mm passes, 15 mm fails. Belt speed: 2.5 m/s passes, 2.0 m/s fails. Belt friction: 0.5 passes. |
| Delivery: free FUEL from the designed hood exit (6.86 m/s, 62°, spin ratio 1) through HUB contact to an assumed sensor plane at 1.50 m | Scored at 0.93 s | Spin lift CL 0.30 and 30 kN/m contact: both still score | 6.55 to 7.10 m/s score. 6.40 and 7.30 m/s strike the rim and miss. |
| Hang: robot with wheel, bumper-upright and hook contacts; winch on a DC motor line, then 3 s with power removed | 37.8 mm minimum clearance through assessment; 2.2° pitch | No brake: the robot settles onto the carpet, so the hold depends on the brake | Winch current limit: 20 A passes, 15 A stalls before the stroke ends. An 8 V bus with 0.2 upright friction passes. |

What these results change:

- **Acquisition window (F2).** The window is narrow, and the belt speed is imposed. At 3 m/s the contacts dissipate up to 786 W at peak. Predicting whether a motor holds that speed under load needs a loaded drive model or a bench measurement. These belong to the F2 compression and drive-sizing work.
- **Delivery release (F2).** The release state is designed, not measured. The sensor location is an assumption.
- **Hang plane (G3).** The hang trial is a side view, so it cannot show the lateral bumper overlap (now 23.9 mm) or roll; gate G3 tests ±25 mm offsets.

## Verification gates and remaining work

[verification-gates.json](verification-gates.json) records each gate's test, pass numbers, calculation basis and fallback:

- **G1, bulk feed:** at least 22 of 24 crossings in 12 s, five trials. By calculation two lanes supply 7.8 FUEL/s against 2.00.
- **G2, loaded stops:** at most one FUEL lost over ten 0.5 g stops. By geometry the lip stands 77 mm above a FUEL's base, more than its 75 mm radius.
- **G3, hang:** at ±25 mm offset, under 5 mm slip and at least 5 mm clearance; the brake holds 1.5 × 663 N.
- **G4, intake:** 20 of 20 captured within 1.0 s at 17.5–25 mm compression, with the loaded belt at 2.5 m/s or faster.
- **G5, shot calibration:** release inside 6.78–6.94 m/s, and at least 19 of 20 scored from 2.7 m.
- **G6, BUMP:** ten crossings each way with no high-centering.

Remaining work outside these gates:

- **Drive margin.** The drive supply limit of 25 A per module (battery side) keeps the 0.16 V weak-pack margin in loaded transit.
- **Native CAD.** The R3 skeleton in Fusion (including the 714 mm frame saddles) is a follow-up for the single-writer Fusion session.

## Reproduce

Run from the project root:

```powershell
$env:PYTHON = '<cad python>'; $env:AGENT_FRC = '<agent-frc checkout>'
python -I -B design/preliminary/ballistics.py
python -I -B design/preliminary/build_package.py --check --fail-fast   # quick revision loop
python -I -B design/preliminary/build_package.py --check               # issued receipt and player
python -I -B design/preliminary/field_trials.py                        # field-interaction trials and player
python -I -B design/preliminary/rehearsal/variants.py                  # field rehearsal re-run at 2.7 m
python -I -B design/preliminary/build_package.py --check --previous design/preliminary/receipt-R3-PD1-held.json
```

The STEP header carries a fixed timestamp, so an unchanged rebuild reproduces every pinned hash.
