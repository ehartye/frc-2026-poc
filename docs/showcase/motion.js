import {attachChapterControls} from './chapter-controls.js';
const robot = document.querySelector('#robot');
if(matchMedia('(max-width: 34rem)').matches) robot.cameraOrbit = '38deg 68deg 2.35m';
const clips = [...document.querySelectorAll('[data-clip]')];
const stow = document.querySelector('#stow');
const pause = document.querySelector('#pause');
const seek = document.querySelector('#seek');
const status = document.querySelector('#status');
let active = '';
let frame;

function showTime() {
  seek.value = robot.currentTime;
  if (!robot.paused) frame = requestAnimationFrame(showTime);
}
function press(selected) {
  for (const button of [stow, ...clips]) button.setAttribute('aria-pressed', String(button === selected));
}
function ready() {
  const missing = clips.some(button => !robot.availableAnimations.includes(button.dataset.clip));
  for (const button of clips) button.disabled = missing;
  if (missing) status.textContent = 'The motion tracks could not be read. The static orbit is linked below.';
  else if (!active) status.textContent = 'Stowed R2C · 117 Fusion solids. Choose a motion to begin.';
}
robot.addEventListener('load', ready);
robot.addEventListener('error', () => {status.textContent = 'The interactive model could not load. Open the static CAD orbit below.';});
for (const button of clips) button.addEventListener('click', async () => {
  cancelAnimationFrame(frame);
  active = button.dataset.clip;
  robot.animationCrossfadeDuration = 0;
  robot.animationName = active;
  const wide = button === clips[1];
  robot.cameraTarget = wide ? '1.0m 1.1m 0m' : '.10m .30m 0m';
  robot.cameraOrbit = wide ? '0deg 84deg 4.7m' : '20deg 74deg 1.9m';
  await robot.updateComplete;
  robot.currentTime = 0;
  robot.play({repetitions: 1});
  seek.max = robot.duration;
  seek.disabled = pause.disabled = false;
  pause.textContent = 'Pause';
  press(button);
  status.textContent = wide ? 'Clip 2 · From the guided handoff through the full opening and the active counter.' : 'Clip 1 · From the carpet to the guided scoring handoff.';
  showTime();
});
robot.addEventListener('finished', () => {seek.value = robot.duration; pause.textContent = 'Replay';});
pause.addEventListener('click', () => {
  if (!robot.paused) {robot.pause(); pause.textContent = 'Resume'; return;}
  if (robot.currentTime >= robot.duration - .02) robot.currentTime = 0;
  robot.play({repetitions: 1}); pause.textContent = 'Pause'; showTime();
});
seek.addEventListener('input', () => {robot.pause(); robot.currentTime = Number(seek.value); pause.textContent = 'Resume';});
stow.addEventListener('click', () => {
  if (!active) return;
  // Construct a fresh model instance so every articulated node returns to its native rest transform.
  location.reload();
});
if (robot.loaded) ready();
const marks = document.querySelector('#chapter-list');
try {
  const response = await fetch('chapters.json');
  if (!response.ok) throw Error('The event register could not load.');
  const register = await response.json();
  attachChapterControls(marks, register, robot);
  marks.addEventListener('click', event => {
    if (!event.target.closest('button')) return;
    requestAnimationFrame(() => {
      active = robot.animationName;
      const button = clips.find(el => el.dataset.clip === active);
      if (!button) return;
      press(button);
      const wide = button === clips[1];
      robot.cameraTarget = wide ? '1.0m 1.1m 0m' : '.10m .30m 0m';
      robot.cameraOrbit = wide ? '0deg 84deg 4.7m' : '20deg 74deg 1.9m';
      seek.max = robot.duration; seek.value = robot.currentTime;
      seek.disabled = pause.disabled = false; pause.textContent = 'Resume';
      status.textContent = marks.querySelector('[role=status]').textContent;
      document.querySelector('.stage').scrollIntoView({block:'start'});
    });
  });
} catch (error) {marks.textContent = error.message;}
