# Three complete REBUILT match rehearsals

[Play the student field lab](field-lab.html#rehearsal). Choose the published series to replay the three project scenarios, or edit the robots and choose the student setup to test your behaviors across the same scenarios. Select **Play match series at 10×**. Reset restores your edited setup. Add red and blue robots in either order in a separate manual trial. Compare stock markers, carried FUEL, scoring attempts, alliance score and blocked paths.

Each match runs a 20 s AUTO, 10 s transition, four 25 s shifts and 30 s end game. The fixed-step model advances 480 simulated seconds in the 48-second series playback budget. All six students' robot roles have distinct starts and configured autonomous and teleoperated behaviors. Slot 2 on each side uses the 680 mm frame, 76 mm bumpers and 740 mm design-height budget. Other slots represent low-profile partner robots. The neutral runner crosses the high-side trench. Each occupied body must clear the structures and the other robots.

| Match | AUTO result (blue–red) | Assumption exercised | Modeled final score (blue–red) |
|---|---:|---|---:|
| Own-zone supply | 24–24 | FMS tie scenario gives blue the first inactive shift; no neutral runner | 36–40 |
| Neutral return | 16–24 | One blue preload batch misses. Each side sends a low-profile neutral runner. | 48–52 |
| Missed preload | 24–8 | One red batch misses and one has an unresolved observation. Blue takes first inactive shift. | 52–40 |

## Read the field

The blue alliance wall is X = 0. +X points downfield and +Y away from the blue outpost end of its wall. Red field positions rotate 180° about midfield. The field measures approximately 651.2 × 317.7 in. The blue HUB pad occupies X 158.6–205.6; its center is (182.1, 158.85). A robot acts at an assigned legal alliance-zone pose, separate from the physical HUB center. At every chosen shooting pose the entire robot bumper lies in its alliance zone.

The nominal 504-piece stock consists of 24 in each depot, 24 in each outpost chute, 8 per robot and 360 in the neutral area. No piece is issued to two robots. The release drawing puts each depot against the alliance wall and each outpost at the outer end. The blue depot marker (12.0, 234.85) in is the centroid of its 24 staged spheres in the [official kickoff STEP](https://firstfrc.blob.core.windows.net/frc2026/FieldAssets/FE-2026-rev-rebuilt-playing-field.step), SHA-256 2ad90e42f2c2db0fab5b22bb65aa0851089e414d568d4ebd127624fa230c7671. The outpost wall datum (0, 30) in is a Figure 5-4 estimate. Both use the nominal inside field boundary. The two locations (42, 233) and (34, 32) are the modeled **chassis action** positions. This action radius represents an available handoff, without solving a roller-to-piece contact. Section 6.3.4.1 specifies the 72 × 206 in center-field staging frame and the 2 in gap between its halves; 180 per half is the project's nominal allocation. Scored FUEL returns to a designated neutral pile after an assumed four seconds. Real HUB outputs send it into neutral space at random. Missed and unresolved pieces remain distinct in the terminal ledger.

## What counts

A script can prescribe a successful full HUB passage, a miss or an unresolved attempt. Only a prescribed success at an eligible active HUB earns one modeled point per FUEL. AUTO, transition and end game are active for both alliances. Odd shifts are inactive for the AUTO winner; even shifts are active for that alliance. The table counts the registered scoring event within its interval. It models neither target sensor lag nor post-interval processing grace. This is a tactical rehearsal for students. Validation of the physical intake, a real scoring shot and target sensor remains a separate experiment.

The [full receipt](match-series.json) contains all six robot poses at every period boundary, waits, piece identities, stock, cargo, returns, terminal outcomes and score events. The [source model](rules-model.json) includes the game-specific station and program definitions. The [rule register](rule-register.json) identifies FIRST V0 and TU00 with source hashes. `node scripts/check-match-series.mjs` independently recomputes points from event outcomes, checks the AUTO leader and phase entitlement, proves all 504 identities are conserved at each final whistle, and requires both alliances to have acquired and scored pieces.
