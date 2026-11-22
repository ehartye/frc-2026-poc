/* Weight ledger, selected-duty battery-side load ledger and role-based commissioning checks.
   Season-neutral: limits, running additions and required roles all come from the scene. */
function signed(v,unit,digits){return (v>=0?'+':'−')+Math.abs(v).toFixed(digits)+' '+unit}
function inspectionLimit(){return data.limits?.inspectionKg}
function runningItems(){return data.details.filter(r=>r.running)}
function weightLedger(){
 const root=$('weightBody');root.replaceChildren();
 const limit=inspectionLimit(),low=data.inspection[0],high=data.inspection[1];
 root.append(text('p','Inspection allowance '+limit.toFixed(2)+' kg. Upper estimate '+high.toFixed(2)+' kg, with '+signed(limit-high,'kg',2)+' headroom.'));
 const ruler=document.createElement('div');ruler.className='weight-ruler';
 const width=Math.max(1,Math.abs(low-limit),Math.abs(high-limit))*1.08,start=limit-width,end=limit+width;const band=document.createElement('i');band.style.left=((low-start)/(end-start)*100)+'%';band.style.width=((high-low)/(end-start)*100)+'%';ruler.append(band,text('b','Limit '+limit.toFixed(3)+' kg'));root.append(ruler);
 const [tab,body]=table(['Inspection allocation','Low, kg','High, kg']);for(const row of data.mass.filter(r=>r.kg[1]>0)){
 const tr=body.insertRow();tr.insertCell().textContent=row.id;for(const v of row.kg)tr.insertCell().textContent=v.toFixed(3)}
 const total=body.insertRow();total.className='grand-total';total.insertCell().textContent='Inspection total';for(const v of data.inspection)total.insertCell().textContent=v.toFixed(3);root.append(tab);
 const details=document.createElement('details');details.append(text('summary','Running configuration · '+range(data.running,2)+' kg'));details.append(text('p',data.runningBasis||'Articles carried in the match but outside the inspection weighing.'));
 const [ta,bd]=table(['Additional article','Low, kg','High, kg']);for(const r of runningItems()){const tr=bd.insertRow();tr.insertCell().textContent=r.name;for(const v of r.kg)tr.insertCell().textContent=v.toFixed(3)}details.append(ta);root.append(details)
}
function drawPowerBars(){
 const e=duty(),holder=$('powerBars');holder.replaceChildren();const max=e.batterySideA[1];
 for(const [i,line] of e.lines.entries()){
 const b=document.createElement('button');b.className='load-bar';b.setAttribute('aria-label','Inspect '+line.name);
 const caption=text('span',line.name),val=text('strong',line.amps[1].toFixed(1)+' A'),track=document.createElement('i'),fill=document.createElement('i');fill.style.width=Math.max(.5,100*line.amps[1]/Math.max(1,max))+'%';fill.style.background=['#2f66b0','#328a8a','#dfac29'][i%3];track.append(fill);b.append(caption,val,track);
 b.onclick=()=>{const target=$('loads').children[i+1];target.open=true;target.scrollIntoView({block:'nearest'});isolated=null;marked=line.members.slice();selected=null;draw()};holder.append(b)
 }
}
function resourcePanel(){
 const e=duty(),limit=inspectionLimit(),worst=data.inspection[1],voc=e.openCircuitV??(e.loadedBusV[0]+e.resistance*e.batterySideA[1]),r=e.resistance,minimum=e.requiredMinV,available=(voc-minimum)/r,imax=e.batterySideA[1];
 const pAt=i=>i*(voc-r*i),peak=Math.max(pAt(e.batterySideA[0]),pAt(imax),e.batterySideA[0]<=voc/(2*r)&&imax>=voc/(2*r)?pAt(voc/(2*r)):0);
 weightLedger();drawPowerBars();const total=$('resources');total.replaceChildren();
 function meter(label,value,message,used,capacity,negative){const block=document.createElement('section');block.className='budget-meter';block.append(text('span',label),text('b',value));const bar=document.createElement('progress');bar.max=Math.max(used,capacity)*1.04;bar.value=used;bar.setAttribute('aria-label',label);block.classList.toggle('over',negative);block.append(bar,text('small',message));const link=text('a',label==='Inspection weight'?'Weight ledger ↓':'Power ledger ↓');link.href=label==='Inspection weight'?'#weightCard':'#powerCard';block.append(link);total.append(block)}
 meter('Inspection weight',data.inspection[0].toFixed(3)+'–'+worst.toFixed(3)+' kg','Limit '+limit.toFixed(3)+' kg · headroom '+signed(limit-worst,'kg',3)+' high / '+signed(limit-data.inspection[0],'kg',3)+' low',worst,limit,worst>limit);
 meter('Battery voltage under load',e.loadedBusV[0].toFixed(3)+' V minimum','Requirement '+minimum.toFixed(2)+' V · headroom '+signed(e.loadedBusV[0]-minimum,'V',3),voc-e.loadedBusV[0],voc-minimum,e.loadedBusV[0]<minimum);
 meter('Battery-side demand',imax.toFixed(1)+' A · '+(peak/1000).toFixed(2)+' kW','Pack budget at '+minimum.toFixed(1)+' V: '+available.toFixed(1)+' A / '+(minimum*available/1000).toFixed(2)+' kW',imax,available,imax>available);
 const mount=$('loads');mount.replaceChildren(text('p',e.case+' · '+voc.toFixed(1)+' V open circuit · '+(1000*r).toFixed(1)+' mΩ battery model. Select a load to highlight its components.'));
 for(const line of e.lines){
  const d=document.createElement('details');const s=document.createElement('summary');s.textContent=line.name+'　 '+range(line.amps,1)+' A';d.append(s);
  const minW=line.amps[0]*e.loadedBusV[0],maxW=line.amps[1]*e.loadedBusV[1];d.append(text('p','Battery input envelope '+Math.floor(minW)+'–'+Math.ceil(maxW)+' W · pack sag contribution '+range(line.amps.map(i=>r*i),3)+' V. Power bounds combine voltage and current extrema.'));
  const group=text('button','Locate this load');group.onclick=()=>{isolated=null;selected=null;marked=line.members.slice();draw();$('stage').scrollIntoView({block:'nearest'});};d.append(group);
  const members=document.createElement('div');members.className='member-buttons';line.members.forEach(n=>{if(data.bodies[n]){const b=text('button',n);b.onclick=()=>{isolated=null;inspect(n);$('stage').scrollIntoView({block:'nearest'})};members.append(b)}});d.append(members);d.append(text('p',!line.members.length?'No placed component is assigned to this load.':line.members.length>1?'Budgeted as a shared load. Individual current split is unavailable.':'Assigned to this component in the duty model.'));mount.append(d)
 }
 // Required roles are commissioned by the package (presentation.required); compare them with the unfiltered placed roster.
 const v=$('required');v.replaceChildren();const names=new Set(entries.map(([n])=>n));
 let missing=0;for(const [role,list] of data.required||[]){const absent=list.filter(n=>!names.has(n));missing+=absent.length;const row=document.createElement('div');row.className='role-row '+(absent.length?'warn':'');row.append(text('strong',absent.length?'Missing':'Present'),text('span',role+'　 '+(list.length-absent.length)+'/'+list.length));if(absent.length)row.append(text('small',absent.join(', ')));v.append(row)}
 if(!(data.required||[]).length)v.append(text('p','The package commissions no required roles.'));
 const warns=$('warningText');warns.textContent=(missing?missing+' missing required representations. ':'Required component counts present. ')+(worst>limit?'High estimate exceeds inspection weight. ':'')+(e.loadedBusV[0]<minimum?'Selected duty falls below voltage requirement. ':'')+(data.focus||'');
}
