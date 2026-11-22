"""Hopper trials for R3: free FUEL as spheres in three dimensions, in through the intake chute, held, and out to the two feeders.

Every FUEL is a free body with penalty contact against the hopper surfaces, the feeder rollers and each other
(explicit semi-implicit Euler). Friction is regularized Coulomb, except on the two surfaces that clamp a staged FUEL,
the lane deck and the feeder rollers: there it is stick-slip with a tangential spring, the law of the lane trials in
field_trials.py, so a clamped FUEL holds until the load exceeds its friction instead of creeping. The floor
belts and the feeder rollers carry imposed surface speeds; the lane controller below decides them from the stage
beams, as the robot's would. A FUEL that a feeder advances to the flywheel is counted and leaves the model there:
what the flywheel then does with it is the launch and batch trials' question (field_trials.py).

The surfaces are the layout's (dimensions.py and the same numbers geometry.py draws), reduced to rectangles and
cylinders. Units are SI. numpy is needed here and nowhere else in the trials.

    python -I -B experiments/preliminary-design/hopper_flow.py        # prints the trial table; field_trials.py records it
"""
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import dimensions as D

MM = 0.001
R = D.R_BALL * MM
G = 9.81
B_X1 = D.BUMPER["x1"]
TAKE_X = (D.frame_constants()["c"][0] + 53.7) * MM    # FUEL centre where it first touches the flywheel: taken by the wheel


