// Run the production pre-upload shell block on an ordinary issued teaching model.
import assert from 'node:assert/strict';
import {generateKeyPairSync,sign} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {mkdtempSync,mkdirSync,readFileSync,writeFileSync,rmSync,cpSync} from 'node:fs';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const [verifier,sourceRoot,sourcePath,stageRoot,stagePath,keyPath]=process.argv.slice(2);
if(!keyPath)throw Error('Usage: node signed-showcase.mjs VERIFIER SOURCE_ROOT SOURCE_PACKET STAGED_ROOT STAGED_PACKET REVIEWER_PUBLIC_KEY');
const read=p=>readFileSync(p);
const source=JSON.parse(read(sourcePath)),staged=JSON.parse(read(stagePath));
assert.equal(source.body.project,staged.body.project);
const project=source.body.project,key=read(keyPath).toString();
const folder=mkdtempSync(path.join(tmpdir(),'season-showcase-control-'));
const workflow=fileURLToPath(new URL('../.github/workflows/robot-showcase.yml',import.meta.url));
const bash=process.env.BASH_BINARY||(process.platform==='win32'?'C:/Program Files/Git/bin/bash.exe':'bash');
const put=(rel,data)=>{
  const dest=path.resolve(folder,rel);
  assert(dest.startsWith(folder+path.sep));
  mkdirSync(path.dirname(dest),{recursive:true});writeFileSync(dest,data);
};
const json=(rel,value)=>put(rel,JSON.stringify(value));
function run(command,args,options={}){
  return spawnSync(command,args,{cwd:folder,encoding:'utf8',...options});
}
function git(...args){
  const r=run('git',['-C','project',...args]);
  assert.equal(r.status,0,r.stderr);return r.stdout.trim();
}
const sourceFiles=source.body.files.map(f=>f.path),stageFiles=staged.body.files.map(f=>f.path);
const sourcePacket='project/.github/model-release/source.json',stagePacket='project/.github/model-release/staged.json';
function promote(){
  for(const name of sourceFiles)put('project/'+name,read(path.join(sourceRoot,name)));
  for(const name of stageFiles)put('runner/showcase/'+name,read(path.join(stageRoot,name)));
  put(sourcePacket,read(sourcePath));put(stagePacket,read(stagePath));
}
const selector='model-selector.html';
function check(label,success,fragment='',reviewKey=key,commitSource=true){
  if(commitSource){
    git('add','-A');
    if(git('diff','--cached','--name-only')){
      git('-c','user.name=Local Test','-c','user.email=local-test@example.invalid','commit','-qm',label);
    }
  }
  const r=run(bash,['gate.sh'],{env:{...process.env,REVIEW_PUBLIC_KEY:reviewKey,
    RUNNER_TEMP:'runner',FRC_VERIFIED_FIELD_ROOT:'runner/field'}});
  const output=r.stdout+r.stderr;assert.equal(r.status===0,success,label+'\n'+output);
  assert(output.includes(fragment),label+'\n'+output);console.log(label+' passed');
}
try{
  const roots=[...new Set([...sourceFiles.map(name=>name.split('/')[0]),'public-selectors'])];
  json('project/.github/public-model-policy.json',{schema:'agent-frc/public-model-policy@1',project,publicRoots:roots,
    modelFiles:[...sourceFiles,'public-selectors/'+selector]});
  json('approved/.github/staged-model-policy.json',{schema:'agent-frc/staged-model-policy@1',project,
    mutableFieldPages:['field.html'],modelFiles:[...stageFiles,selector]});
  put('project/.github/staged-model-policy.json',read(path.join(folder,'approved/.github/staged-model-policy.json')));
  mkdirSync(path.join(folder,'runner/field'),{recursive:true});
  for(const name of [...sourceFiles,'public-selectors/'+selector])put('project/'+name,'original '+name);
  for(const root of ['runner/approved','runner/showcase']){
    for(const name of [...stageFiles,selector])put(root+'/'+name,'original '+name);
    put(root+'/field.html','original field');
  }
  git('init','-q');git('config','core.autocrlf','false');git('add','.');
  git('-c','user.name=Local Test','-c','user.email=local-test@example.invalid','commit','-qm','Synthetic baseline');
  const shell=read(workflow).toString().replaceAll('\r\n','\n').split('      - name: Check the source inventory and every final public byte\n')[1]
    .split('      - if:')[0].split('        run: |\n')[1].trimEnd().split('\n').map(l=>l.slice(10)).join('\n');
  const approvedFingerprint=run(process.execPath,[path.resolve(verifier,'scripts/local-showcase-release.mjs'),'digest','runner/approved']);
  assert.equal(approvedFingerprint.status,0,approvedFingerprint.stderr);
  put('gate.sh',shell.replace('9b6940ab02c2c7ab3189c842bf0c1461e5a1a049',git('rev-parse','HEAD'))
    .replace('e5e7c3bc2082e87a91e651ccc310cb850bab136e4ac193f6ecdc619fa46d64d8',approvedFingerprint.stdout.trim())+'\n');
  cpSync(path.join(verifier,'scripts'),path.join(folder,'verifier/scripts'),{recursive:true});
  check('Unchanged historical fixture',true);
  put('runner/showcase/field.html','new field');put('runner/field/field.html','new field');
  check('Independently generated field',true);
  for(const name of sourceFiles)put('project/'+name,read(path.join(sourceRoot,name)));
  check('Uncommitted CAD replacement',false,'differs from committed bytes',key,false);
  check('Unsigned source model change',false,'without matching approved issue');
  put(sourcePacket,read(sourcePath));check('Missing staged issue',false);
  promote();check('Ordinary signed source and renamed staged model',true);
  put('runner/showcase/'+selector,'unreviewed view');check('Uncovered staged selector',false,'Unreviewed changed');
  put('runner/showcase/'+selector,'original '+selector);
  put('runner/showcase/'+stageFiles[0],'changed after issue');check('Substituted staged artifact',false,'Changed signed public asset');
  promote();const damaged={...source,signature:Buffer.alloc(64).toString('base64')};json(sourcePacket,damaged);
  check('Broken source signature',false,'Invalid reviewer signature');
  promote();put('project/public-selectors/'+selector,'new selection');
  check('Uncovered source selector',false,'without matching approved issue');
  put('project/public-selectors/'+selector,'original public-selectors/'+selector);

  // Isolate same-issue enforcement using a separate, ephemeral trust root.
  const {publicKey,privateKey}=generateKeyPairSync('ed25519');
  const localPacket=body=>({body,signature:sign(null,Buffer.from(JSON.stringify(body)),privateKey).toString('base64')});
  json(sourcePacket,localPacket(source.body));
  json(stagePacket,localPacket({...staged.body,studySha256:'f'.repeat(64)}));
  check('Mismatched engineering issue with verified transport signatures',false,'different engineering issue',
    publicKey.export({format:'pem',type:'spki'}).toString());
}finally{
  assert.equal(path.dirname(path.resolve(folder)),path.resolve(tmpdir()));
  assert(path.basename(folder).startsWith('season-showcase-control-'));
  rmSync(folder,{recursive:true,force:true});
}
