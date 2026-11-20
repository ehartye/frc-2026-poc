import {execFileSync} from 'node:child_process';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {dirname,join,resolve} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {physicalMatchProfile} from './profile.mjs';
import {auditMatch} from './check-match.mjs';

const [builder, output] = process.argv.slice(2);
if (!builder || !output) throw Error('Usage: node kickoff/rehearsal/build.mjs AGENT_FRC OUTPUT_DIRECTORY');
const plugin=resolve(builder);
const site=resolve(output);
await mkdir(site,{recursive:true});
const script=name=>join(plugin,'scripts',name);
const file = name=>join(site,name);
const project=resolve(dirname(fileURLToPath(import.meta.url)),'../..');
const {buildLab}=await import(pathToFileURL(script('kickoff.mjs')));
const model=await physicalMatchProfile();
const profilePath=file('match-profile.json');
await writeFile(profilePath,JSON.stringify(model,null,2)+'\n');
await buildLab(model,file('field-lab.html'));
execFileSync(process.execPath,[script('rehearsal-series.mjs'),profilePath,file('match-series.json')],{stdio:'inherit'});
const series=JSON.parse(await readFile(file('match-series.json')));
const summaries=series.matches.map(match=>auditMatch(model,match));
await writeFile(file('match-summary.json'),JSON.stringify({profileSha256:series.profileSha256,
  modelSeconds:series.modelSeconds,playbackSeconds:series.playbackSeconds,matches:summaries},null,2)+'\n');
execFileSync(process.execPath,[script('strategy-lab.mjs'),profilePath,join(project,'experiments/role-and-support/study.json'),
  '--html',file('alliance-roles.html')],{stdio:['ignore','ignore','inherit']});
execFileSync(process.execPath,[join(project,'experiments/role-and-support/replay-lanes.mjs'),plugin,
  file('depot-lanes'),profilePath],{stdio:'inherit'});
