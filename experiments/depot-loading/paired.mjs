// Pair of adjacent middle lanes with one split center support and independent closing lane stops.
import {box, clamp, radius, state} from '../batch-port/contact.mjs';

import {legalPreloads} from './cartridge.mjs';

const ys = [-.237, -.079, .079, .237];
const surface = (a, c, mu = .30, velocity = [0, 0, 0]) => ({a, c, mu, surface: velocity});
export function pairedDock({locked = false} = {}) {
  const staticParts = [surface([-.334, -.317, .230], [-.330, .317, .55])];
  for (const y of [-.317, -.158, 0, .158, .317])
    staticParts.push(surface([-.330, y - .001, .235], [.148, y + .001, .550]));
  for (const y of ys) {
    staticParts.push(surface([-.330, y - .077, .385], [.149, y + .077, .389], .65));
    staticParts.push(
        surface([.148, y - .077, Math.abs(y) < .1 ? .389 : .235], [.152, y + .077, .550]));
  }
  const lanes = [-.079, .079].map(y => ({y, received: null, housed: null, full: null}));
  let atHeight = null;
  const events = [];
  const height = .220;
  return {
    initial: legalPreloads,
    events,
    targetLift: height,
    carY: 0,
    carV: 0,
    advance(t, lift, b) {
      if (!b.id.startsWith('blue-depot-')) return;
      const row = lanes.find(l => Math.abs(b.y - l.y) < .02);
      if (!row) return;
      if (lift === height && row.received == null && b.z > .30 && b.x > .19 && b.x < .30) {
        row.received = b.id;
        events.push({event: 'supported at loading height', state: state(b, t)});
      }
      if (atHeight == null && lanes.every(l => l.received)) atHeight = t;
      if (atHeight !== null && row.received === b.id) {
        if (row.housed === null && b.x + radius < .148) {
          row.housed = t;
          events.push({event: 'trailing surface inside lane', state: state(b, t)});
        }
        if (row.housed !== null && b.x < -.088 && row.full === null) {
          row.full = t;
          events.push({event: 'stop storage belt', state: state(b, t)});
        }
      }
    },
    contacts(b, t, lift) {
      for (const s of staticParts) box(b, s);
      for (const y of ys) {
        const row = lanes.find(l => l.y === y);
        const drive = atHeight !== null && t > atHeight + .16 && row && row.full == null ? -.60 : 0;
        box(b, surface([-.330, y - .077, .230], [.149, y + .077, .235], .68, [drive, 0, 0]));
        if (!row) continue;
        const retract = locked || atHeight == null ? 0 : clamp((t - atHeight - .02) / .18, 0, 1);
        if (retract < 1)
          box(b,
              surface(
                  [.167, y - .068, .134 - .185 * retract], [.171, y + .068, .410 - .185 * retract],
                  .20, [0, 0, retract > 0 ? -1.028 : 0]));
        box(b, surface([.327, y - .064, .221], [.331, y + .064, .582]));
        if (atHeight !== null)
          box(b, surface([.148, y - .056, .229], [.303, y + .056, .235], .72, [drive, 0, 0]));
        if (row.housed !== null) {
          const close = clamp((t - row.housed - .04) / .18, 0, 1);
          if (close > 0)
            box(b,
                surface(
                    [.148, y - .076, .389 - .154 * close], [.152, y + .076, .546 - .154 * close],
                    .20, [0, 0, close < 1 ? -.154 / .18 : 0]));
        }
      }
      for (const y of [-.158, 0, .158])
        box(b, surface([.165, y - .001, .055 + lift], [.325, y + .001, .181 + lift], .23));
    },
    shelves(b, lift, rate, t) {
      const row = lanes.find(l => Math.abs(b.y - l.y) < .06);
      const drive = atHeight !== null && t > atHeight + .16 && row && row.full == null ? -.60 : 0;
      for (const [lo, hi] of [[-.168, -.148], [-.008, .008], [.148, .168]])
        box(b, surface([.196, lo, .066 + lift], [.292, hi, .072 + lift], .6, [drive, 0, rate]));
    },
    status(stock) {
      const retains = b => b && b.x + radius < .149 && b.x - radius > -.334 &&
          ys.some(y => Math.abs(b.y - y) < .006) && b.z >= .30 && b.z < .48 &&
          Math.hypot(b.vx, b.vy, b.vz) < .05;
      return {
        retainedSourceIds:
            lanes.map(l => stock.find(b => b.id === l.received)).filter(retains).map(b => b.id),
        retainedPreloads: stock.filter(b => b.id.includes('preload') && retains(b)).map(b => b.id),
        events
      };
    }
  };
}
