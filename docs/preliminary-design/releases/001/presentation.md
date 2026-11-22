# Present a preliminary design review

*Reference copy of the Agent FRC presentation contract (`skills/frc-preliminary-design/references/presentation.md`, agent-frc eda17621fb37, version 0.86.0). This release's viewer follows it; the plugin copy is authoritative.*

Give the reviewer an interactive whole-robot blockout and a decision they can inspect. Link the review from the project handoff. Put the selected concept, revision, robot datum, units and current disposition on the opening view. Use the project's Agent FRC presentation theme and [component palette](https://github.com/ehartye/agent-frc/blob/eda17621fb372544d40d4c9ad6cae6828904209d/docs/cad-color-convention.md).

Start with the [copyable full page layout, budget examples and project-local launcher](https://github.com/ehartye/agent-frc/blob/eda17621fb372544d40d4c9ad6cae6828904209d/skills/frc-preliminary-design/references/review-layout-template.md). Its page order puts the viewer first and the resource figures immediately below it.

## What the reviewer can do

Show the reviewed strategic narrative revision and the disposition of each match objective and fallback. Provide a component selector and direct surface picking. Display two separate, project-authored explanations for every placed ID: **Purpose** describes what it does, and **Why it is included** identifies the need or tradeoff that justifies this piece in this architecture. A service gauge, for example, can represent a socket and justify its volume by the required removal sequence. Keep missing explanations visible.

- Orbit through a full revolution and underneath the robot, pan in the view plane, zoom and reset to a fitted view. Provide pointer and keyboard controls and a visible control legend. Keep the camera where the reviewer puts it when scrubbing motion.
- Display depth-tested, closed solid volumes. Preserve cavities, holes, independent moving members and the finite game piece. Include fixed and moving neighbors, bumpers, service stock and withdrawal envelopes. Show/hide labels independently of geometry. Provide a textual category legend and component list.
- Put the floor at the registered ground elevation. Show units and a scale cue. Build visible game pieces and field fixtures from the selected official dimensions or field model, including openings, orientation and height. Preserve the field-to-robot transform during motion. Identify partial fixtures and distinguish nominal surfaces from conservative collision envelopes.
- Play, pause and scrub operating, loaded, disabled/park and service cases. Identify the pose or fraction, operating stage, simultaneously moving groups and independent piece path. Make a collision selectable by pair and case. Hidden components still count in validation and budgets.
- Select components by stable identity and assemble a named subsystem from any selection. Keep category (what an article is), subsystem (which function it serves) and motion group (what it moves with) separate. Preserve custom selections locally or in an export. A shared component appears once in the whole-robot total.

## Choose a representative solid

Use whatever shape captures the fit decision. A cylinder preserves a wheel radius, a sphere preserves ball contact, a torus preserves a central opening, and a swept profile follows a cable bend. Combine primitives or use boolean cuts to form fork gaps, hollow rails, offset housings and other compound shapes. Keep a mounting datum and motion axis. Compare extrema, material occupancy, useful voids and volume with a measured article or drawing. Record the deviation and the clearance it could consume. An equal-volume box can still block a passage or conceal a collision. Keep nominal solids, tolerance envelopes and service sweeps selectable separately. Recheck the changed solid over the same path.

## Review interface

Use the Agent FRC blue-and-gold interface with a large, expandable canvas. Keep functional category colors stable in the model, its legend and inventory. Picking a visible surface should identify the frontmost component and reveal its name, material, subsystem, volume and mass basis. Give reviewers a way to focus on an internal part and then restore the full assembly.

For the opening pose, show the real supports and the finite piece in its intended seat. Verify the pose before sharing it. If a coarse box appears to penetrate a piece, compare it with the shaped part in the same pose, retain the original control and check the whole path again. Mark unmounted allowances and unresolved supports. Do not move the piece to improve a picture.

Trace each moving load into the frame. For a driven wheel, identify the wheel, hub, axle or shaft, reacting bearings, carrier, mount and frame member. Trace the torque path from the motor case and output through any reducer, coupling, belt or chain. A datum axis locates the joint. Model the occupied axle, bearings and attachment separately wherever they constrain the piece, travel or service path. Model spring seats and positive stops on guided mechanisms. Use matched names for handed supports, retain the source IDs, and identify each unsupported or conceptual connection explicitly. Verify the opening pose with every proposed support present.

Render a cable corridor as a swept circular section on its actual centerline when the routing allowance is tubular. Include bend radii and distinguish the outside cable diameter from radial clearance.

## Inventory and budgets

For every component show its category color, role, source or estimate basis, preliminary material, installed quantity, occupied volume and estimated mass or range. Mark placeholders and missing allocations. Use STEP or a closed oriented mesh to measure volume. Distinguish physical material volume from a package envelope and the sum of envelope volumes from their geometric union. A clearance gauge adds no robot weight. Appearance alone cannot establish material or density.

Let reviewers group the inventory by category and by their own subsystem membership. Roll up unique mass lines and volumes. If a mass estimate covers several members and a selection splits that allocation, report the shared range separately until it is apportioned. Show the inspection basis, running configuration, excluded equipment, reserve and mass limits.

For each duty and battery condition, show the selected group's battery-side current range and contribution to voltage sag, alongside the whole-robot minimum bus voltage and its requirement. Components on the same parallel bus share voltage. Sum coincident currents, apply the pack model, and calculate branch drop separately if measured. When only independent current bounds exist, label the result a conservative bound. Expose combined loads that cannot be attributed to one category or subsystem. Never distribute them by volume, silently count missing loads as zero or sum nominal device voltages. [Shared electrical loads](https://github.com/ehartye/agent-frc/blob/eda17621fb372544d40d4c9ad6cae6828904209d/docs/shared-power-review.md)

Lead the weight ledger with the inspection limit, low/high estimate and signed headroom. Separate running additions. Lead the power ledger with selected duty, battery condition, minimum bus voltage, required voltage and margin. Put load bars in battery-side amperes and let the reviewer select a load to see its members. With a pack resistance model, report current and power available at the chosen voltage floor and identify the limiting duty. A pack sag budget alone cannot qualify a breaker, conductor or thermal limit.

Commission expected counts for the selected architecture, including its wheels, propulsion and steering actuators, control computer, power distribution, main disconnect, supply and communications. Compare expected IDs with the unfiltered placed roster. Display missing roles, counts, unallocated loads, voltage violations, overweight estimates and components awaiting a support or connection. Reviewers need to distinguish a missing representation from a missing physical design. Test a deliberately incomplete roster and a failing power case.

The local package player reads project-authored `presentation.components` keyed by placed ID (required `purpose` and `rationale`, optional `category` and `material`), `presentation.required` mapping roles to expected placed IDs, and `presentation.loadMembers` mapping each budget source name to its consuming IDs. Supply these from the architecture and component register. A grouping or camera change preserves the commissioned checks.

## Evidence behind the picture

Label imposed payload motion as prescribed. For a tipping holder, show the reviewer the loaded pose and a separate power-off escape control. Identify the first angle at which gravity points through an opening, the available resisting contacts, and the measured escape distance or obstruction. A collision-free carried path alone establishes clearance.

1. Bind the view to the reviewed geometry, motion definition and result by revision and digest. Check that every displayed mesh is closed, that the roster matches and that mesh volumes agree with source solids at a declared tolerance.
2. Check the parked assembly for positive-volume intersections. Account for all unique pairs, including broad-phase separations. Identify intended interfaces individually with allowed geometry and allowance. Keep unresolved measurements visible.
3. Check clearance throughout each prescribed path, including its endpoints, simultaneous motions, payload and withdrawal tools. Give the method, tolerance and interval coverage. Sampled poses alone establish clearance only at those samples.
4. List the limiting pair, clearance or overlap, and pose/time for each failure. Preserve a displaced control that the same check catches. A blocked or incomplete review still gets a view. Reopen the owning design phase before committing affected hardware. [Layout checker and decision](https://github.com/ehartye/agent-frc/blob/eda17621fb372544d40d4c9ad6cae6828904209d/docs/preliminary-design.md)

## Hand off a LAN review

Serve a dedicated directory containing only the review and its local assets. Bind the server to the selected LAN interface on an available port. Include the LAN URL, revision, launch/stop instructions and expected scope. Open the URL on the host, then on a second device when available. Verify reset, full orbit, pan, label toggle, playback, grouping and a known failed case. Preserve the static bundle for viewing after the host shuts down. Private CAD and unrelated workspace files stay outside the serving directory.

## Field interactions and physics playback

Make the selected architecture the opening view. Provide a named, playable case for each mission-critical interaction. Keep rejected concepts in the decision record. A failed duty holds or revises the selected design.

- **Build the interacting field area at scale.** Use project-owned official geometry or dimensioned drawings at the selected rules cutoff. Register floor, approach, contact surfaces, nearby obstructions, target and any rule-relevant sensors in the same datum as the robot. Record source, units, transform and dimensions. Identify each simplification and the outcome it could change.
- **Drive playback from the physical trial.** Commands may prescribe actuator inputs. Integrate the free payload or supported robot responses that decide the mission. For delivery, continue the same released article with its measured position, orientation and velocity through field contact and the applicable scoring observation. For elevation, resolve fixture compliance or its justified bounds, gravity, unilateral floor contact, actuator capacity, load transfer and the disabled hold through assessment.
- **Expose the evidence in the player.** Use timestamps from the run, allow scrubbing and show the interaction area, event and decision metric together. Link the exact layout, scenario, solver settings and trace. Replay a disabled or adverse control and check timestep or geometric sensitivity where it can change the decision. Report estimated contact properties, missing physical measurements and the first unmet condition. Mark any commanded illustration separately.
