import {cp, mkdir, readFile, rename, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

import {styleOrbit,styleShowcase} from './showcase-navigation.mjs';

const [plugin, output] = process.argv.slice(2);
if (!plugin || !output) throw Error('Usage: node scripts/build-showcase.mjs PLUGIN_ROOT NEW_SITE_DIRECTORY');
const root = fileURLToPath(new URL('../', import.meta.url));
const at = file => path.join(root, file);
const destination = path.resolve(output);
await mkdir(destination, {recursive: false});
const {buildHighlights} = await import(pathToFileURL(path.resolve(plugin, 'scripts/robot-highlights.mjs')));
await buildHighlights(at('highlights.json'), path.join(destination, 'evidence'));
await cp(at('docs/showcase/style.css'),path.join(destination,'style.css'));
await writeFile(path.join(destination,'index.html'),styleShowcase(await readFile(at('docs/showcase/index.html'),'utf8'),'./','model'));
const config = JSON.parse(await readFile(at('kickoff/selected-strategy.json'), 'utf8'));
const study = await readFile(at('docs/showcase/study.js'), 'utf8');
await writeFile(path.join(destination, 'study.js'), study.replace('__CLOCK__', JSON.stringify(config.case)));
for (const name of ['field-lab.html','rule-register.json','match-series.json']) await cp(at('kickoff/' + name), path.join(destination, name));
await cp(at('docs/robot/historical-fixture'), path.join(destination, 'fixture'), {recursive: true});
await cp(at('docs/robot/cad'), path.join(destination, 'robot'), {recursive: true});
await cp(at('docs/robot/r1-chassis'), path.join(destination, 'chassis'), {recursive: true});
await cp(at('docs/vendor'), path.join(destination, 'vendor'), {recursive: true});
await rename(path.join(destination, 'robot/index.html'), path.join(destination, 'robot/orbit.html'));
for(const route of ['robot/orbit.html','chassis/index.html','fixture/index.html']){
  const file=path.join(destination,route);
  await writeFile(file,styleOrbit(await readFile(file,'utf8')));
}
for(const [source,name,section] of [['motion.html','index.html','motion'],['batch.html','batch.html','results']]){
  const html=await readFile(at('docs/showcase/'+source),'utf8');
  await writeFile(path.join(destination,'robot',name),styleShowcase(html,'../',section));
}
for(const file of ['motion.js','batch.js','loading.js']) await cp(at('docs/showcase/'+file),path.join(destination,'robot',file));
const {checkChapters} = await import(pathToFileURL(path.resolve(plugin, 'scripts/replay-chapters.mjs')));
const chapters = await checkChapters(at('experiments/own-zone-cycle/motion-chapters.json'), root);
await writeFile(path.join(destination, 'robot/chapters.json'), JSON.stringify(chapters));
await cp(path.resolve(plugin, 'templates/replay-chapter-controls.mjs'), path.join(destination, 'robot/chapter-controls.js'));

await cp(at('experiments/batch-port/results.json'), path.join(destination, 'robot/batch-data.json'));

await cp(at('experiments/depot-loading/results.json'),path.join(destination,'robot/loading-data.json'));
