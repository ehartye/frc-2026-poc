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

from dimensions import (BATTERY_BOX, BUMPER, DY, EXIT_DEG, FEEDER, FLOOR_BELT_FRONT, FLOOR_BELT_MAIN, FLOOR_PAN, FLOOR_TONGUE, FLYWHEEL_PARTS,
                        FLYWHEEL_R, FRONT_RAIL, GAP, HALF_W, HOPPER, INTAKE, LANE_DECK, PANEL_RIGHT, REAR_WALL_X, R_BALL, VARIANTS,
                        frame_constants, intake_points)

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


def prism_yz(points, x0, x1):
    """Closed polygon in the YZ plane extruded from x0 to x1."""
    poly = BRepBuilderAPI_MakePolygon()
    for y, z in points:
        poly.Add(gp_Pnt(x0, y, z))
    poly.Close()
    face = BRepBuilderAPI_MakeFace(poly.Wire()).Face()
    return BRepPrimAPI_MakePrism(face, gp_Vec(x1 - x0, 0, 0)).Shape()


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
    H = HOPPER
    lane, hw, cheek = H["lane_half"], HALF_W - 24.0, H["cheek_y"]
    wx = REAR_WALL_X[1]
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
    add("lane deck", box((LANE_DECK["x0"], -lane + 2, k["belt_top"] - LANE_DECK["t"]), (LANE_DECK["x1"], lane - 2, k["belt_top"])), "frame")
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

    # Hopper: side walls, the two-lane channel, shelves over the battery and the electronics, cheeks beside the stowed intake.
    add("hopper wall left", box((-312, 316 + DY, 125), (312, 319 + DY, wall)), "hopper")
    add("hopper wall right", box((-312, -319 - DY, 125), (312, -316 - DY, wall)), "hopper")
    gate = k["z0"] + R_BALL + 7
    add("hopper rear wall", box((REAR_WALL_X[0], -lane - 2, gate), (wx, 314 + DY, wall)), "hopper")
    sz, fz = H["shelf_z"], H["front_shelf_z"]
    rise = (hw - lane) * math.tan(math.radians(H["shelf_deg"]))
    fr = H["front_rise"]
    fx_, t, j = H["front_x"], 2.0, 1.5        # j: drawn split at a joint to a neighbouring solid
    for side, s in (("left", 1), ("right", -1)):
        # One formed liner per side: the channel wall, the shelf over the battery or the electronics, the low front
        # shelf under the stowed intake, the step between them, the wall that closes the bay outboard of the cheek and
        # the cheek. Shelf plates are 2 mm thick with their top faces at the trial surfaces. The right liner starts
        # ahead of the inertia ring, behind a pocket wall.
        x0 = wx + j if s > 0 else H["shelf_x0_right"]
        y = lambda v: s * v
        ys = lambda a, b: (min(y(a), y(b)), max(y(a), y(b)))
        out = hw - j
        top = lambda v: sz + (v - lane) / (hw - lane) * rise      # shelf top face height at |y| = v
        plate = lambda xa, xb: prism_yz([(y(lane), sz), (y(out), top(out)), (y(out), top(out) - t), (y(lane), sz - t)], xa, xb)
        panel_end = 84.0                          # the lift-out panel stops short of the stowed hook arm above it
        parts = [
            box((wx + j, ys(lane, lane + t)[0], fl + j), (fx_, ys(lane, lane + t)[1], sz if s < 0 else sz - t - j)),     # channel wall, rear
            box((fx_ - t, ys(lane, lane + t)[0], fl + j), (313, ys(lane, lane + t)[1], fz)),                             # channel wall, front
            prism_yz([(y(lane), fz), (y(cheek + t), fz + fr), (y(cheek + t), fz + fr - t), (y(lane), fz - t)], fx_ - t, FRONT_RAIL["x1"]),  # front shelf
            prism_yz([(y(lane), fz - t), (y(cheek + t), fz + fr - t), (y(cheek + t), top(cheek + t)), (y(lane), sz)], fx_ - t, fx_),         # step
            box((fx_ - t, ys(cheek, out)[0], fz + fr - t), (fx_, ys(cheek, out)[1], wall)),                              # bay wall
            box((fx_ - t, ys(cheek, cheek + t)[0], fz + fr - t), (337, ys(cheek, cheek + t)[1], wall)),                  # cheek
        ]
        if s < 0:   # the right shelf is part of the liner, with the pocket walls ahead of the inertia ring
            parts += [plate(x0, fx_), box((wx + j, -lane - t, sz - t), (x0, -lane, wall)), box((x0 - t, -out, sz - t), (x0, -lane, wall))]
        else:       # the left shelf over the battery is a separate panel that lifts straight out for battery service
            add("hopper shelf left", plate(x0, panel_end), "hopper shelf")
            parts.append(plate(panel_end + j, fx_))
        add(f"hopper liner {side}", fuse(*parts), "hopper")

    # Floor belts: static envelopes of moving belt surfaces, inside the channel.
    add("floor belt main", box((FLOOR_BELT_MAIN["x0"], -lane + 2, fl + 1.5), (FLOOR_BELT_MAIN["x1"], lane - 2, k["belt_top"])), "floor belts")
    add("floor belt front", box((FLOOR_BELT_FRONT["x0"], -lane + 2, fl + 1.5), (FLOOR_BELT_FRONT["x1"], lane - 2, k["belt_top"])), "floor belts")

    # Feeders: one roller per lane ahead of the flywheel, each with a gearmotor outboard of the channel wall. The 12 mm
    # shaft between them passes the channel wall and the shelf's inboard edge and is not drawn.
    fxc, fzc = k["feeder"]
    y0, y1 = FEEDER["lane_y"]
    for side, s in (("left", 1), ("right", -1)):
        add(f"feeder roller {side}", cyl((fxc, s * y0, fzc), (0, s, 0), FEEDER["r"], y1 - y0), "feeders")
        add(f"feeder motor {side}", cyl((fxc, s * 204, fzc), (0, s, 0), 17, 46), "feeders")

    # Shooter: floor-fed flywheel, hood sector, side plates, a motor on each shaft end and the inertia ring.
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
    ry = FLYWHEEL_PARTS["ring_y"]
    add("flywheel inertia ring", cyl((cx, ry[0], cz), (0, 1, 0), FLYWHEEL_PARTS["ring"]["ro"], ry[1] - ry[0]), "shooter")
    add("flywheel motor right", cyl((cx, ry[0] - 2, cz), (0, -1, 0), 30, 79), "shooter")
    add("flywheel motor left", cyl((cx, 184, cz), (0, 1, 0), 30, 79), "shooter")

    # Battery on its end under the left shelf; its cleats and strap. Electronics under the right shelf and in the right bay.
    (bx0, by0, bz0), (bx1, by1, bz1) = BATTERY_BOX
    add("battery", box((bx0, by0, bz0 + (fl - 100)), (bx1, by1, bz1 + (fl - 100))), "battery")
    for name, (lo, hi) in BATTERY_CLEATS.items():      # 6061 cleats on the floor pan at the battery's X ends
        dz = fl - 100.0
        add(name, box((lo[0], lo[1], lo[2] + dz), (hi[0], hi[1], hi[2] + dz)), "battery retention")
    add("battery strap", box((-20, by0 - 2, bz1 + (fl - 100) + 1.5), (10, by1 + 2, bz1 + (fl - 100) + 4.5)), "battery strap")
    (px0, py0, pz0), (px1, py1, pz1) = PANEL_RIGHT
    add("electronics panel", box((px0, py0, pz0 + (fl - 100)), (px1, py1, pz1 + (fl - 100))), "electrical")
    add("electronics panel left", box((82, 282 + DY, fl + 2), (fx_ - 4, 312 + DY, fl + 182)), "electrical")
    # the bay panel and the winch hang under the fixed slide rails, outboard of the carriage plates' path
    add("electronics bay right", box((165, -314 - DY, 245), (280, -(INTAKE["rail_y"][0] - 0.5), 343.5)), "electrical")
    for side, s in (("left", 1), ("right", -1)):       # stage beams, one per lane, on the outside of the channel wall
        y = sorted((s * (lane + 3), s * (lane + 10)))
        add(f"stage sensor {side}", box((FEEDER["sensor_x"] - 6, y[0], k["belt_top"] + R_BALL - 8), (FEEDER["sensor_x"] + 6, y[1], k["belt_top"] + R_BALL + 8)), "electrical")

    # Climber: fixed round outer tubes, round telescoping inner tubes and swing hooks (stowed pointing aft).
    for side, s in (("left", 1), ("right", -1)):
        yc = s * (299 + DY)
        tube_top = hook_top - 116  # below the hook arm at the end of the 29.6 mm seat and 70 mm lift strokes
        add(f"climber tube {side}", cut(cyl((300, yc, 224), (0, 0, 1), 15, tube_top - 224), cyl((300, yc, 223), (0, 0, 1), 13, tube_top - 222)), "climber tubes")
        add(f"climber inner tube {side}", cyl((300, yc, 330 if variant == "R3" else 230), (0, 0, 1), 11, hook_top - 14 - (330 if variant == "R3" else 230)), "climber inner tubes")
        arm = box((87, yc - 11, hook_top - 12), (313, yc + 11, hook_top))
        jaw = box((87, yc - 11, hook_top - 40), (99, yc + 11, hook_top - 12))
        add(f"climber hook {side}", fuse(arm, jaw), "climber hooks")
    add("climber winch", box((165, INTAKE["rail_y"][0] - 0.5, 245), (270, 314 + DY, 343.5)), "climber tubes")

    # Intake carriage in its deployed pose; the start fold is the same carriage translated back by the slide.
    ip = intake_points()
    half = INTAKE["half_width"]
    bx, px, rp = ip["belt_x"], ip["pulley_x"], ip["pulley_r"]
    rx, rz = ip["roller"]
    # The belt module is the belt's own outline: two pulleys joined by the back and front runs.
    belt = fuse(box((bx, -half, ip["bottom_z"]), (ip["front_x"], half, ip["top_z"])),
                cyl((px, -half, ip["bottom_z"]), (0, 1, 0), rp, 2 * half), cyl((px, -half, ip["top_z"]), (0, 1, 0), rp, 2 * half))
    x1, z0, z1 = BUMPER["x1"], INTAKE["back_z0"], INTAKE["back_top"]
    back = prism_xz([(x1 - INTAKE["back_foot"], z0), (x1, z0), (x1, z1), (x1 - INTAKE["back_t"], z1)], -half, half)
    pieces = {"intake belt module": belt,
              "intake top roller": cyl((rx, -half, rz), (0, 1, 0), INTAKE["roller_r"], 2 * half),
              "intake back plate": back}
    for side, s in (("left", 1), ("right", -1)):
        y = sorted((s * INTAKE["plate_y"][0], s * INTAKE["plate_y"][1]))
        pieces[f"intake carriage plate {side}"] = box((INTAKE["plate_x0"], y[0], INTAKE["plate_z"][0]), (ip["front_x"], y[1], INTAKE["plate_z"][1]))
    pieces["entry sensor"] = box((430, INTAKE["plate_y"][0], INTAKE["plate_z"][1] + 1.5), (439, INTAKE["plate_y"][1] - 1, INTAKE["plate_z"][1] + 18))
    dx, dy, dz = INTAKE["shift"]
    for name, shape in pieces.items():
        if intake_stowed:
            t_ = gp_Trsf(); t_.SetTranslation(gp_Vec(-dx, -dy, -dz))
            shape = BRepBuilderAPI_Transform(shape, t_, True).Shape()
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
