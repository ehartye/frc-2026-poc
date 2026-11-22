"""Labeled representative solids for the R3 preliminary package, in the robot STEP frame.

Robot frame: origin on the carpet at the frame center, +X forward (intake), +Y left, +Z up, millimetres.
Every dimension below is a preliminary allocation, not a fabrication dimension. Variant "R3" is the
selected tall floor-fed robot. Variant "R3L" lowers the same arrangement under the TRENCH for the
capacity comparison only.
"""
import math

from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon, BRepBuilderAPI_Transform
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism, BRepPrimAPI_MakeSphere
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.gp import gp_Ax1, gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec

R_BALL = 150.114 / 2
GAP = 3.0            # undeformed reserve between a moving FUEL and the surfaces that guide it
FLYWHEEL_R = 50.8    # 4 in flywheel
EXIT_DEG = 60        # release elevation from the hood end
INTAKE_STOW_DEG = 135
VARIANTS = {
    # floor: top of the hopper floor pan; wall: hopper wall top; hook: hook arm top (stowed)
    "R3": dict(floor=81.0, wall=715.0, hook=750.0, label="Tall floor-fed robot (selected)"),
    "R3L": dict(floor=32.0, wall=530.0, hook=534.0, label="Low trench-runner comparison"),
}


def single(shape):
    it = TopExp_Explorer(shape, TopAbs_SOLID)
    solids = []
    while it.More():
        solids.append(it.Current()); it.Next()
    assert len(solids) == 1, "expected one solid"
    return solids[0]


def box(lo, hi):
    return BRepPrimAPI_MakeBox(gp_Pnt(*lo), gp_Pnt(*hi)).Shape()


def cyl(base, axis, r, h, xdir=None, angle=None):
    ax = gp_Ax2(gp_Pnt(*base), gp_Dir(*axis)) if xdir is None else gp_Ax2(gp_Pnt(*base), gp_Dir(*axis), gp_Dir(*xdir))
    return (BRepPrimAPI_MakeCylinder(ax, r, h) if angle is None else BRepPrimAPI_MakeCylinder(ax, r, h, angle)).Shape()


def sphere(c, r=R_BALL):
    return BRepPrimAPI_MakeSphere(gp_Pnt(*c), r).Shape()


def cut(a, b):
    return single(BRepAlgoAPI_Cut(a, b).Shape())


def fuse(*shapes):
    out = shapes[0]
    for s in shapes[1:]:
        out = BRepAlgoAPI_Fuse(out, s).Shape()
    return single(out)


def prism_xz(points, y0, y1):
    """Closed polygon in the XZ plane extruded from y0 to y1."""
    poly = BRepBuilderAPI_MakePolygon()
    for x, z in points:
        poly.Add(gp_Pnt(x, y0, z))
    poly.Close()
    face = BRepBuilderAPI_MakeFace(poly.Wire()).Face()
    return BRepPrimAPI_MakePrism(face, gp_Vec(0, y1 - y0, 0)).Shape()


def hexagon_prism(cx, cy, circumradius, z0, z1):
    poly = BRepBuilderAPI_MakePolygon()
    for k in range(6):  # corners on +/-Y, flats facing +/-X
        a = math.radians(90 + 60 * k)
        poly.Add(gp_Pnt(cx + circumradius * math.cos(a), cy + circumradius * math.sin(a), z0))
    poly.Close()
    face = BRepBuilderAPI_MakeFace(poly.Wire()).Face()
    return BRepPrimAPI_MakePrism(face, gp_Vec(0, 0, z1 - z0)).Shape()


def bar_xz(p, q, half, y0, y1):
    """Straight plate between two XZ points with a given half-width, extruded in Y."""
    dx, dz = q[0] - p[0], q[1] - p[1]
    n = math.hypot(dx, dz)
    ox, oz = -dz / n * half, dx / n * half
    ex, ez = dx / n * half, dz / n * half
    return prism_xz([(p[0] + ox - ex, p[1] + oz - ez), (q[0] + ox + ex, q[1] + oz + ez),
                     (q[0] - ox + ex, q[1] - oz + ez), (p[0] - ox - ex, p[1] - oz - ez)], y0, y1)


def rotate(shape, origin, axis, deg):
    t = gp_Trsf(); t.SetRotation(gp_Ax1(gp_Pnt(*origin), gp_Dir(*axis)), math.radians(deg))
    return BRepBuilderAPI_Transform(shape, t, True).Shape()


def frame_constants(variant):
    v = VARIANTS[variant]
    belt_top = v["floor"] + 9.0
    z0 = belt_top + GAP + R_BALL                       # lower-layer FUEL center on the floor belts
    rc = FLYWHEEL_R + R_BALL + GAP                     # FUEL center radius around the flywheel axis
    c = (-150.0, z0 + rc)                              # flywheel axis (X, Z); the FUEL enters directly below it
    hood_in = FLYWHEEL_R + 2 * R_BALL + 2 * GAP
    a = math.radians(-90 - EXIT_DEG - 0.0)
    exit_alpha = -(90 + 90 - (90 - EXIT_DEG))          # -150 deg for a 60 deg release
    ea = math.radians(exit_alpha)
    exit_point = (c[0] + rc * math.cos(ea), c[1] + rc * math.sin(ea))
    return dict(v, belt_top=belt_top, z0=z0, rc=rc, c=c, hood_in=hood_in, hood_out=hood_in + 4,
                exit_alpha=exit_alpha, exit_point=exit_point, pitch=2 * R_BALL + 4)


