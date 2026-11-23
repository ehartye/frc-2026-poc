# Own-zone scorer strategy

The project coordinator selected the own-zone scorer for this prebuild POC under authority delegated by the owner. The owner requested visible pickup, shooting and scoring-target evidence. Students can revisit the decision after trying the [field lab](field-lab.html). The [kickoff study](study.md) preserves the original open decision and both candidate roles.

During AUTO, start with up to eight supported FUEL, move to a legal launch pose in the alliance zone and aim for eight sensor crossings while the HUB is active. During an inactive shift, collect and hold the next allocated stock. Prioritize a nearby depot or a committed partner delivery. Move loaded and score while the own HUB is active. If supply or traffic consumes the service window, score the available batch and return to collecting. A neutral collector can reach a larger stock but pays for two field crossings, roof clearance, contested space and the receiver's service. The six-robot rehearsal recorded a 13.05 s wait in its AUTO scenario. That observation motivates a congestion trial in a shift; it does not establish a shift delay.

## When does the clock start?

The original staged calculator allowed arrivals and travel to overlap. If all 24 are onboard at the source by second 5, a **subsequent** five-second loaded transfer and three-second setup leave 12 s in a 25 s shift. That requires 2.00 pieces/s, with zero scheduling slack. Five more seconds of travel leave seven seconds for 14 pieces at that rate. Stock ready at second 18 leaves zero service seconds. By comparison, prepositioned supply at the delivery end gave the original 17 s window and 1.41/s requirement. We adopt the serial, loaded-transfer case for design. The empty return and next supply allocation must be budgeted separately. A missed handoff reduces this robot's target. An inactive HUB awards zero points.

## What CAD and simulation must demonstrate

The provisional 680 × 680 mm frame uses 2,720 mm of the 2,794 mm perimeter budget. The 740 mm starting-height allowance leaves 22 mm under the rule limit and gives up trench access. A 478 × 622 × 317 mm clear storage box admits a rectangular 3 × 4 × 2 stack of 150.114 mm nominal spheres with 4 mm interpiece spacing. Reducing the 622 mm side by 11 mm fails that stack. This test screens empty volume. Wall thickness, operating positions, gravity feeding, jams and retained loads require the assembled robot. A single-row feeder remains viable if its observed service interval meets 0.5 s.

| Student observation | Pass condition |
|---|---|
| Start envelope and receipt | Chassis, intake and stored FUEL clear their registered boundaries at the start pose. |
| Acquire and retain | Match a physical observation to each FUEL entering the robot. Preserve identity during transit and interruption. |
| Feed and score | Up to 24 distinct releases and full opening and sensor crossings before the active deadline. A test that stops at the opening may claim only aperture feasibility. |
| Loss of evidence | Stop counting at the last observed state. Compare low-supply, obstructed and inactive controls. |

Run `node scripts/check-strategy.mjs` from this repository. The input [decision and requirements](selected-strategy.json) uses the dimensions in the [release-day rules register](rule-register.json) and [field profile](field-profile.json). Vendor selection and subsystem packaging follow this decision. The earlier differential-drive fixture is a historical control.

## Reserve the final TOWER berth

Under the same delegated authority, the own-zone scorer carries a low-rung fallback. Before interrupting FUEL service, compare the expected points still available from that service with ten times the chance of a qualified Level 1 hang. With three seconds for approach and nine seconds at the berth, ten points breaks even at 0.83 FUEL/s. If 24 pieces and the planned 2 FUEL/s were actually available the opportunity cost could reach 24 points. With eight available and no replacement source it is at most eight. Clear the partner's route before committing. The prebuild route rehearsal and isolated mechanical hang provide separate evidence.

The final 30 s is a shared active-HUB period. TELEOP TOWER levels are worth 10/20/30. R2C-T1 pursues the first. Its 754 mm stowed height uses 14 mm more than the earlier 740 mm design budget and leaves 8 mm under R107. Keep the eight-FUEL AUTO objective for this robot. A successful AUTO Level 1 could earn 15, subject to the two-robot alliance cap, but its approach, hang and return to collection have no joined evidence in this project's AUTO. See the [climb geometry and controls](../experiments/tower-climb/study.md) and [actual scenario decisions](match-series.md).

## Reserve the depot entrance

When slot 2 takes the depot, assign slot 3 the deep reserve at blue-frame (109, 268) inches, mirrored on red. With the original central parking point both allies blocked each other after AUTO. Moving just one alliance’s reserve restored 24 named depot acquisitions on that side over a full match. A nearer reserve restored only four. The original 30-second refill trials reached 0, 8 and 12 of the 24 fresh pieces required after spending the preloads. Use observed available stock when committing the next service and keep the terminal fallback. [Seven-match field comparison and support checks](../experiments/role-and-support/study.md)
