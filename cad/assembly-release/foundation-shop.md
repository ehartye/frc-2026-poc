# Drivetrain foundation shop traveler

This engineering revision keeps the 680 mm frame width and shifts the four wheel centers from (±268, ±268) to (±265, ±265) mm. Each wheel center is 38.10 mm above level carpet. Positive X faces the intake and positive Y faces the robot's left. All cut, hole and station dimensions below are in millimetres unless stated otherwise. The previous parked model is [R2C-T1](../tower-lift/tower-l1.f3d).

## Cut frame stock

| Article | Qty | Stock and supplier | Square finished length | Installed datum |
| --- | ---: | --- | ---: | --- |
| Side rail | 2 | 6061-T6 rectangular tube 25.4 × 50.8 × 3.175 wall, Online Metals 18003 | 680.0 | X −340 to +340, Y ±327.3, Z 89.4 center |
| Rear rail | 1 | Same 18003 | 629.2 | X −327.3 between side-rail inside faces |
| Front return | 2 | Same 18003 | 164.6 | X +327.3, between absolute Y 150 and 314.6 |
| Deck crossmember | 2 | 6061-T6 square tube 25.4 × 25.4 × 3.175 wall, 18014 | 616.50 | X −151 and +129, top Z 122 |
| Crossmember backing plate | 4 | 6061-T6511 extruded flat 6.35 × 50.8, Online Metals 1145 | 63.50 | Centered on the crossmember at each rail, Z65.50 to Z129.00 |
| Hopper post | 4 | 6061-T6 square tube 19.05 × 19.05 × 1.5748 wall, 18011 | 88.95 | Above each crossmember at Y ±294 |
| Hopper sill | 2 | Same 18011 | 480.0 | X −330 to +150, Y ±294, top Z 230 |

These sections use the manufacturer's nominal straight-wall dimensions. The model uses square idealized stock corners. Inspect the delivered outside radii, actual rail wall, straightness and heat-lot identification before accepting the stock. The [rail](https://www.onlinemetals.com/en/buy/aluminum/1-x-2-x-0-125-aluminum-rectangle-tube-6061-t6-extruded/pid/18003), [crossmember](https://www.onlinemetals.com/en/buy/aluminum/1-x-0-125-aluminum-square-tube-6061-t6-extruded/pid/18014) and [post/sill](https://www.onlinemetals.com/en/buy/aluminum-square-tube-6061) are catalog sections.

