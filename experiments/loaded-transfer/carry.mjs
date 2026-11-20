// Replay both the attained cargo and the loose field stock in inertial STEP
// axes.
import {createHash} from 'node:crypto';
import {readFile, writeFile} from 'node:fs/promises';

import {box, contact, integrate, mass, pair, radius, state} from '../batch-port/contact.mjs';
import {accumulate, localBody} from '../depot-loading/chassis-frame.mjs';
import {ramp, rollerContact} from '../depot-loading/intake-contacts.mjs';
import {sequenceDock} from '../depot-loading/sequence.mjs';

import {loadedPath} from './path.mjs';

const [snapshot, out, timeStep] = process.argv.slice(2), dt = Number(timeStep);
if (!out || !(dt > 0 && dt <= .0005))
  throw Error('Usage: node carry.mjs CHECKPOINT OUTPUT CONTACT_STEP');
const input = await readFile(snapshot), checkpoint = JSON.parse(input);
const read = async path =>
    JSON.parse(await readFile(new URL(path, import.meta.url)));
const depot = await read('../depot-loading/stock-register.json');
const inventory =
    (await read('../../cad/own-zone-upper/appearances.json')).solids;
const path = loadedPath(checkpoint), dock = sequenceDock(depot);
const pad = [0, 0, 0], front = depot.frontTubeBoundsMm;
const surface = (a, c, mu = .35) => ({a, c, mu, surface: pad});
const wallX = Math.min(...depot.sideTubeBoundsMm.map(q => q[0])) / 1000;
let minimumWallM = Infinity;
const field = [front, ...depot.sideTubeBoundsMm].map(
    q => surface(
        q.slice(0, 3).map(n => n / 1000), q.slice(3).map(n => n / 1000)));
const body =
    inventory
        .filter(
            p => /bumper|front return|perimeter tube|deck crossmember/.test(
                p.id))
        .map(p => {
          const a = p.boundsMm.slice(0, 3).map(n => n / 1000),
                c = p.boundsMm.slice(3).map(n => n / 1000);
          if (/front bumper|front return/.test(p.id)) {
            if (p.id.startsWith('left'))
              a[1] = .184;
            else
              c[1] = -.184;
          }
          return surface(a, c);
        });
const tires = inventory.filter(p => p.id.endsWith('public wheel')).map(p => {
  const q = p.boundsMm;
  return {
    id: p.id,
    center: [0, 1, 2].map(i => (q[i] + q[i + 3]) / 2000),
    radius: Math.hypot(q[3] - q[0], q[4] - q[1]) / 2000
  };
});
const ids = new Set(checkpoint.payload.map(p => p.id));
const balls = [...checkpoint.payload, ...checkpoint.remainingField].map(p => {
  const [x, y, z] = p.positionM, [vx, vy, vz] = p.velocityMps,
               [wx, wy, wz] = p.spinRadS;
  return {
    id: p.id,
    x: checkpoint.robotFieldXYM[0] - x,
    y: checkpoint.robotFieldXYM[1] - y,
    z,
    vx: -vx,
    vy: -vy,
    vz,
    wx: -wx,
    wy: -wy,
    wz,
    maxPen: 0
  };
});
const orient = (x, y, c, s) => [c * x + s * y, -s * x + c * y];
function local(world, f) {
  const c = Math.cos(f.yaw), s = Math.sin(f.yaw);
  const [x, y] = orient(world.x - f.xy[0], world.y - f.xy[1], c, s);
  const [vx, vy] = orient(world.vx - f.v[0], world.vy - f.v[1], c, s);
  const [wx, wy] = orient(world.wx, world.wy, c, s);
  const horizontal = {
    ...world,
    x,
    y,
    vx: vx + f.w * y,
    vy: vy - f.w * x,
    wx,
    wy,
    wz: world.wz - f.w,
    fx: 0,
    fy: 0,
    fz: 0,
    mx: 0,
    my: 0,
    mz: 0
  };
  const attitude = {
    cos: Math.cos(f.pitch),
    sin: Math.sin(f.pitch),
    height: f.height,
    dz: f.vz,
    omega: f.wp,
    cog: f.cog
  };
  return {b: localBody(horizontal, attitude), horizontal, attitude, c, s};
}
const expose = (world, f, t) => state(local(world, f).b, t);
let worstTire = {gapM: Infinity}, minimumDoor = Infinity, floorConflict = null,
    openInventory = null;
