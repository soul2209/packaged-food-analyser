(function () {
  const list = document.getElementById('list');
  const filters = document.getElementById('filters');
  const gradeFilter = document.getElementById('grade-filter');
  const search = document.getElementById('search');
  const emptyBox = document.getElementById('history-empty');
  const bar = document.getElementById('compare-bar');
  const barText = document.getElementById('compare-text');
  const compareBtn = document.getElementById('compare-btn');
  const lede = document.getElementById('history-lede');
  const SOURCE = {image: 'Photo', text: 'Pasted text', barcode: 'Barcode'};

  let scans = [];
  let chosen = [];
  const activeGrades = new Set();

  function titleOf(id) {
    const found = scans.find(s => String(s.id) === String(id));
    return found ? found.title : 'Scan ' + id;
  }

  function updateBar() {
    bar.hidden = chosen.length === 0;
    compareBtn.disabled = chosen.length !== 2;
    if (chosen.length === 1) barText.innerHTML = 'Pick one more scan to compare with <strong>' + esc(titleOf(chosen[0])) + '</strong>.';
    if (chosen.length === 2) barText.innerHTML = '<strong>' + esc(titleOf(chosen[0])) + '</strong> against <strong>' + esc(titleOf(chosen[1])) + '</strong>';
    list.querySelectorAll('.pick').forEach(c => {
      c.checked = chosen.includes(c.value);
      c.disabled = !c.checked && chosen.length >= 2;
    });
    list.querySelectorAll('.scan').forEach(li => li.classList.toggle('picked', chosen.includes(li.dataset.id)));
  }

  function renderFilters() {
    const counts = {};
    scans.forEach(s => { counts[s.grade] = (counts[s.grade] || 0) + 1; });
    gradeFilter.innerHTML = ['A', 'B', 'C', 'D', 'E'].map(g =>
      '<button type="button" class="gf ' + gradeClass(g) + (activeGrades.has(g) ? ' on' : '') + '" data-g="' + g + '" aria-pressed="' + activeGrades.has(g) + '"' +
      (counts[g] ? '' : ' disabled') + '>' + g + '<small>' + (counts[g] || 0) + '</small></button>').join('');
    gradeFilter.querySelectorAll('.gf').forEach(b => b.addEventListener('click', () => {
      const g = b.dataset.g;
      if (activeGrades.has(g)) activeGrades.delete(g); else activeGrades.add(g);
      renderFilters();
      renderList();
    }));
  }

  function renderList() {
    const q = search.value.trim().toLowerCase();
    const shown = scans.filter(s =>
      (!activeGrades.size || activeGrades.has(s.grade)) && (!q || s.title.toLowerCase().includes(q)));
    if (!shown.length) {
      list.innerHTML = '<li class="muted">No scans match those filters.</li>';
      return;
    }
    list.innerHTML = shown.map(s =>
      '<li class="scan" data-id="' + s.id + '">' +
      '<label class="pick-box"><input type="checkbox" class="pick" value="' + s.id + '"><span class="sr">Select ' + esc(s.title) + ' to compare</span></label>' +
      '<a class="scan-grade ' + gradeClass(s.grade) + '" href="/report/' + s.id + '" aria-label="Grade ' + esc(s.grade) + '">' + esc(s.grade) + '</a>' +
      '<div class="scan-main"><a class="scan-title" href="/report/' + s.id + '">' + esc(s.title) + '</a>' +
      '<p class="small">' + esc(SOURCE[s.input_type] || s.input_type) + ', ' + esc(formatWhen(s.created_at)) + '</p></div>' +
      '<div class="scan-score"><b>' + Number(s.score) + '</b><div class="mini"><i class="' + gradeClass(s.grade) + '" style="width:' + Number(s.score) + '%"></i></div></div>' +
      '<button type="button" class="link-btn del" data-id="' + s.id + '">Delete</button></li>'
    ).join('');
    list.querySelectorAll('.pick').forEach(c => c.addEventListener('change', () => {
      if (c.checked) { if (chosen.length < 2) chosen.push(c.value); }
      else chosen = chosen.filter(id => id !== c.value);
      updateBar();
    }));
    list.querySelectorAll('.del').forEach(b => b.addEventListener('click', () => {
      if (!b.classList.contains('confirm')) {
        b.classList.add('confirm');
        b.textContent = 'Confirm delete';
        setTimeout(() => { b.classList.remove('confirm'); b.textContent = 'Delete'; }, 3000);
        return;
      }
      fetch('/api/scans/' + b.dataset.id, {method: 'DELETE'}).then(() => {
        chosen = chosen.filter(id => id !== b.dataset.id);
        load();
      });
    }));
    updateBar();
  }

  function load() {
    fetch('/api/scans').then(r => r.json()).then(items => {
      scans = items;
      const has = scans.length > 0;
      filters.hidden = !has;
      list.hidden = !has;
      emptyBox.hidden = has;
      lede.hidden = !has;
      if (has) { renderFilters(); renderList(); } else { bar.hidden = true; }
    }).catch(() => {
      list.innerHTML = '<li class="notice error">Could not load your history. Check that the server is running and reload.</li>';
    });
  }

  search.addEventListener('input', renderList);
  compareBtn.addEventListener('click', () => {
    if (chosen.length === 2) window.location = '/compare?a=' + chosen[0] + '&b=' + chosen[1];
  });
  load();
})();
