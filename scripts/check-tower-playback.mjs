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
const chrome = spawn(chromium, ['--headless=new', '--disable-dev-shm-usage', '--remote-debugging-port=0', '--use-angle=swiftshader',
  '--enable-unsafe-swiftshader', '--no-first-run', '--no-default-browser-check', '--user-data-dir='+profile,
  'about:blank'], {windowsHide:true, stdio:['ignore','ignore','pipe']});
let diagnostics='';
chrome.stderr.on('data',chunk=>{diagnostics=(diagnostics+chunk.toString()).slice(-1500);});
const closed = new Promise(resolve => chrome.once('close',resolve));
let socket;
try {
  let port;
  for (let i=0; i<450 && !port && chrome.exitCode===null; i++) {
    try {port=(await readFile(path.join(profile,'DevToolsActivePort'),'utf8')).split(/\r?\n/)[0];}
    catch {await wait(100);}
  }
  assert.ok(port,'Chromium did not expose its debugging port: '+diagnostics);
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
    for(let i=0;i<450;i++){
      assert.equal(errors.length,0,errors[0]);
      if(await evaluate(expression))return;
      await wait(100);
    }
    const snapshot=await evaluate("({url:location.href, title:document.title, modelLoaded:document.querySelector('model-viewer')?.loaded})");
    throw Error('Timed out waiting for '+expression+' '+JSON.stringify(snapshot));
  }
  await send('Runtime.enable');
  for(const width of [390,1280]){
    await send('Emulation.setDeviceMetricsOverride',{width,height:844,deviceScaleFactor:1,mobile:false});
    const home = new URL('#model', site).href;
    await send('Page.navigate', {url: home});
    await until("location.href===" + JSON.stringify(home) + " && document.querySelector('#featured-robot')?.loaded && !document.querySelector('.assembly-stage .controls').hidden");
    const model = "document.querySelector('#featured-robot')";
    const initial = await evaluate(model + ".getCameraOrbit().theta");
    await evaluate("document.querySelector('#inspect-intake').click()");
    await until("Math.abs(" + model + ".getCameraTarget().x - 0.27) < 0.004");
    assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth'), true);
    await evaluate("document.querySelector('#reset-camera').click()");
    await until("Math.abs(" + model + ".getCameraTarget().x) < 0.15");
    await evaluate("document.querySelector('[data-turn=\"45\"]').click()");
    await until("Math.abs(" + model + ".getCameraOrbit().theta - " + initial + ") > 0.5");
    await evaluate("document.querySelector('#reset-camera').click()");
    await until("Math.abs(" + model + ".getCameraOrbit().theta - " + initial + ") < 0.01");
    await evaluate("document.querySelector('#toggle-still').click()");
    await until("!document.querySelector('#fusion-still').hidden && document.querySelector('#fusion-still').naturalWidth > 0 && document.querySelector('#featured-robot').hidden");
    await evaluate("document.querySelector('#toggle-still').click()");
    await until("document.querySelector('#fusion-still').hidden && !document.querySelector('#featured-robot').hidden");
    assert.ok(await evaluate("document.querySelector('#model a[download]').href.endsWith('/assembly/display.f3d')"));
    assert.ok(await evaluate("document.documentElement.scrollWidth <= innerWidth + 1"));
    console.log(width + 'px: featured Fusion model loaded, rotated and reset');
    const url=new URL('robot/tower.html',site).href+'?test='+width+'-'+Date.now();
    await send('Page.navigate',{url});
    await until('location.href==='+JSON.stringify(url)+" && document.querySelector('#play')?.disabled===false && document.querySelector('#tower')?.loaded");
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
    await evaluate(button+'.click()');
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
