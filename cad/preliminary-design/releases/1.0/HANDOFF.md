# Handoff to detailed design: Chute-fed hood shooter 1.0

Written by `experiments/preliminary-design/handoff.py` from the files in `cad/preliminary-design/releases/1.0/`. The design is in progress until the owner marks it effective. Lengths are millimetres in the robot datum unless a unit is given.

## Design

| Item | Value | File |
| --- | --- | --- |
| Name and version | Chute-fed hood shooter 1.0 | `docs/preliminary-design/releases.json` |
| Blockout | 70 named solids, one per functional volume, in 18 groups | `package.step`, groups in `layout.json` |
| Solid names | Plain words with handedness last, such as `feeder roller left`; envelopes say so in their explanation | `layout.json` presentation.components |
| Field parts | 24 parts of FIRST's official HUB and TOWER at the shot pose | `field/*.step`, source in `cad/field/official/` |

## Frame and datums

| Datum | Value | File |
| --- | --- | --- |
| Origin and axes | Robot datum: carpet plane at the frame centre, +X toward the intake, +Y left, millimetres | `layout.json` datum |
| Floor | Z = 0 at the carpet | `layout.json` datum |
| Mount: floor belts on floor pan | (0, 0, 100). Belt bed rests on the floor pan | `layout.json` mounts |
| Mount: feeder roller left on hopper liner left | (-60, 169, 250.514). Left roller shaft runs in a bearing block on the channel wall of the left liner; its gearmotor hangs from the same block | `layout.json` mounts |
| Mount: feeder motor left on hopper liner left | (-60, 169, 248.514). Gearmotor flange on the bearing block outboard of the channel wall | `layout.json` mounts |
| Mount: feeder roller right on hopper liner right | (-60, -169, 250.514). Right roller shaft runs in a bearing block on the channel wall of the right liner | `layout.json` mounts |
| Mount: feeder motor right on hopper liner right | (-60, -169, 248.514). Gearmotor flange on the bearing block outboard of the channel wall | `layout.json` mounts |
| Mount: shooter on frame rail rear | (-327, 0, 120.65). Shooter side plates bolt to the rear rail top | `layout.json` mounts |
| Mount: intake carriage plate left on intake slide rail left | (300, 266, 400). Left carriage plate runs on the two-stage slide; the fixed stage is drawn | `layout.json` mounts |
| Mount: intake carriage plate right on intake slide rail right | (300, -266, 400). Right carriage plate runs on the two-stage slide; the fixed stage is drawn | `layout.json` mounts |
| Mount: intake belt module on intake carriage plate left | (560, 255, 300). Belt module frame spans the two carriage plates | `layout.json` mounts |
| Mount: intake top roller on intake carriage plate left | (495.5, 255, 565). Top roller shaft runs in bearings in the two carriage plates | `layout.json` mounts |
| Mount: intake back plate on intake carriage plate left | (400, 255, 300). Back plate flanges bolt to the two carriage plates | `layout.json` mounts |
| Mount: entry sensor on intake carriage plate left | (434, 255, 569). Sensor bracket on the top edge of the left carriage plate | `layout.json` mounts |
| Mount: climber inner tube left on climber tube left | (300, 316, 500). Inner tube runs in bushings in the fixed outer tube | `layout.json` mounts |
| Mount: climber inner tube right on climber tube right | (300, -316, 500). Inner tube runs in bushings in the fixed outer tube | `layout.json` mounts |
| Mount: climber hook left on climber inner tube left | (300, 316, 736). Swing joint on the inner tube top | `layout.json` mounts |
| Mount: climber hook right on climber inner tube right | (300, -316, 736). Swing joint on the inner tube top | `layout.json` mounts |
| Mount: battery on battery retention cleat aft | (-95, 291, 150). Battery end face captured between the aft and fore cleats, with the strap over its top | `layout.json` mounts |
| Mount: battery retention on floor pan | (-95, 291, 100). Cleat feet riveted to the floor pan top, which rests on the frame rails | `layout.json` mounts |
| Mount: battery strap on battery retention cleat aft | (-95, 291, 199). Strap anchored to the aft cleat and buckled to the fore cleat over the battery top | `layout.json` mounts |
| Mount: hopper shelf on hopper liner left | (0, 169, 267). Shelf panel rests on the channel wall of the left liner and on the side wall, held by two quarter-turn fasteners | `layout.json` mounts |
| Mount: hopper wall left on frame rail left | (0, 334, 120.65). Side wall foot on the left rail top | `layout.json` mounts |
| Mount: hopper wall right on frame rail right | (0, -334, 120.65). Side wall foot on the right rail top | `layout.json` mounts |
| Mount: hopper liner left on floor pan | (0, 169, 100). Channel wall foot on the floor pan | `layout.json` mounts |
| Mount: hopper liner right on floor pan | (0, -169, 100). Channel wall foot on the floor pan | `layout.json` mounts |
| Mount: hopper rear wall on hopper wall left | (-94.5, 334, 500). Rear wall flange on the left side wall; its right edge is carried by the right liner's pocket wall | `layout.json` mounts |
| Mount: climber tube left on climber tube mount left | (300, 316, 222). Outer tube socket in the tube mount | `layout.json` mounts |
| Mount: climber tube right on climber tube mount right | (300, -316, 222). Outer tube socket in the tube mount | `layout.json` mounts |
| Mount: climber winch on intake slide rail left | (200, 266, 345). Winch plate bolts to the underside of the fixed slide rail, in the bay outboard of the carriage plate; the right cable crosses inside the front rail | `layout.json` mounts |