def surfaces(belt_mps, opt=None):
    """The hopper as rectangles (origin, edge u, edge v, surface velocity, friction class, label), in metres.
    opt overrides the layout for a control or a comparison: wall_x (rear wall face), floor ("trough", "guides" or
    "bin"), shelf_deg, shelf_z, front_x, divider (bool), front ("chute", the layout: closed by the lip and the back
    plate of the deployed intake; or "throat", the open throat of the earlier issue, with throat_ramp)."""
    opt = dict(opt or {})
    K = D.frame_constants()
    H, I_, B, RL = D.HOPPER, D.INTAKE, D.BUMPER, D.FRONT_RAIL
    front_end = RL["x1"] if opt.get("front", "chute") == "chute" else 311.0     # where the channel and front shelves end
    bt, pan, wall = K["belt_top"], K["floor"], K["wall"]
    hw = D.HALF_W - 24.0                       # hopper side wall inner face: 333 mm
    wx = opt.get("wall_x", D.REAR_WALL_X[1])
    gate_z = K["z0"] + D.R_BALL + 7
    lane = opt.get("lane_half", H["lane_half"])
    floor = opt.get("floor", H["floor"])
    front = opt.get("front", "chute")
    shelf_z = opt.get("shelf_z", H["shelf_z"])
    rise = (hw - lane) * math.tan(math.radians(opt.get("shelf_deg", H["shelf_deg"])))
    cheek = H["cheek_y"]
    rects = []

    def rect(o, u, v, label, kind="hard", vel=(0.0, 0.0, 0.0)):
        rects.append((o, u, v, vel, kind, label))

    def box(lo, hi, label, faces="xyzXYZ"):
        (x0, y0, z0), (x1, y1, z1) = lo, hi
        if "z" in faces.lower():
            rect((x0, y0, z1), (x1 - x0, 0, 0), (0, y1 - y0, 0), label)
        if "x" in faces:
            rect((x0, y0, z0), (0, y1 - y0, 0), (0, 0, z1 - z0), label)
        if "X" in faces:
            rect((x1, y0, z0), (0, y1 - y0, 0), (0, 0, z1 - z0), label)
        if "y" in faces:
            rect((x0, y0, z0), (x1 - x0, 0, 0), (0, 0, z1 - z0), label)
        if "Y" in faces:
            rect((x0, y1, z0), (x1 - x0, 0, 0), (0, 0, z1 - z0), label)

    m, f = D.FLOOR_BELT_MAIN, D.FLOOR_BELT_FRONT
    by = (lane, lane) if floor in ("trough", "bin") else (279 + D.DY, 231 + D.DY)
    rect((m["x0"], -by[0], bt), (m["x1"] - m["x0"], 0, 0), (0, by[0] + by[1], 0), "floor belt main", "belt", (-belt_mps, 0, 0))
    rect((D.LANE_DECK["x0"], -lane, bt), (D.LANE_DECK["x1"] - D.LANE_DECK["x0"], 0, 0), (0, 2 * lane, 0), "lane deck", "deck")
    if opt.get("divider", bool(H["divider"])):
        dv = dict(H["divider"] or dict(half_t=1.5, x1=309.0), **opt.get("divider_dims", {}))
        gate_z_div = bt + dv.get("h", gate_z - bt)
        for y in (-dv["half_t"], dv["half_t"]):
            rect((D.LANE_DECK["x0"], y, bt + 2), (dv["x1"] - D.LANE_DECK["x0"], 0, 0), (0, 0, gate_z_div - bt - 2), "lane divider")
        rect((dv["x1"], -dv["half_t"], bt + 2), (0, 2 * dv["half_t"], 0), (0, 0, gate_z_div - bt - 2), "lane divider")
        rect((D.LANE_DECK["x0"], -dv["half_t"], gate_z_div), (dv["x1"] - D.LANE_DECK["x0"], 0, 0), (0, 2 * dv["half_t"], 0), "lane divider")
    rect((f["x0"], -min(180, lane), bt), (f["x1"] - f["x0"], 0, 0), (0, 2 * min(180, lane), 0), "floor belt front", "belt", (-belt_mps, 0, 0))
    rect((D.FLOOR_PAN["x0"], -hw, pan), (D.FLOOR_PAN["x1"] - D.FLOOR_PAN["x0"], 0, 0), (0, 2 * hw, 0), "floor pan")
    rect((D.FLOOR_TONGUE["x0"], -183, pan), (D.FLOOR_TONGUE["x1"] - D.FLOOR_TONGUE["x0"], 0, 0), (0, 366, 0), "floor pan front tongue")
    L = dict(x0=front_end)
    cheek_end = B["x1"] if front == "chute" else 470          # the carriage plates carry the cheek line on to the back plate
    for s in (1, -1):
        side = "left" if s > 0 else "right"
        rect((-340, s * hw, pan), (680, 0, 0), (0, 0, wall - pan), "hopper wall " + side)
        rect((337, min(s * cheek, s * hw), 125), (0, hw - cheek, 0), (0, 0, wall - 125), "hopper front corner wall " + side)
        rect((-143, s * 173, pan), (143 + min(wx, D.FEEDER["x"] + 40), 0, 0), (0, 0, 320), "shooter side plate " + side)
        if floor == "bin":
            # straight walls two lanes apart for the whole height: nothing converges
            rect((wx, s * lane, pan), (337 - wx, 0, 0), (0, 0, wall - pan), "hopper wall " + side)
        elif floor == "trough":
            # a two-lane channel the whole length of the floor. Aft of the stowed intake a shelf slopes up from it to the
            # side wall; under the stowed intake a low shelf slopes up to a cheek wall. The right shelf starts ahead of
            # the inertia ring, behind a pocket wall
            fx_, fz_, fr_ = opt.get("front_x", H["front_x"]), H["front_shelf_z"], opt.get("front_rise", H["front_rise"])
            sx = max(wx, opt.get("shelf_x0_right", H["shelf_x0_right"])) if s < 0 else wx
            rect((wx, s * lane, pan), (fx_ - wx, 0, 0), (0, 0, shelf_z - pan), "hopper channel wall " + side)
            rect((sx, s * lane, shelf_z), (fx_ - sx, 0, 0), (0, s * (hw - lane), rise), "hopper shelf " + side)
            if sx > wx:
                rect((wx, s * lane, shelf_z), (sx - wx, 0, 0), (0, 0, wall - shelf_z), "hopper pocket wall " + side)
                rect((sx, min(s * lane, s * hw), shelf_z), (0, hw - lane, 0), (0, 0, wall - shelf_z), "hopper pocket wall " + side)
            rect((fx_, min(s * lane, s * hw), fz_), (0, hw - lane, 0), (0, 0, shelf_z + rise - fz_), "hopper shelf " + side)
            rect((fx_, s * lane, pan), (front_end - fx_, 0, 0), (0, 0, fz_ - pan), "hopper channel wall " + side)
            rect((fx_, s * lane, fz_), (front_end - fx_, 0, 0), (0, s * (cheek - lane), fr_), "hopper front shelf " + side)
            rect((fx_, s * cheek, fz_), (cheek_end - fx_, 0, 0), (0, 0, wall - fz_), "hopper cheek " + side)
            if front == "throat":   # turns FUEL on the ramp in toward the channel
                rect((417.5, s * 260, B["z1"]), (311 - 417.5, s * (200 - 260), 0), (0, 0, 482 - B["z1"]), "throat guide " + side)
        else:
            box((185, min(s * (185 + D.DY), s * (312 + D.DY)), 80), (312, max(s * (185 + D.DY), s * (312 + D.DY)), 125), "module body", "zxy" if s > 0 else "zxY")
            rect((wx, min(s * lane, s * hw), pan), (0, hw - lane, 0), (0, 0, gate_z - pan), "hopper rear wall")
    # rear wall: a one-FUEL-high gate across the lanes
    rect((wx, -hw, gate_z), (0, 2 * hw, 0), (0, 0, wall - gate_z), "hopper rear wall")
    rect((B["x0"], -cheek, B["z1"]), (B["x1"] - B["x0"], 0, 0), (0, 2 * cheek, 0), "bumper front")
    if front == "chute":
        # no lip: the floor belt runs to the front rail, whose top and the back of the bumper above it close the channel.
        # Above the bumper top the back plate of the deployed intake closes the hopper: a wedge whose hopper-side face
        # leans forward, so a FUEL touching it has its centre over the belt
        foot, top, z0 = B["x1"] - I_["back_foot"], I_["back_top"], I_["back_z0"]
        rect((RL["x0"], -lane, RL["z1"]), (RL["x1"] - RL["x0"], 0, 0), (0, 2 * lane, 0), "frame rail front")
        rect((RL["x1"], -cheek, bt), (0, 2 * cheek, 0), (0, 0, B["z1"] - bt), "bumper front")
        rect((RL["x1"], -cheek, B["z1"]), (B["x0"] - RL["x1"], 0, 0), (0, 2 * cheek, 0), "bumper front")
        rect((foot, -cheek, z0), (B["x1"] - I_["back_t"] - foot, 0, top - z0), (0, 2 * cheek, 0), "chute back plate")
        rect((B["x1"] - I_["back_t"], -cheek, top), (I_["back_t"], 0, 0), (0, 2 * cheek, 0), "chute back plate")
    else:
        L = dict(x0=311.0, x1=313.0, z0=123.0, z1=170.0)     # the vertical front lip of the earlier issue
        rect((L["x0"], -183, L["z0"]), (0, 366, 0), (0, 0, L["z1"] - L["z0"]), "front lip")
        rect((L["x0"], -183, L["z1"]), (L["x1"] - L["x0"], 0, 0), (0, 366, 0), "front lip")
        rect((L["x1"], -260, D.FRONT_RAIL["z1"]), (B["x0"] - L["x1"], 0, 0), (0, 520, 0), "frame rail front")
        rect((B["x0"], -260, D.FRONT_RAIL["z1"]), (0, 520, 0), (0, 0, B["z1"] - D.FRONT_RAIL["z1"]), "bumper front")
        ramp = opt.get("throat_ramp", 0)
        if ramp:   # a plate over the bumper top and rail that slopes down aft to the lip
            rect((L["x0"], -260, L["z1"]), (B["x1"] - L["x0"], 0, ramp - L["z1"]), (0, 520, 0), "throat ramp")
        rect((311, -282 - D.DY, 482), (0, 564 + 2 * D.DY, 0), (0, 0, wall - 482), "hopper front upper wall")
        rect((311, -260, 482), (440 - 311, 0, 420 - 482), (0, 520, 0), "throat cover")
    if floor not in ("trough", "bin"):
        box((-25.0, 253.0, 102.0), (142.0, 329.0, 283.0), "battery", "zxXy")
        box((-90.0, -329.0, 102.0), (170.0, -299.0, 282.0), "electronics panel", "zXY")
    if floor == "guides":   # the earlier issue's full-height plates that turn the floor layer in to the lane mouth
        for (a, b), name in zip((((62.0, 250.0), (wx, 168.0)), ((120.0, -297.0), (wx, -168.0))), ("left", "right")):
            rect((a[0], a[1], pan), (b[0] - a[0], b[1] - a[1], 0), (0, 0, wall - pan), "hopper lane guide " + name)
    O = np.array([r[0] for r in rects], float) * MM
    U = np.array([r[1] for r in rects], float) * MM
    V = np.array([r[2] for r in rects], float) * MM
    return dict(O=O, U=U, V=V, vel=np.array([r[3] for r in rects], float), kind=[r[4] for r in rects], label=[r[5] for r in rects], floor=floor, front=front)


