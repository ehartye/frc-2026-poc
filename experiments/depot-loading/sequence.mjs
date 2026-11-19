// Continuous robot-frame contact. All distances and times are in SI.
import {box, clamp, radius, state} from '../batch-port/contact.mjs';

import {legalPreloads} from './cartridge.mjs';
import {supportAt} from './chassis-frame.mjs';

const shape = (a, c, mu = .3, surface = [0, 0, 0]) => ({a, c, mu, surface});
const centers = [-.237, -.079, .079, .237];
const baseline = [
  [3, 0, 0], [9, 0, 0], [1, 0, 1], [7, 0, 1], [5, 1, 0], [11, 1, 0], [15, 1, 1],
  [21, 1, 1]
];
const curves = (from, to, start, end, t) => {
  const u = clamp((t - start) / (end - start), 0, 1), d = to - from;
  return [
    from + d * u * u * (3 - 2 * u), d * 6 * u * (1 - u) / (end - start),
    u === 0 || u === 1 ? 0 : d * (6 - 12 * u) / (end - start) ** 2
  ];
};

export function sequenceDock(source, limits = {}) {
  const operations = limits.straight ?
      [
        [1, 0, 0], [7, 0, 0], [5, 0, 1], [11, 0, 1], [3, 1, 0], [9, 1, 0],
        [15, 1, 1], [21, 1, 1]
      ] :
      baseline;
  const stockSources = source.floorStock, initialPose = [
    source.centerXM,
    stockSources[operations[0][0] - 1].centerMm[1] / 1000 + .0762
  ];
  const rows = [], gates = centers.map(() => [0, 0]), history = [];
  let index = 0, stage = 'collect', start = 0, lift = 0, rate = 0, y = 0,
      vy = 0, open = 0, conveyor = 0, roller = [0, 0, 0, 0];
  let support = null, supportTime = null, supportEnded = false,
      checkpoint = null;
  let aiming = 0, targetY = 0, tier = 0, leftLane = 0,
      startedPose = initialPose.slice(), destination = initialPose.slice();
  let fieldPose = initialPose.slice(), fieldVel = [0, 0], fieldAcc = [0, 0];
  let previousY = 0, previousH = 0;
  let capture = [null, null], entered = [null, null], periodStart = 0,
      witness = [];
  const prior = new Set();
  const staticParts = [shape([-.334, -.317, .230], [-.330, .317, .550])];
  for (const side of [-.317, -.158, 0, .158, .317])
    staticParts.push(
        shape([-.330, side - .001, .232], [.148, side + .001, .55]));
  const newOperation = () => {
    const [id, side, layer] = operations[index];
    const first = stockSources[id - 1];
    leftLane = side ? 2 : 0;
    targetY = side ? .158 : -.158;
    tier = layer;
    const deep = id >= 15;
    destination = [
      initialPose[0] -
          (deep ? (limits.straight ? (id === 21 ? .365 : .3048) : .286) : 0),
      first.centerMm[1] / 1000 + .0762
    ];
    aiming = Math.min(.605, destination[0] - first.centerMm[0] / 1000 + .060);
    capture = [null, null];
    entered = [null, null];
  };
  newOperation();
  function pulse(name, t) {
    stage = name;
    start = t;
  }
  function arm(t) {
    const target = [
      [0, aiming, .233], [.25, aiming, .155], [.92, .336, .159],
      [1.12, .336, .159], [1.40, .330, .302]
    ];
    for (let i = 1; i < target.length; i++) {
      const [a, x0, z0] = target[i - 1], [b, x1, z1] = target[i];
      if (t > b) continue;
      const [x, vx] = curves(x0, x1, a, b, t),
                [z, vz] = curves(z0, z1, a, b, t);
      return [x, z, vx, vz];
    }
    return [.330, .302, 0, 0];
  }
  function tick(t, stock) {
    const dwell = limits.early ? .035 : .14;
    const h = .220 + tier * .154, dock = stage === 'feed' || stage === 'close';
    conveyor = dock ? -.70 : 0;
    if (stage === 'collect') {
      roller = arm(t - periodStart);
      for (const b of stock) {
        if (prior.has(b.id) || !b.id.startsWith('blue-depot-') || b.x <= .190 ||
            b.x >= .280 || b.z <= .078 || b.z >= .15 || Math.abs(b.vx) >= .12)
          continue;
        const j = +(b.y > 0);
        if (!capture[j] && Math.abs(Math.abs(b.y) - .0762) < .034) {
          capture[j] = b.id;
          witness.push({event: 'on pickup shelf', ...state(b, t)});
        }
      }
      if (capture.every(Boolean)) pulse('lift', t);
    } else if (stage === 'lift') {
      roller = arm(t - periodStart);
      [lift, rate] = curves(0, h, start + dwell, start + dwell + h / .50, t);
      if (t >= start + dwell + h / .50) pulse('index', t);
    } else if (stage === 'index') {
      roller = arm(t - periodStart);
      [y, vy] = curves(0, targetY, start, start + .49, t);
      if (t >= start + .49) pulse('open', t);
    } else if (stage === 'open') {
      open = curves(0, 1, start, start + .18, t)[0];
      gates[leftLane][tier] = gates[leftLane + 1][tier] = open;
      if (t >= start + .18) pulse('feed', t);
    } else if (stage === 'feed') {
      for (let j = 0; j < 2; j++) {
        const b = stock.find(p => p.id === capture[j]);
        if (!entered[j] && b.x + radius < .147 &&
            Math.abs(b.y - centers[leftLane + j]) < .018 &&
            Math.abs(b.z - (.310 + tier * .154)) < .018) {
          entered[j] = b.id;
          witness.push({event: 'trailing surface inside lane', ...state(b, t)});
        }
      }
      if (entered.every(Boolean)) pulse('close', t);
    } else if (stage === 'close') {
      const clearPause = limits.quick ? .015 : .06;
      open = curves(1, 0, start + clearPause, start + clearPause + .18, t)[0];
      gates[leftLane][tier] = gates[leftLane + 1][tier] = open;
      if (t >= start + clearPause + .20) {
        for (const id of entered) prior.add(id);
        rows.push({
          index,
          startedS: periodStart,
          closedS: t,
          sourceIds: [...capture],
          dockedLanes: [leftLane, leftLane + 1],
          tier,
          witness
        });
        witness = [];
        if (index === operations.length - 1) {
          const payload = cargo(stock);
          checkpoint = {
            timeS: t,
            robotFieldXYM: [...fieldPose],
            robotVelocityFieldMps: [...fieldVel],
            robotHeadingDeg: 180,
            carriage: {
              lateralM: y,
              lateralMps: vy,
              liftM: lift,
              liftMps: rate,
              rollerXZ: roller.slice(0, 2),
              rearStopOpenFraction: open
            },
            storageGateOpenFractions: gates.map(pair => [...pair]),
            payload:
                stock.filter(b => payload.includes(b.id)).map(b => state(b, t)),
            remainingField: stock.filter(b => !payload.includes(b.id))
                                .map(b => state(b, t)),
            minimumTrailingFaceMarginM:
                Math.min(...stock.filter(b => payload.includes(b.id))
                             .map(b => .148 - b.x - radius)),
            sourceIds: rows.flatMap(row => row.sourceIds)
          };
        }
        pulse('home', t);
        startedPose = [...fieldPose];
        previousY = targetY;
        previousH = h;
        if (limits.overlap && index + 1 < operations.length) {
          index++;
          newOperation();
          pulse('synchronized return', t);
        }
      }
    } else if (stage === 'home') {
      [y, vy] = curves(targetY, 0, start, start + .49, t);
      [lift, rate] = curves(h, 0, start + .49, start + .49 + h / .50, t);
      if (t >= start + .49 + h / .50) {
        if (index + 1 === operations.length) {
          pulse('hold', t);
          return;
        }
        index++;
        newOperation();
        pulse('move', t);
      }
    } else if (stage === 'synchronized return') {
      // The doors have reclosed. Retract the empty tray while the chassis and
      // high intake move to the next pair.
      const travel = Math.hypot(
          destination[0] - startedPose[0], destination[1] - startedPose[1]);
      const change = Math.max(.48, Math.sqrt(6 * travel / 2.3));
      const rolling = limits.wheel && index === 6;
      const finish = Math.max(
          change, .49 + .16, previousH / .55 + .10,
          rolling ? (limits.wheel.stableS ?? Infinity) : 0);
      const armFinish = Number.isFinite(finish) ? finish : 2.5;
      [y, vy] = curves(previousY, 0, start, start + .49, t);
      [lift, rate] =
          curves(previousH, 0, start + .10, start + .10 + previousH / .55, t);
      for (let j = 0; j < 2; j++)
        [fieldPose[j], fieldVel[j], fieldAcc[j]] =
            curves(startedPose[j], destination[j], start, start + change, t);
      if (rolling) {
        supportTime ??= start;
        support = supportAt(limits.wheel, t - start);
        fieldPose[0] = startedPose[0] - support.x;
        fieldVel[0] = -support.vx;
        fieldAcc[0] = -support.ax;
      }
      const [x, vx] = curves(.330, aiming, start, start + armFinish, t),
                [z, vz] = curves(.302, .233, start, start + armFinish, t);
      roller = [x, z, vx, vz];
      if (t >= start + finish) {
        if (rolling) supportEnded = true;
        periodStart = t;
        pulse('collect', t);
      }
    } else if (stage === 'move') {
      const travel = Math.hypot(
          destination[0] - startedPose[0], destination[1] - startedPose[1]);
      const duration = Math.max(.48, Math.sqrt(6 * travel / 2.3));
      for (let j = 0; j < 2; j++)
        [fieldPose[j], fieldVel[j], fieldAcc[j]] =
            curves(startedPose[j], destination[j], start, start + duration, t);
      const [x, vx] = curves(.330, aiming, start, start + duration, t);
      const [z, vz] = curves(.302, .233, start, start + duration, t);
      roller = [x, z, vx, vz];
      if (t >= start + duration) {
        periodStart = t;
        pulse('collect', t);
      }
    }
    if (supportEnded && supportTime !== null) {
      const elapsed = t - supportTime;
      support = elapsed < 2.5 ? supportAt(limits.wheel, elapsed) : null;
      if (support && index === 6) {
        fieldPose[0] = initialPose[0] - support.x;
        fieldVel[0] = -support.vx;
        fieldAcc[0] = -support.ax;
      } else if (index === 6) {
        fieldVel[0] = 0;
        fieldAcc[0] = 0;
      }
    }
    if (Math.round(t * 1000) % 100 === 0 &&
        (!history.length || t - history.at(-1)[0] > .04))
      history.push([t, stage, index, ...fieldPose]);
  }
  function contacts(b, t) {
    for (const s of staticParts) box(b, s);
    for (let k = 0; k < 4; k++) {
      const c = centers[k], active = (k === leftLane || k === leftLane + 1);
      for (let layer = 0; layer < 2; layer++) {
        const bottom = .235 + .154 * layer,
              drive = active && layer === tier ? conveyor : 0;
        box(b,
            shape(
                [-.330, c - .077, bottom - .004], [.149, c + .077, bottom], .68,
                [drive, 0, 0]));
        const shift = (layer ? 1 : -1) * .164 * gates[k][layer];
        box(b,
            shape(
                [.148, c - .076, bottom + shift],
                [.152, c + .076, bottom + .151 + shift], .20));
      }
    }
    const cap = .055 + lift;
    for (const by of [-.158, 0, .158])
      box(b,
          shape(
              [.165, y + by - .001, cap], [.325, y + by + .001, cap + .128],
              .24, [0, vy, rate]));
    for (const by of [-.079, .079]) {
      const c = y + by;
      box(b,
          shape(
              [.327, c - .066, .221 + lift], [.331, c + .066, .38 + lift], .20,
              [0, vy, rate]));
      if (open < 1)
        box(b,
            shape(
                [.167, c - .064, .132 + lift - .190 * open],
                [.171, c + .064, .267 + lift - .190 * open], .20,
                [0, vy, rate]));
      if (stage === 'open' || stage === 'feed' || stage === 'close') {
        const bottom = .235 + .154 * tier;
        box(b,
            shape(
                [.148, c - .056, bottom - .006], [.303, c + .056, bottom], .72,
                [conveyor, 0, 0]));
      }
    }
    for (const [lo, hi] of [[-.168, -.148], [-.008, .008], [.148, .168]])
      box(b,
          shape(
              [.196, y + lo, .066 + lift], [.292, y + hi, .072 + lift], .60,
              [conveyor, vy, rate]));
  }
  function cargo(stock) {
    return stock
        .filter(
            b => b.x + radius < .149 && b.x - radius > -.335 &&
                centers.some(y => Math.abs(b.y - y) < .007) &&
                Math.min(Math.abs(b.z - .310), Math.abs(b.z - .464)) < .012)
        .map(b => b.id);
  }
  return {
    tick,
    contacts,
    initial: legalPreloads,
    get support() {
      return support
    },
    get pose() {
      return fieldPose
    },
    get velocity() {
      return fieldVel
    },
    get acceleration() {
      return fieldAcc
    },
    get roller() {
      return roller
    },
    status(stock) {
      return {
        stage,
        index,
        capture,
        entered,
        supportTime,
        checkpoint,
        rows,
        openWitness: witness,
        history,
        cargo: cargo(stock)
      };
    },
    cargo
  };
}
