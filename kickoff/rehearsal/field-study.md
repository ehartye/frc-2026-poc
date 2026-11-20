# Six-robot field rehearsal

Play either alliance, follow its three robots, or edit their assignments before the clock starts. The field shows loose FUEL, the number of pieces on each robot, both scores and the current period. Open **Playback and match setup** to play three 160-second matches at 10×. [Field lab](https://ehartye.github.io/frc-2026-poc/field-lab.html#rehearsal) · [Compare alliance roles](https://ehartye.github.io/frc-2026-poc/alliance-roles.html#roleLab) · [Compare DEPOT lanes](https://ehartye.github.io/frc-2026-poc/depot-lanes/#rehearsal)

## The opening

The nominal six-robot match contains 504 FUEL. Each robot starts with its own eight preloads. Forty-eight pieces are queued off-field, 24 at each alliance OUTPOST. The remaining **408 loose pieces** occupy the carpet at kickoff. The lab uses 24 surveyed DEPOT positions per alliance and 360 modeled neutral positions. The neutral layout fits the released 72 × 206 inch staging footprint and leaves the 2 inch central divider gap. The kickoff manual allows approximately ±24 neutral pieces and variation in placement; these trials use the nominal count and a repeatable, slightly irregular distribution. Floor FUEL measures 5.91 inches across. The simulation uses 0.215 kg per piece. [Rule register](../rule-register.json) · [DEPOT coordinates from the registered field model](../../experiments/depot-loading/stock-register.json) · [Season inputs](profile.mjs)

| Robot on either alliance | AUTO | Student default after AUTO |
| --- | --- | --- |
| 1 | Score its own eight preloads from the lower approach | Collect released OUTPOST stock and return to the HUB |
| 2 | Score its own eight preloads from the middle approach | Work the DEPOT using the designated taller robot |
| 3 | Score its own eight preloads from the upper approach | Cross the low trench for accessible neutral FUEL |

Red rotates these datums through 180° about field center. All six starts, preload identities and approach routes are distinct. The published series also includes a parked reserve to test its effect on a teammate. These scenarios prescribe the score classification of a successful HUB attempt. The independent contact study and physical robot qualification have separate evidence.

## Finite human service

In V0, 24 pieces begin in each OUTPOST CHUTE. The chute holds approximately 25 behind a door. The manual permits the human player to introduce FUEL during AUTO. It also describes the lower opening and direct entry from the OUTPOST area. These trials use the chute and a single staffed outlet on each alliance. One queued ID is released at a time. The next piece waits while the first occupies its release slot. A waiting robot must physically reach the available piece to take it. The protected direct-catch area at a HUB exit is excluded from the prescribed returned-piece handoff. The 4-second return delay and two neutral landing datums are project assumptions about a random four-exit process. A missed or unresolved attempt has no asserted landing. [Kickoff §5.5, §5.9, §6.3.4 and gameplay authority](../rule-register.json)

The manual provides no guaranteed human cadence. The same six robots ran at the same speeds with identical programs and 1.5-second outlet collection dwells. By the end of the first 25-second shift, each alliance collected **8, 8 and 7** OUTPOST pieces when the human release took 0.75, 1.5 and 3 seconds respectively. In all three cases a full outlet stopped a second release during AUTO. [Service assumptions and executable trials](service-trials.mjs) · [Matched receipts](operator-trials.json)

## What changed when the pieces occupied space

The highlighted ring marks the ball a robot is pursuing. The gold segment across the front is the intake. Its 18-inch mouth and 5-inch extension are trial assumptions. A ball enters the hopper after its disk touches that segment. Each pickup preserves the individual ID and its contact geometry. The two end grids begin with 24 balls each. A robot can remove them individually from successive rows.

The displayed student roster delivers one ball every 0.5 seconds at an active HUB until its hopper is empty. Intaking and shooting have separate clocks. A closed window, full target or endgame interruption leaves the remaining balls aboard. On a tied AUTO the default trial assigns blue the first-period lead. Published comparisons retain their named batch and outcome assumptions.

| Published match | AUTO FUEL, blue–red | Final modeled score, blue–red | Pickups by slots 1 / 2 / 3, blue | Pickups by slots 1 / 2 / 3, red |
| --- | ---: | ---: | ---: | ---: |
| Own-zone supply | 24–24 | 46–46 | 24 / 0 / 0 | 24 / 0 / 0 |
| Neutral return | 16–24 | 70–74 | 24 / 22 / 44 | 24 / 22 / 48 |
| Missed preload | 24–8 | 74–64 | 24 / 22 / 44 | 24 / 22 / 48 |

The historical Own-zone supply scenario parks a reserve robot in the DEPOT approach. Neither DEPOT collector reaches stock in that case. Moving both reserves to the nearer trial waypoint permits four DEPOT pickups per alliance. Moving both deeper produces 21 blue and 23 red pickups. The student default assigns those reserve slots an active neutral role and separates their return lane. The [aggregate-station comparison](../match-series.md) preserves the earlier waypoint-based results.

The three complete clocks total 480 modeled seconds. Each side’s terminal score is added only after its terminal assessment. The audit reconciles every final piece across carpet, off-field reserve, cargo, returns and terminal outcomes, and checks each operator's release before robot admission. [Score and custody summary](match-summary.json) · [Live full event ledgers](https://ehartye.github.io/frc-2026-poc/match-series.json) · [Live physical input profile](https://ehartye.github.io/frc-2026-poc/match-profile.json) · [Independent checks](check-match.mjs)

Run `node kickoff/rehearsal/build.mjs PATH_TO_AGENT_FRC NEW_DIRECTORY` with the [reviewed plugin revision](https://github.com/ehartye/agent-frc/commit/1751f86b5bf69305b775415991cf48191549b53d) to regenerate the three student labs, their event ledgers and the physical role comparisons. Run `node kickoff/rehearsal/check-layout.mjs` to check all initial piece clearances and six opening jobs.
