// Portfolio Optimization by Markowits — Linear / Swiss Minimalist Frontend Engine
let currentInputMode = 'hayinsights';
let currentCashMode = 'bkm';
let tickerDirectory = [];
let tickerMetaMap = {};
let quizQuestions = [];
let selectedHayTickers = ['FPT', 'MWG', 'VCB', 'HPG', 'VNM'];
let liveLatestPrices = {};
let dropdownHighlightIdx = -1;
let currentDropdownResults = [];
let lastAnalysisData = null;

let manualState = {
  symbols: ['FPT', 'MWG', 'VCB', 'HPG'],
  expected_returns: [0.24, 0.165, 0.135, 0.175],
  std_devs: [0.22, 0.285, 0.18, 0.275],
  corr_matrix: [
    [1.00, 0.42, 0.35, 0.38],
    [0.42, 1.00, 0.40, 0.46],
    [0.35, 0.40, 1.00, 0.32],
    [0.38, 0.46, 0.32, 1.00]
  ],
  latest_prices: { FPT: 114500, MWG: 65200, VCB: 91500, HPG: 27100 }
};

const fmtVND = new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 0 });
const fmtNum = (v, digits = 2) => (v !== undefined && v !== null && !Number.isNaN(Number(v)) ? Number(v).toFixed(digits) : '--');
const fmtPct = (v, digits = 2) => (v !== undefined && v !== null && !Number.isNaN(Number(v)) ? (Number(v) * 100).toFixed(digits) + '%' : '--%');

document.addEventListener('DOMContentLoaded', async () => {
  initTheme();
  bindUIEvents();
  await loadPresets();
  renderManualTable();
  await runMVOOptimization();
});

// --- Theme Management (Light / Dark Mode) ---
function isDarkMode() {
  return document.documentElement.classList.contains('dark');
}

function initTheme() {
  const saved = localStorage.getItem('mvo_theme');
  if (saved === 'light') {
    document.documentElement.classList.remove('dark');
  } else if (saved === 'dark') {
    document.documentElement.classList.add('dark');
  } else {
    // Default to clean Light Mode (Dasher / Swiss style)
    document.documentElement.classList.remove('dark');
  }
  updateThemeIcons();
}

function toggleTheme() {
  const htmlEl = document.documentElement;
  if (htmlEl.classList.contains('dark')) {
    htmlEl.classList.remove('dark');
    localStorage.setItem('mvo_theme', 'light');
  } else {
    htmlEl.classList.add('dark');
    localStorage.setItem('mvo_theme', 'dark');
  }
  updateThemeIcons();
  if (lastAnalysisData) {
    renderPlotlyFrontier(lastAnalysisData);
    renderPlotlyWeights(lastAnalysisData);
    renderBenchmarkTab(lastAnalysisData);
  }
}

function updateThemeIcons() {
  const dark = isDarkMode();
  const sun = document.getElementById('icon-theme-sun');
  const moon = document.getElementById('icon-theme-moon');
  if (sun && moon) {
    sun.classList.toggle('hidden', !dark);
    moon.classList.toggle('hidden', dark);
  }
}

// --- Lower Tab Switching ---
function switchLowerTab(tabName) {
  const tabs = ['execution', 'benchmark', 'stress', 'moments', 'algebra'];
  tabs.forEach(t => {
    const btn = document.getElementById(`tab-btn-${t}`);
    const panel = document.getElementById(`tab-panel-${t}`);
    if (btn) btn.classList.toggle('active', t === tabName);
    if (panel) panel.classList.toggle('hidden', t !== tabName);
  });
  if (tabName === 'benchmark' && lastAnalysisData) {
    setTimeout(() => {
      const el = document.getElementById('chart-benchmark-cum');
      if (el && window.Plotly) Plotly.Plots.resize(el);
    }, 30);
  }
}

// --- Weight Bounds & Cash Allocation Controls ---
function toggleTT98Preset(checked) {
  const rngMin = document.getElementById('rng-w-min');
  const rngMax = document.getElementById('rng-w-max');
  if (checked) {
    if (rngMin) rngMin.value = 0;
    if (rngMax) rngMax.value = 20;
  } else {
    if (rngMax) rngMax.value = 100;
  }
  onWeightBoundSliderChange(true);
}

function onWeightBoundSliderChange(triggerRun = false) {
  const rngMin = document.getElementById('rng-w-min');
  const rngMax = document.getElementById('rng-w-max');
  const lblMin = document.getElementById('lbl-w-min');
  const lblMax = document.getElementById('lbl-w-max');
  const chkTT98 = document.getElementById('chk-tt98-cap');

  const vMin = parseInt(rngMin?.value || '0', 10);
  const vMax = parseInt(rngMax?.value || '100', 10);

  if (lblMin) lblMin.textContent = `${vMin}%`;
  if (lblMax) lblMax.textContent = `${vMax}%`;
  if (chkTT98) chkTT98.checked = (vMin === 0 && vMax === 20);

  if (triggerRun) {
    runMVOOptimization();
  }
}

function setCashMode(mode) {
  currentCashMode = mode === 'mandated' ? 'mandated' : 'bkm';
  const btnBkm = document.getElementById('btn-cash-mode-bkm');
  const btnMan = document.getElementById('btn-cash-mode-mandated');
  const hintBkm = document.getElementById('panel-bkm-cash-hint');
  const panelMan = document.getElementById('panel-mandated-cash');

  if (btnBkm) btnBkm.classList.toggle('active', currentCashMode === 'bkm');
  if (btnMan) btnMan.classList.toggle('active', currentCashMode === 'mandated');
  if (hintBkm) hintBkm.classList.toggle('hidden', currentCashMode !== 'bkm');
  if (panelMan) panelMan.classList.toggle('hidden', currentCashMode !== 'mandated');

  runMVOOptimization();
}

function syncMandatedCashInput(val) {
  const v = Math.max(0, Math.min(90, parseFloat(val) || 0));
  const inp = document.getElementById('inp-mandated-cash');
  const rng = document.getElementById('rng-mandated-cash');
  if (inp) inp.value = v;
  if (rng) rng.value = Math.min(50, v);
}

function syncMandatedCashSlider(val) {
  const v = Math.max(0, Math.min(90, parseFloat(val) || 0));
  const inp = document.getElementById('inp-mandated-cash');
  if (inp) inp.value = v;
}

// --- Event Bindings ---
function bindUIEvents() {
  document.getElementById('rng-risk-a').addEventListener('input', (e) => {
    const val = parseFloat(e.target.value).toFixed(1);
    document.getElementById('lbl-risk-a').textContent = val;
  });
  document.getElementById('rng-risk-a').addEventListener('change', () => runMVOOptimization());

  const rngWMin = document.getElementById('rng-w-min');
  const rngWMax = document.getElementById('rng-w-max');
  const rngCash = document.getElementById('rng-mandated-cash');
  if (rngWMin) rngWMin.addEventListener('change', () => runMVOOptimization());
  if (rngWMax) rngWMax.addEventListener('change', () => runMVOOptimization());
  if (rngCash) rngCash.addEventListener('change', () => runMVOOptimization());

  document.getElementById('chk-allow-short').addEventListener('change', (e) => {
    const allow = e.target.checked;
    const wbPanel = document.getElementById('panel-weight-bounds');
    if (wbPanel) {
      wbPanel.style.opacity = allow ? '0.45' : '1';
      wbPanel.style.pointerEvents = allow ? 'none' : 'auto';
    }
    document.getElementById('lbl-short-desc').innerHTML = allow
      ? 'Unconstrained (Merton closed-form &Sigma;<sup>-1</sup>)'
      : 'Long-only (w<sub>i</sub> &ge; 0, Quadratic Programming)';
    runMVOOptimization();
  });

  const inpSearch = document.getElementById('inp-ticker-search');
  const btnToggleDd = document.getElementById('btn-toggle-ticker-dropdown');
  const ddMenu = document.getElementById('ticker-autocomplete-dropdown');

  if (inpSearch) {
    inpSearch.addEventListener('focus', () => openTickerDropdown(inpSearch.value));
    inpSearch.addEventListener('input', (e) => openTickerDropdown(e.target.value));
    inpSearch.addEventListener('keydown', handleTickerSearchKeydown);
  }

  if (btnToggleDd) {
    btnToggleDd.addEventListener('click', (e) => {
      e.stopPropagation();
      if (ddMenu && !ddMenu.classList.contains('hidden')) {
        closeTickerDropdown();
      } else {
        if (inpSearch) inpSearch.focus();
        openTickerDropdown(inpSearch ? inpSearch.value : '');
      }
    });
  }

  document.addEventListener('click', (e) => {
    const wrapper = document.getElementById('ticker-search-wrapper');
    if (wrapper && !wrapper.contains(e.target)) {
      closeTickerDropdown();
    }
  });

  document.getElementById('inp-excel-upload').addEventListener('change', handleExcelUpload);
  document.getElementById('btn-run-mvo').addEventListener('click', runMVOOptimization);
  document.getElementById('btn-export-excel').addEventListener('click', exportInstitutionalExcel);
}

