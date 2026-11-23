# Preliminary design study: Chute-fed hood shooter, a floor-fed hood shooter with a chute intake on a 680 × 714 mm swerve base

**Chute-fed hood shooter 1.0 · in progress · robot datum: carpet plane at the frame centre, +X toward the intake, +Y left, millimetres.**

Selected architecture: **R3, the tall floor-fed hooded-flywheel robot**. It replaces the R2C upper and the R2C-T1 screw lift for detailing. The [architecture comparison](architecture-comparison.json) and the [re-run field rehearsal](rehearsal/comparison.json) that selected it are unchanged.

Everything the design checks is in its folder [`cad/preliminary-design/releases/1.0/`](../../cad/preliminary-design/releases/1.0/): the [layout plan](../../cad/preliminary-design/releases/1.0/layout.json), the [checker receipt](../../cad/preliminary-design/releases/1.0/receipt.json), the [missions, cycle map and risk register](../../cad/preliminary-design/releases/1.0/missions.json), the [risk register with its bench tests](../../cad/preliminary-design/releases/1.0/verification-gates.json), the [measurements](../../cad/preliminary-design/releases/1.0/measurements.json) and the [physics trials](../../cad/preliminary-design/releases/1.0/field-trials.json). The numbers quoted below are in those files; where this page and a file disagree, the file is right.

## Why the first blockout was not enough

The first blockout of this architecture was layout-checked, but four of its mechanisms had not been driven by a trial, and one of them did not work. It was never accepted and is folded into version 1.0.

| Question the first blockout left open | What the trials show | What changed |
| --- | --- | --- |
| Can the robot collect a batch of 24? | No. A three-dimensional trial that brings FUEL in through the intake, instead of dropping a heap, stalls with 8 of 24 FUEL in the hopper and the rest back in the intake. They enter low, at the height of the second layer, the front fills first and the rest back out into the intake. | The intake is a chute. Its belt lifts each FUEL up the bumper face and then up the carriage's own back plate to 425 mm, and the top roller throws it in over the top of that plate. The back plate is the hopper's front wall while the intake is deployed. |
| Does the heap feed two lanes at 2 FUEL/s? | Not from a flat full-width floor: it wedges at the lane mouth and feeds about half the batch. | The floor is a channel two lanes wide for its whole length, under sloped shelves. The floor belt runs to the front rail, the feeder rollers stand in the hopper ahead of the rear wall and meet at the centre line, and each lane has its own stage beam. An unjam cycle reverses the belt and nudges the intake carriage 40 mm into the FUEL at the front. |
| What holds a staged FUEL off the flywheel? | Nothing did. A running belt wedged it into the stopped wheel. | One braked feeder roller per lane over a fixed lane deck. The flywheel now runs whenever FUEL is aboard, and a feeder advances a FUEL only with the wheel in its ready band. |
| Does the flywheel hold its speed through a batch? | The earlier 6.8% droop summed friction power, not wheel work. A free wheel under two motors and a speed loop holds the band. The band itself had been scanned too coarsely: at 0.025 m/s steps it is 6.725 to 7.100 m/s, not 6.85 to 7.00. | One steel inertia ring on the flywheel shaft (0.0076 kg m², 2.56 kg), and the setpoint moved to 13.6 m/s so the release sits in the middle of the band. |

Two further changes follow from those. The taller intake cannot stand under the low rung, so the hang now swings the hooks forward first, stows the empty intake between them and then closes on the TOWER. The battery moved under a lift-out shelf panel and gained a strap.

## The trials

`field_trials.py` and `hopper_flow.py` integrate free FUEL, the driven intake belt, the free flywheel and the supported robot with penalty contact. The lane trials and the two surfaces that clamp a staged FUEL use stick-slip friction, because a regularized friction law lets a clamped FUEL creep at any load. Each trial family has a nominal run, a control that removes the feature under test, brackets with a passing and a failing value, and a repeat at a finer timestep. `build_package.py` writes that qualification into the record each mission case pins.

| Interaction | Trial family | Mission case that pins it |
| --- | --- | --- |
| Floor FUEL up the chute and over the back plate | `acquire-*` | the acquire cases |
| Fall to the floor belt, carry to the feeder, stage | `entry-*` | the hopper and stage cases |
| Staged FUEL held off the spinning wheel through the transit | `hold-*` | `loaded-transit` |
| Feed on command, wheel takes it, release | `launch-*` | the launch cases |
| 24 FUEL through the one flywheel inside the band | `batch-*` | the last launch case |
| Collect 24 through the chute, hold through a 0.5 g stop, start and turn, feed all 24 | `hopper-*` | the last feed case |
| Flight into the HUB at five drag and spin conditions | `deliver-*` | the flight cases |
| Level 1 hang and 3 s hold with power removed | `hang-*` | `climb-lift` |

The hopper trial's outcome depends on the arrival pattern, so the cycle is run for sixteen patterns. The trial records in the release folder (`trial-hopper-cycle.json`, `trial-hold.json`, `trial-batch.json`, `trial-hang.json`) give the results, controls and brackets.

## What the trials do not show

- Contact stiffness, damping, friction and rolling resistance are estimates. No FUEL force-deflection curve is available. The risk register turns each of these into a bench test with a pass and a fail value.
- The floor belt and feeder roller speeds are imposed. The intake belt and the flywheel are solved under their motors and current limits.
- The hopper trial models the hopper as rectangles and cylinders taken from `dimensions.py`. The feeder shafts, the hood's thickness and the slot between the front rail and the bumper are not in it.
- A loaded acceleration limit of 0.5 g is assumed for the transit. The field rehearsal credited its cycle times without that limit and is not re-run here.
- The delivery and hang trials ran against dimensioned HUB and TOWER surfaces. The layout check and the review use FIRST's official parts from `cad/field/official/`; the trials have not been repeated on them.
- The checked cases move the tracked FUEL in coarse strokes within 40 mm of the solved trace. The recorded trials play as replays in the review's motion list.

## Reproduce

With the project geometry environment selected and `AGENT_FRC` set to the plugin checkout:

```sh
python -I -B experiments/preliminary-design/field_trials.py
python -I -B experiments/preliminary-design/build_package.py --release cad/preliminary-design/releases/1.0 --check --jobs 4
node "$AGENT_FRC/scripts/design.mjs" effective-readiness . --release cad/preliminary-design/releases/1.0
```

The trials take about twenty minutes on eight cores. `dimensions.py` is the one source for the placed solids and the trial surfaces. Rerun the trials after changing it.
