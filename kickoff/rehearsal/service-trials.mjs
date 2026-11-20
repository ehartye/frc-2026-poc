import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {physicalMatchProfile} from './profile.mjs';

const [builder, output]=process.argv.slice(2);
if(!builder||!output) throw Error('Usage: node kickoff/rehearsal/service-trials.mjs AGENT_FRC OUTPUT_JSON');
const {createFieldRehearsal}=await import(pathToFileURL(resolve(builder,'scripts/field-rehearsal.mjs')));
const peak=[];
for(const secondsPerPiece of [0.75,1.5,3]){
  const profile=await physicalMatchProfile({secondsPerPiece});
  const plan=profile.rehearsal,field=createFieldRehearsal(profile);
  const roster=plan.defaults.roster.map(r=>({...field.defaults(r.side,r.slot),...r}));
  const sim=field.create(roster,plan.setups[0],'blue');
  const rows=[];
  for(const phase of plan.periods.slice(0,3)){
    sim.paused=false;
    field.advance(sim,phase.seconds);
    const stats={};
    for(const side of ['blue','red']){
      const station=side+'-outpost';
      const events=sim.game.events.filter(e=>e.station===station);
      const releases=events.filter(e=>e.operation==='release').flatMap(e=>e.pieces);
      const pickups=events.filter(e=>e.operation==='acquire').flatMap(e=>e.pieces);
      assert.equal(new Set(releases).size,releases.length);
      assert.deepEqual(pickups,releases.slice(0,pickups.length));
      assert.equal(sim.game.reserve[station].length+releases.length,24);
      assert.ok(releases.length-pickups.length<=1);
      stats[side]={released:releases.length,retrieved:pickups.length,queued:sim.game.reserve[station].length};
    }
    rows.push({period:phase.name,bySide:stats});
    if(phase!==plan.periods[2])field.nextPhase(sim);
  }
  peak.push({secondsPerPiece,rows});
}
console.log(JSON.stringify(peak));
await writeFile(output,JSON.stringify({scope:'One selected default 3v3 roster from AUTO through the first 25-second shift; outlet occupancy limited to one physical piece each.',trials:peak},null,2)+'\n');