async function loadPresets() {
  try {
    const res = await fetch('/api/presets');
    const data = await res.json();
    tickerDirectory = data.ticker_directory || [];
    tickerMetaMap = {};
    tickerDirectory.forEach(item => {
      tickerMetaMap[item.symbol] = item;
    });
    quizQuestions = data.quiz_questions || [];
    syncBasketUI();
    renderQuizQuestions();
  } catch (err) {
    console.error('Failed to load presets:', err);
  }
}

function getHayInsightsSymbolList() {
  return [...selectedHayTickers];
}

function syncBasketUI() {
  const hiddenInp = document.getElementById('inp-hayinsights-symbols');
  if (hiddenInp) hiddenInp.value = selectedHayTickers.join(', ');
  const cntLbl = document.getElementById('lbl-basket-count');
  if (cntLbl) cntLbl.textContent = selectedHayTickers.length;
  renderSelectedTickerPills();
  updateAssetCountBadge();
}

function applyQuickBasket(syms) {
  selectedHayTickers = [...new Set(syms.map(s => s.trim().toUpperCase()).filter(Boolean))];
  syncBasketUI();
  runMVOOptimization();
}

function addTickerToBasket(sym) {
  const s = (sym || '').trim().toUpperCase();
  if (!s) return;
  if (!selectedHayTickers.includes(s)) {
    selectedHayTickers.push(s);
    syncBasketUI();
    fetchLiveQuoteForPill(s);
  }
}

function removeTickerFromBasket(sym) {
  if (selectedHayTickers.length <= 2) {
    alert('Portfolio requires at least 2 assets.');
    return;
  }
  selectedHayTickers = selectedHayTickers.filter(s => s !== sym);
  syncBasketUI();
}

async function fetchLiveQuoteForPill(sym) {
  try {
    const res = await fetch(`/api/hayinsights/quote/${encodeURIComponent(sym)}`);
    if (!res.ok) return;
    const info = await res.json();
    if (info && info.latest_price) {
      liveLatestPrices[sym] = info.latest_price;
      if (!tickerMetaMap[sym]) {
        tickerMetaMap[sym] = {
          symbol: sym,
          name: info.name || sym,
          exchange: info.exchange || 'VN',
          sector: info.sector || 'Equity'
        };
      }
      renderSelectedTickerPills();
    }
  } catch (_) {}
}

function renderSelectedTickerPills() {
  const container = document.getElementById('selected-ticker-pills');
  if (!container) return;
  container.innerHTML = '';

  selectedHayTickers.forEach(sym => {
    const meta = tickerMetaMap[sym] || {};
    const price = liveLatestPrices[sym];
    const priceHtml = price
      ? `<span class="text-[10px] font-mono" style="color: var(--text-muted);">${fmtVND.format(price)}</span>`
      : '';

    const pill = document.createElement('div');
    pill.className = 'inline-flex items-center gap-1.5 px-2 py-0.5 rounded swiss-card text-xs';
    pill.title = meta.name ? `${sym} — ${meta.name} (${meta.exchange || 'HOSE'})` : sym;
    pill.innerHTML = `
      <span class="font-semibold font-mono text-[11px]" style="color: var(--text-primary);">${sym}</span>
      ${priceHtml}
      <button type="button" class="text-[11px] leading-none hover: opacity-75" style="color: var(--text-muted);" title="Remove ${sym}">&times;</button>
    `;
    pill.querySelector('button').onclick = (e) => {
      e.stopPropagation();
      removeTickerFromBasket(sym);
    };
    container.appendChild(pill);
  });
}

function searchLocalTickerDirectory(query) {
  const q = (query || '').trim();
  if (!q) return tickerDirectory.slice(0, 40);

  const qUp = q.toUpperCase();
  const qLow = q.toLowerCase();

  const exact = [];
  const prefix = [];
  const subSym = [];
  const subMeta = [];

  for (const item of tickerDirectory) {
    const sym = item.symbol;
    if (sym === qUp) exact.push(item);
    else if (sym.startsWith(qUp)) prefix.push(item);
    else if (sym.includes(qUp)) subSym.push(item);
    else if (
      (item.name && item.name.toLowerCase().includes(qLow)) ||
      (item.sector && item.sector.toLowerCase().includes(qLow)) ||
      (item.exchange && item.exchange.toLowerCase().includes(qLow))
    ) {
      subMeta.push(item);
    }
  }

  const combined = [...exact, ...prefix, ...subSym, ...subMeta];
  if (qUp.length >= 2 && qUp.length <= 4 && /^[A-Z0-9]+$/.test(qUp) && !tickerMetaMap[qUp]) {
    combined.push({
      symbol: qUp,
      name: `Fetch '${qUp}' directly from HayInsights API`,
      exchange: 'VN',
      sector: 'Direct API',
      group: 'Custom'
    });
  }
  return combined.slice(0, 35);
}

function highlightMatch(text, query) {
  const q = (query || '').trim().toUpperCase();
  if (!q || !text.startsWith(q)) return text;
  return `<span class="underline font-bold" style="color: var(--accent);">${text.slice(0, q.length)}</span>${text.slice(q.length)}`;
}

function openTickerDropdown(query) {
  const dd = document.getElementById('ticker-autocomplete-dropdown');
  if (!dd) return;
  currentDropdownResults = searchLocalTickerDirectory(query);
  dropdownHighlightIdx = currentDropdownResults.length > 0 ? 0 : -1;
  renderTickerDropdownItems(query);
  dd.classList.remove('hidden');
}

function closeTickerDropdown() {
  const dd = document.getElementById('ticker-autocomplete-dropdown');
  if (dd) dd.classList.add('hidden');
  dropdownHighlightIdx = -1;
}

function renderTickerDropdownItems(query) {
  const dd = document.getElementById('ticker-autocomplete-dropdown');
  if (!dd) return;

  if (currentDropdownResults.length === 0) {
    dd.innerHTML = `<div class="p-3 text-xs text-center" style="color: var(--text-muted);">No matching ticker found.</div>`;
    return;
  }

  let html = '';
  currentDropdownResults.forEach((item, idx) => {
    const isSelected = selectedHayTickers.includes(item.symbol);
    const isHighlighted = idx === dropdownHighlightIdx;
    const bgStyle = isHighlighted ? 'background-color: var(--bg-subtle);' : '';

    const statusBadge = isSelected
      ? `<span class="px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold" style="background-color: var(--accent-soft); color: var(--accent);">Added</span>`
      : `<span class="px-1.5 py-0.5 rounded text-[10px] font-mono swiss-subtle" style="color: var(--text-muted);">+ Add</span>`;

    html += `
      <div data-idx="${idx}" data-sym="${item.symbol}" style="${bgStyle} border-color: var(--border-color);"
        class="ticker-dd-item flex items-center justify-between gap-2 px-3 py-2 cursor-pointer transition">
        <div class="flex items-center gap-2 min-w-0 flex-1">
          ${statusBadge}
          <span class="font-mono font-semibold text-xs w-11 shrink-0" style="color: var(--text-primary);">${highlightMatch(item.symbol, query)}</span>
          <span class="text-xs truncate" style="color: var(--text-secondary);">${item.name}</span>
        </div>
        <div class="flex items-center gap-1.5 shrink-0">
          <span class="text-[10px] hidden sm:inline" style="color: var(--text-muted);">${item.sector || ''}</span>
          <span class="text-[10px] font-mono px-1.5 py-0.5 rounded swiss-subtle" style="color: var(--text-secondary);">${item.exchange || 'VN'}</span>
        </div>
      </div>
    `;
  });

  dd.innerHTML = html;

  dd.querySelectorAll('.ticker-dd-item').forEach(el => {
    el.addEventListener('click', (e) => {
      e.stopPropagation();
      const sym = el.getAttribute('data-sym');
      handleDropdownSelectTicker(sym);
    });
  });
}

