function esc(value) {
  return String(value).replace(/[&<>"']/g, c => (
    {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]
  ));
}

function gradeClass(grade) {
  return 'grade-' + String(grade).toLowerCase();
}

const NUTRIENT_LABELS = {
  sugars: 'Sugars',
  sodium: 'Sodium',
  sat_fat: 'Saturated fat',
  trans_fat: 'Trans fat',
  fibre: 'Dietary fibre'
};
const GOOD_NUTRIENTS = ['fibre'];
const REDUCED = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

function formatWhen(stamp) {
  if (!stamp) return '';
  const date = new Date(String(stamp).replace(' ', 'T') + 'Z');
  if (isNaN(date)) return String(stamp);
  return date.toLocaleString('en-IN', {day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit'});
}

function nutrientState(n) {
  const p = n.percent_of_daily;
  if (GOOD_NUTRIENTS.includes(n.nutrient)) {
    if (p >= 20) return {cls: 'ok', word: 'Good'};
    if (p >= 8) return {cls: 'warn', word: 'Some'};
    return {cls: 'bad', word: 'Low'};
  }
  if (p >= 40) return {cls: 'bad', word: 'High'};
  if (p >= 15) return {cls: 'warn', word: 'Moderate'};
  return {cls: 'ok', word: 'Low'};
}

function animateNumber(el, to, ms) {
  const from = parseInt(el.textContent, 10) || 0;
  if (REDUCED || from === to) { el.textContent = to; return; }
  const start = performance.now();
  const duration = ms || 800;
  function tick(now) {
    const t = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - t, 3);
    el.textContent = Math.round(from + (to - from) * eased);
    if (t < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

const GAUGE_LEN = Math.PI * 80;

function gaugeHTML(score, grade) {
  const n = Math.max(0, Math.min(100, Number(score)));
  return '<div class="gauge ' + gradeClass(grade) + '" data-score="' + n + '" role="img" aria-label="Score ' + n + ' out of 100, grade ' + esc(grade) + '">' +
    '<svg viewBox="0 0 200 118" aria-hidden="true">' +
    '<path class="track" d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke-width="16" stroke-linecap="round"/>' +
    '<path class="arc" d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke-width="16" stroke-linecap="round" stroke-dasharray="0 ' + GAUGE_LEN.toFixed(1) + '"/>' +
    '<text class="num" x="100" y="88" text-anchor="middle">0</text>' +
    '<text class="sub" x="100" y="108" text-anchor="middle">out of 100</text></svg></div>';
}

function setGauge(gauge, score, grade) {
  const n = Math.max(0, Math.min(100, Number(score)));
  gauge.dataset.score = n;
  gauge.className = 'gauge ' + gradeClass(grade);
  gauge.setAttribute('aria-label', 'Score ' + n + ' out of 100, grade ' + grade);
  gauge.querySelector('.arc').style.strokeDasharray = (n / 100 * GAUGE_LEN).toFixed(1) + ' ' + GAUGE_LEN.toFixed(1);
  animateNumber(gauge.querySelector('.num'), n);
}

function mountGauges(root) {
  root.querySelectorAll('.gauge').forEach(g => {
    requestAnimationFrame(() => requestAnimationFrame(() => {
      setGauge(g, g.dataset.score, g.className.replace('gauge grade-', '').toUpperCase());
    }));
  });
}

function mountBars(root) {
  root.querySelectorAll('[data-w]').forEach(el => {
    requestAnimationFrame(() => requestAnimationFrame(() => { el.style.width = el.dataset.w + '%'; }));
  });
}

function wireExplain(root) {
  root.querySelectorAll('.explain').forEach(group => {
    const box = group.querySelector('.note-box');
    group.addEventListener('click', event => {
      const target = event.target.closest('[data-note]');
      if (!target || !box) return;
      group.querySelectorAll('[data-note]').forEach(b => b.setAttribute('aria-pressed', b === target ? 'true' : 'false'));
      box.textContent = target.dataset.note;
      box.hidden = false;
    });
  });
}

function renderResult(r, el) {
  const product = r.product || {};
  const title = product.name || 'Label analysis';
  const subtitle = [product.brand, formatWhen(r.created_at)].filter(Boolean).join(', ');
  const flags = r.ingredient_flags || {};
  const flagged = {};
  [['sugar', 'sugar'], ['trans_fat_risk', 'fat'], ['palm_oil', 'fat']].forEach(pair => {
    (flags[pair[0]] || []).forEach(f => { flagged[f.ingredient] = {kind: pair[1], note: f.note}; });
  });

  let html = '<article class="report">';
  html += '<header class="report-head">' + gaugeHTML(r.score, r.grade) +
    '<div class="report-title"><h2>' + esc(title) + '</h2>' +
    (subtitle ? '<p class="muted">' + esc(subtitle) + '</p>' : '') +
    '<p class="summary"><span class="grade-chip ' + gradeClass(r.grade) + '">' + esc(r.grade) + '</span>' + esc(r.summary) + '</p>' +
    '<p class="small">Confidence in this reading: ' + esc(r.confidence) + (r.provisional ? ' (provisional score)' : '') + (r.category === 'beverage' ? ', scored as a drink' : '') + '</p></div></header>';

  if (r.notes && r.notes.length) {
    html += '<ul class="notice-list">' + r.notes.map(n => '<li>' + esc(n) + '</li>').join('') + '</ul>';
  }

  const per = r.basis_label || '100 g';
  const deductions = r.deductions || [];
  if (deductions.length) {
    const top = Math.max.apply(null, deductions.map(d => Math.abs(d.points)).concat([1]));
    html += '<section class="rsec"><h3>Where the points went</h3><ul class="ledger-list">' + deductions.map(d => {
      const gain = d.points > 0;
      const label = (gain ? '+' : '\u2212') + Math.abs(d.points);
      return '<li><span class="ld-name">' + esc(d.label) + '</span>' +
        '<span class="ld-bar"><i class="' + (gain ? 'gain' : (d.kind === 'cap' ? 'cap' : 'loss')) + '" data-w="' + Math.max(4, Math.abs(d.points) / top * 100) + '"></i></span>' +
        '<b class="pts ' + (gain ? 'gain' : 'loss') + '">' + label + '</b></li>';
    }).join('') + '</ul><p class="small">Started at 100. Each row is points lost or gained.</p></section>';
  }

  html += '<section class="rsec"><h3>Nutrition against WHO limits, per ' + esc(per) + '</h3>';
  if (r.nutrients && r.nutrients.length) {
    html += '<div class="bars">' + r.nutrients.map(n => {
      const s = nutrientState(n);
      const good = GOOD_NUTRIENTS.includes(n.nutrient);
      const effect = n.score_effect > 0 ? '+' + n.score_effect : (n.score_effect < 0 ? '−' + Math.abs(n.score_effect) : '0');
      return '<div class="bar-row"><div class="bar-label"><span class="bar-name">' + esc(NUTRIENT_LABELS[n.nutrient] || n.nutrient) +
        '<span class="state ' + s.cls + '">' + s.word + '</span></span>' +
        '<span class="bar-val">' + esc(n.value) + ' ' + esc(n.unit) + ', ' + n.percent_of_daily + '% of the daily ' + (good ? 'target' : 'limit') +
        '<b class="pts ' + (n.score_effect > 0 ? 'gain' : 'loss') + '">' + effect + ' points</b></span></div>' +
        '<div class="bar" role="img" aria-label="' + n.percent_of_daily + ' percent"><div class="fill ' + s.cls + '" data-w="' + Math.min(100, Math.max(2, n.percent_of_daily)) + '"></div></div></div>';
    }).join('') + '</div>';
  } else {
    html += '<p class="muted">No nutrition values were found. Add a photo of the nutrition table for a full score.</p>';
  }
  html += '</section>';

  const insights = (r.insights || []).filter(i => i.type !== 'nutrient');
  html += '<section class="rsec"><h3>What to know</h3>';
  if (insights.length) {
    html += '<ul class="insights">' + insights.map(i =>
      '<li class="level-' + esc(i.level) + '"><span class="pill">' + esc(i.type) + '</span><span>' + esc(i.text) + '</span></li>'
    ).join('') + '</ul>';
  } else {
    html += '<p class="muted">Nothing concerning was flagged.</p>';
  }
  html += '</section>';

  const additives = r.additives || [];
  if (additives.length) {
    html += '<section class="rsec explain"><h3>Additives found</h3><div class="chips">' + additives.map(a =>
      '<button type="button" class="chip risk-' + esc(a.risk) + '" aria-pressed="false" data-note="' + esc(a.name + ' (' + a.e_number + '), ' + a.category + '. ' + a.note) + '">' +
      esc(a.e_number) + ' ' + esc(a.name) + '<small>' + esc(a.risk) + '</small></button>'
    ).join('') + '</div><p class="note-box" hidden></p><p class="small">Tap an additive to read what it is.</p></section>';
  }

  const allergens = r.allergens || {contains: [], may_contain: []};
  html += '<section class="rsec"><h3>Allergens</h3>';
  if (allergens.contains.length || allergens.may_contain.length) {
    html += '<div class="chips">' +
      allergens.contains.map(a => '<span class="chip allergen">' + esc(a) + '</span>').join('') +
      allergens.may_contain.map(a => '<span class="chip trace">may contain ' + esc(a) + '</span>').join('') + '</div>';
  } else {
    html += '<p class="muted">None detected.</p>';
  }
  html += '</section>';

  if (r.ingredients && r.ingredients.length) {
    const hasFlags = r.ingredients.some(i => flagged[i]);
    html += '<section class="rsec explain"><h3>Ingredients, in label order</h3><p class="ingredients">' + r.ingredients.map(item => {
      const f = flagged[item];
      return f
        ? '<button type="button" class="ing-tok mark-' + f.kind + '" aria-pressed="false" data-note="' + esc(item + ': ' + f.note) + '">' + esc(item) + '</button>'
        : '<span class="ing-tok">' + esc(item) + '</span>';
    }).join(', ') + '.</p><p class="note-box" hidden></p>' +
      (hasFlags ? '<p class="small"><span class="key mark-sugar"></span>sugar <span class="key mark-fat"></span>palm oil or hydrogenated fat. Tap a marked ingredient to see why.</p>' : '') +
      '</section>';
  }

  if (r.scan_id) {
    html += '<p class="report-actions no-print"><a class="btn" href="/report/' + Number(r.scan_id) + '">Open printable report</a>' +
      '<a class="btn" href="/history">See history</a></p>';
  }
  html += '</article>';
  el.innerHTML = html;
  mountGauges(el);
  mountBars(el);
  wireExplain(el);
}

function productName(r) {
  const product = r.product || {};
  return product.name || (r.ingredients || []).slice(0, 3).join(', ') || 'Scan ' + r.scan_id;
}

function renderCompare(first, second, el) {
  function nutrient(r, key) {
    return (r.nutrients || []).find(n => n.nutrient === key);
  }
  function side(text, width, win) {
    return '<div class="vs-val' + (win ? ' win' : '') + '">' + esc(text) + (win ? '<span class="sr"> (better)</span>' : '') + '</div>' +
      '<div class="vs-bar' + (win ? ' win' : '') + '"><i data-w="' + width + '"></i></div>';
  }
  const rows = [];
  const better = (a, b, lowerIsBetter) => a === b ? [false, false] : (lowerIsBetter ? [a < b, b < a] : [a > b, b > a]);

  let w = better(first.score, second.score, false);
  rows.push({label: 'Score', a: side(first.score + ' (' + first.grade + ')', first.score, w[0]), b: side(second.score + ' (' + second.grade + ')', second.score, w[1])});

  Object.keys(NUTRIENT_LABELS).forEach(key => {
    const a = nutrient(first, key), b = nutrient(second, key);
    const lower = !GOOD_NUTRIENTS.includes(key);
    w = a && b ? better(a.value, b.value, lower) : [false, false];
    const fmt = n => n ? n.value + ' ' + n.unit : 'not on label';
    rows.push({
      label: NUTRIENT_LABELS[key],
      a: side(fmt(a), a ? Math.min(100, a.percent_of_daily) : 0, w[0]),
      b: side(fmt(b), b ? Math.min(100, b.percent_of_daily) : 0, w[1])
    });
  });

  const addA = (first.additives || []).length, addB = (second.additives || []).length;
  const top = Math.max(1, addA, addB);
  w = better(addA, addB, true);
  rows.push({label: 'Additives', a: side(addA, addA / top * 100, w[0]), b: side(addB, addB / top * 100, w[1])});

  const listA = (first.allergens.contains || []).join(', ') || 'none';
  const listB = (second.allergens.contains || []).join(', ') || 'none';
  rows.push({label: 'Allergens', a: '<div class="vs-val text">' + esc(listA) + '</div>', b: '<div class="vs-val text">' + esc(listB) + '</div>'});

  let banner;
  if (first.score === second.score) {
    banner = '<div class="winner tie"><strong>It is a tie.</strong><span>Both products score ' + Number(first.score) + '.</span></div>';
  } else {
    const win = first.score > second.score ? first : second;
    const lose = win === first ? second : first;
    banner = '<div class="winner"><span class="grade-chip big ' + gradeClass(win.grade) + '">' + esc(win.grade) + '</span>' +
      '<div><strong>Better choice: ' + esc(productName(win)) + '</strong>' +
      '<span>Scores ' + Number(win.score) + ' against ' + Number(lose.score) + ', ' + (win.score - lose.score) + ' points ahead.</span></div></div>';
  }

  function head(r) {
    return '<div class="vs-head">' + gaugeHTML(r.score, r.grade) +
      '<h3>' + esc(productName(r)) + '</h3>' +
      '<a class="small no-print" href="/report/' + Number(r.scan_id) + '">Open report</a></div>';
  }

  el.innerHTML = banner +
    '<div class="vs">' +
    '<div class="vs-heads">' + head(first) + '<div></div>' + head(second) + '</div>' +
    rows.map(r => '<div class="vs-row"><div class="vs-side left">' + r.a + '</div><div class="vs-label">' + esc(r.label) + '</div><div class="vs-side right">' + r.b + '</div></div>').join('') +
    '</div>' +
    '<p class="small">Bars show each value as a share of the WHO daily limit, or of the daily target for fibre. The better value in each row is marked in bold.</p>';
  mountGauges(el);
  mountBars(el);
}