# Intake geometry in the deployed (installed STEP) pose, in the XZ plane.
INTAKE = dict(pivot=(322.0, 296.0), ramp_front=(580.0, 20.0), ramp_back=(400.0, 200.0), roller_s=210.0,
              roller_r=38.1, half_width=258.0, arm_y=(262.0, 272.0))


def intake_points():
    f, b = INTAKE["ramp_front"], INTAKE["ramp_back"]
    length = math.dist(f, b)
    u = ((b[0] - f[0]) / length, (b[1] - f[1]) / length)
    n = (-u[1], u[0]) if -u[1] > 0 else (u[1], -u[0])       # upward-forward normal of the ramp's carrying face
    if n[1] < 0: n = (-n[0], -n[1])
    s = INTAKE["roller_s"]
    pt = (f[0] + s * u[0], f[1] + s * u[1])
    offset = R_BALL + GAP + R_BALL + GAP + INTAKE["roller_r"]
    centre_off = R_BALL + GAP
    roller = (pt[0] + (centre_off + R_BALL + GAP + INTAKE["roller_r"]) * n[0], pt[1] + (centre_off + R_BALL + GAP + INTAKE["roller_r"]) * n[1])
    return dict(u=u, n=n, length=length, roller=roller, centre_off=centre_off, offset=offset)


