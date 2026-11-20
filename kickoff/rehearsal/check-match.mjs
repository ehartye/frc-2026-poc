import assert from 'node:assert/strict';

/** Replay the 504 physical identities through both operator queues, every bay and both HUBs. */
export function auditMatch(profile, match) {
  const model=profile.rehearsal;
  const game=match.game;
  const supply=model.stations.filter(s=>s.kind==='retrieval');
  const stocks=new Map(supply.map(s=>[s.id,new Set(Array.from({length:s.stock},(_,i)=>s.id+'/'+(i+1)))]));
  const places=new Map([...stocks].flatMap(([station,pieces])=>[...pieces].map(id=>[id,station])));
  const lastHuman=new Map();
  const released=new Set();
  const phaseStart=new Map();
  let time=0;
  for (const phase of model.periods) {phaseStart.set(phase.name,time);time+=phase.seconds;}
  assert.equal(time,160);
  assert.deepEqual(match.periods.map(p=>[p.phase,p.seconds]),model.periods.map(p=>[p.name,p.seconds]));
  const roster=match.roster;
  assert.equal(new Set(roster.map(r=>r.side+'/'+r.slot)).size,6);
  const autoIds=new Set();
  const totals={blue:0,red:0};
  const acquired=Object.fromEntries(roster.map(row=>[row.side[0].toUpperCase()+row.slot,0]));
  for (const row of roster) {
    const robot=row.side[0].toUpperCase()+row.slot;
    const source=stocks.get(row.preload.station);
    for (const id of [...source].slice(0,row.preload.quantity)) places.set(id,robot);
  }
  for (const event of game.events) {
    const {robot,station,phase,operation,outcome,pieces}=event;
    const now=phaseStart.get(phase)+event.timeS;
    if (operation==='release') {
      const source=supply.find(s=>s.id===station);
      assert.equal(robot,'human/'+source.service.operator);
      assert.ok(source.service.phases.includes(phase));
      assert.ok(now-(lastHuman.get(robot)??0)+1e-7>=source.service.secondsPerPiece);
      lastHuman.set(robot,now);
      assert.equal(pieces.length,1);
      for (const id of pieces) {
        assert.ok(stocks.get(station).has(id) && !released.has(id));
        released.add(id);
      }
    }
    if (operation==='acquire' && pieces.length) {
      assert.equal(pieces.length,1);
      const {position:p,mouth:[a,b],radiusIn,robotPosition}=event.contact;
      const dx=b[0]-a[0],dy=b[1]-a[1];
      const u=Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy)));
      assert.ok(Math.hypot(p[0]-a[0]-u*dx,p[1]-a[1]-u*dy)<=radiusIn+1e-6);
      const mid=a.map((v,i)=>(v+b[i])/2);
      assert.ok((p[0]-mid[0])*(mid[0]-robotPosition[0])+(p[1]-mid[1])*(mid[1]-robotPosition[1])>=-1e-6);
      for (const id of pieces) {
        if (station.endsWith('-outpost')) assert.ok(released.has(id));
        assert.ok(places.has(id));
        if (places.get(id)!==station) assert.equal(places.get(id),'returned');
        places.set(id,robot);
      }
      acquired[robot]+=pieces.length;
    }
    if (operation==='attempt' && pieces.length) {
      for (const id of pieces) {
        assert.equal(places.get(id),robot);
        if (phase==='AUTO') {
          assert.ok(!autoIds.has(id));
          assert.ok(id.startsWith(robot[0]==='B'?'blue-preload-'+robot[1]+'/':'red-preload-'+robot[1]+'/'));
          autoIds.add(id);
        }
        places.set(id,['credited','inactive'].includes(outcome)?'returned':'terminal');
      }
      if (outcome==='credited') totals[robot[0]==='B'?'blue':'red']+=pieces.length;
    }
  }
  const stock=Object.values(game.stock).flat(), reserve=Object.values(game.reserve).flat();
  const cargo=Object.values(game.cargo).flat();
  const all=[...stock,...reserve,...cargo,...game.returning.map(x=>x.piece),...game.terminal].map(x=>x.id);
  assert.deepEqual(all.sort(),[...places.keys()].sort());
  const physical=new Set(supply.filter(s=>s.floor||s.service).map(s=>s.id));
  assert.deepEqual(game.motion.pieces.map(p=>p.id).sort(),
    Object.entries(game.stock).filter(([id])=>physical.has(id)).flatMap(([,rows])=>rows.map(p=>p.id)).sort());
  for(const side of ['blue','red']) {
    assert.equal(totals[side],game.endgame.ordinaryScore[side]);
    assert.equal(totals[side]+game.endgame.terminalScore[side],game.score[side]);
  }
  return {id:match.id,score:game.score,auto:game.firstPeriodCount,fuel:totals,
    tower:game.endgame.terminalScore,acquired,individualChuteReleases:released.size,
    final:{floor:game.motion.pieces.length,operators:reserve.length,bays:cargo.length,returning:game.returning.length,terminal:game.terminal.length},
    minimumModeledSecondsBetweenHumanReleases:model.stations.find(s=>s.service).service.secondsPerPiece};
}
