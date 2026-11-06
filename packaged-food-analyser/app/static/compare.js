(function () {
  const params = new URLSearchParams(window.location.search);
  const pickers = document.getElementById('pickers');
  const pickA = document.getElementById('pick-a');
  const pickB = document.getElementById('pick-b');
  const go = document.getElementById('go');
  const target = document.getElementById('compare');
  const emptyBox = document.getElementById('compare-empty');
  const loadPair = document.getElementById('load-pair');
  let scans = [];

  function notice(message) {
    target.innerHTML = '<p class="notice error">' + esc(message) + '</p>';
  }

  function fillSelect(select, wanted, fallbackIndex) {
    select.innerHTML = scans.map(s =>
      '<option value="' + s.id + '">' + esc(s.title) + ' (' + Number(s.score) + ', grade ' + esc(s.grade) + ')</option>').join('');
    const hit = scans.find(s => String(s.id) === String(wanted));
    select.value = hit ? hit.id : (scans[fallbackIndex] || scans[0]).id;
  }

  function showPickers(a, b) {
    const ready = scans.length >= 2;
    pickers.hidden = !ready;
    emptyBox.hidden = ready || !!target.innerHTML.trim();
    if (ready) { fillSelect(pickA, a, 0); fillSelect(pickB, b, 1); }
  }

  function run(a, b) {
    if (String(a) === String(b)) { notice('Pick two different scans to compare.'); return Promise.resolve(); }
    target.innerHTML = '<div class="loading"><span class="spinner" aria-hidden="true"></span><p>Comparing.</p></div>';
    return Promise.all([a, b].map(id => fetch('/api/scans/' + encodeURIComponent(id)).then(r => r.ok ? r.json() : null)))
      .then(([first, second]) => {
        if (!first || !second) { notice('One of those scans could not be found. It may have been deleted from your history.'); return; }
        emptyBox.hidden = true;
        renderCompare(first, second, target);
        history.replaceState(null, '', '/compare?a=' + encodeURIComponent(a) + '&b=' + encodeURIComponent(b));
      })
      .catch(() => notice('Could not load the scans. Check that the server is running and try again.'));
  }

  function loadScans() {
    return fetch('/api/scans').then(r => r.json()).then(items => { scans = items; });
  }

  go.addEventListener('click', () => run(pickA.value, pickB.value));

  loadPair.addEventListener('click', () => {
    loadPair.disabled = true;
    const codes = ['2000000100708', '2000000100005'];
    Promise.all(codes.map(c => fetch('/api/analyze/barcode/' + c).then(r => r.ok ? r.json() : null)))
      .then(pair => {
        if (pair[0] && pair[1]) return pair;
        return fetch('/api/products').then(r => r.json()).then(items => {
          if (items.length < 2) throw new Error('not enough products');
          return Promise.all(items.slice(0, 2).map(p => fetch('/api/analyze/barcode/' + p.barcode).then(r => r.json())));
        });
      })
      .then(pair => loadScans().then(() => {
        showPickers(pair[0].scan_id, pair[1].scan_id);
        return run(pair[0].scan_id, pair[1].scan_id);
      }))
      .catch(() => { notice('Could not load a sample pair. Analyse two products first.'); })
      .finally(() => { loadPair.disabled = false; });
  });

  loadScans().then(() => {
    const a = params.get('a'), b = params.get('b');
    showPickers(a, b);
    if (a && b) run(a, b);
  }).catch(() => notice('Could not load your scans. Check that the server is running and reload.'));
})();