function handleDropdownSelectTicker(sym) {
  if (!sym) return;
  if (selectedHayTickers.includes(sym)) {
    removeTickerFromBasket(sym);
  } else {
    addTickerToBasket(sym);
  }
  const inpSearch = document.getElementById('inp-ticker-search');
  if (inpSearch) {
    inpSearch.value = '';
    openTickerDropdown('');
    inpSearch.focus();
  }
}

function handleTickerSearchKeydown(e) {
  const dd = document.getElementById('ticker-autocomplete-dropdown');
  const isOpen = dd && !dd.classList.contains('hidden');

  if (e.key === 'ArrowDown') {
    e.preventDefault();
    if (!isOpen) {
      openTickerDropdown(e.target.value);
      return;
    }
    if (currentDropdownResults.length > 0) {
      dropdownHighlightIdx = (dropdownHighlightIdx + 1) % currentDropdownResults.length;
      renderTickerDropdownItems(e.target.value);
      scrollDropdownToHighlight();
    }
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    if (isOpen && currentDropdownResults.length > 0) {
      dropdownHighlightIdx = (dropdownHighlightIdx - 1 + currentDropdownResults.length) % currentDropdownResults.length;
      renderTickerDropdownItems(e.target.value);
      scrollDropdownToHighlight();
    }
  } else if (e.key === 'Enter') {
    e.preventDefault();
    if (isOpen && dropdownHighlightIdx >= 0 && currentDropdownResults[dropdownHighlightIdx]) {
      handleDropdownSelectTicker(currentDropdownResults[dropdownHighlightIdx].symbol);
    } else {
      const raw = e.target.value.trim().toUpperCase();
      if (raw.length >= 2) {
        addTickerToBasket(raw);
        e.target.value = '';
        openTickerDropdown('');
      }
    }
  } else if (e.key === 'Escape') {
    closeTickerDropdown();
  }
}

function scrollDropdownToHighlight() {
  const dd = document.getElementById('ticker-autocomplete-dropdown');
  if (!dd || dropdownHighlightIdx < 0) return;
  const item = dd.querySelector(`.ticker-dd-item[data-idx="${dropdownHighlightIdx}"]`);
  if (item) item.scrollIntoView({ block: 'nearest' });
}

function setInputMode(mode) {
  currentInputMode = mode === 'manual' ? 'manual' : 'hayinsights';
  const btnHay = document.getElementById('tab-mode-hayinsights');
  const btnManual = document.getElementById('tab-mode-manual');
  const panelHay = document.getElementById('panel-hayinsights-input');
  const panelManual = document.getElementById('panel-manual-input');

  if (btnHay) btnHay.classList.toggle('active', currentInputMode === 'hayinsights');
  if (btnManual) btnManual.classList.toggle('active', currentInputMode === 'manual');

  if (panelHay) panelHay.classList.toggle('hidden', currentInputMode !== 'hayinsights');
  if (panelManual) panelManual.classList.toggle('hidden', currentInputMode !== 'manual');

  document.getElementById('lbl-data-source-tag').textContent =
    currentInputMode === 'hayinsights' ? 'HayInsights Live API' : 'Manual / Excel Matrix';
  updateAssetCountBadge();
}

function updateAssetCountBadge() {
  const count = currentInputMode === 'hayinsights'
    ? getHayInsightsSymbolList().length
    : manualState.symbols.length;
  const el = document.getElementById('lbl-asset-count');
  if (el) el.textContent = count;
}

// --- Manual Matrix Editor ---
function renderManualTable() {
  const tbl = document.getElementById('manual-param-table');
  if (!tbl) return;
  const n = manualState.symbols.length;

  let html = `<thead><tr>
    <th>Ticker</th>
    <th class="text-right">E(R) %</th>
    <th class="text-right">&sigma; %</th>`;
  for (let i = 0; i < n; i++) {
    html += `<th class="text-center">&rho;(${manualState.symbols[i]})</th>`;
  }
  html += `</tr></thead><tbody>`;

  for (let i = 0; i < n; i++) {
    html += `<tr>
      <td><input type="text" value="${manualState.symbols[i]}" onchange="updateManualSymbol(${i}, this.value)" class="swiss-input w-14 px-1.5 py-0.5 font-semibold uppercase text-xs" /></td>
      <td><input type="number" step="0.5" value="${(manualState.expected_returns[i] * 100).toFixed(2)}" onchange="updateManualER(${i}, this.value)" class="swiss-input w-16 px-1.5 py-0.5 text-right text-xs" /></td>
      <td><input type="number" step="0.5" value="${(manualState.std_devs[i] * 100).toFixed(2)}" onchange="updateManualStd(${i}, this.value)" class="swiss-input w-16 px-1.5 py-0.5 text-right text-xs" /></td>`;
    for (let j = 0; j < n; j++) {
      const ro = i === j ? 'readonly' : '';
      html += `<td><input type="number" step="0.05" min="-0.99" max="1.0" ${ro} value="${manualState.corr_matrix[i][j].toFixed(2)}" onchange="updateManualCorr(${i}, ${j}, this.value)" class="swiss-input w-14 px-1 py-0.5 text-center text-xs" /></td>`;
    }
    html += `</tr>`;
  }
  html += `</tbody>`;
  tbl.innerHTML = html;
  updateAssetCountBadge();
}

function updateManualSymbol(idx, val) {
  manualState.symbols[idx] = val.trim().toUpperCase() || `A${idx + 1}`;
  renderManualTable();
}
function updateManualER(idx, val) {
  manualState.expected_returns[idx] = (parseFloat(val) || 0) / 100.0;
}
function updateManualStd(idx, val) {
  manualState.std_devs[idx] = Math.max(0.01, (parseFloat(val) || 10) / 100.0);
}
function updateManualCorr(i, j, val) {
  const v = Math.max(-0.95, Math.min(1.0, parseFloat(val) || 0));
  manualState.corr_matrix[i][j] = v;
  manualState.corr_matrix[j][i] = v;
  renderManualTable();
}

function addManualAssetRow() {
  const n = manualState.symbols.length;
  if (n >= 10) return;
  const newSym = `CP${n + 1}`;
  manualState.symbols.push(newSym);
  manualState.expected_returns.push(0.15);
  manualState.std_devs.push(0.24);
  manualState.corr_matrix.forEach(row => row.push(0.30));
  const newRow = new Array(n + 1).fill(0.30);
  newRow[n] = 1.0;
  manualState.corr_matrix.push(newRow);
  manualState.latest_prices[newSym] = 50000;
  renderManualTable();
}

function removeManualAssetRow() {
  if (manualState.symbols.length <= 2) return;
  manualState.symbols.pop();
  manualState.expected_returns.pop();
  manualState.std_devs.pop();
  manualState.corr_matrix.pop();
  manualState.corr_matrix.forEach(row => row.pop());
  renderManualTable();
}

async function handleExcelUpload(e) {
  const file = e.target.files[0];
  if (!file) return;
  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/api/upload-excel', { method: 'POST', body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error reading Excel file');

    manualState.symbols = data.symbols;
    manualState.expected_returns = data.expected_returns;
    manualState.std_devs = data.std_devs;
    manualState.corr_matrix = data.corr_matrix;
    manualState.latest_prices = data.latest_prices || {};

    setInputMode('manual');
    renderManualTable();
    document.getElementById('lbl-data-source-tag').textContent = `${file.name} (${data.sessions_count}d)`;
    await runMVOOptimization();
  } catch (err) {
    alert('Upload error: ' + err.message);
  }
}

// --- Risk Tolerance Quiz Modal ---
function renderQuizQuestions() {
  const container = document.getElementById('quiz-questions-container');
  if (!container) return;
  container.innerHTML = '';
  quizQuestions.forEach((q, qIdx) => {
    const card = document.createElement('div');
    card.className = 'p-3.5 swiss-subtle space-y-2';
    let optsHtml = '';
    q.options.forEach((opt, oIdx) => {
      const checked = oIdx === 2 ? 'checked' : '';
      optsHtml += `
        <label class="flex items-start space-x-2 cursor-pointer py-0.5" style="color: var(--text-secondary);">
          <input type="radio" name="quiz_q_${qIdx}" value="${opt.score}" ${checked} class="mt-0.5" style="accent-color: var(--accent);" />
          <span>${opt.label}</span>
        </label>`;
    });
    card.innerHTML = `<div class="font-semibold" style="color: var(--text-primary);">${q.question}</div><div class="space-y-1">${optsHtml}</div>`;
    container.appendChild(card);
  });
}

