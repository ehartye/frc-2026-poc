import {cp, mkdir, readFile, readdir, rename, rmdir, stat, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';
import {gunzipSync} from 'node:zlib';

import {styleOrbit,styleShowcase} from './showcase-navigation.mjs';

const [plugin, output] = process.argv.slice(2);
if (!plugin || !output) throw Error('Usage: node scripts/build-showcase.mjs PLUGIN_ROOT NEW_SITE_DIRECTORY');
const root = fileURLToPath(new URL('../', import.meta.url));
const at = file => path.join(root, file);
const destination = path.resolve(output);
await mkdir(destination, {recursive: false});

// The rough-draft showcase is built exactly as it was published, then moved whole into the detailed design archive.
// Its sources stay registered model files, so the archive keeps the bytes the approved site held.
const {buildHighlights} = await import(pathToFileURL(path.resolve(plugin, 'scripts/robot-highlights.mjs')));
await buildHighlights(at('highlights.json'), path.join(destination, 'evidence'));
await cp(at('docs/showcase/style.css'),path.join(destination,'style.css'));
const layout=JSON.parse(await readFile(at('project-layout.json'),'utf8'));
const handoff=JSON.parse(await readFile(at(layout.publicFusionHandoff),'utf8'));
const download='evidence/evidence/'+handoff.archive.sha256+'.f3d';
const {createHash}=await import('node:crypto');
if(createHash('sha256').update(await readFile(path.join(destination,download))).digest('hex')!==handoff.archive.sha256)
  throw Error('Student download differs from the independently reopened assembly');
const home=(await readFile(at('docs/showcase/index.html'),'utf8')).replace('__PUBLIC_FUSION__',download);
await writeFile(path.join(destination,'index.html'),styleShowcase(home,'./','model'));
const featured = at('cad/showcase-red');
const provenance = JSON.parse(await readFile(path.join(featured, 'provenance.json'), 'utf8'));
const assembly = path.join(destination, 'assembly');
await mkdir(assembly);
for (const name of ['display.f3d', 'display.step', 'display.glb', 'assembly.png']) {
  const bytes = await readFile(path.join(featured, name));
  if (createHash('sha256').update(bytes).digest('hex') !== provenance.sha256[name])
    throw Error('Featured Fusion export changed: ' + name);
  await writeFile(path.join(assembly, name), bytes);
}
await cp(path.join(featured, 'provenance.json'), path.join(assembly, 'provenance.json'));
await cp(at('docs/showcase/assembly-view.js'), path.join(destination, 'assembly-view.js'));
const config = JSON.parse(await readFile(at('kickoff/selected-strategy.json'), 'utf8'));
const study = await readFile(at('docs/showcase/study.js'), 'utf8');
await writeFile(path.join(destination, 'study.js'), study.replace('__CLOCK__', JSON.stringify(config.case)));
await cp(at('kickoff/rule-register.json'),path.join(destination,'rule-register.json'));
execFileSync(process.execPath,[at('kickoff/rehearsal/build.mjs'),plugin,destination],{stdio:'inherit'});
await cp(at('docs/robot/historical-fixture'), path.join(destination, 'fixture'), {recursive: true});
await cp(at('docs/robot/cad'), path.join(destination, 'robot'), {recursive: true});
await cp(at('docs/robot/r1-chassis'), path.join(destination, 'chassis'), {recursive: true});
await cp(at('docs/vendor'), path.join(destination, 'vendor'), {recursive: true});
await cp(at('docs/foundation'),path.join(destination,'foundation'),{recursive:true});
for(const [source,name] of [['foundation-student.f3d','foundation-student.f3d'],['foundation-still.png','assembly.png']])
  await cp(at('cad/assembly-release/'+source),path.join(destination,'foundation',name));
await rename(path.join(destination, 'robot/index.html'), path.join(destination, 'robot/orbit.html'));
for(const route of ['robot/orbit.html','chassis/index.html','fixture/index.html','foundation/index.html']){
  const file=path.join(destination,route);
  await writeFile(file,styleOrbit(await readFile(file,'utf8')));
}
for(const [source,name,section] of [['motion.html','index.html','motion'],['batch.html','batch.html','results'],['tower.html','tower.html','tower']]){
  const html=await readFile(at('docs/showcase/'+source),'utf8');
  await writeFile(path.join(destination,'robot',name),styleShowcase(html,'../',section));
}
for(const file of ['motion.js','batch.js','loading.js','tower.js']) await cp(at('docs/showcase/'+file),path.join(destination,'robot',file));
const {checkChapters} = await import(pathToFileURL(path.resolve(plugin, 'scripts/replay-chapters.mjs')));
const chapters = await checkChapters(at('experiments/own-zone-cycle/motion-chapters.json'), root);
await writeFile(path.join(destination, 'robot/chapters.json'), JSON.stringify(chapters));
await cp(path.resolve(plugin, 'templates/replay-chapter-controls.mjs'), path.join(destination, 'robot/chapter-controls.js'));

await cp(at('experiments/batch-port/results.json'), path.join(destination, 'robot/batch-data.json'));

await cp(at('experiments/depot-loading/results.json'),path.join(destination,'robot/loading-data.json'));

// Withdraw the rough-draft showcase: the committed index declares it, the archive keeps every published file.
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const json=async file=>JSON.parse(await readFile(at(file),'utf8'));
const policy=await json('.github/staged-model-policy.json');
const index=await json('docs/detailed-design/designs.json');
const [design]=index.designs;
const declared=policy.detailedDesigns.withdrawn.find(row=>row.design===design);
if(index.designs.length!==1||index.current!==null||index.designStatus[design]!=='withdrawn'||!declared||index.reason[design]!==declared.reason)
  throw Error('The committed detailed design index must show the one declared design withdrawn and none current');
const tree=path.join(destination,policy.detailedDesigns.root),archive=path.join(tree,'archive',design);
for(const name of declared.files){
  await mkdir(path.dirname(path.join(archive,name)),{recursive:true});
  await rename(path.join(destination,name),path.join(archive,name));
}
async function listing(folder,prefix=''){
  const names=[];
  for(const item of await readdir(folder,{withFileTypes:true})){
    if(item.isDirectory())names.push(...await listing(path.join(folder,item.name),prefix+item.name+'/'));
    else names.push(prefix+item.name);
  }
  return names.sort();
}
// Only the independent field pages and their data stay at their addresses.
async function prune(folder){
  for(const item of await readdir(folder,{withFileTypes:true}))if(item.isDirectory())await prune(path.join(folder,item.name));
  if(folder!==destination&&!(await readdir(folder)).length)await rmdir(folder);
}
await prune(destination);
const field=[...policy.mutableFieldPages,...Object.keys(policy.mutableFieldData)].sort();
const kept=(await listing(destination)).filter(name=>!name.startsWith(policy.detailedDesigns.root+'/'));
if(JSON.stringify(kept)!==JSON.stringify(field))throw Error('Unexpected output beside the field pages: '+kept.filter(name=>!field.includes(name)).join(', '));
for(const name of ['index.html','designs.json'])await cp(at('docs/detailed-design/'+name),path.join(tree,name));

// The entry page and its still follow the primary view: no detailed design is current, so they feature the preliminary design.
const releases=await json('docs/preliminary-design/releases.json');
const release=releases.current,status={'in-progress':'in progress',effective:'effective'}[releases.designStatus?.[release]??'in-progress'];
const record=await json('docs/robot/preliminary-'+release+'.json');
const still=await readFile(at('docs/robot/preliminary-'+release+'.png'));
if(!status||record.release!==release||sha(still)!==record.imageSha256||
  sha(await readFile(at('docs/preliminary-design/releases/'+release+'/receipt.json')))!==record.receiptSha256)
  throw Error('The preliminary still differs from the current release. Regenerate it with preliminary-still.py.');
await mkdir(path.join(destination,'assembly'));
await writeFile(path.join(destination,'assembly/assembly.png'),still);
const text=value=>String(value).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[c]);
const kinds=[[/\.html$/,'Page'],[/\.(f3d|step)$/,'CAD download'],[/\.(glb|stl\.gz)$/,'Display mesh'],[/\.png$/,'Still'],
  [/\.(js|css)$/,'Page script or style'],[/\.json$/,'Data or receipt'],[/./,'Notice']];
