"""Shared R3 dimensions: the one source for the placed solids (geometry.py) and the physics trials (field_trials.py).

Robot frame: origin on the carpet at the frame centre, +X forward (intake), +Y left, +Z up, millimetres.
Every value is a preliminary allocation. This module imports nothing but math, so the trials run without the
CAD kernel. A trial variant may change one of these values to bracket it; the layout draws the nominal value.
"""
import math

R_BALL = 150.114 / 2
GAP = 3.0            # undeformed reserve between a FUEL and a surface that does not drive it
HALF_W = 357.0       # frame half-width in Y: a 714 mm wide, 680 mm long frame (2788 mm perimeter of 2794)
DY = HALF_W - 340.0  # outboard shift of every side feature relative to the 680 mm square foundation
FLYWHEEL_R = 50.8    # 4 in flywheel
EXIT_DEG = 62        # release elevation from the hood end
TRACK_Y = 82.5       # lane of the tracked FUEL
VARIANTS = {
    # floor: top of the hopper floor pan; wall: hopper wall top; hook: hook arm top (stowed)
    "R3": dict(floor=100.0, wall=715.0, hook=750.0, label="Tall floor-fed robot (selected)"),
    "R3L": dict(floor=32.0, wall=530.0, hook=534.0, label="Low trench-runner comparison"),
}

BUMPER = dict(x0=341.5, x1=417.5, z0=48.0, z1=168.0)          # front bumper section in the side view
FRONT_RAIL = dict(x0=314.6, x1=340.0, z0=69.85, z1=120.65)
# The hopper has no front lip. The floor belt runs to the front rail; the rail top, the back of the front bumper above
# it and, above the bumper top, the back plate of the deployed intake close the channel. A FUEL at the front of the
# floor therefore stands on the driven belt, and the 31 mm of bumper top behind the back plate is too shallow to rest on.
FLOOR_BELT_FRONT = dict(x0=177.5, x1=300.0)
FLOOR_BELT_MAIN = dict(x0=-15.0, x1=174.0)                     # ends ahead of the staged FUEL, which stands on the lane deck alone
LANE_DECK = dict(x0=-141.0, x1=-16.5, t=3.0)                  # fixed deck under the feeders and the flywheel, flush with the belt top
FLOOR_BELT_MPS = 1.2                                          # floor belt surface speed toward the flywheel
FLOOR_PAN = dict(x0=-176.0, x1=176.0)                         # floor pan under the main belt
FLOOR_TONGUE = dict(x0=177.5, x1=312.0)                       # front tongue of the floor pan, between the front modules
HANG_MASS_KG = 70.3                                           # hang trial mass: at or above the running mass upper bound

# Shooter pinch. The hood is concentric with the flywheel and tangent to the floor belt top, and the gap between
# wheel and hood is the FUEL diameter less this squeeze. The flywheel runs at speed whenever the robot holds FUEL;
# the feeder rollers ahead of it are the hold-back and the meter (FEEDER below).
# inertia_kgm2: the contact roller plus two outboard inertia rings on the same shaft (flywheel_build() rebuilds it
# from FLYWHEEL_PARTS and must agree). wheel_surface_mps: the speed setpoint. ready_band: a feeder advances a FUEL
# only while the measured wheel speed is within this fraction of the setpoint. motors, gear, stator_a, supply_a: two
# brushless motors, one on each shaft end, direct, with these per-motor current limits.
SHOOTER = dict(squeeze=12.0, wheel_surface_mps=13.6, hood_end_past_release_deg=-2.5, hood_start_deg=-88.0,
               inertia_kgm2=0.0076, motors=2, gear=1.0, stator_a=40.0, supply_a=30.0, ready_band=0.01)

# Flywheel build, for the mass line and the inertia: an aluminum tube roller with a compliant tread, and one steel
# ring on an aluminum web outboard of the right side plate on the same shaft. A ring carries its mass at about twice
# the roller radius squared, so it buys inertia at half the roller weight. One ring is enough: the batch
# trial holds the scoring band with 0.006 kg m2 and this build gives 0.0076. The ring stays 10 mm clear of the right
# feeder shaft, which passes outboard of it.
# rings: how many. ring: outer radius, inner radius, thickness (mm), steel. web: 3 mm aluminum disc to the ring inner
# radius. roller: tube outer radius under the tread, wall, length (mm), aluminum; tread mass and mean radius.
# ring_y: the span of the ring in Y (right side).
FLYWHEEL_PARTS = dict(rings=1, ring=dict(ro=80.0, ri=60.0, t=14.0, density=7.85e-6), web=dict(t=3.0, density=2.70e-6),
                      roller=dict(ro=FLYWHEEL_R - 6.0, wall=3.2, length=340.0, density=2.70e-6, tread_kg=0.45, tread_r=FLYWHEEL_R - 3.0),
                      hub_kg=0.25, ring_y=(-197.0, -183.0))

