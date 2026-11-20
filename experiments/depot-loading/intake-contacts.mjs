import {clamp, contact, radius} from '../batch-port/contact.mjs';
const zero = [0, 0, 0];
export function ramp(b, y, fixed = false) {
  const x0 = .213, z0 = .048, x1 = fixed ? .337 : .402,
        z1 = fixed ? .015 : .035;
  const len = Math.hypot(x1 - x0, z1 - z0), ux = (x1 - x0) / len,
        uz = (z1 - z0) / len;
  const dx = b.x - x0, dz = b.z - z0;
  const u = clamp(dx * ux + dz * uz, 0, len),
        v = clamp(-dx * uz + dz * ux, -.0025, .0025);
  return sphereSurface(
      b,
      [
        x0 + u * ux - v * uz, clamp(b.y, y - .014, y + .014),
        z0 + u * uz + v * ux
      ],
      zero, .28, 2500, 10);
}
function sphereSurface(b, q, s, mu, k, damping) {
  const n = [b.x - q[0], b.y - q[1], b.z - q[2]];
  const d = Math.hypot(...n);
  if (d >= radius || d < 1e-9) return false;
  contact(b, n[0] / d, n[1] / d, n[2] / d, radius - d, ...s, mu, k, damping);
  return true;
}
export function rollerContact(b, pose, wide, stalled = false) {
  const [cx, cz, cxv, czv] = pose, rx = b.x - cx, rz = b.z - cz;
  const radial = Math.hypot(rx, rz),
        f = Math.min(1, .038 / Math.max(1e-9, radial));
  const dx = rx * f, dz = rz * f, spin = stalled ? 0 : 1.25 / .038;
  return sphereSurface(
      b,
      [cx + dx, clamp(b.y, wide ? -.165 : -.126, wide ? .165 : .126), cz + dz],
      [cxv + spin * dz, 0, czv - spin * dx], .65, 2500, 10);
}
