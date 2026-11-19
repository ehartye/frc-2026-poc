const section = document.querySelector('#loading');
const result = await fetch('loading-data.json');
if (!result.ok) throw Error('Could not load the DEPOT evidence');
const data = await result.json();
const clock = section.querySelector('input');
const plot = section.querySelector('svg');
function mark(tag, properties, label) {
  const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, v] of Object.entries(properties)) node.setAttribute(k, v);
  if (label) node.textContent = label;
  plot.append(node);
}
function render() {
  const time = +clock.value;
  const frame = data.pairedFrames.findLast(r => r[0] <= time) || data.pairedFrames[0];
  const x = p => 180 + p * 540, y = p => 92 - p * 300;
  plot.replaceChildren();
  mark('rect', {x: x(.345), y: 12, width: .0762 * 540, height: 152, fill: '#748da4'});
  mark(
      'text', {x: x(.345) + 20, y: 182, fill: 'white', 'text-anchor': 'middle', 'font-size': 13},
      'DEPOT steel');
  for (const lane of [-.079, .079])
    mark('rect', {
      x: x(-.33),
      y: y(lane + .078),
      width: .478 * 540,
      height: .156 * 300,
      fill: '#234e77',
      stroke: '#92adbf'
    });
  mark(
      'text', {x: x(-.085), y: 182, fill: 'white', 'text-anchor': 'middle', 'font-size': 13},
      'Two storage lanes');
  for (const [id, px, py] of frame.slice(1))
    mark('circle', {
      cx: x(px),
      cy: y(py),
      r: 15,
      fill: id.endsWith('03') ? '#f7c966' : '#d3e9fa',
      stroke: '#142d4d',
      'stroke-width': 2
    });
  section.querySelector('output').value = time.toFixed(2) + ' s';
  const admitted = data.trials['pair-fine'].laneEvents.filter(
      e => e.event === 'trailing surface inside lane' && e.state.timeS <= time);
  section.querySelector('[role=status]').textContent = admitted.length +
      ' registered DEPOT pieces fully inside the lanes. Eight preloads started aboard.';
}
clock.oninput = render;
clock.disabled = false;
render();
