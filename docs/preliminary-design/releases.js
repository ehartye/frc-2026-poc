(async () => {
  const select = document.querySelector('#release');
  const frame = document.querySelector('#viewer');
  const direct = document.querySelector('#direct');
  const error = document.querySelector('#error');
  function warn(message) { error.textContent = message; error.hidden = false; }
  try {
    const response = await fetch('./releases.json');
    if (!response.ok) throw new Error('The release index could not be loaded.');
    const {latest, releases} = await response.json();
    const catalog = new Map(releases.map(r => [r.id, r]));
    if (!catalog.has(latest)) throw new Error('The latest release is missing from the index.');
    for (const r of releases) select.add(new Option(r.id + ' · ' + r.title + (r.id === latest ? ' (latest)' : ''), r.id));
    function load() {
      error.hidden = true;
      const query = new URLSearchParams(location.search);
      const id = query.get('release') ?? latest;
      if (!catalog.has(id)) {
        select.selectedIndex = -1;
        frame.removeAttribute('src'); direct.hidden = true;
        warn('Unknown release “' + id + '”. Choose an available release above.');
        return;
      }
      select.value = id;
      const url = new URL('releases/' + encodeURIComponent(id) + '/', location.href);
      url.searchParams.set('case',query.get('case') || catalog.get(id).defaultCase);
      direct.href = url; direct.hidden = false; frame.src = url;
    }
    select.onchange = () => {
      const url = new URL(location.href);
      url.searchParams.set('release', select.value); url.searchParams.delete('case');
      history.pushState(null,'',url); load();
    };
    addEventListener('popstate',load);
    addEventListener('message', e => {
      if (e.source !== frame.contentWindow || e.origin !== location.origin || !e.data || e.data.type !== 'review-case') return;
      const url = new URL(location.href); url.searchParams.set('case', e.data.case);
      history.replaceState(null,'',url); direct.href = frame.contentWindow.location.href;
    });
    load();
  } catch(e) { warn(e.message); }
})();
