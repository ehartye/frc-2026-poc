# What stays in the robot on the way to the HUB?

The earlier [collection trial](../sustained-loading/study.md) omitted the blue alliance wall. Eight loose FUEL moved several metres behind it. The corrected run gives the wall a contact surface at the registered ends of the two DEPOT side tubes and carries each body's position and velocity through the exact attained change of chassis frame. Wall rebounds change the pickup times. Starting with eight unspent preloads, the candidate collects sixteen DEPOT pieces before its scheduled departure in both refinements.

| Contact step | Last gate closes | Time left before departure | Onboard after transfer and settling | Closest uncollected FUEL to a tire during transfer |
|---|---:|---:|---:|---:|
| 0.250 ms | 29.68625 s | 0.31375 s | 24 | 110.5 mm |
| 0.125 ms | 29.337375 s | 0.662625 s | 24 | 80.1 mm |

All 32 individual states continue through the handoff, including the eight loose pieces. A loose piece begins the departure in contact with the robot in each run. The rearward drive first moves the loaded chassis 570 mm east across the registered rail. The nominal four-wheel contact model uses 58.86 kg gross, including 24 FUEL, friction coefficient 0.80 and 50 A per drive motor. It settles in 1.346 s. The remaining level-ground translation and turn follow a prescribed curve to the earlier one-piece scoring pose at field (−5.311, 0.970) m, heading −30.21°. At collection second 35 this curve stops. After three further seconds the 24 pieces remain in their lanes. The HUB receives zero pieces during this study. [Scoring-pose source](../own-zone-cycle/counter-replay.json) · [Carried-state model](carry.mjs).

The contact solver allows deformation. Across the collection runs, maximum nominal FUEL overlap with the wall reaches 16.3 mm. At handoff the nearest loose center is 58.8 mm (fine) or 83.5 mm (coarser) inside the wall. The nominal radius is 75.1 mm. The last storage stop also deflects the nominal sphere by up to 1.33 mm in transit. These are contact-model predictions. The study assumes a flat wall at the side-tube ends, a planar floor, an available DEPOT and a preceding 25-second inactive shift. It includes the DEPOT rails, tire clearance to loose pieces and chassis-to-piece contact. Whole-field traffic, swept chassis interference, module speed/traction during the prescribed turn and attainable flat-ground tracking still require qualification. This is cargo-retention evidence for that motion.

The eight supported preloads are still on the robot. Spending all eight in AUTO and then acquiring the same sixteen would leave **16 onboard, eight short** of the 24-piece shift objective. The strategy requires another eight acquisitions or an independently documented supply. The 12-second service result and the eight-point AUTO objective remain open.

| Refinement | Source gate checkpoint | After settling | Clock, controls and digests |
|---|---|---|---|
| 0.125 ms | [All 32 states](depot-125us.json) | [All 32 states](arrived-125us.json) | [Trial](study-125us.json) |
| 0.250 ms | [All 32 states](depot-250us.json) | [All 32 states](arrived-250us.json) | [Trial](study-250us.json) |

## Reproduce

Run these commands from the repository root. The compact JSON handoffs are regenerated from raw solver outputs. The acquisition inputs come from the [registered field and stock](../depot-loading/stock-register.json). Keep the [earlier late, coarse and stalled controls](../sustained-loading/results.json) when comparing changes.

```sh
mkdir transfer-runs
node experiments/depot-loading/stock.mjs experiments/depot-loading/stock-register.json transfer-runs/loaded-field-250.json blue-depot-01 paired-wheel-field .00025
node experiments/depot-loading/stock.mjs experiments/depot-loading/stock-register.json transfer-runs/loaded-field-125.json blue-depot-01 paired-wheel-field .000125
python experiments/loaded-transfer/receipts.py transfer-runs transfer-runs/checkpoints
node experiments/loaded-transfer/carry.mjs transfer-runs/checkpoints/depot-250us.json transfer-runs/loaded-bounded-transfer-250.json .00025
node experiments/loaded-transfer/carry.mjs transfer-runs/checkpoints/depot-125us.json transfer-runs/loaded-bounded-transfer-125.json .000125
python experiments/loaded-transfer/receipts.py transfer-runs transfer-runs/checkpoints --transit
```