def posts():
    """Vertical cylinders: module motors and climber tubes (x, y, r, z0, z1) in metres."""
    out = []
    for sy in (1, -1):
        out.append((265 * MM, sy * (265 + D.DY) * MM, 32 * MM, 0.127, 0.215))
        out.append((300 * MM, sy * (299 + D.DY) * MM, 15 * MM, 0.224, 0.634))
    return out


# The acquisition trial's capture state, where an arriving FUEL joins this model: x, z (m), vx, vz (m/s), spin (rad/s).
# field_trials.py passes the state its acquire-nominal trial ends with; this default is that state for a direct run.
THROW = (0.340, 0.552, -1.867, 0.221, 48.3)
BOTH_MM = 30.0          # a FUEL this close to the centre line is under both feeder rollers and breaks both stage beams
CHUTE_HOLDS = 4          # FUEL the chute holds above the bumper top with its belt stopped: two rows, counted two abreast


def heap(n, seed, trough, jitter=0.008):
    """n FUEL on a loose lattice above the floor, dropped together."""
    rng = np.random.default_rng(seed)
    xs = (0.055, 0.222)
    pts = []
    layer = 0
    while len(pts) < n:
        # in the trough the two lowest layers stand in the channel; above the shelves a layer is four across
        ys = (-0.200, -0.035, 0.130) if not trough else (-0.082, 0.082) if layer < 6 else (-0.246, 0.246)
        for x in xs:
            for y in ys:
                if len(pts) < n:
                    pts.append((x, y, 0.200 + 0.156 * layer if layer < 6 else 0.50 + 0.156 * (layer - 6)))
        layer += 1
    return np.array(pts) + rng.uniform(-jitter, jitter, (n, 3))


