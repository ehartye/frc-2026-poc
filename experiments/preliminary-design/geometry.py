"""Labeled representative solids for the R3 preliminary package, in the robot STEP frame.

Robot frame: origin on the carpet at the frame center, +X forward (intake), +Y left, +Z up, millimetres.
Every dimension is a preliminary allocation, not a fabrication dimension, and comes from dimensions.py, which the
physics trials read too. Variant "R3" is the selected tall floor-fed robot. Variant "R3L" lowers the same
arrangement under the TRENCH for the capacity comparison only.
"""
import math

from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon, BRepBuilderAPI_Transform
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism, BRepPrimAPI_MakeSphere
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec

from dimensions import (BUMPER, DY, EXIT_DEG, FLOOR_BELT_FRONT, FLOOR_BELT_MAIN, FLOOR_PAN, FLOOR_TONGUE, FLYWHEEL_R, FRONT_LIP,
                        FRONT_RAIL, GAP, HALF_W, INTAKE, R_BALL, VARIANTS, frame_constants, intake_points)

BATTERY_CLEATS = {"battery retention cleat aft": ((-100.0, 255.0, 101.5), (-91.5, 327.0, 200.0)),
                  "battery retention cleat fore": ((78.5, 255.0, 101.5), (80.5, 327.0, 200.0))}


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


