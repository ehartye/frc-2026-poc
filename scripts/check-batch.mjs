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

