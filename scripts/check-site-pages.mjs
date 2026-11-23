// Open the built site's entry page and field lab in Chromium and fail on a broken link or an uncaught page error.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {get} from 'node:http';
import {mkdtemp, readFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {setTimeout as wait} from 'node:timers/promises';

const [site, chromium] = process.argv.slice(2);
if (!site || !chromium) throw Error('Usage: node scripts/check-site-pages.mjs SITE_URL CHROMIUM');
const profile = await mkdtemp(path.join(tmpdir(), 'site-pages-'));
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
    const home=new URL('?test='+width,site).href;
    await send('Page.navigate',{url:home});
    await until("location.href==="+JSON.stringify(home)+" && document.querySelector('figure img')?.complete && document.querySelector('figure img').naturalWidth>0");
    assert.match(await evaluate("document.querySelector('.status').textContent"),/^Preliminary design · .+ \d+\.\d+( · draft \d+)? · (in progress|effective)$/);
    assert.ok(await evaluate("document.documentElement.scrollWidth <= innerWidth + 1"),'The entry page scrolls sideways at '+width+'px');
    assert.equal(await evaluate("document.body.textContent.includes('{{')"),false,'An entry page field was left unfilled');
    console.log(width+'px: entry page shows the current preliminary design and its still');
  }
  // Every same-site link on the entry page has to resolve, so a withdrawn page cannot stay linked.
  const links=await evaluate("[...new Set([...document.querySelectorAll('a[href]')].map(a=>a.href.split('#')[0]).filter(h=>h.startsWith(location.origin)))]");
  assert.ok(links.length>=8,'Expected the entry page to link the review, the status page and the field pages');
  // Plain node:http, one connection per link: the runtime's fetch can abort the whole process on the test server's closed connections.
  const status=link=>new Promise((resolve,reject)=>get(link,{agent:false},response=>{response.resume();resolve(response.statusCode);}).on('error',reject));
  for(const link of links)assert.equal(await status(link),200,'Broken entry page link: '+link);
  console.log(links.length+' same-site entry page links resolve');
  for(const [page,ready] of [['preliminary-design/',"document.querySelector('#release')?.options.length>=1 && !!document.querySelector('iframe')?.src"],
      ['detailed-design/',"document.body.textContent.includes('withdrawn')"]]){
    const url=new URL(page,site).href;
    await send('Page.navigate',{url});
    await until("location.href==="+JSON.stringify(url)+" && "+ready);
    console.log(page+' loads');
  }
  const lab=new URL('field-lab.html#rehearsal',site).href;
  await send('Page.navigate',{url:lab});
  await until("document.querySelector('#replaySeriesSource')?.value==='student'");
  await evaluate("document.querySelector('#rehearsal').open=true");
  const state=()=>evaluate("document.querySelector('#replay-state-B2').textContent");
  const tick=()=>evaluate("document.querySelector('#replayStep').click()");
  const opening=[];
  for(let i=0;i<8;i++){await tick();opening.push(await state());}
  assert.ok(opening.some(s=>/[1-7] aboard/.test(s)));assert.match(opening.at(-1),/0 aboard/);
  await evaluate("document.querySelector('#replayFast').click();document.querySelector('#replayRun').click();document.querySelector('#replayRun').click()");
  await tick();assert.match(await state(),/0 aboard/);
  await tick();assert.match(await state(),/blue-depot\/3.*1 aboard/);
  await tick();assert.match(await state(),/blue-depot\/2.*3 aboard/);
  assert.equal(errors.length,0,errors[0]);
} finally {
  socket?.close();chrome.kill();await closed;
  await rm(profile,{recursive:true,force:true,maxRetries:5,retryDelay:250});
}