## Axes and travel

From `paths.json`. Mirrored members move the same way on the other side.

| Case | First moving member | Travel |
| --- | --- | --- |
| intake-deploy | entry sensor | translates [250.0, 0.0, -95.0] |
| climb-reach | climber hook left | rotates 180 degrees about axis [0.0, 0.0, 1.0] through [300.0, 316.0, 744.0] |
| climb-seat | climber hook left | translates [0.0, 0.0, -29.61799989999861] |
| climb-lift | climber hook left | translates [0.0, 0.0, -70.0] |

## Envelopes

| Measure | Value | File |
| --- | --- | --- |
| Frame | 680 long by 714 wide, 2788 perimeter | `design.json` |
| Bumper zone | 48 to 168 above the carpet, 76 section | `design.json` |
| Starting overhang beyond the frame | 0.0 | `measurements.json` |
| Greatest height in any operating or park pose | 756.257 | `measurements.json` |
| Greatest front extension | 244.614 | `measurements.json` |
| Greatest rear or side extension | 0.0 | `measurements.json` |
| Sides extended at once | 1.0 | `measurements.json` |
| Least clearance over the BUMP crest, static screen | 8.68 | `measurements.json` |

## Interfaces and allowances: fits under 10 mm

Least gap of each pair the layout check measured under 10 mm, from `receipt.json`. Each is an interface for detailed design to dimension, not a verified clearance. Pairs of official field parts are left out.

