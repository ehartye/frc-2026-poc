import {readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
const [plugin, output] = process.argv.slice(2);
if (!output) throw Error('Usage: node score_approaches.mjs PLUGIN OUTPUT');
const root = fileURLToPath(new URL('../../', import.meta.url));
const json = async rel => JSON.parse(await readFile(path.join(root, rel), 'utf8'));
const {createMatchSeries} = await import(pathToFileURL(path.resolve(plugin, 'scripts/rehearsal-series-core.mjs')));
const {createFieldRehearsal} = await import(pathToFileURL(path.resolve(plugin, 'scripts/field-rehearsal.mjs')));
const field = await json('kickoff/rules-model.json');
const study = await json('experiments/own-zone-cycle/single-piece.json');
const strategy = await json('kickoff/selected-strategy.json');
const source = field.rehearsal.programs['shift-depot'].steps.at(-1).at;
const heading = study.refinements.at(-1).flight.headingRad;
const along = [Math.cos(heading), Math.sin(heading)];
const hub = field.rehearsal.stations.find(s => s.id === 'blue-hub');
const start = strategy.case.stockReadyAtSource + strategy.case.loadedTravel + strategy.case.settle;
const period = 'Shift 1';
const cutoff = field.rehearsal.periods.slice(0, 2).reduce((n, p) => n + p.seconds, 0);
const engine = createFieldRehearsal(field);
const match = field.rehearsal.series.matches.find(m => m.id === 'Neutral return');
if (!match) throw Error('Missing comparison scenario');
const configs = [-.25, 0, .25].map(offset => {
  const pose = source.map((v, i) => v + offset / .0254 * along[i]);
  const direction = along;
  const yaw = Math.atan2(direction[1], direction[0]) * 180 / Math.PI;
  const robot = {...engine.defaults('blue', 2), ...match.roster.find(r => r.side === 'blue' && r.slot === 2), heading: yaw};
  const radius = Math.hypot(robot.length / 2 + robot.bumper, robot.width / 2 + robot.bumper);
  const approach = pose.map((v, i) => v - study.refinements.at(-1).mechanism.release.chassisTravelM / .0254 * along[i]);
  const poly = field.rehearsal.obstacles.map(o => {
    const xs = o.poly.map(p => p[0]), ys = o.poly.map(p => p[1]);
    const gap = Math.min(...Array.from({length:101}, (_, i) => {
      const q = approach.map((v, j) => v + (pose[j]-v)*i/100);
      return Math.hypot(Math.max(0, Math.min(...xs)-q[0], q[0]-Math.max(...xs)), Math.max(0, Math.min(...ys)-q[1], q[1]-Math.max(...ys))) - radius;
    })) - Math.hypot(pose[0]-approach[0],pose[1]-approach[1])/200;
    return {name:o.name, gap};
  });
  const evaluated = study.grid.map(row => {
    const f = row.flight;
    if (f.firstSpherePassS === undefined) return {condition:[row.contactNperM,row.initialNoLoadFraction],clear:false,apexM:f.apexM[2]};
    const gaps = [];
    for (const t of [f.firstSpherePassS,f.lastSpherePassS]) for (let i=0;i<6;i++) {
      const a = Math.PI/6 + i*Math.PI/3;
      const relative = [0,1].map(j=>f.releaseFieldM[j]+f.velocityFieldMps[j]*t+offset*along[j]-study.registeredHub.centerM[j]);
      gaps.push(.5*.0254*field.fieldFeatures.hubOpening - .5*.0254*field.fieldFeatures.fuelDiameter - Math.cos(a)*relative[0]-Math.sin(a)*relative[1]);
    }
    return {condition:[row.contactNperM,row.initialNoLoadFraction], clear:Math.min(...gaps)>0, apertureMarginM:Math.min(...gaps)};
  });
  return {offsetM:offset,poseIn:pose,startIn:approach,headingDeg:yaw,minimumStaticClearanceIn:Math.min(...poly.map(o=>o.gap)),wholeBumperZoneClearanceIn:field.fieldFeatures.allianceZoneDepth-pose[0]-radius,aperture:evaluated,minimumPeerProjectionGapIn:Infinity,contactTicks:0};
});
const trial = createMatchSeries(engine,[match]);
trial.advance(cutoff + start);
if(trial.sim.phase !== period) throw Error('Clock mismatch');
const blue = trial.sim.robots.find(r=>r.id==='B2');
const travel = study.refinements.at(-1).mechanism.release.chassisTravelM;
const v = .38, decelTime = .35;
const brakeAt = travel/v-decelTime/2;
function ownPosition(c, time) {
  const braking = Math.min(decelTime, Math.max(0, time-brakeAt));
  const moved = v*Math.min(time,brakeAt)+v*(braking-braking**2/(2*decelTime));
  return c.startIn.map((p,j)=>p+along[j]*moved/.0254);
}
function axes(angle) {
  const h=angle*Math.PI/180;
  return [[Math.cos(h),Math.sin(h)],[-Math.sin(h),Math.cos(h)]];
}
const project=(v,n)=>v[0]*n[0]+v[1]*n[1];
function support(robot, n) {
  const [u,v]=axes(robot.heading);
  return (robot.length/2+robot.bumper)*Math.abs(project(u,n))+(robot.width/2+robot.bumper)*Math.abs(project(v,n));
}
for(let i=0;i<Math.round(4.1/engine.dt);i++){
  const peers = trial.sim.robots.filter(r=>r.id!==blue.id).map(r=>({...r,p:[...r.p]}));
  trial.advance(engine.dt);
  for(const c of configs) for(const peer of peers){
    const own={...blue,heading:c.headingDeg};
    const a=ownPosition(c,i*engine.dt), b=ownPosition(c,(i+1)*engine.dt);
    const p=peer.p, q=trial.sim.robots.find(r=>r.id===peer.id).p;
    const gap=Math.max(...[...axes(own.heading),...axes(peer.heading)].flatMap(n=>[-1,1].map(sign=>{
      const x=sign*(project(a,n)-project(p,n)),y=sign*(project(b,n)-project(q,n));
      return Math.min(x,y)-support(own,n)-support(peer,n);
    })))-v/decelTime*engine.dt**2/8/.0254;
    if(engine.geom.robotContact(a,b,own,p,q,peer)!==null)c.contactTicks++;
    if(gap<c.minimumPeerProjectionGapIn) {c.minimumPeerProjectionGapIn=gap;c.limitingPeer=peer.id;}
  }
}
await writeFile(output,JSON.stringify({profile:field.edition,scenario:match.id,period,startS:start,durationS:4.1,activeSide:'blue if red led AUTO',station:hub.id,configs},null,2)+'\n');
console.log(configs.map(c=>[c.offsetM,c.minimumStaticClearanceIn,c.minimumPeerProjectionGapIn,c.contactTicks,c.aperture.filter(x=>x.clear).length]));
