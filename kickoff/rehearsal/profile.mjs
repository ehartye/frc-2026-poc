/** Physical stock and staffing inputs for the live student rehearsal. Units are field inches. */
import {readFile} from 'node:fs/promises';

const source = relative => new URL(relative, import.meta.url);
const read = async relative => JSON.parse(await readFile(source(relative)));
const round = value => Number(value.toFixed(5));

// A repeatable hypothetical dispersal, not a survey of the released field.
// Twelve columns span the nominal 72-inch depth. A small, bounded displacement
// breaks the regular pattern without making any two nominal spheres intersect.
function neutralPositions(station) {
  const [[x0,y0],[x1,y1]] = station.areaIn;
  const result = [];
  for (let row=0; row<15; row++) {
    for (let column=0; column<12; column++) {
      const dx=0.025*Math.sin(13*row+7*column);
      const dy=0.24*Math.sin(19*row-11*column);
      result.push([round(x0+(column+0.5)*(x1-x0)/12+dx),
                   round(y0+(row+0.5)*(y1-y0)/15+dy)]);
    }
  }
  return result;
}

export async function physicalMatchProfile({secondsPerPiece=1.5} = {}) {
  const [profile, depot] = await Promise.all([
    read('../rules-model.json'), read('../../experiments/depot-loading/stock-register.json'),
  ]);
  const {field, rehearsal} = profile;
  const stations = new Map(rehearsal.stations.map(station => [station.id, station]));
  const mirror = ([x,y]) => [round(field.length-x), round(field.width-y)];
  const fuel = {radiusIn:profile.fieldFeatures.fuelDiameter/2,
                heightIn:profile.fieldFeatures.fuelDiameter, massKg:0.215};
  const bluePositions = depot.floorStock.map(({centerMm:[x,y]}) =>
    [round(x/25.4+field.length/2),round(y/25.4+field.width/2)]);
  for (const side of ['blue','red']) {
    const positions = side === 'blue' ? bluePositions : bluePositions.map(mirror);
    stations.get(side+'-depot').floor = {positions, ...fuel, captureReachIn:5};
    // The kickoff manual gives random return direction into the neutral zone.
    // These floor landing points and the inherited four-second delay are trial
    // assumptions, beyond the protected 48-inch direct-catch band.
    const hub=stations.get(side+'-hub');
    for (const route of Object.values(hub.returns)) {
      route.at=side==='blue' ? [280,123] : mirror([280,123]);
    }
    stations.get(side+'-outpost').service = {
      operator: side+'-chute-attendant', secondsPerPiece,
      phases:rehearsal.periods.map(phase=>phase.name),
      outlet:side==='blue' ? [13,32] : mirror([13,32]),
      ...fuel, capacity:1, captureReachIn:5,
    };
  }
  for (const id of ['neutral-north','neutral-south']) {
    const station=stations.get(id);
    station.floor={positions:neutralPositions(station),...fuel,captureReachIn:5};
  }
  // Each pickup is tested against a real available identity. Four separated
  // services give the OUTPOST operator time to release the next FUEL.
  const feeder=rehearsal.programs['shift-outpost'];
  feeder.steps=feeder.steps.flatMap(step=>step.operation==='acquire'
    ? Array.from({length:4},()=>({...step, quantity:1, dwell:1.5}))
    : [step]);
  const pickup=rehearsal.programs['shift-neutral'].steps.find(step=>step.operation==='acquire');
  pickup.at=[295,247];
  pickup.dwell=0.15;
  pickup.label='Collect reachable FUEL at the near neutral edge';
  const ownZone=rehearsal.series.matches.find(m=>m.id==='Own-zone supply');
  const neutral=rehearsal.series.matches.find(m=>m.id==='Neutral return');
  // First-time students get three working roles. The blocked-lane reserve
  // belongs to the deliberately different published comparison.
  rehearsal.defaults.roster=ownZone.roster.map(row=>{
    const result=structuredClone(row);
    if (result.slot===3) {
      const peer=neutral.roster.find(actor=>actor.side===row.side && actor.slot===3);
      Object.assign(result.plans,peer.plans,{AUTO:row.plans.AUTO});
    }
    return result;
  });
  return profile;
}
