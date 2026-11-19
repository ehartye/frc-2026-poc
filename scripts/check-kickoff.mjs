import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';

// Call with the installed Agent FRC plugin root.
const plugin = process.argv[2];
if (!plugin) throw Error('Usage: node scripts/check-kickoff.mjs PATH_TO_AGENT_FRC');
const root = fileURLToPath(new URL('../kickoff/', import.meta.url));
const read = name => readFile(path.join(root,name),'utf8');
const load = name => import(pathToFileURL(path.resolve(plugin,'scripts',name)));
const {compileRules} = await load('rules.mjs');
const {analyzeWindow} = await load('kickoff-window.mjs');
const {createFieldRehearsal} = await load('field-rehearsal.mjs');
const registerText = await read('rule-register.json');
const profile = JSON.parse(await read('field-profile.json'));
const model = JSON.parse(await read('rules-model.json'));
const generated = compileRules(JSON.parse(registerText),profile);
generated.ruleRegisterSha256 = createHash('sha256').update(registerText).digest('hex');
assert.deepEqual(model,generated);

const periods = model.scoring.phases;
assert.equal(periods.reduce((sum,p)=>sum+p.seconds,0),160);
for (const target of model.scoring.targets) {
  assert.equal(periods.reduce((sum,p,i)=>sum+p.seconds*target.points[i],0),110);
}
const distribution = model.scoring.initialDistribution;
const fixed = distribution.depots*distribution.perDepot + distribution.outposts*distribution.perOutpost;
for (let onboard=0; onboard<=distribution.robots*distribution.maxPerRobot; onboard++) {
  const neutral=model.scoring.inventory[0].total-fixed-onboard;
  assert.ok(neutral>=distribution.neutralAtFullPreload && neutral<=distribution.neutralAtZeroPreload);
}
const base = {stock:504,opening:0,incoming:24,goal:24,window:25,cycle:1,arrival:5,setup:3,travel:5,points:1,cap:null,delivery:'staged'};
const windows = [
  ['AUTO preload', {...base,opening:8,incoming:0,goal:8,window:20,arrival:0,setup:2,travel:3}],
  ['Active shift, one per second', base],
  ['Active shift, two per second', {...base,cycle:0.5}],
  ['Five extra seconds in traffic', {...base,cycle:0.5,travel:10}],
  ['Late supply at second 18', {...base,cycle:0.5,arrival:18}],
  ['Same delivery, inactive HUB', {...base,cycle:0.5,points:0}],
  ['Single-piece return shuttle', {...base,delivery:'shuttle',cycle:0.5,travel:2.5,returnTravel:2.5}]
].map(([name,inputs])=>({name,inputs,result:analyzeWindow(inputs)}));
assert.deepEqual(windows.map(w=>w.result.delivered),[8,17,24,24,14,24,4]);
assert.equal(windows[5].result.points,0);

const engine = createFieldRehearsal(model);
const body = engine.defaults('blue',1);
const line=[[122,32],[240,32]];
const clearance = [
  ['Baseline',body],
  ['Taller trial',{...body,height:24}],
  ['Wider angled trial',{...body,width:30,length:25,bumper:4.5,heading:45}]
].map(([name,b])=>({name,dimensions:[b.length,b.width,b.height],bumper:b.bumper,heading:b.heading,result:engine.assessRoute(line,b)}));
assert.deepEqual(clearance.map(c=>c.result.status),['clear','blocked','blocked']);
const roster=['blue','red'].flatMap(side=>[1,2,3].map(slot=>engine.defaults(side,slot)));
const sim=engine.create(roster);
for (let i=0;i<periods.length;i++) {
  sim.paused=false;
  engine.advance(sim,periods[i].seconds+1);
  assert.equal(sim.phaseHistory[i].seconds,periods[i].seconds);
  if (i<periods.length-1) engine.nextPhase(sim);
}
const traffic=model.routeHypotheses.find(r=>r.phase==='Shift 1' && r.destination==='odd');
const evidence={scope:'Agent-run kickoff box trials. Student decision pending.',windows,clearance,traffic,match:sim.phaseHistory};
console.log(JSON.stringify(evidence,(_key,value)=>value===Infinity?'unattainable at any service rate':value,2));
