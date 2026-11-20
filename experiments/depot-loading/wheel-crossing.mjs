// Pitch and heave of the selected four MAXSwerve wheels approaching the
// registered DEPOT front tube.
import {readFile, writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';

const here = new URL('./', import.meta.url);
const layout =
    JSON.parse(await readFile(new URL('../../cad/own-zone/layout.json', here)));
const source = JSON.parse(await readFile(new URL('stock-register.json', here)));
const R = layout.wheelRadiusMm / 1000;
const high = source.frontTubeBoundsMm[5] / 1000;
const clip = (v, a, b) => Math.max(a, Math.min(b, v));
export function crossing({
  recordStep = .005,
  halfWheelbaseM = layout.wheelAxisFromRobotCenterMm[0] / 1000,
  mass = 58,
  mu = .80,
  currentA = 50,
  cogM = .32,
  step = .000125,
  stroke = .3048,
  duration = .9,
  startFieldXM = source.centerXM,
  direction = -1
}) {
  if (direction !== 1 && direction !== -1) throw Error('Rail crossing requires a straight approach.');
  const [near, far] = [source.frontTubeBoundsMm[0], source.frontTubeBoundsMm[3]]
      .map(x => (x / 1000 - startFieldXM) * direction).sort((a, b) => a - b);
  const g = 9.80665, stiffness = 120000, damping = 650,
        inertia = mass * (.68 ** 2 + .64 ** 2) / 12;
  const ratio = 5.5, eff = .82, kt = 2.6 / 105, resist = 12 / 105,
        kv = 5676 * Math.PI / 30 / 12;
  const wheels = Array.from(
      {length: 4}, (_, i) => ({x: i < 2 ? halfWheelbaseM : -halfWheelbaseM, w: 0, current: 0}));
  let x = 0, z = cogM - mass * g / (4 * stiffness), a = 0, vx = 0, vz = 0,
      va = 0, volts = 12.6;
  const trace = [], maximum = {tilt: 0, current: 0, dropV: 0};
  let peak = 0, ready = null;
  const initialZ = z;
  for (let k = 0; k < Math.ceil(2.5 / step); k++) {
    const t = k * step, phase = clip(t / duration, 0, 1);
    const commandX = stroke * phase ** 2 * (3 - 2 * phase);
    const commandV = 6 * stroke * phase * (1 - phase) / duration;
    const speed = clip(commandV + 5 * (commandX - x), -1.4, 1.4);
    const ca = Math.cos(a), sa = Math.sin(a);
    let fx = 0, fz = -mass * g, torque = 0, battery = 0;
    for (const wheel of wheels) {
      const dx = wheel.x * ca - (R - cogM) * sa,
            dz = wheel.x * sa + (R - cogM) * ca;
      const cx = x + dx, cz = z + dz, cvx = vx - va * dz, cvz = vz + va * dx;
      let tangentTorque = 0;
      const drivenV = clip(
          speed * ratio / R / kv + 1.10 * (speed / R - wheel.w), -volts, volts);
      const current =
          clip((drivenV - wheel.w * ratio / kv) / resist, -currentA, currentA);
      const applied = kt * ratio * eff * current;
      battery += Math.max(0, drivenV * current / volts);
      maximum.current = Math.max(maximum.current, Math.abs(current));
      function support(nx, nz, dist, grip) {
        if (dist >= R) return;
        const velocity = cvx * nx + cvz * nz;
        const normal = Math.max(0, stiffness * (R - dist) - damping * velocity);
        const tx = nz, tz = -nx;
        const slip = cvx * tx + cvz * tz - wheel.w * R;
        const tangential = -grip * normal * Math.tanh(slip / .035);
        const px = normal * nx + tangential * tx,
              pz = normal * nz + tangential * tz;
        fx += px;
        fz += pz;
        torque += dx * pz - dz * px;
        tangentTorque += R * tangential;
      }
      support(0, 1, cz, mu);
      const px = clip(cx, near, far), pz = clip(cz, 0, high);
      const gx = cx - px, gz = cz - pz, dist = Math.hypot(gx, gz);
      if (dist > 1e-9) support(gx / dist, gz / dist, dist, mu);
      wheel.w += (applied - tangentTorque) * step / .0016;
      wheel.current = current;
      torque += applied;
    }
    volts = clip(12.6 - .018 * battery, 7, 12.6);
    maximum.dropV = Math.max(maximum.dropV, 12.6 - volts);
    vx += fx / mass * step;
    vz += fz / mass * step;
    va += torque / inertia * step;
    x += vx * step;
    z += vz * step;
    a += va * step;
    maximum.tilt = Math.max(maximum.tilt, Math.abs(a));
    peak = Math.max(peak, x);
    if (k % Math.max(1,Math.round(recordStep / step)) === 0)
      trace.push([t, x, z - initialZ, a, vx, vz, va]);
    if (t > duration && Math.abs(x - stroke) < .004 && Math.abs(vx) < .04 &&
        Math.abs(a) < .006 && Math.abs(vz) < .02 && ready == null)
      ready = t;
  }
  return {
    mass,
    mu,
    currentA,
    cogM,
    step,
    duration,
    stroke,
    near,
    far,
    railHeightM: high,
    radiusM: R,
    ratio,
    efficiency: eff,
    maximum,
    peakM: peak,
    endM: x,
    stableS: ready,
    trace
  };
}
if (process.argv[1] &&
    import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  const [out, weight, friction, amps, duration] = process.argv.slice(2);
  const r = crossing({
    mass: +weight || 58,
    mu: +friction || .8,
    currentA: +amps || 50,
    duration: +duration || .9
  });
  await writeFile(out, JSON.stringify(r) + '\n');
  console.log([r.mass, r.mu, r.currentA, r.endM, r.stableS, r.maximum]);
}
