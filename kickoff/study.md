# Kickoff field study and student decision

**January 10 kickoff, end-of-day Eastern cutoff.** The ordinary-match study uses FIRST's English V0 and same-day Team Update 00. The later competition manual and the archived subsystem regression belong to separate evidence sets. The [register](rule-register.json) maps each rule to its source section, modeled value or unresolved consequence. The installed Agent FRC workflow compiled the [field profile](field-profile.json) and register into the [reviewed model](rules-model.json).

## Try the kickoff lab

Open [field-lab.html](field-lab.html) from a local checkout in a browser. Compare the loose robot box to the field in the overhead and robot views. In the rehearsal, add blue and red robots, choose their behaviors and run through a period. Change one dimension, heading, source-arrival time or handling rate at a time. Save an opportunity and observation before downloading the narrative. The blue and red HUBs are distinct. The two scoring menu entries describe mutually exclusive schedules for **one alliance's HUB**.

The field is approximately 651.2 × 317.7 in. The legal starting frame perimeter tops out at 110 in and starting height at 30 in. A nominal trench opening is only 50.34 in wide and 22.25 in high. The trial uses a 26 × 26 × 20 in box plus 3 in of bumper thickness on each side. Change those assumptions before inferring a packaging constraint. Both a 20 in and a 24 in design pass the rule's height maximum. Only the shorter trial passed this nominal, straight trench path. A 25 × 30 × 20 in box with assumed 4.5 in bumpers at 45° hit a side allowance. A BUMP crossing needs a separate pitch and ground-clearance study. [Trial evidence](trials.json)

## How much FUEL can one robot use?

Each ordinary match starts with 504 nominal FUEL. The two depots and two outpost chutes each contain 24. Robots can preload up to 8 apiece. With six full preloads the neutral area holds 360 nominal pieces, rising to 408 with no preloads. Field staff can vary neutral staging by about 24. Recycled pieces re-enter neutral space. A robot can count only the share it can actually collect or receive before the deadline. [Register, §6.3.4](rule-register.json)

A match lasts 160 s. Both HUBs are active during the 20 s AUTO, 10 s transition and 30 s end game. Four 25 s shifts alternate which HUB is active. The alliance with more AUTO FUEL has its first shift inactive, and the FMS resolves ties. That leaves each alliance 110 nominal active seconds. A scored FUEL is worth one point when active. The FUEL must actually pass through the opening and its sensor. Processing grace does not extend the available time for a robot to act. [Register, §§6.4–6.5](rule-register.json)

The following scenarios allocate 24 pieces to one robot by second 5 in a 25 s shift, except where noted. The staged case assumes one 5 s loaded transfer and 3 s setup. Its empty return falls outside this scoring window and must be budgeted in the next cycle. The single-piece route assumes 2.5 s each way and 0.5 s combined acquisition/release service per piece. Both compare the same goal, stock and clock. The physical capacity to hold 24, collect them on schedule and score them is an open design question.

| Opportunity and change | Pieces delivered | What sets the limit |
|---|---:|---|
| Staged transfer, one piece/s | 17 of 24 | 17 usable seconds require 1.41 pieces/s for 24 |
| Same shift, two pieces/s | 24 of 24 | Allocated supply |
| Same rate, five extra travel seconds | 24 of 24 | Exactly 2.00 pieces/s required, with zero service margin |
| Same rate, all 24 arrive at second 18 | 14 of 24 | Seven seconds remain, requiring 3.43 pieces/s |
| Single-piece round trips | 4 of 24 | Travel alone for 24 exceeds the entire shift |
| Same staged delivery, own HUB inactive | 24 delivery opportunities, zero points | HUB state |
| Independent AUTO case, eight preloads | 8 of 8 | Three seconds transit and two seconds setup leave fifteen seconds, requiring 0.53 pieces/s |

The first trial rules out a **one-per-second** feeder for that particular 24-piece goal. A faster single-file feeder is still a candidate. One-piece round trips and single-file feeding impose different limits. The goal changes substantially with partner supply and the clock. The [saved trial inputs and outputs](trials.json) expose both.

## Where traffic changes a design requirement

For Shift 1 the route model draws a 175.57 in candidate line from a neutral collection patch to a trial legal shooting position. It predicts overlap with blue partner slot 2 from the start poses, supply and destination. This line is a corridor hypothesis. The rehearsal considers occupied footprints, roofs and obstacles and follows the separately prescribed waypoints.

In the six-robot AUTO trial, the neutral runner and depot runner on each alliance independently waited 13.05 s apiece where their approaches converged. The nominal route assumed 72 in/s. Students can stagger departures or change the designated receiver's lane, then compare the waits. A collector assigned to the crossing should stow inside the tested travel envelope, retain buffered FUEL and resume feeding after a prescribed interruption. Traffic evidence supplies a scenario for testing. Force sizing still requires mass, relative speed, contact direction, stopping distance and fastening inputs. [Period histories and clearance outcomes](trials.json)

## Student strategy brief

**Decision owner:** student design team. **Status:** awaiting role selection. The paragraphs below are experiment candidates written for the team to compare. No team member has selected them.

| Candidate role | Whole cycle and fallback | Provisional evidence requirement |
|---|---|---|
| Own-zone scorer | Start with up to eight preloads, move to an own-zone launch pose, stage and score while the HUB is active. Use an allocated depot or partner supply next. If the handoff arrives late, take the smaller reachable allocation and preserve the next active shift. | With 24 available by second 5 in a 25 s active shift, deliver 24 in the remaining 17 service seconds. Observe pickup, retention and clear-down separately. |
| Neutral collector and returner | Start at a legal line pose, cross the near trench, acquire the assigned neutral stock, retain it through the return and stage it in the alliance zone for scoring. If the trench is blocked, yield and switch to available own-side stock. | Complete the return with a 20 in stowed box, record travel and wait, and hold at least 2 pieces/s if congestion consumes five seconds. Check partner ownership and the receiver's service rate. |

In the lab, record who chose the role, the cycle in their own words, the clock and allocation used, one fallback trigger, the test that could change their choice and its pass/fail measure. Keep the exported observations beside the brief. Hardware selection starts after the team records this choice. The earlier one-preload differential-drive and roller study remains an [archived subsystem experiment](../docs/VERIFICATION.md).

## Reproduce

From this project root with Agent FRC **0.26.0** installed, point `$plugin` to that install. Create fresh generated files in the ignored artifacts directory so the tools can enforce their no-overwrite rule.

```powershell
node "$plugin/scripts/project-layout.mjs" init .
node "$plugin/scripts/rules.mjs" review kickoff/rule-register.json
node "$plugin/scripts/rules.mjs" compile kickoff/rule-register.json kickoff/field-profile.json artifacts/rebuilt-kickoff-model.json
node "$plugin/scripts/kickoff.mjs" --profile artifacts/rebuilt-kickoff-model.json --output artifacts/rebuilt-field-lab.html
node scripts/check-kickoff.mjs "$plugin"
```
