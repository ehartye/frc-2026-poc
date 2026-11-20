// Exercise the real model-viewer at its terminal key and fail on uncaught page errors.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdtemp, readFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {setTimeout as wait} from 'node:timers/promises';

const [site, chromium] = process.argv.slice(2);
if (!site || !chromium) throw Error('Usage: node scripts/check-tower-playback.mjs SITE_URL CHROMIUM');
const profile = await mkdtemp(path.join(tmpdir(), 'tower-playback-'));
const chrome = spawn(chromium, ['--headless=new', '--remote-debugging-port=0', '--use-angle=swiftshader',
  '--enable-unsafe-swiftshader', '--no-first-run', '--no-default-browser-check', '--user-data-dir='+profile,
  'about:blank'], {windowsHide:true, stdio:'ignore'});
const closed = new Promise(resolve => chrome.once('close',resolve));
let socket;
try {
  let port;
  for (let i=0; i<100 && !port; i++) {
    try {port=(await readFile(path.join(profile,'DevToolsActivePort'),'utf8')).split(/\r?\n/)[0];}
    catch {await wait(100);}
  }
  assert.ok(port,'Chromium did not expose its debugging port');
  const targets = await (await fetch('http://127.0.0.1:'+port+'/json')).json();
  socket = new WebSocket(targets.find(t=>t.type==='page').webSocketDebuggerUrl);
  await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
  const errors=[],pending=new Map();
  let sequence=0;
  socket.onmessage=event=>{
    const message=JSON.parse(event.data);
    if(message.method==='Runtime.exceptionThrown'){
      const details=message.params.exceptionDetails;
      errors.push(details.exception?.description??details.text);
    }
    if(pending.has(message.id)){
      const {resolve,reject}=pending.get(message.id);
      pending.delete(message.id);
      if(message.error)reject(Error(message.error.message));else resolve(message.result);
    }
  };
  const send=(method,params={})=>new Promise((resolve,reject)=>{
    const id=++sequence;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));
  });
  const evaluate=async expression=>{
    const result=await send('Runtime.evaluate',{expression,returnByValue:true});
    if(result.exceptionDetails)throw Error(result.exceptionDetails.exception?.description??result.exceptionDetails.text);
    return result.result.value;
  };
  async function until(expression){
    for(let i=0;i<150;i++){
      assert.equal(errors.length,0,errors[0]);
      if(await evaluate(expression))return;
      await wait(100);
    }
    throw Error('Timed out waiting for '+expression);
  }
  await send('Runtime.enable');
  for(const width of [390,1280]){
    await send('Emulation.setDeviceMetricsOverride',{width,height:844,deviceScaleFactor:1,mobile:false});
    await send('Page.navigate',{url:new URL('robot/tower.html',site).href+'?test='+width+'-'+Date.now()});
    await until("document.querySelector('#play')?.disabled===false && document.querySelector('#tower')?.loaded");
    const stage="document.querySelector('#tower')", button="document.querySelector('#play')";
    const held="document.querySelector('[data-t=\"11\"]').click()";
    const checkHeld=async()=>{
      await until(stage+'.paused && '+stage+".currentTime>10.99 && "+button+".textContent==='Replay climb'");
      assert.match(await evaluate("document.querySelector('#status').textContent"),/11\.00 s/);
      await wait(75);
      assert.equal(errors.length,0,errors[0]);
    };
    await evaluate(held);await checkHeld();
    await evaluate("document.querySelector('[data-t=\"9\"]').click()");
    await until(stage+'.currentTime===9');
    await evaluate(held);await checkHeld();
    await evaluate(held);await checkHeld();
    await evaluate(stage+'.timeScale=4;'+button+'.click()');
    await until('!'+stage+'.paused && '+stage+'.currentTime>0 && '+stage+'.currentTime<10');
    await checkHeld();
    await evaluate(held);await checkHeld();
    await evaluate(button+'.click()');
    await until('!'+stage+'.paused && '+stage+'.currentTime>0 && '+stage+'.currentTime<10');
    await evaluate(button+'.click()');
    console.log(width+'px: direct and repeated held pose, power-off seek, timed finish and restart; zero uncaught page errors');
  }
} finally {
  socket?.close();chrome.kill();await closed;
  await rm(profile,{recursive:true,force:true,maxRetries:5,retryDelay:250});
}

