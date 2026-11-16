# 2026 design and limits

Fixed-angle HUB approach and launch. 12 V gives about 252 mm whole-sphere thin-plane margin; 9 V fails.

The proof of concept starts preloaded. It links an ideal differential-drive approach to stationary virtual retention, guide closure, powered release and finite-body target analysis. Target-relative chassis pose and generated exit speed are carried through without substituting a perfect dock or invented score.

## Informed simulation inputs

Straight rigid guide; prescribed contact normal force 15 N and friction coefficient 0.8; ideal virtual sensors and retention; declared mounting transform; constant gravity after exit. These are provisional model inputs, not sourced hardware ratings or measured calibration. CORAL floor friction values 0, 0.1, 0.3 and 0.5 are hypotheses; source-backed mass endpoints are 1.1 and 1.8 lb. NOTE attitude is fixed; FUEL is spherical. Source URLs and drawing hashes live in shared/case-studies/target-frame-evidence.json and piece nominal files. Official drawings and vendor assets are not bundled.

## Preserved controls

9 V versus 12 V, CORAL original versus refined plan and mass boundaries, stalled pose timestamps, immobilized drive, invalid season, and runtime energy/continuity checks. Passing tests mean model invariants hold, not that every shot succeeds.

## Remaining integration

Empty-robot acquisition, field/chassis/bumper collision envelope, mechanical packaging, compliant contacts, real sensors, drive traction and energy, simultaneous drive/mechanism supply, recoil and installed target interactions. No whole robot CAD exists here yet. Sideplate CAD is earlier concept geometry, not a claim that it mates to this plant. Do not manufacture from it without engineering review. No physical robot deployment, calibration or safety validation is included.
