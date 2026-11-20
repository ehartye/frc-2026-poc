import assert from 'node:assert/strict';
import {physicalMatchProfile} from './profile.mjs';

const {field,rehearsal} = await physicalMatchProfile();
const stations = new Map(rehearsal.stations.map(s => [s.id,s]));
const placed=[];
for (const station of stations.values()) {
  if (!station.floor) continue;
  const {radiusIn,positions}=station.floor;
  assert.equal(positions.length, station.stock, station.id+' stock');
  for (const [x,y] of positions) {
    assert.ok(x>=radiusIn && x<=field.length-radiusIn && y>=radiusIn && y<=field.width-radiusIn);
    for (const other of placed) {
      assert.ok(Math.hypot(x-other.x,y-other.y)+0.0001>=radiusIn+other.r, station.id+' floor overlap');
    }
    placed.push({x,y,r:radiusIn});
  }
}
assert.equal(placed.length,408);
const defaultRoster=rehearsal.defaults.roster;
for (const side of ['blue','red']) {
  const rows=defaultRoster.filter(r=>r.side===side);
  assert.deepEqual(rows.map(r=>r.slot).sort(),[1,2,3]);
  assert.equal(new Set(rows.map(r=>r.plans.Transition)).size,3);
  assert.equal(new Set(rows.map(r=>r.preload.station)).size,3);
  assert.equal(new Set(rows.map(r=>rehearsal.programs[r.plans.AUTO].steps.at(-1).at.join())).size,3);
  for (const row of rows) {
    assert.equal(stations.get(row.preload.station).side,side);
    assert.equal(row.preload.quantity,8);
    assert.ok(row.preload.quantity<=row.capacity);
  }
  assert.equal(stations.get(side+'-outpost').stock,24);
  assert.equal(stations.get(side+'-outpost').service.capacity,1);
  assert.deepEqual(stations.get(side+'-outpost').service.phases,rehearsal.periods.map(p=>p.name));
}
assert.equal(placed.length+48+48,504);
console.log('408 separated loose FUEL, 48 distinct preloads and 48 queued at two operators. All six AUTO allocations and default jobs are distinct per alliance.');
