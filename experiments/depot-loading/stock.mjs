// Centered front DEPOT approach with every registered ground piece on the same
// clock.
import {readFile, writeFile} from 'node:fs/promises';

import {box, clamp, contact, integrate, mass, pair, radius, state} from '../batch-port/contact.mjs';

import {ramp,rollerContact} from './intake-contacts.mjs';
import {createDock} from './cartridge.mjs';
import {accumulate, localBody} from './chassis-frame.mjs';
import {pairedDock} from './paired.mjs';
import {sequenceDock} from './sequence.mjs';
import {crossing} from './wheel-crossing.mjs';

const [sourcePath, out, which = 'blue-depot-03', mode = 'reach', step = '0.000125'] =
    process.argv.slice(2);
if (!sourcePath || !out ||
    !['reach', 'stalled', 'fixed', 'load', 'load-stalled-belt',
      'load-locked-gate', 'paired', 'paired-locked-gate', 'paired-series',
      'paired-overlap', 'paired-early', 'paired-rail', 'paired-wheel',
      'paired-wheel-low', 'paired-wheel-high', 'paired-wheel-timed', 'paired-wheel-field']
         .includes(mode))
  throw Error(
      'Usage: node stock.mjs REGISTER OUTPUT [id] [pickup or loading mode] [dt]');
const source = JSON.parse(await readFile(sourcePath, 'utf8'));
const cad = JSON.parse(await readFile(
    new URL('../../cad/own-zone-upper/appearances.json', import.meta.url)));
const native = Object.fromEntries(
    cad.solids.map(p => [p.id, p.boundsMm.map(v => v / 1000)]));
const dt = Number(step), zero = [0, 0, 0];
if (!Number.isFinite(dt) || dt <= 0 || dt > .001)
  throw Error('Choose a positive contact step no greater than one millisecond.');
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
const wheelRun = mode.startsWith('paired-wheel') ?
    crossing(
        mode.endsWith('low')      ? {mass: 68, mu: .6, currentA: 40} :
            mode.endsWith('high') ? {mass: 53, mu: 1, currentA: 60} :
                                    {}) :
    null;
const sequence =
    [
      'paired-series', 'paired-overlap', 'paired-early', 'paired-rail',
      'paired-wheel', 'paired-wheel-low', 'paired-wheel-high',
      'paired-wheel-timed', 'paired-wheel-field'
    ].includes(mode) ?
    sequenceDock(source, {
      overlap: mode !== 'paired-series',
      early: mode === 'paired-early' || mode === 'paired-rail' || !!wheelRun,
      straight: mode === 'paired-rail' || !!wheelRun,
      wheel: wheelRun,
      quick: mode === 'paired-wheel-timed' || mode === 'paired-wheel-field'
    }) :
    null;
const dock = sequence ??
    (wide ? pairedDock({locked: mode === 'paired-locked-gate'}) :
         mode.startsWith('load') ? createDock({
           reverse: mode !== 'load-stalled-belt',
           locked: mode === 'load-locked-gate'
         }) :
                                   null);
if (dock) stock.push(...dock.initial());
const observed = stock.find(r => r.id === which),
      initial = stock.map(b => state(b, 0));
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
      'side steel',
      [source.centerXM - side[3] / 1000, refY - side[4] / 1000, 0], [
        source.centerXM - side[0] / 1000, refY - side[1] / 1000, side[5] / 1000
      ]));
for (const id
         of ['left blue front bumper', 'right blue front bumper',
             'left front return', 'right front return',
             'front deck crossmember', 'rear lift custody gate',
             'front lift custody guide', 'central fore-aft feed deck'])
  if (!dock ||
      !['rear lift custody gate', 'front lift custody guide',
        'central fore-aft feed deck']
           .includes(id))
    shapes.push(cadShape(id));
if (sequence)
  for (const name
           of ['left blue side bumper', 'right blue side bumper',
               'rear blue bumper', 'left perimeter tube',
               'right perimeter tube', 'rear perimeter tube'])
    shapes.push(cadShape(name));