The four crossmember backing plates are 6.35 × 50.80 aluminum 6061-T6511 flat bar, cut to 63.50 and installed vertically. Their outer faces bear against the side rails at absolute Y 314.6, inner faces at 308.25. The plate extends from Z65.50 to 129.00, providing a flat seat for the upper as well as the lower crossmember wall. Fixture and weld the bottom and both long edges of the backing plate to the rail before fitting the crossmember. Only the lower 49.30 mm has an opposing side-rail face. The top 14.20 mm is a cantilever. [Online Metals 1145](https://www.onlinemetals.com/en/buy/aluminum/0-25-x-2-aluminum-rectangle-bar-6061-t6511-extruded/pid/1145)

## Machine the saddles and rails

Machine eight 6061-T6 blocks. The two orientations on each module use the same finished section. The saddle is 26.10 thick across the local U direction, 35.70 along V and 50.80 between the supplier plates. Orient U inward from the chassis wall, V along the tab hole row and H upward. In the supplier reference frame each saddle occupies U −49.60 to −23.50, V 52.00 to 87.70 and H 31.75 to 82.55. On the other tab, exchange the two horizontal source coordinates. The [dimensioned drawing](foundation-saddle.svg) uses finished faces as datums.

1. Machine the two H faces parallel within 0.05. Measure the gap on the actual module and finish the saddle to fit with 0.00–0.05 clearance. Inspect seating at both ends. Do not pull the supplier plates inward to fit an undersized block.
2. Bore the two vertical holes Ø5.30 +0.05/0 through H. Their axes are U −31.75, V 57.15 and 82.55. From the outside rail face of the saddle these are 17.85 inward and 5.15 or 30.55 from its low-V end. Use a paired fixture to hold true position within a Ø0.10 zone. Gauge both holes against the selected article.
3. Drill two Ø6.50 +0.10/0 U through-holes at V 69.85, H 46 and 67. These are 17.85 from the V datum and 14.25 and 35.25 above the bottom. Add two Ø10.70 U through reliefs at V 57.80/81.90, H 57.15. The pair permits access to the internal supplier cap-heads. Break exposed edges 0.2–0.4, preserving the plate lands.
4. Match fixture the rail bosses to the U-axis holes. At each of the 16 positions make a Ø13.10 insert hole in the inboard wall only. Each turned 6061-T6 boss has Ø13.00 OD and length 16.00. Keep the outer tube wall intact. Locate the inboard boss end flush with the saddle face. Prepare a circumferential weld groove, weld in the fixture and finish face flush. Accept seat flatness ≤0.05 before tapping. Drill Ø5.00 through then tap M6×1-6H through. A finished hole with the Ø5.00 tap-drill profile represents a conventional simplified internal thread in CAD.
5. For crossmembers and posts, fixture square-cut ends with 0.25 maximum assembly gap. The post center at Y ±294 leaves 3.175 land on each side in X and 4.725 to the adjacent backing plate in Y. The proposed 1.5 fillet runs around the post foot before nearby parts are installed. A qualified welding procedure and load check must establish allowable post/rail/boss joint strength after welding. The base-stock T6 temper does not represent the as-welded heat-affected zone.

## Fit the purchased hardware

| Article | Qty | Design check |
| --- | ---: | --- |
| REV-21-3005 module, source revision in [selection](../own-zone/layout.json) | 4 | Four unique paired tab axes per corner. Each lower/upper throat is Ø5.0. Keep native STEP private. |
| Bolt Depot 8232, #10-32 × 2¾ in ASTM A574 socket head | 16 | Listed minimum thread length 22.352. The shaft crosses both original tabs and one saddle. Use a 5/32 in key below. [Supplier screw](https://boltdepot.com/Product-Details?product=8232) |
| Bolt Depot 2623, regular zinc steel nylon-insert #10-32 locknut | 16 | 3/8 in AF. Maximum height 6.3246 leaves 4.77665 mm nominal thread beyond nut on the 58.74875 stack. Use the listed nut and inspect full nylon engagement. [Supplier nut](https://boltdepot.com/Product-Details?product=2623) |
| pgb-Europe 20659, ISO 4762 M6×40 cap screw, 8.8 | 16 | 5 mm hex. Its 24 mm thread length covers the 13.90 nominal axial reach into a 16 mm boss. Inspect the full-form engaged length after accounting for the screw tip, weld-face cleanup and entry chamfer. [Supplier screw](https://www.pgb-europe.com/en-gb/20659/socket-cap-screw-8-8-pt-iso4762-m-6x40) |

Install saddle and long screws on the detached module first. Both vertical screws pass freely through the matched holes. Fit locknuts and check the carrier rotates independently. Raise that unit between the perimeter faces and fasten each saddle from inside the frame. The four module sites are independent. Match the fastener to its drive and do not apply a published dry torque to a different plated, lubricated or aluminum-threaded joint. A joint-specific preload and slip qualification remains open.

## Evidence boundaries

The exact supplier STEP and a 360-degree conservative envelope separately exercise mounting interference. Tool calculations use bounded straight keys/socket bodies. Wrench handles, standard extrusion corner radii, wiring and removable bumper service are distinct checks. The nominal static region supports a geometry decision. No physical load, weld strength, inspection mass, motor performance or swerve odometry measurement has been made. Update the kinematics module locations to 0.265 m in both chassis directions when issuing controls for this revision. Existing scoring and climb simulations belong to their named earlier robot.
## Corner load sensitivity

The [elastic mount calculation](module_loads.py) registers the four M6 rail screw centers of one installed corner. It applies a 62 kg gross scenario with 2 g vertical reaction, then evaluates 0.5, 1 and 2 g lateral reaction in eight directions. No friction or clamp preload is credited. The reported pairwise maxima span nine combinations of shear, tension and compressive bearing stiffness. The directions and fasteners producing each column's maximum may differ.

| Load assigned to the corner, at 2 g vertical and 2 g lateral | Largest M6 combined stress | Gross thread-flank shear demand | Mean circumferential weld demand |
| --- | ---: | ---: | ---: |
| Quarter | 53.1 MPa | 9.8 MPa | 15.1 MPa |
| Half | 106.1 MPa | 19.6 MPa | 30.2 MPa |
| All | 212.3 MPa | 39.2 MPa | 60.3 MPa |

The last line includes a maximum 3.66 kN tensile reaction. Thread area assumes 11.9 mm full-form engagement after two pitches of allowances. Weld area assumes a continuous 1.5 mm effective throat around the 13 mm boss. The available as-welded strength, prying, shell bending, thread tolerances, fatigue and actual reaction distribution must be established separately. No 62 kg robot was weighed.
