# R3 preliminary design: a floor-fed hood shooter on a 680 × 714 mm swerve base

**Issue R3-PD2 · robot datum: carpet plane at the frame centre, +X toward the intake, +Y left, millimetres.**

Selected architecture: **R3, the tall floor-fed hooded-flywheel robot**. It replaces the R2C upper and the R2C-T1 screw lift for detailing.

**Status: `layout-checked`** on Agent FRC 0.98.0 (e8bceb4), resubmitted against the held [R3-PD1 receipt](receipt-R3-PD1-held.json) with `--previous … --require-checked --write-view` (exit 0). Its conceptual delivery-pose hold clears through a series-wide `stationPosition` replay: every B2 `blue-hub` attempt in the re-run series stands 32.2–48.6 in from the station centre, every footprint is clear, and each match with attempts delivers. [Receipt](receipt.json).

[Checker receipt](receipt.json) · [Layout plan](layout.json) · [Placed STEP](package.step) · [Motion study](paths.json) · [Budgets](budgets.json) · [Measurements](measurements.json) · [Verification gates](verification-gates.json) · [Re-run rehearsal](rehearsal/comparison.json) · [Architecture comparison](architecture-comparison.json) · [Retention review](retention.json) · [Ballistics](ballistics.json) · [Rules addendum](construction-rules.json) · [Shared dimensions](dimensions.py) · [Field trials](field-trials.json) · [Review index](review/index.html)

## What changed in this revision: the tracked FUEL follows the physics trials

The tracked FUEL's path was a hand-drawn waypoint path with a 3 mm reserve around every guiding surface. It is now fitted to the solved traces of [field_trials.py](field_trials.py): 28 strokes, each within 1.5 mm of every traced sample ([trace_cases.py](trace_cases.py)). Rebuilding it from the traces exposed three defects, and solving the missing transfers exposed more.

- **One source for geometry.** [dimensions.py](dimensions.py) feeds both the placed solids and the trials, so the bumper, intake, floor lane and shooter surfaces have one definition. The HUB, the TOWER and the hook are still written separately in the trials and in geometry.py.
- **Intake drawn at its working squeeze.** The trial captures only when the belt stands 17.5 mm or more inside one FUEL diameter from the bumper face (about 9.6 mm of indentation on each side), so the squeeze is a layout dimension.
  - The belt module moves 26 mm aft, to 20 mm inside one FUEL diameter from the bumper face. The top roller drops 20 mm.
  - Front extension falls from 270.6 mm to 244.6 mm.
  - The slide's drop grows from 62 mm to 90 mm so the lower belt clears the bumper top while deploying, and the carriage plates stop at 385 mm to pass under the front upper wall.
- **Contact is declared, not hidden.** Where a trial solved the FUEL against a surface, that pair is a `payloadCompression` rule in its case. Its limit is the trial's deepest indentation in that stroke's own time window, plus the stroke fit, plus a 0.2 to 0.4 mm sweep margin. The bumper face takes 11.2 mm. The 83.8 mm³ overlap at first contact was this indentation.
- **Hopper entry is now a trial.** No trial covered capture to seat, and the drawn stroke passed through the belt cleat (22,571 mm³).
  - The captured FUEL crosses the lip, lands on the floor belts and rolls aft on its capture momentum.
  - With the old 3 mm reserve around the wheel, nothing stopped it: it rolled up the hood and out of its end at 0.86 m/s (`entry-superseded-3mm-reserve-pinch`). The pinch is therefore drawn at a 12 mm wheel-to-hood squeeze, which makes the stopped wheel the seat stop.
  - With the floor belts stopped it comes to rest against the wheel, 0.02 mm into it. A belt running at 0.05 m/s or more presses it 3.2 to 5.9 mm in, and a spin-up then feeds it early.