let closestWheel = {gapM: Infinity};
const wheelBoxes =
    Object.entries(native)
        .filter(([id]) => id.endsWith('public wheel'))
        .map(([id, q]) => ({
               id,
               x: (q[0] + q[3]) / 2,
               y: (q[1] + q[4]) / 2,
               z: (q[2] + q[5]) / 2,
               enclosingRadius: Math.hypot((q[3] - q[0]) / 2, (q[4] - q[1]) / 2)
             }));
const initialHits = [];
const coords = [], touches = new Map(), settled = [], handoffs = [];
let shelfStart = null;
function roller(t) {
  if (mode === 'fixed')
    return [
      .275 + .103 * Math.cos(-39 * Math.PI / 180),
      .240 + .103 * Math.sin(-39 * Math.PI / 180), 0, 0
    ];
  const poses = [
    [0, targetX, .233], [.25, targetX, .155], [.92, .336, .159],
    [1.12, .336, .159], [1.40, .330, .302]
  ];
  for (let i = 1; i < poses.length; i++) {
    const [a, x0, z0] = poses[i - 1], [b, x1, z1] = poses[i];
    if (t > b) continue;
    const f = (t - a) / (b - a), s = f * f * (3 - 2 * f),
          v = 6 * f * (1 - f) / (b - a);
    return [
      x0 + (x1 - x0) * s, z0 + (z1 - z0) * s, (x1 - x0) * v, (z1 - z0) * v
    ];
  }
  return [.330, .302, 0, 0];
}
const duration = sequence ? 42 : dock ? 8.0 : 2.5;
const baseObstacles = shapes.slice(0, 3).map(s => ({a: [...s.a], c: [...s.c]}));
const custody = [];
const boundedField = mode === 'paired-wheel-field';
const wallX = Math.min(...source.sideTubeBoundsMm.map(q=>q[0])) / 1000;
let previousPose = [source.centerXM,refY], previousVelocity = [0,0];
let minimumStockWallGapM = Infinity;
const wallContacts = new Map();
for (let step = 0; step <= Math.round(duration / dt); step++) {
  const t = step * dt;
  sequence?.tick(
      t,
      sequence.support ? stock.map(b => localBody(b, sequence.support)) :
                         stock);
  const pose = sequence?.roller ?? roller(t);
  if (sequence) {
    if (boundedField) {
      // Transport each body through the exact attained change of translational frame.
      for (const b of stock) {
        b.x += sequence.pose[0]-previousPose[0]-previousVelocity[0]*dt;
        b.y += sequence.pose[1]-previousPose[1]-previousVelocity[1]*dt;
        b.vx += sequence.velocity[0]-previousVelocity[0];
        b.vy += sequence.velocity[1]-previousVelocity[1];
      }
      previousPose = [...sequence.pose];
      previousVelocity = [...sequence.velocity];
    }
    const d = [sequence.pose[0] - source.centerXM, sequence.pose[1] - refY];
    for (let i = 0; i < 3; i++) {
      for (let axis = 0; axis < 2; axis++) {
        shapes[i].a[axis] = baseObstacles[i].a[axis] + d[axis];
        shapes[i].c[axis] = baseObstacles[i].c[axis] + d[axis];
      }
      shapes[i].surface = [...sequence.velocity, 0];
    }
    if (step % Math.round(1 / dt) === 0)
      custody.push([t, sequence.cargo(stock)]);
  }
  const elapsed = shelfStart == null ? 0 : t - shelfStart;
  const maximum = dock?.targetLift ?? .49;
  const lift = clamp((elapsed - .23) * .65, 0, maximum),
        rate = lift > 0 && lift < maximum ? .65 : 0;
  if (!sequence) {
    if (wide) {
      for (const b of stock) dock.advance(t, lift, b);
    } else
      dock?.advance(t, lift, observed);
  }
  for (const world of stock) {
    let b = world;
    b.fx = b.fy = b.mx = b.my = b.mz = 0;
    b.fz = -mass * 9.80665;
    const velocity = sequence?.velocity ?? zero;
    if (sequence && !boundedField) {
      b.fx += mass * sequence.acceleration[0];
      b.fy += mass * sequence.acceleration[1];
    }
    contact(
        b, 0, 0, 1, radius - b.z, velocity[0], velocity[1], 0, .55, 2500, 10);
    for (const surface of shapes.slice(0, 3)) box(b, surface);
    if (boundedField) {
      const gap = sequence.pose[0] - b.x - wallX - radius;
      minimumStockWallGapM = Math.min(minimumStockWallGapM,gap);
      if (gap < 0) {
        if (!wallContacts.has(b.id)) wallContacts.set(b.id,t);
        contact(b,-1,0,0,-gap,velocity[0],velocity[1],0,.30,10000,20);
      }
    }
    const attitude = sequence?.support;
    if (attitude) b = localBody(world, attitude);
    if (sequence && b.z < .2) {
      for (const w of wheelBoxes) {
        const gap = Math.hypot(w.x - b.x, w.y - b.y, w.z - b.z) -
            w.enclosingRadius - radius;
        if (gap < closestWheel.gapM)
          closestWheel = {id: b.id, wheel: w.id, timeS: t, gapM: gap};
      }
    }
    for (const surface of shapes.slice(3)) box(b, surface);
    dock?.contacts(b, t, lift);
    if (wide) {
      for (const y of [-.1362, -.0162, .0162, .1362]) ramp(b, y, mode === 'fixed');
      if (!sequence) dock.shelves(b, lift, rate, t);
    } else
      for (const sign of [-1, 1]) {
        ramp(b, sign * .060, mode === 'fixed');
        const y = sign * .081 + (dock?.carY ?? 0);
        box(b,
            shape(
                'shelf', [.196, y - .009, .066 + lift],
                [.292, y + .009, .072 + lift], .6,
                [dock?.shelfVelocity() ?? 0, dock?.carV ?? 0, rate]));
      }
    if (rollerContact(b, pose, wide, mode === 'stalled') && !touches.has(b.id)) touches.set(b.id, t);
    if (attitude) accumulate(world, b, attitude);
    if (!step && b.maxPen > .001) initialHits.push([b.id, b.maxPen]);
  }
  for (let i = 0; i < stock.length; i++)
    for (let j = 0; j < i; j++) pair(stock[i], stock[j]);
  for (const b of stock) {
    const prev = b.z;
    integrate(b, dt);
    if ((wide ? Math.abs(Math.abs(b.y) - .0762) < .054 :
                Math.abs(b.y) < .065) &&
        b.x < .280 && b.x > .190 && Math.abs(b.vx) < .1 && b.z > .078 &&
        b.z < .15 && !settled.some(s => s.id === b.id)) {
      settled.push(state(b, t));
      shelfStart ??= t;
    }
    if (b.x > .165 && b.x < .335 && Math.abs(b.y) < .070 && prev < .540 &&
        b.z >= .540)
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
  closestWheel: sequence ? closestWheel : null,
  wheel: wheelRun,
  quick: mode === 'paired-wheel-timed' ? {
    mass: wheelRun.mass,
    mu: wheelRun.mu,
    currentA: wheelRun.currentA,
    stableS: wheelRun.stableS,
    endM: wheelRun.endM,
    maximum: wheelRun.maximum
  } :
                                         null,
  fieldBoundary: boundedField ? {wallX,minimumStockWallGapM,wallContacts:[...wallContacts]} : null,
  firstRollerTouch: Object.fromEntries(touches),
  settled,
  handoffs,
  final: stock.map(b => state(b, duration)),
  cartridge: dock?.status(stock),
  custody,
  coords
};
await writeFile(out, JSON.stringify(result) + '\n');
console.log({
  which,
  mode,
  cartridge: sequence ? {
    index: result.cartridge.index,
    stage: result.cartridge.stage,
    cargo: result.cartridge.cargo,
    rows: result.cartridge.rows.map(r => [r.closedS, r.sourceIds])
  } :
                        result.cartridge,
  initialHits,
  roller: [...touches.keys()],
  settled: settled.map(s => s.id),
  handoffs: handoffs.map(s => s.id)
});
