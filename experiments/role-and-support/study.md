# Leave the depot lane open

Play the seven full matches in the [reserve-lane field lab](https://ehartye.github.io/frc-2026-poc/depot-lanes/#rehearsal). Choose the published match series for the controlled comparison. The first match starts all six robots at their original positions. Later matches change where a reserve robot parks after AUTO. The lab runs complete 160-second matches at 10×. The [original field lab](https://ehartye.github.io/frc-2026-poc/field-lab.html#rehearsal) retains its three earlier scenarios.

## Agree on two alliance roles

In the [interactive role comparison](https://ehartye.github.io/frc-2026-poc/alliance-roles.html#roleLab), choose **alliance-depot**, **neutral-return** or **partner-reserve** for B2. Select a match context, inspect its waiting and travel, then replay the complete match with the other five robots unchanged.

In the original own-zone plan, the depot robot and reserve robot try to cross paths just after AUTO. Blue's B2 stops around (81, 166) field inches and B3 stops around (105, 200). Red reproduces the conflict at the opposite end. Both depots still hold all 24 pieces.

| Reserve robot's destination after AUTO | Distinct pieces B2 retrieves | Distinct pieces R2 retrieves | Modeled match score, blue–red |
| --- | ---: | ---: | ---: |
| Both use the original (55, 157) | 0 | 0 | 46–50 |
| Both move to (111, 247) | 4 | 4 | 50–54 |
| Only blue moves to (109, 268) | 24 | 0 | 54–50 |
| Only red moves to the mirrored (109, 268) | 0 | 24 | 46–70 |
| Both use the deeper reserve | 24 | 24 | 54–70 |

Use the deeper reserve when the alliance assigns the depot to B2 or R2. Agree which peer clears the entrance before scheduling a pickup. The listed coordinates are in the blue field frame. Red positions rotate 180 degrees about field center. The asymmetric scores reflect the match's existing active windows. Individual admissions, identity and timing are available in the [seven-match receipt](https://ehartye.github.io/frc-2026-poc/depot-lanes/results.json). Points are assigned by the rehearsal's published scoring assumptions.

Changing only B2's role gives a complementary test. Against peers leaving the supply lane, B2's own-zone depot program receives 16 modeled post-AUTO piece points across the match, versus zero for the same robot's low-trench neutral program. In the blocked context, both roles retrieve zero. The comparator retains the assigned AUTO behavior, height, stock, other five robots and terminal commitment in each published match. [Role definitions](study.json) · [Release-day profile](../../kickoff/rules-model.json)

## Check the collection and field clocks separately

Two complete nominal time-step runs compare the single sideways carriage against the paired direct lanes. By eight seconds, each single-carriage run retains **one new piece and the eight preloads**. Each paired run retains **two new pieces and the eight preloads**. Locked transfer gates produce zero new admissions in either architecture. Prefer the two direct lanes for the next loaded-intake study and require a detected transfer or a recoverable stop before relying on the next admission. The geometry is a simulated candidate. [Source geometry and timed three-dimensional trials](../depot-loading/study.md) · [Full per-piece receipts](../depot-loading/results.json)

The original plan spends eight preloads in AUTO. A full refill then requires **24 fresh pieces**. In the first inactive shift and the next five active seconds, B2's modeled depot admissions total **0, 8 and 12** in the three original six-robot scenarios. Their rates are 0, 0.267 and 0.400 pieces/s against a required 0.800/s. Each window includes waiting and transit. A 24-piece total across an entire match leaves the short-window requirement open. The selected narrative also calls for a later 12-second scoring service. Each of these acquisitions stops at B2's cargo register. [Mission clock and supply conditions](../../kickoff/selected-strategy.md)

## Decide whether the robot can hang

At the earlier R2C-T1 lift's full 100 mm working stroke, the compliant contact simulation with 62 kg gross produced 304.0 N vertical at each hook and 50.99 mm minimum tire clearance after cutoff. An assumed 68 kg gross with its center shifted forward gave 48.80 mm. Reducing thread friction permitted backdrive, leaving 36.85 mm of minimum tire clearance over two seconds unpowered. An early power cut left the tires supporting the robot. The grade, all-up mass, shock, brake duty and long-duration holding capacity still need independent evidence. [Time-dependent load, power loss and ground contacts](../tower-climb/study.md)

The two 12 mm hook plates center their contact lines at transverse positions −88 and +88 mm. At 68 kg with the center of gravity 50 mm off-center, static vertical demand is 523 N on the near hook and 144 N on the far hook. At 88 mm the far reaction reaches zero. With only one hook landed and centered mass, the remaining line carries 667 N and leaves **58.68 N·m of roll moment**. An independent resisting contact would be needed to hold that pose. A later joint is also unresolved: each of the four mast feet has 144 mm² of compression seating on its side rail in the issued foundation. Lifting the frame pulls those interfaces in tension. Both the fastened/welded load path and its capacity must be established. [Roll sensitivity](tower-roll-screen.json) · [Four native mast seats](mast-foot.json) · [Rated load-path inputs and open capacities](lift-model.json)

The bench cart supports the full robot at four rail pads during battery removal. Its lift, locks and rated capacity remain open. The battery sled and keeper support the installed pack as a separate load case. A complete, weighed or conservatively bounded dressed robot and the installed anchors remain prerequisites to a full-weight release.

## Reproduce

From the project root, run the following with the reviewed Agent FRC checkout. The first command writes the full match executable results, design comparison and both load and throughput assessments. The second emits the standalone interactive lab and its admissions register into a fresh directory.

```sh
python experiments/role-and-support/review.py PATH_TO_AGENT_FRC role-results
node experiments/role-and-support/replay-lanes.mjs PATH_TO_AGENT_FRC role-lab
```

All game geometry, scoring and clock assumptions trace to the January 10 release-day V0 and Team Update 00. The parking changes are project strategy comparisons. [Source cutoff and hashes](../../kickoff/rule-register.json)
