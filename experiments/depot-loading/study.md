# How much real stock can the robot collect?

Two neighboring FUEL from the blue DEPOT pass over its steel front tube and enter two different storage lanes. The same two IDs and the eight unspent preloads remain onboard at 8 s in both simulations. This is a 10-piece parked loading state. The [student viewer](https://ehartye.github.io/frc-2026-poc/detailed-design/archive/draft-001/robot/batch.html#loading) compares it with the separate component study that starts with 24 onboard. [Source register](stock-register.json) · [Per-piece ledger](results.json).

## Where the pieces start

The release-day FIRST field STEP locates all 24 blue DEPOT spheres in four ranks of six, at 152.4 mm pitch. The rules explicitly allow a different real arrangement. The nominal FUEL diameter here is 150.114 mm. The three steel tubes are 76.2 mm wide. Their tops sit 28.575 mm above the carpet. The robot faces the alliance wall, with its center 345 mm outside the near face of the front tube. All 24 field pieces are present throughout the three-dimensional comparison. Eight preloads start supported in separate upper and lower magazine pockets. No piece leaves the model when it touches a roller or crosses a gate. [Kickoff V0 §§5, 6.3 and R401/R105–106](../../kickoff/rule-register.json) · [Native field source and pin](../own-zone-cycle/field_register.py).

A first pose 35 mm closer interfered with neighboring stock by 28.7 mm at initialization. At the chosen setback, the tires clear the tube and the undeformed neighboring FUEL clear the bumper. The extended intake uses two raised ramp edges and a forward roller stroke. The proposed paired intake uses four ramp edges and a split center shelf. The two middle magazine lanes receive stock directly. A single-carriage comparison translates the supported piece 79 mm sideways before opening its gate.

| Eight-second case | Whole source pieces retained | Distinct unspent preloads retained | First source entry |
|---|---:|---:|---:|
| Single carriage, 0.250 / 0.125 ms | 1 / 1 | 8 / 8 | 2.2343 / 2.2349 s |
| Single carriage, transfer gate locked | 0 | 8 | — |
| Single carriage, storage belts stopped | 1 | 8 | 2.4390 s |
| Paired fixed lanes, 0.250 / 0.125 ms | 2 / 2 | 8 / 8 | 1.6985 / 1.6988 s |
| Paired lanes, transfer gates locked | 0 | 8 | — |

The continuous rigid-sphere model includes finite roller ends, the raised steel tubes, chassis bumper ends, contacting neighboring FUEL, gravity, carried-piece support, closing lane stops and contact friction. The stopped storage belt still accepts the single piece because it arrives moving. The original parked intake never touches its target. Stalling the extended roller allows contact but loses the transfer. A separate centered reach test accesses the first two ranks. The deeper two remain out of reach from this stationary front pose; the second-rank test assumes the preceding rank has been cleared. The new assembly is a prebuild contact proposal. Its drivetrain path, support structure, other mechanisms, moving clearances, load forces and actuators await assembled CAD and evidence.

The straight 680 mm frame and R401's 127 mm of protected perimeter at each corner allow one rectangular front gap up to 426 mm. The proposed 368 mm opening preserves 156 mm per side. Two nominal FUEL on the registered pitch span 302.514 mm. Three span 454.914 mm. A three-abreast straight intake cannot pass those three untouched centers through this face. The candidate comparison therefore uses two source lanes, preserving individual identities.

## The collection clock

An active shift follows an inactive shift when the official outcome makes that sequence applicable. The own-zone scorer can collect during the preceding 25 s and the first 5 s of the active shift. The separate transfer (5 s), settle (3 s) and service (12 s) still fit only if the robot departs the source at active-shift second 5. For the five-second-only comparison the robot waits until the active shift starts to collect. An observed AUTO point from one of its preloads consumes that ID. This parked experiment represents the eight-unspent case. The other rows are alternative inventory requirements.

| Preloads spent | Already aboard | Fresh pieces required | Five-second rate | Thirty-second rate |
|---:|---:|---:|---:|---:|
| 0 | 8 | 16 | 3.20/s | 0.53/s |
| 1 | 7 | 17 | 3.40/s | 0.57/s |
| 8 | 0 | 24 | 4.80/s | 0.80/s |

With all eight preloads retained, eight two-piece admissions must average 0.625 s each if collection starts in the active shift, or 3.75 s each with the preceding inactive shift available. This first paired admission takes 1.699 s. Repositioning the chassis for the remaining source ranks, resetting the intake, filling the farther storage pockets, then driving to the HUB with 24 pieces all consume time. This experiment qualifies a single admission. The [sustained loading comparison](../sustained-loading/study.md) extends the sequence through the chassis move and the remaining seven admissions. [Selected strategy and fallback](../../kickoff/selected-strategy.md).

## Reproduce

With Node and Python, the complete 3D contact comparison can be rebuilt from the compact project-owned measurements. An authorized copy of the FIRST field model is needed only to remeasure the source. Run from the project root.

```powershell
python experiments/depot-loading/report.py artifacts/depot-loading
```

To inspect the native registration and planar pickup controls, use the local source described in the [selected Fusion handoff](../../cad/own-zone-upper/design.md).

```powershell
python experiments/own-zone-cycle/field_register.py artifacts/own-zone-native/released-field.step artifacts/own-zone-native/depot-registration.json --include-name GE-26601
python experiments/depot-loading/pickup.py artifacts/own-zone-native artifacts/depot-loading/planar.json
```
