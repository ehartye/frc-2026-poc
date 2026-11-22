# R3 layout-002: working plan and state

Branch `feature/r3-layout-002`. Goal: issue preliminary release `layout-002` (status in-progress) that the owner can accept as effective. Nothing is staged or published yet. `layout-001` is issued and must not be edited.

**State of the tree: mid-change, not buildable.** `dimensions.py`, `field_trials.py` and the new `hopper_flow.py` hold the new design and trial code. `field_trials.py`'s `run_trials()` and `main()` still call the old trial signatures, and `geometry.py`, `build_package.py`, `review_data.py`, `study.md`, `verification-gates.json` and `retention.json` are untouched. `field-trials.json` is the layout-001 trace and no longer matches `dimensions.py`.

## Baseline

Reproduced: `field_trials.py` at `81dafcf` rewrote byte-identical outputs (21 s). The layout-001 package check was not re-run.

## Design decisions so far

1. **Feeder rollers are the hold-back and the meter (risk 2).** One compliant 2 in roller per lane at x = -60 mm, 8 mm squeeze, each with its own small gearmotor so the lanes feed the one flywheel in turn. Under the rollers the lane floor is a **fixed deck**, and the main floor belt ends at x = -30 mm. A stopped roller over a fixed deck clamps the staged FUEL between two surfaces that do not move. A stopped roller over a running belt does not hold: the FUEL rolls through at half belt speed (seen in the batch model as uncommanded feeds). The flywheel now runs at speed whenever the robot holds FUEL; the back-off, spin-up and stopped-wheel seat of layout-001 are gone.
2. **Flywheel is a free body with motors (risk 1).** Aluminum tube roller plus two steel rings (210 mm OD, 170 mm ID, 8 mm) on webs outboard of the side plates: 0.0176 kg m², 3.36 kg (`dimensions.flywheel_build()`). Two brushless motors direct, 40 A stator and 30 A supply each. The feeder advances a FUEL only with the wheel within 1% of setpoint.
3. **Intake belt is motor-driven in the trial (risk 3).** One motor at 2:1 to the pulley, 30 A supply limit, 1.5 kg equivalent moving mass.
4. **Hopper floor is a two-lane trough (risk 4), still being worked.** Floor two lanes wide for its whole length with a full-length divider, sloped shelves above (30°) out to the side walls, rear wall back at x = -96…-93 so the feeder rollers stand in the hopper, floor belt 1.2 m/s (a free FUEL translates at only 2/7 of belt speed). The battery and electronics would sit under the shelves; the battery service path under a shelf is unresolved.

## What each risk has turned out to be

Numbers are from probe runs of the code on this branch; `field-trials.json` is not yet regenerated.

| Risk | Before | Now | Status |
|---|---|---|---|
| 1 Flywheel droop | 6.8% for a free 0.006 kg m² wheel against ±2.2% | The 28 J per FUEL summed absolute friction power; net wheel work is 17 J. Free 0.0176 kg m² wheel with two motors: 0.9% fall in a shot, 24 FUEL at 4 FUEL/s release 6.81–6.83 m/s at 12 V and 6.80–6.81 m/s at 8.34 V (band 6.70–7.00). Motors off: 6.75 m/s once, then the interlock refuses. Two FUEL at once: 6.78 m/s (6.74 weak pack), which is why the lanes feed in turn. Spin-up 2.6–2.9 s at 60 A | Passing; brackets to record |
| 2 Hold-back | none | Feeder roller over a fixed deck, FUEL staged 10 mm ahead of the roller centre, 27.7 mm clear of the wheel, 3.9 mm clamp. Hold trial (stick-slip friction): holds 1.5 g with a 30 N queue push and a 60 N push (2 mm creep); fails at 120 N; fails with no feeder; fails under the regularized friction law (control for the law) | Passing |
| 3 Intake power | 786 W peak at an imposed 3 m/s | Momentary slip peak; 4.1 J per FUEL. Driven belt holds 2.96 m/s for one FUEL at 19 A; three abreast on a 9 V bus at the 30 A limit dips to 2.37 m/s and captures. Top-roller height 20–50 mm drop all capture | Passing; ramp to add to the trial |
| 4 Feed rate and batch | 2.8 FUEL/s by calculation, batch unevaluated | 3-D batch trial (`hopper_flow.py`): layout-001's flat floor feeds 12 of 24 in 12 s. The new hopper feeds 24 of 24 in 6.5–10.9 s (2.2–3.7 FUEL/s) in nine of nine heaps, half-step included, and 30 FUEL rolled 10°. Fails with a full-height lane divider (21 in 12 s), belt at 0.6 or 0.3 m/s, and ball friction 0.4 (18 in 12 s, all 24 by 13.3 s). Outcomes vary heap to heap, so G1 stays a bench gate with these numbers | Passing nominal; sensitive |
| 5 Mass | 1.76 kg reserve | Not recomputed | To do |
| 6 Hang squaring, BUMP 8.7 mm, battery strap, joints, 7.66 V | — | Not started | To do |

### Hopper decision (risk 4)

Compared in the batch trial, same 24-FUEL heaps:

