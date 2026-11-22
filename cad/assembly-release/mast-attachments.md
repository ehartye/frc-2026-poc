# Tower mast attachment comparison

Each mast in the issued foundation touches the side rail over a 144 mm² tube end. That surface can carry compression. A lift also pulls upward on a mast foot during part of its travel. The issued assembly has no fastening feature across any of the four feet. The following concepts use the same four foot centers and the registered climb motion.

| Attachment | Result under the modeled load | Design consequence |
| --- | --- | --- |
| M8 transverse fastener through the original 2 mm tube wall | With 60% of the factored pin force on one wall, the calculated bearing stress reaches 171.5 MPa in the original heavy case. | The wall exceeds the 150 MPa study limit. |
| Fitted 12.55 mm cross sleeve through the original mast | One-wall bearing reaches 147.7 MPa at 68 kg and 35 mm forward CG. Changing the assumed upright bumper stiffness from 64 to 32 kN/m raises it to 150.8 MPa. Moving the CG to 50 mm with the softer bumper raises it to 158.4 MPa. | Similar assembly and loading conditions could reverse the design decision. Preserve these cases as controls. |
| Full-height M8 tie with upper and lower pilots | Axial tension passes through the rod from the upper plate to the rail. The 20 × 20 × 3 mm tube carries compression. Both pilots register the tube laterally. | Carry this concept into native CAD and review its end seats, locking hardware, tolerances and access under the same load conditions. |

## Geometry students can inspect

The four axes are at X −180 and −280 mm, Y ±326 mm. Each mast spans Z 114.8 to 744 mm. Face each tube to 629.2 mm and measure the clear opening and corner radii after finishing. Cut each pair of removable octagonal keys to 0.20 mm below the smallest measured opening across flats. The nominal 13.80 mm key assumes a 14.00 mm clear opening. Retain 2.25 mm corner relief. Fit the actual key and tube together over the 26 mm engagement before assembly.

The initial two-nut tie peaked at Z 763 mm, exceeding the 762 mm starting height. The current 694 mm M8 rod terminates inside a keyed upper head. A 19 mm diameter, 4 mm thick flange bears directly on the upper plate, with its top at Z 754 mm. The gross threaded engagement is 27 mm. An equivalent 24.5 mm length is used for the nominal thread shear screen after two pitches are deducted. A cut 6.8 mm tap pilot in the CAD carries the machining intent. The positive geometric overlap of thread major diameter and tap pilot is expected in that representation. The lower washer bears beneath the rail. A fitted internal sleeve supports the two rail walls. The axial load crosses the registered washer faces and the rod threads. The lower Ø12.60 mm pilot engages the Ø12.90 mm rail hole. The upper head uses matching relieved flats across its 6 mm engagement in the plate and 26 mm engagement in the mast. The upper machined plate profile is 14.10 mm across flats for the nominal 13.80 mm head. The small clearance before lateral contact must remain in the motion and strength assessment.

The AMCO 3170300001 tube catalog gives 3.366 kg per 6 m length. Four 629.2 mm cuts account for 1.412 kg before finish machining. The rod stock is Würth 0959 008, M8 × 1 m, DIN 976-1 Form A, class 8.8. The soft bumper stiffness, CG offset and 68 kg gross robot mass used in the study remain design assumptions.

## Load and release limits

The twelve simulated conditions include changed stiffness, a forward CG, one missed hook, lower screw friction, early power loss and a halved integration step. The most demanding modeled single-side foot tension is 1,913.7 N. Twice this reaction plus 750 N assumed tie preload gives 4,577.5 N. The calculated M8 stress is 125.1 MPa at the 36.6 mm² tensile area. Elastic extension from zero load is 0.427 mm over the conservative 683.5 mm span.

The most demanding compressive case gives 3,465.3 N with the same amplification and preload. For a received wall of at least 2.85 mm, outer width of at least 19.90 mm and outer corner radius up to 2 mm, an ideal elastic column with effective-length factor 2 gives 4,011 N. Eccentricity, end fixity and actual preload affect this result. The planar solver does not resolve the yaw motion after one hook loses contact.

Before issuing a climb rating, check installed mass and CG, rod extension and preload, nut retention, lateral pilot bearing, mast buckling and the load path through the drive head. The current head study still has an undrilled reducer at the bottom of the lead-screw envelope. A parked bearing-housing comparison alone cannot establish powered lift or unpowered holding.

The seated flange area measures 94.844 mm² on each of the four machined upper plates. The independently removable bumper panels, battery service cart and four supplier module sweeps clear the tied assembly. The two rear modules have the smallest clearance at 6.55 mm across the supplier solids and installation gauges. [Seat and thread measurements](../../experiments/tower-climb/mast-attachment/low-head-fit.json) · [Supplier fit](../../experiments/tower-climb/mast-attachment/supplier-fit.json) · [Service paths](../../experiments/tower-climb/mast-attachment/service-fit.json)

When both screws hold at the original 100 mm stroke, all four carriage sleeves clear their mast by 0.50 mm. Allowing the carriage to roll freely about one held nut, the first modeled intrusion exceeds 0.005 mm³ when the opposite screw slips 8.465–8.466 mm. At 12 mm all four sleeves intersect their masts. A unilateral brake failure therefore needs an independent stop or synchronization mechanism whose complete response fits the available travel. The 8.465 mm result is a geometry measurement on an ideal carriage. [Differential displacement trial](../../experiments/tower-climb/mast-attachment/differential-guide-fit.json) · [Head and brake comparisons](../../experiments/tower-climb/head-support/study.md)

Run `mast_tie_load.py` for the load cases. The project scripts `mast_tie_fit.py`, `mast_service.py`, `mast_supplier_fit.py` and `mast_travel.py` separately check installed bodies, shop access, supplier wheel sweeps and lift travel. This comparison remains a prebuild candidate pending its whole-robot Fusion reopen.
