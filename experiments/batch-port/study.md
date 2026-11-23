# Can the packed robot serve 24 FUEL in 12 seconds?

The indexed feeder released all 24 named FUEL in 11.953 seconds. Only three of those same IDs completed an independently witnessed score before the deadline in both time-step trials. A closed R2C hopper supported single floor pickup but delivered zero from its 24-piece stock. Keep R2C as the editable student robot while the next feeder and its loading path are compared. [Interactive replay](https://ehartye.github.io/frc-2026-poc/detailed-design/) (page withdrawn with the rough-draft showcase) · [Ledger](results.json) · [R2C native Fusion and exact-download reopen](../../cad/own-zone-upper/design.md).

## From stock to receiver

The current Fusion guide is 130 mm wide and leaves two 22 mm openings. Each FUEL is 150.114 mm in diameter. Each trial below starts with 24 stationary 215 g spheres. The finite shelf circuit includes both turns, the return and the initial shelf phase. Each original R2C shell, floor and belt coordinate comes from the issued STEP appearance inventory. The alternatives are project-owned proposed contact geometry. They still need an editable assembly, moving-part clearance, drives, controls and a loading route.

| Twelve-second trial | Whole port clear | Arrived at ideal receiver | Lost |
|---|---:|---:|---:|
| Original closed port | 0 | 0 | 0 |
| Open split port, floor belts stopped | 0 | 0 | 0 |
| Open split port, belts moving | 3 | 1 | 2 |
| Powered bridge across the opening | 4 | 3 | 0 |
| Bridge with diagonal stock feed | 5 | 4 | 0 |
| Diagonal feed and rear follower | 8 | 5 | 2 |

Port clearance requires the ball's trailing surface to pass the transfer plane. The comparative receiver removes a ball only after reaching both the port and head thresholds. Opening a gate alone can let stock fall below the elevator. The finite four-carrier 1.406 m loop advances only 0.90 carriers/s at its modeled belt speed in these tests. The counts above supersede an early repeating-pitch screen that omitted the return. For pickup, the closed split faces cover the original guide, with the tongue stowed outside the corridor. The centered planar ground trial reached the 540 mm handoff at 1.3425 s. Disabling the roller or removing the guides prevented handoff. This verifies the closed-state contact outline under the declared assumptions. It leaves actuator packaging and the different indexed magazine's floor intake open. [Closed-state geometry and replay](pickup.json).

The distinct indexed candidate uses four lanes of six identifiable pieces, top and bottom tier supports, force-limited stock followers, a moving receiver and seven carriers on one shorter closed loop. Its coupled test retains each piece through storage, the moving port, the lift, the R2C-type paired scoring wheels and their shared recovery. The modeled recovery limit is 0.09 N·m per motor when clear of pieces. Zero recovery reduces the exits from 24 to 22. Repeated releases span approximately 0.518–11.953 s. The source for each clock, handoff and stored piece is available in the experiment runner. [Feeder](magazine.mjs) · [Finite carrier circuit](lift.mjs) · [Receiver](receiver.mjs).

## What reached the active HUB?

One shared field trial advances all released pieces, their mutual contacts, the released native field surfaces and four optical channels on the same clock. An isolated counter event requires the full sphere to traverse the finite top opening, a definite beam interruption attributable to one FUEL, a shared reset and downstream clearance. Both powered field surfaces assume 1 m/s as in the independent single-piece study. Registered housings bound possible optical rays. Actual field speed and sensor processing remain unknown. Shift 1 allows 25 s. The strategic allowance starts service at shift second 13 and leaves 12 s. The extra three seconds for processing require that opening entry preceded deactivation. [Rules and selected clock](../../kickoff/selected-strategy.md) · [Single-piece counter and stationary-field control](../own-zone-cycle/counter-study.md).

| Mechanism / field step | Releases | Clean whole openings | Independent passages | Within 12 s | During processing | Contacting piece pairs |
|---|---:|---:|---:|---:|---:|---:|
| 0.25 / 0.50 ms | 24 | 11 | 7 | 4 | 3 | 18 |
| 0.125 / 0.25 ms | 24 | 12 | 7 | 5 | 2 | 14 |

M0-06, M1-12 and M2-16 cleared within the 12 s in both. Two more, M2-13 and M3-24, completed under both models when processing was included. The ledger reports the latest strict release clock individually for each observed route, accounting for its own processing delay. Moving the same attained service two seconds earlier would bring seven passages inside the active clock in each trial. A five-second advance yields the same seven. Those schedules require a faster settle or stock already at the destination. Their R2C stationary body envelopes clear the modeled traffic over the service window. Loaded travel to that pose remains unverified. [Traffic screen](traffic.json).

The native rim has six inclined sheets of about 3 mm thickness. The clearance check uses the actual sphere cross-section intersecting that slab. At the coarse step, M0-04 contacted another piece, hit the native rim and later interrupted channel 2. Its minimum finite-slab margin was −24.36 mm, so this witness leaves its complete passage unresolved. At the fine step the same ID completed a clean opening at 1.845 s, then cleared channel 3 at 12.051 s. A sensor interruption alone cannot resolve the earlier geometry. [Rim geometry](rim.py) · [Shared passage and optical witness](shared_field.py).

## Why did the middle pieces fail?

| Service order within each lane | First | Second | Third | Fourth | Fifth | Sixth |
|---|---:|---:|---:|---:|---:|---:|
| Clean openings from four lanes, coarse | 4 | 3 | 0 | 0 | 0 | 4 |
| Clean openings from four lanes, fine | 4 | 4 | 0 | 0 | 0 | 4 |
| Fine diagnostic with inter-piece contacts disabled | 4 | 0 | 4 | 0 | 4 | 4 |

The fourth piece in each lane peaked below rim height even in free flight. The third and fifth each recovered four openings in the control. The second piece lost all four. This isolates sensitivity to inter-piece contact separately from the fourth piece's low release. The control lets balls pass through one another and serves only to diagnose the coupled result. The student design question is how to receive and space stock consistently through the full cycle. Testing that change requires the same coupled clocks, a loadable magazine and four lanes' worth of individual evidence.

The legal preload is at most eight. All 24 were deliberately initialized in named storage positions for this component comparison. To claim a complete match target, the design must acquire the additional 16 from an actual supply, retain them through the modeled traffic and attain this service pose before the clock expires. The live field lab's scripted match tallies and this study use different evidence.

## Reproduce

Use the project-local FIRST field cache reconstructed from the pinned source in the [CAD handoff](../../cad/own-zone-upper/design.md). The runner accepts an existing external scratch directory containing the private field mesh and writes raw JSON there. It refreshes the compact student ledger in this folder. It requires Node, NumPy and VTK. Run from the project root.

```powershell
python experiments/batch-port/reproduce.py artifacts/own-zone-native
python experiments/batch-port/pickup.py
node experiments/batch-port/traffic.mjs $plugin experiments/batch-port/traffic.json
```