| Pair | Least gap | Case |
| --- | --- | --- |
| electronics panel / hopper liner right | 1.0 | intake-deploy |
| feeder motor right / hopper liner right | 1.0 | intake-deploy |
| hopper liner left / stage sensor left | 1.0 | intake-deploy |
| hopper liner right / stage sensor right | 1.0 | intake-deploy |
| feeder motor left / hopper shelf left | 1.1 | intake-deploy |
| hopper liner left / hopper shelf left | 1.5 | intake-deploy |
| climber hook left / tower rung 1 | 1.5 | climb-lift |
| climber hook right / tower rung 1 | 1.5 | climb-lift |
| frame rail front / hopper liner left | 1.6 | intake-deploy |
| frame rail front / hopper liner right | 1.6 | intake-deploy |
| climber inner tube left / climber tube left | 2.0 | intake-deploy |
| climber inner tube right / climber tube right | 2.0 | intake-deploy |
| climber hook left / climber inner tube left | 2.0 | intake-deploy |
| climber hook right / climber inner tube right | 2.0 | intake-deploy |
| electronics panel left / hopper liner left | 2.0 | intake-deploy |
| entry sensor / hopper liner left | 2.0 | tower-lateral |
| front left module motors / hopper liner left | 2.0 | intake-deploy |
| front right module motors / hopper liner right | 2.0 | intake-deploy |
| hopper liner left / intake back plate | 2.0 | tower-lateral |
| hopper liner left / intake belt module | 2.0 | tower-lateral |
| hopper liner left / intake carriage plate left | 2.0 | tower-lateral |
| hopper liner left / intake top roller | 2.0 | tower-lateral |
| hopper liner right / intake back plate | 2.0 | tower-lateral |
| hopper liner right / intake belt module | 2.0 | tower-lateral |
| hopper liner right / intake carriage plate right | 2.0 | tower-lateral |
| hopper liner right / intake top roller | 2.0 | tower-lateral |
| FUEL stored 1 / feeder roller right | 4.7 | intake-deploy |
| FUEL tracked / floor belt main | 5.2 | loaded-transit |
| FUEL tracked / hub funnel side 2 | 7.4 | climb-reach |
| FUEL tracked / hub funnel base | 8.8 | climb-reach |

## Interfaces and allowances: intended contacts

From `contacts.json`. A listed pair is left out of that case's clearance test.

