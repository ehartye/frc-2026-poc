import {createHash} from 'node:crypto';
import {readFile, writeFile} from 'node:fs/promises';

import {box, clamp, integrate, mass, pair, radius, state} from './contact.mjs';
import {liftCircuit} from './lift.mjs';

const [mode, output, ...options] = process.argv.slice(2);
if (!output ||
    !['fixed', 'split', 'belts-off', 'bridge', 'diagonal', 'alternate', 'sweep', 'lanes', 'indexed',
      'phased']
         .includes(mode))
  throw Error('Usage: node port.mjs MODE OUTPUT [seconds] [dt] [floor m/s] [shelf m/s]');
const [duration = 12, dt = .0005, floorSpeed = .8, liftSpeed = .318] = options.map(Number);
const raw = await readFile(new URL('../../cad/own-zone-upper/appearances.json', import.meta.url));
const native = JSON.parse(raw);
const by = new Map(native.solids.map(p => [p.id, p.boundsMm.map(q => q / 1000)]));
const zero = [0, 0, 0];
function shape(id, a, c, surface = zero, mu = .3) {
  return {id, a, c, surface, mu};
}
function from(id, surface, mu) {
  const q = by.get(id);
  if (!q) throw Error(id);
  return shape(id, q.slice(0, 3), q.slice(3), surface, mu);
}
const decks = ['left cross feed deck', 'right cross feed deck', 'central fore-aft feed deck'];
const stationary = [
  'hopper back panel', 'left hopper wall', 'right hopper wall', 'left hopper front wing',
  'right hopper front wing', 'front lift custody guide', 'feed diverter vane',
  'left front elevator upright', 'right front elevator upright', 'left rear elevator upright',
  'right rear elevator upright', 'left inside lift belt', 'right inside lift belt',
  'left outside lift belt', 'right outside lift belt'
].map(k => from(k, zero, .22));
const rear = from('rear lift custody gate', zero, .2);
if (mode === 'fixed')
  stationary.push(rear);
else
  stationary.push(
      shape('fixed lower rear guide', rear.a, [rear.c[0], rear.c[1], .226]),
      shape('fixed upper rear guide', [rear.a[0], rear.a[1], .400], rear.c));
const bridge = ['bridge', 'diagonal', 'alternate', 'sweep'].includes(mode);
const diagonal = ['diagonal', 'alternate', 'sweep'].includes(mode);
const belts = decks.map(
    (id, i) => from(
        id,
        mode === 'belts-off' ? zero :
            i === 0          ? [diagonal ? .68 * floorSpeed : 0, -floorSpeed, 0] :
            i === 1          ? [diagonal ? .68 * floorSpeed : 0, floorSpeed, 0] :
                               [floorSpeed, 0, 0],
        .65));
if (bridge)
  belts.push(shape(
      'deployed powered bridge', [.147, -.055, .228], [.304, .055, .235], [floorSpeed, 0, 0], .65));
