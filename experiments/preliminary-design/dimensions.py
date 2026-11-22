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
FRONT_LIP = dict(x0=311.0, x1=313.0, z0=123.0, z1=170.0)
FLOOR_BELT_FRONT = dict(x0=177.5, x1=300.0)
FLOOR_BELT_MAIN = dict(x0=-30.0, x1=174.0)                    # ends under the feeder rollers' entry; the lane deck carries on
LANE_DECK = dict(x0=-143.0, x1=-31.5, t=3.0)                  # fixed deck under the feeders and the flywheel, flush with the belt top
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
SHOOTER = dict(squeeze=12.0, wheel_surface_mps=13.4, hood_end_past_release_deg=-2.5, hood_start_deg=-88.0,
               inertia_kgm2=0.0176, motors=2, gear=1.0, stator_a=40.0, supply_a=30.0, ready_band=0.01)

# Flywheel build, for the mass line and the inertia: an aluminum tube roller with a compliant tread, and one steel
# ring on an aluminum web outboard of each side plate on the same shaft. A ring carries its mass at about 3.5 times
# the roller radius squared, so it buys inertia at a third of the roller's weight.
# ring: outer radius, inner radius, thickness (mm), steel. web: 3 mm aluminum disc to the ring's inner radius.
# roller: tube outer radius under the tread, wall, length (mm), aluminum; tread mass and mean radius.
FLYWHEEL_PARTS = dict(ring=dict(ro=105.0, ri=85.0, t=8.0, density=7.85e-6), web=dict(t=3.0, density=2.70e-6),
                      roller=dict(ro=FLYWHEEL_R - 6.0, wall=3.2, length=340.0, density=2.70e-6, tread_kg=0.45, tread_r=FLYWHEEL_R - 3.0),
                      hub_kg=0.25, ring_y=(183.0, 191.0))

# Feeder: one compliant roller per lane ahead of the flywheel, pressing a FUEL into the floor belt, each with its own
# small gearmotor so the two lanes feed the one flywheel in turn.
# Under each roller the lane floor is the fixed deck, not the belt. Stopped and braked, a roller is the hold-back: a
# staged FUEL is clamped between two surfaces that do not move, clear of the spinning wheel, whatever the belt behind
# it does. Turning, the roller rolls the FUEL along the deck at half its surface speed and into the wheel.
# x: roller axis; r: roller radius; squeeze: the roller underside stands this far inside one FUEL diameter above the
# deck; mps: roller surface speed for a feed; stage_mps: surface speed while drawing a FUEL in to the stage beam;
# sensor_x: the stage beam, crossed by the FUEL centre; period_s: least time between feeds into the one flywheel
# (one FUEL pitch of travel at half the feed surface speed); lane_y: each roller's span in |Y|.
FEEDER = dict(x=-60.0, r=25.4, squeeze=8.0, mps=1.2, stage_mps=0.6, sensor_x=-58.0, period_s=0.25, lane_y=(8.0, 165.0))
REAR_WALL_X = (-96.0, -93.0)                                  # hopper rear wall, behind the feeder rollers, which stand in the hopper

# Intake in the deployed (installed STEP) pose. A vertical belt pinches the FUEL against the front bumper face and
# lifts it; a top roller pushes it aft over the bumper. A two-stage slide translates the whole carriage.
# pinch_squeeze: the belt back run stands this far inside one FUEL diameter from the bumper face.
# pulley_squeeze: the bottom pulley underside stands this far below the top of a FUEL resting on the carpet.
# roller_drop: the top roller is lowered this far into the path of a FUEL at the top of the climb.
INTAKE = dict(shift=(280.0, 0.0, -90.0), half_width=258.0, plate_y=(262.0, 272.0), plate_z=(290.0, 385.0), rail_y=(274.0, 282.0),
              pinch_squeeze=20.0, pulley_squeeze=20.0, roller_drop=20.0, pulley_r=18.5, belt_top=300.0,
              climb_top=270.0, roller_r=38.1, belt_mps=3.0,
              # Belt drive: one brushless motor through gear:1 to the bottom pulley shaft, the top roller belted to it.
              # moving_kg: belt, pulleys, roller and rotor as an equivalent mass at the belt surface.
              gear=2.0, stator_a=40.0, supply_a=30.0, moving_kg=1.5)


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
    """Mass (kg) and inertia (kg m2) of the flywheel as built from FLYWHEEL_PARTS: roller tube, tread, two rings on webs, hubs."""
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
                kg=2 * (ring_kg + web_kg) + tube_kg + o["tread_kg"] + p["hub_kg"],
                inertia=2 * (ring_i + web_i) + tube_i + tread_i + hub_i, ringsInertia=2 * (ring_i + web_i))


assert abs(flywheel_build()["inertia"] - SHOOTER["inertia_kgm2"]) < 2e-4, flywheel_build()


# Hopper floor plan (R3). lane_half: half-width of the two-lane mouth under the rear wall. guides: full-height vertical
# plates that turn the belt-driven floor layer in to that mouth, left then right, each from its outboard end (x, y) to
# the mouth edge at the rear wall. The battery stands ahead of the rear wall so it still lifts straight out.
# divider: half-thickness and forward end of the plate that splits the mouth into the two lanes.
# floor: "trough" keeps the floor two lanes wide for its whole length under sloped shelves; shelf_z, shelf_deg: the
# shelf's inboard edge height and its rise to the side wall.
HOPPER = dict(lane_half=168.0, floor="trough", shelf_z=270.0, shelf_deg=30.0, divider=dict(half_t=1.5, x1=309.0), guides=(((62.0, 250.0), (REAR_WALL_X[1], 168.0)), ((120.0, -297.0), (REAR_WALL_X[1], -168.0))))
BATTERY_BOX = ((-25.0, 236.0 + DY, 102.0), (142.0, 312.0 + DY, 283.0))
PANEL_RIGHT = ((-90.0, -312.0 - DY, 102.0), (170.0, -282.0 - DY, 282.0))