def robot_bodies(variant="R3", intake_stowed=False):
    """Return {name: (shape, group)} for one variant in its installed pose."""
    k = frame_constants(variant)
    fl, wall, hook_top = k["floor"], k["wall"], k["hook"]
    B = {}

    def add(name, shape, group):
        B[name] = (single(shape), group)

    # Frame rails (2 x 1 in tube allocation) split so that bounding-box culling works.
    add("frame rail front", box((314.6, -338, 69.85), (340, 338, 120.65)), "frame")
    add("frame rail rear", box((-340, -338, 69.85), (-314.6, 338, 120.65)), "frame")
    add("frame rail left", box((-313, 314.6, 69.85), (313, 340, 120.65)), "frame")
    add("frame rail right", box((-313, -340, 69.85), (313, -314.6, 120.65)), "frame")
    add("floor pan", box((-176, -313, fl - 6), (176, 313, fl)), "frame")
    add("floor pan front tongue", box((177.5, -183, fl - 6), (312, 183, fl)), "frame")
    add("front lip", box((311, -183, 123), (313, 183, 160)), "frame")
    for side, s in (("left", 1), ("right", -1)):
        y = sorted((s * 274, s * 282))
        add(f"intake pivot mount {side}", box((313.5, y[0], 123), (336, y[1], 279)), "frame")

    # Swerve corners: revolved wheel azimuth envelope, module body and motor envelope.
    for fx, sx in (("front", 1), ("rear", -1)):
        for side, sy in (("left", 1), ("right", -1)):
            cx, cy = sx * 265, sy * 265
            add(f"{fx} {side} wheel azimuth envelope", cyl((cx, cy, 0), (0, 0, 1), 40.3, 76.2), "drivetrain")
            x = sorted((sx * 185, sx * 312)); y = sorted((sy * 185, sy * 312))
            add(f"{fx} {side} module body", box((x[0], y[0], 80), (x[1], y[1], 125)), "drivetrain")
            add(f"{fx} {side} module motors", cyl((cx, cy, 127), (0, 0, 1), 32, 88), "drivetrain")

    # Bumpers in the bumper zone used by the foundation.
    add("bumper front", box((341.5, -416, 48), (417.5, 416, 168)), "bumpers")
    add("bumper rear", box((-417.5, -416, 48), (-341.5, 416, 168)), "bumpers")
    add("bumper left", box((-340, 341.5, 48), (340, 417.5, 168)), "bumpers")
    add("bumper right", box((-340, -417.5, 48), (340, -341.5, 168)), "bumpers")

    # Hopper walls.
    add("hopper wall left", box((-312, 316, 125), (312, 319, wall)), "hopper")
    add("hopper wall right", box((-312, -319, 125), (312, -316, wall)), "hopper")
    add("hopper rear wall", box((-96, -314, k["z0"] + R_BALL + 7), (-93, 314, wall)), "hopper")

    # Floor belts: static envelopes of moving belt surfaces.
    add("floor belt main", box((-140, -279, fl + 1.5), (174, 231, k["belt_top"])), "floor belts")
    add("floor belt front", box((177.5, -180, fl + 1.5), (300, 180, k["belt_top"])), "floor belts")

    # Shooter: floor-fed flywheel, hood sector, side plates and motor.
    cx, cz = k["c"]
    add("flywheel", cyl((cx, -170, cz), (0, 1, 0), FLYWHEEL_R, 340), "shooter")
    a0 = math.radians(-152)
    xdir = (math.cos(a0), 0, math.sin(a0))
    span = math.radians(64)  # -152 to -88 degrees
    outer = cyl((cx, 170, cz), (0, -1, 0), k["hood_out"], 340, xdir, span)
    inner = cyl((cx, 171, cz), (0, -1, 0), k["hood_in"], 342)
    add("hood", cut(outer, inner), "shooter")
    for side, s in (("left", 1), ("right", -1)):
        y = sorted((s * 173, s * 181))
        add(f"shooter side plate {side}", box((-338, y[0], 125), (-100, y[1], cz + 125)), "shooter")
    add("flywheel motor", cyl((cx, -184, cz), (0, -1, 0), 30, 79), "shooter")

    # Battery on its end, left side, withdrawn upward through the open hopper.
    add("battery", box((-90, 236, fl + 2), (77, 312, fl + 2 + 181)), "battery")
    add("electronics panel", box((-90, -312, fl + 2), (150, -282, fl + 182)), "electrical")
    add("entry sensor", box((300, -183, 123), (309, -175, 140)), "electrical")
    add("pinch sensor", box((-160, 182.5, cz - 45), (-140, 190, cz - 25)), "electrical")

    # Climber: fixed round outer tubes, round telescoping inner tubes and swing hooks (stowed pointing aft).
    for side, s in (("left", 1), ("right", -1)):
        yc = s * 299
        tube_top = hook_top - 116  # below the hook arm at the end of the 29.6 mm seat and 70 mm lift strokes
        add(f"climber tube {side}", cut(cyl((300, yc, 224), (0, 0, 1), 15, tube_top - 224), cyl((300, yc, 223), (0, 0, 1), 13, tube_top - 222)), "climber tubes")
        add(f"climber inner tube {side}", cyl((300, yc, 330 if variant == "R3" else 230), (0, 0, 1), 11, hook_top - 14 - (330 if variant == "R3" else 230)), "climber inner tubes")
        arm = box((87, yc - 11, hook_top - 12), (313, yc + 11, hook_top))
        jaw = box((87, yc - 11, hook_top - 40), (99, yc + 11, hook_top - 12))
        add(f"climber hook {side}", fuse(arm, jaw), "climber hooks")

    # Intake in its deployed pose.
    ip = intake_points()
    f, b = INTAKE["ramp_front"], INTAKE["ramp_back"]
    hw = INTAKE["half_width"]
    n = ip["n"]
    ramp = prism_xz([f, b, (b[0] - 4 * n[0], b[1] - 4 * n[1]), (f[0] - 4 * n[0], f[1] - 4 * n[1])], -hw, hw)
    pieces = {"intake ramp": ramp,
              "intake roller": cyl((ip["roller"][0], -hw, ip["roller"][1]), (0, 1, 0), INTAKE["roller_r"], 2 * hw)}
    p, r = INTAKE["pivot"], ip["roller"]
    for side, s in (("left", 1), ("right", -1)):
        y = sorted((s * INTAKE["arm_y"][0], s * INTAKE["arm_y"][1]))
        pieces[f"intake arm {side}"] = fuse(bar_xz(p, r, 12, y[0], y[1]), bar_xz(r, (566.0, 110.0), 12, y[0], y[1]))
    # The roller motor runs inside the roller tube; the deploy gearmotor is coaxial with the pivot and does not translate.
    add("intake pivot drive", cyl((p[0], 224, p[1]), (0, 1, 0), 24, 34), "intake pivot drive")
    for name, shape in pieces.items():
        if intake_stowed:
            shape = rotate(shape, (p[0], 0, p[1]), (0, -1, 0), INTAKE_STOW_DEG)
        add(name, shape, "intake")
    return B, k


def field_bodies(k, hub_center, tower_face_x, tower_y):
    """Field fixtures from the V0 description, placed in the robot frame for the first case."""
    hx, hy = hub_center
    F = {}
    half = 1193.8 / 2
    circ = 1059.18 / 2
    F["hub body"] = single(cut(box((hx - half, hy - half, 0), (hx + half, hy + half, 1777)),
                               hexagon_prism(hx, hy, circ, 1000, 1778)))
    F["hub top"] = single(cut(box((hx - half, hy - half, 1779), (hx + half, hy + half, 1828.8)),
                              hexagon_prism(hx, hy, circ, 1778, 1830)))
    gap = 819.15 / 2
    for side, s in (("left", 1), ("right", -1)):
        y = sorted((tower_y + s * gap, tower_y + s * (gap + 38.1)))
        F[f"tower upright {side}"] = single(box((tower_face_x, y[0], 0), (tower_face_x + 88.9, y[1], 1831.3)))
    rung_x = tower_face_x + 88.9 / 2
    F["tower low rung"] = single(cyl((rung_x, tower_y - gap + 1.6, 685.8), (0, 1, 0), 42.164 / 2, 2 * gap - 3.2))
    return F
