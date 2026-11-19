import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';

const read = rel => readFileSync(new URL('../' + rel, import.meta.url));
const json = rel => JSON.parse(read(rel));
const raw = read('docs/robot/cad/own-zone.glb');
assert.equal(raw.toString('ascii', 0, 4), 'glTF');
assert.equal(raw.readUInt32LE(8), raw.length);
const jsonEnd = 20 + raw.readUInt32LE(12);
const gltf = JSON.parse(raw.toString('utf8', 20, jsonEnd));
const binStart = jsonEnd + 8;
const looks = json('cad/own-zone-upper/appearances.json');
const study = json('experiments/own-zone-cycle/single-piece.json');
const replay = json('experiments/own-zone-cycle/replay.json');
const sourceHash = createHash('sha256').update(read('cad/own-zone-upper/own-zone-public.step')).digest('hex');
assert.equal(looks.sourceSha256, sourceHash);
assert.equal(study.cadSha256, sourceHash);
assert.equal(looks.solids.length, 117);
for (const part of looks.solids) assert.equal(gltf.nodes.filter(n => n.name === part.id && n.mesh != null).length, 1, part.id);
const sameBall = gltf.nodes.findIndex(n => n.name === 'One nominal FUEL');
assert.ok(sameBall >= 0);
const byName = gltf.animations.map(a => a.name);
assert.deepEqual(byName, ['Pickup and lift', 'Release and HUB entry']);

function positions(clip) {
  const channels = clip.channels.filter(c => c.target.node === sameBall && c.target.path === 'translation');
  assert.equal(channels.length, 1);
  const a = gltf.accessors[clip.samplers[channels[0].sampler].output];
  assert.equal(a.type, 'VEC3');
  const start = binStart + (gltf.bufferViews[a.bufferView].byteOffset ?? 0);
  const xyz = key => [0, 1, 2].map(j => raw.readFloatLE(start + (3 * key + j) * 4));
  return {start: xyz(0), end: xyz(a.count - 1)};
}
const pickup = positions(gltf.animations[0]);
const release = positions(gltf.animations[1]);
assert.deepEqual(pickup.end, release.start);
assert.ok(Math.abs(pickup.end[1] - .540) < .001);
assert.ok(replay.atPickup < replay.atLift && replay.atLift < replay.atRelease);
assert.equal(study.grid.length, 9);
assert.equal(study.grid.filter(r => r.flight.outcome === 'clear').length, 2);
assert.ok(study.grid.filter(r => r.flight.outcome !== 'clear').every(r => r.flight.apexM[2] < study.registeredHub.centerM[2]));
for (const run of Object.values(study.controls)) assert.equal(run.lifted, null);
for (const trial of study.refinements) assert.ok(Object.keys(trial.field.contacts).some(name => name.includes('Bottom Plate')));
console.log('117 source-matched solids, continuous two-clip FUEL, nine wheel conditions, three controls, two field refinements.');