def robot_bodies(variant="R3", intake_stowed=False):
    """Return {name: (shape, group)} for one variant in its installed pose."""
    k = frame_constants(variant)
    fl, wall, hook_top = k["floor"], k["wall"], k["hook"]
    B = {}

    def add(name, shape, group):
        B[name] = (single(shape), group)

    # Frame rails (2 x 1 in tube allocation) split so that bounding-box culling works.
    add("frame rail front", box((FRONT_RAIL["x0"], -338 - DY, FRONT_RAIL["z0"]), (FRONT_RAIL["x1"], 338 + DY, FRONT_RAIL["z1"])), "frame")
    add("frame rail rear", box((-340, -338 - DY, 69.85), (-314.6, 338 + DY, 120.65)), "frame")
    add("frame rail left", box((-313, 314.6 + DY, 69.85), (313, HALF_W, 120.65)), "frame")
    add("frame rail right", box((-313, -HALF_W, 69.85), (313, -314.6 - DY, 120.65)), "frame")
    add("floor pan", box((FLOOR_PAN["x0"], -313 - DY, fl - 6), (FLOOR_PAN["x1"], 313 + DY, fl)), "frame")
    add("floor pan front tongue", box((FLOOR_TONGUE["x0"], -183, fl - 6), (FLOOR_TONGUE["x1"], 183, fl)), "frame")
    add("front lip", box((FRONT_LIP["x0"], -183, FRONT_LIP["z0"]), (FRONT_LIP["x1"], 183, FRONT_LIP["z1"])), "frame")
    for side, s in (("left", 1), ("right", -1)):
        y = sorted((s * INTAKE["rail_y"][0], s * INTAKE["rail_y"][1]))
        add(f"intake slide rail {side}", box((160, y[0], 345), (336, y[1], 480)), "frame")
        y = sorted((s * (284 + DY), s * (314 + DY)))
        add(f"climber tube mount {side}", box((300, y[0], 127), (336, y[1], 222)), "frame")

    # Swerve corners: revolved wheel azimuth envelope, module body and motor envelope.
    for fx, sx in (("front", 1), ("rear", -1)):
        for side, sy in (("left", 1), ("right", -1)):
            cx, cy = sx * 265, sy * (265 + DY)
            add(f"{fx} {side} wheel azimuth envelope", cyl((cx, cy, 0), (0, 0, 1), 40.3, 76.2), "drivetrain")
            x = sorted((sx * 185, sx * 312)); y = sorted((sy * (185 + DY), sy * (312 + DY)))
            add(f"{fx} {side} module body", box((x[0], y[0], 80), (x[1], y[1], 125)), "drivetrain")
            add(f"{fx} {side} module motors", cyl((cx, cy, 127), (0, 0, 1), 32, 88), "drivetrain")

    # Bumpers in the bumper zone used by the foundation.
    add("bumper front", box((BUMPER["x0"], -416 - DY, BUMPER["z0"]), (BUMPER["x1"], 416 + DY, BUMPER["z1"])), "bumpers")
    add("bumper rear", box((-417.5, -416 - DY, 48), (-341.5, 416 + DY, 168)), "bumpers")
    add("bumper left", box((-340, 341.5 + DY, 48), (340, 417.5 + DY, 168)), "bumpers")
    add("bumper right", box((-340, -417.5 - DY, 48), (340, -341.5 - DY, 168)), "bumpers")

    # Hopper walls.
    add("hopper wall left", box((-312, 316 + DY, 125), (312, 319 + DY, wall)), "hopper")
    add("hopper wall right", box((-312, -319 - DY, 125), (312, -316 - DY, wall)), "hopper")
    add("hopper front upper wall", box((311, -282 - DY, 482), (313, 282 + DY, min(wall, hook_top - 44))), "hopper")  # 4 mm below the swinging jaws
    add("hopper rear wall", box((-96, -314 - DY, k["z0"] + R_BALL + 7), (-93, 314 + DY, wall)), "hopper")

    # Floor belts: static envelopes of moving belt surfaces.
    add("floor belt main", box((FLOOR_BELT_MAIN["x0"], -279 - DY, fl + 1.5), (FLOOR_BELT_MAIN["x1"], 231 + DY, k["belt_top"])), "floor belts")
    add("floor belt front", box((FLOOR_BELT_FRONT["x0"], -180, fl + 1.5), (FLOOR_BELT_FRONT["x1"], 180, k["belt_top"])), "floor belts")

    # Shooter: floor-fed flywheel, hood sector, side plates and motor.
    cx, cz = k["c"]
    add("flywheel", cyl((cx, -170, cz), (0, 1, 0), FLYWHEEL_R, 340), "shooter")
    end_deg, start_deg = k["hood_span_deg"]            # the launch trial rolls the FUEL off this end
    a0 = math.radians(end_deg)
    xdir = (math.cos(a0), 0, math.sin(a0))
    span = math.radians(start_deg - end_deg)
    outer = cyl((cx, 170, cz), (0, -1, 0), k["hood_out"], 340, xdir, span)
    inner = cyl((cx, 171, cz), (0, -1, 0), k["hood_in"], 342)
    add("hood", cut(outer, inner), "shooter")
    for side, s in (("left", 1), ("right", -1)):
        y = sorted((s * 173, s * 181))
        add(f"shooter side plate {side}", box((-338, y[0], 125), (-100, y[1], cz + 125)), "shooter")
    add("flywheel motor right", cyl((cx, -184, cz), (0, -1, 0), 30, 79), "shooter")
    add("flywheel motor left", cyl((cx, 184, cz), (0, 1, 0), 30, 79), "shooter")

    # Battery on its end, left side, withdrawn upward through the open hopper.
    add("battery", box((-90, 236 + DY, fl + 2), (77, 312 + DY, fl + 2 + 181)), "battery")
    for name, (lo, hi) in BATTERY_CLEATS.items():      # 6061 cleats on the floor pan at the battery's X ends
        dz = fl - 100.0
        add(name, box((lo[0], lo[1], lo[2] + dz), (hi[0], hi[1], hi[2] + dz)), "battery retention")
    add("electronics panel", box((-90, -312 - DY, fl + 2), (170, -282 - DY, fl + 182)), "electrical")
    add("electronics panel left", box((82, 282 + DY, fl + 2), (170, 312 + DY, fl + 182)), "electrical")
    add("entry sensor", box((300, -183, 123), (309, -175, 140)), "electrical")
    add("pinch sensor", box((-160, -190, cz - 75), (-140, -182.5, cz - 55)), "electrical")

    # Climber: fixed round outer tubes, round telescoping inner tubes and swing hooks (stowed pointing aft).
    for side, s in (("left", 1), ("right", -1)):
        yc = s * (299 + DY)
        tube_top = hook_top - 116  # below the hook arm at the end of the 29.6 mm seat and 70 mm lift strokes
        add(f"climber tube {side}", cut(cyl((300, yc, 224), (0, 0, 1), 15, tube_top - 224), cyl((300, yc, 223), (0, 0, 1), 13, tube_top - 222)), "climber tubes")
        add(f"climber inner tube {side}", cyl((300, yc, 330 if variant == "R3" else 230), (0, 0, 1), 11, hook_top - 14 - (330 if variant == "R3" else 230)), "climber inner tubes")
        arm = box((87, yc - 11, hook_top - 12), (313, yc + 11, hook_top))
        jaw = box((87, yc - 11, hook_top - 40), (99, yc + 11, hook_top - 12))
        add(f"climber hook {side}", fuse(arm, jaw), "climber hooks")
    add("climber winch", box((250, -150, wall - 60), (300, 150, wall - 15)), "climber tubes")

    # Intake carriage in its deployed pose; the start fold is the same carriage translated back by the slide.
    ip = intake_points()
    hw = INTAKE["half_width"]
    bx, px, rp = ip["belt_x"], ip["pulley_x"], ip["pulley_r"]
    rx, rz = ip["roller"]
    # The belt module is the belt's own outline: two pulleys joined by the back and front runs.
    belt = fuse(box((bx, -hw, ip["bottom_z"]), (ip["front_x"], hw, ip["top_z"])),
                cyl((px, -hw, ip["bottom_z"]), (0, 1, 0), rp, 2 * hw), cyl((px, -hw, ip["top_z"]), (0, 1, 0), rp, 2 * hw))
    pieces = {"intake belt module": belt,
              "intake top roller": cyl((rx, -hw, rz), (0, 1, 0), INTAKE["roller_r"], 2 * hw)}
    for side, s in (("left", 1), ("right", -1)):
        y = sorted((s * INTAKE["plate_y"][0], s * INTAKE["plate_y"][1]))
        pieces[f"intake carriage plate {side}"] = box((455, y[0], INTAKE["plate_z"][0]), (ip["front_x"], y[1], INTAKE["plate_z"][1]))
    dx, dy, dz = INTAKE["shift"]
    for name, shape in pieces.items():
        if intake_stowed:
            t = gp_Trsf(); t.SetTranslation(gp_Vec(-dx, -dy, -dz))
            shape = BRepBuilderAPI_Transform(shape, t, True).Shape()
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
        F[f"tower upright {side}"] = single(box((tower_face_x, y[0], 9.5), (tower_face_x + 88.9, y[1], 1831.3)))
    rung_x = tower_face_x + 88.9 / 2
    F["tower low rung"] = single(cyl((rung_x, tower_y - gap + 1.6, 685.8), (0, 1, 0), 42.164 / 2, 2 * gap - 3.2))
    # TOWER BASE: 39.0 x 45.18 in plate whose front edge stands about 0.18 in ahead of the uprights; edges up to 8 mm.
    F["tower base"] = single(box((tower_face_x - 4.6, tower_y - 495.3, 0), (tower_face_x - 4.6 + 1147.6, tower_y + 495.3, 8)))
    return F
