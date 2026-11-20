import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {peerLaneProfile} from './peer-lanes.mjs';

const [plugin, destination, physicalProfile] = process.argv.slice(2);
if (!plugin || !destination) throw Error('Usage: node replay-lanes.mjs PLUGIN_ROOT NEW_OUTPUT_DIRECTORY');
const scripts = relative => pathToFileURL(path.resolve(plugin, 'scripts', relative));
const {buildLab} = await import(scripts('kickoff.mjs'));
const {createFieldRehearsal} = await import(scripts('field-rehearsal.mjs'));
const {createMatchSeries} = await import(scripts('rehearsal-series-core.mjs'));
const bytes = await readFile(physicalProfile ?? new URL('../../kickoff/rules-model.json', import.meta.url));
const profile = peerLaneProfile(JSON.parse(bytes));
const field = createFieldRehearsal(profile);
const matches = profile.rehearsal.series.matches;
const seconds = field.periods.reduce((sum, p) => sum + field.phaseSeconds(p.name), 0);
const series = createMatchSeries(field, matches);
series.advance(seconds * matches.length);
assert.equal(series.done, true);
const expected = [[0,0], [4,0], [0,4], [4,4], [24,0], [0,24], [24,24]];
const results = series.results.map((result, index) => {
  const {game} = result;
  const bySide = {};
  for (const side of ['blue', 'red']) {
    const robot = side === 'blue' ? 'B2' : 'R2';
    const admissions = game.events.filter(event => event.robot === robot &&
      event.station === side+'-depot' && event.operation === 'acquire' && event.outcome === 'acquired');
    const pieces = admissions.flatMap(event => event.pieces);
    assert.equal(new Set(pieces).size, pieces.length);
    bySide[side] = {robot, pieces: pieces.length, admissions: admissions.map(({phase, timeS, pieces}) => ({phase, timeS, pieces}))};
  }
  if (physicalProfile) {
    const physicalExpected=[[0,0],[4,0],[0,4],[4,4],[6,0],[0,6],[6,6]];
    assert.deepEqual([bySide.blue.pieces,bySide.red.pieces],physicalExpected[index]);
  } else {
    assert.deepEqual([bySide.blue.pieces, bySide.red.pieces],expected[index]);
  }
  return {id:result.id, score:game.score, depots:bySide};
});
await mkdir(destination, {recursive:true});
await buildLab(profile, path.join(destination, 'index.html'));
await writeFile(path.join(destination, 'results.json'), JSON.stringify({
  rulesProfileSha256:createHash('sha256').update(bytes).digest('hex'),
  secondsPerMatch:seconds, matches:results,
}, null, 2)+'\n', {flag:'wx'});
