import {cp, mkdir, readFile, readdir, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';

import {styleShowcase} from './showcase-navigation.mjs';

const [plugin, output] = process.argv.slice(2);
if (!plugin || !output) throw Error('Usage: node scripts/build-showcase.mjs PLUGIN_ROOT NEW_SITE_DIRECTORY');
const root = fileURLToPath(new URL('../', import.meta.url));
const at = file => path.join(root, file);
const destination = path.resolve(output);
await mkdir(destination, {recursive: false});
const policy = JSON.parse(await readFile(at('cad-showcase.json'),'utf8')).publication;
if (policy?.status !== 'withheld') throw Error('A verified CAD publication gate is required before enabling model downloads.');
await cp(at('docs/showcase/style.css'),path.join(destination,'style.css'));
const home=await readFile(at('docs/showcase/index.html'),'utf8');
await writeFile(path.join(destination,'index.html'),styleShowcase(home,'./','strategy'));
const config = JSON.parse(await readFile(at('kickoff/selected-strategy.json'), 'utf8'));
const study = await readFile(at('docs/showcase/study.js'), 'utf8');
await writeFile(path.join(destination, 'study.js'), study.replace('__CLOCK__', JSON.stringify(config.case)));
for (const name of ['field-lab.html','rule-register.json','match-series.json']) await cp(at('kickoff/' + name), path.join(destination, name));
execFileSync(process.execPath, [at('experiments/role-and-support/replay-lanes.mjs'), plugin, path.join(destination, 'depot-lanes')], {stdio:'inherit'});
execFileSync(process.execPath, [
  path.resolve(plugin, 'scripts/strategy-lab.mjs'), at('kickoff/rules-model.json'),
  at('experiments/role-and-support/study.json'), '--html', path.join(destination, 'alliance-roles.html'),
], {stdio:['ignore','ignore','inherit']});
// Every deployed file is explicitly approved, including generated subdirectories.
const permitted = new Set(['index.html','style.css','study.js','field-lab.html','rule-register.json',
  'match-series.json','alliance-roles.html','depot-lanes/index.html','depot-lanes/results.json']);
async function checkOutput(directory) {
  for (const entry of await readdir(directory,{withFileTypes:true})) {
    const file=path.join(directory,entry.name);
    if (entry.isDirectory()) await checkOutput(file);
    else if (!permitted.has(path.relative(destination,file).split(path.sep).join('/'))) throw Error('Unapproved Pages asset: '+file);
  }
}
await checkOutput(destination);