const samples = [];
let end;
for (let k = 0;; k++) {
  const t = Math.min(k * dt, path.readyS), f = path.sample(t),
        carriage = dock.parkCarriage(checkpoint, t);
  const states = balls.map(b => local(b, f));
  const status = states.filter(({b}) => ids.has(b.id));
  for (const {b} of status) {
    const gate = .148 - b.x - radius;
    minimumDoor = Math.min(minimumDoor, gate);
    if (!openInventory &&
        !(b.x + radius <= .153 && b.x - radius >= -.335 &&
          Math.abs(b.y) < .318 && b.z > .225 && b.z < .55))
      openInventory = {id: b.id, t, robotPosition: [b.x, b.y, b.z]};
  }
  if (k % Math.round(.05 / dt) === 0 || t === path.readyS)
    samples.push({
      timeS: checkpoint.timeS + t,
      poseM: f.xy,
      headingDeg: f.yaw * 180 / Math.PI,
      retained: dock.cargo(status.map(s => s.b)).length
    });
  if (t === path.readyS) {
    end = {
      timeS: checkpoint.timeS + t,
      robotFieldXYM: f.xy,
      robotVelocityFieldMps: f.v,
      robotHeadingDeg: f.yaw * 180 / Math.PI - 360,
      carriage,
      storageGateOpenFractions: checkpoint.storageGateOpenFractions,
      payload: balls.filter(b => ids.has(b.id))
                   .map(b => expose(b, f, checkpoint.timeS + t)),
      remainingField: balls.filter(b => !ids.has(b.id))
                          .map(b => expose(b, f, checkpoint.timeS + t))
    };
    break;
  }
  for (let i = 0; i < balls.length; i++) {
    const world = balls[i], {b, horizontal, attitude, c, s} = states[i];
    world.fx = world.fy = world.mx = world.my = world.mz = 0;
    world.fz = -mass * 9.80665;
    contact(world, 0, 0, 1, radius - world.z, 0, 0, 0, .55, 2500, 10);
    const wallGap = world.x - wallX - radius;
    minimumWallM = Math.min(minimumWallM, wallGap);
    if (wallGap < 0) contact(world, 1, 0, 0, -wallGap, 0, 0, 0, .30, 10000, 20);
    for (const part of field) box(world, part);
    for (const part of body) box(b, part);
    dock.contacts(b, t);
    for (const y of [-.1362, -.0162, .0162, .1362]) ramp(b, y);
    rollerContact(b, [...carriage.rollerXZ, 0, 0], true);
    if (!ids.has(b.id)) {
      for (const wheel of tires) {
        const gap = Math.hypot(
                        b.x - wheel.center[0], b.y - wheel.center[1],
                        b.z - wheel.center[2]) -
            wheel.radius - radius;
        if (gap < worstTire.gapM)
          worstTire = {gapM: gap, id: b.id, t, wheel: wheel.id};
      }
      if ((b.fx || b.fy || b.fz) && !floorConflict)
        floorConflict = {t, id: b.id};
    }
    accumulate(horizontal, b, attitude);
    world.fx += c * horizontal.fx - s * horizontal.fy;
    world.fy += s * horizontal.fx + c * horizontal.fy;
    world.fz += horizontal.fz;
    world.mx += c * horizontal.mx - s * horizontal.my;
    world.my += s * horizontal.mx + c * horizontal.my;
    world.mz += horizontal.mz;
  }
  for (let i = 0; i < balls.length; i++)
    for (let j = 0; j < i; j++) pair(balls[i], balls[j]);
  for (const b of balls) integrate(b, Math.min(dt, path.readyS - t));
}
const {trace, ...wheel} = path.wheel;
const report = {
  sourceSha256: createHash('sha256').update(input).digest('hex'),
  dt,
  departS: checkpoint.timeS + path.departS,
  arriveS: checkpoint.timeS + path.arriveS,
  readyS: end.timeS,
  wheel,
  minimumWallM,
  minimumDoorM: minimumDoor,
  firstEnvelopeEscape: openInventory,
  closestLooseTire: worstTire,
  firstBodyStockContact: floorConflict,
  initial: checkpoint.payload.map(p => p.id),
  end,
  samples
};
await writeFile(out, JSON.stringify(report) + '\n');
console.log({
  start: checkpoint.timeS,
  depart: report.departS,
  arrive: report.arriveS,
  ready: end.timeS,
  minimumDoor,
  escaped: openInventory,
  tire: worstTire,
  fieldContact: floorConflict,
  retained: samples.at(-1),
  wheelSettled: wheel.stableS
});
