// Markowitz Portfolio Optimization — Consistent State, Provenance & Bilingual UI Engine (v2.5.0)
'use strict';

var appState = {
  uiLang: typeof window.getSavedLang === 'function' ? window.getSavedLang() : 'vi',
  inputMode: 'live_market', // 'live_market' | 'uploaded_prices' | 'manual_matrix'
  cashMode: 'utility_no_leverage', // 'utility_no_leverage' | 'fixed_cash'
  riskReportBasis: 'target_complete', // 'target_complete' | 'executed_post_fee'
  benchmarkSymbol: 'VNINDEX',
  benchmarkHorizon: '1y',
  isDirty: false,
  isComputing: false,
  requestSeq: 0,
  benchmarkSeq: 0,
  activeAbortController: null,
  committedSnapshot: null,
  liveMarket: {
    symbols: ['FPT', 'MWG', 'VCB', 'HPG', 'VNM'],
    latestPrices: {}
  },
  uploadedPrices: {
    datasetId: null,
    filename: null,
    uploadedAt: null,
    fromDate: null,
    toDate: null,
    sessionsCount: 0,
    droppedDaysCount: 0,
    symbols: [],
    latestPrices: {},
    latestPriceDates: {}
  },
  manualMatrix: {
    symbols: ['FPT', 'MWG', 'VCB', 'HPG'],
    expected_returns: [0.24, 0.165, 0.135, 0.175],
    std_devs: [0.22, 0.285, 0.18, 0.275],
    corr_matrix: [
      [1.00, 0.42, 0.35, 0.38],
      [0.42, 1.00, 0.40, 0.46],
      [0.35, 0.40, 1.00, 0.32],
      [0.38, 0.46, 0.32, 1.00]
    ],
    latest_prices: { FPT: 114500, MWG: 65200, VCB: 91500, HPG: 27100 },
    datasetId: null,
    filename: null
  }
};
window.appState = appState;

let tickerDirectory = [];
let tickerMetaMap = {};
let quizQuestions = [];
let dropdownHighlightIdx = -1;
let currentDropdownResults = [];
let lastAnalysisData = null;
let lastFocusedBeforeModal = null;
let activeFullscreenChartKey = null;

function getLocaleCode() {
  return appState.uiLang === 'en' ? 'en-US' : 'vi-VN';
}

function fmtVnd(val) {
  if (val === undefined || val === null || Number.isNaN(Number(val))) return '--';
  return new Intl.NumberFormat(getLocaleCode(), { maximumFractionDigits: 0 }).format(Math.round(Number(val)));
}

function fmtNum(v, digits) {
  const d = digits === undefined ? 2 : digits;
  if (v === undefined || v !== undefined && v === null) return '--';
  if (v === undefined || v === null || Number.isNaN(Number(v))) return '--';
  return Number(v).toFixed(d);
}

function fmtPct(v, digits) {
  const d = digits === undefined ? 2 : digits;
  if (v === undefined || v === null || Number.isNaN(Number(v))) return '--%';
  return (Number(v) * 100).toFixed(d) + '%';
}

function tr(key, params) {
  if (typeof window.t === 'function') return window.t(key, params, appState.uiLang);
  return key;
}

document.addEventListener('DOMContentLoaded', async function () {
  initTheme();
  applyLanguageUI(appState.uiLang, false);
  bindUIEvents();
  await loadPresets();
  renderManualTable();
  renderUploadPriceStatus();
  updateAssetCountBadge();
  updateExportLockState();
  await runMVOOptimization();
});

// --- Theme Management ---
function isDarkMode() {
  return document.documentElement.classList.contains('dark');
}

function initTheme() {
  let saved = null;
  try {
    saved = localStorage.getItem('mvo_theme');
  } catch (_) {}
  if (saved === 'dark') {
    document.documentElement.classList.add('dark');
  } else {
    document.documentElement.classList.remove('dark');
  }
  updateThemeIcons();
}