| Pair | Cases | Basis |
| --- | --- | --- |
| FUEL tracked / bumper front | acquire-1, acquire-2 | acquire-nominal 0.0000-0.3350 s: the trial presses the FUEL 11.2 mm into this surface (15 kN/m penalty contact, an estimate, not a measured force-deflection curve). The coarse stroke is within 39.6 mm of that path, so the pair is listed as an intended contact with the trial's indentation as its allowance and is not a clearance result |
| FUEL tracked / feeder roller left | hopper-3, loaded-transit, launch-1 | entry-nominal 0.4130-1.4370 s: the trial presses the FUEL 6.9 mm into this surface (15 kN/m penalty contact, an estimate, not a measured force-deflection curve). The coarse stroke is within 28.3 mm of that path, so the pair is listed as an intended contact with the trial's indentation as its allowance and is not a clearance result |
| FUEL tracked / floor belt main | hopper-2, hopper-3 | entry-nominal 0.2330-0.4130 s: the trial presses the FUEL 5.6 mm into this surface (15 kN/m penalty contact, an estimate, not a measured force-deflection curve). The coarse stroke is within 39.6 mm of that path, so the pair is listed as an intended contact with the trial's indentation as its allowance and is not a clearance result |
| FUEL tracked / flywheel | launch-1, flight-1 | launch-nominal 0.1000-0.2174 s: the trial presses the FUEL 7.7 mm into this surface (15 kN/m penalty contact, an estimate, not a measured force-deflection curve). The coarse stroke is within 27.0 mm of that path, so the pair is listed as an intended contact with the trial's indentation as its allowance and is not a clearance result |
| FUEL tracked / hood | launch-1, flight-1 | launch-nominal 0.1000-0.2174 s: the trial presses the FUEL 10.2 mm into this surface (15 kN/m penalty contact, an estimate, not a measured force-deflection curve). The coarse stroke is within 27.0 mm of that path, so the pair is listed as an intended contact with the trial's indentation as its allowance and is not a clearance result |
| FUEL tracked / hopper rear wall | hopper-1 | entry-nominal 0.0000-0.2330 s: the trial presses the FUEL 4.7 mm into this surface (15 kN/m penalty contact, an estimate, not a measured force-deflection curve). The coarse stroke is within 39.4 mm of that path, so the pair is listed as an intended contact with the trial's indentation as its allowance and is not a clearance result |
| FUEL tracked / hub funnel base | flight-1, flight-2 | deliver-nominal 0.0000-0.8890 s: the FUEL enters the HUB opening and comes to rest in the funnel. The delivery trial solved the flight against a dimensioned opening, not these official parts, so where it lands on them is not a trial result (risk shot-calibration) |
| FUEL tracked / hub funnel side 1 | flight-1, flight-2 | deliver-nominal 0.0000-0.8890 s: the FUEL enters the HUB opening and comes to rest in the funnel. The delivery trial solved the flight against a dimensioned opening, not these official parts, so where it lands on them is not a trial result (risk shot-calibration) |
| FUEL tracked / hub funnel side 2 | flight-1, flight-2 | deliver-nominal 0.0000-0.8890 s: the FUEL enters the HUB opening and comes to rest in the funnel. The delivery trial solved the flight against a dimensioned opening, not these official parts, so where it lands on them is not a trial result (risk shot-calibration) |
| FUEL tracked / hub funnel side 3 | flight-1, flight-2 | deliver-nominal 0.0000-0.8890 s: the FUEL enters the HUB opening and comes to rest in the funnel. The delivery trial solved the flight against a dimensioned opening, not these official parts, so where it lands on them is not a trial result (risk shot-calibration) |
| FUEL tracked / hub funnel side 4 | flight-1, flight-2 | deliver-nominal 0.0000-0.8890 s: the FUEL enters the HUB opening and comes to rest in the funnel. The delivery trial solved the flight against a dimensioned opening, not these official parts, so where it lands on them is not a trial result (risk shot-calibration) |
| FUEL tracked / hub funnel side 5 | flight-1, flight-2 | deliver-nominal 0.0000-0.8890 s: the FUEL enters the HUB opening and comes to rest in the funnel. The delivery trial solved the flight against a dimensioned opening, not these official parts, so where it lands on them is not a trial result (risk shot-calibration) |
| FUEL tracked / hub funnel side 6 | flight-1, flight-2 | deliver-nominal 0.0000-0.8890 s: the FUEL enters the HUB opening and comes to rest in the funnel. The delivery trial solved the flight against a dimensioned opening, not these official parts, so where it lands on them is not a trial result (risk shot-calibration) |
| FUEL tracked / hub net | flight-1, flight-2 | deliver-nominal 0.0000-0.8890 s: the FUEL enters the HUB opening and comes to rest in the funnel. The delivery trial solved the flight against a dimensioned opening, not these official parts, so where it lands on them is not a trial result (risk shot-calibration) |
| FUEL tracked / intake back plate | acquire-1, acquire-2 | acquire-nominal 0.0000-0.3350 s: the trial presses the FUEL 0.0 mm into this surface (15 kN/m penalty contact, an estimate, not a measured force-deflection curve). The coarse stroke is within 39.6 mm of that path, so the pair is listed as an intended contact with the trial's indentation as its allowance and is not a clearance result |
| FUEL tracked / intake belt module | acquire-1, acquire-2 | acquire-nominal 0.0000-0.3350 s: the trial presses the FUEL 9.8 mm into this surface (15 kN/m penalty contact, an estimate, not a measured force-deflection curve). The coarse stroke is within 39.6 mm of that path, so the pair is listed as an intended contact with the trial's indentation as its allowance and is not a clearance result |
| FUEL tracked / intake top roller | acquire-2 | acquire-nominal 0.3350-0.6380 s: the trial presses the FUEL 1.7 mm into this surface (15 kN/m penalty contact, an estimate, not a measured force-deflection curve). The coarse stroke is within 39.8 mm of that path, so the pair is listed as an intended contact with the trial's indentation as its allowance and is not a clearance result |
| FUEL tracked / lane deck | hopper-3, loaded-transit, launch-1 | entry-nominal 0.4130-1.4370 s: the trial presses the FUEL 7.1 mm into this surface (15 kN/m penalty contact, an estimate, not a measured force-deflection curve). The coarse stroke is within 28.3 mm of that path, so the pair is listed as an intended contact with the trial's indentation as its allowance and is not a clearance result |

