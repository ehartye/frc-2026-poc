import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const read = async path => JSON.parse(await readFile(new URL(path,import.meta.url),'utf8'));
const data = await read('../experiments/batch-port/results.json');
const single = await read('../experiments/own-zone-cycle/single-piece.json');
assert.equal(data.studentCadSha256,single.cadSha256);
assert.equal(data.fieldSourceSha256,single.supplierFieldSha256);
for (const t of [...data.trials,data.control]) {
  assert.equal(new Set(t.rows.map(p=>p.id)).size,24);
  for (const p of t.rows) {
    if (p.apertureS!==null) assert.ok(p.releaseS<p.apertureS);
    if (p.sharedClearS!==null) {
      assert.ok(p.apertureS!==null && p.apertureS<p.sharedClearS);
      assert.ok(p.sensorInterruptions.includes(p.channel));
      assert.ok(Math.abs(p.latestStrictReleaseShiftS-(25-p.sharedClearS+p.releaseS))<1e-8);
    }
    assert.equal(p.countWithin,p.sharedClearS!==null && p.sharedClearS<12);
    assert.equal(p.processingOnly,p.sharedClearS!==null && p.apertureS<12 && p.sharedClearS>=12 && p.sharedClearS<=15);
  }
  assert.deepEqual(t.aperturesBySlot,[1,2,3,4,5,6].map(s=>t.rows.filter(p=>p.slot===s && p.apertureS!==null).length));
}
assert.ok(data.control.pieceContacts===false && data.trials.every(t=>t.pieceContacts));
const common=field=>data.trials[0].rows.filter(p=>p[field] && data.trials[1].rows.some(q=>q.id===p.id && q[field])).map(p=>p.id).sort();
assert.deepEqual(data.bothInside,common('countWithin'));
assert.deepEqual(data.bothComplete,common('sharedClearS'));
assert.deepEqual(data.bothInside,['M0-06','M1-12','M2-16']);
assert.deepEqual(data.control.aperturesBySlot,[4,0,4,0,4,4]);
console.log('24 distinct releases per trial; three shared active IDs and five shared complete passages.');


const loading = await read('../experiments/depot-loading/results.json');
const source = await read('../experiments/depot-loading/stock-register.json');
const groundIds = new Set(source.floorStock.map(p=>p.id));
assert.equal(groundIds.size,24);
assert.equal(source.sourceFieldSha256,single.supplierFieldSha256);
for (const name of ['pair-fine','pair-coarse']) {
  const run=loading.trials[name];
  assert.equal(new Set(run.initialIds).size,32);
  assert.equal(run.retainedPreloads.length,8);
  assert.deepEqual(run.retainedSourceIds.toSorted(),['blue-depot-03','blue-depot-04']);
  assert.ok(run.retainedSourceIds.every(id=>groundIds.has(id)));
  assert.deepEqual(run.finalRetained.map(p=>p.id).toSorted(),[...run.retainedSourceIds,...run.retainedPreloads].toSorted());
}
assert.equal(loading.trials['pair-locked'].retainedSourceIds.length,0);
assert.ok(loading.clocks.every(c=>c.stillOnboard+c.autoPreloadsSpent===8 && c.sourcePiecesNeeded+c.stillOnboard===24));
console.log('Two registered DEPOT IDs plus eight independent preloads retained in both refinements; locked gates retain zero new stock.');