- **The belt cleat is removed.** The traced path strikes it, it had no return path in a 7.5 mm belt bed, it sat across two separate belts, and the belt's back-off would drive it into the lip. Flat reversible belts do its work, and the `index` case is gone.
- **Launch is now a trial.** The belt backs the FUEL off the stopped wheel, the wheel spins up over 1.25 s with the belt stopped, then the belt feeds. That ramp keeps the wheel's accelerating power at 334 W, which is 47 A at the 8.34 V weak-pack launch bus if the drive is 85% efficient, inside the launch duty's 60 A flywheel bound. The FUEL releases at 6.86 m/s and 61.9°, and the delivery trial starts from that state, so the release point is one number. It was 13.7 mm from the old trial's first sample because that trace omitted its start.
- **Shooter block.** The flywheel axis drops 18 mm to 297.9 mm so the hood stays tangent to the belt top. The hood ends at −149.5° about the axis, 2.5° short of the 62° tangent, because the FUEL leaves 4° late once the hood ends.
- **Shooter mass line.** A wheel with 0.006 kg m² on a 50.8 mm radius weighs at least 2.3 kg, so the 5.0–6.8 kg shooter line could not hold it with two side plates, the hood and two motors. The line is now 6.5–9.2 kg from the drawn plates and hood. R103 mass becomes 37.2–50.4 kg and the reserve falls from 4.16 to 1.76 kg.
- **Hang mass.** The hang trial ran at 67.6 kg. It now runs at 70.3 kg, at the running mass upper bound.
- **Installed pose.** The tracked FUEL is drawn where the mission finds it, on the carpet. The shooter withdrawal is checked with the floor lane empty: a FUEL seated at the wheel stands over the hood's lower lip and blocks the lift.

What the new trials leave open:

- **No hold-back.** Nothing restrains the seated FUEL forward. Without the back-off, a FUEL at rest 0.23 mm into the stopped wheel still launches at speed and one 0.44 mm in is fed early. That threshold comes from the penalty contact springing a lightly pressed FUEL clear; it is not a measured limit. With the back-off a FUEL 3.2 mm in launches at speed. A FUEL wedged 5.9 mm in by a running belt is not freed by the back-off. Gate G7.
- **Batch collection.** The entry trial is one FUEL in an empty lane with the belts stopped. How 24 FUEL collect and convey is not evaluated.
- **Feed rate.** A free FUEL rolls at 0.22 m/s on the 0.6 m/s belt, which is 2.8 FUEL/s for two lanes against 2.00, not the 7.8 the belt-speed calculation gave.
- **Flywheel load.** The wheel does 28 J of work per FUEL. A free 0.006 kg m² wheel would lose 6.8% of its speed, three times the ±2.2% scoring band. The trial holds wheel speed. More inertia does not fit: 2% droop needs about 0.020 kg m², at least 7.7 kg at the rim, against a 1.76 kg reserve. Gate G5.
- **Scoring band.** Only 6.70 to 7.00 m/s scores at the nominal drag and spin lift and at all four drag and spin corners. 6.55 m/s misses at the high-drag, high-spin corner and 7.15 m/s at both low-drag corners. The band's ends score off the top plate or the cavity wall; the point-mass screen's clean band at this release is 6.76–6.93 m/s.
- **Estimated contact properties decide the launch.** 10 and 30 kN/m score; 7.5 kN/m releases at 6.50 m/s. The squeeze bracket is a force bracket at 15 kN/m.
- **Intake belt load.** The acquisition contacts dissipate up to 786 W at the imposed 3 m/s, above the intake's 30 A supply limit, and the trial fails at 2.0 m/s. Gate G4.
- **Seat position depends on damping.** At damping ratio 0.3 the FUEL rests against the wheel. At 0.20 and 0.10 it rebounds and rests 7 and 62 mm clear of it. It is still seated, and the launch from 62 mm still scores, 0.3 s later.
- **Carrier-free strokes.** The carpet approach, free flight and rolling on stopped belts have no `transportedBy`. Their trial windows are in each case basis.

## What changed from R3-PD1

