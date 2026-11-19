# R2C own-zone robot

[Orbit and play the student model](https://ehartye.github.io/frc-2026-poc/robot/) · [Open the editable Fusion archive](own-zone-public.f3d) · [Download the STEP](own-zone-public.step) · [Read the kickoff decision](../../kickoff/selected-strategy.md)

Open the F3D in Autodesk Fusion to inspect the stowed layout. Four swerve modules sit under the 680 mm square frame. The deployed intake reaches through a 300 mm bumper opening. Two moving shelves and a front guide and rear gate carry the ball vertically to the pair of scoring wheels. The 721.71 mm stowed height clears the project's 740 mm budget. A 3 × 4 × 2 grid fits 24 nominal FUEL inside the modeled hopper. This packing calculation leaves bulk filling, indexing and sustained feeding to a separate test.

## Which geometry students can edit

The [student-download reopen receipt](student-reopen.json) binds the 964,297-byte F3D, SHA-256 `5bed444ce5dc99caa94e38164be3c5cbfbefa6ed7106d2bb0370cbe1abf16dd3`, to an independent Fusion reopen and new STEP export. All 117 solids matched the published STEP exactly in tight bounds, surface area, volume, center of mass and face count. The native project-local intermediate export has its own archive identity.

The public assembly has 103 original single-body components with editable sketches and extrusions plus 14 project-drawn purchased-part envelopes. The [independent Fusion reopen](fusion-progress.json) and [STEP appearance map](appearances.json) identify the definitions and bounds. Positive X points forward, positive Y left and positive Z up. The public STEP SHA-256 is `d4ed979565fe132db45fac32de3265f93ffdff685db3bad976c4450fdfa67810`.

The project-local supplier master is `artifacts/own-zone-native/R2C/own-zone-supplier.f3d`, SHA-256 `ae65324c100cb681ff898bef86b5c209a76a9dc06b6ef3e04ef4d37db8999c70`. Its four REV-21-3005 MAXSwerve placements share the original 74-descendant definition. Its two scoring motor placements use the REV-21-1650 NEO definition extracted from that same supplier archive. The public file preserves the mounting frames using project-drawn envelopes. The [R1 drive handoff](../own-zone/design.md) records the options and supplier source. The R2C native rebuild inputs are in [prepare_upper.py](prepare_upper.py) and the two-guide modification in [fusion_guides.py](fusion_guides.py). Preliminary guides and drive transmissions require detailed design before fabrication.

## What one piece demonstrates

The [single-piece receipt](../../experiments/own-zone-cycle/single-piece.json) carries the same 215 g sphere from contact with the moving intake, through the guided lift, wheel contact, free motion and contact with the registered field surfaces. The chassis approaches at 0.38 m/s and brakes after pickup. The lift reaches a 540 mm handoff in 1.34 s. Removing the two guides, stopping the roller, or disabling both the approach and roller prevents that handoff. Lift and roller motion are prescribed under load. The approach is a local pickup trial at the scoring station. A loaded journey across the field and a sustained 24-piece run still need separate evidence.

| Assumed contact stiffness | Half initial free speed | 70% initial free speed | 90% initial free speed |
|---|---|---|---|
| 7,500 N/m | Falls short | Falls short | Falls short |
| 15,000 N/m | Falls short | Falls short | Falls short |
| 30,000 N/m | Falls short | 269 mm aperture margin | 294 mm aperture margin |

The seven short cases peak between 0.974 m and 1.390 m. The registered opening stands at 1.829 m, so reducing horizontal stand-off alone cannot recover those cases. The better result depends on the assumed foam/contact behavior and initial wheel state. The cases are a sensitivity study with equal display weight and carry no statistical prediction.

The stationary-counter control uses the middle initial speed in the bottom row. The ball reaches the funnel base, transverse roller, ramp, internal wall and bottom plate. The [powered-counter and traffic comparison](../../experiments/own-zone-cycle/counter-study.md) follows the same FUEL through channel 3 on the clear approach. The showcase plays this later run. Repeated service at 2 FUEL/s remains open.

## Reproduce the checks

With Python, NumPy, OCP and VTK installed, run `python cad/own-zone-upper/verify_upper.py` to reopen the public STEP, match every named solid and check stowed and storage bounds. To recreate the field contact evidence, obtain the identified [FIRST kickoff field STEP](https://firstfrc.blob.core.windows.net/frc2026/FieldAssets/FE-2026-rev-rebuilt-playing-field.step). Keep it in the project-local artifact directory. Its SHA-256 is `2ad90e42f2c2db0fab5b22bb65aa0851089e414d568d4ebd127624fa230c7671`.

```powershell
$cache = "artifacts/own-zone-native"
python experiments/own-zone-cycle/field_register.py "$cache/released-field.step" "$cache/field-registration.json"
python experiments/own-zone-cycle/field_mesh.py "$cache/released-field.step" "$cache/blue-hub-private.npz"
python experiments/own-zone-cycle/run.py $cache
python cad/own-zone-upper/animated.py
```

The animation uses the [sampled run](../../experiments/own-zone-cycle/counter-replay.json) and Fusion geometry. The shelves' illustrative return is displayed separately from the ball contact calculation. The student site uses the Apache-2.0 [Google model-viewer 4.1.0](https://github.com/google/model-viewer/tree/v4.1.0) runtime and keeps its license alongside the bundled copy.
