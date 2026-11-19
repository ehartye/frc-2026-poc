const get = id => document.getElementById(id);
const response = await fetch('batch-data.json');
if (!response.ok) throw Error('Could not load the service ledger');
const data = await response.json();
const ns = 'http://www.w3.org/2000/svg';
const plot = get('plot');
const number = n => n == null ? '—' : n.toFixed(3);
function draw(tag, attrs, text) {
  const el = document.createElementNS(ns, tag);
  for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, value);
  if (text) el.textContent = text;
  plot.append(el);
}
for (const row of data.trials[1].rows) get('piece').add(new Option(row.id, row.id));
const trial = () => data.trials[+get('trial').value];
const rows = () => trial().rows.filter(p => !get('piece').value || p.id === get('piece').value);
get('repeat').textContent = data.bothInside.length +
    ' named pieces counted before the cutoff in both trials. ' + data.bothComplete.length +
    ' had a complete passage in both when processing time was included.';
function table() {
  const body = get('rows');
  body.replaceChildren();
  for (const p of rows()) {
    const tr = body.insertRow();
    for (const text
             of [p.id, p.slot, number(p.releaseS), number(p.apertureS), number(p.sharedClearS),
                 p.countWithin        ? 'Active' :
                     p.processingOnly ? 'Processing' :
                                        'Unresolved'])
      tr.insertCell().textContent = text;
  }
}
const x = m => 36 + (m + 6) * 112;
const y = m => 246 - m * 98;
function frame() {
  const t = +get('time').value;
  const run = trial();
  const at = run.frames.findLast(f => f[0] <= t) || [0];
  const seen = rows();
  plot.replaceChildren();
  draw('line', {x1: 16, y1: y(0), x2: 624, y2: y(0), stroke: '#93aac1'});
  const hub = data.openingM;
  draw('line', {
    x1: x(hub[0] - .53),
    y1: y(hub[2]),
    x2: x(hub[0] + .53),
    y2: y(hub[2]),
    stroke: 'white',
    'stroke-width': 3
  });
  draw(
      'text',
      {x: x(hub[0]), y: y(hub[2]) - 9, fill: 'white', 'text-anchor': 'middle', 'font-size': 15},
      'HUB opening');
  for (const [id, px, , pz] of at.slice(1)) {
    if (get('piece').value && id !== get('piece').value) continue;
    draw(
        'circle',
        {cx: x(px), cy: y(pz), r: 7.35, fill: '#f9c863', stroke: '#102c50', 'stroke-width': 1});
  }
  get('clock').value = t.toFixed(2) + ' s';
  const count = key => seen.filter(r => r[key] != null && r[key] <= t).length;
  get('score').textContent = count('releaseS') + ' exited · ' + count('apertureS') +
      ' cleared the rim · ' + seen.filter(r => r.countWithin && r.sharedClearS <= t).length +
      ' in the active window · ' +
      seen.filter(r => r.processingOnly && r.sharedClearS <= t).length + ' during processing';
}
let start, initial, animation;
function stop() {
  cancelAnimationFrame(animation);
  animation = undefined;
  get('play').textContent = 'Play';
}
function advance(now) {
  const t = Math.min(17, initial + (now - start) / 1000);
  get('time').value = t;
  frame();
  if (t < 17)
    animation = requestAnimationFrame(advance);
  else
    stop();
}
get('play').onclick = () => {
  if (animation !== undefined) {
    stop();
    return;
  }
  initial = +get('time').value === 17 ? 0 : +get('time').value;
  start = performance.now();
  get('play').textContent = 'Pause';
  animation = requestAnimationFrame(advance);
};
get('time').oninput = () => {
  stop();
  frame();
};
for (const id of ['trial', 'piece'])
  get(id).onchange = () => {
    table();
    frame();
  };
get('time').disabled = false;
get('play').disabled = false;
table();
frame();