## Operating point and windows

Each trial ran on blockout geometry with estimated contact stiffness and friction. A bracket lists one passing value and the nearest failing one.

| Trial | Input | Passes at | Fails at | Record |
| --- | --- | --- | --- | --- |
| acquire-nominal | belt and bumper squeeze | 15 mm | 10 mm | `acquire-3.json` |
| acquire-nominal | intake belt speed | 2.5 m/s | 2 m/s | `acquire-3.json` |
| acquire-nominal | bumper cover friction | 0.3 coefficient | 0.2 coefficient | `acquire-3.json` |
| acquire-nominal | control: Intake belt locked |  | rejected | `acquire-3.json` |
| acquire-nominal | timestep | 0.0001 s | same outcome at 5e-05 s: True | `acquire-3.json` |
| entry-nominal | stage beam and controller lag | 20 ms | 80 ms | `hopper-3.json` |
| entry-nominal | feeder squeeze | 8 mm | 4 mm | `hopper-3.json` |
| entry-nominal | control: No feeder roller: nothing holds the FUEL off the spinning flywheel |  | rejected | `hopper-3.json` |
| entry-nominal | timestep | 5e-05 s | same outcome at 2.5e-05 s: True | `hopper-3.json` |
| hold-nominal | push from queued FUEL | 90 N | 120 N | `trial-hold.json` |
| hold-nominal | control: No feeder roller |  | rejected | `trial-hold.json` |
| hold-nominal | timestep | 0.0001 s | same outcome at 5e-05 s: True | `trial-hold.json` |
| launch-nominal | flywheel setpoint | 13.3 m/s | 13.1 m/s | `launch-1.json` |
| launch-nominal | wheel-to-hood squeeze | 8 mm | 6 mm | `launch-1.json` |
| launch-nominal | wheel friction | 0.5 coefficient | 0.3 coefficient | `launch-1.json` |
| launch-nominal | contact stiffness | 10000 N/m | 7500 N/m | `launch-1.json` |
| launch-nominal | control: Feeder roller stopped: no feed |  | rejected | `launch-1.json` |
| launch-nominal | timestep | 0.0001 s | same outcome at 5e-05 s: True | `launch-1.json` |
| hopper-cycle-nominal | floor belt speed | 1.2 m/s | 0.6 m/s | `trial-hopper-cycle.json` |
| hopper-cycle-nominal | FUEL collected | 24 FUEL | 27 FUEL | `trial-hopper-cycle.json` |
| hopper-cycle-nominal | control: The earlier issue's intake: FUEL thrown in low through an open throat |  | rejected | `trial-hopper-cycle.json` |
| hopper-cycle-nominal | timestep | 0.0002 s | same outcome at 0.0001 s: True | `trial-hopper-cycle.json` |
| batch-nominal | flywheel stator current limit at the weak-pack bus | 20 A | 5 A | `trial-batch.json` |
| batch-nominal | stator current limit with the bare 0.0026 kg m2 roller at the weak-pack bus | 40 A | 20 A | `trial-batch.json` |
| batch-nominal | control: Flywheel motors off through the batch |  | rejected | `trial-batch.json` |
| batch-nominal | timestep | 0.0001 s | same outcome at 5e-05 s: True | `trial-batch.json` |
| deliver-nominal | release speed | 7.1 m/s | 7.25 m/s | `flight-2.json` |
| deliver-nominal | control: Release 6.40 m/s, below the scoring band |  | rejected | `flight-2.json` |
| deliver-nominal | timestep | 0.0001 s | same outcome at 5e-05 s: True | `flight-2.json` |
| hang-nominal | winch current limit | 20 A | 15 A | `trial-hang.json` |
| hang-nominal | control: No brake: the winch coasts with power removed |  | rejected | `trial-hang.json` |
| hang-nominal | timestep | 0.0001 s | same outcome at 5e-05 s: True | `trial-hang.json` |

