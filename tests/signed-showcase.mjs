// Exercise the actual pre-upload command using an unrelated synthetic issue.
// The test key exists only in this process and signs only the fixture below.
import assert from 'node:assert/strict';
import {createHash,generateKeyPairSync,sign} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {copyFileSync,mkdirSync,mkdtempSync,readFileSync,rmSync,writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const project=fileURLToPath(new URL('../',import.meta.url));
const verifier=path.resolve(process.argv[2]);
const bash=process.env.BASH_BINARY || (process.platform==='win32'?'C:/Program Files/Git/bin/bash.exe':'bash');
const folder=mkdtempSync(path.join(tmpdir(),'synthetic-model-packet-'));
const hash=text=>createHash('sha256').update(text).digest('hex');
const put=(name,bytes)=>{
  const dest=path.join(folder,name);
  mkdirSync(path.dirname(dest),{recursive:true});writeFileSync(dest,bytes);
};
const json=(name,value)=>put(name,JSON.stringify(value));
const read=name=>readFileSync(path.join(folder,name));
const {publicKey,privateKey}=generateKeyPairSync('ed25519');
const pem=publicKey.export({format:'pem',type:'spki'}).toString();
const git=(...args)=>{
  const r=spawnSync('git',args,{cwd:path.join(folder,'project'),encoding:'utf8'});
  if(r.status!==0)throw Error(r.stderr);
  return r.stdout.trim();
};
const source='project/.github/model-release/source.json';
const staged='project/.github/model-release/staged.json';
const signFiles=(root,files,meta={})=>{
  const body={schema:'agent-frc/signed-model-release@5',project:'synthetic-fit',scope:'Isolated synthetic transport test',
    configuration:'single coupon',solids:1,studySha256:hash('test study'),archiveSha256:hash('test archive'),
    stepSha256:hash('test export'),...meta,files:files.map(p=>({path:p,sha256:hash(read(root+'/'+p))}))};
  return {body,signature:sign(null,Buffer.from(JSON.stringify(body)),privateKey).toString('base64')};
};
try{
  json('project/.github/public-model-policy.json',{schema:'agent-frc/public-model-policy@1',project:'synthetic-fit',
    publicRoots:['model'],modelFiles:['model/preview.png','model/view.html']});
  json('approved/.github/staged-model-policy.json',{schema:'agent-frc/staged-model-policy@1',project:'synthetic-fit',
    mutableFieldPages:['field.html'],modelFiles:['preview.png','view.html']});
  put('project/model/preview.png','synthetic historical preview');put('project/model/view.html','synthetic historical view');
  for(const root of ['runner/approved','runner/showcase']){
    put(root+'/preview.png','synthetic historical preview');put(root+'/view.html','synthetic historical view');
    put(root+'/field.html','original field fixture');
  }
  git('init','-q');git('config','core.autocrlf','false');git('add','.');
  git('-c','user.name=Synthetic Test','-c','user.email=synthetic@example.invalid','commit','-qm','Synthetic baseline');
  const workflow=readFileSync(path.join(project,'.github/workflows/robot-showcase.yml'),'utf8').replaceAll('\r\n','\n');
  const block=workflow.split('      - name: Check the source inventory and every final public byte\n')[1]
    .split('      - if:')[0].split('        run: |\n')[1].trimEnd();
  const script=block.split('\n').map(l=>l.slice(10)).join('\n').replace('9b6940ab02c2c7ab3189c842bf0c1461e5a1a049',git('rev-parse','HEAD'));
  put('gate.sh',script+'\n');
  mkdirSync(path.join(folder,'verifier/scripts'),{recursive:true});
  copyFileSync(path.join(verifier,'scripts/public-model-release.mjs'),path.join(folder,'verifier/scripts/public-model-release.mjs'));
  function check(label,success,expected=''){
    const r=spawnSync(bash,['gate.sh'],{cwd:folder,encoding:'utf8',env:{...process.env,
      REVIEW_PUBLIC_KEY:pem,RUNNER_TEMP:'runner',FRC_VERIFIED_FIELD_ROOT:'runner/field'}});
    const output=r.stdout+r.stderr;
    assert.equal(r.status===0,success,label+'\n'+output);assert.ok(output.includes(expected),label+'\n'+output);
    console.log(label+' passed');
  }
  check('Historical unchanged',true);
  put('runner/showcase/field.html','regenerated field');put('runner/field/field.html','regenerated field');
  check('Independent field-only update',true);
  put('project/model/preview.png','synthetic revised preview');put('runner/showcase/preview.png','synthetic revised preview');
  check('Unsigned model change',false,'without matching approved issue');
  json(source,signFiles('project',['model/preview.png']));check('Missing staged packet',false);
  json(staged,signFiles('runner/showcase',['preview.png']));
  check('Signed same-issue source and staged promotion',true);
  put('runner/showcase/view.html','unreviewed selector');check('Uncovered staged selector',false,'Unreviewed changed');
  put('runner/showcase/view.html','synthetic historical view');
  put('runner/showcase/preview.png','substituted after issue');check('Substituted signed media',false,'Changed signed public asset');
  put('runner/showcase/preview.png','synthetic revised preview');
  json(staged,signFiles('runner/showcase',['preview.png'],{stepSha256:hash('another synthetic step')}));
  check('Different independently signed assembly',false,'different engineering issue');
  json(staged,signFiles('runner/showcase',['preview.png']));
  const bad=JSON.parse(read(source));bad.signature=Buffer.alloc(64).toString('base64');json(source,bad);
  check('Invalid source signature',false,'Invalid reviewer signature');
  json(source,signFiles('project',['model/preview.png']));
  put('project/model/view.html','unsigned revised source');check('Uncovered source selector',false,'without matching approved issue');
}finally{
  assert.equal(path.dirname(path.resolve(folder)),path.resolve(tmpdir()));
  assert.ok(path.basename(folder).startsWith('synthetic-model-packet-'));
  rmSync(folder,{recursive:true,force:true});
}