# Feeder: one compliant roller per lane ahead of the flywheel, pressing a FUEL into the floor belt, each with its own
# small gearmotor so the two lanes feed the one flywheel in turn.
# Under each roller the lane floor is the fixed deck, not the belt. Stopped and braked, a roller is the hold-back: a
# staged FUEL is clamped between two surfaces that do not move, clear of the spinning wheel, whatever the belt behind
# it does. Turning, the roller rolls the FUEL along the deck at half its surface speed and into the wheel.
# x: roller axis; r: roller radius; squeeze: the roller underside stands this far inside one FUEL diameter above the
# deck; mps: roller surface speed for a feed; stage_mps: surface speed while drawing a FUEL in to the stage beam;
# sensor_x: the stage beam, crossed by the FUEL centre; period_s: least time between feeds into the one flywheel
# (one FUEL pitch of travel at half the feed surface speed); lane_y: each roller's span in |Y|. The two rollers meet at
# the centre line, so a FUEL that arrives between the lanes is still under a roller.
FEEDER = dict(x=-60.0, r=25.4, squeeze=14.0, mps=1.2, stage_mps=0.6, sensor_x=-56.0, period_s=0.25, lane_y=(1.5, 165.0))
REAR_WALL_X = (-96.0, -93.0)                                  # hopper rear wall, behind the feeder rollers, which stand in the hopper

# Intake in the deployed (installed STEP) pose: a chute on a sliding carriage. A vertical belt pinches the FUEL against
# the front bumper face and then against the back plate of the carriage, which continues the bumper face plane upward,
# and lifts it to the top of the back plate; a top roller throws it aft over that edge into the hopper, above the
# stored FUEL. The back plate is the front wall of the hopper while the intake is deployed. A two-stage slide
# translates the whole carriage; stowed, it stands inside the frame in the front half of the hopper.
# pinch_squeeze: the belt back run stands this far inside one FUEL diameter from the bumper face and the back plate.
# pulley_squeeze: the bottom pulley underside stands this far below the top of a FUEL resting on the carpet.
# roller_drop: the top roller is lowered this far into the path of a FUEL at the top of the climb.
# back_top: top edge of the back plate. back_z0: its lower edge, clear of the bumper top. back_foot: the plate is a
# wedge, its hopper-side face standing this far aft of the bumper face at the lower edge, so a FUEL on the bumper top
# behind it has its centre aft of the front lip and rolls into the hopper. belt_top and climb_top keep the relation
# to the edge the FUEL is pushed over that the earlier issue had to the bumper top.
# roller_ratio: top roller surface speed over belt speed (the roller is belted to the belt drive at this ratio).
BACK_TOP = 425.0
INTAKE = dict(shift=(250.0, 0.0, -95.0), half_width=244.0, plate_y=(250.0, 260.0), plate_z=(190.0, 570.0), plate_x0=372.0, rail_y=(262.0, 270.0),
              pinch_squeeze=20.0, pulley_squeeze=20.0, roller_drop=20.0, pulley_r=18.5, back_top=BACK_TOP, back_z0=172.0, back_foot=45.0,
              back_t=3.0, belt_top=BACK_TOP + 132.0, climb_top=BACK_TOP + 102.0, roller_r=38.1, belt_mps=3.0, roller_ratio=2.0,
              # Belt drive: one brushless motor through gear:1 to the bottom pulley shaft, the top roller belted to it.
              # moving_kg: belt, pulleys, roller and rotor as an equivalent mass at the belt surface.
              gear=2.0, stator_a=40.0, supply_a=30.0, moving_kg=2.2,
              # nudge: in an unjam cycle the slide draws the carriage back this far (mm) along its travel and returns it in
              # this time (s), so the back plate pushes into the FUEL at the front of the hopper and breaks an arch there.
              nudge=(40.0, 0.3))


def frame_constants(variant="R3", squeeze=None):
    v = VARIANTS[variant]
    squeeze = SHOOTER["squeeze"] if squeeze is None else squeeze
    belt_top = v["floor"] + 9.0
    z0 = belt_top + GAP + R_BALL                       # stored lower-layer FUEL centre, drawn with the reserve
    hood_in = FLYWHEEL_R + 2 * R_BALL - squeeze        # hood inner radius about the flywheel axis
    c = (-150.0, belt_top + hood_in)                   # flywheel axis (X, Z): the hood bottom meets the belt top
    rc = FLYWHEEL_R + R_BALL - squeeze / 2             # FUEL centre radius while it is squeezed in the wrap
    exit_alpha = -(90 + 90 - (90 - EXIT_DEG))          # -152 deg for a 62 deg release
    ea = math.radians(exit_alpha)
    exit_point = (c[0] + rc * math.cos(ea), c[1] + rc * math.sin(ea))
    feeder = (FEEDER["x"], belt_top + 2 * R_BALL - FEEDER["squeeze"] + FEEDER["r"])   # feeder roller axis (X, Z)
    return dict(v, belt_top=belt_top, z0=z0, rc=rc, c=c, hood_in=hood_in, hood_out=hood_in + 4, squeeze=squeeze, feeder=feeder,
                exit_alpha=exit_alpha, exit_point=exit_point, pitch=2 * R_BALL + 4,
                hood_span_deg=(exit_alpha - SHOOTER["hood_end_past_release_deg"], SHOOTER["hood_start_deg"]))