## Motion cases

From `missions.json` and `layout.json`. The single prescribed strokes follow their path exactly; the tracked FUEL's strokes are within the stated distance of the solved trace.

| Phase | Cases | Path tolerance |
| --- | --- | --- |
| acquire | intake-deploy, acquire-1, acquire-2, acquire-3 | 40 mm |
| retain | hopper-1, hopper-2, hopper-3, loaded-transit | 40 mm |
| transfer | launch-1 | 40 mm |
| deliver | flight-1, flight-2 | 40 mm |
| reset | not applicable: No reset motion: the intake stays deployed and each lane's feeder stages the next FUEL as the last one leaves, which the hopper cycle trial covers |  |
| endgame | climb-reach, intake-stow, tower-lateral, tower-forward, climb-seat, climb-lift | 40 mm |
| park | park-lower | 40 mm |
| service | battery-cover-remove, battery-withdraw, shooter-withdraw | 40 mm |
| displaced control | intake-deploy: Raise the front left module's motors 40 mm, as a taller motor would, so the deploying carriage plate strikes them | rejected |

## Budgets

| Budget | Value | File |
| --- | --- | --- |
| Inspection weight estimate | 40.09 to 49.96 kg against 52.16 kg | `receipt.json` budgets |
| Reserve under the limit | 2.20 kg | `receipt.json` budgets |
| Running weight with bumpers, battery and 24 FUEL | 55.96 to 69.81 kg | `receipt.json` budgets |
| Least loaded-voltage margin | 0.16 V in loaded-transit-weak (7.66 V against 7.5 V) | `receipt.json` budgets |
| Mass and current by subsystem | one line per subsystem with its basis | `budgets.json` |

## Open risks and bench tests

From `missions.json`.

