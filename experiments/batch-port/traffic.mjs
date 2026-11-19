import {readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const [plugin, output] = process.argv.slice(2);
if (!output) throw Error('Usage: node traffic.mjs PLUGIN OUTPUT');
const acquire = async name => JSON.parse(await readFile(new URL(name, import.meta.url)));
const field = await acquire('../../kickoff/rules-model.json');
const old = await acquire('../own-zone-cycle/approach-comparison.json');
const pose = old.configs.find(c => c.offsetM === .25);
const {createFieldRehearsal} =
    await import(pathToFileURL(path.resolve(plugin, 'scripts/field-rehearsal.mjs')));
const {createMatchSeries} =
    await import(pathToFileURL(path.resolve(plugin, 'scripts/rehearsal-series-core.mjs')));
const engine = createFieldRehearsal(field);
const match = field.rehearsal.series.matches.find(m => m.id === old.scenario);
const rows = [];
for (const [name, start, deadline] of [
         ['selected', 13, 25], ['one-second settle', 11, 25],
         ['stock already at destination', 8, 25]]) {
  const trial = createMatchSeries(engine, [match]);
  trial.advance(30 + start);
  const own = {...trial.sim.robots.find(r => r.id === 'B2'), heading: pose.headingDeg};
  const overlaps = [];
  for (let i = 0; i < Math.round((deadline - start) / engine.dt); i++) {
    const peers = trial.sim.robots.filter(r => r.id !== 'B2').map(r => ({...r, p: [...r.p]}));
    trial.advance(engine.dt);
    for (const p of peers) {
      const next = trial.sim.robots.find(r => r.id === p.id);
      if (engine.geom.robotContact(pose.poseIn, pose.poseIn, own, p.p, next.p, p) !== null) {
        const previous = overlaps.at(-1);
        if (previous?.peer === p.id && Math.abs(previous.toS - (start + i * engine.dt)) < 1e-8)
          previous.toS = start + (i + 1) * engine.dt;
        else
          overlaps.push(
              {peer: p.id, fromS: start + i * engine.dt, toS: start + (i + 1) * engine.dt});
      }
    }
  }
  rows.push({name, startShiftS: start, deadlineShiftS: deadline, overlaps});
}
await writeFile(
    output,
    JSON.stringify(
        {
          scenario: match.id,
          phase: old.period,
          stoppedPoseIn: pose.poseIn,
          headingDeg: pose.headingDeg,
          robotEnvelope:
              '26.77 in square frame, 2.99 in bumpers, bound to original standing R2C. Recheck hardware if candidate exceeds these bounds.',
          rows
        },
        null, 2) +
        '\n');
console.log(rows);
