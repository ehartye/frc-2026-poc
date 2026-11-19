import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';

const read = (file) => readFileSync(new URL('../kickoff/'+file,import.meta.url));
const field = JSON.parse(read('rules-model.json'));
const receipt = JSON.parse(read('match-series.json'));
const register = JSON.parse(read('rule-register.json'));
assert.equal(receipt.profileSha256,createHash('sha256').update(read('rules-model.json')).digest('hex'));
assert.equal(field.ruleRegisterSha256,createHash('sha256').update(read('rule-register.json')).digest('hex'));
assert.equal(register.edition,field.edition);
assert.equal(receipt.stepS,0.05);
assert.equal(receipt.playbackRate,10);
assert.equal(receipt.modelSeconds,480);
assert.equal(receipt.playbackSeconds,48);
assert.equal(receipt.matches.length,3);
const seen = new Set();
const leaders = new Set();
for (const match of receipt.matches) {
  assert.equal(match.roster.length,6);
  assert.deepEqual(match.periods.map(p=>[p.phase,p.seconds]),field.rehearsal.periods.map(p=>[p.name,p.seconds]));
  const game=match.game;
  const remaining = [...Object.values(game.stock).flat(),...Object.values(game.cargo).flat(),...game.returning.map(r=>r.piece),...game.terminal];
  const original = Object.entries(game.initial).flatMap(([id,n])=>Array.from({length:n},(_,i)=>id+'/'+(i+1)));
  assert.equal(original.length,504);
  assert.deepEqual(remaining.map(p=>p.id).sort(),original.sort());
  const first=game.firstPeriodCount;
  const leader=first.blue>first.red?'blue':first.red>first.blue?'red':game.tieWinner;
  leaders.add(first.blue===first.red?'tie':leader);
  const totals={blue:0,red:0};
  for (const e of game.events) {
    const side=e.robot.startsWith('B')?'blue':'red';
    seen.add(side+' '+e.outcome);
    if(e.operation!=='attempt'||!e.pieces.length)continue;
    assert.equal(e.station,side+'-hub');
    const shift=Number(e.phase.split(' ')[1]);
    const active=!e.phase.startsWith('Shift') || (shift%2===0 ? side===leader : side!==leader);
    if (e.outcome==='credited') {
      assert.ok(active);
      assert.equal(e.points,e.pieces.length);
      totals[side]+=e.points;
    } else {
      assert.equal(e.points,0);
      if(e.outcome==='inactive') assert.ok(!active);
    }
  }
  assert.deepEqual(totals,game.score);
  console.log(match.id,game.score,match.periods.length+' complete periods','504 identities conserved');
}
assert.deepEqual([...leaders].sort(),['blue','red','tie']);
for(const side of ['blue','red']) for(const outcome of ['credited','inactive','acquired']) assert.ok(seen.has(side+' '+outcome));
for(const outcome of ['missed','unresolved']) assert.ok([...seen].some(k=>k.endsWith(' '+outcome)));
