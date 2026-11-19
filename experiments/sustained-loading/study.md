# Can the robot leave the DEPOT with 24 FUEL?

Starting pickup when the previous inactive shift begins gives the candidate enough time to retain **16 named DEPOT pieces and eight unspent preloads**. The last pair cleared its storage stops and all shutters finished closing at 29.74 and 29.58 seconds in two time-step refinements. That leaves 0.26–0.42 seconds before the planned departure. Starting pickup at the beginning of the active shift gives the robot only five seconds. It holds ten pieces then. [Rule register](../../kickoff/rule-register.json) · [Own-zone strategy](../../kickoff/selected-strategy.md) · [Compare the measured times and identities](results.json).

| Collection case | Onboard after 5 s | At 25 s | At 30 s | Final closed-gate observation |
|---|---:|---:|---:|---|
| Original 60 ms gate dwell, 0.500 ms step | 10 | 20 | 24 | 30.180 s, 0.180 s late |
| 15 ms gate dwell, 0.500 ms step | 10 | 20 | 22 | Last pair never completes; only DEPOT-22 reaches the pickup shelf |
| 15 ms gate dwell, 0.250 ms step | 10 | 20 | 24 | 29.738 s, smallest trailing clearance 13.35 mm |
| 15 ms gate dwell, 0.125 ms step | 10 | 20 | 24 | 29.580 s, smallest trailing clearance 12.44 mm |
| Lower traction and current with higher gross mass, 0.500 ms step | 10 | 20 | 20 | Chassis stalls at the rail before pair seven |

## Where the time goes

The comparison begins with the 24 released stock positions and all eight supported preloads. The robot takes two FUEL at a time. A rising tray moves them sideways to a pair of storage lanes. Belts move the balls behind separate shutters. The controller waits for both trailing surfaces to enter their lanes, waits another 15 or 60 ms, then commands the same 180 ms shutter stroke and allows another 20 ms to settle. As the tray returns empty, the chassis moves to the next pair. The experiment tracks all neighboring FUEL, open lanes and previously admitted pieces on the same clock. Gate commands read simulated piece positions. A physical sensor, latency budget and actuator capable of matching those strokes still need engineering. [Source geometry](../depot-loading/stock-register.json) · [Intake and carriage sequence](../depot-loading/sequence.mjs).

At the coarsest time step the shorter gate delay changes the path of the last pair. DEPOT-21 stays outside the tray and the controller keeps waiting for its partner. The two finer steps agree on which pieces arrive. Small supply-position or contact changes could still cost the team its departure slot.

The first six paired admissions bring the total to twenty. To reach the third rank the candidate drives straight over the modeled front tube, 76.2 mm wide and 28.575 mm high. After 304.8 mm of driven advance, a further commanded 60.2 mm on flat ground reaches the last pair. Mobile collection retains the 368 mm proposed front opening. The smallest tire-to-FUEL separation, measured against an enclosing sphere for every steer orientation, is 85.9 mm and 86.2 mm in the two timed trials. [Earlier pickup and bumper controls](../depot-loading/study.md) · [Four-wheel model](../depot-loading/wheel-crossing.mjs).

The nominal crossing assumes 58 kg gross supported mass including the twenty FUEL already aboard (4.30 kg), a 320 mm center-of-gravity height, tire friction coefficient 0.80, four 50 A drive limits, a 5.5:1 drive ratio and 82% mechanical efficiency. The model couples the chassis pitch and heave to cargo contact and holds gross mass and center of gravity fixed during the crossing. It reaches the step target and settles in 1.337 s. The combined 68 kg, 0.60 friction and 40 A case stops after 39.8 mm. Changing only gross mass, only friction or only current to those adverse values still clears the tube in the independent wheel calculation. Translation on clear carpet is commanded. The simulation uses a nominal source arrangement and modeled motor, tire and rail contact. The active swerve geometry and primary motor references are in the [drivetrain selection](../../cad/own-zone/design.md).

## What can continue from this result?

The [0.125 ms checkpoint](timed-125us-checkpoint.json) and [0.250 ms checkpoint](timed-250us-checkpoint.json) preserve all 24 onboard identities, the eight remaining field pieces, their positions, linear velocities and spin, the chassis pose, tray position and closed gates. Coordinates use the horizontal robot frame, +X ahead, +Y left, +Z up. Both checks end stopped, heading 180 degrees, before loaded travel. Future scoring evidence must carry these states through five seconds of driving, three seconds of settling and twelve seconds of service. The earlier [packed service test](../batch-port/study.md) started with separately seeded stock. The [R2C Fusion robot](../../cad/own-zone-upper/design.md) remains the issued student assembly. Its current guides differ from this proposed moving cartridge.

All eight preloads are still onboard in this branch. A team that spends those eight during AUTO must acquire **24 new pieces** to reproduce the same full active-shift load. This run earns zero AUTO points.

## Reproduce from the repository root

Use the same filenames in an empty output directory. Each command runs one solver. No restricted supplier file or GUI is needed to replay the registered geometry.

```sh
mkdir loading-runs
node experiments/depot-loading/stock.mjs experiments/depot-loading/stock-register.json loading-runs/loading-coupled-wheel.json blue-depot-01 paired-wheel 0.0005
node experiments/depot-loading/stock.mjs experiments/depot-loading/stock-register.json loading-runs/loading-coupled-wheel-stall.json blue-depot-01 paired-wheel-low 0.0005
node experiments/depot-loading/stock.mjs experiments/depot-loading/stock-register.json loading-runs/loading-final500.json blue-depot-01 paired-wheel-timed 0.0005
node experiments/depot-loading/stock.mjs experiments/depot-loading/stock-register.json loading-runs/loading-final250.json blue-depot-01 paired-wheel-timed 0.00025
node experiments/depot-loading/stock.mjs experiments/depot-loading/stock-register.json loading-runs/loading-final125.json blue-depot-01 paired-wheel-timed 0.000125
python experiments/sustained-loading/summarize.py loading-runs loading-runs/report
node scripts/check-batch.mjs
```

The last arrival and closure times, IDs and counts let students compare a rerun with the committed report. The older control runs have fewer diagnostic fields. The two selected boundaries include both full checkpoint files and SHA-256 digests. [Timed and adverse results](results.json).