- **Field rehearsal re-run at the 2.7 m delivery pose** (the plugin's `rehearsal-series.mjs` on project variants of the kickoff profile).
  - Slot 2's AUTO and depot-shift deliveries move to 2.70 m from the HUB centre. They stay inside the profile's 52 in legal-pose screen; the depot delivery bearing turns from 30° to 24°.
  - **Re-run on Agent FRC 0.84.** Rehearsal results from before 0.84 were understated by permanent robot-to-robot wait cycles: the earlier r3-2p7m series held 27 permanent cycles in which B2 or R2 sat frozen against slot 3 through every shift, and so did the kickoff baseline.
  - Every series now opts into `waitCycles: "yield"` and shares one partner deconfliction. Slot 3's reserve moves to the role-and-support study's deep reserve, and the neutral runner routes east of the depot lane and delivers south of the HUB axis. Slot 2 is drawn at R3's 714 mm width. `--report-deadlocks` gives these wait-cycle counts:
    - **Baseline:** 4 cycles, all cleared, 0 permanent.
    - **R3 and R3L depot:** 0.
    - **R3L trench, sharing the corridor with the neutral runner:** 28 cycles, 21 permanent. Slot 2 and slot 3 meet head-on in the single high-trench corridor and neither can detour.
    - **R3L trench solo** (slot 3 holds the reserve): 0.
  - Slot 2 credits **124 FUEL in both the baseline and the 2.70 m R3 series**, so the pose costs nothing. The alliance totals are 366 for the baseline and 382 for R3.
  - Slot-2 FUEL credited, per match and in total:

    | Series | Own-zone supply | Neutral return | Missed preload | Total |
    |---|---|---|---|---|
    | Kickoff baseline | 44 | 36 | 44 | 124 |
    | R3 at 2.7 m | 44 | 36 | 44 | 124 |
    | R3L depot | 44 | 36 | 44 | 124 |
    | R3L trench, shared or solo | 16 | 8 | 16 | 40 |

  - The earlier "96 against 104" result is withdrawn. It came from deadlocked rehearsals in which slot 2 sat frozen against slot 3.
  - **Why the alliance totals differ (366 for the baseline against 382 for R3).** The difference is a gain, not a loss, and it comes from the 2.7 m pose. Both series use the same partner deconfliction. Slot 2's credits trade ±4 between the alliances (timing against the active windows) and net to zero. The +16 comes entirely from the slot-3 neutral runners, which each credit one more 4-piece delivery in Neutral return and in Missed preload. Moving slot 2's delivery out to 2.7 m clears it from the runner's delivery corridor. Nothing here is a cost to accept.
  - **Why R3 beats R3L when both score 124.** The rehearsal models only footprint, height and route, so R3 and R3L on the depot route tie at 124, match for match. Three things decide it:
    - **Capacity:** by free volume at 0.45–0.55 packing, R3 holds 37.7–46.0 FUEL and R3L 29.4–35.9.
    - **BUMP:** R3 clears it by 8.7 mm at the bumper corner and 24.3 mm at the belly. R3L's 26 mm belly gives −43.7 mm and would high-centre, which leaves it the TRENCH route, worth 40.
    - **Climber:** R3L needs an extra telescoping raise before its hooks swing.

  - R3L on the depot route matches R3. On the TRENCH route it credits 40 shared and 40 solo, with alliance totals of 242 and 234. **R3 stays selected**, and the 2.7 m pose conclusion holds.
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

**R3's allocation.** Flat floor belts feed the bottom FUEL layer straight into a 4 in flywheel pinch. A fixed hood wraps the piece about 62° and releases it at 62° elevation. A diagonal slide carries a vertical belt over the bumper; the belt lifts a floor FUEL against the bumper face. A straight slide never sweeps beyond the R105 reach. The first issue's folding intake swept 360 mm past the perimeter mid-motion.

**Release height and pose.** [ballistics.py](ballistics.py) includes drag (Cd 0.35–0.60) and the downward spin lift a hood shot produces (CL 0–0.30). R3 releases at 0.267 m in the launch trial, so it needs about 2.4 m to the HUB centre before every drag-and-spin corner enters with a usable band (0.15 m/s wide at 2.4 m, 0.03 m/s at 2.2 m). A 0.60–0.70 m release enters from 2.0 m. R3 therefore trades the rehearsed delivery pose for one fewer transfer, and the rehearsal must be re-run with R3 delivering at 2.7 m (robot centre).

**The low variant (R3L) does not lose on capacity.** By exact free volume at 0.45–0.55 packing:

- R3 holds 37.7–46.0 FUEL.
- R3L holds 29.4–35.9 FUEL. It meets 24 with less margin.

A rigid stacked-lattice screen finds only 8 in R3 and 7 in R3L. It is kept as a lower bound, not a decision measure. R3L buys certain TRENCH passage but needs one more climber motion and gives up the BUMP option. **If the BUMP crossing premise (F5) fails, select R3L.**

| | A: R2C-T1 incumbent | **B: R3 selected** | C: R3L trench-runner |
|---|---|---|---|
| Custody | 5 handoffs; 3 of 24 scored | 3 handoffs; tracked piece follows the solved trials carpet to HUB | 3 handoffs |
| Shot | 7 of 9 short | 6.86 m/s from the launch trial; delivery trials score 6.70–7.00 m/s at every drag and spin corner, from 2.43 m | as B, 68 mm lower |
| Mass (R103 52.16 kg) | no ledger | 37.2–50.4 kg, 1.76 kg reserve; ≤57.9 kg with bumpers | about 1 kg less |
| Weak-pack bus | not commissioned | 7.66 V minimum, needs 7.5 V | as B |
| Capacity (free volume) | 24 (box screen) | 37.7–46.0 | 29.4–35.9 |
| Swept envelope | 754 mm stowed | 750 mm; front 244.6 mm; one side; no start overhang | 534 mm, passes TRENCH |
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

| Case | What happens | Time | Shared resource |
|---|---|---|---|
| intake-deploy | Carriage slides 280 mm forward and 90 mm down over the bumper | 0.4 s (estimate) | slide actuator |
| acquire-approach-1 | Robot drives onto the floor FUEL; no mechanism moves it yet | 0.19 s (trial) | drive |
| acquire-climb-1…7, acquire-over-1 | Bottom pulley draws it under, the back run lifts it up the bumper face, the top roller pushes it aft (`transportedBy` intake) | to 0.44 s (trial) | intake belt |
| acquire-throw-1 | Thrown by the roller, it flies over the bumper top; no mechanism touches it | to capture at 0.53 s (trial) | none |
| hopper-drop-1…2, hopper-roll-1…5 | Falls past the lip, lands on the stopped belts and rolls to the stopped flywheel on its capture momentum | reaches the wheel at 0.32 s, at rest by 3.0 s (trial) | none: belts stopped |
| loaded-transit | Robot drives loaded to the shot pose (in the robot frame the field moves) | 3–5 s (estimate) | drive current |
| launch-back-off-1 | Belt reverses at 0.3 m/s and rolls the FUEL 69 mm off the wheel (`transportedBy` floor belts) | 0.5 s (trial schedule) | floor belt |
| launch-coast-1 | Belt stopped while the flywheel spins up; the FUEL coasts another 29 mm | 1.25 s (trial schedule) | flywheel |
| launch-feed-1 | Belt feeds at 0.6 m/s; the FUEL rolls to the wheel at 0.22 m/s (`transportedBy` floor belts) | 0.45 s (trial) | floor belt |
| launch-wrap-1…4 | Wheel takes it, rolls it up the hood and releases it (`transportedBy` floor belts and shooter) | 0.05 s (trial) | flywheel speed |
| flight-1…4 | Free flight into the HUB, off the cavity wall, through the sensor plane | 0.96 s (trial) | none |
| tower-lateral, tower-forward | Bumper stops 5 mm from the uprights with the intake between them | 3 s (estimate) | drive |
| climb-reach, climb-seat, climb-lift | Hooks swing 180° inboard, then seat within 2 mm of the rung (required contact, passed), then lift the robot 70 mm | 3 s (estimate) | winch |
| park-lower | Robot returns to the carpet | 1 s (estimate) | winch |

A FUEL case plays its fitted stroke at a uniform rate; the trial's own timing is in the [player](review/field-interaction.html).

The intake runs while driving. The floor belts stay stopped while a FUEL enters and the flywheel is stopped until the belt has backed the first FUEL off it. The climb cannot overlap scoring.

## Check status

`node scripts/design.mjs preliminary-check <project> experiments/preliminary-design/layout.json --require-checked --write-view` on Agent FRC 0.98.0:

- **With `--previous experiments/preliminary-design/receipt-R3-PD1-held.json`:** `layout-checked`, exit 0 (`priorDecisions[0].repeatVerified: true`, the held acceptance followed through its declared relocation). This is the issued [receipt](receipt.json).
- **Release inputs:** the same package, built with `--release cad/preliminary-design/releases/layout-001`, is `layout-checked` in a scratch copy without `--previous`, on 0.98.0 and on 0.101.2 (ea9981c). From 0.100.0 the checker writes a view only at the project root, so this folder's receipt, which needs the repository root for the held-receipt relocation, is issued on 0.98.0. The release's own receipt and player are regenerated when the release is staged.

What passes:

- **Cases:** all 36 cycle cases and both service withdrawals pass in about 20 s.
- **FUEL contacts:** 51 payload-compression rules, each bounded for its whole stroke. The deepest are 10.9 mm into the bumper face, 10.2 mm into the intake belt, 9.4 mm into the hood, 7.7 mm into the flywheel and 7.2 mm into the HUB cavity wall.
- **Control:** raising the hood 8 mm presses it 16.6 mm into the FUEL in `launch-wrap-3` against an 11.15 mm limit, and the check rejects it.
- **Required contact:** both hooks seat within 1.5 mm of the rung.
- **Budgets:** R103 mass is 37.2–50.4 kg (1.76 kg reserve; the shooter line rose). The weak-pack minimum is 7.66 V against 7.5 V, in loaded transit. The current rows are unchanged; the acquire and launch rows now state what the trials impose against them.
- **Premises:** all thirteen are within range.
  - `start-overhang` 0 mm.
  - `swept-height` 750 mm.
  - `swept-front-extension` 244.6 mm (was 270.6: the belt module moved aft).
  - `swept-other-extension` 0 mm.
  - `sides-extended` 1.
  - `with-bumpers-mass` 57.9 kg (was 55.5: the shooter line).
  - `hopper-capacity` 37.7 and `start-capacity` 37.1 (was 37.2).
  - `shot-window` 2.428 m (was 2.436: the release point is now the launch trial's). The range starts at 2.4 m.
  - `delivery-pose` 48.65 in, and `delivery-hub-distance` 2.70 m.
  - `bump-crossing` 8.7 mm.
  - `hang-bumper-overlap` 23.9 mm.

### Why the held issue stayed reopened before 0.82.2

The contract requires passing the held receipt: "Keep the held receipt in project custody and pass it separately on resubmission." It then limits what can clear a held field premise: "Supported replay inputs include a named program step’s dwell, robot speed, height and heading, and a modeled front pickup mouth. … An unsupported repeat stays open." It also states that "An initial review without a supplied prior receipt cannot clear a historical hold."

Agent FRC 0.82.0 adds a `stepPosition` replay. R3-PD2 registers `delivery-pose` in its shipped form: unit in, B2 in "Neutral return", Shift 1, step 3 "Attempt HUB delivery; credited" at station `blue-hub`, stand-off 48.649 in (2.70 m from the HUB centre). The replay passes: the saved result reproduces, the step is a scoring attempt, the footprint is clear and B2 delivers there in Shift 1. The hold still does not clear, because the check also requires the held R3-PD1 acceptance to carry the same `fieldInput` (`selection==before.get("fieldInput")` in `verify_reopens()`), and that acceptance predates the field and has none. Its bytes are pinned by the held receipt, so it cannot be amended. [Evidence](rehearsal/delivery-pose-evidence.json).

The [package player](review/package-motion.html) and its compressed geometry are committed; regenerate them with `--write-view`. The [review index](review/index.html) links it with the committed [field-interaction player](review/field-interaction.html).

## Field interactions

[field_trials.py](field_trials.py) integrates each mission-critical interaction on the dimensions the layout draws. It writes the [trace](field-trials.json) and a [player](review/field-interaction.html): pick a trial, scrub its run timestamps, and read the outcome, events, imposed and solved quantities, deepest indentations and solver settings. All trials use penalty contact with Coulomb friction, and their stiffness, friction and rolling-resistance values are estimates. No FUEL force–deflection curve is available, so every indentation is a model result.

The tracked FUEL is one chain. `acquire-nominal` ends at capture. `entry-nominal` starts from that state and ends at rest. `launch-nominal` starts from that seat and ends at release. `deliver-nominal` starts from that release state.

| Interaction | Nominal result | Control | Bracket (pass / fail), other inputs held |
|---|---|---|---|
| Acquisition: belt pulls the FUEL under its bottom pulley, lifts it against the bumper face, top roller pushes it over | Captured in 0.53 s, moving aft at 1.17 m/s | Belt and roller locked: not captured, so the belt does the transfer | Squeeze: 17.5 mm passes, 15 mm fails. Belt speed: 2.5 m/s passes, 2.0 m/s fails. Belt friction: 0.5 passes. Bumper friction: 0.3 passes, 0.2 fails. |
| Hopper entry: captured FUEL past the lip, onto the stopped floor belts, to the stopped flywheel | At rest against the wheel, 0.02 mm into it, 437 mm aft of capture, 3.0 s after capture | Set down at rest behind the lip it stays in the throat, so the intake's throw does the transfer. With the earlier 3 mm reserve pinch it rolls out through the shooter | Floor belt speed: stopped passes; 0.05, 0.2 and 0.6 m/s press it 3.2 to 5.9 mm into the wheel and fail. Rolling resistance 0.01 to 0.20 passes. A 2.5 m/s intake belt passes. Damping 0.20 and 0.10 pass, resting 7 and 62 mm clear of the wheel. |
| Launch: belt backs off, wheel spins up, belt feeds, wheel rolls the FUEL up the hood | Released at 6.86 m/s, 61.9°, spin ratio 0.96, 2.26 s after the sequence starts | Belt stopped for the feed: never released. Without the back-off: from the nominal seat (0.02 mm into the wheel) and from 0.23 mm in it still scores, so the back-off is not needed there; from 0.44 mm or 3.2 mm in, the wheel takes it during spin-up and releases near 1.5 m/s. With the back-off the 3.2 mm seat passes | Squeeze: 8 and 16 mm pass, 6 and 20 mm fail. Wheel friction: 0.5 passes, 0.3 fails. Contact stiffness: 10 and 30 kN/m pass, 7.5 kN/m fails. Wheel surface: 13.1 and 13.6 m/s pass, 13.0 and 13.8 m/s fail. A seat wedged 5.9 mm in fails even with the back-off. |
| Delivery: free FUEL from the launch release through HUB contact to an assumed sensor plane at 1.50 m | Scored at 0.96 s off the cavity wall | All four drag and spin corners (Cd 0.35 and 0.60, CL 0 and 0.30) and 30 kN/m contact score | 6.70 to 7.00 m/s score at every corner. 6.55 m/s misses at Cd 0.60 with CL 0.30 and 7.15 m/s at both Cd 0.35 corners; 6.40 and 7.30 m/s miss everywhere. |
| Hang at 70.3 kg: robot with wheel, bumper-upright and hook contacts; winch on a DC motor line, then 3 s with power removed | 37.5 mm minimum clearance through assessment; 2.2° pitch | No brake: the robot settles onto the carpet, so the hold depends on the brake | Winch current limit: 20 A passes, 15 A stalls before the stroke ends. An 8 V bus with 0.2 upright friction passes. |

Half the timestep gives the same outcome in every trial. Capture moves by 1 ms, release speed by 0.003 m/s and the scoring time by 0.4 ms. The entry trial runs at 0.05 ms, half the others' step, because its rest time needed it: 2.33 s at 0.1 ms, 3.03 s at 0.05 ms and 3.04 s at 0.025 ms, with the same seat position.

The superseded belt cleat is kept as a control (`entry-superseded-cleat`). The FUEL strikes it 1.8 mm deep, hops it and still seats, so the cleat did not block entry; it is removed for the reasons above.

What these results change:

- **Acquisition window (F2).** The window is narrow, and the belt speed is imposed. At 3 m/s the contacts dissipate up to 786 W at peak. Predicting whether a motor holds that speed under load needs a loaded drive model or a bench measurement.
- **Entry depends on stopped belts.** The seat exists only while the floor belts are stopped. That conflicts with conveying a batch, which is open.
- **Launch depends on where the FUEL rests.** A FUEL at rest 0.44 mm or more into the wheel is fed early unless the belt backs it off; at 0.23 mm it is not. That threshold is a property of the penalty contact, not a measurement. The back-off is a margin, not a requirement, at the nominal seat. No hold-back is designed (gate G7).
- **Wheel work.** 28 J per FUEL and 1.5 kW peak friction power at the imposed speed. A free wheel would lose 6.8% of its speed against a ±2.2% scoring band (gate G5).
- **Delivery release.** The release state is solved from imposed belt and wheel speeds, not measured. The sensor location is an assumption.
- **Hang plane (G3).** The hang trial is a side view, so it cannot show the lateral bumper overlap (now 23.9 mm) or roll; gate G3 tests ±25 mm offsets.

## Verification gates and remaining work

[verification-gates.json](verification-gates.json) records each gate's test, pass numbers, calculation basis and fallback:

- **G1, bulk feed:** at least 22 of 24 crossings in 12 s, five trials. At belt speed two lanes would supply 7.8 FUEL/s; a free FUEL rolls at 0.22 m/s in the launch trial, which is 2.8 FUEL/s against 2.00.
- **G2, loaded stops:** at most one FUEL lost over ten 0.5 g stops. The lip stands 61 mm above the floor belts, so by statics a floor FUEL needs about 5.2 g to roll over it.
- **G3, hang:** at ±25 mm offset, under 5 mm slip and at least 5 mm clearance; the brake holds 1.5 × 690 N (70.3 kg). The cable load peaks at 1043 N during the lift in the trial.
- **G4, intake:** 20 of 20 captured within 1.0 s at 17.5–25 mm compression, with the loaded belt at 2.5 m/s or faster.
- **G5, shot calibration:** release inside 6.70–7.00 m/s (±2.2%) with the wheel speed measured through each shot, and at least 19 of 20 scored from 2.7 m.
- **G6, BUMP:** ten crossings each way with no high-centering.
- **G7, staging and launch sequence:** 10 of 10 FUEL at rest no more than 1 mm into the stopped wheel, and 10 of 10 released inside 6.70–7.00 m/s with the wheel at speed. If it fails, a hold-back ahead of the flywheel moves the pinch forward and reopens the hopper layout.

Remaining work outside these gates:

- **Drive margin.** The drive supply limit of 25 A per module (battery side) keeps the 0.16 V weak-pack margin in loaded transit.
- **Native CAD.** The R3 skeleton in Fusion (including the 714 mm frame saddles) is a follow-up for the single-writer Fusion session.

## Reproduce

Run from the project root:

```powershell
$env:PYTHON = '<cad python>'; $env:AGENT_FRC = '<agent-frc checkout>'
python -I -B experiments/preliminary-design/ballistics.py
python -I -B experiments/preliminary-design/field_trials.py                        # trials, traces and player (run first: the package is fitted to them)
python -I -B experiments/preliminary-design/build_package.py --check --fail-fast   # quick revision loop
python -I -B experiments/preliminary-design/rehearsal/variants.py                  # field rehearsal re-run at 2.7 m
python -I -B experiments/preliminary-design/build_package.py --check --previous experiments/preliminary-design/receipt-R3-PD1-held.json   # issued receipt and player
python -I -B experiments/preliminary-design/build_package.py --release cad/preliminary-design/releases/layout-001 --check                   # review inputs, checked in a scratch copy
```

The builder refuses traces solved for other dimensions. The STEP header carries a fixed timestamp, so an unchanged rebuild reproduces every pinned hash.
