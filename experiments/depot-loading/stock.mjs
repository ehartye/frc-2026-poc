// Centered front DEPOT approach with every registered ground piece on the same clock.
import {readFile, writeFile} from 'node:fs/promises';

import {box, clamp, contact, integrate, mass, pair, radius, state} from '../batch-port/contact.mjs';

import {createDock} from './cartridge.mjs';
import {pairedDock} from './paired.mjs';

const [sourcePath, out, which = 'blue-depot-03', mode = 'reach', step = '0.000125'] =
    process.argv.slice(2);
if (!sourcePath || !out ||
    !['reach', 'stalled', 'fixed', 'load', 'load-stalled-belt', 'load-locked-gate', 'paired',
      'paired-locked-gate']
         .includes(mode))
  throw Error('Usage: node stock.mjs REGISTER OUTPUT [id] [pickup or loading mode] [dt]');
const source = JSON.parse(await readFile(sourcePath, 'utf8'));
const cad = JSON.parse(
    await readFile(new URL('../../cad/own-zone-upper/appearances.json', import.meta.url)));
const native = Object.fromEntries(cad.solids.map(p => [p.id, p.boundsMm.map(v => v / 1000)]));
const dt = Number(step), zero = [0, 0, 0];
const original = source.floorStock.find(r => r.id === which);
if (!original) throw Error('Unknown registered stock ID');
const wide = mode.startsWith('paired');
const refY = original.centerMm[1] / 1000 + (wide ? .0762 : 0);
const stock = source.floorStock.map(r => ({
                                      id: r.id,
                                      x: source.centerXM - r.centerMm[0] / 1000,
                                      y: refY - r.centerMm[1] / 1000,
                                      z: r.centerMm[2] / 1000,
                                      vx: 0,
                                      vy: 0,
                                      vz: 0,
                                      wx: 0,
                                      wy: 0,
                                      wz: 0,
                                      maxPen: 0
                                    }));
const dock = wide ?
    pairedDock({locked: mode === 'paired-locked-gate'}) :
    mode.startsWith('load') ?
    createDock({reverse: mode !== 'load-stalled-belt', locked: mode === 'load-locked-gate'}) :
    null;
if (dock) stock.push(...dock.initial());
const observed = stock.find(r => r.id === which), initial = stock.map(b => state(b, 0));
const targetX = Math.min(.605, observed.x + .060);
const shape = (id, a, c, mu = .35, surface = zero) => ({id, a, c, mu, surface});
const cadShape = id => {
  const s = shape(id, native[id].slice(0, 3), native[id].slice(3));
  if (wide && (/front bumper|front return/.test(id))) {
    if (id.startsWith('left'))
      s.a[1] = .184;
    else
      s.c[1] = -.184;
  }
  return s;
};
const rail = source.frontTubeBoundsMm;
const shapes = [shape(
    'front steel', [source.centerXM - rail[3] / 1000, refY - rail[4] / 1000, 0],
    [source.centerXM - rail[0] / 1000, refY - rail[1] / 1000, rail[5] / 1000])];
for (const side of source.sideTubeBoundsMm)
  shapes.push(shape(
      'side steel', [source.centerXM - side[3] / 1000, refY - side[4] / 1000, 0],
      [source.centerXM - side[0] / 1000, refY - side[1] / 1000, side[5] / 1000]));
for (const id
         of ['left blue front bumper', 'right blue front bumper', 'left front return',
             'right front return', 'front deck crossmember', 'rear lift custody gate',
             'front lift custody guide', 'central fore-aft feed deck'])
  if (!dock ||
      !['rear lift custody gate', 'front lift custody guide', 'central fore-aft feed deck']
           .includes(id))
    shapes.push(cadShape(id));
