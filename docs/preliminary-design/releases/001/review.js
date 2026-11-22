'use strict';
/* Agent FRC preliminary design review. Season-neutral: every season fact comes from scene.json.gz.
   Field fixtures are scene bodies flagged `fixture`; they draw and pick, but stay out of budgets and the inventory. */
const $=id=>document.getElementById(id);
const text=(tag,value)=>Object.assign(document.createElement(tag),{textContent:value});
const options=(sel,values,labels=values)=>sel.replaceChildren(...values.map((x,i)=>new Option(labels[i],x)));
const range=(r,n=2)=>r.map(v=>v.toFixed(n)).join('–');
const sum=(rows,key)=>rows.reduce((s,r)=>s.map((v,i)=>v+r[key][i]),[0,0]);
const flat=(m,p)=>[0,4,8].map(k=>m[k]*p[0]+m[k+1]*p[1]+m[k+2]*p[2]+m[k+3]);
const identity=[1,0,0,0,0,1,0,0,0,0,1,0];
let selected=null;
let data,entries,fixtureEntries,allEntries,custom,selNames=new Set(),picked=new Set(),marked=[],timer,cam,gl,program,position,color;
const rgb=s=>[1,3,5].map(i=>parseInt(s.slice(i,i+2),16)/255);
const current=()=>data.cases[$('motion').selectedIndex];
const duty=()=>data.power[$('duty').selectedIndex];
const last=c=>c.positions.length-1;
const key=()=> 'agent-frc/preliminary/groups/'+data.step;
function readGroups(){try{return JSON.parse(localStorage.getItem(key())||'{}')}catch{return {}}}
function writeGroups(){try{localStorage.setItem(key(),JSON.stringify(custom))}catch{}}
let isolated=null;
function showFixtures(){return $('cutaway').checked}
function displayedEntries(){return showFixtures()?allEntries:entries}
function poseAt(c,n,t){const s=c.series?.[c.rig?.[n]],f=c.frames?.[n];return s?.[t]||s?.[0]||f?.[t]||f?.[0]||identity}
function fit(az,el,list){
 const c=$('canvas'),w=c.clientWidth||1000,h=c.clientHeight||600,rail=$('labels').checked?labelRail(w):0;
 const ca=Math.cos(az),sa=Math.sin(az),ce=Math.cos(el),se=Math.sin(el);
 const u=[-sa,ca,0],v=[-se*ca,-se*sa,ce],bounds=[Infinity,-Infinity,Infinity,-Infinity],cs=current(),frame=+$('time').value;
 for(const [n,b] of list){if(cs.removed.includes(n))continue;const m=poseAt(cs,n,frame);
  for(const vertex of b.v){const p=flat(m,vertex),x=u.reduce((s,a,i)=>s+a*p[i],0),y=v.reduce((s,a,i)=>s+a*p[i],0);
   bounds[0]=Math.min(bounds[0],x);bounds[1]=Math.max(bounds[1],x);bounds[2]=Math.min(bounds[2],y);bounds[3]=Math.max(bounds[3],y)}}
 const midU=(bounds[0]+bounds[1])/2,midV=(bounds[2]+bounds[3])/2,depth=[ca*ce,sa*ce,se];
 const center=u.map((q,i)=>midU*q+midV*v[i]+(se*475)*depth[i]);
 const scale=.88*Math.min((w-rail-24)/Math.max(1,bounds[1]-bounds[0]),h/Math.max(1,bounds[3]-bounds[2]));
 cam={az,el,x:0,y:0,center,zoom:480*scale/Math.min(w,h)};draw()
}
function reset(){isolated=null;labelPage=0;fit(-.88,.43,entries)}
function interactionFit(){
 // Fit the robot together with every field fixture shown in this case.
 isolated=null;if(!fixtureEntries.length){reset();return}
 if(!showFixtures()){$('cutaway').checked=true}
 fit(-.95,.36,allEntries)
}
let sceneGPU,paintPending=false,locationMap={},lastProjection;
function initGL(){
 const c=$('canvas');gl=c.getContext('webgl',{antialias:true,alpha:false});
 if(!gl)throw Error('Enable WebGL to view the assembly.');
 const vertex='attribute vec3 point;attribute vec3 normal;uniform mat4 pose;uniform mat4 camera;uniform vec3 tint;varying vec3 shade;void main(){gl_Position=camera*pose*vec4(point,1.0);vec3 n=mat3(pose)*normal;float light=.83+.28*dot(n,vec3(.32,-.42,.84));shade=tint*light+vec3(.035);}';
 const fragment='precision mediump float;varying vec3 shade;void main(){gl_FragColor=vec4(shade,1.0);}';
 program=gl.createProgram();for(const [type,src] of [[gl.VERTEX_SHADER,vertex],[gl.FRAGMENT_SHADER,fragment]]){
  const shader=gl.createShader(type);gl.shaderSource(shader,src);gl.compileShader(shader);if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(shader));gl.attachShader(program,shader)}
 gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(program));gl.useProgram(program);
 for(const key of ['camera','pose','tint'])locationMap[key]=gl.getUniformLocation(program,key);
 position=gl.getAttribLocation(program,'point');color=gl.getAttribLocation(program,'normal');gl.enableVertexAttribArray(position);gl.enableVertexAttribArray(color);gl.enable(gl.DEPTH_TEST);
 function upload(values,mode){const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(values),gl.STATIC_DRAW);return {buffer,count:values.length/6,mode}}
 function triangles(s){const out=[];for(const f of s.f){const [a,b,c]=f.map(i=>s.v[i]);const u=b.map((x,i)=>x-a[i]),v=c.map((x,i)=>x-a[i]);const n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]],l=Math.hypot(...n)||1;for(const p of [a,b,c])out.push(...p,n[0]/l,n[1]/l,n[2]/l)}return upload(out,gl.TRIANGLES)}
 const mesh=new Map(allEntries.map(([n,b])=>[n,triangles(b)]));const lineData=[];const add=(a,b)=>lineData.push(...a,0,0,1,...b,0,0,1);
 const fl=data.floor||{min:[-3000,-3000],max:[3000,3000],z:0,step:250},z=fl.z||0,step=fl.step||250;
 for(let x=fl.min[0];x<=fl.max[0];x+=step)add([x,fl.min[1],z],[x,fl.max[1],z]);for(let y=fl.min[1];y<=fl.max[1];y+=step)add([fl.min[0],y,z],[fl.max[0],y,z]);
 const grid=upload(lineData,gl.LINES);lineData.length=0;(data.corners||[]).forEach((p,i,all)=>add(p,all[(i+1)%all.length]));
 const fixtures={};
 function unpack(str,Type){const raw=atob(str),b=new Uint8Array(raw.length);for(let i=0;i<raw.length;i++)b[i]=raw.charCodeAt(i);return new Type(b.buffer)}
 for(const [name,packed] of Object.entries(data.fixtureMeshes||{})){
   const v=unpack(packed.v,Float32Array),f=unpack(packed.f,Uint32Array),out=new Float32Array(f.length*6);
   for(let i=0;i<f.length;i+=3){const a=3*f[i],b=3*f[i+1],c=3*f[i+2];const x=v[b]-v[a],y=v[b+1]-v[a+1],zz=v[b+2]-v[a+2],u=v[c]-v[a],w=v[c+1]-v[a+1],h=v[c+2]-v[a+2];const nx=y*h-zz*w,ny=zz*u-x*h,nz=x*w-y*u,L=Math.hypot(nx,ny,nz)||1;
    for(let j=0;j<3;j++){const k=3*f[i+j],at=6*(i+j);out[at]=v[k];out[at+1]=v[k+1];out[at+2]=v[k+2];out[at+3]=nx/L;out[at+4]=ny/L;out[at+5]=nz/L}}
   fixtures[name]=upload(out,gl.TRIANGLES)
 }
 sceneGPU={fixtures,mesh,grid,aperture:upload(lineData,gl.LINES),ground:triangles({v:[[fl.min[0],fl.min[1],z-.1],[fl.max[0],fl.min[1],z-.1],[fl.max[0],fl.max[1],z-.1],[fl.min[0],fl.max[1],z-.1]],f:[[0,1,2],[0,2,3]]})};
}
function modelMatrix(m){return [m[0],m[4],m[8],0,m[1],m[5],m[9],0,m[2],m[6],m[10],0,m[3],m[7],m[11],1]}
function draw(){if(!cam||paintPending)return;paintPending=true;requestAnimationFrame(render)}
// Place part names in one margin. The two vertical rails form an ordered fan:
// both ends have the same Y order, then leaders run horizontally to material.
let labelPage=0, followLabel=null;
const calloutNodes=[];
function labelRail(width){return Math.min(212,Math.max(92,width*.235))}
function drawLeaders(labels,width,height,rail){
 const layer=$('names'),nav=$('labelPages'),all=$('labels').checked;
 if(!labels.length){layer.hidden=true;nav.hidden=true;return}
 layer.hidden=false;
 let svg=layer.firstElementChild;
 const ns='http://www.w3.org/2000/svg';
 function element(kind){return document.createElementNS(ns,kind)}
 if(!svg){svg=element('svg');svg.classList.add('callout-diagram');svg.setAttribute('aria-label','Component callouts');layer.append(svg)}
 svg.setAttribute('viewBox','0 0 '+width+' '+height);
 const rowHeight=24,capacity=Math.min(13,Math.max(1,Math.floor((height-36)/rowHeight))),pages=[];
 for(const point of labels){
  let page=pages.find(items=>items.length<capacity&&items.every(other=>Math.abs(other.y-point.y)>=7));
  if(!page){page=[];pages.push(page)}page.push(point);
 }
 if(followLabel){const i=pages.findIndex(page=>page.some(p=>p.name===followLabel));if(i>=0)labelPage=i;followLabel=null}
 labelPage=Math.min(labelPage,pages.length-1);
 const page=pages[labelPage].sort((a,b)=>a.y-b.y);
 nav.hidden=!all||pages.length<2;$('labelPageCount').textContent=(labelPage+1)+' / '+pages.length;
 $('labelPrev').disabled=labelPage===0;$('labelNext').disabled=labelPage===pages.length-1;
 // Clamp each label between the previous row and the room needed by later rows.
 let previous=-rowHeight;
 for(let i=0;i<page.length;i++){
  const p=page[i],row=Math.max(17,previous+rowHeight,Math.min(p.y,height-17-(page.length-i-1)*rowHeight));previous=row;
  let node=calloutNodes[i];
  if(!node){
   const g=element('g'),line=element('polyline'),dot=element('circle'),label=element('text'),title=element('title');
   dot.setAttribute('r','2.7');label.classList.add('tag');label.setAttribute('text-anchor','end');label.setAttribute('dominant-baseline','middle');
   g.append(line,dot,label,title);svg.append(g);node={g,line,dot,label,title};calloutNodes.push(node);
   label.addEventListener('click',()=>inspect(g.dataset.part));
  }
  node.g.style.display='';node.g.dataset.part=p.name;
  node.g.classList.toggle('chosen',p.name===selected||marked.includes(p.name));
  const start=rail-12,turn=rail+14;
  node.line.setAttribute('points',[[start,row],[turn,p.y],[p.x,p.y]].map(q=>q.join(',')).join(' '));
  node.dot.setAttribute('cx',p.x);node.dot.setAttribute('cy',p.y);
  node.label.setAttribute('x',start-5);node.label.setAttribute('y',row);
  node.label.textContent=p.name;node.title.textContent=p.name;
  node.label.removeAttribute('textLength');
  const max=rail-24;
  if(node.label.getComputedTextLength()>max){node.label.setAttribute('textLength',max);node.label.setAttribute('lengthAdjust','spacingAndGlyphs')}
  else node.label.removeAttribute('textLength');
 }
 for(const node of calloutNodes.slice(page.length))node.g.style.display='none';
}
function render(){
 paintPending=false;if(!sceneGPU)return;
 const cs=current(),t=+$('time').value,canvas=$('canvas'),width=canvas.clientWidth,height=canvas.clientHeight,dpr=Math.min(devicePixelRatio||1,2);
 const pw=Math.round(width*dpr),ph=Math.round(height*dpr);
 if(canvas.width!==pw||canvas.height!==ph){canvas.width=pw;canvas.height=ph;gl.viewport(0,0,pw,ph)}
 gl.clearColor(.058,.114,.207,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
 const rail=$('labels').checked?labelRail(width):0;
 const ca=Math.cos(cam.az),sa=Math.sin(cam.az),ce=Math.cos(cam.el),se=Math.sin(cam.el),sc=cam.zoom*Math.min(width-rail,height)/480;
 const u=[-sa,ca,0].map(v=>v*2*sc/width),v=[-se*ca,-se*sa,ce].map(v=>v*2*sc/height),z=[ce*ca,ce*sa,se].map(v=>-v/45000);
 const dot=(a,b)=>a.reduce((s,x,i)=>s+x*b[i],0);
 const off=[(2*cam.x+rail)/width-dot(u,cam.center),-2*cam.y/height-dot(v,cam.center),-dot(z,cam.center)];
 lastProjection=p=>[dot(u,p)+off[0],dot(v,p)+off[1],dot(z,p)+off[2]];
 gl.uniformMatrix4fv(locationMap.camera,false,[u[0],v[0],z[0],0,u[1],v[1],z[1],0,u[2],v[2],z[2],0,...off,1]);
 function paint(item,mat,col){gl.bindBuffer(gl.ARRAY_BUFFER,item.buffer);gl.vertexAttribPointer(position,3,gl.FLOAT,false,24,0);gl.vertexAttribPointer(color,3,gl.FLOAT,false,24,12);gl.uniformMatrix4fv(locationMap.pose,false,modelMatrix(mat));gl.uniform3fv(locationMap.tint,col);gl.drawArrays(item.mode,0,item.count)}
 const xy=cs.positions[t]||[0,0],field=[1,0,0,-xy[0],0,1,0,-xy[1],0,0,1,0];
 if($('floor').checked){if(se>0)paint(sceneGPU.ground,field,[.1,.17,.25]);paint(sceneGPU.grid,field,[.16,.25,.34])}
 if(!isolated&&showFixtures()){for(const [name,tint] of cs.fixtureMeshes||[])if(sceneGPU.fixtures[name])paint(sceneGPU.fixtures[name],field,tint);if(data.corners)paint(sceneGPU.aperture,field,[.36,.94,1])}
 const labels=[];for(const [name,b] of displayedEntries()){if(cs.removed.includes(name)||(isolated&&isolated!==name))continue;
  const m=poseAt(cs,name,t);
  let col=b.tint;if(marked.includes(name))col=[1,.34,.14];else if(!b.fixture&&!selNames.has(name))col=b.dim;if(name===selected)col=[1,.79,.27];
  paint(sceneGPU.mesh.get(name),m,col);
  if(rail&&(($('labels').checked&&!b.fixture)||marked.includes(name)||name===selected)){
   const point=lastProjection(flat(m,b.leaderAnchor)),x=(point[0]+1)*width/2,y=(1-point[1])*height/2;
   if(x>rail+17&&x<width-4&&y>4&&y<height-4)labels.push({name,x,y});
  }
 }
 drawLeaders(labels,width,height,rail);$('fraction').textContent=cs.time?cs.time[t].toFixed(2)+' s':Math.round(t/Math.max(1,last(cs))*100)+'%';$('liveMeasure').textContent=cs.measure?.[t]||'Parked assembly';
}
function candidatesForPick(){
 const cs=current(),t=+$('time').value;
 return displayedEntries().filter(([n])=>!cs.removed.includes(n)&&(!isolated||n===isolated)).map(([name,b])=>{
  const m=poseAt(cs,name,t);
  return {name,points:b.v.map(p=>lastProjection(flat(m,p))),faces:b.f}
 })
}
function modelEvidence(){
 const parts=entries.length,maxError=Math.max(...allEntries.map(([,b])=>b.error/Math.max(b.volume,1)));
 $('validation').textContent=data.validationText||(allEntries.filter(([,b])=>b.closed).length+'/'+allEntries.length+' closed meshes ('+parts+' robot, '+fixtureEntries.length+' field) · largest mesh-to-STEP volume difference '+(100*maxError).toPrecision(2)+'%. '+(parts*(parts-1)/2).toLocaleString()+' robot pairs; '+data.static.length+' parked positive-volume pairs, '+data.unresolved.length+' unresolved. Motion evidence appears under each case.')
}
function inspect(n){followLabel=n;selected=n;marked=[];const b=data.bodies[n],box=$('inspector');box.replaceChildren();box.append(text('span',b.fixture?'FIELD FIXTURE':'COMPONENT INSPECTOR'),text('h2',n),text('b',b.category+' / '+b.group),text('p',b.material),text('p',(b.volume/1000).toFixed(1)+' cm³ · '+(b.basis||'Placed planning envelope')));for(const r of data.details.filter(r=>r.members.length===1&&r.members[0]===n))box.append(text('p',range(r.kg,3)+' kg · '+r.name));for(const [label,key] of [['Purpose','purpose'],['Why it is included','rationale']])box.append(text('h3',label),text('p',b[key]||'Missing from this review'));const focus=text('button','Focus part'),restore=text('button','Show assembly');focus.onclick=()=>{const m=poseAt(current(),n,+$('time').value);cam.center=flat(m,b.anchor);const extent=Math.max(...[0,1,2].map(i=>Math.max(...b.v.map(p=>p[i]))-Math.min(...b.v.map(p=>p[i]))));cam.zoom=Math.min(6,300/Math.max(extent,1));cam.x=cam.y=0;isolated=n;draw()};restore.onclick=reset;if(data.support?.[n])box.append(text('p',data.support[n]));box.append(focus,restore);draw()}
function pick(e){const r=$('canvas').getBoundingClientRect(),x=2*(e.clientX-r.left)/r.width-1,y=1-2*(e.clientY-r.top)/r.height;let best=Infinity,hit=null;for(const obj of candidatesForPick())for(const [i,j,k] of obj.faces){const [a,b,c]=[obj.points[i],obj.points[j],obj.points[k]];const det=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1]);if(Math.abs(det)<1e-14)continue;const u=((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/det,v=((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/det,h=1-u-v;if(Math.min(u,v,h)<0)continue;const z=u*a[2]+v*b[2]+h*c[2];if(z<best){best=z;hit=obj.name}}if(hit)inspect(hit)}
function group(){
 const by=$('group').value,sub=$('subset'),opts=by==='Category'?[...new Set(entries.map(([,b])=>b.category))]:by==='Subsystem'?[...new Set(entries.map(([,b])=>b.group))]:Object.keys(custom);
 const old=sub.value;options(sub,opts);if(opts.includes(old))sub.value=old;sub.hidden=by==='Whole robot'||!opts.length;$('editor').hidden=by!=='Custom subsystem';
 if(by==='Custom subsystem')picked=new Set(custom[sub.value]||[]);
 select()
}
function select(){
 const by=$('group').value,val=$('subset').value;
 selNames=new Set(entries.filter(([n,b])=>(by==='Whole robot'||(by==='Category'?val===b.category:by==='Subsystem'?val===b.group:picked.has(n)))).map(([n])=>n));
 budget();inventory();draw()
}
function partition(lines,whole){
 const included=[],shared=[];
 for(const line of lines){const n=line.members.filter(v=>selNames.has(v)).length;if(whole||n&&n===line.members.length)included.push(line);else if(n)shared.push(line)}
 return {included,shared}
}
function budget(){
 resourcePanel();
 const whole=$('group').value==='Whole robot',e=duty(),m=partition(data.mass,whole),p=partition(e.lines,whole),detail=partition(data.details.filter(r=>r.members.length),false),amps=sum(p.included,'amps'),kg=sum(m.included,'kg'),volume=entries.filter(([n])=>selNames.has(n)).reduce((s,[,b])=>s+b.volume,0)/1e6;
 const values=[['Component envelopes',selNames.size+' selected · '+volume.toFixed(2)+' L'],['Inspection mass allocated',m.shared.length&&!m.included.length?'Shared estimate · see detail':range(kg,3)+' kg'+(m.shared.length?' + shared mass':'')],...(!whole&&detail.included.length?[['Identified component estimates',range(sum(detail.included,'kg'),3)+' kg · partial']]:[]),['Attributed battery current',range(amps,1)+' A'+(p.shared.length?' + shared load':'')],['Attributed pack sag',range(amps.map(a=>a*e.resistance),2)+' V'+(p.shared.length?' + shared load':'')],['Whole-robot loaded bus',range(e.loadedBusV,2)+' V · '+e.requiredMinV+' V required']];
 const div=$('summary');div.replaceChildren();for(const [k,v] of values){const row=text('p',k);row.append(text('b',v));div.append(row)}
 const lines=$('lines');lines.replaceChildren();for(const [title,arr,unit,field] of [['Included inspection',m.included,'kg','kg'],['Shared inspection · unapportioned',m.shared,'kg','kg'],['Component estimates · separate basis',detail.included,'kg','kg'],['Included current',p.included,'A','amps'],['Shared current · unapportioned',p.shared,'A','amps']]){
  if(!arr.length)continue;lines.append(text('strong',title));
  for(const v of arr)lines.append(text('p',(v.id||v.name)+' · '+range(v[field],3)+' '+unit))
 }
 lines.append(text('p','The whole-robot bus includes all loads. Ranges from independent extrema can be conservative. Running items are shown separately from inspection allocations.'));
}
function table(headers){const el=document.createElement('table'),head=el.createTHead().insertRow();headers.forEach(h=>head.append(text('th',h)));return [el,el.createTBody()]}
function inventory(){
 const edit=$('group').value==='Custom subsystem',[tab,body]=table([edit?'Use':'Category','Component / subsystem','Preliminary material','Volume']);
 for(const [n,b] of entries){if(!edit&&!selNames.has(n))continue;
  const r=body.insertRow();r.dataset.name=n;const first=r.insertCell();
  if(edit){const ck=document.createElement('input');ck.type='checkbox';ck.checked=picked.has(n);ck.setAttribute('aria-label','Include '+n);ck.onclick=ev=>{ev.stopPropagation();ck.checked?picked.add(n):picked.delete(n);selNames=new Set(picked);budget();draw()};first.append(ck)}
  else{const s=document.createElement('i');s.className='swatch';s.style.background=data.palette[b.category];first.append(s,b.category)}
  const cell=r.insertCell();cell.append(text('b',n),document.createElement('br'),b.group);r.insertCell().textContent=b.material;r.insertCell().textContent=(b.volume/1000).toFixed(1)+' cm³';r.tabIndex=0;r.onclick=()=>inspect(n);r.onkeydown=e=>{if(e.key==="Enter")inspect(n)}
 }
 $('inventory').replaceChildren(tab);$('inventoryScope').textContent=edit?'Check members, give the subsystem a name and save.':'Each row is one placed preliminary envelope. Field fixtures are drawn but not listed. Select a row to locate it.';
}
function evidence(){
 const parked=$('set').selectedIndex===1,cs=current(),rows=parked?data.static.map(x=>({pair:x.pair,status:'overlap',witness:{volumeMm3:x.volume}})):cs.results;
 const counts={};rows.forEach(r=>counts[r.status]=(counts[r.status]||0)+1);
 $('count').textContent=parked?'Installed assembly · '+data.narrow+' broad-phase candidates measured. '+rows.length+' positive-volume pairs.':cs.id+' · '+(Object.entries(counts).map(([k,v])=>v+' '+k).join(' / ')||'no recorded pairs')+(cs.gap==null?'':' · least recorded clearance '+cs.gap+' mm');
 const [tab,body]=table(['Pair','Result','Witness']);let shown=0;for(const f of rows){
  if(!parked&&$('filter').value==='adverse'&&!['fail','open'].includes(f.status))continue;shown++;
  const r=body.insertRow();r.dataset.finding='1';r.insertCell().textContent=f.pair.join(' / ')+(f.stage?' · '+f.stage:'');r.insertCell().textContent=f.status;const w=f.witness||{};r.insertCell().textContent=w.volumeMm3>0?w.volumeMm3.toFixed(2)+' mm³ overlap':Number.isFinite(w.gapMm)?w.gapMm.toFixed(2)+' mm':w.reason||(Array.isArray(w)?'Open interval '+w.map(v=>Math.round(v*100)+'%').join('–'):'Unresolved');
  r.onclick=()=>{stop();marked=f.pair;if(parked){$('time').value=0}else if(Number.isFinite(w.t))$('time').value=Math.round(w.t*last(cs));$('witness').textContent=f.pair.join(' / ')+(Number.isFinite(w.t)?' · recorded at '+(100*w.t).toFixed(2)+'% of the path · nearest displayed frame':' · parked or interval result');draw()}
 }
 if(!shown)body.insertRow().insertCell().textContent=parked?'No positive-volume pairs in the installed assembly.':'No failed or open pairs in this case. Choose “All recorded pairs” to list the passes.';
 $('findings').replaceChildren(tab)
}
function stop(){clearInterval(timer);timer=null;$('play').textContent='Play'}
async function init(){
 const response=await fetch('./scene.json.gz');if(!response.ok)throw Error('Review data unavailable');const bytes=await response.arrayBuffer();const packed=new Uint8Array(bytes);data=await (packed[0]===31&&packed[1]===139?new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))):new Response(bytes)).json();
 const query=new URLSearchParams(location.search);
 allEntries=Object.entries(data.bodies);entries=allEntries.filter(([,b])=>!b.fixture);fixtureEntries=allEntries.filter(([,b])=>b.fixture);custom=readGroups();
 for(const [n,b] of allEntries){b.tint=rgb(data.palette[b.category]||data.palette.reference||'#8A9199');b.dim=b.tint.map((x,i)=>.20*x+.80*[.64,.73,.83][i]);b.anchor=[0,1,2].map(i=>b.v.reduce((s,p)=>s+p[i],0)/b.v.length);let best=Infinity;for(const p of b.v){const d=p.reduce((sum,x,i)=>sum+(x-b.anchor[i])**2,0);if(d<best){best=d;b.leaderAnchor=p}}}
 options($('motion'),data.cases.map(c=>c.key),data.cases.map(c=>c.id));const deep=query.get('case')||data.defaultCase;const ix=data.cases.findIndex(c=>c.key===deep);if(ix>=0)$('motion').selectedIndex=ix;
 options($('duty'),data.power.map(e=>e.case));$('duty').selectedIndex=0;
 $('state').textContent=data.status;document.querySelector('.title p').textContent=data.season+'　/　Preliminary design release '+data.release;document.querySelector('h1').textContent=data.issue;document.title=data.season+' · '+data.issue+' · Preliminary design review';
 const metrics=[['Inspection estimate',range(data.inspection,3)+' kg'],['Running estimate',range(data.running,2)+' kg'],['Package envelope sum',(entries.reduce((s,[,b])=>s+b.volume,0)/1e6).toFixed(1)+' L'],['Movement cases',data.cases.length+' modeled']];
 for(const [label,value] of metrics){const box=document.createElement('div');box.append(text('span',label),text('b',value));$('metrics').append(box)}
 for(const role of new Set(allEntries.map(([,b])=>b.category))){const span=document.createElement('span'),i=document.createElement('i');i.className='swatch';i.style.background=data.palette[role];span.append(i,role);$('legend').append(span)}
 $('cutaway').disabled=!fixtureEntries.length;$('field').disabled=!fixtureEntries.length;
 const n=data.narrativeReview;if(n){$('narrative').replaceChildren(text('p',n.source.file+' · '+n.source.sha256.slice(0,12)),...n.objectives.map(row=>text('p',row.objective+' — '+row.disposition+'. '+row.basis)))}else $('narrative').replaceChildren(text('p','No strategic narrative review is bound to this release.'));
 $('notes').replaceChildren(...(data.notes||[]).map(v=>text('p',v)),text('p','Bound by SHA-256 to STEP '+data.step.slice(0,12)+' · motion '+data.motion.slice(0,12)+' · receipt '+data.receipt.slice(0,12)+' · package player '+data.view.slice(0,12)+'.'));initGL();group();reset();evidence();modelEvidence();
 $('duty').onchange=budget;$('group').onchange=group;$('subset').onchange=()=>{if($('group').value==='Custom subsystem')picked=new Set(custom[$('subset').value]||[]);select()};
 $('save').onclick=()=>{const name=$('subname').value.trim();if(!name||!picked.size){$('inventoryScope').textContent='Enter a subsystem name and select at least one component.';return}custom[name]=[...picked];writeGroups();group();$('subset').value=name;$('subset').onchange()};
 function activate(){
   stop();const c=current();$('time').max=last(c);$('time').value=0;marked=[];selected=null;
   const link=new URL(location.href);link.searchParams.set('case',c.key);history.replaceState({},'',link);if(parent!==window)parent.postMessage({type:'review-case',case:c.key},location.origin);
   const match=data.power.findIndex(e=>e.case===c.duty);if(match>=0){$('duty').selectedIndex=match;budget()}
   $('basis').textContent=c.basis;$('witness').textContent='';evidence();draw();
 }
 $('motion').onchange=activate;$('time').oninput=()=>{stop();draw()};
 $('play').onclick=()=>{if(timer)return stop();const c=current(),times=c.time||c.positions.map((_,i)=>i*.1);if(+$('time').value===times.length-1)$('time').value=0;const start=performance.now(),offset=times[+$('time').value],rate=+$('speed').value;$('play').textContent='Pause';timer=setInterval(()=>{const elapsed=offset+(performance.now()-start)*rate/1000;let t=+$('time').value;while(t<times.length-1&&times[t+1]<=elapsed)t++;$('time').value=t;draw();if(t===times.length-1)stop()},16)};
 $('speed').onchange=stop;$('cutaway').onchange=draw;activate();
 $('labelPrev').onclick=()=>{labelPage=Math.max(0,labelPage-1);draw()};$('labelNext').onclick=()=>{labelPage+=1;draw()};
 for(const id of ['labels','floor'])$(id).onchange=draw;
 $('expand').onclick=async()=>{if(document.fullscreenElement){await document.exitFullscreen()}else{await document.querySelector('.viewer').requestFullscreen()}};
 document.addEventListener('fullscreenchange',()=>{$('expand').textContent=document.fullscreenElement?'Restore':'Expand';draw()});
 $('set').onchange=$('filter').onchange=evidence;$('reset').onclick=reset;$('field').onclick=interactionFit;
 const c=$('canvas');let drag=null;c.oncontextmenu=e=>e.preventDefault();
 c.onpointerdown=e=>{c.setPointerCapture(e.pointerId);drag=[e.clientX,e.clientY,e.shiftKey||e.button===2||e.button===1,e.clientX,e.clientY];c.focus()};
 c.onpointermove=e=>{if(!drag)return;const dx=e.clientX-drag[0],dy=e.clientY-drag[1];if(drag[2]){cam.x+=dx;cam.y+=dy}else{cam.az-=dx*.009;cam.el+=dy*.009}drag[0]=e.clientX;drag[1]=e.clientY;draw()};
 c.onpointerup=e=>{if(drag&&!drag[2]&&Math.hypot(e.clientX-drag[3],e.clientY-drag[4])<5)pick(e);drag=null};c.onpointercancel=()=>drag=null;c.addEventListener('wheel',e=>{e.preventDefault();cam.zoom=Math.max(.04,Math.min(8,cam.zoom*Math.exp(-e.deltaY*.0015)));draw()},{passive:false});
 c.onkeydown=e=>{const v={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]}[e.key];if(e.key==='Home')reset();else if(v){if(e.shiftKey){cam.x+=20*v[0];cam.y+=20*v[1]}else{cam.az+=.15*v[0];cam.el-=.15*v[1]}}else if(e.key==='+'||e.key==='-'){cam.zoom=Math.max(.04,Math.min(8,cam.zoom*(e.key==='+'?1.2:1/1.2)))}else return;e.preventDefault();draw()};
 new ResizeObserver(draw).observe(c);
}
init().catch(e=>{$('state').textContent=e.message;console.error(e)});
