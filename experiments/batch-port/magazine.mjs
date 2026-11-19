import {readFile, writeFile} from 'node:fs/promises';

import {box, clamp, integrate, mass, pair, radius, state} from './contact.mjs';
import {liftCircuit} from './lift.mjs';
import {createReceiver} from './receiver.mjs';

const [output, ...args] = process.argv.slice(2);
if (!output)
  throw Error(
      'Usage: node magazine.mjs OUTPUT [seconds] [dt] [stock belt m/s] [lift m/s] [follower force N]');
const [duration = 12, dt = .0005, floorSpeed = 1.25, liftSpeed = .65, maxPush = 6, carriers = 4, tiered = 0, recoveryNm = -1, axialFaceShiftM = 0, frontShimMm = 0] =
    args.map(Number);
const manifest = JSON.parse(
    await readFile(new URL('../../cad/own-zone-upper/appearances.json', import.meta.url), 'utf8'));
const solids = Object.fromEntries(manifest.solids.map(p => [p.id, p.boundsMm.map(v => v / 1000)]));
const zero = [0, 0, 0];
const shape = (id, a, c, surface = zero, mu = .25) => ({id, a, c, surface, mu});
const ys = [-.237, -.079, .079, .237];
const walls = [shape('back wall', [-.334, -.320, .230], [-.330, .320, .553])];
for (const y of [-.317, -.158, 0, .158, .317])
  walls.push(shape('lane divider', [-.330, y - .001, .231], [.149, y + .001, .550]));
if (tiered)
  walls.push(shape('upper cartridge roof', [-.330, -.317, .546], [.152, .317, .550], zero, .2));
const balls = [];
for (let lane = 0; lane < 4; lane++) {
  for (const x of [-.251, -.097, .057])
    for (const z of [.235 + radius, .239 + 3 * radius]) {
      balls.push({
        id: 'M' + lane + '-' + String(balls.length + 1).padStart(2, '0'),
        lane,
        tier: z > .4 ? 1 : 0,
        x,
        y: ys[lane],
        z,
        vx: 0,
        vy: 0,
        vz: 0,
        wx: 0,
        wy: 0,
        wz: 0,
        maxPen: 0
      });
    }
}
const arrivals = [], transfers = [], starts = [], exits = [], lost = [], moves = [],
      forces = Array(4).fill(0);