const initialHits = [];
const coords = [], touches = new Map(), settled = [], handoffs = [];
let shelfStart = null;
function ramp(b, y) {
  const x0 = .213, z0 = .048, x1 = mode === 'fixed' ? .337 : .402,
        z1 = mode === 'fixed' ? .015 : .035;
  const len = Math.hypot(x1 - x0, z1 - z0), ux = (x1 - x0) / len, uz = (z1 - z0) / len;
  const dx = b.x - x0, dz = b.z - z0;
  const u = clamp(dx * ux + dz * uz, 0, len), v = clamp(-dx * uz + dz * ux, -.0025, .0025);
  return sphereSurface(
      b, [x0 + u * ux - v * uz, clamp(b.y, y - .014, y + .014), z0 + u * uz + v * ux], zero, .28,
      2500, 10);
}
function sphereSurface(b, q, s, mu, k, damping) {
  const n = [b.x - q[0], b.y - q[1], b.z - q[2]];
  const d = Math.hypot(...n);
  if (d >= radius || d < 1e-9) return false;
  contact(b, n[0] / d, n[1] / d, n[2] / d, radius - d, ...s, mu, k, damping);
  return true;
}
function roller(t) {
  if (mode === 'fixed')
    return [
      .275 + .103 * Math.cos(-39 * Math.PI / 180), .240 + .103 * Math.sin(-39 * Math.PI / 180), 0, 0
    ];
  const poses = [
    [0, targetX, .233], [.25, targetX, .155], [.92, .336, .159], [1.12, .336, .159],
    [1.40, .330, .302]
  ];
  for (let i = 1; i < poses.length; i++) {
    const [a, x0, z0] = poses[i - 1], [b, x1, z1] = poses[i];
    if (t > b) continue;
    const f = (t - a) / (b - a), s = f * f * (3 - 2 * f), v = 6 * f * (1 - f) / (b - a);
    return [x0 + (x1 - x0) * s, z0 + (z1 - z0) * s, (x1 - x0) * v, (z1 - z0) * v];
  }
  return [.330, .302, 0, 0];
}
function rollerContact(b, pose) {
  const [cx, cz, cxv, czv] = pose, rx = b.x - cx, rz = b.z - cz;
  const radial = Math.hypot(rx, rz), f = Math.min(1, .038 / Math.max(1e-9, radial));
  const dx = rx * f, dz = rz * f, spin = mode === 'stalled' ? 0 : 1.25 / .038;
  return sphereSurface(
      b, [cx + dx, clamp(b.y, wide ? -.165 : -.126, wide ? .165 : .126), cz + dz],
      [cxv + spin * dz, 0, czv - spin * dx], .65, 2500, 10);
}
const duration = dock ? 8.0 : 2.5;
for (let step = 0; step <= Math.round(duration / dt); step++) {
  const t = step * dt, pose = roller(t);
  const elapsed = shelfStart == null ? 0 : t - shelfStart;
  const maximum = dock?.targetLift ?? .49;
  const lift = clamp((elapsed - .23) * .65, 0, maximum),
        rate = lift > 0 && lift < maximum ? .65 : 0;
  if (wide) {
    for (const b of stock) dock.advance(t, lift, b);
  } else
    dock?.advance(t, lift, observed);
  for (const b of stock) {
    b.fx = b.fy = b.mx = b.my = b.mz = 0;
    b.fz = -mass * 9.80665;
    contact(b, 0, 0, 1, radius - b.z, 0, 0, 0, .55, 2500, 10);
    for (const surface of shapes) box(b, surface);
    dock?.contacts(b, t, lift);
    if (wide) {
      for (const y of [-.1362, -.0162, .0162, .1362]) ramp(b, y);
      dock.shelves(b, lift, rate, t);
    } else
      for (const sign of [-1, 1]) {
        ramp(b, sign * .060);
        const y = sign * .081 + (dock?.carY ?? 0);
        box(b, shape('shelf', [.196, y - .009, .066 + lift], [.292, y + .009, .072 + lift], .6, [
              dock?.shelfVelocity() ?? 0, dock?.carV ?? 0, rate
            ]));
      }
    if (rollerContact(b, pose) && !touches.has(b.id)) touches.set(b.id, t);
    if (!step && b.maxPen > .001) initialHits.push([b.id, b.maxPen]);
  }
  for (let i = 0; i < stock.length; i++)
    for (let j = 0; j < i; j++) pair(stock[i], stock[j]);
  for (const b of stock) {
    const prev = b.z;
    integrate(b, dt);
    if ((wide ? Math.abs(Math.abs(b.y) - .0762) < .054 : Math.abs(b.y) < .065) && b.x < .280 &&
        b.x > .190 && Math.abs(b.vx) < .1 && b.z > .078 && b.z < .15 &&
        !settled.some(s => s.id === b.id)) {
      settled.push(state(b, t));
      shelfStart ??= t;
    }
    if (b.x > .165 && b.x < .335 && Math.abs(b.y) < .070 && prev < .540 && b.z >= .540)
      handoffs.push(state(b, t));
  }
  if (step % Math.round(.025 / dt) === 0)
    coords.push([
      +t.toFixed(4),
      ...stock.filter(b => Math.abs(b.y) < .24)
          .map(b => [b.id, ...[b.x, b.y, b.z].map(v => +v.toFixed(4))])
    ]);
}
const result = {
  dt,
  mode,
  source: which,
  centerYFieldM: refY,
  initial,
  initialHits,
  firstRollerTouch: Object.fromEntries(touches),
  settled,
  handoffs,
  final: stock.map(b => state(b, duration)),
  cartridge: dock?.status(stock),
  coords
};
await writeFile(out, JSON.stringify(result) + '\n');
console.log({
  which,
  mode,
  cartridge: result.cartridge,
  initialHits,
  roller: [...touches.keys()],
  settled: settled.map(s => s.id),
  handoffs: handoffs.map(s => s.id)
});
