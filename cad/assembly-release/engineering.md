# Assembly engineering record

The student archive for R2C-T1 contains 159 editably extruded bodies and two tower sliders. Exact file and contact reviews exposed defects in the complete robot. All 159 bodies reopened with the native physical material “Steel.” Their raw CAD mass was 350.493 kg. The selected battery, drivetrain units, clear guards and bumper covers all require different treatment. The engineering review also found 116 original parts outside the existing tower rigid groups, seven isolated physical parts in the parked STEP, and interference between the intake roller and elevator structure. These observations invalidate any claim of a finished whole-robot mass or build release from the earlier screenshot.

## Drivetrain foundation

The new [shop traveler](foundation-shop.md) and [saddle drawing](foundation-saddle.svg) revise the chassis mounts. The collision check uses the original supplier STEP SHA-256 from the [selected part record](../own-zone/layout.json) at the four revised placements. Public student files contain independently drawn package geometry.

| Check | Original R2C-T1 or initial candidate | Revised foundation |
| --- | --- | --- |
| Saddle height | Original 33.18 mm span in a 50.80 mm gap | 50.80 mm nominal. Machine for the matched pair of real plate faces. |
| Module position from center | ±268 mm. The original upper tab intersects a frame crossmember and hopper post, and the conservative continuous-turn envelope enters the inner rail faces. | ±265 mm. All 72 purchased supplier leaves per module checked against the full parked robot. The analytic full-azimuth envelope clears. |
| Rail fastening and access | Pending mount. In the prototype saddle study the two rear inboard screw paths strike the original crossmember. | Sixteen M6 screws plus sixteen matched long screw/locknut pairs. The four completed-backplate frame corners pass 64 separate key, screw-withdrawal and vertical socket tests. |
| Bearing on module plates | No matched full-height support | Minimum 327.0 mm² per half-saddle on each supplier plate. With the actual cap screw, minimum 21.2394 mm² conservative under-head seat and 46.8411 mm² nut seat. |
| Crossmember support | On the intermediate flat-sided rail the top 7.20 mm of each crossmember extended above its rail. | Four backing plates support the complete 282.2575 mm² crossmember end section. The crossmember-to-plate and plate-to-rail contacts have zero nominal gap and zero common volume. |
| Reproduction | [Original tower archive and assumptions](../tower-lift) | [Supplier geometry checks](drivetrain_fit.py), [seat area measurement](tab_seats.py), [section checks](frame_bearing.py), [editable Fusion construction](fusion_foundation.py), [private purchased-parts relink](private_relink.py) |

The complete robot is still in engineering review. The earlier single-piece scoring replay and tower assessment preserve their original model revision. The source schema and cuts for the revised drivetrain use actual stock and hardware identifiers. Completed fit at this interface is separate from an as-built clamp load, measured mass, wiring test or full-robot acceptance.
