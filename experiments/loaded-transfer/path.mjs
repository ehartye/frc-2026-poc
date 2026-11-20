// One departure clock, beginning at the final loading-gate observation.
import {readFile} from 'node:fs/promises';

import {supportAt} from '../depot-loading/chassis-frame.mjs';
import {crossing} from '../depot-loading/wheel-crossing.mjs';

const target = JSON.parse(await readFile(
    new URL('../own-zone-cycle/counter-replay.json', import.meta.url)));
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

function interpolate(p0, v0, p1, d, t) {
  const u = clamp(t / d, 0, 1), delta = p1 - p0;
  return [
    p0 + v0 * d * u + (3 * delta - 2 * v0 * d) * u * u +
        (-2 * delta + v0 * d) * u ** 3,
    v0 + 2 * (3 * delta / d - 2 * v0) * u + 3 * (-2 * delta / d + v0) * u * u
  ];
}

export function loadedPath(checkpoint, options = {}) {
  const [startX, startY] = checkpoint.robotFieldXYM;
  if (checkpoint.robotHeadingDeg !== 180)
    throw Error('The rail contact path assumes a west-facing robot.');
  const wheel = crossing({
    mass: 58 + (checkpoint.payload.length - 20) * .215,
    stroke: .57,
    direction: 1,
    startFieldXM: startX,
    duration: 1.25,
    ...options
  });
  const turnAt = 1.60, start = supportAt(wheel, turnAt);
  const releaseAt = 30 - checkpoint.timeS, deadline = releaseAt + 5,
        position = target.robotFieldM;
  function sample(t) {
    const drive = t - releaseAt;
    const still = {
      xy: [startX, startY],
      v: [0, 0],
      yaw: Math.PI,
      w: 0,
      pitch: 0,
      wp: 0,
      height: 0,
      vz: 0,
      cog: wheel.cogM
    };
    if (drive <= 0) return still;
    if (drive < turnAt || wheel.stableS === null) {
      const q = supportAt(wheel, Math.min(drive, wheel.trace.at(-1)[0]));
      return {
        ...still,
        xy: [startX + q.x, startY],
        v: [q.vx, 0],
        height: q.height,
        vz: q.dz,
        pitch: -Math.atan2(q.sin, q.cos),
        wp: -q.omega
      };
    }
    if (t >= deadline)
      return {
        ...still,
        xy: [...position],
        yaw: 2 * Math.PI + target.headingRad
      };
    const level = 5 - turnAt, elapsed = drive - turnAt;
    const [x, vx] =
        interpolate(startX + start.x, start.vx, position[0], level, elapsed);
    const [y, vy] = interpolate(startY, 0, position[1], level, elapsed);
    const [yaw, w] = interpolate(
        Math.PI, 0, 2 * Math.PI + target.headingRad, level, elapsed);
    const [height, vz] = interpolate(start.height, start.dz, 0, level, elapsed);
    const [pitch, wp] = interpolate(
        -Math.atan2(start.sin, start.cos), -start.omega, 0, level, elapsed);
    return {
      xy: [x, y],
      v: [vx, vy],
      yaw,
      w,
      height,
      vz,
      pitch,
      wp,
      cog: wheel.cogM
    };
  }
  return {
    sample,
    wheel,
    departS: releaseAt,
    arriveS: deadline,
    readyS: deadline + 3
  };
}