def intake_points(pinch_squeeze=None, pulley_squeeze=None, roller_drop=None):
    """Side-view intake datums in the deployed pose (mm)."""
    i = INTAKE
    pinch = i["pinch_squeeze"] if pinch_squeeze is None else pinch_squeeze
    pulley = i["pulley_squeeze"] if pulley_squeeze is None else pulley_squeeze
    drop = i["roller_drop"] if roller_drop is None else roller_drop
    rp = i["pulley_r"]
    belt_x = BUMPER["x1"] + 2 * R_BALL - pinch         # belt back run, facing the bumper
    pulley_x = belt_x + rp
    bottom_z = 2 * R_BALL - pulley + rp                # bottom pulley centre
    top_z = i["belt_top"] - rp                         # top pulley centre
    ball_x = BUMPER["x1"] + GAP + R_BALL               # nominal roller station above the bumper face
    roller = (ball_x, i["climb_top"] + R_BALL + GAP + i["roller_r"] - drop)
    return dict(belt_x=belt_x, pulley_x=pulley_x, bottom_z=bottom_z, top_z=top_z, pulley_r=rp, roller=roller,
                roller_r=i["roller_r"], front_x=pulley_x + rp)


def flywheel_build():
    """Mass (kg) and inertia (kg m2) of the flywheel as built from FLYWHEEL_PARTS: roller tube, tread, the ring on its web, hubs."""
    p = FLYWHEEL_PARTS
    g, o, wb = p["ring"], p["roller"], p["web"]
    ring_kg = math.pi * (g["ro"] ** 2 - g["ri"] ** 2) * g["t"] * g["density"]
    ring_i = 0.5 * ring_kg * (g["ro"] ** 2 + g["ri"] ** 2) * 1e-6
    web_kg = math.pi * g["ri"] ** 2 * wb["t"] * wb["density"]
    web_i = 0.5 * web_kg * g["ri"] ** 2 * 1e-6
    tube_kg = math.pi * (o["ro"] ** 2 - (o["ro"] - o["wall"]) ** 2) * o["length"] * o["density"]
    tube_i = 0.5 * tube_kg * (o["ro"] ** 2 + (o["ro"] - o["wall"]) ** 2) * 1e-6
    tread_i = o["tread_kg"] * o["tread_r"] ** 2 * 1e-6
    hub_i = 0.5 * p["hub_kg"] * 25.0 ** 2 * 1e-6
    return dict(ringKg=ring_kg, webKg=web_kg, tubeKg=tube_kg, treadKg=o["tread_kg"], hubKg=p["hub_kg"],
                kg=p["rings"] * (ring_kg + web_kg) + tube_kg + o["tread_kg"] + p["hub_kg"],
                inertia=p["rings"] * (ring_i + web_i) + tube_i + tread_i + hub_i, ringsInertia=p["rings"] * (ring_i + web_i))


assert abs(flywheel_build()["inertia"] - SHOOTER["inertia_kgm2"]) < 2e-4, flywheel_build()


# Hopper (R3). The floor is a channel two lanes wide (lane_half) for its whole length, with the floor belt in it and
# the feeder rollers standing in it ahead of the rear wall. Aft of front_x a shelf slopes up from each channel wall
# (shelf_z at its inboard edge, shelf_deg) to the side wall; the battery stands under the left shelf and the
# electronics under the right. The right shelf and its pocket start at shelf_x0_right, ahead of the inertia ring of
# the flywheel. Ahead of front_x a low shelf (front_shelf_z rising front_rise to the cheek wall at cheek_y) passes
# under the stowed intake carriage and under the straight path it deploys along; the cheeks stand inboard of the
# front module motors. The front is closed by the fixed lip and, above it, by the back plate of the
# deployed intake; FUEL come in over the back plate. A full-height lane divider gives FUEL an edge to perch on and
# stalls the batch trial, so there is none.
HOPPER = dict(lane_half=168.0, floor="trough", shelf_z=270.0, shelf_deg=30.0, front_x=118.0, shelf_x0_right=-40.0, front_shelf_z=140.0,
              front_rise=36.0, cheek_y=246.0, divider=None)
BATTERY_BOX = ((-90.0, 236.0 + DY, 102.0), (77.0, 312.0 + DY, 283.0))
PANEL_RIGHT = ((-36.0, -312.0 - DY, 102.0), (115.0, -282.0 - DY, 282.0))