const lift = liftCircuit(.215, .622, carriers, carriers !== 4);
const receiver = createReceiver(solids, Math.max(0, recoveryNm), axialFaceShiftM);
const planes = [], releases = [];
const original = balls.map(b => state(b, 0)), frames = [];
const sweeps = Array.from({length: tiered ? 8 : 4}, () => ({x: -.330, v: 0}));
const tierChange = Array(4).fill(null);
let lane = 0, transition = null, carY = ys[0], carSpeed = 0;
for (let k = 0; k <= Math.round(duration / dt); k++) {
  const t = k * dt;
  if (!transition && lane < 3 && balls.filter(b => b.lane === lane).every(b => b.done)) {
    transition = {start: t, from: carY, to: ys[lane + 1]};
    moves.push({departS: t, fromLane: lane, toLane: lane + 1});
  }
  if (transition) {
    const travel = transition.to - transition.from, acc = 4, half = Math.sqrt(travel / acc),
          clock = t - transition.start;
    if (clock >= 2 * half) {
      lane++;
      carY = ys[lane];
      carSpeed = 0;
      moves.at(-1).arrivedS = t;
      transition = null;
    } else {
      carY = clock <= half ? transition.from + .5 * acc * clock ** 2 :
                             transition.to - .5 * acc * (2 * half - clock) ** 2;
      carSpeed = acc * Math.min(clock, 2 * half - clock);
    }
  }
  if (tiered && !transition && tierChange[lane] === null &&
      balls.filter(b => b.lane === lane && b.tier === 1).every(b => b.done))
    tierChange[lane] = t;
  const upper = tiered && tierChange[lane] === null;
  const retract = tiered && !upper ? clamp((t - tierChange[lane]) / .19, 0, 1) : 0;
  const lowerReady = !tiered || (!upper && retract >= 1);
  const surfaces = [...walls], follower = [];
  for (let j = 0; j < 4; j++) {
    const selected = j === lane && !transition;
    const y = ys[j], lo = y - .078, hi = y + .078;
    // Inactive cartridges shut their forward exit. The active lower throat meters the bottom layer.
    if (!tiered)
      surfaces.push(shape('gate ' + j, [.148, lo, selected ? .398 : .235], [.152, hi, .550]));
    else {
      if (!selected || !lowerReady)
        surfaces.push(shape('lower row stop', [.148, lo, .235], [.152, hi, .386]));
      if (!selected || !upper)
        surfaces.push(shape('upper row stop', [.148, lo, .389], [.152, hi, .547]));
      surfaces.push(shape(
          'upper driven deck', [-.330, lo, .387], [.149, hi, .389],
          [selected && upper ? floorSpeed : 0, 0, 0], .7));
    }
    surfaces.push(shape(
        'belt ' + j, [-.330, lo, .230], [.149, hi, .235],
        [selected && lowerReady ? floorSpeed : 0, 0, 0], .70));
    const s = sweeps[j];
    follower.push(shape(
        'follower ' + j, [s.x - .004, lo + .002, .236], [s.x, hi - .002, .370], [s.v, 0, 0], .22));
  }
  if (tiered && retract < 1)
    surfaces.push(shape(
        'upper withdrawing tongue', [.148 - .155 * retract, carY - .056, .383],
        [.303 - .155 * retract, carY + .056, .389], [upper ? floorSpeed : -.155 / .19, carSpeed, 0],
        .65));
  surfaces.push(shape(
      'powered transfer tongue', [.148, carY - .056, .229], [.303, carY + .056, .235],
      [floorSpeed, carSpeed, 0], .65));
  for (const id
           of ['front lift custody guide', 'left front elevator upright',
               'right front elevator upright', 'left rear elevator upright',
               'right rear elevator upright']) {
    const b = solids[id];
    if (id === 'front lift custody guide' && frontShimMm > 0)
      surfaces.push(shape(
          'upper centering liner', [b[0] - frontShimMm / 1000, b[1] + carY, .488],
          [b[0], b[4] + carY, b[5]], [0, carSpeed, 0], .20));
    surfaces.push(shape(
        id, [b[0], b[1] + carY, Math.max(.217, b[2])], [b[3], b[4] + carY, b[5]],
        [0, carSpeed, 0]));
  }
  if (tiered)
    surfaces.push(shape(
        'upper transfer backstop', [.167, carY - .065, .548], [.171, carY + .065, .687],
        [0, carSpeed, 0], .20));
  if (upper)
    surfaces.push(shape(
        'lower rear guide', [.167, carY - .065, .226], [.171, carY + .065, .385], [0, carSpeed, 0],
        .20));
  else
    surfaces.push(shape(
        'upper rear guide', [.167, carY - .065, .398], [.171, carY + .065, .550], [0, carSpeed, 0],
        .20));
  for (const z of lift.topHeights(t, liftSpeed, .271)) {
    for (const side of ['left', 'right']) {
      const q = solids[side + ' lift shelf 1'];
      surfaces.push(shape(
          'rising shelf ' + side, [q[0], q[1] + carY, z - .006], [q[3], q[4] + carY, z],
          [0, carSpeed, liftSpeed], .6));
    }
  }
  const free = balls.filter(b => !b.done);
  receiver.begin();
  for (const b of free) {
    b.fx = b.fy = b.mx = b.my = b.mz = 0;
    b.fz = -mass * 9.80665;
    for (const p of surfaces) box(b, p);
    if (recoveryNm >= 0) receiver.contact(b, carY, t);
  }
  for (let j = 0; j < 4; j++) {
    const s = sweeps[j], active = j === lane && !transition && lowerReady;
    let reaction = 0;
    const crownX = Math.min(.141, s.x);
    const crown = shape(
        'upper follower ' + j, [crownX - .004, ys[j] - .076, .370], [crownX, ys[j] + .076, .549],
        [s.x < .141 ? s.v : 0, 0, 0], .22);
    for (const b of free) {
      const f = b.fx;
      box(b, follower[j]);
      if (!tiered) box(b, crown);
      reaction += b.fx - f;
    }
    if (tiered) {
      const u = sweeps[j + 4], engaged = j === lane && !transition && upper;
      const face = shape(
          'upper tier follower', [u.x - .004, ys[j] - .076, .390], [u.x, ys[j] + .076, .539],
          [u.v, 0, 0], .22);
      let load = 0;
      for (const b of free) {
        const before = b.fx;
        box(b, face);
        load += b.fx - before;
      }
      u.v = engaged ? clamp(u.v + (maxPush - load - 12 * u.v) / .45 * dt, -.10, .70) : 0;
      u.x = clamp(u.x + u.v * dt, -.330, .174);
    }
    forces[j] = Math.max(forces[j], reaction);
    const driven = active ? maxPush : 0;
    s.v = active ? clamp(s.v + (driven - reaction - 12 * s.v) / .45 * dt, -.10, .70) : 0;
    s.x = clamp(s.x + s.v * dt, -.330, .174);
  }
  for (let i = 0; i < free.length; i++)
    for (let j = i + 1; j < free.length; j++) pair(free[i], free[j]);
  if (recoveryNm >= 0) receiver.advance(dt);
  for (const b of free) {
    const priorZ = b.z;
    if (b.release) {
      releases.push(
          {...state(b, t), receiverY: carY, firstContact: b.headTouch, release: b.release});
      b.done = true;
      continue;
    }
    integrate(b, dt);
    if (priorZ < .540 && b.z >= .540 && b.vz > 0) planes.push({...state(b, t), receiverY: carY});
    if (!b.advanced && b.vx > .05 && b.lane === lane) {
      b.advanced = true;
      starts.push(state(b, t));
    }
    if (!b.mouth && b.x >= .149) {
      b.mouth = true;
      arrivals.push(state(b, t));
    }
    if (!b.passed && b.x - radius >= .171 && b.z > .235) {
      b.passed = true;
      transfers.push(state(b, t));
    }
    if (!b.exited && b.passed && b.z >= .540 && b.vz > 0) {
      b.exited = true;
      if (recoveryNm < 0) b.done = true;
      exits.push({...state(b, t), receiverY: carY});
    }
    if (!b.done && (b.z < 0 || b.z > .85 || b.x > .65 || Math.abs(b.y) > .46)) {
      b.done = true;
      lost.push(state(b, t));
    }
  }
  if (k % Math.round(.05 / dt) === 0)
    frames.push([
      Number(t.toFixed(4)), carY,
      ...free.map(b => [b.id, ...[b.x, b.y, b.z].map(p => Number(p.toFixed(4)))])
    ]);
}
const result = {
  source: 'R2C and proposed four-lane indexing receiver, handoff-only comparison',
  baseStepSha256: manifest.sourceSha256,
  original,
  duration,
  dt,
  floorSpeed,
  liftSpeed,
  maxPush,
  tiered,
  frontShimMm,
  carriers,
  circuitM: lift.length,
  planes,
  releases,
  receiver: receiver.summary(),
  starts,
  arrivals,
  transfers,
  exits,
  lost,
  moves,
  forces,
  maxPenetrationM: Math.max(...balls.map(b => b.maxPen)),
  frames
};
await writeFile(output, JSON.stringify(result) + '\n');
console.log({
  arrivals: arrivals.length,
  transfers: transfers.length,
  thresholds: exits.length,
  upward: planes.length,
  releaseCount: releases.length,
  lost: lost.length,
  moves,
  clearTimes: exits.map(b => +b.timeS.toFixed(2))
});
