"""Batch trial for the R3 hopper: free FUEL as spheres in three dimensions, from a settled heap to the two feeders.

Every FUEL is a free body with penalty contact and regularized Coulomb friction against the hopper surfaces, the
feeder rollers and each other (explicit semi-implicit Euler, the same contact law as field_trials.py). The floor
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
TAKE_X = (D.frame_constants()["c"][0] + 53.7) * MM    # FUEL centre where it first touches the flywheel: taken by the wheel


def surfaces(belt_mps, opt=None):
    """The hopper as rectangles (origin, edge u, edge v, surface velocity, friction class, label), in metres.
    opt overrides the layout for a control or a comparison: wall_x (rear wall face), floor ("trough" or "guides" or "open"),
    shelf_deg, divider (bool)."""
    opt = dict(opt or {})
    K = D.frame_constants()
    H = D.HOPPER
    bt, pan, wall = K["belt_top"], K["floor"], K["wall"]
    hw = D.HALF_W - 24.0                       # hopper side wall inner face: 333 mm
    wx = opt.get("wall_x", D.REAR_WALL_X[1])
    gate_z = K["z0"] + D.R_BALL + 7
    lane = opt.get("lane_half", H["lane_half"])
    floor = opt.get("floor", H["floor"])
    shelf_z = opt.get("shelf_z", H["shelf_z"])
    rise = (hw - lane) * math.tan(math.radians(opt.get("shelf_deg", H["shelf_deg"])))
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
    if opt.get("divider", True):
        dv = dict(H["divider"], **opt.get("divider_dims", {}))
        gate_z_div = bt + dv.get("h", gate_z - bt)
        for y in (-dv["half_t"], dv["half_t"]):
            rect((D.LANE_DECK["x0"], y, bt + 2), (dv["x1"] - D.LANE_DECK["x0"], 0, 0), (0, 0, gate_z_div - bt - 2), "lane divider")
        rect((dv["x1"], -dv["half_t"], bt + 2), (0, 2 * dv["half_t"], 0), (0, 0, gate_z_div - bt - 2), "lane divider")
        rect((D.LANE_DECK["x0"], -dv["half_t"], gate_z_div), (dv["x1"] - D.LANE_DECK["x0"], 0, 0), (0, 2 * dv["half_t"], 0), "lane divider")
    rect((f["x0"], -min(180, lane), bt), (f["x1"] - f["x0"], 0, 0), (0, 2 * min(180, lane), 0), "floor belt front", "belt", (-belt_mps, 0, 0))
    rect((D.FLOOR_PAN["x0"], -hw, pan), (D.FLOOR_PAN["x1"] - D.FLOOR_PAN["x0"], 0, 0), (0, 2 * hw, 0), "floor pan")
    rect((D.FLOOR_TONGUE["x0"], -183, pan), (D.FLOOR_TONGUE["x1"] - D.FLOOR_TONGUE["x0"], 0, 0), (0, 366, 0), "floor pan front tongue")
    L = D.FRONT_LIP
    for s in (1, -1):
        side = "left" if s > 0 else "right"
        rect((-340, s * hw, pan), (680, 0, 0), (0, 0, wall - pan), "hopper wall " + side)
        rect((337, min(s * 260, s * hw), 125), (0, hw - 260, 0), (0, 0, wall - 125), "hopper front corner wall " + side)
        rect((-143, s * 173, pan), (143 + min(wx, D.FEEDER["x"] + 40), 0, 0), (0, 0, 320), "shooter side plate " + side)
        if floor == "bin":
            # straight walls two lanes apart for the whole height: nothing converges
            rect((wx, s * lane, pan), (337 - wx, 0, 0), (0, 0, wall - pan), "hopper wall " + side)
        elif floor == "trough":
            # a two-lane channel the whole length of the floor. Aft of the stowed intake a shelf slopes up from it to the
            # side wall; under the stowed intake a low shelf slopes up to a cheek wall
            fx_, fz_, cheek, fr_ = H["front_x"], H["front_shelf_z"], H["cheek_y"], H["front_rise"]
            rect((wx, s * lane, pan), (fx_ - wx, 0, 0), (0, 0, shelf_z - pan), "hopper channel wall " + side)
            rect((wx, s * lane, shelf_z), (fx_ - wx, 0, 0), (0, s * (hw - lane), rise), "hopper shelf " + side)
            rect((fx_, min(s * lane, s * hw), fz_), (0, hw - lane, 0), (0, 0, shelf_z + rise - fz_), "hopper shelf " + side)
            rect((fx_, s * lane, pan), (337 - fx_, 0, 0), (0, 0, fz_ - pan), "hopper channel wall " + side)
            rect((fx_, s * lane, fz_), (337 - fx_, 0, 0), (0, s * (cheek - lane), fr_), "hopper front shelf " + side)
            rect((fx_, s * cheek, fz_), (470 - fx_, 0, 0), (0, 0, wall - fz_), "hopper cheek " + side)
        else:
            box((185, min(s * (185 + D.DY), s * (312 + D.DY)), 80), (312, max(s * (185 + D.DY), s * (312 + D.DY)), 125), "module body", "zxy" if s > 0 else "zxY")
            rect((wx, min(s * lane, s * hw), pan), (0, hw - lane, 0), (0, 0, gate_z - pan), "hopper rear wall")
    # rear wall: a one-FUEL-high gate across the lanes
    rect((wx, -hw, gate_z), (0, 2 * hw, 0), (0, 0, wall - gate_z), "hopper rear wall")
    # front: lip, bumper-top shelf, the deployed intake closing the throat, upper wall
    rect((L["x0"], -183, L["z0"]), (0, 366, 0), (0, 0, L["z1"] - L["z0"]), "front lip")
    rect((L["x0"], -183, L["z1"]), (L["x1"] - L["x0"], 0, 0), (0, 366, 0), "front lip")
    B = D.BUMPER
    rect((L["x1"], -260, D.FRONT_RAIL["z1"]), (B["x0"] - L["x1"], 0, 0), (0, 520, 0), "frame rail front")
    rect((B["x0"], -260, D.FRONT_RAIL["z1"]), (0, 520, 0), (0, 0, B["z1"] - D.FRONT_RAIL["z1"]), "bumper front")
    rect((B["x0"], -260, B["z1"]), (B["x1"] - B["x0"], 0, 0), (0, 520, 0), "bumper front")
    ramp = opt.get("throat_ramp", H["throat_ramp"])
    if ramp:   # a plate over the bumper top and rail that slopes down aft to the lip, so nothing rests in the throat
        rect((L["x0"], -260, L["z1"]), (B["x1"] - L["x0"], 0, ramp - L["z1"]), (0, 520, 0), "throat ramp")
    rect((311, -282 - D.DY, 482), (0, 564 + 2 * D.DY, 0), (0, 0, wall - 482), "hopper front upper wall")
    tc = H["throat_cover"]
    rect((311, -260, 482), (tc[0] - 311, 0, tc[1] - 482), (0, 520, 0), "throat cover")
    if floor not in ("trough", "bin"):
        box(D.BATTERY_BOX[0], D.BATTERY_BOX[1], "battery", "zxXy")
        box(D.PANEL_RIGHT[0], D.PANEL_RIGHT[1], "electronics panel", "zXY")
    if floor == "guides":
        for (a, b), name in zip(H["guides"], ("left", "right")):
            rect((a[0], a[1], pan), (b[0] - a[0], b[1] - a[1], 0), (0, 0, wall - pan), "hopper lane guide " + name)
    O = np.array([r[0] for r in rects], float) * MM
    U = np.array([r[1] for r in rects], float) * MM
    V = np.array([r[2] for r in rects], float) * MM
    return dict(O=O, U=U, V=V, vel=np.array([r[3] for r in rects], float), kind=[r[4] for r in rects], label=[r[5] for r in rects], floor=floor)


def posts():
    """Vertical cylinders: module motors and climber tubes (x, y, r, z0, z1) in metres."""
    out = []
    for sy in (1, -1):
        out.append((265 * MM, sy * (265 + D.DY) * MM, 32 * MM, 0.127, 0.215))
        out.append((300 * MM, sy * (299 + D.DY) * MM, 15 * MM, 0.224, 0.634))
    return out


def heap(n, seed, trough, jitter=0.008):
    """n FUEL on a loose lattice above the floor, dropped together."""
    rng = np.random.default_rng(seed)
    xs, ys = (0.055, 0.222), ((-0.082, 0.082) if trough else (-0.200, -0.035, 0.130))
    pts = []
    layer = 0
    while len(pts) < n:
        for x in xs:
            for y in ys:
                if len(pts) < n:
                    pts.append((x, y, 0.200 + 0.156 * layer))
        layer += 1
    return np.array(pts) + rng.uniform(-jitter, jitter, (n, 3))


def feed(name, n=24, seed=1, belt=None, period=None, mu_ball=0.7, mu_belt=0.9, mu_hard=0.4, mu_feeder=0.9, k=15000.0, zeta=0.3, mass=0.215,
         crr=0.03, dt=2e-4, settle_s=1.5, t_end=16.0, tilt_deg=0.0, opt=None, reverse=True, feeders=True,
         mu_deck=0.6, intake=None, frames_every=0.04,
         keep_frames=False):
    """Heap of n FUEL to the flywheel. After the heap settles the belts run and the two lane feeders stage and feed in
    turn, no faster than one feed per period. If nothing reaches the flywheel for 1 s while FUEL remain, the belt
    reverses for 0.3 s (an unjam cycle, counted). tilt_deg rolls gravity toward the right wall."""
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
    intake = D.INTAKE["belt_mps"] if intake is None else intake
    sensor = F_["sensor_x"] * MM
    c = 2 * zeta * math.sqrt(k * mass)
    inertia = 0.4 * mass * R * R
    tilt = math.radians(tilt_deg)
    grav = np.array([0.0, -G * math.sin(tilt), -G * math.cos(tilt)])
    pos = heap(n, seed, S["floor"] in ("trough", "bin"))
    vel = np.zeros((n, 3)); om = np.zeros((n, 3))
    alive = np.ones(n, bool)
    P = posts()
    eps = 0.01
    lanes = [dict(mode="staging", ball=None), dict(mode="staging", ball=None)]
    delivered, unjams, last_feed, last_take, last_lane = [], 0, -1e9, 0.0, 1
    reverse_until, first_stall = -1.0, None
    frames, t, step = [], -settle_s, 0
    lost, recirculated, pending, where = 0, 0, [], []
    PINCH_X = (D.BUMPER["x1"] + 45.0) * MM
    next_frame = 0.0

    def contact(n_, pen, surf_v, mu, idx, F, Tq):
        """Accumulate penalty and friction forces for contacts on balls idx with normals n_ (surface to ball)."""
        r_ = -n_ * R
        vc = vel[idx] + np.cross(om[idx], r_) - surf_v
        vn = np.einsum("ij,ij->i", vc, n_)
        Fn = np.maximum(0.0, k * pen - c * vn)
        vt = vc - vn[:, None] * n_
        vtm = np.sqrt(np.einsum("ij,ij->i", vt, vt) + eps * eps)
        Ft = -(mu * Fn / vtm)[:, None] * vt
        np.add.at(F, idx, Fn[:, None] * n_ + Ft)
        w = om[idx]
        wm = np.sqrt(np.einsum("ij,ij->i", w, w) + 0.2 ** 2)
        np.add.at(Tq, idx, np.cross(r_, Ft) - (crr * Fn * R / wm)[:, None] * w)

    while t < t_end and alive.any():
        running = t >= 0.0
        if running and reverse and t - max(last_take, 0.0) > 1.0 and t > reverse_until + 1.0:
            reverse_until = t + 0.3; unjams += 1
            first_stall = round(t, 3) if first_stall is None else first_stall
        vb = 0.0 if not running else (-0.5 * belt if t < reverse_until else belt)
        # lane controller: stage to the beam, hold, feed on the scheduler's command
        uf = [0.0, 0.0]
        if running and feeders:
            for li, ln in enumerate(lanes):
                y0, y1 = lane_y[li]
                inl = np.where(alive & (pos[:, 1] * (1 if li == 0 else -1) > 0) & (pos[:, 0] < sensor + 0.060) & (pos[:, 2] < K["belt_top"] * MM + R + 0.03))[0]
                lead = inl[np.argmin(pos[inl, 0])] if len(inl) else None
                if ln["mode"] == "staging" and lead is not None and pos[lead, 0] <= sensor:
                    ln["mode"], ln["ball"] = "staged", lead
                if ln["mode"] == "staged" and (lead is None or pos[lead, 0] > sensor + 0.02):
                    ln["mode"], ln["ball"] = "staging", None       # the staged FUEL was pushed back out
                uf[li] = dict(staging=F_["stage_mps"], staged=0.0, feeding=F_["mps"])[ln["mode"]]
            if t - last_feed >= period and not any(ln["mode"] == "feeding" for ln in lanes):
                order = [1 - last_lane, last_lane]
                for li in order:
                    if lanes[li]["mode"] == "staged":
                        lanes[li]["mode"] = "feeding"; last_feed, last_lane = t, li
                        uf[li] = F_["mps"]
                        break
        F = np.tile(grav * mass, (n, 1)); Tq = np.zeros((n, 3))
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
            contact(n_, R - dist[bi, mi], S["vel"][mi] * vb, mu_s[mi], ids[bi], F, Tq)
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
        rollers = [(fx, fz, fr, y0, y1, uf[li], mu_feeder) for li, (y0, y1) in enumerate(lane_y)] if feeders else []
        rollers.append((ir[0], ir[1], ir[2], -0.258, 0.258, intake if running else 0.0, mu_belt))
        for (rx, rz, rr, y0, y1, us, mu_r) in rollers:
            q = np.stack([np.full(len(p), rx), np.clip(p[:, 1], y0, y1), np.full(len(p), rz)], axis=1)
            diffp = p - q
            dax = np.sqrt(np.einsum("ij,ij->i", diffp, diffp))
            hit = np.where((dax - rr < R) & (dax > 1e-9))[0]
            if len(hit):
                n_ = diffp[hit] / dax[hit][:, None]
                surf = us * np.stack([n_[:, 2], np.zeros(len(hit)), -n_[:, 0]], axis=1)
                contact(n_, R - (dax[hit] - rr), surf, np.full(len(hit), mu_r), ids[hit], F, Tq)
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
        vel[ids] += F[ids] / mass * dt
        om[ids] += Tq[ids] / inertia * dt
        pos[ids] += vel[ids] * dt
        t += dt; step += 1
        # taken by the flywheel, or out of the robot
        for li, ln in enumerate(lanes):
            b_ = ln["ball"]
            if ln["mode"] == "feeding" and b_ is not None and pos[b_, 0] <= TAKE_X:
                alive[b_] = False
                delivered.append(dict(t=round(t, 4), lane="left" if li == 0 else "right"))
                last_take = t
                ln["mode"], ln["ball"] = "staging", None
        early = alive & (pos[:, 0] <= TAKE_X)
        if early.any():   # reached the wheel with no feed commanded
            for b_ in np.where(early)[0]:
                alive[b_] = False
                delivered.append(dict(t=round(t, 4), lane="left" if pos[b_, 1] > 0 else "right", uncommanded=True))
                for ln in lanes:
                    if ln["ball"] == b_:
                        ln["mode"], ln["ball"] = "staging", None
            last_take = t
        # a FUEL that rolls forward off the bumper top drops into the intake pinch: the running intake lifts it and throws
        # it back in with the acquisition trial's capture state; with the intake stopped it falls to the carpet
        fell = alive & (pos[:, 0] > PINCH_X) & (pos[:, 2] < 0.30)
        for b_ in np.where(fell)[0]:
            if running and intake > 0:
                pos[b_] = (0.5, float(np.clip(pos[b_, 1], -0.18, 0.18)), 5.0 + 0.5 * len(pending)); vel[b_] = 0; om[b_] = 0
                pending.append((t + 0.4, b_))
            else:
                alive[b_] = False; lost += 1
        for due, b_ in [q for q in pending if q[0] <= t]:
            pending.remove((due, b_)); recirculated += 1
            pos[b_] = (0.340, pos[b_, 1], 0.266); vel[b_] = (-1.17, 0.0, -0.46); om[b_] = (0.0, 24.0, 0.0)
        parked = np.zeros(n, bool); parked[[q[1] for q in pending]] = True
        vel[parked] = 0; pos[parked, 2] = 5.0 + 0.5 * np.arange(parked.sum())
        out = alive & ~parked & ((pos[:, 2] < 0.0) | (pos[:, 0] > 0.60) | (np.abs(pos[:, 1]) > (D.HALF_W - 20) * MM) | (pos[:, 2] > 1.5))
        if out.any():
            where += [[round(t, 2)] + [round(float(v) * 1000) for v in pos[b_]] for b_ in np.where(out)[0]]
            lost += int(out.sum()); alive[out] = False
        if keep_frames and t >= next_frame - 1e-9:
            frames.append([round(t, 3)] + [[round(float(v), 4) for v in pos[i]] if alive[i] else None for i in range(n)])
            next_frame += frames_every
    good = [d_ for d_ in delivered if not d_.get("uncommanded")]
    within12 = sum(1 for d_ in good if d_["t"] <= 12.0)
    last = good[-1]["t"] if good else None
    need = math.ceil(n * 22 / 24)
    unmet = None
    if lost:
        unmet = f"{lost} FUEL left the hopper"
    elif any(d_.get("uncommanded") for d_ in delivered):
        unmet = "a FUEL reached the flywheel with no feed commanded"
    elif within12 < min(need, 22):
        unmet = f"{within12} FUEL reached the flywheel in 12 s, fewer than {min(need, 22)}"
    elif len(good) < n:
        unmet = f"{n - len(good)} FUEL still in the hopper after {t_end:g} s"
    ok = unmet is None
    rate = None if not good or last <= 0 else round(len(good) / last, 3)
    return dict(name=name, kind="hopper", passed=ok,
                metric=dict(name="FUEL fed to the flywheel in 12 s", value=within12,
                            requirement=f"at least {min(need, 22)} of {n} fed on command within 12 s, every one fed in the end, none lost and none uncommanded"),
                firstUnmet=unmet,
                imposed=(f"{n} FUEL dropped as a heap and settled for {settle_s} s; then floor belt surface {belt} m/s toward the feeders; each lane's feeder "
                         f"roller {F_['stage_mps']} m/s to the stage beam, stopped while staged, {F_['mps']} m/s on a feed command; intake top roller {intake} m/s; one feed per {period} s at "
                         f"most, lanes in turn; belt reversed 0.3 s after 1 s without a feed" + ("" if tilt_deg == 0 else f"; robot rolled {tilt_deg:g} degrees")),
                solved="every FUEL's translation and spin in three dimensions with penalty contact and Coulomb friction against the hopper, the rollers and each other",
                feed=dict(fed=len(good), within12s=within12, lastFedS=last, ratePerS=rate, unjamCycles=unjams, lost=lost, recirculated=recirculated, firstStallS=first_stall, lostAt=where,
                          uncommanded=sum(1 for d_ in delivered if d_.get("uncommanded")), remaining=int(alive.sum()),
                          byLane={q: sum(1 for d_ in good if d_["lane"] == q) for q in ("left", "right")}, times=[d_["t"] for d_ in good]),
                params=dict(n=n, seed=seed, belt=belt, periodS=period, muBall=mu_ball, muBelt=mu_belt, muHard=mu_hard, muFeeder=mu_feeder, k=k, zeta=zeta,
                            mass=mass, crr=crr, dt=dt, settleS=settle_s, tiltDeg=tilt_deg, layout=dict(opt or {}), reverse=reverse,
                            feeders=feeders, muDeck=mu_deck),
                hopper=dict(rects=[[*[round(float(v), 4) for v in S["O"][i]], *[round(float(v), 4) for v in S["U"][i]], *[round(float(v), 4) for v in S["V"][i]], S["label"][i]]
                                   for i in range(len(S["label"]))] if keep_frames else [],
                            feeder=[fx, fz, fr], takeX=TAKE_X, radius=R),
                contacts={}, events=[dict(t=d_["t"], event=f"FUEL {i + 1} fed from the {d_['lane']} lane" + (" (uncommanded)" if d_.get("uncommanded") else ""))
                                     for i, d_ in enumerate(delivered)],
                frames=frames)


def run_trials():
    return [
        feed("hopper-feed-nominal", keep_frames=True),
        feed("hopper-feed-nominal-half-step", dt=1e-4),
        feed("hopper-feed-seed-2", seed=2),
        feed("hopper-feed-seed-3", seed=3),
        feed("hopper-feed-superseded-flat-floor-with-guides (control)", opt=dict(floor="guides", wall_x=-28.0)),
        feed("hopper-feed-no-unjam-reverse (control)", reverse=False),
        feed("hopper-feed-ball-friction-0.4", mu_ball=0.4),
        feed("hopper-feed-ball-friction-1.0", mu_ball=1.0),
        feed("hopper-feed-wall-friction-0.6", mu_hard=0.6),
        feed("hopper-feed-period-0.5s", period=0.5),
        feed("hopper-feed-30-tilted-10deg (adverse)", n=30, tilt_deg=10.0),
        feed("hopper-feed-8-preload", n=8),
    ]


if __name__ == "__main__":
    import time
    names = sys.argv[1:]
    t0 = time.time()
    for tr in (run_trials() if not names else [feed("probe", **eval("dict(%s)" % a)) for a in names]):
        f = tr["feed"]
        print(f"{tr['name']:48s} {'PASS' if tr['passed'] else 'FAIL'} fed {f['fed']} in12 {f['within12s']} last {f['lastFedS']} rate {f['ratePerS']} "
              f"unjams {f['unjamCycles']} stall@{f['firstStallS']} recirc {f['recirculated']} lost {f['lost']} uncommanded {f['uncommanded']} lanes {f['byLane']}  {tr['firstUnmet'] or ''} {f['lostAt']} [{time.time() - t0:.0f}s]")
