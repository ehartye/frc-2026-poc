import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';

const read=file=>readFileSync(new URL('../'+file,import.meta.url));
const json=file=>JSON.parse(read(file));
const hash=file=>createHash('sha256').update(read(file)).digest('hex');
const folder='experiments/tower-climb/';
const native=json('cad/tower-lift/native-reopen.json');
const still=json('cad/archived-views/robot/cad/receipt.json');
assert.equal(native.stage,'complete');
assert.equal(native.documentsRestored,true);
assert.equal(native.archiveSha256,hash('cad/tower-lift/tower-l1.f3d'));
assert.equal(native.stepSha256,hash('cad/tower-lift/tower-l1.step'));
assert.equal(still.sourceSha256,native.stepSha256);
assert.equal(still.solids,159);
assert.ok(native.rows.some(r=>r.lowerMm===100));
assert.equal(native.joints['Tower load stroke'].travelMm,115);
assert.ok(native.rows.every(r=>r.maximumBoundsErrorMm<0.05));
const clear=json(folder+'clearance.json');
for(const r of clear.filter(r=>r.lowerMm<=100))assert.equal(r.intersections.length,0);
assert.equal(clear.find(r=>r.lowerMm===115).intersections.length,3);
const field=json(folder+'field-clearance.json');
assert.equal(field.samples,441);
assert.equal(field.entryTravelMm,350);
assert.deepEqual(field.unexpected,{});
const extension=json(folder+'extension.json');
assert.ok(Math.abs(extension.minimumEngagedTurns-5)<1e-7);
assert.equal(extension.minimumGuideOverlapMm,87);
const controls=json(folder+'support.json');
for(const name of ['nominal','finer','loaded']){
  const run=controls.find(r=>r.name===name);
  assert.equal(run.conditionalTeleopPoints,10);
  assert.ok(run.atAssessment.tireGapM>.048 && run.atAssessment.baseGapM>.074);
  assert.equal(run.atAssessment.wheelN,0);
  assert.equal(run.atAssessment.down,0.1);
}
for(const name of ['early-cut','stalled-drive','missed-rung'])
  assert.equal(controls.find(r=>r.name===name).conditionalTeleopPoints,0);
const bytes=read('cad/archived-views/robot/cad/tower-climb.glb');
const gltf=JSON.parse(bytes.subarray(20,20+bytes.readUInt32LE(12)).toString());
const bin=bytes.subarray(20+bytes.readUInt32LE(12)+8);
assert.equal(gltf.animations.length,1);
const clip=gltf.animations[0];
const time=json(folder+'motion.json');
const accessor=id=>{
 const a=gltf.accessors[id],view=gltf.bufferViews[a.bufferView];
 return Array.from({length:a.count*({SCALAR:1,VEC3:3,VEC4:4}[a.type])},(_,i)=>bin.readFloatLE((view.byteOffset??0)+(a.byteOffset??0)+4*i));
};
for(const [name,property,axis,expected] of [['Lift carriage','translation',1,r=>-r.down],['Deploying hooks','translation',0,r=>-r.deploy],['Hung R2C robot','translation',1,r=>.320+r.z]]){
 const channel=clip.channels.find(c=>gltf.nodes[c.target.node].name===name&&c.target.path===property);
 const s=clip.samplers[channel.sampler],times=accessor(s.input),values=accessor(s.output);
 assert.equal(times.length,time.length);
 for(const [i,row] of time.entries()){
   assert.ok(Math.abs(times[i]-row.t)<1e-5);
   assert.ok(Math.abs(values[i*3+axis]-expected(row))<1e-6);
 }
}
const roles=json('kickoff/rules-model.json').rehearsal.endgame.actions;
for(const a of roles.filter(a=>a.points>10))assert.deepEqual(a.eligibleRobots,['B1','R1']);
console.log('159 reopened solids, two native sliders, 100 mm working lift, loaded and failed controls, all 441 motion samples.');