const rows=[];
for(const name of await listing(archive)){
  const size=(await stat(path.join(archive,name))).size.toLocaleString('en-US');
  rows.push('<tr><td><a href="'+text(policy.detailedDesigns.root+'/archive/'+design+'/'+name)+'">'+text(name)+'</a></td><td>'+
    kinds.find(([pattern])=>pattern.test(name))[1]+'</td><td class="size">'+size+' bytes</td></tr>');
}
if(rows.length!==declared.files.length)throw Error('The archive must hold exactly the declared files');
const packed=await readFile(at('docs/preliminary-design/releases/'+release+'/review-scene.json.gz'));
if(sha(packed)!==record.sceneSha256)throw Error('The preliminary still was drawn from another review scene');
const fields={status,release,design,count:rows.length,reason:declared.reason,receipt:record.receiptSha256.slice(0,10),
  headline:JSON.parse(gunzipSync(packed)).title,title:record.caption.title,alt:record.caption.alt,pose:record.caption.pose,scope:record.caption.scope};
const page=(await readFile(at('docs/showcase/front-page.html'),'utf8')).replace('<!-- archive-listing -->',rows.join('\n'))
  .replace(/\{\{(\w+)\}\}/g,(match,key)=>{if(!(key in fields))throw Error('Unknown front page field: '+key);return text(fields[key]);});
await writeFile(path.join(destination,'index.html'),page);