function toggleTheme() {
  const htmlEl = document.documentElement;
  if (htmlEl.classList.contains('dark')) {
    htmlEl.classList.remove('dark');
    try { localStorage.setItem('mvo_theme', 'light'); } catch (_) {}
  } else {
    htmlEl.classList.add('dark');
    try { localStorage.setItem('mvo_theme', 'dark'); } catch (_) {}
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

// --- Language Switcher (VI / EN Live Switch Without Re-Optimizing) ---
function setLanguage(lang) {
  const target = lang === 'en' ? 'en' : 'vi';
  applyLanguageUI(target, true);
}

function applyLanguageUI(lang, rerenderData) {
  appState.uiLang = lang === 'en' ? 'en' : 'vi';
  if (typeof window.applyStaticI18n === 'function') {
    window.applyStaticI18n(appState.uiLang);
  }
  const titleText = tr('app.title');
  document.title = titleText;

  const btnVi = document.getElementById('btn-lang-vi');
  const btnEn = document.getElementById('btn-lang-en');
  if (btnVi && btnEn) {
    btnVi.classList.toggle('active', appState.uiLang === 'vi');
    btnEn.classList.toggle('active', appState.uiLang === 'en');
    btnVi.setAttribute('aria-pressed', appState.uiLang === 'vi' ? 'true' : 'false');
    btnEn.setAttribute('aria-pressed', appState.uiLang === 'en' ? 'true' : 'false');
  }

  const allowShortEl = document.getElementById('chk-allow-short');
  const shortDesc = document.getElementById('lbl-short-desc');
  if (shortDesc && allowShortEl) {
    const descTxt = allowShortEl.checked ? tr('short.desc_short') : tr('short.desc_long');
    shortDesc.textContent = descTxt;
  }

  if (rerenderData) {
    updateSourceTagUI();
    renderSelectedTickerPills();
    renderUploadPriceStatus();
    renderManualTable();
    renderQuizQuestionsPreservingSelection();
    if (lastAnalysisData) {
      renderAllCommittedViews(lastAnalysisData);
      if (activeFullscreenChartKey) {
        openChartFullscreen(activeFullscreenChartKey);
      }
    }
  }
}

// --- Dirty / State Locking & Export Guards ---
function markDirty() {
  if (!appState.committedSnapshot && !lastAnalysisData) return;
  appState.isDirty = true;
  const staleBanner = document.getElementById('banner-stale');
  if (staleBanner) staleBanner.classList.remove('hidden');
  updateExportLockState();
}

function clearDirty() {
  appState.isDirty = false;
  const staleBanner = document.getElementById('banner-stale');
  if (staleBanner) staleBanner.classList.add('hidden');
  updateExportLockState();
}

function updateExportLockState() {
  const locked = appState.isDirty || appState.isComputing || !appState.committedSnapshot;
  const snapData = appState.committedSnapshot ? appState.committedSnapshot.responseData : null;
  const isManualOnly = Boolean(snapData && snapData.input_mode_canonical === 'manual_matrix');

  const allExportIds = ['btn-export-excel', 'btn-export-matrix', 'btn-export-matrix-mobile'];
  allExportIds.forEach(function (id) {
    const el = document.getElementById(id);
    if (el) el.disabled = locked;
  });

  const priceExportIds = ['btn-export-prices', 'btn-export-prices-mobile'];
  priceExportIds.forEach(function (id) {
    const el = document.getElementById(id);
    if (el) el.disabled = locked || isManualOnly;
  });
}

// --- Lower Workbench Tabs ---
function switchLowerTab(tabName) {
  const tabs = ['execution', 'benchmark', 'stress', 'moments', 'algebra'];
  tabs.forEach(function (tb) {
    const btn = document.getElementById(`tab-btn-${tb}`);
    const panel = document.getElementById(`tab-panel-${tb}`);
    if (btn) {
      btn.classList.toggle('active', tb === tabName);
      btn.setAttribute('aria-selected', tb === tabName ? 'true' : 'false');
    }
    if (panel) panel.classList.toggle('hidden', tb !== tabName);
  });
  if (tabName === 'benchmark' && lastAnalysisData) {
    setTimeout(function () {
      const el = document.getElementById('chart-benchmark-cum');
      if (el && window.Plotly) Plotly.Plots.resize(el);
    }, 30);
  }
}

// --- Weight Bounds & Cash Mode ---
function toggleCap20Preset(checked) {
  const rngMin = document.getElementById('rng-w-min');
  const rngMax = document.getElementById('rng-w-max');
  if (checked) {
    if (rngMin) rngMin.value = 0;
    if (rngMax) rngMax.value = 20;
  } else {
    if (rngMax) rngMax.value = 100;
  }
  onWeightBoundSliderChange(false);
  markDirty();
}

function toggleTT98Preset(checked) {
  toggleCap20Preset(checked);
}

function onWeightBoundSliderChange() {
  const rngMin = document.getElementById('rng-w-min');
  const rngMax = document.getElementById('rng-w-max');
  const lblMin = document.getElementById('lbl-w-min');
  const lblMax = document.getElementById('lbl-w-max');
  const chkCap20 = document.getElementById('chk-cap-20');

  const vMin = parseInt((rngMin && rngMin.value) ? rngMin.value : '0', 10);
  const vMax = parseInt((rngMax && rngMax.value) ? rngMax.value : '100', 10);

  if (lblMin) lblMin.textContent = `${vMin}%`;
  if (lblMax) lblMax.textContent = `${vMax}%`;
  if (chkCap20) chkCap20.checked = (vMin === 0 && vMax === 20);
  markDirty();
}

function setCashMode(mode) {
  const normalized = (mode === 'fixed_cash' || mode === 'mandated') ? 'fixed_cash' : 'utility_no_leverage';
  appState.cashMode = normalized;
  const btnUtil = document.getElementById('btn-cash-mode-utility');
  const btnFixed = document.getElementById('btn-cash-mode-fixed');
  const hintUtil = document.getElementById('panel-utility-cash-hint');
  const panelFixed = document.getElementById('panel-fixed-cash');

  if (btnUtil) btnUtil.classList.toggle('active', normalized === 'utility_no_leverage');
  if (btnFixed) btnFixed.classList.toggle('active', normalized === 'fixed_cash');
  if (hintUtil) hintUtil.classList.toggle('hidden', normalized !== 'utility_no_leverage');
  if (panelFixed) panelFixed.classList.toggle('hidden', normalized !== 'fixed_cash');
  markDirty();
}

function syncMandatedCashInput(val) {
  let num = parseFloat(val);
  if (Number.isNaN(num)) num = 0;
  const v = Math.max(0, Math.min(100, num));
  const inp = document.getElementById('inp-mandated-cash');
  const rng = document.getElementById('rng-mandated-cash');
  if (inp) inp.value = v;
  if (rng) rng.value = v;
  markDirty();
}

function syncMandatedCashSlider(val) {
  let num = parseFloat(val);
  if (Number.isNaN(num)) num = 0;
  const v = Math.max(0, Math.min(100, num));
  const inp = document.getElementById('inp-mandated-cash');
  if (inp) inp.value = v;
  markDirty();
}

function setRiskReportBasis(basis) {
  appState.riskReportBasis = basis === 'executed_post_fee' ? 'executed_post_fee' : 'target_complete';
  const btnT = document.getElementById('btn-basis-target');
  const btnE = document.getElementById('btn-basis-exec');
  if (btnT) btnT.classList.toggle('active', appState.riskReportBasis === 'target_complete');
  if (btnE) btnE.classList.toggle('active', appState.riskReportBasis === 'executed_post_fee');
  if (lastAnalysisData) {
    renderStressTestingTab(lastAnalysisData);
  }
}

// --- Event Bindings ---
function bindUIEvents() {
  const rngRisk = document.getElementById('rng-risk-a');
  if (rngRisk) {
    rngRisk.addEventListener('input', function (e) {
      const val = parseFloat(e.target.value).toFixed(1);
      const lbl = document.getElementById('lbl-risk-a');
      if (lbl) lbl.textContent = val;
      markDirty();
    });
    rngRisk.addEventListener('change', function () {
      markDirty();
    });
  }

  ['inp-rf', 'inp-nav', 'inp-buy-fee', 'sel-hayinsights-range', 'chk-hayinsights-adj'].forEach(function (id) {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('input', markDirty);
      el.addEventListener('change', markDirty);
    }
  });

  const chkShort = document.getElementById('chk-allow-short');
  if (chkShort) {
    chkShort.addEventListener('change', function (e) {
      const allow = e.target.checked;
      const wbPanel = document.getElementById('panel-weight-bounds');
      if (wbPanel) {
        wbPanel.style.opacity = allow ? '0.45' : '1';
        wbPanel.style.pointerEvents = allow ? 'none' : 'auto';
      }
      const descEl = document.getElementById('lbl-short-desc');
      if (descEl) {
        const descText = allow ? tr('short.desc_short') : tr('short.desc_long');
        descEl.textContent = descText;
      }
      markDirty();
    });
  }

  const inpSearch = document.getElementById('inp-ticker-search');
  const btnToggleDd = document.getElementById('btn-toggle-ticker-dropdown');
  const ddMenu = document.getElementById('ticker-autocomplete-dropdown');

  if (inpSearch) {
    inpSearch.addEventListener('focus', function () { openTickerDropdown(inpSearch.value); });
    inpSearch.addEventListener('input', function (e) { openTickerDropdown(e.target.value); });
    inpSearch.addEventListener('keydown', handleTickerSearchKeydown);
  }

  if (btnToggleDd) {
    btnToggleDd.addEventListener('click', function (e) {
      e.stopPropagation();
      if (ddMenu && !ddMenu.classList.contains('hidden')) {
        closeTickerDropdown();
      } else {
        if (inpSearch) inpSearch.focus();
        openTickerDropdown(inpSearch ? inpSearch.value : '');
      }
    });
  }

  document.addEventListener('click', function (e) {
    const wrapper = document.getElementById('ticker-search-wrapper');
    if (wrapper && !wrapper.contains(e.target)) {
      closeTickerDropdown();
    }
  });

  const inpPriceUpload = document.getElementById('inp-price-upload');
  if (inpPriceUpload) {
    inpPriceUpload.addEventListener('change', function (e) {
      handleFileUpload(e, 'uploaded_prices');
    });
  }

  const inpMatrixUpload = document.getElementById('inp-excel-upload');
  if (inpMatrixUpload) {
    inpMatrixUpload.addEventListener('change', function (e) {
      handleFileUpload(e, 'manual_matrix');
    });
  }

  const btnRun = document.getElementById('btn-run-mvo');
  if (btnRun) btnRun.addEventListener('click', runMVOOptimization);

  const btnExcel = document.getElementById('btn-export-excel');
  if (btnExcel) btnExcel.addEventListener('click', exportInstitutionalExcel);

  const btnPrices = document.getElementById('btn-export-prices');
  if (btnPrices) {
    btnPrices.addEventListener('click', function (e) {
      e.preventDefault();
      exportCurrentPriceData();
    });
  }

  const btnMatrix = document.getElementById('btn-export-matrix');
  if (btnMatrix) {
    btnMatrix.addEventListener('click', function (e) {
      e.preventDefault();
      exportCurrentMatrixData();
    });
  }

  // Modal Escape & Focus Trap handling
  document.addEventListener('keydown', function (e) {
    const fsModal = document.getElementById('modal-chart-fullscreen');
    const qModal = document.getElementById('quiz-box-panel');

    if (e.key === 'Escape') {
      if (fsModal && !fsModal.classList.contains('hidden')) {
        closeChartFullscreen();
        return;
      }
      if (qModal && !qModal.classList.contains('hidden')) {
        toggleQuizModal();
        return;
      }
    }

    if (e.key === 'Tab') {
      if (fsModal && !fsModal.classList.contains('hidden')) {
        trapModalFocus(fsModal, e);
      } else if (qModal && !qModal.classList.contains('hidden')) {
        trapModalFocus(qModal, e);
      }
    }
  });
}

function trapModalFocus(modalEl, event) {
  const focusables = modalEl.querySelectorAll('button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])');
  if (!focusables || focusables.length === 0) return;
  const first = focusables[0];
  const last = focusables[focusables.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

async function loadPresets() {
  try {
    const res = await fetch('/api/presets');
    const data = await res.json();
    tickerDirectory = data.ticker_directory || [];
    tickerMetaMap = {};
    tickerDirectory.forEach(function (item) {
      tickerMetaMap[item.symbol] = item;
    });
    quizQuestions = data.quiz_questions || [];
    syncBasketUI(false);
    renderQuizQuestions([]);
  } catch (err) {
    console.error('Failed to load presets:', err);
  }
}

// --- Live Market Ticker Basket ---
function getHayInsightsSymbolList() {
  return [...appState.liveMarket.symbols];
}

function syncBasketUI(shouldMarkDirty) {
  const hiddenInp = document.getElementById('inp-hayinsights-symbols');
  if (hiddenInp) hiddenInp.value = appState.liveMarket.symbols.join(', ');
  const cntLbl = document.getElementById('lbl-basket-count');
  if (cntLbl) cntLbl.textContent = appState.liveMarket.symbols.length;
  renderSelectedTickerPills();
  updateAssetCountBadge();
  if (shouldMarkDirty !== false) markDirty();
}

function applyQuickBasket(syms) {
  appState.liveMarket.symbols = [...new Set(syms.map(function (s) { return s.trim().toUpperCase(); }).filter(Boolean))];
  syncBasketUI(true);
  runMVOOptimization();
}

function addTickerToBasket(sym) {
  const s = (sym || '').trim().toUpperCase();
  if (!s) return;
  if (!appState.liveMarket.symbols.includes(s)) {
    appState.liveMarket.symbols.push(s);
    syncBasketUI(true);
    fetchLiveQuoteForPill(s);
  }
}

function removeTickerFromBasket(sym) {
  if (appState.liveMarket.symbols.length <= 2) {
    alert(tr('live.min_assets_alert'));
    return;
  }
  appState.liveMarket.symbols = appState.liveMarket.symbols.filter(function (s) { return s !== sym; });
  syncBasketUI(true);
}

async function fetchLiveQuoteForPill(sym) {
  try {
    const res = await fetch(`/api/hayinsights/quote/${encodeURIComponent(sym)}`);
    if (!res.ok) return;
    const info = await res.json();
    if (info && info.latest_price) {
      appState.liveMarket.latestPrices[sym] = info.latest_price;
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

  appState.liveMarket.symbols.forEach(function (sym) {
    const meta = tickerMetaMap[sym] || {};
    const price = appState.liveMarket.latestPrices[sym];
    const priceHtml = price
      ? `<span class="text-[10px] font-mono" style="color: var(--text-muted);">${fmtVnd(price)}</span>`
      : '';

    const pill = document.createElement('div');
    pill.className = 'inline-flex items-center gap-1.5 px-2 py-0.5 rounded swiss-card text-xs';
    pill.title = meta.name ? `${sym} — ${meta.name} (${meta.exchange || 'HOSE'})` : sym;
    const htmlStr = `
      <span class="font-semibold font-mono text-[11px]" style="color: var(--text-primary);">${sym}</span>
      ${priceHtml}
      <button type="button" class="text-[11px] leading-none hover:opacity-75 px-1" style="color: var(--text-muted);" aria-label="Remove ${sym}">&times;</button>
    `;
    pill.innerHTML = htmlStr;
    pill.querySelector('button').onclick = function (e) {
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

  for (let i = 0; i < tickerDirectory.length; i++) {
    const item = tickerDirectory[i];
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
      name: tr('live.direct_api'),
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
    dd.innerHTML = `<div class="p-3 text-xs text-center" style="color: var(--text-muted);">${tr('live.no_match')}</div>`;
    return;
  }

  let html = '';
  currentDropdownResults.forEach(function (item, idx) {
    const isSelected = appState.liveMarket.symbols.includes(item.symbol);
    const isHighlighted = idx === dropdownHighlightIdx;
    const bgStyle = isHighlighted ? 'background-color: var(--bg-subtle);' : '';
    const statusBadge = isSelected
      ? `<span class="px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold" style="background-color: var(--accent-soft); color: var(--accent);">${tr('live.added')}</span>`
      : `<span class="px-1.5 py-0.5 rounded text-[10px] font-mono swiss-subtle" style="color: var(--text-muted);">${tr('live.add')}</span>`;

    html += `
      <div data-idx="${idx}" data-sym="${item.symbol}" style="${bgStyle} border-color: var(--border-color);"
        class="ticker-dd-item flex items-center justify-between gap-2 px-3 py-2 cursor-pointer transition">
        <div class="flex items-center gap-2 min-w-0 flex-1">
          ${statusBadge}
          <span class="font-mono font-semibold text-xs w-11 shrink-0" style="color: var(--text-primary);">${highlightMatch(item.symbol, query)}</span>
          <span class="text-xs truncate" style="color: var(--text-secondary);">${item.name}</span>
        </div>
        <div class="flex items-center gap-1.5 shrink-0">
          <span class="text-[10px] font-mono px-1.5 py-0.5 rounded swiss-subtle" style="color: var(--text-secondary);">${item.exchange || 'VN'}</span>
        </div>
      </div>
    `;
  });

  dd.innerHTML = html;
  dd.querySelectorAll('.ticker-dd-item').forEach(function (el) {
    el.addEventListener('click', function (e) {
      e.stopPropagation();
      const sym = el.getAttribute('data-sym');
      handleDropdownSelectTicker(sym);
    });
  });
}

function handleDropdownSelectTicker(sym) {
  if (!sym) return;
  if (appState.liveMarket.symbols.includes(sym)) {
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

// --- 3 Isolated Input Modes ---
function normalizeInputMode(mode) {
  if (mode === 'uploaded_prices') return 'uploaded_prices';
  if (mode === 'manual_matrix' || mode === 'manual') return 'manual_matrix';
  return 'live_market';
}

function setInputMode(mode) {
  const canon = normalizeInputMode(mode);
  appState.inputMode = canon;

  const modes = ['live_market', 'uploaded_prices', 'manual_matrix'];
  modes.forEach(function (m) {
    const btn = document.getElementById(`tab-mode-${m}`);
    const pnl = document.getElementById(`panel-${m}-input`);
    if (btn) {
      btn.classList.toggle('active', m === canon);
      btn.setAttribute('aria-selected', m === canon ? 'true' : 'false');
    }
    if (pnl) pnl.classList.toggle('hidden', m !== canon);
  });

  updateSourceTagUI();
  updateAssetCountBadge();
  markDirty();
}

function updateSourceTagUI() {
  const lbl = document.getElementById('lbl-data-source-tag');
  if (!lbl) return;
  if (appState.inputMode === 'live_market') {
    lbl.textContent = tr('source.live_tag');
  } else if (appState.inputMode === 'uploaded_prices') {
    lbl.textContent = appState.uploadedPrices.filename || tr('source.uploaded_tag');
  } else {
    lbl.textContent = appState.manualMatrix.filename || tr('source.manual_tag');
  }
}

function updateAssetCountBadge() {
  let count = 0;
  if (appState.inputMode === 'live_market') {
    count = appState.liveMarket.symbols.length;
  } else if (appState.inputMode === 'uploaded_prices') {
    count = appState.uploadedPrices.symbols.length;
  } else {
    count = appState.manualMatrix.symbols.length;
  }
  const el = document.getElementById('lbl-asset-count');
  if (el) el.textContent = count;
}

function renderUploadPriceStatus() {
  const el = document.getElementById('lbl-upload-price-status');
  if (!el) return;
  const up = appState.uploadedPrices;
  if (!up.datasetId) {
    el.textContent = tr('upload.status_empty');
  } else {
    el.textContent = tr('upload.status_loaded', {
      name: up.filename,
      n: up.symbols.length,
      sessions: up.sessionsCount,
      from: up.fromDate || '--',
      to: up.toDate || '--',
      dropped: up.droppedDaysCount || 0
    });
  }
}

// --- Manual Matrix Editor (No hard-coded 50k price fallback) ---
function renderManualTable() {
  const tbl = document.getElementById('manual-param-table');
  if (!tbl) return;
  const mm = appState.manualMatrix;
  const n = mm.symbols.length;

  let html = `<thead><tr>
    <th class="sticky-col">Ticker</th>
    <th class="text-right">${tr('manual.price_col')}</th>
    <th class="text-right">${tr('manual.er_col')}</th>
    <th class="text-right">${tr('manual.std_col')}</th>`;
  for (let i = 0; i < n; i++) {
    html += `<th class="text-center">&rho;(${mm.symbols[i]})</th>`;
  }
  html += `</tr></thead><tbody>`;

  for (let i = 0; i < n; i++) {
    const sym = mm.symbols[i];
    const pVal = mm.latest_prices[sym];
    const pStr = (pVal !== undefined && pVal !== null && Number(pVal) > 0) ? String(pVal) : '';
    html += `<tr>
      <td class="sticky-col"><input type="text" aria-label="Ticker ${i + 1}" value="${sym}" onchange="updateManualSymbol(${i}, this.value)" class="swiss-input w-14 px-1.5 py-0.5 font-semibold uppercase text-xs" /></td>
      <td><input type="number" step="100" min="0" placeholder="--" aria-label="${sym} Price VND" value="${pStr}" onchange="updateManualPrice(${i}, this.value)" class="swiss-input w-20 px-1.5 py-0.5 text-right text-xs" /></td>
      <td><input type="number" step="0.5" aria-label="${sym} Expected Return %" value="${(mm.expected_returns[i] * 100).toFixed(2)}" onchange="updateManualER(${i}, this.value)" class="swiss-input w-16 px-1.5 py-0.5 text-right text-xs" /></td>
      <td><input type="number" step="0.5" aria-label="${sym} Volatility %" value="${(mm.std_devs[i] * 100).toFixed(2)}" onchange="updateManualStd(${i}, this.value)" class="swiss-input w-16 px-1.5 py-0.5 text-right text-xs" /></td>`;
    for (let j = 0; j < n; j++) {
      const ro = i === j ? 'readonly' : '';
      html += `<td><input type="number" step="0.05" min="-0.99" max="1.0" ${ro} aria-label="Correlation ${sym}-${mm.symbols[j]}" value="${mm.corr_matrix[i][j].toFixed(2)}" onchange="updateManualCorr(${i}, ${j}, this.value)" class="swiss-input w-14 px-1 py-0.5 text-center text-xs" /></td>`;
    }
    html += `</tr>`;
  }
  html += `</tbody>`;
  tbl.innerHTML = html;
  updateAssetCountBadge();
}

function updateManualSymbol(idx, val) {
  const mm = appState.manualMatrix;
  const oldSym = mm.symbols[idx];
  const newSym = val.trim().toUpperCase() || `A${idx + 1}`;
  mm.symbols[idx] = newSym;
  if (oldSym !== newSym) {
    mm.latest_prices[newSym] = mm.latest_prices[oldSym];
    delete mm.latest_prices[oldSym];
  }
  renderManualTable();
  markDirty();
}

function updateManualPrice(idx, val) {
  const sym = appState.manualMatrix.symbols[idx];
  const raw = String(val || '').trim();
  if (!raw) {
    appState.manualMatrix.latest_prices[sym] = null;
  } else {
    const parsed = parseFloat(raw);
    appState.manualMatrix.latest_prices[sym] = (!Number.isNaN(parsed) && parsed > 0) ? parsed : null;
  }
  markDirty();
}

function updateManualER(idx, val) {
  appState.manualMatrix.expected_returns[idx] = (parseFloat(val) || 0) / 100.0;
  markDirty();
}

function updateManualStd(idx, val) {
  appState.manualMatrix.std_devs[idx] = Math.max(0.0001, (parseFloat(val) || 10) / 100.0);
  markDirty();
}

function updateManualCorr(i, j, val) {
  if (i === j) return;
  const v = Math.max(-0.99, Math.min(0.99, parseFloat(val) || 0));
  appState.manualMatrix.corr_matrix[i][j] = v;
  appState.manualMatrix.corr_matrix[j][i] = v;
  renderManualTable();
  markDirty();
}

function addManualAssetRow() {
  const mm = appState.manualMatrix;
  const n = mm.symbols.length;
  if (n >= 12) return;
  const newSym = `CP${n + 1}`;
  mm.symbols.push(newSym);
  mm.expected_returns.push(0.15);
  mm.std_devs.push(0.24);
  mm.corr_matrix.forEach(function (row) { row.push(0.30); });
  const newRow = new Array(n + 1).fill(0.30);
  newRow[n] = 1.0;
  mm.corr_matrix.push(newRow);
  mm.latest_prices[newSym] = null;
  renderManualTable();
  markDirty();
}

function removeManualAssetRow() {
  const mm = appState.manualMatrix;
  if (mm.symbols.length <= 2) return;
  const popped = mm.symbols.pop();
  delete mm.latest_prices[popped];
  mm.expected_returns.pop();
  mm.std_devs.pop();
  mm.corr_matrix.pop();
  mm.corr_matrix.forEach(function (row) { row.pop(); });
  renderManualTable();
  markDirty();
}

async function handleFileUpload(e, originPanel) {
  const file = e.target.files[0];
  if (!file) return;
  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/api/upload-excel', { method: 'POST', body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error reading Excel file');

    if (data.source_type === 'uploaded_prices') {
      appState.uploadedPrices = {
        datasetId: data.dataset_id,
        filename: file.name,
        uploadedAt: data.uploaded_at || null,
        fromDate: data.from_date || null,
        toDate: data.to_date || null,
        sessionsCount: data.aligned_price_sessions || data.sessions_count || 0,
        droppedDaysCount: data.dropped_days_count || 0,
        symbols: data.symbols || [],
        latestPrices: data.latest_prices || {},
        latestPriceDates: data.latest_price_dates || {}
      };
      setInputMode('uploaded_prices');
      renderUploadPriceStatus();
    } else {
      appState.manualMatrix = {
        symbols: data.symbols || [],
        expected_returns: data.expected_returns || [],
        std_devs: data.std_devs || [],
        corr_matrix: data.corr_matrix || [],
        latest_prices: data.latest_prices || {},
        datasetId: data.dataset_id || null,
        filename: file.name
      };
      setInputMode('manual_matrix');
      renderManualTable();
    }
    e.target.value = '';
    await runMVOOptimization();
  } catch (err) {
    showErrorBanner('UPLOAD_ERROR', err.message, '');
  }
}

// --- Risk Tolerance Quiz Modal (No Default Checked Options!) ---
function getSelectedQuizAnswers() {
  const out = [];
  for (let i = 0; i < quizQuestions.length; i++) {
    const sel = document.querySelector(`input[name="quiz_q_${i}"]:checked`);
    out.push(sel ? parseInt(sel.value, 10) : null);
  }
  return out;
}

function renderQuizQuestions(preservedSelections) {
  const container = document.getElementById('quiz-questions-container');
  if (!container) return;
  container.innerHTML = '';
  const isEn = appState.uiLang === 'en';

  quizQuestions.forEach(function (q, qIdx) {
    const card = document.createElement('div');
    card.className = 'p-3.5 swiss-subtle space-y-2';
    const qText = (isEn && q.question_en) ? q.question_en : q.question;
    let optsHtml = '';
    const chosenScore = preservedSelections && preservedSelections[qIdx] !== undefined ? preservedSelections[qIdx] : null;

    q.options.forEach(function (opt) {
      const optLabel = (isEn && opt.label_en) ? opt.label_en : opt.label;
      const checkedAttr = chosenScore === opt.score ? 'checked' : '';
      optsHtml += `
        <label class="flex items-start space-x-2 cursor-pointer py-0.5" style="color: var(--text-secondary);">
          <input type="radio" name="quiz_q_${qIdx}" value="${opt.score}" ${checkedAttr} class="mt-0.5" style="accent-color: var(--accent);" />
          <span>${optLabel}</span>
        </label>`;
    });
    const htmlCard = `<div class="font-semibold" style="color: var(--text-primary);">${qText}</div><div class="space-y-1">${optsHtml}</div>`;
    card.innerHTML = htmlCard;
    container.appendChild(card);
  });

  const mapNote = document.getElementById('quiz-mapping-note');
  if (mapNote) {
    const mapText = isEn
      ? 'Score 4..16 Mapping → γ: 4→8.0 | 5→7.0 | 6→6.0 | 8→4.5 | 10→3.5 | 11→3.0 | 14→1.8 | 16→1.2. Educational calibration only; not financial advice.'
      : 'Quy đổi điểm 4..16 → γ: 4→8.0 | 5→7.0 | 6→6.0 | 8→4.5 | 10→3.5 | 11→3.0 | 14→1.8 | 16→1.2. Công cụ minh họa học thuật, không phải tư vấn đầu tư cá nhân hóa.';
    mapNote.textContent = mapText;
  }
}

function renderQuizQuestionsPreservingSelection() {
  const prev = getSelectedQuizAnswers();
  renderQuizQuestions(prev);
}

function toggleQuizModal() {
  const panel = document.getElementById('quiz-box-panel');
  if (!panel) return;
  const opening = panel.classList.contains('hidden');
  if (opening) {
    lastFocusedBeforeModal = document.activeElement;
    const errEl = document.getElementById('quiz-validation-error');
    if (errEl) errEl.classList.add('hidden');
    panel.classList.remove('hidden');
    const closeBtn = document.getElementById('btn-quiz-close');
    if (closeBtn) closeBtn.focus();
  } else {
    panel.classList.add('hidden');
    if (lastFocusedBeforeModal && typeof lastFocusedBeforeModal.focus === 'function') {
      lastFocusedBeforeModal.focus();
    }
    lastFocusedBeforeModal = null;
  }
}

async function submitRiskQuiz() {
  const errEl = document.getElementById('quiz-validation-error');
  const selections = getSelectedQuizAnswers();
  const answeredCount = selections.filter(function (v) { return v !== null; }).length;
  if (answeredCount < 4) {
    if (errEl) {
      errEl.textContent = tr('quiz.missing', { answered: answeredCount });
      errEl.classList.remove('hidden');
    }
    return;
  }
  if (errEl) errEl.classList.add('hidden');

  try {
    const res = await fetch('/api/quiz', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scores: selections })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error evaluating quiz');

    const gamma = data.risk_aversion_gamma || data.risk_aversion_A || 3.0;
    const isEn = appState.uiLang === 'en';
    const tierTxt = (isEn && data.profile_tier_en) ? data.profile_tier_en : data.profile_tier;
    const descTxt = (isEn && data.description_en) ? data.description_en : data.description;

    const rngEl = document.getElementById('rng-risk-a');
    const lblEl = document.getElementById('lbl-risk-a');
    const badgeEl = document.getElementById('quiz-profile-badge');
    const sumEl = document.getElementById('quiz-result-summary');
    if (rngEl) rngEl.value = gamma;
    if (lblEl) lblEl.textContent = fmtNum(gamma, 1);
    if (badgeEl) badgeEl.textContent = `${tierTxt} (γ = ${fmtNum(gamma, 1)})`;
    if (sumEl) sumEl.textContent = `${tierTxt}: ${descTxt}`;

    toggleQuizModal();
    await runMVOOptimization();
  } catch (err) {
    if (errEl) {
      errEl.textContent = err.message;
      errEl.classList.remove('hidden');
    }
  }
}

// --- Benchmark Interactive Attribution Controls (With Race Guard) ---
function updateBenchmarkPillsUI() {
  const horizons = ['6m', '1y', '3y', '5y', 'ytd', 'max'];
  horizons.forEach(function (hz) {
    const pill = document.getElementById(`bm-pill-hz-${hz}`);
    if (pill) {
      if (hz === appState.benchmarkHorizon) {
        pill.classList.add('font-semibold');
        pill.style.backgroundColor = 'var(--accent)';
        pill.style.color = '#ffffff';
      } else {
        pill.classList.remove('font-semibold');
        pill.style.backgroundColor = 'transparent';
        pill.style.color = 'var(--text-secondary)';
      }
    }
  });

  const pVnindex = document.getElementById('bm-pill-idx-vnindex');
  const pVn30 = document.getElementById('bm-pill-idx-vn30');
  if (pVnindex && pVn30) {
    pVnindex.classList.toggle('active', appState.benchmarkSymbol === 'VNINDEX');
    pVn30.classList.toggle('active', appState.benchmarkSymbol === 'VN30');
  }

  const selBmLeft = document.getElementById('sel-benchmark');
  const selBmTab = document.getElementById('sel-benchmark-tab');
  const selHorLeft = document.getElementById('sel-benchmark-horizon');
  const selHorTab = document.getElementById('sel-benchmark-horizon-tab');
  if (selBmLeft) selBmLeft.value = appState.benchmarkSymbol;
  if (selBmTab) selBmTab.value = appState.benchmarkSymbol;
  if (selHorLeft) selHorLeft.value = appState.benchmarkHorizon;
  if (selHorTab) selHorTab.value = appState.benchmarkHorizon;
}

async function setBenchmarkHorizon(horizon) {
  if (!horizon) return;
  appState.benchmarkHorizon = horizon.toLowerCase();
  updateBenchmarkPillsUI();
  if (lastAnalysisData && lastAnalysisData.tangency && lastAnalysisData.symbols) {
    await runBenchmarkAttributionRecalc();
  }
}

async function setBenchmarkIndex(symbol) {
  if (!symbol) return;
  appState.benchmarkSymbol = symbol.toUpperCase();
  updateBenchmarkPillsUI();
  if (lastAnalysisData && lastAnalysisData.tangency && lastAnalysisData.symbols) {
    await runBenchmarkAttributionRecalc();
  }
}

function onBenchmarkConfigChange(newSym, newHorizon) {
  if (newSym) appState.benchmarkSymbol = newSym.toUpperCase();
  if (newHorizon) appState.benchmarkHorizon = newHorizon.toLowerCase();
  updateBenchmarkPillsUI();
  if (lastAnalysisData && lastAnalysisData.tangency && lastAnalysisData.symbols) {
    runBenchmarkAttributionRecalc();
  }
}

async function runBenchmarkAttributionRecalc() {
  const spinner = document.getElementById('bm-attribution-spinner');
  if (spinner) spinner.classList.remove('hidden');
  const seq = ++appState.benchmarkSeq;

  try {
    const rf = (parseFloat(document.getElementById('inp-rf').value) || 4.5) / 100.0;
    const useAdjEl = document.getElementById('chk-hayinsights-adj');
    const useAdj = useAdjEl ? Boolean(useAdjEl.checked) : true;
    const syms = lastAnalysisData.symbols || getHayInsightsSymbolList();
    const tan = lastAnalysisData.tangency || {};
    const optRange = (lastAnalysisData.data_meta && lastAnalysisData.data_meta.range) ? lastAnalysisData.data_meta.range : '1y';

    const reqBody = {
      symbols: syms,
      w_tangency: tan.weights || [],
      tangency_return: tan.expected_return || 0.0,
      tangency_volatility: tan.volatility || 0.0,
      tangency_sharpe: tan.sharpe_ratio || 0.0,
      rf: rf,
      benchmark_symbol: appState.benchmarkSymbol,
      benchmark_range: appState.benchmarkHorizon,
      optimization_range: optRange,
      use_adjusted_close: useAdj,
      input_mode: lastAnalysisData.input_mode_canonical || appState.inputMode,
      dataset_id: lastAnalysisData.data_meta ? lastAnalysisData.data_meta.dataset_id : null,
      run_id: lastAnalysisData.run_id || null
    };

    const res = await fetch('/api/benchmark-attribution', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(reqBody)
    });
    if (!res.ok) {
      const err = await res.json().catch(function () { return {}; });
      throw new Error(err.detail || 'Attribution calculation failed');
    }
    const bmData = await res.json();
    if (seq !== appState.benchmarkSeq) return;

    lastAnalysisData.benchmark_comparison = bmData;
    lastAnalysisData.benchmark_range = appState.benchmarkHorizon;
    lastAnalysisData.benchmark_symbol = appState.benchmarkSymbol;
    renderBenchmarkTab(lastAnalysisData);
    renderPlotlyFrontier(lastAnalysisData);
  } catch (err) {
    console.error('Benchmark attribution recalculation error:', err);
  } finally {
    if (spinner && seq === appState.benchmarkSeq) spinner.classList.add('hidden');
  }
}

// --- Optimization Payload & Request Execution ---
function buildRequestPayload() {
  const rfRaw = parseFloat(document.getElementById('inp-rf').value);
  const rf = (Number.isNaN(rfRaw) ? 4.5 : rfRaw) / 100.0;
  const navRaw = parseFloat(document.getElementById('inp-nav').value);
  const nav = Number.isNaN(navRaw) ? 1000000000 : navRaw;
  const feeRaw = parseFloat(document.getElementById('inp-buy-fee').value);
  const buyFeeRate = Math.max(0, Number.isNaN(feeRaw) ? 0.15 : feeRaw) / 100.0;
  const gammaRaw = parseFloat(document.getElementById('rng-risk-a').value);
  const gamma = Number.isNaN(gammaRaw) ? 3.0 : gammaRaw;
  const allowShort = Boolean(document.getElementById('chk-allow-short').checked);

  const wMinEl = document.getElementById('rng-w-min');
  const wMaxEl = document.getElementById('rng-w-max');
  const wMin = (parseFloat(wMinEl ? wMinEl.value : 0) || 0) / 100.0;
  const wMax = (parseFloat(wMaxEl ? wMaxEl.value : 100) || 100) / 100.0;

  const manEl = document.getElementById('inp-mandated-cash');
  const mandatedCashPct = Math.max(0, Math.min(1, (parseFloat(manEl ? manEl.value : 0) || 0) / 100.0));
  const bmSymEl = document.getElementById('sel-benchmark');
  const bmHorEl = document.getElementById('sel-benchmark-horizon');

  const baseParams = {
    rf: rf,
    risk_aversion_gamma: gamma,
    risk_aversion_A: gamma,
    allow_short: allowShort,
    w_min: wMin,
    w_max: wMax,
    cash_mode: appState.cashMode,
    mandated_cash_pct: mandatedCashPct,
    benchmark_symbol: bmSymEl ? bmSymEl.value : appState.benchmarkSymbol,
    benchmark_range: bmHorEl ? bmHorEl.value : appState.benchmarkHorizon,
    nav_vnd: nav,
    buy_fee_rate: buyFeeRate,
    lot_size: 100,
    n_monte_carlo: 2500,
    risk_report_basis: appState.riskReportBasis,
    lang: appState.uiLang
  };

  if (appState.inputMode === 'live_market') {
    const rngEl = document.getElementById('sel-hayinsights-range');
    const adjEl = document.getElementById('chk-hayinsights-adj');
    return {
      input_mode: 'live_market',
      symbols: getHayInsightsSymbolList(),
      hayinsights_range: rngEl ? rngEl.value : '1y',
      use_adjusted_close: adjEl ? Boolean(adjEl.checked) : true,
      ...baseParams
    };
  }

  if (appState.inputMode === 'uploaded_prices') {
    return {
      input_mode: 'uploaded_prices',
      dataset_id: appState.uploadedPrices.datasetId,
      symbols: [...appState.uploadedPrices.symbols],
      ...baseParams
    };
  }

  const cleanPrices = {};
  appState.manualMatrix.symbols.forEach(function (sym) {
    const val = appState.manualMatrix.latest_prices[sym];
    cleanPrices[sym] = (val !== undefined && val !== null && Number(val) > 0) ? Number(val) : null;
  });

  return {
    input_mode: 'manual_matrix',
    dataset_id: appState.manualMatrix.datasetId,
    symbols: [...appState.manualMatrix.symbols],
    expected_returns: [...appState.manualMatrix.expected_returns],
    std_devs: [...appState.manualMatrix.std_devs],
    corr_matrix: appState.manualMatrix.corr_matrix,
    latest_prices: cleanPrices,
    ...baseParams
  };
}

function showErrorBanner(titleKeyOrText, messageText, suggestionText) {
  const errBox = document.getElementById('banner-error');
  const titleEl = document.getElementById('banner-error-title');
  const msgEl = document.getElementById('banner-error-msg');
  const sugEl = document.getElementById('banner-error-suggestion');
  if (!errBox) return;

  if (titleEl) titleEl.textContent = titleKeyOrText || tr('banner.error_title');
  if (msgEl) msgEl.textContent = messageText || '';
  if (sugEl) {
    sugEl.textContent = suggestionText || '';
    sugEl.classList.toggle('hidden', !suggestionText);
  }
  errBox.classList.remove('hidden');
}

function hideErrorBanner() {
  const errBox = document.getElementById('banner-error');
  if (errBox) errBox.classList.add('hidden');
}

async function runMVOOptimization() {
  if (appState.inputMode === 'uploaded_prices' && !appState.uploadedPrices.datasetId) {
    showErrorBanner(tr('banner.error_title'), tr('upload.must_upload_first'), '');
    markDirty();
    return;
  }

  const payload = buildRequestPayload();
  if (!payload.symbols || payload.symbols.length < 2) {
    showErrorBanner(tr('banner.error_title'), tr('live.min_assets_alert'), '');
    return;
  }

  const seq = ++appState.requestSeq;
  if (appState.activeAbortController) {
    appState.activeAbortController.abort();
  }
  const controller = new AbortController();
  appState.activeAbortController = controller;
  appState.isComputing = true;
  hideErrorBanner();

  const compBanner = document.getElementById('banner-computing');
  if (compBanner) compBanner.classList.remove('hidden');

  const btn = document.getElementById('btn-run-mvo');
  const oldHtml = btn ? btn.innerHTML : '';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span>${tr('btn.running')}</span>`;
  }
  updateExportLockState();

  try {
    const res = await fetch('/api/optimize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal
    });
    const data = await res.json();
    if (seq !== appState.requestSeq) return;

    if (!res.ok) {
      if (data && typeof data.detail === 'object' && data.detail !== null) {
        showErrorBanner(tr('banner.error_title'), data.detail.message || 'Invalid constraints', data.detail.suggestion || '');
      } else {
        showErrorBanner(tr('banner.error_title'), (data && data.detail) ? String(data.detail) : 'Optimization error', '');
      }
      if (appState.committedSnapshot) {
        appState.isDirty = true;
        const staleEl = document.getElementById('banner-stale');
        if (staleEl) staleEl.classList.remove('hidden');
      }
      return;
    }

    lastAnalysisData = data;
    appState.committedSnapshot = {
      runId: data.run_id,
      requestPayload: payload,
      responseData: data,
      computedAt: data.computed_at
    };
    appState.benchmarkSymbol = (data.benchmark_symbol || appState.benchmarkSymbol || 'VNINDEX').toUpperCase();
    appState.benchmarkHorizon = (data.benchmark_range || appState.benchmarkHorizon || '1y').toLowerCase();

    if (data.input_mode_canonical === 'live_market' && data.latest_prices) {
      Object.assign(appState.liveMarket.latestPrices, data.latest_prices);
      renderSelectedTickerPills();
    }

    clearDirty();
    renderAllCommittedViews(data);
  } catch (err) {
    if (err && err.name === 'AbortError') return;
    if (seq !== appState.requestSeq) return;
    showErrorBanner(tr('banner.error_title'), err.message || 'Network error', '');
  } finally {
    if (seq === appState.requestSeq) {
      appState.isComputing = false;
      appState.activeAbortController = null;
      if (compBanner) compBanner.classList.add('hidden');
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = oldHtml;
      }
      updateExportLockState();
    }
  }
}

function renderAllCommittedViews(data) {
  renderProvenanceBox(data);
  renderModelNoticeBanner(data);
  renderModeBadge(data);
  renderKPISummary(data);
  renderPlotlyFrontier(data);
  renderPlotlyWeights(data);
  renderWeightsAndLot100Table(data);
  renderBenchmarkTab(data);
  renderStressTestingTab(data);
  renderMatricesTables(data);
  renderAlgebraStepByStep(data);
}

function renderProvenanceBox(data) {
  const el = document.getElementById('prov-summary-body');
  if (!el) return;
  const meta = data.data_meta || {};
  const srcName = meta.filename ? `${meta.source} (${meta.filename})` : (meta.source || '--');
  const rngTxt = (meta.from_date && meta.to_date) ? `${meta.from_date} → ${meta.to_date}` : (meta.range || 'Parametric Input');
  const html = `
    <div><strong>${tr('prov.source')}</strong> ${srcName}</div>
    <div><strong>${tr('prov.range')}</strong> ${rngTxt}</div>
    <div><strong>${tr('prov.sessions')}</strong> ${meta.aligned_sessions || 0} &middot; <strong>${tr('prov.dropped')}</strong> ${meta.dropped_days_count || 0}</div>
    <div><strong>${tr('prov.basis')}</strong> ${meta.price_basis || '--'}</div>
    <div><strong>${tr('prov.timestamp')}</strong> ${data.computed_at || meta.fetched_at || '--'}</div>
  `;
  el.innerHTML = html;

  const srcTag = document.getElementById('lbl-data-source-tag');
  if (srcTag) {
    if (meta.from_date && meta.to_date) {
      srcTag.textContent = `${meta.from_date} → ${meta.to_date} (${data.sessions_count || 0}d)`;
    } else if (meta.filename) {
      srcTag.textContent = meta.filename;
    } else {
      updateSourceTagUI();
    }
  }
}

function renderModelNoticeBanner(data) {
  const banner = document.getElementById('banner-model-notice');
  if (banner) {
    if (data.tangency_status === 'no_positive_excess_return') {
      banner.textContent = tr('banner.no_positive_excess');
      banner.classList.remove('hidden');
    } else if (data.allow_short) {
      banner.textContent = tr('banner.short_mode');
      banner.classList.remove('hidden');
    } else {
      banner.textContent = '';
      banner.classList.add('hidden');
    }
  }

  const singleLbl = document.getElementById('lbl-singleton-note');
  if (singleLbl) {
    if (data.is_singleton) {
      const wParts = (data.symbols || []).map(function (s, idx) {
        const w = (data.gmv && data.gmv.weights) ? data.gmv.weights[idx] : 0;
        return `${s}: ${fmtPct(w, 1)}`;
      }).join(', ');
      singleLbl.textContent = `${tr('banner.singleton_prefix')} [${wParts}]`;
      singleLbl.classList.remove('hidden');
    } else {
      singleLbl.textContent = '';
      singleLbl.classList.add('hidden');
    }
  }
}

function renderModeBadge(data) {
  const modeLbl = document.getElementById('chart-mode-label');
  if (!modeLbl) return;
  if (data.allow_short) {
    modeLbl.textContent = tr('mode.short');
  } else {
    const minP = Math.round((data.w_min !== undefined ? data.w_min : 0) * 100);
    const maxP = Math.round((data.w_max !== undefined ? data.w_max : 1) * 100);
    if (minP > 0 || maxP < 100) {
      modeLbl.textContent = tr('mode.bounded', { min: minP, max: maxP });
    } else {
      modeLbl.textContent = tr('mode.long_only');
    }
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
  const yStar = comp.y_star_risky_weight !== undefined ? comp.y_star_risky_weight : 0;
  const wRf = comp.w_rf_weight !== undefined ? comp.w_rf_weight : (1 - yStar);
  const uScore = comp.utility_score !== undefined ? comp.utility_score : 0;

  document.getElementById('kpi-comp-y').textContent = fmtPct(yStar, 1);
  document.getElementById('kpi-comp-rfw').textContent = fmtPct(wRf, 1);
  document.getElementById('kpi-comp-ret').textContent = fmtPct(comp.expected_return);
  document.getElementById('kpi-comp-vol').textContent = fmtPct(comp.volatility);
  document.getElementById('kpi-comp-u').textContent = fmtNum(uScore, 4);
}

// --- Plotly Theme Tokens ---
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

function getResponsiveLegendConfig(isCompact) {
  if (isCompact) {
    return {
      orientation: 'h',
      yanchor: 'top',
      y: -0.24,
      xanchor: 'left',
      x: 0,
      font: { size: 9.5 }
    };
  }
  return {
    orientation: 'h',
    yanchor: 'bottom',
    y: 1.02,
    xanchor: 'left',
    x: 0,
    font: { size: 10 }
  };
}

function renderPlotlyFrontier(data) {
  const tkn = getChartThemeTokens();
  const mc = data.monte_carlo || [];
  const fr = data.frontier || [];
  const tan = data.tangency || {};
  const gmv = data.gmv || {};
  const comp = data.complete_portfolio || {};
  const assets = data.individual_assets || [];
  const bm = data.benchmark_comparison || null;
  const gamma = data.risk_aversion_gamma || data.risk_aversion_A || 3.0;
  const compact = window.innerWidth < 640;

  const traceMC = {
    x: mc.map(function (d) { return d.volatility; }),
    y: mc.map(function (d) { return d.return !== undefined ? d.return : (d.expected_return * 100); }),
    mode: 'markers',
    type: 'scattergl',
    name: tr('chart.trace_mc'),
    marker: {
      size: data.is_singleton ? 10 : 4,
      color: mc.map(function (d) { return d.sharpe !== undefined ? d.sharpe : 0; }),
      colorscale: isDarkMode() ? 'Blues' : 'YlGnBu',
      opacity: data.is_singleton ? 0.9 : (isDarkMode() ? 0.35 : 0.45),
      showscale: false
    },
    hoverinfo: 'skip'
  };

  const traceFrontier = {
    x: fr.map(function (p) { return p.volatility * 100; }),
    y: fr.map(function (p) { return (p.return !== undefined ? p.return : p.expected_return) * 100; }),
    mode: 'lines',
    type: 'scatter',
    name: tr('chart.trace_frontier'),
    line: { color: tkn.navyAccent, width: 3 },
    hovertemplate: 'σ: %{x:.2f}%<br>E(R): %{y:.2f}%<extra></extra>'
  };

  const traceCAL = {
    x: (comp.cal_line || []).map(function (p) { return p.volatility * 100; }),
    y: (comp.cal_line || []).map(function (p) { return (p.return !== undefined ? p.return : p.expected_return) * 100; }),
    mode: 'lines',
    type: 'scatter',
    name: tr('chart.trace_cal'),
    line: { color: tkn.amberColor, width: 2, dash: 'dash' },
    hovertemplate: 'σ: %{x:.2f}%<br>E(R): %{y:.2f}%<extra>CAL</extra>'
  };

  const traceIndiff = {
    x: (comp.indifference_curve || []).map(function (p) { return p.volatility * 100; }),
    y: (comp.indifference_curve || []).map(function (p) { return (p.return !== undefined ? p.return : p.expected_return) * 100; }),
    mode: 'lines',
    type: 'scatter',
    name: tr('chart.trace_indiff', { gamma: fmtNum(gamma, 1) }),
    line: { color: tkn.purpleColor, width: 1.5, dash: 'dot' },
    hovertemplate: 'σ: %{x:.2f}%<br>E(R): %{y:.2f}%<extra>U*</extra>'
  };

  const traceAssets = {
    x: assets.map(function (a) { return a.volatility * 100; }),
    y: assets.map(function (a) { return a.expected_return * 100; }),
    text: assets.map(function (a) { return a.symbol; }),
    mode: 'markers+text',
    type: 'scatter',
    name: tr('chart.trace_assets'),
    textposition: 'top center',
    textfont: { family: 'JetBrains Mono', size: 10, color: tkn.fontColor },
    marker: { size: 8, color: tkn.slateColor, line: { width: 1.5, color: tkn.cardBg } },
    hovertemplate: '<b>%{text}</b><br>σ: %{x:.2f}%<br>E(R): %{y:.2f}%<extra></extra>'
  };

  const traceGMV = {
    x: [gmv.volatility * 100],
    y: [gmv.expected_return * 100],
    mode: 'markers',
    type: 'scatter',
    name: tr('chart.trace_gmv'),
    marker: { size: 11, symbol: 'diamond', color: tkn.amberColor, line: { width: 1.5, color: tkn.cardBg } },
    hovertemplate: '<b>GMV</b><br>σ: %{x:.2f}%<br>E(R): %{y:.2f}%<extra></extra>'
  };

  const traceTan = {
    x: [tan.volatility * 100],
    y: [tan.expected_return * 100],
    mode: 'markers',
    type: 'scatter',
    name: tr('chart.trace_tan'),
    marker: { size: 12, symbol: 'circle', color: tkn.emeraldColor, line: { width: 2, color: tkn.cardBg } },
    hovertemplate: '<b>Tangency</b><br>σ: %{x:.2f}%<br>E(R): %{y:.2f}%<br>Sharpe: ' + fmtNum(tan.sharpe_ratio, 3) + '<extra></extra>'
  };

  const traceComp = {
    x: [comp.volatility * 100],
    y: [comp.expected_return * 100],
    mode: 'markers',
    type: 'scatter',
    name: tr('chart.trace_comp'),
    marker: { size: 11, symbol: 'square', color: tkn.purpleColor, line: { width: 1.5, color: tkn.cardBg } },
    hovertemplate: '<b>Complete (C)</b><br>σ: %{x:.2f}%<br>E(R): %{y:.2f}%<extra></extra>'
  };

  const traces = [traceMC, traceFrontier, traceCAL, traceIndiff, traceAssets, traceGMV, traceTan, traceComp];

  if (bm && bm.status === 'available' && bm.benchmark_volatility != null && bm.benchmark_return != null) {
    traces.push({
      x: [bm.benchmark_volatility * 100],
      y: [bm.benchmark_return * 100],
      text: [bm.benchmark_symbol],
      mode: 'markers+text',
      type: 'scatter',
      name: `Benchmark (${bm.benchmark_symbol})`,
      textposition: 'bottom center',
      textfont: { family: 'JetBrains Mono', size: 10, color: tkn.roseColor },
      marker: { size: 11, symbol: 'star', color: tkn.roseColor, line: { width: 1.5, color: tkn.cardBg } },
      hovertemplate: `<b>${bm.benchmark_symbol}</b><br>σ: %{x:.2f}%<br>E(R): %{y:.2f}%<extra></extra>`
    });
  }

  const layout = {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    margin: compact ? { l: 44, r: 12, t: 16, b: 96 } : { l: 50, r: 20, t: 32, b: 44 },
    font: { family: 'Inter, sans-serif', color: tkn.fontColor, size: 11 },
    xaxis: {
      title: tr('chart.x_vol'),
      gridcolor: tkn.gridColor,
      zerolinecolor: tkn.zeroLineColor,
      ticksuffix: '%'
    },
    yaxis: {
      title: tr('chart.y_ret'),
      gridcolor: tkn.gridColor,
      zerolinecolor: tkn.zeroLineColor,
      ticksuffix: '%'
    },
    legend: getResponsiveLegendConfig(compact),
    hovermode: 'closest'
  };

  Plotly.react('chart-frontier', traces, layout, { responsive: true, displayModeBar: false });
}

function renderPlotlyWeights(data) {
  const tkn = getChartThemeTokens();
  const syms = data.symbols || [];
  const categories = [...syms, tr('chart.cash_label')];
  const comp = data.complete_portfolio || {};
  const compAssets = comp.asset_weights || [];
  const wCashComp = comp.w_rf_weight !== undefined ? comp.w_rf_weight : 0;

  const toPct = function (arr, cashVal) {
    const base = (arr || []).map(function (w) {
      return (w !== null && w !== undefined && !Number.isNaN(Number(w))) ? Number((w * 100).toFixed(2)) : 0;
    });
    base.push(Number((cashVal * 100).toFixed(2)));
    return base;
  };

  const traces = [
    {
      x: categories,
      y: toPct(data.gmv ? data.gmv.weights : [], 0),
      name: tr('chart.trace_gmv'),
      type: 'bar',
      marker: { color: tkn.amberColor }
    },
    {
      x: categories,
      y: toPct(data.tangency ? data.tangency.weights : [], 0),
      name: tr('chart.trace_tan'),
      type: 'bar',
      marker: { color: tkn.navyAccent }
    },
    {
      x: categories,
      y: toPct(compAssets, wCashComp),
      name: tr('chart.trace_comp'),
      type: 'bar',
      marker: { color: tkn.emeraldColor }
    }
  ];

  const exec = data.execution || {};
  if (exec.status === 'ready' && Array.isArray(exec.actual_weights_post_fee)) {
    traces.push({
      x: categories,
      y: toPct(exec.actual_weights_post_fee, exec.actual_cash_weight_post_fee || 0),
      name: tr('chart.trace_exec'),
      type: 'bar',
      marker: {
        color: tkn.purpleColor,
        pattern: { shape: '/' }
      }
    });
  }

  const compact = window.innerWidth < 640;
  const layout = {
    barmode: 'group',
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    margin: compact ? { l: 42, r: 10, t: 16, b: 84 } : { l: 48, r: 16, t: 28, b: 36 },
    font: { family: 'Inter, sans-serif', color: tkn.fontColor, size: 11 },
    xaxis: { gridcolor: 'rgba(0,0,0,0)', font: { family: 'JetBrains Mono' } },
    yaxis: {
      title: tr('chart.y_weight'),
      gridcolor: tkn.gridColor,
      zerolinecolor: tkn.zeroLineColor,
      ticksuffix: '%'
    },
    legend: getResponsiveLegendConfig(compact)
  };

  Plotly.react('chart-weights', traces, layout, { responsive: true, displayModeBar: false });
}

// --- Tab 01: Lot-100 Execution (Single Source of Truth from data.execution) ---
function renderWeightsAndLot100Table(data) {
  const tbl = document.getElementById('tbl-weights-lot100');
  const mobileBox = document.getElementById('mobile-execution-cards');
  const reconBox = document.getElementById('exec-reconciliation-bar');
  const disabledBanner = document.getElementById('exec-disabled-banner');
  const driftBanner = document.getElementById('exec-drift-banner');
  const execLbl = document.getElementById('lbl-execution-summary');
  if (!tbl) return;

  const syms = data.symbols || [];
  const nav = data.nav_vnd || 1000000000;
  const wGmv = data.gmv ? (data.gmv.weights || []) : [];
  const wTan = data.tangency ? (data.tangency.weights || []) : [];
  const wEq = data.equal_weight ? (data.equal_weight.weights || []) : [];
  const comp = data.complete_portfolio || {};
  const wComp = comp.asset_weights || [];
  const wCashTarget = comp.w_rf_weight !== undefined ? comp.w_rf_weight : 0;
  const exec = data.execution || {};
  const isReady = exec.status === 'ready';
  const orders = exec.orders || [];

  if (disabledBanner) {
    if (!isReady) {
      let msg = exec.disabled_reason || '';
      if (exec.status === 'disabled_short_mode') msg = tr('exec.disabled_short');
      else if (exec.status === 'disabled_no_prices') {
        const missStr = (exec.missing_price_symbols || []).join(', ');
        msg = tr('exec.disabled_no_prices', { missing: missStr || '--' });
      }
      disabledBanner.textContent = msg;
      disabledBanner.classList.remove('hidden');
    } else {
      disabledBanner.textContent = '';
      disabledBanner.classList.add('hidden');
    }
  }

  if (driftBanner) {
    const drifts = exec.bounds_drift_warnings || [];
    if (isReady && drifts.length > 0) {
      driftBanner.textContent = `${tr('exec.drift_warn')} ${drifts.join(' | ')}`;
      driftBanner.classList.remove('hidden');
    } else {
      driftBanner.textContent = '';
      driftBanner.classList.add('hidden');
    }
  }

  if (reconBox) {
    if (isReady) {
      const reconHtml = `
        <div class="p-2.5 swiss-subtle"><div class="text-[10px]" style="color: var(--text-muted);">${tr('exec.nav_initial')}</div><div class="font-bold">${fmtVnd(exec.nav_vnd)} VND</div></div>
        <div class="p-2.5 swiss-subtle"><div class="text-[10px]" style="color: var(--text-muted);">${tr('exec.equities_val')}</div><div class="font-bold">${fmtVnd(exec.total_purchase_value)} VND</div></div>
        <div class="p-2.5 swiss-subtle"><div class="text-[10px]" style="color: var(--text-muted);">${tr('exec.fees_val')} (${fmtPct(exec.buy_fee_rate, 2)})</div><div class="font-bold" style="color: var(--warning);">${fmtVnd(exec.total_buy_fees)} VND</div></div>
        <div class="p-2.5 swiss-subtle"><div class="text-[10px]" style="color: var(--text-muted);">${tr('exec.cash_rem')}</div><div class="font-bold" style="color: var(--success);">${fmtVnd(exec.cash_remaining)} VND</div></div>
        <div class="p-2.5 swiss-subtle col-span-2 sm:col-span-1"><div class="text-[10px]" style="color: var(--text-muted);">${tr('exec.nav_post_fee')}</div><div class="font-bold" style="color: var(--accent);">${fmtVnd(exec.nav_post_fee)} VND</div></div>
      `;
      reconBox.innerHTML = reconHtml;
    } else {
      reconBox.innerHTML = '';
    }
  }

  let html = `<thead><tr>
    <th class="sticky-col">${tr('exec.col_ticker')}</th>
    <th class="text-right">${tr('exec.col_price')}</th>
    <th class="text-right">${tr('exec.col_wgmv')}</th>
    <th class="text-right">${tr('exec.col_wtan')}</th>
    <th class="text-right">${tr('exec.col_w1n')}</th>
    <th class="text-right">${tr('exec.col_wcomp')}</th>
    <th class="text-right">${tr('exec.col_target')}</th>
    <th class="text-right">${tr('exec.col_shares')}</th>
    <th class="text-right">${tr('exec.col_exec')}</th>
    <th class="text-right">${tr('exec.col_fee')}</th>
    <th class="text-right">${tr('exec.col_actual_w')}</th>
  </tr></thead><tbody>`;

  let mobileHtml = '';

  for (let i = 0; i < syms.length; i++) {
    const sym = syms[i];
    const ord = orders[i] || {};
    const priceVal = ord.price_vnd;
    const priceStr = (priceVal !== null && priceVal !== undefined && priceVal > 0) ? fmtVnd(priceVal) : '--';
    const wt = wTan[i] !== undefined ? wTan[i] : 0;
    const wc = ord.w_complete_target !== undefined ? ord.w_complete_target : (wComp[i] !== undefined ? wComp[i] : 0);
    const targetVnd = ord.target_value_vnd !== undefined ? ord.target_value_vnd : (wc * nav);

    const sharesStr = isReady ? fmtVnd(ord.shares || 0) : '--';
    const execValStr = isReady ? fmtVnd(ord.purchase_value_vnd || 0) : '--';
    const feeStr = isReady ? fmtVnd(ord.buy_fee_vnd || 0) : '--';
    const actualWStr = isReady ? fmtPct(ord.actual_weight_post_fee || 0) : '--%';

    html += `<tr>
      <td class="sticky-col font-semibold">${sym}</td>
      <td class="text-right">${priceStr}</td>
      <td class="text-right">${fmtPct(wGmv[i])}</td>
      <td class="text-right font-semibold" style="color: var(--accent);">${fmtPct(wt)}</td>
      <td class="text-right" style="color: var(--text-muted);">${fmtPct(wEq[i])}</td>
      <td class="text-right font-semibold">${fmtPct(wc)}</td>
      <td class="text-right">${fmtVnd(targetVnd)}</td>
      <td class="text-right font-semibold">${sharesStr}</td>
      <td class="text-right">${execValStr}</td>
      <td class="text-right" style="color: var(--text-muted);">${feeStr}</td>
      <td class="text-right font-semibold">${actualWStr}</td>
    </tr>`;

    mobileHtml += `
      <div class="p-3 rounded border space-y-1.5 text-xs font-mono" style="background-color: var(--bg-subtle); border-color: var(--border-color);">
        <div class="flex items-center justify-between font-bold">
          <span>${sym} (${priceStr} VND)</span>
          <span style="color: var(--accent);">w<sub>C</sub>: ${fmtPct(wc)} → ${actualWStr}</span>
        </div>
        <div class="grid grid-cols-2 gap-1 text-[11px]" style="color: var(--text-secondary);">
          <div>${tr('exec.mobile_target')} ${fmtVnd(targetVnd)}</div>
          <div class="text-right">${tr('exec.mobile_shares')} <strong>${sharesStr}</strong></div>
          <div>${tr('exec.mobile_exec')} ${execValStr}</div>
          <div class="text-right">${tr('exec.mobile_fee')} ${feeStr}</div>
        </div>
      </div>`;
  }

  const targetCashVnd = exec.target_cash_vnd !== undefined ? exec.target_cash_vnd : Math.max(0, wCashTarget * nav);
  const cashRemStr = isReady ? fmtVnd(exec.cash_remaining) : fmtVnd(targetCashVnd);
  const cashWPostFeeStr = isReady ? fmtPct(exec.actual_cash_weight_post_fee) : fmtPct(wCashTarget);

  html += `<tr style="background-color: var(--bg-subtle); color: var(--text-secondary);">
    <td class="sticky-col font-semibold">${tr('exec.cash_row', { rf: fmtPct(data.rf, 1) })}</td>
    <td class="text-right">1</td>
    <td class="text-right">0.00%</td>
    <td class="text-right">0.00%</td>
    <td class="text-right">0.00%</td>
    <td class="text-right font-semibold" style="color: var(--success);">${fmtPct(wCashTarget)}</td>
    <td class="text-right">${fmtVnd(targetCashVnd)}</td>
    <td class="text-right">${tr('exec.cash_reserve')}</td>
    <td class="text-right font-semibold">${cashRemStr}</td>
    <td class="text-right">0</td>
    <td class="text-right font-semibold" style="color: var(--success);">${cashWPostFeeStr}</td>
  </tr>`;

  const sumGmv = wGmv.reduce(function (a, b) { return a + b; }, 0);
  const sumTan = wTan.reduce(function (a, b) { return a + b; }, 0);
  const sumCompAll = wComp.reduce(function (a, b) { return a + b; }, 0) + wCashTarget;
  const totalExecVnd = isReady ? fmtVnd(exec.nav_post_fee) : '--';
  const totalFeeVnd = isReady ? fmtVnd(exec.total_buy_fees) : '--';
  const totalPostFeeW = isReady ? fmtPct(1.0) : '--%';

  html += `<tr class="font-semibold" style="background-color: var(--bg-subtle);">
    <td class="sticky-col">${tr('exec.total_row')}</td>
    <td class="text-right">--</td>
    <td class="text-right">${fmtPct(sumGmv)}</td>
    <td class="text-right" style="color: var(--accent);">${fmtPct(sumTan)}</td>
    <td class="text-right">${fmtPct(1.0)}</td>
    <td class="text-right">${fmtPct(sumCompAll)}</td>
    <td class="text-right">${fmtVnd(nav)}</td>
    <td class="text-right">Lot 100</td>
    <td class="text-right">${totalExecVnd}</td>
    <td class="text-right">${totalFeeVnd}</td>
    <td class="text-right">${totalPostFeeW}</td>
  </tr></tbody>`;

  tbl.innerHTML = html;

  if (mobileBox) {
    mobileHtml += `
      <div class="p-3 rounded border text-xs font-mono flex items-center justify-between" style="background-color: var(--bg-card); border-color: var(--success);">
        <span class="font-bold">${tr('exec.cash_row', { rf: fmtPct(data.rf, 1) })}</span>
        <span class="font-bold" style="color: var(--success);">${cashRemStr} VND (${cashWPostFeeStr})</span>
      </div>`;
    mobileBox.innerHTML = mobileHtml;
  }

  if (execLbl) {
    if (isReady) {
      const sumText = `${tr('exec.equities_val')} ${fmtVnd(exec.total_purchase_value)} VND | ${tr('exec.fees_val')} ${fmtVnd(exec.total_buy_fees)} VND | ${tr('exec.cash_rem')} ${fmtVnd(exec.cash_remaining)} VND (${fmtPct(exec.actual_cash_weight_post_fee, 1)})`;
      execLbl.textContent = sumText;
    } else {
      execLbl.textContent = '';
    }
  }
}

// --- Tab 02: Institutional Benchmark Attribution ---
function renderBenchmarkTab(data) {
  const bm = data.benchmark_comparison;
  const tbl = document.getElementById('tbl-benchmark-scorecard');
  const badge = document.getElementById('lbl-benchmark-badge');
  const unavailBanner = document.getElementById('bm-unavailable-banner');
  const unavailMsg = document.getElementById('bm-unavailable-msg');
  const hwBanner = document.getElementById('bm-horizon-warning');
  if (!bm || !tbl) return;

  const bmRangeTag = (bm.benchmark_range || data.benchmark_range || appState.benchmarkHorizon || '1Y').toUpperCase();
  const bmSym = (bm.benchmark_symbol || appState.benchmarkSymbol || 'VNINDEX').toUpperCase();
  if (badge) badge.textContent = `vs. ${bmSym} (${bmRangeTag})`;
  updateBenchmarkPillsUI();

  if (hwBanner) {
    if (bm.horizon_mismatch_warning) {
      hwBanner.textContent = bm.horizon_mismatch_warning;
      hwBanner.classList.remove('hidden');
    } else {
      hwBanner.textContent = '';
      hwBanner.classList.add('hidden');
    }
  }

  const isAvail = bm.status === 'available';
  if (unavailBanner) {
    unavailBanner.classList.toggle('hidden', isAvail);
    if (!isAvail && unavailMsg) {
      unavailMsg.textContent = bm.message || bm.unavailable_reason || '';
    }
  }

  if (!isAvail) {
    ['bm-kpi-alpha', 'bm-kpi-beta', 'bm-kpi-ir', 'bm-kpi-te', 'bm-kpi-corr'].forEach(function (id) {
      const el = document.getElementById(id);
      if (el) el.textContent = '--';
    });
    const elBps = document.getElementById('bm-kpi-bps');
    const elR2 = document.getElementById('bm-kpi-r2');
    const elMeta = document.getElementById('lbl-bm-period-meta');
    if (elBps) elBps.textContent = '-- bps';
    if (elR2) elR2.textContent = 'R²: --%';
    if (elMeta) elMeta.textContent = '--';
    tbl.innerHTML = `<tbody><tr><td class="p-3 text-center" style="color: var(--text-muted);">${bm.message || ''}</td></tr></tbody>`;
    const cEl = document.getElementById('chart-benchmark-cum');
    if (cEl && window.Plotly) Plotly.purge(cEl);
    return;
  }

  const spreadSign = function (v, isPct) {
    if (v === undefined || v === null || Number.isNaN(Number(v))) return '--';
    const num = Number(v);
    const prefix = num > 0 ? '+' : '';
    return isPct ? `${prefix}${(num * 100).toFixed(2)}%` : `${prefix}${num.toFixed(3)}`;
  };

  const alphaColor = (bm.active_return || bm.jensen_alpha || 0) >= 0 ? 'var(--success)' : 'var(--danger)';
  const irColor = (bm.information_ratio || 0) >= 0 ? 'var(--success)' : 'var(--danger)';

  const elAlpha = document.getElementById('bm-kpi-alpha');
  const elBps = document.getElementById('bm-kpi-bps');
  const elBeta = document.getElementById('bm-kpi-beta');
  const elBetaTag = document.getElementById('bm-kpi-beta-tag');
  const elIr = document.getElementById('bm-kpi-ir');
  const elIrTag = document.getElementById('bm-kpi-ir-tag');
  const elTe = document.getElementById('bm-kpi-te');
  const elCorr = document.getElementById('bm-kpi-corr');
  const elR2 = document.getElementById('bm-kpi-r2');
  const elPeriodMeta = document.getElementById('lbl-bm-period-meta');

  if (elAlpha) {
    elAlpha.textContent = spreadSign(bm.active_return, true);
    elAlpha.style.color = alphaColor;
  }
  if (elBps) {
    const bpsVal = Math.round((bm.active_return || 0) * 10000);
    elBps.textContent = `${bpsVal >= 0 ? '+' : ''}${bpsVal} bps`;
  }
  if (elBeta) elBeta.textContent = fmtNum(bm.beta, 3);
  if (elBetaTag) {
    elBetaTag.textContent = bm.beta > 1.05 ? 'High Beta' : (bm.beta < 0.95 ? 'Defensive' : 'Neutral');
  }
  if (elIr) {
    elIr.textContent = fmtNum(bm.information_ratio, 2);
    elIr.style.color = irColor;
  }
  if (elIrTag) {
    const irV = bm.information_ratio || 0;
    elIrTag.textContent = irV >= 1.0 ? 'High' : (irV >= 0.5 ? 'Good' : (irV >= 0 ? 'Modest' : 'Sub-BM'));
  }
  if (elTe) elTe.textContent = fmtPct(bm.tracking_error);
  if (elCorr) elCorr.textContent = fmtNum(bm.correlation, 3);
  if (elR2) elR2.textContent = `R²: ${fmtPct(bm.r_squared, 1)}`;
  if (elPeriodMeta) {
    elPeriodMeta.textContent = `${bm.start_date || '--'} → ${bm.end_date || '--'} (${bm.sessions_compared || 0}d)`;
  }

  const tblHtml = `
    <thead>
      <tr>
        <th class="sticky-col">${tr('bm.col_metric')}</th>
        <th class="text-right">${tr('bm.col_port')}</th>
        <th class="text-right">${bm.benchmark_symbol}</th>
        <th class="text-right">${tr('bm.col_spread')}</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td class="sticky-col font-medium">E(R) Annualized</td>
        <td class="text-right font-semibold">${fmtPct(bm.portfolio_return)}</td>
        <td class="text-right">${fmtPct(bm.benchmark_return)}</td>
        <td class="text-right font-semibold" style="color: ${alphaColor};">${spreadSign(bm.active_return, true)}</td>
      </tr>
      <tr>
        <td class="sticky-col font-medium">Volatility (&sigma;)</td>
        <td class="text-right">${fmtPct(bm.portfolio_volatility)}</td>
        <td class="text-right">${fmtPct(bm.benchmark_volatility)}</td>
        <td class="text-right">${spreadSign((bm.portfolio_volatility || 0) - (bm.benchmark_volatility || 0), true)}</td>
      </tr>
      <tr>
        <td class="sticky-col font-medium">Sharpe Ratio</td>
        <td class="text-right font-semibold" style="color: var(--accent);">${fmtNum(bm.portfolio_sharpe, 3)}</td>
        <td class="text-right">${fmtNum(bm.benchmark_sharpe, 3)}</td>
        <td class="text-right font-semibold">${spreadSign(bm.sharpe_spread, false)}</td>
      </tr>
      <tr>
        <td class="sticky-col font-medium">Portfolio Beta (&beta;)</td>
        <td class="text-right font-semibold">${fmtNum(bm.beta, 3)}</td>
        <td class="text-right">1.000</td>
        <td class="text-right">${bm.beta > 1.05 ? 'High Beta' : (bm.beta < 0.95 ? 'Defensive' : 'Neutral')}</td>
      </tr>
      <tr>
        <td class="sticky-col font-medium">Jensen's Alpha (&alpha;)</td>
        <td class="text-right font-semibold" style="color: ${alphaColor};">${spreadSign(bm.jensen_alpha, true)}</td>
        <td class="text-right">0.00%</td>
        <td class="text-right" style="color: ${alphaColor};">${bm.jensen_alpha >= 0 ? 'Positive' : 'Negative'}</td>
      </tr>
      <tr>
        <td class="sticky-col font-medium">Tracking Error (TE)</td>
        <td class="text-right">${fmtPct(bm.tracking_error)}</td>
        <td class="text-right">0.00%</td>
        <td class="text-right">Active Risk</td>
      </tr>
      <tr>
        <td class="sticky-col font-medium">Information Ratio (IR)</td>
        <td class="text-right font-semibold" style="color: ${irColor};">${fmtNum(bm.information_ratio, 3)}</td>
        <td class="text-right">--</td>
        <td class="text-right">Alpha / TE</td>
      </tr>
      <tr>
        <td class="sticky-col font-medium">Correlation / R&sup2;</td>
        <td class="text-right">${fmtNum(bm.correlation, 3)}</td>
        <td class="text-right">1.000</td>
        <td class="text-right">R&sup2; = ${fmtPct(bm.r_squared, 1)}</td>
      </tr>
    </tbody>
  `;
  tbl.innerHTML = tblHtml;

  const chartEl = document.getElementById('chart-benchmark-cum');
  if (!chartEl) return;
  const tkn = getChartThemeTokens();
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
      name: `${tr('bm.col_port')} (Base 100)`,
      line: { color: tkn.navyAccent, width: 2.5 }
    });
    traces.push({
      x: dates,
      y: bSeries,
      mode: 'lines',
      type: 'scatter',
      name: `${bm.benchmark_symbol} (Base 100)`,
      line: { color: tkn.roseColor, width: 2, dash: 'dot' }
    });
  }

  const compact = window.innerWidth < 640;
  const layout = {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    margin: compact ? { l: 42, r: 10, t: 14, b: 70 } : { l: 48, r: 16, t: 28, b: 36 },
    font: { family: 'Inter, sans-serif', color: tkn.fontColor, size: 11 },
    xaxis: { gridcolor: tkn.gridColor },
    yaxis: {
      title: 'Indexed Wealth (Base = 100)',
      gridcolor: tkn.gridColor,
      zerolinecolor: tkn.zeroLineColor
    },
    legend: getResponsiveLegendConfig(compact),
    hovermode: 'x unified'
  };
  Plotly.react(chartEl, traces, layout, { responsive: true, displayModeBar: false });
}

// --- Tab 03: Stress Testing & VaR / ES ---
function renderStressTestingTab(data) {
  const stRoot = data.stress_testing;
  const cardsBox = document.getElementById('stress-var-cards');
  const tbl = document.getElementById('tbl-stress-scenarios');
  const scSec = document.getElementById('stress-scenarios-section');
  const methodLbl = document.getElementById('lbl-stress-method');
  const warnBox = document.getElementById('stress-warnings-banner');
  if (!stRoot || !cardsBox || !tbl) return;

  const btnT = document.getElementById('btn-basis-target');
  const btnE = document.getElementById('btn-basis-exec');
  const hasExec = Boolean(stRoot.profiles && stRoot.profiles.executed_post_fee);
  if (btnE) btnE.disabled = !hasExec;
  if (!hasExec && appState.riskReportBasis === 'executed_post_fee') {
    appState.riskReportBasis = 'target_complete';
  }
  if (btnT) btnT.classList.toggle('active', appState.riskReportBasis === 'target_complete');
  if (btnE) btnE.classList.toggle('active', appState.riskReportBasis === 'executed_post_fee');

  const activeProfile = (stRoot.profiles && stRoot.profiles[appState.riskReportBasis]) ? stRoot.profiles[appState.riskReportBasis] : stRoot;
  const vm = activeProfile.var_metrics || {};

  if (methodLbl) {
    const mTxt = `${activeProfile.method || stRoot.method} | N=${stRoot.sample_size || 0} | Cash=${fmtPct(activeProfile.w_cash_weight, 1)} | β=${fmtNum(activeProfile.portfolio_beta, 2)}`;
    methodLbl.textContent = mTxt;
  }

  const warnings = [...(stRoot.sample_warnings || [])];
  if (activeProfile.stress_status === 'unavailable_no_beta_history') {
    warnings.unshift(tr('stress.hist_unavailable'));
  }
  if (warnBox) {
    if (warnings.length > 0) {
      warnBox.textContent = warnings.join(' | ');
      warnBox.classList.remove('hidden');
    } else {
      warnBox.textContent = '';
      warnBox.classList.add('hidden');
    }
  }

  const mddHtml = vm.max_drawdown_complete_pct !== null && vm.max_drawdown_complete_pct !== undefined
    ? `<div class="mt-1.5 text-xl font-bold font-mono" style="color: var(--text-primary);">-${fmtPct(vm.max_drawdown_complete_pct)}</div>
       <div class="text-[11px] font-mono mt-0.5" style="color: var(--text-muted);">100% Equity MDD: -${fmtPct(vm.max_drawdown_risky_pct)}</div>`
    : `<div class="mt-1.5 text-sm font-semibold font-mono" style="color: var(--text-muted);">--</div>
       <div class="text-[11px] mt-0.5" style="color: var(--text-muted);">${tr('stress.mdd_unavail')}</div>`;

  const cardsHtml = `
    <div class="swiss-subtle p-3.5 rounded border" style="border-color: var(--border-color);">
      <div class="text-[11px] font-semibold uppercase tracking-wider" style="color: var(--text-muted);">${tr('stress.var95_1d')}</div>
      <div class="mt-1.5 text-xl font-bold font-mono" style="color: var(--danger);">-${fmtPct(vm.var_95_1d_pct)}</div>
      <div class="text-[11px] font-mono mt-0.5" style="color: var(--text-secondary);">-${fmtVnd(vm.var_95_1d_vnd || 0)} VND (99%: -${fmtPct(vm.var_99_1d_pct)})</div>
    </div>
    <div class="swiss-subtle p-3.5 rounded border" style="border-color: var(--border-color);">
      <div class="text-[11px] font-semibold uppercase tracking-wider" style="color: var(--text-muted);">${tr('stress.es95_1d')}</div>
      <div class="mt-1.5 text-xl font-bold font-mono" style="color: var(--danger);">-${fmtPct(vm.cvar_95_1d_pct)}</div>
      <div class="text-[11px] font-mono mt-0.5" style="color: var(--text-secondary);">-${fmtVnd(vm.cvar_95_1d_vnd || 0)} VND (99%: -${fmtPct(vm.cvar_99_1d_pct)})</div>
    </div>
    <div class="swiss-subtle p-3.5 rounded border" style="border-color: var(--border-color);">
      <div class="text-[11px] font-semibold uppercase tracking-wider" style="color: var(--text-muted);">${tr('stress.var95_21d')}</div>
      <div class="mt-1.5 text-xl font-bold font-mono" style="color: var(--warning);">-${fmtPct(vm.var_95_21d_pct)}</div>
      <div class="text-[11px] font-mono mt-0.5" style="color: var(--text-secondary);">-${fmtVnd(vm.var_95_21d_vnd || 0)} VND (ES: -${fmtPct(vm.cvar_95_21d_pct)})</div>
    </div>
    <div class="swiss-subtle p-3.5 rounded border" style="border-color: var(--border-color);">
      <div class="text-[11px] font-semibold uppercase tracking-wider" style="color: var(--text-muted);">${tr('stress.mdd')}</div>
      ${mddHtml}
    </div>
  `;
  cardsBox.innerHTML = cardsHtml;

  const scenarios = activeProfile.scenarios || [];
  if (scSec) scSec.classList.toggle('hidden', scenarios.length === 0);
  if (scenarios.length === 0) {
    tbl.innerHTML = '';
    return;
  }

  let html = `<thead><tr>
    <th class="sticky-col">Scenario</th>
    <th>Period</th>
    <th class="text-right">Market Shock</th>
    <th class="text-right">100% Equity</th>
    <th class="text-right">Portfolio Impact</th>
    <th class="text-right">Est. Loss (VND)</th>
    <th class="text-right">Post-Shock NAV</th>
    <th class="text-right">Cash Saved</th>
  </tr></thead><tbody>`;

  scenarios.forEach(function (sc) {
    html += `<tr>
      <td class="sticky-col">
        <div class="font-semibold" style="color: var(--text-primary);">${sc.name}</div>
        <div class="text-[11px] font-sans" style="color: var(--text-muted);">${sc.description}</div>
      </td>
      <td class="text-xs" style="color: var(--text-secondary);">${sc.period}</td>
      <td class="text-right font-semibold" style="color: var(--danger);">${fmtPct(sc.market_shock_pct)}</td>
      <td class="text-right" style="color: var(--text-secondary);">${fmtPct(sc.risky_only_impact_pct)}</td>
      <td class="text-right font-semibold" style="color: var(--danger);">${fmtPct(sc.complete_impact_pct)}</td>
      <td class="text-right font-semibold" style="color: var(--danger);">-${fmtVnd(sc.estimated_loss_vnd)}</td>
      <td class="text-right font-semibold">${fmtVnd(sc.post_shock_nav_vnd)}</td>
      <td class="text-right font-semibold" style="color: var(--success);">+${fmtVnd(sc.cash_protection_vnd)}</td>
    </tr>`;
  });

  html += `</tbody>`;
  tbl.innerHTML = html;
}

// --- Tab 04: Asset Moments, CAGR & Covariance ---
function renderMatricesTables(data) {
  const syms = data.symbols || [];
  const assets = data.individual_assets || [];
  const cov = data.cov || [];
  const corr = data.corr || [];

  let htmlStats = `<thead><tr>
    <th class="sticky-col">Ticker</th>
    <th class="text-right">E(R<sub>i</sub>)</th>
    <th class="text-right">CAGR</th>
    <th class="text-right">&sigma;<sub>i</sub></th>
    <th class="text-right">Sharpe</th>
    <th class="text-right">Price (VND)</th>
  </tr></thead><tbody>`;
  assets.forEach(function (a) {
    const pStr = a.latest_price ? fmtVnd(a.latest_price) : '--';
    htmlStats += `<tr>
      <td class="sticky-col font-semibold">${a.symbol}</td>
      <td class="text-right">${fmtPct(a.expected_return)}</td>
      <td class="text-right">${fmtPct(a.cagr)}</td>
      <td class="text-right">${fmtPct(a.volatility)}</td>
      <td class="text-right font-semibold">${fmtNum(a.sharpe_ratio, 3)}</td>
      <td class="text-right">${pStr}</td>
    </tr>`;
  });
  htmlStats += `</tbody>`;
  document.getElementById('tbl-asset-stats').innerHTML = htmlStats;

  let htmlCorr = `<thead><tr><th class="sticky-col">&rho;<sub>i,j</sub></th>`;
  syms.forEach(function (s) { htmlCorr += `<th class="text-right">${s}</th>`; });
  htmlCorr += `</tr></thead><tbody>`;
  for (let i = 0; i < syms.length; i++) {
    htmlCorr += `<tr><td class="sticky-col font-semibold">${syms[i]}</td>`;
    for (let j = 0; j < syms.length; j++) {
      const val = corr[i][j];
      const cls = i === j ? 'font-semibold' : '';
      htmlCorr += `<td class="text-right ${cls}">${fmtNum(val, 3)}</td>`;
    }
    htmlCorr += `</tr>`;
  }
  htmlCorr += `</tbody>`;
  document.getElementById('tbl-corr-matrix').innerHTML = htmlCorr;

  let htmlCov = `<thead><tr><th class="sticky-col">&Sigma;<sub>i,j</sub></th>`;
  syms.forEach(function (s) { htmlCov += `<th class="text-right">${s}</th>`; });
  htmlCov += `</tr></thead><tbody>`;
  for (let i = 0; i < syms.length; i++) {
    htmlCov += `<tr><td class="sticky-col font-semibold">${syms[i]}</td>`;
    for (let j = 0; j < syms.length; j++) {
      htmlCov += `<td class="text-right">${fmtNum(cov[i][j], 5)}</td>`;
    }
    htmlCov += `</tr>`;
  }
  htmlCov += `</tbody>`;
  document.getElementById('tbl-cov-matrix').innerHTML = htmlCov;
}

// --- Tab 05: Merton (1972) Theoretical Reference ---
function renderAlgebraStepByStep(data) {
  const syms = data.symbols || [];
  const invCov = data.inv_cov;
  const sc = data.merton_scalars;
  const mRef = data.merton_unconstrained || {};
  const banner = document.getElementById('algebra-status-banner');
  const invTbl = document.getElementById('tbl-invcov-matrix');
  const scalarsBox = document.getElementById('merton-scalars-box');
  const noteBox = document.getElementById('merton-formulas-note');

  const isSingular = !invCov || !sc || data.merton_status === 'singular_covariance';

  if (banner) {
    if (isSingular) {
      banner.textContent = tr('algebra.singular');
      banner.style.borderColor = 'var(--warning)';
      banner.style.backgroundColor = 'var(--alert-warning-bg)';
    } else if (mRef.is_applied_in_active_portfolio) {
      banner.textContent = tr('algebra.applied_yes');
      banner.style.borderColor = 'var(--accent)';
      banner.style.backgroundColor = 'var(--alert-info-bg)';
    } else {
      banner.textContent = tr('algebra.applied_no');
      banner.style.borderColor = 'var(--warning)';
      banner.style.backgroundColor = 'var(--alert-warning-bg)';
    }
  }

  if (isSingular) {
    if (invTbl) invTbl.innerHTML = `<tbody><tr><td class="p-3 text-center" style="color: var(--text-muted);">${tr('algebra.singular')}</td></tr></tbody>`;
    if (scalarsBox) scalarsBox.innerHTML = '';
    if (noteBox) noteBox.innerHTML = `<div>${tr('algebra.singular')}</div>`;
    return;
  }

  let htmlInv = `<thead><tr><th class="sticky-col">&Sigma;<sup>-1</sup></th>`;
  syms.forEach(function (s) { htmlInv += `<th class="text-right">${s}</th>`; });
  htmlInv += `</tr></thead><tbody>`;
  for (let i = 0; i < syms.length; i++) {
    htmlInv += `<tr><td class="sticky-col font-semibold">${syms[i]}</td>`;
    for (let j = 0; j < syms.length; j++) {
      htmlInv += `<td class="text-right">${fmtNum(invCov[i][j], 3)}</td>`;
    }
    htmlInv += `</tr>`;
  }
  htmlInv += `</tbody>`;
  invTbl.innerHTML = htmlInv;

  const scHtml = `
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
  scalarsBox.innerHTML = scHtml;

  const gmvErClosed = fmtNum((sc.A / sc.C) * 100, 2) + '%';
  const gmvStdClosed = fmtNum(Math.sqrt(Math.max(0, 1.0 / sc.C)) * 100, 2) + '%';
  const unconstW = (mRef.w_tangency || []).map(function (w, idx) { return `${syms[idx]}: ${fmtPct(w, 1)}`; }).join(', ');
  const noteHtml = `
    <div>&bull; <strong>w<sub>GMV</sub> (Unconstrained)</strong> = (&Sigma;<sup>-1</sup> 1)/C &rArr; E(R) = ${gmvErClosed}, &sigma; = ${gmvStdClosed}</div>
    <div>&bull; <strong>w<sub>Tangency</sub> (Unconstrained)</strong>: [${unconstW || '--'}]</div>
    <div>&bull; <strong>y*</strong> = [E(R<sub>T</sub>) - R<sub>f</sub>] / [&gamma; &middot; &sigma;<sub>T</sub>&sup2;]</div>
  `;
  noteBox.innerHTML = noteHtml;
}

// --- Snapshot-Consistent Exports ---
function _getTodayDateTag() {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  return `${y}${m}${d}`;
}

function getCommittedExportBody() {
  if (appState.isDirty || !appState.committedSnapshot) {
    return null;
  }
  const base = appState.committedSnapshot.requestPayload;
  return {
    ...base,
    run_id: appState.committedSnapshot.runId,
    lang: appState.uiLang,
    risk_report_basis: appState.riskReportBasis
  };
}

async function exportCurrentPriceData() {
  const payload = getCommittedExportBody();
  if (!payload) return;
  const btn = document.getElementById('btn-export-prices');
  const oldHtml = btn ? btn.innerHTML : '';
  if (btn) btn.disabled = true;

  try {
    const res = await fetch('/api/export-prices', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const errData = await res.json().catch(function () { return {}; });
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
    showErrorBanner('Export Error', err.message, '');
  } finally {
    if (btn) btn.innerHTML = oldHtml;
    updateExportLockState();
  }
}

async function exportCurrentMatrixData() {
  const payload = getCommittedExportBody();
  if (!payload) return;
  const btn = document.getElementById('btn-export-matrix');
  const oldHtml = btn ? btn.innerHTML : '';
  if (btn) btn.disabled = true;

  try {
    const res = await fetch('/api/export-matrix', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const errData = await res.json().catch(function () { return {}; });
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
    showErrorBanner('Export Error', err.message, '');
  } finally {
    if (btn) btn.innerHTML = oldHtml;
    updateExportLockState();
  }
}

async function exportInstitutionalExcel() {
  const payload = getCommittedExportBody();
  if (!payload) return;
  const btn = document.getElementById('btn-export-excel');
  const oldHtml = btn ? btn.innerHTML : '';
  if (btn) btn.disabled = true;

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
    showErrorBanner('Export Error', err.message, '');
  } finally {
    if (btn) btn.innerHTML = oldHtml;
    updateExportLockState();
  }
}

// --- Fullscreen Responsive Chart Modal (No Modebar / Legend Overlap!) ---
function openChartFullscreen(chartKey) {
  if (!lastAnalysisData) return;
  const modal = document.getElementById('modal-chart-fullscreen');
  const titleEl = document.getElementById('modal-fullscreen-title');
  const subtitleEl = document.getElementById('modal-fullscreen-subtitle');
  const plotContainer = document.getElementById('chart-fullscreen-plot');
  if (!modal || !plotContainer) return;

  if (modal.classList.contains('hidden')) {
    lastFocusedBeforeModal = document.activeElement;
  }
  activeFullscreenChartKey = chartKey;
  let sourceId = 'chart-frontier';

  if (chartKey === 'frontier') {
    sourceId = 'chart-frontier';
    titleEl.textContent = tr('chart.frontier_title');
    subtitleEl.textContent = tr('chart.frontier_sub');
  } else if (chartKey === 'weights') {
    sourceId = 'chart-weights';
    titleEl.textContent = tr('chart.weights_title');
    subtitleEl.textContent = tr('chart.weights_sub');
  } else if (chartKey === 'benchmark') {
    sourceId = 'chart-benchmark-cum';
    const bm = lastAnalysisData.benchmark_comparison || {};
    const sym = (bm.benchmark_symbol || appState.benchmarkSymbol || 'VNINDEX').toUpperCase();
    const rng = (bm.benchmark_range || appState.benchmarkHorizon || '1Y').toUpperCase();
    titleEl.textContent = tr('bm.wealth_title');
    subtitleEl.textContent = `${sym} (${rng})`;
  }

  const sourceEl = document.getElementById(sourceId);
  if (!sourceEl || !sourceEl.data) {
    if (chartKey === 'frontier') renderPlotlyFrontier(lastAnalysisData);
    if (chartKey === 'weights') renderPlotlyWeights(lastAnalysisData);
    if (chartKey === 'benchmark') renderBenchmarkTab(lastAnalysisData);
  }

  const traces = JSON.parse(JSON.stringify((sourceEl && sourceEl.data) ? sourceEl.data : []));
  const layout = JSON.parse(JSON.stringify((sourceEl && sourceEl.layout) ? sourceEl.layout : {}));
  const compact = window.innerWidth < 768;

  delete layout.width;
  delete layout.height;
  layout.autosize = true;
  // Place legend safely at the bottom inside fullscreen modal so Plotly modebar at top-right never overlaps legend!
  layout.margin = compact ? { l: 44, r: 14, t: 44, b: 108 } : { l: 64, r: 28, t: 48, b: 92 };
  layout.legend = {
    orientation: 'h',
    yanchor: 'top',
    y: compact ? -0.22 : -0.14,
    xanchor: 'left',
    x: 0,
    font: { size: compact ? 10 : 11 }
  };
  if (layout.font) layout.font.size = compact ? 10.5 : 12;

  modal.classList.remove('hidden');

  const config = {
    responsive: true,
    displayModeBar: !compact,
    modeBarButtonsToRemove: ['lasso2d'],
    displaylogo: false
  };

  Plotly.newPlot('chart-fullscreen-plot', traces, layout, config).then(function () {
    setTimeout(function () {
      if (window.Plotly) Plotly.Plots.resize('chart-fullscreen-plot');
    }, 30);
  });

  const closeBtn = document.getElementById('btn-fs-close');
  if (closeBtn) closeBtn.focus();
}

function closeChartFullscreen() {
  const modal = document.getElementById('modal-chart-fullscreen');
  if (modal) modal.classList.add('hidden');
  const plot = document.getElementById('chart-fullscreen-plot');
  if (plot && window.Plotly) Plotly.purge(plot);
  activeFullscreenChartKey = null;

  setTimeout(function () {
    ['chart-frontier', 'chart-weights', 'chart-benchmark-cum'].forEach(function (id) {
      const el = document.getElementById(id);
      if (el && window.Plotly) Plotly.Plots.resize(el);
    });
  }, 40);

  if (lastFocusedBeforeModal && typeof lastFocusedBeforeModal.focus === 'function') {
    lastFocusedBeforeModal.focus();
  }
  lastFocusedBeforeModal = null;
}

function resetFullscreenChartPlot() {
  const plot = document.getElementById('chart-fullscreen-plot');
  if (plot && window.Plotly) {
    Plotly.relayout(plot, {
      'xaxis.autorange': true,
      'yaxis.autorange': true
    });
  }
}

window.exportCurrentPriceData = exportCurrentPriceData;
window.exportCurrentMatrixData = exportCurrentMatrixData;
window.exportInstitutionalExcel = exportInstitutionalExcel;
window.openChartFullscreen = openChartFullscreen;
window.closeChartFullscreen = closeChartFullscreen;
window.resetFullscreenChartPlot = resetFullscreenChartPlot;
window.setBenchmarkHorizon = setBenchmarkHorizon;
window.setBenchmarkIndex = setBenchmarkIndex;
window.setLanguage = setLanguage;
window.setRiskReportBasis = setRiskReportBasis;
window.toggleCap20Preset = toggleCap20Preset;
window.toggleTT98Preset = toggleTT98Preset;
