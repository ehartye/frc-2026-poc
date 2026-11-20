const viewer=document.querySelector('#tower');
const play=document.querySelector('#play');
const time=document.querySelector('#time');
const status=document.querySelector('#status');
const actions=[...document.querySelectorAll('[data-t]')];
const duration=11;
function paint(t){
  time.value=t;
  const stage=t<1.25?'Hooks deploying':t<4.89775?'Carriage descending':t<9?'Both tires clear':t<10.99?'Holding with power off':'Assessed low-rung hang';
  const message=stage+' Â· '+Number(t).toFixed(2)+' s';
  if(viewer.paused)status.textContent=message;
  time.setAttribute('aria-valuetext',message);
}
function seek(t){viewer.play({repetitions:1});viewer.pause();viewer.currentTime=Math.min(t,viewer.duration);paint(t);play.textContent=t>=duration?'Replay climb':'Play climb';}
viewer.addEventListener('load',async()=>{
  viewer.animationName='Park, capture, lift and hold';
  await viewer.updateComplete;seek(0);
  for(const control of [play,time,...actions])control.disabled=false;
});
for(const button of actions)button.addEventListener('click',()=>seek(Number(button.dataset.t)));
time.addEventListener('input',()=>seek(Number(time.value)));
play.addEventListener('click',()=>{
  if(!viewer.paused){seek(viewer.currentTime);return;}
  if(viewer.currentTime>=duration-.01)viewer.currentTime=0;
  viewer.play({repetitions:1});play.textContent='Pause';status.textContent='Playing the climb.';
  function frame(){paint(viewer.currentTime);if(!viewer.paused)requestAnimationFrame(frame);}
  requestAnimationFrame(frame);
});
viewer.addEventListener('finished',()=>{
  // Seeking the last key can itself dispatch finished. Only update the controls here.
  paint(duration);
  play.textContent='Replay climb';
});
