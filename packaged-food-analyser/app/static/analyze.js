(function () {
  const tabs = Array.from(document.querySelectorAll('.tab'));
  const panels = Array.from(document.querySelectorAll('.panel'));
  const emptyEl = document.getElementById('empty');
  const resultEl = document.getElementById('result');
  const area = document.getElementById('result-area');
  const imageInput = document.getElementById('image-input');
  const drop = document.getElementById('drop');
  const previewRow = document.getElementById('preview-row');
  const previewImg = document.getElementById('image-preview');
  let objectUrl = null;

  function showPanel(name) {
    tabs.forEach(t => {
      const on = t.dataset.tab === name;
      t.classList.toggle('active', on);
      t.setAttribute('aria-selected', on ? 'true' : 'false');
      t.tabIndex = on ? 0 : -1;
    });
    panels.forEach(p => {
      const on = p.dataset.panel === name;
      p.classList.toggle('active', on);
      p.hidden = !on;
    });
  }
  tabs.forEach((tab, i) => {
    tab.addEventListener('click', () => showPanel(tab.dataset.tab));
    tab.addEventListener('keydown', event => {
      if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
      const next = tabs[(i + (event.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length];
      showPanel(next.dataset.tab);
      next.focus();
    });
  });

  function busy(message) {
    emptyEl.hidden = true;
    resultEl.hidden = false;
    resultEl.innerHTML = '<div class="loading"><span class="spinner" aria-hidden="true"></span><p>' + esc(message) + '</p></div>';
    document.querySelectorAll('.input-panel .btn').forEach(b => { b.disabled = true; });
    scrollToResult();
  }
  function idle() {
    document.querySelectorAll('.input-panel .btn').forEach(b => { b.disabled = false; });
  }
  function scrollToResult() {
    if (window.matchMedia('(max-width: 900px)').matches) {
      area.scrollIntoView({behavior: REDUCED ? 'auto' : 'smooth', block: 'start'});
    }
  }
  function useText(text) {
    document.getElementById('text-input').value = text;
    showPanel('text');
  }
  function fail(message, ocrText) {
    idle();
    emptyEl.hidden = true;
    resultEl.hidden = false;
    let html = '<div class="notice error"><strong>' + esc(message) + '</strong>';
    if (ocrText) {
      html += '<p>The text we read from the photo has been copied into the Paste text tab. Fix any mistakes there and analyse it again.</p>';
    } else {
      html += '<p>Check the input and try again, or switch to another tab.</p>';
    }
    html += '</div>';
    resultEl.innerHTML = html;
    if (ocrText) useText(ocrText);
  }
  function show(result) {
    idle();
    emptyEl.hidden = true;
    resultEl.hidden = false;
    renderResult(result, resultEl);
    if (result.ocr_text) {
      const button = document.createElement('button');
      button.className = 'btn no-print';
      button.type = 'button';
      button.textContent = 'Wrong reading? Edit the extracted text';
      button.addEventListener('click', () => { useText(result.ocr_text); window.scrollTo({top: 0, behavior: REDUCED ? 'auto' : 'smooth'}); });
      const actions = resultEl.querySelector('.report-actions');
      (actions || resultEl.querySelector('.report')).appendChild(button);
    }
    scrollToResult();
  }
  async function send(promise) {
    try {
      const response = await promise;
      const data = await response.json();
      if (!response.ok) { fail(data.error || 'Something went wrong.', data.ocr_text); return; }
      show(data);
    } catch (err) {
      fail('Could not reach the server.');
    }
  }

  fetch('/api/products').then(r => r.json()).then(items => {
    const box = document.getElementById('sample-chips');
    if (!items.length) { box.innerHTML = '<span class="small">No products in the database yet.</span>'; return; }
    box.innerHTML = items.map(p =>
      '<button type="button" class="chip pick-chip" data-code="' + esc(p.barcode) + '">' + esc(p.name) + '</button>').join('');
    box.querySelectorAll('button').forEach(b => b.addEventListener('click', () => {
      document.getElementById('barcode-input').value = b.dataset.code;
      document.getElementById('form-barcode').requestSubmit();
    }));
  }).catch(() => { document.getElementById('sample-chips').innerHTML = ''; });

  function setFile(file) {
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    if (!file) {
      objectUrl = null;
      previewRow.hidden = true;
      document.getElementById('drop-title').textContent = 'Drop a label photo here';
      return;
    }
    objectUrl = URL.createObjectURL(file);
    previewImg.src = objectUrl;
    previewRow.hidden = false;
    document.getElementById('drop-title').textContent = file.name;
  }
  function adopt(fileList) {
    const file = fileList && fileList[0];
    if (!file || !file.type.startsWith('image/')) return false;
    const transfer = new DataTransfer();
    transfer.items.add(file);
    imageInput.files = transfer.files;
    setFile(file);
    return true;
  }

  imageInput.addEventListener('change', () => setFile(imageInput.files[0]));
  document.getElementById('image-clear').addEventListener('click', () => { imageInput.value = ''; setFile(null); });
  ['dragenter', 'dragover'].forEach(name => drop.addEventListener(name, event => { event.preventDefault(); drop.classList.add('over'); }));
  ['dragleave', 'drop'].forEach(name => drop.addEventListener(name, event => { event.preventDefault(); drop.classList.remove('over'); }));
  drop.addEventListener('drop', event => { adopt(event.dataTransfer.files); });
  document.addEventListener('paste', event => {
    if (adopt(event.clipboardData && event.clipboardData.files)) showPanel('image');
  });

  document.getElementById('form-image').addEventListener('submit', event => {
    event.preventDefault();
    if (!imageInput.files[0]) { fail('Choose a label photo first.'); return; }
    const data = new FormData();
    data.append('image', imageInput.files[0]);
    const barcode = document.getElementById('image-barcode').value.trim();
    if (barcode) data.append('barcode', barcode);
    busy('Reading the label. This can take a few seconds.');
    send(fetch('/api/analyze/image', {method: 'POST', body: data}));
  });

  document.getElementById('form-barcode').addEventListener('submit', event => {
    event.preventDefault();
    const code = document.getElementById('barcode-input').value.trim();
    busy('Looking up the product.');
    send(fetch('/api/analyze/barcode/' + encodeURIComponent(code)));
  });

  document.getElementById('barcode-image').addEventListener('change', event => {
    const file = event.target.files[0];
    if (!file) return;
    const data = new FormData();
    data.append('image', file);
    busy('Reading the barcode.');
    send(fetch('/api/analyze/barcode-image', {method: 'POST', body: data}));
    event.target.value = '';
  });

  document.getElementById('form-text').addEventListener('submit', event => {
    event.preventDefault();
    busy('Checking the ingredients.');
    send(fetch('/api/analyze/text', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text: document.getElementById('text-input').value})
    }));
  });

  document.getElementById('load-sample').addEventListener('click', () => {
    document.getElementById('text-input').value =
      'Ingredients: Refined wheat flour (maida) 42%, Sugar, Palm oil, Glucose syrup, Milk solids, Cocoa powder, ' +
      'Raising agents (E500, E450), Emulsifier (Soy lecithin E322), Iodised salt, Colour (E102), Flavour.\n' +
      'Contains: Wheat, Milk, Soy.\nMay contain: Peanuts, Tree nuts.\n' +
      'Nutrition Information (per 100 g)\nEnergy 495 kcal\nProtein 6.1 g\nCarbohydrate 68 g\nTotal Sugars 31 g\n' +
      'Added Sugars 29 g\nTotal Fat 22 g\nSaturated Fat 11.5 g\nTrans Fat 0.2 g\nDietary Fibre 2.1 g\nSodium 410 mg';
  });
})();
