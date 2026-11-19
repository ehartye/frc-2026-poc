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
