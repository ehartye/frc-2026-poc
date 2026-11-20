const viewer = document.querySelector('#featured-robot');
const stage = viewer.closest('.stage');
const controls = stage.querySelector('.controls');
const expand = controls.querySelector('#expand-model');
const initialOrbit = viewer.getAttribute('camera-orbit');

function enableCamera() {
  controls.hidden = false;
  expand.hidden = !document.fullscreenEnabled;
}

viewer.addEventListener('load', enableCamera);
if (viewer.loaded) enableCamera();

for (const button of controls.querySelectorAll('[data-turn]')) {
  button.addEventListener('click', () => {
    const orbit = viewer.getCameraOrbit();
    const theta = orbit.theta * 180 / Math.PI + Number(button.dataset.turn);
    viewer.cameraOrbit = theta + 'deg ' + orbit.phi + 'rad ' + orbit.radius + 'm';
  });
}
controls.querySelector('#inspect-intake').addEventListener('click', () => {
  viewer.cameraTarget = '0.27m 0.065m 0m';
  viewer.cameraOrbit = '100deg 72deg 0.78m';
  viewer.fieldOfView = '30deg';
});
controls.querySelector('#reset-camera').addEventListener('click', () => {
  viewer.cameraTarget = 'auto auto auto';
  viewer.fieldOfView = 'auto';
  viewer.cameraOrbit = initialOrbit;
});
const toggle = controls.querySelector('#toggle-still');
const still = stage.querySelector('#fusion-still');
toggle.addEventListener('click', () => {
  const showStill = still.hidden;
  still.hidden = !showStill;
  viewer.hidden = showStill;
  toggle.setAttribute('aria-pressed', String(showStill));
  for (const button of controls.querySelectorAll('[data-turn], #reset-camera, #inspect-intake')) {
    button.disabled = showStill;
  }
});
expand.addEventListener('click', async () => {
  if (document.fullscreenElement === stage) await document.exitFullscreen();
  else await stage.requestFullscreen();
});
document.addEventListener('fullscreenchange', () => {
  expand.textContent = document.fullscreenElement === stage ? 'Exit full screen' : 'Full screen';
});