function toggleQuizModal() {
  const panel = document.getElementById('quiz-box-panel');
  if (panel) panel.classList.toggle('hidden');
}

async function submitRiskQuiz() {
  const scores = [];
  for (let i = 0; i < quizQuestions.length; i++) {
    const sel = document.querySelector(`input[name="quiz_q_${i}"]:checked`);
    scores.push(sel ? parseInt(sel.value, 10) : 3);
  }

  try {
    const res = await fetch('/api/quiz', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scores })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error evaluating quiz');

    document.getElementById('rng-risk-a').value = data.risk_aversion_A ?? 3.0;
    document.getElementById('lbl-risk-a').textContent = fmtNum(data.risk_aversion_A, 1);
    document.getElementById('quiz-profile-badge').textContent = `${data.profile_tier || 'Moderate'} (A = ${fmtNum(data.risk_aversion_A, 1)})`;
    document.getElementById('quiz-result-summary').textContent = `${data.profile_tier}: ${data.description}`;

    toggleQuizModal();
    await runMVOOptimization();
  } catch (err) {
    alert(err.message);
  }
}

// --- Benchmark Horizon & Index Synchronization ---
function onBenchmarkConfigChange(newSym, newHorizon) {
  const selBmLeft = document.getElementById('sel-benchmark');
  const selBmTab = document.getElementById('sel-benchmark-tab');
  const selHorLeft = document.getElementById('sel-benchmark-horizon');
  const selHorTab = document.getElementById('sel-benchmark-horizon-tab');

  if (newSym) {
    if (selBmLeft) selBmLeft.value = newSym;
    if (selBmTab) selBmTab.value = newSym;
  }
  if (newHorizon) {
    if (selHorLeft) selHorLeft.value = newHorizon;
    if (selHorTab) selHorTab.value = newHorizon;
  }
  runMVOOptimization();
}

// --- MVO Request & Execution ---
function buildRequestPayload() {
  const rf = (parseFloat(document.getElementById('inp-rf').value) || 4.5) / 100.0;
  const nav = parseFloat(document.getElementById('inp-nav').value) || 1_000_000_000;
  const riskA = parseFloat(document.getElementById('rng-risk-a').value) || 3.0;
  const allowShort = document.getElementById('chk-allow-short').checked;
  const wMin = (parseFloat(document.getElementById('rng-w-min')?.value) || 0) / 100.0;
  const wMax = (parseFloat(document.getElementById('rng-w-max')?.value) || 100) / 100.0;
  const mandatedCashPct = (parseFloat(document.getElementById('inp-mandated-cash')?.value) || 0) / 100.0;
  const bmSym = document.getElementById('sel-benchmark')?.value || 'VNINDEX';
  const bmRange = document.getElementById('sel-benchmark-horizon')?.value || '1y';

  const baseParams = {
    rf: rf,
    risk_aversion_A: riskA,
    allow_short: allowShort,
    w_min: wMin,
    w_max: wMax,
    cash_mode: currentCashMode,
    mandated_cash_pct: mandatedCashPct,
    benchmark_symbol: bmSym,
    benchmark_range: bmRange,
    nav_vnd: nav,
    n_monte_carlo: 2500
  };

  if (currentInputMode === 'hayinsights') {
    const syms = getHayInsightsSymbolList();
    const rng = document.getElementById('sel-hayinsights-range')?.value || '1y';
    const useAdj = document.getElementById('chk-hayinsights-adj')?.checked ?? true;
    return {
      input_mode: 'hayinsights',
      symbols: syms,
      hayinsights_range: rng,
      use_adjusted_close: useAdj,
      ...baseParams
    };
  } else {
    return {
      input_mode: 'manual',
      symbols: manualState.symbols,
      expected_returns: manualState.expected_returns,
      std_devs: manualState.std_devs,
      corr_matrix: manualState.corr_matrix,
      latest_prices: manualState.latest_prices,
      ...baseParams
    };
  }
}