def feed(name, n=24, seed=1, belt=None, period=None, mu_ball=0.7, mu_belt=0.9, mu_hard=0.4, mu_feeder=0.9, k=15000.0, zeta=0.3, mass=0.215,
         crr=0.03, dt=2e-4, settle_s=1.5, t_end=16.0, tilt_deg=0.0, opt=None, reverse=True, feeders=True,
         mu_deck=0.6, intake=None, stick=True, frames_every=0.04,
         keep_frames=False, arrive=0, arrive_rate=4.0, feed_from=0.0, accel=None, throw=None, belt_idle=True, unjam=(0.3, 0.5), nudge=None):
    """Heap of n FUEL to the flywheel. After the heap settles the belts run and the two lane feeders stage and feed in
    turn, no faster than one feed per period. If nothing reaches the flywheel for 1 s while FUEL remain, the belt
    reverses for 0.3 s (an unjam cycle, counted). tilt_deg rolls gravity toward the right wall. stick=False uses the
    regularized friction law on the deck and feeders too (the control for the law: a clamped FUEL then creeps).

    arrive of the n FUEL are not in the heap: they come in through the intake, one every 1 / arrive_rate s from t = 0,
    each thrown over the lip with the acquisition trial's capture state at a random lane position when the throat is
    clear, and held in the intake pinch until then. feed_from is when the feed commands begin (None: never, the
    robot only collects and holds); before it the feeders stage and hold. accel is a list of (from s, to s, ax g, ay g)
    robot accelerations felt by every FUEL (+X forward, +Y left)."""
    F_ = D.FEEDER
    belt = D.FLOOR_BELT_MPS if belt is None else belt
    period = F_["period_s"] if period is None else period
    S = surfaces(1.0, opt)
    is_belt = np.array([q == "belt" for q in S["kind"]])
    mu_s = np.where(is_belt, mu_belt, np.where(np.array([q == "deck" for q in S["kind"]]), mu_deck, mu_hard))
    Un, Vn = np.linalg.norm(S["U"], axis=1), np.linalg.norm(S["V"], axis=1)
    Uh, Vh = S["U"] / Un[:, None], S["V"] / Vn[:, None]
    K = D.frame_constants()
    fx, fz, fr = K["feeder"][0] * MM, K["feeder"][1] * MM, F_["r"] * MM
    lane_y = [(F_["lane_y"][0] * MM, F_["lane_y"][1] * MM), (-F_["lane_y"][1] * MM, -F_["lane_y"][0] * MM)]
    ip = D.intake_points()
    ir = (ip["roller"][0] * MM, ip["roller"][1] * MM, ip["roller_r"] * MM)
    intake = D.INTAKE["belt_mps"] * D.INTAKE["roller_ratio"] if intake is None else intake
    chute = S["front"] == "chute"
    sensor = F_["sensor_x"] * MM
    c = 2 * zeta * math.sqrt(k * mass)
    inertia = 0.4 * mass * R * R
    tilt = math.radians(tilt_deg)
    grav = np.array([0.0, -G * math.sin(tilt), -G * math.cos(tilt)])
    pos = np.zeros((n, 3))
    if n - arrive:
        pos[:n - arrive] = heap(n - arrive, seed, S["floor"] in ("trough", "bin"))
    rng = np.random.default_rng(1000 + seed)
    vel = np.zeros((n, 3)); om = np.zeros((n, 3))
    alive = np.ones(n, bool)
    P = posts()
    eps = 0.01
    is_deck = np.array([q == "deck" for q in S["kind"]])
    # carriage nudge: in an unjam cycle the intake slide draws the carriage, and with it the back plate, back along its
    # slide by nudge[0] mm and returns it in nudge[1] s
    nudge = D.INTAKE["nudge"] if nudge is None else nudge
    plate = np.array([q == "chute back plate" for q in S["label"]])
    slide = -np.array(D.INTAKE["shift"]) / np.linalg.norm(D.INTAKE["shift"])
    O0, sv = S["O"].copy(), np.zeros((len(S["label"]), 3))
    # tangential springs of the stick-slip contacts: one row per FUEL on the deck and on each feeder roller
    spring = dict(deck=np.zeros((n, 3)), left=np.zeros((n, 3)), right=np.zeros((n, 3)))
    peak_push, push_f = 0.0, np.zeros(n)
    lanes = [dict(mode="staging", ball=None), dict(mode="staging", ball=None)]
    delivered, unjams, last_feed, last_take, last_lane = [], 0, -1e9, 0.0, 1
    reverse_until, first_stall = -1.0, None
    frames, t, step = [], -settle_s, 0
    lost, recirculated, pending, where = 0, 0, [], []
    throw = THROW if throw is None else throw
    held = np.zeros(n, bool)
    held[n - arrive:] = True
    pending = [(i / arrive_rate, n - arrive + i) for i in range(arrive)]
    pos[n - arrive:, 1] = rng.uniform(-0.17, 0.17, arrive)
    entered, feeding_on = [], False
    PINCH_X = (D.BUMPER["x1"] + (20.0 if chute else 45.0)) * MM
    PINCH_Z = (D.INTAKE["back_top"] + 2 * D.R_BALL) * MM if chute else 0.30
    next_frame = 0.0

    def contact(n_, pen, surf_v, mu, idx, F, Tq, store=None):
        """Accumulate penalty and friction forces for contacts on balls idx with normals n_ (surface to ball).
        store names the tangential-spring table of a stick-slip surface; each ball may appear once per call."""
        r_ = -n_ * R
        vc = vel[idx] + np.cross(om[idx], r_) - surf_v
        vn = np.einsum("ij,ij->i", vc, n_)
        Fn = np.maximum(0.0, k * pen - c * vn)
        vt = vc - vn[:, None] * n_
        if store is None or not stick:
            vtm = np.sqrt(np.einsum("ij,ij->i", vt, vt) + eps * eps)
            Ft = -(mu * Fn / vtm)[:, None] * vt
        else:
            xi = spring[store][idx] + vt * dt
            xi -= np.einsum("ij,ij->i", xi, n_)[:, None] * n_
            Ft = -k * xi - c * vt
            mag = np.sqrt(np.einsum("ij,ij->i", Ft, Ft))
            lim = mu * Fn
            over = mag > lim                              # sliding: the spring keeps only what the friction limit holds
            Ft[over] *= (lim[over] / mag[over])[:, None]
            xi[over] = -Ft[over] / k
            fresh[store][idx] = xi
        np.add.at(F, idx, Fn[:, None] * n_ + Ft)
        w = om[idx]
        wm = np.sqrt(np.einsum("ij,ij->i", w, w) + 0.2 ** 2)
        np.add.at(Tq, idx, np.cross(r_, Ft) - (crr * Fn * R / wm)[:, None] * w)

    while t < t_end and alive.any():
        running = t >= 0.0
        feeding_on = feed_from is not None and t >= feed_from
        if feeding_on and reverse and t - max(last_take, feed_from) > 1.0 and t > reverse_until + 1.0:
            reverse_until = t + unjam[0]; unjams += 1
            first_stall = round(t, 3) if first_stall is None else first_stall
        # the floor belt runs only while a lane is staging or feeding: with both lanes staged and held it stops
        idle = feeders and belt_idle and all(ln["mode"] == "staged" for ln in lanes)
        vb = 0.0 if not running or idle else (-unjam[1] * belt if t < reverse_until else belt)
        sv[:] = S["vel"] * vb
        if nudge[0] and plate.any():
            u = (t - (reverse_until - unjam[0])) / nudge[1] if reverse_until > 0 else 2.0
            if 0.0 <= u <= 1.0:
                S["O"][plate] = O0[plate] + nudge[0] * MM * (1 - abs(2 * u - 1)) * slide
                sv[plate] = (2 if u < 0.5 else -2) * nudge[0] * MM / nudge[1] * slide
            else:
                S["O"][plate] = O0[plate]
        # lane controller: stage to the beam, hold, feed on the scheduler's command
        uf = [0.0, 0.0]
        if running and feeders:
            for li, ln in enumerate(lanes):
                y0, y1 = lane_y[li]
                # each lane has its own stage beam; a FUEL within BOTH_MM of the centre line breaks both, and both rollers then hold or feed it together
                inl = np.where(alive & (pos[:, 1] * (1 if li == 0 else -1) > -BOTH_MM * MM) & (pos[:, 0] < sensor + 0.060) & (pos[:, 2] < K["belt_top"] * MM + R + 0.03))[0]
                lead = inl[np.argmin(pos[inl, 0])] if len(inl) else None
                if ln["mode"] == "staging" and lead is not None and pos[lead, 0] <= sensor:
                    ln["mode"], ln["ball"] = "staged", lead
                if ln["mode"] == "staged" and (lead is None or pos[lead, 0] > sensor + 0.02):
                    ln["mode"], ln["ball"] = "staging", None       # the staged FUEL was pushed back out
                uf[li] = dict(staging=F_["stage_mps"], staged=0.0, feeding=F_["mps"])[ln["mode"]]
            if feeding_on and t - last_feed >= period and not any(ln["mode"] == "feeding" for ln in lanes):
                order = [1 - last_lane, last_lane]
                for li in order:
                    if lanes[li]["mode"] == "staged":
                        lanes[li]["mode"] = "feeding"; last_feed, last_lane = t, li
                        uf[li] = F_["mps"]
                        other = lanes[1 - li]
                        if other["ball"] == lanes[li]["ball"]:      # one FUEL under both rollers: both turn
                            other["mode"] = "feeding"; uf[1 - li] = F_["mps"]
                        break
        g_now = grav
        for (a0, a1, ax, ay) in accel or ():
            if a0 <= t < a1:
                g_now = grav - np.array([ax * G, ay * G, 0.0])
        F = np.tile(g_now * mass, (n, 1)); Tq = np.zeros((n, 3))
        fresh = {q: np.zeros((n, 3)) for q in spring}
        push = np.zeros(n)
        ids = np.where(alive)[0]
        p = pos[ids]
        # rectangles
        d = p[:, None, :] - S["O"][None, :, :]
        a = np.clip(np.einsum("nmj,mj->nm", d, Uh), 0.0, Un[None, :])
        b = np.clip(np.einsum("nmj,mj->nm", d, Vh), 0.0, Vn[None, :])
        diff = d - a[:, :, None] * Uh[None] - b[:, :, None] * Vh[None]
        dist = np.sqrt(np.einsum("nmj,nmj->nm", diff, diff))
        bi, mi = np.where((dist < R) & (dist > 1e-9))
        if len(bi):
            n_ = diff[bi, mi] / dist[bi, mi][:, None]
            dk = is_deck[mi]
            contact(n_[~dk], R - dist[bi, mi][~dk], sv[mi][~dk], mu_s[mi][~dk], ids[bi][~dk], F, Tq)
            if dk.any():
                contact(n_[dk], R - dist[bi, mi][dk], sv[mi][dk], mu_s[mi][dk], ids[bi][dk], F, Tq, "deck")
        # vertical posts
        for (cx, cy, cr, z0, z1) in P:
            q = p.copy(); q[:, 2] = np.clip(p[:, 2], z0, z1)
            rad = np.hypot(p[:, 0] - cx, p[:, 1] - cy)
            scale = np.minimum(1.0, cr / np.maximum(rad, 1e-9))
            q[:, 0] = cx + (p[:, 0] - cx) * scale; q[:, 1] = cy + (p[:, 1] - cy) * scale
            diffp = p - q
            dp = np.sqrt(np.einsum("ij,ij->i", diffp, diffp))
            hit = np.where((dp < R) & (dp > 1e-9))[0]
            if len(hit):
                contact(diffp[hit] / dp[hit][:, None], R - dp[hit], np.zeros((len(hit), 3)), np.full(len(hit), mu_hard), ids[hit], F, Tq)
        # feeder rollers (axis along Y)
        rollers = [(fx, fz, fr, y0, y1, uf[li], mu_feeder, ("left", "right")[li]) for li, (y0, y1) in enumerate(lane_y)] if feeders else []
        rollers.append((ir[0], ir[1], ir[2], -0.258, 0.258, intake if running else 0.0, mu_belt, None))
        for (rx, rz, rr, y0, y1, us, mu_r, store) in rollers:
            q = np.stack([np.full(len(p), rx), np.clip(p[:, 1], y0, y1), np.full(len(p), rz)], axis=1)
            diffp = p - q
            dax = np.sqrt(np.einsum("ij,ij->i", diffp, diffp))
            hit = np.where((dax - rr < R) & (dax > 1e-9))[0]
            if len(hit):
                n_ = diffp[hit] / dax[hit][:, None]
                surf = us * np.stack([n_[:, 2], np.zeros(len(hit)), -n_[:, 0]], axis=1)
                contact(n_, R - (dax[hit] - rr), surf, np.full(len(hit), mu_r), ids[hit], F, Tq, store)
        # FUEL on FUEL
        dd = p[:, None, :] - p[None, :, :]
        dn = np.sqrt(np.einsum("ijk,ijk->ij", dd, dd))
        i_, j_ = np.where(np.triu(dn < 2 * R, 1))
        if len(i_):
            n_ = dd[i_, j_] / dn[i_, j_][:, None]
            pen = (2 * R - dn[i_, j_]) / 2          # two surfaces in series: each takes half
            gi, gj = ids[i_], ids[j_]
            vc = (vel[gi] + np.cross(om[gi], -n_ * R)) - (vel[gj] + np.cross(om[gj], n_ * R))
            vn = np.einsum("ij,ij->i", vc, n_)
            Fn = np.maximum(0.0, k * pen - c * vn)
            vt = vc - vn[:, None] * n_
            vtm = np.sqrt(np.einsum("ij,ij->i", vt, vt) + eps * eps)
            Ft = -(mu_ball * Fn / vtm)[:, None] * vt
            Fij = Fn[:, None] * n_ + Ft
            np.add.at(F, gi, Fij); np.add.at(F, gj, -Fij)
            np.add.at(Tq, gi, np.cross(-n_ * R, Ft)); np.add.at(Tq, gj, np.cross(n_ * R, -Ft))
            # force toward the flywheel on each FUEL from the FUEL around it, smoothed over 20 ms
            np.add.at(push, gi, -Fij[:, 0]); np.add.at(push, gj, Fij[:, 0])
        push_f += (push - push_f) * dt / 0.02
        for ln in lanes:
            if ln["mode"] == "staged" and ln["ball"] is not None:
                peak_push = max(peak_push, float(push_f[ln["ball"]]))
        spring = fresh
        vel[ids] += F[ids] / mass * dt
        om[ids] += Tq[ids] / inertia * dt
        pos[ids] += vel[ids] * dt
        t += dt; step += 1
        # taken by the flywheel, or out of the robot
        for li, ln in enumerate(lanes):
            b_ = ln["ball"]
            if ln["mode"] == "feeding" and b_ is not None and pos[b_, 0] <= TAKE_X:
                if alive[b_]:
                    alive[b_] = False
                    delivered.append(dict(t=round(t, 4), lane="left" if li == 0 else "right"))
                    last_take = t
                ln["mode"], ln["ball"] = "staging", None
        early = alive & (pos[:, 0] <= TAKE_X)
        if early.any():   # reached the wheel with no feed commanded
            for b_ in np.where(early)[0]:
                alive[b_] = False
                delivered.append(dict(t=round(t, 4), lane="left" if pos[b_, 1] > 0 else "right", uncommanded=True, yMm=round(float(pos[b_, 1]) * 1000), modes=[ln["mode"] for ln in lanes], sinceFeedS=round(t - last_feed, 3)))
                for ln in lanes:
                    if ln["ball"] == b_:
                        ln["mode"], ln["ball"] = "staging", None
            last_take = t
        # A FUEL that comes forward over the back plate drops into the chute, between the belt and the back plate, which
        # holds it (20 mm squeeze); the running belt lifts it and the roller throws it back in with the capture state,
        # 0.4 s later. An arriving FUEL waits in the chute the same way while the place it would be thrown to is taken.
        # (With the open throat of the earlier issue the same holds for the pinch against the bumper face.)
        fell = alive & ~held & (pos[:, 0] > PINCH_X) & (pos[:, 2] < PINCH_Z)
        for b_ in np.where(fell)[0]:
            held[b_] = True
            pos[b_] = (0.5, float(np.clip(pos[b_, 1], -0.18, 0.18)), 5.0 + 0.5 * b_); vel[b_] = 0; om[b_] = 0
            if intake > 0:
                pending.append((max(t, 0.0) + 0.4, b_))
        for due, b_ in [q for q in pending if q[0] <= t]:
            spot = np.array([throw[0], pos[b_, 1], throw[1]])
            free = alive & ~held
            if free.any() and np.min(np.linalg.norm(pos[free] - spot, axis=1)) < 2 * R + 0.004:
                continue                  # the throat is occupied: the pinch holds this one until it clears
            pending.remove((due, b_)); held[b_] = False
            if b_ >= n - arrive and b_ not in [q[1] for q in entered]:
                entered.append((round(t, 3), int(b_)))
            else:
                recirculated += 1
            pos[b_] = spot; vel[b_] = (throw[2], 0.0, throw[3]); om[b_] = (0.0, throw[4], 0.0)
        vel[held] = 0; om[held] = 0; pos[held, 2] = 5.0 + 0.5 * np.where(held)[0]
        out = alive & ~held & ((pos[:, 2] < 0.0) | (pos[:, 0] > 0.60) | (np.abs(pos[:, 1]) > (D.HALF_W - 20) * MM) | (pos[:, 2] > 1.5))
        if out.any():
            where += [[round(t, 2)] + [round(float(v) * 1000) for v in pos[b_]] for b_ in np.where(out)[0]]
            lost += int(out.sum()); alive[out] = False
        if keep_frames and t >= next_frame - 1e-9:
            frames.append([round(t, 3)] + [[round(float(v), 4) for v in pos[i]] if alive[i] and not held[i] else None for i in range(n)])
            next_frame += frames_every
    good = [d_ for d_ in delivered if not d_.get("uncommanded")]
    f0 = feed_from or 0.0
    within12 = sum(1 for d_ in good if d_["t"] - f0 <= 12.0)
    last = round(good[-1]["t"] - f0, 4) if good else None
    inside = int((alive & ~held).sum())
    need = math.ceil(n * 22 / 24)
    unmet = None
    if lost:
        unmet = f"{lost} FUEL left the hopper"
    elif any(d_.get("uncommanded") for d_ in delivered):
        unmet = "a FUEL reached the flywheel with no feed commanded"
    elif feed_from is None:
        if int(held.sum()) > CHUTE_HOLDS:
            unmet = (f"{inside} FUEL in the hopper and {int(held.sum())} left in the chute after {t_end:g} s: more than the {CHUTE_HOLDS} the chute holds"
                     if chute else f"{inside} FUEL in the hopper and {int(held.sum())} back in the intake pinch after {t_end:g} s")
    elif within12 < min(need, 22):
        unmet = f"{within12} FUEL reached the flywheel in 12 s, fewer than {min(need, 22)}"
    elif len(good) < n:
        unmet = f"{n - len(good)} FUEL still in the hopper after {t_end:g} s"
    ok = unmet is None
    rate = None if not good or last <= 0 else round(len(good) / last, 3)
    return dict(name=name, kind="hopper", passed=ok,
                metric=(dict(name="FUEL in the hopper", value=inside,
                             requirement=f"all {arrive} arriving FUEL are carried after {t_end:g} s: in the hopper, or at most {CHUTE_HOLDS} waiting in the chute; none lost and none at the flywheel")
                        if feed_from is None else
                        dict(name="FUEL fed to the flywheel in 12 s", value=within12,
                             requirement=f"at least {min(need, 22)} of {n} fed on command within 12 s of the first feed command, every one fed in the end, none lost and none uncommanded")),
                firstUnmet=unmet,
                imposed=((f"{n - arrive} FUEL dropped as a heap and settled for {settle_s} s; " if n - arrive else "")
                         + (f"{arrive} FUEL arrive through the intake, one every {1 / arrive_rate:g} s, each thrown over the lip with the capture state when the throat is clear; " if arrive else "")
                         + ("no feed is commanded; " if feed_from is None else f"feed commands from {feed_from:g} s; ")
                         + "".join(f"robot acceleration ({ax:g}, {ay:g}) g from {a0:g} to {a1:g} s; " for a0, a1, ax, ay in accel or ())
                         + f"floor belt surface {belt} m/s toward the feeders; each lane's feeder "
                         f"roller {F_['stage_mps']} m/s to the stage beam, stopped while staged, {F_['mps']} m/s on a feed command; the belt stops while both lanes are staged and held; intake top roller {intake} m/s; one feed per {period} s at "
                         f"most, lanes in turn; belt reversed 0.3 s after 1 s without a feed" + ("" if tilt_deg == 0 else f"; robot rolled {tilt_deg:g} degrees")),
                solved="every FUEL's translation and spin in three dimensions with penalty contact and Coulomb friction against the hopper, the rollers and each other",
                feed=dict(arrived=len(entered), lastArrivalS=entered[-1][0] if entered else None, inHopper=inside, fed=len(good), within12s=within12, peakPushOnStagedN=round(peak_push, 1), lastFedS=last, ratePerS=rate, unjamCycles=unjams, lost=lost, recirculated=recirculated, firstStallS=first_stall, lostAt=where,
                          uncommanded=sum(1 for d_ in delivered if d_.get("uncommanded")), uncommandedAt=[d_ for d_ in delivered if d_.get("uncommanded")], remaining=int(alive.sum()), heldInChute=int(held.sum()),
                          remainingAtMm=[[round(float(v) * 1000) for v in pos[i]] for i in range(n) if alive[i] and not held[i]],
                          byLane={q: sum(1 for d_ in good if d_["lane"] == q) for q in ("left", "right")}, times=[d_["t"] for d_ in good]),
                params=dict(n=n, seed=seed, belt=belt, periodS=period, muBall=mu_ball, muBelt=mu_belt, muHard=mu_hard, muFeeder=mu_feeder, k=k, zeta=zeta,
                            mass=mass, crr=crr, dt=dt, settleS=settle_s, tiltDeg=tilt_deg, layout=dict(opt or {}), reverse=reverse,
                            feeders=feeders, muDeck=mu_deck, stick=stick, arrive=arrive, arriveRate=arrive_rate, feedFrom=feed_from, beltIdle=belt_idle, unjam=list(unjam), nudge=list(nudge),
                            accel=[list(a) for a in accel or ()]),
                hopper=dict(rects=[[*[round(float(v), 4) for v in S["O"][i]], *[round(float(v), 4) for v in S["U"][i]], *[round(float(v), 4) for v in S["V"][i]], S["label"][i]]
                                   for i in range(len(S["label"]))] if keep_frames else [],
                            feeder=[fx, fz, fr], takeX=TAKE_X, radius=R),
                contacts={}, events=[dict(t=d_["t"], event=f"FUEL {i + 1} fed from the {d_['lane']} lane" + (" (uncommanded)" if d_.get("uncommanded") else ""))
                                     for i, d_ in enumerate(delivered)],
                frames=frames)