| Risk | Closed by, or bench test | Pass | Fail |
| --- | --- | --- | --- |
| flywheel-droop: The flywheel slows under each shot and through a batch, and the release leaves the scoring band | Closed: Flywheel a free 0.0076 kg m2 body (roller plus one inertia ring, 2.56 kg) under two motors and a speed loop, fed only inside a 1% ready band: one shot takes 17 J and drops the wheel 1.9%; 24 FUEL at 4 FUEL/s release at 6.88-6.92 m/s on a 12 V bus and 6.83-6.88 m/s on the 8.34 V weak-pack bus, inside the 6.725-7.100 m/s band (batch trials) |  |  |
| shot-calibration: The model's wheel-to-FUEL speed transfer, drag and spin lift are estimates, so the setpoint that centres the release in the band is not known. The delivery trial also scored against a dimensioned opening, not the official HUB: the official opening is larger along the shot line, its funnel walls slope inward below the rim and a net stands behind it, and the trial's nominal shot arrives 384 mm beyond the HUB centre, where the net's lower edge is | FUEL scored of 20 launched from the 2.7 m pose, with every measured release speed of a 24 FUEL batch inside the band found on the bench | 19 FUEL | 18 FUEL |
| hold-back: A staged FUEL is pushed into the spinning flywheel with no feed commanded | Closed: One braked feeder roller per lane over a fixed lane deck, 14 mm squeeze, floor belt ending ahead of the staged FUEL and stopped while both lanes are staged: the hold trial keeps the FUEL 25.6 mm clear under a 90 N push at 1.5 g and fails at 120 N. In the 16 collect-hold-feed patterns the push on a staged FUEL peaks at 138 N (20 ms mean), above the steady push the hold trial passes, as FUEL land on the heap, and no pattern feeds uncommanded; the bench tests hold-back-force and uncommanded-feed-bench measure the margin |  |  |
| hold-back-force: The hold rests on foam friction and stiffness that are estimates (0.9 and 0.6, 15 kN/m) | Steady push on a staged FUEL that the braked feeder holds without the FUEL reaching the wheel | 90 N | 60 N |
| intake-power: The intake belt cannot hold its speed under the acquisition load at its current limit | Closed: Belt driven in the trial by one motor at 2:1 with a 30 A supply limit: three FUEL abreast on a 9 V bus dip it to 2.13 m/s and are captured; the trial captures down to 2.5 m/s and fails at 2 m/s |  |  |
| acquisition-pinch: Capture depends on the belt squeeze and on cover and back plate friction, which are estimates | Floor FUEL thrown over the back plate within 1.2 s, of 20, at 17.5, 20 and 25 mm squeeze with the belt at or above 2.5 m/s | 20 FUEL | 19 FUEL |
| batch-collection: A batch of 24 cannot be collected: thrown in low through an open throat, the hopper stalls with FUEL backing out into the intake | Closed: The intake is a chute that lifts each FUEL up its own back plate to 425 mm and throws it in over the top; the back plate closes the hopper front. Collect trial: 24 in the hopper and 0 in the chute of 24; collecting 27 leaves more than four in the chute (bracket). The earlier issue's low entry fails the same trial (control) |  |  |
| batch-feed: The collected heap bridges or strands FUEL and the feed falls below 2.00 FUEL/s | Closed: Two-lane channel with the belt running to the front rail, sloped shelves, feeder rollers standing in the hopper and meeting at the centre line, one stage beam per lane, a belt reversal and a 40 mm carriage nudge in the unjam cycle: 16 of 16 collect-hold-feed patterns feed all 24 in 7.1-10.5 s (2.3-3.4 FUEL/s) |  |  |
| feed-rate-bench: Heap behaviour varies from run to run and rests on FUEL-to-FUEL and wall friction estimates; the slowest pattern feeds 24 in 10.5 s against 12 s | FUEL fed to the flywheel within 12 s of the first feed command, 24 collected through the chute, in each of 5 runs | 22 FUEL | 21 FUEL |
| loaded-driving: A hard stop can throw FUEL forward over the chute, which is open above the top roller. Harder stops are tested on single patterns only: at 0.75 g 1 of 1 tested patterns keep and feed all 24; at 1 g 2 of 2 tested patterns keep and feed all 24 | FUEL leaving the robot across ten stops from 3 m/s and five turns at the loaded acceleration limit of 0.5 g with 24 aboard | 0 FUEL | 1 FUEL |
| uncommanded-feed-bench: A FUEL reaches the flywheel while collecting or driving | Uncommanded feeds in 20 collect-and-drive cycles of 24 FUEL | 0 feeds | 1 feeds |
| mass-reserve: The inspection weight estimate tops out 2.20 kg under the 52.16 kg limit | Weighed inspection weight of the robot without bumpers and battery | 52.16 kg | 52.17 kg |
| hang-squaring: The robot hangs yawed or offset and a bumper misses an upright. The hang trial used a dimensioned TOWER BASE 8 mm tall; the official base plate and its brackets are checked for clearance in the climb cases but are not in the trial | Least clearance to the carpet and TOWER BASE through the 3 s hold, at 70.3 kg, seated at 0 and at 20 mm lateral offset each way | 5 mm | 0 mm |
| hang-with-fuel: The intake cannot stow with FUEL in the front of the hopper, and deployed it stands under the rung | Closed: The hang sequence swings the hooks forward first, then stows the empty intake between them, then closes on the TOWER (cases climb-reach, intake-stow, tower-forward, checked). The stow is commanded only with the chute and both stage beams clear; with FUEL aboard the robot keeps shooting and does not hang, which is the strategy's own rule |  |  |
| bump-clearance: The front bumper corner clears the BUMP crest by 8.7 mm in the static screen, which uses a sharp 15 degree profile. The official BUMP crest is rounded and stands 3.7 mm fuller 20 mm either side of the line (cad/field/official/README.md), which is not in the screen | Least clearance of any part other than wheels and bumpers over the BUMP in ten crossings each way, intake retracted | 5 mm | 0 mm |
| battery-strap: The battery has no hold-down | Closed: A strap over the battery top between the two cleats is drawn and mounted, and the shelf panel above it covers it; the service cases remove the panel and strap, then lift the battery (checked) |  |  |
| carriage-cross-ties: The intake's belt module, top roller and back plate stand inside the hopper cheeks and its carriage plates outside them. The ties between them and the moving slide stage are not drawn, so the layout does not show that they clear the cheeks and the bay walls through the slide travel | Least clearance from the carriage cross-ties and the moving slide stage to the hopper cheeks and bay walls over the full slide travel, on the first assembled carriage | 3 mm | 1 mm |
| unregistered-joints: Members carried no registered joint to the frame | Closed: Each separately mounted member has its own mount entry: both feeder rollers and motors, both carriage plates, both inner tubes, both hooks, both climber tubes, the winch, the side walls, liners, rear wall, shelf panel and strap |  |  |
| weak-battery-margin: The loaded-transit duty leaves the smallest voltage margin on a weak battery | Minimum bus voltage through a loaded transit with the flywheel spinning up, on a battery at 0.026 ohm | 7.5 V | 7 V |
| carriage-nudge: The unjam cycle's carriage nudge has to push the back plate into the FUEL at the hopper front. In the recorded trials the pattern run without the nudge also feeds all 24, so the trials do not show the nudge is needed | Arches at the hopper front cleared by one 40 mm nudge, of 10 set by hand with 24 FUEL aboard | 10 arches | 9 arches |
| bump-crossing-dynamic: Driving over the BUMP at speed with stored FUEL is not evaluated | FUEL leaving the robot in ten BUMP crossings each way at 1.5 m/s with 24 aboard and the intake retracted | 0 FUEL | 1 FUEL |
| loaded-robot-contact: Robot-to-robot contact while carrying FUEL is not evaluated | FUEL leaving the robot in five 1 m/s bumper-to-bumper contacts on each side with 24 aboard | 1 FUEL | 2 FUEL |

