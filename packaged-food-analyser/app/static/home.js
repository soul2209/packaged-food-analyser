(function () {
  const demo = document.getElementById('demo');
  if (!demo) return;

  const toks = Array.from(demo.querySelectorAll('.tok'));
  const flagToks = toks.filter(t => t.classList.contains('flag'));
  const gaugeWrap = document.getElementById('demo-gauge');
  const barsEl = document.getElementById('demo-bars');
  const say = document.getElementById('demo-say');
  const reset = document.getElementById('demo-reset');

  const TAIL = '.\nContains: Wheat, Milk, Soy.\nMay contain: Peanuts, Tree nuts.\n' +
    'Nutrition Information (per 100 g)\nEnergy 495 kcal\nProtein 6.1 g\nCarbohydrate 68 g\nTotal Sugars 31 g\n' +
    'Added Sugars 29 g\nTotal Fat 22 g\nSaturated Fat 11.5 g\nTrans Fat 0.2 g\nDietary Fibre 2.1 g\nSodium 410 mg';
  const DEFAULT_SAY = 'Tap an underlined ingredient to leave it out of the recipe and see what it cost.';

  let base = null;
  let current = null;
  let sequence = 0;

  function buildText() {
    const active = toks.filter(t => !t.classList.contains('out')).map(t => t.dataset.text);
    return 'Ingredients: ' + active.join(', ') + TAIL;
  }

  function preview() {
    return fetch('/api/analyze/preview', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text: buildText()})
    }).then(r => {
      if (!r.ok) throw new Error('bad response');
      return r.json();
    });
  }

  function renderBars(nutrients) {
    barsEl.innerHTML = (nutrients || []).map(n => {
      const s = nutrientState(n);
      return '<div class="mini-row"><span class="mini-name">' + esc(NUTRIENT_LABELS[n.nutrient] || n.nutrient) + '</span>' +
        '<span class="mini-val">' + esc(n.value) + ' ' + esc(n.unit) + '</span>' +
        '<div class="bar"><div class="fill ' + s.cls + '" data-w="' + Math.min(100, Math.max(2, n.percent_of_daily)) + '"></div></div>' +
        '<span class="mini-pct">' + n.percent_of_daily + '%</span></div>';
    }).join('');
    mountBars(barsEl);
  }

  function noteFor(text) {
    const parts = [];
    const flags = (base && base.ingredient_flags) || {};
    ['sugar', 'trans_fat_risk', 'palm_oil'].forEach(key => {
      (flags[key] || []).forEach(f => {
        if (f.ingredient.toLowerCase() === text.toLowerCase()) parts.push(f.note);
      });
    });
    ((base && base.additives) || []).forEach(a => {
      if (new RegExp('\\b' + a.e_number + '\\b', 'i').test(text)) parts.push(a.name + ' (' + a.e_number + '): ' + a.note);
    });
    return parts.join(' ');
  }

  function setSay(html) {
    say.innerHTML = '<p>' + html + '</p>';
  }

  function anyOut() {
    return flagToks.some(t => t.classList.contains('out'));
  }

  function toggle(tok) {
    const was = current ? current.score : null;
    const goingOut = !tok.classList.contains('out');
    tok.classList.toggle('out', goingOut);
    tok.setAttribute('aria-pressed', goingOut ? 'true' : 'false');
    reset.hidden = !anyOut();
    const mine = ++sequence;

    preview().then(result => {
      if (mine !== sequence) return;
      current = result;
      setGauge(gaugeWrap.querySelector('.gauge'), result.score, result.grade);
      const name = '<strong>' + esc(tok.dataset.text) + '</strong>';
      const note = noteFor(tok.dataset.text);
      const delta = was === null ? 0 : result.score - was;
      let lead;
      if (goingOut) {
        lead = delta > 0
          ? 'Left out ' + name + ': the score goes from ' + was + ' to ' + result.score + ', ' + delta + (delta === 1 ? ' point' : ' points') + ' back.'
          : 'Left out ' + name + ': no change on its own, because other ingredients trigger the same checks.';
      } else {
        lead = delta < 0
          ? 'Put ' + name + ' back: the score goes from ' + was + ' to ' + result.score + ', ' + Math.abs(delta) + (Math.abs(delta) === 1 ? ' point' : ' points') + ' lost.'
          : 'Put ' + name + ' back: no change on its own.';
      }
      setSay(lead + (note ? ' <span class="why">' + esc(note) + '</span>' : ''));
    }).catch(() => {
      setSay('The preview could not reach the server. Check that the app is still running.');
    });
  }

  flagToks.forEach(tok => tok.addEventListener('click', () => toggle(tok)));

  reset.addEventListener('click', () => {
    flagToks.forEach(t => { t.classList.remove('out'); t.setAttribute('aria-pressed', 'false'); });
    reset.hidden = true;
    const mine = ++sequence;
    preview().then(result => {
      if (mine !== sequence) return;
      current = result;
      setGauge(gaugeWrap.querySelector('.gauge'), result.score, result.grade);
      setSay(DEFAULT_SAY);
    }).catch(() => {});
  });

  preview().then(result => {
    base = current = result;
    gaugeWrap.innerHTML = gaugeHTML(result.score, result.grade);
    mountGauges(gaugeWrap);
    renderBars(result.nutrients);
  }).catch(() => {
    setSay('The live sample needs the app server. Start it with python run.py and reload.');
  });
})();
