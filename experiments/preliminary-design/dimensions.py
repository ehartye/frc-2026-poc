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
FLOOR_BELT_MAIN = dict(x0=-140.0, x1=174.0)
FLOOR_BELT_MPS = 0.6                                          # floor belt surface speed toward the flywheel
FLOOR_PAN = dict(x0=-176.0, x1=176.0)                         # floor pan under the main belt
FLOOR_TONGUE = dict(x0=177.5, x1=312.0)                       # front tongue of the floor pan, between the front modules
HANG_MASS_KG = 70.3                                           # hang trial mass: at or above the running mass upper bound

# Shooter pinch. The hood is concentric with the flywheel and tangent to the floor belt top, and the gap between
# wheel and hood is the FUEL diameter less this squeeze. The squeeze makes a stopped wheel the FUEL's stop and a
# spinning wheel its drive; launch trials bracket it.
# spin_up_s: a linear ramp of the 0.006 kg m2 wheel (209 J) peaks at 2 x 209 J / spin_up_s. At 1.25 s that is 334 W,
# 47 A at the 8.34 V weak-pack launch bus with 85% drive efficiency, inside the launch duty's 60 A flywheel bound.
SHOOTER = dict(squeeze=12.0, wheel_surface_mps=13.4, hood_end_past_release_deg=-2.5, hood_start_deg=-88.0, spin_up_s=1.25,
               inertia_kgm2=0.006)

# Intake in the deployed (installed STEP) pose. A vertical belt pinches the FUEL against the front bumper face and
# lifts it; a top roller pushes it aft over the bumper. A two-stage slide translates the whole carriage.
# pinch_squeeze: the belt back run stands this far inside one FUEL diameter from the bumper face.
# pulley_squeeze: the bottom pulley underside stands this far below the top of a FUEL resting on the carpet.
# roller_drop: the top roller is lowered this far into the path of a FUEL at the top of the climb.
INTAKE = dict(shift=(280.0, 0.0, -90.0), half_width=258.0, plate_y=(262.0, 272.0), plate_z=(290.0, 385.0), rail_y=(274.0, 282.0),
              pinch_squeeze=20.0, pulley_squeeze=20.0, roller_drop=20.0, pulley_r=18.5, belt_top=300.0,
              climb_top=270.0, roller_r=38.1, belt_mps=3.0)


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
    return dict(v, belt_top=belt_top, z0=z0, rc=rc, c=c, hood_in=hood_in, hood_out=hood_in + 4, squeeze=squeeze,
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