## Trials and replays

Every trial ran on blockout geometry and estimated contact properties. The delivery and hang trials ran against dimensioned field surfaces, not the official parts the layout check uses.

| Motion | What it plays | Repeat on real parts |
| --- | --- | --- |
| One FUEL from the carpet into the HUB (recorded trials) | Recorded trials acquire-nominal, entry-nominal, launch-nominal and deliver-nominal of field-trials.json, played one after another | Yes |
| Collect, hold and feed 24 FUEL (recorded trial) | Recorded trial hopper-cycle-nominal of field-trials.json: every FUEL's translation and spin in three dimensions with penalty contact and Coulomb friction against the hopper, the rollers and each other | Yes |
| Hold the staged FUEL off the flywheel (recorded trial) | Recorded trial hold-nominal of field-trials.json: FUEL translation and spin with penalty contact, Coulomb friction, gravity and rolling resistance | Yes |
| Launch 24 FUEL through the one flywheel (recorded trial) | Recorded trial batch-nominal of field-trials.json: every FUEL's translation and spin, and the flywheel speed through the whole batch | Yes |
| Lift on the low rung and hold with power removed (recorded trial) | Recorded trial hang-nominal of field-trials.json: robot translation and pitch with unilateral wheel, bumper, upright and hook contacts | Yes |

## First work items

1. Draw the carriage cross-ties and the moving slide stage, and check them against the hopper cheeks through the slide travel (risk carriage-cross-ties).
2. Measure a FUEL force-deflection curve and the foam friction on the feeder roller and lane deck; repeat the hold-back and acquisition trials with them (risks hold-back-force, acquisition-pinch).
3. Repeat the delivery and hang trials against the official HUB and TOWER parts, then find the flywheel setpoint on the bench (risks shot-calibration, hang-squaring).
4. Set the withdrawal clearances of the battery, shelf panel and shooter module. The service cases here show no interference and hold no reserve.
5. Weigh the mass estimate against real parts as they are chosen: the reserve is small (risk mass-reserve).
