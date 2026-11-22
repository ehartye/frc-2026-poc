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

| Risk | Before | Now (probe runs, not yet recorded in `field-trials.json`) | Status |
|---|---|---|---|
| 1 Flywheel droop | 6.8% for a free 0.006 kg m² wheel against ±2.2% | The 28 J per FUEL summed absolute friction power; the net wheel work is 17 J (17.8 J in the layout-001 trial itself). With the free 0.0176 kg m² wheel and motors, the wheel falls 0.8% in a shot and releases at 6.85 m/s. A 24-FUEL batch at 4 FUEL/s releases 6.84–6.85 m/s at 12 V and 6.83–6.84 m/s at 8.34 V (band 6.70–7.00). Motors off: 6.78 m/s for one shot, then the interlock refuses the next. Spin-up from rest 2.6–2.9 s at 60 A battery-side | Passing in probes; brackets and half-step not yet run |
| 2 Hold-back | none | Staged FUEL clamped 3.9 mm, 22.8 mm clear of the wheel. The `hold()` trial (belt running, 0.5–1.5 g, queue push) is written but not yet run | Design change made; trial to run |
| 3 Intake power | 786 W peak at an imposed 3 m/s | 786 W is a momentary slip peak; the belt gives each FUEL 4.1 J. Driven belt stays at 2.96 m/s for one FUEL at 19 A; three abreast on a 9 V bus at the 30 A limit dips to 2.37 m/s and still captures | Passing in probes |
| 4 Feed rate and batch | 2.8 FUEL/s by calculation, batch unevaluated | **Open.** Wheel side sustains 4 FUEL/s. Hopper side (`hopper_flow.py`, 24 free FUEL in 3-D): the layout-001 flat floor with lane guides jams (12–15 of 24 in 12 s). The trough feeds 20–22 in 5–9 s (2.3–3.2 FUEL/s), then strands the rest; seed 2 fed only 11 | Not passing |
| 5 Mass | 1.76 kg reserve | Not recomputed. New wheel 3.36 kg sits inside the old 2.7–3.6 kg wheel range; feeders, deck, divider and shelves add mass | To do |
| 6 Hang squaring, BUMP 8.7 mm, battery strap, joints, 7.66 V | — | Not started | To do |

Findings in the trough model that still need a design answer:

- **FUEL strand on the bumper-top shelf** ahead of the front lip (2–4 of 24 at x ≈ 382 mm), out of reach of the belts. The intake top roller does not return them. Needs a throat ramp or closure that leaves the acquisition path alone.
- **Seed 2 stalls with both lanes empty** while 12 FUEL sit bridged above the trough on the shelves and rear wall. The 336 mm trough is 2.2 FUEL wide. Candidates: steeper or lower-friction shelves, a wider trough, agitation from the exposed feeder roller tops, or dropping the full-height divider to a low rail.
- **Front corners were open in layout-001** between about 222 and 482 mm height outboard of the intake; corner walls are assumed in the model and must be drawn.
- The 30-FUEL, 10° tilt case lost 3 FUEL over the wall or throat.

If the hopper cannot be made to pass, compare real alternatives (R3L, a different feed) with the rehearsal tooling using `rehearsal.waitCycles: "yield"`, and rank options on time, risk, complexity, best practice and maintainability.

## Next steps, in order

1. Settle the hopper: fix the throat stranding and the bridging, then pass nominal, three seeds, half-step, friction brackets, a control and the adverse tilt case.
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
