// One lower-tier cartridge dock. Positive delivery is observed only after a source ID remains
// supported.
import {box, clamp, radius, state} from '../batch-port/contact.mjs';
const lanes = [-.237, -.079, .079, .237];
const deckZ = .235;
const surface = (a, c, mu = .3, velocity = [0, 0, 0]) => ({a, c, mu, surface: velocity});

export function legalPreloads() {
  return lanes.flatMap((y, i) => [0, 1].map(t => ({
                                              id: 'blue-unspent-preload-' + (1 + i * 2 + t),
                                              x: -.251,
                                              y,
                                              z: deckZ + .154 * t + radius,
                                              vx: 0,
                                              vy: 0,
                                              vz: 0,
                                              wx: 0,
                                              wy: 0,
                                              wz: 0,
                                              maxPen: 0
                                            })));
}
export function createDock({reverse = true, locked = false} = {}) {
  const laneY = lanes[2], height = .220, events = [];
  let atHeight = null, firstCapture = null, carY = 0, carV = 0, feeding = false, housed = null,
      stopAt = null;
  const staticParts = [surface([-.334, -.317, .230], [-.330, .317, .55])];
  for (const y of [-.317, -.158, 0, .158, .317])
    staticParts.push(surface([-.330, y - .001, .235], [.148, y + .001, .550], .22));
  for (const y of lanes) {
    staticParts.push(surface([-.330, y - .077, .385], [.149, y + .077, .389], .65));
    if (y !== laneY)
      staticParts.push(surface([.148, y - .078, .235], [.152, y + .078, .550]));
    else
      staticParts.push(surface([.148, y - .078, .389], [.152, y + .078, .550]));
  }
  const fixedFront = surface([.327, -.065, .221], [.331, .065, .582], .2);
  return {
    targetLift: height,
    events,
    initial: legalPreloads,
    advance(t, lift, b) {
      if (lift === height && atHeight == null && b.z > .30 && b.x > .19 && b.x < .30) {
        firstCapture = b.id;
        atHeight = t;
        events.push({event: 'supported at loading height', state: state(b, t)});
      }
      if (atHeight == null) return;
      const u = clamp((t - atHeight - .10) / .45, 0, 1);
      carY = laneY * u * u * (3 - 2 * u);
      carV = laneY * 6 * u * (1 - u) / .45;
      feeding = u === 1;
      if (feeding && b.id === firstCapture && b.x + radius < .148 && housed == null) {
        housed = t;
        events.push({event: 'trailing surface inside lane', state: state(b, t)});
      }
      // Release the powered belt only after the arriving piece reaches the next unoccupied pocket.
      if (housed != null && b.x < -.088 && stopAt == null) {
        stopAt = t;
        events.push({event: 'stop storage belt', state: state(b, t)});
      }
    },
    get carY() {
      return carY;
    },
    get carV() {
      return carV;
    },
    contacts(b, t, lift) {
      for (const s of staticParts) box(b, s);
      box(b, fixedFront);
      if (housed !== null) {
        const closed = clamp((t - housed - .04) / .18, 0, 1);
        if (closed > 0)
          box(b,
              surface(
                  [.148, laneY - .076, .389 - .154 * closed],
                  [.152, laneY + .076, .546 - .154 * closed], .2,
                  [0, 0, closed < 1 ? -.154 / .18 : 0]));
      }
      const drive = feeding && reverse && stopAt == null ? -.6 : 0;
      for (const y of lanes)
        box(b, surface([-.330, y - .077, .230], [.149, y + .077, deckZ], .68, [
              y === laneY ? drive : 0, 0, 0
            ]));
      const railStart = .165, railEnd = .325, guideZ = .055 + lift;
      for (const sign of [-1, 1]) {
        const y = carY + sign * .080;
        box(b, surface([railStart, y - .0015, guideZ], [railEnd, y + .0015, guideZ + .125], .23, [
              0, carV, 0
            ]));
      }
      // The rear stop retracts below the loading shelf when the lane is docked.
      const drop = locked || atHeight == null ? 0 : clamp((t - atHeight - .55) / .18, 0, 1);
      if (drop < 1)
        box(b,
            surface(
                [.167, carY - .065, .134 - .185 * drop], [.171, carY + .065, .410 - .185 * drop],
                .20, [0, carV, drop > 0 ? -1.028 : 0]));
      if (feeding)
        box(b, surface([.148, laneY - .056, .229], [.303, laneY + .056, .235], .72, [drive, 0, 0]));
    },
    shelfVelocity() {
      return feeding && reverse && stopAt == null ? -.6 : 0;
    },
    status(stock) {
      const b = stock.find(p => p.id === firstCapture);
      const retains = p => p.x + radius < .149 && p.x - radius > -.334 &&
          Math.abs(p.y - lanes.reduce((a, c) => Math.abs(c - p.y) < Math.abs(a - p.y) ? c : a)) <
              .005 &&
          p.z >= .30 && p.z < .48 && Math.hypot(p.vx, p.vy, p.vz) < .05;
      return {
        destinationLaneY: laneY,
        retainedSourceId: b && retains(b) ? b.id : null,
        retainedPreloads: stock.filter(p => p.id.includes('preload') && retains(p)).map(p => p.id),
        events
      };
    }
  };
}
