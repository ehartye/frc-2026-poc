// Express robot-only contacts in the pitched chassis frame and return forces to
// horizontal axes.
export function localBody(b, frame) {
  if (!frame) return b;
  const {cos: c, sin: s, height, dz, omega, cog} = frame;
  const x = c * b.x + s * (b.z - height - cog),
        z = -s * b.x + c * (b.z - height - cog);
  return {
    ...b,
    x,
    z: z + cog,
    vx: c * b.vx + s * (b.vz - dz) + omega * z,
    vz: -s * b.vx + c * (b.vz - dz) - omega * x,
    wx: c * b.wx + s * b.wz,
    wy: b.wy + omega,
    wz: -s * b.wx + c * b.wz,
    fx: 0,
    fy: 0,
    fz: 0,
    mx: 0,
    my: 0,
    mz: 0
  };
}
export function accumulate(world, local, frame) {
  if (!frame) return;
  const {cos: c, sin: s} = frame;
  world.fx += c * local.fx - s * local.fz;
  world.fz += s * local.fx + c * local.fz;
  world.fy += local.fy;
  world.mx += c * local.mx - s * local.mz;
  world.mz += s * local.mx + c * local.mz;
  world.my += local.my;
  world.maxPen = Math.max(world.maxPen, local.maxPen);
}
export function supportAt(run, t) {
  const dt = run.trace[1][0] - run.trace[0][0],
        i = Math.max(0, Math.min(run.trace.length - 2, Math.floor(t / dt)));
  const a = run.trace[i], b = run.trace[i + 1],
        u = Math.max(0, Math.min(1, (t - a[0]) / dt));
  const v = a.map((n, k) => n + u * (b[k] - n));
  return {
    x: v[1],
    height: v[2],
    cos: Math.cos(v[3]),
    sin: Math.sin(v[3]),
    vx: v[4],
    dz: v[5],
    omega: v[6],
    ax: (b[4] - a[4]) / dt,
    cog: run.cogM
  };
}
