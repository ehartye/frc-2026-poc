import {createHash} from 'node:crypto';
import {readFileSync, writeFileSync} from 'node:fs';
import {crossing} from '../../experiments/depot-loading/wheel-crossing.mjs';

const fieldFile = new URL('../../experiments/depot-loading/stock-register.json', import.meta.url);
const fieldData = readFileSync(fieldFile);
const field = JSON.parse(fieldData);
const pickupRow = field.floorStock.find(row => row.id === 'blue-depot-03');
const chassisYmm = pickupRow.centerMm[1] + 76.2;
const upperY = field.frontTubeBoundsMm[4];
if (chassisYmm - 87 < field.frontTubeBoundsMm[1] || chassisYmm + 84 > upperY) {
  throw Error('The complete sled does not overlap the finite tube laterally');
}

// At these robot X limits, at least one Y location on the floor or socket head
// has material. All the Y locations lie within the long face of the tube.
const underside = [
  {name:'sled bottom', fromX:-137, toX:54, bottom:41.65},
  {name:'aft screw heads', fromX:-114.25, toX:-105.75, bottom:35.65},
  {name:'fore screw heads', fromX:21.75, toX:30.25, bottom:35.65}
];

function clearance(trace, dropMm) {
  let nearest = null;
  let firstContact = null;
  const compressionM = trace.mass * 9.80665 / (4 * 120000);
  for (const [timeS, travel, heave, pitch] of trace.trace) {
    const cos = Math.cos(pitch);
    const sin = Math.sin(pitch);
    for (const member of underside) {
      const localZ = (member.bottom - dropMm) / 1000 - trace.cogM;
      const projectedOriginX = travel - localZ * sin;
      const fromX = Math.max(member.fromX / 1000, (trace.near - projectedOriginX) / cos);
      const toX = Math.min(member.toX / 1000, (trace.far - projectedOriginX) / cos);
      if (toX < fromX) continue;
      const x = sin < 0 ? toX : fromX;
      const worldZ = trace.cogM - compressionM + heave + x * sin + localZ * cos;
      const clearanceMm = 1000 * (worldZ - trace.railHeightM);
      if (!nearest || clearanceMm < nearest.clearanceMm) {
        nearest = {timeS,member:member.name,robotAxisXMm:1000*x,clearanceMm};
      }
      if (clearanceMm <= 0 && !firstContact) {
        firstContact = {timeS,member:member.name,clearanceMm};
      }
    }
  }
  return {dropMm,minimum:nearest,firstContact,flatGroundLoadedClearanceMm:35.65-dropMm-compressionM*1000};
}

const cases = [
  {name:'registered pickup advance',stroke:.3048,duration:.9},
  {name:'whole assembly traverses the rail',stroke:.90,duration:1.85}
];
const rows = [];
for (const {name,stroke,duration} of cases) {
  for (const [mass,mu,currentA] of [[58,.8,50],[68,.55,40]]) {
    const trace = crossing({halfWheelbaseM:.265,step:.000125,recordStep:.0005,mass,mu,currentA,stroke,duration});
    rows.push({
      case:name,massKg:mass,friction:mu,motorCurrentCapA:currentA,strokeM:stroke,
      achievedM:trace.endM,readyS:trace.stableS,railXM:[trace.near,trace.far],
      railTopMm:1000*trace.railHeightM,cases:[0,6,8,10,12,14].map(drop=>clearance(trace,drop))
    });
  }
}
const result = {
  sourceRegisterSha256:createHash('sha256').update(fieldData).digest('hex'),
  sourceFieldSha256:field.sourceFieldSha256, chassisYmm, headingDeg:field.fieldHeadingDeg,
  section:underside, halfWheelbaseMm:265, integratorStepS:.000125, traceStepS:.0005, rows,
  scope:'Four wheels with contact against carpet and the registered front tube. Gross supported mass and traction are scenario inputs. The complete 900 mm crossing is a deliberate engineering comparison. A touch invalidates subsequent free-motion prediction. No model of battery-sled contact forces, operator service or added qualification of earlier gameplay.'
};
if (!process.argv[2]) throw Error('Usage: node battery-rail.mjs OUTPUT.json');
writeFileSync(process.argv[2],JSON.stringify(result,null,2)+'\n');