THROAT_THROW = (0.340, 0.266, -1.17, -0.46, 24.0)   # the earlier issue's capture state, low over the bumper top
SUPERSEDED = dict(floor="guides", wall_x=-28.0, divider=True, divider_dims=dict(x1=40.0), front="throat")
OPEN_THROAT = dict(front="throat", throat_ramp=188.0, front_x=170.0, shelf_x0_right=-93.0)   # the two-lane trough fed through an open throat


TRANSIT = lambda g: [(7.0, 7.4, -g, 0.0), (7.8, 8.2, g, 0.0), (8.6, 9.0, 0.0, g)]   # a stop, a start and a turn at g
CYCLE = dict(n=24, arrive=24, feed_from=10.0, t_end=26.0)


def run_trials(only=None, throw=None):
    """The hopper trials. A cycle collects 24 FUEL through the intake chute, holds them through a loaded stop, start
    and turn, then feeds them all: nominal, timestep, fifteen more arrival patterns, controls that remove one feature
    each, and brackets. throw is the acquisition trial's capture state."""
    cyc = lambda g=0.5, **kw: dict(dict(CYCLE, accel=TRANSIT(g)), **kw)
    specs = [
        ("hopper-cycle-nominal", cyc(keep_frames=True)),
        ("hopper-cycle-nominal-half-step", cyc(dt=1e-4)),
        *[(f"hopper-cycle-pattern-{i}", cyc(seed=i)) for i in range(2, 17)],
        ("hopper-cycle-open-throat-low-entry (control: the earlier issue's fill)", cyc(opt=OPEN_THROAT, throw=THROAT_THROW, nudge=(0.0, 0.3))),
        ("hopper-cycle-superseded-flat-floor-open-throat (control)", cyc(opt=SUPERSEDED, throw=THROAT_THROW, nudge=(0.0, 0.3), belt=0.6)),
        ("hopper-cycle-regularized-friction-law (control for the law)", cyc(stick=False)),
        ("hopper-cycle-belt-runs-while-staged (cause isolation)", cyc(belt_idle=False)),
        ("hopper-cycle-1g-pattern-2-no-nudge (cause isolation)", cyc(1.0, seed=2, nudge=(0.0, 0.3))),
        ("hopper-cycle-1g-pattern-2", cyc(1.0, seed=2)),
        ("hopper-cycle-1g-pattern-3 (adverse)", cyc(1.0, seed=3)),
        ("hopper-cycle-0.75g-pattern-3", cyc(0.75, seed=3)),
        ("hopper-cycle-full-height-divider (cause isolation)", cyc(opt=dict(divider=True))),
        ("hopper-cycle-no-unjam-reverse", cyc(reverse=False)),
        ("hopper-cycle-belt-0.6mps", cyc(belt=0.6)),
        ("hopper-cycle-belt-0.3mps", cyc(belt=0.3)),
        ("hopper-cycle-ball-friction-0.4", cyc(mu_ball=0.4)),
        ("hopper-cycle-ball-friction-1.0", cyc(mu_ball=1.0)),
        ("hopper-cycle-ball-friction-1.3", cyc(mu_ball=1.3)),
        ("hopper-cycle-wall-friction-0.6", cyc(mu_hard=0.6)),
        ("hopper-cycle-wall-friction-0.8", cyc(mu_hard=0.8)),
        ("hopper-cycle-period-0.5s", cyc(period=0.5, t_end=30.0)),
        ("hopper-cycle-arrivals-8-per-s", cyc(arrive_rate=8.0)),
        ("hopper-cycle-rolled-10deg (adverse)", cyc(tilt_deg=10.0)),
        ("hopper-cycle-8-preload", cyc(n=8, arrive=8)),
        ("hopper-collect-24-hold", dict(n=24, arrive=24, feed_from=None, t_end=12.0, accel=TRANSIT(0.5))),
        ("hopper-collect-27-hold", dict(n=27, arrive=27, feed_from=None, t_end=12.0)),
        ("hopper-collect-30-hold", dict(n=30, arrive=30, feed_from=None, t_end=12.0)),
        ("hopper-feed-dropped-heap", dict()),
        ("hopper-feed-dropped-heap-pattern-2", dict(seed=2)),
    ]
    specs = [(name, dict(kw, throw=kw.get("throw", throw))) for name, kw in specs if only is None or name in only]
    try:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=8) as pool:
            return list(pool.map(_one, specs))
    except (ImportError, OSError):
        return [_one(q) for q in specs]


def _one(spec):
    return feed(spec[0], **spec[1])


if __name__ == "__main__":
    import time
    names = sys.argv[1:]
    t0 = time.time()
    for tr in (run_trials() if not names else [feed("probe", **eval("dict(%s)" % a)) for a in names]):
        f = tr["feed"]
        print(f"{tr['name']:62s} {'PASS' if tr['passed'] else 'FAIL'} in hopper {f['inHopper']} chute {f['heldInChute']} fed {f['fed']} in12 {f['within12s']} last {f['lastFedS']} rate {f['ratePerS']} "
              f"push {f['peakPushOnStagedN']} N unjams {f['unjamCycles']} recirc {f['recirculated']} lost {f['lost']} uncommanded {f['uncommanded']}  {tr['firstUnmet'] or ''} [{time.time() - t0:.0f}s]", flush=True)
