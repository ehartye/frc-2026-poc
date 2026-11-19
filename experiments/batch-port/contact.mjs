// SI rigid foam spheres with compliant normals and regularized Coulomb friction.
export const radius = .150114 / 2, mass = .215, inertia = .4 * mass * radius ** 2;
export const norm = (a, b, c) => Math.sqrt(a * a + b * b + c * c);
export const clamp = (v, lo, hi) => Math.max(lo, Math.min(v, hi));

function apply(b, nx, ny, nz, fx, fy, fz, arm = -radius) {
  b.fx += fx;
  b.fy += fy;
  b.fz += fz;
  b.mx += arm * (ny * fz - nz * fy);
  b.my += arm * (nz * fx - nx * fz);
  b.mz += arm * (nx * fy - ny * fx);
}
export function contact(
    b, nx, ny, nz, depth, sx, sy, sz, friction, stiffness = 10000, damping = 20) {
  if (depth <= 0) return;
  const ux = b.vx - radius * (b.wy * nz - b.wz * ny) - sx;
  const uy = b.vy - radius * (b.wz * nx - b.wx * nz) - sy;
  const uz = b.vz - radius * (b.wx * ny - b.wy * nx) - sz;
  const vn = ux * nx + uy * ny + uz * nz;
  const normal = Math.max(0, stiffness * depth - damping * vn);
  const tx = ux - nx * vn, ty = uy - ny * vn, tz = uz - nz * vn;
  const slip = norm(tx, ty, tz);
  const factor = -friction * normal * Math.tanh(slip / .035) / Math.max(slip, 1e-12);
  const fx = normal * nx + tx * factor, fy = normal * ny + ty * factor,
        fz = normal * nz + tz * factor;
  apply(b, nx, ny, nz, fx, fy, fz);
  b.maxPen = Math.max(b.maxPen, depth);
  return [fx, fy, fz];
}
export function box(b, shape) {
  const {a, c, surface, mu} = shape;
  const x = b.x - clamp(b.x, a[0], c[0]), y = b.y - clamp(b.y, a[1], c[1]),
        z = b.z - clamp(b.z, a[2], c[2]);
  const ds = x * x + y * y + z * z;
  if (ds >= radius ** 2) return;
  if (ds < 1e-14) {
    const offsets = [b.x - a[0], c[0] - b.x, b.y - a[1], c[1] - b.y, b.z - a[2], c[2] - b.z];
    const i = offsets.indexOf(Math.min(...offsets));
    const n = [0, 0, 0];
    n[Math.floor(i / 2)] = i % 2 ? 1 : -1;
    contact(b, ...n, radius + offsets[i], ...surface, mu);
    return;
  }
  const d = Math.sqrt(ds);
  contact(b, x / d, y / d, z / d, radius - d, ...surface, mu);
}
export function pair(a, b) {
  const dx = a.x - b.x, dy = a.y - b.y, dz = a.z - b.z, ds = dx * dx + dy * dy + dz * dz;
  if (ds >= 4 * radius ** 2) return;
  const d = Math.max(1e-9, Math.sqrt(ds)), nx = dx / d, ny = dy / d, nz = dz / d;
  const sx = b.vx + radius * (b.wy * nz - b.wz * ny), sy = b.vy + radius * (b.wz * nx - b.wx * nz),
        sz = b.vz + radius * (b.wx * ny - b.wy * nx);
  const f = contact(a, nx, ny, nz, 2 * radius - d, sx, sy, sz, .35, 9000, 16);
  if (f) apply(b, nx, ny, nz, -f[0], -f[1], -f[2], radius);
}
export function integrate(b, dt) {
  b.vx += b.fx / mass * dt;
  b.vy += b.fy / mass * dt;
  b.vz += b.fz / mass * dt;
  b.wx += b.mx / inertia * dt;
  b.wy += b.my / inertia * dt;
  b.wz += b.mz / inertia * dt;
  b.x += b.vx * dt;
  b.y += b.vy * dt;
  b.z += b.vz * dt;
}
export function state(b, t) {
  return {
    id: b.id,
    timeS: t,
    positionM: [b.x, b.y, b.z],
    velocityMps: [b.vx, b.vy, b.vz],
    spinRadS: [b.wx, b.wy, b.wz]
  };
}
