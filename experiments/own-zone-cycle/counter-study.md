# One counter passage in an active HUB

[Play the two clips and jump to the scoring event](https://ehartye.github.io/frc-2026-poc/detailed-design/) (page withdrawn with the rough-draft showcase) · [Inspect the source-bound receipt](counter-result.json) · [Compare all nine robot contact cases](single-piece.json)

One modeled FUEL earned **one point 16.987 seconds into Shift 1**. The same physical passage earns zero with the other AUTO leader and an inactive blue HUB. The source is the kickoff V0 rule that requires passage through the opening and the sensor array. The Neutral return scenario gave red the AUTO lead, activating blue's first shift. The complete local event fits inside the active window, without using a processing allowance. [Project rule register](../../kickoff/rule-register.json)

## Why the robot moved 250 mm

B2 approaches with the native 680 mm frame and 76 mm bumpers. The study intersects its swept bumper with the five contemporaneous robot trajectories from the independently run Neutral return rehearsal. Each period uses 50 ms steps. The clearances include the curved-velocity interpolation bound and the complete final 399 mm pickup approach. Fixed-obstacle clearance uses a conservative circle around the bumpers. A negative peer gap accompanies a swept rectangle contact in these trials. [Approach comparison](approach-comparison.json)

| Position along the approach | Static clearance | Minimum peer separation bound | Peer-contact ticks | Robot contact cases clearing the aperture |
|---|---:|---:|---:|---:|
| 250 mm back | 944 mm | −130 mm | 16 | 2 of 9 |
| Original field program | 728 mm | −20 mm | 3 | 2 of 9 |
| 250 mm toward the HUB | 512 mm | 106 mm | 0 | 2 of 9 |

The closer pose clears the modeled partner traffic. It leaves the seven low-apex conditions short of the opening. The physically passing example uses the project’s 30,000 N/m foam/contact hypothesis and 70% initial free-speed case. The ball’s speed and spin at release are taken from the preceding pickup/lift integration. The robot has stopped when contact with the wheels ends. The trial then carries that same state through the actual registered field surfaces. The earlier assigned whole-match tactic and scores remain separate.

## A counter event students can inspect

The field's registered transverse tube and eight inclined wheel stacks receive prescribed surface speeds of 1 m/s in the outward direction. Contact transfers motion only where the sphere touches an actual surface. The speeds and contact friction are simulation assumptions. Four independently paired field sensors and reflectors define the possible optical passages. For each pair the witness tests every bounding-box corner ray where it crosses the sphere-center plane. A positive margin means the sphere interrupts every physically possible ray between the registered housings at once. The display's cyan line marks the channel centers.

| Field contact step | Channel | Guaranteed occlusion margin | Block after release | Whole sphere clear downstream |
|---|---:|---:|---:|---:|
| 0.500 ms | 3 | 5.31 mm | 2.428 s | 2.557 s |
| 0.250 ms | 3 | 5.32 mm | 2.406 s | 2.536 s |
| 0.125 ms | 3 | 5.36 mm | 2.451 s | 2.581 s |

The full sphere cleared the top opening 0.802 s after release, before the first registered field contact. At the finest step channel 3 stayed fully occluded for 30.875 ms, then cleared. It provided one unambiguous interruption for that piece. With both field drives stopped, the same piece settles upstream. At the original pose, powering only the wheel stacks also leaves the ball upstream. Powering only the transverse tube allowed a passage there. The active point is model-scoped. Actual firmware debounce, optical calibration, field speeds and FMS signals remain outside this simulation.

The selected strategy allocates 12 s for 24 deliveries. This receipt contains one piece, one modeled point and no estimate of steady-state throughput. The fixed 130 mm-wide rear lift guide blocks discharge from the current hopper at the bottom-layer ball height. Beside it, the two gaps against the hopper front wings are only 22 mm each. The 24-piece packing grid and the clear ground-pickup path therefore establish distinct capabilities. The next comparison needs an operable hopper transfer and identifiable consecutive pieces.

## Rebuild

Use the [R2C CAD handoff](../../cad/own-zone-upper/design.md) to reconstruct the private field mesh from the pinned FIRST source. From the checkout, with Agent FRC 0.33.0 installed at the path in `$plugin`, run the following commands. They reconstruct the approach, rerun the field dynamics with drive controls, and validate the public GLB event register.

```powershell
node experiments/own-zone-cycle/score_approaches.mjs $plugin experiments/own-zone-cycle/approach-comparison.json
python experiments/own-zone-cycle/run_counter.py artifacts/own-zone-native
python cad/own-zone-upper/animated.py
python experiments/own-zone-cycle/register_motion.py
node "$plugin/scripts/replay-chapters.mjs" experiments/own-zone-cycle/motion-chapters.json .
```
