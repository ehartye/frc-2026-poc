import assert from 'node:assert/strict';
const base = process.argv[2];
if (!base) throw Error('Supply the site URL.');
async function get(file) { return fetch(new URL(file,base),{cache:'no-store'}); }
const home = await get('./');
assert.equal(home.status,200);
const html = await home.text();
assert.match(html,/Robot CAD under review/);
assert.doesNotMatch(html,/<model-viewer|\.(?:f3d|step|glb)["']/i);
for(const page of ['field-lab.html','depot-lanes/','alliance-roles.html']){
  const response=await get(page);
  assert.equal(response.status,200,page);
  assert.match(await response.text(),/id="replayField"/,page);
}
for(const file of ['assembly/display.glb','assembly/display.f3d','assembly/display.step','assembly/assembly.png',
  'robot/','robot/orbit.html','robot/tower.html','robot/tower-climb.glb','fixture/','foundation/foundation-student.f3d',
  'evidence/','chassis/']){
  assert.equal((await get(file)).status,404,file);
}
console.log('Strategy and all three lab routes are available. Withheld CAD routes return 404.');