const lanes = ['lanes', 'indexed', 'phased'].includes(mode);
if (lanes) {
  belts.splice(0, 3);
  for (const y of [-.155, -.001, .153])
    stationary.push(
        shape('thin lane divider', [-.330, y - .001, .235], [-.018, y + .001, .535], zero, .20));
  for (const [j, y] of [-.232, -.078, .076, .230].entries()) {
    belts.push(shape(
        'storage lane ' + j, [-.330, y - .077, .230], [.001, y + .077, .235], [floorSpeed, 0, 0],
        .65));
  }
  for (const sign of [-1, 1]) {
    const lo = sign < 0 ? -.311 : .037, hi = sign < 0 ? -.037 : .311;
    belts.push(shape(
        'front lateral ' + sign, [.001, lo, .230], [.148, hi, .235], [0, -sign * floorSpeed, 0],
        .65));
  }
  belts.push(
      shape('center discharge', [.001, -.037, .230], [.148, .037, .235], [floorSpeed, 0, 0], .65));
}
const balls = [];
for (const x of [-.251, -.097, .057])
  for (const y of [-.232, -.078, .076, .230])
    for (const z of [.235 + radius, .239 + 3 * radius]) {
      balls.push({
        id: 'batch-' + String(balls.length + 1).padStart(2, '0'),
        x,
        y,
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
const original = balls.map(b => state(b, 0));
const events = [], frames = [];
const lift = liftCircuit(.084, .622);
const count = {
  clearedPort: 0,
  atHead: 0,
  lost: 0
};
const pieces = balls.length;
let sweepX = -.330, sweepV = 0;
const profiles = {};
for (const b of balls) profiles[b.id] = {maxX: b.x, maxZ: b.z};
for (let step = 0; step <= Math.round(duration / dt); step++) {
  const t = step * dt;
  // Two 65-mm leaves translate into side pockets. Their closed union reproduces the R2C guide.
  const open = t < .2 ? 0 : Math.min(.087, (t - .2) * .435);
  const leafSpeed = t >= .2 && t < .4 ? .435 : 0;
  const leaves = mode === 'fixed' ? [] : [1, -1].map(sign => {
    const y0 = sign > 0 ? open : -.065 - open;
    return shape(
        'moving split guide', [rear.a[0], y0, .226], [rear.c[0], y0 + .065, .400],
        [0, sign * leafSpeed, 0], .2);
  });
  const ledges = [];
  // The four pairs of fixed-pitch CAD shelves share one belt. The ascending side engages in their
  // registered X/Y corridor.
  for (const z of lift.topHeights(t, liftSpeed, .289)) {
    for (const side of ['left', 'right']) {
      const q = by.get(side + ' lift shelf 1');
      ledges.push(
          shape(side + ' shelf', [q[0], q[1], z - .006], [q[3], q[4], z], [0, 0, liftSpeed], .6));
    }
  }
  if (mode === 'alternate') {
    const leftFirst = Math.floor(t / .63) % 2 === 0;
    belts[0].surface[1] = leftFirst ? -floorSpeed : 0;
    belts[1].surface[1] = leftFirst ? 0 : floorSpeed;
  }
  if (mode === 'indexed' || mode === 'phased') {
    const service = Math.floor(t / (mode === 'indexed' ? 1.15 : .47)) % 4;
    const side = service % 2 === 0 ? -1 : 1;
    for (const belt of belts) {
      if (belt.id.startsWith('storage lane ')) {
        const n = Number(belt.id.split(' ').at(-1));
        belt.surface[0] = (n === ([1, 2, 0, 3][service]) || mode === 'phased') ? floorSpeed : 0;
      }
      if (belt.id.startsWith('front lateral ')) {
        const sign = Number(belt.id.split(' ').at(-1));
        belt.surface[1] = sign === side ? -sign * floorSpeed : 0;
      }
    }
  }
  const surfaces = [...stationary, ...belts, ...leaves, ...ledges];
  const free = balls.filter(b => !b.done);
  for (const b of free) {
    b.fx = b.fy = b.mx = b.my = b.mz = 0;
    b.fz = -mass * 9.80665;
    for (const s of surfaces) box(b, s);
  }
  if (mode === 'sweep') {
    const ram = shape(
        'force-limited rear follower', [sweepX - .004, -.31, .236], [sweepX, .31, .549],
        [sweepV, 0, 0], .22);
    let reaction = 0;
    for (const b of free) {
      const before = b.fx;
      box(b, ram);
      reaction += b.fx - before;
    }
    sweepV = clamp(sweepV + (22 - reaction - 35 * sweepV) / 1.2 * dt, -.10, .25);
    sweepX = clamp(sweepX + sweepV * dt, -.330, .062);
  }
  for (let i = 0; i < free.length; i++)
    for (let j = i + 1; j < free.length; j++) pair(free[i], free[j]);
  for (const b of free) {
    integrate(b, dt);
    const record = profiles[b.id];
    record.maxX = Math.max(record.maxX, b.x);
    record.maxZ = Math.max(record.maxZ, b.z);
    if (!b.port && b.x - radius >= rear.c[0] && b.z > .235) {
      b.port = true;
      count.clearedPort++;
      events.push({kind: 'full port clearance', ...state(b, t)});
    }
    if (!b.head && b.port && b.z >= .54 && b.vz > 0) {
      b.head = true;
      count.atHead++;
      events.push({kind: 'upward head handoff', ...state(b, t)});
      // This fixture has no downstream receiver. Stop at the measured handoff to expose an
      // optimistic port-service ceiling.
      b.done = true;
    }
    if (!b.done && (b.z < 0 || b.z > .85 || b.x > .6 || Math.abs(b.y) > .5)) {
      b.done = true;
      count.lost++;
      events.push({kind: 'left fixture', ...state(b, t)});
    }
  }
  if (step % Math.round(.05 / dt) === 0)
    frames.push([
      Number(t.toFixed(4)),
      ...free.map(b => [b.id, ...[b.x, b.y, b.z].map(p => Number(p.toFixed(4)))])
    ]);
}
const result = {
  mode,
  duration,
  dt,
  floorSpeed,
  liftSpeed,
  circuitM: lift.length,
  pairedCarriers: lift.carriers,
  baseStepSha256: native.sourceSha256,
  appearanceSha256: createHash('sha256').update(raw).digest('hex'),
  pieces,
  original,
  count,
  events,
  profiles,
  sweepX,
  maxPenetrationM: Math.max(...balls.map(b => b.maxPen)),
  frames
};
await writeFile(output, JSON.stringify(result) + '\n');
console.log(
    mode, count, 'max penetration mm', result.maxPenetrationM * 1000, 'max X',
    Math.max(...Object.values(profiles).map(p => p.maxX)));