| Option | Result | Time | Risk | Complexity | Best practice | Maintainability |
|---|---|---|---|---|---|---|
| A. layout-001 flat full-width floor, lane guides, rear wall as gate | 7–15 of 24 in 12 s; wedges at the lane mouth under the pile | 1 | 5 | 1 | 4 | 1 |
| B. Two-lane trough, sloped shelves, full-height lane divider | 15–22; FUEL perch on the divider and shelf edges | 3 | 4 | 3 | 3 | 3 |
| C. Straight two-lane bin, no shelves | feeds, but holds about 21–23 FUEL by volume | 2 | 3 | 2 | 2 | 2 |
| **D. Two-lane trough, shelves, no divider, feeder rollers standing in the hopper, throat ramp and cover, 1.2 m/s belt, intake running** | **24 of 24 in 6.5–10.9 s, nine heaps** | 4 | 1 | 4 | 1 | 4 |
| E. Powered serializer or vectoring floor | not modeled; kept as G1's fallback | 5 | 2 | 5 | 2 | 5 |

Ranks are 1 best. D is selected. What D changes in the layout:

- Floor two lanes wide (336 mm) from the rear wall to the lip, no divider. Rear shelves rise 30° from 270 mm at the channel edge to the side walls, from the rear wall to x = 170. Ahead of that a low shelf (170 → 216 mm) runs under the stowed intake to cheek walls at |y| = 260.
- Rear wall stays at x = -96…-93; the feeder rollers stand in the hopper ahead of it and positively pull the floor FUEL out from under the pile.
- Main floor belt ends at x = -30 and runs at 1.2 m/s (a free FUEL translates at 2/7 of belt speed). Fixed lane deck from there under the rollers and the wheel.
- Throat: a ramp over the rail and bumper top down to the lip, guides turning FUEL in to the channel, a fixed cover from the front upper wall to above the top roller, front corner walls. A FUEL pushed forward off the ramp drops into the intake pinch and the running intake throws it back.
- Battery and right electronics panel sit under the rear shelves. **Open:** the left shelf must open for the battery lift; the service case needs a staged extraction.
- Capacity falls with the shelves; recompute the premise.

## Next steps, in order

1. (Done) Hopper settled as option D; trial set with controls and brackets is `hopper_flow.run_trials()`.
2. Rewrite `field_trials.run_trials()`/`main()` for the new chain (acquire → entry to stage → launch with the free wheel → deliver), add `hold`, `batch`, spin-up and the hopper trials, bump the issue to R3-PD3, extend the player template for the new trial kinds.
3. `geometry.py`: feeder rollers and motors, lane deck, divider, shelves, rings, moved rear wall, front corner walls, battery strap; then `build_package.py` (phases, `freePath` for the flight and throw cases, per-member mounts and joints, `scenarioId`, mass and electrical rows, capacity code that hardcodes the old wall at -93 and pinch at -150).
4. Risks 5 and 6, then gates, retention review and study.
5. Check to `layout-checked` with `--previous` the published layout-001 receipt and `--output`; validate the scene; stage.
6. Independent adversarial review (subagent, model fable), fix, PR (do not merge), wiki pages.

## Rules given during this session

- **Effective bar:** whole mission cycle checked for clearance, mass and voltage; every mission-critical interaction passes a physics trial with a control and sensitivity brackets; the mission animation is trial-driven; every open risk closed by design change or recorded as a bench test with pass/fail numbers. `plugin-backlog` is adding a readiness report command; use it when it lands. Do not mark the release effective; the owner does.
- **One animation list in one view:** trials become entries in the stock viewer's motion selector, not separate player pages. Ask `plugin-backlog` whether trial-driven replay entries have landed before staging; if not, tell the coordinator before staging with separate players.
- **File layout:** the repository is the project root for the check; the review page and scene live in `cad/preliminary-design/releases/layout-002/`, never at a project root; no re-rooting or copying held files in. Wait for the plugin change that allows a sub-folder `view`.
- **Tidy in the PR:** remove `experiments/preliminary-design/review/package-motion.html` and `package-motion.geometry.json.gz` if no issued receipt pins them, and say so.
- **Front page and README:** `withdraw-2026` pins the README and site to layout-001 as current. Do not land a release that changes `current` before its withdrawal PR merges; changing `current` needs a policy PR and approval advance. Coordinate timing with it.
- No Fusion. Commit with explicit paths. Never git in the wiki vault. Send plugin friction to `plugin-backlog`.

## Plugin friction to send (not yet sent)

- None confirmed against the plugin yet; the work so far is project trial code.

## Readiness report (landed after parking)

Agent FRC 0.112.0 (`5bc3f97`, PR 178) adds `node scripts/design.mjs effective-readiness PROJECT`. It is informational (exit 0). Not yet run here. To satisfy it:

- `missions.json` declares a `cycle` map (acquire, retain, transfer, deliver, reset, endgame, park, service → checked cases, or `notApplicable` with a reason) and a `risks` register (`closedBy`, or `benchTest` with measure, pass and fail values).
- Each pinned trial file carries a `qualification` record: passing result, rejected control, brackets with a passing and a failing value, and a timestep check.
- Contract: `docs/preliminary-design.md#judge-readiness-to-be-marked-effective` in the plugin. Re-copy the plugin's `stage.py` before staging; it prints the report with `--set-status RELEASE effective --readiness PLUGIN/scripts/effective-readiness.mjs`.