async function runMVOOptimization() {
  const payload = buildRequestPayload();
  if (payload.symbols.length < 2) {
    alert('Please select at least 2 assets.');
    return;
  }

  const btn = document.getElementById('btn-run-mvo');
  const oldHtml = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span>Computing Optimization...</span>';

  try {
    const res = await fetch('/api/optimize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Optimization error');

    lastAnalysisData = data;

    if (data.latest_prices) {
      Object.assign(liveLatestPrices, data.latest_prices);
      renderSelectedTickerPills();
    }

    if (data.data_meta && data.data_meta.from_date) {
      document.getElementById('lbl-data-source-tag').textContent =
        `${data.data_meta.from_date} → ${data.data_meta.to_date} (${data.sessions_count}d)`;
    }

    const noteEl = document.getElementById('box-bounds-note');
    if (noteEl) {
      if (data.bounds_adjusted_note) {
        noteEl.textContent = data.bounds_adjusted_note;
        noteEl.classList.remove('hidden');
      } else {
        noteEl.textContent = '';
        noteEl.classList.add('hidden');
      }
    }

    const modeLbl = document.getElementById('chart-mode-label');
    if (modeLbl) {
      if (data.allow_short) {
        modeLbl.innerHTML = 'Short-Sales Allowed (Closed-Form)';
      } else {
        const minP = Math.round((data.w_min ?? 0) * 100);
        const maxP = Math.round((data.w_max ?? 1) * 100);
        if (minP > 0 || maxP < 100) {
          modeLbl.innerHTML = `Bounded QP (${minP}% &le; w<sub>i</sub> &le; ${maxP}%)`;
        } else {
          modeLbl.innerHTML = 'Long-Only (w<sub>i</sub> &ge; 0)';
        }
      }
    }

    renderKPISummary(data);
    renderPlotlyFrontier(data);
    renderPlotlyWeights(data);
    renderWeightsAndLot100Table(data);
    renderBenchmarkTab(data);
    renderStressTestingTab(data);
    renderMatricesTables(data);
    renderAlgebraStepByStep(data);
  } catch (err) {
    alert('Optimization Error: ' + err.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = oldHtml;
  }
}

function renderKPISummary(data) {
  const tan = data.tangency || {};
  document.getElementById('kpi-tan-ret').textContent = fmtPct(tan.expected_return);
  document.getElementById('kpi-tan-vol').textContent = fmtPct(tan.volatility);
  document.getElementById('kpi-tan-var').textContent = fmtNum(tan.variance, 4);
  document.getElementById('kpi-tan-sr').textContent = fmtNum(tan.sharpe_ratio, 3);

  const gmv = data.gmv || {};
  document.getElementById('kpi-gmv-ret').textContent = fmtPct(gmv.expected_return);
  document.getElementById('kpi-gmv-vol').textContent = fmtPct(gmv.volatility);
  document.getElementById('kpi-gmv-var').textContent = fmtNum(gmv.variance, 4);
  document.getElementById('kpi-gmv-sr').textContent = fmtNum(gmv.sharpe_ratio, 3);

  const comp = data.complete_portfolio || {};
  const yStar = comp.y_star_risky_weight ?? comp.y_risky ?? 0;
  const wRf = comp.w_rf_weight ?? comp.w_rf ?? (1 - yStar);
  const uScore = comp.utility_score ?? comp.utility ?? 0;

  document.getElementById('kpi-comp-y').textContent = fmtPct(yStar, 1);
  document.getElementById('kpi-comp-rfw').textContent = fmtPct(wRf, 1);
  document.getElementById('kpi-comp-ret').textContent = fmtPct(comp.expected_return);
  document.getElementById('kpi-comp-vol').textContent = fmtPct(comp.volatility);
  document.getElementById('kpi-comp-u').textContent = fmtNum(uScore, 4);
}

// --- Plotly Charts (Synchronized with Swiss Light / Dark Theme) ---
function getChartThemeTokens() {
  const dark = isDarkMode();
  return {
    fontColor: dark ? '#cbd5e1' : '#334155',
    gridColor: dark ? '#1e293b' : '#e2e8f0',
    zeroLineColor: dark ? '#334155' : '#cbd5e1',
    navyAccent: dark ? '#3b82f6' : '#2563eb',
    emeraldColor: dark ? '#10b981' : '#059669',
    amberColor: dark ? '#f59e0b' : '#d97706',
    purpleColor: dark ? '#a855f7' : '#7c3aed',
    roseColor: dark ? '#f43f5e' : '#e11d48',
    slateColor: dark ? '#94a3b8' : '#64748b',
    cardBg: dark ? '#0f172a' : '#ffffff'
  };
}

function renderPlotlyFrontier(data) {
  const t = getChartThemeTokens();
  const mc = data.monte_carlo || [];
  const fr = data.frontier || [];
  const tan = data.tangency || {};
  const gmv = data.gmv || {};
  const comp = data.complete_portfolio || {};
  const assets = data.individual_assets || [];
  const bm = data.benchmark_comparison || null;

  // 1. Monte Carlo Random Portfolios (already in % in simulate_monte_carlo)
  const traceMC = {
    x: mc.map(d => d.volatility),
    y: mc.map(d => d.return ?? (d.expected_return * 100)),
    mode: 'markers',
    type: 'scattergl',
    name: 'Feasible Set (Monte Carlo)',
    marker: {
      size: 4,
      color: mc.map(d => d.sharpe ?? d.sharpe_ratio ?? 0),
      colorscale: isDarkMode() ? 'Blues' : 'YlGnBu',
      opacity: isDarkMode() ? 0.35 : 0.45,
      showscale: false
    },
    hoverinfo: 'skip'
  };

  // 2. Efficient Frontier Curve
  const traceFrontier = {
    x: fr.map(p => p.volatility * 100),
    y: fr.map(p => (p.return ?? p.expected_return) * 100),
    mode: 'lines',
    type: 'scatter',
    name: 'Efficient Frontier',
    line: { color: t.navyAccent, width: 3 },
    hovertemplate: '&sigma;: %{x:.2f}%<br>E(R): %{y:.2f}%<extra>Efficient Frontier</extra>'
  };

  // 3. Capital Allocation Line (CAL)
  const traceCAL = {
    x: (comp.cal_line || []).map(p => p.volatility * 100),
    y: (comp.cal_line || []).map(p => (p.return ?? p.expected_return) * 100),
    mode: 'lines',
    type: 'scatter',
    name: 'CAL (Capital Allocation Line)',
    line: { color: t.amberColor, width: 2, dash: 'dash' },
    hovertemplate: '&sigma;: %{x:.2f}%<br>E(R): %{y:.2f}%<extra>CAL</extra>'
  };

  // 4. Utility Indifference Curve
  const traceIndiff = {
    x: (comp.indifference_curve || []).map(p => p.volatility * 100),
    y: (comp.indifference_curve || []).map(p => (p.return ?? p.expected_return) * 100),
    mode: 'lines',
    type: 'scatter',
    name: `Indifference Curve (A=${data.risk_aversion_A})`,
    line: { color: t.purpleColor, width: 1.5, dash: 'dot' },
    hovertemplate: '&sigma;: %{x:.2f}%<br>E(R): %{y:.2f}%<extra>Utility U*</extra>'
  };

  // 5. Individual Assets
  const traceAssets = {
    x: assets.map(a => a.volatility * 100),
    y: assets.map(a => a.expected_return * 100),
    text: assets.map(a => a.symbol),
    mode: 'markers+text',
    type: 'scatter',
    name: 'Individual Assets',
    textposition: 'top center',
    textfont: { family: 'JetBrains Mono', size: 10, color: t.fontColor },
    marker: { size: 8, color: t.slateColor, line: { width: 1.5, color: t.cardBg } },
    hovertemplate: '<b>%{text}</b><br>&sigma;: %{x:.2f}%<br>E(R): %{y:.2f}%<extra></extra>'
  };

  // 6. GMV Portfolio
  const traceGMV = {
    x: [gmv.volatility * 100],
    y: [gmv.expected_return * 100],
    mode: 'markers',
    type: 'scatter',
    name: 'GMV (Min Variance)',
    marker: { size: 11, symbol: 'diamond', color: t.amberColor, line: { width: 1.5, color: t.cardBg } },
    hovertemplate: '<b>GMV Portfolio</b><br>&sigma;: %{x:.2f}%<br>E(R): %{y:.2f}%<extra></extra>'
  };

  // 7. Tangency Portfolio
  const traceTan = {
    x: [tan.volatility * 100],
    y: [tan.expected_return * 100],
    mode: 'markers',
    type: 'scatter',
    name: 'Tangency (Max Sharpe)',
    marker: { size: 12, symbol: 'circle', color: t.emeraldColor, line: { width: 2, color: t.cardBg } },
    hovertemplate: '<b>Tangency Portfolio</b><br>&sigma;: %{x:.2f}%<br>E(R): %{y:.2f}%<br>Sharpe: ' + fmtNum(tan.sharpe_ratio, 3) + '<extra></extra>'
  };

  // 8. Complete Portfolio C
  const traceComp = {
    x: [comp.volatility * 100],
    y: [comp.expected_return * 100],
    mode: 'markers',
    type: 'scatter',
    name: 'Complete Portfolio (C)',
    marker: { size: 11, symbol: 'square', color: t.purpleColor, line: { width: 1.5, color: t.cardBg } },
    hovertemplate: '<b>Complete Portfolio C</b><br>&sigma;: %{x:.2f}%<br>E(R): %{y:.2f}%<extra></extra>'
  };

  const traces = [traceMC, traceFrontier, traceCAL, traceIndiff, traceAssets, traceGMV, traceTan, traceComp];

  // 9. Benchmark Point (VN-Index / VN30)
  if (bm && bm.benchmark_volatility != null && bm.benchmark_return != null) {
    traces.push({
      x: [bm.benchmark_volatility * 100],
      y: [bm.benchmark_return * 100],
      text: [bm.benchmark_symbol],
      mode: 'markers+text',
      type: 'scatter',
      name: `Benchmark (${bm.benchmark_symbol})`,
      textposition: 'bottom center',
      textfont: { family: 'JetBrains Mono', size: 10, color: t.roseColor },
      marker: { size: 11, symbol: 'star', color: t.roseColor, line: { width: 1.5, color: t.cardBg } },
      hovertemplate: `<b>${bm.benchmark_symbol}</b><br>&sigma;: %{x:.2f}%<br>E(R): %{y:.2f}%<br>Sharpe: ${fmtNum(bm.benchmark_sharpe, 3)}<extra></extra>`
    });
  }

  const layout = {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    margin: { l: 50, r: 20, t: 10, b: 42 },
    font: { family: 'Inter, sans-serif', color: t.fontColor, size: 11 },
    xaxis: {
      title: 'Annualized Volatility σ (%)',
      gridcolor: t.gridColor,
      zerolinecolor: t.zeroLineColor,
      ticksuffix: '%'
    },
    yaxis: {
      title: 'Expected Return E(R) (%)',
      gridcolor: t.gridColor,
      zerolinecolor: t.zeroLineColor,
      ticksuffix: '%'
    },
    legend: {
      orientation: 'h',
      yanchor: 'bottom',
      y: 1.01,
      xanchor: 'left',
      x: 0,
      font: { size: 10 }
    },
    hovermode: 'closest'
  };

  Plotly.react(
    'chart-frontier',
    traces,
    layout,
    { responsive: true, displayModeBar: false }
  );
}

function renderPlotlyWeights(data) {
  const t = getChartThemeTokens();
  const syms = data.symbols || [];
  const compWeights = data.complete_portfolio?.asset_weights || data.complete_portfolio?.asset_weights_in_complete || [];
  const wGmv = (data.gmv?.weights || []).map(w => w != null && !Number.isNaN(+w) ? +(w * 100).toFixed(2) : 0);
  const wTan = (data.tangency?.weights || []).map(w => w != null && !Number.isNaN(+w) ? +(w * 100).toFixed(2) : 0);
  const wComp = compWeights.map(w => w != null && !Number.isNaN(+w) ? +(w * 100).toFixed(2) : 0);

  const trGmv = {
    x: syms,
    y: wGmv,
    name: 'GMV (Min Risk)',
    type: 'bar',
    marker: { color: t.amberColor }
  };
  const trTan = {
    x: syms,
    y: wTan,
    name: 'Tangency (Max Sharpe)',
    type: 'bar',
    marker: { color: t.navyAccent }
  };
  const trComp = {
    x: syms,
    y: wComp,
    name: 'Complete Portfolio (C)',
    type: 'bar',
    marker: { color: t.emeraldColor }
  };

  const layout = {
    barmode: 'group',
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    margin: { l: 48, r: 16, t: 10, b: 32 },
    font: { family: 'Inter, sans-serif', color: t.fontColor, size: 11 },
    xaxis: { gridcolor: 'rgba(0,0,0,0)', font: { family: 'JetBrains Mono' } },
    yaxis: {
      title: 'Weight (%)',
      gridcolor: t.gridColor,
      zerolinecolor: t.zeroLineColor,
      ticksuffix: '%'
    },
    legend: {
      orientation: 'h',
      yanchor: 'bottom',
      y: 1.02,
      xanchor: 'left',
      x: 0,
      font: { size: 10 }
    }
  };

  Plotly.react('chart-weights', [trGmv, trTan, trComp], layout, { responsive: true, displayModeBar: false });
}

// --- Data Tables Rendering ---
function renderWeightsAndLot100Table(data) {
  const tbl = document.getElementById('tbl-weights-lot100');
  if (!tbl) return;

  const syms = data.symbols || [];
  const nav = data.nav_vnd || 1_000_000_000;
  const prices = data.latest_prices || {};
  const wGmv = data.gmv?.weights || [];
  const wTan = data.tangency?.weights || [];
  const wEq = data.equal_weight?.weights || [];
  const comp = data.complete_portfolio || {};
  const wComp = comp.asset_weights || comp.asset_weights_in_complete || [];
  const wCashTarget = comp.w_rf_weight ?? 0;
  const isMandatedCash = (comp.cash_mode === 'mandated');

  let totalAllocatedVnd = 0;

  let html = `<thead><tr>
    <th>Ticker / Asset</th>
    <th class="text-right">Price (VND)</th>
    <th class="text-right">w<sub>GMV</sub></th>
    <th class="text-right">w<sub>Tangency</sub></th>
    <th class="text-right">w<sub>1/N</sub></th>
    <th class="text-right">w<sub>Complete</sub></th>
    <th class="text-right">Target Value (VND)</th>
    <th class="text-right">Lot-100 Shares</th>
    <th class="text-right">Executed Value (VND)</th>
    <th class="text-right">Fee (0.15%)</th>
    <th class="text-right">Sell Tax (0.10%)</th>
  </tr></thead><tbody>`;

  for (let i = 0; i < syms.length; i++) {
    const sym = syms[i];
    const p = prices[sym] && prices[sym] > 0 ? prices[sym] : 50000;
    const wt = wTan[i] ?? 0;
    const wc = wComp[i] ?? wt;
    // If user explicitly set Mandated Cash %, size Lot 100 orders against Complete Portfolio weight wc
    const sizingWeight = isMandatedCash ? wc : wt;
    const targetVnd = sizingWeight * nav;
    const rawShares = targetVnd / p;
    const lot100Shares = Math.floor(rawShares / 100) * 100;
    const actualVnd = lot100Shares * p;
    const feeVnd = Math.abs(actualVnd) * 0.0015;
    const taxVnd = Math.abs(actualVnd) * 0.0010;
    totalAllocatedVnd += actualVnd;

    html += `<tr>
      <td class="font-semibold">${sym}</td>
      <td class="text-right">${fmtVND.format(p)}</td>
      <td class="text-right">${fmtPct(wGmv[i])}</td>
      <td class="text-right font-semibold" style="color: var(--accent);">${fmtPct(wt)}</td>
      <td class="text-right" style="color: var(--text-muted);">${fmtPct(wEq[i])}</td>
      <td class="text-right font-semibold">${fmtPct(wc)}</td>
      <td class="text-right">${fmtVND.format(targetVnd)}</td>
      <td class="text-right font-semibold">${fmtVND.format(lot100Shares)}</td>
      <td class="text-right">${fmtVND.format(actualVnd)}</td>
      <td class="text-right" style="color: var(--text-muted);">${fmtVND.format(feeVnd)}</td>
      <td class="text-right" style="color: var(--text-muted);">${fmtVND.format(taxVnd)}</td>
    </tr>`;
  }

  const cashResidual = nav - totalAllocatedVnd;
  const targetCashVnd = Math.max(0, wCashTarget * nav);

  // Explicit Cash / Risk-Free Asset Row
  html += `<tr style="background-color: var(--bg-subtle); color: var(--text-secondary);">
    <td class="font-semibold">CASH / R<sub>f</sub> (${fmtPct(data.rf, 1)})</td>
    <td class="text-right">1</td>
    <td class="text-right">0.00%</td>
    <td class="text-right">0.00%</td>
    <td class="text-right">0.00%</td>
    <td class="text-right font-semibold" style="color: var(--success);">${fmtPct(wCashTarget)}</td>
    <td class="text-right">${fmtVND.format(targetCashVnd)}</td>
    <td class="text-right">Cash Reserve</td>
    <td class="text-right font-semibold">${fmtVND.format(cashResidual)}</td>
    <td class="text-right">0</td>
    <td class="text-right">0</td>
  </tr>`;

  html += `<tr class="font-semibold" style="background-color: var(--bg-subtle);">
    <td>TOTAL PORTFOLIO NAV</td>
    <td class="text-right">--</td>
    <td class="text-right">${fmtPct(wGmv.reduce((a, b) => a + b, 0))}</td>
    <td class="text-right" style="color: var(--accent);">${fmtPct(wTan.reduce((a, b) => a + b, 0))}</td>
    <td class="text-right">${fmtPct(1.0)}</td>
    <td class="text-right">${fmtPct(wComp.reduce((a, b) => a + b, 0) + wCashTarget)}</td>
    <td class="text-right">${fmtVND.format(nav)}</td>
    <td class="text-right">Lot 100</td>
    <td class="text-right">${fmtVND.format(nav)}</td>
    <td class="text-right">${fmtVND.format(Math.abs(totalAllocatedVnd) * 0.0015)}</td>
    <td class="text-right">${fmtVND.format(Math.abs(totalAllocatedVnd) * 0.0010)}</td>
  </tr></tbody>`;

  tbl.innerHTML = html;

  const execLbl = document.getElementById('lbl-execution-summary');
  if (execLbl) {
    execLbl.innerHTML = `Equities: <strong>${fmtVND.format(totalAllocatedVnd)} VND</strong> &middot; Cash / R<sub>f</sub> Reserve: <strong>${fmtVND.format(cashResidual)} VND (${fmtPct(cashResidual / nav, 1)})</strong>`;
  }
}

// --- Tab 02: Institutional Benchmark Comparison ---
function renderBenchmarkTab(data) {
  const bm = data.benchmark_comparison;
  const tbl = document.getElementById('tbl-benchmark-scorecard');
  const badge = document.getElementById('lbl-benchmark-badge');
  if (!bm || !tbl) return;

  const bmRangeTag = bm.benchmark_range || (data.benchmark_range || '1Y');
  if (badge) {
    badge.textContent = `vs. ${bm.benchmark_symbol} (${bmRangeTag})`;
  }

  const spreadSign = (v, isPct = true) => {
    if (v === undefined || v === null || Number.isNaN(Number(v))) return '--';
    const num = Number(v);
    const prefix = num > 0 ? '+' : '';
    return isPct ? `${prefix}${(num * 100).toFixed(2)}%` : `${prefix}${num.toFixed(3)}`;
  };

  const alphaColor = bm.jensen_alpha >= 0 ? 'var(--success)' : 'var(--danger)';
  const irColor = bm.information_ratio >= 0 ? 'var(--success)' : 'var(--danger)';

  tbl.innerHTML = `
    <thead>
      <tr>
        <th>Metric</th>
        <th class="text-right">Tangency Portfolio</th>
        <th class="text-right">${bm.benchmark_symbol}</th>
        <th class="text-right">Active / Spread</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td class="font-medium">Expected Return E(R)</td>
        <td class="text-right font-semibold">${fmtPct(bm.portfolio_return)}</td>
        <td class="text-right">${fmtPct(bm.benchmark_return)}</td>
        <td class="text-right font-semibold" style="color: ${bm.active_return >= 0 ? 'var(--success)' : 'var(--danger)'};">${spreadSign(bm.active_return, true)}</td>
      </tr>
      <tr>
        <td class="font-medium">Annualized Volatility (&sigma;)</td>
        <td class="text-right">${fmtPct(bm.portfolio_volatility)}</td>
        <td class="text-right">${fmtPct(bm.benchmark_volatility)}</td>
        <td class="text-right">${spreadSign(bm.portfolio_volatility - bm.benchmark_volatility, true)}</td>
      </tr>
      <tr>
        <td class="font-medium">Sharpe Ratio</td>
        <td class="text-right font-semibold" style="color: var(--accent);">${fmtNum(bm.portfolio_sharpe, 3)}</td>
        <td class="text-right">${fmtNum(bm.benchmark_sharpe, 3)}</td>
        <td class="text-right font-semibold">${spreadSign(bm.sharpe_spread, false)}</td>
      </tr>
      <tr>
        <td class="font-medium">Portfolio Beta (&beta;)</td>
        <td class="text-right font-semibold">${fmtNum(bm.beta, 3)}</td>
        <td class="text-right">1.000</td>
        <td class="text-right">${bm.beta > 1.05 ? 'High Beta' : (bm.beta < 0.95 ? 'Defensive' : 'Market Neutral')}</td>
      </tr>
      <tr>
        <td class="font-medium">Jensen's Alpha (&alpha;)</td>
        <td class="text-right font-semibold" style="color: ${alphaColor};">${spreadSign(bm.jensen_alpha, true)}</td>
        <td class="text-right">0.00%</td>
        <td class="text-right" style="color: ${alphaColor};">${bm.jensen_alpha >= 0 ? 'Outperform' : 'Underperform'}</td>
      </tr>
      <tr>
        <td class="font-medium">Tracking Error (TE)</td>
        <td class="text-right">${fmtPct(bm.tracking_error)}</td>
        <td class="text-right">0.00%</td>
        <td class="text-right">Active Risk</td>
      </tr>
      <tr>
        <td class="font-medium">Information Ratio (IR)</td>
        <td class="text-right font-semibold" style="color: ${irColor};">${fmtNum(bm.information_ratio, 3)}</td>
        <td class="text-right">--</td>
        <td class="text-right">Alpha / TE</td>
      </tr>
      <tr>
        <td class="font-medium">Correlation (&rho;) / R&sup2;</td>
        <td class="text-right">${fmtNum(bm.correlation, 3)}</td>
        <td class="text-right">1.000</td>
        <td class="text-right">R&sup2; = ${fmtPct(bm.r_squared, 1)}</td>
      </tr>
    </tbody>
  `;

  // Render Cumulative Wealth Chart
  const chartEl = document.getElementById('chart-benchmark-cum');
  if (!chartEl) return;

  const t = getChartThemeTokens();
  const cum = bm.cumulative_series || {};
  const dates = cum.dates || [];
  const pSeries = cum.portfolio_base100 || [];
  const bSeries = cum.benchmark_base100 || [];

  const traces = [];
  if (dates.length > 0) {
    traces.push({
      x: dates,
      y: pSeries,
      mode: 'lines',
      type: 'scatter',
      name: 'Tangency Portfolio (Base 100)',
      line: { color: t.navyAccent, width: 2.5 }
    });
    traces.push({
      x: dates,
      y: bSeries,
      mode: 'lines',
      type: 'scatter',
      name: `${bm.benchmark_symbol} (Base 100)`,
      line: { color: t.roseColor, width: 2, dash: 'dot' }
    });
  }

  const layout = {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    margin: { l: 45, r: 16, t: 10, b: 32 },
    font: { family: 'Inter, sans-serif', color: t.fontColor, size: 11 },
    xaxis: { gridcolor: t.gridColor },
    yaxis: {
      title: 'Indexed Wealth (100)',
      gridcolor: t.gridColor,
      zerolinecolor: t.zeroLineColor
    },
    legend: {
      orientation: 'h',
      yanchor: 'bottom',
      y: 1.02,
      xanchor: 'left',
      x: 0,
      font: { size: 10 }
    },
    hovermode: 'x unified'
  };

  Plotly.react(chartEl, traces, layout, { responsive: true, displayModeBar: false });
}

// --- Tab 03: Stress Testing & Tail Risk (VaR / CVaR) ---
function renderStressTestingTab(data) {
  const st = data.stress_testing;
  const cardsBox = document.getElementById('stress-var-cards');
  const tbl = document.getElementById('tbl-stress-scenarios');
  const methodLbl = document.getElementById('lbl-stress-method');
  if (!st || !cardsBox || !tbl) return;

  const vm = st.var_metrics || {};
  if (methodLbl) {
    methodLbl.innerHTML = `Method: <strong>${st.method}</strong> &bull; &beta; = <strong>${fmtNum(st.portfolio_beta, 2)}</strong> &bull; Cash Buffer = <strong>${fmtPct(st.w_cash_weight, 1)}</strong>`;
  }

  cardsBox.innerHTML = `
    <div class="swiss-subtle p-3.5 rounded border" style="border-color: var(--border-color);">
      <div class="text-[11px] font-semibold uppercase tracking-wider" style="color: var(--text-muted);">1-Day VaR (95%)</div>
      <div class="mt-1.5 text-xl font-bold font-mono" style="color: var(--danger);">-${fmtPct(vm.var_95_1d_pct)}</div>
      <div class="text-[11px] font-mono mt-0.5" style="color: var(--text-secondary);">-${fmtVND.format(vm.var_95_1d_vnd || 0)} VND</div>
    </div>
    <div class="swiss-subtle p-3.5 rounded border" style="border-color: var(--border-color);">
      <div class="text-[11px] font-semibold uppercase tracking-wider" style="color: var(--text-muted);">1-Day CVaR / Expected Shortfall (95%)</div>
      <div class="mt-1.5 text-xl font-bold font-mono" style="color: var(--danger);">-${fmtPct(vm.cvar_95_1d_pct)}</div>
      <div class="text-[11px] font-mono mt-0.5" style="color: var(--text-secondary);">-${fmtVND.format(vm.cvar_95_1d_vnd || 0)} VND</div>
    </div>
    <div class="swiss-subtle p-3.5 rounded border" style="border-color: var(--border-color);">
      <div class="text-[11px] font-semibold uppercase tracking-wider" style="color: var(--text-muted);">1-Month (21d) VaR (95%)</div>
      <div class="mt-1.5 text-xl font-bold font-mono" style="color: var(--warning);">-${fmtPct(vm.var_95_21d_pct)}</div>
      <div class="text-[11px] font-mono mt-0.5" style="color: var(--text-secondary);">-${fmtVND.format(vm.var_95_21d_vnd || 0)} VND</div>
    </div>
    <div class="swiss-subtle p-3.5 rounded border" style="border-color: var(--border-color);">
      <div class="text-[11px] font-semibold uppercase tracking-wider" style="color: var(--text-muted);">Max Historical Drawdown (MDD)</div>
      <div class="mt-1.5 text-xl font-bold font-mono" style="color: var(--text-primary);">-${fmtPct(vm.max_drawdown_complete_pct)}</div>
      <div class="text-[11px] font-mono mt-0.5" style="color: var(--text-muted);">100% Equity MDD: -${fmtPct(vm.max_drawdown_risky_pct)}</div>
    </div>
  `;

  const scenarios = st.scenarios || [];
  let html = `<thead><tr>
    <th>Historical Crisis / Stress Scenario</th>
    <th>Period</th>
    <th class="text-right">VN-Index Shock</th>
    <th class="text-right">100% Equity Impact</th>
    <th class="text-right">Complete Portfolio Impact</th>
    <th class="text-right">Est. NAV Loss (VND)</th>
    <th class="text-right">Post-Shock NAV (VND)</th>
    <th class="text-right">Cash Buffer Saved (VND)</th>
  </tr></thead><tbody>`;

  scenarios.forEach(sc => {
    html += `<tr>
      <td>
        <div class="font-semibold" style="color: var(--text-primary);">${sc.name}</div>
        <div class="text-[11px] font-sans" style="color: var(--text-muted);">${sc.description}</div>
      </td>
      <td class="text-xs" style="color: var(--text-secondary);">${sc.period}</td>
      <td class="text-right font-semibold" style="color: var(--danger);">${fmtPct(sc.market_shock_pct)}</td>
      <td class="text-right" style="color: var(--text-secondary);">${fmtPct(sc.risky_only_impact_pct)}</td>
      <td class="text-right font-semibold" style="color: var(--danger);">${fmtPct(sc.complete_impact_pct)}</td>
      <td class="text-right font-semibold" style="color: var(--danger);">-${fmtVND.format(sc.estimated_loss_vnd)}</td>
      <td class="text-right font-semibold">${fmtVND.format(sc.post_shock_nav_vnd)}</td>
      <td class="text-right font-semibold" style="color: var(--success);">+${fmtVND.format(sc.cash_protection_vnd)}</td>
    </tr>`;
  });

  html += `</tbody>`;
  tbl.innerHTML = html;
}

function renderMatricesTables(data) {
  const syms = data.symbols;
  const assets = data.individual_assets;
  const cov = data.cov;
  const corr = data.corr;

  // 1. Asset Stats
  let htmlStats = `<thead><tr>
    <th>Ticker</th>
    <th class="text-right">E(R<sub>i</sub>)</th>
    <th class="text-right">&sigma;<sub>i</sub></th>
    <th class="text-right">&sigma;<sub>i</sub>&sup2;</th>
    <th class="text-right">Sharpe</th>
  </tr></thead><tbody>`;
  assets.forEach(a => {
    htmlStats += `<tr>
      <td class="font-semibold">${a.symbol}</td>
      <td class="text-right">${fmtPct(a.expected_return)}</td>
      <td class="text-right">${fmtPct(a.volatility)}</td>
      <td class="text-right">${fmtNum(a.variance, 4)}</td>
      <td class="text-right font-semibold">${fmtNum(a.sharpe_ratio, 3)}</td>
    </tr>`;
  });
  htmlStats += `</tbody>`;
  document.getElementById('tbl-asset-stats').innerHTML = htmlStats;

  // 2. Correlation Matrix
  let htmlCorr = `<thead><tr><th>&rho;<sub>i,j</sub></th>`;
  syms.forEach(s => { htmlCorr += `<th class="text-right">${s}</th>`; });
  htmlCorr += `</tr></thead><tbody>`;
  for (let i = 0; i < syms.length; i++) {
    htmlCorr += `<tr><td class="font-semibold">${syms[i]}</td>`;
    for (let j = 0; j < syms.length; j++) {
      const val = corr[i][j];
      const cls = i === j ? 'font-semibold' : '';
      htmlCorr += `<td class="text-right ${cls}">${fmtNum(val, 3)}</td>`;
    }
    htmlCorr += `</tr>`;
  }
  htmlCorr += `</tbody>`;
  document.getElementById('tbl-corr-matrix').innerHTML = htmlCorr;

  // 3. Covariance Matrix
  let htmlCov = `<thead><tr><th>&Sigma;<sub>i,j</sub></th>`;
  syms.forEach(s => { htmlCov += `<th class="text-right">${s}</th>`; });
  htmlCov += `</tr></thead><tbody>`;
  for (let i = 0; i < syms.length; i++) {
    htmlCov += `<tr><td class="font-semibold">${syms[i]}</td>`;
    for (let j = 0; j < syms.length; j++) {
      htmlCov += `<td class="text-right">${fmtNum(cov[i][j], 5)}</td>`;
    }
    htmlCov += `</tr>`;
  }
  htmlCov += `</tbody>`;
  document.getElementById('tbl-cov-matrix').innerHTML = htmlCov;
}

function renderAlgebraStepByStep(data) {
  const syms = data.symbols || [];
  const invCov = data.inv_cov || [];
  const sc = data.merton_scalars || { A: 0, B: 0, C: 1, D: 0 };

  let htmlInv = `<thead><tr><th>&Sigma;<sup>-1</sup></th>`;
  syms.forEach(s => { htmlInv += `<th class="text-right">${s}</th>`; });
  htmlInv += `</tr></thead><tbody>`;
  for (let i = 0; i < syms.length; i++) {
    htmlInv += `<tr><td class="font-semibold">${syms[i]}</td>`;
    for (let j = 0; j < syms.length; j++) {
      htmlInv += `<td class="text-right">${fmtNum(invCov[i][j], 3)}</td>`;
    }
    htmlInv += `</tr>`;
  }
  htmlInv += `</tbody>`;
  document.getElementById('tbl-invcov-matrix').innerHTML = htmlInv;

  const scalarsBox = document.getElementById('merton-scalars-box');
  scalarsBox.innerHTML = `
    <div class="p-2.5 swiss-subtle">
      <div class="text-[10px]" style="color: var(--text-muted);">A = 1' &Sigma;<sup>-1</sup> &mu;</div>
      <div class="text-sm font-bold mt-0.5" style="color: var(--text-primary);">${fmtNum(sc.A, 4)}</div>
    </div>
    <div class="p-2.5 swiss-subtle">
      <div class="text-[10px]" style="color: var(--text-muted);">B = &mu;' &Sigma;<sup>-1</sup> &mu;</div>
      <div class="text-sm font-bold mt-0.5" style="color: var(--text-primary);">${fmtNum(sc.B, 4)}</div>
    </div>
    <div class="p-2.5 swiss-subtle">
      <div class="text-[10px]" style="color: var(--text-muted);">C = 1' &Sigma;<sup>-1</sup> 1</div>
      <div class="text-sm font-bold mt-0.5" style="color: var(--text-primary);">${fmtNum(sc.C, 4)}</div>
    </div>
    <div class="p-2.5 swiss-subtle">
      <div class="text-[10px]" style="color: var(--text-muted);">D = B&middot;C - A&sup2;</div>
      <div class="text-sm font-bold mt-0.5" style="color: var(--accent);">${fmtNum(sc.D, 4)}</div>
    </div>
  `;

  const noteBox = document.getElementById('merton-formulas-note');
  const gmvErClosed = fmtNum((sc.A / sc.C) * 100, 2) + '%';
  const gmvStdClosed = fmtNum(Math.sqrt(Math.max(0, 1.0 / sc.C)) * 100, 2) + '%';
  noteBox.innerHTML = `
    <div>&bull; <strong>w<sub>GMV</sub></strong> = (&Sigma;<sup>-1</sup> 1) / C &rArr; E(R<sub>GMV</sub>) = A/C = <strong>${gmvErClosed}</strong>, &sigma;<sub>GMV</sub> = 1/&radic;C = <strong>${gmvStdClosed}</strong></div>
    <div>&bull; <strong>w<sub>Tangency</sub></strong> = [&Sigma;<sup>-1</sup> (&mu; - R<sub>f</sub>&middot;1)] / [A - C&middot;R<sub>f</sub>]</div>
    <div>&bull; <strong>y* (Optimal Risky Weight)</strong> = [E(R<sub>T</sub>) - R<sub>f</sub>] / [A &middot; &sigma;<sub>T</sub>&sup2;]</div>
  `;
}

function _getTodayDateTag() {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  return `${y}${m}${d}`;
}

async function exportCurrentPriceData() {
  const payload = buildRequestPayload();
  const btn = document.getElementById('btn-export-prices');
  const oldHtml = btn ? btn.innerHTML : '';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span>Exporting Prices...</span>';
  }

  try {
    const res = await fetch('/api/export-prices', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || 'Error exporting price dataset');
    }

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const nAssets = payload.symbols ? payload.symbols.length : 0;
    const winTag = (payload.hayinsights_range || '1Y').toUpperCase();
    a.download = `Portfolio_Prices_${nAssets}Assets_${winTag}_${_getTodayDateTag()}.xlsx`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  } catch (err) {
    alert('Price Data Export Error: ' + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = oldHtml;
    }
  }
}

async function exportCurrentMatrixData() {
  const payload = buildRequestPayload();
  const btn = document.getElementById('btn-export-matrix');
  const oldHtml = btn ? btn.innerHTML : '';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span>Exporting Matrix...</span>';
  }

  try {
    const res = await fetch('/api/export-matrix', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || 'Error exporting parameter matrix');
    }

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const nAssets = payload.symbols ? payload.symbols.length : 0;
    a.download = `Portfolio_Matrix_${nAssets}Assets_${_getTodayDateTag()}.xlsx`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  } catch (err) {
    alert('Matrix Data Export Error: ' + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = oldHtml;
    }
  }
}

async function exportInstitutionalExcel() {
  const payload = buildRequestPayload();
  const btn = document.getElementById('btn-export-excel');
  const oldHtml = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span>Exporting...</span>';

  try {
    const res = await fetch('/api/export-excel', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error('Error generating Excel report');

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const modeTag = payload.allow_short ? 'ShortAllowed' : 'LongOnly';
    a.download = `Portfolio_MVO_Report_${modeTag}_${_getTodayDateTag()}.xlsx`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  } catch (err) {
    alert('Excel Export Error: ' + err.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = oldHtml;
  }
}
